#!/usr/bin/env python3
"""
grimg.py - reader/extractor for the Red Storm Engine PS2 ".img" archives used by
Ghost Recon (SLUS-20613: gr.img, menu.img) and Ghost Recon Jungle Storm
(SLUS-20820: gr.img).

The container is byte-identical in layout to Rainbow Six 3 PS2's vokes*.img.

  64-byte header, all little-endian u32:
     [0] total file size (matches the real file size exactly)
     [1] (unknown / name-table length-ish)
     [2] entry-table offset            (always 0x800)
     [3] entry-table end
     [4] name-table offset
     [5] data start
     [6] 1
     [8] (unknown secondary table offset, lies between [3] and [4])

  Entry table = N * 48-byte records, 12 little-endian u32:
     +0x00 nameOffset   byte offset into the name table, NUL-terminated ASCII
     +0x04 next         *** NOT a sibling pointer ***  see trap below
     +0x08 parent       record index of the containing directory (0 = root)
     +0x0C firstChild
     +0x10 ?
     +0x14 isFile       1 = file, 0 = directory
     +0x18 size
     +0x1C size2        (== size on every record observed)
     +0x20 dataOffset   absolute byte offset in the archive
     +0x24..0x2C ?

  TRAP: +0x04 is the link of ONE globally name-sorted list spanning every
  record in the archive, not a per-directory sibling chain. Walking it from
  record 1 silently drops most of the archive. This reader enumerates the
  record array 0..N-1 and rebuilds each path from the `parent` chain.

Files are LZO-compressed in a chunked container more often than not; --extract and
--cat decompress transparently via rselzo.py (pass --raw to get the stored bytes).

CLI:
  python grimg.py --img A.img [--img B.img] --list [regex]
  python grimg.py --iso "Ghost Recon (USA).iso" --list        (reads GR.IMG + MENU.IMG
                                                               straight out of the ISO)
  python grimg.py --img A.img --extract <regex> --out <dir>
  python grimg.py --img A.img --cat <exact/path>
  python grimg.py --img A.img --census                        (extension tally)
  python grimg.py --img A.img --verify                        (archive integrity)
  python grimg.py --img A.img --sweep                         (decompress everything)
"""

import argparse
import os
import re
import struct
import sys

try:
    import rselzo
except ImportError:
    rselzo = None

REC = 48


SECTOR = 2048


def iso_images(iso_path):
    """Find the *.IMG archives inside a retail ISO. Returns [(name, byteBase)].

    Unlike Rainbow Six 3's disc, the ISO9660 directory record sizes here AGREE
    with each image's own header field [0], on both games' ISOs."""
    fh = open(iso_path, "rb")
    fh.seek(16 * SECTOR)
    pvd = fh.read(SECTOR)
    if pvd[1:6] != b"CD001":
        raise SystemExit("%s is not an ISO9660 image" % iso_path)
    root = pvd[156:190]
    lba = struct.unpack("<I", root[2:6])[0]
    ln = struct.unpack("<I", root[10:14])[0]
    fh.seek(lba * SECTOR)
    d = fh.read(ln)
    out, o = [], 0
    while o < len(d):
        L = d[o]
        if L == 0:
            o = (o // SECTOR + 1) * SECTOR
            if o >= len(d):
                break
            continue
        e = d[o:o + L]
        elba = struct.unpack("<I", e[2:6])[0]
        nl = e[32]
        nm = e[33:33 + nl].decode("latin1").split(";")[0]
        if nm.upper().endswith(".IMG"):
            out.append((nm.lower(), elba * SECTOR))
        o += L
    fh.close()
    return out


class GrImg:
    def __init__(self, path, base=0, name=None):
        """`base` lets the archive live at a byte offset inside a bigger file
        (i.e. inside a retail ISO) instead of being a loose .img."""
        self.path = path
        self.base = base
        self.name = name or os.path.basename(path)
        self.fh = open(path, "rb")
        self.fh.seek(base)
        h = struct.unpack("<16I", self.fh.read(64))
        self.declared_size = h[0]
        self.ent_off, self.ent_end, self.name_off, self.data_off = h[2], h[3], h[4], h[5]
        self.real_size = (os.path.getsize(path) - base) if base == 0 else h[0]
        self.n = (self.ent_end - self.ent_off) // REC
        self.fh.seek(base + self.ent_off)
        self.ent = self.fh.read(self.ent_end - self.ent_off)
        self.fh.seek(base + self.name_off)
        self.names = self.fh.read(self.data_off - self.name_off)
        self.files = {}   # PATH -> (idx, size, offset)
        self.dirs = set()
        self._walk()

    # -- raw record access -------------------------------------------------
    def rec(self, i):
        return struct.unpack("<12I", self.ent[i * REC:(i + 1) * REC])

    def _name(self, o):
        e = self.names.find(b"\0", o)
        return self.names[o:e].decode("latin1")

    def _path(self, i):
        parts, seen = [], set()
        while i and i not in seen:
            seen.add(i)
            r = self.rec(i)
            parts.append(self._name(r[0]))
            i = r[2]
        return "/" + "/".join(reversed(parts))

    def _walk(self):
        for i in range(self.n):
            r = self.rec(i)
            p = self._path(i).upper()
            if r[5] == 1:
                self.files[p] = (i, r[6], r[8])
            else:
                self.dirs.add(p)

    # -- io ----------------------------------------------------------------
    def get(self, path):
        k = path.upper()
        if k not in self.files:
            return None
        _, size, off = self.files[k]
        self.fh.seek(self.base + off)
        return self.fh.read(size)

    def sanity(self):
        """Return a list of human-readable integrity findings."""
        out = []
        out.append("declared size %d, real size %d -> %s"
                   % (self.declared_size, self.real_size,
                      "MATCH" if self.declared_size == self.real_size else "MISMATCH"))
        bad_off = bad_name = 0
        total = 0
        for p, (i, size, off) in self.files.items():
            total += size
            if off < self.data_off or off + size > self.real_size:
                bad_off += 1
            if not p.strip("/"):
                bad_name += 1
        out.append("%d records, %d files, %d dirs" % (self.n, len(self.files), len(self.dirs)))
        out.append("file bytes %d (%.1f%% of archive)" % (total, 100.0 * total / self.real_size))
        out.append("entries with out-of-range data span: %d" % bad_off)
        out.append("entries with empty path: %d" % bad_name)
        return out


def open_all(imgs, isos):
    arcs = [GrImg(p) for p in (imgs or [])]
    for iso in (isos or []):
        for nm, base in iso_images(iso):
            arcs.append(GrImg(iso, base, nm))
    if not arcs:
        raise SystemExit("give --img and/or --iso")
    return arcs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", action="append",
                    help="a loose gr.img / menu.img (repeatable)")
    ap.add_argument("--iso", action="append",
                    help="a retail ISO; every *.IMG inside it is opened (repeatable)")
    ap.add_argument("--list", nargs="?", const=".", default=None)
    ap.add_argument("--extract")
    ap.add_argument("--out", default=".")
    ap.add_argument("--cat")
    ap.add_argument("--census", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--raw", action="store_true",
                    help="do not LZO-decompress on extract/cat")
    ap.add_argument("--sweep", action="store_true",
                    help="try to decompress every file; report the tally")
    a = ap.parse_args()

    arcs = open_all(a.img, a.iso)

    if a.verify:
        for v in arcs:
            print("== %s" % v.name)
            for line in v.sanity():
                print("   " + line)

    if a.list is not None:
        rx = re.compile(a.list, re.I)
        for v in arcs:
            for p in sorted(v.files):
                if rx.search(p):
                    i, size, off = v.files[p]
                    print("%-10s %-62s %10d  0x%09X" % (v.name, p, size, off))

    if a.census:
        from collections import Counter
        c, byte = Counter(), Counter()
        for v in arcs:
            for p, (i, size, off) in v.files.items():
                ext = os.path.splitext(p)[1].upper() or "(none)"
                c[ext] += 1
                byte[ext] += size
        print("%-10s %6s %14s" % ("EXT", "COUNT", "BYTES"))
        for ext, n in c.most_common():
            print("%-10s %6d %14d" % (ext, n, byte[ext]))

    if a.sweep:
        from collections import Counter
        ok, plain, fail = Counter(), Counter(), Counter()
        errs = []
        for v in arcs:
            for p in sorted(v.files):
                ext = os.path.splitext(p)[1].upper() or "(none)"
                d = v.get(p)
                if not rselzo.is_compressed(d):
                    plain[ext] += 1
                    continue
                try:
                    rselzo.decompress(d)
                    ok[ext] += 1
                except Exception as e:
                    fail[ext] += 1
                    if len(errs) < 20:
                        errs.append("%s: %s" % (p, e))
        print("%-10s %8s %8s %8s" % ("EXT", "LZO-OK", "PLAIN", "LZO-FAIL"))
        for ext in sorted(set(ok) | set(plain) | set(fail)):
            print("%-10s %8d %8d %8d" % (ext, ok[ext], plain[ext], fail[ext]))
        print("TOTAL      %8d %8d %8d" % (sum(ok.values()), sum(plain.values()),
                                          sum(fail.values())))
        for e in errs:
            print("  !! " + e)

    if a.extract:
        rx = re.compile(a.extract, re.I)
        n = 0
        for v in arcs:
            for p in sorted(v.files):
                if not rx.search(p):
                    continue
                d = v.get(p)
                if not a.raw and rselzo is not None:
                    try:
                        d = rselzo.unpack(d)
                    except Exception:
                        pass
                dst = os.path.join(a.out, v.name, p.lstrip("/").replace("/", os.sep))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, "wb") as o:
                    o.write(d)
                n += 1
                print("%-62s %10d -> %s" % (p, len(d), dst))
        print("extracted %d file(s)" % n)

    if a.cat:
        for v in arcs:
            d = v.get(a.cat)
            if d is not None:
                if not a.raw and rselzo is not None:
                    try:
                        d = rselzo.unpack(d)
                    except Exception:
                        pass
                sys.stdout.buffer.write(d)
                return
        sys.exit("not found: " + a.cat)


if __name__ == "__main__":
    main()

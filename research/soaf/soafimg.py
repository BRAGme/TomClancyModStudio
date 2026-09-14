"""Sum of All Fears PS2 `MENU.IMG` / `SOAF.IMG` -- a 40-byte-record vokes.

Same family as Rainbow Six 3's `VOKES*.IMG` and Ghost Recon's `GR.IMG`, and the
64-byte u32 header is byte-for-byte the same idea:

    [0] total file size   [2] entry-table offset (0x800)   [3] entry-table end
    [4] name-table offset [5] data start

but **the record is 40 bytes here, not 48**.  Measured, not assumed: MENU.IMG's
table spans 13,280 bytes and SOAF.IMG's spans 98,520, and 40 is the only one of
{32, 40, 48} that divides both (332 and 2,463 records).

    +0x00 u32 nameOffset      byte offset into the name table
    +0x04 u32 next            GLOBAL name-sorted link -- NOT a sibling pointer
    +0x08 u32 parent          record index of the containing directory
    +0x0c u32 firstChild
    +0x10 u32 compressed      0 = stored, 1 = rselzo-wrapped
    +0x14 u32 isFile          1 for files
    +0x18 u32 storedSize      bytes actually occupying the archive
    +0x1c u32 rawSize         == storedSize when compressed == 0
    +0x20 u32 dataOffset      absolute byte offset in the archive
    +0x24 u32 hash            32-bit name hash (see note)

Ghost Recon's 48-byte record has the same first nine fields and three spare
u32s; SOAF drops two of them and adds the hash.  The `compressed` flag at +0x10
is the field Ghost Recon's reader never needed, because there every data file
had to be sniffed -- here the archive says so outright, and the pair
(storedSize, rawSize) is exactly the rselzo container's (in, out) totals.

The +0x24 word is a per-name constant: `COMMON.PAK` carries 0x000120FD in both
MENU.IMG and SOAF.IMG.  That file is also byte-identical in the two archives, so
this evidence does not separate "name hash" from "content checksum" -- treated
here as opaque and preserved on write.

THE TRAP carried over from vokes.py: +0x04 is a single globally name-sorted list
spanning every record, so walking it from record 1 silently drops everything
that sorts before it.  Enumerate the record array and climb `parent` instead.
"""

from __future__ import annotations

import os
import struct

REC = 40


class SoafImgError(Exception):
    pass


class Entry:
    __slots__ = ("index", "path", "size", "raw_size", "offset", "compressed", "hash")

    def __init__(self, index, path, size, raw_size, offset, compressed, hash_):
        self.index = index
        self.path = path
        self.size = size            # bytes in the archive
        self.raw_size = raw_size    # bytes after decompression
        self.offset = offset
        self.compressed = compressed
        self.hash = hash_

    @property
    def ext(self):
        return os.path.splitext(self.path)[1].upper().lstrip(".")

    def __repr__(self):
        return "Entry(%s, size=%d, raw=%d, off=0x%x, lzo=%d)" % (
            self.path, self.size, self.raw_size, self.offset, self.compressed)


class SoafImg:
    def __init__(self, fh, base=0, name="?", owns=False):
        self.fh, self.base, self.name, self._owns = fh, base, name, owns
        h = struct.unpack("<16I", self._read(0, 64))
        self.filesize = h[0]
        self.ent_off, self.ent_end, self.name_off, self.data_start = h[2], h[3], h[4], h[5]
        if self.ent_off != 0x800 or self.ent_end <= self.ent_off:
            raise SoafImgError("%s: entry table at 0x%x..0x%x is not a vokes table"
                               % (name, self.ent_off, self.ent_end))
        span = self.ent_end - self.ent_off
        if span % REC:
            raise SoafImgError("%s: entry table %d bytes is not a multiple of %d"
                               % (name, span, REC))
        self.count = span // REC
        self.ent = bytearray(self._read(self.ent_off, span))
        self.names = self._read(self.name_off, self.data_start - self.name_off)
        self.files: dict[str, Entry] = {}
        self.dirs: dict[str, int] = {}
        self._build()

    @classmethod
    def from_file(cls, path):
        fh = open(path, "rb")
        return cls(fh, 0, os.path.basename(str(path)), owns=True)

    @classmethod
    def from_iso(cls, iso, entry):
        return cls(iso.fh, entry.lba * 2048, entry.path.lstrip("/"))

    def _read(self, off, n):
        self.fh.seek(self.base + off)
        return self.fh.read(n)

    def close(self):
        if self._owns:
            self.fh.close()

    # -- records -----------------------------------------------------------
    def rec(self, i):
        return struct.unpack("<10I", self.ent[i * REC:(i + 1) * REC])

    def _name(self, off):
        end = self.names.find(b"\0", off)
        return self.names[off:end if end >= 0 else None].decode("latin1")

    def _path(self, i):
        parts, seen = [], set()
        while i and i not in seen:
            seen.add(i)
            r = self.rec(i)
            parts.append(self._name(r[0]))
            i = r[2]
        return "/" + "/".join(reversed(parts))

    def _build(self):
        for i in range(1, self.count):
            r = self.rec(i)
            p = self._path(i)
            if r[5] == 1 and r[7]:
                self.files[p.upper()] = Entry(i, p, r[6], r[7], r[8], r[4], r[9])
            elif r[5] != 1:
                self.dirs[p.upper()] = i

    # -- data --------------------------------------------------------------
    def read_raw(self, e) -> bytes:
        """The bytes as they sit in the archive, still compressed if flagged."""
        if isinstance(e, str):
            e = self.files[e.upper()]
        return self._read(e.offset, e.size)

    def read_file(self, e) -> bytes:
        """Decompressed contents."""
        if isinstance(e, str):
            e = self.files[e.upper()]
        blob = self.read_raw(e)
        if not e.compressed:
            return blob
        from tcps2.rselzo import decompress as _rselzo_decompress
        return _rselzo_decompress(blob)


def open_all(folder):
    return {n: SoafImg.from_file(os.path.join(folder, n))
            for n in ("MENU.IMG", "SOAF.IMG")}

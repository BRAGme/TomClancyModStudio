"""Write the tool's edits into the copy the Xbox actually reads.

Why this exists
---------------

`System\\LINEAR.INI` contains::

    File=(Src="System\\xboxufiles.umd",mode=1)

`xboxufiles.umd` is the bundle holding every `.u` package -- `R6Game.u`,
`R6Engine.u`, `Engine.u`, `Core.u`. The game copies it to the Xbox hard-drive
cache at boot and **reuses that copy forever**: the executable carries the bare
filename, a `Z:\\` prefix and a `\\.copy` marker, and `Z:` is partition 1. So a
patch written to the disc is never executed -- the console keeps running the
stale copy off its own hard drive. Proven by reading both: the disc said
`9B 03` and the cached copy said `9A 00`.

That is also why some edits always appeared to work and others never did. Only
`xboxufiles.umd` is in the copy list. `xboxdynamic.umd` -- the 38 ini files,
`R6GameSettings.ini`, the 115 `.tpt` templates -- and the per-level `.LIN`
files are read from the disc every time. An ini edit showing up in game while
a script edit never does is the signature of this, not of a bad patch.

What this does
--------------

After an apply, the whole container is copied from the disc image into the
cached file on the emulated hard drive. The container's length never changes
-- the `.umd` slots are fixed and every edit preserves length -- so this is an
overwrite in place, cluster for cluster, with no allocation anywhere.

Only clusters that are already allocated in the image are written. A qcow2
that would need a new cluster for this is refused rather than grown, because
growing one means touching refcounts and L2 tables, and a half-written
allocation would cost the user their hard drive rather than a play-test.

**Internal snapshots share clusters.** If the image has any, an in-place write
is visible to them too. That is reported rather than prevented: it changes
nothing structurally, and the alternative -- copy-on-write -- is the very
machinery this deliberately does not implement.
"""

from __future__ import annotations

import os
import re
import struct

QCOW_MAGIC = b"QFI\xfb"
L1_MASK = L2_MASK = 0x00FFFFFFFFFFFE00
COMPRESSED = 1 << 62

FATX_MAGIC = b"FATX"
#: a title's `Z:` is partition 1 of the Xbox hard drive
PARTITION1 = 0x00080000
#: FATX reserves 4 KiB for its superblock before the allocation table
FATX_RESERVED = 0x1000
DIR_ENTRY = 64
ATTR_DIRECTORY = 0x10

#: the container the game caches, on the disc and on the hard drive
CONTAINER_ISO = "/SYSTEM/XBOXUFILES.UMD"
CONTAINER_HDD = "system/xboxufiles.umd"


class HddError(Exception):
    pass


# ---------------------------------------------------------------------------
# where xemu keeps its hard drive
# ---------------------------------------------------------------------------
def find_image(toml_path=None):
    """The `hdd_path` out of xemu's config, or None."""
    if toml_path is None:
        base = os.environ.get("APPDATA")
        if not base:
            return None
        toml_path = os.path.join(base, "xemu", "xemu", "xemu.toml")
    try:
        with open(toml_path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return None
    m = re.search(r"^\s*hdd_path\s*=\s*['\"](.+?)['\"]\s*$", text, re.M)
    if not m:
        return None
    path = m.group(1)
    return path if os.path.exists(path) else None


# ---------------------------------------------------------------------------
# qcow2, enough of it
# ---------------------------------------------------------------------------
class Qcow2:
    def __init__(self, path, writable=False):
        self.path = path
        self.fh = open(path, "r+b" if writable else "rb")
        head = self.fh.read(72)
        if head[:4] != QCOW_MAGIC:
            raise HddError("%s is not a qcow2 image" % path)
        (self.version, _bo, _bs, self.cluster_bits, self.size, _crypt,
         self.l1_size, self.l1_off, _rc, _rcc, self.nb_snapshots,
         _so) = struct.unpack(">IQIIQIIQQIIQ", head[4:72])
        self.cluster_size = 1 << self.cluster_bits
        self.l2_bits = self.cluster_bits - 3
        self.l2_size = 1 << self.l2_bits
        self.l1_span = 1 << (self.cluster_bits + self.l2_bits)
        self.fh.seek(self.l1_off)
        self.l1 = struct.unpack(">%dQ" % self.l1_size,
                                self.fh.read(8 * self.l1_size))

    def close(self):
        self.fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def physical(self, guest):
        """Where a guest byte lives in the file, or None if unallocated."""
        l1_i = guest // self.l1_span
        if l1_i >= len(self.l1) or not (self.l1[l1_i] & L1_MASK):
            return None
        l2_i = (guest >> self.cluster_bits) & (self.l2_size - 1)
        self.fh.seek((self.l1[l1_i] & L1_MASK) + 8 * l2_i)
        entry = struct.unpack(">Q", self.fh.read(8))[0]
        if entry & COMPRESSED:
            raise HddError("compressed cluster at guest 0x%X" % guest)
        if not (entry & L2_MASK):
            return None
        return (entry & L2_MASK) + (guest & (self.cluster_size - 1))

    def read(self, guest, length):
        out = bytearray()
        while length > 0:
            take = min(self.cluster_size - (guest & (self.cluster_size - 1)),
                       length)
            phys = self.physical(guest)
            if phys is None:
                out += bytes(take)
            else:
                self.fh.seek(phys)
                chunk = self.fh.read(take)
                out += chunk + bytes(take - len(chunk))
            guest += take
            length -= take
        return bytes(out)

    def write(self, guest, data):
        """Overwrite allocated clusters only. Never grows the image."""
        pos = 0
        while pos < len(data):
            take = min(self.cluster_size - (guest & (self.cluster_size - 1)),
                       len(data) - pos)
            phys = self.physical(guest)
            if phys is None:
                raise HddError(
                    "guest 0x%X is not allocated; this would have to grow the "
                    "image, which is refused" % guest)
            self.fh.seek(phys)
            self.fh.write(data[pos:pos + take])
            guest += take
            pos += take
        self.fh.flush()


# ---------------------------------------------------------------------------
# FATX, enough of it
# ---------------------------------------------------------------------------
class Fatx:
    """One FATX partition, read-only, addressed in GUEST offsets."""

    def __init__(self, img, part_off=PARTITION1, part_len=0x2EE00000):
        self.img = img
        self.start = part_off
        head = img.read(part_off, 18)
        if head[:4] != FATX_MAGIC:
            raise HddError("no FATX partition at guest 0x%X" % part_off)
        self.volume_id, sectors_per_cluster, self.fat_copies = \
            struct.unpack("<IIH", head[4:14])
        self.cluster_bytes = sectors_per_cluster * 512
        clusters = part_len // self.cluster_bytes
        self.entry_size = 2 if clusters < 0xFFF5 else 4
        fat_bytes = clusters * self.entry_size
        fat_bytes = (fat_bytes + 0xFFF) & ~0xFFF          # 4 KiB aligned
        self.fat_off = part_off + FATX_RESERVED
        self.data_off = self.fat_off + fat_bytes * self.fat_copies
        self.clusters = clusters
        self._fat = None

    def _fat_table(self):
        if self._fat is None:
            n = self.clusters
            raw = self.img.read(self.fat_off, n * self.entry_size)
            fmt = "<%d%s" % (n, "H" if self.entry_size == 2 else "I")
            self._fat = struct.unpack(fmt, raw[:n * self.entry_size])
        return self._fat

    def cluster_guest(self, n):
        """Cluster numbers are 1-based; cluster 1 is the root directory."""
        return self.data_off + (n - 1) * self.cluster_bytes

    def chain(self, first):
        end = 0xFFF8 if self.entry_size == 2 else 0xFFFFFFF8
        fat = self._fat_table()
        out, n, seen = [], first, set()
        while n and n < len(fat) and n not in seen:
            out.append(n)
            seen.add(n)
            nxt = fat[n]
            if nxt >= end or nxt == 0:
                break
            n = nxt
        return out

    def entries(self, first_cluster):
        for c in self.chain(first_cluster):
            blob = self.img.read(self.cluster_guest(c), self.cluster_bytes)
            for off in range(0, len(blob), DIR_ENTRY):
                raw = blob[off:off + DIR_ENTRY]
                if len(raw) < DIR_ENTRY:
                    return
                nlen = raw[0]
                if nlen in (0x00, 0xFF):
                    return
                if nlen == 0xE5:
                    continue
                name = raw[2:2 + nlen].decode("latin1")
                attr = raw[1]
                cluster, size = struct.unpack("<II", raw[44:52])
                yield {"name": name, "attr": attr, "cluster": cluster,
                       "size": size, "dir": bool(attr & ATTR_DIRECTORY)}

    def find(self, path):
        """`a/b/c.ext` -> its entry, case-insensitively, or None."""
        cur, ent = 1, None
        for part in [p for p in path.replace("\\", "/").split("/") if p]:
            ent = None
            for e in self.entries(cur):
                if e["name"].lower() == part.lower():
                    ent = e
                    break
            if ent is None:
                return None
            cur = ent["cluster"]
        return ent

    def extents(self, entry):
        """[(guestOffset, length)] covering the file's bytes, in order."""
        out, left = [], entry["size"]
        for c in self.chain(entry["cluster"]):
            if left <= 0:
                break
            take = min(self.cluster_bytes, left)
            out.append((self.cluster_guest(c), take))
            left -= take
        if left > 0:
            raise HddError("%s: cluster chain is %d bytes short"
                           % (entry["name"], left))
        return out


# ---------------------------------------------------------------------------
# the operation
# ---------------------------------------------------------------------------
def cached_state(hdd_path, container=CONTAINER_HDD):
    """(entry, extents) for the cached container, or (None, None)."""
    with Qcow2(hdd_path) as img:
        fs = Fatx(img)
        entry = fs.find(container)
        if entry is None:
            return None, None
        return entry, fs.extents(entry)


def sync(hdd_path, payload, container=CONTAINER_HDD, dry_run=False):
    """Overwrite the cached container with `payload`.

    Returns a dict describing what happened. The length must match exactly:
    the `.umd` slots are fixed and every edit this tool makes preserves
    length, so a mismatch means the assumption broke and writing would be
    wrong.
    """
    with Qcow2(hdd_path, writable=not dry_run) as img:
        fs = Fatx(img)
        entry = fs.find(container)
        if entry is None:
            return {"found": False, "written": 0, "container": container}
        if entry["size"] != len(payload):
            raise HddError(
                "%s is %d bytes on the hard drive and %d on the disc; "
                "refusing to write" % (container, entry["size"],
                                       len(payload)))
        ex = fs.extents(entry)
        same = img.read(ex[0][0], 0) is not None    # keeps the reader honest
        before = b"".join(img.read(off, ln) for off, ln in ex)
        if before == payload:
            return {"found": True, "written": 0, "identical": True,
                    "size": entry["size"], "snapshots": img.nb_snapshots,
                    "container": container}
        if dry_run:
            return {"found": True, "written": 0, "identical": False,
                    "size": entry["size"], "snapshots": img.nb_snapshots,
                    "container": container, "differs": sum(
                        1 for a, b in zip(before, payload) if a != b)}
        pos = 0
        for off, ln in ex:
            img.write(off, payload[pos:pos + ln])
            pos += ln
        after = b"".join(img.read(off, ln) for off, ln in ex)
        if after != payload:
            raise HddError("wrote %s but it did not read back" % container)
        del same
        return {"found": True, "written": pos, "identical": False,
                "size": entry["size"], "snapshots": img.nb_snapshots,
                "container": container}

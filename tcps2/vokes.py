"""The Red Storm / Ubisoft PS2 read-only filesystem.

The same container is used by Rainbow Six 3's `VOKES0/1/2.IMG` and by Ghost
Recon / Ghost Recon Jungle Storm's `GR.IMG` and `MENU.IMG`.

64-byte header of u32:

    [0] total file size          [3] entry-table end
    [1] (count-ish, unused)      [4] name-table offset
    [2] entry-table offset       [5] data start

then 48-byte records, all u32:

    +0x00 nameOffset   +0x04 next      +0x08 parent   +0x0c firstChild
    +0x10 ?            +0x14 isFile    +0x18 size     +0x1c size2
    +0x20 dataOffset   +0x24..0x2c ?

THE TRAP, and it is a costly one: `next` at +0x04 is **not** a sibling pointer.
It is the link of a single globally name-sorted list spanning every record in
the archive. Walking it from record 1 silently drops everything that sorts
before record 1's name -- on the Rainbow Six 3 disc that hid 200 MB of content
including three complete missions. Always enumerate the record array and build
each path by climbing the `parent` chain, which is what this module does.
"""

from __future__ import annotations

import struct

REC = 48


class VokesError(Exception):
    pass


class Region:
    """A vokes archive addressed relative to its own byte 0.

    Backed either by a loose file or by a byte range inside an ISO, so the same
    code patches a disc image and an extracted folder.
    """

    def __init__(self, fh, base, name, owns=False):
        self.fh, self.base, self.name, self._owns = fh, base, name, owns

    @classmethod
    def from_file(cls, path, writable=False):
        fh = open(path, "r+b" if writable else "rb")
        import os
        return cls(fh, 0, os.path.basename(str(path)), owns=True)

    @classmethod
    def from_iso(cls, iso, entry):
        return cls(iso.fh, entry.lba * 2048, entry.path.lstrip("/"))

    def read(self, off, n):
        self.fh.seek(self.base + off)
        return self.fh.read(n)

    def write(self, off, data):
        self.fh.seek(self.base + off)
        self.fh.write(data)

    def close(self):
        if self._owns:
            self.fh.close()


class Entry:
    __slots__ = ("index", "path", "size", "offset")

    def __init__(self, index, path, size, offset):
        self.index, self.path, self.size, self.offset = index, path, size, offset

    def __repr__(self):
        return "Entry(%s, size=%d, offset=0x%x)" % (self.path, self.size, self.offset)


class Vokes:
    def __init__(self, region: Region):
        self.r = region
        h = struct.unpack("<16I", region.read(0, 64))
        self.filesize = h[0]
        self.ent_off, self.ent_end, self.name_off, self.data_off = h[2], h[3], h[4], h[5]
        self.data_start = h[5]
        if self.ent_off != 0x800 or self.ent_end <= self.ent_off:
            raise VokesError("%s: not a vokes archive (table at 0x%x..0x%x)"
                             % (region.name, self.ent_off, self.ent_end))
        span = self.ent_end - self.ent_off
        if span % REC:
            raise VokesError("%s: entry table %d bytes is not a multiple of %d"
                             % (region.name, span, REC))
        self.count = span // REC
        self.ent = bytearray(region.read(self.ent_off, span))
        self.names = region.read(self.name_off, self.data_off - self.name_off)
        self.files: dict[str, Entry] = {}
        self._build()

    # -- records -----------------------------------------------------------
    def rec(self, i):
        return struct.unpack("<12I", self.ent[i * REC:(i + 1) * REC])

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
        for i in range(self.count):
            r = self.rec(i)
            if r[5] == 1 and r[6]:
                self.files[self._path(i).upper()] = Entry(i, self._path(i), r[6], r[8])

    # -- data --------------------------------------------------------------
    def read_file(self, path) -> bytes:
        e = self.files[path.upper()]
        return self.r.read(e.offset, e.size)

    def read_entry(self, e: Entry) -> bytes:
        return self.r.read(e.offset, e.size)

    # -- writing -----------------------------------------------------------
    ALIGN = 16

    def _set_entry(self, e, offset, size):
        base = e.index * REC
        struct.pack_into("<I", self.ent, base + 0x18, size)
        struct.pack_into("<I", self.ent, base + 0x1C, size)
        struct.pack_into("<I", self.ent, base + 0x20, offset)
        self.r.write(self.ent_off + base + 0x18, struct.pack("<II", size, size))
        self.r.write(self.ent_off + base + 0x20, struct.pack("<I", offset))
        e.offset, e.size = offset, size

    def _live_extents(self, exclude=None):
        out = []
        for e in self.files.values():
            if e is exclude:
                continue
            out.append((e.offset, e.offset + e.size))
        out.sort()
        return out

    def free_blocks(self, exclude=None):
        """Byte ranges inside the archive that no file entry covers.

        Includes everything after the last file, which every one of these
        archives pads with 64 KB of zeros. It does NOT assume an uncovered
        range is usable -- see `_is_blank`. Ghost Recon's GR.IMG carries a 6 MiB
        hole that no entry points at and which is full of real data, so
        "nothing references it" is not the same as "it is free".
        """
        blocks = []
        cursor = self.data_start
        for start, end in self._live_extents(exclude):
            if start > cursor:
                blocks.append((cursor, start - cursor))
            cursor = max(cursor, end)
        if cursor < self.filesize:
            blocks.append((cursor, self.filesize - cursor))
        return blocks

    def _is_blank(self, offset, length, budget=1 << 24):
        if length > budget:
            return False
        step = 1 << 16
        for o in range(offset, offset + length, step):
            chunk = self.r.read(o, min(step, offset + length - o))
            if chunk.strip(b"\x00"):
                return False
        return True

    def allocate(self, size, exclude=None):
        """Offset of a 16-byte-aligned, provably empty run of `size` bytes.

        Best fit, so a relocated file lands in the slot a previous relocation
        vacated instead of eating the 64 KB pad at the end of the archive.
        Every candidate is read and required to be all zeros first: an
        unreferenced range is not necessarily an unused one.
        """
        candidates = []
        for start, length in self.free_blocks(exclude):
            aligned = (start + self.ALIGN - 1) & ~(self.ALIGN - 1)
            usable = length - (aligned - start)
            if usable >= size:
                candidates.append((usable, aligned))
        if not candidates:
            raise VokesError("%s has no free run of %d bytes left"
                             % (self.r.name, size))
        for _usable, offset in sorted(candidates):
            if self._is_blank(offset, size):
                return offset
        raise VokesError("%s: every free run big enough for %d bytes holds data "
                         "no file claims -- refusing to write over it"
                         % (self.r.name, size))

    def write(self, path, data):
        """Replace a file, relocating it if it has outgrown its slot.

        Small enough, and it goes back where it was. Too big, and it moves to
        free space and its old slot is zeroed, which both makes the change
        reversible and puts that run back in the pool for the next file.
        """
        e = self.files[path.upper()]
        if len(data) <= e.size:
            self.r.write(e.offset, data)
            if len(data) < e.size:
                self.r.write(e.offset + len(data), b"\x00" * (e.size - len(data)))
            self._set_entry(e, e.offset, len(data))
            return e.offset
        old_off, old_size = e.offset, e.size
        dest = self.allocate(len(data), exclude=e)
        self.r.write(dest, data)
        self._set_entry(e, dest, len(data))
        # Release the old run -- but only the part of it the new one does not
        # occupy. The allocator is allowed to grow a file into its own slot plus
        # the gap next to it, and blindly zeroing the old range would then wipe
        # the bytes just written.
        new_a, new_b = dest, dest + len(data)
        for a, b in ((old_off, min(old_off + old_size, new_a)),
                     (max(old_off, new_b), old_off + old_size)):
            if b > a:
                self.r.write(a, b"\x00" * (b - a))
        return dest

    def replace(self, path, data):
        """Backwards-compatible name for `write`."""
        return self.write(path, data)


def open_archives(iso, pattern=r"/(VOKES\d|GR|MENU)\.IMG$") -> list:
    """Every vokes archive in an ISO, in disc order."""
    out = []
    for ent in iso.find_all(pattern):
        if ent.is_dir:
            continue
        try:
            out.append(Vokes(Region.from_iso(iso, ent)))
        except VokesError:
            continue
    return out

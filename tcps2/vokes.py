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

    def replace(self, path, data):
        """In-place replacement. Must be <= the original size: the data area is
        not relocatable without rebuilding every offset in the archive."""
        e = self.files[path.upper()]
        if len(data) > e.size:
            raise VokesError("%s: replacement is %d bytes, original is %d"
                             % (e.path, len(data), e.size))
        self.r.write(e.offset, data)
        base = e.index * REC
        struct.pack_into("<I", self.ent, base + 0x18, len(data))
        struct.pack_into("<I", self.ent, base + 0x1C, len(data))
        self.r.write(self.ent_off + base + 0x18, struct.pack("<II", len(data), len(data)))
        e.size = len(data)


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

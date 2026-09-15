"""XDVDFS -- the filesystem on an Xbox disc image, read and written in place.

An `.iso` is the shape these games are actually kept in, and extracting one to
edit it is both slow and a good way to end up with two copies that disagree. The
filesystem is small enough to implement properly:

    sector 32 (0x10000)   the volume descriptor
        0x00  char  magic[20]   "MICROSOFT*XBOX*MEDIA"
        0x14  u32   rootDirectorySector
        0x18  u32   rootDirectorySize
        0x7EC char  magic[20]   again, as a terminator

    a directory is a run of sectors holding a binary search tree of entries,
    each one 4-byte aligned:
        u16  leftOffset     in 4-byte units from the start of the directory
        u16  rightOffset    0xFFFF (or 0) means no child
        u32  startSector
        u32  size
        u8   attributes     0x10 = directory
        u8   nameLength
        char name[nameLength]

Two things about this format decide how the rest of this module is written.

**A file is sector-aligned and therefore usually has slack.** Its directory
entry records an exact byte size, but the disc gave it a whole number of 2 KB
sectors, so a file can grow into its own padding without moving anything -- and
the entry's size field is four bytes at a known offset, so growing it is a
32-bit write rather than a rebuild. That is what lets the `.ASS` server scripts,
which exist only as loose files and legitimately change length, be edited on a
disc image as well as in an extracted folder.

**Some images carry a global offset.** Plain xiso rips start the filesystem at
byte 0; redump-style XGD1 and XGD2 images put a lead-in in front of it. So the
descriptor is looked for at each of the known bases and the one that answers is
used, rather than assuming.

Writing opens the image read-write and seeks; nothing is ever rebuilt or
relocated, so a failed edit cannot leave an image with a directory that points
somewhere wrong.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass

SECTOR = 2048
DESCRIPTOR_SECTOR = 32
MAGIC = b"MICROSOFT*XBOX*MEDIA"

#: where the filesystem starts, in the images this is likely to meet. 0 is a
#: plain xiso rip; the others are the lead-in sizes redump uses.
BASES = (0, 0x18300000, 0x2080000, 0xFD90000, 0x1FB20000)

ATTR_DIRECTORY = 0x10

#: a directory tree deeper than this is a corrupt image, not a game
MAX_DEPTH = 16


class XisoError(Exception):
    pass


@dataclass
class Entry:
    path: str          # "/System/default.xbe", as recorded, with real case
    sector: int        # first sector of the data, relative to the base
    size: int          # exact byte length
    directory: bool
    size_field: int    # absolute file offset of the u32 size, for growing it

    @property
    def allocated(self) -> int:
        """Bytes the disc actually gave this file, padding included."""
        return ((self.size + SECTOR - 1) // SECTOR) * SECTOR


class Xiso:
    """One disc image. Open read-only by default."""

    def __init__(self, path, writable=False):
        self.path = os.path.abspath(str(path))
        self.writable = writable
        self._fh = open(self.path, "r+b" if writable else "rb")
        try:
            self.base = self._find_base()
            self.files = {}          # upper-case path -> Entry
            self._read_tree()
        except Exception:
            self._fh.close()
            raise

    # -- lifecycle ---------------------------------------------------------
    def close(self):
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    # -- the volume descriptor --------------------------------------------
    def _find_base(self):
        size = os.path.getsize(self.path)
        for base in BASES:
            offset = base + DESCRIPTOR_SECTOR * SECTOR
            if offset + SECTOR > size:
                continue
            self._fh.seek(offset)
            block = self._fh.read(SECTOR)
            if block[:20] == MAGIC and block[0x7EC:0x7EC + 20] == MAGIC:
                return base
        raise XisoError("no XDVDFS volume descriptor -- not an Xbox disc image")

    def _descriptor(self):
        self._fh.seek(self.base + DESCRIPTOR_SECTOR * SECTOR)
        block = self._fh.read(SECTOR)
        return struct.unpack_from("<II", block, 0x14)

    # -- walking the directory tree ---------------------------------------
    def _read_tree(self):
        root_sector, root_size = self._descriptor()
        pending = [("", root_sector, root_size, 0)]
        while pending:
            prefix, sector, size, depth = pending.pop()
            if not size or depth > MAX_DEPTH:
                continue
            start = self.base + sector * SECTOR
            self._fh.seek(start)
            block = self._fh.read(((size + SECTOR - 1) // SECTOR) * SECTOR)
            for entry in self._walk_node(block, start, 0, prefix):
                self.files[entry.path.upper()] = entry
                if entry.directory:
                    pending.append((entry.path, entry.sector, entry.size,
                                    depth + 1))

    def _walk_node(self, block, start, offset, prefix):
        """Every entry in one directory, iteratively.

        Iteratively rather than by recursion because the tree is the *file
        names'* binary search tree, not the directory hierarchy: a folder with a
        few thousand files is one node chain thousands deep, and Python's
        recursion limit is a thousand.
        """
        out = []
        stack = [offset]
        seen = set()
        while stack:
            at = stack.pop()
            if at in seen or at < 0:
                continue
            seen.add(at)
            byte = at * 4
            if byte + 14 > len(block):
                continue
            left, right, sector, size, attrs, nlen = struct.unpack_from(
                "<HHIIBB", block, byte)
            if nlen == 0 or byte + 14 + nlen > len(block):
                continue
            name = block[byte + 14:byte + 14 + nlen].decode("latin1")
            if name in (".", ".."):
                continue
            out.append(Entry("%s/%s" % (prefix, name), sector, size,
                             bool(attrs & ATTR_DIRECTORY),
                             start + byte + 8))
            for child in (left, right):
                if child not in (0, 0xFFFF):
                    stack.append(child)
        return out

    # -- reading -----------------------------------------------------------
    def read(self, entry: Entry, offset=0, length=None) -> bytes:
        if length is None:
            length = entry.size - offset
        if offset < 0 or length < 0 or offset + length > entry.allocated:
            raise XisoError("%s: read of %d bytes at %d is outside the file"
                            % (entry.path, length, offset))
        self._fh.seek(self.base + entry.sector * SECTOR + offset)
        return self._fh.read(length)

    # -- writing -----------------------------------------------------------
    def write(self, entry: Entry, offset: int, data: bytes):
        """Overwrite bytes inside a file. Never changes its length."""
        if not self.writable:
            raise XisoError("this image was opened read-only")
        if offset + len(data) > entry.allocated:
            raise XisoError("%s: writing %d bytes at %d would run past the "
                            "space the disc gave it"
                            % (entry.path, len(data), offset))
        self._fh.seek(self.base + entry.sector * SECTOR + offset)
        self._fh.write(data)

    def replace(self, entry: Entry, data: bytes):
        """Replace a whole file, growing or shrinking it within its own slack.

        The disc rounded every file up to a sector, so there is usually room to
        grow; what cannot move is the file's start. Anything left over is zeroed
        so a shortened file does not trail its old tail, and the directory
        entry's size field is rewritten so the game is told the new length.
        """
        if not self.writable:
            raise XisoError("this image was opened read-only")
        if len(data) > entry.allocated:
            raise XisoError(
                "%s: %d bytes will not fit the %d the disc allocated. Growing "
                "past a file's own sector padding would mean relocating it, "
                "which this tool does not do."
                % (entry.path, len(data), entry.allocated))
        at = self.base + entry.sector * SECTOR
        self._fh.seek(at)
        self._fh.write(data)
        pad = entry.allocated - len(data)
        if pad:
            self._fh.write(b"\0" * pad)
        if len(data) != entry.size:
            self._fh.seek(entry.size_field)
            self._fh.write(struct.pack("<I", len(data)))
            entry.size = len(data)

    def flush(self):
        if self._fh is not None and self.writable:
            self._fh.flush()


def is_xiso(path) -> bool:
    try:
        with Xiso(path):
            return True
    except (OSError, XisoError, struct.error):
        return False

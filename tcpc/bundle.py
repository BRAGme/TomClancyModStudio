r"""GRIN Diesel `.bundle` archives, as Advanced Warfighter 1 and 2 ship them.

The two GRAW games keep essentially everything in `Bundles\quick.bundle` and
`Bundles\patch.bundle` -- 3.8 GB and 3.7 GB respectively, 47,674 files between
the four of them. Nothing else on this shelf works that way, so this is the one
game family where the stock data has to be read out of an archive before it can
be edited.

**Read-only, and deliberately so.** Nothing here writes a bundle. It does not
need to: Diesel looks a file up on disk before it looks in the archive, so a
change is delivered as a loose file under `Data\` and the multi-gigabyte
archives are never opened for writing. See `games/graw.py`.

## The format

Little-endian throughout, and the whole of it::

    0x00  "BNDL"
    0x04  u32  version            2 in both games
    0x08  u64  index_end          the index runs from 0x10 to here

    then records, until index_end:
      0x01  push directory   u8 marker (always 1), NUL-terminated name
      0x02  file             u64 offset, u32 size,
                             u8 marker (always 1), NUL-terminated name
      0x03  pop directory
      0x00  end of index

File data is stored **uncompressed** at those absolute offsets, contiguously
and in index order -- each entry's offset is the previous one's offset plus its
size, which is what confirmed the field widths in the first place.

The grammar was settled by parsing rather than guessed: all four indexes
consume to exactly `index_end` with no bytes left over, and not one of the
47,674 entries points past the end of its file.
"""

from __future__ import annotations

import os
import struct

MAGIC = b"BNDL"
HEADER = 16

#: push a directory, a file, pop a directory, end
T_DIR, T_FILE, T_POP, T_END = 1, 2, 3, 0


class BundleError(Exception):
    pass


class Bundle:
    """One `.bundle`, opened for reading."""

    def __init__(self, path):
        self.path = str(path)
        self.version = 0
        #: lower-case internal path -> (offset, size)
        self.files = {}
        #: the same paths in the spelling the archive uses
        self.names = {}
        self._fh = None
        self._read_index()

    # -- index -------------------------------------------------------------

    def _read_index(self):
        size = os.path.getsize(self.path)
        with open(self.path, "rb") as fh:
            head = fh.read(HEADER)
            if len(head) < HEADER or head[:4] != MAGIC:
                raise BundleError("%s is not a Diesel bundle"
                                  % os.path.basename(self.path))
            self.version, = struct.unpack_from("<I", head, 4)
            end, = struct.unpack_from("<Q", head, 8)
            if not (HEADER <= end <= size):
                raise BundleError("index end 0x%x is outside the file" % end)
            idx = fh.read(end - HEADER)

        p, stack = 0, []
        while p < len(idx):
            tag = idx[p]
            p += 1
            if tag == T_END:
                break
            if tag == T_POP:
                if stack:
                    stack.pop()
                continue
            if tag not in (T_DIR, T_FILE):
                raise BundleError("unknown record %02x at index+%d" % (tag, p - 1))
            off = length = 0
            if tag == T_FILE:
                off, = struct.unpack_from("<Q", idx, p)
                p += 8
                length, = struct.unpack_from("<I", idx, p)
                p += 4
            p += 1                      # the marker byte, always 1
            stop = idx.index(b"\0", p)
            name = idx[p:stop].decode("latin-1")
            p = stop + 1
            if tag == T_DIR:
                stack.append(name)
                continue
            if off + length > size:
                raise BundleError("%s runs past the end of the archive" % name)
            full = "/".join(stack + [name])
            self.files[full.lower()] = (off, length)
            self.names[full.lower()] = full

    # -- reading -----------------------------------------------------------

    def __contains__(self, rel):
        return _key(rel) in self.files

    def __len__(self):
        return len(self.files)

    def read(self, rel) -> bytes:
        hit = self.files.get(_key(rel))
        if hit is None:
            raise KeyError(rel)
        off, length = hit
        if self._fh is None:
            self._fh = open(self.path, "rb")
        self._fh.seek(off)
        data = self._fh.read(length)
        if len(data) != length:                           # pragma: no cover
            raise BundleError("short read on %s" % rel)
        return data

    def close(self):
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()


class BundleSet:
    """Every bundle a game ships, searched in the right order.

    **`patch.bundle` wins over `quick.bundle`**, which is the whole reason this
    class exists rather than a dict comprehension: the patch is the later data
    and 2,112 of its paths also appear in the 3 GB original. Reading the wrong
    one gives the pre-patch values, silently.
    """

    #: later entries win
    ORDER = ("quick.bundle", "patch.bundle")

    def __init__(self, folder):
        self.folder = str(folder)
        self.bundles = []
        for name in self.ORDER:
            path = os.path.join(self.folder, name)
            if os.path.isfile(path):
                try:
                    self.bundles.append(Bundle(path))
                except BundleError:
                    continue

    def __len__(self):
        return len(self.paths())

    def paths(self) -> list:
        seen = {}
        for b in self.bundles:
            seen.update(b.names)
        return sorted(seen.values())

    def __contains__(self, rel):
        return any(rel in b for b in self.bundles)

    def read(self, rel) -> bytes:
        for b in reversed(self.bundles):
            if rel in b:
                return b.read(rel)
        raise KeyError(rel)

    def find(self, pattern) -> list:
        """Archive paths matching a glob, in the archive's own spelling."""
        from .engine import expand
        return expand(self.paths(), pattern)

    def close(self):
        for b in self.bundles:
            b.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()


def _key(rel):
    return str(rel).replace("\\", "/").lstrip("/").lower()

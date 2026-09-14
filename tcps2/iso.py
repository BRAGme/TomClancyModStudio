"""ISO9660 access for PS2 discs.

Read-only directory parsing plus raw sector read/write, which is all the patcher
needs: every edit this tool makes is byte-size preserving at the ISO level, so
the directory never has to be rebuilt.

Trap worth knowing: some Ubisoft PS2 discs declare a bogus size for their big
archives (Rainbow Six 3 lists VOKES0.IMG as 1 byte). Always take the LBA from
the directory and the size from the file's own header when the two disagree.
"""

from __future__ import annotations

import re
import struct

SECTOR = 2048

#: (raw sector size, offset of the 2048 user bytes within it). A plain .iso is
#: (2048, 0); a CloneCD-style MODE2/2352 .bin carries 2,352-byte sectors with
#: the user data 24 bytes in, and Sum of All Fears ships that way.
GEOMETRIES = ((2048, 0), (2352, 24), (2352, 16), (2336, 8))


class IsoError(Exception):
    pass


class DirEntry:
    __slots__ = ("path", "lba", "size", "is_dir")

    def __init__(self, path, lba, size, is_dir):
        self.path = path
        self.lba = lba
        self.size = size
        self.is_dir = is_dir

    @property
    def offset(self) -> int:
        return self.lba * SECTOR

    def __repr__(self):
        return "DirEntry(%s, lba=%d, size=%d)" % (self.path, self.lba, self.size)


class Iso:
    """An ISO9660 image opened for reading, or for in-place patching."""

    def __init__(self, path, writable=False):
        self.path = str(path)
        self.writable = writable
        self.fh = open(self.path, "r+b" if writable else "rb")
        self._entries = None
        self.raw_sector, self.data_off = self._find_geometry()
        self._check_pvd()

    def _find_geometry(self):
        """Work out the sector layout by looking for CD001 at sector 16."""
        for raw, off in GEOMETRIES:
            try:
                self.fh.seek(16 * raw + off)
                if self.fh.read(6)[1:6] == b"CD001":
                    return raw, off
            except OSError:
                continue
        return 2048, 0            # let _check_pvd produce the real complaint

    @property
    def interleaved(self):
        return self.raw_sector != SECTOR or self.data_off != 0

    # -- lifecycle ---------------------------------------------------------
    def close(self):
        try:
            self.fh.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- sectors -----------------------------------------------------------
    # Everything above this line works in the LOGICAL address space -- the flat
    # stream of 2,048-byte user areas -- and these three translate it to wherever
    # the bytes really sit. On a plain .iso that is a straight seek; on a 2,352-
    # byte CD image it has to step sector by sector.

    def read_logical(self, offset, n):
        if not self.interleaved:
            self.fh.seek(offset)
            return self.fh.read(n)
        out = bytearray()
        while n > 0:
            lba, within = divmod(offset, SECTOR)
            take = min(n, SECTOR - within)
            self.fh.seek(lba * self.raw_sector + self.data_off + within)
            chunk = self.fh.read(take)
            if not chunk:
                break
            out += chunk
            offset += len(chunk)
            n -= len(chunk)
        return bytes(out)

    def write_logical(self, offset, data):
        if not self.writable:
            raise IsoError("ISO opened read-only")
        if not self.interleaved:
            self.fh.seek(offset)
            self.fh.write(data)
            return
        view = memoryview(data)
        while view:
            lba, within = divmod(offset, SECTOR)
            take = min(len(view), SECTOR - within)
            self.fh.seek(lba * self.raw_sector + self.data_off + within)
            self.fh.write(view[:take])
            view = view[take:]
            offset += take

    def read(self, lba, n):
        return self.read_logical(lba * SECTOR, n)

    def read_at(self, byte_offset, n):
        return self.read_logical(byte_offset, n)

    def write(self, lba, data):
        self.write_logical(lba * SECTOR, data)

    def flush(self):
        self.fh.flush()

    # -- directory ---------------------------------------------------------
    def _check_pvd(self):
        pvd = self.read(16, SECTOR)
        if len(pvd) < SECTOR or pvd[1:6] != b"CD001":
            raise IsoError("not an ISO9660 image (no CD001 at sector 16): %s" % self.path)
        self._pvd = pvd

    @property
    def volume_id(self) -> str:
        return self._pvd[40:72].decode("latin1").strip()

    def entries(self) -> dict:
        """Full recursive listing, keyed by upper-case '/'-rooted path."""
        if self._entries is None:
            root = self._pvd[156:190]
            lba = struct.unpack("<I", root[2:6])[0]
            ln = struct.unpack("<I", root[10:14])[0]
            out = {}
            self._walk(lba, ln, "", out, 0)
            self._entries = out
        return self._entries

    def _walk(self, lba, length, prefix, out, depth):
        if depth > 8:
            return
        data = self.read(lba, length)
        o = 0
        while o < len(data):
            rec_len = data[o]
            if rec_len == 0:
                # rest of this sector is padding
                o = (o // SECTOR + 1) * SECTOR
                if o >= len(data):
                    break
                continue
            e = data[o:o + rec_len]
            if len(e) < 33:
                break
            e_lba = struct.unpack("<I", e[2:6])[0]
            e_size = struct.unpack("<I", e[10:14])[0]
            flags = e[25]
            nl = e[32]
            raw_name = e[33:33 + nl]
            o += rec_len
            if nl == 1 and raw_name in (b"\x00", b"\x01"):
                continue  # '.' and '..'
            name = raw_name.decode("latin1").split(";")[0]
            path = prefix + "/" + name
            is_dir = bool(flags & 0x02)
            out[path.upper()] = DirEntry(path, e_lba, e_size, is_dir)
            if is_dir:
                self._walk(e_lba, e_size, path, out, depth + 1)

    def find(self, pattern) -> DirEntry | None:
        """First entry whose path matches `pattern` (case-insensitive regex)."""
        rx = re.compile(pattern, re.I)
        for path, ent in sorted(self.entries().items()):
            if rx.search(path):
                return ent
        return None

    def find_all(self, pattern) -> list:
        rx = re.compile(pattern, re.I)
        return [e for p, e in sorted(self.entries().items()) if rx.search(p)]

    def read_text_file(self, pattern, limit=4096) -> str | None:
        ent = self.find(pattern)
        if ent is None:
            return None
        n = ent.size if 0 < ent.size <= limit else limit
        return self.read(ent.lba, n).decode("latin1", "replace")

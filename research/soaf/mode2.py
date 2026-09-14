"""Present a raw CD image (MODE1/2352 or MODE2/2352) as a plain 2048-byte ISO.

The Sum of All Fears (PS2, SLES-511.80) ships as a .bin/.cue pair whose track is
2352 bytes per sector, not 2048.  `tcps2.iso.Iso` assumes 2048-byte sectors and
seeks with `lba * 2048`, so it cannot open the .bin directly.

This module is a *file-like shim*: it wraps the raw .bin and re-presents it as
the stream of 2048-byte user-data areas, so `Iso` -- and `vokes.Region`, which
also seeks by absolute byte offset into `iso.fh` -- work unmodified.

Sector layout actually measured on this disc (not assumed):

    offset  0..11   sync  00 FF FF FF FF FF FF FF FF FF FF 00
    offset 12..14   MSF address (BCD)
    offset 15       mode byte           -- 0x02 on this disc
    offset 16..23   subheader, 8 bytes  -- MODE2 FORM1 (XA)
    offset 24..2071 2048 bytes of user data
    offset 2072..   EDC/ECC

So the user-data window is [24, 24+2048).  `detect_layout()` re-derives that
window from the image instead of hard-coding it: it hunts for the `CD001`
descriptor and reports the sector size and the data offset that put it at
sector 16 + 1.

Usage:

    from mode2 import open_iso
    iso = open_iso(r"...\\game.bin")     # returns a tcps2.iso.Iso
    for p, e in sorted(iso.entries().items()): ...

`open_iso` transparently falls back to a plain 2048 ISO, so it is safe to use as
the general entry point for any PS2 image.
"""

from __future__ import annotations

import io
import os
import struct

USER = 2048

# (raw sector size, offset of user data within the sector)
LAYOUTS = (
    (2048, 0),     # plain ISO / MODE1 cooked
    (2352, 16),    # MODE1/2352
    (2352, 24),    # MODE2/2352 FORM1  <- Sum of All Fears
    (2336, 8),     # MODE2/2336
    (2448, 24),    # 2352 + 96 bytes subchannel
)


class Mode2Error(Exception):
    pass


def detect_layout(path):
    """Return (raw_sector_size, data_offset) by finding CD001 at sector 16.

    Verified rather than guessed: the candidate is accepted only if the
    descriptor at sector 16 is a primary volume descriptor (type 1) and the
    terminator chain at sector 16+n ends in a type-255 `CD001` record.
    """
    size = os.path.getsize(path)
    with open(path, "rb") as fh:
        for raw, off in LAYOUTS:
            if size % raw:
                continue
            fh.seek(16 * raw + off)
            blk = fh.read(USER)
            if len(blk) < USER or blk[1:6] != b"CD001" or blk[0] != 1:
                continue
            # walk the descriptor chain to a terminator -- proves the stride
            ok = False
            for n in range(1, 16):
                fh.seek((16 + n) * raw + off)
                d = fh.read(7)
                if len(d) < 7 or d[1:6] != b"CD001":
                    break
                if d[0] == 255:
                    ok = True
                    break
            if ok:
                return raw, off
    raise Mode2Error("no ISO9660 volume descriptor found in %s" % path)


class Mode2File(io.RawIOBase):
    """Read-only file object over the 2048-byte user data of a 2352 image.

    Seek/read positions are in *cooked* space, so byte N here is byte
    N % 2048 of cooked sector N // 2048, i.e. raw offset
    (N // 2048) * raw_sector + data_offset + (N % 2048).
    """

    def __init__(self, path, raw_sector=None, data_offset=None):
        self.path = str(path)
        if raw_sector is None or data_offset is None:
            raw_sector, data_offset = detect_layout(self.path)
        self.raw_sector = raw_sector
        self.data_offset = data_offset
        self._fh = open(self.path, "rb")
        self._raw_size = os.path.getsize(self.path)
        self.sectors = self._raw_size // raw_sector
        self._size = self.sectors * USER
        self._pos = 0

    # -- io.RawIOBase contract --------------------------------------------
    def readable(self):
        return True

    def writable(self):
        return False

    def seekable(self):
        return True

    def tell(self):
        return self._pos

    def seek(self, off, whence=io.SEEK_SET):
        if whence == io.SEEK_SET:
            self._pos = off
        elif whence == io.SEEK_CUR:
            self._pos += off
        else:
            self._pos = self._size + off
        if self._pos < 0:
            self._pos = 0
        return self._pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = max(0, self._size - self._pos)
        out = bytearray()
        pos = self._pos
        while n > 0 and pos < self._size:
            lba, within = divmod(pos, USER)
            take = min(n, USER - within)
            self._fh.seek(lba * self.raw_sector + self.data_offset + within)
            blk = self._fh.read(take)
            if not blk:
                break
            out += blk
            pos += len(blk)
            n -= len(blk)
            if len(blk) < take:
                break
        self._pos = pos
        return bytes(out)

    def readinto(self, b):
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)

    def close(self):
        try:
            self._fh.close()
        finally:
            super().close()

    # -- convenience -------------------------------------------------------
    def read_sector(self, lba, n=1):
        self.seek(lba * USER)
        return self.read(n * USER)

    def raw_sector_bytes(self, lba):
        """The whole 2352-byte sector, sync header and all (for inspection)."""
        self._fh.seek(lba * self.raw_sector)
        return self._fh.read(self.raw_sector)


def open_iso(path):
    """Open any PS2 image as a `tcps2.iso.Iso`, cooking 2352 images on the fly."""
    from tcps2.iso import Iso

    raw, off = detect_layout(path)
    if raw == USER and off == 0:
        return Iso(path)

    iso = Iso.__new__(Iso)
    iso.path = str(path)
    iso.writable = False
    iso.fh = Mode2File(path, raw, off)
    iso._entries = None
    iso._check_pvd()
    return iso


if __name__ == "__main__":
    import sys

    p = sys.argv[1]
    raw, off = detect_layout(p)
    print("layout: %d-byte sectors, user data at +%d" % (raw, off))
    iso = open_iso(p)
    print("volume id: %r" % iso.volume_id)
    for path, e in sorted(iso.entries().items()):
        print("%-40s lba=%-8d size=%d%s" % (e.path, e.lba, e.size, "  <DIR>" if e.is_dir else ""))

"""Uniform word access to the two kinds of patchable image on these discs.

  soz  Rainbow Six 3's `SP.SOZ`: `u32 size` + one zlib stream in a fixed extent,
       decompressed to a flat image that loads at a fixed address.

  raw  Ghost Recon's and Jungle Storm's boot ELF, which is not compressed at
       all. A virtual address maps to a file offset by the program header, so
       words are read and written straight through the disc image without ever
       holding 37 MB in memory.

Both present `read_word` / `write_word` in virtual addresses, so a game profile
never has to care which it is patching.
"""

from __future__ import annotations

import hashlib
import struct

from .soz import SozImage


class OverlayError(Exception):
    pass


class SozOverlay:
    kind = "soz"

    def __init__(self, iso, entry, spec):
        self.iso, self.entry, self.spec = iso, entry, spec
        self.img = SozImage.unpack(iso.read(entry.lba, entry.size), spec.base_va)
        if spec.image_size and len(self.img.image) != spec.image_size:
            raise OverlayError(
                "%s decompresses to %d bytes, expected %d -- this is not the "
                "disc revision the profile was built for"
                % (spec.name, len(self.img.image), spec.image_size))

    def read_word(self, va):
        return self.img.read_word(va)

    def write_word(self, va, value):
        self.img.write_word(va, value)

    def sha1(self):
        return hashlib.sha1(bytes(self.img.image)).hexdigest()

    def container(self):
        return self.img.pack()

    def store(self):
        self.iso.write(self.entry.lba, self.img.pack())
        self.iso.flush()


class RawOverlay:
    """An uncompressed file inside the ISO, patched in place.

    No backup container is kept for these: the file is tens of megabytes and
    the only bytes that ever change are the handful of words in the profile, so
    the original words are recorded in a small sidecar instead.
    """

    kind = "raw"

    def __init__(self, iso, entry, spec):
        self.iso, self.entry, self.spec = iso, entry, spec
        self.base = entry.lba * 2048
        self.delta = spec.file_delta
        self.limit = spec.file_span or entry.size
        self._dirty = {}

    def _off(self, va):
        off = va - self.spec.base_va + self.delta
        if not (0 <= off <= self.limit - 4):
            raise OverlayError("VA 0x%08x is outside %s" % (va, self.spec.name))
        return self.base + off

    def read_word(self, va):
        if va in self._dirty:
            return self._dirty[va]
        return struct.unpack("<I", self.iso.read_at(self._off(va), 4))[0]

    def write_word(self, va, value):
        self._dirty[va] = value & 0xFFFFFFFF

    def sha1(self):
        return ""          # not hashed: see the class docstring

    def store(self):
        for va, value in self._dirty.items():
            self.iso.write_logical(self._off(va), struct.pack("<I", value))
        self.iso.flush()
        self._dirty.clear()


def open_overlay(iso, spec):
    ent = iso.find(spec.iso_pattern)
    if ent is None:
        raise OverlayError("%s is not on this disc" % spec.name)
    if spec.kind == "soz":
        return SozOverlay(iso, ent, spec)
    return RawOverlay(iso, ent, spec)

"""The `.SOZ` overlay container used by Rainbow Six 3 PS2.

Layout is trivially simple: `u32 uncompressedSize` followed by one zlib stream,
stored in a fixed ISO extent. The EE loads the decompressed image at a fixed
base (0x00100000 for SP.SOZ), so a virtual address maps to a file offset by
subtraction and the overlay can be patched like a flat binary.

The only constraint is the extent: the re-compressed container must fit in the
bytes the disc already reserves for it, otherwise the ISO directory would have
to be rebuilt. In practice re-deflating at maximum effort beats the disc's own
packer by a comfortable margin.
"""

from __future__ import annotations

import struct
import zlib


class SozError(Exception):
    pass


class SozImage:
    """A decompressed overlay image plus the machinery to put it back."""

    def __init__(self, image: bytes, base_va: int, extent: int):
        self.image = bytearray(image)
        self.base_va = base_va
        self.extent = extent

    # -- word access -------------------------------------------------------
    def _off(self, va):
        off = va - self.base_va
        if not (0 <= off <= len(self.image) - 4):
            raise SozError("VA 0x%08x is outside the overlay image" % va)
        return off

    def read_word(self, va) -> int:
        return struct.unpack_from("<I", self.image, self._off(va))[0]

    def write_word(self, va, value):
        struct.pack_into("<I", self.image, self._off(va), value & 0xFFFFFFFF)

    # -- container ---------------------------------------------------------
    def pack(self) -> bytes:
        body = bytes(self.image)
        best = min((zlib.compress(body, lvl) for lvl in (9, 8, 7, 6)), key=len)
        blob = struct.pack("<I", len(body)) + best
        if len(blob) > self.extent:
            raise SozError(
                "re-compressed overlay is %d bytes, %d too big for its %d-byte extent"
                % (len(blob), len(blob) - self.extent, self.extent))
        blob += b"\0" * (self.extent - len(blob))
        if zlib.decompress(blob[4:]) != body:
            raise SozError("round-trip check failed -- refusing to write")
        return blob

    @classmethod
    def unpack(cls, container: bytes, base_va: int) -> "SozImage":
        if len(container) < 8:
            raise SozError("overlay container is truncated")
        declared = struct.unpack_from("<I", container)[0]
        try:
            image = zlib.decompressobj().decompress(container[4:])
        except zlib.error as exc:
            raise SozError("overlay does not decompress: %s" % exc) from exc
        if len(image) != declared:
            raise SozError("overlay declares %d bytes but yields %d" % (declared, len(image)))
        return cls(image, base_va, len(container))


def load_from_iso(iso, entry, base_va) -> SozImage:
    container = iso.read(entry.lba, entry.size)
    return SozImage.unpack(container, base_va)


def store_to_iso(iso, entry, soz: SozImage):
    blob = soz.pack()
    if len(blob) != entry.size:
        raise SozError("packed container is %d bytes, extent is %d" % (len(blob), entry.size))
    iso.write(entry.lba, blob)
    iso.flush()

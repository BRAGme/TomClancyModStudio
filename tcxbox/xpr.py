"""Xbox Packed Resources -- the `.XPR` textures Ghost Recon 2 uses for its UI.

Ghost Recon 2 and Summit Strike replaced the first game's `.RSB` bitmaps with
the console's own container. An XPR is a D3D resource written straight out of
memory, so nothing in it is a picture format in its own right: the header holds
the `D3DPixelContainer` fields and the body is whatever the GPU wanted.

    0x00  'XPR0'
    0x04  u32 totalSize
    0x08  u32 headerSize      -- where the pixels begin, 0x800 in practice
    0x18  u32 Format          -- the packed D3D format word

and the Format word unpacks as

    bits  8..15  D3DFMT code
    bits 16..19  mip levels
    bits 20..23  log2 width
    bits 24..27  log2 height

Across Ghost Recon 2's UI folder that comes out as 52 A8R8G8B8, 16 R5G6B5, 11
DXT1 and one DXT5 -- and the two uncompressed ones are **swizzled**, which is
the part worth getting right. Xbox stores an uncompressed texture in Morton
order, so a naive read gives a picture assembled out of correctly coloured
4 x 4 tiles in the wrong places. Morton order is separable -- the address is the
bits of x and y interleaved -- so the inverse is two small lookup tables and one
gather rather than a per-pixel bit loop, which matters when the menu backdrop is
half a million pixels.

Compressed formats are never swizzled: a DXT block is already a tile.
"""

from __future__ import annotations

import struct

MAGIC = b"XPR0"

#: the Xbox D3DFMT codes these games actually use
FMT_R5G6B5 = 0x05
FMT_A8R8G8B8 = 0x06
FMT_X8R8G8B8 = 0x07
FMT_DXT1 = 0x0C
FMT_DXT3 = 0x0E
FMT_DXT5 = 0x0F
#: the linear (already unswizzled) variants, which need no deswizzle
LINEAR = {0x1E, 0x1F, 0x20, 0x2E, 0x2F, 0x30}


class XprError(Exception):
    pass


def parse(data: bytes):
    """(pixelOffset, formatCode, width, height, mipLevels)."""
    if data[:4] != MAGIC:
        raise XprError("not an XPR0 resource")
    _total, header = struct.unpack_from("<II", data, 4)
    fmt, = struct.unpack_from("<I", data, 0x18)
    code = (fmt >> 8) & 0xFF
    mips = (fmt >> 16) & 0xF
    width = 1 << ((fmt >> 20) & 0xF)
    height = 1 << ((fmt >> 24) & 0xF)
    if not 0 < header < len(data):
        raise XprError("the pixel offset is outside the file")
    return header, code, width, height, mips


def is_xpr(data: bytes) -> bool:
    try:
        parse(data)
        return True
    except (XprError, struct.error):
        return False


def _morton_tables(width, height):
    """(xTable, yTable) such that offset = xTable[x] | yTable[y]."""
    logw = max(width.bit_length() - 1, 0)
    logh = max(height.bit_length() - 1, 0)
    n = min(logw, logh)
    xs = []
    for x in range(width):
        v = 0
        for i in range(n):
            v |= ((x >> i) & 1) << (2 * i)
        if logw > logh:
            v |= (x >> n) << (2 * n)
        xs.append(v)
    ys = []
    for y in range(height):
        v = 0
        for i in range(n):
            v |= ((y >> i) & 1) << (2 * i + 1)
        if logh > logw:
            v |= (y >> n) << (2 * n)
        ys.append(v)
    return xs, ys


def _deswizzle(raw: bytes, width, height, stride) -> bytes:
    xs, ys = _morton_tables(width, height)
    out = bytearray(width * height * stride)
    pos = 0
    for y in range(height):
        ybase = ys[y]
        for x in range(width):
            src = (ybase | xs[x]) * stride
            out[pos:pos + stride] = raw[src:src + stride]
            pos += stride
    return bytes(out)


def to_image(data: bytes):
    """A Pillow image for the top mip level."""
    from PIL import Image

    offset, code, width, height, _mips = parse(data)
    raw = data[offset:]

    if code in (FMT_DXT1, FMT_DXT3, FMT_DXT5):
        blocks = {FMT_DXT1: 1, FMT_DXT3: 2, FMT_DXT5: 3}[code]
        need = (width // 4) * (height // 4) * (8 if code == FMT_DXT1 else 16)
        return Image.frombytes("RGBA", (width, height), raw[:need], "bcn",
                               blocks)

    if code in (FMT_A8R8G8B8, FMT_X8R8G8B8) or code in LINEAR:
        stride = 4
        body = raw[:width * height * stride]
        if code not in LINEAR:
            body = _deswizzle(body, width, height, stride)
        mode = "BGRA" if code == FMT_A8R8G8B8 else "BGRX"
        return Image.frombytes("RGBA" if code == FMT_A8R8G8B8 else "RGB",
                               (width, height), body, "raw", mode)

    if code == FMT_R5G6B5:
        body = _deswizzle(raw[:width * height * 2], width, height, 2)
        return Image.frombytes("RGB", (width, height), body, "raw", "BGR;16")

    raise XprError("D3D format 0x%02X is not one this reads" % code)

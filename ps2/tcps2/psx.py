"""Rainbow Six Lockdown's `.PSX` textures.

Lockdown stores every menu texture as a `.PSX`: a 70-byte header, a CLUT, and
one byte per pixel. The pixels are not a raster. They are the *transfer* the
game hands to the PS2 graphics synthesiser, so the file is in GS upload order
and reading it straight out gives noise.

The chain, each link established against a PCSX2 GS dump of the main menu
rather than assumed:

1. The file is a linear PSMCT32 (32-bit) transfer, `tw` x `th` pixels. Those
   two dimensions are in the header at +4 and +6 -- a 256x256 texture ships as
   a 512x32 transfer, which is exactly eight GS pages in a row.
2. The GS scatters that transfer into local memory by its PSMCT32 addressing.
   Comparing the file against the 4 MB memory snapshot in the dump showed this
   step is a permutation of 8-byte groups, and fitting it recovered a bijective
   13-bit index permutation that reproduces GS memory byte for byte.
3. The texture unit then reads that memory back as PSMT8 (8-bit indexed). The
   within-page order below was derived from the verified permutation and the
   known-good picture, then checked as a closed form on all 8192 entries.

So decoding runs step 3 forward and step 2 backwards. The result matches the
screenshot embedded in the dump.

A second `.PSX` variant (header +12 == 4) carries a 64-byte CLUT and is not
indexed colour; those are mask textures and are not decoded here.
"""

from __future__ import annotations

import struct

#: byte offsets of the four 16x4 columns that make up a 16x16 PSMT8 block
_COL64 = (
    (0,  4, 16, 20, 32, 36, 48, 52,  2,  6, 18, 22, 34, 38, 50, 54),
    (8, 12, 24, 28, 40, 44, 56, 60, 10, 14, 26, 30, 42, 46, 58, 62),
    (33, 37, 49, 53, 1, 5, 17, 21, 35, 39, 51, 55,  3,  7, 19, 23),
    (41, 45, 57, 61, 9, 13, 25, 29, 43, 47, 59, 63, 11, 15, 27, 31),
)
#: which block of a 128x64 page holds a given 16x16 tile
_BLOCK8 = (
    (0,  1,  4,  5, 16, 17, 20, 21),
    (2,  3,  6,  7, 18, 19, 22, 23),
    (8,  9, 12, 13, 24, 25, 28, 29),
    (10, 11, 14, 15, 26, 27, 30, 31),
)
#: PSMCT32: which block of a 64x32 page, and which word inside a column
_BLOCK32 = (
    (0,  1,  4,  5, 16, 17, 20, 21),
    (2,  3,  6,  7, 18, 19, 22, 23),
    (8,  9, 12, 13, 24, 25, 28, 29),
    (10, 11, 14, 15, 26, 27, 30, 31),
)
_COLWORD32 = ((0, 1, 4, 5, 8, 9, 12, 13),
              (2, 3, 6, 7, 10, 11, 14, 15))

_LUT_CACHE = {}


class PsxError(Exception):
    pass


def _psmt8(x, y, width):
    """Byte address in GS memory of texel (x, y) of a `width`-wide PSMT8 image."""
    page = (x // 128) + (y // 64) * max(1, width // 128)
    px, py = x % 128, y % 64
    col = (py >> 2) & 3
    xi = px & 15
    if col & 1:
        # odd columns swap the halves of each run of eight -- this is the term
        # that separates PSMT8 from a plain bit permutation
        xi = (xi & ~7) | ((xi + 4) & 7)
    return (page * 8192
            + _BLOCK8[(py >> 4) & 3][(px >> 4) & 7] * 256
            + col * 64 + _COL64[py & 3][xi])


def _psmct32(x, y, width):
    """Byte address in GS memory of 32-bit pixel (x, y) of a `width`-wide buffer."""
    page = (x // 64) + (y // 32) * max(1, width // 64)
    px, py = x % 64, y % 32
    return (page * 2048
            + _BLOCK32[py // 8][px // 8] * 64
            + ((py % 8) // 2) * 16          # column index within the block
            + _COLWORD32[py & 1][px & 7]) * 4


def _order(width, height, tw):
    """For each output texel, the index of the file byte holding it."""
    key = (width, height, tw)
    table = _LUT_CACHE.get(key)
    if table is None:
        n = width * height
        # step 2, backwards: GS address -> position in the linear transfer
        back = [0] * n
        for m in range(n):
            word = m >> 2
            addr = _psmct32(word % tw, word // tw, tw) + (m & 3)
            if addr < n:
                back[addr] = m
        # step 3, forwards: texel -> GS address
        table = [back[_psmt8(x, y, width)]
                 for y in range(height) for x in range(width)]
        _LUT_CACHE[key] = table
    return table


def _unswizzle_clut(pal):
    """PS2 256-entry CLUTs ship with entries 8..15 and 16..23 of each block of
    32 exchanged."""
    out = bytearray(pal)
    for base in range(0, len(pal) // 4, 32):
        for j in range(8):
            a, b = (base + 8 + j) * 4, (base + 16 + j) * 4
            out[a:a + 4], out[b:b + 4] = pal[b:b + 4], pal[a:a + 4]
    return bytes(out)


def header(blob):
    """(width, height, transfer width, transfer height, clut selector)."""
    if len(blob) < 70:
        raise PsxError("PSX is too short to hold a header")
    w, h, tw, th = struct.unpack_from("<HHHH", blob)
    return w, h, tw, th, blob[12]


def to_image(blob):
    """Return an RGBA PIL image, or None for the variants we do not decode."""
    try:
        from PIL import Image
    except ImportError:
        return None
    w, h, tw, th, sel = header(blob)
    if sel != 8 or not (0 < w <= 4096 and 0 < h <= 4096) or not tw:
        return None
    if tw * th * 4 != w * h:
        # the header's own consistency check: the transfer must carry exactly
        # as many bytes as the image has pixels
        return None
    if len(blob) < 70 + 1024 + w * h:
        return None
    pal = _unswizzle_clut(blob[70:70 + 1024])
    px = blob[70 + 1024:70 + 1024 + w * h]
    img = Image.new("RGBA", (w, h))
    img.putdata([(pal[px[i] * 4], pal[px[i] * 4 + 1], pal[px[i] * 4 + 2],
                  min(255, pal[px[i] * 4 + 3] * 2))
                 for i in _order(w, h, tw)])
    return img

"""Red Storm Engine PS2 `.RSB` bitmaps, as shipped in Ghost Recon and Jungle
Storm, decoded far enough to skin this tool with the games' own artwork.

Lifted from the format work in `research/rsb.py` and trimmed to the decoder.
Two PS2 traps that usually apply were checked and **refuted** for this format:
there is no CLUT swizzle, and alpha really is 0-255 rather than the 0-128 the
hardware normally uses -- the maximum alpha byte across both games is 255.
"""

from __future__ import annotations

from . import rselzo as _rselzo

import argparse
import os
import re
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

                                                   # noqa: E402
                                                  # noqa: E402

HDR = 28

# properties-trailer size, by version (direct-colour rasters only)
TRAILER = {4: 53, 5: 61, 6: 65}

# REFUTED by experiment - see module docstring.  Left in as a switch so the
# test can be reproduced.
SWIZZLE_CLUT256 = False


class RsbError(Exception):
    pass


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def maybe_unpack(data):
    """Decompress an rselzo container; pass plain data straight through."""
    try:
        return _rselzo.unpack(data)
    except Exception:
        return data


def unswizzle_clut256(pal):
    """PS2 256-entry CLUT de-interleave: swap [i+8:i+16] with [i+16:i+24]
    for every block of 32 entries.  `pal` is a list of 256 4-tuples."""
    out = list(pal)
    for i in range(0, 256, 32):
        out[i + 8:i + 16], out[i + 16:i + 24] = \
            pal[i + 16:i + 24], pal[i + 8:i + 16]
    return out


def read_palette(data, off, n, swizzle=False):
    """Palette entries are stored B,G,R,A in memory order.  Returned as
    R,G,B,A tuples ready for PNG."""
    pal = []
    for i in range(n):
        b, g, r, a = data[off + i * 4: off + i * 4 + 4]
        pal.append((r, g, b, a))
    if swizzle and n == 256:
        pal = unswizzle_clut256(pal)
    return pal


# --------------------------------------------------------------------------
# minimal PNG writer (no Pillow dependency)
# --------------------------------------------------------------------------

def write_png(path, w, h, rgba):
    """rgba: bytes/bytearray of len w*h*4."""
    raw = bytearray()
    stride = w * 4
    for y in range(h):
        raw.append(0)                       # filter type 0 (None)
        raw += rgba[y * stride:(y + 1) * stride]

    def chunk(tag, payload):
        return (struct.pack('>I', len(payload)) + tag + payload +
                struct.pack('>I', zlib.crc32(tag + payload) & 0xffffffff))

    ihdr = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk(b'IHDR', ihdr))
        f.write(chunk(b'IDAT', zlib.compress(bytes(raw), 9)))
        f.write(chunk(b'IEND', b''))


# --------------------------------------------------------------------------
# the decoder
# --------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# version 8 -- The Sum of All Fears
# ---------------------------------------------------------------------------
#
# The version 6 header with seven bytes inserted after `height`, which pushes
# the channel depths to +19/+23/+27/+31 and the pixels to **+35** -- an odd
# offset, which is unusual enough to be worth stating. It was measured rather
# than guessed: scanning candidate bases 28..43 and scoring each by mean
# horizontal colour difference gives about 88 for every even base and about 16
# for every odd one, and `35 + w*h*bpp/8 + 66 == filesize` then closes exactly
# on every file. 16-bit pixels are RGB565 with red in the high bits, confirmed
# by a US flag coming out red, white and blue rather than blue, white and red.

V8_HDR = 35
V8_TRAILER = 66


def is_v8(data):
    return len(data) >= 36 and struct.unpack_from("<I", data, 0)[0] == 8


def parse_v8(data):
    w, h = struct.unpack_from("<II", data, 4)
    rb, gb, bb, ab = data[19], data[23], data[27], data[31]
    bpp = rb + gb + bb + ab
    if bpp not in (16, 32):
        raise RsbError("v8 bpp %d (%d,%d,%d,%d) not handled"
                       % (bpp, rb, gb, bb, ab))
    need = V8_HDR + w * h * bpp // 8 + V8_TRAILER
    if need != len(data):
        raise RsbError("v8 size mismatch: %dx%d bpp%d wants %d, file is %d"
                       % (w, h, bpp, need, len(data)))
    npx = w * h
    out = bytearray(npx * 4)
    if bpp == 16:
        for i, v in enumerate(struct.unpack_from("<%dH" % npx, data, V8_HDR)):
            r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
            out[i * 4 + 0] = (r << 3) | (r >> 2)
            out[i * 4 + 1] = (g << 2) | (g >> 4)
            out[i * 4 + 2] = (b << 3) | (b >> 2)
            out[i * 4 + 3] = 255
    else:
        px = data[V8_HDR:V8_HDR + npx * 4]
        for i in range(npx):
            r, g, b, a = px[i * 4:i * 4 + 4]
            out[i * 4:i * 4 + 4] = bytes((r, g, b, min(255, a * 2)))
    return dict(kind="raster", version=8, width=w, height=h,
                mask=(rb, gb, bb, ab), bpp=bpp, rgba=bytes(out))


def parse(data):
    """Return a dict describing an RSB.

    kind == 'jpeg'  -> keys: version, name, jpeg (bytes)
    kind == 'raster'-> keys: version, width, height, mask, bpp, rgba (bytes)
    """
    data = maybe_unpack(data)
    if len(data) < 12:
        raise RsbError('too short (%d bytes)' % len(data))

    version, flag = struct.unpack_from('<HH', data, 0)

    if is_v8(data):
        return parse_v8(data)

    if version == 3:
        nlen, = struct.unpack_from('<I', data, 4)
        if nlen > 256 or 8 + nlen + 4 > len(data):
            raise RsbError('version 3 name length %d out of range' % nlen)
        name = data[8:8 + nlen].decode('latin-1')
        jlen, = struct.unpack_from('<I', data, 8 + nlen)
        jpeg = data[12 + nlen:12 + nlen + jlen]
        if jpeg[:2] != b'\xff\xd8':
            raise RsbError('version 3 payload is not a JPEG (%s)' %
                           jpeg[:4].hex())
        return dict(kind='jpeg', version=version, name=name, jpeg=jpeg,
                    declared_len=jlen, actual_len=len(data) - (12 + nlen))

    if version not in (0, 1, 4, 5, 6):
        raise RsbError('unhandled RSB version %d (flag %d)' % (version, flag))

    w, h, rb, gb, bb, ab = struct.unpack_from('<6I', data, 4)
    if not (0 < w <= 4096 and 0 < h <= 4096):
        raise RsbError('implausible dimensions %dx%d' % (w, h))
    bpp = rb + gb + bb + ab
    mask = (rb, gb, bb, ab)
    npx = w * h
    out = bytearray(npx * 4)

    if bpp == 4:
        pal = read_palette(data, HDR, 16, swizzle=False)
        base = HDR + 64
        need = base + (npx + 1) // 2
        if len(data) < need:
            raise RsbError('short 4bpp payload: have %d need %d'
                           % (len(data), need))
        for i in range(npx):
            byte = data[base + (i >> 1)]
            idx = (byte & 0x0f) if (i & 1) == 0 else (byte >> 4)
            out[i * 4:i * 4 + 4] = bytes(pal[idx])

    elif bpp == 8:
        pal = read_palette(data, HDR, 256, swizzle=SWIZZLE_CLUT256)
        base = HDR + 1024
        if len(data) < base + npx:
            raise RsbError('short 8bpp payload: have %d need %d'
                           % (len(data), base + npx))
        for i in range(npx):
            out[i * 4:i * 4 + 4] = bytes(pal[data[base + i]])

    elif bpp == 16:
        base = HDR
        if len(data) < base + npx * 2:
            raise RsbError('short 16bpp payload')
        words = struct.unpack_from('<%dH' % npx, data, base)
        if mask == (5, 6, 5, 0):
            # BGR order from the low bit up: B[0:5] G[5:11] R[11:16]
            for i, v in enumerate(words):
                b = (v & 0x1f)
                g = (v >> 5) & 0x3f
                r = (v >> 11) & 0x1f
                out[i * 4 + 0] = (r << 3) | (r >> 2)
                out[i * 4 + 1] = (g << 2) | (g >> 4)
                out[i * 4 + 2] = (b << 3) | (b >> 2)
                out[i * 4 + 3] = 255
        else:                                   # (4,4,4,4) -> BGRA nibbles
            for i, v in enumerate(words):
                out[i * 4 + 2] = (v & 0xf) * 17            # B
                out[i * 4 + 1] = ((v >> 4) & 0xf) * 17     # G
                out[i * 4 + 0] = ((v >> 8) & 0xf) * 17     # R
                out[i * 4 + 3] = ((v >> 12) & 0xf) * 17    # A

    elif bpp == 32:
        base = HDR
        if len(data) < base + npx * 4:
            raise RsbError('short 32bpp payload')
        px = data[base:base + npx * 4]
        # 32bpp is the one direct format stored A,R,G,B (see docstring)
        for i in range(npx):
            a, r, g, b = px[i * 4:i * 4 + 4]
            out[i * 4:i * 4 + 4] = bytes((r, g, b, a))

    else:
        raise RsbError('unhandled bit mask %s (bpp=%d)' % (mask, bpp))

    return dict(kind='raster', version=version, width=w, height=h,
                mask=mask, bpp=bpp, rgba=bytes(out))


def flatten(rgba, bg):
    """Alpha-composite straight-alpha RGBA onto an opaque (r,g,b)."""
    out = bytearray(len(rgba))
    for i in range(0, len(rgba), 4):
        r, g, b, a = rgba[i:i + 4]
        out[i + 0] = (r * a + bg[0] * (255 - a)) // 255
        out[i + 1] = (g * a + bg[1] * (255 - a)) // 255
        out[i + 2] = (b * a + bg[2] * (255 - a)) // 255
        out[i + 3] = 255
    return bytes(out)


def decode_to_file(data, out_base, bg=None):
    """Write <out_base>.png or <out_base>.jpg.  Returns the path written."""
    info = parse(data)
    if info['kind'] == 'jpeg':
        p = out_base + '.jpg'
        with open(p, 'wb') as f:
            f.write(info['jpeg'])
        return p
    p = out_base + '.png'
    px = info['rgba'] if bg is None else flatten(info['rgba'], bg)
    write_png(p, info['width'], info['height'], px)
    return p


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


# ---------------------------------------------------------------------------

def to_image(data):
    """A PIL image for either RSB shape, or None when Pillow is missing."""
    try:
        from PIL import Image
    except ImportError:
        return None
    import io
    info = parse(data)
    if info["kind"] == "jpeg":
        return Image.open(io.BytesIO(info["jpeg"])).convert("RGB")
    img = Image.frombytes("RGBA", (info["width"], info["height"]), info["rgba"])
    bg = Image.new("RGB", img.size, (18, 21, 26))
    bg.paste(img, mask=img.split()[3])
    return content_crop(bg, img.split()[3])


def content_crop(rgb, alpha=None):
    """Trim a power-of-two texture page back to the picture on it.

    These menu textures sit in the top-left of a 1024x512 or 512x512 page and
    the rest of the page is filler -- sometimes transparent, sometimes a flat
    colour. Both cases are handled by walking in from the right and bottom
    while the row or column stays uniform.
    """
    from PIL import Image, ImageChops

    if alpha is not None:
        box = alpha.getbbox()
        if box and (box[2] - box[0]) >= 64 and (box[3] - box[1]) >= 64                 and (box[2] - box[0]) * (box[3] - box[1]) < rgb.width * rgb.height:
            return rgb.crop(box)

    w, h = rgb.size
    px = rgb.load()

    def uniform_column(x):
        first = px[x, 0]
        for y in range(0, h, max(1, h // 48)):
            c = px[x, y]
            if abs(c[0] - first[0]) + abs(c[1] - first[1]) + abs(c[2] - first[2]) > 12:
                return False
        return True

    def uniform_row(y):
        first = px[0, y]
        for x in range(0, w, max(1, w // 48)):
            c = px[x, y]
            if abs(c[0] - first[0]) + abs(c[1] - first[1]) + abs(c[2] - first[2]) > 12:
                return False
        return True

    right = w
    while right > w // 2 and uniform_column(right - 1):
        right -= 1
    bottom = h
    while bottom > h // 2 and uniform_row(bottom - 1):
        bottom -= 1
    if right < w or bottom < h:
        return rgb.crop((0, 0, right, bottom))
    return rgb

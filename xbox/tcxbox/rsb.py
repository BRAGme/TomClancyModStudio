"""Red Storm `.RSB` bitmaps as the Xbox discs ship them, decoded far enough to
skin this tool with the games' own artwork.

The PS2 decoder that came with the other Mod Studio is no use here: those discs
ship versions 4 to 6 with a palette, and Ghost Recon and Island Thunder on Xbox
ship versions 8 and 9 with none. The layout is small enough to state in full:

    0x00  u32 version          8 or 9
    0x04  u32 width
    0x08  u32 height
    0x0C  u32 ?                always 0
    0x10  u8  ?, u8 ?, u8 ?, u8 redBits
    0x14  u8  ?, u8 ?, u8 ?, u8 greenBits
    0x18  u8  ?, u8 ?, u8 ?, u8 blueBits
    0x1C  u8  ?, u8 ?, u8 ?, u8 alphaBits
    0x20  u8  ?, u8 ?, u8 ?
    0x23  pixels
    ...   a fixed properties trailer

**35 bytes of header, not 36.** That is the one number here worth being sure
about, and it was settled by decoding rather than by counting fields: at 36 the
1024x512 menu backdrop comes out sheared by half a pixel per row and at 35 it is
the game's blue HUD ring, sharp. An odd header is unusual enough that the
arithmetic is worth writing down -- `shell_bgd-01.rsb` is 1,048,685 bytes for
1024 x 512 x 2, which leaves 109 bytes for header and trailer together.

**The bit depths do not always describe the storage.** `main_menu-01.rsb` says
8/8/8/0 and holds 262,144 bytes for 524,288 pixels: half a byte each, which is
DXT1. So the encoding is decided by dividing the body by the pixel count rather
than by trusting the header, and 0.5, 2, 3 and 4 bytes per
pixel are all real across the two games -- Island Thunder's main menu page is
24-bit where Ghost Recon's is DXT1.
"""

from __future__ import annotations

import struct

HEADER = 35

#: bytes after the pixels, by version. Derived the same way the header was.
TRAILER = {8: 66, 9: 74}


class RsbError(Exception):
    pass


def parse_header(data: bytes):
    """(version, width, height, rgbaBits)."""
    if len(data) < HEADER:
        raise RsbError("too short to be an .rsb")
    version, width, height = struct.unpack_from("<3I", data, 0)
    if version not in TRAILER or not (0 < width <= 4096 and 0 < height <= 4096):
        raise RsbError("unhandled .rsb version %d" % version)
    bits = tuple(data[o] for o in (0x13, 0x17, 0x1B, 0x1F))
    return version, width, height, bits


def is_rsb(data: bytes) -> bool:
    try:
        parse_header(data)
        return True
    except (RsbError, struct.error):
        return False


def to_image(data: bytes):
    """A Pillow image, RGB or RGBA."""
    from PIL import Image

    version, width, height, bits = parse_header(data)
    body = len(data) - HEADER - TRAILER[version]
    pixels = width * height
    if body <= 0 or pixels <= 0:
        raise RsbError("no pixel data")
    per = body / float(pixels)
    raw = data[HEADER:HEADER + body]

    if abs(per - 0.5) < 0.01:
        # DXT1. Pillow's "bcn" decoder wants the block format number.
        return Image.frombytes("RGBA", (width, height), raw, "bcn", 1)
    if abs(per - 2.0) < 0.01:
        mode = "BGR;16" if bits[3] == 0 else "BGRA;15"
        return Image.frombytes("RGB" if bits[3] == 0 else "RGBA",
                               (width, height), raw, "raw", mode)
    if abs(per - 3.0) < 0.01:
        # Island Thunder's main menu page is the only 24-bit raster in either
        # game, and it decodes with its true colours one byte EARLIER than the
        # 16- and 32-bit ones do -- at 35 the sky comes out green and the sea
        # magenta, at 34 it is the grey-blue dawn the box art uses. With a
        # single sample there is no way to say whether the header is a byte
        # shorter here or the channel order is rotated, so this records what
        # was observed rather than inventing a rule for it.
        return Image.frombytes("RGB", (width, height),
                               data[HEADER - 1:HEADER - 1 + body], "raw", "BGR")
    if abs(per - 4.0) < 0.01:
        return Image.frombytes("RGBA", (width, height), raw, "raw", "BGRA")
    raise RsbError("%.3f bytes per pixel is not a format this reads" % per)


def content_crop(image):
    """Trim the filler a power-of-two page leaves around the art.

    These menu pages are 1024 x 512 with a 640 x 480 picture in the top-left
    corner and flat filler beyond it, so the crop walks in from the right and
    the bottom while each edge row or column is a single colour. Doing it by
    measurement rather than by a hardcoded 640 x 480 matters because the icons
    on the same page are not that shape.
    """
    rgb = image.convert("RGB")
    w, h = rgb.size
    px = rgb.load()

    def uniform_col(x):
        first = px[x, 0]
        return all(px[x, y] == first for y in range(0, h, max(1, h // 64)))

    def uniform_row(y):
        first = px[0, y]
        return all(px[x, y] == first for x in range(0, w, max(1, w // 64)))

    right = w
    while right > w // 4 and uniform_col(right - 1):
        right -= 1
    bottom = h
    while bottom > h // 4 and uniform_row(bottom - 1):
        bottom -= 1
    if (right, bottom) == (w, h):
        return image
    return image.crop((0, 0, right, bottom))

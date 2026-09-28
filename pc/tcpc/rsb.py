r"""Red Storm `.RSB` bitmaps as the PC builds ship them.

Four versions turn up across the three Red Storm games here, in two header
layouts:

* **v4/v5/v6** -- Ghost Recon. 28-byte header: version, width, height, then the
  four channel depths as u32 each.
* **v8** -- Sum of All Fears, **v9/v10** -- Lockdown. 35-byte header, the same
  three u32s followed by the channel depths as the *last* byte of each of four
  u32 slots. 35 is an odd number and that is not a typo; it was settled by
  decoding rather than by counting fields, first in the Xbox tool and again
  here against these files.

**The declared bit depth does not always describe the storage.** Lockdown's
`background01.rsb` says 8/8/8/8 for a 1024x1024 page, which would be four
megabytes, and the file is half a megabyte: half a byte per pixel, which is
DXT1. So the encoding is decided by asking what actually FITS rather than by
trusting the header -- try the declared depth, then DXT5, then DXT1, and take
the first whose pixel data fits inside the file with a small trailer left over.

That also means no table of trailer sizes is needed. The bytes after the
pixels are properties this tool does not read, and are simply ignored, which is
one fewer per-version constant to be wrong about.

Nothing here is ever written. The artwork is read out of the user's own
installation at run time and cached locally; it is never redistributed.
"""

from __future__ import annotations

import struct

#: where the pixels start, by version.
#:
#: Three values, not two, and the third one cost a mistake worth recording.
#: v8 really does put its pixels at the odd offset 35. v9 and v10 insert eight
#: MORE bytes -- usually eight 0xFF, but `background00.rsb` has
#: `ff ff ff ff 00 00 00 00` there, which is what proves it is a header field
#: and not pixels -- and start at 43.
#:
#: Reading a v9 at 35 does not fail. It decodes, and it looks fine, because
#: eight bytes is two pixels of a 32-bit raster or one block of a DXT1 one, so
#: the whole image is simply shifted a few pixels sideways with a couple of
#: stray white pixels at the top left. It was settled by looking at the bytes
#: instead: from 43 onwards `r6lockdown.rsb` falls into clean `00 0b 0b 0b`
#: groups -- transparent near-black, an image's border -- and from 35 it does
#: not.
PIXELS_AT = {4: 28, 5: 28, 6: 28, 8: 35, 9: 43, 10: 43}

#: how many bytes may sit after the pixels and still look like a properties
#: trailer rather than a bad guess. Measured: 61 and 65 on Ghost Recon, 66 on
#: Sum of All Fears, 74 and 122 on Lockdown.
MAX_TRAILER = 256


class RsbError(Exception):
    pass


def parse_header(data: bytes):
    """(version, width, height, (r, g, b, a) bit depths, pixel offset)."""
    if len(data) < 36:
        raise RsbError("too short to be an .rsb")
    version, = struct.unpack_from("<I", data, 0)
    if version not in PIXELS_AT:
        raise RsbError("unhandled .rsb version %d" % version)
    base = PIXELS_AT[version]
    if version <= 6:
        w, h, rb, gb, bb, ab = struct.unpack_from("<6I", data, 4)
    else:
        w, h = struct.unpack_from("<II", data, 4)
        rb, gb, bb, ab = (data[o] for o in (0x13, 0x17, 0x1B, 0x1F))
    if rb + gb + bb + ab > 32:
        # Sum of All Fears' `cmi.rsb` declares (0, 0, 0, 255). Whatever that
        # field means there, it is not a channel width, and trusting it would
        # ask for a 16-megabyte raster from a 262-kilobyte file. Zeroing it
        # sends `to_image` to its measured fallbacks, which get it right.
        rb = gb = bb = ab = 0
    if not (0 < w <= 8192 and 0 < h <= 8192):
        raise RsbError("implausible dimensions %dx%d" % (w, h))
    return version, w, h, (rb, gb, bb, ab), base


def is_rsb(data: bytes) -> bool:
    try:
        parse_header(data)
        return True
    except (RsbError, struct.error):
        return False


def to_image(data: bytes):
    """A Pillow image, RGB or RGBA."""
    from PIL import Image

    version, w, h, bits, base = parse_header(data)
    npx = w * h
    avail = len(data) - base
    declared = sum(bits)

    # In order of preference: what the header says, then the block formats
    # small enough to be mistaken for it, then the plain depths -- the last
    # group only matters for the one file whose declared depth is nonsense.
    order = [(declared, "raw", bits), (8, "dxt5", bits), (4, "dxt1", bits)]
    if not declared:
        order += [(32, "raw", (8, 8, 8, 8)), (24, "raw", (8, 8, 8, 0)),
                  (16, "raw", (5, 6, 5, 0))]
    for bpp, how, use_bits in order:
        if bpp <= 0:
            continue
        need = npx * bpp // 8
        if need <= 0 or need > avail or avail - need > MAX_TRAILER:
            continue
        raw = data[base:base + need]
        if how == "dxt1":
            return Image.frombytes("RGBA", (w, h), raw, "bcn", 1)
        if how == "dxt5":
            return Image.frombytes("RGBA", (w, h), raw, "bcn", 3)
        return _raw_image(raw, w, h, use_bits)

    raise RsbError("%dx%d v%d: no encoding fits %d bytes (header says %d bpp)"
                   % (w, h, version, avail, declared))


def _raw_image(raw, w, h, bits):
    from PIL import Image
    rb, gb, bb, ab = bits
    bpp = rb + gb + bb + ab

    # RED FIRST, unlike the PS2 and Xbox builds of these same games, whose
    # rasters are stored blue first. Settled by looking rather than by
    # reasoning: read as BGR, Ghost Recon's main menu comes out with cyan
    # faces on soldiers in blue-grey woodland camouflage; read as RGB it is
    # skin, green jungle and the right camouflage.
    if bpp == 24 and (rb, gb, bb) == (8, 8, 8):
        return Image.frombytes("RGB", (w, h), raw, "raw", "RGB")
    if bpp == 32 and (rb, gb, bb, ab) == (8, 8, 8, 8):
        # ...but a 32-bit raster is **ARGB**, not RGBA -- alpha comes FIRST,
        # so it is not simply the 24-bit order with a channel appended. Read
        # as RGBA, Lockdown's logo is cyan and pink on an opaque block and
        # Ghost Recon's medals are flat cyan; read as ARGB the logo is red and
        # white on transparency and the medals have ribbons. Confirmed
        # separately in both header families, so it is the format and not one
        # game's quirk.
        return Image.frombytes("RGBA", (w, h), raw, "raw", "ARGB")
    if bpp == 16 and (rb, gb, bb, ab) == (5, 6, 5, 0):
        return Image.frombytes("RGB", (w, h), raw, "raw", "BGR;16")
    if bpp == 16 and ab:
        # 4/4/4/4 and 1/5/5/5 both turn up; unpack by hand rather than hunt for
        # the Pillow raw mode that happens to match this channel order.
        return _unpack16(raw, w, h, bits)
    if bpp == 16:
        return Image.frombytes("RGB", (w, h), raw, "raw", "BGR;15")
    raise RsbError("unhandled channel layout %s" % (bits,))


def _unpack16(raw, w, h, bits):
    from PIL import Image
    rb, gb, bb, ab = bits
    # Channels are packed low to high in the order blue, green, red, alpha --
    # the byte-order swap that makes a 24-bit raster read red first leaves a
    # 16-bit one, whose channels are bit fields inside a little-endian word,
    # with blue in the low bits.
    shifts = {}
    at = 0
    for name, n in (("b", bb), ("g", gb), ("r", rb), ("a", ab)):
        shifts[name] = (at, n)
        at += n
    out = bytearray(w * h * 4)
    values = struct.unpack_from("<%dH" % (w * h), raw, 0)
    for i, v in enumerate(values):
        for j, name in enumerate("rgba"):
            shift, n = shifts[name]
            if not n:
                out[i * 4 + j] = 255
                continue
            c = (v >> shift) & ((1 << n) - 1)
            # expand to 8 bits so full-scale stays full-scale
            out[i * 4 + j] = (c * 255) // ((1 << n) - 1)
    return Image.frombytes("RGBA", (w, h), bytes(out))


def load(path):
    """Decode a `.rsb` from disk, or None if it is not one this can read."""
    try:
        with open(path, "rb") as fh:
            return to_image(fh.read())
    except (OSError, RsbError, struct.error, ValueError):
        return None

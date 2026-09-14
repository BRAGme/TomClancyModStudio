"""Sum of All Fears PS2 artwork: the `.RSB` versions Ghost Recon never used,
plus the `.PAK` texture-sheet container.

`tcps2.rsb` already decodes versions 1, 3 (JPEG), 4, 5 and 6, and 224 of the
234 `.RSB` files in this game go through it unchanged.  The other ten are
**version 8**, which Ghost Recon does not ship and which `tcps2.rsb` rejects,
and two `.RSB` files that are really single-entry `.PAK`s.

VERSION 8 -- measured, and the size arithmetic closes exactly on all 8 files:

    +0   u32 version = 8
    +4   u32 width
    +8   u32 height
    +12  7 bytes, unidentified     <- the only difference from version 6
    +19  u32 rBits
    +23  u32 gBits
    +27  u32 bBits
    +31  u32 aBits
    +35  pixels                    <- note: an ODD offset
    end  66-byte trailer

i.e. it is the 28-byte version-6 header with seven bytes inserted after
`height`, so `35 + width*height*bpp/8 + 66 == filesize` for every one of
DECORATIONS, LOAD_ICON, MAIN_MENU-01..05 and SOAF_COMMAND_BKGRND.

That odd pixel base is not a guess.  Scanning candidate bases 28..43 and
scoring each render by mean horizontal colour difference, every EVEN base
scored ~88 and every ODD base ~16 -- the 16-bit words genuinely start on an odd
byte.  The colour order is then ordinary RGB565 with red in the HIGH bits,
confirmed by the US flag in MAIN_MENU-01 coming out red/white/blue.

.PAK -- a flat chain of named texture sheets, no header and no index:

    u32   flags          0 = stored, 2 = compressed
    u32   nameLen        includes the NUL
    char  name[nameLen]
    u32   0x13           constant on every record in all four PAKs
    u32   width
    u32   height
    flags == 0:  u32 0x410, u32 0x8040, u32 0x08000000, u32 0, u32 0
                 then a 1024-byte RGBA palette, w*h 8-bit indices,
                 and a 20-byte trailer
    flags == 2:  u32 firstChunkSize, u32 0x410, then the chunk chain

**The flags==2 codec is NOT cracked** -- see `art.md`.  It does not matter for
artwork, because every compressed PAK record's name also exists as a plain
`.RSB` in SOAF.IMG (checked, 0 exceptions), so the same picture is reachable
uncompressed.
"""

from __future__ import annotations

import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from tcps2 import rsb as _rsb   # noqa: E402

V8_HDR = 35
V8_TRAILER = 66


class ArtError(Exception):
    pass


# ---------------------------------------------------------------------------
# RSB version 8
# ---------------------------------------------------------------------------

def is_v8(data):
    return len(data) >= 36 and struct.unpack_from("<I", data, 0)[0] == 8


def parse_v8(data):
    w, h = struct.unpack_from("<II", data, 4)
    rb, gb, bb, ab = data[19], data[23], data[27], data[31]
    bpp = rb + gb + bb + ab
    if bpp not in (16, 32):
        raise ArtError("v8 bpp %d (%d,%d,%d,%d) not handled" % (bpp, rb, gb, bb, ab))
    need = V8_HDR + w * h * bpp // 8 + V8_TRAILER
    if need != len(data):
        raise ArtError("v8 size mismatch: %dx%d bpp%d wants %d, file is %d"
                       % (w, h, bpp, need, len(data)))
    npx = w * h
    out = bytearray(npx * 4)
    if bpp == 16:
        words = struct.unpack_from("<%dH" % npx, data, V8_HDR)
        for i, v in enumerate(words):
            r = (v >> 11) & 31
            g = (v >> 5) & 63
            b = v & 31
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


# ---------------------------------------------------------------------------
# .PAK
# ---------------------------------------------------------------------------

PAK_TAG = 0x13
_NAME_RX = re.compile(rb"[ -~]+")


def pak_records(data):
    """Every record in a .PAK, as dicts. Scans rather than walks, because the
    flags==2 payload length is only known by reaching the next record."""
    hits = []
    n = len(data)
    for o in range(0, n - 40):
        fl, nl = struct.unpack_from("<II", data, o)
        if fl not in (0, 2) or not (2 <= nl <= 96) or o + 8 + nl + 24 > n:
            continue
        nm = data[o + 8:o + 8 + nl]
        if nm[-1:] != b"\0" or not _NAME_RX.fullmatch(nm[:-1]):
            continue
        if struct.unpack_from("<I", data, o + 8 + nl)[0] != PAK_TAG:
            continue
        w, h = struct.unpack_from("<II", data, o + 8 + nl + 4)
        hits.append(dict(offset=o, flags=fl, name=nm[:-1].decode("latin1"),
                         width=w, height=h, body=o + 8 + nl + 12))
    for i, r in enumerate(hits):
        r["end"] = hits[i + 1]["offset"] if i + 1 < len(hits) else n
    return hits


def pak_record_image(data, rec):
    """RGBA for a stored (flags==0) record. Raises for flags==2."""
    if rec["flags"] != 0:
        raise ArtError("%s: PAK flags=2 records use an undecoded codec"
                       % rec["name"])
    w, h = rec["width"], rec["height"]
    base = rec["body"] + 20          # 0x410, 0x8040, 0x08000000, 0, 0
    pal = _rsb.read_palette(data, base, 256)
    px = base + 1024
    slack = rec["end"] - (px + w * h)
    if not (16 <= slack <= 32):
        raise ArtError("%s: %dx%d 8bpp does not fill the record (%d bytes slack)"
                       % (rec["name"], w, h, slack))
    out = bytearray(w * h * 4)
    for i in range(w * h):
        r, g, b, a = pal[data[px + i]]
        out[i * 4:i * 4 + 4] = bytes((r, g, b, min(255, a * 2)))
    return dict(kind="raster", version="pak", width=w, height=h,
                mask=(8, 8, 8, 8), bpp=8, rgba=bytes(out))


# ---------------------------------------------------------------------------
# one entry point
# ---------------------------------------------------------------------------

def parse_named(data):
    """The `.RSB` shape that starts with a name instead of a version.

    Only LANGUAGE_SELECT.RSB uses it.  `nameLen` here EXCLUDES the terminating
    NUL -- unlike the .PAK records, where it includes it -- and the version-8
    header then starts at `8 + nameLen`, so the name's NUL is the low byte of
    its `version` field (0).  Measured: width and height both read 256 at
    +4/+8 from that base, 256*256*4 accounts for all but 59 bytes of the file,
    and the picture that comes out is the six language flags.
    """
    nl = struct.unpack_from("<I", data, 4)[0]
    base = 8 + nl
    w, h = struct.unpack_from("<II", data, base + 4)
    px = len(data) - w * h * 4
    if px < base + 8 or not (0 < w <= 4096 and 0 < h <= 4096):
        raise ArtError("named RSB: %dx%d does not fit %d bytes" % (w, h, len(data)))
    out = bytearray(w * h * 4)
    for i in range(w * h):
        r, g, b, a = data[px + i * 4:px + i * 4 + 4]
        out[i * 4:i * 4 + 4] = bytes((r, g, b, min(255, a * 2)))
    return dict(kind="raster", version="named", width=w, height=h,
                mask=(8, 8, 8, 8), bpp=32, rgba=bytes(out))


def parse(data):
    """Any Sum of All Fears RSB, including version 8 and the PAK-wrapped ones."""
    if is_v8(data):
        return parse_v8(data)
    ver, flag = struct.unpack_from("<HH", data, 0)
    if ver in (0, 2) and flag == 0:
        recs = pak_records(data)
        if recs:
            return pak_record_image(data, recs[0])
        return parse_named(data)
    return _rsb.parse(data)


def to_image(data):
    """A PIL RGB image, matte-composited and trimmed to its content."""
    from PIL import Image
    info = parse(data)
    if info["kind"] == "jpeg":
        import io
        return Image.open(io.BytesIO(info["jpeg"])).convert("RGB")
    img = Image.frombytes("RGBA", (info["width"], info["height"]), info["rgba"])
    bg = Image.new("RGB", img.size, (18, 21, 26))
    bg.paste(img, mask=img.split()[3])
    return bg


def to_rgba(data):
    from PIL import Image
    info = parse(data)
    if info["kind"] == "jpeg":
        import io
        return Image.open(io.BytesIO(info["jpeg"])).convert("RGBA")
    return Image.frombytes("RGBA", (info["width"], info["height"]), info["rgba"])

#!/usr/bin/env python3
"""
rsb.py - decoder for Red Storm Engine PS2 ".RSB" bitmaps as shipped in
Ghost Recon PS2 (SLUS-20613) and Ghost Recon Jungle Storm PS2 (SLUS-20820).

Reuses grimg.py (archive reader) and rselzo.py (LZO container) - it does not
duplicate either.

--------------------------------------------------------------------------
CONTAINER
--------------------------------------------------------------------------
An .RSB inside gr.img / menu.img may be stored raw or wrapped in the rselzo
chunk container.  `rselzo.unpack()` is tried first and falls back to raw.

--------------------------------------------------------------------------
HEADER  (all little-endian; two shapes, selected by `version`)
--------------------------------------------------------------------------
  +0x00  u16  version      0, 1, 3, 4, 5 or 6 in these two games
  +0x02  u16  flag         1 for version 0/1, 0 for version 3..6
                           (this is the PS2 split of the PC build's u32
                            version field; RSB(ps2).bt calls it `B`)

  --- version == 3 : a *named JPEG wrapper*, NOT a raster ------------------
  +0x04  u32  nameLen
  +0x08  char name[nameLen]      lower-case, no extension, no NUL
  +N+8   u32  jpegLen            == filesize - (12 + nameLen), exactly
  +N+12  u8   jpeg[jpegLen]      begins FF D8 FF E0 .. JFIF
     Verified on all 468 version-3 files across both games: jpegLen matched
     the residual file size exactly every time and every payload ended in
     FF D9.  These carry all the mission-briefing / loading / storyboard art
     (the SF_* names) and the DMG_LOGO / MUS_LOGO splash screens.

  --- version 0,1,4,5,6 : a raster ----------------------------------------
  +0x04  u32  width
  +0x08  u32  height
  +0x0C  u32  redBits          \
  +0x10  u32  greenBits         |  "BIT_MASK" in RSB(ps2).bt.
  +0x14  u32  blueBits          |  On PS2 the SUM is the bits per pixel.
  +0x18  u32  alphaBits        /
  +0x1C  ...  payload (see below)

--------------------------------------------------------------------------
PAYLOAD, by bit mask.  bpp = red+green+blue+alpha
--------------------------------------------------------------------------
The four BIT_MASK words are NOT bit widths on PS2.  Their SUM is the bits
per pixel, and the individual values only distinguish 565 from 4444:

  bpp == 4   mask (1,1,1,1)   16-colour palettised
      +0x1C   16 * 4 bytes  B,G,R,A palette       (64 bytes)
      +0x5C   width*height/2 bytes, 2 pixels per byte, LOW nibble first
  bpp == 8   mask (2,2,2,2)   256-colour palettised
      +0x1C   256 * 4 bytes B,G,R,A palette       (1024 bytes)
      +0x41C  width*height bytes, one index per pixel
  bpp == 16  mask (4,4,4,4)   u16 LE  B[0:4] G[4:8] R[8:12] A[12:16]
  bpp == 16  mask (5,6,5,0)   u16 LE  B[0:5] G[5:11] R[11:16], alpha = 255
  bpp == 32  mask (8,8,8,8)   4 bytes, A,R,G,B in memory order

BYTE ORDER - this is the one thing the data disagrees with itself about,
and it follows exactly the rule in the PC template RSB.bt:
      bits total == 32  ->  ARGB
      anything else     ->  BGRA   (palettes and both 16-bit forms)
  Proof for the palettised path: /LANGUAGE_SELECT.RSB decodes to the UK,
  French, Italian and Spanish flags.  Read as R,G,B,A the tricolore comes
  out red-white-blue and the Spanish flag blue-cyan; read as B,G,R,A every
  flag is correct.
  Proof for 565: /EVILTWIN.RSB is a photographic human face - warm skin
  with R in the HIGH bits, blue skin with R in the low bits.
  Proof for 32bpp: /DECORATIONS.RSB is the US medal rack - the Bronze Star
  is gold as A,R,G,B and blue as A,B,G,R.
  4444 is untestable and does not matter: all 688128 RGBA4444 pixels in
  both games are grey (r nibble == g nibble == b nibble), 0 exceptions.

  Rows are top-to-bottom, left-to-right, LINEAR.  There is NO PS2
  page/block swizzle on an RSB index plane (contrast .BMZ, below).

--------------------------------------------------------------------------
THE TWO PS2 TRAPS - both TESTED, both REFUTED for RSB
--------------------------------------------------------------------------
 1. CLUT swizzle (swap entries [i+8:i+16] with [i+16:i+24] in every block
    of 32): NOT PRESENT.  Applying it to /MAIN_MENU_PS2.RSB turns a clean
    jungle photo into blotchy colour patches; leaving it alone is correct.
    `unswizzle_clut256()` is kept below so the test can be rerun, and
    because the .BMZ path may still want it - but SWIZZLE_CLUT256 is False.

 2. Alpha 0..128: NOT PRESENT in RSB.  Alpha is a plain 0..255 byte.
    Measured over every palette and every 32bpp alpha byte in both games
    the maximum is 255, and 255 is one of the two most common values.
    (The .BMZ texture banks look like they DO - see below.)

--------------------------------------------------------------------------
.BMZ / .BMB  (partial - see the notes in the project write-up)
--------------------------------------------------------------------------
.BMZ is NOT an RSB and is not a container of RSBs.  It is an rselzo-
compressed bank of ready-to-send PS2 GS texture-upload DMA/GIF packets:

  +0x00 u32  (unidentified)
  +0x04 u32  if the top bit is set this is a format tag (seen FFFFFFFF,
             FFFFFFFE, FFFFFFFD, FFFFFFFC) and the record count is at +0x08,
             records start at +0x0C; otherwise this word IS the record
             count and records start at +0x08.
  record stride by tag: FFFFFFFF -> 44, FFFFFFFE -> 48, FFFFFFFC -> 68,
                        no tag   -> 40 bytes.
  Every record begins  u32 id, u32 width, u32 height, u32 version, u32 bpp
  and ends             u32 clutPacketOff, u32 pixelPacketOff
  (offsets relative to the end of the record table).
  CLUT payload  = base + clutPacketOff  + 0xC0, 1024 or 64 bytes, and here
                  the order is R,G,B,A - the OPPOSITE of an RSB palette
                  (with B,G,R,A a beach level's sand and grass come out
                  blue; with R,G,B,A they are sand and grass).
                  Alpha here does look like the PS2 0..128 convention:
                  0x80 is by far the commonest value (501473 of ~870000
                  entries sampled) - but values above 128 do occur, so
                  treat the 2x scale as probable, not proven.
  Pixel payload = base + pixelPacketOff + 0x80, w*h or w*h/2 bytes,
                  **PS2 PSMT8-swizzled** - the standard 16x8 block/column
                  de-swizzle is required or you get salt-and-pepper noise.
  546 of the 639 .BMZ/.BMB files in the two games satisfy the invariant
  rec[i+1].clutPacketOff == rec[i].pixelPacketOff + 0x80 + pixelBytes.
  .BMB is a different thing again and is NOT this container.

--------------------------------------------------------------------------
TRAILER
--------------------------------------------------------------------------
Direct-colour rasters carry a fixed-size properties trailer after the pixel
array (the RSB_PROPERTIES struct of RSB(ps2).bt):
      version 4 -> 53 bytes,  version 5 -> 61 bytes,  version 6 -> 65 bytes.
Palettised rasters (versions 0, 1 and the palettised version 5s) have NO
trailer: header+palette+indices is the exact file size.  The decoder does
not need the trailer and ignores it.

--------------------------------------------------------------------------
CLI
--------------------------------------------------------------------------
  python rsb.py <input.rsb> <output.png>
  python rsb.py --img <archive.img> --extract '<regex>' --out <dir>
  python rsb.py --img <archive.img> --census
  ...  --bg 1e222a      flatten onto an opaque background instead of
                        writing straight alpha (a lot of this art is white
                        or pale on a fully transparent field and is
                        invisible in a viewer that mattes onto white)

A version-3 RSB is written as <name>.jpg, everything else as <name>.png.
Note for git-bash users: a --extract pattern starting with '/' is mangled
by MSYS path conversion.  Prefix the command with MSYS_NO_PATHCONV=1.
"""

import argparse
import os
import re
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import grimg                                                   # noqa: E402
import rselzo                                                  # noqa: E402

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
        return rselzo.unpack(data)
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

def parse(data):
    """Return a dict describing an RSB.

    kind == 'jpeg'  -> keys: version, name, jpeg (bytes)
    kind == 'raster'-> keys: version, width, height, mask, bpp, rgba (bytes)
    """
    data = maybe_unpack(data)
    if len(data) < 12:
        raise RsbError('too short (%d bytes)' % len(data))

    version, flag = struct.unpack_from('<HH', data, 0)

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

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('input', nargs='?', help='an .rsb file on disk')
    ap.add_argument('output', nargs='?', help='output .png (or .jpg for v3)')
    ap.add_argument('--img', help='read from a gr.img / menu.img archive')
    ap.add_argument('--extract', help='regex of archive paths to decode')
    ap.add_argument('--out', help='output directory for --extract')
    ap.add_argument('--census', action='store_true',
                    help='tabulate RSB variants in --img')
    ap.add_argument('--bg', metavar='RRGGBB',
                    help='flatten onto this opaque colour instead of '
                         'writing straight alpha')
    a = ap.parse_args(argv)

    bg = None
    if a.bg:
        s = a.bg.lstrip('#')
        if len(s) != 6:
            ap.error('--bg wants six hex digits, e.g. 1e222a')
        bg = tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))

    if a.img and a.census:
        import collections
        arc = grimg.GrImg(a.img)
        tally = collections.Counter()
        for p in sorted(arc.files):
            if not p.upper().endswith('.RSB'):
                continue
            try:
                i = parse(arc.get(p))
            except Exception as e:
                tally[('ERROR', str(e)[:40])] += 1
                continue
            tally[(i['version'], 'jpeg' if i['kind'] == 'jpeg'
                   else '%dbpp %s' % (i['bpp'], i['mask']))] += 1
        for k, v in sorted(tally.items(), key=lambda kv: str(kv[0])):
            print('%-40s %d' % (str(k), v))
        return 0

    if a.img and a.extract:
        if not a.out:
            ap.error('--extract needs --out')
        os.makedirs(a.out, exist_ok=True)
        arc = grimg.GrImg(a.img)
        rx = re.compile(a.extract, re.I)
        n = bad = 0
        for p in sorted(arc.files):
            if not p.upper().endswith('.RSB') or not rx.search(p):
                continue
            base = os.path.join(a.out,
                                os.path.splitext(os.path.basename(p))[0])
            try:
                w = decode_to_file(arc.get(p), base, bg)
            except Exception as e:
                print('FAIL %s: %s' % (p, e), file=sys.stderr)
                bad += 1
                continue
            print('%s -> %s' % (p, os.path.basename(w)))
            n += 1
        print('decoded %d, failed %d' % (n, bad), file=sys.stderr)
        return 1 if bad else 0

    if not a.input:
        ap.error('give an input file, or --img with --extract/--census')
    with open(a.input, 'rb') as f:
        data = f.read()
    if a.output:
        info = parse(data)
        if info['kind'] == 'jpeg':
            with open(a.output, 'wb') as f:
                f.write(info['jpeg'])
        else:
            px = info['rgba'] if bg is None else flatten(info['rgba'], bg)
            write_png(a.output, info['width'], info['height'], px)
        print(a.output)
    else:
        print(decode_to_file(data, os.path.splitext(a.input)[0], bg))
    return 0


if __name__ == '__main__':
    sys.exit(main())

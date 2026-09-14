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
     Verified byte-exact on all 359 version-3 files in GR gr.img.

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
  bpp == 4   mask (1,1,1,1)   16-colour palettised
      +0x1C   16 * 4 bytes  RGBA8888 palette      (64 bytes)
      +0x5C   width*height/2 bytes, 2 pixels per byte, LOW nibble first
  bpp == 8   mask (2,2,2,2)   256-colour palettised
      +0x1C   256 * 4 bytes RGBA8888 palette      (1024 bytes)
      +0x41C  width*height bytes, one index per pixel
  bpp == 16  mask (4,4,4,4)   u16 LE, RGBA4444  (R in bits 0-3 .. A in 12-15)
  bpp == 16  mask (5,6,5,0)   u16 LE, RGB565    (R in bits 0-4, B in 11-15)
  bpp == 32  mask (8,8,8,8)   4 bytes, R,G,B,A in memory order

  Rows are stored top-to-bottom, left-to-right, un-swizzled.  There is NO
  PS2 page/block swizzle on the index plane - verified visually.

--------------------------------------------------------------------------
THE TWO PS2 TRAPS - measured, not assumed
--------------------------------------------------------------------------
 1. CLUT swizzle: PRESENT, and only on the 256-entry (bpp==8) palette.
    Entries are stored with the middle two groups of 8 of every 32-entry
    block exchanged.  Un-swizzle with, for each block of 32 starting at i:
        pal[i+8:i+16] <-> pal[i+16:i+24]
    The 16-entry (bpp==4) palette is NOT swizzled (a 16-entry CLUT is a
    single half-block and the GS never reorders it).

 2. Alpha range: PRESENT.  Stored alpha is 0..128 (0x80 = fully opaque),
    the PS2 GS convention.  Convert with  a = min(255, a*255//128).
    This applies to the palette alpha (bpp 4 and 8) and to the 8-bit alpha
    of bpp==32.  It does NOT apply to the 4-bit alpha of RGBA4444, which is
    a plain 0..15 field expanded by  a*17.

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
"""

import argparse
import io
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


def decode_to_file(data, out_base):
    """Write <out_base>.png or <out_base>.jpg.  Returns the path written."""
    info = parse(data)
    if info['kind'] == 'jpeg':
        p = out_base + '.jpg'
        with open(p, 'wb') as f:
            f.write(info['jpeg'])
        return p
    p = out_base + '.png'
    write_png(p, info['width'], info['height'], info['rgba'])
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
    a = ap.parse_args(argv)

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
                w = decode_to_file(arc.get(p), base)
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
            write_png(a.output, info['width'], info['height'], info['rgba'])
        print(a.output)
    else:
        print(decode_to_file(data, os.path.splitext(a.input)[0]))
    return 0


if __name__ == '__main__':
    sys.exit(main())

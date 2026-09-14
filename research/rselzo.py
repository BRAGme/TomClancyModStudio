#!/usr/bin/env python3
"""
rselzo.py - the compressed-container layer used inside Ghost Recon PS2
(SLUS-20613) and Ghost Recon Jungle Storm PS2 (SLUS-20820) data files.

CONTAINER
  A compressed RSE PS2 data file is a bare sequence of chunks. There is no
  magic number:

      repeat until EOF:
          u32  compressedSize      (little-endian)
          u32  rawSize             (little-endian, always <= 0x4000)
          u8   blob[compressedSize]

  rawSize is 0x4000 (16384) for every chunk except the last.

  *** compressedSize == rawSize means the chunk is STORED, not compressed. ***
  Feeding a stored chunk to the LZO decoder produces a "bad back-reference"
  almost immediately; that is the tell. Because there is
  no magic, the sniff test is: walk the chain and require it to land exactly
  on EOF with every rawSize <= 0x4000. Files that ship as plain text (.ATR,
  .GUN, .KIT, .PRJ, .VCL, .ITM, .ENV, .XML) start with '<' and fail the test.

  NOTE the field order is (compressed, raw) - the OPPOSITE of the (raw,
  compressed) order used by Rainbow Six 3 PS2's .LIN packages.

PAYLOAD
  Each blob is a stock **LZO1X** stream - exactly what lzo1x_decompress eats.
  Nothing about the bitstream is Red-Storm-specific; only the framing is.

  Reference decode of AVATAR.TOE chunk 0, which is how it was identified:
      2F          0x2F > 17 -> "first literal run" of 0x2F-17 = 30 bytes
                  "<TOEFile>\\r\\n\\t<VersionNumber>2.0"
      82 00       t=0x82 >= 64: copy (t>>5)+1 = 5 bytes from
                  dist = 1 + ((t>>2)&7) + (0x00<<3) = 1        -> "00000"
                  then ip[-2]&3 = 2 trailing literals          -> "</"
      2C 5C 00    t=0x2C in [32,64): copy (t&31)+2 = 14 from
                  dist = 1 + (0x005C>>2) = 24                  -> "VersionNumber>"
"""

import struct


def lzo1x_decompress(src):
    """Faithful pure-python lzo1x_decompress (the LZO reference control flow,
    with its gotos turned into an explicit label variable)."""
    out = bytearray()
    n = len(src)
    ip = 0
    t = 0

    def lit(count):
        nonlocal ip
        out.extend(src[ip:ip + count])
        ip += count

    # --- entry: the "first literal run" special case -----------------------
    if src[0] > 17:
        t = src[0] - 17
        ip = 1
        if t < 4:
            label = "match_next"
        else:
            lit(t)
            label = "first_literal_run"
    else:
        label = "top"

    m_pos = 0
    while True:
        if label == "top":
            t = src[ip]; ip += 1
            if t >= 16:
                label = "match"; continue
            if t == 0:
                while src[ip] == 0:
                    t += 255; ip += 1
                t += 15 + src[ip]; ip += 1
            lit(t + 3)
            label = "first_literal_run"; continue

        if label == "first_literal_run":
            t = src[ip]; ip += 1
            if t >= 16:
                label = "match"; continue
            # M1 inside a first literal run: fixed 0x800 base, copies 3 bytes
            m_pos = len(out) - (1 + 0x0800) - (t >> 2) - (src[ip] << 2)
            ip += 1
            for _ in range(3):
                out.append(out[m_pos]); m_pos += 1
            label = "match_done"; continue

        if label == "match":
            if t >= 64:
                m_pos = len(out) - 1 - ((t >> 2) & 7) - (src[ip] << 3)
                ip += 1
                t = (t >> 5) - 1
                label = "copy_match"; continue
            elif t >= 32:
                t &= 31
                if t == 0:
                    while src[ip] == 0:
                        t += 255; ip += 1
                    t += 31 + src[ip]; ip += 1
                d = src[ip] | (src[ip + 1] << 8); ip += 2
                m_pos = len(out) - 1 - (d >> 2)
            elif t >= 16:
                m_pos = len(out) - ((t & 8) << 11)
                t &= 7
                if t == 0:
                    while src[ip] == 0:
                        t += 255; ip += 1
                    t += 7 + src[ip]; ip += 1
                d = src[ip] | (src[ip + 1] << 8); ip += 2
                m_pos -= (d >> 2)
                if m_pos == len(out):
                    break                       # EOF marker (11 00 00)
                m_pos -= 0x4000
            else:
                m_pos = len(out) - 1 - (t >> 2) - (src[ip] << 2)
                ip += 1
                for _ in range(2):
                    out.append(out[m_pos]); m_pos += 1
                label = "match_done"; continue
            label = "copy_match"; continue

        if label == "copy_match":
            if m_pos < 0:
                raise ValueError("bad back-reference at ip=%d" % ip)
            for _ in range(t + 2):
                out.append(out[m_pos]); m_pos += 1
            label = "match_done"; continue

        if label == "match_done":
            t = src[ip - 2] & 3
            label = "match_next"; continue

        if label == "match_next":
            if t == 0:
                label = "top"; continue
            lit(t)
            t = src[ip]; ip += 1
            label = "match"; continue

    return bytes(out)


# --------------------------------------------------------------------------
def chunks(data):
    """Yield (compSize, rawSize, blobOffset). Raises if the chain is bogus."""
    o = 0
    while o + 8 <= len(data):
        comp, raw = struct.unpack("<II", data[o:o + 8])
        if comp == 0 or raw == 0 or raw > 0x4000 or o + 8 + comp > len(data):
            raise ValueError("not a chunked container at 0x%X" % o)
        yield comp, raw, o + 8
        o += 8 + comp
    if o != len(data):
        raise ValueError("chunk chain ended at 0x%X, file is 0x%X"
                         % (o, len(data)))


def is_compressed(data):
    if len(data) < 8:
        return False
    try:
        list(chunks(data))
        return True
    except (ValueError, struct.error):
        return False


def decompress(data):
    """Decompress a whole chunked file. Returns plain bytes."""
    out = bytearray()
    for comp, raw, off in chunks(data):
        if comp == raw:
            # STORED chunk: the compressor gave up, bytes are literal.
            out += data[off:off + raw]
            continue
        d = lzo1x_decompress(data[off:off + comp])
        if len(d) != raw:
            raise ValueError("chunk at 0x%X: produced %d bytes, header says %d"
                             % (off, len(d), raw))
        out += d
    return bytes(out)


def unpack(data):
    """decompress() when it is a container, else return data unchanged."""
    return decompress(data) if is_compressed(data) else data


if __name__ == "__main__":
    import sys
    sys.stdout.buffer.write(unpack(open(sys.argv[1], "rb").read()))

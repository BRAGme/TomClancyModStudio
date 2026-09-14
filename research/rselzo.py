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

This module both reads (`decompress`/`unpack`) and writes (`compress`) the
container. See FORMATS.md section 2.4 for the encoder's verified correctness and
its known size gap versus the retail lzo1x_999 output.

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


# --------------------------------------------------------------------------
# Compressor
#
# Needed because a replacement file must fit its existing archive slot
# (see FORMATS.md 1.7) and a stored rewrite is ~4x too big: M02_FARM.MIS
# decompresses 20367 -> 77123, and its all-STORED form would be 77163.
#
# Chunks here are never larger than 0x4000 bytes, so a back-reference offset
# can never exceed 0x3FFF. That means the M4 (long-offset) token is never
# required and this encoder emits only M2 and M3 matches plus literal runs.
# --------------------------------------------------------------------------
_MIN_MATCH = 3
_CHAIN = 256       # hash-chain depth; higher = smaller output, slower


def lzo1x_compress(src):
    """Produce an LZO1X stream that lzo1x_decompress() turns back into `src`.

    Hash-chained longest-match search with one-byte lazy matching. Canonical
    LZO1X output; only M2 and M3 tokens are ever emitted (see note above)."""
    n = len(src)
    out = bytearray()
    table = {}      # 3-byte key -> list of recent positions, oldest first
    ip = 0
    ii = 0          # start of the pending literal run
    last_tok = -1   # index in `out` of the byte the decoder reads as op[-2]

    def emit_literals(t):
        if t == 0:
            return
        if not out:
            # start of stream: 17+t selects the decoder's first-literal-run path
            if t <= 238:
                out.append(17 + t)
            elif t <= 18:
                out.append(t - 3)
            else:
                tt = t - 18
                out.append(0)
                while tt > 255:
                    tt -= 255
                    out.append(0)
                out.append(tt)
        elif t <= 3:
            out[last_tok] |= t
        elif t <= 18:
            out.append(t - 3)
        else:
            tt = t - 18
            out.append(0)
            while tt > 255:
                tt -= 255
                out.append(0)
            out.append(tt)
        out.extend(src[ii:ii + t])

    def cost(L, off):
        """Bytes this match costs to encode."""
        if L <= 8 and off <= 0x0800:
            return 2                      # M2
        return 3 + (0 if L <= 33 else 1 + (L - 33) // 255)   # M3

    def find(pos):
        """Best match for src[pos:]. Returns (length, offset, gain).

        "Best" is by NET gain (bytes saved), not raw length: an M2 token costs
        2 bytes and an M3 token costs 3+, so a shorter near match can beat a
        longer far one. Scoring by length alone costs ~2% of output size."""
        if pos + _MIN_MATCH > n:
            return 0, 0, 0
        chain = table.get(src[pos:pos + _MIN_MATCH])
        if not chain:
            return 0, 0, 0
        best_len, best_off, best_gain = 0, 0, 0
        for cand in reversed(chain):
            off = pos - cand
            if off > 0x3FFF:
                break
            L = _MIN_MATCH
            while pos + L < n and src[cand + L] == src[pos + L]:
                L += 1
            gain = L - cost(L, off)
            if gain > best_gain:
                best_len, best_off, best_gain = L, off, gain
                if L >= 264:
                    break
        return best_len, best_off, best_gain

    def index(pos):
        if pos + _MIN_MATCH > n:
            return
        c = table.setdefault(src[pos:pos + _MIN_MATCH], [])
        c.append(pos)
        if len(c) > _CHAIN:
            del c[0]

    while ip + _MIN_MATCH <= n:
        m_len, m_off, m_gain = find(ip)
        index(ip)
        if m_len < _MIN_MATCH:
            ip += 1
            continue

        # lazy match: deferring by one byte costs 1 literal byte, so only take
        # the next position when it gains more than that
        if ip + 1 + _MIN_MATCH <= n:
            _, _, n_gain = find(ip + 1)
            if n_gain > m_gain + 1:
                ip += 1
                continue

        emit_literals(ip - ii)
        off = m_off - 1
        if m_len <= 8 and m_off <= 0x0800:
            out.append(((m_len - 1) << 5) | ((off & 7) << 2))
            last_tok = len(out) - 1
            out.append(off >> 3)
        else:
            if m_len <= 33:
                out.append(0x20 | (m_len - 2))
            else:
                rest = m_len - 33
                out.append(0x20)
                while rest > 255:
                    rest -= 255
                    out.append(0)
                out.append(rest)
            out.append((off << 2) & 0xFF)
            last_tok = len(out) - 1
            out.append(off >> 6)

        for k in range(ip + 1, ip + m_len):
            index(k)
        ip += m_len
        ii = ip

    emit_literals(n - ii)
    out += b"\x11\x00\x00"          # M4 end-of-stream marker
    return bytes(out)


def compress(plain, chunk=0x4000):
    """Build a chunked container from plain bytes. Each chunk is stored
    uncompressed whenever compression does not actually help, which is the
    same rule the retail data follows."""
    out = bytearray()
    for o in range(0, len(plain), chunk):
        raw = plain[o:o + chunk]
        packed = lzo1x_compress(raw)
        if len(packed) >= len(raw):
            out += struct.pack("<II", len(raw), len(raw)) + raw
        else:
            out += struct.pack("<II", len(packed), len(raw)) + packed
    return bytes(out)


if __name__ == "__main__":
    import sys
    sys.stdout.buffer.write(unpack(open(sys.argv[1], "rb").read()))

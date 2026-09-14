"""The compressed container inside Ghost Recon PS2 and Jungle Storm PS2 files.

CONTAINER -- a bare chain of chunks, with no magic number:

    repeat until EOF:
        u32  compressedSize   (little-endian)
        u32  rawSize          (little-endian, always <= 0x4000)
        u8   blob[compressedSize]

`rawSize` is 0x4000 for every chunk but the last, and **`compressedSize ==
rawSize` means the chunk is STORED**, not compressed -- feeding a stored chunk
to the LZO decoder produces a bad back-reference almost immediately, which is
the tell. Note the field order is (compressed, raw), the opposite of Rainbow
Six 3's `.LIN` packages.

Since there is no magic, the sniff test is to walk the chain and require it to
land exactly on EOF. Files that ship as plain text start with `<` and fail on
the first step.

PAYLOAD -- each blob is a stock **LZO1X** stream. Nothing about the bitstream is
Red Storm's; only the framing above is.

WRITING FILES BACK is the hard half, because a replacement has to fit the slot
the archive already reserves for it and a stored rewrite is about four times too
big. Two things make it work:

  * a cost-aware encoder, which refuses a match that does not actually pay for
    its own token -- a three-byte match too far away to use the short form costs
    three bytes to encode three bytes, so emitting it makes the file bigger;
  * `repack`, which re-compresses only the chunks whose plain bytes actually
    changed and copies the rest of the original container verbatim. Paired with
    edits that keep the raw length identical, that bounds the damage to the one
    chunk you touched instead of re-packing the whole file at a slightly worse
    ratio than the retail tool managed.
"""

from __future__ import annotations

import struct

CHUNK = 0x4000
MIN_MATCH = 3
MAX_DIST = 0x3FFF        # a chunk is never bigger than 0x4000
EOF_MARKER = b"\x11\x00\x00"


class LzoError(Exception):
    pass


# ---------------------------------------------------------------------------
# decode
# ---------------------------------------------------------------------------

def lzo1x_decompress(src: bytes) -> bytes:
    """The LZO reference control flow, with its gotos as an explicit label.

    Two details are easy to get wrong and both corrupt the output silently:
    after a match the trailing-literal count is `ip[-2] & 3` -- the byte two
    before the pointer, not the token -- and the M1 case reached from a first
    literal run uses a fixed 0x800 distance base and copies three bytes, where
    the M1 reached from a match copies two.
    """
    out = bytearray()
    n = len(src)
    ip = 0
    t = 0

    def lit(count):
        nonlocal ip
        out.extend(src[ip:ip + count])
        ip += count

    if not src:
        raise LzoError("empty stream")
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
    try:
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
                m_pos = len(out) - (1 + 0x0800) - (t >> 2) - (src[ip] << 2)
                ip += 1
                if m_pos < 0:
                    raise LzoError("bad back-reference at ip=%d" % ip)
                for _ in range(3):
                    out.append(out[m_pos]); m_pos += 1
                label = "match_done"; continue

            if label == "match":
                if t >= 64:
                    m_pos = len(out) - 1 - ((t >> 2) & 7) - (src[ip] << 3)
                    ip += 1
                    t = (t >> 5) - 1
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
                        break                      # end of stream
                    m_pos -= 0x4000
                else:
                    m_pos = len(out) - 1 - (t >> 2) - (src[ip] << 2)
                    ip += 1
                    if m_pos < 0:
                        raise LzoError("bad back-reference at ip=%d" % ip)
                    for _ in range(2):
                        out.append(out[m_pos]); m_pos += 1
                    label = "match_done"; continue
                label = "copy_match"; continue

            if label == "copy_match":
                if m_pos < 0:
                    raise LzoError("bad back-reference at ip=%d" % ip)
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
    except IndexError as exc:
        raise LzoError("ran off the end of the stream at ip=%d" % ip) from exc

    return bytes(out)


# ---------------------------------------------------------------------------
# encode
# ---------------------------------------------------------------------------

def _match_cost(length, dist):
    """Bytes the encoder will spend on this match, token included."""
    if length <= 8 and dist <= 0x0800:
        return 2                                   # M2
    if length <= 33:
        return 3                                   # M3
    return 3 + (length - 33 + 254) // 255          # M3 with a length extension


def lzo1x_compress(src: bytes, chain_depth=512) -> bytes:
    """An LZO1X stream that `lzo1x_decompress` turns back into `src`.

    Hash-chained longest match with one-byte lazy evaluation, and -- the part
    that matters for fitting a retail archive slot -- a match is only taken when
    it encodes in fewer bytes than the literals it replaces. A three-byte match
    that has to use the long form costs three bytes to save three, so taking it
    is a loss once the literal run it interrupts has to be re-opened.
    """
    n = len(src)
    out = bytearray()
    table: dict[bytes, list] = {}
    ip = 0
    ii = 0            # start of the pending literal run
    last_tok = -1     # index in `out` of the byte the decoder reads as op[-2]

    def emit_literals(t):
        nonlocal last_tok
        if t == 0:
            return
        if not out:
            # 17+t selects the decoder's first-literal-run entry path
            if t <= 238:
                out.append(17 + t)
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

    def find(pos):
        """(length, dist) of the best PROFITABLE match at `pos`, else (0, 0)."""
        if pos + MIN_MATCH > n:
            return 0, 0
        chain = table.get(src[pos:pos + MIN_MATCH])
        if not chain:
            return 0, 0
        best_len = best_dist = 0
        best_gain = 0
        limit = n - pos
        for cand in reversed(chain):
            dist = pos - cand
            if dist > MAX_DIST:
                break
            length = MIN_MATCH
            while length < limit and src[cand + length] == src[pos + length]:
                length += 1
            gain = length - _match_cost(length, dist)
            if gain > best_gain:
                best_gain, best_len, best_dist = gain, length, dist
                if length >= 264:
                    break
        return (best_len, best_dist) if best_gain > 0 else (0, 0)

    def index(pos):
        if pos + MIN_MATCH > n:
            return
        c = table.setdefault(src[pos:pos + MIN_MATCH], [])
        c.append(pos)
        if len(c) > chain_depth:
            del c[0]

    while ip + MIN_MATCH <= n:
        m_len, m_dist = find(ip)
        index(ip)
        if not m_len:
            ip += 1
            continue

        # lazy: defer if the next position pays better
        if ip + 1 + MIN_MATCH <= n:
            n_len, n_dist = find(ip + 1)
            if n_len and (n_len - _match_cost(n_len, n_dist)) > \
                    (m_len - _match_cost(m_len, m_dist)):
                ip += 1
                continue

        emit_literals(ip - ii)
        off = m_dist - 1
        if m_len <= 8 and m_dist <= 0x0800:
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
    out += EOF_MARKER
    return bytes(out)


# ---------------------------------------------------------------------------
# container
# ---------------------------------------------------------------------------

def chunks(data: bytes):
    """Yield (compressedSize, rawSize, blobOffset). Raises on a bogus chain."""
    o = 0
    while o + 8 <= len(data):
        comp, raw = struct.unpack_from("<II", data, o)
        if comp == 0 or raw == 0 or raw > CHUNK or o + 8 + comp > len(data):
            raise LzoError("not a chunked container at 0x%X" % o)
        yield comp, raw, o + 8
        o += 8 + comp
    if o != len(data):
        raise LzoError("chunk chain ended at 0x%X but the file is 0x%X"
                       % (o, len(data)))


def is_compressed(data: bytes) -> bool:
    if len(data) < 8:
        return False
    try:
        list(chunks(data))
        return True
    except (LzoError, struct.error):
        return False


def decompress(data: bytes) -> bytes:
    out = bytearray()
    for comp, raw, off in chunks(data):
        if comp == raw:
            out += data[off:off + raw]
            continue
        d = lzo1x_decompress(data[off:off + comp])
        if len(d) != raw:
            raise LzoError("chunk at 0x%X produced %d bytes, header says %d"
                           % (off, len(d), raw))
        out += d
    return bytes(out)


def unpack(data: bytes) -> bytes:
    """decompress() when it is a container, otherwise the data unchanged."""
    return decompress(data) if is_compressed(data) else data


def compress(plain: bytes, chunk=CHUNK) -> bytes:
    """Build a container from scratch. Falls back to a stored chunk wherever
    compression does not actually help, which is what the retail data does."""
    out = bytearray()
    for o in range(0, len(plain), chunk):
        raw = plain[o:o + chunk]
        packed = lzo1x_compress(raw)
        if len(packed) >= len(raw):
            out += struct.pack("<II", len(raw), len(raw)) + raw
        else:
            out += struct.pack("<II", len(packed), len(raw)) + packed
    return bytes(out)


def repack(original: bytes, new_plain: bytes) -> bytes:
    """Re-emit a container, re-compressing only what actually changed.

    Our encoder is a couple of percent looser than whatever Red Storm shipped
    with, so re-compressing a whole untouched file makes it too big for its own
    archive slot. Keeping every chunk whose plain bytes are unchanged -- byte
    for byte, in its original compressed form -- means an edit only pays for the
    chunks it actually touches. Chunk boundaries are fixed at 0x4000 of plain
    data, so this works whenever the edit preserves the total length.
    """
    if not is_compressed(original):
        return new_plain

    old_plain = decompress(original)
    out = bytearray()
    pos = 0
    old_chunks = list(chunks(original))
    for i, (comp, raw, off) in enumerate(old_chunks):
        want = new_plain[pos:pos + raw]
        if len(want) == raw and want == old_plain[pos:pos + raw]:
            out += struct.pack("<II", comp, raw) + original[off:off + comp]
        else:
            packed = lzo1x_compress(want)
            if len(packed) >= len(want):
                out += struct.pack("<II", len(want), len(want)) + want
            else:
                out += struct.pack("<II", len(packed), len(want)) + packed
        pos += raw
        if pos >= len(new_plain):
            break

    # the edit made the file longer than the original: append fresh chunks
    while pos < len(new_plain):
        want = new_plain[pos:pos + CHUNK]
        packed = lzo1x_compress(want)
        if len(packed) >= len(want):
            out += struct.pack("<II", len(want), len(want)) + want
        else:
            out += struct.pack("<II", len(packed), len(want)) + packed
        pos += len(want)

    if decompress(bytes(out)) != new_plain:
        raise LzoError("repack round-trip failed -- refusing to write")
    return bytes(out)

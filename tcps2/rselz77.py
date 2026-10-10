"""
Red Storm RSE PS2 ".PAK" texture segment codec  --  class `lz77`.

Reverse engineered from Tom Clancy's Ghost Recon (PS2, SLUS-206.13), whose ELF
retains a full symbol table (.symtab, 38722 symbols).  Relevant symbols / VAs:

    0x00539310  __ct__4lz77Fv                               (sets window = 0x10000)
    0x00539110  decode__4lz77FPUciPPUc                       lz77::decode(src, len, &dst)
    0x00538F70  input_match__4lz77FP10lz77_match             lz77::input_match(&m)
    0x00538EB0  input_bitstream_bit__4lz77FP13in_bit_streami lz77::input_bitstream_bit(bs,n)
    0x0051BE10  RefreshActive__12UITextureMgrFP9UITexture     the caller (both decodes)
    0x0051B660  LoadingTexturePak__12UITextureMgrFiPCc        the .PAK record loop
    0x0051D910  LoadPS2Img__9UITexture...                     stand-alone .ps2img reader

Jungle Storm (SLUS-208.20) is stripped; the same routines, located by matching
input_bitstream_bit's first 16 bytes (a unique hit) and then following jal
targets.  Same algorithm, same struct offsets, different register allocation:

    0x0051D160  lz77::lz77            (lui v0,1 / sw v0,0(a0)  -> window 0x10000)
    0x0051D1C0  lz77::decode
    0x0051D390  lz77::input_match
    0x0051D4F0  lz77::input_bitstream_bit
    0x0051D130  bit-width helper, out-of-lined here: returns max(1, bitlen(a0))
    0x00500F60  UITextureMgr::RefreshActive equivalent (calls decode twice)

File offsets: GR  = VA - 0x00100000 + 0x80
              JS  = VA - 0x00100000 + 0x100

Wire format of one segment inside a .PAK record:

    u32 size                 # bytes that follow, INCLUDING the rawSize field
    u32 rawSize              # uncompressed length (= 16 byte GIFtag + payload)
    u8  bitstream[size - 4]

lz77::decode is handed a pointer to `rawSize` and the length `size`; it reads
rawSize itself from the first four bytes, allocates rawSize+1 bytes, and treats
everything after as the bitstream.  decompress() below takes the bitstream and
rawSize separately.

Bit I/O
-------
input_bitstream_bit(bs, n) gathers n bits, LSB-first *within each byte* and
LSB-first *into the result* (the first bit read becomes bit 0 of the value).
It returns -1 when the input is exhausted:
  * immediately, if cur >= end on entry;
  * mid-value, if the byte pointer passes end while bits are still owed.

Token stream (input_match)
--------------------------
avail = number of output bytes currently addressable in the window
      = min(bytes emitted so far, 65536)
base  = index of the window start in the output = len(out) - avail

    flag = read(1)
    flag < 0                -> end of stream
    flag == 0               -> LITERAL: read(8), append it
    flag == 1               -> MATCH:
        off = read(max(1, bit_length(avail - 1)))
        y   = avail - off - 1
        if   y == 0            : length = 1
        elif bit_length(y) < 4 : length = read(bit_length(y)) + 1
        else                   :                       # y >= 8
            if read(1) == 0    : length = read(2) + 1               #  1..4
            else:
                k = 1
                while True:                                         # count 1-bits
                    k += 1
                    if read(1) == 0: break
                length = (1 << k) + read(k) + 1                     #  2^k+1 .. 2^(k+1)
        copy `length` bytes from out[base + off]  (off is a FORWARD offset from
        the window start, not a backward distance)

After every token: avail += length (1 for a literal); if avail > 65536 then
avail = 65536 (so base slides to len(out) - 65536).

End of stream is purely input exhaustion -- rawSize is never used as a loop
bound.  A partially-filled final byte can therefore decode into at most one
extra spurious literal, which is why the game allocates rawSize+1 bytes and
ignores the tail.  decompress() truncates to rawSize.
"""

WINDOW = 0x10000


class _BitReader:
    """Mirror of lz77::input_bitstream_bit / struct in_bit_stream."""
    __slots__ = ("buf", "end", "cur", "bitpos")

    def __init__(self, buf):
        self.buf = buf
        self.end = len(buf)
        self.cur = 0
        self.bitpos = 0

    def read(self, n):
        if not (self.cur < self.end):
            return -1
        if n <= 0:
            return 0
        buf, result, i = self.buf, 0, 0
        while True:
            result |= ((buf[self.cur] >> self.bitpos) & 1) << i
            self.bitpos += 1
            if self.bitpos >= 8:
                self.bitpos = 0
                self.cur += 1
                if not (self.cur < self.end) and i < n - 1:
                    return -1
            i += 1
            if not (i < n):
                break
        return result


def _bitlen(v):
    return v.bit_length() if v > 0 else 0


def decompress(body, raw_size):
    """Decode one .PAK segment body. Returns exactly raw_size bytes."""
    bs = _BitReader(body)
    out = bytearray()
    avail = 0
    started = False

    while True:
        flag = bs.read(1)
        if flag < 0:
            break
        if flag == 0:
            ch = bs.read(8)
            out.append(ch & 0xFF)           # an `lb` of -1 would store 0xFF
            if not started:
                started = True
                avail = 1
            else:
                avail += 1
        else:
            nb = max(1, _bitlen(avail - 1)) if avail >= 1 else 1
            off = bs.read(nb)
            if off < 0:
                raise ValueError("EOF inside match offset")
            y = avail - off - 1
            if y == 0:
                length = 1
            else:
                nb2 = max(1, _bitlen(y))
                if nb2 < 4:
                    length = bs.read(nb2) + 1
                else:
                    if bs.read(1) == 0:
                        length = bs.read(2) + 1
                    else:
                        k = 1
                        while True:
                            k += 1
                            if bs.read(1) == 0:
                                break
                        length = (1 << k) + bs.read(k) + 1
            src = len(out) - avail + off
            if src < 0 or length < 1:
                raise ValueError("bad match: off=%d len=%d avail=%d pos=%d"
                                 % (off, length, avail, len(out)))
            for i in range(length):
                out.append(out[src + i])    # byte-at-a-time, so overlap = RLE
            avail += length
        if avail > WINDOW:
            avail = WINDOW

    if len(out) < raw_size:
        raise ValueError("short output: got %d, want %d" % (len(out), raw_size))
    return bytes(out[:raw_size])


# ---------------------------------------------------------------------------
# Encoder.  NOT a port of the game's compressor (RSE's encoder lives in their
# PC-side tools and is not in the ELF); this emits the same token stream with a
# greedy longest-match search, so decompress(compress(x), len(x)) == x.
# ---------------------------------------------------------------------------

class _BitWriter:
    def __init__(self):
        self.out = bytearray()
        self.bitpos = 0

    def write(self, value, n):
        for i in range(n):
            if self.bitpos == 0:
                self.out.append(0)
            if (value >> i) & 1:
                self.out[-1] |= 1 << self.bitpos
            self.bitpos = (self.bitpos + 1) & 7

    def bytes(self):
        return bytes(self.out)


def _len_capacity(y):
    """Largest length the length-code can express for this y (y >= 1)."""
    nb2 = max(1, _bitlen(y))
    if nb2 < 4:
        return 1 << nb2
    return 1 << 25


def _encode_length(bw, length, y):
    """Inverse of the length decoder. Returns False if length is unrepresentable."""
    if y == 0:
        return length == 1
    nb2 = max(1, _bitlen(y))
    if nb2 < 4:
        if not (1 <= length <= (1 << nb2)):
            return False
        bw.write(length - 1, nb2)
        return True
    if 1 <= length <= 4:
        bw.write(0, 1)
        bw.write(length - 1, 2)
        return True
    k = 1
    while k <= 24:
        k += 1
        lo, hi = (1 << k) + 1, (1 << (k + 1))
        if lo <= length <= hi:
            bw.write((1 << (k - 1)) - 1, k - 1)   # k-1 one-bits
            bw.write(0, 1)                        # terminating zero
            bw.write(length - 1 - (1 << k), k)
            return True
    return False


def compress(data, min_match=3, max_cand=64):
    """Produce a bitstream that decompress(..., len(data)) reproduces exactly."""
    bw = _BitWriter()
    n = len(data)
    data = bytes(data)
    pos = 0
    avail = 0
    started = False
    index = {}                                  # min_match-byte key -> positions
    while pos < n:
        best_len, best_off = 0, 0
        if started:
            base = pos - avail
            key = data[pos:pos + min_match]
            if len(key) == min_match:
                cands = index.get(key)
                if cands:
                    tried = 0
                    for cand in reversed(cands):
                        if cand < base:
                            break
                        tried += 1
                        if tried > max_cand:
                            break
                        off = cand - base
                        if off > avail - 1:
                            continue
                        y = avail - off - 1
                        # Never let a match run past the write head.  The game
                        # copies with memcpy(), whose behaviour on an
                        # overlapping forward copy is not byte-at-a-time, so an
                        # overlapping (RLE-style) match would not round-trip on
                        # the real console.  Retail data contains exactly zero
                        # of them across both discs (0 of 3784119 matches), so
                        # the original encoder clamped the same way.
                        limit = min(n - pos, pos - cand)
                        ln = 0
                        while ln < limit and data[cand + ln] == data[pos + ln]:
                            ln += 1
                        if y == 0:
                            ln = min(ln, 1)
                        else:
                            ln = min(ln, _len_capacity(y))
                        if ln > best_len:
                            best_len, best_off = ln, off
        if best_len >= min_match:
            y = avail - best_off - 1
            bw.write(1, 1)
            bw.write(best_off, max(1, _bitlen(avail - 1)))
            if not _encode_length(bw, best_len, y):
                raise AssertionError("length %d not encodable for y=%d" % (best_len, y))
            emitted = best_len
        else:
            bw.write(0, 1)
            bw.write(data[pos], 8)
            emitted = 1
        for j in range(pos, pos + emitted):
            if j + min_match <= n:
                index.setdefault(data[j:j + min_match], []).append(j)
        pos += emitted
        if not started:
            started = True
            avail = 1
        else:
            avail += emitted
        if avail > WINDOW:
            avail = WINDOW
    return bw.bytes()

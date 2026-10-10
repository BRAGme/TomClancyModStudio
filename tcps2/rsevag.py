"""PS2 SPU ADPCM, the format every sample in a Red Storm `.SB` / `.SS` is in.

Sixteen bytes per block, 28 samples:

    byte 0   low nibble  = shift (0..12), high nibble = predictor (0..4)
    byte 1   flags: 1 end, 2 loop region, 3 loop end, 4 loop start,
             6 loop start (region), 7 end + mute; 0 otherwise
    bytes 2..15  28 four-bit residuals, LOW nibble of each byte first

    s    = sign_extend(nibble << 12) >> shift
    out  = s + (f0[pred] * h1 + f1[pred] * h2) / 64, clamped to int16

This exists because Ghost Recon records the ambience library at **16,000 Hz**
and Jungle Storm the same sounds at **11,025 Hz** -- 1,336 of the 1,431 names
the two share. The Ghost Recon samples are not longer, only denser, so they
overflow the resident bank they have to fit in. Decoding, resampling to Jungle
Storm's rate and re-encoding gets the real recording into the budget.

The encoder picks a predictor open-loop (the cheap part, vectorised) and then
quantises closed-loop, which is what keeps the drift of an ADPCM re-encode
bounded. Round-trip error is measured in `tests`, not assumed.
"""

from __future__ import annotations

import struct

#: the SPU's four fixed predictors, numerator over 64
F0 = (0, 60, 115, 98, 122)
F1 = (0, 0, -52, -55, -60)
BLOCK = 16
PER_BLOCK = 28
#: flags that end the sample; 7 also mutes
END_FLAGS = (1, 7)


def _clamp16(v):
    return -32768 if v < -32768 else (32767 if v > 32767 else v)


def decode(data: bytes):
    """[int16] -- every block, flags honoured only for where the data stops."""
    out = []
    h1 = h2 = 0
    for off in range(0, len(data) - BLOCK + 1, BLOCK):
        b0 = data[off]
        shift, pred = b0 & 0x0F, b0 >> 4
        if pred > 4:
            pred = 0
        if shift > 12:
            shift = 12
        f0, f1 = F0[pred], F1[pred]
        for i in range(PER_BLOCK):
            byte = data[off + 2 + (i >> 1)]
            nib = (byte >> 4) if (i & 1) else (byte & 0x0F)
            s = nib << 12
            if s & 0x8000:
                s -= 0x10000
            s >>= shift
            v = _clamp16(s + ((f0 * h1 + f1 * h2) >> 6))
            out.append(v)
            h2, h1 = h1, v
        if data[off + 1] in END_FLAGS:
            break
    return out


def flags(data: bytes):
    """The per-block flag bytes, so a rebuilt sample can keep its loop."""
    return [data[o + 1] for o in range(0, len(data) - BLOCK + 1, BLOCK)]


def resample(pcm, src_rate, dst_rate):
    """Band-limited resample. Returns [int16]."""
    import numpy as np

    if src_rate == dst_rate or not pcm:
        return list(pcm)
    x = np.asarray(pcm, dtype=np.float64)
    n_out = max(1, int(round(len(x) * dst_rate / float(src_rate))))
    if dst_rate < src_rate:
        # low-pass first or the fold-back is audible on the insect beds
        cutoff = 0.45 * dst_rate / float(src_rate)
        taps = 63
        m = np.arange(taps) - (taps - 1) / 2.0
        h = np.sinc(2 * cutoff * m) * np.hamming(taps)
        h /= h.sum()
        x = np.convolve(x, h, mode="same")
    pos = np.arange(n_out) * (len(x) - 1) / float(max(n_out - 1, 1))
    y = np.interp(pos, np.arange(len(x)), x)
    return [int(v) for v in np.clip(np.rint(y), -32768, 32767)]


def encode(pcm, block_flags=None) -> bytes:
    """ADPCM for `pcm`, padded to whole blocks.

    `block_flags` is an optional per-block flag byte list -- pass the source's,
    stretched to the new block count, to keep a looping sample looping.
    """
    import numpy as np

    n_blocks = (len(pcm) + PER_BLOCK - 1) // PER_BLOCK
    src = np.zeros(n_blocks * PER_BLOCK, dtype=np.int64)
    src[:len(pcm)] = np.asarray(pcm, dtype=np.int64)

    out = bytearray()
    h1 = h2 = 0
    for b in range(n_blocks):
        want = src[b * PER_BLOCK:(b + 1) * PER_BLOCK]
        # try all five predictors closed-loop and keep the one whose
        # reconstruction is actually closest; choosing open-loop instead costs
        # about 0.8 dB and saves no measurable time
        best = None
        for p in range(5):
            f0, f1 = F0[p], F1[p]
            a1, a2, peak = h1, h2, 0
            for v in want:
                r = v - ((f0 * a1 + f1 * a2) >> 6)
                if abs(r) > peak:
                    peak = abs(r)
                a2, a1 = a1, v
            # decode does s = (q << 12) >> shift, so a BIGGER shift is a FINER
            # step: take the biggest whose residuals still fit in a nibble.
            # Searching upward from 0 stops at the coarsest quantiser and
            # turns the whole bank into noise.
            shift = 12
            while shift > 0 and ((peak << shift) >> 12) > 7:
                shift -= 1
            a1, a2, err, nibbles = h1, h2, 0, []
            for v in want:
                pr = (f0 * a1 + f1 * a2) >> 6
                q = ((v - pr) << shift) >> 12
                if q > 7:
                    q = 7
                elif q < -8:
                    q = -8
                # q is already signed; the sign-extend in `decode` undoes the
                # nibble packing and must not be repeated here
                rec = _clamp16(pr + ((q << 12) >> shift))
                err += (v - rec) * (v - rec)
                nibbles.append(q & 0x0F)
                a2, a1 = a1, rec
            if best is None or err < best[0]:
                best = (err, p, shift, nibbles, a1, a2)
        _err, pred, shift, nibbles, h1, h2 = best

        flag = 0
        if block_flags is not None and b < len(block_flags):
            flag = block_flags[b]
        out.append((pred << 4) | shift)
        out.append(flag)
        for i in range(0, PER_BLOCK, 2):
            out.append(nibbles[i] | (nibbles[i + 1] << 4))
    return bytes(out)


def stretch_flags(src_flags, n_blocks):
    """`src_flags` mapped onto `n_blocks`, keeping loop points in proportion."""
    if not src_flags or n_blocks <= 0:
        return [0] * max(n_blocks, 0)
    out = [0] * n_blocks
    scale = (n_blocks - 1) / float(max(len(src_flags) - 1, 1))
    for i, f in enumerate(src_flags):
        if f:
            j = min(n_blocks - 1, int(round(i * scale)))
            out[j] = f
    # a sample must still end where it ends
    if any(f in END_FLAGS for f in src_flags):
        out[-1] = 1 if 1 in src_flags else out[-1] or 1
    return out

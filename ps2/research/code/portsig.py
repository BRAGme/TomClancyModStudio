#!/usr/bin/env python3
"""portsig.py - locate a Ghost Recon function inside the stripped Jungle Storm ELF.

Both games are Metrowerks CodeWarrior 2.4.1.01 builds of the same Red Storm Engine
source tree, so a function body is usually instruction-for-instruction identical
except for the fields that carry an address:

    lui   rt, HI          -> low 16 bits differ
    jal   target          -> low 26 bits differ
    beq/bne/... offset    -> usually identical (PC-relative, same body)
    addiu rt, rs, LO      -> low 16 bits differ ONLY when rs came from a lui

This masks lui immediates and jal targets to zero, keeps everything else, and slides
the resulting signature over the target image.

    python portsig.py <gr-VA-hex> [nwords] [--target js|offline|online] [--min N]

Prints every candidate match with its VA in the target and the exact score.
`nwords` defaults to the symbol size from Ghost Recon's symbol table.
"""
import sys, struct
import rsetool


def mask(w):
    op = w >> 26
    if op == 0x0F:                       # lui
        return w & 0xFFFF0000
    if op in (0x02, 0x03):               # j / jal
        return w & 0xFC000000
    return w


def signature(img, va, n):
    return [mask(img.word(va + i * 4)) for i in range(n)]


def find(sig, timg, min_ratio=0.90):
    """Anchor on the RAREST word of the signature, not the first.

    Metrowerks re-allocates registers between builds, so a prologue word is a
    terrible anchor. The rarest interior word gives far more hits and is what
    makes this work across the two titles.
    """
    d = timg.data
    n = len(sig)
    nw = len(d) // 4
    words = struct.unpack_from("<%dI" % nw, d, 0)
    mw = [mask(w) for w in words]
    from collections import Counter
    freq = Counter(mw)
    # pick the signature word that is rarest in the target and not a nop/trivial
    cand = [(freq.get(sig[k], 0), k) for k in range(n)
            if sig[k] not in (0, 0x03E00008) and freq.get(sig[k], 0) > 0]
    if not cand:
        return []
    cand.sort()
    need = int(n * min_ratio)
    seen, out = set(), []
    for _, anchor in cand[:8]:          # try the 8 rarest anchors
        tgt = sig[anchor]
        for i in range(nw):
            if mw[i] != tgt:
                continue
            base = i - anchor
            if base < 0 or base + n > nw or base in seen:
                continue
            seen.add(base)
            hit = sum(1 for k in range(n) if mw[base + k] == sig[k])
            if hit >= need:
                out.append((timg.va(base * 4), hit, n))
    return out


def main(a):
    if not a:
        print(__doc__); return 1
    va = int(a[0], 16)
    target = "js"
    minr = 0.90
    if "--target" in a: target = a[a.index("--target") + 1]
    if "--min" in a: minr = float(a[a.index("--min") + 1])
    n = None
    if len(a) > 1 and not a[1].startswith("--"):
        n = int(a[1])
    gr = rsetool.Image("gr")
    s = rsetool.gr_sym_at(va)
    if n is None:
        n = (s[1] // 4) if s and s[1] else 40
    print("source: GR 0x%08x  %s  (%d words)" % (va, s[2] if s else "?", n))
    sig = signature(gr, va, n)
    timg = rsetool.Image(target)
    hits = find(sig, timg, minr)
    if not hits:
        print("  no match in %s at ratio %.2f" % (target, minr))
        return 0
    for tva, hit, tot in sorted(hits, key=lambda h: -h[1]):
        print("  %s 0x%08x   %d/%d words (%.1f%%)" % (target, tva, hit, tot, 100.0 * hit / tot))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

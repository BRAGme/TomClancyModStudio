#!/usr/bin/env python3
"""portmap.py -- port every Ghost Recon patch site into SOAF by signature.

For each VA in Ghost Recon's STOCK table: find the containing GR function,
signature-match that function into the target image, and report the
corresponding VA there plus whether the stock word survived the port.

A site is usable only when the whole function matched AND the word at the
ported address is byte-identical to Ghost Recon's stock word (or differs only
in the fields a relocation legitimately changes: lui immediates, jal targets).
"""
import sys, struct
ROOT = r"C:\Users\Tristan\Documents\GitHub\TomClancyPS2-ModStudio"
sys.path.insert(0, ROOT)
sys.path.insert(0, ROOT + r"\research\code")
import rsetool, portsig
from tcps2.games import ghost_recon

TARGET = sys.argv[1] if len(sys.argv) > 1 else "soaf"
MINR = float(sys.argv[2]) if len(sys.argv) > 2 else 0.90

gr = rsetool.Image("gr")
tgt = rsetool.Image(TARGET)
syms = [(v, s, n) for v, s, t, n in rsetool.gr_symbols() if t == 2 and s]
syms.sort()


def sym_at(va):
    best = None
    for v, s, n in syms:
        if v <= va < v + s:
            if best is None or v > best[0]:
                best = (v, s, n)
    return best


def kind(w):
    op = w >> 26
    return "lui" if op == 0x0F else ("jal" if op in (2, 3) else "")


# group the patch sites by the function that contains them
groups = {}
orphans = []
for va, word in sorted(ghost_recon.STOCK.items()):
    s = sym_at(va)
    if s is None:
        orphans.append((va, word))
    else:
        groups.setdefault(s, []).append((va, word))

print("Ghost Recon -> %s signature port" % TARGET.upper())
print("%d patch sites in %d functions, %d outside any function\n"
      % (sum(len(v) for v in groups.values()), len(groups), len(orphans)))

cache = {}
ok = exact = 0
rows = []
for (sv, ss, sn) in sorted(groups):
    sites = groups[(sv, ss, sn)]
    n = max(ss // 4, 8)
    if (sv, n) not in cache:
        sig = portsig.signature(gr, sv, n)
        hits = portsig.find(sig, tgt, MINR)
        cache[(sv, n)] = max(hits, key=lambda h: h[1]) if hits else None
    hit = cache[(sv, n)]
    short = sn.split("__")[0][:38] or sn[:38]
    if hit is None:
        rows.append(("  --------  %-38s  %-5s  no match (%d words)"
                     % (short, "", n), 0))
        continue
    tva, score, tot = hit
    pct = 100.0 * score / tot
    for va, word in sites:
        d = va - sv
        tw = tgt.word(tva + d)
        if tw is None:
            rows.append(("  %08x  %-38s  +%-4x  ported VA out of range"
                         % (va, short, d), 0))
            continue
        k = kind(word)
        if tw == word:
            v, note = 2, "exact"
        elif k == "lui" and (tw >> 26) == 0x0F and (tw >> 16) == (word >> 16):
            v, note = 1, "lui, imm differs %04x" % (tw & 0xFFFF)
        elif k == "jal" and (tw >> 26) == (word >> 26):
            v, note = 1, "jal -> %08x" % ((tw & 0x03FFFFFF) << 2)
        else:
            v, note = 0, "WORD DIFFERS: %08x" % tw
        ok += 1 if v else 0
        exact += 1 if v == 2 else 0
        rows.append(("  %08x  %-38s  +%-4x  %08x@%.0f%%  %08x  %s"
                     % (va, short, d, tva, pct, tva + d, note), v))

for text, _v in rows:
    print(text)

print("\n%d of %d sites ported with the stock word intact (%d byte-exact)"
      % (ok, sum(len(v) for v in groups.values()), exact))
if orphans:
    print("\n%d sites outside any GR function (injected code regions, "
          "data words):" % len(orphans))
    for va, word in orphans[:400]:
        print("  %08x  %08x" % (va, word))

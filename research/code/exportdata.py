"""The export offsets tile perfectly but the bytes at them are wrong, so they
are relative to a data-region base. Solve for that base by scoring a layout
fit across all 2,061 Functions at each candidate."""
import collections, struct, sys
sys.path.insert(0, r"C:\Users\Tristan\Documents\GitHub\TomClancyPS2-ModStudio")
from tcps2.iso import Iso
from tcps2 import vokes, lin, upackage
from tcps2.upackage import compact_index

RS3 = r"E:\PS2 Games\Tom Clancy's Rainbow Six 3 (USA).iso"
with Iso(RS3) as iso:
    for arc in vokes.open_archives(iso, r"/VOKES\d\.IMG$"):
        if "/COMMON.LIN" in arc.files:
            data = lin.decompress(arc.read_entry(arc.files["/COMMON.LIN"]))
            break
sigs = [b for b, _ in upackage.packages(data)]
for base, _p in upackage.packages(data):
    try:
        names, imports, exports = upackage.tables(data, base)
    except Exception:
        continue
    if "m_bUseWheel" in names:
        break
funcs = [(n, s, o) for c, n, s, o in exports if c == "Function" and s > 12]
lo = min(o for _c, _n, s, o in exports if s > 0)
hi = max(o + s for _c, _n, s, o in exports if s > 0)
print("relative span %#x..%#x (%d bytes); file %d" % (lo, hi, hi - lo, len(data)))

def fit(B):
    good = 0
    trailers = collections.Counter()
    for nm, size, off in funcs:
        pos = B + off
        if pos < 0 or pos + size > len(data):
            return 0, None
        try:
            for _ in range(4):                       # super,next,scripttext,children
                _v, pos = compact_index(data, pos)
            pos += 8                                 # line, textpos
            ss = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            t = (B + off + size) - (pos + ss)
            if 0 <= t <= 32 and ss <= size:
                good += 1
                trailers[t] += 1
        except Exception:
            pass
    return good, trailers

cands = {}
cands["end of file"] = len(data) - hi
for i, s in enumerate(sigs):
    cands["before sig %d (%#x)" % (i, s)] = s - hi
cands["zero"] = 0
best = []
for label, B in cands.items():
    if B < -lo:
        continue
    good, tr = fit(B)
    if good > len(funcs) * 0.2:
        best.append((good, label, B, tr.most_common(3) if tr else []))
best.sort(reverse=True)
print("\ncandidates fitting more than 20%% of %d functions:" % len(funcs))
for good, label, B, tr in best[:8]:
    print("   %-28s B=%#010x  %5d (%.1f%%)  trailers %s"
          % (label, B, good, 100.0 * good / len(funcs), tr))
if not best:
    print("   none -- the layout guess is wrong too, not just the base")

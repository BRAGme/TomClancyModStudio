"""How many of the 132 magic hits are real packages? A 4-byte magic inside 2 MB
of object data will occur by chance, and a false one splits a gap that is
really contiguous."""
import sys
sys.path.insert(0, r"C:\Users\Tristan\Documents\GitHub\TomClancyPS2-ModStudio")
from tcps2.iso import Iso
from tcps2 import vokes, lin, upackage
from tcps2.upackage import Package, compact_index

RS3 = r"E:\PS2 Games\Tom Clancy's Rainbow Six 3 (USA).iso"
with Iso(RS3) as iso:
    for arc in vokes.open_archives(iso, r"/VOKES\d\.IMG$"):
        if "/COMMON.LIN" in arc.files:
            data = lin.decompress(arc.read_entry(arc.files["/COMMON.LIN"]))
            break

def tables_end(base):
    pkg = Package(data, base)
    if not (0 < pkg.n_names < 200000 and 0 <= pkg.n_imports < 100000
            and 0 < pkg.n_exports < 200000 and 0 < pkg.o_names < 4096):
        raise ValueError("implausible header")
    pos = base + pkg.o_names
    for _ in range(pkg.n_names):
        ln, pos = compact_index(data, pos)
        if not 0 < ln < 1024 or pos + ln + 4 > len(data):
            raise ValueError("bad name")
        pos += ln + 4
    for _ in range(pkg.n_imports):
        _c, pos = compact_index(data, pos); _n, pos = compact_index(data, pos)
        pos += 4; m, pos = compact_index(data, pos)
        if not 0 <= m < pkg.n_names:
            raise ValueError("bad import")
    for _ in range(pkg.n_exports):
        _c, pos = compact_index(data, pos); _s, pos = compact_index(data, pos)
        pos += 4; n, pos = compact_index(data, pos); pos += 4
        sz, pos = compact_index(data, pos)
        if sz > 0:
            _o, pos = compact_index(data, pos)
        if not 0 <= n < pkg.n_names:
            raise ValueError("bad export")
    return pos

real, fake = [], []
for base, _p in upackage.packages(data):
    try:
        real.append((base, tables_end(base)))
    except Exception as exc:
        fake.append((base, str(exc)[:40]))
print("%d magic hits: %d parse as real packages, %d do not"
      % (len(real) + len(fake), len(real), len(fake)))
print("first few that do not:", [(hex(b), why) for b, why in fake[:5]])

real.sort()
gaps, prev = [], 0
for s, e in real:
    if s > prev:
        gaps.append((prev, s))
    prev = max(prev, e)
if prev < len(data):
    gaps.append((prev, len(data)))
gaps.sort(key=lambda g: -(g[1] - g[0]))
print("\nlargest gaps using only real packages:")
for s, e in gaps[:6]:
    print("   %#010x .. %#010x   %9d bytes" % (s, e, e - s))
need = 2321838
fits = [(s, e) for s, e in gaps if e - s >= need]
print("\ngaps big enough for the script package's %d bytes: %d" % (need, len(fits)))
for s, e in fits:
    print("   %#x..%#x  -> base = %#x" % (s, e, s - 0x210a8))

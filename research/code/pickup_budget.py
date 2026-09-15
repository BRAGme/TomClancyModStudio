"""How many bytes would Rainbow Six 3 have to find to carry Ghost Recon 2's
weapon-pickup cluster?

Three costs per export that RS3 does not already have:
  * the object's serialised data (the `size` field)
  * a name table entry, if the name is new to RS3's pool
  * an export table row
"""
import re, sys
sys.path.insert(0, r"C:\Users\Tristan\Documents\GitHub\TomClancyPS2-ModStudio")
from tcps2.iso import Iso
from tcps2 import vokes, lin, upackage
from tcps2.upackage import compact_index, Package

GR2 = r"E:\PS2 Games\Tom Clancy's Ghost Recon 2 (USA) (En,Fr,Es).iso"
RS3 = r"E:\PS2 Games\Tom Clancy's Rainbow Six 3 (USA).iso"

PATTERNS = ("alterweapon", "groundweapon", "iofixedgun", "weapon2", "clips2",
            "bulletsinweapon2", "remainingbulletnum2", "mioweapon",
            "szengineweaponclass", "changeweapon", "canacceptactionkey",
            "r6getcircumstantialaction", "isinteractiveobject",
            "needswitchtoprimaryweapon", "adjustweapontype",
            "getprimaryweapon", "m_poldweapon", "m_weaponfake",
            "m_nbackuplastweapon", "m_fweapondiscardtime", "pickup")

def load(path, pattern, key):
    with Iso(path) as iso:
        for arc in vokes.open_archives(iso, pattern):
            if key in arc.files:
                return lin.decompress(arc.read_entry(arc.files[key]))
    raise SystemExit("no %s" % key)

def export_rows(data, base):
    """[(cls, name, size, rowBytes)] walking the export table by hand so the
    row's own byte cost can be measured."""
    pkg = Package(data, base)
    names, pos = [], base + pkg.o_names
    name_cost = {}
    for _ in range(pkg.n_names):
        start = pos
        ln, pos = compact_index(data, pos)
        nm = data[pos:pos + ln - 1].decode("latin-1")
        pos += ln + 4
        names.append(nm)
        name_cost[nm] = pos - start
    imports = []
    for _ in range(pkg.n_imports):
        _c, pos = compact_index(data, pos)
        _n, pos = compact_index(data, pos)
        pos += 4
        nm, pos = compact_index(data, pos)
        imports.append(names[nm])
    out = []
    for _ in range(pkg.n_exports):
        start = pos
        cls, pos = compact_index(data, pos)
        _s, pos = compact_index(data, pos)
        pos += 4
        nm, pos = compact_index(data, pos)
        pos += 4
        size, pos = compact_index(data, pos)
        if size > 0:
            _o, pos = compact_index(data, pos)
        cname = ("Class" if cls == 0 else
                 imports[-cls - 1] if cls < 0 else "(export)")
        out.append((cname, names[nm], size, pos - start))
    return names, out, name_cost

gr2 = load(GR2, r"/(VOKES\d|GR2)\.IMG$", "/COMMONOFF.LIN")
rs3 = load(RS3, r"/VOKES\d\.IMG$", "/COMMON.LIN")

rs3_names, rs3_exports = set(), set()
for base, _p in upackage.packages(rs3):
    try:
        n, _i, x = upackage.tables(rs3, base)
    except Exception:
        continue
    rs3_names |= set(n)
    rs3_exports |= {nm for _c, nm, _s, _o in x}
print("RS3 COMMON.LIN: %d distinct names, %d distinct export names"
      % (len(rs3_names), len(rs3_exports)))

rows = []
for base, _p in upackage.packages(gr2):
    try:
        names, exports, name_cost = export_rows(gr2, base)
    except Exception:
        continue
    for cname, nm, size, rowb in exports:
        low = nm.lower()
        if any(p in low for p in PATTERNS):
            rows.append((nm, cname, size, rowb,
                         name_cost.get(nm, 0), nm in rs3_exports,
                         nm in rs3_names))

seen = set()
uniq = []
for r in rows:
    if r[0] in seen:
        continue
    seen.add(r[0])
    uniq.append(r)
uniq.sort(key=lambda r: -r[2])

print("\n%-34s %-16s %7s %5s %5s  %s" %
      ("export", "class", "serial", "row", "name", "already in RS3?"))
need_serial = need_row = need_name = 0
have = 0
for nm, cname, size, rowb, namec, in_exp, in_names in uniq:
    mark = "export" if in_exp else ("name only" if in_names else "NO")
    print("%-34s %-16s %7d %5d %5d  %s" % (nm, cname, size, rowb, namec, mark))
    if in_exp:
        have += 1
        continue
    need_serial += size
    need_row += rowb
    need_name += 0 if in_names else namec

print("\n%d exports in the cluster; %d already exist in RS3" % (len(uniq), have))
print("bytes Rainbow Six 3 would have to find:")
print("   serialised objects  %6d" % need_serial)
print("   export table rows   %6d" % need_row)
print("   name table entries  %6d" % need_name)
print("   TOTAL               %6d" % (need_serial + need_row + need_name))
print("\nagainst 4,280 bytes of unreachable script found on the RS3 disc.")

# ---------------------------------------------------------------------------
# R6IOFixedGun is a SIBLING feature -- mounted guns -- that happens to share
# the IO prefix, and m_TrainingWeapon2 matched on "weapon2" but is a training
# variable. Neither is part of picking a weapon up off the ground.
NOT_PICKUP = {"R6IOFixedGun", "m_IOFixedGun", "m_TrainingWeapon2"}
min_serial = min_row = min_name = 0
for nm, cname, size, rowb, namec, in_exp, in_names in uniq:
    if in_exp or nm in NOT_PICKUP:
        continue
    min_serial += size
    min_row += rowb
    min_name += 0 if in_names else namec

print("\nminimal pickup set (dropping %s):" % ", ".join(sorted(NOT_PICKUP)))
print("   serialised objects  %6d" % min_serial)
print("   export table rows   %6d" % min_row)
print("   name table entries  %6d" % min_name)
print("   TOTAL               %6d" % (min_serial + min_row + min_name))

AVAIL = 4280
print("\navailable on the RS3 disc: %d bytes of unreachable script" % AVAIL)
for label, total in (("everything matched", need_serial + need_row + need_name),
                     ("minimal pickup set", min_serial + min_row + min_name)):
    gap = AVAIL - total
    print("   %-20s %6d  ->  %s by %d bytes"
          % (label, total, "FITS" if gap >= 0 else "SHORT", abs(gap)))

# ---------------------------------------------------------------------------
# The serialised objects can live anywhere there is room. The NAME TABLE and
# the EXPORT TABLE cannot: they are contiguous runs, and growing either one
# shifts every byte after it. The only way to add a row without growing the
# table is to overwrite a row that is already there -- which means the six
# unreachable classes give six rows and six names, and no more.
DEAD = {"R6XboxReticule": 1298, "R6RainbowVoices": 1019, "R6ConsoleXbox": 664,
        "R6XboxGadgetReticule": 617, "R6XboxGrenadeReticule": 563,
        "R6IOAlarmSystem": 119}
new_exports = [r for r in uniq if not r[5] and r[0] not in NOT_PICKUP]
new_names = [r for r in new_exports if not r[6]]
print("\nthe part that cannot use scattered space:")
print("   export rows needed   %3d   reusable from dead classes  %d"
      % (len(new_exports), len(DEAD)))
print("   name entries needed  %3d   reusable from dead classes  %d"
      % (len(new_names), len(DEAD)))
print("   short by             %3d rows and %d names"
      % (max(0, len(new_exports) - len(DEAD)),
         max(0, len(new_names) - len(DEAD))))
print("\n   (object data itself: %d bytes into %d bytes of dead class data --"
      % (min_serial, sum(DEAD.values())))
print("    that half fits, in six separate holes)")

"""The last reference channel: everything on the disc that is not a .LIN.

Mission objective classes are the obvious worry -- Rainbow Six 3 plainly has
hostage rescue, so a class called R6MObjRescueHostage being 'unreachable' is a
claim that needs the INI and DAT files checked before it is believed."""
import json, sys
sys.path.insert(0, r"C:\Users\Tristan\Documents\GitHub\TomClancyPS2-ModStudio")
from tcps2.iso import Iso
from tcps2 import vokes

ISO = r"E:\PS2 Games\Tom Clancy's Rainbow Six 3 (USA).iso"
free = json.load(open("free_tight.json"))
keys = {n: n.encode() for n in free}          # bare, not NUL-terminated
hits = {n: [] for n in free}

with Iso(ISO) as iso:
    for arc in vokes.open_archives(iso, r"/VOKES\d\.IMG$"):
        for name, e in sorted(arc.files.items()):
            if name.upper().endswith(".LIN"):
                continue
            try:
                data = arc.read_entry(e)
            except Exception:
                continue
            for nm, key in keys.items():
                if key in data:
                    hits[nm].append(name)
    # and the ISO's own files outside the archives
    for path in sorted(iso.entries()):
        ent = iso.find(path.replace(".", r"\.").replace("+", r"\+") + "$")
        if ent is None or getattr(ent, "is_dir", False) or ent.size > 8_000_000:
            continue
        try:
            data = iso.read(ent.lba, ent.size)
        except Exception:
            continue
        for nm, key in keys.items():
            if key in data:
                hits[nm].append("ISO:" + path)

still_free = {n: s for n, s in free.items() if not hits[n]}
lost = {n: hits[n] for n in free if hits[n]}
print("%d were free after the level scan" % len(free))
print("%d are referenced by a non-.LIN file after all" % len(lost))
for n, where in sorted(lost.items())[:14]:
    print("   %-38s %s" % (n, where[:3]))
print("\nSTILL FREE: %d classes, %d bytes"
      % (len(still_free), sum(still_free.values())))
json.dump(still_free, open("free_final.json", "w"), indent=1)
print("\nbiggest 15:")
for nm, s in sorted(still_free.items(), key=lambda kv: -kv[1])[:15]:
    print("   %-40s %6d" % (nm, s))

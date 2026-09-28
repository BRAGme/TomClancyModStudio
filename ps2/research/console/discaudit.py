"""What is ACTUALLY on each test disc, read off the disc.

Not "what did the build script intend" -- the whole reason the last two days
went sideways is that intent and artifact diverged silently. So: diff every
overlay word and every archive file against the pristine image and print what
really differs.
"""
import os
import struct
import sys

sys.path.insert(0, r"C:\Users\Tristan\Documents\GitHub\TomClancyPS2-ModStudio")
from tcps2 import dataedit, iso as isomod, lin, soz                  # noqa: E402
from tcps2.games import BY_ID                                        # noqa: E402

SRC = r"E:\PS2 Games\Tom Clancy's Rainbow Six 3 (USA).iso.orig"
HANG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hang")
p = BY_ID["r6_3_slus20883"]
STOCK = p.overlays[0]

orig = isomod.Iso(SRC)
ao = dataedit._archives(orig, p)
oent = orig.find(r"/SP\.SOZ$")
osoz = orig.read(oent.lba, oent.size)

for name in sorted(os.listdir(HANG)):
    if not name.lower().endswith(".iso"):
        continue
    path = os.path.join(HANG, name)
    print("=== %s ===" % name)
    d = isomod.Iso(path)
    # -- overlay words
    ent = d.find(r"/SP\.SOZ$")
    blob = d.read(ent.lba, ent.size)
    if blob == osoz:
        print("  SP.SOZ identical to stock")
    else:
        a = soz.SozImage.unpack(blob, 0x00100000)
        b = soz.SozImage.unpack(osoz, 0x00100000)
        # compare word by word over the image
        n = 0
        shown = 0
        for off in range(0, min(len(a.image), len(b.image)) - 3, 4):
            wa = struct.unpack_from("<I", a.image, off)[0]
            wb = struct.unpack_from("<I", b.image, off)[0]
            if wa != wb:
                n += 1
                if shown < 12:
                    print("    %08x  %08x -> %08x"
                          % (0x00100000 + off, wb, wa))
                    shown += 1
        print("  SP.SOZ: %d word(s) differ" % n)
    # -- data files
    al = dataedit._archives(d, p)
    changed = []
    for arc_name, arc in sorted(al.items()):
        a0 = ao.get(arc_name)
        if a0 is None:
            continue
        for key, e in sorted(arc.files.items()):
            e0 = a0.files.get(key)
            if e0 is None:
                continue
            b1, b0 = arc.read_entry(e), a0.read_entry(e0)
            if b1 == b0:
                continue
            if key.endswith(".LIN"):
                try:
                    p1, p0 = lin.decompress(b1), lin.decompress(b0)
                    nb = sum(1 for x, y in zip(p0, p1) if x != y)
                    changed.append("%s %s: %d payload byte(s), len %+d"
                                   % (arc_name, e.path, nb, len(p1) - len(p0)))
                    continue
                except Exception:                                    # noqa: BLE001
                    pass
            changed.append("%s %s: differs" % (arc_name, e.path))
    print("  %d data file(s) differ from stock" % len(changed))
    for line in changed[:12]:
        print("    %s" % line)
    d.close()
    print()
orig.close()

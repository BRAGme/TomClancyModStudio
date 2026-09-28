"""Regenerate a profile's relocation signature table.

    python tools/make_sigtable.py --soz path/to/SP.SOZ.orig
    python tools/make_sigtable.py --iso "Rainbow Six 3 (USA).iso"

Writes `tcps2/games/<profile>_sig.py`. Takes about a minute and a half for
Rainbow Six 3, which is why the result is committed rather than built at startup.

Run this whenever a new code option is added, because a new option brings new
addresses and the table has to cover them. `tests/run_tests.py` fails loudly if
it has not been run -- see `run_revision_table`.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tcps2 import revision                                     # noqa: E402
from tcps2.games import BY_ID                                  # noqa: E402
from tcps2.iso import Iso                                      # noqa: E402
from tcps2.soz import SozImage                                 # noqa: E402

HEADER = '''"""Relocation signatures for %(title)s -- GENERATED, do not hand-edit.

Written by `tools/make_sigtable.py` from the pristine %(overlay)s
(sha1 %(sha1)s, %(size)d bytes, base 0x%(base)08x).

Each row is `virtual address: (words before the address, the window in hex)`.
The window is verbatim out of the pristine image; `tcps2/revision.py` decides
which fields of it to ignore. A row that no longer agrees with the profile's own
stock word is dropped on load, so a stale table degrades into "this option is
disabled here" rather than into a wrong write.

%(stats)s
"""

SOURCE_SHA1 = "%(sha1)s"

SIGS = {
'''


def overlay_image(args, profile):
    spec = profile.overlays[0]
    if args.soz:
        raw = open(args.soz, "rb").read()
        return bytes(SozImage.unpack(raw, spec.base_va).image)
    with Iso(args.iso) as iso:
        ent = iso.find(spec.iso_pattern)
        if ent is None:
            raise SystemExit("%s is not on that disc" % spec.name)
        raw = iso.read(ent.lba, ent.size)
    img = SozImage.unpack(raw, spec.base_va)
    got = hashlib.sha1(bytes(img.image)).hexdigest()
    if spec.image_sha1 and got != spec.image_sha1:
        # Signatures cut from a patched image would encode this tool's own
        # words as if the game shipped them.
        for va, word in (profile.stock_words or {}).items():
            img.write_word(va, word)
        got = hashlib.sha1(bytes(img.image)).hexdigest()
        if got != spec.image_sha1:
            raise SystemExit(
                "that %s is neither pristine (%s) nor repairable to it -- it "
                "hashes to %s. Signatures must come from a stock image."
                % (spec.name, spec.image_sha1, got))
    return bytes(img.image)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="r6_3_slus20883")
    ap.add_argument("--soz", help="a pristine overlay container")
    ap.add_argument("--iso", help="a disc to take one from")
    ap.add_argument("--out", help="where to write it")
    args = ap.parse_args()
    if not (args.soz or args.iso):
        raise SystemExit("need --soz or --iso")

    profile = BY_ID[args.profile]
    spec = profile.overlays[0]
    data = overlay_image(args, profile)
    img = revision.Image(data, spec.base_va)

    need = revision.signature_addresses(profile, img)
    print("%d addresses need a signature" % len(need))
    t = time.time()
    sigs, bad = revision.build_signatures(img, need)
    print("built %d in %.0fs, refused %d" % (len(sigs), time.time() - t, len(bad)))
    for va, why in sorted(bad.items()):
        print("  REFUSED %s" % why)

    widths = sorted(s.width for s in sigs.values())
    stats = ("%d addresses, %d..%d words wide (median %d, mean %.1f), "
             "%.1f KiB of window.\n%d refused as not uniquely locatable."
             % (len(sigs), widths[0], widths[-1], widths[len(widths) // 2],
                sum(widths) / len(widths), sum(widths) * 4 / 1024.0, len(bad)))
    print(stats)

    out = args.out or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "tcps2", "games", "%s_sig.py" % profile.id)
    sha1 = hashlib.sha1(data).hexdigest()
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(HEADER % {"title": profile.title, "overlay": spec.name,
                           "sha1": sha1, "size": len(data),
                           "base": spec.base_va, "stats": stats})
        for key, (before, blob) in sorted(revision.pack_table(sigs).items()):
            if len(blob) <= 56:
                fh.write(' "%s": (%d, "%s"),\n' % (key, before, blob))
                continue
            fh.write(' "%s": (%d,\n' % (key, before))
            for i in range(0, len(blob), 56):
                fh.write('  "%s"%s\n' % (blob[i:i + 56],
                                         ")," if i + 56 >= len(blob) else ""))
        fh.write("}\n")
        if bad:
            fh.write("\n#: addresses with no unique signature. Every option that\n"
                     "#: touches one of these is disabled on any disc that is not\n"
                     "#: the exact revision the profile was built for.\n")
            fh.write("NO_SIGNATURE = {\n")
            for va, why in sorted(bad.items()):
                fh.write(' 0x%08x: "%s",\n' % (va, why.replace('"', "'")))
            fh.write("}\n")
        else:
            fh.write("\nNO_SIGNATURE = {}\n")
    print("wrote %s (%.1f KiB)" % (out, os.path.getsize(out) / 1024.0))


if __name__ == "__main__":
    main()

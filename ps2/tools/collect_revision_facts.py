"""Collect everything needed to support another pressing of a supported disc.

    python tools/collect_revision_facts.py "path/to/their.iso"

Reads only. Prints a short block to paste back, and -- if the overlay turns out
to be a different build -- writes the overlay container beside the script, which
is about 1.8 MB for Rainbow Six 3 and is the ONLY file needed to extend support.
Nobody has to send a disc image.
"""

from __future__ import annotations

import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tcps2.detect import identify                              # noqa: E402
from tcps2.iso import Iso                                      # noqa: E402
from tcps2.soz import SozImage                                 # noqa: E402


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    path = sys.argv[1]
    det = identify(path)
    if not det.ok:
        print("not a supported disc: %s" % det.message)
        return 1
    profile = det.profile
    spec = profile.overlays[0] if profile.overlays else None

    print("----- paste this back -----")
    print("game          %s (%s)" % (profile.title, profile.serial))
    print("volume id     %s" % det.volume)
    print("boot file     %s" % det.boot)
    print("disc CRC      %s   (profile expects %s)"
          % (det.crc, profile.pcsx2_crc))

    with Iso(path) as iso:
        ent = iso.find(r"/" + profile.boot.replace(".", r"\.") + "$")
        if ent is not None:
            boot = iso.read(ent.lba, ent.size)
            print("boot size     %d" % len(boot))
            print("boot sha1     %s" % hashlib.sha1(boot).hexdigest())
        if spec is None:
            print("---------------------------")
            return 0
        ent = iso.find(spec.iso_pattern)
        if ent is None:
            print("%-13s MISSING FROM THIS DISC" % spec.name)
            print("---------------------------")
            return 0
        container = iso.read(ent.lba, ent.size)

    print("%-13s %d bytes in a %d-byte extent" % (spec.name, ent.size, ent.size))
    if spec.kind == "soz":
        img = bytes(SozImage.unpack(container, spec.base_va).image)
        got = hashlib.sha1(img).hexdigest()
        print("overlay size  %d" % len(img))
        print("overlay sha1  %s" % got)
        print("              %s"
              % ("SAME as the profile's image -- nothing has to move, this disc "
                 "only needs its CRC accepting"
                 if got == spec.image_sha1 else
                 "DIFFERENT from the profile's %s -- send the file below"
                 % spec.image_sha1))
        same = got == spec.image_sha1
    else:
        same = True
    print("---------------------------")

    if not same:
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "%s.%s.container" % (spec.name, det.crc))
        with open(out, "wb") as fh:
            fh.write(container)
        print()
        print("wrote %s (%.1f MB)" % (out, len(container) / 1e6))
        print("That one file is enough to build a signature table for this "
              "pressing. The disc image is not needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

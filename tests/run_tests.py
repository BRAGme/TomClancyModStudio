"""End-to-end suite.

Builds a small synthetic disc carrying a real stock overlay and drives the
patcher against it, so nothing here can damage a retail ISO. Point it at a
stock `SP.SOZ` container, or at a Rainbow Six 3 disc it can take one from:

    python tests/run_tests.py --soz path/to/sp.soz.orig
    python tests/run_tests.py --iso "Tom Clancy's Rainbow Six 3 (USA).iso"
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from make_fixture import build  # noqa: E402

from tcps2 import engine  # noqa: E402
from tcps2.detect import identify  # noqa: E402
from tcps2.iso import Iso  # noqa: E402
from tcps2.soz import SozImage  # noqa: E402
from tcps2.games.r6_3 import PROFILE, STOCK  # noqa: E402

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("  %s  %s%s" % ("PASS" if ok else "FAIL", name,
                          ("   " + detail) if detail and not ok else ""))
    return ok


def stock_container(args):
    """The pristine SP.SOZ container, from wherever the caller pointed us."""
    if args.soz:
        return open(args.soz, "rb").read()
    if args.iso:
        with Iso(args.iso) as iso:
            ent = iso.find(r"/SP\.SOZ$")
            raw = iso.read(ent.lba, ent.size)
        img = SozImage.unpack(raw, PROFILE.overlays[0].base_va)
        if hashlib.sha1(bytes(img.image)).hexdigest() == PROFILE.overlays[0].image_sha1:
            return raw
        # the disc is patched -- put the known words back to recover stock
        for va, word in STOCK.items():
            img.write_word(va, word)
        if hashlib.sha1(bytes(img.image)).hexdigest() != PROFILE.overlays[0].image_sha1:
            raise SystemExit("that ISO carries changes this tool does not know "
                             "about; pass --soz with a stock container instead")
        return SozImage(img.image, PROFILE.overlays[0].base_va, len(raw)).pack()
    raise SystemExit("need --soz or --iso")


def boot_elf(args):
    if args.iso:
        with Iso(args.iso) as iso:
            ent = iso.find(r"/SLUS_208\.83$")
            if ent:
                return iso.read(ent.lba, ent.size)
    # a stand-in that still parses: the CRC check just won't match
    return b"\x7fELF" + b"\0" * 4092


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--soz")
    ap.add_argument("--iso")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    work = tempfile.mkdtemp(prefix="tcms-test-")
    try:
        run(args, work)
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)

    print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
    return 1 if FAIL else 0


def run(args, work):
    base = PROFILE.overlays[0].base_va
    soz = stock_container(args)
    iso_path = os.path.join(work, "FIXTURE.iso")
    build(iso_path, [("SP.SOZ", soz), ("SLUS_208.83", boot_elf(args))])

    print("\n[disc]")
    det = identify(iso_path)
    check("a supported disc is recognised", det.ok and det.profile is PROFILE,
          det.message)
    with Iso(iso_path) as iso:
        ent = iso.find(r"/SP\.SOZ$")
        check("SP.SOZ is found at its own extent", ent is not None and ent.size == len(soz))

    print("\n[overlay]")
    img = SozImage.unpack(soz, base)
    check("overlay decompresses to the expected size",
          len(img.image) == PROFILE.overlays[0].image_size)
    check("overlay hash matches the profile",
          hashlib.sha1(bytes(img.image)).hexdigest() == PROFILE.overlays[0].image_sha1)
    bad = [(va, w) for va, w in STOCK.items() if img.read_word(va) != w]
    check("every stock word in the profile matches the image (%d sites)" % len(STOCK),
          not bad, "mismatched: %s" % bad[:4])
    check("pack/unpack round-trips",
          SozImage.unpack(img.pack(), base).image == img.image)

    print("\n[apply]")
    vals = PROFILE.defaults()
    pl = engine.plan(iso_path, PROFILE, vals)
    check("plan finds the disc pristine", pl.pristine_source == "hash")
    check("plan raises no warnings", not pl.warnings, str(pl.warnings))
    r = engine.apply(iso_path, PROFILE, vals)
    check("every word applied is verified from the disc",
          r["applied"] == r["verified"] and r["applied"] > 0,
          "%d of %d" % (r["verified"], r["applied"]))
    check("a backup was taken", os.path.exists(r["backup"]))

    print("\n[re-apply from pristine, not from the patched disc]")
    vals2 = dict(vals, wave_total=99, wave_trigger=5, wave_gate="away",
                 bodies="30", decal_ring=64, viewmodel=False, fx_weather=False)
    r2 = engine.apply(iso_path, PROFILE, vals2)
    check("second apply verifies", r2["applied"] == r2["verified"])
    with Iso(iso_path) as iso:
        ent = iso.find(r"/SP\.SOZ$")
        live = SozImage.unpack(iso.read(ent.lba, ent.size), base)
    want = {0x0040AF58: 0x24020063, 0x0040AFDC: 0x24030005,
            0x0040A874: 0x24020005, 0x0040A790: 0x14400003,
            0x00379B30: 0x24060040, 0x00317600: 0x3C0341F0}
    for va, w in want.items():
        check("0x%08x holds %08x" % (va, w), live.read_word(va) == w,
              "reads %08x" % live.read_word(va))
    for va in (0x00302DA8, 0x003531D0):
        check("0x%08x went back to stock when its option was cleared" % va,
              live.read_word(va) == STOCK[va], "reads %08x" % live.read_word(va))

    print("\n[restore]")
    rv = engine.revert(iso_path, PROFILE)
    check("restore reports the stock hash", rv["hash_ok"])
    with Iso(iso_path) as iso:
        ent = iso.find(r"/SP\.SOZ$")
        check("the container is byte-identical to stock",
              iso.read(ent.lba, ent.size) == soz)

    print("\n[settings model]")
    s = PROFILE.setting("wave_total")
    check("an out-of-range value is clamped", s.coerce(9999) == s.maximum)
    check("nonsense falls back to the default", s.coerce("banana") == s.default)
    off = dict(PROFILE.defaults(), wave_enable=False)
    check("no wave words are emitted when wave mode is off",
          not any("wave:" in e.note for e in PROFILE.build_edits(off)))
    check("the cheat file is empty when wave mode is off",
          not PROFILE.build_pnach(off))
    check("a dependency reports as unmet",
          PROFILE.unmet("wave_total", off) == ["Enable wave mode"])

    print("\n[cheat file]")
    words = PROFILE.build_pnach(PROFILE.defaults())
    check("the cave is 67 words plus a hijack", len(words) == 68)
    path = engine.write_pnach(os.path.join(work, "x.pnach"), PROFILE, words, "21CC1EC3")
    text = open(path, encoding="utf-8").read()
    check("every word becomes a patch line", text.count("patch=1,EE,") == 68)
    check("no [section] headers -- they never load mid-session",
          "[" not in text.replace("[21CC1EC3]", ""))
    engine.write_pnach(path, PROFILE, words, "21CC1EC3")
    check("rewriting does not duplicate the block",
          open(path, encoding="utf-8").read().count("patch=1,EE,") == 68)

    print("\n[crc]")
    check("the PCSX2 CRC is an XOR of every word",
          engine.pcsx2_crc(b"\x01\x00\x00\x00\x02\x00\x00\x00") == "00000003")


if __name__ == "__main__":
    raise SystemExit(main())

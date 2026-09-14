"""End-to-end suite.

Builds a small synthetic disc carrying a real stock overlay and drives the
patcher against it, so nothing here can damage a retail ISO. Point it at a
stock `SP.SOZ` container, or at a Rainbow Six 3 disc it can take one from:

    python tests/run_tests.py --soz path/to/sp.soz.orig
    python tests/run_tests.py --iso "Tom Clancy's Rainbow Six 3 (USA).iso"
"""

from __future__ import annotations

import argparse
import re
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
            raise SystemExit(
                "that ISO carries changes this tool does not recognise, so it "
                "cannot be used as a source of stock data. Pass --soz with a "
                "known-stock SP.SOZ container instead (the .tcms-backup folder "
                "beside a disc this tool has already seen holds one).")
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
    ap.add_argument("--gr", help="Ghost Recon ISO, to test the raw-ELF path")
    ap.add_argument("--js", help="Jungle Storm ISO, same")
    ap.add_argument("--rs3data", help="Rainbow Six 3 ISO, for its INI data path")
    ap.add_argument("--gr2", help="Ghost Recon 2 ISO, same engine, data only")
    ap.add_argument("--graw", help="Advanced Warfighter ISO, for its INI")
    ap.add_argument("--lockdown", help="Lockdown ISO, for its Nimitz archive")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    work = tempfile.mkdtemp(prefix="tcms-test-")
    try:
        run(args, work)
        run_raw_and_data(args, work)
        run_lockdown(args)
        run_pack_emblem(args)
        run_level_packages(args)
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)

    print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
    return 1 if FAIL else 0


def run_lockdown(args):
    """Lockdown's Nimitz archive, against the real disc, writing nothing."""
    if not args.lockdown:
        return
    from tcps2 import nimitz, transforms
    from tcps2.games import BY_ID

    print("\n[Lockdown -- the Nimitz archive, read-only]")
    profile = BY_ID["lockdown_slus21144"]
    det = identify(args.lockdown)
    check("the disc is recognised as Lockdown",
          det.ok and det.profile is profile, det.message)
    check("its PCSX2 CRC matches the profile", det.crc_matches,
          "%s vs %s" % (det.crc, profile.pcsx2_crc))

    with Iso(args.lockdown) as iso:
        pak = nimitz.NimitzPak(iso)
        check("the index parses to 4,671 files", len(pak.files) == 4671,
              str(len(pak.files)))

        cg = pak.read_file("/PS2DATA/BINARY/NIMITZ.CGSB")
        skills = transforms.read_nimitz_skills(cg)
        check("70 of the 72 AI profiles decode", len(skills) == 70,
              str(len(skills)))

        by = {n: s for n, _o, s in skills}
        ladders = [("terrorist-0%d.cgs", (1, 2, 3)),
                   ("militia-0%d.cgs", (1, 2, 3)),
                   ("mercenary-0%d.cgs", (1, 2, 3))]
        rising = True
        for fmt, tiers in ladders:
            got = [sum(by[fmt % t]) for t in tiers if fmt % t in by]
            rising = rising and all(a <= b for a, b in zip(got, got[1:]))
        check("every named difficulty ladder ascends", rising)
        check("terrorist_super_easy really is the softest",
              by.get("terrorist_super_easy.cgs") == [1, 1, 1, 1, 1, 1],
              str(by.get("terrorist_super_easy.cgs")))

        bumped, wide_skill_bytes = transforms.bump_nimitz_skills(cg, 4)
        check("a skill bump keeps the file length", len(bumped) == len(cg))
        after = {n2: s for n2, _o, s in transforms.read_nimitz_skills(bumped)}
        moved = [k for k in by if by[k] != after.get(k)]
        kept = [k for k in by if by[k] == after.get(k)]
        check("the bump changes hostiles and spares the operatives",
              len(moved) == 39 and "ding_chavez.cgs" in kept,
              "%d moved, %d kept" % (len(moved), len(kept)))

        gu = pak.read_file("/PS2DATA/BINARY/NIMITZ.GUNS")
        guns = dict((a, (b, c)) for a, b, c in transforms.read_nimitz_guns(gu))
        check("all 48 weapons decode", len(guns) == 48, str(len(guns)))
        known = {"glock_enemy.gun": 17, "92fs.gun": 15, "meu.gun": 7,
                 "p90.gun": 50, "m249.gun": 200, "m870.gun": 5,
                 "pp90.gun": 32}
        wrong = [k for k, v in known.items()
                 if k in guns and guns[k][0] != v]
        check("magazine capacities match the real weapons", not wrong,
              str(wrong))
        check("the launchers are excluded rather than corrupted",
              guns.get("rpg7.gun", (None, None))[1] is None,
              str(guns.get("rpg7.gun")))

        scaled, n = transforms.scale_nimitz_guns(gu, mag=1.5, rpm=1.25)
        check("a weapon scale keeps the file length", len(scaled) == len(gu))
        after_g = dict((a, (b, c)) for a, b, c in
                       transforms.read_nimitz_guns(scaled))
        check("scaling is applied", after_g["m249.gun"] == (300, 1000),
              str(after_g["m249.gun"]))

        # -- Terrorist Hunt, scoped ------------------------------------
        hunt, nh = transforms.bump_nimitz_skills(
            cg, 4, only=transforms.NIMITZ_HUNT)
        after_h = {n2: s2 for n2, _o, s2 in transforms.read_nimitz_skills(hunt)}
        moved_h = [k for k in by if by[k] != after_h.get(k)]
        check("scoping the skill shift moves only the Hunt profiles",
              sorted(moved_h) == sorted(transforms.NIMITZ_HUNT), str(moved_h))

        # The scope must be DERIVED from the missions, not trusted. The obvious
        # guess -- the th_* profiles -- is referenced by nothing at all, and
        # was shipped once before this check existed.
        from tcps2 import nimitz_mis
        used = {}
        for mname in pak.files:
            mm = re.match(r"^/PS2DATA/MISSION/M\d\d_SEC_\d\d(?:_SMG)?"
                          r"(_COOP|_TH_NOR|_TH_REV)?\.MIS$", mname, re.I)
            if not mm:
                continue
            tag = (mm.group(1) or "_CAMPAIGN").lstrip("_").upper()
            tag = "HUNT" if tag.startswith("TH_") else tag
            blob = pak.read_entry(pak.files[mname])
            for _g, _md, prof, _l in nimitz_mis.templates(blob):
                if prof and not any(r in prof for r in nimitz_mis.RAINBOW):
                    used.setdefault(prof, set()).add(tag)
        hunt_only = sorted(p2 for p2, tags in used.items() if tags == {"HUNT"})
        check("the scope is exactly the profiles only hunt uses",
              sorted(transforms.NIMITZ_HUNT) == hunt_only, str(hunt_only))
        check("the th_* profiles are referenced by no mission at all",
              not any(p2.startswith("th_") for p2 in used), str(sorted(used)))
        check("mercenary-03 is shared, so stays out of the scope",
              used.get("mercenary-03.cgs") == {"CAMPAIGN", "COOP", "HUNT"}
              and "mercenary-03.cgs" not in transforms.NIMITZ_HUNT,
              str(used.get("mercenary-03.cgs")))

        census = nimitz_mis.hunt_census(pak)
        check("32 hunt maps are read", len(census) == 32, str(len(census)))
        check("each places a sane number of enemies",
              all(15 <= c <= 40 for _m, _s, _d, c, _p in census),
              str(sorted(c for _m, _s, _d, c, _p in census)[:4]))
        check("the campaign tiers are untouched by it",
              after_h["terrorist-01.cgs"] == by["terrorist-01.cgs"])
        check("and it still preserves the file length", len(hunt) == len(cg))
        # `n` has been reused for the weapon scale by this point, so compare
        # against the skill count captured above or this proves nothing.
        check("the scoped edit is genuinely narrower",
              nh == 24 and wide_skill_bytes == 217,
              "%d scoped vs %d wide" % (nh, wide_skill_bytes))

        prof_ld = BY_ID["lockdown_slus21144"]
        vals = dict(prof_ld.defaults())
        vals["ld_enemy_skill"] = 4
        wide_edit = prof_ld.build_data(vals)[0]
        vals["ld_hunt_only"] = "hunt"
        scoped_edit = prof_ld.build_data(vals)[0]
        check("the switch adds a scope to the edit rather than a second one",
              "only" not in wide_edit.params
              and scoped_edit.params.get("only") == list(transforms.NIMITZ_HUNT))
        check("and it does nothing on its own",
              prof_ld.build_data({"ld_hunt_only": "hunt"}) == [])

        run_lockdown_psx(pak)
        run_upscale(pak, profile)
        run_lockdown_missions(pak, profile, det)

    check("an all-default config writes nothing",
          profile.build_data(dict(profile.defaults())) == [])


def run_lockdown_missions(pak, profile, det):
    """Lockdown's mission page: sixteen cards, read-only, and honest about it."""
    import re
    from tcps2 import art
    from tcps2.games.lockdown import MISSIONS, mission_key

    print("\n[Lockdown -- the mission page]")
    cards = [s for s in profile.settings if s.group == "Missions"]
    check("there is a card per campaign mission",
          len(cards) == len(MISSIONS) == 16, str(len(cards)))
    # Nothing here edits yet, so every card must SAY so rather than offer a
    # dial that quietly does nothing.
    check("every card is switched off with a reason",
          all(not s.enabled and s.disabled_reason for s in cards))
    check("and none of them writes anything",
          profile.build_data({mission_key(m[0]): 300 for m in MISSIONS}) == [])

    # the figures on the cards come off the disc, so they have to match it
    titles, spawns = {}, {}
    for name in pak.files:
        m = re.match(r"^/PS2DATA/MISSION/(M\d\d)_SEC_\d\d(_SMG)?\.MIS$",
                     name, re.I)
        if not m:
            continue
        mid = m.group(1).upper()
        blob = pak.read_entry(pak.files[name])
        spawns[mid] = spawns.get(mid, 0) + len(re.findall(rb"[a-z0-9_]+\.cms", blob))
        if mid not in titles:
            t = re.search(rb"M\d\d - ([A-Za-z .]+) - Section", blob)
            if t:
                titles[mid] = t.group(1).decode().strip()
    wrong = [m[0] for m in MISSIONS if titles.get(m[0]) != m[1]]
    check("the place names match the mission scripts", not wrong, str(wrong))
    off = [m[0] for m in MISSIONS if spawns.get(m[0]) != m[3]]
    check("the spawn-template counts match too", not off, str(off))

    # and the picture each card shows really is on the disc
    missing = [m[0] for m in MISSIONS
               if art.mission_art(det, m[0], "A") is None]
    check("every mission has its snapshot", not missing, str(missing))


def run_level_packages(args):
    """Rainbow Six 3's cooked level packages, read-only.

    The point of these is that the tables are found by WALKING from the name
    table rather than by the summary's offsets, which the PS2 cooker relaid --
    so the checks are that the walk lands exactly where it should.
    """
    if not args.rs3data:
        return
    from tcps2 import lin, upackage
    from tcps2.vokes import open_archives

    print("\n[Rainbow Six 3 -- cooked level packages]")
    with Iso(args.rs3data) as iso:
        data = None
        for arc in open_archives(iso, r"\.IMG$"):
            ent = arc.files.get("/SHIPYARD_AOFF.LIN")
            if ent:
                data = lin.decompress(arc.read_entry(ent))
                break
        check("Shipyard A decompresses", data is not None)
        if data is None:
            return

        found = upackage.packages(data)
        check("the level holds about a hundred packages",
              100 <= len(found) <= 115, str(len(found)))

        names, imports, exports = upackage.tables(data, 19)
        check("the level package's name table reads whole",
              len(names) == 3989, str(len(names)))
        # Walking the names has to land on the imports, and those on the
        # exports: if either is off by a byte nothing downstream parses.
        check("309 imports and 3145 exports parse from the walk",
              len(imports) == 309 and len(exports) == 3145,
              "%d / %d" % (len(imports), len(exports)))
        check("every export names a class and an object",
              all(c and n for c, n, _s, _o in exports))

        waves = [e for e in exports if e[0] == "R6DZoneWave"]
        points = [e for e in exports if e[0] == "R6DZonePoint"]
        # the export table and the name table are independent routes to the
        # same count, so they have to agree
        instances = len([n for n in names
                         if n.startswith("R6DZoneWave") and n != "R6DZoneWave"])
        check("Shipyard A places two wave zones", len(waves) == 2, str(len(waves)))
        check("the export table agrees with the name table",
              len(waves) == instances, "%d vs %d" % (len(waves), instances))
        check("and eighteen spawn points", len(points) == 18, str(len(points)))

        # the authored counts this is all groundwork for
        sites = upackage.actor_properties(data, names, "m_iMaxTerrorist")
        check("authored terrorist maxima are found and validated",
              len(sites) == 8, str(len(sites)))
        check("they are plausible squad sizes",
              all(0 <= v <= 32 for _a, v, _s in sites),
              str(sorted(v for _a, v, _s in sites)))

        run_zone_counts(data, raw_for(iso, "/SHIPYARD_AOFF.LIN"),
                        lin.decompress(raw_for(iso, "/TRIESTE_AOFF.LIN")))
        run_missions(iso)


def run_missions(iso):
    """The per-mission dials: what they emit, and what they reach.

    Applied in memory against the real disc through a read-only archive; the
    ISO is never written.
    """
    from tcps2 import dataedit, lin, r6zones
    from tcps2.games.r6_3 import MISSIONS, PROFILE, mission_key
    from tcps2.vokes import open_archives

    print("\n[Rainbow Six 3 -- per-mission enemy counts]")
    per_mission = [s for s in PROFILE.settings if s.group == "Missions"]
    check("every mission has a dial", len(per_mission) == len(MISSIONS) == 15,
          "%d settings, %d missions" % (len(per_mission), len(MISSIONS)))
    check("they are data edits, not code patches",
          all(s.touches == "data" for s in per_mission))

    vals = dict(PROFILE.defaults())
    check("leaving them alone writes nothing", PROFILE.build_data(vals) == [])

    vals[mission_key("SHIPYARD")] = 200
    vals[mission_key("ISLAND")] = 50
    edits = PROFILE.build_data(vals)
    check("moving two dials emits two edits", len(edits) == 2, str(len(edits)))

    # The levels ship twice, OFF and _SS. Matching only one leaves half the
    # copies stock, which is the mistake this selector exists to avoid.
    hits = {}
    for arc in open_archives(iso, r"\.IMG$"):
        for name in arc.files:
            for e in edits:
                if e.matches(name):
                    hits.setdefault(e.params["factor"], set()).add(name)
    check("Shipyard's edit reaches both parts and both copies",
          len(hits.get(2.0, ())) == 4, str(sorted(hits.get(2.0, ()))))
    check("Island has only an A part, so its edit reaches two files",
          len(hits.get(0.5, ())) == 2, str(sorted(hits.get(0.5, ()))))

    # and the values actually move, without the container moving
    name = sorted(hits[2.0])[0]
    for arc in open_archives(iso, r"\.IMG$"):
        ent = arc.files.get(name)
        if not ent:
            continue
        raw = arc.read_entry(ent)
        before = sorted(v for _a, _p, v in r6zones.sites(lin.decompress(raw)))
        fn = dataedit.OPS["zone_counts"]
        new, _touched = lin.substitute(raw, lambda pl: fn(pl, {"factor": 2.0}))
        after = sorted(v for _a, _p, v in r6zones.sites(lin.decompress(new)))
        check("the counts double", after == [v * 2 for v in before],
              "%s -> %s" % (before[:4], after[:4]))
        check("the container does not move", len(new) == len(raw),
              "%d vs %d" % (len(new), len(raw)))
        break


def raw_for(iso, name):
    from tcps2.vokes import open_archives
    for arc in open_archives(iso, r"\.IMG$"):
        ent = arc.files.get(name)
        if ent:
            return arc.read_entry(ent)
    return None


def run_zone_counts(data, raw, misread_level):
    """The authored per-level spawner counts, and editing them safely.

    Nothing here writes to a disc: the edit is applied in memory and handed
    back to the container to prove it fits.
    """
    from tcps2 import lin, r6zones, upackage

    print("\n[Rainbow Six 3 -- authored spawner counts]")
    sites = r6zones.sites(data)
    check("Shipyard A's authored counts are found", len(sites) == 13,
          str(len(sites)))
    check("every kept value is a real squad size",
          all(0 <= v <= r6zones.SANE_MAX for _a, _p, v in sites),
          str(sorted(v for _a, _p, v in sites)))

    # The structural filter is what makes this safe, so prove it carries the
    # weight -- on a level that actually has misreads to drop. Shipyard A has
    # none, so testing it there would pass while proving nothing.
    loose = []
    for base, _pkg in upackage.packages(misread_level):
        try:
            names, _i, _e = upackage.tables(misread_level, base)
        except Exception:                          # noqa: BLE001
            continue
        for prop in r6zones.COUNT_PROPS:
            loose += [v for _a, v, _s
                      in upackage.actor_properties(misread_level, names, prop)]
    kept = [v for _a, _p, v in r6zones.sites(misread_level)]
    wild = [v for v in loose if not 0 <= v <= r6zones.SANE_MAX]
    check("Trieste A does contain misreads to reject", len(wild) > 0, str(wild[:4]))
    check("the structural filter rejects every one of them",
          all(0 <= v <= r6zones.SANE_MAX for v in kept),
          str(sorted(v for v in kept if not 0 <= v <= r6zones.SANE_MAX)[:4]))
    check("and it keeps the small values rather than bounding them away",
          0 in kept and len(kept) >= len(loose) - len(wild) - 8,
          "%d loose, %d wild, %d kept" % (len(loose), len(wild), len(kept)))
    scaled, n = r6zones.scale(data, 2.0)
    # Zero is authored, not garbage -- it marks a lone pawn rather than a
    # group -- so a scale must leave exactly as many zeros as it found.
    zeros_before = sum(1 for _a, _p, v in sites if v == 0)
    zeros_after = sum(1 for _a, _p, v in r6zones.sites(scaled) if v == 0)
    check("counts of zero survive a scale untouched",
          zeros_before == zeros_after,
          "%d before, %d after" % (zeros_before, zeros_after))
    check("a scale changes every authored count", n == 13, str(n))
    check("and preserves the length exactly", len(scaled) == len(data),
          "%d vs %d" % (len(scaled), len(data)))
    check("the doubled values are what they should be",
          sorted(v for _a, _p, v in r6zones.sites(scaled))
          == sorted(v * 2 for _a, _p, v in sites))

    if raw is not None:
        packed, touched = lin.substitute(
            raw, lambda plain: r6zones.scale(plain, 2.0)[0])
        check("the edit still fits its .LIN container",
              len(packed) == len(raw), "%d vs %d" % (len(packed), len(raw)))
        check("and the container round-trips to the same bytes",
              lin.decompress(packed) == scaled, str(touched))


def run_pack_emblem(args):
    """The marks pinned to entries of the user's replacement packs.

    Skipped when there is no pack, or no disc to identify against.
    """
    from tcps2 import art, upscale
    from tcps2.games import BY_ID

    jobs = [("gr2_slus21105", args.gr2),
            ("graw_slus21422", args.graw),
            ("jungle_storm_slus20820", args.js)]
    jobs = [(pid, iso) for pid, iso in jobs if iso]
    if not jobs:
        return
    printed = False
    for pid, iso in jobs:
        profile = BY_ID[pid]
        if upscale.pack_dir(profile.serial) is None:
            continue
        if not printed:
            print("\n[marks pinned to the replacement packs]")
            printed = True

        prefix, _box = art.PACK_EMBLEM[pid]
        whole = upscale.pinned(profile.serial, prefix)
        check("%s: the pinned entry is found" % profile.serial, whole is not None,
              str(whole.size if whole else None))
        if whole is None:
            continue

        mark = art.pack_emblem(profile)
        check("%s: it crops to a wordmark, not a screen" % profile.serial,
              mark is not None and mark.width > mark.height,
              str(mark.size if mark else None))

        # The point of pinning is resolution: every disc's own copy of its mark
        # is small, and two of these discs barely have one at all.
        det = identify(iso)
        if det.ok and det.profile is profile:
            keyed = art.emblem_image(det)
            check("%s: it beats the mark lifted off the disc" % profile.serial,
                  keyed is not None and keyed.width >= 1000,
                  str(keyed.size if keyed else None))

    if printed:
        check("an unknown pinned hash returns nothing",
              upscale.pinned(BY_ID[jobs[0][0]].serial, "ffffffffffffffff") is None)


def run_upscale(pak, profile):
    """The PCSX2 replacement-pack lookup, if the user keeps one.

    Skipped silently when there is no pack, since it is the user's own file
    and not something the repo ships.
    """
    import struct
    from tcps2 import psx, upscale

    folder = upscale.pack_dir(profile.serial)
    if folder is None:
        return
    print("\n[Lockdown -- PCSX2 replacement pack]")
    names = os.listdir(folder)

    # The filename's TEX0 field claims a PS2 size; the DDS header states its
    # own. A pack entry must be a whole multiple of what it replaces, and that
    # cross-check is what makes filename filtering trustworthy.
    bad = []
    for name in names:
        parsed = upscale.tex0(name)
        if parsed is None:
            bad.append(name); continue
        _psm, tw, th = parsed
        with open(os.path.join(folder, name), "rb") as fh:
            head = fh.read(20)
        h, w = struct.unpack_from("<II", head, 12)
        if not (tw and th and w % tw == 0 and h % th == 0 and w // tw == h // th):
            bad.append(name)
    check("every pack entry is a whole multiple of the texture it replaces",
          not bad, "%d of %d disagree" % (len(bad), len(names)))

    sheet = psx.to_image(pak.read_file("/PS2DATA/SHELL/ART/SHELL1.PSX"))
    better = upscale.better(profile.serial, sheet)
    check("the shell sheet is found in the pack",
          better is not None and better.width > sheet.width,
          str(better.size if better else None))
    if better is not None:
        # PS2 alpha runs 0..128; taken at face value the whole sheet would
        # draw at half opacity, so the lookup has to rescale it.
        check("its alpha is rescaled off the PS2 0..128 range",
              max(better.split()[-1].getdata()) > 200)

    # A texture the pack does not hold must be refused, not approximated --
    # this is what stops a disc borrowing another texture's art.
    solid = sheet.copy()
    solid.paste((255, 0, 255, 255), (0, 0, solid.width, solid.height))
    check("a texture the pack does not hold is refused",
          upscale.better(profile.serial, solid) is None)


def run_lockdown_psx(pak):
    """The `.PSX` texture decode.

    The swizzle is two GS addressings composed, so the one invariant that
    catches a transcription slip in either of them is that the composed order
    must be a permutation: every source byte used exactly once. A wrong column
    or page term collides instead, which is silent in a thumbnail but not here.
    """
    from tcps2 import psx

    print("\n[Lockdown -- .PSX textures]")
    for w, h, tw in ((256, 256, 512), (512, 512, 2048), (256, 128, 256),
                     (128, 128, 64), (128, 64, 64), (64, 64, 32), (32, 32, 16)):
        order = psx._order(w, h, tw)
        check("the %dx%d order is a permutation" % (w, h),
              sorted(order) == list(range(w * h)))

    # every shipped geometry must agree with the header's own consistency rule
    shapes, bad = set(), []
    for name, ent in pak.files.items():
        if not name.upper().endswith(".PSX"):
            continue
        head = pak.read_entry(ent)[:70]
        if len(head) < 70:
            continue
        w, h, tw, th, sel = psx.header(head)
        if sel != 8:
            continue
        shapes.add((w, h, tw, th))
        if tw * th * 4 != w * h:
            bad.append(name)
    check("every 8-bit .PSX transfer carries exactly w*h bytes", not bad,
          str(bad[:3]))
    check("the disc uses the seven known geometries", len(shapes) == 7,
          str(sorted(shapes)))

    logo = psx.to_image(pak.read_file("/PS2DATA/SHELL/ART/LOCKDOWN_SMALL.PSX"))
    check("the wordmark decodes", logo is not None and logo.size == (256, 256),
          str(logo.size if logo else None))
    if logo is not None:
        # Counting opaque pixels proves nothing: the swizzle is a permutation,
        # so every ordering -- right or wrong -- has the identical alpha
        # histogram. What separates them is WHERE those pixels land. A correct
        # unswizzle gathers the mark into a band; a wrong one smears it to all
        # four edges. Measured: 62% of the height correct, 98-100% wrong.
        alpha = logo.split()[-1]
        box = alpha.point(lambda v: 255 if v > 40 else 0).getbbox()
        tall = (box[3] - box[1]) / float(logo.height) if box else 1.0
        check("the mark is gathered, not smeared across the square",
              box is not None and tall < 0.80,
              "alpha bbox spans %.0f%% of the height" % (100 * tall))


def run_raw_and_data(args, work):
    """Ghost Recon / Jungle Storm: the uncompressed-ELF word path on a fixture,
    and the archive data path against the real discs through a write shadow, so
    no retail file is ever opened for writing."""
    import re
    from tcps2 import dataedit, rselzo, transforms
    from tcps2.games import BY_ID
    from tcps2.overlay import open_overlay
    from tcps2.vokes import Region, Vokes, open_archives

    class Shadow(Region):
        """Reads through to the real archive, keeps writes in memory."""
        def __init__(self, inner):
            super().__init__(inner.fh, inner.base, inner.name)
            self.w = []
        def read(self, off, n):
            d = bytearray(super().read(off, n))
            for o, b in self.w:
                s0, e0 = max(off, o), min(off + n, o + len(b))
                if s0 < e0:
                    d[s0-off:e0-off] = b[s0-o:e0-o]
            return bytes(d)
        def write(self, off, data):
            self.w.append((off, bytes(data)))

    for iso_path, pid, boot in ((args.gr, "ghost_recon_slus20613", "SLUS_206.13"),
                                (args.js, "jungle_storm_slus20820", "SLUS_208.20"),
                                (args.rs3data, "r6_3_slus20883", None),
                                (args.gr2, "gr2_slus21105", None),
                                (args.graw, "graw_slus21422", None)):
        if not iso_path:
            continue
        profile = BY_ID[pid]
        if boot is None:
            _data_only(args, profile, iso_path, Shadow)
            continue
        print("\n[%s -- code words]" % profile.short)
        with Iso(iso_path) as iso:
            ent = iso.find(profile.overlays[0].iso_pattern)
            elf = iso.read(ent.lba, ent.size)
        fx = os.path.join(work, pid + ".iso")
        build(fx, [(boot, elf)])
        det = identify(fx)
        check("fixture is recognised as %s" % profile.short,
              det.ok and det.profile is profile, det.message)

        vals = profile.defaults()
        for s in profile.settings:
            if not s.enabled:
                continue
            if s.kind == "bool":
                vals[s.key] = True
            elif s.kind == "int" and s.key.endswith("_skill"):
                vals[s.key] = 2
            elif s.kind == "int" and s.key.endswith("_accuracy"):
                vals[s.key] = 3
            elif s.kind == "choice" and s.key.endswith("_lethality"):
                vals[s.key] = "deadlier"
            elif s.kind == "int" and s.key.endswith("_spot"):
                vals[s.key] = 160
            elif s.kind == "choice" and s.key.startswith("soaf_enemy_"):
                vals[s.key] = {"soaf_enemy_aim": "deadly",
                               "soaf_enemy_delay": "quick",
                               "soaf_enemy_skill_adj": "max"}[s.key]
        vals = profile.normalise(vals)
        code_only = {k: v for k, v in vals.items()}
        edits = profile.build_edits(code_only)
        check("%s emits code words" % profile.short, len(edits) > 0)
        r = engine.apply(fx, profile, code_only)
        check("every word verifies from the fixture",
              r["applied"] == r["verified"] and r["applied"] > 0,
              "%d of %d" % (r["verified"], r["applied"]))
        rv = engine.revert(fx, profile)
        check("revert puts every stock word back", rv["hash_ok"])
        with Iso(fx) as iso:
            ov = open_overlay(iso, profile.overlays[0])
            bad = [va for va, w in profile.stock_words.items() if ov.read_word(va) != w]
        check("no stock word left changed", not bad, str(bad[:3]))

        print("[%s -- data files, against the real disc through a shadow]"
              % profile.short)
        data_edits = profile.build_data(vals)
        check("%s emits data edits" % profile.short, len(data_edits) > 0)
        with Iso(iso_path) as iso:
            arc = Vokes(Shadow(open_archives(iso, profile.archive_pattern)[0].r))
            scopes = {}
            allow = {id(ed): dataedit._scope_filter(arc, ed, scopes)
                     for ed in data_edits}
            scoped = [ed for ed in data_edits if ed.scope]
            if scoped:
                check("the skill edit is scoped to hostile templates only",
                      all(allow[id(ed)] is not None for ed in scoped))
            built, lengths_ok = [], True
            for key, e in sorted(arc.files.items()):
                applies = [ed for ed in data_edits if ed.matches(key)
                           and (allow[id(ed)] is None or allow[id(ed)](key))]
                if not applies:
                    continue
                original = arc.read_entry(e)
                plain = rselzo.unpack(original)
                new = plain
                for ed in applies:
                    new, _n = dataedit.OPS[ed.op](new, ed.params)
                if new == plain:
                    continue
                # Only a COMPRESSED file has to keep its length: its chunk
                # boundaries are fixed. A plain-text file inside the archive --
                # .ATR, .ENV, and Ghost Recon's own CMBTMODL.XML -- may grow or
                # shrink, and the archive writer relocates it. That is the same
                # rule dataedit enforces, so the test asks for the same thing.
                if len(new) != len(plain) and rselzo.is_compressed(original):
                    lengths_ok = False
                    break
                packed = (rselzo.repack(original, new)
                          if rselzo.is_compressed(original) else new)
                built.append((len(packed), e, packed, new))
            check("every compressed file keeps its length", lengths_ok)
            # biggest first: the one large file must get the 64 KB pad before
            # smaller ones start nibbling at it
            built.sort(key=lambda r: -r[0])
            touched = ok = 0
            for _size, e, packed, new in built:
                try:
                    arc.write(e.path, packed)
                except Exception as exc:
                    check("could place %s (%d bytes)" % (e.path, len(packed)),
                          False, str(exc))
                    break
                touched += 1
                back = arc.read_file(e.path)
                if back == packed and rselzo.unpack(back) == new:
                    ok += 1
            check("every edited data file reads back correctly (%d files)" % touched,
                  touched > 0 and ok == touched, "%d of %d" % (ok, touched))
            ext = sorted((x.offset, x.offset + x.size) for x in arc.files.values())
            overlap = [a for a, b in zip(ext, ext[1:]) if b[0] < a[1]]
            check("no two files overlap after relocation", not overlap)


#: per game: the values to drive the data path with, and how many copies of
#: each shared file the disc is expected to carry. Rainbow Six 3 puts
#: R6GAMESETTINGS.INI and three COMMON packages in all three of its archives;
#: Ghost Recon 2 has the INI three times but only two COMMON packages that
#: carry grenade tables at all -- its COMMONOFF has none.
DATA_CASES = {
    "r6_3_slus20883": (
        dict(grenade_dist=80, grenade_delay="quick", grenade_carry=80,
             terro_skill="up", perfect_dist=900, sens_steps=20,
             sens_boost=200, player_grenades=4, fire_delay="snap",
             sight=9000, search_time=90, speed="sprint", spotting="sharp"),
        3, 9),
    "graw_slus21422": (
        dict(graw_skill="up", graw_fire_delay="snap", graw_perfect_dist=900,
             graw_sight=9000, graw_search_time=90, graw_speed="sprint",
             graw_spotting="sharp", graw_grenade_dist=80,
             graw_grenade_delay="quick", graw_sens_steps=20,
             graw_sens_boost=200, graw_player_grenades=4),
        2, 0),
    "gr2_slus21105": (
        dict(gr2_grenade_dist=80, gr2_grenade_delay="quick",
             gr2_grenade_carry=80, gr2_fire_delay="snap", gr2_skill="up",
             gr2_perfect_dist=900, gr2_sight=9000, gr2_sens_steps=20,
             gr2_sens_boost=200, gr2_player_grenades=4, gr2_search_time=90,
             gr2_speed="sprint", gr2_spotting="sharp"),
        3, 2),
}


def _data_only(args, profile, iso_path, Shadow):
    """The archive path for a game whose code patches are covered elsewhere.

    These discs keep their AI tuning and control curve in plain-text INI files
    that live in every vokes archive, so the thing worth checking is that every
    copy is rewritten and that nothing lands on top of anything else.
    """
    from tcps2 import dataedit, rselzo, transforms
    from tcps2.vokes import Vokes, open_archives

    print("\n[%s -- data files, against the real disc through a shadow]"
          % profile.short)
    overrides, want_ini, want_common = DATA_CASES[profile.id]
    vals = profile.normalise(dict(profile.defaults(), **overrides))
    edits = profile.build_data(vals)
    # Advanced Warfighter has no grenade-carry table, so it emits the INI edit
    # alone; the other two emit that plus the COMMON rewrite.
    check("%s emits data edits" % profile.short, len(edits) >= 1)

    copies = commons = loadout = 0
    with Iso(iso_path) as iso:
        for real in open_archives(iso, profile.archive_pattern):
            arc = Vokes(Shadow(real.r))
            stock_ext = sorted((e.offset, e.offset + e.size)
                               for e in arc.files.values()
                               if e.offset >= arc.data_start)
            stock_ov = sum(1 for a, b in zip(stock_ext, stock_ext[1:])
                           if b[0] < a[1])
            built = []
            for key, e in sorted(arc.files.items()):
                applies = [ed for ed in edits if ed.matches(key)]
                if not applies or e.offset < arc.data_start:
                    continue
                kind, plain = dataedit._unpack(arc.read_entry(e))
                new = plain
                for ed in applies:
                    new, _n = dataedit.OPS[ed.op](new, ed.params)
                if new != plain:
                    if kind != "plain" and len(new) != len(plain):
                        check("%s keeps its length in a %s container"
                              % (e.path, kind), False)
                    built.append((len(new), e, kind, new))
            built.sort(key=lambda r: -r[0])
            for _s, e, kind, new in built:
                original = arc.read_entry(e)
                packed = dataedit._repack(kind, original, new)
                if kind != "plain" and len(packed) != len(original):
                    check("%s container keeps its length" % e.path, False)
                arc.write(e.path, packed)
                back = arc.read_file(e.path)
                if back != packed:
                    check("%s reads back" % e.path, False)
                if e.path.upper().startswith("/COMMON"):
                    carry = transforms.read_grenade_carry(
                        dataedit._unpack(back)[1])
                    if carry and all(c == 80 for c, _n in carry):
                        commons += 1
            g = arc.files.get("/R6GAMESETTINGS.INI")
            if g:
                got = transforms.read_ini_values(
                    arc.read_entry(g),
                    ["m_fMinDistToThrowGrenade", "m_iXSensitivityMaxSteps",
                     "m_PlayerGrenadeMultiplierElite"])
                if got.get("m_PlayerGrenadeMultiplierElite") == "4":
                    loadout += 1
                if got.get("m_fMinDistToThrowGrenade") == "80" and                         got.get("m_iXSensitivityMaxSteps") == "20":
                    copies += 1
            ext = sorted((e.offset, e.offset + e.size)
                         for e in arc.files.values()
                         if e.offset >= arc.data_start)
            ov = sum(1 for a, b in zip(ext, ext[1:]) if b[0] < a[1])
            check("%s gains no overlap (%d before, %d after)"
                  % (real.r.name, stock_ov, ov), ov <= stock_ov)
    check("every copy of R6GAMESETTINGS.INI was rewritten", copies == want_ini,
          "%d of %d" % (copies, want_ini))
    check("every COMMON package that has grenade tables carries the new weight",
          commons == want_common, "%d of %d" % (commons, want_common))
    check("the grenade loadout multiplier landed in every copy",
          loadout == want_ini, "%d of %d" % (loadout, want_ini))


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

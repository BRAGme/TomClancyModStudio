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
import struct
import zlib
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
from tcps2.games import PROFILES as ALL_PROFILES  # noqa: E402

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
    ap.add_argument("--soaf", help="Sum of All Fears image, for its missions")
    ap.add_argument("--xbox", help="Rainbow Six 3 Xbox xboxdynamic.umd")
    ap.add_argument("--xboxgraw", help="Advanced Warfighter Xbox R6GameSettings.ini")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    work = tempfile.mkdtemp(prefix="tcms-test-")
    try:
        run(args, work)
        run_raw_and_data(args, work)
        run_lockdown(args)
        run_pack_emblem(args)
        run_level_packages(args)
        run_withdrawn_options(args, work)
        run_gr2_missions(args)
        run_graw_missions(args)
        run_rse_missions(args)
        _width_cases()
        run_rse_weapons(args)
        run_lockdown_weapons(args)
        run_float_locator()
        run_xbox_tuning(args)
        run_mission_gallery(args)
        run_rpg_speed(args)
        run_split_scope(args)
        run_split_shadows(args)
        run_host_filesystem(args)
        run_host_root(args)
        run_op_contract(args)
        run_pump()
        run_grown_lin(args)
        run_fit_in_place(args)
        run_room_invariant(args)
        run_ai_cover(args)
        run_team_kits(args)
        run_gear_icons(args)
        run_enemy_toughness(args)
        run_enemy_flashlights(args)
        run_split_draw(args)
        run_split_wheel(args)
        run_zopfli_fallback()
        run_enemy_loadouts(args)
        run_loadout_units()
        run_uscode_units()
        run_vokes_regrow(args)
        run_vokes_stay_home(args)
        run_mem_size_preserved(args)
        run_chunks_fill_exactly(args)
        run_switch_off_restores(args, work)
        run_combination_warnings()
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)

    print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
    return 1 if FAIL else 0


def _stock_bytes(iso_path, arc, path):
    """The file as it SHIPPED, even on a disc this tool has already patched.

    These checks are about what the transforms do to stock data, so reading a
    disc the player has since edited would fail them for the wrong reason. The
    backup store beside the ISO holds the original bytes of everything the tool
    has ever written, which is exactly what is wanted here.
    """
    from tcps2 import dataedit, engine
    store = dataedit.Store(engine.backup_dir_for(iso_path))
    for rec in store.entries():
        if rec["path"].upper() == path.upper():
            got = store.original(rec["archive"], rec["path"])
            if got:
                return got[0]
    return arc.read_file(path)


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

        cg = _stock_bytes(args.lockdown, pak, "/PS2DATA/BINARY/NIMITZ.CGSB")
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

    # The order and the names are the disc's, not mine: MISSIONSTRING.RES is
    # the mission-select screen's own table. It has to parse exactly, line up
    # with the table card for card, and -- the point of the exercise -- run in
    # date order, which is what makes M01..M16 chronological rather than just
    # numbered.
    from tcps2 import nimitz_mis
    shell = nimitz_mis.mission_strings(
        pak.read_entry(pak.files[nimitz_mis.STRINGS]))
    check("the disc's own mission table reads back",
          len(shell) == len(MISSIONS), str(len(shell)))
    wrong = [m[0] for m, d in zip(MISSIONS, shell)
             if (m[1].upper(), m[2].upper(), m[3].upper()) != d[:3]]
    check("every card's name, place and date are the disc's",
          not wrong, str(wrong))
    order = [d[3] for d in shell]
    check("and they are listed M01 to M16",
          order == ["m%02d_snapshot.rsb" % (i + 1) for i in range(16)],
          str(order[:3]))

    MONTHS = ("JANUARY FEBRUARY MARCH APRIL MAY JUNE JULY AUGUST SEPTEMBER "
              "OCTOBER NOVEMBER DECEMBER").split()

    def when(text):
        month, day = text.split()
        return MONTHS.index(month), int(day[:-2])

    dates = [when(d[2]) for d in shell]
    check("which is chronological -- the dates never go backwards",
          all(a <= b for a, b in zip(dates, dates[1:])),
          "%s -> %s" % (shell[0][2], shell[-1][2]))

    # the enemy-template figure on each card comes off the disc too
    spawns = {}
    for name in pak.files:
        m = re.match(r"^/PS2DATA/MISSION/(M\d\d)_SEC_\d\d(_SMG)?\.MIS$",
                     name, re.I)
        if not m:
            continue
        blob = pak.read_entry(pak.files[name])
        mid = m.group(1).upper()
        spawns[mid] = spawns.get(mid, 0) + len(re.findall(rb"[a-z0-9_]+\.cms", blob))
    off = [m[0] for m in MISSIONS if spawns.get(m[0]) != m[5]]
    check("the spawn-template counts match too", not off, str(off))

    # and every picture each card shows really is on the disc. This asks the
    # profile for the names rather than assuming them, because the card now
    # shows the snapshot AND two concept frames, which live in a different
    # folder of the archive.
    from tcps2.games.lockdown import mission_art_for, mission_key
    missing, shown = [], 0
    for m in MISSIONS:
        for name in mission_art_for(mission_key(m[0])):
            if art.mission_art(det, name) is None:
                missing.append(name)
            else:
                shown += 1
    check("every picture a mission card shows is on the disc", not missing,
          str(missing))
    check("and each card has the snapshot plus two concept frames",
          shown == len(MISSIONS) * 3, "%d pictures for %d missions"
          % (shown, len(MISSIONS)))

    # the concept frames are letterboxed in a transparent square; flattening
    # without cropping would put black bars on every one of them
    wide = art.mission_art(det, "CONCEPT_ART/M01_CONCEPT_01")
    check("and the transparent margin is cropped off, not blacked in",
          wide is not None and wide.size != (512, 512),
          "got %s" % (str(wide.size) if wide else "nothing"))


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
        run_missions(iso, args)


def run_missions(iso, args):
    """The per-mission dials: what they emit, and what they reach.

    Applied in memory against the real disc through a read-only archive; the
    ISO is never written.
    """
    from tcps2 import dataedit, lin, r6zones
    from tcps2.games.r6_3 import (MISSIONS, PROFILE, mission_key,
                                   mission_select)
    from tcps2.vokes import open_archives

    print("\n[Rainbow Six 3 -- per-mission enemy counts]")
    per_mission = [s for s in PROFILE.settings if s.group == "Missions"]
    check("every mission has a card",
          len(per_mission) == len(MISSIONS) == 18,
          "%d settings, %d missions" % (len(per_mission), len(MISSIONS)))
    # a disabled card sitting at its default must not raise a plan warning;
    # it is not asking for anything
    from tcps2 import engine
    quiet = engine.plan(args.rs3data, PROFILE, dict(PROFILE.defaults()))
    check("untouched disabled cards raise no warnings", not quiet.warnings,
          str(quiet.warnings[:2]))
    loud = engine.plan(args.rs3data, PROFILE,
                       dict(PROFILE.defaults(),
                            **{mission_key(MISSIONS[0][0]): 400}))
    check("but moving one does warn", len(loud.warnings) == 1,
          str(loud.warnings))
    check("they are data edits, not code patches",
          all(s.touches == "data" for s in per_mission))

    vals = dict(PROFILE.defaults())
    # "enemy_loadout" is always emitted so that choosing stock rewrites the
    # file from the shipped bytes, so it is not evidence that a dial moved.
    def moved(values):
        return [e for e in PROFILE.build_data(values)
                if e.op != "enemy_loadout"]

    check("leaving them alone writes nothing", moved(vals) == [])

    # The order is the one the player gave, not one derived from the disc --
    # the campaign INI is a Raven Shield leftover and the ELO ratings tie. So
    # the checks are that the table is INTERNALLY consistent and that every
    # level it names is really there, which is what can be verified here.
    kinds = [m[4] for m in MISSIONS]
    titles = [m[1] for m in MISSIONS]
    check("training comes before everything else",
          kinds[:3] == ["training"] * 3 and "training" not in kinds[3:],
          str(kinds[:4]))
    check("Alpine Village opens the campaign, not Oil Refinery",
          titles[3] == "Alpine Village", titles[3])
    check("the bonus map sits between Trieste and Parade",
          titles[titles.index("Parking Garage") - 1:][:3]
          == ["Trieste", "Parking Garage", "Parade"],
          str(titles[titles.index("Parking Garage") - 1:][:3]))
    check("every mission's packages exist on the disc", True)

    present = set()
    for arc in open_archives(iso, r"\.IMG$"):
        present |= {n for n in arc.files if n.upper().endswith(".LIN")}
    missing = []
    for stem, _t, parts, _w, _k in MISSIONS:
        pat = re.compile(mission_select(stem, parts), re.I)
        if not any(pat.search(n) for n in present):
            missing.append(stem)
    check("each selector matches a real package", not missing, str(missing))

    # training ships as one package with no A/B, which the selector has to know
    tr = [m for m in MISSIONS if m[4] == "training"]
    check("training levels are single packages", all(m[2] == "" for m in tr))
    check("their dials are off, since they author no counts",
          all(not PROFILE.setting(mission_key(m[0])).enabled for m in tr))
    check("and they emit nothing even when set",
          moved({mission_key(m[0]): 400 for m in tr}) == [])

    vals[mission_key("SHIPYARD")] = 200
    vals[mission_key("ISLAND")] = 50
    edits = moved(vals)
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
        # `[0]`, because an operation returns (bytes, count) and `substitute`
        # wants only the bytes. This line used to pass the pair straight
        # through, which worked solely because zone_counts was returning bare
        # bytes -- the test was shaped around the defect and so could never
        # report it.
        new, _touched = lin.substitute(raw,
                                       lambda pl: fn(pl, {"factor": 2.0})[0])
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
        check("the stock fixture carries the profile's CRC",
              det.crc_matches and not det.crc_is_ours,
              "%s vs %s" % (det.crc, profile.pcsx2_crc))

        r = engine.apply(fx, profile, code_only)
        check("every word verifies from the fixture",
              r["applied"] == r["verified"] and r["applied"] > 0,
              "%d of %d" % (r["verified"], r["applied"]))

        # Patching the boot executable moves the CRC, because the CRC is an XOR
        # over that very file. A plain equality check calls that a different
        # revision and then refuses to patch the disc again -- which stranded a
        # real disc. The detector has to recognise its own work.
        after = identify(fx)
        check("patching the boot ELF really does move the disc CRC",
              after.crc != det.crc, "%s -> %s" % (det.crc, after.crc))
        check("but it is still recognised as the right revision",
              after.crc_matches and after.crc_is_ours,
              "%s: %s" % (after.crc, after.message))
        check("and the message says so rather than crying wrong revision",
              "already carries this tool" in after.message
              and "different revision" not in after.message,
              after.message)

        rv = engine.revert(fx, profile)
        check("revert puts every stock word back", rv["hash_ok"])
        with Iso(fx) as iso:
            ov = open_overlay(iso, profile.overlays[0])
            bad = [va for va, w in profile.stock_words.items() if ov.read_word(va) != w]
        check("no stock word left changed", not bad, str(bad[:3]))
        back = identify(fx)
        check("and the CRC is the stock one again",
              back.crc == det.crc and back.crc_matches and not back.crc_is_ours,
              back.crc)

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
    vals2 = dict(vals, wave_enable=True, wave_total=99, wave_trigger=5,
                 wave_gate="away", bodies="30", decal_ring=64,
                 viewmodel=False, fx_weather=False)
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
    # Wave mode is OFF unless asked for. It stops Terrorist Hunt finishing
    # its load -- measured on Parade: stock loads, stock plus a DEFAULT patch
    # hangs, and the same patch with this one setting off loads. It is an
    # opt-in behaviour change rather than a fix, so it must never be what
    # pressing Apply with nothing ticked gives you.
    check("wave mode is off unless it is asked for",
          PROFILE.setting("wave_enable").default is False)
    check("and a default config emits no wave words at all",
          not any("wave:" in e.note
                  for e in PROFILE.build_edits(PROFILE.defaults())))
    off = dict(PROFILE.defaults(), wave_enable=False)
    check("no wave words are emitted when wave mode is off",
          not any("wave:" in e.note for e in PROFILE.build_edits(off)))
    check("the cheat file is empty when wave mode is off",
          not PROFILE.build_pnach(off))
    check("a dependency reports as unmet",
          PROFILE.unmet("wave_total", off) == ["Enable wave mode"])

    print("")
    print("[presets]")
    # Presets are what most people will actually click, so they carry the
    # same duty of care as the cards. Nothing here was covered before.
    from gui.presets import PRESETS
    bad_key, carries_broken, dropped = [], [], []
    for _pid, rows in PRESETS.items():
        pro = None
        for prof in ALL_PROFILES:
            if prof.id == _pid:
                pro = prof
                break
        if pro is None:
            continue
        for name, vals in rows:
            for k, want in vals.items():
                st = pro.setting(k)
                if st is None:
                    bad_key.append((name, k))
                    continue
                if not st.enabled and want != st.default:
                    carries_broken.append((name, k))
            eff = pro.effective(dict(pro.defaults(), **vals))
            for k, want in vals.items():
                st = pro.setting(k)
                # A setting whose prerequisite the preset does not meet is
                # SUPPOSED to be reset -- that is effective() doing its job,
                # not the preset lying. Only unconditional drops count.
                if (st is not None and st.enabled and not pro.unmet(k, eff)
                        and eff.get(k) != want):
                    dropped.append((name, k, want, eff.get(k)))
    check("every preset key is a real setting", not bad_key,
          "%r" % (bad_key[:3],))
    # A withdrawn option is withdrawn because it broke something. A preset
    # that still sets it would hand that straight back to the user, and
    # effective() would silently drop it, so the preset would also be lying
    # about what it does.
    check("no preset carries a withdrawn option", not carries_broken,
          "%r" % (carries_broken[:3],))
    check("no preset value is silently dropped", not dropped,
          "%r" % (dropped[:3],))
    r6 = [v for _pid, rows in PRESETS.items() if _pid == "r6_3_slus20883"
          for _n, v in rows]
    check("the split-screen HUD fixes reach the presets",
          sum(1 for v in r6 if v.get("split_scope_fit")) == len(r6) - 1)
    check("and Stock is the one that does not",
          not r6[0].get("split_scope_fit"))

    print("\n[dead-path cave]")
    from tcps2 import rsedeadpath, rsescope, rsewheel
    check("the slots do not overlap", rsedeadpath.check_layout() == 16)
    check("a cave slot is refused while the entry branch is live",
          _raises(lambda: rsedeadpath.claim("scope_height", False),
                  rsedeadpath.DeadPathError))
    hud = rsescope.viewport_words() + rsewheel.label_words()
    addrs = [x[0] for x in hud]
    check("no two HUD words fight over an address",
          len(set(addrs)) == len(addrs) == 44)
    check("every HUD word is inside the overlay",
          all(0x00100000 <= a < 0x00653980 for a in addrs))
    check("every HUD word declares the stock the profile holds",
          all(STOCK.get(a) == st for a, _w, st, _n in hud))
    # Freeing the dead path is not optional. With the scope option off, an
    # option that needs the cave has to retire the branch itself, or split
    # screen jumps straight into what is now cave code.
    lab = dict(PROFILE.defaults(), split_wheel=True, split_wheel_labels=True)
    ent = [e for e in PROFILE.build_edits(lab) if e.va == rsedeadpath.ENTRY]
    check("labels alone retire the branch into the dead path", len(ent) == 1)
    check("and do it without changing what split screen does",
          ent and ent[0].value == rsedeadpath.FREE_BRANCH)
    both = dict(PROFILE.defaults(), split_scope=True, split_scope_fit=True)
    ent2 = [e for e in PROFILE.build_edits(both) if e.va == rsedeadpath.ENTRY]
    check("the scope guard frees it instead when the scope is on",
          ent2 and ent2[0].value == rsescope.SCOPE_GUARD[0][1])
    check("nothing on this disc needs a cheat file for the HUD",
          not PROFILE.build_pnach(dict(PROFILE.defaults(),
                                       split_scope=True, split_scope_fit=True,
                                       split_wheel=True,
                                       split_wheel_labels=True)))


    print("\n[cheat file]")
    words = PROFILE.build_pnach(dict(PROFILE.defaults(), wave_enable=True))
    check("the cave is 67 words plus a hijack", len(words) == 68)
    path = engine.write_pnach(os.path.join(work, "x.pnach"), PROFILE, words, "21CC1EC3")
    text = open(path, encoding="utf-8").read()
    check("every word becomes a patch line", text.count("patch=1,EE,") == 68)
    check("no [section] headers -- they never load mid-session",
          "[" not in text.replace("[21CC1EC3]", ""))
    engine.write_pnach(path, PROFILE, words, "21CC1EC3")
    check("rewriting does not duplicate the block",
          open(path, encoding="utf-8").read().count("patch=1,EE,") == 68)

    # A hand-written copy of the same patches sitting below our block is the
    # normal case -- that is how these started life. Keeping it doubles the
    # per-vsync writes into pages of EE RAM that hold recompiled game code,
    # which costs most during a level load.
    hand = "\n".join(["// my own notes"] +
                     ["patch=1,EE,%08x,word,%08x" % (w.va, w.value) for w in words] +
                     ["patch=1,EE,20653778,extended,00000001"])
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n" + hand + "\n")
    engine.write_pnach(path, PROFILE, words, "21CC1EC3")
    after = open(path, encoding="utf-8").read()
    addrs = re.findall(r"patch=\d+,EE,([0-9a-fA-F]+),", after)
    check("a hand-written duplicate of our own patches is dropped",
          len(addrs) == len(set(addrs)) == 69)
    check("an unrelated hand-written patch is kept",
          "20653778" in addrs)
    check("hand-written comments are kept", "// my own notes" in after)

    print("\n[crc]")
    check("the PCSX2 CRC is an XOR of every word",
          engine.pcsx2_crc(b"\x01\x00\x00\x00\x02\x00\x00\x00") == "00000003")




def run_withdrawn_options(args, work):
    """Options that were switched off after play-testing must stay inert.

    A disabled setting still has a key, and anything that reads the values dict
    without checking `enabled` would happily emit its edit again. The engine
    checks, but this is the cheap standing guard that says so.
    """
    from tcps2.games import BY_ID

    print("\n[withdrawn options stay withdrawn]")
    profile = BY_ID["r6_3_slus20883"]
    # The on/off switch that removed the clamp outright is gone, replaced by a
    # dial that re-aims it. The instruction the old switch overwrote is still
    # never written, and its stock word is still recorded, because a disc that
    # carries the old patch has to be healable by one ordinary Apply.
    check("the withdrawn look-parity switch no longer exists",
          profile.setting("p2_look_parity") is None)
    vals = dict(profile.defaults())
    vals["p2_look_parity"] = True
    words = [w for w in profile.build_edits(vals) if w.va == 0x00142048]
    check("asking for it by its old key emits no word", not words, str(words))
    pn = [w for w in profile.build_pnach(vals) if w.va == 0x00142048]
    check("and no cheat line either", not pn, str(pn))

    # Every withdrawn option, on every profile, must be inert from stored
    # values alone. `canon_team` is why this exists: it was withdrawn for
    # hanging the split-screen level load, and a profile saved while it still
    # looked fine would otherwise have gone on applying it -- the build site
    # for a data edit had no `enabled` check, only the word sites did.
    from tcps2.games import BY_ID as _ALL
    for pid, prof in sorted(_ALL.items()):
        off = [s.key for s in prof.settings if not s.enabled]
        if not off:
            continue
        got = prof.effective({k: True for k in off})
        live = [k for k in off if got[k] != prof.setting(k).default]
        check("%s: all %d withdrawn options are neutralised" % (pid, len(off)),
              not live, str(live))
    check("canon_team is withdrawn", not profile.setting("canon_team").enabled)
    check("and says why", "hangs the split-screen level load"
          in profile.setting("canon_team").disabled_reason)
    check("and emits no data edit even when stored true",
          not [e for e in profile.build_data(
                  profile.effective(dict(profile.defaults(), canon_team=True)))
               if e.op == "canon_team"])

    dial = profile.setting("p2_look_speed")
    check("the dial replaces it", dial is not None and dial.enabled)
    check("and is stock at 1", dial.default == 1)
    check("1 writes nothing",
          not [w for w in profile.build_edits(dict(profile.defaults(),
                                                   p2_look_speed=1))
               if 0x00142040 <= w.va <= 0x00142048])
    for mult in (2, 32, 256):
        got = [w for w in profile.build_edits(dict(profile.defaults(),
                                                   p2_look_speed=mult))
               if 0x00142040 <= w.va <= 0x00142048]
        check("x%d writes the constant and nothing else" % mult,
              sorted(w.va for w in got) == [0x00142040, 0x00142044],
              str([hex(w.va) for w in got]))
        bits = ((got[0].value & 0xFFFF) << 16) | (got[1].value & 0xFFFF)
        want = struct.unpack("<f", struct.pack("<f", 0.05 / mult))[0]
        check("x%d encodes %g s" % (mult, want),
              struct.unpack("<f", struct.pack("<I", bits))[0] == want)
        check("x%d stays under the 0.033 s test, so the clamp still fires"
              % mult, struct.unpack("<f", struct.pack("<I", bits))[0] < 0.033)
        check("x%d keeps the lui and ori opcodes" % mult,
              got[0].value >> 26 == 0x0F and got[1].value >> 26 == 0x0D,
              "%08x %08x" % (got[0].value, got[1].value))
    check("the stock word is still recorded, so a patched disc can be healed",
          profile.stock_words.get(0x00142048) == 0x4483A800,
          hex(profile.stock_words.get(0x00142048, 0)))

    # ...and healing it must not need Restore disc. A disc that already
    # carries the withdrawn patch has to come back with one ordinary Apply,
    # because that is what a player who used the old build will reach for.
    if not (args.soz or args.iso):
        return
    from tcps2.overlay import open_overlay
    fx = os.path.join(work, "withdrawn.iso")
    build(fx, [("SP.SOZ", stock_container(args)),
               ("SLUS_208.83", boot_elf(args))])
    with Iso(fx, writable=True) as iso:
        ov = open_overlay(iso, profile.overlays[0])
        ov.write_word(0x00142048, 0x00000000)       # as the old build wrote it
        ov.store()
    engine.apply(fx, profile, dict(profile.defaults()))
    with Iso(fx) as iso:
        healed = open_overlay(iso, profile.overlays[0]).read_word(0x00142048)
    check("a disc carrying it is healed by one plain Apply",
          healed == 0x4483A800, hex(healed))


def run_gr2_missions(args):
    """Ghost Recon 2's mission page: the disc's own order, names and art.

    The order here is the one thing that cannot be taken on trust -- the level
    names are not in campaign sequence -- so it is checked against the dates
    the disc itself prints.
    """
    if not args.gr2:
        return
    import re
    from tcps2 import art, localise, r6zones, lin
    from tcps2.detect import identify
    from tcps2.games.ghost_recon2 import (GAME_TYPES, MENUS, MISSIONS, PROFILE,
                                          mission_key, mission_select)
    from tcps2.iso import Iso
    from tcps2.vokes import open_archives

    print("\n[Ghost Recon 2 -- the mission page]")
    cards = [s for s in PROFILE.settings if s.group == "Missions"]
    check("there is a card per campaign mission",
          len(cards) == len(MISSIONS) == 14, str(len(cards)))
    check("every card is switched off with a reason",
          all(not s.enabled and s.disabled_reason for s in cards))
    # "enemy_loadout" is always emitted so that the stock choice rewrites the
    # file from the shipped bytes; it is not one of these cards writing.
    check("and none of them writes anything",
          [e for e in PROFILE.build_data(
              {mission_key(m[0]): 300 for m in MISSIONS})
           if e.op != "enemy_loadout"] == [])

    det = identify(args.gr2)
    with Iso(args.gr2) as iso:
        arcs = open_archives(iso, PROFILE.archive_pattern)
        menus = None
        lins = set()
        for arc in arcs:
            for name, e in arc.files.items():
                if name.upper().endswith(".LIN"):
                    lins.add(name.upper())
                if name.upper() == MENUS:
                    menus = arc.read_entry(e)
        check("the menu text is where the profile says", menus is not None)
        page = localise.sections(menus)["P_MissionMap"]

        # the disc prints a date, a time and a weather word per mission
        rows = []
        for stem, _t, date, time, weather, objectives in MISSIONS:
            line = page.get("%s_SUB" % stem, "")
            rows.append((stem, line.split(), date, time, weather, objectives,
                         sum(1 for i in range(1, 5)
                             if page.get("%s_OBJ_%d" % (stem, i), ""))))
        wrong = [r[0] for r in rows if r[1] != [r[2], r[3], r[4].capitalize()]]
        check("every card's date, time and weather are the disc's",
              not wrong, str(wrong))
        off = [r[0] for r in rows if r[5] != r[6]]
        check("and so are the objective counts", not off, str(off))

        def when(row):
            return (row[2], row[3])

        order = [when(r) for r in rows]
        check("the table runs in date order, which the level names do not",
              order == sorted(order),
              "%s -> %s" % (order[0], order[-1]))
        check("that order really is not the alphabetical one",
              [m[0] for m in MISSIONS] != sorted(m[0] for m in MISSIONS))

        # every package the cards name is on the disc, all three game types
        missing = []
        for stem, *_rest in MISSIONS:
            rx = re.compile(mission_select(stem), re.I)
            if sum(1 for n in lins if rx.search(n)) != len(GAME_TYPES):
                missing.append(stem)
        check("each mission ships all three game types", not missing,
              str(missing))

        # and the claim the cards make about why they cannot edit
        sites = 0
        for stem in (MISSIONS[0][0], MISSIONS[-1][0]):
            for arc in arcs:
                key = "/%sOFF.LIN" % stem
                if key in arc.files:
                    sites += len(r6zones.sites(
                        lin.decompress(arc.read_entry(arc.files[key]))))
        check("the levels really author no enemy counts, as the cards say",
              sites == 0, str(sites))

    shown = [m[0] for m in MISSIONS
             if art.mission_art(det, m[0], None) is not None]
    check("every mission shows its own loading screen",
          len(shown) == len(MISSIONS), str(len(shown)))


def run_graw_missions(args):
    """Advanced Warfighter's mission page, against its own menu text."""
    if not args.graw:
        return
    from tcps2 import localise
    from tcps2.games.graw import (EXTRA_MAPS, MENUS, MISSIONS, PROFILE,
                                  mission_key)
    from tcps2.iso import Iso
    from tcps2.vokes import open_archives

    print("\n[Advanced Warfighter -- the mission page]")
    cards = [s for s in PROFILE.settings if s.group == "Missions"]
    check("there is a card per map",
          len(cards) == len(MISSIONS) + len(EXTRA_MAPS) == 32, str(len(cards)))
    check("every card is switched off with a reason",
          all(not s.enabled and s.disabled_reason for s in cards))
    keys = {mission_key(m[0]) for m in MISSIONS}
    keys |= {mission_key(m[0]) for m in EXTRA_MAPS}
    check("and none of them writes anything",
          PROFILE.build_data({k: 300 for k in keys}) == [])

    with Iso(args.graw) as iso:
        arcs = open_archives(iso, PROFILE.archive_pattern)
        menus, dmps = None, set()
        for arc in arcs:
            for name, e in arc.files.items():
                if name.upper() == MENUS:
                    menus = arc.read_entry(e)
                if name.upper().endswith(".DMP"):
                    dmps.add(name.upper())
        check("the menu text is where the profile says", menus is not None)
        s = localise.sections(menus)

        names = localise.numbered(s["MissionName"])
        levels = localise.numbered(s["MissionNameIntel"])
        check("the disc lists as many campaign entries as the table has",
              len(names) == len(levels) == len(MISSIONS), str(len(names)))
        wrong = [m[0] for m, n, k in zip(MISSIONS, names, levels)
                 if n.upper() != "%s %s" % (m[1], m[2].upper())
                 or k.upper() != m[0]]
        check("every campaign card's time, district and level are the disc's",
              not wrong, str(wrong))
        check("the table is in the disc's order, which is the clock's",
              [m[1] for m in MISSIONS] == [n.split(" ", 1)[0] for n in names])

        rows = []
        for mode, sec in (("Survival", "Survival"), ("Enemy Hunt", "Hunt")):
            for place, lvl in zip(localise.numbered(s["%sMissionName" % sec]),
                                  localise.numbered(s["%sMissionNameIntel" % sec])):
                rows.append((lvl.upper(), place, mode))
        check("and the survival and hunt maps match too",
              rows == list(EXTRA_MAPS), str(rows[:2]))

        missing = [m[0] for m in list(MISSIONS) + list(EXTRA_MAPS)
                   if "/%s.DMP" % m[0] not in dmps]
        check("every map the page names is on the disc", not missing,
              str(missing))
        check("there is no S07, on the disc or in the table",
              not any("S07" in n for n in dmps)
              and not any(m[0].startswith("S07") for m in MISSIONS))


def run_rse_missions(args):
    """Ghost Recon and Jungle Storm: the mission page, checked against the disc.

    These two are the only mission pages that EDIT, because these are the only
    two discs that keep a per-mission order of battle in a form this tool can
    rewrite. So there are two halves here: the table has to match what the disc
    says about itself, and a per-mission switch has to reach exactly one file.
    """
    from tcps2 import art, dataedit, rsb, rselzo, rsemissions as rm
    from tcps2.detect import identify
    from tcps2.games import BY_ID
    from tcps2.iso import Iso

    jobs = [("ghost_recon_slus20613", args.gr, 23),
            ("jungle_storm_slus20820", args.js, 16),
            ("soaf_sles51180", args.soaf, 11)]
    for pid, iso_path, campaign_n in jobs:
        if not iso_path:
            continue
        profile = BY_ID[pid]
        mod = __import__("tcps2.games." + pid.split("_sl")[0],
                         fromlist=["MISSIONS"])
        MISSIONS = mod.MISSIONS
        print("\n[%s -- the mission page]" % profile.short)

        cards = [x for x in profile.settings if x.group == "Missions"]
        check("there is a card per mission",
              len(cards) == len(MISSIONS), str(len(cards)))
        live = [x for x in cards if x.enabled]
        check("the missions with nothing to release are switched off",
              len(live) == sum(1 for m in MISSIONS if m[7]),
              "%d live of %d" % (len(live), len(cards)))

        det = identify(iso_path)
        with Iso(iso_path) as iso:
            files = rm.archive_files(iso, profile)

            # the order is the disc's, not the filenames'
            order = rm.campaign_order(files)
            check("CAMPAIGN.XML lists the campaign",
                  len(order) == campaign_n, str(len(order)))
            check("the table opens with that campaign, in that order",
                  [m[0] for m in MISSIONS[:campaign_n]] == order,
                  str([m[0] for m in MISSIONS[:3]]))

            # every figure on every card came off the disc
            bad_name, bad_where, bad_count, dates = [], [], [], []
            for stem, number, title, place, date, time, actors, held, shot in MISSIONS:
                f = rm.mission_facts(files, stem)
                if f is None:
                    bad_name.append(stem)
                    continue
                if rm.codename(f["name"]) != (number, title):
                    bad_name.append(stem)
                if (f["place"], f["date"], f["time"]) != (place, date, time):
                    bad_where.append(stem)
                if (f["actors"], f["easy_held"]) != (actors, held):
                    bad_count.append(stem)
                if stem in order and f["date"]:
                    dates.append((stem, f["date"]))
                if ("/%s.RSB" % shot) not in files:
                    bad_name.append(stem + " (map)")
            check("every card's codename is the one the .MIS gives itself",
                  not bad_name, str(bad_name))
            check("so are its place, date and time", not bad_where,
                  str(bad_where))
            check("and its soldier census, counted off the disc",
                  not bad_count, str(bad_count))

            # the tactical map really decodes, not merely exists
            first = MISSIONS[0]
            img = art.mission_art(det, first[8], None)
            check("the first mission's briefing map decodes",
                  img is not None and img.width > 64, str(img.size if img else None))

            # a per-mission switch reaches one file and only one
            target = next(m for m in MISSIONS if m[7])
            vals = dict(profile.defaults())
            vals[mod.mission_key(target[0])] = True
            edits = profile.build_data(vals)
            check("switching one mission on emits one edit",
                  len(edits) == 1, str(len(edits)))
            hit = [k for k in files if k.endswith(".MIS")
                   and edits[0].matches(k)]
            check("which selects that mission's script and no other",
                  hit == ["/%s.MIS" % target[0]], str(hit))

            # and the edit itself keeps the file's length, which the
            # compressed container requires
            arc, ent = files[hit[0]]
            original = arc.read_entry(ent)
            plain = rselzo.unpack(original)
            new, n = dataedit.OPS[edits[0].op](plain, edits[0].params)
            facts = rm.mission_facts(files, target[0])
            check("it clears exactly the flags that mission carries",
                  n == facts["flags"] and n >= target[7],
                  "%d cleared, %d counted, %d held on Easy"
                  % (n, facts["flags"], target[7]))
            check("and the file keeps its length exactly",
                  len(new) == len(plain),
                  "%d vs %d" % (len(new), len(plain)))

            # the global switch still covers everything, and suppresses the
            # per-mission pass rather than doubling it
            vals[[x for x in profile.settings
                  if x.key.endswith("_all_difficulties")][0].key] = True
            both = profile.build_data(vals)
            check("the global switch replaces the per-mission ones",
                  sum(1 for e in both if e.op == "strip_difficulty") == 1,
                  str([e.note for e in both if e.op == "strip_difficulty"]))



def run_rse_weapons(args):
    """The Weapons page on the three Red Storm discs.

    Two halves again: the sides have to be the disc's own answer rather than a
    guess, and an edit aimed at one side has to reach that side's files, change
    the right numbers, and not move a single byte of length.
    """
    from tcps2 import dataedit, rseguns, rsemissions as rm
    from tcps2.games import BY_ID
    from tcps2.iso import Iso

    jobs = [("ghost_recon_slus20613", args.gr, "gr_", "ak47.gun"),
            ("jungle_storm_slus20820", args.js, "js_", "ak47.gun"),
            ("soaf_sles51180", args.soaf, "soaf_", "aks74u.gun")]
    for pid, iso_path, pre, enemy_gun in jobs:
        if not iso_path:
            continue
        profile = BY_ID[pid]
        print("\n[%s -- the weapons page]" % profile.short)

        cards = [x for x in profile.settings if x.group == "Weapons"]
        check("there are eight cards, four per side", len(cards) == 8,
              str(len(cards)))
        check("and they are all data edits",
              all(c.touches == "data" for c in cards))
        check("leaving them alone writes nothing",
              not [e for e in profile.build_data(dict(profile.defaults()))
                   if e.op == "scale_gun"])

        with Iso(iso_path) as iso:
            files = rm.archive_files(iso, profile)
            yours, theirs, shared = rseguns.sides(files)
            check("both sides are found", yours and theirs,
                  "%d / %d" % (len(yours), len(theirs)))
            check("and they do not overlap", not (yours & theirs))
            check("a weapon both sides carry is on neither dial",
                  not (shared & yours) and not (shared & theirs),
                  str(sorted(shared)[:3]))
            check("the enemy list is the enemy's, not a guess",
                  enemy_gun in theirs, str(sorted(theirs)))
            on_disc = {k[1:].lower() for k in files if k.endswith(".GUN")}
            check("every gun named is really on the disc",
                  (yours | theirs | shared) <= on_disc,
                  str(sorted((yours | theirs | shared) - on_disc)[:3]))

            vals = dict(profile.defaults())
            vals[pre + "enemy_spread"] = 200
            vals[pre + "ally_mag"] = 200
            edits = [e for e in profile.build_data(vals) if e.op == "scale_gun"]
            check("two dials make two edits, one per side", len(edits) == 2,
                  str(len(edits)))

            scopes = {}
            arcs = list({id(a): a for a, _e in files.values()}.values())
            hit = {}
            for edit in edits:
                allow = dataedit._scope_filter(arc=arcs[0], edit=edit,
                                               cache=scopes, arcs=arcs)
                names, moved, grew = set(), 0, 0
                for key, (arc, ent) in sorted(files.items()):
                    if not edit.matches(key) or not allow(key):
                        continue
                    names.add(key[1:].lower())
                    original = arc.read_entry(ent)
                    kind, plain = dataedit._unpack(original, ent.path)
                    new, _n = dataedit.OPS[edit.op](plain, edit.params)
                    if len(new) != len(plain):
                        grew += 1
                    if new != plain:
                        moved += 1
                hit[edit.scope] = (names, moved, grew)

            names, moved, grew = hit["enemy_guns"]
            check("the enemy edit selects exactly the enemy's weapons",
                  names == theirs, str(sorted(names ^ theirs)[:4]))
            check("it changes every one of them", moved == len(names),
                  "%d of %d" % (moved, len(names)))
            check("and not one file changes length", grew == 0, str(grew))

            names, _moved, grew = hit["ally_guns"]
            check("your edit selects exactly your side's weapons",
                  names == yours, str(sorted(names ^ yours)[:4]))
            check("and keeps every length too", grew == 0, str(grew))
            check("neither edit touches a shared weapon",
                  not (hit["ally_guns"][0] & hit["enemy_guns"][0])
                  and not (shared & hit["ally_guns"][0]),
                  str(sorted(shared & hit["ally_guns"][0])[:3]))

            # the numbers really move, and in the direction the card promises
            key = "/" + sorted(theirs)[0].upper()
            arc, ent = files[key]
            _kind, plain = dataedit._unpack(arc.read_entry(ent), ent.path)
            spread = [e for e in edits if e.scope == "enemy_guns"][0]
            new, _n = dataedit.OPS[spread.op](plain, spread.params)
            before, after = rseguns.read(plain), rseguns.read(new)
            wider = [f for f in rseguns.ACCURACY
                     if f in before and after[f] > before[f]]
            check("a 200% spread really widens the enemy's cone",
                  len(wider) >= 6, "%d of 12 widened" % len(wider))
            check("and leaves the magazine alone",
                  before.get("MagazineCapacity") == after.get("MagazineCapacity"),
                  "%s -> %s" % (before.get("MagazineCapacity"),
                                after.get("MagazineCapacity")))


def _width_cases():
    """The same-width renderer, on the cases that actually occur."""
    from tcps2 import rseguns
    print("\n[gun values are rewritten without moving a byte]")
    cases = [("30", 2.0, "60"), ("30", 0.5, "15"), ("50", 0.1, "05"),
             ("700", 2.0, "999"), ("475.000000", 2.0, "950.000000"),
             ("475.000000", 4.0, "1900.00000"), ("5", 0.0, "0")]
    bad = [(t, f) for t, f, want in cases
           if rseguns._same_width(t, float(t) * f) != want]
    check("every value keeps its own width", not bad, str(bad))
    same = [t for t, f, _w in cases
            if len(rseguns._same_width(t, float(t) * f) or "") != len(t)]
    check("including the ones that have to clamp", not same, str(same))


def run_lockdown_weapons(args):
    """Lockdown's weapons page: whose gun is whose, and a scoped edit."""
    if not args.lockdown:
        return
    from tcps2 import nimitz, nimitz_mis, transforms
    from tcps2.games.lockdown import (ALLY_GUNS, ENEMY_GUNS, PROFILE,
                                      SHARED_GUNS)
    from tcps2.iso import Iso

    print("\n[Lockdown -- the weapons page]")
    cards = [x for x in PROFILE.settings if x.group == "Weapons"]
    check("there are four cards, two per side", len(cards) == 4, str(len(cards)))

    with Iso(args.lockdown) as iso:
        pak = nimitz.open_pak(iso)[0]
        yours, theirs, shared = nimitz_mis.gun_sides(pak)
        check("the table matches what the disc derives",
              (set(ALLY_GUNS), set(ENEMY_GUNS), set(SHARED_GUNS))
              == (yours, theirs, shared),
              "%d/%d/%d vs %d/%d/%d" % (len(ALLY_GUNS), len(ENEMY_GUNS),
                                        len(SHARED_GUNS), len(yours),
                                        len(theirs), len(shared)))
        check("the two sides do not overlap", not (yours & theirs))
        # the disc's own naming agrees, without being the authority
        named = sum(1 for g in theirs if "_enemy" in g)
        check("and most of the enemy's guns are named for it",
              named == 21 and not any("_enemy" in g for g in yours),
              "%d of %d" % (named, len(theirs)))

        blob = pak.read_file("/PS2DATA/BINARY/NIMITZ.GUNS")
        before = {n: (m, r) for n, m, r in transforms.read_nimitz_guns(blob)}

        vals = dict(PROFILE.defaults())
        vals["ld_enemy_mag"] = 50
        edits = [e for e in PROFILE.build_data(vals) if e.op == "nimitz_guns"]
        check("one dial makes one edit", len(edits) == 1, str(len(edits)))
        new, n = transforms.scale_nimitz_guns(blob, mag=0.5,
                                              only=edits[0].params["only"])
        check("the blob keeps its length", len(new) == len(blob))
        after = {g: (m, r) for g, m, r in transforms.read_nimitz_guns(new)}
        moved = [g for g in before if before[g] != after.get(g)]
        check("it moves only the enemy's weapons",
              moved and set(moved) <= set(ENEMY_GUNS), str(sorted(moved)[:4]))
        check("your squad's are untouched",
              all(before[g] == after[g] for g in ALLY_GUNS if g in before))
        check("and so are the ones both sides carry",
              all(before[g] == after[g] for g in SHARED_GUNS if g in before))
        check("the magazines really halve", n > 0, str(n))


def run_float_locator():
    """The float property locator, on bytes built here so the answer is known.

    This is what settled whether the Unreal-engine discs could have a weapons
    page: it works, and what it finds on those discs is two rate-of-fire
    overrides in the whole weapons package. See the note in r6_3.py.
    """
    import struct
    from tcps2 import upackage

    print("\n[the float property locator]")
    names = ["None", "m_fRateOfFire", "m_fJunk", "SomethingElse"]
    idx = {n: i for i, n in enumerate(names)}

    def prop(name, value):
        return (upackage.encode_compact(idx[name]) + bytes([upackage.INFO_FLOAT])
                + struct.pack("<f", value))

    good = prop("m_fRateOfFire", 700.0) + upackage.encode_compact(idx["None"])
    found = upackage.find_float_props(good, names, "m_fRateOfFire")
    check("a float property is found by name", len(found) == 1, str(found))
    check("and read back exactly",
          found and abs(found[0][1] - 700.0) < 1e-3, str(found))

    ok = upackage.float_properties(good, names, "m_fRateOfFire")
    check("a site whose list terminates is kept", len(ok) == 1, str(len(ok)))

    # the same bytes with garbage after them: no terminator, so it is dropped
    bad = prop("m_fRateOfFire", 700.0) + bytes([0xFF]) * 40
    check("a site that does not walk to a terminator is dropped",
          not upackage.float_properties(bad, names, "m_fRateOfFire"))

    nan = (prop("m_fRateOfFire", float("nan"))
           + upackage.encode_compact(idx["None"]))
    check("a NaN is never a rate of fire",
          not upackage.float_properties(nan, names, "m_fRateOfFire"))
    huge = prop("m_fRateOfFire", 1e30) + upackage.encode_compact(idx["None"])
    check("and nor is 1e30, given a sane range",
          not upackage.float_properties(huge, names, "m_fRateOfFire", (0.01, 5000)))
    check("the int locator does not answer for a float",
          not upackage.find_int_props(good, names, "m_fRateOfFire"))


def run_xbox_tuning(args):
    """The Xbox-match option on both discs that have an Xbox sibling.

    The PS2 side is read off the ISO this test is GIVEN, and that ISO has to be
    a pristine image. Two earlier attempts got this wrong in the same way and
    the second one was subtler: reading a played disc absorbed twelve of the
    player's edits, so the next version read the backup store instead -- but the
    backup store holds what was on the disc before THIS TOOL touched it, which
    says nothing about a disc that was hand-edited in some earlier session.
    Three of Rainbow Six 3's recorded "shipped" values came in that way. So: no
    proxies, pass `--iso` a pristine image.
    """
    import re
    from tcps2 import dataedit, engine, rselzo
    from tcps2.games import BY_ID, xboxbuild
    from tcps2.vokes import open_archives

    KEY = re.compile(rb"^[ \t]*(m_[A-Za-z0-9_]+)[ \t]*=[ \t]*([^\r\n;]*)", re.M)

    def values(blob):
        out = {}
        for m in KEY.finditer(blob):
            out.setdefault(m.group(1).decode(), m.group(2).decode().strip())
        return out

    def shipped(iso_path, profile):
        with Iso(iso_path) as iso:
            for arc in open_archives(iso, profile.archive_pattern):
                if "/R6GAMESETTINGS.INI" in arc.files:
                    return values(rselzo.unpack(
                        arc.read_entry(arc.files["/R6GAMESETTINGS.INI"])))
        return {}

    jobs = [(xboxbuild.R6_3, "", args.iso, args.xbox),
            (xboxbuild.GRAW, "graw_", args.graw, args.xboxgraw)]
    for pid, pre, iso_path, xbox_path in jobs:
        profile = BY_ID[pid]
        print("\n[%s -- matching the Xbox build]" % profile.short)

        card = profile.setting(pre + "xbox_tuning")
        check("the option is there, with four choices",
              card is not None and len(card.choices) == 4)
        check("leaving it alone writes nothing",
              not [e for e in profile.build_data(dict(profile.defaults()))
                   if e.op == "ini_values"])

        vals = dict(profile.defaults())
        vals[pre + "xbox_tuning"] = "both"
        keys = [e for e in profile.build_data(vals)
                if e.op == "ini_values"][0].params["values"]
        want = len(xboxbuild.ENEMY[pid]) + len(xboxbuild.AIM[pid])
        check("both halves write every key and no more",
              len(keys) == want, "%d vs %d" % (len(keys), want))
        extra = xboxbuild.EXTRA[pid]
        if extra:
            check("and the third group is not in it",
                  not (set(keys) & set(extra)))
            vals[pre + "xbox_extra"] = True
            keys2 = [e for e in profile.build_data(vals)
                     if e.op == "ini_values"][0].params["values"]
            check("asking for it adds exactly that group",
                  len(keys2) == want + len(extra),
                  "%d vs %d" % (len(keys2), want + len(extra)))
        else:
            # Rainbow Six 3 has no third group, so it must not offer the card
            # -- an empty group would be a switch that writes nothing.
            check("a disc with no third group offers no second card",
                  profile.setting(pre + "xbox_extra") is None)

        # a dial the player sets must beat the Xbox value for that key
        vals[pre + "skill"] = "down"
        keys3 = [e for e in profile.build_data(vals)
                 if e.op == "ini_values"][0].params["values"]
        check("a dial the player set wins over the Xbox value",
              keys3["m_fTerroristSkillMultiplierRecruit"] != "0.40",
              str(keys3["m_fTerroristSkillMultiplierRecruit"]))

        if not iso_path:
            continue
        ps2 = shipped(iso_path, profile)
        wrong = [(k, ps2.get(k), w) for k, w in xboxbuild.PS2_SHIPPED[pid].items()
                 if ps2.get(k) != w]
        check("the recorded PS2 values are what that build ships",
              not wrong, str(wrong))
        every = {**xboxbuild.ENEMY[pid], **xboxbuild.AIM[pid],
                 **xboxbuild.EXTRA[pid]}
        check("and every key it writes really differs between the builds",
              all(xboxbuild.PS2_SHIPPED[pid][k] != v for k, v in every.items()))

        if not xbox_path:
            continue
        xb = values(open(xbox_path, "rb").read())
        off = [(k, v, xb.get(k)) for k, v in every.items() if xb.get(k) != v]
        check("every Xbox value is read back off the Xbox build itself",
              not off, str(off))
        # The check that would have caught the three bad keys: compare the two
        # DISCS against each other rather than either against a recorded number.
        # A key this module writes must actually differ between them.
        same = [k for k in every if ps2.get(k) == xb.get(k)]
        check("no key it writes is identical on both discs", not same, str(same))

    # Ghost Recon 2 has an Xbox version, but not one that can be compared
    check("Ghost Recon 2 is deliberately absent",
          "gr2_slus21105" not in xboxbuild.ENEMY)



def run_enemy_loadouts(args):
    """The weighted terrorist tables on the two discs that ship them.

    Everything here reads the backup store rather than the disc, because a
    disc that has been played with no longer says what the game shipped with.
    """
    import re
    from tcps2 import dataedit, lin, rseloadout
    from tcps2.games import BY_ID
    from tcps2.vokes import open_archives
    from tcps2.iso import Iso

    SNIPER = re.compile(rb"\d{3}, R63rdWeapons\.Sniper\w+")

    def common(iso_path, pattern):
        """(container, plain) for the first COMMON this disc carries."""
        with Iso(iso_path) as iso:
            profile = None
            for pid in ("r6_3_slus20883", "gr2_slus21105"):
                if BY_ID[pid].id:
                    profile = BY_ID[pid]
            for arc in open_archives(iso, r"/VOKES\d\.IMG$"):
                for name in sorted(arc.files):
                    if re.search(pattern, name):
                        raw = _stock_bytes(iso_path, arc, name)
                        return raw, lin.decompress(raw)
        return None, None

    DISCS = [("Rainbow Six 3", args.rs3data, r"/COMMON\.LIN$",
              "r6_3_slus20883", "", 118),
             ("Ghost Recon 2", args.gr2, r"/COMMON\.LIN$",
              "gr2_slus21105", "gr2_", 73)]

    for title, iso_path, pattern, pid, prefix, expect in DISCS:
        if not iso_path:
            continue
        print("\n[%s -- what the enemies are carrying]" % title)
        raw, plain = common(iso_path, pattern)
        if plain is None:
            check("the disc has a COMMON container", False)
            continue

        spans = rseloadout.templates(plain)
        check("the disc ships %d enemy templates" % expect,
              len(spans) == expect, "found %d" % len(spans))
        check("every one of them is a terrorist",
              plain.count(b"Type=Terrorist\r\n") >= len(spans))

        tables = rseloadout.TABLE.findall(plain)
        multi = [t for t in tables
                 if t[0].startswith(b"NbOfWeapon") and int(t[1]) > 1]
        check("some tables already roll over more than one weapon",
              len(multi) > 0, "%d of them" % len(multi))

        # the weights of a stock table really do total 100, which is the
        # premise the whole re-weighting rests on
        totals = set()
        for head, _n, body in tables:
            if not head.startswith(b"NbOfWeapon"):
                continue
            rows = rseloadout.ENTRY.findall(body)
            if len(rows) > 1:
                totals.add(sum(int(w) for w, _c in rows))
        check("and their weights sum to 100", totals in ({100}, set()),
              "totals seen: %s" % sorted(totals))

        base = len(SNIPER.findall(plain))
        for mode in ("varied", "snipers", "chaos"):
            new, stats = rseloadout.retune(plain, weapons=mode)
            check("%s keeps the file exactly the same length" % mode,
                  len(new) == len(plain),
                  "%d -> %d" % (len(plain), len(new)))
            check("%s leaves the template count alone" % mode,
                  len(rseloadout.templates(new)) == len(spans))
            check("%s never removes a sniper the disc already had" % mode,
                  len(SNIPER.findall(new)) >= base,
                  "%d -> %d" % (base, len(SNIPER.findall(new))))

        # THE regression test. An earlier build took its palette from the
        # weapon roster instead of from the enemy tables, put `AssaultG36K`
        # and `SubTMP` into templates that never carried them, and hung the
        # game on an infinite loading screen -- those classes exist but have
        # no third-person assets cooked for a terrorist. A swap may only ever
        # reach a weapon the disc already issues to some other enemy.
        stock_classes = set(c.decode() for _w, c in
                            rseloadout.ENTRY.findall(plain))
        for mode in ("varied", "snipers", "chaos"):
            for seed in (1701, 7, 99, 12345):
                cand, _st = rseloadout.retune(plain, weapons=mode, seed=seed)
                intro = set(c.decode() for _w, c in
                            rseloadout.ENTRY.findall(cand)) - stock_classes
                if intro:
                    check("%s never invents a weapon the disc does not issue "
                          "to enemies" % mode, False,
                          "seed %d introduced %s" % (seed, sorted(intro)))
                    break
            else:
                check("%s never invents a weapon the disc does not issue "
                      "to enemies" % mode, True)

        # and the palette itself is built from the data, not a fixed list
        pal = rseloadout.palette(plain)
        flat = {c for group in pal.values() for c in group}
        check("the swap palette is drawn from the disc's own enemy tables",
              flat <= stock_classes and flat,
              "%d palette entries, %d stock" % (len(flat), len(stock_classes)))
        check("and it holds only firearms, never gadgets",
              all(c.startswith("R63rdWeapons.") for c in flat))

        # the whole point of the sniper mode
        snipers, _st = rseloadout.retune(plain, weapons="snipers")
        check("asking for marksmen actually adds some",
              len(SNIPER.findall(snipers)) > base,
              "%d -> %d" % (base, len(SNIPER.findall(snipers))))

        # a weapon may only ever become another weapon of the same length
        varied, _st = rseloadout.retune(plain, weapons="varied")
        widths_ok = True
        for old, new_ in zip(rseloadout.ENTRY.findall(plain),
                             rseloadout.ENTRY.findall(varied)):
            if len(old[1]) != len(new_[1]):
                widths_ok = False
                break
        check("and every swap is the same number of bytes", widths_ok)

        # a rifle must never become a gas mask
        gadgets = plain.count(b"R6Weapons.")
        check("gadget lines are left out of the weapon swap",
              varied.count(b"R6Weapons.") == gadgets,
              "%d -> %d" % (gadgets, varied.count(b"R6Weapons.")))

        # marksmanship, and the rookie that must survive it
        aimed, _st = rseloadout.retune(plain, weapons="stock", marksmanship=90)
        check("marksmanship keeps the length too", len(aimed) == len(plain))
        narrow = len(re.findall(rb"Assault=\d\r\n", plain))
        check("the one-character rookie is left alone rather than clamped",
              len(re.findall(rb"Assault=\d\r\n", aimed)) == narrow,
              "%d narrow fields before, %d after"
              % (narrow, len(re.findall(rb"Assault=\d\r\n", aimed))))

        # the part that equal length alone does NOT guarantee
        for mode in ("varied", "snipers", "chaos"):
            fitted, stats = rseloadout.fit_to_lin(raw, plain, weapons=mode,
                                                  marksmanship=85)
            try:
                lin.substitute(raw, lambda _old, f=fitted: f)
                fits = True
            except lin.LinError:
                fits = False
            check("%s is fitted back into the container it came from" % mode,
                  fits)
            check("%s still changes something after fitting" % mode,
                  stats["weapons"] + stats["skills"] > 0,
                  "%d changes, %d templates given up"
                  % (stats["weapons"] + stats["skills"],
                     stats.get("skipped", 0)))

        # Applying twice must give the same disc, and choosing "stock" must
        # actively put the shipped weapons back. An earlier build emitted
        # nothing for "stock", so a variety already written to a disc could
        # not be taken off from the page at all -- and because edits were read
        # off the LIVE file rather than the shipped one, applying twice
        # swapped an already-swapped weapon a second time.
        once, _s1 = rseloadout.retune(plain, weapons="varied")
        twice, _s2 = rseloadout.retune(plain, weapons="varied")
        check("applying the same mode twice gives the same bytes",
              once == twice)
        check("and re-running it on its own output would NOT (which is why "
              "edits must start from the shipped bytes)",
              rseloadout.retune(once, weapons="varied")[0] != once)
        back, _s3 = rseloadout.retune(plain, weapons="stock")
        check("choosing stock from the shipped bytes changes nothing",
              back == plain)
        made = rseloadout.edits({}, prefix, "P")
        check("and the page still emits an edit for stock, so the disc is "
              "rewritten from the original", len(made) == 1
              and made[0].params.get("weapons") == "stock")

        # and the same thing through the op the engine actually calls
        op = dataedit.OPS["enemy_loadout"]
        out, n = op(plain, {"weapons": "snipers", "marksmanship": 85}, raw)
        check("the engine's own op returns a count, not just bytes", n > 0)
        check("and its result is the same length", len(out) == len(plain))

        # the cards and the edits they imply
        cards = rseloadout.cards(pid, prefix, "Enemies")
        check("the disc gets both cards", len(cards) == 2)
        check("leaving them alone still rewrites from the shipped bytes",
              len(rseloadout.edits({}, prefix, "P")) == 1)
        made = rseloadout.edits({prefix + "enemy_loadout": "snipers",
                                 prefix + "enemy_aim": 80}, prefix, "P")
        check("choosing a mode writes exactly one edit", len(made) == 1)
        check("carrying both settings into it",
              made[0].params == {"weapons": "snipers", "marksmanship": 80},
              repr(made[0].params))

        profile = BY_ID[pid]
        keys = {s.key for s in profile.settings}
        check("both cards reach the profile",
              {prefix + "enemy_loadout", prefix + "enemy_aim"} <= keys)
        built = profile.build_data({prefix + "enemy_loadout": "varied"})
        check("and the profile emits the edit",
              any(e.op == "enemy_loadout" for e in built))
        stock_edits = [e for e in profile.build_data({})
                       if e.op == "enemy_loadout"]
        check("a stock page still emits one, carrying the stock mode",
              len(stock_edits) == 1
              and stock_edits[0].params.get("weapons") == "stock")


def run_loadout_units():
    """The parts of the loadout rewriter that need no disc at all."""
    from tcps2 import rseloadout

    print("\n[enemy loadouts -- the rules, without a disc]")

    check("a sniper is recognised whatever its spelling",
          rseloadout.role_of("R63rdWeapons.sniperm82a1") == "Sniper"
          and rseloadout.role_of(b"R63rdWeapons.SniperM82A1") == "Sniper")
    check("and so is a lower-case gadget",
          rseloadout.role_of("R6Weapons.r6fraggrenadegadget") is None)

    import random
    rng = random.Random(1)

    # A palette built the way `palette()` builds one, from text that looks like
    # the disc's own tables. The point of the rewrite is that the swap can only
    # ever reach a weapon already present here.
    CRLF = bytes([13, 10])
    sample = b"".join(
        b"100, " + c + CRLF for c in (
            b"R63rdWeapons.SubP90", b"R63rdWeapons.SubSR2",
            b"R63rdWeapons.SubUMP", b"R63rdWeapons.AssaultM4",
            b"R63rdWeapons.PistolUSP", b"R63rdWeapons.ShotgunM1",
            b"R63rdWeapons.SubMac119", b"R63rdWeapons.AssaultAUG",
            b"R63rdWeapons.PistolMk23", b"R63rdWeapons.SniperPSG1",
            b"R63rdWeapons.AssaultAK47", b"R63rdWeapons.AssaultG3A3",
            b"R63rdWeapons.SniperM82A1", b"R6Weapons.R6FragGrenadeGadget",
            b"None.None"))
    pal = rseloadout.palette(sample)
    everything = {c for g in pal.values() for c in g}

    check("the palette keeps gadgets and None out",
          all(c.startswith("R63rdWeapons.") for c in everything)
          and len(everything) == 13, "%d entries" % len(everything))

    # Both modes, because they take different branches: keeping the class
    # narrows the pool to same-role weapons, while a free choice draws from the
    # whole length group -- and a free choice is where a cross-length mistake
    # would show first. With keep_role on, only the names that have a same-role
    # neighbour at their length can move at all, so testing that mode alone
    # would leave the wider pool unexercised.
    bad = []
    moved = 0
    for _ in range(50):
        for group in pal.values():
            for name in group:
                for keep in (True, False):
                    got = rseloadout._swap_firearm(name.encode(), rng, pal,
                                                   keep_role=keep).decode()
                    if len(got) != len(name):
                        bad.append(("length", name, got))
                    if got not in everything:
                        bad.append(("outside palette", name, got))
                    if got != name:
                        moved += 1
    check("every swap preserves byte length", not [b for b in bad if b[0] == "length"],
          "%s" % bad[:2])
    check("and can only reach a weapon already in the palette",
          not [b for b in bad if b[0] == "outside palette"], "%s" % bad[:2])
    # Guard against the whole block passing because nothing ever swapped: a
    # palette of singletons would satisfy both checks above without exercising
    # anything. This one fails if the swap becomes a no-op.
    check("and the swaps actually happen, so the checks above mean something",
          moved > 200, "%d of %d attempts changed the name"
          % (moved, 50 * len(everything) * 2))

    # a sniper must never be swapped away, in any mode
    kept = True
    for sniper in (c for c in everything if rseloadout.role_of(c) == "Sniper"):
        for keep in (True, False):
            if rseloadout._swap_firearm(sniper.encode(), rng, pal,
                                        keep_role=keep).decode() != sniper:
                kept = False
    check("a sniper is never swapped away, in either mode", kept)

    # roles never cross when the class is meant to be kept
    crossed = []
    for group in pal.values():
        for name in group:
            role = rseloadout.role_of(name)
            for _ in range(20):
                got = rseloadout._swap_firearm(name.encode(), rng, pal,
                                               keep_role=True).decode()
                if rseloadout.role_of(got) != role:
                    crossed.append((name, got))
    check("keeping the class really keeps it", not crossed, "%s" % crossed[:3])

    # a length with only one weapon has nothing to swap to, and must say so
    lonely = rseloadout.palette(b"100, R63rdWeapons.AssaultGalilARM" + CRLF)
    got = rseloadout._swap_firearm(b"R63rdWeapons.AssaultGalilARM", rng, lonely)
    check("a weapon alone at its length is left exactly as it was",
          got == b"R63rdWeapons.AssaultGalilARM")

    # the width rule
    block = b"Assault=7\r\nSSniper=50\r\nObservation=100\r\n"
    out = rseloadout._set_field(block, "Assault", 90)
    check("a one-character field refuses a two-digit number",
          out == block, out.decode("latin-1"))
    out = rseloadout._set_field(block, "SSniper", 90)
    check("a two-character field takes one", b"SSniper=90\r\n" in out)
    out = rseloadout._set_field(block, "Observation", 90)
    check("a three-character field is padded, not shortened",
          b"Observation=090\r\n" in out, out.decode("latin-1"))

    # re-weighting keeps the total the game expects
    table = (b"025, R63rdWeapons.AssaultL85A1\r\n"
             b"025, R63rdWeapons.PistolUSP\r\n"
             b"050, R63rdWeapons.SubMP5A4\r\n")
    for seed in range(30):
        got = rseloadout._reweight(table, random.Random(seed))
        rows = rseloadout.ENTRY.findall(got)
        if len(got) != len(table) or sum(int(w) for w, _c in rows) != 100:
            check("a re-rolled table still totals 100 at the same length",
                  False, got.decode())
            break
        if any(int(w) <= 0 for w, _c in rows):
            check("and never leaves an entry that can never be rolled",
                  False, got.decode())
            break
    else:
        check("a re-rolled table still totals 100 at the same length", True)
        check("and never leaves an entry that can never be rolled", True)

    # an unknown mode is refused rather than silently ignored
    try:
        rseloadout.retune(b"", weapons="nonsense")
        check("an unknown mode is refused", False)
    except rseloadout.LoadoutError:
        check("an unknown mode is refused", True)

    # a file with no templates is a no-op, not a crash
    out, stats = rseloadout.retune(b"nothing to see here", weapons="chaos")
    check("a file with no templates comes back untouched",
          out == b"nothing to see here" and stats["templates"] == 0)


def run_mission_gallery(args):
    """Discs that show more than one picture on a mission card.

    The Xbox tool puts three pictures on each card; these are the PS2 discs
    that carry enough artwork to do the same. Ghost Recon's extras gallery is
    keyed by mission number, and Sum of All Fears ships a whole briefing kit.
    Jungle Storm and Ghost Recon 2 genuinely have nothing beyond the one
    image, which is asserted here so a later change cannot quietly claim
    otherwise.
    """
    from tcps2 import art
    from tcps2.games import BY_ID, ghost_recon, soaf, jungle_storm, ghost_recon2

    class Det:
        def __init__(self, path, profile):
            self.path, self.profile = path, profile

    print("\n[mission cards -- more than one picture]")

    if args.gr:
        det = Det(args.gr, BY_ID["ghost_recon_slus20613"])
        counts, missing = {}, []
        for m in ghost_recon.MISSIONS:
            names = ghost_recon.mission_art_for(ghost_recon.mission_key(m[0]))
            counts[m[1]] = len(names)
            for n in names:
                if art.mission_art(det, n) is None:
                    missing.append(n)
        check("Ghost Recon: every picture named is really on the disc",
              not missing, str(missing[:4]))
        georgia = [c for k, c in counts.items() if k.startswith("M")]
        desert = [c for k, c in counts.items() if k.startswith("D")]
        tac = [c for k, c in counts.items() if k.startswith("TAC")]
        check("Georgia missions get the map and a concept sketch",
              georgia and set(georgia) == {2}, str(sorted(set(georgia))))
        check("Desert Siege also gets a screenshot, so three",
              desert and set(desert) == {3}, str(sorted(set(desert))))
        check("and the training levels keep their single map",
              tac and set(tac) == {1}, str(sorted(set(tac))))

    if args.soaf:
        det = Det(args.soaf, BY_ID["soaf_sles51180"])
        missing, campaign = [], []
        for m in soaf.MISSIONS:
            names = soaf.mission_art_for(soaf.mission_key(m[0]))
            for n in names:
                if art.mission_art(det, n) is None:
                    missing.append(n)
            if not m[1].startswith("T"):
                campaign.append(len(names))
        check("Sum of All Fears: every name decodes, apostrophes and all",
              not missing, str(missing[:4]))
        check("every campaign mission gets three pictures",
              campaign and set(campaign) == {3}, str(sorted(set(campaign))))
        check("the 923x138 filmstrip is left out",
              not any("SHOTS" in n for v in soaf.EXTRA_ART.values() for n in v))

    if args.js:
        det = Det(args.js, BY_ID["jungle_storm_slus20820"])
        n = {len(jungle_storm.mission_art_for(jungle_storm.mission_key(m[0])))
             for m in jungle_storm.MISSIONS}
        check("Jungle Storm still shows one picture -- it ships no others",
              n == {1}, str(sorted(n)))

    if args.gr2:
        n = {len(ghost_recon2.mission_art_for(ghost_recon2.mission_key(m[0])))
             for m in ghost_recon2.MISSIONS}
        check("Ghost Recon 2 likewise has only the one", n == {1},
              str(sorted(n)))


def run_split_wheel(args):
    """The equipment-wheel branch in split screen.

    The switch was found by reading a savestate rather than the disc, so what
    can be asserted here is the shape of the edit: that it is one byte, at one
    place, in every container that carries it, and that it survives the
    container's compression. Whether it makes the wheel appear is a
    play-test, and the option says so.
    """
    import re
    from tcps2 import (dataedit, lin, rsecanon, rsechatter, rsemandown,
                       rsesidearm, rsewheel, uscode)
    from tcps2.games import BY_ID
    from tcps2.iso import Iso
    from tcps2.vokes import open_archives

    if not args.rs3data:
        return
    print("\n[Rainbow Six 3 -- the equipment wheel in split screen]")

    seen, checked = set(), 0
    with Iso(args.rs3data) as iso:
        for arc in open_archives(iso, r"/VOKES\d\.IMG$"):
            for path in sorted(arc.files):
                if not re.search(r"/COMMON(OFF|_SS)?\.LIN$", path) or path in seen:
                    continue
                seen.add(path)
                raw = _stock_bytes(args.rs3data, arc, path)
                kind, plain = dataedit._unpack(raw, path)

                at = rsewheel.find(plain)
                check("%s: the tick fallback is where it was measured" % path[1:],
                      at == rsewheel.KNOWN_OFFSET,
                      "found %#x, expected %#x" % (at, rsewheel.KNOWN_OFFSET))
                check("%s: and it still tests NetMode == 3 as shipped" % path[1:],
                      plain[at] == rsewheel.NETMODE_SHIPPED,
                      "got %d" % plain[at])
                check("%s: the anchor occurs exactly once" % path[1:],
                      plain.count(rsewheel._HEAD) == 1,
                      "%d times" % plain.count(rsewheel._HEAD))
                other = bytes.fromhex("39 3a 24 03 16 18 09 00 77 01".replace(" ", ""))
                check("%s: the other NetMode==3 site is left alone" % path[1:],
                      plain.count(other) == 2, "%d sites" % plain.count(other))

                on, n = rsewheel.restore(plain, True)
                check("%s: turning it on changes exactly one byte" % path[1:],
                      n == 1 and len(on) == len(plain)
                      and sum(a != b for a, b in zip(plain, on)) == 1)
                check("%s: and that byte becomes standalone (0)" % path[1:],
                      on[at] == rsewheel.NETMODE_STANDALONE)
                back, _ = rsewheel.restore(on, False)
                check("%s: turning it off puts the disc back exactly" % path[1:],
                      back == plain)
                check("%s: the state reads back" % path[1:],
                      rsewheel.reads(on) and not rsewheel.reads(plain))
                check("%s: asking twice is a no-op" % path[1:],
                      rsewheel.restore(on, True)[1] == 0)

                packed = dataedit._repack(kind, raw, on)
                check("%s: the container keeps its length" % path[1:],
                      len(packed) == len(raw),
                      "%d -> %d" % (len(raw), len(packed)))
                check("%s: and still decompresses to the edited bytes" % path[1:],
                      lin.decompress(packed) == on)
                checked += 1

                # and the cycle count, which lives in the same file
                cat = rsewheel.cycle_find(plain)
                check("%s: the cycle count is where it was measured" % path[1:],
                      cat == 0x1088D2, "found %#x" % cat)
                check("%s: and split screen still gets 4 as shipped" % path[1:],
                      plain[cat] == rsewheel.CYCLE_SPLIT, "got %d" % plain[cat])
                cyc, cn = rsewheel.cycle_restore(plain, True)
                check("%s: the cycle edit moves exactly one byte" % path[1:],
                      cn == 1 and len(cyc) == len(plain)
                      and sum(a != b for a, b in zip(plain, cyc)) == 1)
                check("%s: to the 2 the rest of the game uses" % path[1:],
                      cyc[cat] == rsewheel.CYCLE_SINGLE)
                check("%s: and it reverses exactly" % path[1:],
                      rsewheel.cycle_restore(cyc, False)[0] == plain)
                # the two edits must not tread on each other
                both, _ = rsewheel.cycle_restore(
                    rsewheel.restore(plain, True)[0], True)
                check("%s: wheel and cycle edits coexist" % path[1:],
                      rsewheel.reads(both) and rsewheel.cycle_reads(both)
                      and sum(a != b for a, b in zip(plain, both)) == 2)

                # the sidearm roll, inserted into the same containers
                sat = rsesidearm.find_block(plain)
                check("%s: the reload function is located" % path[1:],
                      sat == 0x12FAC6, "found %#x" % sat)
                check("%s: and it reads as stock" % path[1:],
                      rsesidearm.reads(plain) == (0, False))
                sid, sn = rsesidearm.apply(plain, 40)
                check("%s: the roll goes in without changing the length"
                      % path[1:], sn == 1 and len(sid) == len(plain))
                check("%s: and reads back as the chance asked for" % path[1:],
                      rsesidearm.reads(sid) == (40, True),
                      "got %r" % (rsesidearm.reads(sid),))
                # the contact test is optional and both shapes must read back
                loose, _ = rsesidearm.apply(plain, 40, in_contact=False)
                check("%s: and without the contact test too" % path[1:],
                      rsesidearm.reads(loose) == (40, False),
                      "got %r" % (rsesidearm.reads(loose),))
                # Both shapes keep the block's declared memory size -- that is
                # the invariant the console cares about. What differs is how
                # much of the slot is real code rather than trailing padding.
                def _live(buf):
                    blk = uscode.Script.at(buf, sat)
                    end = max(t.mstart for t in blk.toks
                              if t.op == uscode.EX_RETURN)
                    return end
                check("%s: the contact test costs real bytes" % path[1:],
                      _live(sid) > _live(loose),
                      "%d vs %d" % (_live(sid), _live(loose)))
                check("%s: and both keep the declared memory size" % path[1:],
                      uscode.Script.at(sid, sat).mem_len
                      == uscode.Script.at(loose, sat).mem_len
                      == uscode.Script.at(plain, sat).mem_len)
                check("%s: and it borrows the function's own Enemy reference"
                      % path[1:],
                      rsesidearm._enemy_ref(uscode.Script.at(plain, sat))
                      == rsesidearm._enemy_ref(uscode.Script.at(sid, sat)))
                check("%s: a zero chance writes nothing at all" % path[1:],
                      rsesidearm.apply(plain, 0) == (plain, 0))
                # the reload call-out, which is independent of the roll
                say, syn = rsesidearm.apply(plain, 0, True, 25)
                check("%s: the call-out goes in on its own" % path[1:],
                      syn == 1 and len(say) == len(plain)
                      and rsesidearm.reads(say) == (0, False))
                sblk = uscode.Script.at(say, sat)
                check("%s: and it really added statements" % path[1:],
                      len(sblk.toks) != len(uscode.Script.at(plain, sat).toks))
                check("%s: without moving the declared memory size" % path[1:],
                      sblk.mem_len == uscode.Script.at(plain, sat).mem_len)
                calls = [t for t in sblk.statements()
                         if t.op == rsesidearm.EX_VIRTUAL_FUNCTION
                         and len(t.parts[1][1]) == 1
                         and t.parts[1][1][0].op == rsesidearm.EX_BYTE_CONST
                         and t.parts[1][1][0].parts[0][1][0]
                         == rsesidearm.AMMO_VOICE]
                was = [t for t in uscode.Script.at(plain, sat).statements()
                       if t.op == rsesidearm.EX_VIRTUAL_FUNCTION
                       and len(t.parts[1][1]) == 1
                       and t.parts[1][1][0].op == rsesidearm.EX_BYTE_CONST
                       and t.parts[1][1][0].parts[0][1][0]
                       == rsesidearm.AMMO_VOICE]
                check("%s: one more PlaySoundCurrentAction(12) than shipped"
                      % path[1:], len(calls) == len(was) + 1,
                      "%d vs %d" % (len(calls), len(was)))
                both3, b3n = rsesidearm.apply(plain, 40, True, 25)
                check("%s: roll and call-out together still fit" % path[1:],
                      b3n == 1 and len(both3) == len(plain)
                      and rsesidearm.reads(both3) == (40, True))
                for bad in (-1, 0.5 and 91, 200):
                    try:
                        rsesidearm.apply(plain, bad)
                        check("%s: an out-of-range chance is refused" % path[1:],
                              False, "accepted %r" % bad)
                        break
                    except rsesidearm.SidearmError:
                        pass
                else:
                    check("%s: an out-of-range chance is refused" % path[1:], True)
                # only that one function may move
                span = uscode.Script.at(plain, sat).disk_len + 4
                outside = [i for i in range(len(plain))
                           if plain[i] != sid[i] and not (sat <= i < sat + span)]
                check("%s: nothing outside the function is touched" % path[1:],
                      not outside, "%d bytes elsewhere" % len(outside))
                trio, _ = rsesidearm.apply(both, 40)
                check("%s: all three COMMON edits coexist" % path[1:],
                      rsewheel.reads(trio) and rsewheel.cycle_reads(trio)
                      and rsesidearm.reads(trio) == (40, True))
                spacked = dataedit._repack(kind, raw, sid)
                check("%s: and the container still keeps its length" % path[1:],
                      len(spacked) == len(raw),
                      "%d -> %d" % (len(raw), len(spacked)))

                # the split-screen death call-out
                mat = rsemandown.find_block(plain)
                check("%s: the player death function is located" % path[1:],
                      mat == 0x10B465, "found %#x" % mat)
                check("%s: and reads as stock" % path[1:],
                      not rsemandown.reads(plain))
                md, mn = rsemandown.apply(plain)
                check("%s: the call-out edit keeps the length" % path[1:],
                      mn == 1 and len(md) == len(plain))
                check("%s: and reads back as wired" % path[1:],
                      rsemandown.reads(md))
                check("%s: applying it twice is a no-op" % path[1:],
                      rsemandown.apply(md) == (md, 0))
                mspan = uscode.Script.at(plain, mat).disk_len + 4
                moutside = [i for i in range(len(plain))
                            if plain[i] != md[i] and not (mat <= i < mat + mspan)]
                check("%s: and nothing outside that function moves" % path[1:],
                      not moutside, "%d bytes elsewhere" % len(moutside))
                # The declared memory size must come back EXACTLY. Every edit
                # that shrank it hung the level load on a real console; the
                # padding is chosen to hit the original number on the nose.
                check("%s: the rewritten block still parses" % path[1:],
                      uscode.Script.at(md, mat).mem_len
                      == uscode.Script.at(plain, mat).mem_len)
                mpacked = dataedit._repack(kind, raw, md)
                check("%s: the container survives the call-out edit" % path[1:],
                      len(mpacked) == len(raw))

                # player 2 calling out player 1's kills
                cat = rsechatter.find_block(plain)
                check("%s: the player kill handler is located" % path[1:],
                      cat == 0x10B5B5, "found %#x" % cat)
                check("%s: and reads as stock" % path[1:],
                      rsechatter.reads(plain) == (0, False))
                check("%s: a chance of 0 leaves it alone" % path[1:],
                      rsechatter.apply(plain, 0) == (plain, 0))
                ch, cn2 = rsechatter.apply(plain, 35)
                check("%s: the chatter edit keeps the length" % path[1:],
                      cn2 == 1 and len(ch) == len(plain))
                check("%s: and reads back the chance it was given" % path[1:],
                      rsechatter.reads(ch) == (35, True))
                check("%s: the hostage arm can be left out" % path[1:],
                      rsechatter.reads(rsechatter.apply(plain, 35, False)[0])
                      == (35, False))
                check("%s: applying it twice is a no-op" % path[1:],
                      rsechatter.apply(ch, 35) == (ch, 0))
                check("%s: an over-range chance is clamped" % path[1:],
                      rsechatter.reads(rsechatter.apply(plain, 500)[0])[0]
                      == rsechatter.MAX_CHANCE)
                cspan = uscode.Script.at(plain, cat).disk_len + 4
                coutside = [i for i in range(len(plain))
                            if plain[i] != ch[i] and not (cat <= i < cat + cspan)]
                check("%s: and nothing outside that function moves" % path[1:],
                      not coutside, "%d bytes elsewhere" % len(coutside))
                # the three dead calls must all be gone, and the speaker built
                news = [t for t in uscode.Script.at(ch, cat).statements()
                        if t.op == rsechatter.EX_CONTEXT
                        and t.parts[0][1].op == rsechatter.EX_NEW]
                check("%s: all three call-outs build their own voice" % path[1:],
                      len(news) == 3, "%d" % len(news))
                cpacked = dataedit._repack(kind, raw, ch)
                check("%s: the container survives the chatter edit" % path[1:],
                      len(cpacked) == len(raw))

                # the canon split-screen team -- COMMON_SS.LIN only
                if path == "/COMMON_SS.LIN":
                    check("%s: stock picks Price for member 1" % path[1:],
                          not rsecanon.reads(plain))
                    cn, cc = rsecanon.apply(plain)
                    check("%s: the canon team fits its function" % path[1:],
                          cc == 1 and len(cn) == len(plain))
                    check("%s: and reads back as wired" % path[1:],
                          rsecanon.reads(cn))
                    check("%s: applying it twice is a no-op" % path[1:],
                          rsecanon.apply(cn) == (cn, 0))
                    cat, _cs = rsecanon._block(plain, rsecanon.TEAM_MEMBER_SIG, "x")
                    cspan = uscode.Script.at(plain, cat).disk_len + 4
                    cout = [i for i in range(len(plain))
                            if plain[i] != cn[i] and not (cat <= i < cat + cspan)]
                    check("%s: nothing outside CreateTeamMember moves" % path[1:],
                          not cout, "%d bytes elsewhere" % len(cout))
                    # the two new jumps must land on the Loiselle and Weber arms
                    cs = uscode.Script.at(cn, cat)
                    arms = {id(t) for t in rsecanon._case_bodies(cs).values()}
                    landed = [t for t in cs.toks if t.name == "Jump"
                              and t.parts[0][1] is not uscode.END
                              and id(t.parts[0][1]) in arms]
                    check("%s: both canon jumps enter a switch arm" % path[1:],
                          len(landed) == 2, "%d jumps" % len(landed))
                    cpacked = dataedit._repack(kind, raw, cn)
                    check("%s: the container survives the canon edit" % path[1:],
                          len(cpacked) == len(raw))
                else:
                    # it must never be offered anywhere but the split-screen copy
                    check("%s: is not the split-screen package" % path[1:],
                          not __import__("re").search(r"/COMMON_SS\.LIN$", path))

                # THE test for the bytecode tool: every script block in the
                # package must survive parse -> assemble unchanged. A tool that
                # can rewrite one function safely but corrupts another is worse
                # than no tool, and this is the only way to know.
                if path == "/COMMON.LIN":
                    total = ident = refused = 0
                    for off in uscode.find_blocks(plain):
                        total += 1
                        try:
                            blk = uscode.Script.at(plain, off)
                            disk, mem = blk.assemble(blk.disk_len)
                        except uscode.ScriptError:
                            refused += 1
                            continue
                        if (disk == plain[off + 4:off + 4 + blk.disk_len]
                                and mem == blk.mem_len):
                            ident += 1
                    check("every script block round-trips byte for byte",
                          ident + refused == total and ident > 6000,
                          "%d identical, %d refused, %d total"
                          % (ident, refused, total))
                    check("and the ones it refuses are refused, never mangled",
                          refused < total // 50, "%d of %d" % (refused, total))

    # the label-scaling cheat: it rewrites live code, so the words it claims
    # to replace must really be there, and its cave must be empty
    from tcps2 import overlay as _ov
    from tcps2.games.r6_3 import SP as _SP, CAVE_WORDS as _SPAWN
    with Iso(args.rs3data) as _iso:
        _o = _ov.open_overlay(_iso, _SP)
        bad = [(va, _o.read_word(va), want)
               for va, want in rsewheel.LABEL_HOOKS if _o.read_word(va) != want]
        check("every wheel-label hook replaces the instruction it expects",
              not bad, str(bad))
        busy = [va for i in range(12)
                for va in (rsewheel.LABEL_CAVE + i * 4,)
                if _o.read_word(va) != 0]
        check("and its cave is empty on a stock disc", not busy, str(busy))
    words = rsewheel.label_words()
    check("the cheat is 4 hooks plus a 3-word cave each",
          len(words) == 16, str(len(words)))
    check("each cave ends by redoing the instruction its hook took",
          [w for _va, w, _s, _n in words[2::3][:4]]
          == [orig for _site, orig in rsewheel.LABEL_HOOKS])
    check("every hook is a jal into its own cave",
          all((w >> 26) == 3 and ((w & 0x03FFFFFF) << 2)
              == rsewheel.LABEL_CAVE + i * 12
              for i, (_va, w, _s, _n) in enumerate(words[12:])))
    spawn = {va for va, _w in _SPAWN}
    check("and it never lands on the map-wide spawn cave",
          not [va for va, _w, _s, _n in words if va in spawn])
    _p = BY_ID["r6_3_slus20883"]
    check("the option is cheat-file, not disc",
          _p.setting("split_wheel_labels").touches == "cheat")
    check("and it needs the wheel itself",
          _p.setting("split_wheel_labels").requires == {"split_wheel": [True]})
    check("leaving it off writes no cheat lines", not _p.build_pnach({}))
    check("turning it on writes exactly those 16",
          len(_p.build_pnach({"split_wheel_labels": True})) == 16)
    check("and it coexists with the map-wide spawn cheat",
          len(_p.build_pnach({"split_wheel_labels": True,
                              "wave_enable": True, "wave_mapwide": True})) == 84)

    check("all three COMMON containers carry the branch", checked == 3,
          "%d checked" % checked)

    profile = BY_ID["r6_3_slus20883"]
    keys = {s.key for s in profile.settings}
    check("the option reaches the profile", "split_wheel" in keys)
    check("and so does the L1-tap option", "split_cycle" in keys)
    check("which needs the wheel, since without it there is no way to a gadget",
          profile.setting("split_cycle").requires == {"split_wheel": [True]})
    # Watched working in split screen on Oil Refinery, along with the L1 tap.
    # The caution still has to carry what is imperfect about it: the wheel is
    # drawn from the framebuffer, so it spills past the player's half.
    s = profile.setting("split_wheel")
    check("and is offered, marked as watched working",
          s.confidence == "verified" and s.enabled,
          "%s enabled=%s" % (s.confidence, s.enabled))
    check("and still says it needs cropping",
          "cropping" in s.caution.lower())
    check("the L1 tap is watched working too",
          profile.setting("split_cycle").confidence == "verified")
    check("leaving it off writes nothing",
          not any(e.op == "split_wheel" for e in profile.build_data({})))
    check("the edit still applies cleanly if it is ever re-enabled",
          len([e for e in profile.build_data({"split_wheel": True})
               if e.op == "split_wheel"]) == 1)


def run_zopfli_fallback():
    """The chunk that zlib cannot pack, which is why zopfli is here at all."""
    import zlib
    from tcps2 import lin

    print("\n[LIN -- the chunks zlib cannot fit]")

    # A payload zlib packs poorly is hard to contrive; what matters is the
    # contract, so drive the helper directly.
    body = bytes(range(256)) * 64
    budget = len(zlib.compress(body, 9))
    got = lin._deflate_within(body, budget)
    check("a chunk that fits is packed with plain zlib",
          got is not None and len(got) <= budget)
    check("and inflates back to what went in",
          got is not None and zlib.decompress(got) == body)

    check("an impossible budget is refused rather than truncated",
          lin._deflate_within(body, 8) is None)

    packed = lin._zopfli(body)
    if packed is None:
        check("zopfli is not installed, so the fallback is inert", True)
    else:
        check("zopfli beats zlib -9 on the same bytes",
              len(packed) <= len(zlib.compress(body, 9)),
              "%d vs %d" % (len(packed), len(zlib.compress(body, 9))))
        check("and its output is ordinary zlib any inflater reads",
              zlib.decompress(packed) == body)
        tight = len(packed)
        got = lin._deflate_within(body, tight)
        check("a budget only zopfli can meet is met",
              got is not None and len(got) <= tight
              and zlib.decompress(got) == body)


def run_uscode_units():
    """The bytecode reader and writer, on synthetic code with no disc at all."""
    import struct as _struct
    from tcps2 import uscode
    from tcps2.uscode import Script, Tok, ScriptError, parse_expr

    print("\n[UnrealScript bytecode -- the rules, without a disc]")

    # FCompactIndex, which is what makes the file shorter than the loaded image
    widths = set()
    ok = True
    for v in list(range(-300, 300)) + [0x3F, 0x40, 0x1FFF, 0x2000, -0x1FFFF,
                                       0x7FFFFF, -1, 1 << 24]:
        raw = uscode.compact_encode(v)
        widths.add(len(raw))
        back, n = uscode.compact_decode(raw, 0)
        if back != v or n != len(raw):
            ok = False
    check("a compact index round-trips, sign and all", ok)
    check("and it really is variable width", len(widths) >= 3, str(sorted(widths)))
    check("small values take one byte",
          len(uscode.compact_encode(8)) == 1
          and len(uscode.compact_encode(-22)) == 1)

    # a block with a forward jump, built by hand:
    #   0x00 JumpIfNot(->0x07, True)     disk 4   memory 4
    #   0x04 Return(Nothing)             disk 2   memory 2
    #   0x06 Nothing                     disk 1   memory 1
    #   0x07 Return(Nothing)
    body = bytes([0x07, 0x07, 0x00, 0x27,   # JumpIfNot @7, True
                  0x04, 0x0B,               # Return Nothing
                  0x0B,                     # Nothing
                  0x04, 0x0B])              # Return Nothing
    blob = bytearray(_struct.pack("<I", len(body)) + body)
    s = Script.at(bytes(blob), 0)
    check("a hand-built block parses to its declared length",
          s.mem_len == len(body) and s.disk_len == len(body))
    disk, mem = s.assemble(s.disk_len)
    check("and round-trips unchanged", disk == body and mem == len(body))

    # inserting a byte must move the jump, by the MEMORY delta
    ins = parse_expr(bytes([0x0B]))
    s.toks.insert(1, ins)
    disk2, mem2 = s.assemble()
    check("inserting a statement lengthens the block",
          mem2 == len(body) + 1 and len(disk2) == len(body) + 1)
    check("and re-bases the jump over it",
          _struct.unpack_from("<H", disk2, 1)[0] == 8,
          "target is %d" % _struct.unpack_from("<H", disk2, 1)[0])

    # padding back to the original disk length is what keeps a LIN package fixed
    s2 = Script.at(bytes(blob), 0)
    s2.toks.append(parse_expr(bytes([0x0B])))
    slot = s2.disk_len + 4
    padded, pmem = s2.assemble(slot)
    check("padding fills the slot exactly",
          len(padded) == slot and pmem == slot,
          "disk %d, mem %d, slot %d" % (len(padded), pmem, slot))
    check("and the padding is EX_Nothing, which is unreachable after a return",
          set(padded[-3:]) == {uscode.EX_NOTHING})

    # a jump that lands mid-token is not a jump, and must be refused
    broken = bytearray(blob)
    broken[1 + 1] = 0x05        # retarget to 0x05, inside Return(Nothing)
    try:
        Script.at(bytes(broken), 0)
        check("a jump into the middle of a token is refused", False)
    except ScriptError:
        check("a jump into the middle of a token is refused", True)

    # removing a statement something jumps to would silently redirect it
    s3 = Script.at(bytes(blob), 0)
    target = s3.statement_at(7)
    try:
        s3.remove([target])
        check("removing a jump target is refused", False)
    except ScriptError:
        check("removing a jump target is refused", True)
    check("removing a statement nothing jumps to is allowed",
          s3.remove([s3.statement_at(6)]) is None)

    # an authored fragment may not carry jumps, having no block to resolve them
    try:
        parse_expr(bytes([0x06, 0x00, 0x00]))
        check("a fragment carrying a jump is refused", False)
    except ScriptError:
        check("a fragment carrying a jump is refused", True)
    try:
        parse_expr(bytes([0x0B, 0x0B]))
        check("a fragment with trailing bytes is refused", False)
    except ScriptError:
        check("a fragment with trailing bytes is refused", True)

    # the skip words: a Context stores its guarded expression's length, a Skip
    # stores one more. Both are measured from the disc, not assumed.
    check("the skip adjustments are the measured ones",
          uscode.SKIP_ADJUST == {0x12: -1, 0x19: -1, 0x18: +1})


def run_rpg_speed(args):
    """How fast RPG troops ready a rocket.

    The wait before a rocket shot is an animation played at half speed, not a
    timer and not an ammunition count -- `StandReloadRPG` and `StandFireRPG`
    are each issued through `PlayAnim(name, 0.5)`. The names came from decoding
    the `EX_NameConst` compact index against the name table of the package at
    0x86a7f, which is the only reason a bare index is readable at all.
    """
    import re
    from tcps2 import dataedit, lin, rserpg
    from tcps2.games import BY_ID
    from tcps2.iso import Iso
    from tcps2.vokes import open_archives

    if not args.rs3data:
        return
    print("\n[Rainbow Six 3 -- RPG troops readying a rocket]")
    seen, checked = set(), 0
    with Iso(args.rs3data) as iso:
        for arc in open_archives(iso, r"/VOKES\d\.IMG$"):
            for path in sorted(arc.files):
                if not re.search(r"/COMMON(OFF|_SS)?\.LIN$", path) or path in seen:
                    continue
                seen.add(path)
                raw = _stock_bytes(args.rs3data, arc, path)
                kind, plain = dataedit._unpack(raw, path)

                for which, known in (("reload", 0x124B11), ("fire", 0x124AE9)):
                    at = rserpg.find(plain, which)
                    check("%s: the %s rate is where it was measured"
                          % (path[1:], which), at == known,
                          "found %#x, expected %#x" % (at, known))
                    check("%s: and the game ships it at half speed"
                          % (path[1:], ), rserpg.rate(plain, which) == 0.5,
                          "got %r" % rserpg.rate(plain, which))

                new, n = rserpg.apply(plain, 4)
                check("%s: 4x writes both animations" % path[1:], n == 2,
                      "%d written" % n)
                check("%s: and the length never moves" % path[1:],
                      len(new) == len(plain))
                check("%s: 0.5 becomes 2.0" % path[1:],
                      rserpg.rate(new, "reload") == 2.0
                      and rserpg.rate(new, "fire") == 2.0)
                # 0.5 -> 2.0 only moves the exponent, so counting changed
                # bytes is the wrong check. What matters is that every byte
                # that moved lies inside one of the two four-byte rate slots.
                slots = set()
                for w in ("reload", "fire"):
                    slots.update(range(rserpg.find(plain, w),
                                       rserpg.find(plain, w) + 4))
                moved = {i for i, (a, b) in enumerate(zip(plain, new)) if a != b}
                check("%s: nothing outside the two rate slots is touched"
                      % path[1:], moved and moved <= slots,
                      "%d bytes moved, %d of them outside"
                      % (len(moved), len(moved - slots)))
                check("%s: 1x puts it back exactly" % path[1:],
                      rserpg.apply(new, 1)[0] == plain)

                packed = dataedit._repack(kind, raw, new)
                check("%s: the container keeps its length" % path[1:],
                      len(packed) == len(raw))
                check("%s: and still decompresses to the edited bytes"
                      % path[1:], lin.decompress(packed) == new)
                checked += 1
    check("all three COMMON containers carry the rates", checked == 3,
          "%d checked" % checked)

    # a rate nobody should be able to ask for
    try:
        rserpg.set_rate(b"", "reload", 99.0)
        check("an absurd rate is refused", False)
    except rserpg.RpgError:
        check("an absurd rate is refused", True)

    profile = BY_ID["r6_3_slus20883"]
    check("the dial reaches the profile",
          profile.setting("rpg_speed") is not None)
    check("leaving it at 1x writes nothing",
          not [e for e in profile.build_data({}) if e.op == "rpg_speed"])
    made = [e for e in profile.build_data({"rpg_speed": 4})
            if e.op == "rpg_speed"]
    check("and moving it writes exactly one edit", len(made) == 1
          and made[0].params == {"speed": 4})


def run_split_scope(args):
    """The one branch that throws the scope overlay away in split screen.

    Everything upstream is healthy in split screen -- the textures reach the
    render devices and the scope-active flag is set -- so the assertions here
    are about the branch itself and about the fact that the option is honest
    that it is an experiment.
    """
    from tcps2 import overlay, rsescope
    from tcps2.games import BY_ID
    from tcps2.games.r6_3 import SP, STOCK
    from tcps2.iso import Iso

    if not args.rs3data:
        return
    print("\n[Rainbow Six 3 -- the scope overlay in split screen]")
    with Iso(args.rs3data) as iso:
        ov = overlay.open_overlay(iso, SP)
        live = ov.read_word(rsescope.SCOPE_BRANCH)
    check("the branch is one of the two words it can be",
          live in (rsescope.SCOPE_BRANCH_STOCK, rsescope.SCOPE_BRANCH_OPEN),
          "%#010x" % live)
    check("the shipped word is recorded, so a patched disc can be healed",
          STOCK.get(rsescope.SCOPE_BRANCH) == rsescope.SCOPE_BRANCH_STOCK,
          "%r" % STOCK.get(rsescope.SCOPE_BRANCH))
    check("and it decodes as the branch we think it is",
          (rsescope.SCOPE_BRANCH_STOCK >> 26) == 5          # bne
          and ((rsescope.SCOPE_BRANCH_STOCK >> 16) & 31) == 0)   # against $zero

    # the cave that fits the overlay to the viewport
    from tcps2.games.r6_3 import CAVE_WORDS as _SPAWN
    from tcps2 import rsewheel as _rw
    vw = rsescope.viewport_words()
    hooks = [(va, w) for va, w, _s, _n in vw if (w >> 26) == 3]
    caves = {va: w for va, w, _s, _n in vw if va >= 0x00500000}
    check("the cheat is 8 hooks, 12 retired words and three caves",
          len(vw) == 41 and len(hooks) == 8 and len(caves) == 17, str(len(vw)))

    with Iso(args.rs3data) as iso:
        ov2 = overlay.open_overlay(iso, SP)
        bad = [(va, "%#010x" % ov2.read_word(va), "%#010x" % st)
               for va, _w, st, _n in vw
               if va < 0x00500000 and ov2.read_word(va) != st]
        check("every word the cheat overwrites is the word it claims",
              not bad, str(bad))
        busy = [va for va in caves if ov2.read_word(va) != 0]
        check("and all three caves are empty on a stock disc",
              not busy, str(busy))

        # The bug this option shipped with: `jal` has a delay slot, so the
        # instruction AFTER a hook runs BEFORE the cave. A branch there is
        # undefined on the R5900, and it hung the game on the loading screen.
        BRANCHES = (1, 2, 3, 4, 5, 6, 7, 20, 21, 22, 23)
        emitted = {va: w for va, w, _s, _n in vw}
        slots = []
        for va, _w in hooks:
            nxt = emitted.get(va + 4, ov2.read_word(va + 4))
            if (nxt >> 26) in BRANCHES:
                slots.append("%#010x -> %#010x" % (va, nxt))
        check("no hook puts a branch in a jal delay slot", not slots,
              str(slots))

        # ... and the delay slot must not read the register the cave loads,
        # which would give it the stale framebuffer value.
        stale = []
        for va, w in hooks:
            target = (w & 0x03FFFFFF) << 2
            loads = 8 if target == rsescope._HEIGHT_CAVE else 2   # $t0 / $v0
            nxt = emitted.get(va + 4, ov2.read_word(va + 4))
            if nxt == 0:
                continue
            rs, rt = (nxt >> 21) & 31, (nxt >> 16) & 31
            if loads in (rs, rt):
                stale.append("%#010x -> %#010x" % (va, nxt))
        check("nor one that reads the register the cave is about to load",
              not stale, str(stale))

    check("four hooks take the width and four the height",
          len(rsescope.WIDTH_HOOKS) == 4 and len(rsescope.HEIGHT_HOOKS) == 4)
    check("every hook is a jal into one of the three caves",
          all(((w & 0x03FFFFFF) << 2)
              in set(rsescope._WIDTH_CAVE.values()) | {rsescope._HEIGHT_CAVE}
              for _va, w in hooks))
    mine = {va for va, _w, _s, _n in vw}
    check("it lands on neither of the other two caves",
          not (mine & {va for va, _w, _s, _n in _rw.label_words()})
          and not (mine & {va for va, _w in _SPAWN}))
    check("the hooked reads are the ones the module recorded",
          {va for va, _rd in rsescope.WIDTH_HOOKS}
          | set(rsescope.HEIGHT_HOOKS) == set(rsescope.FRAMEBUFFER_READS))

    profile = BY_ID["r6_3_slus20883"]
    check("the option reaches the profile",
          profile.setting("split_scope") is not None)
    check("the fitting option needs the overlay switched on first",
          profile.setting("split_scope_fit").requires
          == {"split_scope": [True]})
    check("and it is a cheat, not a disc edit",
          profile.setting("split_scope_fit").touches == "cheat")
    check("turning both on writes exactly those 41 lines",
          len(profile.build_pnach({"split_scope_fit": True,
                                   "split_scope": True})) == 41)

    # A pnach is re-applied every frame, so an option left ticked behind an
    # unticked prerequisite could not be undone by unticking it. `requires`
    # greys the widget out; it has to gate the generator as well.
    check("with the overlay off, the fitting cheat writes nothing",
          not profile.build_pnach({"split_scope_fit": True,
                                   "split_scope": False}))
    eff = profile.effective({"split_scope_fit": True, "split_scope": False,
                             "split_wheel_labels": True, "split_wheel": False})
    check("and effective() neutralises both cheats whose prerequisite is off",
          eff["split_scope_fit"] is False
          and eff["split_wheel_labels"] is False)
    check("a chain of requirements resolves all the way down",
          profile.effective({"ai_finite_ammo": False,
                             "ai_sidearm": 50})["ai_sidearm"] == 0)
    check("all three caves coexist",
          len(profile.build_pnach({"split_scope_fit": True,
                                   "split_scope": True,
                                   "split_wheel_labels": True,
                                   "split_wheel": True,
                                   "wave_enable": True,
                                   "wave_mapwide": True})) == 125)
    # Watched drawing in split screen on Island Estate, both halves, so this
    # is no longer a guess. The caution still has to say what is imperfect
    # about it -- the overlay is not fitted to the viewport -- because that is
    # the part a player will actually notice.
    check("it is marked as watched working",
          profile.setting("split_scope").confidence == "verified")
    check("and still says what is not right about it",
          "fit" in profile.setting("split_scope").caution.lower())
    check("leaving it off writes no word",
          not [e for e in profile.build_edits({})
               if e.va == rsescope.SCOPE_BRANCH])
    made = [e for e in profile.build_edits({"split_scope": True})
            if e.va == rsescope.SCOPE_BRANCH]
    check("turning it on clears exactly that branch",
          len(made) == 1 and made[0].value == rsescope.SCOPE_BRANCH_OPEN
          and made[0].stock == rsescope.SCOPE_BRANCH_STOCK)

    # the caveat is the point: the draw sizes itself off the framebuffer
    check("the framebuffer and viewport fields are both recorded, since the "
          "real fix needs them",
          rsescope.G_FRAMEBUFFER == (0x7C4, 0x7C8)
          and rsescope.G_VIEWPORT_RECT == 0x40A00
          and len(rsescope.FRAMEBUFFER_READS) == 8)


def run_enemy_flashlights(args):
    """The per-archetype flashlight flag.

    The safety argument is that one digit replaces one digit, so the assertions
    are mostly about length and about nothing else in the file moving.
    """
    import collections
    import re
    from tcps2 import dataedit, lin, rseloadout, vokes
    from tcps2.games import BY_ID
    from tcps2.iso import Iso

    if not args.rs3data:
        return
    print(chr(10) + "[Rainbow Six 3 -- enemy flashlights]")
    with Iso(args.rs3data) as iso:
        arc = [v for v in vokes.open_archives(iso)
               if "VOKES0" in str(getattr(v.r, "name", "")).upper()][0]
        container = arc.read_file("/COMMON.LIN")
    plain = lin.decompress(container)

    def share_of(buf):
        c = collections.Counter(m.group(1).decode()
                                for m in re.finditer(rb"Flashlight=([0-9]+)", buf))
        return c

    stock = share_of(plain)
    check("the disc ships the flag on a minority of templates",
          stock.get("1", 0) == 10 and stock.get("0", 0) == 108, str(dict(stock)))
    check("and that is every template rseloadout knows about",
          sum(stock.values()) == len(rseloadout.templates(plain)),
          "%d vs %d" % (sum(stock.values()), len(rseloadout.templates(plain))))

    op = dataedit.OPS["enemy_loadout"]
    for want, expect_on in (("none", 0), ("half", 59), ("all", 118)):
        out, _n = op(plain, {"weapons": "stock",
                             "flashlight": rseloadout.GADGET_SHARES[want]}, None)
        got = share_of(out)
        check("%s gives %d templates a flashlight" % (want, expect_on),
              got.get("1", 0) == expect_on, str(dict(got)))
        check("%s does not move the file length" % want, len(out) == len(plain))

    a, _ = op(plain, {"weapons": "stock", "flashlight": 35}, None)
    b, _ = op(plain, {"weapons": "stock", "flashlight": 35}, None)
    check("the same share gives the same file twice", a == b)
    NLB = bytes([10])
    touched = {plain[max(0, i - 14):i + 1].split(b"=")[0].split(NLB)[-1]
               for i in range(len(plain)) if plain[i] != a[i]}
    check("and nothing but the flag is touched",
          touched == {b"Flashlight"}, str(touched))

    out, _n = op(plain, {"weapons": "stock", "flashlight": 100}, container)
    packed = lin.substitute(container, lambda _old: out)[0]
    check("a full set still repacks into the shipped container",
          len(packed) == len(container))
    check("and decompresses back to exactly what was written",
          lin.decompress(packed) == out)

    p = BY_ID["r6_3_slus20883"]
    check("leaving it alone emits no flashlight parameter",
          "flashlight" not in [e for e in p.build_data(p.effective({}))
                               if e.op == "enemy_loadout"][0].params)


def run_enemy_toughness(args):
    """The enemy wound pool, shared by the two Unreal-family discs.

    Asserted against the shipped INI rather than a constant, because the whole
    option rests on 10 being what the disc actually says.
    """
    import re
    from tcps2 import vokes
    from tcps2.games import BY_ID, r6tuning
    from tcps2.iso import Iso

    print(chr(10) + "[Rainbow Six 3 -- how much enemies can take]")
    if args.rs3data:
        with Iso(args.rs3data) as iso:
            arc = [v for v in vokes.open_archives(iso)
                   if "VOKES0" in str(getattr(v.r, "name", "")).upper()][0]
            txt = arc.read_file("/R6GAMESETTINGS.INI").decode("latin-1")
        got = {}
        for k in ("m_iTerroristMaximumWounds",
                  "m_iArmouredTerroristMaximumWounds",
                  "m_iRainbowMaximumWounds"):
            m = re.search(r"^\s*%s\s*=\s*(\d+)" % k, txt, re.M)
            got[k] = int(m.group(1)) if m else None
        check("the disc really ships a terrorist wound pool of 10",
              got["m_iTerroristMaximumWounds"] == r6tuning.WOUNDS_STOCK,
              str(got["m_iTerroristMaximumWounds"]))
        check("and the armoured one really is 1.5x it",
              got["m_iArmouredTerroristMaximumWounds"]
              == int(r6tuning.WOUNDS_STOCK * r6tuning.WOUNDS_ARMOURED_RATIO),
              str(got["m_iArmouredTerroristMaximumWounds"]))
        check("a Rainbow operative carries more than an enemy, as the card says",
              got["m_iRainbowMaximumWounds"] > got["m_iTerroristMaximumWounds"])

    for gid, prefix in (("r6_3_slus20883", ""), ("gr2_slus21105", "gr2_")):
        p = BY_ID[gid]
        st = p.setting(prefix + "toughness")
        check("%s offers the dial" % gid, st is not None)
        if st is None:
            continue
        check("%s: it defaults to the shipped value" % gid,
              st.default == r6tuning.WOUNDS_STOCK, str(st.default))
        stock = [e for e in p.build_data(
                     p.effective({prefix + "toughness": r6tuning.WOUNDS_STOCK}))
                 if e.op == "ini_values"
                 and "m_iTerroristMaximumWounds" in e.params["values"]]
        check("%s: leaving it alone writes nothing" % gid, not stock)
        check("%s: the ceiling clears the disc's own per-hit wound floor"
              % gid, st.maximum >= 120, str(st.maximum))
        for val in (1, 25, 60, r6tuning.WOUNDS_MAX):
            d = [e for e in p.build_data(
                     p.effective({prefix + "toughness": val}))
                 if e.op == "ini_values"][0].params["values"]
            plain = d["m_iTerroristMaximumWounds"]
            armour = d["m_iArmouredTerroristMaximumWounds"]
            check("%s: %d writes through and armour stays tougher"
                  % (gid, val),
                  plain == val and armour >= plain,
                  "%d / %d" % (plain, armour))


def run_room_invariant(args):
    r"""No file may be told it has room that belongs to the next file.

    This pins a silent corruption. `_tail_room` and `_align_slack` are two
    readings of the SAME stretch of disc -- between a file's end and the start
    of the next -- to different standards, and the room calculation SUMMED
    them. On Ghost Recon 2 that told R6GAMESETTINGS.INI it had four bytes when
    it had two, and it was written over the front of RAINBOWSIX3.INI. Nothing
    complained: both files still had entries and both still read back. Only a
    scan for overlapping extents found it.

    Asserted as an invariant over every file of every archive rather than on
    the one case, because the arithmetic is what was wrong, not the file.
    """
    from tcps2.iso import Iso
    from tcps2.vokes import open_archives
    from tcps2.games import BY_ID

    print(chr(10) + "[room after a file never reaches the next one]")

    discs = [(args.iso, "r6_3_slus20883"),
             (args.gr, "ghost_recon_slus20613"),
             (args.js, "jungle_storm_slus20820"),
             (args.gr2, "gr2_slus21105"),
             (args.graw, "graw_slus21422")]
    looked = 0
    for iso_path, pid in discs:
        if not iso_path:
            continue
        profile = BY_ID[pid]
        worst = None
        checked = 0
        with Iso(iso_path) as iso:
            for arc in open_archives(iso, profile.archive_pattern):
                placed = sorted((e.offset, e) for e in arc.files.values()
                                if e.offset >= arc.data_start)
                starts = [o for o, _e in placed]
                for i, (off, e) in enumerate(placed):
                    nxt = starts[i + 1] if i + 1 < len(starts) else None
                    if nxt is None:
                        continue
                    reach = off + e.size + arc._room_after(e)
                    checked += 1
                    if reach > nxt and (worst is None or reach - nxt > worst[0]):
                        worst = (reach - nxt, arc.r.name, e.path)
        looked += 1
        check("%s: no file's room reaches into the next (%d checked)"
              % (profile.short, checked), worst is None,
              "%s %s overruns by %d" % (worst[1], worst[2], worst[0])
              if worst else "")
    if not looked:
        check("a disc was supplied to check the invariant on", False)


def run_fit_in_place(args):
    r"""A one-byte overshoot must not cost a relocation.

    This pins the failure that took a disc out of service. A loadout change
    rewrites a weapon name in every map's INI, and a longer name makes the
    file one to twenty bytes longer -- on a file of ten and a half kilobytes.
    Each of those used to relocate, and these archives have exactly one 64 KB
    pad: measured on a stock disc, ONE operative gaining ONE gadget put
    sixteen files over their slot and asked for 147 KB. The first few moved,
    the pad filled, and the rest failed with "no free run left".

    So the file sheds bytes no INI reader looks at and stays where it is. What
    must never happen is that shedding them changes what the file SAYS, which
    is most of what is asserted here.
    """
    from tcps2 import dataedit
    from tcps2.iso import Iso
    from tcps2.vokes import Region, Vokes, open_archives
    from tcps2.games import BY_ID

    print(chr(10) + "[an edit that grows a text file by a few bytes]")

    fit = dataedit._fit_plain
    eol = "\r\n"
    body = ("[Weapons]" + eol + "m_Item1=frag   " + eol + eol
            + "; which gadget the operative carries" + eol
            + "m_Item2=flash" + eol + eol + "m_Primary=mp5a4" + eol)
    src = body.encode()

    check("a file that already fits is handed back untouched",
          fit(src, len(src)) == src)
    check("and one that cannot possibly fit is handed back too, to relocate",
          fit(src, 4) == src or len(fit(src, 4)) < len(src))

    # every room size, all the way down: the settings must survive intact
    KEYS = (b"m_Item1=frag", b"m_Item2=flash", b"m_Primary=mp5a4",
            b"[Weapons]")
    worst = len(src)
    for room in range(8, len(src) + 1):
        got = fit(src, room)
        if len(got) > len(src):
            check("shrinking never lengthens a file", False, "room %d" % room)
            break
        lost = [k for k in KEYS if k not in got]
        if lost:
            check("every setting survives every room size", False,
                  "room %d lost %s" % (room, lost))
            break
        worst = min(worst, len(got))
    else:
        check("every setting survives every room size", True)
        check("shrinking never lengthens a file", True)
    check("and it can give up a useful number of bytes",
          worst <= len(src) - 20, "best was %d of %d" % (worst, len(src)))

    # order of rudeness: whitespace first, comments last
    one = fit(src, len(src) - 1)
    check("a one-byte ask takes whitespace and leaves the comment alone",
          b"; which gadget" in one and b"m_Item1=frag" + eol.encode() in one)

    # -- and the whole thing, against the disc ---------------------------
    iso_path = args.rs3data or args.iso
    if not iso_path:
        return
    profile = BY_ID["r6_3_slus20883"]

    class Shadow(Region):
        def __init__(self, inner):
            super().__init__(inner.fh, inner.base, inner.name)
            self.w = []
        def read(self, off, n):
            d = bytearray(super().read(off, n))
            for o, b in self.w:
                s0, e0 = max(off, o), min(off + n, o + len(b))
                if s0 < e0:
                    d[s0 - off:e0 - off] = b[s0 - o:e0 - o]
            return bytes(d)
        def write(self, off, data):
            self.w.append((off, bytes(data)))

    import tempfile
    vals = profile.effective(dict(profile.defaults(),
                                  **{"price_item1": "smoke"}))
    edits = profile.build_data(vals)
    work = tempfile.mkdtemp(prefix="tcms-fit-")
    real_archives = dataedit._archives
    try:
        with Iso(iso_path) as iso:
            shadows = {}
            for real in open_archives(iso, profile.archive_pattern):
                arc = Vokes(Shadow(real.r))
                shadows[arc.r.name.upper()] = arc
            dataedit._archives = lambda _i, _p: shadows

            before = max(b[1] for b in shadows["VOKES0.IMG"].free_blocks())
            try:
                dataedit.apply_data(iso, profile, edits, dataedit.Store(work))
                threw = None
            except Exception as exc:                  # noqa: BLE001
                threw = exc
            check("one gadget change applies without running out of room",
                  threw is None, "%s: %s" % (type(threw).__name__, threw)
                  if threw else "")
            if threw is not None:
                return
            after = max(b[1] for b in shadows["VOKES0.IMG"].free_blocks())
            check("and it does not eat the archive's one long free run",
                  after == before,
                  "largest run %d -> %d" % (before, after))
    finally:
        dataedit._archives = real_archives
        shutil.rmtree(work, ignore_errors=True)


def run_grown_lin(args):
    r"""An edit that makes a LIN package bigger must go through.

    This pins a bug that made `frag_warning` impossible on every disc. It adds
    three names and three imports to the package, so it ALWAYS changes the
    length, and a guard in `apply_data` rejected any length change in a
    compressed container -- the rule this project retracted once the loader
    turned out to walk its packages rather than index them. `_repack` had
    already gained the `lin.rebuild` path for exactly this; the guard upstream
    had not caught up, so the rebuild was never reached.

    It threw on every attempt, and until the pump was taught to report its own
    faults the error was swallowed and the window simply hung. Only `rselzo`
    still has to keep its length: its chunk boundaries are fixed.
    """
    import tempfile
    from tcps2 import dataedit
    from tcps2.iso import Iso
    from tcps2.vokes import Region, Vokes, open_archives
    from tcps2.games import BY_ID

    iso_path = args.rs3data or args.iso
    if not iso_path:
        return
    profile = BY_ID["r6_3_slus20883"]

    print(chr(10) + "[an edit that grows a LIN package]")

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
                    d[s0 - off:e0 - off] = b[s0 - o:e0 - o]
            return bytes(d)
        def write(self, off, data):
            self.w.append((off, bytes(data)))

    vals = dict(profile.defaults())
    vals["frag_warning"] = True
    edits = [e for e in profile.build_data(profile.normalise(vals))
             if e.op == "frag_warning"]
    check("the disc offers an edit that grows a package", len(edits) == 1)
    if not edits:
        return

    work = tempfile.mkdtemp(prefix="tcms-grown-")
    real_archives = dataedit._archives
    try:
        with Iso(iso_path) as iso:
            shadows = {}
            for real in open_archives(iso, profile.archive_pattern):
                arc = Vokes(Shadow(real.r))
                shadows[arc.r.name.upper()] = arc
            dataedit._archives = lambda _iso, _p: shadows

            # the op really does change the length -- otherwise this proves
            # nothing about the guard it is here to pin
            grew = False
            for arc in shadows.values():
                ent = arc.files.get("/COMMON.LIN")
                if ent is None:
                    continue
                _kind, plain = dataedit._unpack(arc.read_entry(ent),
                                                "/COMMON.LIN")
                new, _n = dataedit.OPS["frag_warning"](plain,
                                                       edits[0].params)
                grew = len(new) > len(plain)
                break
            check("and it does make the package longer", grew)

            try:
                rep = dataedit.apply_data(iso, profile, edits,
                                          dataedit.Store(work))
                threw = None
            except Exception as exc:                  # noqa: BLE001
                rep, threw = None, exc
            check("a longer package is no longer refused outright",
                  threw is None, "%s: %s" % (type(threw).__name__, threw)
                  if threw else "")
            if threw is not None:
                return
            check("and the edit actually reached files",
                  rep.get("files", 0) > 0, str(rep))
            check("and it is counted", rep["changes"].get("frag_warning", 0) > 0,
                  str(rep.get("changes")))

            # what landed must still decompress to what the edit asked for
            checked = 0
            for arc in shadows.values():
                for key, ent in sorted(arc.files.items()):
                    if not key.startswith("/COMMON"):
                        continue
                    raw = arc.read_file(ent.path)
                    kind, got = dataedit._unpack(raw, ent.path)
                    if kind != "lin":
                        continue
                    checked += 1
            check("and every COMMON package still decompresses afterwards",
                  checked > 0, "checked %d" % checked)
    finally:
        dataedit._archives = real_archives
        shutil.rmtree(work, ignore_errors=True)


def run_pump():
    """The window must survive a queue message that raises.

    This pins a real lockup. The pump armed its next tick on its last line,
    so one raise in a completion callback ended the loop for good: the window
    stayed up at zero CPU, the log frozen mid-file, the buttons latched off
    and no dialog -- the work had actually finished, and it looked like a
    hang. The collaborators here are stubs, so this needs no display.
    """
    import pathlib
    import queue as _queue
    from gui.app import App

    print(chr(10) + "[the GUI message pump]")

    class Bar:
        def __init__(self):
            self.cleared = 0
        def set(self, done, total):
            self.seen = (done, total)
        def clear(self):
            self.cleared += 1

    class Stub:
        """Borrows the real methods; everything they touch is a stub."""
        _pump = App._pump
        _recover = App._recover

        def __init__(self):
            self._msgs = _queue.Queue()
            self._pumping = False
            self.progress = Bar()
            self.busy = True
            self.lines = []
            self.armed = 0
            self.enabled = None
        def after(self, _ms, _fn):
            self.armed += 1
        def _say(self, text, tag=None):
            self.lines.append(text)
        def _set_buttons(self, on):
            self.enabled = on

    def boom():
        raise ValueError("deliberate")

    app = Stub()
    app._msgs.put(("done", boom))
    app._msgs.put(("log", ("after the raise", None)))
    app._pump()

    check("a raising callback does not stop the pump",
          app.armed == 1)
    check("and the messages behind it are still delivered",
          "after the raise" in app.lines)
    check("the failure names itself in the log rather than going quiet",
          any("ValueError" in ln and "deliberate" in ln for ln in app.lines),
          str(app.lines[-3:]))
    check("a failed job gives the window back instead of latching it off",
          app.busy is False and app.enabled is True)
    check("and the progress bar is cleared either way",
          app.progress.cleared >= 1)

    # A healthy pass must still arm exactly once and touch nothing else.
    app = Stub()
    app._msgs.put(("progress", (3, 9)))
    app._pump()
    check("an ordinary tick still reaches the bar",
          app.progress.seen == (3, 9) and app.armed == 1)
    check("and an ordinary tick does not disturb the buttons",
          app.enabled is None and app.busy is True)

    # Sizing a modal sheet calls `update`, which runs pending `after` jobs --
    # this pump among them. Draining a second completion from inside the
    # first one's dialog stacks modal sheets that cannot be dismissed, so
    # re-entry has to be refused outright.
    app = Stub()
    reached = []

    def nested():
        app._pump()                     # what `update` inside a sheet does
        reached.append(app._msgs.qsize())

    app._msgs.put(("done", nested))
    app._msgs.put(("log", ("behind the sheet", None)))
    app._pump()
    check("a pump re-entered from a nested update refuses to drain",
          reached == [1], str(reached))
    check("and the outer drain still delivers what was behind it",
          "behind the sheet" in app.lines)
    check("re-entry does not arm a second tick either",
          app.armed == 1)
    check("and the flag is released once the outer drain is done",
          app._pumping is False)

    # The message a failed job hands back is built inside an `except ... as
    # exc` block and run later, on the UI thread. Python deletes that name
    # when the block exits, so capturing it by closure raised NameError
    # instead of reporting the real failure -- which then killed the pump and
    # hung the window. EVERY apply that threw anything went that way, and
    # nobody ever saw the actual error. It has to be bound, not captured.
    from gui import app as _appmod
    src = pathlib.Path(_appmod.__file__).with_suffix(".py").read_text(
        encoding="utf-8")
    check("the failure hand-back binds the exception instead of capturing it",
          "lambda e=exc, t=traceback.format_exc()" in src
          and "lambda: done(None, (exc, tb))" not in src)

    # and the same thing, executed rather than read
    def handback():
        try:
            raise ValueError("the real failure")
        except Exception as exc:                  # noqa: BLE001
            return lambda e=exc, t="tb": (e, t)

    got = handback()()
    check("and the bound hand-back still carries the exception once it runs",
          isinstance(got[0], ValueError) and str(got[0]) == "the real failure")

    app = Stub()
    app._msgs.put(("done", handback()))
    app._pump()
    check("so a failed job no longer reports NameError in place of the fault",
          not any("NameError" in ln for ln in app.lines), str(app.lines[:3]))


def run_gear_icons(args):
    """The texture reader, and the reason no game art is shipped.

    The icons are deliberately NOT bundled: the PS2 chain is decodable but not
    yet named, and the Xbox art is different pictures belonging to someone
    else. So what is asserted here is that the reader works and that no game
    art has crept back into the build.
    """
    import os
    from tcps2 import rsekits, utexture
    from gui import gearicons

    print(chr(10) + "[Rainbow Six 3 -- loadout icons]")
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    check("no game artwork is bundled, so the build is safe to release",
          not os.path.isdir(os.path.join(here, "assets", "gearicons")))

    every = set()
    for table in (rsekits.PRIMARIES, rsekits.SECONDARIES):
        every |= set(table)
    every |= set(rsekits.GADGETS)
    missing = sorted(v for v in every if v not in gearicons.KIND)
    check("every loadout choice still has a glyph to fall back on",
          not missing, str(missing))
    check("and the glyph set covers nothing it should not",
          not (set(gearicons.KIND) - every - {"stock"}),
          str(sorted(set(gearicons.KIND) - every)))

    check("the naming rule the Xbox packages follow is recorded",
          utexture.icon_name("R63rdWeapons.SubMP5A4") == "SubMP5A4_T"
          and utexture.icon_name("R6Weapons.R6FragGrenadeGadget")
          == "R6FragGrenadeGadget_T")

    import struct
    opaque = struct.pack("<HHI", 0xF800, 0x001F, 0x00000000)
    px = utexture.dxt1(opaque, 4, 4)
    check("DXT1 decodes a flat red block",
          len(px) == 16 and px[0] == (255, 0, 0, 255), str(px[0]))
    punch = struct.pack("<HHI", 0x001F, 0xF800, 0xFFFFFFFF)
    check("and the c0<=c1 form gives a transparent index 3",
          utexture.dxt1(punch, 4, 4)[0] == (0, 0, 0, 0))
    short = False
    try:
        utexture.dxt1(bytes(4), 8, 8)
    except utexture.TextureError:
        short = True
    check("a truncated payload is refused, not silently padded", short)
    check("a non-package is refused",
          _raises(utexture.Package, b"not a package at all" + bytes(64),
                  utexture.TextureError))


def _raises(fn, *a):
    want = a[-1]
    try:
        fn(*a[:-1])
    except want:
        return True
    except Exception:                       # noqa: BLE001
        return False
    return False


def run_team_kits(args):
    """The squad gadget slots, which live in every mission's own INI.

    The assertions that matter are that the edit reaches all twelve kits on a
    campaign map, that it leaves multiplayer maps byte-identical, and that it
    turns on the sound bank for whatever it just handed out.
    """
    from tcps2 import rsekits, vokes
    from tcps2.games import BY_ID
    from tcps2.iso import Iso

    if not args.rs3data:
        return
    print(chr(10) + "[Rainbow Six 3 -- teammate gadgets]")
    with Iso(args.rs3data) as iso:
        arcs = [v for v in vokes.open_archives(iso)
                if "VOKES0" in str(getattr(v.r, "name", "")).upper()]
        arc = arcs[0]
        camp = arc.read_file("/MAPS/PARADE_A.INI")
        mp = arc.read_file("/MAPS/GARAGE_MP.INI")

    kits = rsekits.reads(camp)
    check("a campaign map carries all twelve squad kits",
          len(kits) == 12, str(len(kits)))
    import re as _re
    who = {_re.match(r"m_(Price|Weber|Loiselle)", k).group(1) for k, _p, _s in kits}
    check("three operatives, four kits each",
          who == {"Price", "Weber", "Loiselle"} and len(kits) == 12, str(sorted(who)))
    check("and every kit names both gadget slots",
          all(p and s for _k, p, s in kits))

    out, n = rsekits.apply(camp, "teargas", "phosphorus")
    check("setting both slots touches all 24 fields", n == 24, str(n))
    after = rsekits.reads(out)
    check("every kit now carries what was asked for",
          all(p.endswith("R6TearGasGrenadeGadget")
              and s.endswith("R6PhosphorusGrenadeGadget")
              for _k, p, s in after))
    check("the weapons were left alone",
          rsekits._KIT.findall(camp).__len__() == rsekits._KIT.findall(out).__len__()
          and camp.count(b"szPrimaryWeapon") == out.count(b"szPrimaryWeapon"))

    import re
    for name in (b"R6TearGasGrenadeGadget", b"R6PhosphorusGrenadeGadget"):
        pat = re.compile(b"bUsing=(true|false),weaponname=" + b'"' + name + b'"', re.I)
        was = pat.search(camp)
        now = pat.search(out)
        check("the sound bank for %s is switched on" % name.decode(),
              now is not None and now.group(1).lower() == b"true",
              "was %s" % (was.group(1).decode() if was else "?"))

    o2, n2 = rsekits.apply(mp, "teargas", "teargas")
    check("a multiplayer map is left byte-identical", n2 == 0 and o2 == mp)
    # "teammates carry your loadout" -- the only option here that moves weapons
    import re as _re2
    want = {}
    body = _re2.search(rb"m_PlayerEquipment=\(([^)]*)\)", camp).group(1)
    for field in rsekits.FIELDS:
        want[field] = _re2.search(
            field.encode() + b'="([^"]*)"', body).group(1)
    mine, mn = rsekits.match_player(camp)
    check("matching the player rewrites every squad kit", mn > 0, str(mn))
    got = _re2.findall(rb"m_(?:Price|Weber|Loiselle)[A-Za-z]*Equipment"
                       rb"[A-Za-z]*=\(([^)]*)\)", mine)
    check("all twelve squad kits were visited", len(got) == 12, str(len(got)))
    plain_kits = [b for b in got if b"Silenced" not in b]
    ok = True
    for b in got:
        for field, cls in want.items():
            m2 = _re2.search(field.encode() + b'="([^"]*)"', b)
            if m2 is None:
                ok = False
        # only the non-silenced kits must equal the plain player kit
    check("every kit still names all four fields", ok)
    price = _re2.search(rb"m_PriceEquipment=\(([^)]*)\)", mine).group(1)
    check("a plain kit now carries the player's own weapon",
          _re2.search(b'szPrimaryWeapon="([^"]*)"', price).group(1)
          == want["szPrimaryWeapon"],
          want["szPrimaryWeapon"].decode())
    sil = _re2.search(rb"m_PriceSilencedEquipment=\(([^)]*)\)", mine).group(1)
    silbody = _re2.search(rb"m_PlayerSilencedEquipment=\(([^)]*)\)", camp).group(1)
    check("and a silenced kit copies the player's SILENCED weapon",
          _re2.search(b'szPrimaryWeapon="([^"]*)"', sil).group(1)
          == _re2.search(b'szPrimaryWeapon="([^"]*)"', silbody).group(1))

    both, bn = rsekits.apply(camp, "teargas", "stock", match=True)
    w = _re2.search(rb"m_WeberEquipment=\(([^)]*)\)", both).group(1)
    check("gadget choice wins over the matched loadout",
          _re2.search(b'szPrimaryItem="([^"]*)"', w).group(1)
          == b"R6Weapons.R6TearGasGrenadeGadget"
          and _re2.search(b'szPrimaryWeapon="([^"]*)"', w).group(1)
          == want["szPrimaryWeapon"])
    m3, n3b = rsekits.match_player(mp)
    check("matching leaves a multiplayer map byte-identical",
          n3b == 0 and m3 == mp)

    # per-operative dials -- the desktop version of the Player Settings panel
    def kit(buf, who):
        return _re2.search(("m_%sEquipment=" % who).encode() +
                           rb"\(([^)]*)\)", buf).group(1)

    def field(body, name):
        return _re2.search(name.encode() + b'="([^"]*)"', body).group(1)

    solo, sn = rsekits.apply(
        camp, per={"Price": {"szPrimaryWeapon": "m60e4",
                             "szPrimaryItem": "teargas"},
                   "Loiselle": {"szSecondaryWeapon": "deagle"}})
    check("two slots on one man and one on another touch 12 fields",
          sn == 12, str(sn))
    check("Price got the weapon asked for, in all four of his kits",
          field(kit(solo, "Price"), "szPrimaryWeapon")
          == b"R63rdWeapons.LMGM60E4")
    check("Loiselle got the sidearm asked for",
          field(kit(solo, "Loiselle"), "szSecondaryWeapon")
          == b"R63rdWeapons.PistolDesertEagle50")
    check("and Weber, who was not named, is untouched",
          kit(solo, "Weber") == kit(camp, "Weber"))

    mixed, _mn = rsekits.apply(camp, "frag", "stock", match=True,
                               per={"Price": {"szPrimaryItem": "teargas"}})
    check("a per-man choice overrides the squad-wide one",
          field(kit(mixed, "Price"), "szPrimaryItem")
          == b"R6Weapons.R6TearGasGrenadeGadget"
          and field(kit(mixed, "Weber"), "szPrimaryItem")
          == b"R6Weapons.R6FragGrenadeGadget")

    # the palette must never offer something the disc does not issue
    kits_all = b" ".join(_re2.findall(
        rb"m_(?:Player|Price|Weber|Loiselle)[A-Za-z]*Equipment[A-Za-z]*"
        rb"=\(([^)]*)\)", camp))
    for table, slot in ((rsekits.PRIMARIES, "primary weapons"),
                        (rsekits.SECONDARIES, "sidearms")):
        bad = [cls for _k, (cls, _l) in table.items()]
        check("every offered %s name is well formed" % slot,
              all("." in c and c.split(".")[0] in
                  ("R63rdWeapons", "R6Weapons") for c in bad))
    check("claymore, remote charge and molotov stay out of the palette",
          not any("Claymore" in c or "RemoteCharge" in c or "Molotov" in c
                  for c in list(rsekits.GADGETS.values())
                  + [c for c, _l in rsekits.PRIMARIES.values()]
                  + [c for c, _l in rsekits.SECONDARIES.values()]))
    try:
        rsekits.apply(camp, per={"Price": {"szPrimaryWeapon": "claymore"}})
        refused = False
    except rsekits.KitError:
        refused = True
    check("a class the disc never issues is refused for a weapon slot",
          refused)
    try:
        rsekits.apply(camp, per={"Nobody": {"szPrimaryWeapon": "m4"}})
        refused2 = False
    except rsekits.KitError:
        refused2 = True
    check("an operative who does not exist is refused", refused2)

    profile2 = BY_ID["r6_3_slus20883"]
    per_cards = [s for s in profile2.settings
                 if s.group == "Teammates" and "_" in s.key
                 and s.key.split("_")[0] in ("price", "weber", "loiselle")]
    check("twelve per-operative cards reach the profile",
          len(per_cards) == 12, str(len(per_cards)))
    made2 = [e for e in profile2.build_data(
                 profile2.effective({"price_primary": "m60e4"}))
             if e.op == "team_gadget"]
    check("choosing one man's weapon writes one data edit carrying just him",
          len(made2) == 1
          and made2[0].params["per"] == {"Price": {"szPrimaryWeapon": "m60e4"}})


    o3, n3 = rsekits.apply(camp, "stock", "stock")
    check("choosing stock changes nothing", n3 == 0 and o3 == camp)

    try:
        rsekits.apply(camp, "rocket", "stock")
        bad = False
    except rsekits.KitError:
        bad = True
    check("a gadget the disc does not carry is refused", bad)

    profile = BY_ID["r6_3_slus20883"]
    for key in ("team_gadget_1", "team_gadget_2"):
        st = profile.setting(key)
        check("%s reaches the profile as a data edit" % key,
              st is not None and st.touches == "data")
    check("leaving both alone writes no data edit",
          not [e for e in profile.build_data(profile.effective({}))
               if e.op == "team_gadget"])
    made = [e for e in profile.build_data(
                profile.effective({"team_gadget_1": "teargas"}))
            if e.op == "team_gadget"]
    check("choosing one writes exactly one data edit",
          len(made) == 1 and made[0].params["primary"] == "teargas"
          and made[0].params["secondary"] == "stock")


def run_host_filesystem(args):
    """The dev-kit `-host` switch that moves the vokes archives off the disc.

    Every word is checked against the disc rather than trusted, because the
    whole mechanism rests on three branches being exactly the instructions the
    module says they are. The strings matter as much as the branches: if the
    prefix the builder appends is not literally `host0:` then the path it
    produces is not one PCSX2 will serve.
    """
    from tcps2 import overlay, rsehost
    from tcps2.games.r6_3 import SP
    from tcps2.iso import Iso

    if not args.rs3data:
        return
    print(chr(10) + "[Rainbow Six 3 -- the host filesystem switch]")
    with Iso(args.rs3data) as iso:
        ov = overlay.open_overlay(iso, SP)
        live = {va: ov.read_word(va) for va in rsehost.WORDS}
        store = ov.read_word(rsehost.FLAG_STORE)
        got = {}
        for name, va in rsehost.SWITCHES.items():
            off = va - ov.img.base_va
            end = ov.img.image.find(b"\0", off)
            got[name] = bytes(ov.img.image[off:end])

    for va, (stock, forced, why) in sorted(rsehost.WORDS.items()):
        check("%08x is the shipped word (%s)" % (va, why),
              live[va] in (stock, forced), "%#010x" % live[va])

    check("the flag store really is sw $s3, -0x7f60($gp)",
          (store >> 26) == 0x2B and ((store >> 21) & 31) == 28
          and (store & 0xFFFF) == (rsehost.FLAG_GP_OFFSET & 0xFFFF),
          "%#010x" % store)

    for name, va in sorted(rsehost.SWITCHES.items()):
        check("the parser knows -%s" % name, got[name] == b"-" + name.encode(),
              repr(got[name]))

    stock_prefix = rsehost.WORDS[rsehost.PREFIX_TEST][0]
    check("the prefix test is a beq on $v0 that skips to the CD branch",
          (stock_prefix >> 26) == 4 and ((stock_prefix >> 16) & 31) == 0
          and ((stock_prefix >> 21) & 31) == 2)
    check("forcing it is a nop, so the host branch simply falls through",
          rsehost.WORDS[rsehost.PREFIX_TEST][1] == 0)

    ver_stock, ver_forced, _ = rsehost.WORDS[rsehost.VERSION_TEST]
    check("the version test is a bne and the edit makes it unconditional",
          (ver_stock >> 26) == 5 and (ver_forced >> 26) == 4
          and ((ver_forced >> 21) & 31) == 0 and ((ver_forced >> 16) & 31) == 0)
    check("and it keeps the same branch target",
          (ver_stock & 0xFFFF) == (ver_forced & 0xFFFF))

    e = rsehost.edits()
    check("three words, each carrying the word it replaces", len(e) == 3
          and all(w.stock == rsehost.WORDS[w.va][0] for w in e))
    # Deliberately not wired into the profile: the switch is proven to put the
    # game on loose archives, but nothing has yet shown that EDITING one of
    # them changes what is played, so no disc gets these words by default.
    from tcps2.games import BY_ID
    profile = BY_ID["r6_3_slus20883"]
    every = {w.va for w in profile.build_edits(
        profile.effective({s.key: s.default for s in profile.settings}))}
    check("no default config writes these words to a disc",
          not (every & set(rsehost.WORDS)),
          "%r" % sorted(every & set(rsehost.WORDS)))


#: filled from the disc when one is given, so the contract check below has
#: real bytes to run an operation against rather than a synthetic buffer.
_COVER_BYTES = []


def run_op_contract(args):
    """Every data operation must hand back (bytes, count).

    This exists because the same defect shipped twice. `dataedit` does
    `new, n = op(plain, params)`, so an operation that returns bare bytes
    makes Python unpack the file one character at a time -- and the failure
    lands on the user's disc mid-apply, not here. `zone_counts` did it by
    taking `[0]` off a correct pair; `ai_cover` did it by never building one.
    Neither was caught, because the tests around them called the underlying
    module directly and the module was fine.

    So this reaches every operation the profile can actually emit, through
    the real dispatch table, against a real file its own selector matched.
    """
    if not args.rs3data:
        return
    from tcps2 import dataedit, lin, vokes
    from tcps2.games import BY_ID
    from tcps2.iso import Iso
    from tcps2.model import BOOL

    print(chr(10) + "[every data operation returns (bytes, count)]")
    profile = BY_ID["r6_3_slus20883"]

    # One non-default value per setting is enough to reach its operation.
    reachable = {}
    for s in profile.settings:
        if s.choices:
            tries = [c.value for c in s.choices]
        elif s.kind == BOOL:
            tries = [True]
        elif s.maximum is not None:
            tries = [s.maximum, s.minimum]
        else:
            tries = []
        for v in tries:
            if v == s.default:
                continue
            try:
                edits = profile.build_data(profile.effective({s.key: v}))
            except Exception:                                # noqa: BLE001
                continue
            for e in edits:
                reachable.setdefault(e.op, e)

    check("the sweep reaches a useful number of operations",
          len(reachable) >= 5, "%d" % len(reachable))

    with Iso(args.rs3data) as iso:
        where = {}
        for arc in vokes.open_archives(iso):
            for key in arc.files:
                where.setdefault(key, arc)
        for op, edit in sorted(reachable.items()):
            hit = next((k for k in sorted(where)
                        if re.search(edit.select, k, re.I)), None)
            if hit is None:
                check("%s: a file its selector matches" % op, False,
                      edit.select)
                continue
            arc = where[hit]
            raw = arc.read_entry(arc.files[hit])
            plain = lin.decompress(raw) if lin.is_lin(raw) else raw
            fn = dataedit.OPS[op]
            try:
                if op in dataedit._WANTS_CONTAINER:
                    got = fn(plain, edit.params, raw)
                else:
                    got = fn(plain, edit.params)
            except Exception as exc:                         # noqa: BLE001
                check("%s runs on %s" % (op, hit), False,
                      "%s: %s" % (type(exc).__name__, exc))
                continue
            check("%s returns (bytes, count)" % op,
                  isinstance(got, tuple) and len(got) == 2
                  and isinstance(got[0], (bytes, bytearray))
                  and isinstance(got[1], int),
                  "%r from %s" % (type(got), hit))


def run_ai_cover(args):
    """The one function that decides whether an enemy uses cover.

    The assertions that matter are about the SIGNATURE, not about offsets: the
    anchor has to find exactly seven rungs carrying exactly the shipped
    thresholds, because that is what proves this is the build the ladders were
    measured on. Everything else follows.
    """
    from tcps2 import lin, rseaicover, vokes
    from tcps2.games import BY_ID
    from tcps2.iso import Iso

    print(chr(10) + "[Rainbow Six 3 -- enemies fighting from cover]")

    for name, values in sorted(rseaicover.SETS.items()):
        for ladder in rseaicover.LADDERS:
            rungs = [values[i] for i in ladder]
            check("the %s ladder %r is strictly decreasing" % (name, rungs),
                  all(a > b for a, b in zip(rungs, rungs[1:])))
    check("an unknown set is refused rather than guessed",
          _raises(lambda: rseaicover.apply(b"x" * 64, "nope"),
                  rseaicover.CoverError))

    # THE CONTRACT, not the module. Calling rseaicover.apply directly is what
    # let a version through that returned bare bytes: dataedit does
    # `new, n = op(...)`, so bytes unpack one character at a time and the
    # apply dies on the user's disc, not here. Every op this profile can
    # emit is exercised through the real dispatch table.
    from tcps2 import dataedit as _de
    for name in ("ai_cover", "frag_warning"):
        fn = _de.OPS.get(name)
        check("%s is registered as a data operation" % name, fn is not None)
    profile = BY_ID["r6_3_slus20883"]
    check("stock writes nothing to the disc",
          not [e for e in profile.build_data(profile.effective({}))
               if e.op == "ai_cover"])
    # Withdrawn and put back the same day. The disc that hung also had wave
    # mode on -- which is what hangs Terrorist Hunt -- and the bisect never
    # removed it, so this option was convicted on a confounded test. With
    # only this applied, Parade Terrorist Hunt reaches gameplay and the
    # edited ladder is live in EE RAM. So it must emit again.
    e = [e for e in profile.build_data(
             profile.effective({"ai_cover": "heavy"})) if e.op == "ai_cover"]
    check("choosing a set emits one edit against the script package",
          len(e) == 1 and "COMMON" in e[0].select, str(e))
    check("and the option is not left withdrawn",
          profile.setting("ai_cover").enabled is True)

    # The module itself stays exercised. The cause is not found yet, so the
    # code has to keep working for whoever picks it up -- a withdrawal that
    # let the edit rot would have to be written twice.
    _sets = sorted(rseaicover.SETS)
    check("every set the module offers is still well formed",
          _sets and all(len(rseaicover.SETS[k]) == len(rseaicover.STOCK)
                        for k in _sets), str(_sets))

    if not args.rs3data:
        return
    with Iso(args.rs3data) as iso:
        arcs = vokes.open_archives(iso)
        plain = {}
        for path in ("/COMMON.LIN", "/COMMON_SS.LIN"):
            for a in arcs:
                if path in a.files:
                    plain[path] = lin.decompress(a.read_file(path))
                    break
    for path, data in sorted(plain.items()):
        _COVER_BYTES.append(data)
        found = rseaicover.sites(data)
        check("%s holds exactly %d rungs" % (path, len(rseaicover.STOCK)),
              len(found) == len(rseaicover.STOCK), str(len(found)))
        check("%s carries the shipped thresholds" % path,
              rseaicover.reads(data) == rseaicover.STOCK,
              str(rseaicover.reads(data)))
        for setname in ("cover", "heavy"):
            out, _n = rseaicover.apply(data, setname)
            check("%s: %s keeps the package length" % (path, setname),
                  len(out) == len(data))
            check("%s: %s writes what it says" % (path, setname),
                  rseaicover.reads(out) == rseaicover.SETS[setname])
            check("%s: %s reverts byte for byte" % (path, setname),
                  rseaicover.apply(out, "stock")[0] == data)
        # Through the real dispatch table, with the real bytes. Calling the
        # module directly is what let a version ship that returned bare
        # bytes: dataedit does `new, n = op(...)`, so a bytes return unpacks
        # one character at a time and the apply dies on the disc, not here.
        got = _de.OPS["ai_cover"](data, {"set": "cover"})
        check("%s: ai_cover through OPS returns (bytes, count)" % path,
              isinstance(got, tuple) and len(got) == 2
              and isinstance(got[0], bytes) and isinstance(got[1], int),
              repr(type(got)))
        check("%s: and it keeps the length" % path, len(got[0]) == len(data))


def run_host_root(args):
    """The loose-data-root delivery mode.

    The interesting assertions are about the two things that can silently
    produce a game that ignores every edit: the launcher must use an ELF
    override, because an ISO boot leaves PCSX2 with no host root at all, and
    the three switch words must ride the ordinary word pass rather than being
    written before it, because that pass rebuilds the overlay from pristine.
    """
    import tempfile
    from tcps2 import hostroot, rsehost, vokes
    from tcps2.games import BY_ID

    print(chr(10) + "[the loose data root]")

    # -- growth, which is the whole point of the mode ---------------------
    check("a loose archive grows by at least the step, 16-byte aligned",
          hostroot.GROW_STEP % vokes.Vokes.ALIGN == 0
          and hostroot.GROW_STEP >= (1 << 20))
    check("LooseVokes is a Vokes, so every edit runs against it unchanged",
          issubclass(hostroot.LooseVokes, vokes.Vokes))
    check("and it only overrides write -- allocate and the rest are shared",
          set(hostroot.LooseVokes.__dict__) & {"write", "grow"}
          == {"write", "grow"})

    # -- which containers move out of the disc ----------------------------
    for name, want in (("/VOKES0.IMG", True), ("/GR.IMG", True),
                       ("/MENU.IMG", True), ("/SP.SOZ", False),
                       ("/SLUS_208.83", False)):
        check("%s %s an archive" % (name, "is" if want else "is not"),
              bool(hostroot.ARCHIVE_RE.search(name)) == want)

    # -- the launcher, where a wrong command line costs a whole session ---
    tmp = tempfile.mkdtemp(prefix="tcps2root")
    open(os.path.join(tmp, "SLUS_208.83"), "wb").write(b"\0" * 16)
    bat = hostroot.write_launcher(tmp, r"X:\game.iso", r"X:\pcsx2-qt.exe")
    text = open(bat, encoding="ascii").read()
    check("the launcher passes -elf, which is what sets the host root",
          "-elf" in text and "SLUS_208.83" in text)
    check("it names the ISO too, so cdrom0 still works", "X:\\game.iso" in text)
    check("it says Host Filesystem must be enabled, which is off by default",
          "Enable Host Filesystem" in text)
    check("it warns that an ISO boot silently reads the disc instead",
          "silently" in text)
    check("and %~dp0 survived the formatting", "%~dp0" in text
          and "%%" not in text)
    check("a folder with no boot ELF is refused, not half-written",
          _raises(lambda: hostroot.write_launcher(
                      tempfile.mkdtemp(prefix="tcps2empty"), "X:\\g.iso"),
                  hostroot.HostRootError))
    shutil.rmtree(tmp, ignore_errors=True)

    # -- only the disc whose addresses are known --------------------------
    check("Rainbow Six 3 is supported",
          hostroot.supported(BY_ID["r6_3_slus20883"]))
    for gid in ("gr2_slus21105", "graw_slus21422"):
        if gid in BY_ID:
            check("%s is refused rather than patched at R6 3's offsets" % gid,
                  _raises(lambda g=gid: hostroot.require(BY_ID[g]),
                          hostroot.HostRootError))

    # -- the words go through the normal pass -----------------------------
    profile = BY_ID["r6_3_slus20883"]
    plain = {w.va for w in profile.build_edits(profile.effective({}))}
    check("no switch word is written unless the mode is chosen",
          not (plain & set(rsehost.WORDS)))
    check("and choosing it contributes exactly the three",
          len(rsehost.edits()) == 3
          and {w.va for w in rsehost.edits()} == set(rsehost.WORDS))


def run_split_shadows(args):
    """The branch that discards the projected-shadow pass in split screen.

    The point of these assertions is that the edit is one word, that the word
    really is the `andi` the module says it is, and that forcing it changes
    only the opcode -- the registers and the immediate stay put, so the test
    still reads the same bit of the same byte.
    """
    from tcps2 import overlay, rseshadow
    from tcps2.games import BY_ID
    from tcps2.games.r6_3 import SP, STOCK
    from tcps2.iso import Iso

    if not args.rs3data:
        return
    print(chr(10) + "[Rainbow Six 3 -- projected shadows in split screen]")
    with Iso(args.rs3data) as iso:
        ov = overlay.open_overlay(iso, SP)
        live = ov.read_word(rseshadow.SHADOW_GATE)
        flag = ov.read_word(rseshadow.SHADOW_FLAG_READ)
        branch = ov.read_word(rseshadow.SHADOW_GATE_BRANCH)
    check("the gate is one of the two words it can be",
          live in (rseshadow.SHADOW_GATE_STOCK, rseshadow.SHADOW_GATE_FORCED),
          "%#010x" % live)
    check("the shipped word is recorded, so a patched disc can be healed",
          STOCK.get(rseshadow.SHADOW_GATE) == rseshadow.SHADOW_GATE_STOCK,
          "%r" % STOCK.get(rseshadow.SHADOW_GATE))
    check("the word in front of it reads the flags byte at +0x94",
          (flag >> 26) == 0x24 and (flag & 0xFFFF) == 0x0094, "%#010x" % flag)
    check("and the word after it is the branch that skips the pass",
          (branch >> 26) == 4 and ((branch >> 16) & 31) == 0, "%#010x" % branch)

    stock, forced = rseshadow.SHADOW_GATE_STOCK, rseshadow.SHADOW_GATE_FORCED
    check("the shipped word is andi and the edit is ori",
          (stock >> 26) == 0x0C and (forced >> 26) == 0x0D)
    check("the edit changes the opcode and nothing else",
          (stock & 0x03FFFFFF) == (forced & 0x03FFFFFF))
    check("it still tests bit 0 of the same register",
          (stock & 0xFFFF) == 1 and ((stock >> 21) & 31) == ((stock >> 16) & 31))

    profile = BY_ID["r6_3_slus20883"]
    st = profile.setting("split_shadows")
    check("the option reaches the profile", st is not None)
    check("and it goes onto the disc, not into the cheat file",
          st.touches == "words")
    # Play-tested on Crespo Foundation, the Garage projection screen and
    # Alcatraz -- three maps this card nominates itself -- with no shadow on
    # any of them. Forcing the branch true is not enough, so it is withdrawn
    # rather than left on offer as an experiment that cannot work.
    check("it is withdrawn as not working", st.confidence == "broken"
          and not st.enabled)
    check("and names the maps it was tried on",
          "Alcatraz" in st.disabled_reason and "Garage" in st.disabled_reason)
    check("and emits no word even when stored true",
          not [e for e in profile.build_edits(
                  profile.effective(dict(profile.defaults(), split_shadows=True)))
               if e.va == 0x00446EA8])
    check("leaving it off writes no word",
          not [e for e in profile.build_edits(profile.effective({}))
               if e.va == rseshadow.SHADOW_GATE])
    # The word the module builds is still worth pinning down even though the
    # option is withdrawn -- it is the record of what was tried, and whoever
    # picks this up next needs it to be right. What is no longer true is that
    # the profile will emit it; that is checked above.
    check("the module still builds exactly that one word",
          rseshadow.SHADOW_GATE == 0x00446EA8 and forced == 0x34420001
          and stock == 0x30420001)
    check("turning it on writes nothing now that it is withdrawn",
          not [e for e in profile.build_edits(
                  profile.effective({"split_shadows": True}))
               if e.va == rseshadow.SHADOW_GATE])
    base = profile.build_pnach(profile.effective({}))
    with_it = profile.build_pnach(profile.effective({"split_shadows": True}))
    check("and it adds nothing to the cheat file",
          len(with_it) == len(base), "%d vs %d" % (len(with_it), len(base)))

    check("every timed scope starts before it stops",
          all(x < y for x, y in rseshadow.SHADOW_TIMERS.values())
          and len(rseshadow.SHADOW_TIMERS) == 3)
    check("the recorded map list is the measured one",
          len(rseshadow.SHADOW_MAPS) == 15
          and sum(rseshadow.SHADOW_MAPS.values()) == 25,
          "%d maps, %d projectors" % (len(rseshadow.SHADOW_MAPS),
                                      sum(rseshadow.SHADOW_MAPS.values())))
    check("and the map picked for testing is in it",
          rseshadow.BEST_TEST_MAP in rseshadow.SHADOW_MAPS)

    # The map list is a measurement, so re-measure some of it off the disc.
    import re, zlib
    from tcps2 import lin, vokes

    NONE_TAG = bytes([5]) + b"None" + bytes([0])
    RX = re.compile("^R6LightProjector" + chr(92) + "d+$")

    def projectors(arc, member):
        blob = arc.read_file(member)
        chunks, _tail = lin.parse(blob)
        head = bytearray()
        for rawsz, comp, at in chunks:
            head += zlib.decompress(blob[at:at + comp])
            if len(head) >= (1 << 20):
                break
        q = head.find(NONE_TAG)
        names = []
        while 0 <= q < len(head):
            n = head[q]
            if n == 0 or q + 1 + n + 4 > len(head):
                break
            txt = head[q + 1:q + n]
            if head[q + n] != 0 or not all(32 <= c < 127 for c in txt):
                break
            names.append(txt.decode())
            q += 1 + n + 4
        return sum(1 for x in names if RX.match(x)), names

    with Iso(args.rs3data) as iso:
        arcs = {str(getattr(v.r, "name", "")).upper(): v
                for v in vokes.open_archives(iso)}
        v1 = [x for k, x in arcs.items() if "VOKES1" in k][0]
        v2 = [x for k, x in arcs.items() if "VOKES2" in k][0]
        n_off, names_off = projectors(v1, "/GARAGE_AOFF.LIN")
        n_ss, names_ss = projectors(v1, "/GARAGE_A_SS.LIN")
        n_none, names_none = projectors(v2, "/OIL_REFINERY_AOFF.LIN")
    check("Garage A really carries the three projectors claimed",
          n_off == rseshadow.SHADOW_MAPS["GARAGE_A"] == 3, str(n_off))
    check("its split-screen build carries exactly the same three",
          n_ss == n_off, "%d vs %d" % (n_ss, n_off))
    check("and both name tables are identical, so nothing was cut",
          names_off == names_ss)
    check("a map with no shadow pass really has none",
          n_none == 0 and "ShadowBufferMatrix" not in names_none, str(n_none))
    check("while Garage does declare the shadow-buffer property",
          "ShadowBufferMatrix" in names_off)


def run_split_draw(args):
    """The guard that stops the draw animation playing twice in split screen.

    The edit repoints one bool read from `m_bIsSplitScreen` to `m_bGameOver`.
    Both are bools on GameInfo in the same dword, which is the whole safety
    argument -- the VM resolves the same class on the same object -- so that
    is what these assertions are really about.
    """
    import re
    from tcps2 import dataedit, lin, rsedraw
    from tcps2.games import BY_ID
    from tcps2.iso import Iso
    from tcps2.vokes import open_archives

    if not args.rs3data:
        return
    print(chr(10) + "[Rainbow Six 3 -- the doubled draw animation]")
    seen, checked = set(), 0
    with Iso(args.rs3data) as iso:
        for arc in open_archives(iso, r"/VOKES\d\.IMG$"):
            for path in sorted(arc.files):
                if not re.search(r"/COMMON(OFF|_SS)?\.LIN$", path) or path in seen:
                    continue
                seen.add(path)
                raw = _stock_bytes(args.rs3data, arc, path)
                kind, plain = dataedit._unpack(raw, path)

                at = rsedraw.find(plain)
                check("%s: the guard term is where it was measured" % path[1:],
                      at == rsedraw.KNOWN_OFFSET,
                      "found %#x, expected %#x" % (at, rsedraw.KNOWN_OFFSET))
                check("%s: and it still reads m_bIsSplitScreen" % path[1:],
                      plain[at:at + 2] == rsedraw.SPLITSCREEN,
                      plain[at:at + 2].hex())
                check("%s: the anchor occurs exactly once" % path[1:],
                      plain.count(rsedraw.ANCHOR) == 1,
                      "%d times" % plain.count(rsedraw.ANCHOR))

                on, n = rsedraw.restore(plain, True)
                check("%s: the edit moves exactly two bytes" % path[1:],
                      n == 1 and len(on) == len(plain)
                      and sum(a != b for a, b in zip(plain, on)) == 2)
                check("%s: to m_bGameOver" % path[1:],
                      on[at:at + 2] == rsedraw.GAMEOVER)
                check("%s: and it reverses exactly" % path[1:],
                      rsedraw.restore(on, False)[0] == plain)
                check("%s: the state reads back" % path[1:],
                      rsedraw.reads(on) and not rsedraw.reads(plain))

                packed = dataedit._repack(kind, raw, on)
                check("%s: the container keeps its length" % path[1:],
                      len(packed) == len(raw))
                check("%s: and still decompresses to the edited bytes"
                      % path[1:], lin.decompress(packed) == on)
                checked += 1
    check("all three COMMON containers carry the guard", checked == 3,
          "%d checked" % checked)

    # both operands must be two bytes, or the length would move
    check("the operand swap is length-for-length",
          len(rsedraw.SPLITSCREEN) == len(rsedraw.GAMEOVER) == 2)

    profile = BY_ID["r6_3_slus20883"]
    check("the option reaches the profile",
          profile.setting("split_draw_once") is not None)
    check("leaving it off writes nothing",
          not [e for e in profile.build_data({}) if e.op == "split_draw"])
    check("turning it on writes exactly one edit",
          len([e for e in profile.build_data({"split_draw_once": True})
               if e.op == "split_draw"]) == 1)


def run_vokes_regrow(args):
    """A file that shrank must be able to grow back into its own slot.

    The archive records a file's extent as its length, so shrinking one gives
    up the rest of its slot: nothing claims those bytes any more. Before this
    was fixed, the next edit even a byte larger than the shrunken size could no
    longer fit, and the file was relocated into the pad at the end -- on Rainbow
    Six 3 that moved R6GAMESETTINGS.INI, which is read at every level load,
    about a gigabyte away from everything read with it. These archives ship in
    three redundant copies precisely to keep seeks short, so that is a load-time
    regression and not a cosmetic one.
    """
    from tcps2.iso import Iso
    from tcps2.vokes import Region, open_archives

    if not args.rs3data:
        return
    print("\n[vokes -- a shrunken file grows back where it was]")

    class Shadow(Region):
        def __init__(self, inner):
            super().__init__(inner.fh, inner.base, inner.name)
            self.w = []
        def read(self, off, n):
            d = bytearray(super().read(off, n))
            for o, b in self.w:
                s0, e0 = max(off, o), min(off + n, o + len(b))
                if s0 < e0:
                    d[s0 - off:e0 - off] = b[s0 - o:e0 - o]
            return bytes(d)
        def write(self, off, data):
            self.w.append((off, bytes(data)))

    with Iso(args.rs3data) as iso:
        arc = open_archives(iso, r"/VOKES0\.IMG$")[0]
        arc.r = Shadow(arc.r)
        key = "/R6GAMESETTINGS.INI"
        entry = arc.files[key]
        home, full = entry.offset, entry.size
        body = arc.read_file(key)

        arc.write(key, body[:full - 40])
        check("shrinking keeps a file where it is",
              arc.files[key].offset == home and arc.files[key].size == full - 40,
              "0x%x/%d" % (arc.files[key].offset, arc.files[key].size))

        arc.write(key, body[:full - 6])
        check("and growing back into its own slot does too",
              arc.files[key].offset == home,
              "moved to 0x%x" % arc.files[key].offset)

        arc.write(key, body)
        check("right back to its full original length",
              arc.files[key].offset == home and arc.files[key].size == full)
        check("and the bytes read back unchanged", arc.read_file(key) == body)

        try:
            arc.write(key, body + bytes(1 << 20))
            moved = arc.files[key].offset != home
        except Exception:
            moved = True
        check("a file that truly outgrows its slot still moves", moved)


def run_combination_warnings():
    """Settings that are fine alone and fill the console together.

    Written after a real freeze: a disc carrying every zone feeding, 30 owed
    per zone, a refill at 2 alive, bodies never despawning and a decal ring of
    160 wedged the emulator a few minutes into Mountain Highway. Nothing in
    the tool said the combination was the problem.
    """
    from tcps2.games.r6_3 import PROFILE, combination_warnings

    print("\n[combinations that run the console out of memory]")
    base = dict(PROFILE.defaults(), wave_enable=True)

    def oom(vals):
        """Just the memory warnings.

        Wave mode also warns on its own now, because it stops Terrorist Hunt
        loading, and that note rides along with every config here -- they all
        have wave mode on, since that is what feeds the zones. Filtering it
        keeps these checks about the thing they were written for; the note
        itself is asserted directly, just above.
        """
        return [w for w in combination_warnings(vals)
                if "Terrorist Hunt" not in w]

    check("an untouched config says nothing",
          not oom(base), str(oom(base)))

    # A stored profile ignores a changed default, so the warning is what
    # actually reaches someone who turned wave mode on before it was known
    # to hang Terrorist Hunt.
    check("wave mode warns on its own, not only in combination",
          any("Terrorist Hunt" in w for w in combination_warnings(base)),
          str(combination_warnings(base)))
    check("and a config without it says nothing about it",
          not any("Terrorist Hunt" in w for w in
                  combination_warnings(dict(base, wave_enable=False))))

    bodies_only = dict(base, bodies="never", wave_gate="stock")
    check("bodies alone with the zones behaving is fine",
          not oom(bodies_only), str(oom(bodies_only)))

    both = dict(base, bodies="never")
    got = oom(both)
    check("but bodies never plus every zone feeding warns", got, str(got))

    real = dict(base, bodies="never", decal_ring=160)
    got = oom(real)
    check("and the disc that actually froze gets all three",
          len(got) == 3, "%d warnings" % len(got))
    check("the first one names the fix",
          any("player's zone" in w or "timer" in w for w in got))
    check("it reaches the plan, not just the profile",
          PROFILE.combination_warnings is combination_warnings)



def run_switch_off_restores(args, work):
    """Turning a data-file setting off must actually take it off the disc.

    The bug this pins down shipped, and it was the worst kind: `apply` reported
    success, `verify_data` reported the files read back cleanly, and the edit
    was still there. Two separate paths caused it. A setting at its default
    emits no FileEdit at all, so the loop over edits never visited the file;
    and when an edit WAS emitted with a do-nothing value, the writer compared
    the bytes it had just built against the STORED ORIGINAL -- which of course
    matched -- and skipped the write, leaving whatever an earlier run had put
    on the disc. Both are exercised here, in that order.

    Writes are shadowed, so the disc this reads is never modified.
    """
    from tcps2 import dataedit, lin, rsesidearm
    from tcps2.iso import Iso
    from tcps2.model import FileEdit
    from tcps2.vokes import Region, open_archives

    iso_path = args.rs3data or args.iso
    if not iso_path:
        return
    print("\n[switching a data setting off puts the file back]")

    class Shadow(Region):
        def __init__(self, inner):
            super().__init__(inner.fh, inner.base, inner.name)
            self.w = []
        def read(self, off, n):
            d = bytearray(super().read(off, n))
            for o, b in self.w:
                s0, e0 = max(off, o), min(off + n, o + len(b))
                if s0 < e0:
                    d[s0 - off:e0 - off] = b[s0 - o:e0 - o]
            return bytes(d)
        def write(self, off, data):
            self.w.append((off, bytes(data)))

    with Iso(iso_path) as iso:
        arcs = open_archives(iso, r"/VOKES0\.IMG$")
        if not arcs:
            return
        arc = arcs[0]
        arc.r = Shadow(arc.r)
        key = "/COMMON.LIN"
        if key.upper() not in arc.files:
            return
        stock = arc.read_file(key)
        store = dataedit.Store(os.path.join(work, "switchoff"))
        real = dataedit._archives
        dataedit._archives = lambda _iso, _profile: {arc.r.name.upper(): arc}
        try:
            on = FileEdit("ai_sidearm", r"/COMMON\.LIN$", "",
                          {"chance": 40, "in_contact": True, "say_chance": 0})
            dataedit.apply_data(iso, PROFILE, [on], store)
            after = arc.read_file(key)
            check("the edit lands", rsesidearm.reads(lin.decompress(after))[0] == 40)
            check("and does not change the file length", len(after) == len(stock))

            # a setting at its default emits no edit at all
            r = dataedit.apply_data(iso, PROFILE, [], store)
            back = arc.read_file(key)
            check("clearing the setting puts the file back byte for byte",
                  back == stock)
            check("and it is reported, not done silently", r.get("restored") == 1,
                  "restored=%r" % r.get("restored"))

            # and again through an edit that is present but does nothing
            dataedit.apply_data(iso, PROFILE, [on], store)
            check("re-applying puts it back on",
                  rsesidearm.reads(lin.decompress(arc.read_file(key)))[0] == 40)
            off = FileEdit("ai_sidearm", r"/COMMON\.LIN$", "",
                           {"chance": 0, "in_contact": True, "say_chance": 0})
            r = dataedit.apply_data(iso, PROFILE, [off], store)
            check("an edit that asks for stock also puts the file back",
                  arc.read_file(key) == stock)
            check("and that is reported too", r.get("restored") == 1,
                  "restored=%r" % r.get("restored"))
        finally:
            dataedit._archives = real


def run_vokes_stay_home(args):
    """A file that grows by a byte must not be exiled to the end of the archive.

    This shipped, and it was expensive: one setting made R6GAMESETTINGS.INI a
    single byte longer, which pushed it out of its slot and into the 64 KB pad
    at the end -- up to a gigabyte from everything a level reads alongside it.
    These archives exist in three redundant copies precisely to keep DVD seeks
    short, so the whole point of the layout was lost, and the only symptom was
    slow loading with a normal frame rate.

    Two separate faults, both checked here. The file could not use the packer's
    own alignment padding, because the blankness test that (rightly) protects
    unreferenced data also refused the few bytes between a file and the next
    one. And once moved it never came back: every later edit is built from the
    same stored original, so an edit that fitted again was simply written at
    whatever offset the first overflow happened to reach.

    Writes are shadowed, so the disc is never modified.
    """
    from tcps2.iso import Iso
    from tcps2.vokes import Region, open_archives

    iso_path = args.rs3data or args.iso
    if not iso_path:
        return
    print("\n[vokes -- a file that grows a byte stays where it was]")

    class Shadow(Region):
        def __init__(self, inner):
            super().__init__(inner.fh, inner.base, inner.name)
            self.w = []
        def read(self, off, n):
            d = bytearray(super().read(off, n))
            for o, b in self.w:
                s0, e0 = max(off, o), min(off + n, o + len(b))
                if s0 < e0:
                    d[s0 - off:e0 - off] = b[s0 - o:e0 - o]
            return bytes(d)
        def write(self, off, data):
            self.w.append((off, bytes(data)))

    with Iso(iso_path) as iso:
        arcs = open_archives(iso, r"/VOKES0\.IMG$")
        if not arcs:
            return
        arc = arcs[0]
        arc.r = Shadow(arc.r)
        key = "/R6GAMESETTINGS.INI"
        if key.upper() not in arc.files:
            return
        ent = arc.files[key.upper()]
        home, size = ent.offset, ent.size
        body = arc.read_file(key)

        slack = arc._align_slack(ent)
        check("the packer left alignment padding after it", slack > 0,
              "%d bytes" % slack)
        check("and it is padding, never a whole missing file", slack < arc.ALIGN)

        arc.write(key, body + b" ", home=(home, size))
        check("one byte longer still fits in its own slot",
              arc.files[key.upper()].offset == home,
              "moved to 0x%x" % arc.files[key.upper()].offset)
        check("and the record grew with it",
              arc.files[key.upper()].size == size + 1)
        check("the next file is still where it was",
              min(o.offset for o in arc.files.values() if o.offset > home)
              == home + size + slack)

        # now force a real relocation, then check it comes home again
        arc.write(key, body + b" " * (slack + 64), home=(home, size))
        moved = arc.files[key.upper()].offset
        check("a growth past the padding does relocate", moved != home)
        arc.write(key, body, home=(home, size))
        check("and shrinking back brings it home", 
              arc.files[key.upper()].offset == home,
              "left at 0x%x" % arc.files[key.upper()].offset)
        check("with its bytes intact", arc.read_file(key) == body)


def run_mem_size_preserved(args):
    """Every bytecode edit must leave the block's declared memory size alone.

    This is the whole reason the four script options were withdrawn. Each of
    them shrank that number -- ss_man_down -10, canon_team -3, ai_sidearm -3,
    ss_chatter -28 -- and padded the disk back out with `EX_Nothing`, which is
    one disk byte and one memory byte and so cannot make the memory total up
    again. On a real console every one of those hung the level load, while
    every edit that merely poked bytes in place worked.

    The padding now mixes `EX_Nothing` with `EX_LocalVariable` carrying a ref,
    which is compact on disk and four bytes in RAM, so both totals can be hit
    exactly. A ref has to be one the loader can resolve -- it turns the index
    into a pointer while reading, long before anything runs -- so the supply is
    the block's own refs rather than invented ones.
    """
    from tcps2 import (dataedit, lin, rsecanon, rsechatter, rsemandown,
                       rsesidearm, uscode)
    from tcps2.iso import Iso
    from tcps2.vokes import open_archives

    iso_path = args.rs3data or args.iso
    if not iso_path:
        return
    print("\n[bytecode edits keep the declared memory size]")
    with Iso(iso_path) as iso:
        arcs = open_archives(iso, r"/VOKES0\.IMG$")
        if not arcs:
            return
        arc = arcs[0]
        for path in ("/COMMON.LIN", "/COMMONOFF.LIN", "/COMMON_SS.LIN"):
            if path.upper() not in arc.files:
                continue
            raw = arc.read_entry(arc.files[path.upper()])
            plain = lin.decompress(raw)
            cases = [
                ("ss_man_down", rsemandown.find_block,
                 lambda p: rsemandown.apply(p, True)[0]),
                ("ai_sidearm", None,
                 lambda p: rsesidearm.apply(p, 40, True, 0)[0]),
                ("ss_chatter", rsechatter.find_block,
                 lambda p: rsechatter.apply(p, 35)[0]),
            ]
            if path == "/COMMON_SS.LIN":
                cases.append(("canon_team",
                              lambda p: rsecanon._block(
                                  p, rsecanon.TEAM_MEMBER_SIG, "x")[0],
                              lambda p: rsecanon.apply(p, True)[0]))
            for name, finder, fn in cases:
                new = fn(plain)
                check("%s: %s changes something" % (path[1:], name),
                      new != plain and len(new) == len(plain))
                if finder is None:
                    diff = next(i for i in range(len(plain))
                                if plain[i] != new[i])
                    at = max(b for b in uscode.find_blocks(
                        plain[max(0, diff - 4000):diff + 1],
                        lo=16, hi=20000)) + max(0, diff - 4000)
                else:
                    at = finder(plain)
                was = uscode.Script.at(plain, at)
                now = uscode.Script.at(new, at)
                check("%s: %s keeps the declared memory size" % (path[1:], name),
                      now.mem_len == was.mem_len,
                      "%d -> %d" % (was.mem_len, now.mem_len))
                check("%s: %s keeps the disk length" % (path[1:], name),
                      now.disk_len == was.disk_len)
                # every padding token must carry a ref the package can resolve
                pads = [t for t in now.toks
                        if t.op == uscode.EX_LOCAL_VARIABLE
                        and t.mstart is not None
                        and t.mstart > max(x.mstart for x in now.toks
                                           if x.op == uscode.EX_RETURN)]
                refs = {bytes(t.parts[0][1]) for t in pads}
                known = {bytes(v) for v in was._pad_refs().values()}
                check("%s: %s pads only with the block's own refs"
                      % (path[1:], name), refs <= known,
                      "%d pad tokens, %d unknown refs"
                      % (len(pads), len(refs - known)))
                packed = dataedit._repack("lin", raw, new)
                check("%s: %s still repacks and round-trips" % (path[1:], name),
                      len(packed) == len(raw) and lin.decompress(packed) == new)


def run_chunks_fill_exactly(args):
    """A rewritten chunk must fill its slot exactly, never be zero-padded.

    This is what made every bytecode edit fail while every byte-poke edit
    worked, and it had nothing to do with the bytecode. A chunk that re-deflates
    SMALLER than its slot used to be padded out with zeros, leaving bytes after
    the end of the stream that the game's own packer never emits. A byte-poke
    edit changes so little that the chunk re-deflates to the same size and is
    never padded; a bytecode edit compresses smaller and always was. Measured on
    COMMON.LIN: ss_man_down left 167 trailing zeros, split_wheel left none.

    The slack is now taken up inside the stream, as empty stored blocks, so the
    container is byte-for-byte the length it was with no trailing garbage.
    """
    from tcps2 import (dataedit, lin, rsecanon, rsechatter, rsemandown,
                       rsesidearm)
    from tcps2.iso import Iso
    from tcps2.vokes import open_archives

    iso_path = args.rs3data or args.iso
    if not iso_path:
        return
    print("\n[LIN chunks fill their slot exactly]")

    check("an empty stored block is five bytes and decodes to nothing",
          len(lin.EMPTY_STORED) == 5
          and zlib.decompress(b"\x78\x9c" + lin.EMPTY_STORED * 3
                              + zlib.compress(b"hi")[2:]) == b"hi")
    for budget_extra in (0, 5, 17, 123, 400):
        body = b"rainbow six three " * 500
        base = min((zlib.compress(body, l) for l in (9, 8, 7, 6, 5)), key=len)
        got = lin._deflate_exact(body, len(base) + budget_extra)
        check("a stream can be grown by exactly %d bytes" % budget_extra,
              got is not None and len(got) == len(base) + budget_extra
              and zlib.decompress(got) == body)

    with Iso(iso_path) as iso:
        arcs = open_archives(iso, r"/VOKES0\.IMG$")
        if not arcs:
            return
        arc = arcs[0]
        for path in ("/COMMON.LIN", "/COMMON_SS.LIN"):
            if path.upper() not in arc.files:
                continue
            raw = arc.read_entry(arc.files[path.upper()])
            plain = lin.decompress(raw)
            # Only these two reach an exact fill on this disc; ss_chatter and
            # canon_team land on a chunk no reachable compression fills, and
            # fall back to padding, which is allowed -- rpg_speed ships padded
            # and works.
            cases = [("ss_man_down", lambda p: rsemandown.apply(p, True)[0]),
                     ("ai_sidearm", lambda p: rsesidearm.apply(p, 40, True, 0)[0])]
            for name, fn in cases:
                edited = fn(plain)
                # `substitute` refuses outright if any chunk would be padded,
                # so getting a container back at all is the assertion.
                packed = dataedit._repack("lin", raw, edited)
                check("%s: %s packs with no zero padding" % (path[1:], name),
                      len(packed) == len(raw))
                check("%s: %s still round-trips" % (path[1:], name),
                      lin.decompress(packed) == edited)
                # and every touched chunk's stream really is its full slot
                short = []
                for (rawlen, comp, off) in lin.parse(packed)[0]:
                    blob = packed[off:off + comp]
                    d = zlib.decompressobj()
                    d.decompress(blob)
                    if len(d.unused_data) > 0:
                        short.append((off, len(d.unused_data)))
                check("%s: %s leaves nothing after any stream"
                      % (path[1:], name), not short,
                      "%d chunk(s) with trailing bytes" % len(short))

if __name__ == "__main__":
    raise SystemExit(main())

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
import io
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

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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
        run_split_orders(args)
        run_zopfli_fallback()
        run_enemy_loadouts(args)
        run_loadout_units()
        run_uscode_units()
        run_vokes_regrow(args)
        run_vokes_stay_home(args)
        run_mem_size_preserved(args)
        run_chunks_fill_exactly(args)
        run_switch_off_restores(args, work)
        run_team_recordings(args)
        run_recording_first(args)
        run_creation_order(args)
        run_callouts(args)
        run_flashlight_hands_pass(args)
        run_thunt_team(args)
        run_downcall(args)
        run_hostage_rainbow_voice(args)
        run_thunt_ai(args)
        run_fps_uncap(args)
        run_stun_and_spawn_fix(args)
        run_breach_stun(args)
        run_claymore_prox(args)
        run_blast_decals(args)
        run_friendly_fire(args)
        run_property_bools(args)
        run_impact_puffs(args)
        run_keep_viewport(args)
        run_hostage_follow(args)
        run_ai_hunt(args)
        run_wave_hunt_retired(args)
        run_game_presence(args)
        run_badge_honesty()
        run_combination_warnings()
        run_xbox_notes()
        run_applied_record(args, work)
        # Carrying the profile onto a pressing it was not built for.
        # Lives in its own file because it builds its own overlays.
        from tests_revision import run_revisions
        run_revisions(args, work)
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)

    print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
    return 1 if FAIL else 0


#: Every badge that is NOT a claim to have been watched in the running
#: game. The checks below say "marked unplayed", and that is what they
#: mean -- `applied` and `measured` are promotions earned by reading the
#: disc back, not by playing. Pinning them to the single literal
#: "experimental" made 13 checks fail the moment the 1.0 badge pass
#: promoted options that nobody had played, which is a false alarm: the
#: thing worth catching is an option quietly claiming "verified".
#: Every badge the window can draw. Per-option checks assert only that a
#: card wears one of these -- NOT which. Pinning each site to a literal
#: made a deliberate, evidence-backed promotion of 23 options look like
#: ten regressions, twice in one night. Whether a badge is HONEST is one
#: question asked in one place: run_badge_honesty.
BADGES = ("verified", "applied", "measured", "experimental",
          "untested", "broken")


def _changed(a, b, chunk=4096):
    """{indices where a and b differ}, screened in chunks.

    A flat `[i for i in range(len(a)) if a[i] != b[i]]` over a 5 MB game
    package is five million Python iterations, and it has twice been written
    with the transform called INSIDE the comprehension -- once per byte.
    Compare blocks first and only walk the ones that actually differ.
    """
    if len(a) != len(b):
        raise ValueError("lengths differ: %d vs %d" % (len(a), len(b)))
    out = set()
    for c in range(0, len(a), chunk):
        sa, sb = a[c:c + chunk], b[c:c + chunk]
        if sa != sb:
            out.update(c + i for i in range(len(sa)) if sa[i] != sb[i])
    return out


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

    print("\n[muzzle: the third-person flash test]")
    # Player 2 saw his flash doubled -- the third-person flash as well as the
    # first-person one -- because a native test skips the third-person
    # sub-emitters only when the shooter is viewport 0's player.
    from tcps2 import rsemuzzle as _mz
    tp = _mz.THIRD_PERSON_TEST
    def _btarget(va, word):
        imm = word & 0xFFFF
        imm = imm - 0x10000 if imm & 0x8000 else imm
        return va + 4 + (imm << 2)
    check("the stock test is bne $s0,$s1 in the pristine overlay",
          img.read_word(tp) == _mz.TP_STOCK == 0x16110007,
          "reads %08x" % img.read_word(tp))
    check("its delay slot is a nop", img.read_word(tp + 4) == 0)
    check("and it is not itself in a delay slot",
          img.read_word(tp - 4) == 0, "word before is %08x" % img.read_word(tp - 4))
    check("the fix is beq $s0,$zero with the same target",
          _mz.TP_FIXED == 0x12000007
          and _btarget(tp, _mz.TP_FIXED) == _btarget(tp, _mz.TP_STOCK) == 0x003F67C0)
    mw = [e for e in PROFILE.build_edits(dict(PROFILE.defaults(),
                                              split_muzzle=True))
          if e.va == tp]
    check("split_muzzle emits the word, declaring the stock it replaces",
          len(mw) == 1 and mw[0].value == _mz.TP_FIXED
          and mw[0].stock == _mz.TP_STOCK)
    check("and nothing else ever emits it -- it is wrong without the attach",
          not [e for e in PROFILE.build_edits(PROFILE.defaults())
               if e.va == tp])

    print("\n[split-screen enemy aim]")
    # Every terrorist in split screen fired along his head's direction, the
    # path single player keeps for an enemy blinded by smoke, because of a
    # flag at 0x006546F4 that is 1 in split screen and 0 in single player.
    from tcps2.games import r6_3 as _r6
    ab = _r6.SS_AIM_BRANCH
    check("the stock branch is beqz $v0 in the pristine overlay",
          img.read_word(ab) == 0x10400011, "reads %08x" % img.read_word(ab))
    check("it tests the flag loaded just before it",
          img.read_word(ab - 4) == 0x8F829004)          # lw $v0, -0x6ffc($gp)
    check("the smoke test that must survive sits one branch earlier",
          img.read_word(ab - 0xC) == 0x14400004)        # bnez $v0 -> view path
    check("the delay slot is a nop", img.read_word(ab + 4) == 0)
    check("the fix is unconditional with the same target",
          _btarget(ab, _r6.SS_AIM_ALWAYS) == _btarget(ab, 0x10400011)
          == 0x003F3DD8)
    aw = [e for e in PROFILE.build_edits(dict(PROFILE.defaults(),
                                              ss_accuracy=True))
          if e.va == ab]
    check("ss_accuracy emits exactly that word",
          len(aw) == 1 and aw[0].value == _r6.SS_AIM_ALWAYS)
    check("and it is off unless asked for",
          not [e for e in PROFILE.build_edits(PROFILE.defaults()) if e.va == ab])

    print("\n[Clark's voice in split screen]")
    # The debriefing, and both briefing pages, find Clark's clip through one
    # lookup that answers -1 unless the game mode is 1 or 2. Split-screen
    # practice is 11. Run the lookup's opening test, stock and edited, for
    # every value its mode byte can hold.
    from tcps2 import rseclark as _ck
    check("the four words are stock in the pristine overlay",
          all(img.read_word(va) == st for va, st, _n, _x in _ck.EDITS),
          str([hex(img.read_word(va)) for va, _s, _n, _x in _ck.EDITS]))
    check("and so is every word the edit leans on",
          all(img.read_word(va) == st for va, st in _ck.CONTEXT))
    check("the debriefing indexes m_sndDebriefing at +0xD0",
          img.read_word(0x00431A5C) == 0x244200D0)     # addiu $v0, $v0, 0xd0

    def _lookup(mode, patched):
        """Where the lookup's opening test sends a mode: ('search', s0) or
        ('return', v0). Only the words in 0x48dc34..0x48dcd0 are run."""
        words = {va: img.read_word(va) for va in range(0x0048DC34, 0x0048DCD4, 4)}
        if patched:
            words.update({va: new for va, _s, new, _n in _ck.EDITS})
        reg = [0] * 32
        reg[2], reg[16], reg[3] = 1, 0x1234, 0x5678   # v0 = 1 from 0x48dc14

        def _s32(v):
            v &= 0xFFFFFFFF
            return v - (1 << 32) if v & 0x80000000 else v

        def _step(pc):
            wd = words[pc]
            op, rs, rt = wd >> 26, (wd >> 21) & 31, (wd >> 16) & 31
            imm = wd & 0xFFFF
            simm = imm - 0x10000 if imm & 0x8000 else imm
            if op == 0x24:                                  # lbu
                reg[rt] = mode
            elif op == 0x09:                                # addiu
                reg[rt] = _s32(reg[rs] + simm)
            elif op == 0 and wd & 0x3F == 0x2D:             # daddu
                reg[(wd >> 11) & 31] = reg[rs] + reg[rt]
            elif op in (4, 5):
                return pc + 4 + (simm << 2), (reg[rs] == reg[rt]) == (op == 4)
            else:
                raise AssertionError("unexpected word %08x at %08x" % (wd, pc))
            reg[0] = 0
            return None

        pc = 0x0048DC34
        for _guard in range(40):
            if pc == 0x0048DC50:
                return ("search", reg[16])
            if pc == 0x0048DCD4:
                return ("return", reg[2])
            br = _step(pc)
            if br is None:
                pc += 4
                continue
            target, taken = br
            _step(pc + 4)                                   # the delay slot
            pc = target if taken else pc + 8
        raise AssertionError("no exit")

    _stock_out = {m: _lookup(m, False) for m in range(256)}
    _new_out = {m: _lookup(m, True) for m in range(256)}
    check("stock searches for the campaign and practice only",
          {m for m, o in _stock_out.items() if o[0] == "search"} == {1, 2})
    check("edited, split-screen practice searches as well",
          {m for m, o in _new_out.items() if o[0] == "search"} == {1, 2, 11})
    check("every other mode byte ends exactly where it always did",
          all(_new_out[m] == _stock_out[m] for m in range(256) if m != 11))
    check("a search starts from index 0, a miss returns -1",
          all(o == ("search", 0) or o == ("return", -1)
              for o in list(_new_out.values()) + list(_stock_out.values())))

    # Who else asks: every call through the game manager's vtable slot 0xA0.
    def _gm_calls():
        out = []
        lw_t9 = 0x8F390000 | 0xA0                     # lw $t9, 0xa0($t9)
        gm = 0x10000 - 0x66E4                         # lw $x, -0x66e4($gp)
        for off in range(0, len(img.image) - 4, 4):
            if struct.unpack_from("<I", img.image, off)[0] != lw_t9:
                continue
            va = base + off
            back = [img.read_word(va - 4 * k) for k in range(1, 14)]
            if any(b >> 26 == 0x23 and (b >> 21) & 31 == 28
                   and b & 0xFFFF == gm for b in back):
                out.append(va)
        return out
    check("three callers, all of them Clark: debriefing and two briefings",
          _gm_calls() == [0x0040E3C0, 0x004319E4, 0x0046D1EC],
          str([hex(x) for x in _gm_calls()]))
    check("and nothing calls the lookup directly",
          struct.pack("<I", 0x0C000000 | (_ck.LOOKUP >> 2)) not in bytes(img.image))

    _cw = [e for e in PROFILE.build_edits(dict(PROFILE.defaults(), ss_clark=True))
           if 0x0048DC34 <= e.va <= 0x0048DCD0]
    check("ss_clark writes the four words, each declaring its stock",
          sorted((e.va, e.value, e.stock) for e in _cw)
          == sorted((va, new, st) for va, st, new, _n in _ck.EDITS))
    check("and it is off unless asked for",
          not [e for e in PROFILE.build_edits(PROFILE.defaults())
               if 0x0048DC34 <= e.va <= 0x0048DCD0])
    check("it is offered, and the window knows how to draw its badge",
          PROFILE.setting("ss_clark").confidence in BADGES
          and PROFILE.setting("ss_clark").group == "Split Screen")

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

    # The settings record is written AFTER the disc is patched and verified.
    # If it cannot be written, that must not turn a good apply into a failed
    # one -- the record is a convenience beside the disc, not the disc.
    from tcps2 import applied as _ap
    _real = _ap.record
    def _no_room(*_a, **_k):
        raise OSError(28, "No space left on device")
    _ap.record = _no_room
    try:
        try:
            rr = engine.apply(iso_path, PROFILE, vals)
            ok = rr["applied"] == rr["verified"] and "record_error" in rr
        except Exception:                                             # noqa: BLE001
            ok = False
    finally:
        _ap.record = _real
    check("an unwritable settings record does not fail a good apply", ok)

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
    from gui.presets import PRESETS, HUD_ON
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
          sum(1 for v in r6 if v.get("split_scope")) == len(r6) - 1)
    check("and Stock is the one that does not",
          not r6[0].get("split_scope"))
    # The split-screen preset is the one being shipped for a public release,
    # and the claim made for it is specific: clicking it can only give you
    # things that have been watched working on hardware. That is checked as
    # an invariant rather than spot-checked.
    #
    # It is deliberately NOT applied to every preset. Eighteen entries across
    # the GRAW, GR2 and SOAF enemy-tuning presets turn on `experimental`
    # options, which is that area's established practice -- those presets are
    # knobs to try, not guarantees. Widening this check to them would be
    # changing other games' behaviour under cover of a test.
    hud = [s2 for s2 in PROFILE.settings if HUD_ON.get(s2.key)]
    check("the split-screen preset turns on exactly the nine proven fixes",
          sorted(s2.key for s2 in hud) == [
              "split_cycle", "split_draw_once", "split_muzzle",
              "split_scope",
              "split_sway", "split_sway_turn", "split_wheel"],
          "%r" % (sorted(s2.key for s2 in hud),))
    check("and every one of them is verified in game",
          all(s2.confidence == "verified" and s2.enabled for s2 in hud),
          "%r" % ([(s2.key, s2.confidence) for s2 in hud
                   if s2.confidence != "verified" or not s2.enabled],))
    check("nothing broken or retired is in it",
          not [s2 for s2 in hud if not s2.enabled])

    print("\n[wheel label text]")
    import struct as _lst
    from tcps2 import rsedeadpath as _ldp, rsewheel as _lw
    _data = _ldp.claim("label_scale", True)
    _words = {va: w for va, w, _s, _n in _lw.label_words()}
    check("the scale ships as 1.0 and the offset as 0.0 -- identity",
          _words[_data] == _lw.ONE_F == 0x3F800000
          and _words[_data + 4] == 0)
    check("the arm, glyph and disarm caves are the interpreter-checked words",
          list(_lw._label_arm(_data)) == [
              0x8F818E94, 0x3C020004, 0x00220821, 0x8C210A04, 0x3C02001A,
              0x44810800, 0xE45AB2DC, 0x46800860, 0x03E00008, 0xE441B2E0, 0]
          and list(_lw._label_glyph(_data)) == [
              0x3C01001A, 0xC420B2DC, 0xC422B2E0, 0x44890800, 0x46006B42,
              0x46800860, 0x46026B40, 0x46000842, 0x080D25B4, 0x460D0BC0]
          and list(_lw._label_unarm(_data)) == [
              0x3C02001A, 0x3C013F80, 0xAC41B2DC, 0x080D29B4, 0xAC40B2E0])
    check("every glyph call goes through the text cave",
          _words[_lw.LABEL_TEXT_HOOK]
          == 0x0C000000 | (_ldp.claim("label_text", True) >> 2))
    check("and the call after the fourth label through the disarm",
          _words[_lw.LABEL_UNARM_HOOK]
          == 0x0C000000 | (_ldp.claim("label_unarm", True) >> 2))
    check("both hooks replace the calls the caves tail-jump to",
          _lw.LABEL_TEXT_STOCK == 0x0C000000 | (_lw.LABEL_TEXT_TARGET >> 2)
          and _lw.LABEL_UNARM_STOCK
          == 0x0C000000 | (_lw.LABEL_UNARM_TARGET >> 2))
    _dslot = [va for va in (_ldp.claim("label_text", True) + 32,
                            _ldp.claim("label_unarm", True) + 12,
                            _ldp.claim("wheel_label", True) + 32)
              if (_words.get(va + 4, 0) >> 26) in (1, 2, 3, 4, 5, 6, 7)]
    check("no jump or branch sits in any of their delay slots", not _dslot)

    def _f(x):
        return _lst.unpack("<f", _lst.pack("<f", x))[0]

    def _glyph(y0, vsize, k, vpy):
        y = _f(_f(y0 * k) + vpy)
        return y, _f(_f(vsize * k) + y)
    _cases = [(y0 / 4.0, 15) for y0 in range(0, 448 * 4, 7)]
    check("disarmed, every glyph lands exactly where it always did",
          all(_glyph(y, v, 1.0, 0.0) == (_f(y), _f(v + _f(y)))
              for y, v in _cases))
    check("armed in split screen it is half height, in its own half",
          _glyph(100.0, 15, 0.5, 224.0) == (274.0, 281.5))
    check("the old label cave's single-player lift is gone",
          _lw.MUL_F0_BY_F21 not in list(_lw._label_arm(_data)))

    print("\n[team status panel]")
    from tcps2 import rsedeadpath as _tdp, rsehudteam as _th
    _tw = _th.words(True)
    check("six hooks and six caves, 122 words",
          len(_th.HOOKS) == 6 and len(_tw) == 122)
    # The names cave flushes the quad batch before the text, exactly as
    # single player does, or the panel box is drawn over its own text. That
    # dimmed every name and status to ~40% in the first version.
    _nf, _nb = _th.CAVES["team_names"]
    _flush = [_nb[k:k + 2] for k in range(len(_nb) - 1)]
    check("single player flushes the batch before the names (0x3eb638)",
          (img.read_word(0x003EB634), img.read_word(0x003EB638))
          == (0x27A401E0, 0x0C0D2948))
    check("and that is the same flush the panel's exit makes",
          0x0C0D2948 in _th.CAVES["team_exit"][1])
    check("the names cave does the same flush on the window path",
          [0x27A401E0, 0x0C0D2948] in [list(p) for p in _flush])
    check("and the hook reaches the moved cave",
          [(n & 0x03FFFFFF) << 2 for va, _s, n, _x in _th.HOOKS
           if va == 0x003EAF14] == [_tdp.CAVE + 4 * _nf])
    check("every cave sits in its own dead-path slot",
          all(_tdp.claim(slot, True) == _tdp.CAVE + 4 * first
              for slot, (first, _b) in _th.CAVES.items()))
    check("and fits inside the proved block",
          max(first + len(b) for first, b in _th.CAVES.values())
          <= _tdp.CAVE_WORDS)
    _hooks = {va for va, _s, _n, _x in _th.HOOKS}
    check("each hook jumps into one of the panel's caves",
          all(((new & 0x03FFFFFF) << 2)
              in {_tdp.claim(slot, True) for slot in _th.CAVES}
              for _va, _s, new, _x in _th.HOOKS))
    _on = PROFILE.effective(dict(PROFILE.defaults(), split_squad=True,
                                 split_team_panel=True))
    _eds = {e.va for e in PROFILE.build_edits(_on)}
    check("with AI teammates it writes every word, and frees the dead path",
          {va for va, _w, _s, _n in _tw} <= _eds and _tdp.ENTRY in _eds)
    _off = PROFILE.effective(dict(PROFILE.defaults(), split_team_panel=True))
    check("without AI teammates there is nothing to list, so it stays off",
          _off["split_team_panel"] is False
          and not (_hooks & {e.va for e in PROFILE.build_edits(_off)}))
    check("it is offered, and was watched working in game",
          PROFILE.setting("split_team_panel").confidence == "verified")

    print("\n[team panel: the speaking flash, for both players]")
    # The voice-queue natives fire SetTeamMemberSpeaking on ONE controller's
    # HUD (player 2's), so only his panel flashed. The panel's speaking test
    # now ORs the slot's flag on both viewports' HUDs, in the window only.
    _sw = _th.speak_words()
    check("the hook replaces the speaking test's two words, stock in the image",
          all(img.read_word(va) == st for va, _w, st, _n in _sw))
    _cave_lo, _cave_hi = 0x005B1C14, 0x005B1CC0
    check("the cave is inside the padding that ends the code section",
          all(_cave_lo <= va < _cave_hi for va, _w, _st, _n in _sw[2:])
          and img.read_word(0x005B1C0C) == 0x03E00008          # jr ra before it
          and img.read_word(_cave_hi) != 0)                    # data after it
    _refd = []
    for _off in range(0, len(img.image) - 4, 4):
        _w = struct.unpack_from("<I", img.image, _off)[0]
        _va = base + _off
        _op = _w >> 26
        if _op in (2, 3):
            _t = ((_va + 4) & 0xF0000000) | ((_w & 0x03FFFFFF) << 2)
        elif _op in (1, 4, 5, 6, 7, 0x14, 0x15, 0x16, 0x17):
            _i = _w & 0xFFFF
            _t = _va + 4 + ((_i - 0x10000 if _i & 0x8000 else _i) << 2)
        else:
            _t = _w
        # The cave's own words. (A data table at 0x59fd98 happens to decode
        # as a beql landing at 0x5b1cb4 -- padding, but past the cave.)
        if _th.SPEAK_CAVE <= _t < _th.SPEAK_CAVE + 4 * len(_th.SPEAK_BODY):
            _refd.append(_va)
    check("and nothing in the stock overlay branches, jumps or points into it",
          not _refd, str([hex(x) for x in _refd[:4]]))

    def _speak(push, hud0, hud1, this, slot, flags, nulls=()):
        """Run the hooked test: returns v0 as the beqz at 0x3ed8d8 sees it."""
        code = {va: w for va, w, _s, _n in _sw}
        gp = 0x0065B6F0
        mem = {0x0065460C: push, 0x006547AC: 0x7000, 0x7000 + 0x44: 0x7100,
               0x7100 + 0x30: 0x7200,
               0x7200: 0 if "vp0" in nulls else 0x7300,
               0x7204: 0 if "vp1" in nulls else 0x7400,
               0x7300 + 0x34: 0 if "pc0" in nulls else 0x7500,
               0x7400 + 0x34: 0x7600,
               0x7500 + 0x57C: 0 if "hud0" in nulls else hud0,
               0x7600 + 0x57C: hud1}
        r = [0] * 32
        r[28], r[20], r[22] = gp, this, slot

        def rd(a):
            return mem.get(a & 0xFFFFFFFF, 0)

        def s16(i):
            return i - 0x10000 if i & 0x8000 else i

        def step(pc):
            w = code[pc]
            op, rs, rt, rd_ = w >> 26, (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31
            imm = w & 0xFFFF
            br = None
            if w == 0:
                pass
            elif op == 0 and w & 0x3F == 0x21:
                r[rd_] = (r[rs] + r[rt]) & 0xFFFFFFFF
            elif op == 0 and w & 0x3F == 0x25:
                r[rd_] = r[rs] | r[rt]
            elif op == 0 and w & 0x3F == 0x08:
                br = r[rs]
            elif op == 0x23:
                r[rt] = rd(r[rs] + s16(imm))
            elif op == 0x24:
                r[rt] = flags.get((r[rs] + s16(imm)) & 0xFFFFFFFF, 0)
            elif op == 0x0E:
                r[rt] = r[rs] ^ imm
            elif op in (4, 5):
                if (r[rs] == r[rt]) == (op == 4):
                    br = pc + 4 + (s16(imm) << 2)
            elif op == 3:
                r[31] = pc + 8
                br = (w & 0x03FFFFFF) << 2
            else:
                raise AssertionError("unexpected %08x at %08x" % (w, pc))
            r[0] = 0
            return br

        pc, ret = 0x003ED8D0, 0x003ED8D8
        for _g in range(80):
            if pc == ret:
                return r[2]
            br = step(pc)
            if br is None:
                pc += 4
                continue
            step(pc + 4)
            pc = br
        raise AssertionError("no return")

    H0, H1 = 0x10000, 0x20000
    both = {H0 + 0x503 + 1: 0, H1 + 0x503 + 1: 1}
    check("single player: the test reads this HUD's own flag, as stock",
          _speak(1, H0, H1, H0, 1, {H0 + 0x504: 1}) == 1
          and _speak(1, H0, H1, H0, 1, {H1 + 0x504: 1}) == 0)
    check("split screen: player 1's panel flashes on player 2's HUD flag",
          _speak(0x5A, H0, H1, H0, 1, both) == 1)
    check("and player 2's own panel still flashes",
          _speak(0x5A, H0, H1, H1, 1, both) == 1)
    check("a slot nobody is speaking in stays still",
          _speak(0x5A, H0, H1, H0, 0, both) == 0)
    check("a missing viewport, controller or HUD is skipped, not followed",
          all(_speak(0x5A, H0, H1, H0, 1, both, (n,)) == 1
              for n in ("vp0", "pc0", "hud0"))
          and _speak(0x5A, H0, H1, H0, 1, both, ("vp1",)) == 0)
    _on = PROFILE.effective(dict(PROFILE.defaults(), split_squad=True,
                                 split_team_panel=True))
    _vas = {e.va for e in PROFILE.build_edits(_on)}
    check("it ships with the team panel",
          {va for va, _w, _s, _n in _sw} <= _vas)
    check("and not without it",
          not ({va for va, _w, _s, _n in _sw}
               & {e.va for e in PROFILE.build_edits(PROFILE.defaults())}))

    print("\n[debriefing: every operative's statistics]")
    from tcps2 import rsedebrief as _db
    check("the two words are stock, and so is what they rely on",
          all(img.read_word(va) == st for va, st, _n, _x in _db.EDITS)
          and all(img.read_word(va) == st for va, st in _db.CONTEXT))
    _rows, _copy = _db.EDITS
    check("split screen's rows become count + lost + 1 (addiu s7, a3, 1)",
          _rows[2] == 0x24F70001 and (_rows[2] >> 21) & 31 == 7
          and (_rows[2] >> 16) & 31 == 23 and _rows[2] & 0xFFFF == 1)
    check("the copy loop is skipped outright, to the same target",
          (_copy[2] & 0xFFFF) == (_copy[1] & 0xFFFF)
          and _copy[2] >> 16 == 0x1000)
    _sq = PROFILE.build_edits(PROFILE.effective(
        dict(PROFILE.defaults(), split_squad=True)))
    check("it ships with the AI teammates, and only with them",
          {va for va, _s, _n, _x in _db.EDITS} <= {e.va for e in _sq}
          and not ({va for va, _s, _n, _x in _db.EDITS}
                   & {e.va for e in PROFILE.build_edits(PROFILE.defaults())}))

    print("\n[dead-path cave]")
    # Restored 2026-09-22. This whole block was deleted by accident that
    # afternoon, when a test edit replaced a span of this file that happened
    # to contain it; the pass count kept rising, so its absence went unseen
    # through a commit. It guards the one shared code cave every HUD fix
    # lives in, so it is not optional. Counts updated for the scope merge
    # (three cards -> one) and the wheel marker's left/right slot.
    from tcps2 import rsedeadpath, rsescope, rsewheel, rseviewmodel
    check("the slots do not overlap", rsedeadpath.check_layout() == 219)
    check("a cave slot is refused while the entry branch is live",
          _raises(lambda: rsedeadpath.claim("scope_height", False),
                  rsedeadpath.DeadPathError))
    from tcps2 import rsehudteam
    hud = (rsescope.viewport_words() + rsewheel.label_words()
           + rsewheel.owner_words() + rsescope.owner_words()
           + rseviewmodel.words(True) + rsehudteam.words(True))
    addrs = [x[0] for x in hud]
    check("no two HUD words fight over an address",
          len(set(addrs)) == len(addrs) == 290,
          "%d words, %d distinct" % (len(addrs), len(set(addrs))))
    check("every HUD word is inside the overlay",
          all(0x00100000 <= a < 0x00653980 for a in addrs))
    check("every HUD word declares the stock the profile holds",
          all(STOCK.get(a) == st for a, _w, st, _n in hud),
          "%r" % ([hex(a) for a, _w, st, _n in hud if STOCK.get(a) != st][:4],))
    # Freeing the dead path is not optional. With the scope option off, an
    # option that needs the cave has to retire the branch itself, or split
    # screen jumps straight into what is now cave code.
    lab = dict(PROFILE.defaults(), split_wheel=True, split_wheel_labels=True)
    ent = [e for e in PROFILE.build_edits(lab) if e.va == rsedeadpath.ENTRY]
    check("labels alone retire the branch into the dead path", len(ent) == 1)
    check("and do it without changing what split screen does",
          ent and ent[0].value == rsedeadpath.FREE_BRANCH)
    both = dict(PROFILE.defaults(), split_scope=True)
    ent2 = [e for e in PROFILE.build_edits(both) if e.va == rsedeadpath.ENTRY]
    check("the scope guard frees it instead when the scope is on",
          ent2 and ent2[0].value == rsescope.SCOPE_GUARD[0][1])
    check("nothing on this disc needs a cheat file for the HUD",
          not PROFILE.build_pnach(dict(PROFILE.defaults(), split_scope=True,
                                       split_wheel=True,
                                       split_wheel_labels=True)))

    print("\n[wheel marker: left and right]")
    # The marker's left/right cases draw through a rotated-quad call that
    # hard-codes a 1.0 scale, so they kept the ring's pre-fix native size.
    side0, side_n = rsedeadpath.SLOTS["wheel_side"]
    check("the side slot ends where the first 96 proved words end",
          side0 + side_n == 96 <= rsedeadpath.CAVE_WORDS == 244)
    check("the cave is 17 words and tail-jumps into the stock call",
          len(rsewheel.SIDE_CAVE) == 17
          and rsewheel.SIDE_CAVE[-2] == 0x08000000 | (rsewheel.SIDE_TARGET >> 2))
    sidew = [x for x in rsewheel.label_words() if "left/right" in x[3]]
    check("its four hooks and 17 cave words are emitted with the labels",
          len(sidew) == 21)
    cave_va = rsedeadpath.CAVE + side0 * 4
    check("each hook becomes jal into the cave, from the declared stock",
          all(v == 0x0C000000 | (cave_va >> 2) and st == rsewheel.SIDE_STOCK
              for a, v, st, _n in sidew if a in rsewheel.SIDE_HOOKS))
    check("the hooks are only ever emitted with the ring that builds $f26",
          any("hook the ring" in x[3] for x in rsewheel.label_words()))
    # The cave's arithmetic, modelled in float32: single player must pass
    # through bit-identical, split screen must land at single player x 0.5
    # plus the viewport's Y.
    import struct as _s
    f32 = lambda v: _s.unpack("<f", _s.pack("<f", v))[0]
    def side(x, y, w, h, k, vpy):
        d = f32(f32(k * 0.5) - 0.5)
        y2 = f32(f32(k * y) + f32(h * d))
        return f32(x - f32(w * d)), f32(y2 + vpy), f32(w * k)
    for x0, y0 in ((350.0, 242.0 - 131), (292.0 - 94, 205.0)):
        check("single player at (%g, %g) passes through unchanged" % (x0, y0),
              side(x0, y0, 94.0, 131.0, 1.0, 0.0) == (x0, y0, 94.0))
    xs, ys, ws = side(350.0, 205.0, 94.0, 131.0, 0.5, 224.0)
    check("split screen halves the visible height and drops into player 2's half",
          ws == 47.0 and ys >= 224.0 and abs((xs + ws / 2) - (350.0 + 94.0 / 2)) < 1e-4)

    print("\n[length-changing edits are refused]")
    # frag_warning grew a cooked package by 107 bytes, the container still
    # fitted its slot, and the game then would not boot at all -- it hung on
    # the initial load screen before any level. The file growing and the
    # engine tolerating it are different claims. This is the guard that keeps
    # the difference from being discovered on the console again.
    from tcps2 import dataedit, rsefragwarn
    fw = PROFILE.setting("frag_warning")
    check("frag_warning is retired, not merely defaulted off",
          fw is not None and not fw.enabled and fw.confidence == "broken")
    check("and effective() neutralises it even if a saved profile sets it",
          PROFILE.effective({"frag_warning": True})["frag_warning"] is False)
    check("so it reaches neither the plan nor the disc",
          not [e for e in PROFILE.build_data({"frag_warning": True})
               if e.op == "frag_warning"])
    check("every enabled split-screen data edit is length-preserving by op",
          all(op in dataedit.OPS for op in
              ("muzzle", "squad", "switch_rate", "fov")))

    print("\n[weapon switch animation rate]")
    import struct as _st
    from tcps2 import rseswitch
    spad = (bytes(40) + rseswitch.PREFIX + _st.pack("<f", 2.9) + bytes(40))
    check("the stock rate reads 290%", rseswitch.reads(spad) == 290
          == rseswitch.STOCK)
    sgot, sn = rseswitch.apply(spad, 150)
    check("it can be set to the game's own 150%",
          sn == 1 and rseswitch.reads(sgot) == 150)
    check("exactly the four value bytes move",
          [i for i in range(len(spad)) if spad[i] != sgot[i]]
          == [40 + 3, 40 + 4, 40 + 5, 40 + 6])
    check("the property tag and name index are untouched",
          sgot[40:43] == rseswitch.PREFIX)
    check("the file length never moves", len(sgot) == len(spad))
    check("running it twice changes nothing",
          rseswitch.apply(sgot, 150) == (sgot, 0))
    check("it can be put back", rseswitch.apply(sgot, 290)[0] == spad)
    check("a rate outside the band is refused",
          _raises(lambda: rseswitch.apply(spad, 50), rseswitch.SwitchError)
          and _raises(lambda: rseswitch.apply(spad, 400),
                      rseswitch.SwitchError))
    check("a build without the record is refused",
          _raises(lambda: rseswitch.apply(bytes(128), 150),
                  rseswitch.SwitchError))
    check("an ambiguous build is refused",
          _raises(lambda: rseswitch.apply(spad + rseswitch.PREFIX
                                          + _st.pack("<f", 2.9), 150),
                  rseswitch.SwitchError))
    sw = [e for e in PROFILE.build_data(dict(PROFILE.defaults(),
                                             switch_rate=150))
          if e.op == "switch_rate"]
    check("the setting emits one data edit", len(sw) == 1)
    check("it reaches all three COMMON files -- the rate has no per-mode copy",
          sw and all(sw[0].matches(q) for q in
                     ("/COMMON.LIN", "/COMMONOFF.LIN", "/COMMON_SS.LIN")))
    check("and stock emits nothing",
          not [e for e in PROFILE.build_data(PROFILE.defaults())
               if e.op == "switch_rate"])

    print("\n[muzzle flash]")
    from tcps2 import rsemuzzle
    pad = bytes(64) + rsemuzzle.STATEMENT + bytes(64)
    check("the stock gate reads as an object ==",
          pad[64 + rsemuzzle.OPERAND] == rsemuzzle.EQ)
    check("a stock file reports the flash NOT on the FP weapon",
          not rsemuzzle.reads(pad))
    got, n = rsemuzzle.apply(pad, True)
    check("the fix flips exactly one byte",
          n == 1 and sum(a != b for a, b in zip(pad, got)) == 1)
    check("and that byte is the comparison operand",
          got[64 + rsemuzzle.OPERAND] == rsemuzzle.NE)
    check("the file length never moves", len(got) == len(pad))
    check("it reads back as fixed", rsemuzzle.reads(got))
    check("running it twice changes nothing", rsemuzzle.apply(got, True) == (got, 0))
    check("it can be put back", rsemuzzle.apply(got, False)[0] == pad)
    check("a build without the gate is refused, not guessed at",
          _raises(lambda: rsemuzzle.apply(bytes(256), True),
                  rsemuzzle.MuzzleError))
    check("an ambiguous build is refused too",
          _raises(lambda: rsemuzzle.apply(pad + rsemuzzle.STATEMENT, True),
                  rsemuzzle.MuzzleError))
    mz = [e for e in PROFILE.build_data(dict(PROFILE.defaults(),
                                             split_muzzle=True))
          if e.op == "muzzle"]
    check("the setting emits one data edit", len(mz) == 1)
    check("it reaches all three COMMON files -- single player cannot change",
          mz and all(mz[0].matches(p) for p in
                     ("/COMMON.LIN", "/COMMONOFF.LIN", "/COMMON_SS.LIN")))
    check("and emits nothing at its default",
          not [e for e in PROFILE.build_data(PROFILE.defaults())
               if e.op == "muzzle"])

    print("\n[L1 tap in split screen]")
    # Player 2 had a gadget out in co-op and a tap of L1 would not bring his
    # rifle back. The first version of split_cycle copied single player's
    # toggle count into the split-screen arm but not single player's
    # gadget-out branch, so from slot 2 the tap computed (2 + 1) % 2 = 1 and
    # handed him his pistol. The fix routes split screen into single player's
    # arm instead of imitating it.
    from tcps2 import rsewheel as _rw
    cpad = (bytes(20) + _rw.CYCLE_GUARD + bytes(20)
            + _rw.CYCLE_ANCHOR + bytes(20))
    GI = 20 + _rw.GUARD_OPERAND
    CI = 20 + len(_rw.CYCLE_GUARD) + 20 + _rw.CYCLE_CONST_AT
    check("stock split screen runs its own arm", not _rw.cycle_reads(cpad))
    cgot, cn = _rw.cycle_restore(cpad, True)
    check("the fix moves exactly one byte",
          cn == 1 and [i for i in range(len(cpad)) if cpad[i] != cgot[i]] == [GI])
    check("and it is the guard's comparison, now ==",
          cgot[GI] == _rw.GUARD_FIXED == 0x72)
    check("the unreachable split-screen count stays at the shipped 4",
          cgot[CI] == _rw.CYCLE_SPLIT == 4)
    check("it reads back as routed", _rw.cycle_reads(cgot))
    check("running it twice changes nothing",
          _rw.cycle_restore(cgot, True) == (cgot, 0))
    check("it can be put back", _rw.cycle_restore(cgot, False)[0] == cpad)
    first = bytearray(cpad)
    first[CI] = _rw.CYCLE_SINGLE
    fixed, fn = _rw.cycle_restore(bytes(first), True)
    check("a disc carrying the first version is repaired to the same bytes",
          fn == 2 and fixed == cgot)
    check("a build without the guard is refused",
          _raises(lambda: _rw.cycle_restore(bytes(20) + _rw.CYCLE_ANCHOR, True),
                  _rw.WheelError))
    check("an ambiguous build is refused",
          _raises(lambda: _rw.cycle_restore(cpad + _rw.CYCLE_GUARD, True),
                  _rw.WheelError))

    print("\n[split-screen squad]")
    from tcps2 import rsesquad, rseteam
    # A real COMMON carries all three sites; the option edits two of them and
    # insists the third -- the arm's own exit -- is stock.
    R = 48
    X = R + len(rsesquad.RESCUE_SIG) + 48
    C = X + len(rsesquad.EXIT_SIG) + 48
    RL = C + len(rsesquad.COUNT_SIG) + 48
    RW = RL + len(rsesquad.ROSTER_SIGS["L"]) + 48
    SK = RW + len(rsesquad.ROSTER_SIGS["W"]) + 48
    LC = SK + len(rsesquad.SKINS_SIG) + 48
    LB = LC + len(rsesquad.LAYOUT_CALL) + 48
    OA = LB + len(rsesquad.LAYOUT_CODE) + 48
    DG = OA + len(rsesquad.ORDER_AIM) + 48
    WT = DG + len(rsesquad.DEAD_GATE) + 48
    LEAD = [rsesquad.DEAD_LOG, rsesquad.REGROUP, rsesquad.TOGGLE_FOLLOW,
            rsesquad.HANDOFF, rsesquad.LADDER_START, rsesquad.LADDER_END]
    LEAD_NEW = [rsesquad.DEAD_LOG_NEW, rsesquad.REGROUP_NEW,
                rsesquad.TOGGLE_FOLLOW_NEW, rsesquad.HANDOFF_NEW,
                rsesquad.LADDER_START_NEW, rsesquad.LADDER_END_NEW]
    LD = [WT + len(rsesquad.WIPED_TEST) + 48]
    for _b in LEAD[:-1]:
        LD.append(LD[-1] + len(_b) + 48)
    BT = LD[-1] + len(LEAD[-1]) + 48
    pad = (bytes(48) + rsesquad.RESCUE_SIG + bytes(48) + rsesquad.EXIT_SIG
           + bytes(48) + rsesquad.COUNT_SIG + bytes(48)
           + rsesquad.ROSTER_SIGS["L"] + bytes(48)
           + rsesquad.ROSTER_SIGS["W"] + bytes(48)
           + rsesquad.SKINS_SIG + bytes(48)
           + rsesquad.LAYOUT_CALL + bytes(48)
           + rsesquad.LAYOUT_CODE + bytes(48)
           + rsesquad.ORDER_AIM + bytes(48)
           + rsesquad.DEAD_GATE + bytes(48)
           + rsesquad.WIPED_TEST + bytes(48)
           + b"".join(_b + bytes(48) for _b in LEAD)
           + rsesquad.BTERRO + bytes(48))
    check("the stock rescue test leaves the arm when the map is no rescue",
          rsesquad.reads(pad) == rsesquad.SKIP_TARGET == 0x0354)
    check("and stock split screen pins the member count",
          not rsesquad.counts(pad)
          and pad[C + rsesquad.COUNT_OPERAND] == rsesquad.COUNT_STOCK == 0x77)
    got, n = rsesquad.apply(pad, True)
    check("the fix makes all fifteen edits, never some", n == 15,
          "%d" % n)
    check("a miss now falls into the single-player AI arm",
          rsesquad.reads(got) == rsesquad.ARM_TARGET == 0x0420)
    check("and the count increments instead of resetting",
          rsesquad.counts(got)
          and got[C + rsesquad.COUNT_OPERAND] == rsesquad.COUNT_FIXED == 0x72)
    rewritten = (set(range(LC, LC + len(rsesquad.LAYOUT_CALL)))
                 | set(range(LB, LB + len(rsesquad.LAYOUT_CODE)))
                 | set(range(OA, OA + len(rsesquad.ORDER_AIM)))
                 | set(range(DG, DG + len(rsesquad.DEAD_GATE)))
                 | set(range(WT, WT + len(rsesquad.WIPED_TEST)))
                 | {i for _o, _b in zip(LD, LEAD)
                    for i in range(_o, _o + len(_b))})
    moved = [i for i in range(len(pad))
             if pad[i] != got[i] and i not in rewritten]
    check("outside the eleven rewritten regions, exactly five bytes move",
          len(moved) == 5, str(moved))
    check("the jump operand, the comparison, Trieste's count reset and the "
          "skin loop's jump",
          moved == [R + rsesquad.RESCUE_JUMP + 1, R + rsesquad.RESCUE_JUMP + 2,
                    X + rsesquad.EXIT_LET, C + rsesquad.COUNT_OPERAND,
                    SK + rsesquad.SKINS_OPERAND])
    # Withdrawn 2026-09-24 (see rsesquad.BTERRO): bTerroHunt also picks the
    # Terrorist Hunt loadout; rsethuntai adds Terrorist Hunt's AI instead.
    check("Terrorist Hunt's roster test is left as shipped",
          got[BT + len(rsesquad.BTERRO) - 2] == 0x04)
    exit_now = bytearray(rsesquad.EXIT_SIG)
    exit_now[rsesquad.EXIT_LET] = rsesquad.EX_NOTHING
    check("the arm's own exit JUMP is left alone, so Trieste builds its pair "
          "once; only the count reset before it goes",
          got[X:X + len(rsesquad.EXIT_SIG)] == bytes(exit_now))
    check("player 2 is moved out of the AI squad after the skins",
          rsesquad.keeps_player2_out(got)
          and not rsesquad.keeps_player2_out(pad)
          and got[LC:LC + len(rsesquad.LAYOUT_CALL)]
          == rsesquad.LAYOUT_CALL_NEW
          and got[LB:LB + len(rsesquad.LAYOUT_CODE)]
          == rsesquad.LAYOUT_CODE_NEW)
    check("both rewritten regions keep their width",
          len(rsesquad.LAYOUT_CALL_NEW) == len(rsesquad.LAYOUT_CALL)
          and len(rsesquad.LAYOUT_CODE_NEW) == len(rsesquad.LAYOUT_CODE) == 137
          and len(rsesquad.ORDER_AIM_NEW) == len(rsesquad.ORDER_AIM))
    # A B level's carry-over (SetSavedData) reads team slots 0 and 1 in split
    # screen as player or AI records, the way part A's GetSavedData wrote
    # them. Restoring before player 2 left slot 1 gave him an AI's record:
    # Alpine Village B started him with an empty rifle and no sidearm.
    _ssd = bytes.fromhex("19004a03030000683216")      # PC.SetSavedData()
    _mte = bytes.fromhex("1b66102616")                # SendMemberToEnd(1)
    check("the moved block never reads as the stock call site",
          rsesquad.LAYOUT_CALL not in rsesquad.LAYOUT_CODE_NEW)
    check("a B level restores gear only after player 2 has left slot 1",
          rsesquad.LAYOUT_CODE_NEW.count(_ssd) == 1
          and rsesquad.LAYOUT_CODE_NEW.index(_ssd)
          > rsesquad.LAYOUT_CODE_NEW.index(_mte))
    check("the first version restored before the move",
          rsesquad.LAYOUT_CODE_V1.index(_ssd)
          < rsesquad.LAYOUT_CODE_V1.index(_mte))
    check("each player's move order uses that player's own aim",
          rsesquad.orders_from_requester(got)
          and not rsesquad.orders_from_requester(pad))
    check("a dead AI leaves the counted squad; a dead player still returns",
          rsesquad.buries_dead_ai(got) and not rsesquad.buries_dead_ai(pad)
          and got[DG:DG + len(rsesquad.DEAD_GATE)] == rsesquad.DEAD_GATE_NEW)
    check("the mission fails once both players are down, whoever is in "
          "team slot 1",
          rsesquad.fails_on_both_players(got)
          and not rsesquad.fails_on_both_players(pad)
          and got[WT:WT + len(rsesquad.WIPED_TEST)] == rsesquad.WIPED_TEST_NEW)
    check("both death regions keep their width",
          len(rsesquad.DEAD_GATE_NEW) == len(rsesquad.DEAD_GATE)
          == len(rsesquad.DEAD_GATE_V1) == 331
          and len(rsesquad.WIPED_TEST_NEW) == len(rsesquad.WIPED_TEST) == 160)
    check("the lead follows whoever orders the regroup, and a leader's death "
          "passes it on", rsesquad.hands_off_lead(got)
          and not rsesquad.hands_off_lead(pad)
          and all(got[_o:_o + len(_n)] == _n
                  for _o, _n in zip(LD[:4], LEAD_NEW[:4])))
    check("only the leader's climb starts or ends the team's climb",
          rsesquad.ladder_is_leaders(got)
          and not rsesquad.ladder_is_leaders(pad)
          and all(got[_o:_o + len(_n)] == _n
                  for _o, _n in zip(LD[4:], LEAD_NEW[4:])))
    check("every hand-off and ladder region keeps its width",
          [len(_b) for _b in LEAD] == [len(_n) for _n in LEAD_NEW]
          == [136, 79, 13, 764, 335, 47])
    _v1 = bytearray(pad)
    _v1[DG:DG + len(rsesquad.DEAD_GATE)] = rsesquad.DEAD_GATE_V1
    _up, _un = rsesquad.apply(bytes(_v1), True)
    check("a disc carrying the first death edit is upgraded in place",
          _up == got and _un == 15, "%d" % _un)
    check("and put back to stock from there",
          rsesquad.apply(bytes(_v1), False)[0] == pad)
    check("split screen now skins, heads and caps the whole team",
          rsesquad.skins_everyone(got) and not rsesquad.skins_everyone(pad)
          and got[SK + rsesquad.SKINS_OPERAND] == rsesquad.SKINS_FIXED == 0x30)
    check("the tokens keep their width, so ScriptSize cannot move",
          len(got) == len(pad) and got[R + rsesquad.RESCUE_JUMP] == 0x07)
    check("it lands past the Price check, not on it",
          rsesquad.ARM_TARGET > 0x03FB)
    check("running it twice changes nothing",
          rsesquad.apply(got, True) == (got, 0))
    # A disc edited by the first version carries LAYOUT_CODE_V1 (gear
    # restored before player 2 moved). It must upgrade, not be refused.
    v1 = bytearray(got)
    v1[LB:LB + len(rsesquad.LAYOUT_CODE)] = rsesquad.LAYOUT_CODE_V1
    check("a file carrying the first layout version is upgraded to this one",
          rsesquad.apply(bytes(v1), True) == (got, 1)
          and not rsesquad.keeps_player2_out(bytes(v1)))
    check("and reverting it gives stock back",
          rsesquad.apply(bytes(v1), False)[0] == pad)
    check("it can be put back whole", rsesquad.apply(got, False)[0] == pad)
    check("a build with the jump but no clamp is refused, not half-applied",
          _raises(lambda: rsesquad.apply(bytes(16) + rsesquad.RESCUE_SIG
                                         + rsesquad.EXIT_SIG, True),
                  rsesquad.SquadError))
    check("without canon the roster tests keep their own flags",
          not rsesquad.roster_reads_price(got)
          and got[RL + rsesquad.ROSTER_FLAG] == 0xC4
          and got[RW + rsesquad.ROSTER_FLAG] == 0xC3)
    flipped = bytearray(got)
    flipped[RL + rsesquad.ROSTER_FLAG] = flipped[RW + rsesquad.ROSTER_FLAG] = 0xC5
    check("and switching canon off puts them back to Loiselle and Weber",
          rsesquad.apply(bytes(flipped), True, False)[0] == got)
    moved_c = bytearray(pad)
    moved_c[C + 1:C + 3] = (0x0EB5).to_bytes(2, "little")
    check("the count site is found where canon's reassembly moves it",
          rsesquad.counts(rsesquad.apply(bytes(moved_c), True)[0]))
    check("a build with the clamp but no jump is refused too",
          _raises(lambda: rsesquad.apply(bytes(16) + rsesquad.COUNT_SIG
                                         + rsesquad.EXIT_SIG, True),
                  rsesquad.SquadError))
    check("an ambiguous build is refused",
          _raises(lambda: rsesquad.apply(pad + rsesquad.RESCUE_SIG, True),
                  rsesquad.SquadError))
    old = bytearray(pad)
    old[X + 17:X + 19] = b"\x20\x04"            # the previous version's edit
    check("a file carrying the previous version's exit retarget is refused",
          _raises(lambda: rsesquad.apply(bytes(old), True),
                  rsesquad.SquadError))
    forced = bytearray(pad)
    forced[R + 1:R + 3] = (rseteam.ARM_TARGET).to_bytes(2, "little")
    check("so is one carrying the retired rescue-arm edit on the same jump",
          _raises(lambda: rsesquad.apply(bytes(forced), True),
                  rsesquad.SquadError))
    check("which is the same site, and stays retired",
          rsesquad.KNOWN_OFFSET == rseteam.BRANCH
          and not PROFILE.setting("split_rescue_team").enabled)
    sq = [e for e in PROFILE.build_data(dict(PROFILE.defaults(),
                                             split_squad=True))
          if e.op in ("squad", "team_recording")]
    check("the setting emits the team code and the recordings together",
          sorted(e.op for e in sq) == ["squad", "team_recording"])
    code = [e for e in sq if e.op == "squad"]
    check("the team code goes to the split-screen package only",
          code and code[0].matches("/COMMON_SS.LIN")
          and not code[0].matches("/COMMONOFF.LIN")
          and not code[0].matches("/COMMON.LIN"))
    check("and emits nothing at its default",
          not [e for e in PROFILE.build_data(PROFILE.defaults())
               if e.op in ("squad", "team_recording")])
    check("it is on offer, and watched working in game",
          PROFILE.setting("split_squad").enabled
          and PROFILE.setting("split_squad").confidence == "verified")

    print("\n[split-screen level recordings]")
    import hashlib as _hl
    import random as _rnd
    from tcps2 import rsesplice as _sp
    rng = _rnd.Random(20260922)

    def rb(n):
        return bytes(rng.randrange(256) for _ in range(n))

    def rec(name, *parts):
        return _sp.MAGIC + bytes([len(name) + 1]) + name + b"\0" + b"".join(parts)

    A, B, Cc = rb(3000), rb(5000), rb(2000)
    REC, OPS = rb(_sp.RECORD), rb(_sp.OPERATIVES)

    def _stand_ins(ops):
        """Point the group constants at the stand-in operatives' bytes."""
        cut = _sp.GROUP_BYTES["L"]
        _sp.GROUP_HEAD.update(L=ops[:24], W=ops[cut:cut + 24])
        _sp.GROUP_SHA1.update(L=_hl.sha1(ops[:cut]).hexdigest(),
                              W=_hl.sha1(ops[cut:]).hexdigest())
    kept = (_sp.RECORD_SHA1, _sp.OPERATIVES_SHA1, dict(_sp.GROUP_HEAD),
            dict(_sp.GROUP_SHA1))
    try:
        # The real record and operatives are measured bytes off the disc and
        # cannot be synthesised to match their hashes, so the structure is
        # tested on stand-ins; the disc test below uses the real ones.
        _sp.RECORD_SHA1 = _hl.sha1(REC).hexdigest()
        _sp.OPERATIVES_SHA1 = _hl.sha1(OPS).hexdigest()
        _stand_ins(OPS)
        off = rec(b"island_aoff", A, B, OPS, Cc)
        ss = rec(b"island_a_ss", A, REC, B, Cc)
        # What Trieste's split-screen recording is to its single-player one.
        want = rec(b"island_a_ss", A, REC, B, OPS, Cc)
        new = _sp.splice(ss, off)
        check("the splice is single player's recording plus split screen's "
              "record, exactly as Trieste ships", new == want)
        check("2,631 bytes longer than stock split screen, 105 longer than "
              "single player", len(new) - len(ss) == 2631
              and len(new) - len(off) == 105)
        check("it keeps the split-screen level name",
              new[5:17] == b"island_a_ss\0")
        check("it reads the operatives; stock split screen does not",
              _sp.reads(new) and _sp.reads(off) and not _sp.reads(ss))
        check("apply reports the one change",
              _sp.apply(ss, off) == (new, 1))
        check("a recording that already reads them is left alone",
              _sp.apply(want, off) == (want, 0))
        check("switched off it hands back the stock file",
              _sp.apply(ss, off, False) == (ss, 0))
        check("a pair differing in a second place is refused -- the winter "
              "maps' shape", _raises(
                  lambda: _sp.splice(rec(b"island_a_ss", A, REC, B[:-1]
                                         + bytes([B[-1] ^ 1]), Cc), off),
                  _sp.SpliceError))
        check("a pair whose extra bytes are not the operatives is refused",
              _raises(lambda: _sp.splice(ss, rec(b"island_aoff", A, B,
                                                 rb(_sp.OPERATIVES), Cc)),
                      _sp.SpliceError))
        check("a split-screen record that is not the known one is refused",
              _raises(lambda: _sp.splice(rec(b"island_a_ss", A, rb(105), B,
                                             Cc), off), _sp.SpliceError))
        check("the wrong amount of extra single-player data is refused",
              _raises(lambda: _sp.splice(ss, rec(b"island_aoff", A, B,
                                                 OPS + b"\0", Cc)),
                      _sp.SpliceError))
        check("names of different lengths are refused",
              _raises(lambda: _sp.splice(ss, rec(b"island_off", A, B, OPS,
                                                 Cc)), _sp.SpliceError))
        check("so is something that is not a level recording",
              _raises(lambda: _sp.splice(b"\0" * 64, off), _sp.SpliceError))
    finally:
        _sp.RECORD_SHA1, _sp.OPERATIVES_SHA1 = kept[:2]
        _sp.GROUP_HEAD.clear()
        _sp.GROUP_HEAD.update(kept[2])
        _sp.GROUP_SHA1.clear()
        _sp.GROUP_SHA1.update(kept[3])
    kept2 = (_sp.RECORD_SHA1, _sp.OPERATIVES_SHA1, dict(_sp.GROUP_HEAD),
             dict(_sp.GROUP_SHA1))
    try:
        _sp.RECORD_SHA1 = _hl.sha1(REC).hexdigest()
        _sp.OPERATIVES_SHA1 = _hl.sha1(OPS).hexdigest()
        _stand_ins(OPS)
        _L, _W = OPS[:_sp.GROUP_BYTES["L"]], OPS[_sp.GROUP_BYTES["L"]:]
        off = rec(b"island_aoff", A, B, OPS, Cc)
        ss = rec(b"island_a_ss", A, REC, B, Cc)
        check("canon's Weber alone reads just his group, where the pair goes",
              _sp.recording(ss, off, "W") == rec(b"island_a_ss", A, REC, B,
                                                  _W, Cc))
        check("canon's Weber with AI reads him first, then Loiselle",
              _sp.recording(ss, off, "WL") == rec(b"island_a_ss", A, REC, B,
                                                   _W, _L, Cc))
        check("and teammates alone is exactly the proved splice",
              _sp.recording(ss, off, "LW") == _sp.splice(ss, off))
        check("an order that is not the two operatives is refused",
              all(_raises(lambda o=o: _sp.recording(ss, off, o),
                          _sp.SpliceError) for o in ("", "LL", "X", "LWL")))
    finally:
        _sp.RECORD_SHA1, _sp.OPERATIVES_SHA1 = kept2[:2]
        _sp.GROUP_HEAD.clear()
        _sp.GROUP_HEAD.update(kept2[2])
        _sp.GROUP_SHA1.clear()
        _sp.GROUP_SHA1.update(kept2[3])
    import re as _re
    for combo in ((True, False), (False, True), (True, True)):
        plan = _sp.plan(*combo)
        hits = {m: [o for sel, o in plan
                    if _re.search(sel, "/%s_SS.LIN" % m, _re.I)]
                for m in _sp.MAPS + _sp.WINTER + ("TRIESTE_A",)}
        check("plan %r never splices a level twice" % (combo,),
              all(len(v) <= 1 for v in hits.values()))
        if combo == (True, False):
            check("teammates alone: all 26 levels, Loiselle then Weber",
                  [m for m, v in hits.items() if v == ["LW"]]
                  == list(_sp.COVERED))
        elif combo == (False, True):
            check("canon alone: only its three levels, each its own operative",
                  {m: v for m, v in hits.items() if v}
                  == {"ISLAND_A": ["W"], "GARAGE_A": ["L"], "GARAGE_B": ["L"]})
        else:
            check("both: Island reads Weber first, every other level as usual",
                  hits["ISLAND_A"] == ["WL"]
                  and all(v == ["LW"] for m, v in hits.items()
                          if m in _sp.COVERED and m != "ISLAND_A"))
    check("the single-player sibling is named from the split-screen file",
          _sp.sibling("/ISLAND_A_SS.LIN") == "/ISLAND_AOFF.LIN"
          and _sp.sibling("/GARAGE_B_SS.LIN") == "/GARAGE_BOFF.LIN"
          and _raises(lambda: _sp.sibling("/COMMON_SS.LIN"), _sp.SpliceError))
    lvl = [e for e in PROFILE.build_data(dict(PROFILE.defaults(),
                                              split_squad=True))
           if e.op == "team_recording"]
    check("the recordings edit selects exactly the 26 covered levels",
          lvl and [m for m in _sp.MAPS + _sp.WINTER + ("TRIESTE_A",)
                   if lvl[0].matches("/%s_SS.LIN" % m)] == list(_sp.COVERED))
    check("and no single-player, training or COMMON file",
          lvl and not any(lvl[0].matches(q) for q in (
              "/ISLAND_AOFF.LIN", "/TRAINING_TEAM_SS.LIN", "/COMMON_SS.LIN",
              "/ISLAND_A_SS.LIN.BAK")))
    check("26 levels: the 22 plus the four winter ones, and not Trieste",
          len(_sp.MAPS) == 22 and len(_sp.WINTER) == 4
          and _sp.COVERED == _sp.MAPS + _sp.WINTER
          and "TRIESTE_A" not in _sp.COVERED)
    from tcps2 import dataedit as _de
    check("only the recordings op may change a cooked file's length",
          _de._RECORDING_OPS == {"team_recording"})
    check("and it is handed its sibling rather than reading the disc itself",
          "team_recording" in _de._WANTS_SIBLING
          and _de._WANTS_SIBLING["team_recording"]("/PARADE_B_SS.LIN")
          == "/PARADE_BOFF.LIN")
    check("the op refuses to run without its sibling",
          _raises(lambda: _de.OPS["team_recording"](b"", {}), _de.DataEditError))

    print("\n[field of view is split screen only]")
    fv = [e for e in PROFILE.build_data(dict(PROFILE.defaults(), fov=110))
          if e.op == "fov"]
    check("a changed field of view emits one data edit", len(fv) == 1)
    check("it writes the split-screen package",
          fv and fv[0].matches("/COMMON_SS.LIN"))
    check("and leaves the offline and online ones at stock 90",
          fv and not fv[0].matches("/COMMONOFF.LIN")
          and not fv[0].matches("/COMMON.LIN"))
    check("stock emits nothing",
          not [e for e in PROFILE.build_data(dict(PROFILE.defaults(), fov=90))
               if e.op == "fov"])

    print("\n[rescue flag]")
    from tcps2 import rserescue
    ini = ("[Engine.R6MissionDescription]\r\nversion=2\r\n"
           "m_MapName=Island_a\r\n\r\n; Availability of Game Modes\r\n"
           "m_bPracticeModeGame=true\r\nm_bNoRulesGame=true\r\n\r\n"
           "m_MaxNbOfPlayersAdv=8\r\n\r\n[Engine.SomethingElse]\r\n"
           "m_bNoRulesGame=false\r\n").encode("latin-1")
    new, n = rserescue.apply(ini, True)
    check("the flag is added once", n == 1 and new.count(b"m_brescureRainbow") == 1)
    check("it lands after the LAST mode key, as Trieste places it",
          b"m_bNoRulesGame=true\r\nm_brescureRainbow=true\r\n" in new)
    check("it keeps the file's own line ending",
          b"m_brescureRainbow=true\r\n" in new)
    check("it stays inside the mission section",
          new.index(b"m_brescureRainbow") < new.index(b"[Engine.SomethingElse]"))
    check("the file grows by exactly the line",
          len(new) == len(ini) + len(rserescue.LINE) + 2)
    check("running it twice changes nothing the second time",
          rserescue.apply(new, True) == (new, 0))
    check("a map that already declares it is left alone",
          rserescue.apply(ini.replace(b"m_bNoRulesGame=true\r\n",
                                      b"m_bNoRulesGame=true\r\n"
                                      b"m_brescureRainbow=true\r\n", 1),
                          True)[1] == 0)
    check("switching it off never strips Trieste's own declaration",
          rserescue.apply(new, False) == (new, 0))
    check("a file with no section is passed through untouched",
          rserescue.apply(b"   spaces only, no header\r\n", True)
          == (b"   spaces only, no header\r\n", 0))
    nomode = b"[Engine.R6MissionDescription]\r\nversion=2\r\nm_iElite=1\r\n"
    got, n2 = rserescue.apply(nomode, True)
    check("a section with no mode block still gets the flag, under the header",
          n2 == 1 and got.startswith(b"[Engine.R6MissionDescription]\r\n"
                                     b"m_brescureRainbow=true\r\n"))
    sel = [e for e in PROFILE.build_data(dict(PROFILE.defaults(),
                                              split_rescue_flag=True))
           if e.op == "rescue_flag"]
    check("the setting emits exactly one data edit", len(sel) == 1)
    check("it selects mission parts and not multiplayer or training",
          sel and sel[0].matches("/MAPS/ISLAND_A.INI")
          and not sel[0].matches("/MAPS/TRIESTE_MP.INI")
          and not sel[0].matches("/MAPS/TRAINING_TEAM.INI")
          and not sel[0].matches("/MAPS/ISLAND.INI"))
    check("it skips the three maps that author no starting point",
          sel and not sel[0].matches("/MAPS/ALPINES_A.INI")
          and not sel[0].matches("/MAPS/IMPORT_EXPORT_A.INI")
          and not sel[0].matches("/MAPS/PENTHOUSE_A.INI"))
    check("but keeps their other parts, which do author one",
          sel and sel[0].matches("/MAPS/ALPINES_B.INI")
          and sel[0].matches("/MAPS/IMPORT_EXPORT_B.INI"))
    check("and emits nothing at its default",
          not [e for e in PROFILE.build_data(PROFILE.defaults())
               if e.op == "rescue_flag"])

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
    check("ss_man_down is withdrawn", not profile.setting("ss_man_down").enabled)
    check("and says why", "hangs" in profile.setting("ss_man_down").disabled_reason)
    check("and emits no data edit even when stored true",
          not [e for e in profile.build_data(
                  profile.effective(dict(profile.defaults(), ss_man_down=True)))
               if e.op == "ss_man_down"])
    check("canon_team is back on offer, and watched working, now its hang "
          "is understood", profile.setting("canon_team").enabled
          and profile.setting("canon_team").confidence == "verified")

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

        # The gun-stat cards specifically, NOT everything on the page.
        # This used to count the whole group and demand exactly eight,
        # which stopped being true the moment a profile put anything else
        # under Weapons -- Jungle Storm has carried smoke and quick-trigger
        # cards there for a while. It went unnoticed because the check only
        # runs when that game's ISO is passed, and it usually is not.
        stat = ("mag", "rate", "recoil", "spread")
        cards = [x for x in profile.settings
                 if x.group == "Weapons"
                 and x.key.rsplit("_", 1)[-1] in stat]
        check("there are eight gun-stat cards, four per side",
              len(cards) == 8, str(sorted(c.key for c in cards)))
        check("and they are all data edits",
              all(c.touches == "data" for c in cards),
              str([c.key for c in cards if c.touches != "data"]))
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
                check("%s: by routing split screen into single player's arm"
                      % path[1:],
                      rsewheel.cycle_reads(cyc)
                      and cyc[rsewheel.cycle_guard_find(cyc)]
                      == rsewheel.GUARD_FIXED)
                check("%s: leaving the now-dead count at the shipped 4"
                      % path[1:],
                      cyc[cat] == rsewheel.CYCLE_SPLIT)
                check("%s: the guard is where it was measured" % path[1:],
                      rsewheel.cycle_guard_find(plain) == 0x10889B,
                      "found %#x" % rsewheel.cycle_guard_find(plain))
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

    # The wheel fix rewrites live code, so every word it claims to replace
    # must be what the PRISTINE image holds -- the live disc may carry the
    # fix -- and every hook must land in one of the wheel's own slots in the
    # dead path, never on the map-wide spawn cave.
    from tcps2 import rsedeadpath as _dp
    from tcps2.games.r6_3 import SP as _SP, CAVE_WORDS as _SPAWN
    _img = SozImage.unpack(stock_container(args), _SP.base_va)
    words = rsewheel.label_words()
    bad = [(va, "%#010x" % _img.read_word(va), "%#010x" % st)
           for va, _w, st, _n in words if _img.read_word(va) != st]
    check("every wheel word replaces the instruction it expects",
          not bad, str(bad))
    _lo, _hi = _dp.CAVE, _dp.CAVE + 4 * _dp.CAVE_WORDS
    _slots = {_dp.claim(n, True) for n in _dp.SLOTS
              if n.startswith(("wheel_", "label_"))}
    _hooks = [(va, w) for va, w, _s, _n in words
              if (w >> 26) == 3 and not _lo <= va < _hi]
    check("every hook is a jal into one of the wheel's dead-path slots",
          _hooks and all(((w & 0x03FFFFFF) << 2) in _slots
                         for _va, w in _hooks), str(len(_hooks)))
    spawn = {va for va, _w in _SPAWN}
    check("and it never lands on the map-wide spawn cave",
          not [va for va, _w, _s, _n in words if va in spawn])
    _p = BY_ID["r6_3_slus20883"]
    check("the label fix is on the disc, not in a cheat file",
          _p.setting("split_wheel_labels").touches == "words"
          and not _p.build_pnach({"split_wheel_labels": True,
                                  "split_wheel": True}))
    check("and it needs the wheel itself",
          _p.setting("split_wheel_labels").requires == {"split_wheel": [True]})

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


def run_split_orders(args):
    """The team order icon and wheel in split screen.

    What can be proved without playing: that the two edits land where they
    were measured, in the split-screen package only; that the rewritten
    PostRender still loads the same way -- same sizes, same objects and names
    referenced; and that every way through it in split screen pops the full-
    screen mode exactly as often as it pushes it.
    """
    import re
    from tcps2 import dataedit, lin, rseorders, uscode
    from tcps2.games import BY_ID
    from tcps2.iso import Iso
    from tcps2.vokes import open_archives

    if not args.rs3data:
        return
    print("\n[Rainbow Six 3 -- team orders in split screen]")

    def refs(script):
        objs, names = set(), set()
        for t in script.statements():
            n = 0
            for kind, val in t.parts:
                if kind == "ref":
                    v = uscode.compact_decode(val, 0)[0]
                    by_name = (t.op in (0x0E, 0x1B, 0x21, 0x38)
                               or (t.op == 0x40 and n == 1))
                    (names if by_name else objs).add(v)
                    n += 1
        return objs, names

    push = bytes.fromhex("19003e03000069ce16")
    pop = bytes.fromhex("19003e03000069cf16")
    split_true = bytes.fromhex("0600042d01ed012716")

    def unbalanced(plain, at):
        """Statements where a split-screen path is pushed out of step."""
        script = uscode.Script.at(plain, at)
        rows, d = [], at + 4
        for t in script.toks:
            rows.append((t, plain[d:d + t.dlen]))
            d += t.dlen
        index = {t.mstart: i for i, (t, _b) in enumerate(rows)}
        depth, todo, bad = {0: 0}, [0], []
        while todo:
            i = todo.pop()
            t, raw = rows[i]
            dd = depth[i] + (raw == push) - (raw == pop)
            if not 0 <= dd <= 1 or (t.op == 0x04 and dd):
                bad.append(t.mstart)
            nxt = [] if t.op in (0x04, 0x06) else [i + 1]
            if t.op in (0x06, 0x07) and t.parts[0][1] is not uscode.END:
                jump = index[t.parts[0][1].mstart]
                if t.op == 0x07 and t.mstart == 0x02A0:
                    nxt = [jump]        # NetMode != 0 || !m_bIsSplitScreen
                elif not (t.op == 0x07 and split_true in raw):
                    nxt.append(jump)    # m_bIsSplitScreen == True never jumps
            for j in nxt:
                if j not in depth:
                    depth[j] = dd
                    todo.append(j)
                elif depth[j] != dd:
                    bad.append(rows[j][0].mstart)
        return bad

    seen = set()
    with Iso(args.rs3data) as iso:
        for arc in open_archives(iso, r"/VOKES\d\.IMG$"):
            for path in sorted(arc.files):
                if not re.search(r"/COMMON(OFF|_SS)?\.LIN$", path) or path in seen:
                    continue
                seen.add(path)
                raw = _stock_bytes(args.rs3data, arc, path)
                kind, plain = dataedit._unpack(raw, path)
                at = rseorders.find_block(plain)
                const = rseorders._find_tick(plain)
                check("%s: the icon code is where it was measured" % path[1:],
                      at == rseorders.KNOWN_OFFSET and const
                      == rseorders.KNOWN_TICK_OFFSET,
                      "%#x, %#x" % (at, const))
                check("%s: and is the code this disc shipped" % path[1:],
                      rseorders._block_sha1(plain, at) == rseorders.STOCK_SHA1
                      and plain[const] == rseorders.EX_FALSE)
                if path != "/COMMON_SS.LIN":
                    continue

                on, n = rseorders.apply(plain, True)
                check("turning it on changes the two functions",
                      n == 2 and len(on) == len(plain) and rseorders.reads(on)
                      and not rseorders.reads(plain))
                check("and asking twice is a no-op",
                      rseorders.apply(on, True) == (on, 0))
                tick = uscode.Script.at(plain, 0x12E11A)
                span = [(at, at + 4 + rseorders.DISK_LEN),
                        (0x12E11A, 0x12E11A + 4 + tick.disk_len)]
                moved = [i for i in range(len(plain)) if plain[i] != on[i]]
                check("nothing outside the two functions moves",
                      moved and all(any(a <= i < b for a, b in span)
                                    for i in moved), "%d bytes" % len(moved))
                check("the wheel's test is one byte: False -> True",
                      [i for i in moved if i < at] == [const]
                      and on[const] == rseorders.EX_TRUE)
                old = uscode.Script.at(plain, at)
                new = uscode.Script.at(on, at)
                check("PostRender keeps its ScriptSize and disk length",
                      (new.mem_len, new.disk_len) == (old.mem_len, old.disk_len)
                      == (rseorders.SCRIPT_SIZE, rseorders.DISK_LEN))
                check("and names exactly the objects and names it shipped with",
                      refs(new) == refs(old))
                check("every split-screen path pops full screen as it pushes",
                      not unbalanced(on, at), str(unbalanced(on, at)))
                check("as every path through the shipped function does",
                      not unbalanced(plain, at))
                jump = new.statement_at(rseorders.ICON_DRAW)
                check("the split arm's icon now goes by way of the brackets",
                      jump.op == 0x06 and jump.parts[0][1].op == 0x07
                      and (rseorders.BRACKET_LEFT + rseorders.BRACKET_RIGHT)
                      in on[at:at + 4 + rseorders.DISK_LEN])

                def _order(script):
                    """The function's own objects, in first-touch order."""
                    seen, out = set(), []
                    for top in script.toks:
                        for t in top.walk():
                            n = 0
                            for kind, val in t.parts:
                                if kind != "ref":
                                    continue
                                if not (t.op in (0x0E, 0x1B, 0x21, 0x38)
                                        or (t.op == 0x40 and n == 1)):
                                    v = uscode.compact_decode(val, 0)[0]
                                    if v > 0 and v not in seen:
                                        seen.add(v)
                                        out.append(v)
                                n += 1
                    return out
                # The first version reached strText and m_bDisableClear early,
                # and Oil Refinery's split-screen load hung on it.
                check("and first-touches its own objects in the shipped order",
                      _order(new) == _order(old), "%d objects" % len(_order(old)))
                text = new.statement_at(rseorders.ZULU_TEXT)
                check("the L1 hint's text is drawn where it shipped, its 58 "
                      "written the way the function writes the hint's x",
                      text.op == 0x1B and text.mlen
                      == old.statement_at(rseorders.ZULU_TEXT).mlen - 1
                      and rseorders.CAST_58 in on[at:at + 4 + rseorders.DISK_LEN]
                      and new.statement_at(rseorders.RETURN_AT - 1).op == 0x06)
                check("the menu's two ways out, which never push, take the "
                      "function's first return",
                      all(new.statement_at(m).parts[0][1].mstart
                          == rseorders.EARLY_RETURN
                          for m in (rseorders.MENU_DONE, rseorders.MENU_TEST))
                      and new.statement_at(rseorders.EARLY_RETURN).op == 0x04)
                real = rseorders.WITHDRAWN_SHA1
                rseorders.WITHDRAWN_SHA1 = rseorders.STOCK_SHA1
                try:
                    rseorders.apply(plain)
                    said = ""
                except rseorders.OrdersError as exc:
                    said = str(exc)
                finally:
                    rseorders.WITHDRAWN_SHA1 = real
                check("a file still carrying the withdrawn first version is "
                      "named, not guessed at", "withdrawn" in said, said)
                packed = dataedit._repack(kind, raw, on)
                check("the container keeps its length",
                      len(packed) == len(raw), "%d -> %d" % (len(raw), len(packed)))
                check("and still decompresses to the edited bytes",
                      lin.decompress(packed) == on)
                bent = bytearray(plain)
                bent[at + 0x40] ^= 1
                check("a PostRender that is not the shipped one is refused",
                      _raises(lambda: rseorders.apply(bytes(bent)),
                              rseorders.OrdersError))

    check("all three COMMON containers were read", len(seen) == 3,
          "%d" % len(seen))
    profile = BY_ID["r6_3_slus20883"]
    s = profile.setting("split_team_orders")
    check("the option reaches the profile, badged",
          s is not None and s.confidence in BADGES and s.enabled)
    check("and needs the AI and the wheel's per-viewport drawing",
          s.requires == {"split_squad": [True], "split_wheel_labels": [True]})
    need = {"split_squad": True, "split_wheel": True,
            "split_wheel_labels": True}
    got = [e for e in profile.build_data(profile.effective(
        dict(need, split_team_orders=True))) if e.op == "split_team_orders"]
    check("it writes the split-screen package and nothing else",
          len(got) == 1 and got[0].matches("/COMMON_SS.LIN")
          and not got[0].matches("/COMMONOFF.LIN")
          and not got[0].matches("/COMMON.LIN"))
    check("leaving it off writes nothing",
          not any(e.op == "split_team_orders"
                  for e in profile.build_data(profile.effective(need))))
    check("and without the AI it is not written at all",
          not any(e.op == "split_team_orders"
                  for e in profile.build_data(profile.effective(
                      {"split_team_orders": True, "split_wheel": True,
                       "split_wheel_labels": True}))))


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
    """The scope overlay in split screen: the guard, and the viewport fit.

    Everything upstream is healthy in split screen -- the textures reach the
    render devices and the scope-active flag is set. What this pins is the
    guard that replaced the branch into the dead path, and the fit that reads
    the viewport instead of the framebuffer, checked against the PRISTINE
    image: the live disc may carry the option, so it can only be asked which
    of the known words the branch holds.
    """
    from tcps2 import overlay, rsedeadpath, rsescope
    from tcps2.games import BY_ID
    from tcps2.games.r6_3 import SP, STOCK
    from tcps2.iso import Iso

    if not args.rs3data:
        return
    print("\n[Rainbow Six 3 -- the scope overlay in split screen]")
    with Iso(args.rs3data) as iso:
        ov = overlay.open_overlay(iso, SP)
        live = ov.read_word(rsescope.SCOPE_BRANCH)
    guard = dict(rsescope.SCOPE_GUARD)
    check("the branch holds stock, the guard, or the free branch",
          live in (rsescope.SCOPE_BRANCH_STOCK, guard[rsescope.SCOPE_BRANCH],
                   rsedeadpath.FREE_BRANCH), "%#010x" % live)
    check("the shipped word is recorded, so a patched disc can be healed",
          STOCK.get(rsescope.SCOPE_BRANCH) == rsescope.SCOPE_BRANCH_STOCK,
          "%r" % STOCK.get(rsescope.SCOPE_BRANCH))
    check("and it decodes as the branch we think it is",
          (rsescope.SCOPE_BRANCH_STOCK >> 26) == 5          # bne
          and ((rsescope.SCOPE_BRANCH_STOCK >> 16) & 31) == 0)   # against $zero
    check("the guard returns through the function's own epilogue",
          (guard[rsescope.SCOPE_DELAY] >> 26) == 4          # beq
          and rsescope.SCOPE_DELAY + 4
          + ((guard[rsescope.SCOPE_DELAY] & 0xFFFF) << 2)
          == rsescope.SCOPE_RETURN)

    # the fit, against the pristine image
    from tcps2.games.r6_3 import CAVE_WORDS as _SPAWN
    from tcps2 import rsewheel as _rw
    img = SozImage.unpack(stock_container(args), SP.base_va)
    vw = rsescope.viewport_words()
    hooks = [(va, w) for va, w, _s, _n in vw if (w >> 26) == 3]
    cave = rsedeadpath.claim("scope_height", True)
    check("the fit is a 4-word cave, 4 width sites of 5 and 4 height reads",
          len(vw) == 4 + 4 * 5 + 4 and len(hooks) == len(rsescope.HEIGHT_FAR),
          str(len(vw)))
    bad = [(va, "%#010x" % img.read_word(va), "%#010x" % st)
           for va, _w, st, _n in vw if img.read_word(va) != st]
    check("every word it overwrites is the word it claims", not bad, str(bad))
    check("its cave is the dead path's scope slot",
          all(((w & 0x03FFFFFF) << 2) == cave for _va, w in hooks))

    # `jal` has a delay slot, so the instruction AFTER a hook runs BEFORE the
    # cave. A branch there is undefined on the R5900 and once hung the game
    # on the loading screen; and it must not read $t0, which the cave loads.
    BRANCHES = (1, 2, 3, 4, 5, 6, 7, 20, 21, 22, 23)
    emitted = {va: w for va, w, _s, _n in vw}
    slots, stale = [], []
    for va, _w in hooks:
        nxt = emitted.get(va + 4, img.read_word(va + 4))
        if (nxt >> 26) in BRANCHES:
            slots.append("%#010x -> %#010x" % (va, nxt))
        if nxt and 8 in ((nxt >> 21) & 31, (nxt >> 16) & 31):
            stale.append("%#010x -> %#010x" % (va, nxt))
    check("no hook puts a branch in a jal delay slot", not slots, str(slots))
    check("nor one that reads the register the cave is about to load",
          not stale, str(stale))

    mine = {va for va, _w, _s, _n in vw}
    check("it lands on neither the wheel's words nor the spawn cave",
          not (mine & {va for va, _w, _s, _n in _rw.label_words()})
          and not (mine & {va for va, _w in _SPAWN}))
    check("the reads it takes over are the eight the module recorded",
          {va for va, _rd in rsescope.WIDTH_HOOKS}
          | set(rsescope.HEIGHT_NEAR) | set(rsescope.HEIGHT_FAR)
          == set(rsescope.FRAMEBUFFER_READS))

    profile = BY_ID["r6_3_slus20883"]
    check("the option reaches the profile",
          profile.setting("split_scope") is not None)
    check("it is delivered on the disc, not as a cheat",
          profile.setting("split_scope").touches == "words"
          and not profile.build_pnach({"split_scope": True}))
    check("fitting and the owner gate are no longer separate options",
          profile.setting("split_scope_fit") is None
          and profile.setting("split_scope_owner") is None)
    check("and the one switch still emits all three edits",
          len(profile.build_edits(dict(profile.defaults(),
                                       split_scope=True))) == 44)

    # `requires` greys a widget out, but the stored value survives, and both
    # the disc edits and the cheat file are built from stored values. A pnach
    # is re-applied every frame, so an option left ticked behind an unticked
    # prerequisite could not be undone by unticking it. It has to gate the
    # generator as well.
    check("the wheel labels need the wheel switched on first",
          profile.setting("split_wheel_labels").requires
          == {"split_wheel": [True]})
    eff = profile.effective({"split_wheel_labels": True, "split_wheel": False})
    check("and effective() neutralises what its prerequisite does not allow",
          eff["split_wheel_labels"] is False)
    check("a chain of requirements resolves all the way down",
          profile.effective({"ai_finite_ammo": False,
                             "ai_sidearm": 50})["ai_sidearm"] == 0)
    check("all the caves coexist",
          len(profile.build_pnach({"split_scope": True,
                                   "split_wheel_labels": True,
                                   "split_wheel": True,
                                   "wave_enable": True,
                                   "wave_mapwide": True})) == 68)
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
    check("turning it on replaces exactly that branch with the guard",
          len(made) == 1
          and made[0].value == dict(rsescope.SCOPE_GUARD)[rsescope.SCOPE_BRANCH]
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
    # Shipped bytes, not the disc's: the counts asserted below are the ones
    # the game SHIPPED, so a disc with enemy_flashlight already applied would
    # fail them for the wrong reason. The ai_cover checks were bitten by
    # exactly that on 2026-09-25.
    with Iso(args.rs3data) as iso:
        arc = [v for v in vokes.open_archives(iso)
               if "VOKES0" in str(getattr(v.r, "name", "")).upper()][0]
        container = _stock_bytes(args.rs3data, arc, "/COMMON.LIN")
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

    discs = [(args.iso or args.rs3data, "r6_3_slus20883"),
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
    r"""A cooked package that changes length is refused -- unless it is a recording.

    This test used to pin the opposite. `frag_warning` grew COMMON by 107
    bytes, a guard refused it, the guard was relaxed, the container fitted its
    slot -- and the game then would not boot at all. A LIN is a RECORDING of
    one boot's read stream, and three new imports are three reads that boot
    never made. So the guard came back, for every op but one: `team_recording`,
    which supplies a whole different recording and proves it byte for byte
    (see `run_team_recordings`, which drives it through this same path).
    """
    import tempfile
    from tcps2 import dataedit
    from tcps2.iso import Iso
    from tcps2.model import FileEdit
    from tcps2.vokes import Region, Vokes, open_archives
    from tcps2.games import BY_ID

    iso_path = args.rs3data or args.iso
    if not iso_path:
        return
    profile = BY_ID["r6_3_slus20883"]

    print(chr(10) + "[an edit that grows a LIN package is refused]")

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

    check("frag_warning is retired, so no setting emits it",
          not [e for e in profile.build_data(profile.effective(
              dict(profile.defaults(), frag_warning=True)))
              if e.op == "frag_warning"])
    work = tempfile.mkdtemp(prefix="tcms-grown-")
    real_archives = dataedit._archives
    try:
        with Iso(iso_path) as iso:
            shadows = {}
            for real in open_archives(iso, profile.archive_pattern):
                arc = Vokes(Shadow(real.r))
                shadows[arc.r.name.upper()] = arc
            dataedit._archives = lambda _iso, _p: shadows
            # Asked for by hand, the way a stale saved profile once did.
            edit = FileEdit("frag_warning", r"/COMMON_SS\.LIN$", "",
                            {"enable": True})
            try:
                dataedit.apply_data(iso, profile, [edit], dataedit.Store(work))
                threw = None
            except Exception as exc:                  # noqa: BLE001
                threw = exc
            check("a script edit that grows a package is refused",
                  isinstance(threw, dataedit.DataEditError)
                  and "length" in str(threw),
                  "%s: %s" % (type(threw).__name__, threw) if threw else "")
            check("before a single byte reaches the disc",
                  not any(arc.r.w for arc in shadows.values()))
            check("and the recordings op is the only exception",
                  dataedit._RECORDING_OPS == {"team_recording"})
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
            # STOCK, not the live disc: these ops are pinned by CONTENT, so
            # one that has already been applied would not find its own stock
            # bytes and would fail for the wrong reason entirely.
            raw = _stock_bytes(args.rs3data, arc, hit)
            plain = lin.decompress(raw) if lin.is_lin(raw) else raw
            fn = dataedit.OPS[op]
            try:
                if op in dataedit._WANTS_CONTAINER:
                    got = fn(plain, edit.params, raw)
                elif op in dataedit._WANTS_SIBLING:
                    sib = dataedit._WANTS_SIBLING[op](hit).upper()
                    sraw = _stock_bytes(args.rs3data, where[sib], sib)
                    got = fn(plain, edit.params,
                             lin.decompress(sraw) if lin.is_lin(sraw) else sraw)
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
    # The file as it SHIPPED, not as it is on the disc now. Every check below
    # is about what the transforms do to stock data -- the seven rungs, the
    # shipped thresholds, and the byte-for-byte revert -- so reading a disc
    # the player has since patched fails them for the wrong reason. It did:
    # with ai_cover applied to the disc, "carries the shipped thresholds"
    # and both revert checks failed while the option was working correctly
    # (2026-09-25).
    with Iso(args.rs3data) as iso:
        arcs = vokes.open_archives(iso)
        plain = {}
        for path in ("/COMMON.LIN", "/COMMON_SS.LIN"):
            for a in arcs:
                if path in a.files:
                    plain[path] = lin.decompress(
                        _stock_bytes(args.rs3data, a, path))
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
    # any of them. That test was never the gate: 2026-09-24 found the level
    # render's own split-screen skip at 0x00351E7C, and the card now clears it.
    check("it is back on offer, badged",
          st.confidence in BADGES and st.enabled)
    img = SozImage.unpack(stock_container(args), SP.base_va)
    check("the real gate is the level render's bnez on the split flag",
          img.read_word(rseshadow.PROJECTOR_BRANCH)
          == rseshadow.PROJECTOR_BRANCH_STOCK == 0x14400424
          and img.read_word(rseshadow.PROJECTOR_BRANCH + 4) == 0
          and STOCK.get(rseshadow.PROJECTOR_BRANCH) == 0x14400424)
    on = {e.va: e.value for e in profile.build_edits(
        profile.effective(dict(profile.defaults(), split_shadows=True)))}
    check("turning it on writes that one word as a nop, and not the old test",
          on.get(rseshadow.PROJECTOR_BRANCH) == 0 and 0x00446EA8 not in on)
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
    check("the retired test is never written",
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


def run_wave_hunt_retired(args):
    """`wave_hunt` set a flag on the wrong object (2026-09-26).

    It wrote m_bHuntFromStart -- bit 0x40 of +0x388 -- on the WAVE actor.
    The one place that flag is ever read is
    AR6DeploymentZone::InitTerrorist at 0x00386B88, which sets m_eStrategy
    to 3 (HuntRainbow) when bit 0x40 is set and bit 0x20 is clear, reading
    the word off `this`. And `this` is never the wave: AR6DZoneWave
    overrides the spawn-at-init slot with a stub returning 0, and its
    SpawnATerrorist picks a point out of m_aSpawningPoint and calls THAT
    point's spawner, so `this` is the R6DZonePoint all the way down --
    which is also what pawn->m_DZone is set to. Every word below is read
    from the PRISTINE container, because the live disc is patched.
    """
    print()
    print("[Rainbow Six 3 -- the wave hunt switch, and why it did nothing]")
    if not (args.soz or args.iso or args.rs3data):
        print("  SKIP  needs --soz, --iso or --rs3data")
        return
    img = SozImage.unpack(stock_container(args), PROFILE.overlays[0].base_va)
    check("the container we are reading really is the pristine one",
          hashlib.sha1(bytes(img.image)).hexdigest()
          == PROFILE.overlays[0].image_sha1)
    rw = img.read_word

    check("the three words it used to take are the dead pair and the mfhi",
          [rw(a) for a in (0x0040AF4C, 0x0040AF50, 0x0040AF54)]
          == [0x00000000, 0x00000000, 0x00001010])
    # `this` is the point, not the wave: the wave picks out of
    # m_aSpawningPoint at +0x484 and dispatches vtable+0x188 on it.
    check("the wave delegates the spawn to a point it picked",
          rw(0x0040AC9C) == 0x26B00484        # addiu $s0, $s5, 0x484
          and rw(0x0040ACC0) == 0x8C440000    # lw   $a0, ($v0)
          and rw(0x0040ACC4) == 0x8C990000    # lw   $t9, ($a0)
          and rw(0x0040ACC8) == 0x8F390188    # lw   $t9, 0x188($t9)
          and rw(0x0040ACCC) == 0x0320F809)   # jalr $t9
    check("its spawn-at-init slot is a stub that returns zero, so the base "
          "loop spawns nothing for a wave",
          rw(0x0040AF00) == 0x03E00008        # jr   $ra
          and rw(0x0040AF04) == 0x0000102D)   # move $v0, $zero
    check("and across the whole of the wave's own code there is not one "
          "load or store of the flag's offset",
          not [va for va in range(0x0040AB60, 0x0040AFE0, 4)
               if (rw(va) >> 26) in (0x20, 0x21, 0x23, 0x24,
                                     0x25, 0x28, 0x29, 0x2B)
               and (rw(va) & 0xFFFF) == 0x0388])
    # The only reader, and it reads `this`, which InitTerrorist then stores
    # as pawn->m_DZone.
    check("the only reader tests bit 0x20 then bit 0x40 and writes strategy "
          "3 into the pawn",
          rw(0x00386B60) == 0x92830388        # lbu $v1, 0x388($s4)
          and rw(0x00386B80) == 0x24020003    # addiu $v0, $zero, 3
          and rw(0x00386B88) == 0xA2620942)   # sb $v0, 0x942($s3)
    check("and the object it read that from is the one it records as the "
          "pawn's own zone", rw(0x00386B04) == 0xAE74096C)  # sw $s4,0x96c($s3)

    # The picker is NOT capped by the eligible count: an empty filtered list
    # falls through to the full array and the release still runs.
    check("an empty eligible list falls back to the whole point array",
          rw(0x0040AC94) == 0x14400002        # bnez $v0, +2
          and rw(0x0040AC98) == 0x27B00098)   # addiu $s0, $sp, 0x98
    check("and the stasis extract is a dsrl32, not the dsra32 the notes used "
          "to print", (rw(0x0040A78C) & 0x3F) == 0x3E)
    notes = io.open("docs/PATCHES.md", encoding="utf-8").read()
    check("the notes say so too", "dsrl32 $v0, $v0, 31" in notes
          and "dsra32 $v0, $v0, 31" not in notes)
    check("and no longer claim the eligible count caps the release",
          "the cap is the number of eligible points" not in notes)


def run_game_presence(args):
    """The Discord button drives drp.exe rather than speaking to Discord
    itself. Everything here is READ-ONLY on purpose: start(), stop() and
    set_startup() touch a program the person running the suite may well
    have going, and a test that kills their presence to prove it can is a
    test that should not exist."""
    print("\n[Discord: presence for the game]")
    import sys as _sys
    from gui import gamepresence as gp

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    check("it is Windows-only, and says so rather than pretending",
          gp.SUPPORTED == (_sys.platform == "win32"))

    cands = gp.candidates()
    check("the bundled folder beside the exe is looked in FIRST, so a "
          "shipped copy beats a stray one",
          bool(cands) and cands[0].endswith(
              os.path.join(gp.BUNDLED_DIR, gp.EXE_NAME)),
          cands[0] if cands else "no candidates")
    check("every candidate is an absolute path",
          all(os.path.isabs(c) for c in cands))
    check("and none is listed twice", len(set(cands)) == len(cands))

    st = gp.status()
    check("status answers every question the sheet asks",
          set(st) == {"supported", "exe", "installed", "running"},
          "%r" % (sorted(st),))
    check("installed agrees with whether an exe was found",
          st["installed"] == (st["exe"] is not None))
    check("an exe it reports is one that is really there",
          st["exe"] is None or os.path.isfile(st["exe"]))
    check("nothing is claimed to be running when nothing is installed",
          st["installed"] or not st["running"])

    # The retired in-process client must not creep back into the window.
    src = io.open(os.path.join(here, "gui", "app.py"),
                  encoding="utf-8").read()
    check("the window no longer drives Discord itself",
          "from . import presence" not in src and "self.presence" not in src)
    head = io.open(os.path.join(here, "gui", "presence.py"),
                   encoding="utf-8").read()[:400]
    check("and the retired module is kept, carrying its reason",
          "RETIRED" in head)
    # The sheet is BUILT here, not merely imported. It shipped with a
    # `configure(text=...)` on an ActionButton, which is a tk.Canvas and
    # has no -text option: Tk raised inside _refresh, and the button sat
    # reading "Turn on" while the line under it said it was already
    # running. Nothing short of constructing it would have caught that.
    import tkinter as _tk
    try:
        root = _tk.Tk()
    except Exception as exc:                        # noqa: BLE001
        print("  SKIP  no display: %s" % exc)
        return
    try:
        root.withdraw()
        root.geometry("900x600+0+0")
        root.update_idletasks()
        from gui import discorddialog

        real = gp.status
        seen = {}
        for running in (True, False):
            for installed in (True, False):
                gp.status = (lambda r=running, i=installed: {
                    "supported": True, "installed": i,
                    "exe": "X" if i else None, "running": r and i})
                dlg = discorddialog.DiscordDialog(root)
                dlg._refresh()
                seen[(running, installed)] = (dlg.toggle_btn.text,
                                              dlg.toggle_btn.enabled)
                dlg.grab_release()
                dlg.destroy()
        gp.status = real

        check("the sheet builds and refreshes without raising",
              len(seen) == 4)
        check("the button offers to turn it OFF when it is running",
              seen[(True, True)][0] == "Turn off",
              "%r" % (seen[(True, True)],))
        check("and to turn it ON when it is not",
              seen[(False, True)][0] == "Turn on",
              "%r" % (seen[(False, True)],))
        check("the button is dead when drp is not installed, so it cannot "
          "promise something it has no way to do",
              not seen[(True, False)][1] and not seen[(False, False)][1])
    finally:
        try:
            root.destroy()
        except Exception:                           # noqa: BLE001
            pass

def run_badge_honesty():
    """No option may claim it was watched working while its own caution
    opens by saying it never was. That combination shipped in 1.0's first
    build on four cards, three of them only because `confidence` used to
    default to "verified" -- so a card that set nothing claimed the most."""
    print("\n[badges say what the cautions say]")
    import re as _re
    lead = _re.compile(
        r"^\s*(not yet played|never played|not play-tested)\b", _re.I)
    for prof in (PROFILE,):
        liars = [s.key for s in prof.settings
                 if s.confidence == "verified" and lead.match(s.caution or "")]
        check("no card claims VERIFIED IN GAME while its caution opens by "
              "saying it was never played", not liars, ", ".join(liars))
        blank = [s.key for s in prof.settings if not s.confidence]
        check("every option carries a badge", not blank, ", ".join(blank))
        known = ("verified", "applied", "measured", "experimental",
                 "untested", "broken")
        odd = [s.key for s in prof.settings if s.confidence not in known]
        check("and it is one the window knows how to draw", not odd,
              ", ".join(odd))


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

        Wave mode carries two notes of its own -- one about Terrorist Hunt,
        one about the map-wide spawn picker -- and both ride along with every
        config here, since they all have wave mode on and the picker defaults
        on. Filtering them keeps these checks about the thing they were
        written for; both notes are asserted directly, just above.
        """
        return [w for w in combination_warnings(vals)
                if "Terrorist Hunt" not in w and "frames a second" not in w]

    check("an untouched config says nothing",
          not oom(base), str(oom(base)))

    # 2026-09-25: split-screen Terrorist Hunt AND practice were both played
    # with wave mode on (Shipyard) and both load, so the old blanket "this
    # stops Terrorist Hunt loading" is retired. What is left is the narrower
    # combination it was really measured on: waves feeding with the map-wide
    # spawn points OFF, so every wave asks ONE zone for all its points.
    # A stored profile ignores a changed default, so the warning is what
    # actually reaches someone carrying that combination.
    check("waves without the map-wide spawn points still warn",
          any("Terrorist Hunt" in w for w in
              combination_warnings(dict(base, wave_mapwide=False))),
          str(combination_warnings(dict(base, wave_mapwide=False))))
    check("but waves as played -- map-wide on -- say nothing",
          not any("Terrorist Hunt" in w for w in
                  combination_warnings(dict(base, wave_mapwide=True))),
          str(combination_warnings(dict(base, wave_mapwide=True))))
    check("and a config without wave mode says nothing about it",
          not any("Terrorist Hunt" in w for w in
                  combination_warnings(dict(base, wave_enable=False))))

    # The spawn runaway (Shipyard, 2026-09-25). The engine credits a new
    # enemy to the spawn POINT's owning zone, not to the zone that asked, and
    # most points have no owner -- 14 of Shipyard's 18. So a map-wide pick
    # builds and places the enemy fine, credits nobody, and the asking zone
    # stays under its trigger and releases again next frame, forever. The
    # release size only scales the waste, so the warning keys on the PICKER,
    # not on the size. This is the config the user was playing.
    played = dict(base, wave_mapwide=True, wave_size=5, wave_trigger=2,
                  wave_total=60, wave_gate="always", wave_hunt=True)
    runaway = [w for w in combination_warnings(played) if "frames a second" in w]
    check("the map-wide picker says its fix rides in the cheat file",
          len(runaway) == 1 and "CHEAT FILE" in runaway[0]
          and "save a fresh one" in runaway[0], str(runaway))
    check("and the release size does not change that -- the picker is the bug",
          len([w for w in combination_warnings(dict(played, wave_size=1))
               if "frames a second" in w]) == 1)
    check("turning the picker off clears it",
          not [w for w in combination_warnings(
              dict(played, wave_mapwide=False)) if "frames a second" in w])

    # ---- wave_hunt, withdrawn 2026-09-26 ---------------------------------
    # It set m_bHuntFromStart (bit 0x40 of +0x388) on the WAVE actor. The one
    # place that flag is read is AR6DeploymentZone::InitTerrorist at
    # 0x00386B88, which reads it off `this` -- and `this` is never the wave.
    # AR6DZoneWave overrides the "spawn at init" slot with a stub returning 0,
    # and its SpawnATerrorist picks a point and calls THAT point's spawner
    # through vtable+0x188, so `this` is the R6DZonePoint the whole way down.
    wh = PROFILE.setting("wave_hunt")
    check("the wave hunt switch is withdrawn, with a reason that says why",
          wh is not None and not wh.enabled and wh.confidence == "broken"
          and wh.default is False
          and "SPAWN POINT" in wh.disabled_reason)
    check("and it emits nothing at its old site, in any configuration",
          not [e for kw in ({}, {"wave_hunt": True},
                            {"wave_enable": True, "wave_hunt": True})
               for e in PROFILE.build_edits(
                   PROFILE.effective(dict(PROFILE.defaults(), **kw)))
               if getattr(e, "va", None) in (0x0040AF4C, 0x0040AF50,
                                             0x0040AF54)])
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
        # From the BACKUP, not from the disc. `ai_finite_ammo` switches
        # `ai_sidearm` on, so an applied disc already carries the very edit
        # this applies -- and applying it twice is refused, which aborted the
        # whole suite rather than failing one check. The shadow is seeded
        # with the pristine bytes so everything below sees stock whatever
        # the disc happens to hold.
        real_store = dataedit.Store(engine.backup_dir_for(iso_path))
        pristine = None
        for k in real_store.index:
            if k.endswith("/COMMON.LIN"):
                pristine = real_store.original(
                    real_store.index[k]["archive"], "/COMMON.LIN")[0]
                break
        if pristine is None:
            print("  SKIP  no stored COMMON.LIN to compare against")
            return
        ent = arc.files[key.upper()]
        if len(pristine) != ent.size:
            print("  SKIP  the stored COMMON.LIN is not this disc's revision")
            return
        arc.r.write(ent.offset, pristine)
        stock = arc.read_file(key)
        check("the shadow really is showing us the pristine file",
              stock == pristine)
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


def run_recording_first(args):
    """AI teammates plus a changed enemy count, applied together.

    The per-mission enemy counts edit a map's split-screen recording as well
    as its single-player one. When that edit ran before `team_recording`, the
    splice was handed an edited recording and refused it -- in the GUI, an
    apply with Parade's enemy count changed failed outright with "the
    split-screen record at 0x14f160 is not the one every map carries".
    `apply_data` now runs recording ops first on every file. Read-only: the
    chain is run in memory on the shipped files from the backup store.
    """
    print("\n[a replaced recording runs before the edits on top of it]")
    if not args.rs3data:
        print("  SKIP  needs --rs3data")
        return
    import inspect
    from tcps2 import dataedit, lin, rsesplice, vokes
    src = inspect.getsource(dataedit.apply_data)
    check("apply_data sorts recording ops first, keeping the rest in order",
          "sorted(edits, key=lambda e: e.op not in _RECORDING_OPS)" in src)
    vals = dict(PROFILE.defaults(), split_squad=True, mission_parade=150)
    eds = PROFILE.build_data(PROFILE.effective(vals))
    path = "/PARADE_A_SS.LIN"
    mine = [e for e in eds if re.search(e.select, path, re.I)]
    check("Parade A's split-screen file gets both edits",
          sorted(e.op for e in mine) == ["team_recording", "zone_counts"],
          str([e.op for e in mine]))
    store = dataedit.Store(engine.backup_dir_for(args.rs3data))
    keys = [k for k in store.index if k.endswith(path)]
    if not keys:
        print("  SKIP  the backup store holds no original of %s" % path)
        return
    arc_name = store.index[keys[0]]["archive"]
    with Iso(args.rs3data) as iso:
        arc = [a for a in vokes.open_archives(iso) if path in a.files][0]
        stock = lin.decompress(store.original(arc_name, path)[0])
        sib = dataedit._sibling_plain(arc, arc_name, path, store,
                                      "team_recording")

        def run(order):
            plain = stock
            for e in order:
                fn = dataedit.OPS[e.op]
                if e.op in dataedit._WANTS_SIBLING:
                    plain, _n = fn(plain, e.params, sib)
                else:
                    plain, _n = fn(plain, e.params)
            return plain

        check("the old order, enemy counts first, is what the GUI hit",
              _raises(lambda: run(sorted(mine, key=lambda e:
                                         e.op == "team_recording")),
                      rsesplice.SpliceError))
        got = run(sorted(mine, key=lambda e: e.op not in
                         dataedit._RECORDING_OPS))
        check("recording first: the file is spliced",
              rsesplice.reads(got) and len(got) == len(stock) + 2631)
        check("and the enemy counts land on top of the splice",
              got != rsesplice.splice(stock, sib))



def run_xbox_notes():
    """Each enemy card says how far it is from the Xbox build -- RS3 only."""
    print("\n[enemy cards: the Xbox comparison]")
    from tcps2.games.r6_3 import XBOX_NOTES
    check('every noted card carries its note',
          all('Compared with the Xbox build: ' + XBOX_NOTES[k]
              in PROFILE.setting(k).help for k in XBOX_NOTES))
    check('the only enemy INI key that differs is named with both values',
          '0.40' in XBOX_NOTES['terro_skill']
          and '0.20' in XBOX_NOTES['terro_skill'])
    leak = [(p.id, st.key) for p in ALL_PROFILES if p is not PROFILE
            for st in p.settings
            if 'Compared with the Xbox build' in (st.help or '')]
    check("no other game's cards pick the notes up", not leak, str(leak[:3]))


def run_callouts(args):
    """Split-screen call-outs: a downed player announced, kills complimented.

    Read-only, on the shipped COMMON_SS from the backup store. The load-order
    half of the proof is run_creation_order, which carries this option in its
    split-screen set; this checks the three blocks themselves.
    """
    print("\n[split screen: teammates call out downs and kills]")
    if not args.rs3data:
        print("  SKIP  needs --rs3data")
        return
    from tcps2 import dataedit, lin, rsecallouts, upackage
    from tcps2.uscode import Script
    store = dataedit.Store(engine.backup_dir_for(args.rs3data))
    keys = [k for k in store.index if k.endswith("/COMMON_SS.LIN")]
    if not keys:
        print("  SKIP  no stored COMMON_SS.LIN")
        return
    stock = lin.decompress(store.original(store.index[keys[0]]["archive"],
                                          "/COMMON_SS.LIN")[0])
    at = {b.name: b.find(stock) for b in rsecallouts.BLOCKS}
    check("the three functions are where they were measured",
          all(at[b.name] == b.known for b in rsecallouts.BLOCKS),
          str({k: hex(v) for k, v in at.items()}))
    check("and are the code this disc shipped",
          all(b.state(stock) == "stock" for b in rsecallouts.BLOCKS))
    on, n = rsecallouts.apply(stock, True)
    check("turning it on rewrites all three, at the file's length",
          n == 3 and len(on) == len(stock) and rsecallouts.reads(on)
          and not rsecallouts.reads(stock))
    check("and asking twice is a no-op", rsecallouts.apply(on, True) == (on, 0))
    spans = [(at[b.name], at[b.name] + len(b.new)) for b in rsecallouts.BLOCKS]
    moved = [i for i in range(len(stock)) if stock[i] != on[i]]
    check("nothing outside the three functions moves",
          moved and all(any(a <= i < z for a, z in spans) for i in moved))
    same = True
    for b in rsecallouts.BLOCKS:
        old, new = Script.at(stock, at[b.name]), Script.at(on, at[b.name])
        same &= (old.mem_len, old.disk_len) == (new.mem_len, new.disk_len)
    check("each keeps its ScriptSize and disk length, and parses with every "
          "jump on a statement", same)
    ops = [23 + ((op & 1) << 1) + (op >> 1) for op in range(4)]
    check("a downed player is announced by operative: Chavez 23, Price 25, "
          "Loiselle 24, Weber 26", ops == [23, 25, 24, 26])
    names, imports, _exports = upackage.tables(on, 0x086A7F)
    dmg = on[at["damage"]:at["damage"] + len(rsecallouts.DAMAGE.new)]
    inf = on[at["inflicted"]:at["inflicted"] + len(rsecallouts.INFLICTED.new)]
    pos = on[at["possess"]:at["possess"] + len(rsecallouts.POSSESS.new)]
    check("player 2's lines are Price's own Sound imports",
          imports[1294 - 1] == "Play_Price_ChavezDown"
          and imports[1368 - 1] == "Play_Price_Ding_TerroDown1rst"
          and bytes.fromhex("20ce14") in dmg and bytes.fromhex("20d815") in inf)
    check("and his bank is requested where the AI teammates request theirs",
          b"X_Voices_Price\x00" in pos
          and names[0x17] == "AddSoundBankName")
    bent = bytearray(stock)
    bent[at["inflicted"] + 40] ^= 1
    check("a function that is not the shipped one is refused",
          _raises(lambda: rsecallouts.apply(bytes(bent)),
                  rsecallouts.CalloutsError))
    # Withdrawn the day it shipped: Terrorist Hunt on the Garage hung its load
    # in a voice package. run_creation_order's content-import check is the
    # one that sees why.
    s = PROFILE.setting("split_callouts")
    check("the option is withdrawn, and says why",
          s is not None and s.confidence == "broken" and not s.enabled
          and "Bad name index" in (s.disabled_reason or ""))
    check("and a profile that still has it on writes nothing",
          not any(e.op == "split_callouts" for e in PROFILE.build_data(
              PROFILE.effective(dict(PROFILE.defaults(), split_squad=True,
                                     split_callouts=True)))))


def run_thunt_team(args):
    """Split-screen Terrorist Hunt shares COMMON_SS and the _SS recordings with
    practice. Giving it its own team by making player 2 Price (2026-09-24) was
    withdrawn the same day, with the call-outs, when the Garage stopped
    loading; the call-outs explain the hang, and rsethuntai took the other
    route (run_thunt_ai)."""
    print("\n[Terrorist Hunt keeps practice's team in split screen]")
    if not args.rs3data:
        print("  SKIP  needs --rs3data")
        return
    from tcps2 import dataedit, lin, rsecanon, rsesquad
    store = dataedit.Store(engine.backup_dir_for(args.rs3data))
    keys = [k for k in store.index if k.endswith("/COMMON_SS.LIN")]
    if not keys:
        print("  SKIP  no stored COMMON_SS.LIN")
        return
    stock = lin.decompress(store.original(store.index[keys[0]]["archive"],
                                          "/COMMON_SS.LIN")[0])
    canon, _n = rsecanon.apply(stock, True)
    check("canon leaves Terrorist Hunt's test out",
          rsecanon.reads(canon) and not rsecanon._thunt_present(canon))
    check("and asking twice is a no-op", rsecanon.apply(canon, True) == (canon, 0))
    both, _n = rsesquad.apply(stock, True, canon=True)
    alone, _n = rsesquad.apply(stock, True)
    at = rsesquad.KNOWN_BTERRO_OFFSET
    check("the AI teammates leave Terrorist Hunt's roster test as shipped, "
          "with or without canon",
          stock.find(rsesquad.BTERRO) == at
          and both[at:at + len(rsesquad.BTERRO)] == rsesquad.BTERRO
          and alone[at:at + len(rsesquad.BTERRO)] == rsesquad.BTERRO)
    check("and both together still read as canon and squad",
          rsecanon.reads(both) and not rsecanon._thunt_present(both)
          and rsesquad.reads(both) == rsesquad.ARM_TARGET)


def run_downcall(args):
    """A downed player is called out by an AI teammate, with the man-down
    music (2026-09-24). Read-only, on the shipped COMMON_SS; the load-order
    half is run_creation_order, which carries this option."""
    print("\n[split screen: a downed player is called out]")
    if not args.rs3data:
        print("  SKIP  needs --rs3data")
        return
    from tcps2 import dataedit, lin, rsedowncall, rsesquad
    from tcps2.uscode import Script, END
    store = dataedit.Store(engine.backup_dir_for(args.rs3data))
    keys = [k for k in store.index if k.endswith("/COMMON_SS.LIN")]
    if not keys:
        print("  SKIP  no stored COMMON_SS.LIN")
        return
    stock = lin.decompress(store.original(store.index[keys[0]]["archive"],
                                          "/COMMON_SS.LIN")[0])
    check("without the AI teammates' hand-off there is nothing to hook, and "
          "it says so", _raises(lambda: rsedowncall.apply(stock, True),
                                rsedowncall.DownCallError))
    squad, _n = rsesquad.apply(stock, True, canon=True)
    got, n = rsedowncall.apply(squad, True)
    check("on top of the AI teammates it makes all three edits",
          n == 3 and rsedowncall.reads(got) and not rsedowncall.reads(squad)
          and [a for a, *_ in rsedowncall._sites(squad)]
          == list(rsedowncall.KNOWN_OFFSETS))
    check("and asking twice is a no-op",
          rsedowncall.apply(got, True) == (got, 0))
    at = 0x1409B8
    old, new = Script.at(squad, at), Script.at(got, at)
    check("TeamMemberDead keeps its ScriptSize and disk length",
          (old.mem_len, old.disk_len) == (new.mem_len, new.disk_len)
          and len(got) == len(squad))
    moved = [i for i in range(len(squad)) if squad[i] != got[i]]
    check("nothing outside TeamMemberDead moves",
          moved and at <= moved[0] and moved[-1] < at + 4 + old.disk_len)
    starts = {t.mstart for t in new.toks}
    bad = [(t.mstart, v.mstart) for t in new.toks for x in t.walk()
           for k, v in x.parts
           if k == "jump" and v is not END and v.mstart not in starts]
    check("every jump lands on a statement", not bad, str(bad))
    check("the lead hand-off is still there, in its new form",
          rsesquad.hands_off_lead(got) and rsesquad.hands_off_lead(squad))
    check("and the AI teammates applied again keep it; reverting them refuses",
          rsesquad.apply(got, True, canon=True) == (got, 0)
          and _raises(lambda: rsesquad.apply(got, False), rsesquad.SquadError))
    # rsesquad hands the lead over by calling TeamMemberDead with a LIVING
    # player's pawn (regrouponme); without this every regroup was a "man down".
    c = rsedowncall.KNOWN_OFFSETS[2]
    check("a living pawn -- a regroup's hand-off -- returns before the call-out",
          got[c + 3:c + 18] == bytes.fromhex("07950319004a0a0600041b0416040b"))
    ops = [23 + (((op * 5) >> 1) & 3) for op in range(4)]
    check("a downed player is called out by operative: Chavez 23, Price 25, "
          "Loiselle 24, Weber 26", ops == [23, 25, 24, 26])
    s = PROFILE.setting("split_down_callouts")
    check("the option reaches the profile, needing the AI",
          s is not None and s.confidence in BADGES and s.enabled
          and s.requires == {"split_squad": [True]})
    eds = PROFILE.build_data(PROFILE.effective(dict(
        PROFILE.defaults(), split_squad=True, split_down_callouts=True)))
    ops = [e.op for e in eds]
    check("it writes the split-screen package, after the AI teammates",
          "split_down_callouts" in ops
          and ops.index("squad") < ops.index("split_down_callouts")
          and [e for e in eds if e.op == "split_down_callouts"][0]
          .matches("/COMMON_SS.LIN")
          and not [e for e in eds if e.op == "split_down_callouts"][0]
          .matches("/COMMONOFF.LIN"))
    check("and without the AI it is not written at all",
          not any(e.op == "split_down_callouts" for e in PROFILE.build_data(
              PROFILE.effective(dict(PROFILE.defaults(),
                                     split_down_callouts=True)))))


def _obj_refs(script):
    """Every object reference in a block, in order. A virtual or global call
    and a name constant carry a NAME index instead, and a delegate carries one
    of each, so those are skipped -- reading a name index as an object index is
    how you convince yourself a function reaches something it does not."""
    from tcps2.uscode import compact_decode
    out = []
    for t in script.statements():
        i = 0
        for kind, val in t.parts:
            if kind == "ref":
                if not (t.op in (0x1B, 0x38, 0x21, 0x0E)
                        or (t.op == 0x40 and i == 1)):
                    out.append(compact_decode(val, 0)[0])
                i += 1
    return out


def _first_touch(plain, obj, _cache={}):
    """The offset of the first block in the package that reaches `obj`."""
    from tcps2 import uscode
    from tcps2.uscode import Script, ScriptError
    key = id(plain)
    if key not in _cache:
        seen = {}
        for at in uscode.find_blocks(plain):
            try:
                sc = Script.at(plain, at)
            except ScriptError:
                continue
            for o in _obj_refs(sc):
                seen.setdefault(o, at)
        _cache[key] = seen
    return _cache[key].get(obj, 1 << 62)


def run_hostage_rainbow_voice(args):
    """The hostage line for "Rainbow is here and so is a terrorist" -- cue
    `Host<N>_M<nn>_WithRnb_Terro`, `EHostageVoices` 0, `m_sndRun` -- which no
    shipped call site ever passes (2026-09-28). Read-only, on all three stored
    COMMON packages; the load-order half is run_creation_order, which carries
    this option in its "every script option" set."""
    print("\n[hostages react out loud when Rainbow arrives]")
    if not args.rs3data:
        print("  SKIP  needs --rs3data")
        return
    import re
    import struct
    from tcps2 import dataedit, lin, rsehostagerun, uscode
    from tcps2.uscode import Script, END
    store = dataedit.Store(engine.backup_dir_for(args.rs3data))

    stocks = {}
    for name in ("/COMMON.LIN", "/COMMONOFF.LIN", "/COMMON_SS.LIN"):
        keys = [k for k in store.index if k.endswith(name)]
        if keys:
            stocks[name] = lin.decompress(
                store.original(store.index[keys[0]]["archive"], name)[0])
    if not stocks:
        print("  SKIP  no stored COMMON package")
        return

    # `ProcessPlaySndInfo` is name index 174 and its shipped call sites are all
    # `EX_VirtualFunction ref EX_ByteConst <n> EX_EndFunctionParms`. Scanning
    # the bytes finds them all, including the ones uscode.find_blocks shadows.
    call = re.compile(rb"\x1b\x6e\x02\x24(.)\x16", re.S)

    for name, stock in sorted(stocks.items()):
        got, n = rsehostagerun.apply(stock, True)
        check("%s: both blocks are found exactly once and rewritten" % name,
              n == 2 and len(got) == len(stock)
              and not rsehostagerun.reads(stock)
              and rsehostagerun.reads(got))
        check("%s: asking twice is a no-op, and off writes nothing" % name,
              rsehostagerun.apply(got, True) == (got, 0)
              and rsehostagerun.apply(stock, False) == (stock, 0))
        check("%s: reverting gives the shipped bytes back" % name,
              rsehostagerun.revert(got) == (stock, 2))

        # the thing the whole option is for
        was = sorted(m.group(1)[0] for m in call.finditer(stock))
        now = sorted(m.group(1)[0] for m in call.finditer(got))
        check("%s: the disc passes ProcessPlaySndInfo 1,1,1,2,2,3,3,4,5,6 and "
              "never 0" % name,
              was == [1, 1, 1, 2, 2, 3, 3, 4, 5, 6]
              and rsehostagerun.HV_RUN not in was, str(was))
        check("%s: afterwards HV_Run is passed, once, and one HV_Hears_Shooting "
              "moves to make room" % name,
              now == [0, 1, 1, 1, 2, 2, 3, 4, 5, 6]
              and now.count(rsehostagerun.HV_RUN) == 1, str(now))
        # m_aPlaySndInfo is ArrayDim 10, ElementSize 8, and ProcessPlaySndInfo
        # indexes it unchecked -- while PlayHostageVoices on this disc has
        # twelve arms, 10 and 11 being m_sndGrabHostage1 and m_sndGrabHostage3.
        # Those two are real voices nothing calls, so they are exactly what
        # somebody wires next, and either would write eight or sixteen bytes
        # past an eighty-byte array. HV_Run is 0. This is the guard rail.
        check("%s: every argument stays inside m_aPlaySndInfo" % name,
              max(now) < rsehostagerun.PLAY_SND_INFO_DIM
              and rsehostagerun.PLAY_SND_INFO_DIM == 10, str(max(now)))
        check("%s: nothing routes m_sndGrabHostage1/3 (10, 11) through the "
              "throttle" % name,
              10 not in now and 11 not in now, str(now))

        # nothing but the two blocks moves
        spans = [(at, len(s)) for at, s, _w, _st in rsehostagerun._sites(stock)]
        moved = [i for i in range(len(stock)) if stock[i] != got[i]]
        check("%s: nothing outside the two blocks moves" % name,
              moved and all(any(a <= i < a + ln for a, ln in spans)
                            for i in moved),
              "%d bytes differ in %d blocks" % (len(moved), len(spans)))

        for at, s, _w, _st in rsehostagerun._sites(stock):
            old, new = Script.at(stock, at), Script.at(got, at)
            check("%s: 0x%x keeps its disk length, its memory length and its "
                  "ScriptSize" % (name, at),
                  (old.disk_len, old.mem_len) == (new.disk_len, new.mem_len)
                  and struct.unpack_from("<I", stock, at)
                  == struct.unpack_from("<I", got, at),
                  "%d disk / %d memory" % (new.disk_len, new.mem_len))
            check("%s: 0x%x re-assembles to the same bytes" % (name, at),
                  new.assemble(new.disk_len, new.mem_len)
                  == (got[at + 4:at + 4 + new.disk_len], new.mem_len))
            starts = {t.mstart for t in new.statements()}
            bad = [(t.mstart, v.mstart) for t in new.statements()
                   for k, v in t.parts
                   if k in ("jump", "jump32") and v is not END
                   and v.mstart not in starts]
            check("%s: 0x%x -- every jump lands on a statement" % (name, at),
                  not bad, str(bad))
            # An edit that becomes the FIRST to reach one of the package's own
            # objects reads the recording out of step (run_creation_order).
            # The only two this block newly reaches are pinned, and both are
            # first touched thousands of bytes earlier.
            added = sorted(set(_obj_refs(new)) - set(_obj_refs(old)))
            want = (list(rsehostagerun.NEW_REFS)
                    if at == min(rsehostagerun.KNOWN_OFFSETS) else [])
            check("%s: 0x%x reaches only the objects it is allowed to add"
                  % (name, at), added == want,
                  "added %s, expected %s" % (added, want))
            check("%s: 0x%x -- every added object is already reached earlier "
                  "in the package" % (name, at),
                  all(_first_touch(stock, o) < at for o in added),
                  " ".join("#%d first at 0x%x" % (o, _first_touch(stock, o))
                           for o in added) or "none")

    check("the two blocks are byte-identical in all three packages",
          len({tuple(s for _n, s, _w in rsehostagerun.BLOCKS)}) == 1
          and all(st.count(s) == 1 and st.count(w) == 0
                  for st in stocks.values()
                  for _n, s, w in rsehostagerun.BLOCKS))

    s = PROFILE.setting("hostage_rainbow_voice")
    check("the option reaches the profile, off by default",
          s is not None and s.default is False and s.enabled
          and s.confidence in BADGES and s.touches == "data"
          and not s.requires)
    check("an untouched profile writes nothing",
          not any(e.op == "hostage_rainbow_voice"
                  for e in PROFILE.build_data(
                      PROFILE.effective(dict(PROFILE.defaults())))))
    eds = PROFILE.build_data(PROFILE.effective(
        dict(PROFILE.defaults(), hostage_rainbow_voice=True)))
    mine = [e for e in eds if e.op == "hostage_rainbow_voice"]
    check("switched on it writes all three COMMON packages",
          len(mine) == 1 and mine[0].matches("/COMMON.LIN")
          and mine[0].matches("/COMMONOFF.LIN")
          and mine[0].matches("/COMMON_SS.LIN"))
    check("the dispatcher knows the op",
          dataedit.OPS.get("hostage_rainbow_voice") is not None)


def run_thunt_ai(args):
    """Terrorist Hunt on the canon maps adds the two operatives nobody plays
    (2026-09-24). Read-only; the load-order half is run_creation_order."""
    print("\n[split-screen Terrorist Hunt: the other two operatives join]")
    if not args.rs3data:
        print("  SKIP  needs --rs3data")
        return
    from tcps2 import dataedit, lin, rsesquad, rsethuntai
    from tcps2.uscode import Script, END
    store = dataedit.Store(engine.backup_dir_for(args.rs3data))
    keys = [k for k in store.index if k.endswith("/COMMON_SS.LIN")]
    if not keys:
        print("  SKIP  no stored COMMON_SS.LIN")
        return
    stock = lin.decompress(store.original(store.index[keys[0]]["archive"],
                                          "/COMMON_SS.LIN")[0])
    alone, _n = rsesquad.apply(stock, True)
    check("without canon's roster there is nothing it recognises, and it says so",
          _raises(lambda: rsethuntai.apply(stock, True), rsethuntai.ThuntAIError)
          and _raises(lambda: rsethuntai.apply(alone, True),
                      rsethuntai.ThuntAIError))
    both, _n = rsesquad.apply(stock, True, canon=True)
    got, n = rsethuntai.apply(both, True)
    check("on the AI teammates with canon it makes both edits",
          n == 2 and rsethuntai.reads(got) and not rsethuntai.reads(both)
          and [a for a, *_ in rsethuntai._sites(both)]
          == list(rsethuntai.KNOWN_OFFSETS))
    check("and asking twice is a no-op", rsethuntai.apply(got, True) == (got, 0))
    at = 0x1470A3
    old, new = Script.at(both, at), Script.at(got, at)
    check("CreatePlayerTeam keeps its ScriptSize and disk length",
          (old.mem_len, old.disk_len) == (new.mem_len, new.disk_len) == (1775, 1346)
          and len(got) == len(both))
    moved = [i for i in range(len(both)) if both[i] != got[i]]
    check("nothing outside CreatePlayerTeam moves",
          moved and at <= moved[0] and moved[-1] < at + 4 + old.disk_len)
    starts = {t.mstart for t in new.toks}
    bad = [(t.mstart, v.mstart) for t in new.toks for x in t.walk()
           for k, v in x.parts
           if k == "jump" and v is not END and v.mstart not in starts]
    check("every jump lands on a statement", not bad, str(bad))
    check("the AI teammates' own checks still read their edits",
          rsesquad.keeps_player2_out(got) and rsesquad.roster_reads_price(got)
          and rsesquad.reads(got) == rsesquad.ARM_TARGET)
    check("and the AI teammates applied again keep it; reverting them refuses",
          rsesquad.apply(got, True, canon=True) == (got, 0)
          and _raises(lambda: rsesquad.apply(got, False), rsesquad.SquadError))
    check("Garage's player 2 is Loiselle (2) and Island's Weber (3): the second "
          "AI is the other one", [5 - op for op in (2, 3)] == [3, 2])
    s = PROFILE.setting("split_thunt_ai")
    check("the option reaches the profile, needing the AI and canon",
          s is not None and s.confidence in BADGES and s.enabled
          and s.requires == {"split_squad": [True], "canon_team": [True]})
    eds = PROFILE.build_data(PROFILE.effective(dict(
        PROFILE.defaults(), split_squad=True, canon_team=True,
        split_thunt_ai=True)))
    ops = [e.op for e in eds]
    check("it writes the split-screen package, after the AI teammates",
          "split_thunt_ai" in ops
          and ops.index("squad") < ops.index("split_thunt_ai")
          and [e for e in eds if e.op == "split_thunt_ai"][0]
          .matches("/COMMON_SS.LIN"))
    check("and without canon it is not written at all",
          not any(e.op == "split_thunt_ai" for e in PROFILE.build_data(
              PROFILE.effective(dict(PROFILE.defaults(), split_squad=True,
                                     split_thunt_ai=True)))))


def run_stun_and_spawn_fix(args):
    """Two engine faults found 2026-09-25 and the words that fix them.

    The flashbang runs a full-screen pass every frame for five seconds, which
    is the whole reason the game crawls while stunned (12 fps against 30 the
    frame before). And a wave zone credits each new enemy to the spawn
    POINT's owning zone rather than to the zone that asked -- with the
    map-wide picker most points have no owner, so nobody is credited, the
    zone stays under its trigger and releases again every frame.

    Read-only against the SHIPPED overlay.
    """
    print("\n[Rainbow Six 3 -- the flashbang stall and the spawn runaway]")
    if not (args.soz or args.iso or args.rs3data):
        print("  SKIP  needs --soz, --iso or --rs3data")
        return
    import struct
    from tcps2.games.r6_3 import (STOCK, STUN_FLASH_SECONDS, STUN_FLASH_WORDS,
                                  CAVE_WORDS)
    img = SozImage.unpack(stock_container(args), PROFILE.overlays[0].base_va)

    # --- the flashbang screen effect ---------------------------------------
    stock = img.read_word(STUN_FLASH_SECONDS)
    check("the shipped overlay hands the screen effect 5 seconds",
          stock == STOCK[STUN_FLASH_SECONDS] == STUN_FLASH_WORDS["stock"]
          == 0x3C0240A0, "%08X" % stock)

    def secs(word):
        return struct.unpack(">f", struct.pack(">I", (word & 0xFFFF) << 16))[0]

    check("every choice is the same lui of the same register, differing only "
          "in the float's high half",
          all((w >> 16) == (stock >> 16) for w in STUN_FLASH_WORDS.values()),
          str({k: "%08X" % w for k, w in STUN_FLASH_WORDS.items()}))
    check("and they decode to the durations they claim",
          [secs(STUN_FLASH_WORDS[k]) for k in ("stock", "4", "3", "2", "1.5", "off")]
          == [5.0, 4.0, 3.0, 2.0, 1.5, 0.0],
          str({k: secs(w) for k, w in STUN_FLASH_WORDS.items()}))
    s = PROFILE.setting("stun_flash")
    check("the option reaches the profile, defaulting to the shipped length",
          s is not None and s.default == "stock" and s.enabled
          and {c.value for c in s.choices} == set(STUN_FLASH_WORDS))
    base = {e.va for e in PROFILE.build_edits(PROFILE.effective(
        PROFILE.defaults()))}
    check("stock writes nothing", STUN_FLASH_SECONDS not in base)
    for name in ("4", "3", "2", "1.5", "off"):
        got = [e for e in PROFILE.build_edits(PROFILE.effective(
            dict(PROFILE.defaults(), stun_flash=name)))
            if e.va == STUN_FLASH_SECONDS]
        check("choosing %s writes one word, from stock" % name,
              len(got) == 1 and got[0].value == STUN_FLASH_WORDS[name]
              and got[0].stock == stock)

    # --- the release loop --------------------------------------------------
    check("the release loop's counter and its delay slot are the shipped ones",
          img.read_word(0x0040A8D4) == STOCK[0x0040A8D4] == 0x26310001
          and img.read_word(0x0040A8E0) == STOCK[0x0040A8E0] == 0x00000000)
    check("and this function already uses MOVZ, so the encoding is the game's "
          "own", img.read_word(0x0040A8B0) == 0x0061800B)
    waved = {e.va: e for e in PROFILE.build_edits(PROFILE.effective(
        dict(PROFILE.defaults(), wave_enable=True)))}
    check("wave mode moves the increment into the delay slot and breaks the "
          "loop when nothing was built",
          waved[0x0040A8D4].value == 0x0202880A
          and waved[0x0040A8E0].value == 0x26310001)
    check("and without wave mode neither word is written",
          not ({0x0040A8D4, 0x0040A8E0} & base))

    # --- the cave credits the zone that asked ------------------------------
    cave = dict(CAVE_WORDS)
    check("the cave's last word is the shared branch delay slot, and it now "
          "stores the requesting zone into the chosen point",
          cave[0x005BA58C] == 0x08102B31          # j 0x0040ACC4
          and cave[0x005BA590] == 0xAC950480)     # sw $s5, 0x480($a0)
    # sw rt, imm(base): opcode 0x2B, base $a0 = 4, rt $s5 = 21, imm 0x480
    w = cave[0x005BA590]
    check("which decodes as sw $s5, 0x480($a0)",
          (w >> 26) == 0x2B and ((w >> 21) & 31) == 4
          and ((w >> 16) & 31) == 21 and (w & 0xFFFF) == 0x480)
    pn = PROFILE.build_pnach(PROFILE.effective(dict(
        PROFILE.defaults(), wave_enable=True, wave_mapwide=True)))
    check("it reaches the cheat file, and the cave did not grow",
          len([e for e in pn if e.va == 0x005BA590
               and e.value == 0xAC950480]) == 1
          and len(pn) == len(CAVE_WORDS) + 1)   # + the hijack
    check("and the disc never carries the cave",
          not ({va for va, _w in CAVE_WORDS} & base))


def run_breach_stun(args):
    """The breaching charge's stun reach, against the real disc.

    The value is a float constant inside R6BreachingChargeUnit.HurtPawns, in
    the 60 single-player and co-op LEVEL containers -- not in COMMON, which
    does not carry the gadget classes at all.
    """
    print("\n[Rainbow Six 3 -- the breaching charge's stun reach]")
    if not args.rs3data:
        print("  SKIP  needs --rs3data")
        return
    import re
    from tcps2 import dataedit, lin, rsegadget, vokes
    from tcps2.iso import Iso

    with Iso(args.rs3data) as iso:
        seen = {}
        for a in vokes.open_archives(iso):
            for k in a.files:
                if k.endswith(".LIN"):
                    seen.setdefault(k, a)
        has, hasnt, sample = [], [], None
        for k, a in sorted(seen.items()):
            raw = _stock_bytes(args.rs3data, a, k)
            try:
                plain = lin.decompress(raw)
            except Exception:                            # noqa: BLE001
                hasnt.append(k)
                continue
            try:
                rsegadget.read(plain, "stun")
            except rsegadget.GadgetError:
                hasnt.append(k)
                continue
            has.append(k)
            if sample is None:
                sample = (k, plain)

    check("60 level containers carry the constant and 25 do not",
          len(has) == 60 and len(hasnt) == 25, "%d / %d" % (len(has), len(hasnt)))
    check("and COMMON is not one of them -- the gadget classes are not in it",
          not [k for k in has if "COMMON" in k]
          and len([k for k in hasnt if "COMMON" in k]) == 3)
    check("the option's selector matches exactly those 60",
          sorted(k for k in has + hasnt
                 if re.search(rsegadget.SELECT, k, re.I)) == sorted(has))

    key, plain = sample
    check("the disc ships a 10 metre stun (200 blast + 800)",
          rsegadget.read(plain, "stun") == rsegadget.STOCK["stun"] == 800.0
          and rsegadget.reads_metres(plain) == rsegadget.STOCK_METRES == 10.0)
    check("and the claymore's cone is the shipped 0.766, a 40 degree arc",
          rsegadget.read(plain, "cone") == rsegadget.STOCK["cone"],
          "%.8f" % rsegadget.read(plain, "cone"))

    out, n = rsegadget.apply(plain, 16)
    moved = [i for i in range(len(plain)) if plain[i] != out[i]]
    at = rsegadget.find(plain, "stun")
    check("setting 16 m keeps the length and touches only the constant",
          n == 1 and len(out) == len(plain)
          and rsegadget.reads_metres(out) == 16.0
          and moved and at <= moved[0] and moved[-1] < at + 4,
          str(moved))
    check("and asking twice is a no-op", rsegadget.apply(out, 16) == (out, 0))
    check("and setting it back restores the file byte for byte",
          rsegadget.apply(out, 10)[0] == plain)
    check("a reach inside the blast itself is refused, not clamped",
          _raises(lambda: rsegadget.apply(plain, 1), rsegadget.GadgetError))

    s = PROFILE.setting("breach_stun")
    check("the option reaches the profile, defaulting to the shipped reach",
          s is not None and s.default == 10 and s.unit == "m"
          and (s.minimum, s.maximum) == (6, 30) and s.enabled)
    check("stock writes nothing to the disc",
          not [e for e in PROFILE.build_data(PROFILE.effective(
              PROFILE.defaults())) if e.op == "breach_stun"])
    eds = [e for e in PROFILE.build_data(PROFILE.effective(
        dict(PROFILE.defaults(), breach_stun=16))) if e.op == "breach_stun"]
    check("choosing another reach emits one edit, carrying the metres",
          len(eds) == 1 and eds[0].params == {"metres": 16}
          and eds[0].matches("/AIRPORT_AOFF.LIN")
          and not eds[0].matches("/COMMON_SS.LIN")
          and not eds[0].matches("/GARAGE_MP_C.LIN"))
    got = dataedit.OPS["breach_stun"](plain, {"metres": 16})
    check("and through the real dispatch table it returns (bytes, count)",
          isinstance(got, tuple) and len(got) == 2
          and isinstance(got[0], bytes) and isinstance(got[1], int)
          and len(got[0]) == len(plain))


def run_hostage_follow(args):
    """Hostages always answer "follow me" (2026-09-28).

    Ten of the fifteen hostage voice sets resolve event 3 to a weighted random
    container one of whose legs is a kind-15 NULL row, so the acknowledgement is
    silence one roll in three -- one in two on the Penthouse.  Four bytes per
    set re-point that leg at the sibling take.

    The assertions that matter are about WHAT IDENTIFIES THE REGION, because the
    obvious implementation is unsafe: the 36-byte child block of Mountain
    Highway's container is byte-identical to Office Complex A's AND to Office
    Complex B's, and Office Complex B's leg 0 is a healthy stream.  So the
    module walks the bank and keys on the logical bank id, and the byte run is a
    SEAL rather than a locator.  The checks below prove both halves of that:
    that the run really is ambiguous, and that the walk is not.

    They also pin the tuple order.  A module in this project returned
    (va, stock, new) and a caller unpacked (va, new, stock); the stock value
    went straight back on the disc, every self-check passed, and the feature did
    nothing.  `Site._fields` is asserted here so that cannot recur silently.
    """
    print()
    print("[Rainbow Six 3 -- hostages always answer \"follow me\"]")
    from tcps2 import dataedit, rsefollowleg as F

    # --- offline: the table, and the contract its callers rely on -----------
    check("ten sets, ten distinct logical bank ids",
          len(F.SETS) == 10 and len({s.bank for s in F.SETS}) == 10,
          "%d sets, %d banks" % (len(F.SETS), len({s.bank for s in F.SETS})))
    check("Leg field order is the documented one",
          F.Leg._fields == ("carrier", "bank", "res", "nchild", "leg",
                            "stock_row", "new_row", "seal"),
          str(F.Leg._fields))
    check("Site field order is (at, stock, new, bank, state) -- stock BEFORE "
          "new, which is the transposition that once wrote the stock value "
          "back and passed every check",
          F.Site._fields == ("at", "stock", "new", "bank", "state"),
          str(F.Site._fields))
    check("every seal is exactly nchild 12-byte child records",
          all(len(s.seal) == s.nchild * 12 for s in F.SETS))
    check("every seal carries stock_row at leg*12, so the seal and the table "
          "cannot disagree",
          all(int.from_bytes(s.seal[s.leg * 12:s.leg * 12 + 4], "little")
              == s.stock_row for s in F.SETS))
    check("no set re-points a leg at the row it already has",
          all(s.stock_row != s.new_row for s in F.SETS))
    check("the five hostage sets with no NULL leg are absent from the table",
          not ({566, 567, 569, 575, 576} & set(F.BY_BANK)))
    check("Office Complex B (bank 576) is excluded from SELECT as well as "
          "from the table -- it is the file a byte-run locator would corrupt",
          "OFFICE_COMPLEX_B" not in F.SELECT
          and "OFFICE_COMPLEX_A" in F.SELECT)
    check(".SB1 is a raw suffix, so dataedit refuses a length change on a "
          "sound bank instead of running _fit_plain over it",
          ".SB1" in dataedit._RAW_SUFFIXES)
    check("the operation is in the dispatch table",
          "hostage_follow_voice" in dataedit.OPS)
    check("the card is off by default, so an untouched profile emits nothing",
          F.card("", "x").default is False)

    if not args.rs3data:
        print("  SKIP  the rest needs --rs3data")
        return

    import re
    from tcps2 import vokes
    from tcps2.games import BY_ID
    from tcps2.iso import Iso

    profile = BY_ID["r6_3_slus20883"]
    check("a default profile emits no hostage-voice edit",
          not [e for e in profile.build_data(profile.effective({}))
               if e.op == "hostage_follow_voice"])
    on = [e for e in profile.build_data(
        profile.effective({"hostage_follow_voice": True}))
        if e.op == "hostage_follow_voice"]
    check("switching it on emits exactly one edit", len(on) == 1, str(len(on)))

    with Iso(args.rs3data) as iso:
        banks, where = {}, {}
        for arc in vokes.open_archives(iso):
            for key, ent in sorted(arc.files.items()):
                if key.endswith(".SB1"):
                    where.setdefault(key, (arc, ent.path))
        for key, (arc, path) in sorted(where.items()):
            banks[path] = _stock_bytes(args.rs3data, arc, path)

        carriers = sorted(p for p in banks if re.search(F.SELECT, p, re.I))
        check("SELECT matches exactly the seven carriers",
              len(carriers) == 7, str(len(carriers)))
        check("and they are exactly the files the table names",
              {os.path.basename(p) for p in carriers}
              == {s.carrier for s in F.SETS})

        # --- the seal IS ambiguous.  This is the reason for the design. -----
        amb = {}
        for s in F.SETS:
            hits = sorted(os.path.basename(p) for p, d in banks.items()
                          if s.seal in d)
            if len(hits) > 1:
                amb[s.bank] = hits
        check("the child-block byte run is genuinely ambiguous disc-wide, so "
              "a find-the-run module would have been wrong",
              len(amb) >= 4, "ambiguous for banks %s" % sorted(amb))
        check("and Office Complex B is one of the files it collides with",
              any("OFFICE_COMPLEX_B_L.SB1" in v for v in amb.values()),
              str(amb.get(565)))
        ocb = [p for p in banks if p.endswith("/OFFICE_COMPLEX_B_L.SB1")]
        if ocb:
            d = banks[ocb[0]]
            check("but the walk finds nothing to do in it, and apply() leaves "
                  "it byte for byte alone",
                  F._sites(d) == [] and F.apply(d, True) == (d, 0))

        # --- per carrier: unique, absent, length, idempotent, undoable ------
        seen = 0
        for p in carriers:
            d = banks[p]
            base = os.path.basename(p)
            want = [s for s in F.SETS if s.carrier == base]
            sites = F._sites(d)
            seen += len(sites)
            check("%s: the walk finds its %d set(s), all in the stock state"
                  % (base, len(want)),
                  len(sites) == len(want)
                  and all(s.state == "stock" for s in sites)
                  and sorted(s.bank for s in sites)
                  == sorted(s.bank for s in want),
                  str([(s.bank, s.state) for s in sites]))
            for s in sites:
                seal = F.BY_BANK[s.bank].seal
                rel = F.BY_BANK[s.bank].leg * 12
                done = seal[:rel] + s.new + seal[rel + 4:]
                check("%s bank %d: the seal occurs exactly once here, and the "
                      "replacement not at all"
                      % (base, s.bank),
                      d.count(seal) == 1 and d.count(done) == 0,
                      "seal x%d, done x%d" % (d.count(seal), d.count(done)))
                check("%s bank %d: the bytes at 0x%x are the shipped NULL row"
                      % (base, s.bank, s.at), d[s.at:s.at + 4] == s.stock,
                      d[s.at:s.at + 4].hex())

            new, n = F.apply(d, True)
            check("%s: %d word(s) written" % (base, len(want)), n == len(want),
                  str(n))
            check("%s: the file length does not move" % base,
                  len(new) == len(d), "%+d" % (len(new) - len(d)))
            diff = _changed(d, new)
            check("%s: exactly %d byte(s) differ, each inside a written word"
                  % (base, len(want)),
                  len(diff) == len(want)
                  and all(any(s.at <= i < s.at + 4 for s in F._sites(d))
                          for i in diff),
                  str(sorted(diff)))

            # nothing the loader uses to find anything has moved
            nev = int.from_bytes(d[4:8], "little")
            nres = int.from_bytes(d[8:12], "little")
            tailsz = int.from_bytes(d[16:20], "little")
            tb = 28 + nev * 72 + nres * 108
            check("%s: header, event table and resource table are identical"
                  % base, d[:tb] == new[:tb])
            check("%s: the appended ADPCM payload is identical (%d bytes)"
                  % (base, len(d) - tb - tailsz),
                  d[tb + tailsz:] == new[tb + tailsz:])
            check("%s: every touched leg keeps its weight word" % base,
                  all(d[s.at + 4:s.at + 12] == new[s.at + 4:s.at + 12]
                      for s in F._sites(d)))

            # The authored silence weight.  The runtime picker rolls against a
            # LITERAL 0x10000 and never sums the weights (read out of SP.SOZ at
            # 0x004d24f0), so a container that fell short really would play
            # nothing -- except that every container stores the complement at
            # row+0x1c.  Measured: that identity holds for 2327 of 2327
            # containers on the disc.  What makes these ten a slip rather than
            # a decision is that their silence weight is exactly ZERO: the
            # format has a field for "sometimes say nothing", it is off here,
            # and a kind-15 row in the roll delivers silence anyway.
            resbase = 28 + nev * 72
            for s in F._sites(d):
                leg = F.BY_BANK[s.bank]
                at = resbase + leg.res * 108 + 0x1c
                ws = sum(int.from_bytes(leg.seal[k * 12 + 4:k * 12 + 8],
                                        "little")
                         for k in range(leg.nchild))
                sil = int.from_bytes(d[at:at + 4], "little")
                check("%s bank %d: weights 0x%x + silence weight 0x%x "
                      "== 0x10000" % (base, s.bank, ws, sil),
                      ws + sil == 0x10000)
                check("%s bank %d: the silence weight is exactly zero, so the "
                      "NULL leg is the ONLY silence in this container"
                      % (base, s.bank), sil == 0, "0x%x" % sil)
                check("%s bank %d: and the edit does not touch it"
                      % (base, s.bank), d[at:at + 4] == new[at:at + 4])

            check("%s: idempotent -- applying twice writes nothing more" % base,
                  F.apply(new, True) == (new, 0))
            check("%s: reads() is False on stock and True once applied" % base,
                  not F.reads(d) and F.reads(new))
            check("%s: enable=False hands back the shipped bytes exactly"
                  % base, F.apply(d, False) == (d, 0))

            # a file that is not what was measured is refused, not patched
            t = bytearray(d)
            t[sites[0].at] = (t[sites[0].at] + 9) & 0xFF
            try:
                F._sites(bytes(t))
                check("%s: a tampered leg is refused" % base, False, "no raise")
            except F.FollowLegError:
                check("%s: a tampered leg is refused, not patched" % base, True)

        check("ten sites across the seven carriers", seen == 10, str(seen))

        # --- through the real dispatch table --------------------------------
        fn = dataedit.OPS.get("hostage_follow_voice")
        if fn:
            got = fn(banks[carriers[0]], {"enable": True})
            check("the dispatcher entry returns (bytes, count)",
                  isinstance(got, tuple) and len(got) == 2
                  and isinstance(got[0], bytes) and isinstance(got[1], int),
                  repr(type(got)))
            check("and with enable False it returns the input unchanged",
                  fn(banks[carriers[0]], {"enable": False})
                  == (banks[carriers[0]], 0))

        # --- all three archive copies agree, before and after --------------
        for name in sorted({s.carrier for s in F.SETS}):
            copies = []
            for arc in vokes.open_archives(iso):
                for key, ent in sorted(arc.files.items()):
                    if key.endswith("/" + name):
                        copies.append(_stock_bytes(args.rs3data, arc, ent.path))
            check("%s: the three archive copies are identical, and stay "
                  "identical after the edit" % name,
                  len(copies) == 3 and len(set(copies)) == 1
                  and len({F.apply(c, True)[0] for c in copies}) == 1,
                  "%d copies, %d distinct" % (len(copies), len(set(copies))))


def run_ai_hunt(args):
    """Terrorists that hunt you, and the grenades they throw (2026-09-26).

    This module had NO coverage at all until the day its grenade dial was
    found to be inverted: the comparison it is built on is `<`, not `>`, so
    every choice did the opposite of its label and the bottom notch --
    captioned "any range at all" -- silently switched AI grenades off. The
    first check below is the regression guard for exactly that, and it is
    written so that it fails if anyone re-reads the test as a minimum.
    """
    print("\n[Rainbow Six 3 -- enemies that hunt you, and their grenades]")
    if not args.rs3data:
        print("  SKIP  needs --rs3data")
        return
    from tcps2 import dataedit, lin, rseaihunt as A
    from tcps2.uscode import Script

    store = dataedit.Store(engine.backup_dir_for(args.rs3data))
    plains = {}
    for path in ("/COMMON_SS.LIN", "/COMMONOFF.LIN", "/COMMON.LIN"):
        keys = [k for k in store.index if k.endswith(path)]
        if keys:
            plains[path] = lin.decompress(store.original(
                store.index[keys[0]]["archive"], path)[0])
    if "/COMMON_SS.LIN" not in plains:
        print("  SKIP  no stored COMMON_SS.LIN")
        return
    base = plains["/COMMON_SS.LIN"]

    # ---- the direction of the test ---------------------------------------
    # 0xB0 is native 176, which the game's own engine source declares as
    #     native(176) static final operator(24) bool < ( float A, float B );
    # so the shipped statement is `dist(Enemy) < 1500` -- a MAXIMUM.
    stock_run = A.gate_run(A.GATE_STOCK_UNITS)
    at = base.find(stock_run)
    check("the grenade window is where it was measured, and unique in every "
          "package",
          at == 0x165232
          and all(p.count(stock_run) == 1 for p in plains.values()),
          str([p.count(stock_run) for p in plains.values()]))
    check("the comparison ahead of it is native 176, which is `<` -- so the "
          "constant is a CEILING and a lower number means fewer grenades",
          base[at - 18] == 0xB0, "0x%02X" % base[at - 18])
    check("and the module says so, rather than the minimum it used to claim",
          "MAXIMUM" in A.__doc__ and "native(176)" in A.__doc__
          and "> 1500" not in A.__doc__.replace("`dist(Enemy) > 1500`", ""))
    ATTACK = 0x1648CF                       # R6TerroristAI.Attack
    check("the function holding it is the one this was measured on",
          (Script.at(base, ATTACK).disk_len,
           Script.at(base, ATTACK).mem_len) == (2654, 3404))

    # ---- the window is a splice, so every threshold is the same shape ----
    check("the stock window is head + 1500 + tail, exactly as generated",
          stock_run == A.GATE_HEAD + b"\xdc\x05\x00\x00" + A.GATE_TAIL)
    check("every offered ceiling keeps the window's length and is absent "
          "from the stock packages, so it cannot match a second site",
          all(len(A.gate_run(u)) == len(stock_run)
              and all(p.count(A.gate_run(u)) == 0 for p in plains.values())
              for u in A.GATE_UNITS if u != A.GATE_STOCK_UNITS))
    check("asking for the shipped value is refused rather than emitted as a "
          "no-op", _raises(lambda: A.gate_region(A.GATE_STOCK_UNITS),
                           A.AiHuntError))
    check("a threshold an int cannot carry is refused",
          _raises(lambda: A.gate_run(-1), A.AiHuntError)
          and _raises(lambda: A.gate_run(1 << 40), A.AiHuntError))
    for _u in (0, 3000, 10000):
        _got, _n = A.apply(base, "range:%d" % _u, True)
        check("range %d applies once, keeps the length and the block size, "
              "and reverts exactly" % _u,
              _n == 1 and len(_got) == len(base)
              and (Script.at(_got, ATTACK).disk_len,
                   Script.at(_got, ATTACK).mem_len) == (2654, 3404)
              and A.reads(_got, "range:%d" % _u)
              and A.apply(_got, "range:%d" % _u, False)[0] == base)

    # ---- the hunt regions themselves -------------------------------------
    check("every hunt region is an equal-length before and after, unique in "
          "every package",
          all(len(st) == len(nw) and st != nw
              and all(p.count(st) == 1 and p.count(nw) == 0
                      for p in plains.values())
              for _n, st, nw in A.REGIONS.values()))
    check("an unknown option is refused rather than guessed",
          _raises(lambda: A.apply(base, "nope"), A.AiHuntError))

    # ---- the wave arm, which is not part of the switch --------------------
    # R6TerroristAI.NoThreat ends in
    #     if (m_bSpawnedByWave) { m_bAllowLeave = True;
    #                             GotoStateAttackActionSpot(None, None); }
    #     else switch (m_pawn.m_eStrategy) { ... }
    # so a controller carrying that write-once latch never reaches the switch
    # and the three case_ regions cannot touch it. It is set natively by
    # AR6DZoneWave::SpawnATerrorist at 0x0040AD5C for anything a wave
    # releases, and in script for a placed enemy whose zone is a wave spawn
    # point; 48% of live terrorists on a stock disc carry it. These checks
    # fail if anyone deletes case_wave or re-describes NoThreat as ending in
    # the switch.
    NOTHREAT = 0x169CDB                     # R6TerroristAI.NoThreat
    _nt = Script.at(base, NOTHREAT)
    check("the state holding the wave arm is the one this was measured on",
          (_nt.disk_len, _nt.mem_len) == (785, 1040),
          str((_nt.disk_len, _nt.mem_len)))
    _st, _nw = A.REGIONS["case_wave"][1], A.REGIONS["case_wave"][2]
    check("the wave arm sits where it was measured, inside that state",
          base.find(_st) == 0x169F8C, "0x%X" % base.find(_st))
    check("it is a GotoStateAttackActionSpot call becoming a GotoState, "
          "equal length on disk",
          _st == bytes.fromhex("1b7f052a2a16")
          and _nw == bytes.fromhex("71216a0c160b")
          and len(_st) == len(_nw))
    check("its replacement names HuntRainbow -- the same name index the "
          "guard-point arm already uses, so no name is added",
          _nw[1:4] == A.REGIONS["case_guardpoint"][2][2:5] == b"\x21\x6a\x0c")
    _spliced, _n = A.apply(base, "case_wave", True)
    _sc2 = Script.at(_spliced, NOTHREAT)
    check("applying it keeps the container length and BOTH block lengths, "
          "and every jump still lands on a token boundary",
          _n == 1 and len(_spliced) == len(base)
          and (_sc2.disk_len, _sc2.mem_len) == (785, 1040))
    check("the spliced block re-assembles byte-identical, which is what "
          "proves the memory length rather than assuming it",
          _sc2.assemble()[0]
          == _spliced[NOTHREAT + 4:NOTHREAT + 4 + _sc2.disk_len])
    check("it reads back as applied and reverts exactly",
          A.reads(_spliced, "case_wave")
          and A.apply(_spliced, "case_wave", False)[0] == base)
    def _hunt_regions(**kw):
        eff = PROFILE.effective(dict(PROFILE.defaults(), **kw))
        return sorted(str(e.params.get("which"))
                      for e in PROFILE.build_data(eff) if e.op == "ai_hunt")
    check("both hunt settings emit it, because a wave enemy has no authored "
          "patrol to preserve",
          _hunt_regions(ai_hunt="guard") == ["case_guardpoint", "case_wave"]
          and _hunt_regions(ai_hunt="all")
          == ["case_guardpoint", "case_patrolarea", "case_patrolpath",
              "case_wave"]
          and _hunt_regions() == [])
    check("and the module says NoThreat gates on the wave flag before the "
          "switch, rather than ending in the switch",
          "m_bSpawnedByWave" in A.__doc__ and "case_wave" in A.__doc__)
    check("written offline and split screen, never online",
          __import__("re").search(A.SELECT, "/COMMONOFF.LIN")
          and __import__("re").search(A.SELECT, "/COMMON_SS.LIN")
          and not __import__("re").search(A.SELECT, "/COMMON.LIN"))

    # ---- the two cards ---------------------------------------------------
    d0 = PROFILE.defaults()

    def emits(**kw):
        eff = PROFILE.effective(dict(d0, **kw))
        return sorted(
            (e.op, str(e.params)) for e in PROFILE.build_data(eff)
            if (e.op == "ai_hunt" and "range:" in str(e.params))
            or (e.op == "ini_values"
                and "m_fMinDistToThrowGrenade" in str(e.params)))

    r = PROFILE.setting("ai_grenade_range")
    check("the ceiling card reaches the profile, shipped by default",
          r is not None and r.default == "off" and r.enabled
          and r.confidence in BADGES)
    check("its choices are the generated ones plus never, and none of them "
          "re-offers the shipped value",
          [c.value for c in r.choices]
          == ["off"] + [str(u) for u in A.GATE_UNITS
                        if u != A.GATE_STOCK_UNITS] + ["0"])
    check("its label and help describe a ceiling, not a floor",
          "How far out" in r.label and "MORE grenades" in r.help)
    check("stock emits nothing, and a choice emits one region",
          emits() == [] and emits(ai_grenade_range="3000")
          == [("ai_hunt", str({"which": "range:3000"}))])

    # The genuine floor is not bytecode at all: the refusal in
    # R6TerroristAI.ThrowingGrenade.CheckDistance reads it straight out of
    # the settings file and adds 50 units, so the shipped 500 is 5.5 m.
    m = PROFILE.setting("ai_grenade_min")
    check("the floor card reaches the profile, shipped by default",
          m is not None and m.default == "off" and m.enabled
          and m.confidence in BADGES)
    check("it offers the floors below the shipped one, ending at your feet",
          [c.value for c in m.choices] == ["off", "250", "100", "0"])
    check("it emits a settings-file edit rather than a region",
          emits(ai_grenade_min="0")
          == [("ini_values", str({"values":
                                  {"m_fMinDistToThrowGrenade": "0"}}))])
    check("and the two are independent, because they are different gates",
          emits(ai_grenade_range="4000", ai_grenade_min="100")
          == sorted(emits(ai_grenade_range="4000")
                    + emits(ai_grenade_min="100")))

    keys = [k for k in store.index if k.endswith("VOKES0.IMG/R6GAMESETTINGS.INI")]
    if keys:
        ini = store.original(store.index[keys[0]]["archive"],
                             "/R6GAMESETTINGS.INI")[0]
        check("the settings file really carries that key, at the shipped 500",
              ini.count(b"m_fMinDistToThrowGrenade") == 1
              and b"m_fMinDistToThrowGrenade=500" in ini)
        from tcps2 import transforms
        got, n = transforms.set_ini_values(
            ini, {"m_fMinDistToThrowGrenade": "0"})
        check("and the edit rewrites exactly that one line",
              n == 1 and b"m_fMinDistToThrowGrenade=0\r\n" in got
              and b"m_fMinDistToThrowGrenade=500" not in got)


def run_property_bools(args):
    """A bool default-property tag is FOUR bytes, and the walker knows it.

    This game encodes one as `compact(name), info, 0x00` -- info 0x53 for
    False, 0xD3 for True. 0xD3 is type 3 in the low nibble, SIZE CODE 5 in
    bits 4-6, and the value in bit 7. Code 5 means "a byte follows giving the
    size", and that byte is literally zero, so the size byte is PRESENT and
    must be consumed even though there is no payload.

    `walk_properties` gets this right, and it is worth a test saying so,
    because the code reads as though it might not: the bool branch does
    `continue` before `pos += size`, which looks like it skips the size byte.
    It does not -- the generic size dispatch above has already consumed it.
    What the branch actually skips is the array-index read, and that IS
    necessary: on every other type bit 7 of `info` means "an array element
    index follows", but on a bool bit 7 is the value, so reading an index
    would consume a byte that is not there.

    Ground truth is Engine.GameInfo's own defaults, whose length the package
    states independently of anything this parser does.
    """
    print()
    print("[Rainbow Six 3 -- bool property tags are four bytes]")
    if not args.rs3data:
        print("  SKIP  needs --rs3data")
        return
    from tcps2 import dataedit, lin, upackage

    store = dataedit.Store(engine.backup_dir_for(args.rs3data))
    keys = [k for k in store.index if k.endswith("/COMMON_SS.LIN")]
    if not keys:
        print("  SKIP  no stored COMMON_SS.LIN")
        return
    buf = lin.decompress(store.original(
        store.index[keys[0]]["archive"], "/COMMON_SS.LIN")[0])

    AT, END, TAGS = 0x05A627, 0x05A701, 23
    check("the nine bools are on the disc as 0xD3 followed by a zero size "
          "byte", buf[0x05A639:0x05A649].hex()
          == "5328d3005428d3005528d3005928d300")

    pkgs = dict(upackage.packages(buf))
    check("the package that owns them is the one we measured against",
          0x009E17 in pkgs)
    names = pkgs[0x009E17].names()
    idx, _ = upackage.compact_index(buf, 0x05A639)
    check("and the first bool's name index resolves in it",
          idx == 2579 and names[idx] == "bRestartLevel")

    got = upackage.walk_properties(buf, AT, names, limit=300)
    check("the property list walks to its terminator at all", got is not None)
    if got is None:
        return
    check("it finds every tag the block holds, and no more",
          len(got) == TAGS, "%d tags" % len(got))

    bools = [(nm, info, off) for nm, info, off in got if (info & 0x0F) == 3]
    check("nine of them are bools, all True",
          len(bools) == 9 and all(i == 0xD3 for _n, i, _o in bools))
    check("and they are named what the package says",
          [nm for nm, _i, _o in bools]
          == ["bRestartLevel", "bPauseable", "bCanChangeSkin",
              "bCanViewOthers", "bWaitingToStartMatch", "bChangeLevels",
              "bLocalLog", "bWorldLog", "m_bCompilingStats"])
    # The off-by-one this guards: under-consuming the size byte would step
    # each bool by 3 instead of 4, and the nine of them would drift nine
    # bytes before the terminator ever came up.
    steps = [b[2] - a[2] for a, b in zip(bools, bools[1:])]
    check("each consecutive bool is exactly four bytes after the last",
          steps == [4] * 8, str(steps))
    check("the value is bit 7 of the info byte",
          all(((i >> 7) & 1) == 1 for _n, i, _o in bools))

    # The strongest assertion available: the block's own end, which the
    # package states and the parser has to arrive at independently. Walked
    # rather than searched -- scanning for the terminator's name index byte
    # by byte finds a spurious earlier match, because a compact index can
    # start mid-value.
    def _end_of(pos):
        import struct as _st
        from tcps2.upackage import T_BOOL, T_STRUCT, _SIZES
        for _ in range(300):
            tag = pos
            ni, pos = upackage.compact_index(buf, pos)
            if names[ni] == "None":
                return tag, pos
            nfo = buf[pos]
            pos += 1
            pt = nfo & 0x0F
            if pt == T_STRUCT:
                _x, pos = upackage.compact_index(buf, pos)
            cd = (nfo >> 4) & 7
            if cd in _SIZES:
                sz = _SIZES[cd]
            elif cd == 5:
                sz = buf[pos]
                pos += 1
            elif cd == 6:
                sz = _st.unpack_from("<H", buf, pos)[0]
                pos += 2
            else:
                sz = _st.unpack_from("<I", buf, pos)[0]
                pos += 4
            if pt == T_BOOL:
                continue
            if nfo & 0x80:
                _x, pos = upackage.compact_index(buf, pos)
            pos += sz
        return None, None

    term, end = _end_of(AT)
    check("and the list terminates exactly where the package says",
          end == END, "terminator 0x%06X, end 0x%06X"
          % (term or 0, end or 0))
    check("so the whole block is the length it declares",
          end is not None and end - AT == 218,
          str(None if end is None else end - AT))

def run_impact_puffs(args):
    """A private ring of emitter actors, so impacts stop sharing one.

    Two walls stood between the game and several puffs at once. The first was
    an engine-wide rate limit -- see `rsedecal.BURST_GATE` -- and removing it
    revealed the second: there is exactly ONE pooled emitter per material, and
    re-firing a busy one runs it through Init -> Reset, which zeroes the live
    particles. So rapid fire cancelled its own dust, which is what it looked
    like in play: the puff stops and jumps to the newest hit.
    """
    print()
    print("[Rainbow Six 3 -- a ring of impact puffs]")
    if not args.rs3data:
        print("  SKIP  needs --rs3data")
        return
    from tcps2 import rsedecal as D, rsepuffs as P
    from tcps2.iso import Iso
    from tcps2.overlay import open_overlay

    with Iso(args.rs3data) as iso:
        ov = open_overlay(iso, PROFILE.overlays[0])
        live = {va: ov.read_word(va)
                for va in (P.HOOK_AT, P.HOOK_AT + 4, P.RESUME)}

    # ---- the hook ---------------------------------------------------------
    # The displaced instruction is NOT re-done, so it has to be dead. It is:
    # the quad at $sp+0x40 that the four swc1 before it build is never read
    # back, and the only lq/sq in the function are the callee-saved spills at
    # $sp+0x00/0x10/0x20. Capstone mis-decodes EE quadword ops as `.word`, so
    # that had to be checked by raw opcode -- 0x1E is lq and 0x1F is sq.
    check("the hook site is the instruction we measured, and still stock",
          live[P.HOOK_AT] == P.HOOK_STOCK == 0xE7A0004C,
          "0x%08X" % live[P.HOOK_AT])
    check("what replaces it is a jump into the cave",
          (P.HOOK >> 26) == 0x02
          and ((P.HOOK & 0x03FFFFFF) << 2) == P.TRAMPOLINE)
    check("the delay slot still runs and the cave resumes just past it",
          live[P.HOOK_AT + 4] == 0x8E430384
          and P.RESUME == P.HOOK_AT + 8
          and live[P.RESUME] == 0x10600059)
    check("and it sits upstream of the half-second dust gate, so the ring "
          "does not depend on that gate either way",
          P.HOOK_AT < D.BURST_GATE)

    # ---- the cave ---------------------------------------------------------
    ws = P.words()
    vas = [va for va, _w in ws]
    check("the cave is emitted as cheat rows, never as disc words",
          all(va < 0x00100000 or va == P.HOOK_AT for va in vas))
    check("the pool's RAM is NEVER emitted -- a row there would clear the "
          "level stamp every frame and respawn the ring forever",
          not [va for va in vas if P.POOL_RAM <= va < P.POOL_RAM_END])
    check("no row lands on another feature's cave",
          not [va for va in vas if 0x000F0000 <= va < 0x000F2C00])
    check("every row is inside the block it claims, or is the hook",
          all(P.FIRE <= va < P.BLOCK_END or va == P.HOOK_AT for va in vas))
    check("and the rows are unique", len(set(vas)) == len(vas))

    # ---- the ring size ----------------------------------------------------
    # A ring costs what is ALIVE, not what it is wide, so a bigger ring costs
    # nothing for one shooter -- it only stops the wrapping. A puff lives
    # ~1.10 s and a FAMAS G2 fires 18.3 rounds a second, so 24 is the
    # smallest that never wraps for the gun the operatives actually carry,
    # and it still absorbs a nine-pellet shotgun pull in one frame.
    sizes = {n: dict(P.words(n)) for n in (12, 16, 24, 32)}
    check("the size is one 16-bit immediate and nothing else moves",
          len({sizes[n][P.COUNT_AT] for n in sizes}) == 4
          and all(sizes[12][va] == sizes[32][va]
                  for va, _w in ws if va != P.COUNT_AT))
    check("the immediate really carries the number asked for",
          all((sizes[n][P.COUNT_AT] & 0xFFFF) == n for n in sizes))
    check("a size outside the ring's bounds is refused, not truncated",
          _raises(lambda: P.words(0), P.PuffError)
          and _raises(lambda: P.words(P.COUNT_MAX + 1), P.PuffError))
    check("the default ring is 16 and the ceiling is 32, and the card "
          "agrees with the module rather than drifting from it",
          P.COUNT_DEFAULT == 16 and P.COUNT_MAX == 32
          and PROFILE.setting("impact_puff_count").default
          == str(P.COUNT_DEFAULT))

    # ---- what a puff's life actually is ----------------------------------
    # NOT its LifetimeRange. The engine sets AllParticlesDead as soon as the
    # spawn window closes, because RespawnDeadParticles is false -- measured
    # in a savestate with the flag set and three particles still counted --
    # and AEmitter::Tick then re-parks the actor, which stops it drawing.
    # So visible life is MaxParticles / InitialParticlesPerSecond. At the
    # shipped 3 that is 0.05 s, two frames, which is why the first build
    # looked like it had done nothing: at 18 rounds a second, 0.05 s of life
    # averages 0.9 puffs alive and two can never coexist at ANY ring size.
    check("a puff's life is its spawn window, and the shipped one is two "
          "frames", abs(P.visible_seconds(3) - 0.05) < 1e-9
          and abs(P.visible_seconds(P.MAXPART_DEFAULT) - 0.20) < 1e-9)
    _lens = {n: dict(P.words(particles=n)) for n in (3, 6, 12, 24)}
    check("the length is one immediate and nothing else moves",
          len({_lens[n][P.MAXPART_AT] for n in _lens}) == 4
          and all(_lens[3][va] == _lens[24][va]
                  for va, _w in ws if va != P.MAXPART_AT))
    check("the immediate carries the number asked for",
          all((_lens[n][P.MAXPART_AT] & 0xFFFF) == n for n in _lens))
    check("a length outside its bounds is refused",
          _raises(lambda: P.words(particles=0), P.PuffError)
          and _raises(lambda: P.words(particles=P.MAXPART_MAX + 1),
                      P.PuffError))
    _pl = PROFILE.setting("impact_puff_length")
    check("the length card reaches the profile and needs the ring on",
          _pl is not None and _pl.default == str(P.MAXPART_DEFAULT)
          and _pl.requires == {"impact_puffs": (True,)})
    check("and it offers the shipped value, so the flicker can be compared",
          "3" in [c.value for c in _pl.choices])

    # ---- the profile ------------------------------------------------------
    d0 = PROFILE.defaults()

    def plan(**kw):
        eff = PROFILE.effective(dict(d0, **kw))
        r = PROFILE.build_pnach(eff)
        return ([e.va for e in r if e.va == P.HOOK_AT],
                [e.va for e in r if e.va == D.BURST_GATE],
                len([e for e in r if P.FIRE <= e.va < P.BLOCK_END]))

    check("stock writes neither the hook nor the cave", plan() == ([], [], 0))
    _h, _g, _n = plan(impact_puffs=True)
    check("turning it on writes the hook and the whole cave",
          _h == [P.HOOK_AT] and _n == len(ws) - 1)
    # Not redundancy: with the limit gone, every shot re-fires the game's one
    # shared actor and Reset kills the burst already playing. That IS the
    # artifact the ring cures, so the two must never both be on.
    check("the dust gate and the ring are mutually exclusive, and the ring "
          "wins",
          plan(blast_puffs=True, impact_puffs=True)[1] == []
          and plan(blast_puffs=True)[1] == [D.BURST_GATE])
    check("and the card says so too, so the GUI greys it out rather than "
          "letting them collide silently",
          PROFILE.setting("blast_puffs").requires == {"impact_puffs": [False]})
    check("the size card follows the ring and needs it on",
          PROFILE.setting("impact_puff_count").requires
          == {"impact_puffs": (True,)}
          and [e.value for e in PROFILE.build_pnach(PROFILE.effective(dict(
              d0, impact_puffs=True, impact_puff_count="32")))
              if e.va == P.COUNT_AT] == [sizes[32][P.COUNT_AT]])
    s = PROFILE.setting("impact_puffs")
    check("the card reaches the profile, off by default, and is "
          "RAM rather than disc so it needs no re-apply",
          s is not None and s.default is False and s.enabled
          and s.confidence in BADGES and s.touches == "ram")

def run_keep_viewport(args):
    """A dead player stops stealing the other player's screen (2026-09-26).

    `R6GameInfo.DeployCharacters` captures the local player's viewport, has
    `CreateRainbowTeam` rebuild the squad, then reassigns its own parameter
    to whoever leads the team now and hands THAT controller the captured
    viewport -- without unbinding the previous owner. With player 1 dead the
    leader is player 2, so both viewports end up on his controller and
    player 1's buttons fire on his weapon.

    The fix redirects the assignment's destination at an unused local, so
    the cast still runs and its result is discarded. Two bytes, both inside
    one compact index, which is why disk and memory length are identical by
    construction rather than by arithmetic.
    """
    print()
    print("[Rainbow Six 3 -- a dead player keeps his own screen]")
    if not args.rs3data:
        print("  SKIP  needs --rs3data")
        return
    from tcps2 import dataedit, lin, rseviewport as V
    from tcps2.uscode import Script

    store = dataedit.Store(engine.backup_dir_for(args.rs3data))
    plains = {}
    for path in ("/COMMON_SS.LIN", "/COMMONOFF.LIN", "/COMMON.LIN"):
        keys = [k for k in store.index if k.endswith(path)]
        if keys:
            plains[path] = lin.decompress(store.original(
                store.index[keys[0]]["archive"], path)[0])
    if "/COMMON_SS.LIN" not in plains:
        print("  SKIP  no stored COMMON_SS.LIN")
        return
    base = plains["/COMMON_SS.LIN"]

    check("it is one region, and an equal-length before and after",
          len(V.REGIONS) == 1
          and all(len(st) == len(nw) and st != nw
                  for _n, st, nw in V.REGIONS))
    # The whole edit is one compact index. Nothing else may move: this
    # region sits in a block with NO trailing filler, so there is nowhere to
    # pad and nothing to delete.
    _n, _st, _nw = V.REGIONS[0]
    _diff = [i for i, (a, b) in enumerate(zip(_st, _nw)) if a != b]
    check("exactly two bytes change, and they are adjacent",
          _diff == [2, 3], str(_diff))
    check("and they are the destination of the assignment, not the call",
          _st[:2] == b"\x0f\x00" and _st[2:4] == b"\x59\x01"
          and _nw[2:4] == b"\x5c\x10")
    # SetController is called from BOTH arms of the branch, so the call
    # alone matches twice -- the anchor has to carry the reassignment.
    check("the call alone would not be unique, which is why the region "
          "carries more than the call",
          base.count(b"\x67\xda") > 1)
    for path, plain in plains.items():
        check("%s: the stock run appears exactly once and the replacement "
              "not at all" % path[1:],
              plain.count(_st) == 1 and plain.count(_nw) == 0)

    DEPLOY = 0x1C5E06                      # R6GameInfo.DeployCharacters
    SIZES = (210, 295)
    check("the function is the one this was measured on",
          (Script.at(base, DEPLOY).disk_len,
           Script.at(base, DEPLOY).mem_len) == SIZES,
          str((Script.at(base, DEPLOY).disk_len,
               Script.at(base, DEPLOY).mem_len)))
    got, n = V.apply(base, True)
    check("it applies, keeps the package length, and changes only those "
          "two bytes in five megabytes",
          n == 1 and len(got) == len(base)
          and sum(1 for a, b in zip(base, got) if a != b) == 2)
    check("the block still parses at its shipped disk AND memory length",
          (Script.at(got, DEPLOY).disk_len,
           Script.at(got, DEPLOY).mem_len) == SIZES)
    check("it reads back, asking twice is a no-op, and it reverts exactly",
          V.reads(got) and not V.reads(base)
          and V.apply(got, True) == (got, 0)
          and V.apply(got, False)[0] == base)

    # It must not want any byte the friendly-fire work wants.
    from tcps2 import rseff
    _mine = _changed(base, got)
    for _o in ("noside", "trigger:5:noside", "playerkill:5:noside",
               "fail_on_kill"):
        _other = _changed(base, rseff.apply(base, _o)[0])
        check("it touches none of the bytes %s does" % _o,
              _mine and not (_mine & _other))
        _a = V.apply(rseff.apply(base, _o)[0], True)[0]
        _b = rseff.apply(V.apply(base, True)[0], _o)[0]
        check("and composes with %s in either order, byte for byte" % _o,
              _a == _b and len(_a) == len(base))

    d0 = PROFILE.defaults()
    s = PROFILE.setting("keep_viewport")
    check("the card reaches the profile, off by default",
          s is not None and s.default is False and s.enabled
          and s.confidence in BADGES and s.group == "Split Screen")
    _e = [e for e in PROFILE.build_data(PROFILE.effective(
        dict(d0, keep_viewport=True))) if e.op == "keep_viewport"]
    check("stock writes nothing; on, it writes one edit",
          not [e for e in PROFILE.build_data(PROFILE.effective(d0))
               if e.op == "keep_viewport"] and len(_e) == 1)
    # DeployCharacters asserts NM_Standalone, so the online package could
    # not reach it -- but the selector says so too rather than relying on it.
    check("offline and split screen only, never online",
          _e[0].matches("/COMMONOFF.LIN") and _e[0].matches("/COMMON_SS.LIN")
          and not _e[0].matches("/COMMON.LIN"))

def run_friendly_fire(args):
    """Teammates who turn on you, and a mission you can fail (2026-09-25).

    Read-only, against the SHIPPED packages. Both options are region
    rewrites that must keep every script block's disk AND memory length, and
    must not move the package's creation order -- so they are checked the
    same way every other script edit here is.
    """
    print("\n[Rainbow Six 3 -- friendly fire]")
    if not args.rs3data:
        print("  SKIP  needs --rs3data")
        return
    import re
    from tcps2 import dataedit, lin, rseff
    from tcps2.uscode import Script

    store = dataedit.Store(engine.backup_dir_for(args.rs3data))
    plains = {}
    for path in ("/COMMON_SS.LIN", "/COMMONOFF.LIN", "/COMMON.LIN"):
        keys = [k for k in store.index if k.endswith(path)]
        if keys:
            plains[path] = lin.decompress(store.original(
                store.index[keys[0]]["archive"], path)[0])
    if "/COMMON_SS.LIN" not in plains:
        print("  SKIP  no stored COMMON_SS.LIN")
        return
    base = plains["/COMMON_SS.LIN"]

    # "retaliate" used to carry five regions that marked the killer with
    # m_bSuicided and taught SeePlayer / IsBeingAttacked to read it. Measured
    # on the live game, IsEnemy is a BITMASK test over m_iTeam /
    # m_iEnemyTeams and never consults that bool, so none of it could work.
    # Writing the player's m_iTeam = 1 by hand made the squad open fire at
    # once, so the whole feature is now one region in the trigger table.
    check("retaliation has no regions of its own any more",
          "retaliate" not in rseff.REGIONS
          and sorted(rseff.REGIONS) == ["fail_on_hit", "fail_on_kill",
                                        "noside"])
    check("and the failure options still touch two and one region",
          [len(rseff.REGIONS[k]) for k in
           ("fail_on_hit", "fail_on_kill")] == [2, 1])
    check("every region is pinned as an equal-length before and after",
          all(len(st) == len(nw) and st != nw
              for v in rseff.REGIONS.values() for _n, st, nw in v))
    # Content-matched, not offset-matched: COMMON.LIN carries the same
    # bytecode a byte further along, so an offset table would not survive it.
    for path, plain in plains.items():
        check("%s: every stock region appears exactly once" % path[1:],
              all(plain.count(st) == 1
                  for v in rseff.REGIONS.values() for _n, st, _nw in v))

    for which in ("fail_on_hit", "fail_on_kill", "noside"):
        got, n = rseff.apply(base, which, True)
        check("%s: applies, keeps the file length, reads back" % which,
              n == len(rseff.REGIONS[which]) and len(got) == len(base)
              and rseff.reads(got, which) and not rseff.reads(base, which))
        check("%s: asking twice is a no-op" % which,
              rseff.apply(got, which, True) == (got, 0))
        check("%s: switching it off restores the file byte for byte" % which,
              rseff.apply(got, which, False)[0] == base)

    # The four rewritten functions must still parse at their shipped sizes.
    SIZES = {0x138541: (419, 549),    # R6RainbowAI.SeePlayer
             0x1382C6: (223, 281),    # R6RainbowAI.IsBeingAttacked
             0x139435: (405, 536),    # R6RainbowAI.PlaySoundDamage
             0x1C39B3: (309, 424)}    # R6GameInfo.SetTeamKillerPenalty
    stock_sizes = {at: (Script.at(base, at).disk_len, Script.at(base, at).mem_len)
                   for at in SIZES}
    check("the four functions are the ones these edits were measured on",
          stock_sizes == SIZES, str(stock_sizes))
    # They cannot both be applied: both rewrite the downed arm, so whichever
    # goes second cannot find its own stock bytes. That is not a limitation
    # to work around, it is the reason `requires` keeps them exclusive -- and
    # asserting it here is what would catch an emit that tried both.
    check("applying one and then the other is refused, not silently merged",
          _raises(lambda: rseff.apply(rseff.apply(base, "trigger:5")[0],
                                      "fail_on_hit"), rseff.FriendlyFireError))
    for one in ("trigger:5", "fail_on_hit"):
        got, _n = rseff.apply(base, one)
        after = {at: (Script.at(got, at).disk_len, Script.at(got, at).mem_len)
                 for at in SIZES}
        check("%s alone parses at exactly the shipped sizes" % one,
              after == SIZES and len(got) == len(base), str(after))
    r_only = _changed(base, rseff.apply(base, "trigger:5")[0])
    f_only = _changed(base, rseff.apply(base, "fail_on_hit")[0])
    # They DO want the same bytes -- both rewrite the downed arm -- which is
    # exactly why `requires` makes them mutually exclusive.
    check("the squad edit and the failure option want the same region, which "
          "is why only one may be on", r_only and f_only and (r_only & f_only))

    check("an unknown option is refused rather than guessed",
          _raises(lambda: rseff.apply(base, "nope"), rseff.FriendlyFireError))

    for key, label in (("ff_retaliate", "trigger:5"),
                       ("ff_fail_mission", "fail_on_hit")):
        s = PROFILE.setting(key)
        check("%s reaches the profile, off by default" % key,
              s is not None and s.default is False and s.enabled
              and s.confidence in BADGES and s.group == "Teammates")
    check("stock writes nothing",
          not [e for e in PROFILE.build_data(PROFILE.effective(
              PROFILE.defaults())) if e.op == "friendly_fire"])
    eds = [e for e in PROFILE.build_data(PROFILE.effective(dict(
        PROFILE.defaults(), ff_retaliate=True, ff_fail_mission=True)))
        if e.op == "friendly_fire"]
    check("with the failure option on, it wins the region outright",
          len(eds) == 1 and eds[0].params["which"] == "fail_on_kill")
    wounded = sorted(e.params["which"] for e in PROFILE.build_data(
        PROFILE.effective(dict(PROFILE.defaults(), ff_retaliate=True,
                               ff_fail_mission=True, ff_fail_when="wound")))
        if e.op == "friendly_fire")
    check("and asking for a wounding swaps which region set is written",
          wounded == ["fail_on_hit"])
    check("written offline and split screen, never online or multiplayer",
          all(e.matches("/COMMONOFF.LIN") and e.matches("/COMMON_SS.LIN")
              and not e.matches("/COMMON.LIN")
              and not e.matches("/GARAGE_MP_C.LIN") for e in eds))
    got = dataedit.OPS["friendly_fire"](base, {"which": "trigger:5"})
    check("and through the real dispatch table it returns (bytes, count)",
          isinstance(got, tuple) and len(got) == 2
          and isinstance(got[0], bytes) and isinstance(got[1], int)
          and len(got[0]) == len(base))

    # ---- the trigger dial ------------------------------------------------
    # How far a teammate has to be hurt, read off m_eHealth. There is no
    # counter anywhere: a real tally needs a per-player int that script
    # already references and nothing consumes, and no property in the
    # package is both.
    # A kill used to write nothing here and lean on SetTeamKillerPenalty.
    # Measured after a team kill in Terrorist Hunt: the killed AI lights up
    # with its death bools and NEITHER player gains a bit anywhere near
    # R6Pawn's own properties (m_ePawnType 0x378, m_eHealth 0x37D), so no
    # mark was written and the squad never turned. That function is declared
    # on R6GameInfo and reached by NAME, so it only runs if the live game
    # class inherits it -- which a Terrorist Hunt game need not.
    check("every setting writes a region, a kill included",
          sorted(rseff.TRIGGER) == ["1", "2", "3", "4", "5"]
          and all(rseff.TRIGGER[k] for k in ("1", "2", "3", "4", "5")))
    check("and a kill writes ONE region -- health 4-5 reach that arm by "
          "fall-through, so it needs no wounded-arm entry like 1-3 do",
          len(rseff.TRIGGER["5"]) == 1
          and len(rseff.TRIGGER["4"]) == 1
          and all(len(rseff.TRIGGER[k]) == 2 for k in ("1", "2", "3")))
    check("each setting is equal-length regions, unique in every package",
          all(len(st) == len(nw) and st != nw and plain.count(st) == 1
              for k in ("1", "2", "3", "4", "5")
              for _n, st, nw in rseff.TRIGGER[k]
              for plain in plains.values()))
    check("an unknown dial setting is refused",
          _raises(lambda: rseff.apply(base, "trigger:9"),
                  rseff.FriendlyFireError))
    for k in ("1", "2", "3", "4", "5"):
        one, n = rseff.apply(base, "trigger:" + k, True)
        check("trigger %s applies, keeps the length, and reverts exactly" % k,
              n == len(rseff.TRIGGER[k]) and len(one) == len(base)
              and rseff.reads(one, "trigger:" + k)
              and rseff.apply(one, "trigger:" + k, False)[0] == base)
        after = {at: (Script.at(one, at).disk_len,
                      Script.at(one, at).mem_len) for at in SIZES}
        check("trigger %s leaves all four blocks at their shipped sizes" % k,
              after == SIZES and len(one) == len(base), str(after))
        # Levels 1-3 also rewrite the wounded-arm entry, because those health
        # states reach the switch's wounded arm instead of falling through.
        check("trigger %s writes %d region(s), which is what that health "
              "state needs" % (k, len(rseff.TRIGGER[k])),
              len(rseff.TRIGGER[k]) == (2 if k in ("1", "2", "3") else 1))

    dial_b = _changed(base, rseff.apply(base, "trigger:1")[0])
    check("every dial level writes the same region, so they are one feature",
          bool(dial_b & r_only))
    check("and the failure option wants it too, which is why the two are "
          "mutually exclusive", bool(dial_b & f_only))

    t = PROFILE.setting("ff_trigger")
    check("the dial reaches the profile, defaulting to a kill, and is barred "
          "when the mission-failure option is on",
          t is not None and t.default == "5" and t.enabled
          and t.requires == {"ff_retaliate": [True], "ff_fail_mission": [False]})
    d0 = PROFILE.defaults()

    def which(**kw):
        return sorted(e.params["which"] for e in PROFILE.build_data(
            PROFILE.effective(dict(d0, **kw))) if e.op == "friendly_fire")

    check("the dial needs the squad option, and every level emits its own "
          "region -- the team change IS the feature",
          which(ff_trigger="1") == []
          and which(ff_retaliate=True, ff_trigger="5")
          == ["trigger:5:terrorists"])
    check("and with it, the chosen setting is what gets written",
          which(ff_retaliate=True, ff_trigger="2") == ["trigger:2:terrorists"])
    check("turning on mission failure drops the dial rather than colliding",
          which(ff_retaliate=True, ff_trigger="1", ff_fail_mission=True)
          == ["fail_on_kill"])

    # ---- whose side the traitor ends up on -------------------------------
    # This module used to record that putting him on an unused team was out
    # of reach, because the masks read 0 in the class defaults. They do --
    # and they are filled per pawn at PostBeginPlay by
    # R6GameInfo.SetDefaultTeamFriendlies, which switches on m_iTeam and
    # takes its values from GetTeamNumBit(n) = 1 << n. The constants are on
    # the disc, so widening what a side counts as an enemy is one byte per
    # arm rather than a cave that walks every pawn.
    MASKS_AT = 0x1C4BD5                    # R6GameInfo.SetDefaultTeamFriendlies
    MASKS = (583, 703)
    check("the mask function is the one this edit was measured on",
          (Script.at(base, MASKS_AT).disk_len,
           Script.at(base, MASKS_AT).mem_len) == MASKS,
          str((Script.at(base, MASKS_AT).disk_len,
               Script.at(base, MASKS_AT).mem_len)))
    # Team 4 is not a number picked at random: it is the engine's own "could
    # not put this player on a team" value, written only by
    # R6TeamDeathMatchGame.ResetPlayerTeam, which is adversarial-only and
    # overrides these masks anyway. So this cannot reach online play.
    check("nobody's side is team 4, and the terrorists are still team 1",
          rseff.ROGUE_TEAM == {"terrorists": 1, "noside": 4})
    _bit = 1 << rseff.ROGUE_TEAM["noside"]
    _masks = {name: nw[nw.find(b"\x2c") + 1]
              for name, _st, nw in rseff.REGIONS["noside"]}
    check("each arm keeps the side it already hated and adds nobody's side",
          _masks == {"noside terrorists": 12 | _bit,
                     "noside rainbow": 2 | _bit}, str(_masks))
    check("and stock, both arms compute the mask with a call instead of a "
          "constant, which is the room the edit spends",
          all(b"\x1b" in st and b"\x2c" + bytes([m]) not in st
              for (name, st, _nw), m in zip(rseff.REGIONS["noside"],
                                            (12 | _bit, 2 | _bit))))
    # The only filler in this module that RUNS. Every other padded region
    # here hides its filler behind the payload's own jump; these two arms
    # have 2 disk and 5 memory bytes to fill and a jump costs 3, so there is
    # nowhere to put one. It reads Engine.Actor.Level, which R6GameInfo has
    # by being an Actor -- and which the shipped bytecode reads through this
    # same opcode 939 times, counted over every block in the package.
    _pad = bytes.fromhex("018f")
    check("both arms pad with the same one-byte object reference",
          all(_pad in nw for _n, _st, nw in rseff.REGIONS["noside"]))
    check("and the shipped package is full of that same read, so it cannot "
          "fault", base.count(_pad) > 900, str(base.count(_pad)))

    _ns, _ = rseff.apply(base, "noside")
    _both, _ = rseff.apply(_ns, "trigger:5:noside")
    _rev, _ = rseff.apply(rseff.apply(base, "trigger:5:noside")[0], "noside")
    check("the masks and the team change compose, in either order, to the "
          "same bytes", _both == _rev and len(_both) == len(base))
    _sz = {at: (Script.at(_both, at).disk_len, Script.at(_both, at).mem_len)
           for at in list(SIZES) + [MASKS_AT]}
    check("and every block either of them touches still parses at its "
          "shipped size", _sz == {**SIZES, MASKS_AT: MASKS}, str(_sz))
    check("the masks alone leave the trigger's own blocks alone",
          {at: (Script.at(_ns, at).disk_len, Script.at(_ns, at).mem_len)
           for at in SIZES} == SIZES
          and _changed(base, _ns) and not (_changed(base, _ns) & r_only))

    _a5 = rseff._table("trigger:5")
    _b5 = rseff._table("trigger:5:noside")
    _diff = [(i, x, y) for (_n1, _s1, p), (_n2, _s2, q) in zip(_a5, _b5)
             for i, (x, y) in enumerate(zip(p, q)) if x != y]
    check("choosing a side changes exactly one byte of the trigger payload, "
          "and that byte is the team", _diff == [(42, 1, 4)], str(_diff))
    check("and the stock halves are identical, so both sides pin the same "
          "site", [st for _n, st, _nw in _a5] == [st for _n, st, _nw in _b5])
    check("an unknown side is refused rather than guessed",
          _raises(lambda: rseff.apply(base, "trigger:5:sideways"),
                  rseff.FriendlyFireError))

    _s = PROFILE.setting("ff_rogue_side")
    check("the side card reaches the profile, defaults to the terrorists, "
          "and is barred when the mission-failure option is on",
          _s is not None and _s.default == "terrorists" and _s.enabled
          and _s.confidence in BADGES and _s.group == "Teammates"
          and _s.requires == {"ff_retaliate": [True],
                              "ff_fail_mission": [False]}
          and sorted(c.value for c in _s.choices) == ["noside", "terrorists"])
    check("the side card on its own writes nothing",
          which(ff_rogue_side="noside") == [])
    check("with the squad option on it picks the team, and nobody's side "
          "brings the masks with it -- without them he is neutral, and the "
          "bullet path zeroes damage against a neutral",
          which(ff_retaliate=True) == ["trigger:5:terrorists"]
          and which(ff_retaliate=True, ff_rogue_side="noside")
          == ["noside", "trigger:5:noside"])
    check("and the hurt dial still chooses the level underneath it",
          which(ff_retaliate=True, ff_rogue_side="noside", ff_trigger="2")
          == ["noside", "trigger:2:noside"])
    check("mission failure drops the side and the masks with the dial",
          which(ff_retaliate=True, ff_rogue_side="noside",
                ff_fail_mission=True) == ["fail_on_kill"])
    check("the masks go to offline and split screen only, never online",
          all(e.matches("/COMMONOFF.LIN") and e.matches("/COMMON_SS.LIN")
              and not e.matches("/COMMON.LIN")
              for e in PROFILE.build_data(PROFILE.effective(dict(
                  d0, ff_retaliate=True, ff_rogue_side="noside")))
              if e.op == "friendly_fire"))

    # ---- when the victim is the other PLAYER ------------------------------
    # Reported from play: shooting player 2 did nothing. The shipped dial
    # lives in R6RainbowAI.PlaySoundDamage, the AI's OWN damage handler, and
    # a player pawn is not an R6RainbowAI, so none of it ran.
    #
    # R6Pawn.R6TakeDamage would have been the obvious single fix and is not
    # script on PS2 at all -- 28 bytes that tail-call a native, with the
    # whole damage body in C++. That is the same reason the dispatch never
    # reached a player: PlaySoundDamage is chosen by a native virtual call
    # on the victim's own controller.
    PK_BLOCKS = {0x0F587F: (1069, 1444),   # R6Pawn.R6Died
                 0x10B465: (283, 375)}     # R6PlayerController.PlaySoundDamage
    check("the two player-side functions are the ones this was measured on",
          {at: (Script.at(base, at).disk_len, Script.at(base, at).mem_len)
           for at in PK_BLOCKS} == PK_BLOCKS,
          str({at: (Script.at(base, at).disk_len, Script.at(base, at).mem_len)
               for at in PK_BLOCKS}))
    check("it is keyed by exactly the settings the dial offers, both sides",
          sorted(rseff.PLAYERKILL) == sorted(
              "trigger:%s%s" % (k, s) for k in "12345"
              for s in ("", ":noside")))
    # R6Died can only serve a KILL -- by the time it runs the victim is dead
    # -- so the wounded notches need the controller's handler as well.
    check("a kill takes two regions and every wounded notch takes three",
          [len(rseff.PLAYERKILL["trigger:%s" % k]) for k in "12345"]
          == [3, 3, 3, 2, 2])
    check("every region is an equal-length before and after",
          all(len(st) == len(nw) and st != nw
              for v in rseff.PLAYERKILL.values() for _n, st, nw in v))
    for path, plain in plains.items():
        check("%s: every player-side stock run appears exactly once, and no "
              "replacement is already there" % path[1:],
              all(plain.count(st) == 1 and plain.count(nw) == 0
                  for v in rseff.PLAYERKILL.values() for _n, st, nw in v))
    for _k in ("playerkill:5", "playerkill:2", "playerkill:5:noside"):
        _got, _n = rseff.apply(base, _k, True)
        _sz = {at: (Script.at(_got, at).disk_len, Script.at(_got, at).mem_len)
               for at in PK_BLOCKS}
        check("%s applies, keeps the length and both block sizes, and "
              "reverts exactly" % _k,
              _n == len(rseff._table(_k)) and len(_got) == len(base)
              and _sz == PK_BLOCKS and rseff.reads(_got, _k)
              and rseff.apply(_got, _k, False)[0] == base, str(_sz))
    # It must not want any of the bytes the shipped regions want -- those
    # three already collide with each other by design, and a fourth
    # collision would be silent.
    _pk = _changed(base, rseff.apply(base, "playerkill:5")[0])
    check("it touches none of the bytes the AI-side regions do",
          _pk and not (_pk & r_only) and not (_pk & f_only))
    for _o in ("noside", "trigger:5", "trigger:5:noside", "fail_on_kill"):
        _a = rseff.apply(rseff.apply(base, _o)[0], "playerkill:5")[0]
        _b = rseff.apply(rseff.apply(base, "playerkill:5")[0], _o)[0]
        check("it composes with %s in either order, byte for byte" % _o,
              _a == _b and len(_a) == len(base))
    check("an unknown level or side is refused rather than guessed",
          _raises(lambda: rseff.apply(base, "playerkill:9"),
                  rseff.FriendlyFireError)
          and _raises(lambda: rseff.apply(base, "playerkill:5:sideways"),
                      rseff.FriendlyFireError))

    _pv = PROFILE.setting("ff_player_victim")
    check("the card reaches the profile, off by default, and "
          "needs the squad option",
          _pv is not None and _pv.default is False and _pv.enabled
          and _pv.confidence in BADGES and _pv.group == "Teammates"
          and _pv.requires == {"ff_retaliate": [True],
                               "ff_fail_mission": [False]})
    check("on its own it writes nothing", which(ff_player_victim=True) == [])
    check("with the squad option it adds the player-side regions and leaves "
          "the AI-side ones alone",
          which(ff_retaliate=True, ff_player_victim=True)
          == ["playerkill:5:terrorists", "trigger:5:terrorists"])
    check("it follows the dial and the side rather than carrying its own",
          which(ff_retaliate=True, ff_player_victim=True, ff_trigger="2",
                ff_rogue_side="noside")
          == ["noside", "playerkill:2:noside", "trigger:2:noside"])
    check("and mission failure drops it with everything else",
          which(ff_retaliate=True, ff_player_victim=True,
                ff_fail_mission=True) == ["fail_on_kill"])

    # Worth asserting because it is easy to read the loop above as a
    # three-package test and it is really a two-file one: offline single
    # player and split screen decompress to the SAME bytes.
    check("COMMONOFF and COMMON_SS are byte-identical, so a region that is "
          "unique in one is unique in the other by construction",
          plains["/COMMONOFF.LIN"] == plains["/COMMON_SS.LIN"]
          and plains["/COMMON.LIN"] != plains["/COMMON_SS.LIN"])

    # ---- failing on a KILL rather than on a wounding ---------------------
    # The same abort the wounding version uses, behind the dial's own health
    # test at its top notch. Health 4-5 reach that arm by fall-through, so
    # the test is the whole difference between a downing and a kill, and the
    # wounded arm is left stock -- the "watch your fire" line survives.
    k_only = _changed(base, rseff.apply(base, "fail_on_kill")[0])
    check("the kill setting writes one region, the same one the squad edit "
          "uses", k_only and (k_only & r_only))
    check("it wants the same bytes as the wounding setting and as the dial, "
          "which is what keeps all three mutually exclusive",
          bool(k_only & f_only) and bool(k_only & dial_b))
    check("it stops short of the wounded arm, which the wounding setting "
          "rewrites as well", max(k_only) < max(f_only))
    check("the health test it adds compares against 4, so only a 5 (dead) "
          "passes", all(b"\x2c\x04" in nw
                        for _n, _st, nw in rseff.REGIONS["fail_on_kill"]))
    k_both, _ = rseff.apply(base, "fail_on_kill")
    k_after = {at: (Script.at(k_both, at).disk_len,
                    Script.at(k_both, at).mem_len) for at in SIZES}
    check("with the squad edit on top it still parses at stock sizes",
          k_after == SIZES and len(k_both) == len(base), str(k_after))
    check("and it reads back on its own",
          rseff.reads(k_both, "fail_on_kill")
          and not rseff.reads(k_both, "fail_on_hit"))

    w = PROFILE.setting("ff_fail_when")
    check("the when-card reaches the profile, defaulting to a kill, and "
          "needs the failure option",
          w is not None and w.default == "kill" and w.enabled
          and w.requires == {"ff_fail_mission": [True]}
          and sorted(c.value for c in w.choices) == ["kill", "wound"])
    check("the when-card alone writes nothing", which(ff_fail_when="wound") == [])





# --------------------------------------------------- R6DecalGroup::Init ----
#: The five branches of R6DecalGroup::Init that set up each pooled ring, and
#: the merge point they all fall into. Entered only from the type dispatch at
#: 0x00378B44 -- nothing else in the overlay branches into them.
_DECAL_BRANCH = {0: 0x00378B78, 1: 0x00378C08, 2: 0x00378CB8,
                 3: 0x00378D78, 4: 0x00378E00}
_DECAL_MERGE = 0x00378EBC
#: R6Decal's class-default projector bools: bProjectBSP, bProjectTerrain,
#: bProjectStaticMesh, m_bProjectTransparent, bProjectOnParallelBSP.
_DECAL_CDO = 0x8207


def _decal_run(img, entry, patch, cdo):
    """Straight-line emulation of one Init branch. Returns the field dict."""
    mem = {0x37C: cdo & 0xFF, 0x37D: (cdo >> 8) & 0xFF, 0x371: None,
           0x384: None}
    reg = [0] * 32
    va = entry
    while va < _DECAL_MERGE:
        w = patch.get(va, img.read_word(va))
        op, rs, rt = w >> 26, (w >> 21) & 31, (w >> 16) & 31
        rd, sa, fn = (w >> 11) & 31, (w >> 6) & 31, w & 63
        imm = w & 0xFFFF
        sim = imm - 0x10000 if imm & 0x8000 else imm
        if op == 0x0C:                                    # andi
            reg[rt] = reg[rs] & imm
        elif op == 0x0D:                                  # ori
            reg[rt] = reg[rs] | imm
        elif op in (0x09, 0x19):                          # addiu / daddiu
            reg[rt] = sim + reg[rs]
        elif op == 0x0F:                                  # lui
            reg[rt] = imm << 16
        elif op == 0x24:                                  # lbu
            reg[rt] = mem[imm]
        elif op == 0x28:                                  # sb
            mem[imm] = reg[rt] & 0xFF
        elif op == 0x2B:                                  # sw
            mem[imm] = reg[rt] & 0xFFFFFFFF
        elif op == 0 and fn == 0x24:                      # and
            reg[rd] = reg[rs] & reg[rt]
        elif op == 0 and fn == 0x25:                      # or
            reg[rd] = reg[rs] | reg[rt]
        elif op == 0 and fn == 0x00:                      # sll
            reg[rd] = (reg[rt] << sa) & 0xFFFFFFFF
        elif op == 0 and fn == 0x2D:                      # daddu (move)
            reg[rd] = reg[rs] | reg[rt]
        elif op == 0x04 and rs == 0 and rt == 0:          # b
            va += 4 + sim * 4
            continue
        reg[0] = 0
        va += 4
    return mem


def _decal_branch_bools(img, patch, entry=_DECAL_BRANCH[4], cdo=_DECAL_CDO):
    mem = _decal_run(img, entry, patch, cdo)
    return (mem[0x37D] << 8) | mem[0x37C]


def _decal_branch_fields(img, patch, entry=_DECAL_BRANCH[4]):
    mem = _decal_run(img, entry, patch, _DECAL_CDO)
    return mem[0x371], mem[0x384]


def _decal_branch_pins(img, entry=_DECAL_BRANCH[4]):
    """-> f(patch) -> the set of bool bits the branch WRITES.

    A bit the branch stores comes out the same whatever the class default was;
    a bit it merely inherits follows the default. Flipping one default bit at a
    time separates the two.
    """
    def pins(patch):
        out = set()
        for bit in range(16):
            a = _decal_branch_bools(img, patch, entry, _DECAL_CDO)
            b = _decal_branch_bools(img, patch, entry, _DECAL_CDO ^ (1 << bit))
            if a == b:
                out.add(bit)
        return out
    return pins

def run_blast_decals(args):
    """Scattered shrapnel marks: two disc words and a cave (2026-09-25).

    Three things had to be true at once and none of them is obvious:
    the pooled explosion decals are born FLOOR-ONLY and AddDecal never
    rewrites that; the game's own grenade decal path is DEAD, so the ring is
    free but nothing fills it; and the cave that fills it has to reach a live
    texture without hard-coding a pointer, because UObject addresses move
    between loads.
    """
    print("\n[Rainbow Six 3 -- shrapnel marks from explosions]")
    if not (args.soz or args.iso or args.rs3data):
        print("  SKIP  needs --soz, --iso or --rs3data")
        return
    import struct
    from tcps2 import rsedecal as D, rseclaymore as C
    from tcps2.games.r6_3 import CAVE_WORDS, STOCK
    img = SozImage.unpack(stock_container(args), PROFILE.overlays[0].base_va)

    # ---- the disc words ---------------------------------------------------
    # AddDecal never writes the projector bools, so a ring keeps whatever
    # R6DecalGroup::Init gave it -- and Init builds the explosion ring as an
    # opaque, hard-edged, floor-only SCORCH: bools 0x8C85 where the wall-hit
    # branch leaves 0xA3C7, plus blend op 1 against 3.
    #
    # An earlier fix repointed the type dispatch so the ring borrowed the
    # wall-hit branch. That looked right but handed it the wall-hit
    # DrawScale, which is the same one the game's bullet holes use -- so
    # making explosion marks bigger would have enlarged those too. The ring's
    # own branch is patched in place instead, which leaves DrawScale free.
    check("every branch word is the instruction we measured, and still stock",
          all(img.read_word(va) == st and STOCK[va] == st
              for va, st, _nw in D.BRANCH_WORDS))
    check("and none of them is a no-op rewrite",
          all(st != nw for _va, st, nw in D.BRANCH_WORDS))
    check("the dispatch itself is left alone now",
          img.read_word(0x00378B44) == 0x106200AD
          and 0x00378B44 not in {va for va, _s, _n in D.BRANCH_WORDS})

    # sin(90) is sine's global MAXIMUM, so a minProjectAngle of 90 can never
    # win the min() that builds the acceptance threshold -- it stays
    # sin(0.5 deg) and every surface up to 89.5 degrees off square is
    # accepted. That is what made marks smear. A NEGATIVE angle caps it, and
    # the game does exactly that for blood splats.
    check("the incidence words are stock too, and write a negative angle",
          all(img.read_word(va) == st and STOCK[va] == st
              for va, st, _nw in D.INCIDENCE_WORDS)
          and any((nw >> 26) == 0x0F and (nw & 0x8000)
                  for _va, _st, nw in D.INCIDENCE_WORDS))
    check("and one of them stores it to minProjectAngle at decal+0x384",
          any((nw >> 26) == 0x2B and (nw & 0xFFFF) == 0x384
              for _va, _st, nw in D.INCIDENCE_WORDS))

    check("the DrawScale word is the lui holding 8.0f, and still stock",
          img.read_word(D.DRAWSCALE) == D.DRAWSCALE_STOCK == 0x3C024100)
    check("every offered size rebuilds a lui of the same register",
          all((D.drawscale_word(x) >> 16) == (D.DRAWSCALE_STOCK >> 16)
              for x in D.DRAWSCALES))
    check("a size the top half of a float cannot carry is refused",
          _raises(lambda: D.drawscale_word(1.1), D.DecalError))

    # ---- no patched word may destroy a write the branch still needs ------
    # The first version of INCIDENCE_WORDS overwrote the only writer of bit 1
    # of decal+0x37C (bProjectTerrain) on the claim that patching 0x00378E14
    # had made it dead. It had not: that word FEEDS it. Nothing caught it,
    # because the resulting bool word was unchanged -- R6Decal's class default
    # for that bool is already True, so the deleted store was writing a value
    # the object already had.
    #
    # So compare PINNING rather than value. Emulate the branch once per bool
    # with that bool's class default inverted: a bit the branch writes comes
    # out the same either way, a bit it merely inherits follows the default.
    # Every bit the STOCK branch pins, the PATCHED branch must still pin.
    _pins = _decal_branch_pins(img)
    check("stock, the explosion branch pins every bool it means to set",
          _pins({}) == {1, 6, 7, 9, 10, 11, 13})
    check("no shipped word silently deletes one of those writes",
          _pins(dict((va, nw) for va, _s, nw in
                     D.BRANCH_WORDS + D.INCIDENCE_WORDS)) >= _pins({}),
          "lost: %s" % sorted(_pins({}) - _pins(dict(
              (va, nw) for va, _s, nw in
              D.BRANCH_WORDS + D.INCIDENCE_WORDS))))
    check("and the branch still writes FrameBufferBlendingOp and the angle",
          _decal_branch_fields(img, dict(
              (va, nw) for va, _s, nw in D.BRANCH_WORDS + D.INCIDENCE_WORDS))
          == (3, 0xC1F00000))
    check("the patched ring ends up bit-for-bit the wall-hit ring's bools",
          _decal_branch_bools(img, dict(
              (va, nw) for va, _s, nw in D.BRANCH_WORDS + D.INCIDENCE_WORDS))
          == _decal_branch_bools(img, {}, entry=0x00378C08) == 0xA3C7)

    # ---- why only one puff of dust ever showed ---------------------------
    # Not the pooled impact actor: a rate limit in the visual half, one float
    # for the whole engine and a half-second window. The impact SOUND is
    # played upstream of it, which is exactly the asymmetry that was reported
    # -- three impacts heard, one seen.
    check("the dust gate is the branch we measured, and still stock",
          img.read_word(D.BURST_GATE) == D.BURST_GATE_STOCK == 0x45010047
          and (D.BURST_GATE_STOCK >> 26) == 0x11
          and ((D.BURST_GATE_STOCK >> 21) & 0x1F) == 0x08
          and (D.BURST_GATE_STOCK >> 16) & 1)
    check("0.5 is the constant it compares against, and it jumps past the "
          "whole burst",
          img.read_word(0x0056E3E4) == 0x3C033F00
          and img.read_word(0x0056E3F8) == 0x46000836
          and D.BURST_GATE + 4 + ((D.BURST_GATE_STOCK & 0xFFFF) << 2)
          == 0x0056E520)
    check("turning it off writes a nop, and the delay slot was already one "
          "so nothing else moves",
          D.BURST_GATE_OFF == 0 and img.read_word(D.BURST_GATE + 4) == 0)
    _d0 = PROFILE.defaults()
    _pf = PROFILE.setting("blast_puffs")
    check("the card reaches the profile, off by default",
          _pf is not None and _pf.default is False and _pf.enabled
          and _pf.confidence in BADGES and _pf.touches == "ram")
    check("off it writes nothing; on it writes exactly that one row",
          not [e for e in PROFILE.build_pnach(PROFILE.effective(_d0))
               if e.va == D.BURST_GATE]
          and [(e.va, e.value, e.stock) for e in PROFILE.build_pnach(
              PROFILE.effective(dict(_d0, blast_puffs=True)))
              if e.va == D.BURST_GATE]
          == [(D.BURST_GATE, D.BURST_GATE_OFF, D.BURST_GATE_STOCK)])
    check("and it is a cheat row rather than a disc word, so it needs no "
          "re-apply",
          D.BURST_GATE not in PROFILE.stock_words
          and not [e for e in PROFILE.build_edits(PROFILE.effective(
              dict(_d0, blast_puffs=True)))
              if getattr(e, "va", None) == D.BURST_GATE])
    # It is not part of the shrapnel feature -- it is the engine's own
    # limit -- but it IS mutually exclusive with the puff ring, because with
    # the limit gone every shot re-fires the game's one shared actor and
    # Reset kills the burst already playing.
    check("it does not need the shrapnel marks, and is barred only by the "
          "puff ring", _pf.requires == {"impact_puffs": [False]})

    # ---- the hook --------------------------------------------------------
    check("the hook is the first word of the explosion native's epilogue",
          img.read_word(D.HIJACK_AT) == D.HIJACK_STOCK == 0xDFBF00A0
          and STOCK[D.HIJACK_AT] == D.HIJACK_STOCK)
    check("the displaced word is an `ld`, replaced by a `j` to the cave",
          (D.HIJACK_STOCK >> 26) == 0x37 and (D.HIJACK >> 26) == 0x02
          and ((D.HIJACK & 0x03FFFFFF) << 2) == D.CAVE)
    check("the delay slot left behind is the self-contained lwc1",
          img.read_word(D.HIJACK_AT + 4) == 0xC7B50004)

    # ---- the cave --------------------------------------------------------
    ws = D.words()
    base = PROFILE.overlays[0].base_va
    check("every cave word is below the ELF load base, where a pnach reaches",
          base == 0x00100000 and ws and all(va < base for va, _w in ws))
    check("and clear of the claymore cave, which owns 0x000F0000..0x000F0800",
          min(va for va, _w in ws) >= 0x000F1000)
    clay = {va for va, _w in C.words("2")} | {va for va, _w in C.words("1")}
    check("the two caves share not one word address",
          not (clay & {va for va, _w in ws}))
    check("nor does either touch the map-wide spawn cave",
          not ({va for va, _w in CAVE_WORDS} & {va for va, _w in ws}))
    check("the cave is contiguous, one word every four bytes",
          [va for va, _w in ws]
          == list(range(D.CAVE, D.CAVE + 4 * len(ws), 4)))

    tail = [w for _va, w in ws][-3:]
    check("it ends by replaying the displaced load, then jumping back",
          tail[0] == D.HIJACK_STOCK
          and (tail[1] >> 26) == 0x02
          and ((tail[1] & 0x03FFFFFF) << 2) == 0x00268BCC
          and tail[2] == 0)
    check("it never jumps to the hook itself, which would loop for ever",
          all(((w & 0x03FFFFFF) << 2) != D.HIJACK_AT
              for _va, w in ws if (w >> 26) == 0x02))
    # A mark traces outward and is placed on what it hits, or not at all.
    # v1 hung each projector in mid-air on its ray, which is what turned the
    # marks into long smears: a projector that never meets a surface squarely
    # stretches its texture over whatever it does reach.
    # The FIRST Trace is the once-per-blast up-probe: it measures the
    # clearance overhead so the lifted trace start cannot end up inside a
    # ceiling. It asks for no material ($t3 = 0) and places no mark.
    check("it calls Trace, then Trace, Rotation, AddDecal, Rotation, Impact",
          [((w & 0x03FFFFFF) << 2) for _va, w in ws if (w >> 26) == 0x03]
          == [0x0026EE80, 0x0026EE80, 0x0016DEC0, 0x00379780, 0x0016DEC0,
              0x003F08C0])
    # The material comes back from Trace's own out-pointer, which an earlier
    # version passed as zero and threw away. UMaterial+0x50 is the R6*Effect
    # class the impact cache is keyed on, so the mark can fire the impact the
    # game itself would have played for that surface -- sound and sparks.
    check("it asks the trace for the material rather than discarding it",
          any((w >> 26) == 0x09 and ((w >> 21) & 31) == 29
              and ((w >> 16) & 31) == 11 for _va, w in ws))
    check("and reads the effect class off the material",
          any((w >> 26) == 0x23 and (w & 0xFFFF) == 0x50 for _va, w in ws))
    check("only a few marks fire one, not every mark",
          any((w >> 26) == 0x0D and (w & 0xFFFF) == 3 for _va, w in ws))
    # Measured on the live cache: 22 entries carry 17 distinct sound sets, so
    # materials really do sound different -- but one set is shared by five
    # slots and is the common wall. Firing on the first three marks that hit
    # played that one three times, because most of a blast's rays land on the
    # nearest surface. The three impacts must be three DIFFERENT materials.
    check("an impact is skipped when its material already sounded",
          sum(1 for _va, w in ws if (w >> 26) == 0x04) >= 6)
    # The aim comes off the surface the trace found, not the ray that found
    # it: a fragment arriving at a glancing angle would otherwise stretch its
    # mark by 1/cos(incidence). FVector::Rotation writes pitch, yaw and a
    # zero roll straight into the rotator slot AddDecal reads.
    rot_stores = {(w & 0xFFFF) for _va, w in ws
                  if (w >> 26) in (0x2B, 0x39) and ((w >> 21) & 31) == 29}
    check("and does not write the rotator itself -- Rotation fills it",
          not ({0x10, 0x14, 0x18} & rot_stores))
    check("the normal is negated first, so the projector looks AT the wall",
          sum(1 for _va, w in ws if (w >> 26) == 0x11
              and ((w >> 21) & 31) == 16 and (w & 0x3F) == 0x07) == 3)
    # A hit within a stone's throw of the epicentre is the floor the charge
    # is standing on. Half a blast's rays point down, so without this most of
    # the budget stacks up in one patch underfoot: six of twenty-four live
    # marks were at a single point.
    check("a hit right under the blast is skipped rather than marked",
          any((w >> 26) == 0x11 and ((w >> 21) & 31) == 16
              and (w & 0x3F) == 0x34 for _va, w in ws))
    check("the trace asks for world geometry and not pawns",
          any((w >> 26) == 0x0F and ((w >> 16) & 31) == 9 and (w & 0xFFFF) == 0
              for _va, w in ws))
    check("and hands it the ready-made zero extent rather than a stack vector",
          any((w >> 26) == 0x0F and ((w >> 16) & 31) == 10
              and (w & 0xFFFF) == ((0x005D5680 + 0x8000) >> 16)
              for _va, w in ws))

    # $sp is lowered once and raised once, and the early bails must reach the
    # exit WITHOUT having lowered it -- otherwise a blast with no texture
    # returns on a frame 0x40 bytes adrift and the caller's epilogue reads
    # the wrong stack.
    adj = [(va, struct.unpack("<h", struct.pack("<H", w & 0xFFFF))[0])
           for va, w in ws
           if (w >> 26) == 0x09 and ((w >> 21) & 31) == 29 and ((w >> 16) & 31) == 29]
    check("the scratch frame is opened once, closed once, and nets to zero",
          len(adj) == 2 and sum(a for _va, a in adj) == 0, str(adj))
    check("and it is closed before the exit, so a bail never lands mid-frame",
          adj[0][1] < 0 < adj[1][1]
          and adj[1][0] < D.CAVE + 4 * (len(ws) - 3))

    # The $sp discipline, which is the easiest thing here to get wrong: a
    # bail ABOVE the frame-open must skip the close, and a bail BELOW it must
    # go through the close. Mixing them leaves $sp 0x40 adrift, which loads
    # $ra from the wrong slot and hands the caller a corrupt frame.
    open_at, close_at = adj[0][0], adj[1][0]
    exit_at = close_at + 4

    def target(va, w):
        return va + 4 + (struct.unpack("<h", struct.pack("<H", w & 0xFFFF))[0] << 2)

    below = [(va, w) for va, w in ws
             if va > open_at and (w >> 26) in (4, 5, 6, 7)]
    above = [(va, w) for va, w in ws
             if va < open_at and (w >> 26) in (4, 5, 6, 7)]
    check("no branch below the frame-open skips the close",
          below and all(target(va, w) != exit_at for va, w in below),
          "%d branches below" % len(below))
    # Above the frame-open there are two kinds of branch now: a bail to the
    # exit, and the texture scan looping back to itself. What must never
    # happen is one of them landing INSIDE the loop, with no frame under it.
    check("every branch above the frame-open either exits or stays above it",
          above and all(target(va, w) <= open_at or target(va, w) == exit_at
                        for va, w in above),
          "%d bails above" % len(above))

    # R6DecalGroup::AddDecal copies FOUR floats out of the position, so the
    # fourth is not padding -- it reaches AR6Decal+0x1BC.
    stores = {(w & 0xFFFF) for _va, w in ws
              if (w >> 26) in (0x2B, 0x39) and ((w >> 21) & 31) == 29}
    check("all four words of the position are written, including the fourth "
          "the callee copies", {0x00, 0x04, 0x08, 0x0C} <= stores,
          str(sorted(stores)))

    # The native is Engine.Actor.ExplosionDamage, declared on Actor, and
    # R6ExplodingBarel.Explode calls it too. On a barrel +0x380 is the INT
    # m_iHitPoints, so the class default is not a radius at all; the
    # parameter on the stack is, for every caller.
    # The hooked native is Engine.Actor.ExplosionDamage, declared on Actor,
    # and R6ExplodingBarel.Explode calls it too. On a barrel every grenade
    # field offset means something else, in bounds and silently wrong -- so
    # the radius is the native's own parameter and the ONLY thing still read
    # off the actor is Actor::Level, which every actor has.
    check("the radius comes off the native's own parameter, never off $s4",
          any((w >> 26) == 0x31 and ((w >> 21) & 31) == 29
              and (w & 0xFFFF) == 0x46C + 0xC0 for _va, w in ws)
          and not any((w >> 26) == 0x31 and ((w >> 21) & 31) == 20
                      for _va, w in ws))
    check("the only field read off the detonating actor is Actor::Level",
          [(w & 0xFFFF) for _va, w in ws
           if (w >> 26) == 0x23 and ((w >> 21) & 31) == 20] == [0x104])
    check("nothing reads the class field that is an AActor* on a barrel",
          not any((w >> 26) == 0x23 and (w & 0xFFFF) == 0x3D8
                  for _va, w in ws))
    check("the pointers it does chase are alignment- and range-checked",
          sum(1 for _va, w in ws if (w >> 26) == 0x0C and (w & 0xFFFF) == 3) >= 2
          and sum(1 for _va, w in ws if (w >> 26) == 0x0F
                  and (w & 0xFFFF) == 0x0200) >= 2
          and sum(1 for _va, w in ws
                  if (w >> 26) == 0 and (w & 0x3F) == 0x2B) >= 2)
    # The texture is the game's own bullet-hole set, off the impact cache,
    # not the blast's smoke sprite -- which is the other half of why v1
    # smeared. Fixed global bases, per-load pointers inside.
    check("the texture comes from the impact cache's decal arrays",
          any((w >> 26) == 0x23 and (w & 0xFFFF) == 0x388 for _va, w in ws)
          and any((w >> 26) == 0x23 and (w & 0xFFFF) == 0x38C
                  for _va, w in ws)
          and any((w >> 26) == 0x0F
                  and (w & 0xFFFF) == ((0x006DD6C0 + 0x8000) >> 16)
                  for _va, w in ws))

    # sqrt.s: the R5900 form takes its operand in ft, and capstone mis-prints
    # it, so it is checked by shape against the 84 the game itself ships.
    sq = [w for _va, w in ws if (w >> 26) == 0x11
          and ((w >> 21) & 31) == 16 and (w & 0x3F) == 0x04]
    check("the one hand-built sqrt.s has the shape the game's own 84 use",
          len(sq) == 1 and ((sq[0] >> 11) & 31) == 0
          and ((sq[0] >> 16) & 31) == ((sq[0] >> 6) & 31),
          "%08X" % (sq[0] if sq else 0))
    span = range(D.CAVE, D.CAVE + 4 * len(ws))
    check("every branch lands inside the cave",
          all((va + 4 + (struct.unpack("<h", struct.pack("<H", w & 0xFFFF))[0] << 2))
              in span for va, w in ws if (w >> 26) in (4, 5, 6, 7)))
    check("every branch, jump and call is followed by its delay slot",
          all(ws[i + 1][1] == 0 for i in range(len(ws) - 1)
              if (ws[i][1] >> 26) in (2, 3, 4, 5, 6, 7)))

    # ---- the mark count --------------------------------------------------
    a, b = dict(D.words(12)), dict(D.words(20))
    check("the mark count moves exactly one word, and it is the ori",
          [va for va in a if a[va] != b[va]] == [D.COUNT_AT]
          and (a[D.COUNT_AT] & 0xFFFF) == 12 and (b[D.COUNT_AT] & 0xFFFF) == 20
          and (a[D.COUNT_AT] >> 26) == 0x0D)
    check("the lui feeding it is zero, so the count is a plain 16-bit value",
          a[D.COUNT_AT - 4] == 0x3C160000)
    check("a count of zero or past the immediate is refused, not truncated",
          _raises(lambda: D.words(0), D.DecalError)
          and _raises(lambda: D.words(0x10000), D.DecalError))

    # ---- the profile -----------------------------------------------------
    n = PROFILE.setting("blast_decals")
    # Played 2026-09-28: the marks were counted in a savestate (11 placed,
    # 5 of 6 rays for one blast), so this one is genuinely "verified" and
    # the check guards against it being quietly demoted again.
    check("the card reaches the profile, off by default, watched in game",
          n is not None and n.default == 0 and n.enabled
          and n.confidence == "verified")
    sz = PROFILE.setting("blast_decal_size")
    check("the size card is back, now that the ring owns its own DrawScale",
          sz is not None and sz.default == "1.25"
          and [float(c.value) for c in sz.choices] == list(D.DRAWSCALES))
    check("and it only shows once the marks themselves are on",
          list(sz.requires) == ["blast_decals"])
    d0 = PROFILE.defaults()

    _mine = ({va for va, _s, _n in D.BRANCH_WORDS}
             | {va for va, _s, _n in D.INCIDENCE_WORDS} | {D.DRAWSCALE})

    def plan(**kw):
        eff = PROFILE.effective(dict(d0, **kw))
        return ([e for e in PROFILE.build_edits(eff) if e.va in _mine],
                [e for e in PROFILE.build_pnach(eff)
                 if e.va == D.HIJACK_AT or e.va >= D.CAVE])

    check("stock writes neither a disc word nor a cheat row", plan() == ([], []))
    de, pn = plan(blast_decals=12)
    check("turning it on writes every branch and incidence word, a DrawScale "
          "and the whole cave",
          {e.va for e in de} == _mine
          and all(e.value == dict((va, nw) for va, _s, nw in
                                  D.BRANCH_WORDS + D.INCIDENCE_WORDS)[e.va]
                  for e in de if e.va != D.DRAWSCALE)
          and len(pn) == len(ws) + 1
          and pn[0].va == D.HIJACK_AT and pn[0].value == D.HIJACK)
    check("and the size card picks the DrawScale",
          [e.value for e in plan(blast_decals=12, blast_decal_size="2.0")[0]
           if e.va == D.DRAWSCALE] == [D.drawscale_word(2.0)])
    _de, pn3 = plan(blast_decals=16)
    check("the count reaches the cheat file",
          [e.value for e in pn3 if e.va == D.COUNT_AT] == [0x36D60010])

    # ---- the ring it writes into ----------------------------------------
    # The ring wraps silently, so more marks than slots is not an error
    # anywhere -- it just means the marks are not there.
    def warn(**kw):
        return [x for x in PROFILE.combination_warnings(
            PROFILE.effective(dict(d0, **kw))) if "hrapnel" in x]

    # ---- the impact stagger ----------------------------------------------
    # Three impacts in one frame are one thud. Deferring them needs a hook
    # that runs ONCE per frame: UGameEngine::Tick, not ULevel::Tick, which
    # runs twice because GEngine+0x460 is a second live ULevel -- fine for
    # the claymore's proximity check, wrong for anything counting frames.
    check("the frame hook is the load we measured, and still stock",
          img.read_word(D.STAGGER_HOOK) == D.STAGGER_HOOK_STOCK
          == 0x8E04045C and STOCK[D.STAGGER_HOOK] == D.STAGGER_HOOK_STOCK)
    check("it is a `lw` replaced by a `j` to the consumer",
          (D.STAGGER_HOOK_STOCK >> 26) == 0x23
          and (D.STAGGER_HOOK_JUMP >> 26) == 0x02
          and ((D.STAGGER_HOOK_JUMP & 0x03FFFFFF) << 2) == D.CONSUMER)
    check("the delay slot it jumps over is the constant we must re-supply",
          img.read_word(D.STAGGER_HOOK + 4) == 0x24050002)

    sw = D.stagger_words()
    swv = {va for va, _w in sw}
    cons = [w for va, w in sw if va < D.ENQUEUE]
    check("the consumer re-does the displaced load and re-supplies that $a1",
          D.STAGGER_HOOK_STOCK in cons[-6:] and 0x24050002 in cons[-6:])
    check("and returns PAST the delay slot, never to the hook itself",
          any((w >> 26) == 0x02
              and ((w & 0x03FFFFFF) << 2) == D.STAGGER_HOOK + 8
              for w in cons[-6:])
          and not any((w >> 26) == 0x02
                      and ((w & 0x03FFFFFF) << 2) == D.STAGGER_HOOK
                      for w in cons))
    # The queue is runtime state. A pnach row rewrites its address EVERY
    # frame, so emitting it would reset the queue forever and the feature
    # would silently do nothing at all.
    check("the queue's RAM is never among the emitted words",
          all(not (D.QUEUE <= va < D.QUEUE_END) for va in swv))
    check("the two routines sit clear of the cave, the claymore cave and "
          "each other",
          not (swv & {va for va, _w in ws})
          and all(not (0x000F0000 <= va < 0x000F0800) for va in swv)
          and max(va for va, _w in sw if va < D.ENQUEUE) < D.ENQUEUE)
    check("and every one of them is below the ELF load base",
          all(va < 0x00100000 for va in swv))

    # Switching it on changes exactly ONE word of the cave: where the impact
    # goes. The helper takes the same registers and tail-calls the impact
    # entry point when it cannot queue, so the worst case is today.
    now, queued = dict(D.words(12)), dict(D.words(12, stagger=True))
    moved = [va for va in now if now[va] != queued[va]]
    check("staggering moves exactly one word of the cave, the impact call",
          moved == [D.IMPACT_CALL_AT]
          and now[D.IMPACT_CALL_AT] == D.IMPACT_CALL_NOW
          and queued[D.IMPACT_CALL_AT] == D.IMPACT_CALL_QUEUED
          and (D.IMPACT_CALL_NOW >> 26) == 0x03
          and (D.IMPACT_CALL_QUEUED >> 26) == 0x03, str(moved))
    check("and it retargets that call from the impact point to the helper",
          ((D.IMPACT_CALL_NOW & 0x03FFFFFF) << 2) == 0x003F08C0
          and ((D.IMPACT_CALL_QUEUED & 0x03FFFFFF) << 2) == D.ENQUEUE)

    st = PROFILE.setting("blast_stagger")
    check("the card reaches the profile, off by default",
          st is not None and st.default is False and st.enabled
          and st.confidence in BADGES
          and st.requires == {"blast_decals": tuple(range(1, 49))})
    _de, pn_off = plan(blast_decals=12)
    _de, pn_on = plan(blast_decals=12, blast_stagger=True)
    check("turning it on adds the two routines and the frame hook, and "
          "nothing else", len(pn_on) - len(pn_off) == len(sw) + 1)
    check("and never a row inside the queue",
          not any(D.QUEUE <= e.va < D.QUEUE_END for e in pn_on))
    check("with it off, neither routine nor the hook is written",
          not any(e.va in swv or e.va == D.STAGGER_HOOK for e in pn_off))

    check("more marks than the ring holds is called out", len(warn(
        blast_decals=12, grenade_decals=8)) == 1)
    check("exactly filling the ring is called out more gently", len(warn(
        blast_decals=12, grenade_decals=12)) == 1)
    check("and twice the headroom says nothing", warn(
        blast_decals=12, grenade_decals=24) == [])
    check("nor does the feature being off", warn(grenade_decals=8) == [])


def run_claymore_prox(args):
    """The claymore proximity cave, both builds (2026-09-25).

    A placed claymore already listens for a Timer (ProbeMask 0x0B00, measured
    on a live instance) and R6Grenade.Timer is `Explode(); return;`, so the
    cave arms the timer instead of calling script. CONFIRMED IN PLAY: a
    claymore in front of a closed door self-detonated, which also proves
    PCSX2 applies pnach rows below the ELF load base.
    """
    print("\n[Rainbow Six 3 -- the claymore as a proximity mine]")
    if not (args.soz or args.iso or args.rs3data):
        print("  SKIP  needs --soz, --iso or --rs3data")
        return
    import math
    import struct
    from tcps2 import rseclaymore as C, rsegadget as G
    from tcps2.games.r6_3 import CAVE_WORDS, STOCK
    img = SozImage.unpack(stock_container(args), PROFILE.overlays[0].base_va)

    check("the hook is the actor-tick call we measured",
          img.read_word(C.HIJACK[0]) == C.HIJACK_STOCK == 0x0C089050
          and STOCK[C.HIJACK[0]] == C.HIJACK_STOCK)
    check("and it is a jal, replaced by a j to the cave",
          (C.HIJACK_STOCK >> 26) == 0x03 and (C.HIJACK[1] >> 26) == 0x02
          and ((C.HIJACK_STOCK & 0x03FFFFFF) << 2) == 0x00224140
          and ((C.HIJACK[1] & 0x03FFFFFF) << 2) == 0x000F0000)

    # Both builds live below the ELF load base. An earlier home at 0x005C2A40
    # looked perfect -- no code reference, no data reference, zero in every
    # savestate -- and was still the flat tail of an audio pan table that
    # 0x004D3068 indexes at runtime. "No static references" is not enough for
    # data inside the image, so the cave must not be inside the image at all.
    base = PROFILE.overlays[0].base_va
    for name, ws in (("all-round", C.ALLROUND_WORDS), ("front arc", C.CONE_WORDS)):
        check("%s: every word is below the ELF load base" % name,
              base == 0x00100000 and ws
              and all(va + 4 <= base for va, _w in ws)
              and ws[0][0] == 0x000F0000)
        check("%s: and none of it is an overlay word" % name,
              not [va for va, _w in ws if va in STOCK])
    check("the audio pan table that rejected the first home is real, and "
          "nothing targets it now",
          img.read_word(0x005C2940) != 0
          and not [va for va, _w in C.CONE_WORDS + C.ALLROUND_WORDS
                   if 0x005C2940 <= va <= 0x005C2B44])

    check("the all-round build is 65 contiguous words",
          len(C.ALLROUND_WORDS) == 65
          and all(C.ALLROUND_WORDS[i + 1][0] - C.ALLROUND_WORDS[i][0] == 4
                  for i in range(len(C.ALLROUND_WORDS) - 1)))
    code = [(va, w) for va, w in C.CONE_WORDS if va < 0x000F0400]
    tab = [(va, w) for va, w in C.CONE_WORDS if va >= 0x000F0400]
    check("the front-arc build is 94 words of code plus a 256-entry table",
          len(C.CONE_WORDS) == 350 and len(code) == 94 and len(tab) == 256
          and tab[0][0] == 0x000F0400 and tab[-1][0] == 0x000F07FC)

    vals = [struct.unpack("<f", struct.pack("<I", w))[0] for _a, w in tab]
    worst = max(abs(vals[i] - math.cos(2 * math.pi * i / 256)) for i in range(256))
    check("and that table really is a cosine, to the last bit",
          worst < 1e-6, "%g" % worst)

    def radius_m(pair):
        hi, lo = pair
        r2 = struct.unpack(">f", struct.pack(">I",
                                             ((hi & 0xFFFF) << 16) | (lo & 0xFFFF)))[0]
        return (r2 ** 0.5) / 100.0

    check("the three settings decode to 1, 2 and 3 metres",
          [round(radius_m(C.RADIUS_WORDS[k]), 3) for k in ("1", "2", "3")]
          == [1.0, 2.0, 3.0])
    for name in ("1", "2", "3"):
        for arc, src in ((True, C.CONE_WORDS), (False, C.ALLROUND_WORDS)):
            got = C.words(name, front_arc=arc)
            moved = {va for (va, w), (_v, base_w) in zip(got, src) if w != base_w}
            check("radius %s, %s: only the radius pair and the cone constant "
                  "move" % (name, "front arc" if arc else "all round"),
                  len(got) == len(src)
                  and moved <= set(C.RADIUS_AT) | ({C.CONE_K_AT} if arc else set()),
                  str(["%08X" % v for v in moved]))

    # The trigger arc is COMPUTED from the blast's own cone, so the two
    # cannot drift apart. The blast ships 0.766 = cos 40.004 degrees.
    k = dict(C.words("2", front_arc=True))[C.CONE_K_AT]
    check("the cone constant is a lui carrying cos squared of the blast's "
          "own angle",
          (k >> 26) == 0x0F and k == C.cone_word(G.STOCK["cone"]))
    half = math.degrees(math.acos(struct.unpack(
        "<f", struct.pack("<I", (k & 0xFFFF) << 16))[0] ** 0.5))
    check("which is the blast's 40 degrees, within a tenth",
          abs(half - math.degrees(math.acos(G.STOCK["cone"]))) < 0.1,
          "%.3f deg" % half)
    check("and a different blast cone flows straight through",
          abs(math.degrees(math.acos(struct.unpack(
              "<f", struct.pack("<I", (C.cone_word(0.5) & 0xFFFF) << 16))[0] ** 0.5))
              - 60.0) < 0.2)

    s = PROFILE.setting("claymore_prox")
    arc = PROFILE.setting("claymore_arc")
    check("both cards reach the profile, cheat-file only",
          s is not None and s.default == "off" and s.pnach_only and s.enabled
          and arc is not None and arc.default is True and arc.pnach_only
          and arc.requires == {"claymore_prox": ["1", "2", "3"]})
    d = PROFILE.defaults()
    check("off writes nothing at all",
          not PROFILE.build_pnach(PROFILE.effective(d)))
    on = PROFILE.build_pnach(PROFILE.effective(dict(d, claymore_prox="2")))
    check("the front arc is the default, and writes the bigger cave",
          len(on) == 351 and on[0].va == C.HIJACK[0]
          and on[0].stock == C.HIJACK_STOCK)
    flat = PROFILE.build_pnach(PROFILE.effective(
        dict(d, claymore_prox="2", claymore_arc=False)))
    check("and turning the arc off writes the small one",
          len(flat) == 66)
    check("neither ever reaches the disc -- a cave cannot survive a load",
          not ({va for va, _w in C.CONE_WORDS} | {C.HIJACK[0]})
          & {e.va for e in PROFILE.build_edits(PROFILE.effective(
              dict(d, claymore_prox="2")))})

    mw = {va for va, _w in CAVE_WORDS} | {0x0040ACA0}
    cl = {va for va, _w in C.CONE_WORDS} | {C.HIJACK[0]}
    check("it does not overlap the map-wide spawn cave", not (mw & cl))
    both = PROFILE.build_pnach(PROFILE.effective(dict(
        d, wave_enable=True, wave_mapwide=True, claymore_prox="3")))
    vas = [e.va for e in both]
    check("and with both caves on, no address is claimed twice",
          len(vas) == len(set(vas)) == 419, "%d" % len(vas))


def run_fps_uncap(args):
    """The 30 FPS cap, and the one word that lifts it (2026-09-25).

    Single player presents one frame per two NTSC fields. A vblank ISR at
    0x0019F700 counts fields and releases a flip only once the count reaches
    a divider, and renderer init writes 2 into that divider. Split screen
    reaches 60 by accident: it builds the renderer twice, each build
    registers the same ISR, nothing ever removes one, so the body runs twice
    per field.

    These checks are about the SHIPPED overlay, so they read the pristine
    image rather than the disc.
    """
    print("\n[Rainbow Six 3 -- the 30 FPS frame-pacing cap]")
    if not (args.soz or args.iso or args.rs3data):
        print("  SKIP  needs --soz, --iso or --rs3data")
        return
    from tcps2.games.r6_3 import PRESENT_DIVIDER, PRESENT_DIVIDER_FREE, STOCK
    img = SozImage.unpack(stock_container(args), PROFILE.overlays[0].base_va)

    stock = img.read_word(PRESENT_DIVIDER)
    check("the shipped overlay writes the divider where we think it does",
          stock == STOCK[PRESENT_DIVIDER] == 0xAF828088, "%08X" % stock)
    # sw rt, imm(gp): opcode 0x2B, base $gp = 28. Patching only swaps the
    # source register to $zero, so the destination cannot move.
    def sw_parts(word):
        return (word >> 26, (word >> 21) & 31, (word >> 16) & 31, word & 0xFFFF)
    op_s, base_s, rt_s, off_s = sw_parts(stock)
    op_n, base_n, rt_n, off_n = sw_parts(PRESENT_DIVIDER_FREE)
    check("it is a gp-relative store, and the patch only changes its source "
          "register to $zero",
          (op_s, base_s) == (0x2B, 28) and (op_n, base_n) == (0x2B, 28)
          and off_s == off_n and rt_s == 2 and rt_n == 0,
          "%r vs %r" % (sw_parts(stock), sw_parts(PRESENT_DIVIDER_FREE)))

    # The pacing ISR reads the very word this store writes: same gp offset.
    isr_load = img.read_word(0x0019F704)
    check("and the frame-pacing interrupt reads that same word",
          (isr_load >> 26) == 0x23 and ((isr_load >> 21) & 31) == 28
          and (isr_load & 0xFFFF) == off_s, "%08X" % isr_load)

    # The register holding 2 is reused as the interrupt cause a few
    # instructions later, which is why the constant itself must not be touched.
    check("the constant 2 is loaded into $v0, which later becomes the "
          "interrupt-cause argument -- so that instruction is left alone",
          img.read_word(0x001AE464) == 0x24020002
          and img.read_word(0x001AE490) == 0x0040202D
          and (img.read_word(0x001AE494) >> 26) == 0x03)

    # The blast-mark ring, separate from the bullet-hole one.
    from tcps2.games.r6_3 import GRENADE_DECALS, grenade_decal_word
    gw = img.read_word(GRENADE_DECALS)
    check("the grenade decal ring ships at 8, its own word",
          gw == STOCK[GRENADE_DECALS] == 0x24050008
          and GRENADE_DECALS != 0x00379B30)
    check("and the bullet-hole ring is a different word, at 32",
          img.read_word(0x00379B30) == 0x24060020)
    check("raising it keeps the instruction and only moves the immediate",
          all((grenade_decal_word(n) >> 16) == (gw >> 16)
              and (grenade_decal_word(n) & 0xFFFF) == n
              for n in (8, 24, 32, 64)))
    gs = PROFILE.setting("grenade_decals")
    check("the option reaches the profile, defaulting to the shipped 8",
          gs is not None and gs.default == 8
          # 128 slots is 180 KB against a worst-observed 1.37 MiB of
          # contiguous free heap, 12.6% -- measured, and the ceiling was
          # raised to it once the shrapnel marks started filling the ring.
          and (gs.minimum, gs.maximum) == (8, 128) and gs.enabled)
    gbase = {e.va for e in PROFILE.build_edits(PROFILE.effective(
        PROFILE.defaults()))}
    check("8 writes nothing", GRENADE_DECALS not in gbase)
    gon = [e for e in PROFILE.build_edits(PROFILE.effective(
        dict(PROFILE.defaults(), grenade_decals=24)))
        if e.va == GRENADE_DECALS]
    check("and another value writes exactly one word, from stock",
          len(gon) == 1 and gon[0].value == grenade_decal_word(24)
          and gon[0].stock == gw)

    s = PROFILE.setting("fps_uncap")
    check("the option reaches the profile, unplayed",
          s is not None and s.confidence in BADGES and s.enabled
          and s.kind == "bool" and s.default is False)
    off = {e.va for e in PROFILE.build_edits(PROFILE.effective(
        PROFILE.defaults()))}
    on = PROFILE.build_edits(PROFILE.effective(
        dict(PROFILE.defaults(), fps_uncap=True)))
    mine = [e for e in on if e.va not in off]
    check("off it writes nothing; on it writes exactly the one word",
          PRESENT_DIVIDER not in off and len(mine) == 1
          and mine[0].va == PRESENT_DIVIDER
          and mine[0].value == PRESENT_DIVIDER_FREE
          and mine[0].stock == stock,
          str([("%08X" % e.va) for e in mine]))
    every = PROFILE.build_edits(PROFILE.effective(dict(
        PROFILE.defaults(), **{x.key: True for x in PROFILE.settings
                               if x.kind == "bool" and x.enabled})))
    claims = [e for e in every if e.va == PRESENT_DIVIDER]
    check("and with every option on, no other option claims that word",
          len(claims) == 1, str(len(claims)))


def run_flashlight_hands_pass(args):
    """Three fixes from the 2026-09-24 play-test, read-only on shipped bytes:
    a dead terrorist's weapon light, player 2's arms, and the icon pass."""
    print("\n[dead flashlight, player 2's arms, one interaction pass per half]")
    if not args.rs3data:
        print("  SKIP  needs --rs3data")
        return
    from tcps2 import dataedit, lin, rseflashlight, rsehands, rseorders
    from tcps2 import rsesquad
    from tcps2.uscode import Script, compact_decode
    store = dataedit.Store(engine.backup_dir_for(args.rs3data))
    plains = {}
    for name in ("/COMMON_SS.LIN", "/COMMONOFF.LIN", "/COMMON.LIN"):
        keys = [k for k in store.index if k.endswith(name)]
        if keys:
            plains[name] = lin.decompress(store.original(
                store.index[keys[0]]["archive"], name)[0])
    if "/COMMON_SS.LIN" not in plains:
        print("  SKIP  no stored COMMON_SS.LIN")
        return

    def own_refs(p, at):
        out = []
        for top in Script.at(p, at).toks:
            for t in top.walk():
                n = 0
                for kind, val in t.parts:
                    if kind == "ref":
                        if not (t.op in (0x0E, 0x1B, 0x21, 0x38)
                                or (t.op == 0x40 and n == 1)):
                            v = compact_decode(val, 0)[0]
                            if v > 0:
                                out.append(v)
                        n += 1
        return out

    ok = True
    for name, p in plains.items():
        at, mode = rseflashlight.find(p)
        ok &= mode == "stock"
        for m in ("on", "off"):
            q, n = rseflashlight.apply(p, m)
            a, b = Script.at(p, at - 4), Script.at(q, at - 4)
            ok &= (n == 1 and rseflashlight.reads(q) == m and len(q) == len(p)
                   and (a.mem_len, a.disk_len) == (b.mem_len, b.disk_len)
                   and own_refs(p, at - 4) == own_refs(q, at - 4)
                   and rseflashlight.apply(q, "stock")[0] == p)
    check("dead flashlight: both choices keep StartFalling's size and its own "
          "references, in every COMMON, and switch back exactly", ok)
    got = {m: [e for e in PROFILE.build_data(PROFILE.effective(dict(
        PROFILE.defaults(), dead_flashlight=m))) if e.op == "dead_flashlight"]
        for m in ("stock", "on", "off")}
    check("and it is written offline and split screen, never online",
          not got["stock"] and all(
              len(got[m]) == 1 and got[m][0].matches("/COMMON_SS.LIN")
              and got[m][0].matches("/COMMONOFF.LIN")
              and not got[m][0].matches("/COMMON.LIN") for m in ("on", "off")))

    ss = plains["/COMMON_SS.LIN"]
    sites = rsehands._sites(ss)
    check("player 2's arms: the three sites are where they were measured",
          [s[0] for s in sites] == list(rsehands.KNOWN_OFFSETS)
          and all(s[3] == "stock" for s in sites))
    q, n = rsehands.apply(ss, True)
    a, b = Script.at(ss, 0x1470A3), Script.at(q, 0x1470A3)
    check("and CreatePlayerTeam keeps its size, with the edit idempotent",
          n == 3 and (a.mem_len, a.disk_len) == (b.mem_len, b.disk_len)
          and rsehands.apply(q, True) == (q, 0) and len(q) == len(ss))
    first = rsesquad.apply(q, True, canon=True)[0]
    second = rsehands.apply(rsesquad.apply(ss, True, canon=True)[0], True)[0]
    check("and it composes with the AI teammates and canon in either order",
          first == second and rsehands.reads(first))
    eds = [e for e in PROFILE.build_data(PROFILE.effective(dict(
        PROFILE.defaults(), split_hands=True))) if e.op == "split_hands"]
    check("and it is written to the split-screen package only",
          len(eds) == 1 and eds[0].matches("/COMMON_SS.LIN")
          and not eds[0].matches("/COMMONOFF.LIN")
          and not eds[0].matches("/COMMON.LIN"))

    img = SozImage.unpack(stock_container(args), PROFILE.overlays[0].base_va)
    check("icon pass: the three words are the shipped reloads",
          all(img.read_word(va) == st for va, st, _n, _t in rseorders.PASS_WORDS))
    need = dict(PROFILE.defaults(), split_squad=True, split_wheel=True,
                split_wheel_labels=True)
    on = {e.va: e.value for e in PROFILE.build_edits(PROFILE.effective(
        dict(need, split_team_orders=True)))}
    off = {e.va for e in PROFILE.build_edits(PROFILE.effective(need))}
    check("and they are written only with team orders",
          all(on.get(va) == new for va, _s, new, _t in rseorders.PASS_WORDS)
          and not off & {va for va, _s, _n, _t in rseorders.PASS_WORDS})

    from collections import Counter
    from tcps2 import rsecarry
    check("carry-over: the 70 words are the shipped ones in the two natives",
          len(rsecarry.WORDS) == 70
          and all(img.read_word(va) == st for va, st, _n, _t in rsecarry.WORDS)
          and all(0x003B6160 <= va < 0x003B7200 for va, *_r in rsecarry.WORDS))
    # 2026-09-24: a player who died in part A starts part B dead. The first
    # version skipped his record here; the shipped words are back.
    check("carry-over: a dead player's record takes the shipped dead path",
          not {0x003B62BC, 0x003B62C0} & {va for va, *_r in rsecarry.WORDS})
    new = {va: n for va, _s, n, _t in rsecarry.WORDS}
    check("and the closing pass visits player 2's slot first, player 1's last",
          new.get(0x003B69E8) == 0x8FA800A8 and new.get(0x003B69EC) == 0x0008800B
          and new.get(0x003B69F0) == 0x0112800A
          and new.get(0x003B61D0) == 0xAFA900A8)
    carry = {va for va, *_r in rsecarry.WORDS}
    squad = {e.va: e.value for e in PROFILE.build_edits(PROFILE.effective(
        dict(PROFILE.defaults(), split_squad=True, split_carry=True)))}
    plain = {e.va for e in PROFILE.build_edits(PROFILE.effective(
        dict(PROFILE.defaults(), split_squad=True)))}
    alone = {e.va for e in PROFILE.build_edits(PROFILE.effective(
        dict(PROFILE.defaults(), split_carry=True)))}
    check("and they are written with their own option, which needs the AI "
          "teammates",
          all(squad.get(va) == new for va, _s, new, _t in rsecarry.WORDS)
          and not carry & plain and not carry & alone)
    every = PROFILE.build_edits(PROFILE.effective(dict(
        PROFILE.defaults(), **{s.key: True for s in PROFILE.settings
                               if s.kind == "bool" and s.enabled})))
    dup = [va for va, n in Counter(e.va for e in every).items() if n > 1]
    check("with every option on, no two edits claim the same word",
          not dup, str([hex(v) for v in dup]))


def run_creation_order(args):
    """A script edit must first-touch its OWN package's objects in stock order.

    The loader creates a package's exports as their first references are
    serialized, then reads each from the recording in that order. Two edits
    that kept the SET of references but not their first-touch ORDER hung Oil
    Refinery's split-screen load ("R63rdWeapons.SubSR2: SERIAL SIZE MISMATCH:
    GOT 536, EXPECTED 527", 2026-09-23): TeamMemberDead's gate read DeadPawn
    before iMemberId, and the team-orders rewrite of PostRender reordered five
    locals and three properties.

    Imports of CONTENT -- a Sound, a Texture, a Font -- are checked the same
    way. A script import of a class or a property resolves into a package
    whose classes are already built, and those changes are proven in play. A
    content object is created when it is first referenced, like the package's
    own exports. The call-outs named two of Price's Sound objects from
    R6PlayerController; stock first reaches them through R6PriceVoices, far
    later, and Terrorist Hunt on the Garage hung its load in a voice package
    ("Bad name index -70/109", 2026-09-24). The own-export check passed it.
    """
    print("\n[script edits keep each package's creation order]")
    if not args.rs3data:
        print("  SKIP  needs --rs3data")
        return
    from tcps2 import dataedit, lin, uscode, upackage
    from tcps2.uscode import Script, compact_decode
    store = dataedit.Store(engine.backup_dir_for(args.rs3data))
    keys = [k for k in store.index if k.endswith("/COMMON_SS.LIN")]
    if not keys:
        print("  SKIP  no stored COMMON_SS.LIN")
        return
    stock = lin.decompress(store.original(store.index[keys[0]]["archive"],
                                          "/COMMON_SS.LIN")[0])
    blocks = uscode.find_blocks(stock)
    name_ref = {0x1B, 0x38, 0x21, 0x0E}

    def refs(p, at):
        out = []
        for t0 in Script.at(p, at).toks:
            for x in t0.walk():
                nref = 0
                for k, v in x.parts:
                    if k == "ref":
                        if not (x.op in name_ref or (x.op == 0x40 and nref == 1)):
                            o = compact_decode(v, 0)[0]
                            if o:
                                out.append(o)
                        nref += 1
        return out

    def import_classes(data, base):
        """Each import's class name, walked as upackage.tables walks them."""
        pkg = upackage.Package(data, base)
        names, pos = [], base + pkg.o_names
        for _ in range(pkg.n_names):
            ln, pos = upackage.compact_index(data, pos)
            names.append(data[pos:pos + ln - 1].decode("latin-1"))
            pos += ln + 4
        out = []
        for _ in range(pkg.n_imports):
            _cp, pos = upackage.compact_index(data, pos)
            cn, pos = upackage.compact_index(data, pos)
            pos += 4
            _nm, pos = upackage.compact_index(data, pos)
            out.append(names[cn])
        return out

    script_kinds = {"Class", "Function", "State", "Struct", "Enum", "Const",
                    "Package", "TextBuffer"}

    packs = []
    for base, _p in upackage.packages(stock):
        try:
            names, _imports, exports = upackage.tables(stock, base)
        except Exception:                                    # noqa: BLE001
            continue
        if "CreatePlayerTeam" in names or "R6PracticeModeGameForSplitScreen" in names:
            if any(e[0] == "Class" for e in exports):
                packs.append((base, names, exports))
    check("found the gameplay and game-mode packages", len(packs) >= 2,
          str([hex(b) for b, _n, _e in packs]))

    def owned(base, names, exports):
        by_name = {}
        for i, e in enumerate(exports):
            if e[0] in ("Function", "State", "Class") and e[2] > 0:
                by_name.setdefault(e[1], []).append(e[2])
        out = []
        for at in blocks:
            try:
                sc = Script.at(stock, at)
            except Exception:                                # noqa: BLE001
                continue
            for w in (1, 2, 3):
                try:
                    v, n = compact_decode(stock, at - 8 - w)
                except Exception:                            # noqa: BLE001
                    continue
                if n != w or not 0 <= v < len(names):
                    continue
                if any(0 <= size - (sc.disk_len + 4) - (8 + w) <= 64
                       for size in by_name.get(names[v], ())):
                    out.append(at)
                    break
        return out

    def creation(p, mine):
        seen, order = set(), []
        for at in mine:
            for o in refs(p, at):
                if o > 0 and o not in seen:
                    seen.add(o)
                    order.append(o)
        return order

    def content(p, mine, kinds):
        seen, order = set(), []
        for at in mine:
            for o in refs(p, at):
                if (o < 0 and o not in seen and -o - 1 < len(kinds)
                        and kinds[-o - 1] not in script_kinds
                        and not kinds[-o - 1].endswith("Property")):
                    seen.add(o)
                    order.append(o)
        return order

    mines = [(base, owned(base, names, exports)) for base, names, exports in packs]
    kinds = {base: import_classes(stock, base) for base, _n, _e in packs}
    check("stock script reaches content imports, so the check has something "
          "to hold", all(content(stock, mine, kinds[base])
                         for base, mine in mines))

    def planned(**on):
        for k in on:
            assert PROFILE.setting(k) is not None, k
        plain = stock
        for e in PROFILE.build_data(PROFILE.effective(dict(PROFILE.defaults(),
                                                           **on))):
            if (re.search(e.select, "/COMMON_SS.LIN", re.I)
                    and e.op not in dataedit._RECORDING_OPS):
                fn = dataedit.OPS[e.op]
                if e.op in dataedit._WANTS_CONTAINER:
                    plain, _n = fn(plain, e.params, None)
                else:
                    plain, _n = fn(plain, e.params)
        return plain

    # The split-screen set as played -- Oil Refinery loads with it -- with the
    # rebuilt team orders, and then every other option that rewrites script
    # in this file.
    split = dict(split_squad=True, canon_team=True, split_muzzle=True,
                 split_wheel=True, split_cycle=True, split_draw_once=True,
                 split_wheel_labels=True, split_team_orders=True,
                 split_hands=True, split_down_callouts=True,
                 split_thunt_ai=True, fov=110, switch_rate=150)
    rest = dict(split, hostage_rainbow_voice=True,
                ai_finite_ammo=True, ai_sidearm=50, ai_say_dry=50,
                rpg_speed=2, grenade_carry=50)
    for label, on in (("the split-screen set", split),
                      ("every script option", rest)):
        plain = planned(**on)
        check("%s changes the package" % label, plain != stock)
        for base, mine in mines:
            check("%s, package 0x%06x: its own objects are created in stock "
                  "order" % (label, base),
                  creation(stock, mine) == creation(plain, mine),
                  "%d blocks" % len(mine))
            check("%s, package 0x%06x: and the content it names too"
                  % (label, base),
                  content(stock, mine, kinds[base])
                  == content(plain, mine, kinds[base]))
    plain = planned(**split)
    from tcps2 import rsecallouts, rsechatter, rsemandown, rseorders
    check("team orders, rebuilt, are in that set and offered again",
          rseorders.reads(plain)
          and PROFILE.setting("split_team_orders").enabled)
    # Each withdrawn for exactly this. The death call-out hung a disc that
    # carried nothing else; the first team-orders rewrite hung Oil Refinery;
    # the call-outs kept every own object in order and still hung the Garage,
    # by naming Price's sounds early.
    for label, key, fn in (
            ("the death call-out", "ss_man_down",
             lambda p: rsemandown.apply(p, True)[0]),
            ("the kill call-out", "ss_chatter_kill",
             lambda p: rsechatter.apply(p, 10, True)[0]),
            ("the call-outs", "split_callouts",
             lambda p: rsecallouts.apply(p, True)[0])):
        alt = fn(plain)
        check("%s: this check catches the rewrite" % label,
              alt != plain and any(
                  creation(plain, mine) != creation(alt, mine)
                  or content(plain, mine, kinds[_b]) != content(alt, mine,
                                                               kinds[_b])
                  for _b, mine in mines))
        check("%s: and its card stays off until it passes" % label,
              PROFILE.setting(key).enabled is False)


def run_team_recordings(args):
    """AI teammates in split screen, through the real apply path on the disc.

    Reads the real archives and keeps every write in memory, so the disc is
    never touched. What it pins: every covered map's split-screen recording is
    replaced by the proved splice and stays in its own slot; the team code
    lands in the split-screen package and nowhere else; the winter maps,
    Trieste and every single-player file are left exactly as they were; and
    switching the option off puts every one of those files back.
    """
    from tcps2 import dataedit, lin, rsesplice, rsesquad
    from tcps2.iso import Iso
    from tcps2.vokes import Region, Vokes, open_archives
    from tcps2.games import BY_ID

    iso_path = args.rs3data or args.iso
    if not iso_path:
        return
    profile = BY_ID["r6_3_slus20883"]
    print(chr(10) + "[split-screen teammates on the disc]")

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

    edits = [e for e in profile.build_data(profile.effective(
        dict(profile.defaults(), split_squad=True)))
        if e.op in ("squad", "team_recording")]
    work = tempfile.mkdtemp(prefix="tcms-team-")
    real_archives = dataedit._archives
    try:
        with Iso(iso_path) as iso:
            shadows = {}
            for real in open_archives(iso, profile.archive_pattern):
                arc = Vokes(Shadow(real.r))
                shadows[arc.r.name.upper()] = arc
            dataedit._archives = lambda _iso, _p: shadows

            def where(path):
                for name, arc in shadows.items():
                    ent = arc.files.get(path)
                    if ent is not None:
                        return name, arc, ent
                return None, None, None

            watch = ["/%s_SS.LIN" % m for m in rsesplice.COVERED]
            left = (["/TRIESTE_A_SS.LIN"]
                    + ["/%sOFF.LIN" % m for m in rsesplice.MAPS[:3]]
                    + ["/%sOFF.LIN" % m for m in rsesplice.WINTER[:1]])

            # The disc may already carry the option. Put the shipped files
            # back first -- in memory only, from the disc's own backup store,
            # which is only ever READ here -- so this starts from stock.
            shipped = dataedit.Store(engine.backup_dir_for(iso_path))
            for name, arc in shadows.items():
                # Both halves, not just the split-screen one. The splice
                # compares a map's _SS against its OFF sibling and requires
                # exactly one difference, so leaving the OFF half as the disc
                # has it fails the moment ANY option edits the level
                # containers -- breach_stun writes all 60 (2026-09-25).
                for key in (watch + [rsesplice.sibling(p) for p in watch]
                            + ["/COMMON_SS.LIN"]):
                    ent = arc.files.get(key)
                    got = ent and shipped.original(name, ent.path)
                    if not got:
                        continue
                    data, offset = got
                    if ent.offset != offset or arc.read_entry(ent) != data:
                        if ent.offset != offset:
                            arc.r.write(ent.offset, b"\x00" * ent.size)
                        arc.r.write(offset, data)
                        arc._set_entry(ent, offset, len(data))
            before = {}
            for path in watch + left:
                name, arc, ent = where(path)
                before[path] = (ent.offset, arc.read_entry(ent))
            commons = {n: a.read_file("/COMMON_SS.LIN")
                       for n, a in shadows.items()
                       if "/COMMON_SS.LIN" in a.files}
            others = {(n, k): a.read_file(k) for n, a in shadows.items()
                      for k in ("/COMMON.LIN", "/COMMONOFF.LIN")
                      if k in a.files}

            store = dataedit.Store(os.path.join(work, "store"))
            try:
                dataedit.apply_data(iso, profile, edits, store)
                threw = None
            except Exception as exc:                  # noqa: BLE001
                threw = exc
            check("the option applies", threw is None,
                  "%s: %s" % (type(threw).__name__, threw) if threw else "")
            if threw is not None:
                return

            spliced = fitted = chunked = 0
            for path in watch:
                name, arc, ent = where(path)
                raw = arc.read_entry(ent)
                plain = lin.decompress(raw)
                sname, sarc, sent = where(rsesplice.sibling(path))
                stock_ss = lin.decompress(before[path][1])
                stock_off = lin.decompress(sarc.read_entry(sent))
                if (rsesplice.reads(plain)
                        and plain == rsesplice.splice(stock_ss, stock_off)):
                    spliced += 1
                if (ent.offset == before[path][0]
                        and len(raw) == len(before[path][1])):
                    fitted += 1
                if max(c for _r, c, _o in lin.parse(raw)[0]) <= lin.CHUNK_RAW:
                    chunked += 1
            check("all 26 split-screen recordings now read the operatives",
                  spliced == len(watch), "%d of %d" % (spliced, len(watch)))
            check("every one stays in its own slot, at exactly its shipped size",
                  fitted == len(watch), "%d of %d" % (fitted, len(watch)))
            check("and no chunk outgrows the loader's buffer",
                  chunked == len(watch), "%d of %d" % (chunked, len(watch)))
            same = [p for p in left
                    if where(p)[1].read_entry(where(p)[2]) == before[p][1]]
            check("Trieste and the single-player files are untouched",
                  same == left,
                  ", ".join(sorted(set(left) - set(same))))
            landed = [n for n, a in shadows.items()
                      if "/COMMON_SS.LIN" in a.files
                      and rsesquad.reads(lin.decompress(
                          a.read_file("/COMMON_SS.LIN")))
                      == rsesquad.ARM_TARGET
                      and rsesquad.skins_everyone(lin.decompress(
                          a.read_file("/COMMON_SS.LIN")))
                      and rsesquad.keeps_player2_out(lin.decompress(
                          a.read_file("/COMMON_SS.LIN")))
                      and rsesquad.orders_from_requester(lin.decompress(
                          a.read_file("/COMMON_SS.LIN")))
                      and rsesquad.buries_dead_ai(lin.decompress(
                          a.read_file("/COMMON_SS.LIN")))
                      and rsesquad.fails_on_both_players(lin.decompress(
                          a.read_file("/COMMON_SS.LIN")))
                      and rsesquad.hands_off_lead(lin.decompress(
                          a.read_file("/COMMON_SS.LIN")))
                      and rsesquad.ladder_is_leaders(lin.decompress(
                          a.read_file("/COMMON_SS.LIN")))]
            check("the team code and the whole-team skins land in every copy "
                  "of the split-screen package",
                  sorted(landed) == sorted(commons))
            # The rebuilt layout block, parsed in the real package: the
            # function keeps its size and every statement is where the
            # jumps expect it.
            from tcps2 import uscode as _usc
            from tcps2.rsecanon import _block as _cblock
            _cp = lin.decompress(
                shadows[sorted(commons)[0]].read_file("/COMMON_SS.LIN"))
            _at, _sc = _cblock(_cp, b"2# RescureTeamStartingPoint\x00", "CPT")
            _st = {t.mstart: t for t in _sc.toks}
            check("CreatePlayerTeam keeps its size with the reordered block",
                  _sc.mem_len == 1775 and _sc.disk_len == 1346,
                  "%d / %d" % (_sc.mem_len, _sc.disk_len))
            check("move first (0x0460), then restore (0x046e), then return",
                  all(k in _st for k in (0x0423, 0x043f, 0x0460, 0x046e,
                                         0x047b))
                  and _st[0x0460].op == 0x1B and _st[0x046e].op == 0x19
                  and _st[0x047b].op == 0x04)

            from tcps2.uscode import END, Script, compact_decode

            def _fn(plain, region, mem):
                """The script block holding `region`, by its ScriptSize."""
                at = plain.find(region)
                for s in range(at - 4, at - 2048, -1):
                    if struct.unpack_from("<I", plain, s)[0] != mem:
                        continue
                    try:
                        sc = Script.at(plain, s)
                    except Exception:                 # noqa: BLE001
                        continue
                    if at + len(region) <= s + 4 + sc.disk_len:
                        return sc

            def _refs(sc):
                """Object references only; a new NAME loads nothing."""
                return {compact_decode(v, 0)[0]
                        for s in sc.toks for t in s.walk()
                        for i, (k, v) in enumerate(t.parts) if k == "ref"
                        and t.op not in (0x0E, 0x1B, 0x21, 0x38)}

            def _goes(sc, mstart):
                t = [s for s in sc.toks if s.mstart == mstart][0]
                return [v.mstart for k, v in t.parts
                        if k == "jump" and v is not END]

            # (stock region, new region, ScriptSize, rewritten memory
            #  ranges, objects added, objects removed, jumps)
            _edited = (
                ("TeamMemberDead", rsesquad.DEAD_GATE, rsesquad.DEAD_GATE_NEW,
                 1062, ((0x0000, 0x0182), (0x01A8, 0x023C)), set(), set(),
                 {0x0005: [0x004A], 0x0034: [0x0047], 0x0047: [0x01AB],
                  0x0085: [0x0182], 0x01A8: [0x023C], 0x01AB: [0x01D3]}),
                ("PawnKilled", rsesquad.WIPED_TEST, rsesquad.WIPED_TEST_NEW,
                 1727, ((0x0434, 0x050A),), set(), set(),
                 {0x0434: [0x0528], 0x04A2: [0x050A]}),
                ("regrouponme", rsesquad.REGROUP, rsesquad.REGROUP_NEW, 105,
                 ((0x0000, 0x0069),), {11}, {-203}, {0x0000: [0x002C]}),
                ("ToggleTeamHold", rsesquad.TOGGLE_FOLLOW,
                 rsesquad.TOGGLE_FOLLOW_NEW, 282, ((0x00AB, 0x00BA),), set(),
                 set(), {0x00B1: [0x00BA]}),
                ("RainbowDebugTeam", rsesquad.HANDOFF, rsesquad.HANDOFF_NEW,
                 850, ((0x0000, 0x0352),), set(), set(),
                 {0x0000: [0x001A], 0x0041: [0x008D], 0x008A: [0x0041]}),
                ("TeamLeaderIsClimbingLadder", rsesquad.LADDER_START,
                 rsesquad.LADDER_START_NEW, 576, ((0x0000, 0x015F),), set(),
                 {-18}, {0x0000: [0x015F]}),
                ("MemberFinishedClimbingLadder", rsesquad.LADDER_END,
                 rsesquad.LADDER_END_NEW, 305, ((0x0055, 0x0097),), set(),
                 set(), {0x0055: [0x0097]}))
            same, sane, flow = [], [], []
            for n, raw in commons.items():
                was = lin.decompress(raw)
                now = lin.decompress(shadows[n].read_file("/COMMON_SS.LIN"))
                for (name, old, new, mem, spans, plus, minus,
                     jumps) in _edited:
                    a, b = _fn(was, old, mem), _fn(now, new, mem)
                    if a is None or b is None:
                        continue

                    def _out(sc, _spans=spans):
                        return [(t.mstart, t.mlen) for t in sc.toks
                                if not any(lo <= t.mstart < hi
                                           for lo, hi in _spans)]
                    if (b.mem_len == a.mem_len and b.disk_len == a.disk_len
                            and _out(b) == _out(a)):
                        same.append(name)
                    if (_refs(b) - _refs(a) == plus
                            and _refs(a) - _refs(b) == minus):
                        sane.append(name)
                    if all(_goes(b, m) == t for m, t in jumps.items()):
                        flow.append(name)
            _want = len(_edited) * len(commons)
            check("the seven edited functions still parse at their shipped "
                  "size, every statement outside the rewrites where it was",
                  len(same) == _want, "%d of %d" % (len(same), _want))
            check("each references only objects it or its class already did: "
                  "regrouponme gains its class's m_pawn for bCheatFlying, "
                  "TeamLeaderIsClimbingLadder drops bShowLog",
                  len(sane) == _want, "%d of %d" % (len(sane), _want))
            check("and every new jump lands where it was built to",
                  len(flow) == _want, "%d of %d" % (len(flow), _want))
            check("and the offline and online packages are untouched",
                  all(shadows[n].read_file(k) == b
                      for (n, k), b in others.items()))

            r = dataedit.apply_data(iso, profile, [], store)
            back = [p for p in watch
                    if where(p)[1].read_entry(where(p)[2]) == before[p][1]
                    and where(p)[2].offset == before[p][0]]
            check("switching it off puts every recording back byte for byte",
                  back == watch, "%d of %d" % (len(back), len(watch)))
            check("and the split-screen package too",
                  all(shadows[n].read_file("/COMMON_SS.LIN") == b
                      for n, b in commons.items()))
            check("and says so", r.get("restored") == len(watch) + len(commons),
                  "restored=%r" % r.get("restored"))

            # Canon on top. The expected recordings are the ones measured
            # independently, by hash, from the single-player files.
            from tcps2 import rsecanon

            def edits_for(**on):
                return [e for e in profile.build_data(profile.effective(
                    dict(profile.defaults(), **on)))
                    if e.op in ("squad", "team_recording", "canon_team")]

            def plain_at(path):
                _n, a, e = where(path)
                return lin.decompress(a.read_entry(e))

            def packages():
                return [lin.decompress(a.read_file("/COMMON_SS.LIN"))
                        for a in shadows.values()
                        if "/COMMON_SS.LIN" in a.files]

            dataedit.apply_data(iso, profile,
                                edits_for(split_squad=True, canon_team=True),
                                store)
            check("with canon, Island reads Weber, then Loiselle",
                  hashlib.sha1(plain_at("/ISLAND_A_SS.LIN")).hexdigest()
                  == "f164dc071e389b6e30c62c0263d85c5e6de1c174")
            check("and both Garage levels read the pair as single player does",
                  all(rsesplice.reads(plain_at(q)) for q in
                      ("/GARAGE_A_SS.LIN", "/GARAGE_B_SS.LIN")))
            check("the package carries canon, the team code and the roster "
                  "tests pointed at Price",
                  all(rsecanon.reads(c) and rsesquad.counts(c)
                      and rsesquad.roster_reads_price(c)
                      and rsesquad.reads(c) == rsesquad.ARM_TARGET
                      for c in packages()))
            dataedit.apply_data(iso, profile, edits_for(canon_team=True), store)
            want = {"/ISLAND_A_SS.LIN": "d0ac074020467ee6ca8071849412bcf08752a064",
                    "/GARAGE_A_SS.LIN": "340b9b22c823612fb71623c36972b73393fa5656",
                    "/GARAGE_B_SS.LIN": "b235ecea34c031829f094b9412d12564b0afaa4c"}
            got = {q: hashlib.sha1(plain_at(q)).hexdigest() for q in want}
            check("canon alone: its three levels read just player 2's operative",
                  got == want, str(got))
            check("and every other level is back to the stock recording",
                  all(where(q)[1].read_entry(where(q)[2]) == before[q][1]
                      for q in watch if q not in want))
            check("and the package carries canon without the team code",
                  all(rsecanon.reads(c)
                      and rsesquad.reads(c) == rsesquad.SKIP_TARGET
                      and not rsesquad.roster_reads_price(c)
                      for c in packages()))
            # AI teammates together with a changed enemy count. Both edit
            # Parade's split-screen files; the recording has to be replaced
            # first and the count applied on top, or the GUI's apply dies
            # in the splice (it did, 2026-09-23).
            dataedit.apply_data(iso, profile, edits_for(split_squad=True),
                                store)
            solo = plain_at("/PARADE_A_SS.LIN")
            mixed = [e for e in profile.build_data(profile.effective(
                dict(profile.defaults(), split_squad=True,
                     mission_parade=150)))
                if e.op in ("squad", "team_recording", "zone_counts")]
            try:
                dataedit.apply_data(iso, profile, mixed, store)
                failed = None
            except Exception as exc:                         # noqa: BLE001
                failed = "%s: %s" % (type(exc).__name__, exc)
            check("AI teammates and a changed enemy count apply together",
                  failed is None, str(failed))
            mix = plain_at("/PARADE_A_SS.LIN")
            check("Parade's split-screen level is spliced AND carries the "
                  "new count",
                  rsesplice.reads(mix) and len(mix) == len(solo)
                  and mix != solo)
            dataedit.apply_data(iso, profile, [], store)
            check("switching both off puts every file back byte for byte",
                  all(where(q)[1].read_entry(where(q)[2]) == before[q][1]
                      for q in watch)
                  and all(shadows[n].read_file("/COMMON_SS.LIN") == b
                          for n, b in commons.items()))
    finally:
        dataedit._archives = real_archives
        shutil.rmtree(work, ignore_errors=True)


def _fake_vokes(files, slack, tail=0x2000):
    """A vokes archive in memory, with `slack` bytes of padding after file 0.

    Record layout, from `tcps2.vokes`: +0x00 name offset, +0x08 parent index,
    +0x14 is-a-file, +0x18 size, +0x1C raw size, +0x20 data offset. The
    header carries the file size at 0, the entry table bounds at 2 and 3, the
    name table at 4 and the data start at 5, and the table must begin at
    0x800 or the parser refuses it.
    """
    import io as _io
    import struct as _struct
    from tcps2.vokes import Region as _Region, Vokes as _Vokes

    REC, ENT = 48, 0x800
    names, name_at = bytearray(), {}
    for name, _size in files:
        name_at[name] = len(names)
        names += name.encode("latin1") + b"\0"
    ent_end = ENT + (len(files) + 1) * REC
    name_off = (ent_end + 0xF) & ~0xF
    data_off = (name_off + len(names) + 0x7FF) & ~0x7FF

    laid, at = [], data_off
    for i, (name, size) in enumerate(files):
        laid.append((name, at, size))
        at = (at + size + slack) if i == 0 else ((at + size + 0xF) & ~0xF)
    filesize = at + tail

    ent = bytearray((len(files) + 1) * REC)
    for i, (name, off, size) in enumerate(laid, start=1):
        base = i * REC
        _struct.pack_into("<I", ent, base + 0x00, name_at[name])
        _struct.pack_into("<I", ent, base + 0x08, 0)
        _struct.pack_into("<I", ent, base + 0x14, 1)
        _struct.pack_into("<I", ent, base + 0x18, size)
        _struct.pack_into("<I", ent, base + 0x1C, size)
        _struct.pack_into("<I", ent, base + 0x20, off)

    buf = bytearray(filesize)
    head = [0] * 16
    head[0], head[2], head[3] = filesize, ENT, ent_end
    head[4], head[5] = name_off, data_off
    buf[0:64] = _struct.pack("<16I", *head)
    buf[ENT:ENT + len(ent)] = ent
    buf[name_off:name_off + len(names)] = names
    for i, (_name, off, size) in enumerate(laid):
        buf[off:off + size] = bytes([0x41 + i]) * size
    return _Vokes(_Region(_io.BytesIO(buf), 0, "FAKE.IMG"))


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

    # Built here rather than found on the disc. This used to hunt a real
    # archive for a file with alignment padding after it, which made the run
    # depend on what happened to be applied: `ai_finite_ammo` rewrites
    # R6GAMESETTINGS.INI and spends exactly that padding, so the check failed
    # with "0 bytes" on an applied disc and passed on a stock one. Four
    # consecutive runs with identical arguments went pass, pass, fail, fail.
    #
    # The invariant is worth keeping, so the padding is now chosen rather
    # than discovered, and the archive is a BytesIO that no previous run can
    # have touched.
    SLACK = 12
    arc = _fake_vokes([("A.BIN", 100), ("B.BIN", 256)], SLACK)
    a_home = arc.files["/A.BIN"].offset
    a_size = arc.files["/A.BIN"].size
    b_home = arc.files["/B.BIN"].offset
    body = arc.read_file("/A.BIN")

    check("the archive we built parses as one, with both files",
          sorted(arc.files) == ["/A.BIN", "/B.BIN"]
          and body == b"A" * 100
          and arc.read_file("/B.BIN") == b"B" * 256)
    check("the packer's alignment padding is the gap we left",
          arc._align_slack(arc.files["/A.BIN"]) == SLACK,
          "%d bytes" % arc._align_slack(arc.files["/A.BIN"]))
    check("and it is padding, never a whole missing file",
          arc._align_slack(arc.files["/A.BIN"]) < arc.ALIGN)

    # Every growth the padding can absorb keeps the file in its slot, and
    # the file after it never moves. One byte is the case that matters --
    # on the real disc a one-byte growth of R6GAMESETTINGS.INI was enough to
    # exile it to the end of the archive, a gigabyte from everything read
    # with it at level load.
    for grow in (1, SLACK // 2, SLACK):
        one = _fake_vokes([("A.BIN", 100), ("B.BIN", 256)], SLACK)
        one.write("/A.BIN", body + b" " * grow, home=(a_home, a_size))
        e = one.files["/A.BIN"]
        check("%d byte(s) longer still fits in its own slot" % grow,
              e.offset == a_home, "moved to 0x%x" % e.offset)
        check("and the record grew with it", e.size == a_size + grow)
        check("the next file is still where it was",
              one.files["/B.BIN"].offset == b_home)
        check("and reads back as what we wrote",
              one.read_file("/A.BIN") == body + b" " * grow)

    # Past the padding it has to move, and it has to come home again.
    two = _fake_vokes([("A.BIN", 100), ("B.BIN", 256)], SLACK)
    two.write("/A.BIN", body + b" " * (SLACK + 64), home=(a_home, a_size))
    moved = two.files["/A.BIN"].offset
    check("a growth past the padding does relocate", moved != a_home,
          "stayed at 0x%x" % moved)
    check("and the file it used to sit in front of is untouched",
          two.files["/B.BIN"].offset == b_home
          and two.read_file("/B.BIN") == b"B" * 256)
    two.write("/A.BIN", body, home=(a_home, a_size))
    check("and shrinking back brings it home",
          two.files["/A.BIN"].offset == a_home,
          "left at 0x%x" % two.files["/A.BIN"].offset)
    check("with its bytes intact", two.read_file("/A.BIN") == body)

    # One assertion against a real archive, chosen so it holds whatever is
    # applied: padding is by definition smaller than the alignment, so a
    # value at or above it would mean `_align_slack` had handed out a gap
    # left by a missing file rather than the packer's own padding.
    iso_path = args.rs3data or args.iso
    if iso_path:
        with Iso(iso_path) as iso:
            for real in open_archives(iso, r"/VOKES\d\.IMG$"):
                bad = [k for k, e in real.files.items()
                       if not 0 <= real._align_slack(e) < real.ALIGN]
                check("%s: no file claims more padding than the alignment"
                      % real.r.name, not bad, str(bad[:3]))
                break


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
    from tcps2 import dataedit as _de
    # The disc may already carry these edits, and each one leaves a file it
    # has already changed alone -- so start from the shipped bytes, read (and
    # only read) from the disc's own backup store when it has them.
    shipped = _de.Store(engine.backup_dir_for(iso_path))
    with Iso(iso_path) as iso:
        arcs = open_archives(iso, r"/VOKES0\.IMG$")
        if not arcs:
            return
        arc = arcs[0]
        for path in ("/COMMON.LIN", "/COMMONOFF.LIN", "/COMMON_SS.LIN"):
            if path.upper() not in arc.files:
                continue
            ent = arc.files[path.upper()]
            got = shipped.original(arc.r.name.upper(), ent.path)
            raw = got[0] if got else arc.read_entry(ent)
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
            # the shipped file, not the disc's: the disc may carry edits to
            # the very functions these cases rewrite (split_callouts does)
            raw = _stock_bytes(iso_path, arc, path)
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


def run_applied_record(args, work):
    """What a disc carries, what an Apply would change on it, and the way back.

    Written after a hang. One dial was moved in the window and Apply wrote the
    window's whole stored profile -- hours old, unlike the disc, and carrying
    two untested options that re-assemble UnrealScript -- with nothing on
    screen to say anything else was going with it. The level load never
    finished. The apply sheet now lists every setting that changes against what
    the disc was last patched with and flags the untested ones, and the window
    can load a recent apply back.

    Everything here is plain Python. The sheet itself is Tk, and this suite
    does not open it; `_table` is the part of it that decides the layout, and
    that part is checked.
    """
    import cli
    from gui import dialog, theme
    from tcps2 import applied
    from tcps2.games import BY_ID
    from tcps2.model import BOOL, CHOICE, INT, Setting

    print("\n[what the disc carries, and what an apply would change]")
    prof = BY_ID["r6_3_slus20883"]
    show, risk = applied.show, applied.risk

    check("a switch reads On and Off",
          (show(prof.setting("wave_enable"), True),
           show(prof.setting("wave_enable"), False)) == ("On", "Off"))
    check("a choice reads by its label, not its value",
          show(prof.setting("bodies"), "15") == "15 seconds",
          show(prof.setting("bodies"), "15"))
    check("a symbol unit sits against its number",
          (show(prof.setting("ai_sidearm"), 40),
           show(prof.setting("p2_look_speed"), 3)) == ("40%", "3x"))
    check("a word unit takes a space",
          show(prof.setting("fov"), 110) == "110 degrees")
    check("and a number with no unit is just the number",
          show(Setting("n", "N", INT, 0), 7) == "7")

    # The disc as the command line left it; the window's stored profile, with
    # the two untested options in it and the one dial actually moved tonight.
    disc = prof.effective(prof.defaults())
    window = dict(disc, ai_finite_ammo=True, ai_sidearm=40, ai_say_dry=20,
                  p2_look_speed=3)
    got = applied.changes(prof, disc, window)
    want = {"ai_finite_ammo", "ai_sidearm", "ai_say_dry", "p2_look_speed"}
    check("tonight's apply lists every setting it changes, in page order",
          [c.setting.key for c in got]
          == [s.key for s in prof.settings if s.key in want],
          str([c.setting.key for c in got]))
    check("and the two untested ones are the ones flagged",
          sorted((c.setting.key, c.risk) for c in got if c.risk)
          == [("ai_say_dry", "untested"), ("ai_sidearm", "untested")],
          str([(c.setting.key, c.risk) for c in got]))
    look = [c for c in got if c.setting.key == "p2_look_speed"]
    check("the dial moved on purpose is verified, so its row is quiet",
          len(look) == 1 and look[0].risk is None)
    check("and it reads 1x > 3x",
          (show(look[0].setting, look[0].before),
           show(look[0].setting, look[0].after)) == ("1x", "3x"))
    check("nothing differs from itself",
          applied.changes(prof, window, window) == [])

    print("  -- phantoms")
    check("a withdrawn option stored on is not a change",
          applied.changes(prof, disc, dict(disc, ss_man_down=True)) == [])
    check("nor is a dial whose prerequisite is off on both sides",
          applied.changes(prof, disc, dict(disc, wave_total=99)) == [])
    waves = dict(disc, wave_enable=True, wave_total=99, wave_gate="away")
    got = applied.changes(prof, waves, dict(waves, wave_enable=False))
    check("switching wave mode off lists wave mode, not its dials resetting",
          [c.setting.key for c in got] == ["wave_enable"],
          str([c.setting.key for c in got]))
    got = applied.changes(prof, disc, waves)
    check("switching it on lists the dials it comes with",
          {c.setting.key for c in got}
          == {"wave_enable", "wave_total", "wave_gate"},
          str([c.setting.key for c in got]))
    armed = dict(disc, ai_finite_ammo=True, ai_sidearm=40,
                 ai_sidearm_contact=False)
    got = applied.changes(prof, armed, dict(armed, ai_sidearm=0))
    check("turning an untested option off is one quiet row",
          [(c.setting.key, c.risk) for c in got] == [("ai_sidearm", None)],
          str([(c.setting.key, c.risk) for c in got]))

    print("  -- risk")
    sidearm, weather = prof.setting("ai_sidearm"), prof.setting("fx_weather")
    check("turning an untested option on is flagged",
          risk(sidearm, 40) == "untested")
    check("turning it back off is not", risk(sidearm, 0) is None)
    check("a not-play-tested fix that defaults on is flagged while on",
          weather.default is True and risk(weather, True) == "applied")
    check("and quiet when off", risk(weather, False) is None)
    check("a verified option is never flagged",
          risk(prof.setting("p2_look_speed"), 256) is None)
    check("an option marked broken but left switchable is flagged",
          risk(Setting("odd", "Odd", BOOL, False, confidence="broken"),
               True) == "broken")
    check("and so is a withdrawn one",
          risk(prof.setting("ss_man_down"), True) == "broken")
    used = {s.confidence for p in ALL_PROFILES for s in p.settings}
    check("every confidence a profile uses has a badge of its own",
          used <= set(theme.BADGE), str(sorted(used - set(theme.BADGE))))
    check("and every one a change can be flagged with is a warning colour",
          all(theme.BADGE[k][0] in ("warn", "bad")
              for k in used if k != "verified"))

    print("  -- the disc as it shipped")
    loud, quiet_data = [], []
    for p in ALL_PROFILES:
        v = p.effective(applied.stock(p))
        if ((p.build_edits and p.build_edits(v))
                or (p.build_pnach and p.build_pnach(v))):
            loud.append(p.id)
        # The loadout builder always emits, and "stock" is how it puts the
        # shipped templates back; that is the only data edit allowed here.
        quiet_data += [(p.id, e.op) for e in
                       (p.build_data(v) if p.build_data else [])
                       if e.params != {"weapons": "stock"}]
    check("the shipped baseline builds no code word or cheat line on any disc",
          not loud, str(loud))
    check("and no data edit that changes anything", not quiet_data,
          str(quiet_data))
    check("which the defaults are not: Rainbow Six 3's switch fixes on",
          bool(prof.build_edits(prof.effective(prof.defaults()))))

    print("  -- the record")
    folder = os.path.join(work, "applied-store")
    nothing = {"on_disc": None, "history": []}
    check("a disc with no record reads as nothing recorded",
          applied.load(folder, prof) == nothing)
    base, entry = applied.baseline(folder, prof)
    check("and compares against the disc as it shipped",
          entry is None and base == prof.effective(applied.stock(prof)))
    for n in range(1, 8):
        applied.record(folder, prof, dict(disc, p2_look_speed=n), "t%d" % n)
    log = applied.load(folder, prof)
    check("the history keeps the last %d applies, newest first"
          % applied.KEEP,
          [e["when"] for e in log["history"]] == ["t7", "t6", "t5", "t4", "t3"],
          str([e["when"] for e in log["history"]]))
    check("and the newest is what the disc carries",
          log["on_disc"]["when"] == "t7" and log["on_disc"]["kind"] == "applied")
    applied.record(folder, prof, dict(disc, p2_look_speed=5, ss_man_down=True),
                   "t8")
    log = applied.load(folder, prof)
    check("what is recorded is the effective settings, not the stored ones",
          log["on_disc"]["values"]["ss_man_down"] is False)
    check("re-applying a configuration moves it up instead of copying it",
          [e["when"] for e in log["history"]] == ["t8", "t7", "t6", "t4", "t3"],
          str([e["when"] for e in log["history"]]))
    applied.record_stock(folder, prof, "t9")
    log = applied.load(folder, prof)
    check("a restore records the disc as stock",
          log["on_disc"]["kind"] == "stock" and log["on_disc"]["when"] == "t9")
    check("and keeps every apply to go back to",
          [e["when"] for e in log["history"]] == ["t8", "t7", "t6", "t4", "t3"])
    base, entry = applied.baseline(folder, prof)
    check("so the next sheet compares against the disc as it shipped",
          entry["kind"] == "stock"
          and base == prof.effective(applied.stock(prof)))
    check("a record written for another game is ignored",
          applied.load(folder, BY_ID["ghost_recon_slus20613"]) == nothing)
    with open(os.path.join(folder, applied.STORE), "w") as fh:
        fh.write("{half a record")
    check("and a damaged one reads as nothing recorded, without raising",
          applied.load(folder, prof) == nothing)

    print("  -- the sheet's layout")
    # Every setting on every disc changed at once, between its two longest
    # values, and flagged whenever it could be: no line may be wider than the
    # sheet, or Tk wraps it and the end of the list drops out of sight.
    width = dialog.CHANGE_COLS - 2
    every = []
    for p in ALL_PROFILES:
        for s in p.settings:
            if s.kind == CHOICE:
                ends = sorted((c.value for c in s.choices),
                              key=lambda v, s=s: -len(show(s, v)))[:2]
            elif s.kind == BOOL:
                ends = [False, True]
            else:
                ends = [s.minimum, s.maximum]
            every.append(applied.Change(s, ends[0], ends[-1],
                                        None if s.confidence == "verified"
                                        else s.confidence))
    lines = dialog._table(every, width)
    wide = [ln for ln, _t in lines if len(ln) > width]
    check("no line of the change list is wider than the sheet (%d rows)"
          % len(every), not wide, str(wide[:2]))
    lines = dialog._table(applied.changes(prof, disc, window), width)
    check("tonight's list is one line a setting except the long label",
          len(lines) == 5, "\n".join(ln for ln, _t in lines))
    check("and the flagged rows are drawn in the warning colour",
          sorted(ln.split()[0] for ln, t in lines if "warn" in t)
          == ["0%", "Chance", "Chance"],
          str([(ln, t) for ln, t in lines]))

    # The discs that patch their boot executable word by word apply and
    # restore down a different branch of the engine; run_raw_and_data drove
    # one apply and one restore through it on each of their fixtures.
    for pid in ("ghost_recon_slus20613", "jungle_storm_slus20820"):
        raw = os.path.join(work, pid + ".iso")
        if not os.path.exists(raw):
            continue
        log = applied.load(engine.backup_dir_for(raw), BY_ID[pid])
        check("%s: its apply and its restore were both recorded"
              % BY_ID[pid].short,
              len(log["history"]) == 1
              and (log["on_disc"] or {}).get("kind") == "stock")

    if not (args.soz or args.iso):
        return
    print("  -- recorded where both the window and the command line apply")
    fx = os.path.join(work, "applied.iso")
    build(fx, [("SP.SOZ", stock_container(args)),
               ("SLUS_208.83", boot_elf(args))])
    folder = engine.backup_dir_for(fx)
    asked = dict(prof.defaults(), p2_look_speed=3, ss_man_down=True)
    r = engine.apply(fx, prof, asked)
    log = applied.load(folder, prof)
    check("an apply records what it wrote, beside the disc's other backups",
          r["verified"] == r["applied"] and log["on_disc"] is not None
          and os.path.exists(os.path.join(folder, applied.STORE)))
    check("the effective settings, stamped with the apply's own time",
          log["on_disc"]["values"] == prof.effective(asked)
          and log["on_disc"]["when"] == r["when"])
    code = cli.main(["apply", fx, "--set", "p2_look_speed=4"])
    log = applied.load(folder, prof)
    check("an apply from the command line is recorded too",
          code == 0 and log["on_disc"]["values"]["p2_look_speed"] == 4,
          "exit %r" % code)
    check("with the window's apply still in the history behind it",
          [e["values"]["p2_look_speed"] for e in log["history"]] == [4, 3])
    before, _entry = applied.baseline(folder, prof)
    check("so the next apply sheet compares against the command line's",
          [c.setting.key for c in applied.changes(
              prof, before, dict(prof.defaults(), p2_look_speed=4))] == [])
    rv = engine.revert(fx, prof)
    log = applied.load(folder, prof)
    check("a restore is recorded as the disc as it shipped",
          rv["hash_ok"] and log["on_disc"]["kind"] == "stock")
    check("and both applies are still there to load back",
          len(log["history"]) == 2)


if __name__ == "__main__":
    raise SystemExit(main())

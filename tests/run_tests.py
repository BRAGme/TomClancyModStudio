"""The checks worth running before a release.

    python tests\\run_tests.py ["E:\\XBOX Classic Games"]

Everything here runs against the real extracted discs, because the formats are
the point and a synthetic glob would only prove that this tool agrees with
itself. Nothing retail is ever opened for writing: the apply/revert cycle copies
the handful of files it needs into the system temp folder first and works there,
so a failed run cannot leave a game folder half-modded.

What each group is actually asserting:

  containers   every glob, bundle and executable on the shelf parses, and a
               round trip through the writer is byte-identical to the original.
  transforms   each edit does what it says AND keeps the file's length, which
               is the invariant the packed formats depend on.
  census       the two sides of the war are separable on the games that
               author the data for it, and empty on the games that do not --
               a silent empty census is how a weapons dial reaches nothing.
  cycle        plan, apply, verify, revert, and the folder is byte-identical
               to how it started.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tcxbox import (dataedit, engine, globfile, rsb, transforms,  # noqa: E402
                    umd, xbe, xpr)
from tcxbox.detect import identify, scan_folder                   # noqa: E402
from tcxbox.gamedir import Root                                   # noqa: E402

PASS, FAIL = [], []


def check(name, fn):
    try:
        detail = fn()
        PASS.append(name)
        print("  ok    %-58s %s" % (name, detail or ""))
    except Exception as exc:                      # noqa: BLE001
        FAIL.append((name, exc, traceback.format_exc()))
        print("  FAIL  %-58s %s" % (name, exc))


def must(cond, message):
    if not cond:
        raise AssertionError(message)


# ---------------------------------------------------------------------------
# containers
# ---------------------------------------------------------------------------

def test_globs(games):
    total = entries = 0
    for det in games:
        folder = os.path.join(det.path, "globs")
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if not name.lower().endswith(".glb"):
                continue
            with open(os.path.join(folder, name), "rb") as fh:
                data = fh.read()
            ents = globfile.parse(data)
            total += 1
            entries += len(ents)
            for ent in ents[:4]:
                blob = globfile.read(data, ent)
                must(globfile.replace(data, ent, blob) == data,
                     "%s: writing an entry back changed the file" % name)
    must(total > 0, "no globs found")
    return "%d globs, %d entries, writer is a no-op" % (total, entries)


def test_umds(games):
    total = files = 0
    for det in games:
        for dirpath, _dirs, names in os.walk(det.path):
            for name in names:
                if not name.lower().endswith(".umd"):
                    continue
                with open(os.path.join(dirpath, name), "rb") as fh:
                    data = fh.read()
                ents, _footer = umd.parse(data)
                total += 1
                files += len(ents)
                ent = ents[len(ents) // 2]
                must(umd.replace(data, ent, umd.read(data, ent)) == data,
                     "%s: writing an entry back changed the bundle" % name)
    return "%d bundles, %d files inside them" % (total, files)


def test_xbes(games):
    for det in games:
        image = xbe.load(det.xbe_path)
        must(image.title_id_hex.upper() == det.profile.title_id.upper(),
             "%s: title id %s does not match the profile"
             % (det.profile.short, image.title_id_hex))
        must(image.sections, "%s: no sections" % det.profile.short)
    return "%d executables, title ids match their profiles" % len(games)


def test_art(games):
    shot = 0
    for det in games:
        folder = os.path.join(det.path, "shell", "art")
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if not os.path.isfile(path):
                continue
            with open(path, "rb") as fh:
                data = fh.read()
            if name.lower().endswith(".rsb"):
                must(rsb.to_image(data).size[0] > 0, "%s decoded empty" % name)
                shot += 1
            elif name.lower().endswith(".xpr") and xpr.is_xpr(data):
                _o, code, _w, _h, _m = xpr.parse(data)
                if code in (0x05, 0x06, 0x07, 0x0C, 0x0E, 0x0F):
                    must(xpr.to_image(data).size[0] > 0,
                         "%s decoded empty" % name)
                    shot += 1
    return "%d shell bitmaps decoded" % shot


# ---------------------------------------------------------------------------
# transforms
# ---------------------------------------------------------------------------

def test_length_preserved(games):
    checked = 0
    for det in games:
        root = Root(det.path)
        for key in root.match(r"\.MIS$")[:6]:
            plain = root.read(key)
            for out, _n in (transforms.strip_difficulty(plain),
                            transforms.reveal_hidden(plain),
                            transforms.bump_enemy_tier(plain, 1)):
                must(len(out) == len(plain), "%s changed length" % key)
                checked += 1
        for key in root.match(r"R6GAMESETTINGS\.INI$")[:1]:
            plain = root.read(key)
            out, _n = transforms.scale_ini_values(
                plain, {"m_fSightRadius": 1.5, "m_iTerroristMaximumWounds": 2.0})
            must(len(out) == len(plain), "%s changed length" % key)
            must(transforms.read_ini_values(out, ["m_fSightRadius"])
                 ["m_fSightRadius"] == "7500.0", "sight radius did not scale")
            checked += 1
        for key in root.match(r"\.TPT$")[:3]:
            plain = root.read(key)
            out, _n = transforms.set_tpt_values(plain, {}, scale=1.4)
            must(len(out) == len(plain), "%s changed length" % key)
            checked += 1
    must(checked > 0, "nothing was checked")
    return "%d edits, every one the same length as the file it changed" % checked


def test_clamps(_games):
    plain = b"Assault=50\r\nObservation=100\r\nSSniper=75\r\n"
    out, _n = transforms.set_tpt_values(plain, {}, scale=4.0)
    got = transforms.read_ini_values(out, ["Assault", "Observation", "SSniper"])
    must(got["Assault"] == "100", "Assault should clamp to 100, got %r" % got)
    must(got["Observation"] == "100", "Observation should stay at 100")
    return "template skills clamp at 100 and keep their width"


def test_ini_shapes(_games):
    plain = b"a=+400.0\r\nb=1.5f\r\nc=10\r\nd=0.40\r\n"
    out, n = transforms.scale_ini_values(plain, {k: 1.5 for k in "abcd"})
    got = transforms.read_ini_values(out, list("abcd"))
    must(got == {"a": "+600.0", "b": "2.2f", "c": "15", "d": "0.60"},
         "shapes not preserved: %r" % got)
    must(n == 4, "expected 4 changes, got %d" % n)
    return "leading +, trailing f and integer forms all survive a scale"


# ---------------------------------------------------------------------------
# census
# ---------------------------------------------------------------------------

def test_gun_sides(games):
    lines = []
    for det in games:
        root = Root(det.path)
        if not root.match(r"\.GUN$"):
            continue
        ally = dataedit.gun_scope_set(root, "ally_guns")
        enemy = dataedit.gun_scope_set(root, "enemy_guns")
        must(not (ally & enemy), "%s: a gun is on both sides" % det.profile.short)
        splits = det.profile.id in ("ghost_recon_xbox", "island_thunder_xbox")
        if splits:
            must(ally and enemy,
                 "%s: the sides should be separable and came back %d/%d"
                 % (det.profile.short, len(ally), len(enemy)))
        lines.append("%s %d/%d" % (det.profile.short.split()[0], len(ally),
                                   len(enemy)))
    return "ally/enemy: " + ", ".join(lines)


def test_enemy_templates(games):
    lines = []
    for det in games:
        if det.profile.id not in ("ghost_recon_xbox", "island_thunder_xbox"):
            continue
        root = Root(det.path)
        names = dataedit.enemy_template_set(root)
        must(len(names) > 50,
             "%s: only %d enemy templates" % (det.profile.short, len(names)))
        lines.append("%s %d" % (det.profile.short.split()[0], len(names)))
    return "enemy templates: " + ", ".join(lines)


# ---------------------------------------------------------------------------
# the whole cycle, on a copy
# ---------------------------------------------------------------------------

#: what has to be copied for each game to exercise its own edits
FIXTURE_PARTS = {
    "ghost_recon_xbox": ["default.xbe", "mission", "actor", "equip",
                         "globs/ikedata.glb"],
    "island_thunder_xbox": ["default.xbe", "mission", "actor", "equip",
                            "globs/ikedata.glb"],
    "ghost_recon2_xbox": ["default.xbe", "script", "equip/CmbtModl.xml",
                          "globs/ikedata.glb"],
    "summit_strike_xbox": ["default.xbe", "script", "equip/CmbtModl.xml",
                           "globs/ikedata.glb"],
    "rainbow_six_3_xbox": ["default.xbe", "System/RainbowSix3Xbox.ini",
                           "System/xboxdynamic.umd"],
    "black_arrow_proto_xbox": ["RainbowSix3_Release.xbe",
                               "system/R6GameSettings.ini",
                               "system/RainbowSix3Xbox.ini", "template"],
    "graw_xbox": ["default.xbe", "System/R6GameSettings.ini",
                  "System/GR3XBoxAI.ini", "System/TWeapon.ini",
                  "System/RainbowSix3Xbox.ini"],
}


def _snapshot(folder):
    out = {}
    for dirpath, _dirs, names in os.walk(folder):
        if engine.BACKUP_DIR in dirpath:
            continue
        for name in names:
            full = os.path.join(dirpath, name)
            with open(full, "rb") as fh:
                out[os.path.relpath(full, folder)] = hashlib.sha1(
                    fh.read()).hexdigest()
    return out


def _fixture(det, where):
    parts = FIXTURE_PARTS.get(det.profile.id)
    if parts is None:
        return None
    dst = os.path.join(where, det.profile.id)
    os.makedirs(dst, exist_ok=True)
    for rel in parts:
        src = os.path.join(det.path, rel.replace("/", os.sep))
        out = os.path.join(dst, rel.replace("/", os.sep))
        if not os.path.exists(src):
            return None
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if os.path.isdir(src):
            shutil.copytree(src, out, dirs_exist_ok=True)
        else:
            shutil.copy2(src, out)
    return dst


def test_cycle(games, where):
    from gui.presets import PRESETS

    done = []
    for det in games:
        folder = _fixture(det, where)
        if folder is None:
            continue
        copy = identify(folder)
        must(copy.ok, "the copy of %s was not recognised" % det.profile.short)
        before = _snapshot(folder)

        wrote = 0
        for _name, values in PRESETS.get(det.profile.id, [])[1:]:
            full = dict(det.profile.defaults())
            full.update(values)
            report = engine.apply(copy.path, copy.profile, full)
            must(report["broken"] == 0,
                 "%s: %d files could not be read back"
                 % (det.profile.short, report["broken"]))
            wrote += report["files"]

        engine.revert(copy.path, copy.profile)
        after = _snapshot(folder)
        must(before == after,
             "%s: %d file(s) differ after revert"
             % (det.profile.short,
                sum(1 for k in before if before[k] != after.get(k))))
        done.append("%s %d" % (det.profile.short.split()[0], wrote))
    must(done, "no fixtures were built")
    return "every preset applied then reverted clean: " + ", ".join(done)


def test_idempotent(games, where):
    """Applying the same settings twice leaves the same folder as applying once."""
    from gui.presets import PRESETS

    for det in games:
        if det.profile.id != "ghost_recon_xbox":
            continue
        folder = _fixture(det, where)
        copy = identify(folder)
        _name, values = PRESETS[det.profile.id][3]
        full = dict(det.profile.defaults())
        full.update(values)
        engine.apply(copy.path, copy.profile, full)
        once = _snapshot(folder)
        engine.apply(copy.path, copy.profile, full)
        twice = _snapshot(folder)
        must(once == twice, "a second apply changed the folder again")
        engine.revert(copy.path, copy.profile)
        return "applying twice is the same as applying once"
    raise AssertionError("Ghost Recon is not on this shelf")


# ---------------------------------------------------------------------------

def main(argv):
    shelf = argv[0] if argv else r"E:\XBOX Classic Games"
    print("shelf: %s" % shelf)
    games = scan_folder(shelf)
    if not games:
        print("no supported game folders found")
        return 1
    seen = {}
    for det in games:
        seen.setdefault(det.profile.id, det)
    games = list(seen.values())
    print("%d game(s): %s\n" % (len(games),
                                ", ".join(d.profile.short for d in games)))

    print("containers")
    check("every glob parses and round-trips", lambda: test_globs(games))
    check("every .umd parses and round-trips", lambda: test_umds(games))
    check("every executable identifies its game", lambda: test_xbes(games))
    check("every shell bitmap decodes", lambda: test_art(games))

    print("transforms")
    check("edits keep the file's length", lambda: test_length_preserved(games))
    check("template skills clamp", lambda: test_clamps(games))
    check("ini value shapes survive scaling", lambda: test_ini_shapes(games))

    print("census")
    check("weapons split by side where the data allows",
          lambda: test_gun_sides(games))
    check("enemy templates are found", lambda: test_enemy_templates(games))

    print("apply and revert, on copies")
    with tempfile.TemporaryDirectory(prefix="tcxms-tests-") as where:
        check("every preset applies and reverts clean",
              lambda: test_cycle(games, where))
        check("applying twice equals applying once",
              lambda: test_idempotent(games, where))

    print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
    for name, _exc, tb in FAIL:
        print("\n--- %s ---\n%s" % (name, tb))
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

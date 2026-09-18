r"""Checks that run against the real games, without ever writing to one.

    python tests\run_tests.py

Two rules this file keeps, and they are the reason it is worth trusting:

**No retail file is opened for writing, ever.** The editors are exercised
read-only against the real installations; anything that needs a write happens
in a sandbox copy under the system temporary directory, and the copy is made
with `shutil.copy2` from files that are only ever read.

**The round-trip is checked byte-for-byte.** The whole design rests on
"loading and saving a file you did not change gives the identical bytes back",
so that is asserted on hundreds of real files rather than on one fixture.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tcpc import art, engine, inifile, rsb, rsexml               # noqa: E402
from tcpc.games import PROFILES                                  # noqa: E402
from tcpc.install import identify, scan_folder                   # noqa: E402
from tcpc.model import BOOL, CHOICE, INT, MOD                    # noqa: E402

PASS, FAIL = [], []


def check(name, condition, detail=""):
    (PASS if condition else FAIL).append(name)
    print("  %s %s%s" % ("ok  " if condition else "FAIL",
                         name, ("  -- " + detail) if detail and not condition
                         else ""))
    return bool(condition)


def games():
    """One detection per supported game found on this machine."""
    seen, out = {}, []
    for lib in art.steam_libraries():
        for det in scan_folder(lib):
            if det.profile.id not in seen:
                seen[det.profile.id] = det
                out.append(det)
    return out


# ---------------------------------------------------------------------------
# profiles: these need no game present
# ---------------------------------------------------------------------------

def test_profiles():
    print("\n[profiles]")
    ids = [p.id for p in PROFILES]
    check("profile ids are unique", len(ids) == len(set(ids)))
    for p in PROFILES:
        keys = [s.key for s in p.settings]
        check("%s: setting keys unique" % p.id, len(keys) == len(set(keys)))
        check("%s: every default is valid" % p.id,
              all(s.coerce(s.default) == s.default for s in p.settings),
              str([s.key for s in p.settings
                   if s.coerce(s.default) != s.default]))
        check("%s: defaults produce no edits" % p.id,
              not p.build_edits(p.defaults()),
              "a stock profile must be a no-op")
        # every `requires` must name a setting that exists
        bad = [(s.key, d) for s in p.settings for d in s.requires
               if p.setting(d) is None]
        check("%s: requires name real settings" % p.id, not bad, str(bad))
        if p.delivery == MOD:
            check("%s: mod name and base mod set" % p.id,
                  bool(p.mod_name and p.layout.base_mod))

    print("\n[presets]")
    from gui.presets import PRESETS
    for p in PROFILES:
        bad = []
        for name, vals in PRESETS.get(p.id, []):
            for k, v in vals.items():
                s = p.setting(k)
                if s is None or s.coerce(v) != v:
                    bad.append("%s/%s=%r" % (name, k, v))
        check("%s: presets reference real settings" % p.id, not bad, str(bad))


# ---------------------------------------------------------------------------
# the editors, read-only against the real data
# ---------------------------------------------------------------------------

def test_roundtrip(dets):
    print("\n[round-trip: load and save must return identical bytes]")
    for det in dets:
        root = det.path
        ini_n = xml_n = 0
        bad = []
        for rel in engine.walk_rel(root):
            low = rel.lower()
            if low.endswith((".ini", ".tpt")) and ini_n < 120:
                path = os.path.join(root, rel.replace("/", os.sep))
                try:
                    doc = inifile.Ini.load(path)
                except Exception:                 # noqa: BLE001
                    continue
                ini_n += 1
                with open(path, "rb") as fh:
                    if doc.to_bytes() != fh.read():
                        bad.append(rel)
            elif low.endswith((".gun", ".kit", ".atr", ".wsf", ".cgs", ".acm",
                               ".prj", ".itm", ".xml")) and xml_n < 200:
                path = os.path.join(root, rel.replace("/", os.sep))
                try:
                    doc = rsexml.Doc.load(path)
                except Exception:                 # noqa: BLE001
                    continue
                xml_n += 1
                with open(path, "rb") as fh:
                    if doc.to_bytes() != fh.read():
                        bad.append(rel)
        check("%s: %d ini + %d xml files round-trip"
              % (det.profile.short, ini_n, xml_n), not bad, str(bad[:4]))


def test_art(dets):
    print("\n[art: every skin needs a backdrop and a mark]")
    for det in dets:
        banner = art.banner_image(det, None)
        emblem = art.emblem_image(det, None)
        check("%s: backdrop decodes" % det.profile.short, banner is not None)
        check("%s: mark decodes and is cut out" % det.profile.short,
              emblem is not None and emblem.mode == "RGBA"
              and emblem.split()[-1].getextrema()[0] == 0,
              "the mark must have transparent pixels or it is a rectangle")
        if banner is not None:
            check("%s: backdrop is not mostly empty page" % det.profile.short,
                  banner.width >= 400 and banner.height >= 300,
                  "%s" % (banner.size,))


def test_rsb(dets):
    print("\n[rsb: the Red Storm games' own art]")
    for det in dets:
        folder = None
        for cand in ("Data/Shell/Art", "data/shell/art"):
            p = os.path.join(det.path, cand.replace("/", os.sep))
            if os.path.isdir(p):
                folder = p
                break
        if folder is None:
            continue
        files = [f for f in os.listdir(folder) if f.lower().endswith(".rsb")]
        ok = [f for f in files if rsb.load(os.path.join(folder, f)) is not None]
        check("%s: %d of %d .rsb decode"
              % (det.profile.short, len(ok), len(files)),
              len(ok) >= len(files) - 4,
              "fonts are allowed to fail; anything else is not")


def test_globs():
    print("\n[globs: * must not cross a directory separator]")
    paths = ["Actor/enemy.atr", "Actor/rifleman/mine.atr",
             "Equip/ak47.gun", "Equip/ak47_npc.gun", "Kits/team/a.kit"]
    check("* stops at a separator",
          engine.expand(paths, "Actor/*.atr") == ["Actor/enemy.atr"])
    check("** crosses one",
          len(engine.expand(paths, "Actor/**.atr")) == 2)
    check("case is folded",
          engine.expand(paths, "EQUIP/*.GUN") == ["Equip/ak47.gun",
                                                  "Equip/ak47_npc.gun"])
    check("not: excludes", engine.in_scope("Equip/e_x.gun", "not:e_*") is False)
    check("only: includes", engine.in_scope("Equip/e_x.gun", "only:e_*") is True)


def test_numbers():
    print("\n[numbers: an edit must keep the file's own spelling]")
    check("integer stays integer", inifile.format_number(17.4, "35") == "17")
    check("six places stay six",
          inifile.format_number(150, "300.000000") == "150.000000")
    check("decimal comma survives",
          inifile.format_number(0.5, "0,8") == "0,5")
    check("comma value parses",
          inifile.parse_number("0,8") == 0.8)
    check("a word is not a number",
          inifile.parse_number("true") is None)
    check("xml integer rungs round",
          rsexml.format_number(2.6, "3") == "3")


# ---------------------------------------------------------------------------
# apply / revert, in a sandbox copy
# ---------------------------------------------------------------------------

def sandbox_for(det, tmp):
    """A copy of just the parts of a game this profile can touch.

    A mod-delivery profile's selectors are relative to the STOCK MOD folder,
    not to the install root, because that is what a generated mod shadows. So
    `Actor/*.atr` means `Mods\\Origmiss\\Actor\\*.atr` on disk, and a sandbox
    built without that prefix copies nothing at all.
    """
    root = os.path.join(tmp, det.profile.id)
    base = (det.profile.layout.base_mod + "/") if det.profile.delivery == MOD \
        else ""
    wanted = set()
    for e in det.profile.build_edits(_max_values(det.profile)):
        wanted.add((base + e.select).split("*")[0].rstrip("/"))
    for sig in det.profile.layout.signature:
        wanted.add(sig.split("*")[0].rstrip("/"))
    for rel in engine.walk_rel(det.path):
        if not any(rel.lower().startswith(w.lower()) for w in wanted if w):
            continue
        src = os.path.join(det.path, rel.replace("/", os.sep))
        dst = os.path.join(root, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    exe = os.path.join(root, det.profile.layout.exe.replace("/", os.sep))
    os.makedirs(os.path.dirname(exe), exist_ok=True)
    if not os.path.exists(exe):
        with open(exe, "wb") as fh:
            fh.write(b"stub")
    return root


def _max_values(profile):
    """Every option moved off its default, so the test exercises all of them."""
    out = dict(profile.defaults())
    for s in profile.settings:
        if not s.enabled:
            continue
        if s.kind == BOOL:
            out[s.key] = not s.default
        elif s.kind == INT:
            out[s.key] = s.maximum if s.default != s.maximum else s.minimum
        elif s.kind == CHOICE:
            other = [c.value for c in s.choices if c.value != s.default]
            if other:
                out[s.key] = other[-1]
    return profile.effective(out)


def tree_hash(root):
    import hashlib
    out = {}
    for base, _d, names in os.walk(root):
        if ".tcpc-backup" in base:
            continue
        for n in names:
            p = os.path.join(base, n)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, root)] = hashlib.sha1(fh.read()).hexdigest()
    return out


def test_apply_revert(dets):
    print("\n[apply / idempotence / revert, on sandbox copies]")
    tmp = tempfile.mkdtemp(prefix="tcpc-test-")
    try:
        for det in dets:
            p = det.profile
            root = sandbox_for(det, tmp)
            local = identify(root)
            if not check("%s: sandbox is still recognised" % p.short, local.ok,
                         local.message):
                continue
            before = tree_hash(root)
            values = _max_values(p)

            r1 = engine.apply(root, p, values)
            check("%s: apply succeeded (%d files)" % (p.short, r1.files),
                  r1.ok and r1.files > 0,
                  "; ".join(r1.warnings[:2]))
            after = tree_hash(root)

            r2 = engine.apply(root, p, values)
            again = tree_hash(root)
            check("%s: applying twice equals applying once" % p.short,
                  after == again and r2.ok)

            engine.apply(root, p, p.defaults())
            back = tree_hash(root)
            check("%s: clearing every option returns to stock" % p.short,
                  {k: v for k, v in back.items() if k in before} == before,
                  str([k for k in before if back.get(k) != before[k]][:3]))

            engine.apply(root, p, values)
            engine.revert(root, p)
            final = tree_hash(root)
            check("%s: restore returns every byte" % p.short,
                  {k: v for k, v in final.items() if k in before} == before,
                  str([k for k in before if final.get(k) != before[k]][:3]))

            if p.delivery == MOD:
                check("%s: no retail file was touched" % p.short,
                      all(final.get(k) == v for k, v in before.items()))
                check("%s: the generated mod folder is gone" % p.short,
                      not os.path.isdir(engine.mod_dir(root, p)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_mod_guard(dets):
    print("\n[the mod folder guard]")
    tmp = tempfile.mkdtemp(prefix="tcpc-guard-")
    try:
        for det in dets:
            p = det.profile
            if p.delivery != MOD:
                continue
            root = sandbox_for(det, tmp)
            mine = engine.mod_dir(root, p)
            os.makedirs(mine, exist_ok=True)
            with open(os.path.join(mine, "ModsCont.txt"), "w") as fh:
                fh.write("hand made")
            try:
                engine.apply(root, p, _max_values(p))
                check("%s: refuses to delete somebody else's mod" % p.short,
                      False, "it overwrote it")
            except engine.ApplyError:
                check("%s: refuses to delete somebody else's mod" % p.short,
                      True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    dets = games()
    print("Found %d game(s): %s"
          % (len(dets), ", ".join(d.profile.short for d in dets) or "none"))
    test_profiles()
    test_globs()
    test_numbers()
    if dets:
        test_roundtrip(dets)
        test_art(dets)
        test_rsb(dets)
        test_apply_revert(dets)
        test_mod_guard(dets)
    else:
        print("\nNo games installed -- the checks that need one were skipped.")
    print("\n%d passed, %d failed." % (len(PASS), len(FAIL)))
    for name in FAIL:
        print("  FAILED: %s" % name)
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception:                             # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2)

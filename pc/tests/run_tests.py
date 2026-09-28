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
import re
import shutil
import struct
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tcpc import art, engine, inifile, rsb, rsexml, upackage     # noqa: E402
from tcpc.games import PROFILES                                  # noqa: E402
from tcpc.install import identify, scan_folder                   # noqa: E402
from tcpc.model import BOOL, CHOICE, INT, IniEdit, MOD, Setting  # noqa: E402

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
    for lib in art.search_roots():
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

def test_created_files():
    r"""An in-place profile that ADDS a file the game never shipped.

    Raven Shield's cut game modes need a `.mod` that does not exist, which
    breaks the assumption every other in-place edit rests on: that the file is
    already there and has a pristine copy to go back to. A created file has no
    pristine copy, so undoing it means DELETING it -- and getting that wrong
    leaves litter in someone's game folder that no Revert will ever clear.
    """
    print("\n[in-place profiles that create a file]")
    from tcpc.model import FileCopy, GameProfile, Layout

    root = tempfile.mkdtemp(prefix="tcpc-new-")
    try:
        os.makedirs(os.path.join(root, "system"))
        stock = os.path.join(root, "system", "existing.ini")
        with open(stock, "w") as fh:
            fh.write("[a]\nk=1\n")
        body = b"[Engine.R6Mod]\nm_szGameTypes=RGM_DefendMode\n"
        profile = GameProfile(
            id="t", title="T", short="T",
            layout=Layout(signature=["system/existing.ini"], data_dir="system"),
            delivery="inplace",
            settings=[Setting("make", "Make", BOOL, False)],
            build_edits=lambda v: ([FileCopy("system/Generated.mod", data=body,
                                             note="generated mod")]
                                   if v["make"] else []))
        made = os.path.join(root, "system", "Generated.mod")

        engine.apply(root, profile, {"make": True})
        check("created: the new file is written", os.path.isfile(made))
        check("created: with exactly the stated content",
              open(made, "rb").read() == body)
        check("created: the manifest records it as created, not modified",
              engine.read_manifest(root).get("created") == ["system/Generated.mod"]
              and engine.read_manifest(root).get("files") == [])

        engine.apply(root, profile, {"make": True})
        check("created: applying twice leaves one copy",
              os.path.isfile(made) and open(made, "rb").read() == body)

        engine.apply(root, profile, {"make": False})
        check("created: clearing the option deletes it", not os.path.isfile(made))

        engine.apply(root, profile, {"make": True})
        engine.revert(root, profile)
        check("created: revert deletes it", not os.path.isfile(made))
        check("created: a file that was already there is untouched",
              open(stock).read() == "[a]\nk=1\n")

        # and the guard: a missing file that NOTHING can supply is still an
        # error, not an invitation to invent one.
        profile.build_edits = lambda v: [IniEdit("system/absent.ini",
                                                 section="a", key="k", value=2)]
        out = engine.apply(root, profile, {"make": True})
        check("created: an ordinary edit to a missing file is still refused",
              not os.path.isfile(os.path.join(root, "system", "absent.ini"))
              and out.warnings,
              "no file should be invented and the user should be told: %s"
              % out.warnings[:2])
    finally:
        shutil.rmtree(root, ignore_errors=True)


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
    # Three value sets, not one. `_max_values` flips a boolean OFF its
    # default, so an option that defaults to ON contributes nothing to the max
    # set -- Raven Shield's menu-bar mirror is exactly that, and it left
    # `R6Description.u` out of the sandbox entirely. The booleans are put back
    # in a third pass so every file any setting can reach gets copied.
    maxed = _max_values(det.profile)
    restored = dict(maxed)
    for s in det.profile.settings:
        if s.kind == BOOL:
            restored[s.key] = not maxed[s.key]
    wanted = set()
    for values in (maxed, det.profile.effective(restored),
                   det.profile.effective(det.profile.defaults())):
        for e in det.profile.build_edits(values):
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
            if p.delivery == "overlay":
                continue          # multi-gigabyte archives; see test_overlay
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


def write_bundle(path, entries):
    """Build a `BNDL` archive. Test-only -- the tool itself never writes one.

    Having a writer here is worth more than the convenience: the reader was
    developed against the retail archives, so a round-trip through an
    independently written one is the check that the format was understood
    rather than merely pattern-matched into working.
    """
    tree = {}
    for name, data in entries.items():
        node = tree
        parts = name.split("/")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = data

    # Two passes: the offsets have to be absolute, and they depend on how long
    # the index turns out to be, which depends on the names and not on the
    # offsets -- so build the index once with placeholders to learn its size.
    def build(base):
        idx, at = bytearray(), base

        def walk(node):
            nonlocal at
            for key in sorted(node):
                val = node[key]
                if isinstance(val, dict):
                    idx.append(1)
                    idx.append(1)
                    idx.extend(key.encode("latin-1") + b"\0")
                    walk(val)
                    idx.append(3)
                else:
                    idx.append(2)
                    idx.extend(struct.pack("<Q", at))
                    idx.extend(struct.pack("<I", len(val)))
                    idx.append(1)
                    idx.extend(key.encode("latin-1") + b"\0")
                    at += len(val)
        walk(tree)
        return bytes(idx)

    size = len(build(0))
    index = build(16 + size)
    assert len(index) == size
    blob = b"".join(entries[k] for k in _ordered(tree))
    with open(path, "wb") as fh:
        fh.write(b"BNDL" + struct.pack("<I", 2)
                 + struct.pack("<Q", 16 + len(index)))
        fh.write(index)
        fh.write(blob)


def _ordered(tree, prefix=""):
    """File paths in the order `write_bundle` lays their data down."""
    out = []
    for key in sorted(tree):
        val = tree[key]
        if isinstance(val, dict):
            out += _ordered(val, prefix + key + "/")
        else:
            out.append(prefix + key)
    return out


def test_bundle(dets):
    print("\n[bundle: the Diesel archives]")
    from tcpc.bundle import Bundle, BundleSet
    tmp = tempfile.mkdtemp(prefix="tcpc-bndl-")
    try:
        entries = {"context.xml": b"<context/>",
                   "data/units/weapons/u_test.xml": b"<units><var name='a' value='1'/></units>",
                   "data/settings/x.xml": b"x" * 5000,
                   "settings/loose.xml": b"<loose/>"}
        path = os.path.join(tmp, "quick.bundle")
        write_bundle(path, entries)
        b = Bundle(path)
        check("a written bundle reads back", len(b) == len(entries),
              "%d of %d" % (len(b), len(entries)))
        check("every file comes back byte-identical",
              all(b.read(k) == v for k, v in entries.items()))
        b.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    for det in dets:
        if det.profile.delivery != MOD and det.profile.layout.bundles_dir:
            folder = os.path.join(det.path,
                                  det.profile.layout.bundles_dir)
            with BundleSet(folder) as bs:
                check("%s: %d files indexed from the real archives"
                      % (det.profile.short, len(bs)), len(bs) > 10000)
                w = bs.find("data/units/weapons/*.xml")
                check("%s: weapon definitions are readable XML" % det.profile.short,
                      bool(w) and b"<units>" in bs.read(w[0]))


def test_overlay(dets):
    print("\n[overlay: write loose, never touch the archive]")
    from tcpc.bundle import BundleSet
    for det in dets:
        p = det.profile
        if p.delivery != "overlay":
            continue
        tmp = tempfile.mkdtemp(prefix="tcpc-ovl-")
        try:
            root = os.path.join(tmp, p.id)
            # A stand-in install: the signature files, plus a small archive
            # carrying the real weapon definitions out of the retail one.
            for sig in p.layout.signature:
                dest = os.path.join(root, sig.replace("/", os.sep))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                if not sig.endswith(".bundle"):
                    with open(dest, "wb") as fh:
                        fh.write(b"stub")
            entries = {}
            with BundleSet(os.path.join(det.path,
                                        p.layout.bundles_dir)) as bs:
                for rel in bs.find("data/units/weapons/*.xml"):
                    entries[rel] = bs.read(rel)
                    # ...and its compiled twin, which is the file the engine
                    # actually reads. A stand-in archive without them would
                    # test a path the real game never takes.
                    twin = engine.compiled_twin(p, rel)
                    if twin and twin in bs:
                        entries[twin] = bs.read(twin)
            write_bundle(os.path.join(root, "Bundles", "quick.bundle"), entries)
            exe = os.path.join(root, p.layout.exe.replace("/", os.sep))
            os.makedirs(os.path.dirname(exe) or root, exist_ok=True)
            with open(exe, "wb") as fh:
                fh.write(b"stub")

            local = identify(root)
            if not check("%s: stand-in install is recognised" % p.short,
                         local.ok, local.message):
                continue
            # a hand-placed loose file the tool must NOT delete
            keep = os.path.join(root, "Data", "textures", "mine.dds")
            os.makedirs(os.path.dirname(keep), exist_ok=True)
            with open(keep, "wb") as fh:
                fh.write(b"my texture pack")

            before = tree_hash(root)
            values = _max_values(p)
            r1 = engine.apply(root, p, values)
            check("%s: overlay apply wrote files" % p.short,
                  r1.ok and len(r1.verified) > 0, "; ".join(r1.warnings[:2]))
            suffix = p.layout.compiled_suffix
            wrote_compiled = [k for k in r1.verified if k.lower().endswith(suffix)]
            check("%s: the COMPILED twin was written too" % p.short,
                  len(wrote_compiled) > 0,
                  "editing only the source is a no-op in this engine")
            check("%s: the compiled twin carries the edit" % p.short,
                  _twin_edited(root, det.path, p, wrote_compiled),
                  "the engine reads this file, so an unchanged one is a no-op")
            check("%s: the archive was not modified" % p.short,
                  tree_hash(root)["Bundles\\quick.bundle"]
                  == before["Bundles\\quick.bundle"])
            after = tree_hash(root)

            engine.apply(root, p, values)
            check("%s: applying twice equals applying once" % p.short,
                  tree_hash(root) == after)

            rv = engine.revert(root, p)
            final = tree_hash(root)
            check("%s: restore removes every file it added" % p.short,
                  final == before,
                  str([k for k in set(final) ^ set(before)][:3]))
            check("%s: somebody else's loose file survived" % p.short,
                  os.path.isfile(keep))
            check("%s: revert reported what it removed" % p.short, rv.files > 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def _twin_edited(root, real_root, profile, rels):
    """Did a written compiled file come back DIFFERENT from the retail one?

    Compared against the real archive rather than against a fixed number,
    because the option the sweep picks is not always the one that lowers the
    value -- an earlier version of this check asserted "spread went down" and
    failed on a preset that widens it.
    """
    from tcpc import xmlbin
    from tcpc.bundle import BundleSet
    with BundleSet(os.path.join(real_root, profile.layout.bundles_dir)) as bs:
        for rel in rels:
            key = rel.replace("\\", "/")
            if key.lower().startswith("data/"):
                key = "data/" + key.split("/", 1)[1]
            if key not in bs:
                continue
            path = os.path.join(root, rel.replace("/", os.sep))
            try:
                with open(path, "rb") as fh:
                    mine, _a = xmlbin.loads(fh.read())
                theirs, _b = xmlbin.loads(bs.read(key))
            except Exception:                     # noqa: BLE001
                continue
            a = [n.get("value") for n in xmlbin.select(mine, "var[name=spread_normal]")]
            b = [n.get("value") for n in xmlbin.select(theirs, "var[name=spread_normal]")]
            if a and b and a != b:
                return True
    return False


def _enemy_total(text):
    """Enemy soldiers a world file places.

    Advanced Warfighter places squads, not men, and the squad's size is the
    digit on the end of the name it references -- so counting enemies is
    counting suffixes.
    """
    total = 0
    for ref in re.findall(r'<unit name="group_unit"[^>]*group="([^"]+)"', text):
        if not ref.lower().startswith(("mex", "ag_")):
            continue
        m = re.match(r"^(.*?)(\d+)$", ref)
        total += int(m.group(2)) if m else 1
    return total


def test_graw_enemies(dets):
    """The squad rename is the largest single edit in the tool.

    It rewrites names rather than numbers, and a name the group manager cannot
    generate is a squad that does not spawn -- so the table is checked against
    the game it came from rather than trusted.
    """
    print("\n[GRAW enemy levers]")
    from tcpc.bundle import BundleSet
    from tcpc.games import BY_ID
    import importlib
    for det in dets:
        p = det.profile
        if p.id not in ("graw", "graw2"):
            continue
        mod = importlib.import_module("tcpc.games." + p.id)
        sizes = getattr(mod, "SQUAD_SIZE", {})
        check("%s: squad table is not empty" % p.short, bool(sizes))

        values = dict(p.defaults())
        values["enemy_squads"] = "full"
        table = {}
        for e in p.build_edits(values):
            if e.select.endswith("world.xml") and e.remap:
                table = e.remap

        bad = [v for v in table.values()
               if not any(v == "%s%d" % (b, n) for b, n in sizes.items())]
        check("%s: every renamed-to squad is one the game generates" % p.short,
              bool(table) and not bad, str(bad[:4]))
        friendly = [k for k in list(table) + list(table.values())
                    if not k.lower().startswith(("mex", "ag_"))]
        check("%s: no friendly squad is renamed" % p.short, not friendly,
              str(friendly[:4]))

        with BundleSet(os.path.join(det.path, p.layout.bundles_dir)) as bs:
            refs = set()
            worlds = [w for w in bs.paths() if w.endswith("/xml/world.xml")]
            for w in worlds:
                refs.update(re.findall(
                    r'<unit name="group_unit"[^>]*group="([^"]+)"',
                    bs.read(w).decode("latin-1")))
            first = [w for w in worlds if "mission01" in w]
            text = bs.read(first[0]).decode("latin-1") if first else ""
        check("%s: the table reaches names the shipped worlds use" % p.short,
              bool(set(table) & refs),
              "no world references anything this would rewrite")

        if not text:
            continue
        doc = rsexml.Doc(text)
        status, n = doc.remap_attr("unit[name=group_unit]", "group", table)
        before, after = _enemy_total(text), _enemy_total(doc.text)
        check("%s: mission 1 renames %d placements" % (p.short, n),
              status == "changed" and n > 0)
        check("%s: mission 1 gains enemies (%d -> %d)"
              % (p.short, before, after), after > before)

        values["enemy_squads"] = "thin"
        thin = {}
        for e in p.build_edits(values):
            if e.select.endswith("world.xml") and e.remap:
                thin = e.remap
        doc2 = rsexml.Doc(text)
        doc2.remap_attr("unit[name=group_unit]", "group", thin)
        check("%s: half-strength loses enemies (%d -> %d)"
              % (p.short, before, _enemy_total(doc2.text)),
              _enemy_total(doc2.text) < before)


def _rs3_packages(root):
    """Every Raven Shield package present under `root`.

    A sandbox holds only what an edit selects, and `R61stWeapons.u` is
    deliberately not selected -- it carries first-person hands and no
    statistics -- so a missing file here is the profile being precise rather
    than something going wrong.
    """
    out = {}
    for f in ("R6Weapons.u", "R63rdWeapons.u", "R61stWeapons.u",
              "R6Description.u"):
        path = os.path.join(root, "system", f)
        if os.path.exists(path):
            out[f] = upackage.Package.load(path)
    return out


def _csv_rows(name):
    import csv
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "research", name)
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def test_packages(dets):
    r"""Raven Shield's compiled `.u` weapon and ammunition patching.

    The first half is the reason any of this can be trusted: the offsets this
    tool computes by parsing are compared against `research/*.csv` and
    `rs3_descbars.json`, which were derived separately during the research
    pass. An earlier version of `upackage` searched for a property's name
    index instead of parsing the list, agreed with the research on 1,808 of
    1,809 weapon offsets, and was WRONG -- the one disagreement was a byte
    pair inside a float. A single mismatch here means the same thing.
    """
    det = next((d for d in dets if d.profile.id == "ravenshield"), None)
    if det is None:
        return
    print("\n[Raven Shield: compiled package patching]")
    profile = det.profile
    pkgs = _rs3_packages(det.path)

    # -- offsets, against independently derived research ------------------
    for name, files in (("rs3_weapons.csv", ("R6Weapons.u", "R63rdWeapons.u",
                                             "R61stWeapons.u")),
                        ("rs3_ammo.csv", ("R6Weapons.u",))):
        agree = bad = 0
        first = ""
        for row in _csv_rows(name):
            pkg = next((pkgs[f] for f in files
                        if (pkgs[f].export(row["class"]) or _N).is_class), None)
            if pkg is None:
                bad += 1
                continue
            for col, want in row.items():
                if not col.endswith("@") or not want:
                    continue
                prop = pkg.find_property(row["class"], col[:-1])
                value = pkg.get(row["class"], col[:-1])
                stated = (row.get(col[:-1]) or "").strip()
                if prop is None or prop.offset != int(want, 16) \
                        or not _same(value, stated):
                    bad += 1
                    first = first or "%s.%s" % (row["class"], col[:-1])
                    continue
                agree += 1
        check("Raven Shield: %s -- %d offsets and values agree" % (name, agree),
              bad == 0 and agree > 200, "%d disagree, first %s" % (bad, first))

    import json
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "research", "rs3_descbars.json")
    with open(path) as fh:
        bars = json.load(fh)
    desc = pkgs["R6Description.u"]
    agree = bad = 0
    for row in bars:
        for col, want in list(row.items()):
            if not col.endswith("@"):
                continue
            for i, expect in enumerate(row[col[:-1]]):
                key = "%s[%d]" % (col[:-1], i)
                prop = desc.find_property(row["class"], key)
                if prop is None or desc.get(row["class"], key) != expect \
                        or (i == 0 and prop.offset != int(want, 16)):
                    bad += 1
                else:
                    agree += 1
    check("Raven Shield: menu stat bars -- %d array elements agree" % agree,
          bad == 0 and agree > 600, "%d disagree" % bad)

    # -- a class that cannot be parsed is refused, not guessed at ---------
    refused = []
    for pkg in pkgs.values():
        for e in pkg.classes():
            if e.size <= 0:
                continue
            try:
                pkg.defaults(e.name)
            except upackage.PackageError:
                refused.append(e.name)
    check("Raven Shield: 535 classes parse, the %d with script are refused"
          % len(refused), len(refused) == 6 and "R6Weapons" in refused,
          str(sorted(refused)))
    check("Raven Shield: a refused class is not written to",
          pkgs["R6Weapons.u"].set("R6Weapons", "m_iEnergy", 1) is False)

    # -- the header is NOT the same shape for a class and a function ------
    # `UObject::Serialize` writes a tagged property list for every object
    # whose class is not `UClass`, so a Function, State or Struct export
    # carries an empty one -- a single `None` byte -- before `SuperField`.
    # Miss it and the whole header shifts one index, which does not crash and
    # does not look wrong: `FriendlyName` simply comes out of `Children`.
    # The check is that `FriendlyName` resolves to the export's own name,
    # which Unreal guarantees for everything except an operator, where it is
    # the token instead (`DivideEqual_VectorFloat` is `/=`).
    OPERATORS = set("+-*/%^&|!~<>=$@") | {"Dot", "Cross", "ClockwiseFrom"}

    def friendly(pkg, e):
        pos = pkg._struct_prologue(e)
        back = e.offset
        if not e.is_class:
            back = pkg._walk(back, e.offset + e.size, "", [])
        for _ in range(4):
            _v, back = upackage.compact_index(pkg.data, back)
        idx, end = upackage.compact_index(pkg.data, back)
        assert end == pos, "prologue disagrees with itself"
        return pkg.names[idx] if 0 <= idx < len(pkg.names) else None

    named = ops = broken = classes = 0
    wrong = []
    for pkg in pkgs.values():
        for e in pkg.exports:
            if e.size <= 0:
                continue
            kind = "Class" if e.is_class else e.class_name
            if kind not in ("Class", "Function", "State", "Struct"):
                continue
            try:
                got = friendly(pkg, e)
            except Exception as exc:                      # noqa: BLE001
                broken += 1
                wrong.append("%s: %s" % (e.name, exc))
                continue
            if got == e.name:
                named += 1
                classes += e.is_class
            elif got and not e.is_class and set(got) <= OPERATORS:
                ops += 1
            else:
                broken += 1
                wrong.append("%s -> %r" % (e.name, got))
    # No operators are expected in these three packages -- they live in
    # Core.u, which a sandbox never selects -- so `ops` is reported, not
    # required.
    check("Raven Shield: %d class/function/state/struct headers parse "
          "(%d named, %d operators)" % (named + ops, named, ops),
          broken == 0 and classes > 100 and named > 1000, str(wrong[:4]))

    # ...and the reason the branch is there: without it, a function's header
    # is read one index short. If this ever starts passing, the fix is gone.
    pkg = pkgs["R6Weapons.u"]
    e = next(x for x in pkg.exports
             if x.class_name == "Function" and x.size > 0)
    pos = e.offset
    for _ in range(5):                       # the old, class-only walk
        _v, pos = upackage.compact_index(pkg.data, pos)
    check("Raven Shield: a function header does not start where a class "
          "header does", pos != pkg._struct_prologue(e),
          "%s: the class-only walk and the real prologue both end at 0x%x"
          % (e.name, pos))

    # -- types: a `b` prefix settles nothing ------------------------------
    caps = ("bSingle", "bThreeRound", "bFullAuto", "bCMag", "bSilencer",
            "bLight", "bMiniScope", "bHeatVision")
    third = pkgs["R63rdWeapons.u"]
    capped = [e.name for e in third.classes() if e.size > 0
              and any(third.find_property(e.name, "m_stWeaponCaps." + c)
                      for c in caps)]
    wrong = [(n, c) for n in capped for c in caps
             if third.find_property(n, "m_stWeaponCaps." + c)
             and third.find_property(n, "m_stWeaponCaps." + c).kind != "int"]
    check("Raven Shield: the %d classes with weapon caps hold them as INTS, "
          "not bools" % len(capped), capped and not wrong, str(wrong[:3]))
    check("Raven Shield: asking for a cap as a bool returns nothing",
          capped and third.find_property(capped[0], "m_stWeaponCaps.bSingle",
                                         "bool") is None)
    bools = [(e.name, prop) for pkg in pkgs.values()
             for e in pkg.classes() if e.size > 0
             for path, prop in _safe_defaults(pkg, e.name).items()
             if path == prop.path and prop.kind == "bool"]
    check("Raven Shield: %d genuinely bool-typed properties do exist"
          % len(bools), len(bools) > 50)

    # a bool write must touch exactly one byte -- its own tag -- and be exactly
    # reversible, because the value lives in bit 7 of a byte that also encodes
    # the type.
    name, prop = bools[0]
    owner = next(p for p in pkgs.values()
                 if p.find_property(name, prop.path) is not None)
    before = owner.to_bytes()
    was = owner.get(name, prop.path)
    owner.set(name, prop.path, not was)
    after = owner.to_bytes()
    moved = [i for i in range(len(before)) if before[i] != after[i]]
    check("Raven Shield: flipping %s.%s changes exactly its own tag byte"
          % (name, prop.path),
          len(before) == len(after) and moved == [prop.offset]
          and owner.get(name, prop.path) is (not was), str(moved[:4]))
    owner.set(name, prop.path, was)
    check("Raven Shield: flipping it back restores the original bytes",
          owner.to_bytes() == before)

    # -- and now an actual apply, on a sandbox copy ------------------------
    tmp = tempfile.mkdtemp(prefix="tcpc-upkg-")
    try:
        root = sandbox_for(det, tmp)
        values = dict(profile.defaults())
        values.update(weapon_recoil="half", ammo_damage="x2",
                      weapon_magazines=4, menu_bars=True)
        stock = _rs3_packages(root)
        sizes = {f: os.path.getsize(os.path.join(root, "system", f))
                 for f in stock}

        result = engine.apply(root, profile, profile.effective(values))
        check("Raven Shield: package apply succeeded", result.ok,
              "; ".join(result.warnings[:2]))

        after = _rs3_packages(root)
        check("Raven Shield: every package is the same length as before",
              all(os.path.getsize(os.path.join(root, "system", f)) == n
                  for f, n in sizes.items()),
              str({f: os.path.getsize(os.path.join(root, "system", f))
                   for f, n in sizes.items()
                   if os.path.getsize(os.path.join(root, "system", f)) != n}))

        # recoil really halved, on a weapon the menu offers
        was = stock["R63rdWeapons.u"].get("NormalAssaultM4",
                                          "m_stAccuracyValues.fWeaponJump")
        now = after["R63rdWeapons.u"].get("NormalAssaultM4",
                                          "m_stAccuracyValues.fWeaponJump")
        check("Raven Shield: M4 muzzle climb halved (%.3f -> %.3f)" % (was, now),
              abs(now - was / 2) < 1e-3)

        # damage is on the ammunition
        was = stock["R6Weapons.u"].get("ammo556mmNATONormalFMJ", "m_iEnergy")
        now = after["R6Weapons.u"].get("ammo556mmNATONormalFMJ", "m_iEnergy")
        check("Raven Shield: 5.56 NATO energy doubled (%d -> %d)" % (was, now),
              now == was * 2)

        # ...and explosives share the field but are deliberately left alone
        held = [c for c in ("R6FragGrenade", "R6FlashBang", "R6ClaymoreUnit",
                            "R6BreachingChargeUnit", "R6RemoteChargeUnit")
                if stock["R6Weapons.u"].get(c, "m_iEnergy")
                != after["R6Weapons.u"].get(c, "m_iEnergy")]
        check("Raven Shield: grenades and charges keep their own energy",
              not held, str(held))

        # magazines are an addition, not a multiplication
        was = stock["R63rdWeapons.u"].get("NormalAssaultM4", "m_iNbOfClips")
        now = after["R63rdWeapons.u"].get("NormalAssaultM4", "m_iNbOfClips")
        check("Raven Shield: magazines %d -> %d is the stated +4" % (was, now),
              now == was + 4)

        # the menu bar moved the RIGHT way: less recoil is a HIGHER bar
        was = stock["R6Description.u"].get("R6DescAssaultM4", "m_ARecoilPercent[0]")
        now = after["R6Description.u"].get("R6DescAssaultM4", "m_ARecoilPercent[0]")
        check("Raven Shield: halved recoil raised the menu's recoil bar "
              "(%d -> %d)" % (was, now), now > was and now <= 100)
        was = stock["R6Description.u"].get("R6DescAssaultM4", "m_ADamagePercent[0]")
        now = after["R6Description.u"].get("R6DescAssaultM4", "m_ADamagePercent[0]")
        check("Raven Shield: doubled damage raised the menu's damage bar "
              "(%d -> %d)" % (was, now), now > was and now <= 100)
        check("Raven Shield: no stat bar was pushed past 100",
              all(after["R6Description.u"].get(e.name, "%s[%d]" % (bar, i)) <= 100
                  for e in after["R6Description.u"].classes() if e.size > 0
                  for bar in ("m_ADamagePercent", "m_ARecoilPercent",
                              "m_AAccuracyPercent", "m_ARecoveryPercent")
                  for i in range(3)
                  if after["R6Description.u"].find_property(
                      e.name, "%s[%d]" % (bar, i))))

        # nothing outside the property values moved: every differing byte must
        # belong to a four-byte value this tool meant to write.
        for f in ("R63rdWeapons.u", "R6Weapons.u"):
            a = stock[f].to_bytes()
            b = after[f].to_bytes()
            diff = [i for i in range(len(a)) if a[i] != b[i]]
            owned = set()
            for e in after[f].classes():
                if e.size <= 0:
                    continue
                try:
                    table = after[f].defaults(e.name)
                except upackage.PackageError:
                    continue
                for prop in table.values():
                    if prop.size == 4:
                        owned.update(range(prop.offset, prop.offset + 4))
            stray = [i for i in diff if i not in owned]
            check("Raven Shield: %s -- all %d changed bytes sit inside a "
                  "property value" % (f, len(diff)),
                  diff and not stray, "%d stray at %s" % (len(stray), stray[:4]))

        # the package is still loadable by the same reader, which is the only
        # cheap proxy for "the engine will still load it"
        check("Raven Shield: the edited packages still parse",
              all(len(p.classes()) == len(stock[f].classes())
                  for f, p in after.items()))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _safe_defaults(pkg, name):
    try:
        return pkg.defaults(name)
    except upackage.PackageError:
        return {}


class _N:
    is_class = False


def _same(value, stated):
    if not stated:
        return True
    try:
        if isinstance(value, bool):
            return str(value).lower() == stated.lower() or \
                stated in ("1", "0") and value == (stated == "1")
        if isinstance(value, int):
            return int(float(stated)) == value
        return abs(float(stated) - value) <= max(1e-4, abs(float(stated)) * 1e-5)
    except (TypeError, ValueError):
        return True


def test_rs3_modes(dets):
    r"""Raven Shield's game modes: the cut four, and the per-map mode lists.

    The interesting assertion is the last one. Every class name this profile
    writes into a map file is checked against `R6Game.u`'s own export table, so
    a typo here fails the suite rather than shipping a map that names a class
    the engine cannot resolve -- which is exactly the shipped bug the
    `fix_survival` option exists to correct.
    """
    det = next((d for d in dets if d.profile.id == "ravenshield"), None)
    if det is None:
        return
    print("\n[Raven Shield: game modes]")
    profile, root = det.profile, det.path
    exported = {e.name for e in
                upackage.Package.load(os.path.join(root, "system", "R6Game.u"))
                .classes() if e.size > 0}

    # every class the profile names must exist
    from tcpc.games import _rs3_modes
    named = {c for c, _cap in _rs3_modes.HUNT_MODES + _rs3_modes.STORY_MODES}
    named |= {spec[1].split(".", 1)[1] for spec in _rs3_modes.CUT_MODES}
    missing = sorted(n for n in named if n not in exported)
    check("Raven Shield: all %d game classes the profile names exist in "
          "R6Game.u" % len(named), not missing, str(missing))

    # and the cut ones really are unlisted by every shipped .mod
    listed = set()
    mods = os.path.join(root, "Mods")
    for f in os.listdir(mods) if os.path.isdir(mods) else []:
        if not f.lower().endswith(".mod"):
            continue
        with open(os.path.join(mods, f), encoding="latin-1") as fh:
            for line in fh:
                m = re.match(r'\s*m_szGameTypes\s*=\s*"?([A-Za-z_0-9]+)', line)
                if m:
                    listed.add(m.group(1))
    cut_tokens = {"RGM_DefendMode", "RGM_ReconMode", "RGM_SquadDeathmatch",
                  "RGM_SquadTeamDeathmatch"}
    check("Raven Shield: the four cut modes are listed by no shipped .mod",
          listed and not (cut_tokens & listed), str(sorted(cut_tokens & listed)))

    tmp = tempfile.mkdtemp(prefix="tcpc-modes-")
    try:
        sandbox = sandbox_for(det, tmp)
        maps = os.path.join(sandbox, "maps")
        if not os.path.isdir(maps):
            check("Raven Shield: map files reached the sandbox", False)
            return

        def bad_refs():
            out = []
            for f in sorted(os.listdir(maps)):
                if not f.lower().endswith(".ini"):
                    continue
                with open(os.path.join(maps, f), encoding="latin-1") as fh:
                    for line in fh:
                        m = re.search(r"(GameTypes|SkinsPerGameTypes)="
                                      r"\(package=R6Game,type=(\w+)", line)
                        if m and m.group(2) not in exported:
                            out.append((f, m.group(1), m.group(2)))
            return out

        def with_hunt():
            n = 0
            for f in os.listdir(maps):
                if not f.lower().endswith(".ini"):
                    continue
                with open(os.path.join(maps, f), encoding="latin-1") as fh:
                    if any("type=R6TerroristHuntGame," in ln for ln in fh):
                        n += 1
            return n

        before_bad, before_hunt = bad_refs(), with_hunt()
        check("Raven Shield: the shipped maps really do name a missing class "
              "(%d line(s))" % len(before_bad), len(before_bad) == 3,
              str(before_bad))

        values = dict(profile.defaults())
        values.update(cut_modes=True, map_modes="hunt", fix_survival=True)
        result = engine.apply(sandbox, profile, profile.effective(values))
        check("Raven Shield: modes apply succeeded", result.ok,
              "; ".join(result.warnings[:2]))

        check("Raven Shield: Terrorist Hunt reached every map (%d -> %d)"
              % (before_hunt, with_hunt()),
              with_hunt() > before_hunt
              and with_hunt() == len([f for f in os.listdir(maps)
                                      if f.lower().endswith(".ini")]))
        check("Raven Shield: no map now names a class R6Game.u does not export",
              not bad_refs(), str(bad_refs()))

        made = os.path.join(sandbox, "Mods", "Defend.game")
        check("Raven Shield: a .game descriptor was created", os.path.isfile(made))
        if os.path.isfile(made):
            doc = inifile.Ini.load(made)
            check("Raven Shield: it registers the cut class in both sections",
                  all(doc.get(s, "GameType") == "R6Game.R6DefendGame"
                      for s in _rs3_modes.GAME_SECTIONS))

        engine.revert(sandbox, profile)
        check("Raven Shield: revert puts the shipped typo back, byte for byte",
              bad_refs() == before_bad and with_hunt() == before_hunt)
        check("Raven Shield: revert removes the .game descriptors",
              not os.path.exists(made))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_sides(dets):
    r"""No option aimed at the enemy may reach the player's own people.

    Both Red Storm profiles got this wrong by scoping "enemy" to a FOLDER.
    Ghost Recon's `mp_enemies` option -- on by default, labelled "also apply
    to multiplayer and co-op enemies" -- pointed at
    `Actor\MP Actor Files\*\*.atr`, which is the player's own four MP classes,
    four per platoon; the real script-spawned enemies are `opposing_force_*`
    in the Actor root and were already covered. And in Sum of All Fears 49 of
    the 448 root actors carry a `<KitPath>`, which means they were equipped
    out of the player's kit folders: eleven support teams and a hostage.

    So the test is not "does the glob look right", it is: take every enemy
    option, plan it against the real installation, and assert that not one
    targeted file is friendly.
    """
    import re
    print("\n[Red Storm: enemy options must not reach friendly actors]")
    kitpath = re.compile(rb"<\s*KitPath\s*>\s*[^\s<]", re.I)
    for det in dets:
        profile = det.profile
        if profile.id not in ("ghost_recon", "soaf"):
            continue
        values = dict(profile.defaults())
        for key, value in (("enemy_skill", "sharp"), ("enemy_armour", "up"),
                           ("enemy_awareness", "up")):
            if profile.setting(key):
                values[key] = value
        plan = engine.plan(det.path, profile,
                           profile.build_edits(profile.effective(values)))
        base = os.path.join(det.path, profile.layout.base_mod.replace("/", os.sep))
        actors = [r for r in plan if r.lower().startswith("actor/")
                  and r.lower().endswith(".atr")]
        check("%s: enemy options reach %d actor files" % (profile.short,
                                                          len(actors)),
              len(actors) > 100)

        friendly = []
        for rel in actors:
            path = os.path.join(base, rel.replace("/", os.sep))
            try:
                with open(path, "rb") as fh:
                    if kitpath.search(fh.read()):
                        friendly.append(rel)
            except OSError:
                pass
        check("%s: none of them is an actor equipped from the player's kits"
              % profile.short, not friendly,
              "%d friendly: %s" % (len(friendly), friendly[:3]))

        under_mp = [r for r in plan if "mp actor files" in r.lower()]
        check("%s: the player's own multiplayer characters are untouched"
              % profile.short, not under_mp, str(under_mp[:3]))

        # and the negative: the friendly actors really are in the folder the
        # old glob swept, so this test would have failed before the fix.
        everything = engine.expand(engine.walk_rel(base), "Actor/*.atr")
        carried = [r for r in everything
                   if kitpath.search(open(os.path.join(base,
                      r.replace("/", os.sep)), "rb").read())]
        check("%s: %d of the %d root actors are friendly (0 is fine, it means "
              "the folder rule happened to hold here)"
              % (profile.short, len(carried), len(everything)),
              len(everything) > 100)


def test_graw_direction(dets):
    r"""`skill_shooting` runs backwards, and the game's own data proves it.

    This shipped inverted: "Elite" doubled the number and "Green" cut it,
    when in fact the campaign's elite units carry the LOWEST values. Rather
    than assert a constant, the test rebuilds the ladder from the compiled
    group manager and checks the profile scales in the same direction the
    game's own tiering does.
    """
    print("\n[GRAW: which way enemy marksmanship runs]")
    from tcpc import xmlbin
    from tcpc.games import _graw_enemies
    for det in dets:
        profile = det.profile
        if profile.id not in ("graw", "graw2"):
            continue
        twin = engine.compiled_twin(profile,
                                    "data/lib/managers/xml/group_manager.xml")
        with engine.open_bundles(det.path, profile) as bundles:
            root, _inc = xmlbin.loads(bundles.read(twin))

        by_soldier = {}

        def collect(node, soldier):
            if node.kind != xmlbin.ELEMENT:
                return
            if node.name == "soldier":
                soldier = node.get("name", soldier)
            if node.name == "var" and node.get("name") == "skill_shooting":
                by_soldier.setdefault(soldier, node.get("value"))
            for kid in node.kids:
                collect(kid, soldier)

        collect(root, None)
        check("%s: the compiled group manager declares %d shooting figures"
              % (profile.short, len(by_soldier)), len(by_soldier) > 20)
        if not by_soldier:
            continue

        best = min(by_soldier.values(), key=float)
        worst = max(by_soldier.values(), key=float)
        elite = sorted(k for k, v in by_soldier.items() if v == best)
        rabble = sorted(k for k, v in by_soldier.items() if v == worst)
        # The elite here are named: a boss, or special-forces leaders. The
        # worst are guerillas or the rank and file. If that ever stops being
        # true the direction below is no longer safe to assume.
        check("%s: the lowest figure (%s) belongs to elite units, the highest "
              "(%s) to the rank and file" % (profile.short, best, worst),
              float(best) < float(worst)
              and any(w in elite[0] for w in ("carlos", "sf_", "leader"))
              and not any(w in rabble[0] for w in ("carlos",)),
              "lowest=%s highest=%s" % (elite[:2], rabble[:2]))

        # ...so "sharper" must scale DOWN
        sharper = _graw_enemies.SKILL_SPREAD["elite"]
        greener = _graw_enemies.SKILL_SPREAD["green"]
        check("%s: 'Elite' scales the spread down (x%g) and 'Green' up (x%g)"
              % (profile.short, sharper, greener),
              sharper < 1.0 < greener)

        # and the options proven dead are shipped visibly disabled
        for key in ("enemy_precision",) + (("enemy_senses",)
                                           if profile.id == "graw2" else ()):
            setting = profile.setting(key)
            check("%s: %s is shipped disabled with a reason"
                  % (profile.short, key),
                  setting is not None and not setting.enabled
                  and len(setting.disabled_reason) > 40)
            values = dict(profile.defaults())
            values[key] = [c.value for c in setting.choices
                           if c.value != setting.default][0]
            note = "senses" if "senses" in key else "accuracy"
            live = [e for e in profile.build_edits(profile.effective(values))
                    if note in (e.note or "")]
            check("%s: and it really emits nothing" % profile.short, not live)


def test_npc_split(dets):
    r"""Ghost Recon's enemy-weapon split actually separates the two sides.

    The assertion that matters is about a SHARED gun. Eight of the thirteen
    guns enemy kits name are enemy-only, so a split that quietly did nothing
    would still look right on those. Five -- at4, dragunov, m16, rpk74, sa80
    -- are carried by both sides, and those are the whole reason the feature
    exists. The test tightens the player's weapons and loosens the enemy's in
    the same apply, then checks a shared gun came out different on each side.
    """
    import re
    det = next((d for d in dets if d.profile.id == "ghost_recon"), None)
    if det is None:
        return
    print("\n[Ghost Recon: the enemy gets its own weapons]")
    profile = det.profile
    from tcpc.games import _gr_npc

    stock_mod = os.path.join(det.path,
                             profile.layout.base_mod.replace("/", os.sep))
    kits = _gr_npc.enemy_kits(stock_mod)
    check("Ghost Recon: %d enemy kits found, naming %d guns"
          % (len(kits), len({g for gs in kits.values() for g in gs})),
          len(kits) > 20 and kits)
    check("Ghost Recon: the co-op and adversarial spawn kits are included",
          all(any(n in k.lower() for k in kits)
              for n in ("opposing_force_0", "default.kit")),
          str(sorted(k.rsplit("/", 1)[-1] for k in kits)[:4]))
    check("Ghost Recon: the two allied-exclusive kits are excluded",
          not any(k.rsplit("/", 1)[-1].lower() in _gr_npc.ALLIED_ONLY_KITS
                  for k in kits))

    def read(path, tag):
        with open(path, encoding="latin-1", errors="replace") as fh:
            m = re.search(r"<%s>\s*([\d.]+)\s*</%s>" % (tag, tag), fh.read())
        return float(m.group(1)) if m else None

    tmp = tempfile.mkdtemp(prefix="tcpc-npc-")
    try:
        root = os.path.join(tmp, "gr")
        for base, _d, names in os.walk(stock_mod):
            for n in names:
                if not n.lower().endswith((".kit", ".gun", ".atr", ".xml",
                                           ".mis")):
                    continue
                src = os.path.join(base, n)
                rel = os.path.relpath(src, det.path)
                dst = os.path.join(root, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
        exe = os.path.join(root, profile.layout.exe.replace("/", os.sep))
        os.makedirs(os.path.dirname(exe) or root, exist_ok=True)
        with open(exe, "wb") as fh:
            fh.write(b"stub")

        values = dict(profile.defaults())
        values.update(npc_weapons=True, npc_accuracy="loose", npc_recoil="double",
                      weapon_accuracy="tight", recoil="none", npc_mags=4)
        result = engine.apply(root, profile, profile.effective(values))
        check("Ghost Recon: the split applies with no warnings",
              result.ok and not result.warnings,
              "; ".join(result.warnings[:2]))

        mod = engine.mod_dir(root, profile)
        equip = os.path.join(mod, "Equip")
        copies = [f for f in os.listdir(equip) if f.endswith("_npc.gun")]
        check("Ghost Recon: %d enemy weapon copies written" % len(copies),
              len(copies) >= 10)

        # the case the feature exists for: a gun BOTH sides carry
        tag = "StationaryStandAccuracy"
        shared = "m16.gun"
        stock = read(os.path.join(stock_mod, "Equip", shared), tag)
        player = read(os.path.join(equip, shared), tag)
        enemy = read(os.path.join(equip, _gr_npc.npc_name(shared)), tag)
        check("Ghost Recon: %s is a gun both sides carry, and the two sides "
              "now differ (stock %s -> player %s, enemy %s)"
              % (shared, stock, player, enemy),
              None not in (stock, player, enemy)
              and player < stock < enemy)

        # the enemy's kit really points at the copy
        kit = os.path.join(equip, "ak47 only.kit")
        if os.path.isfile(kit):
            with open(kit, encoding="latin-1") as fh:
                text = fh.read()
            check("Ghost Recon: the enemy's kit names the copy",
                  "ak47_npc.gun" in text)
            check("Ghost Recon: and carries the extra magazines",
                  re.search(r"<MagazineCount>\s*6\s*</MagazineCount>", text))

        # nothing the player draws from was written into the mod
        player_kits = os.path.join(mod, "Kits")
        check("Ghost Recon: not one of the player's own kits was touched",
              not os.path.isdir(player_kits)
              or not any(f.lower().endswith(".kit")
                         for _b, _d, ns in os.walk(player_kits) for f in ns))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_soaf_npc_split(dets):
    r"""Sum of All Fears' split, which needs a mechanism Ghost Recon does not.

    Ghost Recon separates the sides by folder. This game has no enemy kit
    folder: 239 enemy placements wear `Kits\mercenaries\` kits and 176 wear
    `multi_NN` loadouts out of `Kits\team\`, which is also where the player's
    own loadouts live. So the borrowed ones are COPIED rather than shadowed
    and the missions are rewritten to name the copies.

    Two things therefore have to be true at once, and both are asserted: the
    player's `Kits\team\` must come through completely untouched, and no
    mission may be left naming a bare `multi_NN.kit` on an enemy.
    """
    import re
    det = next((d for d in dets if d.profile.id == "soaf"), None)
    if det is None:
        return
    print("\n[Sum of All Fears: the enemy gets its own weapons]")
    profile = det.profile
    from tcpc.games import _soaf_npc

    stock_mod = os.path.join(det.path,
                             profile.layout.base_mod.replace("/", os.sep))
    shadow, borrowed = _soaf_npc.enemy_kits(stock_mod)
    check("SOAF: %d enemy kits shadowed in place, %d borrowed loadouts copied"
          % (len(shadow), len(borrowed)), len(shadow) > 20 and len(borrowed) > 5)
    check("SOAF: every borrowed loadout is a team kit, every shadowed one is "
          "a mercenaries kit",
          all(k.startswith(_soaf_npc.TEAM) for k in borrowed)
          and all(k.startswith(_soaf_npc.MERC) for k in shadow))

    # the measurement the whole mechanism rests on
    enemy_named = _soaf_npc.enemy_mission_kits(stock_mod)
    allied = {"hrt_stealth.kit", "open_assault.kit", "cqb_assault.kit",
              "no_gun.kit"}
    check("SOAF: no allied-only kit is named by a non-allied actor",
          not (enemy_named & allied), str(sorted(enemy_named & allied)))

    tmp = tempfile.mkdtemp(prefix="tcpc-soafnpc-")
    try:
        root = os.path.join(tmp, "soaf")
        for base, _d, names in os.walk(stock_mod):
            for n in names:
                if not n.lower().endswith((".kit", ".gun", ".atr", ".xml",
                                           ".mis", ".gtf")):
                    continue
                src = os.path.join(base, n)
                dst = os.path.join(root, os.path.relpath(src, det.path))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
        exe = os.path.join(root, profile.layout.exe.replace("/", os.sep))
        os.makedirs(os.path.dirname(exe) or root, exist_ok=True)
        with open(exe, "wb") as fh:
            fh.write(b"stub")

        values = dict(profile.defaults())
        values.update(npc_weapons=True, npc_accuracy="loose", npc_recoil="double",
                      weapon_accuracy="tight", recoil="none", npc_mags=3)
        result = engine.apply(root, profile, profile.effective(values))
        check("SOAF: the split applies with no warnings",
              result.ok and not result.warnings,
              "; ".join(result.warnings[:2]))

        mod = engine.mod_dir(root, profile)

        def read(path, tag):
            with open(path, encoding="latin-1", errors="replace") as fh:
                m = re.search(r"<%s>\s*([\d.]+)\s*</%s>" % (tag, tag), fh.read())
            return float(m.group(1)) if m else None

        tag = "StationaryStandAccuracy"
        for shared in ("m16.gun", "dragunov.gun"):
            stock = read(os.path.join(stock_mod, "Equip", shared), tag)
            player = read(os.path.join(mod, "Equip", shared), tag)
            enemy = read(os.path.join(mod, "Equip",
                                      _soaf_npc.npc_name(shared)), tag)
            check("SOAF: %s is carried by both sides and they now differ "
                  "(stock %s -> player %s, enemy %s)"
                  % (shared, stock, player, enemy),
                  None not in (stock, player, enemy) and player < stock < enemy)

        # the player's loadout folder must be completely absent from the mod
        team = os.path.join(mod, _soaf_npc.TEAM.replace("/", os.sep))
        check("SOAF: not one of the player's team loadouts was written",
              not os.path.isdir(team) or not os.listdir(team),
              str(os.listdir(team)[:3] if os.path.isdir(team) else []))

        # and no mission may still send an enemy to a borrowed loadout
        missions = os.path.join(mod, "Mission")
        named = set()
        for n in os.listdir(missions) if os.path.isdir(missions) else []:
            if not n.lower().endswith(".mis"):
                continue
            with open(os.path.join(missions, n), encoding="latin-1",
                      errors="replace") as fh:
                named |= set(re.findall(r'Kit\s*=\s*"([^"]+)"', fh.read()))
        bare = sorted(k for k in named
                      if k.lower().startswith("multi_")
                      and not k.lower().endswith("_npc.kit"))
        check("SOAF: every borrowed loadout reference was rewritten",
              named and not bare, str(bare[:4]))
        check("SOAF: the allied kits are still named unchanged",
              allied & named, str(sorted(allied & named)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_lockdown_sides(dets):
    r"""Lockdown ships the split already done -- so prove it stays clean.

    This is the one game here that needed no `_npc` copies: 42 `e_*.gun`
    enemy weapons, each paired 1:1 with a player twin, zero enemy-only. The
    risk is therefore not "does the split work" but "does an enemy option
    leak", because the two sides sit in the SAME folder and differ only by a
    two-character prefix. So the test sets every enemy-side option, applies,
    and requires every single player weapon file to come back byte-identical.
    """
    det = next((d for d in dets if d.profile.id == "lockdown"), None)
    if det is None:
        return
    print("\n[Lockdown: the enemy half of the weapon model]")
    profile = det.profile
    src = os.path.join(det.path, "data", "equip")
    if not os.path.isdir(src):
        return
    guns = [f for f in os.listdir(src) if f.lower().endswith(".gun")]
    enemy = [f for f in guns if f.lower().startswith("e_")]
    player = [f for f in guns if not f.lower().startswith("e_")]
    check("Lockdown: %d enemy weapons, %d player weapons, and every enemy one "
          "has a player twin" % (len(enemy), len(player)),
          enemy and player
          and not {f[2:].lower() for f in enemy} - {f.lower() for f in player})

    tmp = tempfile.mkdtemp(prefix="tcpc-ldsides-")
    try:
        root = os.path.join(tmp, "ld")
        for rel in ("data/equip", "data/mission", "data/actor",
                    "data/options.xml"):
            s = os.path.join(det.path, rel.replace("/", os.sep))
            if os.path.isfile(s):
                d = os.path.join(root, rel.replace("/", os.sep))
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(s, d)
            elif os.path.isdir(s):
                for base, _d, names in os.walk(s):
                    for n in names:
                        p = os.path.join(base, n)
                        d = os.path.join(root, os.path.relpath(p, det.path))
                        os.makedirs(os.path.dirname(d), exist_ok=True)
                        shutil.copy2(p, d)
        exe = os.path.join(root, profile.layout.exe.replace("/", os.sep))
        os.makedirs(os.path.dirname(exe) or root, exist_ok=True)
        with open(exe, "wb") as fh:
            fh.write(b"stub")

        values = dict(profile.defaults())
        values.update(enemy_move_penalty="none", enemy_blind_fire="none",
                      enemy_recoil="none", enemy_magazines="x2",
                      enemy_range="x0.5", enemy_accuracy=60,
                      enemy_damage="x2")
        result = engine.apply(root, profile, profile.effective(values))
        check("Lockdown: the enemy options apply", result.ok,
              "; ".join(result.warnings[:2]))

        equip = os.path.join(root, "data", "equip")

        def same(name):
            with open(os.path.join(equip, name), "rb") as a, \
                    open(os.path.join(src, name), "rb") as b:
                return a.read() == b.read()

        leaked = [f for f in player if not same(f)]
        check("Lockdown: not one of the %d player weapons was touched"
              % len(player), not leaked, str(leaked[:4]))
        moved = [f for f in enemy if not same(f)]
        check("Lockdown: all %d enemy weapons were" % len(enemy),
              len(moved) == len(enemy), "%d changed" % len(moved))

        # ...and the reverse: a player-side option must not reach the enemy
        engine.revert(root, profile)
        values = dict(profile.defaults())
        values.update(recoil="none", magazines="x2", player_damage="x1.5")
        engine.apply(root, profile, profile.effective(values))
        crossed = [f for f in enemy if not same(f)]
        check("Lockdown: and a player-side option reaches no enemy weapon",
              not crossed, str(crossed[:4]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_mission_ai(dets):
    r"""Enemy behaviour scripted in the missions, and the bug that hid it.

    `apply_xml` used to decide whether an attribute was present by asking the
    FIRST matching element. Ghost Recon's `m07_river.mis` has seventeen
    `<Alertness>` steps of which three declare no `State`, and one of those
    three is first -- so the edit was reported absent and fourteen elements
    went unwritten, silently, in two of the twenty-nine missions. The check
    below would have caught it: it counts across the whole campaign rather
    than trusting one file.
    """
    import re
    print("\n[Red Storm: enemy behaviour in the mission plans]")
    for det in dets:
        profile = det.profile
        if profile.id not in ("ghost_recon", "soaf"):
            continue
        stock_mod = os.path.join(det.path,
                                 profile.layout.base_mod.replace("/", os.sep))
        missions = os.path.join(stock_mod, "Mission")
        if not os.path.isdir(missions):
            continue

        def states(folder):
            got, blank = {}, 0
            for n in os.listdir(folder):
                if not n.lower().endswith(".mis"):
                    continue
                with open(os.path.join(folder, n), encoding="latin-1",
                          errors="replace") as fh:
                    for tag in re.findall(r"<Alertness\b[^>]*>", fh.read()):
                        m = re.search(r'State\s*=\s*"(\d+)"', tag)
                        if m:
                            got[m.group(1)] = got.get(m.group(1), 0) + 1
                        else:
                            blank += 1
            return got, blank

        before, blank = states(missions)
        check("%s: the campaign declares %d alertness states (%d steps "
              "declare none)" % (profile.short, sum(before.values()), blank),
              sum(before.values()) > 20 and set(before) == {"1", "2"},
              str(before))

        tmp = tempfile.mkdtemp(prefix="tcpc-ai-")
        try:
            root = os.path.join(tmp, "g")
            for base, _d, names in os.walk(stock_mod):
                for n in names:
                    if not n.lower().endswith((".kit", ".gun", ".atr", ".xml",
                                               ".mis", ".gtf")):
                        continue
                    src = os.path.join(base, n)
                    dst = os.path.join(root, os.path.relpath(src, det.path))
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
            exe = os.path.join(root, profile.layout.exe.replace("/", os.sep))
            os.makedirs(os.path.dirname(exe) or root, exist_ok=True)
            with open(exe, "wb") as fh:
                fh.write(b"stub")

            values = dict(profile.defaults())
            values["enemy_alertness"] = "alert"
            if profile.setting("enemy_grenades"):
                values.update(enemy_grenades=False, enemy_speed="x1.5")
            result = engine.apply(root, profile, profile.effective(values))
            check("%s: the behaviour options apply with no warnings"
                  % profile.short, result.ok and not result.warnings,
                  "; ".join(result.warnings[:2]))

            after, after_blank = states(os.path.join(engine.mod_dir(root, profile),
                                                     "Mission"))
            check("%s: EVERY declared state became alert, in all missions "
                  "(%s -> %s)" % (profile.short, before, after),
                  after.get("1", 0) == 0
                  and after.get("2") == sum(before.values()))
            check("%s: the steps that declare no state were left alone"
                  % profile.short, after_blank == blank)

            if profile.setting("enemy_grenades"):
                mod = engine.mod_dir(root, profile)
                avail = set()
                for n in os.listdir(os.path.join(mod, "Mission")):
                    if not n.lower().endswith(".mis"):
                        continue
                    with open(os.path.join(mod, "Mission", n),
                              encoding="latin-1", errors="replace") as fh:
                        avail |= set(re.findall(
                            r'<Grenades\b[^>]*Available\s*=\s*"(\d+)"', fh.read()))
                check("%s: enemy grenades really switched off" % profile.short,
                      avail == {"0"}, str(sorted(avail)))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def test_graw_sides(dets):
    r"""Advanced Warfighter ships its own player/AI split; prove we use it.

    Every weapon is declared TWICE in the same file -- `scar_heavy` and
    `scar_heavy_3rd` -- each with a complete `weapon_data` stats block, and
    the inventory extension appends `_3rd` for any unit that is not
    `player_controlled`. Shipped values are identical, which is why nobody
    noticed. The test is that a one-sided option moves exactly one of the two.
    """
    from tcpc.bundle import BundleSet
    from tcpc import xmlbin
    print("\n[Advanced Warfighter: the player/AI split it already ships]")
    for det in dets:
        p = det.profile
        if p.delivery != "overlay":
            continue
        tmp = tempfile.mkdtemp(prefix="tcpc-side-")
        try:
            root = os.path.join(tmp, p.id)
            for sig in p.layout.signature:
                dest = os.path.join(root, sig.replace("/", os.sep))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                if not sig.endswith(".bundle"):
                    with open(dest, "wb") as fh:
                        fh.write(b"stub")
            entries, probe = {}, None
            with BundleSet(os.path.join(det.path,
                                        p.layout.bundles_dir)) as bs:
                for rel in bs.find("data/units/weapons/*.xml"):
                    entries[rel] = bs.read(rel)
                    twin = engine.compiled_twin(p, rel)
                    if twin and twin in bs:
                        entries[twin] = bs.read(twin)
                        node, _inc = xmlbin.loads(entries[twin])
                        names = [u.get("name") for u in
                                 xmlbin.select(node, "unit")]
                        if (probe is None
                                and any(n and n.endswith("_3rd") for n in names)
                                and xmlbin.select(
                                    node, "unit[name!=*_3rd]/stats/"
                                          "var[name=spread_normal]")):
                            probe = twin
            write_bundle(os.path.join(root, "Bundles", "quick.bundle"), entries)
            exe = os.path.join(root, p.layout.exe.replace("/", os.sep))
            os.makedirs(os.path.dirname(exe) or root, exist_ok=True)
            with open(exe, "wb") as fh:
                fh.write(b"stub")
            if not check("%s: a weapon declaring both sides was found"
                         % p.short, probe is not None):
                continue

            def sides():
                loose = os.path.join(root, probe.replace("/", os.sep))
                raw = (open(loose, "rb").read() if os.path.isfile(loose)
                       else entries[probe])
                node, _inc = xmlbin.loads(raw)
                pick = lambda sel: [n.get("value") for n in
                                    xmlbin.select(node, sel)]
                return (pick("unit[name!=*_3rd]/stats/var[name=spread_normal]"),
                        pick("unit[name=*_3rd]/stats/var[name=spread_normal]"))

            stock_player, stock_ai = sides()
            check("%s: the two sides ship identical spread (%s vs %s)"
                  % (p.short, stock_player, stock_ai),
                  stock_player and stock_player == stock_ai)

            for side, moves, holds in (("player", 0, 1), ("ai", 1, 0)):
                for junk in ("Data", "data", ".tcpc-backup"):
                    shutil.rmtree(os.path.join(root, junk), ignore_errors=True)
                values = dict(p.defaults())
                values.update(weapon_side=side, weapon_spread="tight",
                              weapon_damage="x2")
                result = engine.apply(root, p, p.effective(values))
                now = sides()
                changed = now[moves] != (stock_player, stock_ai)[moves]
                unchanged = now[holds] == (stock_player, stock_ai)[holds]
                check("%s: weapon_side=%s moves only that side (%s -> %s)"
                      % (p.short, side, stock_player, now),
                      result.ok and changed and unchanged,
                      "; ".join(result.warnings[:2]))

                # damage is the newest option on that scope and has its own
                # value range (1-2.5 for carried arms, 10-15 for the mounted
                # guns), so it is checked rather than assumed to follow.
                def dmg(sel):
                    loose = os.path.join(root, probe.replace("/", os.sep))
                    raw = (open(loose, "rb").read() if os.path.isfile(loose)
                           else entries[probe])
                    node, _i = xmlbin.loads(raw)
                    return [n.get("value") for n in xmlbin.select(node, sel)]
                mine = dmg("unit[name!=*_3rd]/stats/var[name=damage]")
                theirs = dmg("unit[name=*_3rd]/stats/var[name=damage]")
                if mine and theirs:
                    check("%s: and weapon damage split with it (yours %s, "
                          "theirs %s)" % (p.short, mine, theirs),
                          (mine != theirs)
                          and (float(mine[0]) > float(theirs[0])
                               if side == "player" else
                               float(theirs[0]) > float(mine[0])))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def test_rs3_expansions(dets):
    r"""Gold's two expansions must be retuned with the base game, and only them.

    Athena Sword and Iron Wrath ship their own weapons, ammunition and menu
    bars in packages of their own. Every option here used to stop at
    `system\`, so a person who turned an option on got it on the base game and
    silently not on the 31 expansion weapons or the three expansion ammunition
    pairs.

    The second half is the one that matters more. The tempting spelling of the
    fix is a glob over `Mods\*\System\*Weapons.u`, and `Mods\` is also where a
    person's OWN mods live -- this machine has SupplyDrop, which carries
    fourteen weapon packages. Retuning somebody else's mod without being asked
    would be a worse bug than the one being fixed, so it is asserted against.
    """
    det = next((d for d in dets if d.profile.id == "ravenshield"), None)
    if det is None:
        return
    print("\n[Raven Shield: the Gold expansions]")
    profile = det.profile
    from tcpc.games import _rs3_ammo

    OFFICIAL = ("Mods/AthenaSword/System/ASWeapons.u",
                "Mods/AthenaSword/System/ASDescription.u",
                "Mods/IronWrath/System/MP2Weapons.u",
                "Mods/IronWrath/System/MP23rdWeapons.u",
                "Mods/IronWrath/System/MP2Description.u")

    values = dict(_max_values(profile))
    values["menu_bars"] = True                 # a default-ON bool; max turns it off
    values["ammo_character"] = "realistic"
    selects = {e.select.replace("\\", "/") for e in
               profile.build_edits(profile.effective(values))}
    missing = [f for f in OFFICIAL if f not in selects]
    check("Raven Shield: all %d expansion packages are named by the edits"
          % len(OFFICIAL), not missing, str(missing))

    # -- and nothing INSIDE anybody else's mod folder --------------------
    # Files written directly into `Mods\` are ours: the cut-mode option ships
    # `Mods\Defend.game` and three more, which is how OpenRVS lists a mode.
    # What must never be touched is the CONTENT of a folder somebody else
    # installed, so the check is on the folder, not on the prefix.
    MINE = ("athenasword", "ironwrath")
    stray = sorted(f for f in selects
                   if f.lower().startswith("mods/") and "/" in f[5:]
                   and f.split("/")[1].lower() not in MINE)
    check("Raven Shield: nothing inside a third-party mod folder is selected",
          not stray, str(stray[:4]))
    others = sorted(d for d in os.listdir(os.path.join(det.path, "Mods"))
                    if os.path.isdir(os.path.join(det.path, "Mods", d))
                    and d.lower() not in MINE)
    check("Raven Shield: %d third-party mod folder(s) installed here are "
          "left alone (%s)" % (len(others), ", ".join(others) or "none"),
          not any(f.lower().startswith("mods/" + d.lower() + "/")
                  for d in others for f in selects), str(others))

    tmp = tempfile.mkdtemp(prefix="tcpc-gold-")
    try:
        root = sandbox_for(det, tmp)
        copied = [f for f in OFFICIAL
                  if os.path.exists(os.path.join(root, f.replace("/", os.sep)))]
        if len(copied) != len(OFFICIAL):
            check("Raven Shield: the expansion packages reached the sandbox",
                  False, str(sorted(set(OFFICIAL) - set(copied))))
            return
        sizes = {f: os.path.getsize(os.path.join(root, f.replace("/", os.sep)))
                 for f in OFFICIAL}

        result = engine.apply(root, profile, profile.effective(values))
        check("Raven Shield: the expansion apply succeeded", result.ok,
              "; ".join(result.warnings[:2]))
        written = {c.rel.replace("\\", "/") for c in result.changes}
        unwritten = [f for f in OFFICIAL if f not in written]
        check("Raven Shield: all %d expansion packages were written"
              % len(OFFICIAL), not unwritten, str(unwritten))

        grew = [f for f in OFFICIAL
                if os.path.getsize(os.path.join(root, f.replace("/", os.sep)))
                != sizes[f]]
        check("Raven Shield: no expansion package changed length",
              not grew, str(grew))

        # -- and the three expansion ammunition pairs really moved --------
        # A SECOND apply, with only this one option off default. The max set
        # above also turns `ammo_damage` up, which scales `m_iEnergy` as well,
        # so the arithmetic to check against would be the product of two
        # options rather than the one being tested. An in-place apply rebuilds
        # from pristine, so running it twice is safe -- and exercises that.
        only = dict(profile.defaults())
        only["ammo_character"] = "realistic"
        second = engine.apply(root, profile, profile.effective(only))
        check("Raven Shield: a second apply rebuilds from pristine", second.ok,
              "; ".join(second.warnings[:2]))
        jhp = _rs3_ammo.CHARACTER["realistic"]["jhp"]
        moved, wrong = [], []
        for rel, cls in (("Mods/AthenaSword/System/ASWeapons.u",
                          "ammo9x39mmSP6NormalJHP"),
                         ("Mods/IronWrath/System/MP2Weapons.u",
                          "ammo46x30mmNormalJHP"),
                         ("Mods/IronWrath/System/MP2Weapons.u",
                          "ammo46x30mmSubsonicJHP")):
            was = upackage.Package.load(
                os.path.join(det.path, rel.replace("/", os.sep)))
            now = upackage.Package.load(
                os.path.join(root, rel.replace("/", os.sep)))
            want = int(was.get(cls, "m_iEnergy") * jhp["energy"])
            got = now.get(cls, "m_iEnergy")
            if got == want and abs(now.get(cls, "m_fKillStunTransfer")
                                   - jhp["stun"]) < 1e-6:
                moved.append(cls)
            else:
                wrong.append("%s %s->%s want %s" % (cls, was.get(cls, "m_iEnergy"),
                                                    got, want))
        check("Raven Shield: the %d expansion hollow-point classes are "
              "retuned" % len(moved), len(moved) == 3, str(wrong))


        mismatched = [c for c in result.changes if c.status == "stock-mismatch"]
        check("Raven Shield: every expansion edit found the stock value it "
              "expected", not mismatched,
              str([(c.rel, c.what) for c in mismatched[:3]]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_rs3_ammo_character(dets):
    r"""FMJ and JHP ship undifferentiated; prove the option differentiates them.

    The first half of this test is the justification for the option existing
    at all, so it asserts the complaint rather than assuming it: across every
    calibre that offers both rounds, the damage figure is the SAME NUMBER.
    If a future build of the game ever stops being true, the option's premise
    is gone and this fails loudly.
    """
    det = next((d for d in dets if d.profile.id == "ravenshield"), None)
    if det is None:
        return
    print("\n[Raven Shield: ball versus hollow point]")
    profile = det.profile
    from tcpc.games import _rs3_ammo

    stock = upackage.Package.load(os.path.join(det.path, "system",
                                               "R6Weapons.u"))
    pairs = []
    for e in stock.classes():
        if e.size <= 0 or not e.name.endswith("FMJ"):
            continue
        twin = e.name[:-3] + "JHP"
        if stock.export(twin):
            pairs.append((e.name, twin))
    check("Raven Shield: %d calibres ship both a ball and a hollow-point round"
          % len(pairs), len(pairs) > 25)

    same_energy = [f for f, j in pairs
                   if stock.get(f, "m_iEnergy") == stock.get(j, "m_iEnergy")]
    # 32 of 33, not all 33: ammo545mm7N6Subsonic is the single calibre where
    # the hollow point really does carry more energy (+12%). Asserting the
    # exact count rather than "all" keeps the option's stated premise honest.
    check("Raven Shield: and the damage figure is identical on %d of the %d "
          "-- which is the whole reason for the option"
          % (len(same_energy), len(pairs)),
          len(same_energy) == len(pairs) - 1,
          "%d differ, expected exactly 1" % (len(pairs) - len(same_energy)))
    # m_iPenetrationFactor is a DIVISOR: a round's budget is roughly
    # energy / factor. The hollow point's 4 against ball's inherited 1 means
    # BALL gets four times the budget and goes through doors the hollow point
    # bounces off. That is correct, not backwards -- an earlier version of
    # this suite asserted the opposite and the option built on it was harmful.
    # Asserted here so nobody "fixes" it again.
    base = stock.get("R6Bullet", "m_iPenetrationFactor")
    divisors = [j for _f, j in pairs
                if (stock.get(j, "m_iPenetrationFactor") or 0) > (base or 0)]
    check("Raven Shield: hollow points carry a higher penetration DIVISOR on "
          "all %d, so ball out-penetrates them %gx"
          % (len(divisors),
             (stock.get(pairs[0][1], "m_iPenetrationFactor") or 1) / (base or 1)),
          len(divisors) == len(pairs))
    typed = [f for f, _j in pairs
             if stock.find_property(f, "m_szBulletType") is not None]
    check("Raven Shield: and all %d ball rounds override the bullet type the "
          "base class defaults to JHP" % len(typed), len(typed) == len(pairs))

    tmp = tempfile.mkdtemp(prefix="tcpc-ammo-")
    try:
        root = sandbox_for(det, tmp)
        values = dict(profile.defaults())
        values.update(ammo_character="realistic")
        result = engine.apply(root, profile, profile.effective(values))
        check("Raven Shield: the ammunition option applies", result.ok,
              "; ".join(result.warnings[:2]))

        after = upackage.Package.load(os.path.join(root, "system",
                                                   "R6Weapons.u"))
        harder = softer = stops = 0
        for f, j in pairs:
            if after.get(j, "m_iEnergy") > stock.get(j, "m_iEnergy"):
                harder += 1
            if after.get(f, "m_iEnergy") < stock.get(f, "m_iEnergy"):
                softer += 1
            if after.get(j, "m_fKillStunTransfer") \
                    > after.get(f, "m_fKillStunTransfer"):
                stops += 1
        check("Raven Shield: every hollow point now hits harder (%d/%d) and "
              "every ball round softer (%d/%d)"
              % (harder, len(pairs), softer, len(pairs)),
              harder == len(pairs) and softer == len(pairs))
        # The point of this one. An earlier version of the option rewrote the
        # penetration field in both directions and made ball ammunition WORSE
        # at the one thing it is already best at. It must not be touched.
        moved = [j for _f, j in pairs
                 if after.get(j, "m_iPenetrationFactor")
                 != stock.get(j, "m_iPenetrationFactor")]
        check("Raven Shield: and not one penetration figure was touched",
              not moved and after.get("R6Bullet", "m_iPenetrationFactor")
              == stock.get("R6Bullet", "m_iPenetrationFactor"),
              "%d moved" % len(moved))
        check("Raven Shield: hollow point staggers harder on all %d -- "
              "including the one pair that ships it backwards" % stops,
              stops == len(pairs))
        check("Raven Shield: ball reaches further than hollow point everywhere",
              all(after.get(f, "m_fRange") > after.get(j, "m_fRange")
                  for f, j in pairs))

        # the package must still be the same length and still parse
        a = os.path.getsize(os.path.join(det.path, "system", "R6Weapons.u"))
        b = os.path.getsize(os.path.join(root, "system", "R6Weapons.u"))
        check("Raven Shield: the package is unchanged in length (%d bytes)" % b,
              a == b)

        check("Raven Shield: ball still declares itself FMJ afterwards, so it "
              "still passes through a body",
              all(after.find_property(f, "m_szBulletType") is not None
                  for f, _j in pairs))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_rse_damage(dets):
    r"""Weapon damage, and the armour factors base Ghost Recon leaves out.

    Damage is built from the weapon's own kill energy, `K1*v + K2*v*v`, and
    the hit-location factor divides into it. Energy is LINEAR in the two K's,
    so scaling both by one factor scales energy by exactly that and leaves
    every ballistic curve's shape alone -- which is why the velocity trio is
    not touched. The test asserts that rather than describing it.

    The armour half is a shipped omission: base Ghost Recon's combat model
    has 8 entries where both expansions have 12, and the missing four are the
    armoured-chest factors. A missing factor reads as zero and a zero factor
    is a certain kill, so armour does nothing on the base campaign.
    """
    import re
    print("\n[Red Storm: weapon damage and the missing armour factors]")

    def elements(raw):
        return dict(re.findall(r"<(\w+)>([^<]*)</\1>", raw.decode("latin-1")))

    for det in dets:
        profile = det.profile
        if profile.id not in ("ghost_recon", "soaf"):
            continue
        stock_mod = os.path.join(det.path,
                                 profile.layout.base_mod.replace("/", os.sep))
        equip = os.path.join(stock_mod, "Equip")
        guns = [f for f in os.listdir(equip) if f.lower().endswith(".gun")]
        both = 0
        for g in guns:
            with open(os.path.join(equip, g), encoding="latin-1",
                      errors="replace") as fh:
                text = fh.read()
            if all(("<%s>" % k) in text for k in _rse_kill_coeffs()):
                both += 1
        check("%s: all %d weapons carry both kill coefficients"
              % (profile.short, both), both == len(guns))

        tmp = tempfile.mkdtemp(prefix="tcpc-dmg-")
        try:
            root = os.path.join(tmp, "g")
            for base, _d, names in os.walk(stock_mod):
                for n in names:
                    if not n.lower().endswith((".kit", ".gun", ".atr", ".xml",
                                               ".mis", ".gtf")):
                        continue
                    src = os.path.join(base, n)
                    dst = os.path.join(root, os.path.relpath(src, det.path))
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
            exe = os.path.join(root, profile.layout.exe.replace("/", os.sep))
            os.makedirs(os.path.dirname(exe) or root, exist_ok=True)
            with open(exe, "wb") as fh:
                fh.write(b"stub")

            values = dict(profile.defaults())
            values["weapon_damage"] = "x2"
            result = engine.apply(root, profile, profile.effective(values))
            check("%s: the damage option applies" % profile.short, result.ok,
                  "; ".join(result.warnings[:2]))
            mod = engine.mod_dir(root, profile)
            probe = sorted(guns)[0]

            def read(path, tag):
                with open(path, encoding="latin-1", errors="replace") as fh:
                    m = re.search(r"<%s>\s*([-\d.eE]+)\s*</%s>" % (tag, tag),
                                  fh.read())
                return float(m.group(1)) if m else None

            a = os.path.join(equip, probe)
            b = os.path.join(mod, "Equip", probe)
            doubled = all(
                abs(read(b, k) - 2 * read(a, k)) < 1e-6 for k in _rse_kill_coeffs())
            untouched = all(read(b, v) == read(a, v) for v in
                            ("VelocityCoefficient0", "VelocityCoefficient1",
                             "VelocityCoefficient2"))
            check("%s: both kill coefficients doubled on %s"
                  % (profile.short, probe), doubled)
            check("%s: and the velocity coefficients were left alone"
                  % profile.short, untouched)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # -- the armour omission, Ghost Recon only ---------------------------
    det = next((d for d in dets if d.profile.id == "ghost_recon"), None)
    if det is None:
        return
    from tcpc.games import _gr_npc
    base_mod = os.path.join(det.path,
                            det.profile.layout.base_mod.replace("/", os.sep))
    with open(os.path.join(base_mod, "Equip", "CmbtModl.xml"), "rb") as fh:
        stock = elements(fh.read())
    check("Ghost Recon: the base combat model has %d entries and no armour "
          "factors" % len(stock),
          len(stock) == 8 and not any("Armored" in k for k in stock))

    expansion = os.path.join(det.path, "Mods", "Mp1", "Equip", "CmbtModl.xml")
    if os.path.isfile(expansion):
        with open(expansion, "rb") as fh:
            theirs = elements(fh.read())
        made = _gr_npc.armour_edits({"armour_works": True}, base_mod)
        check("Ghost Recon: an expansion ships 12 entries, so the numbers are "
              "not invented", len(theirs) == 12)
        check("Ghost Recon: the generated model matches the expansion's "
              "values exactly",
              made and elements(made[0].data) == theirs)
    check("Ghost Recon: and it is not emitted unless asked",
          not _gr_npc.armour_edits({"armour_works": False}, base_mod))


def _rse_kill_coeffs():
    from tcpc.games._rse import KILL_COEFFS
    return KILL_COEFFS


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
    test_created_files()
    if dets:
        test_roundtrip(dets)
        test_art(dets)
        test_rsb(dets)
        test_bundle(dets)
        test_apply_revert(dets)
        test_overlay(dets)
        test_graw_enemies(dets)
        test_packages(dets)
        test_rs3_modes(dets)
        test_rs3_expansions(dets)
        test_rs3_ammo_character(dets)
        test_sides(dets)
        test_graw_direction(dets)
        test_npc_split(dets)
        test_soaf_npc_split(dets)
        test_lockdown_sides(dets)
        test_mission_ai(dets)
        test_rse_damage(dets)
        test_graw_sides(dets)
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

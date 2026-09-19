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

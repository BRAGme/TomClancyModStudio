r"""Read a Raven Shield installation and answer the questions a script mod asks.

    python tools\rs3_probe.py "D:\SteamLibrary\steamapps\common\Rainbow Six 3 Gold"

Written for `mods\TarkovRvS`, which needs three facts that are not in any
document and are not guessable:

  1. **What are the pawn classes called?** The player's three are written down
     in `Mods\RavenShield.mod`. The terrorists' are not -- they are named in
     the AI templates, and a mod that subclasses the wrong one does not
     compile.
  2. **Which property on a pawn means posture?** Zone resolution is geometric
     and a prone man breaks it; the fix needs whatever Raven Shield calls
     lying down.
  3. **Is there an armour property reachable from script at all?** Tarkov's
     identity is penetration against armour class, and the Raven Shield
     modding community's position is that armour is handled in native code. If
     any of it is a class default, it is reachable; if none of it is, that is
     worth knowing before building against it.

It reads. It never opens a game file for writing, and it has no arguments that
could. Everything it prints comes out of `tcpc.upackage`, the same Unreal
Engine 2 package reader the mod manager uses to patch weapon statistics, so
anything this tool can see is something the manager could also edit.

    --pawns              the pawn class tree, and which ones templates spawn
    --props CLASS        every default property of one class, with offsets
    --classes [PATTERN]  class names across every package
    --grep PATTERN       properties whose name matches, across pawn classes
    --ammo-of CLASS      which round a weapon class actually fires
"""

from __future__ import annotations

import argparse
import fnmatch
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tcpc.upackage import Package, PackageError      # noqa: E402

#: Packages worth opening, in the order a reader would want them. Expansion
#: packages are named one by one rather than globbed over `Mods\`, for the
#: same reason the mod manager does it: `Mods\` is where a person's OWN mods
#: live, and walking into those would report somebody else's classes as if
#: they were the game's.
PACKAGES = (
    "system/R6Characters.u",
    "system/R6Engine.u",
    "system/R6Game.u",
    "system/Engine.u",
    "system/R6Weapons.u",
    "system/R63rdWeapons.u",
    "Mods/AthenaSword/System/ASCharacters.u",
    "Mods/IronWrath/System/MP2Characters.u",
)

#: A class is pawn-ish if its name or its parent's name says so. Done by name
#: because the export table records only the immediate parent, so walking to
#: the real root would mean resolving imports across packages -- and the names
#: in this game are descriptive enough that it is not worth it.
PAWNISH = re.compile(r"pawn|rainbow|terro|hostage|character|civil|operative",
                     re.I)

#: `NNN, Package.Class` -- how a template weights a pool entry.
TPT_ENTRY = re.compile(r"^\s*\d+\s*,\s*([A-Za-z0-9_]+\.[A-Za-z0-9_]+)\s*$")


def open_packages(root, only=None):
    """Every package that is there, skipping the ones that are not."""
    out = []
    for rel in (only or PACKAGES):
        path = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.exists(path):
            continue
        try:
            out.append((rel, Package.load(path)))
        except PackageError as exc:
            print("  !! %s: %s" % (rel, exc))
    return out


def value_of(pkg, cls, prop):
    """A printable value, or the property's kind when it is not a scalar."""
    got = pkg.get(cls, prop.path)
    if got is not None:
        return got
    if prop.kind == "object":
        name = pkg.object_name(cls, prop.path)
        if name:
            return "-> " + name
    return "(%s)" % prop.kind


# ---------------------------------------------------------------------------
# the three questions
# ---------------------------------------------------------------------------

def cmd_pawns(root):
    print("\n=== pawn classes, by package ===")
    found = {}
    for rel, pkg in open_packages(root):
        hits = [e for e in pkg.classes()
                if PAWNISH.search(e.name) or PAWNISH.search(e.super_name or "")]
        if not hits:
            continue
        print("\n%s  (%d of %d classes)" % (rel, len(hits), len(pkg.classes())))
        for e in sorted(hits, key=lambda x: x.name.lower()):
            print("  %-34s : %s" % (e.name, e.super_name or "?"))
            found[e.name] = rel
    if not found:
        print("  none -- is that the game folder?")

    print("\n=== pawn classes the AI templates actually spawn ===")
    print("These are the ones to subclass for enemies. The count is how many")
    print("template files name it, which is a fair proxy for how much of the")
    print("game you change by replacing it.\n")
    tally, where = {}, {}
    pattern = os.path.join(root, "template", "*.tp[th]")
    for path in sorted(glob.glob(pattern)):
        try:
            with open(path, "r", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        for line in text.splitlines():
            m = TPT_ENTRY.match(line)
            if not m:
                continue
            ref = m.group(1)
            # A template's pools hold weapons and grenades too; only the
            # entries that name something pawn-ish are bodies.
            if not PAWNISH.search(ref.split(".")[-1]):
                continue
            tally[ref] = tally.get(ref, 0) + 1
            where.setdefault(ref, os.path.basename(path))
    if not tally:
        print("  no template\\*.tpt pawn entries found.")
    for ref, n in sorted(tally.items(), key=lambda kv: -kv[1]):
        print("  %-44s %4d templates   e.g. %s" % (ref, n, where[ref]))


def cmd_grep(root, pattern):
    print("\n=== properties matching %r on pawn-ish classes ===" % pattern)
    rx = re.compile(pattern, re.I)
    any_hit = False
    for rel, pkg in open_packages(root):
        for e in pkg.classes():
            if not (PAWNISH.search(e.name) or PAWNISH.search(e.super_name or "")):
                continue
            try:
                table = pkg.defaults(e.name)
            except PackageError:
                continue
            paths = sorted({p.path for p in table.values() if rx.search(p.path)})
            if not paths:
                continue
            any_hit = True
            print("\n  %s  %s" % (rel, e.name))
            for path in paths:
                prop = table[path]
                print("    %-40s %-7s @0x%06x = %s"
                      % (path, prop.kind, prop.offset,
                         value_of(pkg, e.name, prop)))
    if not any_hit:
        print("\n  nothing. Either no class AUTHORS such a property -- Unreal")
        print("  only serialises a default that differs from its parent's, so")
        print("  an inherited value is invisible here -- or it does not exist.")
        print("  Check the parent classes named by --pawns before concluding")
        print("  the second.")


def cmd_props(root, class_name):
    print("\n=== every default property of %s ===" % class_name)
    for rel, pkg in open_packages(root):
        try:
            table = pkg.defaults(class_name)
        except PackageError:
            continue
        e = pkg.export(class_name)
        print("\n%s  (export %d, parent %s)"
              % (rel, e.index, e.super_name or "?"))
        for path in sorted({p.path for p in table.values()}):
            prop = table[path]
            print("  %-44s %-7s @0x%06x = %s"
                  % (path, prop.kind, prop.offset,
                     value_of(pkg, class_name, prop)))
        return
    print("  not found in any package this tool opens. Try --classes '*%s*'."
          % class_name)


def cmd_classes(root, pattern):
    print("\n=== classes matching %r ===" % pattern)
    for rel, pkg in open_packages(root):
        hits = sorted(e.name for e in pkg.classes()
                      if fnmatch.fnmatch(e.name.lower(), pattern.lower()))
        if hits:
            print("\n%s" % rel)
            for name in hits:
                print("  %s" % name)


def cmd_ammo_of(root, class_name):
    """Which round a weapon fires -- an ObjectProperty, so it has to be
    followed rather than read."""
    print("\n=== the round %s fires ===" % class_name)
    for rel, pkg in open_packages(root):
        try:
            table = pkg.defaults(class_name)
        except PackageError:
            continue
        for path in sorted({p.path for p in table.values()}):
            if not re.search(r"bullet|ammo|clip|cartridge", path, re.I):
                continue
            name = pkg.object_name(class_name, path)
            print("  %-40s -> %s" % (path, name or pkg.get(class_name, path)))
        return
    print("  not found.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("game", help="the Rainbow Six 3 folder")
    ap.add_argument("--pawns", action="store_true")
    ap.add_argument("--props", metavar="CLASS")
    ap.add_argument("--classes", metavar="PATTERN")
    ap.add_argument("--grep", metavar="PATTERN")
    ap.add_argument("--ammo-of", metavar="CLASS", dest="ammo_of")
    args = ap.parse_args(argv)

    root = args.game
    if not os.path.isdir(root):
        ap.error("no such folder: %s" % root)

    did = False
    if args.pawns:
        cmd_pawns(root); did = True
    if args.props:
        cmd_props(root, args.props); did = True
    if args.classes:
        cmd_classes(root, args.classes); did = True
    if args.grep:
        cmd_grep(root, args.grep); did = True
    if args.ammo_of:
        cmd_ammo_of(root, args.ammo_of); did = True

    if not did:
        # No flags: answer the three questions the mod needs, in order.
        cmd_pawns(root)
        cmd_grep(root, r"armor|armour|health|protect|damage|resist")
        cmd_grep(root, r"prone|crouch|posture|stance|lying")
        print("\n--- what to do with this ---")
        print("1. Put the terrorist pawn class the templates spawn into")
        print("   mods\\TarkovRvS\\Classes\\TarkovTerrorist.uc.template and")
        print("   rename it to .uc.")
        print("2. Put the posture property into TarkovZones.IsProne().")
        print("3. If an armour property showed up, it is reachable from")
        print("   script and Tarkov-style armour classes are back on the")
        print("   table. If nothing did, armour is native and that part of")
        print("   the mod stays out.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

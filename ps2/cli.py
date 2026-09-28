"""Command line for the same engine the window drives.

    python ModStudio.py --cli games   [game]      -- no disc needed
    python ModStudio.py --cli scan    [folder]
    python ModStudio.py --cli info    <iso>
    python ModStudio.py --cli list    <iso>
    python ModStudio.py --cli plan    <iso> [--set key=value ...] [--preset NAME]
    python ModStudio.py --cli apply   <iso> [--set key=value ...] [--preset NAME]
    python ModStudio.py --cli revert  <iso>
    python ModStudio.py --cli cheat   <iso> [--set ...] [--out FILE]
    python ModStudio.py --cli art     <iso> --out DIR
    python ModStudio.py --cli files   <iso> [--grep REGEX]

`scan` takes the folder your discs are in rather than a disc, and is the only
verb here that does. With no folder it looks in the current one.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

from tcps2 import art, engine
from tcps2.detect import identify, scan_folder
from tcps2.model import BOOL, CHOICE, INT


def _values(profile, args):
    vals = profile.defaults()
    if args.preset:
        from gui.presets import PRESETS
        for name, preset in PRESETS.get(profile.id, []):
            if args.preset.lower() in name.lower():
                vals.update(preset)
                break
        else:
            raise SystemExit("no preset matching %r" % args.preset)
    for item in args.set or []:
        if "=" not in item:
            raise SystemExit("--set wants key=value, got %r" % item)
        key, raw = item.split("=", 1)
        s = profile.setting(key)
        if s is None:
            raise SystemExit("unknown option %r (try `list`)" % key)
        if s.kind == BOOL:
            vals[key] = raw.strip().lower() in ("1", "true", "yes", "on")
        elif s.kind == INT:
            vals[key] = int(raw)
        else:
            vals[key] = raw
    return profile.normalise(vals)


def _need(path):
    det = identify(path)
    if not det.ok:
        raise SystemExit(det.message)
    return det


def cmd_scan(args):
    """Every supported disc in a folder.

    Deliberately not the full identify: `scan_folder` skips the PCSX2 CRC,
    which XORs every word of a boot executable that is 37 MB on one of these
    discs, and the check for this tool's own code patches, which has to inflate
    a compressed overlay. Neither tells you anything you need in order to
    choose a disc, and with them a shelf of eight takes the better part of a
    minute instead of a tenth of a second. Whichever one you then open gets the
    full check.
    """
    folder = args.folder or os.getcwd()
    found = scan_folder(folder)
    if not found:
        print("No supported discs in %s" % folder)
        return 1
    width = max(len(d.profile.short) for d in found)
    for det in sorted(found, key=lambda d: (d.profile.short,
                                            os.path.basename(d.path))):
        print("%-*s  %-11s  %s" % (width, det.profile.short,
                                   det.profile.serial,
                                   os.path.basename(det.path)))
    print("\n%d disc%s in %s"
          % (len(found), "" if len(found) == 1 else "s", os.path.abspath(folder)))
    return 0


def cmd_info(args):
    det = _need(args.iso)
    print("%s" % det.title)
    print("  serial      %s" % det.profile.serial)
    print("  boot        %s" % det.boot)
    print("  volume id   %s" % det.volume)
    print("  disc CRC    %s%s" % (det.crc, "" if det.crc_matches else "   (UNEXPECTED)"))
    print("  cheat file  %s.pnach" % det.profile.pcsx2_crc)
    print("  backup      %s" % ("present" if det.has_backup else "not taken yet"))
    rev = getattr(det, "rev", None)
    if rev is not None and not rev.known and det.profile.overlays:
        c = rev.capability
        print("  %-10s  %s" % (det.profile.overlays[0].name,
                               "a different build than this profile was made for"))
        if c is not None:
            print("  options     %d work, %d switched off, %d unaffected"
                  % (len(c.code_ok), len(c.disabled), len(c.data_only)))
            for key in sorted(c.disabled):
                print("     off: %-26s %s" % (key, c.disabled[key]))
    if det.message:
        print("  note        %s" % det.message)
    if det.profile.notes:
        print()
        print(det.profile.notes)
    return 0


def _print_settings(p):
    """One profile's options. Shared by `list` (needs a disc) and `games`
    (does not), so the two can never drift apart."""
    if not p.settings:
        print("%s has no options yet." % p.title)
        return 0
    group = None
    for s in p.settings:
        if s.group != group:
            group = s.group
            print("\n[%s]" % group)
        kind = s.kind
        if kind == INT:
            rng = "%d..%d" % (s.minimum, s.maximum)
        elif kind == CHOICE:
            rng = "|".join(str(c.value) for c in s.choices)
        else:
            rng = "true|false"
        flags = []
        if s.pnach_only:
            flags.append("cheat-file")
        if not s.enabled:
            flags.append("DISABLED")
        if s.confidence != "verified":
            flags.append(s.confidence)
        print("  %-20s %-26s default=%-8s %s"
              % (s.key, rng, s.default, " ".join(flags)))
        print("      %s" % s.label)
    return 0


def cmd_list(args):
    return _print_settings(_need(args.iso).profile)


def cmd_games(args):
    """Every game and every option, with no disc involved.

    The text twin of the window's Preview: it answers "what can this do"
    for someone who does not own the disc, and it is the only path here that
    opens nothing at all.
    """
    from tcps2.games import PROFILES
    if not args.game:
        print("%-22s %-11s %-9s %s" % ("GAME", "SERIAL", "OPTIONS", "ID"))
        for p in sorted(PROFILES, key=lambda q: q.short):
            print("%-22s %-11s %-9d %s"
                  % (p.short, p.serial, len(p.settings), p.id))
        print("\nAdd a game to see its options, e.g. "
              "--cli games %s" % sorted(PROFILES, key=lambda q: q.short)[0].id)
        return 0
    want = args.game.lower()
    for p in PROFILES:
        if want in (p.id.lower(), p.short.lower(), p.serial.lower()):
            print("%s  (%s)" % (p.title, p.serial))
            return _print_settings(p)
    raise SystemExit("no game matching %r -- run `--cli games` for the list"
                     % args.game)


def cmd_plan(args):
    det = _need(args.iso)
    vals = _values(det.profile, args)
    pl = engine.plan(args.iso, det.profile, vals)
    print("%s -- pristine overlay recovered via %s" % (pl.game_title, pl.pristine_source))
    for e in pl.edits:
        print("  %08x  %08x -> %08x   %s" % (e.va, e.stock, e.value, e.note))
    for d in pl.data:
        extra = (" " + str(d.params)) if d.params else ""
        scope = (" [%s]" % d.scope) if d.scope else ""
        print("  data   %-16s %-14s%s%s   %s"
              % (d.op, d.select, scope, extra, d.note))
    print("  %d word(s) into the disc, %d data edit(s), %d in the cheat file"
          % (len(pl.edits), len(pl.data), len(pl.pnach)))
    for w in pl.warnings:
        print("  ! %s" % w)
    return 0


def cmd_root(args):
    """Export a loose data root, and the launcher that makes PCSX2 use it."""
    from tcps2 import hostroot
    det = _need(args.iso)
    hostroot.require(det.profile)
    dest = args.out or os.path.join(
        os.path.dirname(os.path.abspath(args.iso)),
        os.path.splitext(os.path.basename(args.iso))[0] + " data")
    print("exporting to %s" % dest)
    rep = hostroot.export(args.iso, dest, progress=lambda m: print(m))
    bat = hostroot.write_launcher(dest, args.iso, args.pcsx2)
    print("%d files, %.1f GB, archives: %s"
          % (rep["files"], rep["bytes"] / (1 << 30), ", ".join(rep["archives"])))
    print("launcher: %s" % bat)
    if not args.pcsx2:
        print("  edit it to point at your pcsx2-qt.exe")
    print("then: apply --data-root \"%s\"" % dest)
    return 0


def cmd_apply(args):
    det = _need(args.iso)
    vals = _values(det.profile, args)
    root = getattr(args, "data_root", None)
    rev = getattr(det, "rev", None)
    if rev is not None and not rev.known:
        # The window greys these out; the command line never saw them at all and
        # went straight to engine.apply. The engine still refuses to write a plan
        # it cannot place, but being told which options were dropped, before
        # anything is written, is the difference between a warning and a mystery.
        print("this is not the pressing this profile was built for:")
        print("  %s" % rev.note())
        asked = det.profile.effective(vals)
        blocked = [s.label for s in det.profile.settings
                   if not rev.allows(s.key)
                   and asked.get(s.key) not in (None, False, 0, "stock",
                                                s.default)]
        if blocked:
            print("  these were asked for and cannot run here: %s"
                  % ", ".join(sorted(blocked)))
            return 2
        for s in det.profile.settings:
            if not rev.allows(s.key):
                vals[s.key] = s.default
    r = engine.apply(args.iso, det.profile, vals, data_root=root,
                     progress=lambda m: print("  " + m))
    print("%d of %d words verified by reading the disc back"
          % (r["verified"], r["applied"]))
    if r.get("data"):
        d = r["data"]
        print("%d data file(s) rewritten%s, %d read back cleanly%s"
              % (d.get("files", 0),
                 (", %d put back" % d["restored"]) if d.get("restored") else "",
                 d.get("verified", 0),
                 (", %d BROKEN" % d["broken"]) if d.get("broken") else ""))
        for op, n in sorted(d.get("changes", {}).items()):
            print("   %-18s %d change(s)" % (op, n))
    print("backup: %s" % r["backup"])
    pn = det.profile.build_pnach(vals) if det.profile.build_pnach else []
    if pn:
        print("%d option word(s) still need the cheat file -- run `cheat`" % len(pn))
    return 0 if r["verified"] == r["applied"] else 1


def cmd_revert(args):
    det = _need(args.iso)
    r = engine.revert(args.iso, det.profile,
                      data_root=getattr(args, "data_root", None),
                      progress=lambda m: print("  " + m))
    print("restored; stock hash %s" % ("matches" if r["hash_ok"] else "DOES NOT MATCH"))
    return 0 if r["hash_ok"] else 1


def cmd_cheat(args):
    det = _need(args.iso)
    vals = _values(det.profile, args)
    words = det.profile.build_pnach(vals) if det.profile.build_pnach else []
    words, refused = engine.relocated_pnach(args.iso, det.profile, words)
    for why in refused:
        print("  skipped: %s" % why)
    if not words:
        print("nothing selected needs a cheat file")
        return 0
    crc = det.crc or det.profile.pcsx2_crc
    out = args.out or ("%s.pnach" % crc)
    engine.write_pnach(out, det.profile, words, crc)
    print("wrote %d patch lines to %s" % (len(words), out))
    dirs = engine.find_pcsx2_cheat_dirs()
    if dirs:
        print("PCSX2 cheat folders found on this machine:")
        for d in dirs:
            print("   %s" % d)
    return 0


def cmd_art(args):
    det = _need(args.iso)
    os.makedirs(args.out, exist_ok=True)
    img = art.banner_image(det, args.out)
    if img is None:
        print("no artwork could be decoded from this disc")
        return 1
    print("banner %dx%d saved under %s" % (img.size[0], img.size[1], args.out))
    from tcps2.iso import Iso
    n = 0
    with Iso(det.path) as iso:
        for path, image in art.iso_art(iso, [r"\.FBZ$"], limit=40):
            name = path.strip("/").replace("/", "_") + ".png"
            image.save(os.path.join(args.out, name))
            n += 1
    print("%d screen(s) exported" % n)
    return 0


def cmd_files(args):
    det = _need(args.iso)
    from tcps2.iso import Iso
    from tcps2.vokes import open_archives
    rx = re.compile(args.grep, re.I) if args.grep else None
    total = 0
    with Iso(det.path) as iso:
        for arc in open_archives(iso):
            rows = [e for k, e in sorted(arc.files.items()) if not rx or rx.search(k)]
            print("== %s  (%d of %d files)" % (arc.r.name, len(rows), len(arc.files)))
            for e in rows:
                print("   %-52s %10d  @0x%09x" % (e.path, e.size, e.offset))
            total += len(rows)
    print("%d file(s)" % total)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ModStudio --cli",
                                 description="Patch Tom Clancy PS2 discs in place.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, with_sets=False, with_out=False):
        p.add_argument("iso")
        if with_sets:
            p.add_argument("--set", action="append", metavar="KEY=VALUE")
            p.add_argument("--preset", metavar="NAME")
        if with_out:
            p.add_argument("--out", metavar="PATH")
        return p

    gp = sub.add_parser("games", help="every game and option, with no disc")
    gp.add_argument("game", nargs="?")
    gp.set_defaults(fn=cmd_games)

    sp = sub.add_parser("scan", help="list the discs in a folder")
    sp.add_argument("folder", nargs="?")
    sp.set_defaults(fn=cmd_scan)

    common(sub.add_parser("info")).set_defaults(fn=cmd_info)
    common(sub.add_parser("list")).set_defaults(fn=cmd_list)
    common(sub.add_parser("plan"), True).set_defaults(fn=cmd_plan)
    app = common(sub.add_parser("apply"), True)
    app.add_argument("--data-root", metavar="FOLDER",
                     help="patch the loose archives in FOLDER instead of the "
                          "ones inside the ISO, and switch the disc onto them")
    app.set_defaults(fn=cmd_apply)
    rp = common(sub.add_parser("revert"))
    rp.add_argument("--data-root", metavar="FOLDER")
    rp.set_defaults(fn=cmd_revert)

    ep = common(sub.add_parser(
        "data-root", help="export a loose data root the game reads instead "
                          "of the disc"), False, True)
    ep.add_argument("--pcsx2", metavar="EXE",
                    help="path to pcsx2-qt.exe, written into the launcher")
    ep.set_defaults(fn=cmd_root)
    common(sub.add_parser("cheat"), True, True).set_defaults(fn=cmd_cheat)
    common(sub.add_parser("art"), False, True).set_defaults(fn=cmd_art)
    fp = common(sub.add_parser("files"))
    fp.add_argument("--grep", metavar="REGEX")
    fp.set_defaults(fn=cmd_files)

    args = ap.parse_args(argv if argv is not None else sys.argv[1:])
    if getattr(args, "out", None) is None and args.cmd == "art":
        raise SystemExit("art needs --out DIR")
    try:
        return args.fn(args)
    except engine.EngineError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

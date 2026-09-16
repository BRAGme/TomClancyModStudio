"""The same tool without the window.

    XboxModStudio.exe --cli games  [game]          -- no disc needed
    XboxModStudio.exe --cli scan   [shelf folder]
    XboxModStudio.exe --cli show   <game>
    XboxModStudio.exe --cli plan   <game> [--set key=value ...] [--preset N]
    XboxModStudio.exe --cli apply  <game> [--set key=value ...] [--preset N]
    XboxModStudio.exe --cli revert <game>

A <game> is either a disc image or a folder one was extracted into; `scan`
lists both, images first. `scan` with no argument looks in the current folder.
"""

from __future__ import annotations

import argparse
import os
import sys

from tcxbox import engine
from tcxbox.detect import identify, scan_folder
from tcxbox.model import BOOL, CHOICE, INT


def _presets(profile):
    try:
        from gui.presets import PRESETS
    except Exception:                             # noqa: BLE001
        return []
    return PRESETS.get(profile.id, [])


def _coerce(setting, text):
    if setting.kind == BOOL:
        return text.strip().lower() in ("1", "true", "yes", "on")
    if setting.kind == INT:
        return int(text)
    return text


def _values_from_args(profile, args):
    values = profile.defaults()
    if args.preset is not None:
        presets = _presets(profile)
        if not 0 <= args.preset < len(presets):
            raise SystemExit("preset %d is out of range (0-%d)"
                             % (args.preset, len(presets) - 1))
        name, chosen = presets[args.preset]
        print("preset: %s" % name)
        values.update(chosen)
    for pair in args.set or []:
        if "=" not in pair:
            raise SystemExit("--set wants key=value, got %r" % pair)
        key, text = pair.split("=", 1)
        setting = profile.setting(key.strip())
        if setting is None:
            raise SystemExit("%r is not a setting on %s" % (key, profile.short))
        values[setting.key] = _coerce(setting, text)
    return profile.normalise(values)


def _require(path):
    det = identify(path)
    if not det.ok:
        raise SystemExit(det.message)
    return det


def cmd_scan(args):
    folder = args.folder or os.getcwd()
    found = scan_folder(folder)
    if not found:
        print("No supported games under %s" % folder)
        return 1
    for det in found:
        print("%-18s  %s  %s" % (det.profile.short, det.title_id, det.path))
    return 0


def _print_settings(profile):
    """One profile's options. Shared by `show` (needs the game) and `games`
    (does not), so the two can never drift apart."""
    print("\nsettings:")
    for group in profile.groups():
        print("  [%s]" % group)
        for s in profile.settings:
            if s.group != group:
                continue
            extra = ""
            if s.kind == INT:
                extra = " (%d-%d%s)" % (s.minimum, s.maximum,
                                        " " + s.unit if s.unit else "")
            elif s.kind == CHOICE:
                extra = " (%s)" % "|".join(str(c.value) for c in s.choices)
            flag = "" if s.enabled else "  [disabled: %s]" % s.disabled_reason
            print("    %-28s %-7s default=%-8s %s%s%s"
                  % (s.key, s.kind, s.default, s.confidence, extra, flag))


def cmd_games(args):
    """Every game and every option, with no disc involved.

    The text twin of the window's Preview: it answers "what can this do" for
    someone who does not own the game, and it is the only path here that opens
    nothing at all.
    """
    from tcxbox.games import PROFILES
    if not args.game:
        print("%-26s %-10s %-9s %s" % ("GAME", "TITLE ID", "OPTIONS", "ID"))
        for p in sorted(PROFILES, key=lambda q: q.short):
            print("%-26s %-10s %-9d %s"
                  % (p.short, p.title_id, len(p.settings), p.id))
        print("\nAdd a game to see its options, e.g. --cli games %s"
              % sorted(PROFILES, key=lambda q: q.short)[0].id)
        return 0
    want = args.game.lower()
    for p in PROFILES:
        if want in (p.id.lower(), p.short.lower(), p.title_id.lower()):
            print("%s  (title id %s)" % (p.title, p.title_id))
            _print_settings(p)
            return 0
    raise SystemExit("no game matching %r -- run `--cli games` for the list"
                     % args.game)


def cmd_show(args):
    det = _require(args.folder)
    print("%s" % det.title)
    print("  %-11s %s" % ("disc image" if det.kind == "iso" else "folder",
                          det.path))
    print("  executable  %s" % os.path.basename(det.xbe_path))
    print("  title id    %s  (%s)" % (det.title_id, det.title_name))
    print("  backup      %s" % (engine.backup_dir_for(det.path)
                                if det.has_backup else "not taken yet"))
    if det.message:
        print("  note        %s" % det.message)
    presets = _presets(det.profile)
    if presets:
        print("\npresets:")
        for i, (name, _v) in enumerate(presets):
            print("  %2d  %s" % (i, name))
    _print_settings(det.profile)
    return 0


def cmd_plan(args):
    det = _require(args.folder)
    values = _values_from_args(det.profile, args)
    plan = engine.plan(det.path, det.profile, values)
    print("%d edit(s) across %d file(s)" % (plan.total, plan.files))
    seen = {}
    for key, edit in plan.data:
        seen.setdefault(edit.note or edit.op, []).append(key)
    for note, keys in sorted(seen.items()):
        print("  %-60s %d file(s)" % (note[:60], len(keys)))
        for key in keys[:3]:
            print("      %s" % key)
        if len(keys) > 3:
            print("      ... and %d more" % (len(keys) - 3))
    for w in plan.warnings:
        print("  ! %s" % w)
    return 0


def cmd_apply(args):
    det = _require(args.folder)
    values = _values_from_args(det.profile, args)
    report = engine.apply(det.path, det.profile, values,
                          progress=lambda m: print("  " + m))
    print("rewrote %d file(s), put %d back, %d read back cleanly, %d broken"
          % (report["files"], report["restored"], report["verified"],
             report["broken"]))
    for op, n in sorted((report.get("changes") or {}).items()):
        print("  %-20s %d value(s)" % (op, n))
    print("backup: %s" % report["backup"])
    return 1 if report["broken"] else 0


def cmd_revert(args):
    det = _require(args.folder)
    out = engine.revert(det.path, det.profile, progress=lambda m: print("  " + m))
    print("restored %d file(s)" % out["files"])
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="XboxModStudio --cli",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("games", help="every game and option, with no disc")
    g.add_argument("game", nargs="?")
    g.set_defaults(fn=cmd_games)

    s = sub.add_parser("scan", help="list the supported games on a shelf")
    s.add_argument("folder", nargs="?")
    s.set_defaults(fn=cmd_scan)

    for name, fn, help_text in (("show", cmd_show, "what this game offers"),
                                ("plan", cmd_plan, "what would change"),
                                ("apply", cmd_apply, "change it"),
                                ("revert", cmd_revert, "put it all back")):
        s = sub.add_parser(name, help=help_text)
        s.add_argument("folder")
        if name in ("plan", "apply"):
            s.add_argument("--set", action="append", metavar="KEY=VALUE")
            s.add_argument("--preset", type=int)
        s.set_defaults(fn=fn)

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except engine.EngineError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

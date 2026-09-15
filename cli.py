"""The same tool without the window.

    ModStudio.exe --cli scan   [folder]
    ModStudio.exe --cli show   <game folder>
    ModStudio.exe --cli plan   <game folder> [--set key=value ...] [--preset N]
    ModStudio.exe --cli apply  <game folder> [--set key=value ...] [--preset N]
    ModStudio.exe --cli revert <game folder>

`scan` with no folder looks in the folder above each recently used game, which
is usually the shelf everything was extracted into.
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
        print("No supported game folders under %s" % folder)
        return 1
    for det in found:
        print("%-18s  %s  %s" % (det.profile.short, det.title_id, det.path))
    return 0


def cmd_show(args):
    det = _require(args.folder)
    print("%s" % det.title)
    print("  folder      %s" % det.path)
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
    print("\nsettings:")
    for group in det.profile.groups():
        print("  [%s]" % group)
        for s in det.profile.settings:
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
    ap = argparse.ArgumentParser(prog="ModStudio --cli",
                                 description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="list supported game folders")
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

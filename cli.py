r"""Command-line mode. Same profiles, same engine, no window.

    ModStudio.exe --cli find
    ModStudio.exe --cli show    "<game folder>"
    ModStudio.exe --cli preview "<game folder>" enemy_accuracy=45 recoil=x0.5
    ModStudio.exe --cli apply   "<game folder>" enemy_accuracy=45
    ModStudio.exe --cli restore "<game folder>"

`preview` is `apply` without writing anything, and prints every value that
would change. It is the one worth using first.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tcpc import art, engine                                   # noqa: E402
from tcpc.games import PROFILES                                # noqa: E402
from tcpc.install import identify, scan_folder                 # noqa: E402
from tcpc.model import BOOL, CHOICE, INT, MOD, OVERLAY         # noqa: E402

USAGE = __doc__


def _open(path):
    det = identify(path)
    if not det.ok:
        print("Not a supported game folder: %s" % (det.message or path))
        return None
    return det


def cmd_find(_args):
    found = 0
    for lib in art.search_roots():
        for det in scan_folder(lib):
            print("%-18s %s" % (det.profile.short, det.path))
            found += 1
    if not found:
        print("No supported games found in a Steam library or on a drive root.")
        print("Supported: %s" % ", ".join(sorted(p.short for p in PROFILES)))
    return 0


def cmd_show(args):
    if not args:
        print(USAGE)
        return 2
    det = _open(args[0])
    if det is None:
        return 1
    p = det.profile
    print("%s\n  %s" % (p.title, det.path))
    print("  delivery: %s" % _delivery(p))
    print("  executable: %s (%s)" % (p.layout.exe, det.exe_version or "not found"))
    if p.delivery != MOD:
        man = engine.read_manifest(det.path)
        kept = len(man.get("files", [])) + len(man.get("created", []))
        print("  backup: %s" % ("%d file(s) tracked" % kept if kept
                                else "nothing written yet"))
    for group in p.groups():
        print("\n  [%s]" % group)
        for s in p.settings:
            if s.group != group:
                continue
            if s.kind == BOOL:
                shape = "on|off"
            elif s.kind == INT:
                shape = "%d..%d" % (s.minimum, s.maximum)
            else:
                shape = "|".join(str(c.value) for c in s.choices)
            print("    %-20s %-34s default=%-10s %s"
                  % (s.key, shape, s.default, s.confidence))
    return 0


def _delivery(p):
    if p.delivery == MOD:
        return ("generates a mod folder (%s), retail files untouched"
                % os.path.join(p.layout.mods_dir, p.mod_name))
    if p.delivery == OVERLAY:
        return ("writes loose files under %s that shadow the bundles, which "
                "are never opened for writing" % (p.layout.overlay_dir or "Data"))
    return "edits files in place, pristine copies kept"


def _values(profile, pairs):
    """Parse `key=value` arguments against the profile's own settings."""
    out = dict(profile.defaults())
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit("Expected key=value, got %r" % pair)
        key, _, raw = pair.partition("=")
        key = key.strip()
        s = profile.setting(key)
        if s is None:
            raise SystemExit("%s has no option called %r" % (profile.short, key))
        raw = raw.strip()
        if s.kind == BOOL:
            value = raw.lower() in ("1", "true", "yes", "on")
        elif s.kind == INT:
            value = int(raw)
        else:
            value = raw
        coerced = s.coerce(value)
        if s.kind == CHOICE and coerced != value:
            raise SystemExit("%s must be one of: %s"
                             % (key, ", ".join(str(c.value) for c in s.choices)))
        out[key] = coerced
    return out


def _run(args, dry):
    if not args:
        print(USAGE)
        return 2
    det = _open(args[0])
    if det is None:
        return 1
    values = _values(det.profile, args[1:])
    result = engine.apply(det.path, det.profile, values, dry_run=dry)
    for line in result.log():
        print(line)
    for w in result.warnings:
        print("  ! %s" % w)
    changed = sum(1 for c in result.changes if c.status == "changed")
    print("\n%s: %d value(s) across %d file(s)."
          % ("Would change" if dry else "Changed", changed, result.files))
    if not dry and det.profile.delivery == MOD:
        print("Mod built. Turn it on in the game's own Mods menu.")
    if not dry and det.profile.delivery == OVERLAY:
        print("Written as loose files. The bundles were not modified.")
    return 0 if result.ok else 1


def cmd_preview(args):
    return _run(args, True)


def cmd_apply(args):
    return _run(args, False)


def cmd_restore(args):
    if not args:
        print(USAGE)
        return 2
    det = _open(args[0])
    if det is None:
        return 1
    result = engine.revert(det.path, det.profile)
    for w in result.warnings:
        print("  ! %s" % w)
    print("Restored %d file(s)." % result.files)
    return 0 if result.ok else 1


COMMANDS = {"find": cmd_find, "show": cmd_show, "preview": cmd_preview,
            "apply": cmd_apply, "restore": cmd_restore}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    fn = COMMANDS.get(argv[0])
    if fn is None:
        print("Unknown command %r.\n%s" % (argv[0], USAGE))
        return 2
    return fn(argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())

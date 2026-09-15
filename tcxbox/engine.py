"""Applying a settings dict to a game, and undoing it again.

Three rules make this safe to run over and over, and they are the PS2 tool's:

  1. Every write starts from the file as it SHIPPED, never from whatever is in
     the game now. The originals are on disk in the backup folder, so applying
     twice gives the same result as applying once, and clearing an option really
     removes it -- an apply puts back every file it touched before that no
     longer matches an edit.

  2. Nothing is written until the game has been positively identified as the
     one the profile is for, by the title id in its own executable.

  3. Everything replaced is copied into a `.tcxms-backup` folder beside the
     game -- next to the disc image, or next to the extracted folder -- first,
     so a mod can still be undone a month later.

A disc image is edited in place. It is opened read-only to plan and read-write
only for the moments an apply or a revert is actually writing, so a tool left
sitting on a game does not hold the image open against xemu.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from . import dataedit
from .gamedir import Root

BACKUP_DIR = ".tcxms-backup"


class EngineError(Exception):
    pass


@dataclass
class Plan:
    """What a settings dict would do, before anything is written."""
    game_title: str
    data: list = field(default_factory=list)      # (key, edit) rows
    warnings: list = field(default_factory=list)

    @property
    def clean(self):
        return not self.warnings

    @property
    def total(self):
        return len(self.data)

    @property
    def files(self):
        return len({key for key, _edit in self.data})


def backup_dir_for(game_path) -> str:
    """Where a game's originals live.

    Beside the game, named for it, whether that is a folder or a disc image --
    so a shelf with both an `.iso` and the folder someone extracted from it
    keeps two independent sets and neither can restore the other's bytes into
    the wrong one.
    """
    game_path = os.path.abspath(str(game_path))
    root = os.path.join(os.path.dirname(game_path), BACKUP_DIR)
    return os.path.join(root, os.path.basename(game_path))


def has_backup(game_path) -> bool:
    return os.path.exists(os.path.join(backup_dir_for(game_path),
                                       dataedit.MANIFEST))


def _warnings(profile, values):
    out = []
    for s in profile.settings:
        # "stock", False and 0 all mean "leave this alone", and so does a value
        # still sitting on its own default, so none of those is worth a warning
        # even when a master switch above it is off.
        value = values.get(s.key)
        asking = value not in (None, False, 0, "stock", s.default)
        if not s.enabled and asking:
            out.append("%s is disabled in this build: %s"
                       % (s.label, s.disabled_reason))
        if asking and profile.unmet(s.key, values):
            out.append("%s does nothing without: %s"
                       % (s.label, ", ".join(profile.unmet(s.key, values))))
    return out


def plan(game_path, profile, values, root=None) -> Plan:
    values = profile.normalise(values)
    warnings = _warnings(profile, values)
    edits = profile.build_data(values) if profile.build_data else []
    rows = []
    if edits:
        own = root is None
        r = root or Root(game_path)
        try:
            rows = dataedit.plan_data(r, edits)
        except dataedit.DataEditError as exc:
            warnings.append(str(exc))
        finally:
            if own:
                r.close()
        asked = {e.op for e in edits}
        hit = {e.op for _k, e in rows}
        for op in sorted(asked - hit):
            warnings.append("nothing in this game matches the %s edit" % op)
    return Plan(profile.title, rows, warnings)


def apply(game_path, profile, values, progress=None, root=None) -> dict:
    values = profile.normalise(values)
    edits = profile.build_data(values) if profile.build_data else []
    folder = backup_dir_for(game_path)
    store = dataedit.Store(folder)

    def say(msg):
        if progress:
            progress(msg)

    report = {"files": 0, "restored": 0, "verified": 0, "broken": 0,
              "changes": {}, "backup": folder,
              "when": time.strftime("%Y-%m-%d %H:%M:%S")}

    say("Reading %s" % os.path.basename(str(game_path)))
    own = root is None
    r = root or Root(game_path, writable=True)
    try:
        say("Editing the game's own data files")
        out = dataedit.apply_data(r, edits, store, progress=progress)
        report.update(out)
    finally:
        if own:
            r.close()

    # Re-opened rather than re-used: reading the files back through the handle
    # that just wrote them would confirm this tool's own buffers, not the game.
    say("Verifying against the game")
    with Root(game_path) as check:
        good, bad = dataedit.verify_data(check, store)
    report["verified"], report["broken"] = good, bad
    return report


def revert(game_path, profile, progress=None) -> dict:
    folder = backup_dir_for(game_path)
    store = dataedit.Store(folder)
    if not store.keys():
        raise EngineError("nothing recorded for this game -- there is "
                          "nothing to undo")
    with Root(game_path, writable=True) as r:
        out = dataedit.revert_data(r, store, progress=progress)
    out["restored"] = out["files"] > 0
    return out

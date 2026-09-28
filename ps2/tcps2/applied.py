"""What a disc was last patched with, and what an Apply would change on it.

Why this exists
---------------

The window keeps its own copy of every control in its settings file, saved on
every click, and Apply writes whatever the window holds. That copy is not the
disc. A disc patched from the command line, or from the window on another day,
carries something else -- and pressing Apply after moving ONE control wrote
the window's whole stored profile with nothing on screen to say that anything
else was going with it. That is how two untested options that re-assemble
UnrealScript reached a disc alongside a change to player 2's look speed, and
the level load hung.

So the engine records what it applied, beside the other backups for that disc,
at the one point the window and the command line both pass through: the end of
a successful `engine.apply`. A record kept by the window alone would be wrong
after every command-line apply, which is exactly when it is needed. The apply
sheet compares against it, and the window can load any recent apply back.

What is recorded
----------------

`applied-settings.json` in the disc's backup folder:

    {"profile": <id>,
     "on_disc": {"when": ..., "kind": "applied" | "stock", "values": {...}},
     "history": [<the last KEEP applies, newest first>]}

`values` is always the EFFECTIVE settings dict -- what `GameProfile.effective`
makes of it -- because that is what the disc was built from. A withdrawn
option or an unmet prerequisite stored against the profile never reached the
disc, and recording it would make it look as if it had.

A revert sets `on_disc` to "stock" and leaves the history alone, so the
settings that were working before a restore are still there to load.

Nothing here touches Tk, so every rule in it is checked by the suite.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from .model import BOOL, CHOICE, Setting

STORE = "applied-settings.json"

#: how many applies are kept to go back to
KEEP = 5


def _shipped(setting):
    """The value that leaves this setting's part of the game alone."""
    return False if setting.kind == BOOL else setting.default


def stock(profile) -> dict:
    """The settings that describe a disc as it shipped.

    Not `profile.defaults()`. A default is this tool's recommendation, and
    several are ON: Rainbow Six 3's split-screen effect fixes default to on,
    which is seven code words on an Apply with nothing touched. Comparing a
    restored disc against the defaults would leave exactly those out of the
    apply sheet, and the sheet exists so that nothing is written it did not
    list. Every switch off and every dial on its default builds no code word
    and no cheat line on any profile; the suite checks that.
    """
    return {s.key: _shipped(s) for s in profile.settings}


# ---------------------------------------------------------------------------
# the record
# ---------------------------------------------------------------------------

def _path(folder):
    return os.path.join(folder, STORE)


def load(folder, profile) -> dict:
    """{"on_disc": entry or None, "history": [entries, newest first]}.

    Anything unreadable reads as nothing recorded rather than as an error. This
    is a convenience beside the backups, and a damaged copy must never be what
    stops a disc being patched. A record for a different game is ignored for
    the same reason: the folder is named after the image's stem, so "X.iso"
    and "X.bin" side by side share one.
    """
    empty = {"on_disc": None, "history": []}
    try:
        with open(_path(folder), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return empty
    if not isinstance(data, dict) or data.get("profile") != profile.id:
        return empty
    return {"on_disc": data.get("on_disc"),
            "history": list(data.get("history") or [])}


def _save(folder, profile, log):
    os.makedirs(folder, exist_ok=True)
    with open(_path(folder), "w", encoding="utf-8") as fh:
        json.dump({"profile": profile.id, "on_disc": log["on_disc"],
                   "history": log["history"]}, fh, indent=1)


def record(folder, profile, values, when) -> None:
    """Note a successful apply of `values`.

    Applying settings already in the history moves that entry to the front
    instead of adding a copy. Re-applying one configuration while testing a
    single dial is the usual run of the command line, and five copies of it
    would push out the configuration that was working before it -- the one
    this history is for.
    """
    values = profile.effective(values)
    entry = {"when": when, "kind": "applied", "values": values}
    log = load(folder, profile)
    older = [e for e in log["history"]
             if profile.effective(e.get("values") or {}) != values]
    log["history"] = [entry] + older[:KEEP - 1]
    log["on_disc"] = entry
    _save(folder, profile, log)


def record_stock(folder, profile, when) -> None:
    """Note that the disc was put back as it shipped.

    The history is kept. The reason to restore a disc is usually that the
    latest apply broke something, and the settings from before it are what
    gets asked for next.
    """
    log = load(folder, profile)
    log["on_disc"] = {"when": when, "kind": "stock", "values": stock(profile)}
    _save(folder, profile, log)


def baseline(folder, profile):
    """(values, entry): the effective settings on the disc now, and the record
    they come from -- None when nothing has been recorded.

    With no record the answer is the disc as it shipped. That is exact for a
    disc this tool has never written. For one last patched by a build that kept
    no record, it still lists everything the new settings turn on, which is the
    half that can break a disc; what they turn off that the older build put
    there goes unlisted, and the sheet says so.
    """
    entry = load(folder, profile)["on_disc"]
    values = entry.get("values") if entry else None
    return profile.effective(stock(profile) if values is None else values), entry


# ---------------------------------------------------------------------------
# the difference, and how risky each part of it is
# ---------------------------------------------------------------------------

@dataclass
class Change:
    setting: Setting
    before: Any
    after: Any
    #: the confidence badge the row has to wear, or None for a quiet row
    risk: str | None


def changes(profile, before, after) -> list:
    """Every setting whose effect an Apply of `after` would change, in the
    order the window shows them.

    Both sides go through `effective`, so a withdrawn option stored against a
    profile, or a dial whose prerequisite is off on both sides, is not a change:
    the disc gets the same either way.

    That alone still leaves phantoms when the prerequisite ITSELF changes.
    Switching wave mode off resets its dials to their defaults, and listing
    "Enemies each zone owes 99 > 30" for a mode being switched off reads as a
    change that is not happening. So a setting the NEW values leave without
    its prerequisite is not listed: it does nothing after the apply, and the
    prerequisite's own row already says so.
    """
    old, new = profile.effective(before), profile.effective(after)
    return [Change(s, old[s.key], new[s.key], risk(s, new[s.key]))
            for s in profile.settings
            if old[s.key] != new[s.key] and not profile.unmet(s.key, new)]


def risk(setting, value):
    """The confidence badge a change to `value` has to carry, or None.

    Only a change toward DOING something is risky: moving an option to anything
    but its shipped value when it has not been watched working. Switching an
    untested option off is the cure for a hang, not a cause of one, so it
    stays quiet.

    Withdrawn options are pinned to their defaults by `effective` before a diff
    ever sees them. They are flagged here anyway, so an option marked broken
    but left switchable could never pass as a quiet row.
    """
    if value == _shipped(setting):
        return None
    if not setting.enabled or setting.confidence == "broken":
        return "broken"
    return None if setting.confidence == "verified" else setting.confidence


def show(setting, value) -> str:
    """A value the way a person reads it: On or Off, a choice by its label, a
    number with its unit."""
    if setting.kind == BOOL:
        return "On" if value else "Off"
    if setting.kind == CHOICE:
        return next((c.label for c in setting.choices if c.value == value),
                    str(value))
    unit = setting.unit
    # A word takes a space ("90 degrees"); a symbol does not ("40%", "3x").
    gap = " " if len(unit) > 1 and unit[0].isalpha() else ""
    return "%s%s%s" % (value, gap, unit)

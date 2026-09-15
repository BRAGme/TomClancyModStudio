"""The declarative model the GUI renders and the engine applies.

A game profile is a list of Settings. Each Setting is one control in the UI.
Turning the settings into concrete edits is the profile's own job
(`build_data`), because the interesting options are parameterised -- "one tier
tougher" is a rewrite of every enemy template name in 47 mission files, not a
flag.

There is one kind of edit on Xbox, and that is the whole point of the port.
On PS2 the good options were MIPS immediates baked into a compressed overlay,
so that tool needed a disassembler's worth of addresses and a code-word store.
Every one of these games keeps its interesting numbers in text on the disc --
XML under `mission\\` and `actor\\`, ini files under `System\\` -- so a FileEdit
is all there is, and the risk of a wrong address goes away with it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

BOOL = "bool"
INT = "int"
CHOICE = "choice"


@dataclass
class Choice:
    value: Any
    label: str
    help: str = ""


@dataclass
class Setting:
    key: str
    label: str
    kind: str
    default: Any
    group: str = "General"
    help: str = ""
    minimum: int = 0
    maximum: int = 100
    unit: str = ""
    choices: list = field(default_factory=list)
    #: other settings that must hold given values for this one to do anything
    requires: dict = field(default_factory=dict)
    #: shown in the UI in a warning colour
    caution: str = ""
    #: set False for settings that are documented but not yet implemented
    enabled: bool = True
    #: free-form note shown under the control when `enabled` is False
    disabled_reason: str = ""
    #: how far this option has actually been proven, shown as a badge:
    #:   "verified"     -- watched working in the running game
    #:   "applied"      -- the files are confirmed rewritten in the game folder,
    #:                     effect not independently observed
    #:   "experimental" -- reasoned from the data, never tested
    #:   "broken"       -- known not to work, shipped disabled with the reason
    #:
    #: The default is deliberately NOT "verified": a card that nobody
    #: remembered to badge should understate what is known about it, not claim
    #: someone watched it work.
    confidence: str = "applied"
    #: what this option rewrites. Always "data" here; kept so the GUI copied
    #: from the PS2 tool keeps working unchanged.
    touches: str = "data"

    def coerce(self, value):
        if self.kind == BOOL:
            return bool(value)
        if self.kind == INT:
            try:
                v = int(value)
            except (TypeError, ValueError):
                return self.default
            return max(self.minimum, min(self.maximum, v))
        if self.kind == CHOICE:
            valid = [c.value for c in self.choices]
            return value if value in valid else self.default
        return value


@dataclass
class FileEdit:
    """A change to the game's own data files.

    `select` is a regex over the game folder's upper-case keys (see
    `gamedir.Root`), `op` names one of the transforms in `dataedit.OPS`, and
    every transform keeps the file's length -- which is not a nicety here: a
    glob has no index, so a file that grows by a byte moves every entry after
    it, and Rainbow Six 3's `.umd` bundle would need its whole index relaid.
    """
    op: str
    select: str
    params: dict = field(default_factory=dict)
    note: str = ""
    #: extra filter resolved from the folder itself. "enemy_templates" narrows
    #: the match to the .atr files the missions hand to a non-allied company,
    #: so a "tougher enemies" edit cannot quietly buff the player's own squad.
    scope: str = ""

    def matches(self, key) -> bool:
        import re
        return bool(re.search(self.select, key, re.I))


@dataclass
class Marker:
    """A file that must be present for a folder to be this game.

    `rel` is checked case-insensitively, because the same game ships `System`
    on one disc and `system` on another.
    """
    rel: str
    why: str = ""


@dataclass
class GameProfile:
    id: str
    title: str
    short: str
    title_id: str             # the XBE certificate's title id, e.g. "55530006"
    xbe: str = "default.xbe"  # the executable that identifies the folder
    #: relative paths that must exist under the game folder
    markers: list = field(default_factory=list)
    #: when the game's real root is not the folder the user picks. Rainbow Six
    #: 3 Black Arrow's prototype disc is an installer whose payload sits under
    #: Files\Black_Arrow_XBOX_media.
    root_hint: str = ""
    settings: list = field(default_factory=list)
    #: values -> list[FileEdit]; raises ValueError for an impossible combination
    build_data: Callable[[dict], list] = None
    notes: str = ""
    #: art paths inside the game folder, used to skin the UI
    ui_art: dict = field(default_factory=dict)
    #: key -> [artName], so a settings page can show the game's own art beside
    #: the option it belongs to
    mission_art_for: Any = None

    def defaults(self) -> dict:
        return {s.key: s.default for s in self.settings}

    def groups(self) -> list:
        seen = []
        for s in self.settings:
            if s.group not in seen:
                seen.append(s.group)
        return seen

    def setting(self, key):
        for s in self.settings:
            if s.key == key:
                return s
        return None

    def normalise(self, values: dict) -> dict:
        out = self.defaults()
        for s in self.settings:
            if s.key in values:
                out[s.key] = s.coerce(values[s.key])
        return out

    def unmet(self, key, values) -> list:
        """Human-readable list of requirements this setting does not have."""
        s = self.setting(key)
        if not s:
            return []
        missing = []
        for dep_key, want in s.requires.items():
            dep = self.setting(dep_key)
            if dep is None:
                continue
            have = values.get(dep_key, dep.default)
            ok = have in want if isinstance(want, (list, tuple, set)) else have == want
            if not ok:
                missing.append(dep.label)
        return missing

"""The declarative model the GUI renders and the engine applies.

This is the PS2/Xbox Mod Studio model re-aimed at PC installs. The *settings*
half is unchanged on purpose -- a Setting is still one control in the UI, still
carries how far it has been proven, and a profile still turns settings into
concrete edits in its own `build_edits`. What changes is the other half: a PC
game is a folder of loose text, not a disc image, so there are no virtual
addresses and no overlays. Every edit here names a FILE and a place inside it.

Four edit kinds cover all five games:

  IniEdit    one key in one section of a `.ini`. Unreal Engine 2 (Raven Shield)
             and Unreal Engine 3 (Vegas) both configure this way. The writer
             keeps the file's own byte habits -- CRLF, key order, comments, and
             Vegas's decimal COMMA -- because a config file that comes back
             reordered is indistinguishable from a corrupted one.

  XmlAttr    one attribute of one element in a Red Storm pseudo-XML file
             (`.gun`, `.wsf`, `CmbtModl.xml`, `options.xml`). Lockdown is
             written this way throughout.

  XmlText    the text of one element in a Red Storm pseudo-XML file
             (`.atr`, `.gtf`, `.kit`). Ghost Recon and Sum of All Fears are
             written this way throughout.

  FileCopy   a whole file placed into the install (or into a generated mod
             folder), optionally transformed on the way.

Each edit is a *selector plus a value*. The selector may be a glob, so one
setting can say "every enemy actor file" without the profile listing 459 paths.

DELIVERY -- how the edits reach the game -- is a property of the profile, not
of the edit, and there are two:

  "mod"      Ghost Recon and Sum of All Fears both load `Mods\\<name>\\` folders
             that shadow `Mods\\Origmiss\\`. The tool generates one. Nothing
             retail is ever written, and turning the mod off in the game's own
             menu is a complete uninstall.

  "inplace"  Raven Shield, Lockdown and Vegas have no such folder. Those are
             edited where they sit, and safety comes from the same invariant
             the PS2 tool uses: every apply rebuilds each touched file from a
             PRISTINE copy taken the first time that file was ever written, so
             applying twice equals applying once and clearing an option really
             removes it.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

BOOL = "bool"
INT = "int"
CHOICE = "choice"

#: delivery modes
MOD = "mod"
INPLACE = "inplace"
#: Advanced Warfighter keeps everything in multi-gigabyte `.bundle` archives,
#: and the Diesel engine looks a file up on disk BEFORE it looks in the
#: archive. So the stock value is read out of the bundle, the edited file is
#: written loose under `Data\`, and the archives are never opened for writing.
#: Reverting deletes exactly the files the tool created and restores any it
#: had to write over -- never the whole folder, because the user's own texture
#: replacements live in the same tree.
OVERLAY = "overlay"


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
    #:   "applied"      -- the edit is confirmed in the file, effect not
    #:                     independently observed
    #:   "experimental" -- reasoned from the data, never tested
    #:   "broken"       -- known not to work, shipped disabled with the reason
    confidence: str = "experimental"
    #: what this option rewrites, shown as a tag:
    #:   "config"  an .ini the game reads at start-up
    #:   "data"    the game's own data files
    #:   "mod"     a generated mod folder, so retail files are untouched
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


# ---------------------------------------------------------------------------
# edits
# ---------------------------------------------------------------------------

@dataclass
class Edit:
    """Base: what every edit has in common.

    `select` is a path relative to the install root, and may be a glob.
    `note` is what the log line says, so an apply reads as a list of changes
    rather than a list of paths.
    """
    select: str
    note: str = ""
    #: optional predicate over a parsed file, used when a glob is too blunt to
    #: express the real scope -- "enemy actors" is a property of the file's
    #: contents, not of its name, and a `.atr` glob that also caught the
    #: player's own squad would quietly buff the wrong side.
    scope: str = ""

    @property
    def kind(self):
        return type(self).__name__


@dataclass
class IniEdit(Edit):
    section: str = ""
    key: str = ""
    #: one field inside an Unreal struct literal, when the value is not the
    #: whole of what the key holds -- `m_Rainbow=(fStandSlow=300,fStandFast=800,
    #: ...)` is five numbers under one key, and Raven Shield's entire AI
    #: hearing model is written that way.
    field: str = ""
    value: Any = None
    #: the value expected to be there before the write. Checked and reported,
    #: never silently ignored -- a stock value that does not match means this
    #: is a different build and the profile's arithmetic is not about this game.
    stock: Any = None
    #: multiply the file's own value instead of replacing it, so one setting
    #: can say "every weapon 20% more accurate" across 30 weapon sections that
    #: all start from different numbers
    scale: float = None
    #: added after scaling, so an edit reads `value * scale + offset`. Needed
    #: because "two more magazines" is an addition and expressing it as a
    #: multiplication would give a different answer for every weapon.
    offset: float = None
    #: clamp after scaling and offsetting
    minimum: float = None
    maximum: float = None
    #: how a missing key is treated. "add" appends it to the section (UE reads
    #: keys that are absent from the file as their compiled-in default, so
    #: adding one is the normal way to override); "skip" leaves the file alone
    #: and logs it; "error" fails the apply.
    absent: str = "add"


@dataclass
class XmlAttr(Edit):
    #: element path, e.g. "GunFile/Common/UIData". Matched loosely against the
    #: nesting, so a profile does not have to spell every intermediate level.
    path: str = ""
    attr: str = ""
    value: Any = None
    #: {old value: new value}, applied per element and only where the current
    #: value is a key. For the edits that are neither a constant nor a scaling:
    #: Advanced Warfighter encodes how many soldiers a placement spawns in the
    #: GROUP NAME it references, so "fuller squads" is a rename from
    #: `mex_guerilla_patrol2` to `mex_guerilla_patrol4` -- a different string
    #: per placement, and one that must not be invented, because only the names
    #: the group manager generates exist.
    remap: dict = field(default_factory=dict)
    stock: Any = None
    #: multiply the file's own value instead of replacing it, so one setting
    #: can say "every weapon 20% less accurate" across 108 files that all start
    #: from different numbers.
    scale: float = None
    #: added after scaling, so an edit reads `value * scale + offset`. Needed
    #: because "two more magazines" is an addition and expressing it as a
    #: multiplication would give a different answer for every weapon.
    offset: float = None
    #: clamp after scaling and offsetting
    minimum: float = None
    maximum: float = None
    absent: str = "skip"


@dataclass
class XmlText(Edit):
    path: str = ""
    value: Any = None
    #: {old: new}, as on `XmlAttr` -- for element text rather than an
    #: attribute. Both kinds carry it so a caller never has to know which
    #: dialect a game uses to know what an edit can express.
    remap: dict = field(default_factory=dict)
    stock: Any = None
    scale: float = None
    #: added after scaling, so an edit reads `value * scale + offset`. Needed
    #: because "two more magazines" is an addition and expressing it as a
    #: multiplication would give a different answer for every weapon.
    offset: float = None
    #: clamp after scaling and offsetting
    minimum: float = None
    maximum: float = None
    absent: str = "skip"


@dataclass
class IniLines(Edit):
    r"""A key Unreal reads as a LIST, written once per element.

    `IniEdit` is wrong for these. Unreal builds an array by assigning the same
    key repeatedly::

        GameTypes=(package=R6Game,type=R6StoryModeGame,maxNb=16)
        GameTypes=(package=R6Game,type=R6TerroristHuntGame,maxNb=16)

    and `set` rewrites the LAST line, which changes an element instead of
    adding one. So this edit works on the list as a whole: `add` ensures values
    are present, `drop` removes them, `swap` rewrites one in place.

    `swap` exists separately from drop-then-add because position is meaningful:
    Raven Shield lists a map's modes in menu order, so removing and re-adding
    would silently reorder somebody's menu.

    All three are idempotent, which they have to be -- every apply rebuilds
    from pristine and runs the same edits again.
    """
    section: str = ""
    key: str = ""
    #: values to ensure are present
    add: list = field(default_factory=list)
    #: values to ensure are absent
    drop: list = field(default_factory=list)
    #: {old: new}, whole values rewritten where they sit
    swap: dict = field(default_factory=dict)
    #: rename the SECTION itself, for a shipped typo in a section header.
    rename: str = ""
    #: {old: new} applied as a literal substring INSIDE each value, for a
    #: struct element where only one field is wrong and the rest differ from
    #: line to line -- so there is no whole value to match on.
    sub: dict = field(default_factory=dict)


@dataclass
class PropEdit(Edit):
    r"""One compiled class default inside an Unreal Engine 2 package.

    Raven Shield's weapon and ammunition statistics are not configuration --
    they are class defaults compiled into `system\*.u`, and this is the only
    edit kind here that writes binary. Two rules make that safe:

    **Equal width, always.** A float is replaced by a float and an int by an
    int, so the file's length never changes and its export table stays valid.

    **A property that is not already authored is skipped, never added.** Unreal
    serialises a property only when its value differs from its class default,
    so adding one would move every byte after it. `absent` therefore defaults
    to "skip", and a weapon that inherits a value cannot be tuned on its own --
    its parent can.

    `cls` is a class name or a glob over class names. Its real scope, though,
    is `prop`: an edit naming `m_stAccuracyValues.fWeaponJump` reaches exactly
    the 143 classes that have a weapon's accuracy struct, however broad the
    glob, because nothing else in the package carries that property. Scoping by
    what a class IS rather than by what it is called is why `cls="*"` is a
    reasonable thing to write here.
    """
    cls: str = "*"
    #: property path. Dotted into a struct (`m_stAccuracyValues.fBaseAccuracy`)
    #: and indexed into an array (`m_ADamagePercent[0]`).
    prop: str = ""
    value: Any = None
    #: only meaningful when `cls` names a single class -- a glob spans classes
    #: whose stock values all differ, so there is no one value to expect.
    stock: Any = None
    scale: float = None
    offset: float = None
    minimum: float = None
    maximum: float = None
    absent: str = "skip"


@dataclass
class FileCopy(Edit):
    """Place a file. `source` is read from the install unless `data` is given.

    Used for the two things an attribute edit cannot express: shipping a file
    the game does not have, and replacing one wholesale.
    """
    source: str = ""
    data: bytes = None


# ---------------------------------------------------------------------------
# profile
# ---------------------------------------------------------------------------

@dataclass
class Layout:
    """Where a game keeps the things this tool cares about.

    Kept separate from the profile because detection needs it before a profile
    is chosen, and because the two RSE games differ only in these paths.
    """
    #: files that must all exist for this to be that game. Relative, globs OK.
    signature: list = field(default_factory=list)
    #: the executable, used for the version/build check and the window subtitle
    exe: str = ""
    #: where generated mods go, for MOD delivery
    mods_dir: str = ""
    #: the stock mod folder a generated one shadows, for MOD delivery
    base_mod: str = ""
    #: where the config files live, for INPLACE delivery on an Unreal game
    config_dir: str = ""
    #: where the game's own data lives
    data_dir: str = ""
    #: OVERLAY only: the folder holding the `.bundle` archives
    bundles_dir: str = ""
    #: OVERLAY only: the loose tree a bundle path is written into. A bundle
    #: path of `data/units/x.xml` lands at `<overlay_dir>/units/x.xml`, because
    #: the archive's own root directory IS this folder.
    overlay_dir: str = ""
    #: OVERLAY only: how this game names a file's COMPILED twin. GRAW 1
    #: appends `.bin`, GRAW 2 replaces `.xml` with `.xmb`. The engine loads
    #: the twin in preference to the source, so an edit that does not reach it
    #: does nothing at all -- which is why this is not optional.
    compiled_suffix: str = ""


@dataclass
class GameProfile:
    id: str
    title: str
    short: str
    layout: Layout
    delivery: str = INPLACE
    settings: list = field(default_factory=list)
    #: values -> list[Edit]; raises ValueError for an impossible combination
    build_edits: Callable[[dict], list] = None
    #: the name of the mod folder this profile generates, for MOD delivery
    mod_name: str = ""
    #: shown on the mod's own card in the game's mod selector
    mod_blurb: str = ""
    notes: str = ""
    #: art paths inside the install, used to skin the UI
    ui_art: dict = field(default_factory=dict)
    #: optional (values) -> [str]: warnings that depend on a COMBINATION of
    #: settings rather than on any one of them
    combination_warnings: Callable[[dict], list] = None
    #: key -> [image paths], so a settings page can show the game's own art
    #: beside the option it belongs to
    mission_art_for: Any = None

    def defaults(self) -> dict:
        return {s.key: s.default for s in self.settings}

    def edits_for(self, values, root=None) -> list:
        """`build_edits`, told which installation it is building for.

        Almost every profile's edits depend only on the settings, and those
        keep the one-argument form. Ghost Recon's enemy-weapon split is the
        exception: WHICH guns to copy is read out of the installation's own
        kit files, because a list written down in the profile goes stale
        against whatever mods are actually installed. A profile that needs
        that declares a second parameter and gets the root.
        """
        fn = self.build_edits
        if fn is None:
            return []
        try:
            wants = len(inspect.signature(fn).parameters)
        except (TypeError, ValueError):            # pragma: no cover
            wants = 1
        return fn(values, root) if wants >= 2 else fn(values)

    def groups(self) -> list:
        seen = []
        for s in self.settings:
            if s.group not in seen:
                seen.append(s.group)
        return seen

    def setting(self, key) -> "Setting | None":
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

    def effective(self, values: dict) -> dict:
        """`normalise`, then neutralise every setting whose prerequisites the
        chosen values do not meet.

        `requires` only greys a widget out. The stored value survives, and the
        edits are built from stored values, so an option whose prerequisite was
        switched off would go on being emitted. Same guard as the PS2 tool, for
        the same reason it was needed there.

        Resolved to a fixed point, because requirements chain.
        """
        out = self.normalise(values)
        # A withdrawn option must be inert no matter what is stored against it:
        # the reason an option gets withdrawn is usually that it broke
        # something, which is the worst thing to keep silently applying.
        for s in self.settings:
            if not s.enabled:
                out[s.key] = s.default
        for _ in range(len(self.settings) + 1):
            changed = False
            for s in self.settings:
                if not s.requires or out.get(s.key) == s.default:
                    continue
                if self.unmet(s.key, out):
                    out[s.key] = s.default
                    changed = True
            if not changed:
                break
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

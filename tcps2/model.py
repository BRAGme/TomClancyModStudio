"""The declarative model the GUI renders and the engine applies.

A game profile is a list of Settings. Each Setting is one control in the UI.
Turning the settings into concrete edits is the profile's own job
(`build_edits`), because the interesting options are parameterised -- "30
enemies per zone" is a MIPS immediate baked into an instruction, not a flag.

Two kinds of edit exist:

  WordEdit   a 32-bit word at a virtual address inside a game overlay. Applied
             by rebuilding the overlay from its pristine image, so the result is
             the same whether you patch once or twenty times.

  PnachWord  a word that must be re-applied every frame by the emulator rather
             than baked into the disc. Only one thing needs this so far, and it
             needs it for a measured reason: a code cave written once into the
             overlay image does not survive a level load, while a pnach rewrites
             it continuously.
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
    #: True when this setting can only be delivered as an emulator cheat file
    pnach_only: bool = False
    #: set False for settings that are documented but not yet implemented
    enabled: bool = True
    #: free-form note shown under the control when `enabled` is False
    disabled_reason: str = ""
    #: how far this option has actually been proven, shown as a badge:
    #:   "verified"     -- watched working in the running game
    #:   "applied"      -- the patch is confirmed in the image, effect not
    #:                     independently observed
    #:   "experimental" -- reasoned from the disassembly, never tested
    #:   "broken"       -- known not to work, shipped disabled with the reason
    confidence: str = "verified"
    #: what this option rewrites: "code" (the executable or overlay), "data"
    #: (files inside the game's own archives) or "cheat" (an emulator file)
    touches: str = "code"

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
class WordEdit:
    va: int
    value: int
    stock: int
    note: str = ""
    target: str = "main"

    def __repr__(self):
        return "WordEdit(0x%08x -> 0x%08x  %s)" % (self.va, self.value, self.note)


@dataclass
class FileEdit:
    """A change to data files inside the game's own archives.

    `select` is a regex over the archive's upper-case paths, `op` names one of
    the transforms in `dataedit.OPS`, and every transform is required to keep
    the file length so the compressed chunk boundaries never move.
    """
    op: str
    select: str
    archive: str = ""
    params: dict = field(default_factory=dict)
    note: str = ""
    #: extra filter resolved from the archive itself. "enemy_templates" narrows
    #: the match to the .atr files used by non-allied companies, so a "tougher
    #: enemies" edit cannot quietly buff the player's own squad.
    scope: str = ""

    def matches(self, key) -> bool:
        import re
        return bool(re.search(self.select, key, re.I))


@dataclass
class Overlay:
    """A patchable overlay container inside the ISO."""
    name: str            # UI name, e.g. "SP.SOZ"
    iso_pattern: str     # regex used to locate it in the disc directory
    base_va: int         # where the decompressed image loads on the EE
    kind: str = "soz"    # "soz" (u32 size + zlib) or "raw" (patch the file directly)
    image_size: int = 0  # expected decompressed size, 0 = don't check
    image_sha1: str = "" # sha1 of the PRISTINE decompressed image, "" = don't check
    file_delta: int = 0  # byte offset in the file that base_va maps to ("raw")
    file_span: int = 0   # how far that mapping runs, 0 = to the end of the file


@dataclass
class GameProfile:
    id: str
    title: str
    short: str
    serial: str               # e.g. "SLUS-20883"
    boot: str                 # boot file name on the disc, e.g. "SLUS_208.83"
    volume_hint: str = ""
    overlays: list = field(default_factory=list)
    settings: list = field(default_factory=list)
    #: ISO -> list[WordEdit]; raises ValueError for an impossible combination
    build_edits: Callable[[dict], list] = None
    #: ISO -> list[WordEdit] that must go in a pnach rather than the disc
    build_pnach: Callable[[dict], list] = None
    #: ISO -> list[FileEdit] applied to the game's own data archives
    build_data: Callable[[dict], list] = None
    #: which archives this game's data edits live in
    archive_pattern: str = ""
    #: which archive format those are. "vokes" is the Red Storm / Unreal family
    #: container every other disc here uses; "nimitz" is Lockdown's four-volume
    #: PS2DATA archive, which is indexed by a separate file and never relocated.
    archive_kind: str = "vokes"
    #: crc32 PCSX2 uses for the cheat filename, e.g. "21CC1EC3"
    pcsx2_crc: str = ""
    #: {virtual address: stock 32-bit word} for every site the profile touches
    stock_words: dict = field(default_factory=dict)
    notes: str = ""
    #: art paths inside the game's own archives, used to skin the UI
    ui_art: dict = field(default_factory=dict)
    #: optional (values) -> [str]: warnings that depend on a
    #: COMBINATION of settings rather than on any one of them
    combination_warnings: Callable[[dict], list] = None
    #: key -> [(levelStem, part)], so a settings page can show the game's own
    #: art beside the option it belongs to. Left unset for the discs that ship
    #: no per-level pictures.
    mission_art_for: Any = None

    def defaults(self) -> dict:
        return {s.key: s.default for s in self.settings}

    def groups(self) -> list:
        seen = []
        for s in self.settings:
            if s.group not in seen:
                seen.append(s.group)
        return seen

    def setting(self, key) -> Setting | None:
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

        `requires` only greys a widget out. The stored value survives, and both
        the disc edits and the cheat file are built from stored values, so an
        option whose prerequisite was switched off went on being emitted. That
        is worse for a cheat than for a disc edit: a pnach is re-applied every
        frame, so unticking the prerequisite could not undo it at all -- which
        is exactly how eight scope hooks stayed live in memory after the option
        that needed them had been turned off.

        Resolved to a fixed point, because requirements chain (a setting can
        require one that itself requires another).
        """
        out = self.normalise(values)
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


# -- small MIPS helpers, used by the profiles ------------------------------

def addiu(rt: int, rs: int, imm: int) -> int:
    """addiu rt, rs, imm  (imm is encoded as 16 bits)"""
    return (0x09 << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)


def li(rt: int, imm: int) -> int:
    """addiu rt, $zero, imm -- load a small immediate."""
    return addiu(rt, 0, imm)


# EE register numbers used by the profiles
ZERO, AT, V0, V1 = 0, 1, 2, 3
S0, S1, S2, S3 = 16, 17, 18, 19

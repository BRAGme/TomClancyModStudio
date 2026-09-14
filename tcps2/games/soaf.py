"""The Sum of All Fears (PS2, SLES-51180) -- profile.

Red Storm's engine again, the same family as Ghost Recon PS2 and Jungle Storm,
but an earlier build and the odd one out on this shelf in three ways.

**It ships as a CD image, not a DVD.** The retail rip is MODE2/2352, so the
2,048 bytes of user data sit 24 bytes into each 2,352-byte sector. `tcps2.iso`
detects that and presents a flat logical view, which is what lets everything
else work unchanged.

**Its archives use 40-byte records, not 48** -- same fields up to +0x24, one
trailing word instead of three. Two of those fields are better than the later
games': +0x10 is an explicit `compressed` flag and the two sizes are (stored,
raw), so nothing has to be sniffed.

**Its textures are RSB version 8**, which is version 6 with seven bytes inserted
after the height, putting the pixels at the odd offset +35.

What it shares is the part that matters: the mission grammar is byte-for-byte
the one Ghost Recon uses, down to the spaces around `Easy = "0"`, so the same
transforms run on it unmodified.
"""

from __future__ import annotations

from ..model import BOOL, INT, FileEdit, GameProfile, Overlay, Setting
from . import rstuning

BOOT = "SLES_511.80"

ELF = Overlay(
    name=BOOT,
    iso_pattern=r"/SLES_511\.80$",
    base_va=0x00100000,
    kind="raw",
    file_delta=0x80,
    file_span=0x004A5780 + 0x80,
)

STOCK = {}

NOTES = (
    "The Sum of All Fears reads correctly -- 2,751 files across SOAF.IMG and "
    "MENU.IMG, with every one of its 1,674 compressed files decoding to exactly "
    "the length it declares -- and the tool wears its artwork.\n\n"
    "Its missions use the same grammar as Ghost Recon's, so the enemy options "
    "here are the same edits, running on this game unmodified.\n\n"
    "It has no render patches. Unlike Ghost Recon, which shipped an unstripped "
    "debug build, this executable is stripped, and it routes its tunables "
    "through name-driven registration tables rather than the instruction "
    "immediates that made Ghost Recon patchable -- so there is nothing "
    "honest to offer there yet.\n\n"
    "Two levers it has that Ghost Recon does not, both still to be wired up: "
    "CMBTMODL.XML holds the entire wound and difficulty model as named floats, "
    "and its game-type script tables are populated where all of Ghost Recon's "
    "missions shipped theirs empty."
)


def _settings():
    return [
        Setting("soaf_all_difficulties", "Every soldier on every difficulty",
                BOOL, False, "Enemies", confidence="applied", touches="data",
                help="The same per-actor Easy/Normal/Hard suppression flags "
                     "Ghost Recon uses. Deleting them puts the full "
                     "Hard-difficulty force into every mission at every "
                     "setting.",
                caution="Rewrites the mission files inside SOAF.IMG."),
        Setting("soaf_reveal_hidden", "Spawn the script-held reinforcements",
                BOOL, False, "Enemies", confidence="experimental",
                touches="data",
                help="Actors that ship Hidden=\"1\" wait for a mission script. "
                     "This puts them on the map from the start.",
                caution="An actor a script expects to spawn later may behave "
                        "oddly when it is already there."),
        Setting("soaf_skill", "Extra enemy skill", INT, 0, "Enemies",
                minimum=0, maximum=4, unit="points", confidence="applied",
                touches="data",
                help="Adds to armour, weapon skill, stamina, stealth and "
                     "leadership in every hostile template. Only templates used "
                     "by non-allied companies are touched, so your own side is "
                     "left alone."),
    ] + rstuning.cards("soaf_") + rstuning.soaf_cards()


def build_data(v: dict) -> list:
    out = []
    if v.get("soaf_all_difficulties"):
        out.append(FileEdit("strip_difficulty", r"\.MIS$", "SOAF.IMG",
                            note="every soldier on every difficulty"))
    if v.get("soaf_reveal_hidden"):
        out.append(FileEdit("reveal_hidden", r"\.MIS$", "SOAF.IMG",
                            note="spawn the script-held reinforcements"))
    skill = int(v.get("soaf_skill", 0))
    if skill:
        out.append(FileEdit("bump_stats", r"\.ATR$", "SOAF.IMG",
                            {"steps": skill},
                            "+%d to every hostile template's skills" % skill,
                            scope="enemy_templates"))
    out += rstuning.edits("soaf_", v, "SOAF.IMG")
    out += rstuning.soaf_edits(v)
    return out


PROFILE = GameProfile(
    id="soaf_sles51180",
    title="Tom Clancy's The Sum of All Fears",
    short="Sum of All Fears",
    serial="SLES-51180",
    boot=BOOT,
    volume_hint="SOAF",
    pcsx2_crc="4691F6F7",
    overlays=[ELF],
    settings=_settings(),
    build_edits=lambda v: [],
    build_pnach=lambda v: [],
    build_data=build_data,
    archive_pattern=r"/(SOAF|MENU)\.IMG$",
    stock_words=STOCK,
    notes=NOTES,
    ui_art={"archive": "vokes", "patterns": [r"\.RSB$"]},
)

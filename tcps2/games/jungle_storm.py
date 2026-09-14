"""Tom Clancy's Ghost Recon: Jungle Storm (PS2, SLUS-20820) -- profile.

The same Red Storm engine as Ghost Recon PS2, with a smaller boot ELF and two
overlay blobs in an `MWo3` container. Those overlays turned out to be the Fonix
speech-recognition engine and the Ubi.com lobby client -- no gameplay in either
-- so unlike Rainbow Six 3 the thing to patch here is the boot executable.

Jungle Storm is the one game of the three with a **named, editable enemy count**.
Its Defend game type carries `Recruit enemy count`, `Veteran enemy count` and
`Elite enemy count` as script variables, shipping at 20/25/35 single player and
30/40/50 in co-op. That is the closest thing either Ghost Recon has to a
built-in wave-size dial, and it is a direct edit rather than a code patch.

Two differences from Ghost Recon worth knowing, both measured:

  * Jungle Storm's executable is **stripped** -- the symbol table is present but
    empty -- so its addresses were recovered by matching code signatures against
    the unstripped Ghost Recon build and walking the call graph from there.
  * It **flattened the skill ladder**. Ghost Recon names templates by tier
    (`_rec_`/`_vet_`/`_eli_`); Jungle Storm names them by appearance and leaves
    almost every placed enemy at the bottom of the stat range. So tier promotion
    does not exist here and the skill dial edits the numbers directly.
"""

from __future__ import annotations

from ..model import (BOOL, CHOICE, INT, Choice, FileEdit, GameProfile, Overlay,
                     Setting, WordEdit)
from . import rstuning

BASE = 0x00100000
FILE_DELTA = 0x100         # ELF PT_LOAD: VA 0x00100000 lives at file 0x100
FILE_SPAN = 0x00512900 + FILE_DELTA
NOP = 0x00000000

ELF = Overlay(
    name="SLUS_208.20",
    iso_pattern=r"/SLUS_208\.20$",
    base_va=BASE,
    kind="raw",
    file_delta=FILE_DELTA,
    file_span=FILE_SPAN,
)

STOCK = {
    0x00431930: 0x24050014,   # addiu a1, zero, 20   bullet-hole array
    0x0043194C: 0x2A020014,   # slti  v0, s0, 20     its clear-loop bound
    0x00245E4C: 0x3C0341F0,   # lui v1, 0x41f0       30.0f decal lifetime
    0x00245F28: 0x3C024000,   # lui v0, 0x4000       2.0f short-lived surfaces
    0x00245EF8: 0x1000000F,   # b                    unknown surface -> no decal
    0x00423B08: 0x1440000B,   # bne  EffMgrPS2::PreRender
    0x00423E60: 0x14400024,   # bne  hot air / heat haze
    0x00424D70: 0x1440007C,   # bne  night vision
    0x00427BA4: 0x10400005,   # beq  SnowEffectPS2 ctor (inverted sense)
    0x00388958: 0x28420003,   # slti ToggleCameraView wrap
}

DECAL_LIFE = {"stock": None, "120": 0x3C0342F0, "1000": 0x3C03447A}
SHORT_LIFE = {"stock": None, "120": 0x3C0242F0, "1000": 0x3C02447A}

NOTES = (
    "Jungle Storm keeps its enemies in data. The population options rewrite the "
    "game's own mission and game-type files; the originals are copied beside the "
    "ISO first and “Restore disc” puts every one back at the byte it "
    "came from.\n\n"
    "Shipping totals across the 21 missions with an order of battle: 657 enemies "
    "on Easy, 804 on Normal, 955 on Hard and Elite. That spread is the per-actor "
    "difficulty suppression flags.\n\n"
    "Defend is the mode with a real enemy-count dial -- the game type names its "
    "three counts as script variables, 20/25/35 solo and 30/40/50 in co-op.\n\n"
    "The render options patch the boot executable. Its symbol table is stripped, "
    "so those addresses were recovered by matching code against the unstripped "
    "Ghost Recon build; every stock word is checked before anything is written, "
    "but none has been watched working in a running game."
)


def _settings():
    return [
        # ---- defend waves -----------------------------------------------
        Setting("js_defend_enable", "Set the Defend enemy counts", BOOL, False,
                "Enemy Waves", confidence="applied",
                help="Defend is the one mode in either Ghost Recon whose enemy "
                     "counts are named, editable numbers rather than placed "
                     "actors. Ships at 20/25/35 for single player and 30/40/50 "
                     "for co-op.", touches="data"),
        Setting("js_defend_recruit", "Recruit difficulty", INT, 20, "Enemy Waves",
                minimum=5, maximum=200, unit="enemies", confidence="applied",
                requires={"js_defend_enable": True}, touches="data"),
        Setting("js_defend_veteran", "Veteran difficulty", INT, 25, "Enemy Waves",
                minimum=5, maximum=200, unit="enemies", confidence="applied",
                requires={"js_defend_enable": True}, touches="data"),
        Setting("js_defend_elite", "Elite difficulty", INT, 35, "Enemy Waves",
                minimum=5, maximum=200, unit="enemies", confidence="applied",
                requires={"js_defend_enable": True},
                caution="These are total enemies for the whole round. Raising "
                        "all three a long way has not been tested for framerate.",
                touches="data"),

        # ---- enemies ----------------------------------------------------
        Setting("js_all_difficulties", "Every soldier on every difficulty", BOOL,
                False, "Enemies", confidence="applied",
                help="The game removes soldiers on lower difficulties with "
                     "per-actor Easy/Normal/Hard flags. Deleting them puts the "
                     "full Hard force into every mission at every setting -- "
                     "657 enemies becomes 955 across the campaign.",
                caution="Rewrites 18 mission files inside GR.IMG.", touches="data"),
        Setting("js_reveal_hidden", "Spawn the script-held reinforcements", BOOL,
                False, "Enemies", confidence="experimental",
                help="Actors that ship with Hidden=\"1\" wait for a mission "
                     "script. This puts them on the map from the start.",
                caution="An actor a script expects to spawn later may behave "
                        "oddly when it is already there.", touches="data"),
        Setting("js_skill", "Extra enemy skill", INT, 0, "Enemies",
                minimum=0, maximum=4, unit="points", confidence="applied",
                help="Adds to armour, weapon skill, stamina, stealth and "
                     "leadership in every hostile template. Jungle Storm leaves "
                     "almost every placed enemy at the bottom of the range, so "
                     "this has more room here than it does in Ghost Recon. Only "
                     "templates used by non-allied companies are touched.",
                caution="Two points is already a large jump from the shipped "
                        "values.", touches="data"),

        # ---- bullet holes -----------------------------------------------
        Setting("js_decal_pool", "Bullet holes kept on screen", INT, 20,
                "Bullet Holes", minimum=20, maximum=400, unit="holes",
                confidence="experimental",
                help="A 20-entry ring, with a separate clear-loop bound that "
                     "has to move with it. Note the bound is a different "
                     "instruction here than in Ghost Recon, so the two games "
                     "genuinely need different words."),
        Setting("js_decal_life", "How long bullet holes last", CHOICE, "stock",
                "Bullet Holes", confidence="experimental",
                choices=[Choice("stock", "Stock (30 seconds)", ""),
                         Choice("120", "2 minutes", ""),
                         Choice("1000", "Until the pool wraps", "")]),
        Setting("js_decal_short", "Also extend the short-lived surfaces", BOOL,
                False, "Bullet Holes", confidence="experimental",
                requires={"js_decal_life": ("120", "1000")},
                help="Three surface types get a 2-second hole instead of 30."),
        Setting("js_decal_everywhere", "Bullet holes on every surface", BOOL,
                False, "Bullet Holes", confidence="experimental",
                help="Removes the early-out that draws nothing on a surface "
                     "type the decal code does not recognise.",
                caution="Untested, and the most invasive of the decal options."),

        # ---- split screen -----------------------------------------------
        Setting("js_ss_effects", "Restore split-screen effects", BOOL, False,
                "Split Screen", confidence="experimental",
                help="Like Ghost Recon, the engine keeps a reduced render path "
                     "for split screen -- here it drops bullet holes and "
                     "foliage. These are the pre-render, heat-haze, "
                     "night-vision and snow gates: the creation and update side, "
                     "which does not touch how the viewports are set up.",
                caution="The main render gate was deliberately left out. "
                        "Forcing it skips the second viewport's setup."),

        # ---- camera -----------------------------------------------------
        Setting("js_extra_cameras", "Unlock the chase and ghost cameras", BOOL,
                False, "World", confidence="experimental",
                help="The camera cycle wraps at 3 of the 5 modes the engine "
                     "defines. This raises the wrap so chase and ghost join in."),
    ] + rstuning.cards("js_")


def build_edits(v: dict) -> list:
    e = []

    def w(va, value, note):
        e.append(WordEdit(va, value, STOCK[va], note))

    pool = int(v.get("js_decal_pool", 20))
    if pool != 20:
        w(0x00431930, 0x24050000 | (pool & 0xFFFF), "bullet-hole pool = %d" % pool)
        w(0x0043194C, 0x2A020000 | (pool & 0xFFFF), "bullet-hole clear loop = %d" % pool)

    life = v.get("js_decal_life", "stock")
    if DECAL_LIFE.get(life):
        w(0x00245E4C, DECAL_LIFE[life], "bullet-hole lifetime")
        if v.get("js_decal_short"):
            w(0x00245F28, SHORT_LIFE[life], "short-lived surfaces too")
    if v.get("js_decal_everywhere"):
        w(0x00245EF8, NOP, "draw a hole on unrecognised surfaces too")

    if v.get("js_ss_effects"):
        w(0x00423B08, NOP, "split screen: PreRender")
        w(0x00423E60, NOP, "split screen: heat haze")
        w(0x00424D70, NOP, "split screen: night vision")
        # this one is inverted -- the fix is an unconditional branch, not a nop
        w(0x00427BA4, 0x10000005, "split screen: snow constructor")

    if v.get("js_extra_cameras"):
        w(0x00388958, 0x28420006, "camera cycle wraps at 6, not 3")
    return e


def build_data(v: dict) -> list:
    out = []
    if v.get("js_defend_enable"):
        out.append(FileEdit("gtf_variables", r"DEFEND\.GTF$", "GR.IMG",
                            {"values": {
                                "Recruit enemy count": int(v.get("js_defend_recruit", 20)),
                                "Veteran enemy count": int(v.get("js_defend_veteran", 25)),
                                "Elite enemy count": int(v.get("js_defend_elite", 35)),
                            }},
                            "Defend enemy counts"))
    if v.get("js_all_difficulties"):
        out.append(FileEdit("strip_difficulty", r"\.MIS$", "GR.IMG",
                            note="every soldier on every difficulty"))
    if v.get("js_reveal_hidden"):
        out.append(FileEdit("reveal_hidden", r"\.MIS$", "GR.IMG",
                            note="spawn the script-held reinforcements"))
    skill = int(v.get("js_skill", 0))
    if skill:
        out.append(FileEdit("bump_stats", r"\.ATR$", "GR.IMG", {"steps": skill},
                            "+%d to every hostile template's skills" % skill,
                            scope="enemy_templates"))
    out += rstuning.edits("js_", v, "GR.IMG")
    return out


PROFILE = GameProfile(
    id="jungle_storm_slus20820",
    title="Tom Clancy's Ghost Recon: Jungle Storm",
    short="Jungle Storm",
    serial="SLUS-20820",
    boot="SLUS_208.20",
    volume_hint="SLUS_20820",
    pcsx2_crc="DE1E4DEE",
    overlays=[ELF],
    settings=_settings(),
    build_edits=build_edits,
    build_pnach=lambda v: [],
    build_data=build_data,
    archive_pattern=r"/GR\.IMG$",
    stock_words=STOCK,
    notes=NOTES,
    ui_art={"archive": "vokes", "patterns": [r"\.RSB$"]},
)

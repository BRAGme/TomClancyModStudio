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



#: Every mission with an order of battle, in the order the disc plays it.
#:
#: `CAMPAIGN.XML` inside the archive lists the campaign in play order, and each
#: `.MIS` names itself in its own `<Shell>` and `<Engine>` blocks -- codename,
#: location, date and time. Here the two are NOT the same: the Colombia campaign is assembled out of the `G0x` and `U0x` files in a scrambled order, so J01 is `g03_the_rock.mis` and J03 is `u05_rail.mis`. Sorting the filenames would put the campaign in the wrong sequence outright. The `<Name>` numbering and the dates both agree with CAMPAIGN.XML instead.
#:
#: The last field is the briefing's tactical map, which the port renamed when it
#: cooked it: `m09_swamp.mis` asks for `M09_SWAMPS.RSB`. So the image name is
#: recorded rather than derived, and a test checks every one of them is really
#: in the archive.
#:
#: (stem, number, codename, place, date, time, soldiers, held back on Easy, map)
MISSIONS = (
    ("C01_PLANTATION", "C01", "Watchful Yeoman", "Punta Tabacal", "March 20, 2010", "06:30", 48, 13, "C01_PLANTATION"),
    ("C02_MILITARY_CAMP", "C02", "Angel Rage", "Pinar del Rio", "April 3, 2010", "19:30", 50, 19, "C02_MILITARY_CAMP"),
    ("C03_HIGH_SIERRA", "C03", "Jaguar Maze", "Sierra de los Organos", "Apr. 12, 2010", "11:20", 47, 19, "C03_HIGH_SIERRA"),
    ("C04_SWAMP_AIRFIELD", "C04", "Hidden Spectre", "Cabo Pepe, Isla de la Juventud", "Apr. 21, 2010", "10:40", 55, 28, "C04_SWAMP_AIRFIELD"),
    ("C05_BRIDGES", "C05", "Rapid Python", "Sierra de los Organos", "April 27, 2010", "01:00", 50, 14, "C05_BRIDGES"),
    ("C06_POLLING_CENTER", "C06", "Liberty Storm", "Cienfuegos", "May 12, 2010", "06:45", 51, 12, "C06_POLLING_CENTER"),
    ("C07_BEACH_RESORT", "C07", "Ocean Forge", "Northwest Cuba, Near Dimas", "May 19, 2010", "11:45", 54, 14, "C07_BEACH_RESORT"),
    ("C08_MOUNTAIN_STRONGHOLD", "C08", "Righteous Archer", "Sierra de los Organos", "June 6, 2010", "08:20", 55, 13, "C08_MOUNTAIN_STRONGHOLD"),
    ("G03_THE_ROCK", "J01", "Totem Ground", "Alta Magdalena", "Aug. 01, 2010", "15:20", 70, 36, "G03_THE_ROCK"),
    ("G04_TRAIN", "J02", "Vapor Knife", "Cienaga Grande", "August 13, 2010", "08:15", 72, 20, "G04_TRAIN"),
    ("U05_RAIL", "J03", "Ocelot Desert", "Tatacoa Desert", "Aug. 17, 2010", "22:00", 54, 3, "U05_RAIL"),
    ("G02_VILLAGE", "J04", "Ocean Hammer", "Buenaventura, Valle de Cauca", "Aug. 28, 2010", "09:00", 72, 9, "G02_VILLAGE"),
    ("G05_DOCK", "J05", "Titan Bolt", "Choco Department", "Sept. 03, 2010", "14:00", 57, 17, "G05_DOCK"),
    ("U02_RIVER", "J06", "Silver Spider", "Meta Department", "Sept. 11, 2010", "20:30", 64, 17, "U02_RIVER"),
    ("U03_RESCUE", "J07", "Whisper Shadow", "Huila Department", "Sept. 28, 2010", "07:45", 76, 39, "U03_RESCUE"),
    ("U01_TRANSMISSION", "J08", "Eagle Clarion", "Caqueta Department", "Oct. 13, 2010", "10:00", 78, 16, "U01_TRANSMISSION"),
    ("TAC01_SHOOTING", "TAC01", "Shooting", "Lubana River", "June 10, 2008", "10:00", 15, 0, "TAC01_SHOOTING"),
    ("TAC02_RESCUE", "TAC02", "Rescue", "South Ossetian Autonomous Region", "May 2, 2008", "15:00", 23, 6, "TAC02_RESCUE"),
    ("TAC03_DEMOLITION", "TAC03", "Demolition", "Severodvinsk, Russia", "Sept. 22, 2008", "09:00", 23, 0, "TAC03_DEMOLITION"),
    ("TAC04_ANTIVEHICLE", "TAC04", "Anti Vehicle", "Venta, Lithuania", "June 24, 2008", "02:15", 6, 0, "TAC04_ANTIVEHICLE"),
    ("TAC05_DEFEND", "TAC05", "Defend", "South Ossetian Autonomous Region", "April 16, 2008", "18:00", 31, 5, "TAC05_DEFEND"),
)

MISSION_GROUP = "Missions"


def mission_key(stem):
    return "mission_" + stem.lower()


def mission_art_for(key):
    """The briefing map this mission's card should show."""
    for mission in MISSIONS:
        if key == mission_key(mission[0]):
            return [mission[8]]
    return []


def mission_select(stem):
    """A regex matching just this mission's script inside the archive."""
    return r"/%s\.MIS$" % stem


def _mission_settings():
    """One switch per mission: put that mission's full force into every
    difficulty, without touching any other mission.

    This is the global "every soldier on every difficulty" switch aimed at one
    file. The figures on each card are counted out of the disc: how many actors
    the mission places, and how many of them carry a flag that removes them
    below Hard. A mission with no flags gets a card that says so and a switch
    that is off, because there is nothing there to release.
    """
    out = []
    for stem, number, title, place, date, time, actors, held, _map in MISSIONS:
        when = ", ".join(x for x in (place, date, time) if x)
        if held:
            help_text = ("%s. %d soldiers placed, %d of them removed below "
                         "Hard. This puts the full Hard force into this "
                         "mission at every difficulty, and nothing else moves."
                         % (when, actors, held))
        else:
            help_text = ("%s. %d soldiers placed, none of them suppressed on "
                         "any difficulty -- this mission already turns out in "
                         "full at every setting." % (when, actors))
        out.append(Setting(
            mission_key(stem), "%s  %s" % (number, title), BOOL, False,
            MISSION_GROUP, help=help_text, touches="data",
            enabled=bool(held),
            disabled_reason=("" if held else
                             "Nothing to release: this mission authors no "
                             "difficulty suppression flags at all, so every "
                             "soldier already turns out at every setting."),
            confidence="measured"))
    return out


def build_data(v: dict) -> list:
    out = []
    # Per-mission first, and skipped entirely when the global
    # switch is on: that one already strips every .MIS, so a
    # per-mission edit on top would be a second pass over a file
    # with nothing left in it to strip.
    if not v.get("js_all_difficulties"):
        for mission in MISSIONS:
            if v.get(mission_key(mission[0])):
                out.append(FileEdit(
                    "strip_difficulty", mission_select(mission[0]),
                    "GR.IMG",
                    note="every soldier in %s %s"
                         % (mission[1], mission[2])))
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
    settings=_settings() + _mission_settings(),
    build_edits=build_edits,
    build_pnach=lambda v: [],
    build_data=build_data,
    archive_pattern=r"/GR\.IMG$",
    stock_words=STOCK,
    mission_art_for=mission_art_for,
    notes=NOTES,
    ui_art={"archive": "vokes", "patterns": [r"\.RSB$"]},
)

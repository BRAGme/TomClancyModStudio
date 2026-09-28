"""Ghost Recon 2 (PS2, SLUS-21105) -- profile.

The name says Ghost Recon, but the disc says Rainbow Six 3. This is not the Red
Storm engine the 2001 Ghost Recon and Jungle Storm run on: it is the same
Unreal-derived PS2 build Rainbow Six 3 and Advanced Warfighter use, and it shows
in every part of the layout -- `SP.SOZ` and `MP.SOZ` compressed overlays, vokes
archives, `.LIN` packages, and an `R6GAMESETTINGS.INI` whose keys and shipped
values are Rainbow Six 3's to the decimal place.

That is why this profile exists at all, and also why it is smaller than Rainbow
Six 3's. Everything here is **data**, not code:

  * `R6GAMESETTINGS.INI` ships three copies across the vokes archives and holds
    the AI tuning and the control curve in plain text. Same keys, same stock
    numbers, so Rainbow Six 3's transforms run on it unmodified.

  * `COMMON.LIN` holds the enemy templates, and the grenade picture in it was
    counted rather than assumed. Of the 73 `NbOfGrenade` tables: 43 always come
    up empty, 18 always spawn a frag grenade, 8 roll a frag against nothing at
    20/15/25/30 percent, 2 always carry a molotov, 1 a smoke, and 1 rolls 10
    percent frag against 10 percent tear gas. The 8 rolled tables are the ones
    with a number in them to change, and they use the same three-digit weighted
    form Rainbow Six 3 uses, so the same digit-for-digit edit works.

    **Two of those gadget classes are dead on this disc.** Searching the
    decompressed `SP.SOZ` and `MP.SOZ` overlays case-insensitively:
    `R6FragGrenadeGadget` appears 4 times, `R6SmokeGrenadeGadget` once,
    `R6TearGasGrenadeGadget` once, `R6PhosphorusGrenadeGadget` once --
    but `R6MolotovGadget` and `R6FlashBangGadget` appear **zero** times, in
    either overlay. The molotov is named in `COMMON.LIN` and in no other package
    on the disc, not even `COMMONOFF.LIN`, which carries every other gadget
    class. Rainbow Six 3's overlay, by contrast, names all six. So the two
    molotov templates here reference a class this build cannot instantiate:
    leftovers from the Rainbow Six 3 codebase, not content.

    The throwing machinery itself is real. `COMMON.LIN`'s script name table
    registers `ServerThrowGrenade`, `CanThrowGrenade`, `TooCloseToThrowGrenade`,
    `GrenadeWasThrown`, `GetSaveDistanceToThrow` and
    `m_bThrowGrenadeWithLeftHand`, the animation table has `StandPullPin` and
    `StandThrowGrenade`, and `m_fMinDistToThrowGrenade` is a registered
    variable. `ThrowGrenade` appears 5 times in `SP.SOZ` and twice in `MP.SOZ`.

What is **not** here is the wave system, the render switches and the split-screen
fixes. Those are virtual addresses inside Rainbow Six 3's `SP.SOZ`, and this is
a different overlay from a different build a year later. Reusing them would
write into whatever happens to sit at those offsets. Ghost Recon 2's own overlay
has not been mapped, so the tool offers nothing that pretends to.
"""

from __future__ import annotations

from ..model import (BOOL, CHOICE, INT, Choice, FileEdit, GameProfile, Overlay,
                     Setting)
from . import r6tuning
from .. import rseloadout

#: the COMMON containers that carry the 73 enemy templates
COMMON_FILES = r"/COMMON(OFF)?\.LIN$"

BOOT = "SLUS_211.05"

#: the boot ELF, for detection and for the CRC check. Two program headers; the
#: loaded one is at file +0x80 and maps to 0x01400000.
ELF = Overlay(
    name=BOOT,
    iso_pattern=r"/SLUS_211\.05$",
    base_va=0x01400000,
    kind="raw",
    file_delta=0x80,
    file_span=0x00024200 + 0x80,
)

STOCK = {}

#: read out of this disc's own R6GAMESETTINGS.INI, not assumed from Rainbow Six
SKILL_SETS = {
    "stock": ("0.20", "0.70", "1.25"),
    "up":    ("0.28", "0.98", "1.75"),
    "elite": ("1.25", "1.25", "1.25"),
    "down":  ("0.12", "0.42", "0.75"),
}
GRENADE_DELAYS = {
    "stock":   ("1.0", "0.5"),
    "quick":   ("0.5", "0.25"),
    "instant": ("0.1", "0.05"),
}
FIRE_DELAYS = {
    "stock": ("1.0", "0.5"),
    "quick": ("0.5", "0.25"),
    "snap":  ("0.15", "0.1"),
}
SENS_BASE = {"x_mult": 0.70, "y_mult": 0.60, "x_step": 0.15, "y_step": 0.15}

NOTES = (
    "Ghost Recon 2 is a Rainbow Six 3 disc wearing a Ghost Recon badge. It has "
    "SP.SOZ and MP.SOZ overlays, vokes archives and .LIN packages -- the "
    "Rainbow Six 3 layout exactly, and nothing like the Red Storm engine the "
    "2001 Ghost Recon and Jungle Storm run on.\n\n"
    "Because of that, its R6GAMESETTINGS.INI is Rainbow Six 3's file: the same "
    "keys, shipping the same numbers, in three copies across the archives. Its "
    "COMMON.LIN carries 73 weapon-and-grenade tables in the same format. Both "
    "read and write correctly here, which is what the Enemies and Controls "
    "pages are built on.\n\n"
    "On grenades: the throwing machinery is real -- the script name table "
    "registers ServerThrowGrenade, CanThrowGrenade, TooCloseToThrowGrenade and "
    "GrenadeWasThrown, the animation table has StandPullPin and "
    "StandThrowGrenade, and m_fMinDistToThrowGrenade is a live variable. But "
    "two gadget classes the templates name are NOT in this build: "
    "R6MolotovGadget and R6FlashBangGadget appear zero times in either "
    "overlay, while frag, smoke, tear gas and phosphorus all appear. Rainbow "
    "Six 3's overlay names all six. So the molotov and flashbang templates "
    "here are leftovers from that codebase and cannot spawn. Frags can, and "
    "the reason you may never have seen one thrown is the 500-unit minimum "
    "throw distance rather than the carry chance.\n\n"
    "There are no code options. Rainbow Six 3's wave, render and split-screen "
    "patches are addresses inside ITS overlay; this is a different build and "
    "those offsets mean something else in it. This disc's overlay has not been "
    "mapped, so there is nothing honest to put on a Waves page yet.\n\n"
    "Everything on the two editing pages here is a plain-text edit to a file "
    "inside the archives, backed up before it is written and reversible from "
    "Restore disc.\n\n"
    "The Missions page reads rather than edits. Rainbow Six 3's equivalent "
    "works because that disc authors m_iMinTerrorist and m_iMaxTerrorist into "
    "its levels; Ghost Recon 2 runs the same engine and authors neither. That "
    "was searched rather than assumed: the locator that finds 458 counts "
    "across Rainbow Six 3's campaign finds ZERO across all fourteen campaign "
    "levels and the training level, and none of those packages exports an "
    "enemy actor either. They spawn from mission script instead -- "
    "Action_SpawnTerrorist is a registered script name in them -- so there is "
    "no number to scale.\n\n"
    "The order on that page is worth a note, because it is not the one the "
    "file names suggest: S02_02 is the second mission and S01_02 the sixth. "
    "R6MENUS.INT gives every mission a date, time and weather line, and those "
    "dates run from 2007-07-06 to 2007-12-22 without going backwards. The "
    "titles come off the levels' own loading screens.\n\n"
    "No wave mode, and no dial for a bigger starting garrison either. Both "
    "were looked for properly. Rainbow Six 3's system is R6DZoneWave actors "
    "placed in the levels; this disc exports none, and nothing here names "
    "GR3DeploymentZone or m_iNbToSpawn. The words FirstWave, secondwave, "
    "thirdwave, Reinforce1..4 and Reinforcementa..d DO appear in the level "
    "packages, which looks promising until you see what they are: script tags "
    "a designer typed for a trigger in one level, not an engine feature with "
    "numbers behind it.\n\n"
    "As for spawning more to begin with, the whole campaign authors twenty "
    "terrorist-count properties: one in S02_01, five in S02_03 and fourteen in "
    "S03_05 -- and all fourteen of those read zero, which on this engine means "
    "an individual rather than a group. Six usable numbers in fourteen levels "
    "is not something to put a dial on. The enemies are placed one at a time "
    "by each level's own script.\n\n"
    "One thing the savestates settled: the copy the game actually loads is "
    "GR2.IMG's. Its m_fXSensitivityMultiplier reads 0.70 where both VOKES "
    "copies say 0.60, and 0.70 is what turns up in the engine's parsed cache "
    "in memory. The tool writes all three copies, so this changes nothing in "
    "practice -- but it is the reason to keep writing all three."
)


def _settings():
    return [
        # ---- enemies -----------------------------------------------------
        Setting("gr2_grenade_carry", "How many enemies carry a grenade", INT,
                20, "Enemies", minimum=0, maximum=100, unit="%",
                confidence="applied", touches="data",
                help="What an enemy spawns holding is a weighted roll made "
                     "once, at spawn, over a small table in his template. "
                     "Eight of this disc's 73 tables roll a FRAG grenade "
                     "against nothing, at 20, 15, 25 and 30 percent, and this "
                     "sets that share. A further 18 always spawn a frag. The "
                     "frag class is live: it is in both overlays, and four of "
                     "the ten ST*_MAP_C multiplayer packages name it.",
                caution="If you have never seen an enemy throw one, the dial "
                        "below is the likelier reason than this one -- an NPC "
                        "will not throw at anything closer than 500 units, and "
                        "in tight rooms that rules out most fights. There is no "
                        "separate throw chance; once he is holding one the "
                        "decision is deterministic."),
        Setting("gr2_grenade_dist", "How close enemies will throw grenades",
                INT, 500, "Enemies", minimum=25, maximum=900, unit="units",
                confidence="experimental", touches="data",
                help="The variable the engine checks before letting an enemy "
                     "throw. It ships at 500 -- far enough that a lot of this "
                     "game's fights never qualify -- and the theory is that "
                     "dropping it to 150-250 brings grenades into rooms "
                     "instead of only across open ground.",
                caution="Play-tested at 80 and nothing changed, so treat this "
                        "as unproven. What HAS been checked: the key is "
                        "registered in this disc's own script, the overlay "
                        "names R6GAMESETTINGS.ini, the edit lands in all "
                        "three copies, no memory-card save carries an "
                        "overriding value, and a savestate shows the engine "
                        "keeps a parsed copy of that file in memory. So the "
                        "number reaches the game and the behaviour did not "
                        "follow, which points at the variable being one more "
                        "of the Rainbow Six 3 leftovers this build registers "
                        "without using -- like the two dead gadget classes on "
                        "the Loadout page. research/code/p2s.py reads that "
                        "cache out of a savestate if you want to confirm the "
                        "80 arrived."),
        Setting("gr2_grenade_delay", "How long they think about it first",
                CHOICE, "stock", "Enemies", confidence="applied",
                touches="data",
                choices=[
                    Choice("stock", "Stock (1.0s recruit, 0.5s veteran)", ""),
                    Choice("quick", "Quicker (0.5s / 0.25s)",
                           "Roughly twice as many grenades per fight."),
                    Choice("instant", "Barely any (0.1s / 0.05s)",
                           "They throw the moment they have a reason to."),
                ],
                help="The reaction delay before an enemy commits to a throw."),
        Setting("gr2_fire_delay", "How fast they open fire", CHOICE, "stock",
                "Enemies", confidence="applied", touches="data",
                choices=[
                    Choice("stock", "Stock (1.0s recruit, 0.5s veteran)", ""),
                    Choice("quick", "Quicker (0.5s / 0.25s)", ""),
                    Choice("snap", "Almost instant (0.15s / 0.1s)",
                           "They shoot as soon as they see you. Hard."),
                ],
                help="The pause between an enemy acquiring you and pulling the "
                     "trigger. This is the biggest single lever on how "
                     "dangerous a firefight feels."),
        Setting("gr2_skill", "Enemy skill", CHOICE, "stock", "Enemies",
                confidence="applied", touches="data",
                choices=[
                    Choice("stock", "Stock (0.20 / 0.70 / 1.25)", ""),
                    Choice("up", "Sharper (+40%)", ""),
                    Choice("elite", "Everyone near-elite",
                           "All three tiers at 1.25, so recruits shoot like "
                           "elites do."),
                    Choice("down", "Softer (-40%)", ""),
                ],
                help="The per-difficulty multiplier the AI scales its aim and "
                     "its reactions by."),
        Setting("gr2_perfect_dist", "Range at which enemies never miss", INT,
                500, "Enemies", minimum=50, maximum=3000, unit="units",
                confidence="applied", touches="data",
                help="Inside this distance an enemy's shots have no dispersion "
                     "at all. It ships at 500."),
        Setting("gr2_sight", "How far enemies can see you", INT, 5000,
                "Enemies", minimum=500, maximum=15000, unit="units",
                confidence="applied", touches="data",
                help="The spotting radius every enemy searches inside. It ships "
                     "at 5000. Raising it makes open ground genuinely "
                     "dangerous; lowering it makes stealth much easier.",
                caution="This is the raw radius. The movement penalties still "
                        "apply on top of it, so the practical distance is "
                        "shorter when you are still and longer when you run."),

    ] + r6tuning.cards(["search_time", "speed", "spotting", "toughness"], "gr2_",
                       "Enemies") + rseloadout.cards(
        "gr2_slus21105", "gr2_", "Enemies") + [

        # ---- your loadout ------------------------------------------------
        Setting("gr2_player_grenades", "Grenades you carry", INT, 1, "Loadout",
                minimum=1, maximum=10, unit="x", confidence="applied",
                touches="data",
                help="The AMMO MULTIPLIERS block scales what you start a "
                     "mission holding. Grenades ship at 1x on all three "
                     "difficulties -- the loadout you picked and nothing more. "
                     "Raising it multiplies every grenade in that loadout.",
                caution="This multiplies the loadout, so it does nothing for a "
                        "kit you sent out with no grenades in it."),
    ] + r6tuning.cards(["player_mags"], "gr2_", "Loadout") + [

        # ---- controls ----------------------------------------------------
        Setting("gr2_sens_steps", "Look sensitivity ceiling", INT, 10,
                "Controls", minimum=10, maximum=30, unit="steps",
                confidence="applied", touches="data",
                help="The in-game sensitivity slider stops at 10. This raises "
                     "how far it goes, so there are faster settings to pick "
                     "than the game normally offers."),
        Setting("gr2_sens_boost", "Look speed at each step", INT, 100,
                "Controls", minimum=50, maximum=400, unit="%",
                confidence="applied", touches="data",
                help="Scales the sensitivity multiplier and the per-step "
                     "increment together, so every notch on the slider moves "
                     "the camera further. 100% is stock."),
    ]



#: The campaign in the order the game plays it, which is **not** the order the
#: level names suggest: `S02_02` is the second mission and `S01_02` the sixth.
#:
#: The disc settles it. `R6MENUS.INT` gives every mission a date, time and
#: weather line, and its keys run in an order whose dates never go backwards --
#: 2007-07-06 through 2007-12-22. The titles are the game's own too: each
#: mission's loading screen, `/DI/EN/LOADING<stem>.EN`, prints its name across
#: the top, and those are the names below. A test re-reads the dates off the
#: disc and checks this table against them.
#:
#: (stem, title, date, time, weather, objectives)
MISSIONS = (
    ("S01_01", "Tank Ambush", "2007-07-06", "11:15", "clear", 2),
    ("S02_02", "Broken Wings", "2007-07-07", "07:00", "stormy", 3),
    ("S01_03", "Village Hunt", "2007-07-07", "20:00", "clear", 1),
    ("S01_04", "Convoy Strike", "2007-07-07", "23:30", "rain", 4),
    ("S02_01", "Refinery Assault", "2007-07-08", "19:45", "clear", 3),
    ("S01_02", "Caged Tiger", "2007-07-08", "20:30", "clear", 3),
    ("S02_03", "Bird Down", "2007-07-09", "19:30", "clear", 3),
    ("S02_04", "Holding On", "2007-07-09", "20:30", "clear", 1),
    ("S02_05", "Tides of War", "2007-07-10", "15:45", "clear", 2),
    ("S03_01", "Command Siege", "2007-11-14", "17:30", "clear", 3),
    ("S03_02", "Cargo Raid", "2007-11-27", "02:00", "clear", 2),
    ("S03_03", "Medusa", "2007-12-01", "15:15", "clear", 3),
    ("S03_04", "Death Train", "2007-12-20", "10:30", "snow", 3),
    ("S03_05", "Paik's Revenge", "2007-12-22", "06:30", "blizzard", 2),
)

#: every campaign level ships three times, one per game type the menu offers
GAME_TYPES = (("Mission", "OFF"), ("Fire Fight", "_FFOFF"),
              ("Lone Wolf", "_LWOLF"))

MISSION_GROUP = "Missions"

#: where the menu text lives, for the tests that check the table against it
MENUS = "/LOCALIZE/R6MENUS.INT"


def mission_key(stem):
    return "mission_" + stem.lower()


def mission_art_for(key):
    """The art base name for a mission card -- the level's own loading screen."""
    for stem, *_rest in MISSIONS:
        if key == mission_key(stem):
            return [stem]
    return []


def mission_select(stem):
    """A regex matching every package this mission ships -- all three types."""
    return r"/%s(OFF|_FFOFF|_LWOLF)\.LIN$" % stem


def _mission_settings():
    """One card per mission: the level's own loading screen, what the disc says
    about it, and a dial that is switched off because there is nothing to turn.

    Rainbow Six 3's Missions page edits for real because that disc authors
    `m_iMinTerrorist` and `m_iMaxTerrorist` into its levels. Ghost Recon 2 runs
    the same engine and authors neither: across all fourteen campaign levels
    and the training level, the count locator finds **zero** sites, and no
    enemy actor class is exported by any of them. The enemies come from mission
    script instead -- `Action_SpawnTerrorist` is a registered script name in
    these packages -- so there is no authored number to scale.
    """
    out = []
    for stem, title, date, time, weather, objectives in MISSIONS:
        out.append(Setting(
            mission_key(stem), "%s  %s" % (stem.replace("_", "-"), title),
            INT, 100, MISSION_GROUP, minimum=25, maximum=400, unit="%",
            help="%s %s, %s. %d objective%s. Ships three times, one per game "
                 "type: Mission, Fire Fight and Lone Wolf."
                 % (date, time, weather, objectives,
                    "" if objectives == 1 else "s"),
            touches="data", enabled=False,
            disabled_reason=(
                "Reading only -- these levels author no enemy counts at all, "
                "so there is nothing for a dial to change. See About this "
                "disc."),
            confidence="broken"))
    return out


def build_data(v: dict) -> list:
    """Ghost Recon 2 keeps its AI tuning and its control curve in plain text."""
    out = []
    ini = {}

    if int(v.get("gr2_grenade_dist", 500)) != 500:
        ini["m_fMinDistToThrowGrenade"] = int(v["gr2_grenade_dist"])
    delay = v.get("gr2_grenade_delay", "stock")
    if delay != "stock":
        rec, vet = GRENADE_DELAYS[delay]
        ini["m_fGrenadeReactionDelayRecruit"] = rec
        ini["m_fGrenadeReactionDelayVeteran"] = vet
    fire = v.get("gr2_fire_delay", "stock")
    if fire != "stock":
        rec, vet = FIRE_DELAYS[fire]
        ini["m_fReactionTimeForFiringRecruit"] = rec
        ini["m_fReactionTimeForFiringVeteran"] = vet
    skill = v.get("gr2_skill", "stock")
    if skill != "stock":
        rec, vet, eli = SKILL_SETS[skill]
        ini["m_fTerroristSkillMultiplierRecruit"] = rec
        ini["m_fTerroristSkillMultiplierVeteran"] = vet
        ini["m_fTerroristSkillMultiplierElite"] = eli
    if int(v.get("gr2_perfect_dist", 500)) != 500:
        ini["m_fDistForPerfectAccuracyTerro"] = "%.1f" % float(v["gr2_perfect_dist"])
    if int(v.get("gr2_sight", 5000)) != 5000:
        ini["m_fSightRadius"] = "%.1f" % float(v["gr2_sight"])
    # the dials shared with Rainbow Six 3 and Advanced Warfighter; the keys
    # that overlap with the lines above resolve to the same value.
    ini.update(r6tuning.ini_updates("gr2_", v))
    steps = int(v.get("gr2_sens_steps", 10))
    if steps != 10:
        ini["m_iXSensitivityMaxSteps"] = steps
        ini["m_iYSensitivityMaxSteps"] = steps
    boost = int(v.get("gr2_sens_boost", 100)) / 100.0
    if abs(boost - 1.0) > 0.001:
        ini["m_fXSensitivityMultiplier"] = "%.3f" % (SENS_BASE["x_mult"] * boost)
        ini["m_fYSensitivityMultiplier"] = "%.3f" % (SENS_BASE["y_mult"] * boost)
        ini["m_fXSensitivityStepIncrement"] = "%.3f" % (SENS_BASE["x_step"] * boost)
        ini["m_fYSensitivityStepIncrement"] = "%.3f" % (SENS_BASE["y_step"] * boost)

    if ini:
        out.append(FileEdit("ini_values", r"/R6GAMESETTINGS\.INI$", "",
                            {"values": ini}, "AI and control settings"))
    carry = int(v.get("gr2_grenade_carry", 20))
    if carry != 20:
        out.append(FileEdit("grenade_carry", r"/COMMON(OFF)?\.LIN$", "",
                            {"percent": carry},
                            "%d%% of two-entry templates carry a grenade" % carry))
    out += rseloadout.edits(v, "gr2_", COMMON_FILES)
    return out


PROFILE = GameProfile(
    id="gr2_slus21105",
    title="Tom Clancy's Ghost Recon 2",
    short="Ghost Recon 2",
    serial="SLUS-21105",
    boot=BOOT,
    volume_hint="GHOSTRECON2",
    pcsx2_crc="82E1D0EA",
    overlays=[ELF],
    settings=_settings() + _mission_settings(),
    build_edits=lambda v: [],
    build_pnach=lambda v: [],
    build_data=build_data,
    archive_pattern=r"/(VOKES\d|GR2)\.IMG$",
    stock_words=STOCK,
    notes=NOTES,
    mission_art_for=mission_art_for,
    ui_art={"archive": "iso", "fbz": [r"/DI/LE/LOADING/EN/.*\.FBZ$"]},
)

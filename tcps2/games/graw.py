"""Ghost Recon Advanced Warfighter (PS2, SLUS-21422) -- profile.

It carries the Ghost Recon name, but this is **not** the Red Storm engine the
other two Ghost Recons run. It is Rainbow Six 3's: volume id `GR3`, Rainbow Six
3's disc layout down to `VOKES*.IMG` and `GVS.DAT`, and an overlay carrying
Rainbow Six 3's class names.

It does **not**, however, inherit Rainbow Six 3's deployment-zone wave system,
and that was worth establishing properly rather than assuming: a scan of all
five archives finds zero occurrences of `m_iNbToSpawn`, `m_NumberInWave`,
`m_bHuntFromStart` or `R6DZoneWave`, and in a package-serialised engine a
property that is never named in a package was never authored. So none of the
Rainbow Six 3 wave patches port. What replaced it is `GR3DeploymentZone` with
`m_iNbOfTerroristToSpawn`, and a wave set called "Endure" that exists in exactly
one file on the disc.

The overlay itself owns exactly **two** spawn numbers, both inside the Tick of
the `ScriptSpawnTerrorists` latent command at `0x0058E430` -- how often it
releases, and how many it releases each time. Everything else about a Survival
round lives in per-level data that has not been decoded. Those two are the dials
below.

`SP.IMG` is a plain uncompressed ELF, so a word patch is an in-place write with
no container to rebuild. Note its PT_LOAD sits at file offset **0x800**, not the
0x80 the other games use -- that was measured from the program header, and
getting it wrong writes 0x780 bytes off target.

Being Rainbow Six 3's engine does pay off in one large way: this disc ships
`R6GAMESETTINGS.INI`, twice, with the same AI keys and the same shipped values
as Rainbow Six 3 and Ghost Recon 2 -- compared key by key across all three, not
assumed. That is where the Enemies, Controls and Loadout pages come from, and
none of it is a code patch. The only value that differs is the look sensitivity
multiplier: 0.60/0.52 here against 0.70/0.60 on the other two, which is why
`SENS_BASE` is per profile.

Its `COMMON.LIN` has no two-entry grenade tables at all, so unlike the other
two there is no grenade-carry share to set -- checked, not assumed.
"""

from __future__ import annotations

from ..model import (CHOICE, INT, Choice, FileEdit, GameProfile, Overlay,
                     Setting, WordEdit)
from . import r6tuning, xboxbuild

BOOT = "SLUS_214.22"

#: the single-player overlay: a plain ELF, unlike Rainbow Six 3's packed one
SP = Overlay(
    name="SP.IMG",
    iso_pattern=r"/SP\.IMG$",
    base_va=0x00100000,
    kind="raw",
    file_delta=0x800,
    file_span=0x00634380 + 0x800,
)

STOCK = {
    0x0058E4BC: 0x3C023F80,   # lui v0, 0x3f80  -- 1.0s between releases
    0x0058E508: 0x24020001,   # addiu v0, zero, 1 -- one enemy per release
}

#: the upper half of an IEEE float; only these bits are settable by `lui`
INTERVALS = {
    "stock": 0x3F80,   # 1.0s
    "0.5": 0x3F00,
    "0.25": 0x3E80,
    "2.0": 0x4000,
}

#: this disc's own shipped look curve. Rainbow Six 3 and Ghost Recon 2 ship
#: 0.70/0.60; Advanced Warfighter is slower out of the box.
SENS_BASE = {"x_mult": 0.60, "y_mult": 0.52, "x_step": 0.15, "y_step": 0.15}

NOTES = (
    "Advanced Warfighter reads correctly and the tool wears its artwork.\n\n"
    "Despite the name this is Rainbow Six 3's engine, not Ghost Recon's -- same "
    "volume id, same disc layout, same class names. But it did not inherit "
    "Rainbow Six 3's deployment-zone wave system: none of the property names "
    "that system needs appears anywhere in the five archives, so none of that "
    "work carries over.\n\n"
    "Its spawner is a mission-script command that releases one enemy per second "
    "until the script's count is used up. Those two numbers are the only spawn "
    "values the executable owns, and they are what the options here change. How "
    "many enemies a given Survival wave asks for lives in the level's own data, "
    "in a container that has not been decoded yet.\n\n"
    "One thing that is NOT in the EXECUTABLE: difficulty does not scale "
    "enemies there at all. The difficulty setting has three readers in the "
    "whole overlay -- two health regeneration gates and one picking between "
    "four authored floats.\n\n"
    "The difficulty that does exist is data. This disc ships "
    "R6GAMESETTINGS.INI twice, holding the same AI keys as Rainbow Six 3 and "
    "Ghost Recon 2 at the same shipped values, and that is what the Enemies, "
    "Controls and Loadout pages edit: skill multipliers, the range inside "
    "which a shot cannot miss, sight radius, how long they hunt after losing "
    "you, how fast they move, what movement does to spotting, the grenade "
    "timings, the look curve and the grenade loadout. All plain text, all "
    "reversible.\n\n"
    "Mission S07 is cut. The executable's level table jumps from s06_b straight "
    "to s08_a, and the briefing list does the same.\n\n"
    "The Missions page reads rather than edits, and the reason is the level "
    "format. Rainbow Six 3 runs this same engine and its Missions page does "
    "edit, because its levels are serialised Unreal packages: the authored "
    "counts sit in them as int properties that can be found by name and "
    "rewritten in place. Advanced Warfighter cooks its levels the other way. A "
    ".DMP is a memory image -- 21 MB with not one package signature in it, a "
    "flat name pool where m_iNbOfTerroristToSpawn appears exactly once with no "
    "value beside it, and live objects carrying raw pointers. Reaching a count "
    "in there needs the class layout out of SP.IMG and then object "
    "identification inside a heap dump, so the page shows the missions and "
    "says so.\n\n"
    "What the page does show is the disc's own table. PREGAMEMENUS.INT holds "
    "the mission-selection screen's list -- a time and a district per entry, "
    "and the level each one loads -- plus the Survival and Enemy Hunt maps, "
    "which is where all 32 cards and their order come from."
)


def _settings():
    return [
        Setting("graw_interval", "How often Survival releases an enemy", CHOICE,
                "stock", "Enemy Waves", confidence="applied",
                choices=[
                    Choice("stock", "Stock -- one per second", ""),
                    Choice("0.5", "Twice as often", ""),
                    Choice("0.25", "Four times as often", ""),
                    Choice("2.0", "Half as often", ""),
                ],
                help="The scripted spawner drips enemies in one at a time on a "
                     "timer. This is that timer, and it is one of only two "
                     "spawn numbers the executable owns."),
        Setting("graw_per_release", "Enemies released each time", INT, 1,
                "Enemy Waves", minimum=1, maximum=8, unit="enemies",
                confidence="experimental",
                help="How many come out on each tick of the timer above. "
                     "Raising it multiplies the arrival rate without touching "
                     "the total a level asks for.",
                caution="The count is handed to UnrealScript, which has not "
                        "been read, so what a level does with more than one at "
                        "a time is a reasonable guess rather than a measured "
                        "fact. Try it one step at a time."),
    ] + r6tuning.cards(
        ["skill", "fire_delay", "perfect_dist", "sight", "search_time",
         "speed", "spotting", "grenade_dist", "grenade_delay"],
        "graw_", "Enemies",
    ) + xboxbuild.cards(xboxbuild.GRAW, "graw_", "Enemies") + r6tuning.cards(["sens_steps", "sens_boost"], "graw_", "Controls") \
      + r6tuning.cards(["player_grenades", "player_mags"], "graw_", "Loadout")



#: The campaign as the mission-selection screen lists it, straight off the disc.
#:
#: `PREGAMEMENUS.INT` carries two parallel blocks: `[MissionName]`, which is
#: what the player reads -- a time of day and a district -- and
#: `[MissionNameIntel]`, which names the level each entry loads. Advanced
#: Warfighter's campaign is one continuous day, so the times are the order, and
#: the two blocks together are the whole table. There is no `S07`: the disc
#: jumps from `S06` to `S08`, in the level files and in the menu list alike.
#:
#: (level, time, district, mission number, objectives that mission authors)
MISSIONS = (
    ("S01_A", "06:30", "Industrial District", 1, 7),
    ("S01_B", "07:00", "Industrial District", 1, 7),
    ("S02_A", "11:05", "Suburbs", 2, 12),
    ("S02_B", "11:30", "Suburbs", 2, 12),
    ("S03_A", "13:00", "Downtown", 3, 8),
    ("S03_B", "16:00", "Downtown", 3, 8),
    ("S04_A", "21:00", "Santa Fe Hills", 4, 7),
    ("S04_B", "22:00", "Santa Fe Hills", 4, 7),
    ("S05_A", "04:00", "Chapultepec Park", 5, 7),
    ("S05_B", "04:30", "Chapultepec Park", 5, 7),
    ("S06_A", "06:30", "Chapultepec Palace", 6, 9),
    ("S06_B", "07:00", "Chapultepec Palace", 6, 9),
    ("S08_A", "08:00", "Shanty Town", 8, 8),
    ("S08_B", "08:30", "Shanty Town", 8, 8),
    ("S09_A", "14:00", "Industrial District", 9, 6),
    ("S09_B", "14:30", "Industrial District", 9, 6),
    ("S10_A", "17:06", "Suburbs", 10, 7),
    ("S10_B", "18:23", "Suburbs", 10, 7),
    ("S11_A", "03:00", "Zocalo Plaza", 11, 12),
    ("S11_B", "04:00", "Zocalo Plaza", 11, 12),
    ("S12_A", "06:00", "Downtown", 12, 4),
    ("S12_B", "08:00", "Downtown", 12, 4),
)

#: the two standalone modes, from the same file's own blocks
EXTRA_MAPS = (
    ("SURVIVAL_03B", "Embassy", "Survival"),
    ("SURVIVAL_05B", "Chapultepec Park", "Survival"),
    ("SURVIVAL_09A", "Train Yard", "Survival"),
    ("SURVIVAL_S11B", "Zocalo Plaza", "Survival"),
    ("SURVIVAL_S12A", "Angel Plaza", "Survival"),
    ("ENEMYHUNT_01B", "Tequila Factory", "Enemy Hunt"),
    ("ENEMYHUNT_02A", "City Centre", "Enemy Hunt"),
    ("ENEMYHUNT_04B", "Sante Fe Hills", "Enemy Hunt"),
    ("ENEMYHUNT_06B", "Barracks", "Enemy Hunt"),
    ("ENEMYHUNT_10A", "Rooftops", "Enemy Hunt"),
)

MISSION_GROUP = "Missions"

#: where the menu text lives, for the tests that check the tables against it
MENUS = "/PREGAMEMENUS.INT"


def mission_key(level):
    return "mission_" + level.lower()


def _mission_settings():
    """One card per map: what the disc calls it, and a dial that is off.

    Rainbow Six 3 runs this same engine and its Missions page edits for real,
    because its levels are serialised Unreal packages -- the authored counts
    sit in them as int properties that can be found by name and rewritten in
    place. Advanced Warfighter cooks its levels the other way. A `.DMP` is a
    **memory image**: 21 MB with not one package signature in it, a flat name
    pool where `m_iNbOfTerroristToSpawn` appears exactly once with no value
    beside it, and live objects carrying raw pointers. Reaching a count in
    there means knowing the class layout out of `SP.IMG` and then identifying
    objects in a heap dump, which is not something to guess at, so the page
    reads rather than writes.
    """
    out = []
    for level, time, district, number, objectives in MISSIONS:
        part = level[-1]
        out.append(Setting(
            mission_key(level),
            "%s  %s  %s" % (level.replace("_", "-"), time, district),
            INT, 100, MISSION_GROUP, minimum=25, maximum=400, unit="%",
            help="Mission %d, part %s -- %s at %s. Mission %d authors %d "
                 "objectives across its parts."
                 % (number, part, district, time, number, objectives),
            touches="data", enabled=False,
            disabled_reason=DMP_REASON, confidence="broken"))
    for level, place, mode in EXTRA_MAPS:
        out.append(Setting(
            mission_key(level), "%s  %s" % (mode, place), INT, 100,
            MISSION_GROUP, minimum=25, maximum=400, unit="%",
            help="%s, played in %s. Chosen from the main menu rather than "
                 "from the campaign." % (mode, place),
            touches="data", enabled=False,
            disabled_reason=DMP_REASON, confidence="broken"))
    return out


DMP_REASON = ("Reading only -- this disc cooks its levels as memory images, "
              "so there is no authored count to change. See About this disc.")


def build_edits(v: dict) -> list:
    e = []
    interval = v.get("graw_interval", "stock")
    if interval != "stock":
        word = 0x3C020000 | INTERVALS[interval]
        e.append(WordEdit(0x0058E4BC, word, STOCK[0x0058E4BC],
                          "Survival spawn interval = %ss" % interval))
    n = int(v.get("graw_per_release", 1))
    if n != 1:
        e.append(WordEdit(0x0058E508, 0x24020000 | (n & 0xFFFF),
                          STOCK[0x0058E508],
                          "%d enemies per release" % n))
    return e


def build_data(v: dict) -> list:
    """Everything on the Enemies, Controls and Loadout pages is one INI file.

    Both copies are rewritten -- the game reads whichever answers first -- and
    an all-default config produces no edit at all, so a stock disc stays stock.
    """
    # The Xbox block first, so any dial the player set themselves overwrites
    # the Xbox value for that key rather than the other way round.
    ini = dict(xboxbuild.ini_updates(xboxbuild.GRAW,
                                     v.get("graw_xbox_tuning", "stock"),
                                     bool(v.get("graw_xbox_extra"))))
    ini.update(r6tuning.ini_updates("graw_", v))
    ini.update(r6tuning.sens_updates("graw_", v, SENS_BASE))
    if not ini:
        return []
    return [FileEdit("ini_values", r"/R6GAMESETTINGS\.INI$", "",
                     {"values": ini}, "AI and control settings")]


PROFILE = GameProfile(
    id="graw_slus21422",
    title="Tom Clancy's Ghost Recon Advanced Warfighter",
    short="Advanced Warfighter",
    serial="SLUS-21422",
    boot=BOOT,
    volume_hint="GR3",
    pcsx2_crc="433B0342",
    overlays=[SP],
    settings=_settings() + _mission_settings(),
    build_edits=build_edits,
    build_pnach=lambda v: [],
    build_data=build_data,
    # GR3_1 and GR3_2 hold every single-player level package and are easy to
    # miss -- this disc has five archives, not the three the others have.
    archive_pattern=r"/(VOKES\d|MENU|GR3_\d)\.IMG$",
    stock_words=STOCK,
    notes=NOTES,
    ui_art={"archive": "iso", "fbz": [r"/CD/LE/GR3_\d\.FBZ$"]},
)

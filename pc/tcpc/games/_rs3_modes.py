r"""Raven Shield's game modes: the four cut ones, and which maps allow what.

## The cut modes, and the route that does NOT work

`system\R6Game.u` exports six game classes that no menu ever offers:
`R6DefendGame`, `R6DefendCoopGame`, `R6ReconGame`, `R6ReconCoopGame`,
`R6SquadDeathmatch` and `R6SquadTeamDeathmatch`. Their mode tokens --
`RGM_DefendMode`, `RGM_DefendCoopMode`, `RGM_ReconMode`, `RGM_ReconCoopMode`,
`RGM_SquadDeathmatch`, `RGM_SquadTeamDeathmatch` -- exist as strings in
`Engine.u` and `R6Game.u`, and are six of the thirty-one `RGM_*` tokens that
**no shipped `.mod` lists**. `RavenShield.ini`'s own server-browser filter
already ships `bDefend=True, bRecon=True, bSquadDeathMatch=True,
bSquadTeamDeathMatch=True`, so the browser is expecting modes the menus never
offer.

The obvious route is to add `m_szGameTypes="RGM_DefendMode"` to a `.mod`.
**That does not work, and it was nearly built here before it was checked.**
`Engine.u`'s `R6ModConfig.AddModSpecificGameModes` is a hardcoded registry of
fourteen token-to-class records, and none of the six cut tokens has one.
`m_szGameTypes` is a FILTER over that registry, never an extension -- so
listing a token the registry does not know is inert.

## The route that does work, and how we know

OpenRVS scans `Mods\*.game` in `OpenCustomMissionWidget.LoadNewGameTypes` and
registers whatever it finds, which bypasses the hardcoded registry entirely. A
descriptor is four keys::

    [OpenRVS.OpenCustomMissionWidget]
    GameType=R6Game.R6DefendGame
    ParentGameType=RGM_TerroristHuntMode
    ButtonText=DEFEND
    HelpString=...

The decisive evidence that the cut classes really run is sitting in this
install: `Mods\GameTypePack.utx` is not a texture package at all -- it is a
**code** package, Unreal 118/14, and its class `VIPDefendGame` has
`R6DefendGame` as its superclass. Somebody is already subclassing the cut
Defend mode and playing it. This profile registers the base classes directly.

Six descriptors ship here (`Assassinate`, `Bots`, `CountDown`, `HostageRandom`,
`StealthWolf`, `VIPDefend`) and every one of them writes the same four keys
into two sections -- the second named for the active mod -- so that is the
shape generated here.

**This needs OpenRVS.** Without it nothing scans `Mods\*.game` and the files
are inert clutter. That is stated on the option rather than detected, and
Revert deletes them either way.

### What the modes need from a map

Read out of the classes' own compiled behaviour rather than assumed: **Defend
needs exactly one hostage** -- it complains at zero and at more than one,
because the hostage *is* the VIP -- and **Recon needs an extraction zone**. So
these modes will start on some maps and not others, which is why the option
says so plainly instead of promising a mode on all 52.

The two co-op variants are deliberately not offered: `R6DefendCoopGame` and
`R6ReconCoopGame` have no members of their own at all.

## Which maps allow which modes

`maps\<Map>.ini` carries, under `[Engine.R6MissionDescription]`, one line per
mode the map permits::

    GameTypes=(package=R6Game,type=R6TerroristHuntGame,maxNb=16)

That is a repeated-key array, which is why `IniLines` exists. Across the 52
shipped map inis, ten training maps have no Terrorist Hunt and eighteen have
no Story Mode.

### A shipped bug, fixed

Two map files name a game class that does not exist. `R6Game.u` exports
`R6DeathMatch`, which is how the other 41 maps spell it; there is no
`R6DeathMatchGame` anywhere in the package.

The damage is not the same on both maps, and the difference is worth stating
because it decides what the option can honestly claim:

* **`dp_desal.ini`** has it in its `GameTypes` line, so Survival is not
  available on that map at all.
* **`dp_desal.ini` and `Boiler_House.ini`** both have it in
  `SkinsPerGameTypes`, so the team skins for Survival name a class that cannot
  be matched. Boiler House's own `GameTypes` line is spelled correctly, so
  Survival does run there.

A census of all 53 map files for classes `R6Game.u` does not export finds
these three lines and nothing else.
"""

from ..model import BOOL, CHOICE, Choice, FileCopy, IniLines, Setting

MAPS = "maps/*.ini"
MISSION_SECTION = "Engine.R6MissionDescription"

#: One `.game` descriptor per cut mode. `parent` is the mode whose rules and
#: menu placement it inherits, copied from how the shipped descriptors pair
#: themselves up (`VIPDefend` -> Terrorist Hunt, `Bots` -> Deathmatch).
CUT_MODES = [
    ("Defend", "R6Game.R6DefendGame", "RGM_TerroristHuntMode", "DEFEND",
     "Hold the position and keep the VIP alive. Cut from the retail menus; "
     "the class needs a map with exactly one hostage, who is the VIP."),
    ("Recon", "R6Game.R6ReconGame", "RGM_LoneWolfMode", "RECON",
     "Reach the extraction zone. Cut from the retail menus; the class needs a "
     "map with an extraction zone."),
    ("SquadDeathmatch", "R6Game.R6SquadDeathmatch", "RGM_DeathmatchMode",
     "SQUAD DEATHMATCH",
     "Deathmatch in squads. Cut from the retail menus, though the server "
     "browser still filters for it."),
    ("SquadTeamDeathmatch", "R6Game.R6SquadTeamDeathmatch",
     "RGM_TeamDeathmatchMode", "SQUAD TEAM DEATHMATCH",
     "Team deathmatch in squads. Cut from the retail menus, though the server "
     "browser still filters for it."),
]

#: the sections a shipped descriptor writes. The second is named for the mod
#: that is running; SupplyDrop is what `openrvs.ini` forces on this install and
#: is what every shipped `.game` here names.
GAME_SECTIONS = ("OpenRVS.OpenCustomMissionWidget",
                 "SupplyDropSP.OpenCustomMissionWidget")

#: modes worth adding to a map that lacks them, with the player cap the other
#: maps use for each
HUNT_MODES = [("R6TerroristHuntGame", 16), ("R6TerroristHuntCoopGame", 16)]
STORY_MODES = [("R6StoryModeGame", 16), ("R6PracticeModeGame", 16),
               ("R6MissionGame", 16)]


def _line(cls, cap):
    return "(package=R6Game,type=%s,maxNb=%d)" % (cls, cap)


def settings():
    return [
        Setting(
            "cut_modes", "Restore the cut game modes", BOOL, False,
            group="Game modes",
            help="Raven Shield ships four finished game modes that no menu "
                 "offers: Defend, Recon, Squad Deathmatch and Squad Team "
                 "Deathmatch. This registers them so they appear in the "
                 "custom-mission list.",
            caution="Needs OpenRVS, which is what scans for these files -- "
                    "without it they sit there doing nothing. Defend needs a "
                    "map with exactly one hostage and Recon needs an "
                    "extraction zone, so neither will start everywhere. "
                    "Nothing retail is modified: four small files are added to "
                    "Mods\\ and Revert deletes them.",
            confidence="experimental", touches="mod"),
        Setting(
            "map_modes", "Which modes each map allows", CHOICE, "stock",
            group="Game modes",
            help="Every map file lists the modes that may be played on it. Ten "
                 "training maps have no Terrorist Hunt and eighteen maps have "
                 "no Story, Practice or Mission mode -- not because they "
                 "cannot support them, but because the list says so.",
            caution="A mode added to a map that has no actors for it may show "
                    "in the menu and then fail to start. This has not been "
                    "watched in a running game.",
            choices=[
                Choice("stock", "Stock", "As shipped."),
                Choice("hunt", "Terrorist Hunt everywhere",
                       "Adds Hunt and Hunt Co-op to every map that lacks them."),
                Choice("all", "Every mode everywhere",
                       "Adds Hunt, Hunt Co-op, Story, Practice and Mission."),
            ],
            confidence="experimental", touches="data"),
        Setting(
            "fix_survival", "Fix Survival on Boiler House and Desalination",
            BOOL, False, group="Game modes",
            help="Both maps name a game class called R6DeathMatchGame. There "
                 "is no such class: the other 41 maps spell it R6DeathMatch. "
                 "On Desalination the bad name is in the mode list itself, so "
                 "Survival cannot be played there at all; on both maps it is "
                 "also in the team-skin line. This corrects the spelling.",
            confidence="experimental", touches="data"),
    ]


def edits(values):
    out = []
    v = values

    if v["cut_modes"]:
        for name, cls, parent, button, blurb in CUT_MODES:
            body = []
            for section in GAME_SECTIONS:
                body += ["[%s]" % section,
                         "GameType=%s" % cls,
                         "ParentGameType=%s" % parent,
                         "ButtonText=%s" % button,
                         "HelpString=%s" % blurb,
                         ""]
            out.append(FileCopy("Mods/%s.game" % name,
                                data=("\r\n".join(body)).encode("cp1252"),
                                note="game mode: " + button))

    mode = v["map_modes"]
    if mode != "stock":
        wanted = list(HUNT_MODES) + (list(STORY_MODES) if mode == "all" else [])
        out.append(IniLines(MAPS, section=MISSION_SECTION, key="GameTypes",
                            add=[_line(c, cap) for c, cap in wanted],
                            note="modes allowed per map"))

    if v["fix_survival"]:
        # Named rather than globbed: exactly these two maps carry the typo, and
        # a glob would quietly start "fixing" any map a future patch spells
        # that way, which is a different decision from the one made here.
        for rel in ("maps/Boiler_House.ini", "maps/dp_desal.ini"):
            for key in ("GameTypes", "SkinsPerGameTypes"):
                out.append(IniLines(rel, section=MISSION_SECTION, key=key,
                                    sub={"type=R6DeathMatchGame,":
                                         "type=R6DeathMatch,"},
                                    note="Survival class spelling in " + key))
    return out

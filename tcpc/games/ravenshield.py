r"""Rainbow Six 3: Raven Shield (PC, Gold edition) -- Unreal Engine 2.

Raven Shield has four independently addressable tiers, and this profile uses
the three that are text:

1. **`config` variables in `system\*.ini` and `Save\Profiles\user.ini`.**
   Unreal only reads a variable from an ini if the class declared it `config`,
   so the useful question is not "what keys are in the file" but "what
   variables are flagged". Every key this profile writes was confirmed flagged
   in the compiled packages, which is why keys that are absent from the shipped
   files can still be added and take effect.
2. **AI templates in `template\*.tpt`** -- 266 plain-text files of
   `Assault=80`-style keys with no section header at all, which is the real AI
   difficulty surface. `DiffLevel` is only a reaction-time knob by comparison.
3. **`Sound.ini`, which is not about sound.** It is the AI HEARING model: how
   far a terrorist hears you per posture and pace, and how far a reload, a
   door or a gunshot carries. The whole stealth economy is in one file.

4. **The compiled `.u` packages**, where weapon and ammunition statistics live
   as tagged property lists. These are rewritten in place at identical width,
   so the file's length never changes and its export table stays valid. The
   property list is parsed from the start of the class rather than searched
   for -- see `tcpc.upackage` for why searching for one is unsafe -- and the
   loadout menu's own stat bars are rewritten to match, so the menu does not
   go on describing the weapon the gun used to be. The modelling is in
   `_rs3_weapons.py`.

**This installation is not stock**, and the tool says so rather than pretending
otherwise: `system\openrvs.ini` carries `ForceStartMod=SupplyDrop`, which
replaces the player pawn, the teammate AI and the player controller classes.
Options that write to `user.ini` still apply; options that reason about stock
class behaviour may not.
"""

from . import _rs3_ammo, _rs3_modes, _rs3_weapons
from ..model import (BOOL, CHOICE, Choice, GameProfile, INPLACE, INT,
                     IniEdit, Layout, Setting)

LAYOUT = Layout(
    signature=[
        "system/R6Weapons.u",
        "system/R6ClassDefines.ini",
        "system/RavenShield.ini",
        "backgrounds/Main_menu_01.tga",
    ],
    exe="system/RavenShield.exe",
    config_dir="system",
    data_dir="system",
)

USER_INI = "Save/Profiles/user.ini"
SOUND_INI = "system/Sound.ini"
COOP_INI = "system/ServerCOOP.ini"
SERVER_INI = "system/Server.ini"
ADVER_INI = "system/ServerADVER.ini"
TEMPLATES = "template/*.tpt"

#: The eight skill stats every AI template carries, all on a 0-100 scale.
SKILLS = ("Assault", "Demolitions", "Electronics", "SSniper", "Stealth",
          "SelfControl", "Leadership", "Observation")

#: The five postures the noise model scores the player on, loudest last.
POSTURES = ("fStandSlow", "fStandFast", "fCrouchSlow", "fCrouchFast", "fProne")

#: Every HUD element that has its own `config` flag.
HUD_KEYS = ("HUDShowCharacterInfo", "HUDShowCurrentTeamInfo",
            "HUDShowOtherTeamInfo", "HUDShowWeaponInfo",
            "HUDShowWaypointInfo", "HUDShowActionIcon", "HUDShowPlayersName")

SETTINGS = [
    # -- Difficulty ------------------------------------------------------
    Setting(
        "terrorists", "Terrorists per round", INT, 25, group="Difficulty",
        minimum=1, maximum=100, unit=" terrorists",
        help="How many the co-operative server spawns. This is the count the "
             "game's own co-op and terrorist-hunt setup uses.",
        confidence="experimental", touches="config"),
    Setting(
        "difficulty", "Difficulty level", CHOICE, "2", group="Difficulty",
        help="What the game's own menu calls Recruit, Veteran and Elite. The "
             "game's description of it is narrow and worth quoting: on Elite "
             "terrorists take less time before shooting. It is a reaction "
             "timer, not a competence setting -- for competence, use the AI "
             "template options.",
        choices=[
            Choice("0", "Recruit", "Terrorists take longest to shoot."),
            Choice("1", "Veteran", ""),
            Choice("2", "Elite", "Terrorists shoot soonest. The default."),
        ],
        confidence="experimental", touches="config"),
    Setting(
        "ai_backup", "Fill empty co-op slots with AI teammates", BOOL, True,
        group="Difficulty", confidence="experimental", touches="config"),
    Setting(
        "friendly_fire", "Friendly fire", BOOL, True, group="Difficulty",
        caution="Multiplayer only. Raven Shield has no single-player "
                "equivalent of this key, so it will not change a campaign "
                "mission.",
        confidence="experimental", touches="config"),

    # -- AI templates ----------------------------------------------------
    Setting(
        "terro_skill", "Terrorist competence", CHOICE, "stock",
        group="AI templates",
        help="Every AI template scores its terrorists on eight stats from 0 "
             "to 100 -- assault, demolitions, electronics, sniping, stealth, "
             "self-control, leadership and observation. The stock templates "
             "sit around 50, with some mission-specific ones at 75. This is "
             "the real difficulty surface; the difficulty level above only "
             "changes how long they wait before firing.",
        choices=[
            Choice("stock", "Stock", "Around 50."),
            Choice("green", "Green", "Two thirds."),
            Choice("hard", "Hardened", "Half again."),
            Choice("elite", "Elite", "Everything at 95."),
        ],
        confidence="experimental", touches="config"),
    Setting(
        "terro_nerve", "Terrorist nerve", CHOICE, "stock",
        group="AI templates",
        help="Each template mixes six personalities that must total 100: "
             "coward, desk jockey, normal, hardened, suicide bomber and "
             "sniper. This shifts the mix without changing the total.",
        choices=[
            Choice("stock", "Stock", "Roughly 10 / 5 / 50 / 20 / 10 / 5."),
            Choice("timid", "Timid",
                   "Cowards and desk jockeys take the hardened share."),
            Choice("fanatic", "Fanatical",
                   "The hardened share takes the cowards', and suicide "
                   "bombers double."),
        ],
        caution="The six must add up to 100 and the tool keeps them adding up, "
                "but nothing here has been watched in a running game.",
        confidence="experimental", touches="config"),
    Setting(
        "terro_helmets", "Terrorists wear helmets", CHOICE, "stock",
        group="AI templates",
        help="A percentage chance per template. Stock is mostly 0, which is "
             "why headshots are so reliable.",
        choices=[
            Choice("stock", "Stock", "Mostly none."),
            Choice("half", "Half of them", ""),
            Choice("all", "All of them", ""),
        ],
        confidence="experimental", touches="config"),

    # -- Stealth ---------------------------------------------------------
    Setting(
        "footsteps", "How far the AI hears you walk", CHOICE, "stock",
        group="Stealth",
        help="Five distances, one per posture: standing slow 300, standing "
             "fast 800, crouching slow 200, crouching fast 400, prone 400. "
             "They are what makes a slow approach worth doing.",
        choices=[
            Choice("stock", "Stock", ""),
            Choice("quiet", "You are quieter", "Halved."),
            Choice("loud", "You are louder", "Doubled."),
            Choice("silent", "Silent", "Zeroed. Nothing hears your feet."),
        ],
        confidence="experimental", touches="config"),
    Setting(
        "gunfire_alert", "How far gunfire and explosions carry", CHOICE,
        "stock", group="Stealth",
        help="Bullet impacts and ricochets reach 1100, an explosion 3000. "
             "Lowering these keeps a firefight local instead of pulling the "
             "whole level onto you.",
        choices=[
            Choice("stock", "Stock", ""),
            Choice("x0.5", "Halved", "Firefights stay local."),
            Choice("x2", "Doubled", "One shot brings the level."),
        ],
        confidence="experimental", touches="config"),
    Setting(
        "quiet_reloads", "Reloading and equipping are quiet", BOOL, False,
        group="Stealth",
        help="A reload carries 500 and swapping equipment 600, both as an "
             "investigate-grade noise. This drops them to a quarter.",
        confidence="experimental", touches="config"),

    # -- Interface -------------------------------------------------------
    Setting(
        "reticule", "Show the crosshair", BOOL, True, group="Interface",
        confidence="experimental", touches="config"),
    Setting(
        "radar", "Show the motion tracker", BOOL, True, group="Interface",
        confidence="experimental", touches="config"),
    Setting(
        "hud", "Show the rest of the HUD", BOOL, True, group="Interface",
        help="Seven elements at once -- character info, both teams' info, "
             "weapon info, waypoints, the action icon and player names. Each "
             "has its own flag; they are moved together because a partial HUD "
             "is rarely what anyone wants.",
        confidence="experimental", touches="config"),
    Setting(
        "aim_assist", "Aim assist", INT, 0, group="Interface",
        minimum=0, maximum=10, unit=" / 10",
        help="Ships at 1 in the template profile and 0 in this installation's "
             "own. The game binds F2 to toggle it, so it is a real feature "
             "rather than a leftover.",
        confidence="experimental", touches="config"),
    Setting(
        "hide_bodies", "Bodies disappear", BOOL, False, group="Interface",
        confidence="experimental", touches="config"),
    Setting(
        "fov", "Field of view", INT, 95, group="Interface",
        minimum=60, maximum=120, unit=" degrees",
        help="Written to the OpenRVS field-of-view key, which is what this "
             "installation actually reads -- it overrides the engine's own "
             "DesiredFOV of 90.",
        confidence="experimental", touches="config"),
] + _rs3_modes.settings() + _rs3_weapons.settings() + _rs3_ammo.settings()

SKILL_SCALE = {"green": 0.66, "hard": 1.5}
NERVE = {
    "timid": {"Coward": 25, "DeskJockey": 15, "Normal": 50, "Hardened": 5,
              "SuicideBomber": 3, "PSniper": 2},
    "fanatic": {"Coward": 2, "DeskJockey": 3, "Normal": 40, "Hardened": 35,
                "SuicideBomber": 15, "PSniper": 5},
}


def build_edits(values):
    out = []
    v = values

    # -- difficulty -------------------------------------------------------
    if v["terrorists"] != 25:
        out.append(IniEdit(COOP_INI, section="Engine.R6ServerInfo",
                           key="NbTerro", value=v["terrorists"], stock="25",
                           note="terrorists per round"))
    if v["difficulty"] != "2":
        for ini in (COOP_INI, SERVER_INI, ADVER_INI):
            out.append(IniEdit(ini, section="Engine.R6ServerInfo",
                               key="DiffLevel", value=v["difficulty"],
                               note="difficulty level"))
    if not v["ai_backup"]:
        out.append(IniEdit(COOP_INI, section="Engine.R6ServerInfo",
                           key="AIBkp", value="False", stock="True",
                           note="AI backup teammates"))
    if not v["friendly_fire"]:
        for ini in (COOP_INI, SERVER_INI, ADVER_INI):
            out.append(IniEdit(ini, section="Engine.R6ServerInfo",
                               key="FriendlyFire", value="False",
                               note="friendly fire"))

    # -- AI templates -----------------------------------------------------
    skill = v["terro_skill"]
    if skill == "elite":
        for stat in SKILLS:
            out.append(IniEdit(TEMPLATES, section="", key=stat, value=95,
                               absent="skip", note="terrorist " + stat))
    elif skill in SKILL_SCALE:
        for stat in SKILLS:
            out.append(IniEdit(TEMPLATES, section="", key=stat,
                               scale=SKILL_SCALE[skill], minimum=0,
                               maximum=100, absent="skip",
                               note="terrorist " + stat))

    nerve = NERVE.get(v["terro_nerve"])
    if nerve:
        for trait, share in nerve.items():
            out.append(IniEdit(TEMPLATES, section="", key=trait, value=share,
                               absent="skip", note="personality: " + trait))

    helmets = {"half": 50, "all": 100}.get(v["terro_helmets"])
    if helmets is not None:
        out.append(IniEdit(TEMPLATES, section="", key="Helmet", value=helmets,
                           absent="skip", note="helmet chance"))

    # -- stealth ----------------------------------------------------------
    feet = {"quiet": 0.5, "loud": 2.0, "silent": 0.0}.get(v["footsteps"])
    if feet is not None:
        for posture in POSTURES:
            out.append(IniEdit(SOUND_INI, section="R6Game.R6NoiseMgr",
                               key="m_Rainbow", field=posture, scale=feet,
                               minimum=0, note="footstep noise: " + posture))

    alert = {"x0.5": 0.5, "x2": 2.0}.get(v["gunfire_alert"])
    if alert:
        for key in ("m_SndBulletImpact", "m_SndBulletRicochet",
                    "m_sndExplosion", "m_SndGrenadeImpact"):
            out.append(IniEdit(SOUND_INI, section="R6Game.R6NoiseMgr",
                               key=key, field="fSndDist", scale=alert,
                               minimum=0, note="alert radius: " + key))

    if v["quiet_reloads"]:
        for key in ("m_SndReload", "m_SndEquipping"):
            out.append(IniEdit(SOUND_INI, section="R6Game.R6NoiseMgr",
                               key=key, field="fSndDist", scale=0.25,
                               minimum=0, note="quiet " + key))

    # -- interface --------------------------------------------------------
    # These are `config` variables, so a key that is absent from the file is
    # simply the compiled-in default and adding it is the supported way to
    # override -- hence `absent="add"`, which is the IniEdit default.
    if not v["reticule"]:
        out.append(IniEdit(USER_INI, section="Engine.R6GameOptions",
                           key="HUDShowReticule", value="False",
                           note="crosshair off"))
    if not v["radar"]:
        out.append(IniEdit(USER_INI, section="Engine.R6GameOptions",
                           key="ShowRadar", value="False",
                           note="motion tracker off"))
    if not v["hud"]:
        for key in HUD_KEYS:
            out.append(IniEdit(USER_INI, section="Engine.R6GameOptions",
                               key=key, value="False", note=key))
    if v["aim_assist"] != 0:
        out.append(IniEdit(USER_INI, section="Engine.R6GameOptions",
                           key="AutoTargetSlider", value=v["aim_assist"],
                           note="aim assist"))
    if v["hide_bodies"]:
        out.append(IniEdit(USER_INI, section="Engine.R6GameOptions",
                           key="HideDeadBodies", value="TRUE", stock="FALSE",
                           note="hide bodies"))
    if v["fov"] != 95:
        out.append(IniEdit("system/openrvs.ini", section="OpenRVS.OpenFOV",
                           key="FieldOfView", value=v["fov"], stock="95",
                           note="field of view"))

    # -- game modes -------------------------------------------------------
    out.extend(_rs3_modes.edits(v))

    # -- weapons and ammunition, in the compiled packages -----------------
    out.extend(_rs3_weapons.edits(v))
    out.extend(_rs3_ammo.edits(v))
    return out


def combination_warnings(values):
    out = []
    if values["footsteps"] == "silent" and values["terro_skill"] == "green":
        out.append("Silent footsteps and green terrorists together leave very "
                   "little opposition.")
    if values["terro_skill"] == "elite" and values["difficulty"] == "2":
        out.append("Elite templates on the Elite difficulty level is two "
                   "increases at once: skill at 95 AND the shortest reaction "
                   "time.")
    return out


NOTES = r"""
Raven Shield is configured, not packed. Everything this tool writes is a key in
a text file the engine reads at start-up, so every option is reversible by
Restore and readable by eye afterwards.

The one thing worth understanding about Unreal ini files: a variable is only
read from an ini if the class that owns it was compiled with the `config`
keyword. That is why some keys this tool writes are not in the shipped file at
all -- they are compiled-in defaults, and adding the key is the supported way
to override one. Every key written here was confirmed flagged in the packages.

Sound.ini is misnamed. It is the AI HEARING model -- how far a terrorist hears
your footsteps per posture, how far a reload carries, how far a gunshot pulls
attention -- and it is the whole stealth economy of the game in sixteen lines.

template\*.tpt is where terrorist competence lives: 266 plain-text files with
eight skill stats, a six-way personality mix that must total 100, and per-team
weapon and equipment pools. The difficulty level in the menu is only a reaction
timer by comparison; the game's own description says so.

WHAT IS NOT HERE, AND WHY

Unlocking the cut game modes. R6DefendGame, R6DefendCoopGame, R6ReconGame and
R6ReconCoopGame are fully compiled in R6Game.u and no shipped .mod lists their
mode names, so they never appear in a menu. Re-enabling them is a text edit to
a generated .mod file -- not a binary patch -- and it is the highest-value
unlock available here. It needs the mod-descriptor route, which this profile
does not use yet.

Weapon restriction. R6ServerInfo carries ten config-flagged Restricted* arrays
that appear in no shipped ini file: a complete kit-lock system nobody ever
used. The exact value syntax is unverified, which is the only reason it is not
an option yet.

ABOUT THIS PARTICULAR INSTALLATION

It is not stock. system\openrvs.ini sets ForceStartMod=SupplyDrop, which
replaces the player pawn, the teammate AI and the player-controller classes.
The ini options above still apply; anything that assumes stock class behaviour
may not.

The weapon and ammunition options write to the compiled packages, which is a
different kind of change from everything else here and carries two caveats
worth repeating: a Steam file verification restores the stock packages without
saying so, and a server running stock packages may reject a client whose do not
match. Revert puts every byte back.

Those options cover Gold's two official expansions as well as the base game --
Athena Sword and Iron Wrath keep their weapons, ammunition and menu bars in
packages of their own, so the 31 expansion weapons and the three expansion
ammunition pairs are retuned alongside the rest. Any OTHER mod in Mods\ is
deliberately left alone, which matters here: with ForceStartMod=SupplyDrop set,
the guns SupplyDrop adds keep their own figures, and options tuned against
stock weapons will not describe them.

Nothing in this profile has been watched working in a running game.
"""

PROFILE = GameProfile(
    id="ravenshield",
    title="Rainbow Six 3: Raven Shield",
    short="Raven Shield",
    layout=LAYOUT,
    delivery=INPLACE,
    settings=SETTINGS,
    build_edits=build_edits,
    combination_warnings=combination_warnings,
    notes=NOTES,
)

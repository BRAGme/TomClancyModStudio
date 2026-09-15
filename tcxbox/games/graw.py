"""Ghost Recon: Advanced Warfighter on the original Xbox.

Not a Ghost Recon at all underneath: this is Rainbow Six 3's engine with a Ghost
Recon front end, which is why it shares `R6GameSettings.ini` with that game key
for key -- all 240 of them, plus 21 of its own -- and why its classes are still
called `R6Engine.GR3Terrorist`.

It ships more of itself loose than Rainbow Six 3 does. There is no `.umd`
bundle: the whole System folder is on the disc as files, including two tuning
files the retail Rainbow Six 3 disc does not carry at all.

  * `GR3XBoxAI.ini` -- your AI teammates. Assault skill, firing accuracy,
    weapon dispersion per fire mode, the suppression window, and the zones the
    teammate controller works in.
  * `TWeapon.ini` -- the enemy's weapons, per enemy class: damage range,
    fire delays, aim scatter, grenade willingness, and a dynamic-difficulty
    block that raises and lowers the fight as it goes.

Both were checked rather than assumed: the strings `GR3XBoxAI` and `TWeapon`
both appear inside the cooked `System\\Common.lin`, which is the shipped build
naming them as its config files. `R6GameSettings` does not appear there -- but
that file carries its own instruction to reload it from the console, and it is
the same file Rainbow Six 3 reads, so the pages it drives are badged applied and
this one difference is written on the About page rather than hidden.

The 21 keys GRAW adds to the shared table are a scoring block (awards for a
terrorist killed or a civilian rescued), a movement boost, HUD colours, and
close-range wound multipliers for multiplayer.
"""

from __future__ import annotations

from ..model import CHOICE, INT, Choice, FileEdit, GameProfile, Marker, Setting
from . import r6_3, r6engine

TEAM = "Your team"
ENEMY_GUNS = "Enemy weapons"

AI_INI = r"GR3XBOXAI\.INI$"
TWEAPON_INI = r"TWEAPON\.INI$"

#: every enemy class in TWeapon.ini carries the same field names, so a scale
#: reaches all of them at once rather than needing a card per class.
ENEMY_HARM = ("fWeaponHarmLow", "fWeaponHarmHigh",
              "fFixedGunHarmLow", "fFixedGunHarmHigh")
ENEMY_DELAY = ("fWeaponDelaySmall", "fWeaponDelayBig")
ENEMY_SCATTER = ("fWeaponRandomAngle", "fWeaponRandomAngleMax",
                 "fFixedGunAngleSmall", "fFixedGunAngleBig")
ENEMY_GRENADE = ("fGrenadeSmall", "fGrenadeBig", "fGrenadePossibility")

TEAM_SKILL = ("cfg_AssaultSkill", "cfg_FiringAccuracy")
TEAM_SPREAD = ("fWeaponDispersionSingle", "fWeaponDispersionThreeRound",
               "fWeaponDispersionFullAuto", "fFixedGunDispersion")
TEAM_ZONES = ("ThreatEvaluationZone", "ProtectionZone", "DetachZone")

BCD = ("BCDDefault[0]", "BCDDefault[1]", "BCDDefault[2]", "BCDDefault[3]",
       "BCDDefault[4]", "desBCDScore")


def _scale(key, label, group, help_text, caution=""):
    return Setting(key, label, CHOICE, "stock", group, confidence="applied",
                   choices=[Choice("stock", "As shipped", ""),
                            Choice("less", "Half", ""),
                            Choice("little_less", "Three quarters", ""),
                            Choice("little_more", "A quarter more", ""),
                            Choice("more", "Half again", ""),
                            Choice("much_more", "Double", "")],
                   help=help_text, caution=caution)


SETTINGS = (
    r6engine.cards("graw_", has_templates=False)
    + r6_3._render_cards("graw_")
    + [
        _scale("graw_team_skill", "Teammate skill", TEAM,
               "cfg_AssaultSkill and cfg_FiringAccuracy in GR3XBoxAI.ini, "
               "which ship at 0.1 and 5.0. These are your three AI teammates, "
               "not the enemy."),
        _scale("graw_team_spread", "Teammate weapon spread", TEAM,
               "The dispersion each fire mode gets -- single, three-round "
               "burst, full auto, and a fixed gun. The file writes what each "
               "one means beside it: full auto is 1.5 m at 20 m. LOWER is a "
               "better shot, so “half” makes them deadlier."),
        _scale("graw_team_zones", "How far teammates range from you", TEAM,
               "The threat-evaluation, protection and detach zones -- 15 m, "
               "5 m and 100 m. The last is the distance at which a teammate "
               "gives up and regroups on you."),
        Setting("graw_team_ai", "Teammate AI", CHOICE, "stock", TEAM,
                confidence="experimental",
                choices=[Choice("stock", "As shipped (on)", ""),
                         Choice("true", "Disabled", "")],
                help="bDisableTeammateAI in GR3XBoxAI.ini. It is the shipped "
                     "build's own switch for turning the squad off, presumably "
                     "for testing.",
                caution="Untested, and the plainest way to break a campaign "
                        "mission that needs a teammate to do something."),

        _scale("graw_enemy_harm", "Enemy weapon damage", ENEMY_GUNS,
               "The low and high ends of the damage a hit does, for every "
               "enemy class at once, and the same for fixed guns. They ship at "
               "20 to 30."),
        _scale("graw_enemy_delay", "Enemy fire delay", ENEMY_GUNS,
               "How long an enemy waits between bursts -- 0.08 s inside a "
               "burst and 0.7 s between them. LOWER is a harder game."),
        _scale("graw_enemy_scatter", "Enemy aim scatter", ENEMY_GUNS,
               "How far off an enemy's shots wander, in degrees: 2.5 normally "
               "and up to 4.5. LOWER means they hit you more."),
        _scale("graw_enemy_grenades", "Enemy grenade use", ENEMY_GUNS,
               "How likely an enemy is to throw one, and how hard they lean on "
               "the small and big variants."),
        _scale("graw_bcd", "Dynamic difficulty target", ENEMY_GUNS,
               "GRAW rates the fight as it goes and steers it -- five default "
               "levels from 650 to 2500 and a target score of 2200 it tries to "
               "hold you at. Scaling the whole block moves where it aims.",
               "This is a feedback loop, not a dial: the game will spend the "
               "mission trying to reach whatever you set."),
    ]
)


def build_data(v: dict) -> list:
    out = r6engine.edits("graw_", v, has_templates=False)
    out += r6_3._render_edits("graw_", v)

    ai_factors, ai_values = {}, {}
    for key, names in (("graw_team_skill", TEAM_SKILL),
                       ("graw_team_spread", TEAM_SPREAD),
                       ("graw_team_zones", TEAM_ZONES)):
        choice = v.get(key, "stock")
        if choice != "stock":
            for n in names:
                ai_factors[n] = r6engine.STEPS[choice]
    if v.get("graw_team_ai") == "true":
        ai_values["bDisableTeammateAI"] = "true"
    if ai_factors:
        out.append(FileEdit("scale_ini", AI_INI, {"factors": ai_factors},
                            "teammate AI: %d value(s) scaled" % len(ai_factors)))
    if ai_values:
        out.append(FileEdit("ini_values", AI_INI, {"values": ai_values},
                            "teammate AI: " + ", ".join(sorted(ai_values))))

    gun_factors = {}
    for key, names in (("graw_enemy_harm", ENEMY_HARM),
                       ("graw_enemy_delay", ENEMY_DELAY),
                       ("graw_enemy_scatter", ENEMY_SCATTER),
                       ("graw_enemy_grenades", ENEMY_GRENADE),
                       ("graw_bcd", BCD)):
        choice = v.get(key, "stock")
        if choice != "stock":
            for n in names:
                gun_factors[n] = r6engine.STEPS[choice]
    if gun_factors:
        out.append(FileEdit("scale_ini", TWEAPON_INI, {"factors": gun_factors},
                            "enemy weapons: %d value(s) scaled"
                            % len(gun_factors)))
    return out


NOTES = (
    "GRAW on the original Xbox is Rainbow Six 3's engine wearing a Ghost Recon "
    "front end. It shares R6GameSettings.ini with that game key for key, and "
    "its own classes are still named GR3Terrorist and GR3Teammate.\n\n"
    "Unlike retail Rainbow Six 3 it ships its System folder loose, with two "
    "tuning files that disc does not carry at all: GR3XBoxAI.ini for your three "
    "AI teammates and TWeapon.ini for the enemy's weapons. Both are named "
    "inside the cooked System\\Common.lin, which is the shipped build saying it "
    "reads them.\n\n"
    "One honest caveat. R6GameSettings.ini is NOT named in Common.lin the way "
    "those two are. It is the same file Rainbow Six 3 reads and it carries its "
    "own instruction to reload it from the console, so the pages it drives are "
    "badged applied -- but if a change on the Enemies or Feel page does nothing "
    "here while the teammate and enemy-weapon pages work, that is the "
    "difference, and it is worth saying so before you go looking."
)

GRAW = GameProfile(
    id="graw_xbox",
    title="Tom Clancy's Ghost Recon: Advanced Warfighter",
    short="GRAW",
    title_id="55530054",
    markers=[Marker("System", "the loose System folder"),
             Marker("System/R6GameSettings.ini", "the shared gameplay table"),
             Marker("System/GR3XBoxAI.ini", "the teammate AI table"),
             Marker("System/TWeapon.ini", "the enemy weapon table")],
    settings=SETTINGS,
    build_data=build_data,
    notes=NOTES,
    ui_art={"backdrop": "LoadingScreens/Background.tga",
            "emblem": "LoadingScreens/Splash.dds",
            "emblem_key": (75, 185)},
)

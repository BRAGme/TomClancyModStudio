r"""Lockdown options that live in files the profile already opens.

Three groups, all verified against the shipped data on this machine.

## The multiplayer maps can be played alone

Every `data\mission\*.mis` opens with::

    <Shell SinglePlayerMissionType="..." MultiPlayerMissionType="...">

Censused across all 101 missions, `SinglePlayerMissionType` is `Campaign` on
38, `Terrorist Hunt` on 32, `Training` on 1, and **`Not Available` on exactly
30 -- which are exactly the 30 `mp*.mis` multiplayer maps**. The game's own
level-editor guide (`NED Guide.doc`, which ships) describes these as the
authored values rather than a computed state.

So "play the multiplayer maps in single player" is one attribute on 30 files.
What is NOT proven is that the single-player hunt front-end enumerates them
once they say so -- the maps do carry unit rosters and spawn data like any
other mission, and the 32 shipped hunt maps are themselves re-shelled copies
of campaign maps, but nothing in the data settles it. The option says so.

## ForcedMiss is four numbers, not one

`enemy_forced_miss` shipped incomplete. `badguys.acm` carries::

    ForcedMiss="-100"
    AdjustForcedMissSingleShot="25" AdjustForcedMissBurst="20"
    AdjustForcedMissFullAuto="10"

and the game's own never-miss configuration -- `rainbow.acm`, used by the
player's squad -- carries `ForcedMiss="1"` with all three adjustments at
`-1`. Setting only `ForcedMiss` left the per-fire-mode scaling at 25/20/10,
so enemies went on missing deliberately in single shots more than anywhere
else. The option now writes all four, copying what the game does for the side
that is supposed not to miss.

## `options.xml`, which the profile already writes

Six complete HUD colour schemes ship as `hudThemeBG0..5` / `hudThemeFG0..5`
RGBA pairs with `hudTheme="0"` selecting among them -- the same shape as the
Advanced Warfighter palette option, in a file this profile already edits. Also
here: `maxBulletHoles`, `enableFirstPersonWeapon`, `sniperZoomMultiplier` and
the mouse sensitivities.
"""

from ..model import BOOL, CHOICE, Choice, INT, Setting, XmlAttr

OPTIONS = "data/options.xml"
BADGUYS = "data/mission/badguys.acm"
MP_MISSIONS = "data/mission/mp*.mis"

#: what the player's own squad uses, and therefore what "never miss on
#: purpose" means in this game's own terms
NEVER_MISS = {"ForcedMiss": "1", "AdjustForcedMissSingleShot": "-1",
              "AdjustForcedMissBurst": "-1", "AdjustForcedMissFullAuto": "-1"}
STOCK_MISS = {"ForcedMiss": "-100", "AdjustForcedMissSingleShot": "25",
              "AdjustForcedMissBurst": "20", "AdjustForcedMissFullAuto": "10"}


def settings():
    return [
        Setting(
            "mp_maps_single", "Play the multiplayer maps on your own", BOOL,
            False, group="Difficulty",
            help="Thirty multiplayer maps ship marked 'Not Available' for "
                 "single player. They carry unit rosters and spawn points "
                 "like every other mission; this marks them as Terrorist "
                 "Hunt instead.",
            caution="The mark is what the map claims about itself. Nothing in "
                    "the data proves the single-player menu will list them "
                    "once it changes, and this has not been watched in a "
                    "running game.",
            confidence="experimental", touches="data"),
        Setting(
            "hud_theme", "HUD colour scheme", CHOICE, "0", group="Interface",
            help="Lockdown ships six complete HUD colour schemes and uses the "
                 "first. The other five are finished and unreachable from the "
                 "game's own menus.",
            choices=[Choice(str(i), name, "") for i, name in enumerate(
                ["Stock blue", "Scheme 2", "Scheme 3", "Scheme 4",
                 "Scheme 5", "Scheme 6"])],
            confidence="applied", touches="config"),
        Setting(
            "view_model", "Show your own weapon", BOOL, True, group="Interface",
            help="Hides the first-person weapon model without touching the "
                 "rest of the HUD.",
            confidence="applied", touches="config"),
        Setting(
            "bullet_holes", "Bullet holes kept on screen", INT, 100,
            group="Interface", minimum=0, maximum=1000, unit=" holes",
            help="How many bullet impacts stay before the oldest is recycled.",
            confidence="applied", touches="config"),
        Setting(
            "sniper_zoom", "Sniper zoom", INT, 5, group="Weapons",
            minimum=1, maximum=20, unit="x",
            help="The magnification a sniper scope gives.",
            confidence="applied", touches="config"),
    ]


def edits(values, forced_miss_on):
    out = []
    v = values

    if v["mp_maps_single"]:
        out.append(XmlAttr(MP_MISSIONS, path="Shell",
                           attr="SinglePlayerMissionType",
                           value="Terrorist Hunt", stock="Not Available",
                           note="multiplayer map playable alone"))

    if not forced_miss_on:
        for attr, value in NEVER_MISS.items():
            out.append(XmlAttr(BADGUYS, path="Combat", attr=attr, value=value,
                               stock=STOCK_MISS[attr],
                               note="enemies no longer miss on purpose: "
                                    + attr))

    if v["hud_theme"] != "0":
        out.append(XmlAttr(OPTIONS, path="Preferences/game", attr="hudTheme",
                           value=v["hud_theme"], stock="0",
                           note="HUD colour scheme"))
    if not v["view_model"]:
        out.append(XmlAttr(OPTIONS, path="Preferences/game",
                           attr="enableFirstPersonWeapon", value="false",
                           stock="true", note="first-person weapon model"))
    if v["bullet_holes"] != 100:
        out.append(XmlAttr(OPTIONS, path="Preferences/game",
                           attr="maxBulletHoles", value=v["bullet_holes"],
                           stock="100", note="bullet holes kept"))
    if v["sniper_zoom"] != 5:
        out.append(XmlAttr(OPTIONS, path="Preferences/input",
                           attr="sniperZoomMultiplier", value=v["sniper_zoom"],
                           stock="5", note="sniper zoom"))
    return out


# ---------------------------------------------------------------------------
# the enemy half of the weapon model
# ---------------------------------------------------------------------------
#
# Lockdown is the one game here that ships the split already done: 42 `e_*.gun`
# files, each paired 1:1 with a player twin, and not one enemy-only weapon. So
# there is nothing to create -- the two sides were separate all along, and the
# only asymmetry was in which knobs this tool exposed.
#
# It exposed two (enemy marksmanship, enemy damage) out of a complete AI
# accuracy model. `Common/AIAccuracy` carries three blocks and every one of the
# 42 enemy guns holds IDENTICAL values, so one number really does cover the
# whole opposition:
#
#     Accuracy      BaseAccuracy  15    Recoil  -5
#     Movement      ShooterShuffle -10   ShooterWalk -20   ShooterRun -30
#     MethodOfFire  Overhead      -30   Wild    -40
#
# They are PENALTIES subtracted from the base, which is why "sharper" scales
# them towards zero rather than up.

AI_ACCURACY = "Common/AIAccuracy"

#: {attribute: stock value}, measured identical across all 42 enemy guns
MOVE_PENALTY = {"ShooterShuffle": "-10", "ShooterWalk": "-20",
                "ShooterRun": "-30"}
FIRE_PENALTY = {"Overhead": "-30", "Wild": "-40"}

PENALTY_SCALE = {"none": 0.0, "half": 0.5, "double": 2.0}


def enemy_settings():
    return [
        Setting(
            "enemy_move_penalty", "How much moving spoils enemy aim", CHOICE,
            "stock", group="Difficulty",
            help="Every enemy weapon docks accuracy when its owner is moving: "
                 "10 shuffling, 20 walking, 30 running, against a base of 15. "
                 "That is why backing away from a charging enemy works. These "
                 "are penalties, so 'none' makes enemies shoot as well on the "
                 "move as standing still.",
            choices=[
                Choice("stock", "Stock", "-10 / -20 / -30."),
                Choice("half", "Halved", "Enemies suffer less for moving."),
                Choice("none", "None", "Moving costs them nothing."),
                Choice("double", "Doubled", "A moving enemy is nearly "
                                            "harmless."),
            ],
            confidence="experimental", touches="data"),
        Setting(
            "enemy_blind_fire", "How much blind firing spoils enemy aim",
            CHOICE, "stock", group="Difficulty",
            help="The penalty for firing overhead from cover (-30) or wild "
                 "(-40). Enemies lean on both, so this decides how dangerous "
                 "they are while they are behind something.",
            choices=[
                Choice("stock", "Stock", "-30 / -40."),
                Choice("half", "Halved", ""),
                Choice("none", "None", "Blind fire is as accurate as aimed."),
                Choice("double", "Doubled", ""),
            ],
            confidence="experimental", touches="data"),
        Setting(
            "enemy_recoil", "Enemy recoil", CHOICE, "stock",
            group="Difficulty",
            help="The accuracy an enemy loses per shot, stock -5 against your "
                 "own 0. This is the enemy half of the Recoil option on the "
                 "Weapons page.",
            choices=[
                Choice("stock", "Stock", "-5."),
                Choice("none", "None", "Enemy fire does not climb."),
                Choice("double", "Doubled", ""),
            ],
            confidence="experimental", touches="data"),
        Setting(
            "enemy_magazines", "Enemy magazine capacity", CHOICE, "stock",
            group="Difficulty",
            help="How many rounds an enemy fires before reloading. The enemy "
                 "half of the Magazine capacity option on the Weapons page.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("x0.5", "Half", "They reload twice as often."),
                Choice("x2", "Double", ""),
            ],
            confidence="experimental", touches="data"),
        Setting(
            "enemy_range", "How far enemy weapons reach", CHOICE, "stock",
            group="Difficulty",
            help="Stock enemy weapon range. Shortening it keeps firefights "
                 "closer without making enemies any worse at them.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("x0.5", "Half", ""),
                Choice("x1.5", "Longer", ""),
            ],
            confidence="experimental", touches="data"),
    ]


def enemy_edits(values, enemy_guns):
    """`enemy_guns` is the profile's own selector for the `e_*.gun` half."""
    out = []
    v = values

    move = PENALTY_SCALE.get(v["enemy_move_penalty"])
    if move is not None:
        for attr, stock in MOVE_PENALTY.items():
            out.append(XmlAttr(enemy_guns, path=AI_ACCURACY + "/Movement",
                               attr=attr, scale=move, stock=stock,
                               note="enemy movement penalty: " + attr))
    blind = PENALTY_SCALE.get(v["enemy_blind_fire"])
    if blind is not None:
        for attr, stock in FIRE_PENALTY.items():
            out.append(XmlAttr(enemy_guns, path=AI_ACCURACY + "/MethodOfFire",
                               attr=attr, scale=blind, stock=stock,
                               note="enemy blind-fire penalty: " + attr))
    kick = {"none": 0.0, "double": 2.0}.get(v["enemy_recoil"])
    if kick is not None:
        out.append(XmlAttr(enemy_guns, path=AI_ACCURACY + "/Accuracy",
                           attr="Recoil", scale=kick, stock="-5",
                           note="enemy recoil"))
    mags = {"x0.5": 0.5, "x2": 2.0}.get(v["enemy_magazines"])
    if mags:
        out.append(XmlAttr(enemy_guns, path="ReloadData", attr="clipSize",
                           scale=mags, minimum=1, note="enemy magazine size"))
    reach = {"x0.5": 0.5, "x1.5": 1.5}.get(v["enemy_range"])
    if reach:
        out.append(XmlAttr(enemy_guns, path="WeaponData", attr="range",
                           scale=reach, minimum=1, note="enemy weapon range"))
    return out

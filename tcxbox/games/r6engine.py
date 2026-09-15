"""The gameplay table the Unreal-engine Tom Clancy games on Xbox share.

Rainbow Six 3, its Black Arrow prototype and Ghost Recon: Advanced Warfighter
all ship `R6GameSettings.ini` -- 240 keys under `[Engine.R6GameplaySettings]`
and five more classes -- and **all 240 keys are the same in all three**. GRAW
adds 21 of its own and drops none. So one page drives every one of them, and
the differences that do exist are in the values rather than the field names:
Rainbow Six 3 gives the squad a crouched running speed of +250 where GRAW gives
+150. That is why every dial here *scales* the number the game shipped instead
of writing an absolute.

**This file is live, and it says so itself.** Halfway down, above the gamepad
block, is the comment

    All the attributes in this section can be refreshed
    in-game by opening the console and typing REFRESHGAMESETTINGS

which is the shipped build telling you it reads this file at run time. That is
better evidence than a guess about what a cooked package might override, and it
is why the options here are badged as applied rather than experimental.

**Where the file is** differs per game and does not change the edits. Black
Arrow's prototype and GRAW keep it loose in `System\\`. Retail Rainbow Six 3
keeps it inside `System\\xboxdynamic.umd`, along with 37 other ini files and the
115 terrorist templates -- which is why that game looks unmoddable from the file
tree and is not. The selector matches both, and `gamedir` writes whichever
copies exist.
"""

from __future__ import annotations

from ..model import BOOL, CHOICE, INT, Choice, FileEdit, Setting

ENEMIES = "Enemies"
SQUAD = "Your side"
FEEL = "Feel"
CHEATS = "Cheats"

SETTINGS_FILE = r"R6GAMESETTINGS\.INI$"

#: choice value -> factor, for the three-step dials
STEPS = {"stock": 1.0, "less": 0.5, "little_less": 0.75,
         "little_more": 1.25, "more": 1.5, "much_more": 2.0}

TERRO_SKILL = ("m_fTerroristSkillMultiplierRecruit",
               "m_fTerroristSkillMultiplierVeteran",
               "m_fTerroristSkillMultiplierElite")

TERRO_REACT = ("m_fReactionTimeForFiringRecruit",
               "m_fReactionTimeForFiringVeteran",
               "m_fGrenadeReactionDelayRecruit",
               "m_fGrenadeReactionDelayVeteran")

TERRO_SPEED = ("m_fTerroristRelaxSpeed", "m_fTerroristWalkingSpeed",
               "m_fTerroristRunningSpeed", "m_fTerroristCrouchedRunningSpeed",
               "m_fTerroristCrouchedWalkingSpeed")

RAINBOW_SPEED = ("m_fRainbowWalkingSpeed", "m_fRainbowRunningSpeed",
                 "m_fRainbowCrouchedWalkingSpeed",
                 "m_fRainbowCrouchedRunningSpeed")

SIGHT = ("m_fSightRadius",)

ZOOM = tuple("m_fRetZoomModifier_%d" % n for n in range(1, 6))

CHEAT_KEYS = (("m_bCheatChavezNoDie", "Chavez"),
              ("m_bCheatPriceNoDie", "Price"),
              ("m_bCheatLoiselleNoDie", "Loiselle"),
              ("m_bCheatWeberNoDie", "Weber"))

#: The PS2 build's aim table, read out of its own disc rather than invented:
#: `R6GAMESETTINGS.INI` inside `vokes0.img` at offset 0x20C90 (17,267 bytes),
#: section `[Engine.R6GameplaySettings]`. The Xbox copy of the same file lives
#: inside `System\xboxdynamic.umd` at 0x126140 (16,690 bytes) and is the only
#: place either disc defines these keys -- they are UE2 `config` properties
#: declared in `Engine.u`, not constants in `default.xbe`.
#:
#: 54 aim-related keys were diffed across the two discs: 27 are already
#: identical (all six `*Sensitivity*` keys among them, so the in-game slider is
#: NOT the difference), 11 are PS2-only and cannot be ported, and these 16 are
#: the ones that both exist on Xbox and differ.
#:
#: The 11 control points are the stick-deflection-to-turn-rate curve. Xbox's is
#: quadratic -- exactly 2.7*n^2 for n=1..8 -- so half deflection asks for
#: 67.5 deg/s where PS2 asks for 30. That is the acceleration people feel. The
#: dead zone compounds it: Xbox spends 40% of stick travel doing nothing, so
#: every correction begins in the steep part of the curve.
PS2_AIM = {
    "m_afRotationControlPoints[0]": 1,
    "m_afRotationControlPoints[1]": 6,
    "m_afRotationControlPoints[2]": 12,
    "m_afRotationControlPoints[3]": 18,
    "m_afRotationControlPoints[4]": 24,
    "m_afRotationControlPoints[5]": 30,
    "m_afRotationControlPoints[6]": 50,
    "m_afRotationControlPoints[7]": 80,
    "m_afRotationControlPoints[8]": 120,
    "m_afRotationControlPoints[9]": 140,
    "m_afRotationControlPoints[10]": 270,
    "m_fRotationControlPoint": 90,
    "m_fRotationZoomingMultiplier": 0.7,
    "m_fSmoothingTime": "0.20",
    "m_fAimDamping": 0.8,
    "m_fDeadZone": 0.1,
}

#: `m_fDeadZone` is split out of `PS2_AIM` by the "keep" choice. PS2 sticks were
#: new when that 0.1 was chosen; a worn Xbox controller can drift inside it.
AIM_DEADZONE = "m_fDeadZone"



def _scale_card(key, label, group, help_text, caution="", down=True):
    choices = [Choice("stock", "As shipped", "")]
    if down:
        choices += [Choice("less", "Half", ""),
                    Choice("little_less", "Three quarters", "")]
    choices += [Choice("little_more", "A quarter more", ""),
                Choice("more", "Half again", ""),
                Choice("much_more", "Double", "")]
    return Setting(key, label, CHOICE, "stock", group, choices=choices,
                   confidence="applied", help=help_text, caution=caution)


#: Every place these discs keep `R6RainbowAI.RainbowReloadWeapon`. Retail
#: Rainbow Six 3 has it twice -- in the cooked `System\\Common.lin` and in
#: `System\\R6Engine.u` inside `System\\xboxufiles.umd` -- and the two copies are
#: byte-identical. Black Arrow ships only the cooked one; the Black Arrow
#: prototype ships only a loose `R6Engine.u` under
#: `Files\\Black_Arrow_XBOX_media`. This regex names all of them, and
#: `apply_data` simply writes whichever a given disc has.
#:
#: Editing both copies on retail is deliberate. Which one the running game
#: loads is NOT settled: both copies of `RainbowSix3Xbox.ini` declare
#: `Paths=d:\\System\\*.u` and no `*.lin` path at all, yet there is not one
#: loose `.u` on the disc, and `default.xbe` names only `xboxdynamic.umd`.
#: Since the copies are identical and the edit is deterministic and
#: length-preserving, writing both makes the question moot.
SCRIPT_FILES = r"/COMMON\.LIN$|/R6ENGINE\.U$"


def _sidearm_cards(prefix):
    from .. import rsesidearm
    from ..model import BOOL
    need = {prefix + "unlimited_teammate_ammo": ["false"]}
    return [
        Setting(prefix + "sidearm", "Chance of drawing the pistol instead of "
                "reloading", INT, 0, SQUAD, minimum=0,
                maximum=rsesidearm.MAX_CHANCE, unit="%",
                confidence="untested", requires=need,
                help="Stock, a teammate reaches for his sidearm only when the "
                     "rifle is completely spent -- he never transitions "
                     "mid-fight the way the animation and the loadout plainly "
                     "expect. The decision is one test in "
                     "`R6RainbowAI.RainbowReloadWeapon`, which reloads whenever "
                     "any magazine remains. This puts a roll on that test, so "
                     "this percentage of dry magazines end with the pistol "
                     "coming out instead. 0% is the game exactly as it "
                     "shipped.",
                caution="Not play-tested, and this one rewrites compiled "
                        "UnrealScript rather than a line of text: the roll is "
                        "inserted, every jump in the function is re-based "
                        "around it, and the space is paid for by deleting a "
                        "debug log line that cannot run. The result is read "
                        "back through the same parser before it is written. "
                        "Capped at %d%% because a teammate who never reloads "
                        "would swap between two weapons that both still report "
                        "ammunition." % rsesidearm.MAX_CHANCE),
        Setting(prefix + "say_dry", "Chance of calling out a reload", INT, 0,
                SQUAD, minimum=0, maximum=100, unit="%",
                confidence="untested",
                help="**There is no reloading line in this game.** All three "
                     "operatives have 101 voice events each and exactly one is "
                     "about ammunition; the only reload sounds on the disc are "
                     "a shotgun and a grenade launcher. So this does the "
                     "nearest honest thing: it plays the ammunition line -- "
                     "\"No ammo, sir\" / \"Weapon's dry\" -- when a teammate "
                     "reloads, this often. It is the game's own call, copied "
                     "from the branch that fires when both weapons are spent "
                     "and inserted into the reload branch behind a roll.",
                caution="Not play-tested. Unlike the card above this one needs "
                        "no other setting -- it sits in the branch that runs "
                        "either way, so it works on a stock disc where "
                        "teammates reload constantly. Start low; 15-25% is "
                        "about one call-out every few magazines."),
        Setting(prefix + "sidearm_contact", "...only when they are in contact",
                BOOL, True, SQUAD, confidence="untested",
                requires={prefix + "sidearm":
                          list(range(1, rsesidearm.MAX_CHANCE + 1))},
                help="With this on, the roll only happens to a teammate who "
                     "currently has an enemy -- one with nobody shooting at him "
                     "always reloads, which is what he should do. The test is "
                     "the game's own: the function already checks "
                     "`Enemy != None` to decide whether to break off an attack "
                     "before reloading, and the reference is lifted from there "
                     "rather than hardcoded."),
    ]


def cards(prefix, has_templates):
    out = [
        _scale_card(prefix + "terro_skill", "Terrorist skill", ENEMIES,
                    "One multiplier per difficulty -- 0.40 on Recruit, 0.70 on "
                    "Veteran, 1.25 on Elite -- applied to every skill a "
                    "terrorist rolls. This scales all three together, so the "
                    "ladder between the difficulties is kept.",
                    "Double puts Recruit above shipped Elite."),
        _scale_card(prefix + "terro_react", "Terrorist reaction time", ENEMIES,
                    "How long a terrorist waits after noticing you before "
                    "firing, and the same for reacting to a grenade: one "
                    "second on Recruit, half on Veteran. LOWER is a harder "
                    "game, so “half” here means they shoot sooner."),
        _scale_card(prefix + "sight", "How far anyone can see", ENEMIES,
                    "m_fSightRadius is the base spotting distance in "
                    "centimetres -- 5000 is fifty metres -- before the light "
                    "level, the observation skill and whether either party is "
                    "moving are applied to it.",
                    "The file calls this a base sight radius for everybody, "
                    "not a terrorist-only number."),
        _scale_card(prefix + "terro_speed", "How fast terrorists move", ENEMIES,
                    "Their relaxed, walking, running and both crouched speeds "
                    "together. They ship faster than you on every one of them: "
                    "+518 running against your +400."),
        _scale_card(prefix + "terro_wounds", "How much a terrorist can take",
                    ENEMIES,
                    "Terrorists ship with 10 wounds and armoured ones with 15, "
                    "against your 60. This scales both."),

        _scale_card(prefix + "player_wounds", "How much you can take", SQUAD,
                    "Your 60 wounds in single player and 20 in multiplayer, "
                    "and your AI teammates' 40, scaled together."),
        _scale_card(prefix + "squad_speed", "How fast your side moves", SQUAD,
                    "Walking, running and both crouched speeds for you and "
                    "your team."),
        _scale_card(prefix + "ammo", "How much ammunition you start with",
                    SQUAD,
                    "The per-difficulty magazine multiplier -- three magazines "
                    "on Recruit, two on Veteran and Elite -- and the grenade "
                    "multiplier with it."),
        Setting(prefix + "unlimited_teammate_ammo",
                "Teammates never run out of ammunition", CHOICE, "stock", SQUAD,
                choices=[Choice("stock", "As shipped (on)", ""),
                         Choice("true", "On", ""), Choice("false", "Off", "")],
                confidence="applied",
                help="m_bUnlimitedRainbowMagazines ships true: your AI "
                     "teammates have infinite magazines and you do not. "
                     "Turning it off is a realism option.",
                caution="It is also the switch the two cards below depend on. "
                        "While magazines are unlimited the engine pins every "
                        "teammate weapon's clip count at 1 for the whole "
                        "mission, so the branch that draws a sidearm can never "
                        "be reached."),
    ] + _sidearm_cards(prefix) + [
        Setting(prefix + "falling_damage", "Falling damage", CHOICE, "stock",
                SQUAD, confidence="applied",
                choices=[Choice("stock", "As shipped", ""),
                         Choice("off", "Off",
                                "Every threshold pushed out of reach."),
                         Choice("harsh", "Harsher",
                                "Half the safe height, so short drops hurt.")],
                help="Four heights in centimetres decide it: safe below 3 m, "
                     "then a quarter, a half and three quarters of your wounds, "
                     "and dead at 9 m."),

        _scale_card(prefix + "zoom", "Scope magnification", FEEL,
                    "The five zoom steps -- 1.5x, 2.5x, 3.5x, 10x and 20x -- "
                    "scaled together."),
        _scale_card(prefix + "sensitivity", "Look sensitivity", FEEL,
                    "The X and Y multipliers the gamepad runs through, which "
                    "ship at 0.70 and 0.60. This is the same number the "
                    "in-game menu moves, set outside it."),
        Setting(prefix + "aim_ps2", "Aiming response", CHOICE, "stock", FEEL,
                choices=[
                    Choice("stock", "As shipped",
                           "The Xbox curve: 2.7*n^2, and 40% of the stick "
                           "dead."),
                    Choice("ps2", "PlayStation 2",
                           "The PS2 disc's own numbers, all 16 of them, dead "
                           "zone included."),
                    Choice("ps2_keep_deadzone", "PlayStation 2, stock dead zone",
                           "The PS2 curve, but the Xbox 0.40 dead zone left "
                           "alone."),
                ],
                confidence="applied",
                help="Replaces the turn-rate curve with the one the PS2 "
                     "version ships. Xbox ramps as the square of stick "
                     "deflection, so half a push asks for 67.5 deg/s where "
                     "the PS2 asks for 30 -- that is the acceleration that "
                     "makes it hard to settle on a target. Also brings over "
                     "the dead zone (0.40 to 0.10), the zoom multiplier "
                     "(1.0 to 0.7, so zoomed aim slows down), smoothing and "
                     "damping. Look sensitivity is untouched: both discs "
                     "already ship the same numbers.",
                caution="The PS2 dead zone is 0.10. On a worn controller that "
                        "can let the stick drift on its own -- if it does, use "
                        "the stock dead zone choice."),
        _scale_card(prefix + "reload", "Reload speed", FEEL,
                    "m_fReloadSpeed, which ships at 1.0. Bigger is faster."),
        _scale_card(prefix + "ragdoll", "Ragdoll force", FEEL,
                    "The Karma impact and angular impact factors -- how hard a "
                    "body is thrown by what killed it.",
                    "Double is comfortably into comedy."),
        _scale_card(prefix + "blood", "Blood decal size", FEEL,
                    "The minimum and maximum blood stain sizes and how long "
                    "one takes to grow."),
        _scale_card(prefix + "tracers", "Tracer speed and length", FEEL,
                    "How fast a tracer travels and how long its streak is."),
    ]

    for key, who in CHEAT_KEYS:
        out.append(Setting(
            prefix + "cheat_" + who.lower(), "%s cannot die" % who, CHOICE,
            "stock", CHEATS, confidence="applied",
            choices=[Choice("stock", "As shipped (off)", ""),
                     Choice("true", "On", ""), Choice("false", "Off", "")],
            help="One of four invulnerability switches the developers left in "
                 "the shipped settings file, one per named operator. They are "
                 "the game's own cheats, not something this tool invents."))

    if has_templates:
        out += [
            Setting(prefix + "tpt_skill", "Terrorist template skill", INT, 100,
                    ENEMIES, minimum=25, maximum=200, unit="%",
                    confidence="applied",
                    help="Every terrorist on a map comes from a `.tpt` "
                         "template carrying eight skills from 0 to 100 -- "
                         "assault, demolitions, electronics, sniping, stealth, "
                         "self-control, leadership and observation. This scales "
                         "all eight in every template and clamps at 100.",
                    caution="This multiplies the numbers the level designer "
                            "chose, so a template that was already at 100 "
                            "cannot go higher."),
            Setting(prefix + "grenades", "Share of terrorists carrying grenades",
                    INT, 0, ENEMIES, minimum=0, maximum=100, unit="%",
                    confidence="applied",
                    help="A template's grenade table is two lines that must add "
                         "up to 100 -- so much chance of a grenade, the rest of "
                         "nothing. Zero here leaves each template's own number "
                         "alone; anything else sets them all.",
                    caution="Only reaches templates that already have a "
                            "two-entry grenade table."),
        ]
    return out


def edits(prefix, v, has_templates):
    out = []
    factors = {}
    setters = {}

    def scale(key, names):
        choice = v.get(prefix + key, "stock")
        if choice != "stock":
            for n in names:
                factors[n] = STEPS[choice]

    scale("terro_skill", TERRO_SKILL)
    scale("terro_react", TERRO_REACT)
    scale("sight", SIGHT)
    scale("terro_speed", TERRO_SPEED)
    scale("terro_wounds", ("m_iTerroristMaximumWounds",
                           "m_iArmouredTerroristMaximumWounds"))
    scale("player_wounds", ("m_iPlayerMaximumWounds", "m_iMPPlayerMaximumWounds",
                            "m_iRainbowMaximumWounds"))
    scale("squad_speed", RAINBOW_SPEED)
    scale("ammo", ("m_PlayerMagazineMultiplierRecruit",
                   "m_PlayerMagazineMultiplierVeteran",
                   "m_PlayerMagazineMultiplierElite",
                   "m_PlayerGrenadeMultiplierRecruit",
                   "m_PlayerGrenadeMultiplierVeteran",
                   "m_PlayerGrenadeMultiplierElite"))
    scale("zoom", ZOOM)
    scale("sensitivity", ("m_fXSensitivityMultiplier",
                          "m_fYSensitivityMultiplier"))
    scale("reload", ("m_fReloadSpeed",))
    scale("ragdoll", ("m_fKarmaImpactFactor", "m_fKarmaImpactAngularFactor"))
    scale("blood", ("m_fBloodStainMinSize", "m_fBloodStainMaxSize",
                    "m_fBloodStainGrowthTime"))
    scale("tracers", ("m_fBulletTracersSpeed", "m_fBulletTracersLength"))

    falling = v.get(prefix + "falling_damage", "stock")
    if falling == "off":
        # Every threshold pushed past any drop a level contains. 99999 cm is a
        # kilometre; the fields are five and four characters wide and the
        # scaler refuses anything that will not fit, so these are set outright.
        setters.update({"m_iSafeFallingHeight": "99999",
                        "m_iLowerWoundFallingHeight": "99999",
                        "m_iUpperWoundFallingHeight": "99999",
                        "m_iDeathFallingHeight": "99999"})
    elif falling == "harsh":
        setters.update({"m_iSafeFallingHeight": "00150",
                        "m_iLowerWoundFallingHeight": "0250",
                        "m_iUpperWoundFallingHeight": "0350",
                        "m_iDeathFallingHeight": "0450"})

    ammo_switch = v.get(prefix + "unlimited_teammate_ammo", "stock")
    if ammo_switch != "stock":
        setters["m_bUnlimitedRainbowMagazines"] = ammo_switch

    # Gated on the ammunition switch, not merely shown beneath it: while
    # magazines are unlimited the clip count is pinned at 1 and the branch this
    # reaches is unreachable, so writing the script alone would be a change to
    # the game that could not do anything.
    sidearm = int(v.get(prefix + "sidearm", 0)) if ammo_switch == "false" else 0
    say = int(v.get(prefix + "say_dry", 0))
    if sidearm or say:
        contact = bool(v.get(prefix + "sidearm_contact", True))
        notes = []
        if sidearm:
            notes.append("%d%% chance of drawing the pistol instead of "
                         "reloading%s"
                         % (sidearm, " while in contact" if contact else ""))
        if say:
            notes.append("%d%% chance of calling out a reload" % say)
        out.append(FileEdit("ai_sidearm", SCRIPT_FILES,
                            {"chance": sidearm, "in_contact": contact,
                             "say_chance": say},
                            "; ".join(notes)))

    aim = v.get(prefix + "aim_ps2", "stock")
    if aim != "stock":
        for key, value in PS2_AIM.items():
            if key == AIM_DEADZONE and aim == "ps2_keep_deadzone":
                continue
            setters[key] = value

    for key, who in CHEAT_KEYS:
        choice = v.get(prefix + "cheat_" + who.lower(), "stock")
        if choice != "stock":
            setters[key] = choice

    if factors:
        out.append(FileEdit("scale_ini", SETTINGS_FILE, {"factors": factors},
                            "gameplay table: %d value%s scaled"
                            % (len(factors), "" if len(factors) == 1 else "s")))
    if setters:
        out.append(FileEdit("ini_values", SETTINGS_FILE, {"values": setters},
                            "gameplay table: " + ", ".join(sorted(setters))))

    if has_templates:
        pct = int(v.get(prefix + "tpt_skill", 100))
        if pct != 100:
            out.append(FileEdit("tpt_values", r"\.TPT$", {"scale": pct / 100.0},
                                "terrorist template skills at %d%%" % pct))
        gren = int(v.get(prefix + "grenades", 0))
        if gren:
            out.append(FileEdit("grenade_carry", r"\.TPT$", {"percent": gren},
                                "%d%% of terrorists carry a grenade" % gren))
    return out

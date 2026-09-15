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
                     "Turning it off is a realism option."),
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

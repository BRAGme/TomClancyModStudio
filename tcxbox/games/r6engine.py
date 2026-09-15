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

class Aim:
    """One game's stick-to-turn-rate table, and what can be done about it.

    Eleven control points map how far the stick is pushed, in tenths, to how
    fast the view turns in degrees per second. `ENGINE.U` declares them as UE2
    `config` properties and `R6GAMESETTINGS.INI` carries the values, so editing
    the ini is the whole mechanism.

    This is a per-game record rather than a module constant because the answer
    is per-game, and assuming otherwise shipped a broken option once: the card
    was written from GRAW's numbers and rendered for Rainbow Six 3 too, where
    it offered to install values the disc already had.

      * `stock`    -- what this game's Xbox disc ships.
      * `alts`     -- {name: curve} this tool offers. Authored, not derived: a
                      formula that suits one game's range flatters the other.
      * `ps2`      -- {ini key: value} off the PS2 release, or None when the
                      two discs agree or there is no PS2 release.
      * `table`    -- rows for the card, both columns measured.
      * `same`     -- rows for the "nothing to change" card, when `ps2` is None
                      because the discs already agree.
    """

    def __init__(self, stock, alts, ps2=None, table=(), same=()):
        self.stock = stock
        self.alts = alts
        self.ps2 = ps2
        self.table = table
        self.same = same


def _curve_table(stock, alts):
    """Header plus eleven rows, one per tenth of stick travel."""
    order = ("smooth", "precision", "linear")
    head = ("stick", "stock", "smooth", "precise", "linear", "")
    rows = [head]
    for n, label in enumerate(("at rest", "1/10", "2/10", "3/10", "4/10",
                               "half", "6/10", "7/10", "8/10", "9/10",
                               "full")):
        rows.append((label, str(stock[n]))
                    + tuple(str(alts[k][n]) for k in order)
                    + ("deg/s" if n == 0 else
                       ("<- the one you feel" if n == 5 else ""),))
    return tuple(rows)


# -- Rainbow Six 3 and Black Arrow ------------------------------------------
#: Both ship the same eleven points, and so does the Rainbow Six 3 PS2 disc:
#: its own `R6GAMESETTINGS.INI` inside `vokes0.img` (17,267 bytes) carries
#: these numbers, `m_fDeadZone=0.1`, `m_fSmoothingTime=0.20`,
#: `m_fAimDamping=0.8`, `m_fRotationZoomingMultiplier=0.7` and 0.70/0.60
#: sensitivity -- all identical to the Xbox copy inside `xboxdynamic.umd`
#: (16,690 bytes). Of the 250 keys the two share, 15 differ and none is an aim
#: key. There is nothing to port.
R63_STOCK = (1, 6, 12, 18, 24, 30, 50, 80, 120, 140, 270)

#: Same top speed, no cliff. The shipped ratios run 6.0, 2.0, 1.5, 1.33, 1.25,
#: 1.67, 1.6, 1.5, 1.17, 1.93 -- the curve eases off through the middle and
#: then nearly doubles in the last tenth. This is a steady 1.53x per step.
R63_SMOOTH = (1, 6, 9, 14, 21, 33, 50, 76, 116, 177, 270)

#: Half the stick spent below 30 deg/s, top speed untouched. For overshooting.
R63_PRECISION = (1, 4, 8, 13, 20, 30, 46, 74, 120, 185, 270)

#: Turn rate exactly proportional to deflection -- the literal reading of
#: "1:1". Not obviously what anyone wants: a tenth of a push turns at 28 deg/s
#: instead of 6, so small corrections get harder. Offered because it is the
#: thing the words describe.
R63_LINEAR = (1, 28, 55, 82, 109, 135, 162, 189, 216, 243, 270)

R63_ALTS = {"smooth": R63_SMOOTH, "precision": R63_PRECISION,
            "linear": R63_LINEAR}

R63_SAME = (
    ("", "Xbox", "PS2", ""),
    ("turn curve", "same", "same", "all eleven points"),
    ("dead zone", "0.1", "0.1", ""),
    ("smoothing", "0.20", "0.20", "seconds"),
    ("aim damping", "0.8", "0.8", "when auto-aim has a target"),
    ("zoomed turn", "0.7", "0.7", "multiplier while scoped"),
    ("sensitivity", "0.70 / 0.60", "0.70 / 0.60", "X / Y"),
    ("aim lock-on", "absent", "present", "PS2 only -- see below"),
)

R63_AIM = Aim(R63_STOCK, R63_ALTS, ps2=None,
              table=_curve_table(R63_STOCK, R63_ALTS), same=R63_SAME)

#: Black Arrow never had a PS2 release, so it gets the curve options and no
#: comparison at all.
BA_AIM = Aim(R63_STOCK, R63_ALTS, ps2=None,
             table=_curve_table(R63_STOCK, R63_ALTS))

# -- Ghost Recon: Advanced Warfighter ---------------------------------------
#: GRAW is the game where the platforms really do diverge, and it is where the
#: numbers below came from originally. Xbox, out of `/System/R6GAMESETTINGS.INI`
#: on the disc: the eleven points are exactly 2.7 * n^2, so the curve
#: accelerates the whole way and half a push already asks for 67.5 deg/s. PS2,
#: out of the same file inside `vokes0.img` (18,486 bytes) on the GRAW PS2
#: disc: 35 deg/s at half, and close to straight. 49 of the 254 keys the two
#: discs share differ, and all 18 aim keys are among them.
GRAW_STOCK = ("0.0", "2.7", "10.8", "24.3", "43.2", "67.5", "97.2", "132.3",
              "172.8", "230.7", "320.0")

#: Even ramp to the same top speed -- takes the explosion out of the last third
#: without giving up the ability to spin round.
GRAW_SMOOTH = (0, 3, 7, 13, 23, 40, 64, 100, 155, 225, 320)

#: Deliberately slow through the first half. GRAW's stock curve is steep from
#: the very first tenth, so this is the larger change of the two.
GRAW_PRECISION = (0, 1, 3, 6, 11, 20, 36, 66, 120, 200, 320)

GRAW_LINEAR = (0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320)

GRAW_ALTS = {"smooth": GRAW_SMOOTH, "precision": GRAW_PRECISION,
             "linear": GRAW_LINEAR}

#: Every aim key off the GRAW PS2 disc, including the two that are not part of
#: the curve: smoothing is near zero there (0.01 against 0.15), and the zoom
#: multiplier is BELOW one where Xbox's is 2.5 -- the Xbox build turns two and
#: a half times FASTER while scoped, which is the single oddest number on
#: either disc and most of why the scope is hard to hold.
GRAW_PS2_AIM = {
    "m_afRotationControlPoints[0]": 1,
    "m_afRotationControlPoints[1]": 4,
    "m_afRotationControlPoints[2]": 8,
    "m_afRotationControlPoints[3]": 15,
    "m_afRotationControlPoints[4]": 24,
    "m_afRotationControlPoints[5]": 35,
    "m_afRotationControlPoints[6]": 48,
    "m_afRotationControlPoints[7]": 60,
    "m_afRotationControlPoints[8]": 80,
    "m_afRotationControlPoints[9]": 110,
    "m_afRotationControlPoints[10]": 180,
    "m_fRotationControlPoint": 90,
    "m_fRotationZoomingMultiplier": 0.9,
    "m_fSmoothingTime": "0.01",
    "m_fAimDamping": 0.8,
    "m_fDeadZone": 0.1,
    "m_fXSensitivityMultiplier": "0.60",
    "m_fYSensitivityMultiplier": "0.52",
}

#: Split out of `GRAW_PS2_AIM` by the "keep the dead zone" choice. A tenth was
#: chosen when PS2 sticks were new; a worn Xbox stick can drift inside it, and
#: 0.35 is a long way to come down in one step.
AIM_DEADZONE = "m_fDeadZone"

GRAW_PS2_TABLE = (
    ("stick", "Xbox", "PS2", ""),
    ("at rest", "0.0", "1", "deg/s"),
    ("1/10", "2.7", "4", ""),
    ("2/10", "10.8", "8", ""),
    ("3/10", "24.3", "15", ""),
    ("4/10", "43.2", "24", ""),
    ("half", "67.5", "35", "<- the one you feel"),
    ("6/10", "97.2", "48", ""),
    ("7/10", "132.3", "60", ""),
    ("8/10", "172.8", "80", ""),
    ("9/10", "230.7", "110", ""),
    ("full", "320.0", "180", ""),
    ("", "", "", ""),
    ("dead zone", "0.35", "0.10", "share of travel that does nothing"),
    ("zoomed turn", "2.5", "0.9", "multiplier while scoped"),
    ("smoothing", "0.15", "0.01", "seconds"),
    ("aim damping", "0.65", "0.80", ""),
    ("max rate", "160", "90", "deg/s the vertical is scaled against"),
    ("sensitivity X", "0.70", "0.60", ""),
    ("sensitivity Y", "0.10", "0.52", ""),
)

GRAW_AIM = Aim(GRAW_STOCK, GRAW_ALTS, ps2=GRAW_PS2_AIM,
               table=_curve_table(GRAW_STOCK, GRAW_ALTS))


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


def _aim_cards(prefix, aim):
    """The turning cards for one game: a curve, a dead zone, and either the
    PS2 disc's table or a note saying there is nothing to bring across."""
    out = [
        Setting(prefix + "aim_curve", "Turning curve", CHOICE, "stock", FEEL,
                choices=[
                    Choice("stock", "As shipped", "The disc's own eleven."),
                    Choice("smooth", "Smooth",
                           "Same top speed, evenly ramped."),
                    Choice("precision", "Precision",
                           "Slow through the first half of the stick, same "
                           "top speed. For overshooting."),
                    Choice("linear", "Linear (1:1)",
                           "Turn rate exactly proportional to how far the "
                           "stick is pushed."),
                ],
                confidence="applied",
                help="The eleven control points that map stick deflection to "
                     "turn rate in degrees per second. They live in "
                     "R6GAMESETTINGS.INI and are declared in Engine.u, so "
                     "this is the real dial and not the in-game slider.\n\n"
                     "Smooth evens out the ramp. Precision keeps the top "
                     "speed but makes the first half of the stick slower, "
                     "which is the half you use to settle on a target.",
                table=aim.table),
        Setting(prefix + "deadzone", "Stick dead zone", CHOICE, "stock", FEEL,
                choices=[
                    Choice("stock", "As shipped", ""),
                    Choice("0.05", "Tighter", "0.05 -- reacts sooner."),
                    Choice("0.10", "Tight", "0.10."),
                    Choice("0.20", "Wider", "0.20."),
                    Choice("0.35", "Widest", "0.35 -- for a drifting stick."),
                ],
                confidence="applied",
                help="m_fDeadZone: the share of stick travel that does "
                     "nothing at all. Tightening it makes the smallest "
                     "corrections register, at the cost of letting a worn "
                     "stick drift on its own.",
                caution="If the view creeps while you are not touching the "
                        "stick, this went the wrong way -- go wider."),
    ]
    if aim.ps2:
        out.insert(1, Setting(
            prefix + "aim_ps2", "PlayStation 2 aiming", CHOICE, "stock", FEEL,
            choices=[
                Choice("stock", "As shipped", "The Xbox numbers."),
                Choice("ps2", "PlayStation 2",
                       "The PS2 disc's own values, dead zone included."),
                Choice("ps2_keep_deadzone", "PlayStation 2, stock dead zone",
                       "The PS2 values, but this disc's dead zone left "
                       "alone."),
            ],
            confidence="applied",
            help="Replaces the whole aim table with the one the PS2 release "
                 "ships. Every number below is read off the two discs, not "
                 "estimated.\n\n"
                 "The curve is the headline, but the two rows under it matter "
                 "as much: smoothing is near zero on PS2, and the scoped "
                 "multiplier is below one where this disc's is 2.5 -- the "
                 "Xbox build turns two and a half times FASTER while you are "
                 "looking down a scope.",
            table=aim.table if not aim.ps2 else GRAW_PS2_TABLE,
            caution="The PS2 dead zone is 0.10 against this disc's 0.35. On a "
                    "worn controller that can let the stick drift on its own "
                    "-- if it does, use the stock dead zone choice."))
    if aim.same:
        out.append(Setting(
            prefix + "aim_vs_ps2", "Xbox aiming against PS2", CHOICE, "stock",
            FEEL, choices=[Choice("stock", "Nothing to change here", "")],
            enabled=False,
            disabled_reason="Nothing to apply. The two discs already ship "
                            "identical aim tables, and the keys that make the "
                            "difference do not exist in this build.",
            help="If you came here looking for the PS2 aiming: it is already "
                 "here. Both discs ship the same eleven control points and "
                 "the same dead zone, smoothing, damping, zoom multiplier and "
                 "sensitivity. Of the 250 keys the two copies of "
                 "R6GAMESETTINGS.INI share, 15 differ, and none of them is an "
                 "aim key.\n\n"
                 "What the PS2 disc has and this one does not is a magnetic "
                 "lock-on: fMaxAutoAimDistance, SpeedBaseX and SpeedBaseY, "
                 "fAngleInNormal and fAngleInZoom, and four fLockSpeedLimit "
                 "keys, which drag the reticle toward a target inside a cone. "
                 "Those names appear nowhere in this disc's Engine.u or "
                 "default.xbe, so the Xbox build cannot be told to do it and "
                 "writing the keys into the ini would be ignored. That, not "
                 "sensitivity, is why the PS2 version is easier to put a "
                 "crosshair on someone with.\n\n"
                 "The nearest thing available here is the Precision curve, "
                 "plus a tighter dead zone.",
            table=aim.same))
    return out


def cards(prefix, has_templates, aim, has_script=True):
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
    ] + (_sidearm_cards(prefix) if has_script else []) + [
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
    ] + _aim_cards(prefix, aim) + [
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


def edits(prefix, v, has_templates, aim, has_script=True):
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
    if not has_script:
        sidearm = say = 0
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

    # Order matters: the PS2 table rewrites the same eleven points the curve
    # choice does, so whichever the user set LAST would otherwise depend on
    # dictionary order rather than on intent. The PS2 option is the broader of
    # the two, so it goes first and a curve choice refines it.
    ps2 = v.get(prefix + "aim_ps2", "stock")
    if aim.ps2 and ps2 != "stock":
        for key, value in aim.ps2.items():
            if key == AIM_DEADZONE and ps2 == "ps2_keep_deadzone":
                continue
            setters[key] = value

    curve = v.get(prefix + "aim_curve", "stock")
    if curve in aim.alts:
        for n, rate in enumerate(aim.alts[curve]):
            setters["m_afRotationControlPoints[%d]" % n] = rate

    dead = v.get(prefix + "deadzone", "stock")
    if dead != "stock":
        setters[AIM_DEADZONE] = dead

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

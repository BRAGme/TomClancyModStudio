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

from .. import showlog
from ..model import BOOL, CHOICE, INT, Choice, FileEdit, Setting

ENEMIES = "Enemies"
SQUAD = "Your side"
FEEL = "Feel"
CHEATS = "Cheats"

SETTINGS_FILE = r"R6GAMESETTINGS\.INI$"

#: `R6Game.u`, inside `System\\xboxufiles.umd` -- a fixed slot, so the
#: script edit that lands here has to keep the package's length exactly.
COOP_PACKAGE = r"/R6GAME\.U$"

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

    A per-game record, even though all three Xbox discs turned out to share a
    curve, because the things around the curve are not shared: the dead zone,
    the scoped multiplier and GRAW's Y sensitivity all differ, and so does
    which PS2 disc is the one to compare against.

      * `stock`     -- what this game's Xbox disc ships.
      * `alts`      -- {name: curve} this tool offers. Authored, not derived.
      * `ps2`       -- {ini key: value} off the PS2 release to port, or None.
      * `table`     -- rows for the curve card.
      * `ps2_table` -- rows for the PS2 card. Both columns measured off stock
                       discs; see `XBOX_STOCK` for what happens when they are
                       not.
    """

    def __init__(self, stock, alts, ps2=None, table=(), ps2_table=()):
        self.stock = stock
        self.alts = alts
        self.ps2 = ps2
        self.table = table
        self.ps2_table = ps2_table


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


# -- what every Xbox build ships -------------------------------------------
#: All three Xbox discs carry the SAME eleven control points, and they are
#: exactly 2.7 * n^2: 0, 2.7, 10.8, 24.3, 43.2, 67.5, 97.2, 132.3, 172.8,
#: 230.7, 320. Measured on stock data in every case -- Rainbow Six 3 and GRAW
#: from discs this tool had not edited, Black Arrow through its own pre-edit
#: backup.
#:
#: **This file once said otherwise, and the way it got there is worth keeping.**
#: A census read Rainbow Six 3's disc AFTER the tool had applied its own PS2
#: aiming option to it, found the PS2 numbers sitting in the Xbox ini, and
#: concluded the two platforms agreed. A working option was then deleted and
#: replaced with a card explaining that there was nothing to port. Both were
#: wrong. `engine.has_backup` answers "is this disc stock" in one call, and
#: asking it costs nothing next to retracting a feature that worked.
XBOX_STOCK = ("0.0", "2.7", "10.8", "24.3", "43.2", "67.5", "97.2", "132.3",
              "172.8", "230.7", "320.0")

#: Even ramp to the same top speed -- takes the explosion out of the last third
#: without giving up the ability to spin round.
XBOX_SMOOTH = (0, 3, 7, 13, 23, 40, 64, 100, 155, 225, 320)

#: Deliberately slow through the first half. The shipped curve is steep from
#: the very first tenth, so this is the larger change of the two.
XBOX_PRECISION = (0, 1, 3, 6, 11, 20, 36, 66, 120, 200, 320)

#: Turn rate exactly proportional to deflection -- the literal reading of
#: "1:1". Not obviously what anyone wants: a tenth of a push turns at 32 deg/s
#: instead of 2.7, so small corrections get harder. Offered because it is the
#: thing the words describe.
XBOX_LINEAR = (0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320)

XBOX_ALTS = {"smooth": XBOX_SMOOTH, "precision": XBOX_PRECISION,
             "linear": XBOX_LINEAR}

#: The three Xbox discs differ from each other in only three numbers, none of
#: them on the curve: the dead zone (Rainbow Six 3 0.40, Black Arrow and GRAW
#: 0.35), the scoped multiplier (1.0, 1.0, and GRAW's odd 2.5) and GRAW's Y
#: sensitivity of 0.10 against everyone else's 0.60.
XBOX_DEAD_ZONE = {"r63_": "0.40", "ba_": "0.35", "graw_": "0.35"}


def _ps2_aim(points, control, zoom, smoothing, damping, dead, sens_x=None,
             sens_y=None):
    """A PS2 disc's aim table as a dict of ini writes."""
    out = {"m_afRotationControlPoints[%d]" % n: v
           for n, v in enumerate(points)}
    out.update({"m_fRotationControlPoint": control,
                "m_fRotationZoomingMultiplier": zoom,
                "m_fSmoothingTime": smoothing,
                "m_fAimDamping": damping,
                AIM_DEADZONE: dead})
    if sens_x is not None:
        out["m_fXSensitivityMultiplier"] = sens_x
    if sens_y is not None:
        out["m_fYSensitivityMultiplier"] = sens_y
    return out


#: Split out of a PS2 table by the "keep the dead zone" choice. A tenth was
#: chosen when PS2 sticks were new; a worn Xbox stick can drift inside it, and
#: 0.40 is a long way to come down in one step.
AIM_DEADZONE = "m_fDeadZone"

#: Rainbow Six 3 PS2, out of `R6GAMESETTINGS.INI` inside `vokes0.img`. Verified
#: against that disc's own pre-edit backup, which matches it key for key.
R63_PS2_AIM = _ps2_aim((1, 6, 12, 18, 24, 30, 50, 80, 120, 140, 270),
                       90, 0.7, "0.20", 0.8, 0.1)

#: Ghost Recon Advanced Warfighter PS2, same file inside `vokes0.img` (18,486
#: bytes). That disc has never been edited, so the live bytes are the shipped
#: ones.
GRAW_PS2_AIM = _ps2_aim((1, 4, 8, 15, 24, 35, 48, 60, 80, 110, 180),
                        90, 0.9, "0.01", 0.8, 0.1, "0.60", "0.52")


def _ps2_table(ps2_points, xbox_dead, ps2_dead, xbox_zoom, ps2_zoom,
               ps2_smoothing, ps2_damping, extra=()):
    """The two-column comparison a PS2 aiming card shows.

    Both columns are read off discs. The stick rows are labelled by how far the
    stick is pushed rather than by array index: `m_afRotationControlPoints[5]`
    means nothing, "half" means something.
    """
    rows = [("stick", "Xbox", "PS2", "")]
    for n, label in enumerate(("at rest", "1/10", "2/10", "3/10", "4/10",
                               "half", "6/10", "7/10", "8/10", "9/10",
                               "full")):
        rows.append((label, XBOX_STOCK[n], str(ps2_points[n]),
                     "deg/s" if n == 0 else
                     ("<- the one you feel" if n == 5 else "")))
    rows += [
        ("", "", "", ""),
        ("dead zone", xbox_dead, ps2_dead, "share of travel that does nothing"),
        ("zoomed turn", xbox_zoom, ps2_zoom, "multiplier while scoped"),
        ("smoothing", "0.15", ps2_smoothing, "seconds"),
        ("aim damping", "0.65", ps2_damping, ""),
        ("max rate", "160", "90", "deg/s the vertical is scaled against"),
    ]
    rows += list(extra)
    return tuple(rows)


R63_PS2_TABLE = _ps2_table((1, 6, 12, 18, 24, 30, 50, 80, 120, 140, 270),
                           "0.40", "0.10", "1.0", "0.7", "0.20", "0.80",
                           extra=(("sensitivity", "0.70 / 0.60",
                                   "0.70 / 0.60", "X / Y -- identical"),))

BA_PS2_TABLE = _ps2_table((1, 6, 12, 18, 24, 30, 50, 80, 120, 140, 270),
                          "0.35", "0.10", "1.0", "0.7", "0.20", "0.80",
                          extra=(("sensitivity", "0.70 / 0.60",
                                  "0.70 / 0.60", "X / Y -- identical"),))

GRAW_PS2_TABLE = _ps2_table((1, 4, 8, 15, 24, 35, 48, 60, 80, 110, 180),
                            "0.35", "0.10", "2.5", "0.9", "0.01", "0.80",
                            extra=(("sensitivity X", "0.70", "0.60", ""),
                                   ("sensitivity Y", "0.10", "0.52", "")))

R63_AIM = Aim(XBOX_STOCK, XBOX_ALTS, ps2=R63_PS2_AIM,
              table=_curve_table(XBOX_STOCK, XBOX_ALTS),
              ps2_table=R63_PS2_TABLE)

#: Black Arrow had no PS2 release of its own. It runs the same engine on the
#: same curve, so Rainbow Six 3's PS2 table is still the thing to bring across
#: and the card says whose it is.
BA_AIM = Aim(XBOX_STOCK, XBOX_ALTS, ps2=R63_PS2_AIM,
             table=_curve_table(XBOX_STOCK, XBOX_ALTS),
             ps2_table=BA_PS2_TABLE)

GRAW_AIM = Aim(XBOX_STOCK, XBOX_ALTS, ps2=GRAW_PS2_AIM,
               table=_curve_table(XBOX_STOCK, XBOX_ALTS),
               ps2_table=GRAW_PS2_TABLE)


#: The auto-aim the Xbox build DOES have. Rainbow Six 3 PS2's magnetic lock-on
#: cannot be ported (its key names are in no Xbox binary), but these three are
#: declared in `Engine.u` and shipped on all three discs, and together they are
#: the assist that is actually here:
#:
#:   * `m_fAimDamping` -- rotation is multiplied by this while the auto-aim
#:     system holds a target, so LOWER means the view slows down harder as you
#:     pass over someone. 0.8 on Rainbow Six 3 and Black Arrow, 0.65 on GRAW.
#:   * `m_fAimDampingMinZone` -- the fraction of the circle within which that
#:     damping is at full strength. 0.300 everywhere.
#:   * `m_fAimStrafeStickiness` -- how much the aim is dragged along with a
#:     target you are strafing past. 0.175 everywhere.
#:
#: The four steps below move all three together, because moving one alone gives
#: a result nobody would describe as "more help" or "less".
AIM_ASSIST = {
    "off": {"m_fAimDamping": "1.0", "m_fAimDampingMinZone": "0.000",
            "m_fAimStrafeStickiness": "0.000", "m_bAutoAimZoom": "FALSE"},
    "stronger": {"m_fAimDamping": "0.6", "m_fAimDampingMinZone": "0.450",
                 "m_fAimStrafeStickiness": "0.300", "m_bAutoAimZoom": "TRUE"},
    "strongest": {"m_fAimDamping": "0.4", "m_fAimDampingMinZone": "0.600",
                  "m_fAimStrafeStickiness": "0.500", "m_bAutoAimZoom": "TRUE"},
}

AIM_ASSIST_TABLE = (
    ("", "off", "stock", "stronger", "strongest", ""),
    ("turn damping", "1.0", "0.8", "0.6", "0.4", "lower = slows more"),
    ("full-effect zone", "0.000", "0.300", "0.450", "0.600", "share of circle"),
    ("strafe stickiness", "0.000", "0.175", "0.300", "0.500", ""),
    ("zoom snaps on", "no", "yes", "yes", "yes", ""),
)

#: The two circles and the debug overlay behind them. Rainbow Six 3 ships with
#: the aiming circle OFF and GRAW ships with it ON, which is why this is a
#: per-disc switch rather than a single toggle.
RETICLE = {
    "both": {"m_bShowAimingCircle": "TRUE", "m_bShowAutoAimCircle": "TRUE"},
    "aiming": {"m_bShowAimingCircle": "TRUE", "m_bShowAutoAimCircle": "FALSE"},
    "neither": {"m_bShowAimingCircle": "FALSE", "m_bShowAutoAimCircle": "FALSE"},
}

#: How far a hit shoves the view. Rainbow Six 3 and Black Arrow ship 2000.0
#: against GRAW's 100.0 -- a twentyfold difference, and the reason being shot
#: in Rainbow Six 3 throws your aim off the screen. The two side factors scale
#: it per target: your squad takes half (0.5), terrorists take half again more
#: (1.5). `m_fWeaponJumpFactor` is the muzzle climb that rides along with it.
#: Only the base and the muzzle climb are scaled. The two side factors are
#: RATIOS applied on top of the base, so scaling them as well would square the
#: change -- at "half", the squad would take a quarter rather than a half --
#: and the shipped relationship between the three sides would not survive it.
FLINCH = ("m_fHitMoveFactor", "m_fWeaponJumpFactor")

#: What darkness is worth. These multiply an observer's chance of noticing you
#: in medium and low light -- 0.75 and 0.5, so full dark already halves it.
#: Scaling them DOWN makes night vision and shadow worth more.
LIGHT = ("m_fLowLightPenaltyFactor", "m_fMediumLightPenaltyFactor")

#: What moving is worth, on both sides of the look. The target factors are
#: above one because moving gets you seen (1.4 running, 1.2 walking); the
#: spotter factors are below one because moving makes you a worse observer
#: (0.6 and 0.8).
MOVING_SEEN = ("m_fTargetMovingRunPenaltyFactor",
               "m_fTargetMovingWalkPenaltyFactor")
MOVING_SPOT = ("m_fSpotterMovingRunPenaltyFactor",
               "m_fSpotterMovingWalkPenaltyFactor")

#: Accuracy by stance: standing still, walking, running, crouched. The three
#: modifiers ship at 1.0 and the duck bonus at 1.10, so stock barely
#: distinguishes them -- which is the interesting part.
STANCE = ("m_fRetStationaryAccuracyModifier", "m_fRetWalkingAccuracyModifier",
          "m_fRetWalkingFastAccuracyModifier", "m_fRetDuckAccuracyBonus")

#: Damage by where the round lands. Head is 10 for you and 2 for everyone
#: else, torso 2, arms and legs 1, and the thresholds decide how much damage a
#: limb absorbs before the wound registers (head 0, torso 30, arms/legs 40).
YOUR_HEADSHOTS = ("m_iPlayerShootsHeadMultiplier",
                  "m_iMPPlayerShootsHeadMultiplier",
                  "m_iRainbowShootsHeadMultiplier")
THEIR_HEADSHOTS = ("m_iTerroristShootsHeadMultiplier",
                   "m_iArmouredTerroristShootsHeadMultiplier")

#: How much being wounded costs you. Three bands, each a threshold on remaining
#: health and a multiplier on every skill roll: 0.75 -> 0.90, 0.50 -> 0.80,
#: 0.25 -> 0.70. Scaling the factors down makes injuries bite.
WOUND_SKILL = ("m_fLightlyWoundedSkillFactor", "m_fModeratelyWoundedSkillFactor",
               "m_fSeverelyWoundedSkillFactor")

#: GRAW and Black Arrow only -- Rainbow Six 3's build predates all six.
#: `m_bUnLockFPS` ships false. `m_fMaxAccel`/`m_fMaxDecel` are how fast you get
#: to walking speed and back to nothing (720 each). The boost trio is the
#: sprint: 1.25x above half stick, over a 9-unit zone.
#: `m_fBoostFactor` only. `m_fBoostThreshold` is the stick deflection sprint
#: begins at (0.5) and `m_fBoostZone` the width it ramps over -- doubling the
#: threshold would put sprint beyond full deflection and silently turn the
#: feature off, which is the opposite of what a dial called "double" promises.
BOOST = ("m_fBoostFactor",)
ACCEL = ("m_fMaxAccel", "m_fMaxDecel")


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
                    Choice("stock", "As shipped",
                           "0.40 on Rainbow Six 3, 0.35 on the other two."),
                    Choice("0.10", "PlayStation 2 (0.10)",
                           "What every PS2 disc here ships."),
                    Choice("0.20", "0.20", ""),
                    Choice("0.30", "0.30", ""),
                    Choice("0.40", "0.40", "For a stick that drifts."),
                ],
                confidence="applied",
                help="m_fDeadZone: the share of stick travel that does "
                     "nothing at all. The Xbox builds spend a third to two "
                     "fifths of the stick here and the PS2 discs a tenth, "
                     "which is most of why a small correction on Xbox has to "
                     "start with a shove. Tightening it makes the smallest "
                     "movements register, at the cost of letting a worn stick "
                     "drift on its own.",
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
            table=aim.ps2_table,
            caution="The PS2 dead zone is 0.10 against this disc's 0.35. On a "
                    "worn controller that can let the stick drift on its own "
                    "-- if it does, use the stock dead zone choice."))
    return out


def _extra_cards(prefix, has_boost):
    """The levers the first pass of this file left in the table."""
    out = [
        Setting(prefix + "aim_assist", "Aim assist", CHOICE, "stock", FEEL,
                choices=[
                    Choice("stock", "As shipped", ""),
                    Choice("off", "Off", "No damping, no stickiness, no "
                                         "snap on zoom."),
                    Choice("stronger", "Stronger", ""),
                    Choice("strongest", "Strongest", "As much as the three "
                                                     "keys allow."),
                ],
                confidence="applied",
                help="The Xbox build has its own aim assist and never exposes "
                     "it. Three keys drive it: the view slows while the "
                     "auto-aim system holds a target, the aim is dragged "
                     "along with a target you strafe past, and zooming snaps "
                     "onto one. This moves all three together.\n\n"
                     "This is the nearest thing to the PS2 lock-on that this "
                     "build can actually do.",
                table=AIM_ASSIST_TABLE),
        Setting(prefix + "reticle", "Aiming circles", CHOICE, "stock", FEEL,
                choices=[
                    Choice("stock", "As shipped", ""),
                    Choice("both", "Show both",
                           "The accuracy circle and the auto-aim circle."),
                    Choice("aiming", "Accuracy circle only", ""),
                    Choice("neither", "Hide both", ""),
                ],
                confidence="applied",
                help="Rainbow Six 3 ships with the accuracy circle hidden and "
                     "GRAW ships with it shown, from the same two keys. The "
                     "accuracy circle is how wide your shot can stray; the "
                     "auto-aim circle is the region the assist above works "
                     "in, so showing it is the way to see what that option "
                     "just did."),
        _scale_card(prefix + "flinch", "How hard a hit throws your aim", FEEL,
                    "m_fHitMoveFactor, and the muzzle climb with it. Rainbow "
                    "Six 3 and Black Arrow ship 2000 where GRAW ships 100 -- "
                    "twenty times as much -- which is why taking a round here "
                    "throws the view off the target. Half is a large change.",
                    "The two side factors ride along, so your squad keeps "
                    "taking half what you do and terrorists half again more."),
        Setting(prefix + "stance_accuracy", "Reticle accuracy", CHOICE,
                "stock", FEEL,
                choices=[Choice("stock", "As shipped", ""),
                         Choice("less", "Half", ""),
                         Choice("little_less", "Three quarters", ""),
                         Choice("little_more", "A quarter more", ""),
                         Choice("more", "Half again", ""),
                         Choice("much_more", "Double", "")],
                confidence="experimental",
                help="The four stance modifiers: standing still, walking, "
                     "running, and the crouch bonus. Three of them ship at "
                     "1.0, so the shipped game does not distinguish standing "
                     "from running at all -- scaling them together is "
                     "therefore one overall accuracy dial, not a way to "
                     "separate the stances.",
                caution="Which direction helps is inferred, not observed: the "
                        "crouch one is called a BONUS and ships above 1.0, so "
                        "higher reads as more accurate. Try it on one mission "
                        "before trusting it."),
        _scale_card(prefix + "minimap_zoom", "Minimap zoom", FEEL,
                    "The default zoom and the range the stick can take it "
                    "through -- 500 and 1000 centimetres."),
        _scale_card(prefix + "dark_helps", "What darkness is worth", ENEMIES,
                    "The chance of being noticed in medium and low light, "
                    "which ship at 0.75 and 0.5. LOWER is better for you: "
                    "half here means full dark hides you twice as well and "
                    "night vision is worth carrying.",
                    "Applies to terrorists looking at you and at your squad."),
        _scale_card(prefix + "moving_seen", "How much moving gets you seen",
                    ENEMIES,
                    "1.4 running and 1.2 walking, against 1.0 standing still. "
                    "Higher makes a slow approach matter more."),
        _scale_card(prefix + "moving_spot",
                    "How much moving spoils their watch", ENEMIES,
                    "The other half of the same test: a terrorist on the move "
                    "observes at 0.6 running and 0.8 walking. LOWER makes a "
                    "patrolling guard easier to slip past than a standing "
                    "one."),
        _scale_card(prefix + "search_time", "How long they search", ENEMIES,
                    "m_iDefaultSearchTime, 30 seconds, is how long a "
                    "terrorist who has lost you keeps looking before going "
                    "back to his patrol."),
        _scale_card(prefix + "their_headshots", "Their headshot damage",
                    ENEMIES,
                    "The head multiplier a terrorist gets, armoured or not -- "
                    "2 against the torso's 2 and a limb's 1. The shipped game "
                    "does not reward an enemy for hitting your head."),
        _scale_card(prefix + "your_headshots", "Your headshot damage", SQUAD,
                    "The head multiplier for you and your squad. Yours ships "
                    "at 10 and theirs at 2, so a Ghost is five times worse at "
                    "a head shot than you are.",
                    "Doubling yours makes almost any head hit fatal."),
        _scale_card(prefix + "wound_penalty",
                    "How much a wound costs you", SQUAD,
                    "The skill multiplier at each of the three wound bands -- "
                    "0.90 lightly, 0.80 moderately, 0.70 severely. LOWER "
                    "means being shot degrades you more.",
                    "The thresholds that decide which band you are in are "
                    "left alone, so the ladder keeps its shape."),
        _scale_card(prefix + "formation", "How far your squad spreads", SQUAD,
                    "m_iRainbowFormationDistance, 100 centimetres, is the "
                    "spacing the AI holds when it is following you."),
        _scale_card(prefix + "hostage_wounds", "How much a hostage survives",
                    SQUAD,
                    "m_iHostageMaximumWounds, 10. The two difficulty "
                    "modifiers on a terrorist's chance of executing one are "
                    "left alone."),
        Setting(prefix + "squad_size", "How many operatives you take", INT, 4,
                SQUAD, minimum=1, maximum=8, confidence="experimental",
                help="m_iNbOfRainbow, which ships at 4 -- you and three. "
                     "Whether a mission that places four start points can use "
                     "a fifth is not established, so this is offered as "
                     "something to try rather than something proven.",
                caution="Above 4 the extra operatives may have nowhere to "
                        "spawn. If a mission fails to load, put this back."),
    ]
    if has_boost:
        out += [
            Setting(prefix + "unlock_fps", "Unlock the frame rate", CHOICE,
                    "stock", FEEL,
                    choices=[Choice("stock", "As shipped (locked)", ""),
                             Choice("true", "Unlocked", "")],
                    confidence="experimental",
                    help="m_bUnLockFPS ships false. The key exists on GRAW "
                         "and Black Arrow and not on Rainbow Six 3, so it is "
                         "something the engine gained late. What it does on "
                         "real hardware against an emulator has not been "
                         "watched, which is why it is badged experimental.",
                    caution="An unlocked frame rate on this engine can move "
                            "physics and animation timing with it. Try a "
                            "mission before committing to a campaign."),
            _scale_card(prefix + "sprint", "Sprint", FEEL,
                        "The boost trio: 1.25x speed above half stick "
                        "deflection, over a nine-unit zone."),
            _scale_card(prefix + "accel", "How fast you get moving", FEEL,
                        "m_fMaxAccel and m_fMaxDecel, both 720 -- how quickly "
                        "you reach walking speed and how quickly you stop.",
                        "Scaled together, so this is weight rather than "
                        "speed."),
        ]
    return out


def _coop_cards(prefix):
    return [
        Setting(prefix + "coop_squad", "AI teammates in System Link", CHOICE,
                "stock", "Game modes",
                choices=[
                    Choice("stock", "As shipped", "Single player only."),
                    Choice("on", "Let the host build the squad", ""),
                ],
                confidence="experimental",
                help="The squad is done in two steps after a level loads, "
                     "and each sits behind its own test on Level.NetMode: "
                     "DeployCharacters builds the team, then "
                     "SpawnAIandInitGoInGame spawns the operatives. Both "
                     "ask for NM_Standalone, and a System Link host is "
                     "NM_ListenServer, so neither runs and the squad is "
                     "never there.\n\n"
                     "Both tests become != NM_Client instead: true for "
                     "single player and for the host, false only for a "
                     "guest, whose teammates are replicated to it by the "
                     "host. Four bytes in all, same widths, so nothing in "
                     "the function moves.\n\n"
                     "Opening only the first was tried and was not enough: "
                     "the team object was built and nobody appeared, "
                     "because the pawns come from the second.",
                caution="Experimental in the strongest sense: it rewrites "
                        "compiled UnrealScript in R6Game.u, which every level "
                        "load reads, and it has been verified as bytes rather "
                        "than watched working. The guest is deliberately left "
                        "out -- the host owns the AI and replicates it -- so "
                        "teammates appearing for the host and nobody else is "
                        "the design, not a fault. Restore game puts the "
                        "package back byte for byte."),
        Setting(prefix + "show_log", "Log the squad being built", CHOICE,
                "stock", "Game modes",
                choices=[
                    Choice("stock", "As shipped", "Quiet."),
                    Choice("on", "Narrate the chain", ""),
                ],
                confidence="experimental",
                help="A diagnostic, not a feature. The script is full of "
                     "if (bShowLog) Log(...) lines, and bShowLog lives on "
                     "Actor, so every class carries its own copy. R6GameInfo "
                     "ships with it on, which is why the game mode already "
                     "talks; R6RainbowTeam does not, so the half that would "
                     "name the operative that failed to appear says "
                     "nothing.\n\n"
                     "There is no bit to flip -- a UE2 default list holds "
                     "only what differs from the parent, and neither Actor "
                     "nor R6RainbowTeam holds bShowLog at all -- so instead "
                     "each of these tests has its jump pointed at the line it "
                     "was skipping. The test still runs; both of its answers "
                     "now reach the log. Two bytes a site, and the value "
                     "written is an offset the function already "
                     "contained.\n\n"
                     "Forty sites, every one of them once per level or "
                     "once per player: the mode coming up, the player logging "
                     "in, the team built member by member, and the round "
                     "state machine. The several hundred per-frame ones are "
                     "deliberately left alone, because they would bury the "
                     "answer.",
                caution="This build has NOWHERE TO PUT THE TEXT, and that was "
                        "checked rather than assumed: the executable contains "
                        "no log file name, no drive path and no output-device "
                        "name, in ASCII or in UTF-16 -- only execLog, the "
                        "native's own registration string. Log() is callable "
                        "and goes nowhere. Use \"Show where the squad chain "
                        "stops\" instead, which asks the same question in a "
                        "form you can see. Kept because it costs two bytes a "
                        "site and a debugger, or a build with the device "
                        "linked back in, would read it. Restore game puts "
                        "both packages back byte for byte."),
        Setting(prefix + "reach_probe", "Show where the squad chain stops",
                CHOICE, "stock", "Game modes",
                choices=[
                    Choice("stock", "As shipped", "No probe."),
                    Choice("on", "Turn the two markers on", ""),
                ],
                confidence="experimental",
                help="A diagnostic you read off the screen, because the log "
                     "cannot be read at all in this build.\n\n"
                     "Two conditions in the squad's chain already guard "
                     "effects you can SEE, and each has its jump pointed at "
                     "the body it was skipping, exactly as the log option "
                     "does. NotifyAfterLevelChange turns on god mode for a "
                     "training map; SpawnAIandInitGoInGame unlocks every door "
                     "when the level asks it to. Forced on, they answer a "
                     "question the game will not otherwise tell you:\n\n"
                     "  * invulnerable = the console's level-change handler "
                     "ran all the way to its end, so both NetMode gates "
                     "passed;\n"
                     "  * every door unlocked = the second gate passed and "
                     "the spawn-and-init step ran.\n\n"
                     "If BOTH show up in System Link and there are still no "
                     "teammates, the squad is being built and then thrown "
                     "away, which points at the third conditional at the end "
                     "of that same function -- the one that sends a "
                     "multiplayer game straight to BetweenRound. If neither "
                     "shows up, the handler is not running there at all.",
                caution="This makes you invulnerable and opens every locked "
                        "door, on every map, in every mode. It is a "
                        "measuring instrument, not a way to play -- turn it "
                        "off once it has told you what you needed. Two bytes, "
                        "both of them a jump word inside R6Game.u, and "
                        "Restore game puts the package back byte for byte."),
    ]


def _coop_edits(prefix, v):
    out = []
    if v.get(prefix + "coop_squad") == "on":
        out.append(FileEdit("coop_team", COOP_PACKAGE, {},
                            "the System Link host builds the AI squad"))
    if v.get(prefix + "show_log") == "on":
        out.append(FileEdit("show_log", showlog.PACKAGES, {},
                            "the squad chain narrates itself into the log"))
    if v.get(prefix + "reach_probe") == "on":
        out.append(FileEdit("reach_probe", COOP_PACKAGE, {},
                            "two visible markers show how far the chain got"))
    return out


def cards(prefix, has_templates, aim, has_script=True,
          has_boost=False):
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
    ] + _aim_cards(prefix, aim) + _extra_cards(prefix, has_boost) + [
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
    out += _coop_cards(prefix)
    return out


def edits(prefix, v, has_templates, aim, has_script=True,
          has_boost=False):
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

    out += _coop_edits(prefix, v)

    curve = v.get(prefix + "aim_curve", "stock")
    if curve in aim.alts:
        for n, rate in enumerate(aim.alts[curve]):
            setters["m_afRotationControlPoints[%d]" % n] = rate

    dead = v.get(prefix + "deadzone", "stock")
    if dead != "stock":
        setters[AIM_DEADZONE] = dead

    assist = v.get(prefix + "aim_assist", "stock")
    if assist in AIM_ASSIST:
        setters.update(AIM_ASSIST[assist])

    circles = v.get(prefix + "reticle", "stock")
    if circles in RETICLE:
        setters.update(RETICLE[circles])

    scale("flinch", FLINCH)
    scale("stance_accuracy", STANCE)
    scale("minimap_zoom", ("m_fMinimapZoomDefault", "m_fMinimapZoomRange"))
    scale("dark_helps", LIGHT)
    scale("moving_seen", MOVING_SEEN)
    scale("moving_spot", MOVING_SPOT)
    scale("search_time", ("m_iDefaultSearchTime",))
    scale("their_headshots", THEIR_HEADSHOTS)
    scale("your_headshots", YOUR_HEADSHOTS)
    scale("wound_penalty", WOUND_SKILL)
    scale("formation", ("m_iRainbowFormationDistance",))
    scale("hostage_wounds", ("m_iHostageMaximumWounds",))

    squad = int(v.get(prefix + "squad_size", 4))
    if squad != 4:
        setters["m_iNbOfRainbow"] = squad

    if has_boost:
        fps = v.get(prefix + "unlock_fps", "stock")
        if fps != "stock":
            setters["m_bUnLockFPS"] = fps
        scale("sprint", BOOST)
        scale("accel", ACCEL)

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

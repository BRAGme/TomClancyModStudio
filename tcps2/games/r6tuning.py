"""The tuning the Unreal-family discs share, in one place.

Rainbow Six 3, Ghost Recon 2 and Advanced Warfighter all ship the same
`R6GAMESETTINGS.INI`, and for the AI keys they ship the same *values* -- every
number below was read off all three discs and compared, not assumed:

    m_fTerroristSkillMultiplier{Recruit,Veteran,Elite}   0.20 / 0.70 / 1.25
    m_fDistForPerfectAccuracyTerro                       500.0
    m_fSightRadius                                       5000.0
    m_fReactionTimeForFiring{Recruit,Veteran}            1.0 / 0.5
    m_fGrenadeReactionDelay{Recruit,Veteran}             1.0 / 0.5
    m_fMinDistToThrowGrenade                             500
    m_iDefaultSearchTime                                 30
    m_fTerrorist{Relax,Walking,Running}Speed             +116.0 / +170.0 / +518.0
    m_fSpotterMoving{Walk,Run}PenaltyFactor              0.8 / 0.6
    m_fTargetMoving{Walk,Run}PenaltyFactor               1.2 / 1.4
    m_PlayerGrenadeMultiplier{Recruit,Veteran,Elite}     1 / 1 / 1

The one key that differs is the look sensitivity multiplier: Rainbow Six 3 and
Ghost Recon 2 ship 0.70/0.60, Advanced Warfighter 0.60/0.52. That is why the
sensitivity helpers take the base as an argument rather than assuming it.

Each profile owns its own setting keys -- they are prefixed per game so two
discs' saved settings never collide -- and passes the prefix in here. Nothing in
this module writes anything; it returns the INI updates a profile then wraps in
its own `FileEdit`.
"""

from __future__ import annotations

from ..model import CHOICE, INT, Choice, Setting

# -- the shipped values, as strings, exactly as they appear on disc ---------
STOCK = {
    "skill": ("0.20", "0.70", "1.25"),
    "perfect_dist": 500,
    "sight": 5000,
    "fire_delay": ("1.0", "0.5"),
    "grenade_delay": ("1.0", "0.5"),
    "grenade_dist": 500,
    "search_time": 30,
    "speeds": ("+116.0", "+170.0", "+518.0"),
    "spotter": ("0.8", "0.6"),
    "target": ("1.2", "1.4"),
    "player_grenades": 1,
    "player_mags": 0,
    "sens_steps": 10,
}

SKILL_SETS = {
    "stock": ("0.20", "0.70", "1.25"),
    "up":    ("0.28", "0.98", "1.75"),
    "elite": ("1.25", "1.25", "1.25"),
    "down":  ("0.12", "0.42", "0.75"),
}

#: how long after acquiring you an NPC waits before firing
FIRE_DELAYS = {
    "stock": ("1.0", "0.5"),
    "quick": ("0.5", "0.25"),
    "snap":  ("0.15", "0.1"),
}

GRENADE_DELAYS = {
    "stock":   ("1.0", "0.5"),
    "quick":   ("0.5", "0.25"),
    "instant": ("0.1", "0.05"),
}

#: relax / walk / run, in the game's own units. The leading `+` is how the file
#: ships them and is kept, because nothing is gained by changing the spelling.
SPEEDS = {
    "stock":  ("+116.0", "+170.0", "+518.0"),
    "slow":   ("+87.0", "+128.0", "+389.0"),      # 0.75x
    "fast":   ("+145.0", "+213.0", "+648.0"),     # 1.25x
    "sprint": ("+174.0", "+255.0", "+777.0"),     # 1.5x
}

#: what moving does to whether you are seen. The spotter pair penalises the
#: watcher for moving; the target pair rewards him for the fact that YOU are.
SPOTTING = {
    "stock":   (("0.8", "0.6"), ("1.2", "1.4")),
    "sharp":   (("1.0", "0.9"), ("1.5", "1.9")),
    "blind":   (("0.5", "0.3"), ("1.0", "1.0")),
}


def ini_updates(p: str, v: dict) -> dict:
    """The INI keys a values dict implies, for the settings that are shared.

    `p` is the profile's setting-key prefix ("" for Rainbow Six 3, "gr2_" for
    Ghost Recon 2, "graw_" for Advanced Warfighter). Only keys the caller
    actually defined are looked at, and a value still at its shipped setting
    contributes nothing -- so an all-default config writes an empty dict and the
    disc is never touched.
    """
    out = {}

    skill = v.get(p + "skill", "stock")
    if skill != "stock":
        rec, vet, eli = SKILL_SETS[skill]
        out["m_fTerroristSkillMultiplierRecruit"] = rec
        out["m_fTerroristSkillMultiplierVeteran"] = vet
        out["m_fTerroristSkillMultiplierElite"] = eli

    fire = v.get(p + "fire_delay", "stock")
    if fire != "stock":
        rec, vet = FIRE_DELAYS[fire]
        out["m_fReactionTimeForFiringRecruit"] = rec
        out["m_fReactionTimeForFiringVeteran"] = vet

    delay = v.get(p + "grenade_delay", "stock")
    if delay != "stock":
        rec, vet = GRENADE_DELAYS[delay]
        out["m_fGrenadeReactionDelayRecruit"] = rec
        out["m_fGrenadeReactionDelayVeteran"] = vet

    if p + "grenade_dist" in v and int(v[p + "grenade_dist"]) != 500:
        out["m_fMinDistToThrowGrenade"] = int(v[p + "grenade_dist"])

    if p + "perfect_dist" in v and int(v[p + "perfect_dist"]) != 500:
        out["m_fDistForPerfectAccuracyTerro"] = "%.1f" % float(v[p + "perfect_dist"])

    if p + "sight" in v and int(v[p + "sight"]) != 5000:
        out["m_fSightRadius"] = "%.1f" % float(v[p + "sight"])

    if p + "search_time" in v and int(v[p + "search_time"]) != 30:
        out["m_iDefaultSearchTime"] = int(v[p + "search_time"])

    speed = v.get(p + "speed", "stock")
    if speed != "stock":
        relax, walk, run = SPEEDS[speed]
        out["m_fTerroristRelaxSpeed"] = relax
        out["m_fTerroristWalkingSpeed"] = walk
        out["m_fTerroristRunningSpeed"] = run

    spot = v.get(p + "spotting", "stock")
    if spot != "stock":
        (sw, sr), (tw, tr) = SPOTTING[spot]
        out["m_fSpotterMovingWalkPenaltyFactor"] = sw
        out["m_fSpotterMovingRunPenaltyFactor"] = sr
        out["m_fTargetMovingWalkPenaltyFactor"] = tw
        out["m_fTargetMovingRunPenaltyFactor"] = tr

    mult = int(v.get(p + "player_grenades", 1))
    if mult != 1:
        for tier in ("Recruit", "Veteran", "Elite"):
            out["m_PlayerGrenadeMultiplier" + tier] = mult

    # 0 means "leave the shipped 3/2/2 alone"; anything else applies to all
    # three tiers, because the point of the dial is a flat rule about how much
    # ammunition you start a mission with rather than a difficulty curve.
    mags = int(v.get(p + "player_mags", 0))
    if mags:
        for tier in ("Recruit", "Veteran", "Elite"):
            out["m_PlayerMagazineMultiplier" + tier] = mags

    return out


def sens_updates(p: str, v: dict, base: dict) -> dict:
    """The look-curve keys, against this disc's own shipped multipliers."""
    out = {}
    steps = int(v.get(p + "sens_steps", 10))
    if steps != 10:
        out["m_iXSensitivityMaxSteps"] = steps
        out["m_iYSensitivityMaxSteps"] = steps
    boost = int(v.get(p + "sens_boost", 100)) / 100.0
    if abs(boost - 1.0) > 0.001:
        out["m_fXSensitivityMultiplier"] = "%.3f" % (base["x_mult"] * boost)
        out["m_fYSensitivityMultiplier"] = "%.3f" % (base["y_mult"] * boost)
        out["m_fXSensitivityStepIncrement"] = "%.3f" % (base["x_step"] * boost)
        out["m_fYSensitivityStepIncrement"] = "%.3f" % (base["y_step"] * boost)
    return out


# ---------------------------------------------------------------------------
# the cards themselves
# ---------------------------------------------------------------------------
#
# Three discs, one wording. A profile asks for the cards it wants by name and
# gets them prefixed with its own key, so Rainbow Six 3's `skill` and Advanced
# Warfighter's `graw_skill` are the same card and never collide in a saved
# settings file.

def card(name, prefix, group="Enemies", **over):
    """One shared setting, keyed for this profile."""
    build = _CARDS[name]
    return build(prefix + name, group, over)


def cards(names, prefix, group="Enemies"):
    return [card(n, prefix, group) for n in names]


def _skill(key, group, over):
    return Setting(key, "Enemy skill", CHOICE, "stock", group,
                   confidence="applied", touches="data",
                   choices=[
                       Choice("stock", "Stock (0.20 / 0.70 / 1.25)", ""),
                       Choice("up", "Sharper (+40%)", ""),
                       Choice("elite", "Everyone near-elite",
                              "All three tiers at 1.25, so a recruit-difficulty "
                              "enemy shoots like an elite one."),
                       Choice("down", "Softer (-40%)", ""),
                   ],
                   help="The per-difficulty multiplier the AI scales its aim "
                        "and its reactions by. This is the broadest accuracy "
                        "dial the game has -- it moves every enemy at once.",
                   **over)


def _fire_delay(key, group, over):
    return Setting(key, "How fast they open fire", CHOICE, "stock", group,
                   confidence="applied", touches="data",
                   choices=[
                       Choice("stock", "Stock (1.0s recruit, 0.5s veteran)", ""),
                       Choice("quick", "Quicker (0.5s / 0.25s)", ""),
                       Choice("snap", "Almost instant (0.15s / 0.1s)",
                              "They shoot as soon as they see you. Hard."),
                   ],
                   help="The pause between an enemy acquiring you and pulling "
                        "the trigger. Together with skill this is what makes a "
                        "firefight feel dangerous or forgiving.",
                   **over)


def _perfect_dist(key, group, over):
    return Setting(key, "Range at which enemies never miss", INT, 500, group,
                   minimum=50, maximum=3000, unit="units",
                   confidence="applied", touches="data",
                   help="Inside this distance an enemy's shots have no "
                        "dispersion at all -- they simply hit. It ships at 500. "
                        "Lowering it is the most direct way to make enemies "
                        "survivable up close; raising it does the opposite.",
                   **over)


def _sight(key, group, over):
    return Setting(key, "How far enemies can see you", INT, 5000, group,
                   minimum=500, maximum=15000, unit="units",
                   confidence="applied", touches="data",
                   help="The spotting radius every enemy searches inside. It "
                        "ships at 5000. Raising it makes open ground genuinely "
                        "dangerous; lowering it makes stealth much easier.",
                   caution="This is the raw radius. The movement factors still "
                           "apply on top of it, so the practical distance is "
                           "shorter when you are still and longer when you run.",
                   **over)


def _search_time(key, group, over):
    return Setting(key, "How long they hunt after losing you", INT, 30, group,
                   minimum=2, maximum=180, unit="seconds",
                   confidence="applied", touches="data",
                   help="Break contact and an enemy keeps looking for this "
                        "long before giving up and going back to his patrol. "
                        "It ships at 30 seconds. Raise it and breaking line of "
                        "sight stops being an escape.",
                   **over)


def _speed(key, group, over):
    return Setting(key, "How fast enemies move", CHOICE, "stock", group,
                   confidence="applied", touches="data",
                   choices=[
                       Choice("stock", "Stock (116 / 170 / 518)", ""),
                       Choice("slow", "Slower (-25%)",
                              "More time to react to a flank."),
                       Choice("fast", "Faster (+25%)", ""),
                       Choice("sprint", "Much faster (+50%)",
                              "They close ground fast. Changes the game."),
                   ],
                   help="The relaxed, walking and running speeds, scaled "
                        "together. This is the difficulty lever that changes "
                        "how fights play rather than just how much they hurt.",
                   **over)


def _spotting(key, group, over):
    return Setting(key, "How much movement gives you away", CHOICE, "stock",
                   group, confidence="applied", touches="data",
                   choices=[
                       Choice("stock", "Stock", ""),
                       Choice("sharp", "They notice movement more",
                              "A moving enemy loses less of his own vision, "
                              "and a moving target is spotted further away."),
                       Choice("blind", "They notice movement less",
                              "Moving stops helping them find you, which "
                              "rewards running between cover."),
                   ],
                   help="Four factors decide this. Two penalise a MOVING "
                        "enemy's own eyesight (0.8 walking, 0.6 running); two "
                        "extend how far he spots a target who is moving (1.2 "
                        "walking, 1.4 running). They move together here.",
                   **over)


def _grenade_dist(key, group, over):
    return Setting(key, "How close enemies will throw grenades", INT, 500,
                   group, minimum=25, maximum=900, unit="units",
                   confidence="applied", touches="data",
                   help="The game will not let an enemy throw at anything "
                        "nearer than this, and it ships at 500 -- far enough "
                        "that a lot of fights never qualify. If grenades feel "
                        "absent, this is the dial: 150-250 puts them in rooms "
                        "instead of only across open ground.",
                   **over)


def _grenade_delay(key, group, over):
    return Setting(key, "How long they think about it first", CHOICE, "stock",
                   group, confidence="applied", touches="data",
                   choices=[
                       Choice("stock", "Stock (1.0s recruit, 0.5s veteran)", ""),
                       Choice("quick", "Quicker (0.5s / 0.25s)",
                              "Roughly twice as many grenades per fight."),
                       Choice("instant", "Barely any (0.1s / 0.05s)",
                              "They throw the moment they have a reason to."),
                   ],
                   help="The reaction delay before an enemy commits to a throw.",
                   **over)


def _player_grenades(key, group, over):
    return Setting(key, "Grenades you carry", INT, 1, group, minimum=1,
                   maximum=10, unit="x", confidence="applied", touches="data",
                   help="The AMMO MULTIPLIERS block scales what you start a "
                        "mission holding. Magazines already ship multiplied -- "
                        "3x on Recruit, 2x above it -- but grenades ship at 1x "
                        "on all three. This multiplies them the same way.",
                   caution="It multiplies the loadout, so it does nothing for "
                           "a kit you sent out with no grenades in it.",
                   **over)


def _player_mags(key, group, over):
    return Setting(key, "Magazines you start with", INT, 0, group, minimum=0,
                   maximum=10, unit="x", confidence="applied", touches="data",
                   help="The same AMMO MULTIPLIERS block, for magazines. This "
                        "is the number behind starting a mission with far more "
                        "ammunition than you can use: the kit's own magazine "
                        "count is multiplied by 3 on Recruit and 2 on Veteran "
                        "and Elite. Setting this to 1 gives you exactly what "
                        "the kit says and nothing spare, which is the setting "
                        "to use if you want running dry to be a real "
                        "possibility. 0 leaves the shipped 3/2/2 alone.",
                   caution="There is no way to pick a weapon up off the "
                           "ground in this game, so a dry primary means the "
                           "sidearm and then nothing. 1x is a real "
                           "constraint; go lower and you cannot.",
                   **over)


def _sens_steps(key, group, over):
    return Setting(key, "Look sensitivity ceiling", INT, 10, group, minimum=10,
                   maximum=30, unit="steps", confidence="applied",
                   touches="data",
                   help="The in-game sensitivity slider stops at 10. This "
                        "raises how far it goes, so there are faster settings "
                        "to pick than the game normally offers.",
                   **over)


def _sens_boost(key, group, over):
    return Setting(key, "Look speed at each step", INT, 100, group, minimum=50,
                   maximum=400, unit="%", confidence="applied", touches="data",
                   help="Scales the sensitivity multiplier and the per-step "
                        "increment together, so every notch on the slider "
                        "moves the camera further. 100% is stock.",
                   **over)


_CARDS = {
    "skill": _skill,
    "fire_delay": _fire_delay,
    "perfect_dist": _perfect_dist,
    "sight": _sight,
    "search_time": _search_time,
    "speed": _speed,
    "spotting": _spotting,
    "grenade_dist": _grenade_dist,
    "grenade_delay": _grenade_delay,
    "player_grenades": _player_grenades,
    "player_mags": _player_mags,
    "sens_steps": _sens_steps,
    "sens_boost": _sens_boost,
}

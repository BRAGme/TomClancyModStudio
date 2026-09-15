"""What each Xbox build tunes differently from its PS2 counterpart.

Two of the three Unreal-engine discs have an Xbox sibling running the same
engine with the same settings under the same names, so the two builds can be
compared key by key and the differences offered as an option.

Where the numbers came from
---------------------------

* **Rainbow Six 3**: `System/xboxdynamic.umd` on the Xbox disc, which is that
  build's data files concatenated as plain text with their original comments
  intact. 239 keys in common with the PS2 build, 21 of them different.

* **Advanced Warfighter**: `System/R6GameSettings.ini`, a plain file on the
  Xbox disc. 243 keys in common, 38 different.

The PS2 side of the Rainbow Six 3 comparison had to come out of the backup
store rather than off a disc. A first pass read the disc directly and reported
33 differences; twelve were the player's own edits. A disc that has been
played with does not say what the game shipped with.

**Ghost Recon 2 is not here, and cannot be.** Its Xbox version is a different
game on a different engine -- the disc has no `System` folder, no `.u`
packages, and not one of these key names anywhere in it. There is nothing to
compare the PS2 build against.

What the differences say
------------------------

For Rainbow Six 3 the aim half is the bigger half: the PS2 port made the stick
markedly more forgiving. Kick is less than half, the dead zone a quarter, and
zooming slows your turn where the Xbox build does not.

Advanced Warfighter is a stranger story. Its aim differences run the same way,
but its **wound counts do not**: the Xbox build gives the player twice the
punishment, a Rainbow team-mate NINE times as much, and a terrorist six times
as much. That build is far less lethal all round rather than harder, which is
why the wounds are their own switch here and not part of a difficulty set.
"""

from __future__ import annotations

R6_3 = "r6_3_slus20883"
GRAW = "graw_slus21422"

#: the enemy half, per disc
ENEMY = {
    R6_3: {
        "m_fTerroristSkillMultiplierRecruit": "0.40",
        "m_fMinDistToThrowGrenade": "500",
    },
    GRAW: {
        "m_fTerroristSkillMultiplierRecruit": "0.40",
    },
}

#: the aim half, which on both discs is most of the difference
AIM = {
    R6_3: {
        "m_fWeaponJumpFactor": "125.0",
        "m_fDeadZone": "0.40",
        "m_fAimDamping": "0.65",
        "m_fSmoothingTime": "0.15",
        "m_fRotationControlPoint": "160",
        "m_fRotationZoomingMultiplier": "1.0",
    },
    GRAW: {
        "m_fWeaponJumpFactor": "125.0",
        "m_fDeadZone": "0.35",
        "m_fAimDamping": "0.65",
        "m_fSmoothingTime": "0.15",
        "m_fRotationControlPoint": "160",
        "m_fRotationZoomingMultiplier": "2.5",
    },
}

#: the third group, which differs in kind between the two discs
EXTRA = {
    R6_3: {
        "m_bUnlimitedRainbowMagazines": "true",
        "m_iNbOfBulletWhenEmpty": "5",
    },
    GRAW: {
        "m_iPlayerMaximumWounds": "120",
        "m_iRainbowMaximumWounds": "360",
        "m_iTerroristMaximumWounds": "60",
        "m_iMPPlayerMaximumWounds": "60",
    },
}

#: how to label that third group on each disc
EXTRA_LABEL = {
    R6_3: ("...including the Xbox ammunition rules",
           "The other two differences go the other way: the Xbox build gives "
           "Rainbow unlimited magazines and leaves 5 rounds in a weapon that "
           "has run dry, where the PS2 build gives neither. Separate from the "
           "difficulty set because it makes the game easier, not harder."),
    GRAW: ("...including the Xbox wound counts",
           "The Xbox build is far less lethal on every side at once: the "
           "player takes 120 wounds instead of 60, a Rainbow team-mate 360 "
           "instead of 40, a terrorist 60 instead of 10, and a multiplayer "
           "player 60 instead of 20. Everyone soaks up far more fire, which "
           "is a different game rather than a harder one -- so it is its own "
           "switch."),
}

#: what each PS2 build ships, so a test can prove these really are differences
PS2_SHIPPED = {
    R6_3: {
        "m_fTerroristSkillMultiplierRecruit": "0.20",
        "m_fMinDistToThrowGrenade": "200",
        "m_fWeaponJumpFactor": "60.0",
        "m_fDeadZone": "0.1",
        "m_fAimDamping": "0.8",
        "m_fSmoothingTime": "0.20",
        "m_fRotationControlPoint": "90",
        "m_fRotationZoomingMultiplier": "0.7",
        "m_bUnlimitedRainbowMagazines": "false",
        "m_iNbOfBulletWhenEmpty": "0",
    },
    GRAW: {
        "m_fTerroristSkillMultiplierRecruit": "0.20",
        "m_fWeaponJumpFactor": "60.0",
        "m_fDeadZone": "0.1",
        "m_fAimDamping": "0.8",
        "m_fSmoothingTime": "0.01",
        "m_fRotationControlPoint": "90",
        "m_fRotationZoomingMultiplier": "0.40",
        "m_iPlayerMaximumWounds": "60",
        "m_iRainbowMaximumWounds": "40",
        "m_iTerroristMaximumWounds": "10",
        "m_iMPPlayerMaximumWounds": "20",
    },
}

CHOICES = ("stock", "enemies", "aim", "both")


def ini_updates(pid, choice, extra=False):
    """The INI keys one of the choices implies, for one disc."""
    out = {}
    if choice in ("enemies", "both"):
        out.update(ENEMY.get(pid, {}))
    if choice in ("aim", "both"):
        out.update(AIM.get(pid, {}))
    if extra:
        out.update(EXTRA.get(pid, {}))
    return out


def cards(pid, prefix, group):
    """The two cards, worded for whichever disc this is."""
    from ..model import BOOL, CHOICE, Choice, Setting

    aim = AIM[pid]
    enemy = ENEMY[pid]
    ps2 = PS2_SHIPPED[pid]
    moved = ", ".join(
        "%s %s to %s" % (k.replace("m_f", "").replace("m_i", ""), ps2[k], v)
        for k, v in sorted(enemy.items()))
    extra_label, extra_help = EXTRA_LABEL[pid]
    return [
        Setting(prefix + "xbox_tuning", "Play it the way the Xbox build does",
                CHOICE, "stock", group, confidence="measured", touches="data",
                choices=[Choice("stock", "Leave the PS2 tuning alone"),
                         Choice("enemies", "Enemies only"),
                         Choice("aim", "Aim and recoil only"),
                         Choice("both", "Both")],
                help="Both builds ship the same settings under the same names, "
                     "and this writes the ones that change how it plays. "
                     "Enemies: %s. Aim: the muzzle kicks more than twice as "
                     "hard (%s to %s), the stick dead zone grows from %s to "
                     "%s, and there is less damping settling the reticle. The "
                     "aim half is the bigger half -- the PS2 port was made "
                     "markedly more forgiving to aim with."
                     % (moved, ps2["m_fWeaponJumpFactor"],
                        aim["m_fWeaponJumpFactor"], ps2["m_fDeadZone"],
                        aim["m_fDeadZone"]),
                caution="The individual dials on this page and on Controls are "
                        "applied AFTER this, so anything you set yourself wins "
                        "over the Xbox value for that one key."),
        Setting(prefix + "xbox_extra", extra_label, BOOL, False, group,
                confidence="measured", touches="data", help=extra_help,
                requires={prefix + "xbox_tuning": ["enemies", "aim", "both"]}),
    ]

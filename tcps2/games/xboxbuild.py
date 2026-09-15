"""What the Xbox build of Rainbow Six 3 tunes differently from the PS2 one.

Both builds ship the same settings under the same names -- 239 keys in common
-- and 21 of them carry different numbers. The Xbox values were read out of
`System/xboxdynamic.umd`, which is that build's data files concatenated as
plain text with their original comments intact, and the PS2 values out of the
backup store rather than off a disc, because a disc that has been played with
no longer says what the game shipped with.

Of the 21, most are cosmetic or irrelevant to play -- tracer colours and speed,
HUD text colour, the ELO constant, two voice-chat timings. Seven are not, and
they are what the option here writes.

## Why the Xbox build plays harder

Two of the seven are the enemy:

    m_fTerroristSkillMultiplierRecruit   0.20 -> 0.40   recruits twice as able
    m_fMinDistToThrowGrenade              200 -> 500    grenades thrown from
                                                        further out, not in
                                                        your face

The other five are your own aim, and they are the bigger half. The PS2 port
made the stick markedly more forgiving:

    m_fWeaponJumpFactor                  60.0 -> 125.0  the muzzle kicks more
                                                        than twice as hard
    m_fDeadZone                           0.1 -> 0.40   four times the dead
                                                        zone before the stick
                                                        registers
    m_fAimDamping                         0.8 -> 0.65   less help settling the
                                                        reticle
    m_fSmoothingTime                     0.20 -> 0.15   less smoothing on the
                                                        look input
    m_fRotationControlPoint                90 -> 160    the turn curve's knee
                                                        moved, so fine aim
                                                        covers more of the
                                                        stick's travel

`m_fRotationZoomingMultiplier` (0.7 -> 1.0) goes with those: the Xbox build
does not slow your turn while zoomed.

## Two more, offered separately

    m_bUnlimitedRainbowMagazines        false -> true
    m_iNbOfBulletWhenEmpty                  0 -> 5

These go the other way -- the Xbox build is kinder about ammunition, which is
not what someone asking for the harder feel usually wants -- so they are their
own choice rather than part of the difficulty set.
"""

from __future__ import annotations

#: the enemy half
ENEMY = {
    "m_fTerroristSkillMultiplierRecruit": "0.40",
    "m_fMinDistToThrowGrenade": "500",
}

#: the aim half, which is what most of the difference actually is
AIM = {
    "m_fWeaponJumpFactor": "125.0",
    "m_fDeadZone": "0.40",
    "m_fAimDamping": "0.65",
    "m_fSmoothingTime": "0.15",
    "m_fRotationControlPoint": "160",
    "m_fRotationZoomingMultiplier": "1.0",
}

#: the ammunition half, which goes the other way
AMMO = {
    "m_bUnlimitedRainbowMagazines": "true",
    "m_iNbOfBulletWhenEmpty": "5",
}

#: what the PS2 build ships, so a test can prove these really are differences
PS2_SHIPPED = {
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
}

CHOICES = ("stock", "enemies", "aim", "both")


def ini_updates(choice, ammo=False):
    """The INI keys one of the choices implies."""
    out = {}
    if choice in ("enemies", "both"):
        out.update(ENEMY)
    if choice in ("aim", "both"):
        out.update(AIM)
    if ammo:
        out.update(AMMO)
    return out

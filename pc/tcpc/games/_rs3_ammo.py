r"""Raven Shield: giving ball and hollow-point ammunition a damage contrast.

## What actually separates the two rounds, and what does not

This module shipped once claiming the two rounds are barely different and
that the penetration field runs backwards. **Both were wrong**, and the
corrected picture is more interesting than the wrong one.

Three mechanics already separate them, all shipped, all working:

1. **`m_szBulletType`.** `R6Bullet` defaults to `"JHP"` and the 36 ball
   classes override it to `"FMJ"`. A hollow point that hits a person is
   deactivated on the spot; a ball round with energy left over keeps flying
   and can hit the man behind him.
2. **`m_iPenetrationFactor` is a DIVISOR**, not a rating. The budget a round
   gets is roughly `min(energy - falloff, 5000) / m_iPenetrationFactor`, and
   it passes a surface only if that budget beats the surface's own value. So
   the ball round's inherited 1 buys **four times** the budget of a hollow
   point's 4: ball goes through doors that hollow point bounces off. The data
   was already right. Reading the field as "how well it pierces" is what was
   backwards.
3. **`m_fKillStunTransfer`**, 0.25 against 0.5 -- a hollow-point kill staggers
   harder.

What genuinely does NOT differ is **damage and range**: `m_iEnergy` is the
same number in 35 of the 36 pairs that ship both, and `m_fRange` likewise.
The exception is `ammo545mm7N6Subsonic`, where the hollow point carries 12%
more of both.

## Where the 36 pairs live

33 are in `system\R6Weapons.u`. The other three belong to Gold's two
official expansions and sit in packages of their own -- the 9x39mm SP-6 in
Athena Sword's `ASWeapons.u`, and the 4.6x30mm normal and subsonic loads in
Iron Wrath's `MP2Weapons.u`. This option reached only the base game's until
now, so an expansion round kept its stock figures while everything else
moved. The package list is shared with the weapon options and lives in
`_rs3_weapons.py`, which also says why the two expansions are named one by
one rather than globbed: `Mods\` is where a person's OWN mods live too.

So the honest job for an option here is not "make them different" -- they are
-- but "give them a damage and range contrast as well", so the choice is felt
in a firefight and not only when shooting at a door.

## What this ships

* **FMJ -- ball.** Carries further and loses energy more slowly with distance,
  for less damage per hit. Already the round that beats doors and that can
  pass through one man into another.
* **JHP -- hollow point.** More damage and much more stagger, for shorter
  reach and faster falloff. Already the round that stops in what it hits.

Every figure is scaled from that calibre's OWN stock value, so the balance
between a .22 and a .50 is preserved. Stun is the exception and is set
absolutely, because it only ever holds 0.25 or 0.5 and four of the 36 pairs
do not follow the usual 0.25/0.50: the two `ammo762x54mmR` loads ship them
REVERSED, and the two `ammo30calMagnum` loads give the hollow point 0.25 as
well, so it gets no stagger bonus at all. Scaling would keep all four.

`m_fRangeConversionConst` is a quadratic energy-falloff term,
`RangeConversion(d) = d*d*c + c`. It also gates surface penetration at
distance, so a round given a faster falloff gets worse at doors further away,
which is consistent with everything else about a hollow point.

## What is deliberately NOT touched

**`m_iPenetrationFactor`, in either direction.** An earlier version of this
module dropped the hollow point's 4 to 1 and raised the shared base to 3 or 5,
under the heading "ball ammunition pierces cover". Both edits were harmful:
the first hands hollow points the ball round's door-breaking budget, and the
second DIVIDES every ball round's budget by 3 to 5 -- a 5.56 ball round falls
from 1442 to 480 and stops clearing a 500-point door. The field is already
correct and is left alone.

**Nor is general wall penetration a thing to reach for.** The machinery
exists -- `R6Bullet.HitWall` calls a native that returns an exit point -- but
it is opt-in per material and a material's `m_iPenetration` of 0 means
impenetrable. Only 110 of the base game's 8,412 materials set it, and 104 of
those are doors; the rest are a fence, a wardrobe, a screen and three other
thin props. No walls, no floors, no crates, and no config flag anywhere that
turns it on generally.
"""

from ..model import CHOICE, Choice, PropEdit, Setting
from ._rs3_weapons import AMMO_PACKAGES

#: Each profile: how the round's own stock figures are moved. `stun` is an
#: absolute because the field only ever holds 0.25 or 0.5, and one pair holds
#: them the wrong way round.
CHARACTER = {
    "realistic": {
        "fmj": dict(energy=0.90, rng=1.15, falloff=0.85, stun=0.20),
        "jhp": dict(energy=1.30, rng=0.85, falloff=1.30, stun=0.60),
    },
    "extreme": {
        "fmj": dict(energy=0.80, rng=1.30, falloff=0.70, stun=0.15),
        "jhp": dict(energy=1.60, rng=0.70, falloff=1.60, stun=0.90),
    },
}


def settings():
    return [
        Setting(
            "ammo_character", "What the two ammunition types do", CHOICE,
            "stock", group="Ammunition",
            help="Ball and hollow point already differ in three ways the game "
                 "never explains: ball goes through doors hollow point "
                 "bounces off, ball can pass through one man and hit the one "
                 "behind him, and a hollow-point kill staggers harder. What "
                 "they do NOT differ in is damage or range -- those are the "
                 "same number in 35 of the 36 pairs that offer both. This "
                 "adds that contrast, so the choice is felt in a firefight "
                 "and not only against a door.",
            caution="Every figure is scaled from that calibre's own stock "
                    "value, so the balance between a .22 and a .50 is kept. "
                    "The penetration figure is deliberately left alone: it is "
                    "already correct, and it is a DIVISOR, so raising it "
                    "makes a round worse. Nothing here has been watched in a "
                    "running game.",
            choices=[
                Choice("stock", "Stock",
                       "Same damage and range; the three differences above "
                       "are all there is."),
                Choice("realistic", "Give each round a job",
                       "Ball +15% range and slower falloff for -10% damage; "
                       "hollow point +30% damage and far more stagger for "
                       "-15% range and faster falloff."),
                Choice("extreme", "Make the choice matter",
                       "The same idea, pushed: ball -20% damage for +30% "
                       "range, hollow point +60% damage and triple stagger "
                       "for -30% range."),
            ],
            confidence="applied", touches="data"),
    ]


def edits(values):
    spec = CHARACTER.get(values["ammo_character"])
    if not spec:
        return []
    out = []
    for pkg in AMMO_PACKAGES:
        for cls, key in (("*FMJ", "fmj"), ("*JHP", "jhp")):
            how = spec[key]
            side = "ball" if key == "fmj" else "hollow point"
            out.append(PropEdit(pkg, cls=cls, prop="m_iEnergy",
                                scale=how["energy"], minimum=1,
                                note="%s damage" % side))
            out.append(PropEdit(pkg, cls=cls, prop="m_fRange",
                                scale=how["rng"], minimum=1,
                                note="%s range" % side))
            out.append(PropEdit(pkg, cls=cls, prop="m_fRangeConversionConst",
                                scale=how["falloff"], minimum=0.0001,
                                note="%s energy falloff" % side))
            # absolute, not scaled: the field only ever holds 0.25 or 0.5, and
            # four of the 36 pairs do not follow the usual 0.25/0.50 -- the two
            # `ammo762x54mmR` loads ship them REVERSED, and the two
            # `ammo30calMagnum` loads give the hollow point no bonus at all.
            out.append(PropEdit(pkg, cls=cls, prop="m_fKillStunTransfer",
                                value=how["stun"],
                                note="%s stopping power" % side))
    return out

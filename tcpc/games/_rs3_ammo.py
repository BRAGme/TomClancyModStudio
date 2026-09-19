r"""Raven Shield: making ball and hollow-point ammunition mean different things.

## The complaint is correct, and the data says why

Every weapon in the game offers FMJ or JHP. Across all 33 calibres that ship
both, read straight out of `R6Weapons.u`:

| field | FMJ | JHP |
|---|---|---|
| `m_iEnergy` (damage) | **identical in 32 of the 33 pairs** | |
| `m_fRange` | identical in 32 of 33 | |
| `m_fRangeConversionConst` | identical in 32 of 33 | |
| `m_fKillStunTransfer` | 0.25 | 0.5 |
| `m_iPenetrationFactor` | not authored -> inherits **1** | **4** |

So **the damage figure is literally the same number** in every calibre but
one -- `ammo545mm7N6Subsonic`, where the hollow point carries 12% more energy
and 12% more range, and which is also the only pair whose range differs at
all. Everywhere else the only thing separating the two rounds in ordinary
play is how hard a kill staggers, plus one field that runs the wrong way.

Because a hollow point is the round that is *supposed* not to over-penetrate.
Shipped, JHP pierces **four times** better than ball ammunition. Whichever way
the field is read, the two rounds are not opposites -- they are the same round
with one of them slightly better at everything.

One pair is inconsistent with the rest: `ammo762x54mmR` has its stun values
the other way round (FMJ 0.5, JHP 0.25). Setting stun absolutely rather than
scaling it corrects that as a side effect.

## What this option does about it

Gives each round a job, so the choice before a mission is a real one:

* **FMJ — ball.** Pierces more, carries further, loses energy more slowly with
  distance, and hits with less immediate shock. The round for long sight-lines
  and opposition that is behind something.
* **JHP — hollow point.** Much harder-hitting and far more staggering on an
  unarmoured target, but stops in what it hits and bleeds energy quickly over
  distance. The round for clearing rooms.

Every figure is scaled from that calibre's OWN stock value, so the balance
between a .22 and a .50 is preserved and only the FMJ-versus-JHP relationship
changes. Stun is the exception and is set absolutely, because it only ever
holds 0.25 or 0.5 and one pair holds them backwards.

`m_fRangeConversionConst` is treated as how fast energy bleeds off with
distance. That reading is not a guess: across the 68 ammunition classes that
author both, it correlates with `m_fRange` at **-0.895** on a log scale -- the
longest-reaching round in the game carries 0.0137 and the shortest 0.1231 --
so a bigger constant goes with a shorter round.

## The one thing that cannot be done cleanly

**FMJ classes do not author `m_iPenetrationFactor` at all**; they inherit it
from `R6Bullet`, and this tool cannot add a property to a compiled class
without moving every byte after it. So "ball ammunition pierces" has to be
done by raising the shared base value.

That base is inherited by 96 classes, and ten of them are not bullets --
`R6Grenade`, `R6FragGrenade`, `R6FlashBang`, `R6SmokeGrenade`, the claymore,
the breaching and remote charges. Nothing establishes whether a penetration
factor does anything at all for a thrown explosive. It is therefore a separate
switch rather than part of the main choice, and it says so.

## What this does to the enemy, which is worth knowing

Following `m_pBulletClass` with the package reader: of the 205 weapons that
name a round, **136 name an FMJ class** and the rest name a calibre family.
Not one names a JHP class. The AI has no loadout menu -- it fires whatever its
weapon points at.

So retuning FMJ retunes what the terrorists shoot, and retuning JHP does not.
That is not a bug to route around; it is the shape of the thing. Making ball
ammunition the cover-piercing round makes enemy fire better at coming through
cover, and choosing hollow points for yourself is choosing a round no enemy in
the game carries.
"""

from ..model import BOOL, CHOICE, Choice, PropEdit, Setting

AMMO = "system/R6Weapons.u"

#: the shared base every round without its own value falls back to
BASE_BULLET = "R6Bullet"

#: Each profile: how the round's own stock figures are moved. `stun` is an
#: absolute because the field only ever holds 0.25 or 0.5, and one pair holds
#: them the wrong way round.
CHARACTER = {
    "realistic": {
        "fmj": dict(energy=0.90, rng=1.15, falloff=0.85, stun=0.20),
        "jhp": dict(energy=1.30, rng=0.85, falloff=1.30, stun=0.60),
        "base_pen": 3,
    },
    "extreme": {
        "fmj": dict(energy=0.80, rng=1.30, falloff=0.70, stun=0.15),
        "jhp": dict(energy=1.60, rng=0.70, falloff=1.60, stun=0.90),
        "base_pen": 5,
    },
}


def settings():
    return [
        Setting(
            "ammo_character", "What the two ammunition types do", CHOICE,
            "stock", group="Ammunition",
            help="Raven Shield ships FMJ and JHP with the SAME damage figure "
                 "-- identical in 32 of the 33 calibres that offer both -- "
                 "and the same range. The only thing separating them in play "
                 "is how hard a kill staggers. This gives each round a job: "
                 "ball pierces more and reaches further, hollow point hits "
                 "much harder up close and stops in what it hits.",
            caution="Every figure is scaled from that calibre's own stock "
                    "value, so the balance between a .22 and a .50 is kept. "
                    "What the penetration figure actually governs -- how many "
                    "surfaces a round passes through, and whether body armour "
                    "is one of them -- is not established anywhere in the "
                    "data, so 'pierces' is the field's name rather than a "
                    "measured effect. Nothing here has been watched running.",
            choices=[
                Choice("stock", "Stock",
                       "Same damage, same range; hollow points pierce four "
                       "times better than ball."),
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
        Setting(
            "ammo_ball_pierces", "Ball ammunition pierces cover", BOOL, True,
            group="Ammunition", requires={"ammo_character":
                                          ["realistic", "extreme"]},
            help="Shipped, hollow points carry four times the penetration "
                 "figure of ball ammunition, which is the wrong way round. "
                 "The option above already drops hollow points to the base "
                 "value; this raises the base so ball ammunition is the one "
                 "that pierces.",
            caution="FMJ rounds do not carry a penetration value of their own "
                    "-- they inherit the shared one -- and a compiled class "
                    "cannot be given a new property, so this has to move the "
                    "base. Ninety-six classes inherit it, ten of which are "
                    "grenades and charges rather than bullets. Nothing "
                    "establishes whether penetration means anything for a "
                    "thrown explosive. Turn this off to leave the base alone.",
            confidence="experimental", touches="data"),
    ]


def edits(values):
    v = values
    spec = CHARACTER.get(v["ammo_character"])
    if not spec:
        return []
    out = []
    for cls, key in (("*FMJ", "fmj"), ("*JHP", "jhp")):
        how = spec[key]
        side = "ball" if key == "fmj" else "hollow point"
        out.append(PropEdit(AMMO, cls=cls, prop="m_iEnergy",
                            scale=how["energy"], minimum=1,
                            note="%s damage" % side))
        out.append(PropEdit(AMMO, cls=cls, prop="m_fRange",
                            scale=how["rng"], minimum=1,
                            note="%s range" % side))
        out.append(PropEdit(AMMO, cls=cls, prop="m_fRangeConversionConst",
                            scale=how["falloff"], minimum=0.0001,
                            note="%s energy falloff" % side))
        # absolute, not scaled: the field only ever holds 0.25 or 0.5, and
        # `ammo762x54mmR` ships them the wrong way round.
        out.append(PropEdit(AMMO, cls=cls, prop="m_fKillStunTransfer",
                            value=how["stun"],
                            note="%s stopping power" % side))

    # Hollow points stop in what they hit. They are the only rounds that
    # author a penetration value, so this one can be written directly.
    out.append(PropEdit(AMMO, cls="*JHP", prop="m_iPenetrationFactor",
                        value=1, note="hollow points do not over-penetrate"))

    if v["ammo_ball_pierces"]:
        out.append(PropEdit(AMMO, cls=BASE_BULLET,
                            prop="m_iPenetrationFactor",
                            value=spec["base_pen"], stock=1,
                            note="ball ammunition pierces cover"))
    return out

"""Bullet penetration: what a round will go through.

IT SHIPS SWITCHED OFF, AND NOT FOR THE REASON YOU WOULD GUESS
--------------------------------------------------------------

The energy model is real and complete. `R6Weapons +0x518 m_fKillEnergy` is
**muzzle energy in joules** -- 9 mm 596, .45 730, 5.56 1502, 7.62x39 2019,
.50 BMG 15830, read out of the class defaults in five EE images -- loaded into
`$f21` per pellet at `0x003F12FC`, with `$f20` the per-unit range decay set at
`0x003F1558`. The decay is scaled by 100, so falloff is effectively nil: an AK
loses 0.17% of its energy over fifty metres.

**But no energy value opens anything**, because the model is gated on
`Material.m_iPenetration` (+0x48, an INT, named in `Engine/Material.uc`), and
**every material the disc ships is 0** -- 493 loaded materials across three
levels, all class defaults, and zero validated overrides in all 36 containers.
Zero means impenetrable at `0x003F21D8`.

So raising the budget is not the edit. The edit is at the gate.

WHAT THE EDIT DOES
------------------

It folds `bProjTarget` into the pass-through test the code already runs on
`m_bBulletGoThrough`. Both bit positions were read off the `UBoolProperty`'s
own Offset and BitMask rather than guessed.

**What becomes penetrable:** closed doors, crates, office furniture,
computers, oil drums, cloth props, and elevator and gate movers.

**What does NOT:** walls, floors and ceilings. `bProjTarget` is clear on all
905 CollisionMeshActors, 187 StaticMeshActors and 71 Brushes across three
levels, and world geometry is hard-stopped separately at `0x003F1B14`.

So "shoot through plasterboard" is not honestly reachable: the disc ships no
data saying which surfaces are wood. Alcatraz tags both of its wooden
collision materials `Generic`.

THE COST OPTIONS
----------------

Damage and penetration are the same number -- the `iKillValue` handed to
`R6TakeDamage` IS the remaining budget -- so on any option that charges for a
layer, a round that spends most of its energy arrives weak. That is the whole
design: `doors_and_props` charges nothing and every gun gets through anything
at full damage; the others charge K joules per layer and let the calibre
ladder decide.

THE AI GETS IT TOO, SYMMETRICALLY
----------------------------------

It will not *aim* through a door -- `FastTrace` and `CanSee` do not read
`m_iPenetration` -- but `ATTACK_SprayFireNoStop` fires without consulting
`CanSee`, so suppressive fire at your last known position now comes through
the door you closed behind you. That is a real change to how the game plays,
not a side effect to be smoothed over.

Second thing to watch in play: five `Mover`s per level carry `bProjTarget`. If
a mission uses a large mover as a wall, rounds will cross it.
"""

from __future__ import annotations


class PenetrationError(Exception):
    pass


#: mode -> ((va, stock, new), ...). "off" is the shipped behaviour and emits
#: nothing; it is present so the card has something to name.
MODES = {
    "off": (
    ),
    "doors_and_props": (
        (0x003F21C0, 0x0002163C, 0x30420088),
        (0x003F21C4, 0x000217FE, 0x00000000),
    ),
    "cost_light": (
        (0x003F21C0, 0x0002163C, 0x304B0008),
        (0x003F21C4, 0x000217FE, 0x30420080),
        (0x003F21CC, 0x00000000, 0x240100C8),
        (0x003F21D8, 0x104000EA, 0x002B100B),
        (0x003F21DC, 0x00000000, 0x104000E9),
        (0x003F2408, 0x1080001A, 0x240100C8),
        (0x003F240C, 0x00000000, 0x0024200A),
    ),
    "cost_real": (
        (0x003F21C0, 0x0002163C, 0x304B0008),
        (0x003F21C4, 0x000217FE, 0x30420080),
        (0x003F21CC, 0x00000000, 0x24010258),
        (0x003F21D8, 0x104000EA, 0x002B100B),
        (0x003F21DC, 0x00000000, 0x104000E9),
        (0x003F2408, 0x1080001A, 0x24010258),
        (0x003F240C, 0x00000000, 0x0024200A),
    ),
    "rifles_only": (
        (0x003F21C0, 0x0002163C, 0x304B0008),
        (0x003F21C4, 0x000217FE, 0x30420080),
        (0x003F21CC, 0x00000000, 0x24010640),
        (0x003F21D8, 0x104000EA, 0x002B100B),
        (0x003F21DC, 0x00000000, 0x104000E9),
        (0x003F2408, 0x1080001A, 0x24010640),
        (0x003F240C, 0x00000000, 0x0024200A),
    ),
}

DEFAULT = "off"


def words(mode: str = DEFAULT):
    """[(va, stock, new)] for one mode."""
    if mode not in MODES:
        raise PenetrationError("no such penetration mode: %r" % (mode,))
    return [row for row in MODES[mode] if row[1] != row[2]]


def stock_words():
    """{va: stock} for every address any mode touches."""
    return {va: st for rows in MODES.values() for va, st, _nw in rows}


def cards(prefix, group):
    from .model import CHOICE, Choice, Setting

    return [
        Setting(
            prefix + "penetration", "What a round will go through", CHOICE,
            DEFAULT, group, confidence="experimental", touches="disc",
            choices=[
                Choice("off", "Nothing (as shipped)",
                       "Every surface in the game stops a bullet."),
                Choice("doors_and_props", "Doors and cover, freely",
                       "Any weapon, any number of layers, full damage."),
                Choice("cost_light", "Doors and cover, at a cost",
                       "Every gun still gets through, but arrives weaker."),
                Choice("cost_real", "Only what the calibre can manage",
                       "Pistols and submachine guns are stopped."),
                Choice("rifles_only", "Rifles only",
                       "7.62 and up."),
            ],
            help="The game has a complete penetration model -- muzzle energy "
                 "per cartridge, range falloff, a thickness cost per layer -- "
                 "and ships with it switched off, because every material on "
                 "the disc is marked impenetrable.\n\n"
                 "This turns it on for the things that were clearly meant to "
                 "be shot through: doors, crates, furniture, barrels and the "
                 "movers. Walls, floors and ceilings are untouched and stay "
                 "solid.\n\n"
                 "Damage and penetration are the same number, so on the "
                 "costed settings a round that spends its energy getting "
                 "through arrives weaker on the far side.",
            caution="Not yet played.\n\n"
                    "The AI gets this too. It will not aim through a door, "
                    "but its suppressive fire does not check line of sight -- "
                    "so shooting at where it last saw you now comes through "
                    "the door you closed.\n\n"
                    "A handful of movers per level are large. If a mission "
                    "uses one as a wall, rounds will cross it."),
    ]

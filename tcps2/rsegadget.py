"""Gadget dials: the breaching charge's stun reach, and the claymore's cone.

Both are four-byte float pokes inside existing bytecode -- the edit class this
disc has proven safe. Nothing moves, no length changes, no name or import is
added, and the package's first-touch order cannot shift because no reference
changes: only the bytes of a constant already there.

Where they live
---------------

NOT in `COMMON.LIN` / `COMMONOFF.LIN` / `COMMON_SS.LIN`. The gadget unit
classes are in the **60 single-player and co-op level containers** -- every
`<MAP>_AOFF` / `<MAP>_A_SS` / `<MAP>_BOFF` / `<MAP>_B_SS` plus the six
`TRAINING_*` halves, which carry no `_A`/`_B`. The 20 multiplayer containers
and the two menu ones do not have them. Measured against the disc: 60 files
carry both anchors, 25 carry neither, and all 60 copies are byte-identical.

The breaching charge's stun
---------------------------

It is not a property, so there is nothing in a class default to edit. It is a
float constant inside `R6BreachingChargeUnit.HurtPawns`::

    if (fDistFromGrenade < m_fExplosionRadius + 800.0)
        HitActor = Pawn.Trace(..., End=charge.Location,
                              Start=Pawn.Location + Pawn.EyePosition(), 39)
        if (HitActor == None || HitActor == Self)
            R6Pawn(Pawn).AffectedByGrenade(self, 4)

`m_fExplosionRadius` is 200 on that class, so the shipped stun reaches
200 + 800 = 1000 units, and 100 units is 1 metre -- **10 metres**, gated by a
line-of-sight trace to the charge. `AffectedByGrenade(pawn, 4)` gives the
victim 6 seconds of `m_eEffectiveGrenade = 4`. Type 4 does NOT white out a
human player's screen (type 3, the flashbang, does), so this dial moves how
far the blast disorients the AI and nothing else.

The lethal core is untouched: `m_fKillBlastRadius` 100 (1 m) and
`m_fExplosionRadius` 200 (2 m) are separate values this does not write.

The claymore's cone
-------------------

`R6ClaymoreUnit.HurtPawns` passes `0.766` to the radius-damage native, which
is `cos 40.004 degrees` -- so the blast is already a 40-degree forward cone.
Kept here because it is the same kind of poke and the anchor is verified, but
no card uses it yet.

Not established
---------------

Whether the stun currently lands at all. The explosion native runs first in
`HurtPawns` and chain-fires damage on the charge itself, which is what blows
the door; the per-pawn line-of-sight trace runs afterwards. So the door should
be gone by then -- but that ordering is inferred, and if it is wrong the door
blocks every trace and no value here would help.
"""

from __future__ import annotations

import re
import struct

#: name -> (bytes before the float, bytes after it, what it is)
ANCHORS = {
    "stun": (bytes.fromhex("b000420 2ae01211e".replace(" ", "")),
             bytes.fromhex("1616"),
             "breaching charge stun reach, added to m_fExplosionRadius"),
    "cone": (bytes.fromhex("6710019701 3c012101 67012 71e".replace(" ", "")),
             bytes.fromhex("16"),
             "claymore blast cone, as cos(half-angle)"),
}

#: What the disc ships, measured on all 60 containers. The cone is the literal
#: 0.766 the designers typed, not a computed cos(40) -- it works out to
#: cos 40.004 degrees, and storing the mathematical constant here would make
#: every "is this file stock?" check fail by 4e-5.
STOCK = {"stun": 800.0, "cone": 0.7659999728202820}

#: `m_fExplosionRadius` on R6BreachingChargeUnit, from its class defaults. The
#: test is `dist < m_fExplosionRadius + <stun>`, so the reach on screen is this
#: plus the dial -- which is why the card is in metres and the maths lives here.
BREACH_EXPLOSION_RADIUS = 200.0

#: 100 game units = 1 metre on this engine
UNITS_PER_METRE = 100.0

#: what the shipped constant works out to, in metres
STOCK_METRES = (BREACH_EXPLOSION_RADIUS + STOCK["stun"]) / UNITS_PER_METRE


class GadgetError(Exception):
    pass


def find(plain: bytes, which: str) -> int:
    """Offset of that anchor's four value bytes. Raises unless found once."""
    head, tail, _what = ANCHORS[which]
    good = [m.start() for m in re.finditer(re.escape(head), plain)
            if plain[m.start() + len(head) + 4:
                     m.start() + len(head) + 4 + len(tail)] == tail]
    if not good:
        raise GadgetError("the %s constant is not in this file" % which)
    if len(good) > 1:
        raise GadgetError("the %s constant appears %d times; refusing to guess"
                          % (which, len(good)))
    return good[0] + len(head)


def read(plain: bytes, which: str) -> float:
    return struct.unpack_from("<f", plain, find(plain, which))[0]


def reads_metres(plain: bytes) -> float:
    """The stun reach this file currently carries, in metres."""
    return (BREACH_EXPLOSION_RADIUS + read(plain, "stun")) / UNITS_PER_METRE


def write(plain: bytes, which: str, value: float):
    """Returns (bytes, changed). The length never moves."""
    at = find(plain, which)
    packed = struct.pack("<f", float(value))
    if plain[at:at + 4] == packed:
        return plain, 0
    out = bytearray(plain)
    out[at:at + 4] = packed
    if len(out) != len(plain):
        raise GadgetError("a four-byte poke changed the file length")
    return bytes(out), 1


def apply(plain: bytes, metres: float):
    """Set the breaching charge's stun reach, in metres. Returns (bytes, n)."""
    units = float(metres) * UNITS_PER_METRE - BREACH_EXPLOSION_RADIUS
    if units <= 0:
        raise GadgetError("a stun reach of %g m would be inside the blast "
                          "itself" % metres)
    return write(plain, "stun", units)


#: The 60 level containers and nothing else. COMMON/COMMONOFF/COMMON_SS end in
#: OFF or _SS too, and MENUOFF does, so they are excluded by name; the 20
#: multiplayer containers end `_MP_C` / `_MP_S` and never match.
SELECT = r"^/(?!COMMON|MENU)[A-Z_0-9]+(OFF|_SS)\.LIN$"


def card(prefix, group):
    from .model import INT, Setting

    return Setting(
        prefix + "breach_stun", "Breaching charge stun reach", INT,
        int(round(STOCK_METRES)), group,
        minimum=6, maximum=30, unit="m",
        confidence="experimental", touches="data",
        help="How far a breaching charge leaves enemies disoriented. The game "
             "ships this at 10 metres, and it is checked with a line of sight "
             "to the charge, so it does not reach through a wall that is still "
             "standing. This moves only the stun: the lethal core stays at 1 "
             "metre and the damage radius at 2, so a bigger number does not "
             "make the charge deadlier, only louder.",
        caution="Not yet played. It disorients the AI for six seconds -- it "
                "does not white out a human player's screen, which is the "
                "flashbang's job. Written into all 60 single-player and "
                "co-op level files; multiplayer is untouched.")

"""How long an RPG terrorist spends getting a rocket into the tube.

Rainbow Six 3 does have rocket troops, though not through the weapon tables
every other enemy uses. Whether a spawn zone produces them is
`m_bUseRocketLauncher`, a bit on `R6DeploymentZone` with no script readers at
all, so that choice is made natively. The terrorist side is
`R6TerroristAI.SetPrimaryWeapon` gating on
`m_pawn.m_bUseGrenadeLauncher && EngineWeapon.m_eWeaponType == 6`, then
`R6Terrorist.SetToRocket` spawning an `R6RocketLauncher` and attaching it to a
bone.

Why they always reload first
----------------------------

The load is an animation, and the animation is played at HALF SPEED. Four
one-line helpers on `R6Terrorist` each call `PlayAnim(<name>, 0.5)`, and two of
them are the rocket:

    StandFireRPG      rate 0.5
    StandReloadRPG    rate 0.5      <- the wait before the shot
    StandThrowGrenade rate 0.5
    StandBlinded      rate 0.5

The names were recovered by decoding the `EX_NameConst` compact index at each
call against the name table of the package at `0x86a7f` -- 6500 names -- which
is how a bare index became a readable name.

`PlayLoadRocket`, `SetRocketToLauncher` and `SetRocketToHand` have **no script
callers**: they are animation notifies, fired by name from inside the sequence.
That is why the rocket only reaches the launcher partway through the animation,
and why shortening the animation is the lever rather than reordering any code.

What this does NOT do
---------------------

It does not make them spawn already loaded, and it cannot give some of them a
spare rocket. `R6RocketLauncher` carries `m_aRocket` -- a single rocket object
-- plus `m_classRocket` and `m_wNbOfBounce`, and **no ammunition count
anywhere**. There is no number to vary, so "some have a spare, some do not" is
not a thing this engine models. Raising the rate is the honest version of the
same wish: they stop standing there winding up.

The edit
--------

The rate is an `EX_FloatConst` -- four bytes -- inside a call that reads::

    1b 30            PlayAnim
    21 43 2c         NameConst -> StandReloadRPG
    1e 00 00 00 3f   FloatConst 0.5      <- these four bytes
    16 04 0b         EndFunctionParms ; Return Nothing

Four bytes for four bytes, so the container's length never moves. Each anchor
occurs exactly once in each of `COMMON.LIN`, `COMMONOFF.LIN` and
`COMMON_SS.LIN`, at plain offsets `0x124ae9` (fire) and `0x124b11` (reload).
"""

from __future__ import annotations

import re
import struct

#: The animation rate the game ships for every one of these.
SHIPPED_RATE = 0.5

#: (anchorBytes, offsetOfTheFloatWithinTheAnchor) per animation. The two lead
#: bytes `1b 30` are the PlayAnim call itself; they are part of the anchor
#: because the NameConst index alone is only two bytes and a four-byte float of
#: 0.5 is common enough elsewhere in the file to want the company.
ANIMS = {
    "fire": (bytes.fromhex("1b3021 5229 1e0000003f 16040b".replace(" ", "")), 6,
             "StandFireRPG", 0x124AE9),
    "reload": (bytes.fromhex("1b3021 432c 1e0000003f 16040b".replace(" ", "")), 6,
               "StandReloadRPG", 0x124B11),
}


class RpgError(Exception):
    pass


def _head(anchor, at):
    return anchor[:at]


def find(plain: bytes, which: str) -> int:
    """The offset of that animation's rate float, or raise."""
    anchor, at, label, _known = ANIMS[which]
    head = anchor[:at]
    hits = [m.start() for m in re.finditer(re.escape(head), plain)]
    # The float itself changes, so match on the head and check the tail shape.
    good = [h for h in hits if plain[h + at + 4:h + at + 7] == anchor[at + 4:]]
    if not good:
        raise RpgError("the %s animation call is not in this file" % label)
    if len(good) > 1:
        raise RpgError("the %s animation call appears %d times; refusing to "
                       "guess" % (label, len(good)))
    return good[0] + at


def rate(plain: bytes, which: str) -> float:
    return struct.unpack_from("<f", plain, find(plain, which))[0]


def set_rate(plain: bytes, which: str, value: float):
    """Write one animation's play rate. Returns (plain, changed)."""
    if not 0.05 <= value <= 16.0:
        raise RpgError("an animation rate of %r is outside anything sane" % value)
    at = find(plain, which)
    packed = struct.pack("<f", float(value))
    if plain[at:at + 4] == packed:
        return plain, 0
    out = bytearray(plain)
    out[at:at + 4] = packed
    if len(out) != len(plain):
        raise RpgError("the rate edit changed the file length")
    return bytes(out), 1


def apply(plain: bytes, speed: int):
    """Scale both rocket animations by `speed`. Returns (plain, changed)."""
    n = 0
    for which in ("reload", "fire"):
        plain, k = set_rate(plain, which, SHIPPED_RATE * speed)
        n += k
    return plain, n


def card(prefix, group):
    from .model import INT, Setting

    return Setting(
        prefix + "rpg_speed", "How fast RPG enemies ready a rocket", INT, 1,
        group, minimum=1, maximum=8, unit="x",
        confidence="measured", touches="data",
        help="Rocket troops spend a long time winding up before they shoot, "
             "and the reason is that the animation is played at HALF speed -- "
             "`StandReloadRPG` and `StandFireRPG` are both issued at a rate of "
             "0.5. This multiplies that rate, so 2x is real time and 4x is "
             "twice as fast as the game was ever meant to play it.",
        caution="It cannot make them spawn with one already loaded, and it "
                "cannot give some of them a spare. The rocket only reaches the "
                "launcher partway through the animation, on an animation "
                "notify, and the launcher carries no ammunition count at all "
                "-- so there is no spare to hand out. Shortening the wind-up "
                "is the part that is actually reachable.")

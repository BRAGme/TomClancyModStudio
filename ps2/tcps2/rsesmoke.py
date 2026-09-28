"""Smoke that actually blinds, as quickly as it looks like it does.

The blind zone is real, and it is volumetric
--------------------------------------------

`R6Grenade.Explode` spawns an invisible `R6SmokeCloud` collision cylinder and
`R6SmokeCloud.Timer` grows its radius every 0.25 s. It is a genuine occluder,
not a proximity test: the AI's `LineOfSightTo` trace lacks the exempt bit
(0x00080000) so smoke DOES block it, while the player's own aim trace carries
that bit, which is why you can shoot out of your own cloud.

The fault is the RAMP, not the radius
-------------------------------------

    m_fSmokeSize            500 units (5 m)
    m_fSmokeExpensionTime   30.0 s      <- the game's own misspelling
    m_fSmokeDuration        20.0 s      -> LifeSpan

The cylinder grows to its full 500 over THIRTY seconds, but the cloud only
lives TWENTY. So the blind zone is destroyed at 333 units -- 67% of its
authored size -- and never once reaches what it was designed for. Worse, at
6 s, when the particle size curve has hit its knee and the cloud already
looks 82% grown, the blind cylinder is at 100 units: twenty per cent. At two
seconds it is a third of a metre against an obviously thick cloud.

That gap between what you can see and what an enemy cannot is the whole
complaint, and it is a timing bug rather than a mismatch of sizes -- in
absolute terms the finished blind zone is generous. So this shortens the
ramp instead of widening anything. Six seconds matches the particle curve's
own knee (RelativeTime 0.30 of a 20 s life).

Where it lives
--------------

NOT in the COMMON packages -- those carry only the weapon package's header.
The defaults are replayed at level load, so the record sits once in every
level container, and the edit is the same four bytes in each.

Not established
---------------

The cloud is spawned only when `Level.NetMode == 0`. In any networked
session -- which includes online co-op and terrorist hunt, since those run as
a listen server -- no cloud is created at all and smoke blocks nothing. This
setting cannot help there; it is an offline and split-screen fix by nature,
not by choice.
"""

from __future__ import annotations

H = bytes.fromhex


class SmokeError(Exception):
    pass


#: Every level container. The record is absent from COMMON and MENU.
SELECT = r"^/(?!COMMON|MENU)[A-Z_0-9]+(OFF|_SS)\.LIN$"

STOCK_SECONDS = 30.0

#: seconds -> (label, stock bytes, new bytes). The window carries the NEXT
#: property's tag and value as well, so a match cannot be a stray float.
RAMPS = {
    "15": ("ramp 15 s", H("4003240000f0414503240000fa43"), H("400324000070414503240000fa43")),
    "10": ("ramp 10 s", H("4003240000f0414503240000fa43"), H("400324000020414503240000fa43")),
    "6": ("ramp 6 s", H("4003240000f0414503240000fa43"), H("4003240000c0404503240000fa43")),
    "3": ("ramp 3 s", H("4003240000f0414503240000fa43"), H("400324000040404503240000fa43")),
}


def _entry(seconds):
    key = "%g" % float(seconds)
    if key not in RAMPS:
        raise SmokeError("no such smoke ramp: %r" % seconds)
    return RAMPS[key]


def reads(plain: bytes, seconds) -> bool:
    _n, _st, new = _entry(seconds)
    return plain.count(new) == 1


def apply(plain: bytes, seconds, enable: bool = True):
    """Returns (bytes, regions changed)."""
    name, stock, new = _entry(seconds)
    want, other = (new, stock) if enable else (stock, new)
    if plain.count(want) == 1:
        return plain, 0
    if plain.count(other) != 1:
        raise SmokeError("%s: %s" % (name, "not found" if not
                         plain.count(other) else "found %d times"
                         % plain.count(other)))
    at = plain.index(other)
    out = bytearray(plain)
    out[at:at + len(want)] = want
    return bytes(out), 1


def card(prefix, group):
    from .model import CHOICE, Choice, Setting

    return Setting(
        prefix + "smoke_ramp", "How fast smoke blinds the enemy", CHOICE,
        "off", group,
        choices=[Choice("off", "Thirty seconds (as shipped)",
                        "The blind zone never finishes growing -- the cloud "
                        "expires first.")]
        + [Choice("%g" % s, "%g seconds" % s,
                  "Matches the cloud's own visible growth." if s == 6.0 else "")
           for s in (15.0, 10.0, 6.0, 3.0)],
        confidence="experimental", touches="data",
        help="Smoke does hide you from the enemy, but the zone it hides you "
             "in grows far more slowly than the cloud looks like it does. It "
             "is built to reach five metres after thirty seconds -- except "
             "the cloud only lasts twenty, so it never gets there.\n\n"
             "Six seconds after the pin, when the smoke already looks thick, "
             "the part that actually blinds anyone is a metre across. "
             "Shortening the ramp makes the cover match what you can see.",
        caution="Not yet played.\n\n"
                "This does nothing online. The cloud is only created in "
                "single player and split screen -- an online co-op or "
                "terrorist hunt session runs as a host, and no cloud is made "
                "at all, so smoke blocks nothing there however this is set.")

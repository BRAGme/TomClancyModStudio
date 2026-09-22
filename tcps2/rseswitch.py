"""The choppy weapon switch, which is one float the developers set too high.

What is actually wrong
----------------------

The weapon-switch animation is not a different animation from the smooth ones,
and nothing about the switch path skips frames. It plays the SAME first-person
hands animation the game plays elsewhere -- at 2.9 times the rate, so it is
over in about a third of the rendered poses.

`R6AbstractFirstPersonHands` plays every first-person animation, and the rates
it uses are:

======================  ===================================  ======
what you see            call                                 rate
======================  ===================================  ======
aim down sights in      ``PlayAnim('ZoomIn')``               1.0
aim down sights out     ``PlayAnim('ZoomOut')``              1.0
firing                  ``PlayAnim('Fireburst_b', rate)``    1.0
reload                  ``PlayAnim('Reload', m_fReloadSpeed)``  per weapon
draw, NOT a switch      ``PlayAnim('Begin', 1.5)``           **1.5**
holster, NOT a switch   ``PlayAnim('End', 1.5)``             **1.5**
draw, weapon switch     ``PlayAnim('Begin', m_fAnimAcceleration)``   **2.9**
holster, weapon switch  ``PlayAnim('End', m_fAnimAcceleration)``     **2.9**
======================  ===================================  ======

The last two are the only readers of `m_fAnimAcceleration` in the whole game,
and the game's own ladder and interaction code plays the identical `'Begin'`
and `'End'` sequences at 1.5. That is the strongest evidence that 2.9 is the
outlier rather than the intent: the developers picked 1.5 for the same
animation everywhere they were not in a hurry.

Which is why the reload and the sight raise look smooth and the switch does
not. It is a rate, not a stutter.

The edit
--------

One float, in the `R6AbstractFirstPersonHands` class defaults. The record is
`7E 01 | 24 | <float>` -- compact name index, `0x24` meaning FloatProperty of
four bytes, then the value. Only the value moves, so the property list keeps
its length and nothing downstream shifts.

It is found by searching for that record rather than by a stored offset, and
the module refuses to act unless it appears exactly once. Measured on this
disc it sits at plain `0x1E8AD0` in `COMMON_SS.LIN` and `COMMONOFF.LIN` and
`0x1E8ADB` in `COMMON.LIN` -- recorded for reference, not used. There is also
exactly ONE bare 2.9 float in the entire five-megabyte image, so even the
weaker search would be unambiguous.

The trade, stated plainly
-------------------------

The switch advances on `AnimEnd`, with no timer anywhere in the path, so the
rate fully determines the duration. Lowering it makes the switch smoother AND
slower, in exact proportion: at 1.5 each half takes 1.93 times as long as
stock, at 1.0 it takes 2.9 times as long.

Nothing desynchronises. The equip sound is one-shot at state entry,
`m_bLockWeaponActions` is cleared in `RaiseWeapon.EndState` and
`m_bChangingWeapon` in `FirstPersonAnimOver` -- all of which follow the
animation rather than racing it.

What was ruled out on the way
-----------------------------

Every mechanical explanation, each by measurement:

* `m_bNoTick` during the switch -- `WeaponUpState` calls
  `SetFPWeapons(True)` BEFORE `GotoState('RaiseWeapon')`, so the hands that
  play the raise are ticking;
* the mesh being re-attached mid-animation -- `AttachToBone` happens once, in
  `LoadFirstPersonWeapon`, at loadout time;
* a spawn or streaming hitch -- a switch spawns, loads and destroys nothing;
* an interpolation assuming 60 fps -- there is no such loop, and no timers;
* `LODBias` / `bAnimByOwner` -- neither appears in the defaults at all.
"""

from __future__ import annotations

import struct

#: Rate as a percentage, so the card can be an integer dial. 290 is stock.
STOCK = 290
MINIMUM, MAXIMUM = 100, 290

#: The serialised default record: compact name index, FloatProperty tag, value.
PREFIX = bytes([0x7E, 0x01, 0x24])

#: Where it landed on the disc this was measured on. Not used to find it.
KNOWN = {"COMMON_SS.LIN": 0x1E8AD0,
         "COMMONOFF.LIN": 0x1E8AD0,
         "COMMON.LIN": 0x1E8ADB}


class SwitchError(Exception):
    pass


def _site(plain: bytes) -> int:
    """Offset of the float itself, whatever rate it currently holds."""
    found = []
    at = plain.find(PREFIX)
    while at >= 0:
        value = struct.unpack_from("<f", plain, at + 3)[0]
        if MINIMUM / 100.0 - 0.01 <= value <= MAXIMUM / 100.0 + 0.01:
            found.append(at + 3)
        at = plain.find(PREFIX, at + 1)
    if len(found) != 1:
        raise SwitchError(
            "expected exactly 1 weapon-switch animation rate, found %d -- "
            "this is not the build this was measured on" % len(found))
    return found[0]


def reads(plain: bytes) -> int:
    """The current rate, as a percentage."""
    return int(round(struct.unpack_from("<f", plain, _site(plain))[0] * 100))


def apply(plain: bytes, percent: int):
    """Rewrite the rate. Returns (bytes, changed). Four bytes, in place."""
    if not MINIMUM <= percent <= MAXIMUM:
        raise SwitchError("%d%% is outside the %d..%d this writes"
                          % (percent, MINIMUM, MAXIMUM))
    at = _site(plain)
    if reads(plain) == percent:
        return plain, 0
    out = bytearray(plain)
    struct.pack_into("<f", out, at, percent / 100.0)
    if len(out) != len(plain):
        raise SwitchError("the switch-rate edit changed the file length")
    return bytes(out), 1


HELP = ("The weapon-switch animation is the same one the game plays when you "
        "come off a ladder -- but the switch runs it at 2.9x where everything "
        "else runs it at 1.5x or slower, so you see about a third as many "
        "frames of it. This sets the rate. Lower is smoother and slower, in "
        "exact proportion.")

CAUTION = (
    "One float in a class default, rewritten in place, so no bytecode is "
    "touched and nothing shifts. It is located by its property record rather "
    "than a stored offset, and there is exactly one 2.9 in the whole "
    "five-megabyte package, so it cannot be confused with anything else.\n\n"
    "290% is stock. 150% is the rate the game itself uses for the IDENTICAL "
    "animation everywhere that is not a weapon switch -- ladders and "
    "interactions -- which is the best evidence that 2.9 was the odd one "
    "out.\n\n"
    "IT ALSO MAKES THE SWITCH SLOWER, and there is no way to separate the "
    "two. The state machine advances when the animation ends and there is no "
    "timer anywhere in the path, so duration scales as 1/rate: 150% takes "
    "1.93x as long as stock, 100% takes 2.9x as long. If switching weapons "
    "starts to feel sluggish in a firefight, raise it back.\n\n"
    "Nothing desynchronises at any setting -- the equip sound is one-shot at "
    "state entry, and both the weapon-lock and changing-weapon flags are "
    "cleared by events that follow the animation rather than race it.\n\n"
    "Not play-tested. It applies to every mode, because the rate is a single "
    "class default and there is no per-mode copy of it.")


def card(prefix, group):
    from .model import INT, Setting

    return Setting(
        prefix + "switch_rate", "Weapon switch animation speed", INT, STOCK,
        group, minimum=MINIMUM, maximum=MAXIMUM, unit="%",
        confidence="measured", touches="data",
        help=HELP, caution=CAUTION)

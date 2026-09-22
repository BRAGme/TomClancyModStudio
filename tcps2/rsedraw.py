"""The weapon draw animation that plays twice in split screen.

Switching weapons in split screen plays the draw animation, and then plays it
again -- with a second equip sound. It does not happen in single player.

Two paths raise the weapon
--------------------------

Entering weapon state `RaiseWeapon` replays the animation **by design**:
`R6Weapons::RaiseWeapon::BeginState` explicitly re-calls `BeginState` on the
first-person hands when they are already in that state, rather than ignoring
the re-entry. So anything that drives the weapon into `RaiseWeapon` twice
produces two animations.

Two things do:

* `R6PlayerController::WeaponUpState`, the end of the first-person discard
  animation, raises the new weapon -- and never clears `PendingWeapon`.
* `R6Rainbow::ChangingWeaponEnd`, an animation notify on the THIRD-person
  character mesh, raises it again. It is reached only through
  `ChangingWeaponEnd_Forward` / `_Backward`, which are notify names carried by
  `AnimNotify_Script` objects in the `R6Rainbow_UKX` package -- nothing in
  script calls it.

`ChangingWeaponEnd` opens with a guard that returns early precisely to stop the
notify duplicating the first-person path::

    if ( Controller != None && Controller IsA 'R6PlayerController'
         && bBehindView == False && IsLocallyControlled()
         && Level.Game != None
         && !Level.Game.m_bIsSplitScreen )      <- the term that matters
        return;

That last term switches the protection off in split screen, because split
screen normally has no visible first-person weapon for the other path to have
raised. Restoring the first-person weapon re-enables that path without
re-enabling the guard, so both fire.

Why it is only "occasional": it is a race. If the third-person notify lands
BEFORE the first-person discard animation ends, `ChangingWeaponEnd` raises once
and clears `PendingWeapon`, and `WeaponUpState` then hits its
`PendingWeapon == None` early return -- one animation. The double appears when
the notify lands after.

The edit
--------

Make the guard's last term true in both modes, so split screen takes the same
early return single player already takes. Everything `ChangingWeaponEnd` does
for the third-person model runs BEFORE the guard, which is why single player is
perfectly happy returning there today.

`!Level.Game.m_bIsSplitScreen` becomes `!Level.Game.m_bGameOver`. Both are
bools on **`GameInfo`, in the same dword at offset 0x3a0** -- split screen is
bit `0x200000`, game-over is bit `0x10000` -- so the VM resolves the same class
on the same object and reads a valid offset and bitmask. That is the whole
reason this operand and not an arbitrary one: pointing the read at a property
of some other class would have it read a wrong offset on the Game object.

`m_bGameOver` reads 0 in all six savestates checked, single and split, so
`!m_bGameOver` is true during play and the guard fires. Once the mission is
over it flips and the old behaviour returns -- at which point there is no
firefight left to spoil.

Two bytes, both a compact object index: `ed 01` (import -109,
`m_bIsSplitScreen`) becomes `e4 02` (import -164, `m_bGameOver`). Same length,
so the container never moves.

The alternative that was rejected
---------------------------------

There is a one-byte version: flip the `!=` at the later `Level.Game != None`
test so the split-screen raise short-circuits away. It was not taken. In the
notify-first ordering `ChangingWeaponEnd` still clears `PendingWeapon`,
`WeaponUpState` then bails, and **nothing raises the weapon at all** --
leaving `m_bLockWeaponActions` and `m_bHideReticule` set and the player unable
to use weapon actions. Trading an occasional double animation for an occasional
lockout is a bad bargain. This edit has no such ordering failure.
"""

from __future__ import annotations

import re

#: `BoolVariable(InstanceVariable(...))` then the two-byte operand.
_LEAD = bytes.fromhex("2d01")

#: The guard term as it ships, with enough of the context chain in front to be
#: unique: `! Level . Game . m_bIsSplitScreen` followed by the two
#: EndFunctionParms that close the AND.
#:
#: The `!` and its context chain alone are NOT unique -- three sites in the
#: file share them. What distinguishes this one is the term immediately in
#: front: the `Level.Game != None` test that guards the dereference, and the
#: `18 1b 00` skip that joins the two with `&&`.
ANCHOR = bytes.fromhex(
    "01" "a6" "2a" "1616"     # ... Level.Game != None, closing the previous term
    "18" "1b00"               # && (skip 27 if it short-circuits)
    "81"                      # ! (native 129)
    "1919"                    # Context, Context
    "01" "8f05" "000401"      # Level
    "a6" "060004"             # .Game
    "2d01" "ed01"             # .m_bIsSplitScreen
    "1616"
)

#: Where the two operand bytes sit inside `ANCHOR`: past the trailing
#: `16 16`, and past the `2d 01` that introduces them.
OPERAND_AT = len(ANCHOR) - 4

SPLITSCREEN = bytes.fromhex("ed01")     # import -109, m_bIsSplitScreen
GAMEOVER = bytes.fromhex("e402")        # import -164, m_bGameOver

#: measured, so a test can assert rather than search blindly
KNOWN_OFFSET = 0x0011FDFC


class DrawError(Exception):
    pass


def find(plain: bytes) -> int:
    """The offset of the guard's operand bytes, or raise."""
    head = ANCHOR[:OPERAND_AT]
    tail = ANCHOR[OPERAND_AT + 2:]
    good = []
    for m in re.finditer(re.escape(head), plain):
        at = m.start() + OPERAND_AT
        if plain[at:at + 2] in (SPLITSCREEN, GAMEOVER) and \
                plain[at + 2:at + 2 + len(tail)] == tail:
            good.append(at)
    if not good:
        raise DrawError("the draw-animation guard is not in this file")
    if len(good) > 1:
        raise DrawError("the draw-animation guard appears %d times; refusing "
                        "to guess which one to change" % len(good))
    return good[0]


def restore(plain: bytes, enable: bool = True):
    """Point the guard at `m_bGameOver`, or put `m_bIsSplitScreen` back."""
    at = find(plain)
    want = GAMEOVER if enable else SPLITSCREEN
    if plain[at:at + 2] == want:
        return plain, 0
    out = bytearray(plain)
    out[at:at + 2] = want
    if len(out) != len(plain):
        raise DrawError("the draw-guard edit changed the file length")
    return bytes(out), 1


def reads(plain: bytes) -> bool:
    return plain[find(plain):find(plain) + 2] == GAMEOVER


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_draw_once", "Play the weapon draw animation once",
        BOOL, False, group, confidence="verified", touches="data",
        help="In split screen, switching weapons plays the draw animation "
             "twice, with the equip sound doubled. Two separate things raise "
             "the weapon -- the first-person switch, and an animation notify "
             "on the third-person model -- and the notify has a guard that "
             "stops it duplicating the other one, which the game switches OFF "
             "in split screen because split screen normally has no visible "
             "first-person weapon. Restoring that weapon brought the other "
             "path back without restoring its guard. This makes the guard "
             "apply in split screen too, exactly as it does in single player.",
        caution="Not play-tested. It only ever ADDS an early return that "
                "single player already takes, and everything the notify does "
                "for the third-person model happens before that point, so it "
                "should not change how anyone else sees you. A cheap check "
                "costing nothing: the doubled equip SOUND should be audible "
                "in split screen even with the view-model option off, since "
                "only the drawing is gated.")

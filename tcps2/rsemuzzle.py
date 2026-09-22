"""Muzzle flashes in split screen, which are one byte of UnrealScript away.

What is actually wrong
----------------------

The flash is not missing. It is attached to the wrong weapon.

`R6Weapons.LoadFirstPersonWeapon` decides where the flash emitter lives, and
the decision is guarded:

```
0x0104: JumpIfNot(-> 0x013d,  Level.Game == None || !Level.Game.m_bIsSplitScreen )
0x0137:     AttachEmittersToFPWeapon()
0x013d: m_FPWeapon.PlayAnim(m_FPWeapon.m_WeaponNeutralAnim)
```

In split screen `Level.Game` exists and `m_bIsSplitScreen` is true, so both
arms of the `||` are false and the call is skipped.
`AttachEmittersToFPWeapon` is the only code anywhere that moves the flash onto
the first-person weapon -- it clears `m_bDrawFromBase`, calls `SetBase(None)`
and `AttachToBone(m_pMuzzleFlashEmitter, 'TagMuzzle')` on the FP weapon. Its
mirror, `AttachEmittersTo3rdWeapon`, is called by `CreateWeaponEmitters` at
spawn and by `RemoveFirstPersonWeapon`, so the two are a designed toggle and
split screen is simply stuck on the third-person side of it. A savestate
measured the flash actor sitting at the third-person muzzle (z = -1713.4)
rather than the first-person one (z = -1612.4), which is the same story from
the other end.

The edit
--------

One byte: the `==` in the first arm becomes `!=`.

```
Level.Game != None || !Level.Game.m_bIsSplitScreen
```

`0x72` is `native114`, object `==`; `0x77` is `native119`, object `!=`. Both
are single-byte native opcodes, so nothing about the statement's width moves,
`ScriptSize` cannot change, and no jump operand is touched. That matters: this
engine hangs on any edit that RE-ASSEMBLES bytecode, which is why every edit
in this project is an operand swap inside an existing token.

Why it is safe in single player
-------------------------------

Because it changes nothing there. In single player the call already runs, via
the second arm (`!m_bIsSplitScreen` is true). After the edit it runs via the
first arm instead (`Level.Game != None` is true). Same call, same place, same
outcome -- only the reason differs. The same argument covers the online build.

That is worth stating plainly, because it is what makes this edit cheap to
ship: it can go into all three COMMON files without anyone having to be right
about which one split screen loads. The disc holds `COMMON.LIN` (online),
`COMMONOFF.LIN` (offline) and `COMMON_SS.LIN` (split screen), the latter two
byte-identical, and the statement appears exactly once in each. Patching all
three removes the only guess in the change.

Found by signature, not by offset
---------------------------------

The 37-byte statement is searched for rather than seeked to, and the module
refuses to act unless it appears exactly once. A stored offset is only true
for the build it was measured on; a signature that must be unique is true for
any build that still contains the statement. Measured on this disc the
offsets are `0x1DE796` in `COMMON_SS.LIN` and `COMMONOFF.LIN` and `0x1DE7A1`
in `COMMON.LIN` -- recorded for reference, not used.

The one thing the disassembly could not settle
----------------------------------------------

Whether player 1's flash, now a world actor parented to player 1's
first-person weapon, stays out of player 2's viewport. The design said it
should -- the emitters carry `m_iDrawWeaponPreDisplay`, which is what puts
them in the per-viewport weapon pre-display pass, the same pass that draws the
FP weapon itself -- but that flag is read by native code that is not in the
overlay and not in any script, so it was inference either way.

Play-tested on Alpine Village split screen: both players get a flash on their
own weapon and it does not cross the split. Settled by running it, which is
the only way it was ever going to be settled.

A companion edit, deliberately not shipped
------------------------------------------

`AttachEmittersToFPWeapon` also contains a `DynamicLoadObject` for the
empty-shell static mesh, behind a `StaticMesh == None` guard. Split screen has
never executed it, so restoring the call introduces one object load per weapon
per player that split screen did not do before. It is the same load single
player performs on every weapon, so it is not exotic -- but it is new
behaviour in the mode with less memory, and this project has been bitten by
load-time additions more than once.

Suppressing it is also a one-byte operand swap: at the guard's `EX_NoObject`
(`0x2a`) write `EX_Self` (`0x17`), making `StaticMesh == Self`, which is never
true. `SHELL_GUARD` below records the signature. It is NOT wired to a setting,
because it must go to the split-screen file only -- applying it to
`COMMONOFF.LIN` would take shell casings away from single player -- and that
reintroduces the one guess this edit was designed to avoid. If the flash fix
turns out to cost anything at weapon switch, that is the next thing to try,
and it should be tested on its own.
"""

from __future__ import annotations

#: The whole guarded statement, `JumpIfNot` through the two closing `EX_
#: EndFunctionParms`. It is the unit that must be unique, so a stray `0x72`
#: elsewhere in the package can never be mistaken for this one.
STATEMENT = bytes([
    0x07, 0x3D, 0x01,              # JumpIfNot -> 0x013d
    0x84,                          # EX_NativeParm / bool eval
    0x72,                          # native114  ==(Object, Object)   <-- edited
    0x19, 0x01, 0x9A, 0x05, 0x00, 0x04, 0x01, 0xAB,   # Level.Game
    0x2A,                          # EX_NoObject (None)
    0x16,                          # EX_EndFunctionParms
    0x18, 0x1B, 0x00,              # EX_Skip (the || short-circuit)
    0x81,                          # native129  !(bool)
    0x19, 0x19, 0x01, 0x9A, 0x05, 0x00, 0x04, 0x01, 0xAB,
    0x06, 0x00, 0x04,              # Level.Game.m_bIsSplitScreen
    0x2D, 0x01, 0xCF, 0x01,        # bool -> byte
    0x16, 0x16,                    # EX_EndFunctionParms x2
])

#: Byte to change, as an index into STATEMENT.
OPERAND = 4

EQ = 0x72       # native114, ==
NE = 0x77       # native119, !=

#: Where it landed on the disc this was measured on. Not used to find it.
KNOWN = {"COMMON_SS.LIN": 0x1DE796,
         "COMMONOFF.LIN": 0x1DE796,
         "COMMON.LIN": 0x1DE7A1}

#: The empty-shell `DynamicLoadObject` guard inside AttachEmittersToFPWeapon.
#: Recorded, not wired -- see the module docstring.
SHELL_GUARD = bytes([
    0x07, 0xC7, 0x01,              # JumpIfNot -> 0x01c7 (Return)
    0x72,                          # native114  ==
    0x19, 0x2E, 0xF8, 0x01, 0x10, 0x25, 0x19, 0x01, 0x02, 0x05, 0x00, 0x00,
    0x01, 0xCE, 0x01, 0x05, 0x00, 0x04, 0x01, 0xFF, 0x03,
    0x2A,                          # EX_NoObject  -> EX_Self (0x17) suppresses
    0x16,
])
SHELL_OPERAND = 25
SHELL_SELF = 0x17


class MuzzleError(Exception):
    pass


def _site(plain: bytes) -> int:
    """Offset of the one guarded statement, whichever operand it holds."""
    found = []
    for op in (EQ, NE):
        probe = bytearray(STATEMENT)
        probe[OPERAND] = op
        probe = bytes(probe)
        at = plain.find(probe)
        while at >= 0:
            found.append(at)
            at = plain.find(probe, at + 1)
    if len(found) != 1:
        raise MuzzleError(
            "expected exactly 1 muzzle-flash gate, found %d -- this is not "
            "the build this was measured on" % len(found))
    return found[0]


def reads(plain: bytes) -> bool:
    """True if the flash is already attached to the first-person weapon."""
    return plain[_site(plain) + OPERAND] == NE


def _shell_site(plain: bytes) -> int:
    """Offset of the empty-shell DynamicLoadObject guard's operand."""
    found = []
    for op in (0x2A, SHELL_SELF):
        probe = bytearray(SHELL_GUARD)
        probe[SHELL_OPERAND] = op
        probe = bytes(probe)
        at = plain.find(probe)
        while at >= 0:
            found.append(at)
            at = plain.find(probe, at + 1)
    if len(found) != 1:
        raise MuzzleError(
            "expected exactly 1 empty-shell guard, found %d -- this is not "
            "the build this was measured on" % len(found))
    return found[0] + SHELL_OPERAND


def shelled(plain: bytes) -> bool:
    """True if the empty-shell mesh load is suppressed."""
    return plain[_shell_site(plain)] == SHELL_SELF


def apply(plain: bytes, enable: bool = True, shell: bool = False):
    """Flip the gate, and optionally suppress the empty-shell load.

    `shell` exists because restoring the attach call also restores a
    `DynamicLoadObject` inside it, and split screen has never run that load.
    It belongs ONLY in `COMMON_SS.LIN` -- suppressing it in the offline
    package would take shell casings away from single player, where the load
    has always worked.

    Returns (bytes, changed). Bytes move in place; the length never does.
    """
    out = bytearray(plain)
    changed = 0

    at = _site(plain)
    want = NE if enable else EQ
    if plain[at + OPERAND] != want:
        out[at + OPERAND] = want
        changed += 1

    # Only looked for when it is actually wanted. A site this edit is not
    # going to touch has no business being a precondition for the one it is,
    # and the flash statement and the shell guard are independent.
    if shell:
        sat = _shell_site(plain)
        swant = SHELL_SELF if enable else 0x2A
        if plain[sat] != swant:
            out[sat] = swant
            changed += 1

    if len(out) != len(plain):
        raise MuzzleError("the muzzle-flash edit changed the file length")
    return bytes(out), changed


HELP = ("The flash is not missing in split screen -- it is attached to the "
        "third-person weapon instead of the one you are looking down. The "
        "call that moves it sits behind a split-screen test, and this is that "
        "test, inverted.")

CAUTION = (
    "One byte of UnrealScript: the object comparison `Level.Game == None` "
    "becomes `!= None`, so the first arm of the guard is true whenever a game "
    "exists and the attach call runs in every mode.\n\n"
    "Single player cannot change, and that is provable rather than hoped for: "
    "the call already runs there through the guard's second arm, so after the "
    "edit it runs through the first instead. Same call, same place. That is "
    "why this goes into all three COMMON files -- nobody has to be right "
    "about which one split screen loads.\n\n"
    "Both opcodes are one byte, so the statement's width, the function's "
    "ScriptSize and every jump target are untouched. No bytecode is "
    "re-assembled, which is the thing that hangs this engine.\n\n"
    "PLAY-TESTED on Alpine Village split screen: both players get a flash on "
    "their own weapon, and it does not bleed across the split. That last "
    "part was the one thing the disassembly could not settle -- the emitters carry the flag that puts them in the per-viewport weapon pass, but that flag "
    "is read by native code outside the overlay, so until it ran it was "
    "inference. It is not any more.")


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_muzzle", "Muzzle flashes on your own weapon",
        BOOL, False, group, confidence="verified", touches="data",
        help=HELP, caution=CAUTION)

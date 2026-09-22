"""Why both players' weapons sway together in split screen.

The defect
----------

With "Show your weapon in split screen" on, moving one player's stick moves
the OTHER player's weapon too, and it keeps doing it when the first player is
dead.

Where it is NOT
---------------

Worth recording, because two plausible answers were measured and refuted
before the real one turned up.

The option itself only clears a gate: it nops `sw $zero, 0x80cc($gp)` at
`0x00302da8`, so the game stops switching the viewmodel off. The gate reads 1
in a split-screen savestate -- a flag, not a pointer -- and cannot carry
motion.

The routine that walks to the viewmodel touches 22 gp-relative globals.
Diffing two savestates that differ only by player 1's stick shows **none of
them move**, and no float that does move appears at two addresses, so it is
not a mirrored pair either. The carrier is one level further down: the gate
block calls the viewmodel's vtable slot `+0x170`, and the sway lives there.

The carrier, proved bit-exactly
-------------------------------

`0x003f53b0` (vtable slot `0x170`) and its identical twin `0x003f4a80`
(slot `0x174`) read the sticks from four game-wide globals::

    003f5518  lwc1  $f3, 0x8d14($gp)     ; left stick X
    003f5524  lwc1  $f2, 0x8d18($gp)     ; left stick Y
    003f5528  lwc1  $f1, 0x8d24($gp)     ; right stick X
    003f552c  lwc1  $f0, 0x8d28($gp)     ; right stick Y
    003f5540..                            ; this->0x524.. += 0.33 * (target - now)

`this` is the per-player viewmodel object; the inputs are not.

Across the two savestates, with only player 1's stick moved:

===============================  =========  =========
word                             centred    deflected
===============================  =========  =========
`gp+0x8d14` (the global)         00000000   BF800000
player 1 pawn `+0x4e8`           00000000   BF800000
player 2 pawn `+0x4e8`           00000000   00000000
player 1 viewmodel `+0x524`      012DE450   BF7FFFFD
player 2 viewmodel `+0x524`      012DE450   **BF7FFFFD**
===============================  =========  =========

Player 2's sway reaches the **bit-identical** value while player 2's own
input stays at zero. Simulating the 0.33 lerp with EE round-toward-zero
against a target of -1.0 converges on exactly `0xBF7FFFFD`, so that is a
match rather than a coincidence.

The per-player value already exists
-----------------------------------

The input handler at `0x00141cc4` writes both:

* `0x00142b04`  `swc1 $f22, 0x8d14($gp)` -- the global. It sits in the delay
  slot of `bne $s2, $zero`, so it runs for **every** pad, and the last one
  processed wins.
* `0x00142b6c`  `swc1 $f22, 0x4e8($v0)` where `$v0` is that player's pawn --
  the correct per-player mirror, same register, same value.

So the fix is not to invent anything: point the viewmodel's reads at the
mirror the game already maintains. That also explains the dead-player case --
when the pawn is null the mirror store is skipped by the `beq` at
`0x00142b64`, but the unconditional global store still runs.

`$s0` is the owning pawn at both sites, null-checked just above at
`0x003f541c` / `0x003f4aec` and already dereferenced at `+0x4d8`, with no
write to it and no call in between.

The right stick has no mirror
-----------------------------

`gp+0x8d24` / `gp+0x8d28` are written with no per-player equivalent anywhere
in the image, so there is nothing to point at. `CENTRE_RIGHT` zeroes that
channel instead: it removes the cross-talk by removing the effect for both
players. Giving player 2 a correct right-stick sway needs a cave in the input
handler plus two free words on the pawn, which is a bigger job than this.
"""

from __future__ import annotations

#: `lwc1 $fN, 0x4e8($s0)` / `0x4ec($s0)` -- the pawn's own left-stick mirror
_F3_LEFT_X = 0xC60304E8
_F2_LEFT_Y = 0xC60204EC

#: (va, stockWord, newWord). Both copies of the routine are patched: slot
#: 0x170 is what the split-screen gate path calls, slot 0x174 is the same
#: code reached from elsewhere, and leaving one behind would make the
#: behaviour depend on which weapon class is in hand.
LEFT_STICK = (
    (0x003F4BE8, 0xC7838D14, _F3_LEFT_X),   # delay slot of beq zero,zero
    (0x003F4BF0, 0xC7838D14, _F3_LEFT_X),
    (0x003F4BF4, 0xC7828D18, _F2_LEFT_Y),
    (0x003F5518, 0xC7838D14, _F3_LEFT_X),   # delay slot of beq zero,zero
    (0x003F5520, 0xC7838D14, _F3_LEFT_X),
    (0x003F5524, 0xC7828D18, _F2_LEFT_Y),
)

#: `mtc1 $zero, $fN` -- kills the right-stick channel for everyone
_MTC1_F1 = 0x44800800
_MTC1_F0 = 0x44800000

CENTRE_RIGHT = (
    (0x003F4BF8, 0xC7818D24, _MTC1_F1),
    (0x003F4BFC, 0xC7808D28, _MTC1_F0),
    (0x003F5528, 0xC7818D24, _MTC1_F1),
    (0x003F552C, 0xC7808D28, _MTC1_F0),
)


def words(right_too: bool = False):
    """[(va, word, stockWord, note)] for the sway fix."""
    out = [(va, new, stock, "split screen: weapon sway follows its own player")
           for va, stock, new in LEFT_STICK]
    if right_too:
        out += [(va, new, stock,
                 "split screen: centre the right-stick sway channel")
                for va, stock, new in CENTRE_RIGHT]
    return out


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_sway", "Each player's weapon sways to their own stick",
        BOOL, False, group, confidence="untested", touches="words",
        help="With the weapon shown in split screen, both players' weapons "
             "lean to whichever stick moved last -- and keep doing it when "
             "the player driving them is dead. The routine that sways the "
             "weapon reads the stick from four game-wide globals instead of "
             "from the player holding it. This points the two left-stick "
             "reads at the per-player copy the game already keeps on the "
             "pawn.",
        caution="Six words on the disc, no cave, every stock word checked "
                "against the image first. The carrier was proved bit-exactly: "
                "with only player 1's stick moved, player 2's sway state "
                "reaches 0xBF7FFFFD, the identical value, while player 2's "
                "own input stays at zero. In single player this is a no-op by "
                "construction, because the global and the one player's mirror "
                "hold the same number.\n\n"
                "The RIGHT stick is not fixed. It has no per-player copy "
                "anywhere in the image, so there is nothing to point it at. "
                "That channel feeds a smaller translation offset, so expect "
                "some cross-talk to remain.\n\n"
                "Not play-tested. If the weapons still track each other "
                "rigidly rather than just leaning together, the base "
                "orientation has a second carrier and this is only half the "
                "defect.",
        requires={prefix + "viewmodel": [True]})


def turn_card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_sway_turn", "Turning does not sway the weapon",
        BOOL, False, group, confidence="untested", touches="words",
        help="The weapon is meant to lean when you MOVE. It also leans when you TURN, because the same routine mixes in the right stick -- and that channel has no per-player copy, so in split screen one player turning leans the other player's weapon as well. This centres the turn channel: the weapon stops responding to the look stick, for both players and in single player too.",
        caution='Four words on the disc, no cave, every stock word checked against the image first. This is the half of the sway fix that could not be done by pointing at a per-player value, because the right stick has no per-player copy anywhere in the image -- the game only ever stores it to one global. So the cross-talk is removed by removing the effect rather than by separating it. That means it changes single player too: turning will no longer lean your weapon there either. Whether that reads as a fix or a loss is a matter of taste, which is why it is its own switch rather than part of the sway option. Giving player 2 a correct turn sway instead would need a cave in the input handler plus two free words on the pawn, which is a larger job than this.',
        requires={prefix + "split_sway": [True]})

"""Being flashbanged costs ~45 ms a frame. One word is the whole cause.

THE DEFECT
----------

While a pawn is flashbanged the game re-runs its entire deafening routine
**every frame, for the full six seconds**, instead of once when the grenade
goes off. The player sees the frame rate collapse to roughly a quarter and
recover the instant the ringing stops -- which is the tell, because the white
flash has long since faded by then.

Two engine functions share a latch at `gp[-0x6478]`, and one of them clears it
unconditionally.

`UGameEngine::Tick` (`0x002E81A0`), while `m_eEffectiveGrenade == 3`
(flashbang) and `m_fRemainingGrenadeTime > 0`::

    002E9144  lbu   $v1, 0x37a($a1)      ; m_eEffectiveGrenade
    002E914C  bne   $v1, 3, skip
    002E9154  lwc1  $f1, 0x43c($a1)      ; m_fRemainingGrenadeTime
    002E9168  bc1t  skip                 ; <= 0 ?
    002E9184  sb    $v0, 0x3be($a1)      ; request the visual effect
    002E9190  sw    $zero, -0x6478($gp)  ; clear "already deafening" -- ALWAYS

`0x002E9190` sits past all three branch targets, so it runs every frame no
matter what the tests above decided.

`UGameEngine::Draw` (`0x002EF0C0`) reads that same latch at `0x002EF8E4`
(`lw $v0, -0x6478($gp)`, the matching half of the pair), finds it zero again,
and re-runs the deafen block at `0x002EF900..0x002EFA40`. That block is
**22 audio calls**:

* 1 x re-trigger of `m_sndHearToneSound` -- the ringing, started afresh
* 11 x `SetChannelVolume` (`Audio` vtable `+0xEC`), channels 1..11
* 1 x `Audio` vtable `+0x104`
* 9 x `SetChannelVolume(15, ch, fade)` where the fade time is
  `m_fRemainingGrenadeTime` itself -- it shrinks every frame, so the fade
  target never converges

WHY IT IS SO EXPENSIVE UNDER EMULATION
--------------------------------------

The DARE audio update reaches the IOP through a **blocking** `sceSifCallRpc`
(`0x00117FE8`, wrapper `0x004C8B70`, `mode=0`, `endfunc=NULL`, with a spin-wait
at `0x004C8BB4`), plus one further blocking round trip per 4096 bytes queued
(`0x004D5628..0x004D5648`). A blocking SIF RPC forces PCSX2 to synchronise the
EE and IOP clocks, and re-arming twenty channel fades and a sound event every
frame keeps that ring permanently full.

That last step -- attributing the *magnitude* to SIF synchronisation -- is
inference from code structure. The per-frame flood itself is read straight off
the disassembly.

WHAT THE EDIT DOES
------------------

Removes the redundant clear. With it gone the deafen block runs **once**, when
the flashbang lands, instead of about sixty times a second for six seconds.

The latch is touched in only six places in the whole image, and it is already
cleared correctly on the effect's own expiry path (`0x002F06B8`) and on level
reset (`0x0048E010`). Nothing else depends on the clear in `Tick`.

Nothing audible changes: the ringing still plays, the ducking still applies
with its intended fade, and the stop sound and volume restore at expiry are
untouched. In fact the teardown *needs* this -- all three `EndOfGrenadeEffect`
script bodies are logging and bookkeeping only, so the native expiry path at
`0x002F0674`/`0x002F06B8` is the only teardown there is, and it is gated on the
latch being non-zero. Keeping the latch set through the effect is what that
path expects.

DELIVERED ON THE DISC, NOT IN THE CHEAT FILE
--------------------------------------------

This word is **not** `pnach_only`, and that is deliberate.

`0x002E9190` lives in page `0x002E9000`, which holds `UGameEngine::Tick` --
the hottest function in the game. A `.pnach` row is re-applied every vsync and
dirties the 4 KB page it lands in, forcing PCSX2 to discard and rebuild every
recompiled block in that page. That is the same mechanism that stalled level
loading from page `0x00273000` (2026-09-27), and here it would land on the
per-frame engine tick, which is worse. Writing the word into `SP.SOZ` once
avoids it entirely.

NOT ESTABLISHED
---------------

* Never played. The stock word and its pair were read out of the pristine
  overlay and verified by hand; the frame rate result is not observed.
* Whether split-screen co-op loads `SP.SOZ` or `MP.SOZ` was not established.
  Every address in this project is an `SP.SOZ` virtual address, so if the
  split-screen path runs the other overlay this edit is inert there.
* A fallback exists and is not taken: shortening the two `6.f` duration
  literals (`R6Pawn.AffectedByGrenade` and
  `R6Pawn.R6ClientAffectedByFlashbang`, the float dwords at plain `0x0F4226`
  and `0x0F4383` in each COMMON package). That shortens the flood rather than
  removing it, and costs the player a shorter blind.
"""

from __future__ import annotations


class FlashCostError(Exception):
    pass


#: The redundant latch clear in `UGameEngine::Tick`.
#: `sw $zero, -0x6478($gp)` -> `nop`.
LATCH_CLEAR_AT = 0x002E9190
LATCH_CLEAR_STOCK = 0xAF809B88
LATCH_CLEAR_NEW = 0x00000000

#: The matching read in `UGameEngine::Draw`. Never written -- kept so the
#: module can assert the pair it relies on, and so a test can prove the two
#: really do name the same `$gp` slot (both encode offset `0x9B88`).
LATCH_READ_AT = 0x002EF8E4
LATCH_READ_WORD = 0x8F829B88


def words(enable: bool = True):
    """[(va, new, stock)] for the edit.

    Tuple order is (address, NEW, STOCK) -- the order `build_pnach` unpacks.
    Reversing it writes the stock value back and the option silently does
    nothing, which has happened before (2026-09-27).
    """
    return ([(LATCH_CLEAR_AT, LATCH_CLEAR_NEW, LATCH_CLEAR_STOCK)]
            if enable else [])


def stock_words():
    """{va: stock} for the word this module touches."""
    return {LATCH_CLEAR_AT: LATCH_CLEAR_STOCK}


def reads(word_at) -> bool:
    """True if `word_at(va)` shows the edit in place."""
    return word_at(LATCH_CLEAR_AT) == LATCH_CLEAR_NEW


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "flashbang_cost", "Flashbangs do not wreck the frame rate",
        BOOL, False, group, confidence="experimental", touches="code",
        help="While you are flashbanged the game drops to roughly a quarter "
             "of its frame rate, and recovers the moment the ringing stops.\\n\\n"
             "It is re-running the whole deafening routine every frame for "
             "the six seconds the effect lasts -- restarting the ringing, and "
             "re-arming twenty channel fades, sixty times a second -- because "
             "one line clears the flag that was supposed to say it had "
             "already done it. That line does nothing else, and the flag is "
             "cleared properly elsewhere when the effect ends.\\n\\n"
             "This removes that one line. Nothing sounds different: the same "
             "ringing, the same muffling, the same recovery.",
        caution="Not yet played.\\n\\n"
                "This is written to the disc rather than the cheat file on "
                "purpose. The instruction sits in the same small region of "
                "memory as the engine's per-frame update, and a cheat line "
                "re-applied every frame would force the emulator to keep "
                "rebuilding that region -- which is what caused the mission "
                "loading stalls.")

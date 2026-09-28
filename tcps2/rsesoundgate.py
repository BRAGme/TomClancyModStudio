"""WITHDRAWN 2026-09-28. The premise below is false and the edit is the
prime suspect for enemies firing with no gunshot at all.

WHAT WAS WRONG
--------------

This module was built on the claim that several weapons have no
third-person fire sample, so an AI firing one clicks and never bangs.
**Not one of the thirty weapon classes has a None third-person fire
sound.** `SubMP5A4.m_FullAutoStereoSnd` is `Sub_MP5A4.Play_MP5A4_FullAuto`,
a real 22050 Hz sample measuring -9.0 dB against its `_1ST` twin's -9.5.
The edit never turned silence into sound. The MP5A4 case that appeared to
improve was not this fix.

WHAT IT ACTUALLY DID, AND WHY THAT IS WORSE
-------------------------------------------

It swaps a **mono 22050 Hz** asset for a **stereo 28000 Hz** one. Measured
across all 93 weapon banks: 63 third-person banks are `nchan=1`, and all
29 `_1ST` banks are `nchan=2`. Stock, at most ONE stereo fire source is
ever alive -- the weapon in your hands. With this on, every firing enemy
is one, so a six-man firefight asks the SPU for six stereo voices where
the game was built to expect one.

That fits the reports: enemies with a UMP45, a MAC-11 and an M16 firing
with a trigger click and no shot. Attenuation cannot explain those --
`Play_SMG_Trigger` carries a 15 m max distance while every third-person
fire event is at full volume out to 10 m, so anywhere you can hear the
click the bang should be at roughly 0 dB. A sound that does not start is
the only mechanism left, and voice pressure is the only thing this edit
moves.

The SPU voice-allocation failure itself is INFERRED: the mono-to-stereo
doubling is measured, the starvation is not, and testing it needs a
running emulator. That is the gap between prime suspect and convicted.

Also refuted along the way: the earlier idea that first-person samples are
quieter for silenced weapons. The 1st-minus-3rd delta is -1.45 dB for
silenced against -1.19 dB for unsilenced, permutation p = 0.712. And no
`_1ST` event on the disc has a smaller max distance than its third-person
twin; the smallest gap is +30 m.

THE ORIGINAL NOTES FOLLOW, KEPT AS WRITTEN.

AI teammates fire with the first-person gunshot instead of the third-person
one, which for several weapons is the only sample that exists.

What the game does now
----------------------

`R6PawnReplicationInfo.AssignSound` is the one place a pawn's sound slots are
filled. It runs once per weapon per pawn, on the client, and it does three
things in order: copy fifteen of the weapon class's sounds into its own
`m_*Snd[u8CurrentWeapon]` arrays; then, **only for the player**, overwrite
three of those slots with the PS2-only first-person variants; then register
every bank the weapon needs.

The PS2 port added the three properties that make the split possible --
`m_SingleFireStereoSnd1st`, `m_FullAutoStereoSnd1st` and
`m_FullAutoEndStereoSnd1st`. They exist on neither the Xbox build (whose
`AssignSound` has no gate, no `Log` and no override block at all) nor on the
PC 1.56 source. What the PS2 build does with them:

    m_TriggerSnd[i] = WeaponClass.default.m_TriggerSnd;         // and 14 more
    ...
    if ( m_ControllerOwner.Pawn.m_bIsPlayer )                   // mem 0x01af
    {
        if (True) Log("sxd:" $ string(Self) $ ": Player's "     // mem 0x01ca
                      $ string(WeaponClass) $ " Stereo Sound Loaded");
        if (WeaponClass.default.m_SingleFireStereoSnd1st  != None)   // 0x020b
            m_SingleFireStereoSnd[i]  = WeaponClass.default.m_SingleFireStereoSnd1st;
        if (WeaponClass.default.m_FullAutoStereoSnd1st    != None)   // 0x023b
            m_FullAutoStereoSnd[i]    = WeaponClass.default.m_FullAutoStereoSnd1st;
        if (WeaponClass.default.m_FullAutoEndStereoSnd1st != None)   // 0x026b
            m_FullAutoEndStereoSnd[i] = WeaponClass.default.m_FullAutoEndStereoSnd1st;
    }
    AddAndFindBankInSound(WeaponClass.default.m_EquipSnd, LBS_Gun);  // 0x029b
    ... 23 more, INCLUDING all three ...Snd1st ...

So the player and an AI holding the same gun are handed different audio files,
decided once, here. For weapons whose third-person sample was never authored
the AI's slot is left holding `None`, the native play path returns on a NULL
`USound*`, and because `m_TriggerSnd` is played first and unconditionally what
comes out is a dry mechanical click and no gunshot. Reported in play on the
TMP, the MP5SD5 and the MP5A4.

What this does
--------------

It makes the three overrides apply to every pawn, by retargeting the gate's
own jump rather than removing it:

    if ( m_ControllerOwner.Pawn.m_bIsPlayer )   // false -> 0x020b, was 0x029b

A player's pawn passes the test and falls through exactly as before -- `Log`
included, so the debug spam stays player-only and reads the same as a stock
disc. An AI's pawn fails it and now lands on the first override instead of
past all three. Both then run all three, and both then run the unguarded bank
block that always followed.

**It asks for nothing new, and that is measured, not argued.** All three
`...Snd1st` properties are registered by this same function for every pawn --
`AddAndFindBankInSound` calls at mem 0x030d, 0x0359 and 0x037f, outside the
gate. So on the call that now assigns a first-person sample to an AI, that
sample's bank has already been queued by the AI's own call, three statements
later. No new sound bank, no new name, no new import, no new export, and no
reference of any kind is added, removed or reordered.

Why it is length-neutral
------------------------

The edit is the two-byte WORD operand of one `EX_JumpIfNot`, and nothing else.
(In practice only one of the two bytes moves -- 0x029b and 0x020b share their
high half -- so the file differs from stock in a single byte. The module writes
the whole word anyway, because the word is the thing that has a meaning.)

* **Disk length**: two bytes overwritten in place. The block stays 815 bytes.
* **Memory length**: a jump word is two bytes in the file and two bytes in RAM
  -- it is not an `FCompactIndex` reference, so the 1.369x disk-to-memory
  expansion does not touch it. The block stays 1125 bytes loaded.
* **`ScriptSize`**: unchanged, because the memory length is. It is not
  rewritten at all.
* **Jump operands are absolute MEMORY offsets** (`tcps2/uscode.py`), so the
  new value is written as-is: 0x020b, not a disk offset.

And 0x020b is not a number this module invented. The `if (True)` wrapper in
front of the `Log`, two bytes further on, already carries `0b 02` as its own
false-target -- the compiler's own word for "where the `Log` statement ends".
The edit reuses a target the shipped bytecode already contains.

The bytes
---------

One 24-byte region, the gate statement plus the `if (True)` header that
follows it, changed at offset 1:

    07 9b02 19 19 01 4712 0500 04 01 06 0600 04 2d 01 480c   07 0b02 27
       ^^^^ -> 0b02

Read left to right: `JumpIfNot(0x029b, Context(Context(m_ControllerOwner,
Pawn), BoolVariable(m_bIsPlayer)))`, then `JumpIfNot(0x020b, True)`. The
references decode to exports 1159, 6, 776 of the owning package and are
untouched.

The region occurs exactly once in `COMMON.LIN`, `COMMONOFF.LIN` and
`COMMON_SS.LIN`, in the block whose `ScriptSize` word sits at file 0x07aea3
in all three, and the replacement occurs in none of them. It occurs in no
level container at all -- 209 decompressed `.LIN` blobs covering 110 distinct
filenames, every mission, every multiplayer map, every training map and both
menus: the count is 1 in every COMMON copy (58 of them, stock and patched
alike, including the copies read back off the played disc) and 0 in every
other container. That is why the file selector is the three COMMON packages
and why that is complete.

Not established
---------------

* **Not played.** Nothing here has been heard in the game.
* **How much of the reported silence this fixes depends on the weapon, and
  that part is not settled.** Live RAM from an earlier session shows an AI
  carrying an L85A1 with `m_SingleFireStereoSnd` = `Play_L85A1_SingleShots`,
  i.e. a third-person sample that does exist. For a weapon like that this
  edit does not turn silence into sound; it swaps a far-mic sample for a
  close-mic one. The weapons where the third-person cue appears never to have
  been authored -- the silenced TMP among them -- are the ones this should
  fix outright. Which weapons fall in which group is a play-test question.
* **A competing diagnosis is on file and is not excluded by this.**
  `scratch-2026-09-27/aisilence/REPORT.txt` root-causes a second, certain
  defect in the same subsystem: `m_BurstFireStereoSnd` is `None` on all 30
  weapon classes and no burst asset ships, so any weapon in 3-round burst
  fires silently on either side of the player/AI fork. That is an overlay
  edit, not a script edit, and it is not in this module.
* **Which containers, and why all three.** `COMMONOFF.LIN` is offline,
  `COMMON_SS.LIN` split screen, `COMMON.LIN` online; the region is identical
  in all three, at the same file offset. Offline is where the bug was
  reported, so that one is mandatory. The online package is included because
  AI teammates exist in co-op and because `AssignSound` is `simulated` and
  client-side -- which is a reason to expect no replication consequence, not a
  measurement of one. Nothing about online play was tested. Dropping the `?`
  from `SELECT` restricts this to the two offline packages, matching the
  choice `rseff` makes for a gameplay change.
* **No second gate was looked for.** The three override statements occur
  exactly once each in each COMMON copy, so there is no duplicate of this
  block; but whether some other function re-assigns these slots later was not
  swept.
"""

from __future__ import annotations

H = bytes.fromhex


class SoundGateError(Exception):
    pass


#: `JumpIfNot(0x029b, m_ControllerOwner.Pawn.m_bIsPlayer)` followed by the
#: `if (True)` that guards the player-only `Log`. 24 bytes; the changed word is
#: at offset 1.
GATE_KEY = H("079b02191901471205000401060600042d01480c" "070b0227")

#: the jump word as shipped (the statement after the third override) and as
#: this edit leaves it (the first override) -- both MEMORY offsets
STOCK_TARGET = 0x029b
NEW_TARGET = 0x020b

#: offset of the changed word inside `GATE_KEY`
WORD_AT = 1

#: the `ScriptSize` word of `R6PawnReplicationInfo.AssignSound`, the same file
#: offset in all three COMMON packages. 1125 bytes in memory, 815 on disk.
SCRIPT_SIZE_AT = 0x07aea3

#: and the file offset of the two bytes this module writes, in all three
KNOWN_OFFSETS = (0x07afcd,)

#: the containers that carry this script: the three COMMON packages and no
#: level container (measured -- see the docstring)
SELECT = r"/COMMON(OFF|_SS)?\.LIN$"


def _edits():
    """(name, key -- whole, in its stock form, found exactly once --, offset of
    the changed bytes within the key, stock bytes, new bytes)."""
    return (
        ("the player gate in AssignSound: fall into the first-person overrides",
         GATE_KEY, WORD_AT,
         STOCK_TARGET.to_bytes(2, "little"),
         NEW_TARGET.to_bytes(2, "little")),
    )


def _sites(plain: bytes):
    """[(offset of the changed bytes, stock, new, state)] or raise."""
    out = []
    for name, key, rel, stock, new in _edits():
        done = key[:rel] + new + key[rel + len(stock):]
        hits = []
        for form, state in ((key, "stock"), (done, "new")):
            at = plain.find(form)
            if at >= 0 and plain.find(form, at + 1) >= 0:
                raise SoundGateError("%s: found more than once" % name)
            if at >= 0:
                hits.append((at + rel, state))
        if len(hits) != 1:
            raise SoundGateError("%s: %s" % (name, "not found" if not hits
                                             else "both forms present"))
        out.append((hits[0][0], stock, new, hits[0][1]))
    return out


def reads(plain: bytes) -> bool:
    try:
        return all(s[3] == "new" for s in _sites(plain))
    except SoundGateError:
        return False


def apply(plain: bytes, enable: bool = True):
    """Returns (plain, changed). The length never moves, on disk or in memory,
    and `ScriptSize` is not touched. Refuses anything it does not recognise."""
    if not enable or reads(plain):
        return plain, 0
    out = bytearray(plain)
    n = 0
    for at, stock, new, state in _sites(plain):
        if state == "stock":
            out[at:at + len(stock)] = new
            n += 1
    return bytes(out), n


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "ai_weapon_sound",
        "Teammates fire with the first-person gunshots",
        BOOL, False, group, confidence="broken", touches="data",
        enabled=False,
        disabled_reason=
            "Withdrawn 2026-09-28. The fault it was written to fix does "
            "not exist -- every weapon on the disc has a third-person "
            "fire sample. What this actually does is give every firing "
            "enemy a stereo 28 kHz sound where the game expects one mono "
            "22 kHz one, and it is the prime suspect for the reports of "
            "enemies firing with a trigger click and no gunshot.",
        help="The PS2 build keeps two sets of firing samples per weapon and "
             "hands the better one only to the weapon you are holding: the "
             "line that loads them tests whether the pawn is the player. For "
             "several guns -- the silenced TMP among them -- the other set "
             "appears never to have been recorded, so an AI teammate firing "
             "one makes the trigger click and no shot. This gives every "
             "teammate the same samples you get. It loads no new audio: the "
             "game already registers those banks for every pawn, player or "
             "not, a few lines further down the same function.",
        caution="WITHDRAWN -- see the note above. The original caution follows.\n\n"
                "The first-person samples are close-mic'd and "
                "carry no distance cue, so a teammate firing across the "
                "street may sound nearer than he is -- that is the known "
                "cosmetic cost of this fix. It is a two-byte change to one "
                "jump in the sound-loading script, the same length on disc "
                "and in memory; if a level stops loading, turn this off "
                "first.")

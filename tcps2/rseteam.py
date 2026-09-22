"""Making the split-screen arm build the two AI operatives.

What Trieste proved
-------------------

The teammates option has four failed attempts behind it, all hanging the
level load with byte-identical hang states, and the best explanation was that
bringing a non-resident operative class into a split-screen level init is what
wedges it. **That is dead.** Split-screen Practice Mode on Trieste runs
`CreatePlayerTeam`'s rescue arm on the retail disc with no patch at all, and a
savestate taken there reads `Trieste_a_ss`, the EE in game code, viewport
index 2, and `R6RainbowLoiselle`, `R6RainbowWeber` and `R6RainbowAI` all
resident -- every one of which is absent from an ordinary split-screen load.
The engine builds AI Rainbow operatives in split screen, runs them, gives them
green friendly name tags, and reaches gameplay.

So the question is what the four attempts did that Trieste does not.

What this edits
---------------

`R6RainbowTeam.CreatePlayerTeam` has two tests in a row::

    mem 0x0162   JumpIfNot(0x0357, Level.Game.m_bIsSplitScreen)
                 ; fall through = split screen, 0x0357 = single player
    mem 0x01F9   JumpIfNot(0x0354, GetMissionDescription().m_bRescureRainbow)
    mem 0x020B   ; the rescue arm:
                 ;   m_iMemberCount = 2
                 ;   CreateTeamMember(2, m_CoverSpots[1], False, ...)
                 ;   m_iMemberCount = 3
                 ;   CreateTeamMember(3, m_CoverSpots[2], False, ...)
                 ;   m_iMemberCount = 4

`m_bRescureRainbow` is true in exactly ONE of 96 map INIs -- Trieste -- which
is why that arm has only ever run there. Pointing the second jump at
`0x020B`, the statement it already falls through to, turns it into a no-op and
the rescue arm runs on every split-screen level.

Two bytes. No re-assembly, no `ScriptSize` change, no rebasing -- the whole
class of problem that the earlier attempts lived in.

Why this is shaped like the rescue arm and not like the single-player one
-------------------------------------------------------------------------

The four attempts jumped into the SINGLE-PLAYER builder, which relies on
`CreateTeamMember` doing `m_iMemberCount++`. Split screen pins that count to
1 on every call, at mem 0x0EDE, so those attempts would have written every
operative into `m_Team[1]` -- on top of player 2 -- even if the load had
survived. The rescue arm does not use `++`: it writes 2, 3 and 4 by hand
around the calls, because the authors knew about the pin. Reusing it inherits
that correctness for free.

What is NOT known
-----------------

Whether every map places `m_CoverSpots[1]` and `[2]`. Trieste does. If
another map does not, `CreateTeamMember` takes its "invalid spawning point"
path, and what that does on a split-screen load is exactly what this
experiment is for. Expect some maps to misbehave; that is the point of
testing it rather than shipping it on.
"""

from __future__ import annotations

#: The rescue test inside `CreatePlayerTeam`, at plain offset in COMMON*.LIN.
#: `07` is EX_JumpIfNot; the two bytes after it are a little-endian MEMORY
#: offset, which is what UE2 bytecode jumps carry -- not a file offset.
BRANCH = 0x0014721D
OPCODE = 0x07

#: Where it jumps when the mission is not a rescue, and where it falls
#: through to when it is. Retargeting the first to the second makes the jump
#: a no-op, so the rescue arm always runs.
SKIP_TARGET = 0x0354
ARM_TARGET = 0x020B


class TeamError(Exception):
    pass


def _check(plain):
    if plain[BRANCH] != OPCODE:
        raise TeamError("plain 0x%06x is %02x, not the EX_JumpIfNot this "
                        "build should have" % (BRANCH, plain[BRANCH]))
    live = plain[BRANCH + 1] | (plain[BRANCH + 2] << 8)
    if live not in (SKIP_TARGET, ARM_TARGET):
        raise TeamError("the rescue branch points at 0x%04x, which is "
                        "neither the shipped 0x%04x nor the patched 0x%04x"
                        % (live, SKIP_TARGET, ARM_TARGET))
    return live


def reads(plain: bytes) -> bool:
    """True if the rescue arm already runs unconditionally."""
    return _check(plain) == ARM_TARGET


def apply(plain: bytes, enable: bool = True):
    """Run the rescue arm everywhere AND spawn somewhere that exists.

    Returns (bytes, changed). Two bytes move and the length never does.
    """
    live = _check(plain)
    want = ARM_TARGET if enable else SKIP_TARGET
    if live == want:
        return plain, 0
    out = bytearray(plain)
    out[BRANCH + 1] = want & 0xFF
    out[BRANCH + 2] = (want >> 8) & 0xFF
    if len(out) != len(plain):
        raise TeamError("the team edit changed the file length")
    out, more = spots_apply(bytes(out), enable)
    return out, 1 + more


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_rescue_team", "Build the two AI operatives",
        BOOL, False, group, confidence="untested", touches="data",
        caution='EXPERIMENTAL, third attempt, and paired with the streaming-budget option -- turn BOTH on. Attempt one unlocked the rescue arm and hung off Trieste. Attempt two also pointed both spawns at m_CoverSpots[0], the spot the game null-checks and single player trusts everywhere, and Island wedged identically. So the spawn point is not the cause either. Four explanations are now refuted by measurement: the bytecode edits (this is four bytes with no re-assembly), the operative class load (Trieste builds the same operatives and runs), the gametype (Practice hangs too) and the spawn point. All four were about the TEAM. The wedge is not a crash -- it is the console frozen re-reading the last chunk of the level file -- so the untested lever is the STREAMING, which is what the budget option is for.',
        help="Split screen builds a two-man team and stops. The engine can "
             "build AI Rainbow operatives in split screen -- Trieste proves "
             "it on the retail disc -- but the code that does it is behind a "
             "mission flag that only Trieste sets. This points that test at "
             "the arm it guards, so the arm runs on every split-screen "
             "level.")


# ---------------------------------------------------------------------------
# spawning them somewhere that exists on every map
# ---------------------------------------------------------------------------

#: The split-screen rescue arm spawns at `m_CoverSpots[1]` and `[2]`. Those
#: two are only DERIVED, at mem 0x025c, and only when `m_CoverSpots[0]` is
#: not None::
#:
#:     0x024f  if (m_CoverSpots[0] != None) {
#:     0x025c      m_CoverSpots[1] = m_CoverSpots[0].m_CoverGroup[0]
#:     0x0276      m_CoverSpots[2] = m_CoverSpots[0].m_CoverGroup[1]
#:             }
#:     0x02b9  CreateTeamMember(2, m_CoverSpots[1], False, ...)
#:     0x0300  CreateTeamMember(3, m_CoverSpots[2], False, ...)
#:
#: So on a map without a cover GROUP behind spot 0, both spawn into nothing.
#: The single-player arm never does this: it uses `m_CoverSpots[0]` at mem
#: 0x0378 and falls all the way back to `teamStartingPoint` at 0x056d.
#:
#: Pointing both calls at `m_CoverSpots[0]` is two ONE-byte edits, because
#: the index sits inside the array expression and the replacement is the
#: same width:
#:
#:     1a 26 01 28   ArrayElement(IntOne,         m_CoverSpots)  -> 25 IntZero
#:     1a 2c 02 01 28  ArrayElement(IntConstByte 2, m_CoverSpots) -> 00
#:
#: No re-assembly, no length change. Both operatives then share one spot,
#: which is ugly, but spot 0 is the one the game itself null-checks and the
#: one the single-player arm trusts on every map.
#:
#: Each signature occurs TWICE -- once in the split-screen arm and once in
#: the single-player arm at mem 0x054f/0x0300. Only the FIRST is touched.
SPOT2_SIG = bytes.fromhex("1b7101" "2c02" "1a26" "0128")
SPOT2_AT = 6            # the IntOne byte inside the signature
SPOT2_ONE, SPOT2_ZERO = 0x26, 0x25

SPOT3_SIG = bytes.fromhex("1b7101" "2c03" "1a2c02" "0128")
SPOT3_AT = 7            # the IntConstByte operand
SPOT3_TWO, SPOT3_ZERO = 0x02, 0x00


def _spot(plain, sig, at, stock, want):
    """Offset of the SPLIT-SCREEN arm's index byte, patched or not.

    Each signature occurs twice -- the split-screen arm first, then the
    single-player arm. Searching for the shipped form alone is wrong once
    the first has been patched, because `find` then lands on the SECOND,
    which is the single-player copy and must never be touched. So both
    forms are searched and the earliest wins.
    """
    shipped = bytearray(sig)
    shipped[at] = stock
    patched = bytearray(sig)
    patched[at] = want
    hits = [i for i in (plain.find(bytes(shipped)), plain.find(bytes(patched)))
            if i >= 0]
    if not hits:
        raise TeamError("neither the shipped nor the patched spawn "
                        "expression is in this file")
    return min(hits) + at


def spots_read(plain: bytes) -> bool:
    """True if both calls already spawn at m_CoverSpots[0]."""
    a = _spot(plain, SPOT2_SIG, SPOT2_AT, SPOT2_ONE, SPOT2_ZERO)
    b = _spot(plain, SPOT3_SIG, SPOT3_AT, SPOT3_TWO, SPOT3_ZERO)
    return plain[a] == SPOT2_ZERO and plain[b] == SPOT3_ZERO


def spots_apply(plain: bytes, enable: bool = True):
    """Point both rescue-arm spawns at m_CoverSpots[0], or put them back."""
    out = bytearray(plain)
    changed = 0
    for sig, at, stock, zero in ((SPOT2_SIG, SPOT2_AT, SPOT2_ONE, SPOT2_ZERO),
                                 (SPOT3_SIG, SPOT3_AT, SPOT3_TWO, SPOT3_ZERO)):
        i = _spot(plain, sig, at, stock, zero)
        want = zero if enable else stock
        if out[i] != want:
            out[i] = want
            changed += 1
    if len(out) != len(plain):
        raise TeamError("the spawn-point edit changed the file length")
    return bytes(out), changed


# ---------------------------------------------------------------------------
# the streaming budget, the one per-mode number in the overlay
# ---------------------------------------------------------------------------

#: `0x00472160` reads, in full::
#:
#:     lw    $a0, 0x8fb0($gp)     ; g_bSplitScreen
#:     addiu $v0, $zero, 3
#:     addiu $v1, $zero, 6
#:     jr    $ra
#:     movz  $v0, $v1, $a0        ; delay slot: split ? 3 : 6
#:
#: Split screen runs on HALF the streaming slots single player gets, and this
#: is the only number in the overlay that differs by mode. One caller, at
#: `0x004ca264`.
#:
#: Replacing the `movz` with `daddu $v0, $v1, $zero` returns 6 always. It
#: sits in the `jr` delay slot, which is safe: the replacement is another
#: non-branch instruction and the register it writes is the return value.
BUDGET = 0x00472170
BUDGET_STOCK = 0x0064100A       # movz  $v0, $v1, $a0
BUDGET_SIX = 0x0060102D         # daddu $v0, $v1, $zero


def budget_card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_stream_budget",
        "Give split screen the full streaming budget", BOOL, False, group,
        confidence="broken", touches="code",
        enabled=False,
        disabled_reason="WITHDRAWN -- it corrupts memory. On hardware it produced an R5900 exception, 'Jump to unaligned address (PC: 0xffffffff)', which is a corrupted function pointer or return address, not a resource shortage.\n\nThe reasoning behind it was sound and the patch itself is correct: 0x00472160 really does return 3 in split screen and 6 otherwise, it really is the only per-mode number in the overlay, and the edit really is one non-branch instruction replacing another in a jr delay slot. What was not checked is what the CALLER does with the value. There is one caller, at 0x004ca264, and if it uses the count to size or index a table that split screen allocated for three, returning six walks off the end of it. That is exactly the shape of the crash.\n\nSo the budget is not a free knob: it is half of a pair, and the other half is however much memory split screen reserved. Making this work would mean finding and raising that allocation too, which is a real change rather than a one-word switch.\n\nThe lesson is narrower than 'do not raise budgets'. The plan that proposed this flagged the risk as audio dropouts or stutter -- a graceful degradation. It is not graceful; it scribbles. A value that one site returns can still be a size that another site trusted.",

        help='Split screen runs on three streaming slots where single player gets six, and that is the only number in the whole game that differs by mode. This gives both modes six.',
        caution="EXPERIMENTAL, and aimed at one specific thing: the load wedge that has defeated six different teammate edits. That wedge is not a crash and not a null dereference -- it is the console frozen re-reading the last chunk of the level file at off=0x540000 len=0x4680, which is exactly what a starved streaming budget plus one extra request during level init would look like. Every explanation refuted so far was about the TEAM -- the bytecode edits, the operative class load, the gametype, the spawn point. None was about the streaming.\n\nOne word, in a jr delay slot, replacing one non-branch instruction with another. Single player already returns 6, so it is a no-op there by construction.\n\nIt raises split screen's streaming memory and bandwidth to what single player already uses. If audio drops out or levels stutter, this is the first thing to turn off.")

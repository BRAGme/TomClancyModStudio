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
        BOOL, False, group, confidence="broken", touches="data",
        enabled=False,
        disabled_reason="Tested twice on hardware and withdrawn. Version one unlocked the rescue arm and hung on every map but Trieste. Version two also pointed both spawns at m_CoverSpots[0], the spot the game itself null-checks and single player trusts everywhere -- and Island wedged identically, off=0x540000 len=0x4680, the same frozen re-read of the level .LIN's final chunk. So the spawn point is NOT the cause either. That is the fourth explanation this wedge has survived. Refuted by measurement, in order: the bytecode edits (this is two bytes with no re-assembly), the operative class load (Trieste builds the same operatives and runs), the gametype (Practice hangs too), and now the spawn point. Six separate edits reproduce it and Trieste is the sole exception. What it is worth keeping for: the wedge now has a switchable trigger. Yesterday it could only be reached through a frozen savestate. Anyone picking this up can turn it on and off in four bytes, which is the right position from which to attack it with a debugger.",
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

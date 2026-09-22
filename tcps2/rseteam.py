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
    """Point the rescue test at its own arm, or put it back.

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
    return bytes(out), 1


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_rescue_team", "Build the two AI operatives",
        BOOL, False, group, confidence="broken", touches="data",
        enabled=False,
        disabled_reason='Tested on hardware and it HANGS on any map but Trieste, so it is withdrawn. Island Estate wedges in split screen, in Practice Mode as well as Terrorist Hunt, so it is the map and not the gametype. m_brescureRainbow is set in exactly ONE of 96 map INIs -- Trieste is the only level authored for the rescue, and the only one that places the cover spots this arm spawns at. What the test did buy is worth more than the option. The hang state matches the known wedge EXACTLY: IOP streaming frozen at off=0x540000 len=0x4680, the final partial chunk of the level .LIN. That is the same freeze as ss_man_down, canon_team and all four earlier teammate attempts. This edit is TWO BYTES with no re-assembly and no inserted control flow, which kills the theory that the bytecode edits were to blame. Six failures are one bug, and its trigger is now a two-byte switch rather than a frozen savestate. It also refutes the residency theory from the other direction: Trieste builds the same operatives in split screen and runs fine, so it is not the operative class load either. What separates them is that Trieste has somewhere valid to put them.',
        help="Split screen builds a two-man team and stops. The engine can "
             "build AI Rainbow operatives in split screen -- Trieste proves "
             "it on the retail disc -- but the code that does it is behind a "
             "mission flag that only Trieste sets. This points that test at "
             "the arm it guards, so the arm runs on every split-screen "
             "level.",
        caution="EXPERIMENTAL. Two bytes, no re-assembly, and it reuses the "
                "game's own rescue arm rather than jumping into the "
                "single-player builder -- which is what the four withdrawn "
                "attempts did, and that builder relies on a member counter "
                "that split screen pins to 1, so they would have written "
                "every operative on top of player 2 even had they "
                "loaded.\n\n"
                "What is not known is whether every map places the two cover "
                "spots the arm spawns them at. Trieste does. A map that does "
                "not will take the \"invalid spawning point\" path, and what "
                "that does during a split-screen load is exactly what this "
                "is for. Expect some maps to misbehave, and use RESTORE DISC "
                "if one does.")

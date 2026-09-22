"""AI teammates in split screen, by sending it down the arm that already works.

The shape of CreatePlayerTeam
-----------------------------

`R6RainbowTeam.CreatePlayerTeam` lives in the package at plain `0x086a7f` in
every COMMON build, script block at `0x1470a3`, disk 1346 / memory 1775. Read
whole, it is a fork with two arms:

```
0x0150: CreateTeamMember(0, p_playerStartingPoint, True, PC)      ; player 1
0x0162: JumpIfNot(-> 0x357, Level.Game.m_bIsSplitScreen)          ; THE FORK
          ; ---- split-screen arm ----
0x017d:   PC = R6PlayerController(Level.m_playerList[1])          ; player 2
0x0198:   if (PC != None)
0x01c4:     CreateTeamMember(1, m_CoverSpots[0], True, PC, bTerroHunt)
0x01f9:   if (aMissionDescription.m_bRescureRainbow)              ; Trieste only
0x02b9:     CreateTeamMember(2, m_CoverSpots[1], False, PC, False)
0x0300:     CreateTeamMember(3, m_CoverSpots[2], False, PC, False)
0x0354:   Jump(-> 0x688)                                          ; <-- THE END
          ; ---- single-player arm ----
0x0357: ... CreateTeamMember(1, ...)      ; Price
0x03fb: if (!bTerroHunt && !m_bMissionPrice) RemoveMember()
0x0420: ... rescue cover-spot setup, skipped when the flag is false
0x04d1: if (... && m_CoverSpots[1] != None)
0x054f:     CreateTeamMember(2, m_CoverSpots[1], False, PC, bTerroHunt)
0x056d:   else CreateTeamMember(2, teamStartingPoint, False, PC, bTerroHunt)
0x0586: if (!bTerroHunt && !m_bMissionLoiselle) RemoveMember()
0x05ab: ... CreateTeamMember(3, ...)      ; Weber
0x0663: if (!bTerroHunt && !m_bMissionWeber) RemoveMember()
0x0688: end
```

Split screen creates player 2 as member 1 and then **jumps clean over the
entire AI-creation section**. That unconditional `Jump` at memory `0x0354` is
the whole reason there are no teammates. It is not a flag, not a budget and
not missing content -- it is one jump.

Why every previous attempt failed
---------------------------------

Six attempts all aimed at the `JumpIfNot` at memory `0x01f9` (disk
`0x14721d`), forcing the **rescue** arm to run. That arm spawns at
`m_CoverSpots[1]` and `m_CoverSpots[2]`, which are filled from
`RescureTeamStartingPoint` -- and it has **no fallback** if they come back
null. On a map that authors no starting point the spawn target is nothing at
all, which is exactly the wedge that was seen, most recently on Alpine
Village with no code patched whatsoever.

The single-player arm is written defensively where the rescue arm is not.
`0x04d1` tests `m_CoverSpots[1] != None` and falls through to `0x056d`, which
spawns at `teamStartingPoint` -- a local assigned at `0x0028`/`0x0036` from
the function's own parameters, so it always exists. That is the difference,
and it is why this edit points at that arm instead.

The edit
--------

Retarget one `Jump`: memory `0x0354`, `0x0688` -> `0x0420`.

Landing at `0x0420` rather than `0x03fb` is deliberate. `0x03fb` is the
`m_bMissionPrice` check, and `RemoveMember` takes off the member most
recently added -- which in the split-screen arm is **player 2**, a human. On
any map where Price is not in the mission that would delete the second player
from his own team. `0x0420` starts just past it, which is correct on its own
terms too: player 2 occupies Price's slot, so Price's presence test has
already been answered by there being a second player at all.

What the split-screen team then becomes:

| member | who |
| ------ | --- |
| 0 | player 1 |
| 1 | player 2 |
| 2 | AI, Loiselle, subject to `m_bMissionLoiselle` |
| 3 | AI, Weber, subject to `m_bMissionWeber` |

which is the same pair of operatives Trieste produces, reached without
needing anything Trieste authors.

Three bytes wide, and only two of them change: `06 88 06` becomes
`06 20 04`. The token keeps its width, so `ScriptSize` cannot move and no
other jump is touched -- the rule this engine hangs on breaking.

Why it is safe outside split screen
-----------------------------------

Memory `0x0354` is only reachable through the `m_bIsSplitScreen` branch at
`0x0162`. Single player and online take the other arm at `0x0357` and never
execute this instruction. The edit is therefore not merely harmless in those
modes, it is **unreachable** -- which is why it is written to all three COMMON
files and nobody has to be right about which one a mode loads.

What is NOT established
-----------------------

Three things, all of which need the disc to run:

* that `CreateTeamMember` succeeds for members 2 and 3 in split screen at
  all. The engine demonstrably can build AI operatives in split screen --
  Trieste does it on the retail disc -- but Trieste does it through the other
  arm.
* that passing player 2's `PlayerController` is right. In the split-screen
  arm `PlayerController` was reassigned at `0x017d` to player 2, so the AI
  are created against player 2 rather than player 1. What that argument
  governs was not traced. It may mean the AI follow player 2, which is a
  behaviour question rather than a correctness one.
* that `m_iMemberCount` ends up correct. The rescue arm sets it explicitly
  (`0x020b`, `0x02cf`, `0x0317`); the single-player arm never does, so
  `CreateTeamMember` must maintain it. That was inferred from the asymmetry,
  not read.
"""

from __future__ import annotations

#: Context through the `Jump`, long enough to be unique in all three COMMON
#: builds. The last three bytes are the instruction itself.
SIGNATURE = bytes([
    0x3A, 0x24, 0x0A, 0x16,        # ...end of the m_iMemberCount store
    0x1B, 0x45, 0x05, 0x16,        # VirtualFunction(RemoveMember)
    0x1B, 0x45, 0x05, 0x16,        # VirtualFunction(RemoveMember)
    0x0F, 0x01, 0x16, 0x26,        # Let(m_iMemberCount, IntOne())
    0x06, 0x88, 0x06,              # Jump -> 0x0688      <-- retargeted
])

#: Index of the `Jump` opcode inside SIGNATURE; its target is the next two
#: bytes, little-endian.
JUMP = 16

SKIP_TARGET = 0x0688        # stock: straight to the end of the function
ARM_TARGET = 0x0420         # the single-player AI arm, past the Price check

#: Measured on this disc. Not used to find anything.
KNOWN_OFFSET = 0x147326

#: The second half of the fix, and the reason the first half alone wedged.
#:
#: `CreateTeamMember` ends by maintaining the member count, and in split
#: screen it does not count -- it RESETS::
#:
#:     0x0ead: if (Level.Game != None && Level.Game.m_bIsSplitScreen)
#:     0x0ede:     m_iMemberCount = 1        ; hard reset
#:     0x0ee8: else m_iMemberCount++
#:
#: The rescue arm survives that by setting the count explicitly around each
#: of its calls (2, 3, 4, then 1). The single-player arm the jump above lands
#: in does not, so AI creation runs with the count pinned at 1: both
#: operatives are written into `m_Team[1]`, on top of player 2, and
#: `iSpawnTry` -- assigned `m_iMemberCount` at mem `0x0067` -- starts from 1
#: instead of 0. The wedged savestate's retained error buffer reads
#: "Script serialization mismatch: Got 0, expected -184945406", which is what
#: that kind of arithmetic damage looks like by the time the engine notices.
#:
#: The condition is `(Level.Game != None) && Level.Game.m_bIsSplitScreen`.
#: Changing `native119` (object `!=`) to `native114` (object `==`) makes the
#: first operand false, the `&&` short-circuits, and the reset is skipped in
#: favour of the increment.
#:
#: Single player is unchanged, and provably so: there the condition was
#: ALREADY false (`m_bIsSplitScreen` is false), so it already took the
#: increment. After the edit it still takes the increment, by the other
#: operand. Same path, same result.
COUNT_SIG = bytes([
    0x07, 0xE8, 0x0E,              # JumpIfNot -> 0x0ee8 (the increment)
    0x82,                          # bool eval
    0x77,                          # native119  !=(Object, Object)   <-- edited
    0x19, 0x01, 0x8F, 0x05, 0x00, 0x04, 0x01, 0xA6,   # Level.Game
    0x2A,                          # EX_NoObject (None)
    0x16,                          # EX_EndFunctionParms
])
COUNT_OPERAND = 4
COUNT_STOCK = 0x77      # native119, !=
COUNT_FIXED = 0x72      # native114, ==

#: Measured on this disc. Not used to find anything.
KNOWN_COUNT_OFFSET = 0x146BC6


class SquadError(Exception):
    pass


def _site(plain: bytes) -> int:
    """Offset of the SIGNATURE, whichever target the jump currently holds."""
    found = []
    for target in (SKIP_TARGET, ARM_TARGET):
        probe = bytearray(SIGNATURE)
        probe[JUMP + 1] = target & 0xFF
        probe[JUMP + 2] = (target >> 8) & 0xFF
        probe = bytes(probe)
        at = plain.find(probe)
        while at >= 0:
            found.append(at)
            at = plain.find(probe, at + 1)
    if len(found) != 1:
        raise SquadError(
            "expected exactly 1 split-screen team jump, found %d -- this is "
            "not the build this was measured on" % len(found))
    return found[0]


def reads(plain: bytes) -> int:
    """The jump's current target."""
    at = _site(plain) + JUMP + 1
    return plain[at] | (plain[at + 1] << 8)


def _count_site(plain: bytes) -> int:
    """Offset of the member-count clamp, whichever operator it holds."""
    found = []
    for op in (COUNT_STOCK, COUNT_FIXED):
        probe = bytearray(COUNT_SIG)
        probe[COUNT_OPERAND] = op
        probe = bytes(probe)
        at = plain.find(probe)
        while at >= 0:
            found.append(at)
            at = plain.find(probe, at + 1)
    if len(found) != 1:
        raise SquadError(
            "expected exactly 1 member-count clamp, found %d -- this is not "
            "the build this was measured on" % len(found))
    return found[0]


def counts(plain: bytes) -> bool:
    """True if split screen increments the member count instead of pinning it."""
    return plain[_count_site(plain) + COUNT_OPERAND] == COUNT_FIXED


def apply(plain: bytes, enable: bool = True):
    """Both halves. Returns (bytes, changed). Length never moves.

    They are deliberately not separable. The jump alone was play-tested and
    wedged, because it routes AI creation into an arm that never maintains
    the member count; the clamp alone does nothing, because nothing reaches
    the code that would notice. An option that can be half-applied is an
    option that can be tested into a misleading answer.
    """
    out = bytearray(plain)
    changed = 0

    at = _site(plain)
    want = ARM_TARGET if enable else SKIP_TARGET
    if reads(plain) != want:
        out[at + JUMP + 1] = want & 0xFF
        out[at + JUMP + 2] = (want >> 8) & 0xFF
        changed += 1

    cat = _count_site(plain)
    cwant = COUNT_FIXED if enable else COUNT_STOCK
    if plain[cat + COUNT_OPERAND] != cwant:
        out[cat + COUNT_OPERAND] = cwant
        changed += 1

    if len(out) != len(plain):
        raise SquadError("the squad edit changed the file length")
    return bytes(out), changed


HELP = ("Split screen creates player 2 as the second team member and then "
        "jumps straight over the code that creates the AI operatives. This "
        "retargets that one jump into the arm single player already uses, so "
        "the team is filled out with Loiselle and Weber behind the two "
        "players.")

CAUTION = (
    "EXPERIMENTAL, but a different shape from the six attempts before it, and "
    "the reason they failed is now understood.\n\n"
    "All six retargeted the branch that forces the RESCUE arm. That arm "
    "spawns at cover spots derived from a rescue starting point, with no "
    "fallback when they come back null -- so on a map that authors no "
    "starting point it spawns operatives nowhere, which is the wedge that "
    "kept happening. Alpine Village reproduced it with no code patched at "
    "all, just one line of INI, which is what finally made the cause "
    "clear.\n\n"
    "This points at the SINGLE-PLAYER arm instead, which is written "
    "defensively where the rescue arm is not: it tests the cover spot for "
    "null and falls back to the team starting point, a value the function "
    "assigns from its own parameters and which therefore always exists.\n\n"
    "Two bytes, inside a jump that keeps its width, so ScriptSize does not "
    "move and no other jump is touched.\n\n"
    "Single player and online cannot change, and this time it is stronger "
    "than safe -- the instruction is UNREACHABLE unless split screen is "
    "running, because it sits inside the branch the split-screen test "
    "guards.\n\n"
    "PLAY-TESTED on Alpine Village, and it wedged -- but it got FURTHER than "
    "anything before it, and the savestate says where. The AI operatives "
    "start being built: R6RainbowLoiselle goes from 4 references in a working "
    "split-screen state to 8 in the wedged one, R6RainbowWeber from 4 to 7. "
    "So the jump lands correctly and the team code runs. The EE is then "
    "parked in the kernel with the UnrealScript VM's opcode dispatch on the "
    "stack, which means it hung inside script, downstream of this edit.\n\n"
    "It is not an infinite load. The console is parked in the engine's fatal "
    "error handler, and the wedged savestate still holds the message: the "
    "retained error buffer at 0x005b9070 reads \"Script serialization "
    "mismatch: Got 0, expected -184945406\", where four working states all "
    "hold the pristine default \"General protection fault!\". Only the wedged "
    "state carries FORMATTED linker errors rather than bare format strings, "
    "among them \"failed to alloc 50331656 bytes\" (0x03000008, a length read "
    "from garbage) and a serial-size mismatch naming R6Characters.\n\n"
    "CreateTeamMember also ends with `if (m_bIsSplitScreen) m_iMemberCount = "
    "1; else m_iMemberCount++;` -- a hard RESET, not an increment. That is "
    "fixed here too, because resetting a count instead of counting is wrong "
    "on its own terms and the operatives need m_Team[2] and [3] to be free. "
    "It was NOT the cause: Alpine Village failed byte-identically with the "
    "count fix and without it.\n\n"
    "Island Estate then failed with a DIFFERENT error, and that is the most "
    "informative thing this option has produced: \"BAD EXPORT INDEX 93/84\". "
    "R6Characters has exactly 84 exports; the loader asked for 93. Alpine "
    "reads garbage of another shape entirely -- a 50331656-byte allocation, "
    "import index 567337 of 103 -- so what gets read depends on memory state, "
    "not on the map.\n\n"
    "That rules out the last content-shaped explanation. Not the Winter "
    "classes: Island is not a winter map. Not the routing: the jump lands "
    "correctly and the operatives begin to build, which the savestate string "
    "counts show. Loading these pawn classes through DynamicLoadObject at "
    "team-build time resolves out of range inside R6Characters, and nothing "
    "reachable from a same-width operand swap changes that.\n\n"
    "Leave this OFF. RESTORE DISC puts everything back.")


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_squad", "AI teammates in split screen",
        BOOL, False, group, confidence="broken", touches="data",
        enabled=False,
        disabled_reason=(
            "Play-tested on Alpine Village and Island Estate. Both wedge the "
            "level load, and the reason is now known and is not reachable "
            "from here.\n\n"
            "The routing this option performs is CORRECT -- the operatives "
            "genuinely start being built, which the savestates show. What "
            "fails is the class load underneath it: CreateTeamMember resolves "
            "each pawn with DynamicLoadObject out of the R6Characters "
            "package, and that lookup lands out of range. Island asked for "
            "export 93 of 84; Alpine read a 50,331,656-byte allocation length "
            "and import index 567337 of 103. Different garbage per map, so it "
            "is reading uninitialised memory rather than hitting one bug.\n\n"
            "Nine explanations are closed by measurement: the level data "
            "(identical tables between the offline and split-screen builds), "
            "the script (those two files are byte-identical), the streaming "
            "budget (that number is the audio stream cap), the rescue flag, "
            "the member count (byte-identical failure with and without the "
            "fix), the Winter pawn classes (Island is not a winter map), the "
            "spawn point, the gametype and the operative class load itself.\n\n"
            "Fixing it would mean editing the cooked R6Characters package, "
            "which is a different and much riskier class of change than the "
            "same-width operand swaps everything here is built from. The "
            "diagnosis is kept so none of it has to be found twice."),
        help=HELP, caution=CAUTION)

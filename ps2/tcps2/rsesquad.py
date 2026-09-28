"""AI teammates in split screen: the team code half.

Why every attempt before this one wedged
----------------------------------------

Six attempts made split screen build Loiselle and Weber, by four different
routes through `R6RainbowTeam.CreatePlayerTeam`, and every one of them wedged
the level load. The routes were never the problem. A split-screen level file
is a RECORDING of what one boot read, replayed in order, and that boot never
created the operatives -- so the moment any route asks for Loiselle's class,
the engine reads the next recorded bytes as that class and the load falls out
of step for good. Island's savestate from the last attempt retains the
engine's own error, "BAD EXPORT INDEX 93/84", and "SERIAL SIZE MISMATCH: GOT
66, EXPECTED 321", where 321 bytes is R6RainbowWeber's class.

`rsesplice` supplies the recording a boot with operatives reads. This module
makes the boot ask for it. Neither works alone and they are one option.

The shape of CreatePlayerTeam
-----------------------------

In the package at plain `0x086a7f` of every COMMON build, script block at
`0x1470a3`, disk 1346 / memory 1775::

    0x0150: CreateTeamMember(0, p_playerStartingPoint, True, PC)      ; player 1
    0x0162: JumpIfNot(-> 0x357, Level.Game.m_bIsSplitScreen)
              ; ---- split-screen arm ----
    0x017d:   PC = R6PlayerController(Level.m_playerList[1])          ; player 2
    0x0198:   if (PC != None)
    0x01c4:     CreateTeamMember(1, m_CoverSpots[0], True, PC, bTerroHunt)
    0x01f9:   if (aMissionDescription.m_bRescureRainbow)   <-- THIS JUMP
    0x02b9:     CreateTeamMember(2, m_CoverSpots[1], False, PC, False)
    0x0300:     CreateTeamMember(3, m_CoverSpots[2], False, PC, False)
    0x0354:   Jump(-> 0x688)
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

The edit
--------

The rescue test at `0x01f9` (disk `0x14721d`) jumps to `0x0354` when the map is
not a rescue -- straight out of the function. It now jumps to `0x0420`, into
the single-player arm just past its Price check, so every non-rescue map
creates Loiselle and Weber exactly as single player does, and removes whichever
the mission's roster leaves out:

| member | who |
| ------ | --- |
| 0 | player 1 |
| 1 | player 2 |
| 2 | AI Loiselle, unless the mission leaves her out |
| 3 | AI Weber, unless the mission leaves him out |

Why this jump and not the `Jump` at `0x0354`, which the previous version
retargeted: that one runs after the rescue arm as well, so on Trieste -- where
the rescue arm already builds both operatives -- it would build them twice.
Retargeting the rescue test's miss leaves Trieste's hit exactly as shipped.

Landing at `0x0420` rather than `0x03fb` is deliberate: `0x03fb` removes the
member most recently added when Price is not in the mission, and in split
screen that member is player 2.

The member count
----------------

`CreateTeamMember` ends by maintaining the member count, and in split screen
it RESETS rather than counts::

    0x0ead: if (Level.Game != None && Level.Game.m_bIsSplitScreen)
    0x0ede:     m_iMemberCount = 1
    0x0ee8: else m_iMemberCount++

The rescue arm survives that by setting the count itself around each call.
The single-player arm does not, so without this both operatives would be
written into `m_Team[1]`, on top of player 2. `native119` (object `!=`)
becomes `native114` (object `==`): the first operand goes false, the `&&`
short-circuits, and the increment runs. Single player already took the
increment, by the other operand, and still does. On Trieste the rescue arm's
own assignments overwrite the count after every call, so it ends where it
always did.

Both edits keep their token widths, so `ScriptSize` cannot move. They are
written to `COMMON_SS.LIN` only -- the package split screen loads -- and both
sit where only split screen reaches anyway.

When someone dies
-----------------

Two split-screen branches were written for a team of exactly two humans.

`R6MObjAcceptableRainbowLosses.PawnKilled` (block `0x1d699b`, mem 1727)
fails the mission when a player dies. Single player fails at once (`0x0574`).
Split screen instead asks, at `0x0434`, whether `m_Team[0]` and `m_Team[1]`
are both dead or None, and otherwise announces "has been incapacitated"
(`0x0528`) and returns. Retail's `m_Team[1]` is player 2. Here it is an AI,
so while the AI lives the mission never fails. The test now reads each
player's own pawn: `R6PlayerController(Killed.Level.m_playerList[k]).m_pawn`
for k = 0 and 1, the list and cast the function's multiplayer loop already
uses (`0x05e8`).

`R6RainbowTeam.TeamMemberDead` (block `0x1409b8`, mem 1062) opens with
`if (Level.Game.m_bIsSplitScreen) return;`. In split screen a dead AI therefore
stays in the counted squad. The ladder code waits for it for good:
`AllMembersAreOnTheSameSideOfTheLadder` and `VerifyTeamLadderClimbing` count
it, and the next AI's pace member is still the corpse. `m_bTeamIsClimbingLadder`
never clears, and `R6PlayerController.CanIssueTeamOrder` refuses both players
while it is set. The gate now also asks `DeadPawn.m_bIsPlayer`. A player's
death still returns: single player's leader path would make an AI the leader,
and its tail would write player 2 over an AI's slot. An AI's death gets single
player's bookkeeping, which clears the ladder flag once no living AI is on the
ladder and moves the dead member out of the count. Its writes stop below
`m_iMemberCount + m_iMembersLost`, which is where player 2 sits, so he is never
moved. That is also why the failure test finds the players through their
controllers: after an AI dies, `m_Team[m_iMemberCount]` is no longer player 2,
and `R6Game` has no import for `m_iMembersLost`.

Both are region rewrites of exactly the stock disk and memory length. Every
statement outside them keeps its offset. Each function still references
exactly the objects and names it did, so its load asks for nothing new: the
new tests use only references the function already holds, and the dead bytes
after `PawnKilled`'s new jump keep `m_Team`, which only the old test used.
`TeamMemberDead` gives up its first `bShowLog` debug print to make room.
Everything that print referenced is used again later in the function, and
`bShowLog` reads False on the team in every savestate.

What is NOT established
-----------------------

* Who the AI follow. The split-screen arm reassigned `PC` to player 2's
  controller at `0x017d`, and the single-player arm passes `PC` to
  `CreateTeamMember`, so the operatives are created against player 2 rather
  than player 1. What that argument governs was not traced.
* How the AI look. `LoadMissionRainbowSkins` clamps its member count to 2 in
  split screen (mem `0x0825`), so they may wear their class's default skin
  rather than the mission's camouflage.
* The winter levels. `rsesplice` covers them too, but their order is
  reasoned from an exact accounting of what single player reads, not proved
  by a map like Trieste -- see its notes. Before it did, Alpine Village
  wedged with exactly the recording desync every other level had.

Retired neighbour: `rseteam` (`split_rescue_team`) retargeted this same jump to
`0x020b` to force the rescue arm. It stays retired; this refuses a file that
carries its edit rather than guessing.
"""

from __future__ import annotations

#: The rescue test at memory `0x01f9`, with two bytes of the next statement
#: so the pattern is unique in all three COMMON builds.
RESCUE_SIG = bytes([
    0x07, 0x54, 0x03,              # JumpIfNot -> 0x0354      <-- retargeted
    0x19,                          # Context:
    0x00, 0x71, 0x0C,              #   local aMissionDescription
    0x06, 0x00, 0x04,              #   (skip 6, result size 4)
    0x2D, 0x01, 0xCB, 0x04,        #   .m_bRescureRainbow
    0x0F, 0x01,                    # next statement: Let(...
])

#: Index of the `JumpIfNot` opcode inside RESCUE_SIG; its target is the next
#: two bytes, little-endian, in MEMORY offsets as all cooked jumps are.
RESCUE_JUMP = 0

SKIP_TARGET = 0x0354        # stock: out of the split-screen arm
ARM_TARGET = 0x0420         # the single-player AI arm, past the Price check

#: Measured on this disc, identical in all three COMMON builds. Not used to
#: find anything.
KNOWN_OFFSET = 0x14721D

#: The split-screen arm's own exit, which the previous version of this option
#: retargeted. It must stay stock now, or Trieste builds its operatives twice.
EXIT_SIG = bytes([
    0x3A, 0x24, 0x0A, 0x16,        # ...end of the m_iMemberCount store
    0x1B, 0x45, 0x05, 0x16,        # VirtualFunction(RemoveMember)
    0x1B, 0x45, 0x05, 0x16,        # VirtualFunction(RemoveMember)
    0x0F, 0x01, 0x16, 0x26,        # Let(m_iMemberCount, IntOne())
    0x06, 0x88, 0x06,              # Jump -> 0x0688
])
#: Where its `Jump` opcode sits.
KNOWN_EXIT_OFFSET = 0x147326

#: The AI's own heads, bodies and caps. `LoadMissionRainbowSkins` loads every
#: operative's skins, heads and cap classes unconditionally, then hands them
#: out in a loop -- and in split screen that loop is capped at two members::
#:
#:     0x080a: if (Level.Game.m_bIsSplitScreen)
#:     0x0825:     iMemberCount = 2
#:     0x082d:     goto 0x083b                <-- this jump
#:     0x0830: else iMemberCount = m_iMemberCount
#:     0x083b: for (i = 0; i < iMemberCount; i++) ... skins, head, cap
#:
#: so the AI, members 2 and 3, kept their mesh's built-in materials: Weber's
#: head on the ordinary levels, Price's face on the winter ones. The jump
#: now lands on 0x0830, so split screen counts the real team. It loads
#: nothing: the loop has no DynamicLoadObject and every head, body and cap it
#: hands out was loaded before 0x080a. It needs the count fix above, without
#: which split screen's m_iMemberCount is 1 and player 2 would lose his skin.
SKINS_SIG = bytes([
    0x0F, 0x00, 0x74, 0x19, 0x2C, 0x02,   # iMemberCount = 2
    0x06, 0x3B, 0x08,                     # Jump -> 0x083b     <-- retargeted
    0x0F, 0x00, 0x74, 0x19, 0x01, 0x16,   # iMemberCount = m_iMemberCount
])
SKINS_OPERAND = 7
SKINS_STOCK = 0x3B          # -> 0x083b, the loop
SKINS_FIXED = 0x30          # -> 0x0830, the real count
KNOWN_SKINS_OFFSET = 0x147E13

#: ...and on Trieste, whose rescue arm pins the count to 1 before the skins
#: are handed out (`Let(m_iMemberCount, IntOne())`, mem 0x034d, inside
#: EXIT_SIG), the uncapped loop would skip player 2. That Let becomes
#: EX_Nothing, which leaves `m_iMemberCount` and `1` as two statements that
#: evaluate and discard -- same width on disk and in memory, and the jumps
#: onto 0x034d still land on a statement. `R6GameInfo.CreateRainbowTeam`
#: resets every team's count afterwards, so Trieste's teams end as shipped.
EXIT_LET = 12
EX_LET = 0x0F
EX_NOTHING = 0x0B

#: Player 2 out of the squad.
#:
#: With player 2 created as member 1 and the AI behind him, the squad code --
#: which treats every counted member after index 0 as an AI -- orders player
#: 2 about with them: each follow order reshuffles him among the AI and sends
#: his controller into FollowLeader, a state it does not have, and the AI's
#: wait loop (`bLocked`, R6RainbowAI.FollowLeader 0x05cd) waits for the last
#: member, who could be him. That is "they go where they were told and then
#: hold". Retail split screen keeps player 2 OUTSIDE the counted range
#: ([P1, P2], count 1), so after the skins are handed out this moves him to
#: the end and counts him out: [P1, AI..., P2], count 1 + the AI.
#:
#: The code lives in the rescue cover-spot block at mem 0x0420-0x04d0, which
#: nothing in the split-screen package can reach any more (the jump there,
#: the rescue test's miss above, lands on its first statement, which now
#: jumps straight past it to 0x04d1 exactly as the flag test did). The call to
#: SetSavedData() at 0x06e1 jumps into it::
#:
#:     if (m_bRescureRainbow) m_iMemberCount = 1;               // Trieste as shipped
#:     else if (m_iMemberCount > 1 && m_Team[1].m_bIsPlayer)
#:         { SendMemberToEnd(1); m_iMemberCount--; }
#:     PC.SetSavedData()
#:     return
#:
#: SetSavedData goes LAST, after player 2 has moved. It is the native
#: (0x003B6160) that carries each member's health, stats and ammunition from
#: an A level into its B level, and in split screen it looks at team slots 0
#: and 1 only, reading each as a player or an AI record by who sits there --
#: as does its twin GetSavedData, which wrote them at the end of part A. Part
#: A ends as [P1, AI..., P2], so slot 1 was saved as an AI; restoring BEFORE
#: the move put player 2 in slot 1 and read that AI record as his inventory.
#: He started Alpine Village B with an empty AK-47 and an EMPTY sidearm slot.
#: After the move both sides see the same layout: player 1 and the first AI
#: carry over, and player 2 starts a B level with his normal loadout.
#:
#: Every token is lifted from this package; the balance is dead filler, so
#: both regions keep their disk and memory lengths and ScriptSize is 1775.
LAYOUT_CALL = bytes.fromhex("19004a03030000683216040b")    # SetSavedData(); return
LAYOUT_CALL_NEW = bytes.fromhex("06230400710c0b0b0b0b040b")
LAYOUT_CODE = bytes.fromhex(
    "07d104821900710c0600042d01cb04181d00811919018f05000401a6080004612f214a04161616e7701f322320526573637572655465616d5374617274696e67506f696e7400395600631416161b40031900631405000c018c1607d104771a2501282a160f1a2601281a25191a25012805000801e1030f1a2c0201281a26191a25012805000801e103")
LAYOUT_CODE_NEW = bytes.fromhex(
    "06d104"                                             # 0x0420 Jump -> 0x04d1
    "073f041900710c0600042d01cb04"                       # 0x0423 if (m_bRescureRainbow)
    "0f011626"                                           # 0x0435   m_iMemberCount = 1
    "066e04"                                             # 0x043c   goto 0x046e
    "076e04829701162616181200191a26010a0600042d01b716"   # 0x043f if (count > 1 && m_Team[1].m_bIsPlayer)
    "1b66102616"                                         # 0x0460   SendMemberToEnd(1)
    "a6011616"                                           # 0x0467   m_iMemberCount--
    "19004a03030000683216"                               # 0x046e PC.SetSavedData()
    "0b"                                                 # 0x047a (nothing: see below)
    "040b"                                               # 0x047b return
    "0016" + "00710c" * 7 + "0b" * 44)
#: The EX_Nothing between the call and the return is there so this block
#: never contains LAYOUT_CALL's twelve bytes (`SetSavedData(); return`),
#: which is how the call site at 0x06e1 is found -- two matches and the edit
#: rightly refuses to guess.
#: The previous version of LAYOUT_CODE_NEW, which restored before the move.
#: Never written again; kept so a test can prove the order changed.
LAYOUT_CODE_V1 = bytes.fromhex(
    "06d10419004a03030000683216074a041900710c0600042d01cb040f011626040b077904829701162616181200191a26010a0600042d01b7161b66102616a6011616040b"
    "0016" + "00710c" * 7 + "0b" * 46)
KNOWN_LAYOUT_OFFSETS = (0x1475DD, 0x1473BF)

#: Player 2's "move here" used player 1's aim point: TeamActionRequest read
#: `m_TeamLeader.Controller`. It now reads `actionRequested.aQueryTarget`, the
#: controller that asked -- the form the menu-order path already uses -- so
#: for player 1 nothing changes.
ORDER_AIM = bytes.fromhex("1b7901192e0519014f01050004019405000c017a0e16")
ORDER_AIM_NEW = bytes.fromhex("1b7901192e051900580205000401b305000c017a0e16")
KNOWN_ORDER_OFFSET = 0x145CBF

#: `TeamMemberDead` mem 0x0000-0x00a7, see "When someone dies". The four
#: statements after the gate move down whole. The debug print's bytes become
#: a jump and dead filler.
_DEAD_BODY = bytes.fromhex(
    "1b7a1116"                                  # UpdateEscortList()
    "1b540f16"                                  # UpdateTeamGadgetStatus()
    "0f004f0f393a19004a0a050001012c"            # iMemberId = DeadPawn.m_iID
    "0f1919004a0a050004019405000401a52a")       # DeadPawn.Controller.Enemy = None
DEAD_GATE = (
    bytes.fromhex("071d00" "1919018f05000401a60600042d01ed01" "040b")
    + _DEAD_BODY
    + bytes.fromhex(
        "07a7002d0192e7707070703956171f20205465616d4d656d62657244656164282920"
        "646561645061776e3d00163956004a0a161f20694d656d62657249643d0016395300"
        "4f0f1616"))
DEAD_GATE_NEW = (
    bytes.fromhex("073100" "82"                 # if (Level.Game.m_bIsSplitScreen
                  "1919018f05000401a60600042d01ed01"
                  "181000" "19004a0a0600042d01b7" "16"  # && DeadPawn.m_bIsPlayer)
                  "040b")                       #     return;
    + _DEAD_BODY
    + bytes.fromhex("06a700" "004a0a" + "0b" * 51))
KNOWN_DEAD_GATE_OFFSET = 0x1409BC

#: `R6MObjAcceptableRainbowLosses.PawnKilled` mem 0x0434-0x050a: the jump to
#: "has been incapacitated" (0x0528) unless both players are down.
WIPED_TEST = bytes.fromhex(
    "0728058284721a251919001d05000401d70105001001b62a1618470082771a251919001d"
    "05000401d70105001001b62a1618260081191a251919001d05000401d70105001001b606"
    "00041b091616161618680084721a261919001d05000401d70105001001b62a1618470082"
    "771a261919001d05000401d70105001001b62a1618260081191a261919001d05000401d7"
    "0105001001b60600041b091616161616")
WIPED_TEST_NEW = bytes.fromhex(
    "072805" "82"
    # !R6PlayerController(Killed.Level.m_playerList[0]).m_pawn.IsAlive()
    "8119192e8810" "25" "1919000b050004018f05000001a0" "05000401e901"
    "0600041b091616"
    "183400"
    # && !R6PlayerController(Killed.Level.m_playerList[1]).m_pawn.IsAlive()
    "8119192e8810" "26" "1919000b050004018f05000001a0" "05000401e901"
    "0600041b091616"
    "16"
    "060a05"                                    # -> 0x050a, over the dead bytes
    + "001d" * 5 + "01d701" "01b6" + "0b" * 66)
KNOWN_WIPED_OFFSET = 0x1D6CE2

#: `CreateTeamMember`'s count maintenance, see the notes above.
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

#: The jump target inside COUNT_SIG, which is the one thing about it that
#: moves: `canon_team` re-assembles CreateTeamMember, and the increment it
#: jumps to goes from 0x0ee8 to 0x0eb5. Both are accepted, so this edit
#: finds its site before or after canon's, in either order. A wildcard would
#: not do: the rest of the pattern, `Level.Game != None`, occurs eleven more
#: times in the package.
COUNT_TARGETS = (0x0EE8, 0x0EB5)

#: The operand byte, measured on this disc. Not used to find anything.
KNOWN_COUNT_OFFSET = 0x146BC6


#: With `canon_team` as well, player 2 is created as the mission's own
#: operative on three levels, and the single-player arm would then create the
#: same operative again as AI. Its two removal tests::
#:
#:     0x0586: if (!bTerroHunt && !m_bMissionLoiselle) RemoveMember()
#:     0x0663: if (!bTerroHunt && !m_bMissionWeber)    RemoveMember()
#:
#: are pointed at `m_bMissionPrice` instead -- one byte each, the property's
#: import index inside a compact index of the same width (c3 Weber, c4
#: Loiselle, c5 Price). Price is out exactly on the levels canon changes, so
#: both AI go and the team is the roster; on the all-three levels both stay.
#: No single flag is right on every roster: OLDCITY_A (Price only) keeps both
#: AI. Only emitted when both options are on.
ROSTER_SIGS = {
    # JumpIfNot(next) (!bTerroHunt && !GetMissionDescription().<flag>)
    #     RemoveMember()
    "L": bytes.fromhex("07ab05" "82" "812d00530416" "181000"
                       "81196516160600042d01c40c16" "16" "1b450516"),
    "W": bytes.fromhex("078806" "82" "812d00530416" "181000"
                       "81196516160600042d01c30c16" "16" "1b450516"),
}
ROSTER_FLAG = 23                # the compact index's first byte
ROSTER_STOCK = {"L": 0xC4, "W": 0xC3}
ROSTER_PRICE = 0xC5
KNOWN_ROSTER_OFFSETS = {"L": 0x1474E9, "W": 0x147595}


class SquadError(Exception):
    pass


def _roster_site(plain: bytes, who: str) -> int:
    found = []
    for flag in (ROSTER_STOCK[who], ROSTER_PRICE):
        probe = bytearray(ROSTER_SIGS[who])
        probe[ROSTER_FLAG] = flag
        found += _find_all(plain, bytes(probe))
    if len(found) != 1:
        raise SquadError("expected exactly 1 %s removal test, found %d"
                         % (who, len(found)))
    return found[0] + ROSTER_FLAG


def roster_reads_price(plain: bytes) -> bool:
    """True if both removal tests read the Price flag."""
    return all(plain[_roster_site(plain, w)] == ROSTER_PRICE for w in "LW")


def _find_all(plain: bytes, probe: bytes):
    found = []
    at = plain.find(probe)
    while at >= 0:
        found.append(at)
        at = plain.find(probe, at + 1)
    return found


def _site(plain: bytes) -> int:
    """Offset of RESCUE_SIG, whichever of our two targets the jump holds."""
    found = []
    for target in (SKIP_TARGET, ARM_TARGET):
        probe = bytearray(RESCUE_SIG)
        probe[RESCUE_JUMP + 1] = target & 0xFF
        probe[RESCUE_JUMP + 2] = (target >> 8) & 0xFF
        found += _find_all(plain, bytes(probe))
    if len(found) != 1:
        raise SquadError(
            "expected exactly 1 split-screen rescue test, found %d -- this is "
            "not the build this was measured on, or another edit holds the "
            "jump" % len(found))
    return found[0]


def reads(plain: bytes) -> int:
    """The rescue test's current miss target."""
    at = _site(plain) + RESCUE_JUMP + 1
    return plain[at] | (plain[at + 1] << 8)


def _exit_site(plain: bytes) -> int:
    """Offset of EXIT_SIG, with its count reset as a Let or as Nothing."""
    found = []
    for op in (EX_LET, EX_NOTHING):
        probe = bytearray(EXIT_SIG)
        probe[EXIT_LET] = op
        found += _find_all(plain, bytes(probe))
    if len(found) != 1:
        raise SquadError("expected exactly 1 split-screen arm exit, found %d"
                         % len(found))
    return found[0]


def _exit_is_stock(plain: bytes) -> bool:
    """The exit JUMP is stock (the Let before it may be either form)."""
    try:
        _exit_site(plain)
        return True
    except SquadError:
        return False


def _skins_site(plain: bytes) -> int:
    found = []
    for t in (SKINS_STOCK, SKINS_FIXED):
        probe = bytearray(SKINS_SIG)
        probe[SKINS_OPERAND] = t
        found += _find_all(plain, bytes(probe))
    if len(found) != 1:
        raise SquadError("expected exactly 1 split-screen skin cap, found %d"
                         % len(found))
    return found[0] + SKINS_OPERAND


def _pair_site(plain: bytes, stock: bytes, new: bytes, what: str,
               older=()):
    """(offset, isNew) of one of two same-length forms, unique in the file.

    `older` are earlier versions of `new`. They are found like the other two
    and reported as not new, so an apply rewrites them to the current form
    and a revert puts back stock -- a file edited by a previous version of
    this option is upgraded, never refused and never half-understood."""
    a, b = _find_all(plain, stock), _find_all(plain, new)
    c = [x for form in older for x in _find_all(plain, form)]
    if len(a) + len(b) + len(c) != 1:
        raise SquadError("expected exactly 1 %s, found %d"
                         % (what, len(a) + len(b) + len(c)))
    return (a or b or c)[0], bool(b)


def keeps_player2_out(plain: bytes) -> bool:
    """True if split screen moves player 2 out of the AI squad after skins."""
    return (_pair_site(plain, LAYOUT_CALL, LAYOUT_CALL_NEW, "SetSavedData call")[1]
            and _pair_site(plain, LAYOUT_CODE, LAYOUT_CODE_NEW, "cover-spot block",
                           (LAYOUT_CODE_V1,))[1])


def orders_from_requester(plain: bytes) -> bool:
    return _pair_site(plain, ORDER_AIM, ORDER_AIM_NEW, "order aim")[1]


def buries_dead_ai(plain: bytes) -> bool:
    """True if a dead AI leaves the counted squad in split screen."""
    return _pair_site(plain, DEAD_GATE, DEAD_GATE_NEW, "TeamMemberDead gate")[1]


def fails_on_both_players(plain: bytes) -> bool:
    """True if split screen fails the mission when both players are down."""
    return _pair_site(plain, WIPED_TEST, WIPED_TEST_NEW, "wiped-out test")[1]


def skins_everyone(plain: bytes) -> bool:
    """True if split screen skins the whole team, not just two members."""
    return (plain[_skins_site(plain)] == SKINS_FIXED
            and plain[_exit_site(plain) + EXIT_LET] == EX_NOTHING)


def _count_site(plain: bytes) -> int:
    """Offset of the member-count clamp, whichever operator it holds."""
    found = []
    for op in (COUNT_STOCK, COUNT_FIXED):
        for target in COUNT_TARGETS:
            probe = bytearray(COUNT_SIG)
            probe[COUNT_OPERAND] = op
            probe[1] = target & 0xFF
            probe[2] = (target >> 8) & 0xFF
            found += _find_all(plain, bytes(probe))
    if len(found) != 1:
        raise SquadError(
            "expected exactly 1 member-count clamp, found %d -- this is not "
            "the build this was measured on" % len(found))
    return found[0]


def counts(plain: bytes) -> bool:
    """True if split screen increments the member count instead of pinning it."""
    return plain[_count_site(plain) + COUNT_OPERAND] == COUNT_FIXED


def apply(plain: bytes, enable: bool = True, canon: bool = False):
    """Both halves. Returns (bytes, changed). Length never moves.

    `canon` also points the two removal tests at Price -- see ROSTER_SIGS --
    and first applies `rsecanon` itself, because canon LIFTS those two tests
    into its own code and must see them before they are rewritten. It is
    idempotent, so the canon card's own edit running afterwards is a no-op;
    and it refuses rather than lift a rewritten test, so running before it
    cannot be silently wrong.

    They are deliberately not separable: the jump without the count writes
    both operatives over player 2, and the count without the jump does
    nothing anyone can see. Neither ships without the recordings either --
    that is the card's job, not this function's.
    """
    pre = 0
    if enable and canon:
        from . import rsecanon
        plain, pre = rsecanon.apply(plain, True)
    at = _site(plain)
    cat = _count_site(plain)
    if not _exit_is_stock(plain):
        raise SquadError(
            "the split-screen arm's exit jump is not stock -- a file carrying "
            "the previous version of this edit would build Trieste's "
            "operatives twice")

    out = bytearray(plain)
    changed = 0
    want = ARM_TARGET if enable else SKIP_TARGET
    if reads(plain) != want:
        out[at + RESCUE_JUMP + 1] = want & 0xFF
        out[at + RESCUE_JUMP + 2] = (want >> 8) & 0xFF
        changed += 1

    cwant = COUNT_FIXED if enable else COUNT_STOCK
    if plain[cat + COUNT_OPERAND] != cwant:
        out[cat + COUNT_OPERAND] = cwant
        changed += 1

    sat = _skins_site(plain)
    swant = SKINS_FIXED if enable else SKINS_STOCK
    if plain[sat] != swant:
        out[sat] = swant
        changed += 1
    lat = _exit_site(plain) + EXIT_LET
    lwant = EX_NOTHING if enable else EX_LET
    if plain[lat] != lwant:
        out[lat] = lwant
        changed += 1

    for stock, new, what, older in (
            (LAYOUT_CALL, LAYOUT_CALL_NEW, "SetSavedData call", ()),
            (LAYOUT_CODE, LAYOUT_CODE_NEW, "cover-spot block", (LAYOUT_CODE_V1,)),
            (ORDER_AIM, ORDER_AIM_NEW, "order aim", ()),
            (DEAD_GATE, DEAD_GATE_NEW, "TeamMemberDead gate", ()),
            (WIPED_TEST, WIPED_TEST_NEW, "wiped-out test", ())):
        at_pair, _is_new = _pair_site(plain, stock, new, what, older)
        # Compared with the form wanted, not with "is it new": an older
        # version is neither stock nor new and has to be rewritten either way.
        want_bytes = new if enable else stock
        if plain[at_pair:at_pair + len(stock)] != want_bytes:
            out[at_pair:at_pair + len(stock)] = want_bytes
            changed += 1

    for who in "LW":
        at_flag = _roster_site(plain, who)
        fwant = ROSTER_PRICE if (enable and canon) else ROSTER_STOCK[who]
        if plain[at_flag] != fwant:
            out[at_flag] = fwant
            changed += 1

    if len(out) != len(plain):
        raise SquadError("the squad edit changed the file length")
    return bytes(out), changed + pre


HELP = ("Split screen builds player 2 and then skips the code that creates the "
        "AI operatives. This sends it through the same code single player "
        "uses, so the two players are joined by Loiselle and Weber -- or "
        "whichever of them the mission's own roster includes -- and swaps in "
        "split-screen level files that contain the operatives, which is what "
        "every earlier attempt was missing.")

CAUTION = (
    "Watched working on 2026-09-22, on Alpine Village and on a non-winter "
    "mission: Loiselle and Weber spawn as AI, both players can command them, "
    "and their name tags are right. That first test found two faults; both "
    "are fixed, and the fixes were watched working on Alpine Village the "
    "same night:\n\n"
    "- They wore Price's or Weber's default look. Split screen hands out "
    "skins, heads and caps to only two team members; it now does the whole "
    "team, so each wears his own head, the mission's camouflage and his cap. "
    "Nothing new is loaded -- everything they wear was already in memory.\n"
    "- They went where they were told and then held. Player 2 was counted "
    "inside the AI squad, so orders shuffled him in among them and the AI "
    "waited for him. He is now kept outside it, as retail split screen does, "
    "so the AI follow player 1 in single file; and player 2's own 'move "
    "here' uses his own aim.\n\n"
    "Deaths (not yet watched in game): the mission fails once both players "
    "are down, whether or not an AI still lives -- the split-screen rule "
    "looked at team slot 1, which is now an AI. A dead AI now leaves the "
    "squad as in single player; before, it stayed counted, and a death on a "
    "ladder left the team 'CLIMBING LADDER' and refusing orders from both "
    "players. Known limit: if player 1 dies the AI keep following his "
    "position.\n\n"
    "Why it works where six earlier attempts did not:\n\n"
    "Every one of them wedged the load for the same reason, whatever code it "
    "patched: a split-screen level file is a RECORDING of what one boot read, "
    "and that boot never created the operatives. When the team code asks for "
    "Loiselle's class, the engine reads the next recorded bytes as that class "
    "and falls out of step. Island's wedged savestate still holds the "
    "engine's own error, with the byte size of Weber's class in it.\n\n"
    "So this also REPLACES each map's split-screen level file with the single "
    "player one plus the 105 bytes only split screen reads. That is exactly "
    "how Trieste's split-screen file relates to its single-player file on the "
    "retail disc -- and Trieste is the one map where split screen already "
    "builds the operatives and plays. Every replacement is proved byte for "
    "byte before it is written, and each fits its own slot on the disc.\n\n"
    "Every mission is covered; Trieste needs nothing. The four winter levels "
    "-- Alpine Village and Mountain Highway, A and B -- are the least certain: "
    "their single-player files also read one texture in a different order, "
    "and there is no winter Trieste to prove what split screen then reads. "
    "The order was worked out from an exact accounting of every byte instead. "
    "If one of them hangs, save a state -- the engine keeps its own error.\n\n"
    "Not yet known: whether the AI follow player 1 or player 2, and whether "
    "they wear the mission's camouflage (split screen only loads two sets of "
    "skins).\n\n"
    "Single player and online are untouched. RESTORE DISC puts every file "
    "back.")


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_squad", "AI teammates in split screen",
        BOOL, False, group, confidence="verified", touches="data",
        help=HELP, caution=CAUTION)

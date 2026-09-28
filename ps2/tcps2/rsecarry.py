"""Split screen's part A -> part B carry-over, by player rather than by slot.

Reported 2026-09-24: Ding died in part A of a Terrorist Hunt map, Eddie
finished it, and in part B Ding came back with Eddie's ammo and health while
Eddie got a free refill.

How the carry-over works
------------------------

Two natives, both in the overlay:

* `GetSavedData` (native 0x833 -> 0x003B6BB0) SAVES. Its only caller is the
  in-game menu's Continue handler (0x56C97C), which passes player 1's
  controller; both split-screen players share the one team object. It appends
  floats to a list in the game manager (`*(0x0065500C)+0x54`): a 1.0, then a
  record per team slot -- operative id, wounds left, kills, shots, hits, and
  for a player the current weapon plus 4 x 28 floats of ammunition (118 floats;
  an AI's is 5). In split screen it writes exactly two, for slots 0 and 1, in
  slot order. Wounds of 0 means dead.
* `SetSavedData` (native 0x832 -> 0x003B6160) RESTORES, called from
  `CreatePlayerTeam` at every level start. In split screen it visits slots 0
  and 1 and hands players their records BY POSITION -- the saved operative id
  is never checked. It works in two stages (measured 2026-09-24): a record
  loop writes every record -- wounds, kills, shots, hits, weapon, ammunition;
  a zero-wound record also sets the health state to dead -- and raises only
  `GetMaximumWounds`, `SetWoundedHealthState` and `SwitchWeapon`. Then a
  closing pass visits the same slots: for a pawn with no wounds it hides the
  body, raises `GotoDeadState` and then `R6RainbowTeam.UpdateTeamStatus`,
  which calls `TeamMemberDead` -- and that, in split screen, hands the lead
  over when the dead pawn led (`rsesquad`). All synchronous. The closing pass
  runs only when `NetMode` is 0, as it is in split screen.

Why Ding got Eddie's
--------------------

`rsesquad`'s lead hand-off swaps slot 0 with the other player's slot
(`m_iMemberCount + m_iMembersLost`) when the leader dies. So at the end of A the
team was [Eddie, AI, AI, Ding(dead)] and the save wrote Eddie's record, then an
AI's; Ding's was never saved. At the start of B, after the layout block moves
player 2 to the end, the team is [Ding, AI, AI, Eddie]: slot 0 -- Ding -- took
the first player record, Eddie's, and Eddie's slot was never visited.

What this does
--------------

70 words inside the two natives, no code cave:

* Save: in split screen, player 1's record first and player 2's second,
  whichever of them holds slot 0 (player 1 is operative 0, Chavez; measured in
  five savestates on four maps). If the other player's slot is empty or holds
  an AI, the shipped behaviour is kept. The new code uses two provably dead
  six-word runs inside `GetSavedData` (reachable only through a `bltz` that
  follows an `lbu`) and drops an unused `Cast` call.
* Restore: in split screen, the second record goes to the slot
  `m_iMemberCount + m_iMembersLost` -- player 2's after the layout block's move,
  and slot 1 on maps with no AI, which is the shipped behaviour. A player who
  died in A starts B DEAD, the shipped dead path, for continuity (the user's
  call, 2026-09-24; the first version started him fresh).
* Closing pass: in split screen it visits slot k (`m_iMemberCount +
  m_iMembersLost`, player 2's) FIRST and slot 0 LAST, where shipped it visits
  slots 0 and 1. Shipped, with AI teammates player 2's slot was never visited
  -- a dead player 2 had dead health but never entered the dead state, stayed
  visible and stayed on the radar -- and without AI player 1's hand-off swap
  moved him into slot 1 and his death was processed twice. Last, player 1's
  hand-off can only happen after everyone else is done. Single player keeps
  its order: the prologue stores k's offset at `sp+0xA8`, 0 in single player.
  Room: the patched HUD loop compacted by three words, and the pass's float
  wounds test (`cvt.s.w` + `c.ole.s` + `bc1f`) became `lw` + `bgtz`, the same
  answer for every 32-bit value. Those seven words (0x3B69E8-0x3B69FC,
  0x3B6A04) were live; nothing else in the pass was free.

It relies on `SetSavedData` running AFTER the layout block's
`SendMemberToEnd(1); m_iMemberCount--`, which is how `rsesquad` has done it
since 2026-09-23 -- so it ships with `split_squad` and only with it.

Behaviour this changes: player 2 now keeps his own state; the AI teammates
start part B fresh (one AI in slot 1 used to carry over); a player who died in
A starts B dead, and with `split_down_callouts` his death is called out once
as part B starts.

Checked by running the stock and patched words through an interpreter with
mock teams and the script events modelled from the disc bytecode: 22
split-screen part A -> part B cases (player 1 dead after the hand-off, player
2 dead, both dead in either order, both alive in the retail and AI layouts,
the no-AI and canon maps, one AI, all AI dead) pass, where the shipped words
pass 3 and the first version 9; single player byte-identical to the shipped
words in 48 runs, a dead player-1 record included; randomised registers and
stack; real-RAM round trips on three savestates; no collision in 79 option
combinations. Harness: tcms-research/scratch-2026-09-25/carry_dead/run_all.py.
Not yet played.
"""

from __future__ import annotations

#: (va, stock word, new word, note). Stock words verified against the shipped
#: overlay by the suite.
WORDS = (
    (0x003B6198, 0x00031EBC, 0x30630020, 'restore: andi $v1, $v1, 0x20'),
    (0x003B619C, 0x00031FFE, 0x0080A02D, 'restore: move $s4, $a0'),
    (0x003B61A0, 0x10600003, 0x8C8D078C, 'restore: lw $t5, 0x78c($a0)'),
    (0x003B61A4, 0x0080A02D, 0x8DBE037C, 'restore: lw $fp, 0x37c($t5)'),
    (0x003B61A8, 0x10000004, 0x8DA9039C, 'restore: lw $t1, 0x39c($t5)'),
    (0x003B61AC, 0x241E0002, 0x03C94821, 'restore: addu $t1, $fp, $t1'),
    (0x003B61B0, 0x8E83078C, 0x00094880, 'restore: sll $t1, $t1, 2'),
    (0x003B61B4, 0x8C7E037C, 0x01A95821, 'restore: addu $t3, $t5, $t1'),
    (0x003B61B8, 0x00000000, 0x8D6B03C0, 'restore: lw $t3, 0x3c0($t3)'),
    (0x003B61BC, 0x8E86057C, 0x240A0004, 'restore: addiu $t2, $zero, 4'),
    (0x003B61C0, 0x001E082A, 0x014B480A, 'restore: movz $t1, $t2, $t3'),
    (0x003B61C4, 0x10200012, 0x0123500B, 'restore: movn $t2, $t1, $v1'),
    (0x003B61C8, 0x0000382D, 0xAFAA00A4, 'restore: sw $t2, 0xa4($sp)'),
    (0x003B61CC, 0x0000402D, 0x0003480A, 'restore: movz $t1, $zero, $v1'),
    (0x003B61D0, 0x2404FFFF, 0xAFA900A8, 'restore: sw $t1, 0xa8($sp)'),
    (0x003B61D4, 0x8E83078C, 0x00035902, 'restore: srl $t3, $v1, 4'),
    (0x003B61D8, 0x00681821, 0x0163F00B, 'restore: movn $fp, $t3, $v1'),
    (0x003B61DC, 0x8C6303C4, 0x8E86057C, 'restore: lw $a2, 0x57c($s4)'),
    (0x003B61E0, 0x10600005, 0x001E7080, 'restore: sll $t6, $fp, 2'),
    (0x003B61E4, 0x00000000, 0x1BC0000A, 'restore: blez $fp, 0x3b6210'),
    (0x003B61E8, 0x8C65094C, 0x00CE7021, 'restore: addu $t6, $a2, $t6'),
    (0x003B61EC, 0x00C81821, 0x8DA303C4, 'restore: lw $v1, 0x3c4($t5)'),
    (0x003B61F0, 0x10000003, 0x2405FFFF, 'restore: addiu $a1, $zero, -1'),
    (0x003B61F4, 0xAC650484, 0x10600002, 'restore: beqz $v1, 0x3b6200'),
    (0x003B61F8, 0x00C81821, 0x25AD0004, 'restore: addiu $t5, $t5, 4'),
    (0x003B61FC, 0xAC640484, 0x8C65094C, 'restore: lw $a1, 0x94c($v1)'),
    (0x003B6200, 0x24E70001, 0x24C60004, 'restore: addiu $a2, $a2, 4'),
    (0x003B6204, 0x00FE182A, 0x14CEFFF9, 'restore: bne $a2, $t6, 0x3b61ec'),
    (0x003B6208, 0x1460FFF2, 0xACC50480, 'restore: sw $a1, 0x480($a2)'),
    (0x003B620C, 0x25080004, 0x00000000, 'restore: nop'),
    (0x003B69A8, 0x8FA300A0, 0x8FA400A4, 'restore: lw $a0, 0xa4($sp)'),
    (0x003B69B4, 0x26730004, 0x02649821, 'restore: addu $s3, $s3, $a0'),
    (0x003B69E8, 0x00901821, 0x8FA800A8, 'restore: lw $t0, 0xa8($sp)'),
    (0x003B69EC, 0x8C6303C0, 0x0008800B, 'restore: movn $s0, $zero, $t0'),
    (0x003B69F0, 0x44800000, 0x0112800A, 'restore: movz $s0, $t0, $s2'),
    (0x003B69F4, 0xC4610630, 0x00901821, 'restore: addu $v1, $a0, $s0'),
    (0x003B69F8, 0x46800860, 0x8C6303C0, 'restore: lw $v1, 0x3c0($v1)'),
    (0x003B69FC, 0x46000836, 0x8C690630, 'restore: lw $t1, 0x630($v1)'),
    (0x003B6A04, 0x4500003C, 0x1D20003C, 'restore: bgtz $t1, 0x3b6af8'),
    (0x003B6C18, 0x000216BC, 0x30420020, 'save: andi $v0, $v0, 0x20'),
    (0x003B6C1C, 0x000217FE, 0x8E48078C, 'save: lw $t0, 0x78c($s2)'),
    (0x003B6C20, 0x10400003, 0x8D09037C, 'save: lw $t1, 0x37c($t0)'),
    (0x003B6C24, 0x24170002, 0x8D0A039C, 'save: lw $t2, 0x39c($t0)'),
    (0x003B6C28, 0x10000006, 0x012AB821, 'save: addu $s7, $t1, $t2'),
    (0x003B6C2C, 0x8C8205B0, 0x0000882D, 'save: move $s1, $zero'),
    (0x003B6C30, 0x8E42078C, 0x24190004, 'save: addiu $t9, $zero, 4'),
    (0x003B6C34, 0x8C43037C, 0x10400005, 'save: beqz $v0, 0x3b6c4c'),
    (0x003B6C38, 0x8C42039C, 0x00174880, 'save: sll $t1, $s7, 2'),
    (0x003B6C3C, 0x0062B821, 0x01095821, 'save: addu $t3, $t0, $t1'),
    (0x003B6C40, 0x8C8205B0, 0x8D6C03C0, 'save: lw $t4, 0x3c0($t3)'),
    (0x003B6C44, 0x0C0E4704, 0x158000CB, 'save: bnez $t4, 0x3b6f74'),
    (0x003B6C48, 0x8C440000, 0x24170002, 'save: addiu $s7, $zero, 2'),
    (0x003B6C4C, 0x0017082A, 0xAFB90004, 'save: sw $t9, 4($sp)'),
    (0x003B6C50, 0x10200121, 0x0017082A, 'save: slt $at, $zero, $s7'),
    (0x003B6C54, 0x0000B02D, 0x10200120, 'save: beqz $at, 0x3b70d8'),
    (0x003B6C58, 0x0000882D, 0x0000B02D, 'save: move $s6, $zero'),
    (0x003B6E6C, 0x30420001, 0x0009C823, 'save: negu $t9, $t1'),
    (0x003B6E70, 0x00621825, 0x0138C80A, 'save: movz $t9, $t1, $t8'),
    (0x003B6E74, 0x44830000, 0x1000FF75, 'save: b 0x3b6c4c'),
    (0x003B6E78, 0x00000000, 0x0138880B, 'save: movn $s1, $t1, $t8'),
    (0x003B6F74, 0x30420001, 0x918F03BE, 'save: lbu $t7, 0x3be($t4)'),
    (0x003B6F78, 0x00621825, 0x31EF0001, 'save: andi $t7, $t7, 1'),
    (0x003B6F7C, 0x44830000, 0x11E0FF33, 'save: beqz $t7, 0x3b6c4c'),
    (0x003B6F80, 0x00000000, 0x8D0D03C0, 'save: lw $t5, 0x3c0($t0)'),
    (0x003B6F84, 0x46800520, 0x1000FFB9, 'save: b 0x3b6e6c'),
    (0x003B6F88, 0x4614A500, 0x8DB8094C, 'save: lw $t8, 0x94c($t5)'),
    (0x003B70C8, 0x26D60001, 0x8FA30004, 'save: lw $v1, 4($sp)'),
    (0x003B70CC, 0x02D7182A, 0x26D60001, 'save: addiu $s6, $s6, 1'),
    (0x003B70D0, 0x1460FEE2, 0x16D7FEE2, 'save: bne $s6, $s7, 0x3b6c5c'),
    (0x003B70D4, 0x26310004, 0x02238821, 'save: addu $s1, $s1, $v1'),
)


def words():
    """[(va, word, stockWord, note)] for build_edits."""
    return [(va, new, stock, "carry-over: " + note)
            for va, stock, new, note in WORDS]


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_carry",
        "Split screen: part B gives each player his own ammo and health",
        BOOL, False, group, confidence="experimental", touches="words",
        requires={prefix + "split_squad": [True]},
        help="A two-part mission carries the team's ammunition and health from "
             "part A into part B. Split screen does it by team slot, not by "
             "player, and the lead hand-off moves players between slots -- so "
             "if player 1 died and player 2 finished part A, player 1 started "
             "part B with player 2's gear and player 2 got a free refill. This "
             "carries each player's own state; a player who died in part A "
             "stays dead in part B, and the other player leads.",
        caution="Not yet played. 70 words of the game's own save and restore "
                "code; checked in an emulator against every team layout, not "
                "in the game. The AI teammates start part B fresh. The restore "
                "runs at every level start, so if levels stop loading, turn "
                "this off first.")

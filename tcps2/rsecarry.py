"""Split screen's part A -> part B carry-over: by player, and the dead stay dead.

Reported 2026-09-24: Ding died in part A of a Terrorist Hunt map, Eddie
finished it, and in part B Ding came back with Eddie's ammo and health while
Eddie got a free refill. Reported again 2026-10-10, against the first fix for
that: AI teammates killed in part A were alive again in part B.

The second report is the one that shaped this module. A teammate who died in
part A should be dead in part B; the first version made the AI start fresh
because it spent both of split screen's two saved records on the two players,
leaving no room for an AI record at all.

How the carry-over works
------------------------

Two natives, both in the overlay:

* `GetSavedData` (native 0x833 -> 0x003B6BB0) SAVES. Its only caller is the
  in-game menu's Continue handler (0x56C97C), which passes player 1's
  controller; both split-screen players share the one team object. It appends
  floats to a list in the game manager (`*(0x0065500C)+0x54`): a 1.0, then a
  record per team slot -- operative id, wounds left, kills, shots, hits, and
  for a player the current weapon plus 4 x 28 floats of ammunition (118
  floats; an AI's is 5). Wounds of 0 means dead.
* `SetSavedData` (native 0x832 -> 0x003B6160) RESTORES, called from
  `CreatePlayerTeam` at every level start. It works in two stages: a record
  loop writes wounds, kills, shots, hits, weapon and ammunition, and a closing
  pass hides the body of a pawn with no wounds, raises `GotoDeadState` and
  then `R6RainbowTeam.UpdateTeamStatus` -> `TeamMemberDead`.

TWO THINGS THE FIRST INVESTIGATION GOT WRONG
--------------------------------------------

**The "exactly two records in split screen" is not a structural limit.** It is
a plain immediate -- `addiu $s7, $zero, 2` -- and `$s7` is touched at six
instructions in the whole function, all of them the loop's own bookkeeping.
The destination is not a fixed buffer either: `TArray::Add` reallocs without
bound. The single-player arm already runs the same loop for `m_iMemberCount +
m_iMembersLost` records. So there was never a reason the AI could not be
saved.

**The restore does NOT hand every record out by position.** That is true of
the player arm only. The AI arm is a search loop that compares the record's
first float against the pawn's own operative id at +0x94C and skips on a
mismatch, so an AI record lands on the right teammate however part B happens
to order the slots. A roster that differs between parts degrades to "that AI
starts fresh", not to corruption.

What this does
--------------

73 words inside the two natives. **No code cave** -- `rsedeadpath`'s region is
a fixed named-slot map with only 25 free words in runs of 10, 10 and 5, and
nothing here goes near it.

* Save: the bound becomes `k = m_iMemberCount + m_iMembersLost`, so the list
  is player 1, then every AI, then player 2. If the lead hand-off has moved
  player 2 into slot 0 the walk runs in reverse, which puts player 1's record
  first either way and reverses the AI among themselves -- which the id search
  makes irrelevant.
* Restore: the AI records are found where they always were, at float 119,
  because slot 0 is always one of the two players. Player 2's record is read
  at `list.num - 118` rather than computed from the AI count, so it is exact
  for every roster.
* Closing pass: it walks DOWNWARD, slot k first and slot 0 last. Upward is
  wrong and was wrong before: with two dead AI the guard at 0x3B69DC fires
  early and the second one never enters the dead state -- a standing corpse.
  Simulated under both plausible shapes of `TeamMemberDead`'s compaction,
  downward is correct in all five death patterns and upward in none.

The old `m_bIsPlayer` test is gone from both sides, which is a correctness win
rather than a saving. The first version tested `m_Team[k] != 0 && m_bIsPlayer`
on the save and only `m_Team[k] != 0` on the restore, and that asymmetry meant
a save that fell back to two records was read back as though it held two
player records -- a 113-float out-of-bounds read of wild weapon and ammunition
values. With both sides testing the identical condition they cannot disagree.
No AI carries operative id 0, so slot 0 is still identified without the flag.

It relies on `SetSavedData` running AFTER the layout block's
`SendMemberToEnd(1); m_iMemberCount--`, which is how `rsesquad` has done it
since 2026-09-23 -- so it ships with `split_squad` and only with it.

Why there is no cheaper version
-------------------------------

Two words would do it -- make both split-screen arms fall through to the
single-player arms -- and it is not enough. With ONE dead teammate it works.
With TWO it leaves the second alive, because that needs the downward closing
walk, which needs the split flag and the two stack words, which needs the
prologue rework. The nine two-AI missions include Alpine, Oil Refinery and
Mountain Highway, which is exactly where the fault was reported. It also
regresses player 2 below the shipped behaviour on the no-AI maps. So the full
73 words are the floor.

NOT YET PLAYED. Checked by running the stock and patched words through an
interpreter with mock teams and the script events modelled from the disc
bytecode: 168 of 168 reachable split-screen part A -> part B cases pass, where
the shipped words pass 34 and the first version 96 -- and every one of that
version's 72 failures is "an AI died in part A and is alive in part B", the
reported fault, reproduced. Scored per criterion the patch is 50/50 on the
dead-stay-dead rule and 50/50 on player 2 keeping his own state, against stock
36/4 and the first version 32/50. Single player is byte-identical to the
shipped words in both the saved float list and the restored effect, over every
roster and death combination. Zero out-of-list reads across 324 combinations;
a whole-image branch scan finds nothing branching into any rewritten run.

"""

from __future__ import annotations

#: (va, stock word, new word, note). Every stock word was read back
#: from the pristine SP.SOZ before it was written here: 73 of 73,
#: zero mismatches. Nothing is in the shared code cave.
WORDS = (
    (0x003B6198, 0x00031EBC, 0x00031E80,
     "setup: sll $v1,$v1,26   (bit5 -> bit31)"),
    (0x003B619C, 0x00031FFE, 0x00031FC3,
     "setup: sra $v1,$v1,31   (-1 split / 0 single)"),
    (0x003B61A0, 0x10600003, 0x0080A02D,
     "setup: move $s4,$a0"),
    (0x003B61A4, 0x0080A02D, 0x8C8D078C,
     "setup: lw $t5,0x78c($a0)   team"),
    (0x003B61A8, 0x10000004, 0x8DBE037C,
     "setup: lw $fp,0x37c($t5)   m_iMemberCount"),
    (0x003B61AC, 0x241E0002, 0x8DA9039C,
     "setup: lw $t1,0x39c($t5)   m_iMembersLost"),
    (0x003B61B0, 0x8E83078C, 0x03C94821,
     "setup: addu $t1,$fp,$t1    k"),
    (0x003B61B4, 0x8C7E037C, 0x00095080,
     "setup: sll $t2,$t1,2       4k"),
    (0x003B61B8, 0x00000000, 0x01AA5021,
     "setup: addu $t2,$t5,$t2"),
    (0x003B61BC, 0x8E86057C, 0x8D4B03C0,
     "setup: lw $t3,0x3c0($t2)   m_Team[k]"),
    (0x003B61C0, 0x001E082A, 0x252C0001,
     "setup: addiu $t4,$t1,1     k+1"),
    (0x003B61C4, 0x10200012, 0x012B600A,
     "setup: movz $t4,$t1,$t3    empty slot -> k"),
    (0x003B61C8, 0x0000382D, 0x0183F00B,
     "setup: movn $fp,$t4,$v1    split -> that"),
    (0x003B61CC, 0x0000402D, 0x27CFFFFF,
     "setup: addiu $t7,$fp,-1"),
    (0x003B61D0, 0x2404FFFF, 0x0003780A,
     "setup: movz $t7,$zero,$v1  single -> 0"),
    (0x003B61D4, 0x8E83078C, 0xAFAF00B4,
     "setup: sw $t7,0xb4($sp)    closing start"),
    (0x003B61D8, 0x00681821, 0x346E0001,
     "setup: ori $t6,$v1,1       -1 split / +1 single"),
    (0x003B61DC, 0x8C6303C4, 0xAFAE00B8,
     "setup: sw $t6,0xb8($sp)    closing step"),
    (0x003B61E0, 0x10600005, 0x8E86057C,
     "prepass: lw $a2,0x57c($s4)"),
    (0x003B61E4, 0x00000000, 0x001E7080,
     "prepass: sll $t6,$fp,2"),
    (0x003B61E8, 0x8C65094C, 0x1BC00009,
     "prepass: blez $fp,0x3b6210"),
    (0x003B61EC, 0x00C81821, 0x00CE7021,
     "prepass: addu $t6,$a2,$t6   end"),
    (0x003B61F0, 0x10000003, 0x8DA303C4,
     "prepass: LOOP lw $v1,0x3c4($t5)"),
    (0x003B61F4, 0xAC650484, 0x2405FFFF,
     "prepass: li $a1,-1"),
    (0x003B61F8, 0x00C81821, 0x10600002,
     "prepass: beqz $v1,0x3b6204"),
    (0x003B61FC, 0xAC640484, 0x25AD0004,
     "prepass: addiu $t5,$t5,4 (delay)"),
    (0x003B6200, 0x24E70001, 0x8C65094C,
     "prepass: lw $a1,0x94c($v1)"),
    (0x003B6204, 0x00FE182A, 0x24C60004,
     "prepass: addiu $a2,$a2,4"),
    (0x003B6208, 0x1460FFF2, 0x14CEFFF9,
     "prepass: bne $a2,$t6,LOOP"),
    (0x003B620C, 0x25080004, 0xACC50480,
     "prepass: sw $a1,0x480($a2) (delay)"),
    (0x003B6990, 0x8FA300B0, 0x8F83991C,
     "tail: lw $v1,-26340($gp)"),
    (0x003B6994, 0x24630076, 0x8C630058,
     "tail: lw $v1,0x58($v1)   list.num"),
    (0x003B6998, 0xAFA300B0, 0x2463FF89,
     "tail: addiu $v1,$v1,-119"),
    (0x003B699C, 0x8FA300A0, 0xAFA300B0,
     "tail: sw $v1,0xb0($sp)   cursor"),
    (0x003B69A0, 0x24630001, 0x8FA300A0,
     "tail: lw $v1,0xa0($sp)"),
    (0x003B69A4, 0xAFA300A0, 0x24630001,
     "tail: addiu $v1,$v1,1"),
    (0x003B69A8, 0x8FA300A0, 0xAFA300A0,
     "tail: sw $v1,0xa0($sp)"),
    (0x003B69CC, 0x0000902D, 0x8FB200B4,
     "closing: lw $s2,0xb4($sp)  start"),
    (0x003B6A08, 0x00000000, 0x8FB700B8,
     "closing: lw $s7,0xb8($sp)  step"),
    (0x003B6AF8, 0x26520001, 0x02579021,
     "closing: addu $s2,$s2,$s7"),
    (0x003B6AFC, 0x025E182A, 0x025E182B,
     "closing: sltu $v1,$s2,$fp  stops at -1"),
    (0x003B6C18, 0x000216BC, 0x30420020,
     "save: andi $v0,$v0,0x20"),
    (0x003B6C1C, 0x000217FE, 0x8E48078C,
     "save: lw $t0,0x78c($s2)"),
    (0x003B6C20, 0x10400003, 0x8D09037C,
     "save: lw $t1,0x37c($t0)"),
    (0x003B6C24, 0x24170002, 0x8D0A039C,
     "save: lw $t2,0x39c($t0)"),
    (0x003B6C28, 0x10000006, 0x012AB821,
     "save: addu $s7,$t1,$t2   $s7 = k"),
    (0x003B6C2C, 0x8C8205B0, 0x0000882D,
     "save: move $s1,$zero"),
    (0x003B6C30, 0x8E42078C, 0x24190004,
     "save: li $t9,4"),
    (0x003B6C34, 0x8C43037C, 0x10400005,
     "save: beqz $v0,0x3b6c4c"),
    (0x003B6C38, 0x8C42039C, 0x00174880,
     "save: sll $t1,$s7,2"),
    (0x003B6C3C, 0x0062B821, 0x01095821,
     "save: addu $t3,$t0,$t1"),
    (0x003B6C40, 0x8C8205B0, 0x8D6C03C0,
     "save: lw $t4,0x3c0($t3)  m_Team[k]"),
    (0x003B6C44, 0x0C0E4704, 0x15800089,
     "save: bnez $t4,0x3b6e6c"),
    (0x003B6C48, 0x8C440000, 0x00000000,
     "save: nop (delay; fallback keeps $s7=k)"),
    (0x003B6C4C, 0x0017082A, 0xAFB90004,
     "save: sw $t9,4($sp)  stride"),
    (0x003B6C50, 0x10200121, 0x0017082A,
     "save: slt $at,$zero,$s7"),
    (0x003B6C54, 0x0000B02D, 0x10200120,
     "save: beqz $at,0x3b70d8"),
    (0x003B6C58, 0x0000882D, 0x0000B02D,
     "save: move $s6,$zero"),
    (0x003B6E6C, 0x30420001, 0x8D0D03C0,
     "save: lw $t5,0x3c0($t0)   m_Team[0]"),
    (0x003B6E70, 0x00621825, 0x26F70001,
     "save: addiu $s7,$s7,1     bound k+1"),
    (0x003B6E74, 0x44830000, 0x8DB8094C,
     "save: lw $t8,0x94c($t5)   opid(slot 0)"),
    (0x003B6E78, 0x00000000, 0x00195023,
     "save: negu $t2,$t9        -4"),
    (0x003B6E7C, 0x46800520, 0x1000003D,
     "save: b 0x3b6f74"),
    (0x003B6E80, 0x4614A500, 0x0158C80B,
     "save: movn $t9,$t2,$t8 (delay) stride -4"),
    (0x003B6F74, 0x30420001, 0x0138880B,
     "save: movn $s1,$t1,$t8    start 4k"),
    (0x003B6F78, 0x00621825, 0x1000FF34,
     "save: b 0x3b6c4c"),
    (0x003B6F7C, 0x44830000, 0x00000000,
     "save: nop (delay)"),
    (0x003B6F84, 0x46800520, 0x00000000,
     "save: nop (spare dead word)"),
    (0x003B6F88, 0x4614A500, 0x00000000,
     "save: nop (spare dead word)"),
    (0x003B70C8, 0x26D60001, 0x8FA30004,
     "save: lw $v1,4($sp)"),
    (0x003B70CC, 0x02D7182A, 0x26D60001,
     "save: addiu $s6,$s6,1"),
    (0x003B70D0, 0x1460FEE2, 0x16D7FEE2,
     "save: bne $s6,$s7,loop"),
    (0x003B70D4, 0x26310004, 0x02238821,
     "save: addu $s1,$s1,$v1"),
)

#: Words the FIRST version of this patch wrote that this one does not.
#: They are emitted with the shipped value so a disc carrying that
#: version is healed rather than left half-patched; on a clean disc
#: each one is a no-op.
REPAIR = (
    (0x003B69B4, 0x26730004,
     "repair: put back the word the first version took"),
    (0x003B69E8, 0x00901821,
     "repair: put back the word the first version took"),
    (0x003B69EC, 0x8C6303C0,
     "repair: put back the word the first version took"),
    (0x003B69F0, 0x44800000,
     "repair: put back the word the first version took"),
    (0x003B69F4, 0xC4610630,
     "repair: put back the word the first version took"),
    (0x003B69F8, 0x46800860,
     "repair: put back the word the first version took"),
    (0x003B69FC, 0x46000836,
     "repair: put back the word the first version took"),
    (0x003B6A04, 0x4500003C,
     "repair: put back the word the first version took"),
    (0x003B6F80, 0x00000000,
     "repair: put back the word the first version took"),
)


def words():
    """[(va, word, stockWord, note)] for build_edits."""
    out = [(va, new, stock, "carry-over: " + note)
           for va, stock, new, note in WORDS]
    out += [(va, shipped, shipped, "carry-over: " + note)
            for va, shipped, note in REPAIR]
    return out


def stock_words():
    """{va: shipped word} for the profile's STOCK, both sets."""
    d = {va: stock for va, stock, _new, _note in WORDS}
    d.update({va: shipped for va, shipped, _note in REPAIR})
    return d


def selftest(overlay_image):
    """Every stock word against a pristine overlay image. [] = pass."""
    bad = []
    for va, stock, _new, _note in WORDS:
        if overlay_image.read_word(va) != stock:
            bad.append("%08X" % va)
    for va, shipped, _note in REPAIR:
        if overlay_image.read_word(va) != shipped:
            bad.append("%08X repair" % va)
    seen = [va for va, *_ in WORDS]
    if len(set(seen)) != len(seen):
        bad.append("a VA is written twice")
    if set(seen) & {va for va, *_ in REPAIR}:
        bad.append("a repair VA is also a patched VA")
    return bad


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_carry",
        "Split screen: part B remembers part A",
        BOOL, False, group, confidence="experimental", touches="words",
        requires={prefix + "split_squad": [True]},
        help="A two-part mission carries the team's ammunition, health and "
             "losses from part A into part B.\n\n"
             "Split screen did it by team slot rather than by player, and the "
             "lead hand-off moves players between slots -- so if player 1 "
             "died and player 2 finished part A, player 1 started part B with "
             "player 2's gear and player 2 got a free refill.\n\n"
             "This carries each player's own state, and it carries the AI "
             "teammates too: one who died in part A is dead in part B, which "
             "the game only ever managed for whichever teammate happened to "
             "sit in slot 1. A player who died in part A also stays dead, and "
             "the other player leads.",
        caution="Not yet played. 73 words of the game's own save and restore "
                "code, checked against every team layout in an emulator and "
                "not in the game.\n\n"
                "The restore runs at every level start, so if levels stop "
                "loading, turn this off first.")

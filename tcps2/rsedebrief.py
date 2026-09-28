"""The debriefing's operative statistics, with the AI teammates in them.

The debriefing page (0x004314D0) lists one row per team member -- name,
health, kills, accuracy, shots, hits -- read off player 1's team,
`m_Team[0 .. rows-1]`. How many rows::

    0x00431568  a3 = m_iMemberCount + m_iMembersLost
    0x00431570  rows = a3                        // single player: everyone
    0x00431574  if (Level.Game.m_bIsSplitScreen)
    0x0043157c      rows = 2                     <-- this word
    0x00431580      if (mission flag, R6MissionDescription+0x4e bit 3
                        && mode == 11 && a3 < 4)  <-- and this branch
                        copy player 2's team into m_Team[a3 ..] and add rows

Retail split screen's team is [P1, P2], so two rows were everyone. With AI
teammates (`split_squad`) the team is [P1, AI..., P2] and two rows showed
player 1 and one AI -- the debriefing the user saw left the team out.

Both players share ONE team object (both controllers' +0x78c point at the
same R6RainbowTeam in every split-screen savestate), so the copy loop, were
its mission flag ever set, would write player 1 over player 2's slot and one
past the four-entry array. The flag is clear in every savestate.

The edit:

* rows = m_iMemberCount + m_iMembersLost + 1. With `split_squad` player 2
  sits at m_Team[m_iMemberCount + m_iMembersLost] -- the layout keeps him
  there, and a dead AI's bookkeeping stops below him -- so that is exactly
  every member: 4 with both AI, 2 without them, which is also retail's 2.
* the copy loop's guard becomes unconditional, so it never runs in split
  screen; the rows above already include player 2.

Both words run only in split screen: 0x0043157C is reached only when the
split-screen flag is set, and 0x00431580 is its own split-screen test.
Emitted with `split_squad`, which guarantees the layout the count relies on.
"""

from __future__ import annotations

#: (va, stock, new, note)
EDITS = (
    (0x0043157C, 0x24170002, 0x24F70001,
     "debrief rows: addiu s7,zero,2 -> addiu s7,a3,1 (count + lost + 1)"),
    (0x00431580, 0x10600022, 0x10000022,
     "debrief rows: beqz v1 -> b (never copy player 2's team over the array)"),
)

#: Words the edit relies on and does not change.
CONTEXT = (
    (0x00431568, 0x00833821),   # addu a3, a0, v1    count + lost
    (0x00431574, 0x10400002),   # beqz v0, 0x431580  single player skips 0x43157c
    (0x00431584, 0x0000202D),   # the branch's delay slot
)


def words():
    """[(va, value, stock, note)] for the overlay."""
    return [(va, new, stock, note) for va, stock, new, note in EDITS]

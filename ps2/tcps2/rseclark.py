"""Clark's debriefing in split screen.

In a single-player practice mission Clark reads the debriefing when the
mission-success screen comes up. In split screen he says nothing. Nothing is
missing: split screen loads the same in-game menu (`R6MagmaInteractionInGame`,
one instance in every split-screen savestate), and that menu holds all
sixteen debriefing clips in `m_sndDebriefing[16]` at +0xD0 --
`Play_Debrief_M00` to `Play_Debrief_M14`, and Trieste's `Play_Debreif_M15`,
the typo shipped. What stops him is a game-mode test.

Where the line is played
------------------------

The debriefing page is built by the function at 0x004314D0, which the menu
reaches for every mode but terrorist hunt (0x00433060 sends only modes 4 and
10 elsewhere) -- and which already handles mode 11 itself, collecting player
2's statistics at 0x004315A0. On a success (`R6MissionObjectiveMgr+0x370 ==
1`) it starts the victory music, then::

    0x004319d0  name  = GameManager.CurrentMap        ; "Alpines", "Oil_Refinery"
    0x004319e4  index = GameManager->vtable[0xA0](name)
    0x00431a24  if (index == -1) skip
    0x00431a5c  PlaySound(Viewports[0].Actor, m_sndDebriefing[index], slot 9)

`vtable[0xA0]` is 0x0048DC10. It finds the map in the game manager's mission
list (`+0x60`, sixteen names from Training_team to Airport), so the index
lines up with the clip array. But it only looks when the game-mode byte
(`GameManager+0x31`) is 1 or 2 -- StoryModeGame or PracticeModeGame -- and
returns -1 for everything else::

    0x0048dc34  lbu   $v1, 0x31($a0)       ; the mode
    0x0048dc38  beq   $v1, $v0, search     ; $v0 = 1: the campaign
    0x0048dc3c  addiu $s0, $zero, -1
    0x0048dc40  addiu $v0, $zero, 2
    0x0048dc44  bne   $v1, $v0, return     ; not practice either: -1
    0x0048dc48  daddu $v0, $s0, $zero

Split-screen practice is mode 11, PracticeModeGameForSplitScreen, from the
moment its map launches (0x0048ECEC); the split-screen menus before that run
as 2. Every split-screen savestate taken in a mission reads 11, across five
maps. So at the success screen the lookup returns -1 and the clip is never
played.

The edit
--------

Four words give the test a third arm, so it accepts 1, 2 and 11::

    0x0048dc38  beq   $v1, $v0, search     ; mode 1 (unchanged)
    0x0048dc3c  addiu $v0, $zero, 11
    0x0048dc40  beq   $v1, $v0, search     ; mode 11
    0x0048dc44  addiu $v0, $zero, 2
    0x0048dc48  bne   $v1, $v0, 0x48dccc   ; not mode 2: return -1
    0x0048dc4c  daddu $s0, $zero, $zero    ; (the search's own first word)

The miss now goes to 0x0048DCCC, the function's own not-found tail
(`$s0 = -1; $v0 = $s0; return`), instead of setting -1 on the way. That is
what frees the two words the third compare needs. Every mode except 11
takes the branch it always took and returns what it always returned, for
every byte value -- not just the thirteen modes the game defines -- so
single player, the campaign and terrorist hunt cannot change.

What else the lookup feeds
--------------------------

Exactly three call sites reach 0x0048DC10, all through the game manager's
vtable (the base class's slot 0xA0 is a stub that returns -1), and all
three only pick a clip with the index:

* 0x004319E4, the debriefing above.
* 0x0040E3C0, the main menu's briefing voice (`m_sndBriefing[index]`,
  played when `m_bClarkBriefing` is set).
* 0x0046D1EC, the pre-game briefing page (`P_PreGameBriefing`), which STOPS
  the briefing clip through audio vtable 0x124.

The two briefing pages belong to the menus, which run as mode 2 in split
screen and already find their clip; they only see mode 11 if they are
reached after a split-screen map has launched. Nothing touches progression
or saving. The one other reference to the function is an entry in a
frame-description table, not a call.

Which missions Clark can debrief
--------------------------------

`PlaySound` never loads a sound bank: the clip must already be resident,
and it is resident only in the bank of the level part where the mission
ends. Read off all thirty level banks on the pristine disc:

* one-part missions -- Island Estate (M04), Trieste (M15), Penthouse (M10),
  and the team training map (M00) -- carry it in their only bank;
* the other twelve carry it in their B part only. An A part has none, or
  just the mission's `Play_M##_Nil` companion.

Single player and split screen load the same part bank, so this is the same
list single-player practice has: a win on Alpine Village A is silent in both
modes, and a win on Alpine Village B is not. Island (0x02610000) and Trieste
(0x02720000) have the clip resident in split-screen savestates.
"""

from __future__ import annotations

#: The lookup: map name -> index into the mission list, or -1.
LOOKUP = 0x0048DC10

#: (va, stock, new, note), in address order.
EDITS = (
    (0x0048DC3C, 0x2410FFFF, 0x2402000B,
     "Clark: addiu s0,-1 -> addiu v0,11 (delay slot of the mode-1 test)"),
    (0x0048DC40, 0x24020002, 0x10620002,
     "Clark: addiu v0,2 -> beq v1,v0 search (split-screen practice)"),
    (0x0048DC44, 0x14620023, 0x24020002,
     "Clark: bne v1,v0 return -> addiu v0,2 (delay slot)"),
    (0x0048DC48, 0x0200102D, 0x14620020,
     "Clark: daddu v0,s0 -> bne v1,v0 not-found tail (0x48dccc)"),
)

#: Words the edit relies on and does not change: the mode load, the mode-1
#: test, the search's first word (now also the last branch's delay slot) and
#: the not-found tail the miss is sent to.
CONTEXT = (
    (0x0048DC34, 0x90830031),   # lbu   v1, 0x31(a0)
    (0x0048DC38, 0x10620004),   # beq   v1, v0, 0x48dc4c
    (0x0048DC4C, 0x0000802D),   # daddu s0, zero, zero
    (0x0048DCCC, 0x2410FFFF),   # addiu s0, zero, -1
    (0x0048DCD0, 0x0200102D),   # daddu v0, s0, zero
)

#: The game-mode enum, from the URL builder's jump table at 0x005EC160.
STORY, PRACTICE, PRACTICE_SPLIT = 1, 2, 11


def words():
    """[(va, value, stock, note)] for the overlay."""
    return [(va, new, stock, note) for va, stock, new, note in EDITS]


HELP = ("In a single-player practice mission Clark reads the debriefing when "
        "you win. In split screen he says nothing. The clips are all loaded; "
        "the game only looks one up in the campaign and in single-player "
        "practice. This adds split-screen practice to that list, so Clark "
        "debriefs the two of you as well.")

CAUTION = ("He speaks where single player has him speak: after the part of "
           "a mission that ends it. Island Estate, Trieste and Penthouse are "
           "one part and always have him; the other missions have him only "
           "after their B part -- winning an A part is silent in single "
           "player too, because its sound bank has no debriefing.\n\n"
           "Four words in the lookup that picks the clip. Every other game "
           "mode takes the branch it always took, so single player, the "
           "campaign and terrorist hunt cannot change. The clip is played "
           "exactly as single player plays it: the same array, the same "
           "sound slot, through player 1's view. Not yet heard in game -- "
           "win Island Estate in split screen to hear it.")


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "ss_clark", "Clark's debriefing",
        BOOL, False, group, confidence="applied", touches="words",
        help=HELP, caution=CAUTION)

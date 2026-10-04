"""Online co-op HUD and map: no Frag Pts, the other fireteam's panel, squad AI as friends (Jungle Storm, SLUS-20820).

WHAT THE HUD IS
---------------

The soldier HUD is one object (vtable 0x005A9F00, the display manager's +0x15C,
drawn by 0x00265440 from 0x0036798C). It is Ghost Recon's SoldierPanel with
Jungle Storm's multiplayer additions folded in, and it keeps two "slots":

    slot 0  +0x04 id, +0x0C SimHuman+0x1B0, +0x14 fireteam   -> the right panel
    slot 1  +0x08 id, +0x10 SimHuman+0x1B0, +0x18 fireteam   -> the left panel

Each slot has a 5-quad frame model and a 7-quad icon model (+0x3C/+0x58 for
slot 0, +0x74/+0x90 for slot 1), and a 3D soldier icon drawn by the human
panel renderer (0x0051F2E0, slot state at 0x0068A930 + slot * 0xEA0; the
HUD sets slot 1 every frame, the renderer clears it after drawing).

In single player, 0x00268770 fills slot 1 with the first living member of the
OTHER fireteam (`+0x18 = (+0x14 == 0)`), so the left panel shows that team's
letter, soldier icon (health colour), order and ROE icons. In split screen
slot 1 is player 2. Online the same routine bails out at 0x002688F4
(IIkeStateMgr::InMultiplayerMode): slot 1 stays empty, and the MP tail
(0x00268AD4) forces the fireteam index to 0 -- why the host's panel reads "A"
although the roster puts him in Bravo.

Online, the draw takes its multiplayer branch (0x002663D4): the clock, then
"Frag Pts: +N" (token 0x039004A7, text at 0x00266B54..0x00266FFC, deathmatch
score), then the room's counter line at 0x00267000 (0x0028EE70 by game type:
type 0 "Remaining:" = mission objectives not yet complete, type 1 "Enemy:",
...; co-op relevant, kept), the respawns left by the heart. Slot 1's frame
model +0x74 is reused for three boxes: [0] Frag Pts, [1] the counter, [2] the
clock; [3], [4] and the whole +0x90 model are unused online.

WHAT THIS MODULE DOES (online co-op rooms only: room type 0x0062AD20 == 1)
--------------------------------------------------------------------------

1. Five single-player gates in the HUD answer "not multiplayer" in a co-op
   room. Each is `jal 0x00125880` (IRSGameStateMgr*) followed by vt+0x9C
   (InMultiplayerMode); `coop_get` returns the real manager, or in a co-op
   room a stand-in object whose vt+0x9C returns 0:

       0x002688DC  0x00268770 picks slot 1 like single player (the other
                   fireteam's first active member in the rules manager's
                   roster) and keeps the real fireteam in +0x14 -- so the
                   host's right panel now reads B, which he is
       0x00268B68  0x00268B30 hands out slot 1's soldier (also asked by
                   SimHuman 0x003A9C48/0x003BEF50/0x003BF870, which keep the
                   icon's pose and dead state current, as in single player)
       0x002656F0  the human panel's slot 1 is set every frame (the 3D
                   soldier, coloured by his health: vt+0x298 wounded,
                   vt+0x29C down -- both replicated to the joiner)
       0x002658A0  the fireteams' order/ROE states are read; slot 1's feed
                   +0x90's order and ROE icons (slot 0's online icons are the
                   heart and the clock and are re-textured as the same)
       0x00265B1C  +0x90[0], the "whole team down" marker

   and one vt+0xA4 gate:

       0x00266B34  the observer test before Frag Pts. The stand-in's vt+0xA4
                   asks the real InObserverMode; an observer gets the stock
                   branch, anyone else resumes at 0x00267000 -- past Frag Pts
                   (its text and its "+N" change flash; 0x00627FD8..E8 are
                   only used there).

   Not opened: 0x00267EB4, the letter's flash timers (0x00265200). Their
   reasons are set by the command interface (0x00286B58, while the player
   gives an order) and radio traffic (0x00231C28/0x00231C80); in single player
   the player commands the other fireteam, so the left letter blinks. Online
   the players order their own fireteams (grcooporders), so the blink would
   point at the wrong team; the letter keeps its team colour instead.

2. 0x00267040: the counter line is drawn at y 370 (Frag Pts' line, in the
   first box) instead of 400.

3. 0x00267E6C, the MP branch's draw of +0x74: in a co-op room `draw74`
   (every frame) gives the second box zero size, writes single player's two
   left frames into +0x74[3]/[4] and single player's order/ROE icon
   rectangles into +0x90[3]/[4] (the online layout sizes them from slot 0's
   heart and clock), colours the frames (grey; Alpha green 0x174F27 or Bravo
   blue 0x61422F, the watched team's) or clears them, draws +0x74 and then
   +0x90. The panel is shown when slot 1 has a soldier, single player's own
   test of him passes (SimHuman +0x62C clear, 0x0025EFC0) and the player is
   not an observer (the stock HUD hides soldier icons then). On the joiner
   (InMultiplayerClientMode) the order and ROE icons stay hidden: fireteam AI
   runs on the host only (the joiner's AI manager has no fireteam objects),
   so the joiner has no order state to show. It also sets the HUD's re-pick
   flag +0x39, which the stock HUD sets for good after its first avatar
   change; a console that built its HUD before the other fireteam existed
   (the joiner) would otherwise never fill slot 1. Then the two letters:
   +0x90 quad 2 (the watched letter) gets single player's size, A 118 or
   B 121 wide -- 0x00262A50 sizes it from OUR letter (0x00262350 is asked
   for slot 0), and a Charlie player's "letter" is an equipment icon; and
   a player past Bravo loses +0x58 quad 2 (his own letter, colour 0): the
   HUD atlas (decoded from RAM: A, B, circled 1-4, equipment icons) has no C,
   and tex 3 + team would be the pistol icon.

4. The map screen (online: the command map draws only its MP panel, 0x0028D800 ->
   0x0028FB90, and the team icon pass 0x00296760):

   - Markers. Each soldier's category comes from 0x00293DB0. Online, a
     soldier without a player link (SimHuman +0x750, the flaw grcooplabel
     fixed for the reticle label) is sorted by name -- "Civilian"/"Hostage"/
     "Friendly" -> 2, anything else -> 3, an enemy -- so the fill AI came out
     as red enemy dots (icon 0, colour 240,60,60), and on a joiner whose link
     lookup failed even the players did. In a co-op room, before the name
     test, `map_ai` asks SimHuman::IsPlayersSquad (vt+0x568 = 0x003BBFE0: the
     players' company 0x0057A1C8 and platoon 0x0057A1D0, set on both
     consoles); yes -> category 0, the other player's category: the friendly
     soldier icon with its ring (icons 1 and 9), green 78,159,46 in a co-op
     room (the local player's own marker keeps its yellow blink). All three
     fireteams' AI qualify, Charlie included. Enemies, civilians and players
     with a link are untouched, and so is which soldiers are shown at all:
     that is 0x002970B0, before the category -- enemies appear as stock
     only while the players' side knows of them, fading out after.
   - Scoreboard. The MP panel lists "Frag Pts" and each player's score
     (0x00290334.. title, 0x002905A4..0x00290C0C player list, frame model
     quads 2-8 = the title box and six player rows, the players' icons model
     +0x18C). In a co-op room the title text, the list and the icons model
     are skipped (`skip_text`/`skip_first`/`skip_draw`: the replaced call
     returns at once) and `map_frame` clears quads 2-8's colours before the
     frame model is drawn. The team header, "Objectives" with its counter
     ("Remaining: 4" / "Enemy: 8"), the mission line and the dimmed backdrop
     stay.

Which team is shown: single player's rule, `other = (own == 0) ? 1 : 0`. With
the AI fill (grlan js_coop_ai) the roster is Alpha = joiner + 2 AI, Bravo =
host + 2 AI, Charlie = 3 AI: the host watches Alpha and the joiner Bravo.
The stock online HUD printed "A" for everyone (the MP tail above); the host
now sees his real B. Single player has two fireteams and two HUD slots, so
there is no Charlie panel to enable; Charlie (no human in it) gets none.
Without the AI fill each fireteam is one human, so each watches the other.
A player who takes over a Charlie soldier (single player's rule would give
Alpha for anyone): 0x002688C4 (`+0x18 = (+0x14 == 0)`, 5 words) calls
`other_team` instead, which in a co-op room gives the other player's home
fireteam -- the host Alpha, the joiner Bravo, read from the game state
manager's mode byte (*0x00684A78 + 0x1F2: 1 offline, 2 host, 3 joiner; the
byte InMultiplayerClientMode tests), not from anything the panel draws.
Alpha and Bravo players, other rooms and offline games get the stock answer.

Deathmatch and team rooms (room type 0 / 2) and every offline game are
unchanged: the gates return the real manager there, and every other hook sits
in the multiplayer branch and tests the room first. An offline game with a
stale room byte still meets the stand-in only at the five vt+0x9C gates,
whose answer (0) is what InMultiplayerMode gives offline anyway.

Caves: five unreferenced SDK library routines (no jump, branch, pointer or
lui pair reaches any word of them from the ELF or either overlay; no option
of the current tree writes them): 0x00185380, 0x0018BAE0, 0x00183D78,
0x001979E0, 0x001745C8.

Checked in the RAM interpreter, the game's own HUD init and draw run over
RAM (scratchpad agent_hud/vhud.py): twelve online co-op dumps (seven host,
five joiner; mission "Remaining" and firefight "Enemy" rooms; with and
without the AI fill), ten offline dumps (single player and split screen,
also with a stale room byte of 1: identical to stock), co-op dumps forced
to deathmatch / team rooms (identical to stock, Frag Pts drawn), and events
(watched soldier down -> next member; whole team down -> marker, no soldier
icon; wounded -> state 1; observer -> stock branch, no panel; a HUD built
before the other fireteam existed -> filled on the next frames); the map's
icon pass and MP panel over eight co-op dumps (squad AI now friendly, every
other soldier drawn as stock, scoreboard gone with six rows coloured,
header/objectives/mission line as stock), forced deathmatch/team rooms and
six offline dumps (identical to stock). A player in Charlie
(agent_hud/vcharlie.py): the 6C2F39B0 host save (company 0 mission, host on
a Charlie rifleman) and the other co-op saves with the avatar moved into
Charlie, Bravo or Alpha on host and joiner: right letter hidden only past
Bravo, left letter and frame in the watched team's letter/colour at single
player's size, watched team's first active soldier in slot 1, watched team
wiped out -> its marker, the choice steady. Not yet played.
"""

from __future__ import annotations

from .grasm import assemble
from .model import BOOL, Setting

#: code caves: unreferenced routines, first word .. end (exclusive)
CAVE_A, CAVE_A_END = 0x00185380, 0x00185438      # 46 words: the stand-in, the Frag Pts skip, the counter line
CAVE_B, CAVE_B_END = 0x0018BAE0, 0x0018BBA8      # 50 words: draw74
CAVE_C, CAVE_C_END = 0x00183D78, 0x00183E30      # 46 words: paint (the frames and icon rectangles)
CAVE_D, CAVE_D_END = 0x001979E0, 0x00197A6C      # 35 words: single player's quads, other_team
CAVE_E, CAVE_E_END = 0x001745C8, 0x00174678      # 44 words: the map screen

SYMS = dict(
    GETSTATE=0x00125880,    # IRSGameStateMgr* (lw 0x684A78)
    UIDRAW=0x0015A1B0,      # UIModel draw
    AFTER_FRAG=0x00267000,  # the counter line, right after the Frag Pts block
    MDRAW=0x004FF330,       # renderer: draw a UI model (a1)
    TEXT=0x00219540,        # draw a text line
    FIRSTPLAYER=0x00147E60, # the game info's first player record
    CAT_NAME=0x00293E30,    # the map category's name test, after its two loads
    CAT_EXIT=0x002940A4,    # the map category's exit (v0 = category)
)

#: the online map screen (section 4 above): in place, (va, stock, cave label or None, note)
MAP_EDITS = (
    (0x00293E28, 0x8E190000, "map_ai", "map: an AI in the players' squad is a friend, not an enemy dot"),
    (0x00293E2C, 0x8F39000C, None, "map: (moved into the cave)"),
    (0x0028FC80, 0x0C13FCCC, "map_frame", "map: the panel frames, minus the Frag Pts boxes in co-op"),
    (0x0028FCC8, 0x0C13FCCC, "skip_draw", "map: the Frag Pts players' icons, not in co-op"),
    (0x002903D4, 0x0C086550, "skip_text", "map: the 'Frag Pts' title, not in co-op"),
    (0x002905B0, 0x0C051F98, "skip_first", "map: the Frag Pts player list, empty in co-op"),
)

#: the six gates: `jal 0x00125880` -> `jal coop_get`
GATES = (
    (0x002688DC, "slot 1 is chosen as in single player (0x00268770)"),
    (0x00268B68, "slot 1's soldier is handed out (0x00268B30)"),
    (0x002656F0, "the soldier icon of slot 1 (human panel) is set"),
    (0x002658A0, "the fireteams' order and ROE icons are read"),
    (0x00265B1C, "the other fireteam's 'all down' marker"),
    (0x00266B34, "observer test before Frag Pts: co-op resumes after it"),
)
GATE_STOCK = 0x0C049620                          # jal 0x00125880

#: 0x00268770's choice of the watched fireteam, `+0x18 = (+0x14 == 0)` -> `+0x18 = other_team(+0x14)`
PICK_AT = 0x002688C4
PICK_STOCK = (0x8E620014, 0x0002102B, 0x38420001, 0x304200FF, 0xAE620018)
#: s4 is +0x14 here (stored at 0x002688BC; nothing branches into 0x002688B0..0x002688E0); a0, v1
#: and at are dead (next comes the gate call 0x002688DC, whose result feeds a0)
SRC_PICK = """
    sltiu a0, s4, 2                  ; own team is Alpha or Bravo
    lui   v1, 0x63
    jal   other_team
    sltiu v0, s4, 1                  ; single player's answer: (own == 0)
    sw    v0, 0x18(s3)
"""

YPOS_AT = 0x00267040        # lui v1, 0x42a0 ; lui v0, 0x43c8 (x 80, y 400 of the counter line)
DRAW74_AT = 0x00267E6C      # jal 0x0015A1B0 (+0x74, the MP branch's boxes)

SRC_A = """
coop_get:                            ; stands in for 0x00125880 at the gates
    lui   at, 0x63
    lbu   at, -0x52E0(at)            ; room type 0x0062AD20, 1 = co-op
    addiu at, at, -1
    bnez  at, cg_real
    lui   v0, %hi(FAKE)
    jr    ra
    addiu v0, v0, %lo(FAKE)
cg_real:
    j     GETSTATE
    nop
FAKE:
    .word SLOTS-0x9C                 ; the stand-in: its vtable is SLOTS - 0x9C
SLOTS:
    .word RET0                       ; vt+0x9C InMultiplayerMode: no
    .word RET0                       ; vt+0xA0 (never asked of it)
    .word FAKE_A4                    ; vt+0xA4, asked only at 0x00266B34
RET0:
    jr    ra
    move  v0, zero
FAKE_A4:                             ; InObserverMode before Frag Pts, in a co-op room
    addiu sp, sp, -0x10
    sd    ra, 0(sp)
    jal   GETSTATE
    nop
    lw    t9, 0(v0)
    lw    t9, 0xA4(t9)
    jalr  t9                         ; the real InObserverMode
    move  a0, v0
    ld    ra, 0(sp)
    bnez  v0, fa_ret                 ; an observer: back to the stock observer branch
    addiu sp, sp, 0x10
    lui   ra, %hi(AFTER_FRAG)        ; anyone else: resume past the Frag Pts block
    addiu ra, ra, %lo(AFTER_FRAG)
fa_ret:
    jr    ra
    nop
ypos:                                ; the counter line's y, called from 0x00267040
    lui   at, 0x63
    lbu   at, -0x52E0(at)
    addiu at, at, -1
    bnez  at, yp_ret
    lui   v0, 0x43C8                 ; 400.0, the second box (stock)
    lui   v0, 0x43B9                 ; co-op: 370.0, the first box
yp_ret:
    jr    ra
    nop
"""

SRC_B = """
draw74:                              ; for the MP branch's draw of +0x74: a0 = hud + 0x74, s1 = hud
    lui   at, 0x63
    lbu   at, -0x52E0(at)
    addiu at, at, -1
    beqz  at, d_coop
    nop
    j     UIDRAW                     ; not a co-op room: the stock draw
    nop
d_coop:
    addiu sp, sp, -0x20
    sd    ra, 0x10(sp)
    sw    zero, 0(sp)                ; show the other fireteam's panel?
    sw    zero, 4(sp)                ; ... with its order and ROE icons?
    lw    v0, 8(s1)                  ; slot 1's soldier id, -1 = none
    addiu v0, v0, 1
    beqz  v0, d_paint
    lw    v0, 0x10(s1)               ; his SimHuman + 0x1B0
    beqz  v0, d_paint
    nop
    lw    v0, 0x47C(v0)              ; SimHuman + 0x62C: single player's own test (0x0025EFC0)
    bnez  v0, d_paint
    nop
    jal   GETSTATE
    nop
    lw    t9, 0(v0)
    lw    t9, 0xA4(t9)
    jalr  t9                         ; InObserverMode: an observer gets no soldier icons, as stock
    move  a0, v0
    sltiu v0, v0, 1
    sw    v0, 0(sp)
    jal   GETSTATE
    nop
    lw    t9, 0(v0)
    lw    t9, 0x98(t9)
    jalr  t9                         ; InMultiplayerClientMode: the joiner runs no fireteam AI,
    move  a0, v0                     ; so it has no order/ROE state to show
    sltiu v0, v0, 1
    sw    v0, 4(sp)
d_paint:
    lw    a1, 4(sp)
    jal   paint
    lw    a0, 0(sp)
    jal   UIDRAW
    addiu a0, s1, 0x74
    lw    v0, 0(sp)
    beqz  v0, d_done
    nop
    jal   UIDRAW
    addiu a0, s1, 0x90
d_done:
    ld    ra, 0x10(sp)
    jr    ra
    addiu sp, sp, 0x20
"""

SRC_C = """
paint:                               ; a0 = show, a1 = order/ROE icons too, s1 = hud; a leaf
    li    v0, 1                      ; +0x39: re-pick both slots next frame (0x00268770), as the
    sb    v0, 0x39(s1)               ; stock HUD does for good after its first avatar change
    lw    v1, 0x8C(s1)               ; +0x74's quads (model + 0x18), 0x28 bytes each
    lw    v0, 0x38(v1)               ; quad 1, the counter's old box: XYZ1 = XYZ0 (no size)
    sw    v0, 0x48(v1)
    lui   t0, %hi(TPL)
    addiu t0, t0, %lo(TPL)
    addiu t1, v1, 0x78               ; quads 3 and 4 <- single player's two left frames
    addiu t2, t0, 0x50               ; (grey, Alpha green)
p_copy:
    lw    v0, 0(t0)
    addiu t0, t0, 4
    sw    v0, 0(t1)
    bne   t0, t2, p_copy
    addiu t1, t1, 4
    lw    t2, 0x18(s1)               ; the watched fireteam
    beqz  t2, p_alpha
    lw    v0, 0x10(t0)               ; Bravo blue (TPL + 0x60)
    sw    v0, 0xA0(v1)
p_alpha:
    bnez  a0, p_shown
    lw    t3, 0xA8(s1)               ; +0x90's quads
    sw    zero, 0x78(v1)             ; hidden: neither frame drawn
    sw    zero, 0xA0(v1)
p_shown:
    lw    v0, 0(t0)                  ; order and ROE icons at single player's size
    sw    v0, 0x88(t3)
    lw    v0, 4(t0)
    sw    v0, 0x98(t3)
    lw    v0, 8(t0)
    sw    v0, 0xB0(t3)
    lw    v0, 12(t0)
    bnez  a1, p_letter
    sw    v0, 0xC0(t3)
    sw    zero, 0x78(t3)             ; the joiner: no order/ROE icons (colour 0)
    sw    zero, 0xA0(t3)
p_letter:                            ; +0x90 quad 2, the watched letter: 0x00262A50 sizes it by
    lui   v0, 0x8BAA                 ; OUR letter (tex 3 + own team); give it its own size
    beqz  t2, p_la
    ori   v0, v0, 0x7360             ; A: XYZ1 (118, 410.63)
    addiu v0, v0, 0x30               ; B: XYZ1 (121, 410.63)
p_la:
    sw    v0, 0x70(t3)
    lw    t2, 0x14(s1)               ; own fireteam
    sltiu t2, t2, 2
    bnez  t2, p_ret
    lw    v1, 0x70(s1)               ; +0x58's quads
    sw    zero, 0x50(v1)             ; past Bravo: the atlas has no letter (tex 3 + team would be
p_ret:                               ; an equipment icon) -- quad 2 not drawn
    jr    ra
    nop
"""

#: single player's left panel quads, read from six single-player savestates
#: (identical in all): +0x74[0] and [1], then the XYZ0/XYZ1 of +0x90[3] and [4];
#: then the watched fireteam's rule for a player past Bravo
SRC_D = """
TPL:
    .word 0x41646464                 ; frame 1: grey (paint clears it when hidden)
    .word 0x3F800000                 ;   Q 1.0
    .word 0x027007B0                 ;   UV0
    .word 0x00000000
    .word 0x89CC6F20                 ;   XYZ0 (50, 380.75)
    .word 0x00000001
    .word 0x05000000                 ;   UV1
    .word 0x00000000
    .word 0x8C3176D0                 ;   XYZ1 (173, 419.06)
    .word 0x00000001
    .word 0x64174F27                 ; frame 2: Alpha green (paint writes Bravo blue over it)
    .word 0x3F800000
    .word 0x0D0007A0
    .word 0x00000000
    .word 0x8AD96FF0                 ;   (63, 397.56)
    .word 0x00000001
    .word 0x0B600000
    .word 0x00000000
    .word 0x8C5D7790                 ;   (185, 421.81)
    .word 0x00000001
    .word 0x89BD6FA0                 ; order icon XYZ0 (58, 379.81)
    .word 0x8B247120                 ;   XYZ1 (82, 402.25)
    .word 0x8AE86FA0                 ; ROE icon XYZ0 (58, 398.5)
    .word 0x8C4E7110                 ;   XYZ1 (81, 420.88)
    .word 0x6461422F                 ; Bravo blue
other_team:                          ; from 0x002688C4: a0 = own team < 2, v0 = single player's
    bnez  a0, ot_ret                 ; answer (own == 0), v1 = 0x630000. Alpha or Bravo: that
    lui   a0, 0x68                   ; answer. Past Bravo, in a co-op room: the other player's
    lbu   v1, -0x52E0(v1)            ; home fireteam. Room type (1 = co-op)
    lw    a0, 0x4A78(a0)             ; the game state manager (0x00684A78)
    lbu   a0, 0x1F2(a0)              ; its mode, InMultiplayerClientMode's byte: 1 offline,
    xori  v1, v1, 1                  ; 2 host, 3 joiner
    sltiu a0, a0, 3
    xori  a0, a0, 1                  ; joiner 1 (Bravo, the host's), else 0 (Alpha, the joiner's)
ot_ret:
    jr    ra
    .word 0x0083100A                 ; movz v0, a0, v1: only in a co-op room (else stock, 0)
"""


#: the map screen: category fix (0x00293E28) and the co-op scoreboard (0x0028FB90's MP panel)
SRC_E = """
map_ai:                              ; the map's category test, no player link (an AI):
    lui   at, 0x63
    lbu   at, -0x52E0(at)
    addiu at, at, -1
    bnez  at, ma_stock               ; not a co-op room: stock
    lw    t9, 0(s1)                  ; s1 = his SimHuman
    lw    t9, 0x568(t9)              ; IsPlayersSquad (0x003BBFE0): the players' company and platoon
    jalr  t9
    move  a0, s1
    bnez  v0, ma_friend
    nop
ma_stock:
    lw    t9, 0(s0)                  ; stock from here: the two words moved from 0x00293E28
    j     CAT_NAME
    lw    t9, 0xC(t9)
ma_friend:
    j     CAT_EXIT
    move  v0, zero                   ; category 0, the other player's: a friendly soldier icon
skip_draw:
    lui   t9, %hi(MDRAW)
    b     sk_room
    addiu t9, t9, %lo(MDRAW)
skip_first:
    lui   t9, %hi(FIRSTPLAYER)
    b     sk_room
    addiu t9, t9, %lo(FIRSTPLAYER)
skip_text:
    lui   t9, %hi(TEXT)
    addiu t9, t9, %lo(TEXT)
sk_room:                             ; the call it replaced, unless this is a co-op room
    lui   at, 0x63
    lbu   at, -0x52E0(at)
    addiu at, at, -1
    .word 0x03E1C80A                 ; movz t9, ra, at: in a co-op room the call returns at once
    jr    t9
    move  v0, zero                   ; (and 'no first player': the list loop never starts)
map_frame:                           ; a1 = the panel's frame model (25 quads, 0x70 bytes each)
    lui   at, 0x63
    lbu   at, -0x52E0(at)
    addiu at, at, -1
    bnez  at, mf_draw
    lw    v1, 8(a1)                  ; its GS data: GIF tag, then the quads
    addiu v1, v1, 0xF0               ; quad 2: the 'Frag Pts' title box, then six player rows
    addiu v0, v1, 0x310
mf_loop:
    sw    zero, 0(v1)                ; both triangles' colour: not drawn
    addiu v1, v1, 0x70
    bne   v1, v0, mf_loop
    sw    zero, -0x38(v1)            ; (the second triangle of the quad just passed)
mf_draw:
    j     MDRAW
    nop
"""


def _labels():
    """Every label of the five caves (two passes: each cave names the others)."""
    syms = dict(SYMS)
    for _ in range(2):
        found = {}
        for src, base in ((SRC_A, CAVE_A), (SRC_B, CAVE_B), (SRC_C, CAVE_C), (SRC_D, CAVE_D),
                          (SRC_E, CAVE_E)):
            s = dict(syms)
            for k in ("paint", "TPL", "coop_get", "ypos", "draw74"):
                s.setdefault(k, 0)
            _w, lab = assemble(src, base, s)
            found.update(lab)
        syms.update(found)
    return syms


CAVES_SRC = ((SRC_A, CAVE_A, CAVE_A_END), (SRC_B, CAVE_B, CAVE_B_END), (SRC_C, CAVE_C, CAVE_C_END),
             (SRC_D, CAVE_D, CAVE_D_END), (SRC_E, CAVE_E, CAVE_E_END))


def build() -> list:
    """[(va, word)] for the five caves."""
    syms = _labels()
    out = []
    for src, base, end in CAVES_SRC:
        words, _lab = assemble(src, base, syms)
        if base + 4 * len(words) > end:
            raise ValueError("cave 0x%08x: %d words, room %d" % (base, len(words), (end - base) // 4))
        out += [(base + 4 * i, w) for i, w in enumerate(words)]
    return out


#: the retail words of every word this module writes (SLUS_208.20)
_CAVE_STOCK_HEX = {
    CAVE_A: (
        "27BDFFB0FFB30030FFB2002000C0982DFFB0000000A0902DFFBF00400080802D06010008FFB10010"
        "3C027FFF3C0300623442FFFF2471C2C80202802410000005240200203C0200573C0300578C516618"
        "8C62661C0202102B14400004000000003C0280001000000D344200690C060CC80000000000101900"
        "00711821AC720000AC7300040380202D10400003AC6400080C060CDE000000000000102DDFBF0040"
        "DFB30030DFB20020DFB10010DFB0000003E0000827BD0050"),
    CAVE_B: (
        "27BDFFA03C030062FFB20030FFB000102472C500FFBF0050FFB30040FFB100208E42002414400003"
        "0080802D1000001F2402FF9C3C1100570C05E8CC8E246634044100033C070062100000182402FF38"
        "3C13006224E7C5803C0B0019ACF000040240202D256BBA10AFA00000240500150000302D24080030"
        "2669DAC00C05F5AA240A00040040802D12000005000000000C05E8C08E246634100000040200102D"
        "0C05E8C08E2466348E62DAC0DFBF0050DFB30040DFB20030DFB10020DFB0001003E0000827BD0060"),
    CAVE_C: (
        "27BDFFC0FFB20020FFB000003C120057FFBF0030265065F8FFB100108E0200080441000400000000"
        "3C0280001000001C344280018E02001010400004000000003C02800010000016344200100C060CC8"
        "000000008E0500080040882D0C05E7F82404000B144000082402FFFF0C05EB702404000B0C060F00"
        "24040C000C060EFC0000202D2402FFFFFE4065F812200003AE0200080C060CDE000000000000102D"
        "DFBF0030DFB20020DFB10010DFB0000003E0000827BD0040"),
    CAVE_D: (
        "27BDFFB0FFB20020FFB100100080902DFFB0000000A0882DE7B4004000C0802DFFBF00300C060CC8"
        "46006506DA240000DA0500004408A00048A830004A29233C4B0001C34B063A2C4BC621BC4BC82A48"
        "FA49000010400007DFBF0030DFB20020DFB10010DFB00000C7B4004008060CDE27BD0050DFB20020"
        "DFB10010DFB00000C7B4004003E0000827BD0050"),
    CAVE_E: (
        "34028001108200263C02005734028003108200213C020057340280021082001C3C02005734028004"
        "108200173C0200573402801110820010340280131082000C3C02005734028012108200073C020057"
        "34028014548200130000102D3C020057100000102442AE001000000E2442A8C01000000C2442A480"
        "3C0200578C4292AC10000009ACA20000100000062442A45010000004244293801000000224429300"
        "8C4292A8ACA2000003E0000824020001"),
}


def _stock_words(base: int) -> list:
    h = _CAVE_STOCK_HEX[base]
    if len(h) % 8:
        raise ValueError("cave 0x%08x: stock table is not whole words" % base)
    return [int(h[i:i + 8], 16) for i in range(0, len(h), 8)]


JS_STOCK = {}
for _base, _end in ((CAVE_A, CAVE_A_END), (CAVE_B, CAVE_B_END), (CAVE_C, CAVE_C_END), (CAVE_D, CAVE_D_END),
                   (CAVE_E, CAVE_E_END)):
    _ws = _stock_words(_base)
    if _base + 4 * len(_ws) != _end:
        raise ValueError("cave 0x%08x: %d stock words for %d" % (_base, len(_ws), (_end - _base) // 4))
    JS_STOCK.update((_base + 4 * i, w) for i, w in enumerate(_ws))
JS_STOCK.update((va, GATE_STOCK) for va, _n in GATES)
JS_STOCK.update({YPOS_AT: 0x3C0342A0, YPOS_AT + 4: 0x3C0243C8, DRAW74_AT: 0x0C05686C})
JS_STOCK.update((va, stock) for va, stock, _t, _n in MAP_EDITS)
JS_STOCK.update((PICK_AT + 4 * i, w) for i, w in enumerate(PICK_STOCK))


def _jal(target: int) -> int:
    return 0x0C000000 | ((target >> 2) & 0x03FFFFFF)


def edits() -> list:
    """(va, value, stock, note), only the words that change."""
    syms = _labels()
    rows = []
    for va, note in GATES:
        rows.append((va, _jal(syms["coop_get"]), GATE_STOCK, "co-op HUD: " + note))
    rows.append((YPOS_AT, _jal(syms["ypos"]), JS_STOCK[YPOS_AT],
                 "co-op HUD: the counter line moves up into the first box"))
    rows.append((YPOS_AT + 4, 0x3C0342A0, JS_STOCK[YPOS_AT + 4], "co-op HUD: (x 80, in the delay slot)"))
    rows.append((DRAW74_AT, _jal(syms["draw74"]), JS_STOCK[DRAW74_AT],
                 "co-op HUD: draw the other fireteam's panel on the left"))
    pick, _l = assemble(SRC_PICK, PICK_AT, syms)
    if len(pick) != len(PICK_STOCK):
        raise ValueError("the pick is %d words, room %d" % (len(pick), len(PICK_STOCK)))
    for i, w in enumerate(pick):
        rows.append((PICK_AT + 4 * i, w, PICK_STOCK[i],
                     "co-op HUD: the watched fireteam when the player is past Bravo"))
    for va, stock, target, note in MAP_EDITS:
        if target is None:
            word = 0x00000000
        elif stock >> 26 == 3:                      # a call: call the cave instead
            word = _jal(syms[target])
        else:                                       # a plain word: jump to the cave
            word = 0x08000000 | ((syms[target] >> 2) & 0x03FFFFFF)
        rows.append((va, word, stock, "co-op " + note))
    for va, word in build():
        if word != JS_STOCK[va]:
            rows.append((va, word, JS_STOCK[va], "co-op HUD cave"))
    return rows


def js_edits(v: dict) -> list:
    return edits() if v.get("js_coop_hud") else []


def cards(prefix: str = "js_", group: str = "Online") -> list:
    return [
        Setting(prefix + "coop_hud", "Online co-op: squad HUD and map instead of Frag Pts", BOOL,
                False, group, confidence="experimental",
                help="Online co-op uses the deathmatch HUD: a 'Frag Pts' score on the left and "
                     "no panel for the other fireteam. In co-op rooms this drops Frag Pts, moves "
                     "the mission counter ('Remaining' objectives, 'Enemy' left) up into its box, "
                     "and adds single player's left panel for the other player's fireteam: its "
                     "letter and its lead soldier's icon, coloured by his health (it moves on to "
                     "the next man when he goes down). The host sees Alpha, the joiner Bravo. "
                     "If you take over a Charlie soldier you watch the other player's home "
                     "fireteam, and your own panel shows no letter (the game has no 'C'). "
                     "Your own panel now shows your real fireteam letter -- the host is Bravo, "
                     "the stock online HUD printed A for everyone. On the host the panel also "
                     "shows Alpha's order and ROE icons; the joiner runs no squad AI, so his "
                     "panel leaves them out. The clock and your respawns stay. On the map screen "
                     "your AI squadmates are drawn as friendly soldiers like the other player "
                     "instead of red enemy dots, and the Frag Pts scoreboard is gone (the "
                     "objectives and mission lines stay). Deathmatch and team rooms, single "
                     "player and split screen are unchanged.",
                caution="Not yet played. Checked by running the game's own HUD and map code over "
                        "RAM from online co-op missions (host and joiner) and from single-player "
                        "and split-screen saves. Each console draws its own HUD and map: only the "
                        "console with this option changes, so give it to both players."),
    ]


def selftest(js_elf=None) -> list:
    import struct
    fails = []
    rows = edits()
    for va, _w, s, _n in rows:
        if JS_STOCK.get(va) != s:
            fails.append("%08x: edit stock %08x, table %s" % (va, s, JS_STOCK.get(va)))
    if len(set(va for va, _w, _s, _n in rows)) != len(rows):
        fails.append("an address is written twice")
    syms = _labels()
    movz = [w for va, w in build() if w == 0x0083100A]
    if len(movz) != 1 or (movz[0] >> 26, (movz[0] >> 21) & 31, (movz[0] >> 16) & 31, (movz[0] >> 11) & 31,
                          movz[0] & 63) != (0, 4, 3, 2, 0x0A):
        fails.append("movz v0, a0, v1 encoding")
    movz = [w for va, w in build() if w == 0x03E1C80A]
    if len(movz) != 1 or (movz[0] >> 26, (movz[0] >> 21) & 31, (movz[0] >> 16) & 31, (movz[0] >> 11) & 31,
                          movz[0] & 63) != (0, 31, 1, 25, 0x0A):
        fails.append("movz t9, ra, at encoding")
    if syms["SLOTS"] - 0x9C + 0x9C != syms["SLOTS"] or dict(build())[syms["FAKE"]] != syms["SLOTS"] - 0x9C:
        fails.append("stand-in vtable pointer")
    if js_elf is not None:
        def word(va):
            return struct.unpack_from("<I", js_elf, va - 0x00100000 + 0x100)[0]
        for va, want in JS_STOCK.items():
            if word(va) != want:
                fails.append("stock %08x: disc %08x, recorded %08x" % (va, word(va), want))
        # each gate is followed by the InMultiplayerMode (vt+0x9C) or InObserverMode (vt+0xA4) call
        for va, _n in GATES:
            seq = [word(va + 4 * k) for k in range(6)]
            slot = 0xA4 if va == 0x00266B34 else 0x9C
            if seq[2] != 0x8C590000 or seq[3] != 0x8F390000 | slot or seq[4] != 0x0320F809                     or seq[5] != 0x0040202D:
                fails.append("gate %08x: not jal/lw/lw vt+0x%x/jalr/move" % (va, slot))
        context = {0x00266FFC: 0xAC227FE8,     # the Frag Pts block's last word (sw v0, 0x7fe8(at))
                   0x00267000: 0x3C050059,     # the counter line starts here (lui a1, 0x59)
                   0x00267048: 0x44836000,     # mtc1 v1, f12
                   0x0026704C: 0x44826800,     # mtc1 v0, f13
                   0x00267E68: 0x26240074,     # addiu a0, s1, 0x74
                   0x00267E70: 0x00000000,
                   0x00264EEC: 0x0320F809,
                   0x00293E20: 0x14400042,     # bnez v0 (player link): the company test at 0x293F2C
                   0x00293E30: 0x0320F809,     # jalr t9 (the name getter; CAT_NAME)
                   0x002940A4: 0xDFBF0040,     # ld ra, 0x40(sp) (CAT_EXIT)
                   0x0028FC84: 0x26A50020,     # addiu a1, s5, 0x20 (the frame model)
                   0x0028FCCC: 0x26A5018C,     # addiu a1, s5, 0x18c (the players' icons)
                   0x002905B8: 0x0040982D,     # move s3, v0 (the list's first player)
                   0x002688BC: 0xAE740014,     # sw s4, 0x14(s3): the pick may read s4
                   0x002688C0: 0xAE620008,     # sw v0, 8(s3), before the pick
                   0x002688D8: 0xA2600118,     # sb zero, 0x118(s3), after it
                   0x00262A50: 0x27BDFE60,     # the 7-quad position helper (sizes quad 2 by slot 0)
                   0x003BBFE0: 0x27BDFFE0,     # IsPlayersSquad
                   0x005B5C38: 0x003BBFE0}     # SimHuman vt+0x568
        for va, want in context.items():
            if word(va) != want:
                fails.append("context %08x: disc %08x, expected %08x" % (va, word(va), want))
    return fails


if __name__ == "__main__":
    s = _labels()
    for src, base, end in CAVES_SRC:
        w, _l = assemble(src, base, s)
        print("%08x: %d words of %d" % (base, len(w), (end - base) // 4))

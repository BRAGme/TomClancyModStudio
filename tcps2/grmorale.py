"""Enemy morale and searching the last known position: Jungle Storm (SLUS-20820) and Ghost Recon (SLUS-20613).

Two enemy options, the same engine code in both games.

Morale (js_enemy_morale / gr_enemy_morale)
------------------------------------------

As shipped, a fire team fights to the last man. The game has the start of a
morale system and never finished it: HumanAI::UpdateMorale (GR 0x00198F00,
JS 0x003E8F70), called for every soldier every frame, works out "pinned down,
the last man of a team that has lost men, nerve below 0.5" and then does
nothing with the answer (its UpdateFleeingFlag is `return 0`). The engine's
flight behaviour (FleeBehavior, built only by mission-script "panic" actions)
makes a soldier drop his gun, refuse orders and surrender -- no use here.

FireTeamAI::Update counts its men every frame with UpdateTeamStatus (GR
0x0018BC70, JS 0x003DC5A0), which keeps the number still in action (not dead,
not incapacitated: SimHumanState::IsOutOfAction) at FireTeamAI +0xD0. That call
(GR 0x0018DD30, JS 0x003DE304) now goes through `mor`, which makes it and then
compares the count before and after. The team breaks at the moment K x (men in
action) first drops to the team's size or below -- K = 2 for "half" (half the
team down), 3 for "two thirds" -- so it happens once per team, and only:

  * for a hostile team (SimHuman::IsEnemy's test on each member: the player's
    squad, split-screen and co-op teams are never touched);
  * that knows where an enemy is (FireTeamAI::GetClosestEnemy from the team's
    position; a team cut down by an unseen sniper does not know which way to go);
  * with someone left; teams of more than 6 are never counted by the game.

Then, for the team: a DelayBehavior (the engine's "wait N seconds", type 0x12)
goes on top of its script for 30 s. The team's own plan -- the engagement
(OpenFight etc.) and the mission plan under it -- is suspended, not lost, so
OpenFight's re-plans cannot send the survivors forward again or stack probes
on them while they go; the Delay's state type is set to 2 ("engaged") so that
FireTeamAI::UpdateEnemyList treats the team as already fighting and stacks no
new engagement on it (the test it applies to TeamEngagement itself; read from
the code -- the savestates had no new contact during the pause to show it).
After 30 s the Delay ends and the team fights on from where it now is.

And for every surviving member who is hostile, taking orders (AcceptingOrders)
and not fleeing, a hostage, a captive or riding (top types 0x18-0x1B): his
script is cleared and a RunForCoverBehavior is put on it, built as OpenFight
builds one (new 0x44, the constructor, the threat at +0x18), its cover point
chosen here: the nearest free cover point (RSCoverPoint, the level's array at
RSLevel +0x78/+0x7C, 36 bytes each, +0x21 taken) of the level he stands on
(SimHuman +0x58) that is at least 10 m farther from the enemy than he is,
within 40 m of him, with the enemy inside its arc (RSCoverPoint::Is-
LocationWithinCoverArc, inline: a radius covers every side, else edge A x
(enemy - cover) >= 0 and edge B x (enemy - cover) > 0). RunForCoverBehavior::
SetCoverPoint (the stock call) sets where he stands and reserves the point, so
team-mates take different ones. When there is none, RunForCover runs its own
search, as it always does (cover from the enemy within 50 m, which may be where
he is). The game's flee search (SearchForCoverPointBetween2Points) was tried
first and rejected: it walks its voxel grid only from the lower to the higher
index on each axis (GR, read), and in JS it returned nothing for two
retreats toward +x -y that had 21 and 17 cover points meeting its own tests.

RunForCover is the stock "break contact" order: he runs (crouched when under
heavy fire), fires only at an enemy closer than the point he is running to
(HumanAI::UpdateCombat's rule for type 0xA), and at the cover crouches, takes
the cover and scans toward the enemy +-45 degrees every 3 s. His script is then
empty, so he engages anyone he sees. Survivors stay armed, on their own level,
within 40 m, and fight back: "kill all" objectives are still completable.

Search (js_enemy_search / gr_enemy_search)
------------------------------------------

As shipped, an enemy who loses sight of you side-steps and looks at the spot
(EngageThreat "clearing LOS"), and when his awareness of you lapses the
engagement ends and he stands where he is: in savestate FF7CE6B7.01 a whole
5-man team stands with empty scripts 17 s after losing contact, 114 m from
where they last saw the player. EngageThreatBehavior::Process calls
HumanAI::SetCurrentThreat every frame it runs, so HumanAI +0x64 is the threat's
id, +0x68 his position on the last frame engaged (the last known position) and
+0x74 that frame's time; HumanAI::Update forgets the threat 30 s later.

HumanAI::UpdateMorale -- the dead morale check above, whose only caller is
HumanAI::Update (move a0, s0; jal) and whose answer nobody reads -- is replaced
by `srch`. Run as shipped for 423 soldiers in five savestates it changed no
byte of RAM, so the replacement takes nothing away. For a soldier who is:

  * hostile, with a threat, 5 to 12 s after he last had it engaged (5 s: what
    "a few seconds" means here; up to 12: a soldier busy for the first seconds
    -- suppressing the spot, say -- still goes),
  * more than 4 m from the last known position,
  * idle (empty script) or holding a CoverArea that is not ours,
  * in a team in an open fight (TeamEngagement 0x1D with OpenFight 0x29 in its
    own script) or with no plan left (empty team script: the fight is over, or
    a post with no plan) -- not a team defending a zone, a building or a
    vehicle, nor a patrol or path the team has gone back to,
  * taking orders, with ground under the last known position (RSSimScene::
    FindLevel),

his script gets, on top of what he had: a CoverAreaBehavior (pool) at the
spot, half-arc 3.0 rad -- the whole circle, and the mark that says "searched" --
ending 20 s from now, and on top of that a LocationBehavior (pool) to the spot
on that level. He walks there (engaging anyone he sees on the way: Location is
not a type UpdateCombat holds fire for), then looks all round it, a new look
every 3 s, firing at what he sees, until the 20 s are up; then what he had
before comes back (verified: OpenFight's CoverArea and probes under it). A
move that ends at once (no path) leaves our sweep on top, which blocks a new
order, so nothing repeats; the window closes 12 s after contact.

Who wins when (no option edits another's words)
-----------------------------------------------

  * Sight beats everything: UpdateCombat puts EngageThreat on top of a moving
    or sweeping searcher, and a falling-back soldier fires at anyone closer
    than his cover.
  * Enemies suppress (grsuppress): its 3-7 s of fire at the spot the frame
    sight is lost comes first; the search waits while Suppress is on top and
    starts after it if still inside the 12 s.
  * Advance / flank / hold cover (grtactics): a soldier carrying out a probe is
    left to it (busy). A searcher (Location on top) within 50 m of the enemy's
    reported position is "busy" to OpenFight (the stock suppress-or-hold roll,
    not tac_roll); farther out OpenFight may stack a probe on him, which goes
    the same way and hands back to the search when it ends. A hold-cover
    CoverArea gets the search on top during the window and is back after the
    sweep. A broken team's OpenFight is suspended under the Delay for 30 s --
    morale beats tactics -- after which tactics resume from the new position.
  * Morale beats search: a broken team's top is the Delay, so its men do not
    walk back toward you; by the time the Delay ends the contact is past 12 s.
  * Hearing (grawareness) drives investigation by idle teams that patrol and
    posted guards' scans before a fight; search only acts after an engagement
    (+0x64 set by EngageThreat). No overlap.

Online co-op: the AI runs on the host, so only the host's disc matters; every
console carries the same words. Neither routine draws a random number or
creates anything a joiner would have to create.

Verified in the interpreter (scratchpad ai2/M: vt_morale.py, vt_search.py,
t_update.py, t_purity.py) over savestate RAM with the option words written in:
JS 55EBB12A.01 / FF7CE6B7.01 / D2052FC1.02, GR 3D55F8ED.01. Not yet played.
"""

from __future__ import annotations

import struct

from .grasm import Asm, assemble
from .model import BOOL, CHOICE, Choice, Setting

# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------

#: per game: engine functions and objects the routines call or read
SYMS = {
    "js": dict(
        UTS=0x003DC5A0,         # FireTeamAI::UpdateTeamStatus(team, &out, &active, &wounded)
        CLOSEST=0x003DBAE0,     # FireTeamAI::GetClosestEnemy(team, &pos, bool) -> EnemyStruct (+4 position)
        GETHAI=0x003DF0F0,      # FireTeamAI::GetHumanAI(team, index)
        ACCEPT=0x003E4260,      # HumanAI::AcceptingOrders
        NEW=0x00103470,         # operator new
        DELAYCT=0x001ACBB0,     # DelayBehavior::DelayBehavior (0x20 bytes, type 0x12)
        ADDEL=0x001B6E10,       # RSScript::AddElement(script, behaviour) -- on top
        CLEAR=0x001B7140,       # RSScript::ClearScript
        RFCCT=0x001B7460,       # RunForCoverBehavior::RunForCoverBehavior (0x44 bytes, type 0xA)
        SETCP=0x001B75A0,       # RunForCoverBehavior::SetCoverPoint(rfc, ai, coverpoint, level)
        SCENE=0x00689E30,       # RSSimScene*
        CLOCK=0x00684768,       # RSClock* (+0xD4 seconds)
        AIMGR=0x0062C6F8,       # IkeAIMgr*
        COVPOOL=0x003F1BE0,     # IkeAIMgr::GetPoolCoverAreaBehavior
        LOCPOOL=0x003F1BC0,     # IkeAIMgr::GetPoolLocationBehavior
        SETLOC=0x001B2810,      # LocationBehavior::SetLocation(loc, &point, level)
        FINDLEVEL=0x004EB6B0,   # RSSimScene::FindLevel(scene, &point)
    ),
    "gr": dict(
        UTS=0x0018BC70, CLOSEST=0x0018B130, GETHAI=0x0018EAD0, ACCEPT=0x00193F80, NEW=0x00102DB0,
        DELAYCT=0x001B0BD0, ADDEL=0x001BAEC0, CLEAR=0x001BAAE0, RFCCT=0x001BB870, SETCP=0x001BB660,
        SCENE=0x006376D0, CLOCK=0x005DFC20, AIMGR=0x005E5778,
        COVPOOL=0x001A1CC0, LOCPOOL=0x001A1CA0, SETLOC=0x001B7310, FINDLEVEL=0x00504690,
    ),
}

# ---------------------------------------------------------------------------
# Morale: FireTeamAI::Update's call to UpdateTeamStatus goes through `mor`
# ---------------------------------------------------------------------------

#: setting value -> K: the team breaks when K x (members still in action) <= members
THRESHOLDS = {"half": 2, "two_thirds": 3}
PAUSE = 30.0            # s the team's own plan waits while the survivors fall back
BACK = 10.0             # m: a cover point must be at least this much farther from the enemy than he is
RANGE = 40.0            # m: ... and no farther than this from him

MOR_SRC = """
mor:                                ; a0 team, a1 &out of action, a2 &in action, a3 &wounded
    addiu sp, sp, -0x80
    sd    ra, 0x78(sp)
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s2, 0x20(sp)
    sq    s3, 0x30(sp)
    sq    s4, 0x40(sp)
    sq    s5, 0x50(sp)
    sq    s6, 0x60(sp)
    move  s0, a0
    jal   UTS                       ; the stock count; it updates +0xD0
    lw    s1, 0xD0(a0)              ; (delay) members in action before
    lw    t0, 0xD0(s0)              ; members in action now
    beqz  t0, mo_out                ; nobody left
    lw    t1, 0x18(s0)              ; (delay) members
{KNOW}    slt   v0, t1, t2
    bnez  v0, mo_out                ; members < K x now: not broken
{KBEFORE}    slt   v0, t1, t3
    beqz  v0, mo_out                ; members >= K x before: broken already, not just now
    move  a0, s0                    ; (delay)
    addiu a1, s0, 0xC4              ; the team's position
    jal   CLOSEST                   ; the closest enemy it knows of
    move  a2, zero
    beqz  v0, mo_out                ; none: nothing to fall back from
    move  s3, v0                    ; (delay)
    sw    zero, 0x70(sp)            ; the team's pause not pushed yet
    move  s2, zero                  ; member index
mo_loop:
    lw    t0, 0x18(s0)
    slt   t0, s2, t0
    beqz  t0, mo_out
    move  a0, s0                    ; (delay)
    jal   GETHAI
    move  a1, s2
    beqz  v0, mo_next
    move  s1, v0                    ; (delay) his HumanAI
    lw    t0, 0x14(s1)              ; SimHuman
    beqz  t0, mo_next
    nop
    lw    t0, 0x458(t0)
    lbu   t0, 0xB7(t0)              ; SimHuman::IsEnemy's own test
    beqz  t0, mo_next               ; not hostile
    lw    t0, 0xC(s1)               ; (delay) his script
    lw    t0, 4(t0)
    beqz  t0, mo_ok
    nop
    lw    t0, 4(t0)
    addiu t0, t0, -0x18
    sltiu t0, t0, 4
    bnez  t0, mo_next               ; fleeing, hostage, captive or riding: leave him be
mo_ok:
    nop
    jal   ACCEPT                    ; alive and taking orders
    move  a0, s1
    beqz  v0, mo_next
    lw    t0, 0x70(sp)              ; (delay)
    bnez  t0, mo_rfc
    nop
    jal   NEW                       ; the team's own plan waits while they go
    li    a0, 0x20
    beqz  v0, mo_rfc
    sw    v0, 0x70(sp)              ; (delay) pushed (a failed allocation is retried)
    jal   DELAYCT
    move  a0, v0
    lui   t0, {PAUSE}
    sw    t0, 0x18(v0)              ; seconds
    li    t0, 2
    sw    t0, 8(v0)                 ; reads as "engaged": UpdateEnemyList stacks no new fight on it
    lw    a0, 0xC(s0)
    jal   ADDEL
    move  a1, v0
mo_rfc:
    jal   NEW
    li    a0, 0x44
    beqz  v0, mo_next
    nop
    jal   RFCCT                     ; the game's RunForCover, built as OpenFight builds one
    move  a0, v0
    move  s4, v0
    lwc1  f0, 4(s3)
    lwc1  f1, 8(s3)
    lwc1  f2, 0xC(s3)
    swc1  f0, 0x18(s4)              ; the threat it runs from
    swc1  f1, 0x1C(s4)
    swc1  f2, 0x20(s4)
    lw    t0, 0x14(s1)
    lw    s5, 0x58(t0)              ; the level he stands on
    beqz  s5, mo_push               ; none: RunForCover searches as it always does
    lwc1  f2, 0x2C(s1)              ; (delay)
    sub.s f2, f2, f0
    lwc1  f3, 0x30(s1)
    sub.s f3, f3, f1
    mul.s f2, f2, f2
    mul.s f3, f3, f3
    add.s f2, f2, f3
    sqrt.s f2, f2                   ; his distance from the enemy
    lui   t0, {BACK}
    mtc1  t0, f3
    add.s f2, f2, f3
    mul.s f7, f2, f2                ; f7: cover must be at least this far from the enemy (squared)
    lui   t0, {RANGE2}
    mtc1  t0, f8                    ; f8: the nearest so far (squared), at most RANGE
    mtc1  zero, f9
    move  s6, zero                  ; the cover point chosen
    lw    t1, 0x78(s5)              ; the level's cover points (36 bytes each)
    lw    t2, 0x7C(s5)              ; and their count
cp_loop:
    blez  t2, cp_done
    addiu t2, t2, -1                ; (delay)
    lbu   t3, 0x21(t1)
    bnez  t3, cp_next               ; someone has it
    lwc1  f0, 0(t1)                 ; (delay)
    lwc1  f1, 4(t1)
    lwc1  f2, 0x2C(s1)
    sub.s f2, f0, f2
    lwc1  f3, 0x30(s1)
    sub.s f3, f1, f3
    mul.s f2, f2, f2
    mul.s f3, f3, f3
    add.s f2, f2, f3                ; from him (squared)
    c.lt.s f2, f8
    bc1f  cp_next                   ; no nearer than the one he has
    lwc1  f4, 4(s3)                 ; (delay)
    sub.s f4, f4, f0                ; to the enemy: dx
    lwc1  f5, 8(s3)
    sub.s f5, f5, f1                ; dy
    mul.s f0, f4, f4
    mul.s f1, f5, f5
    add.s f0, f0, f1
    c.lt.s f0, f7
    bc1t  cp_next                   ; not far enough back
    lwc1  f0, 0xC(t1)               ; (delay) a radius: round cover, covers every side
    c.lt.s f9, f0
    bc1t  cp_take
    lwc1  f0, 0x10(t1)              ; (delay) RSCoverPoint::IsLocationWithinCoverArc, inline:
    lwc1  f1, 0x14(t1)
    mul.s f0, f0, f5
    mul.s f1, f1, f4
    sub.s f0, f0, f1                ; edge A x (enemy - cover) >= 0
    c.lt.s f0, f9
    bc1t  cp_next
    lwc1  f0, 0x18(t1)              ; (delay)
    lwc1  f1, 0x1C(t1)
    mul.s f0, f0, f5
    mul.s f1, f1, f4
    sub.s f0, f0, f1                ; edge B x (enemy - cover) > 0
    c.lt.s f9, f0
    bc1f  cp_next
    nop
cp_take:
    mov.s f8, f2
    move  s6, t1
cp_next:
    b     cp_loop
    addiu t1, t1, 36                ; (delay)
cp_done:
    beqz  s6, mo_push               ; no cover back there: RunForCover searches as it always does
    move  a0, s4                    ; (delay)
    move  a1, s1
    move  a2, s6
    jal   SETCP                     ; that cover point is where he runs (and it is his now)
    move  a3, s5
mo_push:
    jal   CLEAR                     ; what he was doing is dropped
    lw    a0, 0xC(s1)
    lw    a0, 0xC(s1)
    jal   ADDEL
    move  a1, s4
mo_next:
    b     mo_loop
    addiu s2, s2, 1
mo_out:
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    lq    s3, 0x30(sp)
    lq    s4, 0x40(sp)
    lq    s5, 0x50(sp)
    lq    s6, 0x60(sp)
    ld    ra, 0x78(sp)
    jr    ra
    addiu sp, sp, 0x80
"""

#: K x t0 -> t2 and K x s1 -> t3
MUL = {2: ("    addu  t2, t0, t0\n", "    addu  t3, s1, s1\n"),
       3: ("    addu  t2, t0, t0\n    addu  t2, t2, t0\n", "    addu  t3, s1, s1\n    addu  t3, t3, s1\n")}

# ---------------------------------------------------------------------------
# Search: HumanAI::UpdateMorale (a stub whose answer is never used) becomes `srch`
# ---------------------------------------------------------------------------

DELAY = 5.0             # s after sight was lost before he moves in
WINDOW = 12.0           # s: the move starts no later than this after sight was lost
NEAR = 4.0              # m: closer than this to the spot, he is there
SWEEP_ARC = 3.0         # rad half-arc of the CoverArea at the spot (all round; marks it as ours)
SWEEP = 20.0            # s the CoverArea at the spot lasts, counted from the order

SRCH1_SRC = """
srch:                               ; a0 HumanAI (HumanAI::Update calls this every frame)
    lw    t0, 0x64(a0)              ; the threat he last engaged (-1 none)
    bltz  t0, sr_no
    lw    t1, 0x14(a0)              ; (delay) SimHuman
    beqz  t1, sr_no
    lw    t2, 0xA4(a0)              ; (delay) his fire team
    beqz  t2, sr_no
    lw    t1, 0x458(t1)             ; (delay)
    lbu   t1, 0xB7(t1)
    beqz  t1, sr_no                 ; not hostile
    lui   t3, %hi(CLOCK)            ; (delay)
    lw    t3, %lo(CLOCK)(t3)
    lwc1  f0, 0xD4(t3)              ; now
    lwc1  f1, 0x74(a0)              ; the last frame he had him engaged
    sub.s f0, f0, f1
    lui   t3, {DELAY}
    mtc1  t3, f1
    c.lt.s f0, f1
    bc1t  sr_no                     ; lost him only just now
    lui   t3, {WINDOW}              ; (delay)
    mtc1  t3, f1
    c.lt.s f0, f1
    bc1f  sr_no                     ; long ago: this contact is over
    lwc1  f0, 0x2C(a0)              ; (delay)
    lwc1  f1, 0x68(a0)              ; the last known position
    sub.s f0, f0, f1
    lwc1  f1, 0x30(a0)
    lwc1  f2, 0x6C(a0)
    sub.s f1, f1, f2
    mul.s f0, f0, f0
    mul.s f1, f1, f1
    add.s f0, f0, f1
    lui   t3, {NEAR2}
    mtc1  t3, f1
    c.lt.s f0, f1
    bc1t  sr_no                     ; he is there
    lw    t3, 0xC(a0)               ; (delay) his script
    lw    t3, 4(t3)
    beqz  t3, sr_go                 ; standing with nothing to do
    nop
    lw    t4, 4(t3)
    addiu t4, t4, -0x13
    bnez  t4, sr_no                 ; busy (moving, firing, throwing...): not now
    lui   t4, {SWEEP_ARC}           ; (delay)
    lw    t5, 0x34(t3)
    beq   t4, t5, sr_no             ; holding our own sweep: he has searched
sr_go:
    nop
    j     SRCH2
    nop
sr_no:
    jr    ra
    nop
"""

SRCH2_SRC = """
sr2:                                ; a0 HumanAI, t2 his team: he lost sight of his enemy 5-12 s ago
    lw    t3, 0xC(t2)               ; the team's script
    lw    t3, 4(t3)
    beqz  t3, s2_go                 ; no plan left (its fight over, or a post with no plan): go
    nop
    lw    t4, 4(t3)
    addiu t4, t4, -0x1D
    bnez  t4, s2_no                 ; on its plan (patrol, path, holding an area...): stays with it
    lw    t3, 0xC(t3)               ; (delay) the engagement's own script
    lw    t3, 4(t3)
    beqz  t3, s2_no
    nop
    lw    t4, 4(t3)
    addiu t4, t4, -0x29
    bnez  t4, s2_no                 ; defending a zone, a building, a vehicle...: he stays
    nop
s2_go:
    addiu sp, sp, -0x30
    sd    ra, 0x20(sp)
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    jal   ACCEPT                    ; alive and taking orders
    move  s0, a0                    ; (delay)
    beqz  v0, s2_out
    lui   a0, %hi(SCENE)            ; (delay)
    lw    a0, %lo(SCENE)(a0)
    jal   FINDLEVEL                 ; ground under the last known position?
    addiu a1, s0, 0x68
    beqz  v0, s2_out
    move  s1, v0                    ; (delay) its level
    lui   a0, %hi(AIMGR)
    jal   COVPOOL                   ; the sweep at the spot, under the move
    lw    a0, %lo(AIMGR)(a0)
    lwc1  f0, 0x68(s0)
    swc1  f0, 0x1C(v0)              ; facing the spot (from on it: his own facing)
    lwc1  f0, 0x6C(s0)
    swc1  f0, 0x20(v0)
    lwc1  f0, 0x70(s0)
    swc1  f0, 0x24(v0)
    lui   t0, {SWEEP_ARC}
    sw    t0, 0x34(v0)              ; the whole circle
    lui   t0, %hi(CLOCK)
    lw    t0, %lo(CLOCK)(t0)
    lwc1  f0, 0xD4(t0)
    lui   t0, {SWEEP}
    mtc1  t0, f1
    add.s f0, f0, f1
    swc1  f0, 0x40(v0)              ; until
    lw    a0, 0xC(s0)
    jal   ADDEL
    move  a1, v0
    lui   a0, %hi(AIMGR)
    jal   LOCPOOL                   ; the move to the spot, on top
    lw    a0, %lo(AIMGR)(a0)
    move  a0, v0
    addiu a1, s0, 0x68
    move  a2, s1
    jal   SETLOC
    move  s1, v0                    ; (delay) keep the behaviour
    lw    a0, 0xC(s0)
    jal   ADDEL
    move  a1, s1
s2_out:
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    ld    ra, 0x20(sp)
    addiu sp, sp, 0x30
s2_no:
    jr    ra
    nop
"""


def _hi(f):
    b = struct.unpack("<I", struct.pack("<f", f))[0]
    assert b & 0xFFFF == 0, f
    return "%#x" % (b >> 16)


def mor_src(k):
    kn, kb = MUL[k]
    return MOR_SRC.format(KNOW=kn, KBEFORE=kb, PAUSE=_hi(PAUSE), BACK=_hi(BACK), RANGE2=_hi(RANGE * RANGE))


def srch1_src():
    return SRCH1_SRC.format(DELAY=_hi(DELAY), WINDOW=_hi(WINDOW), NEAR2=_hi(NEAR * NEAR),
                            SWEEP_ARC=_hi(SWEEP_ARC))


def srch2_src():
    return SRCH2_SRC.format(SWEEP_ARC=_hi(SWEEP_ARC), SWEEP=_hi(SWEEP))


def count(src):
    return sum(1 for kind, _ in Asm._items(src) if kind == "ins")


# ---------------------------------------------------------------------------
# Where the routines go
# ---------------------------------------------------------------------------

#: per game: hook sites, caves [(start, end)], the UpdateMorale body the search replaces
LAYOUT = {
    "js": dict(
        MOR_HOOK=(0x003DE304, 0x0C0F7168),          # FireTeamAI::Update: jal UpdateTeamStatus
        MOR=[(0x001802B8, 0x00180458),              # sceGetstat twin (104 words)
             (0x0018CDDC, 0x0018CEAC),              # dead function (52 words)
             (0x00182A78, 0x00182AD8),              # dead function (24 words)
             (0x0019638C, 0x001963F8)],             # dead function (27 words)
        MORALE_FN=(0x003E8F70, 0x003E9040),         # HumanAI::UpdateMorale (52 words)
        SRCH2=[(0x00196AB8, 0x00196B40),            # dead VU0 helper (34 words)
               (0x00185260, 0x001852D8),            # dead function (30 words)
               (0x0018C46C, 0x0018C4E0)],           # dead function (29 words)
    ),
    "gr": dict(
        MOR_HOOK=(0x0018DD30, 0x0C062F1C),
        MOR=[(0x00416090, 0x004162C8),              # sceLseek (142 words)
             (0x00417210, 0x0041732C)],             # sceFormat, after the search (71 words)
        MORALE_FN=(0x00198F00, 0x00198FD0),
        SRCH2=[(0x00417108, 0x00417210)],           # sceFormat, after another option's words (66 words)
    ),
}

_BRANCH = {"b", "beq", "bne", "beqz", "bnez", "blez", "bgtz", "bltz", "bgez", "bc1f", "bc1t",
           "j", "jal", "jr", "jalr"}


def place(src, caves, syms, what):
    """Assemble `src` across `caves` [(start, end), ...]: where one fills up, a `j` to the next is
    put in (never between a branch and its delay slot). Labels are global, so a branch may reach
    into another cave when it is in range (the assembler refuses one that is not).
    -> ([(va, word)], labels). Same approach as grawareness's islands."""
    items = Asm._items(src)
    left = sum(1 for kind, _ in items if kind == "ins")
    caves = list(caves)
    pc, end = caves.pop(0)
    placed, labels, pending, slot = [], {}, [], False
    for kind, x in items:
        if kind == "label":
            pending.append(x)
            continue
        need = 2 if x.split()[0] in _BRANCH else 1
        if not slot and pc + 4 * left > end and pc + 4 * (need + 2) > end:
            if not caves:
                raise ValueError("%s routine outgrows its caves" % what)
            placed += [(pc, "j %#x" % caves[0][0]), (pc + 4, "nop")]
            pc, end = caves.pop(0)
        labels.update((p, pc) for p in pending)
        pending = []
        placed.append((pc, x))
        pc, left, slot = pc + 4, left - 1, need == 2
    if pc > end:
        raise ValueError("%s routine outgrows its caves" % what)
    syms = dict(syms, **labels)
    return [(va, assemble(x, va, syms)[0][0]) for va, x in placed], labels


def morale_words(game, k):
    return place(mor_src(k), LAYOUT[game]["MOR"], SYMS[game], "morale")


def search_words(game):
    """(part 2 placed, labels2), (part 1 placed over UpdateMorale, labels1)."""
    w2, l2 = place(srch2_src(), LAYOUT[game]["SRCH2"], SYMS[game], "search")
    w1, l1 = place(srch1_src(), [LAYOUT[game]["MORALE_FN"]], dict(SYMS[game], SRCH2=l2["sr2"]), "search")
    return (w2, l2), (w1, l1)


# ---------------------------------------------------------------------------
# Stock words: every word an option here can write
# ---------------------------------------------------------------------------

_JS_MOR1_HEX = (   # 0x001802B8..0x00180458, sceGetstat twin
    "27BDFF30 FFB10050 FFB600A0 0080882D FFB700B0 00A0B02D FFB20060 2404000C"
    "FFBF00C0 3C170061 FFB50090 26F27000 FFB40080 FFB30070 0C05F8CC FFB00040"
    "3C020057 8C434FEC 54600004 92220000 0C05F918 00000000 92220000 0000802D"
    "0040182D 1060000E A2420010 27B30030 3C150062 3C140061 26100001 2A020400"
    "1040000A 02301021 02502021 90430000 1460FFF9 A0830010 10000005 24020400"
    "27B30030 3C150062 3C140061 24020400 56020004 AE56000C A240040F 241003FF"
    "AE56000C 24020001 AFA20014 27A40010 AFA00018 26947C40 0C05E8B8 AFA00024"
    "0040882D AE530004 24020004 AE510000 AE420008 26A48700 26E77000 26080011"
    "AFA00000 2405000C 0000302D 0280482D 240A0004 0C05F5AA 0000582D 04410007"
    "3C022000 0C05E8BC 0220202D 0C05F8D8 00000000 1000000F 2402FFF5 02821025"
    "0C05F8D8 8C500000 16000005 00000000 0C05E8BC 0220202D 10000006 2402FFF5"
    "0C05E8C8 0220202D 0C05E8BC 0220202D 8FA20030 DFBF00C0 DFB700B0 DFB600A0"
    "DFB50090 DFB40080 DFB30070 DFB20060 DFB10050 DFB00040 03E00008 27BD00D0"
)
_JS_MOR2_HEX = (   # 0x0018CDDC..0x0018CEAC, a dead function and the pad word before it
    "00000000 27BDFFA0 3C020062 FFB20030 FFB10020 2452C500 FFB00010 00A0882D"
    "FFBF0050 FFB30040 8E420024 14400003 0080802D 1000001F 2402FF9C 3C130057"
    "0C05E8CC 8E646634 04410003 3C070062 10000018 2402FF38 3C090062 24E7C580"
    "3C0B0019 ACF00004 0240202D ACF10008 2529DAC0 256BBA10 AFA00000 24050011"
    "24060001 24080030 0C05F5AA 240A0004 0040802D 16000004 3C030057 24020011"
    "10000003 AC626630 0C05E8C0 8E646634 0200102D DFBF0050 DFB30040 DFB20030"
    "DFB10020 DFB00010 03E00008 27BD0060"
)
_JS_SRCH2A_HEX = (   # 0x00196AB8..0x00196B40, a dead VU0 helper
    "27BDFFB0 FFB20020 FFB10010 0080902D FFB00000 00A0882D E7B40040 00C0802D"
    "FFBF0030 0C060CC8 46006506 DA240000 DA050000 4408A000 48A83000 4B0001C3"
    "4B063A2C 4BE621BC 4BE82A48 FA490000 10400007 DFBF0030 DFB20020 DFB10010"
    "DFB00000 C7B40040 08060CDE 27BD0050 DFB20020 DFB10010 DFB00000 C7B40040"
    "03E00008 27BD0050"
)
_JS_SRCH2B_HEX = (   # 0x00185260..0x001852D8, a dead function
    "27BDFFE0 00041202 FFB00000 FFBF0010 04800006 00028100 8E020004 00821026"
    "304200FF 10400004 00000000 3C028000 1000000D 34428002 8E040004 0C06117A"
    "00000000 0040202D 14800007 0080102D 3C020062 8C43C2C0 AC50C2C0 AE030000"
    "AE000004 0080102D DFBF0010 DFB00000 03E00008 27BD0020"
)
_JS_SRCH2C_HEX = (   # 0x0018C46C..0x0018C4E0, a dead function and the pad word before it
    "00000000 27BDFFD0 3C040062 FFB00010 3C070062 3C100062 3C0B0019 FFBF0020"
    "2484C500 24E7C580 256BBA10 AFA00000 24050035 0000302D 24080030 2609DAC0"
    "0C05F5AA 240A0004 10400005 3C040058 0C05F142 24842878 10000002 2402FFFF"
    "8E02DAC0 DFBF0020 DFB00010 03E00008 27BD0030"
)
_JS_MOR3_HEX = (   # 0x00182A78..0x00182AD8, a dead function
    "27BDFFD0 3C020057 FFB00000 FFB10010 3C100018 26102FC0 0080882D AC515348"
    "0200282D FFBF0020 0C05E7E4 24040001 0200282D 0C05E7E4 24040002 0200282D"
    "0C05E7E4 24040003 0220102D DFBF0020 DFB10010 DFB00000 03E00008 27BD0030"
)
_JS_MOR4_HEX = (   # 0x0019638C..0x001963F8, a dead function and the pad word before it
    "00000000 27BDFFD0 3C020062 FFB00010 24060014 2450DF40 FFBF0020 AE040004"
    "3C030062 AC46DF40 24050001 2464DD00 AFA00000 0000302D 0200382D 24080080"
    "0200482D 240A0080 0C05F5AA 0000582D 04430002 8E020008 0000102D DFBF0020"
    "DFB00010 03E00008 27BD0030"
)
_JS_UPDATEMORALE_HEX = (   # 0x003E8F70..0x003E9040, HumanAI::UpdateMorale
    "27BDFFD0 FFBF0020 7FB10010 7FB00000 8C8300A4 10600029 0080802D 0C0FB2E4"
    "00000000 0C0F9098 0200202D 10400023 00000000 8E040014 3C010061 8C990000"
    "8F390344 0320F809 8C314280 8E390000 0220202D 8F39012C 0320F809 0040282D"
    "9043000C 14600015 00000000 8E04011C 24030003 14830011 00000000 0C0F71D0"
    "8E0400A4 28410002 1020000C 00000000 8E0300A4 8C630018 00621823 18600007"
    "00000000 C6010164 3C033F00 44830000 00000000 46000836 00000000 DFBF0020"
    "7BB10010 7BB00000 03E00008 27BD0030"
)
_GR_MOR_HEX = (   # 0x00416090..0x004162C8, sceLseek
    "27BDFF40 FFB40080 FFB20060 00C0A02D FFB50090 00A0902D FFB10050 3C15005F"
    "FFB00040 26B1E100 FFBF00B0 FFB600A0 0C10551E FFB30070 0040802D 0C10563E"
    "24040004 3C030057 8C62E1C0 14400005 00000000 0C10564A 00000000 1000006C"
    "2402FFFF 12000004 00000000 8E130004 16600005 3C02005F 0C10564A 00000000"
    "10000063 2402FFF7 8E030000 2442F1C0 AE320010 02021023 AE23000C 00021103"
    "AE340014 AE220018 24050001 27A40010 AFA50014 AFA00018 0C1046B8 AFA00024"
    "0040902D 24030004 27A20030 AE230008 AE220004 32628000 10400024 AEB2E100"
    "3C140057 0C1046C8 8E84E1CC 3C070057 0000302D 8CE3E140 2402FFFF 14620008"
    "3C16005F 8EA3E100 3C10005F 00031023 ACE3E140 10000011 AEA2E100 00000000"
    "3C10005F 24C60001 28C20020 1040000B 00061080 24E3E140 00432821 2404FFFF"
    "8CA20000 1444FFF8 24C60001 8E220000 00021823 ACA20000 AE230000 0C1046C0"
    "8E84E1CC 10000004 2610ED40 3C16005F 3C10005F 2610ED40 26C4F3C0 26A7E100"
    "AFA00000 24050004 0000302D 2408001C 0200482D 240A0004 0C10531C 0000582D"
    "04410007 3C022000 0C1046BC 0240202D 0C10564A 00000000 10000015 2402FFF5"
    "02021025 0C10564A 8C500000 16000005 32628000 0C1046BC 0240202D 1000000C"
    "2402FFF5 10400005 00000000 0C1046BC 0240202D 10000006 0000102D 0C1046C8"
    "0240202D 0C1046BC 0240202D 8FA20030 DFBF00B0 DFB600A0 DFB50090 DFB40080"
    "DFB30070 DFB20060 DFB10050 DFB00040 03E00008 27BD00C0"
)
_GR_SRCH2_HEX = (   # 0x00417108..0x00417210, sceFormat past the words another option writes
    "3C020057 8C43E1C0 54600004 92020000 0C10567E 00000000 92020000 0000282D"
    "00021E00 1060000F A262000C 2A270401 24A50001 00000000 28A20400 1040000A"
    "02051021 02652021 90430000 A083000C 00031E00 5460FFF8 24A50001 10000003"
    "24020400 2A270401 24020400 50A20001 A260040B 56400003 92420000 10000014"
    "A260040C 0000282D 00021E00 1060000D A262040C 2666040C 24A50001 00000000"
    "28A20400 10400007 02451021 00C52021 90430000 A0830000 00031E00 5460FFF8"
    "24A50001 24020400 50A20001 A260080B 14E00005 00000000 0C10564A 00000000"
    "10000045 2402FFF9 1A20000F 0000282D 2666080C 27B20030 3C15005F 3C14005F"
    "02C51021 00C52021"
)
_GR_MOR2_HEX = (   # 0x00417210..0x0041732C, the rest of the sceFormat run
    "90430000 24A50001 00B1102A A0830000 1440FFF9 00000000 10000005 AE710C0C"
    "27B20030 3C15005F 3C14005F AE710C0C 24020001 AFA20014 27A40010 AFA00018"
    "26F0E100 AFA00024 0C1046B8 2694ED40 0040882D 0200202D 24020004 AE720004"
    "AE620008 24050C10 0C1050E0 AE710000 26A4F3C0 0200382D AFA00000 2405000E"
    "0000302D 24080C10 0280482D 240A0004 0C10531C 0000582D 04410007 3C022000"
    "0C1046BC 0220202D 0C10564A 00000000 1000000F 2402FFF5 02821025 0C10564A"
    "8C500000 16000005 00000000 0C1046BC 0220202D 10000006 2402FFF5 0C1046C8"
    "0220202D 0C1046BC 0220202D 8FA20030 DFBF00C0 DFB700B0 DFB600A0 DFB50090"
    "DFB40080 DFB30070 DFB20060 DFB10050 DFB00040 03E00008 27BD00D0"
)
_GR_UPDATEMORALE_HEX = (   # 0x00198F00..0x00198FD0, HumanAI::UpdateMorale
    "27BDFFD0 FFBF0020 7FB10010 7FB00000 8C8300A4 10600029 70808628 0C067320"
    "00000000 0C064FE0 72002628 10400023 00000000 8E040014 3C01005E 8C990000"
    "8F390340 0320F809 8C314FA8 8E390000 72202628 8F390124 0320F809 70402E28"
    "9043000C 14600015 00000000 8E04011C 24030003 14830011 00000000 0C062F90"
    "8E0400A4 28410002 1020000C 00000000 8E0300A4 8C630018 00621823 18600007"
    "00000000 C6010164 3C033F00 44830000 00000000 46000836 00000000 DFBF0020"
    "7BB10010 7BB00000 03E00008 27BD0030"
)


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())            # fixed 8-digit words, never .split() alone
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


JS_STOCK = {}
for _a, _h in ((0x001802B8, _JS_MOR1_HEX), (0x0018CDDC, _JS_MOR2_HEX), (0x00196AB8, _JS_SRCH2A_HEX),
               (0x00185260, _JS_SRCH2B_HEX), (0x0018C46C, _JS_SRCH2C_HEX), (0x00182A78, _JS_MOR3_HEX),
               (0x0019638C, _JS_MOR4_HEX), (0x003E8F70, _JS_UPDATEMORALE_HEX)):
    JS_STOCK.update(_stock_words(_a, _h))
JS_STOCK[LAYOUT["js"]["MOR_HOOK"][0]] = LAYOUT["js"]["MOR_HOOK"][1]
GR_STOCK = {}
for _a, _h in ((0x00416090, _GR_MOR_HEX), (0x00417108, _GR_SRCH2_HEX), (0x00417210, _GR_MOR2_HEX),
               (0x00198F00, _GR_UPDATEMORALE_HEX)):
    GR_STOCK.update(_stock_words(_a, _h))
GR_STOCK[LAYOUT["gr"]["MOR_HOOK"][0]] = LAYOUT["gr"]["MOR_HOOK"][1]
STOCK = {"js": JS_STOCK, "gr": GR_STOCK}


def edits_for(game, morale="off", search=False):
    """(va, value, stock, note); [] when both are off."""
    st, lay = STOCK[game], LAYOUT[game]
    out = []
    if morale in THRESHOLDS:
        words, labels = morale_words(game, THRESHOLDS[morale])
        out += [(va, w, st[va], "enemy morale: a fire team that loses %s falls back"
                 % ("half its men" if morale == "half" else "two thirds of its men")) for va, w in words]
        hook, hook_stock = lay["MOR_HOOK"]
        out.append((hook, assemble("jal %#x" % labels["mor"], hook)[0][0], hook_stock,
                    "enemy morale: FireTeamAI::Update's team count goes through the morale routine"))
    if search:
        (w2, _), (w1, _) = search_words(game)
        out += [(va, w, st[va], "enemy search: the move to the last known position") for va, w in w2]
        out += [(va, w, st[va], "enemy search: HumanAI::UpdateMorale (an unused stub) checks for a lost contact")
                for va, w in w1]
    return out


def js_edits(v: dict):
    return edits_for("js", v.get("js_enemy_morale", "off"), bool(v.get("js_enemy_search")))


def gr_edits(v: dict):
    return edits_for("gr", v.get("gr_enemy_morale", "off"), bool(v.get("gr_enemy_search")))


def cards(prefix: str = "js_", group: str = "Enemies") -> list:
    return [
        Setting(prefix + "enemy_morale", "Enemy teams break and fall back", CHOICE, "off", group,
                confidence="experimental",
                choices=[
                    Choice("off", "Off (as shipped)", "Every fire team fights to the last man."),
                    Choice("half", "When half are down",
                           "A team of 4 breaks at its second man down, a team of 6 at its third."),
                    Choice("two_thirds", "When two thirds are down",
                           "Tougher: a team of 4 breaks at its third man down, a team of 6 at its "
                           "fourth; a pair never breaks."),
                ],
                help="The game has the start of a morale system that was never finished, so every "
                     "enemy fire team fights to the last man. With this, the moment a hostile team "
                     "is down to half its men (dead or incapacitated) -- or a third, with 'two "
                     "thirds' -- while it knows where you are, the survivors stop what they are "
                     "doing and run back to cover: each to the nearest free cover point at least "
                     "10 m farther from you than he was and within 40 m of him (where there is "
                     "none, to the nearest cover the game's own 'run for cover' finds). On the way "
                     "they fire only at someone closer than where they are going; at the cover "
                     "they crouch and watch your direction, and shoot at what they see. Their "
                     "team's own orders wait 30 s while they regroup; then the team fights on "
                     "from there. It happens once per team. Your squad, split-screen and online "
                     "partners' teams are never affected.",
                caution="Never played. Survivors stay armed and within reach, so 'kill all' "
                        "objectives are unchanged. A team cut down by an enemy it has not "
                        "located does not fall back, and the game never counts teams of more "
                        "than 6. Breaking clears each survivor's orders at once; usually that is "
                        "nothing, but a soldier carrying a long pile of stacked orders can cost "
                        "about 10 ms that one frame (measured: 3 million instructions for one "
                        "with 14 stacked orders -- the game itself spends a million clearing the "
                        "dead man's pile in the same frame). Online co-op: only the host's disc "
                        "counts."),
        Setting(prefix + "enemy_search", "Enemies search where they last saw you", BOOL, False, group,
                confidence="experimental",
                help="As shipped, an enemy who loses sight of you looks at the spot, and when "
                     "he gives up simply stands where he is. With this, 5 s after a hostile "
                     "soldier last had you in his sights (up to 12 s if he was busy, say "
                     "suppressing the spot), if he has nothing to do or is holding a covered "
                     "spot, he walks to where he last saw you, firing at anyone he sees on the "
                     "way, then looks all round that spot for the rest of 20 s before going back "
                     "to what he was told. Soldiers whose team is defending a building, a zone "
                     "or a vehicle, or has gone back to its patrol route, stay put. Your squad "
                     "is not affected.",
                caution="Never played. It works with the other enemy options: suppressive fire "
                        "comes first, a soldier already advancing (probing) is left to it, and a "
                        "team that has broken ('Enemy teams break and fall back') does not come "
                        "back to search. Guards at a post with no orders of their own will "
                        "leave it to search. Online co-op: only the host's disc counts."),
    ]


#: every range a word here may be written in (as claimed in the shared caves file), per game
CLAIMED = {
    "gr": [(0x00416090, 0x004162C8), (0x00417108, 0x00417210), (0x00417210, 0x0041732C),
           (0x00198F00, 0x00198FD0), (0x0018DD30, 0x0018DD34)],
    "js": [(0x001802B8, 0x00180458), (0x0018CDDC, 0x0018CEAC), (0x00196AB8, 0x00196B40),
           (0x00185260, 0x001852D8), (0x0018C46C, 0x0018C4E0), (0x00182A78, 0x00182AD8),
           (0x0019638C, 0x001963F8), (0x003E8F70, 0x003E9040), (0x003DE304, 0x003DE308)],
}


def selftest(gr_elf: bytes = None, js_elf: bytes = None, used: dict = None):
    """Stock words against the executables, no address twice, every variant fits its caves and stays in
    the claimed ranges; with `used` ({"gr": set(VA), "js": set(VA)}: the other options' words), no
    overlap. [] = pass."""
    bad = []
    for game, elf, d in (("gr", gr_elf, 0x80), ("js", js_elf, 0x100)):
        st = STOCK[game]
        if elf is not None:
            for va, w in st.items():
                off = va - 0x100000 + d
                if int.from_bytes(elf[off:off + 4], "little") != w:
                    bad.append("%s stock %08X" % (game, va))
        for va in st:
            if not any(lo <= va < hi for lo, hi in CLAIMED[game]):
                bad.append("%s %08X outside the claimed ranges" % (game, va))
        if used:
            clash = sorted(set(st) & set(used.get(game, ())))
            if clash:
                bad.append("%s %d words another option writes, e.g. %08X" % (game, len(clash), clash[0]))
        if edits_for(game, "off", False):
            bad.append("%s off builds words" % game)
        for mo in ("off",) + tuple(THRESHOLDS):
            for se in (False, True):
                try:
                    e = edits_for(game, mo, se)
                except ValueError as ex:
                    bad.append("%s %s/%s: %s" % (game, mo, se, ex))
                    continue
                if len({va for va, *_ in e}) != len(e):
                    bad.append("%s %s/%s duplicate VA" % (game, mo, se))
                if any(va not in st for va, *_ in e):
                    bad.append("%s %s/%s VA without a stock word" % (game, mo, se))
                if any(s != st[va] for va, _, s, _ in e):
                    bad.append("%s %s/%s stock column differs from the table" % (game, mo, se))
        # the search's first part must fit UpdateMorale exactly, and the hook must call the routine
        (w2, l2), (w1, l1) = search_words(game)
        lo, hi = LAYOUT[game]["MORALE_FN"]
        if w1[0][0] != lo or w1[-1][0] >= hi:
            bad.append("%s search part 1 does not sit in UpdateMorale" % game)
        words, labels = morale_words(game, 2)
        hook = [x for x in edits_for(game, "half") if x[0] == LAYOUT[game]["MOR_HOOK"][0]]
        if not hook or ((hook[0][1] & 0x3FFFFFF) << 2) != labels["mor"] or hook[0][1] >> 26 != 3:
            bad.append("%s morale hook is not jal mor" % game)
    return bad

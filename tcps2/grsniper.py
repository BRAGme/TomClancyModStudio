"""Enemy snipers relocate: Jungle Storm (SLUS-20820) and Ghost Recon (SLUS-20613).

How an enemy sniper fights
--------------------------

Neither game has a sniper behaviour. A soldier is a sniper because of the gun
in his hands: SimHuman::IsSniper (GR 0x003DE170, JS 0x003BD860) and
EngageThreatBehavior's ZoomIn both test the firearm's GunFile weapon motion
type (+0xF8) for 2 or 3. Savestates of Jungle Storm missions show the enemy
snipers (guns 14 and 60, motion type 2) in ordinary fire teams -- holding a
CoverArea, in formation, probing or idle, many of them on watchtower decks a
few metres across -- and when one sees you he engages from wherever he
stands (EngageThreatBehavior on top of his script, re-pushed by HumanAI::
UpdateCombat for as long as he sees you) and never moves for it. Once you
know where the shot came from you can pin him there. Ghost Recon's data has
sniper rifles too (gun indices 0, 12, 21, 26, 30, 32, 41, 46 in the two GR
savestates), but no GR savestate holds an enemy carrying one.

What this changes (hostile AI with a sniper rifle only)
-------------------------------------------------------

Every round goes through SimHuman::UpdateBurst. After its round loop (GR
0x003D2E58, JS 0x003B24B4) the stock call there (IIkeRulesMgr::Get /
RSClock::Get) goes through ``sn_shot``, which returns that call's result
untouched and, when the call fired at least one round, the shooter is the AI
(control type +0x138 == 1), hostile (SimHuman +0x458 -> +0xB7, IsEnemy's own
test) and the gun that fired is a sniper rifle (its GunFile motion type 2 or
3, IkeDataMgr vtable +0x4C on the Firearm's gun index), counts the shot on
his HumanAI (IkeAIMgr::GetHumanAI). On the chosen shot -- every shot, or
every second one -- the count starts again and ``sn_move`` gives him a new
firing position:

  * not twice, not from anything special: nothing if a RunForCover is
    anywhere in his script (ours, or the one OpenFight gives), or if the top
    of his script is anything but Location, MoveInFormation, EngageThreat,
    Suppress, CoverArea, Probe or nothing -- riding (0x1B), fragging,
    scripted actions, hostages are left alone;
  * the threat T: the target he is engaging (HumanAI::SetCurrentThreat, which
    EngageThreat refreshes every tick: +0x64 id, +0x68 position, +0x74 time)
    if one was ever set and it is under 5 s old -- the id is -1 until then and
    +0x68 / +0x74 are uninitialised heap (the savestates show garbage there,
    some of it with "fresh-looking" times) -- else the closest enemy his fire
    team knows of (FireTeamAI::GetClosestEnemy +4, what OpenFight hands
    RunForCover); none -> nothing;
  * T closer than 15 m: nothing (a close fight, not sniping);
  * his ground: RSSimScene::FindRoom + RSSimRoom::FindLevelPointIsOver (what
    RSSimScene::FindLevel asks per room) give the height of the floor under
    him; a new spot must have ground within 2 m of it -- on a watchtower the
    ground below is 6-10 m down, so he never steps or runs off his perch;
  * another cover point: the game's own cover search (SearchForCoverPoint,
    the one RunForCover uses) run from a point 8 m behind him (away from T),
    20 m around it: the closest free cover point whose cover arc faces T (his
    own is occupied by him, so never offered). It is taken only if it is at
    least 3 m from him, not nearer T than he is by more than 2 m -- never
    forward into the open -- and its ground (a cover point's z) is within
    2 m of his;
  * else a step out of the line of fire: the first of (4 m back, 6 m to one
    side), (4 back, 6 to the other side), (7 straight back), (1.5 back, 2.5
    to one side), (1.5 back, 2.5 to the other) whose point has ground on his
    own RSLevel within 2 m of his; the side alternates from one move to the
    next (bit 7 of the counter); the short steps keep a sniper on a small
    deck. None -> he stays;
  * then the stock RunForCoverBehavior (new 0x44, its constructor, the threat
    at +0x18) goes on top of his script with that spot already chosen: for a
    cover point RunForCoverBehavior::SetCoverPoint itself (+0x38 set, the
    destination, HumanAI::SetCoverPoint takes the point and frees his old
    one); for a step +0x28 the point on that ground, +0x34 his level, +0x38
    and +0x39 (crouch on arrival) set, and HumanAI::StopUsingCover. Its own
    Process then does the rest -- a LocationBehavior to the spot (stock
    ValidateLocation nudges it off walls), the run, the crouch, the cover, a
    scan toward T -- exactly what RunForCover does after its own search. When
    it ends, what he was doing before resumes from the new spot (EngageThreat
    if he still sees you, his CoverArea, his team's plan). HumanAI::
    UpdateCombat does not interrupt a RunForCover with a new engagement
    unless the threat is nearer than the destination.

The shot count is kept in HumanAI +0x10D (+0x10C is StartUsingCover's byte,
+0x110 the cover point pointer: the bytes between are padding -- no load or
store with offset 0x10D-0x10F touches a HumanAI in either executable or
Jungle Storm's overlays, and none of 0x100/0x108 is a wide access to one),
bit 7 the side of the next step; the halfword at +0x10E holds 'SN' (0x4E53)
so a counter is only trusted once this routine has started it.

Players, network copies and everyone else
-----------------------------------------

A player's soldier has control type 0 (and in both games a HumanAI of his
own), a soldier simulated on another console 2: both leave at the first
test. A friendly AI sniper (your squad) fails the hostile test, any other gun
the motion-type test. With the option off no word is written.

Online co-op (Jungle Storm): the AI runs on the host. Savestates of both
consoles of the same co-op missions (host 9C04BFE8 / FA828984 in the main
sstates folder, joiner in pcsx2-coop2) show every enemy soldier with control
type 1 and a HumanAI on the host and control type 2 and NO HumanAI on the
joiner, so the joiner's disc never moves anyone; the host's soldier moves by
the stock RunForCover and reaches the joiners through the normal soldier
updates, like any other AI movement. Nothing random is used. The host's disc
decides.

Works with the other AI options: grtactics' OpenFight re-plans see the
RunForCover as "busy" (they may put a Suppress on top, which ends and lets
the move go on); with the AI smoke option (grsmoke hooks RunForCover's
LocationBehavior push) a relocating sniper may pop smoke first.

The patch
---------

  GR 0x003D2E58  jal 0x0035FD20 (IIkeRulesMgr::Get) -> jal sn_shot
                 (s4 SimHuman, s3 Firearm, s0 rounds fired this call)
  JS 0x003B24B4  jal 0x00124100 (RSClock::Get)      -> jal sn_shot
                 (s5 SimHuman, s4 Firearm, s2 rounds fired this call)

sn_shot ends in ``j`` to the stock call with the original return address,
so the caller gets the same v0; every routine saves the s-registers it uses
(sq/lq) and touches only caller-saved registers otherwise. No other option
writes either word; quick trigger and the third-person camera hook other
words of UpdateBurst. The step table (5 pairs of floats, 0-terminated) sits
at the start of the first cave.

Caves (claimed as agent S; the routines are spread over them with a ``j``
where one fills): GR sceSifAllocSysMemory..sceSifLoadIopHeap
0x00418B20..0x00418D27, sceSifUnloadModule..sceSifLoadStartModuleBuffer
0x00419300..0x004194F7, Read32 + the head of DecodeBlocks
0x0042ED40..0x0042EE6F; JS unreferenced GS/DMA register helpers
0x00175968..0x00175ABF and 0x00175C30..0x00175D03, the twins of
sceSifLoadStartModule..sceSifLoadElf 0x00182458..0x001825C7, unreferenced
code 0x00184888..0x0018499B and 0x00184A70..0x00184AFF. No jump, branch,
pointer or lui/low-half pair (64-instruction window) reaches them from the
executable (JS: or either overlay), and no other option writes them.

Verified in the RAM interpreter (scratchpad ai2/S: verify.py, t_ub.py) on 9 JS
and 2 GR savestates, patched as these edits patch them, never played:

  * the whole SimHuman::UpdateBurst on real JS enemy snipers (and GR riflemen
    given a sniper rifle): one round fired, the gunshot message sent, the
    hook reached once after the loop; on -> RunForCover on top of his script,
    off -> nothing (stubs: the message's delivery, the direction maths, the
    per-round sound/FX call -- none of them on the path to the hook);
  * the hook on every hostile AI sniper with a HumanAI in the JS states: 4
    cover-point moves, 20 steps (almost all 2.9 m on watchtower decks), 39
    stay (no threat known -- not engaged -- or no ground level with them);
    GR (72 + 30 riflemen given gun 26 and the player as threat): 52 cover
    points, 39 steps, 10 riders left alone, 1 with no spot level with him. Each move: a new
    RunForCover, threat as expected, at least 2.9 m, never a close fight,
    never nearer the threat than SLACK, ground within CLIMB; a cover point
    free before, taken after, facing the threat; a step on his RSLevel and the
    first good candidate on its side; s0-s7, fp, sp, f20-f30 and v0 intact;
  * the game's own RSScript::Process (HumanAI::Update's script tick) then
    starts a LocationBehavior to the spot and sets the HumanAI's move target
    (+0x8C) to it;
  * every rifleman, player, friendly sniper and hostile sniper forced to
    control type 2 -- each first given a fresh engaged threat so that only
    the test protecting him stands in the way -- and the joiner's 6 enemy
    snipers: not one byte of game RAM written;
  * two shots: the first counted from a garbage padding to 1, the second
    moves; more shots while moving, and a shot with an EngageThreat pushed on
    top of the move, add no second RunForCover; zero rounds does nothing;
    the step side alternates (or stays when the other side has no ground);
  * 11 mutations (each test removed or off by one) are each caught.
"""

from __future__ import annotations

import struct

from .grasm import Asm, assemble
from .model import CHOICE, Choice, Setting

#: shots before a sniper moves ("off" = as shipped)
SHOTS = {"off": 0, "1": 1, "2": 2}

MIN_THREAT = 15.0     # m: a threat nearer than this is a close fight -- no move
BACK = 8.0            # m behind him (away from the threat): where the cover search is centred
RADIUS = 20.0         # m around that point
MIN_MOVE = 3.0        # m: a cover point nearer than this is not a new position
SLACK = 2.0           # m: a cover point may be at most this much nearer the threat than he is
#: the fallback steps tried in order, (back, side) in metres; the side changes sign from one move to the
#: next. The short ones keep a sniper on a small platform (a watchtower's deck is a few metres across).
STEPS = ((4.0, 6.0), (4.0, -6.0), (7.0, 0.0), (1.5, 2.5), (1.5, -2.5))
CLIMB = 2.0           # m: the new spot's ground may be at most this much above or below his
FRESH = 5.0           # s: how old the engaged threat may be
MARK = 0x4E53         # 'SN' in HumanAI +0x10E: the counter at +0x10D is ours

#: behaviour types a sniper may be moved from (bit n = type n): Location 1, MoveInFormation 3,
#: EngageThreat 8, Suppress 9, CoverArea 0x13, Probe 0x14 (ids from the GR constructors; JS's are
#: the same -- every vtable seen on a JS soldier's script carries the GR id)
TYPE_OK = (1 << 1) | (1 << 3) | (1 << 8) | (1 << 9) | (1 << 0x13) | (1 << 0x14)
RFC_TYPE = 0x0A

GAMES = {
    "gr": dict(
        HOOK=0x003D2E58, HOOK_STOCK=0x0C0D7F48,      # jal IIkeRulesMgr::Get (slot: nop)
        TAIL=0x0035FD20,
        SH="s4", GUN="s3", N="s0",
        DATAMGR=0x005E4D98,                          # IIkeDataMgr (vtable +0x4C: GunFile of a gun index)
        AIMGR=0x003663A0, GETHAI=0x001A1890,         # IkeAIMgr::Get, IkeAIMgr::GetHumanAI(SimHuman*)
        CLOCK=0x005DFC20,                            # RSClock* (+0xD4 seconds)
        CLOSEST=0x0018B130,                          # FireTeamAI::GetClosestEnemy(pos, false)
        SCENE=0x006376D0, SEARCH=0x004FCEF0,         # RSSimScene*; SearchForCoverPoint
        FINDROOM=0x005044E0,                         # RSSimScene::FindRoom(point)
        LEVELOVER=0x004DAD60,                        # RSSimRoom::FindLevelPointIsOver(pt, face&, height&)
        NEW=0x00102DB0, RFC_CT=0x001BB870,           # operator new; RunForCoverBehavior::RunForCoverBehavior
        RFC_SETCP=0x001BB660,                        # RunForCoverBehavior::SetCoverPoint(human, cp, level)
        ADDEL=0x001BAEC0, STOPCOVER=0x00197930,      # RSScript::AddElement; HumanAI::StopUsingCover
        RFC_VT=0x005941A0,
        CAVES=((0x00418B20, 0x00418D28), (0x00419300, 0x004194F8), (0x0042ED40, 0x0042EE70)),
    ),
    "js": dict(
        HOOK=0x003B24B4, HOOK_STOCK=0x0C049040,      # jal RSClock::Get (slot: nop)
        TAIL=0x00124100,
        SH="s5", GUN="s4", N="s2",
        DATAMGR=0x00614070,
        AIMGR=0x001225D0, GETHAI=0x003F17D0,
        CLOCK=0x00684768,
        CLOSEST=0x003DBAE0,
        SCENE=0x00689E30, SEARCH=0x004E3DF0,
        FINDROOM=0x004EB880,
        LEVELOVER=0x004C1830,
        NEW=0x00103470, RFC_CT=0x001B7460,
        RFC_SETCP=0x001B75A0,
        ADDEL=0x001B6E10, STOPCOVER=0x003E7A90,
        RFC_VT=0x005A37E0,
        CAVES=((0x00175968, 0x00175AC0), (0x00175C30, 0x00175D04), (0x00182458, 0x001825C8),
               (0x00184888, 0x0018499C), (0x00184A70, 0x00184B00)),
    ),
}


def _hi(f):
    b = struct.unpack("<I", struct.pack("<f", f))[0]
    assert b & 0xFFFF == 0, f
    return b >> 16


def _bits(f):
    return struct.unpack("<I", struct.pack("<f", f))[0]


def _srlv(rd, rt, rs):
    """srlv rd, rt, rs (grasm has no variable shifts)."""
    r = "zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7".split()
    return (r.index(rs) << 21) | (r.index(rt) << 16) | (r.index(rd) << 11) | 0x06


# From UpdateBurst after its round loop, in place of the stock call there. {N} rounds fired by this
# call, {SH} the SimHuman, {GUN} the Firearm. Returns through the stock call (same ra, same v0).
SHOT_SRC = """
sn_steps:{STEPS}
sn_shot:
    beqz  {N}, sn_tail                ; no round this call
    lw    t0, 0x138({SH})             ; (delay) control type
    addiu t1, zero, 1
    bne   t0, t1, sn_tail             ; only a soldier the AI drives here (players 0, network copies 2)
    lw    t0, 0x458({SH})             ; (delay)
    lbu   t0, 0xb7(t0)                ; hostile (SimHuman::IsEnemy)
    beqz  t0, sn_tail
    lui   a0, %hi(DATAMGR)            ; (delay)
    addiu sp, sp, -0x30
    sd    ra, 0x20(sp)
    sq    s0, 0x10(sp)
    lw    a0, %lo(DATAMGR)(a0)
    lhu   a1, 8({GUN})                ; the gun that fired: its GunFile
    lw    t9, 0(a0)
    lw    t9, 0x4c(t9)
    jalr  t9
    nop
    lw    t0, 0xf8(v0)                ; weapon motion type
    addiu t0, t0, -2
    sltiu t0, t0, 2                   ; 2 or 3: a sniper rifle (SimHuman::IsSniper's test)
    beqz  t0, sn_out
    nop
    jal   AIMGR
    nop
    move  a0, v0
    jal   GETHAI                      ; his HumanAI
    move  a1, {SH}
    beqz  v0, sn_out                  ; none (not simulated on this console)
    move  s0, v0                      ; (delay)
    lhu   t0, 0x10e(s0)               ; padding: our marker?
    lbu   t1, 0x10d(s0)               ; padding: shots counted, bit 7 = side of the next step
    li    t2, {MARK}
    beq   t0, t2, sn_count
    nop
    sh    t2, 0x10e(s0)               ; first sniper shot: a fresh counter
    move  t1, zero
sn_count:
    addiu t1, t1, 1
    andi  t3, t1, 0x7f
    sltiu t3, t3, {SHOTS}
    bnez  t3, sn_keep                 ; not yet
    nop
    andi  t1, t1, 0x80
    xori  t1, t1, 0x80                ; count 0, the next step to the other side
    sb    t1, 0x10d(s0)
    jal   MOVE
    move  a0, s0
    b     sn_out
    nop
sn_keep:
    sb    t1, 0x10d(s0)
sn_out:
    ld    ra, 0x20(sp)
    lq    s0, 0x10(sp)
    addiu sp, sp, 0x30
sn_tail:
    j     TAIL                        ; the stock call, which returns to UpdateBurst
    nop
"""

# a0 = the sniper's HumanAI. Frame: T +0, the probe point +0x10, out level +0x20, out cover point +0x24,
# s0..s2 +0x30/+0x40/+0x50, ra +0x70, ux/uy/d +0x80/+0x84/+0x88, side +0x8C, back +0x90, his ground +0x94.
MOVE_SRC = """
sn_move:
    addiu sp, sp, -0xa0
    sd    ra, 0x70(sp)
    sq    s0, 0x30(sp)
    sq    s1, 0x40(sp)
    sq    s2, 0x50(sp)
    move  s0, a0
    lw    t0, 0xc(s0)                 ; his script
    lw    t0, 4(t0)                   ; its top behaviour
    beqz  t0, mv_free
    nop
    lw    t1, 4(t0)                   ; its type
    sltiu t2, t1, 32
    beqz  t2, mv_out
    lui   t2, {OK_HI}                 ; (delay)
    ori   t2, t2, {OK_LO}
    .word {SRLV}                      ; srlv t2, t2, t1
    andi  t2, t2, 1
    beqz  t2, mv_out                  ; doing something else: leave him
    nop
mv_walk:
    lw    t1, 4(t0)
    addiu t1, t1, -{RFC}
    beqz  t1, mv_out                  ; already running for cover (ours or the team's)
    nop
    lw    t0, 0x10(t0)                ; the next one down
    bnez  t0, mv_walk
    nop
mv_free:
    lw    t0, 0x3c(s0)                ; his RSLevel
    beqz  t0, mv_out
    lw    t1, 0x64(s0)                ; (delay) his current threat's id: -1 until one is set (and
    addiu t1, t1, 1                   ;   until then +0x68/+0x74 are uninitialised heap)
    beqz  t1, mv_close
    lui   t0, %hi(CLOCK)              ; (delay)
    lw    t0, %lo(CLOCK)(t0)
    lwc1  f0, 0xd4(t0)                ; now
    lwc1  f1, 0x74(s0)                ; when it was set
    sub.s f0, f0, f1                  ; its age
    mtc1  zero, f1
    c.lt.s f0, f1
    bc1t  mv_close                    ; from a later clock: not this fight
    lui   t0, {FRESH}                 ; (delay)
    mtc1  t0, f1
    c.lt.s f0, f1
    bc1t  mv_t                        ; engaged lately: that target
    addiu a0, s0, 0x68                ; (delay) its position
mv_close:
    lw    a0, 0xa4(s0)                ; else the closest enemy his team knows of
    beqz  a0, mv_out
    addiu a1, s0, 0x2c                ; (delay)
    jal   CLOSEST
    move  a2, zero
    beqz  v0, mv_out
    addiu a0, v0, 4                   ; (delay) where that enemy was reported
mv_t:
    lw    t0, 0(a0)
    lw    t1, 4(a0)
    lw    t2, 8(a0)
    sw    t0, 0(sp)
    sw    t1, 4(sp)
    sw    t2, 8(sp)
    lwc1  f0, 0x2c(s0)                ; P
    lwc1  f1, 0x30(s0)
    lwc1  f2, 0(sp)
    lwc1  f3, 4(sp)
    sub.s f4, f0, f2                  ; P - T: away from the threat
    sub.s f5, f1, f3
    mul.s f6, f4, f4
    mul.s f7, f5, f5
    add.s f6, f6, f7
    sqrt.s f6, f6                     ; d
    lui   t0, {MIN_THREAT}
    mtc1  t0, f7
    c.lt.s f6, f7
    bc1t  mv_out                      ; a close fight
    nop
    div.s f4, f4, f6                  ; u = (P - T) / d
    div.s f5, f5, f6
    swc1  f4, 0x80(sp)
    swc1  f5, 0x84(sp)
    swc1  f6, 0x88(sp)
    jal   FLOOR                       ; the ground under him
    addiu a0, s0, 0x2c
    beqz  v0, mv_out
    lwc1  f4, 0x80(sp)                ; (delay)
    swc1  f0, 0x94(sp)
    lwc1  f5, 0x84(sp)
    lwc1  f0, 0x2c(s0)
    lwc1  f1, 0x30(s0)
    lui   t0, {BACK}                  ; the search point: BACK m behind him
    mtc1  t0, f7
    mul.s f8, f4, f7
    mul.s f9, f5, f7
    add.s f8, f0, f8
    add.s f9, f1, f9
    swc1  f8, 0x10(sp)
    swc1  f9, 0x14(sp)
    lw    t0, 0x34(s0)
    sw    t0, 0x18(sp)
    addiu a0, sp, 0x10
    lw    a1, 0x3c(s0)
    move  a2, sp
    lui   a3, %hi(SCENE)
    lw    a3, %lo(SCENE)(a3)
    addiu t0, sp, 0x20
    addiu t1, sp, 0x24
    lui   t2, {RADIUS}
    jal   SEARCH                      ; the closest free cover point facing T
    mtc1  t2, f12
    andi  v0, v0, 0xff
    beqz  v0, mv_step                 ; none
    lw    s1, 0x24(sp)                ; (delay) found: the cover point
    lwc1  f0, 0(s1)                   ; C (its z is the ground there)
    lwc1  f1, 4(s1)
    lwc1  f2, 8(s1)
    lwc1  f3, 0x94(sp)
    sub.s f2, f2, f3
    mul.s f2, f2, f2
    lui   t0, {CLIMB2}
    mtc1  t0, f3
    c.lt.s f3, f2
    bc1t  mv_step                     ; not level with his ground (a drop off his perch, a climb)
    lwc1  f2, 0x2c(s0)                ; (delay)
    lwc1  f3, 0x30(s0)
    sub.s f2, f0, f2
    sub.s f3, f1, f3
    mul.s f2, f2, f2
    mul.s f3, f3, f3
    add.s f2, f2, f3                  ; |C - P|^2
    lui   t0, {MIN_MOVE2}
    mtc1  t0, f3
    c.lt.s f2, f3
    bc1t  mv_step                     ; where he is already
    lwc1  f2, 0(sp)                   ; (delay)
    lwc1  f3, 4(sp)
    sub.s f2, f0, f2
    sub.s f3, f1, f3
    mul.s f2, f2, f2
    mul.s f3, f3, f3
    add.s f2, f2, f3                  ; |C - T|^2
    lwc1  f4, 0x88(sp)
    lui   t0, {SLACK}
    mtc1  t0, f5
    sub.s f4, f4, f5
    mul.s f4, f4, f4                  ; (d - SLACK)^2
    c.lt.s f2, f4
    bc1t  mv_step                     ; toward the threat: no
    nop
    jal   NEWRFC
    nop
    beqz  v0, mv_out
    move  s2, v0                      ; (delay)
    move  a0, v0
    move  a1, s0
    move  a2, s1
    jal   RFC_SETCP                   ; stock: destination, his cover point (the old one freed)
    lw    a3, 0x20(sp)                ; (delay) the cover point's level
    b     mv_push
    nop
mv_step:
    lbu   t0, 0x10d(s0)               ; bit 7: which side this time
    andi  t0, t0, 0x80
    sll   t0, t0, 24
    sw    t0, 0x8c(sp)                ; the side's sign bit
    lui   s1, %hi(sn_steps)
    addiu s1, s1, %lo(sn_steps)       ; {{back, side}} metres to try, in order; 0 ends
mv_try:
    lw    t0, 0(s1)                   ; back
    beqz  t0, mv_out                  ; none left: he stays
    lw    t1, 4(s1)                   ; (delay) side
    lw    t2, 0x8c(sp)
    xor   t1, t1, t2                  ; this time's side
    mtc1  t0, f7
    mtc1  t1, f6
    lwc1  f4, 0x80(sp)
    lwc1  f5, 0x84(sp)
    mul.s f8, f4, f7                  ; Q = P + u * back + (-uy, ux) * side
    mul.s f9, f5, f7
    mul.s f10, f5, f6
    mul.s f11, f4, f6
    sub.s f8, f8, f10
    add.s f9, f9, f11
    lwc1  f0, 0x2c(s0)
    lwc1  f1, 0x30(s0)
    add.s f8, f0, f8
    add.s f9, f1, f9
    swc1  f8, 0x10(sp)
    swc1  f9, 0x14(sp)
    lwc1  f0, 0x34(s0)
    lui   t0, 0x3f80                  ; probed a metre above him, so rising ground counts
    mtc1  t0, f1
    add.s f0, f0, f1
    swc1  f0, 0x18(sp)
    jal   FLOOR
    addiu a0, sp, 0x10
    lw    t0, 0x3c(s0)
    bne   v0, t0, mv_next             ; no ground there, or not his RSLevel
    lwc1  f1, 0x94(sp)                ; (delay)
    sub.s f1, f0, f1
    mul.s f1, f1, f1
    lui   t0, {CLIMB2}
    mtc1  t0, f2
    c.lt.s f1, f2
    bc1t  mv_found                    ; level with the ground he stands on
    swc1  f0, 0x18(sp)                ; (delay) the destination: on that ground
mv_next:
    b     mv_try
    addiu s1, s1, 8
mv_found:
    jal   NEWRFC
    nop
    beqz  v0, mv_out
    move  s2, v0                      ; (delay)
    lw    t0, 0x10(sp)
    lw    t1, 0x14(sp)
    lw    t2, 0x18(sp)
    sw    t0, 0x28(s2)                ; the destination
    sw    t1, 0x2c(s2)
    sw    t2, 0x30(s2)
    lw    t0, 0x3c(s0)
    sw    t0, 0x34(s2)                ; on his RSLevel
    addiu t0, zero, 1
    sb    t0, 0x38(s2)                ; chosen: RunForCover skips its own search
    sb    t0, 0x39(s2)                ; and crouches when he gets there
    jal   STOPCOVER                   ; out of any cover point he holds
    move  a0, s0
mv_push:
    lw    a0, 0xc(s0)
    jal   ADDEL                       ; on top of his script
    move  a1, s2
mv_out:
    ld    ra, 0x70(sp)
    lq    s0, 0x30(sp)
    lq    s1, 0x40(sp)
    lq    s2, 0x50(sp)
    jr    ra
    addiu sp, sp, 0xa0
"""

# a0 = a point: v0 = the RSLevel of the ground under it (0: none), f0 = that ground's height --
# RSSimScene::FindRoom, then RSSimRoom::FindLevelPointIsOver (what RSSimScene::FindLevel asks per room)
FLOOR_SRC = """
sn_floor:
    addiu sp, sp, -0x30
    sd    ra, 0x20(sp)
    sq    s0, 0x10(sp)
    move  s0, a0
    lui   a0, %hi(SCENE)
    lw    a0, %lo(SCENE)(a0)
    jal   FINDROOM
    move  a1, s0
    beqz  v0, fl_out                  ; in no room
    move  a0, v0                      ; (delay)
    move  a1, s0
    addiu a2, sp, 0                   ; RSFloorFace*&
    jal   LEVELOVER
    addiu a3, sp, 4                   ; float& height
    lwc1  f0, 4(sp)
fl_out:
    ld    ra, 0x20(sp)
    lq    s0, 0x10(sp)
    jr    ra
    addiu sp, sp, 0x30
"""

# a new RunForCoverBehavior whose threat is the caller's T (the caller's sp+0); v0 = it, or 0
NEW_SRC = """
sn_new:
    addiu sp, sp, -0x20
    sd    ra, 0x10(sp)
    jal   NEW
    addiu a0, zero, 0x44
    beqz  v0, nw_out
    nop
    jal   RFC_CT
    move  a0, v0
    lw    t0, 0x20(sp)
    lw    t1, 0x24(sp)
    lw    t2, 0x28(sp)
    sw    t0, 0x18(v0)                ; the threat it faces
    sw    t1, 0x1c(v0)
    sw    t2, 0x20(v0)
nw_out:
    ld    ra, 0x10(sp)
    jr    ra
    addiu sp, sp, 0x20
"""


def _src(game, shots):
    g = GAMES[game]
    fmt = dict(N=g["N"], SH=g["SH"], GUN=g["GUN"], MARK=hex(MARK), SHOTS=shots,
               OK_HI=hex(TYPE_OK >> 16), OK_LO=hex(TYPE_OK & 0xFFFF), SRLV=hex(_srlv("t2", "t2", "t1")),
               RFC=hex(RFC_TYPE), FRESH=hex(_hi(FRESH)), MIN_THREAT=hex(_hi(MIN_THREAT)), BACK=hex(_hi(BACK)),
               RADIUS=hex(_hi(RADIUS)), MIN_MOVE2=hex(_hi(MIN_MOVE * MIN_MOVE)), SLACK=hex(_hi(SLACK)),
               CLIMB2=hex(_hi(CLIMB * CLIMB)),
               STEPS="".join("\n    .word %#x\n    .word %#x" % (_bits(b), _bits(sd)) for b, sd in STEPS)
                     + "\n    .word 0\n")
    return [("sn_shot", SHOT_SRC.format(**fmt)), ("sn_move", MOVE_SRC.format(**fmt)),
            ("sn_new", NEW_SRC.format(**fmt)), ("sn_floor", FLOOR_SRC.format(**fmt))]


_DELAYED = {"b", "beq", "bne", "beqz", "bnez", "blez", "bgtz", "bltz", "bgez", "bc1t", "bc1f",
            "j", "jal", "jr", "jalr"}


def _spread(src, caves):
    """Place `src` over `caves` [(start, end), ...] in order: where one fills, `j` to the next (never
    between a branch and its delay slot). -> ([(va, word)], labels)."""
    items = Asm._items(src)
    caves = list(caves)
    pc, end = caves.pop(0)
    placed, labels, pending, slot = [], {}, [], False
    left = sum(1 for kind, _ in items if kind == "ins")
    for kind, x in items:
        if kind == "label":
            pending.append(x)
            continue
        need = 2 if x.split()[0] in _DELAYED else 1
        if not slot and pc + 4 * left > end and pc + 4 * (need + 2) > end:
            if not caves:
                raise ValueError("sniper routines outgrow their caves")
            placed += [(pc, "j %#x" % caves[0][0]), (pc + 4, "nop")]
            pc, end = caves.pop(0)
        labels.update((p, pc) for p in pending)
        pending = []
        placed.append((pc, x))
        pc, left, slot = pc + 4, left - 1, need == 2
    if pc > end:
        raise ValueError("sniper routines outgrow their caves")
    return placed, labels


def layout(game, shots=2):
    """[(va, word)] of the three routines spread over the game's caves, and their labels."""
    g = GAMES[game]
    src = "".join(s for _, s in _src(game, shots))
    placed, labels = _spread(src, g["CAVES"])
    syms = {k: g[k] for k in ("TAIL", "DATAMGR", "AIMGR", "GETHAI", "CLOCK", "CLOSEST", "SCENE", "SEARCH",
                              "FINDROOM", "LEVELOVER", "NEW", "RFC_CT", "RFC_SETCP", "ADDEL", "STOPCOVER")}
    syms.update(labels, MOVE=labels["sn_move"], NEWRFC=labels["sn_new"], FLOOR=labels["sn_floor"])
    return [(va, assemble(x, va, syms)[0][0]) for va, x in placed], labels


def _stock_words(base, hexwords):
    """Fixed 8-digit words (adjacent string literals join with no separator)."""
    h = "".join(hexwords.split())
    assert len(h) % 8 == 0
    return {base + 4 * i: int(h[8 * i:8 * i + 8], 16) for i in range(len(h) // 8)}


# every cave word as the retail executables ship it
_GR_STOCK_HEX = {
    0x00418B20: (   # ..0x00418D28, 130 words: sceSifAllocSysMemory..sceSifLoadIopHeap
        "3C020057 27BDFFD0 8C43E1D8 0080382D FFBF0020 FFB00010 04600015 0000102D"
        "3C02005F 3C04005F 2443F500 AC45F500 AC670004 3C10005F AC660008 2484F480"
        "0060382D 24050004 AFA00000 0000302D 2408000C 2609F4C0 240A0004 0C10531C"
        "0000582D 04410002 8E02F4C0 0000102D DFBF0020 DFB00010 03E00008 27BD0030"
        "3C030057 27BDFFD0 8C62E1D8 0080282D FFBF0020 04410003 FFB00010 10000012"
        "0000102D 3C07005F 3C04005F ACE5F500 3C10005F 2484F480 24E7F500 AFA00000"
        "24050002 0000302D 24080004 2609F4C0 240A0004 0C10531C 0000582D 04410002"
        "8E02F4C0 2402FFFF DFBF0020 DFB00010 03E00008 27BD0030 27BDFFF0 FFBF0000"
        "0C1062E8 00000000 DFBF0000 03E00008 27BD0010 00000000 3C020057 27BDFFD0"
        "8C43E1D8 0080302D FFBF0020 04610003 FFB00010 10000030 0000102D 90C20000"
        "3C07005F 24E3F540 A0620004 00021600 10400011 0000402D 3C09005F 3C10005F"
        "25080001 00000000 290200FC 1040000C 00C81021 24E3F540 90440000 00681821"
        "A0640004 00042600 5480FFF7 25080001 10000004 240200FC 3C09005F 3C10005F"
        "240200FC 55020005 ACE5F540 24E2F540 240800FB A04000FF ACE5F540 24E2F540"
        "2524F480 A04000FF 0040382D 25080005 AFA00000 24050003 0000302D 2609F4C0"
        "240A0004 0C10531C 0000582D 04410002 8E02F4C0 2402FFFF DFBF0020 DFB00010"
        "03E00008 27BD0030"),
    0x00419300: (   # ..0x004194F8, 126 words: sceSifUnloadModule..sceSifLoadStartModuleBuffer
        "27BDFFC0 FFB10020 FFBF0030 0080882D 0C10634A FFB00010 04400018 3C02FFFF"
        "0C10638A 00000000 10400004 3C10005F 3C02FFFE 10000011 3442FFFC 3C04005F"
        "2607F640 AE11F640 2484F840 AFA00000 24050008 0000302D 24080004 00E0482D"
        "240A0004 0C10531C 0000582D 04430003 8E02F640 3C02FFFE 3442FFFF DFBF0030"
        "DFB10020 DFB00010 03E00008 27BD0040 27BDFFD0 FFB00010 FFBF0020 0C10634A"
        "0080802D 0440001E 3C02FFFF 0C10638A 00000000 50400004 3C02005F 3C02FFFE"
        "10000017 3442FFFC 0200282D 2450F648 240600FC 0C101C9C 0200202D 2603FFF8"
        "3C04005F 0060382D A0600103 2484F840 24050009 AFA00000 0000302D 24080200"
        "00E0482D 240A0004 0C10531C 0000582D 04430003 8E02FFF8 3C02FFFE 3442FFFF"
        "DFBF0020 DFB00010 03E00008 27BD0030 27BDFFC0 FFB10020 FFBF0030 0080882D"
        "0C10634A FFB00010 04400018 3C02FFFF 0C10638A 00000000 10400004 3C10005F"
        "3C02FFFE 10000011 3442FFFC 3C04005F 2607F640 AE11F640 2484F840 AFA00000"
        "2405000A 0000302D 24080004 00E0482D 240A0004 0C10531C 0000582D 04430003"
        "8E02F640 3C02FFFE 3442FFFF DFBF0030 DFB10020 DFB00010 03E00008 27BD0040"
        "27BDFFE0 FFBF0010 0C1063BC 03A0382D DFBF0010 03E00008 27BD0020 00000000"
        "27BDFFF0 FFBF0000 0C1063BC 00000000 DFBF0000 03E00008"),
    0x0042ED40: (   # ..0x0042EE70, 76 words: Read32 + the head of DecodeBlocks
        "90860000 24840001 90830000 24840001 90850000 00031A00 90820001 00C33025"
        "00052C00 00C53025 00021600 03E00008 00C21025 00000000 27BDFF60 FFB70080"
        "FFB20030 3C170059 FFBF0090 0080902D FFB60070 FFB50060 FFB40050 FFB30040"
        "FFB10020 FFB00010 AE400008 8E510000 1000003B 8E550004 8E42000C 26100004"
        "1040000C 02B4B021 8E420010 8C430000 0070182B 00000000 00000000 00000000"
        "00000000 00000000 00000000 1460FFFA 00000000 0C10BB50 0220202D 0040982D"
        "8E42000C 1040000D 0200882D 8E420010 02132021 8C430000 0064102B 00000000"
        "00000000 00000000 00000000 00000000 00000000 1440FFFA 00000000 0274102B"
        "1040000E 02A0302D AFB40000 0220202D 0260282D 03A0382D 0C10C034 0000402D"
        "8FA30000 10740009 26E491E0 0C0403CC"),
}
_JS_STOCK_HEX = {
    0x00175968: (   # ..0x00175AC0, 86 words: unreferenced GS/DMA register helpers
        "3C031000 24040008 34633000 24020001 03E00008 AC640000 27BDFFF0 FFBF0000"
        "0C05D6B0 00000000 24030001 14430005 0000102D 3C031000 24020001 34633000"
        "AC600000 DFBF0000 03E00008 27BD0010 27BDFFF0 1480000B FFBF0000 0C05D688"
        "00000000 3C03FFFF 3C041000 3463FFFB 34843010 00431024 AC820000 1000000B"
        "DFBF0000 24020001 14820008 DFBF0000 0C05D688 00000000 3C031000 34420004"
        "34633010 AC620000 DFBF0000 03E00008 27BD0010 00000000 3C031000 34633020"
        "8C620000 30420004 03E00008 00021082 27BDFFF0 1480000B FFBF0000 0C05D688"
        "00000000 3C03FFFF 3C041000 3463FFFE 34843010 00431024 AC820000 1000000B"
        "DFBF0000 24020001 14820009 DFBF0000 0C05D688 00000000 3C031000 34420001"
        "34633010 AC620000 DFBF0000 24020001 03E00008 27BD0010 27BDFFF0 FFBF0000"
        "0C05D688 00000000 DFBF0000 30420001 03E00008 27BD0010"),
    0x00175C30: (   # ..0x00175D04, 53 words: unreferenced GS/DMA register helpers
        "27BDFFE0 FFB00000 FFBF0010 0C05D742 0080802D 10400003 24030001 14430003"
        "00000000 1000000C 0000102D 16000003 3C021000 10000005 24030002 16030006"
        "24020001 3C021000 24030004 34423C10 AC430000 24020001 DFBF0010 DFB00000"
        "03E00008 27BD0020 27BDFFF0 FFBF0000 0C05D742 00000000 24030001 14430006"
        "0000102D 3C031000 24040008 34633C10 24020001 AC640000 DFBF0000 03E00008"
        "27BD0010 00000000 00052840 00063080 00851025 3C031000 00461025 34633C20"
        "03E00008 AC620000 3C031000 34633C20 03E00008"),
    0x00182458: (   # ..0x001825C8, 92 words: sceSifLoadStartModule..sceSifLoadElf twins
        "27BDFFF0 FFBF0000 0C060884 0000402D DFBF0000 03E00008 27BD0010 00000000"
        "27BDFF90 FFB40050 FFB30040 00C0A02D FFB20030 00E0982D FFB00010 00A0902D"
        "FFBF0060 0080802D 0C06068E FFB10020 0440002C 3C02FFFF 0C0606CE 00000000"
        "50400004 3C020062 3C02FFFE 10000025 3442FFFC 0200282D 245189C8 240600FC"
        "0220202D 0C05B8F2 2630FFF8 0240282D A2000103 262400FC 0C05B8F2 240600FC"
        "3C040062 A20001FF 0260282D 24848BC0 AFA00000 0000302D 0200382D 24080200"
        "0200482D 240A0010 0C05F5AA 0000582D 04430004 8E22FFF8 3C02FFFE 10000009"
        "3442FFFF 54400004 AE820000 3C02FFFE 10000004 3442FFFD 0000102D 8E030004"
        "AE830004 DFBF0060 DFB40050 DFB30040 DFB20030 DFB10020 DFB00010 03E00008"
        "27BD0070 00000000 27BDFFF0 FFBF0000 0C06091E 24070001 DFBF0000 03E00008"
        "27BD0010 00000000 00A0302D 27BDFFF0 3C050058 FFBF0000 24A51D78 0C06091E"
        "24070001 DFBF0000 03E00008 27BD0010"),
    0x00184888: (   # ..0x0018499C, 69 words: unreferenced
        "27BDFFD0 00041282 FFB00000 FFBF0020 00028180 04800005 FFB10010 8E030008"
        "308203FF 50430004 3C020057 3C028000 1000001F 34428002 244265F8 8C43001C"
        "54640004 8E02000C 3C028000 10000018 34420010 30420001 10400015 0000102D"
        "0C061118 00000000 8E05000C 0040882D DE040010 3C02FFFF DE030018 3442FFFE"
        "0224202F 30A60002 0064182D 00A22824 FE030018 10C00005 AE05000C 0C061062"
        "0200202D 0C060FDC 0220202D 24020001 DFBF0020 DFB10010 DFB00000 03E00008"
        "27BD0030 00000000 27BDFFD0 FFB00000 FFB10010 FFBF0020 0C060CC8 0080802D"
        "0200202D 0C061222 0040882D 12200003 0040802D 0C060CDE 00000000 0200102D"
        "DFBF0020 DFB10010 DFB00000 03E00008 27BD0030"),
    0x00184A70: (   # ..0x00184B00, 36 words: unreferenced
        "00041282 04800005 00022980 8CA30008 308203FF 50430003 8CA2000C 03E00008"
        "2402FFFF 30420001 10400005 00000000 DCA30018 DCA20010 03E00008 0043102F"
        "03E00008 0000102D 27BDFFD0 FFB00000 FFB10010 FFBF0020 0C060CC8 0080802D"
        "0200202D 0C06129C 0040882D 12200003 0040802D 0C060CDE 00000000 0200102D"
        "DFBF0020 DFB10010 DFB00000 03E00008"),
}

GR_STOCK, JS_STOCK = {}, {}
for _b, _h in _GR_STOCK_HEX.items():
    GR_STOCK.update(_stock_words(_b, _h))
for _b, _h in _JS_STOCK_HEX.items():
    JS_STOCK.update(_stock_words(_b, _h))
GR_STOCK[GAMES["gr"]["HOOK"]] = GAMES["gr"]["HOOK_STOCK"]
JS_STOCK[GAMES["js"]["HOOK"]] = GAMES["js"]["HOOK_STOCK"]


def edits_for(game, choice="off"):
    """(va, value, stock, note); [] when off."""
    shots = SHOTS.get(choice, 0)
    if not shots:
        return []
    g = GAMES[game]
    st = GR_STOCK if game == "gr" else JS_STOCK
    what = "every shot" if shots == 1 else "every %d shots" % shots
    placed, labels = layout(game, shots)
    out = [(va, w, st[va], "sniper relocate (%s): count a hostile AI sniper's shots, move him" % what)
           for va, w in placed]
    out.append((g["HOOK"], assemble("jal %#x" % labels["sn_shot"], g["HOOK"])[0][0], g["HOOK_STOCK"],
                "sniper relocate: UpdateBurst's post-loop call goes through the shot counter"))
    return out


def js_edits(v: dict):
    return edits_for("js", v.get("js_sniper_relocate", "off"))


def gr_edits(v: dict):
    return edits_for("gr", v.get("gr_sniper_relocate", "off"))


def cards(prefix: str = "js_", group: str = "Enemies") -> list:
    gr = prefix == "gr_"
    return [
        Setting(prefix + "sniper_relocate", "Enemy snipers relocate", CHOICE, "off", group,
                confidence="experimental",
                choices=[
                    Choice("off", "Off (as shipped)", "A sniper fires from the same spot until he dies."),
                    Choice("1", "After every shot", "He moves after each round he fires."),
                    Choice("2", "After two shots", "He fires twice from a spot, then moves."),
                ],
                help="An enemy sniper normally stays exactly where he first fired from, so once "
                     "you know the spot you can pin him there. With this, an enemy soldier firing "
                     "a sniper rifle at you or your squad moves after the chosen number of shots: to "
                     "another "
                     "cover point within about 25 m that faces you, never more than 2 m nearer you "
                     "than he was, or, where there is none, a few metres back and to the side "
                     "(alternating sides), out of the line he fired along. He runs there, crouches, "
                     "looks back toward you and carries on from the new spot. He never drops more "
                     "than 2 m off the ground he stands on, so a sniper on a %s only shifts a "
                     "couple of metres along it, or stays if there is no room. Snipers in a close "
                     "fight (under 15 m), riders and enemies with any other gun are unchanged; "
                     "your squad and players are never affected."
                     % ("rooftop or tower" if gr else "watchtower deck"),
                caution="Never played. Uses the game's own run-for-cover move, so a sniper whose "
                        "team is in formation may walk back to it later, and with enemy smoke on "
                        "he may pop smoke as he moves. The first move comes after the chosen count "
                        "of that sniper's own shots. %s"
                        % ("Ghost Recon: no savestate had an enemy sniper; checked on riflemen given "
                           "a sniper rifle." if gr else
                           "Online co-op: only the host's disc counts (the AI runs there; the "
                           "joiners see the move like any other).")),
    ]


def selftest(gr_elf: bytes = None, js_elf: bytes = None, used: dict = None, claims: list = None):
    """Stock words against the executables, no VA twice, every variant fits its caves, every written
    word inside a cave or the hook. `used` {game: set of VAs other options write} and `claims`
    [(game, lo, hi_inclusive)] are checked when given. [] = pass."""
    bad = []
    for game, st, elf, d in (("gr", GR_STOCK, gr_elf, 0x80), ("js", JS_STOCK, js_elf, 0x100)):
        if elf is not None:
            for va, w in st.items():
                off = va - 0x100000 + d
                if int.from_bytes(elf[off:off + 4], "little") != w:
                    bad.append("%s stock %08X" % (game, va))
        g = GAMES[game]
        for choice in SHOTS:
            try:
                e = edits_for(game, choice)
            except (ValueError, KeyError) as ex:
                bad.append("%s %s: %s" % (game, choice, ex))
                continue
            if choice == "off" and e:
                bad.append("%s off writes words" % game)
            vas = [va for va, *_ in e]
            if len(set(vas)) != len(vas):
                bad.append("%s %s duplicate VA" % (game, choice))
            for va in vas:
                if va not in st:
                    bad.append("%s %s %08X has no stock word" % (game, choice, va))
                if va != g["HOOK"] and not any(lo <= va < hi for lo, hi in g["CAVES"]):
                    bad.append("%s %s %08X outside the caves" % (game, choice, va))
                if used and va in used.get(game, ()):
                    bad.append("%s %s %08X written by another option" % (game, choice, va))
                if claims is not None and va != g["HOOK"] and not any(
                        cg == game and lo <= va <= hi for cg, lo, hi in claims):
                    bad.append("%s %s %08X outside the claimed caves" % (game, choice, va))
    return bad

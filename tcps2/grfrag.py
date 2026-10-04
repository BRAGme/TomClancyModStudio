"""Enemies throw grenades under suppressive fire: Jungle Storm (SLUS-20820).

Ghost Recon decides it in SuppressBehavior::ShouldIFrag (GR 0x001BD020), called
from SuppressBehavior::Process just before a soldier starts spraying: a soldier
with grenades, not in the player's fireteam, whose team has a combat and a
movement ROE, throws at the point it would have sprayed when that point is on a
level, both rooms are outdoors, it is 15-40 m away (10-75 m with a launcher), a
75% roll passes and FireTeamAI::IsOkToFragHereNow agrees (no friendly near the
blast, the team's 30 s since its last grenade). Then it hands the throw to a
FragLocationBehavior and waits (state 2).

Jungle Storm has no ShouldIFrag: its SuppressBehavior::Process (JS 0x001B87A0)
goes straight to StartSpraying (0x001B8C20), and the only place a
FragLocationBehavior is made is a team investigating a spot 20-30 m off. Every
piece the check needs is still there -- GetNumGrenades 0x003EA060,
HasGrenadeLauncher 0x003EA140, GetPlayerAI 0x003DD160, IsOkToFragHereNow
0x003E0A70, FindLevel 0x004EB6B0 (scene at 0x00689E30), SetFormationLeader
0x003DD600, the FragLocationBehavior constructor 0x001B0720, AddElement
0x001B6E10 -- matched call-for-call against Ghost Recon's TeamInvestigation and
ShouldIFrag, with the same object layout (HumanAI +0x132, +0xA4 team, +0x2C
position, +0x0C script; FireTeamAI +0x1C movement ROE, +0x20 combat ROE, +0xD9
script control; the sim word GR reads at +0x588 is +0x5B8 here).

One routine makes Ghost Recon's decision with the rules Ghost Recon's 'Enemies
throw grenades more readily' sets: indoors too, 10 m to the hand range (35, 50
or 60 m, see RANGES; 10-75 m with a launcher). The friendly and 30 s checks in
IsOkToFragHereNow stay. Three places ask it:

  * suppressive fire -- the call to StartSpraying in SuppressBehavior::Process
    (0x001B8984), at the point it would have sprayed, every time by default.
    No: StartSpraying, as before;
  * the start of an engagement -- EngageThreatBehavior::Process (0x001AD4C0)
    state 0 calls its spray-or-aim starter 0x001ADD60 once per target (the only
    call, 0x001ADA54). The routine is asked first, at the threat's position
    (the threat's controller at +0x1C, vtable +0x32C), with a roll (one in
    three by default, FRAG_CHANCES). A throw leaves the engagement in state 0:
    the throw goes on top of the soldier's script (RSScript::AddElement
    pushes), and when it is done the engagement asks again -- the team's 30 s
    wait then says no and it aims. Jungle Storm's enemies seldom suppress (once
    in 130 s of a firefight in a save state).
  * the frame a soldier loses sight of the threat he is engaging -- through
    grsuppress's hook on EngageThreatBehavior's LOS call (0x001AD988), at the
    threat's position, one time in two by default. A later savestate showed why
    the two above were not enough: 295 engagement starts and no grenade queued,
    with every living enemy 49-273 m away. Engagements start far beyond a hand
    throw; losing sight of you behind cover is when they are close.

How far a hand throw reaches. The throw leaves at IkeConstants' hand-throw
speed (+0x23C, 25 m/s; HumanMotion's throw at JS 0x00339520 reads it -- the AI
holds the button 1 s, past the 0.5 s that picks it over the 10 m/s lob), along
the soldier's look direction, which HumanAI::GetFacingForProjectile (JS
0x003E9C70) picks: the lowest angle from -30 to 45 degrees, in half degrees,
that clears the target's height at its distance -- in a vacuum. The grenade
itself flies with drag (SimProjectile: force -AirResistanceConstant x
velocity, so 0.125 / 0.39 kg = 0.32 per second for FRAG.PRJ, g 9.8), which
caps a 25 m/s throw at about 36 m (at 35 degrees) and brought a throw aimed
at a man 35 m away down about 30 m out. So with this option the aim solves the flight with
that drag: the loop's height sum (0x003E9F4C) goes through aim_h, which uses
the drag / mass of the projectile being thrown (aim_vel, on the thrown-item
path at 0x003E9D6C, reads it through IkeDataMgr::GetProjectileData). Beyond
30 m the AI throws harder: aim_vel scales the hand speed for an AI-controlled
soldier (SimHuman +0x138 == 1) by the range's factor and marks his HumanMotion,
and arm (the throw's speed read) throws that hard for the mark, so the aim and
the throw agree. Nearer, and for players, the throw is the game's own.

A diagnostic build showed a queued throw that never left the hand:
FragLocationBehavior::Process (0x001B0820) drops the throw when anything lies
within 10 m along the throw's arc (HumanAI::FragLOSBlocked 0x003E9570), which
in the jungle is nearly always. The distance is now 4 m (0x001B09B0).

Caves: sceDread (0x00180160..0x001802B8) holds the decision and
sceSifGetOtherData (0x0017D220..0x0017D378) the throw and the two entries;
both are unreferenced in the loaded image and in both overlays, and near enough
for a branch. The aim and the arm use the unused tails of three of grsmoke's
caves (0x00175E80..0x00175F30, 0x00197C30..0x00197CF4, 0x00173A68..0x00173AA4),
which grsmoke gave up.
Not yet played.

Ghost Recon (SLUS-20613)
------------------------

Ghost Recon has the decision (SuppressBehavior::ShouldIFrag, 0x001BD020) and
'Enemies throw grenades more readily' (grextras, gr_enemy_grenades) already
rewrites its rules to indoors, 10-60 m, every time. With that option on, the
Ghost Recon edits here (gr_enemy_frag_range, gr_enemy_frag_chance) make it
behave like Jungle Storm's 'Enemies throw grenades':

  * suppressive fire -- SuppressBehavior::Process's ``jal ShouldIFrag``
    (0x001BCD88) asks the routine instead (``should``): the same checks with
    the hand range of the throw-distance option and the chance option's
    suppressive-fire roll. The game's own code after the call still queues
    the FragLocationBehavior and waits (state 2), or sprays. ShouldIFrag has
    no other caller, so grextras's words in it no longer decide anything (they
    stay written; on "60" / "normal" the routine's answer is ShouldIFrag's).
  * the start of an engagement -- EngageThreatBehavior::Process state 0 asks
    ShouldISpray (0x001B2860) at 0x001B2F10 and then starts spraying or
    aiming inline; the routine is asked first (``engage``), at the threat's
    position (controller vtable +0x328), and a throw goes on at 0x001B2F3C,
    past both starters, leaving state 0 as in Jungle Storm.
  * the frame sight is lost -- grsuppress's Ghost Recon hook, with GR_DECIDE.

The throw: FragLocationBehavior::Process's 10 m clear-arc test becomes 4 m
(0x001B4404). The aim: GetFacingForProjectile (0x00199C90) keeps the speed in
f20 (Jungle Storm f25), g positive in f24 and the target height in f22;
aim_vel is entered from the thrown-item path (0x00199D88, whose slot loads
the hand speed, IkeConstants +0x234), aim_h from the loop's height sum
(0x00199F4C) and returns to its compare (0x00199F78); IkeDataMgr is read from
0x005E4D98 (vtable +0x48 GetProjectileData; FRAG: Weight 0.39, AirResistance
0.125 at +0x34 / +0x38, as in Jungle Storm). arm hooks HumanMotion::
HandleThrowItem's ManlyGrenadeVelocity call (0x0035D8E0); HumanMotion +0x1E is
padding in Ghost Recon too (the constructor writes +0x1C/+0x1D bytes and +0x20;
no HumanMotion method touches +0x1E; savestates hold junk there).

Caves: sceMkdir (0x00416EF0..0x0041709C) the decision, sceSifGetOtherData
(0x00414848..0x004149A0) the throw and the engage entry, sceCdDiskReady
(0x0040D1A8..0x0040D3A0) aim_h, aim_vel and arm; unreferenced (no jump,
branch, pointer or lui/low-half pair reaches them or the word before them)
and written by no other option at any value.
"""

from __future__ import annotations

import struct

from .grasm import assemble

CAVE, CAVE_END = 0x00180160, 0x001802B8        # sceDread: the decision
CAVE2, CAVE2_END = 0x0017D220, 0x0017D378      # sceSifGetOtherData: the throw, the spray
HOOK, HOOK_STOCK = 0x001B8984, 0x0C06E308        # jal StartSpraying (a0 = behaviour, slot: a1 = soldier)
ENGAGE_HOOK, ENGAGE_HOOK_STOCK = 0x001ADA54, 0x0C06B758   # jal 0x1add60 (a0 = behaviour, slot: a1 = soldier)
LOS, LOS_STOCK, LOS_NEW = 0x001B09B0, 0x3C034120, 0x3C034080   # lui v1, 10.0 -> 4.0 (FragLOSBlocked's reach)

SYMS = dict(
    StartSpraying=0x001B8C20, EngageStart=0x001ADD60, GetNumGrenades=0x003EA060,
    HasGrenadeLauncher=0x003EA140, GetPlayerAI=0x003DD160, FindLevel=0x004EB6B0, SCENE=0x00689E30,
    IsOkToFragHereNow=0x003E0A70, SetFormationLeader=0x003DD600, New=0x00103470,
    FragLocation=0x001B0720, AddElement=0x001B6E10, RandomFloat=0x001129C0, RNG=0x00613510,
)
#: js_enemy_frag_chance -> (sight lost [grsuppress], engagement start, suppressive fire): upper halves of
#: the float the roll (0..1) must come under; 0x3F80 is 1.0, 0x3F81 just over it: every time. With
#: 'Enemies suppress' a failed sight-lost roll can still end in a throw: he may suppress the spot, and
#: suppressive fire asks again -- so the suppression roll scales with the rest.
FRAG_CHANCES = {
    "low": (0x3E80, 0x3E2B, 0x3F00),       # 1 in 4, 1 in 6, 1 in 2
    "normal": (0x3F00, 0x3EAB, 0x3F80),    # 1 in 2, 1 in 3, always (as Ghost Recon's 'more readily')
    "high": (0x3F40, 0x3F2B, 0x3F80),      # 3 in 4, 2 in 3, always
    "max": (0x3F81, 0x3F81, 0x3F81),
}
#: js_enemy_frag_range -> (the hand decision's limit in m, the AI's throw speed x the game's 25 m/s).
#: With the drag the grenade flies with, 25 m/s reaches ~36 m, x1.28125 (32 m/s) ~53 m and x1.4375
#: (35.9 m/s) ~63 m on the level; the last two still reach their limit 3 m uphill.
RANGES = {"35": (35.0, 1.0), "50": (50.0, 1.28125), "60": (60.0, 1.4375)}
NEAR = 30.0                  # m: nearer, the AI throws at the game's own speed (reaches ~36 m)
BOOST = 0x5A5A               # aim_vel's mark for a harder throw

AIM_CAVE, AIM_CAVE_END = 0x00175E80, 0x00175F30   # grsmoke's second cave's tail: aim_h
ARM_CAVE, ARM_CAVE_END = 0x00197C30, 0x00197CF4   # grsmoke's report cave's tail: aim_vel
ARM2_CAVE, ARM2_CAVE_END = 0x00173A68, 0x00173AA4 # grsmoke's thread cave's tail: arm
AIM_VEL, AIM_VEL_STOCK = 0x003E9D6C, 0x10000019   # b 0x3e9dd4 (slot: lwc1 f25, 0x23c(v0), the hand speed)
AIM_SUM, AIM_SUM_STOCK = 0x003E9F4C, 0x461AC842   # mul.s f1, f25, f26: the loop's height sum starts
ARM, ARM_STOCK = 0x00339520, 0x0C0CE5DC           # jal ManlyGrenadeVelocity (slot: move a0, v0)
AIM_SYMS = dict(DATAMGR=0x001245F0, FACING_ON=0x003E9DD4, FACING_CMP=0x003E9F74)

# decide: a0 unused, a1 = the HumanAI, a2 = the aim point (RSVector3 *), a3 = the chance
# (float bits: the roll must come under it). v0 = 1 when a FragLocationBehavior was queued.
SRC = """
decide:
    addiu sp, sp, -0x70
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s2, 0x20(sp)
    sq    s3, 0x30(sp)
    sq    s4, 0x40(sp)
    sq    s5, 0x50(sp)
    sd    ra, 0x60(sp)
    move  s0, a2
    move  s1, a1
    move  s5, a3
    lbu   v0, 0x132(s1)          ; carries grenades at all
    beqz  v0, no
    lw    v0, 0x14(s1)
    lw    v0, 0x5b8(v0)
    bnez  v0, no
    lw    s2, 0xa4(s1)           ; its fireteam
    beqz  s2, no
    li    s3, 2                  ; grenades needed: 2, or 1 when the script runs the team
    lbu   v0, 0xd9(s2)
    beqz  v0, count
    nop
    li    s3, 1
count:
    jal   GetNumGrenades
    move  a0, s1
    slt   at, v0, s3
    bnez  at, no
    nop
    jal   HasGrenadeLauncher
    move  a0, s1
    andi  s3, v0, 0xff           ; s3 = launcher
    lbu   v0, 0xd9(s2)
    bnez  v0, roe
    nop
    jal   GetPlayerAI            ; never the player's own fireteam
    move  a0, s2
    bnez  v0, no
    nop
roe:
    lw    v0, 0x20(s2)           ; combat ROE
    beqz  v0, no
    lw    v0, 0x1c(s2)           ; movement ROE
    beqz  v0, no
    lwc1  f0, 0x2c(s1)           ; distance squared, soldier to aim point
    lwc1  f1, 0x0(s0)
    sub.s f0, f0, f1
    mul.s f2, f0, f0
    lwc1  f0, 0x30(s1)
    lwc1  f1, 0x4(s0)
    sub.s f0, f0, f1
    mul.s f0, f0, f0
    add.s f2, f2, f0
    lwc1  f0, 0x34(s1)
    lwc1  f1, 0x8(s0)
    sub.s f0, f0, f1
    mul.s f0, f0, f0
    add.s f2, f2, f0
    lui   v0, 0x42c8             ; 10 m
    mtc1  v0, f1
    lui   v0, {MAX_HI}             ; the hand range
    c.lt.s f2, f1
    bc1t  no
    ori   v0, v0, {MAX_LO}
    beqz  s3, far
    nop
    lui   v0, 0x45af             ; 75 m with a launcher
    ori   v0, v0, 0xc800
far:
    mtc1  v0, f1
    nop
    c.le.s f2, f1
    bc1f  no
    lui   a0, %hi(RNG)
    addiu a0, a0, %lo(RNG)
    move  a1, zero
    move  a2, zero
    mtc1  zero, f12
    lui   v0, 0x3f80
    jal   RandomFloat            ; 0..1
    mtc1  v0, f13
    mtc1  s5, f1
    nop
    c.lt.s f0, f1
    bc1f  no
    lui   at, %hi(SCENE)
    b     level
    lw    a0, %lo(SCENE)(at)
"""

# the second cave: the level, the throw, and the two entries
SRC2 = """
level:
    jal   FindLevel              ; the aim point must be on a level
    move  a1, s0
    beqz  v0, no
    move  a0, s2
    move  a1, s0
    move  a2, v0
    jal   IsOkToFragHereNow      ; no friendly near the blast, 30 s since the team's last
    move  a3, s1
    beqz  v0, no
    move  a1, s1
    jal   SetFormationLeader
    lw    a0, 0xa4(s1)
    jal   New
    li    a0, 0x34
    beqz  v0, no
    nop
    jal   FragLocation
    move  a0, v0
    lwc1  f0, 0x0(s0)
    swc1  f0, 0x1c(v0)
    lwc1  f0, 0x4(s0)
    swc1  f0, 0x20(v0)
    lwc1  f0, 0x8(s0)
    swc1  f0, 0x24(v0)
    sw    zero, 0x2c(v0)
    lw    a0, 0xc(s1)
    jal   AddElement             ; on top of the soldier's script: it runs next
    move  a1, v0
    b     out
    li    v0, 1
no:
    move  v0, zero
out:
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    lq    s3, 0x30(sp)
    lq    s4, 0x40(sp)
    lq    s5, 0x50(sp)
    ld    ra, 0x60(sp)
    jr    ra
    addiu sp, sp, 0x70

; SuppressBehavior::Process: a0 = the behaviour (aim point +0x34), a1 = the soldier
suppress:
    addiu sp, sp, -0x30
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sd    ra, 0x20(sp)
    move  s0, a0
    move  s1, a1
    addiu a2, a0, 0x34
    jal   decide
    lui   a3, {CHANCE_SUPPRESS}
    beqz  v0, spray
    li    v1, 2                  ; wait for the throw
    b     sout
    sw    v1, 0x20(s0)
spray:
    move  a0, s0
    jal   StartSpraying
    move  a1, s1
    b     sout
    nop

; EngageThreatBehavior::Process, state 0: a0 = the behaviour (threat +0x1C), a1 = the soldier
engage:
    addiu sp, sp, -0x30
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sd    ra, 0x20(sp)
    move  s0, a0
    move  s1, a1
    lw    a0, 0x1c(a0)
    beqz  a0, start
    nop
    lw    t9, 0(a0)
    lw    t9, 0x32c(t9)          ; the threat's position
    jalr  t9
    nop
    beqz  v0, start
    move  a2, v0
    move  a1, s1
    jal   decide
    lui   a3, {CHANCE_ENGAGE}
    bnez  v0, sout               ; thrown: state 0 stays, the engagement asks again after
    nop
start:
    move  a0, s0
    jal   EngageStart
    move  a1, s1
sout:
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    ld    ra, 0x20(sp)
    jr    ra
    addiu sp, sp, 0x30
"""

# GetFacingForProjectile's height sum with the grenade's drag. Entered by jal from 0x003E9F4C, in the
# loop over angles: f0 = sin a, f25 = the speed, f26 = D / (v cos a) (the drag-free time to the target's
# distance D), f20 = -g, f21 = the target's height over the hand, v0 = 2.0 (for the game's own sum).
# With drag k (1/s): the fraction of the speed left at D is y = 1 - k t26 = e^-kt, and the height there
# is (v sin a + g/k) t26 - (g/k) t. ln y = 256 ln y^(1/256), a short series. Returns to the compare
# (0x003E9F74) with f0 = the height; the game's own sum for anything aim_vel did not set up.
SRC_AIM = """
aim_h:
    lui   t0, %hi(aim_k)
    lw    t1, %lo(aim_tag)(t0)
    mfc1  t2, $f25
    bne   t1, t2, ah_free           ; not a hand throw aim_vel set up (a launcher)
    lwc1  $f3, %lo(aim_k)(t0)       ; k = drag / mass
    mfc1  t1, $f3
    beqz  t1, ah_free
    mul.s $f5, $f3, $f26            ; k t26
    lui   t1, 0x3f80
    mtc1  t1, $f6                   ; 1
    sub.s $f7, $f6, $f5             ; y
    lui   t1, 0x3c23                ; 0.00995
    mtc1  t1, $f8
    c.lt.s $f8, $f7
    bc1t  ah_root
    li    t1, 8
    mov.s $f7, $f8                  ; the drag stops it short of D: t = 4.6 / k, far below
ah_root:
    sqrt.s $f7, $f7
    addiu t1, t1, -1
    bnez  t1, ah_root
    nop
    sub.s $f7, $f7, $f6             ; d = y^(1/256) - 1
    lui   t1, 0x3eab                ; 1/3
    mtc1  t1, $f8
    lui   t1, 0xbf00                ; -1/2
    mul.s $f8, $f8, $f7
    mtc1  t1, $f9
    add.s $f8, $f8, $f9
    mul.s $f8, $f8, $f7
    add.s $f8, $f8, $f6
    mul.s $f8, $f8, $f7             ; ln y^(1/256) = d - d^2/2 + d^3/3
    lui   t1, 0xc380                ; -256
    mtc1  t1, $f9
    mul.s $f8, $f8, $f9             ; kt
    div.s $f8, $f8, $f3             ; t
    div.s $f4, $f20, $f3            ; -g/k
    mul.s $f2, $f25, $f0
    sub.s $f2, $f2, $f4
    mul.s $f2, $f2, $f26
    mul.s $f4, $f4, $f8
    j     FACING_CMP
    add.s $f0, $f2, $f4
ah_free:
    jr    ra
    mul.s $f1, $f25, $f26           ; the word the call replaced
"""

# aim_vel: jal from GetFacingForProjectile's thrown-item path, whose slot loaded f25 = the hand speed;
# s0 = the target, s1 = the HumanAI, s2 = the item (+8 its projectile). An AI-controlled soldier aiming
# more than NEAR m (flat) away throws harder: f25 x the range's factor, and his HumanMotion's padding
# halfword +0x1E (never written by the game: savestates hold junk there) carries BOOST to the throw.
# Nearer he throws as the game does -- a harder throw at a near target is nearly flat and runs on long
# past it. Notes the projectile's drag / mass for aim_h, tagged with the speed; goes on at 0x003E9DD4.
SRC_ARM = """
aim_vel:
    lw    t0, 0x14(s1)
    lbu   t1, 0x138(t0)             ; 1: AI-controlled
    lw    t2, 0x458(t0)             ; his HumanMotion
    addiu t1, t1, -1
    bnez  t1, av_k
    sh    zero, 0x1e(t2)
    lwc1  $f0, 0x0(s0)
    lwc1  $f1, 0x2c(s1)
    sub.s $f0, $f0, $f1
    lwc1  $f1, 0x4(s0)
    lwc1  $f2, 0x30(s1)
    sub.s $f1, $f1, $f2
    mul.s $f0, $f0, $f0
    mul.s $f1, $f1, $f1
    add.s $f0, $f0, $f1
    lui   t1, {NEAR_HI}
    mtc1  t1, $f1
    nop
    c.lt.s $f1, $f0
    bc1f  av_k
    lui   t1, {ARM_HI}
    mtc1  t1, $f0
    li    t1, {BOOST}
    sh    t1, 0x1e(t2)
    mul.s $f25, $f25, $f0
av_k:
    jal   DATAMGR
    nop
    lw    t9, 0(v0)
    lw    t9, 0x48(t9)              ; IkeDataMgr::GetProjectileData
    move  a0, v0
    jalr  t9
    lhu   a1, 8(s2)
    beqz  v0, av_set
    mtc1  zero, $f0
    lwc1  $f1, 0x34(v0)             ; weight
    c.lt.s $f0, $f1
    bc1f  av_set
    nop
    lwc1  $f0, 0x38(v0)             ; AirResistanceConstant
    div.s $f0, $f0, $f1
av_set:
    lui   t0, %hi(aim_k)
    swc1  $f0, %lo(aim_k)(t0)
    j     FACING_ON
    swc1  $f25, %lo(aim_tag)(t0)
aim_k:
    .word 0
aim_tag:
    .word 0
"""

# arm: HumanMotion's throw reads the hand speed through it (a0 = IkeConstants, s3 = HumanMotion, +4 the
# SimHuman): x the range's factor when aim_vel marked the throw and the AI still controls him. The mark
# is used up.
SRC_ARM2 = """
arm:
    lwc1  $f0, 0x23c(a0)            ; ManlyGrenadeVelocity
    lw    t0, 4(s3)
    lbu   t0, 0x138(t0)
    lhu   t1, 0x1e(s3)
    sh    zero, 0x1e(s3)
    addiu t0, t0, -1
    bnez  t0, arm_out
    addiu t1, t1, -{BOOST}
    bnez  t1, arm_out
    lui   t1, {ARM_HI}
    mtc1  t1, $f1
    nop
    mul.s $f0, $f0, $f1
arm_out:
    jr    ra
    nop
"""

_AIM_STOCK_HEX = (    # grsmoke's second cave's tail, 0x00175E80..0x00175F30
    "24020001 AEC30018 358C3C50 8E630000 AEC3001C 8E840000 AEC40020 8E230000"
    "AEC30024 8E040000 AEC40028 8E430000 8CC40000 8D050000 8DC60000 8D670000"
    "8D280000 A6C3002C A6C4002E A6C50030 A6C60032 A6C70034 A6C80036 8DE40000"
    "8DA50000 8D430000 A2D5003E A2C3003C A2D7003D A6C40038 8D830000 A6C5003A"
    "A2C3003F DFBF0080 DFB70070 DFB60060 DFB50050 DFB40040 DFB30030 DFB20020"
    "DFB10010 DFB00000 03E00008 27BD0090"
)
_ARM_STOCK_HEX = (    # grsmoke's report cave's tail, 0x00197C30..0x00197CF4
    "FFBF0050 0C060CC8 0100802D DA280000 DA440000 DA450010 DA460020 DA470030"
    "DA890000 DA6A0000 DA8B0000 DA6C0000 4BE821BC 4BE828BD 4BE830BE 4BE83A0B"
    "4BC84ADB 4BC8531B 4A0002FF 4A0002FF 48C08000 4BAB42EC 4BA8632C 4A2B4B3C"
    "4A2C533C 4A0002FF 22310010 DA280000 2210FFFF 48438000 306300C0 10600004"
    "00000000 1410FFEA 00000000 20030001 10400003 0060802D 0C060CDE 00000000"
    "0200102D DFBF0050 DFB40040 DFB30030 DFB20020 DFB10010 DFB00000 03E00008"
    "27BD0060"
)
_ARM2_STOCK_HEX = (   # grsmoke's thread cave's tail, 0x00173A68..0x00173AA4
    "0040202D 10000005 0260102D 0220282D 0C05E85C 0000982D 0260102D DFBF0050"
    "DFB40040 DFB30030 DFB20020 DFB10010 DFB00000 03E00008 27BD0060"
)
_CAVE2_STOCK_HEX = (   # sceSifGetOtherData, 0x0017D220..0x0017D378
    "27BDFF70 FFB10030 0080882D FFB50070 FFB40060 3C040061 FFB30050 00C0A02D"
    "FFB20040 00A0982D FFB00020 00E0A82D FFBF0080 0100902D 0C05F3C2 24846F80"
    "0040802D 1200003B 2402FFFF 8E020018 32430001 AE300000 AE220004 AE130020"
    "AE140024 AE150028 AE100014 14600022 AE11001C 24020001 AFA00008 AFA20004"
    "0C05E8B8 03A0202D 04410005 AE220008 0C05F3EC 0200202D 10000026 2402FFFD"
    "3C048000 0200282D 3484000C 24060040 0000382D 0000402D 0C05F2B2 0000482D"
    "14400007 00000000 0C05F3EC 0200202D 0C05E8BC 8E240008 10000016 2402FFFE"
    "0C05E8C8 8E240008 0C05E8BC 8E240008 10000010 0000102D 2402FFFF 3C048000"
    "AE220008 3484000C 0200282D 24060040 0000382D 0000402D 0C05F2B2 0000482D"
    "14400004 0000102D 0C05F3EC 0200202D 2402FFFE DFBF0080 DFB50070 DFB40060"
    "DFB30050 DFB20040 DFB10030 DFB00020 03E00008 27BD0090"
)
_CAVE_STOCK_HEX = (   # sceDread, 0x00180160..0x001802B8
    "27BDFF70 FFB10050 FFB30070 00A0882D FFB20060 3C130061 FFB00040 FFBF0080"
    "0C05F7AE 26727000 0040802D 0C05F8CC 2404000B 3C020057 8C434FEC 14600005"
    "00000000 0C05F8D8 00000000 1000003B 2402FFFF 12000004 00000000 8E020004"
    "54400005 8E020000 0C05F8D8 00000000 10000032 2402FFF7 24030001 AE510010"
    "27A40010 AE42000C AFA30014 AFA00018 0C05E8B8 AFA00024 0040882D 27A30030"
    "3C020061 AE717000 24507C40 3C040062 24020004 AE430004 AE420008 24848700"
    "0240382D 2405000B AFA00000 0000302D 24080020 0200482D 240A0004 0C05F5AA"
    "0000582D 04410007 3C022000 0C05E8C8 0220202D 0C05F8D8 00000000 1000000F"
    "2402FFF5 02021025 0C05F8D8 8C500000 16000005 00000000 0C05E8BC 0220202D"
    "10000006 2402FFF5 0C05E8C8 0220202D 0C05E8BC 0220202D 8FA20030 DFBF0080"
    "DFB30070 DFB20060 DFB10050 DFB00040 03E00008 27BD0090"
)


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


JS_STOCK = _stock_words(CAVE, _CAVE_STOCK_HEX)
JS_STOCK.update(_stock_words(CAVE2, _CAVE2_STOCK_HEX))
JS_STOCK.update(_stock_words(AIM_CAVE, _AIM_STOCK_HEX))
JS_STOCK.update(_stock_words(ARM_CAVE, _ARM_STOCK_HEX))
JS_STOCK.update(_stock_words(ARM2_CAVE, _ARM2_STOCK_HEX))
JS_STOCK[HOOK] = HOOK_STOCK
JS_STOCK[ENGAGE_HOOK] = ENGAGE_HOOK_STOCK
JS_STOCK[LOS] = LOS_STOCK
JS_STOCK[AIM_VEL] = AIM_VEL_STOCK
JS_STOCK[AIM_SUM] = AIM_SUM_STOCK
JS_STOCK[ARM] = ARM_STOCK


def _bits(f):
    return struct.unpack("<I", struct.pack("<f", f))[0]


def _assemble(rng="50", chance="normal"):
    """(decision words, second-cave words, second-cave labels)."""
    limit = _bits(RANGES[rng][0] ** 2)
    src2 = SRC2.format(CHANCE_SUPPRESS=hex(FRAG_CHANCES[chance][2]), CHANCE_ENGAGE=hex(FRAG_CHANCES[chance][1]))
    words2, labels2 = assemble(src2, CAVE2, dict(SYMS, decide=CAVE))
    src = SRC.format(MAX_HI=hex(limit >> 16), MAX_LO=hex(limit & 0xFFFF))
    words, labels = assemble(src, CAVE, dict(SYMS, no=labels2["no"], level=labels2["level"]))
    assert labels["decide"] == CAVE
    if CAVE + 4 * len(words) > CAVE_END or CAVE2 + 4 * len(words2) > CAVE2_END:
        raise ValueError("grenade routine outgrows its caves")
    return words, words2, labels2


def _assemble_aim(rng="50"):
    """(aim_h words, aim_vel words, arm words, labels)."""
    arm = _bits(RANGES[rng][1])
    assert arm & 0xFFFF == 0 and _bits(NEAR ** 2) & 0xFFFF == 0
    k = dict(ARM_HI=hex(arm >> 16), NEAR_HI=hex(_bits(NEAR ** 2) >> 16), BOOST=hex(BOOST))
    wa, la = assemble(SRC_ARM.format(**k), ARM_CAVE, AIM_SYMS)
    w2, l2 = assemble(SRC_ARM2.format(**k), ARM2_CAVE, AIM_SYMS)
    wh, lh = assemble(SRC_AIM, AIM_CAVE, dict(AIM_SYMS, aim_k=la["aim_k"], aim_tag=la["aim_tag"]))
    for base, end, w in ((AIM_CAVE, AIM_CAVE_END, wh), (ARM_CAVE, ARM_CAVE_END, wa), (ARM2_CAVE, ARM2_CAVE_END, w2)):
        if base + 4 * len(w) > end:
            raise ValueError("grenade aim outgrows its cave at %#x (%d words, room %d)" % (base, len(w), (end - base) // 4))
    return wh, wa, w2, dict(la, **lh, **l2)


def edits(rng="50", chance="normal"):
    """(va, value, stock, note)."""
    words, words2, labels2 = _assemble(rng, chance)
    out = [(CAVE + 4 * i, w, JS_STOCK[CAVE + 4 * i], "enemy grenades: the throw decision")
           for i, w in enumerate(words)]
    out += [(CAVE2 + 4 * i, w, JS_STOCK[CAVE2 + 4 * i],
             "enemy grenades: the throw, and the suppress / engage entries")
            for i, w in enumerate(words2)]
    out.append((HOOK, assemble("jal %#x" % labels2["suppress"], HOOK)[0][0], HOOK_STOCK,
                "enemy grenades: suppressive fire asks the routine first"))
    out.append((ENGAGE_HOOK, assemble("jal %#x" % labels2["engage"], ENGAGE_HOOK)[0][0],
                ENGAGE_HOOK_STOCK, "enemy grenades: a new engagement asks the routine first"))
    out.append((LOS, LOS_NEW, LOS_STOCK, "enemy grenades: a throw needs 4 m of clear arc, not 10 m"))
    wh, wa, w2, la = _assemble_aim(rng)
    out += [(AIM_CAVE + 4 * i, w, JS_STOCK[AIM_CAVE + 4 * i], "AI grenades: the aim with drag")
            for i, w in enumerate(wh)]
    out += [(ARM_CAVE + 4 * i, w, JS_STOCK[ARM_CAVE + 4 * i], "AI grenades: the aim's speed and drag")
            for i, w in enumerate(wa)]
    out.append((AIM_VEL, assemble("jal %#x" % la["aim_vel"], AIM_VEL)[0][0], AIM_VEL_STOCK,
                "AI grenades: the aim learns the throw's speed and drag"))
    out.append((AIM_SUM, assemble("jal %#x" % la["aim_h"], AIM_SUM)[0][0], AIM_SUM_STOCK,
                "AI grenades: the aim's height at the target counts the drag"))
    if RANGES[rng][1] != 1.0:
        out += [(ARM2_CAVE + 4 * i, w, JS_STOCK[ARM2_CAVE + 4 * i], "AI grenades: the AI's throw speed")
                for i, w in enumerate(w2)]
        out.append((ARM, assemble("jal %#x" % la["arm"], ARM)[0][0], ARM_STOCK,
                    "AI grenades: an AI soldier throws x%g as hard" % RANGES[rng][1]))
    return out


def js_edits(v: dict):
    if not v.get("js_enemy_grenades"):
        return []
    return edits(v.get("js_enemy_frag_range", "50"), v.get("js_enemy_frag_chance", "normal"))


# ---------------------------------------------------------------------------
# Ghost Recon (SLUS-20613)
# ---------------------------------------------------------------------------

GR_CAVE, GR_CAVE_END = 0x00416EF0, 0x0041709C      # sceMkdir: the decision (and ShouldIFrag's stand-in)
GR_CAVE2, GR_CAVE2_END = 0x00414848, 0x004149A0    # sceSifGetOtherData: the throw, the engage entry
GR_AIM_CAVE, GR_AIM_CAVE_END = 0x0040D1A8, 0x0040D3A0   # sceCdDiskReady: aim_h, aim_vel, arm
GR_HOOK, GR_HOOK_STOCK = 0x001BCD88, 0x0C06F408    # jal ShouldIFrag (slot: addiu a2, s1, 0x34)
GR_ENGAGE_HOOK, GR_ENGAGE_HOOK_STOCK = 0x001B2F10, 0x0C06CA18   # jal ShouldISpray (slot: swc1 f0, 0x20(s2))
GR_LOS, GR_LOS_STOCK, GR_LOS_NEW = 0x001B4404, 0x3C034120, 0x3C034080   # lui v1, 10.0 -> 4.0
GR_AIM_VEL, GR_AIM_VEL_STOCK = 0x00199D88, 0x10000018   # b 0x199dec (slot: lwc1 f20, 0x234(v0), the hand speed)
GR_AIM_SUM, GR_AIM_SUM_STOCK = 0x00199F4C, 0x461AA042   # mul.s f1, f20, f26: the loop's height sum starts
GR_ARM, GR_ARM_STOCK = 0x0035D8E0, 0x0C0D7700           # jal ManlyGrenadeVelocity (slot: move a0, v0)

GR_SYMS = dict(
    ShouldISpray=0x001B2860, ENGAGE_ON=0x001B2F3C, GetNumGrenades=0x0019A0A0,
    HasGrenadeLauncher=0x0019A180, GetPlayerAI=0x0018C930, FindLevel=0x00504690, SCENE=0x006376D0,
    IsOkToFragHereNow=0x00190290, SetFormationLeader=0x0018CFA0, New=0x00102DB0,
    FragLocation=0x001B4650, AddElement=0x001BAEC0, RandomFloat=0x00113DC0, RNG=0x005DF770,
)
GR_AIM_SYMS = dict(DATAMGR=0x005E4D98, FACING_ON=0x00199DEC, FACING_CMP=0x00199F78)

# should: SuppressBehavior::Process's call to ShouldIFrag (a0 the behaviour, a1 the soldier, a2 its aim
# point) -- the answer only; the game queues the throw and waits (state 2) itself. decide: a1 the HumanAI,
# a2 the aim point, a3 the chance (float bits); v0 = 1 when it queued a FragLocationBehavior. s4 tells the
# two apart. Ghost Recon's layout is Jungle Storm's but for the sim word (SimHuman +0x588, JS +0x5B8).
GR_SRC = """
should:
    lui   a3, {CHANCE_SUPPRESS}
    b     dec_go
    move  t0, zero               ; (delay) the answer only
decide:
    li    t0, 1                  ; queue the throw here
dec_go:
    addiu sp, sp, -0x70
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s2, 0x20(sp)
    sq    s3, 0x30(sp)
    sq    s4, 0x40(sp)
    sq    s5, 0x50(sp)
    sd    ra, 0x60(sp)
    move  s0, a2
    move  s1, a1
    move  s5, a3
    move  s4, t0
    lbu   v0, 0x132(s1)          ; carries grenades at all
    beqz  v0, no
    lw    v0, 0x14(s1)
    lw    v0, 0x588(v0)
    bnez  v0, no
    lw    s2, 0xa4(s1)           ; its fireteam
    beqz  s2, no
    li    s3, 2                  ; grenades needed: 2, or 1 when the script runs the team
    lbu   v0, 0xd9(s2)
    beqz  v0, count
    nop
    li    s3, 1
count:
    jal   GetNumGrenades
    move  a0, s1
    slt   at, v0, s3
    bnez  at, no
    nop
    jal   HasGrenadeLauncher
    move  a0, s1
    andi  s3, v0, 0xff           ; s3 = launcher
    lbu   v0, 0xd9(s2)
    bnez  v0, roe
    nop
    jal   GetPlayerAI            ; never the player's own fireteam
    move  a0, s2
    bnez  v0, no
    nop
roe:
    lw    v0, 0x20(s2)           ; combat ROE
    beqz  v0, no
    lw    v0, 0x1c(s2)           ; movement ROE
    beqz  v0, no
    lwc1  f0, 0x2c(s1)           ; distance squared, soldier to aim point
    lwc1  f1, 0x0(s0)
    sub.s f0, f0, f1
    mul.s f2, f0, f0
    lwc1  f0, 0x30(s1)
    lwc1  f1, 0x4(s0)
    sub.s f0, f0, f1
    mul.s f0, f0, f0
    add.s f2, f2, f0
    lwc1  f0, 0x34(s1)
    lwc1  f1, 0x8(s0)
    sub.s f0, f0, f1
    mul.s f0, f0, f0
    add.s f2, f2, f0
    lui   v0, 0x42c8             ; 10 m
    mtc1  v0, f1
    lui   v0, {MAX_HI}             ; the hand range
    c.lt.s f2, f1
    bc1t  no
    ori   v0, v0, {MAX_LO}
    beqz  s3, far
    nop
    lui   v0, 0x45af             ; 75 m with a launcher
    ori   v0, v0, 0xc800
far:
    mtc1  v0, f1
    nop
    c.le.s f2, f1
    bc1f  no
    lui   a0, %hi(RNG)
    addiu a0, a0, %lo(RNG)
    move  a1, zero
    move  a2, zero
    mtc1  zero, f12
    lui   v0, 0x3f80
    jal   RandomFloat            ; 0..1
    mtc1  v0, f13
    mtc1  s5, f1
    nop
    c.lt.s f0, f1
    bc1f  no
    lui   at, %hi(SCENE)
    b     level
    lw    a0, %lo(SCENE)(at)
"""

# the second cave: the level, the throw (decide only), and EngageThreatBehavior's entry
GR_SRC2 = """
level:
    jal   FindLevel              ; the aim point must be on a level
    move  a1, s0
    beqz  v0, no
    move  a0, s2
    move  a1, s0
    move  a2, v0
    jal   IsOkToFragHereNow      ; no friendly near the blast, 30 s since the team's last
    move  a3, s1
    beqz  v0, no
    nop
    beqz  s4, out                ; ShouldIFrag's caller queues the throw itself
    li    v0, 1
    move  a1, s1
    jal   SetFormationLeader
    lw    a0, 0xa4(s1)
    jal   New
    li    a0, 0x34
    beqz  v0, no
    nop
    jal   FragLocation
    move  a0, v0
    lwc1  f0, 0x0(s0)
    swc1  f0, 0x1c(v0)
    lwc1  f0, 0x4(s0)
    swc1  f0, 0x20(v0)
    lwc1  f0, 0x8(s0)
    swc1  f0, 0x24(v0)
    sw    zero, 0x2c(v0)
    lw    a0, 0xc(s1)
    jal   AddElement             ; on top of the soldier's script: it runs next
    move  a1, v0
    b     out
    li    v0, 1
no:
    move  v0, zero
out:
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    lq    s3, 0x30(sp)
    lq    s4, 0x40(sp)
    lq    s5, 0x50(sp)
    ld    ra, 0x60(sp)
    jr    ra
    addiu sp, sp, 0x70

; EngageThreatBehavior::Process, state 0, in place of its ShouldISpray call: a0 = the behaviour (threat
; +0x1C), a1 = the soldier. A throw skips ShouldISpray / StartSpraying / StartAiming (on at 0x001B2F3C)
; and leaves the engagement in state 0; otherwise the stock question, answered to the caller.
engage:
    addiu sp, sp, -0x30
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sd    ra, 0x20(sp)
    move  s0, a0
    move  s1, a1
    lw    a0, 0x1c(a0)
    beqz  a0, start
    nop
    lw    t9, 0(a0)
    lw    t9, 0x328(t9)          ; the threat's position
    jalr  t9
    nop
    beqz  v0, start
    move  a2, v0
    move  a1, s1
    jal   decide
    lui   a3, {CHANCE_ENGAGE}
    beqz  v0, start
    nop
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    j     ENGAGE_ON              ; thrown: state 0 stays, the engagement asks again after
    addiu sp, sp, 0x30
start:
    move  a0, s0
    move  a1, s1
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    ld    ra, 0x20(sp)
    j     ShouldISpray
    addiu sp, sp, 0x30
"""

# aim_h for Ghost Recon's loop (0x00199F4C): f0 = sin a, f20 = the speed, f26 = D / (v cos a), f24 = +g
# (Ghost Recon negates it inside the sum), f22 = the target's height (the compare at 0x00199F78).
GR_SRC_AIM = """
aim_h:
    lui   t0, %hi(aim_k)
    lw    t1, %lo(aim_tag)(t0)
    mfc1  t2, $f20
    bne   t1, t2, ah_free           ; not a hand throw aim_vel set up (a launcher)
    lwc1  $f3, %lo(aim_k)(t0)       ; k = drag / mass
    mfc1  t1, $f3
    beqz  t1, ah_free
    mul.s $f5, $f3, $f26            ; k t26
    lui   t1, 0x3f80
    mtc1  t1, $f6                   ; 1
    sub.s $f7, $f6, $f5             ; y
    lui   t1, 0x3c23                ; 0.00995
    mtc1  t1, $f8
    c.lt.s $f8, $f7
    bc1t  ah_root
    li    t1, 8
    mov.s $f7, $f8                  ; the drag stops it short of D: t = 4.6 / k, far below
ah_root:
    sqrt.s $f7, $f7
    addiu t1, t1, -1
    bnez  t1, ah_root
    nop
    sub.s $f7, $f7, $f6             ; d = y^(1/256) - 1
    lui   t1, 0x3eab                ; 1/3
    mtc1  t1, $f8
    lui   t1, 0xbf00                ; -1/2
    mul.s $f8, $f8, $f7
    mtc1  t1, $f9
    add.s $f8, $f8, $f9
    mul.s $f8, $f8, $f7
    add.s $f8, $f8, $f6
    mul.s $f8, $f8, $f7             ; ln y^(1/256) = d - d^2/2 + d^3/3
    lui   t1, 0xc380                ; -256
    mtc1  t1, $f9
    mul.s $f8, $f8, $f9             ; kt
    div.s $f8, $f8, $f3             ; t
    neg.s $f4, $f24                 ; -g
    div.s $f4, $f4, $f3             ; -g/k
    mul.s $f2, $f20, $f0
    sub.s $f2, $f2, $f4
    mul.s $f2, $f2, $f26
    mul.s $f4, $f4, $f8
    j     FACING_CMP
    add.s $f0, $f2, $f4
ah_free:
    jr    ra
    mul.s $f1, $f20, $f26           ; the word the call replaced
"""

# aim_vel: jal from GetFacingForProjectile's thrown-item path (0x00199D88), whose slot loaded f20 = the
# hand speed; s0 = the target, s1 = the HumanAI, s2 = the item (+8 its projectile). As Jungle Storm's,
# with Ghost Recon's IkeDataMgr pointer read directly.
GR_SRC_ARM = """
aim_vel:
    lw    t0, 0x14(s1)
    lbu   t1, 0x138(t0)             ; 1: AI-controlled
    lw    t2, 0x458(t0)             ; his HumanMotion
    addiu t1, t1, -1
    bnez  t1, av_k
    sh    zero, 0x1e(t2)
    lwc1  $f0, 0x0(s0)
    lwc1  $f1, 0x2c(s1)
    sub.s $f0, $f0, $f1
    lwc1  $f1, 0x4(s0)
    lwc1  $f2, 0x30(s1)
    sub.s $f1, $f1, $f2
    mul.s $f0, $f0, $f0
    mul.s $f1, $f1, $f1
    add.s $f0, $f0, $f1
    lui   t1, {NEAR_HI}
    mtc1  t1, $f1
    nop
    c.lt.s $f1, $f0
    bc1f  av_k
    lui   t1, {ARM_HI}
    mtc1  t1, $f0
    li    t1, {BOOST}
    sh    t1, 0x1e(t2)
    mul.s $f20, $f20, $f0
av_k:
    lui   v0, %hi(DATAMGR)
    lw    v0, %lo(DATAMGR)(v0)      ; IkeDataMgr
    lw    t9, 0(v0)
    lw    t9, 0x48(t9)              ; IkeDataMgr::GetProjectileData
    move  a0, v0
    jalr  t9
    lhu   a1, 8(s2)
    beqz  v0, av_set
    mtc1  zero, $f0
    lwc1  $f1, 0x34(v0)             ; weight
    c.lt.s $f0, $f1
    bc1f  av_set
    nop
    lwc1  $f0, 0x38(v0)             ; AirResistanceConstant
    div.s $f0, $f0, $f1
av_set:
    lui   t0, %hi(aim_k)
    swc1  $f0, %lo(aim_k)(t0)
    j     FACING_ON
    swc1  $f20, %lo(aim_tag)(t0)
aim_k:
    .word 0
aim_tag:
    .word 0
"""

# arm: HumanMotion::HandleThrowItem reads the hand speed through it (0x0035D8E0; a0 = IkeConstants, s3 =
# HumanMotion, +4 the SimHuman); Ghost Recon's ManlyGrenadeVelocity is IkeConstants +0x234.
GR_SRC_ARM2 = """
arm:
    lwc1  $f0, 0x234(a0)            ; ManlyGrenadeVelocity
    lw    t0, 4(s3)
    lbu   t0, 0x138(t0)
    lhu   t1, 0x1e(s3)
    sh    zero, 0x1e(s3)
    addiu t0, t0, -1
    bnez  t0, arm_out
    addiu t1, t1, -{BOOST}
    bnez  t1, arm_out
    lui   t1, {ARM_HI}
    mtc1  t1, $f1
    nop
    mul.s $f0, $f0, $f1
arm_out:
    jr    ra
    nop
"""

_GR_CAVE_STOCK_HEX = (   # sceMkdir, 0x00416EF0..0x0041709C
    "27BDFF30 FFB10050 FFB600A0 0080882D FFB700B0 00A0B02D FFB20060 24040007"
    "FFBF00C0 3C17005F FFB50090 26F2E100 FFB40080 FFB30070 0C10563E FFB00040"
    "3C020057 8C43E1C0 54600004 92220000 0C10567E 00000000 92220000 0000802D"
    "00021E00 10600011 A2420010 27B30030 3C15005F 3C14005F 26100001 00000000"
    "2A020400 1040000C 02301021 02502021 90430000 A0830010 00031E00 5460FFF8"
    "26100001 10000005 24020400 27B30030 3C15005F 3C14005F 24020400 56020004"
    "AE56000C A240040F 241003FF AE56000C 24020001 AFA20014 27A40010 AFA00018"
    "2694ED40 0C1046B8 AFA00024 0040882D AE530004 24020004 AE510000 AE420008"
    "26A4F3C0 26E7E100 26080011 AFA00000 24050007 0000302D 0280482D 240A0004"
    "0C10531C 0000582D 04410007 3C022000 0C1046BC 0220202D 0C10564A 00000000"
    "1000000F 2402FFF5 02821025 0C10564A 8C500000 16000005 00000000 0C1046BC"
    "0220202D 10000006 2402FFF5 0C1046C8 0220202D 0C1046BC 0220202D 8FA20030"
    "DFBF00C0 DFB700B0 DFB600A0 DFB50090 DFB40080 DFB30070 DFB20060 DFB10050"
    "DFB00040 03E00008 27BD00D0"
)
_GR_CAVE2_STOCK_HEX = (  # sceSifGetOtherData, 0x00414848..0x004149A0
    "27BDFF70 FFB10030 0080882D FFB50070 FFB40060 3C04005F FFB30050 00C0A02D"
    "FFB20040 00A0982D FFB00020 00E0A82D FFBF0080 0100902D 0C10517E 2484E080"
    "0040802D 1200003B 2402FFFF 8E020018 32430001 AE300000 AE220004 AE130020"
    "AE140024 AE150028 AE100014 14600022 AE11001C 24020001 AFA00008 AFA20004"
    "0C1046B8 03A0202D 04410005 AE220008 0C1051A8 0200202D 10000026 2402FFFD"
    "3C048000 0200282D 3484000C 24060040 0000382D 0000402D 0C105076 0000482D"
    "14400007 00000000 0C1051A8 0200202D 0C1046BC 8E240008 10000016 2402FFFE"
    "0C1046C8 8E240008 0C1046BC 8E240008 10000010 0000102D 2402FFFF 3C048000"
    "AE220008 3484000C 0200282D 24060040 0000382D 0000402D 0C105076 0000482D"
    "14400004 0000102D 0C1051A8 0200202D 2402FFFE DFBF0080 DFB50070 DFB40060"
    "DFB30050 DFB20040 DFB10030 DFB00020 03E00008 27BD0090"
)
_GR_AIM_STOCK_HEX = (    # sceCdDiskReady, 0x0040D1A8..0x0040D3A0
    "27BDFF60 FFB60070 3C160056 FFB20030 8EC21D90 0080902D FFBF0090 FFB70080"
    "FFB50060 FFB40050 FFB30040 FFB10020 18400004 FFB00010 3C040058 0C104F22"
    "24846728 0C103144 3C130056 8E641DAC 0C1046CC 00000000 8E631DAC 1462005B"
    "24020006 0C10333A 24040001 14400045 0000202D 0C10510C 3C110056 8E221DC4"
    "0441002C 3C15005F 3C14005F 1000000B 3C170056 00000000 2403FFFF 00000000"
    "2442FFFF 00000000 00000000 00000000 00000000 1443FFFA 00000000 26B0B7D0"
    "3C058000 0200202D 34A5059A 0C1052A8 0000302D 04430013 8E020024 8EC21D90"
    "18400005 3C020010 3C040058 0C104F22 24846738 3C020010 2403FFFF 00000000"
    "2442FFFF 00000000 00000000 00000000 00000000 1443FFFA 00000000 1000FFE8"
    "26B0B7D0 1040FFDC 3C020010 10000003 AE201DC4 3C14005F 3C170056 2690B810"
    "AE92B810 0200202D 0C1050E0 24050004 26F12F80 26A4B7D0 0200382D AFA00000"
    "0000282D 0000302D 24080004 0220482D 240A0004 0C10531C 0000582D 04430009"
    "8EC21D90 8E641DAC 0C1046C0 00000000 3A440008 2403FFFF 24020006 1000000B"
    "0064100A 18400003 3C040058 0C104F22 24846758 3C022000 8E641DAC 02221025"
    "0C1046C0 8C500000 0200102D DFBF0090 DFB70080 DFB60070 DFB50060 DFB40050"
    "DFB30040 DFB20030 DFB10020 DFB00010 03E00008 27BD00A0"
)

GR_STOCK = _stock_words(GR_CAVE, _GR_CAVE_STOCK_HEX)
GR_STOCK.update(_stock_words(GR_CAVE2, _GR_CAVE2_STOCK_HEX))
GR_STOCK.update(_stock_words(GR_AIM_CAVE, _GR_AIM_STOCK_HEX))
GR_STOCK[GR_HOOK] = GR_HOOK_STOCK
GR_STOCK[GR_ENGAGE_HOOK] = GR_ENGAGE_HOOK_STOCK
GR_STOCK[GR_LOS] = GR_LOS_STOCK
GR_STOCK[GR_AIM_VEL] = GR_AIM_VEL_STOCK
GR_STOCK[GR_AIM_SUM] = GR_AIM_SUM_STOCK
GR_STOCK[GR_ARM] = GR_ARM_STOCK
assert len(GR_STOCK) == ((GR_CAVE_END - GR_CAVE) + (GR_CAVE2_END - GR_CAVE2)
                         + (GR_AIM_CAVE_END - GR_AIM_CAVE)) // 4 + 6

#: grsuppress's Ghost Recon sight-lost entry calls this (a1 the HumanAI, a2 the point, a3 the chance)
GR_DECIDE = GR_CAVE + 12


def _gr_assemble(rng="50", chance="normal"):
    """(decision words, second-cave words, all labels)."""
    limit = _bits(RANGES[rng][0] ** 2)
    src2 = GR_SRC2.format(CHANCE_ENGAGE=hex(FRAG_CHANCES[chance][1]))
    w2, l2 = assemble(src2, GR_CAVE2, dict(GR_SYMS, decide=GR_DECIDE))
    src = GR_SRC.format(MAX_HI=hex(limit >> 16), MAX_LO=hex(limit & 0xFFFF),
                        CHANCE_SUPPRESS=hex(FRAG_CHANCES[chance][2]))
    w1, l1 = assemble(src, GR_CAVE, dict(GR_SYMS, no=l2["no"], level=l2["level"]))
    assert l1["decide"] == GR_DECIDE and l1["should"] == GR_CAVE
    if GR_CAVE + 4 * len(w1) > GR_CAVE_END or GR_CAVE2 + 4 * len(w2) > GR_CAVE2_END:
        raise ValueError("GR grenade routine outgrows its caves (%d/%d, %d/%d words)"
                         % (len(w1), (GR_CAVE_END - GR_CAVE) // 4, len(w2), (GR_CAVE2_END - GR_CAVE2) // 4))
    return w1, w2, dict(l1, **l2)


def _gr_assemble_aim(rng="50"):
    """(aim_h + aim_vel + its two data words, arm words, labels) -- one cave, arm last."""
    arm = _bits(RANGES[rng][1])
    k = dict(ARM_HI=hex(arm >> 16), NEAR_HI=hex(_bits(NEAR ** 2) >> 16), BOOST=hex(BOOST))
    wa, la = assemble(GR_SRC_AIM + GR_SRC_ARM.format(**k), GR_AIM_CAVE, GR_AIM_SYMS)
    w2, l2 = assemble(GR_SRC_ARM2.format(**k), GR_AIM_CAVE + 4 * len(wa), GR_AIM_SYMS)
    assert (la["aim_k"] + 0x8000) >> 16 == (la["aim_tag"] + 0x8000) >> 16      # one %hi for both
    if GR_AIM_CAVE + 4 * (len(wa) + len(w2)) > GR_AIM_CAVE_END:
        raise ValueError("GR grenade aim outgrows its cave (%d words, room %d)"
                         % (len(wa) + len(w2), (GR_AIM_CAVE_END - GR_AIM_CAVE) // 4))
    return wa, w2, dict(la, **l2)


def gr_edits_for(rng="50", chance="normal"):
    """Ghost Recon (va, value, stock, note)."""
    w1, w2, lab = _gr_assemble(rng, chance)
    out = [(GR_CAVE + 4 * i, w, GR_STOCK[GR_CAVE + 4 * i], "enemy grenades: the throw decision")
           for i, w in enumerate(w1)]
    out += [(GR_CAVE2 + 4 * i, w, GR_STOCK[GR_CAVE2 + 4 * i], "enemy grenades: the throw, and the engage entry")
            for i, w in enumerate(w2)]
    out.append((GR_HOOK, assemble("jal %#x" % lab["should"], GR_HOOK)[0][0], GR_HOOK_STOCK,
                "enemy grenades: suppressive fire asks the routine instead of ShouldIFrag"))
    out.append((GR_ENGAGE_HOOK, assemble("jal %#x" % lab["engage"], GR_ENGAGE_HOOK)[0][0],
                GR_ENGAGE_HOOK_STOCK, "enemy grenades: a new engagement asks the routine first"))
    out.append((GR_LOS, GR_LOS_NEW, GR_LOS_STOCK, "enemy grenades: a throw needs 4 m of clear arc, not 10 m"))
    wa, w2a, la = _gr_assemble_aim(rng)
    out += [(GR_AIM_CAVE + 4 * i, w, GR_STOCK[GR_AIM_CAVE + 4 * i], "AI grenades: the aim with drag, its speed")
            for i, w in enumerate(wa)]
    out.append((GR_AIM_VEL, assemble("jal %#x" % la["aim_vel"], GR_AIM_VEL)[0][0], GR_AIM_VEL_STOCK,
                "AI grenades: the aim learns the throw's speed and drag"))
    out.append((GR_AIM_SUM, assemble("jal %#x" % la["aim_h"], GR_AIM_SUM)[0][0], GR_AIM_SUM_STOCK,
                "AI grenades: the aim's height at the target counts the drag"))
    if RANGES[rng][1] != 1.0:
        base = GR_AIM_CAVE + 4 * len(wa)
        out += [(base + 4 * i, w, GR_STOCK[base + 4 * i], "AI grenades: the AI's throw speed")
                for i, w in enumerate(w2a)]
        out.append((GR_ARM, assemble("jal %#x" % la["arm"], GR_ARM)[0][0], GR_ARM_STOCK,
                    "AI grenades: an AI soldier throws x%g as hard" % RANGES[rng][1]))
    return out


def gr_edits(v: dict):
    """Ghost Recon, under 'Enemies throw grenades more readily' (gr_enemy_grenades, grextras's words)."""
    if not v.get("gr_enemy_grenades"):
        return []
    return gr_edits_for(v.get("gr_enemy_frag_range", "50"), v.get("gr_enemy_frag_chance", "normal"))


def selftest(gr_elf: bytes, js_elf: bytes):
    """Every stock word against the executables, no address twice. [] = pass."""
    bad = []
    for va, w in JS_STOCK.items():
        off = va - 0x100000 + 0x100
        if int.from_bytes(js_elf[off:off + 4], "little") != w:
            bad.append("js %08X" % va)
    for va, w in GR_STOCK.items():
        off = va - 0x100000 + 0x80
        if int.from_bytes(gr_elf[off:off + 4], "little") != w:
            bad.append("gr %08X" % va)
    for game, fn, st in (("js", edits, JS_STOCK), ("gr", gr_edits_for, GR_STOCK)):
        for rng in RANGES:
            for chance in FRAG_CHANCES:
                e = fn(rng, chance)
                if len({va for va, *_ in e}) != len(e):
                    bad.append("%s duplicate VA" % game)
                if any(va not in st for va, *_ in e):
                    bad.append("%s VA without a stock word" % game)
    return bad

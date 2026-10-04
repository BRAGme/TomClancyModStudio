"""Smoke grenades: Jungle Storm (SLUS-20820).

Jungle Storm has no smoke grenade: its projectiles are the M67 frag, three
launcher rounds, shells and two joke files (CHICKEN.PRJ, SQUIRREL.PRJ, listed
in EQUIP_PRJ.DIR and loaded, carried by no kit). Smoke exists only as effects
-- burning wrecks and a few maps set "smoke_small/medium/large_type1-3" on
helper points, IkeEffectsMgr::CreateGeneralEffect (JS 0x002409D0) makes them,
and a name like "smoke_large_type3(45)" gives the effect a 45 s life (the
maps' own say 1000000). This adds one, in four parts.

  * The grenade. SQUIRREL.PRJ becomes a smoke grenade (projectile index 9;
    FRAG.PRJ is 4, the order EQUIP_PRJ.DIR loads them in, and every grenade
    in a savestate carried 4): the M67 model, a 2 s fuse, no blast, name token
    WPN_SMOKE, and visual explosion type 0 -- "none", which no shipped
    projectile uses and which marks it as smoke below. Every language's
    strings file gets "WPN_SMOKE" -> "SMOKE" in place of the PC-only
    "toggle_console" line (no code or data names it), same length.

  * Choosing it. SimHuman's change-magazine message (the reload key; the case
    at JS 0x003A62D8) asks SimHumanState::IsUsingItem (0x00334170, called at
    0x003A631C) before anything else. That call goes through a routine that,
    on a press while the current slot (SimHuman +0x1E7, inventory +0x514,
    vtable +0x2C) holds a thrown item (vtable 0x005A75B0) of frag or smoke,
    swaps the item's projectile index (+8) between 4 and 9 and answers "busy"
    so the press ends there. The count is shared; the HUD names the slot from
    the projectile file, so it reads FRAG or SMOKE. A throw reads the index
    at release (InventoryItem::GetIndex in HandleControllerThrewItem).

  * The cloud. IkeSimulationMgr::HandleDetonateProjectile (JS 0x0036FEA0)
    sends the explosion visual (message 0x1EF, Create at 0x0037018C), then
    the damage, then removes the projectile (message 0x53 at 0x00370408).
    The Create call goes through a routine: for a projectile whose visual
    type is 0 it sends TriggerGeneralEffect (0x1FB) the way the mission
    scripts do (JS 0x00352348: name, position, the up vector, room id from
    the scene's vtable +0x28 a metre above, -1), records the cloud, and
    resumes at the removal with no visual, no damage and no explosion alert.
    Anything else is created as before. The default look, "round", fires
    smoke_medium_type2, whose empty PARTICLE_EFFECT14.POB is rebuilt as a
    dome of smoke (see 'the round cloud' below).

  * Sight. A ring of the last 8 clouds {x, y, z + 1.5 m, time} is kept. A
    sight line that passes within 5 m of a cloud's centre from 2 s after it
    pops until 5 s before it ends is blocked, for AwarenessMgr::
    CheckLineOfSight (JS 0x003D3EF0; its four calls go through a routine that
    skips it -- the looker's eye from vtable +0x328, the target point from
    GetAwarenessLookToPoint 0x003D4A50) and for IkeSimulationMgr::
    LineOfSightClear (0x0037AA80, entered through a jump: the engagement's
    "still in sight" test, answered no). A clock that goes backwards (a
    load) forgets every cloud. Both routines return at once, untouched, when
    no cloud is alive.

  * The kits. js_smoke_kits gives some grenade kits smoke from the start:
    their <ItemFileName>frag.prj becomes squirrel.prj (four bytes of
    indentation pay for the longer name, so each .KIT keeps its length).
    The detonation routine recognises the smoke grenade by its explosion
    data (IkeDataMgr vtable +0x48, GetProjectileData(9), +0x4C): the
    howitzer shell (5) also has visual type 0.

  * The AI. See 'the AI pops smoke when it runs for cover' below: a
    soldier running for cover may first throw smoke 10 m toward his
    threat (caves 0x00197F00, 0x0018CAB0, both unreferenced routines).

Caves: three unreferenced library routines (DMA/GS register save and
restore) at 0x00175678 (99 words), 0x00175808 (82) and 0x00175D58 (118), and
a thread body with the routine that would start it (0x00173908, 103; only
the starter forms the body's address, and nothing calls the starter) -- no
call, branch, pointer or address formation reaches any of them from outside
in the image or either overlay, and no other option writes them. Not yet
played.

Ghost Recon (SLUS-20613), the gr_ options: the same grenade, cloud, sight and
AI, the same settings, at Ghost Recon's addresses (it is an unstripped build;
every twin is named in research/code/symbols_gr.txt). What differs:

  * Indices. GR's EQUIP_PRJ.DIR has no 30 mm grenade, so FRAG.PRJ is 3 and
    SQUIRREL.PRJ 8 (every grenade in the GR savestates carries 3); the
    howitzer shell, 4, is the other projectile with no visual. GR's
    squirrel-mode cheat (gSquirrelMode) throws SQUIRREL.PRJ, so with this on
    that cheat throws smoke.

  * The reload key: SimHuman::ProcessMessage's change-magazine case
    (0x003C7654), its IsUsingItem call 0x003C765C; the key state is the
    caller's sp+0x6F and the inventory SimHuman +0x4F4; ThrownItem's vtable
    is 0x00597E60.

  * The cloud. GR's handler for TriggerGeneralEffect
    (IkeEffectsMgr::HandleTriggerGeneralEffect, 0x00249D40) is an empty stub,
    so the routine calls IkeEffectsMgr::CreateGeneralEffect (0x0024DE60) the
    way AddGeneralEffects does for a map's helper points, with the arguments
    Jungle Storm's trigger handler gives it: the general effect type
    (kGeneralEffectNames: smoke_large_type1/2/3 = 11/14/17,
    smoke_medium_type2 = 13), the name "smoke_...(45)" (CreateGeneralEffect
    parses the life out of it), the grenade's position, no rotation, no
    parent, the Room the explosion visual would have named (Scene's rooms by
    the projectile's sim room id), false, true. HandleDetonateProjectile is
    0x003925E0: the visual is message 0x196, created at 0x003928F0 with the
    projectile in s0, its ExplosionData in s1 and the position at the
    caller's sp+0x1C8; a popped grenade resumes at the removal (0x00392B7C,
    s3 = 0: no explosion alert), a held one leaves through 0x00392BE8 (the
    stack's collision record destroyed, then the epilogue).
    SimProjectile::CheckForDetonation (0x003E5000) resends the detonation
    every update past the fuse, so holding works as in Jungle Storm.

  * Sight: CheckLineOfSight 0x003F4010 (calls at 0x003F39C4, 0x003F3B00,
    0x003F3D0C, 0x003F3D80), the eye at vtable +0x324, the look-to point
    0x003F4BE0; LineOfSightClear 0x0039CD10 (frame 0xC0).

  * The AI: RunForCoverBehavior::Process 0x001BB1E0, AddElement at
    0x001BB438 (HumanAI s1, behaviour s2); FragLocationBehavior::Process's
    FragLOSBlocked 0x001B4424, IsOkToFragHereNow 0x001B449C,
    ReportGrenadeUse 0x001B44B8; the release's GetIndex 0x00398770 (thrower
    s0). GR has no players'-company static: "your squad" is the company
    IkeRulesMgr::GetPlayerCompanyIndex(player 0) answers (vtable +0xE0).

  * Data: SQUIRREL.PRJ, the kits and the five language strings files are in
    MENU.IMG as well as GR.IMG, and a mission uses the items parsed from
    MENU.IMG, so every GR data edit takes archive "" (both copies);
    STRINGS.TXT and the particle files are in GR.IMG only. The particle files
    (PARTICLE_EFFECT12/14/15/17/18.POB) and the M67 model are byte for byte
    Jungle Storm's. GR's riflemen carry no frags, so the kits are each class's
    Demolitions, Heavy Weapons and Sniper grenade kits (GR_SMOKE_KITS).

  GR caves (GR_CAVES; gr_layout packs the routines largest first): lzo /
  ptr_check library code 0x0042F180..0x0042F9CC (after grcombatmusic's
  routine) and scePad code 0x0042AC00..0x0042B018, unreferenced in the image;
  the rest are spare. Verified in the RAM interpreter on GR savestates, not
  yet played.
"""

from __future__ import annotations

import re
import struct

from .grasm import assemble

CAVES = [(0x00175678, 0x00175804), (0x00175808, 0x00175950), (0x00175D58, 0x00175E80), (0x00173908, 0x00173A68),
         (0x0018CC80, 0x0018CDDC), (0x0018CEB0, 0x0018CFBC)]   # ..0x00175F30 and ..0x00173AA4 are grfrag's

HOOK_TOGGLE, HOOK_TOGGLE_STOCK = 0x003A631C, 0x0C0CD05C   # jal IsUsingItem (slot: addiu a0, s1, 0x1b4)
HOOK_DET, HOOK_DET_STOCK = 0x0037018C, 0x0C1263F4         # jal RSGameMessage::Create (a0 = 0x1ef)
LOSC, LOSC_STOCK = 0x0037AA80, (0x27BDFF50, 0xFFBF0050)   # LineOfSightClear's first two words
CHECKLOS = 0x003D3EF0
CHECKLOS_CALLS = (0x003D3884, 0x003D39C0, 0x003D3BDC, 0x003D3C50)
CHECKLOS_STOCK = 0x0C0F4FBC                               # jal CheckLineOfSight

FRAG, SMOKE = 4, 9                                        # projectile indices (EQUIP_PRJ.DIR order)
LOOKS = ("smoke_large_type1", "smoke_large_type2", "smoke_large_type3", "round")
ROUND_EFFECT = "smoke_medium_type2"                       # the effect "round" fires; its POB is rebuilt below
DURATION = 45                                             # s, the effect's life
ON, OFF = 2.0, DURATION - 5.0                             # the cloud blocks sight between these ages
RADIUS = 5.0
INVALID = -1.0e9                                          # a ring slot's time before any cloud

SYMS = dict(
    ISUSING=0x00334170, THROWN_VT=0x005A75B0,
    CREATE=0x00498FD0, ADD_STR=0x00125750, ADD_VEC=0x0014E0E0, ADD_US=0x00133B80, ADD_INT=0x00136A20,
    SEND=0x00125810, RELEASE=0x00124AE0, CONSTS=0x00124280, UPVEC=0x00245A60, SCENE=0x00122730,
    RESUME=0x00370408, CLOCK=0x00684768, DATAMGR=0x001245F0, LOOKTO=0x003D4A50, CHECKLOS=CHECKLOS, LOSC_BODY=LOSC + 8,
    EXIT=0x00370480,
)

HOLD_SLOTS = 2                                            # grenades whose landing is waited on at once
                                                          # (a third pops where it is, as it did before)
HOLD_EPS = 0.03                                           # m per frame under which it counts as stopped
HOLD_MAX = 5.0                                            # s to wait for it to stop before popping anyway
HOLD_STALE = 1.0                                          # s without a frame after which a slot is another grenade's


def _hi(f):
    return struct.unpack("<I", struct.pack("<f", f))[0] >> 16


def _bits(f):
    return struct.unpack("<I", struct.pack("<f", f))[0]


assert _bits(ON) & 0xFFFF == 0 and _bits(OFF) & 0xFFFF == 0 and _bits(RADIUS * RADIUS) & 0xFFFF == 0

# ---- the reload key: frag <-> smoke ------------------------------------------------------------
# called for jal IsUsingItem in the change-magazine case: a0 = SimHumanState, s1 = SimHuman,
# the caller's sp+0x7f = the key's state (1 pressed). v0 = 1 ends the case there.
SRC_TOGGLE = """
smk_toggle:
    addiu sp, sp, -0x20
    sd    ra, 0x10(sp)
    jal   ISUSING
    nop
    bnez  v0, st_out                ; busy: as before
    lbu   t0, 0x9f(sp)              ; (delay) pressed (the caller's sp+0x7f)
    beqz  t0, st_zero
    nop
    lw    t9, 0x514(s1)             ; inventory
    lb    a1, 0x1e7(s1)             ; current slot
    lw    t9, 0x2c(t9)
    jalr  t9
    addiu a0, s1, 0x514
    beqz  v0, st_zero
    lui   t0, %hi(THROWN_VT)
    addiu t0, t0, %lo(THROWN_VT)
    lw    t1, 0(v0)
    bne   t1, t0, st_zero           ; not a thrown item
    lhu   t1, 8(v0)                 ; (delay) its projectile
    li    t2, {FRAG}
    beq   t1, t2, st_set
    li    t3, {SMOKE}               ; (delay) frag -> smoke
    bne   t1, t3, st_zero
    move  t3, t2                    ; (delay) smoke -> frag
st_set:
    sh    t3, 8(v0)
    b     st_out
    li    v0, 1                     ; the press is used up
st_zero:
    move  v0, zero
st_out:
    ld    ra, 0x10(sp)
    jr    ra
    addiu sp, sp, 0x20
"""

# ---- the detonation --------------------------------------------------------------------------
# called for jal Create(0x1ef) in HandleDetonateProjectile: s3 = ExplosionData (+8 visual type),
# the caller's sp+0x248 = where it went off.
SRC_DET = """
smk_det:
    lw    t0, 8(s3)
    bnez  t0, sd_create             ; a real explosion
    nop
    addiu sp, sp, -0x60
    sd    ra, 0x50(sp)
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s2, 0x20(sp)
    jal   DATAMGR
    nop
    lw    t9, 0(v0)
    lw    t9, 0x48(t9)              ; IkeDataMgr::GetProjectileData
    move  a0, v0
    jalr  t9
    li    a1, {SMOKE}
    addiu v0, v0, 0x4c              ; the smoke grenade's ExplosionData
    bne   v0, s3, sd_other          ; another projectile with no visual (the howitzer shell)
    addiu s0, sp, 0x2a8             ; (delay) the caller's sp+0x248, where the grenade is now
    move  a0, s0
    jal   smk_hold                  ; has it stopped moving?
    move  a1, s4                    ; (delay) the SimProjectile
    beqz  v0, sd_hold               ; no: let it fly on, the fuse asks again next frame
    nop
    jal   SCENE
    nop
    lwc1  $f0, 0(s0)
    swc1  $f0, 0x30(sp)
    lwc1  $f0, 4(s0)
    swc1  $f0, 0x34(sp)
    lwc1  $f0, 8(s0)
    lui   t0, 0x3f80
    mtc1  t0, $f1
    add.s $f0, $f0, $f1
    swc1  $f0, 0x38(sp)             ; a metre up
    lw    t9, 0(v0)
    lw    t9, 0x28(t9)              ; the room there
    move  a0, v0
    jalr  t9
    addiu a1, sp, 0x30
    andi  s1, v0, 0xffff
    ori   t0, zero, 0xffff
    beq   s1, t0, sd_done           ; no room: no effect, no cloud
    nop
    jal   CREATE
    li    a0, 0x1fb                 ; TriggerGeneralEffect
    move  s2, v0
    lui   a1, %hi(smk_name)
    addiu a1, a1, %lo(smk_name)
    jal   ADD_STR
    move  a0, s2
    move  a1, s0
    jal   ADD_VEC                   ; where
    move  a0, s2
    jal   CONSTS
    nop
    jal   UPVEC
    move  a0, v0
    move  a1, v0
    jal   ADD_VEC                   ; up
    move  a0, s2
    move  a1, s1
    jal   ADD_US                    ; room
    move  a0, s2
    li    a1, -1
    jal   ADD_INT                   ; no handle kept
    move  a0, s2
    li    a0, 1
    move  a1, s2
    jal   SEND
    move  a2, zero
    jal   RELEASE
    move  a0, s2
sd_ring:
    b     smk_note
    nop
"""

SRC_DET2 = """
smk_note:                           ; the ring entry: x, y, z + 1.5, now
    lui   t0, %hi(CLOCK)
    lw    t0, %lo(CLOCK)(t0)
    beqz  t0, sd_done
    nop
    lwc1  $f0, 0xd4(t0)             ; now
    lui   t1, %hi(smk_next)
    lw    t2, %lo(smk_next)(t1)
    andi  t2, t2, 7
    addiu t3, t2, 1
    sw    t3, %lo(smk_next)(t1)
    sll   t2, t2, 4
    lui   t4, %hi(smk_ring)
    addiu t4, t4, %lo(smk_ring)
    addu  t4, t4, t2
    lwc1  $f1, 0(s0)
    swc1  $f1, 0(t4)
    lwc1  $f1, 4(s0)
    swc1  $f1, 4(t4)
    lwc1  $f1, 8(s0)
    lui   t5, 0x3fc0                ; 1.5 m
    mtc1  t5, $f2
    add.s $f1, $f1, $f2
    swc1  $f1, 8(t4)
    swc1  $f0, 12(t4)
    lui   t5, {OFF_HI}
    mtc1  t5, $f2
    add.s $f2, $f0, $f2             ; it stops blocking then
    lui   t1, %hi(smk_until)
    lwc1  $f1, %lo(smk_until)(t1)
    c.lt.s $f1, $f2
    bc1f  sd_done
    nop
    swc1  $f2, %lo(smk_until)(t1)
sd_done:
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    ld    ra, 0x50(sp)
    addiu sp, sp, 0x60
    move  s2, zero                  ; no explosion alert
    lui   ra, %hi(RESUME)
    addiu ra, ra, %lo(RESUME)       ; on to removing the projectile
    jr    ra
    nop
sd_hold:                            ; still in the air or rolling: handle nothing, keep the grenade
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    ld    ra, 0x50(sp)
    addiu sp, sp, 0x60
    j     EXIT                      ; HandleDetonateProjectile's own epilogue
    nop
sd_create:
    j     CREATE
    nop
"""

# ---- the cloud waits for the grenade to land -------------------------------------------------
# SimProjectile::CheckForDetonation (JS 0x003C49C0) keeps NO "already detonated" flag: while the
# fuse is past and the projectile is alive it sends message 0x201 again every frame. So a smoke
# grenade that goes off in the air can simply be left alone -- it keeps bouncing, the detonation is
# offered again next frame, and the cloud pops when it comes to rest. Rest is measured from the
# position the handler is about to explode at (its own sp+0x248, read from the projectile's live
# state), because consecutive frames give consecutive positions; that needs no struct offsets.
SRC_HOLD = """
smk_hold:                           ; a0 = &position, a1 = SimProjectile
                                    ; v0 = 1: pop the cloud here.  0: hold, it is still moving
    lui   t0, %hi(CLOCK)
    lw    t0, %lo(CLOCK)(t0)
    beqz  t0, sh_pop                ; no clock: never hold
    nop
    lwc1  $f0, 0xd4(t0)             ; now
    lui   t1, %hi(smk_slots)
    addiu t1, t1, %lo(smk_slots)
    li    t2, {SLOTS}
    move  t3, zero                  ; the first free slot passed
sh_find:
    lw    t4, 0(t1)
    beq   t4, a1, sh_seen
    nop
    bnez  t4, sh_next
    nop
    bnez  t3, sh_next
    nop
    move  t3, t1
sh_next:
    addiu t2, t2, -1
    bnez  t2, sh_find
    addiu t1, t1, 24
    beqz  t3, sh_pop                ; every slot taken: this one pops where it is
    nop
    move  t1, t3
    sw    a1, 0(t1)                 ; first sight of this grenade
    b     sh_reset
    nop
sh_seen:
    lwc1  $f2, 20(t1)
    sub.s $f2, $f0, $f2             ; since the last frame
    mtc1  zero, $f3
    c.lt.s $f2, $f3
    bc1t  sh_reset                  ; the clock went back: a load
    lui   t5, {STALE_HI}
    mtc1  t5, $f3
    c.lt.s $f3, $f2
    bc1t  sh_reset                  ; a gap: another grenade at the same address
    nop
    lwc1  $f2, 16(t1)
    sub.s $f2, $f0, $f2             ; how long it has been held
    lui   t5, {MAXW_HI}
    mtc1  t5, $f3
    c.lt.s $f3, $f2
    bc1t  sh_free                   ; long enough: pop wherever it is
    nop
    lwc1  $f4, 0(a0)
    lwc1  $f5, 4(t1)
    sub.s $f4, $f4, $f5
    mul.s $f6, $f4, $f4
    lwc1  $f4, 4(a0)
    lwc1  $f5, 8(t1)
    sub.s $f4, $f4, $f5
    mul.s $f4, $f4, $f4
    add.s $f6, $f6, $f4
    lwc1  $f4, 8(a0)
    lwc1  $f5, 12(t1)
    sub.s $f4, $f4, $f5
    mul.s $f4, $f4, $f4
    add.s $f6, $f6, $f4             ; how far it moved, squared
    lui   t5, {EPS2_HI}
    ori   t5, t5, {EPS2_LO}
    mtc1  t5, $f3
    c.lt.s $f6, $f3
    bc1t  sh_free                   ; it has stopped: the cloud pops here
    nop
    b     sh_keep
    nop
sh_reset:
    swc1  $f0, 16(t1)               ; the hold starts now
sh_keep:
    lwc1  $f1, 0(a0)
    swc1  $f1, 4(t1)
    lwc1  $f1, 4(a0)
    swc1  $f1, 8(t1)
    lwc1  $f1, 8(a0)
    swc1  $f1, 12(t1)
    b     sh_hold
    swc1  $f0, 20(t1)
sh_free:
    sw    zero, 0(t1)
sh_pop:
    jr    ra
    li    v0, 1
sh_hold:
    jr    ra
    move  v0, zero
"""

SRC_SLOTS = """
smk_slots:                          ; {SLOTS} x {{projectile, x, y, z, held since, last seen}}
{SLOTDATA}
"""

# ---- is a live cloud across this sight line --------------------------------------------------
# a0 = &eye, a1 = &target -> v0 = 1 when blocked. Leaf; f0-f17, t0-t5.
SRC_BLOCKED = """
smk_blocked:
    lui   t0, %hi(CLOCK)
    lw    t0, %lo(CLOCK)(t0)
    beqz  t0, sb_no
    nop
    lwc1  $f0, 0xd4(t0)             ; now
    lui   t1, %hi(smk_last)
    lwc1  $f1, %lo(smk_last)(t1)
    swc1  $f0, %lo(smk_last)(t1)
    lui   t2, 0x3f80
    mtc1  t2, $f2
    sub.s $f1, $f1, $f2
    c.lt.s $f0, $f1                 ; the clock went back a second or more: a load
    bc1f  sb_scan
    lui   t3, %hi(smk_ring)
    addiu t3, t3, %lo(smk_ring)
    li    t4, 8
    lui   t5, {INV_HI}
    ori   t5, t5, {INV_LO}
sb_clr:
    sw    t5, 12(t3)
    addiu t4, t4, -1
    bnez  t4, sb_clr
    addiu t3, t3, 16
    lui   t1, %hi(smk_until)
    b     sb_no
    sw    zero, %lo(smk_until)(t1)
sb_scan:
    lwc1  $f3, 0(a1)
    lwc1  $f7, 0(a0)
    sub.s $f3, $f3, $f7             ; d = target - eye
    lwc1  $f4, 4(a1)
    lwc1  $f7, 4(a0)
    sub.s $f4, $f4, $f7
    lwc1  $f5, 8(a1)
    lwc1  $f7, 8(a0)
    sub.s $f5, $f5, $f7
    mul.s $f6, $f3, $f3
    mul.s $f7, $f4, $f4
    add.s $f6, $f6, $f7
    mul.s $f7, $f5, $f5
    add.s $f6, $f6, $f7             ; dd
    addiu t3, t3, %lo(smk_ring)     ; t3 already holds %hi(smk_ring)
    li    t4, 8
sb_loop:
    lwc1  $f8, 12(t3)
    sub.s $f8, $f0, $f8             ; its age
    lui   t5, {ON_HI}
    mtc1  t5, $f9
    c.lt.s $f8, $f9
    bc1t  sb_next                   ; not yet thick
    lui   t5, {OFF_HI}
    mtc1  t5, $f9
    c.lt.s $f8, $f9
    bc1f  sb_next                   ; thinning out, or never was
    nop
    lwc1  $f9, 0(a0)
    lwc1  $f7, 0(t3)
    sub.s $f9, $f9, $f7             ; f = eye - centre
    lwc1  $f10, 4(a0)
    lwc1  $f7, 4(t3)
    sub.s $f10, $f10, $f7
    lwc1  $f11, 8(a0)
    lwc1  $f7, 8(t3)
    b     smk_seg
    sub.s $f11, $f11, $f7
sb_next:
    addiu t4, t4, -1
    bnez  t4, sb_loop
    addiu t3, t3, 16
sb_no:
    jr    ra
    move  v0, zero
"""

SRC_BLOCKED2 = """
smk_seg:                            ; the closest point of the segment to the centre
    mul.s $f12, $f9, $f3
    mul.s $f7, $f10, $f4
    add.s $f12, $f12, $f7
    mul.s $f7, $f11, $f5
    add.s $f12, $f12, $f7           ; f.d
    mtc1  zero, $f13                ; t = 0
    c.lt.s $f12, $f13
    bc1f  sg_close                  ; the centre is behind the eye
    nop
    neg.s $f13, $f12
    c.lt.s $f13, $f6
    bc1t  sg_div
    lui   t5, 0x3f80
    b     sg_close
    mtc1  t5, $f13                  ; beyond the target: t = 1
sg_div:
    div.s $f13, $f13, $f6
sg_close:
    mul.s $f14, $f13, $f3
    add.s $f14, $f14, $f9
    mul.s $f15, $f13, $f4
    add.s $f15, $f15, $f10
    mul.s $f16, $f13, $f5
    add.s $f16, $f16, $f11
    mul.s $f17, $f14, $f14
    mul.s $f7, $f15, $f15
    add.s $f17, $f17, $f7
    mul.s $f7, $f16, $f16
    add.s $f17, $f17, $f7
    lui   t5, {R2_HI}
    mtc1  t5, $f7
    c.lt.s $f17, $f7
    bc1f  sb_next
    nop
    jr    ra
    li    v0, 1
"""

# ---- the two sight tests ---------------------------------------------------------------------
SRC_LOS = """
smk_los:                            ; CheckLineOfSight(a0 mgr, a1 looker, a2 target, a3, t0)
    lui   t9, %hi(CLOCK)
    lw    t9, %lo(CLOCK)(t9)
    beqz  t9, sl_go
    lui   at, %hi(smk_until)
    lwc1  $f0, 0xd4(t9)
    lwc1  $f1, %lo(smk_until)(at)
    c.lt.s $f0, $f1
    bc1f  sl_go                     ; no cloud alive
    nop
    addiu sp, sp, -0x50
    sd    ra, 0x40(sp)
    sw    a0, 0x00(sp)
    sw    a1, 0x04(sp)
    sw    a2, 0x08(sp)
    sw    a3, 0x0c(sp)
    sw    t0, 0x10(sp)
    lw    t9, 0(a1)
    lw    t9, 0x328(t9)             ; his eye
    jalr  t9
    move  a0, a1
    lwc1  $f0, 0(v0)
    swc1  $f0, 0x20(sp)
    lwc1  $f0, 4(v0)
    swc1  $f0, 0x24(sp)
    lwc1  $f0, 8(v0)
    swc1  $f0, 0x28(sp)
    jal   LOOKTO                    ; the point he looks for
    lw    a0, 0x08(sp)
    move  a1, v0
    jal   smk_blocked
    addiu a0, sp, 0x20
    lw    a0, 0x00(sp)
    lw    a1, 0x04(sp)
    lw    a2, 0x08(sp)
    lw    a3, 0x0c(sp)
    lw    t0, 0x10(sp)
    ld    ra, 0x40(sp)
    bnez  v0, sl_out                ; smoke between them: nothing seen this time
    addiu sp, sp, 0x50
sl_go:
    j     CHECKLOS
    nop
sl_out:
    jr    ra
    nop
"""

SRC_CLEAR = """
smk_clear:                          ; LineOfSightClear(a0 mgr, a1 controller, a2 &target, f12)
    lui   t9, %hi(CLOCK)
    lw    t9, %lo(CLOCK)(t9)
    beqz  t9, sc_go
    lui   at, %hi(smk_until)
    lwc1  $f0, 0xd4(t9)
    lwc1  $f1, %lo(smk_until)(at)
    c.lt.s $f0, $f1
    bc1f  sc_go
    nop
    addiu sp, sp, -0x50
    sd    ra, 0x40(sp)
    sw    a0, 0x00(sp)
    sw    a1, 0x04(sp)
    sw    a2, 0x08(sp)
    swc1  $f12, 0x0c(sp)
    lw    t9, 0(a1)
    lw    t9, 0x328(t9)             ; his eye
    jalr  t9
    move  a0, a1
    lwc1  $f0, 0(v0)
    swc1  $f0, 0x20(sp)
    lwc1  $f0, 4(v0)
    swc1  $f0, 0x24(sp)
    lwc1  $f0, 8(v0)
    swc1  $f0, 0x28(sp)
    lw    a1, 0x08(sp)
    jal   smk_blocked
    addiu a0, sp, 0x20
    lw    a0, 0x00(sp)
    lw    a1, 0x04(sp)
    lw    a2, 0x08(sp)
    lwc1  $f12, 0x0c(sp)
    ld    ra, 0x40(sp)
    bnez  v0, sc_no
    addiu sp, sp, 0x50
sc_go:
    addiu sp, sp, -0xb0             ; LineOfSightClear's own first two words
    j     LOSC_BODY
    sd    ra, 80(sp)
sc_no:
    jr    ra
    move  v0, zero
"""

SRC_OTHER = """
sd_other:                           ; not the smoke grenade: Create(0x1ef) as before
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    ld    ra, 0x50(sp)
    addiu sp, sp, 0x60
    j     CREATE
    li    a0, 0x1ef
"""

SRC_DATA = """
smk_ring:
{RING}
smk_next:
    .word 0
smk_until:
    .word 0
smk_last:
    .word 0
smk_name:
    .asciiz "{NAME}"
"""

_CAVE_STOCK_HEX = {
    0x0018CC80: (
        "27BDFF70 3C020062 FFB60070 FFB40050 2456C500 FFB30040 0080A02D FFB20030"
        "00A0982D FFB00010 00E0902D FFBF0080 FFB50060 FFB10020 8EC20024 14400003"
        "00C0802D 1000003B 2402FF9C 3C150057 0C05E8CC 8EA46634 04400036 2402FF38"
        "12000006 00000000 82020000 10400003 00000000 16400005 3C020062 0C05E8C0"
        "8EA46634 1000002B 2402FF2E 24030010 2451C5B0 AC54C5B0 0200282D AE330004"
        "AE230008 26240014 0C05B8F2 240603FF 3C100062 0240282D 2610C560 A2200413"
        "0200202D 0C05B8F2 24060020 2610FFE0 0000202D AE300010 0C05E958 A200003F"
        "3C090062 3C0B0019 02C0202D 0220382D 2529DAC0 256BBA10 AFA00000 2405000E"
        "24060001 24080414 0C05F5AA 240A0004 0040802D 16000004 3C030057 24020013"
        "10000003 AC626630 0C05E8C0 8EA46634 0200102D DFBF0080 DFB60070 DFB50060"
        "DFB40050 DFB30040 DFB20030 DFB10020 DFB00010 03E00008 27BD0090"),
    0x0018CEB0: (
        "27BDFF90 3C020062 FFB40050 FFB30040 2454C500 FFB10020 0080982D FFB00010"
        "00A0882D FFBF0060 FFB20030 8E820024 14400003 00C0802D 1000002C 2402FF9C"
        "3C120057 0C05E8CC 8E446634 04400027 2402FF38 12000004 00000000 82020000"
        "14400005 3C020062 0C05E8C0 8E446634 1000001E 2402FF2E 0200282D 2450C5B0"
        "AC53C5B0 AE110004 26040014 0C05B8F2 240603FF A2000413 3C090062 3C0B0019"
        "0200382D 0280202D 2529DAC0 256BBA10 24050012 AFA00000 24060001 24080414"
        "0C05F5AA 240A0004 0040802D 16000004 3C030057 24020012 10000003 AC626630"
        "0C05E8C0 8E446634 0200102D DFBF0060 DFB40050 DFB30040 DFB20030 DFB10020"
        "DFB00010 03E00008 27BD0070"),
    0x00175678: (
        "27BDFED0 FFB200B0 FFBF0120 0080902D FFBE0110 FFB70100 FFB600F0 FFB500E0"
        "FFB400D0 FFB300C0 FFB100A0 0C05D4FE FFB00090 14400049 0000102D 27A20050"
        "0000882D AFA20084 27B40010 27A20060 27B50020 AFA20080 27B60030 27B70040"
        "27BE0070 2653021C 0240802D 00000000 26250400 03A0202D 30A5FFFF 0C05D51A"
        "26310001 7BA20000 2E230020 7E020000 1460FFF7 26100010 03A0202D 0C05D51A"
        "24050430 0260802D 8FA20000 0280202D 24050431 0000882D 0C05D51A AE420200"
        "8FA20010 02A0202D 24050432 0C05D51A AE420204 8FA20020 02C0202D 24050434"
        "0C05D51A AE420208 8FA20030 02E0202D 24050435 0C05D51A AE42020C 8FA20040"
        "24050436 8FA40084 0C05D51A AE420210 8FA20050 24050437 8FA40080 0C05D51A"
        "AE420214 8FA20060 AE420218 00000000 26250420 03C0202D 30A5FFFF 0C05D51A"
        "26310001 97A20070 2E230010 A6020000 1460FFF7 26100002 24020001 DFBF0120"
        "DFBE0110 DFB70100 DFB600F0 DFB500E0 DFB400D0 DFB300C0 DFB200B0 DFB100A0"
        "DFB00090 03E00008 27BD0130"),
    0x00175808: (
        "27BDFFA0 FFB20030 FFBF0050 0080902D FFB30040 FFB10020 0C05D4FE FFB00010"
        "14400042 0000102D 0000882D 2653021C 0240802D 00000000 7A020000 26240400"
        "3084FFFF 03A0282D 7FA20000 0C05D50A 26310001 2E220020 1440FFF7 26100010"
        "9E420200 70001CA9 7FA30000 24040430 03A0282D 0C05D50A FFA20000 0260802D"
        "9E420204 24040431 03A0282D 0000882D 0C05D50A FFA20000 9E420208 24040432"
        "03A0282D 0C05D50A FFA20000 9E42020C 24040434 03A0282D 0C05D50A FFA20000"
        "9E420210 24040435 03A0282D 0C05D50A FFA20000 9E420214 24040436 03A0282D"
        "0C05D50A FFA20000 9E420218 24040437 03A0282D 0C05D50A FFA20000 00000000"
        "96020000 26240420 3084FFFF 03A0282D FFA20000 0C05D50A 26310001 2E220010"
        "1440FFF7 26100002 24020001 DFBF0050 DFB30040 DFB20030 DFB10020 DFB00010"
        "03E00008 27BD0060"),
    0x00175D58: (
        "27BDFF70 3C021000 FFB60060 34423C40 FFBF0080 0080B02D FFB50050 FFB40040"
        "FFB30030 FFB20020 FFB10010 FFB00000 FFB70070 0C05D742 8C570000 2C420002"
        "14400003 3C021000 10000058 0000102D 3C031000 34423D00 34633D10 8C450000"
        "3C041000 34843D20 3C061000 AEC50000 34C63D30 3C051000 3C071000 8C620000"
        "34A53D40 34E73D50 3C0C1000 AEC20004 358C3D60 3C131000 3C141000 8C820000"
        "36733D70 36943C70 3C111000 AEC20008 36313C80 3C101000 3C121000 8CC20000"
        "36103C00 36523CD0 3C061000 AEC2000C 34C63C90 3C081000 3C0E1000 8CA20000"
        "35083CA0 35CE3CB0 3C0B1000 AEC20010 356B3CE0 3C091000 3C0F1000 8CE20000"
        "35293CC0 35EF3C30 3C0D1000 AEC20014 35AD3C60 3C0A1000 0017AA02 8D830000"
        "354A3C20 3C0C1000 24020001 AEC30018 358C3C50 8E630000 AEC3001C 8E840000"
        "AEC40020 8E230000 AEC30024 8E040000 AEC40028 8E430000 8CC40000 8D050000"
        "8DC60000 8D670000 8D280000 A6C3002C A6C4002E A6C50030 A6C60032 A6C70034"
        "A6C80036 8DE40000 8DA50000 8D430000 A2D5003E A2C3003C A2D7003D A6C40038"
        "8D830000 A6C5003A A2C3003F DFBF0080 DFB70070 DFB60060 DFB50050 DFB40040"
        "DFB30030 DFB20020 DFB10010 DFB00000 03E00008 27BD0090"),
    0x00173908: (   # a thread body and, at 0x00173A38, the routine that would start it: never called
        "27BDFF60 FFBE0080 FFB70070 3C1E0061 FFB60060 3C170057 FFB50050 3C160058"
        "FFB40040 3C150061 FFB30030 3C140057 FFB20020 3C130057 FFB10010 3C120061"
        "FFBF0090 3C110057 FFB00000 3C020057 0C05E8C8 8C4492A0 8E8392D8 2402FFFF"
        "14620008 8EE29290 AE6092B4 3C020057 AE8092D8 AC409294 0C05E848 AFC043D4"
        "8EE29290 18400004 26C40600 8E4543C0 0C05F142 8E2692DC 8E4343C0 10600009"
        "00000000 8E2292DC 10400006 00000000 0380802D 8EBC43C4 0060F809 8E2492DC"
        "0200E02D AE6092B4 1000FFE1 3C020057 27BDFFA0 FFB40040 FFB10010 3C140057"
        "0080882D FFB30030 FFB20020 24130001 FFB00000 00A0902D 8E849294 00C0802D"
        "1480001A FFBF0050 0C05E874 00000000 3C030061 3C050061 AC6243D8 0040202D"
        "0C05E878 24A543E0 3C030061 3C020017 24634410 24423908 AC70000C 0060202D"
        "AC620004 AC720008 AC710014 0C05E838 AC600010 0000282D AE829294 0C05E840"
        "0040202D 10000005 0260102D 0220282D 0C05E85C 0000982D 0260102D DFBF0050"
        "DFB40040 DFB30030 DFB20020 DFB10010 DFB00000 03E00008 27BD0060"),
}


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


JS_STOCK = {}
for _b, _h in _CAVE_STOCK_HEX.items():
    JS_STOCK.update(_stock_words(_b, _h))
JS_STOCK[HOOK_TOGGLE] = HOOK_TOGGLE_STOCK
JS_STOCK[HOOK_DET] = HOOK_DET_STOCK
JS_STOCK[LOSC], JS_STOCK[LOSC + 4] = LOSC_STOCK
for _va in CHECKLOS_CALLS:
    JS_STOCK[_va] = CHECKLOS_STOCK


def _sources(look: str):
    if look not in LOOKS:
        raise ValueError("smoke look %r" % look)
    k = dict(FRAG=FRAG, SMOKE=SMOKE, OFF_HI=hex(_hi(OFF)), ON_HI=hex(_hi(ON)), R2_HI=hex(_hi(RADIUS * RADIUS)),
             INV_HI=hex(_bits(INVALID) >> 16), INV_LO=hex(_bits(INVALID) & 0xFFFF),
             SLOTS=HOLD_SLOTS, STALE_HI=hex(_hi(HOLD_STALE)), MAXW_HI=hex(_hi(HOLD_MAX)),
             EPS2_HI=hex(_bits(HOLD_EPS * HOLD_EPS) >> 16), EPS2_LO=hex(_bits(HOLD_EPS * HOLD_EPS) & 0xFFFF),
             SLOTDATA="\n".join("    .word 0" for _ in range(6 * HOLD_SLOTS)))
    assert _bits(HOLD_STALE) & 0xFFFF == 0 and _bits(HOLD_MAX) & 0xFFFF == 0
    ring = "\n".join("    .word 0\n    .word 0\n    .word 0\n    .word %#x" % _bits(INVALID) for _ in range(8))
    effect = ROUND_EFFECT if look == "round" else look
    data = SRC_DATA.replace("{RING}", ring).replace("{NAME}", "%s(%d)" % (effect, DURATION))
    return [
        (0, SRC_BLOCKED.format(**k) + SRC_TOGGLE.format(**k)),
        (1, SRC_BLOCKED2.format(**k) + SRC_LOS),
        (2, SRC_DET.format(**k)),
        (3, SRC_CLEAR + SRC_OTHER + data),
        (4, SRC_HOLD.format(**k)),
        (5, SRC_DET2.format(**k) + SRC_SLOTS.format(**k)),
    ]


def _labels_of(src):
    return {m.group(1) for m in re.finditer(r"^(\w+):", src, re.M)}


def assemble_all(look: str = LOOKS[2]):
    """{cave base: words}, labels."""
    pieces = _sources(look)
    names = set().union(*(_labels_of(s) for _i, s in pieces))
    labels = {n: CAVES[0][0] for n in names}            # first-pass stand-ins
    for _ in range(3):
        words, new = {}, {}
        for i, src in pieces:
            base = CAVES[i][0]
            local = _labels_of(src)
            w, l = assemble(src, base, dict(SYMS, **{k: v for k, v in labels.items() if k not in local}))
            words[base] = w
            new.update(l)
        if new == labels:
            break
        labels = new
    for i, (base, end) in enumerate(CAVES):
        n = len(words.get(base, []))
        if base + 4 * n > end:
            raise ValueError("smoke routine outgrows cave %d at %#x (%d words, room %d)"
                             % (i, base, n, (end - base) // 4))
    return words, labels


def edits(look: str = LOOKS[2]):
    """(va, value, stock, note)."""
    words, l = assemble_all(look)
    out = []
    for base, w in words.items():
        out += [(base + 4 * i, x, JS_STOCK[base + 4 * i], "smoke grenades: routines") for i, x in enumerate(w)]
    j = lambda op, target, at: assemble("%s %#x" % (op, target), at)[0][0]  # noqa: E731
    out.append((HOOK_TOGGLE, j("jal", l["smk_toggle"], HOOK_TOGGLE), HOOK_TOGGLE_STOCK,
                "smoke grenades: reload with grenades in hand switches frag / smoke"))
    out.append((HOOK_DET, j("jal", l["smk_det"], HOOK_DET), HOOK_DET_STOCK,
                "smoke grenades: a smoke projectile pops a cloud, no blast"))
    out.append((LOSC, j("j", l["smk_clear"], LOSC), LOSC_STOCK[0],
                "smoke grenades: LineOfSightClear through a cloud is no"))
    out.append((LOSC + 4, 0, LOSC_STOCK[1], "smoke grenades: LineOfSightClear (slot)"))
    for va in CHECKLOS_CALLS:
        out.append((va, j("jal", l["smk_los"], va), CHECKLOS_STOCK,
                    "smoke grenades: no spotting through a cloud"))
    return out


def js_edits(v: dict):
    if not v.get("js_smoke"):
        return []
    return edits(v.get("js_smoke_look", "round")) + ai_edits(v.get("js_smoke_ai", "all"),
                                                          v.get("js_smoke_ai_chance", "2"))


# ---- the AI pops smoke when it runs for cover -------------------------------------------------
# RunForCoverBehavior::Process (JS 0x001B76E0; vtable 0x005A37E0 = GR's + 0xF640) finds a cover point and,
# the first time (+0x3A), pushes a LocationBehavior to it: AddElement at 0x001B7914 (s2 = the HumanAI,
# s3 = the behaviour, threat position +0x18; s0/s1/s4/s5 are only restored after, by its epilogue). The
# routine pushes the move as before and then, maybe, a FragLocationBehavior on top -- he throws first,
# then runs. The throw is made smoke at its release: IkeSimulationMgr's ControllerThrewItem handler reads
# the item's projectile at 0x00376470 (thrower SimHuman in s2) and a marked soldier's frag leaves as smoke;
# FragLocationBehavior's "no friendly near the blast" check at the throw (IsOkToFragHereNow, 0x001B0A44,
# a3 = the HumanAI) is answered yes for a marked soldier -- smoke has no blast -- and so is its arc check
# (HumanAI::FragLOSBlocked at 0x001B09D0: a branch within the first metres cancelled the first smoke seen
# in play). A mark lasts 10 s. The queue leaves the team's grenade clock alone (the throw sets it, through
# ReportGrenadeUse, as a frag's does): stamping it at the queue blocked that team's frags for 30 s even when
# the throw never came. Instead a gate (0x00175AF0): 15 s between AI smokes anywhere, none while 2 clouds
# are alive -- a large cloud is heavy on the frame rate.

CAVES_AI = [(0x00197F00, 0x001980A0), (0x0018CAB0, 0x0018CC7C), (0x00175AF0, 0x00175BA8),
            (0x00197C08, 0x00197C30)]          # 0x00197C30..0x00197CF4 is grfrag's
HOOK_RFC, HOOK_RFC_STOCK = 0x001B7914, 0x0C06DB84   # jal RSScript::AddElement (slot: move a1, s0)
HOOK_OK, HOOK_OK_STOCK = 0x001B0A44, 0x0C0F829C     # jal IsOkToFragHereNow (slot: move a3, s2)
HOOK_IDX, HOOK_IDX_STOCK = 0x00376470, 0x0C08AF38   # jal InventoryItem::GetIndex (slot: move a0, s1)
HOOK_ARC, HOOK_ARC_STOCK = 0x001B09D0, 0x0C0FA55C   # jal HumanAI::FragLOSBlocked (slot: swc1 f0, 0x58(sp))
AI_GAP = 15.0                                       # s between two AI smokes, anywhere
AI_MAX_CLOUDS = 2                                   # no AI smoke while this many clouds are alive
HOOK_REP, HOOK_REP_STOCK = 0x001B0A60, 0x0C0F83EC   # jal HumanAI::ReportGrenadeUse (slot: move a1, s2)
AI_CHANCES = {"4": 0x3E80, "3": 0x3EAB, "2": 0x3F00, "1": 0x3F81}   # js_smoke_ai_chance: 1 in N per run for
                                                                    # cover (0x3F81, just over 1: every time)
AI_SIDES = ("off", "squad", "enemies", "all")

AI_SYMS = dict(
    ADDELEM=0x001B6E10, ISOK=0x003E0A70, GETNUMGREN=0x003EA060, HASLAUNCHER=0x003EA140,
    REPORTGREN=0x003E0FB0, FRAGCTOR=0x001B0720, NEW=0x00103470, RANDOMFLOAT=0x001129C0, RNG=0x00613510,
    CLOCK=0x00684768, SQUAD_CO=0x0057A1C8, LOSBLOCKED=0x003E9570,
)

SRC_RFC = """
rfc_smoke:                          ; AddElement(a0 script, a1 the move) in RunForCover
    addiu sp, sp, -0x40
    sd    ra, 0x30(sp)
    jal   ADDELEM                   ; the move, as before
    nop
    lw    s0, 0x14(s2)              ; his SimHuman
    beqz  s0, rs_out
    nop
    lw    t0, 0x178(s0)             ; his company
    lui   at, %hi(SQUAD_CO)
    lw    t1, %lo(SQUAD_CO)(at)
    xor   t0, t0, t1                ; 0: the players' squad
{SIDE}
    lbu   t0, 0x132(s2)             ; carries grenades at all
    beqz  t0, rs_out
    lw    s1, 0xa4(s2)              ; (delay) his fireteam
    beqz  s1, rs_out
    lui   t0, %hi(CLOCK)
    lw    t0, %lo(CLOCK)(t0)
    beqz  t0, rs_out
    nop
    lwc1  $f0, 0xd4(t0)             ; now
    lwc1  $f1, 0xec(s1)             ; the team's last grenade
    sub.s $f1, $f0, $f1
    lui   t1, 0x41f0                ; 30 s, the game's own wait
    mtc1  t1, $f2
    c.lt.s $f1, $f2
    bc1t  rs_out
    nop
    jal   smk_gate                  ; 15 s since the last AI smoke, fewer than 2 clouds alive
    nop
    beqz  v0, rs_out
    nop
    jal   GETNUMGREN
    move  a0, s2
    blez  v0, rs_out
    nop
    jal   HASLAUNCHER               ; a launcher would fire, not throw
    move  a0, s2
    andi  v0, v0, 0xff
    bnez  v0, rs_out
    lui   a0, %hi(RNG)
    addiu a0, a0, %lo(RNG)
    move  a1, zero
    move  a2, zero
    mtc1  zero, $f12
    lui   v0, 0x3f80
    jal   RANDOMFLOAT               ; 0..1
    mtc1  v0, $f13
    lui   v0, {CHANCE}
    mtc1  v0, $f1
    nop
    c.lt.s $f0, $f1
    bc1f  rs_out
    nop
    b     rs_geo
    nop
rs_out:
    ld    ra, 0x30(sp)
    jr    ra
    addiu sp, sp, 0x40

smk_ok:                             ; IsOkToFragHereNow(a0 team, a1 &aim, a2 level, a3 HumanAI) at the throw
    lw    t8, 0x14(a3)
    move  t9, ra
    jal   smk_find
    nop
    move  ra, t9
    beqz  v0, so_ask
    nop
    jr    ra
    li    v0, 1                     ; smoke: no blast to keep friends from
so_ask:
    j     ISOK
    nop

smk_arc:                            ; FragLOSBlocked(a0 HumanAI, a1 &point, f12 reach) before the throw
    lw    t8, 0x14(a0)
    move  t9, ra
    jal   smk_find
    nop
    move  ra, t9
    beqz  v0, sa_ask
    nop
    jr    ra
    move  v0, zero                  ; smoke: a branch in the way does not matter
sa_ask:
    j     LOSBLOCKED
    nop

smk_idx:                            ; InventoryItem::GetIndex(a0) at the release; s2 = the thrower
    lhu   v1, 8(a0)
    li    t0, {FRAG}
    bne   v1, t0, si_out
    move  t8, s2
    move  t9, ra
    jal   smk_find
    nop
    move  ra, t9
    beqz  v0, si_out
    nop
    sw    zero, 0(v0)               ; used up
    jr    ra
    li    v0, {SMOKE}
si_out:
    jr    ra
    move  v0, v1
"""

SRC_RFC2 = """
rs_geo:                             ; 12-90 m from the threat: throw 10 m toward it
    lwc1  $f3, 0x18(s3)
    lwc1  $f4, 0x2c(s2)
    sub.s $f3, $f3, $f4
    lwc1  $f4, 0x1c(s3)
    lwc1  $f5, 0x30(s2)
    sub.s $f4, $f4, $f5
    lwc1  $f5, 0x20(s3)
    lwc1  $f6, 0x34(s2)
    sub.s $f5, $f5, $f6
    mul.s $f6, $f3, $f3
    mul.s $f7, $f4, $f4
    add.s $f6, $f6, $f7
    mul.s $f7, $f5, $f5
    add.s $f6, $f6, $f7             ; d^2
    lui   t0, 0x4310                ; 12^2
    mtc1  t0, $f7
    c.lt.s $f6, $f7
    bc1t  rs_out
    lui   t0, 0x45fd
    ori   t0, t0, 0x2000            ; 90^2
    mtc1  t0, $f7
    c.lt.s $f7, $f6
    bc1t  rs_out
    nop
    sqrt.s $f6, $f6                 ; d
    lui   t0, 0x4120                ; 10 m
    mtc1  t0, $f7
    div.s $f7, $f7, $f6             ; k = 10 / d
    mul.s $f3, $f3, $f7
    mul.s $f4, $f4, $f7
    mul.s $f5, $f5, $f7
    lwc1  $f6, 0x2c(s2)
    add.s $f3, $f3, $f6
    swc1  $f3, 0x00(sp)             ; the aim point
    lwc1  $f6, 0x30(s2)
    add.s $f4, $f4, $f6
    swc1  $f4, 0x04(sp)
    lwc1  $f6, 0x34(s2)
    add.s $f5, $f5, $f6
    swc1  $f5, 0x08(sp)
    jal   NEW
    li    a0, 0x34
    beqz  v0, rs_out
    nop
    jal   FRAGCTOR
    move  a0, v0
    move  s4, v0
    lwc1  $f0, 0x00(sp)
    swc1  $f0, 0x1c(s4)
    lwc1  $f0, 0x04(sp)
    swc1  $f0, 0x20(s4)
    lwc1  $f0, 0x08(sp)
    swc1  $f0, 0x24(s4)
    sw    zero, 0x2c(s4)            ; level: found at the throw
    lw    a0, 0xc(s2)
    jal   ADDELEM                   ; on top: he throws, then runs
    move  a1, s4
    lui   t0, %hi(CLOCK)            ; mark him for 10 s: a free, stale or his own slot
    lw    t0, %lo(CLOCK)(t0)
    lwc1  $f0, 0xd4(t0)
    lui   t5, %hi(smk_ai_last)
    swc1  $f0, %lo(smk_ai_last)(t5) ; the gate's clock
    lui   t1, %hi(smk_marks)
    addiu t1, t1, %lo(smk_marks)
    move  t4, t1                    ; fallback: slot 0
    li    t2, 4
rs_slot:
    lw    t3, 0(t1)
    beq   t3, s0, rs_put
    lwc1  $f1, 4(t1)
    c.lt.s $f1, $f0
    bc1t  rs_put                    ; expired (or never used)
    addiu t2, t2, -1
    bnez  t2, rs_slot
    addiu t1, t1, 8
    move  t1, t4
rs_put:
    lui   t0, 0x4120                ; 10 s
    mtc1  t0, $f1
    add.s $f1, $f0, $f1
    sw    s0, 0(t1)
    b     rs_out
    swc1  $f1, 4(t1)

smk_find:                           ; t8 = SimHuman -> v0 = his live mark, or 0. t0-t3, f0-f1.
    lui   t0, %hi(CLOCK)
    lw    t0, %lo(CLOCK)(t0)
    beqz  t0, sf_no
    nop
    lwc1  $f0, 0xd4(t0)
    lui   v0, %hi(smk_marks)
    addiu v0, v0, %lo(smk_marks)
    li    t2, 4
sf_loop:
    lw    t3, 0(v0)
    bne   t3, t8, sf_next
    lwc1  $f1, 4(v0)
    c.lt.s $f0, $f1
    bc1t  sf_yes
    nop
sf_next:
    addiu t2, t2, -1
    bnez  t2, sf_loop
    addiu v0, v0, 8
sf_no:
    move  v0, zero
sf_yes:
    jr    ra
    nop

smk_marks:
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
"""

SRC_GATE = """
smk_gate:                           ; v0 = 1: {GAP} s since the last AI smoke and fewer than {MAXC} clouds alive
    lui   t0, %hi(CLOCK)
    lw    t0, %lo(CLOCK)(t0)
    beqz  t0, sg_no
    nop
    lwc1  $f0, 0xd4(t0)             ; now
    lui   t1, %hi(smk_ai_last)
    lwc1  $f1, %lo(smk_ai_last)(t1)
    sub.s $f1, $f0, $f1
    mtc1  zero, $f3
    c.lt.s $f1, $f3
    bc1t  sg_count                  ; the clock went back (a load): no wait
    lui   t2, {GAP_HI}
    mtc1  t2, $f2
    c.lt.s $f1, $f2
    bc1t  sg_no
    nop
sg_count:
    lui   t3, %hi(SMK_RING)
    addiu t3, t3, %lo(SMK_RING)
    li    t4, 8
    move  t5, zero
    lui   t2, {LIFE_HI}             ; a cloud's life
    mtc1  t2, $f2
sg_loop:
    lwc1  $f1, 12(t3)
    sub.s $f1, $f0, $f1             ; its age
    c.lt.s $f1, $f3
    bc1t  sg_next                   ; from before a load
    nop
    c.lt.s $f1, $f2
    bc1f  sg_next
    nop
    addiu t5, t5, 1
sg_next:
    addiu t4, t4, -1
    bnez  t4, sg_loop
    addiu t3, t3, 16
    jr    ra
    sltiu v0, t5, {MAXC}
sg_no:
    jr    ra
    move  v0, zero
smk_ai_last:
    .word {INVALID}
"""

# A throw reports the grenade to the team (HumanAI::ReportGrenadeUse, JS 0x003E0FB0, which writes team+0xEC =
# now), and IsOkToFragHereNow refuses a frag from a team that used one in the last 30 s.  Smoke went through the
# same throw, so every smoke a team put out stopped that team fragging for half a minute -- with smoke allowed
# every 15 s, the enemy threw smoke and never a grenade.  Smoke is not a frag, so it does not report one.
SRC_REP = """
smk_rep:                            ; a0 = the team, a1 = the HumanAI throwing
    move  t9, ra
    jal   smk_find                  ; is he throwing smoke?
    lw    t8, 0x14(a1)              ; (delay) his SimHuman
    bnez  v0, sr_quiet
    move  ra, t9                    ; (delay) either way, go back to his caller
    j     REPORTGREN                ; a real grenade: the team waits 30 s as it always did
    nop
sr_quiet:
    jr    ra
    nop
"""

_SIDE_SRC = {
    "squad": "    bnez  t0, rs_out                ; your squad only\n    nop",
    "enemies": "    beqz  t0, rs_out                ; everyone but your squad\n    nop",
    "all": "",
}

_AI_STOCK_HEX = {
    0x00197C08: (
        "27BDFFA0 FFB40040 FFB30030 0080A02D FFB20020 00A0982D FFB10010 00C0902D"
        "FFB00000 00E0882D FFBF0050 0C060CC8 0100802D DA280000 DA440000 DA450010"
        "DA460020 DA470030 DA890000 DA6A0000 DA8B0000 DA6C0000 4BE821BC 4BE828BD"
        "4BE830BE 4BE83A0B 4BC84ADB 4BC8531B 4A0002FF 4A0002FF 48C08000 4BAB42EC"
        "4BA8632C 4A2B4B3C 4A2C533C 4A0002FF 22310010 DA280000 2210FFFF 48438000"
        "306300C0 10600004 00000000 1410FFEA 00000000 20030001 10400003 0060802D"
        "0C060CDE 00000000 0200102D DFBF0050 DFB40040 DFB30030 DFB20020 DFB10010"
        "DFB00000 03E00008 27BD0060"),
    0x00197F00: (
        "27BDFF60 FFB70080 FFB20030 3C170058 FFBF0090 0080902D FFB60070 FFB50060"
        "FFB40050 FFB30040 FFB10020 FFB00010 AE400008 8E510000 1000003B 8E550004"
        "8E42000C 26100004 1040000C 02B4B021 8E420010 8C430000 0070182B 00000000"
        "00000000 00000000 00000000 00000000 00000000 1460FFFA 00000000 0C065FB2"
        "0220202D 0040982D 8E42000C 1040000D 0200882D 8E420010 02132021 8C430000"
        "0064102B 00000000 00000000 00000000 00000000 00000000 00000000 1440FFFA"
        "00000000 0274102B 1040000E 02A0302D AFB40000 0220202D 0260282D 03A0382D"
        "0C066496 0000402D 8FA30000 10740009 26E42F68 0C05ADDE 0220282D 10000006"
        "8E420008 02A0202D 0220282D 0C05A8D6 0260302D 8E420008 02338821 02C0A82D"
        "00541021 AE420008 8E42000C 1040000B 26300004 8E420010 8C430000 0070182B"
        "00000000 00000000 00000000 00000000 00000000 1460FFFA 00000000 0C065FB2"
        "0220202D 0040A02D 1680FFB5 0200882D 0200102D DFBF0090 DFB70080 DFB60070"
        "DFB50060 DFB40050 DFB30040 DFB20030 DFB10020 DFB00010 03E00008 27BD00A0"),
    0x00175AF0: (   # a DMA/GS register save routine, like the first three caves: unreferenced
        "27BDFFE0 FFB00000 FFBF0010 0C05D6B0 0080802D 24030002 14430003 3C021000"
        "10000021 0000102D 3C031000 34423040 34633050 8C440000 3C071000 34E73060"
        "3C091000 AE040000 35293070 3C081000 3C0A1000 8C620000 35083020 354A3080"
        "3C061000 AE020004 34C63090 3C051000 24020001 8CE40000 34A530A0 AE040008"
        "8D230000 AE03000C 8D040000 AE040010 8D430000 AE030014 8CC40000 AE040018"
        "8CA30000 AE03001C DFBF0010 DFB00000 03E00008 27BD0020"),
    0x0018CAB0: (
        "27BDFF60 3C020062 FFB70080 FFB60070 2457C500 FFB40050 00E0B02D FFB30040"
        "0080A02D FFB20030 00A0982D FFB10020 00C0902D FFBF0090 FFB50060 FFB00010"
        "8EE20024 14400003 0100882D 10000054 2402FF9C 3C150057 0C05E8CC 8EA46634"
        "0440004F 2402FF38 12400004 00000000 82420000 14400005 3C020062 0C05E8C0"
        "8EA46634 10000046 2402FF2E 32310007 2450C5B0 AC54C5B0 AE130004 3C020062"
        "AE110008 2443C540 26040014 0240282D 2449C540 6AC60007 6EC60000 6AC7000F"
        "6EC70008 6AC80017 6EC80010 B1260007 B5260000 B127000F B5270008 B1280017"
        "B5280010 6AC6001F 6EC60018 6AC70027 6EC70020 6AC8002F 6EC80028 B126001F"
        "B5260018 B1270027 B5270020 B128002F B5280028 6AC60037 6EC60030 6AC7003F"
        "6EC70038 B1260037 B5260030 B127003F B5270038 AE030010 0C05B8F2 240603FF"
        "A2000413 0C05E958 0000202D 3C090062 3C0B0019 0200382D 02E0202D 2529DAC0"
        "256BBA10 AFA00000 2405000E 24060001 24080414 0C05F5AA 240A0004 0040802D"
        "16000004 3C030057 2402000E 10000003 AC626630 0C05E8C0 8EA46634 0200102D"
        "DFBF0090 DFB70080 DFB60070 DFB50060 DFB40050 DFB30040 DFB20030 DFB10020"
        "DFB00010 03E00008 27BD00A0"),
}
for _b, _h in _AI_STOCK_HEX.items():
    JS_STOCK.update(_stock_words(_b, _h))
JS_STOCK[HOOK_RFC] = HOOK_RFC_STOCK
JS_STOCK[HOOK_OK] = HOOK_OK_STOCK
JS_STOCK[HOOK_IDX] = HOOK_IDX_STOCK
JS_STOCK[HOOK_ARC] = HOOK_ARC_STOCK
JS_STOCK[HOOK_REP] = HOOK_REP_STOCK


def assemble_ai(side: str = "all", chance: str = "2"):
    """{cave base: words}, labels."""
    if side not in _SIDE_SRC:
        raise ValueError("smoke AI side %r" % side)
    k = dict(CHANCE=hex(AI_CHANCES[chance]), FRAG=FRAG, SMOKE=SMOKE, SIDE=_SIDE_SRC[side], GAP=int(AI_GAP),
             GAP_HI=hex(_hi(AI_GAP)), LIFE_HI=hex(_hi(float(DURATION))), MAXC=AI_MAX_CLOUDS,
             INVALID=hex(_bits(INVALID)))
    assert _bits(AI_GAP) & 0xFFFF == 0 and _bits(float(DURATION)) & 0xFFFF == 0
    pieces = [(0, SRC_RFC.format(**k)), (1, SRC_RFC2.format(**k)), (2, SRC_GATE.format(**k)),
              (3, SRC_REP.format(**k))]
    names = set().union(*(_labels_of(src) for _i, src in pieces))
    labels = {n: CAVES_AI[0][0] for n in names}
    for _ in range(3):
        words, new = {}, {}
        for i, src in pieces:
            base = CAVES_AI[i][0]
            local = _labels_of(src)
            syms = dict(AI_SYMS, SMK_RING=assemble_all()[1]["smk_ring"])
            w, l = assemble(src, base, dict(syms, **{a: b for a, b in labels.items() if a not in local}))
            words[base] = w
            new.update(l)
        if new == labels:
            break
        labels = new
    for i, (base, end) in enumerate(CAVES_AI):
        if base + 4 * len(words[base]) > end:
            raise ValueError("smoke AI routine outgrows cave %d at %#x (%d words, room %d)"
                             % (i, base, len(words[base]), (end - base) // 4))
    return words, labels


def ai_edits(side: str = "all", chance: str = "2"):
    """(va, value, stock, note) for the AI's smoke; [] when side is 'off'."""
    if side == "off":
        return []
    words, l = assemble_ai(side, chance)
    out = []
    for base, w in words.items():
        out += [(base + 4 * i, x, JS_STOCK[base + 4 * i], "smoke grenades: the AI's smoke") for i, x in enumerate(w)]
    j = lambda target, at: assemble("jal %#x" % target, at)[0][0]  # noqa: E731
    out.append((HOOK_RFC, j(l["rfc_smoke"], HOOK_RFC), HOOK_RFC_STOCK,
                "smoke grenades: running for cover may start with a smoke grenade toward the threat"))
    out.append((HOOK_OK, j(l["smk_ok"], HOOK_OK), HOOK_OK_STOCK,
                "smoke grenades: a smoke throw needs no clear blast area"))
    out.append((HOOK_IDX, j(l["smk_idx"], HOOK_IDX), HOOK_IDX_STOCK,
                "smoke grenades: a soldier throwing smoke releases smoke"))
    out.append((HOOK_ARC, j(l["smk_arc"], HOOK_ARC), HOOK_ARC_STOCK,
                "smoke grenades: a smoke throw needs no clear arc"))
    out.append((HOOK_REP, j(l["smk_rep"], HOOK_REP), HOOK_REP_STOCK,
                "smoke grenades: smoke does not use up the team's 30 s grenade wait"))
    return out


# ---- data: the grenade and its name ----------------------------------------------------------

SMOKE_PRJ = (
    "<ProjectileFile>\r\n"
    "\t<VersionNumber>2.000000</VersionNumber>\r\n"
    "\t<NameToken>WPN_SMOKE</NameToken>\r\n"
    "\t<ModelFileName>iw_grenade_fragm67.qob</ModelFileName>\r\n"
    "\t<Weight>0.390000</Weight>\r\n"
    "\t<AirResistanceConstant>0.125</AirResistanceConstant>\r\n"
    "\t<DetonateOnImpact>0</DetonateOnImpact>\r\n"
    "\t<DelayTime>2.000000</DelayTime>\r\n"
    "\t<ExplosionDataVersion>1</ExplosionDataVersion>\r\n"
    "\t<VisualExplosionType>0</VisualExplosionType>\r\n"
    "\t<IsDirectional>FALSE</IsDirectional>\r\n"
    "\t<BlastRadius>0.100000</BlastRadius>\r\n"
    "\t<CombatCoefficient>\r\n"
    "\t\t<CombatCoefficientIndex>0</CombatCoefficientIndex>\r\n"
    "\t\t<CombatCoefficientV0>0</CombatCoefficientV0>\r\n"
    "\t\t<CombatCoefficientV1>0</CombatCoefficientV1>\r\n"
    "\t\t<CombatCoefficientV2>0</CombatCoefficientV2>\r\n"
    "\t\t<CombatCoefficientK1>0</CombatCoefficientK1>\r\n"
    "\t\t<CombatCoefficientK2>0</CombatCoefficientK2>\r\n"
    "\t</CombatCoefficient>\r\n"
    "\t<IconNdx>0</IconNdx>\r\n"
    "</ProjectileFile>\r\n").encode("ascii")
SQUIRREL_SIZE = 892
assert len(SMOKE_PRJ) <= SQUIRREL_SIZE, len(SMOKE_PRJ)


def _op_smoke_prj(plain, params):
    if b"squirrel.qob" not in plain and b"WPN_SMOKE" not in plain:
        raise ValueError("SQUIRREL.PRJ is not the shipped file")
    return SMOKE_PRJ, 1


_LABEL = re.compile(rb'\t"toggle_console"(\t+)"[^"\r\n]*"')


def _op_smoke_label(plain, params):
    m = _LABEL.search(plain)
    if not m:
        raise ValueError("no toggle_console line to carry the smoke label")
    old = m.group()
    head, tail = b'\t"WPN_SMOKE"', b'"SMOKE"'
    tabs = len(old) - len(head) - len(tail)
    if tabs < 1:
        raise ValueError("toggle_console line too short")
    return plain[:m.start()] + head + b"\t" * tabs + tail + plain[m.end():], 1


_KIT_ITEM = re.compile(rb"([ 	]*)<ItemFileName>frag\.prj</ItemFileName>", re.I)


def _op_smoke_kit(plain, params):
    """The kit's thrown item becomes the smoke grenade. The four extra letters are paid for with four
    bytes of line indentation (the deepest-indented lines first), so the file keeps its length."""
    m = _KIT_ITEM.search(plain)
    if not m:
        raise ValueError("kit carries no frag.prj")
    out = plain[:m.start()] + m.group().replace(b"frag.prj", b"squirrel.prj") + plain[m.end():]
    lines = out.split(b"\n")
    need = len(out) - len(plain)
    while need:
        k = max(range(len(lines)), key=lambda i: len(lines[i]) - len(lines[i].lstrip(b" \t")))
        if lines[k][:1] not in (b" ", b"\t"):
            raise ValueError("no indentation left to keep the kit's length")
        lines[k] = lines[k][1:]
        need -= 1
    out = b"\n".join(lines)
    assert len(out) == len(plain)
    return out, 1


# ---- the round cloud ---------------------------------------------------------------------------
# A general effect "smoke_x_typeN" is particle type N-1, one RSParticleSystem read from PARTICLE_EFFECT<N>.POB
# (IkeEffectsMgr::CreateGeneralEffect maps types 0-27 one to one, JS table 0x005892B0; GR's registration order,
# EffectManager::Initialize, is ParticleEffect1..59). smoke_large_type3 is POB 18: a 3ds Max Blizzard -- 75
# particles 9 m wide born anywhere on a flat 24 x 8 m rectangle, the waterfall mist of the ravine and river maps
# -- which is why that cloud reads as a few big flat cards and fills the screen. POB 14 (smoke_medium_type2) is a
# blank SuperSpray (no particles, no texture) that no map, mission or vehicle names; "round" rebuilds it from POB
# 17 (smoke_medium_type3, a working SuperSpray smoke column, ike_fx_smoke_light) with a dome's numbers.
#
# The particle block follows the emitter object's name (length-prefixed, NUL included) by 84 bytes of object
# header, then u32 emitter type (3 SuperSpray, 0 Blizzard), u32 n, n bytes of user properties, then the members
# RSParticleSystem::ReadBinaryPOB (GR 0x004BD060) reads, in order. Offsets below are from that point. What each
# does was read off RSParticleSystem::UpdatePointParticles (GR 0x004C72F0): a SuperSpray particle leaves at
# polar angle off_axis +- axis_spread from the emitter's +Z (world up: the effect is sent the up vector), azimuth
# off_plane +- plane_spread, speed times 1 + speed_var noise per component; count particles are born per
# emission window, never more than count alive.
ROUND_FIELDS = {                      # name: (offset, POB 17's value, the dome's)
    "speed":        (12, 2.4, 1.0),     # m/s
    "speed_var":    (16, 0.0062606, 0.5),
    "grow_for":     (20, 1.1667, 1.5),  # s from small to full size
    "life":         (36, 4.3333, 6.0),  # s
    "life_var":     (40, 0.0, 1.0),
    "size":         (44, 3.2, 3.5),     # m
    "size_var":     (48, 0.0, 0.8),
    "off_axis":     (124, 0.0, 0.65),   # rad: 0 .. 1.3 from straight up
    "axis_spread":  (128, 0.61087, 0.65),
    "plane_spread": (136, 3.1415927, 3.1415927),
}
ROUND_COUNT = (192, 90, 84)           # i0d8: about 60 alive at 6 s each
ROUND_SOURCE = "/PARTICLE_EFFECT17.POB"


def _pob_block(b: bytes, emitter: bytes) -> int:
    """Where the particle members start, after the emitter type, the property string and its length."""
    i = b.find(emitter + b"\x00")
    if i < 0 or b.find(emitter + b"\x00", i + 1) >= 0:
        raise ValueError("POB: emitter %r not found once" % emitter)
    p = i + len(emitter) + 1 + 84
    kind, n = struct.unpack_from("<II", b, p)
    if kind != 3:
        raise ValueError("POB: emitter type %d, not a SuperSpray" % kind)
    return p + 8 + n


def _op_smoke_round(plain, params, sibling=None):
    if sibling is None:
        raise ValueError("smoke_round is built from %s" % ROUND_SOURCE)
    blank = _pob_block(plain, b"SuperSpray01")
    if struct.unpack_from("<I", plain, blank + ROUND_COUNT[0])[0] not in (0, ROUND_COUNT[2]):
        raise ValueError("PARTICLE_EFFECT14.POB is not the shipped blank")
    out = bytearray(sibling)
    p = _pob_block(sibling, b"SuperSpray01")
    if b"ike_fx_smoke_light" not in sibling:
        raise ValueError("%s is not the shipped smoke" % ROUND_SOURCE)
    for name, (off, stock, new) in ROUND_FIELDS.items():
        got = struct.unpack_from("<f", sibling, p + off)[0]
        if abs(got - stock) > 1e-3 * max(1.0, abs(stock)):
            raise ValueError("%s: %s is %g, not the shipped %g" % (ROUND_SOURCE, name, got, stock))
        struct.pack_into("<f", out, p + off, new)
    off, stock, new = ROUND_COUNT
    if struct.unpack_from("<I", sibling, p + off)[0] != stock:
        raise ValueError("%s: particle count is not the shipped %d" % (ROUND_SOURCE, stock))
    struct.pack_into("<I", out, p + off, new)
    return bytes(out), 1


#: kits (single player's kit menus) that carry smoke instead of frags, per choice
SMOKE_KITS = {
    "none": (),
    "second": ("RIFLEMAN-07", "HEAVY-WEAPONS-07", "SNIPER-07"),
    "all": ("RIFLEMAN-03", "RIFLEMAN-07", "HEAVY-WEAPONS-03", "HEAVY-WEAPONS-07", "SNIPER-03", "SNIPER-07",
            "DEMOLITIONS-07", "BUZZ_GORDON-03", "FREDERIK_SUNDSTROM-03", "GUS_BARBER-03", "HENRY_RAMIREZ-03",
            "JACK_STONE-03", "JOHN_DUVAL-03", "KLAUS_HENKEL-03", "OLIVIA_PASCARELLI-03",
            "SANTIAGO_GONZALEZ-03", "SUSAN_GREY-03", "WILL_JACOBS-03"),
}


def _register():
    from . import dataedit
    dataedit.OPS.setdefault("smoke_prj", _op_smoke_prj)
    dataedit.OPS.setdefault("smoke_label", _op_smoke_label)
    dataedit.OPS.setdefault("smoke_kit", _op_smoke_kit)
    dataedit.OPS.setdefault("smoke_round", _op_smoke_round)
    dataedit._WANTS_SIBLING.setdefault("smoke_round", lambda path: ROUND_SOURCE)


_register()


def data_edits(v: dict, prefix: str = "js_") -> list:
    """The grenade, its name, the kits and the round cloud.  Ghost Recon ships the projectiles, the kits and the
    five language strings files in MENU.IMG as well as GR.IMG, and a mission uses the item data parsed from
    MENU.IMG (a shotgun edited in GR.IMG alone got the stock G36 and crashed), so there every edit takes
    archive "" -- both copies.  The particle files are in GR.IMG only, so "" finds that one."""
    if not v.get(prefix + "smoke"):
        return []
    from .model import FileEdit
    arc = "GR.IMG" if prefix == "js_" else ""
    out = [FileEdit("smoke_prj", r"/SQUIRREL\.PRJ$", arc, {}, "SQUIRREL.PRJ becomes the smoke grenade"),
           FileEdit("smoke_label", r"STRINGS\.TXT$", arc, {}, "WPN_SMOKE = SMOKE")]
    table = SMOKE_KITS if prefix == "js_" else GR_SMOKE_KITS
    kits = table.get(v.get(prefix + "smoke_kits", "second"), ())
    if kits:
        out.append(FileEdit("smoke_kit", r"/(%s)\.KIT$" % "|".join(re.escape(k) for k in kits), arc, {},
                            "%d kit(s) carry smoke grenades" % len(kits)))
    if v.get(prefix + "smoke_look", "round") == "round":
        out.append(FileEdit("smoke_round", r"/PARTICLE_EFFECT14\.POB$", arc, {},
                            "PARTICLE_EFFECT14.POB becomes the round smoke cloud"))
    return out


# =============================================================================================
# Ghost Recon (SLUS-20613): the same grenade, cloud, sight and AI, at Ghost Recon's addresses.
# =============================================================================================
# GR is an unstripped build (research/code/symbols_gr.txt); every twin below is named there.

GR_FRAG, GR_SMOKE = 3, 8          # EQUIP_PRJ.DIR has no 30MMGLGRENADE in GR: FRAG.PRJ is 3, SQUIRREL.PRJ 8
#: the general effect each look fires (kGeneralEffectNames, GR 0x0055F090; types 0-27 are particle effects
#: N+1 one to one, CreateGeneralEffect's table 0x00579970)
GR_LOOK_TYPES = {"smoke_large_type1": 11, "smoke_large_type2": 14, "smoke_large_type3": 17, "round": 13}

#: (start, end) of every GR cave.  The first three are lzo/ptr_check and scePad library code that nothing in
#: the image reaches (either side of grcombatmusic's routine at 0x0042F088..0x0042F180); the last three are
#: memory-pool array destructors, unreferenced but for @EX@ records.  gr_layout fills the first two today;
#: the others are room to grow.
GR_CAVES = [(0x0042F180, 0x0042F9CC), (0x0042AC00, 0x0042B018), (0x0042EF88, 0x0042F088),
            (0x003FAB60, 0x003FABC0), (0x003FABD0, 0x003FAC30), (0x003FAC40, 0x003FACA0)]

GR_HOOK_TOGGLE, GR_HOOK_TOGGLE_STOCK = 0x003C765C, 0x0C0D5FD8   # jal IsUsingItem (slot: addiu a0, s1, 0x1b4)
GR_HOOK_DET, GR_HOOK_DET_STOCK = 0x003928F0, 0x0C049A88         # jal RSGameMessage::Create (a0 = 0x196)
GR_LOSC, GR_LOSC_STOCK = 0x0039CD10, (0x27BDFF40, 0xFFBF0050)   # LineOfSightClear's first two words
GR_CHECKLOS_CALLS = (0x003F39C4, 0x003F3B00, 0x003F3D0C, 0x003F3D80)
GR_CHECKLOS_STOCK = 0x0C0FD004                                   # jal CheckLineOfSight
GR_HOOK_RFC, GR_HOOK_RFC_STOCK = 0x001BB438, 0x0C06EBB0         # jal RSScript::AddElement (slot: move a1, s0)
GR_HOOK_OK, GR_HOOK_OK_STOCK = 0x001B449C, 0x0C0640A4           # jal IsOkToFragHereNow (slot: move a3, s2)
GR_HOOK_IDX, GR_HOOK_IDX_STOCK = 0x00398770, 0x0C0E2340         # jal InventoryItem::GetIndex (slot: move a0, s2)
GR_HOOK_ARC, GR_HOOK_ARC_STOCK = 0x001B4424, 0x0C06655C         # jal HumanAI::FragLOSBlocked
GR_HOOK_REP, GR_HOOK_REP_STOCK = 0x001B44B8, 0x0C064208         # jal FireTeamAI::ReportGrenadeUse

GR_SYMS = dict(
    ISUSING=0x00357F60,        # SimHumanState::IsUsingItem
    THROWN_VT=0x00597E60,      # ThrownItem's vtable
    DATAMGR=0x0036A020,        # IIkeDataMgr::Get (vt+0x48 GetProjectileData(us), as SimProjectile's own init)
    GETSIMROOM=0x00366030,     # RSSimController::GetSimRoom
    ROOMID=0x00376520,         # RSSimRoom::GetID
    SCENE=0x00632AF8,          # Scene::mInstance (+0xC: RSArray<Room*>)
    EFFMGR=0x005E76A0,         # IkeEffectsMgr::mIkeEffectsMgr
    CGE=0x0024DE60,            # IkeEffectsMgr::CreateGeneralEffect
    STR_CT=0x0053EBE0, STR_DT=0x0053EAE0,   # RSString(const char*), ~RSString
    CREATE=0x00126A20,         # RSGameMessage::Create(Us)
    RESUME=0x00392B7C,         # HandleDetonateProjectile: removing the projectile (message 0x52)
    EXIT=0x00392BE8,           # HandleDetonateProjectile: ~RSLineCollisionInfoWithUserData, then the epilogue
    CLOCK=0x005DFC20,          # RSClock (+0xD4: TotalElapsedSeconds)
    LOOKTO=0x003F4BE0,         # IkeSimController::GetAwarenessLookToPoint
    CHECKLOS=0x003F4010,       # AwarenessMgr::CheckLineOfSight
    LOSC_BODY=GR_LOSC + 8,
    ADDELEM=0x001BAEC0,        # RSScript::AddElement
    ISOK=0x00190290,           # FireTeamAI::IsOkToFragHereNow
    GETNUMGREN=0x0019A0A0,     # HumanAI::GetNumGrenades
    HASLAUNCHER=0x0019A180,    # HumanAI::HasGrenadeLauncher
    REPORTGREN=0x00190820,     # FireTeamAI::ReportGrenadeUse
    FRAGCTOR=0x001B4650,       # FragLocationBehavior::FragLocationBehavior
    NEW=0x00102DB0,            # operator new
    RANDOMFLOAT=0x00113DC0, RNG=0x005DF770,  # RSRandom::Float(f, f, file, line) on the AI's generator
    RULES=0x0035FD20,          # IIkeRulesMgr::Get (vt+0xE0: GetPlayerCompanyIndex(player, 1))
    LOSBLOCKED=0x00199570,     # HumanAI::FragLOSBlocked
)

# ---- the reload key (SimHuman::ProcessMessage's change-magazine case, GR 0x003C7654) ----------
# a0 = SimHumanState, s1 = SimHuman, the caller's sp+0x6f = the key's state; inventory at +0x4F4
GR_SRC_TOGGLE = """
smk_toggle:
    addiu sp, sp, -0x20
    sd    ra, 0x10(sp)
    jal   ISUSING
    nop
    bnez  v0, st_out                ; busy: as before
    lbu   t0, 0x8f(sp)              ; (delay) pressed (the caller's sp+0x6f)
    beqz  t0, st_zero
    nop
    lw    t9, 0x4f4(s1)             ; inventory
    lb    a1, 0x1e7(s1)             ; current slot
    lw    t9, 0x2c(t9)
    jalr  t9
    addiu a0, s1, 0x4f4
    beqz  v0, st_zero
    lui   t0, %hi(THROWN_VT)
    addiu t0, t0, %lo(THROWN_VT)
    lw    t1, 0(v0)
    bne   t1, t0, st_zero           ; not a thrown item
    lhu   t1, 8(v0)                 ; (delay) its projectile
    li    t2, {FRAG}
    beq   t1, t2, st_set
    li    t3, {SMOKE}               ; (delay) frag -> smoke
    bne   t1, t3, st_zero
    move  t3, t2                    ; (delay) smoke -> frag
st_set:
    sh    t3, 8(v0)
    b     st_out
    li    v0, 1                     ; the press is used up
st_zero:
    move  v0, zero
st_out:
    ld    ra, 0x10(sp)
    jr    ra
    addiu sp, sp, 0x20
"""

# ---- the detonation (IkeSimulationMgr::HandleDetonateProjectile, GR 0x003925E0) ----------------
# For jal Create(0x196) -- the explosion visual: s0 = the SimProjectile, s1 = its ExplosionData, the caller's
# sp+0x1c8 = where it went off.  GR's handler for TriggerGeneralEffect (IkeEffectsMgr 0x00249D40) is an empty
# stub, so the cloud is made the way AddGeneralEffects makes a map's: CreateGeneralEffect(type, name, where,
# rotation, parent, Room, false, true) -- the arguments Jungle Storm's trigger handler passes it -- in the
# Room the explosion visual would have named (the projectile's sim room id, Scene's rooms).
GR_SRC_DET = """
smk_det:
    lw    t0, 8(s1)                 ; its visual explosion type
    bnez  t0, sd_create             ; a real explosion
    nop
    addiu sp, sp, -0x70
    sd    ra, 0x60(sp)
    sq    s0, 0x10(sp)
    sq    s1, 0x20(sp)
    sq    s2, 0x30(sp)
    jal   DATAMGR
    nop
    lw    t9, 0(v0)
    lw    t9, 0x48(t9)              ; GetProjectileData
    move  a0, v0
    jalr  t9
    li    a1, {SMOKE}
    addiu v0, v0, 0x4c              ; the smoke grenade's ExplosionData
    bne   v0, s1, sd_other          ; another projectile with no visual (the howitzer shell)
    move  s2, s0                    ; (delay) the SimProjectile
    addiu s0, sp, 0x238             ; the caller's sp+0x1c8, where the grenade is now
    move  a0, s0
    jal   smk_hold                  ; has it stopped moving?
    move  a1, s2
    beqz  v0, sd_hold               ; no: let it fly on, the fuse asks again next frame
    nop
    jal   GETSIMROOM                ; the room the explosion visual would have been sent
    move  a0, s2
    jal   ROOMID
    move  a0, v0
    andi  t0, v0, 0xff
    lui   t1, %hi(SCENE)
    lw    t1, %lo(SCENE)(t1)
    beqz  t1, sd_done               ; no scene: no effect, no cloud
    sll   t0, t0, 2
    lw    t1, 0xc(t1)               ; its rooms
    addu  t1, t1, t0
    lw    s1, 0(t1)                 ; the Room
    beqz  s1, sd_done
    lui   s2, %hi(EFFMGR)
    lw    s2, %lo(EFFMGR)(s2)       ; IkeEffectsMgr
    beqz  s2, sd_done
    lui   a1, %hi(smk_name)
    addiu a1, a1, %lo(smk_name)
    jal   STR_CT                    ; RSString "smoke_...(45)"
    addiu a0, sp, 0x40
    sw    zero, 0x50(sp)            ; no rotation: the effect's +Z is world up
    sw    zero, 0x54(sp)
    sw    zero, 0x58(sp)
    lui   t0, 0x3f80
    sw    t0, 0x5c(sp)
    li    v0, 1
    sd    v0, 0(sp)                 ; the ninth argument: true
    move  a0, s2
    li    a1, {TYPE}                ; the general effect
    addiu a2, sp, 0x40              ; its name; the "(45)" is its life in seconds
    move  a3, s0                    ; where
    addiu t0, sp, 0x50              ; rotation
    move  t1, zero                  ; no parent
    move  t2, s1                    ; the Room
    jal   CGE
    move  t3, zero
    addiu a0, sp, 0x40
    jal   STR_DT
    li    a1, -1
smk_note:                           ; the ring entry: x, y, z + 1.5, now
    lui   t0, %hi(CLOCK)
    lw    t0, %lo(CLOCK)(t0)
    beqz  t0, sd_done
    nop
    lwc1  $f0, 0xd4(t0)             ; now
    lui   t1, %hi(smk_next)
    lw    t2, %lo(smk_next)(t1)
    andi  t2, t2, 7
    addiu t3, t2, 1
    sw    t3, %lo(smk_next)(t1)
    sll   t2, t2, 4
    lui   t4, %hi(smk_ring)
    addiu t4, t4, %lo(smk_ring)
    addu  t4, t4, t2
    lwc1  $f1, 0(s0)
    swc1  $f1, 0(t4)
    lwc1  $f1, 4(s0)
    swc1  $f1, 4(t4)
    lwc1  $f1, 8(s0)
    lui   t5, 0x3fc0                ; 1.5 m
    mtc1  t5, $f2
    add.s $f1, $f1, $f2
    swc1  $f1, 8(t4)
    swc1  $f0, 12(t4)
    lui   t5, {OFF_HI}
    mtc1  t5, $f2
    add.s $f2, $f0, $f2             ; it stops blocking then
    lui   t1, %hi(smk_until)
    lwc1  $f1, %lo(smk_until)(t1)
    c.lt.s $f1, $f2
    bc1f  sd_done
    nop
    swc1  $f2, %lo(smk_until)(t1)
sd_done:
    lq    s0, 0x10(sp)
    lq    s1, 0x20(sp)
    lq    s2, 0x30(sp)
    ld    ra, 0x60(sp)
    addiu sp, sp, 0x70
    move  s3, zero                  ; no explosion alert (GR's instigator is s3)
    lui   ra, %hi(RESUME)
    addiu ra, ra, %lo(RESUME)       ; on to removing the projectile
    jr    ra
    nop
sd_hold:                            ; still in the air or rolling: handle nothing, keep the grenade
    lq    s0, 0x10(sp)
    lq    s1, 0x20(sp)
    lq    s2, 0x30(sp)
    ld    ra, 0x60(sp)
    addiu sp, sp, 0x70
    j     EXIT                      ; HandleDetonateProjectile's own way out
    nop
sd_create:
    j     CREATE
    nop
sd_other:                           ; not the smoke grenade: Create(0x196) as before
    lq    s0, 0x10(sp)
    lq    s1, 0x20(sp)
    lq    s2, 0x30(sp)
    ld    ra, 0x60(sp)
    addiu sp, sp, 0x70
    j     CREATE
    li    a0, 0x196
"""


def _gr_eye(src, frame=None):
    """A sight routine at GR's offsets: the eye is vtable +0x324 there (GetAwarenessLocation), and
    LineOfSightClear's frame is 0xC0."""
    out = src.replace("lw    t9, 0x328(t9)             ; his eye", "lw    t9, 0x324(t9)             ; his eye")
    if out.count("0x324(t9)") != 1:
        raise ValueError("sight routine: eye offset not found once")
    if frame:
        old = "addiu sp, sp, -0xb0             ; LineOfSightClear's own first two words"
        if old not in out:
            raise ValueError("sight routine: LineOfSightClear's frame not found")
        out = out.replace(old, "addiu sp, sp, -%#x             ; LineOfSightClear's own first two words" % frame)
    return out


# ---- the AI (RunForCoverBehavior::Process, GR 0x001BB1E0: s1 = HumanAI, s2 = the behaviour; after its
# AddElement only the epilogue runs, which restores s0-s5) -------------------------------------------
# Your squad is the company GetPlayerCompanyIndex(player 0) answers: GR has no players'-company static.
_GR_SIDE_SRC = {
    "squad": "bnez  t0, rs_out                ; your squad only",
    "enemies": "beqz  t0, rs_out                ; everyone but your squad",
}
_GR_SIDE_CALL = """
    jal   RULES                     ; IIkeRulesMgr::Get
    nop
    lw    t9, 0(v0)
    move  a0, v0
    lw    t9, 0xe0(t9)              ; GetPlayerCompanyIndex(player 0, 1)
    move  a1, zero
    jalr  t9
    li    a2, 1
    lw    t0, 0x178(s0)             ; his company
    xor   t0, t0, v0                ; 0: the players' squad
    {TEST}
    nop
"""

GR_SRC_RFC = """
rfc_smoke:                          ; AddElement(a0 script, a1 the move) in RunForCover
    addiu sp, sp, -0x40
    sd    ra, 0x30(sp)
    jal   ADDELEM                   ; the move, as before
    nop
    lw    s0, 0x14(s1)              ; his SimHuman
    beqz  s0, rs_out
    nop
{SIDE}
    lbu   t0, 0x132(s1)             ; carries grenades at all
    beqz  t0, rs_out
    lw    s3, 0xa4(s1)              ; (delay) his fireteam
    beqz  s3, rs_out
    lui   t0, %hi(CLOCK)
    lw    t0, %lo(CLOCK)(t0)
    beqz  t0, rs_out
    nop
    lwc1  $f0, 0xd4(t0)             ; now
    lwc1  $f1, 0xec(s3)             ; the team's last grenade
    sub.s $f1, $f0, $f1
    lui   t1, 0x41f0                ; 30 s, the game's own wait
    mtc1  t1, $f2
    c.lt.s $f1, $f2
    bc1t  rs_out
    nop
    jal   smk_gate                  ; 15 s since the last AI smoke, fewer than 2 clouds alive
    nop
    beqz  v0, rs_out
    nop
    jal   GETNUMGREN
    move  a0, s1
    blez  v0, rs_out
    nop
    jal   HASLAUNCHER               ; a launcher would fire, not throw
    move  a0, s1
    andi  v0, v0, 0xff
    bnez  v0, rs_out
    lui   a0, %hi(RNG)
    addiu a0, a0, %lo(RNG)
    move  a1, zero
    move  a2, zero
    mtc1  zero, $f12
    lui   v0, 0x3f80
    jal   RANDOMFLOAT               ; 0..1
    mtc1  v0, $f13
    lui   v0, {CHANCE}
    mtc1  v0, $f1
    nop
    c.lt.s $f0, $f1
    bc1t  rs_geo
    nop
rs_out:
    ld    ra, 0x30(sp)
    jr    ra
    addiu sp, sp, 0x40
rs_geo:                             ; 12-90 m from the threat: throw 10 m toward it
    lwc1  $f3, 0x18(s2)
    lwc1  $f4, 0x2c(s1)
    sub.s $f3, $f3, $f4
    lwc1  $f4, 0x1c(s2)
    lwc1  $f5, 0x30(s1)
    sub.s $f4, $f4, $f5
    lwc1  $f5, 0x20(s2)
    lwc1  $f6, 0x34(s1)
    sub.s $f5, $f5, $f6
    mul.s $f6, $f3, $f3
    mul.s $f7, $f4, $f4
    add.s $f6, $f6, $f7
    mul.s $f7, $f5, $f5
    add.s $f6, $f6, $f7             ; d^2
    lui   t0, 0x4310                ; 12^2
    mtc1  t0, $f7
    c.lt.s $f6, $f7
    bc1t  rs_out
    lui   t0, 0x45fd
    ori   t0, t0, 0x2000            ; 90^2
    mtc1  t0, $f7
    c.lt.s $f7, $f6
    bc1t  rs_out
    nop
    sqrt.s $f6, $f6                 ; d
    lui   t0, 0x4120                ; 10 m
    mtc1  t0, $f7
    div.s $f7, $f7, $f6             ; k = 10 / d
    mul.s $f3, $f3, $f7
    mul.s $f4, $f4, $f7
    mul.s $f5, $f5, $f7
    lwc1  $f6, 0x2c(s1)
    add.s $f3, $f3, $f6
    swc1  $f3, 0x00(sp)             ; the aim point
    lwc1  $f6, 0x30(s1)
    add.s $f4, $f4, $f6
    swc1  $f4, 0x04(sp)
    lwc1  $f6, 0x34(s1)
    add.s $f5, $f5, $f6
    swc1  $f5, 0x08(sp)
    jal   NEW
    li    a0, 0x34
    beqz  v0, rs_out
    nop
    jal   FRAGCTOR
    move  a0, v0
    move  s4, v0
    lwc1  $f0, 0x00(sp)
    swc1  $f0, 0x1c(s4)
    lwc1  $f0, 0x04(sp)
    swc1  $f0, 0x20(s4)
    lwc1  $f0, 0x08(sp)
    swc1  $f0, 0x24(s4)
    sw    zero, 0x2c(s4)            ; level: found at the throw
    lw    a0, 0xc(s1)
    jal   ADDELEM                   ; on top: he throws, then runs
    move  a1, s4
    lui   t0, %hi(CLOCK)            ; mark him for 10 s: a free, stale or his own slot
    lw    t0, %lo(CLOCK)(t0)
    lwc1  $f0, 0xd4(t0)
    lui   t5, %hi(smk_ai_last)
    swc1  $f0, %lo(smk_ai_last)(t5) ; the gate's clock
    lui   t1, %hi(smk_marks)
    addiu t1, t1, %lo(smk_marks)
    move  t4, t1                    ; fallback: slot 0
    li    t2, 4
rs_slot:
    lw    t3, 0(t1)
    beq   t3, s0, rs_put
    lwc1  $f1, 4(t1)
    c.lt.s $f1, $f0
    bc1t  rs_put                    ; expired (or never used)
    addiu t2, t2, -1
    bnez  t2, rs_slot
    addiu t1, t1, 8
    move  t1, t4
rs_put:
    lui   t0, 0x4120                ; 10 s
    mtc1  t0, $f1
    add.s $f1, $f0, $f1
    sw    s0, 0(t1)
    b     rs_out
    swc1  $f1, 4(t1)
"""

GR_SRC_OK = """
smk_ok:                             ; IsOkToFragHereNow(a0 team, a1 &aim, a2 level, a3 HumanAI) at the throw
    lw    t8, 0x14(a3)
    move  t9, ra
    jal   smk_find
    nop
    move  ra, t9
    beqz  v0, so_ask
    nop
    jr    ra
    li    v0, 1                     ; smoke: no blast to keep friends from
so_ask:
    j     ISOK
    nop
"""

GR_SRC_ARC = """
smk_arc:                            ; FragLOSBlocked(a0 HumanAI, a1 &point, f12 reach) before the throw
    lw    t8, 0x14(a0)
    move  t9, ra
    jal   smk_find
    nop
    move  ra, t9
    beqz  v0, sa_ask
    nop
    jr    ra
    move  v0, zero                  ; smoke: a branch in the way does not matter
sa_ask:
    j     LOSBLOCKED
    nop
"""

GR_SRC_IDX = """
smk_idx:                            ; InventoryItem::GetIndex(a0) at the release; s0 = the thrower (GR)
    lhu   v1, 8(a0)
    li    t0, {FRAG}
    bne   v1, t0, si_out
    move  t8, s0
    move  t9, ra
    jal   smk_find
    nop
    move  ra, t9
    beqz  v0, si_out
    nop
    sw    zero, 0(v0)               ; used up
    jr    ra
    li    v0, {SMOKE}
si_out:
    jr    ra
    move  v0, v1
"""

GR_SRC_FIND = """
smk_find:                           ; t8 = SimHuman -> v0 = his live mark, or 0. t0-t3, f0-f1.
    lui   t0, %hi(CLOCK)
    lw    t0, %lo(CLOCK)(t0)
    beqz  t0, sf_no
    nop
    lwc1  $f0, 0xd4(t0)
    lui   v0, %hi(smk_marks)
    addiu v0, v0, %lo(smk_marks)
    li    t2, 4
sf_loop:
    lw    t3, 0(v0)
    bne   t3, t8, sf_next
    lwc1  $f1, 4(v0)
    c.lt.s $f0, $f1
    bc1t  sf_yes
    nop
sf_next:
    addiu t2, t2, -1
    bnez  t2, sf_loop
    addiu v0, v0, 8
sf_no:
    move  v0, zero
sf_yes:
    jr    ra
    nop
smk_marks:
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
"""

#: (piece, group): "smoke" pieces go in whenever gr_smoke is on, "ai" ones only with an AI side.  Pieces
#: reach each other only by j/jal/%hi-%lo, so any piece may sit in any cave.
_GR_PIECES = ("toggle", "det", "hold", "slots", "sight", "los", "clear", "data",
              "rfc", "ok", "arc", "idx", "find", "gate", "rep")
_GR_AI_PIECES = {"rfc", "ok", "arc", "idx", "find", "gate", "rep"}


def _gr_sources(look: str, side: str, chance: str) -> dict:
    if look not in GR_LOOK_TYPES:
        raise ValueError("smoke look %r" % look)
    if side not in ("squad", "enemies", "all", "off"):
        raise ValueError("smoke AI side %r" % side)
    k = dict(FRAG=GR_FRAG, SMOKE=GR_SMOKE, TYPE=GR_LOOK_TYPES[look], OFF_HI=hex(_hi(OFF)), ON_HI=hex(_hi(ON)),
             R2_HI=hex(_hi(RADIUS * RADIUS)), INV_HI=hex(_bits(INVALID) >> 16), INV_LO=hex(_bits(INVALID) & 0xFFFF),
             SLOTS=HOLD_SLOTS, STALE_HI=hex(_hi(HOLD_STALE)), MAXW_HI=hex(_hi(HOLD_MAX)),
             EPS2_HI=hex(_bits(HOLD_EPS * HOLD_EPS) >> 16), EPS2_LO=hex(_bits(HOLD_EPS * HOLD_EPS) & 0xFFFF),
             SLOTDATA="\n".join("    .word 0" for _ in range(6 * HOLD_SLOTS)),
             CHANCE=hex(AI_CHANCES[chance]), GAP=int(AI_GAP), GAP_HI=hex(_hi(AI_GAP)),
             LIFE_HI=hex(_hi(float(DURATION))), MAXC=AI_MAX_CLOUDS, INVALID=hex(_bits(INVALID)))
    test = _GR_SIDE_SRC.get(side)
    k["SIDE"] = _GR_SIDE_CALL.replace("{TEST}", test) if test else ""
    ring = "\n".join("    .word 0\n    .word 0\n    .word 0\n    .word %#x" % _bits(INVALID) for _ in range(8))
    effect = ROUND_EFFECT if look == "round" else look
    data = SRC_DATA.replace("{RING}", ring).replace("{NAME}", "%s(%d)" % (effect, DURATION))
    return {
        "toggle": GR_SRC_TOGGLE.format(**k),
        "det": GR_SRC_DET.format(**k),
        "hold": SRC_HOLD.format(**k),
        "slots": SRC_SLOTS.format(**k),
        "sight": SRC_BLOCKED.format(**k) + SRC_BLOCKED2.format(**k),
        "los": _gr_eye(SRC_LOS),
        "clear": _gr_eye(SRC_CLEAR, frame=0xC0),
        "data": data,
        "rfc": GR_SRC_RFC.replace("{SIDE}", k["SIDE"]).replace("{CHANCE}", k["CHANCE"]),
        "ok": GR_SRC_OK,
        "arc": GR_SRC_ARC,
        "idx": GR_SRC_IDX.format(**k),
        "find": GR_SRC_FIND,
        "gate": SRC_GATE.format(**k),
        "rep": SRC_REP,
    }


def _words_in(src: str) -> int:
    from .grasm import Asm
    return sum(Asm._size(x) for kind, x in Asm._items(src) if kind == "ins")


def gr_layout() -> dict:
    """{piece: cave base}: first fit, largest piece first, sized by the largest variant of each piece, so
    every setting puts every piece at the same address."""
    sizes = {}
    for look in GR_LOOK_TYPES:
        for side in ("squad", "enemies", "all"):
            for p, src in _gr_sources(look, side, "2").items():
                sizes[p] = max(sizes.get(p, 0), _words_in(src))
    room = [[lo, hi] for lo, hi in GR_CAVES]
    out = {}
    for p in sorted(_GR_PIECES, key=lambda q: (-sizes[q], _GR_PIECES.index(q))):
        for c in room:
            if c[0] + 4 * sizes[p] <= c[1]:
                out[p] = c[0]
                c[0] += 4 * sizes[p]
                break
        else:
            raise ValueError("Ghost Recon smoke: no cave left for %s (%d words)" % (p, sizes[p]))
    return out


def gr_assemble(look: str = "round", side: str = "all", chance: str = "2"):
    """{piece: (base, words)}, labels -- every piece, whatever the AI setting (the caller picks)."""
    srcs = _gr_sources(look, side, chance)
    where = gr_layout()
    names = set().union(*(_labels_of(s) for s in srcs.values()))
    labels = {n: where["det"] for n in names}           # first-pass stand-ins
    for _ in range(4):
        out, new = {}, {}
        for p, src in srcs.items():
            local = _labels_of(src)
            syms = dict(GR_SYMS, SMK_RING=labels["smk_ring"])
            w, l = assemble(src, where[p], dict(syms, **{a: b for a, b in labels.items() if a not in local}))
            out[p] = (where[p], w)
            new.update(l)
        if new == labels:
            break
        labels = new
    else:
        raise ValueError("Ghost Recon smoke: labels did not settle")
    for p, (base, w) in out.items():
        if not any(lo <= base and base + 4 * len(w) <= hi for lo, hi in GR_CAVES):
            raise ValueError("Ghost Recon smoke: %s leaves its cave" % p)
    return out, labels


def gr_edits(v: dict) -> list:
    """(va, value, stock, note) for Ghost Recon: gr_smoke, gr_smoke_look, gr_smoke_ai, gr_smoke_ai_chance."""
    if not v.get("gr_smoke"):
        return []
    side = v.get("gr_smoke_ai", "all")
    pieces, l = gr_assemble(v.get("gr_smoke_look", "round"), side, v.get("gr_smoke_ai_chance", "2"))
    out = []
    for p in _GR_PIECES:
        if p in _GR_AI_PIECES and side == "off":
            continue
        base, w = pieces[p]
        what = "the AI's smoke" if p in _GR_AI_PIECES else "routines"
        out += [(base + 4 * i, x, GR_STOCK[base + 4 * i], "smoke grenades: %s" % what) for i, x in enumerate(w)]
    j = lambda op, target, at: assemble("%s %#x" % (op, target), at)[0][0]  # noqa: E731
    out.append((GR_HOOK_TOGGLE, j("jal", l["smk_toggle"], GR_HOOK_TOGGLE), GR_HOOK_TOGGLE_STOCK,
                "smoke grenades: reload with grenades in hand switches frag / smoke"))
    out.append((GR_HOOK_DET, j("jal", l["smk_det"], GR_HOOK_DET), GR_HOOK_DET_STOCK,
                "smoke grenades: a smoke projectile pops a cloud, no blast"))
    out.append((GR_LOSC, j("j", l["smk_clear"], GR_LOSC), GR_LOSC_STOCK[0],
                "smoke grenades: LineOfSightClear through a cloud is no"))
    out.append((GR_LOSC + 4, 0, GR_LOSC_STOCK[1], "smoke grenades: LineOfSightClear (slot)"))
    for va in GR_CHECKLOS_CALLS:
        out.append((va, j("jal", l["smk_los"], va), GR_CHECKLOS_STOCK,
                    "smoke grenades: no spotting through a cloud"))
    if side != "off":
        out.append((GR_HOOK_RFC, j("jal", l["rfc_smoke"], GR_HOOK_RFC), GR_HOOK_RFC_STOCK,
                    "smoke grenades: running for cover may start with a smoke grenade toward the threat"))
        out.append((GR_HOOK_OK, j("jal", l["smk_ok"], GR_HOOK_OK), GR_HOOK_OK_STOCK,
                    "smoke grenades: a smoke throw needs no clear blast area"))
        out.append((GR_HOOK_IDX, j("jal", l["smk_idx"], GR_HOOK_IDX), GR_HOOK_IDX_STOCK,
                    "smoke grenades: a soldier throwing smoke releases smoke"))
        out.append((GR_HOOK_ARC, j("jal", l["smk_arc"], GR_HOOK_ARC), GR_HOOK_ARC_STOCK,
                    "smoke grenades: a smoke throw needs no clear arc"))
        out.append((GR_HOOK_REP, j("jal", l["smk_rep"], GR_HOOK_REP), GR_HOOK_REP_STOCK,
                    "smoke grenades: smoke does not use up the team's 30 s grenade wait"))
    return out


#: the kit-screen kits that carry smoke instead of frags, per gr_smoke_kits choice.  Ghost Recon's riflemen
#: carry no frags; each class's second grenade kit is "second".  Every one is in GR.IMG and MENU.IMG alike.
GR_SMOKE_KITS = {
    "none": (),
    "second": ("DEMOLITIONS-06", "HEAVY-WEAPONS-06", "SNIPER-08"),
    "all": ("DEMOLITIONS-03", "DEMOLITIONS-06", "DEMOLITIONS-10", "HEAVY-WEAPONS-02", "HEAVY-WEAPONS-06",
            "HEAVY-WEAPONS-10", "SNIPER-04", "SNIPER-08", "SNIPER-12", "ASTRA_GALINSKY-04", "DIETER_MUNZ-02",
            "D_JODIT_HAILE-02", "GURAM_OSADZE-02", "JACK_STONE-04", "NIGEL_TUNNEY-02", "SCOTT_IBRAHIM-04"),
}

_GR_CAVE_STOCK_HEX = {
    0x0042F180: (
        "01AC6821 01896021 01AC6821 01836021 01AC6821 018A6021 01AC6821 01866021"
        "1160FFCD 01AC6821 51E00009 0199001B 91C20000 25EFFFFF 25CE0001 01826021"
        "00000000 1DE0FFFA 01AC6821 0199001B 71B9001B 53300001 000001CD 53300001"
        "000001CD 00001010 70001810 0040602D 1700FFB3 0060682D 000D1400 004C1025"
        "DFB10010 DFB00000 03E00008 27BD0020 27BDFFF0 FFBF0000 0C100E26 00000000"
        "DFBF0000 03E00008 27BD0010 00000000 27BDFFF0 FFBF0000 0C100E4C 00000000"
        "DFBF0000 03E00008 27BD0010 00000000 27BDFFF0 FFBF0000 0C100E78 00000000"
        "DFBF0000 03E00008 27BD0010 00000000 27BDFFF0 FFBF0000 0C100EBA 00000000"
        "DFBF0000 03E00008 27BD0010 00000000 27BDFFF0 3C020056 8C4318D4 0080382D"
        "FFBF0000 3C020059 00A0302D 8C64000C 0C1005BC 24459250 DFBF0000 0000102D"
        "03E00008 27BD0010 03E00008 24020001 03E00008 24020001 27BDFF10 FFB700D0"
        "27A2004F FFB20080 27B70030 FFB10070 27B20050 FFB00060 24110001 FFBF00E0"
        "2410001F FFB600C0 FFB500B0 FFB400A0 FFB30090 00000000 A0500000 2610FFFF"
        "00000000 00000000 00000000 0601FFFA 2442FFFF 03A0202D 0C10BBE4 24050008"
        "03A2A021 029D8023 06010007 0280A82D 3C040059 24050402 0C10BCA4 24849278"
        "10000002 02228824 32310001 2A020008 54400006 32310001 3C040059 24050403"
        "0C10BCA4 24849280 02228824 0240202D 240500FF 0C100EBA 24060008 97A30050"
        "3402FFFF 10620006 3C040059 24050406 0C10BCA4 248492A0 10000002 02228824"
        "32310001 3C02FFFF 8FA30050 3442FFFF 10620006 3C040059 24050407 0C10BCA4"
        "248492B8 10000002 02228824 32310001 DFA30050 2402FFFF 10620006 3C040059"
        "24050408 0C10BCA4 248492D0 10000002 02228824 32310001 3C02FFFF 8FA30050"
        "3442FFFF 10620006 3C040059 24050409 0C10BCA4 248492E8 10000002 02228824"
        "32310001 24020001 56220011 FFA00050 3C160059 0280982D 02A0902D 24100007"
        "12530005 26C49308 0C10BCA4 2405040E 10000002 02228824 32310001 26730004"
        "2610FFFF 0601FFF6 26520004 FFA00050 8FA20050 10400006 3C040059 24050412"
        "0C10BCA4 24849360 10000002 02228824 32310001 8FA20050 10400006 3C040059"
        "24050413 0C10BCA4 24849378 10000002 02228824 32310001 32310001 24020001"
        "56220075 0220102D 26A40004 24100009 26A20024 00000000 AC540000 2610FFFF"
        "00000000 00000000 00000000 0601FFFA 2442FFFC 0000282D 0C100EBA 24060020"
        "8EA30000 10740006 3C040059 2405041A 0C10BCA4 24849390 10000002 02228824"
        "32310001 3C130059 26B20004 24100007 8E420000 10400005 266493A8 0C10BCA4"
        "2405041C 10000002 02228824 32310001 2610FFFF 0601FFF6 26520004 8EA20024"
        "10540006 3C040059 2405041D 0C10BCA4 248493B8 10000002 02228824 32310001"
        "24020001 16220044 0220102D 27A40031 24050004 0C10BBE4 0080982D 24500001"
        "02F09021 32420003 10400005 2405042A 3C040059 0C10BCA4 248493D0 30510001"
        "56000006 32310001 3C040059 24050430 0C10BCA4 248493F0 02228824 0253102B"
        "10400006 3C040059 24050432 0C10BCA4 248493F8 10000002 02228824 32310001"
        "2E020005 54400006 32310001 3C040059 24050434 0C10BCA4 24849408 02228824"
        "27A20035 0242102B 54400006 32310001 3C040059 24050436 0C10BCA4 24849410"
        "02228824 24020001 16220013 0220102D 02F01021 03B01821 8C440000 14800006"
        "8C700034 3C040059 2405043D 0C10BCA4 24849420 30510001 56000006 32310001"
        "3C040059 2405043E 0C10BCA4 24849428 02228824 0220102D DFBF00E0 DFB700D0"
        "DFB600C0 DFB500B0 DFB400A0 DFB30090 DFB20080 DFB10070 DFB00060 03E00008"
        "27BD00F0 00000000 27BDFFB0 FFB00020 FFBF0040 0C10BCB2 FFB10030 0C10BCB4"
        "30500001 02028024 24020001 12020003 24110001 1000003A 2402FFFF 2403001F"
        "27A2001F 00000000 A0430000 2463FFFF 00000000 00000000 00000000 0461FFFA"
        "2442FFFF 0220802D 24020001 1602002A 3A030001 0C10BE06 00000000 10400005"
        "240504B7 3C040059 0C10BCA4 24849430 30500001 16110020 3A030001 3C020057"
        "0000182D 8C42F280 1040000A 3C04005F 0040302D 24852630 2462FFFD ACA20000"
        "24630001 0066102B 00000000 1440FFFA 24A50004 0C10BE14 24842630 10400006"
        "3C040059 240504C2 0C10BCA4 24849448 10000002 02028024 32100001 24020001"
        "16020005 3A030001 0C10BCB6 00000000 30500001 3A030001 2402FFFF 0003100A"
        "DFBF0040 DFB10030 DFB00020 03E00008 27BD0050 00000000 27BDFFF0 3C020059"
        "24469460 68C30007 6CC30000 8CC40008 B3A30007 B7A30000 AFA40008 8FA20000"
        "2C420001 03E00008 27BD0010 00000000 8C830000 2402FFFD 14620009 0000282D"
        "8C830004 2402FFFE 54620006 24050001 8C830008 2402FFFF 10620002 00000000"
        "24050001 03E00008 00A0102D 00000000 27BDFFF0 3C030057 24020001 FFBF0000"
        "AC62F284 8FAC0010 1080002A 8FAD0018 2403FFFF 10A30004 0000202D 24020002"
        "14A20022 00000000 10C30003 24020004 14C2001E 00000000 10E30003 24020008"
        "14E2001A 00000000 11030003 24020004 15020016 00000000 11230003 24020004"
        "15220012 00000000 11430003 24020004 1542000E 00000000 11630003 24020004"
        "1562000A 00000000 11830003 24020004 15820006 00000000 11A30003 24020004"
        "15A20002 00000000 24040001 14800003 00000000 10000003 2402FFFF 0C10BDBA"
        "00000000 DFBF0000 03E00008 27BD0010 90A20002 34079F5F 90A30001 00872018"
        "00021140 90A60000 00431026 00021140 00461026 00042142 00471018 30843FFF"
        "00021142 30423FFF 10820006 3C040059 3C060059 24849208 24C69470 080FFEB6"
        "240505DB 03E00008 00000000"),

    0x0042AC00: (
        "0080302D 24030070 2404001C 70C31818 00A42018 27BDFFF0 3C02005F FFBF0000"
        "24422390 00832021 00441021 8C430010 1060001D 0000102D 0C10A8DA 00C0202D"
        "0040302D 24030001 90C20072 50430003 90C20064 10000014 0000102D 2C420002"
        "14400011 0000102D 90C20066 2C420002 1440000D 0000102D 90C5007A 90C4007C"
        "90C3007B 00052A38 90C20079 00042638 00031C38 0044102D 0065182D 0043102D"
        "0002103C 0002103F DFBF0000 03E00008 27BD0010 00000000 27BDFFB0 3C02005F"
        "FFB00010 2403000A 24502580 FFB20030 FFB10020 0080902D FFBF0040 00A0882D"
        "AE06000C 3C04005F AC432580 24842340 AE120004 24050001 AE110008 0000302D"
        "AFA00000 0200382D 24080080 0200482D 240A0080 0C10531C 0000582D 04430003"
        "8E030010 1000000A 0000102D 24020001 14620007 0060102D 0240202D 0220282D"
        "0C10A952 24060002 8E030010 0060102D DFBF0040 DFB20030 DFB10020 DFB00010"
        "03E00008 27BD0050 0080302D 24030070 2404001C 70C31818 00A42018 27BDFFF0"
        "3C02005F FFBF0000 24422390 00832021 00441021 8C430010 10600007 0000102D"
        "0C10AB00 00C0202D 3C030003 3463FFFF 00431026 2C420001 DFBF0000 03E00008"
        "27BD0010 00000000 0080302D 24030070 2404001C 70C31818 00A42018 27BDFFF0"
        "3C02005F FFBF0000 24422390 00832021 00441021 8C430010 14600003 00C0202D"
        "10000003 0000102D 0C10AB2E 24060FFF DFBF0000 03E00008 27BD0010 00000000"
        "0080302D 24030070 2404001C 70C31818 00A42018 27BDFFF0 3C02005F FFBF0000"
        "24422390 00832021 00441021 8C430010 14600003 00C0202D 10000003 0000102D"
        "0C10AB2E 0000302D DFBF0000 03E00008 27BD0010 00000000 27BDFFB0 3C02005F"
        "FFB20030 2403000B FFB00010 0080902D 24502580 FFB10020 FFBF0040 00A0882D"
        "AE120004 3C04005F AC432580 24842340 AE110008 24080080 68C20007 6CC20000"
        "88C3000B 98C30008 B2020013 B602000C AA030017 BA030014 0200482D 24050001"
        "AFA00000 0000302D 0200382D 240A0080 0C10531C 0000582D 04430003 8E03001C"
        "1000000A 0000102D 24020001 14620007 0060102D 0240202D 0220282D 0C10A952"
        "24060002 8E03001C 0060102D DFBF0040 DFB20030 DFB10020 DFB00010 03E00008"
        "27BD0050 00000000 27BDFFD0 3C02005F FFB00010 2403000C 24502580 3C04005F"
        "FFBF0020 24842340 AC432580 24050001 AFA00000 0000302D 0200382D 24080080"
        "0200482D 240A0080 0C10531C 0000582D 04430002 8E02000C 0000102D DFBF0020"
        "DFB00010 03E00008 27BD0030 00000000 27BDFFD0 3C02005F FFB00010 2406000D"
        "24502580 FFBF0020 AE040004 3C03005F AC462580 24050001 24642340 AFA00000"
        "0000302D 0200382D 24080080 0200482D 240A0080 0C10531C 0000582D 04430002"
        "8E02000C 0000102D DFBF0020 DFB00010 03E00008 27BD0030"),

    0x0042EF88: (
        "03E00008 0080102D 27BDFFD0 FFB10010 FFB00000 0080882D 00A0802D 16000007"
        "FFBF0020 3C040059 3C060059 24849208 24C69218 0C0FFEB6 240501E1 0C10BBE2"
        "0220202D 2604FFFF 52000001 000001CD 00441821 0070001B 00001812 00701818"
        "00628023 0090202B 10800006 3C040059 3C060059 24849208 24C69228 0C0FFEB6"
        "240501ED 0200102D DFBF0020 DFB10010 DFB00000 03E00008 27BD0030 00000000"
        "03E00008 0004102B 3C020059 03E00008 24429230 00000000 03E00008 24021060"
        "3C020059 03E00008 24429238 00000000 3C020059 03E00008 24429240 00000000"
        "3C020059 03E00008 24429238 00000000 3C020059 03E00008 24429240 00000000"),

    0x003FAB60: (
        "27BDFFD0 FFBF0020 7FB10010 7FB00000 70808E28 1220000C 70A08628 8E240000"
        "10800004 0010143C 0C040AF8 00000000 0010143C 0002143F 18400004 72201628"
        "0C040B14 72202628 72201628 DFBF0020 7BB10010 7BB00000 03E00008 27BD0030"),

    0x003FABD0: (
        "27BDFFD0 FFBF0020 7FB10010 7FB00000 70808E28 1220000C 70A08628 8E240000"
        "10800004 0010143C 0C040AF8 00000000 0010143C 0002143F 18400004 72201628"
        "0C040B14 72202628 72201628 DFBF0020 7BB10010 7BB00000 03E00008 27BD0030"),

    0x003FAC40: (
        "27BDFFD0 FFBF0020 7FB10010 7FB00000 70808E28 1220000C 70A08628 8E240000"
        "10800004 0010143C 0C040AF8 00000000 0010143C 0002143F 18400004 72201628"
        "0C040B14 72202628 72201628 DFBF0020 7BB10010 7BB00000 03E00008 27BD0030"),
}

GR_STOCK = {}
for _b, _h in _GR_CAVE_STOCK_HEX.items():
    GR_STOCK.update(_stock_words(_b, _h))
GR_STOCK[GR_HOOK_TOGGLE] = GR_HOOK_TOGGLE_STOCK
GR_STOCK[GR_HOOK_DET] = GR_HOOK_DET_STOCK
GR_STOCK[GR_LOSC], GR_STOCK[GR_LOSC + 4] = GR_LOSC_STOCK
for _va in GR_CHECKLOS_CALLS:
    GR_STOCK[_va] = GR_CHECKLOS_STOCK
GR_STOCK[GR_HOOK_RFC] = GR_HOOK_RFC_STOCK
GR_STOCK[GR_HOOK_OK] = GR_HOOK_OK_STOCK
GR_STOCK[GR_HOOK_IDX] = GR_HOOK_IDX_STOCK
GR_STOCK[GR_HOOK_ARC] = GR_HOOK_ARC_STOCK
GR_STOCK[GR_HOOK_REP] = GR_HOOK_REP_STOCK


def selftest(gr_elf: bytes, js_elf: bytes):
    """Every stock word against the executable, no address twice. [] = pass."""
    bad = []
    for va, w in JS_STOCK.items():
        off = va - 0x100000 + 0x100
        if int.from_bytes(js_elf[off:off + 4], "little") != w:
            bad.append("js %08X" % va)
    for look, side in zip(LOOKS, ("squad", "enemies", "all", "all")):
        e = edits(look) + ai_edits(side)
        if len({va for va, *_ in e}) != len(e):
            bad.append("js duplicate VA")
        if any(va not in JS_STOCK for va, *_ in e):
            bad.append("js VA without a stock word")
    # Ghost Recon: VA = file offset + 0x100000 - 0x80
    gw = lambda va: int.from_bytes(gr_elf[va - 0x100000 + 0x80:va - 0x100000 + 0x84], "little")  # noqa: E731
    for va, w in GR_STOCK.items():
        if gw(va) != w:
            bad.append("gr %08X" % va)
    for look, t in GR_LOOK_TYPES.items():          # kGeneralEffectNames[type] is the effect the look names
        p = gw(0x0055F090 + 4 * t)
        name = gr_elf[p - 0x100000 + 0x80:].split(b"\0", 1)[0].decode("latin-1")
        if name != (ROUND_EFFECT if look == "round" else look):
            bad.append("gr effect type %d is %r" % (t, name))
    for look in GR_LOOK_TYPES:
        for side in ("off",) + AI_SIDES[1:]:
            for chance in AI_CHANCES:
                e = gr_edits(dict(gr_smoke=True, gr_smoke_look=look, gr_smoke_ai=side, gr_smoke_ai_chance=chance))
                if len({va for va, *_ in e}) != len(e):
                    bad.append("gr duplicate VA (%s %s %s)" % (look, side, chance))
                if any(va not in GR_STOCK or s != GR_STOCK[va] for va, _v, s, _n in e):
                    bad.append("gr VA without its stock word (%s %s %s)" % (look, side, chance))
    if gr_edits({"gr_smoke": False}):
        bad.append("gr edits with gr_smoke off")
    return bad

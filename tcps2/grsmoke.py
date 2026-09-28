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
    Anything else is created as before.

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

Caves: three unreferenced library routines (DMA/GS register save and
restore) at 0x00175678 (99 words), 0x00175808 (82) and 0x00175D58 (118), and
a thread body with the routine that would start it (0x00173908, 103; only
the starter forms the body's address, and nothing calls the starter) -- no
call, branch, pointer or address formation reaches any of them from outside
in the image or either overlay, and no other option writes them. Not yet
played.
"""

from __future__ import annotations

import re
import struct

from .grasm import assemble

CAVES = [(0x00175678, 0x00175804), (0x00175808, 0x00175950), (0x00175D58, 0x00175F30), (0x00173908, 0x00173AA4)]

HOOK_TOGGLE, HOOK_TOGGLE_STOCK = 0x003A631C, 0x0C0CD05C   # jal IsUsingItem (slot: addiu a0, s1, 0x1b4)
HOOK_DET, HOOK_DET_STOCK = 0x0037018C, 0x0C1263F4         # jal RSGameMessage::Create (a0 = 0x1ef)
LOSC, LOSC_STOCK = 0x0037AA80, (0x27BDFF50, 0xFFBF0050)   # LineOfSightClear's first two words
CHECKLOS = 0x003D3EF0
CHECKLOS_CALLS = (0x003D3884, 0x003D39C0, 0x003D3BDC, 0x003D3C50)
CHECKLOS_STOCK = 0x0C0F4FBC                               # jal CheckLineOfSight

FRAG, SMOKE = 4, 9                                        # projectile indices (EQUIP_PRJ.DIR order)
LOOKS = ("smoke_large_type1", "smoke_large_type2", "smoke_large_type3")
DURATION = 45                                             # s, the effect's life
ON, OFF = 2.0, DURATION - 5.0                             # the cloud blocks sight between these ages
RADIUS = 5.0
INVALID = -1.0e9                                          # a ring slot's time before any cloud

SYMS = dict(
    ISUSING=0x00334170, THROWN_VT=0x005A75B0,
    CREATE=0x00498FD0, ADD_STR=0x00125750, ADD_VEC=0x0014E0E0, ADD_US=0x00133B80, ADD_INT=0x00136A20,
    SEND=0x00125810, RELEASE=0x00124AE0, CONSTS=0x00124280, UPVEC=0x00245A60, SCENE=0x00122730,
    RESUME=0x00370408, CLOCK=0x00684768, DATAMGR=0x001245F0, LOOKTO=0x003D4A50, CHECKLOS=CHECKLOS, LOSC_BODY=LOSC + 8,
)


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
    nop
    jal   SCENE
    addiu s0, sp, 0x2a8             ; (delay) the caller's sp+0x248
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
sd_create:
    j     CREATE
    nop
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
             INV_HI=hex(_bits(INVALID) >> 16), INV_LO=hex(_bits(INVALID) & 0xFFFF))
    ring = "\n".join("    .word 0\n    .word 0\n    .word 0\n    .word %#x" % _bits(INVALID) for _ in range(8))
    data = SRC_DATA.replace("{RING}", ring).replace("{NAME}", "%s(%d)" % (look, DURATION))
    return [
        (0, SRC_BLOCKED.format(**k) + SRC_TOGGLE.format(**k)),
        (1, SRC_BLOCKED2.format(**k) + SRC_LOS),
        (2, SRC_DET.format(**k) + SRC_DET2.format(**k)),
        (3, SRC_CLEAR + SRC_OTHER + data),
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
    return edits(v.get("js_smoke_look", LOOKS[2])) if v.get("js_smoke") else []


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


_register()


def data_edits(v: dict) -> list:
    if not v.get("js_smoke"):
        return []
    from .model import FileEdit
    out = [FileEdit("smoke_prj", r"/SQUIRREL\.PRJ$", "GR.IMG", {}, "SQUIRREL.PRJ becomes the smoke grenade"),
           FileEdit("smoke_label", r"STRINGS\.TXT$", "GR.IMG", {}, "WPN_SMOKE = SMOKE")]
    kits = SMOKE_KITS.get(v.get("js_smoke_kits", "second"), ())
    if kits:
        out.append(FileEdit("smoke_kit", r"/(%s)\.KIT$" % "|".join(re.escape(k) for k in kits), "GR.IMG", {},
                            "%d kit(s) carry smoke grenades" % len(kits)))
    return out


def selftest(gr_elf: bytes, js_elf: bytes):
    """Every stock word against the executable, no address twice. [] = pass."""
    bad = []
    for va, w in JS_STOCK.items():
        off = va - 0x100000 + 0x100
        if int.from_bytes(js_elf[off:off + 4], "little") != w:
            bad.append("js %08X" % va)
    for look in LOOKS:
        e = edits(look)
        if len({va for va, *_ in e}) != len(e):
            bad.append("js duplicate VA")
        if any(va not in JS_STOCK for va, *_ in e):
            bad.append("js VA without a stock word")
    return bad

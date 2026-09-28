"""Shrapnel marks for Ghost Recon (SLUS-20613) and Jungle Storm (SLUS-20820).

Rainbow Six 3 gained an option that scatters fragment marks around a
grenade blast. Ghost Recon's explosions leave no mark at all: the blast
damages controllers and plays its effect, and the bullet-hole system only
ever hears about gunshots. This adds the marks.

Both detonation handlers -- IkeSimulationMgr::HandleDetonateProjectile
(grenades, 40 mm, rockets) and HandleDetonateExplosive (claymores, satchel
charges) -- call ExplosionData::IsDirectional once, with the ExplosionData
in $a0. That call is redirected to a routine which, before answering the
same question, traces N rays with the game's own line test
(RSSimRoom::FindLineCollision, flagged as a gunshot that ignores every
controller -- the same flags HandleDetonateProjectile uses for its own
floor test). Each ray that meets a wall, floor or ceiling puts a bullet
hole there through IkeEffectsMgr::DisplayBullethole, with the surface type
that PackWorldDamageFlags reports for that face, as HandleGunshot does for
a bullet. It then returns ExplosionData::m_bDirectional, which is all
IsDirectional did.

The rays leave from the blast moved 0.6 m clear of whatever it touched:
six 0.6 m line tests along the axes find a floor, wall or ceiling that
close, and the origin steps back from each (a grenade on the ground bursts
0.6 m above it, a 40 mm round on a wall 0.6 m out from it). Every second ray
flies in a direction picked uniformly over a sphere, 2.5x the blast radius
(clamped to 16 m), so walls, beams, fences and anything overhead take
marks; the others each aim at a point picked uniformly over a disc as wide
as the blast radius, reaching 1.5x that far so slopes still catch them. The
disc lies on the first surface straight below that origin -- one extra line
test, 40 m down -- so a grenade that bursts in the air, or high on a wall,
marks the ground under it; with nothing below, the disc sits 0.75 m below
the origin. (Until 2026-09-28 the origin was simply 0.75 m above the blast:
a round that burst on a wall then traced its downward probe along the wall
face, found the "ground" on the wall, and put every mark there.)

Marks can be drawn larger than a bullet's hole on the same surface.
DisplayBullethole picks a size per surface (0.4 m on dirt-like surfaces,
0.07-0.08 m on concrete, rock and metal) and hands it to
BulletHoleManagerPS2::AddOneBulletHole in $f13; that one call goes through
``scaled_add``, which multiplies the size by a word the shrapnel routine
sets for its own marks and puts back to 1.0 afterwards, so bullets are
unchanged. The impact is the bullet's for that surface -- dust, or sparks
and dust on hard surfaces, or a splash on water -- and every mark may play
the bullet's impact sound, which the game itself plays only on a random
share of hits. (An earlier
version spread the rays over a sphere, which sent half of them into the sky
in the open, and lifted a projectile's origin along the normal of its last
collision, which a direct impact need not have set.)

Blasts under 0.5 m radius (smoke, flashbangs, duds) make no marks. The
spread is seeded from the epicentre, so one blast always leaves the same
pattern.

The routine lives in ``sceWrite`` (GR 0x00416538, JS 0x0017EFD0, 704
bytes), which nothing in either executable calls or points at: the only
words in the Ghost Recon file naming that range are debug information past
the end of the loaded image, and Jungle Storm has none. ``findground``,
``scaled_add`` and the scale word sit at the end of sceReadlink (GR
0x00418950, JS 0x001813F0), likewise unreferenced. The number of rays
is one immediate (``addiu s1, zero, N``), so the slider is that word.

The RSLineCollisionInfo layout -- hit point at +0x10, normal at +0x04,
face at +0x3C, room at +0x40 -- is the one HandleGunshot reads for its
world-hit message; FindLineCollision initialises +0x34..+0x4C itself in
both games, so the routine does not run the constructor. Every encoding
was assembled by ``grasm`` and matches a hand-checked prototype word for
word; the routine was run in an interpreter against stubbed engine calls
(ray count, seed, radius gate, register and stack contract), not in a game.
"""

from __future__ import annotations

from .grasm import assemble

GAMES = {
    "gr": dict(
        CAVE=0x00416538, CAVE_END=0x004167F8,  # sceWrite, unreferenced
        FLC=0x004D8540,        # RSSimRoom::FindLineCollision(line, info, f, ctrl, Ui, Ui, Ui, b)
        PWDF=0x00393D50,       # PackWorldDamageFlags(face, room, bool)
        DB=0x00249610,         # IkeEffectsMgr::DisplayBullethole(pos, nrm, type, node)
        VEC=0x0C,              # RSLine3's vector (SetVector stores at +0xC)
        # HandleDetonateProjectile 0x003925E0, frame 0x280
        HOOK_P=0x00392A14, POS_P=0x1D8, CTRL_P="s0",
        # HandleDetonateExplosive 0x00392DA0, frame 0x200
        HOOK_E=0x00393178, POS_E=0x188, CTRL_E="s2",
        STOCK_HOOK=0x0C0E4B0C,  # jal ExplosionData::IsDirectional (0x00392C30)
        HELPER=0x00418950, HELPER_END=0x00418A28,   # end of sceReadlink
        SPH=0x00417F80, SPH_END=0x004181EC,         # sceMount, unreferenced
        SPH_STOCK=(
            "27bdff20 ffb00040 ffb700b0 0080802d ffb600a0 00c0b82d ffb30070 00e0b02d"
            "ffb10050 00a0982d ffbe00c0 0100882d ffb20060 24040014 ffbf00d0 3c1e005f"
            "ffb50090 27d2e100 0c10563e ffb40080 3c030057 8c62e1c0 54400004 92020000"
            "0c10567e 00000000 92020000 0000282d 00021e00 1060000f a242000c 2a270401"
            "24a50001 00000000 28a20400 1040000a 02051021 02452021 90430000 a083000c"
            "00031e00 5460fff8 24a50001 10000003 24020400 2a270401 24020400 50a20001"
            "a240040b 92620000 0000282d 00021e00 1060000c a242040c 2646040c 24a50001"
            "28a20400 10400007 02651021 00c52021 90430000 a0830000 00031e00 5460fff8"
            "24a50001 24020400 50a20001 a240080b 14e00005 00000000 0c10564a 00000000"
            "10000046 2402fff9 1a20000f 0000282d 2646080c 27b30030 3c15005f 3c14005f"
            "02c51021 00c52021 90430000 24a50001 00b1102a a0830000 1440fff9 00000000"
            "10000005 ae510c10 27b30030 3c15005f 3c14005f ae510c10 24020001 ae570c0c"
            "27a40010 afa20014 27d0e100 afa00018 2694ed40 0c1046b8 afa00024 0040882d"
            "0200202d 24020004 ae530004 ae420008 24050c14 0c1050e0 ae510000 26a4f3c0"
            "0200382d afa00000 24050014 0000302d 24080c14 0280482d 240a0004 0c10531c"
            "0000582d 04410007 3c022000 0c1046bc 0220202d 0c10564a 00000000 1000000f"
            "2402fff5 02821025 0c10564a 8c500000 16000005 00000000 0c1046bc 0220202d"
            "10000006 2402fff5 0c1046c8 0220202d 0c1046bc 0220202d 8fa20030 dfbf00d0"
            "dfbe00c0 dfb700b0 dfb600a0 dfb50090 dfb40080 dfb30070 dfb20060 dfb10050"
            "dfb00040 03e00008 27bd00e0"),
        DB_HOOK=0x002497C4, DB_HOOK_STOCK=0x0C11B6B0,  # DisplayBullethole: jal AddOneBulletHole
        ADDONE=0x0046DAC0,
        FX=0x00416B48, FX_END=0x00416D24,      # sceIoctl2, unreferenced
        EFFMGR=0x005E76A8,                     # mIIkeEffectsMgr
        SNDMGR=0x005E7AE0,                     # mIIkeSoundMgr
        EMPS2=0x00630D68,                      # EffMgrPS2 instance
        RIPOFF=0x6274,                         # EffMgrPS2 -> WaterRippleManagerPS2
        RIPPLE=0x0046B410,                     # WaterRippleManagerPS2::AddOneWaterRipple
        FX_STOCK=(
            "27bdff30 ffb700b0 ffb50090 0100b82d ffb40080 00a0a82d ffb30070 0120a02d"
            "ffb00040 00e0982d ffb600a0 00c0802d ffb20060 3c16005f ffb10050 ffbf00c0"
            "0c10551e 26d1e100 0040902d 0c10563e 2404001a 3c020057 8c43e1c0 14600003"
            "00000000 0c10567e 00000000 12400004 00000000 8e420004 14400005 2e620401"
            "0c10564a 00000000 10000049 2402fff7 10400003 2e820401 14400005 00000000"
            "0c10564a 00000000 10000041 2402ffea 16000003 0200282d 10000004 ae20041c"
            "26240014 0c100e4c 0260302d 8e420000 24030001 ae350010 27a40010 ae22000c"
            "26d0e100 ae33041c afa30014 afa00018 0c1046b8 afa00024 0040902d 24030004"
            "27a20030 ae340418 ae220004 0200202d ae230008 24050420 ae370414 0c1050e0"
            "ae320000 3c02005f 3c04005f 2451ed40 2484f3c0 0200382d afa00000 2405001a"
            "0000302d 24080420 0220482d 240a0004 0c10531c 0000582d 04410007 3c022000"
            "0c1046bc 0240202d 0c10564a 00000000 1000000f 2402fff5 02221025 0c10564a"
            "8c500000 16000005 00000000 0c1046bc 0240202d 10000006 2402fff5 0c1046c8"
            "0240202d 0c1046bc 0240202d 8fa20030 dfbf00c0 dfb700b0 dfb600a0 dfb50090"
            "dfb40080 dfb30070 dfb20060 dfb10050 dfb00040 03e00008 27bd00d0"),
        HELPER_STOCK=(
            "24020001 afa00018 afa20014 27a40010 0c1046b8 afa00024 0040882d ae530004"
            "24020004 ae510000 ae420008 26c4f3c0 26e7e100 24050019 afa00000 0000302d"
            "2408080c 0200482d 240a0004 0c10531c 0000582d 04410007 3c022000 0c1046bc"
            "0220202d 0c10564a 00000000 1000000f 2402fff5 02021025 0c10564a 8c500000"
            "16000005 00000000 0c1046bc 0220202d 10000006 2402fff5 0c1046c8 0220202d"
            "0c1046bc 0220202d 8fa20030 dfbf00c0 dfb700b0 dfb600a0 dfb50090 dfb40080"
            "dfb30070 dfb20060 dfb10050 dfb00040 03e00008 27bd00d0"),
    ),
    "js": dict(
        CAVE=0x0017EFD0, CAVE_END=0x0017F290,
        FLC=0x004C40E0,
        PWDF=0x003716A0,
        DB=0x00245E40,
        VEC=0x10,              # Jungle Storm's SetVector (0x00370500) stores at +0x10
        # HandleDetonateProjectile 0x0036FEA0, frame 0x270
        HOOK_P=0x003702B0, POS_P=0x238, CTRL_P="s4",
        # HandleDetonateExplosive 0x003705E0, frame 0x220
        HOOK_E=0x00370994, POS_E=0x208, CTRL_E="s2",
        STOCK_HOOK=0x0C073684,  # jal IsDirectional (0x001CDA10)
        HELPER=0x001813F0, HELPER_END=0x001814E8,
        SPH=0x00180A40, SPH_END=0x00180CAC,         # sceMount again
        SPH_STOCK=(
            "27bdff20 ffb00040 ffb700b0 0080802d ffb600a0 00c0b82d ffb30070 00e0b02d"
            "ffb10050 00a0982d ffbe00c0 0100882d ffb20060 24040014 ffbf00d0 3c1e0061"
            "ffb50090 27d27000 0c05f8cc ffb40080 3c030057 8c624fec 54400004 92020000"
            "0c05f918 00000000 92020000 0000282d 00021e00 1060000f a242000c 2a270401"
            "24a50001 00000000 28a20400 1040000a 02051021 02452021 90430000 a083000c"
            "00031e00 5460fff8 24a50001 10000003 24020400 2a270401 24020400 50a20001"
            "a240040b 92620000 0000282d 00021e00 1060000c a242040c 2646040c 24a50001"
            "28a20400 10400007 02651021 00c52021 90430000 a0830000 00031e00 5460fff8"
            "24a50001 24020400 50a20001 a240080b 14e00005 00000000 0c05f8d8 00000000"
            "10000046 2402fff9 1a20000f 0000282d 2646080c 27b30030 3c150062 3c140061"
            "02c51021 00c52021 90430000 24a50001 00b1102a a0830000 1440fff9 00000000"
            "10000005 ae510c10 27b30030 3c150062 3c140061 ae510c10 24020001 ae570c0c"
            "27a40010 afa20014 27d07000 afa00018 26947c40 0c05e8b8 afa00024 0040882d"
            "0200202d 24020004 ae530004 ae420008 24050c14 0c05f324 ae510000 26a48700"
            "0200382d afa00000 24050014 0000302d 24080c14 0280482d 240a0004 0c05f5aa"
            "0000582d 04410007 3c022000 0c05e8bc 0220202d 0c05f8d8 00000000 1000000f"
            "2402fff5 02821025 0c05f8d8 8c500000 16000005 00000000 0c05e8bc 0220202d"
            "10000006 2402fff5 0c05e8c8 0220202d 0c05e8bc 0220202d 8fa20030 dfbf00d0"
            "dfbe00c0 dfb700b0 dfb600a0 dfb50090 dfb40080 dfb30070 dfb20060 dfb10050"
            "dfb00040 03e00008 27bd00e0"),
        DB_HOOK=0x00245F8C, DB_HOOK_STOCK=0x0C10C688,  # delay slot: mov.s f13, f20 (the size)
        ADDONE=0x00431A20,
        FX=0x0017F608, FX_END=0x0017F7E4,
        EFFMGR=0x00627570, SNDMGR=0x006279B0, EMPS2=0x0067D128,
        RIPOFF=0x626C, RIPPLE=0x0042F210,
        FX_STOCK=(
            "27bdff30 ffb700b0 ffb50090 0100b82d ffb40080 00a0a82d ffb30070 0120a02d"
            "ffb00040 00e0982d ffb600a0 00c0802d ffb20060 3c160061 ffb10050 ffbf00c0"
            "0c05f7ae 26d17000 0040902d 0c05f8cc 2404001a 3c020057 8c434fec 14600003"
            "00000000 0c05f918 00000000 12400004 00000000 8e420004 14400005 2e620401"
            "0c05f8d8 00000000 10000049 2402fff7 10400003 2e820401 14400005 00000000"
            "0c05f8d8 00000000 10000041 2402ffea 16000003 0200282d 10000004 ae20041c"
            "26240014 0c05a8d6 0260302d 8e420000 24030001 ae350010 27a40010 ae22000c"
            "26d07000 ae33041c afa30014 afa00018 0c05e8b8 afa00024 0040902d 24030004"
            "27a20030 ae340418 ae220004 0200202d ae230008 24050420 ae370414 0c05f324"
            "ae320000 3c020061 3c040062 24517c40 24848700 0200382d afa00000 2405001a"
            "0000302d 24080420 0220482d 240a0004 0c05f5aa 0000582d 04410007 3c022000"
            "0c05e8bc 0240202d 0c05f8d8 00000000 1000000f 2402fff5 02221025 0c05f8d8"
            "8c500000 16000005 00000000 0c05e8bc 0240202d 10000006 2402fff5 0c05e8c8"
            "0240202d 0c05e8bc 0240202d 8fa20030 dfbf00c0 dfb700b0 dfb600a0 dfb50090"
            "dfb40080 dfb30070 dfb20060 dfb10050 dfb00040 03e00008 27bd00d0"),
        HELPER_STOCK=(
            "240203ff 02a0202d 0046800a ae550010 0200282d 0c05f324 ae50000c 26907c40"
            "24020001 afa00018 afa20014 27a40010 0c05e8b8 afa00024 0040882d ae530004"
            "24020004 ae510000 ae420008 26c48700 26e77000 24050019 afa00000 0000302d"
            "2408080c 0200482d 240a0004 0c05f5aa 0000582d 04410007 3c022000 0c05e8bc"
            "0220202d 0c05f8d8 00000000 1000000f 2402fff5 02021025 0c05f8d8 8c500000"
            "16000005 00000000 0c05e8bc 0220202d 10000006 2402fff5 0c05e8c8 0220202d"
            "0c05e8bc 0220202d 8fa20030 dfbf00c0 dfb700b0 dfb600a0 dfb50090 dfb40080"
            "dfb30070 dfb20060 dfb10050 dfb00040 03e00008 27bd00d0"),
    ),
}

FRAME = 0x100
DEFAULT_N = 12
MAX_N = 32
NLIFT_HI = 0xBF40       # -0.75 m: with no ground found, the disc sits this far below the origin
REACH_HI = 0x47A0       # 2^15 x 2.5: rays in any direction fly 2.5x the blast radius
MINR_HI = 0x3F00        # 0.5 m: below this blast radius, no marks
MAXR_HI = 0x4180        # 16.0 m: disc radius clamp
#: mark size multiplier -> the float's high half
SIZES = {"1": 0x3F80, "1.5": 0x3FC0, "2": 0x4000, "3": 0x4040}
SOUNDS = 32             # rays that may play the impact sound (the game rolls for each)

SRC = r"""
; ---------------------------------------------------------------- entries
entry_p:                            ; from HandleDetonateProjectile
    addiu   sp, sp, -{FRAME}
    sd      ra, 0x50(sp)
    addiu   a1, sp, {FRAME}+{POS_P}  ; epicentre, pulled 2 cm back along the flight path
    b       core
    lw      t0, 0x38({CTRL_P})       ; RSSimController::GetSimRoom
entry_e:                            ; from HandleDetonateExplosive
    addiu   sp, sp, -{FRAME}
    sd      ra, 0x50(sp)
    addiu   a1, sp, {FRAME}+{POS_E}  ; explosive's world position
    lw      t0, 0x38({CTRL_E})
; ---------------------------------------------------------------- core
core:
    sq      s0, 0x00(sp)
    sq      s1, 0x10(sp)
    sq      s2, 0x20(sp)
    sq      s3, 0x30(sp)
    sq      s4, 0x40(sp)
    move    s4, a0                  ; ExplosionData*
    beqz    t0, done
    move    s2, t0                  ; RSSimRoom*
    lwc1    f0, 0x0c(s4)            ; ExplosionData::GetBlastRadius
    lui     at, {MINR_HI}
    mtc1    at, f1
    nop
    c.lt.s  f0, f1
    nop
    bc1t    done                    ; radius < MIN: not a fragmenting blast
    lui     at, {MAXR_HI}
    mtc1    at, f1
    nop
    c.lt.s  f1, f0
    nop
    bc1f    reach_ok
    nop
    mov.s   f0, f1                  ; clamp
reach_ok:
    lui     at, 0x3800              ; 2^-15: a sample unit in metres
    mtc1    at, f1
    nop
    mul.s   f0, f0, f1
    swc1    f0, 0x5c(sp)
    lw      t1, 0(a1)               ; seed = hash of the epicentre's float bits
    lw      t2, 4(a1)
    lw      t3, 8(a1)
    sll     t4, t2, 11
    srl     t5, t2, 21
    or      t4, t4, t5
    xor     s3, t1, t4
    sll     t4, t3, 22
    srl     t5, t3, 10
    or      t4, t4, t5
    xor     s3, s3, t4
    bnez    s3, seeded
    nop
    lui     s3, 0x9e37
seeded:
    move    a0, s2                  ; room; a1 is still the epicentre
    jal     {CLEAR}                 ; ray origin: the blast, 0.6 m clear of floor and walls
    addiu   a2, sp, 0x60
    move    a0, s2                  ; room
    jal     findground              ; how far below the ray origin the ground is
    addiu   a1, sp, 0x60            ; ray origin
    swc1    f0, 0x58(sp)            ; dz, the same for every ray
    lui     at, %hi(shr_scale)
    lui     t1, {SCALE_HI}
    sw      t1, %lo(shr_scale)(at)  ; the marks' size multiplier
count:
    addiu   s1, zero, {N}           ; <- marks per explosion (the slider)
    move    s0, zero
loop:
    beq     s0, s1, done
    nop
    andi    t0, s0, 1
    beqz    t0, pick                ; even rays: the disc on the ground
    move    a0, s3
    jal     {SPH}                   ; odd rays: any direction, as far as the blast reaches
    lwc1    f12, 0x5c(sp)           ; blast radius in sample units
    b       aim
    move    s3, v0                  ; the seed moves on
pick:                               ; uniform point in the unit disc, by rejection
    sll     t4, s3, 13              ; xorshift32
    xor     s3, s3, t4
    srl     t4, s3, 17
    xor     s3, s3, t4
    sll     t4, s3, 5
    xor     s3, s3, t4
    sra     t5, s3, 16              ; x  (-32768..32767)
    sll     t6, s3, 16
    sra     t6, t6, 16              ; y
    mtc1    t5, f2
    mtc1    t6, f3
    cvt.s.w f2, f2
    cvt.s.w f3, f3
    mul.s   f5, f2, f2
    mul.s   f6, f3, f3
    add.s   f5, f5, f6              ; |v|^2, in units of 32768^2
    lui     at, 0x4e80              ; 2^30 = 32768^2
    mtc1    at, f6
    nop
    c.lt.s  f6, f5
    nop
    bc1t    pick                    ; outside the disc
    nop
    lwc1    f7, 0x5c(sp)
    mul.s   f2, f2, f7              ; dx, metres
    mul.s   f3, f3, f7              ; dy
    lwc1    f4, 0x58(sp)            ; dz: down to the disc
    mul.s   f5, f2, f2
    mul.s   f6, f3, f3
    add.s   f5, f5, f6
    mul.s   f6, f4, f4
    add.s   f5, f5, f6
    sqrt.s  f6, f5                  ; distance to the target point (>= the lift)
    nop
    nop
    div.s   f2, f2, f6              ; unit direction
    div.s   f3, f3, f6
    div.s   f4, f4, f6
    lui     at, 0x3fc0              ; reach 1.5x the target distance
    mtc1    at, f8
    nop
    mul.s   f12, f6, f8             ; max distance
aim:
    lw      t1, 0x60(sp)            ; RSLine3: point
    sw      t1, 0x70(sp)
    lw      t1, 0x64(sp)
    sw      t1, 0x74(sp)
    lw      t1, 0x68(sp)
    sw      t1, 0x78(sp)
    swc1    f2, 0x70+{VEC}(sp)      ; RSLine3: vector
    swc1    f3, 0x74+{VEC}(sp)
    swc1    f4, 0x78+{VEC}(sp)
    move    a0, s2                  ; room
    addiu   a1, sp, 0x70            ; &line
    addiu   a2, sp, 0x90            ; &RSLineCollisionInfo
    move    a3, zero                ; no shooter
    addiu   t0, zero, 0x81a         ; kIsGunshot | kLineIgnoreAllControllers
    addiu   t1, zero, 1             ; kGunshotTransparent
    move    t2, zero
    jal     {FLC}
    move    t3, zero
    andi    v0, v0, 0xff
    beqz    v0, next
    lw      a0, 0xcc(sp)            ; info+0x3c  RSCollisionFace*
    beqz    a0, next
    move    a2, zero
    jal     {PWDF}                  ; (face, room, false) -> (type<<8)|roomID
    lw      a1, 0xd0(sp)            ; info+0x40  RSSimRoom*
    sw      v0, 0x6c(sp)            ; kept for the impact effect
    srl     a3, v0, 8
    andi    a3, a3, 0x7f            ; surface type, as HandleDisplayBullethole extracts it
    move    a0, zero                ; the effects manager is never read
    addiu   a1, sp, 0xa0            ; info+0x10  hit point
    addiu   a2, sp, 0x94            ; info+0x04  hit normal
    jal     {DB}
    move    t0, zero                ; RSNode* is never read
    addiu   a0, sp, 0xa0            ; info+0x10  hit point
    addiu   a1, sp, 0x94            ; info+0x04  hit normal
    lw      a2, 0x6c(sp)            ; PackWorldDamageFlags result
    jal     {FX}                    ; the bullet's impact effect (and sound)
    sltiu   a3, s0, {SND}           ; sound only for the first SND rays
next:
    b       loop
    addiu   s0, s0, 1
done:
    lui     at, %hi(shr_scale)
    lui     t1, 0x3f80
    sw      t1, %lo(shr_scale)(at)  ; bullets keep their own size
    lbu     v0, 4(s4)               ; what IsDirectional would have returned
    ld      ra, 0x50(sp)
    lq      s0, 0x00(sp)
    lq      s1, 0x10(sp)
    lq      s2, 0x20(sp)
    lq      s3, 0x30(sp)
    lq      s4, 0x40(sp)
    jr      ra
    addiu   sp, sp, {FRAME}
"""


HELPER_SRC = r"""
shr_scale:
    .word   0x3f800000              ; mark size multiplier: 1.0 except while a blast marks
scaled_add:                         ; jal from DisplayBullethole in place of AddOneBulletHole
    lui     at, %hi(shr_scale)
    lwc1    f0, %lo(shr_scale)(at)
    nop
    mul.s   f13, f13, f0            ; the hole's size
    j       {ADDONE}
    nop
findground:                         ; a0 = room, a1 = &ray origin -> f0 = dz to the disc
    addiu   sp, sp, -0x90
    sd      ra, 0x80(sp)
    sq      s0, 0x70(sp)
    lw      t1, 0(a1)
    lw      t2, 4(a1)
    lw      s0, 8(a1)               ; origin z, bits
    sw      t1, 0x00(sp)            ; RSLine3: point
    sw      t2, 0x04(sp)
    sw      s0, 0x08(sp)
    sw      zero, {VEC}(sp)         ; RSLine3: vector, straight down
    sw      zero, {VEC}+4(sp)
    lui     t1, 0xbf80
    sw      t1, {VEC}+8(sp)
    addiu   a1, sp, 0x00
    addiu   a2, sp, 0x20            ; RSLineCollisionInfo
    move    a3, zero                ; no shooter
    addiu   t0, zero, 0x81a         ; kIsGunshot | kLineIgnoreAllControllers
    addiu   t1, zero, 1             ; kGunshotTransparent
    move    t2, zero
    lui     at, 0x4220              ; 40 m
    mtc1    at, f12
    jal     {FLC}
    move    t3, zero
    andi    v0, v0, 0xff
    beqz    v0, fg_none
    lwc1    f0, 0x38(sp)            ; hit point z (info+0x18)
    mtc1    s0, f1
    lui     at, 0xbe80              ; -0.25
    sub.s   f0, f0, f1              ; dz = ground - origin
    mtc1    at, f1
    nop
    c.lt.s  f1, f0                  ; less than 0.25 m below the origin: under an overhang
    nop
    bc1f    fg_out
    nop
fg_none:
    lui     at, {NLIFT_HI}
    mtc1    at, f0                  ; nothing below: aim at the blast's own height
    nop
fg_out:
    ld      ra, 0x80(sp)
    lq      s0, 0x70(sp)
    jr      ra
    addiu   sp, sp, 0x90
"""


SRC_FX = r"""
; The tail of IkeEffectsMgr::HandleDisplayBullethole (GR 0x249FF8.., JS 0x245540..):
; what a bullet's world hit plays after its hole.
;   a0 = &hit point, a1 = &hit normal, a2 = PackWorldDamageFlags result,
;   a3 > 0: also play the surface's impact sound
fx:
    addiu   sp, sp, -0x70
    sd      ra, 0x50(sp)
    sq      s0, 0x00(sp)
    sq      s1, 0x10(sp)
    sq      s2, 0x20(sp)
    move    s0, a0                  ; hit point
    move    s1, a1                  ; hit normal
    srl     s2, a2, 8
    andi    s2, s2, 0x7f            ; surface type
    blez    a3, effect
    andi    a3, a2, 0xff            ; room id
    lui     t0, %hi({SNDMGR})
    lw      a0, %lo({SNDMGR})(t0)   ; IIkeSoundMgr
    beqz    a0, effect
    move    a1, s2
    lw      t9, 0(a0)
    lui     at, 0x3dcc
    ori     at, at, 0xcccd
    mtc1    at, f12                 ; 0.1
    lw      t9, 0x48(t9)            ; PlayBulletHit(type, &pos, room, 0.1)
    jalr    t9
    move    a2, s0
effect:
    lui     t0, %hi({EFFMGR})
    lw      a0, %lo({EFFMGR})(t0)   ; IIkeEffectsMgr
    beqz    a0, out
    addiu   t1, s2, -9
    sltiu   at, t1, 2
    bnez    at, water               ; 9, 10
    addiu   t1, s2, -12
    sltiu   at, t1, 5
    bnez    at, sparks              ; 12..16
    addiu   t1, s2, -4
    sltiu   at, t1, 2
    bnez    at, sparks              ; 4, 5
    addiu   t1, s2, -2
    bnez    t1, dust                ; anything else but 2
    nop
sparks:                             ; AddParticleEffect(pos, normal, 31, 0, 0, 1, 0,0,0,0,0,0, false)
    lw      t9, 0(a0)
    move    a1, s0
    move    a2, s1
    addiu   a3, zero, 0x1f
    move    t0, zero
    move    t1, zero
    move    t2, zero
    lui     at, 0x3f80
    mtc1    at, f12
    mtc1    zero, f13
    mtc1    zero, f14
    mtc1    zero, f15
    mtc1    zero, f16
    mtc1    zero, f17
    mtc1    zero, f18
    lw      t9, 0xac(t9)
    jalr    t9
    nop
    b       dust                    ; and the dust puff a bullet leaves on softer ground
    nop
water:                              ; ripple 5 cm above the hit, then the splash on it
    lui     t0, %hi({EMPS2})
    lw      v0, %lo({EMPS2})(t0)    ; EffMgrPS2
    lw      a0, {RIPOFF}(v0)        ; WaterRippleManagerPS2
    beqz    a0, splash
    lwc1    f0, 0(s0)
    lwc1    f1, 4(s0)
    lwc1    f2, 8(s0)
    lui     at, 0x3d4c
    ori     at, at, 0xcccd
    mtc1    at, f3                  ; 0.05
    nop
    add.s   f2, f2, f3
    swc1    f0, 0x30(sp)
    swc1    f1, 0x34(sp)
    swc1    f2, 0x38(sp)
    lui     at, 0x3f80
    sw      zero, 0x40(sp)
    sw      zero, 0x44(sp)
    sw      at, 0x48(sp)            ; (0, 0, 1)
    addiu   a1, sp, 0x30
    addiu   a2, sp, 0x40
    lui     at, 0x3f00
    mtc1    at, f12                 ; 0.5
    nop
    jal     {RIPPLE}                ; AddOneWaterRipple(pos, up, 0.5, 0.5)
    mov.s   f13, f12
splash:
    move    a1, s0
    b       billboard
    addiu   a2, zero, 8
dust:                               ; the puff sits half a metre above the hit
    lwc1    f0, 0(s0)
    lwc1    f1, 4(s0)
    lwc1    f2, 8(s0)
    lui     at, 0x3f00
    mtc1    at, f3                  ; 0.5
    nop
    add.s   f2, f2, f3
    swc1    f0, 0x30(sp)
    swc1    f1, 0x34(sp)
    swc1    f2, 0x38(sp)
    addiu   a1, sp, 0x30
    addiu   a2, zero, 7
billboard:                          ; AddBillboardEffect(pos, type, 0, 0, 1.0, 0.0)
    lui     t0, %hi({EFFMGR})
    lw      a0, %lo({EFFMGR})(t0)
    lw      t9, 0(a0)
    move    a3, zero
    move    t0, zero
    lui     at, 0x3f80
    mtc1    at, f12
    mtc1    zero, f13
    lw      t9, 0xb0(t9)
    jalr    t9
    nop
out:
    ld      ra, 0x50(sp)
    lq      s0, 0x00(sp)
    lq      s1, 0x10(sp)
    lq      s2, 0x20(sp)
    jr      ra
    addiu   sp, sp, 0x70
"""


SPH_SRC = r"""
sphdir:                             ; a0 = seed, f12 = blast radius * 2^-15
                                    ; -> v0 = seed, f2..f4 = unit direction, f12 = reach
sd_pick:                            ; uniform point in the unit ball, by rejection
    sll     t4, a0, 13              ; xorshift32
    xor     a0, a0, t4
    srl     t4, a0, 17
    xor     a0, a0, t4
    sll     t4, a0, 5
    xor     a0, a0, t4
    sra     t5, a0, 16              ; x
    sll     t6, a0, 16
    sra     t6, t6, 16              ; y
    sll     t4, a0, 13
    xor     a0, a0, t4
    srl     t4, a0, 17
    xor     a0, a0, t4
    sll     t4, a0, 5
    xor     a0, a0, t4
    sra     t7, a0, 16              ; z
    mtc1    t5, f2
    mtc1    t6, f3
    mtc1    t7, f4
    cvt.s.w f2, f2
    cvt.s.w f3, f3
    cvt.s.w f4, f4
    mul.s   f5, f2, f2
    mul.s   f6, f3, f3
    mul.s   f7, f4, f4
    add.s   f5, f5, f6
    add.s   f5, f5, f7              ; |v|^2, in units of 32768^2
    lui     at, 0x4e80              ; 2^30
    mtc1    at, f6
    nop
    c.lt.s  f6, f5
    nop
    bc1t    sd_pick                 ; outside the ball
    lui     at, 0x4b00              ; 2^23: too short to normalise well
    mtc1    at, f6
    nop
    c.lt.s  f5, f6
    nop
    bc1t    sd_pick
    nop
    sqrt.s  f6, f5
    nop
    nop
    div.s   f2, f2, f6              ; unit direction
    div.s   f3, f3, f6
    div.s   f4, f4, f6
    lui     at, {REACH_HI}          ; 2^15 x 2.5: back to metres, fragments fly past the blast
    mtc1    at, f7
    nop
    mul.s   f12, f12, f7            ; reach: 2.5 x the blast radius
    jr      ra
    move    v0, a0
clearance:                          ; a0 = room, a1 = &blast, a2 = &out
                                    ; out = the blast moved 0.6 m clear of any surface met
                                    ; within 0.6 m along the six axes (floor, wall, ceiling)
    addiu   sp, sp, -0xd0
    sq      s0, 0x80(sp)
    sq      s1, 0x90(sp)
    sq      s2, 0xa0(sp)
    sq      s3, 0xb0(sp)
    sd      ra, 0xc0(sp)
    move    s0, a0                  ; room
    move    s1, a2                  ; out
    move    s3, a1                  ; blast
    lw      t1, 0(a1)
    sw      t1, 0(s1)
    lw      t1, 4(a1)
    sw      t1, 4(s1)
    lw      t1, 8(a1)
    sw      t1, 8(s1)
    move    s2, zero                ; axis: 0 +x, 1 -x, 2 +y, 3 -y, 4 +z, 5 -z
cl_loop:
    lw      t1, 0(s3)               ; RSLine3: point = the blast
    sw      t1, 0(sp)
    lw      t1, 4(s3)
    sw      t1, 4(sp)
    lw      t1, 8(s3)
    sw      t1, 8(sp)
    sw      zero, {VEC}(sp)         ; RSLine3: vector = the axis
    sw      zero, {VEC}+4(sp)
    sw      zero, {VEC}+8(sp)
    srl     t2, s2, 1
    sll     t2, t2, 2
    addu    t2, t2, sp
    andi    t3, s2, 1
    beqz    t3, cl_dir
    lui     t4, 0x3f80
    lui     t4, 0xbf80
cl_dir:
    sw      t4, {VEC}(t2)
    move    a0, s0
    addiu   a1, sp, 0
    addiu   a2, sp, 0x20            ; RSLineCollisionInfo
    move    a3, zero                ; no shooter
    addiu   t0, zero, 0x81a         ; kIsGunshot | kLineIgnoreAllControllers
    addiu   t1, zero, 1             ; kGunshotTransparent
    move    t2, zero
    lui     at, 0x3f19
    ori     at, at, 0x999a          ; 0.6 m
    mtc1    at, f12
    jal     {FLC}
    move    t3, zero
    andi    v0, v0, 0xff
    beqz    v0, cl_next
    srl     t2, s2, 1               ; (delay)
    sll     t2, t2, 2
    addiu   t5, sp, 0x30            ; info+0x10: hit point
    addu    t5, t5, t2
    lwc1    f0, 0(t5)               ; the hit, on this axis
    addu    t6, s1, t2
    lwc1    f2, 0(t6)               ; out, on this axis
    lui     at, 0x3f19
    ori     at, at, 0x999a
    mtc1    at, f1
    andi    t3, s2, 1
    bnez    t3, cl_neg
    nop
    sub.s   f0, f0, f1              ; a surface ahead: stay 0.6 m short of it
    c.lt.s  f0, f2
    nop
    bc1f    cl_next
    nop
    b       cl_store
    nop
cl_neg:
    add.s   f0, f0, f1              ; a surface behind: stay 0.6 m past it
    c.lt.s  f2, f0
    nop
    bc1f    cl_next
    nop
cl_store:
    swc1    f0, 0(t6)
cl_next:
    addiu   s2, s2, 1
    slti    t1, s2, 6
    bnez    t1, cl_loop
    nop
    ld      ra, 0xc0(sp)
    lq      s0, 0x80(sp)
    lq      s1, 0x90(sp)
    lq      s2, 0xa0(sp)
    lq      s3, 0xb0(sp)
    jr      ra
    addiu   sp, sp, 0xd0
"""


def _stock_words(base, hexwords):
    digits = "".join(hexwords.split())
    if len(digits) % 8:
        raise ValueError("stock table is not a whole number of words")
    return {base + i // 2: int(digits[i:i + 8], 16)
            for i in range(0, len(digits), 8)}


#: sceWrite as shipped, all 176 words, and the two IsDirectional calls
GR_STOCK = _stock_words(0x00416538, (
    "27bdff20 ffb50090 ffb10050 00c0a82d ffb700b0 00a0882d ffb20060 3c17005f"
    "ffb00040 26f2e100 ffbf00d0 ffbe00c0 ffb600a0 ffb40080 0c10551e ffb30070"
    "0040802d 0c10563e 24040003 3c030057 8c62e1c0 14400005 00000000 0c10564a"
    "00000000 1000008a 2402ffff 12000004 00000000 8e160004 56c00005 8e030000"
    "0c10564a 00000000 10000081 2402fff7 3c02005f 2442f1c0 24040001 ae43000c"
    "02021023 afa40014 00021103 ae42002c 27a40010 ae550014 ae510010 afa00018"
    "0c1046b8 afa00024 0040a02d 24030004 27a20030 ae430008 ae420004 32c28000"
    "10400024 aef4e100 3c130057 0c1046c8 8e64e1cc 3c070057 0000302d 8ce3e140"
    "2402ffff 14620008 3230000f 8ee3e100 3c1e005f 00031023 ace3e140 10000011"
    "aee2e100 00000000 3c1e005f 24c60001 28c20020 1040000b 00061080 24e3e140"
    "00432821 2404ffff 8ca20000 1444fff8 24c60001 8e420000 00021823 aca20000"
    "ae430000 0c1046c0 8e64e1cc 10000003 00000000 3230000f 3c1e005f 16000003"
    "00111102 10000004 0000802d 2623fff0 00021100 00438023 02b0182a 3c132000"
    "02d31024 14400004 02a3800b 02a0282d 0c1050e0 0220202d 02338825 ae500018"
    "1a00000b 0000282d 2646001c 00000000 02251021 00c52021 90430000 24a50001"
    "00b0102a a0830000 1440fff9 00000000 27d0ed40 3c02005f 2444f3c0 26e7e100"
    "afa00000 24050003 0000302d 24080030 0200482d 240a0004 0c10531c 0000582d"
    "04410007 3c022000 0c1046bc 0280202d 0c10564a 00000000 10000015 2402fff5"
    "02021025 0c10564a 8c500000 16000005 32c28000 0c1046bc 0280202d 1000000c"
    "2402fff5 10400005 00000000 0c1046bc 0280202d 10000006 0000102d 0c1046c8"
    "0280202d 0c1046bc 0280202d 8fa20030 dfbf00d0 dfbe00c0 dfb700b0 dfb600a0"
    "dfb50090 dfb40080 dfb30070 dfb20060 dfb10050 dfb00040 03e00008 27bd00e0"))
GR_STOCK[GAMES["gr"]["HOOK_P"]] = GAMES["gr"]["STOCK_HOOK"]
GR_STOCK[GAMES["gr"]["HOOK_E"]] = GAMES["gr"]["STOCK_HOOK"]
GR_STOCK.update(_stock_words(GAMES["gr"]["HELPER"], GAMES["gr"]["HELPER_STOCK"]))
GR_STOCK[GAMES["gr"]["DB_HOOK"]] = GAMES["gr"]["DB_HOOK_STOCK"]
GR_STOCK.update(_stock_words(GAMES["gr"]["FX"], GAMES["gr"]["FX_STOCK"]))
GR_STOCK.update(_stock_words(GAMES["gr"]["SPH"], GAMES["gr"]["SPH_STOCK"]))

JS_STOCK = _stock_words(0x0017EFD0, (
    "27bdff20 ffb50090 ffb10050 00c0a82d ffb700b0 00a0882d ffb20060 3c170061"
    "ffb00040 26f27000 ffbf00d0 ffbe00c0 ffb600a0 ffb40080 0c05f7ae ffb30070"
    "0040802d 0c05f8cc 24040003 3c030057 8c624fec 14400005 00000000 0c05f8d8"
    "00000000 1000008a 2402ffff 12000004 00000000 8e160004 56c00005 8e030000"
    "0c05f8d8 00000000 10000081 2402fff7 3c020062 24428500 24040001 ae43000c"
    "02021023 afa40014 00021103 ae42002c 27a40010 ae550014 ae510010 afa00018"
    "0c05e8b8 afa00024 0040a02d 24030004 27a20030 ae430008 ae420004 32c28000"
    "10400024 aef47000 3c130057 0c05e8c8 8e644ffc 3c070057 0000302d 8ce34f68"
    "2402ffff 14620008 3230000f 8ee37000 3c1e0061 00031023 ace34f68 10000011"
    "aee27000 00000000 3c1e0061 24c60001 28c20020 1040000b 00061080 24e34f68"
    "00432821 2404ffff 8ca20000 1444fff8 24c60001 8e420000 00021823 aca20000"
    "ae430000 0c05e8c0 8e644ffc 10000003 00000000 3230000f 3c1e0061 16000003"
    "00111102 10000004 0000802d 2623fff0 00021100 00438023 02b0182a 3c132000"
    "02d31024 14400004 02a3800b 02a0282d 0c05f324 0220202d 02338825 ae500018"
    "1a00000b 0000282d 2646001c 00000000 02251021 00c52021 90430000 24a50001"
    "00b0102a a0830000 1440fff9 00000000 27d07c40 3c020062 24448700 26e77000"
    "afa00000 24050003 0000302d 24080030 0200482d 240a0004 0c05f5aa 0000582d"
    "04410007 3c022000 0c05e8bc 0280202d 0c05f8d8 00000000 10000015 2402fff5"
    "02021025 0c05f8d8 8c500000 16000005 32c28000 0c05e8bc 0280202d 1000000c"
    "2402fff5 10400005 00000000 0c05e8bc 0280202d 10000006 0000102d 0c05e8c8"
    "0280202d 0c05e8bc 0280202d 8fa20030 dfbf00d0 dfbe00c0 dfb700b0 dfb600a0"
    "dfb50090 dfb40080 dfb30070 dfb20060 dfb10050 dfb00040 03e00008 27bd00e0"))
JS_STOCK[GAMES["js"]["HOOK_P"]] = GAMES["js"]["STOCK_HOOK"]
JS_STOCK[GAMES["js"]["HOOK_E"]] = GAMES["js"]["STOCK_HOOK"]
JS_STOCK.update(_stock_words(GAMES["js"]["HELPER"], GAMES["js"]["HELPER_STOCK"]))
JS_STOCK[GAMES["js"]["DB_HOOK"]] = GAMES["js"]["DB_HOOK_STOCK"]
JS_STOCK.update(_stock_words(GAMES["js"]["FX"], GAMES["js"]["FX_STOCK"]))
JS_STOCK.update(_stock_words(GAMES["js"]["SPH"], GAMES["js"]["SPH_STOCK"]))


def build_helper(game):
    """(words, labels) for findground, scaled_add and the scale word."""
    g = GAMES[game]
    fmt = {k: (hex(v) if isinstance(v, int) else v) for k, v in g.items()}
    words, labels = assemble(HELPER_SRC.format(NLIFT_HI=hex(NLIFT_HI), **fmt), g["HELPER"])
    if g["HELPER"] + 4 * len(words) > g["HELPER_END"]:
        raise ValueError("%s shrapnel helpers overflow sceReadlink" % game)
    return words, labels


def build_sph(game):
    """(words, labels) for the sphere-direction picker."""
    g = GAMES[game]
    words, labels = assemble(SPH_SRC.format(REACH_HI=hex(REACH_HI), FLC=hex(g["FLC"]),
                                            VEC=hex(g["VEC"])), g["SPH"])
    if g["SPH"] + 4 * len(words) > g["SPH_END"]:
        raise ValueError("%s sphere picker overflows sceMount" % game)
    return words, labels


def build_fx(game):
    """(words, labels) for the impact-effect routine."""
    g = GAMES[game]
    fmt = {k: hex(g[k]) for k in ("FX", "EFFMGR", "SNDMGR", "EMPS2", "RIPOFF", "RIPPLE")}
    words, labels = assemble(SRC_FX.format(**fmt), g["FX"])
    if g["FX"] + 4 * len(words) > g["FX_END"]:
        raise ValueError("%s impact routine overflows sceIoctl2" % game)
    return words, labels


def build(game, n=DEFAULT_N, size="1"):
    """(words, labels) for the routine with `n` rays per blast."""
    g = GAMES[game]
    _hw, hl = build_helper(game)
    _sw, sl = build_sph(game)
    fmt = {k: (hex(v) if isinstance(v, int) else v) for k, v in g.items()}
    src = SRC.format(FRAME=hex(FRAME), N=int(n), CLEAR=hex(sl["clearance"]),
                     NLIFT_HI=hex(NLIFT_HI), MINR_HI=hex(MINR_HI),
                     MAXR_HI=hex(MAXR_HI), SCALE_HI=hex(SIZES.get(str(size), 0x3F80)),
                     SND=SOUNDS, **fmt)
    words, labels = assemble(src, g["CAVE"], hl)
    if g["CAVE"] + 4 * len(words) > g["CAVE_END"]:
        raise ValueError("%s shrapnel routine overflows sceWrite" % game)
    return words, labels


def edits(game, n, size="1"):
    """[(va, value, stock, note)] for `n` marks per blast (0 = off)."""
    n = max(0, min(MAX_N, int(n)))
    if not n:
        return []
    g = GAMES[game]
    stock = GR_STOCK if game == "gr" else JS_STOCK
    words, labels = build(game, n, size)
    hw, hl = build_helper(game)
    out = [(g["CAVE"] + 4 * i, w, stock[g["CAVE"] + 4 * i],
            "shrapnel marks: routine in sceWrite") for i, w in enumerate(words)]
    out += [(g["HELPER"] + 4 * i, w, stock[g["HELPER"] + 4 * i],
             "shrapnel marks: ground finder and size scale") for i, w in enumerate(hw)]
    fw, _fl = build_fx(game)
    out += [(g["FX"] + 4 * i, w, stock[g["FX"] + 4 * i],
             "shrapnel marks: the bullet's impact effect") for i, w in enumerate(fw)]
    sw, _sl = build_sph(game)
    out += [(g["SPH"] + 4 * i, w, stock[g["SPH"] + 4 * i],
             "shrapnel marks: rays in every direction") for i, w in enumerate(sw)]
    out.append((g["HOOK_P"], 0x0C000000 | (labels["entry_p"] >> 2) & 0x3FFFFFF,
                g["STOCK_HOOK"], "shrapnel marks: grenades, 40 mm and rockets"))
    out.append((g["HOOK_E"], 0x0C000000 | (labels["entry_e"] >> 2) & 0x3FFFFFF,
                g["STOCK_HOOK"], "shrapnel marks: placed charges"))
    out.append((g["DB_HOOK"], 0x0C000000 | (hl["scaled_add"] >> 2) & 0x3FFFFFF,
                g["DB_HOOK_STOCK"], "shrapnel marks: hole size through the scale word"))
    return out


def gr_edits(v):
    return edits("gr", v.get("gr_shrapnel", 0) or 0, v.get("gr_shrapnel_size", "1"))


def js_edits(v):
    return edits("js", v.get("js_shrapnel", 0) or 0, v.get("js_shrapnel_size", "1"))


def selftest(gr_elf=None, js_elf=None):
    """Return a list of failures (empty = pass)."""
    import struct
    fails = []
    for game, stock, elf, delta in (("gr", GR_STOCK, gr_elf, 0x80),
                                    ("js", JS_STOCK, js_elf, 0x100)):
        g = GAMES[game]
        if len(stock) != ((g["CAVE_END"] - g["CAVE"]) + (g["HELPER_END"] - g["HELPER"])
                          + (g["FX_END"] - g["FX"]) + (g["SPH_END"] - g["SPH"])) // 4 + 3:
            fails.append("%s stock table covers %d words" % (game, len(stock)))
        for n, size in ((1, "1"), (DEFAULT_N, "2"), (MAX_N, "3")):
            words, labels = build(game, n, size)
            if words[(labels["count"] - g["CAVE"]) // 4] != 0x24110000 | n:
                fails.append("%s: ray count word is not addiu s1, zero, %d" % (game, n))
            for va, _w, s, _note in edits(game, n, size):
                if stock.get(va) != s:
                    fails.append("%s %08x: edit stock %08x, table %s"
                                 % (game, va, s, stock.get(va)))
        if edits(game, 0):
            fails.append("%s: 0 marks still writes words" % game)
        if elf is not None:
            for va, want in stock.items():
                got = struct.unpack_from("<I", elf, va - 0x00100000 + delta)[0]
                if got != want:
                    fails.append("%s stock %08x: disc %08x, recorded %08x"
                                 % (game, va, got, want))
    return fails

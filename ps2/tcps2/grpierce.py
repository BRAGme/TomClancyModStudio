"""Bullets go through thin cover by calibre: Jungle Storm (SLUS-20820).

IkeSimulationMgr::HandleGunshot (JS 0x00370EA0, Ghost Recon's is 0x00393610)
traces each round once -- RSSimRoom::FindLineCollision's JS twin 0x004C40E0,
range FLT_MAX, from the shooter's room -- and the first thing the line meets
takes it: a soldier or vehicle gets ControllerShot (msg 0x203), scenery gets
WorldShot (0x202: the hole and the hit sound), nothing gets GunshotMissed
(0x204). A plank fence stops a rifle round like a concrete wall.

The trace call (0x003711D8) now goes through a routine that traces the same
way and, while the line ends on scenery, asks whether the round goes on:

  * not a floor or a roof: the face's normal must be within ~45 degrees of
    level (z squared under 0.49); a round never goes down through the ground;
  * the surface type (PackWorldDamageFlags 0x003716A0, bits 8-14; the list
    is Ghost Recon's IkeSurfacePropertyType, from its debug information) has
    a cost in joules (TABLE below, 0xFFFF = never: ground, water, sand, snow);
  * the round still has that much energy. It starts with the gun's muzzle
    energy, KillCoefficient1 * v + KillCoefficient2 * v^2 at v =
    VelocityCoefficient0 (GunFile +0x84, +0x88, +0x78 -- the same layout as
    Ghost Recon's, whose GunFile::GetKillEnergy it is at range 0), and every
    surface it passes takes its cost off. The coefficients put these in
    joules: pistols 500-900, 5.56 mm ~3000, 7.62x39 ~3900, 7.62x51 ~6500,
    .50 ~32000 (Heroes Unleashed numbers).

A round that goes on leaves a WorldShot where it went in (built exactly as the
handler builds its own: shooter, slot, start, direction, hit point, normal,
damage flags), then the trace starts again 5 mm past the hit along the shot,
in the room RSSimScene::FindRoom (0x004EB880) finds there (the face's own room
if none), at most 6 surfaces a round. So a door or wall with a back face gives
that face too -- the exit hole on the far side -- and once a round has gone
into something, a face whose normal points along the shot (the round leaving
a solid) costs nothing: entering pays, leaving is free. Ground, water and the
other never-surfaces stay closed from either side. A surface that is a single sheet has no far face and
keeps one hole. What the last trace meets is handed back to the handler as if
it were the only one, with the distance measured from the shooter, so the
soldier behind the fence gets an ordinary ControllerShot. Damage is not cut:
ControllerShot carries no energy, and the game works it out from the gun and
the distance as it always did.

Costs: glass, foliage and grass 100; wood, drywall, carpet and safety glass
300; thin metal 1500; metal, pipes, tanks and electrical 2500; heavy wood 3500
(7.62x39 and up); thick metal 12000; concrete and bullet-resistant glass
20000 (.50 only).

Caves: sceDevConsDrawS (0x001764C8, 107 words) holds the loop; the twins of
iRotateThreadReadyQueue and iSuspendThread (0x0017B228..0x0017B340) the step
to the next trace and the way out; lzo_adler32's (0x00198210..0x00198398) the
trace, the WorldShot and the table. None is referenced from the loaded image
or either overlay, nor written by any other option. Not yet played.
"""

from __future__ import annotations

from .grasm import assemble

CAVE, CAVE_END = 0x001764C8, 0x00176674      # sceDevConsDrawS twin
CAVE2, CAVE2_END = 0x0017B228, 0x0017B340    # iRotateThreadReadyQueue + iSuspendThread twins
CAVE3, CAVE3_END = 0x00198210, 0x00198398    # lzo_adler32 twin
HOOK, HOOK_STOCK = 0x003711D8, 0x0C131038    # HandleGunshot: jal FindLineCollision (slot: move t3, zero)

SYMS = dict(
    FLC=0x004C40E0, PackWorldDamageFlags=0x003716A0, FindRoom=0x004EB880, SCENE=0x00689E30,
    DATAMGR=0x00614070, Create=0x00498FD0, AddInt=0x00136A20, AddChar=0x00133270,
    AddVec=0x0014E0E0, AddUs=0x00133B80, SendMaster=0x0019F750, Release=0x00124AE0,
)
MSG_WORLDSHOT = 0x202
NEVER = 0xFFFF
#: joules to get through, by IkeSurfacePropertyType (0 = none, 1..27)
TABLE = (
    NEVER,   # 0  no property
    300,     # 1  carpet
    20000,   # 2  concrete
    300,     # 3  wood
    2500,    # 4  metal
    NEVER,   # 5  asphalt
    NEVER,   # 6  sand
    100,     # 7  low grass
    100,     # 8  high grass
    NEVER,   # 9  puddle
    NEVER,   # 10 water
    300,     # 11 drywall
    1500,    # 12 thin metal
    12000,   # 13 thick metal
    2500,    # 14 metal gas tank
    2500,    # 15 steam pipe
    2500,    # 16 electrical
    NEVER,   # 17 snow
    300,     # 18 safety glass
    20000,   # 19 bullet-resistant glass
    NEVER,   # 20 ice
    NEVER,   # 21 mud
    100,     # 22 glass
    100,     # 23 foliage
    NEVER,   # 24 gravel
    100,     # 25 broken glass
    3500,    # 26 heavy wood
    100,     # 27 grass
)
MAX_SURFACES = 6

# HandleGunshot's frame (its sp): +0x178 shooter id, +0x17F slot, +0x168 start, +0x158 direction.
# The call: a0 room, a1 line (point +0, vector +0x10), a2 collision info, a3 the shooter,
# t0 flags, t1 face mask, t2 = 1, t3 = 0, f12 = FLT_MAX. Info: +0x04 normal, +0x10 hit point,
# +0x34 distance, +0x38 controller, +0x3C face, +0x40 room.
FRAME = 0xA0
SRC = """
pierce:
    addiu sp, sp, -{FRAME}
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s2, 0x20(sp)
    sq    s3, 0x30(sp)
    sq    s4, 0x40(sp)
    sq    s5, 0x50(sp)
    sq    s6, 0x60(sp)
    sq    s7, 0x70(sp)
    sd    ra, 0x80(sp)
    swc1  f20, 0x88(sp)
    move  s0, a0                 ; room
    move  s1, a1                 ; line
    move  s2, a2                 ; collision info
    move  s3, a3                 ; the shooter
    move  s4, t0
    move  s5, t1
    move  s7, zero               ; surfaces passed
    lwc1  f0, 0x0(s1)            ; the shooter's start, to put back
    swc1  f0, 0x90(sp)
    lwc1  f0, 0x4(s1)
    swc1  f0, 0x94(sp)
    lwc1  f0, 0x8(s1)
    swc1  f0, 0x98(sp)
    jal   trace
    mtc1  zero, f20              ; energy: none until the gun is found
    lb    a1, {SLOT}(sp)
    lw    t9, 0x0(s3)
    lw    t9, 0x2f8(t9)
    jalr  t9                     ; the item in the slot that fired
    move  a0, s3
    beqz  v0, loop
    lhu   a1, 0x8(v0)            ; its index
    lui   at, %hi(DATAMGR)
    lw    a0, %lo(DATAMGR)(at)
    lw    t9, 0x0(a0)
    lw    t9, 0x4c(t9)
    jalr  t9                     ; its GunFile
    nop
    beqz  v0, loop
    nop
    lwc1  f0, 0x78(v0)           ; muzzle velocity
    lwc1  f1, 0x84(v0)
    lwc1  f2, 0x88(v0)
    mul.s f1, f1, f0
    mul.s f2, f2, f0
    mul.s f2, f2, f0
    add.s f20, f1, f2            ; muzzle energy
loop:
    beqz  s6, done
    slti  at, s7, {MAX}
    beqz  at, done
    lw    v0, 0x38(s2)           ; a soldier or vehicle: it is his
    bnez  v0, done
    lw    a0, 0x3c(s2)
    beqz  a0, done
    lwc1  f0, 0xc(s2)            ; floors and roofs stop it
    mul.s f0, f0, f0
    lui   v0, 0x3efa
    ori   v0, v0, 0xe148         ; 0.49
    mtc1  v0, f1
    nop
    c.lt.s f0, f1
    bc1f  done
    lw    a1, 0x40(s2)
    jal   PackWorldDamageFlags
    move  a2, zero
    srl   v0, v0, 8
    andi  v0, v0, 0x7f           ; the surface type
    sltiu at, v0, {NTYPES}
    beqz  at, done
    sll   v0, v0, 1
    lui   at, %hi(TABLE)
    addu  at, at, v0
    lhu   v0, %lo(TABLE)(at)     ; joules to get through
    mtc1  v0, f1
    nop
    cvt.s.w f1, f1
    jal   backface               ; leaving a solid costs nothing
    nop
    c.lt.s f20, f1
    bc1t  done
    nop
    sub.s f20, f20, f1
    jal   worldshot              ; the hole where it went in
    addiu a0, sp, {FRAME}
    lwc1  f0, 0x10(s1)           ; 5 mm on along the shot
    lwc1  f1, 0x14(s1)
    lwc1  f2, 0x18(s1)
    mul.s f3, f0, f0
    mul.s f4, f1, f1
    add.s f3, f3, f4
    mul.s f4, f2, f2
    add.s f3, f3, f4
    sqrt.s f3, f3
    lui   v0, 0x3ba3
    ori   v0, v0, 0xd70a         ; 0.005
    mtc1  v0, f4
    nop
    div.s f4, f4, f3
    b     step
    nop
"""

# second cave: the 5 mm step, the next trace, the way out
SRC2 = """
step:
    mul.s f0, f0, f4
    mul.s f1, f1, f4
    mul.s f2, f2, f4
    lwc1  f3, 0x10(s2)
    add.s f0, f0, f3
    swc1  f0, 0x0(s1)
    lwc1  f3, 0x14(s2)
    add.s f1, f1, f3
    swc1  f1, 0x4(s1)
    lwc1  f3, 0x18(s2)
    add.s f2, f2, f3
    swc1  f2, 0x8(s1)
    lui   at, %hi(SCENE)
    lw    a0, %lo(SCENE)(at)
    jal   FindRoom               ; the room past the surface
    move  a1, s1
    bnez  v0, again
    move  s0, v0
    lw    s0, 0x40(s2)           ; none: the surface's own
again:
    jal   trace
    addiu s7, s7, 1
    b     loop
    nop
dist:
    lwc1  f0, 0x10(s2)           ; distance from the shooter to the last hit
    lwc1  f1, 0x90(sp)
    sub.s f0, f0, f1
    mul.s f3, f0, f0
    lwc1  f0, 0x14(s2)
    lwc1  f1, 0x94(sp)
    sub.s f0, f0, f1
    mul.s f0, f0, f0
    add.s f3, f3, f0
    lwc1  f0, 0x18(s2)
    lwc1  f1, 0x98(sp)
    sub.s f0, f0, f1
    mul.s f0, f0, f0
    add.s f3, f3, f0
    sqrt.s f3, f3
    b     out
    swc1  f3, 0x34(s2)
done:
    beqz  s7, out
    lwc1  f0, 0x90(sp)           ; the line as it was
    swc1  f0, 0x0(s1)
    lwc1  f0, 0x94(sp)
    swc1  f0, 0x4(s1)
    lwc1  f0, 0x98(sp)
    beqz  s6, out
    swc1  f0, 0x8(s1)
    b     dist
    nop
out:
    move  v0, s6
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    lq    s3, 0x30(sp)
    lq    s4, 0x40(sp)
    lq    s5, 0x50(sp)
    lq    s6, 0x60(sp)
    lq    s7, 0x70(sp)
    ld    ra, 0x80(sp)
    lwc1  f20, 0x88(sp)
    jr    ra
    addiu sp, sp, {FRAME}
"""

# third cave: the trace, the WorldShot, the costs
SRC3 = """
trace:                           ; FindLineCollision as HandleGunshot calls it; s6 = hit
    addiu sp, sp, -0x10
    sd    ra, 0x0(sp)
    move  a0, s0
    move  a1, s1
    move  a2, s2
    move  a3, s3
    move  t0, s4
    move  t1, s5
    li    t2, 1
    move  t3, zero
    lui   v0, 0x7f7f
    ori   v0, v0, 0xffff
    jal   FLC
    mtc1  v0, f12
    andi  s6, v0, 0xff
    ld    ra, 0x0(sp)
    jr    ra
    addiu sp, sp, 0x10

worldshot:                       ; a0 = HandleGunshot's frame, s2 = the collision info
    addiu sp, sp, -0x30
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sd    ra, 0x20(sp)
    move  s1, a0
    lw    a0, 0x3c(s2)
    lw    a1, 0x40(s2)
    jal   PackWorldDamageFlags
    move  a2, zero
    sw    v0, 0x28(sp)
    jal   Create
    li    a0, {MSG}
    move  s0, v0
    lw    a1, 0x178(s1)          ; shooter
    jal   AddInt
    move  a0, s0
    lb    a1, 0x17f(s1)          ; slot
    jal   AddChar
    move  a0, s0
    move  a0, s0
    jal   AddVec
    addiu a1, s1, 0x168          ; start
    move  a0, s0
    jal   AddVec
    addiu a1, s1, 0x158          ; direction
    move  a0, s0
    jal   AddVec
    addiu a1, s2, 0x10           ; hit point
    move  a0, s0
    jal   AddVec
    addiu a1, s2, 0x4            ; normal
    lhu   a1, 0x28(sp)
    jal   AddUs
    move  a0, s0
    li    a0, 1
    jal   SendMaster
    move  a1, s0
    jal   Release
    move  a0, s0
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    ld    ra, 0x20(sp)
    jr    ra
    addiu sp, sp, 0x30
backface:                        ; f1 = the cost -> 0 when the round is leaving a solid it entered:
    beqz  s7, bf_out                 ;   something already passed (s7), not a never-surface (v0 =
    xori  t0, v0, 0xffff             ;   the table's word), and the face's normal along the shot
    beqz  t0, bf_out
    lwc1  f2, 0x4(s2)
    lwc1  f3, 0x10(s1)
    mul.s f2, f2, f3
    lwc1  f3, 0x8(s2)
    lwc1  f5, 0x14(s1)
    mul.s f3, f3, f5
    add.s f2, f2, f3
    lwc1  f3, 0xc(s2)
    lwc1  f5, 0x18(s1)
    mul.s f3, f3, f5
    add.s f2, f2, f3
    mtc1  zero, f3
    nop
    c.lt.s f3, f2
    bc1f  bf_out
    nop
    mov.s f1, f3
bf_out:
    jr    ra
    nop
TABLE:
"""

_CAVE_STOCK_HEX = (   # sceDevConsDrawS twin, 0x001764C8..0x00176674
    "27BDFF20 AFA40020 FFB600A0 24040002 FFB50090 FFB40080 FFBF00D0 0000A02D"
    "FFBE00C0 FFB700B0 FFB30070 FFB20060 FFB10050 FFB00040 0C05DE88 AFA0002C"
    "AFA20024 03A0202D 8FA20020 3C057000 8C430004 8C560000 AFA30028 0C0658FE"
    "8C550008 3C057000 27A40010 0C0658FE 34A52000 8FA30024 8C620000 34420040"
    "AC620000 8FA20028 1040003A 0000202D 12C00032 0000982D 8FA30020 27BE0004"
    "26970001 24630018 AFA30030 00000000 8FA2002C 02D38023 24030004 00029100"
    "03B28821 2E020005 0062800A 0C065902 0220202D 8FA2002C 02A0402D 8FA50030"
    "0200482D 38420001 0260302D AFA2002C 0220202D 0280382D 0C05DC8E 02709821"
    "0220202D 0000282D 0000302D 0C06593A 0000382D 0C065906 0220202D 0000202D"
    "0C05E3C4 0000282D 03D29021 3C038000 8E450000 8FA40024 30A53FFF 0C05DF54"
    "00A32825 00108040 0276102B 1440FFD8 02B0A821 10000003 8FA30028 26970001"
    "8FA30028 02E0A02D 0283102B 1440FFC8 0000202D 0C05E3C4 0000282D DFBF00D0"
    "DFBE00C0 DFB700B0 DFB600A0 DFB50090 DFB40080 DFB30070 DFB20060 DFB10050"
    "DFB00040 03E00008 27BD00E0"
)
_CAVE2_STOCK_HEX = (  # iRotateThreadReadyQueue + iSuspendThread twins, 0x0017B228..0x0017B340
    "27BDFFE0 FFB00000 0080802D 2E020080 10400005 FFBF0010 3C020057 8C434F48"
    "14600003 3C030061 10000010 2402FFFF 3C050061 24634BD8 8CA44BD0 8C620004"
    "24070001 304201FF 00023040 24420001 00662821 AC620004 A0A70008 00A0182D"
    "0C05E8C4 A0700009 0200102D DFBF0010 DFB00000 03E00008 27BD0020 00000000"
    "27BDFFE0 FFBF0010 FFB00000 2403FFD1 0000000C 0040802D 12040005 2E020100"
    "0C05E898 00000000 10000018 DFBF0010 10400004 3C020057 8C434F48 14600003"
    "3C030061 10000010 2402FFFF 3C050061 24634BD8 8CA44BD0 8C620004 24070002"
    "304201FF 00023040 24420001 00662821 AC620004 A0A70008 00A0182D 0C05E8C4"
    "A0700009 0200102D DFBF0010 DFB00000 03E00008 27BD0020"
)
_CAVE3_STOCK_HEX = (  # lzo_adler32 twin, 0x00198210..0x00198398
    "27BDFFE0 00A0702D FFB10010 00C0C02D FFB00000 00046C02 15C00003 308CFFFF"
    "10000055 24020001 13000051 241115AF 3419FFF1 0000802D 0238102B 240F15B0"
    "0302780A 29E20010 14400035 030FC023 91C20000 25EFFFF0 91C30001 29EB0010"
    "01826021 91C40002 01AC6821 91C20003 01836021 91C50004 01AC6821 91C30005"
    "01846021 91C60006 01AC6821 91C40007 01826021 91C70008 01AC6821 91C20009"
    "01856021 91C8000A 01AC6821 91C5000B 01836021 91C9000C 01AC6821 91C3000D"
    "01866021 91CA000E 01AC6821 91C6000F 01846021 25CE0010 01AC6821 01876021"
    "01AC6821 01826021 01AC6821 01886021 01AC6821 01856021 01AC6821 01896021"
    "01AC6821 01836021 01AC6821 018A6021 01AC6821 01866021 1160FFCD 01AC6821"
    "51E00009 0199001B 91C20000 25EFFFFF 25CE0001 01826021 00000000 1DE0FFFA"
    "01AC6821 0199001B 71B9001B 53300001 000001CD 53300001 000001CD 00001010"
    "70001810 0040602D 1700FFB3 0060682D 000D1400 004C1025 DFB10010 DFB00000"
    "03E00008 27BD0020"
)


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


JS_STOCK = _stock_words(CAVE, _CAVE_STOCK_HEX)
JS_STOCK.update(_stock_words(CAVE2, _CAVE2_STOCK_HEX))
JS_STOCK.update(_stock_words(CAVE3, _CAVE3_STOCK_HEX))
JS_STOCK[HOOK] = HOOK_STOCK


def _table_words():
    h = list(TABLE) + [NEVER] * (len(TABLE) % 2)
    return [h[i] | (h[i + 1] << 16) for i in range(0, len(h), 2)]


def _assemble():
    """(words, second-cave words, third-cave words incl. the table, labels)."""
    fmt = dict(FRAME=hex(FRAME), SLOT=hex(FRAME + 0x17F), MAX=MAX_SURFACES, NTYPES=len(TABLE),
               MSG=hex(MSG_WORLDSHOT))
    src, src2, src3 = SRC.format(**fmt), SRC2.format(**fmt), SRC3.format(**fmt)
    w3, l3 = assemble(src3, CAVE3, SYMS)                      # calls out only
    w3 = w3 + _table_words()
    far = dict(SYMS, trace=l3["trace"], worldshot=l3["worldshot"], backface=l3["backface"], TABLE=l3["TABLE"])
    _w2, l2 = assemble(src2, CAVE2, dict(far, loop=CAVE))     # sizes: loop is a stand-in
    w, l1 = assemble(src, CAVE, dict(far, step=l2["step"], done=l2["done"]))
    w2, l2 = assemble(src2, CAVE2, dict(far, loop=l1["loop"]))
    for base, end, words in ((CAVE, CAVE_END, w), (CAVE2, CAVE2_END, w2), (CAVE3, CAVE3_END, w3)):
        if base + 4 * len(words) > end:
            raise ValueError("penetration routine outgrows its cave at %#x: %d words, room %d"
                             % (base, len(words), (end - base) // 4))
    return w, w2, w3, dict(l1, **l2, **l3)


def edits():
    """(va, value, stock, note)."""
    w, w2, w3, labels = _assemble()
    out = [(CAVE + 4 * i, x, JS_STOCK[CAVE + 4 * i], "penetration: the trace loop")
           for i, x in enumerate(w)]
    out += [(CAVE2 + 4 * i, x, JS_STOCK[CAVE2 + 4 * i], "penetration: the next trace, the way out")
            for i, x in enumerate(w2)]
    out += [(CAVE3 + 4 * i, x, JS_STOCK[CAVE3 + 4 * i], "penetration: trace, WorldShot, costs")
            for i, x in enumerate(w3)]
    out.append((HOOK, assemble("jal %#x" % labels["pierce"], HOOK)[0][0], HOOK_STOCK,
                "penetration: each round's trace goes through the routine"))
    return out


def js_edits(v: dict):
    return edits() if v.get("js_penetration") else []


def selftest(gr_elf: bytes, js_elf: bytes):
    """Every stock word against the executable, no address twice. [] = pass."""
    bad = []
    for va, w in JS_STOCK.items():
        off = va - 0x100000 + 0x100
        if int.from_bytes(js_elf[off:off + 4], "little") != w:
            bad.append("js %08X" % va)
    e = edits()
    if len({va for va, *_ in e}) != len(e):
        bad.append("js duplicate VA")
    if any(va not in JS_STOCK for va, *_ in e):
        bad.append("js VA without a stock word")
    return bad

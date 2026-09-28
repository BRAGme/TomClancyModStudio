"""Blood splatter: Ghost Recon (SLUS-20613) and Jungle Storm (SLUS-20820).

A bullet wound already sends the blood spray: SimHuman::ApplyDamage (GR
0x003D54D0) builds the "bloody human" message from the wound's world position
and the bullet's direction, reversed (TakeGunshotDamage negates the shot
vector), and the effects manager puffs a spray there if Blood is on. The only
blood left behind is the pool under a body (BloodPoolPS2, one per death).

This leaves a mark on whatever the bullet would carry blood onto. Right after
the spray is sent, the game's own line test (RSSimRoom::FindLineCollision,
flagged as a gunshot that ignores every soldier, as the shrapnel marks use it)
follows the bullet on from the wound, tilted a little down, for 3 m. If it
meets a wall, floor or anything else, a mark goes there; if not, a second test
straight down finds the ground under the wound. The mark is a bullet hole --
same ring, same lifetime (the one "How long bullet holes last" sets), drawn in
split screen too -- whose frame has bit 0x100 set. BulletHolePS2::Render draws
such a hole with the blood pool's own texture (one of its last three frames:
the spread-out pool) and the blood pool's colour, dark red at half alpha,
instead of a bullet hole's faint grey.

Needs Blood on (the spray and the pools are what that setting turns on).

Caves: sceDevFont (GR 0x0040EED8, JS 0x00177788) and sceDevConsMessage (GR
0x0040E4F0, JS 0x00176DA0) for the routine, the rest of
_id2type (GR 0x004279F8, JS 0x00192AC0; grtrigger has its first 0x80 bytes)
for the two render patches and the colour. Neither is referenced by the loaded
image or Jungle Storm's online/offline overlays. Not yet played.
"""

from __future__ import annotations

from .grasm import assemble

GAMES = {
    "gr": dict(
        CAVE=0x0040EED8, CAVE_END=0x0040F014,         # sceDevFont
        CAVE3=0x0040E4F0, CAVE3_END=0x0040E60C,       # sceDevConsMessage
        CAVE2=0x004279F8, CAVE2_END=0x00427B74,       # _id2type, after grtrigger
        HOOK=0x003D57B4, HOOK_STOCK=0x0C0D76C8,       # ApplyDamage: jal RSObject::Release(message)
        RELEASE=0x0035DB20,
        POS=0x1C0, DIR=0x1D0,                         # ApplyDamage's frame: wound, -bullet direction
        FLC=0x004D8540, VEC=0x0C,
        EFFGET=0x0045D400,                            # EffMgrPS2::Get
        MGR="lw      a0, 0x627c(v0)",                 # its BulletHoleManagerPS2
        ADDONE=0x0046DAC0,                            # AddOneBulletHole(mgr, frame, pos, nrm, life, size)
        LIFE=0x00249638,                              # DisplayBullethole: lui v1, <life> (the decal-life word)
        TEX_HOOK=0x0046DDA4, TEX_STOCK=0x8C440080,    # BulletHolePS2::Render: lw a0,0x80(v0) (texture set)
        TEX_NOP=0x0046DDAC, TEX_NOP_STOCK=0x8E830020,  # lw v1,0x20(s4) (frame) -- set by the patch instead
        COL_HOOK=0x0046DED8, COL_STOCK=0x2442FED0,    # addiu v0,v0,-0x130 (the faint grey)
        COL_LO=-0x130, HOLE="s4", MODELS=0x00630B48,
        COLOR=0x00427B60,                             # 16-byte aligned, in CAVE2
    ),
    "js": dict(
        CAVE=0x00177788, CAVE_END=0x001778C4,         # twin of sceDevFont
        CAVE3=0x00176DA0, CAVE3_END=0x00176EBC,       # twin of sceDevConsMessage
        CAVE2=0x00192AC0, CAVE2_END=0x00192C3C,
        HOOK=0x003B5240, HOOK_STOCK=0x0C0492B8,
        RELEASE=0x00124AE0,
        POS=0x240, DIR=0x230,
        FLC=0x004C40E0, VEC=0x10,
        EFFGET=0x00422F50,
        MGR="jal     0x00244de0\n    move    a0, v0\n    move    a0, v0",
        ADDONE=0x00431A20,
        LIFE=0x00245E4C,
        TEX_HOOK=0x00431CF0, TEX_STOCK=0x8C440080,
        TEX_NOP=0x00431CF8, TEX_NOP_STOCK=0x8E030020,
        COL_HOOK=0x00431E48, COL_STOCK=0x2442B710,
        COL_LO=-0x48F0, HOLE="s0", MODELS=0x0067CF48,
        COLOR=0x00192C20,
    ),
}

WALL = 0x3F00      # 0.5 m
BLOOD_RGBA = (0x10, 0, 0, 0x40)   # the blood pool's colour, spread out: dark red, half alpha
FLOOR = 0x3ECC     # 0.4 m

SPLAT_SRC = """
splat:                                  ; jal from ApplyDamage in place of Release(message)
    addiu   sp, sp, -0x100
    sd      ra, 0x40(sp)
    sd      a0, 0x48(sp)                ; the message, released on the way out
    sq      s0, 0x00(sp)
    sq      s1, 0x10(sp)
    sq      s2, 0x20(sp)
    sq      s3, 0x30(sp)
    lw      s0, 0x38(s5)                ; the soldier's RSSimRoom
    beqz    s0, out
    addiu   s1, sp, 0x100+{POS}         ; the wound, world
    lwc1    f2, 0x100+{DIR}(sp)         ; the bullet's direction, reversed
    lwc1    f3, 0x104+{DIR}(sp)
    lwc1    f4, 0x108+{DIR}(sp)
    neg.s   f2, f2
    neg.s   f3, f3
    neg.s   f4, f4
    mul.s   f5, f2, f2
    mul.s   f6, f3, f3
    add.s   f5, f5, f6
    mul.s   f6, f4, f4
    add.s   f5, f5, f6
    sqrt.s  f6, f5
    nop
    nop
    lui     at, 0x3a83                  ; 0.001
    mtc1    at, f7
    nop
    c.lt.s  f6, f7
    nop
    bc1t    down                        ; no direction: straight down only
    nop
    div.s   f2, f2, f6
    div.s   f3, f3, f6
    div.s   f4, f4, f6
    lui     at, 0x3eb3                  ; 0.35: tilted down
    mtc1    at, f7
    nop
    sub.s   f4, f4, f7              ; (not renormalised: the reach is 2-4 m)
    jal     ray
    nop
    bnez    v0, go_mark
    lui     s2, {WALL}                  ; a wall-sized mark
down:
    mtc1    zero, f2
    mtc1    zero, f3
    lui     at, 0xbf80                  ; straight down
    jal     ray
    mtc1    at, f4
    beqz    v0, out
    lui     s2, {FLOOR}                 ; a floor-sized mark
go_mark:
    j       mark                        ; (in the second cave; comes back to out)
    nop
out:
    ld      a0, 0x48(sp)
    ld      ra, 0x40(sp)
    lq      s0, 0x00(sp)
    lq      s1, 0x10(sp)
    lq      s2, 0x20(sp)
    lq      s3, 0x30(sp)
    j       {RELEASE:#x}
    addiu   sp, sp, 0x100

"""

# the line test, and the mark itself (jumped to from SPLAT_SRC, jumps back to its out)
AUX_SRC = """
ray:                                    ; from the wound (s1) along f2..f4, 3 m; v0 = hit
    addiu   sp, sp, -0x10
    sd      ra, 0(sp)
    lw      t1, 0(s1)                   ; RSLine3: point
    sw      t1, 0x60(sp)
    lw      t1, 4(s1)
    sw      t1, 0x64(sp)
    lw      t1, 8(s1)
    sw      t1, 0x68(sp)
    swc1    f2, 0x60+{VEC}(sp)          ; RSLine3: vector
    swc1    f3, 0x64+{VEC}(sp)
    swc1    f4, 0x68+{VEC}(sp)
    move    a0, s0                      ; room
    addiu   a1, sp, 0x60                ; &line
    addiu   a2, sp, 0x80                ; &RSLineCollisionInfo (0x70 in the caller's frame)
    move    a3, zero                    ; no shooter
    addiu   t0, zero, 0x81a             ; kIsGunshot | kLineIgnoreAllControllers
    addiu   t1, zero, 1                 ; kGunshotTransparent
    move    t2, zero
    lui     at, 0x4040                  ; 3 m
    mtc1    at, f12
    jal     {FLC:#x}
    move    t3, zero
    andi    v0, v0, 0xff
    ld      ra, 0(sp)
    jr      ra
    addiu   sp, sp, 0x10

mark:
    lwc1    f7, 0x74(sp)                ; info+0x04: hit normal (the line test's info is at 0x70 here)
    lwc1    f8, 0x78(sp)
    lwc1    f9, 0x7c(sp)
    lui     at, 0x3ca3                  ; 0.02: off the surface, as a bullet hole is
    ori     at, at, 0xd70a
    mtc1    at, f10
    nop
    mul.s   f11, f7, f10
    lwc1    f12, 0x80(sp)               ; info+0x10: hit point
    add.s   f12, f12, f11
    swc1    f12, 0xc0(sp)
    mul.s   f11, f8, f10
    lwc1    f12, 0x84(sp)
    add.s   f12, f12, f11
    swc1    f12, 0xc4(sp)
    mul.s   f11, f9, f10
    lwc1    f12, 0x88(sp)
    add.s   f12, f12, f11
    swc1    f12, 0xc8(sp)
    lw      s3, 0x80(sp)                ; which of the pool's last frames: from the hit point
    srl     s3, s3, 6
    andi    s3, s3, 3
    jal     {EFFGET:#x}
    ori     s3, s3, 0x100               ; the blood bit
    {MGR}
    lui     t1, %hi({LIFE:#x})
    lhu     t1, %lo({LIFE:#x})(t1)      ; a bullet hole's lifetime, as the decal setting left it
    sll     t1, t1, 16
    mtc1    t1, f12
    mtc1    s2, f13                     ; size
    move    a1, s3
    addiu   a2, sp, 0xc0
    jal     {ADDONE:#x}
    addiu   a3, sp, 0x74
    j       out
    nop
"""

RENDER_SRC = """
tex:                                    ; jal from BulletHolePS2::Render; v0 = EffMgrPS2
    lw      v1, 0x20({HOLE})            ; the hole's frame
    andi    t9, v1, 0x100
    bnez    t9, tex_blood
    lw      a0, 0x80(v0)                ; the bullet holes' texture set, as shipped
    jr      ra
    nop
tex_blood:
    lw      a0, 0x64(v0)                ; the blood pool's texture set
    lui     t8, %hi({MODELS:#x})
    lw      t8, %lo({MODELS:#x})(t8)
    sll     t7, a0, 2
    addu    t7, t7, t8
    lw      t7, 4(t7)                   ; its model
    lw      t7, 0x10(t7)                ; frame count
    andi    v1, v1, 0xff
    subu    v1, t7, v1
    addiu   v1, v1, -1                  ; one of the last frames
    bgez    v1, tex_ok
    nop
    move    v1, zero
tex_ok:
    jr      ra
    nop
col:                                    ; jal from BulletHolePS2::Render in place of the colour's addiu
    lw      t9, 0x20({HOLE})
    andi    t9, t9, 0x100
    bnez    t9, col_blood
    addiu   v0, v0, {COL_LO}            ; the faint grey, as shipped
    jr      ra
    nop
col_blood:
    lui     v0, %hi(blood_rgba)
    jr      ra
    addiu   v0, v0, %lo(blood_rgba)
"""

_GR_CAVE_STOCK_HEX = (   # sceDevFont, 0x0040EED8..0x0040F014
    "27BDFF70 FFB30040 00A0982D FFB60070 FFB20030 0080282D FFB10020 0120B02D"
    "0100882D FFB50060 FFB00010 00C0902D FFBF0080 03A0202D FFB40050 0C10AC3A"
    "0260802D 03A0202D 0000282D 0000302D 0C10AC58 0000382D 8FA20000 92250000"
    "2455FFFC 10A0001D 26310001 3C140058 2402000A 14A20003 000528C0 0260802D"
    "26520060 268367D8 00A32821 0010203C 0012103C 0004203E 0002143A DCA80000"
    "00822025 2405FFFF 0005283C 00852825 3C0780FF 03A0202D 2406000C 34E7FFFF"
    "0C103A00 02C0482D 26100080 92250000 14A0FFE7 26310001 8FA20000 2442FFFC"
    "3C035000 00551023 03A0202D 00021083 0000282D 00021082 0000302D 00431025"
    "0000382D 0C10AC76 AEA20000 8FA20000 DFBF0080 DFB60070 2442FFF0 DFB50060"
    "DFB40050 DFB30040 DFB20030 DFB10020 DFB00010 03E00008 27BD0090"
)
_GR_CAVE2_STOCK_HEX = (   # _id2type after grtrigger, 0x004279F8..0x00427B74
    "00129638 3411BDA0 00118E38 3410FFE0 00108638 3419FFF8 0019CE38 3418F000"
    "0018C638 340FC000 000F7E38 DC670008 10EB0011 0167102B 14400005 00000000"
    "50F70028 DC680000 1000003C 25290001 54F6003A 25290001 DC620000 00D53824"
    "54E20036 25290001 AC890000 240A0001 10000031 ACAC0000 DC680000 3402BD88"
    "00021638 11020011 0048102B 14400007 00000000 1114000B 00D03824 1113000B"
    "00CB3824 1000000B 0000102D 11120008 00D93824 11110005 00CB3824 10000005"
    "0000102D 10000003 2402001F 00D93824 24020007 54E80019 25290001 10000011"
    "01C21024 3402E000 00021638 15020004 00000000 00D83824 10000007 2402000F"
    "150F0004 00C73824 00C23824 10000002 2402001F 0000102D 54E80008 25290001"
    "01A21024 AC890000 0002103C 0002103F 240A0001 ACA20000 25290001 2D22000A"
    "10400003 24630010 5140FFB9 DC670008 DFB70070 0140102D DFB60060 DFB50050"
    "DFB40040 DFB30030 DFB20020 DFB10010 DFB00000 03E00008 27BD0080"
)
_GR_CAVE3_STOCK_HEX = (   # sceDevConsMessage, 0x0040E4F0..0x0040E60C
    "27BDFFA0 FFB40040 FFB10010 00E0A02D FFB00000 00A0882D 0080802D FFB20020"
    "00C0902D 0000202D 0280282D FFBF0050 0C10378E FFB30030 1600001E 0200202D"
    "24530002 0220202D 0240282D 0260302D 0C10361E 24070003 0040802D 12000028"
    "DFBF0050 0260382D 0200202D 0000282D 0000302D 0C103984 24080003 0200202D"
    "24050001 0C103824 24060001 0200202D 0280282D DFBF0050 DFB40040 DFB30030"
    "DFB20020 DFB10010 DFB00000 0810378E 27BD0060 2625FFFF 2646FFFF 24470002"
    "0C103984 24080003 0220282D 0240302D 0C103824 0200202D 0200202D 0280282D"
    "DFBF0050 DFB40040 DFB30030 DFB20020 DFB10010 DFB00000 0810378E 27BD0060"
    "DFB40040 DFB30030 DFB20020 DFB10010 DFB00000 03E00008 27BD0060"
)
_JS_CAVE_STOCK_HEX = (   # sceDevFont's twin, 0x00177788..0x001778C4
    "27BDFF70 FFB30040 00A0982D FFB60070 FFB20030 0080282D FFB10020 0120B02D"
    "0100882D FFB50060 FFB00010 00C0902D FFBF0080 03A0202D FFB40050 0C0658FE"
    "0260802D 03A0202D 0000282D 0000302D 0C06591C 0000382D 8FA20000 92250000"
    "2455FFFC 10A0001D 26310001 3C140058 2402000A 14A20003 000528C0 0260802D"
    "26520060 26830868 00A32821 0010203C 0012103C 0004203E 0002143A DCA80000"
    "00822025 2405FFFF 0005283C 00852825 3C0780FF 03A0202D 2406000C 34E7FFFF"
    "0C05DC2C 02C0482D 26100080 92250000 14A0FFE7 26310001 8FA20000 2442FFFC"
    "3C035000 00551023 03A0202D 00021083 0000282D 00021082 0000302D 00431025"
    "0000382D 0C06593A AEA20000 8FA20000 DFBF0080 DFB60070 2442FFF0 DFB50060"
    "DFB40050 DFB30040 DFB20030 DFB10020 DFB00010 03E00008 27BD0090"
)
_JS_CAVE2_STOCK_HEX = (   # _id2type's twin after grtrigger, 0x00192AC0..0x00192C3C
    "00129638 3411BDA0 00118E38 3410FFE0 00108638 3419FFF8 0019CE38 3418F000"
    "0018C638 340FC000 000F7E38 DC670008 10EB0011 0167102B 14400005 00000000"
    "50F70028 DC680000 1000003C 25290001 54F6003A 25290001 DC620000 00D53824"
    "54E20036 25290001 AC890000 240A0001 10000031 ACAC0000 DC680000 3402BD88"
    "00021638 11020011 0048102B 14400007 00000000 1114000B 00D03824 1113000B"
    "00CB3824 1000000B 0000102D 11120008 00D93824 11110005 00CB3824 10000005"
    "0000102D 10000003 2402001F 00D93824 24020007 54E80019 25290001 10000011"
    "01C21024 3402E000 00021638 15020004 00000000 00D83824 10000007 2402000F"
    "150F0004 00C73824 00C23824 10000002 2402001F 0000102D 54E80008 25290001"
    "01A21024 AC890000 0002103C 0002103F 240A0001 ACA20000 25290001 2D22000A"
    "10400003 24630010 5140FFB9 DC670008 DFB70070 0140102D DFB60060 DFB50050"
    "DFB40040 DFB30030 DFB20020 DFB10010 DFB00000 03E00008 27BD0080"
)
_JS_CAVE3_STOCK_HEX = (   # sceDevConsMessage's twin, 0x00176DA0..0x00176EBC
    "27BDFFA0 FFB40040 FFB10010 00E0A02D FFB00000 00A0882D 0080802D FFB20020"
    "00C0902D 0000202D 0280282D FFBF0050 0C05D9BA FFB30030 1600001E 0200202D"
    "24530002 0220202D 0240282D 0260302D 0C05D84A 24070003 0040802D 12000028"
    "DFBF0050 0260382D 0200202D 0000282D 0000302D 0C05DBB0 24080003 0200202D"
    "24050001 0C05DA50 24060001 0200202D 0280282D DFBF0050 DFB40040 DFB30030"
    "DFB20020 DFB10010 DFB00000 0805D9BA 27BD0060 2625FFFF 2646FFFF 24470002"
    "0C05DBB0 24080003 0220282D 0240302D 0C05DA50 0200202D 0200202D 0280282D"
    "DFBF0050 DFB40040 DFB30030 DFB20020 DFB10010 DFB00000 0805D9BA 27BD0060"
    "DFB40040 DFB30030 DFB20020 DFB10010 DFB00000 03E00008 27BD0060"
)


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


GR_STOCK = _stock_words(GAMES["gr"]["CAVE"], _GR_CAVE_STOCK_HEX)
GR_STOCK.update(_stock_words(GAMES["gr"]["CAVE2"], _GR_CAVE2_STOCK_HEX))
GR_STOCK.update(_stock_words(GAMES["gr"]["CAVE3"], _GR_CAVE3_STOCK_HEX))
JS_STOCK = _stock_words(GAMES["js"]["CAVE"], _JS_CAVE_STOCK_HEX)
JS_STOCK.update(_stock_words(GAMES["js"]["CAVE2"], _JS_CAVE2_STOCK_HEX))
JS_STOCK.update(_stock_words(GAMES["js"]["CAVE3"], _JS_CAVE3_STOCK_HEX))
for _st, _g in ((GR_STOCK, GAMES["gr"]), (JS_STOCK, GAMES["js"])):
    for _k in ("HOOK", "TEX_HOOK", "TEX_NOP", "COL_HOOK"):
        _st[_g[_k]] = _g[{"HOOK": "HOOK_STOCK", "TEX_HOOK": "TEX_STOCK",
                          "TEX_NOP": "TEX_NOP_STOCK", "COL_HOOK": "COL_STOCK"}[_k]]


def routines(game: str):
    """(splat words, aux words, render words, render labels)."""
    g = GAMES[game]
    fmt = dict(WALL="%#x" % WALL, FLOOR="%#x" % FLOOR, **g)
    # two passes: each cave names labels in the other
    _, sl = assemble(SPLAT_SRC.format(**fmt), g["CAVE"], {"ray": 0, "mark": 0})
    aw, al = assemble(AUX_SRC.format(**fmt), g["CAVE3"], {"out": sl["out"]})
    sw, sl = assemble(SPLAT_SRC.format(**fmt), g["CAVE"], {"ray": al["ray"], "mark": al["mark"]})
    rw, rl = assemble(RENDER_SRC.format(**g), g["CAVE2"], {"blood_rgba": g["COLOR"]})
    if g["CAVE2"] + 4 * len(rw) > g["COLOR"]:
        raise ValueError("blood splatter render patches run into the colour")
    if (g["CAVE"] + 4 * len(sw) > g["CAVE_END"] or g["CAVE2"] + 4 * len(rw) > g["CAVE2_END"]
            or g["CAVE3"] + 4 * len(aw) > g["CAVE3_END"]):
        raise ValueError("blood splatter routines outgrow their caves")
    return sw, aw, rw, rl


def edits(game: str):
    """(va, value, stock, note)."""
    g = GAMES[game]
    st = GR_STOCK if game == "gr" else JS_STOCK
    sw, aw, rw, rl = routines(game)
    out = [(g["CAVE"] + 4 * i, w, st[g["CAVE"] + 4 * i], "blood splatter: follow the bullet")
           for i, w in enumerate(sw)]
    out += [(g["CAVE3"] + 4 * i, w, st[g["CAVE3"] + 4 * i], "blood splatter: the mark")
            for i, w in enumerate(aw)]
    out += [(g["CAVE2"] + 4 * i, w, st[g["CAVE2"] + 4 * i], "blood splatter: drawn as blood")
            for i, w in enumerate(rw)]
    out += [(g["COLOR"] + 4 * i, w, st[g["COLOR"] + 4 * i], "blood splatter: its colour")
            for i, w in enumerate(BLOOD_RGBA)]
    out.append((g["HOOK"], assemble("jal %#x" % g["CAVE"], g["HOOK"])[0][0], g["HOOK_STOCK"],
                "blood splatter: after the spray, before the message is released"))
    out.append((g["TEX_HOOK"], assemble("jal %#x" % rl["tex"], g["TEX_HOOK"])[0][0], g["TEX_STOCK"],
                "blood splatter: texture set and frame per hole"))
    out.append((g["TEX_NOP"], 0x00000000, g["TEX_NOP_STOCK"], "blood splatter: (frame set above)"))
    out.append((g["COL_HOOK"], assemble("jal %#x" % rl["col"], g["COL_HOOK"])[0][0], g["COL_STOCK"],
                "blood splatter: colour per hole"))
    return out


def gr_edits(v: dict):
    return edits("gr") if v.get("gr_blood") and v.get("gr_blood_splatter") else []


def js_edits(v: dict):
    return edits("js") if v.get("js_blood") and v.get("js_blood_splatter") else []


def selftest(gr_elf: bytes, js_elf: bytes):
    """Every stock word against the executables, no address twice. [] = pass."""
    bad = []
    for game, st, elf, d in (("gr", GR_STOCK, gr_elf, 0x80), ("js", JS_STOCK, js_elf, 0x100)):
        for va, w in st.items():
            off = va - 0x100000 + d
            if int.from_bytes(elf[off:off + 4], "little") != w:
                bad.append("%s %08X" % (game, va))
        e = edits(game)
        if len({va for va, *_ in e}) != len(e):
            bad.append("%s duplicate VA" % game)
        if any(va not in st for va, *_ in e):
            bad.append("%s VA without a stock word" % game)
        if GAMES[game]["COLOR"] & 15:
            bad.append("%s colour not 16-byte aligned" % game)
    return bad

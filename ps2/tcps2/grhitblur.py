"""Split-screen hit blur for Ghost Recon (SLUS-20613) and Jungle Storm (SLUS-20820).

When your soldier is hit, single player blurs the screen for five seconds
with a few dark blotches. Split screen starts the same effect -- the
trigger, SimHuman::ApplyDamage (GR 0x003D54D0, JS 0x003B4F70), only asks
whether the soldier is human-controlled -- and never draws it:
EffMgrPS2::Render (GR 0x0045E160, JS 0x00423C10) draws the hit blur only in
its full-screen block, and its per-viewport split-screen loop draws night
vision, the scope-zoom blur, the scope mask and the black screen but not the
hit blur. (Split-screen savestates hold all ten blotches still alive 20 s
after they were made: the render, which retires them, never ran.) There is
also only one blur object, shared by both players.

This gives each player a blur of their own, drawn on their own half:

  * the effects manager builds two hit blurs back to back instead of one
    (0x420 bytes instead of 0x210; blur 1 is player 1 and single player,
    blur 2 player 2) -- ``ctor2``;
  * ApplyDamage picks blur 2 when split screen is on and the hit soldier is
    the one player 2 is viewing (SimHuman+0x128 == GetObserverID(1), the test
    the game already uses to send the scope-zoom blur to the right player)
    -- ``getblur``;
  * the split loop's scope-zoom blur call also draws that half's hit blur
    -- ``splitblur``: the blotches first, in the half's own draw area, then
    the blur itself with the two full-screen copy constants pointed at that
    half (rows S..S+223, downsample heights 56 and 112, which keep single
    player's 4x and 2x strength), and the full-screen offset and scissor
    ``init_frame`` uses; afterwards the constants go back to stock and the
    half's draw area is set again.

Single player is unchanged apart from 0x210 more bytes of heap per mission.
The routines live in sceSymlink + sceReadlink (GR 0x00418680, JS
0x00181140), which nothing in the loaded image references. Every hook's
stock word was checked against the executables, and the routines were run in
an interpreter with stubbed engine calls (blur choice, call order, the
constants each pass sees, restoring them, the blotch hide and restore,
register contract). Not yet played.

Not included: rewriting ScreenBlurPS2::ClearEffect to clear both blurs. A
switch or follow clears only blur 1, as stock clears the one blur; a blur
lasts five seconds at most.
"""

from __future__ import annotations

from .grasm import assemble

DSLL32_A1_A1 = 0x0005283C          # dsll32 a1, a1, 0 (grasm has no dsll32)

GAMES = {
    "gr": dict(
        CAVE=0x00418680, CAVE_END=0x004188F0,      # before grcamera's unhide routine
        Render=0x0046C820, Ctor=0x0046C6E0, EffGet=0x0045D400, WriteOneReg=0x00466B10,
        SetSplit=0x0044EBC0, GSYS=0x00630B40, SimGet=0x0037A0A0,
        BLUR=0x6284, F2D_UV=0x0056FE40, D2F_RECT=0x0056FE50,
        H1=0x00632240, H2=0x00632260, H1G=0x00632248, H2G=0x00632268,
        HOOKS=((0x0045D6C4, 0x24040210, "addiu a0, zero, 0x420", "allocate two hit blurs"),
               (0x0045D6E0, 0x0C11B1B8, "jal ctor2", "build both hit blurs"),
               (0x003D554C, 0x0C0E5A3C, "jal getblur", "ApplyDamage picks the hit player's blur"),
               (0x0045E4AC, 0x0C11B208, "jal splitblur", "split loop draws each half's hit blur")),
        STOCK=(
            "27bdff40 ffb00040 ffb10050 0080802d ffb600a0 00a0882d ffb20060 24040011"
            "ffbf00b0 3c16005f ffb50090 26d2e100 ffb40080 0c10563e ffb30070 3c020057"
            "8c43e1c0 54600004 92020000 0c10567e 00000000 92020000 0000282d 00021e00"
            "10600010 a242000c 27b30030 3c15005f 3c14005f 24a50001 28a20400 1040000c"
            "02051021 02452021 90430000 a083000c 00031e00 5460fff8 24a50001 10000005"
            "24020400 27b30030 3c15005f 3c14005f 24020400 50a20001 a240040b 92220000"
            "0000282d 00021e00 1060000c a242040c 2646040c 24a50001 28a20400 10400007"
            "02251021 00c52021 90430000 a0830000 00031e00 5460fff8 24a50001 24020400"
            "50a20001 a240080b 24020001 afa00018 afa20014 27a40010 afa00024 0c1046b8"
            "2690ed40 0040882d ae530004 24020004 ae510000 ae420008 26a4f3c0 26c7e100"
            "24050018 afa00000 0000302d 2408080c 0200482d 240a0004 0c10531c 0000582d"
            "04410007 3c022000 0c1046bc 0220202d 0c10564a 00000000 1000000f 2402fff5"
            "02021025 0c10564a 8c500000 16000005 00000000 0c1046bc 0220202d 10000006"
            "2402fff5 0c1046c8 0220202d 0c1046bc 0220202d 8fa20030 dfbf00b0 dfb600a0"
            "dfb50090 dfb40080 dfb30070 dfb20060 dfb10050 dfb00040 03e00008 27bd00c0"
            "27bdff30 ffb10050 ffb50090 0080882d ffb00040 00a0a82d ffb700b0 00c0802d"
            "ffb20060 24040011 ffbf00c0 3c17005f ffb600a0 26f2e100 ffb40080 0c10563e"
            "ffb30070 3c030057 8c62e1c0 54400004 92220000 0c10567e 00000000 92220000"
            "0000282d 00021e00 10600012 a2420014 2e060400 27b30030 3c16005f 3c14005f"
            "24a50001"),
    ),
    "js": dict(
        CAVE=0x00181140, CAVE_END=0x001813A0,      # before grcamera's unhide routine
        Render=0x00430770, Ctor=0x00430680, EffGet=0x00422F50, WriteOneReg=0x0042C050,
        SetSplit=0x004151A0, GSYS=0x0067CF40, SimGet=0x001245D0,
        BLUR=0x627C, F2D_UV=0x0057B680, D2F_RECT=0x0057B690,
        H1=0x0057B668, H2=0x0057B678, H1G=None, H2G=None,
        HOOKS=((0x00423154, 0x24040210, "addiu a0, zero, 0x420", "allocate two hit blurs"),
               (0x00423168, 0x0C10C1A0, "jal ctor2", "build both hit blurs"),
               (0x003B4FD8, 0x0C0DD8CC, "jal getblur", "ApplyDamage picks the hit player's blur"),
               (0x00423F40, 0x0C10C1DC, "jal splitblur", "split loop draws each half's hit blur")),
        STOCK=(
            "27bdff40 ffb00040 ffb10050 0080802d ffb600a0 00a0882d ffb20060 24040011"
            "ffbf00b0 3c160061 ffb50090 26d27000 ffb40080 0c05f8cc ffb30070 3c020057"
            "8c434fec 54600004 92020000 0c05f918 00000000 92020000 0000282d 00021e00"
            "10600010 a242000c 27b30030 3c150062 3c140061 24a50001 28a20400 1040000c"
            "02051021 02452021 90430000 a083000c 00031e00 5460fff8 24a50001 10000005"
            "24020400 27b30030 3c150062 3c140061 24020400 50a20001 a240040b 92220000"
            "0000282d 00021e00 1060000c a242040c 2646040c 24a50001 28a20400 10400007"
            "02251021 00c52021 90430000 a0830000 00031e00 5460fff8 24a50001 24020400"
            "50a20001 a240080b 24020001 afa00018 afa20014 27a40010 afa00024 0c05e8b8"
            "26907c40 0040882d ae530004 24020004 ae510000 ae420008 26a48700 26c77000"
            "24050018 afa00000 0000302d 2408080c 0200482d 240a0004 0c05f5aa 0000582d"
            "04410007 3c022000 0c05e8bc 0220202d 0c05f8d8 00000000 1000000f 2402fff5"
            "02021025 0c05f8d8 8c500000 16000005 00000000 0c05e8bc 0220202d 10000006"
            "2402fff5 0c05e8c8 0220202d 0c05e8bc 0220202d 8fa20030 dfbf00b0 dfb600a0"
            "dfb50090 dfb40080 dfb30070 dfb20060 dfb10050 dfb00040 03e00008 27bd00c0"
            "27bdff30 ffb10050 ffb50090 0080882d ffb00040 00a0a82d ffb700b0 00c0802d"
            "ffb20060 24040011 ffbf00c0 3c170061 ffb600a0 26f27000 ffb40080 0c05f8cc"
            "ffb30070 3c030057 8c624fec 54400004 92220000 0c05f918 00000000 92220000"
            "0000282d 00021e00 10600012 a2420014"),
    ),
}

_GUARDS = """
        li    t1, 1
        lui   at, %hi(H1G)
        sb    t1, %lo(H1G)(at)          ; height 1's first-call init has run
        lui   at, %hi(H2G)
        sb    t1, %lo(H2G)(at)          ; height 2's likewise
"""

SRC = """
; ---------------------------------------------------------------- ctor2
; EffMgrPS2's constructor: two type-1 ScreenBlurPS2 back to back. Blur 1 (+0)
; is player 1 and single player, blur 2 (+0x210) split-screen player 2.
ctor2:
        addiu sp, sp, -0x20
        sd    ra, 0x00(sp)
        sq    s0, 0x10(sp)
        jal   Ctor                      ; ScreenBlurPS2(a0, 1, 0.5)
        move  s0, a0
        lui   t0, 0x3f00
        mtc1  t0, f12                   ; 0.5 again (f12 is caller-saved)
        addiu a0, s0, 0x210
        jal   Ctor                      ; ScreenBlurPS2(a0 + 0x210, 1, 0.5)
        li    a1, 1
        move  v0, s0
        ld    ra, 0x00(sp)
        lq    s0, 0x10(sp)
        jr    ra
        addiu sp, sp, 0x20

; ---------------------------------------------------------------- getblur
; In place of EffMgrPS2::GetScreenBlur in SimHuman::ApplyDamage
; (a0 = EffMgrPS2, s5 = the damaged soldier, past the human-controlled test).
getblur:
        addiu sp, sp, -0x20
        sd    ra, 0x00(sp)
        sq    s0, 0x10(sp)
        lw    s0, BLUR(a0)              ; blur 1
        lui   at, %hi(GSYS)
        lw    t0, %lo(GSYS)(at)
        lbu   t0, 0x2880(t0)            ; split-screen draw flag
        beqz  t0, gb_done
        nop
        jal   SimGet                    ; IIkeSimulationMgr::Get
        nop
        lw    t9, 0(v0)
        move  a0, v0
        lw    t9, 0x64(t9)              ; GetObserverID
        jalr  t9
        li    a1, 1
        lw    t0, 0x128(s5)             ; the damaged soldier's object id
        bne   t0, v0, gb_done
        nop
        addiu s0, s0, 0x210             ; player 2's blur
gb_done:
        move  v0, s0
        ld    ra, 0x00(sp)
        lq    s0, 0x10(sp)
        jr    ra
        addiu sp, sp, 0x20

; ---------------------------------------------------------------- splitblur
; In place of the split loop's scope-zoom blur Render (a0 = that blur, a1 = 1,
; a2 = viewport; the loop has just set the viewport's draw area).
splitblur:
        addiu sp, sp, -0x40
        sd    ra, 0x00(sp)
        sq    s0, 0x10(sp)
        sq    s1, 0x20(sp)
        sq    s2, 0x30(sp)
        jal   Render                    ; stock: the scope-zoom blur
        move  s0, a2                    ; s0 = viewport (0 top, 1 bottom)
        jal   EffGet
        nop
        lw    s1, BLUR(v0)              ; blur 1
        beqz  s1, sb_out
        sll   t0, s0, 9
        sll   t1, s0, 4
        addu  t0, t0, t1                ; viewport * 0x210
        addu  s1, s1, t0                ; this player's blur
        lbu   t0, 9(s1)                 ; active?
        beqz  t0, sb_out
        nop
; -- pass A: the blotches only, in this half's own draw area
        sb    zero, 9(s1)
        move  a0, s1
        li    a1, 1
        jal   Render
        move  a2, s0
        li    t0, 1
        sb    t0, 9(s1)
; -- hide the blotches from pass B (bit k of s2 = blotch k was alive)
        move  s2, zero
        li    t2, 1
        addiu t0, s1, 0x30
        addiu t1, s1, 0x210
sb_hide:
        lbu   t3, 0(t0)
        beqz  t3, sb_hide_next
        nop
        or    s2, s2, t2
        sb    zero, 0(t0)
sb_hide_next:
        addiu t0, t0, 0x30
        bne   t0, t1, sb_hide
        sll   t2, t2, 1
; -- point both blur passes at this half: S = 224 * viewport
        sll   t0, s0, 5
        sll   t1, s0, 8
        subu  t0, t1, t0                ; t0 = S
        subu  t2, zero, s0
        lui   t3, 0x3e60
        and   t2, t2, t3                ; S/1024 as a float: 0 or 0.21875
        sll   t4, s0, 23
        addu  t3, t3, t4                ; (S+224)/1024: 0.21875 or 0.4375
        lui   at, %hi(F2D_UV)
        sw    t2, %lo(F2D_UV+4)(at)     ; frame -> depth source v0
        sw    t3, %lo(F2D_UV+12)(at)    ; frame -> depth source v1
        lui   at, %hi(D2F_RECT)
        sw    t0, %lo(D2F_RECT+4)(at)   ; depth -> frame destination y0 = S
        addiu t1, t0, 224
        sw    t1, %lo(D2F_RECT+12)(at)  ; destination y1 = S + 224
        li    t1, 56
        lui   at, %hi(H1)
        sw    t1, %lo(H1)(at)           ; pass 1: 160x56 (4x, as 160x112 of 448 lines)
        li    t1, 112
        lui   at, %hi(H2)
        sw    t1, %lo(H2)(at)           ; pass 2: 320x112 (2x)
{GUARDS}
; -- full-screen XYOFFSET_1 and SCISSOR_1 for pass B
        li    a0, 0x18
        li    a1, 0x7200
        .word DSLL32
        jal   WriteOneReg               ; XYOFFSET_1 = (0x6c00, 0x7200)
        ori   a1, a1, 0x6c00
        li    a0, 0x40
        lui   a1, 0x01bf
        .word DSLL32
        lui   t0, 0x027f
        jal   WriteOneReg               ; SCISSOR_1 = x 0..639, y 0..447
        or    a1, a1, t0
; -- pass B: the blur, drawn over rows S..S+223 only
        move  a0, s1
        li    a1, 1
        jal   Render
        move  a2, s0
; -- the stock full-screen constants back
        lui   at, %hi(F2D_UV)
        sw    zero, %lo(F2D_UV+4)(at)
        lui   t0, 0x3ee0
        sw    t0, %lo(F2D_UV+12)(at)    ; 0.4375
        lui   at, %hi(D2F_RECT)
        sw    zero, %lo(D2F_RECT+4)(at)
        li    t0, 448
        sw    t0, %lo(D2F_RECT+12)(at)
        li    t0, 112
        lui   at, %hi(H1)
        sw    t0, %lo(H1)(at)
        li    t0, 224
        lui   at, %hi(H2)
        sw    t0, %lo(H2)(at)
; -- the blotches back
        li    t2, 1
        li    t3, 1
        addiu t0, s1, 0x30
        addiu t1, s1, 0x210
sb_show:
        and   t4, s2, t2
        beqz  t4, sb_show_next
        nop
        sb    t3, 0(t0)
sb_show_next:
        addiu t0, t0, 0x30
        bne   t0, t1, sb_show
        sll   t2, t2, 1
; -- this half's draw area again, for the mask and black-screen passes after
        lui   at, %hi(GSYS)
        lw    a0, %lo(GSYS)(at)
        jal   SetSplit
        move  a1, s0
sb_out:
        ld    ra, 0x00(sp)
        lq    s0, 0x10(sp)
        lq    s1, 0x20(sp)
        lq    s2, 0x30(sp)
        jr    ra
        addiu sp, sp, 0x40
"""


def _stock_words(base, hexwords):
    digits = "".join(hexwords.split())
    if len(digits) % 8:
        raise ValueError("stock table is not a whole number of words")
    return {base + i // 2: int(digits[i:i + 8], 16)
            for i in range(0, len(digits), 8)}


def _table(game):
    g = GAMES[game]
    t = _stock_words(g["CAVE"], g["STOCK"])
    for va, stock, _ins, _note in g["HOOKS"]:
        t[va] = stock
    return t


GR_STOCK = _table("gr")
JS_STOCK = _table("js")


def build(game):
    g = GAMES[game]
    syms = {k: v for k, v in g.items() if isinstance(v, int)}
    syms["DSLL32"] = DSLL32_A1_A1
    src = SRC.replace("{GUARDS}", _GUARDS if g["H1G"] else "")
    words, labels = assemble(src, g["CAVE"], syms)
    if g["CAVE"] + 4 * len(words) > g["CAVE_END"]:
        raise ValueError("%s hit-blur routines overflow their cave" % game)
    return words, labels, syms


def edits(game):
    g = GAMES[game]
    stock = GR_STOCK if game == "gr" else JS_STOCK
    words, labels, syms = build(game)
    out = [(g["CAVE"] + 4 * i, w, stock[g["CAVE"] + 4 * i], "split-screen hit blur: routine")
           for i, w in enumerate(words)]
    allsyms = dict(syms, **labels)
    for va, st, ins, note in g["HOOKS"]:
        out.append((va, assemble(ins, va, allsyms)[0][0], st, "split-screen hit blur: " + note))
    return out


def gr_edits(v):
    return edits("gr") if v.get("gr_ss_hitblur") else []


def js_edits(v):
    return edits("js") if v.get("js_ss_hitblur") else []


def selftest(gr_elf=None, js_elf=None):
    import struct
    fails = []
    for game, stock, elf, delta in (("gr", GR_STOCK, gr_elf, 0x80), ("js", JS_STOCK, js_elf, 0x100)):
        for va, _w, s, _n in edits(game):
            if stock.get(va) != s:
                fails.append("%s %08x: edit stock %08x, table %s" % (game, va, s, stock.get(va)))
        if elf is not None:
            for va, want in stock.items():
                got = struct.unpack_from("<I", elf, va - 0x00100000 + delta)[0]
                if got != want:
                    fails.append("%s stock %08x: disc %08x, recorded %08x" % (game, va, got, want))
    return fails

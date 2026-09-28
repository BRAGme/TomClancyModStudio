"""SELECT takes you to the copies: Jungle Storm (SLUS-20820).

Total war's allied copies are members 3 and up of their fireteam (x2: a
fireteam of you and 2 becomes members 0-4, the copy of member m at m + 2).
Jungle Storm has two ways to change soldier by hand and neither reaches them
reliably:

  - the command map (hold L1) steps through six slots, Alpha 1-3 and Bravo
    1-3, each one member 0, 1 or 2 of a fireteam: the originals only;
  - a SELECT press (the HUD handler at JS 0x002823C0) takes over the soldier
    IkeSimulationMgr's pick (vtable +0xA4, 0x0037AE80) answers: the friendly
    the HUD is naming under your crosshair, else a short ray. A copy behind
    foliage, out of range or off the reticle is not picked, and the press
    does nothing (a savestate log: 7 presses, 3 picks, 2 switches).

The pick call (0x002824EC, ``jalr t9``) now goes through a routine that
answers the pick when it found someone -- a soldier under the crosshair is
taken over exactly as before -- and otherwise the next living copy after
you in squad order: Alpha 3, 4, 5, Bravo 3, 4, 5, round again. The order key
is fireteam * 8 + member (SimHuman +0x448, +0x44C); members 0-2 are skipped,
so the L1 menu stays the originals and SELECT the copies. "Living" is the
rules manager's active flag (IkeRulesMgr vtable +0x134 gives the fireteam,
its member vector at +0x0C holds {id, active} pairs; vtable +0x118/+0x11C/
+0x120 read the same entries), the one FindNextTeamMember tests. The answer
is the soldier's SimHuman + 0x148, the pointer the pick itself returns
(IIkeObjectMgr vtable +0x38 gives SimHuman + 0x1B0), so the handler's own
checks and IkeSimulationMgr's switch (vtable +0x158) run on it unchanged. It
works while you lie dead, before the automatic hand-off: the switch is the
one that hand-off makes.

Active when total war copies the allies (js_tw_allies above 1). It replaces
an earlier fallback in the command map (a dead original's slot took his
copy), so the L1 menu is stock again. Caves: the twins of scePowerOffHandler
(0x0017E370, 36 words), SetDebugHandler (0x00182AD8, 33 words) and
sceScfGetLanguage (0x0019B808, 24 words), none referenced in the loaded
image or either overlay nor written by any other option. Not yet played.
"""

from __future__ import annotations

from .grasm import assemble

CAVE, CAVE_END = 0x0017E370, 0x0017E400      # scePowerOffHandler twin
CAVE2, CAVE2_END = 0x00182AD8, 0x00182B5C    # SetDebugHandler twin
CAVE3, CAVE3_END = 0x0019B808, 0x0019B868    # sceScfGetLanguage twin
HOOK, HOOK_STOCK = 0x002824EC, 0x0320F809    # jalr t9 = the pick (slot: addiu a3, sp, 0x68)

SYMS = dict(
    RULES=0x00124610,           # IIkeRulesMgr::Get
    OBJMGR=0x0014A7E0,          # IIkeObjectMgr::Get
    COMPANY=0x0057A1C8, PLATOON=0x0057A1D0,  # the player's squad
)

# In the handler: s0 = your id, s1 = IkeSimulationMgr, s4 = you (IIkeObjectMgr's
# SimHuman + 0x1B0). s2 and s3 are written by the handler after the pick before
# it reads them, and its epilogue restores them, so they are used unsaved here.
SRC = """
sel_pick:
    addiu sp, sp, -0x40
    sq    s5, 0x00(sp)
    sq    s6, 0x10(sp)
    sq    s7, 0x20(sp)
    sd    ra, 0x30(sp)
    jalr  t9                        ; the crosshair pick
    nop
    bnez  v0, sel_out               ; someone under the crosshair: as before
    lw    t0, 0x298(s4)             ; your fireteam (SimHuman +0x448)
    lw    t1, 0x29c(s4)             ; your member (+0x44C)
    sll   t0, t0, 3
    addu  s7, t0, t1                ; s7 = your key
    jal   RULES
    nop
    move  s5, v0                    ; s5 = the rules manager
    lw    t9, 0(s5)
    lw    t9, 0x114(t9)             ; fireteams in the platoon
    lui   at, %hi(COMPANY)
    lw    a1, %lo(COMPANY)(at)
    lui   at, %hi(PLATOON)
    lw    a2, %lo(PLATOON)(at)
    jalr  t9
    move  a0, s5
    sll   s6, v0, 3                 ; s6 = keys, 8 per fireteam
    b     sel_step
    li    s2, 1                     ; s2 = steps past your key
"""

SRC2 = """
sel_step:
    slt   t0, s2, s6
    beqz  t0, sel_none              ; round the platoon once: nobody
    addu  s3, s7, s2                ; s3 = the key
    sltu  t0, s3, s6
    bnez  t0, sel_key
    andi  t0, s3, 7                 ; (delay) his member
    subu  s3, s3, s6                ; wrap
    andi  t0, s3, 7
sel_key:
    sltiu t0, t0, 3
    bnez  t0, sel_next              ; members 0-2: the originals, on the L1 menu
    lw    t9, 0(s5)
    lw    t9, 0x134(t9)             ; the fireteam
    lui   at, %hi(COMPANY)
    lw    a1, %lo(COMPANY)(at)
    lui   at, %hi(PLATOON)
    lw    a2, %lo(PLATOON)(at)
    srl   a3, s3, 3
    jalr  t9
    move  a0, s5
    beqz  v0, sel_next
    andi  t1, s3, 7
    lw    t0, 0x10(v0)              ; members.count
    sltu  t0, t1, t0
    beqz  t0, sel_next
    lw    t0, 0xc(v0)               ; members: {id, active}, 8 bytes each
    sll   t1, t1, 3
    addu  t0, t0, t1
    lbu   t1, 4(t0)
    li    t2, 1
    beq   t1, t2, sel_found         ; alive
    lw    a1, 0(t0)                 ; (delay) his id
sel_next:
    b     sel_step
    addiu s2, s2, 1
"""

SRC3 = """
sel_found:
    jal   OBJMGR
    sw    a1, 0x38(sp)
    lw    t9, 0(v0)
    lw    a1, 0x38(sp)
    lw    t9, 0x38(t9)              ; his SimHuman + 0x1B0
    jalr  t9
    move  a0, v0
    beqz  v0, sel_out
    nop
    b     sel_out
    addiu v0, v0, -0x68             ; SimHuman + 0x148, as the pick answers
sel_none:
    move  v0, zero
sel_out:
    lq    s5, 0x00(sp)
    lq    s6, 0x10(sp)
    lq    s7, 0x20(sp)
    ld    ra, 0x30(sp)
    jr    ra
    addiu sp, sp, 0x40
"""

_CAVE_STOCK_HEX = (   # scePowerOffHandler twin, 0x0017E370..0x0017E400
    "27BDFFA0 FFB30030 FFB20020 0080982D FFB40040 00A0902D FFB00000 2404001B"
    "FFBF0050 3C100062 FFB10010 0C05F8CC 26148780 3C020057 8C434FEC 14600003"
    "00000000 0C05F918 00000000 0C060CC8 00000000 8E118780 3C030062 AE920004"
    "AE138780 AC7C87C0 10400003 00000000 0C060CDE 00000000 0C05F8D8 00000000"
    "0220102D DFBF0050 DFB40040 DFB30030"
)
_CAVE2_STOCK_HEX = (  # SetDebugHandler twin, 0x00182AD8..0x00182B5C
    "0080302D 27BDFFE0 24C4FFFF FFBF0010 2C82000D 14400004 FFB00000 3C02FFFF"
    "10000014 3442FFFF 3C020057 00061880 24425350 2C840003 00621821 8C700000"
    "10800007 AC650000 3C050018 00C0202D 0C05E7E4 24A53200 10000006 0200102D"
    "3C050018 00C0202D 0C05E7E8 24A53200 0200102D DFBF0010 DFB00000 03E00008"
    "27BD0020"
)
_CAVE3_STOCK_HEX = (  # sceScfGetLanguage twin, 0x0019B808..0x0019B868
    "27BDFFE0 FFBF0010 0C05E8E4 03A0202D 0C066DF2 00000000 10400003 3C020057"
    "1000000C 904268EC 0C05E8E4 03A0202D 8FA30000 00031342 30420007 54400004"
    "00031402 00031102 10000002 30420001 3042001F DFBF0010 03E00008 27BD0020"
)


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


JS_STOCK = _stock_words(CAVE, _CAVE_STOCK_HEX)
JS_STOCK.update(_stock_words(CAVE2, _CAVE2_STOCK_HEX))
JS_STOCK.update(_stock_words(CAVE3, _CAVE3_STOCK_HEX))
JS_STOCK[HOOK] = HOOK_STOCK


def _layout():
    """(cave, source): the pick and the setup, the search, the answer."""
    return [(CAVE, SRC), (CAVE2, SRC2), (CAVE3, SRC3)]


def edits():
    """(va, value, stock, note)."""
    pieces = _layout()
    labels = dict(sel_step=CAVE2, sel_out=CAVE3, sel_none=CAVE3, sel_found=CAVE3)   # first-pass stand-ins
    for _ in range(2):                      # the first pass sizes, the second resolves across caves
        out_words = []
        new = {}
        for base, src in pieces:
            w, l = assemble(src, base, dict(SYMS, **{k: v for k, v in labels.items() if k not in _local(src)}))
            out_words.append((base, w))
            new.update(l)
        labels = new
    ends = {CAVE: CAVE_END, CAVE2: CAVE2_END, CAVE3: CAVE3_END}
    out = []
    for base, w in out_words:
        if base + 4 * len(w) > ends[base]:
            raise ValueError("SELECT routine outgrows the cave at %#x (%d words, room %d)"
                             % (base, len(w), (ends[base] - base) // 4))
        out += [(base + 4 * i, x, JS_STOCK[base + 4 * i], "SELECT takes you to the copies: routine")
                for i, x in enumerate(w)]
    out.append((HOOK, assemble("jal %#x" % labels["sel_pick"], HOOK)[0][0], HOOK_STOCK,
                "SELECT takes you to the copies: nobody under the crosshair = the next living copy"))
    return out


def _local(src):
    return {ln.split(":")[0].strip() for ln in src.splitlines() if ln.strip().endswith(":")}


def js_edits(v: dict):
    return edits() if int(v.get("js_tw_allies", "1")) > 1 else []


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

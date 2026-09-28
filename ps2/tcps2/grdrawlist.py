"""The soldier draw sort: Ghost Recon (SLUS-20613) and Jungle Storm (SLUS-20820).

Each frame, per split-screen view, one routine (GR 0x00454600, JS 0x0041C040)
sorts the visible character instances by model so each model's state is set
once: 75 stack buckets of 0x40 bytes -- a count and 30 u16 instance indexes --
filled from the character list (count +0x130, pointers +0x134, an instance's
model +0x2F0, its visible flag +0x2DC + view), then two passes walk the
buckets (GR 0x00445290 / 0x00445240, JS 0x0040D900 / 0x0040DB30). Nothing
checks a bucket's count. The 31st visible instance of one model writes its
index over the next bucket's count, that count then indexes far past its
bucket, and the pass hands the draw call pointers read from the wrong place.

Stock never sees 30 of one model in a view. Total war does: Jungle Storm C03
at x4 lists 105 soldiers, 41 of them one model, and froze loading in with a
TLB miss inside 0x0040D900 (a pointer of 0x10), its model table overwritten.

The routine is rewritten in place with the same entry, frame and saved
registers. The buckets become a linked list per model: a head per model and a
next link per instance, both in the stock frame, built from the last instance
to the first so each model's list is in index order. The two passes walk the
lists model by model, so the draw calls come in exactly the stock order
(checked against the stock routine in an interpreter for populations stock
survives) with no per-model limit. Model numbers outside the model count are
skipped where stock would write outside its frame. Ghost Recon's third pass,
which does not use the buckets, is left as it was.

Played 2026-09-28: Jungle Storm C03 at x4 (128 MB) loads and plays.
"""

from __future__ import annotations

from .grasm import assemble

GAMES = {
    "gr": dict(
        FUNC=0x00454600,
        START=0x00454634,     # after the prologue and its jal (delay slot move128 s0,a1)
        END=0x004547A0,       # the unsorted third pass, kept
        LIST="s1", VIEW="s0", ST="s2", SI="s3", SJ="s4",
        HB=0x70, FRAME=0x1330,
        F1=0x00445290, F2=0x00445240,
        TAIL="    b     0x4547a0\n    nop\n",
    ),
    "js": dict(
        FUNC=0x0041C040,
        START=0x0041C070,     # after the prologue and its jal (delay slot move s4,a1)
        END=0x0041C1D8,       # the stock epilogue ends at 0x0041C1D4
        LIST="s0", VIEW="s4", ST="s1", SI="s2", SJ="s3",
        HB=0x60, FRAME=0x1320,
        F1=0x0040D900, F2=0x0040DB30,
        TAIL="""    ld    ra, 0x50(sp)
    lq    s4, 0x40(sp)
    lq    s3, 0x30(sp)
    lq    s2, 0x20(sp)
    lq    s1, 0x10(sp)
    lq    s0, 0(sp)
    jr    ra
    addiu sp, sp, 0x1320
""",
    ),
}

# heads: 128 s16 at sp+HB (the model table has 75 slots); next links from sp+HB+0x100
SRC = """
    lw    t0, 0({LIST})          ; model count
    sltiu t1, t0, 76
    bnez  t1, types_ok
    nop
    addiu t0, zero, 75           ; never happens: the model table has 75 slots
types_ok:
    addiu t3, sp, {HB}
    addiu t4, sp, {NB}
    addiu t5, zero, -1
clear:
    sh    t5, 0(t3)              ; every head = -1 (empty)
    addiu t3, t3, 2
    bne   t3, t4, clear
    nop
    lw    t7, 0x130({LIST})      ; instance count
    slti  t1, t7, {CAP1}
    bnez  t1, collect
    nop
    addiu t7, zero, {CAP}        ; never happens: the list holds 1000
collect:                         ; i = count-1 .. 0, pushed onto its model's list
    addiu t7, t7, -1
    bltz  t7, sorted
    sll   v1, t7, 2
    addu  v1, {LIST}, v1
    lw    a0, 0x134(v1)
    beqz  a0, collect
    addu  v1, {VIEW}, a0
    lbu   v1, 0x2dc(v1)          ; visible in this view
    beqz  v1, collect
    nop
    lw    v1, 0x2f0(a0)          ; model
    sltu  t1, v1, t0
    beqz  t1, collect            ; no such model: stock wrote outside its frame
    sll   v1, v1, 1
    addu  v1, v1, sp
    lh    t2, {HB}(v1)
    sh    t7, {HB}(v1)           ; head[model] = i
    sll   t1, t7, 1
    addu  t1, t1, sp
    b     collect
    sh    t2, {NB}(t1)           ; next[i] = the old head
sorted:
    move  {ST}, t0
{PASS1}{PASS2}{TAIL}"""

PASS = """    move  {SI}, zero
p{n}:
    slt   v1, {SI}, {ST}
    beqz  v1, p{n}end
    sll   v1, {SI}, 1
    addu  v1, v1, sp
    lh    {SJ}, {HB}(v1)
p{n}q:
    bltz  {SJ}, p{n}next
    sll   v1, {SJ}, 2
    addu  v1, {LIST}, v1
    lw    a0, 0x134(v1)          ; re-read, as stock does
    beqz  a0, p{n}r
    move  a1, {VIEW}
    jal   {F}
    nop
p{n}r:
    sll   v1, {SJ}, 1
    addu  v1, v1, sp
    b     p{n}q
    lh    {SJ}, {NB}(v1)
p{n}next:
    b     p{n}
    addiu {SI}, {SI}, 1
p{n}end:
"""


def source(game: str) -> str:
    g = dict(GAMES[game])
    g["NB"] = "%#x" % (g["HB"] + 0x100)
    cap = (g["FRAME"] - g["HB"] - 0x100) // 2
    g["CAP"], g["CAP1"] = cap, cap + 1
    g["HB"] = "%#x" % g["HB"]
    passes = [PASS.format(n=n, F="%#x" % g["F%d" % n], **g) for n in (1, 2)]
    return SRC.format(PASS1=passes[0], PASS2=passes[1], **g)


def words(game: str):
    g = GAMES[game]
    w, _ = assemble(source(game), g["START"])
    if g["START"] + 4 * len(w) > g["END"]:
        raise ValueError("draw sort outgrows the routine it replaces")
    return w


_GR_STOCK_HEX = (   # 0x00454634..0x004547A0
    "27A30070 27A41330 AC600000 24630040 00000000 00000000 00000000 1464FFFA"
    "00000000 70002E28 10000014 70003628 8C640134 50800010 24C60004 02041821"
    "906302DC 1060000B 00000000 8C8302F0 00031980 007D1821 24670070 8CE40000"
    "24830001 ACE30000 00041840 00E31821 A4650004 24C60004 24A50001 8E230130"
    "00A3182A 1460FFEA 02261821 70009628 10000016 7000AE28 1000000C 7000A628"
    "00941821 94630004 00031880 02231821 8C640134 50800004 26940002 0C1114A4"
    "72002E28 26940002 26730001 02BD1821 24640070 8C830000 0263182A 1460FFF1"
    "00941821 26B50040 26520001 8E230000 0243182A 1460FFE8 70009E28 70009628"
    "10000016 7000AE28 1000000C 7000A628 00941821 94630004 00031880 02231821"
    "8C640134 50800004 26940002 0C111490 00000000 26940002 26730001 02BD1821"
    "24640070 8C830000 0263182A 1460FFF1 00941821 26B50040 26520001 8E230000"
    "0243182A 1460FFE8 70009E28"
)
_JS_STOCK_HEX = (   # 0x0041C070..0x0041C1D8
    "27A40060 27A31320 AC800000 24840040 00000000 00000000 1483FFFB 00000000"
    "10000013 0000302D 02031821 8C640134 1080000E 02841821 906302DC 1060000B"
    "00000000 8C8302F0 00031980 007D1821 24650060 8CA30000 24640001 00031840"
    "ACA40000 00A31821 A4660004 24C60001 8E030130 00C3182A 1460FFEB 00061880"
    "10000014 0000982D 0000902D 007D1821 1000000B 24710060 02231821 94630004"
    "00031880 02031821 8C640134 10800003 0280282D 0C103640 00000000 26520001"
    "8E230000 0243182A 1460FFF3 00121840 26730001 8E030000 0263182A 1460FFEA"
    "00131980 10000014 0000982D 0000902D 007D1821 1000000B 24710060 02231821"
    "94630004 00031880 02031821 8C640134 10800003 00000000 0C1036CC 00000000"
    "26520001 8E230000 0243182A 1460FFF3 00121840 26730001 8E030000 0263182A"
    "1460FFEA 00131980 DFBF0050 7BB40040 7BB30030 7BB20020 7BB10010 7BB00000"
    "03E00008 27BD1320"
)


def _stock_words(base, hexwords):
    ws = "".join(hexwords.split())
    return {base + 4 * i: int(ws[8 * i:8 * i + 8], 16) for i in range(len(ws) // 8)}


GR_STOCK = _stock_words(GAMES["gr"]["START"], _GR_STOCK_HEX)
JS_STOCK = _stock_words(GAMES["js"]["START"], _JS_STOCK_HEX)


def edits(game: str):
    """(va, value, stock, note) -- only the words that change."""
    g = GAMES[game]
    st = GR_STOCK if game == "gr" else JS_STOCK
    out = []
    for i, w in enumerate(words(game)):
        va = g["START"] + 4 * i
        if w != st[va]:
            out.append((va, w, st[va], "total war: soldier draw sort without the 30-per-model limit"))
    return out


def selftest(gr_elf: bytes, js_elf: bytes):
    """Every stock word against the executables, the rewrite inside its routine. [] = pass."""
    bad = []
    for game, st, elf, d in (("gr", GR_STOCK, gr_elf, 0x80), ("js", JS_STOCK, js_elf, 0x100)):
        g = GAMES[game]
        if sorted(st) != list(range(g["START"], g["END"], 4)):
            bad.append("%s stock table does not cover the routine" % game)
        for va, w in st.items():
            off = va - 0x100000 + d
            if int.from_bytes(elf[off:off + 4], "little") != w:
                bad.append("%s %08X" % (game, va))
        try:
            e = edits(game)
        except ValueError as ex:
            bad.append("%s %s" % (game, ex))
            continue
        if any(va not in st for va, *_ in e):
            bad.append("%s VA without a stock word" % game)
    return bad

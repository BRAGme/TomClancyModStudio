"""Enemies lay down suppressive fire when they lose sight of you: Jungle Storm (SLUS-20820).

Jungle Storm's soldiers seldom suppress: a diagnostic build counted one
SuppressBehavior in 130 s of a firefight, and none in another. The game makes
them only from team behaviours (open fight, defending a zone) under
conditions a squad in the jungle rarely meets.

EngageThreatBehavior::Process (JS 0x001AD4C0) asks every frame whether its
threat is still in sight -- IkeSimulationMgr::LineOfSightClear (0x0037AA80,
called at 0x001AD988) -- and when not, sets state 4, "clearing LOS". That call
now goes through a routine that answers exactly as before and, on the frame
sight is first lost (the answer is no and the state is not yet 4), with a
one-in-two roll, hands the soldier a SuppressBehavior on the threat's
position (his controller at +0x1C, vtable +0x32C). It is built the way the
game's own open-fight code builds one (JS 0x001B5190): SuppressLOSClear
(0x003E9710, 30 degrees) must agree, new 0x5C, the constructor 0x001B8490,
the point at +0x34, type 1 at +0x24, an end time of now + 3-7 s at +0x18
(RSRandom::Float 0x001129C0; clock 0x00684768 +0xD4), then RSScript::
AddElement (0x001B6E10) puts it on top of the soldier's script. He fires at
the spot for a few seconds, then the engagement carries on where it was.

'Enemies throw grenades' uses the same moment. grfrag's decision was asked
only when an engagement starts and under suppression, and a savestate after
a firefight had every living enemy 49-273 m from the player (median 145 m):
engagements start far beyond the 10-35 m of a hand throw, and 295 engagement
starts queued no grenade. With that option on, the frame sight is first lost
asks grfrag's decision (grfrag.CAVE) at the threat's position with a
roll (one in two by default) -- he ducked behind cover, often close -- and a queued throw
replaces the suppression. The hook is in when either option is on, each part
only when its option is.

Caves: the twins of sceVu0ViewScreenMatrix (0x001975B8, 65 words: the
decision) and sceSifUnloadModule (0x00182140, 36 words: the build), neither
referenced in the loaded image or either overlay nor written by any other
option. Not yet played.

Ghost Recon (SLUS-20613)
------------------------

gr_enemy_suppress, the same behaviour. Ghost Recon's EngageThreatBehavior::
Process (0x001B2990) is the code Jungle Storm inherited, with the same
registers (s1 the HumanAI, s2 the behaviour, state at +0x24, threat at
+0x1C); the hook is its ``jal IkeSimulationMgr::LineOfSightClear``
(0x0039CD10) at 0x001B2E38. The threat's position is its controller's vtable
+0x328 (Jungle Storm +0x32C). The SuppressBehavior is built as Ghost Recon's
OpenFight builds one (0x001B8BA8): SuppressLOSClear (0x00199780) at 30
degrees, new 0x58 (0x00102DB0), the constructor 0x001BD510, point +0x34, type
1 at +0x24, end time now + 3-7 s at +0x18 (RSRandom::Float 0x00113DC0, rng
0x005DF770, clock 0x005DFC20 +0xD4), RSScript::AddElement 0x001BAEC0. With
'Enemies throw grenades more readily' (gr_enemy_grenades) on, the frame sight
is lost first asks grfrag's Ghost Recon decision (grfrag.GR_DECIDE) with
gr_enemy_frag_chance's sight-lost roll, as in Jungle Storm. One cave holds
the decision and the build: sceDevConsDrawS (0x0040DC18..0x0040DDC4, 107
words), unreferenced and written by no other option.
"""

from __future__ import annotations

from . import grfrag
from .grasm import assemble

CAVE, CAVE_END = 0x001975B8, 0x001976BC     # sceVu0ViewScreenMatrix twin: the decision
CAVE2, CAVE2_END = 0x00182140, 0x001821D0   # sceSifUnloadModule twin: the SuppressBehavior
HOOK, HOOK_STOCK = 0x001AD988, 0x0C0DEAA0     # jal LineOfSightClear (slot: addiu a2, sp, 0x90)
CHANCE = 0x3F00                               # upper half of 0.5

SYMS = dict(
    LOSClear=0x0037AA80, SuppressLOSClear=0x003E9710, SUPPRESS_ARC=0x00583D60,
    New=0x00103470, SuppressCtor=0x001B8490, AddElement=0x001B6E10,
    RandomFloat=0x001129C0, RNG=0x00613510, CLOCK=0x00684768,
)

# s1 = the HumanAI, s2 = the EngageThreatBehavior (EngageThreatBehavior::Process's registers)
SRC = """
sup_los:                            ; LineOfSightClear's arguments -> its answer
    addiu sp, sp, -0x40
    sq    s0, 0x00(sp)
    sq    s3, 0x10(sp)
    sq    s4, 0x20(sp)
    sd    ra, 0x30(sp)
    jal   LOSClear
    nop
    bnez  v0, sl_out                ; still in sight
    move  s0, v0
    lw    t0, 0x24(s2)              ; engagement state
    li    t1, 4
    beq   t0, t1, sl_out            ; sight was lost before this frame
    lw    a0, 0x1c(s2)              ; (delay) the threat
    beqz  a0, sl_out
    nop
    lw    t9, 0(a0)
    lw    t9, 0x32c(t9)             ; his position
    jalr  t9
    nop
    beqz  v0, sl_out
    move  s3, v0
{frag}{suppress}sl_out:
    move  v0, s0
    lq    s0, 0x00(sp)
    lq    s3, 0x10(sp)
    lq    s4, 0x20(sp)
    ld    ra, 0x30(sp)
    jr    ra
    addiu sp, sp, 0x40
"""

# 'Enemies throw grenades': grfrag's decision, at the spot he went to ground
SRC_FRAG = """
    move  a1, s1
    move  a2, s3
    jal   decide
    lui   a3, {CHANCE_FRAG}
    bnez  v0, sl_out                ; a grenade is on its way: no suppression
    nop
"""

# 'Enemies suppress': the roll, then SuppressLOSClear, then the behaviour (second cave)
SRC_SUPPRESS = """
    lui   a0, %hi(RNG)
    addiu a0, a0, %lo(RNG)
    move  a1, zero
    move  a2, zero
    mtc1  zero, $f12
    lui   v0, 0x3f80
    jal   RandomFloat               ; 0..1
    mtc1  v0, $f13
    lui   v0, {CHANCE}
    mtc1  v0, $f1
    nop
    c.lt.s $f0, $f1
    bc1f  sl_out
    move  a0, s1
    move  a1, s3
    lui   at, %hi(SUPPRESS_ARC)
    jal   SuppressLOSClear          ; can he put rounds there at all
    lwc1  $f12, %lo(SUPPRESS_ARC)(at)
    beqz  v0, sl_out
    nop
    b     sl_make
    nop
"""

# the second cave: build it and put it on his script
SRC2 = """
sl_make:
    jal   New
    li    a0, 0x5c
    beqz  v0, sl_out
    nop
    jal   SuppressCtor
    move  a0, v0
    move  s4, v0
    lwc1  $f0, 0x0(s3)
    swc1  $f0, 0x34(s4)
    lwc1  $f0, 0x4(s3)
    swc1  $f0, 0x38(s4)
    lwc1  $f0, 0x8(s3)
    swc1  $f0, 0x3c(s4)
    li    v0, 1
    sw    v0, 0x24(s4)
    lui   a0, %hi(RNG)
    addiu a0, a0, %lo(RNG)
    move  a1, zero
    move  a2, zero
    lui   v0, 0x4040                ; 3 s
    mtc1  v0, $f12
    lui   v0, 0x40e0                ; 7 s
    jal   RandomFloat
    mtc1  v0, $f13
    lui   at, %hi(CLOCK)
    lw    v1, %lo(CLOCK)(at)
    lwc1  $f1, 0xd4(v1)             ; now
    add.s $f0, $f0, $f1
    swc1  $f0, 0x18(s4)             ; until
    lw    a0, 0xc(s1)               ; on top of his script
    jal   AddElement
    move  a1, s4
    b     sl_out
    nop
"""

_CAVE2_STOCK_HEX = (  # sceSifUnloadModule twin, 0x00182140..0x001821D0
    "27BDFFC0 FFB10020 FFBF0030 0080882D 0C06068E FFB00010 04400018 3C02FFFF"
    "0C0606CE 00000000 10400004 3C100062 3C02FFFE 10000011 3442FFFC 3C040062"
    "260789C0 AE1189C0 24848BC0 AFA00000 2405000A 0000302D 24080004 00E0482D"
    "240A0004 0C05F5AA 0000582D 04430003 8E0289C0 3C02FFFE 3442FFFF DFBF0030"
    "DFB10020 DFB00010 03E00008 27BD0040"
)
_CAVE_STOCK_HEX = (   # sceVu0ViewScreenMatrix twin, 0x001975B8..0x001976BC
    "27BDFF60 46008807 E7B40060 46009507 C7A100A0 E7B50068 46120000 46130D42"
    "FFB00040 4613A502 0080802D 46018C42 E7BA0090 46009CC7 E7B90088 4600AD42"
    "E7B80080 4611A500 E7B70078 46019CC0 E7B60070 46006586 46006E06 460075C6"
    "46007E86 00000000 00000000 4613AD43 00000000 00000000 4613A503 FFBF0050"
    "0C065BD6 46008646 3C013F80 44810000 03A0202D E6160014 E6160000 AE000028"
    "AE00003C E600002C 0C065BD6 E6000038 0200202D E7B80000 E7B70014 03A0282D"
    "E7B50028 0080302D E7BA0030 E7B90034 0C0659AC E7B40038 DFBF0050 DFB00040"
    "C7BA0090 C7B90088 C7B80080 C7B70078 C7B60070 C7B50068 C7B40060 03E00008"
    "27BD00A0"
)


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


JS_STOCK = _stock_words(CAVE, _CAVE_STOCK_HEX)
JS_STOCK.update(_stock_words(CAVE2, _CAVE2_STOCK_HEX))
JS_STOCK[HOOK] = HOOK_STOCK


def edits(suppress: bool = True, frag: bool = False, chance: str = "normal"):
    """(va, value, stock, note). suppress: the SuppressBehavior; frag: grfrag's decision first, with
    grfrag.FRAG_CHANCES[chance]'s sight-lost roll."""
    if not suppress and not frag:
        return []
    src = SRC.format(frag=SRC_FRAG.format(CHANCE_FRAG=hex(grfrag.FRAG_CHANCES[chance][0])) if frag else "",
                     suppress=SRC_SUPPRESS.format(CHANCE=hex(CHANCE)) if suppress else "")
    syms = dict(SYMS, decide=grfrag.CAVE)
    out = []
    if suppress:
        w2, l2 = assemble(SRC2, CAVE2, dict(syms, sl_out=CAVE))                 # sizes: sl_out a stand-in
        w1, l1 = assemble(src, CAVE, dict(syms, sl_make=l2["sl_make"]))
        w2, l2 = assemble(SRC2, CAVE2, dict(syms, sl_out=l1["sl_out"]))
    else:
        w1, l1 = assemble(src, CAVE, syms)
        w2 = []
    if CAVE + 4 * len(w1) > CAVE_END or CAVE2 + 4 * len(w2) > CAVE2_END:
        raise ValueError("suppression routine outgrows its caves (%d/%d, %d/%d words)"
                         % (len(w1), (CAVE_END - CAVE) // 4, len(w2), (CAVE2_END - CAVE2) // 4))
    what = " and ".join(x for x, on in (("grenade", frag), ("suppression", suppress)) if on)
    out += [(CAVE + 4 * i, w, JS_STOCK[CAVE + 4 * i], "sight lost: the decision (%s)" % what)
            for i, w in enumerate(w1)]
    out += [(CAVE2 + 4 * i, w, JS_STOCK[CAVE2 + 4 * i], "enemy suppression: the SuppressBehavior")
            for i, w in enumerate(w2)]
    out.append((HOOK, assemble("jal %#x" % l1["sup_los"], HOOK)[0][0], HOOK_STOCK,
                "sight lost: losing sight of the threat may bring a %s" % what))
    return out


def js_edits(v: dict):
    return edits(bool(v.get("js_enemy_suppress")), bool(v.get("js_enemy_grenades")),
                 v.get("js_enemy_frag_chance", "normal"))


# ---------------------------------------------------------------------------
# Ghost Recon (SLUS-20613)
# ---------------------------------------------------------------------------

GR_CAVE, GR_CAVE_END = 0x0040DC18, 0x0040DDC4      # sceDevConsDrawS: the decision, then the behaviour
GR_HOOK, GR_HOOK_STOCK = 0x001B2E38, 0x0C0E7344    # jal LineOfSightClear (slot: addiu a2, sp, 0x98)

GR_SYMS = dict(
    LOSClear=0x0039CD10, SuppressLOSClear=0x00199780, New=0x00102DB0, SuppressCtor=0x001BD510,
    AddElement=0x001BAEC0, RandomFloat=0x00113DC0, RNG=0x005DF770, CLOCK=0x005DFC20,
)

# s1 = the HumanAI, s2 = the EngageThreatBehavior (Ghost Recon's EngageThreatBehavior::Process keeps the
# same registers); the threat's position is its controller's vtable +0x328 in Ghost Recon (JS +0x32C)
GR_SRC = """
sup_los:                            ; LineOfSightClear's arguments -> its answer
    addiu sp, sp, -0x40
    sq    s0, 0x00(sp)
    sq    s3, 0x10(sp)
    sq    s4, 0x20(sp)
    sd    ra, 0x30(sp)
    jal   LOSClear
    nop
    bnez  v0, sl_out                ; still in sight
    move  s0, v0
    lw    t0, 0x24(s2)              ; engagement state
    li    t1, 4
    beq   t0, t1, sl_out            ; sight was lost before this frame
    lw    a0, 0x1c(s2)              ; (delay) the threat
    beqz  a0, sl_out
    nop
    lw    t9, 0(a0)
    lw    t9, 0x328(t9)             ; his position
    jalr  t9
    nop
    beqz  v0, sl_out
    move  s3, v0
{frag}{suppress}sl_out:
    move  v0, s0
    lq    s0, 0x00(sp)
    lq    s3, 0x10(sp)
    lq    s4, 0x20(sp)
    ld    ra, 0x30(sp)
    jr    ra
    addiu sp, sp, 0x40
"""

# 'Enemies suppress': the roll, then SuppressLOSClear (30 degrees, as OpenFight asks it), then the behaviour
GR_SRC_SUPPRESS = """
    lui   a0, %hi(RNG)
    addiu a0, a0, %lo(RNG)
    move  a1, zero
    move  a2, zero
    mtc1  zero, $f12
    lui   v0, 0x3f80
    jal   RandomFloat               ; 0..1
    mtc1  v0, $f13
    lui   v0, {CHANCE}
    mtc1  v0, $f1
    nop
    c.lt.s $f0, $f1
    bc1f  sl_out
    move  a0, s1
    move  a1, s3
    lui   at, 0x3f06                ; 30 degrees
    ori   at, at, 0x0a92
    jal   SuppressLOSClear          ; can he put rounds there at all
    mtc1  at, $f12
    beqz  v0, sl_out
    nop
    b     sl_make
    nop
"""

# the behaviour, built as OpenFight builds one (0x001B8BB4): new 0x58, the constructor, point, type 1,
# an end time 3-7 s from now, on top of his script
GR_SRC2 = """
sl_make:
    jal   New
    li    a0, 0x58
    beqz  v0, sl_out
    nop
    jal   SuppressCtor
    move  a0, v0
    move  s4, v0
    lwc1  $f0, 0x0(s3)
    swc1  $f0, 0x34(s4)
    lwc1  $f0, 0x4(s3)
    swc1  $f0, 0x38(s4)
    lwc1  $f0, 0x8(s3)
    swc1  $f0, 0x3c(s4)
    li    v0, 1
    sw    v0, 0x24(s4)
    lui   a0, %hi(RNG)
    addiu a0, a0, %lo(RNG)
    move  a1, zero
    move  a2, zero
    lui   v0, 0x4040                ; 3 s
    mtc1  v0, $f12
    lui   v0, 0x40e0                ; 7 s
    jal   RandomFloat
    mtc1  v0, $f13
    lui   at, %hi(CLOCK)
    lw    v1, %lo(CLOCK)(at)
    lwc1  $f1, 0xd4(v1)             ; now
    add.s $f0, $f0, $f1
    swc1  $f0, 0x18(s4)             ; until
    lw    a0, 0xc(s1)               ; on top of his script
    jal   AddElement
    move  a1, s4
    b     sl_out
    nop
"""

_GR_CAVE_STOCK_HEX = (   # sceDevConsDrawS, 0x0040DC18..0x0040DDC4
    "27BDFF20 AFA40020 FFB600A0 24040002 FFB50090 FFB40080 FFBF00D0 0000A02D"
    "FFBE00C0 FFB700B0 FFB30070 FFB20060 FFB10050 FFB00040 0C103C14 AFA0002C"
    "AFA20024 03A0202D 8FA20020 3C057000 8C430004 8C560000 AFA30028 0C10AC3A"
    "8C550008 3C057000 27A40010 0C10AC3A 34A52000 8FA30024 8C620000 34420040"
    "AC620000 8FA20028 1040003A 0000202D 12C00032 0000982D 8FA30020 27BE0004"
    "26970001 24630018 AFA30030 00000000 8FA2002C 02D38023 24030004 00029100"
    "03B28821 2E020005 0062800A 0C10AC3E 0220202D 8FA2002C 02A0402D 8FA50030"
    "0200482D 38420001 0260302D AFA2002C 0220202D 0280382D 0C103A62 02709821"
    "0220202D 0000282D 0000302D 0C10AC76 0000382D 0C10AC42 0220202D 0000202D"
    "0C1041CC 0000282D 03D29021 3C038000 8E450000 8FA40024 30A53FFF 0C103CE8"
    "00A32825 00108040 0276102B 1440FFD8 02B0A821 10000003 8FA30028 26970001"
    "8FA30028 02E0A02D 0283102B 1440FFC8 0000202D 0C1041CC 0000282D DFBF00D0"
    "DFBE00C0 DFB700B0 DFB600A0 DFB50090 DFB40080 DFB30070 DFB20060 DFB10050"
    "DFB00040 03E00008 27BD00E0"
)

GR_STOCK = _stock_words(GR_CAVE, _GR_CAVE_STOCK_HEX)
GR_STOCK[GR_HOOK] = GR_HOOK_STOCK
assert len(GR_STOCK) == (GR_CAVE_END - GR_CAVE) // 4 + 1


def gr_edits_for(suppress: bool = True, frag: bool = False, chance: str = "normal"):
    """Ghost Recon (va, value, stock, note). frag: grfrag's Ghost Recon decision first (gr_enemy_grenades)."""
    if not suppress and not frag:
        return []
    src = GR_SRC.format(frag=SRC_FRAG.format(CHANCE_FRAG=hex(grfrag.FRAG_CHANCES[chance][0])) if frag else "",
                        suppress=GR_SRC_SUPPRESS.format(CHANCE=hex(CHANCE)) if suppress else "")
    syms = dict(GR_SYMS, decide=grfrag.GR_DECIDE)
    words, labels = assemble(src + (GR_SRC2 if suppress else ""), GR_CAVE, syms)
    if GR_CAVE + 4 * len(words) > GR_CAVE_END:
        raise ValueError("GR suppression routine outgrows its cave (%d/%d words)"
                         % (len(words), (GR_CAVE_END - GR_CAVE) // 4))
    what = " and ".join(x for x, on in (("grenade", frag), ("suppression", suppress)) if on)
    out = [(GR_CAVE + 4 * i, w, GR_STOCK[GR_CAVE + 4 * i], "sight lost: the decision (%s)" % what)
           for i, w in enumerate(words)]
    out.append((GR_HOOK, assemble("jal %#x" % labels["sup_los"], GR_HOOK)[0][0], GR_HOOK_STOCK,
                "sight lost: losing sight of the threat may bring a %s" % what))
    return out


def gr_edits(v: dict):
    return gr_edits_for(bool(v.get("gr_enemy_suppress")), bool(v.get("gr_enemy_grenades")),
                        v.get("gr_enemy_frag_chance", "normal"))


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
        for sup, frag in ((True, False), (False, True), (True, True)):
            for chance in grfrag.FRAG_CHANCES:
                try:
                    e = fn(sup, frag, chance)
                except ValueError as ex:
                    bad.append("%s %s/%s/%s: %s" % (game, sup, frag, chance, ex))
                    continue
                if len({va for va, *_ in e}) != len(e):
                    bad.append("%s duplicate VA" % game)
                if any(va not in st for va, *_ in e):
                    bad.append("%s VA without a stock word" % game)
    return bad

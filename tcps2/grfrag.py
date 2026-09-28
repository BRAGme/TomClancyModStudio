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
throw grenades more readily' sets: indoors too, 10-35 m by hand (10-75 m with a
launcher). The friendly and 30 s checks in IsOkToFragHereNow stay. Three
places ask it:

  * suppressive fire -- the call to StartSpraying in SuppressBehavior::Process
    (0x001B8984), at the point it would have sprayed, every time (as Ghost
    Recon). No: StartSpraying, as before;
  * the start of an engagement -- EngageThreatBehavior::Process (0x001AD4C0)
    state 0 calls its spray-or-aim starter 0x001ADD60 once per target (the only
    call, 0x001ADA54). The routine is asked first, at the threat's position
    (the threat's controller at +0x1C, vtable +0x32C), with a one-in-three
    roll. A throw leaves the engagement in state 0: the throw goes on top of
    the soldier's script (RSScript::AddElement pushes), and when it is done the
    engagement asks again -- the team's 30 s wait then says no and it aims.
    Jungle Storm's enemies seldom suppress (once in 130 s of a firefight in a
    save state).
  * the frame a soldier loses sight of the threat he is engaging -- through
    grsuppress's hook on EngageThreatBehavior's LOS call (0x001AD988), at the
    threat's position, one time in two. A later savestate showed why the two
    above were not enough: 295 engagement starts and no grenade queued, with
    every living enemy 49-273 m away. Engagements start far beyond a hand
    throw; losing sight of you behind cover is when they are close.

A diagnostic build showed a queued throw that never left the hand:
FragLocationBehavior::Process (0x001B0820) drops the throw when anything lies
within 10 m along the throw's arc (HumanAI::FragLOSBlocked 0x003E9570), which
in the jungle is nearly always. The distance is now 4 m (0x001B09B0).

Caves: sceDread (0x00180160..0x001802B8) holds the decision and
sceSifGetOtherData (0x0017D220..0x0017D378) the throw and the two entries;
both are unreferenced in the loaded image and in both overlays, and near enough
for a branch. Not yet played.
"""

from __future__ import annotations

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
CHANCE_SUPPRESS = 0x3F80     # upper half of 1.0: always, as Ghost Recon
CHANCE_ENGAGE = 0x3EAB       # 0.334: one engagement in three

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
    lui   v0, 0x4499             ; 35 m by hand
    c.lt.s f2, f1
    bc1t  no
    ori   v0, v0, 0x2000
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
JS_STOCK[HOOK] = HOOK_STOCK
JS_STOCK[ENGAGE_HOOK] = ENGAGE_HOOK_STOCK
JS_STOCK[LOS] = LOS_STOCK


def _assemble():
    """(decision words, second-cave words, second-cave labels)."""
    src2 = SRC2.format(CHANCE_SUPPRESS=hex(CHANCE_SUPPRESS), CHANCE_ENGAGE=hex(CHANCE_ENGAGE))
    words2, labels2 = assemble(src2, CAVE2, dict(SYMS, decide=CAVE))
    words, labels = assemble(SRC, CAVE, dict(SYMS, no=labels2["no"], level=labels2["level"]))
    assert labels["decide"] == CAVE
    if CAVE + 4 * len(words) > CAVE_END or CAVE2 + 4 * len(words2) > CAVE2_END:
        raise ValueError("grenade routine outgrows its caves")
    return words, words2, labels2


def edits():
    """(va, value, stock, note)."""
    words, words2, labels2 = _assemble()
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
    return out


def js_edits(v: dict):
    return edits() if v.get("js_enemy_grenades") else []


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

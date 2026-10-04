"""A quick trigger finger: Ghost Recon (SLUS-20613) and Jungle Storm (SLUS-20820).

The trigger is a per-frame level: SimHuman::UpdateActions (GR 0x003CFFA0)
compares this frame's use-item bit with last frame's and calls
StartUsingFirearm on the press and ContinueUsingFirearm every frame it is
held. StartUsingFirearm (GR 0x003D22F0, JS 0x003B18E0) throws the press away
when it comes sooner than one round-interval (60 / rounds-per-minute s, 67-100
ms for most rifles) after the gun's last round -- and Continue only keeps a
burst going, never starts one. So releasing and pressing again quickly leaves
R1 held down on a gun that will not fire until it is let go and pressed again.

The press is kept for the players' own soldiers (control type +0x138 is 0;
the AI's 1 keeps the stock rule), unless the gun has no rate of fire (the
stock rule again). Neither game can then fire faster than the gun's rate:

  * Ghost Recon starts a burst at now - one frame and fires its first round a
    full interval later, so a kept press never beats the rate -- the first
    round comes at the same delay as any other press;
  * Jungle Storm starts a burst one interval back, so its first round leaves
    at once -- which is why it needs the rule. A kept press starts the burst
    at the gun's last round instead, so the first round leaves exactly one
    interval after it, the same moment it would have had R1 never been let go.

Cave: _id2type (GR 0x00427978, JS 0x00192A40), unreferenced in the loaded
image and in Jungle Storm's online/offline overlays.

Played (2026-10-04): the kept press was not the whole story -- a short tap still
fired nothing in Ghost Recon, and a quick tap after a burst fired nothing in
either game. See "a short tap fires" below: GR's first round now leaves on the
press, and in both games a full-auto tap released before its round fires that
round when the rate allows, then ends. Checked in an interpreter on savestates
(scratchpad trig/tapsuite.py, jtaps.py), not yet played.
"""

from __future__ import annotations

from .grasm import assemble

GAMES = {
    "gr": dict(
        CAVE=0x00427978, CAVE_END=0x004279F8,
        HOOK=0x003D2448, HOOK_STOCK=0x4600A034,     # c.lt.s f20,f0 (elapsed < interval); slot: nop
        ELAPSED="f20", INTERVAL="f0", OPT="s1",      # s1 = the gun's selective option (u16 rpm at +0)
        GO=0x003D2458, DROP=0x003D2598,              # the burst start / the epilogue
    ),
    "js": dict(
        CAVE=0x00192A40, CAVE_END=0x00192AC0,
        HOOK=0x003B1A8C, HOOK_STOCK=0x46140034,     # c.lt.s f0,f20
        SLOT=0x003B1A90, SLOT_STOCK=0x4501003B,     # bc1t (the drop) -- now the jump's slot, a nop
        ELAPSED="f0", INTERVAL="f20", OPT="s0",
        GO=0x003B1A98, DROP=0x003B1B80,
        START=0x003B1ACC, START_STOCK=0xE6400244,   # swc1 f0,0x244(s2): burst start = now - interval
    ),
}

# replaces the cooldown test; s2 = the SimHuman
KEEP_SRC = """
    c.lt.s {ELAPSED}, {INTERVAL}     ; stock: sooner than one interval after the last round
    lw    v1, 0x138(s2)              ; control type: 1 = AI
    addiu at, zero, 1
    bc1f  go                         ; not too soon: as shipped
    lhu   v0, 0({OPT})               ; rounds per minute
    beq   v1, at, drop               ; the AI: dropped, as shipped
    nop
    bnez  v0, go                     ; a player's press is kept, if the gun has a rate
    nop
drop:
    j     {DROP:#x}
    nop
go:
    j     {GO:#x}
    nop
"""

# Jungle Storm: the burst start, never before the gun's last round (players only)
START_SRC = """
    lw    v1, 0x138(s2)              ; control type: 1 = AI
    addiu at, zero, 1
    beq   v1, at, store              ; the AI: as shipped
    lwc1  f1, 0x24c(s2)              ; the gun's last round
    c.lt.s f0, f1                    ; would the burst start before it?
    nop
    bc1f  store
    nop
    mov.s f0, f1                     ; then start it there: first round one interval after it
store:
    jr    ra
    swc1  f0, 0x244(s2)
"""

_GR_CAVE_STOCK_HEX = (   # _id2type, 0x00427978..0x004279F8
    "27BDFF80 3C030057 FFB70070 30C2FFFF FFB60060 0006763A FFB50050 0006683E"
    "FFB40040 0002603C 000C603F FFB30030 2463F0C0 FFB20020 0000502D FFB10010"
    "0000482D FFB00000 340BFFFF 000B5E38 3417FF00 0017BE38 2416FFFF 0016B63A"
    "2415FFFF 0015AA3C 0015AE3A 3414BD20 0014A638 3413BD80 00139E38 3412BD90"
)
_JS_CAVE_STOCK_HEX = (   # its twin, 0x00192A40..0x00192AC0
    "27BDFF80 3C030057 FFB70070 30C2FFFF FFB60060 0006763A FFB50050 0006683E"
    "FFB40040 0002603C 000C603F FFB30030 246366E8 FFB20020 0000502D FFB10010"
    "0000482D FFB00000 340BFFFF 000B5E38 3417FF00 0017BE38 2416FFFF 0016B63A"
    "2415FFFF 0015AA3C 0015AE3A 3414BD20 0014A638 3413BD80 00139E38 3412BD90"
)


# ---- Ghost Recon: a short tap fires (2026-10-04) ----------------------------------------------------
# Keeping the press was not enough there. GR's burst starts at now - one frame, so the first round
# comes one interval after the press (5 frames for an M16 at 60 fps), and on a full-auto gun
# StopUsingFirearm ends the burst on release (BurstOver) -- a tap shorter than that fires nothing,
# and a quick tap after a burst (which may not fire before the gun's last round + one interval) is
# dropped the same way. Semi-auto pulls already finish after release: NotUsingFirearm keeps calling
# ContinueUsingFirearm while +0x250 (firing) is set, and UpdateBurst ends a pull at its round count.
# For the players' soldiers (+0x138 == 0) only:
#   S  the burst starts one interval earlier, so its first round leaves on the press frame -- but
#      never before the gun's last round (+0x24C), so a burst never beats the rate;
#   P  a full-auto release before the first round leaves the burst running (+0x248 rounds = 0);
#   N  each frame R1 is up, after ContinueUsingFirearm: a running full-auto burst with a round out
#      ends (BurstOver) -- the tap fired its one round -- and one with none after 1 s ends too, so a
#      burst that cannot fire never holds the trigger (StartUsingFirearm drops presses while firing).
# Jungle Storm already fires a press's first round at once (its burst starts one interval back), so it
# gets P and N only: there the lost tap is the quick one after a burst, which the rate makes wait.
TAP = {
    "gr": dict(
        START_HOOK=0x003D248C, START_STOCK=0x0C0D6544,   # jal RSConstants::Get; slot stores the burst start
        STOP_HOOK=0x003D27B0, STOP_STOCK=0x0C0F4BCC,     # StopUsingFirearm, full auto: jal BurstOver
        NOTU_HOOK=0x003D27E4, NOTU_STOCK=0x0C0F4978,     # NotUsingFirearm: jal ContinueUsingFirearm
        CAVE2=0x00427A70, CAVE2_END=0x00427B60,          # more of _id2type (blood splatter: 0x4279F8-0x427A6C)
        CONT=0x003D25E0, OVER=0x003D2F30, INV=0x4F4, SELOPT=0x00220DE0, CLK=0x0035DB70, TOTAL=0x0035DB60,
    ),
    "js": dict(
        STOP_HOOK=0x003B1DE0, STOP_STOCK=0x0C0EC964,     # the same two calls in its twins
        NOTU_HOOK=0x003B1E14, NOTU_STOCK=0x0C0EC6F0,
        CAVE2=0x00192B38, CAVE2_END=0x00192C20,          # its _id2type twin, past blood splatter's words
        CONT=0x003B1BC0, OVER=0x003B2590, INV=0x514, SELOPT=0x002202E0, CLK=0x00124100, TOTAL=0x001574B0,
    ),
}
GR_TAP = TAP["gr"]

# S: entered from the hooked jal; s2 = the SimHuman, s1 = its selective option (u16 rpm at +0),
# f20 = now, f0 = the stock burst start (now - frame), already stored at +0x244. Ends in RSConstants::Get.
TAP_START_SRC = """
    lw    v1, 0x138(s2)              ; control type: 0 = a player
    bnez  v1, out
    lhu   v0, 0(s1)                  ; rounds per minute
    beqz  v0, out                    ; no rate: as shipped
    lui   at, 0x4270                 ; 60.0
    mtc1  at, f1
    mtc1  v0, f2
    cvt.s.w f2, f2
    div.s f1, f1, f2                 ; one interval
    lwc1  f2, 0x24c(s2)              ; the gun's last round
    c.lt.s f20, f2                   ; a last round in the future (an older clock)?
    sub.s f0, f0, f1                 ; start one interval earlier: the first round leaves now
    bc1t  out                        ; then keep the start as shipped
    c.lt.s f0, f2                    ; (slot) would it start before the last round?
    swc1  f0, 0x244(s2)
likely:
    bc1t  out                        ; made bc1tl below: if so, and only then, the slot runs --
    swc1  f2, 0x244(s2)              ; -- start at the last round: one interval after it
out:
    j     0x359510                   ; RSConstants::Get, the call this replaces
    nop
"""


def _start_words(base):
    """S assembled at `base`; the assembler has no branch-likely, so `likely:`'s bc1t gets its nd bit."""
    words, labels = assemble(TAP_START_SRC, base)
    i = (labels["likely"] - base) // 4
    assert words[i] >> 16 == 0x4501, "S: no bc1t at its likely: label"
    words[i] |= 0x00020000                       # bc1t -> bc1tl
    return words

# P: replaces StopUsingFirearm's `jal BurstOver` (full auto only); a0 = the SimHuman
TAP_STOP_SRC = """
    lw    v1, 0x138(a0)              ; control type: 0 = a player
    bnez  v1, over
    lhu   v0, 0x248(a0)              ; rounds out in this burst
    bnez  v0, over
    nop
    jr    ra                         ; a player's tap with no round out yet: let it fire
    nop
over:
    j     {OVER:#x}                  ; BurstOver, as shipped
    nop
"""

# N: replaces NotUsingFirearm's `jal ContinueUsingFirearm` (taken only while +0x250 is set); a0 = the SimHuman
TAP_NOTU_SRC = """
    addiu sp, sp, -0x20
    sd    ra, 0x10(sp)
    sq    s0, 0(sp)
    move  s0, a0
    jal   {CONT:#x}                  ; ContinueUsingFirearm, as shipped
    nop
    lbu   v1, 0x250(s0)              ; still firing?
    beqz  v1, done
    lw    v1, 0x138(s0)
    bnez  v1, done                   ; not a player: as shipped
    lw    t9, {INV:#x}(s0)            ; the current firearm
    lb    a1, 0x1e7(s0)
    lw    t9, 0x2c(t9)
    jalr  t9
    addiu a0, s0, {INV:#x}
    jal   {SELOPT:#x}                ; Firearm::GetCurrentSelectiveOption
    move  a0, v0
    lbu   v1, 4(v0)                  ; full auto?
    beqz  v1, done                   ; a semi / burst pull ends itself, as shipped
    lhu   v0, 0x248(s0)              ; rounds out
    bnez  v0, over                   ; the tap's round is out
    nop
    jal   {CLK:#x}                   ; RSClock::Get
    nop
    jal   {TOTAL:#x}                 ; TotalElapsedSeconds
    move  a0, v0
    lwc1  f1, 0x244(s0)              ; burst start
    lui   at, 0x3f80                 ; 1 s with nothing out: give up
    mtc1  at, f2
    sub.s f0, f0, f1
    c.lt.s f2, f0
    nop
    bc1f  done
    nop
over:
    jal   {OVER:#x}                  ; BurstOver
    move  a0, s0
done:
    ld    ra, 0x10(sp)
    lq    s0, 0(sp)
    jr    ra
    addiu sp, sp, 0x20
"""

_GR_CAVE2_STOCK_HEX = (   # _id2type, 0x00427A70..0x00427B60
    "DC680000 3402BD88 00021638 11020011 0048102B 14400007 00000000 1114000B"
    "00D03824 1113000B 00CB3824 1000000B 0000102D 11120008 00D93824 11110005"
    "00CB3824 10000005 0000102D 10000003 2402001F 00D93824 24020007 54E80019"
    "25290001 10000011 01C21024 3402E000 00021638 15020004 00000000 00D83824"
    "10000007 2402000F 150F0004 00C73824 00C23824 10000002 2402001F 0000102D"
    "54E80008 25290001 01A21024 AC890000 0002103C 0002103F 240A0001 ACA20000"
    "25290001 2D22000A 10400003 24630010 5140FFB9 DC670008 DFB70070 0140102D"
    "DFB60060 DFB50050 DFB40040 DFB30030"
)
#: its twin's first 58 words, 0x00192B38..0x00192C20 (read from SLUS_208.20: the same code)
_JS_CAVE2_STOCK_HEX = "".join(_GR_CAVE2_STOCK_HEX.split())[:58 * 8]


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


GR_STOCK = _stock_words(GAMES["gr"]["CAVE"], _GR_CAVE_STOCK_HEX)
JS_STOCK = _stock_words(GAMES["js"]["CAVE"], _JS_CAVE_STOCK_HEX)
GR_STOCK[GAMES["gr"]["HOOK"]] = GAMES["gr"]["HOOK_STOCK"]
GR_STOCK.update(_stock_words(TAP["gr"]["CAVE2"], _GR_CAVE2_STOCK_HEX))
JS_STOCK.update(_stock_words(TAP["js"]["CAVE2"], _JS_CAVE2_STOCK_HEX))
for _g, _st in (("gr", GR_STOCK), ("js", JS_STOCK)):
    for _k in ("START", "STOP", "NOTU"):
        if _k + "_HOOK" in TAP[_g]:
            _st[TAP[_g][_k + "_HOOK"]] = TAP[_g][_k + "_STOCK"]
for _k in ("HOOK", "SLOT", "START"):
    JS_STOCK[GAMES["js"][_k]] = GAMES["js"][_k + "_STOCK"]


def edits(game: str):
    """(va, value, stock, note)."""
    g = GAMES[game]
    st = GR_STOCK if game == "gr" else JS_STOCK
    kw, _ = assemble(KEEP_SRC.format(**g), g["CAVE"])
    words = list(kw)
    if game == "js":
        start = g["CAVE"] + 4 * len(words)
        sw, _ = assemble(START_SRC, start)
        words += sw
    if g["CAVE"] + 4 * len(words) > g["CAVE_END"]:
        raise ValueError("trigger routines outgrow their cave")
    out = [(g["CAVE"] + 4 * i, w, st[g["CAVE"] + 4 * i],
            "quick trigger: keep the press" if i < len(kw) else "quick trigger: burst from the last round")
           for i, w in enumerate(words)]
    out.append((g["HOOK"], assemble("j %#x" % g["CAVE"], g["HOOK"])[0][0], g["HOOK_STOCK"],
                "quick trigger: the cooldown test goes through the routine"))
    if game == "js":
        out.append((g["SLOT"], 0x00000000, g["SLOT_STOCK"], "quick trigger: (the jump's delay slot)"))
        out.append((g["START"], assemble("jal %#x" % start, g["START"])[0][0], g["START_STOCK"],
                    "quick trigger: burst start through the routine"))
    t = TAP[game]
    if game == "gr":
        start = g["CAVE"] + 4 * len(words)                    # S after the keep routine
        sw = _start_words(start)
        if start + 4 * len(sw) > g["CAVE_END"]:
            raise ValueError("trigger: the start routine outgrows its cave")
        out += [(start + 4 * i, w, st[start + 4 * i], "quick trigger: the first round leaves on the press")
                for i, w in enumerate(sw)]
        out.append((t["START_HOOK"], assemble("jal %#x" % start, t["START_HOOK"])[0][0], t["START_STOCK"],
                    "quick trigger: burst start through the routine"))
    stop = t["CAVE2"]                                         # P and N in the rest of _id2type
    pw, _ = assemble(TAP_STOP_SRC.format(**t), stop)
    notu = stop + 4 * len(pw)
    nw, _ = assemble(TAP_NOTU_SRC.format(**t), notu)
    if notu + 4 * len(nw) > t["CAVE2_END"]:
        raise ValueError("trigger: the tap routines outgrow their cave")
    out += [(stop + 4 * i, w, st[stop + 4 * i], "quick trigger: a released tap keeps its round")
            for i, w in enumerate(pw)]
    out += [(notu + 4 * i, w, st[notu + 4 * i], "quick trigger: a tap ends after its round")
            for i, w in enumerate(nw)]
    out += [(t["STOP_HOOK"], assemble("jal %#x" % stop, t["STOP_HOOK"])[0][0], t["STOP_STOCK"],
             "quick trigger: release through the routine"),
            (t["NOTU_HOOK"], assemble("jal %#x" % notu, t["NOTU_HOOK"])[0][0], t["NOTU_STOCK"],
             "quick trigger: trigger-up frames through the routine")]
    return out


def gr_edits(v: dict):
    return edits("gr") if v.get("gr_quick_trigger") else []


def js_edits(v: dict):
    return edits("js") if v.get("js_quick_trigger") else []


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
    return bad

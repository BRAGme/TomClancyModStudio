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
image and in Jungle Storm's online/offline overlays. Not yet played.
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


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


GR_STOCK = _stock_words(GAMES["gr"]["CAVE"], _GR_CAVE_STOCK_HEX)
JS_STOCK = _stock_words(GAMES["js"]["CAVE"], _JS_CAVE_STOCK_HEX)
GR_STOCK[GAMES["gr"]["HOOK"]] = GAMES["gr"]["HOOK_STOCK"]
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

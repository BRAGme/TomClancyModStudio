"""The zoom holds while you turn and move: Ghost Recon (SLUS-20613) and Jungle Storm (SLUS-20820).

WHAT THE PLAYER SEES
--------------------

Zoom in (R3 clicks with Jungle Storm's controls, R2 / L2 with Ghost Recon's)
and the zoom stays where you put it while you turn and while you walk or run,
as on the Xbox. Before, Ghost Recon dropped you back to 1x the moment you
turned quickly or ran, and Jungle Storm dropped you back the moment you ran.
The zoom still drops back where it did for any other reason: reloading
(Ghost Recon), switching weapon, switching soldier, dying -- and, in Ghost
Recon, a long full-auto burst from a heavy gun while standing (below).

Moving and turning still cost accuracy exactly as before. The spread a shot
can take is the reticle's own inaccuracy, which the zoom does not change
(Reticule::GetShotDirection reads only the reticle): standing still it is 15
on a scale whose top is 1500, walking upright 60, running upright 600 (800
crouched), and turning multiplies it by 10 / 20 / 50 / 100 above 0.5 / 1.5 /
3 / 8 rad/s (the turn bands every weapon in the savestates carries; Jungle
Storm's are the same). The bloom tops out at 1500. Zoomed in, that spread is
simply easier to see.

HOW EACH GAME DROPPED THE ZOOM
------------------------------

Both games keep the zoom as a target field of view (SimHuman +0x1F4) and
SimHuman::Update puts it back to 1x (ZoomToFOV(1.0)), hides the zoom panel and
removes the zoom blur on any frame its reticle says "cannot zoom"
(Reticule::CannotZoom, ReticulePriv byte +0x90) -- for the players' own
soldiers only (the check sits behind IsAvatar). The two games set that byte
differently, in Reticule::GetCurrentNormalizedAccuracy:

  * Ghost Recon (0x003A45F0): "cannot zoom" when the reticle's current
    inaccuracy (+0x08) is over a limit for the stance -- 500 upright, 600
    crouched, 700 prone, 480 wounded (+0x8C, from UpdateBaseAccuracy) -- or
    when a wounded soldier moves at all. The inaccuracy is the reticle bloom,
    and three things raise it: the stance / movement table (UpdateBaseAccuracy:
    the current spread never sits below table[movement][stance] times the
    turning band), turning (that band, from the average turn rate of the last
    five frames), and each round fired (AddImpulse, GunFile recoil +0x98).
    Running upright (600) or crouched (800), or turning faster than about
    3 rad/s standing still (15 x 50), is over the limit at once, and walking
    while turning even slowly is (60 x 10).
  * Jungle Storm (0x00384270): "cannot zoom" when a latch at SimHuman +0x45C
    was set since the last look (the vtable +0x138 test-and-clear, 0x003C0320).
    Its only setter in the game is SimHuman::CalculateCurrentVelocity
    (0x003AC6A4): a full push of the movement stick (93 or more), the run.
    grsprintspeed's L3 sprint sets the same latch. Turning never set it:
    Jungle Storm had already dropped the bloom rule.

WHAT THIS CHANGES
-----------------

Jungle Storm: four words. The "cannot zoom" byte is read by exactly five
calls to Reticule::CannotZoom (0x00384200). Four of them act on the zoom and
now get "no" (`jal CannotZoom` -> `move v0, zero`; the delay slot that loads
a0 is harmless):

  * SimHuman::Update (0x003A9710): the drop to 1x;
  * the click-zoom handler's three steps (0x003B75B8 1x -> 4x, 0x003B776C
    4x -> the most, 0x003B76A8 the most -> 1x), which skipped their zoom
    click sound (C_Zoom_In.wav / C_Zoom_Out.wav) while running -- the zoom it
    set was about to be dropped. Now the zoom stays, so the click plays.

The fifth, DrawCamera (0x00238AFC), keeps the stock answer: it gates the
reticle "hooking" (zoomed in past 1.01x, turn / look / strafe axes near
centre: ReticuleDisplay::SetHookEnemy locks the reticle onto an enemy under
it). The forward axis is not among the axes it checks, so with a held zoom a
straight run would otherwise have hooked -- something the shipped game never
did. The latch, the run flag and everything else are as shipped.

Ghost Recon: the drop to 1x asks a different question. The reticle keeps a
second, shadow bloom per soldier -- the bloom the soldier would have had if he
had stood still and not turned -- and SimHuman::Update's drop looks at that
instead of the real one. The shadow:

  * decays as the reticle does (UpdateCurAccuracy: by inaccuracy x recovery
    rate +0x94 x frame time / 1500 each frame);
  * never sits below the standing-still row of the movement table for the
    soldier's stance (table row 3: 15 / 10 / 7) and never above the reticle's
    real bloom;
  * takes every round's recoil, as the real one does (AddImpulse, clamped to
    the most bloom).

So the drop still comes from recoil -- the stock rule drops the zoom during a
long full-auto burst from a heavy gun (recoil about 100-120 a round) once the
bloom passes the stance's limit, which standing takes about half a second at
900 rounds a minute (whether 600 a minute gets there depends on the soldier's
recovery rate), and it still does on the same frame -- and no longer from
turning, walking, running or moving while wounded. The real
bloom, the limits, the shots' spread and the "cannot zoom" byte itself (which
DrawCamera's reticle hooking still reads, as in Jungle Storm above) are all as
shipped.

The shadow lives in two bytes of ReticulePriv padding (+0x92, u16, in 1/32
units: +0x90 is the "cannot zoom" byte, +0x94 the next float; no code reads
or writes +0x91..+0x93). ReticulePriv is allocated without zeroing; the
"no higher than the real bloom" rule cleans whatever was there on the first
frame.

  * hook 1, ReticulePriv::UpdateBaseAccuracy (0x003A389C): its `jal
    GetTurnVelocity` goes to `frame`, which updates the shadow (s1 = the
    reticle, s0 = the stance) and does the getter's job (f0 = SimHuman
    +0x470) on its way out. Every soldier, every frame.
  * hook 2, Reticule::AddImpulse (0x003A45E0): its `j ReticulePriv::AddImpulse`
    goes to `impulse`, which adds the round's recoil to the shadow and jumps on
    to the stock code with a0 / f12 untouched. Its only caller is
    SimHuman::FiredWeapon.
  * hook 3, SimHuman::Update (0x003CA070): its `jal Reticule::CannotZoom` goes
    to `decide`: v0 = shadow > the stance's limit. Only the players' own
    soldiers reach that call (IsAvatar), so the AI is unchanged: its bloom, its
    "cannot zoom" byte and its accuracy are as shipped (it only gets the
    shadow bytes written, which nothing of its own reads).

Split screen: everything is per soldier (each soldier's own reticle and
SimHuman::Update), so both players get it.

Caves (Ghost Recon): sceScfGetLanguage .. sceScfGetSpdif (0x0054FA08 ..
0x0054FB07: GetLanguage, SetT10kConfig, GetAspect, GetSpdif and their padding)
for `frame` and `decide`, and sceScfGetDateNotation (0x0054FB58 .. 0x0054FBBB)
for `impulse` (42 + 24 words; 0x0054FAB0 .. 0x0054FB07 and 0x0054FBB8 stay
free). None is called, jumped or branched to, pointed at or built with
lui/addiu from anywhere in the loaded image (0x00100000 .. 0x005DED00); the
only calls they make are to IsT10K and GetOsdConfigParam. Jungle Storm needs no
cave.

Every stock word is checked against the retail executables (`selftest`). Run
in an interpreter on the user's savestate RAM; not yet played.
"""

from __future__ import annotations

from .grasm import assemble

# ---------------------------------------------------------------- Ghost Recon
GR_CAVE_A = 0x0054FA08          # frame + decide
GR_CAVE_A_END = 0x0054FB08
GR_CAVE_B = 0x0054FB58          # impulse
GR_CAVE_B_END = 0x0054FBBC

#: (va, stock word, what it was)
GR_HOOKS = {
    "frame": (0x003A389C, 0x0C0E8EA0, "UpdateBaseAccuracy: jal SimHuman::GetTurnVelocity"),
    "impulse": (0x003A45E0, 0x080E8EB8, "Reticule::AddImpulse: j ReticulePriv::AddImpulse"),
    "decide": (0x003CA070, 0x0C0E9160, "SimHuman::Update: jal Reticule::CannotZoom"),
}
GR_ADDIMPULSE = 0x003A3AE0      # ReticulePriv::AddImpulse

# Engine values the routines read (Ghost Recon):
#   *0x005DFC20 = RSClock, +0xD0 frame time (RSClock::Get / FrameElapsedSeconds)
#   *0x005E4D18 = IkeConstants, +0x158 the most bloom (GetMaxInaccuracy, 1500)
#   ReticulePriv: +0x08 bloom, +0x34 + 4 x stance the standing-still row,
#   +0x8C the stance's limit (int), +0x92 the shadow (ours), +0x94 recovery rate
_CVT_W_S_F3 = 0x460018E4        # cvt.w.s f3, f3 (grasm has no cvt.w.s)
_CVT_W_S_F1 = 0x46000864        # cvt.w.s f1, f1

FRAME_SRC = """
frame:                              ; a0 = SimHuman, s1 = ReticulePriv, s0 = stance (0 up, 1 crouched, 2 prone)
    lui     v1, 0x005e
    lw      v1, 0x4d18(v1)          ; IkeConstants
    lui     at, 0x005e
    lw      at, -0x3e0(at)          ; RSClock
    lwc1    f3, 0x158(v1)           ; the most bloom (1500)
    lwc1    f2, 0x94(s1)            ; recovery rate
    lwc1    f1, 0xd0(at)            ; this frame's time
    lhu     v0, 0x92(s1)            ; shadow bloom x 32
    div.s   f2, f2, f3              ; rate / most
    lui     at, 0x3d00              ; 1/32
    mtc1    v0, f3
    mtc1    at, f4
    cvt.s.w f3, f3
    mul.s   f2, f2, f1              ; rate x time / most
    mul.s   f3, f3, f4              ; shadow
    sll     v0, s0, 2
    mul.s   f2, f3, f2
    addu    v0, v0, s1
    lwc1    f4, 0x34(v0)            ; standing still, this stance (table row 3)
    sub.s   f3, f3, f2              ; decays as UpdateCurAccuracy decays the bloom
    lwc1    f5, 8(s1)               ; the real bloom
    c.lt.s  f3, f4
    lui     at, 0x4200              ; 32.0
    bc1f    above
    mtc1    at, f2
    mov.s   f3, f4                  ; no lower than standing still
above:
    c.lt.s  f5, f3
    lwc1    f0, 0x470(a0)           ; the call's own job: SimHuman::GetTurnVelocity
    bc1f    store
    nop
    mov.s   f3, f5                  ; no higher than the real bloom
store:
    mul.s   f3, f3, f2
    .word   {CVT3:#x}                ; cvt.w.s f3, f3
    mfc1    v0, f3
    jr      ra
    sh      v0, 0x92(s1)

decide:                             ; a0 = Reticule -> v0 = 1: back to 1x
    lw      v1, 0(a0)               ; ReticulePriv
    lhu     v0, 0x92(v1)            ; shadow bloom x 32
    lw      v1, 0x8c(v1)            ; the stance's limit
    sll     v1, v1, 5
    jr      ra
    slt     v0, v1, v0              ; over the limit (stock: !(bloom <= limit))
"""

IMPULSE_SRC = """
impulse:                            ; a0 = ReticulePriv, f12 = this round's recoil
    mtc1    zero, f0
    lhu     v0, 0x92(a0)            ; shadow bloom x 32
    lui     at, 0x3d00              ; 1/32
    c.lt.s  f12, f0                 ; a negative push is ignored, as AddImpulse does
    lui     v1, 0x005e
    bc1t    done                    ; (v0 still holds the shadow: stored back unchanged)
    mtc1    v0, f1
    mtc1    at, f2
    lw      v1, 0x4d18(v1)          ; IkeConstants
    cvt.s.w f1, f1
    lui     at, 0x4200              ; 32.0
    mul.s   f1, f1, f2              ; shadow
    lwc1    f2, 0x158(v1)           ; the most bloom
    add.s   f1, f1, f12             ; + the recoil, as the real bloom
    c.lt.s  f2, f1
    mtc1    at, f3
    bc1f    scale
    nop
    mov.s   f1, f2                  ; no more than the most, as the real bloom
scale:
    mul.s   f1, f1, f3
    .word   {CVT1:#x}                ; cvt.w.s f1, f1
    mfc1    v0, f1
done:
    j       {ADD:#x}                 ; ReticulePriv::AddImpulse, as the call did
    sh      v0, 0x92(a0)
"""

_GR_CAVE_A_STOCK_HEX = (   # sceScfGetLanguage .. sceScfGetSpdif, 0x0054FA08..0x0054FB08
    "27BDFFE0 FFBF0010 0C1046E4 03A0202D 0C153E72 00000000 10400003 3C020057 "
    "1000000C 90420B7C 0C1046E4 03A0202D 8FA30000 00031342 30420007 54400004 "
    "00031402 00031102 10000002 30420001 3042001F DFBF0010 03E00008 27BD0020 "
    "3C020057 24470B78 68830007 6C830000 B0E30007 03E00008 B4E30000 00000000 "
    "27BDFFE0 FFBF0010 0C153E72 00000000 10400003 3C030057 10000006 90620B7A "
    "0C1046E4 03A0202D 8FA20000 00021042 30420003 DFBF0010 03E00008 27BD0020 "
    "27BDFFE0 FFBF0010 0C153E72 00000000 10400003 3C030057 10000005 90620B7D "
    "0C1046E4 03A0202D 8FA20000 30420001 DFBF0010 03E00008 27BD0020 00000000 "
)
_GR_CAVE_B_STOCK_HEX = (   # sceScfGetDateNotation, 0x0054FB58..0x0054FBBC
    "27BDFFE0 FFBF0010 0C153E72 00000000 10400003 3C020057 1000000F 90420B7B "
    "0C1046E4 03A0202D 8FA20000 00021342 30420007 14400003 37A40004 10000006 "
    "0000102D 24050001 0C10477C 24060001 93A30004 00031182 DFBF0010 03E00008 "
    "27BD0020 "
)

# ---------------------------------------------------------------- Jungle Storm
_JAL_CANNOTZOOM = 0x0C0E1080    # jal 0x00384200 (Reticule::CannotZoom)
_MOVE_V0_ZERO = 0x0000102D      # move v0, zero
#: (va, stock, new, note): the four Reticule::CannotZoom calls that act on the zoom answer "no"
JS_HOOKS = (
    (0x003A9710, _JAL_CANNOTZOOM, _MOVE_V0_ZERO, "SimHuman::Update: running no longer drops the zoom to 1x"),
    (0x003B75B8, _JAL_CANNOTZOOM, _MOVE_V0_ZERO, "click zoom 1x -> 4x: C_Zoom_In.wav plays while running too"),
    (0x003B76A8, _JAL_CANNOTZOOM, _MOVE_V0_ZERO, "click zoom most -> 1x: C_Zoom_Out.wav plays while running too"),
    (0x003B776C, _JAL_CANNOTZOOM, _MOVE_V0_ZERO, "click zoom 4x -> most: C_Zoom_In.wav plays while running too"),
)


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


_GR_CAVE_STOCK = _stock_words(GR_CAVE_A, _GR_CAVE_A_STOCK_HEX)
_GR_CAVE_STOCK.update(_stock_words(GR_CAVE_B, _GR_CAVE_B_STOCK_HEX))


def _gr_routines():
    """(cave A words, cave B words, labels)."""
    a, la = assemble(FRAME_SRC.format(CVT3=_CVT_W_S_F3), GR_CAVE_A)
    b, lb = assemble(IMPULSE_SRC.format(CVT1=_CVT_W_S_F1, ADD=GR_ADDIMPULSE), GR_CAVE_B)
    if GR_CAVE_A + 4 * len(a) > GR_CAVE_A_END or GR_CAVE_B + 4 * len(b) > GR_CAVE_B_END:
        raise ValueError("zoom-hold routines outgrow their caves")
    la.update(lb)
    return a, b, la


def _gr_stock():
    a, b, _ = _gr_routines()
    st = {GR_CAVE_A + 4 * i: _GR_CAVE_STOCK[GR_CAVE_A + 4 * i] for i in range(len(a))}
    st.update({GR_CAVE_B + 4 * i: _GR_CAVE_STOCK[GR_CAVE_B + 4 * i] for i in range(len(b))})
    for va, stock, _what in GR_HOOKS.values():
        st[va] = stock
    return st


#: every word the module may write, with its retail value
GR_STOCK = _gr_stock()
JS_STOCK = {va: stock for va, stock, _n, _t in JS_HOOKS}


def edits(game: str):
    """(va, value, stock, note)."""
    if game == "js":
        return [(va, new, stock, "zoom holds: " + what) for va, stock, new, what in JS_HOOKS]
    a, b, lab = _gr_routines()
    out = [(GR_CAVE_A + 4 * i, w, GR_STOCK[GR_CAVE_A + 4 * i],
            "zoom holds: shadow bloom per frame" if GR_CAVE_A + 4 * i < lab["decide"]
            else "zoom holds: the drop to 1x asks the shadow bloom")
           for i, w in enumerate(a)]
    out += [(GR_CAVE_B + 4 * i, w, GR_STOCK[GR_CAVE_B + 4 * i], "zoom holds: recoil into the shadow bloom")
            for i, w in enumerate(b)]
    for name, (va, stock, what) in GR_HOOKS.items():
        op = "j" if name == "impulse" else "jal"
        out.append((va, assemble("%s %#x" % (op, lab[name]), va)[0][0], stock,
                    "zoom holds: %s -> %s" % (what, name)))
    return out


def gr_edits(v: dict):
    return edits("gr") if v.get("gr_zoom_hold") else []


def js_edits(v: dict):
    return edits("js") if v.get("js_zoom_hold") else []


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
        if any(va not in st or st[va] != s for va, _w, s, _n in e):
            bad.append("%s VA without its stock word" % game)
    new = {va: w for va, w, *_ in edits("gr")}
    _a, _b, labels = _gr_routines()
    for name, (va, _s, _w) in GR_HOOKS.items():
        if (new[va] & 0x03FFFFFF) << 2 != labels[name]:
            bad.append("gr hook %s does not reach its routine" % name)
    return bad

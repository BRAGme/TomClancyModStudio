"""Sprint on L3: one free button, one dead call, and a threshold that moves.

WHAT JUNGLE STORM ACTUALLY HAS
------------------------------

There is no sprint in this engine and there is no speed number to raise.

`IkeUIMgr::GetMovementSpeedFromInput` (JS **0x0025D080**, 82 words) takes the
left stick's deflection, takes its absolute value through the helper at
0x0019B010, and sorts it into four bands against three hard-coded floats:

    |stick| >  93.0   ->  RUN        returns 2
    |stick| >  60.0   ->  WALK       returns 1
    |stick| >  25.0   ->  SHUFFLE    returns 3
    otherwise         ->  STATIONARY returns 0

That return value is the whole of the player's speed. It picks a motion set --
`HumanMotion` stores it as an enum at +0x3C, 1 walk / 2 run / 3 shuffle -- and
the body's velocity is whatever that animation's root motion carries
(`HumanMotion::GetMotionVelocity` hands back a cached vector at +0x0C). There
is no multiplier downstream of it.

THE SCALAR GHOST RECON HAD IS DEAD HERE, AND THAT IS MEASURED
-------------------------------------------------------------

Ghost Recon PS2 had one. `SimHuman::CalculateCurrentVelocity` (GR 0x003CCA80)
scales the animation's velocity by `IkeSimulationMgr::GetPlayerRunFactor()`
at GR 0x003CCBAC, and both `Get*SpeedFromInput` recompute that factor every
frame as `0.88 * (|stick| / the band's own threshold)` -- the analog fine
control inside a band.

Jungle Storm still **writes** it. `IkeSimulationMgr::SetPlayerRunFactor`
survives at 0x0025D1D0, still multiplies by the same 0.88 (the double at
0x0058AAA0), still stores to the same field, `IkeSimulationMgr + 0x9F8`. It is
called from eight sites across the two speed functions, plus the constructor.

Nothing reads it. Displacement 0x9F8 appears in exactly four instructions in
the whole 5.3 MB image -- `swc1` at 0x0025D204, `sw` at 0x00362B38 (the
constructor's 1.0f), `swc1` at 0x00364C5C and 0x00364CFC -- and every one of
them is a store. There is no `lw`, `lwc1`, `ld` or `lq` at 0x9F8, and no
`addiu rX, rY, 0x9F8` that would let the field be reached through a shifted
base. The consumer was removed and the producer was left behind.

So a *faster than running* sprint is not a number that can be changed. It
would need new arithmetic in the velocity path, or the run animation re-timed
through `MotionManager::SetFrameSpeed` -- which also moves footfall timing and
the noise the awareness system reads off it. This module does neither, and
does not pretend the option exists.

WHAT IT DOES INSTEAD, WHICH IS THE THING THAT WAS ASKED FOR
-----------------------------------------------------------

Ghost Recon on PC has no analog stick. Shift is not a fourth speed there; it
is the switch between walking and running. That is exactly what is reachable
here: **sprint moves the RUN band's threshold down**, so any deflection past
the dead zone gives the run tier instead of needing 93 out of 128.

    sprint off   |stick| > 93  runs        (stock)
    sprint on    |stick| > 25  runs        -- i.e. any real stick movement

The walk and shuffle bands become unreachable while it is on, which is the
point: you are either stopped or running.

The latch clears itself the moment he stops, because "stopped" is a branch
this function already has. The stationary case at 0x0025D198 does nothing but
call the dead `SetPlayerRunFactor(1.0)` -- seven words that write a field
nobody reads. Three of them become the reset.

L3 IS FREE, AND THAT IS MEASURED TOO
------------------------------------

`RSInputImpl::MapForAction` (JS 0x0019B280) fills a 16-entry keycode table per
pad at `this + pad*0x20 + 0x18`, indexed by the bit position of the button in
the buttons word. The index order is the standard PS2 pad word read as
`~((byte2 << 8) | byte3)`: bit 0 L2, 1 R2, 2 L1, 3 R1, 4 triangle, 5 circle,
6 cross, 7 square, 8 SELECT, 9 **L3**, 10 R3, 11 START, 12..15 the d-pad.

Four independent checks agree on that ordering, all against the retail image:

  * index 1 holds 0x81 and index 10 holds 0x59 in configurations 1 and 2, and
    configuration 3 swaps exactly those two -- and configuration 3 is the one
    the Options screen labels as swapping R2 and R3;
  * index 8 holds 0x70, and `grsquad` binds 0x70 as Jungle Storm's SELECT;
  * index 13 holds 0x58 and index 15 holds 0x56, which `grcontrols` names as
    Jungle Storm's peek-right and peek-left on the d-pad;
  * index 12/14 hold 0x74/0x73 and index 4/6 hold 0x75/0x6F in configuration
    2, matching all four of `grcontrols`' configuration-2 captions.

Index 9 -- L3 -- is `addiu t0, zero, -1` at **0x0019B38C**, stored to +0x2A at
0x0019B3D0 for all three configurations, and the scan loop skips any key <= 0
(`blez v1, ...` at 0x0019A4F0). **L3 does nothing in Jungle Storm.** Nothing
is being taken away.

Pad 2's table is pad 1's keycodes plus 0xC5 (the fix-up loop at
0x0019B460..0x0019B47C inside `MapForAction`), so pad 2's L3 carries 0xC4
rather than a skipped value -- a stock quirk, not one this module introduces,
and 0xC4 is bound to no message.

WHY THE HOOK IS ONE WORD
------------------------

`RSInputImpl::Update` calls the "current buttons" accessor at 0x0019A4C0 and
throws the answer away: v0 is not read again before it is redefined at
0x0019A4FC. The call is dead, it runs once per pad per frame, and its delay
slot at 0x0019A4C4 has already loaded the ControllerInfo pointer into a0 --
which is everything the latch needs.

So the hook is `jal 0x19b090` -> `jal CAVE`, one word, with no displaced
instruction to carry. In the cave, a0 is the ControllerInfo, s4 is the pad
index, and the two words the scan loop itself uses are at +0x54 (held this
frame) and +0x58 (held last frame) -- read by the accessors at 0x0019B090 and
0x0019B080 respectively. The press edge is `cur & ~prev & (1 << 9)`.

Every register the cave touches (at, v0, t0, t1) was already clobbered by the
`jal` that used to sit there, and ra is likewise already being written by it.

NOT ESTABLISHED
---------------

* **Never played.** Nothing here has been run.
* Whether `kMsgID_AvatarMove` is delivered on every frame or only when the
  stick value changes. It does not change the outcome -- releasing the stick
  produces a message with |stick| <= 25 either way, which is the frame the
  latch has to clear on -- but if the message stops entirely at rest, the
  latch would clear one frame later than described.
* The predicate at 0x0019A4B8 that can skip the whole button scan was not
  traced. While it is false, L3 is not sampled; so is every other button.
* Split screen shares one latch. The cave only reads pad 1's L3 (`bnez s4`),
  but the threshold word is global, so player 2 runs on player 1's toggle and
  cannot turn it off. Making it per-pad needs a second word and a second hook
  and was not done.
* Online, this is a client-side advantage: the run state replicates normally
  as a legitimate `SimHumanState` run, but the holder reaches it from a light
  stick push while everyone else must push to 93.
"""

from __future__ import annotations

from .grasm import assemble


class SprintError(Exception):
    pass


#: The 520-byte hole inside `lzo1x_decompress_safe`, between grsquad's roster
#: cave (ends 0x00199900) and its handoff cave (starts 0x00199B08). Verified
#: unreferenced: no `j`/`jal` in the boot image or in either overlay targets
#: anywhere in 0x001996A0..0x00199BF4, and no data word points into it.
CAVE = 0x00199900
CAVE_END = 0x00199B08

#: `jal 0x19b090` in RSInputImpl::Update whose result is never read -- v0 is
#: redefined at 0x0019A4FC without an intervening use. Runs once per pad per
#: frame; its delay slot at 0x0019A4C4 leaves the ControllerInfo in a0.
HOOK_AT = 0x0019A4C0
HOOK_STOCK = 0x0C066C24

#: `lui v0, 0x42ba` / `mtc1 v0, f0` -- the 93.0f RUN threshold, the only one
#: the band test reads. The second copy at 0x0025D0DC feeds the dead run
#: factor and is deliberately left alone.
THRESH_AT = 0x0025D0B8
THRESH_STOCK = (0x3C0242BA, 0x44820000)

#: The stationary branch: `SetPlayerRunFactor(1.0)` and nothing else. Seven
#: words, all dead -- the field it writes is never read anywhere in the image.
CLEAR_AT = 0x0025D198
CLEAR_STOCK = (0x0C0489CC, 0x00000000, 0x0040202D, 0x3C023F80,
               0x44826000, 0x0C097474, 0x00000000)

#: The engine's own band thresholds, as float bit patterns.
RUN_STOCK = 0x42BA0000        # 93.0f
BANDS = {"walk": 0x42700000,  # 60.0f -- a half push runs
         "any": 0x41C80000}   # 25.0f -- anything past the dead zone runs
PRESETS = ("off",) + tuple(BANDS)
PRESET_DEFAULT = "off"

_SRC = """
        bnez  s4, out              ; pad 1 only
        nop
        lw    t0, 0x54(a0)         ; buttons held this frame
        lw    t1, 0x58(a0)         ; buttons held last frame
        nor   t1, t1, zero
        and   t0, t0, t1           ; newly pressed this frame
        andi  t0, t0, 0x200        ; bit 9 = L3
        beqz  t0, out
        lui   at, %hi(VAR)
        lw    v0, %lo(VAR)(at)
        lui   t1, {on:#x}          ; sprinting
        lui   t0, {off:#x}         ; stock
        bne   v0, t1, turn_on
        nop
        sw    t0, %lo(VAR)(at)     ; was on  -> off
        jr    ra
        nop
turn_on:
        sw    t1, %lo(VAR)(at)     ; was off -> on
out:
        jr    ra
        nop
VAR:
        .word {stock:#x}
"""


def _cave(preset):
    src = _SRC.format(on=BANDS[preset] >> 16, off=RUN_STOCK >> 16, stock=RUN_STOCK)
    words, labels = assemble(src, CAVE)
    if CAVE + 4 * len(words) > CAVE_END:
        raise SprintError("sprint cave outgrows its hole")
    return words, labels["VAR"]


def edits(preset: str = PRESET_DEFAULT):
    """[(va, value, stock, note)]. "off" emits nothing at all."""
    if preset not in PRESETS:
        raise SprintError("no such sprint preset: %r" % (preset,))
    if preset == "off":
        return []
    words, var = _cave(preset)
    out = [(CAVE + 4 * i, w, None, "sprint on L3: latch")
           for i, w in enumerate(words)]
    thresh, _ = assemble(
        "lui at, %%hi(%#x)\nlwc1 f0, %%lo(%#x)(at)" % (var, var), THRESH_AT)
    for i, w in enumerate(thresh):
        out.append((THRESH_AT + 4 * i, w, THRESH_STOCK[i],
                    "sprint on L3: the run threshold becomes a variable"))
    clear, _ = assemble(
        "lui at, %%hi(%#x)\nlui v0, %#x\nsw v0, %%lo(%#x)(at)\nnop\nnop\nnop\nnop"
        % (var, RUN_STOCK >> 16, var), CLEAR_AT)
    for i, w in enumerate(clear):
        if w == CLEAR_STOCK[i]:
            continue
        out.append((CLEAR_AT + 4 * i, w, CLEAR_STOCK[i],
                    "sprint on L3: stopping clears the latch"))
    out.append((HOOK_AT, assemble("jal %#x" % CAVE, HOOK_AT)[0][0], HOOK_STOCK,
                "sprint on L3: read L3 once per pad per frame"))
    return out


def js_edits(v: dict):
    return edits(v.get("js_sprint_l3", PRESET_DEFAULT))


#: The cave's stock words already live in grsquad's JS_STOCK, which records
#: the whole lzo block. Only the four in-place sites are new.
JS_STOCK = {HOOK_AT: HOOK_STOCK}
JS_STOCK.update({THRESH_AT + 4 * i: w for i, w in enumerate(THRESH_STOCK)})
JS_STOCK.update({CLEAR_AT + 4 * i: w for i, w in enumerate(CLEAR_STOCK)})


def selftest(js_elf: bytes):
    """Every recorded stock word against the retail image. [] = pass."""
    bad = []
    for va, w in JS_STOCK.items():
        o = va - 0x00100000 + 0x100
        got = int.from_bytes(js_elf[o:o + 4], "little")
        if got != w:
            bad.append("%08X: stock %08X, image %08X" % (va, w, got))
    for preset in PRESETS:
        e = edits(preset)
        if len({va for va, *_ in e}) != len(e):
            bad.append("%s: an address is written twice" % preset)
        for va, _w, stock, _t in e:
            if stock is not None and JS_STOCK.get(va) != stock:
                bad.append("%s: %08X stock not registered" % (preset, va))
        for va, _w, stock, _t in e:
            if stock is None and not (CAVE <= va < CAVE_END):
                bad.append("%s: cave word %08X out of bounds" % (preset, va))
    return bad


def card(prefix, group):
    from .model import CHOICE, Choice, Setting

    return Setting(
        prefix + "sprint_l3", "Sprint on L3", CHOICE, PRESET_DEFAULT, group,
        choices=[
            Choice("off", "Off", "As shipped. L3 does nothing."),
            Choice("walk", "Half a push runs",
                   "While sprint is on, pushing the stick about half way "
                   "already gives the running animation."),
            Choice("any", "Any movement runs",
                   "While sprint is on, any push past the dead zone runs. "
                   "This is the closest to holding Shift on the PC game."),
        ],
        help="L3 is unbound in Jungle Storm, so this costs you nothing.\n\n"
             "Click it once and the left stick runs him instead of walking "
             "him. Stop moving and it switches itself off again -- the next "
             "time you push the stick he walks, until you click L3 again.\n\n"
             "This is not a fourth speed. Jungle Storm has four movement "
             "states -- stopped, shuffling, walking, running -- and running "
             "is already the fastest one; the stick reaches it only when you "
             "push it almost all the way. What this does is move that point "
             "down, which is what holding Shift does on the PC game: it is "
             "the switch between walking and running, not a boost past it.\n\n"
             "The game has no number for a speed above running. The one the "
             "PC-derived code used to carry is still written every frame but "
             "nothing reads it any more, so there is nothing to turn up.",
        caution="Never played.\n\n"
                "Running is loud and visible. The awareness system scores a "
                "running soldier far higher than a walking one for both sight "
                "and sound, so a sprint you forget to switch off will get you "
                "noticed. It clears itself whenever you stop, which is most "
                "of the protection you get.\n\n"
                "In split screen both players share one latch. Player 1's L3 "
                "switches it on for both of them and player 2 cannot turn it "
                "off.\n\n"
                "Online this is an advantage over players who have not got "
                "it. The run state itself replicates normally -- it is the "
                "same state the stick produces at full deflection -- so it "
                "will not desynchronise anything.\n\n"
                "Nothing here touches AI teammates or enemies. They choose "
                "their pace through HumanAI, which never goes near this "
                "function.",
        confidence="experimental")

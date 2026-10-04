"""Sprint that is faster than running. Jungle Storm: on top of grsprint's L3
(`js_edits`, `card`). Ghost Recon: the whole L3 sprint (`gr_edits`, `gr_cards`),
described in the Ghost Recon section below the Jungle Storm code.

WHY L3 SPRINT ALONE WAS NOT FASTER
----------------------------------

`grsprint` moves the RUN band of `IkeUIMgr::GetMovementSpeedFromInput` (the 93.0
at 0x0025D0B8) down to 25 or 60 while its L3 latch is on. That picks the run
*animation*. It does not pick the speed, because the player's speed is not the
animation's root motion.

`SimHuman::CalculateCurrentVelocity` is JS **0x003AC4B0** (Ghost Recon's
0x003CCA80, same shape). For a soldier whose control type is 0 -- a person's
soldier, `IsAvatar` is `+0x138 == 0` -- the root-motion velocity
(`HumanMotion + 0x0C`) is only a stop gate: when both of its ground components
are within 0.1 he stands. Otherwise the velocity is built from the stick values
that the MoveForward / MoveRight messages (ids 9 / 0x0A) leave at
`SimHuman + 0x658` / `+0x65C`:

    m     = sqrt(fwd^2 + strafe^2),  direction = stick / m
    speed = 93.0          if m >= 93 (also sets the running flags +0x47C/+0x45C)
          = 0.5 * m       otherwise
    speed *= 0.32         if a leg is wounded (vtable +0x538)
    velocity = direction * speed * the stance's axis constants
               (upright 0.058 forward / 0.022 back / 0.034 sideways,
                crouched 0.038 / 0.016 / 0.020, prone 0.015 / 0.006 / 0.008)

so a full forward push upright is 93 x 0.058 = 5.39 m/s. The velocity code has
its own 93 (0x003AC638), which grsprint does not touch: with sprint on, a light
push gives the run animation at *walking* pace or less, and a full push is the
stock run. That is the "I'm not moving faster" the user saw. Checked on his
savestate (E189327D): his soldier, stick forward -103 / strafe 35, has
|velocity| 5.207 m/s, and the formula gives 5.206.

(Ghost Recon's `GetPlayerRunFactor` multiply, which grsprint notes is dead in
Jungle Storm, scales the root-motion vector; the avatar branch then replaces
that vector with the stick-built one, so it was not the player's speed in
Ghost Recon either.)

WHAT THIS DOES
--------------

Each player has his own sprint switch, and nothing else can turn it off.

Switch. `RSInputImpl::Update` walks the pads once per frame; right after
grsprint's L3 hook it recomputes `sll v1, s4, 5` at **0x0019A4C8**, a value its
delay slot at 0x0019A4BC already holds. That word becomes `jal pad`: for pads 0
and 1, an L3 press edge (`held & ~held_last & 0x200`, the ControllerInfo words
+0x54 / +0x58) flips that pad's switch `LAT[pad]`, and the cave ends with the
`sll` it replaced. Pad index = player index: the input layer attaches avatar
2's id to pad index 1 only (grsquad's finding).

Stopping. The forward-axis handler of `IkeUIMgr` (key 0x13D) calls
`GetMovementSpeedFromInput` at **0x0025C108**, the function's only caller; that
`jal` becomes `jal band`. The handler has player 1's avatar id in `s0` and the
message's own avatar id at `0x58(sp)`, which is how it tells the two players
apart itself (0x0025C0B0). `band` loads grsprint's RUN-threshold word with
this player's value -- the grsprint preset's 25 or 60 when his switch is on,
93 when it is off -- calls the function, and clears his switch when it answers
"stationary". So the band threshold, the speed and the stop are all per
player.

Why this was needed. grsprint keeps one latch for everybody and clears it in
the stationary branch of that function, and the forward axis of every pad
reaches that function every frame even when the stick is centred:
`RSInputImpl::Update` queues a 0x13D event with value 0 for both idle pads
(run in the interpreter on the user's split-screen save BDBB7C5C). An idle
player 2 therefore switched player 1's sprint off every frame, and the first
version of this module only ever sped up player 1.

grsprint's own words still run -- its L3 toggle flips the threshold word, its
stop branch writes 93 into it -- but `band` rewrites that word before every
read, so neither has a lasting effect. The word is now a per-call argument.

Velocity. The avatar branch's next call after choosing `speed` is the leg-wound
test, `jalr t9` at **0x003AC6CC** (delay slot `move a0, s1`). It becomes
`jal vel`; `vel` changes `f20` and then jumps to `t9`, so the leg-wound test
still runs and still returns to the stock code. When

  * the motion set is RUN (`HumanMotion + 0x3C == 2`),
  * he is upright (`HumanMotion + 0x18 == 0`),
  * he is player 1's or player 2's soldier (`SimHuman + 0x128` equals avatar
    id 0 or 1, `*(*0x00684A78 + 0x200 / 0x204)`), and
  * that player's switch is on,

the speed becomes 93 x factor and the two running flags are set, exactly as the
stock full-push branch sets them. Any push that gets the run band therefore
sprints at the full sprint speed in the stick's direction. The stance constants
still apply, so a sideways or backward sprint is faster by the same factor.
Wounded legs still multiply by 0.32 afterwards.

Feet. `HumanMotion::UpdateMotion` (0x00333040) resets the root bone's frame
speed to its default every frame (`MotionManager` vtable +0x60), then asks for
it back (vtable +0x5C, `GetFrameSpeed`) and throws the answer away, then
advances the skeleton (vtable +0x40). The dead call, `jalr t9` at
**0x00333118**, becomes `jal anim`. Under the same conditions (and control
type 0) `anim` multiplies the root bone's frames-per-second (`+0x148`) by the
factor and divides its seconds-per-frame (`+0x14C`). The body animation -- legs,
pelvis, spine, head, everything that inherits the root's rate -- plays that
much faster, so the stride keeps up with the ground. The two arm chains carry
their own motions and their own rate and are not touched, so a reload or a
weapon change while sprinting takes its normal time. The next frame's reset
puts the default back, so nothing accumulates and nothing needs restoring.
Footfall events ride the leg animation, so the footstep cadence rises with it.

Only the local players' soldiers are affected. AI soldiers (control type 1)
take the other branch of `CalculateCurrentVelocity`, and network copies
(control type 2) never run it at all (next section); both are excluded from
`anim` as well.

ONLINE
------

The owning console simulates its own soldier; nobody else runs its velocity
code. `SimHuman::UpdateMovement` (0x003AB700) calls `CalculateCurrentVelocity`
only when `IsLocalOwner` (owner byte `+0x13C` equals this machine's id).
Everyone else's copy is dead-reckoned from the owner's state messages:
`SimHumanState` packs position and *velocity* (+0x18 / +0x24, 0x003C1DF8 /
0x003C1E08), `HandleUpdateSimHuman` (0x003B8430) unpacks them, and
`ExtrapolateState` (0x003AC940) aims the copy at `received position + received
velocity x interval` and, once there, keeps moving it at the received velocity
(0x003AB7D8). The velocity sent is the one this module scales, so a sprinting
player moves at sprint speed on the other screen too.

Nothing snaps him back. A receiving console snaps its copy onto the received
position when the two are more than 4 m apart (0x003B8560) -- towards the
owner, never back. The host (the rules manager's `IsMaster`, vtable +0x48)
also validates each update first, in `0x003C18B0`: it refuses one that lands
15 m or more from its copy, or that needs more than 64 m/s on any axis over
the update interval, and only a refused update leads to the host pushing its
own state back. A 1.5 x sprint is 8.1 m/s, far inside both limits.

What the other console does NOT get is the faster animation: its copy runs the
run motion at the normal rate while moving at sprint speed, so the far view's
feet slide by the factor. Speeding up network copies would mean guessing a
sprint from the received speed, and the copy's speed also carries
dead-reckoning corrections, so that was left alone.

SPLIT SCREEN
------------

Both players sprint, each with his own L3, and each stops his own sprint by
stopping. Single player and online use player 1's switch, as before.

NOT ESTABLISHED
---------------

* Never played. The routines were run on the user's savestate RAM in an
  interpreter; nothing has been watched in the game.
* Footstep sounds and the noise the awareness system hears were not traced.
  They follow the leg animation, so a sprint should sound like a faster run.
* The band function is fed the forward axis only, so a push that is purely
  sideways counts as stopping and switches that player's sprint off.
* A third or fourth pad (multitap) is ignored; only pads 0 and 1 have a
  switch.
* AI teammates move at their run animation's own pace (their branch of
  CalculateCurrentVelocity, 0x003AC7D8, scales nothing; Ghost Recon's x2 / x3
  catch-up multipliers there are gone), so a sprinting leader should outpace
  them.
* The running flag +0x47C also drives a value at +0x494 that grows at 0.3 per
  second up to 14 while it is set; sprinting sets it as a full push does.
"""

from __future__ import annotations

import struct

from . import grsprint
from .grasm import assemble


class SprintSpeedError(Exception):
    pass


#: The tail of lgAudWriteVag (USB headset library): 60 words after the 128
#: bytes grcamera's cave C uses. The function has no caller in the executable
#: or either overlay, and no option writes these words.
CAVE = 0x005539A8
CAVE_END = 0x00553A98
#: newlib's fgets, 78 words, no caller in the executable or either overlay.
#: This module uses the first 42 (0x00167C48..0x00167CEF); 36 stay free.
CAVE2 = 0x00167C48
CAVE2_END = 0x00167D80

#: `jalr t9` = the leg-wound test (vtable +0x538) right after the avatar branch
#: of CalculateCurrentVelocity has chosen the speed in f20.
HOOK_VEL = 0x003AC6CC
#: `jalr t9` = MotionManager::GetFrameSpeed(root), whose answer UpdateMotion
#: never reads, right after SetDefaultFrameSpeed(root).
HOOK_ANIM = 0x00333118
HOOK_STOCK = 0x0320F809
#: `sll v1, s4, 5` in RSInputImpl::Update's pad loop, recomputing what the
#: delay slot at 0x0019A4BC already put in v1 (no branch lands between).
HOOK_PAD = 0x0019A4C8
HOOK_PAD_STOCK = 0x00141940
#: `jal 0x25D080` -- the only call of GetMovementSpeedFromInput, in IkeUIMgr's
#: forward-axis (key 0x13D) handler.
HOOK_BAND = 0x0025C108
HOOK_BAND_STOCK = 0x0C097420
BAND_FN = 0x0025D080

#: IRSGameStateMgr*; GetAvatarID(i) reads +0x200 + 4i of it (as grobserver).
STATEP = 0x00684A78
#: grsprint's RUN-threshold word holds 93.0 when its sprint is off.
RUN_OFF = grsprint.RUN_STOCK
RUN_STOCK_SPEED = 93.0

FACTORS = {"1.25": 1.25, "1.5": 1.5}
PRESETS = ("off",) + tuple(FACTORS)
PRESET_DEFAULT = "off"
#: grsprint presets that lower the run threshold
NEEDS = ("walk", "any")

#: retail words of the cave (lgAudWriteVag + 0x80 .. + 0x16F)
_CAVE_STOCK = (
    "2484F638 0C05ADDE 00000000 3C028000 1000002E 34420004 "
    "0C05E8C8 0120202D 3C030058 2472C60C 0200282D 8E460000 "
    "ACD3000C 24C40030 8E220000 ACC20020 0C05A8D6 8E260000 "
    "8E430000 3C040069 24050015 A0740012 24841240 0000302D "
    "240A0030 8E280000 0000582D 8E470000 2508003F AFA00000 "
    "00084103 00E0482D 0C05F5AA 00084100 3C04005A 1440000A "
    "2484F670 8E420000 8C430020 8C500000 AE230000 0C05E8C0 "
    "8EA40000 10000007 0200102D 00000000 0C05ADDE AE200000 "
    "0C05E8C0 8EA40000 3C028000 DFB00010 DFB10018 DFB20020 "
    "DFB30028 DFB40030 DFB50038 DFBF0040 03E00008 27BD0050 ")
#: retail words of fgets (0x00167C48 .. 0x00167D7F)
_CAVE2_STOCK = (
    "27BDFFC0 FFB30018 00A0982D FFB50028 0080A82D 2A620002 2673FFFF FFB10008 "
    "00C0882D FFB40020 02A0A02D FFB00000 FFB20010 10400012 FFBF0030 10000035 "
    "0000102D 00000000 24630001 8E220004 00728023 AE230000 00501023 0240282D "
    "AE220004 0280202D 0C05A8D6 0200302D 02901821 10000026 A0600000 00000000 "
    "8E300004 5600000B 8E320000 0C05B23E 0220202D 50400006 8E300004 5695001C "
    "A2800000 1000001B 0000102D 00000000 8E320000 0270102B 0262800B 2405000A "
    "0240202D 0C05A878 0200302D 0280202D 0040182D 02709823 0240282D 1460FFDA "
    "0200302D 8E230004 0290A021 8E220000 00701823 00501021 AE230004 0C05A8D6 "
    "AE220000 5660FFDF 8E300004 A2800000 02A0102D DFB00000 DFB10008 DFB20010 "
    "DFB30018 DFB40020 DFB50028 DFBF0030 03E00008 27BD0040 ")


def _words(hexes):
    s = "".join(hexes.split())
    if len(s) % 8:
        raise SprintSpeedError("stock table is not whole words")
    return [int(s[i:i + 8], 16) for i in range(0, len(s), 8)]


CAVE_STOCK = _words(_CAVE_STOCK)
CAVE2_STOCK = _words(_CAVE2_STOCK)

JS_STOCK = {HOOK_VEL: HOOK_STOCK, HOOK_ANIM: HOOK_STOCK,
            HOOK_PAD: HOOK_PAD_STOCK, HOOK_BAND: HOOK_BAND_STOCK}
JS_STOCK.update({CAVE + 4 * i: w for i, w in enumerate(CAVE_STOCK)})
JS_STOCK.update({CAVE2 + 4 * i: w for i, w in enumerate(CAVE2_STOCK)})

#: the speed and the feet (lgAudWriteVag tail)
_SRC = """
; ---- vel: stands in for `jalr t9` at 0x3AC6CC.
; a0 = SimHuman (the jal's delay slot), t9 = the leg-wound test,
; f20 = the speed CalculateCurrentVelocity just chose.
vel:
    lw    v0, 0x458(a0)          ; HumanMotion
    li    t0, 2
    lw    v1, 0x3c(v0)           ; motion set: 2 = run
    bne   v1, t0, vel_out
    lw    v1, 0x18(v0)           ; (delay) stance: 0 = upright
    bnez  v1, vel_out
    lw    v1, 0x128(a0)          ; (delay) his object id
    lui   at, %hi(STATEP)
    lw    t1, %lo(STATEP)(at)    ; IRSGameStateMgr
    lui   at, %hi(LAT)
    lw    t0, 0x200(t1)          ; player 1's avatar id
    beq   v1, t0, vel_p
    lw    t2, %lo(LAT)(at)       ; (delay) player 1's switch
    lw    t0, 0x204(t1)          ; player 2's avatar id
    bne   v1, t0, vel_out        ; nobody's: stock
    lw    t2, %lo(LAT+4)(at)     ; (delay) player 2's switch
vel_p:
    beqz  t2, vel_out
    lui   at, %hi(KRUN)          ; (delay)
    lwc1  f20, %lo(KRUN)(at)     ; speed = 93 x factor
    li    v0, 1
    sb    v0, 0x47c(a0)          ; the flags the stock full-push branch sets
    sb    v0, 0x45c(a0)
vel_out:
    jr    t9                     ; the leg-wound test, returning to 0x3AC6D4
    nop

; ---- anim: stands in for the dead `jalr t9` (GetFrameSpeed) at 0x333118.
; s0 = HumanMotion, a0 = its MotionManager; the root bone's frame speed was
; reset to its default two calls earlier.
anim:
    lw    v0, 4(s0)              ; SimHuman
    li    t0, 2
    lw    v1, 0x3c(s0)           ; motion set: 2 = run
    bne   v1, t0, anim_out
    lw    v1, 0x18(s0)           ; (delay) stance: 0 = upright
    bnez  v1, anim_out
    lw    v1, 0x138(v0)          ; (delay) control type: 0 = a person's
    bnez  v1, anim_out
    lw    v1, 0x128(v0)          ; (delay) his object id
    lui   at, %hi(STATEP)
    lw    t1, %lo(STATEP)(at)
    lui   at, %hi(LAT)
    lw    t0, 0x200(t1)          ; player 1's avatar id
    beq   v1, t0, anim_p
    lw    t2, %lo(LAT)(at)       ; (delay)
    lw    t0, 0x204(t1)          ; player 2's avatar id
    bne   v1, t0, anim_out
    lw    t2, %lo(LAT+4)(at)     ; (delay)
anim_p:
    beqz  t2, anim_out
    lw    a0, 0x1c(a0)           ; (delay) root bone
    beqz  a0, anim_out
    lui   at, %hi(KANIM)         ; (delay)
    lwc1  f0, %lo(KANIM)(at)     ; factor
    lwc1  f1, %lo(KINV)(at)      ; 1 / factor
    lwc1  f2, 0x148(a0)          ; frames per second
    lwc1  f3, 0x14c(a0)          ; seconds per frame
    mul.s f2, f2, f0
    mul.s f3, f3, f1
    swc1  f2, 0x148(a0)
    swc1  f3, 0x14c(a0)
anim_out:
    jr    ra
    nop

KRUN:
    .word KRUN_BITS
KANIM:
    .word KANIM_BITS
KINV:
    .word KINV_BITS
"""

#: the per-player switches (fgets)
_SRC2 = """
; ---- pad: stands in for `sll v1, s4, 5` at 0x19A4C8, once per pad per frame.
; s4 = pad index, s1 -> that pad's ControllerInfo pointer. v0 is not live
; here (grsprint's note on 0x19A4C0) and a0 is reloaded before its next use.
pad:
    sltiu t0, s4, 2
    beqz  t0, pad_out            ; pads 0 and 1 only
    lw    t1, 0(s1)              ; (delay) ControllerInfo
    lw    t0, 0x54(t1)           ; held this frame
    lw    t1, 0x58(t1)           ; held last frame
    nor   t1, t1, zero
    and   t0, t0, t1
    andi  t0, t0, 0x200          ; bit 9 = L3, pressed this frame
    beqz  t0, pad_out
    sll   t1, s4, 2              ; (delay)
    lui   at, %hi(LAT)
    addu  at, at, t1
    lw    t0, %lo(LAT)(at)
    xori  t0, t0, 1              ; click = toggle, as grsprint's L3
    sw    t0, %lo(LAT)(at)
pad_out:
    jr    ra
    sll   v1, s4, 5              ; (delay) the instruction this call replaced

; ---- band: stands in for `jal 0x25D080` at 0x25C108.
; a0 = IkeUIMgr (the jal's delay slot), a1 = the forward-axis value;
; s0 = player 1's avatar id, 0x58(sp) = this message's avatar id.
band:
    lw    t0, 0x58(sp)
    lui   at, %hi(LAT)
    addiu t1, at, %lo(LAT)
    bne   t0, s0, band_p         ; not player 1's message: player 2's switch
    addiu t2, t1, 4              ; (delay)
    move  t2, t1
band_p:
    lw    t0, 0(t2)
    beqz  t0, band_set
    lui   t3, OFF_HI             ; (delay) 93.0: the stock run threshold
    lui   t3, ON_HI              ; grsprint's preset threshold
band_set:
    lui   at, %hi(VAR)
    sw    t3, %lo(VAR)(at)       ; grsprint's threshold word, for this call
    addiu sp, sp, -16
    sd    ra, 0(sp)
    jal   BAND_FN
    sw    t2, 8(sp)              ; (delay)
    lw    t2, 8(sp)
    ld    ra, 0(sp)
    bnez  v0, band_out           ; 0 = stationary
    addiu sp, sp, 16             ; (delay)
    sw    zero, 0(t2)            ; he stopped: his sprint ends
band_out:
    jr    ra
    nop

LAT:
    .word 0                      ; player 1's sprint switch
    .word 0                      ; player 2's
"""


def _f2b(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


def _caves(factor: float, sprint_l3: str):
    """(words, labels, words2, labels2)"""
    words2, labels2 = assemble(_SRC2, CAVE2, {
        "VAR": grsprint._cave(sprint_l3)[1],
        "OFF_HI": RUN_OFF >> 16,
        "ON_HI": grsprint.BANDS[sprint_l3] >> 16,
        "BAND_FN": BAND_FN,
    })
    words, labels = assemble(_SRC, CAVE, {
        "LAT": labels2["LAT"],
        "STATEP": STATEP,
        "KRUN_BITS": _f2b(RUN_STOCK_SPEED * factor),
        "KANIM_BITS": _f2b(factor),
        "KINV_BITS": _f2b(1.0 / factor),
    })
    if CAVE + 4 * len(words) > CAVE_END or CAVE2 + 4 * len(words2) > CAVE2_END:
        raise SprintSpeedError("sprint-speed cave outgrows its hole")
    return words, labels, words2, labels2


def edits(preset: str = PRESET_DEFAULT, sprint_l3: str = "off"):
    """[(va, value, stock, note)]. Nothing unless both a factor and an L3
    sprint preset are chosen: the run threshold this steers is grsprint's."""
    if preset not in PRESETS:
        raise SprintSpeedError("no such sprint speed: %r" % (preset,))
    if preset == "off" or sprint_l3 not in NEEDS:
        return []
    words, labels, words2, labels2 = _caves(FACTORS[preset], sprint_l3)
    out = [(CAVE + 4 * i, w, CAVE_STOCK[i], "sprint speed x%s: speed and feet" % preset)
           for i, w in enumerate(words)]
    out += [(CAVE2 + 4 * i, w, CAVE2_STOCK[i], "sprint speed: per-player L3 switches")
            for i, w in enumerate(words2)]
    for va, label, lab, stock, note in (
            (HOOK_VEL, "vel", labels, HOOK_STOCK,
             "sprint speed: run speed while that player's sprint is on"),
            (HOOK_ANIM, "anim", labels, HOOK_STOCK,
             "sprint speed: body animation keeps up"),
            (HOOK_PAD, "pad", labels2, HOOK_PAD_STOCK,
             "sprint speed: each pad's L3 toggles its player's sprint"),
            (HOOK_BAND, "band", labels2, HOOK_BAND_STOCK,
             "sprint speed: run threshold per player; stopping ends his sprint")):
        out.append((va, assemble("jal %#x" % lab[label], va)[0][0], stock, note))
    return out


def js_edits(v: dict):
    return edits(v.get("js_sprint_speed", PRESET_DEFAULT),
                 v.get("js_sprint_l3", grsprint.PRESET_DEFAULT))


def _fpu_hazards(words):
    """mtc1 read by the next instruction, div/sqrt read within two, or a
    compare straight before bc1 (grcamera's rule)."""
    bad = []

    def writes(w):
        if w >> 26 == 0x11 and (w >> 21) & 31 == 0x04:
            return 1, (w >> 11) & 31
        if w >> 26 == 0x11 and (w >> 21) & 31 == 0x10 and w & 0x3F in (3, 4):
            return 2, (w >> 6) & 31
        return None

    def reads(w):
        r = set()
        if w >> 26 == 0x11 and (w >> 21) & 31 == 0x10:
            r.add((w >> 16) & 31)
            if w & 0x3F != 4:
                r.add((w >> 11) & 31)
        if w >> 26 == 0x39:
            r.add((w >> 16) & 31)
        return r

    for i, w in enumerate(words):
        wr = writes(w)
        if wr:
            gap, reg = wr
            for k in range(1, gap + 1):
                if i + k < len(words) and reg in reads(words[i + k]):
                    bad.append(i)
        if (w >> 26 == 0x11 and (w >> 21) & 31 == 0x10 and w & 0x30 == 0x30
                and i + 1 < len(words) and words[i + 1] >> 16 in (0x4500, 0x4501)):
            bad.append(i)
    return bad


# =========================================================================
# Ghost Recon (SLUS-20613)
# =========================================================================
#
# Ghost Recon has no L3 sprint of its own, so the whole feature is here: the
# per-player switch, the lowered run threshold (grsprint's idea), the speed
# and the legs. Same shape as Jungle Storm, different numbers:
#
# * L3 is NOT free in the stock layout: `RSInputImpl::MapForAction`
#   (0x0054F3E0) binds button index 9 to key 0x56 in all three pad
#   configurations, and `IkeInputMgr::MapInputForAction` binds key 0x56 to
#   message 0x11, kMsgID_PeekLeft (0x0017125C; pad 2's 0x11B at 0x001713C4).
#   grcontrols' Jungle Storm layouts give L3 the key -0xC5, which the input
#   scan skips, so the sprint needs one of those layouts.
# * `IkeUIMgr::GetMovementSpeedFromInput` (0x00270540) bands the forward axis
#   at 80 / 50 / 35 (run / walk / shuffle); its only caller is the forward-axis
#   case of `IkeUIMgr::ProcessMessage` at 0x00272958, which holds the message's
#   avatar id in s2 and player 1's avatar id at 0xB8(sp) (it compares the two
#   itself at 0x002728F0). "Walk" moves the run threshold to 50, "any" to 35.
# * The stick values are the pad byte minus 128, shifted 32 towards the
#   centre (RSInputImpl::Update): -96 is a full push forward, 95 a full push
#   back, and a centred stick reads about +-32.
# * The player's velocity is built from the stick words the MoveForward /
#   MoveRight messages leave at SimHuman +0x62C / +0x630, per axis, linear
#   past a dead zone of 35 (+0.2 m/s from 91), then multiplied by 1.2
#   (0x003CCFD8): a full forward push is (65 x 0.0785 + 0.2) x 1.2 = 6.4 m/s.
#   `GetPlayerRunFactor` still multiplies the root-motion
#   vector at 0x003CCBAC, but for a person's soldier that vector's ground
#   components are then overwritten by the stick-built ones, so the run factor
#   is not his speed here either. Nothing but CalculateCurrentVelocity reads
#   +0x62C / +0x630.
#
# So: while a player's switch is on, he is running (motion set 2), upright and
# the forward stick is really pushed (|value| > 35), `gvel` scales his two
# stick words up so the larger reaches 96 -- a full push in the same
# direction, which gives the stock full-run speed at any push that got the run
# band -- and swaps the 1.2 for 1.2 x the sprint factor. It runs in place of
# the first call of CalculateCurrentVelocity (ClearVelocities, 0x003CCA9C)
# and ends by jumping to it. The legs are Jungle Storm's `anim`, at
# HumanMotion::UpdateMotion's dead GetFrameSpeed call (0x00356EF8).
#
# Caves: five template destructors in 0x100000..0x1FFFFF whose only reference
# in the executable is their own Metrowerks exception-index (@EX@) entry --
# nothing calls them, no vtable or unwinding action (@ET@) names them, and no
# Ghost Recon option writes them or records them.

GR_CAVE = {   # name: (start, words, retail words)
    "vel": (0x00107B40, 45,        # __dt__Q23std4_BCDFv
            "27BDFFD0 FFBF0020 7FB10010 7FB00000 70808628 12000021 70A08E28 1200001A "
            "0011143C 8E030000 8C620008 14400007 00000000 50400004 24020001 10000003 "
            "AC620008 24020001 AC620008 8C620008 2442FFFF AC620008 0002180B AE030000 "
            "8E020000 10400007 00000000 10400003 00000000 0C040B14 8C44000C 0C040B14 "
            "8E040000 0011143C 0002143F 18400004 72001628 0C040B14 72002628 72001628 "
            "DFBF0020 7BB10010 7BB00000 03E00008 27BD0030 "),
    "anim": (0x0015E6A0, 37,       # __dt__48RSPair<Ci,35RSPair<11ShooterData,11ShooterData>>Fv
             "27BDFFD0 FFBF0020 7FB10010 7FB00000 70808628 12000019 70A08E28 26020004 "
             "10400011 0011143C 26040014 50800007 26040004 3C020059 24422070 AE020014 "
             "0C04D860 70002E28 26040004 10800005 3C020059 24422070 AE020004 0C04D860 "
             "70002E28 0011143C 0002143F 18400004 72001628 0C040B14 72002628 72001628 "
             "DFBF0020 7BB10010 7BB00000 03E00008 27BD0030 "),
    "band": (0x001CC7B0, 28,       # __dt__15CampaignMissionFv
             "27BDFFD0 FFBF0020 7FB10010 7FB00000 70808E28 12200010 70A08628 26240D24 "
             "0C05B0E4 2405FFFF 3C02001D 72202628 2445C490 24060074 0C052770 2407001D "
             "0010143C 0002143F 18400004 72201628 0C040B14 72202628 72201628 DFBF0020 "
             "7BB10010 7BB00000 03E00008 27BD0030 "),
    "pad": (0x0014C870, 24,        # __dt__Q23std68vector<...locale5facet...>Fv
            "27BDFFD0 FFBF0000 AFA40010 A7A50020 8FA20010 1040000D 00000000 8FA40010 "
            "70002E28 0C053234 00000000 87A20020 0002143C 0002143F 18400004 00000000 "
            "8FA40010 0C040B14 00000000 8FA20010 DFBF0000 27BD0030 03E00008 00000000 "),
    "norm": (0x0012D940, 24,       # __dt__10RSArray<l>Fv
             "27BDFFD0 FFBF0020 7FB10010 7FB00000 70808E28 1220000C 70A08628 8E240000 "
             "10800004 0010143C 0C040AF8 00000000 0010143C 0002143F 18400004 72201628 "
             "0C040B14 72202628 72201628 DFBF0020 7BB10010 7BB00000 03E00008 27BD0030 "),
}
GR_CAVE_STOCK = {n: _words(h) for n, (_a, _n, h) in GR_CAVE.items()}

GR_HOOK = {   # name: (va, stock)
    "vel": (0x003CCA9C, 0x0C0F891C),     # jal SimHumanState::ClearVelocities
    "anim": (0x00356EF8, 0x0320F809),    # jalr t9 = MotionManager::GetFrameSpeed (dead)
    "pad": (0x0054E570, 0xAFA300B0),     # sw v1, 0xB0(sp), once per pad per frame
    "band": (0x00272958, 0x0C09C150),    # jal IkeUIMgr::GetMovementSpeedFromInput
}
#: in place: the run threshold (80.0) and the velocity's 1.2 become variables
GR_THR_AT = ((0x002705E4, 0x3C0242A0), (0x002705E8, 0x44820000))
GR_KMUL_AT = ((0x003CCFD8, 0x3C023F99), (0x003CCFDC, 0x3442999A))
GR_STATEP = 0x005DFF40            # IRSGameStateMgr*: IkeStateMgr::GetAvatarID reads +0x1F8 + 4i
GR_BAND_FN = 0x00270540
GR_CLEARVEL = 0x003E2470
GR_RUN_STOCK = 0x42A00000         # 80.0
GR_BANDS = {"walk": 0x42480000,   # 50.0
            "any": 0x420C0000}    # 35.0, the shuffle threshold: anything past it runs
GR_L3_PRESETS = ("off",) + tuple(GR_BANDS)
GR_LAYOUTS = ("jungle_storm", "jungle_storm_buttons")
GR_K12 = 0x3F99999A               # 1.2

GR_STOCK = {va: st for va, st in GR_HOOK.values()}
GR_STOCK.update(dict(GR_THR_AT))
GR_STOCK.update(dict(GR_KMUL_AT))
for _n, (_a, _c, _h) in GR_CAVE.items():
    GR_STOCK.update({_a + 4 * i: w for i, w in enumerate(GR_CAVE_STOCK[_n])})


def _rtype(fn, rs=0, rt=0, rd=0):
    return (rs << 21) | (rt << 16) | (rd << 11) | fn


_T0, _T1, _T6, _T7 = 8, 9, 14, 15
_GR_SYMS = {
    "DIV_T7": _rtype(0x1A, _T7, _T6),        # div t7, t6
    "MFLO_T7": _rtype(0x12, rd=_T7),         # mflo t7
    "MULT_T0": _rtype(0x18, _T0, _T7, _T0),  # mult t0, t0, t7 (R5900: rd = LO)
    "MULT_T1": _rtype(0x18, _T1, _T7, _T1),  # mult t1, t1, t7
    "MOVN_T1": _rtype(0x0B, 0, 1, _T1),      # movn t1, zero, at
    "MOVN_T5": _rtype(0x0B, 0, 1, 13),       # movn t5, zero, at
    "MOVN_T6": _rtype(0x0B, 13, 1, _T6),     # movn t6, t5, at
    "STATEP": GR_STATEP,
    "BAND_FN": GR_BAND_FN,
    "CLEARVEL": GR_CLEARVEL,
    "RUN_HI": GR_RUN_STOCK >> 16,
}

_GR_SRC_PAD = """
; ---- gpad: stands in for `sw v1, 0xB0(sp)` at 0x54E570 (RSInputImpl::Update,
; once per pad per frame; the jal's delay slot loads a0 = held buttons).
; s0 = pad index, s3 = that pad's ControllerInfo.
gpad:
    sw    v1, 0xb0(sp)           ; the instruction this call replaced
    sltiu t0, s0, 2
    beqz  t0, gpad_out           ; pads 0 and 1 only
    lw    t1, 0x58(s3)           ; (delay) held last frame
    lw    t0, 0x54(s3)           ; held this frame
    nor   t1, t1, zero
    and   t0, t0, t1
    andi  t0, t0, 0x200          ; bit 9 = L3, pressed this frame
    beqz  t0, gpad_out
    sll   t1, s0, 2              ; (delay)
    lui   at, %hi(LAT)
    addu  at, at, t1
    lw    t0, %lo(LAT)(at)
    xori  t0, t0, 1
    sw    t0, %lo(LAT)(at)
gpad_out:
    jr    ra
    nop
LAT:
    .word 0                      ; player 1's sprint switch
    .word 0                      ; player 2's
"""

_GR_SRC_BAND = """
; ---- gband: stands in for `jal 0x270540` at 0x272958 (delay slot: nop).
; a0 = IkeUIMgr, a1 = forward-axis value; s2 = this message's avatar id,
; 0xB8(sp) = player 1's avatar id.
gband:
    lw    t0, 0xb8(sp)
    lui   at, %hi(LAT)
    addiu t1, at, %lo(LAT)
    bne   t0, s2, gband_p        ; not player 1's message: player 2's switch
    addiu t2, t1, 4              ; (delay)
    move  t2, t1
gband_p:
    lw    t0, 0(t2)
    beqz  t0, gband_set
    lui   t3, RUN_HI             ; (delay) 80.0: the stock run threshold
    lui   t3, ON_HI
gband_set:
    lui   at, %hi(THR)
    sw    t3, %lo(THR)(at)       ; read back at 0x2705E4 for this call
    addiu sp, sp, -16
    sd    ra, 0(sp)
    jal   BAND_FN
    sw    t2, 8(sp)              ; (delay)
    lw    t2, 8(sp)
    ld    ra, 0(sp)
    bnez  v0, gband_out          ; 0 = stationary
    addiu sp, sp, 16             ; (delay)
    sw    zero, 0(t2)            ; he stopped: his sprint ends
gband_out:
    jr    ra
    nop
THR:
    .word 0x42a00000
"""

_GR_SRC_VEL = """
; ---- gvel: stands in for `jal ClearVelocities` at 0x3CCA9C, the first call of
; SimHuman::CalculateCurrentVelocity. s0 = SimHuman, a0 = s0 + 0x1B4 (kept).
gvel:
    lui   at, %hi(KMUL)
    lw    t0, %lo(K12)(at)
    sw    t0, %lo(KMUL)(at)      ; the stock 1.2 unless he sprints
    lw    v0, 0x458(s0)          ; HumanMotion
    li    t0, 2
    lw    v1, 0x3c(v0)           ; motion set: 2 = run
    bne   v1, t0, gvel_out
    lw    v1, 0x18(v0)           ; (delay) stance: 0 = upright
    bnez  v1, gvel_out
    lw    v1, 0x128(s0)          ; (delay) his object id
    lui   at, %hi(STATEP)
    lw    t1, %lo(STATEP)(at)
    lui   at, %hi(LAT)
    lw    t0, 0x1f8(t1)          ; player 1's avatar id
    beq   v1, t0, gvel_p
    lw    t2, %lo(LAT)(at)       ; (delay)
    lw    t0, 0x1fc(t1)          ; player 2's avatar id
    bne   v1, t0, gvel_out
    lw    t2, %lo(LAT+4)(at)     ; (delay)
gvel_p:
    beqz  t2, gvel_out
    lw    t0, 0x62c(s0)          ; (delay) forward stick
    sra   t3, t0, 31
    xor   t4, t0, t3
    subu  t4, t4, t3             ; |forward|
    slti  at, t4, 36
    bnez  at, gvel_out           ; inside the dead zone: letting go, not sprinting
    lui   at, %hi(KMUL)          ; (delay)
    lw    t1, %lo(KSPR)(at)
    j     GNORM
    sw    t1, %lo(KMUL)(at)      ; (delay) 1.2 x the sprint factor
gvel_out:
    j     CLEARVEL               ; ClearVelocities, returning to 0x3CCAA4
    nop
K12:
    .word 0x3f99999a
KSPR:
    .word KSPR_BITS
KMUL:
    .word 0x3f99999a             ; read back at 0x3CCFD8
"""

_GR_SRC_NORM = """
; ---- gnorm: t0 = forward stick, t4 = |forward| > 35. Scale both stick words
; so the larger reaches 96 -- Ghost Recon's full deflection -- keeping the
; direction, then back to gvel_out.
gnorm:
    lw    t1, 0x630(s0)          ; sideways stick
    sra   t3, t1, 31
    xor   t5, t1, t3
    subu  t5, t5, t3             ; |sideways|
    slti  at, t5, 36             ; inside the dead zone (a centred stick reads
    .word MOVN_T1                ;   about 32): movn t1, zero, at -- count it as 0
    .word MOVN_T5                ;   movn t5, zero, at
    slt   at, t4, t5
    move  t6, t4                 ; m = |forward|
    .word MOVN_T6                ; movn t6, t5, at: or |sideways| if larger
gnorm_m:
    li    t7, 0x6000             ; 96 x 256
    .word DIV_T7                 ; div t7, t6
    nop
    nop
    .word MFLO_T7                ; t7 = 96 x 256 / m
    nop
    nop
    .word MULT_T0                ; t0 = forward x t7
    .word MULT_T1                ; t1 = sideways x t7
    sra   t0, t0, 8
    sra   t1, t1, 8
    sw    t0, 0x62c(s0)
    j     GVEL_OUT
    sw    t1, 0x630(s0)          ; (delay)
"""

_GR_SRC_ANIM = """
; ---- ganim: stands in for the dead `jalr t9` (GetFrameSpeed) at 0x356EF8,
; as Jungle Storm's anim. s0 = HumanMotion, a0 = its MotionManager.
ganim:
    lw    v0, 4(s0)              ; SimHuman
    li    t0, 2
    lw    v1, 0x3c(s0)           ; motion set: 2 = run
    bne   v1, t0, ganim_out
    lw    v1, 0x18(s0)           ; (delay) stance: 0 = upright
    bnez  v1, ganim_out
    lw    v1, 0x138(v0)          ; (delay) control type: 0 = a person's
    bnez  v1, ganim_out
    lw    v1, 0x128(v0)          ; (delay) his object id
    lui   at, %hi(STATEP)
    lw    t1, %lo(STATEP)(at)
    lui   at, %hi(LAT)
    lw    t0, 0x1f8(t1)
    beq   v1, t0, ganim_p
    lw    t2, %lo(LAT)(at)       ; (delay)
    lw    t0, 0x1fc(t1)
    bne   v1, t0, ganim_out
    lw    t2, %lo(LAT+4)(at)     ; (delay)
ganim_p:
    beqz  t2, ganim_out
    lw    a0, 0x1c(a0)           ; (delay) root bone
    beqz  a0, ganim_out
    lui   at, %hi(KANIM)         ; (delay)
    lwc1  f0, %lo(KANIM)(at)
    lwc1  f1, %lo(KINV)(at)
    lwc1  f2, 0x148(a0)          ; frames per second
    lwc1  f3, 0x14c(a0)          ; seconds per frame
    mul.s f2, f2, f0
    mul.s f3, f3, f1
    swc1  f2, 0x148(a0)
    swc1  f3, 0x14c(a0)
ganim_out:
    jr    ra
    nop
KANIM:
    .word KANIM_BITS
KINV:
    .word KINV_BITS
"""


def _gr_caves(factor: float, sprint_l3: str):
    """{name: (words, labels)}"""
    out = {}
    s = dict(_GR_SYMS)
    out["pad"] = assemble(_GR_SRC_PAD, GR_CAVE["pad"][0], s)
    s["LAT"] = out["pad"][1]["LAT"]
    s["ON_HI"] = GR_BANDS[sprint_l3] >> 16
    out["band"] = assemble(_GR_SRC_BAND, GR_CAVE["band"][0], s)
    s["GNORM"] = GR_CAVE["norm"][0]
    s["KSPR_BITS"] = _f2b(1.2 * factor)
    out["vel"] = assemble(_GR_SRC_VEL, GR_CAVE["vel"][0], s)
    s["GVEL_OUT"] = out["vel"][1]["gvel_out"]
    out["norm"] = assemble(_GR_SRC_NORM, GR_CAVE["norm"][0], s)
    s["KANIM_BITS"] = _f2b(factor)
    s["KINV_BITS"] = _f2b(1.0 / factor)
    out["anim"] = assemble(_GR_SRC_ANIM, GR_CAVE["anim"][0], s)
    for n, (words, _l) in out.items():
        if len(words) > GR_CAVE[n][1]:
            raise SprintSpeedError("GR %s cave outgrows its hole" % n)
    if out["norm"][1]["gnorm"] != s["GNORM"]:
        raise SprintSpeedError("gnorm is not at the start of its cave")
    return out


def gr_sprint_edits(sprint_l3: str = "off", speed: str = PRESET_DEFAULT,
                    layout: str = "stock"):
    """[(va, value, stock, note)] for Ghost Recon."""
    if sprint_l3 not in GR_L3_PRESETS:
        raise SprintSpeedError("no such sprint preset: %r" % (sprint_l3,))
    if speed not in PRESETS:
        raise SprintSpeedError("no such sprint speed: %r" % (speed,))
    if sprint_l3 == "off" or layout not in GR_LAYOUTS:
        return []
    factor = FACTORS.get(speed, 1.0)
    caves = _gr_caves(factor, sprint_l3)
    names = ["pad", "band", "vel", "norm"] + (["anim"] if speed != "off" else [])
    out = []
    for n in names:
        start = GR_CAVE[n][0]
        for i, w in enumerate(caves[n][0]):
            out.append((start + 4 * i, w, GR_CAVE_STOCK[n][i], "sprint on L3: %s" % n))
    labels = {}
    for n in names:
        labels.update(caves[n][1])
    for n, label, note in (
            ("pad", "gpad", "sprint on L3: each pad's L3 toggles its player's sprint"),
            ("band", "gband", "sprint on L3: run threshold per player; stopping ends his sprint"),
            ("vel", "gvel", "sprint on L3: full-push speed x the sprint factor"),
            ("anim", "ganim", "sprint speed: body animation keeps up")):
        if n not in names:
            continue
        va, stock = GR_HOOK[n]
        out.append((va, assemble("jal %#x" % labels[label], va)[0][0], stock, note))
    thr = labels["THR"]
    for (va, stock), w in zip(GR_THR_AT, assemble(
            "lui at, %%hi(%#x)\nlwc1 f0, %%lo(%#x)(at)" % (thr, thr), GR_THR_AT[0][0])[0]):
        out.append((va, w, stock, "sprint on L3: the run threshold becomes a variable"))
    km = labels["KMUL"]
    for (va, stock), w in zip(GR_KMUL_AT, assemble(
            "lui at, %%hi(%#x)\nlw v0, %%lo(%#x)(at)" % (km, km), GR_KMUL_AT[0][0])[0]):
        out.append((va, w, stock, "sprint on L3: the velocity's 1.2 becomes a variable"))
    return out


def gr_edits(v: dict):
    return gr_sprint_edits(v.get("gr_sprint_l3", "off"),
                           v.get("gr_sprint_speed", PRESET_DEFAULT),
                           v.get("gr_controls", "stock"))


def _gr_selftest(gr_elf=None):
    bad = []
    for n, (a, cnt, _h) in GR_CAVE.items():
        if len(GR_CAVE_STOCK[n]) != cnt:
            bad.append("GR %s stock table has %d words" % (n, len(GR_CAVE_STOCK[n])))
        if not 0x00100000 <= a < 0x00200000:
            bad.append("GR %s cave outside 0x100000..0x1FFFFF" % n)
    if gr_elf is not None:
        for va, w in GR_STOCK.items():
            o = va - 0x00100000 + 0x80
            got = int.from_bytes(gr_elf[o:o + 4], "little")
            if got != w:
                bad.append("GR %08X: stock %08X, image %08X" % (va, w, got))
    inside = [(a, a + 4 * c) for a, c, _h in GR_CAVE.values()]
    singles = {va for va, _s in GR_HOOK.values()} | set(dict(GR_THR_AT)) | set(dict(GR_KMUL_AT))
    for l3 in GR_L3_PRESETS:
        for speed in PRESETS:
            for layout in ("stock",) + GR_LAYOUTS:
                e = gr_sprint_edits(l3, speed, layout)
                tag = "GR %s/%s/%s" % (l3, speed, layout)
                if (l3 == "off" or layout == "stock") and e:
                    bad.append(tag + ": writes words it should not")
                if len({va for va, *_ in e}) != len(e):
                    bad.append(tag + ": an address is written twice")
                for va, _w, stock, _t in e:
                    if stock is None or GR_STOCK.get(va) != stock:
                        bad.append("%s: %08X stock not registered" % (tag, va))
                    if not (va in singles or any(a <= va < b for a, b in inside)):
                        bad.append("%s: %08X outside the caves" % (tag, va))
            if l3 == "off":
                continue
            caves = _gr_caves(FACTORS.get(speed, 1.0), l3)
            for n, (w, lab) in caves.items():
                if _fpu_hazards(w):
                    bad.append("GR %s: FPU hazard in %s at %s" % (speed, n, _fpu_hazards(w)))
            lat = caves["pad"][1]["LAT"]
            if (lat + 0x8000) >> 16 != (lat + 4 + 0x8000) >> 16:
                bad.append("GR: the two switches straddle a %hi boundary")
            lv = caves["vel"][1]
            if len({(lv[k] + 0x8000) >> 16 for k in ("K12", "KSPR", "KMUL")}) != 1:
                bad.append("GR: velocity constants straddle a %hi boundary")
            la = caves["anim"][1]
            if (la["KANIM"] + 0x8000) >> 16 != (la["KINV"] + 0x8000) >> 16:
                bad.append("GR: animation constants straddle a %hi boundary")
    return bad


def selftest(js_elf: bytes = None, gr_elf: bytes = None):
    """[] = pass. Stock words against the retail images, layout, bounds."""
    bad = _gr_selftest(gr_elf)
    if len(CAVE_STOCK) != (CAVE_END - CAVE) // 4:
        bad.append("cave stock table has %d words" % len(CAVE_STOCK))
    if len(CAVE2_STOCK) != (CAVE2_END - CAVE2) // 4:
        bad.append("cave 2 stock table has %d words" % len(CAVE2_STOCK))
    for l3 in NEEDS:
        var = grsprint._cave(l3)[1]
        if not grsprint.CAVE <= var < grsprint.CAVE_END or RUN_OFF != 0x42BA0000:
            bad.append("grsprint's threshold word is not where this module writes it")
        if grsprint.BANDS[l3] & 0xFFFF or RUN_OFF & 0xFFFF:
            bad.append("a threshold does not fit a lui")
    if js_elf is not None:
        for va, w in JS_STOCK.items():
            o = va - 0x00100000 + 0x100
            got = int.from_bytes(js_elf[o:o + 4], "little")
            if got != w:
                bad.append("%08X: stock %08X, image %08X" % (va, w, got))
    hooks = (HOOK_VEL, HOOK_ANIM, HOOK_PAD, HOOK_BAND)
    for preset in PRESETS:
        for l3 in grsprint.PRESETS:
            e = edits(preset, l3)
            if (preset == "off" or l3 == "off") and e:
                bad.append("%s/%s: writes words without both options" % (preset, l3))
            if len({va for va, *_ in e}) != len(e):
                bad.append("%s/%s: an address is written twice" % (preset, l3))
            for va, _w, stock, _t in e:
                if stock is None or JS_STOCK.get(va) != stock:
                    bad.append("%s/%s: %08X stock not registered" % (preset, l3, va))
                if not (CAVE <= va < CAVE_END or CAVE2 <= va < CAVE2_END or va in hooks):
                    bad.append("%s/%s: %08X outside the caves" % (preset, l3, va))
            if preset == "off" or l3 not in NEEDS:
                continue
            words, labels, words2, labels2 = _caves(FACTORS[preset], l3)
            for w in (words, words2):
                if _fpu_hazards(w):
                    bad.append("%s: FPU hazard at word %s" % (preset, _fpu_hazards(w)))
            if len({labels[n] >> 16 for n in ("KRUN", "KANIM", "KINV")}) != 1:
                bad.append("%s: constants straddle a %%hi boundary" % preset)
            lat = labels2["LAT"]
            if (lat + 0x8000) >> 16 != (lat + 4 + 0x8000) >> 16:
                bad.append("the two switches straddle a %hi boundary")
    return bad


def card(prefix, group):
    from .model import CHOICE, Choice, Setting

    return Setting(
        prefix + "sprint_speed", "Sprint speed", CHOICE, PRESET_DEFAULT, group,
        choices=[
            Choice("off", "Off",
                   "Sprint on L3 only switches walking to running, as before."),
            Choice("1.25", "A quarter faster",
                   "While his L3 sprint is on a player runs at 1.25 times the "
                   "normal full run: about 6.7 m/s instead of 5.4."),
            Choice("1.5", "Half as fast again",
                   "While his L3 sprint is on a player runs at 1.5 times the "
                   "normal full run: about 8.1 m/s instead of 5.4."),
        ],
        requires={prefix + "sprint_l3": NEEDS},
        help="Makes the L3 sprint a real sprint. Click L3, push the stick, and "
             "he runs faster than the game's own full run. Stop moving and "
             "the sprint switches itself off. Click L3 again to switch it off "
             "yourself.\n\n"
             "Any push that gets the running pace sprints at full sprint "
             "speed in the direction you push. His legs speed up by the same "
             "amount, so his feet keep up with the ground.\n\n"
             "In split screen each player has his own sprint on his own L3, "
             "and only his own stopping ends it.\n\n"
             "Only while standing upright. Crouched and prone movement are "
             "unchanged, and a leg wound still slows him down as usual.\n\n"
             "Needs Sprint on L3 set to 'Half a push runs' or 'Any movement "
             "runs'. With this on, that choice also becomes per player.",
        caution="Never played.\n\n"
                "Pushing the stick straight sideways counts as stopping, so "
                "it ends the sprint.\n\n"
                "Online, the other player sees you move at your sprint speed, "
                "but your legs on their screen move at the normal running "
                "pace. The game does not pull you back.\n\n"
                "Sprinting counts as running for the enemy, so it is as loud "
                "and visible as a full run.\n\n"
                "AI teammates and enemies are not affected. Your teammates "
                "keep their normal running pace, so they fall behind while "
                "you sprint.",
        confidence="experimental")


def gr_cards(prefix="gr_", group="Controls"):
    """Ghost Recon's two settings: the L3 sprint itself and its speed."""
    from .model import CHOICE, Choice, Setting

    return [
        Setting(
            prefix + "sprint_l3", "Sprint on L3", CHOICE, "off", group,
            choices=[
                Choice("off", "Off", "As shipped."),
                Choice("walk", "Half a push runs",
                       "While sprint is on, pushing the stick a little past "
                       "half way runs, at full running speed."),
                Choice("any", "Any movement runs",
                       "While sprint is on, any push past the dead zone runs, "
                       "at full running speed. This is the closest to holding "
                       "Shift on the PC game."),
            ],
            requires={prefix + "controls": GR_LAYOUTS},
            help="Click L3 and the left stick runs him instead of walking "
                 "him, at full running speed however far you push. Stop "
                 "moving and it switches itself off; click L3 again to "
                 "switch it off yourself.\n\n"
                 "In split screen each player has his own sprint on his own "
                 "L3.\n\n"
                 "Only while standing upright; crouched and prone movement "
                 "are unchanged.\n\n"
                 "Needs the Jungle Storm controller layout: in Ghost Recon's "
                 "own layout L3 is peek left.",
            caution="Never played.\n\n"
                    "Pushing the stick straight sideways counts as stopping, "
                    "so it ends the sprint.\n\n"
                    "Running is loud and visible: the enemy notices a running "
                    "soldier far sooner than a walking one.\n\n"
                    "AI teammates and enemies are not affected.",
            confidence="experimental"),
        Setting(
            prefix + "sprint_speed", "Sprint speed", CHOICE, PRESET_DEFAULT, group,
            choices=[
                Choice("off", "Off",
                       "Sprint on L3 runs at the normal full running speed."),
                Choice("1.25", "A quarter faster",
                       "While his L3 sprint is on a player runs at 1.25 times "
                       "the normal full run: about 8.0 m/s instead of 6.4."),
                Choice("1.5", "Half as fast again",
                       "While his L3 sprint is on a player runs at 1.5 times "
                       "the normal full run: about 9.5 m/s instead of 6.4."),
            ],
            requires={prefix + "sprint_l3": NEEDS},
            help="Makes the L3 sprint faster than the game's own full run. "
                 "His legs speed up by the same amount, so his feet keep up "
                 "with the ground.\n\n"
                 "In split screen each player's sprint is his own.\n\n"
                 "Only while standing upright, and a leg wound still slows "
                 "him down as usual.",
            caution="Never played.\n\n"
                    "Your teammates keep their normal running pace, so they "
                    "fall behind while you sprint.\n\n"
                    "AI teammates and enemies are not affected.",
            confidence="experimental"),
    ]

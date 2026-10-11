r"""Grenade trajectory arc for Ghost Recon / Jungle Storm -- Ghost Recon (SLUS-20613).

Requested 2026-10-10: show the throw arc while a grenade is being charged, as
SOCOM 3 and Combined Assault do.

Ghost Recon only, for now: the routine needs a code cave, and Ghost Recon's
unstripped build lets its dead library stubs be enumerated exactly. Jungle
Storm has no symbols and no free run has been mapped there yet, so this card
does not appear on that profile.

THE THROW IS A TWO-POSITION SWITCH, NOT A CHARGE
------------------------------------------------

The request assumed "the longer you hold R1, the further it goes". It does
not. `SimHuman::StopUsingThrownItem` (GR 0x003D2260, JS 0x003B1850) loads the
hold time, compares it against 0.5 s ONCE, and picks one of two speeds:

    GR 0x003D227C  lwc1 f1, 0x4f0(s0)     ; hold time, SECONDS
    GR 0x003D2280  lui  v0, 0x3f00        ; 0.5 exactly
    GR 0x003D228C  c.olt.s f1, f0
    GR 0x003D2294  bc1f  ...              ; >= 0.5 -> Manly, else Wuss

* held < 0.5 s -> `WussGrenadeVelocity`  = **10.0 m/s** (`lui 0x4120`)
* held >= 0.5 s -> `ManlyGrenadeVelocity` = **25.0 m/s** (`lui 0x41C8`)

Both are compile-time constants in the `IkeConstants` constructor, at
`IkeConstants+0x238`/`+0x234` (GR) and `+0x240`/`+0x23C` (JS); the offsets
differ only because JS's `IkeConstants` grew 8 bytes. `SetGrenadeThrowType`
has exactly two callers in each image, both in that one function, with
immediates 0 and 1 -- so hold time reaches the throw through ONE boolean.

Consequence for this feature: the arc has exactly TWO shapes, so nothing has
to be integrated per frame. Two baked tables are enough.

Also: `HumanMotion+0x20` (the ThrowType) is only written on RELEASE, so it
still holds the PREVIOUS throw while you are winding up. The routine must read
the live hold timer and do the 0.5 s compare itself.

THE FLIGHT, IN CLOSED FORM
--------------------------

`SimProjectile` uses linear drag: force = -AirResistanceConstant x velocity,
so with k = AirResistance/Weight = 0.125 / 0.39 = 0.3205 /s for FRAG.PRJ, and
g 9.8, the exact solution is

    c(t) = 1 - e^(-k t)
    horizontal: p0.xy + (v0.xy / k) * c
    vertical:   p0.z  + (v0.z / k + G/k^2) * c - (G/k) * t

Checked against step-wise integration over 32 (angle, speed, time)
combinations: worst error **0.0019 m**. It also reproduces `grfrag`'s own
figures -- 36.0 / 52.6 / 62.4 m for x1 / x1.28125 / x1.4375 against the ~36 /
~53 / ~63 m that table documents -- so the model is the game's, not a guess.

The samples are spaced uniformly in `c`, not in `t`. Because horizontal
distance is exactly `(v0.xy/k) * c`, that spaces the arc evenly in DISTANCE
instead of bunching the segments at the far end where drag has slowed the
grenade. It also means `c[i] = i * C_MAX/N` is a multiply, so only `t[i]`
needs a table.

THE PRIMITIVE, AND WHY IT IS THE RIGHT ONE
------------------------------------------

`EffMgrPS2::DrawPlane` -- **GR 0x004663B0, JS 0x0042B910** -- draws one
world-space quad per call from a start point, a direction, an up vector, a
length and a width, with a colour at each end. Verified ABI (GR's DWARF
formals, nine GR call sites, two independent JS call sites)::

    $a0  float*  start      (float[4]; the callee overwrites [3] with 1.0)
    $a1  float*  direction  (3 floats, need NOT be normalised)
    $a2  float*  up         (3 floats)
    $f12 float   length     (metres)
    $f13 float   width      (metres)
    $a3  int*    colorStart (int[4] R,G,B,A -- 0..255, GS alpha 0x80 = opaque)
    $t0  int*    colorEnd
    $t1  bool    hasTexture (0 = untextured, what the tracers use)

World space is confirmed by the chain it runs: `DrawScissorTriangle` calls
`sceVu0ViewVolumeClip` then `sceVu0RotTransPers` against the LIVE view matrix
at `*GFX+0x2990`/`+0x2950` and appends to the display list at `*GFX+0xD8`.

**World units are METRES here, and Z is up** -- not Rainbow Six 3's 100 units
per metre. `gGeneralTracerScale` 4.0 and `gHumanTracerScale` 3.0 (GR
0x005603D8/0x005603E8) are dash lengths in metres.

**There is no viewport filter to defeat.** `TracerPS2::TestVisible` is
literally `jr $ra; addiu $v0,$zero,1` in BOTH games (GR 0x0046C1F0, JS
0x00431CC0 -- read back as `03E00008 24020001`). Rainbow Six 3's "you never
see your own tracers" problem does not exist on these discs.

The one trap: `DrawPlane` derives its quad from `cross(up, dir)`, which
collapses as the arc nears vertical. The game's own answer is to emit each
segment twice, once with `up = (0,0,1)` and once with `up = cross((0,0,1),
dir)`; that is exactly why `TracerPS2::Render` issues four `DrawPlane` calls
per dash. So budget 2 quads per segment.

WHERE IT MAY BE CALLED FROM
---------------------------

Inside `EffMgrPS2::Render`, at the slot where the game already issues its own
tracer draws -- after the world draw and before the 2D HUD pass, with the
depth buffer populated and the view matrix loaded. Every stock word below was
read back out of the retail ELF and matched:

    GR single view  0x0045E214 = 0C11AFFC  (jal 0x0046BFF0)   $s3 = EffMgrPS2*
                    0x0045E218 = 8E646280  (delay slot)
    GR split screen 0x0045E2FC = 0C11AFFC                     $s0 = view index
    JS single view  0x00423C98 = 0C10C6DC  (jal 0x00431B70)   $s1 = EffMgrPS2*
                    0x00423C9C = 8E246274  (delay slot)

Bracket the draws with `SetWriteZFlag(0)` / `SetAlphaTrans(1)` ... and restore
`SetWriteZFlag(1)` -- both static, one argument in `$a0`:
GR 0x004650A0 / 0x00465180, JS 0x0042A630 / 0x0042A710.

**Jungle Storm's SPLIT-SCREEN arm omits the tracer manager entirely**, so an
arc hooked this way is invisible in JS split screen without adding a call
there. The user plays co-op over LAN rather than split screen, so the single-
view arm is the one that matters and this is recorded only so it is not
rediscovered later.

FINDING THE LOCAL PLAYER, AND "IS HE WINDING UP?"
-------------------------------------------------

`grcamera.py` already walks it: sim-manager global GR 0x005EACF0 / JS
0x0062B8D0, per-view `SimCamera` at `+0x444`/`+0x448`, soldier at
`SimCamera+0x04`, and `SimHuman+0x138` is zero for a player's own soldier.

The cheapest "winding up a throw" test avoids every vtable call:
`SimHuman+0x458` is the `HumanMotion`, and `HumanMotion+0x38` is the freeze
flag that `HandleThrowItem` sets while the button is held (GR 0x0035D6F4, JS
0x003392CC) -- one pointer load and one byte load, and it can only be set by
the thrown-item path. Then the hold timer at `SimHuman+0x4F0` (GR) / `+0x510`
(JS) picks the table.

Throw position and facing come from the `SimHuman` vtable: position `+0x32C`
(GR) / `+0x330` (JS), direction `+0x2D4` (GR) / `+0x2D8` (JS) -- the same two
the throw message itself carries as payloads 2 and 3.

WHERE IT GOES
-------------

Ghost Recon ships an unstripped debug build, so its dead library stubs can be
enumerated exactly rather than guessed: of 308 `sce*` functions, 145 are the
target of no `jal` anywhere in the mapped span. Subtracting every address the
profile's STOCK map declares leaves **1594 free words in 18 runs**, the
largest being **0x0040C740, 191 words (`sceCdSearchFile`)**.

Subtracting STOCK rather than a swept write-set is the whole point, and it was
nearly got wrong here: a one-setting-at-a-time sweep does not reach
`grcallouts`' three caves (0x00417998, 0x00417BD8, 0x00417DE8), so they looked
free. They are in STOCK. `rsedeadpath`'s region is the same lesson from the
other direction -- a FIXED named-slot map, not a bump allocator.

Budget: ~120 instructions plus the 30 words of `t[]` below, so 0x0040C740's
191 words fit with margin. Jungle Storm has no symbols; its stubs are the same
library and the repo already names several twins (`sceVu0ViewScreenMatrix`
0x001975B8, `sceSifUnloadModule` 0x00182140, `sceDread` 0x00180160), but a JS
free map has NOT been built yet.

WHAT IT COSTS, AND WHAT WAS CHECKED
-----------------------------------

170 words of code in `sceCdSearchFile` and 40 words of tables in `sceIpuInit`,
plus the one hooked `jal`. The routine replaces `EffMgrPS2::Render`'s call to
`TracerManagerPS2::Render` and TAIL-JUMPS to it when finished, with `$a0`
restored, so the tracers it displaced still draw.

Checked by running the assembled words in an interpreter, with `DrawPlane`,
the two render-state setters and the two `SimHuman` getters mocked, against
the closed form above:

* the drawn points match to **0.00001 m**, and each segment's length to
  **0.00001 m**, over both arcs at launch elevations of -15, 0 and +35 deg;
* each of the 14 segments is drawn twice, with `up = (0,0,1)` and
  `up = (-dy, dx, 0)` -- `cross((0,0,1), dir)` worked out by hand, so no
  cross-product call is needed;
* the 0.5 s threshold picks the lob below 0.5 and the full throw at exactly
  0.5 and above, matching the game's own `c.olt.s` / `bc1f`;
* all six early-outs -- no sim manager, no SimCamera, no soldier, not a
  player, no HumanMotion, not winding up -- draw nothing, leave the render
  state alone, preserve `$s0-$s5`, restore `$a0` and `$sp`, and still
  tail-call;
* **not winding up costs 27 instructions**, which is the case that runs on
  almost every frame. A drawn arc costs 1074 plus 28 `DrawPlane` calls.

Two bugs were found this way and both were in the CHECKING, not the routine:
an interpreter that resolved branch targets one instruction too far, and one
that read `SQRT.S` from the `fs` field. On the R5900 `SQRT.S` takes its
operand from **ft** (`SQRT.S fd, ft`), which is what `grasm` emits and what
the hardware does.

NOT YET PLAYED. No pixel of this has been seen.
"""

from __future__ import annotations

import math

#: Linear drag for FRAG.PRJ: AirResistanceConstant / Weight, both read from
#: the projectile file (ProjectileFile +0x38 / +0x34). Gravity is the value
#: the IkeConstants constructor loads (GR 0x0015CDD8).
DRAG_K = 0.125 / 0.39
GRAVITY = 9.8

#: The two throw speeds, in metres per second. Compile-time constants with
#: exactly one writer each; see the module docstring.
SPEED_WUSS = 10.0
SPEED_MANLY = 25.0

#: The hold time that chooses between them, in seconds. A bare `lui 0x3F00`,
#: so retuning it is a single half-word (0x3E80 = 0.25 s, 0x3F80 = 1.0 s).
THROW_THRESHOLD = 0.5

#: Segments in the drawn arc. 14 segments = 15 points = 28 quads a frame,
#: against a scene that draws thousands.
SEGMENTS = 14

#: How far along the flight each arc is drawn, as a fraction of the speed
#: already shed to drag. Picked so the arc ends just below the throwing hand:
#: the lob reaches 7.67 m at -0.04 m, the full throw 37.06 m at -1.48 m.
C_MAX = {"wuss": 0.30, "manly": 0.58}

#: Addresses, per game. Every stock word here was read back out of the retail
#: executable; see the docstring for how each was established.
GAMES = {
    "gr": dict(
        DRAW_PLANE=0x004663B0, SET_WRITE_Z=0x004650A0, SET_ALPHA=0x00465180,
        HOOK=0x0045E214, HOOK_STOCK=0x0C11AFFC, HOOK_DELAY=0x0045E218,
        HOOK_DELAY_STOCK=0x8E646280, TRACER_RENDER=0x0046BFF0,
        HOOK_SPLIT=0x0045E2FC, EFFMGR_REG="s3", VIEW_REG="s0",
        SIM_MGR=0x005EACF0, CAM_AT=0x444, MOTION=0x458, HOLD=0x4F0,
        VT_POS=0x32C, VT_DIR=0x2D4, CAVE=0x0040C740, CAVE_WORDS=191,
        CAVE_NAME="sceCdSearchFile",
        DATA_CAVE=0x00411458, DATA_WORDS=142,
        DATA_CAVE_NAME="sceIpuInit",
    ),
    "js": dict(
        DRAW_PLANE=0x0042B910, SET_WRITE_Z=0x0042A630, SET_ALPHA=0x0042A710,
        HOOK=0x00423C98, HOOK_STOCK=0x0C10C6DC, HOOK_DELAY=0x00423C9C,
        HOOK_DELAY_STOCK=0x8E246274, TRACER_RENDER=0x00431B70,
        HOOK_SPLIT=None, EFFMGR_REG="s1", VIEW_REG="s0",
        SIM_MGR=0x0062B8D0, CAM_AT=0x444, MOTION=0x458, HOLD=0x510,
        VT_POS=0x330, VT_DIR=0x2D8, CAVE=None, CAVE_WORDS=0,
        CAVE_NAME=None,
        #: The routine is SPLIT here, because no single free run holds the
        #: 170 contiguous words Ghost Recon's one cave gives it. The cut is at
        #: `loop:`, the one place it is free: the prologue falls straight into
        #: the loop, so part 1 only has to end with a branch and nothing else
        #: crosses. Part 2 is assembled first, because part 1's six early-outs
        #: branch FORWARD to `bail`, which lives in part 2 -- 0x0017B710 to
        #: 0x0017FFF8 is 0x48E8 bytes, well inside a MIPS branch's +/-128 KB.
        CAVE1=0x0017B710, CAVE1_WORDS=101, CAVE1_NAME="sceTtyHandler",
        CAVE2=0x0017FFF8, CAVE2_WORDS=90, CAVE2_NAME="sceDclose",
        DATA_CAVE=0x001820A0, DATA_WORDS=40,
        DATA_CAVE_NAME="sceSifSearchModuleByName",
        #: Jungle Storm is stripped -- no symtab, and not even a `.text`
        #: section header -- so its dead stubs were found by matching Ghost
        #: Recon's. Every GR `sce*` function that no `jal` targets was masked
        #: (jal targets, `lui` halves and load/store displacements removed,
        #: opcodes and registers kept) and looked up in an index of every
        #: 20-word window of the Jungle Storm image; 100 stubs, kept only
        #: where the match was UNIQUE. The matcher is right: it independently
        #: reproduces six JS caves the repo already documents elsewhere --
        #: sceVu0ViewScreenMatrix 0x001975B8 (grsuppress), sceDread 0x00180160
        #: (grfrag), sceDevConsDrawS 0x001764C8 (grpierce) and
        #: sceChstat/sceRename/sceSync 0x00180458/0x00180698/0x001808A8
        #: (grcallouts).
        #:
        #: Deadness must then be re-tested IN JUNGLE STORM, not inherited:
        #: sceDevctl, sceIpuInit, sceCdDiskReady and sceIpuRestartDMA are all
        #: dead in Ghost Recon and all `jal` targets here.
        #:
        #: What is left after subtracting JS STOCK -- 283 words in four runs,
        #: and the stub space is very nearly gone:
        FREE=((0x0017B710, 101, "sceTtyHandler"),
              (0x0017FFF8, 90, "sceDclose"),
              (0x0017D978, 52, "sceSifRegisterRpc"),
              (0x001820A0, 40, "sceSifSearchModuleByName")),
    ),
}

#: The per-view SimCamera lives at `mIIkeSimulationMgr + 0x444 + 4*view`, so
#: 0x444 is VIEW 0 and 0x448 is VIEW 1 -- in BOTH games. `grcamera`'s note
#: "cameras at +0x444 / +0x448" names the two views, not the two games, and
#: reading it the other way is what made the first Jungle Storm build draw
#: nothing: it looked at view 1, which is null outside split screen, and took
#: the early-out every frame. Measured in a savestate taken mid-throw:
#: +0x444 held 0x03175E00 and +0x448 held 0.
#:
#: `HumanMotion+0x38`, the freeze flag HandleThrowItem sets while the throw
#: button is held. One byte, and only the thrown-item path can set it, which
#: is why it is preferred over walking the inventory through two vtables.
MOTION_FREEZE = 0x38


def samples(which: str, segments: int = SEGMENTS):
    """[(c, t)] for one arc, spaced uniformly in `c`.

    Uniform in `c` is uniform in horizontal distance, because that distance is
    exactly `(v0.xy / k) * c`. Spacing uniformly in TIME instead would crowd
    the segments into the far end of the arc, where drag has slowed the
    grenade most.
    """
    cm = C_MAX[which]
    out = []
    for i in range(segments + 1):
        c = cm * i / segments
        out.append((c, -math.log(1.0 - c) / DRAG_K))
    return out


def point(which: str, speed: float, elev_deg: float, i: int):
    """(forward, up) metres at sample `i`, for checking against the game."""
    c, t = samples(which)[i]
    a = math.radians(elev_deg)
    vx, vz = speed * math.cos(a), speed * math.sin(a)
    return (vx / DRAG_K * c,
            (vz / DRAG_K + GRAVITY / DRAG_K ** 2) * c - (GRAVITY / DRAG_K) * t)


def selftest():
    """Closed form against step-wise integration. [] = pass."""
    bad = []
    for which, speed in (("wuss", SPEED_WUSS), ("manly", SPEED_MANLY)):
        for deg in (-20.0, 0.0, 20.0, 35.0, 55.0):
            a = math.radians(deg)
            v = [speed * math.cos(a), 0.0, speed * math.sin(a)]
            p = [0.0, 0.0, 0.0]
            tprev, dt = 0.0, 0.0002
            for i, (_c, t) in enumerate(samples(which)):
                while tprev < t - 1e-12:
                    h = min(dt, t - tprev)
                    v[0] += -DRAG_K * v[0] * h
                    v[2] += (-GRAVITY - DRAG_K * v[2]) * h
                    p[0] += v[0] * h
                    p[2] += v[2] * h
                    tprev += h
                fwd, up = point(which, speed, deg, i)
                if abs(fwd - p[0]) > 0.02 or abs(up - p[2]) > 0.02:
                    bad.append("%s %g deg sample %d: (%.3f,%.3f) vs (%.3f,%.3f)"
                               % (which, deg, i, fwd, up, p[0], p[2]))
    return bad


_GR_CODE_STOCK = (
    0x27BDFF50, 0xFFB30040, 0xFFB20030, 0x0080982D, 0xFFB60070, 0x00A0902D,
    0xFFBF00A0, 0x3C160056, 0xFFBE0090, 0xFFB70080, 0xFFB50060, 0xFFB40050,
    0xFFB10020, 0x0C103144, 0xFFB00010, 0x8EC41DA8, 0x0C1046CC, 0x00000000,
    0x8EC31DA8, 0x1462009F, 0x0000102D, 0x3C02005F, 0x3C060056, 0x24030001,
    0x8C44B590, 0x3C05005F, 0xACC31D9C, 0x0C104678, 0x24A5B598, 0x0C103312,
    0x24040001, 0x14400060, 0x0000202D, 0x0C10510C, 0x3C110056, 0x8E221DC0,
    0x0441002C, 0x3C17005F, 0x3C140056, 0x3C15005F, 0x1000000A, 0x3C1E005F,
    0x2403FFFF, 0x00000000, 0x2442FFFF, 0x00000000, 0x00000000, 0x00000000,
    0x00000000, 0x1443FFFA, 0x00000000, 0x26F0B780, 0x3C058000, 0x0200202D,
    0x34A50597, 0x0C1052A8, 0x0000302D, 0x04430013, 0x8E020024, 0x8E821D90,
    0x18400005, 0x3C020010, 0x3C040058, 0x0C104F22, 0x248465E8, 0x3C020010,
    0x2403FFFF, 0x00000000, 0x2442FFFF, 0x00000000, 0x00000000, 0x00000000,
    0x00000000, 0x1443FFFA, 0x00000000, 0x1000FFE8, 0x26F0B780, 0x1040FFDC,
    0x3C020010, 0x10000004, 0xAE201DC0, 0x3C140056, 0x3C15005F, 0x3C1E005F,
    0x92430000, 0x26A4B600, 0x0000282D, 0x00031600, 0x1040000C, 0xA0830024,
    0x24860024, 0x24A50001, 0x28A20100, 0x10400007, 0x02451021, 0x00A62021,
    0x90430000, 0xA0830000, 0x00031E00, 0x5460FFF8, 0x24A50001, 0x24020100,
    0x14A20003, 0x26B0B600, 0x26A2B600, 0xA0400123, 0x8E821D90, 0x18400005,
    0xAE100124, 0x3C040058, 0x26050024, 0x0C104F22, 0x24846608, 0x0200202D,
    0x0C1050E0, 0x24050128, 0x26E4B780, 0xAFA00000, 0x0000282D, 0x0000302D,
    0x0200382D, 0x24080128, 0x27C9B740, 0x240A0004, 0x0C10531C, 0x0000582D,
    0x04410006, 0x3C022000, 0x8EC41DA8, 0x0C1046C0, 0x00000000, 0x1000002F,
    0x0000102D, 0x02021025, 0x68430007, 0x6C430000, 0x6844000F, 0x6C440008,
    0x68450017, 0x6C450010, 0x6846001F, 0x6C460018, 0xB2630007, 0xB6630000,
    0xB264000F, 0xB6640008, 0xB2650017, 0xB6650010, 0xB266001F, 0xB6660018,
    0x88430023, 0x98430020, 0xAA630023, 0xBA630020, 0x8E831D90, 0x18600010,
    0x3C040058, 0x26650008, 0x0C104F22, 0x24846620, 0x8E821D90, 0x1840000A,
    0x3C040058, 0x8E650004, 0x0C104F22, 0x24846630, 0x8E821D90, 0x18400004,
    0x3C040058, 0x8E650000,
)

_GR_DATA_STOCK = (
    0x27BDFFF0, 0xFFBF0000, 0x0C1044FC, 0x24040001, 0x3C021000, 0x3C034000,
    0x34422010, 0x3C041000, 0xAC430000, 0x34842010, 0x8C820000, 0x00000000,
    0x00000000, 0x00000000, 0x00000000, 0x0440FFFA, 0x00000000, 0x3C021000,
    0x3C031000, 0x34422000, 0x34632010, 0xAC400000, 0x8C620000, 0x00000000,
    0x00000000, 0x00000000, 0x00000000, 0x0440FFFA, 0x00000000, 0x3C050057,
    0x3C041000, 0x24A5D8F0, 0x34847010, 0x78A20000, 0x3C061000, 0x3C075000,
    0x34C62000, 0x7C820000, 0x3C081000, 0x35082010,
)

_GR_CODE = (
    0x27BDFF20, 0xAFBF00AC, 0xAFA400A8, 0xAFB000B0, 0xAFB100B4, 0xAFB200B8,
    0xAFB400BC, 0x3C09005F, 0x8D29ACF0, 0x11200098, 0x00000000, 0x8D2A0444,
    0x11400095, 0x00000000, 0x8D520004, 0x12400092, 0x00000000, 0x8E480138,
    0x1500008F, 0x00000000, 0x8E480458, 0x1100008C, 0x00000000, 0x91090038,
    0x11200089, 0x00000000, 0x3C110041, 0x26311458, 0xC64204F0, 0xC6230000,
    0x46031034, 0x45010004, 0x26340064, 0xC6240008, 0x10000003, 0x00000000,
    0x26340028, 0xC6240004, 0xE7A400A0, 0x8E590000, 0x8F3902D4, 0x0240282D,
    0x0320F809, 0x27A40090, 0x8E590000, 0x8F39032C, 0x0240202D, 0x0320F809,
    0x00000000, 0x7FA20080, 0xC625000C, 0xC7A400A0, 0x46052102, 0xC7A60090,
    0xC7A70094, 0xC7A80098, 0x46043182, 0x460439C2, 0x46044202, 0xC6290014,
    0x46094200, 0xE7A60070, 0xE7A70074, 0xE7A80078, 0xC6200018, 0xC621001C,
    0xE7A00030, 0xE7A00034, 0xE7A10038, 0x240800FF, 0xAFA80050, 0x240800DC,
    0xAFA80054, 0x24080050, 0xAFA80058, 0x24080080, 0xAFA8005C, 0x7BA80050,
    0x7FA80060, 0x0C119428, 0x0000202D, 0x0C119460, 0x24040001, 0x7BA80080,
    0x7FA80000, 0x0000802D, 0x26090001, 0x44895000, 0x468052A0, 0xC68B0000,
    0x460B5282, 0x00105080, 0x028A5021, 0xC54C0004, 0xC7AD0070, 0x460A6B42,
    0xC7AE0080, 0x460E6B40, 0xE7AD0010, 0xC7AD0074, 0x460A6B42, 0xC7AE0084,
    0x460E6B40, 0xE7AD0014, 0xC7AD0078, 0x460A6B42, 0xC62E0010, 0x460C7382,
    0x460E6B41, 0xC7AE0088, 0x460E6B40, 0xE7AD0018, 0xC7A00010, 0xC7A10000,
    0x46010001, 0xE7A00020, 0xC7A20014, 0xC7A30004, 0x46031081, 0xE7A20024,
    0xC7A40018, 0xC7A50008, 0x46052101, 0xE7A40028, 0x46000182, 0x460211C2,
    0x46073180, 0x460421C2, 0x46073180, 0x46060184, 0xE7A600A4, 0x460011C7,
    0xE7A70040, 0xE7A00044, 0xC6280018, 0xE7A80048, 0x27A40000, 0x27A50020,
    0x27A60030, 0x27A70050, 0x27A80060, 0xC7AC00A4, 0xC62D0024, 0x0C1198EC,
    0x0000482D, 0x27A40000, 0x27A50020, 0x27A60040, 0x27A70050, 0x27A80060,
    0xC7AC00A4, 0xC62D0024, 0x0C1198EC, 0x0000482D, 0x7BA80010, 0x7FA80000,
    0x26100001, 0x2A09000E, 0x1520FFB7, 0x00000000, 0x0C119428, 0x24040001,
    0x8FBF00AC, 0x8FA400A8, 0x8FB000B0, 0x8FB100B4, 0x8FB200B8, 0x8FB400BC,
    0x0811AFFC, 0x27BD00E0,
)

_GR_DATA = (
    0x3F000000, 0x41200000, 0x41C80000, 0x4047AE14, 0x41F49BA6, 0x42BECB53,
    0x00000000, 0x3F800000, 0x00000000, 0x3D4CCCCD, 0x3CAF8AF9, 0x3D8A6969,
    0x3E0BF1B2, 0x3E5448BC, 0x3E8F2669, 0x3EB50929, 0x3EDBD786, 0x3F01CE9F,
    0x3F16337A, 0x3F2B2123, 0x3F409EF7, 0x3F56B4F0, 0x3F6D6BB5, 0x3F826659,
    0x3F8E7114, 0x3D29B101, 0x3E072DE0, 0x3E8A2A74, 0x3ED40140, 0x3F10B62A,
    0x3F396486, 0x3F6441EC, 0x3F88C6E5, 0x3FA0C982, 0x3FBA5571, 0x3FD5A07E,
    0x3FF2EC4F, 0x40094515, 0x401A7028, 0x402D38F7,
)


def words(game="gr"):
    """[(va, new, stock, note)] for build_edits."""
    g = GAMES[game]
    hook = (g["HOOK"], 0x0C000000 | ((g.get("CAVE") or g["CAVE1"]) >> 2 & 0x03FFFFFF),
            g["HOOK_STOCK"],
            "grenade arc: EffMgrPS2::Render calls the arc, which tail-calls "
            "the tracer renderer")
    out = [hook]
    if game == "gr":
        blocks = ((g["CAVE"], _GR_CODE, _GR_CODE_STOCK, "the routine"),
                  (g["DATA_CAVE"], _GR_DATA, _GR_DATA_STOCK, "its tables"))
    else:
        blocks = ((g["CAVE1"], _JS_PART1, _JS_PART1_STOCK, "the routine, part 1"),
                  (g["CAVE2"], _JS_PART2, _JS_PART2_STOCK, "the routine, part 2"),
                  (g["DATA_CAVE"], _JS_DATA, _JS_DATA_STOCK, "its tables"))
    for at, new, stock, what in blocks:
        for i, (n, st) in enumerate(zip(new, stock)):
            out.append((at + 4*i, n, st, "grenade arc: " + what))
    return out


def stock_words(game="gr"):
    """{va: shipped word}, so a revert and the profile's STOCK agree."""
    return {va: st for va, _new, st, _n in words(game)}


def selftest_image(read_word, game="gr"):
    """Every stock word against a pristine image. [] = pass."""
    return ["%08X" % va for va, _n, st, _note in words(game)
            if read_word(va) != st]


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "grenade_arc", "Show the grenade throw arc", BOOL, False,
        group, confidence="experimental", touches="words",
        help="While you are winding up a grenade or smoke, draws the path it "
             "will fly, from your hand to where it comes down.\n\n"
             "The curve is the game's own flight -- the same drag and gravity "
             "the grenade really uses -- so it ends where the grenade lands, "
             "not where a throw with no air would.\n\n"
             "Holding the throw button is a two-position switch in this game, "
             "not a charge: under half a second you get a short lob (10 m/s, "
             "about 7 m), and at half a second or more the full throw (25 m/s, "
             "about 36 m). The arc swaps between those two shapes as you cross "
             "half a second, so it also tells you which of the two throws you "
             "are about to make.",
        caution="Never played. The routine was checked against the flight "
                "model in an interpreter, to a hundredth of a millimetre, but "
                "no frame of it has been seen.\n\n"
                "It does not stop at walls: the curve is drawn through "
                "geometry rather than clipped to the first thing it would "
                "hit.\n\n"
                "In Jungle Storm the routine is split across two dead "
                "library stubs, because no single free run there is long "
                "enough for it.")


_JS_PART1 = (
    0x27BDFF20, 0xAFBF00AC, 0xAFA400A8, 0xAFB000B0, 0xAFB100B4, 0xAFB200B8,
    0xAFB400BC, 0x3C090063, 0x8D29B8D0, 0x1120127C, 0x00000000, 0x8D2A0444,
    0x11401279, 0x00000000, 0x8D520004, 0x12401276, 0x00000000, 0x8E480138,
    0x15001273, 0x00000000, 0x8E480458, 0x11001270, 0x00000000, 0x91090038,
    0x1120126D, 0x00000000, 0x3C110018, 0x263120A0, 0xC6420510, 0xC6230000,
    0x46031034, 0x45010004, 0x26340064, 0xC6240008, 0x10000003, 0x00000000,
    0x26340028, 0xC6240004, 0xE7A400A0, 0x8E590000, 0x8F3902D8, 0x0240282D,
    0x0320F809, 0x27A40090, 0x8E590000, 0x8F390330, 0x0240202D, 0x0320F809,
    0x00000000, 0x7FA20080, 0xC625000C, 0xC7A400A0, 0x46052102, 0xC7A60090,
    0xC7A70094, 0xC7A80098, 0x46043182, 0x460439C2, 0x46044202, 0xC6290014,
    0x46094200, 0xE7A60070, 0xE7A70074, 0xE7A80078, 0xC6200018, 0xC621001C,
    0xE7A00030, 0xE7A00034, 0xE7A10038, 0x240800FF, 0xAFA80050, 0x240800DC,
    0xAFA80054, 0x24080050, 0xAFA80058, 0x24080080, 0xAFA8005C, 0x7BA80050,
    0x7FA80060, 0x0C10A98C, 0x0000202D, 0x0C10A9C4, 0x24040001, 0x7BA80080,
    0x7FA80000, 0x0000802D, 0x100011E3, 0x00000000,
)

_JS_PART1_STOCK = (
    0x27BDFFC0, 0x24020003, 0xFFB10010, 0xFFB00000, 0x00C0882D, 0xFFBF0030,
    0x00A0802D, 0x1082003B, 0xFFB20020, 0x28820004, 0x14400005, 0x24020004,
    0x1082004A, 0xDFBF0030, 0x10000052, 0xDFB20020, 0x1880004F, 0xDFBF0030,
    0x52000019, 0x8E320014, 0x8E220008, 0x00501021, 0x2C420141, 0x14400003,
    0x3C040058, 0x0C05F134, 0x24841B28, 0x8E220008, 0x3206FFFF, 0x8E250014,
    0x8E240000, 0x0C05ED54, 0x00A22821, 0x0040802D, 0x06010004, 0x00000000,
    0x3C040058, 0x0C05F134, 0x24841B50, 0x8E220008, 0x00501021, 0xAE220008,
    0x10000035, 0xDFBF0030, 0x2410000C, 0x96420000, 0x0202102A, 0x10400010,
    0x0240182D, 0x10000003, 0x8E240018, 0x00000000, 0x8E240018, 0x00701021,
    0x90430000, 0x26100001, 0x8C82000C, 0xA0430000, 0x0C05EDA4, 0x8E240018,
    0x96420000, 0x0202102A, 0x5440FFF5, 0x8E230014, 0xAE200008, 0x1000001E,
    0xDFBF0030, 0x8E260004, 0x8E240000, 0x8E250010, 0x0C05ED62, 0x30C6FFFF,
    0x0040282D, 0x04A30006, 0x8E220010, 0x3C040058, 0x0C05F134, 0x24841B68,
    0x1000000F, 0x00000000, 0x8E230004, 0x00451021, 0x00651823, 0xAE220010,
    0xAE230004, 0x1000000A, 0xDFBF0030, 0x8E220004,
)

_JS_PART2 = (
    0x26090001, 0x44895000, 0x468052A0, 0xC68B0000, 0x460B5282, 0x00105080,
    0x028A5021, 0xC54C0004, 0xC7AD0070, 0x460A6B42, 0xC7AE0080, 0x460E6B40,
    0xE7AD0010, 0xC7AD0074, 0x460A6B42, 0xC7AE0084, 0x460E6B40, 0xE7AD0014,
    0xC7AD0078, 0x460A6B42, 0xC62E0010, 0x460C7382, 0x460E6B41, 0xC7AE0088,
    0x460E6B40, 0xE7AD0018, 0xC7A00010, 0xC7A10000, 0x46010001, 0xE7A00020,
    0xC7A20014, 0xC7A30004, 0x46031081, 0xE7A20024, 0xC7A40018, 0xC7A50008,
    0x46052101, 0xE7A40028, 0x46000182, 0x460211C2, 0x46073180, 0x460421C2,
    0x46073180, 0x46060184, 0xE7A600A4, 0x460011C7, 0xE7A70040, 0xE7A00044,
    0xC6280018, 0xE7A80048, 0x27A40000, 0x27A50020, 0x27A60030, 0x27A70050,
    0x27A80060, 0xC7AC00A4, 0xC62D0024, 0x0C10AE44, 0x0000482D, 0x27A40000,
    0x27A50020, 0x27A60040, 0x27A70050, 0x27A80060, 0xC7AC00A4, 0xC62D0024,
    0x0C10AE44, 0x0000482D, 0x7BA80010, 0x7FA80000, 0x26100001, 0x2A09000E,
    0x1520FFB7, 0x00000000, 0x0C10A98C, 0x24040001, 0x8FBF00AC, 0x8FA400A8,
    0x8FB000B0, 0x8FB100B4, 0x8FB200B8, 0x8FB400BC, 0x0810C6DC, 0x27BD00E0,
)

_JS_PART2_STOCK = (
    0x27BDFF60, 0xFFB40080, 0xFFB20060, 0x3C140061, 0xFFB00040, 0x26927000,
    0xFFBF0090, 0xFFB30070, 0x0C05F7AE, 0xFFB10050, 0x0040802D, 0x0C05F8CC,
    0x2404000A, 0x3C030057, 0x8C624FEC, 0x14400005, 0x00000000, 0x0C05F8D8,
    0x00000000, 0x1000003E, 0x2402FFFF, 0x12000004, 0x00000000, 0x8E020004,
    0x54400005, 0x8E030000, 0x0C05F8D8, 0x00000000, 0x10000035, 0x2402FFF7,
    0x24020001, 0xAFA20014, 0x27A40010, 0xAE43000C, 0xAFA00018, 0x0C05E8B8,
    0xAFA00024, 0x0040882D, 0x27A30030, 0x3C020061, 0xAE917000, 0x24537C40,
    0x3C040062, 0x24020004, 0xAE430004, 0xAE420008, 0x24848700, 0x0240382D,
    0x2405000A, 0xAFA00000, 0x0000302D, 0x24080014, 0x0260482D, 0x240A0004,
    0x0C05F5AA, 0x0000582D, 0x04430007, 0xAE000004, 0x0C05E8BC, 0x0220202D,
    0x0C05F8D8, 0x00000000, 0x10000013, 0x2402FFF5, 0x3C022000, 0x02621025,
    0x0C05F8D8, 0x8C500000, 0x16000005, 0x00000000, 0x0C05E8BC, 0x0220202D,
    0x10000009, 0x2402FFF5, 0x0C05E8C8, 0x0220202D, 0x0C05E8BC, 0x0220202D,
    0x8FA20030, 0x2403FFFF, 0x0062182A, 0x0003100B, 0xDFBF0090, 0xDFB40080,
)

_JS_DATA = (
    0x3F000000, 0x41200000, 0x41C80000, 0x4047AE14, 0x41F49BA6, 0x42BECB53,
    0x00000000, 0x3F800000, 0x00000000, 0x3D4CCCCD, 0x3CAF8AF9, 0x3D8A6969,
    0x3E0BF1B2, 0x3E5448BC, 0x3E8F2669, 0x3EB50929, 0x3EDBD786, 0x3F01CE9F,
    0x3F16337A, 0x3F2B2123, 0x3F409EF7, 0x3F56B4F0, 0x3F6D6BB5, 0x3F826659,
    0x3F8E7114, 0x3D29B101, 0x3E072DE0, 0x3E8A2A74, 0x3ED40140, 0x3F10B62A,
    0x3F396486, 0x3F6441EC, 0x3F88C6E5, 0x3FA0C982, 0x3FBA5571, 0x3FD5A07E,
    0x3FF2EC4F, 0x40094515, 0x401A7028, 0x402D38F7,
)

_JS_DATA_STOCK = (
    0x27BDFFD0, 0xFFB00010, 0xFFBF0020, 0x0C06068E, 0x0080802D, 0x0440001E,
    0x3C02FFFF, 0x0C0606CE, 0x00000000, 0x50400004, 0x3C020062, 0x3C02FFFE,
    0x10000017, 0x3442FFFC, 0x0200282D, 0x245089C8, 0x240600FC, 0x0C05B8F2,
    0x0200202D, 0x2603FFF8, 0x3C040062, 0x0060382D, 0xA0600103, 0x24848BC0,
    0x24050009, 0xAFA00000, 0x0000302D, 0x24080200, 0x00E0482D, 0x240A0004,
    0x0C05F5AA, 0x0000582D, 0x04430003, 0x8E02FFF8, 0x3C02FFFE, 0x3442FFFF,
    0xDFBF0020, 0xDFB00010, 0x03E00008, 0x27BD0030,
)

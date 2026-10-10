r"""Enemies animate at the frame rate, instead of stepping.

Jungle Storm throttles every character's POSE update by how far it is from the
camera, and the best any non-player character ever gets is every second frame.
The port does not cause this and does not touch a word of it -- it makes it
conspicuous, by putting Ghost Recon's long-range missions into slots that used
to hold close-quarters jungle maps.

THE GATE
--------

`SimHuman` keeps a real-time accumulator at +0x7BC, a period at +0x7C0 and the
animation delta at +0x7C4. `SimHuman::Update` (VA 0x003A9974..0x003A9990)::

    003A9974  sw    zero, 0x7C4(s0)   ; dt = 0 -- the DEFAULT is do not animate
    003A9978  lwc1  f2, 0x7BC(s0)     ; accumulated real time
    003A997C  lwc1  f0, 0x7C0(s0)     ; the period
    003A9980  c.le.s f2, f0
    003A9984  bc1t  0x003A9994        ; accum <= period -> skip the update
    003A998C  swc1  f2, 0x7C4(s0)     ; else dt = accum
    003A9990  swc1  f1, 0x7BC(s0)     ; accum = 0

A zero dt freezes the whole skeleton: `HumanMotion::Update(float)` tests the
delta with an IsZero helper and jumps straight to its epilogue, skipping both
`UpdateMotion` and `UpdateBones`.

THE PERIOD
----------

`SimHuman::UpdateVisibility` (JS 0x003BEFD0) seeds 0.72 s and takes a Min over
each view on `depth = |dot(charPos - camPos, camFwd)|`, with `max` 80 and
`mid/4` 10 at the default FOV (1 unit is about 1 metre on this engine --
`IKE.SDF` declares a proximity event in metres and the mesh-LOD threshold at 10
coincides with mid/4):

    visible              0.0225 * clamp(depth, 10, 80) / 10   <- 0x00597340
    in range, off screen 0.045 * (3.0 + 1.1 * ratio)          <- 0x00597588
    beyond max           0.045 * (10 + rand() & 7)
    the player's avatar  0                                     <- exempt

which at 60 FPS comes out as:

    the player           60 Hz        40 m        10 Hz
    enemy at <= 10 m     30 Hz        80 m         5.5 Hz
    20 m                 20 Hz        off screen   5 Hz

THE EDIT
--------

One word. `0x00597340` holds the visible branch's slope and has **exactly one
reader** (0x003BF6BC), so steepening it leaves the off-screen and beyond-range
bands exactly as cheap as they are now -- only characters you can actually see
cost more. The constant is byte-identical on a stock disc and on a ported one.

`everything` instead zeroes the 0.72 seed at 0x00597348 (also a single reader,
0x003BF38C). Every later write is a Min against the current value, so a zero
seed pins the period at 0 and every character animates like the player's own.
That includes the ones behind you and the ones past the far plane, 33 to 64 per
mission, each running UpdateMotion + UpdateBones + UpdateMovement +
UpdateWorldBoneLocations every frame rather than every 2 to 46 -- it may not
hold 60 FPS, which is why it is not the default.

NOT CONFIRMED IN PLAY
---------------------

The formula predicts a 2-frame hold at point-blank and 10 Hz at 40 m, which is
the reported symptom, and it is the only rate control on the pose path -- no
character-count cap, no per-frame update budget, no fixed animation timestep
exists. But this was read statically and never watched in a running game. The
measurement that settles it: stand a few metres from a walking enemy and
frame-step. If each pose holds for exactly two frames while your own hands move
every frame, this is the throttle.

WHAT IS NOT THE CAUSE
---------------------

`.CHA` is not animation data. Every `.CHA` on all three discs is exactly 2860
bytes = 4 + 21 * 136, one record per bone of the engine's fixed 21-bone biped
(name table at ~0x0059E1C8), holding a position + quaternion pair and two live
RAM pointers -- the ELF's allocation tag for it is `Limb Anchor Data`. Neither
boot ELF contains the string `.cha` or `.chr` at all; the character loader opens
`<name>.chz` and `<name>.bmz` and nothing else. The motion set is `.BMF` and no
PS2 disc ships one, so the port cannot have given a character "fewer frames".

The port's LOD collapse is real -- 231 of the 237 actor slots the ported
missions use have all three LOD tags pointing at one model, against 22 in stock
Jungle Storm -- and it is irrelevant here. The ATR LOD chain feeds
`MotionManager +0x10`, written once by `SimHuman::SetLOD`, and neither
`UpdateMotion` nor `UpdateBones` ever reads it; the real per-frame mesh LOD
lives inside the `.chz` and `UpdateBoneMatrix` rebuilds every bone
unconditionally. Pointing the LOD tags at distinct donor names would also be
futile: 86% of Ghost Recon's LOD names have no `.chz` on the PS2 disc.
"""

from __future__ import annotations

import struct

#: VA of the visible branch's slope, and of the 0.72 seed. One reader each.
SLOPE_VA = 0x00597340
SEED_VA = 0x00597348
SLOPE_STOCK = 0x3CB851EC          # 0.0225
SEED_STOCK = 0x3F3851EC           # 0.72


def _f(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


#: choice -> (va, word, what it buys). The slope scales linearly with depth
#: from 10 m, so a slope of 1/240 puts the 1/60 s frame boundary at 40 m and
#: 1/480 puts it past the 80 m far limit.
CHOICES = {
    "stock": None,
    "visible": (SLOPE_VA, 0x00000000,
                "full rate for anything on screen; off screen and beyond the "
                "far limit stay as cheap as they are now"),
    "near": (SLOPE_VA, _f(1.0 / 240.0),
             "full rate out to about 40 m, half rate from there to 80 m -- "
             "the cheaper option if `visible` costs frames"),
    "everything": (SEED_VA, 0x00000000,
                   "full rate for every character on the map, on screen or "
                   "not -- may not hold 60 FPS"),
}
DEFAULT = "visible"

#: NOT a knob. 0x00597588 (0.045) is the off-screen and beyond-range base and
#: has FOUR readers -- the constructor at 0x003A4B50 plus 0x003BF668,
#: 0x003BF734 and 0x003BF780 -- so moving it drags both far bands together and
#: changes the cost of characters nobody can see.
FAR_BASE_VA = 0x00597588


def edits(choice: str = DEFAULT):
    """(va, value, stock, note) for each word this option writes."""
    pick = CHOICES.get(choice)
    if pick is None:
        return []
    va, word, what = pick
    stock = SEED_STOCK if va == SEED_VA else SLOPE_STOCK
    return [(va, word, stock, "enemy animation: " + what)]


def js_edits(v: dict):
    choice = v.get("js_anim_rate")
    if not choice or choice == "stock":
        return []
    return edits(str(choice))


def selftest(js_elf: bytes):
    """Both stock constants against the executable. [] = pass."""
    bad = []
    for va, stock in ((SLOPE_VA, SLOPE_STOCK), (SEED_VA, SEED_STOCK)):
        off = va - 0x100000 + 0x100
        if int.from_bytes(js_elf[off:off + 4], "little") != stock:
            bad.append("js %08X" % va)
    for name in CHOICES:
        for va, word, st, _n in edits(name):
            if va not in (SLOPE_VA, SEED_VA) or st not in (SLOPE_STOCK, SEED_STOCK):
                bad.append("%s writes an unexpected site" % name)
    return bad

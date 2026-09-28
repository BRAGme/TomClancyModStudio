"""The shadow pass that split screen throws away.

Nine campaign missions and all three training maps place `R6LightProjector`
actors that cast a projected shadow. In split screen none of them draws.

The data is all still there
---------------------------

This was checked before any code was read, because if the split-screen build
simply shipped without the shadow actors there would be nothing to restore.
Every level ships twice -- `<MAP>OFF.LIN` for offline play and `<MAP>_SS.LIN`
for split screen -- so the two can be compared directly.

They are the same file. `GARAGE_AOFF` and `GARAGE_A_SS` are byte-identical for
the first 6.8 MB, their name tables match exactly (2,789 names each), and the
only difference in the whole package is that the split-screen build drops
**Weber and Loiselle** -- their meshes, heads and ten camo skins apiece. That
is the entire 2,526-byte delta.

Across all 30 offline/split-screen pairs on the disc, **zero** differ in
projector count, in `ShadowBufferMatrix`, or in name-table size.

Nor are the actors skipped at spawn time. In a split-screen savestate on Garage
the three projectors are present and attached, with the same `ProjectorSize`
values (90, 400, 1050) as the single-player one; the only deltas are
`ProjectorAttachedActors` 1 -> 0 and 5 -> 4, which is precisely the teammate
that split screen does not spawn.

So the whole system is built and wired up in split screen, and something
downstream discards it.

Finding the pass
----------------

The renderer carries three profiler timers -- `RenderShadowBuffer`,
`RenderShadowBufferActors` and `RenderShadowBufferBSP`. They are registered into
a stat block whose base is a parameter, so the base was recovered from the one
caller (`0x0060d90c` passes `0x006ea5c0`), which puts `RenderShadowBuffer` at
`0x006ea6a0`. The code that starts and stops that timer is then the pass::

    RenderShadowBuffer         0x00352364..0x003523b0   inside the scene
                                                        render at 0x0034f250
    RenderShadowBufferActors   0x0030a1c8..0x0030a458   0x00309e00, called
    RenderShadowBufferBSP      0x00309f94..0x0030a1bc   from 0x004470e0

`0x00446e60` is the function those inner passes hang off, and it is
unmistakably the renderer: it fetches the global render object `G` through
`lw $a0, -0x716c($gp)` at `0x004470a4`, the same global the scope draw reads.

The gate
--------

It is the first three instructions of that function::

    00446ea4  lbu   $v0, 0x94($a0)     ; a flags byte on the render object
    00446ea8  andi  $v0, $v0, 1        ; bit 0
    00446eac  beqz  $v0, 0x004473a0    ; clear -> return, having drawn nothing

Forcing the test true makes the pass run its body instead of returning at the
top. One word, inside the overlay image, so it is an ordinary disc edit that
reverts exactly -- no code cave, and none of the level-load hazards that come
with one.

What is NOT established
-----------------------

**Which code clears that bit in split screen.** No instruction writes `+0x94`
at that displacement -- all six `sb ... 0x94(...)` sites in the image are stack
writes -- so it is set through some other base, most likely a struct copy.

The field-difference sweep that originally found the scope gate was re-run over
four split-screen and five single-player savestates. It correctly rediscovered
`G+0x409fc`, and turned up only two other flag-shaped fields, `G+0x8634` and
`G+0x8b64`, both 1 in split and 0 in single; neither has a code reference, so
neither is claimed here.

One measurement actively points the other way and is recorded rather than
buried: the object at `gp-0x6250` has the same `+0x94`/`+0x98` shape this
function uses, but its bit 0 reads **1 in split screen and 0 in single** -- the
opposite of what a shadow gate should do. Either that is not the object passed
in `$a0`, or bit 0 means something else. That is why this ships as an
experiment: it is cheap, it reverts, and it answers the question that static
reading has not.
"""

from __future__ import annotations

#: the `andi` that decides whether the shadow pass runs at all
SHADOW_GATE = 0x00446EA8

#: what the game ships there: `andi $v0, $v0, 1`
SHADOW_GATE_STOCK = 0x30420001

#: and the same test forced true: `ori $v0, $v0, 1`
SHADOW_GATE_FORCED = 0x34420001

#: THE REAL GATE (2026-09-24). The level render (0x0034F250) sets a stack flag
#: from `GEngine.mSplitScreenMode` (+0x4E4) and, at 0x00351E7C, skips the whole
#: "DynamicLightProjector" block when it is set -- the shadow-buffer pass AND
#: the additive pass that paints projected light onto walls (the Garage
#: screen's image, the blinds on the yellow wall). Measured in savestates: the
#: block's timer runs in split screen but RenderShadowBuffer / AdditivePass
#: count 0, against thousands in single player. The andi above was never the
#: gate: 0x00447440 sets that bit right before the only call, so in split
#: screen the function is simply never called. Twin of the weather skip at
#: 0x003531D0, which `fx_weather` already clears; this word leaves the flag
#: alone, so weather stays on its own card.
PROJECTOR_BRANCH = 0x00351E7C
PROJECTOR_BRANCH_STOCK = 0x14400424     # bnez $v0, 0x00352f10 (delay slot: nop)
PROJECTOR_BRANCH_OPEN = 0x00000000      # nop

#: the read the gate acts on, and the branch it feeds -- recorded so a later
#: investigation does not have to find them again
SHADOW_FLAG_READ = 0x00446EA4      # lbu $v0, 0x94($a0)
SHADOW_GATE_BRANCH = 0x00446EAC    # beqz $v0, 0x004473a0
SHADOW_PASS = 0x00446E60           # the function itself

#: the timed scopes, by stat name
SHADOW_TIMERS = {
    "RenderShadowBuffer": (0x00352364, 0x003523B0),
    "RenderShadowBufferActors": (0x0030A1C8, 0x0030A458),
    "RenderShadowBufferBSP": (0x00309F94, 0x0030A1BC),
}

#: Which maps place projectors, measured from every level package on the disc:
#: instance names matching `R6LightProjector<n>` in the package's own name
#: table. `ShadowBufferMatrix` -- a property only serialised when the class is
#: instantiated -- agrees with this count on all 80 packages with no
#: exceptions, which is why the list is trusted.
SHADOW_MAPS = {
    "GARAGE_A": 3, "ALCATRAZ_A": 2, "PARADE_A": 2, "PARADE_B": 2,
    "OLDCITY_A": 1, "OLDCITY_B": 1, "SHIPYARD_A": 1, "SHIPYARD_B": 1,
    "OFFICE_COMPLEX_A": 1, "AIRPORT_B": 1, "ALPINES_B": 1,
    "MOUNTAIN_HIGHWAY_B": 1, "TRAINING_BASICS": 3, "TRAINING_TEAM": 4,
    "TRAINING_SHOOTING": 1,
}

#: Parade is the only map that also carries `ForcedShadowReceivers`, an
#: explicit list of actors that must take the shadow, so it is the richest
#: setup on the disc and the best place to test.
BEST_TEST_MAP = "PARADE_A"


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_shadows",
        "Draw projectors in split screen (shadows, projected light)",
        BOOL, False, group, confidence="experimental", touches="words",
        help="Nine missions and all three training maps place light "
             "projectors -- the Garage's projection screen, window-blind "
             "shadows, shadow-casting lights -- and none of them draws in "
             "split screen. The level render skips the whole projector block "
             "whenever split screen is on (one branch, at 0x00351E7C). This "
             "removes that branch, so each half draws its projectors as "
             "single player does. Best tested at the Garage's projection "
             "screen, or on Parade or Alcatraz.",
        caution="Not yet played. Watch the frame rate: every projector in "
                "view is drawn once per half, and each half also pays a small "
                "fixed cost to enter and leave the projector block, even with "
                "no projector in sight. If a map slows down, turn this off. "
                "An earlier version of this card forced a different test "
                "(0x00446EA8) and did nothing in play on 2026-09-15; that test "
                "was never the gate, because in split screen the function it "
                "guards is simply never called.")

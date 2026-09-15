"""The scope overlay that split screen throws away.

Aim down sights in single player and the sight picture is surrounded by the
scope tube and its vignette. In split screen only the bare reticule is drawn.

Where it goes
-------------

The overlay is a post-process, and everything upstream of the draw is healthy
in split screen -- which is what rules out the obvious explanations. Measured
in a split-screen ADS savestate, all of these are byte-identical to the
single-player one:

* `LevelInfo+0x54c` / `+0x550` carry `ScopeBlurTex_Aug` and `ScopeBlurTexAdd`
* `m_bScopeVisionActive` is set
* both `PSX2RenderDevice0` and `PSX2RenderDevice1` carry the two textures
* the global render object's flags byte reads `0x22` -- post-process enabled,
  scope active -- in both

So the data reaches the renderer intact. One instruction stops it.

`G` is the global render object, the word at `gp-0x716c` (`0x00654584`). The
scope draw at `0x0019adb0` opens with::

    0019ae30  lui   $a0, 0x4
    0019ae34  ori   $v1, $a0, 0x09fc
    0019ae38  addu  $v1, $s0, $v1        ; $s0 = G, so $v1 = G + 0x409fc
    0019ae3c  lw    $a1, 0x0($v1)        ; the split-screen mode
    0019ae40  bnez  $a1, 0x0019b15c      ; <-- leaves the full-screen path
    0019ae44  lui   $at, 0x4             ; delay slot, runs either way
    0019ae48  lb    $v1, 0x0($s0)        ; the scope-active test is PAST it

`G+0x409fc` correlates perfectly with the viewport count:

=========================  ==========  ==============  ==================
state                      G+0x409fc   framebuffer     viewport rect
=========================  ==========  ==============  ==================
single player (2 states)   0           640x448         0, 0, 640, 448
split screen (4 states)    2           640x448         0, 224, 640, 224
=========================  ==========  ==============  ==================

The branch target is dead. `0x0019b15c` indexes two arrays at `G+0x417e8` and
`G+0x417ec`, and a whole-image scan for every instruction carrying those
displacements finds exactly one writer each -- all in the init block at
`0x001afcb0`, all storing zero. So in split screen the function returns having
drawn nothing.

Why this is an experiment and not yet a finished fix
----------------------------------------------------

The draw sizes its quads from `G+0x7c4` / `G+0x7c8`, and those are **640x448
in split screen too** -- the whole framebuffer, not the viewport. The
per-viewport rectangle lives at `G+0x40a00`, and the draw never reads it.

So clearing the branch should make the scope appear, drawn across the full
screen rather than fitted to your half, and once per viewport because
`m_bScopeVisionActive` lives on the shared `LevelInfo`. That is very likely
*why* the branch is there.

A finished fix needs a cave that feeds the draw `G+0x40a04` and `G+0x40a0c`
instead of the framebuffer height, at the eight sites that read `0x7c4`/`0x7c8`
(`0x0019af34`, `0x0019af48`, `0x0019af68`, `0x0019afd0`, `0x0019b0a8`,
`0x0019b0bc`, `0x0019b0dc`, `0x0019b144`). This option exists to settle whether
the diagnosis is right before that gets built -- it is one word and reverts
exactly.
"""

from __future__ import annotations

#: the branch that sends split screen down the dead path
SCOPE_BRANCH = 0x0019AE40

#: what the game ships there: `bnez $a1, 0x0019b15c`
SCOPE_BRANCH_STOCK = 0x14A000C6

#: and what turns it into "carry on regardless"
SCOPE_BRANCH_OPEN = 0x00000000

#: the render object's split-screen mode, and the fields the draw ought to be
#: reading. Recorded so the cave that follows does not have to find them again.
G_POINTER = 0x00654584          # the word at gp-0x716c
G_SPLIT_MODE = 0x409FC          # 0 single, 2 split
G_FRAMEBUFFER = (0x7C4, 0x7C8)  # 640x448 in BOTH modes -- the bug behind the bug
G_VIEWPORT_RECT = 0x40A00       # x, y, w, h -- what it should use instead

#: the eight reads of the framebuffer size inside the scope draw
FRAMEBUFFER_READS = (0x0019AF34, 0x0019AF48, 0x0019AF68, 0x0019AFD0,
                     0x0019B0A8, 0x0019B0BC, 0x0019B0DC, 0x0019B144)


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_scope", "Draw the scope overlay in split screen",
        BOOL, False, group, confidence="verified", touches="words",
        help="Aiming down sights in split screen gives you the bare reticule "
             "with none of the scope tube around it. The overlay is not "
             "missing -- the textures, the render devices and the "
             "scope-active flag are all set correctly in split screen. One "
             "branch at the very top of the draw sends split screen down a "
             "path whose lookup tables the game only ever fills with zeroes, "
             "so it returns without drawing. This clears that branch.",
        caution="Watched working in split screen on Island Estate: the scope "
                "draws, once in each half, for both players. The diagnosis "
                "above is confirmed.\n\n"
                "It is not yet a finished fix, and the reason is the one this "
                "card always predicted. The draw takes its size from the "
                "framebuffer, which stays 640x448 in split screen, and never "
                "reads the per-viewport rectangle -- so the overlay sits off "
                "to one side instead of around your crosshair. That is what "
                "\"Fit the scope overlay to your half\" is for; turn it on "
                "with this.")


# ---------------------------------------------------------------------------
# fitting the overlay to the viewport
# ---------------------------------------------------------------------------

#: With the branch cleared, the overlay draws -- confirmed on hardware -- but
#: it is sized from the whole framebuffer and appears once per viewport,
#: exactly as predicted. The draw reads the framebuffer at `G+0x7c4` (width)
#: and `G+0x7c8` (height) through eight instructions, and never touches the
#: per-viewport rectangle at `G+0x40a00`, which holds (x, y, w, h).
#:
#: Measured: single player `(0, 0, 640, 448)`, split screen `(0, 224, 640, 224)`
#: -- and the framebuffer is 640x448 in BOTH. So pointing the reads at the
#: viewport's own width and height is a **no-op in single player**, where the
#: two are the same numbers, and only changes split screen.
#:
#: A 16-bit displacement cannot reach `0x40a08`, so each read becomes a call
#: into a cave that builds the address and loads through it.
#:
#: The delay-slot hazard, which the first attempt got wrong
#: --------------------------------------------------------
#:
#: `jal` has a delay slot, so the instruction AFTER a hook executes BEFORE the
#: cave runs. The four height reads are followed by a `daddu` that does not
#: touch `$t0`, so a one-word hook is safe there. The four WIDTH reads are not:
#: each is followed by `bgez $v0`, which both consumes the register the cave is
#: about to load AND puts a branch inside a `jal` delay slot -- undefined on the
#: R5900. The first version of this cheat did exactly that, and it hung the game
#: on the loading screen (single player included, because the branch at
#: `SCOPE_BRANCH` is not taken when `G+0x409fc` is 0, so single player falls
#: straight through into the corrupted words).
#:
#: What the width sites actually are is a signed divide by two, identical at all
#: four, differing only in the destination register::
#:
#:     lw    $v0, 0x7c4($s0)
#:     bgez  $v0, +20
#:     sra   RD, $v0, 1          ; delay slot, the positive path
#:     addiu $v0, $v0, 1
#:     sra   RD, $v0, 1          ; the negative path
#:
#: so the hook replaces the whole five-word idiom with `jal` plus four `nop`s
#: and lets the cave do the halving. Nothing in the image branches into the
#: interior of any of the four (scanned, 0 hits), so the words are free to go.
#: A viewport width is never negative, so the sign fixup has nothing to do.
#:
#: Three further hazards were checked rather than assumed: no hook site sits in
#: a branch delay slot; `$ra` is saved by the prologue at `0x0019adb4`
#: (`sd $ra, 0xb0($sp)`) so `jal` is free to clobber it; and `$at` is dead at
#: every site. It is a cheat rather than a disc edit for the same reason as the
#: wheel labels -- the only free memory is not preserved across a level load.
VIEWPORT_CAVE = 0x005BA0E8

#: register numbers
_AT, _V0, _A3, _T0, _S0, _S6 = 1, 2, 7, 8, 16, 22

#: low half of the viewport rectangle's width and height offsets
VIEWPORT_W, VIEWPORT_H = 0x0A08, 0x0A0C

#: one width cave per destination register, then the shared height cave
_WIDTH_CAVE = {_A3: VIEWPORT_CAVE, _S6: VIEWPORT_CAVE + 24}
_HEIGHT_CAVE = VIEWPORT_CAVE + 48

#: (site, destinationRegister) -- the five-word divide-by-two idiom
WIDTH_HOOKS = ((0x0019AF34, _A3), (0x0019AF68, _S6),
               (0x0019B0A8, _A3), (0x0019B0DC, _S6))

#: (site,) -- a single `lw $t0, 0x7c8($s0)`
HEIGHT_HOOKS = (0x0019AF48, 0x0019AFD0, 0x0019B0BC, 0x0019B144)

JR_RA = 0x03E00008
NOP = 0x00000000


def _lui(rt, imm):
    return (0x0F << 26) | (rt << 16) | (imm & 0xFFFF)


def _ori(rt, rs, imm):
    return (0x0D << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)


def _addu(rd, rs, rt):
    return (rs << 21) | (rt << 16) | (rd << 11) | 0x21


def _lw(rt, base, disp):
    return (0x23 << 26) | (base << 21) | (rt << 16) | (disp & 0xFFFF)


def _sra(rd, rt, sa):
    return (rt << 16) | (rd << 11) | ((sa & 0x1F) << 6) | 0x03


def _addiu(rt, rs, imm):
    return (0x09 << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)


def _bgez(rs, off):
    return (0x01 << 26) | (rs << 21) | (0x01 << 16) | (off & 0xFFFF)


def _jal(target):
    return 0x0C000000 | ((target >> 2) & 0x03FFFFFF)


def width_stock(rd):
    """The five words a width hook replaces, for the given destination."""
    return (_lw(_V0, _S0, 0x07C4), _bgez(_V0, 3), _sra(rd, _V0, 1),
            _addiu(_V0, _V0, 1), _sra(rd, _V0, 1))


#: the single word a height hook replaces
HEIGHT_STOCK = _lw(_T0, _S0, 0x07C8)


def viewport_words():
    """[(va, word, stockWord, note)] for the viewport-fitting cheat."""
    out = []
    for rd, base in sorted(_WIDTH_CAVE.items()):
        body = (_lui(_AT, 0x0004), _ori(_AT, _AT, VIEWPORT_W),
                _addu(_AT, _S0, _AT), _lw(_V0, _AT, 0),
                JR_RA, _sra(rd, _V0, 1))
        for k, word in enumerate(body):
            out.append((base + k * 4, word, 0,
                        "scope: viewport width, halved into r%d" % rd))
    body = (_lui(_AT, 0x0004), _ori(_AT, _AT, VIEWPORT_H),
            _addu(_AT, _S0, _AT), JR_RA, _lw(_T0, _AT, 0))
    for k, word in enumerate(body):
        out.append((_HEIGHT_CAVE + k * 4, word, 0, "scope: viewport height"))
    for site, rd in WIDTH_HOOKS:
        stock = width_stock(rd)
        out.append((site, _jal(_WIDTH_CAVE[rd]), stock[0],
                    "scope: hook the width read at %#x" % site))
        for k in range(1, 5):
            out.append((site + k * 4, NOP, stock[k],
                        "scope: retire the framebuffer halving at %#x" % site))
    for site in HEIGHT_HOOKS:
        out.append((site, _jal(_HEIGHT_CAVE), HEIGHT_STOCK,
                    "scope: hook the height read at %#x" % site))
    return out


def viewport_card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_scope_fit", "Fit the scope overlay to your half",
        BOOL, False, group, confidence="untested", touches="cheat",
        help="With the overlay switched back on it draws at full-screen size "
             "and once per player, because it takes its dimensions from the "
             "whole framebuffer and never looks at the viewport. This points "
             "those eight reads at the viewport's own width and height "
             "instead.",
        caution="This goes in the CHEAT FILE, not onto the disc -- it needs a "
                "few instructions of its own and the only free memory is not "
                "preserved across a level load. It cannot affect single "
                "player: there the viewport and the framebuffer are the same "
                "640x448, so the reads return exactly what they do now. Not "
                "play-tested.",
        requires={prefix + "split_scope": [True]})

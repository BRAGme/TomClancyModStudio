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

#: RETIRED. Nopping the branch is what the first version did, and it crashes
#: a level load. See `SCOPE_GUARD` below. Kept so a disc patched by that build
#: is recognised and restored rather than mistaken for stock.
SCOPE_BRANCH_OPEN = 0x00000000

#: The delay slot, and what it is for. `lui $at, 0x4` looks like scheduling
#: filler and is not: the branch target opens `ori $at, $at, 0x17e8`, so the
#: dead path consumes the $at this sets. Anything that repurposes this word
#: has to make sure the dead path is never reached.
SCOPE_DELAY = 0x0019AE44
SCOPE_DELAY_STOCK = 0x3C010004

#: Where the function gives up and returns -- the label three other guards in
#: this same routine already branch to. Restores ra and s0..s7 and returns.
SCOPE_RETURN = 0x0019B52C

#: The guard that replaces the branch and its delay slot.
#:
#:     0019ae40  sltiu $at, $a1, 3          ; both real modes are 0 and 2
#:     0019ae44  beq   $at, $zero, 0019b52c ; garbage -> return, draw nothing
#:
#: Single player (mode 0) and split screen (mode 2) both fall through, so the
#: feature works and single player is untouched. A load, where G is null or
#: points at text, takes the branch and draws nothing -- which is what the
#: stock code achieved by accident.
#:
#: It jumps to the epilogue rather than to 0x0019b15c deliberately. The dead
#: path needs $at == 0x40000 from the old delay slot, and the guard has to
#: clobber $at to do its compare; going straight to the return sidesteps that
#: instead of leaving a corrupted address behind.
#:
#: The new branch's delay slot is the untouched `lb $v1, 0x0($s0)` at
#: 0x0019ae48. It runs on both paths, which is harmless: it is a load, $v1 is
#: dead at the epilogue, and a read through a garbage $s0 is a read of RAM.
SCOPE_GUARD = (
    (0x0019AE40, 0x2CA10003),      # sltiu $at, $a1, 3
    (0x0019AE44, 0x102001B9),      # beq   $at, $zero, 0x0019b52c
)

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
                "The first version of this cleared the branch outright, and "
                "that crashed the emulator during the Mountain Highway load "
                "with a VIF FIFO assert. The branch is not only the "
                "split-screen test -- it is also what stops the draw running "
                "before the renderer exists, which measured savestates show "
                "it does not for the whole load. It is now a guard that "
                "admits the two real modes and returns on anything else. "
                "Island Estate had loaded only because the garbage there "
                "happened to be survivable.\n\n"
                "It is not yet a finished fix, and the reason is the one this "
                "card always predicted. The draw takes its size from the "
                "framebuffer, which stays 640x448 in split screen, and never "
                "reads the per-viewport rectangle -- so the overlay sits off "
                "to one side instead of around your crosshair. That is what "
                "\"Fit the scope overlay to your half\" is for; turn it on "
                "with this." + " Watched working in split screen on Mountain Highway: with the cave in the scope draw's dead path the overlay is sized to each half instead of the framebuffer. What it does NOT fix is the overlay appearing for both players at once -- m_bScopeVisionActive lives on the shared LevelInfo, so aiming down sights gives the other player a scope too. That is a separate defect and still open.")


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
#: Where the cave lives now. See `rsedeadpath` for why the run of zeroes at
#: 0x005ba0b8 could not hold it: the game clears that memory, so the hooks
#: jumped into nops and the EE ran off into the kernel exception handler.
#:
#: Most of this no longer needs a cave at all. Each width read is the head of
#: a FIVE-word divide-by-two idiom, which is room enough to build the address
#: inline:
#:
#:     lui   $at, 0x0004
#:     addu  $at, $s0, $at        ; $at = G + 0x40000
#:     lw    $v0, 0x0a08($at)     ; the viewport's own width
#:     sra   RD,  $v0, 1
#:     nop
#:
#: and that leaves `$at` holding `G + 0x40000` afterwards. Two of the four
#: height reads sit immediately after a width site, so they are one word each
#: with no setup:  `lw $t0, 0x0a0c($at)`.
#:
#: The other two are a call away from any width site, where `$at` is long
#: gone -- `$at` is scratch and a callee may use it freely -- so those two go
#: through the cave.
VIEWPORT_W, VIEWPORT_H = 0x0A08, 0x0A0C

#: register numbers
_AT, _V0, _A3, _T0, _S0, _S6 = 1, 2, 7, 8, 16, 22

#: (site, destinationRegister) -- the five-word divide-by-two idiom
WIDTH_HOOKS = ((0x0019AF34, _A3), (0x0019AF68, _S6),
               (0x0019B0A8, _A3), (0x0019B0DC, _S6))

#: height reads that follow a width site, so `$at` is still good
HEIGHT_NEAR = (0x0019AF48, 0x0019B0BC)

#: height reads too far from one, which need the cave
HEIGHT_FAR = (0x0019AFD0, 0x0019B144)

JR_RA = 0x03E00008
NOP = 0x00000000


def _lui(rt, imm):
    return (0x0F << 26) | (rt << 16) | (imm & 0xFFFF)


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


def viewport_words(freed=True):
    """[(va, word, stockWord, note)] for fitting the overlay to the viewport.

    `freed` says the caller has already emitted whatever makes the dead path
    unreachable -- the guard, or `rsedeadpath.FREE_BRANCH`. It is passed
    through rather than assumed because a cave in a block split screen can
    still branch into would be executed as code.
    """
    from . import rsedeadpath

    out = []
    cave = rsedeadpath.claim("scope_height", freed)
    body = (_lui(_AT, 0x0004), _addu(_AT, _S0, _AT), JR_RA,
            _lw(_T0, _AT, VIEWPORT_H))          # the lw is the jr's delay slot
    for k, word in enumerate(body):
        va = cave + k * 4
        out.append((va, word, rsedeadpath.stock(va),
                    "scope: viewport height cave"))

    for site, rd in WIDTH_HOOKS:
        stock = width_stock(rd)
        built = (_lui(_AT, 0x0004), _addu(_AT, _S0, _AT),
                 _lw(_V0, _AT, VIEWPORT_W), _sra(rd, _V0, 1), NOP)
        for k in range(5):
            out.append((site + k * 4, built[k], stock[k],
                        "scope: viewport width at %#x" % site))

    for site in HEIGHT_NEAR:
        out.append((site, _lw(_T0, _AT, VIEWPORT_H), HEIGHT_STOCK,
                    "scope: viewport height at %#x" % site))
    for site in HEIGHT_FAR:
        out.append((site, _jal(cave), HEIGHT_STOCK,
                    "scope: viewport height via the cave at %#x" % site))
    return out


def viewport_card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_scope_fit", "Fit the scope overlay to your half",
        BOOL, False, group, confidence="verified", touches="words",
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

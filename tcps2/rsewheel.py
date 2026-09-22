"""The equipment wheel that split screen replaces with one-item cycling.

Hold L1 in Rainbow Six 3 and an eight-slot wheel opens. In split screen it does
not: L1 steps one item per press, which costs time in a firefight.

What it actually is
-------------------

The wheel is `R6InteractionInventoryMnu`, which extends
`R6InteractionRoseDesVents` (*rose des vents* -- compass rose; the studio was
Ubisoft Montreal) and is drawn by the inherited `DrawRoseDesVents`.

Pressing L1 does not open it. `KeyEvent` sets `m_bCycleWeapon` and starts
`m_fCycleTimer` at 0.3s, and that runs in BOTH modes -- it has no split-screen
test at all, which is why cycling still works. The wheel appears only when the
timer runs out while the button is still down. `Tick` is what counts it down,
and the tail of `Tick` makes the call that opens the wheel.

Measured across three savestates:

=============================  ==============  ==============
state                          m_bShowMenu     m_fCycleTimer
=============================  ==============  ==============
single player, wheel OPEN      **1**           **-0.0118**
split screen, L1 held          0               **0.3000**
split screen, idle             0               0.3000 (stale)
=============================  ==============  ==============

The timer counts down in single player and never moves in split screen. That
is the whole defect.

The gate
--------

`R6PlayerController.Tick` is what ticks the interaction, through
`m_InteractionInventory` at object offset 0x850::

    if ( Level.Game != None && m_InteractionInventory != None
         && Level.Game.m_bIsSplitScreen == False )
        m_InteractionInventory.Tick(fDeltaTime);
    else if ( Level.NetMode == 3 && m_InteractionInventory != None )
        m_InteractionInventory.Tick(fDeltaTime);

Split screen is excluded from the first branch deliberately, and the fallback
only fires at `NetMode == 3`. **`NetMode` is 0 in both single player and split
screen on this console** -- read out of the savestates -- so the fallback is
dead code and nothing ticks the wheel in split screen.

The fix is the constant: `NetMode == 3` becomes `NetMode == 0`.

Why this shape of edit is safe
------------------------------

Single player never reaches the fallback. Its first branch matches (split
screen is false), it ticks, and then jumps past the fallback entirely -- so
the byte this changes is not on the single-player path at all.

The one thing it gives up is online play WITH split screen, where `NetMode`
would be 3 and the fallback would no longer match. Rainbow Six 3's PS2 servers
are long gone, so that combination is not reachable.

One byte, so the container's length never moves, and exactly reversible.

An earlier attempt, now withdrawn
---------------------------------

The first version of this patched a split-screen test in
`R6InteractionInventoryMnu.ActionKeyPressed`. It was verified on the disc in
all three containers and changed nothing, because **nothing calls
`ActionKeyPressed`** -- this class overrides `KeyEvent` and handles the button
itself. It was dead code. `ANCHOR_OLD` keeps the pattern so a disc patched by
that build can be recognised and put back.
"""

from __future__ import annotations

#: The else-branch of `R6PlayerController.Tick`: the Jump that skips it when
#: the first branch ran, the JumpIfNot that guards it, the `NetMode == 3` test
#: and the null-check on `m_InteractionInventory`. 33 bytes, and unique: one
#: occurrence in each of `COMMON.LIN`, `COMMONOFF.LIN` and `COMMON_SS.LIN`, all
#: at plain offset 0x10ecb8, and none anywhere else.
#:
#: The length matters. A shorter pattern also matches a SECOND `NetMode == 3`
#: test at 0x109b9d which ticks a different object entirely -- it carries index
#: `b1` where this one carries `7f 02` (`m_InteractionInventory`) -- and
#: patching that one would change something unrelated.
ANCHOR = bytes.fromhex(
    "06fb00"            # Jump 0xfb -- taken when the first branch ticked
    "07fb00"            # JumpIfNot 0xfb -- the fallback's guard
    "829a393a"
    "1901" "8f05"       # Level
    "0001" "01" "a2"    # .NetMode
    "393a"
    "2403"              # IntConstByte 3   <-- the byte this module changes
    "16"
    "180900"
    "7701" "7f02"       # m_InteractionInventory
    "2a1616"
)

#: Where the constant sits inside `ANCHOR`.
CONST_AT = 21

#: What it ships as, and what it becomes.
NETMODE_SHIPPED = 3
NETMODE_STANDALONE = 0

#: The dead-code site the withdrawn first attempt used, kept only so a disc
#: patched by that build can be recognised and restored.
ANCHOR_OLD = bytes.fromhex(
    "073d008419010d0600042d01c902182500f2"
    "191919010d050004018f050004" "01a60600042d01ed01" "271616040b")

EX_JUMP_IF_NOT = 0x07
EX_JUMP = 0x06

#: where the fallback sits, so a test can assert rather than search blindly
KNOWN_OFFSET = 0x10ECCD          # the constant itself; the anchor starts at 0x10ECB8

#: and where the withdrawn first attempt's site sat
KNOWN_OFFSET_OLD = 0x15EC08


class WheelError(Exception):
    pass


#: The anchor with the constant blanked, so the search finds the site both
#: before and after the edit. Matching on the whole anchor would find it only
#: while it is stock, and the edit could then be neither read back nor undone.
_HEAD = ANCHOR[:CONST_AT]
_TAIL = ANCHOR[CONST_AT + 1:]


def find(plain: bytes) -> int:
    """The offset of the NetMode constant, or raise."""
    at = plain.find(_HEAD)
    if at < 0:
        raise WheelError("the split-screen tick fallback is not in this file")
    if plain.find(_HEAD, at + 1) >= 0:
        raise WheelError("the split-screen tick fallback appears more than "
                         "once; refusing to guess which one to change")
    const = at + CONST_AT
    if plain[const + 1:const + 1 + len(_TAIL)] != _TAIL:
        raise WheelError("the bytes after the NetMode constant are not what "
                         "this disc revision should have")
    if plain[const] not in (NETMODE_SHIPPED, NETMODE_STANDALONE):
        raise WheelError("the NetMode constant is %d, which is neither the "
                         "shipped 3 nor the patched 0" % plain[const])
    return const


def restore(plain: bytes, enable: bool = True):
    """Point the tick fallback at standalone play, or put it back.

    Returns (plain, changed). Exactly one byte moves and the length never does.
    """
    at = find(plain)
    want = NETMODE_STANDALONE if enable else NETMODE_SHIPPED
    if plain[at] == want:
        return plain, 0
    out = bytearray(plain)
    out[at] = want
    if len(out) != len(plain):
        raise WheelError("the wheel edit changed the file length")
    return bytes(out), 1


def reads(plain: bytes) -> bool:
    """True if this file already has the fallback pointed at standalone."""
    return plain[find(plain)] == NETMODE_STANDALONE


def undo_first_attempt(plain: bytes):
    """Put back the dead-code byte the withdrawn first version changed.

    A disc patched by that build carries `EX_Jump` where the game shipped
    `EX_JumpIfNot`. It does nothing either way, but leaving a stray edit on the
    disc would make a later diff lie about what is stock.
    """
    at = plain.find(ANCHOR_OLD[1:])
    if at < 1:
        return plain, 0
    at -= 1
    if plain[at] != EX_JUMP:
        return plain, 0
    out = bytearray(plain)
    out[at] = EX_JUMP_IF_NOT
    return bytes(out), 1


def card(prefix, group):
    """The one option this module offers."""
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_wheel", "Equipment wheel in split screen", BOOL, False,
        group, confidence="verified", touches="data",
        help="Holding L1 opens the eight-slot wheel in single player; in split "
             "screen it steps one item per press instead. The reason is that "
             "nothing counts the hold: the player controller ticks the wheel "
             "only when the game is NOT split screen, and its fallback fires "
             "only in a network mode this console never reports. This points "
             "that fallback at the mode split screen actually runs in.",
        caution="Watched in split screen on Mountain Highway. The wheel's contents -- the weapon icons and the four labels -- scale with the ring now instead of being laid out for a full-height screen, which is a visible improvement. What it does NOT fix is the wheel as a whole: it is drawn at one fixed position that does not follow the viewport, so it spans the split and clips into the other player's half. Measured from a wheel-open savestate: the two per-viewport canvases are geometrically identical -- both 640x224, clip 640x224, centre (320,112) -- and NEITHER carries a screen Y origin, every candidate field reading zero. So the canvas cannot say which half to draw into; that offset comes from the renderer's viewport state and the wheel does not get it. Fixing it means moving the draw into the per-viewport pass or offsetting it by the viewport Y at G+0x40a04, neither of which is a hook on one instruction. Turn this on for the tidier contents; it is an improvement, not a finished fix.",
        requires={prefix + "split_wheel": [True]})


# ---------------------------------------------------------------------------
# the wheel's labels, which do not scale with the viewport
# ---------------------------------------------------------------------------

#: `execDrawRoseDesVents` at `0x00437b20` draws the ring through a scale it
#: derives from the canvas -- `f20 = SizeX/640`, `f21 = SizeY/480`, both read
#: off the canvas the script hands it. The four text labels do NOT go through
#: either. Their geometry is a struct of four floats (X, Y, W, H) built on the
#: stack and passed as `$a2` to a vtable call at `+0x18`:
#:
#:     label   block        X      Y    W    H
#:     top     sp+0x2990   275.0   0   90   80
#:     right   sp+0x29b0   365.0   0   80   80
#:     bottom  sp+0x29d0   275.0   0   90   80
#:     left    sp+0x29f0   195.0   0   80   80
#:
#: The X values sit around the 320 centre exactly as they appear on screen, and
#: `Y` is stored as literal zero in all four -- the vertical position is a
#: float computed into `$f0` just before each call (`115.0 + s4/2` for the
#: first). X needs no correction, because `ClipX` is 640 in both modes; only
#: the Y is wrong, and only in split screen, where the ring shrinks to
#: `224/480` and the labels stay where a 448-tall canvas put them. That is why
#: they spill into the other player's half.
#:
#: Scaling `$f0` by `$f21` is one instruction that does not exist, so this
#: needs a cave -- and it has to be a CHEAT FILE cave rather than a disc edit,
#: because the overlay has no padding inside real code and every large zero run
#: sits in the region the map-wide spawn work already proved is not preserved
#: across a level load. A pnach rewrites its cave every frame, which is exactly
#: what makes it work there.
#:
#: The hook replaces the instruction that loads `$a2`, and the cave puts that
#: instruction back in the delay slot of its own return:
#:
#:     CAVE_n:  mul.s $f0, $f0, $f21
#:              jr    $ra
#:              addiu $a2, $sp, BLOCK      ; the replaced instruction
#:
#: `$ra` is free to clobber at that point: the very next instruction is
#: `jalr $ra, $t9`, which overwrites it anyway.
#: `mul.s $f0, $f0, $f21` -- fmt 16 (single), ft $f21, fs $f0, fd $f0, funct 2
MUL_F0_BY_F21 = 0x46150002
JR_RA = 0x03E00008
NOP = 0x00000000

#: Where each label's vertical position is FINISHED, and the free `nop`
#: immediately before it.
#:
#: The first version of this hooked `addiu $a2, $sp, BLOCK` at 0x004388a8 and
#: friends, on the reading that the Y is "computed into $f0 just before each
#: call". It is, and it is also SPILLED before then:
#:
#:     0043888c  nop
#:     00438890  add.s $f0, $f0, $f1        ; the Y
#:     00438894  jal   00184170
#:     00438898  swc1  $f0, 0x29a4($sp)     ; the Y goes to the stack HERE
#:     004388a8  addiu $a2, $sp, 0x2990     ; the old hook -- far too late
#:
#: so scaling $f0 at the old site scaled a register the draw had stopped
#: reading. That is why the cave was live on hardware and the labels still
#: spilled into the other player's half.
#:
#: The spill cannot be hooked either: it sits in the delay slot of the `jal`
#: above it, and a jump in a delay slot is undefined on the R5900.
#:
#: The `nop` before the add.s can. `jal` there puts the add.s in ITS delay
#: slot, so the Y is computed first, the cave scales it, and the spill that
#: follows stores the scaled value. $ra is free to clobber: the very next
#: instruction is a `jal`, which sets it again.
LABEL_HOOKS = (0x0043888C, 0x00438C0C, 0x00438F88, 0x00439304)

#: what the game ships at each -- a real nop, checked, and nothing in the
#: image branches to any of them or to the add.s behind them
LABEL_STOCK = NOP


def label_words(freed=True):
    """[(va, word, stockWord, note)] for scaling the four labels.

    One cave serves all four, because hooking the nop makes the body the
    same everywhere: scale $f0, return. $f21 is the viewport scale the ring
    already uses, set by `div.s $f21, $f1, $f0` at 0x0043807c; it is
    callee-saved and nothing rewrites it before any hook.

    `freed` carries the caller's confirmation that the dead path's entry
    branch is gone; see `rsedeadpath`.
    """
    from . import rsedeadpath

    out = []
    cave = rsedeadpath.claim("wheel_label", freed)
    for k, word in enumerate((MUL_F0_BY_F21, JR_RA, NOP)):
        va = cave + k * 4
        out.append((va, word, rsedeadpath.stock(va),
                    "wheel labels: scale the label Y by the viewport"))
    jal = 0x0C000000 | ((cave >> 2) & 0x03FFFFFF)
    for i, site in enumerate(LABEL_HOOKS):
        out.append((site, jal, LABEL_STOCK,
                    "wheel labels: hook label %d" % (i + 1)))
    return out


def label_card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_wheel_labels",
        "Keep the wheel's labels inside your half", BOOL, False, group,
        confidence="applied", touches="words",
        caution="Watched in split screen on Mountain Highway: the four labels now scale with the ring instead of sitting where a full-height screen put them, so they no longer drop past the bottom of your half. That part works. What it does NOT fix is where the wheel is drawn. Player 2 holding L1 gets the wheel in PLAYER 1's half. Measured from a savestate with the wheel open: the two per-viewport canvases are geometrically identical -- both 640x224, clip 640x224, centre (320,112) -- and NEITHER carries a screen Y origin, every candidate field reading zero. So the canvas cannot say which half to draw into; that offset comes from the renderer's viewport state, and the wheel is drawn at the framebuffer origin rather than inside the per-viewport pass. Fixing it means moving the draw into that pass or offsetting it by the viewport Y at G+0x40a04, neither of which is a hook on one instruction. Turn this on if you want the labels tidy; it is an improvement, not a finished fix.",
        requires={prefix + "split_wheel": [True]})

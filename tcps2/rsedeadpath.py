"""The one piece of memory on this disc that can hold a code cave.

Why a cave was needed, and why the first two places were wrong
--------------------------------------------------------------

Two split-screen HUD fixes need a handful of instructions of their own:
fitting the scope overlay to a viewport, and scaling the equipment wheel's
labels. Both first used a run of zeroes near the end of the overlay, at
`0x005ba0b8`, carried in a cheat file.

That memory does not survive. A savestate taken while the game was frozen
settles it: the hooks were live -- `0x0019af34` held its `jal` and so did
`0x004388a8` -- and the cave they jumped into read all zeroes, with the EE
parked in the kernel exception handler at `0x8001046c`. Each hook jumped into
a run of nops and ran off the end.

Writing the cave to the DISC instead does not help, and a commit in this repo
briefly claimed it would on the grounds that the bytes are zero inside
`SP.SOZ`. Being in the file says nothing about surviving the load: the region
is in the overlay and the game clears it anyway. Carrying it in a cheat file
does not help either, for a sharper reason -- a mode-1 pnach rewrites the cave
every frame and the game zeroes it between writes, so every frame has a window
where the hook exists and the cave does not. That race is why it was
intermittent: one load fine, the next asserting `FQC = 0 on VIF FIFO READ`.

Where it does work
------------------

The same savestate says what does survive: the hooks did, and they are ordinary
overlay code. So a cave has to live in code, not in a zero run.

There is dead code to spare. The scope draw's split-screen arm at
`0x0019b15c` indexes two arrays that a whole-image scan finds no writer for
except an init block storing zeroes, so it draws nothing and returns -- the
reason `rsescope` exists at all. A scan of the entire image finds **exactly one
branch into it**, the `bne` at `0x0019ae40`, and every user of this region
rewrites that branch. With it rewritten the block is unreachable, and being
code it is loaded and preserved like the hooks.

Keeping the branch honest
-------------------------

Two different edits can free the block, and which one is used matters:

* `rsescope`'s guard, when the scope option is on. It replaces the branch with
  a test that admits the two real modes and returns otherwise.
* `FREE_BRANCH` here, when the scope option is off but something still needs
  the cave. It points the branch at the function's own epilogue instead of the
  dead path, which is **behaviour-identical to stock** -- split screen still
  branches away and still draws nothing -- while leaving the block empty.

Without the second one, turning on the wheel labels alone would leave a live
branch into what is now cave code. `claim` refuses to hand out a slot without
being told the branch has been dealt with, so that cannot be forgotten.
"""

from __future__ import annotations

#: First word of the dead block, and how many words of it are safe to use.
#: The block runs well past this; 24 is what has been read and checked
#: instruction by instruction, and nothing needs more than 16.
CAVE = 0x0019B15C
CAVE_WORDS = 24

#: What the game ships in the first 16 words, so every write is asserted
#: against the real thing rather than assumed to be padding.
STOCK_WORDS = (
    0x342117E8, 0x02011821, 0x00651821, 0x90630000,
    0x106000EF, 0x00000000, 0x348417EC, 0x00051880,
    0x02042021, 0x00831821, 0x8C630000, 0x106000E8,
    0x00000000, 0x24040001, 0x0C064808, 0x0000282D,
    0x3C010004, 0x02010821, 0x8C2309FC, 0x3C010004,
    0x00031880, 0x342117EC, 0x02011021, 0x00431021,
)

#: The block's only entry, and the word that sends it to the epilogue
#: instead. Stock is `bne $a1, $zero, 0x0019b15c`; this is
#: `bne $a1, $zero, 0x0019b52c`, the same test with a different target.
ENTRY = 0x0019AE40
ENTRY_STOCK = 0x14A000C6
FREE_BRANCH = 0x14A001BA

#: Who gets which words. Fixed rather than allocated on demand, so two
#: options can never be handed the same address -- the bug that a shared
#: hand-picked cave address invites.
SLOTS = {
    "scope_height": (0, 4),        # lui / addu / jr / lw
    # One slot, not four. The first design hooked the instruction that built
    # the draw's argument, which is a different word per label, so each label
    # needed its own cave to put its own word back. Hooking the nop before
    # the add.s instead means the cave body is identical for all four --
    # scale f0, return -- so they share it.
    "wheel_label": (4, 3),         # mul.s / jr / nop
    # The weapon-sway stick selector. Six words, shared by both copies
    # of the sway routine because the body does not depend on which.
    "sway_stick": (7, 6),          # lw / sll / addu / lwc1 / jr / lwc1
}


class DeadPathError(Exception):
    pass


def claim(name: str, freed: bool) -> int:
    """The address of a named slot, once the caller confirms the branch is gone.

    `freed` is the caller saying it has emitted either the scope guard or
    `FREE_BRANCH`. It is a parameter rather than a comment because the whole
    safety of this region rests on it: with the branch still live, split
    screen jumps straight into cave code.
    """
    if not freed:
        raise DeadPathError(
            "the dead path still has its entry branch; a cave here would be "
            "executed by split screen. Emit the scope guard or FREE_BRANCH "
            "first.")
    if name not in SLOTS:
        raise DeadPathError("no slot called %r" % (name,))
    first, _n = SLOTS[name]
    return CAVE + first * 4


def stock(va: int) -> int:
    """What the game ships at a cave address."""
    i = (va - CAVE) // 4
    if not (0 <= i < len(STOCK_WORDS)) or (va - CAVE) % 4:
        raise DeadPathError("0x%08x is not a word inside the dead path" % va)
    return STOCK_WORDS[i]


def stock_map() -> dict:
    """Every cave address with its shipped word, for the profile's STOCK."""
    return {CAVE + i * 4: w for i, w in enumerate(STOCK_WORDS)}


def check_layout():
    """No two slots overlap and none runs past what has been checked."""
    used = {}
    for name, (first, n) in sorted(SLOTS.items()):
        if first + n > CAVE_WORDS:
            raise DeadPathError("%s runs past the checked block" % name)
        for k in range(first, first + n):
            if k in used:
                raise DeadPathError("%s overlaps %s at word %d"
                                    % (name, used[k], k))
            used[k] = name
    return len(used)

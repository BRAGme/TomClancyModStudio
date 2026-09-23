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
#:
#: 244: the whole block, 0x0019b15c up to the epilogue at 0x0019b52c. With
#: the entry branch retired, a control-flow walk leaves every word of it
#: unreachable, and a scan of the entire stock image finds exactly one
#: branch or jump into it from outside -- the entry at `ENTRY` -- and no data
#: word pointing into it. The first 96 were proved first; the rest were
#: needed when the wheel's label text wanted three more caves and a pair of
#: data words.
CAVE = 0x0019B15C
CAVE_WORDS = 244

#: What the game ships in every word of the block, so every write is
#: asserted against the real thing rather than assumed to be padding.
STOCK_WORDS = (
    0x342117E8, 0x02011821, 0x00651821, 0x90630000,
    0x106000EF, 0x00000000, 0x348417EC, 0x00051880,
    0x02042021, 0x00831821, 0x8C630000, 0x106000E8,
    0x00000000, 0x24040001, 0x0C064808, 0x0000282D,
    0x3C010004, 0x02010821, 0x8C2309FC, 0x3C010004,
    0x00031880, 0x342117EC, 0x02011021, 0x00431021,
    0x8C440000, 0x8C990000, 0x8F3900A4, 0x0320F809,
    0x00000000, 0x0040A02D, 0x0200202D, 0x0280282D,
    0x0000302D, 0x0000382D, 0x0C06A474, 0x0000402D,
    0x0040282D, 0x0200202D, 0x0000302D, 0x0000382D,
    0x0000402D, 0x27898DAC, 0x0C06A124, 0x0000502D,
    0x8F868DAC, 0x24020080, 0x0002183C, 0x24020089,
    0x00431825, 0x24020042, 0x24C50010, 0xAF858DAC,
    0xFCC30000, 0xFCC20008, 0x8E990000, 0x8F390024,
    0x0320F809, 0x0280202D, 0x8E990000, 0x2456FFFF,
    0x8F390028, 0x0320F809, 0x0280202D, 0xFFB30000,
    0x2443FFFF, 0xFFB60008, 0x3C020004, 0xFFA30010,
    0x34430A00, 0xFFA00018, 0x02032021, 0xFFA00020,
    0x34430A04, 0xFFA00028, 0x34420A08, 0x02031821,
    0x02021021, 0x8C420000, 0x04410003, 0x00023843,
    0x24420001, 0x00023843, 0x3C020004, 0x8C850000,
    0x34420A0C, 0x8C660000, 0x02021021, 0x02A0482D,
    0x8C480000, 0x0220502D, 0x0240582D, 0x0C067130,
    0x0200202D, 0x3C010004, 0x02010821, 0x8C220A08,
    0x04410003, 0x0002B043, 0x24420001, 0x0002B043,
    0x8E990000, 0x8F390024, 0x0320F809, 0x0280202D,
    0x8E990000, 0x2457FFFF, 0x8F390028, 0x0320F809,
    0x0280202D, 0xFFB30000, 0x3C010004, 0xFFB70008,
    0x2442FFFF, 0xFFA00010, 0x02010821, 0xFFA00018,
    0x0200202D, 0xFFA20020, 0x0000302D, 0xFFA00028,
    0x02C0382D, 0x8C220A00, 0x02A0482D, 0x0220502D,
    0x0240582D, 0x3C010004, 0x02010821, 0x8C280A0C,
    0x0C067130, 0x00562821, 0x3C010004, 0x02010821,
    0x8C2409FC, 0x3C010004, 0x00042080, 0x342117F4,
    0x02011821, 0x00641821, 0x8C640000, 0x10800068,
    0x00000000, 0x8C990000, 0x8F3900A4, 0x0320F809,
    0x00000000, 0x0040A02D, 0x0200202D, 0x0280282D,
    0x0000302D, 0x0000382D, 0x0C06A474, 0x0000402D,
    0x0040282D, 0x0200202D, 0x0000302D, 0x0000382D,
    0x0000402D, 0x27898DAC, 0x0C06A124, 0x0000502D,
    0x8F868DAC, 0x24020080, 0x0002183C, 0x24020068,
    0x00431825, 0x24020042, 0x24C50010, 0xAF858DAC,
    0xFCC30000, 0xFCC20008, 0x8E990000, 0x8F390024,
    0x0320F809, 0x0280202D, 0x8E990000, 0x2456FFFF,
    0x8F390028, 0x0320F809, 0x0280202D, 0xFFB30000,
    0x3C010004, 0x2442FFFF, 0xFFB60008, 0xFFA20010,
    0x02010821, 0xFFA00018, 0xFFA00020, 0xFFA00028,
    0x8C220A08, 0x04410003, 0x00023843, 0x24420001,
    0x00023843, 0x3C010004, 0x0200202D, 0x02010821,
    0x02A0482D, 0x8C250A00, 0x0220502D, 0x3C010004,
    0x02010821, 0x8C260A04, 0x3C010004, 0x02010821,
    0x8C280A0C, 0x0C067130, 0x0240582D, 0x3C010004,
    0x02010821, 0x8C220A08, 0x04410003, 0x0002B043,
    0x24420001, 0x0002B043, 0x8E990000, 0x8F390024,
    0x0320F809, 0x0280202D, 0x8E990000, 0x2457FFFF,
    0x8F390028, 0x0320F809, 0x0280202D, 0xFFB30000,
    0x3C010004, 0xFFB70008, 0x2442FFFF, 0xFFA00010,
    0x02010821, 0xFFA00018, 0x02A0482D, 0xFFA20020,
    0x0220502D, 0xFFA00028, 0x0240582D, 0x8C220A00,
    0x0200202D, 0x0000302D, 0x02C0382D, 0x3C010004,
    0x02010821, 0x8C280A0C, 0x0C067130, 0x00562821,
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
    # The wheel's label text. It scales the Y, then adds the viewport's own
    # origin, because the canvas the wheel draws into carries its SIZE but
    # never its ORIGIN -- which is why the wheel lands in the top half
    # whoever opened it.
    "wheel_label": (4, 11),        # mul.s / read VPY / add / jr
    "sway_stick": (15, 6),         # lw / sll / addu / lwc1 / jr / lwc1
    # The wheel's label boxes. Tail-jumps into the 2D primitive so $ra
    # still returns straight to the wheel.
    "wheel_box": (21, 11),
    # The wheel's ring, four quadrant sprites off one Y in $f23.
    # 16 words: it also has to BUILD the ring scale, because the ring
    # is the one element the game draws at native texture size.
    "wheel_ring": (63, 16),
    # The weapon icons. They pass a DESIGN-space Y that the sprite
    # call multiplies by the scale, so this one divides the viewport
    # offset by that scale before adding it.
    # NOT the weapon icons. These four sprite calls draw the blinking
    # marker on the SELECTED direction, and only its up and down cases;
    # left and right go through a different primitive. The weapon icons
    # are the eight box calls, which "wheel_box" already covers.
    "wheel_indicator": (42, 11),
    # The marker's LEFT and RIGHT cases. They go through the rotated-quad
    # call at 0x00469A10, which hard-codes a 1.0 output scale, so they kept
    # the native size the ring had before its own fix -- twice too tall in a
    # half-height viewport and never moved into player 2's half. 17 words:
    # scale the rectangle's width (the visible height, after the 90-degree
    # turn) by the ring's SizeY/448, keep its centre, add the viewport Y.
    "wheel_side": (79, 17),
    # The wheel's label TEXT. Its glyph height is the font's own 15 pixels,
    # added after the only scale the text path has, so the fix lives in the
    # shared string drawer: the wheel arms a (scale, viewport Y) pair in
    # these two DATA words around its four labels (the "wheel_label" slot
    # above is the arm), the drawer applies it to every glyph, and the pair
    # is put back to (1.0, 0.0) after the fourth label. They ship as 1.0 and
    # 0.0, which is what makes every other piece of text bit-identical.
    "label_scale": (96, 2),
    "label_text": (98, 10),        # per glyph: Y0 = k*Y0 + vpY, h = k*VSize
    "label_unarm": (108, 5),       # (1.0, 0.0) again, then the real call
    # The split-screen team panel (rsehudteam): single player's own panel
    # code, entered from the split-screen HUD tail with a marker in the
    # full-screen nesting counter, and every quad shifted into this half
    # while the marker is set. Fixed addresses: the caves were assembled
    # for exactly these words.
    "team_quad": (113, 19),
    "team_entry": (132, 20),
    "team_skipbox": (152, 8),
    "team_names": (160, 10),
    "team_exit": (170, 18),
    "team_roster": (188, 38),
    # Stop one player's wheel drawing into the other's half. The
    # engine dispatcher renders EVERY viewport's interaction list into
    # EACH viewport's canvas, so the per-player gate is honoured and
    # then ignored one level up.
    "wheel_owner": (53, 10),
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

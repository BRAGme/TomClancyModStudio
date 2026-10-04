r"""Where the message box sits on the screen.

Objectives, "mission objective updated", "X has been incapacitated" and the
other boxed messages all go through one place, and the vertical position is a
single immediate.

THE PATH
--------

Script hands the text over and stops being involved::

    R6PlayerController.ClientShowMissionObjective (block 0x108F4C)
        strObjective = ... Localize("Game", p_strObjKey, p_strLocalizationKey)
        playerHUD.DisplayMessage(strObjective, True, False, True)

`R6HUD.DisplayMessage` appends to `m_messageArray` at HUD+0x634, and nothing in
script draws it: `R6HUD.PostRender` is four statements, one of which is
`DrawNativeHUD` (native, 0x003E7488..0x003EFA70), and `R6HUD.DisplayMessages`
only sets the colour, style and font. The box, the background art and the text
are all native.

There are five accesses to the field in the whole renderer, and every one was
read out of the pristine overlay::

    0x003eaf10  addiu $v0, $zero, 0x26   OUR IMMEDIATE (38)
    0x003eaf14  sw    $v0, 0x51c($s4)    the store
    0x003eaf3c  lw    $v0, 0x51c($s4)
    0x003eaf40  addiu $v0, $v0, 20       a CONDITIONAL +20, see below
    0x003eaf44  sw    $v0, 0x51c($s4)
    0x003eafa8  lw    $a2, 0x51c($s4)    the background art's Y
    0x003edf50  lw    $v0, 0x51c($s4)    the text's Y

The art is drawn at X=125, W=390 (`addiu $a1,$zero,125` and
`addiu $a3,$zero,390` at 0x003eaf8c and 0x003eaf90) with this field as its Y.
The text is set up at X=136, W=368, clip bottom 480 (0x003edf4c, 0x003edf54,
0x003edf58) and its origin is `addiu $a2, $v0, 9` in the delay slot at
0x003edf68 -- nine pixels below the box, always. So one immediate moves the art
and the text together, and `PostFadeDrawNativeHUD` reads the same field and
inherits it.

THE +20
-------

0x003eaf3c..0x003eaf44 is a read-modify-write, which looks at first as though
it would overwrite whatever we set. It does not: it is `+= 20`, relative to our
value rather than a replacement. It is gated twice -- `HUD+0x5f0 -> +0x578`
non-zero, then the bool at `+0x4d9` -- so it applies sometimes and not others,
and the real position is Y or Y+20 depending on HUD state. Every number below
is given for the worst case, which is Y+20.

MEASURED IN GAME
----------------

Y=396 was played and photographed, and the screenshot measured in canvas
coordinates (the clip constant of 480 sets the scale). Two numbers came out of
it, and the choices below are derived from them rather than guessed:

    the HUD's top edge      canvas Y 349
                            (max brightness over the left panel jumps from 48
                            to 91 between row 348 and row 349)
    one line of message     canvas Y 402..418 with the field at 396
                            so the glyphs start at Y+6 and a line is 17 tall

That makes the room test `Y + 20 + 6 + 17*lines <= 349` to stay clear of the
HUD, and `Y + 6 + 17*lines <= 480` to stay on screen at all:

    1 line clears the HUD   Y <= 306
    2 lines clear the HUD   Y <= 289
    3 lines clear the HUD   Y <= 272

`above_hud` is 288, the largest value that keeps TWO lines clear of the HUD
even when the +20 fires -- and three lines clear when it does not. `bottom` is
kept at 396 because it is the lowest usable position, but it does overlap the
HUD and its label says so.

A genuinely bottom-anchored box -- `Y = K - height` -- needs a load and a
subtract, which is a cave hook rather than one word, so it is not offered here.

PLAYS NICELY WITH THE TEAM PANEL
---------------------------------

`rsehudteam` replaces the very next word, 0x003EAF14, with a jump into its own
cave, and that cave re-executes the displaced `sw $v0, 0x51c($s4)` in a BRANCH
DELAY SLOT -- so it runs on both the single-player and the split-screen path,
and the only register it touches first is `$at`. Our `$v0` reaches the field
either way. The region below is anchored on the two words ENDING at the target
for the same reason: a window reading forwards matches the pristine overlay but
not a disc that already carries the team-panel hook.

Split screen is a separate code path with its own constants (0x003DEE84 and
0x003DEEA0, one per viewport) and is left alone.
"""

from __future__ import annotations

#: The immediate that sets m_iMessageBoxPosY in DrawNativeHUD.
POS_AT = 0x003EAF10
POS_STOCK = 0x24020026          # addiu $v0, $zero, 38

#: `sw $v0, 0x120($sp)` + the target, little-endian. Unique in the pristine
#: overlay AND on a disc that already carries the team-panel hook.
ANCHOR = bytes.fromhex("2001a2af26000224")

#: Measured off the Y=396 screenshot; see MEASURED IN GAME above.
HUD_TOP = 349           # canvas Y of the HUD's top edge
GLYPH_OFFSET = 6        # the glyphs start this far below the field's value
LINE_HEIGHT = 17        # one line of message text
NUDGE = 20              # the conditional += 20 at 0x003eaf40
CLIP_BOTTOM = 480       # the hard clip at 0x003edf58


def lines_clear_of_hud(y: int) -> int:
    """Lines that fit above the HUD at this Y, worst case (the +20 fires)."""
    return max(0, (HUD_TOP - (y + NUDGE + GLYPH_OFFSET)) // LINE_HEIGHT)


def lines_on_screen(y: int) -> int:
    """Lines that fit before the 480 clip, worst case."""
    return max(0, (CLIP_BOTTOM - (y + NUDGE + GLYPH_OFFSET)) // LINE_HEIGHT)


#: choice -> screen Y.
CHOICES = {
    "stock": 38,
    "middle": 240,
    "above_hud": 288,
    "bottom": 396,
}
DEFAULT = "stock"


def word(choice: str) -> int:
    """The replacement instruction for a choice."""
    y = CHOICES[choice]
    if not 0 <= y <= 0xFFFF:
        raise ValueError("message box Y out of range: %d" % y)
    return (POS_STOCK & 0xFFFF0000) | y


def stock_words():
    """{va: stock} for the word this module touches."""
    return {POS_AT: POS_STOCK}


def reads(word_at) -> str:
    """The choice currently on an overlay, given a word reader."""
    y = word_at(POS_AT) & 0xFFFF
    for name, value in CHOICES.items():
        if value == y:
            return name
    return DEFAULT


def card(prefix, group):
    from .model import CHOICE, Choice, Setting

    return Setting(
        prefix + "msg_box_pos", "Where the message box sits", CHOICE,
        DEFAULT, group, confidence="applied", touches="code",
        choices=[
            Choice("stock", "Near the top", "38 pixels down, as it ships."),
            Choice("middle", "Middle of the screen",
                   "240. Well clear of everything, but in the way of what "
                   "you are shooting at."),
            Choice("above_hud", "Just above the HUD",
                   "288 -- measured so that two lines still clear the top "
                   "edge of the HUD. This is the one to use for subtitles."),
            Choice("bottom", "Over the HUD",
                   "396. The lowest it goes, and it does sit on top of the "
                   "weapon and team panels."),
        ],
        help='Objectives, "objective updated", "X has been incapacitated" '
             'and the other boxed messages all share one position, set by a '
             'single instruction in the native HUD renderer.\n\n'
             'The background art and the text move together: the art is '
             'drawn at this Y and the first line of text nine pixels below '
             'it.\n\n'
             'Split screen has its own separate position and is not changed.',
        caution='The box grows DOWNWARD from wherever it is put, so moving '
                'it down trades away room for long messages.\n\n'
                'Measured off a screenshot: the HUD top edge is at 349 and '
                'a line of message text is 17 pixels tall. "Just above the '
                'HUD" is chosen so two lines still fit above it. "Over the '
                'HUD" was played and does overlap the weapon and team '
                'panels -- readable, but cluttered.\n\n'
                'The game also nudges the box down by a further 20 pixels '
                'in some states, and every figure here already allows for '
                'that.')

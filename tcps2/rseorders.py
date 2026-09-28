"""Team orders in split screen: the order wheel on a held X, and the order icon.

In single player, looking at something the team can act on shows its icon at
the bottom of the screen -- bracketed when the order is for the team, plain
when you are close enough to do it yourself -- and holding X opens a wheel of
the orders for it. With `split_squad` giving split screen its AI, tapping X
already hands the team the default order, but neither the icon nor the wheel
appears. They are two separate script gates, both in the split-screen package,
and both are there because retail split screen had no AI to order.

The wheel
---------

`R6CircumstantialActionQuery.Tick` is what opens it, 0.4 s into a hold::

    0x0038: if (bInRange && bCanBeInterrupted)
                PC.m_InteractionCA.PerformCircumstantialAction(0)
    0x0069: else if (!bInRange && iTeamActionIDList[0] != 0
                     && PC.CanIssueTeamOrder() && PC.CanDisplayTeamOrderMenu()
                     && PC.Level.Game.m_bIsSplitScreen == False)    <-- this
    0x0108:     PC.m_InteractionCA.DisplayMenu(True)

The last operand's `False` becomes `True`. This file is only ever loaded in
split screen, so the test now always passes there; everything before it is
single player's own test, and `CanIssueTeamOrder` still refuses a team of one.

The icon
--------

`R6InteractionCircumstantialAction.PostRender` has two drawing arms::

    0x02a0: if (NetMode != 0 || !m_bIsSplitScreen)
              draw the icon; if (!Query.bInRange) bracket it   <-- single player
    0x0509: iPosY = 240 or 480, by m_ViewportIndex               <-- split screen
    0x0533: if (iIcon > -1 && Query.bInRange)                     <-- this
              push full screen, draw the icon at iPosY

`iIcon` is set only for an order the player may give -- a team order needs
`CanIssueTeamOrder()`, a team of more than one -- so `bInRange` restricts the
split arm to the player's own actions. It is swapped for `bHasAction`, which
`iIcon > -1` already implies outside the training map's skip prompt, and the
split arm borrows single player's
brackets from the single-player arm it can never take: that arm's body is
rewritten in place into the brackets, placed at the split arm's own `iPosY`
one pixel inside the background as single player places them.

Measured on the Oil Refinery savestate with the AI: both players' queries hold
`bHasAction` 1, `bInRange` 0, `iTextureIcon` 39 (team-move-to) and the order
list [1, 0, 0, 6] -- the same values single player's Parade savestate holds.
The icon is computed for both players and then not drawn.

The wheel's toggle hints
------------------------

Once open, the wheel shows "R1 clear" and "L1 Zulu" beside it. Those are drawn
by this script after the wheel, at `(ClipY - 80) / 2`, on the viewport's
canvas -- which carries the viewport's size but not its origin (see
`rsewheel`), so player 2's would land in player 1's half. They are now drawn
the way the split arm above draws its icon: push full screen,
`SetStretch(1.0, 448/480)` -- what that arm computes, and the value every
canvas in the savestates holds -- and `SetClip(640, 240 + 480 * m_ViewportIndex)`,
which makes their own `(ClipY - 80) / 2` the middle of the right half. The pop
runs on both ways out.

Like the split arm's own icon, they are drawn once per viewport pass: the
dispatcher at 0x003431d0 runs every viewport's interactions into each
viewport's canvas. Player 2's first copy is painted over by his own view;
player 1's is drawn twice. Only the owner's pass has had its font set by the
wheel; the other draws with whatever the canvas holds. In every savestate
that is the wheel's own `Rainbow6_15pt` object, neither native HUD routine
(0x003e7490, 0x003dbfd0) stores a font, and a pop resets it to the class
default, None, with which
`Canvas.DrawText` (0x0029db30) draws nothing -- so the second copy should
land exactly on the first or not be drawn at all. Gating it on the canvas's
viewport would need two references this function does not make.

Ruled out
---------

* The interactions exist and run for both players: `InitInteractions` creates
  them unconditionally, the savestate holds one per player with its own
  `ViewportOwner`, the tick dispatcher at 0x003438a0 ticks every viewport's
  `LocalInteractions` with no split-screen test, and `KeyEvent` handles the
  action key (0x0000-0x0140) before its one split-screen test (0x0142), which
  guards only voice recording.
* `R6HUD.m_bDisplayActionIcon` is the message box's button prompt, passed to
  0x003e4d70 identically by single player (0x003eaf80) and the split-screen
  HUD (0x003def14). None of the 21 native `m_bIsSplitScreen` sites is on this
  path; the icon is drawn by script.
* The team side has no split-screen test: `TeamActionRequestFromRoseDesVents`
  takes the move point from the controller that asked, and the Zulu go code
  (`ServerSendGoCode`, bound to Joy4) tests only `NetMode`.

What keeps the load in step
---------------------------

Nothing new is named, imported or loaded. Both functions keep their disk
length and `ScriptSize`, and the rewritten `PostRender` references exactly the
same set of objects and names as the shipped one.

The set is not enough. A split-screen `.LIN` is a recording of one load, and
the loader creates -- and then reads from that recording -- a package's own
objects in the order their first references are serialized. So the rewrite
must also first-touch the function's own locals and properties in the shipped
order. The first version of this edit did not: it drew the L1 hint's text,
and tested the R1 hint, from copies placed in single player's icon arm, which
reached `strText` 14 places early and `m_bDisableClear` 6. Oil Refinery's
split-screen load hung on it ("R63rdWeapons.SubSR2: SERIAL SIZE MISMATCH",
2026-09-23), and loaded again once it was off.

This version moves nothing that touches a late object:

* The icon's brackets and the icon itself live in single player's icon arm,
  as before. The one object they touch first is `iPosY`, which is next in the
  shipped order at that point anyway.
* The push before the hints hangs off the wheel's own draw. That statement
  becomes a jump to a copy of itself, then push, stretch and clip, then a jump
  back to the R1 hint's test -- which stays where it shipped. The wheel's draw
  references only `p_canvas`, `R6HUD` and imports.
* The pop after the hints: the L1 hint's text also stays where it shipped. Its
  `58.0` is re-encoded as `float(58)` from a byte -- the way this function
  already writes the same number for the hint's x (0x0F44) -- and the byte
  that saves, with the two of the final `return`, holds a jump to "pop;
  return". The two ways out that skip the menu jumped to that `return` and
  never pushed; they now jump to the function's first `return` (0x0021),
  which is the same statement.

Apart from jumps, the filler that pads each range and that one constant, every
statement in the new code is lifted from the function itself except four: the
two brackets (single player's, with the split arm's Y) and the stretch and
clip calls (calls the function already makes). The rewrite reuses code only
single player reaches: the single-player icon arm and one single-player
progress arm. Each now starts with a jump to where that arm would have
continued, so reaching one out of turn draws nothing rather than running
split-screen code. The result is pinned by a SHA-1, and the suite checks the
creation order package-wide (`run_creation_order`).

Single player cannot change: this is written to `COMMON_SS.LIN` only, which
the engine picks, by `g_bSplitScreen` at 0x001bca70, only for split screen.

Player 1's icon over his own HUD
--------------------------------

Played 2026-09-24: player 2's icon sat behind his team panel, as single
player's does, and player 1's was drawn over his. Each half is a separate
pass -- scene, interactions (`0x003431D0`, called at `0x002F140C`), then the
HUD's `PostRender` -- and that interaction routine runs EVERY viewport's list
into the canvas it is handed. So player 1's icon is drawn again in player 2's
pass, after player 1's HUD. Retail split screen does the same to player 1's
own-action icon and progress circle.

Three words in the routine's loop fix it. They are three reloads of a pointer
`$v0` already holds, so they are free; they become "skip any list that does
not belong to this canvas's viewport" (`canvas + 0x84` is its `Viewport`, and
a viewport's interaction list is at `+0x5C`, which the loop already has in
`$s2`). The skip lands on the loop's increment, past both the allocate and the
free it pairs. Single player has one viewport, whose canvas points back at it,
so nothing changes there. The order and equipment wheels are unaffected:
`rsewheel`'s owner test already limits them to their own pass. Measured over
24 savestates and run in an interpreter over the disc's own code; not yet
played.
"""

from __future__ import annotations

import hashlib
import struct

from .uscode import Script, ScriptError, parse_expr

#: `... CanDisplayTeamOrderMenu() && PC.Level.Game.m_bIsSplitScreen == ` in
#: `R6CircumstantialActionQuery.Tick`; the constant follows, then the two
#: `EndFunctionParms` of `==` and of the `&&`. Unique in all three COMMON files.
TICK_HEAD = bytes.fromhex("1b5b131616182500f2191919007c0a050004018f05000401"
                          "a60600042d01ed01")
TICK_TAIL = bytes.fromhex("1616")
EX_TRUE = 0x27
EX_FALSE = 0x28
#: the constant, measured on this disc. Not used to find anything.
KNOWN_TICK_OFFSET = 0x12E1C0

#: `PostRender`'s ScriptSize word and first two statements, untouched here.
ANCHOR = bytes.fromhex("a91000000723008472010d2a161812007219010d0500040"
                       "17d012a1616040b")
SCRIPT_SIZE = 4265
DISK_LEN = 3271
KNOWN_OFFSET = 0x15BDCD
STOCK_SHA1 = "cabddabffdb5db893ea3e5f97c560052f5716efd"
PATCHED_SHA1 = "a7aa7236521c143685395743ffcd6ea29eaa1b6a"

#: The interaction PostRender loop at 0x003431D0: (va, stock, new, note). The
#: stock word at each is `lw $v0, 0x8c($sp)`, a reload of what $v0 holds.
PASS_WORDS = (
    (0x00343238, 0x8FA2008C, 0x8EC10084,
     "team orders: this pass's viewport (lw $at, 0x84($s6))"),
    (0x00343240, 0x8FA2008C, 0x2421005C,
     "team orders: its interaction list (addiu $at, $at, 0x5c)"),
    (0x00343248, 0x8FA2008C, 0x16410023,
     "team orders: skip the other viewport's list (bne $s2, $at, 0x3432d8)"),
)


def pass_words():
    """[(va, word, stockWord, note)] for build_edits."""
    return [(va, new, stock, note) for va, stock, new, note in PASS_WORDS]


#: The first version, withdrawn after it hung Oil Refinery's load. Recognised
#: only so that a disc still carrying it is named rather than refused blind.
WITHDRAWN_SHA1 = "6919e66dbb819ae7daf9ec74b695973f8208d419"

#: Code only single player reaches, as memory ranges of the shipped function,
#: and the address that code continued at. Each keeps a jump there first.
DEAD = {
    "icon": (0x030A, 0x0509, 0x069C),        # single player's icon arm
    "progress": (0x0A0D, 0x0A7F, 0x0A7F),    # a single-player progress arm
}

#: Shipped statements, by memory offset, that this lifts, replaces or re-aims.
EARLY_RETURN = 0x0021       # the function's first `return;`
NOT_IN_RANGE = 0x039B       # single player's "if (!Query.bInRange)"
ICON_TEST = 0x0533          # iIcon > -1 && Query.bInRange
PUSH_AT = 0x0556            # the split arm's push
ICON_DRAW = 0x0631          # the split arm's icon
POP_AT = 0x0690             # the split arm's pop
MENU_DONE = 0x0C09          # no menu: jump to the final return
MENU_TEST = 0x0C0C          # if (!m_bShowMenu): jump to the final return
WHEEL_DRAW = 0x0CBD         # the wheel itself, drawn just before the hints
CLEAR_TEST = 0x0CEF         # the R1 hint's test
ZULU_TEST = 0x0EDE          # the L1 hint's test, which skips to the return
ZULU_X = 0x0F44             # the L1 hint's x, which writes float(58)
ZULU_TEXT = 0x106C          # the L1 hint's text, last before the return
RETURN_AT = 0x10A7

#: `58.0` in the L1 hint's text, and `float(58)` as ZULU_X already writes it --
#: EX_PrimitiveCast, IntToFloat, EX_IntConstByte 58 -- one byte shorter.
FLOAT_58 = bytes.fromhex("1e00006842")
CAST_58 = bytes.fromhex("393f2c3a")
RETURN_NOTHING = bytes.fromhex("040b")

#: `InstanceVariable(bInRange)` -> `InstanceVariable(bHasAction)` in ICON_TEST
IN_RANGE_REF = bytes.fromhex("01f301")
HAS_ACTION_REF = bytes.fromhex("01f701")

# the four new statements, in the function's own vocabulary
_BORDER = "393a19002f05000101e705"          # int(hudTextures.icons_border)
_Y = ("393f" "9393" "004904" "2c1f" "16"   # float(iPosY - 31 - GetHeight(border))
      "19002f1300046dbf" + _BORDER + "1616")
_ONE = "1e0000803f"
#: DrawTileEx(canvas, border, 640 * 0.5 - 20, Y, 1, 1)
BRACKET_LEFT = bytes.fromhex(
    "19002f5d0000" "6dc3" "003e" + _BORDER
    + "afab1e000020441e0000003f16393f2c1416" + _Y + _ONE + _ONE + "16")
#: DrawTileEx(canvas, border, 640 * 0.5 + 20 - GetWidth(border), Y, 1, 1, 0, True)
BRACKET_RIGHT = bytes.fromhex(
    "19002f830000" "6dc3" "003e" + _BORDER
    + "afaeab1e000020441e0000003f16393f2c1416"
    "393f19002f1300046dbe" + _BORDER + "1616"
    + _Y + _ONE + _ONE + "1e00000000" "27" "16")
#: canvas.SetStretch(1.0, 448 / 480) -- 0x3f6eeeef, bit for bit what the
#: split arm computes after a push, which sets the clip to 640 x 448
SET_STRETCH = bytes.fromhex("19003e100000" "1cce08" "1e0000803f" "1eefee6e3f" "16")
#: canvas.SetClip(640, 240 + 480 * m_Player.m_ViewportIndex)
SET_CLIP = bytes.fromhex("19003e230000" "6a41" "1e00002044"
                         "393f" "92" "2cf0" "90" "1de0010000"
                         "19010d05000401d007" "161616")

#: filler for the unreachable remainder of a rewritten range: EX_Nothing, and
#: two locals this function already names, to make up the memory size
_NOTHING = b"\x0b"
_LOCAL_1 = bytes.fromhex("003e")            # p_canvas: 2 on disk, 5 in memory
_LOCAL_2 = bytes.fromhex("005f05")          # Query:    3 on disk, 5 in memory

EX_JUMP = 0x06
EX_JUMP_IF_NOT = 0x07
#: an `EX_Jump`, 3 bytes on disk and in memory
JUMP_SIZE = 3


class OrdersError(Exception):
    pass


def _jump(target):
    return bytes([EX_JUMP]) + struct.pack("<H", target)


def _fill(disk, mem):
    for ones in range((mem - disk) // 3 + 1):
        rest = mem - disk - 3 * ones
        twos = rest // 2
        used = 2 * ones + 3 * twos
        if rest % 2 == 0 and used <= disk:
            return _LOCAL_1 * ones + _LOCAL_2 * twos + _NOTHING * (disk - used)
    raise OrdersError("no filler makes %d disk bytes %d in memory" % (disk, mem))


def find_block(plain: bytes) -> int:
    """Offset of the ScriptSize word of the circumstantial-action PostRender."""
    at = plain.find(ANCHOR)
    if at < 0:
        raise OrdersError("the action icon's PostRender is not in this file")
    if plain.find(ANCHOR, at + 1) >= 0:
        raise OrdersError("the action icon's PostRender appears more than "
                          "once; refusing to guess which one to change")
    return at


def _find_tick(plain: bytes) -> int:
    at = plain.find(TICK_HEAD)
    if at < 0 or plain.find(TICK_HEAD, at + 1) >= 0:
        raise OrdersError("expected exactly one split-screen test in the "
                          "order wheel's tick")
    const = at + len(TICK_HEAD)
    if (plain[const] not in (EX_TRUE, EX_FALSE)
            or plain[const + 1:const + 3] != TICK_TAIL):
        raise OrdersError("the order wheel's split-screen test is not the "
                          "one this disc shipped")
    return const


def _block_sha1(plain, at):
    return hashlib.sha1(plain[at:at + 4 + DISK_LEN]).hexdigest()


def _rewrite(stock: bytes) -> bytes:
    """The shipped PostRender (ScriptSize word first) -> the rewritten one."""
    script = Script.at(stock, 0)
    stm, d = {}, 4
    for t in script.toks:
        stm[t.mstart] = (d, stock[d:d + t.dlen], t.mlen)
        d += t.dlen

    def span(m0, m1):
        inside = [m for m in stm if m0 <= m < m1]
        disk = sum(len(stm[m][1]) for m in inside)
        mem = sum(stm[m][2] for m in inside)
        if min(inside) != m0 or mem != m1 - m0:
            raise OrdersError("0x%04x-0x%04x is not a run of whole statements"
                              % (m0, m1))
        return stm[m0][0], disk, mem

    def lift(m):
        return stm[m][1], stm[m][2]

    def made(code):
        return code, parse_expr(code).mlen

    if (stm[EARLY_RETURN][1] != RETURN_NOTHING
            or stm[RETURN_AT][1] != RETURN_NOTHING):
        raise OrdersError("the function's returns are not the shipped ones")

    # What each dead range becomes, after the jump to where it used to go:
    # (label, code, memory size). Code that jumps forward is a callable,
    # given the label addresses once the layout is known. Nothing here may
    # touch one of the function's own objects before the shipped code does --
    # see "What keeps the load in step".
    ranges = {
        "icon": [
            ("brackets", lambda L: bytes([EX_JUMP_IF_NOT])
             + struct.pack("<H", L["icon"]) + stm[NOT_IN_RANGE][1][3:],
             stm[NOT_IN_RANGE][2]),
            ("left",) + made(BRACKET_LEFT),
            ("right",) + made(BRACKET_RIGHT),
            ("icon",) + lift(ICON_DRAW),
            ("icon_done", _jump(POP_AT), JUMP_SIZE),
            ("wheel",) + lift(WHEEL_DRAW),
            ("to_push", lambda L: _jump(L["hints_push"]), JUMP_SIZE),
            ("hints_pop",) + lift(POP_AT),
            ("hints_done",) + lift(EARLY_RETURN),
        ],
        "progress": [
            ("hints_push",) + lift(PUSH_AT),
            ("stretch",) + made(SET_STRETCH),
            ("clip",) + made(SET_CLIP),
            ("to_clear", _jump(CLEAR_TEST), JUMP_SIZE),
        ],
    }
    labels = {}
    for name, parts in ranges.items():
        m = DEAD[name][0] + JUMP_SIZE
        for label, _code, size in parts:
            labels[label] = m
            m += size

    out = bytearray(stock)
    for name, parts in ranges.items():
        m0, m1, cont = DEAD[name]
        at, disk, mem = span(m0, m1)
        code = _jump(cont) + b"".join(c if isinstance(c, bytes) else c(labels)
                                      for _l, c, _s in parts)
        used = JUMP_SIZE + sum(size for _l, _c, size in parts)
        out[at:at + disk] = code + _fill(disk - len(code), mem - used)
    for m0, target in ((ICON_DRAW, labels["brackets"]),
                       (WHEEL_DRAW, labels["wheel"])):
        at, disk, mem = span(m0, m0 + stm[m0][2])
        out[at:at + disk] = (_jump(target)
                             + _fill(disk - JUMP_SIZE, mem - JUMP_SIZE))
    # Everything that jumped to the final return. The menu's two ways out
    # never pushed, so they take the first return instead; the L1 hint's
    # test pops on its way out.
    for m0, op, target in ((MENU_DONE, EX_JUMP, EARLY_RETURN),
                           (MENU_TEST, EX_JUMP_IF_NOT, EARLY_RETURN),
                           (ZULU_TEST, EX_JUMP_IF_NOT, labels["hints_pop"])):
        at = stm[m0][0]
        if out[at] != op or out[at + 1:at + 3] != struct.pack("<H", RETURN_AT):
            raise OrdersError("0x%04x is not the shipped jump to the return"
                              % m0)
        out[at + 1:at + 3] = struct.pack("<H", target)
    # The L1 hint's text stays where it shipped; the byte its 58 gives back,
    # with the final return's two, holds the jump to "pop; return".
    at, text = stm[ZULU_TEXT][0], stm[ZULU_TEXT][1]
    if (text.count(FLOAT_58) != 1 or CAST_58 not in stm[ZULU_X][1]
            or stm[RETURN_AT][0] != at + len(text)):
        raise OrdersError("the L1 hint's text is not the shipped one")
    tail = text.replace(FLOAT_58, CAST_58) + _jump(labels["hints_pop"])
    if len(tail) != len(text) + len(RETURN_NOTHING):
        raise OrdersError("the L1 hint's text does not make room for its jump")
    out[at:at + len(tail)] = tail
    at = stm[ICON_TEST][0]
    ref = out.find(IN_RANGE_REF, at, at + len(stm[ICON_TEST][1]))
    if ref < 0:
        raise OrdersError("the split arm's icon test is not the shipped one")
    out[ref:ref + len(IN_RANGE_REF)] = HAS_ACTION_REF
    return bytes(out)


def reads(plain: bytes) -> bool:
    """True if this file already has both edits."""
    try:
        at = find_block(plain)
        const = _find_tick(plain)
    except OrdersError:
        return False
    return (_block_sha1(plain, at) == PATCHED_SHA1
            and plain[const] == EX_TRUE)


def apply(plain: bytes, enable: bool = True):
    """Both edits. Returns (plain, changed). The length never moves."""
    if not enable or reads(plain):
        return plain, 0
    at = find_block(plain)
    const = _find_tick(plain)
    if _block_sha1(plain, at) == WITHDRAWN_SHA1:
        raise OrdersError("this file carries the first team-orders edit, "
                          "withdrawn after it hung Oil Refinery's load; "
                          "restore the disc before applying this one")
    if _block_sha1(plain, at) != STOCK_SHA1 or plain[const] != EX_FALSE:
        raise OrdersError("the order wheel and icon code is not what this "
                          "disc shipped, and not this edit either")
    block = _rewrite(plain[at:at + 4 + DISK_LEN])
    try:
        script = Script.at(block, 0)
    except ScriptError as exc:
        raise OrdersError("the rewritten PostRender does not parse: %s" % exc)
    if (script.mem_len != SCRIPT_SIZE or script.disk_len != DISK_LEN
            or hashlib.sha1(block).hexdigest() != PATCHED_SHA1):
        raise OrdersError("the rewritten PostRender is not the one this was "
                          "checked against")
    out = bytearray(plain)
    out[at:at + len(block)] = block
    out[const] = EX_TRUE
    if len(out) != len(plain):
        raise OrdersError("the orders edit changed the file length")
    return bytes(out), 2


HELP = ("In single player, looking at a door, a ladder or the floor shows the "
        "order you can give there, and holding X opens a wheel of every order "
        "for it. Split screen shows neither, because it shipped with no team "
        "to order. With AI teammates in split screen this turns both on, for "
        "both players: the icon at the bottom of your half, bracketed when "
        "the order is for the team, and the wheel on a held X.")

CAUTION = (
    "Not yet played. Two script gates, both in the split-screen package, so "
    "single player cannot change: the wheel's opener tested "
    "`m_bIsSplitScreen == False`, and the split-screen icon was drawn only "
    "for actions in your own reach. Nothing new is loaded -- every object the "
    "new code touches, the function already touched, and in the same order -- "
    "and both functions keep their size.\n\n"
    "A first version of this option hung Oil Refinery's split-screen load. "
    "It reached two of the function's objects out of their shipped order, "
    "which a split-screen level file cannot follow. This one keeps the "
    "order, and the suite now checks that for every option.\n\n"
    "Needs the equipment wheel's per-viewport fix, because both wheels are "
    "drawn by the same native: without it player 2's order wheel appears in "
    "player 1's half.\n\n"
    "What to watch: the brackets around a team order's icon, and the R1 "
    "clear / L1 Zulu hints beside the wheel, are placed by reckoning, in "
    "each half. Player 1's hints are drawn twice a frame, as split screen "
    "already draws his own-action icon, so they may look a little heavier "
    "than player 2's -- or, if the second copy ever picks up a different "
    "font, doubled. If anything lands wrong, or the HUD misbehaves after a "
    "wheel closes, turn this off first.")


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_team_orders", "Team orders in split screen: icon and wheel",
        BOOL, False, group, confidence="experimental", touches="data",
        requires={prefix + "split_squad": [True],
                  prefix + "split_wheel_labels": [True]},
        help=HELP, caution=CAUTION)

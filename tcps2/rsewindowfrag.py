r"""Where a teammate throws when you point the order wheel at a window.

Order a frag or a flash at bare world geometry and the wheel forwards your aim
point untouched -- no trace, no floor snap, no navigation-point substitution,
no Z adjustment anywhere between your look point and the native ballistic
solver. The sibling plain-move branch in the same function floor-projects with
a 1500-unit downward ray; the grenade branch deliberately does not.

A window is different. The engine treats windows as doors -- an
`R6IORotatingDoor` with `m_bTreatDoorAsWindow` -- so the wheel leaves the
move-to path entirely, assigns a door action, and `R6RainbowAI.PerformAction`
reaches `PerformGrenadeAction`, which **overwrites** the target::

    m_vLocationOnTarget = m_ActionTarget.Location
                        + 450 * vector(m_ActionTarget.Rotation)

Your aim is never consulted. The throw goes to a point 450 units along the
window's own facing direction, which is the one place in the whole order path
where the aim is discarded.

WHAT THIS CHANGES
-----------------

Only the two numbers in that expression: the sign, and the 450. Both sit in a
33-byte run that occurs exactly once in each of the three packages::

    0f 014703  d7  19 0119 0500 0c 018c d5 39 3f  1d C2010000  39 39 ...
       ^ref199  ^+                                   ^IntConst 450

`d7` is `+` and `d8` is `-`; the constant is a plain four-byte little-endian
`EX_IntConst` operand. Neither changes the disk or memory length.

WHICH SIDE IS WHICH
-------------------

Not knowable from the code: it depends on how each window's rotation was
authored in the level, and that varies. A negative distance puts the aim point
on the opposite side of the glass from the stock one, which is what "through
the window" should mean -- but which side stock lands on is a question for one
play test, not for more reading. That is why this ships as a choice rather than
a switch.

The target is a point, not a path. The AI still has to have line of sight and
pass its own range gate (1500 units, measured in `CanThrowGrenade`), and the
native solver at `0x0038D5C0` arcs the throw upward rather than flattening it,
so a low window may still catch the frame.

ALSO WORTH KNOWING
------------------

`R6RainbowTeam.MoveTeamTo` hardcodes `m_iGrenadeThrower = 1`, discarding the
`SelectMemberWithGrenade()` result it computed 300 bytes earlier, so the same
operative always throws. That is a separate edit and is not made here.
"""

from __future__ import annotations

import struct

H = bytes.fromhex


class WindowFragError(Exception):
    pass


#: Offline and split screen; the online package carries the same code but no
#: AI teammates take orders there.
SELECT = r"/COMMON(OFF|_SS)\.LIN$"

#: The whole expression, as it ships. Unique in each package.
_REGION = H("0f014703d719011905000c018cd5393f1dc2010000"
            "3939190119050" "00c019e1616".replace(" ", ""))

#: Byte offsets inside that run.
_OP_AT = 4             # 0xD7 '+'  /  0xD8 '-'
_DIST_AT = 17          # four-byte little-endian EX_IntConst operand
_STOCK_DIST = 450

#: Recorded, not used -- the region is searched for.
KNOWN_AT = 0x136AFC

#: choice -> signed distance along the window's facing direction
CHOICES = {
    "stock": 450,
    "through": -450,
    "through_short": -200,
    "at_window": 0,
    "further": 900,
}
DEFAULT = "stock"


def _prefix(plain: bytes):
    """Locate the run, whatever sign and distance it currently carries."""
    head = _REGION[:_OP_AT]
    at = plain.find(head)
    while at >= 0:
        if plain[at + _OP_AT] in (0xD7, 0xD8):
            tail_at = at + _OP_AT + 1
            if plain[tail_at:tail_at + _DIST_AT - _OP_AT - 1] == \
                    _REGION[_OP_AT + 1:_DIST_AT]:
                nxt = plain.find(head, at + 1)
                if nxt >= 0 and plain[nxt + _OP_AT] in (0xD7, 0xD8):
                    raise WindowFragError("the window throw was found twice")
                return at
        at = plain.find(head, at + 1)
    raise WindowFragError("the window throw expression was not found")


def reads(plain: bytes) -> str:
    """The choice the file currently carries, or 'stock'."""
    try:
        at = _prefix(plain)
    except WindowFragError:
        return DEFAULT
    sign = -1 if plain[at + _OP_AT] == 0xD8 else 1
    dist = struct.unpack_from("<i", plain, at + _DIST_AT)[0] * sign
    for name, value in CHOICES.items():
        if value == dist:
            return name
    return "stock"


def apply(plain: bytes, choice: str = DEFAULT):
    if choice not in CHOICES:
        raise WindowFragError("unknown window-throw choice %r" % choice)
    if reads(plain) == choice:
        return plain, 0
    at = _prefix(plain)
    want = CHOICES[choice]
    out = bytearray(plain)
    out[at + _OP_AT] = 0xD8 if want < 0 else 0xD7
    struct.pack_into("<i", out, at + _DIST_AT, abs(want))
    if len(out) != len(plain):
        raise WindowFragError("the window throw edit changed the file length")
    return bytes(out), 1


def card(prefix, group):
    from .model import CHOICE, Choice, Setting

    return Setting(
        prefix + "frag_window", "Grenades ordered at a window", CHOICE,
        DEFAULT, group, confidence="experimental", touches="data",
        choices=[
            Choice("stock", "Leave it alone",
                   "450 units out along the window's own facing, which is "
                   "what the game does now."),
            Choice("through", "The far side of the window",
                   "The same distance, mirrored -- the opposite side of the "
                   "glass from wherever stock puts it."),
            Choice("through_short", "Just through the window",
                   "Mirrored and closer, 200 units. Use this one if the far "
                   "side overshoots into the next room."),
            Choice("at_window", "At the window itself",
                   "The window's own position, with no offset either way."),
            Choice("further", "Further out", "900 units, double the stock "
                   "distance -- for a window you want cleared from range."),
        ],
        help="Point the order wheel at bare wall or floor and your teammate "
             "throws exactly where you are looking: nothing in that path "
             "moves the point.\n\n"
             "A window is the exception, because the engine treats windows "
             "as doors. Ordering a grenade at one leaves the aim path "
             "entirely and the AI throws at a point 450 units along the "
             "window's own facing direction instead. Your aim is never "
             "consulted, which is why a grenade meant to go through a window "
             "lands on the near side of it.\n\n"
             "This changes that offset. It does not make the window path use "
             "your aim -- that is not reachable without growing the code.",
        caution="Not yet played, and WHICH SIDE is which cannot be read out "
                "of the code: it depends on how each window's rotation was "
                "authored, and that varies by level. Try \"the far side\" "
                "first and reverse to \"further out\" if it goes the wrong "
                "way.\n\n"
                "The target is a point, not a thrown path. The teammate "
                "still needs line of sight and still has to pass the "
                "1500-unit range gate, and the game's throw arcs upward "
                "rather than flat, so a low window can still catch the "
                "frame.")

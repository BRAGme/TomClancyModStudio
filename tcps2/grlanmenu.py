"""Online room screen: L1 moves up the panels, R1 moves down (Jungle Storm, SLUS-20820).

WHAT THE PLAYER SEES
--------------------

In the online room -- the screen with Soldier, Ready, Force Launch, Lock and
the chat -- L1 and R1 move the highlight from one panel to the next. Stock,
L1 moves it *down* (Soldier -> Force Launch -> chat) and R1 moves it *up*.
Every other menu either has no L1/R1 panels at all or only two of them, so
the direction never shows there.

THIS IS STOCK, NOT A MODSTUDIO PATCH
------------------------------------

The pad is read the same way in every menu. `RSInputImpl::MapForUI` (JS
0x0019B1A0) gives L1 keycode 0x13 and R1 keycode 0x14, and
`IkeInputMgr::MapInputForUI` (0x00140010) binds them to messages 0x29D
(Ghost Recon's `kMsgID_UIPadL1Pressed`) and 0x29E (`UIPadR1Pressed`). What a
screen does with those two messages is up to the screen.

The room screens share one base class (vtable 0x005AFC70, derived 0x005B0010
and 0x005B01D0; `ProcessMessage` 0x0030DAF0 calls the dispatch at
0x0030D090). It keeps up to five panels at `this + 0x23C` and the current
one at `this + 0x250`:

    0  +0x22C  Soldier / Ready ...      top left       (everyone)
    1  +0x230  player list              top right      (host only)
    2  --      never used
    3  +0x228  chat                     bottom         (everyone)
    4  +0x238  Force Launch / Lock      left, middle   (host only)

(stored at 0x0030AA10..0x0030AA40; the host starts on panel 4). The dispatch
sends 0x29D (L1) to the handler at 0x0030CD90 and 0x29E (R1) to 0x0030CEF0.
Both handlers are the same 83 words except one: L1 calls the stepper
0x0030CCD0 with a1 = 1, which does index - 1, and R1 with a1 = 0, which
does index + 1 -- skipping empty and hidden panels, wrapping 0 <-> 4. Panel 4 sits under panel 0 on screen, so from Soldier, L1 (index
0 -> 4) goes down to Force Launch and R1 (4 -> 0) comes back up. That is
exactly the report.

None of this was touched: every ModStudio JS module (the user's option set
plus co-op AI, labels, orders, take-over and L3 sprint) was built and not one
word lands in MapForUI, MapInputForUI or 0x0030A000..0x00316000; and in the
two room-screen RAM dumps (host and joiner, taken on the patched disc) all of
those words equal the retail ELF, as does the live keycode table (L1 0x13,
R1 0x14 at RSInputImpl 0x0061E020 + 0x18).

THE FIX
-------

Two words: the dispatch's two `beq`s swap targets, so L1 runs the R1 handler
and R1 the L1 handler. Nothing else changes -- the handlers, the stepper and
the "step back, step forward" focus refresh at 0x0030B02C (which calls both
handlers directly) are left as they are.

Resulting order (host; the joiner has only Soldier and chat, which both
buttons toggle between, as before):

    R1 (down): Soldier -> Force Launch -> chat -> player list -> Soldier
    L1 (up):   Soldier -> player list -> chat -> Force Launch -> Soldier

The left column -- Soldier, Force Launch, chat -- is now L1 up, R1 down. The
host's player list (top right) is where the cycle wraps.

Only the room screens change. The other online screens that read L1/R1 were
checked and left alone: the lobby (0x0032D7F0), login (0x002FE4D0) and the
two-tab list at 0x00311A50 treat both buttons alike or have two tabs; the
on-screen keyboard (0x00319F80) and rankings (0x00326C20) already step
L1 = previous, R1 = next; the four-state screen at 0x0031BB40
(main_menu_ps2.rsb) steps the other way (L1 = next) but its layout was not
established, so it is not changed. Single player's screens mostly toggle two
panels with either button; Quick Mission (0x002D7800) cycles three with
L1 = next index, R1 = previous, and on-screen direction there was not
established.

VERIFIED
--------

* the two stock words and every claim above against the retail SLUS_208.20;
* the game's own ProcessMessage run over the host and joiner room-screen RAM
  dumps (scratchpad agent_menu/emu_tabs.py): stock L1 steps 0 -> 4 -> 3 -> 1
  -> 0, R1 0 -> 1 -> 3 -> 4 -> 0; with these words the two sequences swap.

Not yet played.
"""

from __future__ import annotations

from .model import BOOL, Setting

#: the room screens' L1 / R1 dispatch (inside 0x0030D090)
L1_BEQ = 0x0030D0D8          # beq v1, v0 (0x29D = L1) -> IDX_DEC
R1_BEQ = 0x0030D0E4          # beq v1, v0 (0x29E = R1) -> IDX_INC
#: `jal 0x0030CD90`: stepper with a1 = 1, index - 1 (0 -> 4 -> 3 -> 1): on screen, DOWN the left column
IDX_DEC = 0x0030D92C
#: `jal 0x0030CEF0`: stepper with a1 = 0, index + 1 (0 -> 1 -> 3 -> 4): on screen, UP the left column
IDX_INC = 0x0030D91C

#: (va, stock, new, note)
JS_EDITS = (
    (L1_BEQ, 0x10620214, 0x10620210, "online room: L1 moves up the panels"),
    (R1_BEQ, 0x1062020D, 0x10620211, "online room: R1 moves down the panels"),
)

#: stock words of every word this module may write (read from SLUS_208.20)
JS_STOCK = {va: stock for va, stock, _new, _note in JS_EDITS}


def _beq_v1_v0(at: int, target: int) -> int:
    off = (target - (at + 4)) >> 2
    return 0x10620000 | (off & 0xFFFF)


def edits() -> list:
    """(va, value, stock, note)"""
    return [(va, new, stock, note) for va, stock, new, note in JS_EDITS]


def js_edits(v: dict) -> list:
    return edits() if v.get("js_lan_menu") else []


def cards(prefix: str = "js_", group: str = "Online") -> list:
    return [
        Setting(prefix + "lan_menu", "Online room: L1 moves up, R1 moves down", BOOL, True,
                group, confidence="experimental",
                help="In the online room, L1 and R1 move between the panels -- Soldier and "
                     "Ready, the host's Force Launch and Lock, the chat, the host's player "
                     "list. Stock, L1 moves down the screen and R1 moves up. This swaps "
                     "them. Only the room screens change; every other menu keeps its "
                     "buttons.",
                caution="Not yet played. Checked by running the room screen's own code over "
                        "RAM from the host's and the joiner's room screens, stock and patched. "
                        "The host's player list, top right, is where the cycle wraps."),
    ]


def selftest(js_elf=None) -> list:
    import struct
    fails = []
    for va, stock, new, _n in JS_EDITS:
        if JS_STOCK.get(va) != stock:
            fails.append("%08x: edit stock %08x, table %s" % (va, stock, JS_STOCK.get(va)))
    # stock words branch where the docstring says, new words branch the other way
    for va, want_stock, want_new in ((L1_BEQ, IDX_DEC, IDX_INC), (R1_BEQ, IDX_INC, IDX_DEC)):
        if _beq_v1_v0(va, want_stock) != JS_STOCK[va]:
            fails.append("%08x: stock target is not %08x" % (va, want_stock))
        if _beq_v1_v0(va, want_new) != dict((a, n) for a, _s, n, _ in JS_EDITS)[va]:
            fails.append("%08x: new word does not branch to %08x" % (va, want_new))
    if js_elf is not None:
        for va, want in JS_STOCK.items():
            got = struct.unpack_from("<I", js_elf, va - 0x00100000 + 0x100)[0]
            if got != want:
                fails.append("stock %08x: disc %08x, recorded %08x" % (va, got, want))
        # the two targets: stock L1's calls the index - 1 handler, stock R1's the index + 1 one
        for tgt, jal in ((IDX_DEC, 0x0C0C3364), (IDX_INC, 0x0C0C33BC)):
            got = struct.unpack_from("<I", js_elf, tgt - 0x00100000 + 0x100)[0]
            if got != jal:
                fails.append("%08x: disc %08x, expected jal %08x" % (tgt, got, jal))
    return fails

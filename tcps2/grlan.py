"""Pointing Jungle Storm's ONLINE menu at a lobby server on your own network.

Jungle Storm's online mode is not peer discovery: the console asks Ubi.com where to go, and Ubi.com's
servers are gone. The bootstrap is short enough to redirect with a string.

How the console finds the lobby
-------------------------------

`GSFetchServerList` (VA 0x00531830) turns a name into an address in two tries::

    0x00531860  lui   a0, 0x5a
    0x00531864  jal   0x006d2bd8        ; inet_addr(a0)
    0x00531868  addiu a0, a0, -0x1b70   ; a0 = 0x0059e490, the name field
    0x0053186c  addiu v1, zero, -1
    0x00531870  beq   v0, v1, 0x531890  ; -1 -> not a dotted quad, go and resolve it
    ...
    0x0053189c  jal   0x006d19e8        ; gethostbyname(a0), same a0
    ...
    0x005318e0  jal   0x006971b0        ; htons(a0)
    0x005318e4  addiu a0, zero, 0x50    ; port 80

**`inet_addr` is tried first**, which is the whole trick: write a dotted quad into the name field and
the console connects straight to that address and never asks a DNS server anything. Nothing else in
the bootstrap has to change, and nothing about the emulator's or the router's DNS has to be arranged.

What it then asks for, and what it reads back
---------------------------------------------

Over that connection it sends the request line at 0x0049e5b0 --
``GET /gsinit.php?dp=GHOSTRECONIT_PS2 HTTP/1.1`` with a ``HOST: gsconnect.ubisoft.com`` header -- and
parses the reply as an INI file. Of everything a real Ubi.com directory returned, `GSGetServerAddress`
(VA 0x006ffdc0, one caller, type 0) reads exactly two keys::

    [Servers]
    RouterIP0=<the lobby machine>
    RouterPort0=<its port>

so a stand-in server only has to answer that one GET. The HOST header is left saying
``gsconnect.ubisoft.com``: it is sent, not checked, and a stand-in has no reason to mind.

The name field's room
---------------------

The field at file 0x0049e590 is 32 bytes -- ``gsconnect.ubisoft.com`` and eleven NUL bytes, ending
exactly where the request line begins at 0x0049e5b0. A dotted quad is at most 15 characters, so the
replacement is written over the whole field with NUL fill and nothing is displaced.

What this does not do
---------------------

This is the disc half only. It gets the console to a lobby server of your choosing; the server still
has to speak GameService (login, rooms, begin game). And it needs `js_skip_dnas`: choosing ONLINE
loads Sony's DNAS.BIN first, whose servers are also gone, so without that the bootstrap is never
reached.

Ghost Recon (SLUS-20613) has none of this -- no `gsconnect`, no `gsinit.php`, no bootstrap -- so the
option is Jungle Storm's alone.

AI backup in online co-op
-------------------------

Online co-op gives each human one soldier. The host's roster writer 0x00377180 can fill every fireteam
with AI (routine 0x0037E040, up to three per team), but only when the game's AI Backup flag is set
(GameInfo +0x3C7, getter 0x00148870), and Jungle Storm's lobby never sets it::

    0x00377554  jal   0x148870          ; AI Backup?
    0x00377558  move  a0, v0
    0x0037755c  beqz  v0, skip

The option asks for the lobby type instead (GameInfo +0x2CC, getter 0x001485A0; 2 is co-op), so the
fill runs in every co-op game and in nothing else. The flag itself stays clear: setting it would also
refuse the lobby's respawn option (0x001486C0) and fill the team games. Only the host builds the
roster; played 2026-09-29 on two consoles: Alpha = the joiner and two AI, Bravo = the host and two AI,
Charlie = three AI, the same on both. Online rules still hold -- respawn at the start, no orders, no
SELECT -- and the multiplayer HUD labels the AI "enemy soldier" (see grcooplabel).
"""

from __future__ import annotations

import struct

from .model import BOOL, INT, Setting

#: the name field GSFetchServerList hands to inet_addr, then to gethostbyname
HOST_VA = 0x0059E490
HOST_ROOM = 32
HOST_STOCK = b"gsconnect.ubisoft.com" + b"\x00" * 11

#: `addiu a0, zero, 0x50` -- the port of the GET, the only one the bootstrap hardcodes
PORT_VA = 0x005318E4
PORT_STOCK = 0x24040050

#: the sign-extended immediate keeps a one-instruction patch honest
PORT_MAX = 0x7FFF

_OCTETS = (("1", 192), ("2", 168), ("3", 1), ("4", 10))

#: (va, stock, new, note): the co-op roster fill asks "is this co-op?" instead of "AI Backup?"
COOP_AI = (
    (0x00377554, 0x0C05221C, 0x8C4202CC, "lw v0, 0x2cc(v0): the lobby type"),
    (0x00377558, 0x0040202D, 0x38420002, "xori v0, v0, 2: co-op is 2"),
    (0x0037755C, 0x1040000F, 0x1440000F, "bnez: no fill unless the game is co-op"),
)
JS_STOCK = {va: stock for va, stock, _new, _note in COOP_AI}
# The lobby name and the port belong here too. Re-applying puts back a word an earlier apply wrote only when its
# address is in the profile's stock table (engine.load_pristine); without these, re-patching a disc that already
# points at a lobby was refused -- "0x0059e490 reads 322e3632" -- until it was restored first.
JS_STOCK.update({HOST_VA + 4 * i: w
                 for i, w in enumerate(struct.unpack("<%dI" % (HOST_ROOM // 4), HOST_STOCK))})
JS_STOCK[PORT_VA] = PORT_STOCK


class LanError(Exception):
    pass


def host_words(text: str) -> list:
    """The name field as eight words, `text` NUL-padded to fill it."""
    raw = text.encode("ascii", "strict")
    if len(raw) >= HOST_ROOM:
        raise LanError("%r needs %d bytes; the field holds %d including its NUL"
                       % (text, len(raw) + 1, HOST_ROOM))
    raw = raw + b"\x00" * (HOST_ROOM - len(raw))
    return list(struct.unpack("<%dI" % (HOST_ROOM // 4), raw))


def address(v: dict, prefix: str = "js_") -> str:
    return ".".join(str(int(v.get("%slan_ip%s" % (prefix, n), d))) for n, d in _OCTETS)


def cards(prefix: str = "js_", group: str = "Online") -> list:
    """The option and the address it points at."""
    on = prefix + "lan"
    return [
        Setting(on, "Online: lobby server on your own network", BOOL, False, group,
                confidence="experimental", requires={prefix + "skip_dnas": [True]},
                help="ONLINE asks gsconnect.ubisoft.com for the address of a "
                     "lobby, and those servers are gone. This writes an address "
                     "of your own over that name. The bootstrap tries inet_addr "
                     "before DNS, so a plain address is taken as it stands and "
                     "no name server is consulted -- which is what makes a "
                     "VPN address such as Radmin's work with nothing else set "
                     "up. Set the four numbers below to the machine running the "
                     "lobby server, on every copy that is going to play.",
                caution="Never played. The disc half only: the machine at that "
                        "address has to answer GET /gsinit.php with a [Servers] "
                        "section and then speak Ubi.com's lobby protocol. "
                        "Needs 'skip the DNAS check' as well, or ONLINE never "
                        "gets this far."),
    ] + [
        Setting("%slan_ip%s" % (prefix, n), "Lobby server address, part %s of 4" % n, INT, d,
                group, minimum=0, maximum=255, requires={on: [True]},
                confidence="experimental",
                help="One number of the address, 0 to 255. The default reads "
                     "192.168.1.10; Radmin VPN hands out 26.x.x.x.")
        for n, d in _OCTETS
    ] + [
        Setting(prefix + "lan_port", "Lobby server: directory port", INT, 80, group,
                minimum=1, maximum=PORT_MAX, requires={on: [True]},
                confidence="experimental",
                help="The port the GET /gsinit.php request goes to; the game "
                     "hardcodes 80. Change it only if the server cannot have "
                     "port 80. The lobby's own port is not patched -- the "
                     "server names it itself, as RouterPort0 in the reply."),
        Setting(prefix + "coop_ai", "Online co-op: AI backup fills every fireteam", BOOL, False,
                group, confidence="experimental", requires={prefix + "skip_dnas": [True]},
                help="Online co-op gives each player one soldier. The game can "
                     "fill every fireteam with AI -- its AI Backup option -- but "
                     "Jungle Storm's lobby never turns it on. This fills them in "
                     "every co-op game: your fireteam gets two AI, and a third "
                     "all-AI fireteam comes along. Only the host's disc builds "
                     "the teams; put it on both anyway.",
                caution="Played once on two consoles: the AI appear on both. "
                        "Online rules still apply -- you respawn at the start "
                        "instead of taking over an AI, and orders and SELECT do "
                        "nothing. The HUD calls the AI 'enemy soldier' unless the "
                        "label fix below is on too."),
    ]


def edits(v: dict, prefix: str = "js_") -> list:
    """(va, value, stock, note) for the bootstrap redirect and the co-op AI fill."""
    out = []
    if v.get(prefix + "coop_ai"):
        out += [(va, new, stock, "online co-op AI backup: " + note) for va, stock, new, note in COOP_AI]
    if not v.get(prefix + "lan"):
        return out
    ip = address(v, prefix)
    stock = list(struct.unpack("<%dI" % (HOST_ROOM // 4), HOST_STOCK))
    for i, (word, was) in enumerate(zip(host_words(ip), stock)):
        if word != was:
            out.append((HOST_VA + 4 * i, word, was, "online: the lobby is at %s" % ip))
    port = int(v.get(prefix + "lan_port", 80))
    if not 1 <= port <= PORT_MAX:
        raise LanError("port %d is out of range 1..%d" % (port, PORT_MAX))
    if port != 80:
        out.append((PORT_VA, 0x24040000 | port, PORT_STOCK,
                    "online: ask the lobby's directory on port %d" % port))
    return out

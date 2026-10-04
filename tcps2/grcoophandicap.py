"""Online co-op: the pause menu's HANDICAP item, and the threat indicator (Jungle Storm, SLUS-20820).

WHAT GREYS HANDICAP ONLINE
--------------------------

The pause menu (vtable 0x005AA2E0; its buttons are looked up by name at
0x002A8250.., HANDICAP = "OPTIONSINGAME" at `this + 0x130`) re-decides HANDICAP
every time it opens, at 0x002A5AD8:

    enable HANDICAP
    if IIkeStateMgr::InMultiplayerMode()        (0x006142D0 vt+0x9C) -> grey it
    if IIkeRulesMgr difficulty == 2 (Elite)      (0x00614280 vt+0x178) -> grey it

The multiplayer test is the only one in the whole pause menu, so online it is
greyed in every room and at every difficulty. (vt+0x178 is the value
CheckLineOfSight uses to pick its Recruit / Veteran / Elite factor: 0 / 1 / 2.)

WHAT HANDICAP HOLDS
-------------------

Four bytes of IkeLocalGameInfo -- the per-console object IIkeStateMgr
vt+0x150 hands out (StateMgr + 0x1110), each read by exactly one getter:

    +0x3FD  Auto Targetting        0x0023A150  reticle locks onto a target (0x00238D48 / 0x00238E10)
    +0x3FE  Crosshair Assistance   0x00261D60  reticle helper (0x00261C3C)
    +0x3FF  Threat Indicator       0x0029CEF0  radar ring, 0x0029CE80: an enemy's arc lights (state 1)
    +0x400  Auto Reload            0x002A8BE0  the player's own soldier reloads by himself (0x003B2510)

The menu keeps a copy at `this + 0x109..0x10C`, loads it at 0x002A8A1C and writes
it back at 0x002A9560 (setters 0x002A96C0/B0/A0/90). Nothing else reads the four
bytes, and none of them is put in a network message: they only change what this
console's HUD draws and how this console's own player aims and reloads. The
submenu greys by difficulty (0x002A8B0C): Recruit leaves all four, Veteran greys
Auto Targetting and Crosshair Assistance, Elite never gets that far.

Online, IkeLocalGameInfo is filled once per mission at 0x0013F530 (from the
launch at 0x00207F90, which takes that branch only when InMultiplayerMode):
room byte 0x0062AD22 == 1 -> Threat Indicator and Auto Reload on, the two aim
aids off; any other value -> all four off. Every online co-op RAM dump on hand
(host and joiner) has 0x0062AD22 = 1, difficulty 1 (Veteran) and the four
bytes 0, 0, 1, 1 -- which is why the ring shows threats and cannot be turned
off. The ring's other state (2) -- the flash toward a nearby enemy who fired
an unsilenced weapon, set by the message handler at 0x0029E590 -- does not
read the byte in stock either, in single player or online, and stays.

WHAT THIS MODULE DOES
---------------------

`js_coop_handicap` -- HANDICAP stays available in online CO-OP rooms. The
multiplayer branch now also reads the room type (0x0062AD20: 0 solo, 1 co-op,
2 team -- the room screen's own test at 0x0030DB0C) and only greys when the
room is not co-op, by branching to the Elite rule's grey call. Four words: the
old branch's delay slot and the multiplayer grey call it guarded (0x002A5B00..
0x002A5B0C); the Elite rule is untouched. InMultiplayerMode returns exactly 0 or 1
(`sltu` at 0x004A3B2C / 0x004A3B48), so on that path v0 already holds the 1 to
compare with. Deathmatch and team rooms stay greyed as stock.

In a Veteran co-op room (the user's) the submenu then offers exactly the two
settings the room already hands out -- Threat Indicator and Auto Reload -- with
the aim aids greyed by the stock difficulty rule. In a Recruit co-op room all
four are offered, as in single player; online starts them all off there.

`js_threat_start` -- whether a mission starts with the threat arcs on:

    stock    as shipped
    online   online missions start with it off (0x0013F54C: store 0, not 1)
    all      online and offline both (also the Recruit / Veteran defaults at
             0x0013F4E8 / 0x0013F504); Elite already starts with it off

Either way the HANDICAP menu can switch it back on (offline always, online
with `js_coop_handicap`).

VERIFIED (retail ELF + the game's own code run over RAM, agent_menu/emu_handicap.py)
-------------------------------------------------------------------------------------

* every stock word below against SLUS_208.20;
* the pause menu's enable block run on the online co-op host's RAM
  (ss_menu_02.bin) with the real pause menu (0x01428A60) and the real button:
  stock greys HANDICAP; patched leaves it enabled in a co-op room, still greys
  it in a solo or team room, and still greys it at Elite; offline
  (ss_menu_01.bin, split screen -- InMultiplayerMode is false there, so
  HANDICAP is already available below Elite) behaves as stock;
* the submenu's own load-and-grey code (0x002A8A1C..0x002A8BC8) on the same RAM:
  Veteran -> Threat Indicator and Auto Reload enabled, the aim aids greyed;
  Recruit -> all four enabled;
* toggling Threat Indicator (0x002A94D0) and leaving (0x002A9560): the byte
  goes 1 -> 0 and the next radar update lights no state-1 arc;
* the radar update (0x0029C940) on the same RAM: with the byte at 1 it lights
  segments 5, 7 and 8 (the ones lit in that RAM), with 0 none;
* the online start (0x0013F530) and the offline start (0x0013F4B0) with each
  `js_threat_start` value;
* all 136 JS option builds: no other edit within 0x20 bytes of these words, and
  no other module's stock table names them.

Not yet played.
"""

from __future__ import annotations

from .model import BOOL, CHOICE, Choice, Setting

#: the pause menu's HANDICAP enable block: the multiplayer grey call, rewritten
MENU_EDITS = (
    (0x002A5B00, 0x00000000, 0x3C010063, "lui at, 0x63"),
    (0x002A5B04, 0x8E440130, 0x9023AD20, "lbu v1, room type (0x0062AD20)"),
    (0x002A5B08, 0x0C08014C, 0x1462000A, "bne v1, v0(=1): not a co-op room -> grey"),
    (0x002A5B0C, 0x0000282D, 0x00000000, "nop"),
)
#: the grey call the new branch lands on (lw a0, 0x130(s2) / jal SetEnabled / move a1, zero)
GREY_AT = 0x002A5B34
ELITE_AT = 0x002A5B10

#: IkeLocalGameInfo + 0x3FF (Threat Indicator) stores at mission start
START_ONLINE = ((0x0013F54C, 0xA08303FF, 0xA08003FF, "threat indicator: online missions start off"),)
START_OFFLINE = (
    (0x0013F4E8, 0xA20303FF, 0xA20003FF, "threat indicator: Recruit missions start off"),
    (0x0013F504, 0xA20303FF, 0xA20003FF, "threat indicator: Veteran missions start off"),
)

THREAT_START = ("stock", "online", "all")

#: stock words of every word this module may write (read from SLUS_208.20)
JS_STOCK = {va: stock for va, stock, _new, _n in MENU_EDITS + START_ONLINE + START_OFFLINE}


def edits(handicap: bool = True, threat_start: str = "stock") -> list:
    """(va, value, stock, note)"""
    if threat_start not in THREAT_START:
        raise ValueError("threat_start must be one of %s" % (THREAT_START,))
    rows = []
    if handicap:
        rows += [(va, new, stock, "online co-op HANDICAP: " + n) for va, stock, new, n in MENU_EDITS]
    if threat_start in ("online", "all"):
        rows += [(va, new, stock, n) for va, stock, new, n in START_ONLINE]
    if threat_start == "all":
        rows += [(va, new, stock, n) for va, stock, new, n in START_OFFLINE]
    return rows


def js_edits(v: dict) -> list:
    return edits(bool(v.get("js_coop_handicap")), v.get("js_threat_start", "stock") or "stock")


def cards(prefix: str = "js_", group: str = "Online") -> list:
    return [
        Setting(prefix + "coop_handicap", "Online co-op: HANDICAP in the pause menu", BOOL, False,
                group, confidence="experimental",
                help="Online, the pause menu greys out HANDICAP in every room. This keeps it "
                     "available in co-op rooms, so each player can turn the threat indicator "
                     "(the arcs on the radar ring) and auto reload on or off for himself. "
                     "The settings are this console's own: they change what your HUD shows and "
                     "how your own soldier reloads, and are never sent to the other player. The "
                     "game's difficulty rules still apply -- on Veteran the two aim aids stay "
                     "greyed, on Elite HANDICAP stays greyed. Deathmatch and team rooms are "
                     "unchanged.",
                caution="Not yet played. Checked by running the pause menu's own code over RAM "
                        "from an online co-op mission. The flash toward an enemy who fires "
                        "nearby is not part of the setting and stays, as in single player."),
        Setting(prefix + "threat_start", "Threat indicator at the start of a mission", CHOICE,
                "stock", group, confidence="experimental",
                choices=[
                    Choice("stock", "As shipped",
                           "Online co-op starts with it on; offline, Recruit and Veteran start "
                           "with it on and Elite with it off."),
                    Choice("online", "Off online",
                           "Online missions start with the arcs off. Offline is unchanged."),
                    Choice("all", "Off everywhere",
                           "Every mission starts with the arcs off, online and offline."),
                ],
                help="The threat indicator lights an arc of the radar ring toward enemies near "
                     "you. This only changes how a mission starts; HANDICAP in the pause menu "
                     "can turn it back on (online only with the option above).",
                caution="Not yet played. Checked by running the game's mission-start code over "
                        "RAM from an online co-op mission."),
    ]


def selftest(js_elf=None) -> list:
    import struct
    fails = []
    for va, _w, s, _n in edits(True, "all"):
        if JS_STOCK.get(va) != s:
            fails.append("%08x: edit stock %08x, table %s" % (va, s, JS_STOCK.get(va)))
    # the new branch lands on the stock grey call; the old one on the Elite rule
    bne = dict((va, new) for va, _s, new, _n in MENU_EDITS)[0x002A5B08]
    if 0x002A5B0C + ((bne & 0xFFFF) << 2) != GREY_AT:
        fails.append("HANDICAP branch does not land on the grey call")
    if js_elf is not None:
        def word(va):
            return struct.unpack_from("<I", js_elf, va - 0x00100000 + 0x100)[0]
        for va, want in JS_STOCK.items():
            if word(va) != want:
                fails.append("stock %08x: disc %08x, recorded %08x" % (va, word(va), want))
        context = {0x002A5AFC: 0x10400004,              # beqz v0, ELITE_AT (kept)
                   ELITE_AT: 0x0C049184,                # jal IIkeRulesMgr::Get
                   GREY_AT: 0x8E440130,                 # lw a0, 0x130(s2)
                   GREY_AT + 4: 0x0C08014C,             # jal SetEnabled
                   GREY_AT + 8: 0x0000282D}             # move a1, zero
        for va, want in context.items():
            if word(va) != want:
                fails.append("context %08x: disc %08x, expected %08x" % (va, word(va), want))
    return fails

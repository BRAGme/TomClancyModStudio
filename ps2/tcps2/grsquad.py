"""AI fireteams for Ghost Recon's split screen.

Single player gives you a squad of named Ghosts. Split screen gives each
player one nameless soldier and nothing else. This puts two named AI
soldiers into each player's fireteam.

Why split screen has nobody
---------------------------

Both modes build the mission's roster the same way: a menu screen writes an
``avatar.toe`` order of battle and the simulation loads it. Single player's
writer (``SPSoldierSelect::CreateTOEFile``) emits up to six named Ghosts in
Alpha, Bravo and Charlie. Split screen's
(``PS2MultiplayerSplitScreenChooseSoldier::CreateTOEFile``, 0x003358A0) runs
its actor loop exactly twice and names the two soldiers ``1P`` and ``2P``
from multiplayer class files. Measured in a Jungle Storm split-screen
savestate: 35 enemies, ``1P`` and ``2P``, and no one else.

Three facts make adding soldiers safe:

* **Player 2 is chosen by name.** ``IkeSimulationMgr::HandleGameObjectCreated``
  (0x0038F3D0) hands a new, locally owned, not-AI soldier to player 2 when its
  name is ``2P`` and to player 1 otherwise.
* **``Owner = -1`` means AI.** ``CreateHuman`` (0x0038A750) sends
  ``Owner != -1`` as the "player controlled" flag, so an entry left at -1 is
  created AI-controlled and never claims either player's controller.
  Single player's writer leaves every Ghost at -1 for the same reason.
* **A soldier is its ``.ATR``.** Name, face, class and model all come from the
  actor file (``rifleman-39.atr`` says *Jeremy Wong*), so pointing an entry at
  a campaign roster file is all it takes to make it a named Ghost.

The patch
---------

One jump at 0x00335FF8, where the actor loop has just finished and before the
two member lists are copied into the Alpha and Bravo team entries, into a cave
that for each extra soldier: grows the actor array, copies player 1's entry
(so every string member is a live object), gives it the next IgorId, sets its
name, ``.atr`` and ``.kit``, sets ``Owner = -1``, and appends the id to that
player's team. A player who is not in the game gets no soldiers.

The cave lives in ``lzo1x_decompress_safe`` (0x00430518, 1,364 bytes): no call
to it, no pointer to it, and no address formed for it anywhere in the image.
The game uses the other decompressor.
"""

from __future__ import annotations

import struct

from .grasm import assemble

# ---------------------------------------------------------------------------
# Ghost Recon (SLUS-20613)
# ---------------------------------------------------------------------------

GR_HOOK = 0x00335FF8            # lw s1,0xc8(sp) after the actor loop
GR_HOOK_STOCK = 0x8FB100C8
GR_RESUME = 0x00336000
GR_CAVE = 0x00430518            # lzo1x_decompress_safe, unreferenced
GR_CAVE_BYTES = 1364

GR_SYMS = {
    "IncActors": 0x001EDC70,    # IncreaseToSize_Array__30RSArray<19SetupFileActorEntry>Fi
    "CopyEntry": 0x001E5E70,    # __as__19SetupFileActorEntryFRC19SetupFileActorEntry
    "StrSetC": 0x0053EA60,      # __as__8RSStringFPCc
    "FnCtorC": 0x0053D4F0,      # __ct__10RSFilenameFPCc
    "FnAssign": 0x0053D3E0,     # __as__10RSFilenameFRC10RSFilename
    "FnDtor": 0x0053D380,       # __dt__10RSFilenameFv
    "IncUi": 0x001343F0,        # IncreaseToSize_Array__11RSArray<Ui>Fi
}

#: (player, entry name, actor file, kit) -- mission 1's own squad from M01.TOE,
#: split between the two fireteams. Every file is on the disc in GR.IMG.
GR_SQUAD = (
    (0, "_Vernon Jefferson", "rifleman-04.atr", "rifleman-01.kit"),
    (0, "_Jon Snyder", "heavy-weapons-30.atr", "heavy-weapons-01.kit"),
    (1, "_Horace Dominguez", "rifleman-48.atr", "rifleman-01.kit"),
    (1, "_Robbie Chukitus", "heavy-weapons-20.atr", "heavy-weapons-01.kit"),
)

#: SetupFileActorEntry, recovered from SetupFileData::ProcessTeamMembers
ENTRY_SIZE = 0x5C               # +0x04 IgorId, +0x0C name, +0x14 atr, +0x20 kit,
                                # +0x50 Hidden, +0x51 CampaignLoad, +0x54 Owner,
                                # +0x58 PlatoonLeader

#: CreateTOEFile's frame at the hook: the two team member lists (RSArray<Ui>,
#: +0 data, +4 count) that are copied into the Alpha and Bravo entries next.
TEAM_LIST = (0x164, 0x194)
SELECTION = 0x15C               # this->selection[player]; -1 = player absent

FRAME = 0x70


def gr_roster_source(squad=GR_SQUAD):
    n = len(squad)
    src = f"""
cave:
    addiu sp, sp, -{FRAME}
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s3, 0x20(sp)
    sq    s4, 0x30(sp)
    sq    s6, 0x40(sp)              ; 0x50..0x5f: a temporary RSFilename
    move  s6, zero                  ; k = soldier index
loop:
    sll   t0, s6, 4                 ; s4 = &table[k] = {{player, name, atr, kit}}
    lui   t1, %hi(table)
    addiu t1, t1, %lo(table)
    addu  s4, t1, t0
    lw    v0, 0(s4)
    sll   v0, v0, 2
    addu  v0, s5, v0
    lw    v1, {SELECTION:#x}(v0)            ; that player's selection
    li    v0, -1
    beq   v1, v0, next              ; player not in the game
    nop
    lw    s3, 0x10(s2)              ; n = actors.count
    addiu a0, s2, 0xc
    jal   IncActors
    addiu a1, s3, 1
    lw    v0, 0xc(s2)               ; actors.data, re-read: the array moved
    sll   t0, s3, 4                 ; n * 0x5c = ((n<<4) + (n<<3) - n) << 2
    sll   t1, s3, 3
    addu  t0, t0, t1
    subu  t0, t0, s3
    sll   t0, t0, 2
    addu  s1, v0, t0                ; s1 = the new entry
    move  a0, s1
    jal   CopyEntry                 ; start from player 1's entry
    move  a1, v0
    lw    v0, 4(s2)                 ; IgorId = setup->nextId++
    addiu v1, v0, 1
    sw    v1, 4(s2)
    sw    v0, 4(s1)
    move  s0, v0
    addiu a0, s1, 0xc               ; name
    jal   StrSetC
    lw    a1, 4(s4)
    addiu a0, sp, 0x50              ; actor file
    jal   FnCtorC
    lw    a1, 8(s4)
    addiu a0, s1, 0x14
    jal   FnAssign
    addiu a1, sp, 0x50
    addiu a0, sp, 0x50
    jal   FnDtor
    li    a1, -1
    addiu a0, sp, 0x50              ; kit
    jal   FnCtorC
    lw    a1, 12(s4)
    addiu a0, s1, 0x20
    jal   FnAssign
    addiu a1, sp, 0x50
    addiu a0, sp, 0x50
    jal   FnDtor
    li    a1, -1
    li    v0, -1
    sw    v0, 0x54(s1)              ; Owner -1: created AI-controlled
    sb    zero, 0x58(s1)            ; not the platoon leader
    lw    v0, 0(s4)
    li    t0, {TEAM_LIST[0] + FRAME:#x}
    beqz  v0, gotlist
    nop
    li    t0, {TEAM_LIST[1] + FRAME:#x}
gotlist:
    addu  s3, sp, t0                ; that player's member list
    lw    s4, 4(s3)
    move  a0, s3
    jal   IncUi
    addiu a1, s4, 1
    lw    v0, 0(s3)
    sll   v1, s4, 2
    addu  v0, v0, v1
    sw    s0, 0(v0)                 ; members[count] = IgorId
next:
    addiu s6, s6, 1
    slti  v0, s6, {n}
    bnez  v0, loop
    nop
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s3, 0x20(sp)
    lq    s4, 0x30(sp)
    lq    s6, 0x40(sp)
    addiu sp, sp, {FRAME}
    lw    s1, 0xc8(sp)              ; the instruction the hook replaced
    j     {GR_RESUME:#x}
    nop
table:
"""
    for i in range(n):
        src += f"    .word {squad[i][0]}\n    .word n{i}\n    .word a{i}\n    .word k{i}\n"
    for i, (_p, name, atr, kit) in enumerate(squad):
        src += f'n{i}: .asciiz "{name}"\na{i}: .asciiz "{atr}"\nk{i}: .asciiz "{kit}"\n'
    return src


def gr_roster_words(squad=GR_SQUAD):
    words, _labels = assemble(gr_roster_source(squad), GR_CAVE, GR_SYMS)
    if len(words) * 4 > GR_CAVE_BYTES:
        raise ValueError("roster cave is %d bytes, room for %d"
                         % (len(words) * 4, GR_CAVE_BYTES))
    return words


#: The cave region as shipped, one word per line of eight. Every word the
#: tool may write must have its stock value on record so the engine can
#: rebuild the pristine executable; `selftest` checks this against the disc.
_GR_CAVE_STOCK_HEX = (
    "27BDFF60 FFBE0080 FFB70070 00E0F02D FFB60060 FFB50050 00C0B02D FFB30030"
    "0085A821 FFB10010 02C0982D FFBF0090 0080882D FFB40040 FFB20020 FFB00000"
    "8FC30000 AFC00000 92220000 2C420012 14400113 02C3B821 92300000 2612FFEF"
    "2E420004 144000F1 26310001 16400008 02F61023 3C040059 3C060059 24849208"
    "24C69528 0C0FFEB6 240509CE 02F61023 0052102B 1440011E 02761823 2603FFF0"
    "02B11023 0043102B 14400116 02761823 92220000 2652FFFF 26310001 A2620000"
    "00000000 1640FFFA 26730001 10000038 92320000 00000000 2E420010 1040004A"
    "26310001 16400016 02F31023 10000003 00000000 00000000 26310001 12B10101"
    "02761823 92220000 5040FFFB 265200FF 92230000 2642000F 00439021 16400007"
    "26310001 3C040059 3C060059 24849208 24C69528 0C0FFEB6 240509E3 02F31023"
    "26430003 0043102B 144000F0 02B11023 26430004 0043102B 144000EA 02761823"
    "92220000 26310001 A2620000 26730001 92220000 26310001 A2620000 26730001"
    "92220000 26310001 A2620000 26730001 92220000 2652FFFF 26310001 A2620000"
    "00000000 1640FFFA 26730001 92320000 2E420010 10400014 26310001 92220000"
    "00121882 2670F7FF 02038023 00021080 02028023 0216182B 146000CF 26310001"
    "02F31023 2C420003 144000C8 26238000 92020000 26100001 A2620000 26730001"
    "10000060 92020000 2E420040 14400018 2E420020 00121082 92230000 30420007"
    "2670FFFF 02028023 000318C0 02038023 0012A142 26310001 0216102B 144000B6"
    "2692FFFF 16400008 26830001 3C040059 3C060059 24849208 24C69528 0C0FFEB6"
    "24050A55 26830001 10000059 02F31023 5440001A 2E420010 3252001F 5640000F"
    "92220000 10000003 00000000 00000000 26310001 12B1009B 02761823 92220000"
    "5040FFFB 265200FF 92230000 2642001F 26310001 00439021 92220000 2670FFFF"
    "92230001 00021082 26310002 00031980 00431021 10000031 02028023 5440001C"
    "92220000 32420008 000212C0 32520007 1640000D 02628023 10000002 00000000"
    "26310001 12B1007F 02761823 92220000 5040FFFB 265200FF 92230000 26420007"
    "26310001 00439021 92220000 92230001 00021082 00031980 00431021 02028023"
    "1213005D 26310002 10000014 2610C000 00121882 2670FFFF 02038023 00021080"
    "02028023 0216182B 1460006B 26310001 02F31023 2C420002 14400064 26238000"
    "92020000 A2620000 26730001 92020001 A2620000 10000021 26730001 0216102B"
    "1440005E 02761823 16400008 02F31023 3C040059 3C060059 24849208 24C69528"
    "0C0FFEB6 24050AD3 02F31023 26430002 0043102B 1440004D 26238000 92020000"
    "26100001 A2620000 26730001 92020000 26100001 A2620000 26730001 00000000"
    "92020000 2652FFFF 26100001 A2620000 00000000 1640FFFA 26730001 90627FFE"
    "30520003 1240001F 0235102B 16400008 02F31023 3C040059 3C060059 24849208"
    "24C69528 0C0FFEB6 24050AF9 02F31023 0052102B 1440002D 02B11023 26430001"
    "0043102B 14400027 02761823 00000000 92220000 2652FFFF 26310001 A2620000"
    "00000000 1640FFFA 26730001 92320000 26310001 0235102B 1440FF5C 2E420040"
    "0235102B 5440FF0C 92320000 02761823 1000001B 2402FFF9 24020001 12420006"
    "3C040059 3C060059 24849208 24C69530 0C0FFEB6 24050B05 02761023 12350006"
    "AFC20000 0235182B 2405FFFC 2402FFF8 10000002 0043280B 0000282D 10000009"
    "00A0102D 10000006 2402FFFC 02761823 10000003 2402FFFB 02761823 2402FFFA"
    "AFC30000 DFBF0090 DFBE0080 DFB70070 DFB60060 DFB50050 DFB40040 DFB30030"
    "DFB20020 DFB10010 DFB00000 03E00008 27BD00A0"
)


def _stock_words(base, hexwords):
    # adjacent string literals join with no separator, so read fixed 8-digit
    # words rather than splitting on spaces
    digits = "".join(hexwords.split())
    if len(digits) % 8:
        raise ValueError("stock table is not a whole number of words")
    words = [int(digits[i:i + 8], 16) for i in range(0, len(digits), 8)]
    return {base + 4 * i: w for i, w in enumerate(words)}


#: every word grsquad may write in Ghost Recon, at its shipped value
GR_STOCK = _stock_words(GR_CAVE, _GR_CAVE_STOCK_HEX)
GR_STOCK[GR_HOOK] = GR_HOOK_STOCK

_JS_CAVE_STOCK_HEX = (
    "27BDFF60 FFBE0080 FFB70070 00E0F02D FFB60060 FFB50050 00C0B02D FFB30030"
    "0085A821 FFB10010 02C0982D FFBF0090 0080882D FFB40040 FFB20020 FFB00000"
    "8FC30000 AFC00000 92220000 2C420012 14400113 02C3B821 92300000 2612FFEF"
    "2E420004 144000F1 26310001 16400008 02F61023 3C040058 3C060058 24842F90"
    "24C632B0 0C05986E 240509CE 02F61023 0052102B 1440011E 02761823 2603FFF0"
    "02B11023 0043102B 14400116 02761823 92220000 2652FFFF 26310001 A2620000"
    "00000000 1640FFFA 26730001 10000038 92320000 00000000 2E420010 1040004A"
    "26310001 16400016 02F31023 10000003 00000000 00000000 26310001 12B10101"
    "02761823 92220000 5040FFFB 265200FF 92230000 2642000F 00439021 16400007"
    "26310001 3C040058 3C060058 24842F90 24C632B0 0C05986E 240509E3 02F31023"
    "26430003 0043102B 144000F0 02B11023 26430004 0043102B 144000EA 02761823"
    "92220000 26310001 A2620000 26730001 92220000 26310001 A2620000 26730001"
    "92220000 26310001 A2620000 26730001 92220000 2652FFFF 26310001 A2620000"
    "00000000 1640FFFA 26730001 92320000 2E420010 10400014 26310001 92220000"
    "00121882 2670F7FF 02038023 00021080 02028023 0216182B 146000CF 26310001"
    "02F31023 2C420003 144000C8 26238000 92020000 26100001 A2620000 26730001"
    "10000060 92020000 2E420040 14400018 2E420020 00121082 92230000 30420007"
    "2670FFFF 02028023 000318C0 02038023 0012A142 26310001 0216102B 144000B6"
    "2692FFFF 16400008 26830001 3C040058 3C060058 24842F90 24C632B0 0C05986E"
    "24050A55 26830001 10000059 02F31023 5440001A 2E420010 3252001F 5640000F"
    "92220000 10000003 00000000 00000000 26310001 12B1009B 02761823 92220000"
    "5040FFFB 265200FF 92230000 2642001F 26310001 00439021 92220000 2670FFFF"
    "92230001 00021082 26310002 00031980 00431021 10000031 02028023 5440001C"
    "92220000 32420008 000212C0 32520007 1640000D 02628023 10000002 00000000"
    "26310001 12B1007F 02761823 92220000 5040FFFB 265200FF 92230000 26420007"
    "26310001 00439021 92220000 92230001 00021082 00031980 00431021 02028023"
    "1213005D 26310002 10000014 2610C000 00121882 2670FFFF 02038023 00021080"
    "02028023 0216182B 1460006B 26310001 02F31023 2C420002 14400064 26238000"
    "92020000 A2620000 26730001 92020001 A2620000 10000021 26730001 0216102B"
    "1440005E 02761823 16400008 02F31023 3C040058 3C060058 24842F90 24C632B0"
    "0C05986E 24050AD3 02F31023 26430002 0043102B 1440004D 26238000 92020000"
    "26100001 A2620000 26730001 92020000 26100001 A2620000 26730001 00000000"
    "92020000 2652FFFF 26100001 A2620000 00000000 1640FFFA 26730001 90627FFE"
    "30520003 1240001F 0235102B 16400008 02F31023 3C040058 3C060058 24842F90"
    "24C632B0 0C05986E 24050AF9 02F31023 0052102B 1440002D 02B11023 26430001"
    "0043102B 14400027 02761823 00000000 92220000 2652FFFF 26310001 A2620000"
    "00000000 1640FFFA 26730001 92320000 26310001 0235102B 1440FF5C 2E420040"
    "0235102B 5440FF0C 92320000 02761823 1000001B 2402FFF9 24020001 12420006"
    "3C040058 3C060058 24842F90 24C632B8 0C05986E 24050B05 02761023 12350006"
    "AFC20000 0235182B 2405FFFC 2402FFF8 10000002 0043280B 0000282D 10000009"
    "00A0102D 10000006 2402FFFC 02761823 10000003 2402FFFB 02761823 2402FFFA"
    "AFC30000 DFBF0090 DFBE0080 DFB70070 DFB60060 DFB50050 DFB40040 DFB30030"
    "DFB20020 DFB10010 DFB00000 03E00008 27BD00A0"
)



# ---------------------------------------------------------------------------
# Jungle Storm (SLUS-20820) -- stripped, same engine, restructured writer
# ---------------------------------------------------------------------------
#
# Jungle Storm's writer (0x002E1FE0) builds each soldier in a stack entry and
# hands a copy to SetupFileData through accessors, so its cave does the same.
# Every helper below was identified at its call site inside that writer, and
# the entry layout is Ghost Recon's (id +0x04, name +0x0C, atr +0x14, kit
# +0x20, Owner +0x54), read off the same stores.

JS_HOOK = 0x002E2330            # jal 0x1e1800, first call after the actor loop
JS_HOOK_STOCK = 0x0C078600
JS_HOOK_TARGET = 0x001E1800     # re-called by the cave with the same arguments
JS_CAVE = 0x001996A0            # lzo1x_decompress_safe again: 329 of its 341
                                # words match Ghost Recon's, nothing refers to it
JS_CAVE_BYTES = 1364

JS_SYMS = {
    "EntryCtor": 0x001D9310,    # SetupFileActorEntry::SetupFileActorEntry (Owner -1)
    "EntryDtor": 0x001D7050,
    "NextId": 0x002C8060,       # SetupFileData: return nextId++
    "AddActor": 0x002C8050,     # SetupFileData: actors.push_back(copy)
    "StrSetC": 0x003FF4A0,      # RSString = const char*
    "FnCtorC": 0x003FD950,      # RSFilename(const char*)
    "FnAssign": 0x003FDA40,     # RSFilename = RSFilename
    "FnDtor": 0x003FDAA0,
    "ResizeUi": 0x002C8FB0,     # RSArray<Ui>::ChangeSize, keeps min(old,new)
}

#: every word grsquad may write in Jungle Storm, at its shipped value
JS_STOCK = _stock_words(JS_CAVE, _JS_CAVE_STOCK_HEX)
JS_STOCK[JS_HOOK] = JS_HOOK_STOCK

JS_SELECTION = 0x1D0            # this->selection[player]
JS_TEAM_LIST = (0x144, 0x114)   # member lists in the writer's frame
JS_FRAME = 0xD0                 # 0x00 saves, 0x50 ra, 0x60 temp, 0x70 entry


def js_roster_source(squad=GR_SQUAD):
    n = len(squad)
    F = JS_FRAME
    src = f"""
cave:
    addiu sp, sp, -{F:#x}
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s4, 0x20(sp)
    sq    s6, 0x30(sp)
    sd    ra, 0x50(sp)
    move  s6, zero
loop:
    sll   t0, s6, 4
    lui   t1, %hi(table)
    addiu t1, t1, %lo(table)
    addu  s4, t1, t0                ; s4 = &table[k]
    lw    v0, 0(s4)
    sll   v0, v0, 2
    addu  v0, s5, v0
    lw    v1, {JS_SELECTION:#x}(v0)
    li    v0, -1
    beq   v1, v0, next
    nop
    jal   EntryCtor
    addiu a0, sp, 0x70
    jal   NextId
    move  a0, s3
    sw    v0, 0x74(sp)              ; IgorId
    move  s0, v0
    addiu a0, sp, 0x7c              ; name
    jal   StrSetC
    lw    a1, 4(s4)
    addiu a0, sp, 0x60              ; actor file
    jal   FnCtorC
    lw    a1, 8(s4)
    addiu a0, sp, 0x84
    jal   FnAssign
    addiu a1, sp, 0x60
    addiu a0, sp, 0x60
    jal   FnDtor
    li    a1, -1
    addiu a0, sp, 0x60              ; kit
    jal   FnCtorC
    lw    a1, 12(s4)
    addiu a0, sp, 0x90
    jal   FnAssign
    addiu a1, sp, 0x60
    addiu a0, sp, 0x60
    jal   FnDtor
    li    a1, -1
    move  a0, s3                    ; Owner stays -1 from the constructor
    jal   AddActor
    addiu a1, sp, 0x70
    lw    v0, 0(s4)
    li    t0, {JS_TEAM_LIST[0] + F:#x}
    beqz  v0, gotlist
    nop
    li    t0, {JS_TEAM_LIST[1] + F:#x}
gotlist:
    addu  s4, sp, t0                ; that player's member list
    lw    s1, 4(s4)
    move  a0, s4
    jal   ResizeUi
    addiu a1, s1, 1
    lw    v0, 0(s4)
    sll   v1, s1, 2
    addu  v0, v0, v1
    sw    s0, 0(v0)                 ; members[count] = IgorId
    addiu a0, sp, 0x70
    jal   EntryDtor
    li    a1, -1
next:
    addiu s6, s6, 1
    slti  v0, s6, {n}
    bnez  v0, loop
    nop
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s4, 0x20(sp)
    lq    s6, 0x30(sp)
    ld    ra, 0x50(sp)
    addiu sp, sp, {F:#x}
    addiu a1, sp, 0x184             ; the replaced call, same arguments
    j     {JS_HOOK_TARGET:#x}
    addiu a0, sp, 0x1e4
table:
"""
    for i in range(n):
        src += f"    .word {squad[i][0]}\n    .word n{i}\n    .word a{i}\n    .word k{i}\n"
    for i, (_p, name, atr, kit) in enumerate(squad):
        src += f'n{i}: .asciiz "{name}"\na{i}: .asciiz "{atr}"\nk{i}: .asciiz "{kit}"\n'
    return src


def js_roster_words(squad=GR_SQUAD):
    words, _labels = assemble(js_roster_source(squad), JS_CAVE, JS_SYMS)
    if len(words) * 4 > JS_CAVE_BYTES:
        raise ValueError("roster cave is %d bytes, room for %d"
                         % (len(words) * 4, JS_CAVE_BYTES))
    return words


# ---------------------------------------------------------------------------
# One life: take over a living teammate instead of respawning
# ---------------------------------------------------------------------------
#
# Split screen already runs single player's death handoff and bails one
# branch early. On death SimHuman::UpdateAutoResPawn waits, then sends
# FollowNextTeamMember (0x21); HandleFollowNextTeamMember calls
# CheckForRespawn and then, in split screen only, returns
# (GR 0x0039673C bnez). Single player carries on into FindNextTeamMember and
# SwitchFollowActor -> RequestControlAvatar (0x19) -> AssignControlAvatar
# (0x1A) -> LocalControlAvatar (0x1B, pad 1) / LocalControlAvatar2 (0x1C,
# pad 2). Six changes let split screen finish the job:
#
#   B1  the split-screen return jumps to a cave that searches the dead
#       soldier's own fireteam for a living AI soldier and switches to him
#   B2  FindNextTeamMember starts from the caller's soldier (the dead one)
#       instead of camera 1's leader -- identical in single player, where the
#       caller passed camera 1's leader
#   B3  its cross-fireteam pass is skipped when the caller passes 2 (the
#       cave does); single player passes 0 or 1. The old "fewer than two
#       teams" guard it replaces is redundant: the loop wraps to its own
#       team and stops at once
#   B4  AssignControlAvatar sends 0x1C when the new soldier OR the valid old
#       soldier is player 2's avatar -- stock only checked the new one, so
#       player 2's handoff would have gone to pad 1
#   B5  the split-screen RequestControlAvatar skips its display-name
#       payload, which the next step reads one item past its end
#   B6' CanRespawn answers no in split screen, whatever the lobby said
#   B7  SimHuman::UpdateAutoResPawn sends the 0x21 in split screen whatever
#       the lobby's respawn setting. Stock split screen sends it only while
#       the player has respawns left (and Jungle Storm never with None):
#       with the count used up it marks the player dead and returns, so a
#       "Respawn: 0" lobby never handed off (seen in play 2026-09-26; SELECT
#       still switched by hand). The branch goes straight to the block that
#       ends that player's fade and sends the message.
#
# When the dead player's fireteam has nobody left, nothing happens: that
# half of the screen stays faded, exactly as it does in stock split screen
# when the respawns run out, and the mission fails through its own check
# once every platoon soldier is down.

GR_HANDOFF = {
    # B1  bnez v0,0x396874 -> j cave
    0x0039673C: 0x1440004D,
    # B2  jal GetLeader ; lw a0,0x444(s5) -> move v0,s0 ; nop
    0x003969C0: 0x0C0E3CE8, 0x003969C4: 0x8EA40444,
    # B3  sltiu at,fp,2 -> andi at,s6,2
    0x00396B4C: 0x2FC10002,
    # B4  the avatar-index test in AssignControlAvatar
    0x0039014C: 0x70002E28, 0x00390150: 0x8EB90000, 0x00390154: 0x72A02628,
    0x00390158: 0x8F390054, 0x0039015C: 0x0320F809, 0x00390160: 0x24050001,
    0x00390164: 0x8FA300B4, 0x00390168: 0x0062B026, 0x0039016C: 0x2ED60001,
    # B5  beqz v0 -> b  (RequestControlAvatar's split-screen name payload)
    0x00390018: 0x10400022,
    # B6' bnez v0,0x17f378 -> bnez v0,0x17f36c (return 0)
    0x0017F348: 0x1440000B,
    # B7  jal GetRespawnType (nop delay slot) -> b 0x3e0120 (end fade, send 0x21)
    0x003E0054: 0x0C0DAF28,
}
GR_HANDOFF_CAVE = 0x00430980    # after the roster cave, same dead function

GR_HANDOFF_NEW = {
    0x003969C0: 0x02001021,     # addu v0, s0, zero
    0x003969C4: 0x00000000,
    0x00396B4C: 0x32C10002,     # andi at, s6, 2
    0x0039014C: 0x24050001,     # addiu a1, zero, 1   -> GetAvatarID(1)
    0x00390150: 0x8FA300B4,     # lw    v1, 0xb4(sp)  new id
    0x00390154: 0x0062B026,     # xor   s6, v1, v0
    0x00390158: 0x2ED60001,     # sltiu s6, s6, 1     new == avatar 2
    0x0039015C: 0x8FA300B8,     # lw    v1, 0xb8(sp)  old id
    0x00390160: 0x00621826,     # xor   v1, v1, v0
    0x00390164: 0x2C630001,     # sltiu v1, v1, 1     old == avatar 2
    0x00390168: 0x00721824,     # and   v1, v1, s2    ... and old id valid
    0x0039016C: 0x02C3B025,     # or    s6, s6, v1
    0x00390018: 0x10000022,     # b 0x3900a4
    0x0017F348: 0x14400008,     # bnez v0, 0x17f36c
    0x003E0054: 0x10000032,     # b 0x3e0120
}

GR_HANDOFF_SRC = """
    bnez  v0, ss                    ; v0 = InSplitScreenMode()
    nop
    j     0x396744                  ; single player: back into stock code
    nop
ss:
    move  a0, s3                    ; IkeSimulationMgr
    addiu a1, sp, 0x64              ; &newID
    jal   0x396910                  ; FindNextTeamMember
    li    a2, 2                     ; AI only, own fireteam only (B3)
    andi  v0, v0, 0xff
    beqz  v0, none
    nop
    lw    a1, 0x64(sp)              ; newID
    move  a2, s1                    ; oldID, the dead soldier
    jal   0x398450                  ; SwitchFollowActor -> 0x19 -> 0x1A -> 0x1B/0x1C
    move  a0, s3
    j     0x396830                  ; stock tail: change-soldier sound, clear blur
    nop
none:
    j     0x396874                  ; nobody left in this fireteam
    nop
"""

JS_HANDOFF = {
    0x003745DC: 0x1440003C,                             # B1
    0x003747A4: 0x0C0DB374, 0x003747A8: 0x8EA40444,     # B2
    0x00374900: 0x2EE10002,                             # B3
    0x0036DBE0: 0x0000282D, 0x0036DBE4: 0x8EB90000, 0x0036DBE8: 0x02A0202D,
    0x0036DBEC: 0x8F390054, 0x0036DBF0: 0x0320F809, 0x0036DBF4: 0x24050001,
    0x0036DBF8: 0x8FA300B4, 0x0036DBFC: 0x0062B026, 0x0036DC00: 0x2ED60001,
    0x0036DA98: 0x10400023,                             # B5
    0x0014FA98: 0x1440000B,                             # B6'
    0x003BFAE8: 0x0C052544,                             # B7 jal GetRespawnType
}
JS_HANDOFF_CAVE = 0x00199B08    # after the roster cave, same dead function

JS_HANDOFF_NEW = {
    0x003747A4: 0x02401021,     # addu v0, s2, zero   (JS keeps the dead soldier in s2)
    0x003747A8: 0x00000000,
    0x00374900: 0x33C10002,     # andi at, fp, 2      (JS copies the argument to fp)
    0x0036DBE0: 0x24050001,
    0x0036DBE4: 0x8FA300B4,
    0x0036DBE8: 0x0062B026,
    0x0036DBEC: 0x2ED60001,
    0x0036DBF0: 0x8FA300B0,     # JS keeps the old id at 0xb0
    0x0036DBF4: 0x00621826,
    0x0036DBF8: 0x2C630001,
    0x0036DBFC: 0x00701824,     # and v1, v1, s0      (old id valid)
    0x0036DC00: 0x02C3B025,
    0x0036DA98: 0x10000023,
    0x0014FA98: 0x14400009,     # bnez v0, 0x14fac0   (return 0)
    0x003BFAE8: 0x10000038,     # b 0x3bfbcc          (end fade, send 0x21)
}

JS_HANDOFF_SRC = """
    bnez  v0, ss
    nop
    j     0x3745e4
    nop
ss:
    move  a0, s3
    addiu a1, sp, 0x68
    jal   0x3746f0                  ; FindNextTeamMember
    li    a2, 2
    andi  v0, v0, 0xff
    beqz  v0, out
    nop
    lw    t9, 0(s3)
    lw    a1, 0x68(sp)
    move  a2, s1
    lw    t9, 0x158(t9)             ; SwitchFollowActor, as JS single player calls it
    jalr  t9
    move  a0, s3
out:
    j     0x3746d0                  ; JS single player also returns straight here
    nop
"""

GR_STOCK.update(GR_HANDOFF)
JS_STOCK.update(JS_HANDOFF)


# ---------------------------------------------------------------------------
# Bullet holes in split screen
# ---------------------------------------------------------------------------
#
# Split screen creates bullet holes and never draws them. EffMgrPS2::Render
# has a full-screen block and a per-viewport split-screen loop; the
# full-screen block calls WaterRippleManagerPS2::Render and then
# BulletHoleManagerPS2::Render, the split loop only the water ripples. A
# Jungle Storm split-screen savestate holds two live holes whose last-update
# time still equals their spawn time seven seconds later -- the render, which
# ages them, never ran.
#
# The fix routes the split loop's water-ripple call through a routine that
# makes both calls, the full-screen order, after that viewport's draw area
# and matrix are set. The ageing update then runs twice a frame with the
# same clock, which changes nothing. The render gate itself is untouched.

GR_BH_HOOK = 0x0045E2E4         # jal WaterRipple::Render in the split loop
GR_BH_HOOK_STOCK = 0x0C11AD38
GR_BH_CAVE = 0x004309D0         # after the handoff cave
GR_BH_SRC = """
    addiu sp, sp, -16
    sd    ra, 0(sp)
    jal   0x46b4e0                  ; WaterRippleManagerPS2::Render (a0 set by the hook's delay slot)
    nop
    jal   0x46dc20                  ; BulletHoleManagerPS2::Render
    lw    a0, 0x627c(s3)            ; EffMgrPS2 (s3) -> bullet-hole manager
    ld    ra, 0(sp)
    jr    ra
    addiu sp, sp, 16
"""

JS_BH_HOOK = 0x00423D78
JS_BH_HOOK_STOCK = 0x0C10BCB8
JS_BH_CAVE = 0x00199B60
JS_BH_SRC = """
    addiu sp, sp, -16
    sd    ra, 0(sp)
    jal   0x42f2e0                  ; water ripples, as before
    nop
    jal   0x431b70                  ; bullet holes
    lw    a0, 0x6274(s1)            ; EffMgrPS2 is s1 in Jungle Storm
    ld    ra, 0(sp)
    jr    ra
    addiu sp, sp, 16
"""

GR_STOCK[GR_BH_HOOK] = GR_BH_HOOK_STOCK
JS_STOCK[JS_BH_HOOK] = JS_BH_HOOK_STOCK


# ---------------------------------------------------------------------------
# The mission briefing in split screen
# ---------------------------------------------------------------------------
#
# Menu screens change by CloseScreen + OpenScreen(name), and every screen of
# the shell is loaded at once, so any screen can open any other. Split
# screen's menu (PS2MultiplayerSplitScreen::Accept) already locks the mission
# exactly like single player does -- MissionLocked loads the mission file and
# the objectives -- and then opens the soldier-choose screen. Single player
# opens SINGLE_BRIEFING at that point. SPBriefing only reads the mission
# file, the objective list and the briefing map, none of which is
# campaign-only.
#
#   A1  split-screen menu, Mission mode only: open SINGLE_BRIEFING instead of
#       the soldier screen (the game's own mode test: index == game-type
#       count in GR, this+0x18C == 0x10 in JS)
#   A2  SPBriefing Accept: in split screen open the soldier screen instead
#       of single player's platoon screen
#   A3  SPBriefing Back: in split screen return to the split-screen menu
#   A4  (GR only) the main menu clears the split-screen draw flag, which is
#       what A2/A3 test. Stock Ghost Recon leaves it set after Split Screen ->
#       Back; Jungle Storm's SINGLE and ONLINE choices already clear it.
#
# The routines live in sceIoctl (GR 0x004167F8, JS 0x0017F290, 844 bytes),
# a library function nothing calls.

GR_UI_CAVE = 0x004167F8
JS_UI_CAVE = 0x0017F290
UI_CAVE_BYTES = 844

_GR_UI_CAVE_STOCK_HEX = (
    "27BDFF40 FFB20060 FFB10050 00C0902D FFB600A0 00A0882D FFB50090 3C16005F"
    "FFB40080 24150001 FFB30070 3C14005F FFB00040 FFBF00B0 0C10551E 26D3E100"
    "0040802D 0C10563E 24040005 3C020057 AE92E0C4 8C43E1C0 14600003 00000000"
    "0C10567E 00000000 12000004 00000000 8E020004 54400005 AE600414 0C10564A"
    "00000000 100000A7 2402FFF7 24020002 12220029 AE600418 2A220003 10400005"
    "24020003 52350007 3C100057 10000032 8E020000 12220027 3C02005F 1000002E"
    "8E020000 0C1046C8 8E04E1CC 3C050057 0000202D 8CA3E140 2402FFFF 1462000B"
    "24020020 24A3E140 2405FFFF 24840001 28820020 10400004 24630004 8C620000"
    "5045FFFB 24840001 24020020 14820004 8E83E0C4 8E82E0C4 10000003 AC400000"
    "24020001 AC620000 0C1046C0 8E04E1CC 1000000D 00000000 3C02005F 3C042000"
    "2442ED90 00441025 8C430000 10000006 AE430000 3C042000 2442ED90 00441025"
    "DC430000 FE430000 0C10564A 00000000 1000006C 0000102D AE710010 16400006"
    "AE62000C AE60041C 27B20030 3C15005F 10000034 3C11005F 0240302D 26640014"
    "24030400 00C41025 30420007 1040001C AE63041C 24C20400 27B20030 3C15005F"
    "3C11005F 68C30007 6CC30000 68C5000F 6CC50008 68C70017 6CC70010 68C8001F"
    "6CC80018 B0830007 B4830000 B085000F B4850008 B0870017 B4870010 B088001F"
    "B4880018 24C60020 24840020 00000000 14C2FFEC 00000000 10000013 24020001"
    "24C20400 27B20030 3C15005F 3C11005F DCC30000 DCC50008 DCC70010 DCC80018"
    "FC830000 FC850008 FC870010 FC880018 24C60020 24840020 00000000 14C2FFF4"
    "00000000 24020001 AFA00018 AFA20014 27A40010 AFA00024 0C1046B8 2634ED40"
    "26D0E100 0040882D 0200202D 24020004 AE720004 AE620008 24050420 0C1050E0"
    "AE710000 26A4F3C0 0200382D AFA00000 24050005 0000302D 24080420 0280482D"
    "240A0004 0C10531C 0000582D 04410007 3C022000 0C1046BC 0220202D 0C10564A"
    "00000000 1000000F 2402FFF5 02821025 0C10564A 8C500000 16000005 00000000"
    "0C1046BC 0220202D 10000006 2402FFF5 0C1046C8 0220202D 0C1046BC 0220202D"
    "8FA20030 DFBF00B0 DFB600A0 DFB50090 DFB40080 DFB30070 DFB20060 DFB10050"
    "DFB00040 03E00008 27BD00C0"
)
_JS_UI_CAVE_STOCK_HEX = (
    "27BDFF40 FFB20060 FFB10050 00C0902D FFB600A0 00A0882D FFB50090 3C160061"
    "FFB40080 24150001 FFB30070 3C140061 FFB00040 FFBF00B0 0C05F7AE 26D37000"
    "0040802D 0C05F8CC 24040005 3C020057 AE926FC8 8C434FEC 14600003 00000000"
    "0C05F918 00000000 12000004 00000000 8E020004 54400005 AE600414 0C05F8D8"
    "00000000 100000B1 2402FFF7 24020002 12220029 AE600418 2A220003 10400005"
    "24020003 52350007 3C100057 1000003C 8E020000 1222002C 3C040057 10000038"
    "8E020000 0C05E8C8 8E044FFC 3C050057 0000202D 8CA34F68 2402FFFF 1462000B"
    "24020020 24A34F68 2405FFFF 24840001 28820020 10400004 24630004 8C620000"
    "5045FFFB 24840001 24020020 14820004 8E836FC8 8E826FC8 10000003 AC400000"
    "24020001 AC620000 0C05E8C0 8E044FFC 10000017 00000000 3C040057 24050440"
    "8C824FE8 3C030061 24637C90 3C042000 00451018 00431021 00441025 8C430000"
    "1000000B AE430000 24050440 8C824FE8 3C030061 24637C90 3C042000 00451018"
    "00431021 00441025 DC430000 FE430000 0C05F8D8 00000000 1000006C 0000102D"
    "AE710010 16400006 AE62000C AE60041C 27B20030 3C150062 10000034 3C110061"
    "0240302D 26640014 24030400 00C41025 30420007 1040001C AE63041C 24C20400"
    "27B20030 3C150062 3C110061 68C30007 6CC30000 68C5000F 6CC50008 68C70017"
    "6CC70010 68C8001F 6CC80018 B0830007 B4830000 B085000F B4850008 B0870017"
    "B4870010 B088001F B4880018 24C60020 24840020 00000000 14C2FFEC 00000000"
    "10000013 24020001 24C20400 27B20030 3C150062 3C110061 DCC30000 DCC50008"
    "DCC70010 DCC80018 FC830000 FC850008 FC870010 FC880018 24C60020 24840020"
    "00000000 14C2FFF4 00000000 24020001 AFA00018 AFA20014 27A40010 AFA00024"
    "0C05E8B8 26347C40 26D07000 0040882D 0200202D 24020004 AE720004 AE620008"
    "24050420 0C05F324 AE710000 26A48700 0200382D AFA00000 24050005 0000302D"
    "24080420 0280482D 240A0004 0C05F5AA 0000582D 04410007 3C022000 0C05E8BC"
    "0220202D 0C05F8D8 00000000 1000000F 2402FFF5 02821025 0C05F8D8 8C500000"
    "16000005 00000000 0C05E8BC 0220202D 10000006 2402FFF5 0C05E8C8 0220202D"
    "0C05E8BC 0220202D 8FA20030"
)

GR_UI_SYMS = {
    "GFX": 0x00630B40,          # g_graphic_sys; +0x2880 = split-screen draw flag
    "DATAMGR": 0x005E4D98,      # mIIkeDataMgr; +0x2d8 = NumberOfGameTypes()
    "S_CHOOSE": 0x005820C0,     # "PS2_MULTI_SPLITSCREEN_CHOOSESOLDIER"
    "S_BRIEF": 0x00572C90,      # "SINGLE_BRIEFING"
    "S_PLATOON": 0x0057EC30,    # "SINGLE_PLATOON"
    "S_SSMENU": 0x00581BB0,     # "PS2_MULTI_SPLITSCREEN"
    "BACK_EPI": 0x0030379C, "BACK_NOGI": 0x00303700, "BACK_GI": 0x003036D8,
}
JS_UI_SYMS = {
    "GFX": 0x0067CF40,
    "S_CHOOSE": 0x00590EC0, "S_BRIEF": 0x0057E5F0,
    "S_PLATOON": 0x0058E190, "S_SSMENU": 0x00590D10,
    "BACK_EPI": 0x002B51FC, "BACK_NOGI": 0x002B5158, "BACK_GI": 0x002B5130,
}

GR_BRIEF_SRC = """
; A1 (jal from the split-screen menu's Accept; a0 = this, t9 = OpenScreen)
pickSS:
    lw    v1, 0x118(a0)             ; chosen game type
    lui   at, %hi(DATAMGR)
    lw    v0, %lo(DATAMGR)(at)
    lw    v0, 0x2d8(v0)             ; NumberOfGameTypes(): the Mission entry
    lui   a1, %hi(S_CHOOSE)
    bne   v1, v0, pickSS_out
    addiu a1, a1, %lo(S_CHOOSE)
    lui   a1, %hi(S_BRIEF)
    addiu a1, a1, %lo(S_BRIEF)
pickSS_out:
    jr    ra
    nop
; A2 (jal from SPBriefing::Accept): platoon screen, or the soldier screen in split screen
pickBrf:
    lui   v0, %hi(GFX)
    lw    v0, %lo(GFX)(v0)
    lui   a1, %hi(S_PLATOON)
    lbu   v0, 0x2880(v0)
    beqz  v0, pickBrf_out
    addiu a1, a1, %lo(S_PLATOON)
    lui   a1, %hi(S_CHOOSE)
    addiu a1, a1, %lo(S_CHOOSE)
pickBrf_out:
    jr    ra
    nop
; A3 (j from SPBriefing::Back after its CloseScreen; s0 = this)
brfBack:
    lui   v0, %hi(GFX)
    lw    v0, %lo(GFX)(v0)
    lbu   v0, 0x2880(v0)
    beqz  v0, brfBack_sp
    lui   at, 0x5e                  ; the replaced delay slot, needed at BACK_NOGI
    lw    t9, 0(s0)
    move  a0, s0
    lui   a1, %hi(S_SSMENU)
    addiu a1, a1, %lo(S_SSMENU)
    lw    t9, 0x118(t9)
    jalr  t9                        ; OpenScreen("PS2_MULTI_SPLITSCREEN", true)
    li    a2, 1
    j     BACK_EPI
    nop
brfBack_sp:
    lbu   v0, 0xe4(s0)              ; the replaced test, then its two stock paths
    bnez  v0, brfBack_gi
    nop
    j     BACK_NOGI
    nop
brfBack_gi:
    j     BACK_GI
    nop
; A4 (jal from MainScreen::SetVisible(true)): the replaced store, and flag = 0
mainClr:
    lui   v0, %hi(GFX)
    lw    v0, %lo(GFX)(v0)
    sw    zero, 0x108(s1)
    jr    ra
    sb    zero, 0x2880(v0)
"""

JS_BRIEF_SRC = """
pickSS:
    lw    v1, 0x18c(a0)             ; Jungle Storm's own Mission test
    li    v0, 0x10
    lui   a1, %hi(S_CHOOSE)
    bne   v1, v0, pickSS_out
    addiu a1, a1, %lo(S_CHOOSE)
    lui   a1, %hi(S_BRIEF)
    addiu a1, a1, %lo(S_BRIEF)
pickSS_out:
    jr    ra
    nop
pickBrf:
    lui   v0, %hi(GFX)
    lw    v0, %lo(GFX)(v0)
    lui   a1, %hi(S_PLATOON)
    lbu   v0, 0x2880(v0)
    beqz  v0, pickBrf_out
    addiu a1, a1, %lo(S_PLATOON)
    lui   a1, %hi(S_CHOOSE)
    addiu a1, a1, %lo(S_CHOOSE)
pickBrf_out:
    jr    ra
    nop
brfBack:
    lui   v0, %hi(GFX)
    lw    v0, %lo(GFX)(v0)
    lbu   v0, 0x2880(v0)
    beqz  v0, brfBack_sp
    nop
    lw    t9, 0(s0)
    move  a0, s0
    lui   a1, %hi(S_SSMENU)
    addiu a1, a1, %lo(S_SSMENU)
    lw    t9, 0x118(t9)
    jalr  t9
    li    a2, 1
    j     BACK_EPI
    nop
brfBack_sp:
    lbu   v0, 0x158(s0)
    bnez  v0, brfBack_gi
    nop
    j     BACK_NOGI
    nop
brfBack_gi:
    j     BACK_GI
    nop
"""

#: (va, stock, instruction assembled at va)
GR_BRIEF_HOOKS = (
    (0x0033A260, 0x244520C0, "jal pickSS"),     # addiu a1,v0,0x20c0 (CHOOSESOLDIER)
    (0x003037D8, 0x2445EC30, "jal pickBrf"),    # addiu a1,v0,-0x13d0 (SINGLE_PLATOON)
    (0x003036CC, 0x920200E4, "j brfBack"),      # lbu v0,0xe4(s0)
    (0x003036D0, 0x1040000B, "nop"),            # beqz v0,0x303700
    (0x002FA568, 0xAE200108, "jal mainClr"),    # sw zero,0x108(s1)
)
JS_BRIEF_HOOKS = (
    (0x002E43FC, 0x24A50EC0, "jal pickSS"),
    (0x002B5060, 0x24A5E190, "jal pickBrf"),
    (0x002B5124, 0x92020158, "j brfBack"),
    (0x002B5128, 0x1040000B, "nop"),
)

GR_STOCK.update(_stock_words(GR_UI_CAVE, _GR_UI_CAVE_STOCK_HEX))
JS_STOCK.update(_stock_words(JS_UI_CAVE, _JS_UI_CAVE_STOCK_HEX))
GR_STOCK.update({va: s for va, s, _ in GR_BRIEF_HOOKS})
JS_STOCK.update({va: s for va, s, _ in JS_BRIEF_HOOKS})


def _brief_edits(src, cave, syms, hooks, stock):
    words, labels = assemble(src, cave, syms)
    if len(words) * 4 > UI_CAVE_BYTES:
        raise ValueError("briefing routines do not fit")
    out = [(cave + 4 * i, w, stock[cave + 4 * i], "split-screen briefing: routine")
           for i, w in enumerate(words)]
    allsyms = dict(syms)
    allsyms.update(labels)
    for va, s, ins in hooks:
        out.append((va, assemble(ins, va, allsyms)[0][0], s,
                    "split-screen briefing: hook"))
    return out


# ---------------------------------------------------------------------------
# Single player's roster in split screen: P1 leads Alpha, P2 leads Bravo
# ---------------------------------------------------------------------------
#
# Builds on the briefing. Split-screen Mission becomes split-screen menu ->
# SINGLE_BRIEFING -> SINGLE_PLATOON -> GO, and GO launches split screen
# straight from the platoon screen: no soldier screen. Player 1 is Alpha's
# first Ghost, player 2 Bravo's first, and every other pick is AI in his own
# fireteam, with his real name, actor file and the kit chosen on the screen
# -- single player's own roster writer does all of it. (The PS2 platoon
# screen has only Alpha and Bravo: its six slots are a 2x3 grid.)
#
#   A1/A3/A4 are the briefing's routines unchanged; A2 is dropped, so the
#   briefing's Accept opens the platoon screen as it does in single player.
#   C1 SPPlatoonScreen::GoGoGo entry: in split screen, with two or more
#      Ghosts picked, do what the soldier screen's Accept did first --
#      ActivateSplitScreenMode (RSGameStateMgr+0x1E9, which every
#      InSplitScreenMode test reads; the main menu's Split Screen choice
#      only set the draw flag), SetMissionIsTraining(0) and
#      SetMissionIsTactical(0). With fewer than two, GO does nothing.
#   C2 in place of GoGoGo's EnableSplitScreen(0): split screen skips it,
#      lends an empty fireteam the other team's last Ghost at position 0
#      (`balance`), runs BeginLoading and single player's roster writer,
#      puts the lent Ghost back on the screen, and rejoins at CheckWeaponSnd.
#   C3 HandleGameObjectCreated's player-2 test, rewritten in place over a
#      dead "1P" compare: player 2 = fireteam index 1 or the name "2P", so
#      the soldier-screen layouts of the other split-screen modes still work.
#      Only player-owned soldiers reach it (AI-controlled ones branch away).
#   C4 the writer's leader test: in split screen Bravo's position 0 also
#      gets Owner = the local system (player 1 is the stock leader).
#
# Both writers and both loaders use the same in-memory avatar.toe, and
# Mission mode's game-type index (0xFFFF) takes single player's load path:
# roster platoon 0 goes into the mission's first allied company. The
# routines take the whole UI cave; stack slots sp+0x40/0x48 in C2 are
# GoGoGo's slot-swap temporaries, dead by then. Checked in an interpreter
# for every team split, not yet played.

GR_SPR_SYMS = dict(GR_UI_SYMS, **{
    "ISTATE": 0x005DFF40,       # IRSGameStateMgr (ActivateSplitScreenMode: slot 0x128)
    "IKESTATE": 0x005E4FF8,     # IIkeStateMgr (SetMissionIsTraining 0x134 / Tactical 0x13C)
    "ROOT": 0x005E6DB8, "BEGINLOAD": 0x0020CBC0,
    "SPTOE": 0x00307180,        # SPPlatoonScreen::CreateTOEFile
    "GATE_RESUME": 0x0030B438, "TAIL_SP": 0x0030B8A4, "TAIL_RESUME": 0x0030B8C0,
    "OWN_NO": 0x00307758,
})
JS_SPR_SYMS = dict(JS_UI_SYMS, **{
    "ISTATE": 0x00684A78, "IKESTATE": 0x006142D0,
    "ROOTGET": 0x00124EF0, "BEGINLOAD": 0x00207F90, "SPTOE": 0x002C7B20,
    "GATE_RESUME": 0x002C4B68, "TAIL_SP": 0x002C4D84, "TAIL_RESUME": 0x002C4DA4,
    "OWN_NO": 0x002C7DD4,
})
#: platoon-screen slot fields (team, position, soldier; stride 0x28), the
#: register GoGoGo keeps the screen in, GoGoGo's prologue, and the roster
#: writer's (loop index, leader index, slot pointer) registers
_SPR_GAME = {
    "GR": dict(TEAM=0xE8, POS=0xEC, SOLD=0xF0, SCREEN="s1", FRAME=0xA0, RA_OFF=48,
               IDX="s1", LEAD="s6", SLOT="s0",
               ROOTLOAD="    lui   at, %hi(ROOT)\n    jal   BEGINLOAD\n    lw    a0, %lo(ROOT)(at)\n"),
    "JS": dict(TEAM=0x15C, POS=0x160, SOLD=0x164, SCREEN="s0", FRAME=0x90, RA_OFF=32,
               IDX="s0", LEAD="s2", SLOT="s1",
               ROOTLOAD="    jal   ROOTGET\n    nop\n    jal   BEGINLOAD\n    move  a0, v0\n"),
}


def _spr_common_src(g):
    T, P, S = g["TEAM"], g["POS"], g["SOLD"]
    return f"""
; C1 (j from GoGoGo+0; a0 = SPPlatoonScreen, ra = GoGoGo's caller)
goGate:
    lui   v0, %hi(GFX)
    lw    v0, %lo(GFX)(v0)
    lbu   v0, 0x2880(v0)
    beqz  v0, gg_go                 ; single player: untouched
    move  v1, zero                  ; Ghosts picked
    addiu t0, a0, {S:#x}
    addiu t1, a0, {S + 6 * 0x28:#x}
gg_cnt:
    lw    v0, 0(t0)
    bltz  v0, gg_nx
    addiu t0, t0, 0x28
    addiu v1, v1, 1
gg_nx:
    bne   t0, t1, gg_cnt
    slti  v0, v1, 2
    bnez  v0, gg_block              ; one Ghost: player 2 would have no soldier
    nop
    addiu sp, sp, -0x20
    sd    ra, 0x00(sp)
    sd    a0, 0x08(sp)
    lui   at, %hi(ISTATE)
    lw    a0, %lo(ISTATE)(at)
    lw    t9, 0(a0)
    lw    t9, 0x128(t9)             ; ActivateSplitScreenMode
    jalr  t9
    nop
    lui   at, %hi(IKESTATE)
    lw    a0, %lo(IKESTATE)(at)
    lw    t9, 0(a0)
    lw    t9, 0x134(t9)             ; SetMissionIsTraining(false)
    jalr  t9
    move  a1, zero
    lui   at, %hi(IKESTATE)
    lw    a0, %lo(IKESTATE)(at)
    lw    t9, 0(a0)
    lw    t9, 0x13c(t9)             ; SetMissionIsTactical(false)
    jalr  t9
    move  a1, zero
    ld    ra, 0x00(sp)
    ld    a0, 0x08(sp)
    addiu sp, sp, 0x20
gg_go:
    addiu sp, sp, -{g["FRAME"]:#x}  ; the two replaced prologue words
    j     GATE_RESUME
    sd    ra, {g["RA_OFF"]}(sp)
gg_block:
    jr    ra
    nop

; C2 (j from GoGoGo's EnableSplitScreen(0) site; screen = {g["SCREEN"]})
ssTail:
    lui   at, %hi(GFX)              ; the two replaced instructions
    lw    a0, %lo(GFX)(at)
    lbu   v0, 0x2880(a0)
    bnez  v0, st_ss
    nop
    j     TAIL_SP                   ; single player: EnableSplitScreen(0) and on
    nop
st_ss:
    jal   balance                   ; v0 = lent slot or 0, v1 = its team<<8|pos
    move  a0, {g["SCREEN"]}
    sd    v0, 0x40(sp)
    sd    v1, 0x48(sp)
{g["ROOTLOAD"]}    jal   SPTOE                     ; single player's roster writer
    move  a0, {g["SCREEN"]}
    ld    v0, 0x40(sp)
    beqz  v0, st_out
    ld    v1, 0x48(sp)
    srl   t0, v1, 8
    sw    t0, {T:#x}(v0)            ; the lent Ghost back to his own team
    andi  t0, v1, 0xff
    sw    t0, {P:#x}(v0)
st_out:
    j     TAIL_RESUME               ; CheckWeaponSnd and the stock launch
    nop

; balance(a0 = screen): an empty fireteam borrows the other one's last Ghost
balance:
    move  t2, zero                  ; Alpha count
    move  t3, zero                  ; Bravo count
    move  t4, zero                  ; Alpha slot with the highest position
    move  t5, zero                  ; Bravo slot with the highest position
    li    t6, -1
    li    t7, -1
    move  t0, a0
    addiu t1, a0, {6 * 0x28:#x}
bl_loop:
    lw    v1, {S:#x}(t0)
    bltz  v1, bl_next
    lw    a1, {T:#x}(t0)
    lw    a2, {P:#x}(t0)
    bnez  a1, bl_b
    nop
    addiu t2, t2, 1
    slt   t8, t6, a2
    beqz  t8, bl_next
    nop
    move  t6, a2
    b     bl_next
    move  t4, t0
bl_b:
    addiu t3, t3, 1
    slt   t8, t7, a2
    beqz  t8, bl_next
    nop
    move  t7, a2
    move  t5, t0
bl_next:
    addiu t0, t0, 0x28
    bne   t0, t1, bl_loop
    nop
    bnez  t3, bl_chkA
    slti  t8, t2, 2
    bnez  t8, bl_none
    li    a1, 1                     ; Bravo empty: Alpha's last -> Bravo position 0
    b     bl_move
    move  v0, t4
bl_chkA:
    bnez  t2, bl_none               ; both fireteams manned
    slti  t8, t3, 2
    bnez  t8, bl_none
    move  a1, zero                  ; Alpha empty: Bravo's last -> Alpha position 0
    move  v0, t5
bl_move:
    lw    v1, {T:#x}(v0)
    lw    a2, {P:#x}(v0)
    sll   v1, v1, 8
    or    v1, v1, a2
    sw    a1, {T:#x}(v0)
    jr    ra
    sw    zero, {P:#x}(v0)
bl_none:
    jr    ra
    move  v0, zero

; C4 (jal from the writer's leader test; its delay slot is the stock store)
ownerTest:
    beq   {g["IDX"]}, {g["LEAD"]}, ot_yes   ; the stock leader: player 1
    lui   v0, %hi(GFX)
    lw    v0, %lo(GFX)(v0)
    lbu   v0, 0x2880(v0)
    beqz  v0, ot_no
    lw    v0, {T:#x}({g["SLOT"]})
    li    v1, 1
    bne   v0, v1, ot_no             ; Bravo ...
    lw    v0, {P:#x}({g["SLOT"]})
    bnez  v0, ot_no                 ; ... position 0: player 2
    nop
ot_yes:
    jr    ra                        ; Owner = GetLocalSystemID()
    nop
ot_no:
    j     OWN_NO
    nop
"""


GR_SPR_SRC = (GR_BRIEF_SRC.split("; A2 ")[0] + GR_BRIEF_SRC[GR_BRIEF_SRC.index("; A3 "):]
              + _spr_common_src(_SPR_GAME["GR"]))
JS_SPR_SRC = (JS_BRIEF_SRC.split("pickBrf:")[0] + JS_BRIEF_SRC[JS_BRIEF_SRC.index("brfBack:"):]
              + _spr_common_src(_SPR_GAME["JS"]))

#: (va, stock, instruction assembled at va) -- the briefing's minus A2
GR_SPR_HOOKS = tuple(h for h in GR_BRIEF_HOOKS if h[0] != 0x003037D8) + (
    (0x0030B430, 0x27BDFF60, "j goGate"),       # addiu sp,sp,-0xa0
    (0x0030B434, 0xFFBF0030, "nop"),            # sd ra,48(sp)
    (0x0030B89C, 0x3C010063, "j ssTail"),       # lui at,0x63
    (0x0030B8A0, 0x8C240B40, "nop"),            # lw a0,0xb40(at)
    (0x00307728, 0x1636000B, "jal ownerTest"),  # bne s1,s6,0x307758
)
JS_SPR_HOOKS = tuple(h for h in JS_BRIEF_HOOKS if h[0] != 0x002B5060) + (
    (0x002C4B60, 0x27BDFF70, "j goGate"),
    (0x002C4B64, 0xFFBF0020, "nop"),
    (0x002C4D7C, 0x3C010068, "j ssTail"),
    (0x002C4D80, 0x8C24CF40, "nop"),
    (0x002C7DA4, 0x1612000B, "jal ownerTest"),
)

#: C3, in place: (base, stock words, source)
GR_SPR_P2 = (0x0038F490, (
    "8E590000 8F390230 0320F809 72402628 70402628 3C020058 0C14FA08 24453F90"
    "8E590000 8F390230 0320F809 72402628 70402628 3C020058 0C14FA08 24453F98"
    "0C0DAF24 305100FF"), """
    lw    t9, 0(s2)
    lw    t9, 0x4d0(t9)             ; SimHuman::GetFireTeamIndex
    jalr  t9
    move  a0, s2
    xori  s1, v0, 1
    sltiu s1, s1, 1                 ; s1 = Bravo
    lw    t9, 0(s2)
    lw    t9, 0x230(t9)             ; GetName
    jalr  t9
    move  a0, s2
    lui   a1, 0x58
    move  a0, v0
    jal   0x53e820                  ; RSString::operator==(const char*)
    addiu a1, a1, 0x3f98            ; "2P"
    andi  v0, v0, 0xff
    nop
    jal   0x36bc90                  ; IRSGameStateMgr::Get (stock)
    or    s1, s1, v0                ; stock: andi s1, v0, 0xff
""")
JS_SPR_P2 = (0x0036CEC8, (
    "8E590000 8F390234 0320F809 0240202D 3C050059 0040202D 0C0FFDA0 24A55858"
    "8E590000 8F390234 0320F809 0240202D 3C050059 0040202D 0C0FFDA0 24A55860"
    "0C049620 305100FF"), """
    lw    t9, 0(s2)
    lw    t9, 0x510(t9)             ; GetFireTeamIndex
    jalr  t9
    move  a0, s2
    xori  s1, v0, 1
    sltiu s1, s1, 1
    lw    t9, 0(s2)
    lw    t9, 0x234(t9)             ; GetName
    jalr  t9
    move  a0, s2
    lui   a1, 0x59
    move  a0, v0
    jal   0x3ff680                  ; RSString==
    addiu a1, a1, 0x5860            ; "2P"
    andi  v0, v0, 0xff
    nop
    jal   0x125880                  ; IRSGameStateMgr getter (stock)
    or    s1, s1, v0
""")

for _stock, _hooks, (_base, _hex, _src) in ((GR_STOCK, GR_SPR_HOOKS, GR_SPR_P2),
                                            (JS_STOCK, JS_SPR_HOOKS, JS_SPR_P2)):
    _stock.update({va: s for va, s, _ in _hooks})
    _stock.update(_stock_words(_base, _hex))


def _spr_edits(src, cave, syms, hooks, p2, stock):
    words, labels = assemble(src, cave, syms)
    if len(words) * 4 > UI_CAVE_BYTES:
        raise ValueError("roster routines do not fit the UI cave")
    out = [(cave + 4 * i, w, stock[cave + 4 * i], "SP roster in split screen: routine")
           for i, w in enumerate(words)]
    allsyms = dict(syms)
    allsyms.update(labels)
    for va, s, ins in hooks:
        out.append((va, assemble(ins, va, allsyms)[0][0], s,
                    "SP roster in split screen: hook"))
    base, _hex, p2src = p2
    pw, _ = assemble(p2src, base)
    if len(pw) != 18:
        raise ValueError("player-2 test must stay 18 words")
    out += [(base + 4 * i, w, stock[base + 4 * i],
             "SP roster in split screen: player 2 = Bravo's leader")
            for i, w in enumerate(pw)]
    return out


# ---------------------------------------------------------------------------
# Team orders and soldier switching in split screen
# ---------------------------------------------------------------------------
#
# Builds on the handoff. Single player switches soldiers with
# FollowNextTeamMember (0x21) and orders the *other* fireteam with a
# QuickOrder that is hard-wired to player 1; split screen binds none of it
# for pad 2 and returns early from the handlers. Instead of reviving the
# player-1-only paths, both players get:
#
#   switch soldier  0x21 carrying that player's avatar id (input flag 0x200
#                   for pad 1, 0x4000 for pad 2 -- the input layer attaches
#                   avatar 2's id only for pad index 1). The handler resolves
#                   the soldier from the id and runs the handoff's own-team,
#                   AI-only search, so a player never lands on the other
#                   player's soldiers.
#   Hold/Advance    0x22 with one int payload (the avatar id): toggles that
#                   soldier's fireteam FireTeamAI::SetDesiredMovementROE.
#   combat ROE      (GR only) 0x22 with the keycode and the avatar id:
#                   cycles Recon/Assault/Suppress.
#
# HandleFollowLastTeamMember (0x22) is entered through a routine that passes
# every message straight to stock code outside split screen, and in split
# screen acts only on messages whose avatar payload is an RSInt -- stock
# 0x22 messages carry a bool and are ignored. The key bindings are added in
# IkeInputMgr::MapInputForAction's split-screen block, the one place pad-2
# keys are bound. HandleFollowNextTeamMember reads payload 0 as a bool to
# pick the id: an RSInt answers true (RSObject::operator bool returns 1),
# the death message's bool answers false.
#
# Buttons (GR): d-pad LEFT = switch, R3 = Hold/Advance, player 1 d-pad
# RIGHT / player 2 SELECT = combat ROE. JS: SELECT = switch, the QuickOrder
# key = Hold/Advance (JS's d-pad left/right are peek, L3 has no keycode).
# GR with Jungle Storm's layout (grcontrols): the same keycodes land on
# SELECT (switch), R2 (Hold/Advance) and player 1's L2 (combat ROE);
# player 2's combat ROE moves from SELECT's keycode to L2's, 0x12C, which
# replaces the stock split-screen binding there (MapKey keeps one binding
# per keycode) -- GR_JS_LAYOUT_KEYS.
#
# Caves: NewPS2Shortcut::RelinkBravo (GR 0x002D4A40) and RelinkAlpha/Bravo
# (JS 0x002A23E0). NewPS2Shortcut::mInstance is only ever stored with zero
# (GR 0x0023BA24, JS 0x0023AD4C; no gp-relative access), so its update --
# the only caller -- never runs.

_GR_ORD_CAVE_STOCK_HEX = (
    "27BDF880 FFBF0090 7FBE0080 7FB70070 7FB60060 7FB50050 7FB40040 7FB30030"
    "7FB20020 7FB10010 7FB00000 AFA40770 3C01005F 8C22ACF0 AFA2056C 8FA4056C"
    "70002E28 8C990000 8F390064 0320F809 00000000 AFA200BC 3C01005F 8C22AB28"
    "AFA20570 8FA40570 8FA500BC 8C990000 8F390038 0320F809 00000000 AFA200C0"
    "3C01005E 8C225780 AFA20574 8FA400C0 8C990000 8F39006C 0320F809 00000000"
    "7FA200A0 8FA400C0 8C990000 8F3900A8 0320F809 00000000 8FA50574 70A02628"
    "7BA500A0 70403628 24070001 8C990000 8F390014 0320F809 00000000 70403628"
    "AFA600C4 8FA30770 8C700024 AFA00144 1000001B 00000000 72002628 8FA50144"
    "0C0B50E8 00000000 70401E28 AFA30374 8FA50374 8CA20000 AFA20578 8FA50578"
    "AFA5057C 8FA5057C 24020019 14A20008 00000000 72002628 8FA50144 0C0B50E8"
    "00000000 AFA20140 1000000D 00000000 8FA60144 24C70001 AFA70144 00000000"
    "8E020004 AFA20580 8FA50144 8FA20580 00A2382A 14E0FFE0 00000000 AFA00140"
    "8FA20140 14400037 00000000 8E050004 AFA50584 8FA60584 AFA60148 8FA30148"
    "24650001 72002628 0C0B9B60 00000000 7040F628 72002628 8FA30148 70602E28"
    "0C0B50E8 00000000 AFA20378 24050019 8FA30378 AC650000 72002628 8FA50148"
    "0C0B50E8 00000000 AFA2037C 2403FFFF 8FA2037C 00403021 ACC30004 72002628"
    "8FA20148 70402E28 0C0B50E8 00000000 AFA20380 2405FFFF 8FA20380 AC450008"
    "72002628 8FA50148 0C0B50E8 00000000 AFA20384 2405FFFF 8FA70384 ACE5000C"
    "72002628 8FA50148 0C0B50E8 00000000 70402E28 AFA50388 2406FFFF 8FA30388"
    "AC660010 AFA00150 10000019 00000000 72002628 8FA50150 0C0B50E8 00000000"
    "AFA2038C 8FA2038C 8C430000 AFA30588 8FA50588 AFA5058C 8FA2058C 24030003"
    "14430008 00000000 72002628 8FA50150 0C0B50E8 00000000 AFA2014C 1000000C"
    "00000000 8FA50150 24A20001 AFA20150 8E050004 AFA50590 8FA30150 8FA50590"
    "0065102A 1440FFE2 00000000 AFA0014C 8FA5014C 14A00033 00000000 8E020004"
    "AFA20594 8FA20594 AFA20154 8FA30154 24650001 72002628 0C0B9B60 00000000"
    "72002628 8FA50154 0C0B50E8 00000000 AFA20390 24030003 8FA50390 ACA30000"
    "72002628 8FA50154 0C0B50E8 00000000 AFA20394 2403FFFF 8FA50394 00A01021"
    "AC430004 72002628 8FA50154 0C0B50E8 00000000 AFA20398 2405FFFF 8FA20398"
    "AC450008 72002628 8FA50154 0C0B50E8 00000000 AFA2039C 2405FFFF 8FA2039C"
    "AC45000C 72002628 8FA50154 0C0B50E8 00000000 AFA203A0 2405FFFF 8FA203A0"
    "AC450010 AFA0015C 10000019 00000000 72002628 8FA5015C 0C0B50E8 00000000"
    "AFA203A4 8FA203A4 8C430000 AFA30598 8FA50598 AFA5059C 8FA2059C 24030003"
    "14430008 00000000 72002628 8FA5015C 0C0B50E8 00000000 AFA20158 1000000C"
    "00000000 8FA5015C 24A20001 AFA2015C 8E050004 AFA505A0 8FA2015C 8FA505A0"
    "0045102A 1440FFE2 00000000 AFA00158 8FA20158 AFA200CC AFA00164 1000001A"
    "00000000 72002628 8FA50164 0C0B50E8 00000000 AFA203A8 8FA503A8 8CA50000"
    "AFA505A4 8FA205A4 AFA205A8 8FA205A8 24030019 14430008 00000000 72002628"
    "8FA50164 0C0B50E8 00000000 AFA20160 1000000D 00000000 8FA20164 24440001"
    "AFA40164 00000000 8E030004 AFA305AC 8FA50164 8FA305AC 00A3102A 1440FFE1"
    "00000000 AFA00160 8FB70160 AFB700C8 72002628 24050019 0C0B5260 00000000"
    "AFA20168 24040003 8FA30168 AC640008 24050001 70A02628 0C0B50C8 00000000"
    "AFA20170 72002628 24050003 0C0B5260 00000000 AFA2016C 2403FFFF 8FB40170"
    "00141080 8FA5016C 00A21021 AC430004 8FA30770 8C710024 AFA00178 1000001A"
    "00000000 72202628 8FA50178 0C0B50E8 00000000 AFA203AC 8FA503AC 8CA20000"
    "AFA205B0 8FA505B0 AFA505B4 8FA505B4 2402001A 14A20008 00000000 72202628"
    "8FA50178 0C0B50E8 00000000 AFA20174 1000000D 00000000 8FA30178 24650001"
    "AFA50178 00000000 8E220004 AFA205B8 8FA50178 8FA205B8 00A2302A 14C0FFE1"
    "00000000 AFA00174 8FA20174 14400037 00000000 8E250004 AFA505BC 8FA205BC"
    "AFA2017C 8FA3017C 24650001 72202628 0C0B9B60 00000000 72202628 8FA3017C"
    "70602E28 0C0B50E8 00000000 AFA203B0 2405001A 8FA303B0 AC650000 72202628"
    "8FA6017C 70C02E28 0C0B50E8 00000000 AFA203B4 2405FFFF 8FA203B4 00403821"
    "ACE50004 72202628 8FA5017C 0C0B50E8 00000000 AFA203B8 2403FFFF 8FA603B8"
    "ACC30008 72202628"
)
_JS_ORD_CAVE_STOCK_HEX = (
    "27BDFFB0 FFBF0040 7FB30030 7FB20020 7FB10010 7FB00000 0C049174 0080802D"
    "8C590000 0040202D 8F390064 0320F809 0000282D 0C0529F8 0040882D 8C590000"
    "0220282D 8F390038 0320F809 0040202D 0C049180 0040982D 8E790000 0040902D"
    "8F39006C 0320F809 0260202D 8E790000 0040882D 8F3900A8 0320F809 0260202D"
    "8E590000 0220282D 0240202D 0040302D 8F390014 0320F809 0000382D 8E040024"
    "24050001 0040882D 24060013 0C0A81BC 00A0382D 8E040024 24050001 24060014"
    "0C0A81BC 00A0382D 8E040024 24050001 24060015 0C0A81BC 00A0382D 0C099FD8"
    "0220202D 24030002 10430013 24050001 1045000B 00000000 10400003 00000000"
    "10000013 8E040024 8E040024 24060013 0C0A8230 00A0382D 1000000C 00000000"
    "8E040024 24060014 0C0A8230 00A0382D 10000006 00000000 8E040024 24050001"
    "24060015 0C0A8230 00A0382D 8E040024 24050001 24060010 0C0A81BC 0000382D"
    "8E040024 24050001 24060011 0C0A81BC 0000382D 8E040024 24050001 24060012"
    "0C0A81BC 0000382D 0C099FDC 0220202D 24030002 10430013 24050001 1045000B"
    "00000000 10400003 00000000 10000013 8E040024 8E040024 24060010 0C0A8230"
    "0000382D 1000000C 00000000 8E040024 24060011 0C0A8230 0000382D 10000006"
    "00000000 8E040024 24050001 24060012 0C0A8230 0000382D 8E040024 24050001"
    "24060004 0C0A81BC 24070003 8E040024 24050001 24060005 0C0A81BC 24070003"
    "8E040024 24050001 24060006 0C0A81BC 24070003 0000202D 0C0A7B84 0000282D"
    "10400008 0000202D 8E040024 24050001 24060004 0C0A8230 24070003 10000037"
    "DFBF0040 0C0A7B84 24050001 10400008 0000202D 8E040024 24050001 24060005"
    "0C0A8230 24070003 1000002B 00000000 0C0A7B84 24050002 10400008 0000202D"
    "8E040024 24050001 24060006 0C0A8230 24070003 10000020 00000000 0C0A7C18"
    "0000282D 14400008 0000202D 8E040024 24050001 24060004 0C0A8230 24070003"
    "10000015 00000000 0C0A7C18 24050001 14400008 0000202D 8E040024 24050001"
    "24060005 0C0A8230 24070003 1000000A 00000000 0C0A7C18 24050002 14400006"
    "00000000 8E040024 24050001 24060006 0C0A8230 24070003 DFBF0040 7BB30030"
    "7BB20020 7BB10010 7BB00000 03E00008 27BD0050 00000000 00000000 00000000"
    "27BDFFB0 FFBF0040 7FB30030 7FB20020 7FB10010 7FB00000 0C049174 0080802D"
    "8C590000 0040202D 8F390064 0320F809 0000282D 0C0529F8 0040882D 8C590000"
    "0220282D 8F390038 0320F809 0040202D 0C049180 0040982D 8E790000 0040902D"
    "8F39006C 0320F809 0260202D 8E790000 0040882D 8F3900A8 0320F809 0260202D"
    "8E590000 0220282D 0240202D 0040302D 8F390014 0320F809 24070001 8E040024"
    "0040882D 24050003 24060019 0C0A81BC 24070001 8E040024 24050003 2406001A"
    "0C0A81BC 24070001 8E040024 24050003 2406001B 0C0A81BC 24070001 0C099FD8"
    "0220202D 24030002 10430013 24070001 1047000B 00000000 10400003 00000000"
    "10000013 8E040024 8E040024 24050003 0C0A8230 24060019 1000000C 00000000"
    "8E040024 24050003 0C0A8230 2406001A 10000006 00000000 8E040024 24050003"
    "2406001B 0C0A8230 24070001 8E040024 24050003 24060016 0C0A81BC 0000382D"
    "8E040024 24050003 24060017 0C0A81BC 0000382D 8E040024 24050003 24060018"
    "0C0A81BC 0000382D 0C099FDC 0220202D 24030002 10430015 24030001 1043000C"
    "00000000 10400003 00000000 10000015 8E040024 8E040024 24050003 24060016"
    "0C0A8230 0000382D 1000000D 00000000 8E040024 24050003 24060017 0C0A8230"
    "0000382D 10000006 00000000 8E040024 24050003 24060018 0C0A8230 0000382D"
    "8E040024 24050003 24060007 0C0A81BC 24070002 8E040024 24050003 24060008"
    "0C0A81BC 24070002 8E040024 24050003 24060009 0C0A81BC 24070002 24040001"
    "0C0A7B84 0000282D 10400008 24040001 8E040024 24050003 24060007 0C0A8230"
    "24070002 10000037 DFBF0040 0C0A7B84 0080282D 10400008 24040001 8E040024"
    "24050003 24060008 0C0A8230 24070002 1000002B 00000000 0C0A7B84 24050002"
    "10400008 24040001 8E040024 24050003 24060009 0C0A8230 24070002 10000020"
    "00000000 0C0A7C18 0000282D 14400008 24040001 8E040024 24050003 24060007"
    "0C0A8230 24070002 10000015"
)

ORD = {
    "GR": dict(
        CAVE=0x002D4A40, GetInputHandler=0x0054F190,
        MAP_HOOK=(0x0017190C, 0x0C153C64),         # jal GetInputHandler, split-screen block
        ORD_HOOK=0x00396D80, ORD_STOCK=(0x27BDFF90, 0xFFBF0050), ORD_RESUME=0x00396D88,
        StateMgrLoad="lui at, %hi(0x5E4FF8)\n lw a0, %lo(0x5E4FF8)(at)",
        ObjMgrGet=0x00366CE0, RSIntVT=0x0058EE30, AIMgrPtr=0x005E5778,
        SetMove=0x0018EFF0, SetCombat=0x0018F010,
        vOut=0x298, vComp=0x340, vPlat=0x4CC, vFT=0x4D0,
        keys=((0x0C3, 0x21, 0x2280), (0x188, 0x21, 0x6080),   # d-pad LEFT: switch
              (0x081, 0x22, 0x3320), (0x146, 0x22, 0x7120),   # R3: tap Hold/Advance, hold: move to
              (0x067, 0x22, 0x3280), (0x136, 0x22, 0x7080)),  # P1 RIGHT / P2 SELECT: combat ROE
        words=((0x00396694, 0x14400011, 0x00000000),  # always take the split-screen branch
               (0x0039669C, 0x24050001, 0x38450001),  # payload index = payload0-as-bool ? 0 : 1
               (0x003966C4, 0x10400003, 0x1040006B)), # lookup null -> return, not deref
        stock_hex=_GR_ORD_CAVE_STOCK_HEX,
    ),
    "JS": dict(
        CAVE=0x002A23E0, GetInputHandler=0x0019B0A0,
        MAP_HOOK=(0x00141798, 0x0C066C28),
        ORD_HOOK=0x00374AF0, ORD_STOCK=(0x27BDFF90, 0xFFBF0050), ORD_RESUME=0x00374AF8,
        StateMgrLoad="jal 0x124620\n nop\n move a0, v0",
        ObjMgrGet=0x0014A7E0, RSIntVT=0x005A1220, AIMgrPtr=0x0062C6F8,
        SetMove=0x003DF600, SetCombat=0x003DF620,
        vOut=0x29C, vComp=0x344, vPlat=0x50C, vFT=0x510,
        keys=((0x070, 0x21, 0x2280), (0x135, 0x21, 0x6080),   # SELECT: switch
              (0x081, 0x22, 0x3320), (0x146, 0x22, 0x7120)),  # QuickOrder key: tap / hold
        words=((0x00374534, 0x14400011, 0x00000000),
               (0x0037453C, 0x24050001, 0x38450001),
               (0x00374564, 0x10400003, 0x1040005A)),
        stock_hex=_JS_ORD_CAVE_STOCK_HEX,
    ),
}


# move to where I'm aiming: engine calls and fields (JS placed through their
# GR counterparts' callers and bodies)
ORD["GR"].update(
    FLC=0x004D8540, SETLOC=0x001B7360, POOLLOC=0x001A1CA0, ACCEPT=0x00193F80,
    CLEAR=0x001BAAE0, ADDELEM=0x001BAEC0, SETMOVEROE=0x0018F030,
    CLOCK=0x005DFC20, SLOT=0x005E95E8,   # kBGSC+0x318 (NewPS2Shortcut static, dead)
    EYE=0x478, LOOK=0x210, VEC=0x0C, HOLDINIT=0x18)
ORD["JS"].update(
    FLC=0x004C40E0, SETLOC=0x001B2760, POOLLOC=0x003F1BC0, ACCEPT=0x003E4260,
    CLEAR=0x001B7140, ADDELEM=0x001B6E10, SETMOVEROE=0x003DF640,
    CLOCK=0x00684768, SLOT=0x006295A8,
    EYE=0x49C, LOOK=0x210, VEC=0x10, HOLDINIT=0x19)


GR_JS_LAYOUT_KEYS = ORD["GR"]["keys"][:4] + (
    (0x067, 0x22, 0x3280), (0x12C, 0x22, 0x7080))    # L2 (both players): combat ROE
assert ORD["GR"]["keys"][4:] == ((0x067, 0x22, 0x3280), (0x136, 0x22, 0x7080))


def _ord_map_src(g):
    s = ["map:", " addiu sp, sp, -0x20", " sd ra, 0x10(sp)", " sq s0, 0x00(sp)",
         " jal %#x" % g["GetInputHandler"], " nop", " move s0, v0"]
    for key, msg, flags in g["keys"]:
        s += [" lw t9, 0(s0)", " lw t9, 0x30(t9)", " move a0, s0",
              " li a1, %#x" % key, " li a2, %#x" % msg, " li a3, %#x" % flags,
              " jalr t9", " li t0, -1"]   # RSInput::MapKey(key, msg, flags, alt=-1)
    s += [" move v0, s0", " ld ra, 0x10(sp)", " lq s0, 0x00(sp)", " jr ra",
          " addiu sp, sp, 0x20"]
    return "\n".join(s)


# move-to tuning
MV_TAP = 0.40      # s: a shorter press is a tap (Hold/Advance), a longer one is "move to"
MV_REACH = 100.0   # m: aim ray length
MV_MIN_T = 2.0     # m: hits closer than this are not an order
MV_BACK = 0.75     # m: pulled back along the ray from the surface
MV_LIFT = 0.40     # m: raised, so RSSimScene::FindLevel sees the floor from above
MV_SPACE = 1.5     # m: each further member stands this much further to the right of the aim


def _fbits_hi(x):
    return struct.unpack("<I", struct.pack("<f", x))[0] >> 16


def _ord_src(g):
    return """
ord:
 addiu sp, sp, -0x60
 sd    ra, 0x50(sp)
 sq    s0, 0x00(sp)
 sq    s1, 0x10(sp)
 sq    s2, 0x20(sp)
 sq    s3, 0x30(sp)
 move  s0, a0
 move  s1, a1
 {StateMgrLoad}
 lw    t9, 0(a0)
 lw    t9, 0xa0(t9)               ; InSplitScreenMode()
 jalr  t9
 nop
 bnez  v0, ss
 nop
 move  a0, s0                     ; not split screen: the stock handler, untouched
 move  a1, s1
 ld    ra, 0x50(sp)
 lq    s0, 0x00(sp)
 lq    s1, 0x10(sp)
 lq    s2, 0x20(sp)
 lq    s3, 0x30(sp)
 addiu sp, sp, 0x60
 addiu sp, sp, -0x70              ; the two replaced prologue words
 j     {ORD_RESUME:#x}
 sd    ra, 0x50(sp)
ss:
 lw    v1, 0x28(s1)               ; payload count
 lw    a2, 0x24(s1)               ; payload array
 li    v0, 1
 beq   v1, v0, have               ; [avatar id]      -> Hold/Advance
 move  s3, zero
 li    v0, 2
 beq   v1, v0, have1              ; [key, avatar id] -> combat ROE
 li    s3, 1
 li    v0, 3
 bne   v1, v0, out                ; [key, avatar id, pressed] -> the Hold/Advance key,
 nop                              ;   reported on press and on release
 lw    t0, 0(a2)
 lw    t0, 8(t0)                  ; key code: pad 2's codes are pad 1's + 0xc5
 slti  t0, t0, 0xc5
 xori  t0, t0, 1
 sll   t0, t0, 2
 lui   t1, %hi({SLOT:#x})
 addiu t1, t1, %lo({SLOT:#x})
 addu  t1, t1, t0                 ; this pad's press time + 1 s (0 = none pending)
 lui   at, %hi({CLOCK:#x})
 lw    t2, %lo({CLOCK:#x})(at)    ; RSClock
 lwc1  $f0, 0xd4(t2)              ; game time, s
 lui   at, 0x3f80
 mtc1  at, $f1
 lw    t3, 8(a2)                  ; RSBool pressed
 lbu   t3, 8(t3)
 add.s $f0, $f0, $f1              ; now + 1
 beqz  t3, released
 lw    t4, 0(t1)
 b     out
 swc1  $f0, 0(t1)                 ; press: remember when
released:
 beqz  t4, out                    ; release without a press: ignore
 sw    zero, 0(t1)
 mtc1  t4, $f1
 lui   at, {TAP_HI:#x}
 mtc1  at, $f2
 sub.s $f0, $f0, $f1              ; held for
 li    s3, 2                      ; long press: move to where I'm aiming
 c.lt.s $f0, $f2
 nop
 bc1f  have1
 nop
 move  s3, zero                   ; tap: Hold/Advance
have1:
 addiu a2, a2, 4
have:
 lw    a0, 0(a2)                  ; the avatar-id payload
 lw    t0, 0(a0)
 lui   t1, %hi({RSIntVT:#x})
 addiu t1, t1, %lo({RSIntVT:#x})
 bne   t0, t1, out                ; stock bool messages are ignored
 nop
 jal   {ObjMgrGet:#x}
 lw    s2, 8(a0)                  ; the id
 lw    t9, 0(v0)
 move  a0, v0
 lw    t9, 0x38(t9)               ; ->GetObject(id), SimHuman+0x1b0
 jalr  t9
 move  a1, s2
 beqz  v0, out
 addiu s2, v0, -0x1b0
 lw    t9, 0(s2)
 lw    t9, {vOut:#x}(t9)          ; IsOutOfAction()
 jalr  t9
 move  a0, s2
 bnez  v0, out
 nop
 lw    t9, 0(s2)
 lw    t9, {vComp:#x}(t9)
 jalr  t9
 move  a0, s2
 sw    v0, 0x40(sp)
 lw    t9, 0(s2)
 lw    t9, {vPlat:#x}(t9)
 jalr  t9
 move  a0, s2
 sw    v0, 0x44(sp)
 lw    t9, 0(s2)
 lw    t9, {vFT:#x}(t9)
 jalr  t9
 move  a0, s2
 move  a3, v0
 lui   at, %hi({AIMgrPtr:#x})
 lw    a0, %lo({AIMgrPtr:#x})(at)
 beqz  a0, out
 lw    a1, 0x40(sp)
 lw    t9, 0(a0)
 lw    t9, 0x14(t9)               ; IkeAIMgr::GetFireTeamAI(company, platoon, fireteam)
 jalr  t9
 lw    a2, 0x44(sp)
 beqz  v0, out
 move  a0, v0
 li    t0, 1
 beq   s3, t0, combat
 nop
 bnez  s3, moveto
 nop
 lw    v1, 0x24(a0)               ; 0 Hold, 1 Advance, 2 Advance at all costs
 jal   {SetMove:#x}
 sltiu a1, v1, 1                  ; Hold -> Advance, else Hold
 b     out
 nop
combat:
 lw    v1, 0x28(a0)               ; 0 Recon, 1 Assault, 2 Suppress
 jal   {SetCombat:#x}
 addiu a1, v1, 1                  ; the setter wraps it
 b     out
 nop
moveto:
 jal   mv                         ; (FireTeamAI, SimHuman)
 move  a1, s2
out:
 ld    ra, 0x50(sp)
 lq    s0, 0x00(sp)
 lq    s1, 0x10(sp)
 lq    s2, 0x20(sp)
 lq    s3, 0x30(sp)
 jr    ra
 addiu sp, sp, 0x60
""".format(TAP_HI=_fbits_hi(MV_TAP), **g)


# frame of the move-to routine
_MV_F = 0x150
_MV_LINE, _MV_INFO, _MV_FAKE, _MV_PT, _MV_SPOT = 0x70, 0x90, 0x108, 0x130, 0x140   # FAKE+0x18 = 0x120 (16-aligned)


def _mv_src(g):
    V = g["VEC"]
    return """
mv:                                   ; a0 = FireTeamAI, a1 = the ordering player's SimHuman
 addiu sp, sp, -{F:#x}
 sd    ra, 0x60(sp)
 sq    s0, 0x00(sp)
 sq    s1, 0x10(sp)
 sq    s2, 0x20(sp)
 sq    s3, 0x30(sp)
 sq    s4, 0x40(sp)
 sq    s5, 0x50(sp)
 move  s0, a0
 move  s1, a1
 lw    a0, 0x38(s1)                   ; RSSimController::GetSimRoom
 beqz  a0, mv_out
 lw    t0, {EYE:#x}(s1)               ; RSLine3: the eye, along the look vector
 lw    t1, {EYE4:#x}(s1)
 lw    t2, {EYE8:#x}(s1)
 sw    t0, {LINE:#x}(sp)
 sw    t1, {LINE4:#x}(sp)
 sw    t2, {LINE8:#x}(sp)
 lw    t0, {LOOK:#x}(s1)
 lw    t1, {LOOK4:#x}(s1)
 lw    t2, {LOOK8:#x}(s1)
 sw    t0, {LV:#x}(sp)
 sw    t1, {LV4:#x}(sp)
 sw    t2, {LV8:#x}(sp)
 addiu a1, sp, {LINE:#x}
 addiu a2, sp, {INFO:#x}              ; RSLineCollisionInfo
 move  a3, zero                       ; no shooter
 addiu t0, zero, 0x81a                ; kIsGunshot | kLineIgnoreAllControllers
 addiu t1, zero, 1                    ; kGunshotTransparent
 move  t2, zero
 lui   at, {REACH_HI:#x}
 mtc1  at, $f12
 jal   {FLC:#x}                       ; RSSimRoom::FindLineCollision
 move  t3, zero
 andi  v0, v0, 0xff
 beqz  v0, mv_out                     ; nothing within reach: no order
 lwc1  $f0, {HIT:#x}(sp)              ; hit point (info+0x10)
 lwc1  $f1, {HIT4:#x}(sp)
 lwc1  $f2, {HIT8:#x}(sp)
 lwc1  $f3, {LINE:#x}(sp)             ; eye
 lwc1  $f4, {LINE4:#x}(sp)
 lwc1  $f5, {LINE8:#x}(sp)
 lwc1  $f6, {LV:#x}(sp)               ; look
 lwc1  $f7, {LV4:#x}(sp)
 lwc1  $f8, {LV8:#x}(sp)
 sub.s $f0, $f0, $f3
 sub.s $f1, $f1, $f4
 sub.s $f2, $f2, $f5
 mul.s $f0, $f0, $f6
 mul.s $f1, $f1, $f7
 mul.s $f2, $f2, $f8
 add.s $f0, $f0, $f1
 add.s $f0, $f0, $f2                  ; t = distance along the ray
 lui   at, {MINT_HI:#x}
 mtc1  at, $f9
 lui   at, {BACK_HI:#x}
 mtc1  at, $f10
 c.lt.s $f0, $f9
 nop
 bc1t  mv_out                         ; closer than MIN_T: not an order
 sub.s $f0, $f0, $f10                 ; pulled back from the surface
 mul.s $f6, $f6, $f0
 mul.s $f7, $f7, $f0
 mul.s $f8, $f8, $f0
 lui   at, {LIFT_HI:#x}
 mtc1  at, $f9
 add.s $f3, $f3, $f6
 add.s $f4, $f4, $f7
 add.s $f5, $f5, $f8
 add.s $f5, $f5, $f9                  ; and lifted, so the floor lookup sees it from above
 swc1  $f3, {PT:#x}(sp)
 swc1  $f4, {PT4:#x}(sp)
 swc1  $f5, {PT8:#x}(sp)
 addiu a0, sp, {FAKE:#x}              ; scratch LocationBehavior: SetLocation finds the level
 jal   {SETLOC:#x}                    ;   and moves the point off obstacles
 addiu a1, sp, {PT:#x}
 beqz  v0, mv_out                     ; no floor under it / stuck in a wall: no order
 lw    t0, {FV:#x}(sp)                ; the validated point is the order
 lw    t1, {FV4:#x}(sp)
 lw    t2, {FV8:#x}(sp)
 sw    t0, {PT:#x}(sp)
 sw    t1, {PT4:#x}(sp)
 sw    t2, {PT8:#x}(sp)
 lw    t0, 0xc(s0)                    ; the fireteam holds: TeamHoldBehavior on top of its script
 lw    t0, 4(t0)
 beqz  t0, push
 nop
 lw    t1, 4(t0)
 li    t2, 0x24
 beq   t1, t2, hold
 nop
push:
 li    t1, 1
 sw    t1, 0x1c(s0)                   ; not Hold, so the setter acts (JS returns early otherwise)
 move  a0, s0
 jal   {SETMOVEROE:#x}                ; SetMovementROE(Hold): drops a fight/investigation, pushes TeamHold
 move  a1, zero
 lw    t0, 0xc(s0)
 lw    t0, 4(t0)
 beqz  t0, desired
 nop
 lw    t1, 4(t0)
 li    t2, 0x24
 bne   t1, t2, desired
 nop
hold:
 li    t1, 1
 sb    t1, {HOLDINIT:#x}(t0)          ; initialised: its first Process would clear the orders below
desired:
 move  a0, s0
 jal   {SetMove:#x}                   ; SetDesiredMovementROE(Hold): UpdateMovementROE leaves it
 move  a1, zero
 move  s2, zero                       ; member index
 move  s3, zero                       ; members ordered so far
loop:
 lw    t0, 0x18(s0)                   ; member count
 slt   t0, s2, t0
 beqz  t0, mv_out
 lw    t1, 0x14(s0)                   ; RSArray<HumanAI*> data
 sll   t0, s2, 2
 addu  t1, t1, t0
 lw    s4, 0(t1)                      ; HumanAI
 beqz  s4, loop
 addiu s2, s2, 1
 lw    t0, 0x14(s4)                   ; its SimHuman
 beqz  t0, loop
 nop
 bne   t0, s1, notme
 lui   t1, 0x4973
 sw    zero, 0x8c(s4)                 ; the ordering player: no destination, so
 sw    zero, 0x90(s4)                 ;   TeamHold::IsPlayerDoingHisPart stays true
 sw    zero, 0x94(s4)                 ;   wherever he walks
 ori   t1, t1, 0xa710
 b     loop
 sw    t1, 0x98(s4)                   ; 998001.0 = 999^2, the engine's "far"
notme:
 lw    t1, 0x138(t0)                  ; control type: 1 = AI
 li    t2, 1
 bne   t1, t2, loop
 nop
 jal   {ACCEPT:#x}                    ; HumanAI::AcceptingOrders
 move  a0, s4
 beqz  v0, loop
 lw    t0, {PT:#x}(sp)                ; this member's spot: the point, or SPACE m per
 lw    t1, {PT4:#x}(sp)               ;   earlier member to the right of the aim
 lw    t2, {PT8:#x}(sp)
 sw    t0, {SPOT:#x}(sp)
 sw    t1, {SPOT4:#x}(sp)
 beqz  s3, spot
 sw    t2, {SPOT8:#x}(sp)
 lwc1  $f0, {LV:#x}(sp)               ; lx
 lwc1  $f1, {LV4:#x}(sp)              ; ly
 mul.s $f2, $f0, $f0
 mul.s $f3, $f1, $f1
 lui   at, 0x3500                     ; 4.8e-7, for a look straight down
 mtc1  at, $f4
 add.s $f2, $f2, $f3
 mtc1  s3, $f5
 add.s $f2, $f2, $f4
 sqrt.s $f2, $f2                      ; |horizontal look|
 cvt.s.w $f5, $f5                     ; k
 lui   at, {SPACE_HI:#x}
 mtc1  at, $f6
 nop
 mul.s $f5, $f5, $f6                  ; k * SPACE
 div.s $f5, $f5, $f2
 nop
 nop
 mul.s $f1, $f1, $f5                  ; right = (ly, -lx, 0) / |h|
 mul.s $f0, $f0, $f5
 lwc1  $f2, {SPOT:#x}(sp)
 lwc1  $f3, {SPOT4:#x}(sp)
 add.s $f2, $f2, $f1
 sub.s $f3, $f3, $f0
 swc1  $f2, {SPOT:#x}(sp)
 swc1  $f3, {SPOT4:#x}(sp)
 addiu a0, sp, {FAKE:#x}              ; is the offset spot usable?
 jal   {SETLOC:#x}
 addiu a1, sp, {SPOT:#x}
 lw    t0, {FV:#x}(sp)                ; yes: the validated spot
 lw    t1, {FV4:#x}(sp)
 bnez  v0, spot_ok
 lw    t2, {FV8:#x}(sp)
 lw    t0, {PT:#x}(sp)                ; no: the point itself
 lw    t1, {PT4:#x}(sp)
 lw    t2, {PT8:#x}(sp)
spot_ok:
 sw    t0, {SPOT:#x}(sp)
 sw    t1, {SPOT4:#x}(sp)
 sw    t2, {SPOT8:#x}(sp)
spot:
 lw    a0, 0xc(s4)                    ; what GiveMoveOrders gives a leader: ClearScript,
 jal   {CLEAR:#x}
 nop
 lui   at, %hi({AIMgrPtr:#x})
 jal   {POOLLOC:#x}                   ; a pooled LocationBehavior,
 lw    a0, %lo({AIMgrPtr:#x})(at)
 move  s5, v0
 move  a0, v0
 jal   {SETLOC:#x}                    ; SetLocation,
 addiu a1, sp, {SPOT:#x}
 beqz  v0, loop                       ; (validated above; GiveMoveOrders also just drops it)
 lw    a0, 0xc(s4)
 jal   {ADDELEM:#x}                   ; AddElement,
 move  a1, s5
 lw    t0, 0x18(s5)                   ; destination + closest-approach reset
 lw    t1, 0x1c(s5)
 lw    t2, 0x20(s5)
 sw    t0, 0x8c(s4)
 sw    t1, 0x90(s4)
 sw    t2, 0x94(s4)
 lui   t0, 0x4973
 ori   t0, t0, 0xa710
 sw    t0, 0x98(s4)
 b     loop
 addiu s3, s3, 1
mv_out:
 ld    ra, 0x60(sp)
 lq    s0, 0x00(sp)
 lq    s1, 0x10(sp)
 lq    s2, 0x20(sp)
 lq    s3, 0x30(sp)
 lq    s4, 0x40(sp)
 lq    s5, 0x50(sp)
 jr    ra
 addiu sp, sp, {F:#x}
""".format(F=_MV_F, LINE=_MV_LINE, LINE4=_MV_LINE + 4, LINE8=_MV_LINE + 8,
           LV=_MV_LINE + V, LV4=_MV_LINE + V + 4, LV8=_MV_LINE + V + 8,
           INFO=_MV_INFO, HIT=_MV_INFO + 0x10, HIT4=_MV_INFO + 0x14, HIT8=_MV_INFO + 0x18,
           FAKE=_MV_FAKE, FV=_MV_FAKE + 0x18, FV4=_MV_FAKE + 0x1C, FV8=_MV_FAKE + 0x20,
           PT=_MV_PT, PT4=_MV_PT + 4, PT8=_MV_PT + 8, SPOT=_MV_SPOT, SPOT4=_MV_SPOT + 4,
           SPOT8=_MV_SPOT + 8,
           EYE=g["EYE"], EYE4=g["EYE"] + 4, EYE8=g["EYE"] + 8,
           LOOK=g["LOOK"], LOOK4=g["LOOK"] + 4, LOOK8=g["LOOK"] + 8,
           REACH_HI=_fbits_hi(MV_REACH), MINT_HI=_fbits_hi(MV_MIN_T), BACK_HI=_fbits_hi(MV_BACK),
           LIFT_HI=_fbits_hi(MV_LIFT), SPACE_HI=_fbits_hi(MV_SPACE),
           **{k: v for k, v in g.items() if k not in ("EYE", "LOOK")})


for _k, _g in ORD.items():
    _g["STOCK"] = _stock_words(_g["CAVE"], _g["stock_hex"])
    _g["STOCK"][_g["MAP_HOOK"][0]] = _g["MAP_HOOK"][1]
    _g["STOCK"][_g["ORD_HOOK"]] = _g["ORD_STOCK"][0]
    _g["STOCK"][_g["ORD_HOOK"] + 4] = _g["ORD_STOCK"][1]
    for _va, _s, _n in _g["words"]:
        _g["STOCK"][_va] = _s
GR_STOCK.update(ORD["GR"]["STOCK"])
JS_STOCK.update(ORD["JS"]["STOCK"])


def _orders_edits(g):
    mw, _ = assemble(_ord_map_src(g), g["CAVE"])
    ord_base = g["CAVE"] + 4 * len(mw)
    ow, _ = assemble(_ord_src(g) + _mv_src(g), ord_base)
    words = mw + ow
    if len(words) > len("".join(g["stock_hex"].split())) // 8:
        raise ValueError("orders routines outgrow their stock table")
    st = g["STOCK"]
    out = [(g["CAVE"] + 4 * i, w, st[g["CAVE"] + 4 * i], "orders + switching: routine")
           for i, w in enumerate(words)]
    va, s = g["MAP_HOOK"]
    out.append((va, assemble("jal %#x" % g["CAVE"], va)[0][0], s,
                "orders + switching: bind both players' keys"))
    out.append((g["ORD_HOOK"], assemble("j %#x" % ord_base, g["ORD_HOOK"])[0][0],
                g["ORD_STOCK"][0], "orders + switching: 0x22 through the orders routine"))
    out.append((g["ORD_HOOK"] + 4, 0, g["ORD_STOCK"][1], "orders + switching: delay slot"))
    for va, s, n in g["words"]:
        out.append((va, n, s, "orders + switching: switch by avatar id"))
    return out


def _bh_edits(src, cave, hook, hook_stock, stock):
    out = []
    for i, w in enumerate(assemble(src, cave)[0]):
        va = cave + 4 * i
        out.append((va, w, stock[va], "split-screen bullet holes: routine"))
    out.append((hook, assemble("jal %#x" % cave, hook)[0][0], hook_stock,
                "split-screen bullet holes: water ripples + holes per viewport"))
    return out


def _handoff_edits(src, cave, b1, table, new, stock):
    out = []
    words = assemble(src, cave)[0]
    for i, w in enumerate(words):
        va = cave + 4 * i
        out.append((va, w, stock[va], "one life: handoff cave"))
    out.append((b1, assemble("j %#x" % cave, b1)[0][0], table[b1],
                "one life: split screen hands over instead of returning"))
    for va, w in new.items():
        out.append((va, w, table[va], "one life: handoff"))
    return out


def gr_edits(fireteams: bool, handoff: bool = False, bullet_holes: bool = False,
             briefing: bool = False, teammates: bool = False, orders: bool = False,
             js_controls: bool = False):
    """(va, value, stock, note) for the chosen Ghost Recon options.
    `teammates` (single player's roster) needs `briefing` and replaces it;
    `orders` needs `handoff`; `js_controls`: Jungle Storm's pad layout is on
    (grcontrols), so the orders' keys follow it."""
    out = []
    if orders and handoff:
        g = dict(ORD["GR"], keys=GR_JS_LAYOUT_KEYS) if js_controls else ORD["GR"]
        out += _orders_edits(g)
    if teammates and briefing:
        out += _spr_edits(GR_SPR_SRC, GR_UI_CAVE, GR_SPR_SYMS, GR_SPR_HOOKS,
                          GR_SPR_P2, GR_STOCK)
        briefing = False
    if briefing:
        out += _brief_edits(GR_BRIEF_SRC, GR_UI_CAVE, GR_UI_SYMS, GR_BRIEF_HOOKS, GR_STOCK)
    if bullet_holes:
        out += _bh_edits(GR_BH_SRC, GR_BH_CAVE, GR_BH_HOOK, GR_BH_HOOK_STOCK, GR_STOCK)
    if handoff:
        out += _handoff_edits(GR_HANDOFF_SRC, GR_HANDOFF_CAVE, 0x0039673C,
                              GR_HANDOFF, GR_HANDOFF_NEW, GR_STOCK)
    if fireteams:
        for i, w in enumerate(gr_roster_words()):
            va = GR_CAVE + 4 * i
            out.append((va, w, GR_STOCK[va], "split-screen fireteams: cave"))
        hook = assemble("j %#x" % GR_CAVE, GR_HOOK)[0][0]
        out.append((GR_HOOK, hook, GR_HOOK_STOCK,
                    "split-screen fireteams: after the 1P/2P actor loop"))
    return out


def js_edits(fireteams: bool, handoff: bool = False, bullet_holes: bool = False,
             briefing: bool = False, teammates: bool = False, orders: bool = False):
    """(va, value, stock, note) for the chosen Jungle Storm options.
    `teammates` (single player's roster) needs `briefing` and replaces it;
    `orders` needs `handoff`."""
    out = []
    if orders and handoff:
        out += _orders_edits(ORD["JS"])
    if teammates and briefing:
        out += _spr_edits(JS_SPR_SRC, JS_UI_CAVE, JS_SPR_SYMS, JS_SPR_HOOKS,
                          JS_SPR_P2, JS_STOCK)
        briefing = False
    if briefing:
        out += _brief_edits(JS_BRIEF_SRC, JS_UI_CAVE, JS_UI_SYMS, JS_BRIEF_HOOKS, JS_STOCK)
    if bullet_holes:
        out += _bh_edits(JS_BH_SRC, JS_BH_CAVE, JS_BH_HOOK, JS_BH_HOOK_STOCK, JS_STOCK)
    if handoff:
        out += _handoff_edits(JS_HANDOFF_SRC, JS_HANDOFF_CAVE, 0x003745DC,
                              JS_HANDOFF, JS_HANDOFF_NEW, JS_STOCK)
    if fireteams:
        for i, w in enumerate(js_roster_words()):
            va = JS_CAVE + 4 * i
            out.append((va, w, JS_STOCK[va], "split-screen fireteams: cave"))
        hook = assemble("jal %#x" % JS_CAVE, JS_HOOK)[0][0]
        out.append((JS_HOOK, hook, JS_HOOK_STOCK,
                    "split-screen fireteams: after the 1P/2P actor loop"))
    return out


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------

#: instruction words read out of SLUS_206.13, with the source that must
#: assemble to each at that address
_ENCODER_CASES = (
    (0x0039E040, "addiu sp, sp, -0xa0", 0x27BDFF60),
    (0x0039E044, "sd ra, 64(sp)", 0xFFBF0040),
    (0x0039E048, "sq s3, 48(sp)", 0x7FB30030),
    (0x0039E058, "jal 0x35fd20", 0x0C0D7F48),
    (0x0039E064, "lw t9, 0x184(t9)", 0x8F390184),
    (0x0039E068, "jalr t9", 0x0320F809),
    (0x0039E09C, "beqz v1, 0x39e0c4", 0x10600009),
    (0x0039E0C4, "lui at, 0x5f", 0x3C01005F),
    (0x0039E0C8, "sw zero, -0x5300(at)", 0xAC20AD00),
    (0x0039E188, "bnez v0, 0x39e10c", 0x1440FFE0),
    (0x0039E368, "jr ra", 0x03E00008),
    (0x003A0BB0, "sltu v0, s2, s1", 0x0251102B),
    (0x003A0B44, "beqz at, 0x3a0bc0", 0x1020001E),
    (0, "sll v1, s1, 2", 0x00111880),
    (0, "slti v0, s1, 3", 0x2A220003),
    (0, "addu v0, v0, v1", 0x00431021),
    (0, "lbu v1, 0x644(s5)", 0x92A30644),
    (0, "lq s0, 0(sp)", 0x7BB00000),
    (0, "ld ra, 64(sp)", 0xDFBF0040),
    (0, "andi v1, v0, 0xffff", 0x3043FFFF),
    (0, "lui at, %hi(0x55ff70)", 0x3C010056),
    (0, "lw a1, %lo(0x55ff70)(at)", 0x8C25FF70),
    (0, "addiu a2, v0, %lo(0x583d70)", 0x24463D70),
    (0x003384C0, "j 0x336000", 0x080CD800),
)


def selftest(gr_elf_bytes=None, js_elf_bytes=None):
    """Return a list of failures (empty = pass). With the real executables,
    also check every recorded stock word."""
    import struct
    fails = []
    for pc, src, want in _ENCODER_CASES:
        got = assemble(src, pc)[0][0]
        if got != want:
            fails.append("encode %r: %08x != %08x" % (src, got, want))
    for name, words, room, stock in (
            ("GR", gr_roster_words(), GR_CAVE_BYTES, GR_STOCK),
            ("JS", js_roster_words(), JS_CAVE_BYTES, JS_STOCK)):
        if len(words) * 4 > room:
            fails.append("%s roster cave too big" % name)
        # every word any option combination writes has its stock value on record
        fn = gr_edits if name == "GR" else js_edits
        for combo in ((True, True, True, True, True, True),
                      (True, True, True, True, False, True),
                      (True, False, False, False, False, False)):
            for va, _w, s, _n in fn(*combo):
                if stock.get(va) != s:
                    fails.append("%s %08x: edit stock %08x, table %s"
                                 % (name, va, s, stock.get(va)))
    # the three routines must not overlap and must stay inside the dead function
    for name, base, room, parts in (
            ("GR", GR_CAVE, GR_CAVE_BYTES,
             ((GR_CAVE, len(gr_roster_words())),
              (GR_HANDOFF_CAVE, len(assemble(GR_HANDOFF_SRC, GR_HANDOFF_CAVE)[0])),
              (GR_BH_CAVE, len(assemble(GR_BH_SRC, GR_BH_CAVE)[0])))),
            ("JS", JS_CAVE, JS_CAVE_BYTES,
             ((JS_CAVE, len(js_roster_words())),
              (JS_HANDOFF_CAVE, len(assemble(JS_HANDOFF_SRC, JS_HANDOFF_CAVE)[0])),
              (JS_BH_CAVE, len(assemble(JS_BH_SRC, JS_BH_CAVE)[0]))))):
        spans = sorted((s, s + 4 * n) for s, n in parts)
        for (a0, a1), (b0, _b1) in zip(spans, spans[1:]):
            if a1 > b0:
                fails.append("%s routines overlap at %08x" % (name, b0))
        if spans[0][0] < base or spans[-1][1] > base + room:
            fails.append("%s routines leave the cave" % name)
    for elf, stock, delta in ((gr_elf_bytes, GR_STOCK, 0x80),
                              (js_elf_bytes, JS_STOCK, 0x100)):
        if elf is None:
            continue
        for va, want in stock.items():
            got = struct.unpack_from("<I", elf, va - 0x00100000 + delta)[0]
            if got != want:
                fails.append("stock %08x: disc %08x, recorded %08x" % (va, got, want))
    return fails

"""Heroes Unleashed spotting distances: Ghost Recon (SLUS-20613) and Jungle Storm (SLUS-20820).

An enemy's sight is capped by the level's spotting distance (the .ENV's
MaxSpot) times a difficulty factor. The PS2 games ship the PC's own per-map
numbers (40-125 m; identical on every map both have). Heroes Unleashed, the PC
realism mod, "corrected" them on every map, mostly to 150 m, a few denser maps
to 45-100 m, and two open ones down (Airbase 120 -> 100, the range 200 -> 150).

The level-file card cannot write these: a two-digit MaxSpot in a compressed
.ENV cannot grow a digit. So this sets the number in code, after the game has
read it. EnvironmentFile::Load (GR 0x001CDE00) stores MaxSpot at +0x90 in the
delay slot of the branch that ends that tag; the branch becomes a jump to a
routine that takes the map's name (MapFileName, the RSFilename at +0x50,
parsed earlier in every PS2 .ENV), keeps what follows its last '\' or '/' up
to the first '.', lower-cases it, hashes it (h = h * 33 ^ c, 24 bits) and
looks it up in a table of (hash, metres). A map in the table gets HU's number;
any other keeps its own. Levels that share a map (the Tactical Training
missions use the multiplayer maps) share its number.

Maps Heroes Unleashed does not ship (Jungle Storm's own campaign, most of
Urban Operations, Depot, the shooting range) get the stock number times HU's
median change (1.67), at most 150 m. A level whose .ENV has no MaxSpot at all
(Vilnius, two multiplayer maps) never reaches the hook and keeps the game's
default.

Cave: sceSifGetIopAddr + sceSifSetIopAddr (GR 0x004198B8, JS twins
0x001825C8), 464 bytes, unreferenced in the loaded image and Jungle Storm's
overlays. Not yet played.
"""

from __future__ import annotations

from .grasm import assemble

GAMES = {
    "gr": dict(
        CAVE=0x004198B8, CAVE_END=0x00419A88,
        HOOK=0x001CE064, HOOK_STOCK=0x1000023E,   # b 0x1ce960 (slot: swc1 f0,0x90(s4) stays)
        BACK=0x001CE960, ENV="s4",
    ),
    "js": dict(
        CAVE=0x001825C8, CAVE_END=0x00182798,
        HOOK=0x001CB5E4, HOOK_STOCK=0x10000204,   # b 0x1cbdf8 (slot: swc1 f0,0x90(s1) stays)
        BACK=0x001CBDF8, ENV="s1",
    ),
}
NAME, SPOT = 0x50, 0x90                         # EnvironmentFile: MapFileName, MaxSpot

#: (map base name, 24-bit hash, metres): every PS2 map, HU's number or stock x1.67 (<= 150)
TABLES = {
    "gr": [
    ("d01_beach", 0xD6F5F7, 100),
    ("d02_refinery", 0xB14A61, 150),
    ("d03_depot", 0x4A6332, 150),   # not in HU: stock x1.67
    ("d04_riverbed", 0xCFAC86, 150),
    ("d05_aurora", 0xF36B24, 100),
    ("d06_ghosttown", 0xF22FB8, 150),
    ("d07_roadblock", 0x3838ED, 150),
    ("d08_tank", 0x352DE3, 150),
    ("dp01_stronghold", 0x8A5416, 150),
    ("dp02_farm_day", 0x1811B2, 150),
    ("dp03_creekbed", 0xB911B1, 150),
    ("dp04_wilderness", 0xC53865, 150),
    ("dp05_ravine", 0x709229, 150),
    ("m01_caves", 0x66BB71, 150),
    ("m02_farm", 0xB45808, 100),
    ("m03_rrbridge", 0x8393AE, 150),
    ("m04_village", 0x4433EA, 150),
    ("m05_embassy", 0x0A48C5, 150),
    ("m06_castle", 0x07D958, 100),
    ("m07_river", 0xB8C7EF, 150),
    ("m08_battlefield", 0x8ADED2, 150),
    ("m09_swamp", 0xCFE463, 45),
    ("m11_pow_camp", 0x74B87A, 100),
    ("m12_docks", 0x299381, 100),
    ("m13_airbase", 0xD90C9F, 100),
    ("m14_mountain", 0xF395BC, 150),
    ("m15_red_square", 0x10C0DB, 150),
    ("mp01_river", 0x61CC79, 150),
    ("mp02_nightbattle", 0xDFA496, 100),
    ("mp03_railroad", 0x9331AF, 90),
    ("mp04_valley", 0xCF142D, 150),
    ("mp05_docks", 0x99AC37, 150),
    ("tac01_shooting", 0xDC7AA7, 125),   # not in HU: stock x1.67
    ("training", 0x4FC460, 150),
    ],
    "js": [
    ("c01_plantation", 0xACB0A7, 150),
    ("c02_military_camp", 0x756341, 150),
    ("c03_high_sierra", 0x24BF70, 150),
    ("c04_swamp_airfield", 0x44B8A7, 63),
    ("c05_bridges", 0xC05A55, 100),
    ("c06_polling_center", 0xD97A71, 150),
    ("c07_beach_resort", 0x6FA904, 150),
    ("c08_mountain_stronghold", 0x8B2AFC, 150),
    ("cp01_hunting_lodge", 0xEE22D0, 150),
    ("cp02_island", 0xD8E433, 150),
    ("cp03_prison", 0x7EC3F6, 150),   # not in HU: stock x1.67
    ("cp04_island_village", 0xDAD4F6, 100),
    ("cp05_market", 0xAB45ED, 150),
    ("dp01_stronghold", 0x8A5416, 150),
    ("dp02_farm_day", 0x1811B2, 150),
    ("dp03_creekbed", 0xB911B1, 150),
    ("dp04_wilderness", 0xC53865, 150),
    ("dp05_ravine", 0x709229, 150),
    ("g02_village", 0x2B3966, 117),   # not in HU: stock x1.67
    ("g03_the_rock", 0x488A48, 117),   # not in HU: stock x1.67
    ("g04_train", 0x5F125C, 117),   # not in HU: stock x1.67
    ("g05_dock", 0xB3819E, 142),   # not in HU: stock x1.67
    ("mp01_river", 0x61CC79, 150),
    ("mp02_nightbattle", 0xDFA496, 100),
    ("mp03_railroad", 0x9331AF, 90),
    ("mp04_valley", 0xCF142D, 150),
    ("mp05_docks", 0x99AC37, 150),
    ("training", 0x4FC460, 150),
    ("u01_transmission", 0x43751D, 133),   # not in HU: stock x1.67
    ("u02_river", 0xB22672, 100),   # not in HU: stock x1.67
    ("u03_rescue", 0xB1323E, 125),   # not in HU: stock x1.67
    ("u05_rail", 0xAD89D9, 150),   # not in HU: stock x1.67
    ],
}

SRC = """
spot:                                   ; j from EnvironmentFile::Load; MaxSpot is already stored
    lw      t0, {NAME}+4({ENV})         ; MapFileName: its string rep
    beqz    t0, back
    nop
    lw      t0, 4(t0)                   ; its characters
    beqz    t0, back
    move    t1, t0                      ; where the base name starts
find:
    lbu     t2, 0(t0)
    beqz    t2, hash0
    addiu   t0, t0, 1
    addiu   t3, t2, -0x5c               ; a backslash
    beqz    t3, sep
    addiu   t3, t2, -0x2f               ; a slash
    bnez    t3, find
    nop
sep:
    b       find
    move    t1, t0                      ; the name starts after it
hash0:
    move    t4, zero
hash:
    lbu     t2, 0(t1)
    beqz    t2, look
    addiu   t3, t2, -0x2e               ; '.' ends it
    beqz    t3, look
    addiu   t1, t1, 1
    addiu   t3, t2, -0x41
    sltiu   t3, t3, 26
    beqz    t3, lower
    nop
    addiu   t2, t2, 0x20                ; A-Z -> a-z
lower:
    sll     t3, t4, 5
    addu    t4, t3, t4                  ; h * 33
    b       hash
    xor     t4, t4, t2                  ; ^ c
look:
    sll     t4, t4, 8                   ; the low 24 bits, where the table keeps them
    lui     t5, %hi(table)
    addiu   t5, t5, %lo(table)
next:
    lw      t6, 0(t5)
    beqz    t6, back                    ; not a map we know: as shipped
    addiu   t5, t5, 4
    xor     t7, t6, t4
    srl     t7, t7, 8
    bnez    t7, next
    nop
    andi    t6, t6, 0xff                ; metres
    mtc1    t6, f0
    nop
    cvt.s.w f0, f0
    swc1    f0, {SPOT}({ENV})
back:
    j       {BACK:#x}
    nop
table:
"""


def words(game: str):
    g = GAMES[game]
    src = SRC.format(NAME=NAME, SPOT=SPOT, **g)
    src += "".join("    .word   %#x\n" % ((h << 8) | m) for _n, h, m in TABLES[game]) + "    .word   0\n"
    w, _ = assemble(src, g["CAVE"])
    if g["CAVE"] + 4 * len(w) > g["CAVE_END"]:
        raise ValueError("spotting table outgrows its cave")
    return w


_GR_CAVE_STOCK_HEX = (   # sceSifGetIopAddr + sceSifSetIopAddr, 0x004198B8..0x00419A88
    "27BDFFA0 FFB30040 FFB20030 0080982D FFB00010 00A0902D FFBF0050 00C0802D"
    "0C10634A FFB10020 04410003 2E020003 10000027 3C02FFFF 10400020 3C11005F"
    "3C04005F 2622F640 AE33F640 0040382D AC500004 2484F840 24050003 AFA00000"
    "0000302D 24080020 00E0482D 240A0020 0C10531C 0000582D 04410004 00000000"
    "3C02FFFE 10000012 3442FFFF 16000004 24020001 9222F640 1000000C A2420000"
    "16020004 24020002 9622F640 10000007 A6420000 52020004 8E22F640 3C02FFFE"
    "10000003 3442FFFE AE420000 0000102D DFBF0050 DFB30040 DFB20030 DFB10020"
    "DFB00010 03E00008 27BD0060 00000000 27BDFFB0 FFB20030 FFB10020 0080902D"
    "FFB00010 00A0882D FFBF0040 0C10634A 00C0802D 04410003 3C07005F 10000025"
    "3C02FFFF 24E3F640 ACF2F640 16000004 AC700004 92220000 1000000D A0620008"
    "24020001 16020004 24020002 96220000 10000007 A4620008 52020004 8E220000"
    "3C02FFFE 10000013 3442FFFE AC620008 24E7F640 3C04005F 2484F840 AFA00000"
    "24050002 0000302D 24080020 00E0482D 240A0010 0C10531C 0000582D 3C04FFFE"
    "2403FFFF 0062182A 3484FFFF 0080102D 0003100B DFBF0040 DFB20030 DFB10020"
    "DFB00010 03E00008 27BD0050 00000000"
)
_JS_CAVE_STOCK_HEX = (   # their twins, 0x001825C8..0x00182798
    "27BDFFA0 FFB30040 FFB20030 0080982D FFB00010 00A0902D FFBF0050 00C0802D"
    "0C06068E FFB10020 04410003 2E020003 10000027 3C02FFFF 10400020 3C110062"
    "3C040062 262289C0 AE3389C0 0040382D AC500004 24848BC0 24050003 AFA00000"
    "0000302D 24080020 00E0482D 240A0020 0C05F5AA 0000582D 04410004 00000000"
    "3C02FFFE 10000012 3442FFFF 16000004 24020001 922289C0 1000000C A2420000"
    "16020004 24020002 962289C0 10000007 A6420000 52020004 8E2289C0 3C02FFFE"
    "10000003 3442FFFE AE420000 0000102D DFBF0050 DFB30040 DFB20030 DFB10020"
    "DFB00010 03E00008 27BD0060 00000000 27BDFFB0 FFB20030 FFB10020 0080902D"
    "FFB00010 00A0882D FFBF0040 0C06068E 00C0802D 04410003 3C070062 10000025"
    "3C02FFFF 24E389C0 ACF289C0 16000004 AC700004 92220000 1000000D A0620008"
    "24020001 16020004 24020002 96220000 10000007 A4620008 52020004 8E220000"
    "3C02FFFE 10000013 3442FFFE AC620008 24E789C0 3C040062 24848BC0 AFA00000"
    "24050002 0000302D 24080020 00E0482D 240A0010 0C05F5AA 0000582D 3C04FFFE"
    "2403FFFF 0062182A 3484FFFF 0080102D 0003100B DFBF0040 DFB20030 DFB10020"
    "DFB00010 03E00008 27BD0050 00000000"
)


def _stock_words(base, hexwords):
    ws = "".join(hexwords.split())
    return {base + 4 * i: int(ws[8 * i:8 * i + 8], 16) for i in range(len(ws) // 8)}


GR_STOCK = _stock_words(GAMES["gr"]["CAVE"], _GR_CAVE_STOCK_HEX)
JS_STOCK = _stock_words(GAMES["js"]["CAVE"], _JS_CAVE_STOCK_HEX)
GR_STOCK[GAMES["gr"]["HOOK"]] = GAMES["gr"]["HOOK_STOCK"]
JS_STOCK[GAMES["js"]["HOOK"]] = GAMES["js"]["HOOK_STOCK"]


def h24(name: str) -> int:
    """The routine's hash of a lower-case base name."""
    h = 0
    for ch in name.encode("latin1"):
        c = ch + 0x20 if 0x41 <= ch <= 0x5A else ch
        h = ((h * 33) & 0xFFFFFFFF) ^ c
    return h & 0xFFFFFF


def edits(game: str):
    """(va, value, stock, note)."""
    g = GAMES[game]
    st = GR_STOCK if game == "gr" else JS_STOCK
    out = [(g["CAVE"] + 4 * i, w, st[g["CAVE"] + 4 * i], "HU spotting: per-map distances")
           for i, w in enumerate(words(game))]
    out.append((g["HOOK"], assemble("j %#x" % g["CAVE"], g["HOOK"])[0][0], g["HOOK_STOCK"],
                "HU spotting: after MaxSpot is read"))
    return out


def gr_edits(v: dict):
    return edits("gr") if v.get("gr_hu_spot") or v.get("gr_hu_all") else []


def js_edits(v: dict):
    return edits("js") if v.get("js_hu_spot") or v.get("js_hu_all") else []


def selftest(gr_elf: bytes, js_elf: bytes):
    """Stock words against the executables, table hashes, no address twice. [] = pass."""
    bad = []
    for game, st, elf, d in (("gr", GR_STOCK, gr_elf, 0x80), ("js", JS_STOCK, js_elf, 0x100)):
        for va, w in st.items():
            off = va - 0x100000 + d
            if int.from_bytes(elf[off:off + 4], "little") != w:
                bad.append("%s %08X" % (game, va))
        if any(h24(n) != h or not 0 < m < 256 for n, h, m in TABLES[game]):
            bad.append("%s table hash/metres" % game)
        if len({h for _n, h, _m in TABLES[game]}) != len(TABLES[game]):
            bad.append("%s hash collision" % game)
        e = edits(game)
        if len({va for va, *_ in e}) != len(e) or any(va not in st for va, *_ in e):
            bad.append("%s edit addresses" % game)
    return bad

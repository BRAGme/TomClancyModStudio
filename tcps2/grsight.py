"""Enemy sightlines and snipers: Ghost Recon (SLUS-20613) and Jungle Storm (SLUS-20820).

AwarenessMgr::CheckLineOfSight (GR 0x003F4010, JS 0x003D3EF0) decides whether a
soldier can see a target. Its first and hardest test is a distance cap: the
level's spotting distance (the .ENV MaxSpot, 48-125 across the campaign) times
a difficulty factor (IkeConstants +0x12C/+0x130/+0x134 -- 0.5 / 0.556 / 0.611;
JS +0x134..) times the player's stance. Stock never lets it pass 76 m. The
scope zoom, alertness, facing, light, movement and the target's signature only
scale detection *inside* that cap, and nothing later in the engagement chain
limits range: aim time grows with distance, the aim offset is fixed past 50 m,
and bullets fly 475-500 m. Nothing in the AI is sniper-specific except the
gun's WeaponMotionType (2 or 3: SVD, PSG1, M82, M98, M24, L96A1, SR25).

  * sight: the three difficulty-factor fetches (a one-line getter each) go
    through a routine that multiplies the factor by K for every hostile
    soldier (SimHuman::IsEnemy), and by K_sniper as well when his current gun
    is a sniper rifle. Allied script teams keep the stock factor; the players'
    squad never used it. No 99 cap, unlike the .ENV spotting card;
  * precision: hostile snipers skip the deliberate 0.10-0.25 m "enemy miss"
    EngageThreatBehavior::CalculateTargetPoint adds (the first of its two
    IsEnemy calls answers "no" for them), keeping only the +-0.10 m aim error;
  * draw distance: SimHuman::UpdateVisibility stops drawing soldiers past
    80 m (x sqrt(zoom) when scoped), per split-screen view
    (UpdateGlobalDistance, GR 0x003A11A8 / 0x003A1258). Enemy reach past that
    means being shot by soldiers you cannot see -- the existing "full
    strength" option already passes it on 12 of 23 Ghost Recon maps.

Caves: GR sceDevctl (0x00418448), JS the twin of GR's sceLseek64
(0x00180CD0), neither referenced from the loaded image (nor, for JS, the
online/offline overlays). The routines were run in an interpreter at the real
call sites against stubbed engine calls (every difficulty, hostile / allied,
each weapon type, null looker, register and stack preservation), and the
draw constant through the whole UpdateGlobalDistance. Not yet played.
"""

from __future__ import annotations

from .grasm import assemble

GAMES = {
    "gr": dict(
        CAVE=0x00418448, CAVE_END=0x00418680,        # sceDevctl, unreferenced
        ISENEMY=0x003DC850,                          # SimHuman::IsEnemy
        CWMT=0x003D90A0,                             # SimHuman::CurrentWeaponMotionType
        # CheckLineOfSight: the three difficulty-factor calls (jal getter ; move a0,v0)
        SITES=((0x003F441C, 0x0C0FD2F0, 0x12C),      # Recruit  -> IkeConstants+0x12c
               (0x003F44CC, 0x0C0FD2EC, 0x130),      # Veteran
               (0x003F457C, 0x0C0FD2E8, 0x134)),     # Elite
        DELAY_STOCK=0x70402628,                      # move a0, v0 (move128 form)
        PREC_HOOK=0x001B1900, PREC_STOCK=0x0C0F7214, # CalculateTargetPoint: 1st jal IsEnemy
        DRAW=(0x003A11A8, 0x003A1258),               # lui v0, 80.0 per viewport
    ),
    "js": dict(
        CAVE=0x00180CD0, CAVE_END=0x00180F08,        # twin of GR sceLseek64, unreferenced
        ISENEMY=0x003BC050,
        CWMT=0x003B89D0,
        SITES=((0x003D42C8, 0x0C0F528C, 0x134),
               (0x003D4378, 0x0C0F5288, 0x138),
               (0x003D4428, 0x0C0F5284, 0x13C)),
        DELAY_STOCK=0x0040202D,                      # move a0, v0 (daddu form)
        PREC_HOOK=0x001AEF00, PREC_STOCK=0x0C0EF014,
        DRAW=(0x00380014, 0x003800C8),
    ),
}
DRAW_STOCK = 0x3C0242A0                              # lui v0, 0x42a0 (80.0)

# hostile, script-controlled lookers only; s0 = the looking SimHuman at all three sites
SIGHT_SRC = """
sight:
    addiu sp, sp, -32
    sd    ra, 16(sp)
    lwc1  f0, 0(a0)             ; the stock factor for this difficulty
    beqz  s0, out
    swc1  f0, 0(sp)
    jal   {isenemy}             ; SimHuman::IsEnemy(looker)
    move  a0, s0
    beqz  v0, out               ; allied script teams keep the stock factor
    lui   v1, {kall}
    mtc1  v1, f1
    lwc1  f0, 0(sp)
    mul.s f0, f0, f1            ; every hostile
    swc1  f0, 0(sp)
    jal   {cwmt}                ; SimHuman::CurrentWeaponMotionType(looker)
    move  a0, s0
    addiu v0, v0, -2
    sltiu v0, v0, 2             ; 2 or 3 = sniper rifle
    beqz  v0, out
    lui   v1, {ksnp}
    mtc1  v1, f1
    lwc1  f0, 0(sp)
    mul.s f0, f0, f1            ; hostile sniper
    swc1  f0, 0(sp)
out:
    lwc1  f0, 0(sp)
    ld    ra, 16(sp)
    jr    ra
    addiu sp, sp, 32
"""

# replaces the FIRST `jal SimHuman::IsEnemy` in EngageThreatBehavior::CalculateTargetPoint:
# answers "not an enemy" for a hostile sniper, so his aim offset skips the extra
# GetEnemiesOffset() miss; the second IsEnemy call still picks the enemy formula
PREC_SRC = """
prec:
    addiu sp, sp, -16
    sd    ra, 0(sp)
    jal   {isenemy}             ; a0 = shooter SimHuman (caller's delay slot)
    sw    a0, 8(sp)
    beqz  v0, out               ; not hostile: 0, as stock
    nop
    jal   {cwmt}
    lw    a0, 8(sp)
    addiu v0, v0, -2
    sltiu v0, v0, 2             ; 1 = sniper rifle
    xori  v0, v0, 1             ; hostile sniper -> 0, other hostile -> 1
out:
    ld    ra, 0(sp)
    jr    ra
    addiu sp, sp, 16
"""

KALL = {"1": 0x3F80, "1.25": 0x3FA0, "1.5": 0x3FC0, "2": 0x4000, "3": 0x4040}
KSNP = {"1": 0x3F80, "1.5": 0x3FC0, "2": 0x4000, "3": 0x4040, "4": 0x4080}
DRAW = {"80": 0x42A0, "120": 0x42F0, "160": 0x4320, "240": 0x4370}

_GR_CAVE_STOCK_HEX = (   # sceDevctl, 0x00418448..0x00418680
    "27BDFF20 FFB10050 FFBE00C0 0080882D FFB700B0 0100F02D FFB600A0 00A0B82D"
    "FFB40080 0120B02D FFB00040 00C0A02D FFB20060 00E0802D FFBF00D0 24040017"
    "FFB50090 0C10563E FFB30070 3C02005F 2452E100 3C020057 8C43E1C0 54600004"
    "92220000 0C10567E 00000000 92220000 0000282D 00021E00 1060000E A242000C"
    "2E060401 24A50001 28A20400 1040000A 02251021 02452021 90430000 A083000C"
    "00031E00 5460FFF8 24A50001 10000003 24020400 2E060401 24020400 50A20001"
    "A240040B 10C00003 2EC20401 14400005 00000000 0C10564A 00000000 1000004A"
    "2402FFEA 12000010 0000282D 2646040C 27B30030 3C15005F 3C11005F 00000000"
    "02851021 00C52021 90430000 24A50001 00B0102B A0830000 1440FFF9 00000000"
    "10000005 AE500810 27B30030 3C15005F 3C11005F AE500810 24020001 AE57080C"
    "27A40010 AFA20014 2634ED40 3C02005F AFA00018 2450E100 0C1046B8 AFA00024"
    "0040882D AE560818 24020004 0200202D AE530004 2405081C AE420008 AE5E0814"
    "0C1050E0 AE510000 26A4F3C0 0200382D AFA00000 24050017 0000302D 2408081C"
    "0280482D 240A0004 0C10531C 0000582D 04410007 3C022000 0C1046BC 0220202D"
    "0C10564A 00000000 1000000F 2402FFF5 02821025 0C10564A 8C500000 16000005"
    "00000000 0C1046BC 0220202D 10000006 2402FFF5 0C1046C8 0220202D 0C1046BC"
    "0220202D 8FA20030 DFBF00D0 DFBE00C0 DFB700B0 DFB600A0 DFB50090 DFB40080"
    "DFB30070 DFB20060 DFB10050 DFB00040 03E00008 27BD00E0"
)
_JS_CAVE_STOCK_HEX = (   # sceLseek64 twin, 0x00180CD0..0x00180F08
    "27BDFF40 FFB40080 FFB20060 00C0A02D FFB50090 00A0902D FFB10050 3C150061"
    "FFB00040 26B17000 FFBF00B0 FFB600A0 0C05F7AE FFB30070 0040802D 0C05F8CC"
    "24040016 3C030057 8C624FEC 14400005 00000000 0C05F8D8 00000000 1000006C"
    "2402FFFF 12000004 00000000 8E130004 16600005 3C020062 0C05F8D8 00000000"
    "10000063 2402FFF7 8E030000 24428500 FE320010 02021023 AE23000C 00021103"
    "AE340018 AE22001C 24050001 27A40010 AFA50014 AFA00018 0C05E8B8 AFA00024"
    "0040902D 24030008 27A20030 AE230008 AE220004 32628000 10400024 AEB27000"
    "3C140057 0C05E8C8 8E844FFC 3C070057 0000302D 8CE34F68 2402FFFF 14620008"
    "3C160062 8EA37000 3C100061 00031023 ACE34F68 10000011 AEA27000 00000000"
    "3C100061 24C60001 28C20020 1040000B 00061080 24E34F68 00432821 2404FFFF"
    "8CA20000 1444FFF8 24C60001 8E220000 00021823 ACA20000 AE230000 0C05E8C0"
    "8E844FFC 10000004 26107C40 3C160062 3C100061 26107C40 26C48700 26A77000"
    "AFA00000 24050016 0000302D 24080020 0200482D 240A0004 0C05F5AA 0000582D"
    "04410007 3C022000 0C05E8BC 0240202D 0C05F8D8 00000000 10000015 2402FFF5"
    "02021025 0C05F8D8 8C500000 16000005 32628000 0C05E8BC 0240202D 1000000C"
    "2402FFF5 10400005 00000000 0C05E8BC 0240202D 10000006 0000102D 0C05E8C8"
    "0240202D 0C05E8BC 0240202D DFA20030 DFBF00B0 DFB600A0 DFB50090 DFB40080"
    "DFB30070 DFB20060 DFB10050 DFB00040 03E00008 27BD00C0"
)


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


GR_STOCK = _stock_words(GAMES["gr"]["CAVE"], _GR_CAVE_STOCK_HEX)
JS_STOCK = _stock_words(GAMES["js"]["CAVE"], _JS_CAVE_STOCK_HEX)
for _st, _g in ((GR_STOCK, GAMES["gr"]), (JS_STOCK, GAMES["js"])):
    for _va, _s, _off in _g["SITES"]:
        _st[_va] = _s
        _st[_va + 4] = _g["DELAY_STOCK"]
    _st[_g["PREC_HOOK"]] = _g["PREC_STOCK"]
    for _va in _g["DRAW"]:
        _st[_va] = DRAW_STOCK


def edits(game: str, kall: str = "1", ksnp: str = "1", prec: bool = False, draw: str = "80"):
    """(va, value, stock, note)."""
    g = GAMES[game]
    st = GR_STOCK if game == "gr" else JS_STOCK
    out = []
    if kall != "1" or ksnp != "1" or prec:
        sw, _ = assemble(SIGHT_SRC.format(isenemy="%#x" % g["ISENEMY"], cwmt="%#x" % g["CWMT"],
                                          kall="%#x" % KALL[kall], ksnp="%#x" % KSNP[ksnp]),
                         g["CAVE"])
        words = list(sw)
        prec_va = g["CAVE"] + 4 * len(sw)
        if prec:
            pw, _ = assemble(PREC_SRC.format(isenemy="%#x" % g["ISENEMY"], cwmt="%#x" % g["CWMT"]),
                             prec_va)
            words += pw
        if g["CAVE"] + 4 * len(words) > g["CAVE_END"]:
            raise ValueError("sight routines outgrow their cave")
        out += [(g["CAVE"] + 4 * i, w, st[g["CAVE"] + 4 * i],
                 "sightlines: routine" if i < len(sw) else "sightlines: sniper precision")
                for i, w in enumerate(words)]
        if kall != "1" or ksnp != "1":
            for va, stock, off in g["SITES"]:
                out.append((va, assemble("jal %#x" % g["CAVE"], va)[0][0], stock,
                            "sightlines: difficulty sight factor through the routine"))
                out.append((va + 4, assemble("addiu a0, v0, %#x" % off, va + 4)[0][0],
                            g["DELAY_STOCK"], "sightlines: a0 = &factor"))
        if prec:
            out.append((g["PREC_HOOK"], assemble("jal %#x" % prec_va, g["PREC_HOOK"])[0][0],
                        g["PREC_STOCK"], "sightlines: snipers skip the enemy miss"))
    if draw != "80":
        for va in g["DRAW"]:
            out.append((va, assemble("lui v0, %#x" % DRAW[draw], va)[0][0], DRAW_STOCK,
                        "sightlines: soldiers drawn to %s m" % draw))
    return out


def gr_edits(v: dict):
    return edits("gr", v.get("gr_enemy_sight_mult", "1"), v.get("gr_sniper_sight", "1"),
                 bool(v.get("gr_sniper_precision")), v.get("gr_soldier_draw", "80"))


def js_edits(v: dict):
    return edits("js", v.get("js_enemy_sight_mult", "1"), v.get("js_sniper_sight", "1"),
                 bool(v.get("js_sniper_precision")), v.get("js_soldier_draw", "80"))


def selftest(gr_elf: bytes, js_elf: bytes):
    """Every stock word against the executables, no address twice. [] = pass."""
    bad = []
    for game, st, elf, d in (("gr", GR_STOCK, gr_elf, 0x80), ("js", JS_STOCK, js_elf, 0x100)):
        for va, w in st.items():
            off = va - 0x100000 + d
            if int.from_bytes(elf[off:off + 4], "little") != w:
                bad.append("%s %08X" % (game, va))
        e = edits(game, "3", "4", True, "240")
        if len({va for va, *_ in e}) != len(e):
            bad.append("%s duplicate VA" % game)
        if any(va not in st for va, *_ in e):
            bad.append("%s VA without a stock word" % game)
    return bad

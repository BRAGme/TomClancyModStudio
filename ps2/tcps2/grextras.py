"""Rainbow Six 3 ideas carried over to Ghost Recon and Jungle Storm.

The Mod Studio's Rainbow Six 3 page grew a set of options for split-screen
parity and enemy behaviour. A survey of the Ghost Recon engine for the same
problems found five worth porting. Every stock word below was read off the
retail executables and every new word disassembled back; none has been
played.

Stance hides you in split screen
    AwarenessMgr::CheckLineOfSight (GR 0x003F4010, JS 0x003D3EF0) shrinks an
    enemy's sight to 3/4 when *player 1* crouches and 1/2 prone, and skips
    that entirely in split screen -- so in split screen crouching and going
    prone give no range bonus at all. The rewrite takes the stance of the
    soldier actually being looked at (the target argument, s3) and drops the
    split-screen test. In single player it also means an AI teammate's own
    stance counts when an enemy looks at him, rather than yours.

Enemies can run out of magazines
    SimHuman::ThisGuyShouldHaveInfiniteAmmo (GR 0x003DBE80) answers yes for
    every soldier in a script-controlled fireteam -- which CreatePlatoon
    sets for every team not named _Alpha, _Bravo or _Charlie, i.e. every
    enemy. One branch ignores that flag. Your own squad already spent
    magazines; this makes the enemy do the same.

Rain in split screen
    EffMgrPS2::SetWeather (GR 0x0045DF30, JS 0x004239E0) refuses to create
    rain in split screen, although the second slot, its cleanup and the
    per-viewport draw are all there -- snow already gets its second
    instance. SetWeather now calls a small routine for each slot (the second
    only in split screen). Ghost Recon also keeps the rain sound in split
    screen and gives each half the full 1,000 snowflakes instead of 500.

Enemies throw grenades more readily (Ghost Recon)
    SuppressBehavior::ShouldIFrag (0x001BD020) throws only when both rooms
    are outdoors, the target is 15-40 m away, and a 75% roll passes. This
    allows indoor throws, 10-60 m, every time the other checks pass --
    IsOkToFragHereNow still keeps grenades off nearby friendlies.

Enemies see at full strength on every difficulty
    IkeConstants writes per-difficulty sight factors for script-controlled
    lookers -- the enemy -- of 0.5 / 0.556 / 0.611 of the level's spotting
    distance. This sets all three to 1.0. The constructor runs once at
    boot; the two constant-pool words are read only by it.
"""

from __future__ import annotations

from .grasm import assemble

# ---------------------------------------------------------------------------
# word tables: (va, stock, new)
# ---------------------------------------------------------------------------

GR_STEALTH = (
    (0x003F45C0, 0x0C0D9B38, 0x8E790000),   # lw   t9, 0(s3)        target controller
    (0x003F45C4, 0x00000000, 0x8F39024C),   # lw   t9, 0x24c(t9)
    (0x003F45C8, 0x0C0DAF24, 0x0320F809),   # jalr t9               -> its human (+0x1b0)
    (0x003F45CC, 0x70408E28, 0x0260202D),   # move a0, s3
    (0x003F45D0, 0x8C590000, 0x10400003),   # beqz v0, +3
    (0x003F45D4, 0x70402628, 0x0040882D),   # move s1, v0
    (0x003F45D8, 0x8F3900EC, 0x2442FE50),   # addiu v0, v0, -0x1b0
    (0x003F45DC, 0x0320F809, 0x0040882D),   # move s1, v0           s1 = target soldier
    (0x003F45E0, 0x70002E28, 0x10000011),   # b    0x3f4628         past the split-screen test
    (0x003F45E4, 0x8E390000, 0x00000000),
)
JS_STEALTH = (
    (0x003D446C, 0x0C0529F8, 0x8E790000),
    (0x003D4470, 0x00000000, 0x8F390250),   # JS's vtable carries one extra slot
    (0x003D4474, 0x0C049620, 0x0320F809),
    (0x003D4478, 0x0040802D, 0x0260202D),
    (0x003D447C, 0x8C590000, 0x10400003),
    (0x003D4480, 0x0040202D, 0x0040802D),
    (0x003D4484, 0x8F3900EC, 0x2442FE50),
    (0x003D4488, 0x0320F809, 0x0040802D),
    (0x003D448C, 0x0000282D, 0x10000011),
    (0x003D4490, 0x8E190000, 0x00000000),
)

GR_ENEMY_AMMO = ((0x003DC074, 0x10400002, 0x10000002),)
JS_ENEMY_AMMO = ((0x003BB848, 0x10400002, 0x10000002),)

GR_GRENADES = (
    (0x001BD170, 0x3C024361, 0x3C0242C8),   # minimum 15 m -> 10 m (distance squared)
    (0x001BD1D4, 0x3C0244C8, 0x3C024561),   # maximum 40 m -> 60 m
    (0x001BD21C, 0x3C023F40, 0x3C023F80),   # 75% roll -> always
    (0x001BD120, 0x14400003, 0x10000003),   # thrower need not be outdoors
    (0x001BD150, 0x14400004, 0x10000004),   # target need not be outdoors
)

GR_SIGHT = (
    (0x005731E8, 0x3F0E38E4, 0x3F800000),   # Veteran 0.556 -> 1.0 (constant pool)
    (0x005731E0, 0x3F1C71C7, 0x3F800000),   # Elite   0.611 -> 1.0 (constant pool)
    (0x0015CB00, 0xADEE012C, 0xADED012C),   # Recruit: store t5 (1.0), not t6 (0.5)
)
JS_SIGHT = (
    (0x0057E7A8, 0x3F0E38E4, 0x3F800000),
    (0x0057E7A0, 0x3F1C71C7, 0x3F800000),
    (0x0012C96C, 0xAE0D0134, 0xAE0C0134),
)

# rain: a routine per game, and SetWeather's rain branch rewritten to call it
_RAIN_CAVE = """
    addiu sp, sp, -32
    sd    ra, 16(sp)
    sq    s0, 0(sp)
    move  s0, a0
    lw    v1, {slot}(s0)            ; already raining in this slot?
    bnez  v1, done
    nop
    jal   {new}
    li    a0, 0x40
    beqz  v0, st
    move  a0, v0
    jal   {ctor}                    ; RainEffectPS2::RainEffectPS2
    nop
st:
    sw    v0, {slot}(s0)
done:
    ld    ra, 16(sp)
    lq    s0, 0(sp)
    jr    ra
    addiu sp, sp, 32
"""
_RAIN_HOOK = """
    jal   {cave}                    ; slot 1
    move  a0, s0
    lui   at, {ghi}
    lw    v1, {glo}(at)
    lbu   v1, 0x2880(v1)            ; split screen?
    beqz  v1, {end}
    nop
    jal   {cave}                    ; slot 2, read by player 2's viewport
    addiu a0, s0, 4
    b     {end}
    nop
"""
GR_RAIN = dict(slot="0x62b4", new="0x102db0", ctor="0x4603c0", cave=0x004170C0,
               ghi="0x63", glo="0xb40", end="0x45e014", hook=0x0045DF54)
JS_RAIN = dict(slot="0x62ac", new="0x103470", ctor="0x425d30", cave=0x00199B84,
               ghi="0x68", glo="-0x30c0", end="0x423ac4", hook=0x00423A04)

GR_RAIN_EXTRA = (
    (0x0025AAB8, 0x10400002, 0x10000002),   # IkeSoundMgr::SetRain keeps its flag
    (0x0025AA48, 0x1440000A, 0x00000000),   # SetRainIntensity runs in split screen
    (0x004626E4, 0x240201F4, 0x00000000),   # 1,000 snowflakes per half, not 500
)

#: stock words the rain routine and hook overwrite
GR_RAIN_STOCK = {
    # sceFormat, unreferenced
    0x004170C0: 0x27BDFF30, 0x004170C4: 0xFFB00040, 0x004170C8: 0xFFB600A0,
    0x004170CC: 0x0080802D, 0x004170D0: 0xFFB20060, 0x004170D4: 0x00C0B02D,
    0x004170D8: 0xFFB10050, 0x004170DC: 0x00A0902D, 0x004170E0: 0xFFB700B0,
    0x004170E4: 0x00E0882D, 0x004170E8: 0xFFB30070, 0x004170EC: 0x2404000E,
    0x004170F0: 0xFFBF00C0, 0x004170F4: 0x3C17005F, 0x004170F8: 0xFFB50090,
    0x004170FC: 0x26F3E100, 0x00417100: 0x0C10563E, 0x00417104: 0xFFB40080,
    # SetWeather's rain branch
    0x0045DF54: 0x8E0362B4, 0x0045DF58: 0x1460002E, 0x0045DF5C: 0x3C010063,
    0x0045DF60: 0x8C230B40, 0x0045DF64: 0x90632880, 0x0045DF68: 0x1460002A,
    0x0045DF6C: 0x24040040, 0x0045DF70: 0x0C040B6C, 0x0045DF74: 0x00000000,
    0x0045DF78: 0x70402628, 0x0045DF7C: 0x10800004,
}
#: JS's routine lives in the grsquad lzo cave (its stock words are there)
JS_RAIN_HOOK_STOCK = {
    0x00423A04: 0x8E0362AC, 0x00423A08: 0x1460002E, 0x00423A0C: 0x3C010068,
    0x00423A10: 0x8C23CF40, 0x00423A14: 0x90632880, 0x00423A18: 0x1460002A,
    0x00423A1C: 0x24040040, 0x00423A20: 0x0C040D1C, 0x00423A24: 0x00000000,
    0x00423A28: 0x0040202D, 0x00423A2C: 0x10800004,
}


def _table(t):
    return {va: s for va, s, _n in t}


GR_STOCK = {}
for _t in (GR_STEALTH, GR_ENEMY_AMMO, GR_GRENADES, GR_SIGHT, GR_RAIN_EXTRA):
    GR_STOCK.update(_table(_t))
GR_STOCK.update(GR_RAIN_STOCK)
JS_STOCK = {}
for _t in (JS_STEALTH, JS_ENEMY_AMMO, JS_SIGHT):
    JS_STOCK.update(_table(_t))
JS_STOCK.update(JS_RAIN_HOOK_STOCK)


def _rain_words(g):
    cave = assemble(_RAIN_CAVE.format(**g), g["cave"])[0]
    hook = assemble(_RAIN_HOOK.format(**dict(g, cave="%#x" % g["cave"])), g["hook"])[0]
    return ([(g["cave"] + 4 * i, w) for i, w in enumerate(cave)],
            [(g["hook"] + 4 * i, w) for i, w in enumerate(hook)])


def gr_edits(v, prefix="gr_"):
    """(va, value, stock, note) for the Ghost Recon options chosen in `v`."""
    out = []

    def add(table, note):
        out.extend((va, n, s, note) for va, s, n in table)

    if v.get(prefix + "ss_stealth"):
        add(GR_STEALTH, "split screen: the target's own stance hides him")
    if v.get(prefix + "enemy_ammo"):
        add(GR_ENEMY_AMMO, "enemies spend magazines")
    if v.get(prefix + "enemy_grenades"):
        add(GR_GRENADES, "enemy grenades: indoors, 10-60 m, every time")
    if v.get(prefix + "enemy_sight_all"):
        add(GR_SIGHT, "enemy sight 1.0 on every difficulty")
    if v.get(prefix + "ss_rain"):
        cave, hook = _rain_words(GR_RAIN)
        out.extend((va, w, GR_RAIN_STOCK[va], "split-screen rain: routine") for va, w in cave)
        out.extend((va, w, GR_RAIN_STOCK[va], "split-screen rain: SetWeather") for va, w in hook)
        add(GR_RAIN_EXTRA, "split-screen rain: sound and snow")
    return out


def js_edits(v, js_squad_stock, prefix="js_"):
    """Jungle Storm; `js_squad_stock` is grsquad.JS_STOCK (the rain routine
    shares grsquad's lzo cave, after its bullet-hole routine)."""
    out = []

    def add(table, note):
        out.extend((va, n, s, note) for va, s, n in table)

    if v.get(prefix + "ss_stealth"):
        add(JS_STEALTH, "split screen: the target's own stance hides him")
    if v.get(prefix + "enemy_ammo"):
        add(JS_ENEMY_AMMO, "enemies spend magazines")
    if v.get(prefix + "enemy_sight_all"):
        add(JS_SIGHT, "enemy sight 1.0 on every difficulty")
    if v.get(prefix + "ss_rain"):
        cave, hook = _rain_words(JS_RAIN)
        out.extend((va, w, js_squad_stock[va], "split-screen rain: routine") for va, w in cave)
        out.extend((va, w, JS_RAIN_HOOK_STOCK[va], "split-screen rain: SetWeather") for va, w in hook)
    return out


def selftest(gr_elf=None, js_elf=None):
    import struct
    from . import grsquad
    fails = []
    for elf, stock, delta in ((gr_elf, GR_STOCK, 0x80), (js_elf, JS_STOCK, 0x100)):
        if elf is None:
            continue
        for va, want in stock.items():
            got = struct.unpack_from("<I", elf, va - 0x100000 + delta)[0]
            if got != want:
                fails.append("stock %08x: disc %08x, recorded %08x" % (va, got, want))
    # the JS rain routine must fit after grsquad's bullet-hole routine
    cave, _ = _rain_words(JS_RAIN)
    bh_end = grsquad.JS_BH_CAVE + 4 * len(assemble(grsquad.JS_BH_SRC, grsquad.JS_BH_CAVE)[0])
    if cave[0][0] < bh_end or cave[-1][0] + 4 > grsquad.JS_CAVE + grsquad.JS_CAVE_BYTES:
        fails.append("JS rain routine collides with grsquad's caves")
    gr_cave, _ = _rain_words(GR_RAIN)
    if any(va not in GR_RAIN_STOCK for va, _w in gr_cave):
        fails.append("GR rain routine outgrows its stock table")
    return fails

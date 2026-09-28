"""The "man down" music for any soldier of your squad: Jungle Storm (SLUS-20820).

When a soldier dies, Jungle Storm's death handler (the block at JS 0x003B5900)
asks IkeSimulationMgr for player 1's avatar (vtable +0x64 with 0) and, only if
the dead soldier is that avatar, plays one of the six death tracks at random
(death1-6.wav, table 0x0057A590, through the sound manager's PlayMusic,
vtable +0x20, 2 s fade). A teammate falling -- an AI Ghost, or player 2 in
split screen -- gets nothing. (Ghost Recon plays the same tracks from
SimHuman::ApplyDamage, behind SimHuman::IsAvatar, through
IkeSoundMgr::PlayAvatarDeathMusic, which waits for a track to finish.)

The call for the avatar (0x003B5914, ``jalr``) goes through a routine that
answers the dead soldier's own id when he belongs to your squad -- the
player's company and platoon, the globals at 0x0057A1C8 / 0x0057A1D0 that
the SELECT and quick-order code test (SimHuman +0x178 company, +0x444
platoon) -- so the comparison after it passes and the track plays; anyone
else is asked about as before. Enemies stay silent. Each death in the squad
starts a track, so deaths close together restart it.

Cave: the twin of sceDevConsGet (0x00176A40, 29 words), unreferenced in the
loaded image and both overlays and written by no other option. Not yet
played.
"""

from __future__ import annotations

from .grasm import assemble

CAVE, CAVE_END = 0x00176A40, 0x00176AB4
HOOK, HOOK_STOCK = 0x003B5914, 0x0320F809      # jalr t9 = IkeSimulationMgr vt+0x64 (a1 = 0 in the slot)
SQUAD_COMPANY, SQUAD_PLATOON = 0x0057A1C8, 0x0057A1D0

SRC = """
md_id:                              ; t9 = SimMgr vt+0x64, a0 = SimMgr, a1 = 0; s5 = the soldier who died
    lw    v0, 0x178(s5)             ; his company
    lui   at, %hi(SQUAD_COMPANY)
    lw    v1, %lo(SQUAD_COMPANY)(at)
    bne   v0, v1, md_ask
    lw    v0, 0x444(s5)             ; his platoon
    lui   at, %hi(SQUAD_PLATOON)
    lw    v1, %lo(SQUAD_PLATOON)(at)
    bne   v0, v1, md_ask
    nop
    jr    ra
    lw    v0, 0x128(s5)             ; one of your squad: his own id, so the track plays
md_ask:
    jr    t9                        ; anyone else: player 1's avatar, as before
    nop
"""

_CAVE_STOCK_HEX = (   # sceDevConsGet twin, 0x00176A40..0x00176AB4
    "27BDFFE0 FFB00000 FFBF0010 0080802D 8E050010 0C05DCFA 8E060014 0040302D"
    "8E050000 8E020010 24420001 0045182B 1460000B AE020010 8E040014 8E030004"
    "0083102B 14400004 24820001 AE030014 10000003 AE050010 AE000010 AE020014"
    "DFBF0010 00C0102D DFB00000 03E00008 27BD0020"
)


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


JS_STOCK = _stock_words(CAVE, _CAVE_STOCK_HEX)
JS_STOCK[HOOK] = HOOK_STOCK


def edits():
    """(va, value, stock, note)."""
    words, labels = assemble(SRC, CAVE, dict(SQUAD_COMPANY=SQUAD_COMPANY, SQUAD_PLATOON=SQUAD_PLATOON))
    if CAVE + 4 * len(words) > CAVE_END:
        raise ValueError("death-music routine outgrows its cave")
    out = [(CAVE + 4 * i, w, JS_STOCK[CAVE + 4 * i], "squad death music: routine") for i, w in enumerate(words)]
    out.append((HOOK, assemble("jal %#x" % labels["md_id"], HOOK)[0][0], HOOK_STOCK,
                "squad death music: a squad member's death answers as the avatar's"))
    return out


def js_edits(v: dict):
    return edits() if v.get("js_squad_death_music") else []


def selftest(gr_elf: bytes, js_elf: bytes):
    """Every stock word against the executable, no address twice. [] = pass."""
    bad = []
    for va, w in JS_STOCK.items():
        off = va - 0x100000 + 0x100
        if int.from_bytes(js_elf[off:off + 4], "little") != w:
            bad.append("js %08X" % va)
    e = edits()
    if len({va for va, *_ in e}) != len(e):
        bad.append("js duplicate VA")
    if any(va not in JS_STOCK for va, *_ in e):
        bad.append("js VA without a stock word")
    return bad

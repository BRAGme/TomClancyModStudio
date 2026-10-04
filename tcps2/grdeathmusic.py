"""The "man down" music for any soldier of your squad: Jungle Storm (SLUS-20820)
and Ghost Recon (SLUS-20613).

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

Ghost Recon (``gr_squad_death_music``)
--------------------------------------
Stock Ghost Recon has two death-music paths in SimHuman::ApplyDamage
(0x003D54D0), both on a killing hit:

* when the dead soldier is a player's (SimHuman::IsAvatar = control type
  +0x138 is 0, so either split-screen player):
  IkeSoundMgr::PlayAvatarDeathMusic (0x0025AC90) plays one of death1-6.wav --
  but only once until that track has ended (a latch, IkeSoundMgr +0x107,
  that UpdateActionMusic clears when no music stream is left);
* the block Jungle Storm keeps (0x003D5ED8..0x003D5F54): it asks
  IkeSimulationMgr::GetObserverID(0) (vtable +0x64) for the soldier player 1
  is watching and, only if that is the dead soldier, plays one of the same six
  tracks (kDeathSound, 0x00560FC0) through PlayMusic (vtable +0x20, 2 s fade).
  PlayMusic ignores a track that is already playing and fades out anything
  else first.

So player 1's death gets a track, player 2's gets one only when no avatar death
track is still playing, and an AI Ghost's death gets nothing.

Ghost Recon has no global for "the player's company and platoon" (Jungle
Storm's setter at 0x003BBFC0 is new; GR's SimHuman::InitializeFromMessage
reads the player flag and stores nothing), so the routine compares with the
local players' own soldiers instead. The call at 0x003D5EEC (``jalr``) goes
through it: for player 1 and then player 2 it asks
IkeSimulationMgr::GetObserver (0x0038FC00; the soldier that player watches,
0 when there is no player 2), and when the dead soldier has that soldier's
company (+0x178) and platoon (+0x444) it answers his own id, so the
comparison after it passes and the track plays. Anyone else is asked about as
before. Enemies, and friendly units outside your platoon, stay silent.

Split screen: there is one music stream for the console, so a squad member's
death plays to both players. "Your squad" is either player's platoon. The
split-screen roster puts 1P and 2P in one platoon (Alpha and Bravo), so in
practice that is one squad, with the AI fireteams and total-war copies in it.
A player's watched soldier is always in his own platoon: his own soldier, the
teammate he took over, or the platoon member grobserver shows him.

Cave: sceVu0ViewScreenMatrix (0x0042BB30, 65 words, 31 used). Nothing in the
loaded image (0x00100000-0x005DED00) jumps, branches, points or builds an
address into it or to the word before it. No word in the RAM of any of the
five GR savestates points or jumps there. Its RAM is byte-identical to the
ELF in all five, and no other option writes it.

Checked in the RAM interpreter on the five Ghost Recon savestates that hold
soldiers. ApplyDamage ran to the end with a killing hit on all 137 living
soldiers, stock and patched. Stock: the track played for player 1 only. With
the option: it played for the 5 players and their 24 squad members, and for
none of the 108 others (enemies and a friendly platoon). Split screen was emulated
by making a soldier player 2 (state manager +0x1FC/+0x204, control type 0),
in his own platoon and in a different one. Not yet played.
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


# ---------------------------------------------------------------------------
# Ghost Recon (SLUS-20613)
# ---------------------------------------------------------------------------

GR_CAVE, GR_CAVE_END = 0x0042BB30, 0x0042BC34   # sceVu0ViewScreenMatrix, 65 words, unreferenced
GR_HOOK, GR_HOOK_STOCK = 0x003D5EEC, 0x0320F809  # jalr t9 = IkeSimulationMgr::GetObserverID (a1 = 0 in the slot)
GR_GET_OBSERVER = 0x0038FC00    # IkeSimulationMgr::GetObserver(i): local player i's soldier, 0 if none

GR_SRC = """
md_gr:                              ; t9 = GetObserverID, a0 = SimMgr, a1 = 0; s5 = the soldier who died
    addiu sp, sp, -0x20
    sd    ra, 0x10(sp)
    sw    a0, 0x00(sp)              ; the simulation manager
    sw    t9, 0x04(sp)              ; GetObserverID
    sw    zero, 0x08(sp)            ; local player 0 (player 1), then 1 (player 2)
md_loop:
    lw    a0, 0x00(sp)
    jal   GET_OBSERVER              ; that player's soldier, 0 when there is no such player
    lw    a1, 0x08(sp)
    beqz  v0, md_next
    lw    v1, 0x178(s5)             ; his company
    lw    t0, 0x178(v0)
    bne   v1, t0, md_next
    lw    v1, 0x444(s5)             ; his platoon
    lw    t0, 0x444(v0)
    bne   v1, t0, md_next
    nop
    ld    ra, 0x10(sp)
    lw    v0, 0x128(s5)             ; one of that player's squad: his own id, so the track plays
    jr    ra
    addiu sp, sp, 0x20
md_next:
    lw    t0, 0x08(sp)
    addiu t0, t0, 1
    slti  t1, t0, 2
    bnez  t1, md_loop
    sw    t0, 0x08(sp)
    lw    a0, 0x00(sp)              ; anyone else: player 1's soldier, as before
    lw    t9, 0x04(sp)
    ld    ra, 0x10(sp)
    move  a1, zero
    jr    t9
    addiu sp, sp, 0x20
"""

_GR_CAVE_STOCK_HEX = (   # sceVu0ViewScreenMatrix, 0x0042BB30..0x0042BC34
    "27BDFF60 46008807 E7B40060 46009507 C7A100A0 E7B50068 46120000 46130D42"
    "FFB00040 4613A502 0080802D 46018C42 E7BA0090 46009CC7 E7B90088 4600AD42"
    "E7B80080 4611A500 E7B70078 46019CC0 E7B60070 46006586 46006E06 460075C6"
    "46007E86 00000000 00000000 4613AD43 00000000 00000000 4613A503 FFBF0050"
    "0C10AD92 46008646 3C013F80 44810000 03A0202D E6160014 E6160000 AE000028"
    "AE00003C E600002C 0C10AD92 E6000038 0200202D E7B80000 E7B70014 03A0282D"
    "E7B50028 0080302D E7BA0030 E7B90034 0C10ACD4 E7B40038 DFBF0050 DFB00040"
    "C7BA0090 C7B90088 C7B80080 C7B70078 C7B60070 C7B50068 C7B40060 03E00008"
    "27BD00A0"
)

GR_STOCK = _stock_words(GR_CAVE, _GR_CAVE_STOCK_HEX)
GR_STOCK[GR_HOOK] = GR_HOOK_STOCK


def gr_routine_edits():
    """(va, value, stock, note) for Ghost Recon."""
    words, labels = assemble(GR_SRC, GR_CAVE, dict(GET_OBSERVER=GR_GET_OBSERVER))
    if GR_CAVE + 4 * len(words) > GR_CAVE_END:
        raise ValueError("Ghost Recon death-music routine outgrows its cave")
    out = [(GR_CAVE + 4 * i, w, GR_STOCK[GR_CAVE + 4 * i], "squad death music: routine")
           for i, w in enumerate(words)]
    out.append((GR_HOOK, assemble("jal %#x" % labels["md_gr"], GR_HOOK)[0][0], GR_HOOK_STOCK,
                "squad death music: a squad member's death answers as player 1's soldier's"))
    return out


def gr_edits(v: dict):
    return gr_routine_edits() if v.get("gr_squad_death_music") else []


def selftest(gr_elf: bytes, js_elf: bytes):
    """Every stock word against the executables, no address twice. [] = pass."""
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
    for va, w in GR_STOCK.items():
        off = va - 0x100000 + 0x80
        if int.from_bytes(gr_elf[off:off + 4], "little") != w:
            bad.append("gr %08X" % va)
    e = gr_routine_edits()
    if len({va for va, *_ in e}) != len(e):
        bad.append("gr duplicate VA")
    if any(va not in GR_STOCK or GR_STOCK[va] != st for va, _w, st, _n in e):
        bad.append("gr VA without its stock word")
    return bad

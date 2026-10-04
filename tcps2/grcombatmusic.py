"""Combat music for fights at range: Jungle Storm (SLUS-20820) and Ghost Recon
(SLUS-20613, at the end).

How the stock game picks its music (the local player's soldier only)
---------------------------------------------------------------------
Every frame, SimHuman's sound update (JS 0x003BCC50; GR names it
SimHuman::UpdateNewSound) runs for the soldier the simulation manager calls
player 1 (vtable +0x64 with 0; on a joining console that is the joiner). It
reads what is playing now (0x003BDDC0: 1 action_1-4, 2 objective,
3 exploration "Exp", 4 "ExpV", 5 death) and:

* exploration (Exp) starts after 15 s without gunfire when nothing plays;
  it fades out (2 s) when a known enemy -- the closest one his fireteam knows
  about -- is within 30 m, or as soon as anyone fires;
* ExpV (tension) starts when a known enemy is within 30 m and no action,
  objective or ExpV track is playing;
* ACTION music (action_1-4.wav, 2 s fade in) starts when the flag at
  SimHuman +0x5F0 is set, unless an action, objective or death track is
  already playing. Tracks are not stopped by any of this: each plays to its
  end, and the next one can start only after that.

The flag is set by SimHuman::TriggleForActionMusic (JS 0x003BDB60), which
SimHuman::StartedShooting (0x003B61C0) runs on the first round of every
soldier's burst. Only a burst by the player himself can set it, and only when

  - 2 or more living enemies are within 50 m of him (0x003BD640 counts them;
    they need not know he is there), or the closest enemy his fireteam
    knows about is within 10 m, or he is zoomed in with a sniper rifle;
  - AND he sees at least one enemy right now (0x003BDA40, which ignores the
    distance it is passed: "any seen awareness").

Everyone else's burst only restarts the 15 s quiet timer (0x003BDDA0). So
opening up on enemies 60-150 m away -- where firefights start now that
enemies hear shots within 60 m and close in from 150 m -- never starts the
action music, and an AI teammate's or an enemy's burst never does.

What this changes
-----------------
Range (``js_combat_music_range``): the 50 m and 10 m above become 75/15,
100/20 or 150/30 m -- the literal in the counter (0x003BD750, used by nothing
else) and the one in the trigger (0x003BDCC8).

Squad engaged / under fire (``js_combat_music_engaged``): the trigger's last
call (0x003BDD70, the 15 s timer restart for the player) goes through a
routine first. When the burst is someone else's -- an AI Ghost, player 2,
the co-op partner, or an enemy -- and he is within the range above of the
player (50 m x the range multiplier) and the closest opponent his own
fireteam knows about is within that range of him too, it sets the action
flag. The music system then treats it as if the player had fired: nothing
restarts a track that is playing, and a fight far from the player (a
teammate 300 m away) stays quiet. The routine lives in the body of
0x003BDA40, rewritten to the same answer in 22 words: the values it worked
out and threw away (look direction, FOV, zoom, IFF range) were all plain
getters, and its only callers are the trigger's two calls.

Music is per console. In online co-op each disc decides for its own player,
so both discs need the option. In split screen there is one music stream
and it follows player 1: stock, player 2's shots never start action music;
with "engaged" they do when player 2 is within range of player 1.

Ghost Recon (``gr_combat_music_range``, ``gr_combat_music_engaged``)
--------------------------------------------------------------------
Ghost Recon's music code is the same design, with its own numbers.
SimHuman::UpdateNewSound (0x003DD520) runs every frame but acts only for the
soldier player 1 watches (IkeSimulationMgr::GetObserverID(0), vtable +0x64).
It reads what is playing (GetCurrentMusictype 0x003DE6C0: 1 action, 2
objective, 3 stealth, 4 recon, 5 death) and:

* stealth (stealth1-9.wav) starts after 30 s without gunfire when nothing
  plays (timer at SimHuman +0x5BC). It fades out (2 s) when the closest enemy
  his fireteam knows about is within 30 m, or as soon as anyone fires
  (SimHuman::SetStealthTime 0x003DE6A0 sets the timer to -2 s);
* recon (Recon_1-5) plays when he is zoomed in with a sniper rifle and sees an
  enemy;
* ACTION music (action_1-4, 2 s fade in) starts when SimHuman +0x5C0 is set,
  unless an action, objective or death track is already playing.

SimHuman::TriggleForActionMusic (0x003DE470), run by StartedShooting
(0x003D6650) on the first round of every soldier's burst, sets that flag only
for player 1's own burst, under Jungle Storm's rule. Two or more living
enemies must be within 50 m (GetCloseEnemyNumber 0x003DDF30), or the closest
enemy his fireteam knows about within 10 m, or he must be zoomed in with a
sniper rifle; AND IsEnemyInCamera (0x003DE350, "any seen awareness", distance
ignored) must hold. Everyone else's burst only restarts player 1's quiet timer
(SetStealthTime at 0x003DE674).

Range: the literals at 0x003DE054 (the counter's 50 m, read nowhere else)
and 0x003DE5C8 (the trigger's 10 m). Engaged: the call at 0x003DE674 goes
through a routine in a cave (lzo_adler32, 0x0042F088, 62 of 98 words; GR's
IsEnemyInCamera is left alone). It sets player 1's action flag for someone
else's burst under the Jungle Storm rule. The closest opponent his own
fireteam knows about must be within 50 m x the multiplier of him, and he must
be within that distance of player 1 OR of player 2. Player 2 is
IkeSimulationMgr::GetObserver(1), 0x0038FC00, absent outside split screen.

Split screen: one music stream, and only player 1's watched soldier runs the
music code. Stock, player 2's bursts never start the action music, and the
range setting changes only player 1's own test. With "engaged", any burst
within range of either player counts (player 2's own included, when his
closest known opponent is within range). That covers a fight around player 2
far from player 1, and the music both players hear starts. A track that is
playing is still never restarted.

Checked in the RAM interpreter on the five GR savestates that hold soldiers,
1,096 runs: TriggleForActionMusic ran for every living soldier as the shooter,
in all 8 variants. In the 2026-09-29 firefight (3D55F8ED), player 1's burst
started nothing in stock. One enemy was within 50 m, the closest known one at
49.8 m, with an enemy in view. At x1.5 it starts the music (6 enemies within
75 m). With "engaged", nearby AI Ghosts' and enemies' bursts set the flag
exactly when the rule above says, and nobody else's did. Split screen was
emulated with a player 2 (state manager +0x1FC/+0x204): another 680 runs per
choice of player 2. Bursts 127 m from player 1 but beside player 2 started
the music. Not yet played.
"""

from __future__ import annotations

import struct

from .grasm import assemble

COUNT_LUI = 0x003BD750      # lui v0, 0x4248 (50.0 m): enemies counted around the player
CLOSE_LUI = 0x003BDCC8      # lui v0, 0x4120 (10.0 m): the closest known enemy
IEC, IEC_END = 0x003BDA40, 0x003BDB60   # "is an enemy in camera": 72 words
HOOK, HOOK_STOCK = 0x003BDD70, 0x0C0EF768   # jal 0x003BDDA0 (the player's 15 s quiet timer restart)
RESTART_QUIET = 0x003BDDA0
ACTION_FLAG = 0x5F0         # SimHuman +0x5F0: start an action track on the next sound update

#: multiplier on the stock 50 m / 10 m, by setting value
SCALE = {"stock": 1.0, "1.5": 1.5, "2": 2.0, "3": 3.0}


def _f32(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


IEC_SRC = """
iec:                                ; is an enemy in camera (this): any seen awareness, as before
    addiu sp, sp, -0x20
    sd    ra, 0x10(sp)
    sq    s0, 0x00(sp)
    jal   AIMGR_GET
    move  s0, a0
    move  a0, v0
    jal   GET_HUMAN_AI
    move  a1, s0
    beqz  v0, iec_out               ; no AI: no, as before
    move  v0, zero
    jal   SIMMGR_GET
    nop
    jal   GET_AWARENESS_MGR
    move  a0, v0
    move  a0, v0
    jal   GET_SEEN
    move  a1, s0
    sltu  v0, zero, v0              ; the list has a first entry
iec_out:
    ld    ra, 0x10(sp)
    lq    s0, 0x00(sp)
    jr    ra
    addiu sp, sp, 0x20

cm_engaged:                         ; in place of the quiet-timer restart; a0 = s0 = the player (or 0)
    addiu sp, sp, -0x20             ; the trigger's s1 = player's id, s2 = who fired; its frame (sp+0x20):
    sd    ra, 0x10(sp)              ;   +0x70 his position, +0x80 him -> closest opponent he knows (z 1000 if none)
    beqz  a0, cm_done
    sw    a0, 0x00(sp)
    lw    v0, 0x128(s2)
    beq   v0, s1, cm_done           ; the player's own burst: the stock test has run
    lui   v1, R2_HI
    ori   v1, v1, R2_LO
    mtc1  v1, f3                    ; range squared
    lwc1  f0, 0xA0(sp)
    lwc1  f1, 0xA4(sp)
    lwc1  f2, 0xA8(sp)
    swc1  f3, 0x04(sp)
    mul.s f0, f0, f0
    mul.s f1, f1, f1
    mul.s f2, f2, f2
    add.s f0, f0, f1
    add.s f0, f0, f2
    c.lt.s f0, f3
    bc1f  cm_done                   ; nobody for him to fight within range
    lw    t9, 0x00(a0)
    lw    t9, 0x238(t9)
    jalr  t9                        ; the player's position
    nop
    lwc1  f0, 0x00(v0)
    lwc1  f4, 0x90(sp)
    sub.s f0, f0, f4
    lwc1  f1, 0x04(v0)
    lwc1  f4, 0x94(sp)
    sub.s f1, f1, f4
    lwc1  f2, 0x08(v0)
    lwc1  f4, 0x98(sp)
    sub.s f2, f2, f4
    mul.s f0, f0, f0
    mul.s f1, f1, f1
    mul.s f2, f2, f2
    add.s f0, f0, f1
    add.s f0, f0, f2
    lwc1  f3, 0x04(sp)
    c.lt.s f0, f3
    bc1f  cm_done                   ; he is farther than that from the player
    lw    a0, 0x00(sp)
    li    v1, 1
    sw    v1, ACTION_FLAG(a0)       ; action music on the player's next sound update
cm_done:
    lw    a0, 0x00(sp)
    ld    ra, 0x10(sp)
    j     RESTART_QUIET             ; the quiet-timer restart, as before
    addiu sp, sp, 0x20
"""

SYMS = dict(AIMGR_GET=0x001225D0, GET_HUMAN_AI=0x003F17D0, SIMMGR_GET=0x00122730,
            GET_AWARENESS_MGR=0x003429F0, GET_SEEN=0x00342900,
            RESTART_QUIET=RESTART_QUIET, ACTION_FLAG=ACTION_FLAG)

# Fixed 8-digit words (adjacent literals join with no separator).
_IEC_STOCK_HEX = (
    "27BDFF80 FFBF0030 7FB10020 7FB00010 E7B40000 8C990000 8F390330 0320F809"
    "0080882D 0040282D 0C042984 27A40070 0C042994 27A40060 0C042994 27A40050"
    "0C048974 00000000 0040202D 0C0FC5F4 0220282D 14400003 27A40040 1000002A"
    "0000102D 0C042984 2625049C 0C049174 00000000 8C590000 8F390048 0320F809"
    "0040202D 8C590000 8F390078 0320F809 0040202D 0C0490A0 00000000 0C0DECD4"
    "0040202D 0C08E85C 0220202D 0C0490A0 46000506 0C08DE9C 0040202D 4600A306"
    "0C08DE84 46000346 0C0489CC 0000802D 0C0D0A7C 0040202D 0220282D 0C0D0A40"
    "0040202D 10000005 00000000 0040202D 24050001 0C0D0A38 26100001 1440FFFB"
    "00000000 0010102A DFBF0030 C7B40000 7BB10020 7BB00010 03E00008 27BD0080"
)


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


JS_STOCK = _stock_words(IEC, _IEC_STOCK_HEX)
JS_STOCK[COUNT_LUI] = 0x3C024248
JS_STOCK[CLOSE_LUI] = 0x3C024120
JS_STOCK[HOOK] = HOOK_STOCK


def _scale(v):
    return SCALE.get(str(v.get("js_combat_music_range", "stock")), 1.0)


def edits(scale=1.0, engaged=False):
    """(va, value, stock, note)."""
    out = []
    if scale != 1.0:
        out.append((COUNT_LUI, 0x3C020000 | (_f32(50.0 * scale) >> 16), JS_STOCK[COUNT_LUI],
                    "combat music: enemies counted within %g m (2 needed)" % (50 * scale)))
        out.append((CLOSE_LUI, 0x3C020000 | (_f32(10.0 * scale) >> 16), JS_STOCK[CLOSE_LUI],
                    "combat music: or one known enemy within %g m" % (10 * scale)))
    if engaged:
        r2 = _f32((50.0 * scale) ** 2)
        words, labels = assemble(IEC_SRC, IEC, dict(SYMS, R2_HI=r2 >> 16, R2_LO=r2 & 0xFFFF))
        if IEC + 4 * len(words) > IEC_END:
            raise ValueError("combat-music routine outgrows 0x%08X" % IEC_END)
        out += [(IEC + 4 * i, w, JS_STOCK[IEC + 4 * i],
                 "combat music: enemy-in-view test, compact" if IEC + 4 * i < labels["cm_engaged"]
                 else "combat music: someone else's burst within %g m" % (50 * scale))
                for i, w in enumerate(words)]
        out.append((HOOK, assemble("jal %#x" % labels["cm_engaged"], HOOK)[0][0], HOOK_STOCK,
                    "combat music: other soldiers' bursts go through the range test"))
    return out


def js_edits(v: dict):
    return edits(_scale(v), bool(v.get("js_combat_music_engaged")))


# ---------------------------------------------------------------------------
# Ghost Recon (SLUS-20613)
# ---------------------------------------------------------------------------

GR_COUNT_LUI = 0x003DE054   # lui v0, 0x4248 (50.0 m) in SimHuman::GetCloseEnemyNumber
GR_CLOSE_LUI = 0x003DE5C8   # lui v0, 0x4120 (10.0 m) in SimHuman::TriggleForActionMusic
GR_HOOK, GR_HOOK_STOCK = 0x003DE674, 0x0C0F79A8   # jal SimHuman::SetStealthTime (player 1's quiet timer)
GR_CAVE, GR_CAVE_END = 0x0042F088, 0x0042F210     # lzo_adler32, 98 words, unreferenced
GR_SET_STEALTH = 0x003DE6A0
GR_ACTION_FLAG = 0x5C0      # SimHuman +0x5C0: start an action track on the next sound update

GR_SRC = """
cm_gr:                              ; in place of SetStealthTime(player 1); a0 = s1 = player 1's soldier (or 0)
    addiu sp, sp, -0x30             ; the trigger's s0 = player 1's id, s2 = who fired; its frame (sp+0x30):
    sd    ra, 0x20(sp)              ;   +0x60 him -> closest opponent he knows (z 1000 if none), +0x70 his position
    beqz  a0, cm_done
    sw    a0, 0x00(sp)
    lw    v0, 0x128(s2)
    beq   v0, s0, cm_done           ; player 1's own burst: the stock test has run
    lui   v1, R2_HI
    ori   v1, v1, R2_LO
    mtc1  v1, f3                    ; range squared
    lwc1  f0, 0x90(sp)
    lwc1  f1, 0x94(sp)
    lwc1  f2, 0x98(sp)
    swc1  f3, 0x04(sp)
    mul.s f0, f0, f0
    mul.s f1, f1, f1
    mul.s f2, f2, f2
    add.s f0, f0, f1
    add.s f0, f0, f2
    c.lt.s f0, f3
    bc1f  cm_done                   ; nobody for him to fight within range
    sw    zero, 0x08(sp)            ; player 1 first
cm_near:                            ; a0 = a local player's soldier
    lw    t9, 0x00(a0)
    lw    t9, 0x234(t9)
    jalr  t9                        ; his position (GetWorldPosition)
    nop
    lwc1  f0, 0x00(v0)
    lwc1  f4, 0xA0(sp)
    sub.s f0, f0, f4
    lwc1  f1, 0x04(v0)
    lwc1  f4, 0xA4(sp)
    sub.s f1, f1, f4
    lwc1  f2, 0x08(v0)
    lwc1  f4, 0xA8(sp)
    sub.s f2, f2, f4
    mul.s f0, f0, f0
    mul.s f1, f1, f1
    mul.s f2, f2, f2
    add.s f0, f0, f1
    add.s f0, f0, f2
    lwc1  f3, 0x04(sp)
    c.lt.s f0, f3
    bc1t  cm_set                    ; the shooter is within range of this player
    lw    v0, 0x08(sp)
    bnez  v0, cm_done               ; player 2 tried too
    li    v0, 1
    sw    v0, 0x08(sp)
    jal   SIMMGR_GET
    nop
    move  a0, v0
    jal   GET_OBSERVER              ; player 2's soldier in split screen, 0 otherwise
    li    a1, 1
    bnez  v0, cm_near
    move  a0, v0
    b     cm_done
    nop
cm_set:
    lw    a0, 0x00(sp)
    li    v1, 1
    sw    v1, ACTION_FLAG(a0)       ; action music on player 1's next sound update
cm_done:
    lw    a0, 0x00(sp)
    ld    ra, 0x20(sp)
    j     SET_STEALTH               ; the quiet-timer restart, as before
    addiu sp, sp, 0x30
"""

GR_SYMS = dict(SIMMGR_GET=0x0037A0A0, GET_OBSERVER=0x0038FC00,
               SET_STEALTH=GR_SET_STEALTH, ACTION_FLAG=GR_ACTION_FLAG)

_GR_CAVE_STOCK_HEX = (   # lzo_adler32, 0x0042F088..0x0042F210
    "27BDFFE0 00A0702D FFB10010 00C0C02D FFB00000 00046C02 15C00003 308CFFFF"
    "10000055 24020001 13000051 241115AF 3419FFF1 0000802D 0238102B 240F15B0"
    "0302780A 29E20010 14400035 030FC023 91C20000 25EFFFF0 91C30001 29EB0010"
    "01826021 91C40002 01AC6821 91C20003 01836021 91C50004 01AC6821 91C30005"
    "01846021 91C60006 01AC6821 91C40007 01826021 91C70008 01AC6821 91C20009"
    "01856021 91C8000A 01AC6821 91C5000B 01836021 91C9000C 01AC6821 91C3000D"
    "01866021 91CA000E 01AC6821 91C6000F 01846021 25CE0010 01AC6821 01876021"
    "01AC6821 01826021 01AC6821 01886021 01AC6821 01856021 01AC6821 01896021"
    "01AC6821 01836021 01AC6821 018A6021 01AC6821 01866021 1160FFCD 01AC6821"
    "51E00009 0199001B 91C20000 25EFFFFF 25CE0001 01826021 00000000 1DE0FFFA"
    "01AC6821 0199001B 71B9001B 53300001 000001CD 53300001 000001CD 00001010"
    "70001810 0040602D 1700FFB3 0060682D 000D1400 004C1025 DFB10010 DFB00000"
    "03E00008 27BD0020"
)

GR_STOCK = _stock_words(GR_CAVE, _GR_CAVE_STOCK_HEX)
GR_STOCK[GR_COUNT_LUI] = 0x3C024248
GR_STOCK[GR_CLOSE_LUI] = 0x3C024120
GR_STOCK[GR_HOOK] = GR_HOOK_STOCK


def _gr_scale(v):
    return SCALE.get(str(v.get("gr_combat_music_range", "stock")), 1.0)


def gr_routine_edits(scale=1.0, engaged=False):
    """(va, value, stock, note) for Ghost Recon."""
    out = []
    if scale != 1.0:
        out.append((GR_COUNT_LUI, 0x3C020000 | (_f32(50.0 * scale) >> 16), GR_STOCK[GR_COUNT_LUI],
                    "combat music: enemies counted within %g m (2 needed)" % (50 * scale)))
        out.append((GR_CLOSE_LUI, 0x3C020000 | (_f32(10.0 * scale) >> 16), GR_STOCK[GR_CLOSE_LUI],
                    "combat music: or one known enemy within %g m" % (10 * scale)))
    if engaged:
        r2 = _f32((50.0 * scale) ** 2)
        words, labels = assemble(GR_SRC, GR_CAVE, dict(GR_SYMS, R2_HI=r2 >> 16, R2_LO=r2 & 0xFFFF))
        if GR_CAVE + 4 * len(words) > GR_CAVE_END:
            raise ValueError("Ghost Recon combat-music routine outgrows 0x%08X" % GR_CAVE_END)
        out += [(GR_CAVE + 4 * i, w, GR_STOCK[GR_CAVE + 4 * i],
                 "combat music: someone else's burst within %g m of a player" % (50 * scale))
                for i, w in enumerate(words)]
        out.append((GR_HOOK, assemble("jal %#x" % labels["cm_gr"], GR_HOOK)[0][0], GR_HOOK_STOCK,
                    "combat music: other soldiers' bursts go through the range test"))
    return out


def gr_edits(v: dict):
    return gr_routine_edits(_gr_scale(v), bool(v.get("gr_combat_music_engaged")))


def selftest(gr_elf: bytes, js_elf: bytes):
    """Every stock word against the executables, no address twice, every variant. [] = pass."""
    bad = []
    for va, w in JS_STOCK.items():
        off = va - 0x100000 + 0x100
        if int.from_bytes(js_elf[off:off + 4], "little") != w:
            bad.append("js %08X" % va)
    for s in SCALE.values():
        for eng in (False, True):
            e = edits(s, eng)
            if len({va for va, *_ in e}) != len(e):
                bad.append("js duplicate VA (x%g, engaged %s)" % (s, eng))
            if any(va not in JS_STOCK or JS_STOCK[va] != st for va, _w, st, _n in e):
                bad.append("js VA without its stock word (x%g, engaged %s)" % (s, eng))
    for va, w in GR_STOCK.items():
        off = va - 0x100000 + 0x80
        if int.from_bytes(gr_elf[off:off + 4], "little") != w:
            bad.append("gr %08X" % va)
    for s in SCALE.values():
        for eng in (False, True):
            e = gr_routine_edits(s, eng)
            if len({va for va, *_ in e}) != len(e):
                bad.append("gr duplicate VA (x%g, engaged %s)" % (s, eng))
            if any(va not in GR_STOCK or GR_STOCK[va] != st for va, _w, st, _n in e):
                bad.append("gr VA without its stock word (x%g, engaged %s)" % (s, eng))
    return bad

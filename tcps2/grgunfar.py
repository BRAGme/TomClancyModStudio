"""Distant gunfire, and gunfire through walls: Jungle Storm (SLUS-20820).

Two separate things decide whether another soldier's gunshot reaches your ears,
and each is an option here.

**How far a shot carries (data: EFFECTS.XBS).** Every sound has a record in
EFFECTS.XBS -- intensity, volume, length, min, max, rolloff -- and the game
copies it verbatim into its sound table (all 777 records sit in RAM unchanged).
A soldier's gun emitter (SimHuman +0x5BC) takes min / max / rolloff from the
first gun sound it loads (Emitter params init 0x00235940), and the voice's
update (RSSoundEffectPS2 vt+0x24, 0x004F2F00) plays it at full volume inside
`min`, then falls off in a straight line to `max` (0 for every gun) at
`rolloff`. Jungle Storm replaced Ghost Recon's halve-per-doubling curve with
this line. On top of it the propagation pass (below) drops any sound whose
listener is `rolloff` or more away. Stock rifles are min 5 m, rolloff 105-110 m:
57 % volume at 50 m, 10 % at 100 m, nothing past 110 m. Machine guns, snipers
and launchers are 200 m.

The option multiplies `rolloff` -- and only that -- for every firing sound:
every `w_*.wav` record with a rolloff of 100 m or more that is not an ambient
effect. `min` stays, so a shot within 5 m is untouched and anything near is
within a fraction of a decibel of stock; the far tail stretches. Suppressed
weapons keep their stock records: the SOCOM M4 (w_m4soccum_*, 30 m), the
silenced M9 and MP5SD (w_sm9_ss, w_smp5_*, 15 m), and the SR-25 SD
(w_sr25s_*, which ships at 200 m). Reloads (15 m), shell casings (10 m),
grenade bounces, whizzes and bullet impacts are other records and do not move.

**Through walls (code: SoundPropagationManager::PropagateForAudio,
0x003D2470).** Ghost Recon's version is an empty stub; Jungle Storm's runs for
every propagated emitter (guns, footsteps, impacts) each time it plays, outside
split screen. With the listener's room (player 1's soldier, SimHuman +0x154)
and the emitter's room (FindRoom 0x004EB880) it asks 0x003D23E0: same room, or
both rooms of the outdoor kind (room +0xA8, vt+0x48, answers 1) ->
open; anything else -> it writes a muffled 0.2 direct + 0.2 indirect into the
emitter and answers "blocked", and the caller then CULLS the sound (Emitter
+0xA3) -- the muffle is never heard. So a man firing inside a hut is silent to
you 3 m outside it: in the host savestate after that fight, the two enemies
about 2 m from the host stand in a room of type 0 while the host is in the
outdoor room, and the stock pass culls both of their guns.

The open path has a second fault: it leaves the direct/indirect levels as they
were. An emitter that was once blocked keeps 0.2 + 0.2 and plays every later
shot at 40 % volume even in the open -- in the same savestate the guns of two
enemies 43 m and 83 m away in the host's own outdoor room sit at 0.2 + 0.2.

With the option on, nothing is culled for a wall any more, and a sound that
crosses one is judged by the line and the distance instead:

  * a gunshot or blast (rolloff 100 m or more) within 50 m whose gun stands in a
    known room gets the game's own sight trace -- RSSimRoom::FindLineCollision
    (0x004C40E0) with the flags AwarenessMgr::CheckLineOfSight uses, from the gun
    toward the listener's eye through the room portals. A clear line (an open
    doorway, a window the AI can see through) counts as the same room: full level.
  * otherwise the muffle fades in with distance: full level within 3 m, down to
    the engine's own 0.2 + 0.2 (40 %, -8 dB) by 10 m and beyond, so a man firing
    next to you round a door jamb still sounds close. Footsteps, reloads and
    impacts take the same fade without a trace.
  * the normal distance fall-off and the "rolloff or more" cut apply as before.

The open path now writes the full levels (0.6 + 0.4, the pair the engine uses for
your own gun), which also clears a stale muffle. A trace costs about 20-35 k EE
instructions (measured in the interpreter) and runs only when a shot starts or
the gun moves 0.5 m (PlayEx / SetPosition re-propagate; nothing per frame).
All in place, no cave: the two room-test calls, the cull and the play are
rewritten (43 words), the trace sits over the old room test they alone called
(0x003D23E0), the fade in the own-gun block (whose three calls became a branch
to the common "full level" path), and d is kept in a spare stack slot.

Both options are local: every console plays sounds itself, and remote players'
guns, AI guns and your own go through the same SimHuman gun emitter, so in
online co-op each disc needs them. Split screen skips propagation entirely, so
the wall option does nothing there.

**Ghost Recon (gr_room_sound).** Ghost Recon never muffles a sound for a wall: its
SoundPropagationManager::PropagateForAudio (0x003F2970) is an empty stub, so every 3D
sound plays at its distance level wherever it is. Its sound code does honour an
emitter's levels: Emitter::CalculateEffectiveVolume (0x00234640) multiplies the
emitter's volume by direct + indirect (+0x20 + +0x24, clamped to 0..1) for every
emitter that propagates (+0xA2), and hands the product to each voice
(RSSoundEffectPS2::SetVolume, voice +0x28), which RSSoundEffectPS2::Update multiplies
into the SPU level beside the distance fall-off (0x0050B084). Stock emitters keep the
constructor's 1.0 + 1.0. The stub is reached from Emitter::Propagate through
IkeSimulationMgr::PropagateForAudio when a sound starts (PlayEx), when an emitter moves
0.5 m (SetPosition / UpdatePosition) and, for playing sounds, when the camera moves
0.5 m -- and nothing on that path tests for split screen.

With the option the stub jumps to a routine that makes Jungle Storm's judgement, with
these differences:

  * the listener is the soldier each view follows (IkeSimulationMgr::GetObserver): his
    eye (+0x518, GetAwarenessLocation) and the room he sees from (+0x154). In split
    screen both players' soldiers are judged and the sound plays at the level of the
    one who hears it best: Ghost Recon gives a split-screen emitter one voice per view
    (+8 and +0xC, each attenuated from its own camera) but one shared volume, so a shot
    is muffled only when it is behind a wall for both players.
  * the sound's room is the room its soldier or vehicle is in (+0x50, then +0x154), and
    RSSimScene::FindRoom on its position only for emitters with neither. Ghost Recon puts
    a gun emitter at the muzzle, which can poke through a wall: in the 3E571E95.01
    savestate a teammate stands in the player's room 28 with his muzzle in room 25.
  * the trace starts in the indoor room -- from the listener's eye in his room when he
    is indoors, else from the sound in its room. A trace that starts in the outdoor room
    took 40-180 k EE instructions in the interpreter, one that starts indoors 4-30 k
    (78 k when a clear line runs on into the open).
  * nothing is ever culled (the voice update already silences a sound past its rolloff);
    a sound past its rolloff for that soldier only gets the distance muffle; a view with
    no soldier, or a soldier in no room, hears it at full level (as stock).
  * full is 0.5 + 0.5 (the stock 1.0 + 1.0 after the clamp), the muffle floor 0.2 + 0.2.

The routine takes 125 words in six stretches nothing references (four unused functions,
alignment padding and an unused two-word tail call): 0x00480480, 0x005485D0, 0x0054FC28,
0x00542F60, 0x0054FAC8 and 0x0054FFF4, plus the stub's first word. One propagation (a
burst starting, the gun moving, the camera moving 0.5 m while it plays) costs 0.5-0.8 k EE
instructions in all when the sound shares the listener's room or is out of his range, about
3 k when it needs FindRoom, 5-32 k with a trace, and up to 78 k when a clear line runs from
a room out into the open (interpreter counts for the whole Emitter::Propagate call).

Channels: the EE hands out the 48 SPU channels first-free (0x00492EC0), with
no stealing; a one-shot sound that finds none is dropped. Channels 0-3 are busy
in every savestate (the stream voices, by inference), and a speech emitter's
voice is a stream (+0x6C), so radio call-outs do not compete. A firing soldier
holds one channel while his sound plays, so more audible distant guns mean more
channels in a large fight: 5-13 of 48 are busy in the online and single-player
savestates, 26-35 in split-screen firefights, where nothing is culled by room.
"""

from __future__ import annotations

import struct

from .grasm import assemble

# --------------------------------------------------------------------------------------------
# 1. How far a shot carries: EFFECTS.XBS
# --------------------------------------------------------------------------------------------

FACTORS = {"stock": None, "1.5": 1.5, "2": 2.0, "3": 3.0}
#: firing sounds shorter-ranged than this (reloads, casings, silenced guns) are left alone
MIN_ROLLOFF = 100.0
#: suppressed weapons keep their stock range whatever it is (w_sr25s ships at 200 m)
SUPPRESSED = ("w_m4soccum_", "w_sm9_", "w_smp5_", "w_sr25s_")
ROLLOFF_AT = 20        # byte offset of rolloff in a record's six floats


class GunFarError(Exception):
    pass


def xbs_records(plain: bytes) -> list:
    """[(name, params offset, min, rolloff, ambient)] for every record of a .XBS.

    Layout: u32 count, then per record u32 nameLen, the name, six f32 (intensity,
    volume, length, min, max, rolloff), u8 ambient, 3 pad bytes, two u32 zero.
    """
    if len(plain) < 4:
        raise GunFarError("not a sound-volume table")
    count = struct.unpack_from("<I", plain, 0)[0]
    o, out = 4, []
    for _ in range(count):
        if o + 4 > len(plain):
            raise GunFarError("sound-volume table ends inside a record")
        n = struct.unpack_from("<I", plain, o)[0]
        p = o + 4 + n
        if n == 0 or n > 64 or p + 36 > len(plain):
            raise GunFarError("bad record at 0x%x" % o)
        name = plain[o + 4:p].decode("latin1")
        _i, _v, _l, mn, _mx, ro = struct.unpack_from("<6f", plain, p)
        out.append((name, p, mn, ro, plain[p + 24]))
        o = p + 36
    if o != len(plain):
        raise GunFarError("sound-volume table has %d bytes past its last record" % (len(plain) - o))
    return out


def carries(name: str, rolloff: float, ambient: int) -> bool:
    """Whether a record is a gunshot the option stretches."""
    low = name.lower()
    return (low.startswith("w_") and not ambient and rolloff >= MIN_ROLLOFF
            and not low.startswith(SUPPRESSED))


def scale_xbs(plain: bytes, factor: float):
    """(new bytes, records changed): every gunshot's rolloff times `factor`, nothing else."""
    if not 1.0 < factor <= 4.0:
        raise GunFarError("factor %r out of range" % factor)
    out = bytearray(plain)
    n = 0
    for name, p, _mn, ro, amb in xbs_records(plain):
        if carries(name, ro, amb):
            struct.pack_into("<f", out, p + ROLLOFF_AT, ro * factor)
            n += 1
    if not n:
        raise GunFarError("no gunshot records found: is this EFFECTS.XBS?")
    return bytes(out), n


def _op_gun_far(plain, params):
    return scale_xbs(plain, float(params["factor"]))


def _register():
    from . import dataedit
    dataedit.OPS.setdefault("gun_far_xbs", _op_gun_far)


_register()


# ---- Ghost Recon: the same records, as XML (EFFECTS.XML) ---------------------------------------
# Ghost Recon reads its sound table from EFFECTS.XML -- one line per sound, `Min`, `Max`, `Rolloff` --
# shipped in both GR.IMG and MENU.IMG (identical; both are edited, as for every GR table a mission may
# take from MENU.IMG). Its fall-off is not Jungle Storm's line: RSSoundEffectPS2::Update (GR 0x0050A7F0,
# at 0x0050AAD4) plays a sound at full level inside `Min` (+0x10), halves it at every doubling of the
# distance after that, and fades the last stretch to nothing at `Rolloff` (+0x18; RSEffectParams +0x0C,
# copied in by SetPlayParams 0x0050A6D0). The 96 gun voices in the 3D55F8ED firefight savestate hold
# min 5 / max 2000 / rolloff 110 there. Stretching only `Rolloff` would add a faint tail and leave a shot
# at 50 m exactly as quiet (5 -> 10 -> 20 -> 40: an eighth), so Ghost Recon's option scales `Min` and
# `Rolloff` together: the whole curve is stretched, every shot sounds as loud as a shot from 1/factor the
# distance did, and it goes silent factor times as far. Same records as JS (`carries`). The XML lives in
# an LZO container whose plain length must not change, so each number is rewritten at its own width
# ("5.000" -> "10.00", "110" -> "220"; ".5" values round to the nearest metre where no digit is free).
import re as _re

_XML_ENTRY = _re.compile(rb"<Entry\s[^>]*?/>")
_XML_ATTR = _re.compile(rb'(\w+)\s*=\s*"([^"]*)"')


def _same_width(x: float, width: int) -> bytes:
    """`x` written in exactly `width` characters, as many decimals as fit."""
    for decimals in range(6, -1, -1):
        s = "%.*f" % (decimals, x)
        if len(s) == width:
            return s.encode()
    raise GunFarError("%g does not fit in %d characters" % (x, width))


def scale_xml(plain: bytes, factor: float):
    """(new bytes, records changed): every gunshot's Min and Rolloff times `factor`, same length."""
    if not 1.0 < factor <= 4.0:
        raise GunFarError("factor %r out of range" % factor)
    out = bytearray(plain)
    n = 0
    for m in _XML_ENTRY.finditer(plain):
        attrs = {}
        for a in _XML_ATTR.finditer(m.group(0)):
            attrs[a.group(1).decode().lower()] = (a.group(2), m.start() + a.start(2), m.start() + a.end(2))
        if not {"filename", "min", "rolloff"} <= set(attrs):
            continue
        name = attrs["filename"][0].decode("latin1")
        try:
            ro = float(attrs["rolloff"][0])
            mn = float(attrs["min"][0])
        except ValueError:
            continue
        amb = attrs.get("ambient", (b"0",))[0]
        if not carries(name, ro, int(float(amb or b"0"))):
            continue
        for key, val in (("min", mn), ("rolloff", ro)):
            _text, a, b = attrs[key]
            new = _same_width(val * factor, b - a)
            if abs(float(new) - val * factor) > 0.01 * val * factor + 0.5:
                raise GunFarError("%s %s: %s is too far from %g" % (name, key, new.decode(), val * factor))
            out[a:b] = new
        n += 1
    if not n:
        raise GunFarError("no gunshot records found: is this EFFECTS.XML?")
    assert len(out) == len(plain)
    return bytes(out), n


def _op_gun_far_xml(plain, params):
    return scale_xml(plain, float(params["factor"]))


from . import dataedit as _dataedit  # noqa: E402
_dataedit.OPS.setdefault("gun_far_xml", _op_gun_far_xml)


def data_edits(v: dict, prefix: str = "js_") -> list:
    factor = FACTORS.get(str(v.get(prefix + "gun_far", "stock")))
    if not factor:
        return []
    from .model import FileEdit
    if prefix == "gr_":
        return [FileEdit("gun_far_xml", r"/EFFECTS\.XML$", "", {"factor": factor},
                         "gunshots carry %gx as far (EFFECTS.XML min and rolloff)" % factor)]
    return [FileEdit("gun_far_xbs", r"/EFFECTS\.XBS$", "GR.IMG", {"factor": factor},
                     "gunshots carry %gx as far (EFFECTS.XBS rolloff)" % factor)]


# --------------------------------------------------------------------------------------------
# 2. Through walls: SoundPropagationManager::PropagateForAudio (0x003D2470), all in place
# --------------------------------------------------------------------------------------------

D_SAVE = 0x003D2668         # the delay slot after "d < rolloff": keeps d at sp+0x78 (unused padding)
OWN_SITE = 0x003D2588       # your own gun: now "b OPEN"; the rest of that block holds FADE
FADE = 0x003D2590
WALL2 = 0x003D23E0          # the old room test: only this function called it, and no longer does
TAIL = 0x003D275C           # the two room-test calls, the cull, and the play, rewritten
TAIL_END = 0x003D2808       # the epilogue, unchanged

OUTDOOR = 0x004C60A0        # room +0xA8, vt+0x48 == 1: the outdoor kind of room
FLC = 0x004C40E0            # RSSimRoom::FindLineCollision(room, line, info, skip, len, in, mask, n, b)
SETCULL = 0x00235710        # Emitter::SetDistanceCull (vt+0xA8 of both emitter classes that propagate)
SETLEVELS = 0x002356C0      # Emitter::SetComponentSoundLevels (vt+0xB8; recomputes, ignores f12/f13)
LEVEL_DIRECT, LEVEL_INDIRECT = 0x00597810, 0x00597808    # the engine's 0.6 / 0.4

#: the flags AwarenessMgr::CheckLineOfSight hands the same trace (JS 0x003D46D4..0x003D476C):
#: kLineOfSightTest | kIgnoreLightOfSightTransparentControllers | kCountUserFlag |
#: kLineIgnoreHumanControllers, see-through faces (kLineOfSightTransparent) and a count of 8
LOS_FLAGS, LOS_MASK, LOS_COUNT = 0x1C10, 0x4, 8


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


JS_STOCK = {}
JS_STOCK.update(_stock_words(WALL2, (       # the room test, 0x003D23E0..0x003D246C
    "27BDFFD0 FFBF0020 7FB10010 7FB00000 00A0882D 14F10003 0140802D 10000017"
    "0000102D 10E00005 00E0202D 0C131828 00000000 1040000A 00000000 12200006"
    "0000102D 0C131828 0220202D 10400004 00000000 0000102D 10000009 DFBF0020"
    "3C010059 24020001 C4207818 E6000010 3C010059 C4207818 E6000014 DFBF0020"
    "7BB10010 7BB00000 03E00008 27BD0030")))
JS_STOCK.update(_stock_words(OWN_SITE, (    # own gun: cull off, 0.6 / 0.4, levels, return
    "8E590000 0240202D 8F3900A8 0320F809 0000282D 3C010059 C4207810 E6200010"
    "3C010059 C4207808 E6200014 8E590000 C62C0010 C62D0014 8F3900B8 0320F809"
    "0240202D 1000008F DFBF0070")))
JS_STOCK.update(_stock_words(TAIL, (        # room test x2, cull, play
    "12A0000C 00000000 8E290040 0260202D 02A0282D 0200382D 27A60090 27A800A0"
    "0220502D 0C0F48F8 0000582D 1000000B 304200FF 8E290040 0260202D 0200282D"
    "02A0382D 27A600A0 27A80090 0220502D 0C0F48F8 0000582D 304200FF 10400008"
    "00000000 8E590000 0240202D 8F3900A8 0320F809 24050001 1000000C 00000000"
    "8E590000 0240202D 8F3900A8 0320F809 0000282D 8E590000 C62C0010 C62D0014"
    "8F3900B8 0320F809 0240202D")))
JS_STOCK[D_SAVE] = 0x00000000
#: words the patch relies on but never writes; checked by selftest
JS_READS = {LEVEL_DIRECT: 0x3F19999A, LEVEL_INDIRECT: 0x3ECCCCCD,     # 0.6, 0.4
            FLC: 0x27BDFEF0, OUTDOOR: 0x27BDFFE0, SETCULL: 0x27BDFFE0, SETLEVELS: 0x27BDFFE0,
            0x005A8B00 + 0xA8: SETCULL, 0x005A8B00 + 0xB8: SETLEVELS,    # the two emitter vtables
            0x005A9AB0 + 0xA8: SETCULL, 0x005A9AB0 + 0xB8: SETLEVELS}

MIN_S_F0_F0_F1, MAX_S_F0_F0_F1 = 0x46010029, 0x46010028      # R5900 MIN.S / MAX.S

# PropagateForAudio's frame: sp+0x78 d (saved at D_SAVE), +0x80 listener - gun, +0x90 the gun,
# +0xA0 the listener (free from here on); s0 listener room, s1 params (emitter+0x10), s2 emitter,
# s5 the gun's room (0 = none)
SRC_TAIL = """
tail:                                   ; stock rule: same room, or both rooms outdoors -> open
    beq   s0, s5, open
    move  a0, s0
    jal   OUTDOOR
    nop
    beqz  v0, wall                      ; listener indoors
    move  a0, s5
    beqz  a0, open                      ; the gun in no room, the listener outdoors
    nop
    jal   OUTDOOR
    nop
    bnez  v0, open
    nop
wall:                                   ; stock culled the sound here
    lwc1  f0, 0x78(sp)                  ; d
    lw    v0, 0xC(s1)                   ; rolloff (float bits)
    lui   at, 0x42C8                    ; only a gunshot or a blast (rolloff >= 100 m) is traced
    slt   at, v0, at
    bnez  at, FADE
    lui   at, 0x4248                    ; (delay) 50 m
    b     WALL2
    mtc1  at, f1                        ; (delay)
    nop                                 ; (unreachable padding up to the epilogue)
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
open:
    lui   at, 0x3F80
    mtc1  at, f0                        ; full level
level:                                  ; f0 = level 0.4 .. 1: direct 0.6 f0, indirect 0.4 f0
    lui   at, %hi(LEVEL_DIRECT)
    lwc1  f1, %lo(LEVEL_DIRECT)(at)
    mul.s f1, f1, f0
    swc1  f1, 0x10(s1)
    lwc1  f1, %lo(LEVEL_INDIRECT)(at)
    mul.s f1, f1, f0
    swc1  f1, 0x14(s1)
    move  a0, s2
    jal   SETCULL                       ; never culled for a wall: SetDistanceCull(0)
    move  a1, zero
    jal   SETLEVELS
    move  a0, s2                        ; then the epilogue
"""

SRC_WALL2 = """
wall2:                                  ; f0 = d, f1 = 50 m
    c.lt.s f1, f0
    bc1t  FADE                          ; beyond 50 m: no trace
    lui   at, 0x3F80                    ; (delay)
    beqz  s5, FADE                      ; the gun in no room: nowhere to start the trace
    mtc1  at, f2                        ; (delay) 1.0
    div.s f2, f2, f0                    ; 1/d
    lwc1  f3, 0x80(sp)                  ; the line: from the gun (+0x90) toward the listener,
    mul.s f3, f3, f2                    ; unit direction written over the listener's point (+0xA0)
    swc1  f3, 0xA0(sp)
    lwc1  f3, 0x84(sp)
    mul.s f3, f3, f2
    swc1  f3, 0xA4(sp)
    lwc1  f3, 0x88(sp)
    mul.s f3, f3, f2
    swc1  f3, 0xA8(sp)
    addiu sp, sp, -0x60                 ; the collision record
    move  a0, s5
    addiu a1, sp, 0xF0
    move  a2, sp
    move  a3, zero
    mov.s f12, f0
    li    t0, LOS_FLAGS
    li    t1, LOS_MASK
    li    t2, LOS_COUNT
    jal   FLC                           ; the AI's own sight trace, gun -> listener
    move  t3, zero
    addiu sp, sp, 0x60
    beqz  v0, OPEN                      ; a clear line (doorway, window): as in the same room
    lwc1  f0, 0x78(sp)                  ; (delay) d
    b     FADE
    nop
"""

SRC_OWN = """
own:
    b     OPEN                          ; your own gun: full level, as before
    nop
fade:                                   ; f0 = d: 1.0 within 3 m, down to 0.4 by 10 m
    lui   at, 0x3DB0
    mtc1  at, f1
    mul.s f0, f0, f1                    ; 0.0859 d
    lui   at, 0x3FA1
    mtc1  at, f1
    sub.s f0, f1, f0                    ; 1.2578 - 0.0859 d
    lui   at, 0x3F80
    mtc1  at, f1
    .word MIN_S
    lui   at, 0x3ECD
    mtc1  at, f1
    b     LEVEL
    .word MAX_S
    nop
    nop
    nop
    nop
"""

SYMS = dict(OUTDOOR=OUTDOOR, FLC=FLC, SETCULL=SETCULL, SETLEVELS=SETLEVELS, FADE=FADE, WALL2=WALL2,
            LEVEL_DIRECT=LEVEL_DIRECT, LEVEL_INDIRECT=LEVEL_INDIRECT, LOS_FLAGS=LOS_FLAGS,
            LOS_MASK=LOS_MASK, LOS_COUNT=LOS_COUNT, MIN_S=MIN_S_F0_F0_F1, MAX_S=MAX_S_F0_F0_F1)


def _code():
    """{va: word} for the three rewritten stretches and the d save."""
    tail, lt = assemble(SRC_TAIL, TAIL, SYMS)
    syms = dict(SYMS, OPEN=lt["open"], LEVEL=lt["level"])
    wall2, _lw = assemble(SRC_WALL2, WALL2, syms)
    own, lo = assemble(SRC_OWN, OWN_SITE, syms)
    if TAIL + 4 * len(tail) != TAIL_END:
        raise ValueError("tail must end on the epilogue (%d words)" % len(tail))
    if len(wall2) > 36 or len(own) != 19 or lo["fade"] != FADE:
        raise ValueError("through-walls code outgrows its stretches")
    out = {}
    for base, words in ((TAIL, tail), (WALL2, wall2), (OWN_SITE, own)):
        for i, w in enumerate(words):
            out[base + 4 * i] = w
    out[D_SAVE] = 0xE7A00078                    # swc1 f0, 0x78(sp)
    return out


def edits():
    """(va, value, stock, note)."""
    def note(va):
        if va == D_SAVE:
            return "sound through walls: keep the listener distance"
        if WALL2 <= va < WALL2 + 0x90:
            return "sound through walls: the line trace (over the old room test)"
        if OWN_SITE <= va < OWN_SITE + 0x4C:
            return "sound through walls: own gun -> full level; the distance muffle"
        return "sound through walls: room rule, trace, muffle by distance, never culled"
    return [(va, w, JS_STOCK[va], note(va)) for va, w in sorted(_code().items()) if w != JS_STOCK[va]]


def js_edits(v: dict):
    return edits() if v.get("js_room_sound") else []


# --------------------------------------------------------------------------------------------
# 3. Through walls, Ghost Recon (SLUS-20613): a routine behind the empty
#    SoundPropagationManager::PropagateForAudio stub (0x003F2970)
# --------------------------------------------------------------------------------------------
# The stub's only caller is IkeSimulationMgr::PropagateForAudio (jal at 0x003A2230), reached from
# Emitter::Propagate (vt+0x5C of both emitter classes) with a1 = the emitter. The routine is spread
# over six stretches nothing references (unreferenced functions and the alignment padding after
# them); every jump between them is explicit.

GR_STUB = 0x003F2970                # jr ra; nop  ->  j room; nop

GR_FRAGS = {                        # name: (base, words)
    "D": (0x00480480, 20),          # RSParser::~RSParser (17) + 3 padding
    "A": (0x005485D0, 40),          # ModsContents::~ModsContents (37) + 3 padding
    "B": (0x0054FC28, 26),          # sceScfGetTimeNotation
    "C": (0x00542F60, 24),          # RSArray<RSArray<RSMemoryPoolNode<RSXMLTag>>*>::~RSArray
    "E": (0x0054FAC8, 16),          # sceScfGetSpdif (15) + 1 padding
    "F": (0x0054FFF4, 3),           # 1 padding after AdjustTime + sceScfGetGMTfromRTC (2)
}

GR_SYMS = dict(
    SIMMGR=0x005EACF0,              # mIIkeSimulationMgr (what Emitter::Propagate calls through)
    GSYS=0x00630B40,                # g_graphic_sys: +0x2880 = two views (CGraphicSystem::EnableSplitScreen)
    SCENE=0x006376D0,               # RSSimScene::s_instance
    FINDROOM=0x005044E0,            # RSSimScene::FindRoom(const RSVector3 &)
    GETOBS=0x0038FC00,              # IkeSimulationMgr::GetObserver(int view) -> the SimHuman that view follows
    OUTDOOR=0x004D5D70,             # RSSimRoom::IsOutdoorRoom (room +0xA8, vt+0x48 == 1)
    VSUB=0x00114490,                # operator-(RSVector3 &out, a, b)
    VLEN=0x00114690,                # RSVector3::Length -> f0
    VNORM=0x00114740,               # RSVector3::Normalize
    VCOPY=0x00122370,               # RSVector3::operator=
    FLC=0x004D8540,                 # RSSimRoom::FindLineCollision(line, info, len, skip, flags, mask, n, b)
    SETLEVELS=0x00234240,           # Emitter::SetComponentSoundLevels (recomputes the volume; f12/f13 unused)
    LOS_FLAGS=LOS_FLAGS, LOS_MASK=LOS_MASK, LOS_COUNT=LOS_COUNT,    # AwarenessMgr::CheckLineOfSight's (0x003F48B0)
    MIN_S=MIN_S_F0_F0_F1, MAX_S=MAX_S_F0_F0_F1,
)

# Frame (0xA0): sp+0 the collision record (FindLineCollision writes +0x00..+0x4F), +0x50 the line
# (origin; direction at +0x5C: Ghost Recon's RSLine3 is two packed RSVector3s), +0x68 d, +0x6C the
# best level so far, +0x70 s2, +0x80 s4, +0x90 ra.  s0 = the emitter, s1 = the listener's room (then
# the room the trace starts in), s2 = the sound's room (-1 = not looked up yet), s4 = the view.
# s0 and s1 are not saved: the only caller restores its own s0/s1 from its frame right after the
# call and uses neither (GR_READS pins those words).
GR_SRC = {
    "D": """
room:                                   ; a1 = the emitter
    addiu sp, sp, -0xA0
    sd    ra, 0x90(sp)
    sq    s2, 0x70(sp)
    sq    s4, 0x80(sp)
    move  s0, a1
    lui   at, 0x3E4D                    ; 0.2: the muffle floor (0.2 + 0.2)
    sw    at, 0x6C(sp)
    lui   v0, %hi(GSYS)
    lw    v0, %lo(GSYS)(v0)
    lbu   s4, 0x2880(v0)
    sltu  s4, zero, s4                  ; split screen: views 1 and 0, else view 0
    j     view
    li    s2, -1                        ; the sound's room: not looked up yet
lookup:                                 ; no soldier or vehicle: the room its position is in
    lui   a0, %hi(SCENE)
    lw    a0, %lo(SCENE)(a0)
    jal   FINDROOM
    addiu a1, s0, 0x40
    j     have
    move  s2, v0
""",
    "A": """
view:
    lui   a0, %hi(SIMMGR)
    lw    a0, %lo(SIMMGR)(a0)
    jal   GETOBS                        ; the soldier this view follows
    move  a1, s4
    beqz  v0, open                      ; nobody: full level
    lw    t0, 0x50(s0)
    beq   t0, v0, open                  ; his own gun or steps: full level
    lw    s1, 0x154(v0)                 ; the room he sees from (IkeSimController::GetViewSimRoom)
    beqz  s1, open                      ; in no room: full level
    addiu a0, sp, 0x50
    jal   VCOPY                         ; the line starts at his eye (SimHuman::GetAwarenessLocation)
    addiu a1, v0, 0x518
    addiu a0, sp, 0x5C
    addiu a1, s0, 0x40
    jal   VSUB                          ; direction: eye -> sound
    addiu a2, sp, 0x50
    jal   VLEN
    addiu a0, sp, 0x5C
    swc1  f0, 0x68(sp)                  ; d
    lwc1  f1, 0x1C(s0)                  ; the sound's rolloff
    c.lt.s f0, f1
    bc1f  fade                          ; past its rolloff for him: the distance muffle, no room test
    nop
    bgez  s2, have
    lw    t0, 0x50(s0)
    beqz  t0, tolookup
    nop
    lw    s2, 0x154(t0)                 ; the room its soldier or vehicle is in
have:
    beq   s1, s2, open                  ; same room
    move  a0, s1
    jal   OUTDOOR
    nop
    beqz  v0, wall                      ; he is indoors: trace from his eye, in his room
    lbu   t0, 0xA1(s0)                  ; the emitter's "propagation disabled"
    b     outdoors
    sltiu t1, s2, 1                     ; the sound in no room
wall:
    lw    v0, 0x1C(s0)
    lui   at, 0x42C8                    ; rolloff 100 m or more: a gunshot, a blast, a loud world sound
    b     wall2
    slt   at, v0, at
""",
    "B": """
wall2:
    bnez  at, fade                      ; footsteps, reloads, impacts: no trace
    lw    v1, 0x68(sp)
    lui   at, 0x4248                    ; 50 m
    slt   at, at, v1
    bnez  at, fade
    addiu a0, sp, 0x5C
    jal   VNORM
    nop
    move  a0, s1                        ; the room the line starts in
    addiu a1, sp, 0x50
    move  a2, sp
    move  a3, zero
    lwc1  f12, 0x68(sp)
    li    t0, LOS_FLAGS
    li    t1, LOS_MASK
    li    t2, LOS_COUNT
    jal   FLC                           ; the AI's own sight trace
    move  t3, zero
    beqz  v0, open                      ; a clear line (a doorway, a window): full level
    nop
    b     fade
    nop
tolookup:
    j     lookup
    nop
""",
    "C": """
fade:                                   ; half the level: 0.5 within 3 m, 0.2 by 10 m
    lwc1  f0, 0x68(sp)
    lui   at, 0x3D30
    mtc1  at, f1
    mul.s f0, f0, f1
    lui   at, 0x3F21
    mtc1  at, f1
    sub.s f0, f1, f0                    ; 0.6289 - 0.04297 d
    lui   at, 0x3F00
    mtc1  at, f1
    .word MIN_S
next:
    lwc1  f1, 0x6C(sp)
    .word MAX_S                         ; the view that hears it best, at least the floor
    swc1  f0, 0x6C(sp)
    bgtz  s4, view
    addiu s4, s4, -1
    swc1  f0, 0x20(s0)                  ; direct
    swc1  f0, 0x24(s0)                  ; indirect
    jal   SETLEVELS
    move  a0, s0
    ld    ra, 0x90(sp)
    lq    s2, 0x70(sp)
    lq    s4, 0x80(sp)
    jr    ra
    addiu sp, sp, 0xA0
""",
    "E": """
outdoors:                               ; he is outdoors (t0 propagation disabled, t1 the sound in no room)
    or    t0, t0, t1
    bnez  t0, open
    move  a0, s2
    jal   OUTDOOR
    nop
    bnez  v0, open                      ; both outdoors
    addiu a0, sp, 0x5C
    addiu a1, sp, 0x50                  ; the sound is indoors: trace from it, in its room
    jal   VSUB                          ; direction: sound -> eye
    addiu a2, s0, 0x40
    addiu a0, sp, 0x50
    jal   VCOPY
    addiu a1, s0, 0x40
    b     wall
    move  s1, s2
""",
    "F": """
open:
    lui   at, 0x3F00                    ; full level: 0.5 + 0.5
    b     next
    mtc1  at, f0
""",
}
GR_LABELS = ("room", "lookup", "view", "have", "wall", "wall2", "tolookup", "fade", "next", "outdoors", "open")

GR_STOCK = {GR_STUB: 0x03E00008, GR_STUB + 4: 0x00000000}
for _base, _hex in (
        (0x00480480, "27BDFFE0 FFBF0010 7FB00000 70808628 12000008 72001628 0005143C 0002143F"
                     "18400003 AE000408 0C040B14 00000000 72001628 DFBF0010 7BB00000 03E00008"
                     "27BD0020 00000000 00000000 00000000"),
        (0x005485D0, "27BDFFD0 FFBF0020 7FB10010 7FB00000 70808E28 12200019 70A08628 26240028"
                     "0C14FAB8 2405FFFF 26240020 0C14FAB8 2405FFFF 26240018 0C14FAB8 2405FFFF"
                     "26240010 0C14FAB8 2405FFFF 26240008 0C14FAB8 2405FFFF 72202628 0C14FAB8"
                     "2405FFFF 0010143C 0002143F 18400004 72201628 0C040B14 72202628 72201628"
                     "DFBF0020 7BB10010 7BB00000 03E00008 27BD0030 00000000 00000000 00000000"),
        (0x0054FC28, "27BDFFE0 FFBF0010 0C153E72 00000000 10400003 3C020057 10000010 90420B7F"
                     "0C1046E4 03A0202D 8FA20000 00021342 30420007 14400003 37A40004 10000007"
                     "0000102D 24050001 0C10477C 24060001 93A30004 00031942 30620001 DFBF0010"
                     "03E00008 27BD0020"),
        (0x00542F60, "27BDFFD0 FFBF0020 7FB10010 7FB00000 70808E28 1220000C 70A08628 8E240000"
                     "10800004 0010143C 0C040AF8 00000000 0010143C 0002143F 18400004 72201628"
                     "0C040B14 72202628 72201628 DFBF0020 7BB10010 7BB00000 03E00008 27BD0030"),
        (0x0054FAC8, "27BDFFE0 FFBF0010 0C153E72 00000000 10400003 3C030057 10000005 90620B7D"
                     "0C1046E4 03A0202D 8FA20000 30420001 DFBF0010 03E00008 27BD0020 00000000"),
        (0x0054FFF4, "00000000 08153FDA 2405FDE4")):
    GR_STOCK.update(_stock_words(_base, _hex))

#: words the routine relies on but never writes; checked by selftest
GR_READS = {
    0x003A2228: 0x72202E28, 0x003A222C: 0x72003628,     # the caller: move a1, s1; move a2, s0
    0x003A2230: 0x0C0FCA5C, 0x003A2234: 0x70402628,     # jal the stub; move a0, v0
    0x003A2238: 0xDFBF0020, 0x003A223C: 0x7BB10010,     # then ld ra; lq s1; lq s0; jr ra: s0/s1 are its own
    0x003A2240: 0x7BB00000, 0x003A2244: 0x03E00008, 0x003A2248: 0x27BD0030,
    0x0059F664: 0x003A2200,                             # IkeSimulationMgr vt+0x104
    0x0059816C: 0x002344E0, 0x005990DC: 0x002344E0,     # Emitter / MovingEmitter vt+0x5C: Emitter::Propagate
    0x005981C8: 0x00234240, 0x00599138: 0x00234240,     # ... vt+0xB8: SetComponentSoundLevels
    0x002345F4: 0x904600A1,                             # Propagate passes +0xA1 (propagation disabled)
    0x005044E0: 0x27BDFF80, 0x0038FC00: 0x27BDFFD0, 0x004D5D70: 0x27BDFFE0, 0x00114490: 0xC4A10000,
    0x00114690: 0x27BDFFF0, 0x00114740: 0x27BDFFE0, 0x00122370: 0xC4A00000, 0x004D8540: 0x27BDFEF0,
    0x00234240: 0x27BDFFB0,                             # the functions called
    0x00197EC4: 0x24820518,                             # GetAwarenessLocation: addiu v0, a0, 0x518
    0x0039B7A4: 0x8C820154,                             # GetViewSimRoom: lw v0, 0x154(a0)
    0x00233554: 0xAC640050,                             # Emitter::SetController: the owner at +0x50
    0x0023348C: 0x24420010,                             # GetParams: emitter + 0x10
    0x002347A8: 0xC4410020, 0x002347B0: 0xC4400024,     # CalculateEffectiveVolume: direct + indirect
    0x0050A7E0: 0xE48C0028, 0x0050B084: 0xC6A00028,     # the voice's volume, into the SPU level
    0x0044EBB4: 0xA0852880,                             # EnableSplitScreen: sb a1, 0x2880(a0)
    0x0058BC78: 0x400, 0x0058BC80: 0x800, 0x0058BC88: 0x1000, 0x0058BCA8: 0x10,    # the trace flags
    0x0058BCD0: 0x4, 0x003F48CC: 0x240A0008,            # see-through faces, count 8 (CheckLineOfSight)
}


def _gr_code():
    """({va: word}, labels): the routine in its six stretches and the stub's jump."""
    labels, out = {}, {}
    for _pass in range(2):
        out = {}
        for key, (base, n) in GR_FRAGS.items():
            syms = dict(GR_SYMS)
            for k in GR_LABELS:
                syms.setdefault(k, labels.get(k, base))
            words, lab = assemble(GR_SRC[key], base, syms)
            if len(words) > n:
                raise ValueError("Ghost Recon through-walls stretch %s: %d words > %d" % (key, len(words), n))
            labels.update(lab)
            for i, w in enumerate(words):
                out[base + 4 * i] = w
    out[GR_STUB] = assemble("j %#x" % labels["room"], GR_STUB)[0][0]
    out[GR_STUB + 4] = 0x00000000
    return out, labels


def gr_edits(v: dict):
    """(va, value, stock, note) for Ghost Recon's 'gr_room_sound': every word of the routine and the stub."""
    if not v.get("gr_room_sound"):
        return []
    code, _labels = _gr_code()
    return [(va, w, GR_STOCK[va],
             "sound through walls: the empty SoundPropagationManager::PropagateForAudio jumps to the routine"
             if va in (GR_STUB, GR_STUB + 4) else
             "sound through walls: room rule, sight trace, muffle by distance (both split-screen views)")
            for va, w in sorted(code.items())]


def _gr_flow_errors(code):
    """Every branch and jump in the routine lands on a routine word or a function it means to call."""
    bad = []
    calls = {GR_SYMS[k] for k in ("FINDROOM", "GETOBS", "OUTDOOR", "VSUB", "VLEN", "VNORM", "VCOPY", "FLC",
                                  "SETLEVELS")}
    for va, w in code.items():
        op = w >> 26
        off = w & 0xFFFF
        off = off - 0x10000 if off & 0x8000 else off
        if op in (1, 4, 5, 6, 7) or (op == 0x11 and (w >> 21) & 31 == 8):
            if va + 4 + 4 * off not in code:
                bad.append("gr branch at %08X leaves the routine" % va)
        elif op == 2 and ((va & 0xF0000000) | ((w & 0x3FFFFFF) << 2)) not in code:
            bad.append("gr jump at %08X leaves the routine" % va)
        elif op == 3 and ((va & 0xF0000000) | ((w & 0x3FFFFFF) << 2)) not in calls:
            bad.append("gr call at %08X to an unexpected function" % va)
    return bad


def selftest(gr_elf: bytes, js_elf: bytes, xbs: bytes = None):
    """Every stock word against the executables, no address twice, the Ghost Recon routine's
    branches inside it; the table op on a real EFFECTS.XBS when one is given. [] = pass."""
    bad = []
    for va, w in list(JS_STOCK.items()) + list(JS_READS.items()):
        off = va - 0x100000 + 0x100
        if int.from_bytes(js_elf[off:off + 4], "little") != w:
            bad.append("js %08X" % va)
    e = edits()
    if len({va for va, *_ in e}) != len(e):
        bad.append("js duplicate VA")
    if any(va not in JS_STOCK for va, *_ in e):
        bad.append("js VA without a stock word")
    if gr_elf is not None:
        for va, w in list(GR_STOCK.items()) + list(GR_READS.items()):
            off = va - 0x100000 + 0x80
            if int.from_bytes(gr_elf[off:off + 4], "little") != w:
                bad.append("gr %08X" % va)
    ge = gr_edits({"gr_room_sound": True})
    if len({va for va, *_ in ge}) != len(ge):
        bad.append("gr duplicate VA")
    if any(va not in GR_STOCK or GR_STOCK[va] != st for va, _w, st, _n in ge):
        bad.append("gr VA without its stock word")
    if gr_edits({}) or gr_edits({"gr_room_sound": False}):
        bad.append("gr edits with the option off")
    code, labels = _gr_code()
    if set(labels) != set(GR_LABELS):
        bad.append("gr labels %s" % sorted(set(labels) ^ set(GR_LABELS)))
    bad += _gr_flow_errors(code)
    if xbs is not None:
        recs = {name: (mn, ro) for name, _p, mn, ro, _a in xbs_records(xbs)}
        amb = {name: a for name, _p, _mn, _ro, a in xbs_records(xbs)}
        for factor in (1.5, 2.0, 3.0):
            new, n = scale_xbs(xbs, factor)
            after = {name: (mn, ro) for name, _p, mn, ro, _a in xbs_records(new)}
            if len(new) != len(xbs) or set(after) != set(recs):
                bad.append("xbs shape changed at %g" % factor)
                continue
            if bytes(b for i, b in enumerate(new) if b != xbs[i]) and \
                    sum(1 for i in range(len(new)) if new[i] != xbs[i]) > 4 * n:
                bad.append("xbs changed more than the rolloff words at %g" % factor)
            for name, (mn, ro) in recs.items():
                want = ro * factor if carries(name, ro, amb[name]) else ro
                if after[name] != (mn, want):
                    bad.append("xbs %s at %g" % (name, factor))
            for name in ("w_m4soccum_ss.wav", "w_smp5_ss.wav", "w_sm9_ss.wav", "w_sr25s_ss.wav",
                         "w_m16_rl.wav", "e_bullet_wiz1.wav", "e_bullet_dirt.wav"):
                if name in recs and after[name] != recs[name]:
                    bad.append("xbs %s moved" % name)
            for name in ("w_m16_ss.wav", "w_ak47_rc.wav", "w_m249_rc.wav"):
                if name in recs and after[name][1] != recs[name][1] * factor:
                    bad.append("xbs %s not scaled" % name)
            if n < 100:
                bad.append("xbs only %d records at %g" % (n, factor))
    return bad

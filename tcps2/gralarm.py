"""Whisper Shadow's alarm, brought down to the other missions' level: Jungle Storm (SLUS-20820).

Where the alarm comes from
--------------------------
Jungle Storm has one mission siren, ``a_siren.wav``: a 2.45 s continuous tone
(11,025 Hz, RMS -13.0 dBFS -- about 6 dB above an AK-47 shot, 11 dB above the fog
horn, 15 dB above the bug loops and 22 dB above tree creaks). Its EFFECTS.XBS
record plays it at full volume within 25 m and fades it in a straight line to
nothing at 400 m. The same sample sits in both level banks that carry it
(bank 58 record 6, bank 60 record 13).

Two campaign missions play it, both through the mission script's "play a sound
at a location" action (CallResponse 0x60, JS 0x00349F50, case at 0x0034E8BC:
pops duration, volume, location, sound; sends message 0x1F9; the sound manager's
handler 0x002517D0 makes a positional emitter, sets its volume (emitter +0xAC),
and, when the duration is not 0, its loop timer (+0xC8) and plays it looping):

=============================  ========  ======  ========  ==========================
mission                        speakers  volume  duration  started by
=============================  ========  ======  ========  ==========================
J03 Ocelot Desert (U05_RAIL)   1         1.0     15 s      the alarm timer, mid-game
J07 Whisper Shadow (U03)       4         1.0     170-200 s InitMission, 2 s in
=============================  ========  ======  ========  ==========================

(The Defend and Siege game types sound a different alarm, ``m_alarm1.wav``, as a
2D one-shot through action 0x5F.)

So Whisper Shadow is not a louder sound but four copies of the same one,
started in the same frame -- they add in step -- and each kept looping for
about three minutes. From the insertion point the four sum to 2.1x one siren
at point-blank (+6 dB); in the central compound to 3.6x (+11 dB).

The fix
-------
Only Whisper Shadow's script changes (``U03_RESCUE.MIS``, the ``<ScriptCompiled>``
block -- the one the game loads: JS 0x003651A8 hands the +0x48 text to
LoadScript 0x00357F00). Each of the four siren calls gets volume 0.25
(-12 dB) and 15 s, Ocelot Desert's length: four sirens in step then never
exceed one siren heard point-blank, and they stop after about six cycles.
Every value is checked against the stock script before anything is written,
and the file keeps its length. Ocelot Desert and the shared sound record are
untouched.
"""

from __future__ import annotations

import re
import struct

MISSION = r"/U03_RESCUE\.MIS$"
SIREN = "a_siren.wav"
PLAY_AT = 0x60                   # CallResponse "play a sound at a location"
#: effect ScriptId -> stock loop seconds, per Whisper Shadow speaker (Sfx_Alarm01..04)
STOCK_SECONDS = {180: 200.0, 184: 180.0, 182: 185.0, 183: 170.0}
STOCK_VOLUME = 1.0
TAME_VOLUME, TAME_SECONDS = 0.25, 15.0

_BLOCK = re.compile(rb"<ScriptCompiled>(\s*)([A-P]+)(\s*)</ScriptCompiled>")
_T_STRING, _T_OBJECT, _T_FLOAT, _T_CALL = 4, 2, 3, 6


class AlarmError(ValueError):
    pass


def _decode(text: bytes) -> bytes:
    """A..P nibble text (low nibble first) -> bytes."""
    return bytes((text[i] - 65) | ((text[i + 1] - 65) << 4) for i in range(0, len(text) - 1, 2))


def _encode(data: bytes) -> bytes:
    return bytes(c for b in data for c in (65 + (b & 15), 65 + (b >> 4)))


def _f32(b: int) -> float:
    return struct.unpack("<f", struct.pack("<I", b))[0]


def _bits(x: float) -> int:
    return struct.unpack("<I", struct.pack("<f", x))[0]


def _strings(blob: bytes):
    """({id: text}, offset where the node graph starts)."""
    count = struct.unpack_from("<I", blob, 0)[0]
    o, out = 4, {}
    for _ in range(count):
        sid, n = struct.unpack_from("<II", blob, o)
        out[sid] = blob[o + 8:o + 8 + n].decode("latin1")
        o += 8 + n
    return out, o


def siren_calls(blob: bytes) -> list:
    """[(offset of the volume word, offset of the seconds word, effect id, volume, seconds)] for
    every ``play a_siren.wav at <effect>, <volume>, <seconds>`` in a compiled script."""
    names, base = _strings(blob)
    n = (len(blob) - base) // 4
    w = struct.unpack_from("<%dI" % n, blob, base)
    out = []
    for k in range(n - 9):
        if (w[k] == _T_STRING and names.get(w[k + 1], "").lower() == SIREN and w[k + 2] == _T_OBJECT
                and w[k + 4] == _T_FLOAT and w[k + 6] == _T_FLOAT and w[k + 8] == _T_CALL
                and w[k + 9] == PLAY_AT):
            at = base + 4 * k
            out.append((at + 20, at + 28, w[k + 3], _f32(w[k + 5]), _f32(w[k + 7])))
    return out


def tame_mission(plain: bytes, volume=TAME_VOLUME, seconds=TAME_SECONDS):
    """(new .MIS bytes, calls changed). Refuses anything but the stock Whisper Shadow calls."""
    m = _BLOCK.search(plain)
    if not m:
        raise AlarmError("no compiled script in this mission file")
    blob = bytearray(_decode(m.group(2)))
    calls = siren_calls(bytes(blob))
    found = {obj: (vol, sec) for _v, _s, obj, vol, sec in calls}
    want = {obj: (STOCK_VOLUME, sec) for obj, sec in STOCK_SECONDS.items()}
    if len(calls) != len(STOCK_SECONDS) or found != want:
        raise AlarmError("Whisper Shadow's siren calls are not the stock ones: %r" % sorted(found.items()))
    for vat, sat, _obj, _vol, _sec in calls:
        struct.pack_into("<I", blob, vat, _bits(float(volume)))
        struct.pack_into("<I", blob, sat, _bits(float(seconds)))
    text = _encode(bytes(blob))
    if len(text) != len(m.group(2)):
        raise AlarmError("the re-encoded script changed length")
    out = plain[:m.start(2)] + text + plain[m.end(2):]
    if len(out) != len(plain):
        raise AlarmError("the mission file changed length")
    return out, len(calls)


def _op_alarm_tame(plain, params):
    return tame_mission(plain, float(params.get("volume", TAME_VOLUME)),
                        float(params.get("seconds", TAME_SECONDS)))


def _register():
    from . import dataedit
    dataedit.OPS.setdefault("alarm_tame_mis", _op_alarm_tame)


_register()


def data_edits(v: dict, prefix: str = "js_") -> list:
    if not v.get(prefix + "alarm_tame"):
        return []
    from .model import FileEdit
    return [FileEdit("alarm_tame_mis", MISSION, "GR.IMG",
                     {"volume": TAME_VOLUME, "seconds": TAME_SECONDS},
                     "Whisper Shadow's four sirens at -12 dB, 15 s")]


def selftest(mission_plain: bytes) -> list:
    """Against the stock U03_RESCUE.MIS. [] = pass."""
    bad = []
    try:
        new, n = tame_mission(mission_plain)
    except AlarmError as ex:
        return [str(ex)]
    if n != 4 or len(new) != len(mission_plain):
        bad.append("changed %d calls, length %+d" % (n, len(new) - len(mission_plain)))
    blob = _decode(_BLOCK.search(new).group(2))
    if sorted((o, round(v, 3), round(s, 3)) for _a, _b, o, v, s in siren_calls(blob)) != \
            sorted((o, TAME_VOLUME, TAME_SECONDS) for o in STOCK_SECONDS):
        bad.append("patched calls read back wrong")
    try:
        tame_mission(new)
        bad.append("a second pass was accepted")
    except AlarmError:
        pass
    return bad

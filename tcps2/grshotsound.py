"""The shotgun's own firing sound, borrowed from The Sum of All Fears (SLES-511.80).

Neither Ghost Recon nor Jungle Storm has a shotgun sound; Sum of All Fears, the same engine, does -- its
Benelli fires `w_shtgn_ss.wav`. This copies that sample in.

**How a sound name reaches audio.** Three hops, and the effects database is not one of them:

    the gun's StartSound -> the level's PS2SOUND\\BNK_<level>.IDC name table (a 128 bucket hash)
                         -> BNK_<bank>.SH record  ->  the bytes at that offset in BNK_<bank>.SB

`PS2LoadSoundData` rebuilds the whole sound set at every level change and loads a weapon's bank only when
some gun in the loaded kits carries the matching `WPN_*` token -- which is why a sound belonging to a gun
nobody is holding is simply silent. **Bank 0 is the exception: it is loaded unconditionally, in every path**,
and a bank is uploaded to SPU RAM whole, so every record in it is resident whether or not anything plays it.

So the sample goes into bank 0, over a record nothing uses. The donor is `W_AK47_SS.WAV` -- the AK's real
firing sounds are `W_AK47_RC/SF.WAV` in bank 1, and this single-shot variant is named by no gun, kit or
mission in either game. It already resolves to bank 0 in every level's name table, so no name table is
touched and the gun only has to ask for `w_ak47_ss.wav`.

**Why it is trimmed rather than resampled.** The sample is 7,216 bytes of 16 kHz PS2 ADPCM. Ghost Recon's
donor slot is 9,440 bytes and is already 16 kHz, so it goes in whole. Jungle Storm's is 6,528 bytes, and
running past it would land in the next record -- which matters, because that record is reachable under a
second name (`RECON_5.WAV`) as well as the dead `W_M16_RL.WAV`. So for Jungle Storm the sample is cut to
whole frames that fit and the last frame is marked as the end of the voice. The cut costs the tail of the
decay, and nothing else in the bank moves.

Every file written keeps its exact length, which matters twice over: these members have at most 8 bytes of
slack in the archive, and the sound code trusts two different lengths (the EE advances its SPU allocator by
the .SH trailer's total while the IOP uploads the real .SB file size), so neither may drift.
"""

from __future__ import annotations

import os
import struct

#: where the sample lives in Sum of All Fears, measured on the retail disc
SOAF_DIRS = (r"E:/PS2 Games/Sum of All Fears, The (Europe) (En,Fr,De,Es,It)",)
SOAF_BANK, SOAF_OFFSET, SOAF_LENGTH = "/BNK_17.SB", 736032, 7216
SOAF_RATE = 16000
SOAF_SHA1 = "1a9f55f8a570a3c8ac3e63232e094b83677825cf"

#: the sound the gun asks for, and the bank 0 record it lands on in each game
DONOR_NAME = "w_ak47_ss.wav"
DONOR_INDEX = {"gr_": 52, "js_": 55}

FRAME = 16                                                # one PS2 ADPCM frame: 2 header bytes + 14 of data
END_FLAG = 0x07                                           # frame flags: end of voice


class SoundError(Exception):
    pass


def _sh_record(sh: bytes, index: int) -> tuple:
    """(offset of the record, rate, lengthMs, byteLength, byteRate, sampleOffset).

    The .SH is a 16-byte header {fileSize, bankId, count, 0}, then 40-byte records, then {sbTotal, ssTotal}.
    Read off BNK_01.SH, whose two records chain 0 -> 6064 -> 11648, exactly its .SB's length.
    """
    count = struct.unpack_from("<I", sh, 8)[0]
    if not 0 <= index < count:
        raise SoundError("bank has %d records, no index %d" % (count, index))
    o = 16 + 40 * index
    rate, ms, blen, brate, off = struct.unpack_from("<5I", sh, o + 4)
    return o, rate, ms, blen, brate, off


def soaf_sample(dirs=SOAF_DIRS) -> bytes:
    """The Sum of All Fears shotgun sample, read from the user's own disc."""
    import hashlib
    import sys
    for d in dirs:
        if not os.path.isdir(d):
            continue
        sys.path.insert(0, r"C:/Users/Tristan/Documents/GitHub/TomClancyPS2-ModStudio/research/soaf")
        import soafimg
        img = soafimg.open_all(d)["SOAF.IMG"]
        sb = img.read_file(SOAF_BANK)
        s = sb[SOAF_OFFSET:SOAF_OFFSET + SOAF_LENGTH]
        if len(s) != SOAF_LENGTH or hashlib.sha1(s).hexdigest() != SOAF_SHA1:
            raise SoundError("%s%s at %d is not the shotgun sample" % (d, SOAF_BANK, SOAF_OFFSET))
        return s
    raise SoundError("the shotgun sound is taken from a Sum of All Fears disc, which was not found at %s"
                     % " or ".join(dirs))


def fit(sample: bytes, room: int) -> bytes:
    """The sample cut to whole frames that fit `room`, ending the voice on its last frame."""
    frames = min(len(sample), room) // FRAME
    if frames < 2:
        raise SoundError("only %d bytes of room: too little for the sample" % room)
    out = bytearray(sample[:frames * FRAME])
    for f in range(frames):                               # clear any end flag the cut left mid-sample
        out[f * FRAME + 1] &= ~END_FLAG & 0xFF
    out[(frames - 1) * FRAME + 1] = END_FLAG              # and end the voice on the last one we kept
    return bytes(out)


def _op_shotgun_snd_sb(plain, params, sibling=None):
    """Write the sample over the donor's run in the bank body. The .SH beside it says where and how much."""
    if sibling is None:
        raise SoundError("the bank body is written from its own .SH")
    _o, _rate, _ms, blen, _brate, off = _sh_record(sibling, int(params["index"]))
    body = fit(soaf_sample(), blen)
    if off + blen > len(plain):
        raise SoundError("record runs past the end of the bank body")
    out = plain[:off] + body + b"\x00" * (blen - len(body)) + plain[off + blen:]
    if len(out) != len(plain):
        raise SoundError("the bank body changed length")
    return out, 1


def _op_shotgun_snd_sh(plain, params):
    """Point the donor record at what was written: its new length, and the rate the sample was authored at."""
    o, rate, _ms, blen, _brate, _off = _sh_record(plain, int(params["index"]))
    body = fit(soaf_sample(), blen)
    ms = int(round(len(body) * 1000.0 / (SOAF_RATE * FRAME / 28.0)))
    out = bytearray(plain)
    struct.pack_into("<4I", out, o + 4, SOAF_RATE, ms, len(body), SOAF_RATE * FRAME // 28)
    return bytes(out), 1


def _register():
    from . import dataedit
    dataedit.OPS.setdefault("shotgun_snd_sb", _op_shotgun_snd_sb)
    dataedit.OPS.setdefault("shotgun_snd_sh", _op_shotgun_snd_sh)
    dataedit._WANTS_SIBLING.setdefault("shotgun_snd_sb", lambda path: path[:-3] + ".SH")


_register()


def data_edits(v: dict, prefix: str = "js_") -> list:
    if not (v.get(prefix + "shotgun") and v.get(prefix + "shotgun_sound")):
        return []
    from .model import FileEdit
    i = DONOR_INDEX[prefix]
    return [FileEdit("shotgun_snd_sb", r"/BNK_00_0\d\.SB$", "GR.IMG", {"index": i},
                     "the Sum of All Fears shotgun sample, into bank 0"),
            FileEdit("shotgun_snd_sh", r"/BNK_00_0\d\.SH$", "GR.IMG", {"index": i},
                     "bank 0's index points at the shotgun sample")]

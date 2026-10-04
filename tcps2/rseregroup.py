r"""The second regroup line, which ships on the disc and cannot be reached.

Every Rainbow operative records two clips for being told to regroup on the
leader -- a first one and a different one for being told again:

    Play_Price_TeamRegroup_OnLead        Play_Price_TeamRegroupOnLead2nd
    Play_Lois_TeamRegroup_OnLead         Play_Lois_TeamRegroupOnLead2nd
    Play_Weber_TeamRegroup_OnLead        Play_Weber_TeamRegroupOnLead2nd

`R6RainbowVoices` holds them in two properties, and this is where it goes
wrong -- the names do not say what they hold::

    m_sndReformOnLead   -> Play_*_TeamRegroup_OnLead      (the first time)
    m_sndRegroupOnLead  -> Play_*_TeamRegroupOnLead2nd    (said again)

read out of the class defaults at 0x1749BB / 0x174C54 / 0x174EEA, where each
entry is <name index><info byte 0x15, ObjectProperty><object ref>.

HOW IT FAILS
------------

`R6RainbowVoices.PlayRainbowVoices` is a `Switch` on an `ERainbowVoices` enum
with one case per event. Two consecutive cases are byte-for-byte identical
apart from their last argument::

    case 5   aPawn.native2730(m_sndReformOnLead, 8, 0)
    case 6   aPawn.native2730(m_sndReformOnLead, 8, 1)

That trailing 0/1 is the first-time / said-again flag, and it lines up exactly
with the pair of clips each operative recorded. So case 6 is the "he has told
you already" event -- and it plays the first-time clip, because the property
whose name begins "Reform" is the one holding the regroup line.

The result is that `m_sndRegroupOnLead` has no reader anywhere in the package
set. Measured: of the 131 sound properties across R6RainbowVoices,
R6TerroristVoices and R6HostageVoices, exactly two are never read, and this is
one of them. The other is R6TerroristVoices.m_sndGoesDown, which has no
duplicated case to borrow a trigger from and is left alone here.

THE EDIT
--------

Two bytes: case 6's operand becomes `m_sndRegroupOnLead` (export 7206) in
place of `m_sndReformOnLead` (export 2739). Both are two-byte compact indices
on disk and four bytes in memory, so the block's length cannot move and
nothing downstream shifts.

The run searched for is both cases together -- forty bytes including the
`Jump`, `Case` and `ByteConst(6)` between them -- because either case on its
own is not unique. Measured once in each of the three packages.
"""

from __future__ import annotations

H = bytes.fromhex


class RegroupError(Exception):
    pass


#: Every package: the teammates speak offline, in split screen and online.
SELECT = r"/COMMON(OFF|_SS)?\.LIN$"

#: key -> (stock, new, recorded offset)
#:
#: regroup_2nd -- PlayRainbowVoices case 5 | Jump, Case, ByteConst(6) |
#: case 6. The two cases differ only in their trailing first-time/repeat
#: flag; case 6's operand becomes m_sndRegroupOnLead (export 7206).
#:
#: terro_down -- PlayTerroristVoices case 0 | Jump, Case, ByteConst(1) |
#: case 1. These two are byte-for-byte identical, not even a differing
#: flag: both play m_sndWounded. CASE 0 is the broken one and it is case
#: 0 whose operand becomes m_sndGoesDown (export 7313).
#:
#: WHICH CASE IS WHICH was got wrong once, so here is the proof. The
#: retail Xbox disc ships uncompiled UnrealScript, and R6TerroristVoices
#: there reads:
#:
#:     case TV_GoesDown:  aPawn.PlayVoices(m_sndWounded,  ... SendToAll);
#:     case TV_Wounded:   aPawn.PlayVoices(m_sndWounded,  ... SendToAll);
#:
#: so the FIRST case is TV_GoesDown and it is the one playing the wrong
#: clip. That the PS2 switch is the same switch is settled by the
#: argument counts, which are a fingerprint: 4,4,3,3,3,3,4,3,3,3,3,3,3,5
#: across the fourteen shared cases, matching the Xbox source exactly.
#: The PS2 build adds TV_GrabHostage1-3 at 14-16 and declares its sound
#: properties in a different order, so the property NAMES cannot be used
#: to identify a case -- only the position and the argument count can.
#:
#: m_sndGoesDown's reference number puts it far outside the block
#: 2746/2778-2792 that the sixteen working terrorist lines occupy -- it
#: was appended to the class later and never wired, exactly as
#: m_sndRegroupOnLead (7206) was.
REGIONS = {
    "regroup_2nd": (
        H("19001c0c00006aaa01732a2408240016"
          "06c00b0ad2002406"
          "19001c0c00006aaa01732a2408240116"),
        H("19001c0c00006aaa01732a2408240016"
          "06c00b0ad2002406"
          "19001c0c00006aaa016670240824 0116".replace(" ", "")),
        0x1736E3),
    "terro_down": (
        H("190077020e00006aaa017a2a240624012402 16".replace(" ", "")
          + "060b020a50002401"
          + "190077020e00006aaa017a2a2406240124 0216".replace(" ", "")),
        H("190077020e00006aaa0151722406240124 0216".replace(" ", "")
          + "060b020a50002401"
          + "190077020e00006aaa017a2a2406240124 0216".replace(" ", "")),
        0x171D53),
}


def _site(plain: bytes, which: str):
    row = REGIONS.get(which)
    if not row:
        raise RegroupError("unknown voice region %r" % which)
    _STOCK, _NEW, _at = row
    if len(_STOCK) != len(_NEW):
        raise RegroupError("the replacement is a different length")
    hits = []
    for form, state in ((_STOCK, "stock"), (_NEW, "new")):
        at = plain.find(form)
        if at >= 0 and plain.find(form, at + 1) >= 0:
            raise RegroupError("the regroup cases were found more than once")
        if at >= 0:
            hits.append((at, state))
    if len(hits) != 1:
        raise RegroupError(
            "%s: %s" % (which,
                        "not found" if not hits else "both forms present"))
    return hits[0]


def reads(plain: bytes, which: str) -> bool:
    """True if that line is wired up."""
    try:
        return _site(plain, which)[1] == "new"
    except RegroupError:
        return False


def apply(plain: bytes, which: str, enable: bool = True):
    want_new = bool(enable)
    if reads(plain, which) == want_new:
        return plain, 0
    stock, new, _at = REGIONS[which]
    at, _state = _site(plain, which)
    want = new if want_new else stock
    out = bytearray(plain)
    out[at:at + len(stock)] = want
    if len(out) != len(plain):
        raise RegroupError("a voice edit changed the file length")
    return bytes(out), 1


def cards(prefix, team_group, enemy_group):
    """One card per line that ships unreachable."""
    from .model import BOOL, Setting

    return [
        Setting(
            prefix + "regroup_2nd",
            "Teammates have a second regroup line", BOOL, False,
            team_group,
            confidence="experimental", touches="data",
            help="Every operative recorded two lines for being told to regroup "
                 "on you -- one for the first time and a different one for "
                 "being told again -- and the second has never been "
                 "reachable.\n\n"
                 "The game raises both events, but both of them play the "
                 "first-time clip, so the said-again recording is read by "
                 "nothing anywhere in the game. This points the said-again "
                 "event at the said-again clip. Nothing is authored and "
                 "the first regroup order sounds exactly as it does now.",
            caution="Not yet played. Read out of the class defaults rather "
                    "than inferred from the names, which matters because "
                    "the names mislead: the property called "
                    "m_sndReformOnLead is the one holding the regroup "
                    "clip, and that is almost certainly how the mistake "
                    "was shipped.\n\n"
                    "What is not proven is how often the game raises the "
                    "said-again event, so you may have to give the order "
                    "twice to hear it."),
        Setting(
            prefix + "terro_down",
            "Enemies have their own line for going down", BOOL, False,
            enemy_group, confidence="experimental", touches="data",
            help="Terrorists recorded a line for being put down and a "
                 "separate one for being wounded. The game raises both "
                 "events -- and both of them play the wounded clip.\n\n"
                 "The two cases that handle them are byte-for-byte "
                 "identical, not even a differing argument, which is what "
                 "gives the mistake away. This points the going-down one "
                 "at the clip recorded for it.",
            caution="Not yet played. The clip is real and sits in the same "
                    "class as the sixteen that do play, but its reference "
                    "number puts it far outside the block they occupy, so "
                    "it was added to the class after the dispatch was "
                    "written and never wired up.\n\n"
                    "What the line actually says was not checked -- the "
                    "enemies speak Spanish and Arabic."),
    ]

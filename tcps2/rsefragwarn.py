"""Giving the frag warning back its own voice line.

The defect
----------

Every grenade a teammate throws has two lines: the one he says as he throws
it, and the one that warns you it is coming. Flash, gas, smoke and phosphorus
all have both, wired to two different objects::

    m_sndThrowFlash      -> Play_<x>_FlashThrow      "flashbang out"
    m_sndDingThrowFlash  -> Play_<x>_FlashThrown     the warning

Frag has both recorded, and both slots point at the SAME object::

    m_sndThrowFrag       -> Play_<x>_FragThrow
    m_sndDingThrowFrag   -> Play_<x>_FragThrow       <-- the slip

So voice action 95 says the throw line instead of the warning, and
`Play_<x>_FragThrown` -- which is in every operative's voice package, in two
takes each -- can never play. Measured on the pristine disc for all three
operatives.

Why this needs the package to grow
----------------------------------

The obvious fix is to repoint the three `m_sndDingThrowFrag` values, and that
is a two-byte change each. But there is nothing to point AT: `FragThrown` is
absent from the gameplay package's name table and from its import table, in
every operative. Flash/Gas/Smoke/Phosphore all have imports; Frag does not.

So the edit has to ADD three names and three imports, which makes the package
longer. That used to be forbidden. It is not: the packages sit back-to-back
with no recorded offsets and the loader walks them, proven by inserting bytes
mid-package and watching a level load and play. See `lin.rebuild`.

What it does NOT change
-----------------------

Appending leaves every existing index alone -- names and imports are
referenced by position, and nothing already in the file points past the old
end -- so no other reference in the package has to be rewritten.
"""

from __future__ import annotations

import struct

from .model import BOOL, Setting
from .upackage import compact_index, encode_compact

MAGIC = 0x9E2A83C1

#: the operative prefixes, in the spelling the voice packages use
OPERATIVES = ("Price", "Lois", "Weber")

#: the slot that is wrong, and the slot that shows what it should look like
WRONG = "m_sndDingThrowFrag"
PATTERN = "m_sndDingThrowFlash"

#: UE2 property type for an object reference
T_OBJECT = 5


class FragWarnError(Exception):
    pass


def _package(plain):
    """(base, names, endOfNames, endOfImports, nNames, nImports) for R6Game."""
    at = plain.find(struct.pack("<I", MAGIC))
    while at >= 0:
        try:
            (magic, _ver, _lic, _flags, n_names, o_names,
             n_exports, _o_exports, n_imports,
             _o_imports) = struct.unpack_from("<IHHIIIIIII", plain, at)
            names, pos = [], at + o_names
            for _ in range(n_names):
                ln, pos = compact_index(plain, pos)
                names.append(plain[pos:pos + ln - 1].decode("latin-1"))
                pos += ln + 4
            end_names = pos
            for _ in range(n_imports):
                for _f in range(2):
                    _v, pos = compact_index(plain, pos)
                pos += 4
                _v, pos = compact_index(plain, pos)
            end_imports = pos
        except Exception:                                        # noqa: BLE001
            at = plain.find(struct.pack("<I", MAGIC), at + 1)
            continue
        if WRONG in names:
            return (at, names, end_names, end_imports, n_names, n_imports)
        at = plain.find(struct.pack("<I", MAGIC), at + 1)
    raise FragWarnError("no package in this file owns %s" % WRONG)


def _import_records(plain, base, start, count):
    """[(offset, length, nameIndex)] for every import, in order."""
    out, pos = [], start
    for _ in range(count):
        first = pos
        for _f in range(2):
            _v, pos = compact_index(plain, pos)
        pos += 4
        nm, pos = compact_index(plain, pos)
        out.append((first, pos - first, nm))
    return out


def already(plain) -> bool:
    _b, names, _n, _i, _nn, _ni = _package(plain)
    return ("Play_%s_FragThrown" % OPERATIVES[0]) in names


def apply(plain: bytes, enable: bool = True):
    """Point each operative's frag-warning slot at its own recorded line."""
    if not enable:
        return plain, 0
    base, names, end_names, end_imports, n_names, n_imports = _package(plain)
    wanted = ["Play_%s_FragThrown" % who for who in OPERATIVES]
    if all(w in names for w in wanted):
        return plain, 0

    # Clone an import that already names a Sound in the same voice packages,
    # so the class and outer references are right by construction rather than
    # by guesswork. One per operative, because each lives in its own package.
    donors = {}
    records = _import_records(plain, base, end_names, n_imports)
    for who in OPERATIVES:
        target = "Play_%s_FragThrow" % who
        if target not in names:
            raise FragWarnError("%s is not in the name table" % target)
        idx = names.index(target)
        hit = [r for r in records if r[2] == idx]
        if not hit:
            raise FragWarnError("no import names %s" % target)
        donors[who] = hit[0]

    out = bytearray(plain)
    name_flags = bytes(out[end_names - 4:end_names])

    # 1. the three names, appended so every existing index is untouched
    blob = bytearray()
    for who in OPERATIVES:
        s = ("Play_%s_FragThrown" % who).encode("latin-1")
        blob += encode_compact(len(s) + 1) + s + b"\0" + name_flags
    out[end_names:end_names] = blob
    shift = len(blob)

    # 2. the three imports, cloned from the throw line and renamed
    new_imports = bytearray()
    for n, who in enumerate(OPERATIVES):
        off, length, _nm = donors[who]
        # Read the donor out of the UNSHIFTED input. Its offset was measured
        # before the names were inserted, and the import table sits after the
        # name table, so reading it from `out` would be off by `shift`.
        rec = bytearray(plain[off:off + length])
        # rebuild the record: two class indices, the 4-byte outer, then the
        # name -- only the name changes, and its width may differ
        p = 0
        _cp, p = compact_index(rec, p)
        _cn, p = compact_index(rec, p)
        p += 4
        head = bytes(rec[:p])
        new_imports += head + encode_compact(n_names + n)
    out[end_imports + shift:end_imports + shift] = new_imports

    # 3. the counts
    struct.pack_into("<I", out, base + 12, n_names + len(OPERATIVES))
    struct.pack_into("<I", out, base + 28, n_imports + len(OPERATIVES))

    # 4. repoint each operative's wrong slot at its new import.
    #    `swap` maps the import index the slot points at NOW (the throw line,
    #    one per operative) to the index of the warning line just appended.
    swap = {}
    for n, who in enumerate(OPERATIVES):
        old = records.index(donors[who])
        swap[old] = n_imports + n
    done = _repoint(out, names, swap)
    if done != len(OPERATIVES):
        raise FragWarnError("expected to repoint %d slots, moved %d"
                            % (len(OPERATIVES), done))
    return bytes(out), done


def _repoint(out, names, swap):
    """Swap m_sndDingThrowFrag from the throw line to the warning line.

    Only the slots that currently point at one of the three throw lines are
    touched, so running this on a disc that already carries the edit, or on
    one where a slot points somewhere unexpected, changes nothing rather than
    guessing.
    """
    needle = encode_compact(names.index(WRONG))
    done, at = 0, out.find(needle)
    while at >= 0:
        info = out[at + len(needle)]
        if (info & 0x0F) == T_OBJECT and (info >> 4) & 7 == 1:
            val = at + len(needle) + 1
            ref, end = compact_index(bytes(out), val)
            old = -ref - 1
            if ref < 0 and old in swap:
                new = encode_compact(-(swap[old]) - 1)
                if len(new) == end - val:
                    out[val:end] = new
                    done += 1
        at = out.find(needle, at + 1)
    return done


def cards(prefix: str, group: str) -> list:
    return [
        Setting(prefix + "frag_warning", "Teammates warn you about their frag",
                BOOL, False, group,
                help="Every other grenade has two lines -- one as it is thrown, "
                     "one warning you it is coming -- but both of frag's slots "
                     "point at the throw line, so the warning never plays. The "
                     "recording is on the disc, two takes for each operative. "
                     "This points the warning slot at it.",
                caution="Not play-tested. This is the first edit that makes a "
                        "cooked package LONGER, which was believed impossible "
                        "until it was measured; the container still fits its "
                        "slot because re-deflating beats the disc's packer.",
                confidence="applied", touches="data"),
    ]

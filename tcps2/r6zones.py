"""Rainbow Six 3's authored spawner counts, per level.

Every wave setting the tool ships today is a global code patch -- one
instruction replaced, which sets the value for every zone in the game at once.
These are the other half: the counts the designers authored into each level,
which can be changed for one mission without touching any other.

Per-map needs nothing cleverer than this, because per-map means per `.LIN` and
each mission part is already its own file.

## Finding them

`upackage` reads the level's cooked packages. A count is then found by its own
name index followed by an int property's info byte -- see that module for why
the export table cannot be used to locate object data.

Two filters, in this order, and the order is the point:

1. The candidate's property list must walk cleanly to its terminator.
2. `m_TerroristAITag` must appear among the properties that follow it.

Measured over the 27 campaign parts: 498 candidates, of which the structural
filter keeps 458 and drops 40. **Every implausible value is in the 40.** The
458 it keeps run 0..15 -- real squad sizes -- so no numeric bound is needed,
and adding one would be a mistake: 148 of the 458 are a legitimate `0`, and
zero appears nowhere else in the distribution.

## Zero means "not a group"

The sites holding `0` sit beside `m_bDontHearPlayer`, `m_bNotSurrender` and
`m_aActionSpot` -- individual terrorists rather than group spawners. They are
left alone by `scale`: multiplying zero achieves nothing and writing a count
onto a single pawn is not what the caller asked for.
"""

from __future__ import annotations

import struct

from . import upackage

#: the two authored counts on a spawner
COUNT_PROPS = ("m_iMinTerrorist", "m_iMaxTerrorist")

#: a real spawner names the AI it spawns; a false positive does not
SPAWNER_MARK = "m_TerroristAITag"

#: no authored count on the disc exceeds this, so anything past it is a misread
SANE_MAX = 32


def sites(data):
    """Every authored count in a decompressed level.

    [(offset, prop, value)] with the offset pointing at the four value bytes,
    so a caller can rewrite one without disturbing its neighbours.
    """
    out = []
    for base, _pkg in upackage.packages(data):
        try:
            names, _imports, _exports = upackage.tables(data, base)
        except (upackage.PackageError, IndexError, UnicodeDecodeError):
            continue
        if not any(p in names for p in COUNT_PROPS):
            continue
        for prop in COUNT_PROPS:
            for at, val, following in upackage.actor_properties(data, names, prop):
                if SPAWNER_MARK in following:
                    out.append((at, prop, val))
    return sorted(set(out))


def wave_zones(data):
    """How many `R6DZoneWave` actors the level places, by class not by guess."""
    total = 0
    for base, _pkg in upackage.packages(data):
        try:
            _n, _i, exports = upackage.tables(data, base)
        except (upackage.PackageError, IndexError, UnicodeDecodeError):
            continue
        total += sum(1 for cls, _nm, _s, _o in exports if cls == "R6DZoneWave")
    return total


def scale(data, factor, lo=1, hi=32):
    """Multiply every authored count in this level. Returns (bytes, changed).

    Length is preserved exactly -- an int32 stays an int32 -- which is what
    `lin.substitute` requires. Counts of zero are left alone; see the note
    above on what they are.
    """
    if factor == 1.0:
        return data, 0
    out = bytearray(data)
    changed = 0
    for at, _prop, val in sites(data):
        if val <= 0 or val > SANE_MAX:
            continue
        new = max(lo, min(hi, int(round(val * factor))))
        if new != val:
            struct.pack_into("<i", out, at, new)
            changed += 1
    return bytes(out), changed

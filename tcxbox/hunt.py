"""Terrorist-hunt spawn counts, inside the cooked level packages.

Rainbow Six 3 and Black Arrow both ship the terrorist WAVE system the PS2 disc
has -- `R6DZoneWave`, `R6DeploymentZone`, `R6DZoneRandomPoints` and the rest --
and their levels place it: 31 of Rainbow Six 3's 41 level packages and 23 of
Black Arrow's 42 carry deployment-zone actors. None of it is reachable from any
ini. The numbers live inside the `.LIN` level packages, which is why this file
exists.

**How the counts are laid out.** Two different actors serialise the same two
properties and telling them apart is the whole job:

  * a site whose neighbourhood contains `m_pWave`, carrying `m_eTerroristHunt`
    and `m_eCoopTerroristHunt`, is a DEPLOYMENT ZONE -- what Terrorist Hunt
    spawns from, and what a wave draws from;
  * a site near `m_pZone`, carrying `m_eStoryMode` and `m_eCoopStoryMode`, is a
    story-mode spawn group. Scaling those would rewrite the campaign's order of
    battle, which is a different option that nobody asked for.

Only the first kind is touched.

**Most zones do not serialise a count at all.** UnrealScript writes a property
only when it differs from the class default, so the disc's own numbers are
sparse: Rainbow Six 3's fourteen campaign levels carry 112 hunt terrorists in
explicit overrides, and Parade, Penthouse and Shipyard place deployment zones
with no counts on them whatsoever. Those fall back to the class default in
`COMMON.LIN`, which is **1 and 1** for a deployment zone and **4 and 4** for the
wave. That default is therefore the more powerful of the two dials, and both are
scaled together here so a single choice means one thing everywhere.

**Why this can be written at all.** A `.LIN` is a chain of
`u32 rawSize, u32 compressedSize, deflate stream`, and `lin.substitute`
re-deflates only the chunks whose plain bytes actually changed, padding each
back to its original compressed size. The container's length never moves, and
neither does any package offset inside it -- which matters because the cooker
relaid those offsets and the loader trusts them.
"""

from __future__ import annotations

import struct

from . import lin, upackage

#: The properties that carry a spawn count.
COUNTS = ("m_iMinTerrorist", "m_iMaxTerrorist")

#: Names looked for around a site to decide what kind of actor it belongs to.
NEAR = ("m_pWave", "m_pZone", "m_bTriggerWhenLastTerroristDies",
        "m_bSpawnedByWave", "m_aSpawningPoints")

#: Siblings that mark a CLASS DEFAULT object in `COMMON.LIN` rather than a
#: placed actor. The deployment zone's default lists the per-mode enable enums
#: right after its counts; the wave's default carries only its editor sprite.
#: `Texture` is safe as a marker precisely because it is only ever reached
#: through a site that already carries `m_iMinTerrorist` -- and the only
#: classes that have one of those are the zones.
DEFAULT_SIBS = ("m_bAllowLeave", "m_bIsTargetable", "Texture")

#: A spawn count outside this is not a spawn count. `actor_properties` already
#: refuses anything whose property list does not walk to a terminator, and that
#: still let one 1,761,740,121 through on Mountain Highway -- four bytes of
#: geometry that happened to sit behind the right name index.
SANE = (0, 400)

#: What the counts are clamped to after scaling. The engine's own biggest
#: shipped zone is twelve; a hundred is far past anything the AI budget was
#: built for and is the point past which this stops being a number worth
#: writing.
CEILING = 100


class HuntError(Exception):
    pass


def _sites(plain: bytes):
    """[(valueOffset, value)] for every hunt spawn count in a decompressed LIN.

    Both the placed deployment zones and the class default qualify; story-mode
    spawn groups do not.
    """
    out = []
    for _off, pkg in upackage.packages(plain):
        try:
            names = pkg.names()
        except Exception:                                     # noqa: BLE001
            continue
        if not any(c in names for c in COUNTS):
            continue
        for prop in COUNTS:
            for at, val, sibs in upackage.actor_properties(plain, names, prop):
                if not SANE[0] <= val <= SANE[1]:
                    continue
                near = upackage.neighbours(plain, at, names, NEAR)
                if "m_pZone" in near and "m_pWave" not in near:
                    continue                    # story-mode spawn group
                is_zone = "m_pWave" in near
                is_default = any(s in sibs for s in DEFAULT_SIBS)
                if is_zone or is_default:
                    out.append((at, val))
    return out


def census(container: bytes):
    """(zones, total) for a `.LIN`, without changing anything."""
    if not lin.is_lin(container):
        return 0, 0
    sites = _sites(lin.decompress(container))
    return len(sites), sum(v for _at, v in sites)


def scale(container: bytes, factor: float):
    """Multiply every hunt spawn count in a `.LIN`. Returns (bytes, changed).

    A zone that ships zero stays zero: zero means "this zone contributes
    nobody", and multiplying it would still be nobody, so the only thing a
    factor could do there is nothing. Saying so is cheaper than leaving a
    reader to work out why the totals do not scale cleanly.
    """
    if not lin.is_lin(container):
        return container, 0
    moved = [0]

    def edit(plain: bytes) -> bytes:
        buf = bytearray(plain)
        for at, val in _sites(plain):
            if val <= 0:
                continue
            new = max(1, min(CEILING, int(round(val * factor))))
            if new == val:
                continue
            struct.pack_into("<i", buf, at, new)
            moved[0] += 1
        return bytes(buf)

    try:
        out, _touched = lin.substitute(container, edit)
    except lin.LinError as exc:
        raise HuntError(str(exc)) from exc
    return out, moved[0]

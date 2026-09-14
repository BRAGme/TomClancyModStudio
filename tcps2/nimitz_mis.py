"""Rainbow Six Lockdown's `.MIS` mission scripts, far enough to read the
Terrorist Hunt setup.

Every playable slice of the game is a `.MIS`: `M01_SEC_01.MIS` for the
campaign, plus `_COOP`, `_TH_NOR` and `_TH_REV` beside it. They are a flat
stream of length-prefixed ASCII (u32 length, then the bytes) with binary
between, so the readable parts can be walked without decoding the rest.

## Characters

A character is defined by a **template**: a group name followed immediately by
three filenames --

    "Generic Enemies"  e_samerc_random_m01.cms  terrorist_basic.cgs
                       e_south_african_mercs.wsf

the model, the AI profile (the same `.cgs` names `NIMITZ.CGSB` defines) and the
weapon loadout. Each **placement** of that character then repeats the group
name alone in a fixed 111-byte record carrying two 3D points -- a position and
what looks like a facing or patrol target. On M01's hunt map every placement
shares a z of -32.0, which is simply one floor.

So the enemy count of a map is the number of records repeating a template's
group name, less the template itself. Counting the literal string "Generic
Enemies" is not enough: about a third of the maps name their groups something
else, and doing it that way reports those as empty.

## What this does and does not allow

Reading is reliable -- the census below is reproduced by `hunt_census` and
checked in the tests.

**Counts cannot be edited through this.** Placements are fixed-size records in
a file whose position inside `PS2DATA.PAK` is fixed, so adding one grows the
file into its neighbour. Removing one would shrink it, which needs the index
size rewritten and a child-count field somewhere in the group header that has
not been located. Neither is done, so nothing here writes.

**Per-map difficulty is still reachable**, just from the other end: the maps do
not all draw on the same profile. M13's hunt uses `mercenary-03`, M16's uses
`merc_basic`, M12/M14/M15 mix two or three, and the rest use
`terrorist_basic`. Scoping a `NIMITZ.CGSB` skill edit to one of those profiles
therefore retunes the maps that use it and leaves the others alone -- which is
what `transforms.bump_nimitz_skills(only=...)` already does.
"""

from __future__ import annotations

import re
import struct

#: the campaign characters, so an enemy census does not count the player's team
RAINBOW = ("chavez", "loiselle", "raymond", "yacoby", "price", "mcallen",
           "murad", "weber", "lofquist", "pak_", "arnavisca", "hanely",
           "filatov", "medina_r")

_CMS = re.compile(rb"([a-z0-9_\-]+\.cms)")
_ASSET = re.compile(rb"[a-z0-9_\-]+\.(?:cgs|wsf)")


def _lp_at(data, end):
    """The length-prefixed string ending at `end`, or None."""
    start = end
    while start > 4 and 32 <= data[start - 1] < 127:
        start -= 1
    if start < 4:
        return None
    declared = struct.unpack_from("<I", data, start - 4)[0]
    if declared != end - start or not declared:
        return None
    return data[start:end].decode("latin-1")


def templates(data):
    """[(group, model, profile, loadout)] for every character in the mission."""
    out = []
    for m in _CMS.finditer(data):
        head = m.start() - 4
        if head < 0 or struct.unpack_from("<I", data, head)[0] != len(m.group(1)):
            continue
        group = _lp_at(data, head)
        if not group:
            continue
        assets = [a.decode() for a in _ASSET.findall(data[m.end():m.end() + 160])]
        profile = next((a for a in assets if a.endswith(".cgs")), "")
        loadout = next((a for a in assets if a.endswith(".wsf")), "")
        out.append((group, m.group(1).decode(), profile, loadout))
    return out


def placements(data, group):
    """How many times `group` is placed, not counting its template."""
    key = struct.pack("<I", len(group)) + group.encode("latin-1")
    return max(0, data.count(key) - 1)


def enemies(data):
    """(count, sorted profiles) of the hostiles this mission places."""
    total, profiles = 0, set()
    for group, _model, profile, _loadout in templates(data):
        if any(r in profile for r in RAINBOW):
            continue
        n = placements(data, group)
        if n:
            total += n
            if profile:
                profiles.add(profile)
    return total, sorted(profiles)


MISSION_RE = re.compile(
    r"^/PS2DATA/MISSION/(M\d\d)_SEC_(\d\d)(?:_SMG)?_(TH_NOR|TH_REV)\.MIS$", re.I)


def hunt_census(pak):
    """[(mission, section, direction, enemyCount, profiles)] for every hunt map."""
    out = []
    for name in sorted(pak.files):
        m = MISSION_RE.match(name)
        if not m:
            continue
        count, profiles = enemies(pak.read_entry(pak.files[name]))
        out.append((m.group(1).upper(), m.group(2), m.group(3).upper(),
                    count, profiles))
    return out

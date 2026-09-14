"""Unreal `.int` localisation files, as the Rainbow Six 3 engine discs ship them.

Three of the seven discs keep their menu text in Unreal's plain `Key=Value`
localisation format -- `[Section]` headers, one key per line. Ghost Recon 2 and
Advanced Warfighter write theirs as UTF-16 with a byte-order mark; Rainbow Six 3
writes some as plain bytes. Both are handled here so callers do not have to
care.

What this is *for* is the mission tables. Advanced Warfighter's
`PREGAMEMENUS.INT` carries the mission-selection screen's own list --
`[MissionName]` for what the player reads and `[MissionNameIntel]` for the
level each entry loads -- and Ghost Recon 2's `R6MENUS.INT` carries a date,
time and weather line per mission plus its objectives. Those are the discs
stating their own mission order, which beats inferring one.

Values are returned exactly as they appear apart from surrounding whitespace:
no escape processing, because none of the keys this reads use any.
"""

from __future__ import annotations

import re

_SECTION = re.compile(r"^\[([^\]\r\n]+)\]\s*$")


def text(data):
    """The file as a string, whichever way the disc encoded it."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    return data.decode("latin-1")


def sections(data):
    """{section: {key: value}} -- later keys win, as Unreal itself resolves them.

    Lines before the first header land under the empty-string section, which is
    where Rainbow Six 3's flatter files keep everything.
    """
    out, here = {}, {}
    out[""] = here
    for line in text(data).splitlines():
        head = _SECTION.match(line.strip())
        if head:
            here = out.setdefault(head.group(1), {})
            continue
        key, sep, value = line.partition("=")
        if sep and key.strip():
            here[key.strip()] = value.strip()
    return out


def numbered(section, prefix="Mission"):
    """[value] from a `Mission1=`, `Mission2=` ... block, in numeric order.

    The game writes these in order but nothing guarantees it, and a gap would
    silently shorten the list, so the run is required to be 1..n with nothing
    missing -- otherwise this raises rather than returning a short table.
    """
    found = {}
    for key, value in section.items():
        m = re.fullmatch(re.escape(prefix) + r"(\d+)", key)
        if m:
            found[int(m.group(1))] = value
    if not found:
        return []
    if sorted(found) != list(range(1, len(found) + 1)):
        raise ValueError("%s keys are not 1..%d: %s"
                         % (prefix, len(found), sorted(found)))
    return [found[i] for i in range(1, len(found) + 1)]

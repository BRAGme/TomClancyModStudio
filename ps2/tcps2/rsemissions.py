"""What Ghost Recon and Jungle Storm say about their own missions.

Both discs answer the two questions a mission page needs, in plain XML inside
`GR.IMG`, so neither the order nor the names have to be inferred:

* **`CAMPAIGN.XML`** lists the campaign in play order, one `<Filename>` per
  mission. On Ghost Recon that is the file order too -- `m01` through `m15`,
  then the eight Desert Siege missions. On Jungle Storm it is emphatically
  **not**: the Colombia campaign is assembled out of the `G0x` and `U0x` files
  in a scrambled order, so `J01` is `g03_the_rock.mis` and `J03` is
  `u05_rail.mis`. Sorting those filenames would put the campaign in the wrong
  sequence entirely.

* **The `.MIS` file's own `<Shell>` and `<Engine>` blocks** carry `<Name>`
  (the codename, "M01 - Iron Dragon"), `<MapName>`, `<LocationText>`,
  `<DateText>` and `<TimeText>`. The `<Name>` numbering agrees with
  `CAMPAIGN.XML`'s order independently, and on both discs the dates climb, so
  three separate things say the same thing about the sequence.

Nothing here writes. The per-mission edits go through `dataedit` like every
other data change, and `transforms.count_actors` does the census.
"""

from __future__ import annotations

import re

from . import rselzo, transforms, vokes

CAMPAIGN = "/CAMPAIGN.XML"

_FILENAME = re.compile(r"<Filename>([^<]*)</Filename>", re.I)


def _tag(data, name):
    m = re.search(("<%s>([^<]*)</%s>" % (name, name)).encode(), data)
    return m.group(1).decode("latin-1").strip() if m else ""


def _plain(arc, entry):
    raw = arc.read_entry(entry)
    return rselzo.decompress(raw) if rselzo.is_compressed(raw) else raw


def archive_files(iso, profile):
    """{UPPERCASE path: (archive, entry)} across the disc's archives."""
    out = {}
    for arc in vokes.open_archives(iso, profile.archive_pattern):
        for name, entry in arc.files.items():
            out.setdefault(name.upper(), (arc, entry))
    return out


def campaign_order(files):
    """The campaign's mission stems, in the order the disc plays them."""
    if CAMPAIGN not in files:
        return []
    text = _plain(*files[CAMPAIGN]).decode("latin-1")
    return [f.upper().rsplit(".", 1)[0] for f in _FILENAME.findall(text)]


def mission_facts(files, stem):
    """What one `.MIS` says about itself, plus its order of battle.

    Returns a dict, or None when the disc has no such mission.
    """
    key = "/%s.MIS" % stem.upper()
    if key not in files:
        return None
    data = _plain(*files[key])
    total, easy, normal, hard = transforms.count_actors(data)
    return {
        "stem": stem.upper(),
        "name": _tag(data, "Name"),
        "map": _tag(data, "MapName"),
        "place": _tag(data, "LocationText"),
        "date": _tag(data, "DateText"),
        "time": _tag(data, "TimeText"),
        "actors": total,
        "easy_held": easy,
        "flags": easy + normal + hard,
    }


_NUMBER = re.compile(r"^([A-Z]{1,4}\d+)\b[\s-]*", re.I)


def codename(name):
    """"M01 - Iron Dragon" -> ("M01", "Iron Dragon").

    Ghost Recon and Jungle Storm separate the two with " - ". The Sum of All
    Fears does not -- it writes "M01 Hostage Rescue Operation" for its campaign
    and "T01 - Movement" for its training, in the same file set -- so the split
    is on the leading mission number rather than on the dash.
    """
    m = _NUMBER.match(name.strip())
    if not m:
        return name.strip(), ""
    return m.group(1).upper(), name.strip()[m.end():].strip()

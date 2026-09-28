"""Red Storm `.GUN` files -- the weapon model, and whose weapon it is.

Ghost Recon, Jungle Storm and The Sum of All Fears each ship their weapons as
plain XML, one file per gun, and the file is the whole model:

    <MagazineCapacity>30</MagazineCapacity>
    <MaxRange>475.000000</MaxRange>
    <Selective><SelectiveOption RateOfFire = "700" IsFullAuto = "1" .../></Selective>
    <Recoil>50</Recoil>
    <RunStandAccuracy>500</RunStandAccuracy>   ... twelve of these ...
    <StationaryProneAccuracy>5</StationaryProneAccuracy>

Accuracy is a cone, so **lower is better**: a scale above 1.0 makes a weapon
less accurate, not more. That is the one place this reads backwards from every
other dial in the tool, and the cards say so.

## Whose gun is it

The discs answer this themselves. A mission's `<Actor>` carries a `Kit`
attribute, a `.KIT` names the `.gun` it holds, and `<Company Allied="1">` is
the player's side -- the same allied/hostile split the enemy-template scope
already uses.

    enemy gun  := some non-allied company hands out a kit that names it
    your gun   := any other kit names it

Two wrinkles, both measured rather than assumed. The Sum of All Fears ships
`MULTI_08_NOGREN.KIT` and `MULTI_08_PRIMARY.KIT` beside the `MULTI_08.KIT` its
missions name -- the same enemy kit with the grenades or the sidearm taken out
-- so a kit inherits the side of its base name. And some weapons genuinely
appear on both sides: seven in Ghost Recon, nine in Jungle Storm, more in The
Sum of All Fears, where Rainbow and the terrorists both carry an MP5. One file
cannot be two weapons, so a gun on both lists is left alone by both dials and
the card names the count.

## Editing without moving a byte

`.GUN` files are inside the chunked compressor, so an edit has to preserve the
file's length exactly. Every value is rewritten into the **same character
width** it already occupied, left-padded with zeros -- `50` becomes `05` going
down and can reach `99` going up -- and floats give up decimal places before
they give up digits. A value that cannot be represented in its own width is
left alone and counted, so a caller can say how many were skipped rather than
silently clamping.
"""

from __future__ import annotations

import re

from . import rselzo, transforms

#: the twelve stance accuracies, in the order the file lists them
ACCURACY = tuple(
    "%s%sAccuracy" % (move, stance)
    for move in ("Run", "Walk", "Shuffle", "Stationary")
    for stance in ("Stand", "Crouch", "Prone"))

#: what each dial reaches. Accuracy is a cone: bigger is worse.
FIELDS = {
    "magazine": ("MagazineCapacity",),
    "range": ("MaxRange",),
    "recoil": ("Recoil",),
    "accuracy": ACCURACY,
}

_KIT = re.compile(rb'Kit\s*=\s*"([^"]+)"')
_ITEM = re.compile(rb"<ItemFileName>([^<]*)</ItemFileName>")
#: the same kit with its grenades or its sidearm taken out -- still that kit
_VARIANT = re.compile(r"^(.*?)(?:_NOGREN|_PRIMARY|_NOGRENADE)$", re.I)
#: the loadout screen's own kits: RIFLEMAN-01, ASTRA_GALINSKY-04, HRT_SNIPER-02
_NUMBERED = re.compile(r"^.+-\d+$")


def _plain(arc, entry):
    raw = arc.read_entry(entry)
    return rselzo.decompress(raw) if rselzo.is_compressed(raw) else raw


def _base_kit(name):
    m = _VARIANT.match(name)
    return m.group(1) if m else name


def _kit_family(files, seeds, enemy):
    """Grow the player's kit set outwards from the ones a mission gave them.

    The Sum of All Fears names its loadouts by role rather than by number --
    CQB_ASSAULT, HRT_SNIPER, FIELD_SNIPER, MILITARY_BREACH -- so the numbered
    rule finds almost none of them. But its missions do hand three of those to
    an allied company, and the rest share a word with one of the three. So the
    set is grown by shared word until it stops growing.

    Only alphabetic words of three letters or more count, and a word that also
    appears in an enemy kit's name is never allowed to pull anything in, which
    is what keeps `M9_ONLY` from dragging every other `_ONLY` kit across.
    """
    stems = [k[1:].rsplit(".", 1)[0] for k in files if k.endswith(".KIT")]
    words = {s: {w for w in re.split(r"[^A-Za-z]+", s) if len(w) >= 3}
             for s in stems}
    banned = set()
    for stem in stems:
        if _base_kit(stem) in enemy:
            banned |= words[stem]

    grown = {s for s in stems if s in seeds}
    while True:
        pool = set()
        for stem in grown:
            pool |= words[stem] - banned
        more = {s for s in stems
                if s not in grown and _base_kit(s) not in enemy
                and words[s] & pool}
        if not more:
            return {_base_kit(s) for s in grown}
        grown |= more


def sides(files):
    """(yours, theirs, shared) as sets of lower-case `.gun` filenames.

    `files` is {UPPERCASE archive path: (archive, entry)}, which is what
    `rsemissions.archive_files` already builds.
    """
    enemy_kits, ally_kits = set(), set()
    for key, (arc, entry) in files.items():
        if not key.endswith(".MIS"):
            continue
        data = _plain(arc, entry)
        for company in transforms.COMPANY_RX.finditer(data):
            side = (ally_kits if transforms.ALLIED_RX.search(company.group(1))
                    else enemy_kits)
            for kit in _KIT.findall(company.group(2)):
                side.add(_base_kit(kit.decode("latin-1").upper()
                                   .rsplit(".", 1)[0]))
    ally_kits -= enemy_kits
    ally_kits |= _kit_family(files, ally_kits, enemy_kits)

    yours, theirs = set(), set()
    for key, (arc, entry) in files.items():
        if not key.endswith(".KIT"):
            continue
        stem = _base_kit(key[1:].rsplit(".", 1)[0])
        guns = {g.decode("latin-1").lower() for g in _ITEM.findall(_plain(arc, entry))
                if g.lower().endswith(b".gun")}
        if stem in enemy_kits:
            theirs |= guns
        elif stem in ally_kits or _NUMBERED.match(stem):
            yours |= guns
        # anything else is an unreferenced kit -- editor leftovers and props.
        # Counting those as the player's is what made every AK look shared.
    return yours - theirs, theirs - yours, yours & theirs


def gun_paths(files, names):
    """The archive paths for a set of `.gun` filenames."""
    want = {"/" + n.upper() for n in names}
    return sorted(k for k in files if k in want)


# ---------------------------------------------------------------------------
# rewriting, in place and to the byte
# ---------------------------------------------------------------------------

def _same_width(text, value):
    """`value` rendered into exactly len(text) characters, or None.

    Integers are left-padded with zeros; floats give up decimal places first
    and only then refuse. `atoi`/`atof` read a leading zero the same as none,
    so this changes the number without changing the file's shape.
    """
    width = len(text)
    if "." not in text:
        if value < 0:
            return None
        out = "%d" % int(round(value))
        if len(out) > width:
            # The field has no room for the number asked for. Clamping to the
            # widest value it CAN hold moves the dial in the direction the
            # player asked rather than leaving the weapon untouched, which is
            # what skipping used to do -- The Sum of All Fears writes its
            # accuracies in three characters, so 700 could not double at all.
            out = "9" * width
        return out.rjust(width, "0")
    places = len(text.split(".", 1)[1])
    while places >= 0:
        out = "%.*f" % (places, value)
        if len(out) <= width:
            return out.rjust(width, "0")
        places -= 1
    return None


def _scale_tag(data, tag, factor):
    rx = re.compile(rb"(<" + tag.encode() + rb">)([^<]*)(</)")
    changed = [0]
    skipped = [0]

    def sub(m):
        text = m.group(2).decode("latin-1")
        try:
            value = float(text)
        except ValueError:
            return m.group(0)
        out = _same_width(text, value * factor)
        if out is None:
            skipped[0] += 1
            return m.group(0)
        changed[0] += 1
        return m.group(1) + out.encode("latin-1") + m.group(3)

    return rx.sub(sub, data), changed[0], skipped[0]


def _scale_attribute(data, attr, factor):
    rx = re.compile(rb"(\b" + attr.encode() + rb'\s*=\s*")([^"]*)(")')
    changed = [0]
    skipped = [0]

    def sub(m):
        text = m.group(2).decode("latin-1")
        try:
            value = float(text)
        except ValueError:
            return m.group(0)
        out = _same_width(text, value * factor)
        if out is None:
            skipped[0] += 1
            return m.group(0)
        changed[0] += 1
        return m.group(1) + out.encode("latin-1") + m.group(3)

    return rx.sub(sub, data), changed[0], skipped[0]


def scale(plain, params):
    """Scale the named groups of fields in one `.GUN`. Length is preserved.

    `params` is {group: factor} over the keys of FIELDS plus "rate", which
    lives on an attribute rather than in an element.
    """
    out, total = plain, 0
    for group, factor in sorted(params.items()):
        factor = float(factor)
        if abs(factor - 1.0) < 1e-9:
            continue
        if group == "rate":
            out, n, _skip = _scale_attribute(out, "RateOfFire", factor)
            total += n
            continue
        for tag in FIELDS.get(group, ()):
            out, n, _skip = _scale_tag(out, tag, factor)
            total += n
    if len(out) != len(plain):                    # cannot happen; proves it
        raise ValueError("gun edit changed length %d -> %d"
                         % (len(plain), len(out)))
    return out, total


def read(plain):
    """{field: value} for the fields this module edits, for a census."""
    out = {}
    for tag in ("MagazineCapacity", "MaxRange", "Recoil") + ACCURACY:
        m = re.search(("<%s>([^<]*)</%s>" % (tag, tag)).encode(), plain)
        if m:
            try:
                out[tag] = float(m.group(1))
            except ValueError:
                pass
    m = re.search(rb'RateOfFire\s*=\s*"([^"]*)"', plain)
    if m:
        try:
            out["RateOfFire"] = float(m.group(1))
        except ValueError:
            pass
    return out

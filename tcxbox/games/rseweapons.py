"""The Weapons page the three Red Storm discs share.

All four Red Storm games on Xbox keep one `.GUN` file per weapon, in the same
XML shape, so one set of cards drives all four -- 48 weapons in Ghost Recon, 61
in Island Thunder, 114 in Ghost Recon 2 and 162 in Summit Strike.

The page is two columns of the same four dials -- your side's weapons and the
enemies' -- because `rseguns.sides` can tell them apart from the missions. A
weapon both sides carry is reached by neither dial: it is one file, and making
the enemy AK worse would make yours worse with it. The cards say how many.

Accuracy is the one dial that reads backwards, and it is labelled to match:
the numbers in the file are a cone, so a bigger number is a worse shot.
"""

from __future__ import annotations

from ..model import INT, FileEdit, Setting

GROUP = "Weapons"

#: (suffix, label, unit, low, high, what it does, which .GUN fields)
DIALS = (
    ("mag", "Magazine capacity", 25, 400,
     "Rounds per magazine, on every weapon %s carries."),
    ("rate", "Rate of fire", 25, 400,
     "Rounds per minute, on every weapon %s carries. Fully automatic weapons "
     "feel this most."),
    ("recoil", "Recoil", 0, 400,
     "How far the muzzle climbs per shot, on every weapon %s carries. Zero is "
     "no climb at all."),
    ("spread", "Shot spread", 25, 400,
     "The aim cone, on every weapon %s carries -- all twelve stance values at "
     "once, from running while standing down to prone and still. This is the "
     "one dial where LOWER is better: the number in the file is the size of "
     "the cone, so 50%% is twice as accurate and 200%% is half."),
)

#: dial suffix -> the field group `rseguns.scale` understands
FIELD_GROUP = {"mag": "magazine", "rate": "rate", "recoil": "recoil",
               "spread": "accuracy"}

SIDES = (("ally", "Your side's", "your squad", "ally_guns"),
         ("enemy", "Enemy", "the enemy", "enemy_guns"))


def cards(prefix, census=None):
    """The eight cards. `census` is (yours, theirs, shared) counts, if known."""
    out = []
    for side, side_label, whose, _scope in SIDES:
        for suffix, label, low, high, help_text in DIALS:
            out.append(Setting(
                "%s%s_%s" % (prefix, side, suffix),
                "%s %s" % (side_label, label.lower()), INT, 100, GROUP,
                minimum=low, maximum=high, unit="%",
                help=help_text % whose,
                touches="data", confidence="applied"))
    return out


def edits(prefix, values):
    """One edit per side per dial, aimed by `rseguns.sides`."""
    out = []
    for side, side_label, _whose, scope in SIDES:
        params = {}
        for suffix, _label, _low, _high, _help in DIALS:
            pct = int(values.get("%s%s_%s" % (prefix, side, suffix), 100))
            if pct != 100:
                params[FIELD_GROUP[suffix]] = pct / 100.0
        if params:
            bits = ", ".join("%s x%.2f" % (k, v) for k, v in sorted(params.items()))
            out.append(FileEdit("scale_gun", r"\.GUN$", params,
                                "%s weapons: %s" % (side_label.rstrip("'s"), bits),
                                scope=scope))
    return out


# ---------------------------------------------------------------------------
# the two games that cannot be split by side
# ---------------------------------------------------------------------------
#
# `rseguns.sides` works by reading a mission's `<Company Allied="1">` blocks and
# the `Kit` attribute on each actor inside them. Ghost Recon 2 and Summit Strike
# author neither: their `.MIS` files hold Igor placement objects and zones, the
# loadouts are `.WSF` weapon sets rather than `.KIT` files, and there is no
# allied flag anywhere in them. So on those two games the census comes back
# empty and a per-side dial would silently reach nothing.
#
# One honest dial that says it moves every weapon in the game is better than two
# that claim a split the data cannot support.

def shared_cards(prefix):
    out = []
    for suffix, label, low, high, help_text in DIALS:
        out.append(Setting(
            "%sall_%s" % (prefix, suffix),
            "%s (all weapons)" % label, INT, 100, GROUP,
            minimum=low, maximum=high, unit="%",
            help=help_text % "everyone" +
                 "  This game gives no way to tell your weapons from theirs -- "
                 "its missions carry no allied flag and no per-actor kit -- so "
                 "this moves every weapon in the game, yours included.",
            confidence="applied"))
    return out


def shared_edits(prefix, values):
    params = {}
    for suffix, _label, _low, _high, _help in DIALS:
        pct = int(values.get("%sall_%s" % (prefix, suffix), 100))
        if pct != 100:
            params[FIELD_GROUP[suffix]] = pct / 100.0
    if not params:
        return []
    bits = ", ".join("%s x%.2f" % (k, v) for k, v in sorted(params.items()))
    return [FileEdit("scale_gun", r"\.GUN$", params, "every weapon: %s" % bits)]

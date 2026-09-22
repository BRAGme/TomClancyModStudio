"""Field of view, and why the weapon looks so big in split screen.

There is no viewmodel FOV on this engine
----------------------------------------

The obvious request -- a slider for the first-person weapon's own field of
view -- cannot be answered, because the weapon does not have one. It is
positioned in world space and projected with the SAME camera as the world.
Three independent checks say so: the draw routine at `0x003f53b0` (and its
twin at `0x003f4a80`) computes an attach-bone matrix, the sway, and a
per-weapon offset, then hands a position and integer angles to the renderer,
with no projection or scale anywhere in its 0x924 bytes; the first-person
flag at `G+0x417d5` has exactly four readers, and they choose a draw bucket, a
fog value and an LOD skip, nothing else; and a search of all 128 MB for any
tangent, cotangent or radian form of 90 degrees against 25.714 finds nothing.

So the weapon looks large in split screen for the reason it appears to: the
same projection into a half-height viewport. Widening the camera is the only
lever, and it moves the world with it.

What this edits
---------------

`DefaultFOV` is a serialised float in the player controller's class defaults.
There are exactly TWO of them in `COMMON.LIN`, which is what made this look
like a runtime override at first:

======================  =========  =======  ================================
package                 offset     value    what it is
======================  =========  =======  ================================
`0x00009e17`            403787     85.0     the base `Engine.PlayerController`
`0x00086a7f`            1159217    **90.0** the R6 subclass -- the live one
======================  =========  =======  ================================

The subclass value is the one that reaches the player, and 90.0 is what the
engine actually runs: the scope drives the same field to 25.714, which is
90/3.5 where 3.5 is that weapon's zoom, and `R6GAMESETTINGS.INI` carries a
comment reading "FOV==90 ---> full speed" for the turn rate.

This rewrites the subclass value. Four bytes, in place, so the package length
never moves and the container is untouched.

The site is found by walking the packages rather than by a stored offset, for
the same reason every other edit here is: an offset is only true for the build
it was measured on. The base value's 85.0 is asserted on the way past, which
doubles as a check that the two have not swapped order.

What it does NOT do
-------------------

It is a class default, so it applies to single player as well as split
screen. There is no per-mode copy to edit. That is stated on the card rather
than hidden, because someone who wants a wider split-screen view probably
does not expect the campaign to change too.
"""

from __future__ import annotations

from . import upackage

#: What the disc ships in the subclass, and in the base class behind it.
STOCK = 90.0
BASE_STOCK = 85.0

#: The engine demonstrably runs 25.7 (scoped) through 90, so the band below
#: is well inside what it handles. It is a tangent, so the top is kept well
#: short of 180 where the projection degenerates.
MINIMUM, MAXIMUM = 60, 120


class FovError(Exception):
    pass


def sites(plain: bytes, prop: str = "DefaultFOV") -> list:
    """[(packageBase, offset, value)] for every default of one property."""
    out = []
    for base, _pkg in upackage.packages(plain):
        try:
            names, _imports, _exports = upackage.tables(plain, base)
        except Exception:                                             # noqa: BLE001
            continue
        if prop not in names:
            continue
        try:
            found = upackage.float_properties(plain, names, prop)
        except Exception:                                             # noqa: BLE001
            continue
        for off, value, _nb in found:
            out.append((base, off, value))
    return sorted(out, key=lambda r: r[1])


def _live(plain):
    """The subclass's DefaultFOV and DesiredFOV -- the pair that reaches the
    player.

    BOTH matter, which the first version of this got wrong. Writing
    DefaultFOV alone changed nothing on hardware: the camera follows
    DesiredFOV, and the two sit seven bytes apart in the same class-default
    block. They are returned together so neither can be edited without the
    other again.
    """
    default = sites(plain, "DefaultFOV")
    desired = sites(plain, "DesiredFOV")
    if len(default) != 2:
        raise FovError("expected 2 DefaultFOV defaults, found %d -- this is "
                       "not the build this was measured on" % len(default))
    if abs(default[0][2] - BASE_STOCK) > 0.01:
        raise FovError("the base class default reads %.3f, not the %.1f this "
                       "build should have" % (default[0][2], BASE_STOCK))
    pkg = default[1][0]
    mine = [r for r in desired if r[0] == pkg]
    if len(mine) != 1:
        raise FovError("expected 1 DesiredFOV in the subclass package, found "
                       "%d" % len(mine))
    return [mine[0], default[1]]


def reads(plain: bytes) -> float:
    """What the live defaults currently say."""
    return _live(plain)[0][2]


def apply(plain: bytes, degrees: int):
    """Rewrite both live defaults. Returns (bytes, changed)."""
    import struct

    if not MINIMUM <= degrees <= MAXIMUM:
        raise FovError("%d degrees is outside the %d..%d this writes"
                       % (degrees, MINIMUM, MAXIMUM))
    out = bytearray(plain)
    changed = 0
    for _base, off, value in _live(plain):
        if abs(value - degrees) < 0.01:
            continue
        struct.pack_into("<f", out, off, float(degrees))
        changed += 1
    if len(out) != len(plain):
        raise FovError("the field-of-view edit changed the file length")
    return bytes(out), changed


def card(prefix, group):
    from .model import INT, Setting

    return Setting(
        prefix + "fov", "Field of view", INT, int(STOCK), group,
        minimum=MINIMUM, maximum=MAXIMUM, unit="degrees",
        confidence="untested", touches="data",
        help="The first-person weapon looks large in split screen because it "
             "is projected with the same camera as the world, into a viewport "
             "half the height. The weapon has no field of view of its own on "
             "this engine, so widening the camera is the only lever -- and it "
             "pulls the weapon back with everything else.",
        caution="Four bytes, rewritten in place, so nothing moves. The value "
                "is found by walking the packages rather than from a stored "
                "offset, and the base class default behind it is checked to "
                "read 85.0 on the way past.\n\n"
                "It is a CLASS DEFAULT, so it applies to single player too. "
                "There is no per-mode copy to edit. If you widen this for "
                "split screen the campaign gets the same view.\n\n"
                "Not play-tested. 90 is stock. The engine demonstrably "
                "handles 25.7 through 90 already, because that is what "
                "aiming a scope does to the same field." + '\n\nFirst attempt wrote DefaultFOV alone and changed nothing on hardware. The camera follows DesiredFOV; the two are seven bytes apart in the same class-default block and both are written now.')

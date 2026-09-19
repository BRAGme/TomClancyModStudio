"""Making enemies fight from cover instead of standing in the open.

The complaint this answers
-------------------------

Enemies stand still and shoot. Raising their accuracy only makes standing
still more lethal, which is the opposite of what anyone wants.

One script function decides it. `R6TerroristAI.GetEngageReaction` rolls
`Rand(100)+1`, shifts the roll by personality, and walks a ladder of
thresholds to pick one of five reactions. Only **ActionSpot** produces cover,
peeking, leaning, blind fire and repositioning -- the other branches are
"stand there and aim", "stand there and spray", and "run away". Shipped, for a
normal unwounded terrorist in a group, ActionSpot is the top **10%** of the
roll. That is the whole problem, in one byte.

What was measured
-----------------

The function holds two ladders -- one for when the terrorist is outnumbered,
one for everything else -- and each rung is a fixed 13-byte statement::

    07 <jumpTarget:16>  97  01 42 01  2c <threshold>     ... 16 04 24 <reaction>
    JumpIfNot           >   the roll  IntConstByte           Return ByteConst

`ANCHOR` is the five bytes from the comparison to the constant. It occurs
**exactly seven times** in both COMMON.LIN and COMMON_SS.LIN, at identical
offsets, carrying exactly the shipped thresholds -- so the sites are found by
signature and nothing here hardcodes an offset. The returned enum values
confirm the reading: 1 ActionSpot, 2 AimedFire, 3 SprayFire, 4 RunAway.

Why the edit is safe to make
----------------------------

Every threshold is one byte and stays one byte, so the package does not move
and the equal-length rule is never tested. The ladders must stay strictly
decreasing or a rung becomes unreachable -- a threshold that is not below the
one before it means the branch above already returned for that roll -- and
every set below is checked for that.
"""

from __future__ import annotations

from .model import CHOICE, Choice, Setting

#: comparison, the roll's variable reference, then the constant's opcode
ANCHOR = bytes.fromhex("970142012c")

#: how many rungs there are, and the value each shipped with, in file order:
#: four for the outnumbered ladder, then three for the ordinary one.
STOCK = (90, 75, 30, 10, 90, 55, 10)

#: which rungs belong to which ladder, so each can be checked on its own
LADDERS = ((0, 1, 2, 3), (4, 5, 6))


class CoverError(Exception):
    pass


#: Each set is the seven thresholds in file order. The only rung that matters
#: is the first of each ladder -- it is the one that buys cover -- but the
#: rungs below it have to come down too, or the branches they guard vanish.
SETS = {
    "stock": STOCK,
    "cover": (70, 55, 25, 10, 70, 45, 10),
    "heavy": (50, 40, 20, 10, 50, 30, 10),
}

#: what each set does to an ordinary, unwounded terrorist in a group
SHARES = {
    "stock": "10% cover, 35% aimed, 45% spray, 10% flee",
    "cover": "30% cover, 25% aimed, 35% spray, 10% flee",
    "heavy": "50% cover, 20% aimed, 20% spray, 10% flee",
}


def _check(values):
    if len(values) != len(STOCK):
        raise CoverError("expected %d thresholds, got %d"
                         % (len(STOCK), len(values)))
    for ladder in LADDERS:
        rungs = [values[i] for i in ladder]
        if any(a <= b for a, b in zip(rungs, rungs[1:])):
            raise CoverError("a ladder must be strictly decreasing, got %r"
                             % (rungs,))
        if not all(1 <= v <= 99 for v in rungs):
            raise CoverError("thresholds must leave room either side: %r"
                             % (rungs,))


def sites(plain: bytes) -> list:
    """Offset of each threshold BYTE, in file order."""
    out, at = [], plain.find(ANCHOR)
    while at >= 0:
        out.append(at + len(ANCHOR))
        at = plain.find(ANCHOR, at + 1)
    return out


def reads(plain: bytes):
    """What the thresholds currently say, for verify and revert."""
    return tuple(plain[o] for o in sites(plain))


def apply(plain: bytes, choice: str = "stock"):
    """Rewrite the ladders. Returns (bytes, rungsChanged).

    The count is not decoration: every data operation hands one back, and
    `dataedit` unpacks the pair. Returning bare bytes made it try to unpack
    the file itself, one byte per name.
    """
    want = SETS.get(choice)
    if want is None:
        raise CoverError("unknown cover setting %r" % (choice,))
    _check(want)
    found = sites(plain)
    if len(found) != len(STOCK):
        raise CoverError("expected %d threshold sites, found %d -- this is "
                         "not the build this was measured on"
                         % (len(STOCK), len(found)))
    live = tuple(plain[o] for o in found)
    if live not in (STOCK, ) and live not in [SETS[k] for k in SETS]:
        raise CoverError("the thresholds read %r, which is neither the "
                         "shipped set nor one this tool writes" % (live,))
    out = bytearray(plain)
    changed = 0
    for off, value in zip(found, want):
        changed += out[off] != value
        out[off] = value
    return bytes(out), changed


def cards(prefix: str, group: str) -> list:
    return [
        Setting(prefix + "ai_cover", "How often enemies fight from cover",
                CHOICE, "stock", group,
                choices=[
                    Choice("stock", "Stock (they mostly stand still)",
                           "The shipped ladder. Cover is the top 10% of the "
                           "roll, so four fights in five are a man standing "
                           "in the open shooting at you."),
                    Choice("cover", "Three times more often",
                           SHARES["cover"]),
                    Choice("heavy", "Half the time",
                           SHARES["heavy"] + ". Changes how a room plays."),
                ],
                help="One function decides what an enemy does when he engages, "
                     "and only one of its five answers makes him use cover, "
                     "peek, lean or blind-fire. This moves the threshold that "
                     "picks it. It is the reason raising accuracy made them "
                     "deadlier without making them smarter -- accuracy "
                     "multiplies the branch where he is standing still.",
                caution="Load-tested 2026-09-19 and it loads. Withdrawn "
                        "earlier the same day and put back: the disc that hung "
                        "also had WAVE MODE on, which is the thing that hangs "
                        "Terrorist Hunt, and the bisect that seemed to convict "
                        "this option never removed it. Confirmed by reading "
                        "the console's own memory -- with only this applied, "
                        "Parade Terrorist Hunt reaches gameplay and the edited "
                        "ladder is live in EE RAM at 0x00c361a5, exactly where "
                        "the shipped one sat.\n\n"
                        "What is still NOT tested is the firefight itself. It "
                        "loads; nobody has yet watched whether they actually "
                        "use the cover.\n\n"
                        "Cover only helps where the level gives them "
                        "somewhere to go: a map ships 28-38 action spots and "
                        "an enemy only looks 20 m for one. Raising \"How far "
                        "they look for cover\" with this is the pair.",
                confidence="applied", touches="data"),
    ]

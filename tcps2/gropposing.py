r"""Desert Siege's own enemy skins, which Ghost Recon ships and never loads.

Ghost Recon's wave modes -- Firefight, Recon, the solo types -- draw their
enemies from a shared roster the engine loads by name, seven templates built
from one format string::

    VA 0x005837E0   "opposing_force_%i.atr"     (file offset = VA - 0x100000 + 0x80)
    VA 0x00583800   "opposing_force_%i.kit"

The disc carries FOURTEEN templates for it, in two complete sets::

    OPPOSING_FORCE_0..6          "a Georgian Rebel"     ICE_Rebel_georgian_1..6ver
    OPPOSING_FORCE_DESERT_0..6   "an Ethiopian Soldier" reg1..reg5, irr1, irr2

and the string has no `_desert` form anywhere in the executable -- "desert"
appears in it only inside the display text "Desert Siege". So the second set
was authored, shipped, and never given a way to load: Desert Siege's wave
modes field Georgian rebels.

Jungle Storm hit the same problem and solved it by editing this very literal,
to `opposing_force_jungle_%i.atr`.

WHAT THIS CHANGES, AND WHAT IT COSTS
------------------------------------

One string. The slot is 32 bytes -- 21 of literal, 11 of padding, with
`opposing_force_%i.kit` starting after it -- and the replacement needs 29, so
nothing moves and no pointer is rewritten.

**There is one roster for the whole disc**, so this is a swap rather than an
addition: choose `desert` and the Georgian rebels stop appearing in the
campaign's own wave modes too. That is the right trade on a disc being played
for Desert Siege and the wrong one otherwise, which is why it is a choice and
why it is off by default.

The kit is not involved. Both sets carry an empty `<KitPath/>` and the weapons
come from the separate `opposing_force_%i.kit` load, which is untouched -- so
the enemies keep their loadouts and only their skins change. (There are five
kit files for seven templates on the stock disc; that is how it ships.)

NOT PLAY-TESTED. The two template sets, the single format string, the absence
of any `_desert` form and the room in the slot are all measured off the disc.
That the roster is what a wave mode actually spawns is inferred from there
being no other enemy source for it.
"""

from __future__ import annotations

import struct

#: The format string the roster is built from, and the slot it sits in.
#: Ghost Recon's ELF maps VA to file offset with +0x80, not Jungle Storm's
#: +0x100 -- getting that wrong puts the edit 128 bytes early.
VA = 0x005837E0
SLOT = 32

STOCK = b"opposing_force_%i.atr"
DESERT = b"opposing_force_desert_%i.atr"

CHOICES = {
    "stock": STOCK,
    "desert": DESERT,
}
DEFAULT = "stock"


def _words(text: bytes):
    """The slot's contents as 32-bit words, NUL-padded."""
    if len(text) >= SLOT:
        raise ValueError("%r does not fit %d bytes with its terminator"
                         % (text, SLOT))
    blob = text.ljust(SLOT, bytes(1))
    return [struct.unpack_from("<I", blob, i)[0] for i in range(0, SLOT, 4)]


#: {va: stock} for every word of the slot, so a revert has them even when the
#: option is off and emits nothing.
GR_STOCK = {VA + i * 4: w for i, w in enumerate(_words(STOCK))}


def edits(choice: str = DEFAULT):
    """(va, value, stock, note) for each word of the slot."""
    want = CHOICES.get(choice)
    if want is None or want == STOCK:
        return []
    new, old = _words(want), _words(STOCK)
    note = "wave enemies: Desert Siege's Ethiopians instead of Georgian rebels"
    return [(VA + i * 4, n, o, note)
            for i, (n, o) in enumerate(zip(new, old)) if n != o]


def card(prefix, group):
    from .model import CHOICE, Choice, Setting

    return Setting(
        prefix + "opposing_force", "Who the wave modes field", CHOICE,
        DEFAULT, group, confidence="experimental", touches="code",
        choices=[
            Choice("stock", "Georgian rebels",
                   "As it ships: ICE_Rebel_georgian, on every map."),
            Choice("desert", "Desert Siege's Ethiopians",
                   "The seven templates the disc carries and never loads, "
                   "on the reg1-5 and irr1-2 models."),
        ],
        help="Firefight, Recon and the solo modes draw their enemies from a "
             "roster the engine loads by name, and the disc carries TWO "
             "complete sets of it -- seven Georgian rebels and seven "
             "Ethiopian soldiers.\n\n"
             "Only the Georgians can ever load. The name is built from one "
             "format string with no desert form anywhere in the executable, "
             "so Desert Siege's own wave enemies were authored, shipped and "
             "left unreachable. Jungle Storm hit the same thing and fixed it "
             "by editing this exact string.",
        caution="There is ONE roster for the whole disc, so this is a swap "
                "rather than an addition: choosing the Ethiopians takes the "
                "Georgian rebels out of the campaign's own wave modes too.\n\n"
                "Weapons are unaffected -- both sets carry an empty kit path "
                "and the loadout comes from a separate file this does not "
                "touch, so only the skins change.\n\n"
                "Not yet confirmed in play. The two sets, the single format "
                "string and the room in the slot are measured off the disc; "
                "that this roster is what a wave actually spawns is inferred "
                "from there being no other source for it.")


def gr_edits(v: dict):
    return edits(str(v.get("gr_opposing_force") or DEFAULT))


def selftest(gr_elf: bytes):
    """The stock slot against the executable. [] = pass."""
    bad = []
    off = VA - 0x100000 + 0x80
    if gr_elf[off:off + len(STOCK)] != STOCK:
        bad.append("gr %08X is not the stock literal" % VA)
    if gr_elf[off + len(STOCK)] != 0:
        bad.append("gr %08X has no terminator" % VA)
    for va, new, old, _n in edits("desert"):
        if (va - VA) % 4 or not (0 <= va - VA < SLOT):
            bad.append("%08X is outside the slot" % va)
    return bad

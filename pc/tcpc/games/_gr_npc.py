r"""Ghost Recon: giving the enemy its own copy of every weapon it carries.

Both sides read the same `Equip\*.gun`, which is why every weapon option in
this profile says it moves the player and the enemy together. This is the way
out, and it is the technique the user's own `PS2Accuracy` mod demonstrates:
ship a second copy of each gun under an `_npc` name, and point the enemy's
KITS at the copies. Stock `Equip\*.gun` is then the player's set, untouched.

Nothing about this needs a mission edit. The side partition is already in the
file layout, and it was measured rather than assumed.

## Who is on which side

Walking all 29 campaign missions and inheriting `Allied="1"` down
Company -> Platoon -> Team to each `<Actor Kit="...">`:

    721 enemy placements   across 18 kits
     38 allied placements  across  4 kits

and **all 22 of those kits live in `Equip\`**, while all 71 kits the player
draws from live under `Kits\`. The two folders share not one path. So the
enemy's kit set is `Equip\*.kit` and shadowing it cannot reach the player.

## Which guns, and why the list is derived rather than written down

The 30 kits in `Equip\` name 13 guns between them, and **five of those are
also named by the player's kits** -- `at4`, `dragunov`, `m16`, `rpk74`,
`sa80`. Those five are the entire problem: they are what makes "enemy
accuracy" move the player's gun too. The other eight are enemy-only and could
safely be edited in place, but they are split as well so that the enemy's
weapon set is wholly its own and a later option can move it freely.

The set is read out of the kits at build time instead of being a list in this
file. The reason is concrete: `PS2Accuracy` carries 31 `_npc.gun`, of which 19
have no base gun in the retail campaign at all -- they belong to Heroes
Unleashed. A fixed list goes stale against whatever is actually installed; the
kits never do.

## The allied NPCs, who are not enemies

Four kits carry allied placements. Two of them -- `m16 only.kit` and
`sa80 only.kit` -- are allied-EXCLUSIVE, so they are left pointing at the
ordinary guns. That does not mean "stock": it means friendly NPCs get whatever
the PLAYER's weapons are set to, which is the right side for them to be on.
`noweapon.kit` names no gun at all and is skipped.

The fourth, `m1911 only.kit`, is used by **both** sides -- two allied
placements and some enemy ones -- so it cannot be separated by kit. It is
treated as an enemy kit and the option says so rather than pretending the
partition is perfect.

## What this fixes about the reference implementation

`PS2Accuracy` shadows 19 of the 30 kits in `Equip\`. The eleven it misses
include `default.kit` and **all five `opposing_force_*.kit`** -- which is
every script-spawned enemy in co-op and adversarial play. Deriving the kit set
from the folder picks those up.
"""

import os
import re

from ._rse import (ITEM_RX, KILL_COEFFS, NPC_ACCURACY, NPC_DAMAGE,
                   NPC_RECOIL, NPC_SUFFIX, PACES, STANCES, npc_name)
from ..model import BOOL, CHOICE, Choice, FileCopy, INT, Setting, XmlText

KITS = "Equip/*.kit"
GUNS = "Equip/*.gun"

#: `<ItemFileName>` is how a kit names the thing it carries.
ITEM = "ItemFileName"

#: Kits with allied placements and NO enemy ones, measured across the 29
#: campaign missions. Left alone by default so friendly NPCs keep stock
#: weapons. `m1911 only.kit` is deliberately NOT here: both sides use it.
ALLIED_ONLY_KITS = ("m16 only.kit", "sa80 only.kit")



def settings():
    return [
        Setting(
            "npc_weapons", "Give the enemy its own weapons", BOOL, False,
            group="Enemies",
            help="Both sides read the same weapon files, which is why the "
                 "weapon options move your guns and theirs together. This "
                 "ships a second copy of each gun the enemy carries and "
                 "points the enemy's kits at the copies, so the two can be "
                 "tuned apart. Your own weapons are then whatever the Weapons "
                 "page says; the enemy's are set below. Friendly NPCs stay on "
                 "the player's side of the split.",
            caution="One kit, m1911 only.kit, is carried by both a handful of "
                    "friendly NPCs and by enemies, so those few friendlies "
                    "get the enemy's pistol. Everything else separates "
                    "cleanly.",
            confidence="experimental", touches="mod"),
        Setting(
            "npc_accuracy", "Enemy weapon accuracy", CHOICE, "stock",
            group="Enemies", requires={"npc_weapons": True},
            help="Applies to the enemy's copies only. Ghost Recon stores "
                 "DISPERSION, so a smaller number is a tighter weapon.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("tight", "Tighter", "Cone reduced by a third."),
                Choice("loose", "Looser", "Half again as wide."),
                Choice("wild", "Wild", "Doubled."),
            ],
            confidence="experimental", touches="mod"),
        Setting(
            "npc_recoil", "Enemy weapon recoil", CHOICE, "stock",
            group="Enemies", requires={"npc_weapons": True},
            help="Applies to the enemy's copies only.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("none", "None", ""),
                Choice("half", "Half", ""),
                Choice("double", "Double", ""),
            ],
            confidence="experimental", touches="mod"),
        Setting(
            "npc_damage", "Enemy weapon damage", CHOICE, "stock",
            group="Enemies", requires={"npc_weapons": True},
            help="How hard the enemy's copies hit. The engine builds kill "
                 "energy from the weapon's own coefficients, so this is the "
                 "enemy half of 'How hard weapons hit' on the Weapons page.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("x1.5", "Harder", ""),
                Choice("x2", "Lethal", "Doubled."),
                Choice("x0.6", "Softer", ""),
            ],
            confidence="experimental", touches="mod"),
        Setting(
            "npc_mags", "Extra magazines for the enemy", INT, 0,
            group="Enemies", minimum=0, maximum=20, unit=" extra",
            requires={"npc_weapons": True},
            help="Enemy kits carry two magazines where the player's carry "
                 "ten. Added to the enemy's kits only.",
            confidence="experimental", touches="mod"),
    ]


def enemy_kits(base_mod_dir):
    """{kit path: [guns it names]} for the kits the enemy draws from.

    Read off the installation rather than listed here -- see the module
    docstring for why a written-down list goes stale.
    """
    out = {}
    folder = os.path.join(base_mod_dir, "Equip")
    if not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(".kit"):
            continue
        if name.lower() in ALLIED_ONLY_KITS:
            continue
        try:
            with open(os.path.join(folder, name), "rb") as fh:
                text = fh.read().decode("latin-1")
        except OSError:                              # pragma: no cover
            continue
        guns = [g.strip() for g in ITEM_RX.findall(text)
                if g.strip().lower().endswith(".gun")]
        if guns:
            out["Equip/" + name] = guns
    return out




def edits(values, base_mod_dir):
    """`base_mod_dir` is the stock mod folder the generated one shadows."""
    v = values
    if not v["npc_weapons"]:
        return []

    kits = enemy_kits(base_mod_dir)
    if not kits:
        return []
    guns = sorted({g for gs in kits.values() for g in gs})
    rename = {g: npc_name(g) for g in guns}

    out = []
    # 1. every enemy kit now names the copies
    for kit in sorted(kits):
        out.append(XmlText(kit, path=ITEM, remap=dict(rename),
                           note="enemy kit points at its own weapons"))

    # 2. the copies themselves, each starting life as the stock gun
    for gun in guns:
        rel = "Equip/" + npc_name(gun)
        out.append(FileCopy(rel, source="Equip/" + gun,
                            note="enemy copy of " + gun))

        acc = NPC_ACCURACY.get(v["npc_accuracy"])
        if acc:
            for pace in PACES:
                for stance in STANCES:
                    out.append(XmlText(
                        rel, path="%s%sAccuracy" % (pace, stance), scale=acc,
                        minimum=0, absent="skip",
                        note="enemy accuracy: %s %s" % (pace.lower(),
                                                        stance.lower())))
        punch = NPC_DAMAGE.get(v["npc_damage"])
        if punch:
            for tag in KILL_COEFFS:
                out.append(XmlText(rel, path=tag, scale=punch, absent="skip",
                                   note="enemy damage: " + tag))
        kick = NPC_RECOIL.get(v["npc_recoil"])
        if kick is not None:
            out.append(XmlText(rel, path="Recoil", scale=kick, minimum=0,
                               absent="skip", note="enemy recoil"))

    # 3. magazines live on the KIT, not the gun
    if v["npc_mags"]:
        for kit in sorted(kits):
            out.append(XmlText(kit, path="MagazineCount",
                               offset=v["npc_mags"], minimum=1, maximum=99,
                               note="enemy magazines"))
    return out


# ---------------------------------------------------------------------------
# body armour, which does nothing in the base campaign
# ---------------------------------------------------------------------------
#
# `Equip\CmbtModl.xml` holds one factor per body part, used as a DIVISOR of
# the shot's kill energy. Four of its entries are the armoured-chest factors,
# one per armour level, and **base Ghost Recon's copy does not have them**:
# its file carries 8 elements where both expansions carry 12, identical but
# for `BallisticArmoredChestFactor0..3` at 0 / 150 / 350 / 750.
#
# The loader zeroes every factor before reading the file, so an absent factor
# is a factor of zero -- and `killChance = 1 - (factor / energy)` with a zero
# factor is a certain kill. Every armour level therefore behaves exactly like
# no armour at all, which makes this profile's own "enemy body armour" option
# a measurable no-op on the base campaign. It works in the expansions, which
# ship the numbers.
#
# The fix is to ship them. The values are not invented: they are copied from
# the expansions' own files, authored by the same developer at the same
# `VersionNumber`. The tool generates the whole file rather than editing it,
# because a span editor cannot insert an element -- and the one thing that
# must not happen is a factor going MISSING, since the loader would read that
# as zero and make the body part instantly fatal.

ARMOUR_FACTORS = (("BallisticArmoredChestFactor0", "0.000000"),
                  ("BallisticArmoredChestFactor1", "150.000000"),
                  ("BallisticArmoredChestFactor2", "350.000000"),
                  ("BallisticArmoredChestFactor3", "750.000000"))

#: the element the four are written after, matching the expansions' order
ARMOUR_AFTER = "BallisticChestFactor"

COMBAT_MODEL = "Equip/CmbtModl.xml"


def armour_setting():
    return Setting(
        "armour_works", "Make body armour work", BOOL, False, group="Enemies",
        help="Ghost Recon's base campaign ships a combat model with no "
             "armoured-chest factors in it -- 8 entries where both expansions "
             "have 12. The loader treats a missing factor as zero, and a zero "
             "factor means a certain kill, so every armour level behaves like "
             "no armour and the body-armour option above changes nothing on "
             "the base campaign. This adds the four numbers, copied verbatim "
             "from the expansions' own files.",
        caution="It makes armoured enemies harder to kill, which is the "
                "point, but it is a change to how the base campaign has "
                "always played. The expansions are unaffected -- they already "
                "have these values.",
        confidence="experimental", touches="mod")


def armour_edits(values, base_mod_dir):
    """Rewrite `CmbtModl.xml` with the armour factors the base game omits."""
    if not values.get("armour_works"):
        return []
    path = os.path.join(base_mod_dir, COMBAT_MODEL.replace("/", os.sep))
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return []
    text = raw.decode("latin-1")
    if ARMOUR_FACTORS[0][0] in text:
        return []                       # already there; nothing to do
    lines = text.splitlines(True)
    out = []
    for line in lines:
        out.append(line)
        if "<%s>" % ARMOUR_AFTER in line:
            # copy the anchor's own indentation and line ending, so the file
            # stays in the shape the game shipped it in
            lead = line[:len(line) - len(line.lstrip())]
            end = line[len(line.rstrip("\r\n")):] or "\r\n"
            for name, value in ARMOUR_FACTORS:
                out.append("%s<%s>%s</%s>%s" % (lead, name, value, name, end))
    return [FileCopy(COMBAT_MODEL, data="".join(out).encode("latin-1"),
                     note="armoured-chest factors the base game omits")]


#: The four factors, once they exist. Ghost Recon's stock ladder is the
#: expansions' -- 0 / 150 / 350 / 750 -- which is steeper at the top than Sum
#: of All Fears' 0 / 150 / 350 / 550.
ARMOUR_TAGS = ["BallisticArmoredChestFactor%d" % i for i in range(4)]

ARMOUR_SCALE = {"x1.7": 1.7, "x0.5": 0.5}


def armour_value_setting():
    return Setting(
        "armour_value", "How much body armour helps", CHOICE, "stock",
        group="Enemies", requires={"armour_works": True},
        help="One factor per armour level, applied to chest hits, and the "
             "engine divides it into the shot's kill energy -- so a bigger "
             "number absorbs more. Level 0 is zero, meaning no armour and no "
             "protection; level 3 is 750. Sum of All Fears has had this "
             "option all along; Ghost Recon could not, because until the "
             "switch above there were no factors in the file to scale.",
        choices=[
            Choice("stock", "Stock", "0 / 150 / 350 / 750."),
            Choice("x1.7", "Armour matters more", ""),
            Choice("x0.5", "Armour matters less", ""),
            Choice("none", "Armour does nothing",
                   "All four at zero, which is what the base game does "
                   "already by leaving them out."),
        ],
        confidence="experimental", touches="mod")


def armour_value_edits(values):
    """Scale the factors `armour_edits` has just put in the file.

    Order matters and the engine provides it: a `FileCopy` supplies the
    file's starting content and the edits in the same group are then applied
    on top of it, so these reach the generated factors rather than the base
    game's missing ones.
    """
    if not values.get("armour_works"):
        return []
    choice = values.get("armour_value", "stock")
    if choice == "none":
        return [XmlText(COMBAT_MODEL, path=tag, value="0.000000",
                        note="armour value") for tag in ARMOUR_TAGS]
    factor = ARMOUR_SCALE.get(choice)
    if not factor:
        return []
    return [XmlText(COMBAT_MODEL, path=tag, scale=factor, minimum=0,
                    note="armour value") for tag in ARMOUR_TAGS]

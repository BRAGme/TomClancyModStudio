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

from ..model import BOOL, CHOICE, Choice, FileCopy, INT, Setting, XmlText

KITS = "Equip/*.kit"
GUNS = "Equip/*.gun"

#: `<ItemFileName>` is how a kit names the thing it carries.
ITEM = "ItemFileName"

#: Kits with allied placements and NO enemy ones, measured across the 29
#: campaign missions. Left alone by default so friendly NPCs keep stock
#: weapons. `m1911 only.kit` is deliberately NOT here: both sides use it.
ALLIED_ONLY_KITS = ("m16 only.kit", "sa80 only.kit")

#: appended to a gun's base name. Matches what `PS2Accuracy` uses, so the two
#: cannot both be installed and disagree about what `ak47_npc.gun` means --
#: whichever mod sits higher in the load order simply wins, as it should.
SUFFIX = "_npc"

_ITEM_RX = re.compile(r"<\s*ItemFileName\s*>\s*([^<]+?)\s*<", re.I)


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
        guns = [g.strip() for g in _ITEM_RX.findall(text)
                if g.strip().lower().endswith(".gun")]
        if guns:
            out["Equip/" + name] = guns
    return out


def npc_name(gun):
    stem, ext = os.path.splitext(gun)
    return stem + SUFFIX + ext


ACCURACY = {"tight": 0.66, "loose": 1.5, "wild": 2.0}
RECOIL = {"none": 0.0, "half": 0.5, "double": 2.0}

#: the twelve-entry accuracy matrix, spelled `<PaceStanceAccuracy>` in the
#: file. Lower is tighter: an AK47 reads 24 standing still and 1200 running.
PACES = ("Run", "Walk", "Shuffle", "Stationary")
STANCES = ("Stand", "Crouch", "Prone")


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

        acc = ACCURACY.get(v["npc_accuracy"])
        if acc:
            for pace in PACES:
                for stance in STANCES:
                    out.append(XmlText(
                        rel, path="%s%sAccuracy" % (pace, stance), scale=acc,
                        minimum=0, absent="skip",
                        note="enemy accuracy: %s %s" % (pace.lower(),
                                                        stance.lower())))
        kick = RECOIL.get(v["npc_recoil"])
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

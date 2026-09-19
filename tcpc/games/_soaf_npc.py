r"""Sum of All Fears: the enemy-weapon split, which needs a second mechanism.

Same goal as Ghost Recon's (`_gr_npc.py`) -- give the enemy its own copies of
the guns it carries so the two sides can be tuned apart -- but the file layout
does not allow the same solution, and the difference is worth writing down.

## Why Ghost Recon's trick does not transfer

Ghost Recon separates the sides by FOLDER: the enemy's kits are loose in
`Equip\` and the player's are under `Kits\`, with not one path in common. Sum
of All Fears has no `Equip\` kit folder at all. All 132 kits live in two
folders and **the enemy draws from both**:

    Kits\mercenaries\   38 kits   239 enemy placements
    Kits\team\          94 kits   176 enemy placements  (the `multi_NN` kits)

`Kits\team\` is also where the player's own loadouts live, so shadowing a
`multi_NN.kit` would change what the enemy carries AND what the player can
pick. That is the reason this game needed a mechanism the tool did not have.

## The measurement that makes the second mechanism safe

Walking all 25 campaign missions and inheriting `Allied="1"` down
Company -> Platoon -> Team to each `<Actor Kit="...">`:

    415 enemy placements   across 23 kits
     61 allied placements  across  5 kits

and **not one allied placement anywhere uses a `multi_*` kit**. The allied
kits are `hrt_stealth`, `open_assault`, `cqb_assault`, `no_gun` and
`m9_only`. So rewriting a mission's `Kit="multi_08.kit"` to
`Kit="multi_08_npc.kit"` cannot reach a friendly soldier -- which is what lets
this be a plain attribute remap rather than the "every node whose ancestor is
not Allied" predicate it looked like it would need.

## So there are two routes, by folder

* **`Kits\mercenaries\`** is the enemy's own folder, so those kits are
  shadowed in place and simply point at the copies. `no_gun.kit` is skipped:
  it is an empty `<KitFile>` naming no weapon.
* **`Kits\team\multi_NN.kit`** belongs to the player as well, so it is left
  alone. Instead a copy is written to `Kits\mercenaries\multi_NN_npc.kit` and
  the campaign missions are rewritten to name it. Kit basenames are unique
  across both folders, so the game's by-name lookup resolves the copy.

## The seam, stated rather than hidden

`m9_only.kit` carries two allied placements as well as fourteen enemy ones, so
those two friendly soldiers get the enemy's pistol. Exactly the same seam as
Ghost Recon's `m1911 only.kit`, and for the same reason: one kit, both sides,
nothing in the file layout to tell them apart.

## Why this matters more here than in Ghost Recon

Ghost Recon's two sides share five guns. Sum of All Fears' share **nineteen**
of the twenty-two the enemy carries, so without the split almost every weapon
option really is moving both sides at once.
"""

import os
import re

from ._rse import (ITEM_RX, KILL_COEFFS, NPC_ACCURACY, NPC_DAMAGE,
                   NPC_RECOIL, NPC_SUFFIX, PACES, STANCES, npc_name)
from ..model import BOOL, CHOICE, Choice, FileCopy, INT, Setting, XmlAttr, XmlText

MERC = "Kits/mercenaries"
TEAM = "Kits/team"
MISSIONS = "Mission/*.mis"
#: the guns both sides draw from, which is what the player keeps
EQUIP_GUNS = "Equip/*.gun"
ITEM = "ItemFileName"

#: the one kit in the enemy's folder that is allied-only. It names no weapon,
#: so it would be a no-op anyway -- skipped so the log does not claim a change.
SKIP_KITS = ("no_gun.kit",)

_TAG_RX = re.compile(r'<(/?)(Company|Platoon|Team|Actor)\b([^>]*)>', re.I)


def _attr(text, key):
    m = re.search(r'%s\s*=\s*"([^"]*)"' % key, text, re.I)
    return m.group(1) if m else None


def enemy_mission_kits(base_mod_dir):
    """Kit names worn by NON-allied actors in the campaign.

    `Allied="1"` is declared on a Company, Platoon or Team and inherited by
    everything under it, so the file has to be walked as a tree rather than
    scanned for actors. An actor with no allied ancestor is an enemy.
    """
    folder = os.path.join(base_mod_dir, "Mission")
    if not os.path.isdir(folder):
        return set()
    out = set()
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(".mis"):
            continue
        try:
            with open(os.path.join(folder, name), "rb") as fh:
                text = fh.read().decode("latin-1")
        except OSError:                              # pragma: no cover
            continue
        stack = []
        for m in _TAG_RX.finditer(text):
            closing, tag, body = m.group(1), m.group(2).lower(), m.group(3)
            if closing:
                if stack and stack[-1][0] == tag:
                    stack.pop()
                continue
            allied = _attr(body, "Allied")
            if tag == "actor":
                side = allied if allied is not None else next(
                    (v for _t, v in reversed(stack) if v is not None), None)
                kit = _attr(body, "Kit")
                if kit and side != "1":
                    out.add(kit.strip())
                continue
            if not body.rstrip().endswith("/"):
                stack.append((tag, allied))
    return out


def _guns_in(path):
    try:
        with open(path, "rb") as fh:
            text = fh.read().decode("latin-1")
    except OSError:                                  # pragma: no cover
        return []
    return [g.strip() for g in ITEM_RX.findall(text)
            if g.strip().lower().endswith(".gun")]


def enemy_kits(base_mod_dir):
    """(kits to shadow in place, kits to copy across) -> {rel: [guns]}.

    The first group is the enemy's own folder. The second is the player's
    folder, where the enemy borrows a loadout and therefore cannot be followed
    by editing the file itself.
    """
    shadow, copy = {}, {}
    merc = os.path.join(base_mod_dir, MERC.replace("/", os.sep))
    if os.path.isdir(merc):
        for name in sorted(os.listdir(merc)):
            if not name.lower().endswith(".kit"):
                continue
            if name.lower() in SKIP_KITS:
                continue
            guns = _guns_in(os.path.join(merc, name))
            if guns:
                shadow[MERC + "/" + name] = guns

    borrowed = {k for k in enemy_mission_kits(base_mod_dir)
                if os.path.isfile(os.path.join(base_mod_dir,
                                               TEAM.replace("/", os.sep), k))}
    team = os.path.join(base_mod_dir, TEAM.replace("/", os.sep))
    for name in sorted(borrowed):
        guns = _guns_in(os.path.join(team, name))
        if guns:
            copy[TEAM + "/" + name] = guns
    return shadow, copy


def settings():
    return [
        Setting(
            "npc_weapons", "Give the enemy its own weapons", BOOL, False,
            group="Enemies",
            help="You and the enemy carry nineteen of the same twenty-two "
                 "weapons, which is why the weapon options move both sides. "
                 "This ships a second copy of each gun the enemy carries and "
                 "points the enemy at the copies, so the two can be tuned "
                 "apart. Your own weapons are then whatever the Weapons page "
                 "says; the enemy's are set below.",
            caution="Sum of All Fears keeps no separate enemy kit folder, so "
                    "for the loadouts the enemy borrows from yours the "
                    "campaign missions are rewritten to name the copies. Not "
                    "one friendly soldier in the campaign wears a borrowed "
                    "loadout, so none of them is affected -- except the two "
                    "who carry m9_only.kit, which is also an enemy kit and "
                    "cannot be told apart.",
            confidence="experimental", touches="mod"),
        Setting(
            "npc_accuracy", "Enemy weapon accuracy", CHOICE, "stock",
            group="Enemies", requires={"npc_weapons": True},
            help="Applies to the enemy's copies only. These are DISPERSION "
                 "numbers, so a smaller one is a tighter weapon.",
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
            help="Added to the enemy's kits only.",
            confidence="experimental", touches="mod"),
    ]


def edits(values, base_mod_dir):
    v = values
    if not v["npc_weapons"]:
        return []
    shadow, borrowed = enemy_kits(base_mod_dir)
    if not shadow and not borrowed:
        return []

    guns = sorted({g for gs in list(shadow.values()) + list(borrowed.values())
                   for g in gs})
    rename = {g: npc_name(g) for g in guns}
    out = []

    # 1. the enemy's own kits point at the copies, in place
    for kit in sorted(shadow):
        out.append(XmlText(kit, path=ITEM, remap=dict(rename),
                           note="enemy kit points at its own weapons"))

    # 2. the loadouts borrowed from the player are COPIED, not shadowed, so
    #    the player's own remain exactly as they were
    kit_rename = {}
    for kit in sorted(borrowed):
        name = kit.rsplit("/", 1)[-1]
        copy_rel = "%s/%s" % (MERC, npc_name(name))
        kit_rename[name] = npc_name(name)
        out.append(FileCopy(copy_rel, source=kit,
                            note="enemy copy of " + name))
        out.append(XmlText(copy_rel, path=ITEM, remap=dict(rename),
                           note="enemy copy points at its own weapons"))

    # 3. ...and the missions name the copies. Safe as a plain remap because no
    #    allied placement in the campaign wears a borrowed loadout.
    if kit_rename:
        out.append(XmlAttr(MISSIONS, path="Actor", attr="Kit",
                           remap=kit_rename,
                           note="enemy placements use the copied loadouts"))

    # 4. the gun copies themselves
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

    # 5. magazines are on the kit
    if v["npc_mags"]:
        for kit in sorted(shadow):
            out.append(XmlText(kit, path="MagazineCount", offset=v["npc_mags"],
                               minimum=1, maximum=99, note="enemy magazines"))
        for kit in sorted(borrowed):
            copy_rel = "%s/%s" % (MERC, npc_name(kit.rsplit("/", 1)[-1]))
            out.append(XmlText(copy_rel, path="MagazineCount",
                               offset=v["npc_mags"], minimum=1, maximum=99,
                               note="enemy magazines"))
    return out

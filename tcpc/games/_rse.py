r"""What Ghost Recon and Sum of All Fears have in common.

They are the same engine -- Red Storm's Ike -- and they mod the same way, so
the options that apply to both live here and each profile adds its own.

**Delivery is a mod folder, and that is the whole safety story.** The game
enumerates `Mods\*.*`, reads each folder's `ModsCont.txt` and lets you pick
one in its own menu; a mod is a SPARSE OVERLAY, so it only has to contain the
files it changes. Nothing retail is written, and switching the mod off in the
game is a complete uninstall. The user's own hand-made `PS2Accuracy` mod is the
proof of the minimum: 51 files, a `ModsCont.txt` and an `Equip\` folder.

**Telling the enemies from your own squad is a matter of WHERE the file is,
not what is in it.** Both games keep their enemy actors loose in
`Actor\*.atr` and the player's squad in subfolders of it -- `rifleman\`,
`demolitions\`, `heavy-weapons\`, `sniper\`, `hero\` in Ghost Recon, and
`Team Members\` in Sum of All Fears. That is why `engine.expand` had to stop
`*` from crossing a separator: under ordinary `fnmatch` semantics "make the
enemies tougher" would also have buffed the player's riflemen.

The obvious-looking discriminator does not work. `<ClassName>` says
`demolitions` on 624 of Ghost Recon's 825 actor files, enemies included, and
Sum of All Fears has no `<ClassName>` at all.
"""

import os
import re

from ..model import (BOOL, CHOICE, Choice, INT, Setting, XmlAttr, XmlText)

#: Enemies: loose at the top of the Actor folder. `*` does not cross a
#: separator, so the player's squad -- which lives one level down -- is not
#: matched.
ENEMY_ACTORS = "Actor/*.atr"

#: ...but the folder is not the whole test, and assuming it was is a mistake
#: this profile shipped. An actor with a `<KitPath>` was equipped out of the
#: PLAYER's kit folders, which makes it friendly however it is filed. In
#: Ghost Recon all 562 root actors lack one, so this changes nothing there; in
#: Sum of All Fears 49 of 448 have one -- eleven support teams and a hostage --
#: and every "tougher enemies" option had been buffing them.
ENEMY_ONLY = "lacks:KitPath"

#: The fixed name every script-spawned multiplayer and co-op enemy uses. These
#: sit in the Actor root, so `ENEMY_ACTORS` already reaches them.
MP_ACTORS = "Actor/opposing_force_*.atr"
GUNS = "Equip/*.gun"
COMBAT_MODEL = "Equip/CmbtModl.xml"

#: How hard a weapon hits. The engine builds kill energy from five fields on
#: the `.gun`, all present on every one of Ghost Recon's 32 and Sum of All
#: Fears' 35:
#:
#:     v(d)      = V0 + V1*d + V2*d*d
#:     energy(d) = K1*v(d) + K2*v(d)*v(d)
#:
#: and the hit-location factor in `CmbtModl.xml` is then a DIVISOR of that:
#: `killChance = 1 - (factor / energy)`. So the gun is the numerator and the
#: combat model the denominator, which is why this tool has options on both.
#:
#: Only the two K's are scaled. Energy is LINEAR in them -- scaling both by
#: the same factor scales energy by exactly that factor and leaves every
#: ballistic curve's shape untouched -- whereas it is quadratic in the
#: velocity trio, and several weapons carry negative V1/V2 that make their
#: curve invert past MaxRange. Retail K1 runs -0.6 to 10 and K2 0.002 to 10.
KILL_COEFFS = ("KillCoefficient1", "KillCoefficient2")

#: Enemy behaviour is scripted per TEAM in the mission plans, not on the
#: actors. Measured across every mission in both games: all 208 Ghost Recon
#: and 65 Sum of All Fears alertness steps -- and every ROE, speed and grenade
#: step with them -- sit under a team with no `Allied="1"` ancestor. Not one
#: belongs to a friendly team, so these can be written globally.
MISSIONS = "Mission/*.mis"

#: Where each game keeps the kits the PLAYER draws from, which is not the same
#: folder in the two of them and is not the same folder as the enemy's in
#: either. Ghost Recon puts the player's under `Kits\<class>\` and the
#: enemy's loose in `Equip\`; Sum of All Fears splits `Kits	eam\` from
#: `Kits\mercenaries\`. Pointing "spare magazines" at the wrong one would
#: resupply the opposition.
PLAYER_KITS = {
    "ghost_recon": "Kits/**/*.kit",
    "soaf": "Kits/team/*.kit",
}

#: Ghost Recon's actor skills are rungs from 1 to 7, not a percentage.
SKILL_MIN, SKILL_MAX = 1, 7
#: ...and armour is 0 to 3, an index into the combat model's armour factors.
ARMOUR_MIN, ARMOUR_MAX = 0, 3


def shared_settings(game_id="ghost_recon"):
    """The options both games can offer, in the order they should appear."""
    return [
        # -- Enemies -----------------------------------------------------
        Setting(
            "enemy_skill", "Enemy marksmanship", CHOICE, "stock",
            group="Enemies",
            help="Every enemy actor file carries four skill rungs from 1 to "
                 "7 -- weapon, stamina, stealth and leadership. This moves "
                 "the weapon rung, which is the one that decides how well "
                 "they shoot. Stock enemies cluster at 2 and 3 in Ghost "
                 "Recon and rather higher in Sum of All Fears.",
            choices=[
                Choice("stock", "Stock", "As the game ships."),
                Choice("green", "Green", "One rung down, with a floor of 1."),
                Choice("sharp", "Sharp", "One rung up."),
                Choice("elite", "Elite", "Every enemy at the top of the "
                                         "scale, 7."),
            ],
            confidence="experimental", touches="mod"),
        Setting(
            "enemy_armour", "Enemy body armour", CHOICE, "stock",
            group="Enemies",
            help="An index from 0 to 3 into the combat model's armour "
                 "factors. It is the difference between a chest hit killing "
                 "and a chest hit not.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("none", "None", "Everyone at 0 -- unarmoured."),
                Choice("up", "One level heavier", ""),
                Choice("max", "Fully armoured", "Everyone at 3."),
            ],
            confidence="experimental", touches="mod"),
        Setting(
            "enemy_awareness", "Enemy stealth and coordination", CHOICE,
            "stock", group="Enemies",
            help="The other three rungs: stealth, stamina and leadership. "
                 "Moved together, because they describe how an enemy squad "
                 "behaves rather than how it shoots.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("up", "Sharper", "One rung up."),
                Choice("down", "Slower", "One rung down."),
            ],
            confidence="experimental", touches="mod"),

        Setting(
            "enemy_alertness", "How alert enemies start", CHOICE, "stock",
            group="Enemies",
            help="Every enemy team's plan carries an alertness state. State 2 "
                 "is alert and state 1 is not -- settled from the missions "
                 "themselves rather than guessed: across the campaign only 1 "
                 "of the 63 plans holding state 1 has an alarm-sounding name, "
                 "against 38 of the 98 holding state 2, including one called "
                 "'Camp Warns Caves'. Every one of these plans belongs to an "
                 "enemy team; not one belongs to a friendly one.",
            choices=[
                Choice("stock", "Stock", "As the missions were authored."),
                Choice("alert", "Everyone alert",
                       "No one is caught unaware. Stealth stops paying."),
                Choice("unaware", "Everyone unaware",
                       "Even the teams scripted to be expecting you."),
            ],
            confidence="experimental", touches="mod"),
        # -- (Ghost Recon only) ------------------------------------
    ] + ([] if game_id != "ghost_recon" else [
        Setting(
            "enemy_grenades", "Enemies throw grenades", BOOL, True,
            group="Enemies",
            help="Grenades are switched on per enemy team in the mission "
                 "plans, and every one of the 80 that mention them switches "
                 "them ON. This turns them off.",
            confidence="experimental", touches="mod"),
        Setting(
            "enemy_speed", "How fast enemies move", CHOICE, "stock",
            group="Enemies",
            help="The movement rate on an enemy team's plan, stock 1.6 to 8 "
                 "with most at 2. Only affects teams whose plan sets one.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("x1.5", "Faster", ""),
                Choice("x0.6", "Slower", ""),
            ],
            confidence="experimental", touches="mod"),
    ]) + [
        Setting(
            "weapon_damage", "How hard weapons hit", CHOICE, "stock",
            group="Weapons",
            help="The engine works out whether a shot kills from the "
                 "weapon's own kill energy against a factor for the body "
                 "part hit. This scales the energy every weapon delivers. "
                 "At fifty metres a stock 9mm reaches about 480 and an M16 "
                 "about 1989, so the spread between a pistol and a rifle is "
                 "already four to one.",
            caution="Scaled so that every weapon's ballistic curve keeps its "
                    "shape -- only the two kill coefficients move, never the "
                    "velocity ones, which are quadratic and carry negative "
                    "signs on some weapons.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("x1.5", "Harder", ""),
                Choice("x2", "Lethal", "Doubled."),
                Choice("x0.6", "Softer", ""),
            ],
            confidence="experimental", touches="mod"),
        # -- Lethality ---------------------------------------------------
        Setting(
            "lethality", "How lethal a hit is", CHOICE, "stock",
            group="Lethality",
            help="The combat model scores each body part with a factor, and "
                 "LOWER is more lethal: the head is 10 and a lower arm is "
                 "1000. This scales all seven, so the relationship between "
                 "them is kept and only the overall lethality moves. It "
                 "applies to everyone, you included.",
            choices=[
                Choice("stock", "Stock", "Head 10, chest 100, limbs 500 to "
                                         "1000."),
                Choice("lethal", "More lethal", "Halved, so hits count for "
                                                "twice as much."),
                Choice("brutal", "One-shot territory",
                       "A quarter. A chest hit is close to fatal."),
                Choice("spongy", "Less lethal", "Doubled."),
            ],
            confidence="experimental", touches="mod"),

        # -- Weapons -----------------------------------------------------
        Setting(
            "weapon_accuracy", "Weapon accuracy", CHOICE, "stock",
            group="Weapons",
            help="The twelve dispersion numbers on every weapon, one per "
                 "posture and pace. HIGHER means worse, so the scale is "
                 "inverted here to read the way you would expect: 'tighter' "
                 "makes the numbers smaller.",
            caution="These files are shared between you and the enemies, so "
                    "by default this moves both sides. In Ghost Recon, "
                    "turning on 'Give the enemy its own weapons' separates "
                    "them and makes this option the player's alone.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("tight", "Tighter", "Halved dispersion."),
                Choice("loose", "Looser", "Doubled."),
                Choice("ps2", "PS2-like", "Four times the dispersion, which "
                                          "is what the console ports play "
                                          "like."),
            ],
            confidence="experimental", touches="mod"),
        Setting(
            "recoil", "Recoil", CHOICE, "stock", group="Weapons",
            choices=[
                Choice("stock", "Stock", "1.5 to 120 depending on the "
                                         "weapon."),
                Choice("x0.5", "Halved", ""),
                Choice("none", "None", ""),
                Choice("x1.5", "Heavier", ""),
            ],
            confidence="experimental", touches="mod"),
        Setting(
            "magazines", "Magazine capacity", CHOICE, "stock", group="Weapons",
            caution="Two weapons ship with a magazine of 30000 rounds -- they "
                    "are mounted guns, not a mistake -- and scaling leaves "
                    "them effectively unchanged.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("x2", "Double", ""),
                Choice("x0.5", "Halved", ""),
            ],
            confidence="experimental", touches="mod"),
        Setting(
            "spare_mags", "Spare magazines carried", INT, 0, group="Weapons",
            minimum=0, maximum=20, unit=" extra",
            help="Added to the magazine count in every kit your own squad "
                 "draws from -- not the enemy's, which are in a different "
                 "folder. Stock kits carry between 2 and 20 depending on the "
                 "weapon, so this is an addition rather than a replacement.",
            confidence="experimental", touches="mod"),
    ]


def shared_edits(values, game_id):
    """The edits those options turn into."""
    out = []
    v = values
    actor_globs = [ENEMY_ACTORS]

    # -- enemy skill rungs -----------------------------------------------
    skill = v["enemy_skill"]
    if skill != "stock":
        for glob in actor_globs:
            if skill == "elite":
                out.append(XmlText(glob, path="Weapon", value="7",
                                   note="enemy marksmanship", scope=ENEMY_ONLY))
            else:
                # A rung up or down, clamped to the 1..7 scale. An addition
                # rather than a multiplication, because the rungs are a scale
                # and not a quantity: scaling turns a 2 into a 2.68 and a 6
                # into an 8, which is off the end.
                out.append(XmlText(
                    glob, path="Weapon",
                    offset=1 if skill == "sharp" else -1,
                    minimum=SKILL_MIN, maximum=SKILL_MAX,
                    note="enemy marksmanship", scope=ENEMY_ONLY))

    aware = v["enemy_awareness"]
    if aware != "stock":
        for glob in actor_globs:
            for tag in ("Stamina", "Stealth", "Leadership"):
                out.append(XmlText(
                    glob, path=tag, offset=1 if aware == "up" else -1,
                    minimum=SKILL_MIN, maximum=SKILL_MAX,
                    note="enemy " + tag.lower(), scope=ENEMY_ONLY))

    armour = v["enemy_armour"]
    if armour != "stock":
        for glob in actor_globs:
            if armour == "none":
                out.append(XmlText(glob, path="ArmorLevel", value="0",
                                   note="enemy armour", scope=ENEMY_ONLY))
            elif armour == "max":
                out.append(XmlText(glob, path="ArmorLevel", value="3",
                                   note="enemy armour", scope=ENEMY_ONLY))
            else:
                out.append(XmlText(glob, path="ArmorLevel", offset=1,
                                   minimum=ARMOUR_MIN, maximum=ARMOUR_MAX,
                                   note="enemy armour", scope=ENEMY_ONLY))

    # -- enemy behaviour, scripted per team in the missions ---------------
    alert = {"alert": {"1": "2"}, "unaware": {"2": "1"}}.get(v["enemy_alertness"])
    if alert:
        # A remap rather than a plain value, on purpose: 47 of the alertness
        # steps declare no State at all, and those mean "whatever the team's
        # default is". Writing a State onto them would be inventing behaviour
        # that was never measured. Only declared states are flipped.
        out.append(XmlAttr(MISSIONS, path="Alertness", attr="State",
                           remap=alert, note="enemy alertness"))
    if game_id == "ghost_recon":
        if not v["enemy_grenades"]:
            out.append(XmlAttr(MISSIONS, path="Grenades", attr="Available",
                               value="0", stock="1", note="enemy grenades"))
        pace = {"x1.5": 1.5, "x0.6": 0.6}.get(v["enemy_speed"])
        if pace:
            out.append(XmlAttr(MISSIONS, path="Speed", attr="Rate",
                               scale=pace, minimum=0.1, note="enemy speed"))

    punch = {"x1.5": 1.5, "x2": 2.0, "x0.6": 0.6}.get(v["weapon_damage"])
    if punch:
        for tag in KILL_COEFFS:
            out.append(XmlText(GUNS, path=tag, scale=punch, note="damage: " + tag))

    # -- lethality --------------------------------------------------------
    lethal = {"lethal": 0.5, "brutal": 0.25, "spongy": 2.0}.get(v["lethality"])
    if lethal:
        for part in ("Head", "Chest", "Abdomen", "UpperArm", "LowerArm",
                     "UpperLeg", "LowerLeg"):
            out.append(XmlText(COMBAT_MODEL,
                               path="Ballistic%sFactor" % part, scale=lethal,
                               minimum=1, note="lethality: " + part.lower()))

    # -- weapons ----------------------------------------------------------
    spread = {"tight": 0.5, "loose": 2.0, "ps2": 4.0}.get(v["weapon_accuracy"])
    if spread:
        for pace in ("Run", "Walk", "Shuffle", "Stationary"):
            for stance in ("Stand", "Crouch", "Prone"):
                out.append(XmlText(
                    GUNS, path="%s%sAccuracy" % (pace, stance), scale=spread,
                    minimum=0, note="accuracy: %s %s" % (pace.lower(),
                                                         stance.lower())))

    kick = {"x0.5": 0.5, "none": 0.0, "x1.5": 1.5}.get(v["recoil"])
    if kick is not None:
        out.append(XmlText(GUNS, path="Recoil", scale=kick, minimum=0,
                           note="recoil"))

    mags = {"x2": 2.0, "x0.5": 0.5}.get(v["magazines"])
    if mags:
        out.append(XmlText(GUNS, path="MagazineCapacity", scale=mags,
                           minimum=1, note="magazine capacity"))

    if v["spare_mags"]:
        # An addition, not a multiplication. Stock kits carry between 2 and 20
        # magazines, so "+5" as a scale would be 3.5x on a pistol kit and
        # 1.25x on a machine-gunner's -- which is not what the label says.
        out.append(XmlText(PLAYER_KITS[game_id], path="MagazineCount",
                           offset=v["spare_mags"], minimum=1, maximum=99,
                           note="spare magazines"))
    return out


# ---------------------------------------------------------------------------
# the enemy-weapon split: vocabulary both games share
# ---------------------------------------------------------------------------
#
# Ghost Recon and Sum of All Fears use the same weapon-file vocabulary even
# though they need different mechanisms to reach the enemy's kits (see
# `_gr_npc.py` and `_soaf_npc.py`). These live here so neither of those two
# modules has to import from the other.

#: appended to a gun's base name to make the enemy's copy. Matches what the
#: `PS2Accuracy` mod uses, so the two cannot both be installed and disagree
#: about what `ak47_npc.gun` means -- whichever sits higher in the load order
#: simply wins, as it should.
NPC_SUFFIX = "_npc"

#: how a kit names the thing it carries
ITEM_RX = re.compile(r"<\s*ItemFileName\s*>\s*([^<]+?)\s*<", re.I)

#: the twelve-entry accuracy matrix, spelled `<PaceStanceAccuracy>` in a
#: `.gun`. LOWER is tighter: an AK47 reads 24 standing still and 1200 running.
PACES = ("Run", "Walk", "Shuffle", "Stationary")
STANCES = ("Stand", "Crouch", "Prone")

NPC_ACCURACY = {"tight": 0.66, "loose": 1.5, "wild": 2.0}
NPC_RECOIL = {"none": 0.0, "half": 0.5, "double": 2.0}
NPC_DAMAGE = {"x1.5": 1.5, "x2": 2.0, "x0.6": 0.6}


def npc_name(name):
    """`ak47.gun` -> `ak47_npc.gun`, `multi_08.kit` -> `multi_08_npc.kit`."""
    stem, ext = os.path.splitext(name)
    return stem + NPC_SUFFIX + ext

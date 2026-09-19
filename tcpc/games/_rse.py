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


def shared_settings():
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
                    "this moves both sides. The way to separate them is the "
                    "one the PS2Accuracy mod uses -- see the notes page.",
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

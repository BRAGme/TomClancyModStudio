r"""Rainbow Six 3: Lockdown (PC) -- Red Storm's Nimitz-era engine.

Every gameplay file is loose, tab-indented pseudo-XML with CRLF under `data\`,
which makes this the most directly editable game on the shelf. What it does not
have is a mod folder that ships, so delivery is INPLACE and the safety comes
from `engine.py`'s pristine-copy rule.

**There is a caveat on that, and it is written down rather than buried.**
`lockdown.exe` contains an entire mod manager -- a `mods/` root, the manifest
fields `NAME AUTHOR SUPPORT VERSION MULTIPLAYER ICON CLIENT-SIDE SERVER-SIDE`,
an active list `ModsSet.txt`, a `-modset` command-line switch and a full
multiplayer mod-negotiation UI. None of it is used by the retail install: no
`mods\` folder ships, so the layout a mod folder must have is unproven. If it
were proven, this profile should switch to MOD delivery like Ghost Recon's,
because that is strictly better. Until someone watches a generated mod folder
load, editing in place is the option that is known to work.

Two facts shape nearly every option here:

* **A weapon file holds the same block once per attachment.** `M8Compact.gun`
  carries `Default`, `RedDot`, `Scope`, `HiCapMag` and `Suppressor`, each with
  its own `<WeaponData>` and `<ReloadData>`. Every edit therefore writes all of
  them -- see `rsexml.set_attr` -- and anything proportional scales each one
  from its own value, so the extended magazine stays extended.
* **Enemies and the player use different copies of the same guns.** The 45
  `e_*.gun` files are the enemy side and the 42 without the prefix are the
  player side, so "enemy damage" and "your damage" are genuinely separate
  sliders rather than one number with a sign.
"""

from . import _lockdown_extra
from ..model import (BOOL, CHOICE, Choice, GameProfile, INPLACE, INT, Layout,
                     Setting, XmlAttr)

LAYOUT = Layout(
    signature=[
        "data/equip/CmbtModl.xml",
        "data/options.xml",
        "data/kits/*.wsf",
        "data/shell/art/background00.rsb",
    ],
    exe="lockdown.exe",
    data_dir="data",
)

#: Every `.gun` the enemy side uses. The prefix is the whole discriminator and
#: it is consistent across all 87 weapon files.
ENEMY_GUNS = "data/equip/e_*.gun"
PLAYER_GUNS = "data/equip/*.gun"

#: The enemy character archetypes, by name. A glob over `*.cgs` would also
#: sweep up the Rainbow operators and the hostages, and buffing the hostages is
#: not what "harder enemies" means.
ENEMY_ACTORS = ["data/actor/terrorist-*.cgs", "data/actor/militia-*.cgs",
                "data/actor/mercenary-*.cgs", "data/actor/paris_cell_leader.cgs"]

#: The nine operators that ship a `_coop` twin. Those twins are a complete
#: hardcore preset Ubisoft shipped and never exposed: head 6 / chest 8 / limbs
#: 9 against the single-player 8 / 20 / 20.
OPERATORS = ["anna_yacoby", "annika_lofquist", "eddie_price", "jamal_murad",
             "louis_loiselle", "pak_suo-won", "renee_raymond", "roger_mcallen"]

COOP_HITPOINTS = {"head": 6, "chest": 8, "leftarm": 9, "rightarm": 9,
                  "leftleg": 9, "rightleg": 9}

SETTINGS = [
    # -- Difficulty ------------------------------------------------------
    Setting(
        "enemy_accuracy", "Enemy marksmanship", INT, 15, group="Difficulty",
        minimum=0, maximum=100, unit=" / 100",
        help="The base accuracy every enemy fires with, written into all 45 "
             "enemy weapon files. 42 of them ship with exactly 15, which is "
             "why one number covers the whole opposition. Rainbow operators "
             "sit at 100 for comparison, so 40 is a noticeably sharper enemy "
             "and 100 makes them shoot like you do.",
        confidence="experimental", touches="data"),
    Setting(
        "enemy_damage", "Enemy weapon damage", CHOICE, "stock",
        group="Difficulty",
        help="Enemy weapons do 2-4 damage where yours do 10-12. This scales "
             "the enemy side only.",
        choices=[
            Choice("stock", "Stock", "2 to 4 per hit."),
            Choice("x2", "Double", "Enemies hurt about as much as a shotgun."),
            Choice("x3", "Triple", "Around half what your own rifle does."),
            Choice("match", "Same as yours",
                   "5x, which puts enemy rifles level with Rainbow rifles."),
        ],
        confidence="experimental", touches="data"),
    Setting(
        "enemy_skill", "Enemy reaction and awareness", CHOICE, "stock",
        group="Difficulty",
        help="The per-character skill rating, separate from how accurate "
             "their weapon is. Stock runs 27 for the weakest militia to 46 "
             "for the best mercenary; Rainbow operators are 100.",
        choices=[
            Choice("stock", "Stock", "27 to 46 depending on the faction."),
            Choice("up", "Sharper", "Half again, so 40 to 69."),
            Choice("elite", "Elite", "Doubled, so 54 to 92."),
            Choice("down", "Slower", "Two thirds, so 18 to 31."),
        ],
        confidence="experimental", touches="data"),
    Setting(
        "ai_team_accuracy", "Enemy squad accuracy floor", INT, 29,
        group="Difficulty", minimum=0, maximum=100, unit=" / 100",
        help="The team-level accuracy the enemy AI combat model applies on "
             "top of the weapon and the character. This is the number the "
             "game's own difficulty setting moves: 29 on Normal, 50 on "
             "Challenge.",
        confidence="experimental", touches="data"),
    Setting(
        "enemy_forced_miss", "Enemies deliberately miss you", BOOL, True,
        group="Difficulty",
        help="Stock enemy AI carries ForcedMiss = -100, a large accuracy "
             "penalty applied so the opening shots of a firefight go wide. "
             "Your own teammates have ForcedMiss = 1 and do not do this. "
             "Turning it off removes the grace period.",
        caution="This is the single harshest option here. Enemies stop "
                "missing on purpose the moment they see you.",
        confidence="experimental", touches="data"),

    # -- Rainbow ---------------------------------------------------------
    Setting(
        "rainbow_hitpoints", "Rainbow durability", CHOICE, "stock",
        group="Rainbow",
        help="Ubisoft shipped two sets of hitpoints for the eight named "
             "operators: the single-player set, and a co-op set roughly two "
             "and a half times squishier. The co-op files are on the disc "
             "already; this copies them over the single-player ones.",
        choices=[
            Choice("stock", "Single-player",
                   "Head 8, chest 20, limbs 20."),
            Choice("coop", "Co-op (the shipped hardcore set)",
                   "Head 6, chest 8, limbs 9 -- the game's own numbers, not "
                   "invented ones."),
        ],
        confidence="experimental", touches="data"),
    Setting(
        "wound_penalties", "Wounds spoil your aim", BOOL, False,
        group="Rainbow",
        help="The global combat model has six body parts, each with an "
             "aim-cone penalty, and all six ship at zero -- being shot in the "
             "arm currently costs you nothing. This switches them on.",
        caution="Shipped inert, and nothing in the data proves the engine "
                "still reads these six values rather than ignoring them. If "
                "you turn this on and notice no difference, that is the most "
                "likely reason.",
        confidence="experimental", touches="data"),
    Setting(
        "player_sway", "Weapon sway while turning", CHOICE, "stock",
        group="Rainbow",
        help="The global turn and lean penalty that sits on top of each "
             "weapon's own.",
        choices=[
            Choice("stock", "Stock", "Turning 60, leaning 2."),
            Choice("steady", "Steadier", "Halved."),
            Choice("none", "None", "Zeroed, for arcade handling."),
            Choice("heavy", "Heavier", "Doubled."),
        ],
        confidence="experimental", touches="data"),

    # -- Weapons ---------------------------------------------------------
    Setting(
        "player_damage", "Your weapon damage", CHOICE, "stock",
        group="Weapons",
        help="Scales every player weapon, and every attachment variant of it, "
             "from its own value -- so the sniper rifle stays stronger than "
             "the shotgun.",
        choices=[
            Choice("stock", "Stock", "Rifles 10-12, pistols 9-11."),
            Choice("x1.5", "Harder hitting", "Half again."),
            Choice("x2", "Double", ""),
            Choice("x0.5", "Halved", "For a longer, grindier fight."),
        ],
        confidence="experimental", touches="data"),
    Setting(
        "magazines", "Magazine capacity", CHOICE, "stock", group="Weapons",
        help="Each attachment variant scales from its own value, so a "
             "high-capacity magazine stays high-capacity.",
        choices=[
            Choice("stock", "Stock", ""),
            Choice("x2", "Double", ""),
            Choice("x0.5", "Halved", ""),
        ],
        confidence="experimental", touches="data"),
    Setting(
        "reserve_ammo", "Ammunition carried", CHOICE, "stock", group="Weapons",
        help="Reserve rounds behind the loaded magazine. Player weapons carry "
             "250 to 999; every enemy weapon already carries 999.",
        choices=[
            Choice("stock", "Stock", ""),
            Choice("x2", "Double", ""),
            Choice("x0.4", "Scarce", "Two fifths."),
        ],
        confidence="experimental", touches="data"),
    Setting(
        "recoil", "Recoil", CHOICE, "stock", group="Weapons",
        help="The kick each shot adds to your aim cone.",
        choices=[
            Choice("stock", "Stock", ""),
            Choice("x0.5", "Halved", ""),
            Choice("none", "None", "Perfectly flat."),
            Choice("x1.5", "Heavier", ""),
        ],
        confidence="experimental", touches="data"),

    # -- Equipment -------------------------------------------------------
    Setting(
        "unlock_equipment", "Unlock the multiplayer-only equipment", BOOL,
        False, group="Equipment",
        help="Six pieces of equipment are complete -- modelled, statted and "
             "named -- but marked unavailable in every single-player mode: "
             "C4, the claymore, the laser tripmine, the lock fuser, the "
             "proximity flash mine and the multi-smoke grenade. This flips "
             "their five single-player flags on.",
        caution="It makes them legal in single player; it does not put them "
                "in anyone's kit, so you will only see them where a kit file "
                "or a mission already asks for them.",
        confidence="experimental", touches="data"),
    Setting(
        "grenades", "Grenades carried", CHOICE, "stock", group="Equipment",
        help="How many of each thrown item you start a mission with. Frags "
             "are 3, flashbangs and smoke 5.",
        choices=[
            Choice("stock", "Stock", ""),
            Choice("x2", "Double", ""),
            Choice("x3", "Triple", ""),
        ],
        confidence="experimental", touches="data"),
    Setting(
        "frag_power", "Grenade lethality", CHOICE, "stock", group="Equipment",
        help="The damage and radius of every explosive, scaled from its own "
             "values so a breaching charge stays weaker than a frag.",
        choices=[
            Choice("stock", "Stock", "Frag 7-15 damage, 2 m kill radius."),
            Choice("x1.5", "Stronger", ""),
            Choice("x0.6", "Weaker", ""),
        ],
        confidence="experimental", touches="data"),

    # -- Interface -------------------------------------------------------
    Setting(
        "reticule", "Show the crosshair", BOOL, True, group="Interface",
        help="Turning it off is the usual first step towards a hardcore run; "
             "the weapon still fires where it is pointed.",
        confidence="applied", touches="config"),
    Setting(
        "hints", "Show hint messages", BOOL, True, group="Interface",
        confidence="applied", touches="config"),
    Setting(
        "camera_shake", "Camera shake from gunfire", BOOL, True,
        group="Interface", confidence="applied", touches="config"),
    Setting(
        "blood", "Blood effects", BOOL, True, group="Interface",
        confidence="applied", touches="config"),
    Setting(
        "dead_bodies", "Bodies stay where they fall", BOOL, True,
        group="Interface", confidence="applied", touches="config"),
    Setting(
        "show_fps", "Show the frame rate", BOOL, False, group="Interface",
        help="One of thirteen developer readouts that ship live in "
             "options.xml and are read by the retail executable. The names in "
             "the file match the exe's own attribute table exactly.",
        confidence="experimental", touches="config"),
    Setting(
        "show_position", "Show the player position", BOOL, False,
        group="Interface",
        help="Another of the shipped developer readouts. Useful when lining "
             "up a camera or a texture replacement.",
        confidence="experimental", touches="config"),
] + _lockdown_extra.settings() + _lockdown_extra.enemy_settings()


def _factor(values, key, table):
    return table.get(values.get(key))


def build_edits(values):
    out = []
    v = values

    # -- Difficulty ------------------------------------------------------
    if v["enemy_accuracy"] != 15:
        out.append(XmlAttr(
            ENEMY_GUNS, path="Common/AIAccuracy/Accuracy",
            attr="BaseAccuracy", value=v["enemy_accuracy"], stock="15",
            note="enemy marksmanship"))

    dmg = {"x2": 2.0, "x3": 3.0, "match": 5.0}.get(v["enemy_damage"])
    if dmg:
        for attr in ("damageMin", "damageMax"):
            out.append(XmlAttr(ENEMY_GUNS, path="WeaponData", attr=attr,
                               scale=dmg, minimum=1, maximum=999,
                               note="enemy weapon damage"))

    skill = {"up": 1.5, "elite": 2.0, "down": 0.66}.get(v["enemy_skill"])
    if skill:
        for glob in ENEMY_ACTORS:
            out.append(XmlAttr(glob, path="AICGSData/Accuracy",
                               attr="AISkillLevel", scale=skill,
                               minimum=1, maximum=100,
                               note="enemy skill rating"))

    if v["ai_team_accuracy"] != 29:
        out.append(XmlAttr(
            "data/mission/badguys.acm", path="Difficulty", attr="Normal",
            value=v["ai_team_accuracy"], stock="29",
            note="enemy squad accuracy"))


    # -- Rainbow ---------------------------------------------------------
    if v["rainbow_hitpoints"] == "coop":
        for name in OPERATORS:
            for part, hp in COOP_HITPOINTS.items():
                out.append(XmlAttr(
                    "data/actor/%s.cgs" % name, path="DamageModel/Hitpoints",
                    attr=part, value=hp, note="co-op hitpoints"))

    if v["wound_penalties"]:
        # 25 is a quarter of the aim-cone contribution the model gives a full
        # damage state, which is the only number in the file that is not zero
        # and so the only scale available to reason from.
        for part in ("Head", "Chest", "LeftArm", "RightArm", "LeftLeg",
                     "RightLeg"):
            out.append(XmlAttr(
                "data/equip/CmbtModl.xml", path="Wounded/" + part,
                attr="Value", value="25.000", stock="0.000",
                note="wound penalty: " + part.lower()))

    sway = {"steady": 0.5, "none": 0.0, "heavy": 2.0}.get(v["player_sway"])
    if sway is not None:
        for leaf in ("Turning/Turning", "Turning/Leaning"):
            out.append(XmlAttr("data/equip/CmbtModl.xml", path=leaf,
                               attr="Value", scale=sway, minimum=0,
                               note="global sway"))

    # -- Weapons ---------------------------------------------------------
    # Every weapon edit below is aimed at the PLAYER's copies. The glob would
    # also match the enemy ones, so each carries an explicit exclusion.
    pdmg = {"x1.5": 1.5, "x2": 2.0, "x0.5": 0.5}.get(v["player_damage"])
    if pdmg:
        for attr in ("damageMin", "damageMax"):
            out.append(_player(XmlAttr(PLAYER_GUNS, path="WeaponData",
                                       attr=attr, scale=pdmg, minimum=1,
                                       maximum=999,
                                       note="your weapon damage")))

    mags = {"x2": 2.0, "x0.5": 0.5}.get(v["magazines"])
    if mags:
        out.append(_player(XmlAttr(PLAYER_GUNS, path="ReloadData",
                                   attr="clipSize", scale=mags, minimum=1,
                                   maximum=9999, note="magazine capacity")))

    ammo = {"x2": 2.0, "x0.4": 0.4}.get(v["reserve_ammo"])
    if ammo:
        out.append(_player(XmlAttr(PLAYER_GUNS, path="ReloadData",
                                   attr="maxAmmo", scale=ammo, minimum=1,
                                   maximum=9999, note="ammunition carried")))

    kick = {"x0.5": 0.5, "none": 0.0, "x1.5": 1.5}.get(v["recoil"])
    if kick is not None:
        out.append(_player(XmlAttr(PLAYER_GUNS, path="PlayerAccuracy/Recoil",
                                   attr="Value", scale=kick, minimum=0,
                                   note="recoil")))

    # -- Equipment -------------------------------------------------------
    if v["unlock_equipment"]:
        locked = ["c4.itm", "claymore.itm", "laser_tripmine.itm",
                  "lock_fuser.itm", "proximity_flash_mine.itm",
                  "SmokeMulti.prj"]
        modes = ("spCampaign", "spTerroristHunt", "spInfiltrator",
                 "spLoneRush", "spSniper")
        for name in locked:
            for mode in modes:
                out.append(XmlAttr(
                    "data/equip/" + name, path="UsableInGameModes", attr=mode,
                    value="1", stock="0",
                    note="unlock %s in single player" % name))

    nades = {"x2": 2.0, "x3": 3.0}.get(v["grenades"])
    if nades:
        for glob in ("data/equip/*.prj", "data/equip/*.itm"):
            out.append(XmlAttr(glob, path="GeneralSettings", attr="count",
                               scale=nades, minimum=1, maximum=99,
                               note="grenades carried"))

    boom = {"x1.5": 1.5, "x0.6": 0.6}.get(v["frag_power"])
    if boom:
        for attr in ("killRange", "maxRange", "baseDamageMin",
                     "baseDamageMax"):
            for glob in ("data/equip/*.prj", "data/equip/*.itm"):
                out.append(XmlAttr(glob, path="ExplosionData", attr=attr,
                                   scale=boom, minimum=0,
                                   note="explosive power"))

    # -- Interface -------------------------------------------------------
    for key, attr in (("reticule", "displayReticule"),
                      ("hints", "displayHints"),
                      ("camera_shake", "enableGunfireCameraShake"),
                      ("blood", "enableblood"),
                      ("dead_bodies", "showDeadBodies")):
        if not v[key]:
            out.append(XmlAttr("data/options.xml", path="Preferences/game",
                               attr=attr, value="false", stock="true",
                               note=attr))
    for key, attr in (("show_fps", "showFrameRate"),
                      ("show_position", "showPlayerPosition")):
        if v[key]:
            out.append(XmlAttr("data/options.xml", path="Preferences/debug",
                               attr=attr, value="true", stock="false",
                               note=attr))
    out.extend(_lockdown_extra.edits(v, v["enemy_forced_miss"]))
    out.extend(_lockdown_extra.enemy_edits(v, ENEMY_GUNS))
    return out


def _player(edit):
    """Mark an edit as applying to the player's weapons only.

    `data\\equip\\*.gun` matches the enemy files too -- they are in the same
    folder and differ only by an `e_` prefix -- so a player-side edit has to
    say so. The engine reads `scope` when it expands the glob.
    """
    edit.scope = "not:e_*"
    return edit


def combination_warnings(values):
    out = []
    if values["enemy_damage"] == "match" and not values["enemy_forced_miss"]:
        out.append("Enemies will hit as hard as you do AND stop missing on "
                   "purpose. Expect to die in the first exchange.")
    if values["rainbow_hitpoints"] == "coop" and values["enemy_accuracy"] > 50:
        out.append("Co-op hitpoints with enemy marksmanship above 50 is well "
                   "past anything the game shipped with.")
    return out


NOTES = """\
Lockdown keeps everything in loose text under data\\, which is why this profile
has more to offer than any other game here -- and why every option edits a real
file in place rather than building a mod.

Two things are worth knowing before you use it.

The first is that lockdown.exe contains a complete, unused mod-folder system: a
mods\\ root, a ModsCont.txt manifest, a ModsSet.txt active list and a -modset
switch, together with the multiplayer negotiation screens for it. No mods\\
folder ships, so nobody has confirmed what one has to contain. If that were
settled this tool would build a mod instead, and nothing retail would be
touched.

The second is that the game notices. The shipped readme says that modifying
.itm, .gun or .prj files makes your server report modified data and stops you
hosting a ranked game. That is the only consequence documented, and it is
confined to ranked multiplayer.

Nothing in this profile has been watched working in a running game. Options are
badged for what is actually known: "measured, not play-tested" means the value
was read out of the file and written back correctly, which is not the same as
seeing it change anything.
"""


PROFILE = GameProfile(
    id="lockdown",
    title="Rainbow Six 3: Lockdown",
    short="Lockdown",
    layout=LAYOUT,
    delivery=INPLACE,
    settings=SETTINGS,
    build_edits=build_edits,
    combination_warnings=combination_warnings,
    notes=NOTES,
)

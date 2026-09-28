r"""The Sum of All Fears (PC) -- the same Ike engine as Ghost Recon.

Delivery is MOD, through the same `Mods\<name>\` overlay. The data is arranged
slightly differently -- there is an `Outfits\` tree and an `Attachments\` tree
Ghost Recon has no equivalent of -- which is also what tells the two installs
apart.

**What Sum of All Fears has and Ghost Recon does not is a real difficulty
model.** Its `CmbtModl.xml` carries eleven extra tags that scale friendly and
enemy competence separately per difficulty tier, plus four armour factors.
None of those eleven exists in `GhostRecon.exe`, so this is the one game on the
shelf where "make Recruit easier" and "make Elite harder" are single numbers
rather than a sweep over hundreds of actor files.
"""

import os

from . import _rse, _soaf_npc
from ..model import (CHOICE, Choice, GameProfile, Layout, MOD, Setting,
                     XmlText)

LAYOUT = Layout(
    signature=[
        "Mods/Origmiss/ModsCont.txt",
        "Mods/Origmiss/Outfits/*",
        "Data/Shell/Art/soaf_command_bkgrnd.rsb",
    ],
    exe="SOAF.exe",
    mods_dir="Mods",
    base_mod="Mods/Origmiss",
    data_dir="Data",
)

COMBAT_MODEL = _rse.COMBAT_MODEL

EXTRA = [
    Setting(
        "difficulty_curve", "Difficulty tiers", CHOICE, "stock",
        group="Difficulty",
        help="Sum of All Fears scales the two sides separately per tier. "
             "Stock, Recruit gives your squad +2 skill and takes 3 off the "
             "enemy, lets enemies aim 35% worse and react 25% slower; Elite "
             "reverses it. This widens or narrows that spread without "
             "touching a single actor file.",
        choices=[
            Choice("stock", "Stock", "Recruit +2/-3, Elite -2/+2."),
            Choice("wide", "Wider spread",
                   "Recruit gentler still and Elite harsher, so the tiers "
                   "feel further apart."),
            Choice("flat", "Flat",
                   "Every tier the same: no skill adjustment, and no aim or "
                   "reaction handicap either way."),
            Choice("hard", "Everything harder",
                   "Elite's handicaps applied across the board."),
        ],
        confidence="experimental", touches="mod"),
    Setting(
        "armour_value", "How much body armour helps", CHOICE, "stock",
        group="Lethality",
        help="Four factors, one per armour level, applied to chest hits. "
             "Higher means the armour absorbs more. Level 0 is 0 -- no "
             "armour, no protection -- and level 3 is 550.",
        choices=[
            Choice("stock", "Stock", "0 / 150 / 350 / 550."),
            Choice("x1.7", "Armour matters more",
                   "Closer to the 400 / 750 / 950 a heavy-realism mod uses."),
            Choice("x0.5", "Armour matters less", ""),
            Choice("none", "Armour does nothing", "All four at zero."),
        ],
        confidence="experimental", touches="mod"),
    Setting(
        "recruit_shield", "How much Recruit protects your squad", CHOICE,
        "stock", group="Difficulty",
        help="The combat model carries a separate multiplier on the chance "
             "of one of YOUR people being killed, used on the Recruit tier "
             "only. Stock halves it. It is the one part of the difficulty "
             "model that protects your squad rather than handicapping the "
             "enemy, and the difficulty-tier option above does not touch it.",
        choices=[
            Choice("stock", "Stock", "Half the usual chance, on Recruit."),
            Choice("x0.5", "Recruit protects them more", "A quarter."),
            Choice("x2", "Recruit protects them less",
                   "Back to the same chance as every other tier."),
        ],
        confidence="experimental", touches="mod"),
    Setting(
        "arcade_lethality", "Arcade mode lethality", CHOICE, "stock",
        group="Difficulty",
        help="A multiplier on every kill chance, applied in arcade mode. "
             "Stock halves it. Does nothing outside arcade mode.",
        choices=[
            Choice("stock", "Stock", "Half."),
            Choice("x0.5", "Gentler still", ""),
            Choice("x2", "As lethal as the normal game", ""),
        ],
        confidence="experimental", touches="mod"),
]

SETTINGS = _rse.shared_settings("soaf") + _soaf_npc.settings() + EXTRA

#: The eleven difficulty tags do NOT all move the same way, which is why this
#: is a table of explicit values rather than a multiplier:
#:
#:   *SkillAdjustment  is ADDED to an actor's skill rung, so more is better
#:                     for whichever side it names.
#:   *AimFactor        multiplies a dispersion, so ABOVE one is worse aim.
#:   *DelayFactor      multiplies a reaction time, so ABOVE one is slower.
#:
#: Reading those three as one "difficulty" number would have made the enemy
#: sharper and slower at the same time.
CURVE = {
    "wide": {
        "RecruitFriendlySkillAdjustment": 3, "RecruitEnemySkillAdjustment": -4,
        "EliteFriendlySkillAdjustment": -3, "EliteEnemySkillAdjustment": 3,
        "RecruitEnemyDelayFactor": "1.500000",
        "EliteEnemyDelayFactor": "0.600000",
        "RecruitEnemyAimFactor": "1.600000",
        "EliteEnemyAimFactor": "0.600000",
    },
    "flat": {
        "RecruitFriendlySkillAdjustment": 0, "RecruitEnemySkillAdjustment": 0,
        "EliteFriendlySkillAdjustment": 0, "EliteEnemySkillAdjustment": 0,
        "RecruitEnemyDelayFactor": "1.000000",
        "VeteranEnemyDelayFactor": "1.000000",
        "EliteEnemyDelayFactor": "1.000000",
        "RecruitEnemyAimFactor": "1.000000",
        "EliteEnemyAimFactor": "1.000000",
    },
    "hard": {
        "RecruitFriendlySkillAdjustment": 0, "RecruitEnemySkillAdjustment": 2,
        "EliteFriendlySkillAdjustment": -2, "EliteEnemySkillAdjustment": 2,
        "RecruitEnemyDelayFactor": "0.750000",
        "VeteranEnemyDelayFactor": "0.750000",
        "EliteEnemyDelayFactor": "0.750000",
        "RecruitEnemyAimFactor": "0.750000",
        "EliteEnemyAimFactor": "0.750000",
    },
}

ARMOUR_FACTORS = ["BallisticArmoredChestFactor%d" % i for i in range(4)]


def build_edits(values, root=None):
    out = _rse.shared_edits(values, "soaf")
    v = values

    if v.get("npc_weapons") and root:
        # Once the enemy carries its own copies, the Weapons page above is the
        # PLAYER's set, so it must stop reaching them: `Equip/*.gun` matches
        # `m16_npc.gun` perfectly well.
        for edit in out:
            if edit.select == _soaf_npc.EQUIP_GUNS and not edit.scope:
                edit.scope = "not:*%s.gun" % _soaf_npc.NPC_SUFFIX
        out += _soaf_npc.edits(
            v, os.path.join(str(root), LAYOUT.base_mod.replace("/", os.sep)))

    curve = CURVE.get(v["difficulty_curve"])
    if curve:
        for tag, value in curve.items():
            out.append(XmlText(COMBAT_MODEL, path=tag, value=value,
                               note="difficulty: " + tag))

    armour = v["armour_value"]
    if armour == "none":
        for tag in ARMOUR_FACTORS:
            out.append(XmlText(COMBAT_MODEL, path=tag, value="0.000000",
                               note="armour value"))
    elif armour in ("x1.7", "x0.5"):
        factor = 1.7 if armour == "x1.7" else 0.5
        for tag in ARMOUR_FACTORS:
            out.append(XmlText(COMBAT_MODEL, path=tag, scale=factor,
                               minimum=0, note="armour value"))
    for key, tag in (("recruit_shield", "RecruitFriendlyKillChanceFactor"),
                     ("arcade_lethality", "ArcadeModeKillChanceFactor")):
        factor = {"x0.5": 0.5, "x2": 2.0}.get(v[key])
        if factor:
            out.append(XmlText(COMBAT_MODEL, path=tag, scale=factor,
                               minimum=0, maximum=1, note=tag))
    return out


def combination_warnings(values):
    out = []
    if values["lethality"] == "brutal" and values["armour_value"] == "none":
        out.append("Quarter-lethality with armour switched off makes a chest "
                   "hit fatal for everyone, including you.")
    if values["difficulty_curve"] == "hard" and values["enemy_skill"] == "elite":
        out.append("The difficulty curve and the actor skill rungs push the "
                   "same quantity from two directions. Together they are two "
                   "handicaps, not one.")
    return out


NOTES = r"""
Sum of All Fears runs Ghost Recon's engine, and this tool mods it the same way:
by building a sparse mod folder under Mods\ that shadows Mods\Origmiss. The
game's own Mods menu turns it on and off, and nothing retail is written.

The difference worth knowing is that this game has a real difficulty model and
Ghost Recon does not. Eleven tags in Equip\CmbtModl.xml scale the two sides
separately per tier: stock Recruit gives your squad +2 skill and takes 3 off
the enemy, makes enemies aim 35% worse and react 25% slower, and Elite reverses
it. Those eleven tag names appear nowhere in GhostRecon.exe, so this page
exists here and not there.

The three kinds of tag do not move the same way, which is worth knowing if you
ever edit the file by hand: a SkillAdjustment is ADDED to a skill rung, an
AimFactor MULTIPLIES a dispersion so above 1 is worse aim, and a DelayFactor
multiplies a reaction time so above 1 is slower. Treating all three as one
"difficulty" number makes the enemy sharper and slower at the same time.

Enemies are NOT told from your own people by where the file sits, and assuming
so was a bug this profile shipped. Your squad is in Actor\Team Members\, but
49 of the 448 actors loose in Actor\ are friendly too -- eleven support teams
and a hostage -- so every "tougher enemies" option was buffing them. An enemy
here is an actor with NO <KitPath>: a kit path means it was equipped out of
your own kit folders. The enemies' names being tokens rather than names --
@SOLDIERNAME on 143 of them, @MILITIANAME on 67 -- is a second, independent
way to tell the two apart.

Separating your weapons from theirs. "Give the enemy its own weapons" on the
Enemies page does it, and it needs a different mechanism from Ghost Recon's
because this game keeps no enemy kit folder. 239 enemy placements wear
Kits\mercenaries\ kits, which are shadowed in place; 176 wear multi_NN
loadouts out of Kits	eam\, which is also where YOUR loadouts live -- so
those are copied to Kits\mercenaries\multi_NN_npc.kit and the campaign
missions are rewritten to name the copies. That rewrite is safe as a plain
rename because, measured across all 25 missions, not one allied placement
wears a borrowed loadout. It matters more here than in Ghost Recon: the two
sides share nineteen of the twenty-two guns the enemy carries, against five
there. See _soaf_npc.py.

Nothing in this profile has been watched working in a running game.
"""

PROFILE = GameProfile(
    id="soaf",
    title="Tom Clancy's The Sum of All Fears",
    short="Sum of All Fears",
    layout=LAYOUT,
    delivery=MOD,
    settings=SETTINGS,
    build_edits=build_edits,
    combination_warnings=combination_warnings,
    mod_name="ModStudio",
    mod_blurb="Mod Studio",
    notes=NOTES,
)

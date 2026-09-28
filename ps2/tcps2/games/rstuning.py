"""The difficulty levers the three Red Storm discs share.

Ghost Recon, Jungle Storm and Sum of All Fears run the same engine and keep the
same two things in the same two places:

**Marksmanship is one integer per template.** An `.ATR` file carries five
single-digit skills -- `ArmorLevel`, `Weapon`, `Stamina`, `Stealth`,
`Leadership` -- and `Weapon` is the one that decides whether a shot lands. The
existing "extra enemy skill" dial moves all five together, which is blunt: it
makes an enemy tougher, sneakier and better led as well as more accurate. The
accuracy card here moves `Weapon` alone, so "they shoot straighter" can be
asked for without anything else changing. The two compose, and the clamp at 1-8
means a value cannot run away.

**Lethality is one small XML file.** `CMBTMODL.XML` holds the whole hit model as
named floats -- a factor per body part, plus four for armour levels. The
direction is now settled by disassembly rather than inference: Ghost Recon's
boot ELF ships a full symbol table, and `CombatModelFile::GetKillChance` at
`0x003d4ae0` computes

    killChance = 1.0 - (BallisticXFactor / penetrationEnergy)

so a factor is a **resistance threshold in energy units, a divisor** -- higher
absorbs more, lower means people die faster. That is why the head sits at 10
and the lower arm at 1000, and why `ArmoredChestFactor0` may legally be 0: it
is only ever the numerator.

That same disassembly settles the side question. There is one
`CombatModelFile` instance, and `GetKillChance` has exactly two callers --
`SimHuman::TakeGunshotDamage` and `SimHuman::TakeExplosionDamage`, which are
every human on the map. On Ghost Recon and Jungle Storm this is symmetric, and
calling it an "enemy toughness" slider would be false. The card says so.

**Sum of All Fears is the exception, and it is a large one.** Its
`CMBTMODL.XML` is version 1.1 and carries twelve fields the Ghost Recons'
parser does not even have names for -- per-side, per-difficulty enemy aim
error, reaction delay and skill adjustment. Those are real enemy-only dials and
they get their own cards on that disc. (Its heaviest armour factor is 550 where
the Ghost Recons ship 750, so everything here scales what the disc actually has
rather than writing absolutes.)

**Both copies matter.** Ghost Recon ships `CMBTMODL.XML` in `GR.IMG` *and*
`MENU.IMG`; Sum of All Fears in `SOAF.IMG` *and* `MENU.IMG`. Jungle Storm has
one. Edits are therefore not pinned to a single archive -- pin them and the
menu and the simulation disagree.
"""

from __future__ import annotations

from ..model import CHOICE, INT, Choice, FileEdit, Setting

#: what `CMBTMODL.XML` ships, for reference. Read off all three discs; the tool
#: scales whatever it finds rather than trusting this table.
STOCK_BALLISTICS = {
    "BallisticHeadFactor": 10.0,
    "BallisticChestFactor": 100.0,
    "BallisticArmoredChestFactor0": 0.0,
    "BallisticArmoredChestFactor1": 150.0,
    "BallisticArmoredChestFactor2": 350.0,
    "BallisticArmoredChestFactor3": 750.0,        # 550 on Sum of All Fears
    "BallisticAbdomenFactor": 400.0,
    "BallisticUpperArmFactor": 700.0,
    "BallisticLowerArmFactor": 1000.0,
    "BallisticUpperLegFactor": 500.0,
    "BallisticLowerLegFactor": 800.0,
}

LETHALITY = {
    "stock": 1.0,
    "much_deadlier": 0.25,
    "deadlier": 0.5,
    "tougher": 1.5,
    "much_tougher": 2.5,
}


def accuracy_card(prefix, group="Enemies"):
    return Setting(
        prefix + "accuracy", "Extra enemy marksmanship", INT, 0, group,
        minimum=0, maximum=7, unit="points", confidence="applied",
        touches="data",
        help="Every enemy template carries five single-digit skills, and "
             "`Weapon` is the one that decides whether a shot lands. This adds "
             "to that one alone, so enemies shoot straighter without also "
             "becoming tougher, sneakier or better led. Only templates used by "
             "non-allied companies are touched, so your own side is left "
             "alone.",
        caution="It stacks with the extra-skill dial, which moves all five "
                "including this one. Values are clamped to 1-8, so asking for "
                "more than the scale holds simply stops at the top.")


#: what the spotting radius is scaled by, as a percentage of the level's own
SPOT_HELP = (
    "Every level carries its own `MaxSpot` -- the distance inside which the AI "
    "can notice you -- and across the campaign they run from 48 to 125. This "
    "scales each level's own number rather than flattening them all to one "
    "value, so the close maps stay close and the open ones stay open.")


def spotting_card(prefix, group="Enemies"):
    return Setting(
        prefix + "spot", "How far enemies can see you", INT, 100, group,
        minimum=40, maximum=250, unit="%", confidence="applied",
        touches="data",
        help=SPOT_HELP,
        caution="This is the AI's vision, not yours, and it is read once when "
                "a level loads -- so it takes effect from the next mission "
                "start. A level whose own number is two digits cannot be "
                "pushed past 99, because not every .ENV is stored "
                "uncompressed and the compressed ones cannot grow by a byte; "
                "those levels stop there instead of being skipped.")


def lethality_card(prefix, group="Enemies"):
    return Setting(
        prefix + "lethality", "How much punishment a body takes", CHOICE,
        "stock", group, confidence="applied", touches="data",
        choices=[
            Choice("stock", "Stock", ""),
            Choice("deadlier", "Half -- people die twice as fast", ""),
            Choice("much_deadlier", "A quarter -- one or two hits",
                   "Close to a realism mod. It cuts both ways."),
            Choice("tougher", "Half again", ""),
            Choice("much_tougher", "Two and a half times",
                   "Long firefights, and armour really matters."),
        ],
        help="CMBTMODL.XML holds the whole hit model as a resistance factor "
             "per body part -- head 10, chest 100, abdomen 400, lower arm "
             "1000 -- plus four for armour levels, which run 0 for none up to "
             "750 for the heaviest. Higher absorbs more. This scales every one "
             "of them together.",
        caution="The file has no side in it: one model, everyone. Making "
                "gunfire deadlier makes it deadlier for you and your squad "
                "too, which is usually the point but is worth knowing.")


def cards(prefix, group="Enemies"):
    return [accuracy_card(prefix, group), lethality_card(prefix, group),
            spotting_card(prefix, group)]


# ---------------------------------------------------------------------------
# Sum of All Fears only: the version 1.1 combat model
# ---------------------------------------------------------------------------
#
# These twelve fields exist on no other disc here. The Ghost Recons' parser has
# no name for them at all, so they are not a shared idea with a different
# value -- they are a later revision of the format.
#
# Direction is inferred from the shipped numbers rather than from code: Recruit
# gets the HIGHER aim and delay factor (1.25) and Elite the lower (0.75), so
# these are error and hesitation terms where a bigger number is a worse enemy.
# The naming is internally consistent with that reading, but Sum of All Fears'
# executable is stripped and the arithmetic was not disassembled -- which is
# why these cards are marked untested rather than measured.

SOAF_AIM = {
    "stock": ("1.250000", "0.750000"),
    "sharp": ("0.900000", "0.500000"),
    "deadly": ("0.600000", "0.300000"),
    "loose": ("1.800000", "1.200000"),
}
SOAF_DELAY = {
    "stock": ("1.250000", "1.050000", "0.750000"),
    "quick": ("0.900000", "0.750000", "0.500000"),
    "instant": ("0.400000", "0.300000", "0.200000"),
    "slow": ("1.800000", "1.500000", "1.100000"),
}
#: (RecruitEnemySkillAdjustment, EliteEnemySkillAdjustment). The Recruit field
#: is two characters wide and the Elite field ONE, so the Elite value can never
#: be negative -- there is no room for the sign. Every option below fits.
SOAF_SKILL_ADJ = {
    "stock": ("-2", "2"),
    "up": ("+1", "5"),
    "max": ("+4", "9"),
    "down": ("-6", "0"),
}


def soaf_cards(group="Enemies"):
    return [
        Setting("soaf_enemy_aim", "Enemy aim error by difficulty", CHOICE,
                "stock", group, confidence="experimental", touches="data",
                choices=[
                    Choice("stock", "Stock (Recruit 1.25, Elite 0.75)", ""),
                    Choice("sharp", "Sharper (0.90 / 0.50)", ""),
                    Choice("deadly", "Much sharper (0.60 / 0.30)",
                           "Elite becomes genuinely unpleasant."),
                    Choice("loose", "Looser (1.80 / 1.20)", ""),
                ],
                help="This disc's combat model is version 1.1 and carries "
                     "per-difficulty enemy factors the Ghost Recons do not "
                     "have. Recruit ships the higher number and Elite the "
                     "lower, so this is aiming ERROR: smaller is a better shot.",
                caution="Read off the field names and the shipped numbers, not "
                        "from code -- this executable is stripped. The "
                        "direction is a confident reading, not a measured one."),
        Setting("soaf_enemy_delay", "Enemy reaction delay by difficulty",
                CHOICE, "stock", group, confidence="experimental",
                touches="data",
                choices=[
                    Choice("stock", "Stock (1.25 / 1.05 / 0.75)", ""),
                    Choice("quick", "Quicker (0.90 / 0.75 / 0.50)", ""),
                    Choice("instant", "Almost none (0.40 / 0.30 / 0.20)", ""),
                    Choice("slow", "Slower (1.80 / 1.50 / 1.10)", ""),
                ],
                help="The same block's Recruit, Veteran and Elite delay "
                     "factors, scaled together. Lower means they open fire "
                     "sooner after noticing you.",
                caution="Same caveat as the aim factors: inferred from the "
                        "names and the shipped ladder, not disassembled."),
        Setting("soaf_enemy_skill_adj", "Enemy skill step by difficulty",
                CHOICE, "stock", group, confidence="experimental",
                touches="data",
                choices=[
                    Choice("stock", "Stock (Recruit -2, Elite +2)", ""),
                    Choice("up", "Harder (+1 / +5)", ""),
                    Choice("max", "Hardest (+4 / +9)",
                           "Recruit stops being a soft option at all."),
                    Choice("down", "Easier (-6 / 0)", ""),
                ],
                help="An integer added to every enemy's skill, chosen by "
                     "difficulty. It sits beside a matching pair for your own "
                     "side, which this does not touch.",
                caution="The Elite field is ONE character wide in the file, so "
                        "it can never be negative -- there is no room for a "
                        "minus sign. The options above all fit."),
    ]


def edits(prefix, v, archive):
    """The FileEdits these two cards imply for one disc."""
    out = []
    acc = int(v.get(prefix + "accuracy", 0))
    if acc:
        out.append(FileEdit(
            "bump_stats", r"\.ATR$", archive,
            {"steps": acc, "stats": ["Weapon"]},
            "+%d marksmanship on every hostile template" % acc,
            scope="enemy_templates"))
    level = v.get(prefix + "lethality", "stock")
    if level != "stock":
        # NOT pinned to one archive: Ghost Recon and Sum of All Fears each ship
        # this file twice and both copies have to agree.
        out.append(FileEdit(
            "scale_ballistics", r"/CMBTMODL\.XML$", "",
            {"factor": LETHALITY[level]},
            "hit resistance scaled to %gx" % LETHALITY[level]))
    spot = int(v.get(prefix + "spot", 100))
    if spot != 100:
        out.append(FileEdit(
            "scale_xml", r"\.ENV$", archive,
            {"factor": spot / 100.0, "prefix": "MaxSpot"},
            "AI spotting distance at %d%% of each level's own" % spot))
    return out


def soaf_edits(v):
    """The version 1.1 fields, on the one disc that has them."""
    values = {}
    aim = v.get("soaf_enemy_aim", "stock")
    if aim != "stock":
        rec, eli = SOAF_AIM[aim]
        values["RecruitEnemyAimFactor"] = rec
        values["EliteEnemyAimFactor"] = eli
    delay = v.get("soaf_enemy_delay", "stock")
    if delay != "stock":
        rec, vet, eli = SOAF_DELAY[delay]
        values["RecruitEnemyDelayFactor"] = rec
        values["VeteranEnemyDelayFactor"] = vet
        values["EliteEnemyDelayFactor"] = eli
    adj = v.get("soaf_enemy_skill_adj", "stock")
    if adj != "stock":
        rec, eli = SOAF_SKILL_ADJ[adj]
        values["RecruitEnemySkillAdjustment"] = rec
        values["EliteEnemySkillAdjustment"] = eli
    if not values:
        return []
    return [FileEdit("xml_values", r"/CMBTMODL\.XML$", "", {"values": values},
                     "per-difficulty enemy factors")]

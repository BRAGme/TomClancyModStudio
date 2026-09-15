"""The difficulty levers the three Red Storm discs share.

Ghost Recon, Island Thunder, Ghost Recon 2 and Summit Strike run the same
engine and keep the same two things in the same two places:

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

**The Xbox numbers are not the PS2 numbers.** These discs ship a chest factor
of 300 where the PS2 discs ship 100, and a lower arm of 1500 against 1000, so
everything here scales what the folder actually holds rather than writing
absolutes read off another platform.

**Both copies matter.** Ghost Recon 2 and Summit Strike ship `CMBTMODL.XML`
loose under equip/ *and* inside globs/ikedata.glb. The selector is
deliberately not anchored to one of them: pin it and the two copies disagree.
"""

from __future__ import annotations

from ..model import CHOICE, INT, Choice, FileEdit, Setting

#: what `CMBTMODL.XML` ships, for reference. Read off all three discs; the tool
#: scales whatever it finds rather than trusting this table.
STOCK_BALLISTICS = {
    "BallisticHeadFactor": 10.0,
    "BallisticChestFactor": 300.0,
    "BallisticArmoredChestFactor0": 0.0,
    "BallisticArmoredChestFactor1": 150.0,
    "BallisticArmoredChestFactor2": 350.0,
    "BallisticArmoredChestFactor3": 500.0,
    "BallisticAbdomenFactor": 600.0,
    "BallisticUpperArmFactor": 1000.0,
    "BallisticLowerArmFactor": 1500.0,
    "BallisticUpperLegFactor": 800.0,
    "BallisticLowerLegFactor": 1200.0,
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
        "stock", group, confidence="applied",         choices=[
            Choice("stock", "Stock", ""),
            Choice("deadlier", "Half -- people die twice as fast", ""),
            Choice("much_deadlier", "A quarter -- one or two hits",
                   "Close to a realism mod. It cuts both ways."),
            Choice("tougher", "Half again", ""),
            Choice("much_tougher", "Two and a half times",
                   "Long firefights, and armour really matters."),
        ],
        help="CMBTMODL.XML holds the whole hit model as a resistance factor "
             "per body part -- head 10, chest 300, abdomen 600, lower arm "
             "1500 -- plus four for armour levels, which run 0 for none up to "
             "500 for the heaviest. Higher absorbs more. This scales every one "
             "of them together.",
        caution="The file has no side in it: one model, everyone. Making "
                "gunfire deadlier makes it deadlier for you and your squad "
                "too, which is usually the point but is worth knowing.")


def cards(prefix, group="Enemies"):
    return [accuracy_card(prefix, group), lethality_card(prefix, group),
            spotting_card(prefix, group)]


def edits(prefix, v):
    """The FileEdits these two cards imply for one disc."""
    out = []
    acc = int(v.get(prefix + "accuracy", 0))
    if acc:
        out.append(FileEdit(
            "bump_stats", r"\.ATR$",
            {"steps": acc, "stats": ["Weapon"]},
            "+%d marksmanship on every hostile template" % acc,
            scope="enemy_templates"))
    level = v.get(prefix + "lethality", "stock")
    if level != "stock":
        # NOT anchored to one copy: Ghost Recon 2 and Summit Strike each ship
        # this file twice, loose and packed, and both have to agree.
        out.append(FileEdit(
            "scale_ballistics", r"CMBTMODL\.XML$",
            {"factor": LETHALITY[level]},
            "hit resistance scaled to %gx" % LETHALITY[level]))
    spot = int(v.get(prefix + "spot", 100))
    if spot != 100:
        out.append(FileEdit(
            "scale_xml", r"\.ENV$",
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

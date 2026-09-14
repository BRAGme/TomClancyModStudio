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
direction is not a guess: `BallisticArmoredChestFactor0` is 0 for no armour and
rises to 750 for the heaviest, and a *damage multiplier* that was zero without
armour would make an unarmoured chest invulnerable. So the factors are
resistance -- **higher absorbs more, lower means people die faster** -- which is
also why the head sits at 10 and the lower arm at 1000.

The file has no side attribute anywhere in it: one `<CombatModelFile>`, one set
of factors. It therefore applies to everybody, the player and his squad
included, and the card says so rather than pretending to be an enemy dial.

Sum of All Fears is not quite identical -- its heaviest armour factor is 550
where the two Ghost Recons ship 750 -- so everything here scales what the disc
actually has rather than writing absolute numbers.
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
        minimum=0, maximum=4, unit="points", confidence="applied",
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
    return [accuracy_card(prefix, group), lethality_card(prefix, group)]


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
        out.append(FileEdit(
            "scale_ballistics", r"/CMBTMODL\.XML$", archive,
            {"factor": LETHALITY[level]},
            "hit resistance scaled to %gx" % LETHALITY[level]))
    return out

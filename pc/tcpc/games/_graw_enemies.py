r"""Advanced Warfighter's enemy levers: how many, how good, how tough.

Three files carry the whole of it, and each needs a different kind of edit --
which is why this is its own module rather than more lines in `_graw.py`.

## How many: the count is encoded in a NAME

A world file does not place soldiers. It places SQUADS::

    <unit name="group_unit" group="mex_guerilla_patrol2" group_id="patrol01">

and the trailing digit is the squad's size. A group declared `split="true"` is
expanded by the group manager into sub-groups `<name>1` … `<name>N`, where N is
its full roster, and `<name>K` is that roster cut to K. So "more enemies" is
not a number to scale -- it is a RENAME, to a different string per placement,
and only the names the generator makes exist.

That is what `XmlAttr.remap` is for. `SQUAD_SIZE` below is the roster of every
enemy squad template, read out of each game's own compiled `group_manager`
(the compiled copy, because GRAW 2 generates most of its groups from macros and
only the compiled form has them expanded). From it the profile builds a map
`mex_guerilla_patrol2` -> `mex_guerilla_patrol4`, and nothing else is touched.

Checked against the shipped worlds before being trusted: across all 44 GRAW 1
world files, every suffixed reference resolves to a declared group and **not one
asks for a K larger than its roster**, so raising K to the roster stays inside
the range the game already uses. At full strength GRAW 1's first mission goes
from 45 enemies to 83, and the campaign from 1,053 to 2,600.

Friendly squads are named `friendly*`, `us_marines_*`, `loyalists*` and are not
in the table, so they cannot be caught by it.

## How good: a scale, and it runs BACKWARDS

`skill_shooting` lives on the soldier templates in `group_manager`. Every one
of the 34 in GRAW 1 and 132 in GRAW 2 belongs to a `mex_*` or `ag_*` soldier --
checked by walking the tree and reading each node's owning `<soldier>` -- so
scaling all of them cannot reach the player's squad.

**A LOWER value is a BETTER shot.** This shipped inverted and the game's own
data is what settles it. Reading the compiled `group_manager`:

    GRAW 1   mex_carlos (the named boss)   0.30      <- best
             mex_sf_*  (special forces)    0.85
             mex_inf_* (regular infantry)  1.00
             mex_gue_* (guerillas)         1.20      <- worst

    GRAW 2   mex_sf_leader_01..04 and their ag_ twins   2.0   <- best
             every one of the other 124 soldiers        2.5

In both games the units the campaign treats as elite carry the lowest number
and the rabble carry the highest, so it is a spread multiplier and not a skill
rating. "Sharper" therefore scales it DOWN.

## How tough: a remap again, to miss the corpses

`damage_points` is health. GRAW 1's living enemies are 4 (with two special NPCs
at 8) and GRAW 1's HUSKS -- the bodies left behind -- are 16, in the same files.
A blanket scale would make corpses harder to shoot to pieces, so this remaps
only the living values and leaves 16 alone.
"""

from ..model import CHOICE, Choice, Setting, XmlAttr

WORLDS = "data/levels/*/xml/world.xml"
GROUPS = "data/lib/managers/xml/group_manager.xml"
GLOBAL = "data/sb_templates/global/sb_global.xml"
SETTINGS_FILE = "data/sb_templates/sb_settings.xml"
ENEMY_UNITS = "data/units/beings/u_mex*.xml"


def settings(game_id="graw"):
    return [
        Setting(
            "enemy_squads", "Enemies per squad", CHOICE, "stock",
            group="Enemies",
            help="Every enemy placement in the campaign names a squad, and the "
                 "squad's size is the digit on the end of that name. This "
                 "rewrites those names. It changes how many enemies spawn "
                 "without moving anybody: the positions, patrol routes and "
                 "mission triggers are all untouched.",
            caution="Full strength is a bigger change than it sounds, and it "
                    "is much bigger in the sequel: Advanced Warfighter's first "
                    "mission goes from 45 enemies to 83, and Advanced "
                    "Warfighter 2's from 46 to 212, because its patrol squads "
                    "hold eight men where the first game's hold four.",
            choices=[
                Choice("stock", "Stock", "As the missions were authored."),
                Choice("full", "Full-strength squads",
                       "Every squad at its complete roster -- the largest size "
                       "the game itself ever asks for."),
                Choice("thin", "Half-strength squads",
                       "Every squad cut to half its placed size, floor of one."),
            ],
            confidence="experimental", touches="data"),
        Setting(
            "enemy_skill", "Enemy marksmanship", CHOICE, "stock",
            group="Enemies",
            help="The per-soldier shooting figure in the group manager. It is "
                 "a SPREAD, so the game's own elite units carry the lowest "
                 "numbers -- special forces 0.85 against guerillas 1.2 in the "
                 "first game, and the named boss lowest of all at 0.30. "
                 "Sharper scales it down. Every one of these belongs to an "
                 "enemy template, so your own squad is not affected.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("sharp", "Sharper", "Spread cut by a third."),
                Choice("elite", "Elite",
                       "Spread halved -- tighter than the game's own special "
                       "forces."),
                Choice("green", "Green", "Spread half again as wide."),
            ],
            confidence="experimental", touches="data"),
        Setting(
            "enemy_precision", "Global enemy accuracy", CHOICE, "stock",
            group="Enemies",
            help="A single multiplier the whole AI reads, sitting on top of "
                 "each soldier's own spread and each weapon's own.",
            choices=[
                Choice("stock", "Stock", "1.0."),
                Choice("x1.4", "Sharper", ""),
                Choice("x0.6", "Blunter", ""),
            ],
            enabled=False,
            disabled_reason=(
                "The value in the file is overwritten before it is ever used. "
                "`apply_difficulty_settings` assigns this variable a literal "
                "on every difficulty tier including Normal, and it runs every "
                "session -- at profile load in the first game, at network "
                "init in the second. Both games keep it in the same compiled "
                "script as that function and nowhere else, which is how it "
                "was caught. Shipped visible and off rather than quietly "
                "doing nothing; use Enemy marksmanship instead."),
            confidence="broken", touches="data"),
        Setting(
            "enemy_health", "Enemy toughness", CHOICE, "stock",
            group="Enemies",
            help="How much damage an enemy takes before dropping. Bodies left "
                 "behind have their own, much higher, value in the same files "
                 "and are deliberately not touched.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("x2", "Twice as tough", ""),
                Choice("x0.5", "Half as tough", ""),
                Choice("one_shot", "One shot", "Everything drops to 1."),
            ],
            confidence="experimental", touches="data"),
        Setting(
            "difficulty", "Difficulty the campaign starts on", CHOICE,
            "normal", group="Enemies",
            help="Both games ship three tiers and default to the middle one. "
                 "The tier TABLES are compiled into the scripts and are not "
                 "reachable from here, but which tier is the default is plain "
                 "data.",
            caution="On the easy tier the game also heals you to full at each "
                    "checkpoint, which the other two tiers do not do.",
            choices=[
                Choice("easy", "Easy", ""),
                Choice("normal", "Normal", "As shipped."),
                Choice("hard", "Hard", ""),
            ],
            confidence="experimental", touches="data"),
        Setting(
            "enemy_senses", "How far enemies see and hear", CHOICE, "stock",
            group="Enemies",
            help="Sight range, peripheral cone, the distance a gunshot "
                 "carries, and the radius inside which you are spotted "
                 "instantly. Stock sight is 150 m.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("keen", "Keener", "Half again as far."),
                Choice("dull", "Duller", "Two thirds."),
                Choice("blind", "Short-sighted",
                       "A third. Stealth becomes very forgiving."),
            ],
            enabled=(game_id == "graw"),
            disabled_reason=(
                "Advanced Warfighter 2 does not read these keys. The first "
                "game's AI detection script accesses `ad_distance_sight` and "
                "its siblings; the sequel's compiled scripts contain not one "
                "reference to any `ad_` key, and use a different family "
                "(`det_*`, 108 references) instead. The keys are still in the "
                "sequel's data, which is exactly why this looked like it "
                "worked."),
            confidence="experimental", touches="data"),
    ]


#: `ad_*` keys worth moving together, all in `sb_global` and all distances or
#: angles where bigger means the enemy notices you sooner.
#: how far each choice scales the spread. Down is sharper.
SKILL_SPREAD = {"sharp": 0.66, "elite": 0.5, "green": 1.5}

SENSES = ("ad_distance_sight", "ad_view_cone_outer", "ad_distance_hear_weapon_ls",
          "ad_distance_hear_weapon_nls", "ad_distance_hear_body_ls",
          "ad_distance_hear_body_nls", "ad_auto_detect_distance")


def edits(values, squad_size, health_values, health_attrs,
          game_id="graw"):
    """`squad_size` is {group name: roster}; `health_*` come from the profile."""
    out = []
    v = values

    # -- how many --------------------------------------------------------
    mode = v["enemy_squads"]
    if mode != "stock":
        table = {}
        for base, size in squad_size.items():
            for k in range(1, size + 1):
                if mode == "full":
                    want = size
                else:
                    want = max(1, k // 2)
                if want != k:
                    table["%s%d" % (base, k)] = "%s%d" % (base, want)
        if table:
            out.append(XmlAttr(WORLDS, path="unit[name=group_unit]",
                               attr="group", remap=table,
                               note="squad size"))

    # -- how good --------------------------------------------------------
    # Down is sharper: see the module docstring for the ladder this is read off.
    skill = SKILL_SPREAD.get(v["enemy_skill"])
    if skill:
        out.append(XmlAttr(GROUPS, path="var[name=skill_shooting]",
                           attr="value", scale=skill, minimum=0,
                           note="enemy marksmanship"))

    precision = {"x1.4": 1.4, "x0.6": 0.6}.get(v["enemy_precision"])
    if precision:
        out.append(XmlAttr(GLOBAL, path="var[name=overall_enemy_precision]",
                           attr="default", scale=precision, minimum=0,
                           stock="1.0", note="global enemy accuracy"))

    # -- how tough -------------------------------------------------------
    tough = v["enemy_health"]
    if tough != "stock":
        table = {}
        for raw in health_values:
            if tough == "one_shot":
                new = "1"
            else:
                factor = 2.0 if tough == "x2" else 0.5
                out_val = max(1.0, float(raw) * factor)
                new = ("%.2f" % out_val).rstrip("0").rstrip(".")
            if new != raw:
                table[raw] = new
        for attr in health_attrs:
            out.append(XmlAttr(ENEMY_UNITS, path="var[name=%s]" % attr,
                               attr="value", remap=dict(table),
                               note="enemy toughness"))

    # -- difficulty tier --------------------------------------------------
    if v["difficulty"] != "normal":
        out.append(XmlAttr(SETTINGS_FILE, path="var[name=difficulty]",
                           attr="default", value=v["difficulty"],
                           stock="normal", note="difficulty tier"))

    # -- senses ----------------------------------------------------------
    senses = {"keen": 1.5, "dull": 0.66, "blind": 0.33}.get(v["enemy_senses"])
    if senses:
        for key in SENSES:
            out.append(XmlAttr(GLOBAL, path="var[name=%s]" % key,
                               attr="default", scale=senses, minimum=1,
                               note="enemy senses: " + key))
    return out

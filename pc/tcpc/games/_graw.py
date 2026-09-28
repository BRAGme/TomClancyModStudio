r"""What Advanced Warfighter 1 and 2 have in common.

Both run GRIN's **Diesel** engine, which is nothing like the other five games
on the shelf. There is no loose data tree to edit and no mod folder to fill:
essentially the whole game lives in two `.bundle` archives of three to four
gigabytes each, 21,356 files in GRAW 1 and 25,052 in GRAW 2.

**Delivery is OVERLAY**, and the reason it works is a property of the engine:
Diesel looks a file up on disk before it looks in the archive. So the stock
value is read out of the bundle, the edited file is written loose in the
install where the archive's own path says it belongs, and the archives are
never opened for writing at all.

That is not a guess about how it *ought* to work. This Advanced Warfighter
installation already has 764 files under `Data\textures\...` dated 2023, which
shadow paths that are also inside `quick.bundle` and are ten times the size --
somebody's high-resolution texture replacements, working, by exactly this
mechanism.

**Reverting never deletes a folder.** `Data\` is shared with those
replacements, so the manifest records every path the tool created and every
path it had to write over, and restoring touches only those.

## The compiled twin

**Both games ship every data file twice, and the engine reads the COMPILED
copy.** `u_m416.xml` has a `u_m416.xmb` beside it (GRAW 1 uses `.xml.bin`), and
100% of the `.xml` in both bundles has such a twin. The proof is inside the
game: `quick.bundle` accidentally ships `temp_merged_log.xml`, a recorded
engine session with 9,508 `<open path="...">` records, and where both forms
exist it opened the compiled one 3,029 times and the source twice.

So editing the plain XML alone does NOTHING. Every option here writes the
source *and* its compiled twin, through `tcpc/xmlbin.py`, which round-trips all
5,674 GRAW 1 and 7,984 of 7,985 GRAW 2 compiled files byte-identically.

## The data

Diesel's gameplay files are plain, commented XML, and they are addressed
differently from anything else here. A weapon does not have elements named for
its fields; it has a flat list of name/value pairs::

    <stats block="weapon_data">
        <var name="clip_max"      value="30"/>
        <var name="spread_normal" value="1.87"/>   <!-- + mods affect this -->
        <var name="recoil_zoom"   value="0.8"/>
        <var name="fire_modes"    value="2"/>      <!-- 1=semi 2=+auto 3=+burst -->
    </stats>

which is why `rsexml` grew a predicate: `var[name=spread_normal]` selects the
element whose `name` says so.

**A weapon file usually defines several weapons.** `u_m8.xml` carries the
rifle, its grenade-launcher variant and the husk left behind when it is
dropped, each with its own `<var name="spread_normal">`. An edit writes all of
them and scales each from its own value, which is what "make every weapon
steadier" should mean.
"""

from ..model import CHOICE, Choice, INT, Setting, XmlAttr

WEAPONS = "data/units/weapons/*.xml"

#: The weapon fields worth a control, with what the game's own comments say
#: they do. Spread and recoil are separate numbers for hip fire and for the
#: zoomed/ironsight view, and they move together here because splitting them
#: would be four controls saying one thing.
SPREAD = ("spread_normal", "spread_zoom")
RECOIL = ("recoil_normal", "recoil_zoom")


def shared_settings():
    return [
        Setting(
            "weapon_spread", "Weapon spread", CHOICE, "stock", group="Weapons",
            help="How wide the cone is, hip-fired and zoomed. Each weapon "
                 "scales from its own numbers, so a rifle stays tighter than "
                 "a submachine gun. It applies to every weapon in the game, "
                 "which is every weapon the enemy carries too.",
            choices=[
                Choice("stock", "Stock", "A Scar L is 1.87 hip, 0.35 zoomed."),
                Choice("tight", "Tighter", "Halved."),
                Choice("laser", "Pinpoint", "A tenth."),
                Choice("loose", "Looser", "Doubled."),
            ],
            confidence="experimental", touches="data"),
        Setting(
            "weapon_recoil", "Recoil", CHOICE, "stock", group="Weapons",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("x0.5", "Halved", ""),
                Choice("none", "None", ""),
                Choice("x1.5", "Heavier", ""),
            ],
            confidence="experimental", touches="data"),
        Setting(
            "magazines", "Magazine capacity", CHOICE, "stock", group="Weapons",
            caution="Mounted guns and vehicle weapons are in the same files "
                    "and carry hundreds of rounds, so scaling them up is "
                    "large in absolute terms.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("x2", "Double", ""),
                Choice("x0.5", "Halved", ""),
            ],
            confidence="experimental", touches="data"),
        Setting(
            "fire_modes", "Unlock every fire mode", CHOICE, "stock",
            group="Weapons",
            help="The game's own comment reads: 1 = semi, 2 = semi+auto, "
                 "3 = semi+auto+burst. Most rifles ship at 2.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("all", "Semi, auto and burst on everything", ""),
            ],
            confidence="experimental", touches="data"),
        Setting(
            "rate_of_fire", "Rate of fire", CHOICE, "stock", group="Weapons",
            help="Stored as the seconds BETWEEN rounds, so a smaller number "
                 "is faster. The control is inverted to read the way you "
                 "would expect.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("fast", "Faster", "A third quicker."),
                Choice("slow", "Slower", "A third slower."),
            ],
            confidence="experimental", touches="data"),
        Setting(
            "weapon_side", "Who the weapon options apply to", CHOICE, "both",
            group="Weapons",
            help="Advanced Warfighter declares every weapon twice in the same "
                 "file -- one copy for whoever is holding it and a second, "
                 "suffixed _3rd, for everything the AI carries. The two ship "
                 "with identical numbers, so the options below have always "
                 "moved both. This picks a side.",
            caution="The AI side is EVERY AI, which is the enemy AND your own "
                    "squad -- the game splits on who is player-controlled, "
                    "not on which team you are. It is a player/AI split, not "
                    "a player/enemy one.",
            choices=[
                Choice("both", "Everyone", "As the options have always worked."),
                Choice("player", "Only the weapon in your hands", ""),
                Choice("ai", "Only weapons the AI carries",
                       "Enemies and your own squad."),
            ],
            confidence="experimental", touches="data"),
        Setting(
            "weapon_damage", "Weapon damage", CHOICE, "stock",
            group="Weapons",
            help="A per-weapon damage multiplier. It is one scale across the "
                 "whole game: a pistol and most rifles sit at 1 to 2.5, the "
                 "Barrett at 10, and the mounted .50 cals and the BMP's "
                 "autocannon at 11 to 15. Twenty-one of Advanced Warfighter's "
                 "weapon files declare it and thirty-two of the sequel's, so "
                 "a weapon that does not is left alone.",
            caution="Obeys 'Who the weapon options apply to' above, so it can "
                    "be aimed at the AI without changing the gun in your "
                    "hands -- or the other way round.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("x0.5", "Softer", "Halved."),
                Choice("x1.5", "Harder", ""),
                Choice("x2", "Lethal", "Doubled."),
            ],
            confidence="experimental", touches="data"),
    ]



#: Advanced Warfighter ships its own player/AI split and nothing in this tool
#: was using it. Every weapon is declared TWICE in the same file -- `scar_light`
#: and `scar_light_3rd` -- each with a complete `weapon_data` stats block, and
#: the shipped values are identical across all 22 GRAW 1 and 21 GRAW 2 pairs.
#: The inventory extension picks between them: a unit that is not
#: `player_controlled` gets the name with `_3rd` appended. Only 8 units in
#: GRAW 1 and 12 in GRAW 2 carry `player_controlled="true"`, and all of them
#: are the human's own body.
#:
#: So `_3rd` is EVERY AI -- the enemy AND your own squad. It is a player/AI
#: split, not a player/enemy one, and the option says so rather than implying
#: a separation the data does not make.
#:
#: The stats are at `unit/stats/var`, so reaching one side means a predicate on
#: an ANCESTOR segment, which is why `rsexml.find` and `xmlbin.select` grew
#: support for that.
UNIT_PLAYER = "unit[name!=*_3rd]"
UNIT_AI = "unit[name=*_3rd]"


def _aimed(side, tail):
    """The selector for one side of the split, or the flat one for both."""
    if side == "player":
        return UNIT_PLAYER + "/stats/" + tail
    if side == "ai":
        return UNIT_AI + "/stats/" + tail
    return tail


def shared_edits(values):
    out = []
    v = values
    side = v.get("weapon_side", "both")

    spread = {"tight": 0.5, "laser": 0.1, "loose": 2.0}.get(v["weapon_spread"])
    if spread:
        for name in SPREAD:
            out.append(XmlAttr(WEAPONS, path=_aimed(side, "var[name=%s]" % name),
                               attr="value", scale=spread, minimum=0,
                               note="weapon spread"))

    kick = {"x0.5": 0.5, "none": 0.0, "x1.5": 1.5}.get(v["weapon_recoil"])
    if kick is not None:
        for name in RECOIL:
            out.append(XmlAttr(WEAPONS, path=_aimed(side, "var[name=%s]" % name),
                               attr="value", scale=kick, minimum=0,
                               note="recoil"))

    mags = {"x2": 2.0, "x0.5": 0.5}.get(v["magazines"])
    if mags:
        out.append(XmlAttr(WEAPONS, path=_aimed(side, "var[name=clip_max]"), attr="value",
                           scale=mags, minimum=1, note="magazine capacity"))

    if v["fire_modes"] == "all":
        out.append(XmlAttr(WEAPONS, path=_aimed(side, "var[name=fire_modes]"), attr="value",
                           value="3", note="every fire mode"))

    rof = {"fast": 0.66, "slow": 1.5}.get(v["rate_of_fire"])
    if rof:
        for name in ("fire_rate_semi", "fire_rate_auto", "fire_rate_burst"):
            out.append(XmlAttr(WEAPONS, path=_aimed(side, "var[name=%s]" % name),
                               attr="value", scale=rof, minimum=0.01,
                               note="rate of fire"))
    dmg = {"x0.5": 0.5, "x1.5": 1.5, "x2": 2.0}.get(v["weapon_damage"])
    if dmg:
        out.append(XmlAttr(WEAPONS, path=_aimed(side, "var[name=damage]"),
                           attr="value", scale=dmg, minimum=0.01,
                           note="weapon damage"))
    return out

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
    ]


def shared_edits(values):
    out = []
    v = values

    spread = {"tight": 0.5, "laser": 0.1, "loose": 2.0}.get(v["weapon_spread"])
    if spread:
        for name in SPREAD:
            out.append(XmlAttr(WEAPONS, path="var[name=%s]" % name,
                               attr="value", scale=spread, minimum=0,
                               note="weapon spread"))

    kick = {"x0.5": 0.5, "none": 0.0, "x1.5": 1.5}.get(v["weapon_recoil"])
    if kick is not None:
        for name in RECOIL:
            out.append(XmlAttr(WEAPONS, path="var[name=%s]" % name,
                               attr="value", scale=kick, minimum=0,
                               note="recoil"))

    mags = {"x2": 2.0, "x0.5": 0.5}.get(v["magazines"])
    if mags:
        out.append(XmlAttr(WEAPONS, path="var[name=clip_max]", attr="value",
                           scale=mags, minimum=1, note="magazine capacity"))

    if v["fire_modes"] == "all":
        out.append(XmlAttr(WEAPONS, path="var[name=fire_modes]", attr="value",
                           value="3", note="every fire mode"))

    rof = {"fast": 0.66, "slow": 1.5}.get(v["rate_of_fire"])
    if rof:
        for name in ("fire_rate_semi", "fire_rate_auto", "fire_rate_burst"):
            out.append(XmlAttr(WEAPONS, path="var[name=%s]" % name,
                               attr="value", scale=rof, minimum=0.01,
                               note="rate of fire"))
    return out

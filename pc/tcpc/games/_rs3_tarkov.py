r"""Raven Shield with Escape from Tarkov's ballistics, handling and keys.

This is the half of "Tarkov in Raven Shield" that needs no compiler. The other
half -- the seven-zone limb model, bleeding, fractures and the medical kit --
cannot be configured into existence, because Raven Shield has one health
figure per pawn and no amount of ini editing adds six more. That part is
UnrealScript and lives in `mods\TarkovRvS\`. This file is what can be done to
the game as it ships, tonight, with the tool that is already here.

## The finding this module is built on

Raven Shield's damage term is bullet ENERGY and Tarkov's is WOUND DAMAGE, and
they do not have the same shape at all:

| | 9mm | 5.56 | 7.62x39 | 7.62x51 | 7.62x54R |
|---|---|---|---|---|---|
| Raven Shield `m_iEnergy` | 567 | 1442 | 1008 | 2547 | 4008 |
| Tarkov damage | 54 | 54 | 61 | 80 | 81 |

Raven Shield's spread across those five is **7.1x**. Tarkov's is **1.5x**.
That is not a balance disagreement, it is a units disagreement: muzzle energy
goes up with the square of velocity, and what a bullet does to a person does
not. It is why a rifle round in Raven Shield kills in one hit and a pistol
round sometimes does not, and why in Tarkov both take two hits to the chest.

So "Tarkov ballistics" is not "more damage" or "less damage". It is
**compressing the spread**, and the only sane direction to compress is
downward -- bring the rifles to the pistols rather than the pistols to the
rifles, or every round in the game one-shots and the limb model it is meant to
set up never gets a chance to matter.

Scaling everything to 10.5 energy per point of Tarkov damage (which is 9mm
Parabellum's own stock figure, 567 / 54) produces a second finding worth
stating plainly:

**Raven Shield's pistol and PDW calibres are already Tarkov-shaped.** 9mm
lands on 1.00, 9x21mm on 0.98, 5.7x28mm on 1.01, .45 ACP on 1.04 and 9x39mm
SP-6 on 0.97. Every one of them is inside five percent of where Tarkov would
put it, so this module emits no edit at all for them. What is out of shape is
the rifles -- 5.56 at 0.39, 7.62x51 at 0.33, 7.62x54R at 0.21 -- and the
shotgun, where buckshot is the one round in the game that is too *weak* by
Tarkov's reckoning, at 1.76.

## What this does NOT touch, and why

**`m_iPenetrationFactor`, in either direction.** `_rs3_ammo.py` worked out the
hard way that the field is a DIVISOR and that the shipped values are already
right; raising it makes a round worse, and lowering a hollow point's 4 hands
it the ball round's door-breaking budget. Tarkov's penetration-against-armour-
class model is the single most Tarkov thing there is and it is deliberately
absent here, because the lever that would express it is the wrong lever. It
belongs in the script mod, where armour can be read per hit.

**Enemy skill.** The brief was Raven Shield's own terrorist AI first, and this
module keeps it. The AI template options in the main profile are there if you
want to move it; nothing here presumes you do.

## Confidence

The Raven Shield figures are read out of the packages (`research/rs3_ammo.csv`,
197 weapon and 61 ammunition classes with byte offsets). Of the Tarkov figures
only five are confirmed against a published chart -- 9x19 Pst, 5.45 PS, 5.56
M855, 7.62x39 PS and BP, 7.62x51 M80 -- and the rest are marked INFERRED in
the table below. Tarkov is patched often enough that any of them may have
moved; each is one number in one table, which is the best that can be done
about that.
"""

from ..model import BOOL, CHOICE, Choice, IniEdit, PropEdit, Setting
from ._rs3_weapons import (AMMO_PACKAGES, POSTURES, RECOIL, WEAPON_PACKAGES,
                           _bar_edits)

USER_INI = "Save/Profiles/user.ini"

#: One row per Raven Shield calibre: the class-name glob, the stock energy of
#: its reference load, the Tarkov round it is being matched to, that round's
#: damage, and whether the Tarkov figure is confirmed.
#:
#: The glob catches every load of that calibre -- Normal, Subsonic, FMJ and
#: JHP -- and the edit is a SCALE, so the relationship between a calibre's
#: own loads survives. That matters more than it looks: `ammo545mm7N6` ships
#: its subsonic hollow point 12% hotter than its subsonic ball, the two
#: `ammo762x54mmR` loads ship their stagger figures reversed, and 7.62x39mm
#: ships no supersonic load at all. Scaling keeps all three oddities; setting
#: absolute values would erase them.
#:
#: Reference energies are from `research/rs3_ammo.csv`.
CALIBRES = (
    # glob,                      stock,  Tarkov load,          dmg, confirmed
    ("ammo9mmParabellum*",         567, "9x19mm Pst gzh",        54, True),
    ("ammo9x21mmR*",               591, "9x21mm PS gzh",         55, False),
    ("ammo9x39mm*",                705, "9x39mm SP-6",           65, False),
    ("ammo57x28mm*",               427, "5.7x28mm SS190",        41, False),
    ("ammo45calAuto*",             730, ".45 ACP AP",            72, False),
    ("ammo50calPistol*",          1769, ".50 AE FMJ",           110, False),
    ("ammo545mm7N6*",             1377, "5.45x39mm PS gs",       56, True),
    ("ammo556mmNATO*",            1442, "5.56x45mm M855",        54, True),
    ("ammo762mmM43*",             1008, "7.62x39mm PS",          61, True),
    ("ammo762mmNATO*",            2547, "7.62x51mm M80",         80, True),
    ("ammo762x54mmR*",            4008, "7.62x54mmR LPS",        81, False),
    ("ammo30calMagnum*",          5205, ".338 Lapua AP",        129, False),
    ("ammo50calM33*",             7500, ".338 Lapua AP",        129, False),
    ("ammo12gaugeSlug",           3175, "12/70 slug",           164, False),
    ("ammo12gaugeBuck",            298, "12/70 8.5mm buckshot",  50, False),
)

#: Energy per point of Tarkov damage. 9mm Parabellum's own stock figure, so
#: 9mm is the fixed point of the whole conversion and nothing in the game gets
#: *stronger* except buckshot.
ENERGY_PER_POINT = 567.0 / 54.0

#: Calibres with no Tarkov counterpart. Left at stock on purpose, and it works
#: out: stock .32 ACP (240), .40 S&W (584), 10mm (618) and .357 Magnum (922)
#: all land inside the 420-850 band the conversion puts everything else in, so
#: leaving them alone is not a gap. Iron Wrath's 4.6x30mm is here for the same
#: reason -- its real muzzle energy is within a few percent of 5.7x28mm, which
#: the conversion scores at 1.01.
UNMAPPED = ("7.65mm Auto (.32 ACP)", ".40 S&W", "10mm Auto", ".357 Magnum",
            "4.6x30mm (Iron Wrath)")

#: Below this much difference, emit nothing. Five percent of a damage figure
#: is not a change anybody can feel, and an edit that cannot be felt still
#: costs a package backup and a mismatch against a stock server.
DEADBAND = 0.05

#: How Tarkov holds a rifle: the muzzle climbs further, the sight takes longer
#: to settle, standing still is precise and moving is not. Four numbers, all
#: scales on the weapon's own stock figures so the difference between an M4 and
#: an RPD survives.
HANDLING = {
    "recoil": 1.60,         # fAccuracyChange + fWeaponJump
    "settle": 1.40,         # fReticuleTime
    "planted": 0.85,        # fBaseAccuracy, fShuffleAccuracy
    "moving": 1.50,         # fWalking, fWalkingFast, fRunningAccuracy
}

#: The two postures Tarkov rewards, and the three it punishes.
PLANTED = ("fBaseAccuracy", "fShuffleAccuracy")
MOVING = tuple(p for p in POSTURES if p not in PLANTED)

#: One key per medical item, and one to read the panel back. `auto` picks the
#: zone that most needs that item, which is what makes the model playable on
#: five keys instead of forty.
KEYBINDS = (
    ("F5", "TkBandage auto"),
    ("F6", "TkTourniquet auto"),
    ("F7", "TkSplint auto"),
    ("F8", "TkPills"),
    ("H", "TkStatus"),
)


def scale_for(stock, damage, strength):
    """What to multiply this calibre's energy by. `strength` of 1.0 is the
    whole conversion; 0.5 is the geometric midpoint, which is the honest way
    to express "halfway" for a multiplier -- an arithmetic midpoint between
    0.21 and 1.0 is not half as strong a change, it is a different one."""
    full = (damage * ENERGY_PER_POINT) / float(stock)
    if strength >= 1.0:
        return full
    return full ** strength


def settings():
    return [
        Setting(
            "tarkov_ballistics", "Tarkov ballistics", CHOICE, "stock",
            group="Tarkov",
            help="Raven Shield stores muzzle ENERGY and Tarkov stores what a "
                 "round does to a person, and the two have very different "
                 "shapes: across 9mm, 5.56, 7.62x39, 7.62x51 and 7.62x54R, "
                 "Raven Shield's figures span 7.1x and Tarkov's span 1.5x. "
                 "This compresses the spread onto Tarkov's, anchored on 9mm "
                 "so that nothing gets stronger except buckshot. Rifles come "
                 "down to roughly a third; every pistol and PDW calibre in "
                 "the game is already within five percent of where Tarkov "
                 "would put it and is left alone.",
            caution="This is the setup for a limb model, not a balance pass. "
                    "On its own it makes firefights longer without giving you "
                    "anywhere new to aim -- the seven-zone model that pays it "
                    "off is UnrealScript and lives in mods\\TarkovRvS. Of the "
                    "Tarkov figures behind the table, five are confirmed "
                    "against a published chart and ten are inferred. Like "
                    "every option in these two groups it is a binary patch of "
                    "the game's own packages: Revert puts every byte back, a "
                    "Steam file verification silently undoes it, and a server "
                    "on stock packages may refuse a client that has it.",
            choices=[
                Choice("stock", "Stock", "Raven Shield's own energy figures."),
                Choice("tarkov", "Tarkov's damage spread",
                       "Rifles to about a third, buckshot up three quarters, "
                       "pistols untouched."),
                Choice("half", "Halfway there",
                       "The geometric midpoint, for when a third feels like "
                       "too much at once."),
            ],
            # All three of these write m_iEnergy too, and the last one to run
            # would decide. Requiring them stock is the profile's own way of
            # saying "pick one".
            requires={"ammo_damage": "stock", "ammo_character": "stock"},
            confidence="experimental", touches="data"),
        Setting(
            "tarkov_handling", "Tarkov weapon handling", CHOICE, "stock",
            group="Tarkov",
            help="Heavier muzzle climb and a slower settle, standing still "
                 "made tighter and moving made much worse -- Tarkov rewards "
                 "being planted and punishes walking fire, and Raven Shield "
                 "ships the same four numbers to say so. Every figure is "
                 "scaled from the weapon's own, so an M4 and an RPD stay as "
                 "different as they were.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("tarkov", "Tarkov",
                       "Climb and settle up 60 and 40 percent, standing "
                       "spread down 15, moving spread up 50."),
            ],
            requires={"weapon_recoil": "stock", "weapon_accuracy": "stock",
                      "weapon_settle": "stock"},
            confidence="experimental", touches="data"),
        Setting(
            "tarkov_keybinds", "Bind the medical keys", BOOL, False,
            group="Tarkov",
            help="F5 bandage, F6 tourniquet, F7 splint, F8 painkillers, H "
                 "read the panel -- the console commands the script mod adds, "
                 "each on `auto` so one key treats whichever body part most "
                 "needs it.",
            caution="These do nothing until mods\\TarkovRvS is built and "
                    "installed; an unbuilt mod leaves you with five keys that "
                    "report an unknown command. Harmless, and it is why this "
                    "is off by default. Revert removes the lines.",
            confidence="experimental", touches="config"),
    ]


def edits(values):
    out = []
    v = values

    strength = {"tarkov": 1.0, "half": 0.5}.get(v["tarkov_ballistics"])
    if strength is not None:
        for glob, stock, load, damage, _confirmed in CALIBRES:
            factor = scale_for(stock, damage, strength)
            if abs(factor - 1.0) < DEADBAND:
                continue                # already where Tarkov would put it
            for pkg in AMMO_PACKAGES:
                out.append(PropEdit(
                    pkg, cls=glob, prop="m_iEnergy", scale=factor, minimum=1,
                    note="%s -> %s" % (glob.rstrip("*"), load)))

    if v["tarkov_handling"] == "tarkov":
        for pkg in WEAPON_PACKAGES:
            for prop in RECOIL:
                out.append(PropEdit(
                    pkg, prop="m_stAccuracyValues." + prop,
                    scale=HANDLING["recoil"], minimum=0,
                    note="Tarkov recoil: " + prop))
            out.append(PropEdit(
                pkg, prop="m_stAccuracyValues.fReticuleTime",
                scale=HANDLING["settle"], minimum=0,
                note="Tarkov settle time"))
            for prop in PLANTED:
                out.append(PropEdit(
                    pkg, prop="m_stAccuracyValues." + prop,
                    scale=HANDLING["planted"], minimum=0,
                    note="Tarkov planted accuracy: " + prop))
            for prop in MOVING:
                out.append(PropEdit(
                    pkg, prop="m_stAccuracyValues." + prop,
                    scale=HANDLING["moving"], minimum=0,
                    note="Tarkov moving accuracy: " + prop))

        # The loadout menu's bars are authored percentages that nothing
        # measures, so a retuned weapon keeps its old bars unless they are
        # rewritten. Recoil and settle moved by a single factor each and can
        # be mirrored exactly; accuracy moved two ways at once and cannot, so
        # it is left out rather than mirrored wrongly. Damage cannot be
        # mirrored at all -- `tarkov_ballistics` is per calibre and nothing
        # this tool reads maps a menu entry to the round it fires.
        if v.get("menu_bars"):
            out.extend(_bar_edits(None, HANDLING["recoil"], None,
                                  HANDLING["settle"]))

    if v["tarkov_keybinds"]:
        for key, command in KEYBINDS:
            out.append(IniEdit(USER_INI, section="Engine.Input", key=key,
                               value=command, note="medical key: " + key))
    return out


def warnings(values):
    out = []
    if values["tarkov_ballistics"] != "stock" and values.get("menu_bars"):
        out.append("Tarkov ballistics changes damage per calibre, and the "
                   "loadout menu's damage bars cannot follow it -- nothing "
                   "this tool reads maps a weapon entry to the round it "
                   "fires. The bars will overstate every rifle.")
    if values["tarkov_ballistics"] != "stock" and values["terro_helmets"] != "stock":
        out.append("Tarkov ballistics and helmets together is a large step: "
                   "rifle rounds at a third of their energy, against heads "
                   "that are now covered.")
    return out

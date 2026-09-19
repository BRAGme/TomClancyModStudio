r"""Raven Shield's weapon and ammunition statistics, in the compiled packages.

This is the one place in the tool that writes binary. Everything else Raven
Shield exposes is an ini or a plain-text template; the guns are not. They are
compiled UnrealScript class defaults inside `system\*.u`, and the mechanism for
reaching them is in `tcpc.upackage`. What is here is the *modelling*: which
properties are worth a control, and which way each one points.

## Which way the numbers point

Three of the five knobs are inverted, which is the whole reason this file
carries measurements rather than assertions.

**Accuracy is dispersion.** `fBaseAccuracy` is a cone, so a bigger number is a
worse weapon. `NormalAssaultM4` reads 1.26 standing, 1.74 shuffling, 2.61
walking and 10.78 running -- the number climbs as the player's stance gets
worse, which is the proof. Making a weapon *more* accurate means scaling these
*down*.

**Recoil is two numbers**, not one: `fAccuracyChange` is how much accuracy each
shot costs, `fWeaponJump` is how far the muzzle climbs. They have to move
together or "less recoil" gives a gun that climbs as far but recovers sooner.

**`fReticuleTime` is a delay.** Lower settles faster.

Damage is the exception and is not on the weapon at all -- it is `m_iEnergy` on
the ammunition, which is why a silenced weapon and its unsuppressed twin can
share a damage figure while differing in everything else.

## The menu would otherwise lie

`R6Description.u` holds the loadout menu's five stat bars as int arrays of up
to three entries -- one per variant of a weapon (NORMAL, CMAG, SILENCED). They
are authored percentages, not anything the game computes, so a gun that has
been retuned keeps its original bars unless they are rewritten too.

The bars run the *opposite* way to the values behind them, which was measured
rather than assumed, across the 139 equippable weapons:

    m_ARecoilPercent   vs fWeaponJump        r = -0.980
    m_AAccuracyPercent vs fBaseAccuracy      r = -0.933
    m_ARecoveryPercent vs fReticuleTime      r = -1.000
    m_ARangePercent    vs m_fMuzzleVelocity  r = +0.812

A higher bar is a better gun. So halving recoil has to move the recoil bar
*up*, and the mirror scales by the reciprocal. It is a proportional mirror and
not the game's own formula: bars are clamped to 100, and a bar already at 0
stays at 0.

## What cannot be done

Unreal serialises a property only where it differs from the class default, so
a property that is not authored cannot be written without lengthening the file
and invalidating the export table. In practice this costs nothing: all 139
weapons the loadout menu offers resolve a value for every property used here,
through their own defaults or an ancestor's. The 57 classes that do not are
abstract bases like `AssaultAK47`, which the menu never offers and which the
`Normal`/`CMag`/`Silenced` variants inherit from -- so an edit to the parent
reaches them anyway.
"""

from ..model import BOOL, CHOICE, Choice, INT, PropEdit, Setting

# Gold's two official expansions -- Athena Sword and Iron Wrath -- ship their
# own weapons, ammunition and menu bars in packages of their own, and every
# option here used to stop at the base game's. A person who turned on "less
# recoil" got it on 142 base weapons and not on the 31 expansion ones, with
# nothing on screen saying so.
#
# These are named ONE BY ONE on purpose. The obvious spelling is a glob over
# `Mods/*/System/*Weapons.u`, and it is wrong: `Mods\` is also where a person's
# OWN mods live. This installation has two of them -- NewOperative and
# SupplyDrop, the latter carrying fourteen weapon packages of its own -- and
# silently retuning somebody else's mod is not this tool's business. Only the
# two folders that ship with Gold are listed.
#
# An install without them is fine: `plan()` expands each path against the real
# folder, so a package that is not there matches nothing and its edits are
# simply not planned.
ATHENA = "Mods/AthenaSword/System/"
IRON = "Mods/IronWrath/System/"

#: the packages carrying weapon classes. `R61stWeapons.u` and `MP21stWeapons.u`
#: are deliberately not here: they hold first-person hands and meshes and no
#: statistics, so including them would only mean backing up and rewriting a
#: file byte for byte.
WEAPON_PACKAGES = ("system/R6Weapons.u", "system/R63rdWeapons.u",
                   ATHENA + "ASWeapons.u", IRON + "MP23rdWeapons.u")

#: ammunition lives with the base weapon classes, and with each expansion's
AMMO_PACKAGES = ("system/R6Weapons.u",
                 ATHENA + "ASWeapons.u", IRON + "MP2Weapons.u")

#: the loadout menu's stat bars
DESC_PACKAGES = ("system/R6Description.u",
                 ATHENA + "ASDescription.u", IRON + "MP2Description.u")

#: Ammunition classes are all named `ammo<calibre><load>`, plus `R6Bullet`,
#: which is the base every one of them inherits from and the value an
#: unspecialised round falls back to. The name glob matters: `m_iEnergy` is
#: also carried by frag grenades, flashbangs, claymores, breaching charges and
#: remote charges, and "bullets hit harder" should not move a breaching charge
#: from 8000 to 16000.
AMMO_CLASSES = ("ammo*", "R6Bullet")

#: the five postures a weapon carries a separate dispersion figure for
POSTURES = ("fBaseAccuracy", "fShuffleAccuracy", "fWalkingAccuracy",
            "fWalkingFastAccuracy", "fRunningAccuracy")

#: recoil, which is two numbers
RECOIL = ("fAccuracyChange", "fWeaponJump")

#: the stat bars are arrays of at most three entries -- 35 weapons have three,
#: 15 have two and 8 have one, so an index that does not exist is skipped.
BAR_SLOTS = 3

RECOIL_SCALE = {"none": 0.0, "quarter": 0.25, "half": 0.5, "x1.5": 1.5}
ACCURACY_SCALE = {"laser": 0.35, "tight": 0.7, "loose": 1.4}
SETTLE_SCALE = {"fast": 0.5, "slow": 1.5}
DAMAGE_SCALE = {"x2": 2.0, "x1.5": 1.5, "x0.5": 0.5}


def settings():
    return [
        Setting(
            "weapon_recoil", "Recoil", CHOICE, "stock", group="Weapons",
            help="How far the muzzle climbs per shot and how much accuracy "
                 "each shot costs. Both numbers move together, because "
                 "changing one alone gives a weapon that climbs as far as "
                 "before but recovers at a different rate.",
            caution="Everything in these two groups is a binary patch of the "
                    "game's own compiled packages. The originals are copied "
                    "before the first write and restored byte for byte by "
                    "Revert, but two things will undo or object to them: a "
                    "Steam file verification silently puts the stock files "
                    "back, and a server running stock packages may refuse a "
                    "client whose packages do not match. Use these for "
                    "single-player and for servers you control.",
            choices=[
                Choice("stock", "Stock", "As shipped."),
                Choice("half", "Half", "Noticeably steadier, still a rifle."),
                Choice("quarter", "A quarter", ""),
                Choice("none", "None", "Every weapon perfectly still."),
                Choice("x1.5", "Heavier", "Half again as much climb."),
            ],
            confidence="applied", touches="data"),
        Setting(
            "weapon_accuracy", "Accuracy", CHOICE, "stock", group="Weapons",
            help="The spread cone, in all five stances -- standing, "
                 "shuffling, walking, moving fast and running. The game "
                 "stores dispersion, so these are scaled DOWN to make a "
                 "weapon tighter; the relationship between stances is kept.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("tight", "Tighter", "Cone reduced by a third."),
                Choice("laser", "Very tight", "A third of stock spread."),
                Choice("loose", "Looser", "Half again as wide."),
            ],
            confidence="applied", touches="data"),
        Setting(
            "weapon_settle", "Reticule settle time", CHOICE, "stock",
            group="Weapons",
            help="How long the crosshair takes to close back down after "
                 "moving or firing. Stock is about half a second for an M4 "
                 "and over two seconds for an RPD.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("fast", "Twice as fast", ""),
                Choice("slow", "Half as fast", ""),
            ],
            confidence="applied", touches="data"),
        Setting(
            "weapon_magazines", "Extra magazines carried", INT, 0,
            group="Weapons", minimum=0, maximum=10, unit=" extra",
            help="Added to every weapon's magazine count. This is an "
                 "addition rather than a multiplier so that it means the same "
                 "thing across weapons that start from 2 and from 34.",
            confidence="applied", touches="data"),
        Setting(
            "ammo_damage", "Bullet damage", CHOICE, "stock", group="Ammunition",
            help="Damage is a property of the ROUND, not of the gun -- which "
                 "is why a silenced weapon and its plain twin hit equally "
                 "hard. This scales the energy of every cartridge in the "
                 "game, from 9mm at 567 to .50 BMG at 15,825.",
            caution="Grenades, flashbangs, claymores, breaching charges and "
                    "remote charges use the same energy field and are "
                    "deliberately left alone.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("x1.5", "Harder", ""),
                Choice("x2", "Lethal", "Doubled."),
                Choice("x0.5", "Softer", "Halved."),
            ],
            confidence="applied", touches="data"),
        Setting(
            "ammo_penetration", "Penetration", CHOICE, "stock",
            group="Ammunition",
            help="How much cover a round will go through. Stock values are "
                 "whole numbers from 1 to 4, and only 34 of the cartridges "
                 "state one at all -- the rest inherit it.",
            choices=[
                Choice("stock", "Stock", ""),
                Choice("max", "Through most cover", "Everything set to 4."),
                Choice("min", "Stopped by cover", "Everything set to 1."),
            ],
            confidence="experimental", touches="data"),
        Setting(
            "menu_bars", "Keep the loadout menu honest", BOOL, True,
            group="Ammunition",
            help="The stat bars in the weapon-selection menu are authored "
                 "percentages, not anything the game measures, so a retuned "
                 "weapon keeps its original bars. With this on, the damage, "
                 "recoil, accuracy and recovery bars are rescaled to match "
                 "what was actually changed.",
            caution="A proportional mirror, not the game's own formula. Bars "
                    "stop at 100, so several weapons will sit at full once "
                    "recoil is heavily reduced.",
            confidence="applied", touches="data"),
    ]


def edits(values):
    """Weapon and ammunition edits, plus the menu bars that describe them."""
    out = []
    v = values

    recoil = RECOIL_SCALE.get(v["weapon_recoil"])
    if recoil is not None:
        for pkg in WEAPON_PACKAGES:
            for prop in RECOIL:
                out.append(PropEdit(pkg, prop="m_stAccuracyValues." + prop,
                                    scale=recoil, minimum=0,
                                    note="recoil: " + prop))

    accuracy = ACCURACY_SCALE.get(v["weapon_accuracy"])
    if accuracy is not None:
        for pkg in WEAPON_PACKAGES:
            for prop in POSTURES:
                out.append(PropEdit(pkg, prop="m_stAccuracyValues." + prop,
                                    scale=accuracy, minimum=0,
                                    note="accuracy: " + prop))

    settle = SETTLE_SCALE.get(v["weapon_settle"])
    if settle is not None:
        for pkg in WEAPON_PACKAGES:
            out.append(PropEdit(pkg, prop="m_stAccuracyValues.fReticuleTime",
                                scale=settle, minimum=0,
                                note="reticule settle time"))

    spare = v["weapon_magazines"]
    if spare:
        for pkg in WEAPON_PACKAGES:
            out.append(PropEdit(pkg, prop="m_iNbOfClips", offset=spare,
                                minimum=1, note="magazines carried"))

    damage = DAMAGE_SCALE.get(v["ammo_damage"])
    if damage is not None:
        for pkg in AMMO_PACKAGES:
            for cls in AMMO_CLASSES:
                out.append(PropEdit(pkg, cls=cls, prop="m_iEnergy",
                                    scale=damage, minimum=1,
                                    note="bullet damage"))

    pen = {"max": 4, "min": 1}.get(v["ammo_penetration"])
    if pen is not None:
        for pkg in AMMO_PACKAGES:
            for cls in AMMO_CLASSES:
                out.append(PropEdit(pkg, cls=cls,
                                    prop="m_iPenetrationFactor", value=pen,
                                    note="penetration"))

    if v["menu_bars"]:
        out.extend(_bar_edits(damage, recoil, accuracy, settle))
    return out


def _bar_edits(damage, recoil, accuracy, settle):
    """Rescale the loadout menu's bars to match what the guns now do.

    Damage tracks its value directly; the other three run the opposite way to
    the numbers behind them, so they are scaled by the reciprocal. A change
    that zeroes recoil has no reciprocal, so those bars are set to full
    instead, which is what "no recoil at all" means on a 0-100 scale.
    """
    plan = [("m_ADamagePercent", damage, False),
            ("m_ARecoilPercent", recoil, True),
            ("m_AAccuracyPercent", accuracy, True),
            ("m_ARecoveryPercent", settle, True)]
    out = []
    for bar, factor, inverted in plan:
        if factor is None or factor == 1.0:
            continue
        for i in range(BAR_SLOTS):
            prop = "%s[%d]" % (bar, i)
            for pkg in DESC_PACKAGES:
                if inverted and factor == 0:
                    out.append(PropEdit(pkg, prop=prop, value=100,
                                        note="menu bar: " + bar))
                    continue
                out.append(PropEdit(
                    pkg, prop=prop,
                    scale=(1.0 / factor) if inverted else factor,
                    minimum=0, maximum=100, note="menu bar: " + bar))
    return out

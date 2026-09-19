r"""Ghost Recon (PC, with Desert Siege and Island Thunder) -- Red Storm's Ike.

Delivery is MOD. The game enumerates `Mods\*.*`, reads each folder's
`ModsCont.txt` and offers it in its own menu, and a mod is a sparse overlay
over `Mods\Origmiss\`, so the generated folder holds only the files an option
actually changes. No retail file is ever opened for writing and switching the
mod off in the game is a complete uninstall.

Most options are shared with Sum of All Fears and live in `_rse.py`. What is
here is what Ghost Recon has and Sum of All Fears does not.

**One thing Ghost Recon does NOT have is a global difficulty block.** Sum of
All Fears' combat model carries eleven tags that scale friendly and enemy skill
separately per difficulty; none of the eleven appears anywhere in
`GhostRecon.exe`, so adding them to this game's `CmbtModl.xml` would be a
silent no-op. That is why the difficulty page here works through the actors
instead.
"""

import os

from . import _rse, _gr_npc
from ..model import GameProfile, Layout, MOD

LAYOUT = Layout(
    signature=[
        "Mods/Origmiss/ModsCont.txt",
        "Mods/Origmiss/CommandMaps/*.rsb",
        "Data/Shell/Art/main_menu-01.rsb",
    ],
    exe="GhostRecon.exe",
    mods_dir="Mods",
    base_mod="Mods/Origmiss",
    data_dir="Data",
)

SETTINGS = (_rse.shared_settings("ghost_recon") + _gr_npc.settings()
            + [_gr_npc.armour_setting(), _gr_npc.armour_value_setting()])


def build_edits(values, root=None):
    out = _rse.shared_edits(values, "ghost_recon")
    if values.get("npc_weapons") and root:
        # Once the enemy carries its own copies, the Weapons page above is
        # the PLAYER's set -- so it must stop reaching the copies. Without
        # this the split would be undone by the very next edit: `Equip/*.gun`
        # matches `ak47_npc.gun` perfectly well.
        for edit in out:
            if edit.select == _gr_npc.GUNS and not edit.scope:
                edit.scope = "not:*%s.gun" % _gr_npc.NPC_SUFFIX
        out += _gr_npc.edits(
            values, os.path.join(str(root),
                                 LAYOUT.base_mod.replace("/", os.sep)))
    if root:
        out += _gr_npc.armour_edits(
            values, os.path.join(str(root),
                                 LAYOUT.base_mod.replace("/", os.sep)))
        out += _gr_npc.armour_value_edits(values)
    return out


def combination_warnings(values):
    out = []
    if values["enemy_skill"] == "elite" and values["enemy_armour"] == "max":
        out.append("Every enemy at skill 7 and armour 3 at once is well past "
                   "anything the campaign was balanced for.")
    if (values["lethality"] == "brutal" and values["weapon_accuracy"] == "tight"
            and not values.get("npc_weapons")):
        out.append("Quarter-lethality with halved dispersion cuts both ways: "
                   "enemies use the same weapon files you do. Turn on 'Give "
                   "the enemy its own weapons' to separate them.")
    return out


NOTES = r"""
Ghost Recon mods are sparse overlays. This tool builds one under Mods\, copies
only the files an option touches out of Mods\Origmiss, edits those copies, and
leaves everything else to fall through to the stock data. Nothing in the game's
own folders is written, and turning the mod off in the game's Mods menu undoes
it completely.

Enemies are told from your own squad by WHERE the file sits: enemy actors are
loose in Actor\, and the player's riflemen, demolitions, heavy weapons,
snipers and heroes are one level down in subfolders of it. The tag that looks
like it should answer the question does not -- <ClassName> says "demolitions"
on 624 of the 825 actor files, enemies included.

WHAT IS NOT HERE, AND WHY

Enemy count. Every actor in a mission carries Easy, Normal and Hard attributes,
and setting one to "0" removes that actor at that difficulty -- 437 of the base
game's 759 actors are present on Easy, 654 on Normal, all 759 on Hard. It is a
real lever and a per-actor one, so it needs a mission editor rather than a
slider, and it is not in this version.

Separating your accuracy from the enemies'. This IS built now -- "Give the
enemy its own weapons" on the Enemies page. Both sides read the same
Equip\*.gun, so with it off the weapon options move both; with it on, the
enemy's kits are shadowed to point at <weapon>_npc.gun copies and the Weapons
page becomes the player's set alone. Which guns to copy is read out of the
installation's own Equip\*.kit files at build time rather than listed in the
profile, because a written-down list goes stale against whatever mods are
installed -- PS2Accuracy, for instance, carries 31 _npc guns of which 19 have
no base gun in the retail campaign at all. See _gr_npc.py.

One seam is honest and unavoidable: m1911 only.kit is carried by both a few
friendly NPCs and by enemies, so those friendlies get the enemy's pistol.
Every other kit separates cleanly.

Body armour does nothing in the base campaign, and that is a shipped
omission rather than a design choice. Equip\CmbtModl.xml holds one factor per
body part, which the engine divides into a shot's kill energy; four of them
are the armoured-chest factors, one per armour level. The base file has eight
entries. Both expansions have twelve -- identical but for
BallisticArmoredChestFactor0..3 at 0 / 150 / 350 / 750. The loader zeroes
every factor before reading the file, so an absent factor is zero, and a zero
factor divided into any energy is a certain kill. Every armour level therefore
behaves exactly like no armour.

"Make body armour work" ships those four numbers, copied from the expansions'
own files. "How much body armour helps" then scales them, which is the option
Sum of All Fears has always had and this game could not.

Nothing in this profile has been watched working in a running game.
"""

PROFILE = GameProfile(
    id="ghost_recon",
    title="Tom Clancy's Ghost Recon",
    short="Ghost Recon",
    layout=LAYOUT,
    delivery=MOD,
    settings=SETTINGS,
    build_edits=build_edits,
    combination_warnings=combination_warnings,
    mod_name="ModStudio",
    mod_blurb="Mod Studio",
    notes=NOTES,
)

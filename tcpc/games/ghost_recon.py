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

from . import _rse
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

SETTINGS = _rse.shared_settings()


def build_edits(values):
    return _rse.shared_edits(values, "ghost_recon")


def combination_warnings(values):
    out = []
    if values["enemy_skill"] == "elite" and values["enemy_armour"] == "max":
        out.append("Every enemy at skill 7 and armour 3 at once is well past "
                   "anything the campaign was balanced for.")
    if values["lethality"] == "brutal" and values["weapon_accuracy"] == "tight":
        out.append("Quarter-lethality with halved dispersion cuts both ways: "
                   "enemies use the same weapon files you do.")
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

Separating your accuracy from the enemies'. Both sides read the same Equip\*.gun
files, so the accuracy option here moves both. The way to separate them is the
one the PS2Accuracy mod in this installation already uses: add a second set of
guns named <weapon>_npc.gun with different accuracy numbers, then shadow the
Equip\*.kit files -- which are the enemy kits, the player's being under
Kits\<class>\ -- to point at them. That technique is understood and is the
obvious next feature; it is not built yet.

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

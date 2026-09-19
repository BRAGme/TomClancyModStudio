r"""Ghost Recon Advanced Warfighter 2 (PC) -- the same Diesel engine.

Delivery is OVERLAY, for the same reason and by the same mechanism as GRAW 1.

**GRAW 2 also has a real mod system, and this profile does not use it.** Its
`mods\readme.txt` says to drop a `<name>.bundle` into `mods\` and add
`<mod_bundle name="<name>"/>` to `context.xml`, one mod at a time, and the game
ships the official `public_tools\bundler\bundler.exe` to build one. That is the
tidier route and it is the obvious next step; it needs a bundle WRITER, and
this tool only has a reader.

Worth recording from that tool, because it settles the question every Diesel
mod has to answer: `bundler\bundle.bat` -- GRIN's own, shipped, documented mod
build -- runs `compile-scripts` and then `quick-bundle`, and **never runs
`compile-xml`**, although that command exists. So an official mod bundle
contains plain `.xml` and no compiled `.xmb` at all, which means the plain XML
this tool edits is the copy the engine reads.
"""

from . import _graw, _graw_enemies
from ..model import CHOICE, Choice, GameProfile, Layout, OVERLAY, Setting, XmlAttr

LAYOUT = Layout(
    signature=[
        "Bundles/quick.bundle",
        "Settings/hud_visibility.xml",
        "mods/readme.txt",
        "public_tools/bundler/bundler.exe",
    ],
    exe="graw2.exe",
    bundles_dir="Bundles",
    overlay_dir="Data",
    compiled_suffix=".xmb",
    data_dir="Data",
)

#: `Settings\hud_palett_2.xml` is loose, self-documented, and ships a COMPLETE
#: second colour scheme that nothing selects. Its own header says how it is
#: meant to be used: "To change colors, copy desired setup into the HUD tag".
#: This does exactly that, which is why it is the one option here that is not a
#: guess about what the developers intended.
HUD_PALETTE = "Settings/hud_palett_2.xml"

#: name -> the alternate scheme's value, read out of the file's own
#: `<HUD_alt1>` block. Colours are 0-1 floats.
HUD_ALT = {
    "A": "0.918 0.494 0.07", "B2": "0.09 0.047 0.016",
    "B1": "0.19 0.15 0.11", "C": "0.365 0.314 0.278",
    "D1": "0.541 0.490 0.454", "D2": "0.835 0.784 0.749",
    "D3": "0.909 0.858 0.824", "K": "0.263 0.212 0.176",
    "X1": "0.188 0.102 0.02", "X2": "0.408 0.32 0.239",
    "X3": "0.765 0.757 0.757",
}

#: ...and the matching text colours from `<HUD_script_alt1>`, which the file
#: says must be changed as well or the scheme is only half applied.
HUD_SCRIPT_ALT = {
    "txt_pos1_color": "cFFea7e12", "txt_pos4_color": "cFF5d5047",
    "txt_pos5_color": "cFF8a7d74", "txt_pos6_color": "cFFd5c8bf",
    "txt_pos7_color": "cFFe8dbd2", "txt_normal_color": "cFFd5c8bf",
    "txt_selected_darker_color": "cFF170c04",
    "txt_selected_color": "cFF32251c",
}

EXTRA = [
    Setting(
        "hud_scheme", "HUD colour scheme", CHOICE, "official",
        group="Interface",
        help="Advanced Warfighter 2 ships two complete colour schemes in "
             "Settings\\hud_palett_2.xml and uses one of them. The file is "
             "loose, commented, and tells you in its own header that the way "
             "to switch is to copy the other block over the live one. This "
             "does that, including the second block of text colours the file "
             "warns you not to forget.",
        choices=[
            Choice("official", "Official",
                   "The teal the game ships with: #001717 panels, #06C2C5 "
                   "rules, an amber #E6AB40 accent."),
            Choice("brown", "Brown",
                   "The alternate scheme in the same file, which nothing "
                   "selects: warm browns with an orange accent."),
        ],
        confidence="experimental", touches="data"),
]

#: Every enemy squad template and its full roster, read out of this game's
#: own compiled `group_manager` -- the compiled copy, because the source is
#: macro-generated and only the compiled form has the groups expanded.
#: Friendly squads are not in it and so cannot be caught by the rename.
SQUAD_SIZE = {
    "ag_mex_mercenary_heavy": 4,
    "ag_mex_mercenary_heavy_night": 4,
    "ag_mex_mercenary_patrol": 8,
    "ag_mex_mercenary_patrol_night": 4,
    "ag_mex_mercenary_recon": 4,
    "ag_mex_mercenary_vehicle_crew": 2,
    "ag_mex_mercenary_vehicle_passangers": 4,
    "ag_mex_special_forces_grenadier": 2,
    "ag_mex_special_forces_heavy": 4,
    "ag_mex_special_forces_heavy_night": 4,
    "ag_mex_special_forces_patrol": 8,
    "ag_mex_special_forces_patrol_night": 4,
    "ag_mex_special_forces_recon": 4,
    "ag_mex_special_forces_vehicle_crew": 2,
    "ag_mex_special_forces_vehicle_passangers": 4,
    "mex_mercenary_heavy": 4,
    "mex_mercenary_heavy_night": 4,
    "mex_mercenary_patrol": 8,
    "mex_mercenary_patrol_night": 4,
    "mex_mercenary_recon": 4,
    "mex_mercenary_vehicle_crew": 3,
    "mex_mercenary_vehicle_passangers": 4,
    "mex_special_forces_grenadier": 2,
    "mex_special_forces_heavy": 4,
    "mex_special_forces_heavy_night": 4,
    "mex_special_forces_patrol": 8,
    "mex_special_forces_patrol_night": 4,
    "mex_special_forces_recon": 4,
    "mex_special_forces_vehicle_crew": 3,
    "mex_special_forces_vehicle_passangers": 4,
}

#: the living-enemy health values these files actually contain.
#: GRAW 2 made health fractional and keeps a matching maximum, so both vars
#: move together.
ENEMY_HEALTH = ['2.75', '3', '4']
ENEMY_HEALTH_ATTRS = ['damage_points', 'damage_points_max']

SETTINGS = _graw.shared_settings() + _graw_enemies.settings("graw2") + EXTRA


def build_edits(values):
    out = (_graw.shared_edits(values)
           + _graw_enemies.edits(values, SQUAD_SIZE, ENEMY_HEALTH,
                                 ENEMY_HEALTH_ATTRS, "graw2"))
    if values["hud_scheme"] == "brown":
        for name, value in HUD_ALT.items():
            out.append(XmlAttr(HUD_PALETTE, path="HUD/xdefine[name=%s]" % name,
                               attr="value", value=value,
                               note="HUD colour " + name))
        for name, value in HUD_SCRIPT_ALT.items():
            out.append(XmlAttr(HUD_PALETTE,
                               path="HUD_script/var[name=%s]" % name,
                               attr="default", value=value,
                               note="HUD text " + name))
    return out


NOTES = r"""
Advanced Warfighter 2 keeps 25,052 files in two .bundle archives totalling
3.7 GB, and this tool reads them rather than writing them: the stock file comes
out of the archive, the edited copy is written loose in the install at the same
path, and Diesel finds the loose one first.

There is a tidier route this profile does not take yet. mods\readme.txt says:

    Add your mod bundles here, edit context.xml add the line
    <mod_bundle name="modname"/> where modname is the bundle filename.
    You can not enable more than one mod at the same time.

and public_tools\bundler\bundler.exe is the official tool for building one.
Doing it that way would put every change in a single file with an off switch,
which is better than loose files in Data\ -- it needs a bundle writer, and this
tool only reads them.

One thing to be clear about, because it is easy to get backwards. In the
RETAIL bundles every .xml has a compiled .xmb twin and the engine reads the
twin -- a session log GRIN shipped by accident records 3,029 compiled opens
against 2 source opens. So this tool writes both forms, and its compiled writer
round-trips 7,984 of the game's 7,985 compiled files byte-identically.

In a MOD bundle the opposite holds, because GRIN's own bundle.bat never runs
compile-xml: such a bundle has no twins, so the source is what loads. Both are
true; they are about different containers.

The HUD colour option is the one thing here that is not an inference. The file
it edits is loose, commented, ships a complete second scheme nobody selects,
and explains in its own header how switching is meant to be done.

Nothing in this profile has been watched working in a running game.
"""

PROFILE = GameProfile(
    id="graw2",
    title="Ghost Recon Advanced Warfighter 2",
    short="GRAW 2",
    layout=LAYOUT,
    delivery=OVERLAY,
    settings=SETTINGS,
    build_edits=build_edits,
    notes=NOTES,
)

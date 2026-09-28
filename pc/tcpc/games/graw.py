r"""Ghost Recon Advanced Warfighter (PC) -- GRIN's Diesel engine.

Delivery is OVERLAY: the stock value is read out of `Bundles\quick.bundle` and
`Bundles\patch.bundle`, and the edited file is written loose where the
archive's own path says it belongs. The archives are never opened for writing.
See `_graw.py` for why that works and `docs/FORMATS.md` for the `BNDL` layout.

Most options are shared with Advanced Warfighter 2 and live in `_graw.py`.
"""

from . import _graw, _graw_enemies
from ..model import GameProfile, Layout, OVERLAY

LAYOUT = Layout(
    signature=[
        "Bundles/quick.bundle",
        "Bundles/init_game.xml",
        "Settings/weapon_ids.txt",
        "Settings/default_mp_weapon_kits.xml",
    ],
    exe="GRAW.exe",
    bundles_dir="Bundles",
    overlay_dir="Data",
    compiled_suffix=".bin",
    data_dir="Data",
)

#: Every enemy squad template and its full roster, read out of this game's
#: own compiled `group_manager` -- the compiled copy, because the source is
#: macro-generated and only the compiled form has the groups expanded.
#: Friendly squads are not in it and so cannot be caught by the rename.
SQUAD_SIZE = {
    "mex_guerilla_heavy": 4,
    "mex_guerilla_heavy_night": 4,
    "mex_guerilla_patrol": 4,
    "mex_guerilla_patrol_night": 4,
    "mex_guerilla_recon": 4,
    "mex_guerilla_vehicle_crew": 2,
    "mex_guerilla_vehicle_passangers": 4,
    "mex_infantry_heavy": 4,
    "mex_infantry_patrol": 4,
    "mex_infantry_patrol_night": 4,
    "mex_infantry_recon": 4,
    "mex_infantry_vehicle_crew": 2,
    "mex_infantry_vehicle_passangers": 4,
    "mex_special_forces_heavy": 4,
    "mex_special_forces_patrol": 4,
    "mex_special_forces_recon": 4,
    "mex_special_forces_silent_ops": 4,
    "mex_special_forces_vehicle_crew": 2,
    "mex_special_forces_vehicle_passangers": 4,
}

#: the living-enemy health values these files actually contain.
#: GRAW 1's living enemies are 4; two special NPCs are 8; husks are 16 in the
#: same files and are deliberately absent from this table.
ENEMY_HEALTH = ['4', '8']
ENEMY_HEALTH_ATTRS = ['damage_points']

SETTINGS = _graw.shared_settings() + _graw_enemies.settings("graw")


def build_edits(values):
    return (_graw.shared_edits(values)
            + _graw_enemies.edits(values, SQUAD_SIZE, ENEMY_HEALTH,
                                  ENEMY_HEALTH_ATTRS, "graw"))


NOTES = r"""
Advanced Warfighter keeps 21,356 files in two .bundle archives totalling 3.8 GB.
This tool never writes to them. It reads the stock file out of the archive,
edits it, and writes the result loose in the install at the path the archive
itself uses -- which the Diesel engine looks at before it looks in the archive.

Every data file here exists twice: u_scar_light.xml and u_scar_light.xml.bin,
its compiled twin. THE ENGINE READS THE COMPILED ONE. A session log the game
accidentally ships proves it -- 3,029 compiled opens against 2 source opens
where both existed. So each option writes both forms, and the compiled writer
round-trips all 5,674 of this game's compiled files byte-identically.

That is how the 764 texture files already sitting under Data\textures\ in this
installation work: they shadow paths that are also inside quick.bundle, and
they are what convinced me the mechanism is real rather than merely plausible.

Because Data\ is shared with those replacements, Restore never deletes the
folder. The manifest records every path this tool created and every path it had
to write over, and restoring touches only those.

Nothing in this profile has been watched working in a running game.
"""

PROFILE = GameProfile(
    id="graw",
    title="Ghost Recon Advanced Warfighter",
    short="GRAW",
    layout=LAYOUT,
    delivery=OVERLAY,
    settings=SETTINGS,
    build_edits=build_edits,
    notes=NOTES,
)

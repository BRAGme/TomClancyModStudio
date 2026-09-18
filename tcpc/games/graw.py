r"""Ghost Recon Advanced Warfighter (PC) -- GRIN's Diesel engine.

Delivery is OVERLAY: the stock value is read out of `Bundles\quick.bundle` and
`Bundles\patch.bundle`, and the edited file is written loose where the
archive's own path says it belongs. The archives are never opened for writing.
See `_graw.py` for why that works and `docs/FORMATS.md` for the `BNDL` layout.

Most options are shared with Advanced Warfighter 2 and live in `_graw.py`.
"""

from . import _graw
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
    data_dir="Data",
)

SETTINGS = _graw.shared_settings()


def build_edits(values):
    return _graw.shared_edits(values)


NOTES = r"""
Advanced Warfighter keeps 21,356 files in two .bundle archives totalling 3.8 GB.
This tool never writes to them. It reads the stock file out of the archive,
edits it, and writes the result loose in the install at the path the archive
itself uses -- which the Diesel engine looks at before it looks in the archive.

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

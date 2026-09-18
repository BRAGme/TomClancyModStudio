r"""Ghost Recon Advanced Warfighter 2 (PC) -- the same Diesel engine.

Delivery is OVERLAY, for the same reason and by the same mechanism as GRAW 1.

**GRAW 2 also has a real mod system, and this profile does not use it.** Its
`mods\readme.txt` says to drop a `<name>.bundle` into `mods\` and add
`<mod_bundle name="<name>"/>` to `context.xml`, one mod at a time, and the
game ships the official `public_tools\bundler\bundler.exe` to build one. That
is the tidier route and it is the obvious next step; it needs a bundle WRITER,
and this tool only has a reader.
"""

from . import _graw
from ..model import GameProfile, Layout, OVERLAY

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
    data_dir="Data",
)

SETTINGS = _graw.shared_settings()


def build_edits(values):
    return _graw.shared_edits(values)


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

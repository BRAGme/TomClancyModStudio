"""Working out which game an extracted folder is, and how healthy it is.

The identity comes from the folder's own executable, not its name. Every Xbox
XBE carries a 32-bit title id in its certificate -- `55530006` for Ghost Recon,
`55530013` for Rainbow Six 3 -- and that is the same four bytes on every copy of
a given game. A folder name is whatever the person who extracted the disc felt
like typing.

Two shapes of folder are accepted. The ordinary one has `default.xbe` at the
top. The other is Rainbow Six 3 Black Arrow's prototype disc, which is a demo
*installer*: its `default.xbe` is Microsoft's installer stub, title id
FFFFFF00, and the game itself sits under `Files\\Black_Arrow_XBOX_media` with
its executable still called `RainbowSix3_Release.xbe`. Pointing this tool at the
folder you downloaded should work, so identification walks down one level
looking for a real game root before giving up.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from . import xbe
from .engine import has_backup
from .games import BY_TITLE_ID, PROFILES
from .gamedir import _resolve_case

#: how deep to look for a game root under the folder the user chose
MAX_DESCENT = 3


@dataclass
class Detection:
    path: str                 # the game root -- what everything else works on
    ok: bool
    profile: object = None
    chosen: str = ""          # what the user actually pointed at
    title_id: str = ""
    title_name: str = ""
    xbe_path: str = ""
    message: str = ""
    missing: tuple = ()
    has_backup: bool = False

    @property
    def title(self):
        return self.profile.title if self.profile else "Unrecognised folder"

    @property
    def id_matches(self):
        return not self.missing


def _xbes(folder):
    """(path, Xbe) for every executable directly in this folder, the one named
    `default.xbe` first."""
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return
    names.sort(key=lambda n: (n.lower() != "default.xbe", n.lower()))
    for name in names:
        if not name.lower().endswith(".xbe"):
            continue
        full = os.path.join(folder, name)
        try:
            yield full, xbe.load(full)
        except (OSError, xbe.XbeError):
            continue


def _candidate_roots(folder, depth=0):
    """This folder and, if nothing here is a supported game, the folders under
    it -- breadth first, so the shallowest match wins."""
    yield folder
    if depth >= MAX_DESCENT:
        return
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return
    for name in names:
        sub = os.path.join(folder, name)
        if os.path.isdir(sub) and not name.startswith("."):
            yield from _candidate_roots(sub, depth + 1)


def identify(path) -> Detection:
    path = os.path.abspath(str(path))
    if os.path.isfile(path):
        # someone dropped default.xbe on the window rather than its folder
        path = os.path.dirname(path)
    if not os.path.isdir(path):
        return Detection(path, False, message="Folder not found.")

    unknown = None
    for root in _candidate_roots(path):
        for xbe_path, image in _xbes(root):
            profile = BY_TITLE_ID.get(image.title_id_hex.upper())
            if profile is None:
                if unknown is None and image.title_id_hex != "FFFFFF00":
                    unknown = (root, xbe_path, image)
                continue
            return _finish(path, root, xbe_path, image, profile)

    if unknown is not None:
        root, xbe_path, image = unknown
        names = ", ".join(sorted({p.short for p in PROFILES}))
        return Detection(path, False, chosen=path, xbe_path=xbe_path,
                         title_id=image.title_id_hex,
                         title_name=image.title_name,
                         message="%s (title id %s) is not one of the games this "
                                 "tool knows. Supported: %s."
                                 % (image.title_name or "This executable",
                                    image.title_id_hex, names))
    return Detection(path, False, chosen=path,
                     message="No Xbox executable under this folder. Choose the "
                             "folder an Xbox disc was extracted into -- the one "
                             "with default.xbe in it.")


def _finish(chosen, root, xbe_path, image, profile) -> Detection:
    missing = tuple(m.rel for m in profile.markers
                    if _resolve_case(root, m.rel) is None)
    msgs = []
    if missing:
        msgs.append("Missing from this folder: %s. Options that edit those "
                    "files will find nothing." % ", ".join(missing))
    return Detection(root, True, profile=profile, chosen=chosen,
                     title_id=image.title_id_hex, title_name=image.title_name,
                     xbe_path=xbe_path, message=" ".join(msgs),
                     missing=missing, has_backup=has_backup(root))


def scan_folder(folder, limit=64) -> list:
    """Every supported game folder directly under `folder`, for a pick list."""
    out = []
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return out
    for name in names:
        sub = os.path.join(folder, name)
        if not os.path.isdir(sub) or name.startswith("."):
            continue
        det = identify(sub)
        if det.ok:
            out.append(det)
        if len(out) >= limit:
            break
    return out

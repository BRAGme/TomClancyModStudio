"""Working out which game a disc image or folder is, and how healthy it is.

The identity comes from the game's own executable, not from its name. Every Xbox
XBE carries a 32-bit title id in its certificate -- `55530006` for Ghost Recon,
`55530013` for Rainbow Six 3 -- and that is the same four bytes on every copy of
a given game. A file name is whatever the person who ripped the disc typed.

Three shapes are accepted:

  * an `.iso`, read through `xiso`; `default.xbe` is looked up in its root;
  * a folder someone extracted, with `default.xbe` at the top;
  * and Rainbow Six 3 Black Arrow's *prototype* disc, which is a demo
    installer: its `default.xbe` is Microsoft's stub with title id FFFFFF00 and
    the game sits under `Files\\Black_Arrow_XBOX_media` with its executable
    still called `RainbowSix3_Release.xbe`. Pointing this tool at the folder
    someone downloaded should work, so a folder that is not itself a game is
    walked into before it is given up on.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from . import xbe, xiso
from .engine import has_backup
from .games import BY_TITLE_ID, PROFILES
from .gamedir import open_source

#: how deep to look for a game root under the folder the user chose
MAX_DESCENT = 3

#: extensions worth opening as a disc image
IMAGE_SUFFIXES = (".iso", ".xiso", ".bin")


@dataclass
class Detection:
    path: str                 # the game -- what everything else works on
    ok: bool
    profile: object = None
    chosen: str = ""          # what the user actually pointed at
    kind: str = ""            # "iso" or "folder"
    title_id: str = ""
    title_name: str = ""
    xbe_path: str = ""
    message: str = ""
    missing: tuple = ()
    has_backup: bool = False

    @property
    def title(self):
        return self.profile.title if self.profile else "Unrecognised game"

    @property
    def id_matches(self):
        return not self.missing


def _image_xbe(path):
    """(name, Xbe) for the boot executable of a disc image, or None."""
    try:
        with xiso.Xiso(path) as iso:
            for name in ("/DEFAULT.XBE", "/RAINBOWSIX3_RELEASE.XBE"):
                entry = iso.files.get(name)
                if entry is None:
                    continue
                try:
                    return name.lstrip("/").lower(), xbe.parse(iso.read(entry))
                except xbe.XbeError:
                    continue
    except (OSError, xiso.XisoError):
        return None
    return None


def _folder_xbes(folder):
    """(path, Xbe) for every executable directly in this folder, `default.xbe`
    first."""
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
    it -- shallowest first."""
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
        if not path.lower().endswith(IMAGE_SUFFIXES):
            # someone dropped default.xbe on the window rather than its game
            return identify(os.path.dirname(path))
        got = _image_xbe(path)
        if got is None:
            return Detection(path, False, chosen=path, kind="iso",
                             message="This is not an Xbox disc image, or its "
                                     "boot executable is missing.")
        name, image = got
        profile = BY_TITLE_ID.get(image.title_id_hex.upper())
        if profile is None:
            return _unknown(path, path, name, image)
        return _finish(path, path, "iso", name, image, profile)

    if not os.path.isdir(path):
        return Detection(path, False, message="Not found.")

    unknown = None
    for root in _candidate_roots(path):
        for xbe_path, image in _folder_xbes(root):
            profile = BY_TITLE_ID.get(image.title_id_hex.upper())
            if profile is None:
                if unknown is None and image.title_id_hex != "FFFFFF00":
                    unknown = (root, xbe_path, image)
                continue
            return _finish(path, root, "folder", xbe_path, image, profile)

    if unknown is not None:
        root, xbe_path, image = unknown
        return _unknown(path, root, xbe_path, image)
    return Detection(path, False, chosen=path, kind="folder",
                     message="No Xbox executable here. Choose a game's disc "
                             "image, or the folder one was extracted into -- "
                             "the one with default.xbe in it.")


def _unknown(chosen, root, xbe_path, image) -> Detection:
    names = ", ".join(sorted({p.short for p in PROFILES}))
    return Detection(root, False, chosen=chosen, xbe_path=xbe_path,
                     title_id=image.title_id_hex, title_name=image.title_name,
                     message="%s (title id %s) is not one of the games this "
                             "tool knows. Supported: %s."
                             % (image.title_name or "This executable",
                                image.title_id_hex, names))


def _finish(chosen, root, kind, xbe_path, image, profile) -> Detection:
    try:
        source = open_source(root)
    except Exception as exc:                      # noqa: BLE001
        return Detection(root, False, chosen=chosen, kind=kind,
                         message="Could not read this game: %s" % exc)
    try:
        missing = tuple(m.rel for m in profile.markers
                        if source.resolve(m.rel) is None)
    finally:
        source.close()

    msgs = []
    if missing:
        msgs.append("Missing from this copy: %s. Options that edit those files "
                    "will find nothing." % ", ".join(missing))
    return Detection(root, True, profile=profile, chosen=chosen, kind=kind,
                     title_id=image.title_id_hex, title_name=image.title_name,
                     xbe_path=xbe_path, message=" ".join(msgs),
                     missing=missing, has_backup=has_backup(root))


def scan(folder, limit=64) -> list:
    """Every supported game directly under `folder` -- images and folders both.

    Disc images first, because on a shelf that has both an `.iso` and the folder
    somebody extracted from it, the image is the copy worth editing: it is the
    one the other was made from.
    """
    out = []
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return out

    # `isfile` as well as the suffix: one of these shelves has a FOLDER called
    # "...(En,Fr,De,Es,It).xiso", which the suffix alone happily calls an image
    # and then lists a second time as a folder.
    files = [n for n in names
             if n.lower().endswith(IMAGE_SUFFIXES)
             and os.path.isfile(os.path.join(folder, n))]
    dirs = [n for n in names
            if not n.startswith(".") and os.path.isdir(os.path.join(folder, n))]
    for name in files + dirs:
        det = identify(os.path.join(folder, name))
        if det.ok:
            out.append(det)
        if len(out) >= limit:
            break
    return out


#: the old name, kept because the tests and the CLI grew up with it
scan_folder = scan

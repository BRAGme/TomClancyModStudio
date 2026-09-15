"""Reading each game's own artwork out of its folder, to skin the window with.

Nothing here is redistributed. The pictures are read from the user's own
extracted disc at run time and cached under `%LOCALAPPDATA%`, which is the same
arrangement the PS2 Mod Studio uses and the only one that is anyone's to make.

Four containers, one per engine generation, all reached the same way:

  * Ghost Recon and Island Thunder -- `.RSB`, versions 8 and 9 (`rsb`).
  * Ghost Recon 2 and Summit Strike -- `.XPR`, the console's own packed
    resource, swizzled (`xpr`).
  * Rainbow Six 3, Black Arrow and GRAW -- ordinary 32-bit `.TGA`, which
    Pillow opens directly.

A menu page is a power-of-two texture with a 4:3 picture in the top-left corner
and filler beyond it, in every one of the three, so everything goes through the
same content crop before it is used.
"""

from __future__ import annotations

import hashlib
import os

from . import rsb, xpr
from .gamedir import _resolve_case


class ArtError(Exception):
    pass


#: where to look when a profile names nothing, or names something this copy of
#: the game does not have. Regional builds are the usual reason -- Summit
#: Strike ships UI_STARTBkgd_EMEA.xpr where Ghost Recon 2 ships _US.
FALLBACK_BACKDROPS = (
    "shell/art/shell_bgd-01.rsb",
    "shell/art/main_menu-01.rsb",
    "shell/art/UI_STARTBkgd_US.xpr",
    "shell/art/UI_STARTBkgd_EMEA.xpr",
    "shell/art/STARTscreen.xpr",
    "LoadingScreens/Background.tga",
    "Splash.tga",
    "Splash_INT.tga",
)

FALLBACK_EMBLEMS = (
    "shell/art/dash_gr-logo.rsb",
    "shell/art/dash_gr-logo.xpr",
)


def _load(path):
    """Whatever this file is, as a Pillow image."""
    from PIL import Image

    with open(path, "rb") as fh:
        head = fh.read(64)
        fh.seek(0)
        data = fh.read()
    if xpr.is_xpr(data):
        return xpr.to_image(data)
    if path.lower().endswith(".rsb") and rsb.is_rsb(data):
        return rsb.to_image(data)
    if head[:4] == b"DDS ":
        return Image.open(path)
    return Image.open(path)


def _first(root, names):
    for rel in names:
        if not rel:
            continue
        full = _resolve_case(root, rel)
        if full and os.path.isfile(full):
            return full
    return None


def _cache_path(cache_dir, root, source, tag):
    if not cache_dir:
        return None
    key = hashlib.sha1(("%s|%s|%s" % (root, source, tag)).encode("utf-8")).hexdigest()[:16]
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "%s-%s.png" % (tag, key))


def _cached(cache_dir, root, source, tag, build):
    from PIL import Image

    path = _cache_path(cache_dir, root, source, tag)
    if path and os.path.exists(path):
        try:
            return Image.open(path).convert("RGBA")
        except OSError:
            pass
    image = build()
    if image is None:
        return None
    image = image.convert("RGBA")
    if path:
        try:
            image.save(path)
        except OSError:
            pass
    return image


def banner_image(detection, cache_dir=None):
    """The backdrop the window is painted on."""
    if not detection or not detection.ok:
        return None
    root = detection.path
    named = (detection.profile.ui_art or {}).get("backdrop")
    source = _first(root, (named,) + FALLBACK_BACKDROPS)
    if source is None:
        return None

    def build():
        try:
            return rsb.content_crop(_load(source))
        except Exception:                          # noqa: BLE001
            return None

    return _cached(cache_dir, root, source, "backdrop", build)


def emblem_image(detection, cache_dir=None):
    """The mark that sits beside the page title, or None for a game with none.

    Only the two Ghost Recon generations carry a square dashboard logo. Rainbow
    Six 3 and GRAW put their wordmark inside the splash art itself, so lifting a
    separate emblem out of them would mean keying a logo out of a photograph --
    the PS2 tool does exactly that for its discs and it is a lot of machinery
    for a picture nobody asked for. These games get a title with no mark, which
    is what their own menus look like.
    """
    if not detection or not detection.ok:
        return None
    root = detection.path
    named = (detection.profile.ui_art or {}).get("emblem")
    source = _first(root, (named,) + FALLBACK_EMBLEMS)
    if source is None:
        return None

    def build():
        try:
            image = rsb.content_crop(_load(source)).convert("RGBA")
        except Exception:                          # noqa: BLE001
            return None
        return _key_black(image)

    return _cached(cache_dir, root, source, "emblem", build)


def _key_black(image, threshold=28):
    """Knock the flat background out of a dashboard logo.

    Both games' logos are drawn light on a solid near-black square with no
    alpha of their own, so a plain threshold is the whole job -- there is no
    need for the autocontrast-then-key the PS2 discs' stamped-in marks require.
    """
    image = image.convert("RGBA")
    px = image.load()
    w, h = image.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r <= threshold and g <= threshold and b <= threshold:
                px[x, y] = (r, g, b, 0)
    return image


def chrome_images(detection, cache_dir=None):
    """Textures for the window chrome.

    There are none, deliberately. All four of these games draw their own panels
    and buttons procedurally rather than from nine-sliced art -- the only menu
    bitmaps on any of the discs are backgrounds, logos and icons -- so the skins
    draw theirs the same way. The function exists because the window code is the
    PS2 tool's and asks for this.
    """
    return {}


def mission_art(detection, name, cache_dir=None):
    """A mission's own briefing map, for the card that switches it on.

    Ghost Recon and Island Thunder name one in every `.MIS` -- `<MapShots>`,
    e.g. `m01_caves_shots.rsb` -- and ship it loose under `commandmaps\\`.
    """
    if not detection or not detection.ok or not name:
        return None
    root = detection.path
    source = _first(root, ("commandmaps/%s.rsb" % name,
                           "commandmaps/%s" % name,
                           "shell/art/%s.rsb" % name))
    if source is None:
        return None

    def build():
        try:
            return rsb.content_crop(_load(source))
        except Exception:                          # noqa: BLE001
            return None

    return _cached(cache_dir, root, source, "mission", build)

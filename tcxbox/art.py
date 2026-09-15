"""Reading each game's own artwork out of it, to skin the window with.

Nothing here is redistributed. The pictures are read from the user's own disc
image or extracted folder at run time and cached under `%LOCALAPPDATA%`, which
is the same arrangement the PS2 Mod Studio uses and the only one that is
anyone's to make.

Four containers, one per engine generation, all reached the same way:

  * Ghost Recon and Island Thunder -- `.RSB`, versions 8 and 9 (`rsb`);
  * Ghost Recon 2 and Summit Strike -- `.XPR`, the console's own packed
    resource, swizzled (`xpr`);
  * Rainbow Six 3, Black Arrow and GRAW -- ordinary `.TGA` and `.DDS`;
  * Critical Hour -- `.DDS` inside its Magma menu tree.

**Every mark here is the game's own high-resolution wordmark**, not its 64-pixel
dashboard icon. That was the first version's mistake and it showed: Ghost
Recon's `dash_gr-logo.rsb` is a 64 x 64 green disc, and scaling it to fill a
header turned it into a blurred slab with a cropped green square behind it. The
same games ship the real thing -- `STARTscreen.rsb` is a 512 x 128 wordmark,
`Splash.xpr` is 512 x 512, Rainbow Six 3's `Splash.tga` is 640 x 480 -- so the
mark is lifted out of those instead and comes out eight times the resolution.

Lifting it means two steps, both measured from the picture rather than
hardcoded per game:

  `wordmark_box`  finds the brightest connected mass and takes its bounding
                  box. On all seven splash screens the wordmark is by some
                  distance the brightest thing in frame, so this lands on the
                  logo and not on the photograph behind it.
  `key_ground`    turns luminance into alpha over a soft ramp, so the dark
                  plate the logo is printed on falls away while the lettering's
                  antialiasing survives. A hard threshold leaves jagged edges;
                  this does not.
"""

from __future__ import annotations

import hashlib
import io
import os

from . import rsb, xpr
from .gamedir import open_source


class ArtError(Exception):
    pass


#: tried in order when a profile names nothing, or names something this copy of
#: the game does not have. Regional builds are the usual reason -- Summit Strike
#: ships UI_STARTBkgd_EMEA.xpr where Ghost Recon 2 ships _US.
FALLBACK_BACKDROPS = (
    "shell/art/shell_bgd-01.rsb",
    "shell/art/main_menu-01.rsb",
    "shell/art/UI_STARTBkgd_US.xpr",
    "shell/art/UI_STARTBkgd_EMEA.xpr",
    "LoadingScreens/Background.tga",
    "LoadingScreens/Splash.dds",
    "XboxData/Magma/Textures/BG/P_CUSTOMTEX/BG_GRADLOBBY.dds",
    "Splash.tga",
    "Splash_INT.tga",
)

FALLBACK_EMBLEMS = (
    "shell/art/STARTscreen.rsb",
    "shell/art/Splash.xpr",
    "shell/art/Splash_EMEA.xpr",
    "LoadingScreens/Splash.dds",
    "XboxData/Magma/Textures/BG/P_COMMONTEX/LOGO_RAINBCRITICAL.dds",
    "Splash.tga",
    "Splash_INT.tga",
)


# ---------------------------------------------------------------------------
# decoding
# ---------------------------------------------------------------------------

def decode(data: bytes, name: str):
    """Whatever this file is, as a Pillow image."""
    from PIL import Image

    low = name.lower()
    if data[:4] == xpr.MAGIC:
        return xpr.to_image(data)
    if low.endswith(".rsb"):
        return rsb.to_image(data)
    return Image.open(io.BytesIO(data))


def _first(source, names):
    """(relpath, bytes) for the first of these that exists."""
    for rel in names:
        if not rel:
            continue
        real = source.resolve(rel)
        if real:
            try:
                return real, source.read(real)
            except Exception:                      # noqa: BLE001
                continue
    return None, None


# ---------------------------------------------------------------------------
# lifting a wordmark out of a splash screen
# ---------------------------------------------------------------------------

def _luma(image):
    return image.convert("RGB").convert("L")


def wordmark_box(image, share=0.72):
    """The bounding box of the brightest mass in the picture, or None.

    `share` is where the threshold sits between the image's median and its
    brightest pixel. A box that ends up covering almost the whole frame means
    the picture has no single bright subject -- a uniformly lit photograph --
    and None is returned so the caller can fall back rather than "crop" to
    everything.
    """
    from PIL import Image

    grey = _luma(image)
    hi = grey.getextrema()[1]
    if hi < 40:
        return None
    cut = int(hi * share)
    mask = grey.point(lambda v, c=cut: 255 if v >= c else 0, mode="1")
    box = mask.getbbox()
    if box is None:
        return None
    w, h = image.size
    bw, bh = box[2] - box[0], box[3] - box[1]
    if bw * bh > 0.80 * w * h or bw < w * 0.10 or bh < h * 0.04:
        return None
    pad_x, pad_y = int(bw * 0.04) + 2, int(bh * 0.10) + 2
    return (max(0, box[0] - pad_x), max(0, box[1] - pad_y),
            min(w, box[2] + pad_x), min(h, box[3] + pad_y))


def key_ground(image, lo=48, hi=150, polarity="light"):
    """Alpha from luminance, over a soft ramp.

    These wordmarks are printed on a plate and carry no alpha of their own.
    Ramping rather than thresholding is what keeps the lettering's antialiased
    edge: a hard cut at any level leaves it jagged, and at this size that is the
    difference between a logo and a stencil. Where the ramp SITS is per game,
    because the plates differ -- Rainbow Six 3's logo is on black and Black
    Arrow's on a lit amber panel, and the same threshold cannot drop both.

    `polarity="dark"` is for a mark printed the other way up: Critical Hour's
    logo is black lettering on white. Keying that by luminance would keep the
    white and throw away the logo, so the ramp is taken on inverted luminance
    and the surviving pixels are set to near-white -- the logo's own shape, in
    the one colour that reads on a dark interface.
    """
    from PIL import Image

    image = image.convert("RGBA")
    grey = _luma(image)
    if polarity == "dark":
        grey = grey.point(lambda v: 255 - v)
    alpha = grey.point(
        lambda v: 0 if v <= lo else (255 if v >= hi
                                     else int(255 * (v - lo) / float(hi - lo))))
    if polarity == "dark":
        image = Image.merge("RGBA", (
            Image.new("L", image.size, 235), Image.new("L", image.size, 238),
            Image.new("L", image.size, 242), alpha))
        return image
    image.putalpha(alpha)
    return image


# ---------------------------------------------------------------------------
# cache
# ---------------------------------------------------------------------------

def _cached(cache_dir, game, source_rel, tag, build):
    from PIL import Image

    path = None
    if cache_dir:
        key = hashlib.sha1(("%s|%s|%s|2" % (game, source_rel, tag))
                           .encode("utf-8")).hexdigest()[:16]
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, "%s-%s.png" % (tag, key))
        if os.path.exists(path):
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


def _open(detection):
    return open_source(detection.path)


# ---------------------------------------------------------------------------
# what the window asks for
# ---------------------------------------------------------------------------

def banner_image(detection, cache_dir=None):
    """The backdrop the window is painted on."""
    if not detection or not detection.ok:
        return None
    named = (detection.profile.ui_art or {}).get("backdrop")
    source = _open(detection)
    try:
        rel, data = _first(source, (named,) + FALLBACK_BACKDROPS)
    finally:
        source.close()
    if rel is None:
        return None

    def build():
        try:
            return rsb.content_crop(decode(data, rel))
        except Exception:                          # noqa: BLE001
            return None

    return _cached(cache_dir, detection.path, rel, "backdrop", build)


def emblem_image(detection, cache_dir=None):
    """The game's wordmark, lifted out of its own splash screen."""
    if not detection or not detection.ok:
        return None
    art = detection.profile.ui_art or {}
    named = art.get("emblem")
    source = _open(detection)
    try:
        rel, data = _first(source, (named,) + FALLBACK_EMBLEMS)
    finally:
        source.close()
    if rel is None:
        return None

    def build():
        try:
            image = rsb.content_crop(decode(data, rel))
        except Exception:                          # noqa: BLE001
            return None
        box = art.get("emblem_box")
        if box:
            w, h = image.size
            image = image.crop((int(box[0] * w), int(box[1] * h),
                                int(box[2] * w), int(box[3] * h)))
        else:
            found = wordmark_box(image)
            if found:
                image = image.crop(found)
        lo, hi = art.get("emblem_key", (48, 150))
        return key_ground(image, lo, hi, art.get("emblem_polarity", "light"))

    return _cached(cache_dir, detection.path, rel, "emblem", build)


def chrome_images(detection, cache_dir=None):
    """Textures for the window chrome.

    There are none, deliberately. These games draw their own panels and buttons
    procedurally rather than from nine-sliced art -- the only menu bitmaps on
    any of the discs are backgrounds, logos and icons -- so the skins draw
    theirs the same way. The function exists because the window code is the PS2
    tool's and asks for this.
    """
    return {}


def mission_art(detection, name, cache_dir=None):
    """A mission's own briefing map, for the card that switches it on.

    Ghost Recon and Island Thunder name one in every `.MIS` -- `<MapShots>`,
    e.g. `m01_caves_shots.rsb` -- and ship it under `commandmaps\\`.
    """
    if not detection or not detection.ok or not name:
        return None
    source = _open(detection)
    try:
        rel, data = _first(source, ("commandmaps/%s.rsb" % name,
                                    "commandmaps/%s" % name,
                                    "shell/art/%s.rsb" % name))
    finally:
        source.close()
    if rel is None:
        return None

    def build():
        try:
            return rsb.content_crop(decode(data, rel))
        except Exception:                          # noqa: BLE001
            return None

    return _cached(cache_dir, detection.path, rel, "mission", build)

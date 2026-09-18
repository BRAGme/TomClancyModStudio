r"""The games' own menu artwork, read out of the user's installation.

Nothing here is redistributed. Every picture is decoded from the copy of the
game on this machine, cached under `%LOCALAPPDATA%`, and used only to skin the
window so the tool looks like the menu you would be standing in.

The PC builds make this much easier than the console ones did. There is no
archive to open: Raven Shield's menu pages are loose 24-bit TGAs, Vegas's logo
is a loose TGA that already carries its own alpha, and the three Red Storm
games keep theirs as loose `.rsb` next to the executable.

**Each mark needs its own treatment**, and the reason is in the art:

* Raven Shield and Sum of All Fears stamp a bright wordmark into dark
  photography, so a luminance key cuts it out cleanly.
* Ghost Recon's is the hard one. It is a mid-grey gradient over jungle, and
  there is no threshold that keeps the lettering and rejects the leaves, so it
  is contrast-stretched first and keyed high; a little sky survives behind it.
* Lockdown and Vegas need no key at all. Both ship a real cut-out with its own
  alpha -- `r6lockdown.rsb` and `RSVegas_Logo.tga` -- which is always worth
  looking for before keying a composited one out of a splash screen.
"""

from __future__ import annotations

import os
import re

from . import rsb


# ---------------------------------------------------------------------------
# where the art is
# ---------------------------------------------------------------------------

#: install-relative candidates for the page behind the whole window, best
#: first. The first one that decodes wins.
BANNERS = {
    "ravenshield": ["backgrounds/Main_menu_01.tga",
                    "backgrounds/Main_menu_02.tga",
                    "backgrounds/CampNew/CampNew_BG.tga"],
    "ghost_recon": ["Data/Shell/Art/main_menu-01.rsb",
                    "Data/Shell/Art/shell_bgd-01.rsb"],
    "soaf": ["Data/Shell/Art/main_menu-01.rsb",
             "Data/Shell/Art/shell_bgd-01.rsb"],
    "lockdown": ["data/shell/art/background00.rsb",
                 "data/shell/art/background05.rsb"],
    # A location slide rather than a loading screen: these are the pages the
    # game's own menu sits on, so the tool ends up on the same plate the game
    # puts its menu on.
    "vegas": ["KellerGame/Slide/Locations/03_Fremont_01.dds",
              "KellerGame/Content/MenusPC/Textures/LoadingScreens/"
              "BackgroundDante.tga",
              "KellerGame/ImageMap/SP_Dam1.dds"],
    # Advanced Warfighter's menu is a 3D scene, so there is no backdrop image
    # to find -- these are its loading screens, which are the same art
    # direction and the only full-page photography it has.
    "graw": ["data/textures/gui/mission_loading_screens_1-4.dds"],
    "graw2": ["data/textures/atlas_gui/mission_gfx/load_sp_m01.dds",
              "data/textures/atlas_gui/mission_gfx/load_mp_hh.dds"],
}

#: Banners that are a sheet rather than a page, as fractions to crop out.
#: Advanced Warfighter packs four loading screens into one 2048x2048 texture.
BANNER_CROP = {
    "graw": (0.0, 0.0, 0.5, 0.5),
}

#: (relative path, crop box as fractions of the decoded page) for the mark.
#: A box of None means the file IS the mark.
EMBLEMS = {
    # the "RAINBOW SIX 3 / RAVEN SHIELD" reticle wordmark, top right of the
    # menu page
    "ravenshield": ("backgrounds/Main_menu_01.tga", (0.52, 0.01, 0.99, 0.20)),
    # "Tom Clancy's GHOST RECON", upper left of the 640x480 content
    "ghost_recon": ("Data/Shell/Art/main_menu-01.rsb", (0.02, 0.20, 0.74, 0.41)),
    # "THE SUM OF ALL FEARS" in gold, top left of the 640x480 content.
    # NOT `soaf_command_bkgrnd.rsb`, which sounds like the right file and is
    # not: it is a 512x128 flat cyan command-screen plate with no lettering
    # on it at all.
    "soaf": ("Data/Shell/Art/main_menu-01.rsb", (0.02, 0.03, 0.74, 0.21)),
    # Lockdown ships its logo as a real cut-out with its own alpha -- the game
    # calls this one `kLogo`. `splash.bmp` has the same logo composited onto a
    # pale gradient and needs keying; this does not.
    "lockdown": ("data/shell/art/r6lockdown.rsb", None),
    # already cut out, alpha and all
    "vegas": ("KellerGame/Content/MenusPC/Textures/SinglePlayer/"
              "RSVegas_Logo.tga", None),
    # inside the bundle; a proper RGBA cut-out, white lettering with the
    # game's teal
    "graw": ("data/textures/atlas_interface/menu/logos_diffuse/"
             "h_1600x1200.dds", None),
    # inside the bundle, and a MASK rather than a picture -- see EMBLEM_MODE
    "graw2": ("data/textures/atlas_gui/general_gfx/sp_logo_h.dds", None),
}

#: how to turn a crop into a mark with a transparent background.
#:   ("key",  floor, gain)  bright lettering on dark art -> keep the bright
#:   ("dark", floor, gain)  dark lettering on pale art  -> keep the dark
#:   ("alpha", 0, 0)        the file already has an alpha channel; use it
EMBLEM_MODE = {
    # Floors are high because these marks are stamped over photography rather
    # than over flat colour: at a low floor the key keeps the scene behind the
    # lettering and the header gets a picture in a box instead of a wordmark.
    "ravenshield": ("key", 135, 4.0),
    # ...except Ghost Recon's, which is a mid-grey gradient with only the
    # "Tom Clancy's" line in white. A floor high enough to reject the jungle
    # behind it also rejects most of the word GHOST RECON, so this one is
    # lifted first and keyed low.
    "ghost_recon": ("lift", 145, 3.6),
    "soaf": ("key", 140, 4.0),
    "lockdown": ("alpha", 0, 0),
    "vegas": ("alpha", 0, 0),
    "graw": ("alpha", 0, 0),
    # Advanced Warfighter 2's wordmark is THREE TINT MASKS, not a picture.
    # Its red, green and blue channels are separate coverage masks and its
    # alpha is the outline; the shader combines them with three palette
    # colours. `data/objects/gui/hud_new/materials.xml` names the material
    # `GRAW_logo` and binds red_color/green_color/blue_color to the palette
    # entries X1, X2 and X3, and `Settings\hud_palett_2.xml` gives those as
    # "logo dark", "logo mid" and "logo bright". Rebuilding it that way is the
    # only thing that produces the real logo -- every plain channel order
    # comes out neon.
    "graw2": ("tint3", 0, 0),
}

#: The three palette colours Advanced Warfighter 2 tints its wordmark with,
#: read out of `Settings\hud_palett_2.xml` rather than sampled.
TINT3 = {"graw2": ((1, 51, 56), (0, 155, 166), (252, 253, 253))}

#: what a single-channel "mask" emblem is painted in. Nothing uses it now that
#: Advanced Warfighter 2's three-mask logo is rebuilt properly, but the mode
#: stays: a one-channel mask is a common enough way to ship a logo.
MASK_INK = {}

#: Marks whose alpha needs its holes filled after keying. Nothing needs it now
#: that Lockdown's real cut-out is being used instead of its splash screen,
#: but the step is kept: it is the answer for any mark whose lettering is a
#: hole punched through a solid block.
CLOSE_ALPHA = {}

#: Ghost Recon and Sum of All Fears draw a 640x480 menu into a 1024x512 page
#: and leave the rest black. Trimming that filler is not cosmetic: the backdrop
#: is scaled to COVER the window, so a page that is 38% empty gets the real
#: picture blown up and pushed off the side.
CONTENT_CROP = {"ghost_recon", "soaf"}


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def _resolve(root, rel):
    """`rel` under `root`, tolerating the case these folders disagree on."""
    if not root:
        return None
    direct = os.path.join(root, rel.replace("/", os.sep))
    if os.path.isfile(direct):
        return direct
    cur = root
    for i, part in enumerate(p for p in rel.split("/") if p):
        try:
            names = os.listdir(cur)
        except OSError:
            return None
        for n in names:
            if n.lower() == part.lower():
                cur = os.path.join(cur, n)
                break
        else:
            return None
    return cur if os.path.isfile(cur) else None


def open_from(detection, rel):
    """Decode `rel` for this game, wherever that game keeps it.

    Six of the seven games keep their menu art loose. Advanced Warfighter
    keeps it inside a 3.8 GB archive, so the loose tree is tried first -- a
    replacement the user dropped in is what the game would show -- and the
    archive is the fallback.
    """
    hit = open_image(_resolve(detection.path, rel))
    if hit is not None:
        return hit
    profile = getattr(detection, "profile", None)
    if profile is None or not profile.layout.bundles_dir or not detection.path:
        return None
    try:
        from .bundle import BundleSet
        folder = os.path.join(detection.path,
                              profile.layout.bundles_dir.replace("/", os.sep))
        with BundleSet(folder) as bundles:
            if rel not in bundles:
                return None
            return decode_bytes(bundles.read(rel))
    except Exception:                             # noqa: BLE001
        return None


def decode_bytes(raw):
    """A picture from bytes, for content that came out of an archive."""
    import io
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(raw))
        img.load()
        return img
    except Exception:                             # noqa: BLE001
        return None


def open_image(path):
    """Decode whatever kind of picture this is, or None."""
    if not path or not os.path.isfile(path):
        return None
    if path.lower().endswith(".rsb"):
        return rsb.load(path)
    try:
        from PIL import Image
        img = Image.open(path)
        img.load()
        return img
    except Exception:                             # noqa: BLE001
        return None


def content_crop(img, tol=10):
    """Trim the uniform filler a power-of-two page leaves around the art.

    Walks in from the right and the bottom while every row or column is within
    `tol` of black, which is what these pages pad with. Left and top are not
    trimmed -- the menu art is anchored there, and a dark scene really can
    start with a black column.
    """
    if img is None:
        return None
    rgb = img.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    right = w
    while right > w // 2:
        col = right - 1
        if any(max(px[col, y]) > tol for y in range(0, h, 4)):
            break
        right -= 1
    bottom = h
    while bottom > h // 2:
        row = bottom - 1
        if any(max(px[x, row]) > tol for x in range(0, right, 4)):
            break
        bottom -= 1
    if right == w and bottom == h:
        return img
    return img.crop((0, 0, right, bottom))


def _crop_frac(img, box):
    if img is None or box is None:
        return img
    w, h = img.size
    x0, y0, x1, y1 = box
    return img.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))


def _cached(cache_dir, profile_id, kind):
    if not cache_dir:
        return None
    return os.path.join(cache_dir, "%s.%s.png" % (profile_id, kind))


def _load_cache(path):
    if not path or not os.path.exists(path):
        return None
    try:
        from PIL import Image
        img = Image.open(path)
        img.load()
        return img
    except Exception:                             # noqa: BLE001
        return None


def _save_cache(img, path):
    if not path or img is None:
        return
    try:
        img.save(path, "PNG")
    except Exception:                             # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# the two the window asks for
# ---------------------------------------------------------------------------

def banner_image(detection, cache_dir=None):
    """The page that goes behind the whole window, or None."""
    profile = getattr(detection, "profile", None)
    if profile is None:
        return None
    cache = _cached(cache_dir, profile.id, "banner")
    hit = _load_cache(cache)
    if hit is not None:
        return hit
    for rel in BANNERS.get(profile.id, []):
        img = open_from(detection, rel)
        if img is None:
            continue
        if profile.id in CONTENT_CROP:
            img = content_crop(img)
        img = _crop_frac(img, BANNER_CROP.get(profile.id))
        img = img.convert("RGB")
        _save_cache(img, cache)
        return img
    return None


def emblem_image(detection, cache_dir=None):
    """The mark for the header, on a transparent background, or None."""
    profile = getattr(detection, "profile", None)
    if profile is None:
        return None
    cache = _cached(cache_dir, profile.id, "emblem")
    hit = _load_cache(cache)
    if hit is not None:
        return hit.convert("RGBA")

    spec = EMBLEMS.get(profile.id)
    if not spec:
        return None
    rel, box = spec
    img = open_from(detection, rel)
    if img is None:
        return None
    if profile.id in CONTENT_CROP:
        img = content_crop(img)
    img = _crop_frac(img, box)

    mode, floor, gain = EMBLEM_MODE.get(profile.id, ("key", 110, 3.2))
    ink = TINT3.get(profile.id) or MASK_INK.get(profile.id, (255, 255, 255))
    rgba = _key(img, mode, floor, gain, ink)
    close = CLOSE_ALPHA.get(profile.id)
    if close:
        rgba = _close_alpha(rgba, close)
    rgba = _trim_alpha(rgba)
    _save_cache(rgba, cache)
    return rgba


def _key(img, mode, floor, gain, ink=(255, 255, 255)):
    from PIL import Image, ImageEnhance, ImageOps
    if mode == "mask":
        rgba = img.convert("RGBA")
        flat = [Image.new("L", rgba.size, c) for c in ink]
        return Image.merge("RGBA", tuple(flat) + (rgba.split()[-1],))
    if mode == "tint3":
        return _tint3(img, ink)

    if mode == "lift":
        # Stretch the crop's own range before keying. A mark set in mid-grey
        # cannot be separated from mid-grey photography by a threshold; pulling
        # the crop's darkest pixels to black and its brightest to white first
        # gives the threshold something to cut on.
        rgb = img.convert("RGB")
        rgb = ImageOps.autocontrast(rgb, cutoff=1)
        img = ImageEnhance.Brightness(rgb).enhance(1.15)
        mode = "key"

    if mode == "alpha":
        rgba = img.convert("RGBA")
        if rgba.split()[-1].getextrema() == (255, 255):
            # The file claims an alpha channel but every pixel is opaque, so
            # there is nothing cut out and a bare rectangle would land in the
            # header. Fall through to the brightness key rather than trust the
            # channel's existence.
            return _key(img, "key", 110, 3.2)
        return rgba

    rgba = img.convert("RGBA")
    px = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, _a = px[x, y]
            lum = (r * 3 + g * 6 + b) // 10
            level = (lum - floor) if mode == "key" else (floor - lum)
            px[x, y] = (r, g, b, max(0, min(255, int(level * gain))))
    return rgba


def _close_alpha(rgba, size):
    """Fill holes in the cutout without moving its outline."""
    from PIL import ImageFilter
    r, g, b, a = rgba.split()
    a = a.filter(ImageFilter.MaxFilter(size)).filter(ImageFilter.MinFilter(size))
    from PIL import Image
    return Image.merge("RGBA", (r, g, b, a))


def _tint3(img, colours):
    """Rebuild a three-mask logo the way its shader does.

    Each of the red, green and blue channels is a separate coverage mask, and
    each is painted in its own palette colour; the three are added, and the
    file's alpha is the outline. Straight addition rather than a weighted
    blend, because that is what an additive tint shader does and because the
    three masks barely overlap.
    """
    rgba = img.convert("RGBA")
    src = rgba.load()
    out = rgba.copy()
    dst = out.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = src[x, y]
            acc = [0, 0, 0]
            for mask, colour in zip((r, g, b), colours):
                if not mask:
                    continue
                for i in range(3):
                    acc[i] += colour[i] * mask // 255
            dst[x, y] = (min(255, acc[0]), min(255, acc[1]),
                         min(255, acc[2]), a)
    return out


def _trim_alpha(rgba, threshold=40):
    """Drop the fully transparent margin the key leaves behind.

    Without it a mark that does not fill its own source is scaled to fit the
    empty space around it rather than to fit itself, and lands in the header
    noticeably smaller than the marks beside it. Thresholding first matters:
    the key leaves a faint haze out to the edges, and a plain `getbbox()` on
    that trims nothing at all.
    """
    if rgba is None:
        return None
    box = rgba.split()[-1].point(lambda a: 255 if a > threshold else 0).getbbox()
    if box and (box[2] - box[0]) > 8 and (box[3] - box[1]) > 8:
        return rgba.crop(box)
    return rgba


def chrome_images(detection, cache_dir=None):
    """Textures the chrome painters use, by name. None of the PC skins needs
    one yet -- they are all drawn -- so this is an empty dict, kept because the
    window calls it and a skin that wants a real texture should have somewhere
    to get it."""
    return {}


def mission_art(detection, name, cache_dir=None):
    """A picture for one mission's card, or None.

    Vegas is the only one of the five that ships a usable still per mission,
    as loose DDS in `KellerGame\\ImageMap`. The Red Storm games keep briefing
    art too and it is decoded by the same `open_image`, so a profile only has
    to name the file.
    """
    profile = getattr(detection, "profile", None)
    if profile is None or not name:
        return None
    return open_from(detection, name)


# ---------------------------------------------------------------------------
# finding the games
# ---------------------------------------------------------------------------

LIBRARY_RX = re.compile(r'"path"\s*"([^"]+)"')


def steam_libraries() -> list:
    """Every `steamapps\\common` Steam knows about.

    Read from `libraryfolders.vdf` rather than guessed, because on this kind of
    machine the five games are spread across whatever drives Steam was pointed
    at -- here they are on two different ones.
    """
    roots = []
    for base in _steam_roots():
        vdf = os.path.join(base, "steamapps", "libraryfolders.vdf")
        try:
            with open(vdf, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        for path in LIBRARY_RX.findall(text):
            path = path.replace("\\\\", "\\")
            _add(roots, os.path.join(path, "steamapps", "common"))
    for base in _steam_roots():
        _add(roots, os.path.join(base, "steamapps", "common"))
    return roots


def _add(roots, path):
    """Append a library, comparing the way the filesystem does.

    The registry and `libraryfolders.vdf` disagree about the case of the Steam
    path on this machine, and a plain `not in` let the same folder in twice --
    which would then have been scanned twice and offered the user the same
    game under two rows.
    """
    if not os.path.isdir(path):
        return
    seen = {os.path.normcase(os.path.normpath(r)) for r in roots}
    if os.path.normcase(os.path.normpath(path)) not in seen:
        roots.append(os.path.normpath(path))


def search_roots() -> list:
    """Everywhere worth looking for one of these games.

    Steam's libraries first, then the top level of every fixed drive. The
    second half is not padding: Advanced Warfighter 1 and 2 are not Steam
    titles and sit directly on a drive root, so a Steam-only sweep finds five
    of the seven games and quietly misses two.
    """
    roots = steam_libraries()
    for drive in _fixed_drives():
        _add(roots, drive)
    return roots


def _fixed_drives() -> list:
    out = []
    if os.name != "nt":
        return out
    import ctypes
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    for i in range(26):
        if not mask & (1 << i):
            continue
        root = "%s:\\" % chr(ord("A") + i)
        # 3 is DRIVE_FIXED. Sweeping a network share or an optical drive would
        # be slow and pointless.
        if ctypes.windll.kernel32.GetDriveTypeW(root) == 3:
            out.append(root)
    return out


def _steam_roots() -> list:
    out = []
    try:
        import winreg
        for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                          (winreg.HKEY_LOCAL_MACHINE,
                           r"SOFTWARE\WOW6432Node\Valve\Steam")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    for value in ("SteamPath", "InstallPath"):
                        try:
                            path = winreg.QueryValueEx(k, value)[0]
                        except OSError:
                            continue
                        path = os.path.normpath(path)
                        if os.path.isdir(path) and path not in out:
                            out.append(path)
            except OSError:
                continue
    except ImportError:
        pass
    for guess in (r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"):
        if os.path.isdir(guess) and guess not in out:
            out.append(guess)
    return out

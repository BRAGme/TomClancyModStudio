"""Pulling artwork out of the games so the tool can wear their own skin.

Rainbow Six 3 stores its full-screen art as `.FBZ`: a 16-byte header
(`u32 rawSize, u32 zSize, u16 width, u16 height, u32 bpp`) followed by one zlib
stream of uncompressed pixels. The loading and legal screens are 640x448x24.

Ghost Recon and Jungle Storm use the Red Storm `.RSB` texture format inside
their `GR.IMG` / `MENU.IMG` archives; that decoder lives in `rsb.py` when it is
available and this module falls back cleanly when it is not.
"""

from __future__ import annotations

import io
import struct
import zlib


class ArtError(Exception):
    pass


def decode_fbz(blob: bytes):
    """Return (width, height, RGB bytes)."""
    if len(blob) < 16:
        raise ArtError("FBZ is too short")
    raw_size, z_size, width, height, bpp = struct.unpack_from("<IIHHI", blob)
    if not (0 < width <= 4096 and 0 < height <= 4096):
        raise ArtError("implausible FBZ dimensions %dx%d" % (width, height))
    try:
        pixels = zlib.decompressobj().decompress(blob[16:16 + z_size] if z_size else blob[16:])
    except zlib.error as exc:
        raise ArtError("FBZ payload does not inflate: %s" % exc) from exc
    if len(pixels) < raw_size:
        raise ArtError("FBZ yields %d bytes, header says %d" % (len(pixels), raw_size))
    pixels = pixels[:raw_size]

    stride = raw_size // height

    # Test the declared depth FIRST. A 32-bit image also satisfies
    # `stride >= width * 3`, so checking the 24-bit case first silently decodes
    # every 32-bit screen as 24-bit and shears it.
    if bpp == 32 or (bpp != 24 and stride >= width * 4):
        rgb = bytearray(width * height * 3)
        for y in range(height):
            src = y * stride
            for x in range(width):
                o = src + x * 4
                d = (y * width + x) * 3
                rgb[d:d + 3] = pixels[o:o + 3]
        return width, height, bytes(rgb)
    if bpp == 24 or stride >= width * 3:
        rgb = bytearray(width * height * 3)
        for y in range(height):
            row = pixels[y * stride:y * stride + width * 3]
            rgb[y * width * 3:y * width * 3 + len(row)] = row
        return width, height, bytes(rgb)
    raise ArtError("unsupported FBZ bpp %d (stride %d for width %d)" % (bpp, stride, width))


def fbz_to_image(blob: bytes):
    """A PIL image, or None if Pillow is not installed."""
    try:
        from PIL import Image
    except ImportError:
        return None
    w, h, rgb = decode_fbz(blob)
    return Image.frombytes("RGB", (w, h), rgb)


def iso_art(iso, patterns, limit=12) -> list:
    """[(path, PIL image)] for every FBZ in the disc matching `patterns`."""
    out = []
    for pat in patterns:
        for ent in iso.find_all(pat):
            if ent.is_dir or ent.size < 64:
                continue
            try:
                img = fbz_to_image(iso.read(ent.lba, ent.size))
            except (ArtError, Exception):
                continue
            if img is not None:
                out.append((ent.path, img))
            if len(out) >= limit:
                return out
    return out


def save_png(image, path):
    image.save(path, "PNG")
    return path


# ---------------------------------------------------------------------------
# "give me something to put at the top of the window"
# ---------------------------------------------------------------------------

#: hand-picked per game: the screens that actually look like the game's UI
BANNER_PREFERENCE = {
    # The loading screen carries the game's own menu chrome -- the angled metal
    # bands and the Rainbow emblem -- over a dark scene, which is exactly the
    # backdrop the in-game menus sit on.
    "graw_slus21422": [r"/CD/LE/GR3_2\.FBZ$", r"/CD/LE/GR3_1\.FBZ$",
                       r"/CD/LE/LANG_BG\.FBZ$"],
    "r6_3_slus20883": [r"/NTSC_DI/LE/LOADING/LVL/SHIPYARD_A\.FBZ$",
                       r"/NTSC_DI/LE/LOADING/LVL/ALCATRAZ_A\.FBZ$",
                       r"/NTSC_DI/LE/LOADING/LVL/MENU\.FBZ$",
                       r"/NTSC_CD/LE/LANG_BG\.FBZ$"],
}

#: where each game keeps the mark that sits in the corner of its menus, and the
#: fraction of that image the mark occupies (left, top, right, bottom)
EMBLEM = {
    "graw_slus21422": ([r"/CD/LE/GR3_2\.FBZ$"], (0.560, 0.050, 1.000, 0.355)),
    "r6_3_slus20883": ([r"/NTSC_DI/LE/LOADING/LVL/MENU\.FBZ$",
                        r"/NTSC_CD/LE/LANG_BG\.FBZ$"],
                       (0.355, 0.775, 0.645, 0.965)),
}
EMBLEM_ARCHIVE = {
    "ghost_recon_slus20613": ("/MAIN_MENU_PS2.RSB", (0.02, 0.035, 0.80, 0.255)),
    "soaf_sles51180": ("/MAIN_MENU_PS2.RSB", (0.0375, 0.0896, 0.7047, 0.2208)),
    # Jungle Storm ships no wordmark anywhere on the disc -- its own menus have
    # no corner mark either -- so it borrows the reticle ring its shell is built
    # around, which is the closest thing it has to a badge.
    "jungle_storm_slus20820": ("/LOAD_NEW_1.RSB", (0.02, 0.02, 0.98, 0.98)),
}

#: how to lift each mark off its background, as (mode, floor, gain).
#:   "lift" -- stamped dark into dark art, so raise it first, then key
#:   "key"  -- already bright on dark, so key straight off
#: The floor is the luminance below which a pixel becomes transparent. Jungle
#: Storm's ring is a dim teal on near-black and disappears entirely at the
#: threshold Ghost Recon's white wordmark needs.
EMBLEM_MODE = {
    "r6_3_slus20883": ("lift", 62, 2.6),
    "ghost_recon_slus20613": ("key", 118, 3.2),
    "jungle_storm_slus20820": ("key", 46, 3.0),
    "graw_slus21422": ("key", 96, 3.0),
    "soaf_sles51180": ("key", 96, 3.0),
}

#: the game's own menu art, by name, inside its archives
ARCHIVE_BANNERS = {
    "ghost_recon_slus20613": ["/MAIN_MENU_PS2.RSB", "/SHELL_BGD_PS2.RSB",
                              "/LOAD-SCREEN.RSB"],
    "jungle_storm_slus20820": ["/SHELL_BGD_PS2.RSB", "/LOAD_NEW_1.RSB",
                               "/LOAD_NEW_2.RSB"],
    "soaf_sles51180": ["/MAIN_MENU_PS2.RSB"],
}


def find_fbz(iso, pattern, archive_pattern=None):
    """An FBZ by path, whether it sits in the ISO tree or inside a vokes archive.

    Rainbow Six 3 keeps its loading screens -- which carry the menu chrome -- in
    `VOKES*.IMG` under `/NTSC_DI/...`, while the legal and language screens sit
    in the ISO's own directory. Callers should not have to know which.
    """
    import re
    ent = iso.find(pattern)
    if ent is not None:
        try:
            return fbz_to_image(iso.read(ent.lba, ent.size))
        except ArtError:
            return None
    rx = re.compile(pattern, re.I)
    from .vokes import open_archives
    for arc in open_archives(iso, archive_pattern or r"/(VOKES\d|GR|MENU)\.IMG$"):
        for key, e in arc.files.items():
            if rx.search(key):
                try:
                    return fbz_to_image(arc.read_entry(e))
                except ArtError:
                    return None
    return None


def banner_image(detection, cache_dir=None):
    """A PIL image to head the window with, or None.

    Tries the disc first and falls back to a cached PNG, so the second launch
    does not have to touch a 4 GB file at all.
    """
    import os
    profile = detection.profile
    if profile is None:
        return None
    cached = os.path.join(cache_dir, profile.id + ".png") if cache_dir else None
    if cached and os.path.exists(cached):
        try:
            from PIL import Image
            return Image.open(cached).convert("RGB")
        except Exception:
            pass

    img = None
    try:
        from .iso import Iso
        with Iso(detection.path) as iso:
            for pat in BANNER_PREFERENCE.get(profile.id, []):
                img = find_fbz(iso, pat, profile.archive_pattern)
                if img is not None:
                    break
            if img is None:
                img = _archive_banner(iso, profile)
    except Exception:
        return None

    if img is not None and cached:
        try:
            img.save(cached, "PNG")
        except Exception:
            pass
    return img


def emblem_image(detection, cache_dir=None):
    """The small mark for the header: Rainbow's laurel badge, the Ghost Recon
    wordmark. Returns a transparent-background PIL image, or None."""
    import os
    profile = detection.profile
    if profile is None:
        return None
    cached = os.path.join(cache_dir, profile.id + ".emblem.png") if cache_dir else None
    if cached and os.path.exists(cached):
        try:
            from PIL import Image
            return Image.open(cached).convert("RGBA")
        except Exception:                         # noqa: BLE001
            pass
    try:
        from PIL import Image, ImageEnhance, ImageOps
        from .iso import Iso
    except ImportError:
        return None

    img = None
    try:
        with Iso(detection.path) as iso:
            pats, box = EMBLEM.get(profile.id, (None, None))
            if pats:
                for pat in pats:
                    src = find_fbz(iso, pat, profile.archive_pattern)
                    if src is not None:
                        img = _crop_frac(src, box)
                        break
            name_box = EMBLEM_ARCHIVE.get(profile.id)
            if img is None and name_box:
                from . import rsb
                from .vokes import open_archives
                name, box = name_box
                for arc in open_archives(iso, profile.archive_pattern or
                                         r"/(VOKES\d|GR|MENU)\.IMG$"):
                    ent = arc.files.get(name.upper())
                    if ent is None:
                        continue
                    try:
                        src = rsb.to_image(arc.read_entry(ent))
                    except Exception:             # noqa: BLE001
                        continue
                    if src is not None:
                        img = _crop_frac(src, box)
                        break
    except Exception:                             # noqa: BLE001
        return None
    if img is None:
        return None

    mode, floor, gain = EMBLEM_MODE.get(profile.id, ("key", 118, 3.2))
    img = img.convert("RGB")
    if mode == "lift":
        # stamped dark into dark art: raise it before keying or nothing survives
        img = ImageOps.autocontrast(img, cutoff=2)
        img = ImageEnhance.Brightness(img).enhance(1.25)
    rgba = img.convert("RGBA")
    px = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, _a = px[x, y]
            lum = (r * 3 + g * 6 + b) // 10
            px[x, y] = (r, g, b, max(0, min(255, int((lum - floor) * gain))))
    if cached:
        try:
            rgba.save(cached, "PNG")
        except Exception:                         # noqa: BLE001
            pass
    return rgba


def _crop_frac(img, box):
    w, h = img.size
    return img.crop((int(w * box[0]), int(h * box[1]),
                     int(w * box[2]), int(h * box[3])))


def _archive_banner(iso, profile):
    """The game's own menu art, out of its own archive."""
    try:
        from . import rsb
    except ImportError:
        return None
    from .vokes import open_archives

    arcs = open_archives(iso, profile.archive_pattern or
                         r"/(VOKES\d|GR|MENU)\.IMG$")
    wanted = ARCHIVE_BANNERS.get(profile.id, [])
    for name in wanted:
        for arc in arcs:
            ent = arc.files.get(name.upper())
            if ent is None:
                continue
            try:
                img = rsb.to_image(arc.read_entry(ent))
            except Exception:                     # noqa: BLE001
                continue
            if img is not None and img.size[0] >= 256:
                return img

    best = None
    for arc in arcs:
        for key, ent in arc.files.items():
            if not key.endswith(".RSB") or ent.size < 60000:
                continue
            try:
                img = rsb.to_image(arc.read_entry(ent))
            except Exception:                     # noqa: BLE001
                continue
            if img is None or img.size[0] < 256:
                continue
            score = img.size[0] * img.size[1]
            if best is None or score > best[0]:
                best = (score, img)
    return best[1] if best else None

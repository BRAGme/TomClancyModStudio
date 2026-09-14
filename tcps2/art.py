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
    if bpp == 24 or stride >= width * 3:
        rgb = bytearray(width * height * 3)
        for y in range(height):
            row = pixels[y * stride:y * stride + width * 3]
            rgb[y * width * 3:y * width * 3 + len(row)] = row
        return width, height, bytes(rgb)
    if bpp == 32 or stride >= width * 4:
        rgb = bytearray(width * height * 3)
        for y in range(height):
            src = y * stride
            for x in range(width):
                o = src + x * 4
                d = (y * width + x) * 3
                rgb[d:d + 3] = pixels[o:o + 3]
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
    "r6_3_slus20883": [r"/NTSC_CD/LE/LANG_BG\.FBZ$", r"/NTSC_CD/LE/PAD_ENG\.FBZ$",
                       r"/NTSC_CD/LE/MCARD/1_01_ENG\.FBZ$"],
}

#: the game's own menu art, by name, inside its archives
ARCHIVE_BANNERS = {
    "ghost_recon_slus20613": ["/MAIN_MENU_PS2.RSB", "/SHELL_BGD_PS2.RSB",
                              "/LOAD-SCREEN.RSB"],
    "jungle_storm_slus20820": ["/SHELL_BGD_PS2.RSB", "/LOAD_NEW_1.RSB",
                               "/LOAD_NEW_2.RSB"],
}


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
                ent = iso.find(pat)
                if ent is None:
                    continue
                try:
                    img = fbz_to_image(iso.read(ent.lba, ent.size))
                except ArtError:
                    continue
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

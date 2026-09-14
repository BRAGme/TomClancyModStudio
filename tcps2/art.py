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
    # Ghost Recon 2's briefing screens are its menu chrome exactly: the drab
    # green plate, the lime rule across the top, the wordmark in the corner.
    "gr2_slus21105": [r"/DI/LE/LOADING/EN/LOADING_ASSAULT\.FBZ$",
                      r"/DI/LE/LOADING/EN/LOADING_SUPREMACY\.FBZ$",
                      r"/DI/ONLINESEL\.FBZ$"],
    "r6_3_slus20883": [r"/NTSC_DI/LE/LOADING/LVL/SHIPYARD_A\.FBZ$",
                       r"/NTSC_DI/LE/LOADING/LVL/ALCATRAZ_A\.FBZ$",
                       r"/NTSC_DI/LE/LOADING/LVL/MENU\.FBZ$",
                       r"/NTSC_CD/LE/LANG_BG\.FBZ$"],
}

#: Lockdown ships no FBZ and no RSB: its loading art is a raw framebuffer dump.
#: 688,128 bytes is exactly 512 x 448 x 3, and decoding it on that assumption
#: produces the game's logo on black rather than noise, which is the check.
RAW_ART = {
    "lockdown_slus21144": (r"/PS2DATA/VIDEO/LOADING\.RAW$", 512, 448, "RGB"),
}

#: and the part of that frame the logo actually occupies, measured from the
#: non-black bounding box rather than guessed
RAW_EMBLEM = {
    "lockdown_slus21144": (0.020, 0.020, 0.580, 0.450),
}

#: where each game keeps the mark that sits in the corner of its menus, and the
#: fraction of that image the mark occupies (left, top, right, bottom)
EMBLEM = {
    "graw_slus21422": ([r"/CD/LE/GR3_2\.FBZ$"], (0.560, 0.050, 1.000, 0.355)),
    "gr2_slus21105": ([r"/DI/LE/LOADING/EN/LOADING_ASSAULT\.FBZ$",
                      r"/DI/LE/LOADING/EN/LOADING_SUPREMACY\.FBZ$"],
                     (0.075, 0.035, 0.945, 0.180)),
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
    # the wordmark is white over a lit olive plate, so the floor has to sit
    # above the plate rather than above black
    "gr2_slus21105": ("key", 150, 4.0),
    # Lockdown's wordmark is a dark red "Rainbow Six" over a bright white
    # "LOCKDOWN". Keying at the usual floor deletes the red half, so it is
    # lifted first and then keyed low.
    "lockdown_slus21144": ("lift", 18, 3.0),
}

#: Jungle Storm ships no lettering anywhere -- no wordmark texture on the disc,
#: and no corner mark in its own menus either -- so the ring its shell is built
#: around is all there is to badge the header with. These are drawn into the
#: middle of it, in the skin's own colour, so the header reads as a game rather
#: than as a circle.
#: (lines, colour, font files). Jungle Storm's own lettering is the
#: `new_font_revised` atlas it shares with Ghost Recon, and that atlas IS
#: Arial -- so setting the ring's text in Arial is the game's real face rather
#: than a lookalike, and it stops the mark reading as a caption pasted on.
EMBLEM_WORDMARK = {
    "jungle_storm_slus20820": (("GHOST RECON", "JUNGLE STORM"), "#d8efe9",
                               ("arialbd.ttf", "ariblk.ttf", "segoeuib.ttf")),
}

#: Lockdown keeps its real menu art in PS2DATA.PAK as `.PSX` textures. Those
#: decode to full RGBA (see `psx.py`), so its mark needs none of the luminance
#: keying the games that only ship a flattened loading screen do.
PSX_BANNERS = {
    "lockdown_slus21144": ["/PS2DATA/SHELL/ART/LOADING01.PSX",
                           "/PS2DATA/SHELL/ART/LOADING07.PSX",
                           "/PS2DATA/SHELL/ART/LOADING09.PSX"],
}
PSX_EMBLEM = {
    "lockdown_slus21144": "/PS2DATA/SHELL/ART/LOCKDOWN_SMALL.PSX",
}

#: Pieces of Lockdown's own shell sheet, by the box they occupy in it.
#: SHELL1 is 256x128 and packs the whole menu kit; these boxes were measured
#: off the decoded sheet, not guessed:
#:   rule    y 115..128 -- the blue rule the menus are banded with. It is two
#:           solid lines with a soft glow between and below them, and it is
#:           uniform across its width, so it stretches to any width cleanly.
#:   chevron x 16..48   -- the pale blue triangles used as scroll markers.
#:   metal   x 96..191  -- the brushed plate behind a highlighted entry.
PSX_CHROME = {
    "lockdown_slus21144": {
        "rule": ("/PS2DATA/SHELL/ART/SHELL1.PSX", (0, 115, 256, 128)),
        "chevron": ("/PS2DATA/SHELL/ART/SHELL1.PSX", (16, 0, 48, 16)),
        "metal": ("/PS2DATA/SHELL/ART/SHELL1.PSX", (96, 37, 191, 112)),
    },
}


#: A mark taken deliberately out of the user's replacement pack, rather than
#: found by matching. Ghost Recon 2's own loading screens carry its wordmark
#: small, dark and stamped into the art, which is why lifting it needs a hard
#: key; its memory-card screen carries the same wordmark large and lit, and the
#: pack holds that screen at 2048x2048. `upscale.better` declines it -- rightly,
#: it is a DIFFERENT screen rather than an upscale of the banner -- so it is
#: named here instead. The box was measured off the texture, not guessed.
#: (leading hash of the pack filename, crop as fractions of the texture)
PACK_EMBLEM = {
    "gr2_slus21105": ("b895175da311ea2e", (0.1040, 0.0366, 0.8955, 0.1738)),
    # Advanced Warfighter's title card, wordmark and skull and all
    "graw_slus21422": ("92dc602e4861b480", (0.1138, 0.1865, 0.9014, 0.7344)),
    # Jungle Storm's title screen. Worth noting against the older comment
    # below: the disc archives really do carry no wordmark, but the pack does,
    # so its header no longer has to make do with a reticle ring and lettering
    # set by hand.
    "jungle_storm_slus20820": ("e3a917d2330a5ba7",
                               (0.0337, 0.0732, 0.5430, 0.2222)),
}

#: How to key a mark that came out of the pack. It sits on a different ground
#: from the disc's own copy -- Jungle Storm's is light lettering over mid-green
#: rather than a dim ring on near-black -- so the floors that work on the disc
#: art would keep the background here. Chosen by keying each at several floors
#: and looking, not by reusing the disc's numbers.
PACK_EMBLEM_MODE = {
    "graw_slus21422": ("key", 130, 3.0),
    "jungle_storm_slus20820": ("key", 125, 3.0),
}


def pack_emblem(profile):
    """The pinned mark from the user's pack, or None when they have no pack."""
    spec = PACK_EMBLEM.get(getattr(profile, "id", None))
    if spec is None:
        return None
    try:
        from . import upscale
    except ImportError:
        return None
    prefix, box = spec
    img = upscale.pinned(profile.serial, prefix)
    if img is None:
        return None
    return _crop_frac(img.convert("RGB"), box)


def chrome_images(detection, cache_dir=None):
    """The game's own shell pieces, for the skin to build its chrome out of.

    Returns a name -> RGBA image dict, empty for the discs that ship nothing
    usable. The pieces are cached beside the banner so the disc is read once.
    """
    import os
    profile = getattr(detection, "profile", None)
    if profile is None:
        return {}
    spec = PSX_CHROME.get(profile.id)
    if not spec:
        return {}
    try:
        from PIL import Image
    except ImportError:
        return {}

    out, missing = {}, []
    for name in spec:
        path = (os.path.join(cache_dir, "%s.%s.png" % (profile.id, name))
                if cache_dir else None)
        if path and os.path.exists(path):
            try:
                out[name] = Image.open(path).convert("RGBA")
                continue
            except Exception:                     # noqa: BLE001
                pass
        missing.append(name)
    if not missing:
        return out

    try:
        from . import upscale
        from .iso import Iso
        with Iso(detection.path) as iso:
            sheets = {}
            for name in missing:
                src, box = spec[name]
                if src not in sheets:
                    sheet = psx_image(iso, profile, src)
                    # If the user keeps a PCSX2 replacement pack for this disc,
                    # the whole shell sheet is usually in it at 2x or 4x. The
                    # boxes are fractions of the sheet, so they scale with it.
                    big = upscale.better(profile.serial, sheet) if sheet else None
                    sheets[src] = (big or sheet,
                                   (big.width // sheet.width) if big else 1)
                sheet, factor = sheets[src]
                if sheet is None:
                    continue
                piece = sheet.crop(tuple(v * factor for v in box))
                out[name] = piece
                if cache_dir:
                    try:
                        piece.save(os.path.join(
                            cache_dir, "%s.%s.png" % (profile.id, name)), "PNG")
                    except Exception:             # noqa: BLE001
                        pass
    except Exception:                             # noqa: BLE001
        return out
    return out

#: the game's own menu art, by name, inside its archives
ARCHIVE_BANNERS = {
    "ghost_recon_slus20613": ["/MAIN_MENU_PS2.RSB", "/SHELL_BGD_PS2.RSB",
                              "/LOAD-SCREEN.RSB"],
    "jungle_storm_slus20820": ["/SHELL_BGD_PS2.RSB", "/LOAD_NEW_1.RSB",
                               "/LOAD_NEW_2.RSB"],
    "soaf_sles51180": ["/MAIN_MENU_PS2.RSB"],
}


#: Where each disc keeps the picture it shows while a mission loads, as a
#: format string taking the level stem and part. Only two discs have per-level
#: art at all -- Ghost Recon, Jungle Storm, Ghost Recon 2 and Advanced
#: Warfighter ship one generic loading screen between them, so a mission page
#: for those would be the same picture fifteen times.
#: Keyed by the art's own base name, not by (stem, part): Rainbow Six 3's
#: training levels are single packages with no A/B suffix, so a two-part
#: pattern cannot name them.
#: Which discs ship a picture per level, and where. Ghost Recon 2's live under
#: a language folder with a `.EN` extension rather than `.FBZ`, but the
#: container is the same one `fbz_to_image` already reads. Advanced Warfighter
#: is deliberately absent: it ships no still art per mission at all -- its
#: briefing is a 3D map with video -- so its cards carry no picture.
MISSION_ART = {
    "r6_3_slus20883": ("fbz", "/NTSC_DI/LE/LOADING/LVL/%s.FBZ"),
    "lockdown_slus21144": ("psx", "/PS2DATA/SHELL/ART/%s_SNAPSHOT.PSX"),
    "gr2_slus21105": ("fbz", "/DI/EN/LOADING%s.EN"),
}


def mission_art(detection, name, cache_dir=None):
    """The game's own loading screen, by its art base name, or None."""
    import os
    profile = getattr(detection, "profile", None)
    spec = MISSION_ART.get(getattr(profile, "id", None))
    if spec is None:
        return None
    kind, pattern = spec
    path = pattern % name
    cached = (os.path.join(cache_dir, "%s.%s.png"
                           % (profile.id, path.strip("/").replace("/", "_")))
              if cache_dir else None)
    if cached and os.path.exists(cached):
        try:
            from PIL import Image
            return Image.open(cached).convert("RGB")
        except Exception:                         # noqa: BLE001
            pass
    img = None
    try:
        from .iso import Iso
        with Iso(detection.path) as iso:
            if kind == "psx":
                img = psx_image(iso, profile, path)
                img = img.convert("RGB") if img is not None else None
            else:
                img = find_fbz(iso, path.replace(".", r"\.") + "$",
                               profile.archive_pattern)
    except Exception:                             # noqa: BLE001
        return None
    if img is not None and cached:
        try:
            img.save(cached, "PNG")
        except Exception:                         # noqa: BLE001
            pass
    return img


def psx_image(iso, profile, name):
    """Decode one `.PSX` out of Lockdown's PS2DATA.PAK, or None."""
    if not name:
        return None
    try:
        from . import psx
        from .nimitz import NimitzPak
    except ImportError:
        return None
    try:
        pak = NimitzPak(iso)
        ent = pak.files.get(name)
        if ent is None:
            return None
        return psx.to_image(pak.read_entry(ent))
    except Exception:                             # noqa: BLE001
        return None


def raw_image(iso, profile_id):
    """A PIL image from a raw framebuffer dump, or None."""
    spec = RAW_ART.get(profile_id)
    if spec is None:
        return None
    pattern, w, h, mode = spec
    ent = iso.find(pattern)
    if ent is None:
        return None
    depth = 3 if mode == "RGB" else 4
    want = w * h * depth
    data = iso.read(ent.lba, max(ent.size, want))[:want]
    if len(data) < want:
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    return Image.frombytes(mode, (w, h), data)


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
    for arc in open_archives(iso, archive_pattern or r"/(VOKES\d|GR2?|MENU)\.IMG$"):
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
            for name in PSX_BANNERS.get(profile.id, []):
                img = psx_image(iso, profile, name)
                if img is not None:
                    from . import upscale
                    img = (upscale.better(profile.serial, img) or img).convert("RGB")
                    break
            if img is None:
                img = raw_image(iso, profile.id)
            for pat in ([] if img is not None
                        else BANNER_PREFERENCE.get(profile.id, [])):
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
    from_pack = False
    # a mark decoded from a .PSX arrives with the game's own alpha, so it must
    # not go through the luminance key -- that would throw the real cutout away
    # and rebuild a worse one from brightness
    already_cut = False
    try:
        with Iso(detection.path) as iso:
            img = psx_image(iso, profile, PSX_EMBLEM.get(profile.id))
            already_cut = img is not None
            if img is None:
                # a pinned mark out of the user's pack, when they have one;
                # it is opaque, so it still goes through the key below
                img = pack_emblem(profile)
                from_pack = img is not None
            raw = None if img is not None else raw_image(iso, profile.id)
            if raw is not None and profile.id in RAW_EMBLEM:
                img = _crop_frac(raw, RAW_EMBLEM[profile.id])
            pats, box = EMBLEM.get(profile.id, (None, None))
            if img is not None:
                pats = None
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
                                         r"/(VOKES\d|GR2?|MENU)\.IMG$"):
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

    if already_cut:
        rgba = img.convert("RGBA")
        box = rgba.split()[-1].point(lambda a: 255 if a > 40 else 0).getbbox()
        if box and (box[2] - box[0]) > 8 and (box[3] - box[1]) > 8:
            rgba = rgba.crop(box)
        if cached:
            try:
                rgba.save(cached, "PNG")
            except Exception:                     # noqa: BLE001
                pass
        return rgba

    mode, floor, gain = (PACK_EMBLEM_MODE.get(profile.id) if from_pack else
                         None) or EMBLEM_MODE.get(profile.id, ("key", 118, 3.2))
    img = img.convert("RGB")
    if mode == "lift":
        # stamped dark into dark art: raise it before keying or nothing survives
        img = ImageOps.autocontrast(img, cutoff=2)
        img = ImageEnhance.Brightness(img).enhance(1.25)
        if gain >= 3.0:
            # Lockdown's mark is half deep crimson on black, which survives the
            # key but comes out almost unreadable at header size. Saturating
            # and lifting it again is the difference between a red smudge and a
            # legible wordmark.
            img = ImageEnhance.Color(img).enhance(1.6)
            img = ImageEnhance.Brightness(img).enhance(1.45)
    rgba = img.convert("RGBA")
    px = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, _a = px[x, y]
            lum = (r * 3 + g * 6 + b) // 10
            px[x, y] = (r, g, b, max(0, min(255, int((lum - floor) * gain))))
    # Lettering set by hand is a stand-in for a wordmark the disc does not
    # carry. Once the pack supplies the real one, stamping it again would
    # print the game's name twice.
    mark = None if from_pack else EMBLEM_WORDMARK.get(profile.id)
    if mark:
        rgba = _stamp_wordmark(rgba, mark[0], mark[1],
                               mark[2] if len(mark) > 2 else None)
    # Trim the fully transparent margin the key leaves behind. Without this a
    # mark that does not fill its own source -- Jungle Storm's ring sits in a
    # square of empty space -- is scaled to fit that empty space rather than to
    # fit itself, and ends up noticeably smaller than the wordmarks beside it.
    # threshold first: the key leaves a faint haze all the way to the edges on
    # some marks, and a plain getbbox() then trims nothing at all
    box = rgba.split()[-1].point(lambda a: 255 if a > 40 else 0).getbbox()
    if box and (box[2] - box[0]) > 8 and (box[3] - box[1]) > 8:
        rgba = rgba.crop(box)
    if cached:
        try:
            rgba.save(cached, "PNG")
        except Exception:                         # noqa: BLE001
            pass
    return rgba


def _stamp_wordmark(rgba, lines, colour, faces=None):
    """Set `lines` into the clear middle of a keyed emblem.

    The size is fitted rather than fixed: whatever the mark's own resolution
    turns out to be, the lettering ends up the same fraction of it, so the
    header looks the same after the thumbnail as it did here.
    """
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont
    except ImportError:
        return rgba
    w, h = rgba.size
    budget_w, budget_h = int(w * 0.60), int(h * 0.46)
    per_line = max(8, budget_h // len(lines))

    def load(size):
        for name in (faces or ("bahnschrift.ttf", "seguisb.ttf", "segoeuib.ttf")):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()

    probe = ImageDraw.Draw(rgba)
    size = per_line
    while size > 8:
        font = load(size)
        widest = max(probe.textlength(t, font=font) for t in lines)
        if widest <= budget_w and size * 1.18 * len(lines) <= budget_h:
            break
        size -= 1
    font = load(size)

    step = int(size * 1.18)
    y = (h - step * len(lines)) // 2
    glow = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for i, text in enumerate(lines):
        x = (w - probe.textlength(text, font=font)) / 2
        gd.text((x, y + i * step), text, font=font, fill=(0, 0, 0, 235))
    glow = glow.filter(ImageFilter.GaussianBlur(max(1, size // 6)))
    rgba.alpha_composite(glow)

    d = ImageDraw.Draw(rgba)
    rgb = tuple(int(colour.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    for i, text in enumerate(lines):
        x = (w - probe.textlength(text, font=font)) / 2
        d.text((x, y + i * step), text, font=font, fill=rgb + (255,))
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
                         r"/(VOKES\d|GR2?|MENU)\.IMG$")
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

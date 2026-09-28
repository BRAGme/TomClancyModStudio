"""Small drawn glyphs for the loadout choices.

Drawn, because the game's own icons cannot honestly be shipped yet
------------------------------------------------------------------

Two routes to the real artwork were opened and neither is finished.

The **PS2 disc** does carry them -- in `MENU.LIN`, as a chain of
`[Texture 8279][Palette 1027]` records, stride 9306, found by scanning for
`00 40 04` (a `None` terminator then `compactIndex(256)`). 43 icons decode
cleanly: 30 guns then 13 gadgets, linear raster, no swizzle. What is missing is
which icon is which. The chain order is not the export order and not the
`WS[]` table order either: index 9 really is a P90, but the slot the `WS[]`
order calls `ASSAULTM4` holds an AK with wooden furniture, and the one it calls
`AssaultAK47` holds a black polymer rifle. Some entries agree by coincidence,
which is exactly how a guessed mapping would slip through.

The **Xbox build** ships the same *weapons* in uncooked `.utx` packages where
names are certain (the PS2 tool's `utexture.py` reads them). But the artwork is not the
same -- correlating the two sets peaks around 0.5, far below what identical
images score -- so those icons are a different game's pictures, and shipping
them would be both wrong and a redistribution of someone else's art.

So: glyphs. When the PS2 chain is named, `for_choice` can extract from the
user's own loaded disc and cache, and nothing else in the GUI changes.

Shape says what class of thing it is and colour says what it does.

What they are for
-----------------

Not decoration -- recognition. A loadout page is a column of near-identical
words (MP5A4, MP5SD5, M16A2, M60E4) and the eye slides off them. Shape says
what class of thing it is and colour says what it does, so "did I give Weber a
machine gun or a sidearm" is answerable without reading. That is why the
silhouettes are deliberately crude and the colours carry the meaning.
"""

from __future__ import annotations

#: choice value -> (shape, colourRole). Shapes are drawn below; colour roles
#: resolve against the active palette so the glyphs follow the disc's skin.
KIND = {
    # primaries -- submachine guns
    "mp5sd5": ("smg", "cool"), "tmp": ("smg", "cool"),
    "ump": ("smg", "cool"), "mp5a4": ("smg", "cool"),
    "p90": ("smg", "cool"), "sr2": ("smg", "cool"),
    # primaries -- rifles
    "g36k": ("rifle", "cool"), "m4": ("rifle", "cool"),
    "famas": ("rifle", "cool"), "l85a1": ("rifle", "cool"),
    "g3a3": ("rifle", "cool"), "aug": ("rifle", "cool"),
    "tar21": ("rifle", "cool"), "galil": ("rifle", "cool"),
    "m16a2": ("rifle", "cool"),
    # primaries -- support
    "m60e4": ("lmg", "cool"),
    # sidearms
    "92fs": ("pistol", "cool"), "mk23": ("pistol", "cool"),
    "usp": ("pistol", "cool"), "deagle": ("pistol", "cool"),
    "psr2": ("pistol", "cool"),
    # thrown
    "frag": ("grenade", "danger"),
    "phosphorus": ("grenade", "hot"),
    "flashbang": ("grenade", "bright"),
    "smoke": ("grenade", "muted"),
    "teargas": ("grenade", "toxic"),
    # placed and worn
    "breaching": ("charge", "danger"),
    "gasmask": ("mask", "cool"),
    # launchers
    "gl_he": ("launcher", "danger"),
    "gl_rp": ("launcher", "danger"),
}

#: the settings whose choices get a glyph. Everything else is left alone --
#: an icon beside "Leave alone" on an unrelated dial would be noise.
_SLOT_SUFFIXES = ("_primary", "_secondary", "_item1", "_item2")
_SLOT_KEYS = ("team_gadget_1", "team_gadget_2")

#: drawn at this multiple and downsampled, which is what keeps the diagonals
#: from looking like staircases at 32 px wide.
_SS = 4

#: the box every icon is fitted into, and what a row must reserve for one
#: even when the choice has no icon -- otherwise "Leave alone" sits hard
#: against its button while every other label is pushed right, and the
#: list reads as ragged.
BOX_W, BOX_H = 96, 44

_cache = {}


def wants_icon(key: str) -> bool:
    """Is this setting a loadout slot?"""
    if key in _SLOT_KEYS:
        return True
    return any(key.endswith(s) for s in _SLOT_SUFFIXES)


def _colours(role):
    from . import theme
    p = theme.P
    return {
        "cool": (getattr(p, "text", "#d8dde3"), getattr(p, "dim", "#8b939c")),
        "danger": (getattr(p, "warn", "#d8863a"), getattr(p, "dim", "#8b939c")),
        "bright": ("#e9d98a", getattr(p, "dim", "#8b939c")),
        "muted": (getattr(p, "dim", "#8b939c"), getattr(p, "faint", "#5d656e")),
        "toxic": ("#9fc06a", getattr(p, "dim", "#8b939c")),
        "hot": ("#c8553d", getattr(p, "dim", "#8b939c")),
    }.get(role, (getattr(p, "text", "#d8dde3"),
                 getattr(p, "dim", "#8b939c")))


def _draw(shape, fg, accent, w, h):
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (w * _SS, h * _SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    W, H = w * _SS, h * _SS
    mid = H // 2

    def bar(x0, y0, x1, y1, col=None):
        d.rectangle([x0 * _SS, y0 * _SS, x1 * _SS, y1 * _SS],
                    fill=col or fg)

    if shape in ("rifle", "smg", "lmg"):
        long = {"rifle": 0.94, "smg": 0.74, "lmg": 0.98}[shape]
        body = int(w * long)
        bar(2, h // 2 - 1, body, h // 2 + 1)            # receiver
        bar(body - 3, h // 2 - 2, body, h // 2)          # muzzle end
        d.polygon([(4 * _SS, (mid + _SS)), (7 * _SS, H - _SS),
                   (10 * _SS, H - _SS), (8 * _SS, mid + _SS)], fill=fg)
        bar(int(w * 0.34), h // 2 - 3, int(w * 0.46), h // 2 - 1, accent)
        if shape == "lmg":
            bar(int(w * 0.40), h // 2 + 1, int(w * 0.60), h - 2, accent)
        elif shape != "smg":
            bar(int(w * 0.46), h // 2 + 1, int(w * 0.54), h - 3, accent)
    elif shape == "pistol":
        bar(int(w * 0.30), mid // _SS - 1, int(w * 0.74), mid // _SS + 1)
        d.polygon([(int(w * 0.34) * _SS, mid + _SS),
                   (int(w * 0.30) * _SS, H - _SS),
                   (int(w * 0.46) * _SS, H - _SS),
                   (int(w * 0.46) * _SS, mid + _SS)], fill=fg)
    elif shape == "grenade":
        r = int(min(w, h) * 0.30)
        cx, cy = int(w * 0.50), h // 2 + 1
        d.ellipse([(cx - r) * _SS, (cy - r) * _SS,
                   (cx + r) * _SS, (cy + r) * _SS], fill=fg)
        bar(cx - 1, cy - r - 3, cx + 1, cy - r, accent)
    elif shape == "charge":
        bar(int(w * 0.32), 3, int(w * 0.68), h - 3)
        bar(int(w * 0.40), 1, int(w * 0.44), 3, accent)
        bar(int(w * 0.56), 1, int(w * 0.60), 3, accent)
    elif shape == "mask":
        cx = int(w * 0.46)
        d.ellipse([(cx - 6) * _SS, 2 * _SS, (cx + 6) * _SS, (h - 2) * _SS],
                  fill=fg)
        # eyepieces, which is what makes it read as a mask and not a grenade
        d.ellipse([(cx - 4) * _SS, (h // 2 - 3) * _SS,
                   (cx - 1) * _SS, (h // 2) * _SS], fill=accent)
        d.ellipse([(cx + 1) * _SS, (h // 2 - 3) * _SS,
                   (cx + 4) * _SS, (h // 2) * _SS], fill=accent)
        # filter cannister off the side
        bar(cx + 6, h // 2 - 1, cx + 10, h // 2 + 2, accent)
    elif shape == "launcher":
        bar(3, h // 2 - 2, int(w * 0.86), h // 2 + 2)
        d.ellipse([int(w * 0.80) * _SS, (h // 2 - 3) * _SS,
                   int(w * 0.94) * _SS, (h // 2 + 3) * _SS], fill=accent)
    else:
        return None
    return im.resize((w, h), Image.LANCZOS)


def _asset_dir():
    import os
    import sys
    base = getattr(sys, "_MEIPASS", os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "assets", "gearicons")


def _class_of(value):
    """The weapon class a choice names.

    The PS2 tool answers this from its own kit tables, which are PS2 loadout
    data and do not describe any of the PC games. The PC side has a better
    source and is not wired to it yet: Lockdown names a picture per weapon in
    the gun file itself (`gunpicture = "r_an94.rsb"`), and Raven Shield keeps
    its inventory art in `Inventory_t.utx`. Until that is read, no icon --
    which the caller already handles, because a choice with no icon simply
    gets no icon column.
    """
    return None


def _fit(im, w, h):
    """Trim the transparent margin, then fit what is left into `w` by `h`.

    The art is a 128x64 canvas with the weapon floating in the middle of it --
    measured across the set, the drawn part is about 72x25, so more than half
    the picture is empty. Pasting that straight into a row-height box renders
    the gun about six pixels tall, which is what made the first attempt look
    like smudges. Trimming to the alpha bounding box first is worth roughly a
    3.5x gain in how big the weapon actually appears.

    Fitting to a common box rather than scaling each by itself keeps a stubby
    pistol and a long rifle at the same visual weight; content heights across
    the set run 17 to 32 px, so scaling each to fill would make the pistols
    enormous.
    """
    from PIL import Image
    bbox = im.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    if bbox:
        im = im.crop(bbox)
    scale = min(w / im.width, h / im.height)
    size = (max(1, int(im.width * scale)), max(1, int(im.height * scale)))
    im = im.resize(size, Image.LANCZOS)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(im, ((w - size[0]) // 2, (h - size[1]) // 2), im)
    return out


def _real(value, w, h):
    """The game's own icon for this choice, trimmed and scaled, or None."""
    import os
    cls = _class_of(value)
    if not cls:
        return None
    path = os.path.join(_asset_dir(), cls.split(".")[-1].lower() + ".png")
    if not os.path.exists(path):
        return None
    from PIL import Image
    return _fit(Image.open(path).convert("RGBA"), w, h)


def for_choice(key: str, value: str, px=None):
    """A Tk image for this choice, or None to leave the row plain.

    The game's own art first, a drawn glyph second, nothing third. Cached per
    (value, size) because a loadout page builds the same icon for three
    operatives and Tk would otherwise hold three copies of each.
    """
    if not wants_icon(key) or value in (None, "", "stock"):
        return None
    # Sized from the art rather than from the row. Measured across the set,
    # trimmed content runs up to 101 px wide (the grenade launcher) and up
    # to 37 tall (the frag grenade), and the two orientations fight each
    # other: a short box starves the portrait gadgets, which is why 60x26
    # rendered the flashbang at 15 px wide. 96x44 clears the tallest item
    # and leaves the guns near their native width.
    w = BOX_W if px is None else px
    h = BOX_H if px is None else max(12, int(w * 0.46))
    ck = (value, w)
    if ck in _cache:
        return _cache[ck]
    im = None
    try:
        im = _real(value, w, h)             # a named extraction, once it exists
    except Exception:                       # noqa: BLE001
        im = None
    if im is None:
        spec = KIND.get(value)
        if spec is None:
            return None
        try:
            shape, role = spec
            fg, accent = _colours(role)
            im = _draw(shape, fg, accent, w, h)
        except Exception:                   # noqa: BLE001
            return None
    if im is None:
        return None
    try:
        from PIL import ImageTk
        img = ImageTk.PhotoImage(im)
    except Exception:                       # noqa: BLE001
        # An icon is a nicety. If Tk is unhappy the row still works.
        return None
    _cache[ck] = img
    return img


def forget():
    """Drop the cache, for a skin change that repaints every row."""
    _cache.clear()

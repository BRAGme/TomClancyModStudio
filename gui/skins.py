"""One skin per disc, so the tool looks like the menu you would be standing in.

Two chrome families cover the shelf, in six colourways:

  ``rs3``  Rainbow Six 3's gunmetal HUD -- translucent slate panels with a
           hairline light edge, corners cut at 45 degrees, wide letterspaced
           uppercase titles, and a red tab on the selected row. Advanced
           Warfighter is the same chrome in its own near-black and teal, which
           is what its menus and loading screens actually are.

  ``gr``   The console shell the Red Storm games use -- flat translucent panels
           inside a bright rule, rounded buttons that fill solid when selected,
           and a heavy white title. Ghost Recon is gold on navy, Jungle Storm
           the same in teal, Sum of All Fears in olive, and Ghost Recon 2 in the
           lime-on-drab its own screens are framed in.

Every skin ranges its title and its disc line to the right, so the six look
like one tool wearing six uniforms rather than six different tools.

Colours were read off the games themselves rather than invented; the artwork is
pulled out of the user's own disc at run time and cached, never redistributed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass
class Palette:
    #: which chrome painter to use
    chrome: str = "rs3"

    bg: str = "#0c0f13"          # window behind everything
    veil: str = "#0a0d11"        # what the background art fades into
    panel: str = "#161b22"       # a card or a group box
    panel2: str = "#1d242c"      # a raised strip inside one
    edge: str = "#8ea3b5"        # the bright hairline
    edge_dim: str = "#38444f"    # the dim one
    text: str = "#c8d6e0"
    dim: str = "#8593a0"
    faint: str = "#59656f"
    title: str = "#dbe6ee"

    accent: str = "#9fb8cc"      # rules, ticks, slider fill
    accent_dim: str = "#5d7a90"
    sel_fill: str = "#2b333c"    # selected nav row
    sel_text: str = "#eaf2f8"
    tab: str = "#b01f22"         # the little red marker

    warn: str = "#d8a23a"
    bad: str = "#d2604a"
    good: str = "#7fc14a"

    #: title treatment
    title_align: str = "right"
    title_track: int = 7         # extra pixels between letters
    title_upper: bool = True
    title_font: str = "Bahnschrift Light"
    body_font: str = "Segoe UI"
    bold_font: str = "Segoe UI Semibold"

    #: PS2 face-button glyph colours, used on the action bar
    glyph_cross: str = "#5b93de"
    glyph_triangle: str = "#46b79c"


RS3 = Palette()

GR = Palette(
    chrome="gr",
    bg="#091321",
    veil="#07101c",
    panel="#14243f",
    panel2="#1d3255",
    edge="#d3a83b",
    edge_dim="#6b5a25",
    text="#b9d6f2",
    dim="#7fa3c6",
    faint="#4d6a86",
    title="#ffffff",
    accent="#d3a83b",
    accent_dim="#8d6f24",
    sel_fill="#e2b944",
    sel_text="#14243f",
    tab="#d3a83b",
    warn="#f0c24a",
    bad="#e2705a",
    good="#8fd257",
    title_align="right",
    title_track=0,
    title_upper=False,
    title_font="Verdana",
    body_font="Segoe UI",
    bold_font="Verdana Bold",
    glyph_cross="#5b93de",
    glyph_triangle="#46b79c",
)

JS = Palette(
    chrome="gr",
    bg="#061513",
    veil="#04100f",
    panel="#0e2f2d",
    panel2="#154340",
    edge="#d3a83b",
    edge_dim="#6b5a25",
    text="#bfe6e0",
    dim="#7fbdb5",
    faint="#4a7a75",
    title="#ffffff",
    accent="#d3a83b",
    accent_dim="#8d6f24",
    sel_fill="#e2b944",
    sel_text="#0e2f2d",
    tab="#d3a83b",
    warn="#f0c24a",
    bad="#e2705a",
    good="#8fd257",
    title_align="right",
    title_track=0,
    title_upper=False,
    title_font="Verdana",
    body_font="Segoe UI",
    bold_font="Verdana Bold",
    glyph_cross="#5b93de",
    glyph_triangle="#46b79c",
)

#: Advanced Warfighter is Rainbow Six 3's engine and its menus follow that
#: house style -- but not its colour. Every one of its own screens is near-black
#: with one hue on it, and that hue measures a flat 180 degrees: the frosted
#: band under the logo samples #2f9090, the bright edge above it #479696. So it
#: gets the gunmetal chrome in teal rather than Rainbow's slate.
GRAW = replace(
    RS3,
    bg="#070b0b",
    veil="#050808",
    panel="#0f1717",
    panel2="#162323",
    edge="#5fcfcf",
    edge_dim="#2b4d4d",
    text="#c2dede",
    dim="#84a9a9",
    faint="#517070",
    title="#e8f8f8",
    accent="#45bcbc",
    accent_dim="#256a6a",
    sel_fill="#15302f",
    sel_text="#dffafa",
    tab="#2f9090",
    good="#5fcf9a",
    glyph_triangle="#45bcbc",
)

#: Ghost Recon 2's shell is the Red Storm frame again, drab olive ruled in the
#: lime its wordmark and every panel edge are drawn in (#b4e198, measured off
#: the language screens).
GR2 = replace(
    GR,
    bg="#0b120a",
    veil="#080d07",
    panel="#182415",
    panel2="#23321c",
    edge="#b4e198",
    edge_dim="#4e6b3f",
    text="#d5e9c8",
    dim="#9bba8b",
    faint="#66805a",
    accent="#b4e198",
    accent_dim="#6f9457",
    sel_fill="#b4e198",
    sel_text="#182415",
    tab="#b4e198",
    warn="#e2d05a",
    good="#9fe57a",
)

SOAF = replace(GR, bg="#0d1410", veil="#0a1109", panel="#16241a",
               panel2="#1e3223", text="#c3dfc6", dim="#8bb492", faint="#5a7d60",
               sel_text="#16241a")

BY_PROFILE = {
    "r6_3_slus20883": RS3,
    "ghost_recon_slus20613": GR,
    "jungle_storm_slus20820": JS,
    "graw_slus21422": GRAW,
    "soaf_sles51180": SOAF,
    "gr2_slus21105": GR2,
}

DEFAULT = RS3


def for_profile(profile) -> Palette:
    if profile is None:
        return DEFAULT
    return BY_PROFILE.get(getattr(profile, "id", ""), DEFAULT)


# ---------------------------------------------------------------------------
# chrome
# ---------------------------------------------------------------------------

def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    """Blend two hex colours, t=0 gives a."""
    ra, rb = _hex(a), _hex(b)
    return "#%02x%02x%02x" % tuple(int(ra[i] + (rb[i] - ra[i]) * t) for i in range(3))


def panel_points(x0, y0, x1, y1, cut, corners="tr,bl"):
    """A rectangle with some corners cut at 45 degrees, as a flat point list."""
    want = set(corners.split(","))
    pts = []
    pts += [x0 + cut, y0] if "tl" in want else [x0, y0]
    pts += [x1 - cut, y0, x1, y0 + cut] if "tr" in want else [x1, y0]
    pts += [x1, y1 - cut, x1 - cut, y1] if "br" in want else [x1, y1]
    pts += [x0 + cut, y1, x0, y1 - cut] if "bl" in want else [x0, y1]
    if "tl" in want:
        pts += [x0, y0 + cut]
    return pts


def round_points(x0, y0, x1, y1, r):
    r = max(0, min(r, (x1 - x0) // 2, (y1 - y0) // 2))
    return [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
            x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]


def paint_panel(canvas, p: Palette, x0, y0, x1, y1, px, tag="chrome", raised=False):
    """Draw one content panel in the active game's style."""
    if x1 - x0 < 4 or y1 - y0 < 4:
        return
    fill = p.panel2 if raised else p.panel
    if p.chrome == "rs3":
        cut = px(11)
        canvas.create_polygon(panel_points(x0, y0, x1, y1, cut),
                              fill=fill, outline=p.edge_dim, width=1,
                              tags=tag)
        # the bright inner hairline the game draws just inside the edge
        inset = px(3)
        canvas.create_polygon(panel_points(x0 + inset, y0 + inset,
                                           x1 - inset, y1 - inset, cut - inset),
                              fill="", outline=mix(p.edge_dim, p.edge, 0.45),
                              width=1, tags=tag)
        # a lit strip along the top, which is what makes it read as metal
        canvas.create_line(x0 + cut, y0 + 1, x1 - cut, y0 + 1,
                           fill=mix(p.edge_dim, p.edge, 0.75), tags=tag)
    else:
        canvas.create_polygon(round_points(x0, y0, x1, y1, px(6)),
                              smooth=True, fill=fill,
                              outline=p.edge_dim, width=px(1), tags=tag)


def paint_group(canvas, p: Palette, x0, y0, x1, y1, px, tag="chrome"):
    """The outer box that wraps a whole page. Ghost Recon rules it in gold."""
    if x1 - x0 < 4 or y1 - y0 < 4:
        return
    if p.chrome == "rs3":
        cut = px(15)
        canvas.create_polygon(panel_points(x0, y0, x1, y1, cut, "tl,tr,br,bl"),
                              fill=p.panel, outline=p.edge, width=1, tags=tag)
        canvas.create_line(x0 + cut, y0 + px(4), x1 - cut, y0 + px(4),
                           fill=p.edge_dim, tags=tag)
    else:
        canvas.create_polygon(round_points(x0, y0, x1, y1, px(8)), smooth=True,
                              fill=p.panel, outline=p.edge, width=px(2), tags=tag)


def paint_button(canvas, p: Palette, x0, y0, x1, y1, px, selected, hover=False,
                 tag="chrome"):
    """One navigation row."""
    if p.chrome == "rs3":
        cut = px(7)
        base = p.sel_fill if selected else (p.panel2 if hover else p.panel)
        canvas.create_polygon(panel_points(x0, y0, x1, y1, cut, "tr,bl"),
                              fill=base,
                              outline=p.edge if selected else p.edge_dim,
                              width=1, tags=tag)
        canvas.create_line(x0 + cut, y0 + 1, x1 - cut, y0 + 1,
                           fill=mix(base, p.edge, 0.5 if selected else 0.25),
                           tags=tag)
        # the red marker the game puts against the active row
        w = px(9)
        canvas.create_rectangle(x0 + px(2), y0 + px(3), x0 + px(2) + w,
                                y1 - px(3),
                                fill=p.tab if selected else mix(p.panel, p.bg, 0.6),
                                outline="", tags=tag)
    else:
        r = px(5)
        if selected:
            canvas.create_polygon(round_points(x0, y0, x1, y1, r), smooth=True,
                                  fill=p.sel_fill, outline=p.accent_dim,
                                  width=px(2), tags=tag)
            canvas.create_line(x0 + r, y0 + px(2), x1 - r, y0 + px(2),
                               fill=mix(p.sel_fill, "#ffffff", 0.45), tags=tag)
        else:
            canvas.create_polygon(round_points(x0, y0, x1, y1, r), smooth=True,
                                  fill=p.panel2 if hover else p.panel,
                                  outline=mix(p.panel2, p.text, 0.30),
                                  width=px(1), tags=tag)


# ---------------------------------------------------------------------------
# lettering
# ---------------------------------------------------------------------------

def _font(name, size):
    from PIL import ImageFont
    files = {
        "Bahnschrift Light": ["bahnschrift.ttf", "segoeuil.ttf"],
        "Verdana": ["verdana.ttf", "segoeui.ttf"],
        "Verdana Bold": ["verdanab.ttf", "segoeuib.ttf"],
        "Segoe UI": ["segoeui.ttf"],
        "Segoe UI Semibold": ["seguisb.ttf", "segoeuib.ttf"],
    }.get(name, ["segoeui.ttf"])
    for f in files:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def draw_tracked(draw, xy, text, font, fill, track=0, anchor_right=False):
    """Letterspaced text. Pillow has no tracking, so step glyph by glyph."""
    x, y = xy
    if anchor_right:
        total = sum(draw.textlength(ch, font=font) + track for ch in text) - track
        x -= total
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + track
    return x


def title_image(text, p: Palette, px, width, height, subtitle="", emblem=None):
    """The header band: chrome, the game's emblem, and the page title."""
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageTk
    except ImportError:
        return None

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    label = text.upper() if p.title_upper else text
    big = _font(p.title_font, px(30))
    small = _font(p.body_font, px(11))

    # A fixed mark box, so the title lands in the same place whether or not a
    # given disc actually has a badge -- Jungle Storm's has to line up with
    # Ghost Recon's or the two skins look unrelated side by side.
    left = px(26)
    box_w, box_h = px(250), height - px(30)
    if emblem is not None:
        em = emblem.convert("RGBA")
        em.thumbnail((box_w, box_h), Image.LANCZOS)
        img.alpha_composite(em, (left + (box_w - em.width) // 2,
                                 (height - em.height) // 2))
    pad = left + box_w + px(22)

    right = p.title_align != "left"
    tx = width - px(30) if right else pad

    if p.chrome == "rs3":
        # the angled rule the game runs under its title
        y = height - px(15)
        cut = px(14)
        d.line([(pad, y), (width - px(26) - cut, y), (width - px(26), y - cut)],
               fill=p.edge_dim, width=px(2))
        draw_tracked(d, (tx, px(10)), label, big, p.title,
                     track=px(p.title_track), anchor_right=right)
        if subtitle:
            draw_tracked(d, (tx, height - px(40)), subtitle, small, p.dim,
                         track=px(1), anchor_right=right)
    else:
        # heavy white title with the dark halo the console shells use
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sx = tx - d.textlength(label, font=big) if right else tx
        sd.text((sx + px(2), px(8)), label, font=big, fill=(0, 0, 0, 210))
        shadow = shadow.filter(ImageFilter.GaussianBlur(px(3)))
        img.alpha_composite(shadow)
        d.text((sx, px(6)), label, font=big, fill=p.title)
        if subtitle:
            ux = tx - d.textlength(subtitle, font=small) if right else tx + px(3)
            d.text((ux, height - px(34)), subtitle, font=small, fill=p.dim)
    return ImageTk.PhotoImage(img)


def glyph(canvas, p: Palette, kind, cx, cy, r, tag="glyph"):
    """A PlayStation face button, drawn rather than lifted from the disc."""
    if kind == "cross":
        c = p.glyph_cross
        canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=c,
                           width=max(1, r // 7), tags=tag)
        k = r * 0.46
        canvas.create_line(cx - k, cy - k, cx + k, cy + k, fill=c,
                           width=max(2, r // 5), tags=tag)
        canvas.create_line(cx - k, cy + k, cx + k, cy - k, fill=c,
                           width=max(2, r // 5), tags=tag)
    else:
        c = p.glyph_triangle
        canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=c,
                           width=max(1, r // 7), tags=tag)
        k = r * 0.52
        canvas.create_polygon(cx, cy - k, cx + k, cy + k * 0.8, cx - k,
                              cy + k * 0.8, fill="", outline=c,
                              width=max(2, r // 5), tags=tag)

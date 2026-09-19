"""One skin per disc, so the tool looks like the menu you would be standing in.

Four chrome families cover the shelf, in seven colourways:

  ``rs3``  Rainbow Six 3's gunmetal HUD -- translucent slate panels with a
           hairline light edge, corners cut at 45 degrees, wide letterspaced
           uppercase titles, and a red tab on the selected row.

  ``graw`` Advanced Warfighter's tactical display. Not Rainbow Six 3's chrome
           in another colour -- a different shape: every frame is a rounded
           rectangle drawn twice, an outer bright cyan stroke and a second one
           inset a few pixels inside it, over near-black. Menu rows are bars
           with the top-right corner sheared off, each one led by a small solid
           triangle, and the selected row inverts to a pale fill with dark
           lettering. Read off the language, profile and difficulty screens.

  ``lock`` Lockdown's Nimitz shell. Square, banded and horizontal: a page
           title in white letterspaced caps on a dark plate whose right end is
           sheared off, with a bright blue rule running the FULL width of the
           screen through it; menu entries as full-width bands rather than
           buttons, the selected one a pale grey plate; and every section
           separated by another of those full-width rules. Taken from the
           game's own menus.

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
    faint: str = "#788693"   # 4.6:1 on panel -- WCAG AA for small text
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
    #: the ink the page title is set in, when the game's own lettering is not
    #: simply white -- Sum of All Fears' wordmark is gold, Lockdown's is red
    #: over white. Empty means "use `title`".
    title_ink: str = ""
    #: a colour drawn behind the title, offset, the way the game's logo is
    title_shadow: str = ""
    title_align: str = "right"
    title_track: int = 7         # extra pixels between letters
    title_upper: bool = True
    title_font: str = "Unispace Bold, Bahnschrift SemiBold, Segoe UI Semibold"
    body_font: str = "Bahnschrift, Segoe UI"
    bold_font: str = "Bahnschrift SemiBold, Segoe UI Semibold"

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
    faint="#7290ae",
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
    title_font="Arial Black, Segoe UI Black",
    body_font="Arial, Segoe UI",
    bold_font="Arial Bold, Segoe UI Semibold",
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
    faint="#5f9d96",
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
    title_font="Arial Black, Segoe UI Black",
    body_font="Arial, Segoe UI",
    bold_font="Arial Bold, Segoe UI Semibold",
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
    chrome="graw",
    bg="#04090a",
    veil="#030607",
    panel="#08181a",
    panel2="#0d2427",
    edge="#3ee0e0",
    edge_dim="#1d5c5f",
    text="#cdeced",
    dim="#8fb9ba",
    faint="#5e888a",
    title="#e8fbfb",
    accent="#3ee0e0",
    accent_dim="#227e80",
    # the game inverts the selected row: pale plate, dark lettering
    sel_fill="#9fc9c9",
    sel_text="#062022",
    tab="#3ee0e0",
    good="#5fcf9a",
    glyph_triangle="#3ee0e0",
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
    faint="#749267",
    accent="#b4e198",
    accent_dim="#6f9457",
    sel_fill="#b4e198",
    sel_text="#182415",
    tab="#b4e198",
    warn="#e2d05a",
    good="#9fe57a",
    title_font="Bahnschrift SemiBold SemiConden, Bahnschrift SemiBold, "
               "Segoe UI Semibold",
    body_font="Franklin Gothic Medium, Segoe UI",
    bold_font="Franklin Gothic Medium, Segoe UI Semibold",
)

SOAF = replace(GR, bg="#0d1410", veil="#0a1109", panel="#16241a",
               panel2="#1e3223", text="#c3dfc6", dim="#8bb492", faint="#6a9371",
               sel_text="#16241a",
               title_ink="#d2a047",
               title_shadow="#4a3208",
               title_font="Impact, Arial Black",
               body_font="Corbel, Segoe UI",
               bold_font="Corbel Bold, Segoe UI Semibold")

#: Measured off the game's own loading frame rather than invented: the ground
#: is flat black (30,856 of 36,000 sampled pixels are #000000), the plate is a
#: cold steel blue clustered tightly at hue 208-210 (#1c252d through #293642),
#: and the lettering is #eaeaea. The crimson is the "Rainbow Six" half of the
#: wordmark. It keeps the cut-cornered chrome; see the note in the profile for
#: why the shape language is not copied from the game's own shell textures.
LOCKDOWN = replace(
    RS3,
    chrome="lock",
    bg="#16233a",
    veil="#0e1728",
    panel="#1e2e47",
    panel2="#2b3f5c",
    edge="#7fc4ea",
    edge_dim="#3c5878",
    text="#dce8f4",
    dim="#9fb6cd",
    faint="#8598ac",
    title="#ffffff",
    accent="#7fc4ea",
    accent_dim="#42648a",
    sel_fill="#5a6b80",
    sel_text="#ffffff",
    tab="#7fc4ea",
    title_shadow="#8c1c16",
    warn="#e0b552",
    bad="#da7d6b",
    good="#7fc14a",
    title_track=6,
)

BY_PROFILE = {
    "r6_3_slus20883": RS3,
    "ghost_recon_slus20613": GR,
    "jungle_storm_slus20820": JS,
    "graw_slus21422": GRAW,
    "soaf_sles51180": SOAF,
    "gr2_slus21105": GR2,
    "lockdown_slus21144": LOCKDOWN,
}

DEFAULT = RS3


def for_profile(profile) -> Palette:
    if profile is None:
        return DEFAULT
    return BY_PROFILE.get(getattr(profile, "id", ""), DEFAULT)


# ---------------------------------------------------------------------------
# chrome
# ---------------------------------------------------------------------------

def angular(p: Palette) -> bool:
    """True for the skins whose controls are cut and sharp rather than rounded.

    Rainbow Six 3 and Advanced Warfighter both draw square marks, cut corners
    and letterspaced uppercase; the Red Storm shell the other four wear draws
    rounded plates and sentence case. Everything that has to choose between
    those two idioms asks this rather than testing for one chrome by name --
    which is how Advanced Warfighter ended up with gold-shell toggles when it
    stopped being an alias of Rainbow Six 3.
    """
    return p.chrome in ("rs3", "graw", "lock")


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


def shear_points(x0, y0, x1, y1, cut):
    """A bar with the top-right corner sheared off, the way GRAW draws a row."""
    return [x0, y0, x1 - cut, y0, x1, y0 + cut, x1, y1, x0, y1]


def _graw_frame(canvas, p: Palette, x0, y0, x1, y1, px, tag, fill, stroke,
                inner=True):
    """The double-stroked rounded rectangle every GRAW panel is built from."""
    r = px(9)
    canvas.create_polygon(round_points(x0, y0, x1, y1, r), smooth=True,
                          fill=fill, outline=stroke, width=px(2), tags=tag)
    if inner and (x1 - x0) > px(30) and (y1 - y0) > px(30):
        d = px(6)
        canvas.create_polygon(round_points(x0 + d, y0 + d, x1 - d, y1 - d,
                                           max(px(3), r - px(3))),
                              smooth=True, fill="",
                              outline=mix(fill, stroke, 0.55), width=px(1),
                              tags=tag)


#: Rows of Lockdown's own rule, lifted out of its shell sheet by `set_textures`
#: as (r, g, b, alpha) top to bottom. The rule is uniform across its width, so
#: the game's pixels can be composited as lines instead of stretched as a
#: bitmap -- same colours, but crisp at any width and any display scale, and
#: with no image cache to invalidate when the window resizes.
LOCK_RULE_ROWS: list = []

#: Lockdown's menu bands, measured off the game's own main menu rather than
#: invented: an ordinary band runs #3b3d45 to #24272f, and the selected one is
#: DARKER and neutral -- #393939 to #191a1a under a lit #575757 top edge -- not
#: the paler plate a highlight would normally be.
LOCK_BAND = ((0x3b, 0x3d, 0x45), (0x24, 0x27, 0x2f))
LOCK_BAND_SEL = ((0x39, 0x39, 0x39), (0x19, 0x1a, 0x1a))
LOCK_BAND_EDGE = "#575757"


def set_textures(images):
    """Hand the skin the game's own shell pieces, or {} to drop them."""
    LOCK_RULE_ROWS.clear()
    rule = (images or {}).get("rule")
    if rule is None:
        return
    try:
        rgba = rule.convert("RGBA")
        px = rgba.load()
        mid = rgba.width // 2
        for y in range(rgba.height):
            LOCK_RULE_ROWS.append(px[mid, y])
    except Exception:                             # noqa: BLE001
        LOCK_RULE_ROWS.clear()


def _blend(rgb, a, under):
    """Composite one texture row over the colour it is drawn on."""
    ur, ug, ub = int(under[1:3], 16), int(under[3:5], 16), int(under[5:7], 16)
    f = a / 255.0
    return "#%02x%02x%02x" % (int(rgb[0] * f + ur * (1 - f)),
                              int(rgb[1] * f + ug * (1 - f)),
                              int(rgb[2] * f + ub * (1 - f)))


def _lock_rule(canvas, p: Palette, x0, x1, y, px, tag, bright=True, under=None):
    """The full-width blue rule Lockdown runs through everything.

    In the game it does not stop at the edge of the thing it belongs to -- it
    crosses the whole screen -- which is most of what makes the menus read as
    banded rather than boxed. It is not one line either: two solid strokes with
    a soft glow between and below them, which is why it is worth taking the
    game's own pixels rather than drawing a hairline.
    """
    rows = LOCK_RULE_ROWS
    if not rows:
        colour = p.edge if bright else p.edge_dim
        canvas.create_line(x0, y, x1, y, fill=colour, width=px(1), tags=tag)
        return
    under = under or p.panel
    height = px(8)
    for i in range(height):
        r, g, b, a = rows[min(len(rows) - 1, i * len(rows) // height)]
        if not a:
            continue
        if not bright:
            a = int(a * 0.45)
        canvas.create_line(x0, y + i - px(1), x1, y + i - px(1),
                           fill=_blend((r, g, b), a, under), tags=tag)


def _lock_band(canvas, x0, y0, x1, y1, top, bottom, tag, cut=0):
    """A menu band, shaded the way the game shades its own.

    `cut` is the 45-degree shear taken off the top-right corner, so the shading
    has to follow the same diagonal `shear_points` describes rather than stop
    short of it and leave a notch.
    """
    span = max(1, y1 - y0)
    for i in range(span):
        f = i / float(span)
        right = x1 - cut + i if i < cut else x1
        canvas.create_line(
            x0, y0 + i, right, y0 + i,
            fill="#%02x%02x%02x" % tuple(int(top[c] + (bottom[c] - top[c]) * f)
                                         for c in range(3)),
            tags=tag)


def paint_panel(canvas, p: Palette, x0, y0, x1, y1, px, tag="chrome", raised=False):
    """Draw one content panel in the active game's style."""
    if x1 - x0 < 4 or y1 - y0 < 4:
        return
    fill = p.panel2 if raised else p.panel
    if p.chrome == "lock":
        canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline="", tags=tag)
        _lock_rule(canvas, p, x0, x1, y0, px, tag, under=fill)
        _lock_rule(canvas, p, x0, x1, y1, px, tag, bright=False, under=fill)
        return
    if p.chrome == "graw":
        _graw_frame(canvas, p, x0, y0, x1, y1, px, tag, fill,
                    mix(p.edge_dim, p.edge, 0.55), inner=False)
        return
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
    if p.chrome == "lock":
        canvas.create_rectangle(x0, y0, x1, y1, fill=p.panel, outline="",
                                tags=tag)
        _lock_rule(canvas, p, x0, x1, y0 + px(1), px, tag, under=p.panel)
        _lock_rule(canvas, p, x0, x1, y1 - px(1), px, tag, under=p.panel)
        return
    if p.chrome == "graw":
        _graw_frame(canvas, p, x0, y0, x1, y1, px, tag, p.panel, p.edge)
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
    if p.chrome == "lock":
        # A full-width band with the right end sheared off, the way the game
        # sets its own menu entries and page titles. The selected band is
        # DARKER than the rest and neutral rather than blue -- that is how the
        # game marks it, together with a lit top edge and its rule underneath.
        cut = int((y1 - y0) * 0.62)
        top, bottom = (LOCK_BAND_SEL if selected else LOCK_BAND)
        if hover and not selected:
            top = tuple(min(255, c + 14) for c in top)
            bottom = tuple(min(255, c + 14) for c in bottom)
        _lock_band(canvas, x0, y0, x1, y1, top, bottom, tag, cut)
        if selected:
            canvas.create_line(x0, y0, x1 - cut, y0, fill=LOCK_BAND_EDGE,
                               width=px(1), tags=tag)
            _lock_rule(canvas, p, x0, x1, y1 - px(1), px, tag,
                       under="#%02x%02x%02x" % bottom)
        return
    if p.chrome == "graw":
        cut = int((y1 - y0) * 0.55)
        base = p.sel_fill if selected else (p.panel2 if hover else p.panel)
        stroke = p.edge if selected else mix(p.edge_dim, p.edge,
                                             0.5 if hover else 0.2)
        canvas.create_polygon(shear_points(x0, y0, x1, y1, cut), fill=base,
                              outline=stroke, width=px(1), tags=tag)
        # the solid wedge the game puts at the head of every row
        m = px(7)
        cy = (y0 + y1) // 2
        mx = x0 + px(8)
        canvas.create_polygon(mx, cy - m, mx + m * 1.5, cy, mx, cy + m,
                              fill=p.sel_text if selected else p.accent,
                              outline="", tags=tag)
        return
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

#: family name -> the files Pillow should try for it, best first. Pillow loads
#: by filename, Tk by family name, so a palette's preference string has to be
#: translatable both ways.
FONT_FILES = {
    # Rainbow Six 3 and Advanced Warfighter declare BankGothic Md BT Medium for
    # titles and a face called RainBow6 for body -- neither is installable, and
    # neither ships on the disc as a file: they are baked pixmap fonts inside
    # MENU*.LIN. Unispace Bold is the closest squared, evenly-spaced face on a
    # stock Windows; Bahnschrift is the closest DIN-ish body.
    "Unispace": ["unispace bd.ttf"],
    "Unispace Bold": ["unispace bd.ttf"],
    # Ghost Recon and Jungle Storm ship the same new_font_revised atlas, and it
    # IS Arial -- so this is the real face, not an approximation.
    "Arial": ["arial.ttf"],
    "Arial Bold": ["arialbd.ttf", "arial.ttf"],
    "Arial Black": ["ariblk.ttf", "arialbd.ttf"],
    # Ghost Recon 2's menus declare Chainlink Semi-Bold and Franklin Gothic
    # Demi. Franklin Gothic Medium is the same family one step lighter;
    # Bahnschrift's SemiBold SemiCondensed instance stands in for Chainlink.
    "Franklin Gothic Medium": ["framd.ttf", "segoeui.ttf"],
    "Bahnschrift": [("bahnschrift.ttf", None)],
    "Bahnschrift Light": [("bahnschrift.ttf", "Light"), "segoeuil.ttf"],
    "Bahnschrift SemiBold": [("bahnschrift.ttf", "SemiBold"), "seguisb.ttf"],
    "Bahnschrift SemiCondensed": [("bahnschrift.ttf", "SemiCondensed")],
    # Windows truncates the family name at 31 characters, which is how it is
    # registered and therefore how Tk asks for it. Kept verbatim on purpose.
    "Bahnschrift SemiBold SemiConden":
        [("bahnschrift.ttf", "SemiBold SemiCondensed"), "seguisb.ttf"],
    # Sum of All Fears' atlas is a Gill Sans-class humanist; Gill Sans is not
    # installed anywhere, so Corbel is the nearest humanist. The logo is a
    # heavy condensed grotesque, which Impact matches.
    "Corbel": ["corbel.ttf"],
    "Corbel Bold": ["corbelb.ttf", "corbel.ttf"],
    "Impact": ["impact.ttf"],
    "Verdana": ["verdana.ttf", "segoeui.ttf"],
    "Verdana Bold": ["verdanab.ttf", "segoeuib.ttf"],
    "Segoe UI": ["segoeui.ttf"],
    "Segoe UI Light": ["segoeuil.ttf", "segoeui.ttf"],
    "Segoe UI Semibold": ["seguisb.ttf", "segoeuib.ttf"],
    "Segoe UI Bold": ["segoeuib.ttf"],
    "Segoe UI Black": ["seguibl.ttf", "segoeuib.ttf"],
    "Tahoma": ["tahoma.ttf"],
    "Tahoma Bold": ["tahomabd.ttf", "tahoma.ttf"],
    "Trebuchet MS": ["trebuc.ttf"],
    "Trebuchet MS Bold": ["trebucbd.ttf", "trebuc.ttf"],
    "Consolas": ["consola.ttf"],
}


def _font(name, size):
    """Load the first face of a comma-separated preference list that exists.

    An entry may be a filename or a `(filename, variationName)` pair; Bahnschrift
    is a single variable font whose weights and widths are named instances
    rather than separate files, and the instance is what makes it match the
    game rather than look like a generic UI face.
    """
    from PIL import ImageFont
    tried = []
    for want in [n.strip() for n in str(name).split(",") if n.strip()]:
        tried += FONT_FILES.get(want, [])
    tried.append("segoeui.ttf")
    for entry in tried:
        fname, variation = entry if isinstance(entry, tuple) else (entry, None)
        try:
            font = ImageFont.truetype(fname, size)
        except OSError:
            continue
        if variation:
            try:
                font.set_variation_by_name(variation)
            except Exception:                     # noqa: BLE001
                pass                              # a static build: still fine
        return font
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def draw_tracked(draw, xy, text, font, fill, track=0, anchor_right=False,
                 shadow=""):
    """Letterspaced text. Pillow has no tracking, so step glyph by glyph.

    `shadow` draws the same lettering once behind and below, which is how both
    Sum of All Fears' and Lockdown's own wordmarks are set.
    """
    x, y = xy
    if anchor_right:
        total = sum(draw.textlength(ch, font=font) + track for ch in text) - track
        x -= total
    if shadow:
        sx = x
        for ch in text:
            draw.text((sx + 2, y + 2), ch, font=font, fill=shadow)
            sx += draw.textlength(ch, font=font) + track
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + track
    return x


#: How much taller than a plain fit the header mark is drawn. A wordmark that
#: only fills the box's width looks undersized in a header it does not fill.
EMBLEM_VSTRETCH = 1.12

#: Where the page title sits in the header, per chrome family.
#: Measured rather than guessed: on the Lockdown header the plate runs 6..122,
#: and the title and the disc line were each pinned 14px off their own edge
#: with a 57px void between them, so the title read as floating at the very
#: top. Dropping it closes most of that gap and makes the two read as a pair.
TITLE_TOP = {"lock": 28, "angular": 20, "plain": 16}


def title_image(text, p: Palette, px, width, height, subtitle="", emblem=None):
    """The header band: chrome, the game's emblem, and the page title."""
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageTk
    except ImportError:
        return None

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    lock_rule_y = None
    if p.chrome == "lock":
        # The backdrop for this disc is its own loading frame, which carries
        # the same logo -- so without a ground under the header the emblem sits
        # on top of a blurred copy of itself. The game's menus have a solid
        # plate here too.
        d.rectangle([0, 0, width, height], fill=_hex(p.veil) + (244,))
        # The plate has to be painted BEFORE the emblem or it covers it: the
        # emblem is composited further down, and this plate spans the whole
        # header so it would erase the logo entirely.
        #
        # The shear is the SAME 45 degrees the nav rows and the action buttons
        # use -- `shear_points` steps `cut` across and `cut` down -- so the
        # header and the buttons read as one shape language rather than two
        # slightly different slopes.
        _top = px(6)
        _plate_h = height - px(30)
        d.polygon(shear_points(0, _top, width, _top + _plate_h, _plate_h),
                  fill=_hex(p.panel2) + (238,))
        lock_rule_y = _top + _plate_h
        d.line([(0, lock_rule_y), (width, lock_rule_y)], fill=p.edge,
               width=px(2))
        # where the diagonal begins, so the title can be kept to the left of it
        lock_shear_x = width - _plate_h

    label = text.upper() if p.title_upper else text
    ink = p.title_ink or p.title
    big = _font(p.title_font, px(30))
    small = _font(p.body_font, px(11))

    # A fixed mark box, so the title lands in the same place whether or not a
    # given disc actually has a badge -- Jungle Storm's has to line up with
    # Ghost Recon's or the two skins look unrelated side by side.
    left = px(26)
    # A wide wordmark is limited by the box WIDTH, but a squarer mark -- like
    # Lockdown's stacked logo -- is limited by its height, so a little more
    # headroom here costs the wide ones nothing and helps the tall ones.
    box_w, box_h = px(258), height - px(16)
    if emblem is not None:
        em = emblem.convert("RGBA")
        # `thumbnail` only ever SHRINKS, so a small mark -- Rainbow Six 3's
        # laurel is 185x85 -- stayed small while the wide wordmarks filled the
        # box, and the shelf looked inconsistent. Scale to fit in both
        # directions instead.
        scale = min(box_w / float(em.width), box_h / float(em.height))
        # Most of these marks are wide wordmarks, so a plain fit is limited by
        # the box WIDTH and leaves vertical headroom unused -- they end up
        # reading small in a header they do not fill. Give them a little more
        # height than the fit, never past the box, so a mark that is already
        # height-limited (Lockdown's stacked logo) is left exactly as it was.
        vscale = min(scale * EMBLEM_VSTRETCH, box_h / float(em.height))
        if abs(scale - 1.0) > 0.01 or abs(vscale - scale) > 0.01:
            em = em.resize((max(1, int(em.width * scale)),
                            max(1, int(em.height * vscale))), Image.LANCZOS)
        # Lockdown's plate does not fill the band -- it starts at px(6) and
        # stops short of the bottom -- so centring on the band puts the logo
        # visibly low inside it.
        mid = (height - em.height) // 2
        if p.chrome == "lock":
            mid = px(6) + ((height - px(30)) - em.height) // 2
        img.alpha_composite(em, (left + (box_w - em.width) // 2, mid))
    pad = left + box_w + px(22)

    right = p.title_align != "left"
    tx = width - px(30) if right else pad

    if p.chrome == "lock":
        # The game's signature plate: it carries the title and its right end is
        # a LONG diagonal that falls away past the lettering, with a bright
        # rule crossing the entire width at its foot.
        # the plate and its rule are already down; only the lettering is left.
        # Keep it clear of the diagonal -- by the title's own baseline the
        # plate's right edge has already pulled in.
        rule_y = lock_rule_y
        # ranged to the LEFT of where the diagonal starts, so the cut falls
        # away to the right of the word rather than through it
        tx = lock_shear_x - px(18)
        draw_tracked(d, (tx, px(TITLE_TOP["lock"])), label, big, ink,
                     track=px(p.title_track), anchor_right=True,
                     shadow=p.title_shadow)
        if subtitle:
            draw_tracked(d, (tx, rule_y - px(24)), subtitle, small, p.dim,
                         track=px(1), anchor_right=True)
        return ImageTk.PhotoImage(img)

    if angular(p):
        # the angled rule the game runs under its title
        y = height - px(15)
        cut = px(14)
        d.line([(pad, y), (width - px(26) - cut, y), (width - px(26), y - cut)],
               fill=p.edge_dim, width=px(2))
        draw_tracked(d, (tx, px(TITLE_TOP["angular"])), label, big, ink,
                     track=px(p.title_track), anchor_right=right,
                     shadow=p.title_shadow)
        if subtitle:
            draw_tracked(d, (tx, height - px(40)), subtitle, small, p.dim,
                         track=px(1), anchor_right=right)
    else:
        # heavy white title with the dark halo the console shells use
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sx = tx - d.textlength(label, font=big) if right else tx
        top = px(TITLE_TOP["plain"])
        sd.text((sx + px(2), top + px(2)), label, font=big, fill=(0, 0, 0, 210))
        shadow = shadow.filter(ImageFilter.GaussianBlur(px(3)))
        img.alpha_composite(shadow)
        if p.title_shadow:
            d.text((sx + px(2), top + px(2)), label, font=big, fill=p.title_shadow)
        d.text((sx, top), label, font=big, fill=ink)
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

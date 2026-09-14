"""Dark theme, and the banner art lifted out of whichever disc is loaded."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

BG = "#12151a"
PANEL = "#1a1f27"
PANEL_HI = "#222935"
LINE = "#2c3542"
TEXT = "#dfe6ef"
DIM = "#8b98a9"
FAINT = "#5d6977"
ACCENT = "#6fae3f"
ACCENT_DIM = "#4c7a2b"
WARN = "#d8a23a"
BAD = "#d2604a"
GOOD = "#6fae3f"

BADGE = {
    "verified": (GOOD, "verified in game"),
    "applied": (WARN, "measured, not play-tested"),
    "experimental": (WARN, "untested"),
    "broken": (BAD, "not working"),
}

#: what an option actually rewrites, shown next to its badge
TOUCH = {
    "code": None,
    "data": (DIM, " GAME DATA "),
    "cheat": (WARN, " CHEAT FILE "),
}

#: pixels-per-logical-pixel for the display the window opened on; every fixed
#: size in the UI is multiplied by this, so the layout survives a 125%/150%/200%
#: display instead of clipping its own text.
SCALE = 1.0


def px(n):
    return int(round(n * SCALE))


def set_dpi_aware():
    """Ask Windows to stop bitmap-stretching the window.

    Without this the whole UI is scaled up by the compositor and comes out
    blurry; with it, Tk hands us real pixels and we do the scaling ourselves.
    """
    import sys
    if not sys.platform.startswith("win"):
        return
    import ctypes
    for fn in (lambda: ctypes.windll.shcore.SetProcessDpiAwareness(2),
               lambda: ctypes.windll.user32.SetProcessDPIAware()):
        try:
            fn()
            return
        except Exception:
            continue


FONT = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 8)
FONT_BOLD = ("Segoe UI Semibold", 10)
FONT_H1 = ("Segoe UI Light", 22)
FONT_H2 = ("Segoe UI Semibold", 12)
FONT_MONO = ("Consolas", 9)


def cache_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "TomClancyPS2ModStudio", "art")
    os.makedirs(path, exist_ok=True)
    return path


def install(root: tk.Misc) -> ttk.Style:
    global SCALE
    try:
        SCALE = max(1.0, root.winfo_fpixels("1i") / 96.0)
    except tk.TclError:
        SCALE = 1.0
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass

    st.configure(".", background=BG, foreground=TEXT, font=FONT,
                 fieldbackground=PANEL, bordercolor=LINE, lightcolor=PANEL,
                 darkcolor=PANEL, focuscolor=ACCENT)
    st.configure("TFrame", background=BG)
    st.configure("Panel.TFrame", background=PANEL)
    st.configure("Card.TFrame", background=PANEL, relief="flat")
    st.configure("TLabel", background=BG, foreground=TEXT)
    st.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
    st.configure("Dim.TLabel", background=BG, foreground=DIM, font=FONT_SMALL)
    st.configure("PanelDim.TLabel", background=PANEL, foreground=DIM, font=FONT_SMALL)
    st.configure("Help.TLabel", background=PANEL, foreground=DIM, font=FONT_SMALL)
    st.configure("Caution.TLabel", background=PANEL, foreground=WARN, font=FONT_SMALL)
    st.configure("H1.TLabel", background=BG, foreground=TEXT, font=FONT_H1)
    st.configure("H2.TLabel", background=PANEL, foreground=TEXT, font=FONT_H2)
    st.configure("Mono.TLabel", background=PANEL, foreground=DIM, font=FONT_MONO)

    st.configure("TCheckbutton", background=PANEL, foreground=TEXT,
                 indicatorcolor=PANEL_HI, focuscolor=PANEL)
    st.map("TCheckbutton",
           background=[("active", PANEL)],
           indicatorcolor=[("selected", ACCENT), ("disabled", LINE)],
           foreground=[("disabled", FAINT)])

    st.configure("TRadiobutton", background=PANEL, foreground=TEXT,
                 indicatorcolor=PANEL_HI, focuscolor=PANEL)
    st.map("TRadiobutton",
           background=[("active", PANEL)],
           indicatorcolor=[("selected", ACCENT), ("disabled", LINE)],
           foreground=[("disabled", FAINT)])

    st.configure("TButton", background=PANEL_HI, foreground=TEXT,
                 borderwidth=0, padding=(px(14), px(7)), font=FONT)
    st.map("TButton",
           background=[("active", LINE), ("disabled", PANEL)],
           foreground=[("disabled", FAINT)])

    st.configure("Accent.TButton", background=ACCENT_DIM, foreground="#f2fbe9",
                 borderwidth=0, padding=(px(18), px(9)), font=FONT_BOLD)
    st.map("Accent.TButton",
           background=[("active", ACCENT), ("disabled", PANEL)],
           foreground=[("disabled", FAINT)])

    st.configure("Danger.TButton", background=PANEL_HI, foreground=BAD,
                 borderwidth=0, padding=(px(14), px(7)))
    st.map("Danger.TButton", background=[("active", LINE)])

    st.configure("Nav.TButton", background=BG, foreground=DIM, borderwidth=0,
                 padding=(px(16), px(11)), anchor="w", font=FONT)
    st.map("Nav.TButton", background=[("active", PANEL)],
           foreground=[("active", TEXT)])
    st.configure("NavOn.TButton", background=PANEL, foreground=TEXT,
                 borderwidth=0, padding=(px(16), px(11)), anchor="w", font=FONT_BOLD)
    st.map("NavOn.TButton", background=[("active", PANEL)])

    st.configure("TEntry", fieldbackground=PANEL, foreground=TEXT,
                 insertcolor=TEXT, borderwidth=0, padding=px(7))
    st.configure("TCombobox", fieldbackground=PANEL, background=PANEL_HI,
                 foreground=TEXT, arrowcolor=DIM, borderwidth=0, padding=px(5))
    st.map("TCombobox", fieldbackground=[("readonly", PANEL)],
           foreground=[("disabled", FAINT)])

    st.configure("Horizontal.TScale", background=PANEL, troughcolor=BG,
                 borderwidth=0, sliderthickness=px(16))
    st.configure("TSeparator", background=LINE)
    st.configure("Vertical.TScrollbar", background=PANEL_HI, troughcolor=BG,
                 borderwidth=0, arrowcolor=DIM)
    st.map("Vertical.TScrollbar", background=[("active", LINE)])
    return st


# ---------------------------------------------------------------------------
# banner art
# ---------------------------------------------------------------------------

def _pil():
    try:
        from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageTk
        return Image, ImageDraw, ImageEnhance, ImageFilter, ImageTk
    except ImportError:
        return None


def make_banner(image, width, height, title, subtitle):
    """Crop, darken and letter a game screenshot into a header banner."""
    mods = _pil()
    if mods is None or image is None:
        return None
    Image, ImageDraw, ImageEnhance, ImageFilter, ImageTk = mods

    src = image.convert("RGB")
    sw, sh = src.size
    scale = max(width / sw, height / sh)
    src = src.resize((max(1, int(sw * scale)), max(1, int(sh * scale))),
                     Image.LANCZOS)
    left = (src.width - width) // 2
    top = int((src.height - height) * 0.66)
    src = src.crop((left, top, left + width, top + height))
    src = ImageEnhance.Brightness(src).enhance(0.78)
    src = src.filter(ImageFilter.GaussianBlur(0.6))

    # fade the bottom edge into the page background
    fade = Image.new("RGB", (width, height), BG)
    mask = Image.linear_gradient("L").resize((width, height))
    src = Image.composite(fade, src, mask.point(lambda v: min(255, int(v * 1.35))))

    d = ImageDraw.Draw(src)
    d.line([(0, height - 1), (width, height - 1)], fill=ACCENT_DIM, width=2)
    _letter(d, width, height, title, subtitle)
    return ImageTk.PhotoImage(src)


def flat_banner(width, height, title, subtitle):
    """Fallback header when there is no disc art to draw on."""
    mods = _pil()
    if mods is None:
        return None
    Image, ImageDraw, _, _, ImageTk = mods
    img = Image.new("RGB", (width, height), PANEL)
    d = ImageDraw.Draw(img)
    for x in range(0, width, 4):
        shade = 26 + int(14 * (x / max(1, width)))
        d.line([(x, 0), (x, height)], fill=(shade, shade + 3, shade + 8))
    d.line([(0, height - 1), (width, height - 1)], fill=LINE, width=2)
    _letter(d, width, height, title, subtitle)
    return ImageTk.PhotoImage(img)


def _letter(draw, width, height, title, subtitle):
    """Draw the game name into the banner, sized to the banner not the display."""
    try:
        from PIL import ImageFont
        f1 = ImageFont.truetype("segoeuil.ttf", px(27))
        f2 = ImageFont.truetype("segoeui.ttf", px(11))
    except Exception:
        f1 = f2 = None
    x = px(26)
    draw.text((x, height - px(62)), title, fill="#f4f8fc", font=f1)
    draw.text((x + px(2), height - px(26)), subtitle, fill="#9fb0c2", font=f2)

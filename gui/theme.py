"""The active skin, the ttk styles built from it, and display scaling.

`P` is the palette in force. `use(palette)` swaps it and re-configures every
ttk style, so loading a different disc re-skins the whole window.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

from .skins import DEFAULT, Palette, for_profile, mix  # noqa: F401

#: the palette currently in force
P: Palette = DEFAULT

#: pixels per logical pixel on this display. Every fixed size is multiplied by
#: it, so the layout survives a 125%/150%/200% monitor instead of clipping its
#: own text.
SCALE = 1.0

_root = None

BADGE = {
    "verified": ("good", "verified in game"),
    "applied": ("warn", "measured, not play-tested"),
    "experimental": ("warn", "untested"),
    "broken": ("bad", "not working"),
}

TOUCH = {
    "code": None,
    "data": ("dim", " GAME DATA "),
    "cheat": ("warn", " CHEAT FILE "),
}


def px(n):
    return int(round(n * SCALE))


def colour(name):
    """Look a palette colour up by the name a badge table stores."""
    return getattr(P, name, P.text)


def F(kind="body", size=10):
    """A tk font tuple in the active skin's faces."""
    if kind == "title":
        return (P.title_font, size)
    if kind == "bold":
        return (P.bold_font, size)
    if kind == "mono":
        return ("Consolas", size)
    return (P.body_font, size)


def set_dpi_aware():
    """Ask Windows to stop bitmap-stretching the window.

    Without this the compositor scales the whole thing up and it comes out
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
        except Exception:                        # noqa: BLE001
            continue


def cache_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "TomClancyPS2ModStudio", "art")
    os.makedirs(path, exist_ok=True)
    return path


# ---------------------------------------------------------------------------

def install(root: tk.Misc) -> ttk.Style:
    global SCALE, _root
    _root = root
    try:
        SCALE = max(1.0, root.winfo_fpixels("1i") / 96.0)
    except tk.TclError:
        SCALE = 1.0
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    _apply(st)
    return st


def use(palette: Palette):
    """Switch skins and restyle everything already on screen."""
    global P
    P = palette
    if _root is not None:
        _apply(ttk.Style(_root))
        _root.configure(bg=P.bg)


def _apply(st: ttk.Style):
    body, small, bold = F("body", 10), F("body", 8), F("bold", 10)

    st.configure(".", background=P.bg, foreground=P.text, font=body,
                 fieldbackground=P.panel, bordercolor=P.edge_dim,
                 lightcolor=P.panel, darkcolor=P.panel, focuscolor=P.accent)
    st.configure("TFrame", background=P.bg)
    st.configure("Panel.TFrame", background=P.panel)
    st.configure("TLabel", background=P.bg, foreground=P.text)
    st.configure("Dim.TLabel", background=P.bg, foreground=P.dim, font=small)

    st.configure("TButton", background=P.panel2, foreground=P.text,
                 borderwidth=0, padding=(px(14), px(7)), font=body)
    st.map("TButton",
           background=[("active", mix(P.panel2, P.edge, 0.25)),
                       ("disabled", P.panel)],
           foreground=[("disabled", P.faint)])

    st.configure("Accent.TButton", background=P.accent_dim,
                 foreground=P.sel_text if P.chrome == "gr" else "#f2fbe9",
                 borderwidth=0, padding=(px(18), px(9)), font=bold)
    st.map("Accent.TButton",
           background=[("active", P.accent), ("disabled", P.panel)],
           foreground=[("disabled", P.faint)])

    st.configure("TEntry", fieldbackground=P.panel, foreground=P.text,
                 insertcolor=P.text, borderwidth=0, padding=px(7))
    st.configure("TCombobox", fieldbackground=P.panel, background=P.panel2,
                 foreground=P.text, arrowcolor=P.dim, borderwidth=0,
                 padding=px(5))
    st.map("TCombobox", fieldbackground=[("readonly", P.panel)],
           foreground=[("disabled", P.faint)])

    st.configure("Vertical.TScrollbar", background=P.panel2, troughcolor=P.bg,
                 borderwidth=0, arrowcolor=P.dim)
    st.map("Vertical.TScrollbar",
           background=[("active", mix(P.panel2, P.edge, 0.35))])


# ---------------------------------------------------------------------------
# the background plate
# ---------------------------------------------------------------------------

def backdrop(image, width, height):
    """Cover the window with the game's own art, pushed back behind the UI."""
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageTk
    except ImportError:
        return None
    if width < 2 or height < 2:
        return None

    plate = Image.new("RGB", (width, height), P.veil)
    if image is not None:
        src = image.convert("RGB")
        scale = max(width / src.width, height / src.height)
        src = src.resize((max(1, int(src.width * scale)),
                          max(1, int(src.height * scale))), Image.LANCZOS)
        left = (src.width - width) // 2
        top = int((src.height - height) * 0.35)
        src = src.crop((left, top, left + width, top + height))
        src = src.filter(ImageFilter.GaussianBlur(px(3)))
        src = ImageEnhance.Brightness(src).enhance(0.86)
        src = ImageEnhance.Color(src).enhance(0.55 if P.chrome == "rs3" else 0.85)
        veil = Image.new("RGB", src.size, P.veil)
        plate = Image.blend(src, veil, 0.28)
    return ImageTk.PhotoImage(plate)

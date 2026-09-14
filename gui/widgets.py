"""Skinned containers: a chrome panel, a scrolling area, a nav row, a card.

A Tk frame cannot carry a drawn background, so anything that needs chrome is a
canvas with its real content placed on top through `create_window`. That is what
lets a setting card wear Rainbow Six 3's cut-corner slate or Ghost Recon's
gold-ruled box while still holding ordinary widgets.
"""

from __future__ import annotations

import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from tcps2.model import BOOL, CHOICE, INT

from . import skins, theme
from .controls import RadioRow, Slider, Toggle


class Chrome(tk.Canvas):
    """A canvas that paints skin chrome behind one content frame."""

    def __init__(self, master, kind="panel", pad=None, autofit=True, **kw):
        super().__init__(master, highlightthickness=0, bd=0, bg=theme.P.bg, **kw)
        self.kind = kind
        self.autofit = autofit
        self.pad = theme.px(14) if pad is None else pad
        self.body = tk.Frame(self, bg=theme.P.panel)
        self._win = self.create_window(self.pad, self.pad, window=self.body,
                                       anchor="nw")
        self.body.bind("<Configure>", self._fit)
        self.bind("<Configure>", self._resize)

    def set_height(self, h):
        """Used when the panel is placed rather than packed: the content has to
        be told how tall to be, since it is not driving the size any more."""
        self.itemconfigure(self._win, height=max(1, h - self.pad * 2))

    def restyle(self):
        self.configure(bg=theme.P.bg)
        self.body.configure(bg=theme.P.panel)
        self._repaint()

    def _fit(self, e):
        if self.autofit:
            self.configure(height=e.height + self.pad * 2)
        self._repaint()

    def _resize(self, e):
        self.itemconfigure(self._win, width=max(1, e.width - self.pad * 2))
        self._repaint()

    def _repaint(self):
        self.delete("chrome")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4 or h < 4:
            return
        painter = skins.paint_group if self.kind == "group" else skins.paint_panel
        painter(self, theme.P, 1, 1, w - 2, h - 2, theme.px)
        self.tag_lower("chrome")


class ScrollArea(ttk.Frame):
    """A vertically scrolling region that behaves itself when resized."""

    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        # An explicit scroll increment matters more than it looks. With the
        # default of 0 a "unit" is a TENTH OF THE WINDOW, so one wheel notch
        # jumps ~80px and drags every embedded child window with it; Windows
        # does not always invalidate what moved, and the result is torn rows
        # and duplicated text. A fixed small increment keeps each step inside
        # what the compositor repaints cleanly.
        self.canvas = tk.Canvas(self, bg=theme.P.bg, highlightthickness=0,
                                bd=0, yscrollincrement=theme.px(18))
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self._yview,
                                 style="Vertical.TScrollbar")
        self.body = tk.Frame(self.canvas, bg=theme.P.bg)
        self._win = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.bar.pack(side="right", fill="y")

        self._settle_id = None
        self.body.bind("<Configure>", self._on_body)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.bind_all("<MouseWheel>", self._wheel, add="+")

    def _yview(self, *args):
        """What the scrollbar drives. Dragging the thumb is a different code
        path from the wheel -- `yview("moveto", frac)` rather than
        `yview_scroll` -- so it needs the same repaint or it tears."""
        self.canvas.yview(*args)
        self.repaint()

    def _settle(self):
        """Runs once the event queue is empty -- i.e. the moment a drag pauses.

        This is the part that is actually verifiable: whatever the screen looks
        like mid-drag, the settled frame is correct, and scheduling it on idle
        guarantees the settle happens rather than waiting for the next event to
        arrive from somewhere else.
        """
        self._settle_id = None
        self.canvas.update_idletasks()
        self._force_paint()

    def repaint(self):
        """Force the embedded child windows to redraw where they now are.

        Every setting card is a canvas holding a frame holding labels, so the
        scrolled content is three levels of real child windows. Tk moves them
        when the canvas scrolls; Windows does not reliably repaint them, and
        what is left on screen is rows from the previous scroll position
        overlaid on the new ones. `update_idletasks` does not fix it because
        nothing has been invalidated -- the OS does not believe anything is
        dirty. RDW_ALLCHILDREN says otherwise about the whole subtree.
        """
        # ORDER MATTERS. Tk defers the geometry work that actually moves the
        # embedded windows to an idle task, so forcing a paint first paints the
        # OLD layout. Let Tk finish moving things, then tell Windows the whole
        # subtree is dirty and must be painted now.
        self.canvas.update_idletasks()
        self._force_paint()
        # ...and book a second one for when the drag pauses, debounced so a
        # long drag queues one settle rather than hundreds.
        if self._settle_id is None:
            self._settle_id = self.after_idle(self._settle)

    def _force_paint(self):
        if sys.platform != "win32":
            return
        try:
            import ctypes
            RDW_INVALIDATE, RDW_ERASE = 0x0001, 0x0004
            RDW_ALLCHILDREN, RDW_UPDATENOW = 0x0080, 0x0100
            ctypes.windll.user32.RedrawWindow(
                self.canvas.winfo_id(), None, None,
                RDW_INVALIDATE | RDW_ERASE | RDW_ALLCHILDREN | RDW_UPDATENOW)
        except Exception:                         # noqa: BLE001
            pass

    def restyle(self):
        self.canvas.configure(bg=theme.P.bg)
        self.body.configure(bg=theme.P.bg)

    def _on_body(self, _e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._sync_bar()

    def _on_canvas(self, e):
        self.canvas.itemconfigure(self._win, width=e.width)
        self._sync_bar()

    def _sync_bar(self):
        box = self.canvas.bbox("all")
        need = bool(box) and (box[3] - box[1]) > self.canvas.winfo_height()
        if need and not self.bar.winfo_ismapped():
            self.bar.pack(side="right", fill="y")
        elif not need and self.bar.winfo_ismapped():
            self.bar.pack_forget()

    def _wheel(self, e):
        """Scroll only when the pointer is over this area, so sliders inside it
        keep their own wheel handling."""
        w = e.widget
        while w is not None:
            if w is self.canvas or w is self.body:
                break
            if isinstance(w, Slider):
                return
            w = getattr(w, "master", None)
        else:
            return
        box = self.canvas.bbox("all")
        if box and (box[3] - box[1]) > self.canvas.winfo_height():
            # three increments per notch: enough travel to feel right, small
            # enough that the embedded canvases repaint in step with it
            self.canvas.yview_scroll(-3 * (e.delta // 120), "units")
            self.repaint()

    def clear(self):
        for child in self.body.winfo_children():
            child.destroy()
        self.canvas.yview_moveto(0)


#: letterspacing candidates, widest first: en quad, four-per-em, thin, none
_GAPS = ("\u2002", "\u2005", "\u2009", "")


def nav_style(labels, avail, sizes=(11, 10, 9)):
    """(font, gap) for a whole nav column: keep the letterspacing, shrink type.

    Advanced Warfighter's menus letterspace every row, and a long label there
    is set smaller rather than set solid. So rather than let one long label
    collapse the tracking for the entire column, step the type size down until
    a real gap fits everything -- and only give up on tracking if even the
    smallest size cannot take it.
    """
    for size in sizes:
        font = theme.F("title", size)
        gap = shared_gap(labels, font, avail)
        if gap:
            return font, gap
    return theme.F("title", sizes[0]), ""


def shared_gap(labels, font, avail):
    """The widest letterspacing that fits EVERY label in a column.

    Picking per row would letterspace the short ones more than the long ones
    and the column would look ragged, so the whole nav agrees on one gap.
    """
    if avail <= 0 or not labels:
        return ""
    measure = tkfont.Font(font=font).measure
    for gap in _GAPS:
        if all(measure(gap.join(t) if gap else t) <= avail for t in labels):
            return gap
    return ""


def _tracked(text, font, avail, gap=None):
    """`text` letterspaced, either with a given gap or the widest that fits."""
    if gap is None:
        gap = shared_gap([text], font, avail)
    return gap.join(text) if gap else text


class NavItem(tk.Canvas):
    """One row of the left-hand menu, drawn the way the game draws it."""

    def __init__(self, master, text, command, height=None, gap=None,
                 font=None):
        h = height or theme.px(40)
        self.gap = gap
        self.nav_font = font
        super().__init__(master, height=h, bg=theme.P.bg, highlightthickness=0,
                         bd=0, cursor="hand2")
        self.text = text
        self.command = command
        self.selected = False
        self.hovered = False
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Button-1>", lambda _e: self.command())
        self.bind("<Enter>", lambda _e: self._hover(True))
        self.bind("<Leave>", lambda _e: self._hover(False))

    def _hover(self, on):
        self.hovered = on
        self._draw()

    def select(self, on):
        self.selected = on
        self._draw()

    def _draw(self):
        p = theme.P
        self.delete("all")
        self.configure(bg=p.bg)
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            return
        skins.paint_button(self, p, 1, 1, w - 2, h - 2, theme.px,
                           self.selected, self.hovered)
        if p.chrome == "graw":
            # Ranged left behind the wedge and letterspaced, like the game's
            # rows -- but measured. A full space between every letter turns
            # "ENEMY WAVES" into something wider than the row and it loses its
            # last word off the sheared edge, so the gap steps down through
            # four-per-em and thin spaces to none until the label fits.
            fg = p.sel_text if self.selected else (p.text if self.hovered
                                                   else p.dim)
            font = self.nav_font or theme.F("title", 11)
            x = theme.px(30)
            avail = w - x - theme.px(18)
            self.create_text(x, h // 2,
                             text=_tracked(self.text.upper(), font, avail,
                                           self.gap),
                             anchor="w", fill=fg, font=font)
        elif p.chrome == "rs3":
            fg = p.sel_text if self.selected else (p.text if self.hovered else p.dim)
            font = theme.F("title", 12)
            x = theme.px(20)
            self.create_text(x, h // 2, text=self.text.upper(), anchor="w",
                             fill=fg, font=font)
        else:
            fg = p.sel_text if self.selected else (p.text if self.hovered else p.dim)
            self.create_text(w // 2, h // 2, text=self.text, anchor="c", fill=fg,
                             font=theme.F("bold" if self.selected else "body", 11))


class ActionButton(tk.Canvas):
    """A bottom-bar action: a skinned button with a label."""

    def __init__(self, master, text, command, accent=False):
        super().__init__(master, height=theme.px(38), bg=theme.P.bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.text, self.command = text, command
        self.accent = accent
        self.enabled = True
        self.hovered = False
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Button-1>", lambda _e: self.enabled and self.command())
        self.bind("<Enter>", lambda _e: self._hover(True))
        self.bind("<Leave>", lambda _e: self._hover(False))

    def _hover(self, on):
        self.hovered = on
        self._draw()

    def set_enabled(self, on):
        self.enabled = on
        self.configure(cursor="hand2" if on else "")
        self._draw()

    def width_needed(self):
        f = theme.F("bold" if self.accent else "body", 11)
        import tkinter.font as tkfont
        return tkfont.Font(font=f).measure(self.text.upper()) + theme.px(44)

    def _draw(self):
        p = theme.P
        self.delete("all")
        self.configure(bg=p.bg)
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            return
        if self.accent and self.enabled:
            skins.paint_button(self, p, 1, 1, w - 2, h - 2, theme.px,
                               True, self.hovered)
            fg = p.sel_text
        else:
            if self.hovered and self.enabled:
                skins.paint_button(self, p, 1, 1, w - 2, h - 2, theme.px,
                                   False, True)
            fg = p.text if self.enabled else p.faint
        self.create_text(w // 2, h // 2, anchor="c", text=self.text.upper(),
                         fill=fg,
                         font=theme.F("bold" if self.accent else "body", 11))


def badge(master, kind):
    name, text = theme.BADGE.get(kind, ("dim", kind))
    return tk.Label(master, text=" " + text.upper() + " ", bg=theme.P.panel,
                    fg=theme.colour(name), font=theme.F("body", 8))


class SettingCard(Chrome):
    """One option: a control, its help, and whatever caveats apply to it."""

    def __init__(self, master, setting, var, on_change):
        super().__init__(master, kind="panel", pad=theme.px(16))
        self.setting = setting
        self.var = var
        self.on_change = on_change
        self._controls = []
        self._gate_lbl = None
        self._build()

    def _text(self, text, colour, size=8, wrap=560, pady=(8, 0)):
        lbl = tk.Label(self.body, text=text, bg=theme.P.panel, fg=colour,
                       font=theme.F("body", size), wraplength=theme.px(wrap),
                       justify="left", anchor="w")
        lbl.pack(fill="x", pady=(theme.px(pady[0]), theme.px(pady[1])))
        return lbl

    def _build(self):
        p, s = theme.P, self.setting
        head = tk.Frame(self.body, bg=p.panel)
        head.pack(fill="x")

        tags = tk.Frame(head, bg=p.panel)
        tags.pack(side="right")
        badge(tags, "broken" if not s.enabled else s.confidence).pack(side="right")
        touch = theme.TOUCH.get("cheat" if s.pnach_only else s.touches)
        if touch:
            tk.Label(tags, text=touch[1], bg=p.panel, fg=theme.colour(touch[0]),
                     font=theme.F("body", 8)).pack(side="right",
                                                   padx=(0, theme.px(6)))

        if s.kind == BOOL:
            tog = Toggle(head, s.label, self.var, self.on_change)
            tog.pack(side="left", fill="x", expand=True)
            self._controls.append(tog)
        else:
            sharp = skins.angular(p)
            tk.Label(head, text=s.label.upper() if sharp else s.label,
                     bg=p.panel, fg=p.title, anchor="w",
                     font=theme.F("title" if sharp else "bold",
                                  13 if sharp else 12)
                     ).pack(side="left")

        if s.kind == INT:
            sl = Slider(self.body, self.var, s.minimum, s.maximum, s.unit,
                        self.on_change)
            sl.pack(fill="x", pady=(theme.px(12), theme.px(2)))
            self._controls.append(sl)
        elif s.kind == CHOICE:
            box = tk.Frame(self.body, bg=p.panel)
            box.pack(fill="x", pady=(theme.px(12), 0))
            for ch in s.choices:
                row = RadioRow(box, ch.label, ch.help, ch.value, self.var,
                               self.on_change)
                row.pack(fill="x", pady=(0, theme.px(7)))
                self._controls.append(row)

        if s.help:
            self._text(s.help, p.dim)
        if s.caution:
            self._text("⚠  " + s.caution, p.warn, pady=(7, 0))
        if not s.enabled and s.disabled_reason:
            self._text("✖  " + s.disabled_reason, p.bad, pady=(7, 0))

    def set_enabled(self, on, reason=""):
        for c in self._controls:
            c.set_enabled(on)
        if self._gate_lbl is not None:
            self._gate_lbl.destroy()
            self._gate_lbl = None
        if not on and reason:
            self._gate_lbl = self._text("→  " + reason, theme.P.faint,
                                        pady=(7, 0))

    def sync(self):
        for c in self._controls:
            if hasattr(c, "sync"):
                c.sync()

"""Skinned containers: a chrome panel, a scrolling area, a nav row, a card.

A Tk frame cannot carry a drawn background, so anything that needs chrome is a
canvas with its real content placed on top through `create_window`. That is what
lets a setting card wear Rainbow Six 3's cut-corner slate or Ghost Recon's
gold-ruled box while still holding ordinary widgets.
"""

from __future__ import annotations

import tkinter as tk
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
        self.canvas = tk.Canvas(self, bg=theme.P.bg, highlightthickness=0, bd=0)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                                 style="Vertical.TScrollbar")
        self.body = tk.Frame(self.canvas, bg=theme.P.bg)
        self._win = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.bar.pack(side="right", fill="y")

        self.body.bind("<Configure>", self._on_body)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.bind_all("<MouseWheel>", self._wheel, add="+")

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
            self.canvas.yview_scroll(-1 * (e.delta // 120), "units")

    def clear(self):
        for child in self.body.winfo_children():
            child.destroy()
        self.canvas.yview_moveto(0)


class NavItem(tk.Canvas):
    """One row of the left-hand menu, drawn the way the game draws it."""

    def __init__(self, master, text, command, height=None):
        h = height or theme.px(40)
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
        if p.chrome == "rs3":
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
    """A bottom-bar action: a PlayStation face button and a label."""

    def __init__(self, master, text, glyph, command, accent=False):
        super().__init__(master, height=theme.px(38), bg=theme.P.bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.text, self.glyph, self.command = text, glyph, command
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
        return tkfont.Font(font=f).measure(self.text.upper()) + theme.px(62)

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
        r = theme.px(11)
        cx = theme.px(20)
        skins.glyph(self, p, self.glyph, cx, h // 2, r)
        self.create_text(cx + r + theme.px(11), h // 2, anchor="w",
                         text=self.text.upper(), fill=fg,
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
            tk.Label(head, text=s.label.upper() if p.chrome == "rs3" else s.label,
                     bg=p.panel, fg=p.title, anchor="w",
                     font=theme.F("title" if p.chrome == "rs3" else "bold",
                                  13 if p.chrome == "rs3" else 12)
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

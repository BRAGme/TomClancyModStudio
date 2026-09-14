"""Reusable pieces: a scrolling area, and one card per setting."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from tcps2.model import BOOL, CHOICE, INT

from . import theme
from .controls import RadioRow, Slider, Toggle


class ScrollArea(ttk.Frame):
    """A vertically scrolling region that behaves itself when resized."""

    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.canvas = tk.Canvas(self, bg=theme.BG, highlightthickness=0, bd=0)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                                 style="Vertical.TScrollbar")
        self.body = ttk.Frame(self.canvas)
        self._win = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.bar.pack(side="right", fill="y")

        self.body.bind("<Configure>", self._on_body)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.bind_all("<MouseWheel>", self._wheel, add="+")

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
        """Scroll only when the pointer is genuinely over this area, so the
        sliders inside it keep their own wheel handling."""
        w = e.widget
        while w is not None:
            if w is self.canvas or w is self.body:
                break
            if isinstance(w, (Slider,)) or getattr(w, "_eats_wheel", False):
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


def badge(master, kind):
    colour, text = theme.BADGE.get(kind, (theme.DIM, kind))
    return tk.Label(master, text=" " + text.upper() + " ", bg=theme.PANEL,
                    fg=colour, font=theme.FONT_SMALL)


class SettingCard(tk.Frame):
    """One option: a control, its help, and whatever caveats apply to it."""

    def __init__(self, master, setting, var, on_change):
        super().__init__(master, bg=theme.PANEL,
                         padx=theme.px(18), pady=theme.px(15))
        self.setting = setting
        self.var = var
        self.on_change = on_change
        self._controls = []
        self._gate_lbl = None
        self._build()

    # -- construction ------------------------------------------------------
    def _text(self, parent, text, colour, font, wrap=560, pady=(8, 0)):
        lbl = tk.Label(parent, text=text, bg=theme.PANEL, fg=colour, font=font,
                       wraplength=theme.px(wrap), justify="left", anchor="w")
        lbl.pack(fill="x", pady=(theme.px(pady[0]), theme.px(pady[1])))
        return lbl

    def _build(self):
        s = self.setting
        head = tk.Frame(self, bg=theme.PANEL)
        head.pack(fill="x")

        tags = tk.Frame(head, bg=theme.PANEL)
        tags.pack(side="right")
        badge(tags, "broken" if not s.enabled else s.confidence).pack(side="right")
        if s.pnach_only:
            tk.Label(tags, text=" CHEAT FILE ", bg=theme.PANEL, fg=theme.WARN,
                     font=theme.FONT_SMALL).pack(side="right", padx=(0, theme.px(6)))

        if s.kind == BOOL:
            tog = Toggle(head, s.label, self.var, self.on_change)
            tog.pack(side="left", fill="x", expand=True)
            self._controls.append(tog)
        else:
            tk.Label(head, text=s.label, bg=theme.PANEL, fg=theme.TEXT,
                     font=theme.FONT_H2, anchor="w").pack(side="left")

        if s.kind == INT:
            sl = Slider(self, self.var, s.minimum, s.maximum, s.unit, self.on_change)
            sl.pack(fill="x", pady=(theme.px(12), theme.px(2)))
            self._controls.append(sl)
        elif s.kind == CHOICE:
            box = tk.Frame(self, bg=theme.PANEL)
            box.pack(fill="x", pady=(theme.px(12), 0))
            for ch in s.choices:
                row = RadioRow(box, ch.label, ch.help, ch.value, self.var,
                               self.on_change)
                row.pack(fill="x", pady=(0, theme.px(7)))
                self._controls.append(row)

        if s.help:
            self.help_lbl = self._text(self, s.help, theme.DIM, theme.FONT_SMALL)
        if s.caution:
            self._text(self, "⚠  " + s.caution, theme.WARN, theme.FONT_SMALL,
                       pady=(7, 0))
        if not s.enabled and s.disabled_reason:
            self._text(self, "✖  " + s.disabled_reason, theme.BAD,
                       theme.FONT_SMALL, pady=(7, 0))

    # -- state -------------------------------------------------------------
    def set_enabled(self, on, reason=""):
        for c in self._controls:
            c.set_enabled(on)
        if self._gate_lbl is not None:
            self._gate_lbl.destroy()
            self._gate_lbl = None
        if not on and reason:
            self._gate_lbl = self._text(self, "→  " + reason, theme.FAINT,
                                        theme.FONT_SMALL, pady=(7, 0))

    def sync(self):
        for c in self._controls:
            if hasattr(c, "sync"):
                c.sync()

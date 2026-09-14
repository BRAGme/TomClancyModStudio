"""Hand-drawn toggle, radio and slider, in whichever skin is active.

ttk's own indicators are a fixed handful of pixels and stay that size on a
scaled display, which on a 150% monitor leaves a checkbox smaller than the full
stop at the end of its own label. These draw themselves at whatever size the
skin asks for, which also lets them wear the game's colours: a steel switch with
a red-lit travel in Rainbow Six 3, a gold one in the two Ghost Recons.
"""

from __future__ import annotations

import tkinter as tk

from . import skins, theme
from .skins import mix, round_points


class _Hit(tk.Canvas):
    """A small canvas that behaves like a button."""

    def __init__(self, master, width, height, on_click):
        super().__init__(master, width=width, height=height, bg=theme.P.panel,
                         highlightthickness=0, bd=0, takefocus=0)
        self._on_click = on_click
        self._enabled = True
        self.hovered = False
        self.bind("<Button-1>", lambda _e: self._enabled and self._on_click())
        self.bind("<Enter>", lambda _e: self._hover(True))
        self.bind("<Leave>", lambda _e: self._hover(False))
        self.configure(cursor="hand2")

    def _hover(self, on):
        self.hovered = on
        self.redraw()

    def set_enabled(self, on):
        self._enabled = on
        self.configure(cursor="hand2" if on else "")
        self.redraw()

    def redraw(self):
        pass


class Toggle(tk.Frame):
    """A switch plus its label, the whole row clickable."""

    def __init__(self, master, text, variable, command=None):
        super().__init__(master, bg=theme.P.panel)
        self.var = variable
        self.command = command
        self._enabled = True

        w, h = theme.px(40), theme.px(21)
        self.pill = _Hit(self, w, h, self.toggle)
        self.pill.redraw = self._draw
        self.pill.pack(side="left", padx=(0, theme.px(12)))

        self.label = tk.Label(self, text=text, bg=theme.P.panel, fg=theme.P.text,
                              font=theme.F("bold", 10), anchor="w", justify="left")
        self.label.pack(side="left", fill="x", expand=True)
        for w_ in (self.label, self):
            w_.bind("<Button-1>", lambda _e: self.toggle())
            w_.configure(cursor="hand2")
        self._draw()

    def toggle(self):
        if not self._enabled:
            return
        self.var.set(not bool(self.var.get()))
        self._draw()
        if self.command:
            self.command()

    def set_enabled(self, on):
        self._enabled = on
        self.pill.set_enabled(on)
        self.label.configure(fg=theme.P.text if on else theme.P.faint,
                             cursor="hand2" if on else "")
        self.configure(cursor="hand2" if on else "")
        self._draw()

    def sync(self):
        self._draw()

    def _draw(self):
        p, c = theme.P, self.pill
        c.delete("all")
        w, h = int(c["width"]), int(c["height"])
        on = bool(self.var.get())
        r = h // 2

        if not self._enabled:
            track, knob, edge = p.panel2, p.faint, p.edge_dim
        elif on:
            track = p.tab if skins.angular(p) else p.sel_fill
            knob = "#f4f8fa" if skins.angular(p) else "#fffaf0"
            edge = mix(track, "#ffffff", 0.3)
        else:
            track = mix(p.panel, p.bg, 0.6 if not c.hovered else 0.2)
            knob = p.dim
            edge = p.edge_dim

        if skins.angular(p):
            from .skins import panel_points
            cut = theme.px(5)
            c.create_polygon(panel_points(1, 1, w - 1, h - 1, cut),
                             fill=track, outline=edge, width=1)
        else:
            c.create_polygon(round_points(1, 1, w - 1, h - 1, r), smooth=True,
                             fill=track, outline=edge, width=theme.px(1))
        pad = theme.px(3)
        kx = (w - r - 1) if on else (r + 1)
        c.create_oval(kx - r + pad, pad, kx + r - pad, h - pad,
                      fill=knob, outline="")


class RadioRow(tk.Frame):
    """One option of a choice: a marker, a label, and an explanation."""

    def __init__(self, master, text, help_text, value, variable, command=None):
        super().__init__(master, bg=theme.P.panel)
        self.var = variable
        self.value = value
        self.command = command
        self._enabled = True

        top = tk.Frame(self, bg=theme.P.panel)
        top.pack(fill="x")
        d = theme.px(18)
        self.dot = _Hit(top, d, d, self.choose)
        self.dot.redraw = self._draw
        self.dot.pack(side="left", padx=(0, theme.px(11)))
        self.label = tk.Label(top, text=text, bg=theme.P.panel, fg=theme.P.text,
                              font=theme.F("body", 10), anchor="w")
        self.label.pack(side="left", fill="x", expand=True)

        self.help = None
        if help_text:
            self.help = tk.Label(self, text=help_text, bg=theme.P.panel,
                                 fg=theme.P.dim, font=theme.F("body", 8),
                                 wraplength=theme.px(520), justify="left",
                                 anchor="w")
            self.help.pack(fill="x", padx=(theme.px(29), 0),
                           pady=(theme.px(1), 0))

        for w_ in (self.label, top):
            w_.bind("<Button-1>", lambda _e: self.choose())
            w_.configure(cursor="hand2")
        variable.trace_add("write", lambda *_a: self._draw())
        self._draw()

    def choose(self):
        if not self._enabled:
            return
        self.var.set(self.value)
        if self.command:
            self.command()

    def set_enabled(self, on):
        self._enabled = on
        self.dot.set_enabled(on)
        self.label.configure(fg=theme.P.text if on else theme.P.faint)
        if self.help:
            self.help.configure(fg=theme.P.dim if on else theme.P.faint)
        self._draw()

    def _draw(self):
        p, c = theme.P, self.dot
        try:
            c.delete("all")
        except tk.TclError:
            return
        d = int(c["width"])
        on = self.var.get() == self.value
        live = self._enabled
        mark = p.tab if skins.angular(p) else p.sel_fill
        ring = p.faint if not live else (mark if on else
                                         (p.edge if c.hovered else p.edge_dim))
        if skins.angular(p):
            from .skins import panel_points
            c.create_polygon(panel_points(1, 1, d - 1, d - 1, theme.px(4)),
                             fill="", outline=ring, width=theme.px(2))
            if on:
                k = theme.px(5)
                c.create_rectangle(k, k, d - k, d - k,
                                   fill=mark if live else p.faint, outline="")
        else:
            c.create_oval(1, 1, d - 1, d - 1, outline=ring, width=theme.px(2))
            if on:
                k = theme.px(5)
                c.create_oval(k, k, d - k, d - k,
                              fill=mark if live else p.faint, outline="")


class Slider(tk.Frame):
    """A draggable track with its value spelled out beside it."""

    def __init__(self, master, variable, minimum, maximum, unit="", command=None):
        super().__init__(master, bg=theme.P.panel)
        self.var = variable
        self.min, self.max = minimum, maximum
        self.unit = unit
        self.command = command
        self._enabled = True
        self._drag = False

        self.h = theme.px(26)
        self.canvas = tk.Canvas(self, height=self.h, bg=theme.P.panel,
                                highlightthickness=0, bd=0, cursor="hand2")
        self.canvas.pack(side="left", fill="x", expand=True)
        self.value_lbl = tk.Label(self, text="", bg=theme.P.panel,
                                  fg=theme.P.text, font=theme.F("bold", 10),
                                  width=13, anchor="e")
        self.value_lbl.pack(side="right", padx=(theme.px(12), 0))

        self.canvas.bind("<Configure>", lambda _e: self._draw())
        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._move)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self._draw()

    # -- interaction -------------------------------------------------------
    def _value_at(self, x):
        w = max(1, self.canvas.winfo_width() - theme.px(16))
        frac = min(1.0, max(0.0, (x - theme.px(8)) / w))
        return int(round(self.min + frac * (self.max - self.min)))

    def _press(self, e):
        if self._enabled:
            self._drag = True
            self._set(self._value_at(e.x))

    def _move(self, e):
        if self._drag and self._enabled:
            self._set(self._value_at(e.x))

    def _release(self, _e):
        self._drag = False

    def _wheel(self, e):
        if self._enabled:
            self._set(self.var.get() + (1 if e.delta > 0 else -1))

    def _set(self, v):
        v = max(self.min, min(self.max, int(v)))
        if v != self.var.get():
            self.var.set(v)
            self._draw()
            if self.command:
                self.command()
        else:
            self._draw()

    def set_enabled(self, on):
        self._enabled = on
        self.canvas.configure(cursor="hand2" if on else "")
        self.value_lbl.configure(fg=theme.P.text if on else theme.P.faint)
        self._draw()

    def sync(self):
        self._draw()

    # -- painting ----------------------------------------------------------
    def _draw(self):
        p, c = theme.P, self.canvas
        c.delete("all")
        w = c.winfo_width()
        if w <= 1:
            self.after(30, self._draw)
            return
        mid = self.h // 2
        pad = theme.px(8)
        span = max(1, w - pad * 2)
        frac = (self.var.get() - self.min) / max(1, (self.max - self.min))
        x = pad + frac * span
        th = theme.px(6)
        fill = p.accent if self._enabled else p.faint

        c.create_rectangle(pad, mid - th // 2, w - pad, mid + th // 2,
                           fill=mix(p.bg, "#000000", 0.25), outline=p.edge_dim)
        if x > pad + 1:
            c.create_rectangle(pad + 1, mid - th // 2 + 1, x, mid + th // 2 - 1,
                               fill=fill, outline="")
        if skins.angular(p):
            from .skins import panel_points
            k = theme.px(7)
            c.create_polygon(panel_points(x - k, mid - k, x + k, mid + k,
                                          theme.px(4)),
                             fill="#e9eef2" if self._enabled else p.panel2,
                             outline=fill, width=theme.px(2))
        else:
            r = theme.px(8)
            c.create_oval(x - r, mid - r, x + r, mid + r,
                          fill=p.sel_fill if self._enabled else p.panel2,
                          outline=p.accent_dim, width=theme.px(2))
        self.value_lbl.configure(text="%d %s" % (self.var.get(), self.unit))

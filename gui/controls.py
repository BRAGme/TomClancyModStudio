"""Hand-drawn toggle, radio and slider.

ttk's own indicators are a fixed handful of pixels and stay that size on a
scaled display, which on a 150% monitor leaves a checkbox smaller than the
full stop at the end of its own label. These draw themselves on a canvas at
whatever size the theme asks for, and they also give us the look the rest of
the window is going for.
"""

from __future__ import annotations

import tkinter as tk

from . import theme


class _CanvasControl(tk.Canvas):
    def __init__(self, master, width, height, **kw):
        super().__init__(master, width=width, height=height, bg=theme.PANEL,
                         highlightthickness=0, bd=0, takefocus=1, **kw)
        self._enabled = True
        self.bind("<Button-1>", self._clicked)
        self.bind("<Enter>", lambda _e: self._hover(True))
        self.bind("<Leave>", lambda _e: self._hover(False))
        self._hovered = False

    def _hover(self, on):
        self._hovered = on
        self.redraw()

    def _clicked(self, _e):
        if self._enabled:
            self.activate()

    def set_enabled(self, on):
        self._enabled = on
        self.configure(cursor="" if not on else "hand2")
        self.redraw()

    def activate(self):
        raise NotImplementedError

    def redraw(self):
        raise NotImplementedError


class Toggle(tk.Frame):
    """A pill switch plus its label, the whole row clickable."""

    def __init__(self, master, text, variable, command=None):
        super().__init__(master, bg=theme.PANEL)
        self.var = variable
        self.command = command
        self._enabled = True

        w, h = theme.px(38), theme.px(20)
        self.pill = _CanvasControl(self, w, h)
        self.pill.activate = self.toggle
        self.pill.redraw = self._draw
        self.pill.pack(side="left", padx=(0, theme.px(11)))

        self.label = tk.Label(self, text=text, bg=theme.PANEL, fg=theme.TEXT,
                              font=theme.FONT_BOLD, anchor="w", justify="left")
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
        self.label.configure(fg=theme.TEXT if on else theme.FAINT,
                             cursor="hand2" if on else "")
        self.configure(cursor="hand2" if on else "")
        self._draw()

    def sync(self):
        self._draw()

    def _draw(self):
        c = self.pill
        c.delete("all")
        w = int(c["width"])
        h = int(c["height"])
        on = bool(self.var.get())
        r = h // 2
        if not self._enabled:
            track, knob = theme.LINE, theme.FAINT
        elif on:
            track = theme.ACCENT if c._hovered else theme.ACCENT_DIM
            knob = "#f4fbec"
        else:
            track = theme.PANEL_HI if not c._hovered else theme.LINE
            knob = theme.DIM
        _round_rect(c, 1, 1, w - 1, h - 1, r, fill=track, outline="")
        cx = (w - r - 1) if on else (r + 1)
        pad = theme.px(3)
        c.create_oval(cx - r + pad, pad, cx + r - pad, h - pad,
                      fill=knob, outline="")


class RadioRow(tk.Frame):
    """One option of a choice: a dot, a label, and an optional explanation."""

    def __init__(self, master, text, help_text, value, variable, command=None):
        super().__init__(master, bg=theme.PANEL)
        self.var = variable
        self.value = value
        self.command = command
        self._enabled = True

        top = tk.Frame(self, bg=theme.PANEL)
        top.pack(fill="x")
        d = theme.px(18)
        self.dot = _CanvasControl(top, d, d)
        self.dot.activate = self.choose
        self.dot.redraw = self._draw
        self.dot.pack(side="left", padx=(0, theme.px(10)))
        self.label = tk.Label(top, text=text, bg=theme.PANEL, fg=theme.TEXT,
                              font=theme.FONT, anchor="w")
        self.label.pack(side="left", fill="x", expand=True)

        self.help = None
        if help_text:
            self.help = tk.Label(self, text=help_text, bg=theme.PANEL,
                                 fg=theme.DIM, font=theme.FONT_SMALL,
                                 wraplength=theme.px(520), justify="left",
                                 anchor="w")
            self.help.pack(fill="x", padx=(theme.px(28), 0), pady=(theme.px(1), 0))

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
        self.label.configure(fg=theme.TEXT if on else theme.FAINT)
        if self.help:
            self.help.configure(fg=theme.DIM if on else theme.FAINT)
        self._draw()

    def _draw(self):
        c = self.dot
        try:
            c.delete("all")
        except tk.TclError:
            return
        d = int(c["width"])
        on = self.var.get() == self.value
        ring = theme.FAINT if not self._enabled else (
            theme.ACCENT if on or c._hovered else theme.LINE)
        c.create_oval(1, 1, d - 1, d - 1, outline=ring, width=theme.px(2))
        if on:
            p = theme.px(5)
            c.create_oval(p, p, d - p, d - p,
                          fill=theme.ACCENT if self._enabled else theme.FAINT,
                          outline="")


class Slider(tk.Frame):
    """A draggable track with its value spelled out beside it."""

    def __init__(self, master, variable, minimum, maximum, unit="", command=None):
        super().__init__(master, bg=theme.PANEL)
        self.var = variable
        self.min, self.max = minimum, maximum
        self.unit = unit
        self.command = command
        self._enabled = True
        self._drag = False

        self.h = theme.px(26)
        self.canvas = tk.Canvas(self, height=self.h, bg=theme.PANEL,
                                highlightthickness=0, bd=0, cursor="hand2")
        self.canvas.pack(side="left", fill="x", expand=True)
        self.value_lbl = tk.Label(self, text="", bg=theme.PANEL, fg=theme.TEXT,
                                  font=theme.FONT_BOLD, width=13, anchor="e")
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
        if not self._enabled:
            return
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
        self.value_lbl.configure(fg=theme.TEXT if on else theme.FAINT)
        self._draw()

    def sync(self):
        self._draw()

    # -- painting ----------------------------------------------------------
    def _draw(self):
        c = self.canvas
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
        th = theme.px(5)
        fill = theme.ACCENT if self._enabled else theme.FAINT
        _round_rect(c, pad, mid - th // 2, w - pad, mid + th // 2 + 1,
                    th // 2, fill=theme.BG, outline="")
        if x > pad:
            _round_rect(c, pad, mid - th // 2, x, mid + th // 2 + 1,
                        th // 2, fill=fill, outline="")
        r = theme.px(8)
        c.create_oval(x - r, mid - r, x + r, mid + r,
                      fill="#eef6e5" if self._enabled else theme.LINE,
                      outline=fill, width=theme.px(2))
        self.value_lbl.configure(text="%d %s" % (self.var.get(), self.unit))


def _round_rect(canvas, x0, y0, x1, y1, r, **kw):
    r = max(0, min(r, (x1 - x0) // 2, (y1 - y0) // 2))
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
           x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return canvas.create_polygon(pts, smooth=True, **kw)

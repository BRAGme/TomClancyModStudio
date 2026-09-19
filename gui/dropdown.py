r"""A picker that wears the game's skin, instead of Tk's.

Why this is not `ttk.Combobox`
------------------------------

The rest of this window is drawn: sheared corners, hairline edges, the
letterspaced faces each game uses. A `ttk.Combobox`'s drop-down is none of
that. It is a Tk listbox in its own toplevel with its own borders and its own
selection colour, and no amount of styling reaches it -- `ttk::style` does not
own the popdown, which is why the game picker opened as a flat panel with a
teal bar across the highlighted row on every skin.

So the list is replaced. The closed control stays a plain entry-shaped box,
and the open list becomes a canvas this file paints in the window's own
colours -- down to the little red marker the selected nav row wears.

What is deliberately kept
-------------------------

**The `ttk.Combobox` API**, as far as the two call sites use it:
`textvariable`, `values=`, `state="readonly"`, `width=`, and a
`<<ComboboxSelected>>` virtual event on choice. Both pickers were written
against that and neither had to change. It also means the smoke test, which
sets the variable and calls the handler directly, goes on working.

**Keyboard.** Up and Down move, Return and Escape close, and typing a letter
jumps to the next entry starting with it -- which a list of eight games with
four different first letters actually benefits from.

**Closing on anything else.** A click outside or the window moving dismisses
it. A drop-down that survives its parent moving is the kind of thing that
ends up orphaned on the desktop.

Why the list is inside the window
---------------------------------

The obvious build is a borderless `Toplevel`, and that was the first one. It
is wrong here for a reason that is not cosmetic: a window with
`overrideredirect` set has no compositor surface, so `PrintWindow` returns a
black bitmap from it -- and `PrintWindow` is how the smoke test photographs
this application without copying whatever else is on the person's screen. A
control that cannot be captured cannot be checked, and this one exists
precisely because nobody had looked closely at the last one.

So the list is a frame `place`d inside the toplevel. It renders in a capture
like everything else, it cannot be orphaned on the desktop, and it flips to
open UPWARDS when it would otherwise run off the bottom -- which the preset
picker, sitting on the last row of the window, always would.
"""

from __future__ import annotations

import tkinter as tk

from . import theme

#: how many rows are shown before the list scrolls
MAX_ROWS = 12

#: row height and side padding, in unscaled pixels
ROW_H = 26
PAD_X = 10


class Dropdown(tk.Frame):
    """A read-only picker. Quacks like the `ttk.Combobox` it replaces."""

    def __init__(self, master, textvariable=None, values=(), width=30,
                 state="readonly", **kw):
        p = theme.P
        super().__init__(master, bg=p.panel2, highlightthickness=1,
                         highlightbackground=p.edge_dim,
                         highlightcolor=p.edge_dim, **kw)
        self.var = textvariable or tk.StringVar()
        self._values = list(values)
        self._width = width
        self._popup = None
        self._rows = []
        self._hot = -1

        self.label = tk.Label(self, textvariable=self.var, bg=p.panel2,
                              fg=p.text, anchor="w",
                              font=theme.F("body", 10),
                              padx=theme.px(PAD_X), pady=theme.px(4))
        self.label.pack(side="left", fill="both", expand=True)
        self.arrow = tk.Canvas(self, width=theme.px(22), height=theme.px(18),
                               bg=p.panel2, highlightthickness=0, bd=0)
        self.arrow.pack(side="right", fill="y")
        self._draw_arrow()

        for w in (self, self.label, self.arrow):
            w.bind("<Button-1>", self._toggle)
        self.bind("<FocusIn>", lambda _e: self._glow(True))
        self.bind("<FocusOut>", lambda _e: self._glow(False))
        self.bind("<Key>", self._on_key)
        self.configure(takefocus=1)
        self._apply_width()

    # -- the ttk.Combobox surface -----------------------------------------

    def configure(self, cnf=None, **kw):
        values = kw.pop("values", None)
        width = kw.pop("width", None)
        kw.pop("state", None)
        if values is not None:
            self._values = list(values)
        if width is not None:
            self._width = width
        if values is not None or width is not None:
            self._apply_width()
        if cnf or kw:
            return super().configure(cnf, **kw)
        return None

    config = configure

    def get(self):
        return self.var.get()

    def set(self, value):
        self.var.set(value)

    def current(self):
        try:
            return self._values.index(self.var.get())
        except ValueError:
            return -1

    # -- appearance --------------------------------------------------------

    def _apply_width(self):
        longest = max((len(v) for v in self._values), default=0)
        self.label.configure(width=max(12, min(self._width, longest + 2)))

    def _content_width(self):
        """How wide the widest entry actually draws, plus padding."""
        import tkinter.font as tkfont
        font = tkfont.Font(font=theme.F("body", 10))
        widest = max((font.measure(v) for v in self._values), default=0)
        bar = theme.px(18) if len(self._values) > MAX_ROWS else 0
        return widest + theme.px(PAD_X) * 2 + bar + 2

    def _draw_arrow(self):
        p = theme.P
        self.arrow.delete("all")
        w = int(self.arrow.cget("width"))
        h = int(self.arrow.cget("height"))
        cx, cy = w // 2, h // 2
        s = max(3, theme.px(4))
        self.arrow.create_polygon(cx - s, cy - s // 2, cx + s, cy - s // 2,
                                  cx, cy + s, fill=p.accent, outline="")

    def _glow(self, on):
        p = theme.P
        self.configure(highlightbackground=p.accent if on else p.edge_dim,
                       highlightcolor=p.accent if on else p.edge_dim)

    # -- opening and closing ----------------------------------------------

    def _toggle(self, _event=None):
        if self._popup is not None:
            self._close()
        else:
            self.focus_set()
            self._open()
        return "break"

    def _open(self):
        if not self._values:
            return
        p = theme.P
        self.update_idletasks()
        row = theme.px(ROW_H)
        shown = min(len(self._values), MAX_ROWS)
        root = self.winfo_toplevel()
        height = row * shown + 2

        # The list is at least as wide as the closed control, and wider if an
        # entry needs it. Inheriting the control's width alone clipped the
        # longest preset name mid-word, because the preset box shares the
        # bottom bar with four buttons and gets whatever is left over.
        width = max(self.winfo_width(), self._content_width())

        # where the control is, in the toplevel's own coordinates
        x = self.winfo_rootx() - root.winfo_rootx()
        # ...and pulled back in if growing it would hang off the right edge
        x = max(0, min(x, root.winfo_width() - width))
        below = self.winfo_rooty() - root.winfo_rooty() + self.winfo_height()
        # Flip upwards when there is not room beneath. The preset picker sits
        # on the last row of the window and never has any.
        above = below - self.winfo_height() - height
        if below + height > root.winfo_height() and above > 0:
            y = above
        else:
            y = below

        frame = tk.Frame(root, bg=p.edge_dim)
        frame.place(x=x, y=y, width=width, height=height)
        frame.lift()

        canvas = tk.Canvas(frame, bg=p.panel, highlightthickness=0, bd=0,
                           width=width - 2, height=height - 2)
        canvas.place(x=1, y=1, width=width - 2, height=height - 2)
        canvas.configure(scrollregion=(0, 0, width, row * len(self._values)))

        self._popup, self._canvas, self._row_h = frame, canvas, row
        current = self.current()
        self._hot = current if current >= 0 else 0
        self._paint_rows()
        self._scroll_to(self._hot)

        canvas.bind("<Motion>", self._on_motion)
        canvas.bind("<Button-1>", self._on_click)
        canvas.bind("<MouseWheel>",
                    lambda e: (canvas.yview_scroll(-e.delta // 120, "units"),
                               "break")[1])
        # Anything that moves the window out from under the list closes it --
        # but ONLY a real move or resize. A `<Configure>` binding that closes
        # on any event at all closes on the ones Tk fires while laying the
        # window out, which shut the list again in the same breath it opened:
        # the first build of this looked, in a screenshot, exactly as though
        # nothing had happened.
        self._geometry = root.winfo_geometry()
        self._hooks = [
            (root, "<Configure>", root.bind("<Configure>", self._maybe_moved,
                                            "+")),
            (root, "<Button-1>", root.bind("<Button-1>",
                                           lambda _e: self._close(), "+")),
        ]

    def _maybe_moved(self, _event=None):
        if self._popup is None:
            return
        root = self.winfo_toplevel()
        if root.winfo_geometry() != self._geometry:
            self._close()

    def _close(self, _event=None):
        if self._popup is None:
            return
        for widget, sequence, funcid in getattr(self, "_hooks", []):
            try:
                widget.unbind(sequence, funcid)
            except tk.TclError:                   # pragma: no cover
                pass
        self._hooks = []
        try:
            self._popup.destroy()
        except tk.TclError:                       # pragma: no cover
            pass
        self._popup = None

    # -- the list itself ---------------------------------------------------

    def _paint_rows(self):
        p = theme.P
        c = self._canvas
        c.delete("all")
        row = self._row_h
        width = int(c.cget("width"))
        for i, value in enumerate(self._values):
            top = i * row
            if i == self._hot:
                c.create_rectangle(0, top, width, top + row,
                                   fill=p.sel_fill, outline="")
                # the same little marker the selected nav row wears
                c.create_rectangle(0, top + 2, theme.px(3), top + row - 2,
                                   fill=p.tab, outline="")
            c.create_text(theme.px(PAD_X), top + row // 2, anchor="w",
                          text=value, font=theme.F("body", 10),
                          fill=p.sel_text if i == self._hot else p.text)

    def _row_at(self, event):
        return int(self._canvas.canvasy(event.y) // self._row_h)

    def _on_motion(self, event):
        index = self._row_at(event)
        if 0 <= index < len(self._values) and index != self._hot:
            self._hot = index
            self._paint_rows()

    def _on_click(self, event):
        index = self._row_at(event)
        if 0 <= index < len(self._values):
            self._choose(index)
        return "break"

    def _scroll_to(self, index):
        total = len(self._values)
        if total <= MAX_ROWS:
            return
        self._canvas.yview_moveto(max(0.0, (index - MAX_ROWS // 2) / total))

    def _choose(self, index):
        self.var.set(self._values[index])
        self._close()
        self.event_generate("<<ComboboxSelected>>")

    # -- keyboard ----------------------------------------------------------

    def _on_key(self, event):
        key = event.keysym
        if key in ("Down", "Up") and self._popup is None:
            self._open()
            return "break"
        if self._popup is None:
            if len(event.char) == 1 and event.char.isprintable():
                return self._jump(event.char)
            return None
        if key == "Escape":
            self._close()
        elif key in ("Return", "space"):
            self._choose(self._hot)
        elif key == "Down":
            self._hot = min(len(self._values) - 1, self._hot + 1)
            self._paint_rows()
            self._scroll_to(self._hot)
        elif key == "Up":
            self._hot = max(0, self._hot - 1)
            self._paint_rows()
            self._scroll_to(self._hot)
        elif len(event.char) == 1 and event.char.isprintable():
            return self._jump(event.char)
        return "break"

    def _jump(self, char):
        """Move to the next entry starting with `char`, wrapping."""
        char = char.lower()
        start = (self._hot + 1) if self._popup is not None else self.current() + 1
        order = list(range(start, len(self._values))) + list(range(0, start))
        for i in order:
            if self._values[i].lstrip().lower().startswith(char):
                if self._popup is not None:
                    self._hot = i
                    self._paint_rows()
                    self._scroll_to(i)
                else:
                    self._choose_silently(i)
                break
        return "break"

    def _choose_silently(self, index):
        self.var.set(self._values[index])
        self.event_generate("<<ComboboxSelected>>")

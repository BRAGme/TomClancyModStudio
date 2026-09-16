"""A hover bubble, and the little question mark that opens it.

Why the cards needed this
-------------------------

Every option carries a `help` paragraph and most carry a `caution` as well,
and both were rendered inline underneath the control. That is honest but it is
long: Rainbow Six 3's Feel page is fifteen cards deep and several of them --
the aiming ones especially -- spend two paragraphs explaining a measurement
before you reach the thing you came to click.

So the prose moves into a bubble behind a `?`, and the card keeps a one-line
summary. The summary is the help text's own first sentence -- not a separate
string to write and keep in step, just the part the author already put first.

What is deliberately NOT hidden
-------------------------------

A `caution` still shows inline. Those say things like "not play-tested" or
"this can freeze the initial load", and a warning you have to go looking for is
not a warning. The `?` carries the full detail; the short form stays where it
cannot be missed.

A `table` is never hidden either. On this tool the table often IS the option:
the aiming cards exist to put two columns of numbers read off two discs beside
each other, and a hover bubble is the wrong shape for columns.
"""

#: Shared with the PS2 tool's `gui/tooltip.py`, which is where it was written.
#: The two copies are kept identical apart from this note and the examples in
#: the docstring -- the same arrangement as `lin.py`, and for the same reason:
#: the last time two copies of a file were left to drift, one of them quietly
#: fell behind by two features. Change one, change the other.

from __future__ import annotations

import tkinter as tk

from . import theme

#: how long the pointer must rest before the bubble appears
DELAY_MS = 350

#: the bubble wraps at this many pixels
WRAP = 420


#: A summary shorter than this is not a summary. Cautions are the reason:
#: theirs routinely open with a bare qualifier -- "Experimental.",
#: "Untested.", "Not play-tested." -- and stopping at the first full stop
#: threw the entire warning away while leaving the card looking like it still
#: carried one. Thirty-five cards across the eight games did exactly that.
FLOOR = 40


def first_sentence(text: str, limit: int = 150, floor: int = FLOOR) -> str:
    """The opening of `text`, for the one-line summary on a card.

    Takes whole sentences until there is something substantive, rather than
    always exactly one: "Experimental." is a label, not a summary, and the
    sentence that follows is the part worth reading. Text that runs out first
    is returned whole -- a summary that hides nothing cannot be a bad one.

    Falls back to a clipped prefix when the result is enormous, which a few of
    the longer cautions are.
    """
    if not text:
        return ""
    flat = " ".join(text.split())
    # Only a full stop or a semicolon ends a sentence here. An em-dash aside
    # nearly always continues one, and splitting on it cut lines mid-thought.
    out, rest = "", flat
    while rest:
        cut = -1
        for end in (". ", "; "):
            at = rest.find(end)
            if at != -1 and (cut == -1 or at < cut):
                cut = at + (1 if end == ". " else 0)
        if cut == -1:
            out = (out + " " + rest).strip()
            break
        out = (out + " " + rest[:cut]).strip().rstrip(" ;")
        rest = rest[cut:].lstrip(" ;")
        if len(out) >= floor:
            break
    if len(out) > limit:
        out = out[:limit].rsplit(" ", 1)[0] + "..."
    return out


class Bubble:
    """A borrowed toplevel that follows one widget."""

    def __init__(self, owner, text):
        self.owner = owner
        self.text = text
        self.win = None
        self._after = None
        owner.bind("<Enter>", self._enter, add="+")
        owner.bind("<Leave>", self._leave, add="+")
        owner.bind("<ButtonPress>", self._leave, add="+")

    def _enter(self, _e=None):
        self._cancel()
        self._after = self.owner.after(DELAY_MS, self._show)

    def _leave(self, _e=None):
        self._cancel()
        self.hide()

    def _cancel(self):
        if self._after is not None:
            try:
                self.owner.after_cancel(self._after)
            except Exception:                   # noqa: BLE001
                pass
            self._after = None

    def _show(self):
        if self.win is not None or not self.text:
            return
        p = theme.P
        try:
            x = self.owner.winfo_rootx() + self.owner.winfo_width() + theme.px(8)
            y = self.owner.winfo_rooty() - theme.px(4)
        except Exception:                       # noqa: BLE001
            return
        self.win = tk.Toplevel(self.owner)
        self.win.wm_overrideredirect(True)
        self.win.configure(bg=p.edge_dim)
        inner = tk.Frame(self.win, bg=p.panel2 if hasattr(p, "panel2") else p.panel)
        inner.pack(padx=1, pady=1)
        tk.Label(inner, text=self.text, bg=inner["bg"], fg=p.text,
                 font=theme.F("body", 9), wraplength=theme.px(WRAP),
                 justify="left", anchor="w",
                 padx=theme.px(10), pady=theme.px(8)).pack()
        self.win.update_idletasks()
        # keep it on screen: flip to the left if it would run off the edge
        sw = self.win.winfo_screenwidth()
        if x + self.win.winfo_width() > sw - theme.px(8):
            x = max(theme.px(8),
                    self.owner.winfo_rootx() - self.win.winfo_width()
                    - theme.px(8))
        self.win.wm_geometry("+%d+%d" % (x, y))

    def hide(self):
        if self.win is not None:
            try:
                self.win.destroy()
            except Exception:                   # noqa: BLE001
                pass
            self.win = None


class Hint(tk.Canvas):
    """A small `?` that shows `text` on hover."""

    def __init__(self, master, text, size=None):
        d = size or theme.px(16)
        super().__init__(master, width=d, height=d, highlightthickness=0,
                         bd=0, bg=theme.P.panel, cursor="question_arrow")
        self.d = d
        self._hot = False
        self.bubble = Bubble(self, text)
        self.bind("<Enter>", self._on, add="+")
        self.bind("<Leave>", self._off, add="+")
        self.redraw()

    def _on(self, _e=None):
        self._hot = True
        self.redraw()

    def _off(self, _e=None):
        self._hot = False
        self.redraw()

    def redraw(self):
        p = theme.P
        self.delete("all")
        self.configure(bg=p.panel)
        edge = p.text if self._hot else p.dim
        d = self.d
        self.create_oval(1, 1, d - 2, d - 2, outline=edge, width=1)
        self.create_text(d / 2, d / 2 + 1, text="?", fill=edge,
                         font=theme.F("bold", 8))

    def set_enabled(self, on):                  # matches the other controls
        self._hot = False
        self.redraw()

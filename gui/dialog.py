"""Message and confirmation sheets, wearing the disc's own skin.

Why these are not `tkinter.messagebox`
--------------------------------------

The common dialog is a white Windows box with a blue system icon, and it
appears in the middle of a Rainbow Six HUD or a Ghost Recon gold-on-navy
panel. It reads as a different program interrupting this one.

The second reason is worse and is what actually forced the change: the common
dialog **cannot scroll**. The apply sheet lists every option's caution, which
on a disc with several experimental settings turned on runs to well over a
thousand words, and the box simply grows until it is taller than the screen
with the buttons pushed off the bottom. Here the body scrolls and the sheet
never exceeds a fraction of the display.

What is deliberately kept
-------------------------

Modality, the Enter/Escape keys, and the return values -- `ask` gives back a
plain bool exactly as `askokcancel` did -- so every call site reads the same
as before and nothing downstream has to know.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import theme
from .widgets import ActionButton, Chrome

#: the sheet never grows past this much of the screen, body scrolls instead
MAX_H = 0.62

#: the message column, in characters. Wide enough that a caution paragraph
#: does not turn into a ladder, narrow enough to stay readable.
COLS = 74

#: never shorter than this, never taller before the scrollbar takes over
MIN_ROWS = 3
MAX_ROWS = 34

#: The panel is a canvas and does not hand the Text's width back up the
#: layout, so the sheet would otherwise be sized by its header and buttons --
#: about 410px, which wraps a caution into a ladder. Set explicitly instead.
MIN_W = 620

#: kind -> (which palette colour names the mark, what the mark says)
KINDS = {
    "info": ("accent", "i"),
    "warn": ("warn", "!"),
    "error": ("bad", "!"),
    "ask": ("accent", "?"),
}


class Sheet(tk.Toplevel):
    """One modal message, with an optional Cancel."""

    def __init__(self, master, title, message, kind="info", cancel=False,
                 ok_text="OK", cancel_text="Cancel"):
        super().__init__(master)
        p = theme.P
        self.result = False
        self.title(title or "")
        self.configure(bg=p.bg)
        self.transient(master.winfo_toplevel())

        pad = theme.px(16)
        outer = tk.Frame(self, bg=p.bg)
        outer.pack(fill="both", expand=True, padx=pad, pady=pad)

        head = tk.Frame(outer, bg=p.bg)
        head.pack(fill="x", pady=(0, theme.px(10)))
        self._mark(head, kind)
        tk.Label(head, text=(title or "").upper(), bg=p.bg, fg=p.title,
                 font=theme.F("bold", 11), anchor="w").pack(
                     side="left", padx=(theme.px(10), 0))

        # autofit, so the panel takes its height from the text inside it --
        # with autofit off it has no natural size and the whole sheet
        # collapses to its minimum no matter how long the message is.
        panel = Chrome(outer, kind="panel", pad=theme.px(10))
        panel.pack(fill="both", expand=True)

        body = tk.Frame(panel.body, bg=p.panel)
        body.pack(fill="both", expand=True)
        self.text = tk.Text(body, bg=p.panel, fg=p.text, bd=0,
                            highlightthickness=0, wrap="word",
                            font=theme.F("body", 10),
                            padx=theme.px(6), pady=theme.px(4),
                            insertbackground=p.panel,
                            selectbackground=p.sel_fill,
                            selectforeground=p.sel_text)
        self.bar = ttk.Scrollbar(body, orient="vertical",
                                 command=self.text.yview,
                                 style="Vertical.TScrollbar")
        self.text.configure(yscrollcommand=self.bar.set)
        # The bar is packed FIRST and hidden later if it turns out not to be
        # needed. Packed after an expanding Text it is allocated nothing and
        # never appears, however long the message is.
        self.bar.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.insert("1.0", message or "")
        # Read-only, but still selectable and copyable -- people paste these
        # into a message to ask what they mean.
        self.text.configure(state="disabled")

        row = tk.Frame(outer, bg=p.bg)
        row.pack(fill="x", pady=(theme.px(12), 0))
        self.ok_btn = ActionButton(row, ok_text, self._ok, accent=True)
        self.ok_btn.configure(width=self.ok_btn.width_needed())
        self.ok_btn.pack(side="right")
        if cancel:
            self.cancel_btn = ActionButton(row, cancel_text, self._cancel)
            self.cancel_btn.configure(width=self.cancel_btn.width_needed())
            self.cancel_btn.pack(side="right", padx=(0, theme.px(10)))

        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self._cancel() if cancel else self._ok())
        self.protocol("WM_DELETE_WINDOW",
                      self._cancel if cancel else self._ok)

        self._size(panel)
        self._centre(master)
        self.grab_set()
        self.ok_btn.focus_set()

    # -- chrome ----------------------------------------------------------
    def _mark(self, parent, kind):
        """A drawn ring rather than a system icon, so it follows the skin."""
        p = theme.P
        colour_name, glyph = KINDS.get(kind, KINDS["info"])
        colour = getattr(p, colour_name, p.accent)
        d = theme.px(22)
        c = tk.Canvas(parent, width=d, height=d, bg=p.bg,
                      highlightthickness=0, bd=0)
        c.pack(side="left")
        c.create_oval(1, 1, d - 2, d - 2, outline=colour, width=theme.px(1))
        c.create_text(d / 2, d / 2 + 1, text=glyph, fill=colour,
                      font=theme.F("bold", 11))

    def _size(self, panel):
        """Fit the text, then cap the height and let the body scroll.

        The Text is sized in CHARACTERS and lines, and Tk sizes the toplevel
        from it, so there is no explicit geometry here at all -- an explicit
        one is what collapsed this to its minimum before.
        """
        wanted = self._rows()
        rows = min(wanted, MAX_ROWS)
        self.text.configure(width=COLS, height=rows)
        # `update`, not `update_idletasks`: the panel takes its height from a
        # <Configure> binding, which does not fire on idle alone, so an idle
        # measurement reads a stale height and the cap below never bites.
        self.update()
        # Shrink until it fits rather than computing a per-line height and
        # trusting it: the chrome, the header and the button row all
        # contribute, and one arithmetic guess got that wrong.
        cap = int(self.winfo_screenheight() * MAX_H)
        while rows > MIN_ROWS and self.winfo_reqheight() > cap:
            rows -= 1
            self.text.configure(height=rows)
            self.update()
        if wanted <= rows:
            self.bar.pack_forget()          # nothing to scroll
            self.update()
        width = max(theme.px(MIN_W), self.winfo_reqwidth())
        self.geometry("%dx%d" % (width, self.winfo_reqheight()))
        self.minsize(width, self.winfo_reqheight())
        self.update()

    def _rows(self) -> int:
        """How many display lines the message needs once wrapped at COLS."""
        total = 0
        last = int(self.text.index("end-1c").split(".")[0])
        for n in range(1, last + 1):
            body = self.text.get("%d.0" % n, "%d.end" % n)
            total += max(1, -(-len(body) // COLS))
        return max(MIN_ROWS, total)

    def _centre(self, master):
        top = master.winfo_toplevel()
        self.update_idletasks()
        x = top.winfo_rootx() + (top.winfo_width() - self.winfo_width()) // 2
        y = top.winfo_rooty() + (top.winfo_height() - self.winfo_height()) // 3
        self.geometry("+%d+%d" % (max(0, x), max(0, y)))

    # -- outcome ---------------------------------------------------------
    def _ok(self):
        self.result = True
        self._close()

    def _cancel(self):
        self.result = False
        self._close()

    def _close(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


def _run(master, title, message, kind, cancel, **kw) -> bool:
    dlg = Sheet(master, title, message, kind=kind, cancel=cancel, **kw)
    master.wait_window(dlg)
    return dlg.result


def info(master, title, message) -> bool:
    return _run(master, title, message, "info", False)


def warn(master, title, message) -> bool:
    return _run(master, title, message, "warn", False)


def error(master, title, message) -> bool:
    return _run(master, title, message, "error", False)


def ask(master, title, message, ok_text="OK", cancel_text="Cancel") -> bool:
    """Modal question. True for the affirmative, exactly like askokcancel."""
    return _run(master, title, message, "ask", True,
                ok_text=ok_text, cancel_text=cancel_text)

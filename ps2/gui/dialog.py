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
import tkinter.font as tkfont
from tkinter import ttk

from tcps2 import applied

from . import theme
from .controls import RadioRow
from .widgets import ActionButton, Chrome

#: the sheet never grows past this much of the screen, body scrolls instead
MAX_H = 0.62

#: the message column, in characters. Wide enough that a caution paragraph
#: does not turn into a ladder, narrow enough to stay readable.
COLS = 74

#: the apply sheet's column. Wider than the rest so that no row of its change
#: list has to be broken: the longest label with its badge, and the longest
#: pair of choice labels, both fit.
CHANGE_COLS = 84

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
    """One modal message, with an optional Cancel.

    `message` is plain text, or a list of (text, tags) runs for a sheet that
    has to colour some of its lines. `extra(parent)`, when given, adds widgets
    under the text before the sheet is sized, so they count toward its height.
    """

    def __init__(self, master, title, message, kind="info", cancel=False,
                 ok_text="OK", cancel_text="Cancel", cols=COLS, extra=None):
        super().__init__(master)
        self.cols = cols
        # Invisible, but MAPPED, until it has been sized and placed.
        # `_size` calls `update`, which maps the window, so without this the
        # sheet appears at Tk's default position, gets measured, and then
        # jumps to the middle -- a visible flicker to the left of the screen.
        # `withdraw` would hide it, but a withdrawn window never receives the
        # <Configure> events the panel sizes itself from, and every sheet
        # then collapses to the same wrong height. Transparency hides it
        # while leaving the geometry machinery running.
        try:
            self.attributes("-alpha", 0.0)
        except tk.TclError:                 # no compositing: live with it
            pass
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
        for name in ("good", "warn", "bad", "dim"):
            self.text.tag_configure(name, foreground=theme.colour(name))
        self.text.tag_configure("mono", font=theme.F("mono", 9))
        if isinstance(message, str) or not message:
            self.text.insert("1.0", message or "")
        else:
            for run, tags in message:
                self.text.insert("end", run, tags)
        # Read-only, but still selectable and copyable -- people paste these
        # into a message to ask what they mean.
        self.text.configure(state="disabled")
        if extra is not None:
            extra(panel.body)

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

        # The reveal is in a `finally`, and it has to stay there. If sizing
        # throws, an un-revealed sheet is a window at alpha 0 that the caller
        # is already blocked on in `wait_window` -- invisible, undismissable,
        # and indistinguishable from the application hanging. That happened:
        # a real error dialog never appeared and the apply looked stuck.
        try:
            self._size(panel)
            self._centre(master)
        finally:
            self._reveal()
        # Belt and braces, in case something later re-hides it.
        self.after(1200, self._reveal)

    def _reveal(self):
        """Make the sheet visible and usable. Safe to call more than once."""
        for step in (lambda: self.attributes("-alpha", 1.0),
                     self.deiconify, self.lift, self.grab_set,
                     self.ok_btn.focus_set):
            try:
                step()
            except tk.TclError:
                pass                     # a dead window, or no compositing

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
        self.text.configure(width=self.cols, height=rows)
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
        """How many display lines the message needs once wrapped at `cols`."""
        total = 0
        last = int(self.text.index("end-1c").split(".")[0])
        for n in range(1, last + 1):
            body = self.text.get("%d.0" % n, "%d.end" % n)
            total += max(1, -(-len(body) // self.cols))
        return max(MIN_ROWS, total)

    def _centre(self, master):
        top = master.winfo_toplevel()
        self.update()
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


def _table(changes, width):
    """The change list as (line, tags) pairs, no line wider than `width`.

    One line a setting where it fits -- the label, the old value right-aligned
    against the arrow, the new one -- in a fixed pitch, because the columns
    only line up in one. Where it does not fit, the label goes above and the
    values beneath it, rather than letting Tk wrap the line: `_rows` counts
    characters, and a line Tk wrapped is a line it did not count, which is how
    the end of a list ends up out of sight with no scrollbar.
    """
    rows = []
    for ch in changes:
        tone, text = theme.BADGE.get(ch.risk, ("warn", ch.risk or ""))
        rows.append((ch.setting.label, applied.show(ch.setting, ch.before),
                     applied.show(ch.setting, ch.after),
                     "  " + text.upper() if ch.risk else "",
                     ("mono", tone) if ch.risk else ("mono",)))
    single = [r for r in rows if len(r[0]) <= width // 2]
    lw = max((len(r[0]) for r in single), default=0)
    ow = min(max((len(r[1]) for r in single), default=0), width // 4)
    out = []
    for label, old, new, badge, tags in rows:
        line = "  %-*s  %*s  >  %s%s" % (lw, label, ow, old, new, badge)
        if len(label) <= lw and len(old) <= ow and len(line) <= width:
            out.append((line, tags))
            continue
        out.append(("  " + label + badge, tags))
        # under the other rows' values if it fits there, indented if not
        pair = "  %-*s  %*s  >  %s" % (lw, "", ow, old, new)
        if len(old) > ow or len(pair) > width:
            pair = "      %s  >  %s" % (old, new)
        if len(pair) <= width:
            out.append((pair, tags))
        else:
            out += [("      " + old, tags), ("    > " + new, tags)]
    return out


def confirm_changes(master, title, head, changes, notes) -> bool:
    """The apply sheet: every setting that will change, then the plan.

    Laid out like a BIOS "save changes" screen. A row that turns on something
    not yet watched working is drawn in the warning colour, with the badge the
    setting's own card wears. That one cue is what was missing when moving a
    single dial carried two untested script rewrites onto a disc with it, and
    the level load hung.
    """
    risky = sum(1 for ch in changes if ch.risk)
    runs = [(head, ())]
    if changes:
        # the widest the table can be in the fixed pitch without wrapping
        body = tkfont.Font(font=theme.F("body", 10)).measure("0")
        mono = tkfont.Font(font=theme.F("mono", 9)).measure("0")
        width = min(CHANGE_COLS, CHANGE_COLS * body // mono) - 2
        runs.append(("\n", ()))
        runs += [("\n" + line, tags) for line, tags in _table(changes, width)]
    if risky:
        runs.append((
            "\n\n%d of these %s not been watched working in the game. If "
            "anything misbehaves after this, %s the first thing to turn off."
            % (risky, "has" if risky == 1 else "have",
               "that is" if risky == 1 else "those are"), ("warn",)))
    if notes:
        runs.append(("\n\n" + "\n".join(notes), ()))
    return _run(master, title, runs, "warn" if risky else "ask", True,
                ok_text="Confirm", cols=CHANGE_COLS)


def choose(master, title, message, options, ok_text="OK",
           cancel_text="Cancel"):
    """Modal pick-one from `options`, a list of (label, help) pairs.

    The index chosen, or None for Cancel. The first option starts selected, so
    Enter on its own takes it.
    """
    picked = tk.IntVar(master, value=0)

    def rows(parent):
        box = tk.Frame(parent, bg=theme.P.panel)
        box.pack(fill="x", pady=(theme.px(10), 0))
        for i, (label, help_text) in enumerate(options):
            RadioRow(box, label, help_text, i, picked).pack(
                fill="x", pady=(0, theme.px(7)))

    ok = _run(master, title, message, "ask", True, ok_text=ok_text,
              cancel_text=cancel_text, extra=rows)
    return picked.get() if ok else None

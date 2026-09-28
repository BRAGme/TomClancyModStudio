"""The Discord Rich Presence sheet.

Wears the active skin, for the same reason everything else does: a Windows
common dialog in the middle of a Rainbow Six HUD looks like a different
program.

WHAT THIS SHEET IS FOR NOW
--------------------------

It used to configure presence for *this window* -- "Playing Tom Clancy PS2 Mod
Studio" -- and it needed the user to go and register a Discord application of
their own before anything appeared at all. Two things were wrong with that.
Nobody has the patcher open while they are actually playing, so the presence
was live at precisely the wrong moment; and the registration step meant the
feature stayed silently dead for almost everyone.

So it now switches on presence for **the game**, by driving `drp.exe`, which
watches PCSX2 and says what you are doing -- the mission, the operative, the
objectives, the difficulty. It ships with its own application ids, so there is
nothing to register and nothing to paste.

Everything the sheet claims is read from the system when it opens, not
remembered from last time: the usual case is that `drp` was started at login,
or on a previous run, and this window has never seen it.
"""

from __future__ import annotations

import tkinter as tk

from . import gamepresence, theme
from .controls import Toggle
from .widgets import ActionButton


class DiscordDialog(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        p = theme.P
        self.title("Discord Rich Presence")
        self.configure(bg=p.bg)
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        self.result = None

        self.st = gamepresence.status()
        self.startup = tk.BooleanVar(value=False)

        pad = theme.px(18)
        body = tk.Frame(self, bg=p.bg)
        body.pack(padx=pad, pady=pad)

        tk.Label(body, text="Show the game you are playing on Discord",
                 bg=p.bg, fg=p.text, anchor="w", font=theme.F("body", 11)
                 ).pack(fill="x")

        tk.Label(body, text=_BLURB, bg=p.bg, fg=p.dim, justify="left",
                 anchor="w", font=theme.F("body", 9),
                 wraplength=theme.px(430)).pack(fill="x",
                                                pady=(theme.px(10), 0))

        tk.Label(body, text=_EXAMPLE, bg=p.panel, fg=p.dim, justify="left",
                 anchor="w", font=theme.F("mono", 8), padx=theme.px(10),
                 pady=theme.px(8)).pack(fill="x", pady=(theme.px(10), 0))

        # Not fill="x": the toggle carries a panel background, and stretched
        # across the sheet it reads as a header band rather than a control.
        Toggle(body, "Start it when I log in", self.startup,
               self._startup_changed).pack(anchor="w",
                                           pady=(theme.px(14), 0))

        self.state_lbl = tk.Label(body, text="", bg=p.bg, fg=p.dim,
                                  anchor="w", justify="left",
                                  font=theme.F("body", 9),
                                  wraplength=theme.px(430))
        self.state_lbl.pack(fill="x", pady=(theme.px(12), 0))

        bar = tk.Frame(self, bg=p.bg)
        bar.pack(fill="x", padx=pad, pady=(0, pad))
        self.close_btn = ActionButton(bar, "Close", self._close)
        self.close_btn.configure(width=self.close_btn.width_needed())
        self.close_btn.pack(side="right", padx=(theme.px(8), 0))
        self.toggle_btn = ActionButton(bar, "Turn on", self._toggle,
                                       accent=True)
        self.toggle_btn.configure(width=self.toggle_btn.width_needed())
        self.toggle_btn.pack(side="right", padx=(theme.px(8), 0))

        self._refresh()
        self.bind("<Escape>", lambda _e: self._close())
        self.update_idletasks()
        self._centre(master)
        self.grab_set()

    # -- state ------------------------------------------------------------
    def _refresh(self, note=""):
        self.st = gamepresence.status()
        p = theme.P
        if not self.st["supported"]:
            msg = ("Game presence is Windows only, because it reads PCSX2 "
                   "through PINE on a named pipe.")
            colour = p.dim
        elif not self.st["installed"]:
            msg = ("drp.exe was not found. It ships in a \"drp\" folder beside "
                   "this program; if you moved one of them, put them back "
                   "together.")
            colour = p.bad
        elif self.st["running"]:
            msg = ("Running. Discord shows the game while PCSX2 is open -- "
                   "start Discord first if it is not already.")
            colour = p.good
        else:
            msg = "Not running."
            colour = p.dim
        self.state_lbl.configure(text=(note + "  " if note else "") + msg,
                                 fg=colour)
        # set_text, NOT configure(text=...): ActionButton is a Canvas, and a
        # Canvas has no -text option. Tk raises for it, which in a refresh
        # called from two places left the button reading "Turn on" while the
        # line above it correctly said the thing was already running.
        self.toggle_btn.set_text(
            "Turn off" if self.st["running"] else "Turn on")
        self.toggle_btn.set_enabled(
            self.st["supported"] and self.st["installed"])

    # -- actions ----------------------------------------------------------
    def _toggle(self):
        if not (self.st["supported"] and self.st["installed"]):
            return
        if self.st["running"]:
            _ok, note = gamepresence.stop()
        else:
            _ok, note = gamepresence.start()
        self.result = note
        self._refresh(note)

    def _startup_changed(self):
        if not (self.st["supported"] and self.st["installed"]):
            self.startup.set(False)
            return
        _ok, note = gamepresence.set_startup(bool(self.startup.get()))
        self.result = note
        self._refresh(note)

    def _centre(self, master):
        top = master.winfo_toplevel()
        x = top.winfo_rootx() + (top.winfo_width() - self.winfo_width()) // 2
        y = top.winfo_rooty() + (top.winfo_height() - self.winfo_height()) // 3
        self.geometry("+%d+%d" % (max(0, x), max(0, y)))

    def _close(self):
        self.grab_release()
        self.destroy()


_BLURB = (
    "This switches on a small background program, drp, that watches the "
    "emulator and tells Discord what you are actually doing -- the mission, "
    "who you are playing as, how many objectives are left. It keeps running "
    "after you close this window, which is the point: you are not patching a "
    "disc and playing it at the same time.\n\n"
    "There is nothing to sign up for. It carries its own Discord application, "
    "so it works the moment you turn it on.")

_EXAMPLE = (
    "PCSX2\n"
    "Rainbow Six 3  -  Terrorist Hunt\n"
    "Alpine Village A  -  Split screen  -  01:12 elapsed")


def configure(master, live=None):
    """Modal. Returns the last thing that happened, or None.

    `live` is accepted and ignored: it was the old in-process presence object,
    and keeping the signature means a caller that still passes it does not
    break while it is being tidied up.
    """
    dlg = DiscordDialog(master)
    master.wait_window(dlg)
    return dlg.result

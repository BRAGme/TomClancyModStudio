"""The Discord Rich Presence settings sheet.

Wears the active skin, for the same reason everything else does: a Windows
common dialog in the middle of a Rainbow Six HUD looks like a different
program.

The whole dialog exists because of one awkward fact -- Discord will not show a
presence without an application id belonging to a real account, and there is no
shared one to ship. So rather than silently doing nothing, the sheet says what
is needed, in the order you would do it, and tells you whether the connection
actually came up.
"""

from __future__ import annotations

import tkinter as tk
import webbrowser

from . import presence, theme
from .controls import Toggle
from .widgets import ActionButton

PORTAL = "https://discord.com/developers/applications"


class DiscordDialog(tk.Toplevel):
    def __init__(self, master, live: presence.Presence | None):
        super().__init__(master)
        p = theme.P
        self.title("Discord Rich Presence")
        self.configure(bg=p.bg)
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        self.result = None
        self.live = live

        saved = presence.load()
        self.enabled = tk.BooleanVar(value=saved["enabled"])
        self.app_id = tk.StringVar(value=saved["app_id"])

        pad = theme.px(18)
        body = tk.Frame(self, bg=p.bg)
        body.pack(padx=pad, pady=pad)

        # Not fill="x": the toggle carries a panel background, and stretched
        # across the sheet it reads as a header band rather than a control.
        Toggle(body, "Show what I am editing on Discord", self.enabled,
               lambda: None).pack(anchor="w")

        tk.Label(body, text=presence.HOW_TO, bg=p.bg, fg=p.dim, justify="left",
                 anchor="w", font=theme.F("body", 9),
                 wraplength=theme.px(430)).pack(fill="x", pady=(theme.px(14), 0))

        # The asset names are exact strings Discord matches on, so they are
        # shown in a fixed pitch to be copied rather than retyped from prose.
        tk.Label(body, text=presence.ASSET_HELP, bg=p.panel, fg=p.dim,
                 justify="left", anchor="w", font=theme.F("mono", 8),
                 padx=theme.px(10), pady=theme.px(8)
                 ).pack(fill="x", pady=(theme.px(8), 0))

        link = tk.Label(body, text=PORTAL, bg=p.bg, fg=p.accent, anchor="w",
                        cursor="hand2", font=theme.F("body", 9))
        link.pack(fill="x", pady=(theme.px(6), 0))
        link.bind("<Button-1>", lambda _e: webbrowser.open(PORTAL))

        row = tk.Frame(body, bg=p.bg)
        row.pack(fill="x", pady=(theme.px(14), 0))
        tk.Label(row, text="Application ID", bg=p.bg, fg=p.text, anchor="w",
                 font=theme.F("body", 10)).pack(side="left")
        self.entry = tk.Entry(row, textvariable=self.app_id, width=24,
                              bg=p.panel2, fg=p.text, relief="flat",
                              insertbackground=p.text, highlightthickness=1,
                              highlightbackground=p.edge_dim,
                              highlightcolor=p.edge, font=theme.F("mono", 10))
        self.entry.pack(side="left", padx=(theme.px(12), 0))

        self.state_lbl = tk.Label(body, text=self._status(), bg=p.bg, fg=p.dim,
                                  anchor="w", justify="left",
                                  font=theme.F("body", 9),
                                  wraplength=theme.px(430))
        self.state_lbl.pack(fill="x", pady=(theme.px(10), 0))

        bar = tk.Frame(self, bg=p.bg)
        bar.pack(fill="x", padx=pad, pady=(0, pad))
        # A bare tk.Canvas asks for 378 logical pixels, which would drag this
        # sheet out to three times the width of its own content.
        for text, fn, accent in (("Cancel", self._cancel, False),
                                 ("Save", self._ok, True)):
            btn = ActionButton(bar, text, fn, accent=accent)
            btn.configure(width=btn.width_needed())
            btn.pack(side="right", padx=(theme.px(8), 0))

        self.bind("<Escape>", lambda _e: self._cancel())
        self.bind("<Return>", lambda _e: self._ok())
        self.update_idletasks()
        self._centre(master)
        self.grab_set()
        self.entry.focus_set()

    def _status(self) -> str:
        if self.live is None:
            return "Not running. Save with the toggle on to start it."
        if self.live.connected:
            return "Connected to Discord."
        return "Not connected: %s. It keeps retrying, so starting Discord " \
               "later is enough." % (self.live.error or "no reason given")

    def _centre(self, master):
        top = master.winfo_toplevel()
        x = top.winfo_rootx() + (top.winfo_width() - self.winfo_width()) // 2
        y = top.winfo_rooty() + (top.winfo_height() - self.winfo_height()) // 3
        self.geometry("+%d+%d" % (max(0, x), max(0, y)))

    def _ok(self):
        app_id = self.app_id.get().strip()
        on = bool(self.enabled.get())
        if on and not app_id.isdigit():
            self.state_lbl.configure(
                fg=theme.P.bad,
                text="An application id is all digits, and Discord will not "
                     "show anything without one. Paste it from the portal "
                     "page, or turn the toggle off.")
            return
        presence.save(on, app_id)
        self.result = (on, app_id)
        self.grab_release()
        self.destroy()

    def _cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()


def configure(master, live):
    """Modal. Returns (enabled, app_id), or None if cancelled."""
    dlg = DiscordDialog(master, live)
    master.wait_window(dlg)
    return dlg.result

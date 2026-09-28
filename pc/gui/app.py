r"""Tom Clancy PC Mod Studio -- the window.

The same window as the PS2 and Xbox tools: one canvas holding the loaded game's
own artwork, with every part of the interface placed onto it so the backdrop
shows in the gaps the way it does in the games' own menus. Which skin is in
force follows the game.

What changes on PC is the thing being opened. There is no disc image and no
CRC; there is a FOLDER, and the two questions at the top of the window are
"where is your Steam library" and "which game in it". And there are two ways an
option can reach the game rather than one -- a generated mod folder for the two
Red Storm titles that load them, the files themselves for the other three --
so the window says which of those it is about to do before it does it.
"""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
import tkinter as tk
import traceback
from tkinter import filedialog

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tcpc import art, engine  # noqa: E402
from tcpc.games import PROFILES  # noqa: E402
from tcpc.install import identify, look, preview_detection  # noqa: E402
from tcpc.model import BOOL, INT, MOD, OVERLAY  # noqa: E402

from . import dialog, discorddialog, dropdown, presence, skins, theme  # noqa: E402
from .presets import PRESETS  # noqa: E402
from .widgets import (ActionButton, Chrome, NavItem, ScrollArea,
                      SettingCard, nav_style)  # noqa: E402

APP_NAME = "Tom Clancy PC Mod Studio"
PRESET_HINT = "Choose a preset…"
#: Bumped whenever the option set changes, because the only question a user
#: can ask about a downloaded executable is "is this the new one" -- and with
#: a fixed name and a fixed version there is no way to answer it. The window
#: title and the first log line both carry it.
VERSION = "1.0"
NOTES_TAB = "About this game"


def _option_count():
    """Every enabled option across every profile.

    On the ready line because it is the cheapest possible answer to "did the
    build I just downloaded actually get the new options" -- a number that
    moves is worth more than a version that might not have been bumped.
    """
    return sum(1 for p in PROFILES for s in p.settings if s.enabled)

HEADER = 148
ACTION_H = 46
LOG_H = 88
GUTTER = 22

#: Both field labels are given the same width in characters so the entry and
#: the picker below it start at the same x.
LABEL_W = 13

#: Shelf entries are label -> path. Preview entries carry this instead of a
#: path, so one picker serves both "the games in your library" and "every game
#: this tool knows", and `_load_install` stays the single way in.
PREVIEW_PREFIX = "preview:"


def settings_path():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "TomClancyPCModStudio")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "settings.json")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("%s %s" % (APP_NAME, VERSION))
        theme.install(self)
        self.configure(bg=theme.P.bg)
        self.geometry("%dx%d" % (theme.px(1160), theme.px(860)))
        self.minsize(theme.px(900), theme.px(660))
        self._set_icon()

        self.detection = None
        self.profile = None
        #: set by --preview so a remembered install does not load over the top
        self.preview_only = False
        #: label -> path for whatever the picker is currently offering
        self._shelf = {}
        self._shelf_dir = ""
        #: Every game folder this tool has ever identified on this machine,
        #: newest first. Kept because a person's games are not all in one
        #: place: a Steam library on one drive, a second library on another,
        #: and the two Advanced Warfighter titles sitting loose at a drive
        #: root because they were never Steam titles. Browsing to one folder
        #: used to replace the picker's contents with whatever was beside it,
        #: so reaching a game on another drive meant browsing again or
        #: sweeping every drive again. These are remembered instead, and the
        #: picker offers all of them however far apart they are.
        self._known = []
        self.vars, self.cards, self.nav_items = {}, {}, {}
        self.active_group = None
        self.busy = False
        self.backdrop_src = None
        self.emblem_src = None
        self._plate = None
        self._header_img = None
        self._title_text = ("Choose a game", "")
        self._msgs = queue.Queue()
        self._pumping = False
        self._recent = []
        self._last_size = (0, 0)
        self._saved_values = {}
        #: None until Discord presence is switched on; see gui/presence.py
        self.presence = None

        self._build()
        self._load_prefs()
        self.protocol("WM_DELETE_WINDOW", self._quit)
        self._start_presence()
        self.after(120, self._pump)

    # -- construction ------------------------------------------------------
    def _set_icon(self):
        base = getattr(sys, "_MEIPASS", os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        for name in ("icon.ico", "icon.png"):
            path = os.path.join(base, "assets", name)
            if not os.path.exists(path):
                continue
            try:
                if name.endswith(".ico"):
                    self.iconbitmap(path)
                else:
                    from PIL import Image, ImageTk
                    self._icon_img = ImageTk.PhotoImage(Image.open(path))
                    self.iconphoto(True, self._icon_img)
                return
            except Exception:                     # noqa: BLE001
                continue

    def _build(self):
        p = theme.P
        self.stage = tk.Canvas(self, bg=p.bg, highlightthickness=0, bd=0)
        self.stage.pack(fill="both", expand=True)
        self.stage.bind("<Configure>", self._on_resize)

        self.header = tk.Label(self.stage, bd=0, bg=p.bg)

        self.disc = Chrome(self.stage, kind="panel", pad=theme.px(9))
        row = tk.Frame(self.disc.body, bg=p.panel)
        row.pack(fill="x")
        self.disc_lbl = tk.Label(row, text="LIBRARY", width=LABEL_W,
                                 anchor="w", bg=p.panel, fg=p.dim,
                                 font=theme.F("body", 9))
        self.disc_lbl.pack(side="left", padx=(theme.px(6), theme.px(12)))
        self.path_var = tk.StringVar()
        # A tk.Entry draws its text hard against its own left edge and has no
        # text inset of its own, so the field is a frame in the entry's colour
        # with the entry inset inside it.
        self.path_well = tk.Frame(row, bg=p.bg)
        self.path_well.pack(side="left", fill="x", expand=True,
                            padx=(0, theme.px(4)))
        self.path_entry = tk.Entry(self.path_well, textvariable=self.path_var,
                                   bg=p.bg, fg=p.text, bd=0,
                                   insertbackground=p.text,
                                   font=theme.F("body", 10), highlightthickness=0)
        self.path_entry.pack(fill="x", expand=True, padx=theme.px(12),
                             pady=theme.px(7))
        self.path_entry.bind("<Return>",
                             lambda _e: self._load_install(self.path_var.get()))
        self.browse_dir = ActionButton(row, "Browse", self._browse_folder)
        self.browse_dir.pack(side="left", padx=(theme.px(10), 0))
        self.find_btn = ActionButton(row, "Find my games", self._autofind)
        self.find_btn.pack(side="left", padx=(theme.px(6), 0))

        # Second line: which game, out of those in that folder. The two fields
        # are the two questions in order, and the top one keeps holding the
        # LIBRARY after a game loads, so the pair reads as a sentence.
        pick = tk.Frame(self.disc.body, bg=p.panel)
        pick.pack(fill="x", pady=(theme.px(9), 0))
        self.shelf_lbl = tk.Label(pick, text="GAME", width=LABEL_W, anchor="w",
                                  bg=p.panel, fg=p.dim, font=theme.F("body", 9))
        self.shelf_lbl.pack(side="left", padx=(theme.px(6), theme.px(12)))
        self.game_var = tk.StringVar()
        self.game_box = dropdown.Dropdown(pick, textvariable=self.game_var,
                                          values=[])
        self.game_box.pack(side="left", fill="x", expand=True,
                           padx=(0, theme.px(4)), pady=theme.px(2))
        self.game_box.bind("<<ComboboxSelected>>", self._pick_game)

        self.status = tk.Label(
            self.stage,
            text="Choose a game folder, or a Steam library full of them.",
            bg=p.bg, fg=p.dim, font=theme.F("body", 9), anchor="w")

        self.group = Chrome(self.stage, kind="group", pad=theme.px(12),
                            autofit=False)
        self.nav = tk.Frame(self.group.body, bg=p.panel, width=theme.px(212))
        self.nav.pack(side="left", fill="y")
        self.nav.pack_propagate(False)
        self.area = ScrollArea(self.group.body)
        self.area.pack(side="left", fill="both", expand=True,
                       padx=(theme.px(12), 0))

        self.bar = tk.Frame(self.stage, bg=p.bg)
        self.preset_lbl = tk.Label(self.bar, text="PRESET", bg=p.bg, fg=p.dim,
                                   font=theme.F("body", 9))
        self.preset_lbl.pack(side="left", padx=(theme.px(4), theme.px(10)))
        self.preset_var = tk.StringVar(value="")
        self.preset_box = dropdown.Dropdown(self.bar, textvariable=self.preset_var,
                                            width=34, values=[])
        self.preset_box.bind("<<ComboboxSelected>>", self._apply_preset)

        self.apply_btn = ActionButton(self.bar, "Apply", self._apply,
                                      accent=True)
        self.dry_btn = ActionButton(self.bar, "Preview changes", self._dry_run)
        self.revert_btn = ActionButton(self.bar, "Restore", self._revert)
        self.discord_btn = ActionButton(self.bar, "Discord", self.discord_setup)
        self.discord_btn.configure(width=self.discord_btn.width_needed())
        for b in (self.apply_btn, self.dry_btn, self.revert_btn):
            b.pack(side="right", padx=(theme.px(10), 0))
            b.set_enabled(False)
        # Packed last of the buttons so it sits at the LEFT of the right-hand
        # group. Never disabled -- it configures the tool rather than touching
        # the game.
        self.discord_btn.pack(side="right", padx=(theme.px(10), 0))

        # The preset box is packed AFTER the buttons, and this is the whole
        # fix for a bug that clipped the Discord button on four of the seven
        # skins. Tk's packer hands out the cavity in call order, so a box
        # packed first with a fixed character width takes its slice before the
        # buttons are measured -- and a character is wider in the letterspaced
        # faces Ghost Recon, both Advanced Warfighters and Sum of All Fears
        # use, so "Discord" lost its D. Packed last it takes only what is
        # left, and `expand` lets it use all of that when there is room.
        self.preset_box.pack(side="left", pady=theme.px(6), fill="x",
                             expand=True)

        self.logwrap = Chrome(self.stage, kind="panel", pad=theme.px(8),
                              autofit=False)
        self.log = tk.Text(self.logwrap.body, height=4, bg=p.panel, fg=p.dim,
                           font=theme.F("mono", 9), bd=0, highlightthickness=0,
                           padx=theme.px(8), pady=theme.px(2), wrap="word",
                           state="disabled")
        self.log.pack(fill="both", expand=True)
        self._log_tags()
        self._say("%s %s (%d options across %d games) -- ready."
                  % (APP_NAME, VERSION, _option_count(), len(PROFILES)))

    def _log_tags(self):
        for tag in ("good", "warn", "bad"):
            self.log.tag_configure(tag, foreground=theme.colour(tag))

    # -- layout ------------------------------------------------------------
    def _on_resize(self, e):
        if (e.width, e.height) == self._last_size:
            return
        self._last_size = (e.width, e.height)
        self._paint_stage(e.width, e.height)
        self._layout(e.width, e.height)

    def _paint_stage(self, w, h):
        self._plate = theme.backdrop(self.backdrop_src, w, h)
        self.stage.delete("plate")
        if self._plate is not None:
            self.stage.create_image(0, 0, image=self._plate, anchor="nw",
                                    tags="plate")
            self.stage.tag_lower("plate")

    def _layout(self, w, h):
        px = theme.px
        x, width = px(GUTTER), w - px(GUTTER) * 2
        head_h = px(HEADER)

        self.header.place(x=0, y=0, width=w, height=head_h)
        self._retitle_image(w, head_h)

        y = head_h + px(10)
        self.disc.place(x=x, y=y, width=width)
        self.update_idletasks()
        y += max(px(52), self.disc.winfo_reqheight()) + px(4)

        # The strip stays flush with the panel above it and only the LETTERING
        # is indented, using the label's own padding. The indent is measured
        # rather than guessed: it depends on the chrome padding, the label's
        # width in whatever face this skin uses, and the entry's own gutter.
        self.status.configure(padx=self._path_indent())
        self.status.place(x=x, y=y, width=width, height=px(20))
        y += px(26)

        bottom = h - px(GUTTER)
        log_top = bottom - px(LOG_H)
        act_top = log_top - px(ACTION_H) - px(8)
        group_h = max(px(140), act_top - y - px(10))
        self.group.place(x=x, y=y, width=width, height=group_h)
        self.group.set_height(group_h)
        self.bar.place(x=x, y=act_top, width=width, height=px(ACTION_H))
        self.logwrap.place(x=x, y=log_top, width=width, height=px(LOG_H))
        self.logwrap.set_height(px(LOG_H))

        for b in (self.browse_dir, self.find_btn, self.apply_btn,
                  self.dry_btn, self.revert_btn, self.discord_btn):
            b.configure(width=b.width_needed())

        self._fit_nav()

    def _fit_nav(self):
        """Size the menu rows to the column they sit in.

        Fixed height until that many rows no longer fit, at which point they
        share the space evenly rather than letting the last page be silently
        clipped off the bottom.
        """
        items = list(self.nav_items.values())
        if not items:
            return
        self.update_idletasks()
        avail = self.nav.winfo_height()
        if avail < theme.px(40):
            return
        n = len(items)
        gap, tall = theme.px(6), theme.px(40)
        if n * tall + (n - 1) * gap > avail:
            gap = max(theme.px(2), gap // 2)
            tall = max(theme.px(20), (avail - gap * (n - 1)) // n)
        for i, item in enumerate(items):
            item.configure(height=tall)
            item.pack_configure(pady=(0, 0 if i == n - 1 else gap))

    def _path_indent(self):
        """How far the path's text sits in from the panel's left edge."""
        try:
            inset = self.path_entry.winfo_rootx() - self.disc.winfo_rootx()
        except tk.TclError:
            return 0
        return inset if 0 < inset < theme.px(400) else 0

    def _retitle(self, title, subtitle):
        self._title_text = (title, subtitle)

    def _retitle_image(self, w, h):
        title, subtitle = self._title_text
        img = skins.title_image(title, theme.P, theme.px, max(w, 10), h,
                                subtitle, self.emblem_src)
        if img is None:
            self.header.configure(text=title, fg=theme.P.title,
                                  font=theme.F("title", 20))
            return
        self._header_img = img
        self.header.configure(image=img, text="", bg=theme.P.bg)

    def _refresh_layout(self):
        w, h = self.stage.winfo_width(), self.stage.winfo_height()
        if w > 4 and h > 4:
            self._paint_stage(w, h)
            self._layout(w, h)

    # -- logging -----------------------------------------------------------
    def _say(self, text, tag=None):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n", tag or ())
        self.log.see("end")
        self.log.configure(state="disabled")

    def _pump(self):
        """Drain the worker queue on the UI thread.

        Every message is handled inside its own guard and the next tick is
        armed in a `finally`. That is not defensiveness for its own sake: the
        loop re-armed itself only on the last line once, so a single raise in
        a completion callback stopped the pump for good. The window stayed up
        at zero CPU with the log frozen mid-job, the buttons latched off and
        no dialog -- indistinguishable from the patcher hanging, when in fact
        the work had finished. A failure here is now a line in the log that
        names the exception, and the window stays usable.

        A message is allowed to open a modal sheet, and sizing a sheet calls
        `update`, which runs pending `after` jobs -- this one among them. So
        without the re-entrancy guard the pump drains a SECOND completion
        while the first one's dialog is still being built, stacking modal
        sheets each blocked in its own `wait_window`. The grab belongs to the
        innermost, the outer ones cannot be dismissed, and the window sits at
        zero CPU behind sheets that may not even be visible yet. Re-entering
        is never useful: the outer drain continues the moment it returns.
        """
        if self._pumping:
            return                      # re-entered from a nested `update`
        self._pumping = True
        try:
            while True:
                try:
                    kind, payload = self._msgs.get_nowait()
                except queue.Empty:
                    break
                try:
                    if kind == "log":
                        self._say(*payload)
                    elif kind == "done":
                        payload()
                except Exception:                     # noqa: BLE001
                    self._recover(kind)
        finally:
            self._pumping = False
            self.after(120, self._pump)

    def report_callback_exception(self, exc, val, tb):
        r"""Put a Tk callback fault in the log, where somebody can see it.

        Tk catches an exception raised inside a callback -- a button command,
        a binding, an `after` job -- and hands it here. The default writes a
        traceback to `sys.stderr` and carries on.

        **This application is built `--windowed`, so it has no stderr.** The
        traceback goes nowhere at all: no console, no file, nothing in this
        window. The button appears not to have worked and the log says
        nothing, which is the least debuggable failure a tool can have, and it
        is invisible in exactly the build that everybody actually runs.

        The queue path was given this treatment already (`_recover`, `_fail`)
        after a fault there hung the window. This is the other half: the same
        report, for the callbacks Tk invokes directly.

        The log is what people send when something goes wrong on their own
        disc, so the whole traceback goes in and not just its last line.
        """
        text = "".join(traceback.format_exception(exc, val, tb))
        try:
            self._say("Something in the interface failed:", "bad")
            for line in text.rstrip().splitlines():
                self._say("  " + line, "bad")
        except Exception:                             # noqa: BLE001
            # The log is part of the window; if the window is what broke,
            # fall back to Tk's own behaviour rather than losing the fault.
            super().report_callback_exception(exc, val, tb)

    def _recover(self, kind):
        """Report a failed queue message and give the window back."""
        detail = traceback.format_exc()
        for line in detail.rstrip().splitlines():
            try:
                self._say(line, "bad")
            except Exception:                         # noqa: BLE001
                break                                 # the log itself is gone
        if kind == "done":
            # The job is over either way; do not leave the buttons latched.
            self.busy = False
            try:
                self._set_buttons(True)
            except Exception:                         # noqa: BLE001
                pass

    def _fail(self, err):
        """Report a job that threw: the message, then where it came from.

        The traceback goes in the log as well as the message, because the one
        line on its own has repeatedly not been enough to say which file or
        which edit gave up -- and the log is what gets sent when something
        goes wrong on somebody else's disc.
        """
        exc, tb = err[0], (err[1] if len(err) > 1 else "")
        self._say(str(exc), "bad")
        for line in str(tb).rstrip().splitlines():
            self._say("  " + line, "bad")

    def _post(self, text, tag=None):
        self._msgs.put(("log", (text, tag)))

    # -- opening a game ----------------------------------------------------
    def _browse_folder(self):
        start = self.path_var.get() or ""
        path = filedialog.askdirectory(
            title="Choose a game folder, or the library that holds them",
            initialdir=start or None, mustexist=True)
        if path:
            self._load_install(path)

    def _autofind(self):
        """Sweep every Steam library on the machine for supported games.

        Worth doing rather than making the user browse. Five of the seven are
        spread across whatever drives Steam was pointed at, and the two
        Advanced Warfighter games are not Steam titles at all -- they sit
        directly on a drive root -- so the sweep covers both.
        """
        found, seen = [], set()
        for lib in art.search_roots():
            for det in engine_scan(lib):
                key = os.path.normcase(det.path)
                if key not in seen:
                    seen.add(key)
                    found.append(det)
        if not found:
            self._say("No supported games found in any Steam library.", "warn")
            dialog.info(self, APP_NAME,
                                "None of the seven supported games turned up "
                                "in a Steam library or at the top of a drive. "
                                "Use Browse to point at one.")
            return
        for det in found:
            self._remember_game(det.path)
        self._offer_known()
        self._say("Found %d game%s." % (len(found), "" if len(found) == 1 else "s"),
                  "good")
        first = list(self._shelf)[0]
        self.game_var.set(first)
        self._load_install(self._shelf[first])

    def _remember_game(self, path):
        """Keep a game folder in the picker's memory, newest first."""
        key = os.path.normcase(os.path.abspath(str(path)))
        self._known = [p for p in self._known
                       if os.path.normcase(os.path.abspath(p)) != key]
        self._known.insert(0, str(path))
        self._known = self._known[:40]

    def _offer_known(self, current=None):
        """Put every remembered game into the picker, wherever it lives.

        Folders that have gone are dropped rather than offered and then
        failing: an external drive that is not plugged in this time should
        quietly not be listed.

        This deliberately identifies each folder rather than scanning its
        parent. Scanning is what makes the difference between one library and
        four visible, and it is also what makes a sweep slow -- `identify`
        opens one folder, `look` opens every folder beside it.
        """
        alive, found = [], []
        for path in self._known:
            if not os.path.isdir(path):
                continue
            det = identify(path)
            if det.ok:
                alive.append(path)
                found.append(det)
        self._known = alive
        if not found:
            return False
        self._fill_shelf("", found, current=current)
        return True

    def _shelf_label(self, det, keep=2, drive=False):
        """What one entry in the picker reads as -- the game, then where it is,
        because a machine can hold the same game twice and this one does."""
        where = _short_path(det.path, keep)
        if drive:
            head = os.path.splitdrive(os.path.abspath(det.path))[0]
            if head:
                where = "%s  %s" % (head, where)
        return "%s   ·   %s" % (det.profile.short, where)

    def _fill_shelf(self, folder, found, current=None):
        self._shelf_dir = folder
        self._shelf = {}
        dets = sorted(found, key=lambda d: (d.profile.short, d.path))
        # The shortest tail that still tells every row apart. Two components
        # is enough almost always -- `common\Ghost Recon` -- but a person with
        # two Steam libraries on two drives has the same game at the same tail
        # on both, and a picker with two identical rows is worse than a long
        # one. So the whole picker lengthens together, which keeps the rows
        # reading alike, and only as far as it has to.
        # Two components is enough almost always -- `common\Ghost Recon`.
        # When it is not, the reason is nearly always that the same game sits
        # at the same tail in two Steam libraries on two different drives, and
        # the compact way to say that is the drive letter, not four more path
        # components. Only if the drive still does not separate them does the
        # tail grow.
        keep, drive = 2, False
        for keep, drive in ((2, False), (2, True), (3, True), (4, True),
                            (5, True)):
            labels = [self._shelf_label(d, keep, drive) for d in dets]
            if len(set(labels)) == len(labels):
                break
        for det in dets:
            self._shelf[self._shelf_label(det, keep, drive)] = det.path
        names = list(self._shelf)
        widest = max((len(n) for n in names), default=30)
        self.game_box.configure(values=names, width=min(74, widest + 2))
        self.game_var.set("")
        if current:
            self._select_in_shelf(current)

    def _select_in_shelf(self, path) -> bool:
        """Point the picker at `path`. False when it is not on offer."""
        for label, known in self._shelf.items():
            if os.path.normcase(known) == os.path.normcase(path):
                self.game_var.set(label)
                return True
        return False

    def _pick_game(self, _event=None):
        path = self._shelf.get(self.game_var.get())
        if path:
            self._load_install(path)

    # -- preview (no install) ----------------------------------------------
    def _enter_preview(self):
        """Fill the picker with every game this tool knows and open the first.

        For looking at what the options ARE without owning the game, which is
        the only way to answer "what does this do" before buying into it.
        """
        self._shelf_dir = ""
        self._shelf = {}
        for p in sorted(PROFILES, key=lambda q: q.short):
            self._shelf["%s   ·   preview" % p.short] = PREVIEW_PREFIX + p.id
        names = list(self._shelf)
        self.game_box.configure(values=names,
                                width=min(74, max(len(n) for n in names) + 2))
        self.path_var.set("")
        self.game_var.set(names[0])
        self._say("Preview: no game loaded, nothing can be written.", "warn")
        self._load_install(self._shelf[names[0]])

    def _load_preview(self, profile_id):
        det = preview_detection(profile_id)
        self.detection, self.profile = det, det.profile
        theme.use(skins.for_profile(det.profile))
        # Every art call takes the (empty) install path, so each one fails its
        # own open and returns nothing. A page cached from the user's own copy
        # is still honoured, which is why preview looks right on the machine
        # that owns the game and stays bare everywhere else.
        skins.set_textures(art.chrome_images(det, theme.cache_dir()))
        self.backdrop_src = art.banner_image(det, theme.cache_dir())
        self.emblem_src = art.emblem_image(det, theme.cache_dir())
        self._restyle()
        self.status.configure(text="preview — no installation loaded",
                              fg=theme.P.warn)
        self._build_settings()
        self._set_buttons(False)

    def _load_install(self, path):
        path = path.strip().strip('"')
        if not path:
            return
        if path.startswith(PREVIEW_PREFIX):
            return self._load_preview(path[len(PREVIEW_PREFIX):])
        self._say("Reading %s" % (os.path.basename(path.rstrip("\\/")) or path))

        # Re-reading a library opens every folder in it and can only find what
        # it just found, so a game chosen out of the picker skips to that one.
        parent = os.path.dirname(path.rstrip("\\/"))
        cached = (self._shelf_dir
                  and os.path.normcase(parent) == os.path.normcase(self._shelf_dir))
        if cached:
            det, shelf = identify(path), []
        else:
            det, shelf = look(path)

        folder = os.path.dirname(det.path) if det.ok else path
        self.path_var.set(folder)
        if shelf:
            # Browsing to a library used to REPLACE the picker with whatever
            # was in that one folder, which is what made a second drive feel
            # like a different session. Everything found is remembered and the
            # picker then offers all of it at once.
            for other in shelf:
                self._remember_game(other.path)
            if det.ok:
                self._remember_game(det.path)
            if not self._offer_known(current=det.path if det.ok else None):
                self._fill_shelf(folder, shelf,
                                 current=det.path if det.ok else None)
        elif det.ok:
            self._remember_game(det.path)
            if not self._select_in_shelf(det.path):
                self._offer_known(current=det.path)
        self.detection = det

        if not det.ok:
            self.profile = None
            # A library of games is not a failure, it is a question.
            tone = theme.P.warn if self._shelf else theme.P.bad
            self.status.configure(text=det.message, fg=tone)
            self._say(det.message, "warn" if self._shelf else "bad")
            self.area.clear()
            self._set_buttons(False)
            return

        self.profile = det.profile
        theme.use(skins.for_profile(det.profile))
        skins.set_textures(art.chrome_images(det, theme.cache_dir()))
        self.backdrop_src = art.banner_image(det, theme.cache_dir())
        self.emblem_src = art.emblem_image(det, theme.cache_dir())
        self._restyle()

        self.status.configure(text=self._status_line(det), fg=theme.P.good)
        self._say("Recognised %s" % det.title, "good")
        if det.message:
            self._say(det.message, "warn")

        self._build_settings()
        self._remember(det.path)

    def _status_line(self, det):
        bits = [det.path, {MOD: "builds a mod folder",
                           OVERLAY: "writes loose files over the bundles"}
                .get(det.profile.delivery, "edits files in place")]
        if det.has_backup:
            bits.append("backup taken")
        return "   •   ".join(bits)

    def _restyle(self):
        """Re-colour the fixed furniture after a skin change."""
        p = theme.P
        self.configure(bg=p.bg)
        self.stage.configure(bg=p.bg)
        for wdg in (self.header, self.status, self.bar):
            wdg.configure(bg=p.bg)
        self.preset_lbl.configure(bg=p.bg, fg=p.dim)
        self.nav.configure(bg=p.panel)
        self.area.restyle()
        self.disc.restyle()
        self.group.restyle()
        self.logwrap.restyle()
        for wdg in self.disc.body.winfo_children():
            wdg.configure(bg=p.panel)
        self.disc_lbl.configure(bg=p.panel, fg=p.dim)
        self.shelf_lbl.configure(bg=p.panel, fg=p.dim)
        self.shelf_lbl.master.configure(bg=p.panel)
        self.path_well.configure(bg=p.bg)
        self.path_entry.configure(bg=p.bg, fg=p.text, insertbackground=p.text)
        self.log.configure(bg=p.panel, fg=p.dim)
        self._log_tags()
        self._refresh_layout()

    def _set_buttons(self, on):
        # Authoritative rather than advisory: _build_settings ends by calling
        # this with True, so preview has to be vetoed HERE or loading a preview
        # profile would re-enable the write buttons behind it.
        if getattr(self.detection, "preview", False):
            on = False
        has = bool(self.profile and self.profile.settings)
        self.apply_btn.set_enabled(on and has)
        self.dry_btn.set_enabled(on and has)
        self.revert_btn.set_enabled(
            on and bool(self.detection and self.detection.has_backup))

    # -- settings ----------------------------------------------------------
    def _build_settings(self):
        p = self.profile
        self.vars, self.cards = {}, {}
        for s in p.settings:
            if s.kind == BOOL:
                v = tk.BooleanVar(value=s.default)
            elif s.kind == INT:
                v = tk.IntVar(value=s.default)
            else:
                v = tk.StringVar(value=s.default)
            self.vars[s.key] = v

        saved = self._saved_values.get(p.id, {})
        if saved:
            for key, value in p.normalise(saved).items():
                if key in self.vars:
                    try:
                        self.vars[key].set(value)
                    except tk.TclError:
                        pass

        names = list(p.groups())
        if p.notes:
            names.append(NOTES_TAB)
        if not names:
            names = [NOTES_TAB]
        names_p = [n for n, _ in PRESETS.get(p.id, [])]
        widest = max((len(n) for n in names_p), default=24)
        self.preset_box.configure(values=names_p, width=min(60, widest + 2))
        self.preset_var.set(PRESET_HINT if names_p else "")

        for child in self.nav.winfo_children():
            child.destroy()
        self.nav_items = {}
        gap = nav_font = None
        if theme.P.chrome in ("graw", "lock"):
            nav_font, gap = nav_style([n.upper() for n in names],
                                      theme.px(212) - theme.px(48))
        for name in names:
            item = NavItem(self.nav, name, lambda n=name: self._show_group(n),
                           gap=gap, font=nav_font)
            item.pack(fill="x", pady=(0, theme.px(6)))
            self.nav_items[name] = item

        self._fit_nav()
        self._show_group(names[0] if names else None)
        self._set_buttons(True)

    def _show_group(self, name):
        self.active_group = name
        self._publish()
        for n, item in self.nav_items.items():
            item.select(n == name)
        where = (_short_path(self.detection.path)
                 or ("preview — nothing loaded"
                     if getattr(self.detection, "preview", False) else ""))
        self._retitle(name or self.profile.short,
                      "%s  ·  %s" % (self.profile.title, where)
                      if where else self.profile.title)
        self._retitle_image(max(self.stage.winfo_width(), 10), theme.px(HEADER))
        self.area.clear()
        body = self.area.body
        # Cleared HERE, before the notes branch, not inside the settings one.
        # `area.clear()` has just destroyed every widget on the previous page,
        # and anything still listed in `self.cards` is now a dead Tk name that
        # raises the moment something touches it. The notes page used to leave
        # the previous page's list in place, so choosing a preset while it was
        # open crashed on the first destroyed toggle.
        self.cards = {}

        if name == NOTES_TAB:
            if self.profile.notes:
                card = Chrome(body, kind="panel", pad=theme.px(16))
                card.pack(fill="x", padx=theme.px(4), pady=theme.px(6))
                tk.Label(card.body, text=self.profile.notes, bg=theme.P.panel,
                         fg=theme.P.dim, font=theme.F("body", 9),
                         wraplength=theme.px(640), justify="left",
                         anchor="w").pack(fill="x")
            self._install_facts(body)
            return

        for s in self.profile.settings:
            if s.group != name:
                continue
            card = SettingCard(body, s, self.vars[s.key], self._changed,
                               images=self._mission_art(s))
            card.pack(fill="x", padx=theme.px(4), pady=theme.px(6))
            self.cards[s.key] = card
        if not self.cards:
            tk.Label(body, text="Nothing to configure here yet.", bg=theme.P.bg,
                     fg=theme.P.faint, font=theme.F("body", 9)
                     ).pack(padx=theme.px(18), pady=theme.px(18), anchor="w")
        self._changed()

    def _install_facts(self, body):
        det = self.detection
        card = Chrome(body, kind="panel", pad=theme.px(16))
        card.pack(fill="x", padx=theme.px(4), pady=theme.px(6))
        prof = det.profile
        if getattr(det, "preview", False):
            # Nothing was read, so every fact that comes OFF an install would
            # be a guess. Only what the profile itself knows is shown.
            rows = [("Folder", "— preview, nothing loaded"),
                    ("Delivery", _delivery_words(prof)),
                    ("Executable", prof.layout.exe),
                    ("Backup", "—")]
        else:
            rows = [("Folder", det.path),
                    ("Executable", "%s  (%s)" % (prof.layout.exe,
                                                 det.exe_version or "not found")),
                    ("Delivery", _delivery_words(prof))]
            if prof.delivery == MOD:
                rows.append(("Mod folder",
                             os.path.join(prof.layout.mods_dir, prof.mod_name)))
                rows.append(("Built", "yes" if os.path.isdir(
                    engine.mod_dir(det.path, prof)) else "not yet"))
            else:
                man = engine.read_manifest(det.path)
                kept = len(man.get("files", [])) + len(man.get("created", []))
                if prof.delivery == OVERLAY:
                    rows.append(("Bundles", prof.layout.bundles_dir
                                 + "  (read only, never written)"))
                    rows.append(("Written to", prof.layout.overlay_dir))
                rows.append(("Tracked", "%d file(s)" % kept if kept
                             else "nothing written yet"))
        for k, v in rows:
            r = tk.Frame(card.body, bg=theme.P.panel)
            r.pack(fill="x", pady=theme.px(2))
            tk.Label(r, text=k, bg=theme.P.panel, fg=theme.P.dim, width=14,
                     anchor="w", font=theme.F("body", 8)).pack(side="left")
            tk.Label(r, text=str(v), bg=theme.P.panel, fg=theme.P.text,
                     anchor="w", font=theme.F("mono", 9)).pack(side="left")

    def _mission_art(self, setting):
        """The game's own art for a mission card, or nothing."""
        spec = getattr(self.profile, "mission_art_for", None)
        if spec is None or self.detection is None:
            return ()
        out = []
        for name in spec(setting.key):
            img = art.mission_art(self.detection, name, theme.cache_dir())
            if img is not None:
                out.append(img)
        return out

    def _values(self):
        return {k: v.get() for k, v in self.vars.items()}

    def _changed(self):
        if not self.profile:
            return
        self._publish()
        vals = self._values()
        for key, card in self.cards.items():
            s = self.profile.setting(key)
            missing = self.profile.unmet(key, vals)
            if not s.enabled:
                card.set_enabled(False)
            elif missing:
                card.set_enabled(False, "needs " + " and ".join(missing))
            else:
                card.set_enabled(True)
        self._save_prefs()

    def _apply_preset(self, _e=None):
        name = self.preset_var.get()
        if name == PRESET_HINT:
            return
        for pname, values in PRESETS.get(self.profile.id, []):
            if pname == name:
                for k, v in values.items():
                    if k in self.vars:
                        self.vars[k].set(v)
                for card in self.cards.values():
                    card.sync()
                self._say("Preset: %s" % name)
                self._changed()
                return

    # -- Discord -----------------------------------------------------------
    def _start_presence(self):
        """Bring the presence up if it is switched on. Failure is silent.

        Discord not being installed is the common case, not a fault, and a
        modal about it on every launch would be worse than the feature is good.
        """
        prefs = presence.load()
        if not prefs["enabled"] or not prefs["app_id"]:
            return
        try:
            self.presence = presence.Presence(prefs["app_id"])
            self.presence.start()
            self._publish()
        except Exception:                         # noqa: BLE001
            self.presence = None

    def discord_setup(self):
        chosen = discorddialog.configure(self, self.presence)
        if chosen is None:
            return
        enabled, app_id = chosen
        # Restart rather than mutate: the application id is fixed at handshake.
        if self.presence is not None:
            self.presence.close()
            self.presence = None
        if enabled and app_id:
            self.presence = presence.Presence(app_id)
            self.presence.start()
            self._publish()
            self._say("Discord presence on. It connects when Discord is running.")
        else:
            self._say("Discord presence off.")

    def _publish(self):
        """Say what is on screen, in the two lines Discord gives us."""
        if self.presence is None:
            return
        if self.profile is None:
            self.presence.update(details="No game loaded", state="Idle",
                                 image="idle", image_text=APP_NAME)
            return
        # Counts controls moved off stock rather than edits built. This runs on
        # every widget change, a slider drag included, so it stays cheap.
        defaults = dict(self.profile.defaults())
        changed = sum(1 for k, v in self._values().items()
                      if k in defaults and v != defaults[k])
        state = self.active_group or "Browsing"
        if changed:
            state += "  -  %d change%s" % (changed, "" if changed == 1 else "s")
        self.presence.update(details="Modding " + self.profile.title,
                             state=state, image=self.profile.id,
                             image_text=self.profile.title)

    def _quit(self):
        if self.presence is not None:
            self.presence.close()
        self.destroy()

    # -- actions -----------------------------------------------------------
    def _guard(self):
        if self.busy:
            return False
        if not (self.detection and self.detection.ok):
            dialog.info(self, APP_NAME, "Load a supported game folder first.")
            return False
        return True

    def _run(self, fn, done):
        self.busy = True
        for b in (self.apply_btn, self.dry_btn, self.revert_btn):
            b.set_enabled(False)

        def worker():
            # `posted` rather than try/except alone: the window is left
            # waiting on this one message, so the ONE thing that must never
            # happen is the thread ending without it. `except Exception`
            # misses MemoryError's rarer siblings and misses a failure in the
            # put itself, and either one strands the buttons off with no
            # dialog and nothing in the log to say why.
            posted = False
            try:
                result = fn()
                self._msgs.put(("done", lambda: done(result, None)))
                posted = True
            except Exception as exc:              # noqa: BLE001
                # Bound as defaults, NOT captured. Python deletes the name
                # `exc` when the except block exits, and this lambda runs
                # later on the UI thread -- so capturing it by closure raised
                # NameError instead of reporting the real failure, which then
                # killed the pump and hung the window. Every apply that threw
                # anything at all went that way, and the actual error was
                # never seen by anybody.
                self._msgs.put(("done", lambda e=exc, t=traceback.format_exc():
                                done(None, (e, t))))
                posted = True
            finally:
                if not posted:
                    tb = traceback.format_exc()
                    err = RuntimeError("the job stopped before it finished, "
                                       "and the disc may be half-written -- "
                                       "use Put back to restore it")
                    self._msgs.put(("done", lambda: done(None, (err, tb))))
        threading.Thread(target=worker, daemon=True).start()

    def _dry_run(self):
        """Work out every change without writing a byte, and list them.

        Worth its own button on PC in a way it was not on PS2. There, an option
        was a handful of words at addresses nobody reads; here one slider can
        rewrite four hundred files, and being able to see exactly which value
        in which file is about to move -- before anything moves -- is the
        difference between a tool you trust and one you back up first.
        """
        if not self._guard():
            return
        path, profile, vals = self.detection.path, self.profile, self._values()

        def done(result, err):
            self.busy = False
            self._set_buttons(True)
            if err:
                self._fail(err)
                dialog.error(self, APP_NAME, str(err[0]))
                return
            real = [c for c in result.changes if c.status == "changed"]
            self._say("Preview: %d value(s) across %d file(s). Nothing written."
                      % (len(real), result.files), "good")
            for line in result.log()[:200]:
                self._say(line)
            if len(result.log()) > 200:
                self._say("  … and %d more." % (len(result.log()) - 200))
            for w in result.warnings:
                self._say("  ! " + w, "warn")

        self._run(lambda: engine.apply(path, profile, vals, dry_run=True), done)

    def _apply(self):
        if not self._guard():
            return
        path, profile, vals = self.detection.path, self.profile, self._values()
        try:
            preview = engine.apply(path, profile, vals, dry_run=True)
        except Exception as exc:                  # noqa: BLE001
            dialog.error(self, APP_NAME, str(exc))
            self._say(str(exc), "bad")
            return

        real = [c for c in preview.changes if c.status == "changed"]
        lines = []
        if profile.delivery == MOD:
            lines.append("Build the mod folder %s from %d file(s), changing %d "
                         "value(s)."
                         % (os.path.join(profile.layout.mods_dir, profile.mod_name),
                            preview.files, len(real)))
            lines.append("Nothing in the game's own files is touched. Turn the "
                         "mod on in the game's Mods menu to use it, and off to "
                         "undo it completely.")
        elif profile.delivery == OVERLAY:
            lines.append("Write %d loose file(s) into %s, changing %d value(s)."
                         % (preview.files, profile.layout.overlay_dir,
                            len(real)))
            lines.append("They shadow the game's .bundle archives, which are "
                         "read but never written. Restore removes exactly the "
                         "files this tool added and puts back any it wrote "
                         "over -- it never deletes the folder.")
        else:
            lines.append("Rewrite %d file(s) in the installation, changing %d "
                         "value(s)." % (preview.files, len(real)))
            lines.append("An untouched copy of every file is kept in "
                         ".tcpc-backup, and Restore puts them all back.")
        if not real and not preview.files:
            lines = ["Nothing is selected, so the game goes back to stock."]
        if preview.warnings:
            lines.append("")
            lines += ["• " + w for w in preview.warnings[:12]]
            if len(preview.warnings) > 12:
                lines.append("• …and %d more." % (len(preview.warnings) - 12))
        lines += ["", "Close the game first."]
        if not dialog.ask(self, APP_NAME, "\n".join(lines)):
            return

        self._say("Applying…")

        def done(result, err):
            self.busy = False
            if err:
                self._fail(err)
                dialog.error(self, APP_NAME, str(err[0]))
            else:
                done_real = [c for c in result.changes if c.status == "changed"]
                self._say("Done: %d value(s) written across %d file(s), all "
                          "read back from disk."
                          % (len(done_real), len(result.verified)),
                          "good" if result.ok else "bad")
                for w in result.warnings[:20]:
                    self._say("  ! " + w, "warn")
                if not result.ok:
                    dialog.error(self, 
                        APP_NAME, "Some files could not be written. The log "
                                  "says which.")
            self.detection = identify(path)
            self._set_buttons(True)

        self._run(lambda: engine.apply(
            path, profile, vals,
            progress=lambda i, n, rel: (i % 25 == 0)
            and self._post("  %d/%d  %s" % (i + 1, n, rel))), done)

    def _revert(self):
        if not self._guard():
            return
        profile, path = self.profile, self.detection.path
        if profile.delivery == MOD:
            what = ("Delete the generated mod folder %s?"
                    % os.path.join(profile.layout.mods_dir, profile.mod_name))
        elif profile.delivery == OVERLAY:
            what = ("Remove every loose file this tool wrote into %s, and put "
                    "back any it wrote over?" % profile.layout.overlay_dir)
        else:
            what = "Put every file this tool changed back exactly as it was?"
        if not dialog.ask(self, APP_NAME, what + "\n\nClose the game first."):
            return

        def done(result, err):
            self.busy = False
            if err:
                self._fail(err)
                dialog.error(self, APP_NAME, str(err[0]))
            else:
                self._say("Restored %d file(s)." % result.files,
                          "good" if result.ok else "bad")
                for w in result.warnings:
                    self._say("  ! " + w, "warn")
            self.detection = identify(path)
            self._set_buttons(True)

        self._run(lambda: engine.revert(path, profile), done)

    # -- preferences -------------------------------------------------------
    def _remember(self, path):
        self._recent = [path] + [p for p in self._recent if p != path]
        self._recent = self._recent[:8]
        self._remember_game(path)
        self._save_prefs()

    def _save_prefs(self):
        data = {"recent": self._recent, "games": self._known, "profiles": {}}
        try:
            with open(settings_path(), encoding="utf-8") as fh:
                data["profiles"] = json.load(fh).get("profiles", {})
        except Exception:                         # noqa: BLE001
            pass
        if self.profile:
            data["profiles"][self.profile.id] = self._values()
        try:
            with open(settings_path(), "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=1)
        except OSError:
            pass

    def _load_prefs(self):
        try:
            with open(settings_path(), encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:                         # noqa: BLE001
            return
        self._recent = data.get("recent", [])
        self._known = [p for p in data.get("games", []) if isinstance(p, str)]
        self._saved_values = data.get("profiles", {})
        self._offer_known()
        for p in self._recent:
            if os.path.isdir(p):
                self.after(250, lambda q=p: (self.detection is None
                                             and not self.preview_only
                                             and self._load_install(q)))
                break


def engine_scan(folder):
    from tcpc.install import scan_folder
    return scan_folder(folder)


def _short_path(path, keep=2):
    """The tail of a path, which is what tells two installs apart.

    A full Steam path is mostly the same forty characters on every entry, and a
    picker where every row starts identically is a picker you have to read to
    the end of.
    """
    if not path:
        return ""
    parts = [p for p in str(path).replace("/", "\\").split("\\") if p]
    return "\\".join(parts[-keep:]) if len(parts) > keep else str(path)


def _delivery_words(profile):
    if profile.delivery == MOD:
        return "generates a mod folder (retail files untouched)"
    if profile.delivery == OVERLAY:
        return "writes loose files that shadow the bundles (bundles untouched)"
    return "edits files in place (pristine copies kept)"


def baked_preview() -> bool:
    """Was this executable built as a preview build?"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    return os.path.exists(os.path.join(base, "assets", "preview.mode"))


def main(argv=None):
    theme.set_dpi_aware()
    argv = list(sys.argv[1:] if argv is None else argv)
    app = App()
    if "--preview" in argv or "-p" in argv or baked_preview():
        # Set before the 250 ms recent-install timer fires, so a machine that
        # has opened a game before still lands in preview when asked for it.
        app.preview_only = True
        app.after(150, app._enter_preview)
    else:
        for arg in argv:
            if os.path.isdir(arg):
                app.after(150, lambda q=arg: app._load_install(q))
                break
    app.mainloop()


if __name__ == "__main__":
    main()

"""Tom Clancy PS2 Mod Studio -- the window.

The whole window sits on one canvas holding the loaded game's own artwork, and
every part of the interface is placed onto it, so the backdrop shows in the gaps
the way it does in the games' own menus. Which skin is in force follows the
disc: gunmetal for Rainbow Six 3, gold-on-navy for Ghost Recon, gold-on-teal for
Jungle Storm.
"""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
import tkinter as tk
import traceback
from tkinter import filedialog, ttk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tcps2 import art, engine  # noqa: E402
from tcps2.detect import identify, look, preview_detection  # noqa: E402
from tcps2.games import PROFILES  # noqa: E402
from tcps2.model import BOOL, INT  # noqa: E402

from . import dialog, discorddialog, presence, skins, theme  # noqa: E402
from .presets import PRESETS  # noqa: E402
from .widgets import (ActionButton, Chrome, NavItem, ProgressBar,
                      ScrollArea, SettingCard, nav_style)  # noqa: E402

APP_NAME = "Tom Clancy PS2 Mod Studio"
PRESET_HINT = "Choose a preset…"
VERSION = "5.8"
NOTES_TAB = "About this disc"

# A square mark -- Jungle Storm's reticle ring, Lockdown's stacked logo -- is
# limited by the header's HEIGHT, not its width, so the wide wordmarks were
# filling their box while the square ones sat well under it. A taller band
# costs the wide marks nothing and gives the square ones room.
HEADER = 148
ACTION_H = 46
LOG_H = 99
GUTTER = 22

#: Both field labels are given the same width in characters so the entry and
#: the picker below it start at the same x. Left to size themselves, "DISC" and
#: "GAMES FOLDER" put the two fields a centimetre apart.
LABEL_W = 13

#: Shelf entries are label -> path. Preview entries carry this instead of a
#: path, so one picker serves both "the discs in your folder" and "every game
#: this tool knows", and `_load_iso` stays the single way in.
PREVIEW_PREFIX = "preview:"


def settings_path():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "TomClancyPS2ModStudio")
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
        #: set by --preview so the remembered disc does not load over the top
        self.preview_only = False
        #: label -> path for whatever the picker is currently offering
        self._shelf = {}
        self._shelf_dir = ""
        self.vars, self.cards, self.nav_items = {}, {}, {}
        self.active_group = None
        self.busy = False
        self.backdrop_src = None
        self.emblem_src = None
        self._plate = None
        self._header_img = None
        self._title_text = ("Choose a disc", "")
        self._msgs = queue.Queue()
        self._pumping = False
        self._recent = []
        self._last_size = (0, 0)
        #: None until Discord presence is switched on; see gui/presence.py
        self.presence = None
        #: A folder of loose archives the game reads instead of the disc's,
        #: or None for the ordinary in-place mode. Remembered per disc: the
        #: two can hold different edits at once and must not be confused.
        self.data_root = None

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
        self.disc_lbl = tk.Label(row, text="GAMES FOLDER", width=LABEL_W,
                                 anchor="w", bg=p.panel, fg=p.dim,
                                 font=theme.F("body", 9))
        self.disc_lbl.pack(side="left", padx=(theme.px(6), theme.px(12)))
        self.path_var = tk.StringVar()
        # A tk.Entry draws its text hard against its own left edge and has no
        # text inset of its own -- `ipadx` grows the widget but the text stays
        # put. So the field is a frame in the entry's colour with the entry
        # inset inside it, which is the only way to get a gutter before the path.
        self.path_well = tk.Frame(row, bg=p.bg)
        self.path_well.pack(side="left", fill="x", expand=True,
                            padx=(0, theme.px(4)))
        self.path_entry = tk.Entry(self.path_well, textvariable=self.path_var,
                                   bg=p.bg, fg=p.text, bd=0,
                                   insertbackground=p.text,
                                   font=theme.F("body", 10), highlightthickness=0)
        self.path_entry.pack(fill="x", expand=True, padx=theme.px(12),
                             pady=theme.px(7))
        self.path_entry.bind("<Return>", lambda _e: self._load_iso(self.path_var.get()))
        self.browse = ActionButton(row, "Disc image", self._browse)
        self.browse.pack(side="left", padx=(theme.px(10), 0))
        self.browse_dir = ActionButton(row, "Folder", self._browse_folder)
        self.browse_dir.pack(side="left", padx=(theme.px(6), 0))

        # Second line: which game, out of the discs in that folder. The two
        # fields are the two questions in order -- where are your discs, and
        # which one -- and the top one keeps holding the FOLDER after a disc
        # loads, so the pair reads as a sentence instead of the top field
        # jumping to a file path the moment you choose something.
        pick = tk.Frame(self.disc.body, bg=p.panel)
        pick.pack(fill="x", pady=(theme.px(9), 0))
        self.shelf_lbl = tk.Label(pick, text="GAME", width=LABEL_W, anchor="w",
                                  bg=p.panel, fg=p.dim, font=theme.F("body", 9))
        self.shelf_lbl.pack(side="left", padx=(theme.px(6), theme.px(12)))
        self.game_var = tk.StringVar()
        self.game_box = ttk.Combobox(pick, textvariable=self.game_var,
                                     state="readonly", values=[])
        self.game_box.pack(side="left", fill="x", expand=True,
                           padx=(0, theme.px(4)), pady=theme.px(2))
        self.game_box.bind("<<ComboboxSelected>>", self._pick_game)

        # Opening line rather than a blank bar: without a disc the window
        # has nothing to say for itself.
        self.status = tk.Label(
            self.stage,
            text="Choose a disc image, or a folder of them.",
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
        self.preset_box = ttk.Combobox(self.bar, textvariable=self.preset_var,
                                       width=34, state="readonly", values=[])
        self.preset_box.pack(side="left", pady=theme.px(6))
        self.preset_box.bind("<<ComboboxSelected>>", self._apply_preset)

        self.apply_btn = ActionButton(self.bar, "Apply to disc", self._apply,
                                      accent=True)
        self.cheat_btn = ActionButton(self.bar, "Cheat file", self._save_pnach)
        self.root_btn = ActionButton(self.bar, "Data root", self._data_root)
        self.revert_btn = ActionButton(self.bar, "Restore disc", self._revert)
        self.discord_btn = ActionButton(self.bar, "Discord", self.discord_setup)
        self.discord_btn.configure(width=self.discord_btn.width_needed())
        for b in (self.apply_btn, self.cheat_btn, self.root_btn,
                  self.revert_btn):
            b.pack(side="right", padx=(theme.px(10), 0))
            b.set_enabled(False)
        # Packed last so it sits at the LEFT of the right-hand group: "Apply to
        # disc" is the primary action and belongs at the end of the row, not
        # with a settings button beyond it. Never disabled -- it configures the
        # tool rather than touching the disc, so it works with nothing loaded.
        self.discord_btn.pack(side="right", padx=(theme.px(10), 0))

        self.logwrap = Chrome(self.stage, kind="panel", pad=theme.px(8),
                              autofit=False)
        self.log = tk.Text(self.logwrap.body, height=4, bg=p.panel, fg=p.dim,
                           font=theme.F("mono", 9), bd=0, highlightthickness=0,
                           padx=theme.px(8), pady=theme.px(2), wrap="word",
                           state="disabled")
        self.progress = ProgressBar(self.logwrap.body)
        self.progress.pack(fill="x", side="top", pady=(0, theme.px(4)))
        self.log.pack(fill="both", expand=True)
        self._log_tags()
        self._say("%s %s -- ready." % (APP_NAME, VERSION))

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

        # The strip stays flush with the panel above it -- moving the whole
        # label left a gap where the backdrop showed through -- and only the
        # LETTERING is indented, using the label's own padding. The indent is
        # measured rather than guessed: it depends on the chrome padding, the
        # DISC label's width in whatever face this skin uses, and the entry's
        # own gutter, three things that move per skin and per DPI.
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

        for b in (self.browse, self.browse_dir, self.apply_btn,
                  self.cheat_btn, self.root_btn, self.revert_btn,
                  self.discord_btn):
            b.configure(width=b.width_needed())

        self._fit_nav()

    def _fit_nav(self):
        """Size the menu rows to the column they sit in.

        The rows are a fixed height until that many of them no longer fit, at
        which point the last page is silently clipped off the bottom -- which is
        what happened to Rainbow Six 3 the moment it grew a ninth page, and what
        happens to any profile on a short enough window. When they do not fit
        they share the space evenly instead, so the column stays deliberate
        rather than cut in half.
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
        """How far the disc path's text sits in from the panel's left edge."""
        try:
            inset = (self.path_entry.winfo_rootx()
                     - self.disc.winfo_rootx())
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
        at zero CPU with the log frozen mid-file, the buttons latched off and
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
                    elif kind == "progress":
                        self.progress.set(*payload)
                    elif kind == "done":
                        # One place, so every job clears the bar -- apply,
                        # revert, export -- rather than each remembering to.
                        self.progress.clear()
                        payload()
                except Exception:                     # noqa: BLE001
                    self._recover(kind)
        finally:
            self._pumping = False
            self.after(120, self._pump)

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
            for step in (lambda: self.progress.clear(),
                         lambda: self._set_buttons(True)):
                try:
                    step()
                except Exception:                     # noqa: BLE001
                    pass

    def _post(self, text, tag=None):
        self._msgs.put(("log", (text, tag)))

    def _tick(self, done, total):
        """Progress from a worker thread. Queued, never drawn from here."""
        self._msgs.put(("progress", (done, total)))

    # -- disc --------------------------------------------------------------
    def _browse(self):
        start = self.path_var.get() or ""
        path = filedialog.askopenfilename(
            title="Choose a PS2 disc image", initialdir=start or None,
            filetypes=[("PS2 disc images", "*.iso *.bin"), ("All files", "*.*")])
        if path:
            self._load_iso(path)

    def _browse_folder(self):
        start = self.path_var.get() or ""
        path = filedialog.askdirectory(
            title="Choose the folder your PS2 discs are in",
            initialdir=start or None, mustexist=True)
        if path:
            self._load_iso(path)

    def _shelf_label(self, det):
        """What one entry in the picker reads as -- the game, then the file,
        because a shelf often holds the same game twice."""
        return "%s   \u00b7   %s   \u00b7   %s" % (
            det.profile.short, det.profile.serial,
            os.path.basename(det.path)[:46])

    def _fill_shelf(self, folder, found, current=None):
        self._shelf_dir = folder
        self._shelf = {}
        for det in sorted(found, key=lambda d: d.profile.short):
            self._shelf[self._shelf_label(det)] = det.path
        names = list(self._shelf)
        widest = max((len(n) for n in names), default=30)
        self.game_box.configure(values=names, width=min(74, widest + 2))
        self.game_var.set("")
        if current:
            self._select_in_shelf(current)

    def _select_in_shelf(self, path):
        for label, known in self._shelf.items():
            if os.path.normcase(known) == os.path.normcase(path):
                self.game_var.set(label)
                return

    def _pick_game(self, _event=None):
        path = self._shelf.get(self.game_var.get())
        if path:
            self._load_iso(path)

    # -- preview (no disc) -------------------------------------------------
    def _enter_preview(self):
        """Fill the picker with every game this tool knows and open the first.

        For looking at what the options ARE without owning the disc, which is
        the only way to answer "what does this do" before buying into it.
        """
        self._shelf_dir = ""
        self._shelf = {}
        for p in sorted(PROFILES, key=lambda q: q.short):
            self._shelf["%s   ·   %s   ·   preview"
                         % (p.short, p.serial)] = PREVIEW_PREFIX + p.id
        names = list(self._shelf)
        self.game_box.configure(values=names,
                                width=min(74, max(len(n) for n in names) + 2))
        self.path_var.set("")
        self.game_var.set(names[0])
        self._say("Preview: no disc loaded, nothing can be written.", "warn")
        self._load_iso(self._shelf[names[0]])

    def _load_preview(self, profile_id):
        det = preview_detection(profile_id)
        self.detection, self.profile = det, det.profile
        theme.use(skins.for_profile(det.profile))
        # Every art call takes the (empty) disc path, so each one fails its own
        # open and returns nothing. A page cached from the user's own disc is
        # still honoured, which is why preview looks right on the machine that
        # owns the game and stays bare everywhere else.
        skins.set_textures(art.chrome_images(det, theme.cache_dir()))
        self.backdrop_src = art.banner_image(det, theme.cache_dir())
        self.emblem_src = art.emblem_image(det, theme.cache_dir())
        self._restyle()
        self.status.configure(text="%s   •   preview — no disc loaded"
                              % det.profile.serial, fg=theme.P.warn)
        self._build_settings()
        self._set_buttons(False)

    def _load_iso(self, path):
        path = path.strip().strip('"')
        if not path:
            return
        if path.startswith(PREVIEW_PREFIX):
            return self._load_preview(path[len(PREVIEW_PREFIX):])
        self._say("Reading %s" % (os.path.basename(path.rstrip("\\/")) or path))

        # Reading a shelf again opens every disc image on it, and can only find
        # what it just found, so a game chosen out of the picker skips to
        # identifying that one.
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
            self._fill_shelf(folder, shelf,
                             current=det.path if det.ok else None)
        elif det.ok:
            self._select_in_shelf(det.path)
        self.detection = det
        # A disc remembers the folder it was last patched through, so the
        # target does not silently change between sessions.
        remembered = getattr(self, "_saved_roots", {}).get(
            os.path.abspath(str(getattr(det, "path", "") or "")))
        self.data_root = remembered if remembered and os.path.isdir(
            remembered) else None
        self._sync_root_ui()

        if not det.ok:
            self.profile = None
            # A folder of discs is not a failure, it is a question.
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

        tone = theme.P.good if det.crc_matches else theme.P.warn
        line = "%s   •   disc CRC %s" % (det.profile.serial, det.crc)
        if det.message:
            line += "   •   " + det.message
        self.status.configure(text=line, fg=tone)
        self._say("Recognised %s (%s)" % (det.title, det.profile.serial), "good")
        if det.message:
            self._say(det.message, "warn")

        self._build_settings()
        self._remember(path)

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
        crc_ok = bool(self.detection and self.detection.crc_matches)
        self.apply_btn.set_enabled(on and has and crc_ok)
        self.cheat_btn.set_enabled(on and has)
        from tcps2 import hostroot
        self.root_btn.set_enabled(on and has and hostroot.supported(self.profile))
        self.revert_btn.set_enabled(on and bool(self.detection
                                                and self.detection.has_backup))

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

        saved = getattr(self, "_saved_values", {}).get(p.id, {})
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
        names_p = [n for n, _ in PRESETS.get(p.id, [])]
        # ttk sizes the drop-down from the entry, so widen it to the longest
        # entry or Rainbow Six 3's names get clipped mid-word
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
        where = (os.path.basename(self.detection.path)
                 or ("preview — no disc"
                     if getattr(self.detection, "preview", False) else ""))
        self._retitle(name or self.profile.short,
                      "%s  ·  %s" % (self.profile.title, where)
                      if where else self.profile.title)
        self._retitle_image(max(self.stage.winfo_width(), 10), theme.px(HEADER))
        self.area.clear()
        body = self.area.body

        if name == NOTES_TAB:
            card = Chrome(body, kind="panel", pad=theme.px(16))
            card.pack(fill="x", padx=theme.px(4), pady=theme.px(6))
            tk.Label(card.body, text=self.profile.notes, bg=theme.P.panel,
                     fg=theme.P.dim, font=theme.F("body", 9),
                     wraplength=theme.px(640), justify="left",
                     anchor="w").pack(fill="x")
            self._disc_facts(body)
            return

        self.cards = {}
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

    def _disc_facts(self, body):
        det = self.detection
        card = Chrome(body, kind="panel", pad=theme.px(16))
        card.pack(fill="x", padx=theme.px(4), pady=theme.px(6))
        if getattr(det, "preview", False):
            # No disc was read, so every fact that comes OFF a disc would be a
            # guess. Only what the profile itself knows is shown.
            rows = [("File", "— preview, no disc loaded"),
                    ("Boot", det.boot), ("Serial", det.profile.serial),
                    ("Expected CRC", det.profile.pcsx2_crc),
                    ("Cheat file", det.profile.pcsx2_crc + ".pnach"),
                    ("Backup", "—")]
        else:
            rows = [("File", det.path), ("Boot", det.boot),
                    ("Serial", det.profile.serial), ("Volume id", det.volume),
                    ("Disc CRC", det.crc + ("" if det.crc_matches else "  (unexpected)")),
                    ("Cheat file", det.profile.pcsx2_crc + ".pnach"),
                    ("Backup", "yes" if det.has_backup else "not taken yet")]
        for k, v in rows:
            r = tk.Frame(card.body, bg=theme.P.panel)
            r.pack(fill="x", pady=theme.px(2))
            tk.Label(r, text=k, bg=theme.P.panel, fg=theme.P.dim, width=14,
                     anchor="w", font=theme.F("body", 8)).pack(side="left")
            tk.Label(r, text=str(v), bg=theme.P.panel, fg=theme.P.text,
                     anchor="w", font=theme.F("mono", 9)).pack(side="left")

    def _mission_art(self, setting):
        """The disc's own loading screens for a mission card, or nothing.

        Only Rainbow Six 3 and Lockdown ship per-level art; everything else
        gets an ordinary card, which is why this returns a list rather than
        insisting on a picture.
        """
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

    # -- actions -----------------------------------------------------------
    # -- Discord -----------------------------------------------------------

    def _start_presence(self):
        """Bring the presence up if it is switched on. Failure is silent.

        There is deliberately no message when this does not work: Discord not
        being installed is the common case, not a fault, and a modal about it
        on every launch would be worse than the feature is good.
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
        # Restart rather than mutate: the application id is fixed at handshake,
        # so changing it means a new connection either way.
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
            self.presence.update(details="No disc loaded", state="Idle",
                                 image="idle", image_text=APP_NAME)
            return
        # Count controls moved off stock rather than edits built. This runs on
        # every widget change, a slider drag included, so it has to stay cheap.
        defaults = dict(self.profile.defaults())
        changed = sum(1 for k, v in self._values().items()
                      if k in defaults and v != defaults[k])
        state = self.active_group or "Browsing"
        if changed:
            state += "  -  %d change%s" % (changed, "" if changed == 1 else "s")
        self.presence.update(details="Modding " + self.profile.title,
                             state=state, image=self.profile.id,
                             image_text="%s  (%s)" % (self.profile.title,
                                                      self.profile.serial))

    def _quit(self):
        if self.presence is not None:
            self.presence.close()
        self.destroy()

    def _guard(self):
        if self.busy:
            return False
        if not (self.detection and self.detection.ok):
            dialog.info(self, APP_NAME, "Load a supported disc image first.")
            return False
        return True

    def _run(self, fn, done):
        self.busy = True
        for b in (self.apply_btn, self.cheat_btn, self.root_btn,
                  self.revert_btn):
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
                tb = traceback.format_exc()
                self._msgs.put(("done", lambda: done(None, (exc, tb))))
                posted = True
            finally:
                if not posted:
                    tb = traceback.format_exc()
                    err = RuntimeError("the job stopped before it finished, "
                                       "and the disc may be half-written -- "
                                       "use Put back to restore it")
                    self._msgs.put(("done", lambda: done(None, (err, tb))))
        threading.Thread(target=worker, daemon=True).start()

    def _apply(self):
        if not self._guard():
            return
        vals = self._values()
        path, profile = self.detection.path, self.profile
        try:
            pl = engine.plan(path, profile, vals)
        except engine.EngineError as exc:
            dialog.error(self, APP_NAME, str(exc))
            self._say(str(exc), "bad")
            return

        lines = []
        if pl.edits:
            lines.append("%d change%s into %s."
                         % (len(pl.edits), "" if len(pl.edits) == 1 else "s",
                            profile.overlays[0].name))
        if pl.data:
            lines.append("%d edit%s to the game's own data files."
                         % (len(pl.data), "" if len(pl.data) == 1 else "s"))
        if pl.pnach:
            lines.append("%d more need the emulator cheat file -- use "
                         "“Cheat file” for those." % len(pl.pnach))
        if not lines:
            lines.append("Nothing is selected, so the disc goes back to stock.")
        if pl.pristine_source == "hash":
            lines.append("A backup of the untouched disc data will be kept next "
                         "to the ISO.")
        if pl.warnings:
            lines.append("")
            lines += ["• " + w for w in pl.warnings]
        lines += ["", "Close the emulator first -- it locks the file."]
        if not dialog.ask(self, APP_NAME, "\n".join(lines)):
            return

        self._say("Patching…")

        def done(result, err):
            self.busy = False
            if err:
                self._say(str(err[0]), "bad")
                dialog.error(self, APP_NAME, str(err[0]))
            else:
                ok = result["verified"] == result["applied"]
                self._say("Done: %d of %d words verified by reading the disc "
                          "back." % (result["verified"], result["applied"]),
                          "good" if ok else "bad")
                d = result.get("data") or {}
                if d.get("files"):
                    self._say("%d data file(s) rewritten, %d read back cleanly."
                              % (d["files"], d.get("verified", 0)),
                              "bad" if d.get("broken") else "good")
                self._say("Backup: %s" % result["backup"])
                if not ok:
                    dialog.error(self, APP_NAME, "Some words did not land. The "
                                                   "disc may be a different build.")
            self.detection = identify(path)
            self._set_buttons(True)

        self.progress.set(0, None)
        self._run(lambda: engine.apply(path, profile, vals,
                                       data_root=self.data_root,
                                       tick=self._tick,
                                       progress=lambda m: self._post("  " + m)),
                  done)

    def _revert(self):
        if not self._guard():
            return
        if not dialog.ask(self, 
                APP_NAME, "Put %s back exactly as it shipped?\n\nClose the "
                          "emulator first." % os.path.basename(self.detection.path)):
            return
        path, profile = self.detection.path, self.profile

        def done(result, err):
            self.busy = False
            if err:
                self._say(str(err[0]), "bad")
                dialog.error(self, APP_NAME, str(err[0]))
            else:
                extra = (", %d data files put back" % result["data"]
                         if result.get("data") else "")
                self._say("Disc restored (stock check %s)%s."
                          % ("passed" if result["hash_ok"] else "FAILED", extra),
                          "good" if result["hash_ok"] else "bad")
            self.detection = identify(path)
            self._set_buttons(True)

        self._run(lambda: engine.revert(path, profile,
                                        data_root=self.data_root,
                                        progress=lambda m: self._post("  " + m)),
                  done)

    def _data_root(self):
        """Choose, or create, the folder the game reads instead of the disc.

        An empty folder is filled from the disc; one that already holds the
        archives is simply selected, so this is both "set up" and "switch
        back to the one I made last week".
        """
        from tcps2 import hostroot
        if not self._guard():
            return
        if self.data_root:
            if dialog.ask(self, 
                    APP_NAME,
                    "Stop using the loose data root and go back to patching "
                    "the disc itself?\n\n%s\n\nThe folder is left alone."
                    % self.data_root):
                self.data_root = None
                self._say("Back to patching the disc in place", "good")
                self._sync_root_ui()
            return
        try:
            hostroot.require(self.profile)
        except hostroot.HostRootError as exc:
            dialog.info(self, APP_NAME, str(exc))
            return
        folder = filedialog.askdirectory(
            title="An empty folder for the loose data, or one you made before")
        if not folder:
            return
        if hostroot.is_root(folder):
            self.data_root = folder
            self._say("Using the loose data root at %s" % folder, "good")
            self._sync_root_ui()
            return
        if os.listdir(folder) and not dialog.ask(self, 
                APP_NAME, "%s is not empty and is not a data root.\n\n"
                          "Export into it anyway?" % folder):
            return
        if not dialog.ask(self, 
                APP_NAME,
                "Copy the whole disc into\n%s\n\nThat is about 2.5 GB and "
                "takes a minute. Afterwards, Apply writes your edits into "
                "that folder instead of the ISO, and files there are allowed "
                "to grow.\n\nClose the emulator first -- it locks the disc."
                % folder):
            return
        path = self.detection.path

        def done(result):
            if isinstance(result, Exception):
                self._say(str(result), "bad")
                dialog.error(self, APP_NAME, str(result))
                self._set_buttons(True)
                return
            rep, bat = result
            self.data_root = folder
            self._say("Exported %d files (%.1f GB); launcher at %s"
                      % (rep["files"], rep["bytes"] / float(1 << 30), bat),
                      "good")
            dialog.info(self, 
                APP_NAME,
                "Done.\n\nRun the game with:\n%s\n\nIt has to be that "
                "launcher -- it passes -elf, which is the only thing that "
                "tells PCSX2 where the loose files are. You must also switch "
                "on Settings -> Emulation -> Enable Host Filesystem, which is "
                "off by default. Boot the ISO on its own and the game runs "
                "happily off the disc with none of your edits in it." % bat)
            self._sync_root_ui()
            self._set_buttons(True)

        def work():
            rep = hostroot.export(path, folder,
                                  progress=lambda m: self._post(m))
            return rep, hostroot.write_launcher(folder, path, _pcsx2_guess())

        self._run(work, done)

    def _sync_root_ui(self):
        """Say which target Apply is pointed at, in the button itself."""
        on = bool(self.data_root)
        self.apply_btn.set_text("Apply to data root" if on else "Apply to disc")
        self.root_btn.set_text("Using data root" if on else "Data root")

    def _save_pnach(self):
        if not self._guard():
            return
        vals = self.profile.effective(self._values())
        words = self.profile.build_pnach(vals) if self.profile.build_pnach else []
        if not words:
            dialog.info(self, APP_NAME,
                                "None of the options you have chosen need a "
                                "cheat file -- they all go into the disc.")
            return
        crc = self.detection.crc or self.profile.pcsx2_crc
        folders = engine.find_pcsx2_cheat_dirs()
        path = filedialog.asksaveasfilename(
            title="Save the PCSX2 cheat file",
            initialdir=folders[0] if folders else os.path.dirname(self.detection.path),
            initialfile="%s.pnach" % crc, defaultextension=".pnach",
            filetypes=[("PCSX2 cheat file", "*.pnach")])
        if not path:
            return
        try:
            engine.write_pnach(path, self.profile, words, crc)
        except OSError as exc:
            dialog.error(self, APP_NAME, str(exc))
            return
        self._say("Wrote %d cheat lines to %s" % (len(words), path), "good")
        dialog.info(self, 
            APP_NAME,
            "Saved %d patch lines.\n\nTurn cheats on for this game in PCSX2 and "
            "restart the emulator so the file is re-read. The lines are "
            "deliberately unlabelled: a named section added while the game is "
            "already running never takes effect." % len(words))

    # -- preferences -------------------------------------------------------
    def _remember(self, path):
        self._recent = [path] + [p for p in self._recent if p != path]
        self._recent = self._recent[:8]
        self._save_prefs()

    def _save_prefs(self):
        data = {"recent": self._recent, "profiles": {}}
        try:
            with open(settings_path(), encoding="utf-8") as fh:
                data["profiles"] = json.load(fh).get("profiles", {})
        except Exception:                         # noqa: BLE001
            pass
        if self.profile:
            data["profiles"][self.profile.id] = self._values()
        roots = data.get("data_roots", {})
        if self.detection:
            key = os.path.abspath(str(self.detection.path))
            if self.data_root:
                roots[key] = self.data_root
            else:
                roots.pop(key, None)
        data["data_roots"] = roots
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
        self._saved_values = data.get("profiles", {})
        self._saved_roots = data.get("data_roots", {})
        for p in self._recent:
            if os.path.isfile(p):
                self.after(250, lambda q=p: (self.detection is None
                                             and not self.preview_only
                                             and self._load_iso(q)))
                break


def _pcsx2_guess():
    """A pcsx2-qt.exe on this machine, or None to leave a placeholder.

    Only ever a convenience -- the launcher says to edit it, and a wrong
    guess is visible in the file rather than hidden in a setting.
    """
    import glob
    seen = []
    for root in (r"E:\Emulators", r"C:\Program Files\PCSX2",
                 os.path.expanduser(r"~\Documents\PCSX2")):
        seen += glob.glob(os.path.join(root, "*", "pcsx2-qt*.exe"))
        seen += glob.glob(os.path.join(root, "pcsx2-qt*.exe"))
    seen.sort(key=lambda p: (0 if "remix" not in p.lower() else 1, len(p)))
    return seen[0] if seen else None


def baked_preview() -> bool:
    """Was this executable built as a preview build?

    `build_exe.py --preview` drops a marker beside the assets. A friend who
    does not own the discs can then just double-click: passing `--preview` on
    a shortcut is not something anyone should have to be told to do.
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    return os.path.exists(os.path.join(base, "assets", "preview.mode"))


def main(argv=None):
    theme.set_dpi_aware()
    argv = list(sys.argv[1:] if argv is None else argv)
    app = App()
    if "--preview" in argv or "-p" in argv or baked_preview():
        # Set before the 250 ms recent-disc timer fires, so a machine that has
        # opened a disc before still lands in preview when asked for preview.
        app.preview_only = True
        app.after(150, app._enter_preview)
    else:
        for arg in argv:
            if os.path.isfile(arg):
                app.after(150, lambda q=arg: app._load_iso(q))
                break
    app.mainloop()


if __name__ == "__main__":
    main()

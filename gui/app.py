"""Tom Clancy Xbox Mod Studio -- the window.

The whole window sits on one canvas holding the loaded game's own artwork, and
every part of the interface is placed onto it, so the backdrop shows in the gaps
the way it does in the games' own menus. Which skin is in force follows the
game, and the colours are each game's own, sampled off its shell art: steel blue
for Ghost Recon, green-teal for Island Thunder, lime for Ghost Recon 2, ice for
Summit Strike, gunmetal for Rainbow Six 3, burnt orange for Black Arrow, teal
for Advanced Warfighter and crimson for Critical Hour.

What you point it at is a game: either the `.iso` it was ripped as, or a folder
someone extracted it into. Both are edited in place and neither is preferred.
The identity comes from the title id in the game's own default.xbe, so a renamed
file is still recognised and a disc holding some other game is never mistaken
for one of these.

A folder with more than one game under it is a SHELF rather than a game, so it
fills the picker beside the path instead of the tool choosing one of them --
pointing at the folder the games live in used to load whichever was reached
first, which looks like picking at random. Everything found stays one click
away afterwards, which is the usual reason to open one of these in the first
place: to compare it with the one next to it.
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

from tcxbox import art, engine  # noqa: E402
from tcxbox.detect import identify, look, preview_detection  # noqa: E402
from tcxbox.games import PROFILES  # noqa: E402
from tcxbox.model import BOOL, INT  # noqa: E402

from . import dialog, discorddialog, presence, skins, theme  # noqa: E402
from .presets import PRESETS  # noqa: E402
from .widgets import (ActionButton, Chrome, NavItem, ScrollArea,
                      SettingCard, nav_style)  # noqa: E402

APP_NAME = "Tom Clancy Xbox Mod Studio"
PRESET_HINT = "Choose a preset…"
VERSION = "1.1"
NOTES_TAB = "About this game"

#: Shelf entries are label -> path. Preview entries carry this instead of a
#: path, so one picker serves both "the games on your shelf" and "every game
#: this tool knows", and `_load_folder` stays the single way in.
PREVIEW_PREFIX = "preview:"

# A square mark -- Ghost Recon 2's stacked wordmark -- is limited by the
# header's HEIGHT, not its width, so the wide marks fill their box while the
# square ones sit well under it. A taller band costs the wide ones nothing and
# gives the square ones room.
HEADER = 148
ACTION_H = 46
LOG_H = 88
GUTTER = 22

#: Both field labels are given the same width in characters so the entry and
#: the picker below it start at the same x. Left to size themselves, "GAME" and
#: "GAMES HERE" put the two fields a centimetre apart and the panel looked
#: assembled rather than laid out.
LABEL_W = 13


def settings_path():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "TomClancyXboxModStudio")
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
        #: set by --preview so the remembered game does not load over the top
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
        self._title_text = ("Choose a game", "")
        self._msgs = queue.Queue()
        self._pumping = False
        self._recent = []
        self._last_size = (0, 0)
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
        self.path_entry.bind("<Return>",
                             lambda _e: self._load_folder(self.path_var.get()))
        self.browse = ActionButton(row, "Disc image", self._browse)
        self.browse.pack(side="left", padx=(theme.px(10), 0))
        self.browse_dir = ActionButton(row, "Folder", self._browse_folder)
        self.browse_dir.pack(side="left", padx=(theme.px(6), 0))

        # Second line: which game, out of the ones in that folder. The two
        # fields are the two questions in order -- where are your games, and
        # which one -- and the top one keeps holding the FOLDER after a game
        # loads, so the pair stays readable as a sentence instead of the top
        # field jumping to a file path the moment you choose something.
        pick = tk.Frame(self.disc.body, bg=p.panel)
        pick.pack(fill="x", pady=(theme.px(9), 0))
        self.shelf_lbl = tk.Label(pick, text="GAME", width=LABEL_W,
                                  anchor="w", bg=p.panel, fg=p.dim,
                                  font=theme.F("body", 9))
        self.shelf_lbl.pack(side="left", padx=(theme.px(6), theme.px(12)))
        self.game_var = tk.StringVar()
        self.game_box = ttk.Combobox(pick, textvariable=self.game_var,
                                     state="readonly", values=[])
        self.game_box.pack(side="left", fill="x", expand=True,
                           padx=(0, theme.px(4)), pady=theme.px(2))
        self.game_box.bind("<<ComboboxSelected>>", self._pick_game)

        self.status = tk.Label(self.stage, text="", bg=p.bg, fg=p.dim,
                               font=theme.F("body", 9), anchor="w")

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

        self.apply_btn = ActionButton(self.bar, "Apply to game", self._apply,
                                      accent=True)
        self.revert_btn = ActionButton(self.bar, "Restore game", self._revert)
        self.discord_btn = ActionButton(self.bar, "Discord", self.discord_setup)
        self.discord_btn.configure(width=self.discord_btn.width_needed())
        for b in (self.apply_btn, self.revert_btn):
            b.pack(side="right", padx=(theme.px(10), 0))
            b.set_enabled(False)
        # Packed last so it sits at the LEFT of the right-hand group: "Apply to
        # game" is the primary action and belongs at the end of the row, not
        # with a settings button beyond it. Never disabled -- it configures the
        # tool rather than touching the disc, so it works with nothing loaded.
        self.discord_btn.pack(side="right", padx=(theme.px(10), 0))

        self.logwrap = Chrome(self.stage, kind="panel", pad=theme.px(8),
                              autofit=False)
        self.log = tk.Text(self.logwrap.body, height=4, bg=p.panel, fg=p.dim,
                           font=theme.F("mono", 9), bd=0, highlightthickness=0,
                           padx=theme.px(8), pady=theme.px(2), wrap="word",
                           state="disabled")
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
                  self.revert_btn, self.discord_btn):
            b.configure(width=b.width_needed())

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

    # -- disc --------------------------------------------------------------
    def _browse(self):
        start = self.path_var.get() or ""
        path = filedialog.askopenfilename(
            title="Choose an Xbox disc image",
            initialdir=os.path.dirname(start) if start else None,
            filetypes=[("Xbox disc images", "*.iso *.xiso *.bin"),
                       ("All files", "*.*")])
        if path:
            self._load_folder(path)

    def _browse_folder(self):
        start = self.path_var.get() or ""
        path = filedialog.askdirectory(
            title="Choose an extracted Xbox game folder",
            initialdir=os.path.dirname(start) if start else None,
            mustexist=True)
        if path:
            self._load_folder(path)

    def _shelf_label(self, det):
        """What one entry in the picker reads as.

        A game on this shelf is here twice as often as not -- once as an image
        and once extracted -- so the kind and the file name are both part of
        the name, or half the list would read the same.
        """
        return "%s   ·   %s   ·   %s" % (
            det.profile.short, "disc image" if det.kind == "iso" else "folder",
            os.path.basename(det.path)[:46])

    def _fill_shelf(self, folder, found, current=None):
        self._shelf_dir = folder
        self._shelf = {}
        for det in sorted(found, key=lambda d: (d.profile.short, d.kind)):
            self._shelf[self._shelf_label(det)] = det.path
        names = list(self._shelf)
        widest = max((len(n) for n in names), default=30)
        self.game_box.configure(values=names, width=min(74, widest + 2))
        for label, path in self._shelf.items():
            if current and os.path.normcase(path) == os.path.normcase(current):
                self.game_var.set(label)
                return
        self.game_var.set("")

    def _pick_game(self, _event=None):
        path = self._shelf.get(self.game_var.get())
        if path:
            self._load_folder(path)

    def _select_in_shelf(self, path):
        for label, known in self._shelf.items():
            if os.path.normcase(known) == os.path.normcase(path):
                self.game_var.set(label)
                return

    # -- preview (no game) -------------------------------------------------
    def _enter_preview(self):
        """Fill the picker with every game this tool knows and open the first.

        For reading what the options ARE without owning the disc.
        """
        self._shelf_dir = ""
        self._shelf = {}
        for p in sorted(PROFILES, key=lambda q: q.short):
            self._shelf["%s   ·   %s   ·   preview"
                         % (p.short, p.title_id)] = PREVIEW_PREFIX + p.id
        names = list(self._shelf)
        self.game_box.configure(values=names,
                                width=min(74, max(len(n) for n in names) + 2))
        self.path_var.set("")
        self.game_var.set(names[0])
        self._say("Preview: no game loaded, nothing can be written.", "warn")
        self._load_folder(self._shelf[names[0]])

    def _load_preview(self, profile_id):
        det = preview_detection(profile_id)
        self.detection, self.profile = det, det.profile
        theme.use(skins.for_profile(det.profile))
        # No artwork in preview: art.banner_image opens the game BEFORE it
        # consults its cache and keys that cache by the game path, so an empty
        # one both raises and misses. The skin is a palette plus drawn chrome,
        # so the window still wears the right colours with no game present.
        skins.set_textures({})
        self.backdrop_src = None
        self.emblem_src = None
        self._restyle()
        self.status.configure(
            text="%s   •   title id %s   •   preview — no game loaded"
                 % (det.profile.short, det.title_id), fg=theme.P.warn)
        self._build_settings()
        self._set_buttons(False)
    def _load_folder(self, path):
        path = path.strip().strip('"')
        if not path:
            return
        if path.startswith(PREVIEW_PREFIX):
            return self._load_preview(path[len(PREVIEW_PREFIX):])
        self._say("Reading %s" % (os.path.basename(path.rstrip("\\/")) or path))

        # Reading a shelf again costs a second -- it opens every disc image on
        # it -- and can only find what it just found, so a game chosen out of
        # the picker skips straight to identifying that one.
        parent = os.path.dirname(path.rstrip("\\/"))
        cached = (self._shelf_dir
                  and os.path.normcase(parent) == os.path.normcase(self._shelf_dir))
        if cached:
            det, shelf = identify(path), []
        else:
            det, shelf = look(path)

        folder = os.path.dirname(det.chosen or det.path) if det.ok else path
        self.path_var.set(folder)
        if shelf:
            self._fill_shelf(folder, shelf,
                             current=det.path if det.ok else None)
        elif det.ok:
            self._select_in_shelf(det.path)
        self.detection = det

        if not det.ok:
            self.profile = None
            # A shelf is not a failure, it is a question, so it is not red.
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

        tone = theme.P.warn if det.missing else theme.P.good
        line = "%s   •   title id %s   •   %s" % (
            "disc image" if det.kind == "iso" else "extracted folder",
            det.title_id, det.title_name or "?")
        if os.path.normcase(det.path) != os.path.normcase(det.chosen):
            line += "   •   game root: %s" % os.path.basename(det.path)
        if det.message:
            line += "   •   " + det.message
        self.status.configure(text=line, fg=tone)
        self._say("Recognised %s (title id %s)" % (det.title, det.title_id),
                  "good")
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
        # this with True, so preview has to be vetoed HERE or opening a preview
        # profile would re-enable the write buttons behind it.
        if getattr(self.detection, "preview", False):
            on = False
        has = bool(self.profile and self.profile.settings)
        self.apply_btn.set_enabled(on and has)
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

        self._show_group(names[0] if names else None)
        self._set_buttons(True)

    def _show_group(self, name):
        self.active_group = name
        self._publish()
        for n, item in self.nav_items.items():
            item.select(n == name)
        where = (os.path.basename(self.detection.path)
                 or ("preview — no game"
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
            # No game was opened, so every fact that comes OFF a disc would be
            # a guess. Only what the profile itself knows is shown.
            rows = [("Kind", "— preview, no game loaded"),
                    ("Game", "—"),
                    ("Title id", det.title_id),
                    ("Title name", det.profile.title),
                    ("Options", "%d" % len(det.profile.settings)),
                    ("Backup", "—")]
            for k, v in rows:
                r = tk.Frame(card.body, bg=theme.P.panel)
                r.pack(fill="x", pady=theme.px(2))
                tk.Label(r, text=k, bg=theme.P.panel, fg=theme.P.dim, width=14,
                         anchor="w", font=theme.F("body", 8)).pack(side="left")
                tk.Label(r, text=str(v), bg=theme.P.panel, fg=theme.P.text,
                         anchor="w", font=theme.F("mono", 9)).pack(side="left")
            return
        rows = [("Kind", "disc image, edited in place" if det.kind == "iso"
                 else "extracted folder"),
                ("Game", det.path),
                ("You chose", det.chosen
                 if os.path.normcase(det.chosen) != os.path.normcase(det.path)
                 else "the same folder"),
                ("Executable", os.path.basename(det.xbe_path)),
                ("Title id", det.title_id),
                ("Title name", det.title_name),
                ("Expected files", "all present" if not det.missing
                 else "missing " + ", ".join(det.missing)),
                ("Backup", engine.backup_dir_for(det.path)
                 if det.has_backup else "not taken yet")]
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
            self.presence.update(details="No game loaded", state="Idle",
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
                                                      self.profile.title_id))

    def _quit(self):
        if self.presence is not None:
            self.presence.close()
        self.destroy()

    def _guard(self):
        if self.busy:
            return False
        if not (self.detection and self.detection.ok):
            dialog.info(self, APP_NAME,
                                "Load a supported game first.")
            return False
        return True

    def _run(self, fn, done):
        self.busy = True
        for b in (self.apply_btn, self.revert_btn):
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
        if pl.data:
            lines.append("%d edit%s across %d of the game's own files."
                         % (pl.total, "" if pl.total == 1 else "s", pl.files))
        else:
            lines.append("Nothing is selected, so the game goes back to stock.")
        lines.append("Every file is copied into %s before it is changed."
                     % engine.backup_dir_for(path))
        if pl.warnings:
            lines.append("")
            lines += ["• " + w for w in pl.warnings]
        lines += ["", "Close xemu first if this game is loaded in it."]
        if self.detection.kind == "iso":
            lines.insert(-2, "This writes into the disc image itself. Every "
                             "file stays where it is; nothing is rebuilt.")
        if not dialog.ask(self, APP_NAME, "\n".join(lines)):
            return

        self._say("Patching…")

        def done(result, err):
            self.busy = False
            if err:
                self._fail(err)
                dialog.error(self, APP_NAME, str(err[0]))
            else:
                ok = not result["broken"]
                self._say("Rewrote %d file(s); %d read back cleanly."
                          % (result["files"], result["verified"]),
                          "good" if ok else "bad")
                if result.get("restored"):
                    self._say("%d file(s) put back to stock because the option "
                              "that changed them is now off."
                              % result["restored"])
                for op, n in sorted((result.get("changes") or {}).items()):
                    self._say("   %s: %d value(s) changed" % (op, n))
                self._say("Backup: %s" % result["backup"])
                if not ok:
                    dialog.error(self, APP_NAME,
                                         "%d file(s) could not be read back "
                                         "afterwards." % result["broken"])
            self.detection = look(path)[0]
            self._set_buttons(True)

        self._run(lambda: engine.apply(path, profile, vals,
                                       progress=lambda m: self._post("  " + m)),
                  done)

    def _revert(self):
        if not self._guard():
            return
        if not dialog.ask(self, 
                APP_NAME, "Put %s back exactly as it shipped?\n\nClose the "
                          "xemu first."
                          % os.path.basename(self.detection.path)):
            return
        path, profile = self.detection.path, self.profile

        def done(result, err):
            self.busy = False
            if err:
                self._fail(err)
                dialog.error(self, APP_NAME, str(err[0]))
            else:
                self._say("Restored %d file(s) to the bytes they shipped "
                          "with." % result["files"], "good")
            self.detection = look(path)[0]
            self._set_buttons(True)

        self._run(lambda: engine.revert(path, profile,
                                        progress=lambda m: self._post("  " + m)),
                  done)

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
        for p in self._recent:
            if os.path.exists(p):
                self.after(250, lambda q=p: (self.detection is None
                                             and not self.preview_only
                                             and self._load_folder(q)))
                break


def baked_preview() -> bool:
    """Was this executable built as a preview build?

    `build_exe.py --preview` drops a marker beside the assets. Someone who
    does not own the discs can then just double-click it: telling a person to
    add `--preview` to a shortcut is telling them to not bother.
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    return os.path.exists(os.path.join(base, "assets", "preview.mode"))


def main(argv=None):
    theme.set_dpi_aware()
    argv = list(sys.argv[1:] if argv is None else argv)
    app = App()
    if "--preview" in argv or "-p" in argv or baked_preview():
        # Set before the 250 ms recent-game timer fires, so a machine that has
        # opened a game before still lands in preview when asked for preview.
        app.preview_only = True
        app.after(150, app._enter_preview)
    else:
        for arg in argv:
            if os.path.exists(arg):
                app.after(150, lambda q=arg: app._load_folder(q))
                break
    app.mainloop()


if __name__ == "__main__":
    main()

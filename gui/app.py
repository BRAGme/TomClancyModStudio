"""Tom Clancy PS2 Mod Studio -- the window."""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
import tkinter as tk
import traceback
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tcps2 import art, engine  # noqa: E402
from tcps2.detect import identify  # noqa: E402
from tcps2.model import BOOL, CHOICE, INT  # noqa: E402

from . import theme  # noqa: E402
from .presets import PRESETS  # noqa: E402
from .widgets import ScrollArea, SettingCard  # noqa: E402

APP_NAME = "Tom Clancy PS2 Mod Studio"
VERSION = "1.0"
BANNER_H = 132   # logical pixels; scaled by the theme once the display is known
NOTES_TAB = "About this disc"


def settings_path():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "TomClancyPS2ModStudio")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "settings.json")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("%s %s" % (APP_NAME, VERSION))
        self.configure(bg=theme.BG)
        theme.install(self)
        self._set_icon()
        self.px = theme.px
        self.geometry("%dx%d" % (self.px(1120), self.px(830)))
        self.minsize(self.px(880), self.px(620))

        self.detection = None
        self.profile = None
        self.vars = {}
        self.cards = {}
        self.active_group = None
        self.busy = False
        self._banner_photo = None
        self._msgs = queue.Queue()
        self._recent = []

        self._build()
        self._load_prefs()
        self.after(120, self._pump)

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
            except Exception:
                continue

    # -- layout ------------------------------------------------------------
    def _build(self):
        self.banner = tk.Label(self, bd=0, bg=theme.BG)
        self.banner.pack(fill="x")
        self._draw_banner()

        disc = ttk.Frame(self, padding=(theme.px(22), theme.px(14), theme.px(22), theme.px(8)))
        disc.pack(fill="x")
        ttk.Label(disc, text="Disc image").pack(side="left", padx=(0, theme.px(10)))
        self.path_var = tk.StringVar()
        self.path_entry = ttk.Entry(disc, textvariable=self.path_var)
        self.path_entry.pack(side="left", fill="x", expand=True)
        self.path_entry.bind("<Return>", lambda _e: self._load_iso(self.path_var.get()))
        ttk.Button(disc, text="Browse…", command=self._browse).pack(side="left", padx=(theme.px(8), 0))

        self.status = ttk.Label(self, text="Choose a Rainbow Six 3, Ghost Recon or "
                                           "Jungle Storm disc image to begin.",
                                style="Dim.TLabel")
        self.status.pack(fill="x", padx=theme.px(24), pady=(0, theme.px(10)))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=theme.px(22))

        self.nav = ttk.Frame(body, width=theme.px(196))
        self.nav.pack(side="left", fill="y")
        self.nav.pack_propagate(False)

        right = ttk.Frame(body, style="Panel.TFrame")
        right.pack(side="left", fill="both", expand=True)
        self.area = ScrollArea(right)
        self.area.pack(fill="both", expand=True, padx=theme.px(2), pady=theme.px(2))

        bar = ttk.Frame(self, padding=(theme.px(22), theme.px(12), theme.px(22), theme.px(6)))
        bar.pack(fill="x")
        ttk.Label(bar, text="Preset").pack(side="left", padx=(0, theme.px(8)))
        self.preset_var = tk.StringVar(value="")
        self.preset_box = ttk.Combobox(bar, textvariable=self.preset_var, width=24,
                                       state="readonly", values=[])
        self.preset_box.pack(side="left")
        self.preset_box.bind("<<ComboboxSelected>>", self._apply_preset)

        self.apply_btn = ttk.Button(bar, text="Apply to disc", style="Accent.TButton",
                                    command=self._apply, state="disabled")
        self.apply_btn.pack(side="right")
        self.cheat_btn = ttk.Button(bar, text="Save cheat file…",
                                    command=self._save_pnach, state="disabled")
        self.cheat_btn.pack(side="right", padx=theme.px(8))
        self.revert_btn = ttk.Button(bar, text="Restore disc", style="Danger.TButton",
                                     command=self._revert, state="disabled")
        self.revert_btn.pack(side="right", padx=theme.px(8))

        logwrap = ttk.Frame(self, padding=(theme.px(22), 0, theme.px(22), theme.px(14)))
        logwrap.pack(fill="x")
        self.log = tk.Text(logwrap, height=6, bg=theme.PANEL, fg=theme.DIM,
                           font=theme.FONT_MONO, bd=0, highlightthickness=0,
                           padx=theme.px(12), pady=theme.px(8), wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)
        self.log.tag_configure("good", foreground=theme.GOOD)
        self.log.tag_configure("warn", foreground=theme.WARN)
        self.log.tag_configure("bad", foreground=theme.BAD)
        self._say("%s %s -- ready." % (APP_NAME, VERSION))

    def _draw_banner(self, image=None, title=APP_NAME, subtitle="Patch a PS2 disc in place"):
        w = max(self.winfo_width(), theme.px(1120))
        h = theme.px(BANNER_H)
        photo = (theme.make_banner(image, w, h, title, subtitle) if image
                 else theme.flat_banner(w, h, title, subtitle))
        if photo is None:
            self.banner.configure(text=title, font=theme.FONT_H1, fg=theme.TEXT,
                                  height=3)
            return
        self._banner_photo = photo
        self.banner.configure(image=photo, text="")

    # -- logging -----------------------------------------------------------
    def _say(self, text, tag=None):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n", tag or ())
        self.log.see("end")
        self.log.configure(state="disabled")

    def _pump(self):
        while True:
            try:
                kind, payload = self._msgs.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._say(*payload)
            elif kind == "done":
                payload()
        self.after(120, self._pump)

    def _post(self, text, tag=None):
        self._msgs.put(("log", (text, tag)))

    # -- disc --------------------------------------------------------------
    def _browse(self):
        start = os.path.dirname(self.path_var.get()) if self.path_var.get() else ""
        path = filedialog.askopenfilename(
            title="Choose a PS2 disc image",
            initialdir=start or None,
            filetypes=[("PS2 disc images", "*.iso *.bin"), ("All files", "*.*")])
        if path:
            self._load_iso(path)

    def _load_iso(self, path):
        path = path.strip().strip('"')
        if not path:
            return
        self.path_var.set(path)
        self._say("Reading %s" % os.path.basename(path))
        det = identify(path)
        self.detection = det
        if not det.ok:
            self.profile = None
            self.status.configure(text=det.message, foreground=theme.BAD)
            self._say(det.message, "bad")
            self._draw_banner()
            self.area.clear()
            self._set_buttons(False)
            return

        self.profile = det.profile
        tone = theme.GOOD if det.crc_matches else theme.WARN
        line = "%s   •   %s   •   disc CRC %s" % (
            det.title, det.profile.serial, det.crc)
        if det.message:
            line += "   •   " + det.message
        self.status.configure(text=line, foreground=tone)
        self._say("Recognised %s (%s)" % (det.title, det.profile.serial), "good")
        if det.message:
            self._say(det.message, "warn")

        self._draw_banner(art.banner_image(det, theme.cache_dir()),
                          det.title, "%s   ·   %s" % (det.profile.serial,
                                                           os.path.basename(path)))
        self._build_settings()
        self._remember(path)

    def _set_buttons(self, on):
        has_edits = bool(self.profile and self.profile.settings)
        crc_ok = bool(self.detection and self.detection.crc_matches)
        self.apply_btn.configure(state="normal" if on and has_edits and crc_ok else "disabled")
        self.cheat_btn.configure(state="normal" if on and has_edits else "disabled")
        can_revert = bool(self.detection and self.detection.has_backup)
        self.revert_btn.configure(state="normal" if on and can_revert else "disabled")

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
        for key, value in p.normalise(saved).items() if saved else []:
            if key in self.vars:
                try:
                    self.vars[key].set(value)
                except tk.TclError:
                    pass

        names = list(p.groups())
        if p.notes:
            names.append(NOTES_TAB)
        self.preset_box.configure(values=[name for name, _ in PRESETS.get(p.id, [])])
        self.preset_var.set("")

        for child in self.nav.winfo_children():
            child.destroy()
        self._nav_buttons = {}
        for name in names:
            b = ttk.Button(self.nav, text=name, style="Nav.TButton",
                           command=lambda n=name: self._show_group(n))
            b.pack(fill="x", pady=theme.px(1))
            self._nav_buttons[name] = b

        self._show_group(names[0] if names else None)
        self._set_buttons(True)

    def _show_group(self, name):
        self.active_group = name
        for n, b in getattr(self, "_nav_buttons", {}).items():
            b.configure(style="NavOn.TButton" if n == name else "Nav.TButton")
        self.area.clear()
        body = self.area.body

        if name == NOTES_TAB:
            card = ttk.Frame(body, style="Card.TFrame", padding=theme.px(18))
            card.pack(fill="x", padx=theme.px(10), pady=theme.px(8))
            ttk.Label(card, text=self.profile.title, style="H2.TLabel").pack(anchor="w")
            ttk.Label(card, text=self.profile.notes, style="Help.TLabel",
                      wraplength=theme.px(620), justify="left").pack(anchor="w", pady=(theme.px(10), 0))
            self._disc_facts(body)
            return

        self.cards = {}
        for s in self.profile.settings:
            if s.group != name:
                continue
            card = SettingCard(body, s, self.vars[s.key], self._changed)
            card.pack(fill="x", padx=theme.px(10), pady=theme.px(6))
            self.cards[s.key] = card
        if not self.cards:
            ttk.Label(body, text="Nothing to configure here yet.",
                      style="PanelDim.TLabel").pack(padx=theme.px(18), pady=theme.px(18), anchor="w")
        self._changed()

    def _disc_facts(self, body):
        det = self.detection
        card = ttk.Frame(body, style="Card.TFrame", padding=theme.px(18))
        card.pack(fill="x", padx=theme.px(10), pady=theme.px(8))
        ttk.Label(card, text="This disc", style="H2.TLabel").pack(anchor="w")
        rows = [("File", det.path),
                ("Boot", det.boot),
                ("Serial", det.profile.serial),
                ("Volume id", det.volume),
                ("Disc CRC", det.crc + ("" if det.crc_matches else "  (unexpected)")),
                ("Cheat file", det.profile.pcsx2_crc + ".pnach"),
                ("Backup", "yes" if det.has_backup else "not taken yet")]
        for k, v in rows:
            r = ttk.Frame(card, style="Card.TFrame")
            r.pack(fill="x", pady=theme.px(2))
            ttk.Label(r, text=k, style="PanelDim.TLabel", width=14).pack(side="left")
            ttk.Label(r, text=str(v), style="Mono.TLabel").pack(side="left")

    def _values(self):
        return {k: v.get() for k, v in self.vars.items()}

    def _changed(self):
        if not self.profile:
            return
        vals = self._values()
        for key, card in self.cards.items():
            missing = self.profile.unmet(key, vals)
            s = self.profile.setting(key)
            if not s.enabled:
                card.set_enabled(False)
            elif missing:
                card.set_enabled(False, "needs " + " and ".join(missing))
            else:
                card.set_enabled(True)
        self._save_prefs()

    def _apply_preset(self, _e=None):
        name = self.preset_var.get()
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
    def _guard(self):
        if self.busy:
            return False
        if not (self.detection and self.detection.ok):
            messagebox.showinfo(APP_NAME, "Load a supported disc image first.")
            return False
        return True

    def _run(self, fn, done):
        self.busy = True
        for b in (self.apply_btn, self.cheat_btn, self.revert_btn):
            b.configure(state="disabled")

        def worker():
            try:
                result = fn()
                self._msgs.put(("done", lambda: done(result, None)))
            except Exception as exc:                      # noqa: BLE001
                tb = traceback.format_exc()
                self._msgs.put(("done", lambda: done(None, (exc, tb))))
        threading.Thread(target=worker, daemon=True).start()

    def _apply(self):
        if not self._guard():
            return
        vals = self._values()
        path = self.detection.path
        profile = self.profile

        try:
            pl = engine.plan(path, profile, vals)
        except engine.EngineError as exc:
            messagebox.showerror(APP_NAME, str(exc))
            self._say(str(exc), "bad")
            return

        lines = ["%d change%s will be written into %s."
                 % (len(pl.edits), "" if len(pl.edits) == 1 else "s",
                    profile.overlays[0].name)]
        if pl.pnach:
            lines.append("%d more need the emulator cheat file -- use "
                         "“Save cheat file” for those." % len(pl.pnach))
        if pl.pristine_source == "hash":
            lines.append("A backup of the untouched disc data will be kept next "
                         "to the ISO.")
        if pl.warnings:
            lines.append("")
            lines += ["• " + w for w in pl.warnings]
        lines.append("")
        lines.append("Close the emulator first -- it locks the file.")
        if not messagebox.askokcancel(APP_NAME, "\n".join(lines)):
            return

        self._say("Patching…")

        def work():
            return engine.apply(path, profile, vals, progress=lambda m: self._post("  " + m))

        def done(result, err):
            self.busy = False
            if err:
                exc, tb = err
                self._say(str(exc), "bad")
                messagebox.showerror(APP_NAME, str(exc))
            else:
                ok = result["verified"] == result["applied"]
                self._say("Done: %d of %d words verified by reading the disc back."
                          % (result["verified"], result["applied"]),
                          "good" if ok else "bad")
                self._say("Backup: %s" % result["backup"])
                if self.profile.build_pnach and self.profile.build_pnach(vals):
                    self._say("Some options still need the cheat file.", "warn")
                if not ok:
                    messagebox.showerror(APP_NAME, "Some words did not land. The "
                                                   "disc may be a different build.")
            self.detection = identify(path)
            self._set_buttons(True)

        self._run(work, done)

    def _revert(self):
        if not self._guard():
            return
        if not messagebox.askokcancel(
                APP_NAME, "Put %s back exactly as it shipped?\n\nClose the "
                          "emulator first." % os.path.basename(self.detection.path)):
            return
        path, profile = self.detection.path, self.profile

        def done(result, err):
            self.busy = False
            if err:
                self._say(str(err[0]), "bad")
                messagebox.showerror(APP_NAME, str(err[0]))
            else:
                self._say("Disc restored (stock hash %s)."
                          % ("matches" if result["hash_ok"] else "DOES NOT match"),
                          "good" if result["hash_ok"] else "bad")
            self.detection = identify(path)
            self._set_buttons(True)

        self._run(lambda: engine.revert(path, profile,
                                        progress=lambda m: self._post("  " + m)), done)

    def _save_pnach(self):
        if not self._guard():
            return
        vals = self._values()
        words = self.profile.build_pnach(vals) if self.profile.build_pnach else []
        if not words:
            messagebox.showinfo(APP_NAME,
                                "None of the options you have chosen need a cheat "
                                "file -- they all go straight into the disc.")
            return
        crc = self.detection.crc or self.profile.pcsx2_crc
        name = "%s.pnach" % crc
        folders = engine.find_pcsx2_cheat_dirs()
        initial = folders[0] if folders else os.path.dirname(self.detection.path)
        path = filedialog.asksaveasfilename(
            title="Save the PCSX2 cheat file",
            initialdir=initial, initialfile=name,
            defaultextension=".pnach",
            filetypes=[("PCSX2 cheat file", "*.pnach")])
        if not path:
            return
        try:
            engine.write_pnach(path, self.profile, words, crc)
        except OSError as exc:
            messagebox.showerror(APP_NAME, str(exc))
            return
        self._say("Wrote %d cheat lines to %s" % (len(words), path), "good")
        messagebox.showinfo(
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
            old = json.load(open(settings_path(), encoding="utf-8"))
            data["profiles"] = old.get("profiles", {})
        except Exception:
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
            data = json.load(open(settings_path(), encoding="utf-8"))
        except Exception:
            return
        self._recent = data.get("recent", [])
        self._saved_values = data.get("profiles", {})
        for p in self._recent:
            if os.path.isfile(p):
                self.after(250, lambda q=p: (self.detection is None
                                             and self._load_iso(q)))
                break


def main():
    theme.set_dpi_aware()
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

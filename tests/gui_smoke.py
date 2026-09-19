r"""Open the real window on every installed game and walk every page.

Not a unit test -- it builds the actual Tk widgets, loads each game's real
artwork out of the user's installation, switches skins, renders every settings
page and every card on it, and reports what broke. A tool whose whole point is
that it looks like the game it is modding cannot be checked by asserting on
data structures.

    python tests\gui_smoke.py                     walk every game it can find
    python tests\gui_smoke.py --shots <dir>       ...and save a PNG per page
    python tests\gui_smoke.py --preview           walk the preview profiles

Nothing is written to any game folder. The window closes itself.
"""

from __future__ import annotations

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tcpc import art                                          # noqa: E402
from tcpc.games import PROFILES                               # noqa: E402
from tcpc.install import scan_folder                          # noqa: E402


def find_games():
    """Every supported installation on this machine, one per game id."""
    seen, out = set(), []
    for lib in art.search_roots():
        for det in scan_folder(lib):
            if det.profile.id in seen:
                continue
            seen.add(det.profile.id)
            out.append(det)
    return out


def grab(app, path):
    """Save what THIS window looks like, and nothing else on the screen.

    Deliberately not `ImageGrab.grab(bbox=...)`. That copies whatever pixels
    are at those screen coordinates, and this window opens behind whatever the
    person was already doing -- so the first version of this captured a browser
    window and wrote someone's private page to disk. `PrintWindow` asks the
    window to render ITSELF into an off-screen bitmap: it cannot pick up
    anything in front of it, and it works while the window is occluded or
    minimised, which is what a smoke test wants anyway.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        from PIL import Image
    except ImportError:
        return False

    app.update_idletasks()
    app.update()
    hwnd = ctypes.windll.user32.GetParent(app.winfo_id()) or app.winfo_id()
    rect = wintypes.RECT()
    if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False
    w, h = rect.right - rect.left, rect.bottom - rect.top
    if w < 8 or h < 8:
        return False

    gdi = ctypes.windll.gdi32
    src = ctypes.windll.user32.GetWindowDC(hwnd)
    dc = gdi.CreateCompatibleDC(src)
    bmp = gdi.CreateCompatibleBitmap(src, w, h)
    gdi.SelectObject(dc, bmp)
    # 2 is PW_RENDERFULLCONTENT: without it a composited window comes back
    # black on current Windows.
    ok = ctypes.windll.user32.PrintWindow(hwnd, dc, 2)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG),
                    ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]

    hdr = BITMAPINFOHEADER()
    hdr.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    hdr.biWidth, hdr.biHeight = w, -h        # negative: top-down rows
    hdr.biPlanes, hdr.biBitCount = 1, 32
    buf = ctypes.create_string_buffer(w * h * 4)
    got = gdi.GetDIBits(dc, bmp, 0, h, buf, ctypes.byref(hdr), 0)

    gdi.DeleteObject(bmp)
    gdi.DeleteDC(dc)
    ctypes.windll.user32.ReleaseDC(hwnd, src)
    if not ok or not got:
        return False
    Image.frombuffer("RGBA", (w, h), buf.raw, "raw", "BGRA", 0, 1
                     ).convert("RGB").save(path)
    return True


def check_shelf(app, games):
    r"""Games in different places must all stay on offer at once.

    A person's games are not in one folder. On this machine they are in two
    Steam libraries on two drives plus two Advanced Warfighter titles sitting
    loose at a drive root, because those were never Steam titles. Browsing to
    one used to replace the picker with whatever was beside it, so reaching a
    game on another drive meant browsing again -- or sweeping every drive
    again, every session.

    So: load each one in turn and require the picker to keep growing rather
    than swapping, and require every entry to still load afterwards.
    """
    print("\n=== the picker, across %d location(s)"
          % len({os.path.dirname(d.path).lower() for d in games}))
    failures = 0
    counts = []
    for det in games:
        app._load_install(det.path)
        app.update()
        counts.append(len(app._shelf))
    drives = sorted({os.path.splitdrive(os.path.abspath(p))[0].upper()
                     for p in app._shelf.values()})
    print("  picker grew %s -> holds %d game(s) across %s"
          % (" -> ".join(str(c) for c in counts[:4]), len(app._shelf),
             ", ".join(drives) or "one drive"))
    if len(app._shelf) < len(games):
        print("  FAILED: the picker lost entries as locations changed")
        failures += 1
    if len(set(app._shelf)) != len(app._shelf):
        print("  FAILED: two entries read identically")
        failures += 1
    for label, path in list(app._shelf.items()):
        app.game_var.set(label)
        app._pick_game()
        app.update()
        det = app.detection
        if not (det and det.ok
                and os.path.normcase(det.path) == os.path.normcase(path)):
            print("  FAILED to load from the picker: %s" % label)
            failures += 1
    if not failures:
        print("  every entry loads without browsing again")
    return failures


def check_dropdown(app):
    r"""The pickers must survive being looked at.

    The skinned list is a frame placed in the window, and the first build
    dismissed it from a `<Configure>` binding -- which Tk fires while laying
    the window out, so it shut in the same breath it opened. In a screenshot
    that is indistinguishable from a control that was never clicked, so it is
    asserted here instead: open it, pump the event loop the way a real session
    does, and require it to still be there.
    """
    from gui import theme

    print("\n=== the pickers")
    failures = 0
    for name, box in (("game", app.game_box), ("preset", app.preset_box)):
        box._open()
        app.update()                      # the event that used to close it
        if box._popup is None:
            print("  FAILED: the %s list closed itself on a redraw" % name)
            failures += 1
            continue
        rows = [t for t in box._canvas.find_all()
                if box._canvas.type(t) == "text"]
        drawn = [box._canvas.itemcget(t, "text") for t in rows]
        if drawn != box._values:
            print("  FAILED: the %s list paints %d row(s) for %d value(s)"
                  % (name, len(drawn), len(box._values)))
            failures += 1
        # wide enough for its own longest entry
        if box._popup.winfo_width() < box._content_width() - 1:
            print("  FAILED: the %s list clips its longest entry" % name)
            failures += 1
        # the marker bar and highlight are the window's, not Tk's
        fills = {box._canvas.itemcget(t, "fill") for t in box._canvas.find_all()
                 if box._canvas.type(t) == "rectangle"}
        if theme.P.tab not in fills:
            print("  FAILED: the %s list is missing the selected marker" % name)
            failures += 1
        box._on_key(type("E", (), {"keysym": "Down", "char": ""})())
        box._on_key(type("E", (), {"keysym": "Escape", "char": ""})())
        if box._popup is not None:
            print("  FAILED: the %s list ignored Escape" % name)
            failures += 1
    # the preset box is on the last row: its list has to open upwards
    app.preset_box._open()
    app.update()
    up = app.preset_box._popup
    if up is None or up.winfo_y() >= (app.preset_box.winfo_rooty()
                                      - app.winfo_rooty()):
        print("  FAILED: the preset list opens downwards, off the window")
        failures += 1
    app.preset_box._close()
    if not failures:
        print("  both open, paint in the skin's colours, and close on Escape")
    return failures


class CallbackWatch:
    r"""Make a Tk callback fault fail the run instead of only printing it.

    Tk catches an exception raised inside a callback -- a button command, a
    binding, an `after` job -- and hands it to `Tk.report_callback_exception`,
    whose default prints a traceback to stderr and carries on. The run
    continues, this file's own counter never hears about it, and the last line
    still says `0 failure(s)`.

    That is not hypothetical. For most of one session this test printed a
    traceback out of the GUI's message pump on every single run and reported
    zero failures throughout, because the counter and the traceback were
    independent -- and the person reading the output had started filtering the
    repeated lines away as noise. They were the symptom of a real bug: the
    pump re-armed itself only on its last line, so one raise in a completion
    callback stopped it for good and hung the window.

    A smoke test that prints a fault and then passes is worse than one that
    never looked, because it supplies the reassurance without the checking. So
    the faults are counted, and each is labelled with whatever was on screen
    when it happened.
    """

    def __init__(self, app):
        self.faults = []
        self.where = "start-up"
        app.report_callback_exception = self._report

    def _report(self, exc, val, tb):
        text = "".join(traceback.format_exception(exc, val, tb))
        self.faults.append((self.where, text))
        sys.stderr.write(text)          # still shown, exactly as before

    def report(self):
        """Print what was caught. Returns how many, to add to the failures."""
        if not self.faults:
            return 0
        print("\n=== %d Tk callback fault(s)" % len(self.faults))
        print("    These print and carry on, so before this they passed.")
        for where, text in self.faults:
            lines = text.rstrip().splitlines()
            print("  %s" % where)
            for line in lines:
                print("    %s" % line)
        return len(self.faults)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    shots = None
    if "--shots" in argv:
        i = argv.index("--shots")
        shots = argv[i + 1]
        os.makedirs(shots, exist_ok=True)
        del argv[i:i + 2]
    preview = "--preview" in argv

    from gui.app import App, PREVIEW_PREFIX
    from gui import theme

    theme.set_dpi_aware()
    app = App()
    watch = CallbackWatch(app)
    app.geometry("1280x900+40+40")
    app.update()

    targets = ([(p.short, PREVIEW_PREFIX + p.id) for p in PROFILES] if preview
               else [(d.profile.short, d.path) for d in find_games()])
    if not targets:
        print("No supported games found. Try --preview.")
        app.destroy()
        return 1

    failures = 0
    if not preview:
        watch.where = "the picker"
        failures += check_shelf(app, find_games())
        watch.where = "the dropdowns"
        failures += check_dropdown(app)
    for name, where in targets:
        print("\n=== %s" % name)
        watch.where = "%s: loading" % name
        try:
            app._load_install(where)
            app.update()
        except Exception:                         # noqa: BLE001
            print("  LOAD FAILED")
            traceback.print_exc()
            failures += 1
            continue
        if app.profile is None:
            print("  not recognised: %s" % app.detection.message)
            failures += 1
            continue
        print("  skin=%s  backdrop=%s  emblem=%s"
              % (theme.P.chrome,
                 app.backdrop_src.size if app.backdrop_src else None,
                 app.emblem_src.size if app.emblem_src else None))
        pages = list(app.nav_items)
        for page in pages:
            watch.where = "%s: %s" % (name, page)
            try:
                app._show_group(page)
                app.update()
            except Exception:                     # noqa: BLE001
                print("  PAGE FAILED: %s" % page)
                traceback.print_exc()
                failures += 1
                continue
            cards = len(app.cards)
            print("    %-22s %d card%s" % (page, cards, "" if cards == 1 else "s"))
            if shots:
                out = os.path.join(shots, "%s-%s.png"
                                   % (app.profile.id,
                                      page.lower().replace(" ", "-")))
                grab(app, out)
        # exercise every preset too: they set real controls, so a preset that
        # names a setting that has been renamed would otherwise only be found
        # by a user clicking it
        from gui.presets import PRESETS
        for pname, _vals in PRESETS.get(app.profile.id, []):
            watch.where = "%s: preset %s" % (name, pname)
            try:
                app.preset_var.set(pname)
                app._apply_preset()
                app.update()
            except Exception:                     # noqa: BLE001
                print("  PRESET FAILED: %s" % pname)
                traceback.print_exc()
                failures += 1

    watch.where = "shutdown"
    app.destroy()
    failures += watch.report()
    print("\n%d failure(s)." % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

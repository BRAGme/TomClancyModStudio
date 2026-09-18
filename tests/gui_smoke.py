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
    app.geometry("1280x900+40+40")
    app.update()

    targets = ([(p.short, PREVIEW_PREFIX + p.id) for p in PROFILES] if preview
               else [(d.profile.short, d.path) for d in find_games()])
    if not targets:
        print("No supported games found. Try --preview.")
        app.destroy()
        return 1

    failures = 0
    for name, where in targets:
        print("\n=== %s" % name)
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
            try:
                app.preset_var.set(pname)
                app._apply_preset()
                app.update()
            except Exception:                     # noqa: BLE001
                print("  PRESET FAILED: %s" % pname)
                traceback.print_exc()
                failures += 1

    app.destroy()
    print("\n%d failure(s)." % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

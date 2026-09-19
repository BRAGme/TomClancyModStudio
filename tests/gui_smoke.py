"""Open the real window on every game on the shelf, walk every page, close it.

This is not a screenshot test and it does not know what the window should look
like. It is here because almost every way the interface can be broken -- a card
whose control kind has no widget, a skin that names a colour the palette does
not have, a settings page that asks the profile for something it stopped
providing -- shows up as an exception while building, and building it for real
is the only way to find those.

    python tests\\gui_smoke.py "E:\\XBOX Classic Games"
"""

from __future__ import annotations

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tcxbox.detect import scan                 # noqa: E402


def main(argv):
    shelf = argv[0] if argv else r"E:\XBOX Classic Games"
    found = scan(shelf)
    if not found:
        print("no supported games under %s" % shelf)
        return 1
    # One of each game is enough to prove every page builds, and this shelf has
    # most of them twice -- as a disc image and as an extracted folder.
    seen, unique = set(), []
    for det in found:
        if det.profile.id not in seen:
            seen.add(det.profile.id)
            unique.append(det)
    found = unique

    from gui.app import App                     # noqa: E402  (needs a display)
    from tests.callbackwatch import CallbackWatch            # noqa: E402

    app = App()
    # A fault inside a Tk callback only prints; without this the run would
    # carry on and still report success. See tests/callbackwatch.py.
    watch = CallbackWatch(app)
    app.geometry("1160x860")
    failures = []
    for det in found:
        watch.where = det.profile.short
        try:
            app._load_folder(det.path)
            app.update()
            for group in list(app.nav_items):
                watch.where = "%s / %s" % (det.profile.short, group)
                app._show_group(group)
                app.update()
            print("  %-18s %2d pages, %2d cards on %s"
                  % (det.profile.short, len(app.nav_items), len(app.cards),
                     app.active_group))
        except Exception as exc:                 # noqa: BLE001
            failures.append((det.profile.short, exc, traceback.format_exc()))
            print("  %-18s FAILED: %s" % (det.profile.short, exc))
    watch.where = "shutdown"
    app.destroy()
    failures.extend(watch.as_tuples())

    if failures:
        for _short, _exc, tb in failures:
            print(tb)
        return 1
    print("%d game(s), every page built" % len(found))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

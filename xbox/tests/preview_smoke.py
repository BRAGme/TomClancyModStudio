"""Drive preview mode through every game and every page with the real widgets.

Uses update() instead of mainloop(), so the window appears for a moment and
closes. Catches anything that only breaks when a profile is opened with no
game behind it -- which is most of what preview mode could get wrong.

Needs no disc: that is the whole point of the mode it tests.
"""
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tcxbox.games import PROFILES
from gui import theme
from gui.app import App, PREVIEW_PREFIX
from tests.callbackwatch import CallbackWatch

def main():
    theme.set_dpi_aware()
    app = App()
    # A fault inside a Tk callback only prints; without this the run would
    # carry on and still report success. See tests/callbackwatch.py.
    watch = CallbackWatch(app)
    app.preview_only = True
    fails = []
    try:
        app._enter_preview()
        app.update()
        labels = list(app._shelf)
        assert len(labels) == len(PROFILES), "shelf has %d, expected %d" % (
            len(labels), len(PROFILES))
        for label in labels:
            watch.where = label
            assert app._shelf[label].startswith(PREVIEW_PREFIX), app._shelf[label]
            app.game_var.set(label)
            try:
                app._pick_game()
                app.update()
            except Exception:
                fails.append("load %s\n%s" % (label, traceback.format_exc()))
                continue
            det = app.detection
            for what, ok in (("preview flag", det.preview is True),
                             ("profile set", app.profile is not None),
                             ("no artwork", app.backdrop_src is None
                              and app.emblem_src is None),
                             ("apply disabled", not app.apply_btn.enabled),
                             ("revert disabled", not app.revert_btn.enabled)):
                if not ok:
                    fails.append("%s: %s FAILED" % (label, what))
            groups = list(app.nav_items)
            for g in groups:
                watch.where = "%s / %s" % (label, g)
                try:
                    app._show_group(g)
                    app.update()
                except Exception:
                    fails.append("%s / page %r\n%s" % (label, g, traceback.format_exc()))
            print("  %-26s %3d settings, %2d pages  write buttons off=%s"
                  % (app.profile.short, len(app.profile.settings), len(groups),
                     not (app.apply_btn.enabled or app.revert_btn.enabled)))
    finally:
        watch.where = "shutdown"
        try: app.destroy()
        except Exception: pass
    fails.extend(watch.as_strings())
    print()
    if fails:
        print("FAILURES (%d):" % len(fails))
        for f in fails: print("---\n" + f)
        return 1
    print("preview smoke: all %d games, all pages, no exceptions, no artwork, "
          "all write buttons disabled" % len(PROFILES))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

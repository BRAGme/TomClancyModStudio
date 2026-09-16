"""Drive preview mode through every game and every tab with the real widgets.

Uses update() instead of mainloop(), so the window appears for a moment and
closes. Catches anything that only breaks when a profile is opened with no
disc behind it -- which is most of what preview mode could get wrong.
"""
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tcps2.games import PROFILES
from gui import theme
from gui.app import App, PREVIEW_PREFIX

def main():
    theme.set_dpi_aware()
    app = App()
    app.preview_only = True
    fails = []
    try:
        app._enter_preview()
        app.update()
        labels = list(app._shelf)
        assert len(labels) == len(PROFILES), "shelf has %d, expected %d" % (
            len(labels), len(PROFILES))
        for label in labels:
            target = app._shelf[label]
            assert target.startswith(PREVIEW_PREFIX), target
            app.game_var.set(label)
            try:
                app._pick_game()
                app.update()
            except Exception:
                fails.append("load %s\n%s" % (label, traceback.format_exc()))
                continue
            det = app.detection
            checks = [
                ("preview flag", det.preview is True),
                ("profile set", app.profile is not None),
                ("apply disabled", not app.apply_btn.enabled),
                ("cheat disabled", not app.cheat_btn.enabled),
                ("revert disabled", not app.revert_btn.enabled),
            ]
            for what, ok in checks:
                if not ok:
                    fails.append("%s: %s FAILED" % (label, what))
            groups = list(app.nav_items)
            for g in groups:
                try:
                    app._show_group(g)
                    app.update()
                except Exception:
                    fails.append("%s / tab %r\n%s" % (label, g, traceback.format_exc()))
            print("  %-46s %2d settings, %2d tabs  buttons off=%s"
                  % (app.profile.short, len(app.profile.settings), len(groups),
                     not (app.apply_btn.enabled or app.cheat_btn.enabled
                          or app.revert_btn.enabled)))
    finally:
        try: app.destroy()
        except Exception: pass
    print()
    if fails:
        print("FAILURES (%d):" % len(fails))
        for f in fails: print("---\n" + f)
        return 1
    print("preview smoke: all %d games, all tabs, no exceptions, "
          "all write buttons disabled" % len(PROFILES))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

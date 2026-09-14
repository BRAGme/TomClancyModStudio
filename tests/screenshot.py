"""Launch the window, load a disc, snap each page, and quit.

This is how the UI gets checked: a layout bug is invisible in a unit test and
obvious in a picture. It captures only the application window's own rectangle.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui import theme  # noqa: E402

theme.set_dpi_aware()

from gui.app import App  # noqa: E402


def shoot(app, out_path):
    """Capture strictly the app's own window, and nothing behind it.

    `-topmost` guarantees no other window can be inside the rectangle, so this
    never picks up anything else that happens to be on screen.
    """
    from PIL import ImageGrab
    app.attributes("-topmost", True)
    app.lift()
    app.update_idletasks()
    app.update()
    x, y = app.winfo_rootx(), app.winfo_rooty()
    w, h = app.winfo_width(), app.winfo_height()
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    img.save(out_path)
    return out_path


def main(iso, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    app = App()
    app.update()
    app.geometry("%dx%d+40+40" % (theme.px(1120), theme.px(830)))
    app.update()
    shots = []

    def run():
        app._load_iso(iso)
        app.update()
        app.after(400, capture_pages)

    def capture_pages():
        names = list(getattr(app, "nav_items", {}).keys()) or ["(none)"]
        for i, name in enumerate(names):
            app._show_group(name)
            app.update_idletasks()
            app.update()
            safe = "".join(c if c.isalnum() else "_" for c in name)
            shots.append(shoot(app, os.path.join(out_dir, "%d_%s.png" % (i, safe))))
        app.quit()

    app.after(300, run)
    app.mainloop()
    app.destroy()
    for s in shots:
        print(s)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

"""Entry point for both the window and the command line.

    "Tom Clancys PS2 ModStudio.exe"                 -- open the window
    "Tom Clancys PS2 ModStudio.exe" <disc.iso>      -- open the window on that disc
    "Tom Clancys PS2 ModStudio.exe" --preview       -- read the options with no disc
    "Tom Clancys PS2 ModStudio.exe" --cli ...       -- do it from a script instead

Preview mode exists so someone without the disc can see what every option does.
Nothing is readable and nothing is writable in it: the write buttons are held
off, and the artwork is absent because it is read from the owner's own disc at
run time and is never shipped with this tool.

Kept as one executable so a release is a single file to download.
"""

from __future__ import annotations

import os
import sys

if getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(sys.executable))
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _attach_console():
    """The packaged exe is built windowed so launching it never flashes a
    console. In --cli mode it borrows the console it was started from, which is
    what makes one binary serve both jobs."""
    if not getattr(sys, "frozen", False) or not sys.platform.startswith("win"):
        return
    import ctypes
    if not ctypes.windll.kernel32.AttachConsole(-1):
        return
    for name, stream, mode in (("stdout", 1, "w"), ("stderr", 2, "w")):
        try:
            setattr(sys, name, open("CONOUT$", mode, buffering=1,
                                    encoding="utf-8", errors="replace"))
        except OSError:
            pass


def main():
    argv = sys.argv[1:]
    if argv and argv[0] in ("--cli", "-c"):
        _attach_console()
        from cli import main as cli_main
        raise SystemExit(cli_main(argv[1:]))
    from gui.app import main as gui_main
    gui_main(argv)


if __name__ == "__main__":
    main()

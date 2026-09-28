r"""Tom Clancy PC Mod Studio -- entry point.

Double-clicked, this opens the window. With `--cli` it runs the command-line
mode instead; one binary serves both, which is why the CLI has to reattach to
the parent console when the build is windowed.
"""

import sys


def main():
    argv = sys.argv[1:]
    if "--cli" in argv:
        argv.remove("--cli")
        _attach_console()
        from cli import main as cli_main
        raise SystemExit(cli_main(argv))
    from gui.app import main as gui_main
    gui_main(argv)


def _attach_console():
    """A windowed build has no stdout. Borrow the caller's."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        if ctypes.windll.kernel32.AttachConsole(-1):
            sys.stdout = open("CONOUT$", "w", buffering=1)
            sys.stderr = open("CONOUT$", "w", buffering=1)
    except Exception:                             # noqa: BLE001
        pass


if __name__ == "__main__":
    main()

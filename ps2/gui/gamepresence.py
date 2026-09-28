r"""Discord Rich Presence for the GAME, by driving `drp.exe`.

WHY THIS DRIVES A SEPARATE PROGRAM INSTEAD OF DOING IT HERE
-----------------------------------------------------------

The obvious design -- speak Discord's IPC from this window, the way
`gui/presence.py` used to -- cannot work for game presence, for a reason that
has nothing to do with Discord:

**Nobody has the patcher open while they are playing.** You close it, you boot
the emulator, you play. A presence owned by this process dies at the moment it
would start being interesting. `drp.exe` is a background program built for
exactly that shape, so this module installs it, starts it and gets out of the
way.

The second reason is registration. `gui/presence.py` needed the user to go and
create a Discord application of their own before anything showed at all, which
is a minute of faff that most people will not do, and the feature was silently
dead until they did. `drp` ships with application ids already registered
(`pcsx2_client_id` in its own `drp.ini`), so there is nothing to set up.

WHAT IT SHOWS
-------------

`drp` watches PCSX2 over PINE and reports what you are *doing* -- the mission,
the operative, objectives, difficulty -- not merely that an emulator is open.
It knows Rainbow Six 3 (`SLUS-20883`), Ghost Recon (`SLUS-20613`) and Jungle
Storm (`SLUS-20820`) in detail, and shows generic presence for anything else
PCSX2 is running.

WHAT THIS MODULE MAY NOT DO
---------------------------

* **Never block the window.** Every call here is either a fast file check or a
  subprocess with a timeout, and the dialog calls them from button presses
  rather than from a paint path.
* **Never show a console.** `drp` is a console program; started without
  `CREATE_NO_WINDOW` it flashes a black box and then owns a window nobody
  asked for.
* **Never be a fault.** Discord not installed, `drp` not present, PCSX2 not
  running -- all normal. Nothing in here raises for those; the dialog reads
  the status and says what is true.

PINE, AND THE ONE REAL CONFLICT
-------------------------------

`drp` reads PCSX2 through PINE, and **PINE serves one client at a time**. So
`drp` running means no other PINE client can attach, and its own diagnostics
say the same about each other. That matters to anyone driving PCSX2 from a
script; it does not matter to this tool, which never speaks PINE.
"""

from __future__ import annotations

import os
import subprocess
import sys

EXE_NAME = "drp.exe"

#: Subfolder beside the ModStudio executable that the release ships it in.
BUNDLED_DIR = "drp"

#: Windows only. Everywhere else this feature is simply absent, which the
#: dialog reports rather than pretending.
SUPPORTED = sys.platform == "win32"

_NO_WINDOW = 0x08000000        # CREATE_NO_WINDOW
_DETACHED = 0x00000008         # DETACHED_PROCESS


def _app_dir() -> str:
    """The folder the tool is running out of, frozen or not."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def candidates() -> list:
    """Every place `drp.exe` is looked for, best first."""
    base = _app_dir()
    out = [os.path.join(base, BUNDLED_DIR, EXE_NAME),
           os.path.join(base, EXE_NAME)]
    # A development checkout sitting beside this one.
    repo = os.path.dirname(base)
    out.append(os.path.join(repo, "drp", "bin", EXE_NAME))
    return out


def find() -> str | None:
    """The `drp.exe` this tool will use, or None."""
    for p in candidates():
        if os.path.isfile(p):
            return p
    return None


def _run(exe, args, timeout=20):
    """Run drp and hand back (ok, output). Never raises."""
    try:
        r = subprocess.run([exe] + list(args), capture_output=True, text=True,
                           timeout=timeout, creationflags=_NO_WINDOW)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except Exception as exc:                       # noqa: BLE001
        return False, str(exc)


def is_running() -> bool:
    """True if a `drp.exe` is already up.

    Asked of the operating system rather than remembered, because the usual
    case is that the user started it on a previous run, or it came up at login
    and this window has never seen it.
    """
    if not SUPPORTED:
        return False
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq " + EXE_NAME],
                           capture_output=True, text=True, timeout=15,
                           creationflags=_NO_WINDOW)
        return EXE_NAME.lower() in (r.stdout or "").lower()
    except Exception:                              # noqa: BLE001
        return False


def start() -> tuple:
    """Start it in the background. Returns (ok, message)."""
    exe = find()
    if exe is None:
        return False, "drp.exe was not found beside the tool."
    if is_running():
        return True, "It was already running."
    try:
        subprocess.Popen([exe], cwd=os.path.dirname(exe),
                         creationflags=_NO_WINDOW | _DETACHED,
                         stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception as exc:                       # noqa: BLE001
        return False, "Could not start it: %s" % exc
    return True, "Game presence is on."


def stop() -> tuple:
    """Stop it. Returns (ok, message)."""
    if not is_running():
        return True, "It was not running."
    try:
        subprocess.run(["taskkill", "/IM", EXE_NAME, "/F"],
                       capture_output=True, timeout=15,
                       creationflags=_NO_WINDOW)
    except Exception as exc:                       # noqa: BLE001
        return False, "Could not stop it: %s" % exc
    return True, "Game presence is off."


def set_startup(on: bool) -> tuple:
    """Ask drp to start itself at login, or stop doing that.

    This is drp's own `--startup` switch rather than anything written from
    here: it owns whatever registry key or shortcut it uses, and duplicating
    that guess is how two programs end up fighting over one entry.
    """
    exe = find()
    if exe is None:
        return False, "drp.exe was not found beside the tool."
    ok, out = _run(exe, ["--startup", "on" if on else "off"])
    if not ok:
        return False, (out.strip().splitlines() or ["drp refused."])[-1]
    return True, ("It will start when you log in."
                  if on else "It will no longer start at login.")


def status() -> dict:
    """Everything the dialog needs, in one cheap call."""
    exe = find()
    return {"supported": SUPPORTED,
            "exe": exe,
            "installed": exe is not None,
            "running": is_running() if exe else False}

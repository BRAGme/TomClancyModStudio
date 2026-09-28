r"""Discord Rich Presence -- "Playing Tom Clancy Xbox Mod Studio", with the disc.

Discord's local IPC is a named pipe on Windows (`\\.\pipe\discord-ipc-N`) and a
unix socket everywhere else, carrying length-prefixed JSON. That is small enough
to speak directly, so this needs no `pypresence` and adds nothing to the build.

Two things are worth knowing before wiring the toggle up.

**It needs an application id of your own.** Discord will only show a presence
for an app registered to someone's account, and there is no generic id to
borrow. Making one is free and takes about a minute -- see `HOW_TO` below, which
the dialog shows verbatim. Without an id the feature stays off and silent.

**None of this may ever be able to break the window.** Discord not running, a
half-open pipe, a version that answers with something unexpected: every one of
those is normal and none of them is the user's problem. So the socket lives on a
daemon thread, every failure drops the connection and retries later, and the
only thing the GUI ever calls is `update()`, which does nothing but hand over a
dict.
"""

from __future__ import annotations

import json
import os
import socket
import struct
import sys
import threading
import time
import uuid
from pathlib import Path

OP_HANDSHAKE, OP_FRAME, OP_CLOSE, OP_PING, OP_PONG = 0, 1, 2, 3, 4

#: Reconnect delay when Discord is not there. Long enough not to spin.
RETRY = 15.0
#: Discord rate-limits SET_ACTIVITY to roughly five per twenty seconds, so
#: updates are coalesced: flipping quickly through pages publishes the page you
#: stopped on, not every page on the way.
MIN_INTERVAL = 4.0

#: Asset keys the dialog asks for. These are the profile ids, so the window can
#: hand its own `profile.id` straight to Discord with no lookup table in
#: between. Any key that is missing simply shows no picture.
#:
#: Discord folds asset keys to lower case and allows only letters, digits,
#: underscores and dashes -- which every profile id here already satisfies.
ASSET_KEYS = ("r6_3_slus20883", "ghost_recon_slus20613",
              "jungle_storm_slus20820", "soaf_sles51180",
              "gr2_slus21105", "graw_slus21422", "lockdown_slus21144",
              "idle")

HOW_TO = (
    "Discord only shows a presence for an application registered to a Discord "
    "account, and there is no shared id to borrow, so this needs one of yours. "
    "It is free and takes about a minute:\n\n"
    "1.  Open discord.com/developers/applications and press New Application.\n"
    "2.  Name it whatever you want to appear under your name -- the "
    "application name is the line that reads \"Playing ...\".\n"
    "3.  Copy the Application ID from that page and paste it below.\n\n"
    "For the disc artwork, open Rich Presence then Art Assets on the same page "
    "and upload an image for each game you want a picture for, named exactly "
    "as listed below. Any one you leave out just shows no picture."
)

#: Shown under HOW_TO so the names can be copied rather than transcribed.
ASSET_HELP = "\n".join([
    "r6_3_slus20883          Rainbow Six 3",
    "ghost_recon_slus20613   Ghost Recon",
    "jungle_storm_slus20820  Jungle Storm",
    "soaf_sles51180          Sum of All Fears",
    "gr2_slus21105           Ghost Recon 2",
    "graw_slus21422          Advanced Warfighter",
    "lockdown_slus21144      Rainbow Six Lockdown",
    "idle                    no disc loaded",
])


def _pipes():
    """Every socket Discord might be listening on, in the order to try."""
    if sys.platform == "win32":
        for i in range(10):
            yield r"\\.\pipe\discord-ipc-%d" % i
        return
    base = (os.environ.get("XDG_RUNTIME_DIR") or os.environ.get("TMPDIR")
            or os.environ.get("TMP") or "/tmp")
    # Flatpak and snap put theirs one level down
    for sub in ("", "app/com.discordapp.Discord", "snap.discord"):
        for i in range(10):
            yield os.path.join(base, sub, "discord-ipc-%d" % i)


class _Pipe:
    """One open IPC connection: a Windows file handle, or a unix socket."""

    def __init__(self, path):
        if sys.platform == "win32":
            self._f = open(path, "r+b", buffering=0)
            self._sock = None
        else:
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._sock.settimeout(5.0)
            self._sock.connect(path)
            self._f = None

    def send(self, op, payload):
        blob = json.dumps(payload).encode("utf-8")
        data = struct.pack("<II", op, len(blob)) + blob
        if self._f is not None:
            self._f.write(data)
            self._f.flush()
        else:
            self._sock.sendall(data)

    def recv(self):
        op, size = struct.unpack("<II", self._read(8))
        return op, (json.loads(self._read(size).decode("utf-8")) if size else {})

    def _read(self, n):
        out = b""
        while len(out) < n:
            chunk = (self._f.read(n - len(out)) if self._f is not None
                     else self._sock.recv(n - len(out)))
            if not chunk:
                raise OSError("Discord closed the pipe")
            out += chunk
        return out

    def close(self):
        try:
            (self._f if self._f is not None else self._sock).close()
        except Exception:
            pass


class Presence:
    """Publishes one activity, and keeps publishing it until told otherwise."""

    def __init__(self, app_id: str):
        self.app_id = str(app_id).strip()
        self._activity = None
        self._dirty = False
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._pipe = None
        self._thread = None
        #: True once the handshake has been answered, so the dialog can say so
        self.connected = False
        #: last reason it is not connected, shown in the dialog rather than hidden
        self.error = ""
        self.started_at = int(time.time())

    # -- what the window calls -------------------------------------------
    def start(self):
        if self._thread is not None or not self.app_id:
            return
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="discord-presence")
        self._thread.start()

    def update(self, details="", state="", image="", image_text=""):
        """Replace the published activity. Never blocks, never raises."""
        activity = {"timestamps": {"start": self.started_at}}
        # Discord rejects a field that is present but shorter than two
        # characters, so a blank one has to be left out rather than sent empty.
        if len(details) >= 2:
            activity["details"] = details[:128]
        if len(state) >= 2:
            activity["state"] = state[:128]
        if image:
            assets = {"large_image": image}
            if len(image_text) >= 2:
                assets["large_text"] = image_text[:128]
            activity["assets"] = assets
        with self._lock:
            if activity != self._activity:
                self._activity = activity
                self._dirty = True

    def close(self):
        self._stop.set()
        if self._pipe is not None:
            try:
                self._pipe.send(OP_FRAME, self._frame(None))
            except Exception:
                pass
        self._drop()

    # -- the thread -------------------------------------------------------
    def _run(self):
        last = 0.0
        while not self._stop.is_set():
            if self._pipe is None and not self._connect():
                self._stop.wait(RETRY)
                continue
            with self._lock:
                activity, dirty = self._activity, self._dirty
            now = time.monotonic()
            if dirty and activity is not None and now - last >= MIN_INTERVAL:
                with self._lock:
                    self._dirty = False
                if self._publish(activity):
                    last = now
                else:
                    self._drop()
                    continue
            self._stop.wait(0.5)
        self._drop()

    def _connect(self) -> bool:
        for path in _pipes():
            try:
                pipe = _Pipe(path)
            except Exception:
                continue
            try:
                pipe.send(OP_HANDSHAKE, {"v": 1, "client_id": self.app_id})
                op, payload = pipe.recv()
            except Exception as exc:
                self.error = str(exc)
                pipe.close()
                continue
            if op == OP_CLOSE:
                # A wrong or unknown application id lands here, and no amount
                # of retrying will fix it, so keep what Discord said.
                self.error = str(payload.get("message")
                                 or "Discord refused that application id")
                pipe.close()
                return False
            self._pipe = pipe
            self.connected = True
            self.error = ""
            with self._lock:
                self._dirty = self._activity is not None
            return True
        if not self.error:
            self.error = "Discord is not running"
        return False

    def _publish(self, activity) -> bool:
        try:
            self._pipe.send(OP_FRAME, self._frame(activity))
            op, payload = self._pipe.recv()
            if op == OP_PING:
                self._pipe.send(OP_PONG, payload)
            return True
        except Exception as exc:
            self.error = str(exc)
            return False

    def _drop(self):
        self.connected = False
        if self._pipe is not None:
            self._pipe.close()
            self._pipe = None

    @staticmethod
    def _frame(activity):
        return {"cmd": "SET_ACTIVITY",
                "args": {"pid": os.getpid(), "activity": activity},
                "nonce": str(uuid.uuid4())}


# -- preferences ---------------------------------------------------------
# The same root the wordmark and glyph caches use. Nothing here is secret -- an
# application id is public -- but it is per user, so it belongs beside the cache
# rather than in the repository or inside the exe.

def _settings_path() -> Path:
    root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(root) / "TomClancyPS2-ModStudio" / "settings.json"


def load() -> dict:
    """{"enabled": bool, "app_id": str}. Never raises; missing file is off."""
    try:
        with open(_settings_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        data = {}
    section = data.get("discord") or {}
    app_id = os.environ.get("TCMS_DISCORD_APP_ID") or section.get("app_id")
    return {"enabled": bool(section.get("enabled", False)),
            "app_id": str(app_id or "").strip()}


def save(enabled: bool, app_id: str):
    """Rewrite only the discord section, leaving any other setting alone."""
    path = _settings_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    data["discord"] = {"enabled": bool(enabled), "app_id": app_id.strip()}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, path)

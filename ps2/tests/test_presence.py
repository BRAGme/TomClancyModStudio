"""Discord presence: the settings file, the activity shape, and staying quiet.

The last of those is the one that matters. Presence is a nicety bolted to the
side of a tool whose actual job is writing to disc images, so the bar is not
"does it connect" -- it is "can it ever take the window down with it". Every
test here that pokes at the socket pokes at a socket that is not there.

Needs no disc and no Discord.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui import presence

passed, failed = 0, []


def ok(name, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print("  ok    " + name)
    else:
        failed.append(name + (("  -- " + detail) if detail else ""))
        print("  FAIL  " + name + (("  -- " + detail) if detail else ""))


def with_temp_settings(fn):
    """Run fn against a settings file in a temp dir, never the real one."""
    real = presence._settings_path
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "settings.json"
        presence._settings_path = lambda: path
        try:
            fn(path)
        finally:
            presence._settings_path = real


# -- the settings file ---------------------------------------------------

def test_settings(path):
    ok("missing file reads as off", presence.load() == {"enabled": False,
                                                        "app_id": ""})
    presence.save(True, " 1234567890 ")
    got = presence.load()
    ok("round-trips, trimmed", got == {"enabled": True, "app_id": "1234567890"},
       repr(got))

    # Someone else's setting must survive our write, or the file becomes ours
    # alone and nothing else can ever be stored beside it.
    data = json.loads(path.read_text(encoding="utf-8"))
    data["window"] = {"maximised": True}
    path.write_text(json.dumps(data), encoding="utf-8")
    presence.save(False, "1234567890")
    after = json.loads(path.read_text(encoding="utf-8"))
    ok("leaves other sections alone", after.get("window") == {"maximised": True},
       repr(after))
    ok("toggling off is persisted", presence.load()["enabled"] is False)

    path.write_text("{ not json at all", encoding="utf-8")
    ok("a corrupt file reads as off, not a crash",
       presence.load() == {"enabled": False, "app_id": ""})
    presence.save(True, "99")
    ok("and a corrupt file is overwritten cleanly",
       presence.load()["app_id"] == "99")

    os.environ["TCMS_DISCORD_APP_ID"] = "555"
    try:
        ok("the environment overrides the file", presence.load()["app_id"] == "555")
    finally:
        del os.environ["TCMS_DISCORD_APP_ID"]


# -- the activity --------------------------------------------------------

def test_activity():
    p = presence.Presence("123456789012345678")
    p.update(details="Modding Rainbow Six 3", state="Controller", image="r6_3_slus20883",
             image_text="Rainbow Six 3  (SLUS-20883)")
    a = p._activity
    ok("details and state carried", a["details"] == "Modding Rainbow Six 3"
       and a["state"] == "Controller")
    ok("asset key carried", a["assets"]["large_image"] == "r6_3_slus20883")
    ok("elapsed clock is set", isinstance(a["timestamps"]["start"], int))
    ok("first update is dirty", p._dirty is True)

    p._dirty = False
    p.update(details="Modding Rainbow Six 3", state="Controller", image="r6_3_slus20883",
             image_text="Rainbow Six 3  (SLUS-20883)")
    ok("an unchanged update is not re-sent", p._dirty is False)

    # Discord rejects a field that is present but under two characters, so a
    # blank one has to be absent rather than empty.
    p.update(details="", state="x", image="")
    ok("short fields are left out", "details" not in p._activity
       and "state" not in p._activity and "assets" not in p._activity,
       repr(p._activity))

    p.update(details="d" * 400, state="s" * 400)
    ok("long fields are clipped to 128", len(p._activity["details"]) == 128
       and len(p._activity["state"]) == 128)

    frame = presence.Presence._frame(None)
    ok("clearing sends a null activity", frame["cmd"] == "SET_ACTIVITY"
       and frame["args"]["activity"] is None and "nonce" in frame)


# -- never takes the window with it --------------------------------------

def test_quiet():
    p = presence.Presence("")
    p.start()
    ok("no application id means no thread at all", p._thread is None)
    p.close()               # must not raise with nothing open
    ok("closing an unstarted presence is fine", True)

    p = presence.Presence("123456789012345678")
    real = presence._pipes
    presence._pipes = lambda: iter(["\\\\.\\pipe\\definitely-not-discord-xyz"])
    try:
        ok("a dead socket returns False, not an exception",
           p._connect() is False)
        ok("and says why", bool(p.error), repr(p.error))
        ok("stays disconnected", p.connected is False)
    finally:
        presence._pipes = real

    p.update(details="Modding Rainbow Six 3", state="Controller")
    ok("update works with no connection", p._dirty is True)
    p.close()
    ok("close with no connection is fine", True)


def test_asset_keys():
    """The asset keys ARE the profile ids.

    The window hands `profile.id` straight to Discord, so if a profile is ever
    renamed the art silently stops appearing -- nothing raises, the picture
    just goes missing. Pinning them here turns that into a failing test.
    """
    from tcps2.games import BY_ID
    keys = set(presence.ASSET_KEYS) - {"idle"}
    ids = set(BY_ID)
    ok("every disc has an asset key", not ids - keys, str(sorted(ids - keys)))
    ok("no asset key names a disc that is gone", not keys - ids,
       str(sorted(keys - ids)))
    ok("the help text lists every key",
       all(k in presence.ASSET_HELP for k in presence.ASSET_KEYS))
    # Discord lower-cases asset keys and accepts only [a-z0-9_-]
    bad = [k for k in presence.ASSET_KEYS
           if k != k.lower() or not all(c.isalnum() or c in "_-" for c in k)]
    ok("every key is a legal Discord asset name", not bad, str(bad))


def main():
    with_temp_settings(test_settings)
    test_asset_keys()
    test_activity()
    test_quiet()
    print("\n%d checks passed, %d failed" % (passed, len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

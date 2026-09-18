"""Finding a game on disk, and saying how healthy it is.

The PS2 and Xbox tools identify a game from something authoritative inside it
-- the boot file named in `SYSTEM.CNF`, the title id in the XBE. A PC install
has no such stamp, so identification here is by SIGNATURE: a short list of
files that only that game has, checked against the folder.

The list is deliberately made of *data* files rather than the executable.
Every one of these installs already has third-party DLLs, ASI loaders and
renamed executables sitting in it from other work, so "is `RavenShield.exe`
present" is a question about what somebody did last week. "Is
`system\\R6Weapons.u` present" is a question about what game this is.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from .games import BY_ID, PROFILES


@dataclass
class Detection:
    path: str
    ok: bool
    profile: object = None
    exe_version: str = ""
    message: str = ""
    has_backup: bool = False
    #: files the profile expects that are not there
    missing: list = field(default_factory=list)
    #: True for a profile opened without an install, to look at the options
    #: only. Nothing is readable and nothing is writable in this state.
    preview: bool = False

    @property
    def title(self):
        return self.profile.title if self.profile else "Unrecognised folder"


def preview_detection(profile) -> Detection:
    """A profile opened with no install behind it, so the options can be read.

    `path` stays EMPTY on purpose. Every art loader takes the install path, and
    an empty one makes them fail their own open and return nothing, so none of
    them needs a preview branch. A page already cached from the user's own copy
    of the game is still used when one exists -- which is why this is not the
    same as shipping the artwork.
    """
    if isinstance(profile, str):
        profile = BY_ID[profile]
    return Detection(
        "", True, profile=profile, preview=True,
        message="Preview only — no installation is loaded, so nothing "
                "can be written. Open a game folder to use these options.")


def _has(root, pattern) -> bool:
    """Is there a file matching this relative pattern under `root`?

    Patterns are matched case-insensitively against the relative path, because
    these installs disagree with themselves about case -- Ghost Recon ships
    `AKS74U.GUN` beside `ak47.gun` in the same folder -- and a signature that
    only matched one spelling would fail on half the shelf.
    """
    pattern = pattern.replace("\\", "/")
    if "*" not in pattern and "?" not in pattern:
        direct = os.path.join(root, pattern.replace("/", os.sep))
        if os.path.exists(direct):
            return True
        # fall through to the case-insensitive walk below
    head, _, tail = pattern.rpartition("/")
    folder = os.path.join(root, head.replace("/", os.sep)) if head else root
    if not os.path.isdir(folder):
        # the directory itself may differ in case
        folder = _resolve_dir(root, head) if head else root
        if folder is None:
            return False
    rx = re.compile(_glob_rx(tail), re.I)
    try:
        return any(rx.fullmatch(n) for n in os.listdir(folder))
    except OSError:
        return False


def _resolve_dir(root, rel):
    """`rel` under `root`, matched a component at a time, ignoring case."""
    cur = root
    for part in [p for p in rel.split("/") if p]:
        try:
            names = os.listdir(cur)
        except OSError:
            return None
        for n in names:
            if n.lower() == part.lower() and os.path.isdir(os.path.join(cur, n)):
                cur = os.path.join(cur, n)
                break
        else:
            return None
    return cur


def _glob_rx(pattern) -> str:
    out = []
    for ch in pattern:
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
    return "".join(out)


def backup_dir_for(root) -> str:
    return os.path.join(str(root), ".tcpc-backup")


def identify(path) -> Detection:
    """Which game, if any, this folder holds."""
    path = os.path.abspath(str(path))
    if not os.path.isdir(path):
        return Detection(path, False, message="Not a folder.")

    scored = []
    for p in PROFILES:
        sig = p.layout.signature
        hits = [s for s in sig if _has(path, s)]
        if hits:
            scored.append((len(hits), len(sig), p, hits))
    if not scored:
        names = ", ".join(sorted(p.short for p in PROFILES))
        return Detection(path, False,
                         message="No supported game here. Supported: %s." % names)

    scored.sort(key=lambda t: (t[0] / t[1], t[0]), reverse=True)
    hits, total, profile, matched = scored[0]
    missing = [s for s in profile.layout.signature if s not in matched]

    # EVERY signature file has to be there. A partial match is not a partial
    # install -- it is a different game. Pointed at a Steam library, a Vegas
    # signature that included the generic `Engine\Config\BaseEngine.ini`
    # claimed five unrelated Unreal titles as Vegas, because one third of a
    # signature was enough. Requiring the whole set is what stops that, and
    # naming the near miss keeps the message useful rather than blank.
    if missing:
        return Detection(path, False, missing=missing,
                         message="This looks like %s, but %s %s not here — "
                                 "so it is not, and nothing will be written."
                                 % (profile.short, ", ".join(missing),
                                    "is" if len(missing) == 1 else "are"))

    folder = backup_dir_for(path)
    bak = os.path.exists(os.path.join(folder, "manifest.json"))

    return Detection(path, True, profile=profile, has_backup=bak,
                     exe_version=_exe_stamp(path, profile))


def _exe_stamp(root, profile) -> str:
    """A short "size/mtime" fingerprint of the game executable.

    Not a version number -- these games do not carry one anywhere readable --
    but enough to notice that the binary changed between one session and the
    next, which on these particular installs happens a lot: every one of them
    is also a Remix project with its own proxy DLLs and patched executables.
    """
    rel = profile.layout.exe
    if not rel:
        return ""
    exe = os.path.join(root, rel.replace("/", os.sep))
    if not os.path.isfile(exe):
        found = _resolve_dir(root, os.path.dirname(rel.replace("\\", "/")))
        if found:
            want = os.path.basename(rel).lower()
            for n in os.listdir(found):
                if n.lower() == want:
                    exe = os.path.join(found, n)
                    break
    try:
        st = os.stat(exe)
    except OSError:
        return ""
    return "%d bytes, %s" % (st.st_size,
                             __import__("time").strftime(
                                 "%Y-%m-%d", __import__("time").localtime(st.st_mtime)))


def scan_folder(folder, limit=40) -> list:
    """Every supported install directly inside `folder`.

    Aimed at a Steam library's `steamapps\\common`, which is where all five of
    these live, so pointing the tool at the library fills the picker.
    """
    out = []
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return out
    for name in names:
        sub = os.path.join(folder, name)
        if not os.path.isdir(sub):
            continue
        det = identify(sub)
        if det.ok:
            out.append(det)
        if len(out) >= limit:
            break
    return out


def look(path):
    """(detection, shelf) -- one install, or the installs sitting in a folder.

    A library folder is not a game, so pointing at one fills the picker rather
    than being an error. Pointing at a game reads it properly and lists what is
    beside it, because the reason to open one of these is usually to do the
    same thing to the next one.
    """
    path = os.path.abspath(str(path))
    if os.path.isfile(path):
        path = os.path.dirname(path)
    det = identify(path)
    if det.ok:
        return det, scan_folder(os.path.dirname(path))
    found = scan_folder(path)
    if found:
        return Detection(path, False,
                         message="%d game%s here — pick one from the list."
                                 % (len(found), "" if len(found) == 1 else "s")), found
    return det, []

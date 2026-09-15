"""An extracted Xbox game folder, presented as one flat, keyed namespace.

The four Red Storm games keep the same file in two places at once: the mission
XML sits loose under `mission\\` **and** inside `globs\\ikedata.glb`, byte for
byte identical, and the enemy templates those missions name sit only inside the
per-level `*_chars.glb`. Editing one copy and not the other is the obvious way
to produce a mod that appears to do nothing, so this module refuses to make that
distinction available: a `Root` indexes loose files and glob members together,
and an edit that matches a key is applied wherever that key is.

Keys are upper-case, `/`-separated, and rooted at the game folder:

    /MISSION/M01_CAVES.MIS                             a loose file
    /GLOBS/IKEDATA.GLB/M01_CAVES.MIS                   the same, in a glob
    /SYSTEM/RAINBOWSIX3XBOX.INI                        loose again
    /SYSTEM/XBOXDYNAMIC.UMD/SYSTEM/R6GAMESETTINGS.INI  inside a bundle

so `\\.MIS$` reaches both copies, `^/MISSION/` reaches only the loose one, and
`\\.GLB/` reaches only the packed ones. A profile normally wants the first.

Rainbow Six 3 is the case that makes all this worth the trouble. Its System
folder looks like two ini files and a pile of cooked packages; the 16 KB
gameplay table and the 115 terrorist templates are inside
`System\\xboxdynamic.umd`, and the bundle holds a SECOND, different copy of
`RainbowSix3Xbox.ini` besides.

The unit of work is the whole folder rather than a disc image because that is
how these games are actually run on this machine -- Cxbx-Reloaded loads the
extracted tree directly -- and because a loose tree has no directory records to
keep consistent. Inside a glob or a bundle, writes are length-preserving: a glob
has no index at all, so every entry's position is implied by the length of the
one before it. A loose file may change size freely, and `dataedit` decides which
rule applies per key rather than imposing the stricter one on everything.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import globfile, umd

#: folders that never hold anything this tool edits. Skipping them is not an
#: optimisation, it is what keeps loading a game folder off the several hundred
#: megabytes of textures and audio next door.
SKIP_DIRS = {"textures", "sounds", "sound", "videos", "video", "media",
             "maps", "staticmeshes", "animations", "model", "motion",
             "magma", "loadingscreens", "rtx-remix", "save", "dvdextras",
             "voicerec", "havokdata", "karmadata", "refmaps", "cubicmaps",
             "commandmaps", "mapobjects", "rendererdata", "briefings"}

#: extensions worth indexing loose. Everything this tool edits is text.
DATA_SUFFIXES = (".mis", ".atr", ".gun", ".kit", ".wsf", ".gtf", ".ass",
                 ".cgs", ".cms", ".prj", ".itm", ".vcl", ".env", ".ini",
                 ".tpt", ".xml", ".kil")

#: bundles that hold a second, different copy of the files next to them.
#: Rainbow Six 3 on Xbox keeps its real System folder in one of these.
BUNDLE_SUFFIX = ".umd"


class RootError(Exception):
    pass


@dataclass
class Place:
    """One physical copy of a file: a loose path, or a slot inside a glob."""
    relpath: str                 # game-folder-relative, OS separators
    entry: object = None         # the container's own entry, when packed
    kind: str = "glob"           # "glob" or "umd"; ignored when entry is None

    @property
    def packed(self) -> bool:
        return self.entry is not None


@dataclass
class File:
    key: str
    name: str
    size: int
    places: list = field(default_factory=list)


class Root:
    """A game folder, indexed once and then addressed by key."""

    def __init__(self, path, index_globs=True):
        self.path = os.path.abspath(str(path))
        self.name = os.path.basename(self.path)
        self.files = {}
        self._glob_cache = {}
        self._dirty = set()
        self._index(index_globs)

    # -- building the index ------------------------------------------------
    def _index(self, index_globs):
        for dirpath, dirnames, filenames in os.walk(self.path):
            rel = os.path.relpath(dirpath, self.path)
            if rel == ".":
                rel = ""
            dirnames[:] = [d for d in dirnames
                           if d.lower() not in SKIP_DIRS and not d.startswith(".")]
            for fn in filenames:
                low = fn.lower()
                relpath = os.path.join(rel, fn) if rel else fn
                if low.endswith(".glb"):
                    if index_globs:
                        self._index_glob(relpath)
                    continue
                if low.endswith(BUNDLE_SUFFIX):
                    self._index_umd(relpath)
                    continue
                if not low.endswith(DATA_SUFFIXES):
                    continue
                key = "/" + relpath.replace("\\", "/").upper()
                size = os.path.getsize(os.path.join(self.path, relpath))
                self.files.setdefault(key, File(key, fn.upper(), size, []))
                self.files[key].places.append(Place(relpath))

    def _index_glob(self, relpath):
        try:
            data = self._glob_bytes(relpath)
            entries = globfile.parse(data)
        except (OSError, globfile.GlobError):
            return
        stem = "/" + relpath.replace("\\", "/").upper()
        for ent in entries:
            if ent.packed:
                continue          # textures and terrain, never data
            key = "%s/%s" % (stem, ent.name.upper())
            self.files.setdefault(key, File(key, ent.name.upper(), ent.size, []))
            self.files[key].places.append(Place(relpath, ent))

    def _index_umd(self, relpath):
        try:
            data = self._glob_bytes(relpath)
            entries, _footer = umd.parse(data)
        except (OSError, umd.UmdError):
            return
        stem = "/" + relpath.replace("\\", "/").upper()
        for ent in entries:
            if not ent.name.lower().endswith(DATA_SUFFIXES):
                continue
            key = "%s/%s" % (stem, ent.name.replace("\\", "/").upper())
            self.files.setdefault(key, File(key, ent.name.upper(), ent.size, []))
            self.files[key].places.append(Place(relpath, ent, kind="umd"))

    # -- glob bodies, held in memory between read and write ----------------
    def _glob_bytes(self, relpath) -> bytes:
        got = self._glob_cache.get(relpath)
        if got is None:
            with open(os.path.join(self.path, relpath), "rb") as fh:
                got = fh.read()
            self._glob_cache[relpath] = got
        return got

    # -- reading and writing ----------------------------------------------
    def read(self, key) -> bytes:
        f = self.files[key.upper()]
        place = f.places[0]
        if place.packed:
            body = self._glob_bytes(place.relpath)
            mod = umd if place.kind == "umd" else globfile
            return mod.read(body, place.entry)
        with open(os.path.join(self.path, place.relpath), "rb") as fh:
            return fh.read()

    def write(self, key, data: bytes):
        """Write `data` to every copy of this key. Glob copies must keep their
        length; a loose file may change size freely."""
        f = self.files[key.upper()]
        for place in f.places:
            if place.packed:
                body = self._glob_bytes(place.relpath)
                mod = umd if place.kind == "umd" else globfile
                self._glob_cache[place.relpath] = mod.replace(
                    body, place.entry, data)
                self._dirty.add(place.relpath)
            else:
                full = os.path.join(self.path, place.relpath)
                with open(full, "wb") as fh:
                    fh.write(data)
        f.size = len(data)

    def flush(self):
        """Commit every glob that was changed. Loose files are already on disk."""
        for relpath in sorted(self._dirty):
            full = os.path.join(self.path, relpath)
            with open(full, "wb") as fh:
                fh.write(self._glob_cache[relpath])
        n = len(self._dirty)
        self._dirty.clear()
        return n

    # -- convenience -------------------------------------------------------
    def match(self, rx):
        """Keys matching a compiled or string regex, in a stable order."""
        import re
        pat = rx if hasattr(rx, "search") else re.compile(rx, re.I)
        return [k for k in sorted(self.files) if pat.search(k)]

    def has(self, *relpaths) -> bool:
        return all(os.path.exists(os.path.join(self.path, p)) for p in relpaths)

    def find_file(self, *relpaths):
        """The first of these relative paths that exists, or None. Case is
        resolved by listing the directory, because the games' own folders are
        `System` on one disc and `system` on another."""
        for rel in relpaths:
            full = _resolve_case(self.path, rel)
            if full:
                return full
        return None


def _resolve_case(root, rel):
    """`rel` under `root`, matched case-insensitively segment by segment."""
    cur = root
    for part in rel.replace("\\", "/").split("/"):
        if not part:
            continue
        try:
            names = os.listdir(cur)
        except OSError:
            return None
        hit = None
        for n in names:
            if n.lower() == part.lower():
                hit = n
                break
        if hit is None:
            return None
        cur = os.path.join(cur, hit)
    return cur

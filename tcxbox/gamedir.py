"""A game, presented as one flat, keyed namespace -- disc image or folder.

The same games turn up in two shapes on a shelf: as an `.iso` the way they were
ripped, and as a folder someone extracted so an emulator could load it directly.
Both are supported and neither is preferred, because they hold exactly the same
files; a `Source` hides which one is underneath and everything above this line
is written once.

Editing a disc image in place is the better default. Extracting a 4 GB image to
change 2 KB of it is slow, and it leaves two copies of the game that can drift
apart. XDVDFS gives every file a whole number of sectors, so a file can usually
grow into its own padding without anything moving -- see `xiso.replace`.

Keys are upper-case, `/`-separated, and rooted at the game:

    /MISSION/M01_CAVES.MIS                             a loose file
    /GLOBS/IKEDATA.GLB/M01_CAVES.MIS                   the same, in a glob
    /SYSTEM/RAINBOWSIX3XBOX.INI                        loose again
    /SYSTEM/XBOXDYNAMIC.UMD/SYSTEM/R6GAMESETTINGS.INI  inside a bundle

so `\\.MIS$` reaches both copies of a mission, `^/MISSION/` reaches only the
loose one, and `\\.GLB/` reaches only the packed ones. A profile normally wants
the first, and that is the point of indexing them together.

**The same file really does exist more than once.** Ghost Recon's mission XML
sits loose under `mission\\` *and* inside `globs\\ikedata.glb`, byte for byte
identical, while the `.atr` templates those missions name sit only inside the
per-level `*_chars.glb`. Ghost Recon 2 ships its combat model loose and packed.
Rainbow Six 3 and Black Arrow keep their whole real System folder inside
`System\\xboxdynamic.umd`, including a second and *different* copy of
`RainbowSix3Xbox.ini`. Editing the visible copy alone is a reliable way to
produce a mod that does nothing, so `Root.write` writes every copy of a key.

Nothing is held in memory: a container is indexed by walking it with small reads
and an entry is read from its own offset when it is asked for. That is what
keeps opening a 4 GB image off the several hundred megabytes of textures inside
it.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from . import globfile, umd, xiso

#: folders that never hold anything this tool edits. Skipping them is not an
#: optimisation, it is what keeps loading a game off the several hundred
#: megabytes of textures and audio next door.
SKIP_DIRS = {"textures", "sounds", "sound", "videos", "video", "media",
             "maps", "staticmeshes", "animations", "model", "motion",
             "magma", "loadingscreens", "rtx-remix", "save", "dvdextras",
             "voicerec", "havokdata", "karmadata", "refmaps", "cubicmaps",
             "commandmaps", "mapobjects", "rendererdata", "briefings",
             "stream", "preload", "uix", "shaders", "binary"}

#: extensions worth indexing loose. Everything this tool edits is text.
DATA_SUFFIXES = (".mis", ".atr", ".gun", ".kit", ".wsf", ".gtf", ".ass",
                 ".cgs", ".cms", ".prj", ".itm", ".vcl", ".env", ".ini",
                 ".tpt", ".xml", ".kil")

#: containers whose members are indexed alongside the loose files
GLOB_SUFFIX = ".glb"
BUNDLE_SUFFIX = ".umd"


class RootError(Exception):
    pass


# ---------------------------------------------------------------------------
# the two shapes a game comes in
# ---------------------------------------------------------------------------

class DirSource:
    """An extracted game folder."""

    kind = "folder"

    def __init__(self, path, writable=False):
        self.path = os.path.abspath(str(path))
        self.name = os.path.basename(self.path)
        self.writable = writable

    def close(self):
        pass

    def flush(self):
        pass

    def iter_files(self):
        for dirpath, dirnames, filenames in os.walk(self.path):
            rel = os.path.relpath(dirpath, self.path)
            rel = "" if rel == "." else rel
            dirnames[:] = [d for d in dirnames
                           if d.lower() not in SKIP_DIRS and not d.startswith(".")]
            for name in filenames:
                relpath = os.path.join(rel, name) if rel else name
                yield relpath, os.path.getsize(os.path.join(self.path, relpath))

    def read(self, relpath, offset=0, length=None):
        with open(os.path.join(self.path, relpath), "rb") as fh:
            if offset:
                fh.seek(offset)
            return fh.read() if length is None else fh.read(length)

    def write(self, relpath, offset, data):
        with open(os.path.join(self.path, relpath), "r+b") as fh:
            fh.seek(offset)
            fh.write(data)

    def replace(self, relpath, data):
        with open(os.path.join(self.path, relpath), "wb") as fh:
            fh.write(data)

    def resolve(self, relpath):
        """`relpath` under this game, matched case-insensitively segment by
        segment, or None. The games are not consistent about it -- `System` on
        one disc and `system` on another."""
        cur = self.path
        for part in relpath.replace("\\", "/").split("/"):
            if not part:
                continue
            try:
                names = os.listdir(cur)
            except OSError:
                return None
            hit = next((n for n in names if n.lower() == part.lower()), None)
            if hit is None:
                return None
            cur = os.path.join(cur, hit)
        return os.path.relpath(cur, self.path)


class IsoSource:
    """An Xbox disc image, read and written in place."""

    kind = "iso"

    def __init__(self, path, writable=False):
        self.path = os.path.abspath(str(path))
        self.name = os.path.basename(self.path)
        self.writable = writable
        self.iso = xiso.Xiso(self.path, writable=writable)

    def close(self):
        self.iso.close()

    def flush(self):
        self.iso.flush()

    def iter_files(self):
        for key, entry in self.iso.files.items():
            if entry.directory:
                continue
            parts = key.strip("/").split("/")
            if any(p.lower() in SKIP_DIRS for p in parts[:-1]):
                continue
            yield entry.path.lstrip("/"), entry.size

    def _entry(self, relpath):
        key = "/" + relpath.replace("\\", "/").upper()
        entry = self.iso.files.get(key)
        if entry is None:
            raise RootError("%s is not on this disc" % relpath)
        return entry

    def read(self, relpath, offset=0, length=None):
        return self.iso.read(self._entry(relpath), offset, length)

    def write(self, relpath, offset, data):
        self.iso.write(self._entry(relpath), offset, data)

    def replace(self, relpath, data):
        self.iso.replace(self._entry(relpath), data)

    def resolve(self, relpath):
        key = "/" + relpath.replace("\\", "/").upper()
        entry = self.iso.files.get(key)
        return entry.path.lstrip("/") if entry else None


def open_source(path, writable=False):
    """Whichever kind of game this path is."""
    path = str(path)
    if os.path.isdir(path):
        return DirSource(path, writable)
    if os.path.isfile(path):
        return IsoSource(path, writable)
    raise RootError("%s is neither a folder nor a file" % path)


# ---------------------------------------------------------------------------
# the index
# ---------------------------------------------------------------------------

@dataclass
class Place:
    """One physical copy of a file: where to read and write its bytes."""
    relpath: str                 # the loose file, or the container holding it
    offset: int = 0
    size: int = 0
    packed: bool = False         # inside a glob or a bundle, so fixed length


@dataclass
class File:
    key: str
    name: str
    size: int
    places: list = field(default_factory=list)


class Root:
    """A game, indexed once and then addressed by key."""

    def __init__(self, path=None, writable=False, index_containers=True,
                 source=None):
        self.source = source if source is not None else open_source(path, writable)
        self.path = self.source.path
        self.name = self.source.name
        self.kind = self.source.kind
        self.files = {}
        self._index(index_containers)

    def close(self):
        self.source.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    # -- building ----------------------------------------------------------
    def _index(self, index_containers):
        for relpath, size in self.source.iter_files():
            low = relpath.lower()
            if low.endswith(GLOB_SUFFIX):
                if index_containers:
                    self._index_glob(relpath, size)
                continue
            if low.endswith(BUNDLE_SUFFIX):
                if index_containers:
                    self._index_umd(relpath, size)
                continue
            if not low.endswith(DATA_SUFFIXES):
                continue
            self._add("/" + relpath.replace("\\", "/").upper(),
                      os.path.basename(relpath).upper(),
                      Place(relpath, 0, size, False))

    def _add(self, key, name, place):
        f = self.files.get(key)
        if f is None:
            f = self.files[key] = File(key, name, place.size, [])
        f.places.append(place)

    def _reader(self, relpath):
        return lambda off, n: self.source.read(relpath, off, n)

    def _index_glob(self, relpath, size):
        try:
            entries = globfile.parse_stream(self._reader(relpath), size)
        except (OSError, RootError, globfile.GlobError):
            return
        stem = "/" + relpath.replace("\\", "/").upper()
        for ent in entries:
            if ent.packed:
                continue          # textures and terrain, never data
            self._add("%s/%s" % (stem, ent.name.upper()), ent.name.upper(),
                      Place(relpath, ent.offset, ent.size, True))

    def _index_umd(self, relpath, size):
        try:
            entries = umd.parse_stream(self._reader(relpath), size)
        except (OSError, RootError, umd.UmdError):
            return
        stem = "/" + relpath.replace("\\", "/").upper()
        for ent in entries:
            if not ent.name.lower().endswith(DATA_SUFFIXES):
                continue
            key = "%s/%s" % (stem, ent.name.replace("\\", "/").upper())
            self._add(key,
                      os.path.basename(ent.name.replace("\\", "/")).upper(),
                      Place(relpath, ent.offset, ent.size, True))

    # -- reading and writing ----------------------------------------------
    def read(self, key) -> bytes:
        place = self.files[key.upper()].places[0]
        return self.source.read(place.relpath, place.offset, place.size)

    def write(self, key, data: bytes):
        """Write `data` to every copy of this key.

        A packed copy must keep its length -- a glob has no index at all, and a
        bundle's would have to be relaid. A loose copy may change size: in a
        folder it is simply rewritten, and on a disc image it can grow into the
        sector padding XDVDFS already gave it.
        """
        f = self.files[key.upper()]
        for place in f.places:
            if place.packed:
                if len(data) != place.size:
                    raise RootError(
                        "%s: %d bytes cannot replace %d inside %s, whose "
                        "entries have no index to relocate them with"
                        % (f.name, len(data), place.size, place.relpath))
                self.source.write(place.relpath, place.offset, data)
            else:
                self.source.replace(place.relpath, data)
                place.size = len(data)
        f.size = len(data)

    def flush(self):
        self.source.flush()
        return 0

    # -- convenience -------------------------------------------------------
    def match(self, rx):
        """Keys matching a regex, in a stable order."""
        pat = rx if hasattr(rx, "search") else re.compile(rx, re.I)
        return [k for k in sorted(self.files) if pat.search(k)]

    def packed(self, key) -> bool:
        """True when any copy of this file lives in a fixed slot."""
        return any(p.packed for p in self.files[key.upper()].places)

    def has(self, *relpaths) -> bool:
        return all(self.source.resolve(p) for p in relpaths)

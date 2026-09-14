"""Applying and undoing edits to data files inside a game's own archives.

The archive is a read-only filesystem with an explicit offset and size per
entry, so a file can be replaced in place when it fits and relocated into free
space when it does not. Every archive here ends with 64 KB of zero padding, and
relocating a file releases its old run back into the pool, so in practice the
first file edited takes the pad and the rest recycle each other's slots -- the
whole of Ghost Recon's 25 wave-bearing missions cost 2.4 KB of the 64.

Originals are copied into a sidecar folder beside the ISO before the first
change, with their offsets, so undoing puts each file back at the exact byte it
came from.
"""

from __future__ import annotations

import json
import os

from . import rselzo, transforms
from .vokes import Vokes, VokesError, open_archives

MANIFEST = "data-edits.json"


class DataEditError(Exception):
    pass


# ---------------------------------------------------------------------------
# the named operations a profile can ask for
# ---------------------------------------------------------------------------

def _op_strip_difficulty(plain, params):
    return transforms.strip_difficulty(plain, params.get("which",
                                                         ("Easy", "Normal", "Hard")))


def _op_reveal_hidden(plain, params):
    return transforms.reveal_hidden(plain)


def _op_bump_tier(plain, params):
    return transforms.bump_enemy_tier(plain, int(params.get("steps", 1)))


def _op_bump_stats(plain, params):
    return transforms.bump_atr_stats(plain, int(params.get("steps", 1)),
                                     stats=params.get("stats", transforms.ATR_STATS))


def _op_gtf_variables(plain, params):
    return transforms.set_gtf_variables(plain, params.get("values", {}))


OPS = {
    "strip_difficulty": _op_strip_difficulty,
    "reveal_hidden": _op_reveal_hidden,
    "bump_tier": _op_bump_tier,
    "bump_stats": _op_bump_stats,
    "gtf_variables": _op_gtf_variables,
}


# ---------------------------------------------------------------------------
# backup store
# ---------------------------------------------------------------------------

class Store:
    """Original bytes and offsets for every archive file we have touched."""

    def __init__(self, folder):
        self.folder = folder
        self.path = os.path.join(folder, MANIFEST)
        self.index = {}
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as fh:
                    self.index = json.load(fh)
            except (OSError, ValueError):
                self.index = {}

    def _blob(self, key):
        safe = key.replace("/", "__").replace("\\", "__").replace(":", "_")
        return os.path.join(self.folder, "orig", safe)

    def remember(self, archive, path, data, offset):
        key = "%s%s" % (archive, path)
        if key in self.index:
            return
        blob = self._blob(key)
        os.makedirs(os.path.dirname(blob), exist_ok=True)
        with open(blob, "wb") as fh:
            fh.write(data)
        self.index[key] = {"archive": archive, "path": path,
                           "offset": offset, "size": len(data)}
        self.save()

    def original(self, archive, path):
        key = "%s%s" % (archive, path)
        rec = self.index.get(key)
        if rec is None:
            return None
        try:
            with open(self._blob(key), "rb") as fh:
                return fh.read(), rec["offset"]
        except OSError:
            return None

    def entries(self):
        return list(self.index.values())

    def save(self):
        os.makedirs(self.folder, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self.index, fh, indent=1)

    def forget_all(self):
        self.index = {}
        self.save()


# ---------------------------------------------------------------------------
# apply / revert
# ---------------------------------------------------------------------------

def enemy_template_set(arc):
    """The `.atr` files any mission hands to a non-allied company.

    Both games keep the two sets completely disjoint -- 568 enemy templates
    against 17 other in Ghost Recon, 274 against 24 in Jungle Storm, with zero
    overlap -- so scoping a skill edit this way is exact, not approximate.
    """
    names = set()
    for key, ent in arc.files.items():
        if not key.endswith(".MIS"):
            continue
        try:
            plain = rselzo.unpack(arc.read_entry(ent))
        except Exception:                       # noqa: BLE001
            continue
        names |= transforms.enemy_templates(plain)
    return {("/" + n).upper() for n in names}


def _scope_filter(arc, edit, cache):
    if edit.scope != "enemy_templates":
        return None
    if arc.r.name not in cache:
        cache[arc.r.name] = enemy_template_set(arc)
    allowed = cache[arc.r.name]
    return lambda key: key.upper() in allowed


def _archives(iso, profile):
    out = {}
    for arc in open_archives(iso, profile.archive_pattern or
                             r"/(VOKES\d|GR|MENU)\.IMG$"):
        out[arc.r.name.upper()] = arc
    return out


def plan_data(iso, profile, edits, store):
    """What the edits would rewrite, without touching anything."""
    rows = []
    arcs = _archives(iso, profile)
    for edit in edits:
        for arc_name, arc in arcs.items():
            if edit.archive and edit.archive.upper() not in arc_name:
                continue
            for key, ent in sorted(arc.files.items()):
                if not edit.matches(key):
                    continue
                rows.append((arc_name, ent.path, edit))
    return rows


def apply_data(iso, profile, edits, store, progress=None, selector=None):
    """Run every edit. Files are written largest first, because the one big
    mission has to land in the 64 KB pad before smaller ones nibble at it."""
    arcs = _archives(iso, profile)
    pending = {}          # (arcName, path) -> (arc, entry, plainBytes)
    counts = {}
    scopes = {}

    def say(msg):
        if progress:
            progress(msg)

    for edit in edits:
        op = OPS.get(edit.op)
        if op is None:
            raise DataEditError("unknown data operation %r" % edit.op)
        for arc_name, arc in arcs.items():
            if edit.archive and edit.archive.upper() not in arc_name:
                continue
            allowed = _scope_filter(arc, edit, scopes)
            for key, ent in sorted(arc.files.items()):
                if not edit.matches(key):
                    continue
                if allowed and not allowed(key):
                    continue
                if selector and not selector(key):
                    continue
                slot = (arc_name, ent.path)
                if slot in pending:
                    _a, _e, plain = pending[slot]
                else:
                    original = arc.read_entry(ent)
                    store.remember(arc_name, ent.path, original, ent.offset)
                    plain = rselzo.unpack(original)
                new, n = op(plain, edit.params)
                if len(new) != len(plain):
                    raise DataEditError(
                        "%s: %s changed the file length, which would move every "
                        "chunk boundary" % (ent.path, edit.op))
                if n:
                    counts[edit.op] = counts.get(edit.op, 0) + n
                pending[slot] = (arc, ent, new)

    # write, biggest first
    built = []
    for (arc_name, path), (arc, ent, plain) in pending.items():
        original = store.original(arc_name, path)
        source = original[0] if original else arc.read_entry(ent)
        if rselzo.unpack(source) == plain:
            continue                       # nothing actually changed
        packed = rselzo.repack(source, plain) if rselzo.is_compressed(source) else plain
        built.append((len(packed), arc, ent, packed))
    built.sort(key=lambda r: -r[0])

    written = 0
    for size, arc, ent, packed in built:
        try:
            arc.write(ent.path, packed)
        except VokesError as exc:
            raise DataEditError("%s: %s" % (ent.path, exc)) from exc
        written += 1
        if written % 10 == 0:
            say("  %d of %d data files rewritten" % (written, len(built)))
    if built:
        say("Rewrote %d data file%s" % (written, "" if written == 1 else "s"))
    return {"files": written, "changes": counts}


def revert_data(iso, profile, store, progress=None):
    """Put every remembered file back, at the offset it came from."""
    arcs = _archives(iso, profile)
    done = 0
    for rec in store.entries():
        arc = arcs.get(rec["archive"].upper())
        if arc is None:
            continue
        got = store.original(rec["archive"], rec["path"])
        if got is None:
            continue
        data, offset = got
        ent = arc.files.get(rec["path"].upper())
        if ent is None:
            continue
        # clear wherever it sits now, then put it back exactly where it was
        if ent.offset != offset:
            arc.r.write(ent.offset, b"\x00" * ent.size)
        arc.r.write(offset, data)
        arc._set_entry(ent, offset, len(data))
        done += 1
        if progress and done % 10 == 0:
            progress("  %d files restored" % done)
    store.forget_all()
    return {"files": done}


def verify_data(iso, profile, store):
    """Read back every file we touched and confirm it still decodes."""
    arcs = _archives(iso, profile)
    ok = bad = 0
    for rec in store.entries():
        arc = arcs.get(rec["archive"].upper())
        ent = arc.files.get(rec["path"].upper()) if arc else None
        if ent is None:
            bad += 1
            continue
        try:
            rselzo.unpack(arc.read_entry(ent))
            ok += 1
        except Exception:                       # noqa: BLE001
            bad += 1
    return ok, bad

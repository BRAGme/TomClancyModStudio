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

from . import lin, rselzo, transforms
from .vokes import Vokes, VokesError, open_archives

MANIFEST = "data-edits.json"

#: A file at least this big is named in the log on its own, because packing it
#: is where the seconds go. COMMON.LIN's payload is 5 MB; a map INI is 3 KB.
_CHATTY_BYTES = 256 * 1024


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


def _op_scale_ballistics(plain, params):
    return transforms.scale_xml_floats(plain, float(params.get("factor", 1.0)))


def _op_scale_xml(plain, params):
    return transforms.scale_xml_floats(
        plain, float(params.get("factor", 1.0)),
        prefix=params.get("prefix", "").encode("latin1"),
        keep_width=bool(params.get("keep_width", True)))


def _op_xml_values(plain, params):
    return transforms.set_xml_values(plain, params.get("values", {}))


def _op_nimitz_skills(plain, params):
    return transforms.bump_nimitz_skills(
        plain, int(params.get("steps", 0)),
        hostile_only=bool(params.get("hostile_only", True)),
        only=params.get("only"))


def _op_nimitz_guns(plain, params):
    return transforms.scale_nimitz_guns(plain,
                                        mag=float(params.get("mag", 1.0)),
                                        rpm=float(params.get("rpm", 1.0)),
                                        only=params.get("only"))


def _op_scale_gun(plain, params):
    from . import rseguns
    return rseguns.scale(plain, params)


def _op_gtf_variables(plain, params):
    return transforms.set_gtf_variables(plain, params.get("values", {}))


def _op_ini_values(plain, params):
    return transforms.set_ini_values(plain, params.get("values", {}))


def _op_grenade_carry(plain, params):
    return transforms.set_grenade_carry(plain, params.get("percent", 20))


def _op_split_wheel(plain, params):
    from . import rsewheel
    # Also put back the byte the withdrawn first attempt changed. It is dead
    # code either way, but a disc still carrying it would make a later
    # stock-vs-disc diff report an edit this tool no longer makes.
    plain, undone = rsewheel.undo_first_attempt(plain)
    plain, n = rsewheel.restore(plain, bool(params.get("enable", True)))
    return plain, n + undone


def _op_rpg_speed(plain, params):
    from . import rserpg
    return rserpg.apply(plain, int(params.get("speed", 1)))


def _op_split_draw(plain, params):
    from . import rsedraw
    return rsedraw.restore(plain, bool(params.get("enable", True)))


def _op_split_cycle(plain, params):
    from . import rsewheel
    return rsewheel.cycle_restore(plain, bool(params.get("enable", True)))


def _op_canon_team(plain, params):
    from . import rsecanon
    return rsecanon.apply(plain, bool(params.get("enable", True)))


def _op_ss_chatter(plain, params):
    from . import rsechatter
    return rsechatter.apply(plain, int(params.get("chance", 0)),
                            bool(params.get("hostage", True)))


def _op_ss_man_down(plain, params):
    from . import rsemandown
    return rsemandown.apply(plain, bool(params.get("enable", True)))


def _op_frag_warning(plain, params):
    from . import rsefragwarn
    return rsefragwarn.apply(plain, bool(params.get("enable", True)))


def _op_ai_cover(plain, params):
    from . import rseaicover
    return rseaicover.apply(plain, str(params.get("set", "stock")))


def _op_ai_sidearm(plain, params):
    from . import rsesidearm
    return rsesidearm.apply(plain, int(params.get("chance", 0)),
                            bool(params.get("in_contact", True)),
                            int(params.get("say_chance", 0)))


def _op_enemy_loadout(plain, params, container=None):
    from . import rseloadout
    mark = params.get("marksmanship")
    mark = None if mark in (None, "", "stock") else int(mark)
    mode = params.get("weapons", "stock")
    # Applied to the plain bytes FIRST, so that when a container is present the
    # fitter measures the text that will actually be written. It is one digit
    # for one digit, so it cannot change the length -- but it does change what
    # deflates, and the chunk check has to see the real thing.
    torch = params.get("flashlight")
    extra = 0
    if torch is not None:
        plain, extra = rseloadout.set_gadget_share(plain, "Flashlight", torch)
    if container is None:
        # No container to measure against, so take the edit at full strength
        # and let the caller's own length check speak. Tests use this path.
        new, stats = rseloadout.retune(plain, weapons=mode, marksmanship=mark)
    else:
        new, stats = rseloadout.fit_to_lin(container, plain, weapons=mode,
                                           marksmanship=mark)
    return new, stats["weapons"] + stats["skills"] + extra


#: Ops that want the file's original container bytes as a third argument,
#: because what they may write depends on what will still deflate into it.
_WANTS_CONTAINER = {"enemy_loadout"}


def _op_zone_counts(plain, params):
    from . import r6zones
    return r6zones.scale(plain, float(params.get("factor", 1.0)))[0]


def _op_team_gadget(plain, params):
    from . import rsekits
    return rsekits.apply(plain, params.get("primary", "stock"),
                         params.get("secondary", "stock"),
                         bool(params.get("match", False)),
                         params.get("per") or {})


def _op_ws_slot(plain, params):
    return transforms.set_ws_slot(plain, int(params["slot"]),
                                  bool(params.get("using", True)))


OPS = {
    "strip_difficulty": _op_strip_difficulty,
    "reveal_hidden": _op_reveal_hidden,
    "bump_tier": _op_bump_tier,
    "bump_stats": _op_bump_stats,
    "gtf_variables": _op_gtf_variables,
    "ini_values": _op_ini_values,
    "team_gadget": _op_team_gadget,
    "ws_slot": _op_ws_slot,
    "grenade_carry": _op_grenade_carry,
    "enemy_loadout": _op_enemy_loadout,
    "split_wheel": _op_split_wheel,
    "ai_sidearm": _op_ai_sidearm,
    "ai_cover": _op_ai_cover,
    "frag_warning": _op_frag_warning,
    "ss_man_down": _op_ss_man_down,
    "ss_chatter": _op_ss_chatter,
    "canon_team": _op_canon_team,
    "split_cycle": _op_split_cycle,
    "split_draw": _op_split_draw,
    "rpg_speed": _op_rpg_speed,
    "scale_ballistics": _op_scale_ballistics,
    "scale_xml": _op_scale_xml,
    "xml_values": _op_xml_values,
    "nimitz_skills": _op_nimitz_skills,
    "nimitz_guns": _op_nimitz_guns,
    "zone_counts": _op_zone_counts,
    "scale_gun": _op_scale_gun,
}


# ---------------------------------------------------------------------------
# containers
# ---------------------------------------------------------------------------

#: files that are raw binary and must never be run through a container sniffer
_RAW_SUFFIXES = (".GUNS", ".CGSB", ".PROJS", ".ITEMS", ".PROS", ".WSFB",
                 ".CMSB", ".CGSB", ".ACMS", ".MISSIONS")


def _unpack(original, path=""):
    """(kind, plainBytes) for whichever container this file uses."""
    if path and path.upper().endswith(_RAW_SUFFIXES):
        return "plain", original
    if lin.is_lin(original):
        return "lin", lin.decompress(original)
    if rselzo.is_compressed(original):
        return "rselzo", rselzo.decompress(original)
    return "plain", original


def _repack(kind, original, plain):
    if kind == "lin":
        # `substitute` is still the better path when the payload happens to be
        # the same length: it re-deflates only the chunks that changed and
        # leaves the container's own length alone, so the archive entry never
        # has to move. When an edit genuinely grows a package -- which is
        # allowed, see `lin.rebuild` -- the whole chain is rebuilt instead.
        # That usually comes out SMALLER anyway, because deflating at level 9
        # beats the packer the disc shipped with.
        if len(plain) == len(lin.decompress(original)):
            return lin.substitute(original, lambda _old: plain)[0]
        _parts, tail = lin.parse(original)
        return lin.rebuild(plain, tail)
    if kind == "rselzo":
        return rselzo.repack(original, plain)
    return plain



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
            _kind, plain = _unpack(arc.read_entry(ent), ent.path)
        except Exception:                       # noqa: BLE001
            continue
        names |= transforms.enemy_templates(plain)
    return {("/" + n).upper() for n in names}


#: how a gun edit is aimed. `rseguns.sides` returns three sets; a weapon that
#: both sides carry is in neither of these, deliberately -- one file cannot be
#: two weapons, so neither dial touches it.
GUN_SCOPES = {"ally_guns": 0, "enemy_guns": 1}


def gun_scope_set(arcs, which):
    """The archive paths of one side's `.gun` files.

    Spanning EVERY archive matters: The Sum of All Fears keeps its weapons in
    one and part of its kit and mission data in another, so working one archive
    at a time sees no missions and decides every gun belongs to nobody.
    """
    from . import rseguns
    files = {}
    for arc in arcs:
        for key, entry in arc.files.items():
            files.setdefault(key.upper(), (arc, entry))
    picked = rseguns.sides(files)[GUN_SCOPES[which]]
    return {("/" + n).upper() for n in picked}


def _scope_filter(arc, edit, cache, arcs=None):
    if edit.scope in GUN_SCOPES:
        if edit.scope not in cache:
            cache[edit.scope] = gun_scope_set(arcs or [arc], edit.scope)
        allowed = cache[edit.scope]
        return lambda k: k.upper() in allowed
    if edit.scope != "enemy_templates":
        return None
    if arc.r.name not in cache:
        cache[arc.r.name] = enemy_template_set(arc)
    allowed = cache[arc.r.name]
    return lambda key: key.upper() in allowed


def _archives(iso, profile):
    """Every archive this profile edits, keyed by name.

    Lockdown's container is a different format entirely, but it presents the
    same handful of methods, so everything downstream -- the backup store, the
    relocation check, verify and revert -- runs unchanged.
    """
    # A loose data root answers this one question for itself, which is all it
    # takes for every edit below -- and the backup store, verify and revert --
    # to run against a folder instead of a disc image.
    if hasattr(iso, "loose_archives"):
        return iso.loose_archives(profile)
    out = {}
    if getattr(profile, "archive_kind", "vokes") == "nimitz":
        from .nimitz import open_pak
        for arc in open_pak(iso):
            out[arc.r.name.upper()] = arc
        return out
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


def apply_data(iso, profile, edits, store, progress=None, selector=None,
               tick=None):
    """Run every edit. Files are written largest first, because the one big
    mission has to land in the 64 KB pad before smaller ones nibble at it.

    `tick(done, total)` is for a progress bar. `total` is None during the
    first half, because which files an edit matches is only known as the
    match is made -- so the caller should show that half as indeterminate and
    the second half, which knows its own length, as a real fraction.
    """
    arcs = _archives(iso, profile)
    pending = {}          # (arcName, path) -> (arc, entry, plainBytes)
    counts = {}
    scopes = {}

    def say(msg):
        if progress:
            progress(msg)

    def beat(done, total=None):
        if tick:
            tick(done, total)

    for edit in edits:
        op = OPS.get(edit.op)
        if op is None:
            raise DataEditError("unknown data operation %r" % edit.op)
        for arc_name, arc in arcs.items():
            if edit.archive and edit.archive.upper() not in arc_name:
                continue
            allowed = _scope_filter(arc, edit, scopes,
                                    list(arcs.values()))
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
                    # Edits are applied to the bytes the game SHIPPED, not to
                    # whatever is on the disc now. The settings page describes
                    # a destination, not a diff: applying twice must give the
                    # same disc, and moving a setting back to its default must
                    # actually undo it. Reading the live file instead makes
                    # edits compound -- a weapon already swapped once gets
                    # swapped again -- and leaves no way back short of a full
                    # restore.
                    stored = store.original(arc_name, ent.path)
                    base = stored[0] if stored else original
                    _kind, plain = _unpack(base, ent.path)
                if len(plain) >= _CHATTY_BYTES:
                    say("  editing %s" % ent.path)
                beat(len(pending) + 1)
                if edit.op in _WANTS_CONTAINER:
                    stored = store.original(arc_name, ent.path)
                    container = stored[0] if stored else arc.read_entry(ent)
                    new, n = op(plain, edit.params, container)
                else:
                    new, n = op(plain, edit.params)
                # Only a compressed container has to keep its length. A LIN's
                # packages carry relaid offsets and an rselzo chunk chain has
                # fixed boundaries, so either would be corrupted by a size
                # change; a plain-text INI can grow or shrink freely, because
                # the archive writer will relocate it.
                kind, _ = _unpack(arc.read_entry(ent), ent.path)
                if len(new) != len(plain) and kind != "plain":
                    raise DataEditError(
                        "%s: %s changed the file length, which a %s container "
                        "cannot survive" % (ent.path, edit.op, kind))
                if n:
                    counts[edit.op] = counts.get(edit.op, 0) + n
                pending[slot] = (arc, ent, new)

    # Anything an earlier run edited that this one does not want back.
    #
    # `pending` is the whole of what the current settings ask for, so a file the
    # store remembers and `pending` does not name is a leftover from a setting
    # that has since been switched off. The loop above cannot see it: it walks
    # the edits, and a setting at its default produces no edit, so the file is
    # never visited and its modified bytes stay on the disc. That breaks the
    # promise the comment above makes -- moving a setting back to its default
    # must actually undo it -- and it breaks it silently, because `verify_data`
    # only asks whether the file still decodes, which a leftover edit does.
    restored = 0
    if selector is None:
        for rec in store.entries():
            arc = arcs.get(rec["archive"].upper())
            if arc is None:
                continue
            ent = arc.files.get(rec["path"].upper())
            if ent is None or (rec["archive"], ent.path) in pending:
                continue
            got = store.original(rec["archive"], rec["path"])
            if got is None:
                continue
            data, offset = got
            if ent.offset == offset and arc.read_entry(ent) == data:
                continue                   # already stock, nothing to undo
            if ent.offset != offset:
                arc.r.write(ent.offset, b"\x00" * ent.size)
            arc.r.write(offset, data)
            arc._set_entry(ent, offset, len(data))
            restored += 1
        if restored:
            say("Put back %d file%s an earlier run had edited"
                % (restored, "" if restored == 1 else "s"))

    # write, biggest first
    #
    # Everything below this line used to happen in silence, and re-deflating a
    # 5 MB script package at maximum effort takes long enough that the log
    # looked identical to a hang -- which is exactly how it was read. So say
    # what is in flight BEFORE starting on it, not after finishing: a line
    # that appears once the slow part is over is no use to anyone watching.
    built, put_back = [], 0
    total = len(pending)
    if total:
        say("  %d file%s to rebuild" % (total, "" if total == 1 else "s"))
    for n, ((arc_name, path), (arc, ent, plain)) in enumerate(
            pending.items(), 1):
        beat(n - 1, total)
        if len(plain) >= _CHATTY_BYTES or n % 25 == 0 or n == total:
            say("  packing %d/%d (%d%%)  %s"
                % (n, total, (n - 1) * 100 // total, path))
        original = store.original(arc_name, path)
        source = original[0] if original else arc.read_entry(ent)
        kind, was = _unpack(source, path)
        if was == plain:
            # The settings ask for the stock file. That is not the same as
            # "nothing to do": an earlier run may have written an edit here,
            # and `was`/`plain` are both computed from the STORED ORIGINAL, so
            # they agree with each other while disagreeing with the disc. Put
            # the original bytes back rather than re-pack them -- a LIN does
            # not deflate to the same bytes twice, so re-packing would be a
            # gratuitous rewrite that cannot even be checked for equality.
            if original and arc.read_entry(ent) != original[0]:
                built.append((len(original[0]), arc, ent, original[0],
                              (original[1], len(original[0]))))
                put_back += 1
            continue
        packed = _repack(kind, source, plain)
        # The offset the file SHIPPED at. An edit that makes a file bigger than
        # its slot has to relocate it, and a single byte is enough; passing home
        # through means the next edit that fits puts it back, instead of leaving
        # it wherever the first overflow landed.
        built.append((len(packed), arc, ent, packed,
                      (original[1], len(original[0])) if original else None))
    built.sort(key=lambda r: -r[0])

    written = 0
    for size, arc, ent, packed, home in built:
        try:
            arc.write(ent.path, packed, home=home)
        except VokesError as exc:
            raise DataEditError("%s: %s" % (ent.path, exc)) from exc
        written += 1
        if written % 10 == 0:
            say("  %d of %d data files rewritten" % (written, len(built)))
    beat(total, total)
    if built:
        say("Rewrote %d data file%s" % (written, "" if written == 1 else "s"))
    return {"files": written - put_back, "restored": restored + put_back,
            "changes": counts}


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
            _unpack(arc.read_entry(ent), ent.path)
            ok += 1
        except Exception:                       # noqa: BLE001
            bad += 1
    return ok, bad

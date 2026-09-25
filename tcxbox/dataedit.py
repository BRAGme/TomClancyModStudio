"""Applying and undoing edits to the files in an extracted game folder.

The shape is the same as the PS2 tool's: a profile hands over a list of
`FileEdit`s, each naming a transform and a regex over the folder's keys, and
this module runs them, remembers every original, and can put them all back.

Two things are different, and both make it safer.

**There is no archive to relocate inside.** A loose file is written straight to
disk, or into its own sectors on a disc image; a glob member or a `.umd` slot is
written in place at the byte it already occupies. So there is no free-space pool
to exhaust and no entry that can end up pointing somewhere else. The cost is
that a file in a fixed slot must keep its length -- and that is checked per key,
not globally, which is what lets the `.ASS` server scripts, which exist only
loose in every one of these games, be rewritten with values of a different
width.

**A logical file may live in more than one place.** `gamedir.Root` keys loose
copies and packed copies separately but `Root.write` writes all the copies of a
key, so the loose `mission\\m01_caves.mis` and the copy inside `ikedata.glb`
cannot drift apart.

Originals go into a sidecar folder beside the game -- next to the disc image or
next to the extracted folder -- before the first change, so undoing puts every
file back byte for byte a month later.
"""

from __future__ import annotations

import json
import os

from . import rseguns, transforms

MANIFEST = "data-edits.json"

#: A file at least this big is named in the log on its own, because packing it
#: is where the seconds go. A .LIN runs to megabytes; a config file is a few KB.
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


def _op_xml_text(plain, params):
    return transforms.set_xml_text(plain, params.get("values", {}))


def _op_scale_xml(plain, params):
    return transforms.scale_xml_floats(
        plain, float(params.get("factor", 1.0)),
        prefix=params.get("prefix", "").encode("latin1"),
        keep_width=bool(params.get("keep_width", True)))


def _op_xml_values(plain, params):
    return transforms.set_xml_values(plain, params.get("values", {}))


def _op_gtf_variables(plain, params):
    return transforms.set_gtf_variables(plain, params.get("values", {}))


def _op_hunt_scale(plain, params):
    from . import hunt
    try:
        return hunt.scale(plain, float(params.get("factor", 1.0)))
    except hunt.HuntError as exc:
        raise DataEditError(str(exc)) from exc


def _op_coop_team(plain, _params):
    from . import coopteam
    return coopteam.open_to_system_link(plain)


def _op_show_log(plain, _params):
    from . import showlog
    return showlog.force_on(plain)


def _op_reach_probe(plain, _params):
    from . import showlog
    return showlog.force_probes(plain)


def _op_campaign(plain, params):
    return transforms.extend_campaign(plain, params.get("add", ()),
                                      replace=bool(params.get("replace")))


def _op_ini_values(plain, params):
    return transforms.set_ini_values(plain, params.get("values", {}))


def _op_scale_ini(plain, params):
    return transforms.scale_ini_values(plain, params.get("factors", {}))


def _op_tpt_values(plain, params):
    return transforms.set_tpt_values(plain, params.get("values", {}),
                                     scale=params.get("scale"))


def _op_grenade_carry(plain, params):
    return transforms.set_grenade_carry(plain, params.get("percent", 20))


def _op_scale_gun(plain, params):
    return rseguns.scale(plain, params)


def _op_ai_sidearm(raw, params):
    """The teammate reload/sidearm roll, inside a cooked Unreal package.

    This is the one op that is not text, and the one that has to look at its
    own container: Rainbow Six 3 keeps the function in `System\\Common.lin`,
    which is zlib-chunked, AND in `System\\R6Engine.u` inside
    `System\\xboxufiles.umd`, which is not. Both are length-preserving either
    way -- the script edit pays for itself out of a dead log line, and `lin`
    re-packs into the same container extent.
    """
    from . import lin, rsesidearm
    if lin.is_lin(raw):
        plain = lin.decompress(raw)
        new, n = rsesidearm.apply(plain, int(params.get("chance", 0)),
                                  bool(params.get("in_contact", True)),
                                  int(params.get("say_chance", 0)))
        if not n:
            return raw, 0
        return lin.substitute(raw, lambda _old: new)[0], n
    return rsesidearm.apply(raw, int(params.get("chance", 0)),
                            bool(params.get("in_contact", True)),
                            int(params.get("say_chance", 0)))


OPS = {
    "ai_sidearm": _op_ai_sidearm,
    "strip_difficulty": _op_strip_difficulty,
    "reveal_hidden": _op_reveal_hidden,
    "bump_tier": _op_bump_tier,
    "bump_stats": _op_bump_stats,
    "gtf_variables": _op_gtf_variables,
    "campaign": _op_campaign,
    "coop_team": _op_coop_team,
    "show_log": _op_show_log,
    "reach_probe": _op_reach_probe,
    "hunt_scale": _op_hunt_scale,
    "ini_values": _op_ini_values,
    "scale_ini": _op_scale_ini,
    "tpt_values": _op_tpt_values,
    "grenade_carry": _op_grenade_carry,
    "scale_ballistics": _op_scale_ballistics,
    "scale_xml": _op_scale_xml,
    "xml_text": _op_xml_text,
    "xml_values": _op_xml_values,
    "scale_gun": _op_scale_gun,
}


# ---------------------------------------------------------------------------
# scopes -- narrowing an edit to one side of the war
# ---------------------------------------------------------------------------

class _View:
    """`rseguns` and `transforms` were written against the PS2 archive's
    (archive, entry) pair. A Root key is both, so this is the whole adapter."""

    def __init__(self, root):
        self.root = root

    def read_entry(self, key):
        return self.root.read(key)


def enemy_template_set(root):
    """The `.atr` files a mission hands to a non-allied company.

    Ghost Recon and Island Thunder keep the two sets completely disjoint, so
    scoping a skill edit this way is exact rather than approximate.
    """
    names = set()
    for key in root.match(r"\.MIS$"):
        try:
            names |= transforms.enemy_templates(root.read(key))
        except Exception:                       # noqa: BLE001
            continue
    return {n.upper() for n in names}


GUN_SCOPES = {"ally_guns": 0, "enemy_guns": 1}


def gun_scope_set(root, which):
    """The base names of one side's `.gun` files.

    `rseguns` keys its census by BASE NAME with a leading slash, because the
    PS2 archives it was written against are flat. A game folder is not: the
    same kit is `/EQUIP/AK47 ONLY.KIT` here. Handing it the full key silently
    produced two empty sides -- the kit stems never matched the names the
    missions asked for -- so the census is keyed by base name and the real key
    is carried alongside for reading. Where a name exists both loose and inside
    a glob the two are byte-identical, so collapsing them loses nothing.
    """
    view = _View(root)
    files = {}
    for key, f in root.files.items():
        files.setdefault("/" + f.name, (view, key))
    picked = rseguns.sides(files)[GUN_SCOPES[which]]
    return {n.upper() for n in picked}


def _scope_filter(root, edit, cache):
    if not edit.scope:
        return None
    if edit.scope in GUN_SCOPES:
        if edit.scope not in cache:
            cache[edit.scope] = gun_scope_set(root, edit.scope)
        allowed = cache[edit.scope]
    elif edit.scope == "enemy_templates":
        if "atr" not in cache:
            cache["atr"] = enemy_template_set(root)
        allowed = cache["atr"]
    else:
        raise DataEditError("unknown scope %r" % edit.scope)
    return lambda key: root.files[key].name in allowed


# ---------------------------------------------------------------------------
# backup store
# ---------------------------------------------------------------------------

class Store:
    """Original bytes for every file we have touched, keyed the same way the
    folder index is."""

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
        safe = key.strip("/").replace("/", "__").replace("\\", "__")
        return os.path.join(self.folder, "orig", safe)

    def remember(self, key, data):
        if key in self.index:
            return
        blob = self._blob(key)
        os.makedirs(os.path.dirname(blob), exist_ok=True)
        with open(blob, "wb") as fh:
            fh.write(data)
        self.index[key] = {"key": key, "size": len(data)}
        self.save()

    def original(self, key):
        if key not in self.index:
            return None
        try:
            with open(self._blob(key), "rb") as fh:
                return fh.read()
        except OSError:
            return None

    def keys(self):
        return list(self.index)

    def save(self):
        os.makedirs(self.folder, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self.index, fh, indent=1)

    def forget_all(self):
        """Drop every remembered original, and the saved bytes with them.

        This used to empty the index and write the empty manifest back, which
        left two things behind: the saved originals -- 141 MB on a Rainbow Six
        3 disc whose level packages had been edited -- and the manifest file
        itself, which is what `engine.has_backup` looks for. So a disc that had
        just been restored to the byte still reported as modded, the
        image-versus-folder check went on skipping it as "already modded", and
        the space never came back.

        Only blobs named in the index are removed, and only after the restore
        that called this has already finished, so nothing is deleted that
        might still be needed.
        """
        for key in list(self.index):
            try:
                os.remove(self._blob(key))
            except OSError:
                pass
        self.index = {}
        for path in (self.path, os.path.join(self.folder, "orig"), self.folder):
            try:
                os.remove(path) if os.path.isfile(path) else os.rmdir(path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# apply / revert
# ---------------------------------------------------------------------------

def plan_data(root, edits):
    """Which keys each edit would rewrite, without touching anything."""
    rows = []
    scopes = {}
    for edit in edits:
        allowed = _scope_filter(root, edit, scopes)
        for key in root.match(edit.select):
            if allowed and not allowed(key):
                continue
            rows.append((key, edit))
    return rows


def apply_data(root, edits, store, progress=None):
    """Run every edit against the folder, starting from the original bytes.

    Starting from the ORIGINAL rather than from what is on disk is what makes
    this idempotent: applying twice gives the same folder as applying once, and
    clearing an option really removes it, because the first thing an apply does
    to a file it has touched before is put the shipped bytes back.
    """
    pending = {}
    counts = {}
    scopes = {}
    #: key -> the bytes this run started from, captured the first time the key
    #: is read and kept until the write loop decides whether it is needed.
    shipped = {}

    def say(msg):
        if progress:
            progress(msg)

    for edit in edits:
        op = OPS.get(edit.op)
        if op is None:
            raise DataEditError("unknown data operation %r" % edit.op)
        allowed = _scope_filter(root, edit, scopes)
        for key in root.match(edit.select):
            if allowed and not allowed(key):
                continue
            if key in pending:
                plain = pending[key]
            else:
                plain = store.original(key)
                if plain is None:
                    plain = root.read(key)
                shipped.setdefault(key, plain)
            new, n = op(plain, edit.params)
            if len(new) != len(plain) and root.packed(key):
                raise DataEditError(
                    "%s: %s changed the file length, which neither a glob nor "
                    "a .umd slot can survive" % (key, edit.op))
            if n:
                counts[edit.op] = counts.get(edit.op, 0) + n
            pending[key] = new

    # Say what is in flight BEFORE starting on it. Packing happens inside
    # `root.write`, and on a big .LIN that takes long enough that a log which
    # only speaks afterwards is indistinguishable from a hang -- which is
    # exactly how it was read on the PS2 build.
    written = 0
    queued = sorted(pending.items())
    if queued:
        say("  %d file%s to check and rebuild"
            % (len(queued), "" if len(queued) == 1 else "s"))
    for n, (key, plain) in enumerate(queued, 1):
        if plain == root.read(key):
            continue
        if len(plain) >= _CHATTY_BYTES or n % 25 == 0 or n == len(queued):
            say("  packing %d/%d  %s" % (n, len(queued), key))
        # Remember here, immediately before the write, and nowhere else.
        #
        # Two earlier placements were both wrong. Remembering when an edit
        # SELECTED a key copied 300 MB of level packages to protect files no
        # edit touched. Moving it to "after the op, if the op changed
        # something" fixed the waste and introduced a hole: a key matched by
        # two edits takes the `key in pending` branch the second time, so a
        # file left alone by the first edit and changed by the second was
        # written with no backup at all -- and `ini_values` and `scale_ini`
        # both select R6GameSettings.ini, so that pairing is not hypothetical.
        #
        # At this line both questions are already answered: the bytes differ
        # from the disc, so a backup is needed, and `shipped` holds what the
        # run started from. `Store.remember` ignores a key it already has, so
        # a second run costs nothing.
        store.remember(key, shipped[key])
        root.write(key, plain)
        written += 1

    # Put back anything we touched on a previous run that no longer matches an
    # edit. Without this, turning an option off would leave its files changed.
    restored = 0
    for key in store.keys():
        if key in pending or key not in root.files:
            continue
        original = store.original(key)
        if original is not None and root.read(key) != original:
            root.write(key, original)
            restored += 1
    root.flush()

    if written or restored:
        say("Rewrote %d file%s%s"
            % (written, "" if written == 1 else "s",
               (" and put %d back" % restored) if restored else ""))
    return {"files": written, "restored": restored, "changes": counts}


def revert_data(root, store, progress=None):
    """Put every remembered file back."""
    done = 0
    for key in store.keys():
        original = store.original(key)
        if original is None or key not in root.files:
            continue
        root.write(key, original)
        done += 1
        if progress and done % 100 == 0:
            progress("  %d files restored" % done)
    root.flush()
    store.forget_all()
    return {"files": done}


def verify_data(root, store):
    """Read every file we touched back off the disc and confirm it is there."""
    ok = bad = 0
    for key in store.keys():
        if key not in root.files:
            bad += 1
            continue
        try:
            root.read(key)
            ok += 1
        except Exception:                       # noqa: BLE001
            bad += 1
    return ok, bad

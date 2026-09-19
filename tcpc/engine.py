"""Turning a profile's edits into files on disk, safely and reversibly.

Two invariants carry over from the PS2 tool, and they are the whole reason
this is safe to run twice:

**Every apply rebuilds from PRISTINE.** Nothing is ever edited on top of an
earlier edit. For an in-place game that means each touched file is restored
from the copy taken the first time it was written, and the whole edit set is
then applied to that; for a mod-folder game it means the generated folder is
deleted and rebuilt from the stock mod. So applying twice equals applying once,
and clearing an option really removes it instead of leaving the last value it
happened to hold.

**Every edit states the value it expects to find.** The stock value is checked
before the write and reported when it does not match, because a stock value
that is not there means the profile's arithmetic was worked out against a
different build of the game and is not about the file in front of it.

The mod-folder route is strictly better where the game has one, and two of
these five do: Ghost Recon and Sum of All Fears load `Mods\\<name>\\` folders
that shadow `Mods\\Origmiss\\`. Nothing retail is written at all, and the
game's own mod selector is a complete uninstall.
"""

from __future__ import annotations

import copy
import fnmatch
import re
import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass, field

from . import inifile, rsexml, upackage, xmlbin
from .install import backup_dir_for
from .model import (FileCopy, INPLACE, IniEdit, IniLines, MOD, OVERLAY,
                    PropEdit, XmlAttr, XmlText)

#: dropped in a generated mod folder so the tool can tell a folder it made
#: from one the user made. Nothing is ever deleted without this present.
MARKER = ".tcpc-generated"
MANIFEST = "manifest.json"


class ApplyError(Exception):
    pass


@dataclass
class Change:
    """One value actually written, for the log and the read-back check."""
    rel: str
    what: str
    old: str
    new: str
    status: str = "changed"      # changed | same | absent | stock-mismatch


@dataclass
class Result:
    ok: bool = True
    changes: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    files: int = 0
    #: rel path -> sha1 of what was written, re-read from disk
    verified: dict = field(default_factory=dict)

    def log(self) -> list:
        out = []
        for c in self.changes:
            if c.status == "changed":
                out.append("  %s: %s  %s -> %s" % (c.rel, c.what, c.old, c.new))
            elif c.status == "stock-mismatch":
                out.append("  %s: %s expected %s, found %s -- written anyway"
                           % (c.rel, c.what, c.old, c.new))
            elif c.status == "absent":
                out.append("  %s: %s is not in this file -- skipped"
                           % (c.rel, c.what))
        return out


# ---------------------------------------------------------------------------
# locating files
# ---------------------------------------------------------------------------

def walk_rel(root):
    """Every file under `root`, as a relative path with forward slashes."""
    out = []
    root = os.path.abspath(root)
    for base, _dirs, names in os.walk(root):
        rel = os.path.relpath(base, root).replace(os.sep, "/")
        if rel == ".":
            rel = ""
        if rel.startswith(".tcpc-backup"):
            continue
        for n in names:
            out.append((rel + "/" + n) if rel else n)
    return out


#: cache of compiled selectors, since a profile reuses a handful of globs
#: across dozens of edits
_RX_CACHE = {}


def expand(paths, pattern) -> list:
    """Relative paths matching `pattern`, case-insensitively.

    NOT `fnmatch`, for one reason that matters: `fnmatch`'s `*` crosses a
    directory separator. Ghost Recon keeps its 562 enemy actors loose in
    `Mods\\Origmiss\\Actor\\` and the player's own squad in subfolders of it,
    so under `fnmatch` the selector `Actor/*.atr` -- which reads as "the enemy
    actors" and is used here to mean exactly that -- would also match
    `Actor/rifleman/*.atr` and quietly apply "make enemies tougher" to the
    player's riflemen.

    So `*` stops at a separator and `**` is the one that crosses it. Case is
    folded here rather than left to the platform, because these folders really
    do mix case within one directory (`AKS74U.GUN` beside `ak47.gun`).
    """
    pat = pattern.replace("\\", "/").lower()
    rx = _RX_CACHE.get(pat)
    if rx is None:
        rx = _RX_CACHE[pat] = re.compile(_glob_rx(pat))
    return [p for p in paths if rx.fullmatch(p.lower())]


def _glob_rx(pattern) -> str:
    out, i = [], 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            if pattern[i:i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# applying one edit to one loaded file
# ---------------------------------------------------------------------------

def _resolve_value(edit, current):
    """The value to write, given what the file currently holds.

    An edit either states a value outright or scales the file's own. Scaling is
    what makes a single slider mean something across 108 weapons that all start
    from different numbers.
    """
    if edit.scale is None and edit.offset is None:
        return edit.value, None
    num = (inifile.parse_number(current) if isinstance(edit, IniEdit)
           else rsexml.parse_number(current))
    if num is None:
        return None, "value %r is not a number, cannot scale" % current
    out = num * (1.0 if edit.scale is None else edit.scale)
    if edit.offset is not None:
        out += edit.offset
    if edit.minimum is not None:
        out = max(edit.minimum, out)
    if edit.maximum is not None:
        out = min(edit.maximum, out)
    fmt = inifile.format_number if isinstance(edit, IniEdit) else rsexml.format_number
    return fmt(out, current), None


def _expand_sections(doc, edits):
    """Turn a `section="*"` edit into one per section the file actually has.

    Vegas copies the same eight camera-shake keys into all 35 of its damage-type
    sections, so "camera shake off" is one option and 35 writes. Listing the
    section names in the profile would mean keeping that list in step with a
    file this tool does not own; asking the file is always right.
    """
    out = []
    for e in edits:
        if getattr(e, "section", "") != "*":
            out.append(e)
            continue
        for name in doc.sections():
            clone = copy.copy(e)
            clone.section = name
            out.append(clone)
    return out


def _shown(edit):
    """How a proportional edit reads in the log."""
    bits = []
    if edit.scale is not None:
        bits.append("x%g" % edit.scale)
    if edit.offset:
        bits.append("%+g" % edit.offset)
    return " ".join(bits) or "="


def apply_ini(doc: "inifile.Ini", edits, rel, out: Result):
    for e in _expand_sections(doc, edits):
        current = (doc.get_field(e.section, e.key, e.field) if e.field
                   else doc.get(e.section, e.key))
        what = "[%s] %s%s" % (e.section or "-", e.key,
                              ("." + e.field) if e.field else "")
        # A key that is simply not in this section, on an edit that says to
        # skip those, is not a problem and must not be reported as one.
        # `section="*"` expands across every section in the file -- Vegas has
        # 35 weapon sections and an `[Internal]` one -- so without this an
        # ordinary option warns once per section that does not carry the key,
        # and real warnings get lost in the noise.
        if current is None and e.absent == "skip":
            out.changes.append(Change(rel, what, "", "", "absent"))
            continue
        value, err = _resolve_value(e, current)
        if err:
            out.warnings.append("%s: %s %s" % (rel, what, err))
            out.changes.append(Change(rel, what, str(current), "", "absent"))
            continue
        if e.stock is not None and current is not None \
                and str(current).strip() != str(e.stock).strip():
            out.changes.append(Change(rel, what, str(e.stock), str(current),
                                      "stock-mismatch"))
            out.warnings.append(
                "%s: %s was expected to be %s but is %s. This build differs "
                "from the one the option was measured on."
                % (rel, what, e.stock, current))
        status = (doc.set_field(e.section, e.key, e.field, value) if e.field
                  else doc.set(e.section, e.key, value, absent=e.absent))
        out.changes.append(Change(rel, what, str(current), str(value),
                                  "changed" if status in ("changed", "added")
                                  else status))


def apply_ini_lines(doc: "inifile.Ini", edits, rel, out: Result):
    """Add, drop and swap elements of a repeated-key list."""
    for e in edits:
        what = "[%s] %s" % (e.section or "-", e.key or "(section)")
        if e.rename:
            status = doc.rename_section(e.section, e.rename)
            out.changes.append(Change(rel, what, e.section, e.rename, status))
            continue
        before = doc.get_all(e.section, e.key)
        n = 0
        for old, new in e.swap.items():
            if doc.replace_line(e.section, e.key, old, new) == "changed":
                n += 1
        for old, new in e.sub.items():
            n += doc.substitute(e.section, e.key, old, new)
        for value in e.drop:
            if doc.remove_line(e.section, e.key, value) == "changed":
                n += 1
        for value in e.add:
            if doc.add_line(e.section, e.key, value) == "added":
                n += 1
        after = doc.get_all(e.section, e.key)
        if not n:
            out.changes.append(Change(rel, what, "%d entr(ies)" % len(before),
                                      "already as asked", "same"))
            continue
        out.changes.append(Change(rel, what, "%d entr(ies)" % len(before),
                                  "%d, %d change(s)" % (len(after), n),
                                  "changed"))


def apply_xml(doc: "rsexml.Doc", edits, rel, out: Result):
    for e in edits:
        is_attr = isinstance(e, XmlAttr)
        # `any_attr`, not `get_attr`: an edit is only "absent" when NOT ONE
        # matching element carries the attribute. Deciding that from the first
        # match alone silently skipped edits with a dozen elements to write.
        current = (doc.any_attr(e.path, e.attr) if is_attr
                   else doc.get_text(e.path))
        what = "%s%s" % (e.path, ("@" + e.attr) if is_attr else "")
        if current is None:
            out.changes.append(Change(rel, what, "", "", "absent"))
            continue
        if e.stock is not None and str(current).strip() != str(e.stock).strip():
            out.changes.append(Change(rel, what, str(e.stock), str(current),
                                      "stock-mismatch"))
            out.warnings.append(
                "%s: %s was expected to be %s but is %s."
                % (rel, what, e.stock, current))

        if e.remap:
            # No single "before" value to print: a remap gives each element the
            # value ITS OWN value maps to, so the first element's is not the
            # story. The count is.
            status, n = (doc.remap_attr(e.path, e.attr, e.remap) if is_attr
                         else doc.remap_text(e.path, e.remap))
            out.changes.append(Change(rel, what, "%d value(s)" % n,
                                      "remapped", status))
            continue

        if e.scale is not None or e.offset is not None:
            # Scaling is delegated so each matching element can start from its
            # own value; see `rsexml.scale_attr` for why that matters.
            fn = doc.scale_attr if is_attr else doc.scale_text
            args = (e.path, e.attr) if is_attr else (e.path,)
            status, n = fn(*args, e.scale, e.offset, e.minimum, e.maximum)
            shown = _shown(e) + ("" if n <= 1 else " (%d places)" % n)
            out.changes.append(Change(rel, what, str(current), shown, status))
            continue

        status = (doc.set_attr(e.path, e.attr, e.value) if is_attr
                  else doc.set_text(e.path, e.value))
        out.changes.append(Change(rel, what, str(current), str(e.value), status))


def apply_package(pkg: "upackage.Package", edits, rel, out: Result):
    r"""Rewrite compiled class defaults in one Unreal package.

    The loop is over CLASSES rather than over edits, because one edit is
    normally aimed at every class that has the property -- "20% less recoil"
    is 143 separate four-byte writes, and logging 143 lines would bury the
    other changes. One line per edit is emitted instead, counting the classes
    it reached.

    A class whose defaults cannot be parsed exactly is skipped and reported.
    That is not a formality: six classes in `R6Weapons.u` still carry compiled
    script, and `ScriptSize` is a memory length, so their property lists cannot
    be located by arithmetic. Guessing at one would put a four-byte write at an
    arbitrary offset in the middle of executable bytecode.
    """
    names = [e.name for e in pkg.classes() if e.size > 0]
    for e in edits:
        want = [n for n in names if _class_match(n, e.cls)]
        hit = 0
        misparsed = []
        firsts = []
        for name in want:
            try:
                table = pkg.defaults(name)
            except upackage.PackageError:
                misparsed.append(name)
                continue
            prop = table.get(e.prop)
            if prop is None:
                continue
            current = pkg.get(name, e.prop)
            if current is None:                       # a type we cannot write
                continue
            if e.stock is not None and len(want) == 1 \
                    and str(current).strip() != str(e.stock).strip():
                out.changes.append(Change(rel, "%s.%s" % (name, e.prop),
                                          str(e.stock), str(current),
                                          "stock-mismatch"))
                out.warnings.append(
                    "%s: %s.%s was expected to be %s but is %s. This build "
                    "differs from the one the option was measured on."
                    % (rel, name, e.prop, e.stock, current))
            value, err = _resolve_prop_value(e, current, prop)
            if err:
                out.warnings.append("%s: %s.%s %s" % (rel, name, e.prop, err))
                continue
            if pkg.set(name, e.prop, value):
                hit += 1
                if len(firsts) < 3:
                    firsts.append("%s %s->%s" % (name, _brief(current),
                                                 _brief(value)))
        what = "%s.%s" % (e.cls, e.prop)
        if misparsed:
            out.warnings.append(
                "%s: %d class(es) could not be parsed and were left alone: %s"
                % (rel, len(misparsed), ", ".join(sorted(misparsed)[:6])))
        if not hit:
            out.changes.append(Change(rel, what, "", "", "absent"))
            continue
        out.changes.append(Change(rel, what, "%d class(es)" % hit,
                                  _shown(e) + " [" + "; ".join(firsts) + "]",
                                  "changed"))


def _class_match(name, pattern) -> bool:
    if pattern in ("*", ""):
        return True
    if pattern.endswith("*"):
        return name.startswith(pattern[:-1])
    if pattern.startswith("*"):
        return name.endswith(pattern[1:])
    return name == pattern


def _brief(value):
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, float):
        return "%g" % value
    return str(value)


def _resolve_prop_value(edit, current, prop):
    """As `_resolve_value`, but the current value is already typed.

    No parsing and no formatting: a package holds numbers as numbers, so the
    string round-trip the text editors need would only lose precision here.
    """
    if edit.scale is None and edit.offset is None:
        return edit.value, None
    if isinstance(current, bool):
        return None, "is a flag and cannot be scaled"
    out = current * (1.0 if edit.scale is None else edit.scale)
    if edit.offset is not None:
        out += edit.offset
    if edit.minimum is not None:
        out = max(edit.minimum, out)
    if edit.maximum is not None:
        out = min(edit.maximum, out)
    if prop.kind in ("int", "byte"):
        out = int(round(out))
    return out, None


# ---------------------------------------------------------------------------
# grouping edits by the file they land in
# ---------------------------------------------------------------------------

def plan(root, profile, edits) -> dict:
    """rel path -> list of edits that apply to it.

    A glob in `select` is expanded against the real folder, so "every enemy
    actor" reaches 459 files without the profile listing one of them. The
    search root for a mod-delivery game is the STOCK mod folder, because that
    is what a generated mod shadows -- expanding against the install root would
    also sweep up whatever other mods are installed beside it.
    """
    if profile.delivery == OVERLAY:
        # Both namespaces, because the game reads from both. Not every file an
        # Advanced Warfighter install loads is inside an archive:
        # `Settings\hud_palett_2.xml` -- which is the whole HUD colour scheme,
        # self-documented, with a second unused scheme sitting under it -- is
        # loose only, and a bundle-only listing would never see it.
        with open_bundles(root, profile) as bs:
            names = list(bs.paths())
        seen = {n.lower() for n in names}
        for rel in walk_rel(root):
            if rel.lower() not in seen and not rel.lower().startswith("bundles/"):
                names.append(rel)
        content_root = root
    else:
        base = source_root(root, profile)
        names = walk_rel(base) if base and os.path.isdir(base) else []
        content_root = base
    # Paths this edit set is about to CREATE. They are not on disk yet, so
    # they cannot be found by expanding a glob -- but edits aimed at them are
    # exactly how a created file gets its content. Ghost Recon's enemy-weapon
    # split copies `ak47.gun` to `ak47_npc.gun` and then retunes the copy;
    # without this the copy is written out stock and the option looks applied
    # while doing nothing.
    coming = {e.select.replace("\\", "/") for e in edits
              if isinstance(e, FileCopy) and not _is_glob(e.select)}
    out = {}
    for e in edits:
        hits = expand(names, e.select)
        if not hits and not _is_glob(e.select):
            rel = e.select.replace("\\", "/")
            # A `FileCopy` naming one exact path that is not there yet is not a
            # miss -- it is the point. This is how an in-place profile ships a
            # file the game never had. A GLOB that matches nothing is still a
            # miss, because there is no single path to invent.
            if isinstance(e, FileCopy) or rel in coming:
                hits = [rel]
        for rel in hits:
            if not in_scope(rel, e.scope, content_root):
                continue
            out.setdefault(rel, []).append(e)
    return out


def _is_glob(pattern) -> bool:
    return any(ch in pattern for ch in "*?")


def in_scope(rel, scope, base=None) -> bool:
    """Whether `rel` survives an edit's extra filter.

    A glob alone is sometimes the wrong shape for what an option means.
    Lockdown keeps the player's weapons and the enemy's in the SAME folder,
    told apart only by an `e_` prefix, so `data\\equip\\*.gun` is every gun in
    the game and "your weapon damage" needs to say which half it meant. The
    filter is written as `not:<glob>` or `only:<glob>` against the file name.

    Two verbs test the file's CONTENTS instead, because sometimes the name
    does not carry the distinction at all. `lacks:<tag>` and `has:<tag>` ask
    whether the file has a non-empty `<tag>` element.

    That is not a theoretical nicety. "Enemy" in the two Red Storm games was
    scoped by folder, and in Sum of All Fears 49 of the 448 actors in the
    enemy folder are friendly -- eleven support teams and a hostage -- so
    every "tougher enemies" option was also buffing them. An enemy there is an
    actor with no `<KitPath>`: a kit path means somebody equipped this actor
    from the player's own kit folders.
    """
    if not scope:
        return True
    verb, _, pattern = scope.partition(":")
    if verb in ("has", "lacks"):
        if base is None:
            raise ApplyError(
                "scope %r tests file contents and needs a search root" % scope)
        path = os.path.join(base, rel.replace("/", os.sep))
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
        except OSError:
            return False
        rx = re.compile(br"<\s*%s\s*>\s*[^\s<]"
                        % re.escape(pattern.encode("latin-1")), re.I)
        found = bool(rx.search(raw))
        return found if verb == "has" else not found
    name = rel.rsplit("/", 1)[-1].lower()
    hit = fnmatch.fnmatchcase(name, pattern.lower())
    if verb == "not":
        return not hit
    if verb == "only":
        return hit
    return True


def source_root(root, profile) -> str:
    """Where pristine content is read FROM."""
    if profile.delivery == MOD:
        return os.path.join(root, profile.layout.base_mod.replace("/", os.sep))
    return root


def open_bundles(root, profile):
    """The game's `.bundle` archives, newest last."""
    from .bundle import BundleSet
    return BundleSet(os.path.join(root,
                                  profile.layout.bundles_dir.replace("/", os.sep)))


def overlay_dest(root, profile, rel) -> str:
    r"""Where a bundle path is written as a loose file.

    **A bundle's root IS the install root.** The archives hold `context.xml`
    and `settings\...` alongside `data\...`, and those are the same
    `context.xml` and `Settings\` folder that sit loose next to the executable.
    So a path is written where it already belongs, and the only special case is
    the first component `data`, which is replaced with the install's real
    `Data\` folder rather than appended to it -- otherwise the file would land
    in `Data\data\` and shadow nothing.

    That `Data\` is where the evidence points: this installation has 764
    hand-added texture files under `Data\textures\...` shadowing
    `data/textures/...` in the archive.
    """
    parts = [p for p in rel.replace("\\", "/").split("/") if p]
    if parts and parts[0].lower() == "data":
        parts = [profile.layout.overlay_dir or "Data"] + parts[1:]
    return os.path.join(root, *[p.replace("/", os.sep) for p in parts])


def mod_dir(root, profile) -> str:
    return os.path.join(root, profile.layout.mods_dir.replace("/", os.sep),
                        profile.mod_name)


# ---------------------------------------------------------------------------
# backups (in-place delivery)
# ---------------------------------------------------------------------------

def _backup_path(root, rel):
    return os.path.join(backup_dir_for(root), "pristine", rel.replace("/", os.sep))


def _manifest_path(root):
    return os.path.join(backup_dir_for(root), MANIFEST)


def read_manifest(root) -> dict:
    try:
        with open(_manifest_path(root), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def write_manifest(root, data):
    path = _manifest_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)


def stash(root, rel) -> bool:
    """Keep a pristine copy of `rel` if there is not one already.

    Returns True when a copy was taken now. Never overwrites an existing one:
    the FIRST copy is the only pristine one, and a second apply would otherwise
    save the already-edited file as the thing to restore to.
    """
    dest = _backup_path(root, rel)
    if os.path.exists(dest):
        return False
    src = os.path.join(root, rel.replace("/", os.sep))
    if not os.path.isfile(src):
        return False
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(src, dest)
    return True


def restore(root, rel) -> bool:
    src = _backup_path(root, rel)
    if not os.path.isfile(src):
        return False
    dest = os.path.join(root, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(src, dest)
    return True


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------

def sha1(path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def apply(root, profile, values, dry_run=False, progress=None) -> Result:
    """Write `values` into the install. Idempotent by construction."""
    root = os.path.abspath(str(root))
    values = profile.effective(values)
    edits = profile.edits_for(values, root)
    out = Result()

    if profile.combination_warnings:
        out.warnings.extend(profile.combination_warnings(values) or [])

    grouped = plan(root, profile, edits)
    missing = [e.select for e in edits
               if not any(e in v for v in grouped.values())]
    for sel in sorted(set(missing)):
        out.warnings.append("Nothing matched %s -- that option changed nothing."
                            % sel)

    if profile.delivery == MOD:
        _apply_mod(root, profile, grouped, out, dry_run, progress)
    elif profile.delivery == OVERLAY:
        _apply_overlay(root, profile, grouped, out, dry_run, progress)
    else:
        _apply_inplace(root, profile, grouped, out, dry_run, progress)
    out.files = len(grouped)
    return out


def copy_source(edit, base):
    """Where a `FileCopy`'s `source` actually is, or None.

    A profile cannot know the absolute path of an installation, so `source` is
    relative to whatever the edits are being read FROM -- the stock mod folder
    for a mod-delivery game, the install root otherwise. An absolute path is
    still honoured for a file the tool ships itself.
    """
    if not edit.source:
        return None
    if os.path.isabs(edit.source):
        return edit.source if os.path.isfile(edit.source) else None
    if not base:
        return None
    path = os.path.join(base, edit.source.replace("/", os.sep))
    return path if os.path.isfile(path) else None


def _edit_bytes(raw, rel, edits, out: Result, base=None):
    """As `_edit_file`, but for content that came out of an archive.

    Written through a temporary file rather than by giving the parsers a bytes
    constructor, so both paths go through exactly the same loader and cannot
    disagree about encoding, line endings or a byte-order mark.
    """
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=os.path.splitext(rel)[1] or ".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(raw)
        return _edit_file(tmp, rel, edits, out, base)
    finally:
        try:
            os.remove(tmp)
        except OSError:                           # pragma: no cover
            pass


def _edit_file(src_bytes_path, rel, edits, out: Result, base=None):
    """Load, edit and return the new bytes for one file."""
    ini_edits = [e for e in edits if isinstance(e, IniEdit)]
    line_edits = [e for e in edits if isinstance(e, IniLines)]
    xml_edits = [e for e in edits if isinstance(e, (XmlAttr, XmlText))]
    pkg_edits = [e for e in edits if isinstance(e, PropEdit)]
    copies = [e for e in edits if isinstance(e, FileCopy)]
    if copies:
        last = copies[-1]
        if last.data is not None:
            raw = last.data
        else:
            found = copy_source(last, base)
            if found is None:
                raise ApplyError("%s: nothing to copy from (%r)"
                                 % (rel, last.source))
            with open(found, "rb") as fh:
                raw = fh.read()
        rest = [e for e in edits if not isinstance(e, FileCopy)]
        if not rest:
            return raw
        # A copy is a STARTING POINT as well as a whole file. Ghost Recon's
        # enemy-weapon split needs `ak47_npc.gun` to be `ak47.gun` with
        # different numbers in it, and expressing that as "copy, then edit"
        # keeps the numbers in the profile where every other option's are.
        out.changes.append(Change(rel, "copied from", last.source, rel,
                                  "changed"))
        return _edit_bytes(raw, rel, rest, out, base)
    if len([x for x in (ini_edits + line_edits, xml_edits, pkg_edits) if x]) > 1:
        raise ApplyError("%s has more than one kind of edit aimed at it" % rel)
    if pkg_edits:
        before = os.path.getsize(src_bytes_path)
        pkg = upackage.Package.load(src_bytes_path)
        apply_package(pkg, pkg_edits, rel, out)
        data = pkg.to_bytes()
        # The whole safety argument for touching a compiled package is that an
        # edit is equal-width, so the export table still describes the file.
        # Check it rather than assert it.
        if len(data) != before:
            raise ApplyError(
                "%s: package edit changed the file length from %d to %d bytes"
                % (rel, before, len(data)))
        return data
    if ini_edits or line_edits:
        doc = inifile.Ini.load(src_bytes_path)
        if ini_edits:
            apply_ini(doc, ini_edits, rel, out)
        if line_edits:
            apply_ini_lines(doc, line_edits, rel, out)
        return doc.to_bytes()
    doc = rsexml.Doc.load(src_bytes_path)
    apply_xml(doc, xml_edits, rel, out)
    return doc.to_bytes()


def _write(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tcpc-tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


def _apply_inplace(root, profile, grouped, out, dry_run, progress):
    manifest = read_manifest(root)
    touched = set(manifest.get("files", []))
    made = set(manifest.get("created", []))

    # Rebuild from pristine: put back everything a previous apply changed,
    # INCLUDING files this apply no longer touches. That is what makes
    # clearing an option actually clear it.
    for rel in sorted(touched):
        if not dry_run:
            restore(root, rel)
    # A file the tool INVENTED has no pristine copy, so undoing it means
    # deleting it. Same rule, different verb.
    for rel in sorted(made):
        if not dry_run:
            path = os.path.join(root, rel.replace("/", os.sep))
            if os.path.isfile(path):
                os.remove(path)
            _prune(os.path.dirname(path), root)

    now, created = [], []
    for i, (rel, edits) in enumerate(sorted(grouped.items())):
        if progress:
            progress(i, len(grouped), rel)
        abs_path = os.path.join(root, rel.replace("/", os.sep))
        fresh = not os.path.isfile(abs_path)
        if fresh and not _supplies_whole_file(edits, root):
            out.warnings.append("%s is not in this installation." % rel)
            continue
        if not dry_run and not fresh:
            stash(root, rel)
        try:
            data = _edit_file(abs_path, rel, edits, out, root)
        except (inifile.IniError, rsexml.RseXmlError, OSError) as exc:
            out.ok = False
            out.warnings.append("%s: %s" % (rel, exc))
            continue
        if not dry_run:
            _write(abs_path, data)
            out.verified[rel] = sha1(abs_path)
        (created if fresh else now).append(rel)
        if fresh:
            out.changes.append(Change(rel, "new file", "absent", "created"))

    if not dry_run:
        manifest["files"] = sorted(set(now))
        manifest["created"] = sorted(set(created))
        manifest["applied"] = time.strftime("%Y-%m-%d %H:%M:%S")
        manifest["game"] = profile.id
        write_manifest(root, manifest)
        # Files that were touched before and are not any more have been
        # restored; their pristine copies stay, because the option may come
        # back and the first copy is the only trustworthy one.


def _supplies_whole_file(edits, base=None) -> bool:
    """Can these edits produce a file that is not there yet?

    Only a `FileCopy` can: every other edit kind changes something in content
    it has to read first. This is what lets an in-place profile ADD a file --
    Raven Shield's cut game modes need a `.mod` that the game never shipped --
    without weakening the rule that an edit to a missing file is an error.
    """
    for e in edits:
        if isinstance(e, FileCopy) and (e.data is not None
                                        or copy_source(e, base) is not None):
            return True
    return False


def _apply_mod(root, profile, grouped, out, dry_run, progress):
    dest_root = mod_dir(root, profile)
    src_root = source_root(root, profile)
    if not os.path.isdir(src_root):
        out.ok = False
        out.warnings.append("The stock mod folder %s is not here, so there is "
                            "nothing to build a mod from."
                            % profile.layout.base_mod)
        return

    if not dry_run:
        _clear_mod(dest_root, out)

    for i, (rel, edits) in enumerate(sorted(grouped.items())):
        if progress:
            progress(i, len(grouped), rel)
        src = os.path.join(src_root, rel.replace("/", os.sep))
        if not os.path.isfile(src):
            # A generated mod may SHIP a file the stock mod never had -- Ghost
            # Recon's enemy-weapon split adds `<gun>_npc.gun` beside the
            # originals -- but only when an edit actually supplies content.
            if not _supplies_whole_file(edits, src_root):
                out.warnings.append("%s is not in the stock mod." % rel)
                continue
        try:
            data = _edit_file(src, rel, edits, out, src_root)
        except (rsexml.RseXmlError, OSError) as exc:
            out.ok = False
            out.warnings.append("%s: %s" % (rel, exc))
            continue
        if not dry_run:
            dest = os.path.join(dest_root, rel.replace("/", os.sep))
            _write(dest, data)
            out.verified[rel] = sha1(dest)

    if not dry_run and grouped:
        _write(os.path.join(dest_root, "ModsCont.txt"),
               mods_cont(profile).encode("cp1252", errors="replace"))
        # Deliberately carries no timestamp. A mod build is then REPRODUCIBLE:
        # the same settings against the same stock data give byte-identical
        # output, so two builds can be diffed against each other and the test
        # that applies twice and compares means something. A date stamp here
        # made every build differ from every other build in exactly one file,
        # which is the least useful possible difference.
        _write(os.path.join(dest_root, MARKER),
               b"Generated by Tom Clancy PC Mod Studio.\r\n"
               b"Deleting this file stops the tool from managing this folder,\r\n"
               b"and stops it from ever deleting the folder.\r\n")


def _apply_overlay(root, profile, grouped, out, dry_run, progress):
    r"""Write loose files that shadow the bundle, and remember exactly which.

    Two kinds of destination, kept apart in the manifest because reverting them
    is not the same operation:

    *created*  -- a path that did not exist loose before. Reverting DELETES it,
                  and the game falls back to the archive.
    *shadowed* -- a path that already had a loose file, which is not
                  hypothetical: this installation has 764 hand-added texture
                  files sitting in exactly that tree. A pristine copy is taken
                  before the first write and reverting puts it back.

    What reverting never does is delete the folder. `Data\` is shared with the
    user's own replacements, so only the recorded paths are touched.
    """
    manifest = read_manifest(root)
    created = list(manifest.get("created", []))
    shadowed = list(manifest.get("files", []))

    # Rebuild from pristine, same rule as everywhere else: undo the last apply
    # completely before working out this one.
    if not dry_run:
        for rel in created:
            path = os.path.join(root, rel.replace("/", os.sep))
            if os.path.isfile(path):
                os.remove(path)
            _prune(os.path.dirname(path), root)
        for rel in shadowed:
            restore(root, rel)

    now_created, now_shadowed = [], []
    try:
        bundles = open_bundles(root, profile)
    except Exception as exc:                      # noqa: BLE001
        out.ok = False
        out.warnings.append("Could not open the game's bundles: %s" % exc)
        return
    with bundles:
        for i, (rel, edits) in enumerate(sorted(grouped.items())):
            if progress:
                progress(i, len(grouped), rel)
            dest = overlay_dest(root, profile, rel)
            dest_rel = os.path.relpath(dest, root).replace(os.sep, "/")
            existed = os.path.isfile(dest)
            # Edit whatever the game would actually load: the loose file if
            # there already is one, the archived copy otherwise.
            try:
                if existed and dest_rel not in created:
                    with open(dest, "rb") as fh:
                        raw = fh.read()
                else:
                    raw = bundles.read(rel)
            except (KeyError, OSError) as exc:
                out.warnings.append("%s: %s" % (rel, exc))
                continue
            try:
                data = _edit_bytes(raw, rel, edits, out)
            except (rsexml.RseXmlError, inifile.IniError) as exc:
                out.ok = False
                out.warnings.append("%s: %s" % (rel, exc))
                continue
            # A file the edits did not actually move is not written at all.
            # Not just tidiness: "every level's world file" is 44 files and
            # 60 MB per form in Advanced Warfighter, and most of them are
            # multiplayer maps that place no soldiers, so without this a
            # single option would copy tens of megabytes to say nothing.
            if not dry_run and data != raw:
                if existed and dest_rel not in created:
                    stash(root, dest_rel)
                    now_shadowed.append(dest_rel)
                else:
                    now_created.append(dest_rel)
                _write(dest, data)
                out.verified[dest_rel] = sha1(dest)

            # ...and the compiled twin, which is the file the engine will
            # actually read. Writing only the source would be a no-op.
            twin = compiled_twin(profile, rel)
            if twin is None:
                continue
            tdest = overlay_dest(root, profile, twin)
            tdest_rel = os.path.relpath(tdest, root).replace(os.sep, "/")
            texisted = os.path.isfile(tdest)
            try:
                if texisted and tdest_rel not in created:
                    with open(tdest, "rb") as fh:
                        traw = fh.read()
                else:
                    traw = bundles.read(twin)
            except (KeyError, OSError):
                continue                       # no twin: the source is the only form
            try:
                tdata = _edit_compiled(traw, twin, edits, out)
            except (xmlbin.XmlBinError, rsexml.RseXmlError) as exc:
                out.ok = False
                out.warnings.append("%s: %s" % (twin, exc))
                continue
            if not dry_run and tdata != traw:
                if texisted and tdest_rel not in created:
                    stash(root, tdest_rel)
                    now_shadowed.append(tdest_rel)
                else:
                    now_created.append(tdest_rel)
                _write(tdest, tdata)
                out.verified[tdest_rel] = sha1(tdest)

    if not dry_run:
        manifest["created"] = sorted(set(now_created))
        manifest["files"] = sorted(set(now_shadowed))
        manifest["applied"] = time.strftime("%Y-%m-%d %H:%M:%S")
        manifest["game"] = profile.id
        write_manifest(root, manifest)


def compiled_twin(profile, rel):
    """The compiled counterpart of a source path, or None."""
    suffix = getattr(profile.layout, "compiled_suffix", "")
    if not suffix or not rel.lower().endswith(".xml"):
        return None
    return rel + suffix if suffix.startswith(".bin") else rel[:-4] + suffix


def _edit_compiled(raw, rel, edits, out: Result):
    """Apply the same edits to a compiled Diesel XML.

    The edits are re-applied to the compiled tree rather than the compiled
    file being regenerated from the edited source, because the tree is what
    round-trips byte-identically. Regenerating would mean writing an
    XML-to-compiled compiler and hoping it agreed with GRIN's about string
    order; this only has to agree with itself.
    """
    root, includes = xmlbin.loads(raw)
    for e in edits:
        if not isinstance(e, XmlAttr):
            continue
        nodes = xmlbin.select(root, e.path)
        if not nodes:
            continue
        for nd in nodes:
            current = nd.get(e.attr)
            if current is None:
                continue
            if e.remap:
                new = e.remap.get(str(current).strip())
                if new is not None:
                    nd.set(e.attr, new)
            elif e.scale is not None or e.offset is not None:
                num = rsexml.parse_number(current)
                if num is None:
                    continue
                value = num * (1.0 if e.scale is None else e.scale)
                if e.offset is not None:
                    value += e.offset
                if e.minimum is not None:
                    value = max(e.minimum, value)
                if e.maximum is not None:
                    value = min(e.maximum, value)
                nd.set(e.attr, rsexml.format_number(value, current))
            else:
                nd.set(e.attr, e.value)
    return xmlbin.dumps(root, includes)


def _prune(folder, root):
    """Remove a directory this tool created, once it is empty."""
    root = os.path.abspath(root)
    folder = os.path.abspath(folder)
    while folder.startswith(root) and folder != root:
        try:
            if os.listdir(folder):
                return
            os.rmdir(folder)
        except OSError:
            return
        folder = os.path.dirname(folder)


def _clear_mod(dest_root, out):
    """Delete a previously generated mod folder -- and only one of those.

    The marker file is the whole safety check. Without it this would happily
    delete a hand-made mod that happened to share the name, and the user has
    hand-made mods sitting in exactly this folder.
    """
    if not os.path.isdir(dest_root):
        return
    if not os.path.isfile(os.path.join(dest_root, MARKER)):
        raise ApplyError(
            "%s already exists and was not made by this tool (no %s in it). "
            "Refusing to delete it -- rename it or choose another mod name."
            % (dest_root, MARKER))
    shutil.rmtree(dest_root)


def mods_cont(profile) -> str:
    """The card the game's own mod selector shows."""
    return ("// Mods Contents\r\n"
            "NAME\t\t\"%s\"\r\n"
            "AUTHOR\t\t\"Tom Clancy PC Mod Studio\"\r\n"
            "SUPPORT\t\t\"\"\r\n"
            "VERSION\t\t\"1.00\"\r\n"
            "MULTIPLAYER\t\"Server-Client\"\r\n"
            % (profile.mod_blurb or profile.mod_name))


# ---------------------------------------------------------------------------
# revert
# ---------------------------------------------------------------------------

def revert(root, profile) -> Result:
    """Put the installation back exactly as it was found."""
    root = os.path.abspath(str(root))
    out = Result()
    if profile.delivery == MOD:
        dest = mod_dir(root, profile)
        if os.path.isdir(dest):
            try:
                _clear_mod(dest, out)
            except ApplyError as exc:
                out.ok = False
                out.warnings.append(str(exc))
                return out
            out.files = 1
            out.changes.append(Change(profile.mod_name, "generated mod", "present",
                                      "removed"))
        return out

    manifest = read_manifest(root)
    # `created` covers every delivery that can add a file the installation did
    # not have -- the loose overlay, and an in-place profile that generates
    # one (Raven Shield's `.mod` files). A file with no pristine copy cannot
    # be restored, only removed, so it is tracked separately from `files`.
    if profile.delivery in (OVERLAY, INPLACE):
        for rel in sorted(manifest.get("created", [])):
            path = os.path.join(root, rel.replace("/", os.sep))
            if os.path.isfile(path):
                os.remove(path)
                out.files += 1
                out.changes.append(Change(rel, "loose file", "added", "removed"))
            _prune(os.path.dirname(path), root)
        manifest["created"] = []
    for rel in sorted(manifest.get("files", [])):
        if restore(root, rel):
            out.files += 1
            out.changes.append(Change(rel, "file", "modified", "restored"))
        else:
            out.warnings.append("No pristine copy of %s to restore." % rel)
    manifest["files"] = []
    write_manifest(root, manifest)
    return out

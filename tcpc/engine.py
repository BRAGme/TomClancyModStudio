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

from . import inifile, rsexml
from .install import backup_dir_for
from .model import (FileCopy, INPLACE, IniEdit, MOD, XmlAttr, XmlText)

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
        value, err = _resolve_value(e, current)
        what = "[%s] %s%s" % (e.section or "-", e.key,
                              ("." + e.field) if e.field else "")
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


def apply_xml(doc: "rsexml.Doc", edits, rel, out: Result):
    for e in edits:
        is_attr = isinstance(e, XmlAttr)
        current = (doc.get_attr(e.path, e.attr) if is_attr
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
    base = source_root(root, profile)
    names = walk_rel(base) if base and os.path.isdir(base) else []
    out = {}
    for e in edits:
        for rel in expand(names, e.select):
            if not in_scope(rel, e.scope):
                continue
            out.setdefault(rel, []).append(e)
    return out


def in_scope(rel, scope) -> bool:
    """Whether `rel` survives an edit's extra filter.

    A glob alone is sometimes the wrong shape for what an option means.
    Lockdown keeps the player's weapons and the enemy's in the SAME folder,
    told apart only by an `e_` prefix, so `data\\equip\\*.gun` is every gun in
    the game and "your weapon damage" needs to say which half it meant. The
    filter is written as `not:<glob>` or `only:<glob>` against the file name.
    """
    if not scope:
        return True
    verb, _, pattern = scope.partition(":")
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
    edits = profile.build_edits(values) if profile.build_edits else []
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
    else:
        _apply_inplace(root, profile, grouped, out, dry_run, progress)
    out.files = len(grouped)
    return out


def _edit_file(src_bytes_path, rel, edits, out: Result):
    """Load, edit and return the new bytes for one file."""
    ini_edits = [e for e in edits if isinstance(e, IniEdit)]
    xml_edits = [e for e in edits if isinstance(e, (XmlAttr, XmlText))]
    copies = [e for e in edits if isinstance(e, FileCopy)]
    if copies:
        last = copies[-1]
        if last.data is not None:
            return last.data
        with open(last.source, "rb") as fh:
            return fh.read()
    if ini_edits and xml_edits:
        raise ApplyError("%s has both ini and xml edits aimed at it" % rel)
    if ini_edits:
        doc = inifile.Ini.load(src_bytes_path)
        apply_ini(doc, ini_edits, rel, out)
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

    # Rebuild from pristine: put back everything a previous apply changed,
    # INCLUDING files this apply no longer touches. That is what makes
    # clearing an option actually clear it.
    for rel in sorted(touched):
        if not dry_run:
            restore(root, rel)

    now = []
    for i, (rel, edits) in enumerate(sorted(grouped.items())):
        if progress:
            progress(i, len(grouped), rel)
        abs_path = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(abs_path):
            out.warnings.append("%s is not in this installation." % rel)
            continue
        if not dry_run:
            stash(root, rel)
        try:
            data = _edit_file(abs_path, rel, edits, out)
        except (inifile.IniError, rsexml.RseXmlError, OSError) as exc:
            out.ok = False
            out.warnings.append("%s: %s" % (rel, exc))
            continue
        if not dry_run:
            _write(abs_path, data)
            out.verified[rel] = sha1(abs_path)
        now.append(rel)

    if not dry_run:
        manifest["files"] = sorted(set(now))
        manifest["applied"] = time.strftime("%Y-%m-%d %H:%M:%S")
        manifest["game"] = profile.id
        write_manifest(root, manifest)
        # Files that were touched before and are not any more have been
        # restored; their pristine copies stay, because the option may come
        # back and the first copy is the only trustworthy one.


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
            out.warnings.append("%s is not in the stock mod." % rel)
            continue
        try:
            data = _edit_file(src, rel, edits, out)
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
    for rel in sorted(manifest.get("files", [])):
        if restore(root, rel):
            out.files += 1
            out.changes.append(Change(rel, "file", "modified", "restored"))
        else:
            out.warnings.append("No pristine copy of %s to restore." % rel)
    manifest["files"] = []
    write_manifest(root, manifest)
    return out

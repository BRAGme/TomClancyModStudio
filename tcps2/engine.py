"""Applying a settings dict to a disc image, and undoing it again.

Three rules make this safe to run over and over:

  1. Every write starts from the PRISTINE image, never from whatever is on the
     disc now. Applying twice gives the same disc as applying once, and turning
     an option off really removes it.

  2. Nothing is written until the pristine state has been positively
     identified -- by hash for the compressed overlay, and by a recorded
     original for every individual word in an uncompressed executable.

  3. Everything replaced is copied into a `.tcms-backup` folder beside the ISO
     first, so a disc can still be put back a month later.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import time
from dataclasses import dataclass, field

from . import dataedit
from .iso import Iso
from .overlay import OverlayError, open_overlay
from .soz import SozImage

BACKUP_DIR = ".tcms-backup"
WORD_STORE = "code-words.json"


class EngineError(Exception):
    pass


@dataclass
class Plan:
    """What a settings dict would do, before anything is written."""
    game_title: str
    edits: list = field(default_factory=list)     # words baked into the disc
    pnach: list = field(default_factory=list)     # words for the emulator
    data: list = field(default_factory=list)      # archive data-file edits
    warnings: list = field(default_factory=list)
    pristine_source: str = ""

    @property
    def clean(self):
        return not self.warnings

    @property
    def total(self):
        return len(self.edits) + len(self.data)


# ---------------------------------------------------------------------------
# where backups live
# ---------------------------------------------------------------------------

def backup_dir_for(iso_path) -> str:
    root = os.path.join(os.path.dirname(os.path.abspath(str(iso_path))), BACKUP_DIR)
    stem = os.path.splitext(os.path.basename(str(iso_path)))[0]
    return os.path.join(root, stem)


def _overlay_backup(iso_path, overlay_name) -> str:
    return os.path.join(backup_dir_for(iso_path), "%s.orig" % overlay_name)


def _sha1(data) -> str:
    return hashlib.sha1(bytes(data)).hexdigest()


class WordStore:
    """Original values of the individual words we patch in an uncompressed
    executable. Hashing and copying a 37 MB ELF for the sake of a dozen words
    would be silly; recording the words is the same guarantee for 400 bytes."""

    def __init__(self, folder):
        self.path = os.path.join(folder, WORD_STORE)
        self.words = {}
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as fh:
                    self.words = {int(k, 16): v for k, v in json.load(fh).items()}
            except (OSError, ValueError):
                self.words = {}

    def remember(self, va, value):
        self.words.setdefault(va, value)

    def original(self, va):
        return self.words.get(va)

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump({"%08x" % k: v for k, v in self.words.items()}, fh, indent=1)

    def clear(self):
        self.words = {}
        self.save()


# ---------------------------------------------------------------------------
# PCSX2's cheat-file CRC
# ---------------------------------------------------------------------------

def pcsx2_crc(data: bytes) -> str:
    """Every 32-bit word of the boot executable, XORed."""
    n = len(data) // 4
    crc = 0
    for value in struct.unpack_from("<%dI" % n, data, 0):
        crc ^= value
    return "%08X" % crc


def iso_crc(iso: Iso, boot_name: str) -> str:
    ent = iso.find(re.escape("/" + boot_name) + "$")
    if ent is None:
        return ""
    return pcsx2_crc(iso.read(ent.lba, ent.size))


def own_crc_shift(iso: Iso, profile) -> int:
    """How far this tool's own code patches have moved the disc's CRC.

    Two of the seven discs keep their patchable code in the BOOT executable
    itself -- Ghost Recon and Jungle Storm both list their ELF as the overlay --
    and the CRC is an XOR over that file's words. So applying a render option to
    one of those discs changes its CRC, and a plain equality check then reports
    the disc as a different revision and disables the very button that wrote it.

    The XOR makes the correction exact rather than approximate: a word changed
    from `stock` to `value` shifts the CRC by `stock ^ value` and by nothing
    else, wherever in the file it sits. This returns the accumulated shift for
    every word the profile owns that is not currently at its stock value, so a
    caller can XOR it out and compare against the pristine CRC.

    Zero when nothing is patched, and zero for the discs whose overlay is not
    the boot file, since none of their words is inside it.
    """
    stock = profile.stock_words or {}
    boot = [o for o in profile.overlays if o.name.upper() == profile.boot.upper()]
    if not stock or not boot:
        return 0
    try:
        ov = open_overlay(iso, boot[0])
    except Exception:                                 # noqa: BLE001
        return 0
    shift = 0
    for va, want in stock.items():
        try:
            cur = ov.read_word(va)
        except Exception:                             # noqa: BLE001
            return 0
        if cur != want:
            shift ^= cur ^ want
    return shift


# ---------------------------------------------------------------------------
# recovering the pristine overlay
# ---------------------------------------------------------------------------

def load_pristine(iso, iso_path, profile, spec, store=None):
    """(overlay, how) with every word this tool owns back at its stock value."""
    ov = open_overlay(iso, spec)
    stock = profile.stock_words or {}

    if spec.kind == "raw":
        unknown = []
        for va, want in stock.items():
            cur = ov.read_word(va)
            if cur == want:
                continue
            if store is not None and store.original(va) == want:
                ov.write_word(va, want)       # ours from a previous run
                continue
            unknown.append(va)
        if unknown:
            raise EngineError(
                "%s has %d word%s this tool did not write and does not "
                "recognise (first at 0x%08x). Use a clean copy of the disc."
                % (spec.name, len(unknown), "" if len(unknown) == 1 else "s",
                   unknown[0]))
        return ov, "words"

    bak = _overlay_backup(iso_path, spec.name)
    ent = iso.find(spec.iso_pattern)
    if os.path.exists(bak):
        with open(bak, "rb") as fh:
            container = fh.read()
        if len(container) == ent.size:
            img = SozImage.unpack(container, spec.base_va)
            if not spec.image_sha1 or _sha1(img.image) == spec.image_sha1:
                ov.img = img
                return ov, "backup"

    if not spec.image_sha1 or ov.sha1() == spec.image_sha1:
        _save_backup(bak, iso.read(ent.lba, ent.size))
        return ov, "hash"

    changed = 0
    for va, want in stock.items():
        if ov.read_word(va) != want:
            ov.write_word(va, want)
            changed += 1
    if spec.image_sha1 and ov.sha1() == spec.image_sha1:
        _save_backup(bak, ov.container())
        return ov, "repaired"

    raise EngineError(
        "%s has been changed by something other than this tool (%d known words "
        "differed and the image still does not match the stock hash). Restore "
        "the disc from a clean copy before patching." % (spec.name, changed))


def _save_backup(path, container):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "wb") as fh:
            fh.write(container)


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------

def plan(iso_path, profile, values) -> Plan:
    # The warnings are about what the player ASKED for, so they read the values
    # as stored. `effective` neutralises a withdrawn or unmet option, which is
    # right for the builders below and would be exactly wrong here: it would
    # silence the one message that explains why the option is not going to do
    # anything.
    asked = profile.normalise(values)
    values = profile.effective(values)
    warnings = []
    edits = profile.build_edits(values) if profile.build_edits else []
    pn = profile.build_pnach(values) if profile.build_pnach else []
    data = profile.build_data(values) if profile.build_data else []

    for s in profile.settings:
        # Only complain about a setting when it is actually asking for
        # something. "stock", False and 0 all mean "leave this alone", so they
        # are never worth a warning even when their master switch is off -- and
        # neither is a value still sitting on its own default.
        value = asked.get(s.key)
        asking = value not in (None, False, 0, "stock", s.default)
        if not s.enabled and asking:
            warnings.append("%s is disabled in this build: %s"
                            % (s.label, s.disabled_reason))
        if asking and profile.unmet(s.key, asked):
            warnings.append("%s does nothing without: %s"
                            % (s.label, ", ".join(profile.unmet(s.key, asked))))

    how = ""
    if profile.overlays:
        spec = profile.overlays[0]
        store = WordStore(backup_dir_for(iso_path))
        with Iso(iso_path) as iso:
            try:
                ov, how = load_pristine(iso, iso_path, profile, spec, store)
            except (EngineError, OverlayError) as exc:
                warnings.append(str(exc))
                ov = None
            if ov is not None:
                for e in edits:
                    cur = ov.read_word(e.va)
                    if cur != e.stock:
                        warnings.append("0x%08x reads %08x, expected the stock "
                                        "%08x" % (e.va, cur, e.stock))
    if profile.combination_warnings:
        warnings.extend(profile.combination_warnings(values))
    return Plan(profile.title, edits, pn, data, warnings, how)


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------

def apply(iso_path, profile, values, progress=None) -> dict:
    values = profile.effective(values)
    edits = profile.build_edits(values) if profile.build_edits else []
    data = profile.build_data(values) if profile.build_data else []
    folder = backup_dir_for(iso_path)
    store = WordStore(folder)

    def say(msg):
        if progress:
            progress(msg)

    report = {"applied": 0, "verified": 0, "failed": [], "data": {},
              "pristine_source": "", "backup": folder,
              "when": time.strftime("%Y-%m-%d %H:%M:%S")}

    say("Opening %s" % os.path.basename(str(iso_path)))
    with Iso(iso_path, writable=True) as iso:
        if profile.overlays:
            spec = profile.overlays[0]
            say("Recovering the untouched %s" % spec.name)
            ov, how = load_pristine(iso, iso_path, profile, spec, store)
            report["pristine_source"] = how
            for e in edits:
                cur = ov.read_word(e.va)
                if cur != e.stock:
                    raise EngineError("refusing to patch: 0x%08x reads %08x but "
                                      "the stock word is %08x"
                                      % (e.va, cur, e.stock))
                store.remember(e.va, e.stock)
                ov.write_word(e.va, e.value)
            report["applied"] = len(edits)
            if edits or spec.kind == "soz":
                say("Writing %d word%s into %s"
                    % (len(edits), "" if len(edits) == 1 else "s", spec.name))
                ov.store()
            store.save()

        # Run the data pass even with nothing to write: the store may remember
        # files an earlier run edited, and switching every data setting back off
        # has to put those back rather than quietly leave them on the disc.
        dstore = dataedit.Store(folder)
        if data or dstore.entries():
            say("Editing the game's own data files")
            report["data"] = dataedit.apply_data(iso, profile, data, dstore,
                                                 progress=progress)

    say("Verifying against the disc")
    with Iso(iso_path) as iso:
        if profile.overlays:
            ov = open_overlay(iso, profile.overlays[0])
            ok = sum(1 for e in edits if ov.read_word(e.va) == e.value)
            report["verified"] = ok
            report["failed"] = [e for e in edits if ov.read_word(e.va) != e.value]
        if report["data"]:
            good, bad = dataedit.verify_data(iso, profile,
                                             dataedit.Store(folder))
            report["data"]["verified"] = good
            report["data"]["broken"] = bad
    return report


# ---------------------------------------------------------------------------
# revert
# ---------------------------------------------------------------------------

def revert(iso_path, profile, progress=None) -> dict:
    folder = backup_dir_for(iso_path)
    out = {"restored": False, "hash_ok": True, "data": 0}

    def say(msg):
        if progress:
            progress(msg)

    with Iso(iso_path, writable=True) as iso:
        dstore = dataedit.Store(folder)
        if dstore.entries():
            say("Restoring %d data file(s)" % len(dstore.entries()))
            out["data"] = dataedit.revert_data(iso, profile, dstore,
                                               progress=progress)["files"]

        if profile.overlays:
            spec = profile.overlays[0]
            if spec.kind == "raw":
                store = WordStore(folder)
                if not store.words:
                    if not out["data"]:
                        raise EngineError("nothing recorded for this disc -- "
                                          "there is nothing to undo")
                else:
                    say("Restoring %d word(s) in %s" % (len(store.words), spec.name))
                    ov = open_overlay(iso, spec)
                    for va, word in store.words.items():
                        ov.write_word(va, word)
                    ov.store()
                    store.clear()
                out["restored"] = True
            else:
                bak = _overlay_backup(iso_path, spec.name)
                if not os.path.exists(bak):
                    raise EngineError("no backup of %s beside this ISO -- there "
                                      "is nothing to restore from" % spec.name)
                with open(bak, "rb") as fh:
                    container = fh.read()
                ent = iso.find(spec.iso_pattern)
                if ent is None or len(container) != ent.size:
                    raise EngineError("the backup does not match this disc")
                say("Restoring %s" % spec.name)
                iso.write(ent.lba, container)
                iso.flush()
                out["restored"] = True

    with Iso(iso_path) as iso:
        spec = profile.overlays[0] if profile.overlays else None
        if spec and spec.kind == "soz" and spec.image_sha1:
            out["hash_ok"] = open_overlay(iso, spec).sha1() == spec.image_sha1
        elif spec and spec.kind == "raw":
            ov = open_overlay(iso, spec)
            out["hash_ok"] = all(ov.read_word(va) == w
                                 for va, w in (profile.stock_words or {}).items())
    return out


# ---------------------------------------------------------------------------
# emulator cheat file
# ---------------------------------------------------------------------------

BEGIN = "// >>> Tom Clancy PS2 Mod Studio -- managed block, do not edit by hand"
END = "// <<< end managed block"


def pnach_text(profile, words, crc) -> str:
    """Unlabelled patch lines.

    Deliberately unlabelled: a named `[section]` added to a cheat file while the
    game is already running never enters the emulator's enabled set, and there
    is nothing in the interface to tell you. Lines with no section above them
    apply whenever cheats are on for the game.
    """
    lines = ["gametitle=%s (%s) [%s]" % (profile.title, profile.serial, crc), "",
             BEGIN]
    for w in words:
        note = ("   // " + w.note) if w.note else ""
        lines.append("patch=1,EE,%08x,word,%08x%s" % (w.va, w.value, note))
    lines.append(END)
    return "\n".join(lines) + "\n"


#: `patch=<place>,EE,<address>,<type>,<value>`, the only form these files use.
PATCH_LINE = re.compile(r"\s*patch\s*=\s*\d+\s*,\s*EE\s*,\s*([0-9a-fA-F]+)\s*,", re.I)


def write_pnach(path, profile, words, crc) -> str:
    """Write or update a .pnach, preserving any lines outside our block.

    Outside lines that patch an address the managed block also patches are
    dropped rather than kept. A hand-written copy of what the tool now emits is
    the normal case -- these patches started life as notes pasted into the file
    by hand -- and keeping both is not harmless. A `place=1` patch is re-applied
    every vsync, and every write into a page of EE RAM holding recompiled code
    throws that code away and makes the emulator build it again; two copies is
    twice that churn, on game code, during the level load that is already the
    busiest the recompiler ever gets.
    """
    mine = {w.va for w in words}
    kept, superseded = [], 0
    if os.path.exists(path):
        inside = False
        for line in open(path, "r", encoding="utf-8", errors="replace"):
            s = line.rstrip("\n")
            if s.startswith(BEGIN):
                inside = True
                continue
            if s.startswith(END):
                inside = False
                continue
            if inside or s.startswith("gametitle="):
                continue
            m = PATCH_LINE.match(s)
            if m and int(m.group(1), 16) in mine:
                if not superseded:
                    kept.append("// (patch lines for addresses the managed block "
                                "above already sets were removed from here)")
                superseded += 1
                continue
            kept.append(s)
    body = pnach_text(profile, words, crc)
    extra = "\n".join(l for l in kept if l.strip())
    text = body + (("\n" + extra + "\n") if extra else "")
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return path


def find_pcsx2_cheat_dirs() -> list:
    """Plausible PCSX2 cheat folders on this machine, best guess first."""
    out, seen = [], set()

    def add(p):
        p = os.path.normpath(p)
        if p not in seen and os.path.isdir(p):
            seen.add(p)
            out.append(p)

    add(os.path.join(os.path.expanduser("~"), "Documents", "PCSX2", "cheats"))
    for root in ("C:\\", "D:\\", "E:\\", "F:\\"):
        base = os.path.join(root, "Emulators")
        if not os.path.isdir(base):
            continue
        try:
            for name in os.listdir(base):
                if "pcsx2" in name.lower():
                    add(os.path.join(base, name, "cheats"))
        except OSError:
            pass
    return out

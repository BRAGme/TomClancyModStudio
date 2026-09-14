"""Applying a settings dict to a disc image, and undoing it again.

Two rules make this safe to run repeatedly:

  1. Every write rebuilds the overlay from its PRISTINE image, never from
     whatever is on the disc now. Applying twice gives the same disc as
     applying once, and turning an option off really removes it.

  2. Nothing is written until the pristine image has been positively
     identified -- by hash, by a sidecar backup, or by showing that every
     byte that differs from stock is one this tool put there.

The pristine image is cached next to the ISO in a `.tcms-backup` folder the
first time an untouched disc is seen, so a user who patches, plays, and comes
back a month later can still get their disc back.
"""

from __future__ import annotations

import hashlib
import os
import re
import struct
import time
from dataclasses import dataclass

from .iso import Iso
from .soz import SozImage, store_to_iso

BACKUP_DIR = ".tcms-backup"


class EngineError(Exception):
    pass


@dataclass
class Plan:
    """What a settings dict would do, before anything is written."""
    game_title: str
    edits: list            # list[WordEdit] baked into the disc
    pnach: list            # list[WordEdit] delivered as an emulator cheat
    warnings: list
    pristine_source: str   # "hash", "backup" or "repaired"

    @property
    def clean(self) -> bool:
        return not self.warnings


def backup_dir_for(iso_path) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(str(iso_path))), BACKUP_DIR)


def _backup_path(iso_path, overlay_name) -> str:
    stem = os.path.splitext(os.path.basename(str(iso_path)))[0]
    return os.path.join(backup_dir_for(iso_path), "%s.%s.orig" % (stem, overlay_name))


def pcsx2_crc(data: bytes) -> str:
    """The CRC PCSX2 puts in a cheat filename: every 32-bit word XORed."""
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


# ---------------------------------------------------------------------------
# pristine overlay recovery
# ---------------------------------------------------------------------------

def load_pristine(iso: Iso, iso_path, profile, overlay, stock_words) -> tuple:
    """Return (SozImage, how) for the untouched overlay.

    `how` is one of "hash" (the disc is stock), "backup" (recovered from the
    sidecar) or "repaired" (the disc was patched by this tool and every changed
    word was put back).
    """
    ent = iso.find(overlay.iso_pattern)
    if ent is None:
        raise EngineError("%s is not on this disc" % overlay.name)

    bak = _backup_path(iso_path, overlay.name)
    if os.path.exists(bak):
        with open(bak, "rb") as fh:
            container = fh.read()
        if len(container) == ent.size:
            img = SozImage.unpack(container, overlay.base_va)
            if not overlay.image_sha1 or _sha1(img.image) == overlay.image_sha1:
                return img, "backup"

    img = SozImage.unpack(iso.read(ent.lba, ent.size), overlay.base_va)
    if overlay.image_size and len(img.image) != overlay.image_size:
        raise EngineError("%s decompresses to %d bytes, expected %d -- this is "
                          "not the disc revision this profile was built for"
                          % (overlay.name, len(img.image), overlay.image_size))

    if not overlay.image_sha1 or _sha1(img.image) == overlay.image_sha1:
        _save_backup(bak, iso.read(ent.lba, ent.size))
        return img, "hash"

    # Not stock. Only proceed if every difference is at an address this tool
    # owns -- then putting the stock words back restores the pristine image.
    changed = []
    for va, stock in (stock_words or {}).items():
        cur = img.read_word(va)
        if cur != stock:
            changed.append(va)
            img.write_word(va, stock)
    if overlay.image_sha1 and _sha1(img.image) == overlay.image_sha1:
        _save_backup(bak, SozImage(img.image, overlay.base_va, ent.size).pack())
        return img, "repaired"

    raise EngineError(
        "%s has been modified by something other than this tool (%d known "
        "words differed and the image still does not match the stock hash). "
        "Restore the disc from a clean copy before patching."
        % (overlay.name, len(changed)))


def _sha1(data) -> str:
    return hashlib.sha1(bytes(data)).hexdigest()


def _save_backup(path, container):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "wb") as fh:
            fh.write(container)


# ---------------------------------------------------------------------------
# plan / apply
# ---------------------------------------------------------------------------

def plan(iso_path, profile, values) -> Plan:
    values = profile.normalise(values)
    warnings = []
    edits = profile.build_edits(values) if profile.build_edits else []
    pn = profile.build_pnach(values) if profile.build_pnach else []

    for s in profile.settings:
        if not s.enabled and values.get(s.key):
            warnings.append("%s is disabled in this build: %s"
                            % (s.label, s.disabled_reason))
        missing = profile.unmet(s.key, values)
        if missing and values.get(s.key) not in (None, False, s.default):
            warnings.append("%s does nothing without: %s"
                            % (s.label, ", ".join(missing)))

    overlay = profile.overlays[0]
    with Iso(iso_path) as iso:
        stock = _profile_stock(profile)
        img, how = load_pristine(iso, iso_path, profile, overlay, stock)
        for e in edits:
            cur = img.read_word(e.va)
            if cur != e.stock:
                warnings.append("0x%08x reads %08x, expected the stock %08x"
                                % (e.va, cur, e.stock))
    return Plan(profile.title, edits, pn, warnings, how)


def _profile_stock(profile):
    return profile.stock_words or {}


def apply(iso_path, profile, values, progress=None) -> dict:
    """Write the settings to the disc. Returns a small report dict."""
    values = profile.normalise(values)
    overlay = profile.overlays[0]
    stock = _profile_stock(profile)
    edits = profile.build_edits(values) if profile.build_edits else []

    def say(msg):
        if progress:
            progress(msg)

    say("Opening %s" % os.path.basename(str(iso_path)))
    with Iso(iso_path, writable=True) as iso:
        ent = iso.find(overlay.iso_pattern)
        say("Recovering the untouched %s" % overlay.name)
        img, how = load_pristine(iso, iso_path, profile, overlay, stock)

        for e in edits:
            cur = img.read_word(e.va)
            if cur != e.stock:
                raise EngineError("refusing to patch: 0x%08x reads %08x but the "
                                  "stock word is %08x" % (e.va, cur, e.stock))
            img.write_word(e.va, e.value)
        say("Applied %d word%s" % (len(edits), "" if len(edits) == 1 else "s"))

        say("Re-compressing %s" % overlay.name)
        store_to_iso(iso, ent, img)

    # read it straight back out of the disc and count what actually landed
    say("Verifying against the disc")
    with Iso(iso_path) as iso:
        ent = iso.find(overlay.iso_pattern)
        live = SozImage.unpack(iso.read(ent.lba, ent.size), overlay.base_va)
        ok = sum(1 for e in edits if live.read_word(e.va) == e.value)
        bad = [e for e in edits if live.read_word(e.va) != e.value]

    return {
        "applied": len(edits),
        "verified": ok,
        "failed": bad,
        "pristine_source": how,
        "backup": _backup_path(iso_path, overlay.name),
        "when": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def revert(iso_path, profile, progress=None) -> dict:
    """Put the disc back to stock."""
    overlay = profile.overlays[0]
    bak = _backup_path(iso_path, overlay.name)
    if not os.path.exists(bak):
        raise EngineError("no backup of %s next to this ISO -- nothing to "
                          "restore from" % overlay.name)
    with open(bak, "rb") as fh:
        container = fh.read()
    with Iso(iso_path, writable=True) as iso:
        ent = iso.find(overlay.iso_pattern)
        if ent is None:
            raise EngineError("%s is not on this disc" % overlay.name)
        if len(container) != ent.size:
            raise EngineError("backup is %d bytes, the disc reserves %d"
                              % (len(container), ent.size))
        if progress:
            progress("Restoring %s from backup" % overlay.name)
        iso.write(ent.lba, container)
        iso.flush()
    with Iso(iso_path) as iso:
        ent = iso.find(overlay.iso_pattern)
        img = SozImage.unpack(iso.read(ent.lba, ent.size), overlay.base_va)
        ok = (not overlay.image_sha1) or _sha1(img.image) == overlay.image_sha1
    return {"restored": True, "hash_ok": ok}


# ---------------------------------------------------------------------------
# emulator cheat file
# ---------------------------------------------------------------------------

BEGIN = "// >>> Tom Clancy PS2 Mod Studio -- managed block, do not edit by hand"
END = "// <<< end managed block"


def pnach_text(profile, words, crc) -> str:
    """Unlabelled patch lines.

    Deliberately unlabelled: a named `[section]` added to a cheat file while the
    game is already running never enters the emulator's enabled set, and there
    is nothing to tick in the UI to notice. Lines with no section above them
    apply whenever cheats are on for the game.
    """
    lines = ["gametitle=%s (%s) [%s]" % (profile.title, profile.serial, crc), ""]
    lines.append(BEGIN)
    for w in words:
        note = ("   // " + w.note) if w.note else ""
        lines.append("patch=1,EE,%08x,word,%08x%s" % (w.va, w.value, note))
    lines.append(END)
    return "\n".join(lines) + "\n"


def write_pnach(path, profile, words, crc) -> str:
    """Write or update a .pnach, preserving any lines outside our block."""
    kept = []
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
            if not inside and not s.startswith("gametitle="):
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

    docs = os.path.join(os.path.expanduser("~"), "Documents", "PCSX2")
    add(os.path.join(docs, "cheats"))
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

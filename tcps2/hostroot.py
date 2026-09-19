"""The second delivery mode: patch a folder of loose files, not the disc.

Why there are two modes
-----------------------

The normal mode edits the ISO in place. Every edit has to fit: a file may be
replaced by one the same size or smaller, or relocated into a free run
*inside its own archive*, and there is no third option because the archive is
pinned to its ISO extent. On a disc that has been patched a few times there is
often no free run left at all -- measured on a played copy, all three archives
refused to re-home a 17 KB settings file.

`-host` mode lifts that. The game keeps the dev-kit host filesystem in retail
(see `rsehost`), so three words in `SP.SOZ` move the whole vokes layer onto
`host0:`, and the archives become ordinary files in a folder. An ordinary file
can simply get bigger, so `LooseVokes` grows one rather than failing.

What still comes off the disc
-----------------------------

The boot ELF loads `cdrom0:SP.SOZ;1`, so the overlay -- and therefore every
word edit -- still lives in the ISO. That write is one small extent, not a
rebuild, and it is the same write the normal mode already does. The ISO also
still supplies the intro videos and the menu art under `NTSC_CD`. So this mode
is "loose DATA root", not "no disc".

How it is launched
------------------

PCSX2 only sets a host root when it is given an ELF override, and the root
becomes the folder holding that ELF -- an ISO boot leaves it unset and every
`host0:` open fails silently, which looks exactly like the game working
normally. `write_launcher` therefore emits the exact command line, and
`export` puts a copy of the boot ELF in the folder for it to point at.
"""

from __future__ import annotations

import os
import re
import struct

from . import rsehost, vokes
from .iso import Iso

#: the archives that move out of the disc and into the folder
ARCHIVE_RE = re.compile(r"/(VOKES\d|GR|MENU)\.IMG$", re.I)

#: how much room to add when a write does not fit. Generous on purpose: the
#: cost is disc space, and the alternative is growing the file once per edit.
GROW_STEP = 4 << 20

#: what the launcher is called inside the root
LAUNCHER = "Launch loose data root.bat"


class HostRootError(Exception):
    pass


class LooseVokes(vokes.Vokes):
    """A vokes archive that is allowed to get bigger.

    This is the whole difference between the two modes. `Vokes.allocate` ends
    its search at `self.filesize`, which it took from the archive header's own
    word[0] -- so making the file longer and telling the header about it is all
    that is needed for the next allocation to succeed. The new space is zeros,
    which is exactly what `allocate` demands before it will use a run.
    """

    def grow(self, extra: int) -> int:
        extra = max(extra, GROW_STEP)
        extra += -extra % vokes.Vokes.ALIGN
        self.r.write(self.filesize, b"\0" * extra)
        self.filesize += extra
        self.r.write(0, struct.pack("<I", self.filesize))
        return self.filesize

    def write(self, path, data, raw_size=None, home=None):
        try:
            return super().write(path, data, raw_size=raw_size, home=home)
        except vokes.VokesError:
            # Out of room is the ONE failure this mode exists to fix. Anything
            # else -- a path that is not in the archive, a refusal to write
            # over bytes no entry claims -- still has to reach the caller.
            self.grow(len(data))
            return super().write(path, data, raw_size=raw_size, home=home)


class HostRoot:
    """A folder of loose archives, standing in for an ISO in the data pass.

    `dataedit` asks its target for archives and nothing else, so presenting
    that one method is enough for every edit, the backup store, verify and
    revert to run against a folder unchanged.
    """

    def __init__(self, path, writable=False):
        self.path = str(path)
        self.writable = writable
        self._open = []
        if not os.path.isdir(self.path):
            raise HostRootError("%s is not a folder" % self.path)

    def archive_paths(self):
        out = []
        for name in sorted(os.listdir(self.path)):
            if ARCHIVE_RE.search("/" + name):
                out.append(os.path.join(self.path, name))
        return out

    def loose_archives(self, profile):
        """{NAME.IMG: LooseVokes} -- the hook `dataedit._archives` looks for."""
        want = re.compile(profile.archive_pattern or ARCHIVE_RE.pattern, re.I)
        out = {}
        for p in self.archive_paths():
            if not want.search("/" + os.path.basename(p)):
                continue
            region = vokes.Region.from_file(p, writable=self.writable)
            try:
                arc = LooseVokes(region)
            except vokes.VokesError:
                region.close()
                continue
            self._open.append(region)
            out[os.path.basename(p).upper()] = arc
        if not out:
            raise HostRootError("%s holds no vokes archive" % self.path)
        return out

    def close(self):
        for r in self._open:
            r.close()
        self._open = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def is_root(path) -> bool:
    """Does this folder look like an exported data root?"""
    try:
        return bool(HostRoot(path).archive_paths())
    except HostRootError:
        return False


def export(iso_path, dest, progress=None) -> dict:
    """Write every file the game needs into `dest`, archives included.

    The archives are copied by their HEADER size, never the ISO directory's:
    Rainbow Six 3 lists `VOKES0.IMG` with size=1 and is read by LBA, and
    trusting the directory there produces a one-byte file and a game that
    cannot boot.
    """
    def say(m):
        if progress:
            progress(m)

    os.makedirs(dest, exist_ok=True)
    report = {"files": 0, "archives": [], "bytes": 0}
    with Iso(iso_path) as iso:
        entries = sorted(iso.entries().items())
        for path, e in entries:
            if e.is_dir:
                continue
            archive = bool(ARCHIVE_RE.search(path))
            size = e.size
            if archive:                      # the directory size is not to be
                size = struct.unpack(        # trusted for these
                    "<I", iso.read_at(e.offset, 4))[0]
            rel = path.lstrip("/").replace("/", os.sep)
            if archive:
                rel = os.path.basename(rel).lower()
            out = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(out) or dest, exist_ok=True)
            say("  %s (%.1f MB)" % (rel, size / 1048576.0)
                if size > (1 << 20) else "  " + rel)
            done = 0
            with open(out, "wb") as fh:
                while done < size:
                    take = min(1 << 24, size - done)
                    fh.write(iso.read_at(e.offset + done, take))
                    done += take
            report["files"] += 1
            report["bytes"] += size
            if archive:
                report["archives"].append(rel)
    if not report["archives"]:
        raise HostRootError("%s holds no vokes archive to export"
                            % os.path.basename(str(iso_path)))
    return report


def write_launcher(dest, iso_path, exe=None) -> str:
    """The .bat that actually gives PCSX2 a host root."""
    elf = _boot_elf(dest)
    if not elf:
        raise HostRootError("no boot ELF in %s -- export it first" % dest)
    exe = exe or r"<path to>\pcsx2-qt.exe"
    body = LAUNCHER_TEXT % {
        "exe": exe, "elf": elf,
        "iso": os.path.abspath(str(iso_path)),
    }
    out = os.path.join(dest, LAUNCHER)
    with open(out, "w", encoding="ascii", newline="\r\n") as fh:
        fh.write(body)
    return out


def _boot_elf(dest):
    """SLUS_xxx.yy, the file PCSX2 is pointed at."""
    for name in sorted(os.listdir(dest)):
        if re.match(r"^SL[UE]S_\d{3}\.\d{2}$", name, re.I):
            return name
    return None


LAUNCHER_TEXT = """@echo off
REM Boots the game with its data read from THIS folder instead of the disc.
REM
REM The -elf override is not decoration. PCSX2 only sets a host root when it
REM is given one, and the root becomes the folder holding the ELF. Boot the
REM ISO on its own and every host0: open fails silently -- the game still
REM runs, straight off the disc, and none of your edits are in it.
REM
REM Also required, and off by default:
REM   Settings -> Emulation -> Enable Host Filesystem
REM PCSX2 confirms it in logs\\emulog.txt:
REM   HLE Host: Set 'host:' root path to: <this folder>

pushd /d "%%~dp0"
"%(exe)s" -elf "%%~dp0%(elf)s" "%(iso)s"
popd
"""


def supported(profile) -> bool:
    """Only the discs whose overlay carries the switch at these addresses.

    Ghost Recon 2 and Advanced Warfighter carry the same `-host` token in
    their own overlays, so they are the obvious next two -- but their
    addresses have not been found, and a word written at Rainbow Six 3's
    offsets would land in the middle of something else.
    """
    return getattr(profile, "id", "") == "r6_3_slus20883"


def require(profile):
    if not supported(profile):
        raise HostRootError(
            "%s has no loose data root yet -- the switch is in its overlay "
            "but the addresses have not been mapped"
            % getattr(profile, "title", profile))


def enable(iso_path, profile, progress=None) -> dict:
    """Put the three host words into the ISO's overlay.

    They have to be on the disc rather than in a cheat file: the archive mount
    happens during overlay init, before PCSX2 has applied a single frame's
    worth of patches, and before the command-line parse that would otherwise
    set the flag.
    """
    from .overlay import open_overlay

    def say(m):
        if progress:
            progress(m)

    if not supported(profile):
        raise HostRootError("%s has not been mapped for host mode"
                            % getattr(profile, "title", profile))
    words = rsehost.edits()
    with Iso(iso_path, writable=True) as iso:
        ov = open_overlay(iso, profile.overlays[0])
        changed = 0
        for w in words:
            cur = ov.read_word(w.va)
            if cur == w.value:
                continue
            if cur != w.stock:
                raise HostRootError(
                    "0x%08x reads %08x, expected the shipped %08x -- "
                    "refusing to patch" % (w.va, cur, w.stock))
            ov.write_word(w.va, w.value)
            changed += 1
            say("  %s" % w.note)
        if changed:
            ov.store()
    return {"words": len(words), "changed": changed}


def disable(iso_path, profile) -> int:
    """Put the shipped words back, so the disc reads its own archives again."""
    from .overlay import open_overlay

    with Iso(iso_path, writable=True) as iso:
        ov = open_overlay(iso, profile.overlays[0])
        back = 0
        for w in rsehost.edits():
            if ov.read_word(w.va) != w.stock:
                ov.write_word(w.va, w.stock)
                back += 1
        if back:
            ov.store()
    return back

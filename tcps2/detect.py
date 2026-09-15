"""Working out which game a disc image is, and how healthy it is."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .engine import backup_dir_for, iso_crc, own_crc_shift
from .games import BY_BOOT, PROFILES
from .iso import Iso, IsoError


@dataclass
class Detection:
    path: str
    ok: bool
    profile: object = None
    boot: str = ""
    crc: str = ""
    volume: str = ""
    message: str = ""
    crc_matches: bool = True
    #: True when the CRC differs from stock only because of our own code patches
    crc_is_ours: bool = False
    has_backup: bool = False

    @property
    def title(self):
        return self.profile.title if self.profile else "Unrecognised disc"


BOOT_RX = re.compile(r"BOOT2\s*=\s*cdrom0:\\?([A-Za-z0-9_.]+)", re.I)


def identify(path, crc=True) -> Detection:
    """What disc this is.

    `crc=False` skips the two expensive parts -- the PCSX2 CRC, which XORs
    every word of a boot executable that is 37 MB on one of these discs, and
    the check for this tool's own code patches, which has to inflate a
    compressed overlay to read them back. Listing a folder of discs does not
    need either, and with them it takes the better part of a minute.
    """
    path = str(path)
    if not os.path.isfile(path):
        return Detection(path, False, message="File not found.")
    try:
        with Iso(path) as iso:
            cnf = iso.read_text_file(r"/SYSTEM\.CNF$") or ""
            m = BOOT_RX.search(cnf)
            boot = m.group(1).strip() if m else ""
            volume = iso.volume_id
            profile = BY_BOOT.get(boot.upper())
            if profile is None:
                # some discs list the boot file with a different separator
                for p in PROFILES:
                    if iso.find(re.escape("/" + p.boot) + "$"):
                        profile, boot = p, p.boot
                        break
            if profile is None:
                names = ", ".join(sorted(p.serial for p in PROFILES))
                return Detection(path, False, boot=boot, volume=volume,
                                 message="Not a supported disc (boot file %r, "
                                         "volume %r). Supported: %s."
                                         % (boot or "?", volume, names))
            crc = iso_crc(iso, profile.boot) if crc else ""
            shift = own_crc_shift(iso, profile) if crc else 0
            missing = [o.name for o in profile.overlays
                       if iso.find(o.iso_pattern) is None]
    except IsoError as exc:
        return Detection(path, False, message=str(exc))
    except PermissionError:
        return Detection(path, False, message="The file is locked -- close the "
                                              "emulator and try again.")
    except OSError as exc:
        return Detection(path, False, message="Could not read the image: %s" % exc)

    # A disc whose boot executable we have patched no longer has its stock CRC.
    # That is not a different revision, and refusing to patch it again would
    # strand anyone who used a code option once -- so undo our own words first
    # and compare against that.
    crc_ok = (not crc) or (not profile.pcsx2_crc) or \
        crc.upper() == profile.pcsx2_crc.upper()
    ours = False
    if not crc_ok and shift:
        stock_crc = "%08X" % (int(crc, 16) ^ shift)
        ours = stock_crc == profile.pcsx2_crc.upper()
        crc_ok = crc_ok or ours
    msgs = []
    if ours:
        msgs.append("This disc already carries this tool's code patches, which "
                    "is why its CRC reads %s rather than the stock %s. That is "
                    "expected, and it is still the right revision. The cheat "
                    "file is named for the CRC the emulator sees, %s."
                    % (crc, profile.pcsx2_crc, crc))
    elif not crc_ok:
        msgs.append("This is a different revision or region than the profile "
                    "was built for (disc CRC %s, expected %s). Options that "
                    "patch code are unsafe here." % (crc, profile.pcsx2_crc))
    if missing:
        msgs.append("Missing from the disc: %s." % ", ".join(missing))

    folder = backup_dir_for(path)
    bak = (os.path.exists(os.path.join(folder, "code-words.json"))
           or os.path.exists(os.path.join(folder, "data-edits.json"))
           or any(os.path.exists(os.path.join(folder, "%s.orig" % o.name))
                  for o in profile.overlays))
    return Detection(path, True, profile=profile, boot=profile.boot, crc=crc,
                     volume=volume, message=" ".join(msgs),
                     crc_matches=crc_ok, crc_is_ours=ours, has_backup=bak)


def scan_folder(folder, limit=200) -> list:
    """Every supported disc image in a folder, for the 'pick a game' list."""
    out = []
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return out
    for name in names:
        if not name.lower().endswith((".iso", ".bin")):
            continue
        det = identify(os.path.join(folder, name), crc=False)
        if det.ok:
            out.append(det)
        if len(out) >= limit:
            break
    return out


def look(path):
    """(detection, shelf) -- one disc, or the discs sitting in a folder.

    A folder is not a disc, so pointing at one fills the picker rather than
    being an error. Pointing at a disc reads it properly and lists what is
    beside it, because the reason to open one of these is usually to do the
    same thing to the next one.
    """
    path = os.path.abspath(str(path))
    if os.path.isdir(path):
        found = scan_folder(path)
        if found:
            return Detection(path, False,
                             message="%d disc%s here \u2014 pick one from the "
                                     "list." % (len(found),
                                                "" if len(found) == 1 else "s")), found
        return Detection(path, False,
                         message="No supported disc images in this folder."), []
    det = identify(path)
    shelf = scan_folder(os.path.dirname(path)) if det.ok else []
    return det, shelf

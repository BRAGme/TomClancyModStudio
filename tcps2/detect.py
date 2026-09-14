"""Working out which game a disc image is, and how healthy it is."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .engine import backup_dir_for, iso_crc
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
    has_backup: bool = False

    @property
    def title(self):
        return self.profile.title if self.profile else "Unrecognised disc"


BOOT_RX = re.compile(r"BOOT2\s*=\s*cdrom0:\\?([A-Za-z0-9_.]+)", re.I)


def identify(path) -> Detection:
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
            crc = iso_crc(iso, profile.boot)
            missing = [o.name for o in profile.overlays
                       if iso.find(o.iso_pattern) is None]
    except IsoError as exc:
        return Detection(path, False, message=str(exc))
    except PermissionError:
        return Detection(path, False, message="The file is locked -- close the "
                                              "emulator and try again.")
    except OSError as exc:
        return Detection(path, False, message="Could not read the image: %s" % exc)

    crc_ok = (not profile.pcsx2_crc) or crc.upper() == profile.pcsx2_crc.upper()
    msgs = []
    if not crc_ok:
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
                     crc_matches=crc_ok, has_backup=bak)


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
        det = identify(os.path.join(folder, name))
        if det.ok:
            out.append(det)
        if len(out) >= limit:
            break
    return out

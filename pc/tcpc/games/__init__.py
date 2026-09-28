r"""One module per game. Each exports a `PROFILE`.

Seven games, four different problems wearing the same badge. Ghost Recon and
Sum of All Fears run Red Storm's Ike engine and load mod folders, so the tool
writes a mod and never touches a retail byte. The two Advanced Warfighter games
are GRIN's Diesel and keep everything in multi-gigabyte archives, so the tool
reads the archive and writes a loose file that shadows it. Raven Shield and Vegas are Unreal
2 and Unreal 3 and configure through `.ini`. Lockdown is Red Storm again but
without the mod loader, so its loose `data\` tree is edited where it sits.
"""

from . import (ghost_recon, graw, graw2, lockdown, ravenshield, soaf,
               vegas)

PROFILES = [
    ravenshield.PROFILE,
    ghost_recon.PROFILE,
    soaf.PROFILE,
    lockdown.PROFILE,
    vegas.PROFILE,
    graw.PROFILE,
    graw2.PROFILE,
]

BY_ID = {p.id: p for p in PROFILES}

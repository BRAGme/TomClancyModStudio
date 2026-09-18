r"""One module per game. Each exports a `PROFILE`.

The five are two different problems wearing the same badge. Ghost Recon and
Sum of All Fears run Red Storm's Ike engine and load mod folders, so the tool
writes a mod and never touches a retail byte. Raven Shield and Vegas are Unreal
2 and Unreal 3 and configure through `.ini`. Lockdown is Red Storm again but
without the mod loader, so its loose `data\` tree is edited where it sits.
"""

from . import ghost_recon, lockdown, ravenshield, soaf, vegas

PROFILES = [
    ravenshield.PROFILE,
    ghost_recon.PROFILE,
    soaf.PROFILE,
    lockdown.PROFILE,
    vegas.PROFILE,
]

BY_ID = {p.id: p for p in PROFILES}

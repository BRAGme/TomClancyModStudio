"""Game profile registry."""

from __future__ import annotations

from . import (ghost_recon, ghost_recon2, graw, jungle_storm, r6_3,
               soaf)

PROFILES = [r6_3.PROFILE, ghost_recon.PROFILE, jungle_storm.PROFILE,
            ghost_recon2.PROFILE, graw.PROFILE, soaf.PROFILE]

BY_BOOT = {p.boot.upper(): p for p in PROFILES}
BY_ID = {p.id: p for p in PROFILES}

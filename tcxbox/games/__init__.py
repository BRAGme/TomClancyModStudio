"""Game profile registry, keyed by the title id in each disc's own XBE."""

from __future__ import annotations

from . import ghost_recon, ghost_recon2, graw, r6_3

PROFILES = [
    r6_3.RAINBOW_SIX_3,
    r6_3.BLACK_ARROW_PROTOTYPE,
    ghost_recon.GHOST_RECON,
    ghost_recon.ISLAND_THUNDER,
    ghost_recon2.GHOST_RECON_2,
    ghost_recon2.SUMMIT_STRIKE,
    graw.GRAW,
]

BY_TITLE_ID = {p.title_id.upper(): p for p in PROFILES}
BY_ID = {p.id: p for p in PROFILES}

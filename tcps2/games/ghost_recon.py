"""Tom Clancy's Ghost Recon (PS2, SLUS-20613) -- profile.

Ghost Recon PS2 is Red Storm's own engine, not the Unreal build Rainbow Six 3
runs on, so nothing from that profile transfers. Its content lives in two
`GR.IMG` / `MENU.IMG` archives, which use the same read-only filesystem as
Rainbow Six 3's `vokes` images -- that part is confirmed and is what lets this
tool read the game's own artwork.

What is NOT yet confirmed is where the enemy population is controlled. The
archives hold compressed-XML game-type files and a large set of mission and
actor-template files, which is the promising route; the alternative is the
37 MB boot ELF. Until one of those is nailed down this profile deliberately
exposes no gameplay switches rather than shipping guesses.
"""

from __future__ import annotations

from ..model import GameProfile, Overlay

BOOT = "SLUS_206.13"

PROFILE = GameProfile(
    id="ghost_recon_slus20613",
    title="Tom Clancy's Ghost Recon",
    short="Ghost Recon",
    serial="SLUS-20613",
    boot=BOOT,
    volume_hint="GHOST_RECON",
    pcsx2_crc="3E571E95",
    overlays=[
        Overlay(name="SLUS_206.13", iso_pattern=r"/SLUS_206\.13$",
                base_va=0x00100000, kind="raw"),
    ],
    settings=[],
    build_edits=lambda v: [],
    build_pnach=lambda v: [],
    notes=(
        "Ghost Recon's disc reads correctly -- the tool can list all 4,690 "
        "files in GR.IMG and MENU.IMG and pull artwork out of them. Gameplay "
        "options are not available yet: the engine is Red Storm's, not the "
        "Unreal build Rainbow Six 3 uses, so none of that work carries over."
    ),
    ui_art={"archive": "vokes", "patterns": [r"\.RSB$"]},
)

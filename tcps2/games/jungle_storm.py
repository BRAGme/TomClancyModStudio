"""Tom Clancy's Ghost Recon: Jungle Storm (PS2, SLUS-20820) -- profile.

Jungle Storm is the same Red Storm engine as Ghost Recon PS2 with a smaller boot
ELF and two overlay blobs, `OFFLINE.BIN` and `ONLINE.BIN`, in a container that
starts with the ASCII tag `MWo3`. Its `GR.IMG` reads with the same archive code
as Ghost Recon's.

As with Ghost Recon, gameplay switches wait on the research rather than being
guessed at.
"""

from __future__ import annotations

from ..model import GameProfile, Overlay

BOOT = "SLUS_208.20"

PROFILE = GameProfile(
    id="jungle_storm_slus20820",
    title="Tom Clancy's Ghost Recon: Jungle Storm",
    short="Jungle Storm",
    serial="SLUS-20820",
    boot=BOOT,
    volume_hint="SLUS_20820",
    pcsx2_crc="DE1E4DEE",
    overlays=[
        Overlay(name="OFFLINE.BIN", iso_pattern=r"/OFFLINE\.BIN$",
                base_va=0x00692700, kind="raw"),
    ],
    settings=[],
    build_edits=lambda v: [],
    build_pnach=lambda v: [],
    notes=(
        "Jungle Storm's disc reads correctly -- the tool can list all 3,016 "
        "files in GR.IMG and pull artwork out of it. Gameplay options are not "
        "available yet."
    ),
    ui_art={"archive": "vokes", "patterns": [r"\.RSB$"]},
)

"""Ghost Recon Advanced Warfighter (PS2, SLUS-21422) -- profile.

It carries the Ghost Recon name, but this is **not** the Red Storm engine the
other two Ghost Recons run. It is Rainbow Six 3's: volume id `GR3`, Rainbow Six
3's own disc layout down to `VOKES*.IMG` and `GVS.DAT`, and an overlay carrying
Rainbow Six 3's class names -- `AR6GameInfo`, `R6Game.R6CoopStoryModeGame`,
`m_bTerroristHuntGame`, `m_bSurvivalGame`.

That makes it the most promising of the five, because Rainbow Six 3's wave work
may port almost directly. Two differences in its favour: `SP.IMG` and `MP.IMG`
are **plain uncompressed ELFs** rather than the zlib-packed `SP.SOZ`, so they
can be read and patched without a container round-trip; and its wave mode is
shipped and named -- Survival Mode, with `Survival_*` maps and a native
`ScriptSpawnTerrorists` call.

Gameplay options are not offered yet. The disc reads, its files list, and its
artwork loads.
"""

from __future__ import annotations

from ..model import GameProfile, Overlay

BOOT = "SLUS_214.22"

#: the single-player overlay: a plain ELF, unlike Rainbow Six 3's compressed one
SP = Overlay(
    name="SP.IMG",
    iso_pattern=r"/SP\.IMG$",
    base_va=0x00100000,
    kind="raw",
    file_delta=0x80,
)

STOCK = {}

NOTES = (
    "Advanced Warfighter reads correctly -- 508 files across VOKES0, VOKES2 and "
    "MENU.IMG -- and the tool wears its artwork. It has no gameplay options "
    "yet.\n\n"
    "Despite the name this is Rainbow Six 3's engine, not Ghost Recon's: same "
    "volume id, same disc layout, same class names in the overlay. So the wave "
    "work already done for Rainbow Six 3 is the natural starting point, and its "
    "overlays are easier to work with -- SP.IMG and MP.IMG are plain "
    "uncompressed ELFs rather than the zlib-packed SP.SOZ.\n\n"
    "Its wave mode ships as Survival Mode, with its own maps and a native spawn "
    "call, so there is a real mode here to make configurable rather than one to "
    "switch on."
)


PROFILE = GameProfile(
    id="graw_slus21422",
    title="Tom Clancy's Ghost Recon Advanced Warfighter",
    short="Advanced Warfighter",
    serial="SLUS-21422",
    boot=BOOT,
    volume_hint="GR3",
    pcsx2_crc="433B0342",
    overlays=[SP],
    settings=[],
    build_edits=lambda v: [],
    build_pnach=lambda v: [],
    build_data=lambda v: [],
    archive_pattern=r"/(VOKES\d|MENU)\.IMG$",
    stock_words=STOCK,
    notes=NOTES,
    ui_art={"archive": "vokes", "patterns": [r"\.RSB$"]},
)

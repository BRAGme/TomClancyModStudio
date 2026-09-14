"""The Sum of All Fears (PS2, SLES-51180) -- profile.

Red Storm's engine again, the same family as Ghost Recon PS2 and Jungle Storm,
but an earlier build of it and the odd one out on this disc shelf in two ways.

**It ships as a CD image, not a DVD.** The retail rip is MODE2/2352, so the
2,048 bytes of user data sit 24 bytes into each 2,352-byte sector. `tcps2.iso`
detects that and presents a flat logical view, which is what lets the archive
reader work at all.

**Its archives use 40-byte records, not 48.** `SOAF.IMG` (2,420 files) and
`MENU.IMG` (331) are otherwise the familiar layout -- the fields match up to
+0x24 and there is one trailing unknown word instead of three. One real
difference: the two size fields are not always equal here. Where they differ the
second is the DECOMPRESSED length, so this game compresses per entry rather than
relying only on the chunk container the later games use.

Gameplay options are not offered yet. The disc reads, its files list, and its
artwork loads; what the numbers mean is still being worked out.
"""

from __future__ import annotations

from ..model import GameProfile, Overlay

BOOT = "SLES_511.80"

ELF = Overlay(
    name=BOOT,
    iso_pattern=r"/SLES_511\.80$",
    base_va=0x00100000,
    kind="raw",
    file_delta=0x80,
    file_span=0x004A5780 + 0x80,
)

STOCK = {}

NOTES = (
    "The Sum of All Fears reads correctly -- 2,751 files across SOAF.IMG and "
    "MENU.IMG -- and the tool wears its artwork. It has no gameplay options "
    "yet.\n\n"
    "Two things about this disc are unlike the others. It is a CD image rather "
    "than a DVD, so its sectors are 2,352 bytes with the real data 24 bytes in; "
    "and its archive records are 40 bytes rather than 48, with the second size "
    "field holding a decompressed length instead of repeating the first.\n\n"
    "It is the same Red Storm engine as Ghost Recon and Jungle Storm, so the "
    "mission and template formats that made those two editable are the obvious "
    "place to look next."
)


PROFILE = GameProfile(
    id="soaf_sles51180",
    title="Tom Clancy's The Sum of All Fears",
    short="Sum of All Fears",
    serial="SLES-51180",
    boot=BOOT,
    volume_hint="SOAF",
    pcsx2_crc="4691F6F7",
    overlays=[ELF],
    settings=[],
    build_edits=lambda v: [],
    build_pnach=lambda v: [],
    build_data=lambda v: [],
    archive_pattern=r"/(SOAF|MENU)\.IMG$",
    stock_words=STOCK,
    notes=NOTES,
    ui_art={"archive": "vokes", "patterns": [r"\.RSB$"]},
)

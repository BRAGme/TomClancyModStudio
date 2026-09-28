"""Rainbow Six: Critical Hour -- recognised, and honestly empty.

This game is on the shelf and the tool identifies it, so it is here rather than
quietly missing. It has no options, and the reason is not that nobody looked.

Critical Hour is not a Rainbow Six 3 build. Its disc has two folders, `Media`
and `XboxData`, and **nothing in it is text**. A census of all 19,085 entries:

  * no `.ini` at all -- not one, where Rainbow Six 3 has 38 and GRAW 40;
  * no `R6GameSettings`, no `.tpt` terrorist templates, no `.umd` bundle;
  * no `.glb` globs, no `.atr`, `.gun`, `.kit`, `.wsf`, `.gtf` or `.cgs`;
  * its 146 `.MIS` files are **cooked binary** -- length-prefixed strings and
    packed floats, not the XML every other Red Storm game on this shelf ships;
  * 7,378 `.PDS` and 8,016 `.DDS` are art, 172 `.LIN` are Magma menu packages,
    and the `.DAT` beside each map is a navigation mesh: a list of coordinates.

The one XML file on the whole disc is `Model\\attachment_table.atf`, which maps
attachment points to models -- a knife to a knife mesh. There is no number in it
anyone would want to change.

So every option this tool offers elsewhere reaches nothing here. Adding a page
of controls that silently did nothing would be worse than this: the card below
says what was looked for and where a future version would have to start, which
is the binary `.MIS` format and the `.PDS` files beside it.
"""

from __future__ import annotations

from ..model import BOOL, GameProfile, Marker, Setting

NOTES = (
    "Critical Hour is recognised but has nothing this tool can safely change "
    "yet, and that is a finding rather than an omission.\n\n"
    "Every other game here keeps its interesting numbers in text -- XML "
    "missions, ini tables, skill templates. Critical Hour ships none. All "
    "19,085 entries on the disc were listed: no ini files at all, no terrorist "
    "templates, no globs, and its 146 mission files are cooked binary rather "
    "than the XML the other Red Storm games use.\n\n"
    "The only XML on the disc is Model\\attachment_table.atf, which says which "
    "model hangs off which attachment point.\n\n"
    "Making this game moddable means reverse-engineering the binary .MIS "
    "format and the .PDS files beside it. Until that is done, showing you a "
    "page of dials that quietly did nothing would be the worse answer."
)

CRITICAL_HOUR = GameProfile(
    id="critical_hour_xbox",
    title="Tom Clancy's Rainbow Six: Critical Hour",
    short="Critical Hour",
    title_id="5553005F",
    markers=[Marker("XboxData", "the game's data folder"),
             Marker("XboxData/Mission", "the cooked mission files")],
    settings=[
        Setting("ch_nothing_yet", "Options for this game", BOOL, False,
                "About", enabled=False, confidence="broken",
                disabled_reason=(
                    "Nothing on this disc is text. No ini files, no terrorist "
                    "templates, no globs, and the 146 mission files are cooked "
                    "binary rather than the XML every other Red Storm game "
                    "here ships. The whole disc was listed to establish that."),
                help="Where this game's options would go. See About this game "
                     "for the census they came from."),
    ],
    build_data=lambda v: [],
    notes=NOTES,
    ui_art={
        "backdrop": "XboxData/Magma/Textures/BG/P_CUSTOMTEX/BG_GRADLOBBY.dds",
        # the one logo on this shelf printed dark on white
        "emblem":
            "XboxData/Magma/Textures/BG/P_COMMONTEX/LOGO_RAINBCRITICAL.dds",
        "emblem_polarity": "dark",
        "emblem_key": (70, 185)},
)

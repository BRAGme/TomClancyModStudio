"""Rainbow Six 3 on Xbox, and Black Arrow.

Both look unmoddable and are not. `System\\` holds 98 cooked `.lin` packages and
two ini files, and the interesting ones are not among them -- they are inside
`System\\xboxdynamic.umd`, a 2.4 MB bundle of 536 files carrying the 16 KB
gameplay table, 37 more ini files and all 115 terrorist templates. `tcxbox.umd`
opens it and `gamedir` writes into it in place, so from these pages it looks
like any other folder. Black Arrow is the same disc again with a little more of
it: 120 templates and 42 ini files.

They get the same cards because it is the same table -- 240 keys, identical in
both -- and the templates differ only in which weapon each one carries.

Black Arrow's *prototype* disc carries the same title id, `55530037`, so one
profile serves both. That is the right answer rather than a shortcut: the
selectors here name files, not places. The prototype is a demo *installer* --
`default.xbe` at its top is Microsoft's stub with title id FFFFFF00, and the
game sits under `Files\\Black_Arrow_XBOX_media` with its executable still called
`RainbowSix3_Release.xbe` and its title name still reading "Rainbow Six White
Release E:\\XBox\\Folder". Nothing on it is bundled, so the same edits land on
loose files instead, and identification walks down to find it.
"""

from __future__ import annotations

from ..model import CHOICE, INT, Choice, FileEdit, GameProfile, Marker, Setting
from . import r6engine

RENDER = "Picture"
RULES = "Rules"

XBOX_INI = r"RAINBOWSIX3XBOX\.INI$"

#: (key, on, off) for the D3D switches worth exposing. Every one of these is
#: already in the shipped file, so this only ever writes a value a line has.
D3D_TOGGLES = (
    ("UseTrilinear", "Trilinear filtering",
     "Ships on. Off gives the harder mip transitions the PS2 build has."),
    ("UseCubemaps", "Cube map reflections", "Ships on."),
    ("UseCompressedLightmaps", "Compressed lightmaps",
     "Ships on. Off is more memory for smoother lighting gradients."),
    ("UseVSync", "Vertical sync", "Ships off."),
    ("UseTripleBuffering", "Triple buffering", "Ships off."),
    ("HighDetailActors", "High detail actors", "Ships on."),
)


def _render_cards(prefix):
    out = [
        Setting(prefix + "texture_lod", "Texture detail", CHOICE, "stock",
                RENDER, confidence="applied",
                choices=[
                    Choice("stock", "As shipped (min 6, max 9)", ""),
                    Choice("full", "Full resolution (min 0, max 12)",
                           "Every texture at its top mip."),
                    Choice("low", "Lower (min 8, max 9)", ""),
                ],
                help="The Xbox client clamps every texture to mip levels 6 "
                     "through 9, which is the memory budget of a 64 MB console "
                     "and not a limit of the art. Opening it up is the single "
                     "most visible change on this page, and it is the one worth "
                     "making before capturing anything.",
                caution="This is a memory setting. On real hardware the full "
                        "range may not fit; under an emulator it generally "
                        "does. It writes both the Xbox and the Windows client "
                        "sections, because the file carries the same key twice "
                        "and only one of them is read."),
        Setting(prefix + "gore", "Gore level", CHOICE, "stock", RENDER,
                confidence="applied",
                choices=[Choice("stock", "As shipped (0)", ""),
                         Choice("1", "1", ""), Choice("2", "2", ""),
                         Choice("3", "3", "")],
                help="[Engine.GameInfo] GoreLevel ships at 0. The field is the "
                     "engine's own and higher values are what the PC build "
                     "uses; what each step does here has not been watched.",
                caution="Untested on this platform."),
        Setting(prefix + "game_speed", "Game speed", INT, 100, RULES,
                minimum=25, maximum=300, unit="%", confidence="applied",
                help="[Engine.GameInfo] GameSpeed, which ships at 1.0. This is "
                     "the whole simulation, not an animation rate.",
                caution="Well away from 100% will desynchronise anything "
                        "networked."),
        Setting(prefix + "console", "Enable the developer console", CHOICE,
                "stock", RULES, confidence="experimental",
                choices=[Choice("stock", "As shipped", ""),
                         Choice("on", "Bind it to the tilde key", "")],
                help="[Engine.Console] ConsoleKey ships at 192, which is the "
                     "tilde key already -- so the binding is there and what is "
                     "unknown is whether this build has a keyboard path to "
                     "reach it. The gameplay table's own comment says you open "
                     "the console and type REFRESHGAMESETTINGS, so the "
                     "developers plainly could.",
                caution="Writes the key the file already holds; it is here "
                        "because the option is worth documenting, not because "
                        "it has been seen to work."),
    ]
    for key, label, help_text in D3D_TOGGLES:
        out.append(Setting(
            prefix + "d3d_" + key.lower(), label, CHOICE, "stock", RENDER,
            confidence="applied",
            choices=[Choice("stock", "As shipped", ""),
                     Choice("True", "On", ""), Choice("False", "Off", "")],
            help=help_text))
    return out


def _render_edits(prefix, v):
    values = {}
    lod = v.get(prefix + "texture_lod", "stock")
    if lod == "full":
        values.update({"TextureMinLOD": "0", "TextureMaxLOD": "12"})
    elif lod == "low":
        values.update({"TextureMinLOD": "8", "TextureMaxLOD": "9"})
    gore = v.get(prefix + "gore", "stock")
    if gore != "stock":
        values["GoreLevel"] = gore
    speed = int(v.get(prefix + "game_speed", 100))
    if speed != 100:
        values["GameSpeed"] = "%.6f" % (speed / 100.0)
    if v.get(prefix + "console") == "on":
        values["ConsoleKey"] = "192"
    for key, _label, _help in D3D_TOGGLES:
        choice = v.get(prefix + "d3d_" + key.lower(), "stock")
        if choice != "stock":
            values[key] = choice
    if not values:
        return []
    return [FileEdit("ini_values", XBOX_INI, {"values": values},
                     "client settings: " + ", ".join(sorted(values)))]


def _settings(prefix):
    return r6engine.cards(prefix, has_templates=True) + _render_cards(prefix)


def _build(prefix):
    def build(v):
        return r6engine.edits(prefix, v, has_templates=True) + _render_edits(prefix, v)
    return build


RETAIL_NOTES = (
    "Rainbow Six 3's real System folder is inside System\\xboxdynamic.umd -- "
    "536 files, including the 16 KB gameplay table and all 115 terrorist "
    "templates. This tool opens that bundle and writes into it at the byte each "
    "file already occupies, so nothing in its index moves and the file the game "
    "loads is the file you edited.\n\n"
    "RainbowSix3Xbox.ini exists twice, loose and bundled, and the two are not "
    "the same file -- 5,393 bytes against 5,155. Both are written, because "
    "editing only the loose one is a real way to change nothing.\n\n"
    "The gameplay table is live: its own comments tell you to type "
    "REFRESHGAMESETTINGS in the console to reload it. That is why the dials on "
    "these pages are badged as applied rather than as experiments."
)

BLACK_ARROW_NOTES = (
    "Black Arrow keeps its real System folder inside System\\xboxdynamic.umd, "
    "the same way Rainbow Six 3 does, and ships a little more of it: 120 "
    "terrorist templates and 42 ini files against 115 and 38. Everything on "
    "these pages reaches into that bundle and writes at the byte each file "
    "already occupies.\n\n"
    "The prototype disc that circulates carries the same title id, so this "
    "profile loads it too. That one is a demo installer -- the game is under "
    "Files\\Black_Arrow_XBOX_media and its executable is still called "
    "RainbowSix3_Release.xbe -- and nothing on it is bundled, so the same "
    "edits land on loose files instead. Point the tool at either.\n\n"
    "The gameplay table is live: its own comments tell you to type "
    "REFRESHGAMESETTINGS in the console to reload it. That is why the dials on "
    "these pages are badged as applied rather than as experiments."
)

RAINBOW_SIX_3 = GameProfile(
    id="rainbow_six_3_xbox",
    title="Tom Clancy's Rainbow Six 3",
    short="Rainbow Six 3",
    title_id="55530013",
    markers=[Marker("System", "the cooked packages and the bundle"),
             Marker("System/xboxdynamic.umd", "the gameplay table and the "
                                              "terrorist templates")],
    settings=_settings("r63_"),
    build_data=_build("r63_"),
    notes=RETAIL_NOTES,
    ui_art={"backdrop": "Splash.tga", "emblem": "Splash.tga"},
)

BLACK_ARROW = GameProfile(
    id="black_arrow_xbox",
    title="Tom Clancy's Rainbow Six 3: Black Arrow",
    short="Black Arrow",
    title_id="55530037",
    markers=[Marker("System", "the cooked packages and the bundle")],
    settings=_settings("ba_"),
    build_data=_build("ba_"),
    notes=BLACK_ARROW_NOTES,
    # Black Arrow's wordmark is printed on a lit amber panel rather than on
    # black, so its ramp sits much higher than Rainbow Six 3's.
    ui_art={"backdrop": "Splash.tga", "emblem": "Splash.tga",
            "emblem_key": (135, 225)},
)

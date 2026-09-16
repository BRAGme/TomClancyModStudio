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
                caution="This is a memory setting: the console had 64 MB and "
                        "this spends it. Under xemu there is more room than the "
                        "hardware had, which is where this is worth trying "
                        "first. It writes both the Xbox and the Windows client "
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
        # Shipped disabled rather than merely cautioned. ConsoleKey already
        # holds 192, so switching this on rewrote the value that was there and
        # reported success -- an option that cannot fail and cannot do
        # anything. It stays as a card because what it documents is true and
        # useful; it just no longer pretends to be a lever.
        Setting(prefix + "console", "Enable the developer console", CHOICE,
                "stock", RULES, enabled=False,
                disabled_reason="Nothing to write: ConsoleKey is already 192. "
                                "Whether this build has a keyboard path to "
                                "the console is the open question, and this "
                                "card cannot change it either way.",
                choices=[Choice("stock", "As shipped", ""),
                         Choice("on", "Bind it to the tilde key", "")],
                help="[Engine.Console] ConsoleKey ships at 192, which is the "
                     "tilde key already -- so the binding is there and what is "
                     "unknown is whether this build has a keyboard path to "
                     "reach it. The gameplay table's own comment says you open "
                     "the console and type REFRESHGAMESETTINGS, so the "
                     "developers plainly could.",
                ),
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


MODES = "Game modes"

#: Every mission description under `Maps\\` carries a block the file itself
#: labels "Availability of Game Modes" -- one boolean per mode, and that block
#: is what the menus read to decide which maps appear under which heading.
#:
#: The shipped split is strict and, once seen, plainly a content decision
#: rather than a technical one. On Rainbow Six 3, all fourteen campaign maps
#: allow Story, Co-op Story, Terrorist Hunt, Terrorist Hunt Co-op, Practice and
#: No Rules, and every one of them has Survival, Team Survival and Sharpshooter
#: turned OFF. The nine multiplayer maps are the exact mirror: Survival, Team
#: Survival, Sharpshooter and No Rules on, Terrorist Hunt and Practice off.
#: Eighteen of the twenty-eight maps have Survival off; thirteen have Terrorist
#: Hunt off.
#:
#: One file gives the game away. `_Debug.ini`, whose map is called `rooms`, has
#: every single flag set true -- the developers' own map, with the whole menu
#: unlocked. Nothing in the format stops any other map from looking like that.
#:
#: Black Arrow has the same block plus three more modes, and is stingier still:
#: Shooting Ground is enabled on two of its thirty-three maps.
SP_MAPS = r"/MAPS/(?!R6MENU|_DEBUG|AUTOPLAY|RAVENSHIELD)(?!.*_MP\.)[^/]+\.INI$"
MP_MAPS = r"/MAPS/[^/]*_MP\.INI$"
ANY_MAP = r"/MAPS/(?!R6MENU|AUTOPLAY|RAVENSHIELD)[^/]+\.INI$"

#: The modes a multiplayer map is allowed and a campaign map is not.
MP_MODES = {"m_bSurvivalGame": "true", "m_bTeamSurvivalGame": "true",
            "m_bSharpShooterGame": "true", "m_bTeamCaptureGame": "true",
            "m_bTeamConquestGame": "true"}

#: ...and the reverse. Practice rides with the hunt because it is the mode that
#: puts you on a map alone with nothing shooting back, which is the useful
#: thing to have on a map you have only ever played against people.
SOLO_MODES = {"m_bTerroristHuntGame": "true", "m_bTerroristHuntCoopGame": "true",
              "m_bPracticeModeGame": "true"}

#: Everything the two discs between them define. `set_ini_values` only rewrites
#: keys a file already has, so the three Black Arrow-only names simply do
#: nothing on a Rainbow Six 3 disc rather than being added to it.
EVERY_MODE = dict(MP_MODES, **SOLO_MODES)
EVERY_MODE.update({"m_bStoryModeGame": "true", "m_bCoopStoryModeGame": "true",
                   "m_bNoRulesGame": "true", "m_bShootingGroundGame": "true"})


def _mode_cards(prefix):
    return [
        Setting(prefix + "modes", "Which modes each map allows", CHOICE,
                "stock", MODES,
                choices=[
                    Choice("stock", "As shipped", ""),
                    Choice("mp_on_campaign", "Multiplayer modes on the "
                           "campaign maps",
                           "Survival, Team Survival and Sharpshooter."),
                    Choice("solo_on_mp", "Terrorist Hunt on the multiplayer "
                           "maps", "And Practice with it."),
                    Choice("both", "Both of the above", ""),
                    Choice("everything", "Every mode on every map", ""),
                ],
                confidence="experimental",
                help="Each map's mission description holds a block the file "
                     "calls \"Availability of Game Modes\" -- one true or "
                     "false per mode -- and the menus read it to decide which "
                     "maps to list where. The shipped split is absolute: "
                     "every campaign map has Survival, Team Survival and "
                     "Sharpshooter off, and every multiplayer map has "
                     "Terrorist Hunt and Practice off.\n\n"
                     "The disc argues this is a choice rather than a limit: "
                     "_Debug.ini, the developers' own map, ships with every "
                     "flag true.",
                caution="Experimental, and the risk is specific. A mode needs "
                        "the spawn points it uses: Terrorist Hunt places "
                        "terrorists from a map's own spawn list, and a "
                        "multiplayer map that has none will start empty. "
                        "Nothing here can corrupt a save -- if a map is no "
                        "use in a mode, it is simply no use."),
        Setting(prefix + "silenced", "Silenced loadout on every mission",
                CHOICE, "stock", MODES,
                choices=[Choice("stock", "As shipped", ""),
                         Choice("true", "Silenced everywhere", "")],
                confidence="applied",
                help="m_bMissionModeUseSilencedEquipment picks which of the "
                     "two loadouts each mission description carries -- the "
                     "assault rifle or the suppressed UMP. Rainbow Six 3 "
                     "turns it on for two maps out of twenty-eight and Black "
                     "Arrow for none of thirty-three, although every mission "
                     "description on both discs spells out a full silenced "
                     "kit that is never used."),
    ]


def _mode_edits(prefix, v):
    choice = v.get(prefix + "modes", "stock")
    out = []
    if choice == "everything":
        out.append(FileEdit("ini_values", ANY_MAP, {"values": EVERY_MODE},
                            "every game mode enabled on every map"))
    else:
        if choice in ("mp_on_campaign", "both"):
            out.append(FileEdit("ini_values", SP_MAPS, {"values": MP_MODES},
                                "multiplayer modes on the campaign maps"))
        if choice in ("solo_on_mp", "both"):
            out.append(FileEdit("ini_values", MP_MAPS, {"values": SOLO_MODES},
                                "Terrorist Hunt and Practice on the "
                                "multiplayer maps"))
    if v.get(prefix + "silenced") == "true":
        out.append(FileEdit("ini_values", SP_MAPS,
                            {"values": {"m_bMissionModeUseSilencedEquipment":
                                        "true"}},
                            "silenced loadout on every mission"))
    return out


#: Every cooked level package, and `Common.lin` with them. The skin packages
#: are excluded because they carry no actors at all, so matching them would
#: only mean decompressing forty more megabytes to find nothing.
LEVEL_FILES = r"/SYSTEM/(?!.*_SKINS)[^/]+\.LIN$"

#: choice -> factor for the hunt-count dial.
HUNT_STEPS = {"less": 0.5, "more": 1.5, "double": 2.0, "triple": 3.0,
              "max": 6.0}


def _hunt_cards(prefix):
    return [
        Setting(prefix + "hunt_count", "Terrorists in a Terrorist Hunt",
                CHOICE, "stock", MODES,
                choices=[Choice("stock", "As shipped", ""),
                         Choice("less", "Half", ""),
                         Choice("more", "Half again", ""),
                         Choice("double", "Double", ""),
                         Choice("triple", "Triple", ""),
                         Choice("max", "Six times", "Clamped at 100 a zone.")],
                confidence="experimental",
                help="The spawn counts on every deployment zone -- the actor "
                     "Terrorist Hunt fills a map from, and the one a wave "
                     "draws from. They are in no ini; they sit inside the "
                     "cooked .LIN level packages, which is why nothing "
                     "reaches them.\n\n"
                     "Two dials move together. Most zones carry no count at "
                     "all and fall back to the class default in Common.lin, "
                     "which ships at 1 and 1; the rest override it per zone, "
                     "and this disc's largest is 12. Scaling both is what "
                     "makes one choice mean one thing everywhere.\n\n"
                     "A zone that ships zero stays zero -- zero means the "
                     "zone contributes nobody, and no multiplier changes "
                     "that.",
                caution="Experimental: verified as bytes, not watched in "
                        "game. It is also the one option here that backs up "
                        "whole level packages -- about 140 MB on Rainbow Six "
                        "3, 53 MB on Black Arrow -- because that is what a "
                        "level is. Counts are clamped to 100, and Restore "
                        "game puts the packages back byte for byte."),
    ]


def _hunt_edits(prefix, v):
    choice = v.get(prefix + "hunt_count", "stock")
    if choice not in HUNT_STEPS:
        return []
    return [FileEdit("hunt_scale", LEVEL_FILES,
                     {"factor": HUNT_STEPS[choice]},
                     "terrorist hunt spawn counts at %d%%"
                     % int(HUNT_STEPS[choice] * 100))]


def _settings(prefix, aim, has_boost=False):
    return (r6engine.cards(prefix, has_templates=True, aim=aim,
                           has_boost=has_boost)
            + _mode_cards(prefix) + _hunt_cards(prefix)
            + _render_cards(prefix))


def _build(prefix, aim, has_boost=False):
    def build(v):
        return (r6engine.edits(prefix, v, has_templates=True, aim=aim,
                               has_boost=has_boost)
                + _mode_edits(prefix, v)
                + _hunt_edits(prefix, v)
                + _render_edits(prefix, v))
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
    settings=_settings("r63_", r6engine.R63_AIM),
    build_data=_build("r63_", r6engine.R63_AIM),
    notes=RETAIL_NOTES,
    ui_art={"backdrop": "Splash.tga", "emblem": "Splash.tga"},
)

BLACK_ARROW = GameProfile(
    id="black_arrow_xbox",
    title="Tom Clancy's Rainbow Six 3: Black Arrow",
    short="Black Arrow",
    title_id="55530037",
    markers=[Marker("System", "the cooked packages and the bundle")],
    settings=_settings("ba_", r6engine.BA_AIM, has_boost=True),
    build_data=_build("ba_", r6engine.BA_AIM, has_boost=True),
    notes=BLACK_ARROW_NOTES,
    # Black Arrow's wordmark is printed on a lit amber panel rather than on
    # black, so its ramp sits much higher than Rainbow Six 3's.
    ui_art={"backdrop": "Splash.tga", "emblem": "Splash.tga",
            "emblem_key": (135, 225)},
)

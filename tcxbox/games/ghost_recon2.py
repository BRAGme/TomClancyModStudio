"""Ghost Recon 2 and Summit Strike on Xbox.

The same engine family as the first two games -- same XML, same globs, same
combat model -- but the parts that hold the *enemies* were rebuilt, and that
changes what this page can honestly offer.

What went away:

  * **No order of battle in the mission file.** A Ghost Recon `.MIS` carries a
    `<Units>` block of `<Actor>` elements with a difficulty flag on each. A
    Ghost Recon 2 `.MIS` carries Igor placement objects and zones -- 83 of them
    in a typical level, all `IgorId`/`ScriptId`/`Pos0`/`Pos1` -- and not one
    `Easy="0"` anywhere in either game. So there is nothing to un-suppress.
  * **No `.atr` templates.** The enemy is a `.CGS` character game set, and those
    hold four lines: type, voice, name and version. The numbers moved into the
    engine.
  * **No allied flag.** With no `<Company Allied="1">` and no per-actor `Kit`,
    there is no way to tell the player's weapons from the enemy's, so the
    weapons page here is one honest set of dials over every gun rather than two
    that claim a split the data cannot support.

What is still there, and is worth having:

  * **The combat model.** `CMBTMODL.XML` survives unchanged in shape, with
    heavier numbers than the first game -- chest 800 against 300, lower arm
    3000 against 1500 -- and it is still the whole hit model for everybody.
    Both copies are edited: these games ship it loose under `equip\\` *and*
    inside `globs\\ikedata.glb`.
  * **The weapons.** 114 `.GUN` files in Ghost Recon 2, 162 in Summit Strike,
    in the same XML as before.
  * **The dedicated-server scripts.** `script\\*.ass` is where these games keep
    the rules that used to be script variables: friendly fire, arcade mode, AI
    backup, first-person-only, the threat indicator, the radar, respawns and
    the difficulty index. They are plain XML and they exist only loose, so
    unlike everything else here they may change length freely.
"""

from __future__ import annotations

from ..model import (BOOL, CHOICE, INT, Choice, FileEdit, GameProfile, Marker,
                     Setting)
from . import rseweapons, rstuning

RULES = "Rules"

#: (tag, label, help) for the plain on/off rules in the .ASS scripts. Every one
#: of these was read out of the shipped files; `TRUE`/`FALSE` is the spelling
#: they use, and writing the other one is the whole edit.
TOGGLES = (
    ("FriendlyFireLethal", "Friendly fire is lethal",
     "Ships TRUE on some scripts and FALSE on others. Forcing it one way makes "
     "every game type agree."),
    ("ArcadeMode", "Arcade mode",
     "Ships FALSE everywhere. The game has the switch; what it does has not "
     "been watched."),
    ("AIBackup", "AI teammates in multiplayer",
     "Ships FALSE everywhere. This is the flag that decides whether a "
     "multiplayer side is filled out with AI."),
    ("FirstPersonOnly", "First person only",
     "Ships FALSE everywhere -- the game is third person by default and this "
     "locks it to the first-person view."),
    ("ThreatIndicator", "Threat indicator",
     "Ships FALSE everywhere. The on-screen warning when you are being aimed "
     "at."),
    ("AllowObservers", "Allow observers", ""),
    ("WeaponSwappingAllowed", "Let players swap weapons", ""),
    ("RandomZones", "Randomise the zones a mission uses",
     "Ships FALSE. With it on, a mission draws different spawn and patrol "
     "zones each time -- the closest thing these games have to a replayability "
     "switch."),
)


def _settings(prefix, guns, name):
    out = [
        Setting(prefix + "no_difficulty_dial", "Every soldier on every difficulty",
                BOOL, False, "Enemies", enabled=False, confidence="broken",
                disabled_reason=(
                    "%s has no per-actor difficulty flags to delete. Its "
                    "mission files hold Igor placement objects and zones, not "
                    "an order of battle -- there is no Easy=\"0\" anywhere in "
                    "the game. The first two Ghost Recons do it that way and "
                    "this one does not." % name),
                help="The first two Ghost Recons' biggest lever, and the "
                     "reason it is not available here."),
        Setting(prefix + "no_tier_dial", "Enemy skill tier", BOOL, False,
                "Enemies", enabled=False, confidence="broken",
                disabled_reason=(
                    "There are no `.atr` skill templates in this game. An "
                    "enemy is a `.cgs` character game set and those carry four "
                    "lines -- type, voice, name and version. The numbers the "
                    "tier dial moved on Ghost Recon moved into the engine."),
                help="Where the recruit/veteran/elite ladder would be."),
        rstuning.lethality_card(prefix),
    ]
    out += rseweapons.shared_cards(prefix)
    out += [
        Setting(prefix + "difficulty", "Difficulty index in the server scripts",
                CHOICE, "stock", RULES, confidence="experimental",
                choices=[
                    Choice("stock", "As shipped (0)", ""),
                    Choice("1", "1", ""),
                    Choice("2", "2", ""),
                    Choice("3", "3", ""),
                ],
                help="Every shipped script carries <Difficulty>0</Difficulty>. "
                     "The field is real and it is written; what the engine does "
                     "with each value has not been watched, which is why the "
                     "options are numbers rather than names.",
                caution="Untested. Turn it on by itself."),
        Setting(prefix + "invuln", "Spawn protection", INT, 0, RULES,
                minimum=0, maximum=60, unit="seconds", confidence="applied",
                help="<InvulnerabilityTimer> in the server scripts, which ship "
                     "5 and 10 seconds depending on the mode. Zero here leaves "
                     "each script's own value alone; anything else sets them "
                     "all."),
    ]
    for tag, label, help_text in TOGGLES:
        out.append(Setting(
            prefix + "rule_" + tag.lower(), label, CHOICE, "stock", RULES,
            confidence="applied",
            choices=[Choice("stock", "As shipped", ""),
                     Choice("TRUE", "On", ""), Choice("FALSE", "Off", "")],
            help=help_text or ("<%s> in every script\\\\*.ass." % tag)))
    return out


def _build_data(prefix):
    def build(v: dict) -> list:
        out = []
        level = v.get(prefix + "lethality", "stock")
        if level != "stock":
            out.append(FileEdit("scale_ballistics", r"CMBTMODL\.XML$",
                                {"factor": rstuning.LETHALITY[level]},
                                "hit resistance scaled to %gx"
                                % rstuning.LETHALITY[level]))
        out += rseweapons.shared_edits(prefix, v)

        values = {}
        for tag, _label, _help in TOGGLES:
            choice = v.get(prefix + "rule_" + tag.lower(), "stock")
            if choice != "stock":
                values[tag] = choice
        diff = v.get(prefix + "difficulty", "stock")
        if diff != "stock":
            values["Difficulty"] = diff
        invuln = int(v.get(prefix + "invuln", 0))
        if invuln:
            values["InvulnerabilityTimer"] = invuln
        if values:
            out.append(FileEdit("xml_text", r"\.ASS$", {"values": values},
                                "server rules: " + ", ".join(sorted(values))))
        return out
    return build


NOTES = (
    "Ghost Recon 2 and Summit Strike run the first game's engine with the enemy "
    "side rebuilt, so two of the options this tool offers on Ghost Recon have "
    "nothing to act on here. They are shipped visible and disabled with the "
    "reason on the card, because “why is that missing” is worth "
    "answering in the interface rather than in a readme.\n\n"
    "What is left is real: one combat model for everybody, every weapon in the "
    "game, and the dedicated-server scripts that carry the rules.\n\n"
    "The combat model ships twice -- loose under equip\\ and inside "
    "globs\\ikedata.glb -- and this tool writes both, because the two "
    "disagreeing is worse than neither changing."
)

GHOST_RECON_2 = GameProfile(
    id="ghost_recon2_xbox",
    title="Tom Clancy's Ghost Recon 2",
    short="Ghost Recon 2",
    title_id="55530005",
    markers=[Marker("globs", "the packed data the engine reads"),
             Marker("script", "the dedicated-server rule scripts"),
             Marker("equip", "the combat model")],
    settings=_settings("gr2_", 114, "Ghost Recon 2"),
    build_data=_build_data("gr2_"),
    notes=NOTES,
    ui_art={"backdrop": "shell/art/UI_STARTBkgd_US.xpr",
            "emblem": "shell/art/dash_gr-logo.xpr",
            "kind": "xpr"},
)

SUMMIT_STRIKE = GameProfile(
    id="summit_strike_xbox",
    title="Tom Clancy's Ghost Recon 2: Summit Strike",
    short="Summit Strike",
    title_id="5553004D",
    markers=[Marker("globs", "the packed data the engine reads"),
             Marker("script", "the dedicated-server rule scripts"),
             Marker("equip", "the combat model")],
    settings=_settings("ss_", 162, "Summit Strike"),
    build_data=_build_data("ss_"),
    notes=NOTES,
    ui_art={"backdrop": "shell/art/UI_STARTBkgd_US.xpr",
            "emblem": "shell/art/dash_gr-logo.xpr",
            "kind": "xpr"},
)

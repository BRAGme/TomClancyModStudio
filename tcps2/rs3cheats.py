r"""The developer console, on a spare pad button.

Rainbow Six 3 ships the complete Ubisoft Montreal cheat and debug console in
retail, and the gate that was supposed to hold it shut does not.

WHY IT IS OPEN
--------------

`R6CheatManager` carries 117 functions, 98 of them `FUNC_EXEC`, plus a 3.5 KB
`help` function holding the developers' own per-command documentation -- 61
commands in seven sections, their typos intact. Every one opens with
`if (!CanExec()) return;`, and `CanExec`'s body is two bytes::

    COMMON.LIN plain 0x07DA69:  83 00 00 00 | 04 27
                                ScriptSize 131 | EX_Return, EX_True

So it returns True on its first statement and the 131 bytes behind it -- the
`m_bUnlockAllCheat` test and the NetMode test -- are unreachable. There is
nothing to unlock. The manager is constructed unconditionally in
`R6PlayerController.PostNetBeginPlay`, output goes to the ordinary HUD message
area, and the shipped game already calls a cheat: `R6ConsoleXbox.
NotifyAfterLevelChange` runs `GodAll(true, true)` on training maps.

WHY IT IS UNREACHABLE ANYWAY
----------------------------

The developers bound their commands to keyboard keys, and the PS2 has no
keyboard -- there is no keyboard driver in the IRX list. `/PSX2USER.INI` still
carries the bindings they used, in `[Engine.Input]`::

    F3=godteam      F5=dbgthis      F7=HideAll      F10=RouteAll

WHY A PAD BINDING IS NOT A GUESS
--------------------------------

The same file already runs console commands from the pad, and already talks to
the cheat system from it::

    Joy9 =PeekLeft           | Cheatkey 4
    Joy10=PeekRight          | Cheatkey 2
    Joy11=GraduallyOpenDoor  | Cheatkey 1
    Joy12=GraduallyCloseDoor | Cheatkey 3

and `[Engine.Input]`'s alias table ends with four entries that are plainly
console commands rather than input actions::

    Aliases[34]=(Command="slomo 0.1")     Aliases[36]=(Command="BehindView 1")
    Aliases[35]=(Command="slomo 1")       Aliases[37]=(Command="ViewClass Pawn")

So the exec path from a pad binding is exercised by the retail disc itself.

**`Joy15` is empty.** One free slot, one line, nothing displaced.

WHAT IS STILL UNPROVEN
----------------------

That a pad-issued string reaches `R6CheatManager` specifically. `slomo` and
`BehindView` are `PlayerController` execs; the CheatManager is a separate
object the controller forwards to, and that last hop is a native virtual call
with no `jal` to follow. Everything else above is read off the disc. The test
takes a minute: bind `godteam` and look for `GodTeam True` in the HUD message
area.

THE FILE GROWS
--------------

`Joy15=` to `Joy15=godteam` is seven bytes longer. `/PSX2USER.INI` is not
inside the chunked compressor, so the archive writer relocates it; this is the
same path the `ini_values` edits for `R6GAMESETTINGS.INI` already take.
"""

from __future__ import annotations

#: the one pad slot `/PSX2USER.INI` leaves empty, in `[Engine.Input]`
FREE_SLOT = "Joy15"

#: Commands offered here are the DEVELOPERS' OWN bindings, read out of
#: `[Engine.Input]` on the retail disc, so each is certainly a real exec on a
#: certainly-correct spelling. The console holds 98; these four are the four
#: that shipped bound to a key.
COMMANDS = {
    "off": (None, ""),
    "godteam": ("godteam",
                "you and your squad stop taking damage (their F3)"),
    "hideall": ("HideAll",
                "hide the HUD, the weapon and the reticule (their F7)"),
    "routeall": ("RouteAll",
                 "draw the AI's routes and waypoints (their F10)"),
    "dbgthis": ("dbgthis",
                "dump what you are looking at to the message area (their F5)"),
}
DEFAULT = "off"


def ini_values(choice: str = DEFAULT) -> dict:
    """`{key: value}` for `transforms.set_ini_values`, or {} for stock."""
    cmd = COMMANDS.get(choice, COMMANDS[DEFAULT])[0]
    return {FREE_SLOT: cmd} if cmd else {}


def card(prefix, group):
    from .model import CHOICE, Choice, Setting

    return Setting(
        prefix + "cheat_key", "Developer command on a spare button", CHOICE,
        DEFAULT, group, confidence="experimental", touches="data",
        choices=[Choice("off", "Nothing", "The button stays unbound.")]
                + [Choice(k, v[0], v[1]) for k, v in sorted(COMMANDS.items())
                   if v[0]],
        help="The game ships Ubisoft Montreal's own cheat and debug console, "
             "98 executable commands, and the check that was meant to keep it "
             "shut returns true on its first instruction -- there is nothing "
             "to unlock.\n\n"
             "What stops you reaching it is that the developers bound their "
             "commands to keyboard keys and the PS2 has no keyboard. Their "
             "bindings are still in the file: F3 was god mode for the team, "
             "F7 hid the interface, F10 drew the AI's routes.\n\n"
             "One pad slot is left empty on the retail disc, and this puts a "
             "command on it.",
        caution="Not yet confirmed in play. The disc already runs console "
                "commands from the pad -- slow motion and the third-person "
                "camera are bound that way, and four buttons already speak to "
                "the cheat system -- but whether a pad-issued string reaches "
                "the cheat manager specifically was read from the data rather "
                "than watched happening.\n\n"
                "If it works you will see the command echo in the HUD message "
                "area, the same place mission messages appear. If nothing "
                "happens, nothing is harmed: an unrecognised command is "
                "ignored.")

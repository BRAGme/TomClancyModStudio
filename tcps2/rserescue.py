"""Telling a map it is a rescue mission, the way Trieste is told.

Why this is different from what came before
-------------------------------------------

Split screen builds a two-man team and stops, and six separate attempts to
make it build more have wedged the level load with an identical IOP streaming
freeze. Trieste is the sole exception: split-screen Practice Mode there runs
`R6RainbowTeam.CreatePlayerTeam`'s rescue arm on the RETAIL disc, creates
Loiselle and Weber as AI, gives them green friendly name tags, and reaches
gameplay.

Every attempt so far **bypassed the check** that guards that arm -- retarget
the `JumpIfNot`, redirect the spawn points, widen the streaming budget. Four
were refuted by measurement and the fifth corrupted memory.

Nobody has tried **setting the flag**.

Measured across all 69 map INIs on the disc (each stored three times, once per
vokes archive, so 207 files): `m_brescureRainbow` appears in exactly ONE of
them, `MAPS/TRIESTE_A.INI`. The other 68 do not carry the key at all, so they
take the class default. Writing `m_brescureRainbow=true` into another map's
`[Engine.R6MissionDescription]` makes that map look to the game exactly as
Trieste does -- not just at the one branch this project kept patching, but
everywhere else the flag is read. `CreatePlayerTeam` alone tests it in four
places (mem 0x01F9, 0x0395, 0x0420, 0x04D1), and only the first was ever
touched.

That is the difference worth testing. If some of the wedge is about setup the
flag performs earlier -- a spawn point resolved, an operative reserved before
the level streams -- no amount of branch patching would ever have reached it.

Where the line goes
-------------------

Trieste puts it at the end of the "Availability of Game Modes" block, after
the last of the `m_b...Game` keys, and this puts it in the same place. INI key
order does not matter to the parser, but matching the one known-good file
costs nothing and removes a variable from an experiment that already has too
many.

Two files on the disc are odd, and both are odd on the RETAIL disc -- checked
byte-for-byte against the pristine copies in the backup store, so this is
Ubisoft's doing and not a previous edit of ours. `MAPS/GARAGE_A.INI` has the
section but no `m_bNoRulesGame`: its `m_iEliteSaveSlots` key is truncated
mid-word and the rest of the line overwritten with spaces. `MAPS/GARAGE_B.INI`
has had its whole header, section line included, replaced by spaces. A file
with no section is left alone and reports no change rather than throwing --
the disc really does ship that way, and one padded file is not a reason to
refuse the other twenty-six.

What it does not claim
----------------------

It does not claim to work. Island may still wedge, and if it does then the
flag is not the difference either, and the honest conclusion is that Trieste
differs in authored level content -- the `RescureTeamStartingPoint` actor and
the cover group behind spot 0 -- which is level data this tool cannot
synthesise.

The key is ADDED, so the file grows by one line. Plain text inside a vokes
archive is allowed to grow; the archive writer relocates the entry and updates
its record. That is the same path `frag_warning` already uses.
"""

from __future__ import annotations

import re

#: The section the flag belongs in. Trieste carries it here, and 67 of the 69
#: map INIs have this section.
SECTION = "[Engine.R6MissionDescription]"

#: Exactly as Trieste spells it, lower-case 'r' and the studio's own
#: misspelling of "rescue" included -- the game matches the key literally.
KEY = "m_brescureRainbow"
LINE = KEY + "=true"

#: The "Availability of Game Modes" keys. The flag goes after the last one.
ANCHOR = re.compile(r"^[ \t]*m_b\w*Game[ \t]*=[^\r\n]*\r?\n", re.I | re.M)


class RescueError(Exception):
    pass


def _section(text):
    """(start, end) of the mission-description section body, or None."""
    m = re.search(re.escape(SECTION), text, re.I)
    if not m:
        return None
    nxt = re.compile(r"^\[", re.M).search(text, m.end())
    return (m.end(), nxt.start() if nxt else len(text))


def reads(text: str) -> bool:
    """True if this INI already declares the flag true."""
    m = re.search(r"^[ \t]*" + re.escape(KEY) + r"[ \t]*=[ \t]*(\w+)", text,
                  re.I | re.M)
    return bool(m) and m.group(1).lower() == "true"


def apply(raw: bytes, enable: bool = True):
    """Add the rescue flag if it is missing. Returns (bytes, changed).

    `enable=False` deliberately does nothing. Switching the card off is handled
    by the edit store putting the pristine file back, and stripping the key
    here would delete Trieste's own stock declaration along with ours.
    """
    text = raw.decode("latin-1")
    if not enable or reads(text):
        return raw, 0

    span = _section(text)
    if span is None:
        # GARAGE_B.INI ships with its header overwritten by spaces.
        return raw, 0
    start, end = span

    last = None
    for m in ANCHOR.finditer(text, start, end):
        last = m
    if last is not None:
        at = last.end()
    else:
        # No mode block (GARAGE_A.INI). Sit directly under the section header.
        nl = text.find("\n", start)
        if nl < 0 or nl >= end:
            raise RescueError(SECTION + " is not newline terminated")
        at = nl + 1

    eol = "\r\n" if text[at - 2:at - 1] == "\r" else "\n"
    out = text[:at] + LINE + eol + text[at:]
    return out.encode("latin-1"), 1


HELP = ("Trieste is the only one of 69 maps that declares itself a Rainbow "
        "rescue, and it is the only map where split screen builds AI "
        "operatives -- on the retail disc, with no patch at all. This writes "
        "the same declaration into the other 26 mission maps.")

CAUTION = (
    "EXPERIMENTAL, and a different shape from everything tried before it. Six "
    "earlier attempts BYPASSED the check that guards the rescue code -- "
    "retargeting the branch, redirecting the spawn points, widening the "
    "streaming budget. Four were refuted by measurement and the fifth "
    "corrupted memory. None of them SET the flag.\n\n"
    "That matters because the flag is read in four places in CreatePlayerTeam "
    "alone and only the first was ever touched. If any part of the wedge is "
    "about setup the flag performs before the level streams, no amount of "
    "branch patching could have reached it.\n\n"
    "One line of text per mission map, placed where Trieste places it. "
    "Multiplayer maps, training maps and the base map files are not "
    "touched.\n\n"
    "TESTED ONCE, on Alpine Village, and it wedged the load.\n\n"
    "An earlier version of this card explained that away: Alpine Village was "
    "said to be one of only three levels that never mention "
    "m_aStartingPoint, so the rescue arm had nowhere to place operatives. "
    "That explanation is RETRACTED. The name is dead across the whole disc -- "
    "it sits in 48 of 54 level name tables and its encoded index appears in "
    "no package body anywhere, so no map authors a starting point and the "
    "name distinguishes nothing. The three maps are still skipped, but only "
    "because one of them is the one that was tested; that is a weak reason "
    "and it is worth saying so.\n\n"
    "The remaining 23 maps have never been tried. Island Estate is the one "
    "to try.\n\n"
    "It may still wedge everywhere. If it does, the difference is authored "
    "level content that no INI key can conjure, and that is the honest end of "
    "this line. RESTORE DISC puts everything back.")


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_rescue_flag",
        "Treat every mission as a rescue", BOOL, False, group,
        confidence="broken", touches="data",
        enabled=False,
        disabled_reason=(
            "Play-tested on Alpine Village and it wedged the level load -- "
            "with no code patched at all, just one line of INI text, which is "
            "itself worth knowing because every earlier wedge involved a "
            "bytecode edit.\n\n"
            "It is retired rather than left untried, because the arm this "
            "flag unlocks calls the same CreateTeamMember as `split_squad`, "
            "and that is where the failure lives: the pawn class is resolved "
            "with DynamicLoadObject out of the R6Characters package and the "
            "lookup lands out of range (export 93 of 84 on Island, import "
            "567337 of 103 on Alpine). No INI key reaches that.\n\n"
            "One thing remains genuinely unexplained and is recorded rather "
            "than papered over: Trieste runs this same arm on the RETAIL disc "
            "and reaches gameplay. Whatever lets it succeed there has not "
            "been found."),
        help=HELP, caution=CAUTION)

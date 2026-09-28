"""Split-screen Terrorist Hunt on the canon maps: the two operatives nobody
plays join as AI teammates.

What split screen does now
--------------------------

With `canon_team`, player 2 is the mission's own operative on three maps --
Garage A/B Loiselle, Island A Weber -- and `split_squad`'s roster removals,
pointed at the Price flag, drop both AI there (neither mission has Price). So
split-screen Terrorist Hunt on those maps is Ding and player 2 alone, while
single-player Terrorist Hunt keeps all four operatives. Split-screen
Terrorist Hunt reads the SAME level files as practice (native LoadMap spawns
both split-screen game classes on every load), so its team cannot be built
differently in a way that reads differently.

What this does
--------------

`CreatePlayerTeam` does everything it does in practice -- creates members 2
and 3 and removes them on these rosters -- and only then, in Terrorist Hunt
and only when player 2 is not Price:

    if (Level.Game.IsA('R6TerroristHuntGame') && m_Team[1].m_iOperativeID != 1) {
        CreateTeamMember(0, teamStartingPoint, False, None);      // the Price arm
        CreateTeamMember(5 - m_Team[1].m_iOperativeID, teamStartingPoint, False, None);
    }

Garage gets AI Price and AI Weber (5 - 2 = 3), Island AI Price and AI
Loiselle (5 - 3 = 2). It runs before the skins, heads and caps are handed
out, before player 2's arms, before `split_squad`'s layout block moves player
2 to the end, and before the carry-over restore -- so the team ends
[Ding, AI, AI, player 2], count 3, as everywhere else.

Why nothing new is read
-----------------------

Every class the two calls load is already loaded by then: Price's by member 0,
Loiselle's and Weber's by the practice sequence that just ran, in the
recording's own order -- and creating an AI whose class is loaded reads
nothing. The single-player and split-screen recordings differ only by the
105-byte record and the two operative class groups, and in single player a
whole AI Loiselle is created between those two groups. `LoadMissionRainbowSkins`
loads the body skin and all four heads and caps unconditionally; its loop
only hands them out. Every operative bank is queued natively for every
non-ENTRY, non-multiplayer map (EE 0x478e10), whoever is in the team, from
SB1 files outside the `.LIN` -- today's split-screen Garage Terrorist Hunt
already has Price's bank and all 291 voice Sound objects resident (savestate,
2026-09-24). `bTerroHunt` is not touched: `CreateTeamMember` uses it to pick a
Terrorist Hunt loadout, which differs on three maps. The two new calls leave
it out, and `bPlayer` and `RainbowPC` with it -- all three are flagged
optional (0x90, measured in RAM), and an omitted optional parameter arrives as
zero (inferred for this build) -- so the new AI get the mission loadout the
practice AI get: Price's `m_PriceEquipment`. On Garage his weapons equal
Loiselle's; on Island his frag grenade lives in R6Weapons, inside COMMON_SS,
already loaded.

(This also retracts the reason given on 2026-09-24 for withdrawing
`rsecanon._thunt`: a different team does NOT read different skins. The Garage
hang that day is explained by `split_callouts` alone.)

The bytes
---------

Two regions of `CreatePlayerTeam` (block 0x1470a3, 1346 disk / 1775 memory),
each rewritten at exactly its length:

* A, mem 0x047d-0x04d1: the dead padding after `split_squad`'s layout block's
  `return` -- the gate and the Price call.
* B, mem 0x04d1-0x0688: single player's member-2/3 arm, which split screen
  reaches through `split_squad`'s jump. Its two `Log("m_CoverSpots[n]:")`
  debug calls pay for the second call; every other statement is kept byte
  for byte, only its jump operands re-based. The two roster removal tests'
  misses move from 0x05ab / 0x0688 to 0x0583 / 0x0637 (`rsesquad` knows both).

Needs `split_squad` and `canon_team`: the regions are their forms, and this
refuses anything else. On every other map, and in practice, the gate falls
through to where the arm always ended. The reverse does not hold either:
`rsesquad.apply` refuses a file that already carries this edit (region A is
the tail of its layout block). Every apply starts from the shipped file, so
that only matters to a tool that re-applies squad to a built one.

Checked (2026-09-24): an interpreter running the real bytecode of both
functions for six maps in practice and Terrorist Hunt -- practice identical to
today, Terrorist Hunt with the same first class loads as practice, four
different operatives, player 2 last, no Accessed None; package creation order
and content-import order unchanged. An independent review then hand-decoded
every new statement, traced the order through skins, hands, the layout block
and SetSavedData, confirmed a Price-class AI with `m_iID` above 0 is "Eddie
Price" (operative 1), and found that the stock split-screen and single-player
recordings of Garage A/B and Island A differ only by the 105-byte record and
the class groups -- while single player builds an AI Price, voices, bank,
weapons and cap included. Not yet played.
"""

from __future__ import annotations

H = bytes.fromhex


class ThuntAIError(Exception):
    pass


#: region A as this edit leaves it (67 bytes)
REGION_A_NEW = H(
    "078806821919018f05000401a6080004612f214a04161814009b191a26010a05"
    "0004014b042616161b710125007808282a160667060b0b0b0b0b0b0b0b0b0b0b"
    "0b0b0b")

#: region B as `split_squad` + `canon_team` leave it (341 bytes) ...
REGION_B_OLD = H(
    "076d058284821900710c0600042d01cb04181d00811919018f05000401a60800"
    "04612f214a0416161618100019018f0600042d01fb0316180b00771a2601282a"
    "1616e7701f6d5f436f76657253706f74735b315d3a003958191a26012805000c"
    "018c16161b71012c021a26012828004a032d005304160686051b71012c020078"
    "0828004a032d0053041607ab0582812d0053041618100081196516160600042d"
    "01c50c16161b450516074a068284821900710c0600042d01cb04181d00811919"
    "018f05000401a6080004612f214a0416161618100019018f0600042d01fb0316"
    "180c00771a2c0201282a1616e7701f6d5f436f76657253706f74735b325d3a00"
    "3958191a2c02012805000c018c16161b71012c031a2c02012828004a032d0053"
    "04160663061b71012c0300780828004a032d0053041607880682812d00530416"
    "18100081196516160600042d01c50c16161b450516")

#: ... and as this edit leaves it
REGION_B_NEW = H(
    "0745058284821900710c0600042d01cb04181d00811919018f05000401a60800"
    "04612f214a0416161618100019018f0600042d01fb0316180b00771a2601282a"
    "16161b71012c021a26012828004a032d00530416065e051b71012c0200780828"
    "004a032d0053041607830582812d0053041618100081196516160600042d01c5"
    "0c16161b45051607f9058284821900710c0600042d01cb04181d00811919018f"
    "05000401a6080004612f214a0416161618100019018f0600042d01fb0316180c"
    "00771a2c0201282a16161b71012c031a2c02012828004a032d00530416061206"
    "1b71012c0300780828004a032d0053041607370682812d005304161810008119"
    "6516160600042d01c50c16161b450516067d0401160b0b0b0b0b0b0b0b0b0b0b"
    "0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b1b7101"
    "932c05191a26010a050004014b0416007808282a16")

#: the roster removal tests' misses once region B is re-laid
ROSTER_MISS = {"L": 0x0583, "W": 0x0637}


def _edits():
    from . import rsesquad
    return (
        ("the dead padding after the layout block: the gate and the Price call",
         rsesquad.LAYOUT_CODE_NEW, 70, rsesquad.LAYOUT_CODE_NEW[70:], REGION_A_NEW),
        ("single player's member-2/3 arm: the second call",
         REGION_B_OLD, 0, REGION_B_OLD, REGION_B_NEW),
    )


KNOWN_OFFSETS = (0x147405, 0x147448)


def _sites(plain: bytes):
    """[(offset of the changed bytes, stock, new, state)] or raise."""
    out = []
    for name, key, rel, stock, new in _edits():
        done = key[:rel] + new + key[rel + len(stock):]
        hits = []
        for form, state in ((key, "stock"), (done, "new")):
            at = plain.find(form)
            if at >= 0 and plain.find(form, at + 1) >= 0:
                raise ThuntAIError("%s: found more than once" % name)
            if at >= 0:
                hits.append((at + rel, state))
        if len(hits) != 1:
            raise ThuntAIError("%s: %s" % (name, "not found" if not hits
                                           else "both forms present"))
        out.append((hits[0][0], stock, new, hits[0][1]))
    return out


def reads(plain: bytes) -> bool:
    try:
        return all(s[3] == "new" for s in _sites(plain))
    except ThuntAIError:
        return False


def apply(plain: bytes, enable: bool = True):
    """Returns (plain, changed). The length never moves. Needs split_squad and
    canon_team already in the file; refuses anything it does not recognise."""
    if not enable or reads(plain):
        return plain, 0
    out = bytearray(plain)
    n = 0
    for at, stock, new, state in _sites(plain):
        if state == "stock":
            out[at:at + len(stock)] = new
            n += 1
    return bytes(out), n


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_thunt_ai",
        "Terrorist Hunt on the canon maps: the other two operatives join",
        BOOL, False, group, confidence="experimental", touches="data",
        requires={prefix + "split_squad": [True], prefix + "canon_team": [True]},
        help="With the mission's own player 2, Terrorist Hunt on the Garage "
             "(player 2 Loiselle) and Island (player 2 Weber) had no AI "
             "teammates, because those missions' rosters leave the others out. "
             "Single-player Terrorist Hunt keeps all four operatives, so this "
             "adds the two nobody plays: Eddie and Weber on the Garage, Eddie "
             "and Loiselle on Island. Practice missions keep their roster.",
        caution="Not yet played. It adds two teammates after the practice "
                "team is built, loading only what is already loaded. If "
                "Terrorist Hunt on the Garage or Island stops loading, turn "
                "this off first.")

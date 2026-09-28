"""Player 2's first-person arms in the mission's outfit.

Reported 2026-09-24: player 2's view model always wears the default dark
outfit, while player 1's matches the mission.

Why
---

Each map's INI sets `m_Skins.missionTeam` (0-12) on the mission description.
The very last statement of `R6RainbowTeam.CreatePlayerTeam` (mem 0x06C1) is::

    m_TeamLeader.SetFirstPersonHandsSkin(GetMissionDescription().m_Skins.missionTeam)

`R6Rainbow.SetFirstPersonHandsSkin` loads `R61stWeapons_T.Hands.R61stHands<x>`
and writes it into `Skins[0]` of the first-person hands on all four carried
weapons. `m_TeamLeader` is the first member created -- player 1 -- and nothing
else calls it in split screen (its two other callers are online-only and pass
the multiplayer skin). So player 2's hands keep the mesh's own material,
`R61stHands`, the default outfit. Measured in four split-screen savestates
across four levels: player 1's hands hold the mission texture on every weapon,
player 2's hold nothing.

This is the view model only. The third-person body is `LoadMissionRainbowSkins`,
which player 2 already gets.

What this does
--------------

Three edits inside `CreatePlayerTeam`, which keeps its 1346 / 1775:

* mem 0x06C1: the leader's call becomes `goto 0x0395`. The rest of the old
  statement stays behind as unreachable bytecode, so its references keep
  their place in the load.
* mem 0x0395: the single-player arm's rescue-map spawn of member 1 -- which
  split screen never runs -- becomes the leader's call, the same call on
  `m_Team[1]`, and `goto 0x06E1`, the statement after the original call.
  `m_Team[1]` is player 2 at that point in every layout: `rsesquad` moves him
  to the end of the team only later, at 0x06E1.
* mem 0x0357: the single-player arm's jump into that region now skips it, so
  only the new `goto` reaches the new code.

Player 2's call asks for the very texture player 1's loaded one statement
earlier, so nothing new is loaded. The package's own objects are created in
exactly the shipped order (checked with and without `split_squad` and
`canon_team`, in both orders). Split-screen package only: in the offline and
online packages that region is live single-player code.

Not established: how it looks. It has not been played.
"""

from __future__ import annotations

H = bytes.fromhex

#: (name, key -- whole, in its stock form, found exactly once --, offset of the
#: changed bytes within the key, stock bytes, new bytes)
EDITS = (
    ("guard: the single-player arm's jump skips the new code",
     H("0795038219018f0600042d01fb03180b00771a2501282a1616"), 1,
     H("95"), H("e3")),
    ("the dead rescue spawn of member 1 becomes both players' calls",
     H("07e303821900710c0600042d01cb04181d00811919018f05000401a608000461"
       "2f214a04161616" "1b7101260057192800" "4a032d00530416" "06fb03"), 0,
     H("07e303821900710c0600042d01cb04181d00811919018f05000401a608000461"
       "2f214a04161616" "1b7101260057192800" "4a032d00530416" "06fb03"),
     H("19014f01170000" "1b450736ef0419651616050004" "01fa0416"     # leader
       "191a26010a170000" "1b450736ef0419651616050004" "01fa0416"   # m_Team[1]
       "06e106" "010a0b0b0b0b")),                                  # goto 0x06e1; filler
    ("the leader's call becomes a jump to them",
     H("1b540f161b7a1016" "19014f01170000"), 8,
     H("19014f01170000"), H("069503014f010b")),
)
KNOWN_OFFSETS = (0x14732A, 0x147356, 0x1475C5)


class HandsError(Exception):
    pass


def _sites(plain: bytes):
    """[(offset of the changed bytes, stock, new, state)] or raise."""
    out = []
    for name, key, rel, stock, new in EDITS:
        done = key[:rel] + new + key[rel + len(stock):]
        hits = []
        for form, state in ((key, "stock"), (done, "new")):
            at = plain.find(form)
            if at >= 0 and plain.find(form, at + 1) >= 0:
                raise HandsError("%s: found more than once" % name)
            if at >= 0:
                hits.append((at + rel, state))
        if len(hits) != 1:
            raise HandsError("%s: %s" % (name, "not found" if not hits
                                         else "both forms present"))
        out.append((hits[0][0], stock, new, hits[0][1]))
    return out


def reads(plain: bytes) -> bool:
    try:
        return all(s[3] == "new" for s in _sites(plain))
    except HandsError:
        return False


def apply(plain: bytes, enable: bool = True):
    """Returns (plain, changed). The length never moves."""
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
        prefix + "split_hands", "Player 2's arms wear the mission outfit",
        BOOL, False, group, confidence="experimental", touches="data",
        requires={prefix + "viewmodel": [True]},
        help="Each mission dresses the team in its own outfit, and player 1's "
             "first-person arms follow it. Player 2's always wear the default "
             "dark outfit, because the game dresses only the team leader's "
             "arms. This dresses player 2's too, with the same call, loading "
             "nothing new.",
        caution="Not yet played. It rewrites part of the team-building "
                "function, keeping its size and load order, in code split "
                "screen never runs. If a level hangs on load, turn this off "
                "first.")

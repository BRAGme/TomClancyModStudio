"""Force the squad chain to narrate itself into the log.

Why this exists
---------------

`R6Game.u` and `R6Engine.u` are full of ``if (bShowLog) Log(...)`` -- 885 of
them across the disc. `bShowLog` is declared on `Actor`, so every actor carries
its own copy, and the shipped defaults set it on exactly one class in the
squad's chain::

    R6GameInfo.bShowLog         True    <- serialised, bit 7 of its info byte
    Actor.bShowLog              absent  -> False
    R6RainbowTeam.bShowLog      absent  -> False

So `R6GameInfo.SpawnAIandInitGoInGame` already speaks, and everything
`R6RainbowTeam` does -- `CreatePlayerTeam`, `CreateTeamMember`, the whole part
that would say WHICH operative failed to appear -- is silent. That is the half
worth hearing when a System Link host builds no squad.

Why not just set the default
----------------------------

There is no bit to flip. A UE2 default list only carries properties that
DIFFER from the parent's, and neither `Actor` nor `R6RainbowTeam` carries
`bShowLog` at all, so turning it on means ADDING a tagged property. That grows
the class's serial range, shifts every later export, and `R6Engine.u` sits in
a fixed-length `.umd` slot. Not available.

What this does instead
----------------------

Each site compiles to::

    JumpIfNot <u16 memTarget>  BoolVariable(InstanceVariable bShowLog)
    Log(...)                                   <- memTarget skips over this

The jump word is rewritten to the memory offset of the instruction that
already follows the condition -- that is, the `Log` itself. The test still
runs, and both of its answers now continue into the log. **Two bytes per site,
and the value written is an offset the function already contains**, so nothing
moves: same disk length, same `ScriptSize`, every other jump still lands where
it did, and the package keeps the length its `.umd` slot demands.

What is switched on
-------------------

Not all 885. Most are per-frame -- `R6Weapons.Fire`, every `Tick`, every
`BeginState` of a weapon animation -- and turning those on would bury the
answer in thousands of lines a second. The set below is the chain a level load
walks once: the game mode coming up, the player logging in, the team being
built member by member, and the round state machine, which is the other
suspect for a squad that is created and then thrown away.

Reading it back
---------------

The log device is the emulator's, not the game's: this build keeps UE2's log
machinery (`ScriptWarning` and `Assertion failed: ` are both still in the XBE)
but names no log file and no drive path, so the text goes out the debug port
and it is xemu that decides whether to show it. If nothing appears there, that
is the sink, not this edit -- the bytes are checked before and after either
way.

One thing is already visible without any of this: `R6GameInfo.DeployCharacters`
opens with ``assert(Level.NetMode == NM_Standalone)`` at line 998. In a System
Link game that assertion is false, so a host that reaches the function at all
should be saying "Assertion failed, line 998" on its own. Its absence would
mean the function is never reached; its presence would mean it is.
"""

from __future__ import annotations

import struct

from .coopteam import (CoopTeamError, _ci, _exports, _imports, _names,
                       _resolve, _script_start, _summary)

#: both packages the chain lives in
PACKAGES = r"/(R6GAME|R6ENGINE)\.U$"

#: the property the sites test, by its own name
FLAG = "bShowLog"

#: (owner, function) pairs that run ONCE per level load or per player, never
#: per frame. Nothing named Tick is here on purpose.
WANTED = frozenset({
    # the game mode coming up
    ("R6GameInfo", "InitGame"),
    ("R6GameInfo", "Login"),
    ("R6GameInfo", "RestartPlayer"),
    ("R6GameInfo", "FindPlayerStart"),
    ("R6GameInfo", "SpawnAI"),
    ("R6GameInfo", "SpawnAIandInitGoInGame"),
    ("R6GameInfo", "ProcessChangeLevelSystem"),
    ("R6GameInfo", "AcceptInventory"),
    ("R6MultiPlayerGameInfo", "Login"),
    ("R6MultiPlayerGameInfo", "PostLogin"),
    ("R6MultiPlayerGameInfo", "InGameSpawnNewPlayer"),
    ("R6MultiPlayerGameInfo", "InitObjectives"),
    ("R6MultiPlayerGameInfo", "ResetPlayerTeam"),
    ("R6CoopStoryModeGame", "InitObjectives"),
    # the squad itself -- the silent half
    ("R6RainbowTeam", "CreatePlayerTeam"),
    ("R6RainbowTeam", "CreateTeamMember"),
    # the round state machine
    ("Connecting", "BeginState"),
    ("Connecting", "EndState"),
    ("WaitingForPlayers", "BeginState"),
    ("PreGame", "BeginState"),
    ("PreGame", "EndState"),
    ("InGame", "BeginState"),
    ("BetweenRound", "BeginState"),
    ("BetweenRound", "EndState"),
    ("EndOfRound", "BeginState"),
})


class ShowLogError(Exception):
    pass


def _ref_index(raw):
    """A `ref` part's compact bytes -> its index."""
    value, _ = _ci(bytes(raw) + bytes(6), 0)
    return value


def _condition(tok):
    """(condTok, propertyIndex) for `if (someBool)`, else None."""
    if tok.name != "JumpIfNot":
        return None
    exprs = [v for k, v in tok.parts if k == "expr"]
    if not exprs or exprs[0].name != "BoolVariable":
        return None
    inner = [v for k, v in exprs[0].parts if k == "expr"]
    if not inner or inner[0].name != "InstanceVariable":
        return None
    refs = [v for k, v in inner[0].parts if k == "ref"]
    if not refs or not isinstance(refs[0], (bytes, bytearray)):
        return None
    return exprs[0], _ref_index(refs[0])


def sites(data: bytes):
    """[(owner, function, wordOffset, stored, wanted)] for every site.

    `wordOffset` is where the jump's u16 sits on disk; `stored` is what it
    holds now and `wanted` is the fall-through. The two are equal once the
    edit has been applied, which is what makes it recognisable and repeatable.
    """
    from . import uscode

    try:
        (_v, _l, _f, nc, no, ec, eo, ic, io) = _summary(data)
    except CoopTeamError:
        return []
    names = _names(data, nc, no)
    if FLAG not in names:
        return []
    rows = _exports(data, names, ec, eo)
    imports = _imports(data, names, ic, io)

    # Disk offsets are what a byte edit needs and `uscode` has no reason to
    # keep them, so the parser is wrapped for these parses and put back in a
    # finally. The note lives in a side table because `Tok` uses __slots__.
    where = {}
    original = uscode._parse_one

    def noting(buf, dp, mp, depth):
        tok, ndp, nmp = original(buf, dp, mp, depth)
        where[id(tok)] = dp
        return tok, ndp, nmp

    out = []
    for name, cls, pkg, size, off in rows:
        if size <= 0 or not _resolve(rows, imports, cls).endswith("Function"):
            continue
        owner = _resolve(rows, imports, pkg)
        if (owner, name) not in WANTED:
            continue
        uscode._parse_one = noting
        try:
            script = uscode.Script.at(data, _script_start(data, off))
        except Exception:                                      # noqa: BLE001
            continue
        finally:
            uscode._parse_one = original
        # Every instruction boundary in this function. A jump may only be
        # pointed at one of these: "one past the condition" is a boundary by
        # construction, so this is really a check that the parse agreed with
        # itself, and it is what stops a mis-parsed function being written to.
        starts = {t.mstart for top in script.toks for t in top.walk()}
        for top in script.toks:
            for tok in top.walk():
                found = _condition(tok)
                if found is None:
                    continue
                cond, idx = found
                if _resolve(rows, imports, idx) != FLAG:
                    continue
                word_at = where[id(tok)] + 1          # past the opcode byte
                stored = struct.unpack_from("<H", data, word_at)[0]
                wanted = cond.mstart + cond.mlen
                if not 0 <= wanted <= 0xFFFF or wanted not in starts:
                    continue
                out.append((owner, name, word_at, stored, wanted))
    return out


def census(data: bytes):
    """(shipped, forced) -- how many sites are in each state."""
    shipped = forced = 0
    for _o, _f, _at, stored, wanted in sites(data):
        if stored == wanted:
            forced += 1
        else:
            shipped += 1
    return shipped, forced


def force_on(data: bytes):
    """Make every site in `WANTED` log whatever `bShowLog` says.

    Returns (bytes, sitesForced). Idempotent: a site already pointing at its
    own fall-through is left alone.
    """
    out, moved = bytearray(data), 0
    for _o, _f, word_at, stored, wanted in sites(data):
        if stored == wanted:
            continue
        struct.pack_into("<H", out, word_at, wanted)
        moved += 1
    return (bytes(out), moved) if moved else (data, 0)

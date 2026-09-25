"""AI teammates in System Link: one comparison, two bytes.

What stops them
---------------

`R6ConsoleXbox.NotifyAfterLevelChange` runs after a level loads::

    Player = GetLocalPlayerController();

    if ( Level.Game.IsA('R6GameInfo') && Level.NetMode == NM_Standalone )
            Level.Game.DeployCharacters(Player, true);   // builds the team
            Player.ClientSetHUD(R6HUD);

    if ( Level.NetMode == NM_Standalone
             && Level.Game.IsA('R6AbstractGameInfo') )
            R6AbstractGameInfo(Level.Game).SpawnAIandInitGoInGame();

    ...
    if ( Level.Game.IsA('R6MultiPlayerGameInfo')
             && Level.NetMode != NM_Standalone )
            Level.Game.GotoState('BetweenRound');        // the round starts

Every `IsA` passes in co-op -- `R6GameInfo` and `R6AbstractGameInfo` are base
classes the co-op modes descend from, `R6CoopStoryModeGame -> R6CoOpMode ->
R6MultiPlayerGameInfo -> R6GameInfo`. The NetMode halves are what differ: a
System Link host is `NM_ListenServer`, a guest is `NM_Client`.

`DeployCharacters` is the ONLY thing anywhere that builds the squad -- an xref
over every package on the disc finds exactly one caller, this one -- so this
gate is the only lever there is.

Only one gate
-------------

`SpawnAIandInitGoInGame` was opened too, in an earlier version, and that was
wrong. The same xref shows `BetweenRound.BeginState` already calls it,
unconditionally, and the third conditional above is what sends a multiplayer
game into `BetweenRound` a few instructions later. So multiplayer runs it
anyway; opening the second gate only made it run TWICE, and it drives
`SpawnAI`, which is::

    foreach AllActors(R6DeploymentZone, pZone) pZone.InitZone();

with `InitZone` being a one-line call to the native `FirstInit`. Making every
deployment zone on the map first-initialise a second time is not something to
do on purpose, and it bought nothing. That gate is left shut.

What this does NOT fix
----------------------

The squad still does not appear in System Link with this applied, and it is
honest to say so here rather than only on the card. What the tracing rules out
is everything downstream: `R6RainbowTeam.CreateTeamMember` refuses only
`NM_Client`, its AI branch (`Spawn(R6RainbowAI)` then `Possess`) has no NetMode
test at all, and `R6CoOpMode.FindPlayerStart` hands out real insertion zones
(`FindTeamInsertionZone(m_byNextPlayerIndex++)`), so start points are fine.
What remains is timing: this gate builds the squad at level load, and the very
next thing the function does is start the multiplayer round, whose
`BetweenRound.EndState` walks every player calling `ResetPlayerTeam`. Moving
the build into the round would mean ADDING a call, and `R6Game.u` sits in a
fixed-length `.umd` slot.

The change
----------

A two-byte edit at that one gate, turning::

    Level.NetMode == NM_Standalone      ->      Level.NetMode != NM_Client

  * the comparison, `EqualEqual_IntInt` (native 154, `0x9A`) becomes
    `NotEqual_IntInt` (native 155, `0x9B`);
  * the constant, `NM_Standalone` (0) becomes `NM_Client` (3).

which reads true for Standalone, Dedicated Server and Listen Server, and false
only for a pure client:

  ===================  =========  ===================================
  where                NetMode    result
  ===================  =========  ===================================
  single player        0          true -- unchanged
  System Link host     2          true -- the squad is built
  System Link guest    3          false -- the host would replicate to it
  ===================  =========  ===================================

Both opcodes were read out of the disc's own `Core.u` rather than remembered:
its 177 `Function` exports carry an `iNative` each, and 154 and 155 resolve to
`Object.EqualEqual_IntInt` and `Object.NotEqual_IntInt`. The third gate in this
same function, the one that sends a multiplayer game to `BetweenRound`, already
uses 155 -- so the pair is in use a few bytes away.

A fourth conditional in the function is left alone: `m_bIsTrainingMap` turning
on `GodAll`, which has nothing to do with any of this.

Why this is safe to write
-------------------------

The edit changes two bytes and moves nothing: same opcode width, same operand
width, so every jump offset in the function still lands where it did and
`R6Game.u` keeps the length its `.umd` slot demands. What it cannot do is prove
the game likes the result -- see the card's caution.

Finding it
----------

Structurally, never at a fixed address, and the offsets do differ per disc.
The export tables of these `.u` files are exact -- they are whole originals,
not the two-range gathers a `.LIN` holds -- so the function is found by name
and owner, its script is PARSED, and each gate is the nearest NetMode
comparison before the call it guards. Both bytes are checked before either is
written, and a gate already carrying the change is recognised and skipped, so
applying twice is the same as applying once.
"""

from __future__ import annotations

import struct

#: native 154 and native 155, as single-byte native opcodes
EQ_INT, NE_INT = 0x9A, 0x9B

#: ENetMode
NM_STANDALONE, NM_CLIENT = 0, 3

PACKAGE = r"/R6GAME\.U$"
FUNCTION = "NotifyAfterLevelChange"
OWNER = "R6ConsoleXbox"
#: ONE call. `SpawnAIandInitGoInGame` is deliberately NOT here -- see the
#: "Only one gate" section above.
CALLS = ("DeployCharacters",)

MAGIC = 0x9E2A83C1


class CoopTeamError(Exception):
    pass


def _ci(buf, pos):
    """UE2 FCompactIndex -> (value, nextPos)."""
    b = buf[pos]
    pos += 1
    neg = b & 0x80
    val = b & 0x3F
    if b & 0x40:
        shift = 6
        while True:
            c = buf[pos]
            pos += 1
            val |= (c & 0x7F) << shift
            shift += 7
            if not (c & 0x80):
                break
    return (-val if neg else val), pos


def _summary(data):
    if len(data) < 40 or struct.unpack_from("<I", data, 0)[0] != MAGIC:
        raise CoopTeamError("not an Unreal package")
    return struct.unpack_from("<HHIIIIIII", data, 4)


def _names(data, count, off):
    out, pos = [], off
    for _ in range(count):
        ln = data[pos]
        pos += 1
        out.append(data[pos:pos + ln - 1].decode("latin1"))
        pos += ln + 4                     # string, its NUL, then flags
    return out


def _imports(data, names, count, off):
    out, pos = [], off
    for _ in range(count):
        _cp, pos = _ci(data, pos)
        _cn, pos = _ci(data, pos)
        pos += 4                          # package index
        on, pos = _ci(data, pos)
        out.append(names[on] if 0 <= on < len(names) else "?")
    return out


def _exports(data, names, count, off):
    rows, pos = [], off
    for _ in range(count):
        cls, pos = _ci(data, pos)
        _sup, pos = _ci(data, pos)
        pkg = struct.unpack_from("<i", data, pos)[0]
        pos += 4
        on, pos = _ci(data, pos)
        pos += 4                          # object flags
        size, pos = _ci(data, pos)
        soff = 0
        if size > 0:
            soff, pos = _ci(data, pos)
        rows.append((names[on] if 0 <= on < len(names) else "?", cls, pkg,
                     size, soff))
    return rows


def _resolve(rows, imports, index):
    if index > 0 and index <= len(rows):
        return rows[index - 1][0]
    if index < 0 and -index <= len(imports):
        return imports[-index - 1]
    return ""


def _script_start(data, off):
    """Where a Function export's `<u32 memSize>` field sits."""
    pos = off
    if data[pos] == 0:                    # the empty tagged property list
        pos += 1
    for _ in range(5):                    # SuperField Next ScriptText
        _v, pos = _ci(data, pos)          # Children FriendlyName
    return pos + 8                        # past Line and TextPos


def _native(tok):
    if tok.op >= 0x70:
        return tok.op
    if 0x60 <= tok.op < 0x70:
        return ((tok.op - 0x60) << 8) | (tok.native2 or 0)
    return None


def _byte_const(tok):
    """The `ByteConst` at the bottom of a conversion chain, or None."""
    cur = tok
    for _ in range(4):
        if cur.name == "ByteConst":
            return cur
        nxt = [v for k, v in cur.parts if k == "expr"]
        if not nxt:
            return None
        cur = nxt[0]
    return None


def _gates(data):
    """[(callName, opOffset, constOffset)] -- one gate per call, or [].

    The gate for a call is the nearest NetMode-against-a-byte-constant
    comparison that appears before it, whichever way round that comparison is
    currently written. Returning both states is what lets a half-applied
    package be recognised instead of being mistaken for a stock one.
    """
    from . import uscode

    try:
        (_v, _l, _f, ncount, noff, ecount, eoff, icount, ioff) = _summary(data)
    except CoopTeamError:
        return []
    names = _names(data, ncount, noff)
    if OWNER not in names or FUNCTION not in names:
        return []
    if not any(c in names for c in CALLS):
        return []
    rows = _exports(data, names, ecount, eoff)
    imports = _imports(data, names, icount, ioff)

    target = None
    for name, cls, pkg, size, soff in rows:
        if (name == FUNCTION and size > 0
                and _resolve(rows, imports, cls).endswith("Function")
                and _resolve(rows, imports, pkg) == OWNER):
            target = soff
            break
    if target is None:
        return []

    # Disk offsets are what a byte edit needs and what `uscode` has no reason
    # to keep, so the parser is wrapped for the length of this one parse and
    # put back afterwards. The note lives in a side table because `Tok` uses
    # __slots__; the Script holds every token, so nothing is collected early.
    where = {}
    original = uscode._parse_one

    def noting(buf, dp, mp, depth):
        tok, ndp, nmp = original(buf, dp, mp, depth)
        where[id(tok)] = dp
        return tok, ndp, nmp

    uscode._parse_one = noting
    try:
        script = uscode.Script.at(data, _script_start(data, target))
    except Exception:                                          # noqa: BLE001
        return []
    finally:
        uscode._parse_one = original

    wanted = {names.index(c): c for c in CALLS if c in names}
    calls, comparisons = [], []
    for top in script.toks:
        for tok in top.walk():
            if tok.name == "VirtualFunction":
                for kind, val in tok.parts:
                    if kind == "ref" and isinstance(val, (bytes, bytearray)):
                        idx, _ = _ci(bytes(val) + bytes(6), 0)
                        if idx in wanted:
                            calls.append((where[id(tok)], wanted[idx]))
            if _native(tok) not in (154, 155):
                continue
            kids = [v for k, v in tok.parts if k == "exprs"]
            for kid in (kids[0] if kids else []):
                const = _byte_const(kid)
                if const is not None:
                    comparisons.append((where[id(tok)], where[id(const)] + 1))

    out = []
    for call_at, call_name in sorted(calls):
        before = [c for c in comparisons if c[0] < call_at]
        if not before:
            continue
        op_at, const_at = max(before)
        out.append((call_name, op_at, const_at))
    return out


def find_gate(data: bytes):
    """The first gate still in its shipped form, or None. Kept for callers
    that only care whether there is anything left to do."""
    for _name, op_at, const_at in _gates(data):
        if data[op_at] == EQ_INT and data[const_at] == NM_STANDALONE:
            return op_at, const_at
    return None


def census(data: bytes):
    """(shipped, opened) -- how many of the gates are in each state."""
    shipped = opened = 0
    for _name, op_at, const_at in _gates(data):
        if data[op_at] == EQ_INT and data[const_at] == NM_STANDALONE:
            shipped += 1
        elif data[op_at] == NE_INT and data[const_at] == NM_CLIENT:
            opened += 1
    return shipped, opened


def open_to_system_link(data: bytes):
    """Let a System Link host build AND spawn the AI squad.

    Returns (bytes, gatesOpened). Idempotent: a gate already carrying the
    change is left alone, so applying twice is the same as applying once, and
    a package where only the first gate was opened -- which an earlier version
    of this module produced -- is finished rather than refused.
    """
    out, moved = bytearray(data), 0
    for _name, op_at, const_at in _gates(data):
        if data[op_at] != EQ_INT or data[const_at] != NM_STANDALONE:
            continue
        out[op_at] = NE_INT
        out[const_at] = NM_CLIENT
        moved += 1
    return (bytes(out), moved) if moved else (data, 0)

"""AI teammates in System Link: one comparison, in script, in `R6Game.u`.

What stops them
---------------

`R6ConsoleXbox.NotifyAfterLevelChange` is what builds Rainbow's AI squad after
a level loads. It does it behind one condition::

    if ( Level.Game.IsA('R6GameInfo') && Level.NetMode == NM_Standalone )
            Level.Game.DeployCharacters(Player, true);   // -> CreateRainbowTeam
            Player.ClientSetHUD(R6HUD);

`IsA('R6GameInfo')` is true in every mode -- `R6GameInfo` is the base class
that `R6StoryModeGame`, `R6MultiPlayerGameInfo`, `R6CoOpMode`,
`R6CoopStoryModeGame` and `R6CoopTerroristHuntGame` all descend from. So the
only half that fails in a System Link game is the NetMode test: the host is
`NM_ListenServer` and a guest is `NM_Client`, and neither is `NM_Standalone`.
`DeployCharacters` never runs, `CreateRainbowTeam` never runs, and the squad is
never built -- which is exactly what a System Link session looks like.

The change
----------

Two bytes, turning::

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
  System Link host     2          true -- the squad now deploys
  System Link guest    3          false -- the host replicates to it
  ===================  =========  ===================================

Both names were read out of the disc's own `Core.u` rather than remembered: its
177 `Function` exports carry an `iNative` each, and 154 and 155 resolve to
`Object.EqualEqual_IntInt` and `Object.NotEqual_IntInt`. The same function
already uses 155 about forty bytes further on, so the pair is in use in this
very context.

Why this is safe to write
-------------------------

The edit changes two bytes and moves nothing: same opcode width, same operand
width, so every jump offset in the function still lands where it did and
`R6Game.u` keeps the length its `.umd` slot demands. What it cannot do is prove
the game likes the result -- see the card's caution.

Finding it
----------

Structurally, never at a fixed address. The export tables of these `.u` files
are exact -- they are whole originals, not the two-range gathers a `.LIN` holds
-- so the function is found by name and owner, its script is PARSED, and the
gate is the last `==`-against-a-byte-constant that appears before the
`DeployCharacters` call. Then both bytes are checked before either is written.
A byte pattern alone would not do: this project has twice been bitten by a name
index that matched inside somebody else's value.
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
CALLS = "DeployCharacters"

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


def _locate(data, expect_op, expect_const):
    """(comparisonOffset, constantValueOffset) for the gate, or None.

    `expect_*` are the bytes that must already be there, so the same walk finds
    an untouched disc and a patched one without either being mistaken for the
    other.
    """
    from . import uscode

    try:
        (_v, _l, _f, ncount, noff, ecount, eoff, icount, ioff) = _summary(data)
    except CoopTeamError:
        return None
    names = _names(data, ncount, noff)
    if any(n not in names for n in (FUNCTION, CALLS, OWNER)):
        return None
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
        return None

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
        return None
    finally:
        uscode._parse_one = original

    wanted_call = names.index(CALLS)
    call_at, gates = None, []
    for top in script.toks:
        for tok in top.walk():
            if tok.name == "VirtualFunction":
                for kind, val in tok.parts:
                    if kind == "ref" and isinstance(val, (bytes, bytearray)):
                        idx, _ = _ci(bytes(val) + bytes(6), 0)
                        if idx == wanted_call:
                            call_at = where.get(id(tok))
            if _native(tok) != (154 if expect_op == EQ_INT else 155):
                continue
            kids = [v for k, v in tok.parts if k == "exprs"]
            for kid in (kids[0] if kids else []):
                const = _byte_const(kid)
                if const is not None:
                    gates.append((where[id(tok)], where[id(const)] + 1))

    if call_at is None:
        return None
    before = [g for g in gates if g[0] < call_at]
    if not before:
        return None
    op_at, const_at = max(before)
    if data[op_at] != expect_op or data[const_at] != expect_const:
        return None
    return op_at, const_at


def find_gate(data: bytes):
    """The shipped gate: `NetMode == NM_Standalone`. None if it is not there."""
    return _locate(data, EQ_INT, NM_STANDALONE)


def census(data: bytes):
    """(shipped, opened) -- which of the two states this package is in."""
    return (find_gate(data) is not None,
            _locate(data, NE_INT, NM_CLIENT) is not None)


def open_to_system_link(data: bytes):
    """Let a System Link host build the AI squad. Returns (bytes, changed).

    Idempotent: a package already carrying the change is returned untouched,
    because the shipped gate is no longer found in it.
    """
    gate = find_gate(data)
    if gate is None:
        return data, 0
    op_at, const_at = gate
    out = bytearray(data)
    out[op_at] = NE_INT
    out[const_at] = NM_CLIENT
    return bytes(out), 1

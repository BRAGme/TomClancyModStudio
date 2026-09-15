"""Split screen's second player, as the mission's own roster describes him.

What is wrong
-------------

In split screen player 2 is always Eddie Price, on every mission, whatever the
story says. On Island Estate the team is Chavez and Weber; in the Parking Garage
it is Chavez and Loiselle. The disc knows this -- it is not a guess.

Where the canon lives
---------------------

Every `/MAPS/<NAME>.INI` carries the roster, and it matches the game::

    ISLAND       Weber true,  Loiselle false, Price false
    GARAGE       Weber false, Loiselle true,  Price false
    OLDCITY_A    Weber false, Loiselle false, Price true
    AIRPORT      all three false -- Chavez goes in alone
    most others  all three true

`R6RainbowTeam.CreatePlayerTeam` already reads them, through
`GetMissionDescription().m_bMissionPrice` and its two siblings, and calls
`RemoveMember()` for anyone the mission does not include.

Why player 2 is Price
---------------------

`CreateTeamMember(iMember, ...)` chooses the pawn class from the member index::

    0 and 1 -> R6Characters.R6RainbowPrice[Winter]
    2       -> R6Characters.R6RainbowLoiselle[Winter]
    3       -> R6Characters.R6RainbowWeber[Winter]

with `bUseWinterMesh` coming from the mission's own skin set. Split screen
builds the team and then keeps **member 1**, and player 2 possesses it -- so
player 2 is Price by construction. Measured in a split-screen savestate: both
pawns are `R6RainbowPriceWinter`, player 1 with `m_iOperativeID` 0 and player 2
with 1. (Member 0 uses the Price class too, which is why
`R6RainbowPrice.PostBeginPlay` special-cases `m_iID == 0` into Ding Chavez.)

What this does
--------------

Rewrites the class choice for member 1 so that, when the mission does not
include Price but does include one of the others, member 1 loads that operative
instead::

    if (iMember == 1 && !m_bMissionPrice) {
        if (m_bMissionWeber)         -> R6RainbowWeber[Winter]
        else if (m_bMissionLoiselle) -> R6RainbowLoiselle[Winter]
    }

**Only `COMMON_SS.LIN` is edited**, and that is the whole reason there is no
split-screen test in the inserted code: `_SS` IS the split-screen package, so
the campaign and Terrorist Hunt copies are untouched by construction. That also
keeps single player exactly as it shipped, where member 1 must stay Price or the
mission-flag removals further down would leave the same operative twice.

Everything downstream follows from the class, which is the point of doing it
here rather than in four places: `m_iOperativeID` and `m_CharacterName` are
class defaults, the HUD's operative list is built from `m_Team[i].m_iOperativeID`
(`R6AbstractHUD.SetOperativeID`), the look-at name reads a character name, and
the death call-out picks its line from the same operative id.

Every piece of the inserted code is lifted off the disc rather than authored:
the six `DynamicLoadObject` statements and the `bUseWinterMesh` test come out of
`CreateTeamMember` itself, and the three `GetMissionDescription().m_bMission*`
tests out of `CreatePlayerTeam`. Nothing here invents a string, a class
reference or a native index.

The bytes are paid for out of the function's own dead `Log()` statements --
`bShowLog` reads False on every live teammate AI -- and the balance is padded
with `EX_Nothing` after the final return, exactly as `tcps2/uscode.py` does
everywhere else.
"""

from __future__ import annotations

import copy
import struct

from . import uscode
from .uscode import END, Script, Tok, ScriptError, compact_encode, parse_expr

#: `CreateTeamMember` is the only function on the disc that names this class.
TEAM_MEMBER_SIG = b"R6Characters.R6RainbowLoiselleWinter\x00"

#: and this string appears only in `CreatePlayerTeam`
PLAYER_TEAM_SIG = b"2# RescureTeamStartingPoint\x00"

#: the class each member index loads, by leaf name
PRICE, LOISELLE, WEBER = "R6RainbowPrice", "R6RainbowLoiselle", "R6RainbowWeber"

EX_JUMP = 0x06
EX_JUMP_IF_NOT = 0x07
EX_NOT_PRE_BOOL = 0x81
EX_EQUAL_INT = 0x9A
EX_INT_ONE = 0x26
EX_END_PARMS = 0x16


class CanonError(Exception):
    pass


def _block(plain, signature, what):
    """The script block containing `signature`.

    A signature may occur more than once -- `CreatePlayerTeam` logs the same
    string twice -- so what has to be unique is the BLOCK, not the hit. Every
    occurrence must land in the same one or this refuses rather than guessing.
    """
    hits = []
    at = plain.find(signature)
    while at >= 0:
        hits.append(at)
        at = plain.find(signature, at + 1)
    if not hits:
        raise CanonError("%s is not in this file" % what)
    found = [_enclosing(plain, h, what) for h in hits]
    if len({f[0] for f in found}) != 1:
        raise CanonError("%s appears in more than one script block" % what)
    return found[0]


def _enclosing(plain, at, what):
    for size_at in range(at - 4, max(0, at - 20000), -1):
        n = struct.unpack_from("<I", plain, size_at)[0]
        if not (16 <= n <= 60000):
            continue
        try:
            script = Script.at(plain, size_at)
        except Exception:
            continue
        if size_at + 4 <= at < size_at + 4 + script.disk_len:
            return size_at, script
    raise CanonError("found %s but no script block around it" % what)


def _jumpfree(tok, what):
    for x in tok.walk():
        for kind, _v in x.parts:
            if kind in ("jump", "jump32", "case", "labels"):
                raise CanonError("%s contains a jump and cannot be copied" % what)
    return tok


def _class_loads(script):
    """{leafName: {True: winterLet, False: plainLet}} lifted off the disc."""
    out = {}
    for tok in script.toks:
        if tok.name != "Let":
            continue
        strings = [v[:-1].decode("latin1") for t in tok.walk()
                   for k, v in t.parts if k == "str"]
        if len(strings) != 1 or not strings[0].startswith("R6Characters."):
            continue
        leaf = strings[0].rsplit(".", 1)[-1]
        winter = leaf.endswith("Winter")
        base = leaf[:-6] if winter else leaf
        out.setdefault(base, {}).setdefault(
            winter, _jumpfree(copy.deepcopy(tok), leaf))
    missing = [n for n in (PRICE, LOISELLE, WEBER)
               if n not in out or len(out[n]) != 2]
    if missing:
        raise CanonError("the disc does not load both meshes for: %s"
                         % ", ".join(missing))
    return out


def _case_bodies(script):
    """The first statement of the Loiselle and Weber arms of the class switch.

    A `Case` marks the arm; the statement after it in the list is the arm's
    body, and entering there runs that arm's own winter/summer choice and its
    own exit jump. Found by the constant the case compares against -- 2 is
    Loiselle and 3 is Weber, the same numbering `m_iOperativeID` uses.
    """
    want = {2: LOISELLE, 3: WEBER}
    out = {}
    for i, tok in enumerate(script.toks):
        if tok.name != "Case":
            continue
        off, expr = tok.parts[0][1]
        if expr is None or expr.name not in ("ByteConst", "IntConstByte"):
            continue
        value = expr.parts[0][1][0]
        if value in want and i + 1 < len(script.toks):
            out.setdefault(want[value], script.toks[i + 1])
    if set(out) != {LOISELLE, WEBER}:
        raise CanonError("the class switch does not have both arms this needs")
    return out


def _winter_test(script):
    for tok in script.toks:
        if tok.name == "JumpIfNot" and tok.parts[1][1].name == "BoolVariable":
            return _jumpfree(copy.deepcopy(tok.parts[1][1]), "bUseWinterMesh")
    raise CanonError("the winter-mesh test is not in CreateTeamMember")


def _member_var(script):
    for tok in script.toks:
        if tok.name == "Switch":
            return _jumpfree(copy.deepcopy(tok.parts[1][1]), "iMember")
    raise CanonError("CreateTeamMember does not switch on its member index")


def _mission_tests(script):
    """The three `GetMissionDescription().m_bMission*` reads, in shipped order.

    Shipped order is Price, Loiselle, Weber -- the order `CreatePlayerTeam`
    removes them in. Taking them positionally rather than by name is deliberate:
    the property reference inside each is a package index this module cannot
    compute, and the names are not in the bytecode at all.
    """
    found = []
    for tok in script.toks:
        if tok.name != "JumpIfNot":
            continue
        for sub in tok.parts[1][1].walk():
            if sub.name != "Context":
                continue
            inner = sub.parts[3][1] if len(sub.parts) > 3 else None
            if (inner is not None and inner.name == "BoolVariable"
                    and sub.parts[0][1].op >= 0x60):
                found.append(_jumpfree(copy.deepcopy(sub), "a mission flag"))
                break
    if len(found) != 3:
        raise CanonError("expected three mission-roster tests, found %d"
                         % len(found))
    return dict(zip((PRICE, LOISELLE, WEBER), found))


def _dead_logs(script):
    """The dead `Log(...)` statements, largest first, as removal candidates.

    The `if (bShowLog)` guard in front of each is deliberately LEFT in place.
    Removing it too would free a few more bytes, but a guard is routinely the
    target of some earlier jump, and `Script.remove` rightly refuses to delete a
    jump target. Left alone the guard simply jumps to the statement it always
    jumped to, which is now the one right after it -- dead either way, since
    `bShowLog` is False on every live teammate AI.
    """
    logs, guards = [], []
    for i, tok in enumerate(script.toks):
        if tok.op < 0x60:
            continue
        if not any(k == "str" for t in tok.walk() for k, _v in t.parts):
            continue
        logs.append((tok.dlen, [tok]))
        guard = script.toks[i - 1] if i else None
        if guard is not None and guard.name == "JumpIfNot"                 and guard.parts[1][1].name == "BoolVariable":
            # only offered AFTER its log has gone -- a guard removed while its
            # log survives would make that log run unconditionally
            guards.append((guard.dlen, [guard], tok))
    logs.sort(key=lambda p: -p[0])
    guards.sort(key=lambda p: -p[0])
    return logs + guards


def apply(plain: bytes, enable: bool = True):
    """Give split screen's second player the mission's own operative."""
    if not enable:
        return plain, 0
    if reads(plain):
        return plain, 0
    size_at, script = _block(plain, TEAM_MEMBER_SIG, "CreateTeamMember")
    _pt_at, player_team = _block(plain, PLAYER_TEAM_SIG, "CreatePlayerTeam")

    winter = _winter_test(script)          # asserted present, though unused:
    member = _member_var(script)           # the arms we jump into rely on it
    flags = _mission_tests(player_team)
    del winter

    # The switch already has an arm for Loiselle and one for Weber, complete
    # with their own winter/summer choice and their own exit jump. So rather
    # than building four more `DynamicLoadObject` statements -- 182 bytes the
    # function has no room for -- the canon case simply JUMPS INTO the arm that
    # already loads the right operative. `bUseWinterMesh` is computed before the
    # switch, so it is already set when the arm is entered.
    arms = _case_bodies(script)
    switch = next(t for t in script.toks if t.name == "Switch")

    def jump_to(target):
        j = Tok(EX_JUMP)
        j.parts = [("jump", target)]
        return j

    def test(cond, target):
        t = Tok(EX_JUMP_IF_NOT)
        t.parts = [("jump", target), ("expr", cond)]
        return t

    def negate(expr):
        n = Tok(EX_NOT_PRE_BOOL)
        n.parts = [("exprs", [expr])]
        return n

    block = [
        test(_equals_one(member), switch),                       # not member 1
        test(negate(copy.deepcopy(flags[PRICE])), switch),       # Price is in
        test(copy.deepcopy(flags[WEBER]), None),                 # -> patched
        jump_to(arms[WEBER]),
        test(copy.deepcopy(flags[LOISELLE]), switch),
        jump_to(arms[LOISELLE]),
    ]
    block[2].parts[0] = ("jump", block[4])      # no Weber -> try Loiselle

    # anything that used to jump at the switch must now enter the new block
    first = block[0]
    for tok in script.statements():
        for i, (kind, val) in enumerate(tok.parts):
            if kind == "jump" and val is switch:
                tok.parts[i] = (kind, first)
            elif kind == "case":
                off, sub = val
                if off is switch:
                    tok.parts[i] = (kind, (first, sub))
    script.toks[script.toks.index(switch):script.toks.index(switch)] = block

    # Pay for it out of the dead log lines, one at a time, until it fits. The
    # assembler's refusal is the budget check: measuring up front would be
    # guesswork, since a copied statement reports the length it had where it
    # came from and a freshly built one reports nothing until assembled.
    out = bytearray(plain)
    spare = _dead_logs(script)
    freed = 0
    while True:
        try:
            script.write_into(out, size_at)
            break
        except ScriptError as exc:
            if not spare:
                raise CanonError("the canon team does not fit: %s (reclaimed "
                                 "%d bytes of dead logging, which was not "
                                 "enough)" % (exc, freed)) from exc
            entry = spare.pop(0)
            size, group = entry[0], entry[1]
            if len(entry) == 3 and entry[2] in script.toks:
                continue            # its log is still there; leave the guard
            try:
                script.remove(group)
                freed += size
            except ScriptError:
                continue
    if len(out) != len(plain):
        raise CanonError("the canon-team edit changed the file length")
    Script.at(bytes(out), size_at)
    return bytes(out), 1


def _equals_one(member):
    eq = Tok(EX_EQUAL_INT)
    one = Tok(EX_INT_ONE)
    eq.parts = [("exprs", [member, one])]
    return eq


def reads(plain: bytes) -> bool:
    """True if this file already picks the canon operative for member 1.

    The tell is a `Jump` straight into one of the class switch's arms. Nothing
    the game ships does that -- an arm is only ever entered through its `Case`.
    """
    try:
        _at, script = _block(plain, TEAM_MEMBER_SIG, "CreateTeamMember")
        arms = set(id(t) for t in _case_bodies(script).values())
    except Exception:
        return False
    for tok in script.toks:
        if tok.name == "Jump":
            target = tok.parts[0][1]
            if target is not END and id(target) in arms:
                return True
    return False


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "canon_team", "Player 2 is the mission's own operative",
        BOOL, False, group, confidence="experimental", touches="data",
        help="In split screen player 2 is Eddie Price on every mission. The "
             "story disagrees, and so does the disc: each map's INI carries the "
             "roster, and Island Estate is Chavez and Weber while the Parking "
             "Garage is Chavez and Loiselle.\n\n"
             "Split screen builds the full team and then keeps member 1, and "
             "member 1 is always the Price class. This makes that choice read "
             "the mission's own roster, so on a map that leaves Price out, "
             "player 2 becomes whoever actually went in. Because the operative "
             "id and the character name are properties of the pawn class, the "
             "HUD name, the name shown when player 1 puts the crosshair on "
             "player 2, and the line called when a player goes down should all "
             "follow from it.\n\n"
             "Only COMMON_SS.LIN is touched -- the split-screen package -- so "
             "single player and Terrorist Hunt are untouched by construction.",
        caution="Experimental, and the most speculative option here: it "
                "inserts about 250 bytes of new script into the function that "
                "builds the team, and it has never been run. That is the same "
                "function four earlier attempts at putting AI teammates into "
                "split screen all hung the level load in -- those added "
                "members, and this only changes which class one member loads, "
                "which is a smaller change, but it is the same code.\n\n"
                "The weapon-select portrait is the one part not traced to the "
                "operative id, so it may keep showing Price even when "
                "everything else changes. If a split-screen level stops "
                "loading, this is the first thing to turn off.")

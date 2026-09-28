"""Player 2 reacting out loud in split screen.

What is wrong
-------------

In single player an AI teammate says "Nice shot" when you drop a tango, and
"Watch your fire, those are the good guys" when you hit a hostage. In split
screen nobody says anything, and the reason is the same three-layer one that
kills the death call-out -- see `rsemandown`, which documents it at length.

The function is `R6PlayerController`'s kill handler, and it ships like this::

    if (Level.NetMode == 0)
      switch (DeadPawn.m_ePawnType) {
        case TERRORIST:
          if (m_iMemberCount > 1 && !DeadPawn.m_bIsKneeling)
            if (m_TeamManager.IsRainbowAINearPlayer() && Rand(100) < 10) {
              if (Damage == 1) m_Team[1].Controller.PlaySoundCurrentAction(100)
              if (Damage == 2) m_Team[1].Controller.PlaySoundCurrentAction(101)
            }
          break;
        case HOSTAGE:
          if (m_iMemberCount > 1 && m_TeamManager.IsRainbowAINearPlayer())
            m_Team[1].Controller.PlaySoundCurrentAction(27)
          break;
      }

Three things stop it in split screen, and only the third is obvious:

1. `m_iMemberCount > 1`. Measured from a savestate, the count is **1** in split
   screen, so this is false before anything else is asked.
2. `IsRainbowAINearPlayer()`. Split screen has no `R6RainbowAI` at all, so this
   can never be true.
3. `m_Team[1].Controller.PlaySoundCurrentAction(...)`. In split screen team slot
   1 is the other PLAYER, and `R6PlayerController` does not override
   `PlaySoundCurrentAction` -- the inherited one is two bytes of
   `Return(Nothing)`. Removing the first two gates alone changes nothing.

What this does
--------------

Neutralises the two gates, and replaces each dead call with one that builds its
own voice, exactly the way `rsemandown` does::

    if (True && !DeadPawn.m_bIsKneeling)
      if (True && Rand(100) < chance)
        new R6PriceVoices.PlayRainbowVoices(m_Team[1], 100 / 101)

The kneeling test is deliberately kept: the game does not compliment you for
executing a man who has already surrendered, and neither does this.

**The percentage is the game's own.** `Rand(100) < 10` is shipped code, so the
setting is not a new gate bolted on -- it is the number Red Storm already chose,
made adjustable. 0 leaves the disc alone.

Whose voice
-----------

Price's, because the class in the `New` is a constant and there is no property
on a pawn that names its voices class -- the voice is decided purely by which
`R6RainbowVoices` subclass gets instantiated. That is *correct* by default:
split screen gives player 2 `m_iOperativeID` 1, which is Price. It is only
wrong if `canon_team` is also on, which can make player 2 Weber or Loiselle for
a given mission; the line then plays in Price's voice. Dispatching on the
operative needs three `New` expressions and their guards, about 80 bytes, and
this function has 28 to spare.

Why only the split-screen package
---------------------------------

`COMMON_SS.LIN` **is** the split-screen package, so single player and Terrorist
Hunt are untouched by construction and no single-player regression is possible.
"""

from __future__ import annotations

import copy
import struct

from . import rsemandown
from .uscode import Script, Tok, ScriptError, compact_encode, parse_expr

#: A window inside the kill handler that this edit never touches.
#:
#: The function carries no string constants, so like the man-down edit it cannot
#: be found by its own text, and the obvious anchor -- the block's `ScriptSize`
#: word, or the start of its bytecode -- is no good either: the edit changes the
#: size, and bytecode byte 1 is the low half of the opening `JumpIfNot`'s target,
#: which moves. Chosen by diffing the block before against after: this is inside
#: the longest run the rewrite leaves alone, which starts two bytes into the
#: bytecode. Measured unique in COMMON.LIN, COMMONOFF.LIN and COMMON_SS.LIN.
ANCHOR = bytes.fromhex("019a393a19018f05000101a2393a2400160501192e02005c")

#: how far the anchor sits past the block's `ScriptSize` word
ANCHOR_AT = 6

#: the two gates, and the three calls, in the block's own memory offsets
KNEEL_GATE = 0x033          # JumpIfNot(AndAnd(m_iMemberCount > 1, !kneeling))
ROLL_GATE = 0x062           # JumpIfNot(AndAnd(IsRainbowAINearPlayer(), Rand))
HOSTAGE_GATE = 0x0F6        # JumpIfNot(AndAnd(m_iMemberCount > 1, AI near))
CALL_KILL = 0x091           # PlaySoundCurrentAction(100)  "nice shot"
CALL_GRENADE = 0x0C9        # PlaySoundCurrentAction(101)  "...with a grenade"
CALL_HOSTAGE = 0x11E        # PlaySoundCurrentAction(27)   "watch your fire"

#: voice actions, read off the `Switch` in `R6RainbowVoices.PlayRainbowVoices`
VOICE_KILL = 100
VOICE_KILL_GRENADE = 101
VOICE_HIT_HOSTAGE = 27

#: the shipped roll, so `reads` can tell an untouched disc from a 10% setting
STOCK_CHANCE = 10
MAX_CHANCE = 90

EX_CONTEXT = 0x19
EX_NEW = 0x11
EX_BYTE_CONST = 0x24
EX_TRUE = 0x27
EX_VIRTUAL_FUNCTION = 0x1B

#: `Less_IntInt`, read off the game's own UFunction table
NATIVE_LESS = 0x96


class ChatterError(Exception):
    pass


def find_block(plain: bytes) -> int:
    """Offset of the ScriptSize word of the player's kill handler."""
    at = plain.find(ANCHOR)
    if at < 0:
        raise ChatterError("the player kill handler is not in this file")
    if plain.find(ANCHOR, at + 1) >= 0:
        raise ChatterError("the player kill handler appears more than once; "
                           "refusing to guess which one to change")
    size_at = at - ANCHOR_AT
    if size_at < 0:
        raise ChatterError("the function has no room for a length word")
    declared = struct.unpack_from("<I", plain, size_at)[0]
    if not (16 <= declared <= 20000):
        raise ChatterError("the word in front of the function is %d, which is "
                           "not a script length" % declared)
    return size_at


def _operands(tok):
    """The `[A, Skip(B)]` list inside an `AndAnd_BoolBool`.

    A native call keeps every argument in one `exprs` part, so the two halves of
    a `&&` are list entries rather than separate fields.
    """
    if tok.op < 0x60 or not tok.parts or tok.parts[0][0] != "exprs":
        raise ChatterError("this disc revision does not gate the call the way "
                           "this edit expects")
    return tok.parts[0][1]


def _speak(proto, pawn, action):
    """`new R6PriceVoices.PlayRainbowVoices(pawn, action)`, as one statement."""
    speak = Tok(EX_VIRTUAL_FUNCTION)
    speak.parts = [("ref", compact_encode(rsemandown.PLAY_RAINBOW_VOICES)),
                   ("exprs", [copy.deepcopy(pawn),
                              parse_expr(bytes([EX_BYTE_CONST, action]))])]
    ctx = Tok(EX_CONTEXT)
    ctx.parts = [("expr", copy.deepcopy(proto)), ("skip", b"\0\0"),
                 ("u8", b"\0"), ("expr", speak)]
    ctx.skip_base = None
    return ctx


def apply(plain: bytes, chance: int = 0, hostage: bool = True):
    """Give player 2 a voice for player 1's kills. Returns (plain, changed)."""
    chance = max(0, min(int(chance), MAX_CHANCE))
    if not chance:
        return plain, 0
    size_at = find_block(plain)
    if reads(plain)[0]:
        return plain, 0
    script = Script.at(plain, size_at)

    kneel = script.statement_at(KNEEL_GATE)
    roll = script.statement_at(ROLL_GATE)
    host = script.statement_at(HOSTAGE_GATE)
    if kneel.name != "JumpIfNot" or roll.name != "JumpIfNot":
        raise ChatterError("this disc revision does not have the two gates "
                           "this edit expects")

    # 1. the two head counts, which are false in split screen
    _operands(kneel.parts[1][1])[0] = parse_expr(bytes([EX_TRUE]))
    # 2. "is an AI teammate nearby", which can never be true without AI
    roll_args = _operands(roll.parts[1][1])
    roll_args[0] = parse_expr(bytes([EX_TRUE]))
    # 3. the roll itself -- the game's own Rand(100) < 10
    cmp_tok = roll_args[1].parts[1][1]
    if cmp_tok.op != NATIVE_LESS:
        raise ChatterError("the roll in this disc revision is not the "
                           "comparison this edit expects")
    cmp_tok.parts[0][1][1] = parse_expr(bytes([EX_BYTE_CONST, chance]))

    proto = rsemandown._price_voices(plain)
    wanted = [(CALL_KILL, VOICE_KILL), (CALL_GRENADE, VOICE_KILL_GRENADE)]
    if hostage:
        host_args = _operands(host.parts[1][1])
        host_args[0] = parse_expr(bytes([EX_TRUE]))
        host_args[1].parts[1] = ("expr", parse_expr(bytes([EX_TRUE])))
        wanted.append((CALL_HOSTAGE, VOICE_HIT_HOSTAGE))
    for off, action in wanted:
        call = script.statement_at(off)
        if call.op != EX_CONTEXT:
            raise ChatterError("the call at 0x%x is not the one this edit "
                               "expects" % off)
        pawn = call.parts[0][1].parts[0][1]
        script.toks[script.toks.index(call)] = _speak(proto, pawn, action)

    out = bytearray(plain)
    script.write_into(out, size_at)
    if len(out) != len(plain):
        raise ChatterError("the chatter edit changed the file length")
    Script.at(bytes(out), size_at)          # read back through the same parser
    return bytes(out), 1


def reads(plain: bytes):
    """(chance, hostage) as this file currently stands. (0, False) if untouched.

    The edit moves every memory offset in the block, so nothing here may look a
    statement up by address. A converted call is a `Context` whose left-hand
    side is a `New` -- shipped code never contexts off a `New` in this function
    -- and the roll is the only `Less_IntInt` in it.
    """
    try:
        script = Script.at(plain, find_block(plain))
    except Exception:                                   # noqa: BLE001
        return 0, False
    actions, chance = set(), 0
    for tok in script.statements():
        if (tok.op == EX_CONTEXT and tok.parts[0][1].op == EX_NEW
                and tok.parts[3][1].op == EX_VIRTUAL_FUNCTION):
            arg = tok.parts[3][1].parts[1][1][-1]
            if arg.op == EX_BYTE_CONST:
                actions.add(arg.parts[0][1][0])
        elif tok.op == NATIVE_LESS:
            arg = tok.parts[0][1][1]
            if arg.op == EX_BYTE_CONST:
                chance = arg.parts[0][1][0]
    if VOICE_KILL not in actions:
        return 0, False
    return chance, VOICE_HIT_HOSTAGE in actions


def cards(prefix, group):
    from .model import BOOL, INT, Setting

    return [
        Setting(prefix + "ss_chatter_kill",
                "Player 2 calls out player 1's kills in split screen",
                INT, 0, group, minimum=0, maximum=MAX_CHANCE, unit="%", confidence="experimental", touches="data",
                help="In single player a teammate says \"Nice shot\" when you "
                     "drop a tango, and a different line when you do it with a "
                     "grenade. In split screen nobody does.\n\n"
                     "Three things stop it, and only the last is obvious: the "
                     "handler asks for more than one team member, which split "
                     "screen does not have; it asks whether an AI teammate is "
                     "nearby, and split screen has no AI at all; and the "
                     "speaker it picks is team slot 1, which in split screen is "
                     "the other PLAYER, whose controller inherits an empty "
                     "`PlaySoundCurrentAction`. This clears all three and gives "
                     "the line its own voice, built the way the game builds one."
                     "\n\nThe percentage is the game's own `Rand(100) < 10`, "
                     "made adjustable rather than invented. 0 leaves the disc "
                     "alone; %d is what the game ships." % STOCK_CHANCE,
                caution="Experimental: reasoned from the disassembly and never "
                        "heard. The line plays in Price's voice, because the "
                        "class is a constant in the bytecode and nothing on a "
                        "pawn names its voices class. That is right by default "
                        "-- split screen makes player 2 Price -- but if you "
                        "also turn on the canon team, player 2 can be Weber or "
                        "Loiselle and will still speak with Price's voice.\n\n"
                        "The kneeling check is kept, so there is no compliment "
                        "for shooting someone who has surrendered."),
        Setting(prefix + "ss_chatter_hostage",
                "...and when player 1 hits a hostage", BOOL, True, group,
                confidence="experimental", touches="data",
                requires={prefix + "ss_chatter_kill": list(range(1, MAX_CHANCE + 1))},
                help="The same handler has a second arm for shooting a "
                     "hostage -- \"Check your fire\" -- gated the same way and "
                     "dead for the same reasons. This one is not a roll: the "
                     "game plays it every time, and so does this.\n\nIt rides "
                     "along with the call-out setting above because it is the "
                     "same function and the same rewrite; there is nothing to "
                     "gain by splitting them."),
    ]

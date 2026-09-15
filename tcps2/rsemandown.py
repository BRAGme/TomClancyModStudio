"""The death call-out that split screen never plays.

What is wrong
-------------

In single player, a teammate says "Lead down. I say again, Lead is down." when
you die. In split screen nobody says anything, and it is not one gate but three
-- the first of which looks like the whole answer and is not.

`R6PlayerController.PlaySoundDamage`, death case (`m_eHealth` == 5)::

    if (!Level.Game.m_bIsSplitScreen)                        <-- 1
        if (m_iMemberCount > 0 && m_Team[1] != None)
            m_Team[1].Controller.PlaySoundCurrentAction(23)   <-- 2

1. That `!m_bIsSplitScreen` test jumps straight past the call. Removable.
2. The speaker is `m_Team[1].Controller`, hardcoded. The array really does hold
   both players in split screen -- measured from a savestate, the slots are
   `[R6RainbowPriceWinter0, R6RainbowPriceWinter1, None, None]` -- so slot 1 is
   the other player, and `R6PlayerController` does not override
   `PlaySoundCurrentAction`. The inherited `Controller.PlaySoundCurrentAction`
   is two bytes: `Return(Nothing)`.
3. And it could not speak even then. `PlayRainbowVoices` has exactly ONE caller
   in the entire loaded script -- `R6RainbowAI.PlaySoundCurrentAction` -- and it
   reads `R6RainbowAI.m_VoicesMgr`, which only an `R6RainbowAI` ever creates.
   Split screen has none: a single-player savestate holds three voices managers
   and a split-screen one holds **zero**.

So no Rainbow voice line of any kind can play in split screen, because the only
thing in the game that owns a voice is the AI teammate.

What this does
--------------

Neutralises the gate and replaces the dead call with one that builds its own
voice::

    if (True)
        if (m_iMemberCount > 0 && m_Team[1] != None)
            new R6PriceVoices.PlayRainbowVoices(m_Team[1], 23)

Both halves are lifted from shipped code rather than invented. The
`New(Nothing, Nothing, Nothing, ObjectConst(R6Engine.R6PriceVoices))` is copied
out of `R6RainbowAI.Possess`, which is where the game builds its own; the
`PlayRainbowVoices` name index and the `m_Team[1]` subtree are copied out of the
function being edited and its one existing caller. `Init()` is deliberately not
called: all it does is `AddSoundBankName("X_Voices_Price")`, and the three
operative voice packages are already loaded in split screen -- confirmed in the
savestate, `X_Voices_Price`, `X_Voices_Weber` and `X_Voices_Loiselle` are all
live `Package` objects there.

The whole thing fits in the function's own 283 disk bytes with nothing to spare,
which is why there is no operative dispatch -- see the card's caution.
"""

from __future__ import annotations

import copy
import struct

from . import uscode
from .uscode import Script, Tok, ScriptError, parse_expr, compact_encode

#: A window inside `R6PlayerController.PlaySoundDamage` that this edit never
#: touches. The function carries no string constants, so unlike the sidearm edit
#: it cannot be found by its own text.
#:
#: Chosen by diffing the block before and against after: of its 283 bytes only
#: two runs survive the rewrite unchanged, and this is the long one. It starts
#: TWO bytes into the bytecode because byte 1 is the low half of the opening
#: `JumpIfNot`'s target, and that target moves -- the obvious anchor, the start
#: of the block or its `ScriptSize` word, would find the function before the
#: edit and never again. Measured unique: one occurrence in each of COMMON.LIN,
#: COMMONOFF.LIN and COMMON_SS.LIN.
ANCHOR = bytes.fromhex(
    "019a393a19018f05000101a2393a240016050119010b0500")

#: how far the anchor sits past the block's `ScriptSize` word
ANCHOR_AT = 6

#: `R6RainbowAI.Possess`, which builds the game's own voices managers. Its first
#: `New` is the operative-1 case, `R6PriceVoices`.
POSSESS_ANCHOR = bytes.fromhex("f9000000")      # ScriptSize = 249

#: Name-table index of `PlayRainbowVoices`, read off the one shipped call in
#: `R6RainbowAI.PlaySoundCurrentAction`. Both functions live in the same
#: sub-package, so they share a name table and the index carries over.
PLAY_RAINBOW_VOICES = 1207

#: Voice action 23 is `m_sndLeadDown`. 24, 25 and 26 are Loiselle, Price and
#: Weber; the shipped code in `R6RainbowAI.PlaySoundDamage` picks between them
#: on `m_iOperativeID`, and this one cannot afford to -- see the module note.
VOICE_LEAD_DOWN = 23

EX_CONTEXT = 0x19
EX_VIRTUAL_FUNCTION = 0x1B
EX_BYTE_CONST = 0x24
EX_TRUE = 0x27
EX_NEW = 0x11

#: where the two statements sit, in the block's own memory offsets
GUARD_AT = 0x033
CALL_AT = 0x07C


class ManDownError(Exception):
    pass


def find_block(plain: bytes) -> int:
    """Offset of the ScriptSize word of `R6PlayerController.PlaySoundDamage`."""
    at = plain.find(ANCHOR)
    if at < 0:
        raise ManDownError("the player death function is not in this file")
    if plain.find(ANCHOR, at + 1) >= 0:
        raise ManDownError("the player death function appears more than once; "
                           "refusing to guess which one to change")
    size_at = at - ANCHOR_AT
    if size_at < 0:
        raise ManDownError("the function has no room for a length word")
    declared = struct.unpack_from("<I", plain, size_at)[0]
    if not (16 <= declared <= 20000):
        raise ManDownError("the word in front of the function is %d, which is "
                           "not a script length" % declared)
    return size_at


def _price_voices(plain: bytes):
    """The `New(..., R6PriceVoices)` expression, copied out of `Possess`.

    Taken from the disc rather than written here, because the class reference
    inside it is a package index this module has no way to compute.
    """
    at = plain.find(POSSESS_ANCHOR)
    while at >= 0:
        try:
            script = Script.at(plain, at)
        except ScriptError:
            at = plain.find(POSSESS_ANCHOR, at + 1)
            continue
        news = [t for t in script.statements() if t.op == EX_NEW]
        if len(news) == 3:
            return copy.deepcopy(news[0])
        at = plain.find(POSSESS_ANCHOR, at + 1)
    raise ManDownError("could not find where the game builds a voices manager")


def apply(plain: bytes, enable: bool = True):
    """Make the split-screen death call-out speak. Returns (plain, changed)."""
    if not enable:
        return plain, 0
    size_at = find_block(plain)
    script = Script.at(plain, size_at)
    if reads(plain):
        return plain, 0

    guard = script.statement_at(GUARD_AT)
    call = script.statement_at(CALL_AT)
    if guard.name != "JumpIfNot" or call.op != EX_CONTEXT:
        raise ManDownError("this disc revision does not have the two "
                           "statements this edit expects")

    # `m_Team[1]`, lifted out of the call being replaced
    pawn = call.parts[0][1].parts[0][1]

    speak = Tok(EX_VIRTUAL_FUNCTION)
    speak.parts = [("ref", compact_encode(PLAY_RAINBOW_VOICES)),
                   ("exprs", [pawn,
                              parse_expr(bytes([EX_BYTE_CONST,
                                                VOICE_LEAD_DOWN]))])]
    ctx = Tok(EX_CONTEXT)
    ctx.parts = [("expr", _price_voices(plain)), ("skip", b"\0\0"),
                 ("u8", b"\0"), ("expr", speak)]
    ctx.skip_base = None

    script.toks[script.toks.index(call)] = ctx
    guard.parts[1] = ("expr", parse_expr(bytes([EX_TRUE])))

    out = bytearray(plain)
    script.write_into(out, size_at)
    if len(out) != len(plain):
        raise ManDownError("the man-down edit changed the file length")
    Script.at(bytes(out), size_at)          # read back through the same parser
    return bytes(out), 1


def reads(plain: bytes) -> bool:
    """True if this file already has the call-out wired."""
    try:
        script = Script.at(plain, find_block(plain))
        guard = script.statement_at(GUARD_AT)
    except Exception:
        return False
    return guard.parts[1][1].op == EX_TRUE


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "ss_man_down", "\"Man down\" when a player dies in split "
        "screen", BOOL, False, group, confidence="experimental",
        touches="data",
        help="In single player a teammate calls it when you go down. In split "
             "screen nobody does, and it is not one gate but three: the death "
             "case is skipped by an explicit `!m_bIsSplitScreen` test; the "
             "speaker is hardcoded to `m_Team[1].Controller`, which in split "
             "screen is the other PLAYER, whose controller inherits an empty "
             "`PlaySoundCurrentAction`; and nothing in split screen owns a "
             "voice at all, because the only thing that builds one is the AI "
             "teammate and split screen has none.\n\n"
             "This drops the gate and gives the call its own voice, built the "
             "way the game builds one -- the `New(... R6PriceVoices)` is "
             "copied out of `R6RainbowAI.Possess`. The three operative voice "
             "banks are already loaded in split screen, so there is nothing to "
             "stream in.",
        caution="Experimental: reasoned from the disassembly and never heard. "
                "Two known limits, both from the same cause -- the rewrite "
                "fills the function's 283 bytes exactly, with nothing spare. "
                "It always plays line 23, \"Lead down\", so player 2 going "
                "down is announced as the lead rather than as Price. And the "
                "speaker is team slot 1, which the game hardcodes: in split "
                "screen that is player 2's own pawn, so when player 2 is the "
                "one who died the line comes from a dead man and may not play "
                "at all. Both are fixed by giving player 2 a real operative "
                "identity, which is a separate job.")

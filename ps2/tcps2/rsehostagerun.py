"""A guarded hostage's reaction to Rainbow arriving: the line that never plays.

What is wrong
-------------

`EHostageVoices` value 0 is `HV_Run`, property `m_sndRun`. Despite the name it
is not "running": the cue recorded for it is `Host<N>_M<nn>_WithRnb_Terro` --
the hostage reacting to Rainbow arriving **while a terrorist is still there**.
It is assigned on all fifteen voice sets, it is resident in every map's own
`<MAP>_L.SB1` as a two-take random container (thirty finished takes across the
game), and `R6HostageVoices.PlayHostageVoices` has a correct `case 0` arm for
it. **Nothing in the loaded script ever passes it.** Verified twice: once by
scanning every live `Script` range in a savestate, and once on disc, where a
byte scan of all three COMMON packages finds eight `ProcessPlaySndInfo(<byte>)`
call sites carrying 1, 2, 3, 3, 4, 5, 6 and 1 -- and no 0.

Why it is missing is not a mystery. Raven Shield 1.56 drives it from
`R6HostageMgr.InitSndEventInfo`, entry `HSTSNDEvent_HstRunTowardRainbow` = 5 ->
`HV_Run`, raised from exactly one place: `state GoHstRunTowardRainbow`, which
the reaction table reaches for `(HstGuarded, threat level 2, roll 61-100)` and
for `(HstFreed, level 2)`. The console build deleted the whole `HSTSNDEvent`
table and that state with it -- `GoHstRunTowardRainbow` is not even in the
package's name table -- and `R6HostageMgr.InitReaction` now reads
`HearShootingReaction` in both of those rows. So the PS2 disc plays the generic
"I hear shooting" line where the PC plays `WithRnb_Terro`.

Why the obvious repair does not work
------------------------------------

Putting the call back in that arm of `R6HostageAI.ProcessThreat` looks right and
is dead. The console build made a second change the PC does not have:
`R6HostageAI.SeePlayerMgr` opens with

    if ( !m_lastSeenPawn.IsAlive() || m_lastSeenPawn.m_ePawnType == PAWN_Rainbow )
        return;

and `PAWN_Rainbow` is 1 -- proved from `GetRainbowWhoEscortThisPawn`, where the
`== 1` branch casts to `R6Rainbow` and the `== 3` branch to `R6Hostage`. The
sight path therefore **never** delivers a Rainbow operative to `ProcessThreat`,
so threat level 2 ("see friend", `NOISE_None`, the only rows that reach
`HV_Run` on PC) can be raised only by a hostage seeing another hostage. Level 2
is also what `GoGuarded_Foetus` and `GoGuarded_frozen` hang off, which is why
hostages cower at each other rather than at you.

Neutralising that early-out is one byte, and it is deliberately NOT done here:
it would also let a **freed** hostage re-enter `ProcessThreat` on every tick he
can see you, and freed level 2 has no absorbing state on this build, so he
would repeat a line once a second. On PC that row goes to
`GoHstRunTowardRainbow`, which changes state and ends it. Restoring that is a
different and much bigger job.

What this does instead
----------------------

The one reachable place where a guarded hostage registers both "Rainbow is
here" and "something just happened" is the `GuardedPlayReaction` arm of
`ProcessThreat` -- `(HstGuarded, level 1)`, a guarded hostage hearing a threat
noise or a death. Guarded means a terrorist is still holding him, which is the
`_Terro` half of the cue; `m_lastSeenPawn` being a Rainbow is the `WithRnb`
half. The shipped reaction table even labels that row "fire a function: react +
noise", and it is the only one of the three arms with no `ProcessPlaySndInfo`
call in it.

    else if ( 'GuardedPlayReaction' == stateName )
    {
        if ( m_iPlayReaction1 == 0 )
        {
            m_iPlayReaction1 = 1;
            m_iPlayReaction2 = RandRange(0,2);
            if ( R6Rainbow(m_lastSeenPawn) == None )      // <-- new
                goto HearShootingReaction;                // <-- new
            ProcessPlaySndInfo( HV_Run );                 // <-- new
        }
        ResetThreatInfo( "GuardedPlayReaction" );
    }

`m_iPlayReaction1 == 0` is the shipped one-shot: `Guarded.BeginState` clears it
and the reaction drain clears it again, so this speaks once per reaction cycle,
at the cadence the hear-shooting line already has. Nothing new is invented.

The "not a Rainbow" path jumps to the `HearShootingReaction` arm's own
`ProcessPlaySndInfo(HV_Hears_Shooting)`, which then runs
`ResetThreatInfo("HearShootingReaction")` and returns -- the same thing the
`GuardedPlayReaction` arm did, because `ResetThreatInfo`'s string argument is
read only inside its own `#ifdefDEBUG` log. So a hostage who has not seen you
says exactly what he says today.

`R6Rainbow(x)` rather than `x.m_ePawnType == PAWN_Rainbow`: `execDynamicCast`
reads the object and yields None for None, so a hostage who has seen nobody
takes the stock path instead of dereferencing None. Both halves of the test are
lifted from shipped bytecode in this class -- the cast from
`GetRainbowWhoEscortThisPawn`, the `!= None` from `Guarded.Timer`.

The second block
----------------

`Guarded.Timer` drains the armed reaction 0.1-0.2 s later and speaks
`ProcessPlaySndInfo(HV_Hears_Shooting)` next to `m_pawn.PlayReaction()`. Left
alone it would put a second hostage line on the same `SLOT_Talk` a tenth of a
second after the first. Its six bytes become a `Jump` to the statement that
already followed it, and -- between the jump and its target, so never executed
-- a dead read of `m_iPlayReaction1`, the counter the statements either side of
it already use. `EX_Jump` is 3 disk and 3 memory, a two-byte reference is 3 and
5: six and eight, exactly what the call was. The animation, the counters and
the one-shot are untouched; only the voice moves, from the drain to the moment
the threat registers.

Where the bytes come from
-------------------------

`ProcessThreat` pays for its insert out of
`if (bShowLog || bThreatShowLog) logX(" NEW THREAT: " $ threatInfo.m_id)`.
**Only the call is deleted; the `if` is kept**, now an empty one whose
`JumpIfNot` lands on the statement that already followed it. That is not
tidiness: this block is the first in the package to reach the export
`bThreatShowLog`, and `run_creation_order` compares the order in which a
package's exports are first touched. Keeping the gate keeps that first touch on
the byte it was on. The other export in the deleted line, `ThreatInfo.m_id`, is
first touched by an earlier block, so dropping this reference to it moves
nothing.

Both blocks keep their disk length and their `ScriptSize`. No name, import or
export is added: `HV_Run` is the byte constant 0, `ProcessPlaySndInfo` is
already called twice in `ProcessThreat`, and `R6Rainbow` and `m_lastSeenPawn`
are already referenced by this class -- the patched blocks' reference multisets
are a subset of the stock ones.

The array hazard
----------------

`m_aPlaySndInfo` is declared with ten elements (`UProperty.ArrayDim` 10,
`ElementSize` 8, at `R6HostageAI+0x630`) and `ProcessPlaySndInfo(i)` indexes it
unchecked. `R6HostageVoices.PlayHostageVoices` on this disc switches on
**twelve** values, not the Xbox source's ten:

    0 m_sndRun   1 m_sndFrozen   2 m_sndFoetal   3 m_sndHears_Shooting
    4 m_sndRnbFollow   5 m_sndRndStayPut   6 m_sndRnbHurt
    7 (no arm)   8 m_sndEntersGas   9 m_sndOnFire
   10 m_sndGrabHostage1        11 m_sndGrabHostage3

so 10 and 11 are real, named, playable voices that nothing currently calls --
and routing either through `ProcessPlaySndInfo` would read and write
`m_aPlaySndInfo[10]` or `[11]`, eight and sixteen bytes past an eighty-byte
array. `HV_Run` is 0, which is safe. The suite asserts that every argument left
in the package is below ten so that nobody wires those two the easy way; they
need `m_VoicesManager.PlayHostageVoices(m_pawn, i)` called directly, the way
`HV_EntersGas` and `HV_OnFire` already are.

(Value 7, `HV_EntersSmoke`, is a separate shipped bug and is left alone:
`R6HostageAI.PlaySoundAffectedByGrenade` calls `PlayHostageVoices(m_pawn, 7)`,
the switch has no arm for 7, and `R6HostageVoices` has no `m_sndEntersSmoke`
property at all. A hostage in CS gas coughs; a hostage in smoke says nothing.)

Not established
---------------

* That it is heard. Reasoned from the disassembly, the PC source and the bank
  walk; never played.
* Whether the line suits a hostage who can see you but is reacting to a noise
  rather than to the sight of you.
* Whether the reaction animation reads oddly now the voice leads it by about a
  tenth of a second instead of landing on it.
"""

from __future__ import annotations

import hashlib

H = bytes.fromhex


class HostageRunError(Exception):
    pass


#: `R6HostageAI.ProcessThreat`, whole, its `ScriptSize` word first.
#: 401 disk bytes, `ScriptSize` 520, neither changed by the edit.
THREAT_STOCK = H(
    "0802000007140019010c0600042d014605040b0f00400d1b750b16075d00ff00400d"
    "014c18161b5901701f6e6577207468726561742067726f75703a2000395700400d16"
    "160f014c1800400d142d005c1e2807f300190160041f00041b5c1100400d010c007d"
    "3a007e3a0052111607f30097366f08005211366f08015a071607e000842d01921807"
    "002d014738161b01701f204e4557205448524541543a200039533670080052111616"
    "0f015a07005211142d005c1e270706022d005c1e0f007e0c190160041d00041b5811"
    "00400d366f08015a071b5d162c641616075a01fe21790f007e0c161b6e022401161b"
    "59011f42616974506c61795265616374696f6e001606060207b101fe21760f007e0c"
    "160793019a01610925160f016109260f01681739441cb61e000000001e0000004016"
    "1b59011f47756172646564506c61795265616374696f6e001606060207e701fe217a"
    "02007e0c161b6e022403161b59011f4865617253686f6f74696e675265616374696f"
    "6e0016060602070602ff007e0c190160040500040143191671007e0c16040b")
THREAT_NEW = H(
    "0802000007140019010c0600042d014605040b0f00400d1b750b16075d00ff00400d"
    "014c18161b5901701f6e6577207468726561742067726f75703a2000395700400d16"
    "160f014c1800400d142d005c1e2807d000190160041f00041b5c1100400d010c007d"
    "3a007e3a0052111607d00097366f08005211366f08015a071607bd00842d01921807"
    "002d014738160f015a07005211142d005c1e2707fb012d005c1e0f007e0c19016004"
    "1d00041b581100400d366f08015a071b5d162c641616073701fe21790f007e0c161b"
    "6e022401161b59011f42616974506c61795265616374696f6e001606fb0107a601fe"
    "21760f007e0c160788019a01610925160f016109260f01681739441cb61e00000000"
    "1e000000401607b501772e01014e022a161b6e022400161b59011f47756172646564"
    "506c61795265616374696f6e001606fb0107dc01fe217a02007e0c161b6e02240316"
    "1b59011f4865617253686f6f74696e675265616374696f6e001606fb0107fb01ff00"
    "7e0c190160040500040143191671007e0c16040b0b0b0b0b0b0b0b0b0b0b0b")

#: `R6HostageAI.Guarded.Timer`, whole, its `ScriptSize` word first.
#: 169 disk bytes, `ScriptSize` 222, neither changed. Six bytes move.
TIMER_STOCK = H(
    "de000000072500990159032c1416071e00811b4109161671217602160f01590325a5"
    "0159031607dc008282828119010c0600042d015605161812008119010c0600042d01"
    "4c0a16161812008119010c0600042d01590416161812008119010c0600042d015c05"
    "161607930077014e022a161b7c031607dc009b016109251607d50099016109016817"
    "161b6e0224031619010c0600001b5d0f160f016109250f0168172506dc00a5016109"
    "16040b")
TIMER_NEW = H(
    "de000000072500990159032c1416071e00811b4109161671217602160f01590325a5"
    "0159031607dc008282828119010c0600042d015605161812008119010c0600042d01"
    "4c0a16161812008119010c0600042d01590416161812008119010c0600042d015c05"
    "161607930077014e022a161b7c031607dc009b016109251607d50099016109016817"
    "1606b50001610919010c0600001b5d0f160f016109250f0168172506dc00a5016109"
    "16040b")

#: (name, stock, new). Both blocks are byte-identical in COMMON.LIN,
#: COMMONOFF.LIN and COMMON_SS.LIN, so one pair serves all three.
BLOCKS = (
    ("R6HostageAI.ProcessThreat", THREAT_STOCK, THREAT_NEW),
    ("R6HostageAI.Guarded.Timer", TIMER_STOCK, TIMER_NEW),
)

#: where they sit in a pristine COMMON.LIN, for the tests only -- the edit
#: itself never uses an offset.
KNOWN_OFFSETS = (0x14C338, 0x14DC30)

#: the voice this adds, and the one the not-Rainbow path borrows
HV_RUN = 0
HV_HEARS_SHOOTING = 3

#: The two objects `ProcessThreat` now reaches that it did not reach before:
#: export 1 `R6Rainbow` and export 142 `R6HostageAI.m_lastSeenPawn`. Neither is
#: new to the package and neither is first touched here -- in COMMON they are
#: first reached at 0x4A042 and 0x4C4B7, both far ahead of this block -- so the
#: order the load creates objects in does not move. `run_creation_order` is
#: what proves that; this is here so a test can name them.
NEW_REFS = (1, 142)

#: `UProperty.ArrayDim` of `R6HostageAI.m_aPlaySndInfo`, read live. Every
#: argument to `ProcessPlaySndInfo` has to stay below it: the function indexes
#: the array without a bounds check and each element is eight bytes.
PLAY_SND_INFO_DIM = 10


def _site(plain: bytes, name, stock, new):
    """(offset, 'stock'|'new') or raise. Refuses anything ambiguous."""
    hits = []
    for form, what in ((stock, "stock"), (new, "new")):
        at = plain.find(form)
        if at >= 0 and plain.find(form, at + 1) >= 0:
            raise HostageRunError("%s appears more than once; refusing to "
                                  "guess which one to change" % name)
        if at >= 0:
            hits.append((at, what))
    if len(hits) != 1:
        raise HostageRunError(
            "%s is not in this file" % name if not hits else
            "%s is present in both its stock and its patched form" % name)
    return hits[0]


def _sites(plain: bytes):
    """[(offset, stock, new, state)] for both blocks, or raise."""
    out = []
    for name, stock, new in BLOCKS:
        at, what = _site(plain, name, stock, new)
        out.append((at, stock, new, what))
    return out


def reads(plain: bytes) -> bool:
    """True if this file already carries both blocks in their patched form."""
    try:
        return all(s[3] == "new" for s in _sites(plain))
    except HostageRunError:
        return False


def apply(plain: bytes, enable: bool = True):
    """Both blocks. Returns (plain, changed). The file length never moves."""
    if not enable or reads(plain):
        return plain, 0
    out = bytearray(plain)
    n = 0
    for at, stock, new, state in _sites(plain):
        if state == "stock":
            out[at:at + len(stock)] = new
            n += 1
    if len(out) != len(plain):
        raise HostageRunError("the hostage-voice edit changed the file length")
    return bytes(out), n


def revert(plain: bytes):
    """Put the shipped bytes back. Returns (plain, changed)."""
    out = bytearray(plain)
    n = 0
    for at, stock, new, state in _sites(plain):
        if state == "new":
            out[at:at + len(new)] = stock
            n += 1
    return bytes(out), n


def digests() -> dict:
    """SHA-1 of each pinned form, so a test can name what it compares."""
    return {name + ":" + what: hashlib.sha1(b).hexdigest()
            for name, s, w in BLOCKS
            for what, b in (("stock", s), ("new", w))}


HELP = (
    "Every hostage voice set on the disc carries a line for the moment "
    "Rainbow walks in while a terrorist is still holding them -- two takes "
    "each, thirty across the game, all of it loaded with the map. Nothing on "
    "the PS2 disc ever plays it. The PC version fires it from a hostage state "
    "the console build deleted.\n\n"
    "This gives it back the one moment that still exists: a guarded hostage "
    "who can see one of your operatives, reacting to a shot or a body. He "
    "says that line instead of the generic \"I hear shooting\", once per "
    "reaction, and his flinch animation is unchanged. A hostage who has not "
    "seen you says exactly what he says today.")

CAUTION = (
    "Not yet played. It rewrites two script functions in the hostage AI, "
    "keeping their sizes, their ScriptSize and the order the level load "
    "creates objects in. The line is the one the actors recorded for this "
    "situation, but nobody has heard it in game, and it now leads the "
    "reaction animation by about a tenth of a second instead of landing on "
    "it. If a level hangs on load, turn this off first.")


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "hostage_rainbow_voice",
        "Hostages react out loud when you arrive",
        BOOL, False, group, confidence="experimental", touches="data",
        help=HELP, caution=CAUTION)

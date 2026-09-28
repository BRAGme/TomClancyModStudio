"""Split-screen call-outs: who speaks when a player goes down or scores a kill.

What split screen ships
-----------------------

Both handlers are `R6PlayerController` functions, and both were written for
single player, where the only player is the lead and every teammate is AI.

`PlaySoundDamage` announces the player's death through `m_Team[1]` with
action 23, "lead is down", behind `if (!Level.Game.m_bIsSplitScreen)`. So in
split screen nobody says anything, and if the gate were simply removed,
player 2's death would also be announced as the lead's.

`PlaySoundInflictedDamage` is the kill handler: on the game's own 10% roll,
and not for a kneeling (surrendered) terrorist, the AI teammate in `m_Team[1]`
says "nice shot" (action 100, 101 for a grenade) when it is near the leader.
With `split_squad` giving split screen its AI this already works for either
player's kills. But player 2 can never say it: a player controller has no
voice at all. The only thing in the game that owns a voice is an AI teammate,
through `R6RainbowAI.m_VoicesMgr`.

What this does
--------------

A player goes down: an AI teammate announces it with that operative's own
line, the mapping single player's `R6RainbowAI.PlaySoundDamage` uses: operative
0 (Chavez) -> 23, 1 (Price) -> 25, 2 (Loiselle) -> 24, 3 (Weber) -> 26. The
action is computed as `23 + ((op & 1) << 1) + (op >> 1)`. It speaks only when
an AI teammate is alive (`m_iMemberCount > 1`, which puts a living AI in
`m_Team[1]` in split screen's [lead, AI..., other player] layout). When none
is and Chavez goes down, player 2 says it himself, if he is alive and plays
Price.

Player 1 kills a terrorist: on the same 10% roll, player 2 says Price's own
"nice shot" line if he is alive and plays Price. Otherwise an AI teammate near
the leader says it, as shipped. Player 2 kills one: an AI teammate near the
leader says it. Shooting a hostage: unchanged.

Giving player 2 a voice
-----------------------

`R6RainbowVoices.PlayRainbowVoices` does nothing more than
`aPawn.native2730(<Sound>, 8, priority)`: a native on the pawn, handed the
Sound object from the voices class's defaults. So player 2 speaks by calling
that native on his own pawn with Price's Sound import directly:
`Play_Price_ChavezDown` (-1294) and `Play_Price_Ding_TerroDown1rst` (-1368).
No voices object is created.

That is also why this loads where the earlier attempts hung. `ss_man_down` and
`ss_chatter_kill` built `new R6PriceVoices` inside these two functions. The
package first touches that class in `R6RainbowAI.Possess` (0x13a278), far later
in the load, and a split-screen `.LIN` is a recording of one load: an object
the package creates earlier than the recording did makes every later read land
out of step. This version assumed imports resolve into packages that are
already loaded, so that naming Price's Sound imports was safe. WRONG, and the
reason the card is withdrawn (see `WITHDRAWN`): a Sound is created when it is
first referenced, and stock first references these through R6PriceVoices'
defaults, far later. `run_creation_order` now checks content imports too.

The sound still has to be in a loaded bank. An operative's bank is requested by
its voices object's `Init`, which calls `AddSoundBankName("X_Voices_<name>")`,
and that only appends to `Level.Game.m_BankListToLoad`. With Price as player 2
nothing requests his. So `R6RainbowAI.Possess`, which runs for each AI teammate
while the team is built (the same moment their own banks are requested), now
also calls `AddSoundBankName("X_Voices_Price")` in place of its dead
`if (bShowLog) Log(...)` print. The list skips names already in it. On a map
with no AI teammate nothing requests the bank, and player 2 stays silent.

Player 2 is found as `Level.m_playerList[1].m_pawn`, the list and index
`CreatePlayerTeam`'s split-screen arm itself uses for player 2. His lines are
gated on his operative being Price, so on the canon maps where he is Weber or
Loiselle he does not speak with Price's voice.

What keeps the load in step
---------------------------

Each block keeps its disk length and `ScriptSize`, and adds no name and no
import. Every own-package object the new code references is one the package
has already created before these functions: `m_iOperativeID` (first touched at
0x04bc91), the controller's `m_CurrentCircumstantialAction` and
`m_PlayerCurrentCA` (0x04c5c8, read as harmless padding), `m_pawn`, the team's
`m_TeamManager`, `m_iMemberCount` and `m_Team`. The objects these functions do
create keep their order: `m_sndWoundedSevereStop` and `m_sndWoundedRunningStop`
where they were, then `instigatedBy`, which the rewritten wounded case still
touches first; in the kill handler `DeadPawn`, then `Damage`. The suite checks
the package-wide creation order (`run_creation_order`).

`PlaySoundDamage`'s wounded case (health 1-3) is dead in split screen behind
the same gate, so it carries player 2's "lead is down" line and starts with a
jump out, which is all split screen ever did there.

Not established
---------------

* That a bank requested from `Possess` loads. The AI teammates request their
  own banks from the same function at the same moment, so it should.
* That `native2730` plays on a player's pawn. Player 2's pawn is the same
  `R6Rainbow` class the AI teammates speak through.
* What each line says. The Sound objects are the ones single player's voices
  classes name for these actions.
"""

from __future__ import annotations

import hashlib


class CalloutsError(Exception):
    pass


class _Block:
    """One script block this edits, by content."""

    def __init__(self, name, anchor, stock_sha1, new_sha1, new, known):
        self.name = name
        self.anchor = anchor
        self.stock_sha1 = stock_sha1
        self.new_sha1 = new_sha1
        self.new = new
        self.known = known

    def find(self, plain: bytes) -> int:
        """By the shipped opening, or by this edit's own (the kill handler's
        first statement is one of the ones rewritten)."""
        hits = set()
        for anchor in (self.anchor, self.new[:len(self.anchor)]):
            at = plain.find(anchor)
            if at >= 0 and plain.find(anchor, at + 1) >= 0:
                raise CalloutsError("%s appears more than once; refusing to "
                                    "guess" % self.name)
            if at >= 0:
                hits.add(at)
        if len(hits) != 1:
            raise CalloutsError("%s is not in this file" % self.name
                                if not hits else
                                "%s matches in two places" % self.name)
        return hits.pop()

    def state(self, plain: bytes) -> str:
        at = self.find(plain)
        got = hashlib.sha1(plain[at:at + len(self.new)]).hexdigest()
        if got == self.new_sha1:
            return "new"
        if got == self.stock_sha1:
            return "stock"
        return "other"


#: R6PlayerController.PlaySoundDamage, R6PlayerController.PlaySoundInflictedDamage
#: and R6RainbowAI.Possess, whole, ScriptSize word first -- built and checked by
#: the layout described above, pinned here byte for byte.
DAMAGE = _Block(
    'damage',
    anchor=bytes.fromhex("770100000775019a393a1901"),
    stock_sha1="03e4d7dc5d38c9ff200883d748b73216747214cc",
    new_sha1="87530f7d8a6adffd66c4164eac052ebdb75bf7a3",
    new=bytes.fromhex(
        "770100000775019a393a19018f05000101a2393a240016050119010b05000101fa010a2e"
        "0024040adc00240507f300971901200500040116261619191a26190120050010010a0500"
        "0401943300001b03393d922c1792949c19010b050004014b04261626169519010b050004"
        "014b042616161616017d01017e0119010b130000610819010b050004015e262403161901"
        "0b130000610819010b050004015d262403160675010ae10024010ae60024020a72012403"
        "06750100482e0f00482e19102619018f05000001c402050004010b07a100827700482e01"
        "0b16182600821900482e0600041b04161812009a1900482e050004014b04261616161900"
        "482e0c00006aaa20ce14240824021606a100010b0b0b0b0b0b0b0b0675010affff040b"),
    known=0x10B465)


INFLICTED = _Block(
    'inflicted',
    anchor=bytes.fromhex("4b0100000749019a393a1901"),
    stock_sha1="8ce3098adf2b8d8f682f173b73dec2207cd4a7e5",
    new_sha1="47982e6f3747621faf5d361a8adb3a25e5567b2f",
    new=bytes.fromhex(
        "4b0100000501192e02005c2a05000101bd0a070124020749018281192e02005c2a060004"
        "2d01e9011618090096a72c64162c0a16160f005c2a19102619018f05000001c402050004"
        "010b07b0008277005c2a010b161826008219005c2a0600041b04161812009a19005c2a05"
        "0004014b042616161619005c2a0c00006aaa20d815240824001606490107490119012006"
        "00041b55041619191a26190120050010010a05000401941900001b03393d922c6439419a"
        "393a005b2a2c02161616064901005b2a005b2a0b0b0a460124030749011901200600041b"
        "55041619191a26190120050010010a05000401940800001b03241b160649010affff040b"),
    known=0x10B5B5)


POSSESS = _Block(
    'possess',
    anchor=bytes.fromhex("f90000001c6d0b00511d160f"),
    stock_sha1="047fc90f32cad90fb27193df39539352284e55d8",
    new_sha1="11a3dcb7800e28beca1150dd30ede17bff8401fb",
    new=bytes.fromhex(
        "f90000001c6d0b00511d160f01082e0100511d141901080600042d01d302270f01b12a0f"
        "1900511d05000401d6012a1b171f585f566f696365735f5072696365001601080b0b0b0b"
        "0b0b0b0b0b0b0b0b07f700829a393a19018f05000101a2393a2400161809007201740c2a"
        "16160504190108050004014b040ab600260f01740c110b0b0b205a2e06e7000acd002c02"
        "0f01740c110b0b0b20562e06e7000ae4002c030f01740c110b0b0b20782e06e7000affff"
        "1901740c0700001b1c1716040b"),
    known=0x13A278)


BLOCKS = (DAMAGE, INFLICTED, POSSESS)


def reads(plain: bytes) -> bool:
    """True if this file already has all three."""
    try:
        return all(b.state(plain) == "new" for b in BLOCKS)
    except CalloutsError:
        return False


def apply(plain: bytes, enable: bool = True):
    """All three blocks. Returns (plain, changed). The length never moves."""
    if not enable or reads(plain):
        return plain, 0
    out = bytearray(plain)
    changed = 0
    for b in BLOCKS:
        state = b.state(plain)
        if state == "other":
            raise CalloutsError("%s is not the code this disc shipped, and "
                                "not this edit either" % b.name)
        if state == "stock":
            at = b.find(plain)
            out[at:at + len(b.new)] = b.new
            changed += 1
    if len(out) != len(plain):
        raise CalloutsError("the call-outs edit changed the file length")
    return bytes(out), changed


HELP = (
    "In single player a teammate says 'lead is down' when you fall, and "
    "compliments your kills. Split screen shipped with no teammates to say "
    "anything, and with no voice at all for player 2. With AI teammates this "
    "restores the call-outs for both players: an AI teammate announces "
    "whichever player goes down, by name, with the line single player uses "
    "for that operative. If no AI teammate is left, player 2 announces player "
    "1. Player 1's kills get a 'nice shot' from player 2 (Price), or from an "
    "AI teammate when he cannot; player 2's kills get one from an AI "
    "teammate. The chance is the game's own 10%.")

CAUTION = (
    "Not yet played. It rewrites three split-screen script functions. It "
    "keeps their sizes and the order the level load creates objects in, which "
    "is what hung the two earlier attempts at this (the death call-out and "
    "the kill call-out, still withdrawn). Player 2 speaks only as Price, and "
    "only on maps with an AI teammate, because the AI teammates are what "
    "request his sound bank. If a level hangs on load, turn this off first.")


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_callouts",
        "Split screen: teammates call out downs and kills",
        BOOL, False, group, confidence="broken", touches="data",
        requires={prefix + "split_squad": [True]},
        help=HELP, caution=CAUTION, enabled=False,
        disabled_reason=WITHDRAWN)


#: Why the card is off.
WITHDRAWN = (
    "Withdrawn 2026-09-24, the same day: with it on, Terrorist Hunt on the "
    "Garage hung its split-screen load with 'Bad name index -70/109' -- and "
    "the only packages in COMMON_SS with 109 names are the three voice "
    "packages, X_Voices_Price, _Loiselle and _Weber. So the load read a voice "
    "package out of step. Two parts of this edit reach Price's voice data "
    "where stock never does: player 2's lines name Price's Sound objects "
    "directly (an import is only safe when the object it names already "
    "exists, and these are created lazily, when R6PriceVoices' defaults "
    "load), and Possess requests Price's bank. The first alone breaks the "
    "recording rule: it is the only edit, withdrawn or live, that names a "
    "sound or texture in "
    "script ahead of the stock load (run_creation_order now checks this). "
    "The bank request is unproven either way. Both have to change before "
    "this comes back.")

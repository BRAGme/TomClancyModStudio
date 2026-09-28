"""Split screen: when a player goes down, a teammate calls it out and the
man-down music plays.

What split screen does now
--------------------------

`R6RainbowTeam.TeamMemberDead` handles every death on the team. For an AI
teammate it runs single player's bookkeeping, which also plays the team's
`m_sndDeathMusic` through the leader's controller (on the team's first loss,
as shipped). For a player, `rsesquad` sends it down a split-screen branch that
hands the lead to the other player and returns -- so a player's death is
silent: no call-out, no music. The call-out single player makes for the
player (`R6PlayerController.PlaySoundDamage`, "lead is down") sits behind a
`!m_bIsSplitScreen` gate.

What this does
--------------

After the hand-off, for a player's death:

    if (DeadPawn.IsAlive())
        return;
    if (m_iMemberCount > 1)
        m_Team[1].Controller.PlaySoundCurrentAction(
            byte(23 + (((DeadPawn.m_iOperativeID * 5) / 2) & 3)));
    if (m_Team[0].IsAlive())
        R6PlayerController(m_Team[0].Controller).ClientPlayMusic(m_sndDeathMusic);

The first test is not decoration. `rsesquad` hands the lead over by calling
`TeamMemberDead` with a LIVING player's pawn: `regrouponme` does it, and so do
hold/follow and the command wheel through it. Without the test every regroup
played "lead is down" and the music (caught by an adversarial review,
2026-09-24). A dead player's own regroup cannot get here: the spectator state
(`CameraPlayer`) sets `bOnlySpectator` and clears `m_pawn`, and `regrouponme`
returns on the first. That leaves only the seconds of death camera before it.

The first living AI teammate says the downed operative's own line -- the
mapping single player's `R6RainbowAI.PlaySoundDamage` uses: operative 0
(Chavez) -> 23 "lead is down", 1 (Price) -> 25, 2 (Loiselle) -> 24, 3 (Weber)
-> 26. `((op * 5) / 2) & 3` swaps the two low bits in one read of the
operative. Division (native 145) rather than a shift: stock script uses `/`,
and never `>>`, so 149's number is only inferred.

`m_iMemberCount > 1` is the test for a living AI: dead AI are moved out of the
count, and the team is [leader, AI..., other player]. With no AI alive nobody
speaks. The speaker is an AI teammate, the only thing in the game
that owns a voice, so no voice object is created and no sound is named -- the
two things that hung the earlier attempts (`ss_man_down` created
`R6PriceVoices` early; `split_callouts` named Price's Sound imports early).

The music is the one an AI teammate's death plays, through the leader's
controller -- after the hand-off, the living player. An AI's death plays it
only on the team's first loss; a player's death plays it every time. It is
skipped when the other player is down too: then the mission is failing, and
single player plays no death music when the player falls.

Trieste is the exception: split screen splits it into three teams -- the
rescued operatives, player 2 alone, player 1 alone -- so a player's team has
no AI and slot 0 is the player himself. There a player's death stays silent.

A player who starts part B dead (`rsecarry`) is marked dead by the carry-over
restore, which raises the same death handling: the call-out and the music
play once at the start of part B, as single player's death music does for a
teammate lost in part A.

Where the bytes come from
-------------------------

Three regions of the function, each rewritten at exactly its stock disk and
memory length:

* mem 0x01d3 (inside `rsesquad`'s hand-off region): the player branch's
  `return` becomes `goto 0x0381`.
* mem 0x02c1-0x030e: single player's "the leader is a dead player" test and
  its body. In split screen slot 0 always holds a player and only an AI's
  death reaches this line, so `m_Team[0] == DeadPawn` is never true. It now
  starts with `goto 0x030e`, where that test went when false; the music call
  follows, entered from the call-out.
* mem 0x037e-0x0406: an `if (bShowLog)` loop of debug prints. `bShowLog` reads
  False on the team in every savestate. It now starts with `goto 0x0406`,
  where that loop ended; the call-out follows.

The load order is kept: every object the new code touches is first touched
earlier in stock, except `m_sndDeathMusic`, whose first touch moves from 0x0319
to the music call at 0x02c9 -- and a dead read of `iIdxDeadPawn` before it
keeps the one object stock first touches in between (0x0300) ahead of it. The
suite checks the package-wide creation order and the content-import order
(`run_creation_order`).

Needs `split_squad`: the entry is in its hand-off region.

Not established
---------------

* That `PlaySoundCurrentAction` from `TeamMemberDead` plays while the team
  is mid-update. Single player calls it on the same AI from the player's
  death handler.
* What the music sounds like over a player's death camera.
"""

from __future__ import annotations

H = bytes.fromhex


class DownCallError(Exception):
    pass


def _dead_log_new():
    from . import rsesquad
    return rsesquad.DEAD_LOG_NEW


#: (name, key -- whole, in its stock form, found exactly once --, offset of the
#: changed bytes within the key, stock bytes, new bytes)
def _edits():
    return (
        ("the player branch's return goes on to the call-out",
         _dead_log_new(), 31, H("040b0b"), H("068103")),
        ("single player's dead-leader test: the music call",
         H("070e038282191a25010a0600042d01b718140081191a25010a0600041b0416"
           "1616180f00721a25010a004a0a16160f005b160116065203"), 0,
         H("070e038282191a25010a0600042d01b718140081191a25010a0600041b0416"
           "1616180f00721a25010a004a0a16160f005b160116065203"),
         H("060e03" "005b16"                        # goto 0x030e; iIdxDeadPawn
           "192e05191a25010a05000401940b00001b6211014e3616"   # the music
           "040b"                                   # return
           "010a" "017006" "017006" + "0b" * 16)),  # dead filler
        ("the team's debug-print loop: the call-out",
         H("0706042d01920f00430425070604960043049201160170061616e7707070707"
           "01f207465616d206c6973743a20693d003953004304161f203a2000163956"
           "1a004304010a161f20616e64206d5f6949443d00163952191a004304010a05"
           "0001012c1616a500430416068e03"), 0,
         H("0706042d01920f00430425070604960043049201160170061616e7707070707"
           "01f207465616d206c6973743a20693d003953004304161f203a2000163956"
           "1a004304010a161f20616e64206d5f6949443d00163952191a004304010a05"
           "0001012c1616a500430416068e03"),
         H("060604"                                 # goto 0x0406
           "079503" "19004a0a0600041b0416"          # if (DeadPawn.IsAlive())
           "040b"                                   #   return;  (a regroup, see above)
           "07da03" "970116" "2616"                 # if (m_iMemberCount > 1)
           "19191a26010a0500040194" "2600" "00"     #   m_Team[1].Controller.
           "1b03" "393d922c179c9190"                #   PlaySoundCurrentAction(byte(23 +
           "19004a0a050004014b04" "2c0516" "2c0216" #     (((op * 5) / 2)
           "2c03161616"                             #     & 3)))
           "07f103" "191a25010a0600041b0416"        # if (m_Team[0].IsAlive())
           "06c902"                                 #   goto the music
           "040b"                                   # return
           "017006" + "0b" * 14)),                  # dead filler
    )


KNOWN_OFFSETS = (0x140B24 + 31, 0x140C05, 0x140C85)


def _sites(plain: bytes):
    """[(offset of the changed bytes, stock, new, state)] or raise."""
    out = []
    for name, key, rel, stock, new in _edits():
        done = key[:rel] + new + key[rel + len(stock):]
        hits = []
        for form, state in ((key, "stock"), (done, "new")):
            at = plain.find(form)
            if at >= 0 and plain.find(form, at + 1) >= 0:
                raise DownCallError("%s: found more than once" % name)
            if at >= 0:
                hits.append((at + rel, state))
        if len(hits) != 1:
            raise DownCallError("%s: %s" % (name, "not found" if not hits
                                            else "both forms present"))
        out.append((hits[0][0], stock, new, hits[0][1]))
    return out


def reads(plain: bytes) -> bool:
    try:
        return all(s[3] == "new" for s in _sites(plain))
    except DownCallError:
        return False


def apply(plain: bytes, enable: bool = True):
    """Returns (plain, changed). The length never moves. Needs split_squad's
    hand-off already in the file; refuses anything it does not recognise."""
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
        prefix + "split_down_callouts", "Teammates call out a downed player",
        BOOL, False, group, confidence="experimental", touches="data",
        requires={prefix + "split_squad": [True]},
        help="When either player goes down, the first AI teammate still "
             "standing calls it out with that operative's own line -- \"lead "
             "is down\" for Ding, the man-down lines for Eddie, Loiselle or "
             "Weber -- and the man-down music an AI teammate's death plays "
             "starts. The music is skipped when both players are down. With "
             "no AI teammate alive nobody speaks, and on Trieste, where each "
             "player is a team of one, a player's death stays silent.",
        caution="Not yet played. It rewrites part of the team's death "
                "handling in code only split screen runs, keeping its size "
                "and load order. If a level hangs on load, turn this off "
                "first.")

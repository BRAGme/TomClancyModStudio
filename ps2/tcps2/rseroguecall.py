"""A traitor's death is called in as "Tango down", not as a lost operative.

The defect
----------

With `ff_retaliate` on, a player who shoots his own squad is moved onto another
team -- 1 (the terrorists) or 4 (nobody's) -- and the squad hunts him. When
they kill him the squad still announces him by name: "Eddie is down", or "lead
down" if he is Ding.

That is not a team test going wrong. **Nothing in either call-out reads the
team at all.** Measured on the disc:

* `R6RainbowTeam.TeamMemberDead`, the split-screen player-casualty line that
  `split_down_callouts` adds, picks its line from `DeadPawn.m_iOperativeID`
  alone -- `23 + (((op * 5) / 2) & 3)`, i.e. RV_LeadDown / RV_LoselleDown /
  RV_PriceDown / RV_WeberDown. An operative is an operative whatever team he
  is on.
* `R6RainbowAI.PlaySoundInflictedDamage`, the kill confirmation ("Tango
  down", `RV_TerroristDown`, action 0), is gated on
  `R6Pawn(DeadPawn).m_ePawnType == PAWN_Terrorist` -- the same `+0x378` field
  the mission-failure accounting keys on, and a traitor is still
  `PAWN_Rainbow`.
* and that second gate never even gets the chance: the only two script sites
  that dispatch `PlaySoundInflictedDamage` at all are
  `R6TerroristAI.PlaySoundDamage` and `R6HostageAI.PlaySoundDamage`, so a
  Rainbow victim -- AI or human -- produces no kill confirmation from anyone.

So the casualty call-out selects on the operative and the kill confirmation
selects on the pawn type, and the cheapest place to make either read the team
is the one this feature already owns.

What this does
--------------

It multiplies the call-out's action index by a 0/1 team factor::

    m_Team[1].Controller.PlaySoundCurrentAction(byte(
        (23 + (((DeadPawn.m_iOperativeID * 5) / 2) & 3))
        * ((DeadPawn.m_iTeam & 2) / 2)))

    m_iTeam 2 (Alpha)  -> 1        m_iTeam 1 (terrorists) -> 0
    m_iTeam 3 (Bravo)  -> 1        m_iTeam 4 (nobody's)   -> 0
                                   m_iTeam 0 (hostage)    -> 0

Bit 1 of `m_iTeam` is exactly what separates a Rainbow element from either of
the two teams `ff_rogue_side` can put a traitor on, so one expression covers
both settings and no per-side variant is needed. Action 0 is
`RV_TerroristDown`: the line every operative says over a dead terrorist. It is
spoken by the same living AI teammate that would have said "Eddie is down", out
of his own already-loaded voice bank, so nothing new is named and no voice
object is created.

A loyal teammate's death is untouched, because his `m_iTeam` is 2.

Where the bytes come from
-------------------------

Both regions are `rsedowncall`'s own, rewritten: this reads the file *after*
`split_down_callouts` has been applied and replaces two of its three runs.
That is also the honest dependency -- with `split_down_callouts` off, a
player's death in split screen is silent and there is no wrong line to fix.

The team factor costs 20 disk / 24 memory bytes and `rsedowncall`'s call-out
region (m=[0x037e,0x0406), 107 disk / 136 memory) has only 17 / 19 of dead
filler. So `if (DeadPawn.IsAlive()) return;` is moved out of it into the spare
room in `rsedowncall`'s other region (m=[0x02c1,0x030e), 55 / 77, with 24 / 31
spare) and reached by the jump that used to sit where it was.

Which statement to move is decided by arithmetic, not taste. A region's
memory-over-disk surplus is fixed by its content, the leftover filler has to
have surplus `3b + 2c`, and **surplus 1 is unreachable**. The alive guard's
surplus is 5 (`DeadPawn` is a two-byte local reference, `IsAlive` a one-byte
FName reference), which leaves region A's live content at 20 of its 22 and the
filler at 2. Moving the death-music branch instead -- surplus 6, two one-byte
references -- would leave the filler at surplus 1 and could not be padded at
all.

Both regions keep their exact disk and memory length, the block still parses at
its shipped 843 / 1062, every jump lands on a statement boundary, and the
package-wide first-touch order is byte-identical to `split_down_callouts`'
own. The only reference the block did not already carry is the import
`Engine.Pawn.m_iTeam`, which `rseff` writes through in this same package.

What it does not do
-------------------

The man-down music still plays over a traitor's death. Gating that as well
needs a second team test and there are only 9 spare disk bytes left in the
region; it was not worth a third region.

The KILLER still says nothing. Making the shooter say "Tango down" needs a
dispatch added to `R6PlayerController.PlaySoundDamage`, whose two spare spans
are already spent by `rseff`'s `ff_player_victim`. The line still gets said --
by the teammate who would otherwise have read the eulogy.

Not established
---------------

* That a traitor's death reaches `TeamMemberDead` down the same split-screen
  branch a loyal player's does. It is the same code path either way -- the
  hand-off does not look at teams -- but it has not been watched in play.
* What the line sounds like over a death camera.
"""

from __future__ import annotations

H = bytes.fromhex


class RogueCallError(Exception):
    pass


#: `R6RainbowTeam.TeamMemberDead`, block 0x1409b8. `stock` is the run
#: `split_down_callouts` leaves in the file, not the disc's own -- see above.
#: Each stock run occurs exactly once, and each replacement not at all, in
#: `/COMMON.LIN`, `/COMMONOFF.LIN` and `/COMMON_SS.LIN` alike.
REGIONS = (
    # m=[0x02c1,0x030e): the death music, plus the relocated alive guard.
    #   0x02c1  goto 0x030e
    #   0x02c4  iIdxDeadPawn                   -- dead read, keeps the load order
    #   0x02c9  R6PlayerController(m_Team[0].Controller)
    #             .ClientPlayMusic(m_sndDeathMusic)
    #   0x02ed  return
    #   0x02ef  if (DeadPawn.IsAlive()) return;        [moved from 0x0381]
    #   0x0303  goto 0x0384                            -- on to the call-out
    #   0x0306  filler
    ("rogue tango 1",
     H("060e03005b16192e05191a25010a05000401940b00001b6211014e3616040b01"
       "0a0170060170060b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"),
     H("060e03005b16192e05191a25010a05000401940b00001b6211014e3616040b07"
       "030319004a0a0600041b0416040b0684030170060b0b0b")),
    # m=[0x037e,0x0406): the call-out, now with the team factor.
    #   0x037e  goto 0x0406                     -- an AI death skips all of this
    #   0x0381  goto 0x02ef                     -- the relocated alive guard
    #   0x0384  if (m_iMemberCount > 1)
    #   0x038f    m_Team[1].Controller.PlaySoundCurrentAction(byte(
    #               (23 + ((op*5)/2 & 3)) * ((DeadPawn.m_iTeam & 2) / 2)))
    #   0x03e1  if (m_Team[0].IsAlive())
    #   0x03f5    goto 0x02c9                   -- the death music
    #   0x03f8  return
    #   0x03fa  filler
    ("rogue tango 2",
     H("06060407950319004a0a0600041b0416040b07da03970116261619191a26010a"
       "05000401942600001b03393d922c179c919019004a0a050004014b042c05162c"
       "02162c0316161607f103191a25010a0600041b041606c902040b0170060b0b0b"
       "0b0b0b0b0b0b0b0b0b0b0b"),
     H("06060406ef0207e103970116261619191a26010a05000401943e00001b03393d"
       "90922c179c919019004a0a050004014b042c05162c02162c031616919c19004a"
       "0a05000401c3022c02162c0216161607f803191a25010a0600041b041606c902"
       "040b018f0b0b0b0b0b0b0b")),
)


def _sites(plain: bytes):
    """[(offset, stock, new, state)] or raise."""
    out = []
    for name, stock, new in REGIONS:
        hits = []
        for form, state in ((stock, "stock"), (new, "new")):
            at = plain.find(form)
            if at >= 0 and plain.find(form, at + 1) >= 0:
                raise RogueCallError("%s: found more than once" % name)
            if at >= 0:
                hits.append((at, state))
        if len(hits) != 1:
            raise RogueCallError(
                "%s: %s" % (name, "not found -- this needs the downed-player "
                            "call-outs turned on first" if not hits
                            else "both forms present"))
        out.append((hits[0][0], stock, new, hits[0][1]))
    return out


def reads(plain: bytes) -> bool:
    try:
        return all(s[3] == "new" for s in _sites(plain))
    except RogueCallError:
        return False


def apply(plain: bytes, enable: bool = True):
    """Returns (plain, changed). The length never moves.

    Needs `rsedowncall` already in the file; refuses anything it does not
    recognise.
    """
    if not enable or reads(plain):
        return plain, 0
    out = bytearray(plain)
    n = 0
    for at, stock, new, state in _sites(plain):
        if state == "stock":
            out[at:at + len(stock)] = new
            n += 1
    if len(out) != len(plain):
        raise RogueCallError("the traitor call-out edit changed the file length")
    return bytes(out), n


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "rogue_tango", "A traitor's death is called \"Tango down\"",
        BOOL, False, group, confidence="experimental", touches="data",
        requires={prefix + "split_down_callouts": [True],
                  prefix + "split_squad": [True],
                  prefix + "ff_retaliate": [True]},
        help="When the squad turns on a player who has shot his own, they "
             "still bury him as one of their own: \"Eddie is down\". Nothing "
             "in that line reads which team he is on -- it is chosen purely "
             "by which operative he was playing. This reads the team, so a "
             "man the squad has been hunting is called in the way they call "
             "in any other kill: \"Tango down\". A loyal teammate's death is "
             "announced exactly as before.",
        caution="Not yet played. It rewrites the call-out the downed-player "
                "option adds, keeping its size and the order the level load "
                "creates objects in. The man-down music still plays over a "
                "traitor, and the man who actually shot him still says "
                "nothing -- the line comes from the teammate who would "
                "otherwise have named him. If a level hangs on load, turn "
                "this off first.")

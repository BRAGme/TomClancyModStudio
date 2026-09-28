"""A dead player stops stealing the other player's screen.

THE BUG, AS IT LOOKS IN PLAY
---------------------------

Split screen, co-op. Player 1 dies during part A of a mission. Part B loads,
and player 1's half of the screen shows a copy of player 2's view with no
HUD -- and player 1's zoom, vision switch and reload land on player 2's gun.

THE BUG, AS IT IS
-----------------

`R6GameInfo.DeployCharacters` runs on every level change. Its only caller is
`R6ConsoleXbox.NotifyAfterLevelChange`, which the PS2 build uses too
(`PSX2GAME.INI` sets `PlayerConsole=R6Game.R6ConsoleXbox`), and which passes
a literal `true`:

    function DeployCharacters(PlayerController ControlledByPlayer, BOOL bIsPlaying)
    {
        CurrentPlayer = ControlledByPlayer.Player;      // player 1's viewport
        CreateRainbowTeam(true, 0, ControlledByPlayer);
        if (bIsPlaying)
        {
            ControlledByPlayer = PlayerController(
                R6RainbowTeam(GetRainbowTeam(0)).m_TeamLeader.Controller);
            SetController(ControlledByPlayer, CurrentPlayer);      // <- here
        }
        else { ... spectator tail, never reached on this path ... }
    }

It captures the local player's viewport, rebuilds the squad, then reassigns
`ControlledByPlayer` to whoever leads the team NOW -- and hands that
controller the captured viewport. `SetController` is native 2010, and it does
not unbind the previous owner.

So with player 1 dead, the team leader resolves to player 2's pawn and
viewport 0 is bound to player 2's controller while he still holds viewport 1.
Both viewports point at him; player 1's controller is orphaned but still
believes it owns viewport 0. Measured in a savestate: exactly that, and it is
the only collapsed binding in 81 states.

That also explains the two things that looked unrelated. Input is delivered to
the bound controller WHOLE, so axis input sums -- player 1's idle stick
contributes nothing and player 2 still moves -- while a button press fires a
discrete exec on player 2's weapon. And the branch that runs returns before
`bOnlySpectator` and `GotoState('CameraPlayer')`, so the game never actually
puts player 1 into its spectator state, which is why there is no HUD.

It latches. Native 2228, `Actor.GetLocalPlayerController()`, disassembles to
`GEngine->Client->Viewports[0]->Actor` -- literal index 0. Once viewport 0 is
stolen, every later level re-enters this same chain as player 2, so that
level's team is built around him as well.

THE FIX
-------

Two bytes, and no jump moves, nothing is deleted and no padding is needed.

`DeployCharacters` declares six locals, two of which are never read:

    ControlledByPlayer 89   CurrentPlayer 383   bIsPlaying 865
    iSoundNb 1004           pTerrorist 1016     pZone 1052

The assignment's DESTINATION is redirected from `ControlledByPlayer` (ref 89,
compact `59 01`) to the unused `pZone` (ref 1052, compact `5c 10`). Both are
two-byte compact indexes, so disk and memory length are identical by
construction. The cast still runs and its result is thrown away;
`SetController` is left holding the controller that came in, which is the one
that owns the viewport.

The guarded form -- test the reassigned value before calling -- was built and
rejected. It needs about sixteen more disk bytes than the region holds, so it
has to spend the dead `else` branch, and spending it means deleting that
branch's object references. That is the reference-order hazard that desynced
Oil Refinery. This form deletes no reference at all.

WHAT CHANGES, HONESTLY
----------------------

Stock hands viewport 0 to whoever leads the Rainbow team after the rebuild.
With this, viewport 0 stays with the controller that already owns it. Single
player is unaffected and so is split screen while player 1 is alive, because
in both the leader IS the local player. Split screen with player 1 dead is
the case this fixes.

One justification that was offered for the guarded form and turns out to be
FALSE, recorded so nobody rebuilds it on that basis: native 2010 already
refuses to write when either argument is null (it guards the controller at
`0x003D9AB0` and the player at `0x003D9ABC`), so an AI team leader -- where
the cast yields None -- already no-ops in stock. There was no black screen to
fix there.

Not yet played. Everything above is static analysis plus one savestate.
"""

from __future__ import annotations

H = bytes.fromhex


class ViewportError(Exception):
    pass


#: Offline single player and split screen. `DeployCharacters` asserts
#: `NM_Standalone`, so the online package could not reach it anyway.
SELECT = r"/COMMON(OFF|_SS)\.LIN$"

#: The two bytes are the compact index at offset 2. Everything either side is
#: carried so the run is unique: `SetController` is called from BOTH arms of
#: the branch, so the call alone matches twice and the anchor has to include
#: the reassignment that precedes it.
REGIONS = [
    ("DeployCharacters viewport theft",
     H("0f00" "5901"
       "2e8b19192e991b4c01251605000401e40205000401ce01"
       "67da005901007f0516"),
     H("0f00" "5c10"
       "2e8b19192e991b4c01251605000401e40205000401ce01"
       "67da005901007f0516")),
]


def _sites(plain: bytes):
    """[(offset, stock, new, state)] or raise."""
    out = []
    for name, stock, new in REGIONS:
        hits = []
        for form, state in ((stock, "stock"), (new, "new")):
            at = plain.find(form)
            if at >= 0 and plain.find(form, at + 1) >= 0:
                raise ViewportError("%s: found more than once" % name)
            if at >= 0:
                hits.append((at, state))
        if len(hits) != 1:
            raise ViewportError(
                "%s: %s" % (name, "not found" if not hits
                            else "both forms present"))
        out.append((hits[0][0], stock, new, hits[0][1]))
    return out


def reads(plain: bytes) -> bool:
    try:
        return all(s[3] == "new" for s in _sites(plain))
    except ViewportError:
        return False


def apply(plain: bytes, enable: bool = True):
    """Returns (bytes, regions changed). The length never moves."""
    want_new = bool(enable)
    if reads(plain) == want_new:
        return plain, 0
    out = bytearray(plain)
    n = 0
    for at, stock, new, _state in _sites(plain):
        want = new if want_new else stock
        if out[at:at + len(stock)] != want:
            out[at:at + len(stock)] = want
            n += 1
    if len(out) != len(plain):
        raise ViewportError("a viewport edit changed the file length")
    return bytes(out), n


def cards(prefix, group):
    from .model import BOOL, Setting

    return [
        Setting(
            prefix + "keep_viewport", "A dead player keeps his own screen",
            BOOL, False, group,
            confidence="experimental", touches="data",
            help="Die in split screen and, at the next level change, your "
                 "half of the screen becomes a copy of the other player's "
                 "view with no HUD -- and your zoom, vision switch and "
                 "reload start landing on his weapon.\n\n"
                 "The game hands your screen to whoever is leading the team "
                 "after it rebuilds the squad, and with you dead that is the "
                 "other player. It never unbinds you first, so you both end "
                 "up pointing at him. This makes your screen stay with you.",
            caution="Not yet played -- it comes from reading the game and "
                    "one saved state, not from a session.\n\n"
                    "It does not give you a spectator camera. It stops the "
                    "other player being sabotaged; what a dead player sees "
                    "afterwards is a separate question.\n\n"
                    "Offline and split screen only, and it changes nothing "
                    "at all while you are alive, because then the team "
                    "leader is already you."),
    ]

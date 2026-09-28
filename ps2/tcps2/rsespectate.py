r"""A dead player watches a living teammate, from his eyes.

WHAT THE GAME ALREADY SHIPS
---------------------------

The PS2 build has a split-screen spectator camera the Xbox build does not.
`R6PlayerController.Dead.EnterSpectatorMode` carries a PS2-only arm -- read out
of the shipped bytecode at `COMMON_SS.LIN.plain` 0x111678, not from any source
tree, because neither the Xbox `.uc` dump nor the Raven Shield 1.56 PC source
contains `m_bIsSplitScreen`, `BeginSpectator` or `sharpShooterRespawn` at all::

    if ( (Level.NetMode != NM_Standalone && !GameReplicationInfo.m_bGameOverRep)
         || (Level.Game != none && Level.Game.m_bIsSplitScreen) )
    {
        if (sharpShooterRespawn) { ... }
        else if (Level.Game != none && Level.Game.m_bIsSplitScreen
                 && native1012() - m_pawn.f_DeadTime > 9.5)
        {
            GotoState('CameraPlayer');
            return;
        }
        else BeginSpectator();
        if (myHUD != none && Viewport(Player) != none)
            R6AbstractHUD(myHUD).StopFadeToBlack();
    }

That second arm is the whole feature. It is also a genuine PS2 addition in a
second way: the Xbox build reaches `CameraPlayer` only through `Dead.Fire`,
whose branch demands `IsPlayerPassiveSpectator() || m_TeamManager == none ||
m_TeamManager.m_iMemberCount <= 0` -- "only once you have no living teammates",
the exact opposite of a headcam. **The PS2 `Dead.Fire` has that entry removed
entirely** (measured: its block at 0x11206C ends on `if(!ready) return; return`
and contains no `GotoState`, no camera-mode store and no member-count test), so
the split-screen route carries no teammate gate.

`CameraPlayer` itself is complete. `BeginState` and `Tick` both call
`SpectatorChangeTeams`, which walks `ForEach AllActors(class'R6Rainbow')`
filtered on the native `IsAlive()` -- Weber and Loiselle included -- and `Tick`
then snaps the controller onto the target every frame::

    SetRotation(ViewTarget.Rotation + R6Pawn(ViewTarget).GetRotationOffset());
    SetLocation(ViewTarget.Location);

`SpectatorChangeTeams`'s `bCanViewOthers` gate is OPEN: it reads TRUE on the live
`Level.Game` in all four split-screen EE images. Co-op is not team-adversarial,
so its `other.m_iTeam != m_iTeamId` `continue` never fires either.

WHY IT HAS NEVER WORKED, AND WHAT THE PREVIOUS PROPOSAL MISSED
--------------------------------------------------------------

None of the above can be reached, because the button that triggers it is
disarmed every single frame.

`R6InteractionCircumstantialAction.ActionKeyReleased` is the only caller of
`EnterSpectatorMode`, and it is gated on `m_Player.m_bReadyToEnterSpectatorMode`.
`Dead.BeginState` sets that flag TRUE unconditionally. An earlier proposal in
this project concluded from exactly those two facts that the flag is therefore
true offline, and shipped a "just in case" card that flips a different gate.
**That conclusion is wrong, and the flag is measured FALSE.**

`R6PlayerController.PlayerTick` -- identified by its own local, which the export
table names `R6PlayerController.PlayerTick.fDeltaTime`, and confirmed by the
`SetEyeLocation(m_pawn, fDeltaTime)` block sitting immediately after it -- runs
this every frame, at `COMMON_SS.LIN.plain` 0x115E74::

    if (GameReplicationInfo != none
        && GameReplicationInfo.m_eServerState != GameReplicationInfo.RSS_InGame)
        m_bReadyToEnterSpectatorMode = false;

Offline that guard PASSES, both halves of it: `GameReplicationInfo` is
`R6GameReplicationInfo0`, not none, and `m_eServerState` is 0 while `RSS_InGame`
is 3. So the flag is stamped back to false on every frame, and the action button
can never reach `EnterSpectatorMode`.

Measured, not reasoned: `m_bReadyToEnterSpectatorMode` reads FALSE on a
controller sitting in state `Dead` in two independent split-screen EE images
(`hd_ee.bin` and `mp_play_ee.bin`). The bool reader was validated first -- 30 of
the controller's 213 bools read TRUE in the same pass, so it is not a reader
stuck at false.

The four other writers of the flag were all checked and none of them explains it:
`Dead.EndState` (leaving the state anyway), `WaitForGameRepInfo.BeginState` (a
state whose only entry is gated on `NetMode != NM_Standalone`), and
`Dead.BeginState` disk+0x4BC, which sits inside a branch whose gate is
`Level.NetMode == NM_Client || (Level.NetMode == NM_ListenServer &&
Viewport(Player) != none)` and therefore jumps clean over it offline. `PlayerTick`
is the only site left, and its guard is the only one that is live offline.

THE EDITS
---------

Four one-shot byte flips, no jump moves, nothing deleted, no padding, and the
disk and memory length of every block is unchanged by construction.

`spectate_enable` -- THE ONE THAT MATTERS
    In the `PlayerTick` guard, `native(119)` ("!=" object) becomes `native(114)`
    ("==" object), so the test reads `GameReplicationInfo == none`. Offline the
    replication info always exists, so the clear never runs; the `&&` is a
    `skip`-form operator, so the right-hand side is not evaluated and nothing is
    dereferenced through a null.

    With the clear gone the flag is governed only by `Dead.BeginState` (TRUE) and
    `Dead.EndState` (FALSE), which means it is TRUE exactly while the controller
    is in state `Dead`. That is the whole safety argument for a living player:
    outside `Dead` the flag is false, so `ActionKeyReleased` behaves as it ships.
    Entering `CameraPlayer` leaves `Dead`, so `EndState` clears it again and the
    button cannot re-trigger.

    On its own this card gives the spectator camera the developers built: a free
    chase camera behind a living teammate.

`spectate_headcam` -- first person, i.e. an actual headcam
    `CameraPlayer.BeginState` has another PS2-only branch::

        if (Level.Game != none && Level.Game.m_bIsSplitScreen)
            m_eCameraMode = CAMERA_3rdPersonFree;    // 2
        else
            m_eCameraMode = CAMERA_FirstPerson;      // 0

    so split screen is deliberately given a chase camera. This flips ONE byte --
    the split-screen arm's `ByteConst 02` becomes `ByteConst 00`. `SetCameraMode`'s
    mode-0 arm then sets `bBehindView = false; m_bAttachCameraToEyes = true`, and
    because `CameraPlayer.PlayerMove` does nothing at all while `bBehindView` is
    false, the spectator cannot look around -- which is what a headcam is, and why
    this is a separate card. The region carries the `else` arm too, because
    `0f01e5022400` on its own IS that else arm and a replacement run has to be
    absent from every package.

`spectate_cycle` -- cycling, without touching the pad configuration
    `SpectatorNextViewTarget` and `SpectatorPrevViewTarget` are `event`s with
    `FUNC_Exec` clear, and nothing in script calls them, so no key binding can
    reach them. This borrows a call that is DEAD offline instead.
    `R6InteractionCircumstantialAction.ActionKeyPressed` opens with::

        if (m_Player.Level.NetMode != NM_Standalone)
            m_Player.ServerActionKeyPressed();
        m_Player.SetRequestedCircumstantialAction();

    Offline that first call can never run. `native(155)` ("!=" int) becomes
    `native(154)` ("==" int) so it does, and the call's FName moves from
    `ServerActionKeyPressed` (1128) to `SpectatorChangeTeams` (364). Both FName
    refs are two bytes on disk and four in memory, so the call stays 4 disk / 6
    memory and the enclosing `Context`'s skip word of 6 still measures right.

    Safe while alive: `SpectatorChangeTeams` is overridden ONLY inside
    `CameraPlayer`, and the class-level `R6PlayerController.SpectatorChangeTeams`
    is an empty stub, so every press outside the spectator camera calls an empty
    function and carries on into `SetRequestedCircumstantialAction()` exactly as
    before. `m_Player` is declared `R6PlayerController`, so the name always
    resolves and `FindFunctionChecked` cannot fail.

    No argument is passed, so `bNextTeam` reads 0 out of the zeroed call frame and
    the previous-target arm runs. That arm wraps round at the end of the actor
    list AND, because it only ever remembers pawns that pass `IsAlive()`, it also
    gets the camera off a teammate who has since been killed -- which the camera
    otherwise sits on for ever, since `Tick` only re-acquires while `ViewTarget`
    is none or self (the `|| !Pawn(viewTarget).IsAlive()` in that test is
    commented out in the shipped code).

`spectate_no_wait` -- the ten-second wait
    The PS2 arm requires about ten seconds since the pawn died
    (`native1012() - m_pawn.f_DeadTime > 9.5`). Pressing earlier is harmless and
    this was checked rather than assumed: the `else` is `BeginSpectator()`, whose
    own `GotoState('CameraPlayer')` sits behind `Level.NetMode != NM_Standalone`,
    so offline it only calls `ResetBlur()` and sets `m_eCameraMode` -- and
    `CameraPlayer.BeginState` overwrites that anyway. This rewrites the 9.5 float
    to 0.0, four bytes for four bytes, two of them different.

WHAT THIS DOES NOT GIVE YOU -- THE HUD
--------------------------------------

There is no HUD while spectating, and no byte edit in these packages can add
one. `R6HUD.PostRender` is a three-line shim around `DrawNativeHUD`, native
1605; the HUD is drawn in C++ and it draws from the local player's `Pawn`, never
from `ViewTarget`. `CameraPlayer.BeginState` sets `pawn = none; m_pawn = none`,
so the native code early-outs. The observable signature is that `m_fScaleX` and
`m_fScaleY` -- written only by native code, never by script -- read 0.0 on a
pawn-less controller and 1.0 / 0.467 on a live one.

So the feature the user asked for and the missing HUD they noticed are two
separate jobs. This delivers the view; the HUD needs the native draw call's
pawn source repointed, which is overlay work, not a `.LIN` edit.

`CameraPlayer.BeginState` does call `StopFadeToBlack()`, so the death fade is
cleared on the way in and the picture is not black.

SCOPE AND COMPOSITION
---------------------

`/COMMONOFF.LIN` and `/COMMON_SS.LIN` only. Every offline route into
`CameraPlayer` needs split screen, so single player is untouched, and
`/COMMON.LIN` (online) is left alone -- which matters for `spectate_enable` and
`spectate_cycle`, because both of them invert a test on `NM_Standalone` and would
mean the opposite thing in a network game.

Measured: all four stock runs occur exactly once in each of the three COMMON
packages and all four replacements are absent from all three. The two offline
packages decompress byte-identically, so content pinning is really a two-file
test. No overlap with any of the 130 byte-runs harvested from the other 52
modules.

ONE CAVEAT WORTH KNOWING BEFORE YOU EDIT PlayerTick AGAIN
--------------------------------------------------------

Three of these four regions sit in blocks that `uscode` parses cleanly, and the
test checks the block's `ScriptSize` still describes its content after the edit.
**`PlayerTick`'s block does not parse.** No candidate `ScriptSize` word within
120 KB before the region both reaches its declared size and covers it; every
candidate runs off the end of the bytecode into the next `UFunction`'s record.
Two hypotheses were tried and neither fixed it: this project's recorded "UE2
Assert has no bDebug byte" quirk, and adding opcode 0x03 as a one-reference
variable op. So the cause is still unknown.

Two consequences, both of which the test states rather than hides:

* `find_blocks()` cannot see `PlayerTick`, so the repo's round-trip test over
  every block in the package has never covered it, and no regression test
  protects this region. A future edit here gets no such safety net.
* For THIS edit it does not matter, and that is checked rather than asserted: the
  edit swaps one single-byte native opcode (`0x77`) for another (`0x72`), leaving
  every operand byte alone. The enclosing expression re-parses to identical disk
  AND memory lengths (36/44 and, for the whole `JumpIfNot`, 39/47), so the
  block's `ScriptSize` is untouched and no jump can move. That is the property a
  `.LIN` edit has to have.

`PlayerTick` is confirmed as the right function from two independent directions:
the block references a local the export table names
`R6PlayerController.PlayerTick.fDeltaTime`, and the export table holds exactly
one `PlayerTick`, on `R6PlayerController`.

Not yet played. Everything above is static analysis of the shipped packages plus
reads of thirteen EE images.
"""

from __future__ import annotations

H = bytes.fromhex


class SpectateError(Exception):
    pass


#: Offline single player and split screen. Never `/COMMON.LIN`: two of these
#: regions invert a `NM_Standalone` test, which online would mean the opposite.
SELECT = r"/COMMON(OFF|_SS)\.LIN$"

#: key -> [(name, stock, new)]. One key per card, so each card is one thing.
REGIONS = {
    # R6PlayerController.PlayerTick, COMMON_SS.LIN.plain 0x115E74. The guard
    # that disarms the spectator button every frame.
    #   07 9000        JumpIfNot -> mem 144
    #   82             native(130)  &&
    #     77 01d401 2a 16      GameReplicationInfo != none   <-- THE BYTE
    #     18 2000              Skip(32)
    #       9b ...             m_eServerState != RSS_InGame(3)
    #   14 2d01d402 28  m_bReadyToEnterSpectatorMode = false
    # The LetBool is carried so the run cannot match the guard alone.
    "spectate_enable": [
        ("PlayerTick spectator-button disarm",
         H("079000" "82" "7701d4012a16" "182000"
           "9b393a1901d40105000101db03393a1901d40102000124031616"
           "142d01d40228"),
         H("079000" "82" "7201d4012a16" "182000"
           "9b393a1901d40105000101db03393a1901d40102000124031616"
           "142d01d40228")),
    ],

    # CameraPlayer.BeginState's split-screen camera mode, 0x11132F.
    #   0f 01e502 2402   m_eCameraMode = CAMERA_3rdPersonFree   <-- THE BYTE
    #   06 1e01          Jump -> mem 286
    #   0f 01e502 2400   m_eCameraMode = CAMERA_FirstPerson
    "spectate_headcam": [
        ("CameraPlayer.BeginState split-screen camera mode",
         H("0f01e5022402" "061e01" "0f01e5022400"),
         H("0f01e5022400" "061e01" "0f01e5022400")),
    ],

    # R6InteractionCircumstantialAction.ActionKeyPressed, 0x15D3DE.
    #   if (m_Player.Level.NetMode != NM_Standalone)   <- 9b native(155) "!="
    #       m_Player.ServerActionKeyPressed();         <- 1b 6811 16
    # 9b -> 9a makes it run offline; 6811 -> 6c05 repoints it at
    # `SpectatorChangeTeams`. Both FName refs are two bytes wide, so the call
    # stays 4 disk / 6 memory and the Context's skip word of 6 is still right.
    "spectate_cycle": [
        ("ActionKeyPressed dead offline call -> SpectatorChangeTeams",
         H("0731009b393a1919010d050004018f05000101a2393a240016"
           "19010d0600001b681116"),
         H("0731009a393a1919010d050004018f05000101a2393a240016"
           "19010d0600001b6c0516")),
    ],

    # Dead.EnterSpectatorMode's "seconds since the pawn died" threshold, 0x11177D.
    #   18 1b00        Skip(27)
    #     b1           native(177)  >  float
    #       af         native(175)  -  float
    #         63f4 16                    native(1012)()
    #         19 010b 0500 04 01e007 16  m_pawn.f_DeadTime
    #       1e 00001841                  FloatConst 9.5   <-- THE FOUR BYTES
    #     16 16
    "spectate_no_wait": [
        ("Dead.EnterSpectatorMode dead-time threshold",
         H("181b00" "b1" "af" "63f416" "19010b05000401e00716" "1e00001841" "1616"),
         H("181b00" "b1" "af" "63f416" "19010b05000401e00716" "1e00000000" "1616")),
    ],
}


def _sites(plain: bytes, which: str):
    """[(offset, stock, new, state)] for one key, or raise."""
    rows = REGIONS.get(which)
    if not rows:
        raise SpectateError("unknown spectate region %r" % which)
    out = []
    for name, stock, new in rows:
        if len(stock) != len(new):
            raise SpectateError("%s: the replacement is a different length" % name)
        hits = []
        for form, state in ((stock, "stock"), (new, "new")):
            at = plain.find(form)
            if at >= 0 and plain.find(form, at + 1) >= 0:
                raise SpectateError("%s: found more than once" % name)
            if at >= 0:
                hits.append((at, state))
        if len(hits) != 1:
            raise SpectateError(
                "%s: %s" % (name, "not found" if not hits
                            else "both forms present"))
        out.append((hits[0][0], stock, new, hits[0][1]))
    return out


def reads(plain: bytes, which: str) -> bool:
    try:
        return all(s[3] == "new" for s in _sites(plain, which))
    except SpectateError:
        return False


def apply(plain: bytes, which: str, enable: bool = True):
    """Returns (bytes, regions changed). The length never moves."""
    want_new = bool(enable)
    if reads(plain, which) == want_new:
        return plain, 0
    out = bytearray(plain)
    n = 0
    for at, stock, new, _state in _sites(plain, which):
        want = new if want_new else stock
        if out[at:at + len(stock)] != want:
            out[at:at + len(stock)] = want
            n += 1
    if len(out) != len(plain):
        raise SpectateError("a spectate edit changed the file length")
    return bytes(out), n


def cards(prefix, group):
    from .model import BOOL, Setting

    need = {prefix + "spectate_enable": [True]}
    return [
        Setting(
            prefix + "spectate_enable",
            "A dead player can watch a living teammate", BOOL, False, group,
            confidence="experimental", touches="data",
            help="Die in split screen, wait about ten seconds, then press and "
                 "release the action button -- the one you use for doors and "
                 "orders. The camera moves to a living teammate: the other "
                 "player, Weber or Loiselle.\n\n"
                 "The game already contains this camera and already knows how "
                 "to find your teammates. What stops it is that the button is "
                 "disarmed again every frame, because the check that does it "
                 "was written for a network game and nobody switched it off "
                 "offline. This is that one byte.\n\n"
                 "On its own you get a free camera behind the teammate's "
                 "shoulder. Add \"...from his eyes\" for a headcam.",
            caution="Not yet played -- it comes from reading the shipped "
                    "packages and thirteen saved states, not from a session.\n\n"
                    "THERE IS NO HUD WHILE YOU WATCH. The HUD is drawn by the "
                    "game's own C++ from your own soldier, and while you are "
                    "spectating you do not have one. Nothing in these files can "
                    "change that; it is separate work.\n\n"
                    "Split screen only, and only on the level you died on. "
                    "After a level change a dead player is put into a plain "
                    "holding state and never enters the dead state, so there is "
                    "nothing there to switch on yet.\n\n"
                    "Use it with \"A dead player keeps his own screen\", which "
                    "is what stops a level change handing your half of the "
                    "screen to the other player.\n\n"
                    "While you are watching someone, the game re-points your "
                    "own squad pointer at his squad. If you also use \"carry "
                    "wounds between parts\", that is the interaction to watch."),
        Setting(
            prefix + "spectate_headcam",
            "...and sees it from his eyes", BOOL, False, group,
            confidence="experimental", touches="data", requires=need,
            help="The spectator camera floats behind the teammate's shoulder. "
                 "This makes it first person instead, so you see exactly what "
                 "he sees.\n\n"
                 "The developers chose the shoulder camera for split screen on "
                 "purpose -- single player already uses first person here -- so "
                 "this is one byte that makes split screen agree with it.\n\n"
                 "In first person the camera is locked to his head, so your "
                 "stick does nothing. That is what makes it a headcam. Leave "
                 "this off if you would rather be able to look around.",
            caution="Not yet played. It does nothing unless \"A dead player can "
                    "watch a living teammate\" is also on."),
        Setting(
            prefix + "spectate_cycle",
            "Action button changes who you watch", BOOL, False, group,
            confidence="experimental", touches="data", requires=need,
            help="Press the action button again while watching and the camera "
                 "steps to another living operative -- the other player, Weber "
                 "or Loiselle -- round and round. It also gets you off a "
                 "teammate who has since been killed, which the camera "
                 "otherwise sits on for good.\n\n"
                 "It costs you nothing while alive: the call it borrows lands "
                 "on an empty function unless you are actually spectating.",
            caution="Not yet played. Your pad configuration is not touched -- "
                    "this reuses the action button you already press."),
        Setting(
            prefix + "spectate_no_wait",
            "No wait before the camera opens", BOOL, False, group,
            confidence="experimental", touches="data", requires=need,
            help="The camera only opens about ten seconds after you died. "
                 "Pressing the action button sooner does nothing visible, so "
                 "you end up pressing twice. This removes the wait.",
            caution="Not yet played. This is the one of these that overrides a "
                    "delay the developers chose, so it is the one most likely "
                    "to look wrong -- the death fade and the blur are still "
                    "running when the camera opens."),
    ]

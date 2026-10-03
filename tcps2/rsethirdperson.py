r"""DRAFT -- Rainbow Six 3 played over the shoulder.

NOT SHIPPED, and NOT PLAYED. Everything below is static analysis of the three
pristine COMMON packages plus disassembly of the pristine SP.SOZ overlay. No
session was run.

THE SHORT VERSION
-----------------

`bBehindView` is the stock UE2 `PlayerController` flag, and this build is
written for it. Nothing needs authoring, nothing needs a code cave, and the
whole feature is **one byte**: the `False` token of the last `bBehindView =
false` that runs when the player is given his soldier.

WHY IT WORKS -- THE THREE THINGS THAT USUALLY KILL THIS
--------------------------------------------------------

*The camera.* `PlayerController.PlayerCalcView` is UnrealScript in this build
(`COMMON*.LIN.plain` block 0x05F8C6) and it is the ONLY thing that writes the
viewport's camera. The overlay calls it by name through `ProcessEvent` at
`0x002EF330`, seeding the parameters from the controller's own Location and
Rotation, and the result is stored at `0x002EF3D0`/`0x002EF3F0` -- the single
writer of viewport `+0x1C0`/`+0x1D0` in the whole image. So the script's
`if (bBehindView) CalcBehindView(...) else CalcFirstPersonView(...)` is the
camera, with nothing native underneath it.

`R6PlayerController.CalcBehindView` (block 0x1156FE) is complete and live::

    CameraRotation = Rotation + Pawn.m_rRotationOffset     // full look, pitch included
    View = vect(1,0,0) >> CameraRotation
    if (Trace(hit, norm, CameraLocation - (Dist+30)*vector(CameraRotation),
              CameraLocation, TRUE) != None)
        ViewDist = FMin((CameraLocation - hit) dot View, Dist)
    else ViewDist = Dist
    CameraLocation -= (ViewDist - 30) * View

`PlayerCalcView` hands it `CameraLocation = Pawn.Location + (CollisionHeight +
30) * vect(0,0,1)` -- a PS2 addition, the Xbox script has no such raise -- and
`Dist = CameraDist * Pawn.Default.CollisionRadius`. `CameraDist` is 9.0 in the
Engine package's `PlayerController` defaults and the R6 pawn classes carry a
default `CollisionRadius` of 35-40, so the camera sits about 300 units back and
105 up, which is roughly 3 m and 1 m at this game's scale. Walls pull it in;
so do characters, because unlike the Engine base this override passes
`bTraceActors = TRUE`.

*The player's own body.* It is hidden in first person by `bOwnerNoSee`, which
is TRUE in the `Pawn` class defaults (the only such default in the package
set, at plaintext 0x05C5EB). The overlay's per-actor visibility filter at
`0x00310A20` carries the stock UE2 rule and its stock override::

    0x00310CF4  lbu   $v0, 0x6f($s0)      ; Actor bool byte, bit 1 = bOwnerNoSee
    0x00310D30  lbu   $v0, 0x4d8($v0)     ; PlayerController bool byte
    0x00310D38  dsrl32 $v0, $v0, 0x1f     ;   bit 6 = bBehindView
    0x00310D3C  bnez  $v0, 0x310d50       ; set -> draw it anyway
    0x00310D44  move  $v0, $zero          ; clear -> cull

So the soldier draws himself the moment the flag is set. No edit needed, and
his `R63rdWeapons` gun comes with him because it is attached to him.

*The shots.* They do not follow the camera, and that is by design rather than
by luck. `R6Pawn.GetFiringStartPoint()` is `Location + EyePosition()`, and
`R6Pawn.EyePosition` (block 0x0F3A88) opens with::

    if (m_bIsPlayer && pc != none && !pc.bBehindView && pc.ViewTarget == self)
        return m_vEyeLocation - Location;      // the head bone
    if (bIsCrouched)      vEyeHeight.Z = 40;
    else if (m_bIsKneeling) vEyeHeight.Z = 20;
    else                  vEyeHeight.Z = 70;

In behind view the player falls through to the posture-based eye every AI
already uses. The overlay agrees literally: the native eye getter at
`0x003A2200` tests the same `+0x4D8` bit 6 at `0x003A2350` and falls through
to `Location + 40.0 / 20.0 / 70.0` -- the same three constants, which is how
the bit was identified. So a round still leaves the soldier's head and cover
his head is behind still stops it.

NOTHING RE-ASSERTS IT
---------------------

The usual wall for a flag like this is something stamping it back every frame.
Nothing does. `LetBool(bBehindView, ...)` occurs exactly fifteen times in the
whole package set and every one is one-shot:

* `ClientReStart` (0x05EFED), `Restart` (0x05FE2A), `Reset` (0x0612D9) and
  `R6PlayerController.DisableFirstPersonViewEffects` (0x11150B) clear it;
* `Spectating.Fire` / `.AltFire`, `ServerViewSelf`, `ServerViewNextPlayer`,
  `GameEnded.BeginState` and one other `BeginState` are spectator and
  end-of-game paths;
* `CameraPlayer.SetCameraMode`'s three arms and `CameraPlayer.EndState` belong
  to the split-screen spectator camera;
* the `exec function BehindView(bool B)` is behind `CheatManager.CanExec()`.

The three that run when the player is given his soldier all run in the order
listed above, so `ClientReStart` decides, and it decides again on every
mission. On death `Dead.BeginState` clears the flag through
`DisableFirstPersonViewEffects`, which is right: the death camera stays stock.

WHAT IS ACTUALLY WRONG
----------------------

Not "what might be" -- these are read out of the shipped code.

*No reticule, and the one you can put back is not where the rounds go.*
`R6Weapons.PostRender` draws the crosshair only when `!aPC.bBehindView`, so it
disappears; `tp_reticle` puts it back. But `R6XboxReticule.PostRender` draws it
at `Canvas.HalfClipX` / `HalfClipY` -- fixed screen centre, with the four arms
spread by the accuracy cone -- so it is the CAMERA's line, while the round is
on a parallel line from the eye 35-40 units lower. The impact therefore sits
below the crosshair by `atan(dz / (range + camera setback))`: about 4 degrees
at 2 m, 1.5 at 10 m, 0.4 at 50 m, which is roughly 30 px near and 3 px far on
a 640-wide 90-degree view. Auto-aim hides most of it, because a locked shot
goes to the target rather than along the crosshair.

*The first-person weapon takes care of itself.* Nothing in script ties
`ShouldDrawWeapon()` to the flag, which looked like a problem until the
overlay was read: the two first-person view-model draw routines
(`0x003F4A80`, vtable +0x170, and its twin `0x003F53B0`, +0x174) both test the
same bit and return early when it is set, at `0x003F4AF4` and `0x003F5424`. So
the view model hides itself and no edit is needed. The same is true of the
muzzle flash: the per-shot effects routine at `0x003F6020` REQUIRES the bit to
be set before it spawns sub-emitters 2-6, the third-person flash, and skips
the first-person-only ones (`0x003F67A8`, `0x003F6960`, `0x003F69C8`).

*Aiming up and down is fine, and the body still turns.* `UpdateRotation` is
native on this build -- `R6PlayerController.UpdateRotation` is the stub
`native4080()`, implemented at `0x003B8DA0` -- so it cannot be read from the
package. It does not have to be: it reads the flag at exactly three places
(`0x003B8FAC`, `0x003B936C`, `0x003B9748`) and the Xbox script of the same
function reads it at exactly three places, in the same roles -- the peeking
camera ROLL (line 1353), and the two `Pawn.FaceRotation` calls (1408, 1463).
`rViewRotation.Pitch += aLookUp` and `AdjustViewPitch` sit outside all three,
so the pitch is untouched and the camera looks where you look. Read out of the
overlay rather than inferred: `aLookUp` (`PC+0x514`) is integrated into the
running pitch at `0x003B8F50`-`0x003B8F70`, clamped to `0x4000`/`0xC000`
(+/-90 degrees) at `0x003B8F74`-`0x003B8FA8`, and the result is differenced
against the controller's own rotation and stored to `Pawn+0x540`
(`m_rRotationOffset.Pitch`) at `0x003B9044`/`0x003B904C` -- and `0x003B9044`
is the behind-view branch's own TARGET, so the behind-view path runs all of
it. The value the guard really drops is the lean ROLL trim: `$s2` is zeroed in
the branch's delay slot and its only consumer is `Pawn+0x548`. The second
`FaceRotation` is guarded by `(!bFreeCamera || !bBehindView)`, and
`bFreeCamera` has ONE reference in the whole package set (this test), no
writer and no serialised default, so it is false for ever and that call still
fires: the soldier turns to face the camera. What behind view really costs
here is the peek tilt, which a chase camera should not have anyway.

*Zoom freezes, and so does the eye -- this is the one that matters.*
`R6PlayerController.PlayerTick` calls `SetEyeLocation` only when
`m_bAttachCameraToEyes && !bBehindView`, `SetEyeLocation` is the sole writer
of `m_vEyeLocation` (`pViewTarget.m_vEyeLocation = GetBoneCoords('R6
PonyTail1').Origin`), and it is also the ONLY caller of `AdjustView`, which is
the FOV interpolation. So behind view costs two things at once: `FovAngle`
never follows `DesiredFOV` again, which kills every zoom, and
`m_vEyeLocation` stops moving.

The second half is the serious one, because `m_vEyeLocation` is not only the
first-person camera. It is `Pawn+0x530` in the overlay -- the same field
`R6Pawn.GetFiringStartPoint` returns through its first-person arm at
`0x003A2350`, and that native is identified beyond doubt by its cache pair:
it stamps `Pawn+0x68C` against `Level.TimeSeconds` and caches to `Pawn+0x7D0`,
which is exactly `m_fLastFSPUpdate` / `m_vFiringStartPoint`. And
`UpdateReticule` -- native, `0x003B9820` -- traces the auto-aim ray FROM
`Pawn+0x530`, storing the hit at `R6PlayerController+0x7C0`, which is the
point `FireBullets` turns each round onto. The overlay gates its own eye
update the same way script does (`0x003B8680` skips the sub-update at
`0x003B8860` when the flag is set), so with nothing done about it the aim ray
would be cast from wherever the eye last was. `tp_keep_eye` removes the gate,
the script writer runs every frame as it does in first person, and both the
zoom and the aim ray are healthy again.

*Three smaller ones, for honesty.* The chase camera's wall trace passes
`bTraceActors = TRUE` -- the Engine base does not -- so a teammate standing
behind you pulls the camera in. With `tp_keep_eye` a scope still zooms, but it
zooms the camera that is three metres behind the soldier rather than putting
you at the sight, which will read as wrong; nothing cheap switches the scope
back to first person, because `SetCameraMode` is an empty stub outside the
spectator state. And the peek tilt is gone, which is the developers' own
choice rather than a defect.

THE EDITS
---------

Offsets are into the decompressed package and are recorded, not used -- every
region is searched for and must be unique.
"""

from __future__ import annotations

H = bytes.fromhex


class ThirdPersonError(Exception):
    pass


#: Offline single player and split screen. Never `/COMMON.LIN`.
SELECT = r"/COMMON(OFF|_SS)\.LIN$"

#: key -> [(name, stock, new)]
REGIONS = {
    # Engine.PlayerController.ClientReStart, block 0x05EFCA, body 0x05EFCE.
    # The spawn chain is R6RainbowTeam.CreateTeamMember -> Possess ->
    #   PossessInit  -> DisableFirstPersonViewEffects  -> bBehindView = false
    #   Restart      -> bBehindView = false
    #                -> ClientReStart -> bBehindView = false   <-- LAST
    # so this is the write that decides, and it runs again on every mission.
    #   07 1400            JumpIfNot -> 0x14   (Pawn == none)
    #   71 216b 07 16      GotoState('WaitingForPawn')
    #   04 0b              return
    #   19 0106 0600 00 1b 6202 16   Pawn.ClientReStart()
    #   1c 6901 01 0616    SetViewTarget(Pawn)
    #   14 2d 013d 28      bBehindView = false        <-- THE BYTE
    #   1b 6704 16         EnterStartState()
    #   04 0b              return
    "tp_camera": [
        ("PlayerController.ClientReStart bBehindView",
         H("0714007201062a1671216b0716040b1901060600001b6202161c6901010616"
           "142d013d28" "1b670416040b"),
         H("0714007201062a1671216b0716040b1901060600001b6202161c6901010616"
           "142d013d27" "1b670416040b")),
        # Restart's own write is overwritten by ClientReStart above, but it is
        # flipped too so the two can never disagree if ClientReStart ever
        # early-returns on a null pawn.
        ("PlayerController.Restart bBehindView",
         H("1c6c0e160f0178201e000000000f0171201e000000001b6704161c6901010616"
           "142d013d28" "1b620216040b"),
         H("1c6c0e160f0178201e000000000f0171201e000000001b6704161c6901010616"
           "142d013d27" "1b620216040b")),
    ],

    # R6PlayerController.PlayerTick, plaintext 0x115EA4. The gate that stops
    # SetEyeLocation -- and therefore AdjustView, the FOV interpolation --
    # the moment behind view is on. `bBehindView` (import -167) becomes
    # `m_bCameraGhost` (export 4045), which is inert by MEASUREMENT rather
    # than by reputation: no LetBool writer instance or default, no block
    # reads it, and its name index reaches no class-defaults entry at all,
    # so the term reads `!false` for ever. Both refs are two bytes on disk
    # and four in memory, so the Skip's count of 9 still measures right and
    # the block's ScriptSize cannot move.
    #
    # This was `m_bFixCamera` until 2026-09-29, and that was wrong. It has a
    # live writer at 0x1171FA -- assigned from another bool, not a constant
    # -- and five blocks read it, one of them CalcBehindView itself, so the
    # gate could close for good instead of never closing.
    #
    # That costs more than the eye position. The weapon recoil SHAKE lives
    # inside SetEyeLocation too, immediately after the eye write:
    # m_fShakeTime, m_fCurrentShake and m_rHitRotation's three
    # RandRange(m_fMaxShake) components are all in that one block. So this
    # single gate governs the eye position, the FOV interpolation and the
    # recoil shake together -- which is exactly the set of three things play
    # reported missing in third person on 2026-09-29.
    #   82                     &&
    #     2d 015609            m_bAttachCameraToEyes
    #     18 0900              Skip(9)
    #       81 2d 01e702       !bBehindView          <-- THE TWO BYTES
    #     16 16
    # The run starts at the `&&` (0x115EA4) and not one byte earlier: the
    # statement before it is `m_bReadyToEnterSpectatorMode = false`, whose
    # closing `28` is the last byte of `rsespectate.spectate_enable`'s run.
    # Starting here the two modules share no byte, and they compose -- each
    # edits an operand outside the other's region.
    "tp_keep_eye": [
        ("PlayerTick eye/FOV gate",
         H("822d015609180900812d01e7021616" "07d300"),
         H("822d015609180900812d014d3f1616" "07d300")),
    ],

    # NOT SHIPPED, kept because it was measured and may still be wanted:
    # R6PlayerController.ShouldDrawWeapon, block 0x116A6D, tail
    # `return m_bShowFPWeapon` -> `return m_bFixCamera` (false for ever), which
    # would suppress the first-person weapon from script. It is unnecessary --
    # the overlay's own view-model draw already returns early on the flag --
    # and it is listed here only so the region is on record. Flipping
    # m_bShowFPWeapon's class default instead does NOT work: five script sites
    # call ShowWeapon(), which puts it back to true.
    #   stock  0101d4010600042d015128160427 042d015c21
    #   new    0101d4010600042d015128160427 042d015e10

    # R6Weapons.PostRender, plaintext 0x1DD9B8 (0x1DD9C3 in /COMMON.LIN).
    # The crosshair's guard ends `&& !aPC.bBehindView`; that term becomes
    # `&& !aPC.m_bMenuDisplayed`, which the same guard already tests two terms
    # earlier, so the test reduces to exactly the shipped one minus the
    # behind-view suppression. Import -143 -> import -376, both two bytes.
    "tp_reticle": [
        ("R6Weapons.PostRender reticule guard",
         H("1616181200811900370600" "042d01cf02" "16160f00"),
         H("1616181200811900370600" "042d01f805" "16160f00")),
    ],
}


def _sites(plain: bytes, which: str):
    rows = REGIONS.get(which)
    if not rows:
        raise ThirdPersonError("unknown third-person region %r" % which)
    out = []
    for name, stock, new in rows:
        if len(stock) != len(new):
            raise ThirdPersonError("%s: the replacement is a different length" % name)
        hits = []
        for form, state in ((stock, "stock"), (new, "new")):
            at = plain.find(form)
            if at >= 0 and plain.find(form, at + 1) >= 0:
                raise ThirdPersonError("%s: found more than once" % name)
            if at >= 0:
                hits.append((at, state))
        if len(hits) != 1:
            raise ThirdPersonError(
                "%s: %s" % (name, "not found" if not hits else "both forms present"))
        out.append((hits[0][0], stock, new, hits[0][1]))
    return out


def reads(plain: bytes, which: str) -> bool:
    try:
        return all(s[3] == "new" for s in _sites(plain, which))
    except ThirdPersonError:
        return False


def apply(plain: bytes, which: str, enable: bool = True):
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
        raise ThirdPersonError("a third-person edit changed the file length")
    return bytes(out), n


# ---------------------------------------------------------------------
# The peek lean, which is an overlay word rather than a script edit.
#
# R6PlayerController.UpdateRotation is native here, and it reads
# bBehindView at three places. The FIRST one, at 0x003B8FAC, is the lean:
#
#   0x003B8FAC  lbu    $a0, 0x4d8($s4)   ; controller bool byte
#   0x003B8FB0  dsll32 $a0, $a0, 0x19
#   0x003B8FB4  dsrl32 $a0, $a0, 0x1f    ; bit 6 = bBehindView
#   0x003B8FB8  bnez   $a0, 0x003B9044   ; behind view -> skip the lean
#   0x003B8FBC  move   $s2, $zero        ; delay slot, runs either way
#
# The block it skips computes the lean ROLL into $s2 (the float run ending
# `mfc1 $s2, $f0` at 0x003B9040), and the join at 0x003B9044 differences
# $s2 and stores it through $s6 -- Pawn+0x548, m_rRotationOffset.Roll. So
# in behind view the roll is always the zero the delay slot wrote, and the
# camera does not lean when you peek. Play confirmed that on 2026-09-29.
#
# Turning the branch into a NOP makes behind view fall through and compute
# the same roll first person does. First person is untouched by
# construction: $a0 is zero there, so the branch was never taken anyway.
PEEK_AT = 0x003B8FB8
PEEK_STOCK = 0x14800022          # bnez $a0, 0x003B9044
PEEK_NEW = 0x00000000            # nop


def stock_words():
    """{va: stock} for the word this module touches."""
    return {PEEK_AT: PEEK_STOCK}


def words(enable=True):
    """[(va, new, stock)] for the peek lean, in the shape build_edits wants."""
    if not enable:
        return []
    return [(PEEK_AT, PEEK_NEW, PEEK_STOCK)]


def cards(prefix, group):
    """The three cards, in the order they depend on each other."""
    from .model import BOOL, Setting

    cam = prefix + "tp_camera"
    return [
        Setting(
            cam, "Play in third person", BOOL, False, group,
            confidence="experimental", touches="data",
            help="Moves the camera behind your soldier instead of "
                 "behind his eyes, about three metres back and a metre "
                 "up.\n\n"
                 "Almost all of this is already in the game. Your body "
                 "is only hidden in first person, and the engine draws "
                 "it again as soon as the camera moves out; the "
                 "first-person weapon hides itself; the muzzle flash "
                 "switches to the one everyone else uses. Shots still "
                 "leave your soldier rather than the camera.\n\n"
                 "Campaign and split screen only. It is deliberately "
                 "not written to the online package.",
            caution="Not yet played.\n\n"
                    "Turn on the other two options with it. On its own "
                    "you lose the crosshair, and the auto-aim traces "
                    "from a point that stops updating.\n\n"
                    "Scopes zoom the chase camera rather than putting "
                    "you at the sight, and the camera pulls in when a "
                    "teammate stands behind you."),
        Setting(
            prefix + "tp_keep_eye", "...and aiming keeps up", BOOL,
            False, group, requires={cam: True},
            confidence="experimental", touches="data",
            help="The routine that tracks where your soldier's eyes are "
                 "is skipped in third person, and it is the only thing "
                 "that updates that position each frame. The auto-aim "
                 "traces FROM it, and the zoom lerp is driven by it, so "
                 "without this your aim ray goes stale and zoom "
                 "freezes.\n\n"
                 "This points the test at a flag that is never true "
                 "instead, so the eye position keeps being written.",
            caution="Not yet played."),
        Setting(
            prefix + "tp_peek", "...and peeking leans the camera", BOOL,
            False, group, requires={cam: True},
            confidence="experimental", touches="code",
            help="UpdateRotation is native on this build and skips the lean "
                 "roll the moment behind view is on -- the roll is left as "
                 "the zero its delay slot wrote, so the camera stays level "
                 "however far you peek. This turns that one branch into a "
                 "nop, so the chase camera leans the way first person "
                 "does.\n\n"
                 "First person cannot change: the branch is only ever taken "
                 "in behind view.",
            caution="Never played. Reported missing in play on 2026-09-29, "
                    "which is what identified the branch.\n\n"
                    "The block it now falls into reads a pointer at "
                    "controller+0x788 and a float inside it. That pointer "
                    "is the same one first person reads every frame, but it "
                    "has not been proven non-null on the behind-view path, "
                    "so a crash while peeking is the failure to watch "
                    "for."),
        Setting(
            prefix + "tp_reticle", "...and the crosshair is drawn",
            BOOL, False, group, requires={cam: True},
            confidence="experimental", touches="data",
            help="The crosshair is suppressed in third person. This "
                 "points that test at a term the same guard already "
                 "checks, so it draws again.",
            caution="Not yet played.\n\n"
                    "The crosshair sits at the centre of the SCREEN "
                    "while the round leaves an eye about half a metre "
                    "lower, so shots land under it -- roughly four "
                    "degrees at two metres, falling to under half a "
                    "degree at fifty. The game's own aim assist hides "
                    "most of that."),
    ]
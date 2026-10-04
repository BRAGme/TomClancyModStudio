"""Third-person camera for Ghost Recon (SLUS-20613) and Jungle Storm (SLUS-20820).

Neither game has a first-person weapon model, so the Rainbow Six 3 view-model
options have nothing to work on. What both games do have is a third-person
camera -- only for spectators. SimCamera::UpdateMovement forces a live
player's view back to first person every frame, and ToggleCameraView snaps
it to 0 as well; the third-person placement runs only after death.

This keeps the view a live player is in, draws the reticle, zoom panel and
action menu in third person too, places the camera with a height, sideways
and distance offset from the soldier's eye, and turns every shot the soldier
fires towards the point under the reticle, so the rounds go where the reticle
is while still starting from the soldier.

Placement (``cam_tp``, called from the view-1 block of
UpdateFollowerCameraMovement) builds the offset H up, L to the soldier's right
-- (ly, -lx, 0) normalised; Z is up and the engine is right-handed -- and D
back along the look vector, then runs the game's own SimCamera::PlaceCamera
sphere sweep from the eye, so walls pull the camera in exactly as they do for
the stock spectator camera. A floor probe keeps it 0.25 m above the ground.
The view looks along the soldier's look vector.
While zoomed (field of view under 1.5 rad) or on a mounted gun it returns 0
and the stock first-person placement runs, so scopes and binoculars work.

Shots. Every round still starts where the game starts it -- the Gunshot
message's origin is SimHuman::GetShootFromLocation, the soldier's eye (his
head) -- so cover his head is behind stops it, as in first person. What changes is where
it is sent. ``cam_tp`` marks SimCamera+0x74 (a spare word only the constructor
writes) 1 when it placed the camera and 0 when it fell back to first person.
SimHuman::UpdateBurst turns a burst's free shots with RSQuat::Set(forward,
look) and applies each round's spread (Reticule::GetShotDirection) on top;
``aim_base`` stands in for that Set when the shooter is a player's soldier
(control type 0) followed by a split-screen camera in third person with the
mark set. It traces the camera's centre line -- from the camera along its
view, which is the soldier's look -- with RSSimRoom::FindLineCollision from
the camera's room, exactly as IkeSimulationMgr::HandleGunshot traces a round
(kIsGunshot, faces marked kGunshotTransparent passed, the soldier himself
ignored), so it stops on scenery and on soldiers; nothing within 1 km gives
the point 1 km out. The burst then turns onto P - O (P that point, O the
shot origin) instead of the look, spread unchanged. If P is not at least 0.5
m ahead of O along the view (the line struck something beside or behind the
soldier) the look is kept. A locked-on shot aims at its target from O rather
than from the camera (``aim_from``, replacing SimCamera::GetLocation there).
Zoomed or scoped (first-person placement), mounted guns, first-person view,
AI and network soldiers: unchanged. "Shots from the eye" marks 0, so free
shots leave the eye parallel to the camera line, landing 0.2-0.5 m off the
reticle.

An earlier version moved the shot origin onto the camera line instead
(SimCamera+0x74 held the offset); from a crouch behind a car the camera's
height let rounds clear it. Its two hook sites are ``RETIRED`` and stay in the
stock table so a disc patched by it is put back.

The routines live in three library functions nothing references:
sceDevConsDraw (GR 0x0040DA50, JS 0x00176300, 456 bytes: cam_tp, aim_from),
sceVu0DropShadowMatrix (GR 0x0042BC38, JS 0x001976C0, 400 bytes: aim_base)
and GR sceMcRename 0x00421F78 (360 bytes) / JS lgAudWriteVag 0x00553928 (368
bytes, the USB headset library's; nothing in the ELF or either overlay
refers to it): floor_clamp. Every stock word was checked against the retail
executables. The routines were run in an interpreter (VU0 micro-program and
scratchpad DMA included, so PlaceCamera and FindLineCollision run for real)
through the real SimHuman::UpdateBurst on RAM from savestates of both games
-- single player, both split-screen cameras, online co-op in Jungle Storm's
J03 Railroad: the Gunshot origin equals stock, the direction points at P,
spread is kept, locked-on shots aim from the origin, and a prone soldier's
round is stopped by the low wall in front of him that the camera line clears
(it used to fly on). Converging shots confirmed in play 2026-09-29.

"Show when cover blocks your shot" (``blocked_edits``, both games): while
the round's own line is blocked short of the reticle point, the reticle turns
amber and moves to where the round would hit (the first build, played
2026-09-29, kept it in place and added a small amber mark there); see the
section below.

"Camera near scenery" (``build_fix`` / ``cam_fix``, the ``*_tp_smooth`` option):
the camera stays on the line from the eye through its full-distance place, is
pulled in front of anything the line from the eye meets (trees and props the
sphere sweep passes), and eases back out instead of jumping.
"""

from __future__ import annotations

import struct

from .grasm import assemble


def _fbits(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


def _li_f(reg_f, x, tmp="at"):
    # always lui + ori, so every preset has the same layout
    b = _fbits(x)
    return ("    lui   %s, 0x%04x\n    ori   %s, %s, 0x%04x\n    mtc1  %s, $f%d\n"
            % (tmp, b >> 16, tmp, tmp, b & 0xFFFF, tmp, reg_f))


GAMES = {
    "gr": dict(
        key="gr",
        EYE=0x478, LOOK=0x210, FOV=0x254, MANNED=0x588,   # SimHuman fields
        PLACE=0x003AB030,       # SimCamera::PlaceCamera
        ISSNIPER=0x003DE170,    # SimHuman::IsSniper: sniper weapon (motion type 2/3), zoom > 1x
        FLOOR=0x004DAD60,       # RSSimRoom::FindLevelPointIsOver(pt, face&, height&)
        SIMMGR=0x005EACF0,      # mIIkeSimulationMgr (cameras at +0x444 / +0x448)
        FLC=0x004D8540,         # RSSimRoom::FindLineCollision(line, info&, max, ignore, flags, mask, 1, 0)
        LCINFO=0x003835B0,      # RSLineCollisionInfo::RSLineCollisionInfo
        QSET=0x00117C90,        # RSQuat::Set(from, to) -- normalises both
        SHOOTFROM=0x2D4,        # SimHuman vtable: GetShootFromLocation(out, slot), the stock shot origin
        LINE_V=0x0C,            # RSLine3: point +0, vector +0xC (12-byte RSVector3)
        UB_SH="s4", UB_SCR=0xD0,                          # SimHuman::UpdateBurst: this, a free temp
        AIMBASE=(0x003D2BA4, 0x0C045F24),                 # its jal RSQuat::Set before the round loop
        CLOCK=0x005DFC20,       # RSClock (+0xD4: TotalElapsedSeconds)
        SCENEGET=0x00359760,    # RSSimScene::Get
        FINDROOM=0x005044E0,    # RSSimScene::FindRoom(scene, pt)
        CAVE_A=0x0040DA50, CAVE_A_BYTES=456,   # sceDevConsDraw, unreferenced
        CAVE_B=0x0042BC38, CAVE_B_BYTES=400,   # sceVu0DropShadowMatrix, unreferenced
        CAVE_C=0x00421F78, CAVE_C_BYTES=360,   # sceMcRename, unreferenced
    ),
    "js": dict(
        key="js",
        EYE=0x49C, LOOK=0x210, FOV=0x254, MANNED=0x5B8,
        PLACE=0x0038AC50,
        ISSNIPER=0x003BD860,    # the same test (motion types 2/3, zoom factor > 1.0)
        FLOOR=0x004C1830,
        SIMMGR=0x0062B8D0,
        FLC=0x004C40E0,
        LCINFO=0x00261A00,
        QSET=0x00115D30,
        SHOOTFROM=0x2D8,
        LINE_V=0x10,            # point +0, vector +0x10 (16-byte RSVector3)
        UB_SH="s5", UB_SCR=0xB0,
        AIMBASE=(0x003B2230, 0x0C04574C),
        CLOCK=0x00684768,
        SCENE=0x00689E30,       # the RSSimScene (grpierce's FindRoom caller loads it the same way)
        FINDROOM=0x004EB880,
        CAVE_A=0x00176300, CAVE_A_BYTES=456,
        CAVE_B=0x001976C0, CAVE_B_BYTES=400,
        CAVE_C=0x00553928, CAVE_C_BYTES=368,   # lgAudWriteVag, unreferenced by the ELF and both overlays
    ),
}

#: kIsGunshot and kGunshotTransparent (GR 0x0058BC38 / 0x0058BCC0, JS 0x0059C270 /
#: 0x0059C2F8): the flag and face mask IkeSimulationMgr::HandleGunshot traces a round with
TRACE_FLAGS, TRACE_MASK = 2, 1
#: how far the reticle point is looked for (metres); nothing hit -> this far along the view
AIM_RANGE = 1000.0
#: the reticle point is used only this far ahead of the shot origin along the view (metres)
AIM_AHEAD = 0.5

#: height above the eye, distance to the right, distance back (metres)
PRESETS = {
    "centered": dict(H=0.35, L=0.0, D=2.75),
    "ots": dict(H=0.20, L=0.45, D=2.25),
    "ots_left": dict(H=0.20, L=-0.45, D=2.25),
}


def _cam_tp_src(g, H, L, D, aim_cam):
    E, K = g["EYE"], g["LOOK"]
    mode = 1 if aim_cam else 0
    return f"""
cam_tp:                              ; a0 = SimCamera. v0=1 placed, v0=0 -> first-person placement
    addiu sp, sp, -0x40
    sd    ra, 0x30(sp)
    sq    s0, 0x20(sp)
    move  s0, a0
    lw    t0, 4(s0)                  ; followed SimHuman
    lw    t1, {g['MANNED']:#x}(t0)   ; IsManningGun(), inlined
    bnez  t1, zoomed                 ; a mounted gun keeps the first-person camera
    nop
    jal   ISSNIPER                   ; SimHuman::IsSniper: a sniper weapon, zoom above 1x --
    move  a0, t0                     ;   true from the first frame of the zoom animation
    andi  v0, v0, 0xff               ;   until it has fully zoomed back out
    bnez  v0, zoomed                 ; so a scope uses the first-person camera
    lw    t0, 4(s0)                  ; the soldier again (t0 is not preserved)
    lwc1  $f0, {g['FOV']:#x}(t0)     ; the soldier's field of view (his zoom) onto this
    swc1  $f0, 0x34(s0)              ;   camera, as the first-person placement does --
    swc1  $f0, 0xcc(s0)              ;   zooming stays in third person
    lwc1  $f0, {K:#x}(t0)            ; lx
    lwc1  $f1, {K + 4:#x}(t0)        ; ly
    lwc1  $f2, {K + 8:#x}(t0)        ; lz
    mul.s $f3, $f0, $f0
    mul.s $f4, $f1, $f1
    lui   at, 0x3500                 ; 4.8e-7, for a look straight up or down
    add.s $f3, $f3, $f4
    mtc1  at, $f4
    nop
    add.s $f3, $f3, $f4
    sqrt.s $f3, $f3                  ; |horizontal look|
    nop
    nop
{_li_f(4, L)}    nop
    div.s $f4, $f4, $f3              ; k = L / |h|   (right = (ly,-lx,0)/|h|)
    nop
    nop
{_li_f(5, D)}    nop
    mul.s $f6, $f1, $f4              ; w.x = ly*k - D*lx
    mul.s $f7, $f0, $f5
    sub.s $f6, $f6, $f7
    swc1  $f6, 0x10(sp)
    mul.s $f6, $f0, $f4              ; w.y = -(lx*k + D*ly)
    mul.s $f7, $f1, $f5
    add.s $f6, $f6, $f7
    neg.s $f6, $f6
    swc1  $f6, 0x14(sp)
{_li_f(6, H)}    mul.s $f7, $f2, $f5              ; w.z = -D*lz: the height goes on the start
    neg.s $f7, $f7
    swc1  $f7, 0x18(sp)
    lwc1  $f0, {E:#x}(t0)            ; sweep start = eye + H up, so a sphere at a prone or
    lwc1  $f1, {E + 4:#x}(t0)        ;   crouched eye that already touches the ground or
    lwc1  $f2, {E + 8:#x}(t0)        ;   cover does not stop the camera in the head
    add.s $f2, $f2, $f6
    swc1  $f0, 0x00(sp)
    swc1  $f1, 0x04(sp)
    swc1  $f2, 0x08(sp)
    move  a0, s0                     ; PlaceCamera(this, &start, &w, 1.0, 0)
    addiu a1, sp, 0x00
    addiu a2, sp, 0x10
    lui   at, 0x3f80
    mtc1  at, $f12
    jal   PLACE
    mtc1  zero, $f13
    jal   POSTPLACE                  ; camera >= floor + 0.25 (after cam_fix, when it is in)
    move  a0, s0
    lw    t0, 4(s0)
    lwc1  $f0, {K:#x}(t0)            ; view direction = soldier's look
    lwc1  $f1, {K + 4:#x}(t0)
    lwc1  $f2, {K + 8:#x}(t0)
    swc1  $f0, 0x8c(s0)
    swc1  $f1, 0x90(s0)
    swc1  $f2, 0x94(s0)
    swc1  $f0, 0xa4(s0)
    swc1  $f1, 0xa8(s0)
    swc1  $f2, 0xac(s0)
    addiu t1, zero, {mode}           ; SimCamera+0x74 (spare): 1 = free shots converge on
    sw    t1, 0x74(s0)               ;   the reticle point, 0 = they leave the eye parallel
    b     out
    addiu v0, zero, 1
zoomed:
    sw    zero, 0x74(s0)             ; first-person placement: shots as stock
    sw    zero, 0x78(s0)             ; and cam_fix eases out again from the eye
    addiu v0, zero, 0
out:
    ld    ra, 0x30(sp)
    lq    s0, 0x20(sp)
    jr    ra
    addiu sp, sp, 0x40
"""


def _aim_from_src(g):
    SH, S = g["UB_SH"], g["UB_SCR"]
    return f"""
aim_from:                            ; for SimCamera::GetLocation ahead of a locked-on shot
    lw    v1, 0x70(a0)
    addiu t0, zero, 1
    bne   v1, t0, af_ret
    addiu v0, a0, 0x10               ; not third person: the stock answer
    addiu sp, sp, -0x10              ; third person: aim from the stock shot origin, so the
    sd    ra, 0(sp)                  ;   round flies at the target from where it starts
    lw    t9, 0({SH})                ; the shooter (UpdateBurst's this)
    lb    a2, 0x1e7({SH})            ; the slot that fires
    lw    t9, {g['SHOOTFROM']:#x}(t9)  ; GetShootFromLocation
    move  a1, {SH}
    jalr  t9
    addiu a0, sp, {0x10 + S:#x}       ; into the caller's free temp
    ld    ra, 0(sp)
    addiu v0, sp, {0x10 + S:#x}
    addiu sp, sp, 0x10
af_ret:
    jr    ra
    nop
"""


def _floor_clamp_src(g):
    E = g["EYE"]
    return f"""
floor_clamp:                         ; a0 = SimCamera: cam.z = max(cam.z, floor + 0.25)
    addiu sp, sp, -0x40
    sd    ra, 0x30(sp)
    sq    s0, 0x20(sp)
    move  s0, a0
    lw    a0, 0x30(s0)               ; camera room (PlaceCamera just set it)
    beqz  a0, fc_out
    lw    t0, 4(s0)
    lwc1  $f0, 0x10(s0)
    lwc1  $f1, 0x14(s0)
    lwc1  $f2, {E + 8:#x}(t0)
    swc1  $f0, 0x00(sp)
    swc1  $f1, 0x04(sp)
    swc1  $f2, 0x08(sp)
    addiu a1, sp, 0x00
    addiu a2, sp, 0x0c               ; RSFloorFace*&
    jal   FLOOR
    addiu a3, sp, 0x10               ; float& height
    beqz  v0, fc_out
    lui   at, 0x3e80                 ; 0.25
    mtc1  at, $f1
    lwc1  $f0, 0x10(sp)
    lwc1  $f2, 0x18(s0)
    add.s $f0, $f0, $f1
    c.lt.s $f2, $f0
    nop
    bc1f  fc_out
    nop
    swc1  $f0, 0x18(s0)
fc_out:
    ld    ra, 0x30(sp)
    lq    s0, 0x20(sp)
    jr    ra
    addiu sp, sp, 0x40
"""


def _aim_base_src(g):
    """RSQuat::Set's stand-in ahead of a burst's free shots (frame: line +0, info +0x20,
    origin +0x80, aim +0x90, the vector to turn onto +0x9C, ra +0xA0, quat/forward +0xA8/+0xAC)."""
    SH, LV = g["UB_SH"], g["LINE_V"]
    ahead = _fbits(AIM_AHEAD)
    if ahead & 0xFFFF:
        raise ValueError("AIM_AHEAD must be a lui-only float")
    return f"""
aim_base:                            ; a0 quat, a1 forward, a2 look: the stock Set's arguments
    addiu sp, sp, -0xb0
    sd    ra, 0xa0(sp)
    sw    a0, 0xa8(sp)
    sw    a1, 0xac(sp)
    sw    a2, 0x9c(sp)               ; turn onto the look direction, as stock ...
    jal   LCINFO                     ; RSLineCollisionInfo, for the trace
    addiu a0, sp, 0x20
    lw    t0, 0x138({SH})            ; ... unless a player's soldier (control type 0)
    bnez  t0, ab_set
    lui   t0, %hi(SIMMGR)
    lw    t0, %lo(SIMMGR)(t0)
    beqz  t0, ab_set
    lw    t4, 0x444(t0)              ; GetSimCamera
    beqz  t4, ab_cam2
    lw    t5, 0x448(t0)              ; GetSimCamera2
    lw    t1, 4(t4)
    beq   t1, {SH}, ab_found
    nop
ab_cam2:
    beqz  t5, ab_set
    move  t4, t5
    lw    t1, 4(t4)
    bne   t1, {SH}, ab_set
ab_found:
    lw    t1, 0x70(t4)               ; ... follows him in third person ...
    addiu t2, zero, 1
    bne   t1, t2, ab_set
    lw    t1, 0x74(t4)               ; ... placed by cam_tp, converging (not zoomed, not "from the eye")
    bne   t1, t2, ab_set
    lw    a0, 0x30(t4)               ; the camera's room
    beqz  a0, ab_set
    lwc1  $f0, 0x10(t4)              ; the camera's centre line: from the camera C ...
    lwc1  $f1, 0x14(t4)
    lwc1  $f2, 0x18(t4)
    swc1  $f0, 0x00(sp)
    swc1  $f1, 0x04(sp)
    swc1  $f2, 0x08(sp)
    lwc1  $f0, 0x8c(t4)              ; ... along its view V, the soldier's look
    lwc1  $f1, 0x90(t4)
    lwc1  $f2, 0x94(t4)
    swc1  $f0, {LV:#x}(sp)
    swc1  $f1, {LV + 4:#x}(sp)
    swc1  $f2, {LV + 8:#x}(sp)
    addiu a1, sp, 0x00
    addiu a2, sp, 0x20
    move  a3, {SH}                   ; his own body does not stop it
    addiu t0, zero, {TRACE_FLAGS}    ; kIsGunshot: what a round would hit ...
    addiu t1, zero, {TRACE_MASK}     ; ... through faces a round passes (kGunshotTransparent)
{_li_f(12, AIM_RANGE)}    move  t3, zero
    jal   FLC                        ; RSSimRoom::FindLineCollision
    addiu t2, zero, 1
    lw    t9, 0({SH})
    lb    a2, 0x1e7({SH})            ; the slot that fires
    lw    t9, {g['SHOOTFROM']:#x}(t9)  ; GetShootFromLocation: the stock shot origin O
    move  a1, {SH}
    jalr  t9
    addiu a0, sp, 0x80
    lwc1  $f3, 0x54(sp)              ; t = info +0x34: distance to the hit, or the range
    lwc1  $f0, 0x00(sp)              ; aim = C + t*V - O (the reticle point P - O)
    lwc1  $f4, {LV:#x}(sp)
    lwc1  $f5, 0x80(sp)
    mul.s $f6, $f4, $f3
    sub.s $f0, $f0, $f5
    add.s $f0, $f0, $f6
    lwc1  $f1, 0x04(sp)
    mul.s $f7, $f0, $f4              ; aim . V
    swc1  $f0, 0x90(sp)
    lwc1  $f4, {LV + 4:#x}(sp)
    lwc1  $f5, 0x84(sp)
    mul.s $f6, $f4, $f3
    sub.s $f1, $f1, $f5
    add.s $f1, $f1, $f6
    lwc1  $f2, 0x08(sp)
    mul.s $f6, $f1, $f4
    swc1  $f1, 0x94(sp)
    add.s $f7, $f7, $f6
    lwc1  $f4, {LV + 8:#x}(sp)
    lwc1  $f5, 0x88(sp)
    mul.s $f6, $f4, $f3
    sub.s $f2, $f2, $f5
    add.s $f2, $f2, $f6
    swc1  $f2, 0x98(sp)
    mul.s $f6, $f2, $f4
    lui   at, {ahead >> 16:#06x}             ; {AIM_AHEAD} m
    mtc1  at, $f8
    add.s $f7, $f7, $f6
    c.lt.s $f8, $f7                  ; P lies ahead of the origin: turn onto it
    addiu t0, sp, 0x90
    bc1t  ab_aim
    nop
ab_set:
    lw    t0, 0x9c(sp)
ab_aim:
    lw    a0, 0xa8(sp)
    lw    a1, 0xac(sp)
    jal   QSET
    move  a2, t0
    ld    ra, 0xa0(sp)
    jr    ra
    addiu sp, sp, 0xb0
"""


def _patches(g, cam_a, lb):
    """{group: [(va, stock, new, note)]}"""
    jal = lambda t: 0x0C000000 | ((t >> 2) & 0x03FFFFFF)
    br = lambda op, rs, frm, to: (op << 26) | (rs << 21) | (((to - (frm + 4)) >> 2) & 0xFFFF)
    if g["key"] == "gr":
        return {
            "enable": [
                (0x003A7CE0, 0x00000000, 0x8E050070, "UpdateMovement: read the view in both paths"),
                (0x003A7CEC, 0x70002E28, 0x30A50001, "UpdateMovement: live player keeps view & 1"),
                (0x003A8BDC, 0xAE000070, 0x00000000, "ToggleCameraView: no snap back to first person"),
            ],
            "reticle": [
                (0x0039FA98, 0x0C0E6E80, 0x8C420070, "IsFirstPersonView: read the view"),
                (0x0039FA9C, 0x70402628, 0x2C420002, "IsFirstPersonView: first or third person"),
                (0x003AA3A8, 0x0C0E6E80, 0x8E020070, "UpdateFollower: read the view"),
                (0x003AA3AC, 0x00000000, 0x2C420002, "UpdateFollower: reticle update in third person"),
            ],
            "place": [
                (0x003AA184, 0x0C044CF4, jal(cam_a), "third person: jal cam_tp"),
                (0x003AA188, 0x00000000, 0x0200202D, "third person: a0 = camera"),
                (0x003AA18C, 0x0C044CF4, br(4, 2, 0x003AA18C, 0x003AA010), "zoomed: first-person placement"),
                (0x003AA190, 0x27A40078, 0x2604008C, "zoomed: a0 as the first-person path expects"),
                (0x003AA194, 0x8E040004, br(4, 0, 0x003AA194, 0x003AA238), "placed: skip the stock placement"),
                (0x003AA198, 0x8C990000, 0x00000000, "placed: nop"),
            ],
            "aim": [
                (0x003D2C3C, 0x0C0E27D8, jal(lb["aim_from"]), "locked-on shot (player 1) aims from the shot origin"),
                (0x003D2D0C, 0x0C0E27D8, jal(lb["aim_from"]), "locked-on shot (player 2) aims from the shot origin"),
                (g["AIMBASE"][0], g["AIMBASE"][1], jal(lb["aim_base"]),
                 "free shots turn onto the reticle point"),
            ],
            "default_tp": [
                (0x003A6DF0, 0x44806000, 0x24020001, "SimCamera starts in third person"),
                (0x003A6E04, 0xAE600070, 0xAE620070, "SimCamera starts in third person: view = 1"),
            ],
        }
    return {
        "enable": [
            (0x0038795C, 0x0000282D, 0x30650001, "UpdateMovement: live player keeps view & 1"),
            (0x003889AC, 0xAE000070, 0x00000000, "ToggleCameraView: no snap back to first person"),
        ],
        "reticle": [
            (0x0037E6E8, 0x0C0DE620, 0x8C420070, "IsFirstPersonView: read the view"),
            (0x0037E6EC, 0x0040202D, 0x2C420002, "IsFirstPersonView: first or third person"),
            (0x0038A06C, 0x0C0DE620, 0x8E020070, "UpdateFollower: read the view"),
            (0x0038A070, 0x00000000, 0x2C420002, "UpdateFollower: reticle update in third person"),
        ],
        "place": [
            (0x00389E38, 0x0C042994, jal(cam_a), "third person: jal cam_tp"),
            (0x00389E3C, 0x27A40088, 0x0200202D, "third person: a0 = camera"),
            (0x00389E40, 0x0C042994, br(4, 2, 0x00389E40, 0x00389CCC), "zoomed: first-person placement"),
            (0x00389E44, 0x27A40078, 0x00000000, "zoomed: nop"),
            (0x00389E48, 0x8E040004, br(4, 0, 0x00389E48, 0x00389F00), "placed: skip the stock placement"),
            (0x00389E4C, 0x8C990000, 0x920200DD, "placed: v0 as 0x389f00 expects"),
        ],
        "aim": [
            (0x003B22C8, 0x0C0D9E7C, jal(lb["aim_from"]), "locked-on shot (player 1) aims from the shot origin"),
            (0x003B2398, 0x0C0D9E7C, jal(lb["aim_from"]), "locked-on shot (player 2) aims from the shot origin"),
            (g["AIMBASE"][0], g["AIMBASE"][1], jal(lb["aim_base"]),
             "free shots turn onto the reticle point"),
        ],
        "default_tp": [
            (0x003869FC, 0x44806000, 0x24030001, "SimCamera starts in third person"),
            (0x00386A04, 0xAE400070, 0xAE430070, "SimCamera starts in third person: view = 1"),
            (0x00388768, 0xAE200070, 0x24050001, "after a cutscene: back to third person"),
            (0x0038876C, 0x8E250070, 0x00000000, "after a cutscene: nop"),
        ],
    }


def _stock_words(base, hexwords):
    digits = "".join(hexwords.split())
    if len(digits) % 8:
        raise ValueError("stock table is not a whole number of words")
    return {base + i // 2: int(digits[i:i + 8], 16)
            for i in range(0, len(digits), 8)}


_DEVCONS = {
    "gr": (
        "3c0c0004 3c020004 358c60d0 34426024 03ace823 019d6821 005d1021 fdb1ff70"
        "0080882d fdbeffe0 fdb7ffd0 24040002 fdb3ff90 fdb2ff80 fdb0ff60 0000902d"
        "fdbffff0 fdb6ffc0 fdb5ffb0 fdb4ffa0 0c103c14 ac400000 3c030004 8e240004"
        "34636020 8e370000 007d1821 27b00020 ac640000 0040f02d 03a0202d 0200282d"
        "0c10ac3a 8e330008 3c050002 27a40010 34a53000 0c10ac3a 02052821 8fc20000"
        "34420040 afc20000 3c020004 34426020 005d1021 8c420000 10400031 26360018"
        "27b50004 0017a040 3c030004 00000000 3c040004 34636024 34846024 007d1821"
        "009d2021 8c630000 00038900 38620001 03b18021 ac820000 0c10ac3e 0200202d"
        "0260402d 0240382d 02e0482d 0200202d 02c0282d 0c103a62 0000302d 26520001"
        "0200202d 0000282d 0000302d 0c10ac76 0000382d 02749821 0c10ac42 0200202d"
        "0c104758 0000202d 0000202d 0c1041cc 0000282d 02b18821 03c0202d 0c103ce8"
        "8e250000 3c030004 34636020 007d1821 8c630000 0243102b 1440ffd5 3c030004"
        "0000202d 0c1041cc 0000282d 3c0c0004 358c60d0 019d6821 ddbffff0 ddbeffe0"
        "ddb7ffd0 ddb6ffc0 ddb5ffb0 ddb4ffa0 ddb3ff90 ddb2ff80 ddb1ff70 ddb0ff60"
        "03e00008 03ace821"),
    "js": (
        "3c0c0004 3c020004 358c60d0 34426024 03ace823 019d6821 005d1021 fdb1ff70"
        "0080882d fdbeffe0 fdb7ffd0 24040002 fdb3ff90 fdb2ff80 fdb0ff60 0000902d"
        "fdbffff0 fdb6ffc0 fdb5ffb0 fdb4ffa0 0c05de88 ac400000 3c030004 8e240004"
        "34636020 8e370000 007d1821 27b00020 ac640000 0040f02d 03a0202d 0200282d"
        "0c0658fe 8e330008 3c050002 27a40010 34a53000 0c0658fe 02052821 8fc20000"
        "34420040 afc20000 3c020004 34426020 005d1021 8c420000 10400031 26360018"
        "27b50004 0017a040 3c030004 00000000 3c040004 34636024 34846024 007d1821"
        "009d2021 8c630000 00038900 38620001 03b18021 ac820000 0c065902 0200202d"
        "0260402d 0240382d 02e0482d 0200202d 02c0282d 0c05dc8e 0000302d 26520001"
        "0200202d 0000282d 0000302d 0c06593a 0000382d 02749821 0c065906 0200202d"
        "0c05e958 0000202d 0000202d 0c05e3c4 0000282d 02b18821 03c0202d 0c05df54"
        "8e250000 3c030004 34636020 007d1821 8c630000 0243102b 1440ffd5 3c030004"
        "0000202d 0c05e3c4 0000282d 3c0c0004 358c60d0 019d6821 ddbffff0 ddbeffe0"
        "ddb7ffd0 ddb6ffc0 ddb5ffb0 ddb4ffa0 ddb3ff90 ddb2ff80 ddb1ff70 ddb0ff60"
        "03e00008 03ace821"),
}
# sceVu0DropShadowMatrix is word-for-word the same in both games
_DROPSHADOW = (
    "46006406 10c0002a 46006bc6 c4a10000 c4a20004 46018242 c4a30008 46027a82"
    "3c013f80 44812800 46037182 e490000c 460009c7 e48f001c 460a4800 e48e002c"
    "46001107 e4870030 46001a07 46060000 e4840034 460179c2 46028102 e4880038"
    "46002801 46017042 e4870010 46027082 e4840004 46050141 46004a40 e4810020"
    "46005280 e4820024 46003180 e485003c 46038002 e4890000 460378c2 e48a0014"
    "e4860028 e4800008 03e00008 e4830018 c4a20000 c4a40004 46028142 c4a70008"
    "46047982 3c01bf80 44810800 46077202 ac80000c 46001247 ac80001c 46062800"
    "ac80002c 46047282 460022c7 46080000 460278c2 46078302 00000000 00000000"
    "46000843 46002941 46003181 46004201 46077b42 46000007 46027082 46048102"
    "460039c7 46000802 46050942 460308c2 46020882 e480003c 46090a42 e4850000"
    "46040902 e4830010 46060982 e4820020 460a0a82 e4890030 460b0ac2 e4840004"
    "460c0b02 e4860014 460d0b42 e48a0024 46080a02 e48b0034 46070842 e48c0008"
    "e48d0018 e4880028 03e00008 e4810038")


# the third cave: GR sceMcRename, JS lgAudWriteVag (the USB headset library's)
_CAVE_C_STOCK = {
    "gr": (
        "27bdff70 ffb50060 ffb40050 3c150057 0080a02d ffb30040 ffb20030 00a0982d"
        "ffb00010 00e0902d 8ea4f014 00c0802d ffbf0080 ffb60070 0c1046cc ffb10020"
        "04410003 3c02005f 1000003d 2402ff38 24560b40 8ec30024 14600005 00000000"
        "0c1046c0 8ea4f014 10000035 2402ff9c 12000006 00000000 82020000 10400003"
        "00000000 16400005 3c02005f 0c1046c0 8ea4f014 1000002a 2402ff2e 24030010"
        "24510bf0 ac540bf0 0200282d ae330004 ae230008 26240014 0c101c9c 240603ff"
        "3c10005f 0240282d 26100ba0 a2200413 0200202d 0c101c9c 24060020 2610ffe0"
        "0000202d ae300010 0c104758 a200003f 3c09005f 02c0202d 0220382d 25292100"
        "afa00000 2405000e 24060001 24080414 240a0004 0c10531c 0000582d 0040802d"
        "16000004 3c030057 24020013 10000003 ac62f010 0c1046c0 8ea4f014 0200102d"
        "dfbf0080 dfb60070 dfb50060 dfb40050 dfb30040 dfb20030 dfb10020 dfb00010"
        "03e00008 27bd0090"),
    "js": (
        "27bdffb0 3c030058 ffb50038 2475c614 8ea90000 3c028000 2408ffff ffb00010"
        "ffb10018 00e0882d ffb30028 0080982d ffb40030 00a0a02d ffb20020 00c0802d"
        "ffbf0040 11280041 3442000a 16000004 3c04005a 1000000b 2484f610 00000000"
        "12200006 3c020058 8e240000 8c43c604 0064182a 10600008 00000000 3c04005a"
        "2484f638 0c05adde 00000000 3c028000 1000002e 34420004 0c05e8c8 0120202d"
        "3c030058 2472c60c 0200282d 8e460000 acd3000c 24c40030 8e220000 acc20020"
        "0c05a8d6 8e260000 8e430000 3c040069 24050015 a0740012 24841240 0000302d"
        "240a0030 8e280000 0000582d 8e470000 2508003f afa00000 00084103 00e0482d"
        "0c05f5aa 00084100 3c04005a 1440000a 2484f670 8e420000 8c430020 8c500000"
        "ae230000 0c05e8c0 8ea40000 10000007 0200102d 00000000 0c05adde ae200000"
        "0c05e8c0 8ea40000 3c028000 dfb00010 dfb10018 dfb20020 dfb30028 dfb40030"
        "dfb50038 dfbf0040 03e00008 27bd0050"),
}

#: sites an earlier version hooked (the Gunshot origin moved onto the camera line, which let
#: rounds clear cover the soldier was behind). Nothing writes them now; they stay in the stock
#: table so a disc patched by that version gets them put back.
RETIRED = {
    "gr": ((0x003D2DE8, 0x72A02628), (0x003D2DEC, 0x0C0D6580)),
    "js": ((0x003B2474, 0x0200202D), (0x003B2478, 0x0C053838)),
}


def _stock_table(game):
    g = GAMES[game]
    t = _stock_words(g["CAVE_A"], _DEVCONS[game])
    t.update(_stock_words(g["CAVE_B"], _DROPSHADOW))
    t.update(_stock_words(g["CAVE_C"], _CAVE_C_STOCK[game]))
    for rows in _patches(g, g["CAVE_A"], {"aim_from": g["CAVE_A"],
                                          "aim_base": g["CAVE_B"]}).values():
        for va, stock, _new, _note in rows:
            t[va] = stock
    for va, stock in RETIRED[game]:
        t[va] = stock
    return t


GR_STOCK = _stock_table("gr")
JS_STOCK = _stock_table("js")


# ---------------------------------------------------------------------------
# Soldiers the camera leaves stay visible
# ---------------------------------------------------------------------------
#
# SimCamera::CameraBeginScene hides the soldier a first-person camera follows
# (RSSimController::Hide -> Actor::SetHidden(1), bit 3 of the actor's flags)
# after noting at SimCamera+0xC whether he was visible. CameraEndScene was
# meant to show him again but its body was compiled out: it looks the soldier
# up and does nothing. So the hide never ends. Savestates show it: in stock
# split screen both players' soldiers are hidden for good, so neither player
# ever sees the other; every Ghost a player has switched away from stays
# invisible; and a third-person camera can never show a soldier that was
# followed in first person for even one frame. Each camera's scene is drawn
# between the two calls (IkeSimulationMgr::RenderUpdate: BeginScene,
# DrawCamera, EndScene, per camera), so restoring the soldier in EndScene
# hides him only from his own first-person view.
UNHIDE = {
    "gr": dict(HOOK=0x003A81FC, HOOK_STOCK=0x0C0E3CE8, LEADER=0x0038F3A0,
               CAVE=0x00418900, STOCK=(
                   "00031e00 5460fff8 24a50001 10000006 24020400 2e060400 27b30030 3c16005f"
                   "3c14005f 24020400 50a20001 a2400413 240203ff 02a0202d 0046800a ae550010"
                   "0200282d 0c1050e0 ae50000c 2690ed40")),
    "js": dict(HOOK=0x00387E7C, HOOK_STOCK=0x0C0DB374, LEADER=0x0036CDD0,
               CAVE=0x001813A0, STOCK=(
                   "24a50001 00000000 28a20400 1040000d 02251021 02452021 90430000 a0830014"
                   "00031e00 5460fff8 24a50001 10000006 24020400 2e060400 27b30030 3c160062"
                   "3c140061 24020400 50a20001 a2400413")),
}
_UNHIDE_SRC = """
unhide:                             ; jal from CameraEndScene; a0 = SimCamera
    addiu sp, sp, -0x20
    sd    ra, 0x10(sp)
    sq    s0, 0(sp)
    jal   {LEADER:#x}               ; SimCamera::GetLeader, the call it replaces
    move  s0, a0
    beqz  v0, uh_out
    lbu   t0, 0xc(s0)               ; was he visible before CameraBeginScene hid him?
    beqz  t0, uh_out
    nop
    lw    a0, 0x34(v0)              ; his actor
    lw    t9, 0(a0)
    lw    t9, 0xc(t9)               ; Actor::SetHidden, as RSSimController::Hide calls it
    jalr  t9
    move  a1, zero
uh_out:
    ld    ra, 0x10(sp)
    lq    s0, 0(sp)
    jr    ra
    addiu sp, sp, 0x20
"""
for _g, _t in (("gr", GR_STOCK), ("js", JS_STOCK)):
    _u = UNHIDE[_g]
    _t.update(_stock_words(_u["CAVE"], _u["STOCK"]))
    _t[_u["HOOK"]] = _u["HOOK_STOCK"]


# ---------------------------------------------------------------------------
# The soldier a camera follows is drawn when the camera is away from his eye
# ---------------------------------------------------------------------------
#
# SimHuman::UpdateVisibility (GR 0x003DF790; JS loop at 0x003BF3D8) keeps a
# per-camera "visible in camera N" byte (GR +0x770, JS +0x7C8) that
# SimHuman::Render requires. For every camera it zeroes the byte of the
# camera's own leader -- whatever the view -- so a soldier is never drawn by
# the camera following him, third person included (a third-person savestate
# shows the camera 2.33 m behind him and his actor not hidden). The hook
# replaces that GetLeader call: ``xleader`` answers the leader only when the
# camera is in first person or within 0.5 m of his eye (a wall pushed it in,
# or a mounted gun), and 0 otherwise, so he is drawn.
XLEADER = {
    "gr": dict(HOOK=0x003DFDCC, HOOK_STOCK=0x0C0E3CE8, CAVE=0x002D5100, EYE=0x478,
               STOCK=("2404ffff 8fa503c0 aca40010 afa00184 1000001b 00000000 72202628 8fa60184"
                      "70c02e28 0c0b50e8 00000000 afa203c4 8fa203c4 8c460000 afa605c0 8fa705c0"
                      "afa705c4 8fa405c4 24050003 14850008 00000000 72202628 8fa50184 0c0b50e8"
                      "00000000 afa20180 1000000d 00000000")),   # dead NewPS2Shortcut::RelinkBravo
    "js": dict(HOOK=0x003BF7A4, HOOK_STOCK=0x0C0DB374, CAVE=0x002A2A2C, EYE=0x49C,
               STOCK=("00000000 0c0a7c18 0080282d 14400008 24040001 8e040024 24050003 24060008"
                      "0c0a8230 24070002 1000000a 00000000 0c0a7c18 24050002 14400006 00000000"
                      "8e040024 24050003 24060009 0c0a8230 24070002 dfbf0040 7bb30030 7bb20020"
                      "7bb10010 7bb00000 03e00008 27bd0050")),   # tail of RelinkBravo, after the orders
}
_XLEADER_SRC = """
xleader:                            ; a0 = SimCamera -> v0 = the soldier to leave undrawn, or 0
    lw    v0, 4(a0)                 ; SimCamera::GetLeader, inlined
    beqz  v0, xl_out
    lw    t0, 0x70(a0)              ; view
    beqz  t0, xl_out                ; first person: never draw him
    lwc1  $f0, 0x10(a0)             ; camera position - his eye
    lwc1  $f1, {EYE:#x}(v0)
    lwc1  $f2, 0x14(a0)
    lwc1  $f3, {EYE4:#x}(v0)
    sub.s $f0, $f0, $f1
    lwc1  $f4, 0x18(a0)
    sub.s $f2, $f2, $f3
    lwc1  $f5, {EYE8:#x}(v0)
    mul.s $f0, $f0, $f0
    sub.s $f4, $f4, $f5
    mul.s $f2, $f2, $f2
    lui   at, 0x3e80                ; (0.5 m)^2
    add.s $f0, $f0, $f2
    mul.s $f4, $f4, $f4
    mtc1  at, $f1
    add.s $f0, $f0, $f4
    c.lt.s $f0, $f1                 ; camera at his eye: leave him undrawn
    nop
    bc1t  xl_out
    nop
    move  v0, zero                  ; camera away from him: draw him
xl_out:
    jr    ra
    nop
"""
for _g, _t in (("gr", GR_STOCK), ("js", JS_STOCK)):
    _x = XLEADER[_g]
    _t.update(_stock_words(_x["CAVE"], _x["STOCK"]))
    _t[_x["HOOK"]] = _x["HOOK_STOCK"]


# ---------------------------------------------------------------------------
# In third person the soldier holds his weapon up, and his muzzle flash shows
# ---------------------------------------------------------------------------
#
# HumanMotion::UpdateArms (GR 0x00357FB0, JS 0x003341C0) puts the arms in the
# aiming poses -- rifle and pistol, standing, crouched and walking -- only while
# SimHuman::IsZooming (GR 0x00358F40 = byte +0x4EE, JS 0x003350D0 = +0x50F)
# answers yes; otherwise they hang at the carry ("low ready"), and after a shot
# only a 1.3 s hold keeps them up. The AI zooms in whenever it aims
# (EngageThreatBehavior::StartAiming), so AI soldiers raise their weapons; a
# player in third person never zooms -- zooming is what sends the camera back
# to first person -- so his soldier never did. Its 7 IsZooming calls (a0 = the
# soldier in every delay slot) go through ``tp_zoom``: a player's soldier
# (control type +0x138 = 0) answers yes, everyone else as before.
#
# IkeEffectsMgr::DrawEffects (GR 0x00252310; JS loop at 0x0023FE88) skips the
# muzzle flash of every soldier for whom ISimHuman +0x12C / +0x154
# (SimHuman::IsHumanAvatar) is true -- the flash of a first-person view -- so
# no player's flash was ever drawn, in third person or by the other half of a
# split screen. Its jalr goes through ``tp_flash``: a soldier drawn in view 0
# or 1 (the per-camera bytes xleader keeps, SimHuman +0x770 / +0x7C8; the flash
# holds SimHuman + 0x1B0) gets his flash drawn; one drawn in neither -- a
# player in first person, the scope included -- is asked as before.
#
# Leaning (peeking) is a full-body motion that HumanMotion::ChoosePeekMotion
# (GR 0x003603F0, JS 0x0033BEE0) picks by weapon: rifles, machine guns and
# launchers lean with the weapon raised and the arm update switched off
# (HumanMotion +0x6A); a pistol gets its own lean with the pistol lowered and
# the arm update left on, and the lean's arms win -- so a pistol never came up
# while leaning. Two words per game send the pistol down the rifle's path (its
# pistol flag cleared, the rifle flag kept), so it leans raised and forward.
TPPOSE = {
    "gr": dict(CAVE=0x0040D9B0, ISZOOM=0x00358F40, VIS=0x770 - 0x1B0,
               ZOOM_SITES=(0x003584B0, 0x00358640, 0x00358784, 0x003588F0,
                           0x00358A7C, 0x00358B5C, 0x00358E2C), ZOOM_STOCK=0x0C0D63D0,
               FLASH_SITE=0x002525C8,
               PEEK=((0x00360448, 0x2FDE0001, 0x0000F02D, "move fp, zero: no pistol lean"),
                     (0x00360484, 0x70009628, 0x00000000, "nop: a pistol keeps the rifle flag")),
               STOCK=("27bdff80 ffb60060 ffb00000 00a0b02d ffbf0070 0000802d ffb40040 ffb30030"
                      "ffb20020 ffb10010 ffb50050 8c950004 8c940000 12a0000f 8c910008 24930018"
                      "00149040 00000000 0200382d 0220402d 02c0202d 0260282d 0000302d 0c103a62"
                      "0280482d 26100001 0215102b 1440fff6 02328821 dfbf0070 dfb60060 dfb50050"
                      "dfb40040 dfb30030 dfb20020 dfb10010 dfb00000 03e00008 27bd0080")),  # sceDevConsRef
    "js": dict(CAVE=0x00176260, ISZOOM=0x003350D0, VIS=0x7C8 - 0x1B0,
               ZOOM_SITES=(0x00334690, 0x00334814, 0x0033494C, 0x00334ABC,
                           0x00334C3C, 0x00334D10, 0x00334FEC), ZOOM_STOCK=0x0C0CD434,
               FLASH_SITE=0x0023FEA8,
               PEEK=((0x0033BF30, 0x2C7E0004, 0x2C5E0005, "sltiu fp, v0, 5: types 0-4 lean raised"),
                     (0x0033BF34, 0x2E520001, 0x0000902D, "move s2, zero: no pistol lean")),
               STOCK=("27bdff80 ffb60060 ffb00000 00a0b02d ffbf0070 0000802d ffb40040 ffb30030"
                      "ffb20020 ffb10010 ffb50050 8c950004 8c940000 12a0000f 8c910008 24930018"
                      "00149040 00000000 0200382d 0220402d 02c0202d 0260282d 0000302d 0c05dc8e"
                      "0280482d 26100001 0215102b 1440fff6 02328821 dfbf0070 dfb60060 dfb50050"
                      "dfb40040 dfb30030 dfb20020 dfb10010 dfb00000 03e00008 27bd0080")),  # sceDevConsRef
}
JALR_T9 = 0x0320F809
_TPPOSE_SRC = """
tp_zoom:                            ; a0 = SimHuman -> v0: arms in the aiming poses
    lw    v0, 0x138(a0)             ; control type: 0 = a player
    beqz  v0, tz_up
    nop
    j     {ISZOOM:#x}               ; SimHuman::IsZooming, as the call did
    nop
tz_up:
    jr    ra
    li    v0, 1
tp_flash:                           ; a0 = SimHuman + 0x1B0, t9 = its IsHumanAvatar -> v0 = 1: no flash
    lbu   v0, {VIS:#x}(a0)          ; drawn in view 0 ...
    lbu   v1, {VIS1:#x}(a0)         ; ... or view 1
    or    v0, v0, v1
    beqz  v0, tf_ask
    nop
    jr    ra
    move  v0, zero                  ; drawn: so is his flash
tf_ask:
    jr    t9                        ; drawn nowhere: as before
    nop
"""
for _g, _t in (("gr", GR_STOCK), ("js", JS_STOCK)):
    _p = TPPOSE[_g]
    _t.update(_stock_words(_p["CAVE"], _p["STOCK"]))
    for _va in _p["ZOOM_SITES"]:
        _t[_va] = _p["ZOOM_STOCK"]
    _t[_p["FLASH_SITE"]] = JALR_T9
    for _va, _st, _new, _n in _p["PEEK"]:
        _t[_va] = _st


def tppose_edits(game):
    """[(va, value, stock, note)]: aiming arms and the muzzle flash in third person."""
    p = TPPOSE[game]
    stock = GR_STOCK if game == "gr" else JS_STOCK
    words, labels = assemble(_TPPOSE_SRC.format(ISZOOM=p["ISZOOM"], VIS=p["VIS"], VIS1=p["VIS"] + 1),
                             p["CAVE"])
    if len(words) > len("".join(p["STOCK"].split())) // 8:
        raise ValueError("%s: third-person pose routines outgrow their cave" % game)
    out = [(p["CAVE"] + 4 * i, w, stock[p["CAVE"] + 4 * i],
            "third-person camera: aiming arms, muzzle flash") for i, w in enumerate(words)]
    for va in p["ZOOM_SITES"]:
        out.append((va, assemble("jal %#x" % labels["tp_zoom"], va)[0][0], p["ZOOM_STOCK"],
                    "third-person camera: a player's arms aim as a zoomed soldier's"))
    out.append((p["FLASH_SITE"], assemble("jal %#x" % labels["tp_flash"], p["FLASH_SITE"])[0][0],
                JALR_T9, "third-person camera: a drawn soldier's muzzle flash is drawn"))
    for va, st, new, note in p["PEEK"]:
        out.append((va, new, st, "third-person camera: a pistol leans raised -- " + note))
    return out


def xleader_edits(game):
    x = XLEADER[game]
    stock = GR_STOCK if game == "gr" else JS_STOCK
    words, _ = assemble(_XLEADER_SRC.format(EYE=x["EYE"], EYE4=x["EYE"] + 4,
                                            EYE8=x["EYE"] + 8), x["CAVE"])
    if len(words) > len("".join(x["STOCK"].split())) // 8:
        raise ValueError("%s: xleader outgrows its cave" % game)
    out = [(x["CAVE"] + 4 * i, w, stock[x["CAVE"] + 4 * i],
            "third-person camera: draw the soldier it follows") for i, w in enumerate(words)]
    out.append((x["HOOK"], assemble("jal %#x" % x["CAVE"], x["HOOK"])[0][0], x["HOOK_STOCK"],
                "third-person camera: visibility asks xleader, not GetLeader"))
    return out


def unhide_edits(game):
    """[(va, value, stock, note)] making CameraEndScene show the soldier again."""
    u = UNHIDE[game]
    stock = GR_STOCK if game == "gr" else JS_STOCK
    words, _ = assemble(_UNHIDE_SRC.format(**u), u["CAVE"])
    out = [(u["CAVE"] + 4 * i, w, stock[u["CAVE"] + 4 * i],
            "soldiers stay visible: routine") for i, w in enumerate(words)]
    out.append((u["HOOK"], assemble("jal %#x" % u["CAVE"], u["HOOK"])[0][0],
                u["HOOK_STOCK"], "soldiers stay visible: CameraEndScene shows him again"))
    return out


# ---------------------------------------------------------------------------
# Third person: show when cover blocks the shot
# ---------------------------------------------------------------------------
#
# Rounds leave the soldier's eye and fly at P, the point under the reticle
# (``aim_base``). When the camera sees over cover his eye is behind, the
# reticle sits on open ground while the rounds hit the cover. This shows it.
# Just before the reticle is drawn, ``tp_mark`` checks aim_base's conditions
# for that view's soldier (third person, placed by cam_tp and converging, a
# player's soldier) and makes one line trace a frame, the two in turn: the
# camera line (aim_base's trace, giving P) and the round's own line from the
# stock origin O towards P, from the room HandleGunshot traces from. P, the hit
# and the verdict are kept per view (64 bytes at the end of cave E) and
# cleared whenever the conditions fail. If the round's line meets anything
# more than 0.5 m short of P -- scenery or another soldier; the soldier himself
# is ignored -- the reticle itself is drawn amber where the round would hit,
# over any friend/foe colour; if that point is off screen, it is drawn amber
# in its own place, so there is always one reticle.
#
# The reticle is ReticuleDisplay (a UIQuadModel: one GIF REGLIST packet, 5
# quads of 2 triangles, RGBAQ + UV/XYZ2 x 3 each, 7 quadwords a quad).
# ReticuleDisplay::Draw (0x0025EBE0) ends with UIModel::Draw(this), which
# UIPacket::AddModel copies into the frame's packet; the hook replaces that
# call. When blocked, it saves the model's packet, writes amber into its
# RGBAQs, moves every vertex by the hit's offset from the view's centre
# (projected with the reticle's own world->screen call 0x0041EAF0 for that
# view) when that keeps it on screen, draws it once and puts the packet back,
# so nothing the game set is left changed. A packet of another shape (sniper,
# binoculars) is drawn as is. (The first build drew the reticle in place and a
# 5/8 copy at the hit; in split screen that copy landed in the wrong half.) Cost: one line trace a frame per
# third-person view (the same trace a round makes: 20k-1.1M EE instructions in
# the interpreter on the test saves, dense scenery costing most) and, while
# blocked, one projection.
#
# Ghost Recon's reticle is the same model with the same packet (tag and 5 quads
# read from savestates), but its ReticuleDisplay::Draw (0x0027D190) calls
# UIPacket::AddModel(packet, this) itself instead of UIModel::Draw(this): the
# hook replaces that jal and puts this in a0 from its delay slot (HOOK_DELAY),
# and UIModel::Draw (0x003A1790, AddModel on UIPacket::Get(), the same packet)
# stands in for the call. Its split number is +0xC8 (Jungle Storm +0xD8), set
# the same way: 0 for a view on its own, -1 / 1 the first / second player's half.
BLOCKED = {
    "gr": dict(
        HOOK=0x0027D538, HOOK_STOCK=0x0C145CB8,   # ReticuleDisplay::Draw: jal UIPacket::AddModel(packet, this)
        HOOK_DELAY=(0x0027D53C, 0x00000000),      # its delay slot: a0 = this (a1) for the stand-in
        UIDRAW=0x003A1790,                        # UIModel::Draw: UIPacket::AddModel(UIPacket::Get(), this)
        PROJ=0x00459240,                          # CGraphicAPI::TransformVertToScreen (api, view, out, in, 0)
        GFX=0x00630B40,                           # its graphics API is *this + 0x100, as the reticle loads it
        SHOOTROOM=0x158,                          # IkeSimController::GetShootFromSimRoom
        SPLIT=0xC8,                               # ReticuleDisplay: split number (ReticuleSetSplitNumber)
        CAVE_D=0x0040F478, CAVE_D_BYTES=904,      # sceDmaSendN, sceDmaSendI, sceDmaRecv, sceDmaRecvN: unreferenced
        CAVE_E=0x0042A638, CAVE_E_BYTES=572,      # scePadInfoAct, scePadInfoComb: unreferenced
        CAVE_NAMES=("sceDmaSendN..sceDmaRecvN (unreferenced)", "scePadInfoAct/Comb (unreferenced)"),
        STOCK_D=(
            "27bdffa0 ffb40040 ffb30030 00c0a02d ffb10010 00a0982d ffb00000 3c110100"
            "ffbf0050 0080802d ffb20020 8e020000 30420100 10400018 3c120058 2631ffff"
            "06210011 00000000 0c0403cc 264477e8 8e040000 00041202 30420001 1040000a"
            "00000000 2405feff 00851824 0000102d 0060202d 00000000 00000000 1440fffa"
            "00000000 ae030000 8e020000 30420100 1440ffeb 2631ffff 3c02ffff 8e030010"
            "3442ffff 54620001 ae130010 8e020000 2403fff3 ae140020 00431024 dfbf0050"
            "34420101 dfb40040 ae020000 dfb30030 dfb20020 dfb10010 dfb00000 03e00008"
            "27bd0060 00000000 27bdffa0 ffb40040 ffb30030 00c0a02d ffb10010 00a0982d"
            "ffb00000 3c110100 ffbf0050 0080802d ffb20020 8e020000 30420100 10400018"
            "3c120058 2631ffff 06210011 00000000 0c0403cc 264477e8 8e040000 00041202"
            "30420001 1040000a 00000000 2405feff 00851824 0000102d 0060202d 00000000"
            "00000000 1440fffa 00000000 ae030000 8e020000 30420100 1440ffeb 2631ffff"
            "3c02ffff 8e030010 3442ffff 54620001 ae130010 8e020000 2403fff3 ae140020"
            "00431024 dfbf0050 34420109 dfb40040 ae020000 dfb30030 dfb20020 dfb10010"
            "dfb00000 03e00008 27bd0060 00000000 27bdffc0 ffb10010 ffb00000 3c110100"
            "ffbf0030 0080802d ffb20020 8e020000 30420100 10400018 3c120058 2631ffff"
            "06210011 00000000 0c0403cc 264477e8 8e040000 00041202 30420001 1040000a"
            "00000000 2405feff 00851824 0000102d 0060202d 00000000 00000000 1440fffa"
            "00000000 ae030000 8e020000 30420100 1440ffeb 2631ffff 8e020000 2403fff3"
            "2404fffe ae000020 00431024 dfbf0030 34420004 dfb20020 00441024 dfb10010"
            "34420100 ae020000 dfb00000 03e00008 27bd0040 00000000 27bdffa0 ffb40040"
            "ffb30030 00c0a02d ffb10010 00a0982d ffb00000 3c110100 ffbf0050 0080802d"
            "ffb20020 8e020000 30420100 10400018 3c120058 2631ffff 06210011 00000000"
            "0c0403cc 264477e8 8e040000 00041202 30420001 1040000a 00000000 2405feff"
            "00851824 0000102d 0060202d 00000000 00000000 1440fffa 00000000 ae030000"
            "8e020000 30420100 1440ffeb 2631ffff 3c02ffff 8e030010 3442ffff 54620001"
            "ae130010 8e020000 2403fff3 2404fffe ae140020 00431024 dfbf0050 00441024"
            "dfb40040 34420100 dfb30030 ae020000 dfb20020 dfb10010 dfb00000 03e00008"
            "27bd0060 00000000"),
        STOCK_E=(
            "0080402d 24030070 2404001c 71031818 00a42018 27bdffd0 3c02005f ffb10010"
            "ffb00000 24422390 ffbf0020 00c0882d 00832021 00441021 8c430010 10600032"
            "00e0802d 0c10a8da 0100202d 0040202d 90850072 24020001 14a2002c 0000102d"
            "90820064 2c420002 14400028 0000102d 9083006a 0223102a 10400023 2402ffff"
            "16220003 24020002 10000020 0060102d 12020011 2a020003 10400005 24020003"
            "12050009 0000102d 10000019 dfbf0020 1202000d 24020004 1202000f 0000102d"
            "10000013 dfbf0020 00111880 00831821 1000000e 90620030 00111880 00831821"
            "1000000a 90620031 00111880 00831821 10000006 90620032 00111880 00831821"
            "10000002 90620033 0000102d dfbf0020 dfb10010 dfb00000 03e00008 27bd0030"
            "0080402d 24030070 2404001c 71031818 00a42018 27bdffd0 3c02005f ffb10010"
            "ffb00000 24422390 ffbf0020 00c0882d 00832021 00441021 8c430010 10600031"
            "00e0802d 0c10a8da 0100202d 0040202d 90830072 24020001 1462002b 0000102d"
            "90820064 2c420002 14400027 0000102d 2405ffff 16250003 9082006b 10000023"
            "dfbf0020 0222102a 5040001f 0000102d 52000011 00111880 1e000005 00000000"
            "12050009 0000102d 10000018 dfbf0020 1203000c 24020002 1202000e 0000102d"
            "10000012 dfbf0020 00111880 00831821 1000000d 90620040 00831821 1000000a"
            "90620041 00111880 00831821 10000006 90620042 00111880 00831821 10000002"
            "90620043 0000102d dfbf0020 dfb10010 dfb00000 03e00008 27bd0030"),
    ),
    "js": dict(
        HOOK=0x0025EF20, HOOK_STOCK=0x0C05686C,   # ReticuleDisplay::Draw: jal UIModel::Draw (a0 = this)
        UIDRAW=0x0015A1B0,                        # UIModel::Draw: UIPacket::AddModel(packet, this)
        PROJ=0x0041EAF0,                          # world -> GS (api, view, out, in, 0), as the reticle calls it
        GFX=0x0067CF40,                           # its graphics API is *this + 0x100
        SHOOTROOM=0x158,                          # SimHuman: GetShootFromSimRoom (IkeSimController +0x158)
        SPLIT=0xD8,                               # ReticuleDisplay: split number
        CAVE_D=0x005544B0, CAVE_D_BYTES=784,      # three unreferenced lgAud-library functions
        CAVE_E=0x00554950, CAVE_E_BYTES=600,      # three more, all unreferenced
        STOCK_D=(
            "27bdffc0 3c030058 ffb10018 2471c614 8e230000 3c028000 2406ffff ffb00010"
            "ffb30028 00a0982d 0080802d 0060202d ffb20020 3442000a 10660020 ffbf0030"
            "0c05e8c8 00000000 3c030058 2472c60c 3c040069 8e470000 0000302d 24050012"
            "24080020 acf0000c 24841240 00e0482d 240a0030 0000582d 0c05f5aa afa00000"
            "54400009 3c04005a 8e420000 8c430020 8c500000 ae630000 0c05e8c0 8e240000"
            "10000006 0200102d 0c05adde 2484f738 0c05e8c0 8e240000 3c028000 dfb00010"
            "dfb10018 dfb20020 dfb30028 dfbf0030 03e00008 27bd0040 27bdffc0 3c030058"
            "ffb30028 2473c614 8e630000 3c028000 2406ffff ffb10018 ffb20020 0080902d"
            "ffb00010 00a0882d ffbf0030 10660033 3442000a 16200008 00000000 3c04005a"
            "0c05adde 2484f690 3c028000 1000002b 34420004 00000000 0c05e8c8 0060202d"
            "3c030058 2470c60c 3c040069 8e020000 24841240 2405000b 0000302d ac52000c"
            "24080030 6a230007 6e230000 6a27000f 6e270008 b0430027 b4430020 b047002f"
            "b4470028 240a0030 afa00000 0000582d 8e070000 0c05f5aa 00e0482d 3c04005a"
            "14400009 2484f6b8 8e020000 8e640000 9443002c 8c500000 0c05e8c0 a623000c"
            "10000006 0200102d 0c05adde 00000000 0c05e8c0 8e640000 3c028000 dfb00010"
            "dfb10018 dfb20020 dfb30028 dfbf0030 03e00008 27bd0040 27bdffc0 3c030058"
            "ffb30028 2473c614 8e630000 3c028000 2406ffff ffb10018 ffb20020 0080902d"
            "ffb00010 00a0882d ffbf0030 10660031 3442000a 16200008 00000000 3c04005a"
            "0c05adde 2484f6d8 3c028000 10000029 34420004 00000000 0c05e8c8 0060202d"
            "3c030058 2470c60c 3c040069 8e020000 24841240 2405000c 0000302d ac52000c"
            "24080030 6a230007 6e230000 6a27000f 6e270008 b0430027 b4430020 b047002f"
            "b4470028 240a0030 afa00000 0000582d 8e070000 0c05f5aa 00e0482d 3c04005a"
            "14400007 2484f6b8 8e020000 8e640000 0c05e8c0 8c500000 10000006 0200102d"
            "0c05adde 00000000 0c05e8c0 8e640000 3c028000 dfb00010 dfb10018 dfb20020"
            "dfb30028 dfbf0030 03e00008 27bd0040"),
        STOCK_E=(
            "27bdffd0 3c030058 ffb10018 2471c614 8e230000 3c028000 2405ffff ffb00010"
            "ffb20020 3442000a 0080802d 0060202d 1065001e ffbf0028 0c05e8c8 00000000"
            "3c030058 2472c60c 3c040069 8e470000 24050006 0000302d 24080020 acf0000c"
            "24841240 00e0482d 240a0020 0000582d 0c05f5aa afa00000 14400007 3c04005a"
            "8e420000 8e240000 0c05e8c0 8c500000 10000006 0200102d 0c05adde 2484f798"
            "0c05e8c0 8e240000 3c028000 dfb00010 dfb10018 dfb20020 dfbf0028 03e00008"
            "27bd0030 00000000 27bdffd0 3c030058 ffb10018 2471c614 8e230000 3c028000"
            "2405ffff ffb00010 ffb20020 3442000a 0080802d 0060202d 1065001e ffbf0028"
            "0c05e8c8 00000000 3c030058 2472c60c 3c040069 8e470000 24050007 0000302d"
            "24080020 acf0000c 24841240 00e0482d 240a0020 0000582d 0c05f5aa afa00000"
            "14400007 3c04005a 8e420000 8e240000 0c05e8c0 8c500000 10000006 0200102d"
            "0c05adde 2484f7c0 0c05e8c0 8e240000 3c028000 dfb00010 dfb10018 dfb20020"
            "dfbf0028 03e00008 27bd0030 00000000 27bdffd0 3c030058 ffb10018 2471c614"
            "8e230000 3c028000 2405ffff ffb00010 ffb20020 3442000a 0080802d 0060202d"
            "1065001e ffbf0028 0c05e8c8 00000000 3c030058 2472c60c 3c040069 8e470000"
            "24050011 0000302d 24080020 acf0000c 24841240 00e0482d 240a0020 0000582d"
            "0c05f5aa afa00000 14400007 3c04005a 8e420000 8e240000 0c05e8c0 8c500000"
            "10000006 0200102d 0c05adde 2484f7e8 0c05e8c0 8e240000 3c028000 dfb00010"
            "dfb10018 dfb20020 dfbf0028 03e00008 27bd0030 00000000"),
    ),
}
#: the blocked colour, GS scale (0x80 = full): amber, (255, 160, 0) -- not the reticle's
#: red (0.94, 0.24, 0.24), green (0x4E, 0x9F, 0x2E), blue (0x5F, 0x84, 0xC3) or civilian grey
BLOCKED_RGB = (0x80, 0x50, 0x00)
#: the reticle moves to the hit only when it stays on screen: within MARK_X GS units of the view's
#: centre sideways and MARK_Y up/down (MARK_Y_SPLIT in half of a split screen; a view is 640 x 448
#: GS units, 640 x 224 split, and the reticle is 32 across). The projection (0x0041EAF0) answers
#: in the view's own frame, centred on (2048, 2048); the reticle's quads are in the frame of the
#: whole screen (a split-screen view's centre is 112 units above or below), so the reticle is
#: moved by the projected point's offset from (2048, 2048).
MARK_X, MARK_Y, MARK_Y_SPLIT = 300, 200, 95
#: per-view state kept at the end of cave E (two views, 32 bytes each; zero on the disc)
STATE_BYTES = 64
#: the reticle's packet: GIF tag words 1-3 (NREG 14, REGLIST; RGBAQ, then UV/XYZ2 x 3, twice)
_RET_TAG = (0xE4000000, 0x14343431, 0x00434343)


def _mark_srcs(g, b):
    """(part in cave D, part in cave E).

    Frame: line +0, info +0x20, O +0x80, H (x, y, z, 1) +0xB0, projected H +0xC0, V +0xD0,
    reach +0xDC, mark flag +0xE0, quads +0xE4, room +0xE8, which trace +0xEC, the saved packet
    +0x100 (36 quadwords), ra/s0-s4 +0x340. State per view, 32 bytes at STATE + 32 * view:
    P +0, its camera +0xC (0 = none), H +0x10, phase byte +0x1C, blocked byte +0x1D."""
    LV = g["LINE_V"]
    R, G_, B = BLOCKED_RGB
    cvt = lambda fd, fs: ".word %#x" % (0x46000024 | (fs << 11) | (fd << 6))   # cvt.w.s
    part_d = f"""
tp_mark:                             ; a0 = the ReticuleDisplay being drawn (UIModel::Draw's stand-in)
    addiu sp, sp, -0x3a0
    sd    ra, 0x340(sp)
    sq    s0, 0x350(sp)
    sq    s1, 0x360(sp)
    sq    s2, 0x370(sp)
    sq    s3, 0x380(sp)
    sq    s4, 0x390(sp)
    move  s0, a0
    lw    t0, {b['SPLIT']:#x}(s0)               ; split number: above 0 is the second player's view
    slt   s4, zero, t0               ; view 0 / 1, as ReticuleDisplay reads it
    sll   t0, s4, 5
    lui   s3, %hi(STATE)
    addiu s3, s3, %lo(STATE)
    addu  s3, s3, t0                 ; this view's state
    lui   t1, %hi(SIMMGR)
    lw    t1, %lo(SIMMGR)(t1)
    beqz  t1, tm_off
    sll   t0, s4, 2
    addu  t1, t1, t0
    lw    s1, 0x444(t1)              ; that view's SimCamera
    beqz  s1, tm_off
    addiu t2, zero, 1
    lw    t0, 0x70(s1)               ; third person ...
    bne   t0, t2, tm_off
    lw    t0, 0x74(s1)               ; ... placed by cam_tp, shots converging (aim_base's test)
    bne   t0, t2, tm_off
    lw    s2, 4(s1)                  ; the soldier
    beqz  s2, tm_off
    nop
    lw    t0, 0x138(s2)              ; a player's
    bnez  t0, tm_off
    lw    t0, 0x30(s1)               ; the camera's room
    beqz  t0, tm_off
    lwc1  $f0, 0x8c(s1)              ; V
    lwc1  $f1, 0x90(s1)
    lwc1  $f2, 0x94(s1)
    swc1  $f0, 0xd0(sp)
    swc1  $f1, 0xd4(sp)
    swc1  $f2, 0xd8(sp)
    lbu   t0, 0x1c(s3)               ; one trace a frame: the camera line and the round's line in turn
    lw    t1, 0xc(s3)
    bne   t1, s1, tm_cam             ; no P for this camera yet
    nop
    bnez  t0, tm_round               ; 1: the round's line is next
    nop
tm_cam:                              ; P: the camera line, traced as aim_base traces it
    lwc1  $f3, 0x10(s1)
    lwc1  $f4, 0x14(s1)
    lwc1  $f5, 0x18(s1)
    swc1  $f3, 0x00(sp)
    swc1  $f4, 0x04(sp)
    swc1  $f5, 0x08(sp)
    swc1  $f0, {LV:#x}(sp)
    swc1  $f1, {LV + 4:#x}(sp)
    swc1  $f2, {LV + 8:#x}(sp)
    lw    t0, 0x30(s1)
{_li_f(0, AIM_RANGE)}    sw    t0, 0xe8(sp)
    swc1  $f0, 0xdc(sp)
    b     tm_trace
    sw    zero, 0xec(sp)
tm_round:                            ; the round's line: O towards P
    lw    t9, 0(s2)                  ; O = GetShootFromLocation
    lb    a2, 0x1e7(s2)
    lw    t9, {g['SHOOTFROM']:#x}(t9)
    move  a1, s2
    jalr  t9
    addiu a0, sp, 0x80
    sh    zero, 0x1c(s3)             ; the camera line next; not blocked until this trace says so
    lwc1  $f0, 0x00(s3)              ; D = P - O
    lwc1  $f3, 0x80(sp)
    lwc1  $f1, 0x04(s3)
    lwc1  $f4, 0x84(sp)
    lwc1  $f2, 0x08(s3)
    lwc1  $f5, 0x88(sp)
    sub.s $f0, $f0, $f3
    sub.s $f1, $f1, $f4
    sub.s $f2, $f2, $f5
    swc1  $f3, 0x00(sp)
    swc1  $f4, 0x04(sp)
    swc1  $f5, 0x08(sp)
    lwc1  $f3, 0xd0(sp)
    lwc1  $f4, 0xd4(sp)
    lwc1  $f5, 0xd8(sp)
    mul.s $f6, $f0, $f3              ; D . V
    mul.s $f7, $f1, $f4
    add.s $f6, $f6, $f7
    mul.s $f7, $f2, $f5
    add.s $f6, $f6, $f7
    lui   at, 0x3f00                 ; 0.5 m
    mtc1  at, $f9
    mul.s $f7, $f0, $f0
    c.lt.s $f9, $f6                  ; P ahead of O, as aim_base requires
    mul.s $f8, $f1, $f1
    bc1f  tm_show
    add.s $f7, $f7, $f8
    mul.s $f8, $f2, $f2
    add.s $f7, $f7, $f8
    sqrt.s $f7, $f7                  ; |D|
    nop
    nop
    sub.s $f10, $f7, $f9             ; reach: anything met before |D| - 0.5 blocks
    c.lt.s $f9, $f10
    div.s $f11, $f9, $f7
    bc1f  tm_show
    swc1  $f10, 0xdc(sp)
    nop
    add.s $f11, $f11, $f11           ; 1 / |D|
    mul.s $f0, $f0, $f11
    mul.s $f1, $f1, $f11
    mul.s $f2, $f2, $f11
    lw    t0, {b['SHOOTROOM']:#x}(s2)    ; the room HandleGunshot traces a round from
    swc1  $f0, {LV:#x}(sp)
    swc1  $f1, {LV + 4:#x}(sp)
    swc1  $f2, {LV + 8:#x}(sp)
    beqz  t0, tm_show
    sw    t0, 0xe8(sp)
    addiu t0, zero, 1
    sw    t0, 0xec(sp)
tm_trace:                            ; RSSimRoom::FindLineCollision as HandleGunshot calls it
    jal   LCINFO
    addiu a0, sp, 0x20
    lw    a0, 0xe8(sp)
    addiu a1, sp, 0x00
    addiu a2, sp, 0x20
    move  a3, s2                     ; the soldier himself does not stop it
    addiu t0, zero, {TRACE_FLAGS}
    addiu t1, zero, {TRACE_MASK}
    lwc1  $f12, 0xdc(sp)
    move  t3, zero
    jal   FLC
    addiu t2, zero, 1
    lwc1  $f3, 0x54(sp)              ; t
    lwc1  $f0, {LV:#x}(sp)           ; start + t * direction: P, or the hit H
    lwc1  $f4, 0x00(sp)
    lwc1  $f1, {LV + 4:#x}(sp)
    mul.s $f0, $f0, $f3
    lwc1  $f5, 0x04(sp)
    mul.s $f1, $f1, $f3
    lwc1  $f2, {LV + 8:#x}(sp)
    lwc1  $f6, 0x08(sp)
    mul.s $f2, $f2, $f3
    add.s $f0, $f0, $f4
    add.s $f1, $f1, $f5
    add.s $f2, $f2, $f6
    lw    t0, 0xec(sp)
    bnez  t0, tm_hit
    andi  v0, v0, 0xff
    swc1  $f0, 0x00(s3)              ; camera line: P for the next frame, whose trace is the round's
    swc1  $f1, 0x04(s3)
    swc1  $f2, 0x08(s3)
    addiu t1, zero, 1
    sb    t1, 0x1c(s3)
    b     tm_show
    sw    s1, 0xc(s3)
tm_hit:                              ; round's line: blocked if it met anything short of the reach
    swc1  $f0, 0x10(s3)
    swc1  $f1, 0x14(s3)
    swc1  $f2, 0x18(s3)
    sb    v0, 0x1d(s3)
tm_show:
    lbu   t0, 0x1d(s3)
    beqz  t0, tm_plain               ; clear: the reticle as it is
    lwc1  $f0, 0x10(s3)              ; blocked: H, and whether it is in front of the camera
    lwc1  $f1, 0x14(s3)
    lwc1  $f2, 0x18(s3)
    lui   at, 0x3f80
    swc1  $f0, 0xb0(sp)
    swc1  $f1, 0xb4(sp)
    swc1  $f2, 0xb8(sp)
    sw    at, 0xbc(sp)
    lwc1  $f3, 0x10(s1)              ; (H - C) . V > 0.25
    lwc1  $f4, 0x14(s1)
    lwc1  $f5, 0x18(s1)
    sub.s $f0, $f0, $f3
    sub.s $f1, $f1, $f4
    sub.s $f2, $f2, $f5
    lwc1  $f3, 0xd0(sp)
    lwc1  $f4, 0xd4(sp)
    lwc1  $f5, 0xd8(sp)
    mul.s $f0, $f0, $f3
    mul.s $f1, $f1, $f4
    mul.s $f2, $f2, $f5
    add.s $f0, $f0, $f1
    lui   at, 0x3e80
    add.s $f0, $f0, $f2
    mtc1  at, $f1
    sw    zero, 0xe0(sp)
    c.lt.s $f1, $f0
    nop
    bc1f  tm_draw
    nop
    addiu t0, zero, 1                ; in front: project H into this view, as the reticle
    sw    t0, 0xe0(sp)               ;   projects its target
    lui   t0, %hi(GFX)
    lw    t0, %lo(GFX)(t0)
    j     tm_proj
    addiu a0, t0, 0x100
"""
    part_e = f"""
tm_proj:                             ; a0 = the graphics API
    move  a1, s4                     ; this view
    addiu a2, sp, 0xc0
    addiu a3, sp, 0xb0
    jal   PROJ
    move  t0, zero
tm_draw:                             ; blocked: amber reticle, and its copy at the hit
    lw    s1, 8(s0)                  ; the model's GIF packet
    beqz  s1, tm_plain
    lui   t1, {_RET_TAG[0] >> 16:#x}
    lw    t0, 4(s1)
    bne   t0, t1, tm_plain
    lui   t1, {_RET_TAG[1] >> 16:#x}
    ori   t1, t1, {_RET_TAG[1] & 0xFFFF:#x}
    lw    t0, 8(s1)
    bne   t0, t1, tm_plain
    lui   t1, {_RET_TAG[2] >> 16:#x}
    ori   t1, t1, {_RET_TAG[2] & 0xFFFF:#x}
    lw    t0, 0xc(s1)
    bne   t0, t1, tm_plain
    lhu   t4, 0(s1)
    andi  t4, t4, 0x7fff             ; quads
    beqz  t4, tm_plain
    sltiu t0, t4, 6
    beqz  t0, tm_plain
    sw    t4, 0xe4(sp)
    sll   t5, t4, 3                  ; save 7 * quads + 1 quadwords
    subu  t5, t5, t4
    addiu t5, t5, 1
    move  t6, s1
    addiu t7, sp, 0x100
tm_save:
    lq    t0, 0(t6)
    addiu t5, t5, -1
    sq    t0, 0(t7)
    addiu t6, t6, 16
    bnez  t5, tm_save
    addiu t7, t7, 16
    addiu t6, s1, 16                 ; each quad's two RGBAQs (+0, +0x38) -> amber
    move  t5, t4
    addiu t0, zero, {R:#x}
    addiu t1, zero, {G_:#x}
    addiu t2, zero, {B:#x}
tm_tint:
    sb    t0, 0(t6)
    sb    t1, 1(t6)
    sb    t2, 2(t6)
    sb    t0, 0x38(t6)
    sb    t1, 0x39(t6)
    sb    t2, 0x3a(t6)
    addiu t5, t5, -1
    bnez  t5, tm_tint
    addiu t6, t6, 0x70
    lw    t0, 0xe0(sp)               ; in front of the camera: the reticle itself goes to the hit
    beqz  t0, tm_one
    lwc1  $f0, 0xc0(sp)              ; the hit in GS 12.4
    lwc1  $f1, 0xc4(sp)
    lui   at, 0x4180
    mtc1  at, $f2
    nop
    mul.s $f0, $f0, $f2
    mul.s $f1, $f1, $f2
    {cvt(0, 0)}
    {cvt(1, 1)}
    mfc1  t2, $f0
    mfc1  t3, $f1
    addiu t2, t2, -0x8000            ; the move, 12.4: the projection is centred on this view (2048,
    addiu t3, t3, -0x8000            ;   2048); the reticle's quads carry the split-screen offset
    addiu t0, t2, {MARK_X * 16:#x}             ; on screen: within {MARK_X} GS sideways ...
    sltiu t0, t0, {MARK_X * 32:#x}
    beqz  t0, tm_one
    lw    t1, {b['SPLIT']:#x}(s0)
    addiu t5, zero, {MARK_Y * 16:#x}           ; ... and {MARK_Y} GS up or down for a view on its own,
    beqz  t1, tm_ylim
    nop
    addiu t5, zero, {MARK_Y_SPLIT * 16:#x}     ; {MARK_Y_SPLIT} for half of a split screen
tm_ylim:
    addu  t0, t3, t5
    sll   t1, t5, 1
    sltu  t0, t0, t1
    beqz  t0, tm_one                 ; off screen: the amber reticle stays in place
    lw    t4, 0xe4(sp)
    addiu t6, s1, 16
tm_quad:
    addiu t7, t6, 16                 ; XYZ2 at +0x10, +0x20, +0x30, +0x48, +0x58, +0x68
    addiu t5, zero, 6
tm_vtx:
    lhu   t0, 0(t7)                  ; every vertex moved by the hit's offset from the view's centre
    addu  t0, t0, t2
    sh    t0, 0(t7)
    lhu   t0, 2(t7)
    addu  t0, t0, t3
    sh    t0, 2(t7)
    addiu t5, t5, -1
    addiu t0, zero, 3
    bne   t5, t0, tm_next
    addiu t7, t7, 16
    addiu t7, t7, 8
tm_next:
    bnez  t5, tm_vtx
    nop
    addiu t4, t4, -1
    bnez  t4, tm_quad
    addiu t6, t6, 0x70
tm_one:
    jal   UIDRAW                     ; one reticle, amber: at the hit, or in place if that is off screen
    move  a0, s0
tm_restore:
    lw    t4, 0xe4(sp)               ; the packet back as the game left it
    sll   t5, t4, 3
    subu  t5, t5, t4
    addiu t5, t5, 1
    move  t6, s1
    addiu t7, sp, 0x100
tm_load:
    lq    t0, 0(t7)
    addiu t5, t5, -1
    sq    t0, 0(t6)
    addiu t6, t6, 16
    bnez  t5, tm_load
    addiu t7, t7, 16
    b     tm_out
    nop
tm_off:                              ; not ours this frame: forget this view's P and hit
    sw    zero, 0xc(s3)
    sb    zero, 0x1d(s3)
tm_plain:                            ; UIModel::Draw as stock
    jal   UIDRAW
    move  a0, s0
tm_out:
    ld    ra, 0x340(sp)
    lq    s0, 0x350(sp)
    lq    s1, 0x360(sp)
    lq    s2, 0x370(sp)
    lq    s3, 0x380(sp)
    lq    s4, 0x390(sp)
    jr    ra
    addiu sp, sp, 0x3a0
"""
    return part_d, part_e


def build_mark(game):
    """([(base, words, name)], labels) for the blocked-shot routine."""
    g, b = GAMES[game], BLOCKED[game]
    d, e = _mark_srcs(g, b)
    syms = {"SIMMGR": g["SIMMGR"], "LCINFO": g["LCINFO"], "FLC": g["FLC"],
            "UIDRAW": b["UIDRAW"], "PROJ": b["PROJ"], "GFX": b["GFX"]}
    state = b["CAVE_E"] + b["CAVE_E_BYTES"] - STATE_BYTES
    syms["STATE"] = state
    we, le = assemble(e, b["CAVE_E"], syms)
    syms.update(le)
    wd, ld = assemble(d, b["CAVE_D"], syms)
    if len(wd) * 4 > b["CAVE_D_BYTES"] or b["CAVE_E"] + len(we) * 4 > state:
        raise ValueError("%s: the blocked-shot routine outgrows its caves" % game)
    we = we + [0] * ((state - b["CAVE_E"]) // 4 - len(we)) + [0] * (STATE_BYTES // 4)
    names = b.get("CAVE_NAMES", ("lgAud (unreferenced)", "lgAud (unreferenced)"))
    return ([(b["CAVE_D"], wd, names[0]), (b["CAVE_E"], we, names[1])],
            dict(ld, **le, STATE=state))


def blocked_edits(game):
    """[(va, value, stock, note)]: amber reticle and a mark where the round would hit."""
    if game not in BLOCKED:
        return []
    b = BLOCKED[game]
    stock = GR_STOCK if game == "gr" else JS_STOCK
    caves, labels = build_mark(game)
    out = []
    for base, words, where in caves:
        out += [(base + 4 * i, w, stock[base + 4 * i],
                 "third-person camera: blocked-shot routine in " + where) for i, w in enumerate(words)]
    out.append((b["HOOK"], assemble("jal %#x" % labels["tp_mark"], b["HOOK"])[0][0], b["HOOK_STOCK"],
                "third-person camera: the reticle is drawn through tp_mark"))
    if "HOOK_DELAY" in b:
        va, st = b["HOOK_DELAY"]
        out.append((va, assemble("move a0, a1", va)[0][0], st,
                    "third-person camera: tp_mark gets the reticle in a0"))
    return out


for _g, _b in BLOCKED.items():
    _t = GR_STOCK if _g == "gr" else JS_STOCK
    _t.update(_stock_words(_b["CAVE_D"], _b["STOCK_D"]))
    _t.update(_stock_words(_b["CAVE_E"], _b["STOCK_E"]))
    _t[_b["HOOK"]] = _b["HOOK_STOCK"]
    if "HOOK_DELAY" in _b:
        _t[_b["HOOK_DELAY"][0]] = _b["HOOK_DELAY"][1]



# ---------------------------------------------------------------------------
# Third person near scenery: trees, slopes, and no jumping (``cam_fix``)
# ---------------------------------------------------------------------------
#
# SimCamera::PlaceCamera sweeps a 0.3 m sphere from S (eye + H up) back along
# w; RSSimRoom::FindSphereCollision there ignores every controller
# (kLineIgnoreAllControllers) and the result is used as it is, every frame.
# Near scenery that gave three things: something the sweep does not stop on
# between the camera and the soldier; a camera pulled in towards S keeps its
# height, so the soldier drops to the bottom of the screen (H above the eye
# over a shorter distance); and every change of the sweep is instant, so he
# jumps between frames on broken ground.
#
# ``cam_fix`` runs after PlaceCamera, before the floor clamp:
#   * framing: the camera goes on the line from the eye through the
#     full-distance camera (N = w + H up), as far from the eye as the sweep
#     let it be -- pulled in, he stays where he was on screen and only grows,
#     and ground rising behind brings it nearer rather than higher;
#   * line of sight: that line from his eye is traced the way a round is
#     traced (scenery, trees, vehicles and props; no soldier stops
#     it; faces a round passes are passed) and the camera comes in to 0.3 m
#     short of anything it meets;
#   * easing: the distance from his eye shrinks at once (and any frame not
#     asking for more re-arms the hold), holds for EASE_HOLD s, then may grow by at most EASE_RATE m/s (about 0.4 s from
#     the eye to 2.75 m; RSClock's frame seconds) -- on broken ground where the
#     sweep flickers, the camera stays in instead of jumping every frame.
#     SimCamera+0x78/+0x7C (spare; the constructor zeroes them) keep the
#     distance and the hold's end, and a zoom resets the distance;
#   * the room: when it moved the camera, RSSimScene::FindRoom gives the room
#     it is now in (PlaceCamera's is for where it put it).
# Cost: one short line trace a frame per third-person view.
EASE_RATE = 7.0         # m/s
EASE_MARGIN = 0.3       # m short of what the line of sight meets
EASE_HOLD = 0.3         # s without easing out after being pulled in
#: its cave(s), per game
CAMFIX = {
    # part 2 (easing, placing, the room) goes after floor_clamp in sceMcRename (cave C)
    "gr": dict(CAVE=0x004190F8, BYTES=520, CAVE2=0x00421FF8, BYTES2=232,
               NAME="unreferenced SIF library routine", STOCK=(
        "27bdff70 ffb60070 ffb30040 00e0b02d ffb10020 0080982d ffb00010 00a0882d"
        "ffbf0080 00c0802d ffb50060 ffb40050 0c10634a ffb20030 04400069 3c02ffff"
        "0c10638a 00000000 10400004 3c14005f 3c02fffe 10000062 3442fffc 0280a82d"
        "2692f640 1200004a ae93f640 2a2200fd 14400042 0200282d 26440104 02041025"
        "30420007 1040001a 0200382d 260200e0 3c05005f 68e30007 6ce30000 68e6000f"
        "6ce60008 68e80017 6ce80010 68e9001f 6ce90018 b0830007 b4830000 b086000f"
        "b4860008 b0880017 b4880010 b089001f b4890018 24e70020 24840020 00000000"
        "14e2ffec 00000000 10000010 00000000 260200e0 3c05005f dcea0000 dce30008"
        "dce60010 dce80018 fc8a0000 fc830008 fc860010 fc880018 24e70020 24840020"
        "00000000 14e2fff4 00000000 68e90007 6ce90000 68ea000f 6cea0008 68e60017"
        "6ce60010 88e8001b 98e80018 b0890007 b4890000 b08a000f b48a0008 b0860017"
        "b4860010 a888001b 26a3f640 240200fc b8880018 10000008 ac620004 26440104"
        "0c100e4c 0220302d 10000002 ae510004 ae400004 3c05005f 26b0f640 24a4f840"
        "afa00000 24050007 0000302d 0200382d 24080200 0200482d 240a0008 0c10531c"
        "0000582d 04430004 8e030004 3c02fffe 10000003 3442ffff 8e82f640 aec30000"
        "dfbf0080 dfb60070 dfb50060 dfb40050 dfb30040 dfb20030 dfb10020 dfb00010"
        "03e00008 27bd0090")),
    # the head of NewPS2Shortcut (0x002A0970): its one caller (0x0029FDD0) runs only while
    # mInstance (0x00629278) is set, and it is only ever stored as zero (0x0023AD4C)
    "js": dict(CAVE=0x002A0970, BYTES=656, NAME="dead NewPS2Shortcut head", STOCK=(
            "27bdfe80 ffbf00a0 7fbe0090 7fb70080 7fb60070 7fb50060 7fb40050 0080a82d"
            "7fb30040 7fb20030 7fb10020 7fb00010 e7b50004 0c07f308 e7b40000 0040202d"
            "0c07f304 24050003 0040a02d 0c08690c 0280202d 0c086928 0280202d 0c08e864"
            "00000000 46000306 0c0835f0 0280202d 0c08e860 00000000 46000306 0c08c924"
            "0280202d 240500ff 27a40160 00a0302d 0000382d 0c10d82c 00a0402d 240500ff"
            "27a40150 00a0302d 00a0382d 0c10d82c 00a0402d 0000982d 27be0148 02a0202d"
            "0c0a85dc 0260282d 1440000d 26a40030 44806000 27a40130 46006346 46006386"
            "0c040d60 460063c6 0040302d 26a40030 0c09ae48 0260282d 10000252 26730001"
            "0260282d 0c09ae4c 27a60150 3c020063 00131900 24429290 26a40030 00438021"
            "0260282d 0c09ae48 0200302d 0c0a7d34 0260202d 0040902d 92a2002c 10400005"
            "00000000 2642ffff 2c410003 14200010 00000000 92a3002d 10600003 00000000"
            "1240000b 00000000 92a2002e 10400003 00000000 12400006 00000000 92a2002f"
            "1040000a 2a62001f 16400008 00000000 3c010059 26a40030 c42cd290 0c09ad50"
            "0260282d 10000226 00000000 1440009e 2a610031 1020009c 0003102b 38420001"
            "0c049174 305600ff 8c590000 0040202d 8f390064 0320f809 0000282d 0c0529f8"
            "0040802d 8c590000 0200282d 8f390038 0320f809 0040202d 0c049180 0040882d"
            "8e390000 0040802d 8f39006c 0320f809 0220202d 8e390000 0040b82d 8f3900a8"
            "0320f809 0220202d 8e190000 02e0282d 02c0382d 0200202d 8f390014 0320f809"
            "0040302d 2643ffe7 2c610002 14200008 0000802d 2643ffed 2c610003 14200005"
            "0040202d 2403001b 16430025 2643ffea 0040202d 0c099fd8 00000000 24030002"
            "10430017 24030001 1043000d 00000000")),
}


def _cam_fix_src(g, H, L, D):
    """(part 1, part 2): framing, line of sight and easing; placing and the room."""
    E, LV = g["EYE"], g["LINE_V"]
    W = (D * D + L * L) ** 0.5            # |w|: right is level and square to the look
    if "SCENE" in g:
        scene = "    lui   t0, %hi(SCENE)\n    lw    a0, %lo(SCENE)(t0)\n"
    else:
        scene = "    jal   SCENEGET\n    nop\n    move  a0, v0\n"
    part1 = f"""
cam_fix:                             ; a0 = SimCamera, just placed; cam_tp's frame above (S +0, w +0x10)
    addiu sp, sp, -0xa0
    sd    ra, 0x90(sp)
    sq    s0, 0x80(sp)
    move  s0, a0
    lw    t0, 4(s0)                  ; the soldier
    lwc1  $f6, {E:#x}(t0)            ; E, the eye: the line starts there
    lwc1  $f7, {E + 4:#x}(t0)
    lwc1  $f8, {E + 8:#x}(t0)
    lwc1  $f3, 0x10(s0)              ; C, where PlaceCamera put it: how far from the eye
    lwc1  $f4, 0x14(s0)
    lwc1  $f5, 0x18(s0)
    swc1  $f6, 0x00(sp)
    sub.s $f3, $f3, $f6
    swc1  $f7, 0x04(sp)
    sub.s $f4, $f4, $f7
    swc1  $f8, 0x08(sp)
    sub.s $f5, $f5, $f8
    mul.s $f3, $f3, $f3
    mul.s $f4, $f4, $f4
    add.s $f3, $f3, $f4
    mul.s $f5, $f5, $f5
    add.s $f3, $f3, $f5
    sqrt.s $f0, $f3                  ; d = |C - E|
    lwc1  $f3, 0xb0(sp)              ; N = w + H up: from the eye to the full-distance camera
    lwc1  $f4, 0xb4(sp)
{_li_f(1, H)}    lwc1  $f5, 0xb8(sp)
    swc1  $f0, 0x70(sp)
    add.s $f5, $f5, $f1
    mul.s $f0, $f3, $f3
    mul.s $f1, $f4, $f4
    add.s $f0, $f0, $f1
    mul.s $f1, $f5, $f5
    add.s $f0, $f0, $f1
    sqrt.s $f0, $f0                  ; |N|
    lui   at, 0x3f80
    mtc1  at, $f1
    nop
    div.s $f1, $f1, $f0
    nop
    nop
    mul.s $f3, $f3, $f1              ; the camera goes along N / |N|: pulled in, he stays where he was
    mul.s $f4, $f4, $f1              ;   on screen, and a slope brings it nearer rather than higher
    mul.s $f5, $f5, $f1
    swc1  $f3, {LV:#x}(sp)
    swc1  $f4, {LV + 4:#x}(sp)
    swc1  $f5, {LV + 8:#x}(sp)
    jal   LCINFO
    addiu a0, sp, 0x20
    lw    a3, 4(s0)                  ; he does not stop it, nor does any soldier
    addiu a1, sp, 0x00
    lw    a0, 0x158(a3)              ; his room
    addiu a2, sp, 0x20
    addiu t0, zero, 0x12             ; kIsGunshot | kIgnoreHumanControllers
    addiu t1, zero, {TRACE_MASK}     ; through faces a round passes (leaves)
    lwc1  $f12, 0x70(sp)
    move  t3, zero
    jal   FLC                        ; the line from his eye to the camera
    addiu t2, zero, 1
    andi  v0, v0, 0xff
    beqz  v0, cf_ease
    lwc1  $f0, 0x70(sp)
    lwc1  $f0, 0x54(sp)              ; met something: stop short of it
{_li_f(1, EASE_MARGIN)}    nop
    sub.s $f0, $f0, $f1
cf_ease:                             ; f0 = what the sweep and the line of sight allow
    lui   t0, %hi(CLOCK)
    lw    t0, %lo(CLOCK)(t0)
    lwc1  $f1, 0xd4(t0)              ; now (RSClock::TotalElapsedSeconds)
    lwc1  $f3, 0x78(s0)              ; last frame's distance
    c.le.s $f0, $f3                  ; not farther: at once, and no easing out for EASE_HOLD s
    lwc1  $f2, 0xd0(t0)              ; this frame's seconds (FrameElapsedSeconds)
    bc1f  cf_out
    nop
{_li_f(4, EASE_HOLD)}    nop
    add.s $f4, $f1, $f4
    b     cf_pos
    swc1  $f4, 0x7c(s0)              ; held until then
cf_out:
    lwc1  $f4, 0x7c(s0)
    c.lt.s $f1, $f4                  ; still held: last frame's distance
    mov.s $f5, $f0
    bc1t  cf_pos
    mov.s $f0, $f3
{_li_f(4, EASE_RATE)}    nop
    mul.s $f2, $f2, $f4
    add.s $f0, $f3, $f2              ; out by EASE_RATE * dt at most ...
    c.lt.s $f5, $f0                  ; ... or to what is allowed
    nop
    bc1f  cf_pos
    nop
    mov.s $f0, $f5
cf_pos:
    mtc1  zero, $f2
    nop
    c.lt.s $f0, $f2
    nop
    bc1f  cf_put
    nop
    mov.s $f0, $f2
    j     cf_put
    nop
"""
    part2 = f"""
cf_put:
    swc1  $f0, 0x78(s0)
    lwc1  $f1, 0x00(sp)              ; camera = E + distance * D/|D|
    lwc1  $f2, {LV:#x}(sp)
    lwc1  $f3, 0x04(sp)
    mul.s $f2, $f2, $f0
    lwc1  $f4, {LV + 4:#x}(sp)
    lwc1  $f5, 0x08(sp)
    mul.s $f4, $f4, $f0
    lwc1  $f6, {LV + 8:#x}(sp)
    add.s $f1, $f1, $f2
    mul.s $f6, $f6, $f0
    add.s $f3, $f3, $f4
    swc1  $f1, 0x10(s0)
    add.s $f5, $f5, $f6
    swc1  $f3, 0x14(s0)
    swc1  $f5, 0x18(s0)
{scene}    jal   FINDROOM                   ; the room it is in now
    addiu a1, s0, 0x10
    beqz  v0, cf_out2
    nop
    sw    v0, 0x30(s0)
cf_out2:
    move  a0, s0
    ld    ra, 0x90(sp)
    lq    s0, 0x80(sp)
    j     FLOORCLAMP
    addiu sp, sp, 0xa0
"""
    return part1, part2


def build_fix(game, preset, distance="preset"):
    """([(base, words)], labels) of cam_fix for a preset, or (None, None) where it has no cave."""
    c = CAMFIX.get(game)
    if not c:
        return None, None
    g = GAMES[game]
    p = dict(PRESETS[preset])
    if distance not in (None, "preset"):
        p["D"] = float(distance)
    syms = {k: g[k] for k in ("LCINFO", "FLC", "CLOCK", "FINDROOM", "SCENE", "SCENEGET") if k in g}
    syms["FLOORCLAMP"] = floor_clamp_at(game)
    one, two = _cam_fix_src(g, p["H"], p["L"], p["D"])
    if c.get("CAVE2"):
        w2, l2 = assemble(two, c["CAVE2"], syms)
        syms.update(l2)
        w1, l1 = assemble(one, c["CAVE"], syms)
        if len(w1) * 4 > c["BYTES"] or len(w2) * 4 > c["BYTES2"]:
            raise ValueError("%s: cam_fix outgrows its caves" % game)
        return [(c["CAVE"], w1), (c["CAVE2"], w2)], dict(l1, **l2)
    w, l = assemble(one + two, c["CAVE"], syms)
    if len(w) * 4 > c["BYTES"]:
        raise ValueError("%s: cam_fix outgrows its cave" % game)
    return [(c["CAVE"], w)], l


def floor_clamp_at(game):
    g = GAMES[game]
    return assemble(_floor_clamp_src(g), g["CAVE_C"], {k: g[k] for k in ("FLOOR",)})[1]["floor_clamp"]


for _g, _c in CAMFIX.items():
    if _c:
        (GR_STOCK if _g == "gr" else JS_STOCK).update(_stock_words(_c["CAVE"], _c["STOCK"]))


#: camera distance choices (metres back from the eye); "preset" keeps the preset's
DISTANCES = ("preset", "1.75", "2.0", "2.25", "2.5", "2.75", "3.0")


#: the functions the three caves overwrite (none is referenced)
CAVE_NAMES = {"gr": ("sceDevConsDraw", "sceVu0DropShadowMatrix", "sceMcRename"),
              "js": ("sceDevConsDraw", "sceVu0DropShadowMatrix", "lgAudWriteVag")}


def build(game, preset, aim_cam=True, distance="preset", smooth=False):
    """([(base, words, cave name)], labels, patches) for a preset.

    Cave A holds cam_tp and aim_from, cave B aim_base, cave C floor_clamp; with ``smooth``
    (where CAMFIX has a cave) cam_fix runs between PlaceCamera and floor_clamp."""
    g = GAMES[game]
    p = dict(PRESETS[preset])
    if distance not in (None, "preset"):
        p["D"] = float(distance)
    syms = {k: g[k] for k in ("PLACE", "SIMMGR", "FLOOR", "ISSNIPER", "FLC", "LCINFO", "QSET")}
    wc, lc = assemble(_floor_clamp_src(g), g["CAVE_C"], syms)
    syms["FLOORCLAMP"] = lc["floor_clamp"]
    wf, lf = build_fix(game, preset, distance) if smooth else (None, None)
    syms["POSTPLACE"] = lf["cam_fix"] if wf else lc["floor_clamp"]
    wa, la = assemble(_cam_tp_src(g, p["H"], p["L"], p["D"], aim_cam) + _aim_from_src(g),
                      g["CAVE_A"], syms)
    wb, lb = assemble(_aim_base_src(g), g["CAVE_B"], syms)
    caves = []
    for (base, nbytes), words, name in zip(((g["CAVE_A"], g["CAVE_A_BYTES"]),
                                            (g["CAVE_B"], g["CAVE_B_BYTES"]),
                                            (g["CAVE_C"], g["CAVE_C_BYTES"])),
                                           (wa, wb, wc), CAVE_NAMES[game]):
        if len(words) * 4 > nbytes:
            raise ValueError("%s camera routines overflow %s" % (game, name))
        caves.append((base, words, name))
    labels = dict(lc, **la, **lb)
    if wf:
        for base, words in wf:
            caves.append((base, words, CAMFIX[game]["NAME"] if base == CAMFIX[game]["CAVE"]
                          else CAVE_NAMES[game][2] + " (after floor_clamp)"))
        labels.update(lf)
    return caves, labels, _patches(g, g["CAVE_A"], labels)


def edits(game, preset, aim_eye=False, distance="preset", smooth=False):
    """[(va, value, stock, note)]; preset 'off' (or anything unknown) = none."""
    if preset not in PRESETS:
        return []
    stock = GR_STOCK if game == "gr" else JS_STOCK
    caves, _labels, groups = build(game, preset, aim_cam=not aim_eye, distance=distance,
                                   smooth=smooth)
    out = []
    for base, words, where in caves:
        out += [(base + 4 * i, w, stock[base + 4 * i],
                 "third-person camera: routine in " + where)
                for i, w in enumerate(words)]
    for rows in groups.values():
        out += [(va, new, st, "third-person camera: " + note)
                for va, st, new, note in rows]
    return out


def _game_edits(game, v):
    p = game + "_"
    out = edits(game, v.get(p + "tp_camera", "off"), bool(v.get(p + "tp_aim_eye")),
                v.get(p + "tp_distance", "preset"), bool(v.get(p + "tp_smooth")))
    # third person cannot work without it: any first-person frame hides him for good
    if v.get(p + "tp_camera", "off") in PRESETS or v.get(p + "show_soldiers"):
        out += unhide_edits(game)
    if v.get(p + "tp_camera", "off") in PRESETS:
        out += xleader_edits(game)
        out += tppose_edits(game)
        if v.get(p + "tp_blocked"):
            out += blocked_edits(game)
    return out


def gr_edits(v):
    return _game_edits("gr", v)


def js_edits(v):
    return _game_edits("js", v)


def _fpu_hazards(words):
    """mtc1 read by the next instruction, div/sqrt read within two, or a
    compare straight before bc1 -- the gaps the game's own compiler keeps."""
    bad = []

    def writes(w):
        if w >> 26 == 0x11 and (w >> 21) & 31 == 0x04:
            return 1, (w >> 11) & 31
        if w >> 26 == 0x11 and (w >> 21) & 31 == 0x10 and w & 0x3F in (3, 4):
            return 2, (w >> 6) & 31
        return None

    def reads(w):
        r = set()
        if w >> 26 == 0x11 and (w >> 21) & 31 == 0x10:
            r.add((w >> 16) & 31)
            if w & 0x3F != 4:
                r.add((w >> 11) & 31)
        if w >> 26 == 0x39:
            r.add((w >> 16) & 31)
        return r

    for i, w in enumerate(words):
        wr = writes(w)
        if wr:
            gap, reg = wr
            for k in range(1, gap + 1):
                if i + k < len(words) and reg in reads(words[i + k]):
                    bad.append(i)
        if (w >> 26 == 0x11 and (w >> 21) & 31 == 0x10 and w & 0x30 == 0x30
                and i + 1 < len(words) and words[i + 1] >> 16 in (0x4500, 0x4501)):
            bad.append(i)
    return bad


def selftest(gr_elf=None, js_elf=None):
    """Return a list of failures (empty = pass)."""
    fails = []
    for game, stock, elf, delta in (("gr", GR_STOCK, gr_elf, 0x80),
                                    ("js", JS_STOCK, js_elf, 0x100)):
        g = GAMES[game]
        sizes = set()
        for preset, smooth in [(pr, sm) for pr in PRESETS for sm in ((False, True) if CAMFIX.get(game) else (False,))]:
            for aim_eye in (False, True):
                caves, _labels, _p = build(game, preset, not aim_eye, smooth=smooth)
                sizes.add((smooth,) + tuple(len(words) for _b, words, _n in caves))
                for _base, words, name in caves:
                    if _fpu_hazards(words):
                        fails.append("%s %s cave %s: FPU hazard at word %s"
                                     % (game, preset, name, _fpu_hazards(words)))
                seen = set()
                for va, _w, s, _note in edits(game, preset, aim_eye, smooth=smooth):
                    if va in seen:
                        fails.append("%s %08x written twice" % (game, va))
                    seen.add(va)
                    if stock.get(va) != s:
                        fails.append("%s %08x: edit stock %08x, table %s"
                                     % (game, va, s, stock.get(va)))
        if len({x[1:] for x in sizes if not x[0]}) != 1 or len({x[1:] for x in sizes if x[0]}) > 1:
            fails.append("%s: presets differ in layout %s" % (game, sizes))
        if edits(game, "off"):
            fails.append("%s: 'off' still writes words" % game)
        u = UNHIDE[game]
        uw = unhide_edits(game)
        if len(uw) - 1 > len("".join(u["STOCK"].split())) // 8:
            fails.append("%s: unhide routine outgrows its stock table" % game)
        taken = {va for va, _w, _s, _n in edits(game, "ots")}
        if taken & {va for va, _w, _s, _n in uw}:
            fails.append("%s: unhide overlaps the camera routines" % game)
        be = blocked_edits(game)
        if be:
            for _b, words, name in build_mark(game)[0]:
                if _fpu_hazards(words):
                    fails.append("%s blocked-shot cave %s: FPU hazard at word %s"
                                 % (game, name, _fpu_hazards(words)))
            others = taken | {va for va, _w, _s, _n in uw + xleader_edits(game) + tppose_edits(game)}
            if others & {va for va, _w, _s, _n in be}:
                fails.append("%s: the blocked-shot routine overlaps the camera's other words" % game)
            if len({va for va, _w, _s, _n in be}) != len(be):
                fails.append("%s: the blocked-shot routine writes a word twice" % game)
            for va, _w, s, _n in be:
                if stock.get(va) != s:
                    fails.append("%s %08x: blocked edit stock %08x, table %s" % (game, va, s, stock.get(va)))
        if elf is not None:
            for va, want in stock.items():
                got = struct.unpack_from("<I", elf, va - 0x00100000 + delta)[0]
                if got != want:
                    fails.append("%s stock %08x: disc %08x, recorded %08x"
                                 % (game, va, got, want))
    return fails

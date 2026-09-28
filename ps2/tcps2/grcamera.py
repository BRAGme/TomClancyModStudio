"""Third-person camera for Ghost Recon (SLUS-20613) and Jungle Storm (SLUS-20820).

Neither game has a first-person weapon model, so the Rainbow Six 3 view-model
options have nothing to work on. What both games do have is a third-person
camera -- only for spectators. SimCamera::UpdateMovement forces a live
player's view back to first person every frame, and ToggleCameraView snaps
it to 0 as well; the third-person placement runs only after death.

This keeps the view a live player is in, draws the reticle, zoom panel and
action menu in third person too, places the camera with a height, sideways
and distance offset from the soldier's eye, and moves every shot's start
point onto the camera's centre line so the reticle is where the rounds go.

Placement (``cam_tp``, called from the view-1 block of
UpdateFollowerCameraMovement) builds the offset H up, L to the soldier's right
-- (ly, -lx, 0) normalised; Z is up and the engine is right-handed -- and D
back along the look vector, then runs the game's own SimCamera::PlaceCamera
sphere sweep from the eye, so walls pull the camera in exactly as they do for
the stock spectator camera. A floor probe keeps it 0.25 m above the ground.
The view looks along the soldier's look vector, parallel to the shot line.
While zoomed (field of view under 1.5 rad) or on a mounted gun it returns 0
and the stock first-person placement runs, so scopes and binoculars work.

``cam_tp`` also stores the camera's offset from the eye, less its component
along the look vector, in SimCamera+0x74 -- a spare vector only the
constructor writes. Two hooks in SimHuman::UpdateBurst use it: a free shot's
origin (the Gunshot message payload) moves by that offset, and a locked-on
shot aims from eye + offset instead of the camera. First-person play and AI
shooters are unchanged. "Shots from the eye" stores zero instead, leaving
free shots a fixed 0.2-0.5 m from the reticle.

The routines live in two library functions nothing calls: sceDevConsDraw
(GR 0x0040DA50, JS 0x00176300, 456 bytes) and sceVu0DropShadowMatrix
(GR 0x0042BC38, JS 0x001976C0, 400 bytes). Every stock word was checked
against the retail executables, and the routines were run in an interpreter
against RAM from single-player and split-screen savestates of both games
(PlaceCamera and the floor query stubbed without collision): camera position,
screen centre through the shot origin, look direction, zoom and mounted-gun
fallback, floor clamp and both split-screen cameras all checked. Not yet
played.
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
        ADDVEC=0x00359600,      # RSGameMessage::AddPayload(const RSVector3&)
        UB_MSG="s5", UB_ORG=0xE0, UB_SCR=0xD0,            # SimHuman::UpdateBurst frame
        CAVE_A=0x0040DA50, CAVE_A_BYTES=456,   # sceDevConsDraw, unreferenced
        CAVE_B=0x0042BC38, CAVE_B_BYTES=400,   # sceVu0DropShadowMatrix, unreferenced
    ),
    "js": dict(
        key="js",
        EYE=0x49C, LOOK=0x210, FOV=0x254, MANNED=0x5B8,
        PLACE=0x0038AC50,
        ISSNIPER=0x003BD860,    # the same test (motion types 2/3, zoom factor > 1.0)
        FLOOR=0x004C1830,
        SIMMGR=0x0062B8D0,
        ADDVEC=0x0014E0E0,
        UB_MSG="s0", UB_ORG=0xA0, UB_SCR=0xB0,
        CAVE_A=0x00176300, CAVE_A_BYTES=456,
        CAVE_B=0x001976C0, CAVE_B_BYTES=400,
    ),
}

#: height above the eye, distance to the right, distance back (metres)
PRESETS = {
    "centered": dict(H=0.35, L=0.0, D=2.75),
    "ots": dict(H=0.20, L=0.45, D=2.25),
    "ots_left": dict(H=0.20, L=-0.45, D=2.25),
}


def _cam_tp_src(g, H, L, D, aim_cam):
    E, K = g["EYE"], g["LOOK"]
    d3 = "swc1  $f3" if aim_cam else "sw    zero"
    d4 = "swc1  $f4" if aim_cam else "sw    zero"
    d5 = "swc1  $f5" if aim_cam else "sw    zero"
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
    jal   FLOORCLAMP                 ; camera >= floor + 0.25
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
    lwc1  $f3, 0x10(s0)              ; d = camera - eye
    lwc1  $f6, {E:#x}(t0)
    sub.s $f3, $f3, $f6
    lwc1  $f4, 0x14(s0)
    lwc1  $f6, {E + 4:#x}(t0)
    sub.s $f4, $f4, $f6
    lwc1  $f5, 0x18(s0)
    lwc1  $f6, {E + 8:#x}(t0)
    sub.s $f5, $f5, $f6
    mul.s $f6, $f3, $f0              ; t = d . look
    mul.s $f7, $f4, $f1
    add.s $f6, $f6, $f7
    mul.s $f7, $f5, $f2
    add.s $f6, $f6, $f7
    mul.s $f7, $f6, $f0              ; delta = d - t*look -> SimCamera+0x74
    sub.s $f3, $f3, $f7
    {d3}, 0x74(s0)
    mul.s $f7, $f6, $f1
    sub.s $f4, $f4, $f7
    {d4}, 0x78(s0)
    mul.s $f7, $f6, $f2
    sub.s $f5, $f5, $f7
    {d5}, 0x7c(s0)
    b     out
    addiu v0, zero, 1
zoomed:
    sw    zero, 0x74(s0)
    sw    zero, 0x78(s0)
    sw    zero, 0x7c(s0)
    addiu v0, zero, 0
out:
    ld    ra, 0x30(sp)
    lq    s0, 0x20(sp)
    jr    ra
    addiu sp, sp, 0x40
"""


def _cave_b_src(g):
    E, O, S = g["EYE"], g["UB_ORG"], g["UB_SCR"]
    return f"""
aim_from:                            ; replaces SimCamera::GetLocation for a locked-on shot
    lw    v1, 0x70(a0)
    addiu t0, zero, 1
    bne   v1, t0, af_ret
    addiu v0, a0, 0x10               ; not third person: the stock answer
    lw    t0, 4(a0)                  ; third person: eye + delta, in the caller's free temp
    lwc1  $f0, {E:#x}(t0)
    lwc1  $f1, 0x74(a0)
    lwc1  $f2, {E + 4:#x}(t0)
    add.s $f0, $f0, $f1
    lwc1  $f3, 0x78(a0)
    swc1  $f0, {S:#x}(sp)
    add.s $f2, $f2, $f3
    lwc1  $f0, {E + 8:#x}(t0)
    lwc1  $f1, 0x7c(a0)
    swc1  $f2, {S + 4:#x}(sp)
    add.s $f0, $f0, $f1
    addiu v0, sp, {S:#x}
    swc1  $f0, {S + 8:#x}(sp)
af_ret:
    jr    ra
    nop

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

shot_origin:                         ; a0 = shooter: move the Gunshot origin onto the camera line
    lui   t0, %hi(SIMMGR)
    lw    t0, %lo(SIMMGR)(t0)
    beqz  t0, so_done
    nop
    lw    t1, 0x444(t0)              ; GetSimCamera
    beqz  t1, so_cam2
    nop
    lw    t2, 4(t1)
    beq   t2, a0, so_found
    nop
so_cam2:
    lw    t1, 0x448(t0)              ; GetSimCamera2
    beqz  t1, so_done
    nop
    lw    t2, 4(t1)
    bne   t2, a0, so_done
    nop
so_found:
    lw    t2, 0x70(t1)
    addiu t3, zero, 1
    bne   t2, t3, so_done
    nop
    lwc1  $f0, {O:#x}(sp)
    lwc1  $f1, 0x74(t1)
    lwc1  $f2, {O + 4:#x}(sp)
    add.s $f0, $f0, $f1
    lwc1  $f3, 0x78(t1)
    swc1  $f0, {O:#x}(sp)
    add.s $f2, $f2, $f3
    lwc1  $f0, {O + 8:#x}(sp)
    lwc1  $f1, 0x7c(t1)
    swc1  $f2, {O + 4:#x}(sp)
    add.s $f0, $f0, $f1
    nop
    swc1  $f0, {O + 8:#x}(sp)
so_done:
    move  a0, {g['UB_MSG']}
    j     ADDVEC
    addiu a1, sp, {O:#x}
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
                (0x003D2C3C, 0x0C0E27D8, jal(lb["aim_from"]), "locked-on shot (player 1) aims from the camera line"),
                (0x003D2D0C, 0x0C0E27D8, jal(lb["aim_from"]), "locked-on shot (player 2) aims from the camera line"),
                (0x003D2DE8, 0x72A02628, jal(lb["shot_origin"]), "shot origin onto the camera line"),
                (0x003D2DEC, 0x0C0D6580, 0x0280202D, "shot origin: a0 = shooter"),
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
            (0x003B22C8, 0x0C0D9E7C, jal(lb["aim_from"]), "locked-on shot (player 1) aims from the camera line"),
            (0x003B2398, 0x0C0D9E7C, jal(lb["aim_from"]), "locked-on shot (player 2) aims from the camera line"),
            (0x003B2474, 0x0200202D, jal(lb["shot_origin"]), "shot origin onto the camera line"),
            (0x003B2478, 0x0C053838, 0x02A0202D, "shot origin: a0 = shooter"),
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


def _stock_table(game):
    g = GAMES[game]
    t = _stock_words(g["CAVE_A"], _DEVCONS[game])
    t.update(_stock_words(g["CAVE_B"], _DROPSHADOW))
    for rows in _patches(g, g["CAVE_A"], {"aim_from": g["CAVE_B"],
                                          "shot_origin": g["CAVE_B"]}).values():
        for va, stock, _new, _note in rows:
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


#: camera distance choices (metres back from the eye); "preset" keeps the preset's
DISTANCES = ("preset", "1.75", "2.0", "2.25", "2.5", "2.75", "3.0")


def build(game, preset, aim_cam=True, distance="preset"):
    """(words_a, labels_a, words_b, labels_b, patches) for a preset."""
    g = GAMES[game]
    p = dict(PRESETS[preset])
    if distance not in (None, "preset"):
        p["D"] = float(distance)
    syms = {"PLACE": g["PLACE"], "SIMMGR": g["SIMMGR"], "ADDVEC": g["ADDVEC"],
            "FLOOR": g["FLOOR"], "ISSNIPER": g["ISSNIPER"]}
    wb, lb = assemble(_cave_b_src(g), g["CAVE_B"], syms)
    syms["FLOORCLAMP"] = lb["floor_clamp"]
    wa, la = assemble(_cam_tp_src(g, p["H"], p["L"], p["D"], aim_cam), g["CAVE_A"], syms)
    if len(wa) * 4 > g["CAVE_A_BYTES"] or len(wb) * 4 > g["CAVE_B_BYTES"]:
        raise ValueError("%s camera routines overflow their caves" % game)
    return wa, la, wb, lb, _patches(g, g["CAVE_A"], lb)


def edits(game, preset, aim_eye=False, distance="preset"):
    """[(va, value, stock, note)]; preset 'off' (or anything unknown) = none."""
    if preset not in PRESETS:
        return []
    g = GAMES[game]
    stock = GR_STOCK if game == "gr" else JS_STOCK
    wa, _la, wb, _lb, groups = build(game, preset, aim_cam=not aim_eye, distance=distance)
    out = []
    for base, words, where in ((g["CAVE_A"], wa, "sceDevConsDraw"),
                               (g["CAVE_B"], wb, "sceVu0DropShadowMatrix")):
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
                v.get(p + "tp_distance", "preset"))
    # third person cannot work without it: any first-person frame hides him for good
    if v.get(p + "tp_camera", "off") in PRESETS or v.get(p + "show_soldiers"):
        out += unhide_edits(game)
    if v.get(p + "tp_camera", "off") in PRESETS:
        out += xleader_edits(game)
        out += tppose_edits(game)
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
        for preset in PRESETS:
            for aim_eye in (False, True):
                wa, _la, wb, _lb, _p = build(game, preset, not aim_eye)
                sizes.add((len(wa), len(wb)))
                for name, words in (("A", wa), ("B", wb)):
                    if _fpu_hazards(words):
                        fails.append("%s %s cave %s: FPU hazard at word %s"
                                     % (game, preset, name, _fpu_hazards(words)))
                seen = set()
                for va, _w, s, _note in edits(game, preset, aim_eye):
                    if va in seen:
                        fails.append("%s %08x written twice" % (game, va))
                    seen.add(va)
                    if stock.get(va) != s:
                        fails.append("%s %08x: edit stock %08x, table %s"
                                     % (game, va, s, stock.get(va)))
        if len(sizes) != 1:
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
        if elf is not None:
            for va, want in stock.items():
                got = struct.unpack_from("<I", elf, va - 0x00100000 + delta)[0]
                if got != want:
                    fails.append("%s stock %08x: disc %08x, recorded %08x"
                                 % (game, va, got, want))
    return fails

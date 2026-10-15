"""Hold the quick-order button: a teammate throws a grenade there (Jungle Storm, Ghost Recon).

What the player gets
--------------------

The quick-order button (R2 on Jungle Storm's layouts and on Ghost Recon with Jungle Storm's
layout; R3 on Ghost Recon's own) is tapped for Hold / Advance and held for "move to" -- in Jungle
Storm's online co-op (grcooporders, js_coop_orders) and in split screen (grsquad 'orders',
js_ss_orders / gr_ss_orders). ``js_r2_hold`` / ``gr_r2_hold`` choose what the HOLD does:

* ``move`` (the default) -- the move-to, exactly as before: not one word of the disc changes.
* ``frag`` -- on release, one AI teammate of your fireteam throws a frag grenade at the point
  you aimed at (online: the marker's point; split screen: the spot under the crosshair).
* ``smoke`` -- the same with a smoke grenade (needs 'Smoke grenades' with 'AI throws smoke' set
  to anything but Never; without them ``smoke`` is ``move``).

A tap is untouched: it still toggles Hold / Advance (grcooporders' co_order and grsquad's ``ord``
send the tap exactly as before; only the long-press branch changes).

Who throws. Of your fireteam's soldiers the routine considers the AI (SimHuman +0x138 == 1:
neither you nor, online, the other player's network copy) that are not out of action (SimHuman
vtable IsOutOfAction, GR +0x298 / JS +0x29C -- the test grsquad's orders use) and carry a grenade
of the kind: thrown items (ThrownItem vtable GR 0x00597E60 / JS 0x005A75B0) in inventory slots 0
and 1 -- the two slots HumanAI::GetNumGrenades counts -- whose projectile (+8) is FRAG (GR 3,
JS 4), or for ``smoke`` FRAG or SMOKE (GR 8, JS 9; a frag thrown under a smoke mark comes out as
smoke). For ``frag`` a grenade launcher with rounds (HumanAI::HasGrenadeLauncher) also counts:
the game's FragLocationBehavior fires the launcher at the point instead of throwing. For
``smoke`` a launcher rules him out -- the behaviour would fire a live 40 mm round, which no mark
turns into smoke (grsmoke's own AI smoke has the same rule). Of those, the one standing NEAREST
THE POINT throws (the shortest throw; a hand throw carries about 36 m, more with 'Enemies throw
grenades' range, whose stronger throw applies to every AI). There is no "selected teammate" for
the quick order in either game, and while the button is held you are aiming at the target, not
at a teammate, so nearest-with-a-grenade is the rule.

In the savestates of Jungle Storm's co-op AI backup, a fireteam's two AI carry a rifle with a grenade
launcher (5 rounds) and no grenade at all: there ``frag`` makes the grenadier fire his launcher at
the point and ``smoke`` finds nobody (smoke needs a kit with grenades -- 'Smoke grenade kits' gives
some classes smoke; the split-screen save's fireteams had two smoke carriers each).

Nobody qualifies (no AI left, nobody carrying one, everybody out of action): nothing happens --
nobody is sent toward the point, Hold / Advance stays as it was, and no grenade is spent. The
marker and the setup sound still come (they are the ordering console's own, before the host
decides).

The throw is the game's own: a FragLocationBehavior (JS ctor 0x001B0720 / GR 0x001B4650, 0x34
bytes, aim at +0x1C, level +0x2C found at the throw) pushed on top of the thrower's script
(RSScript::AddElement on HumanAI +0x0C), exactly how grsmoke's AI smoke and grfrag's enemy
grenades queue theirs. FragLocationBehavior::Process (JS 0x001B0820, GR 0x001B4270) stands him
up, picks the grenade (HumanAI +0xA0 +8 = 3), turns him to the arc HumanAI::GetFacingForProjectile
picks, drops the throw if its first 10 m are blocked (FragLOSBlocked; 4 m with 'Enemies throw
grenades', none for smoke under grsmoke's hook), then asks FireTeamAI::IsOkToFragHereNow and
presses use (UseItem; a hand throw holds it 1 s). The release is HumanMotion::HandleThrowItem (JS
0x00338EA0, its release block 0x003394F8; GR 0x0035D3A0): it sends ControllerThrewItem (JS 0x20B / GR 0x1B1) to the MASTER
(SendMaster, JS 0x00339628 / GR 0x0035D9E8) and DecrementCount's the item (JS 0x00339678 / GR
0x0035DA38) -- that is where the grenade is consumed; the order spends none of its own, so a
throw that is dropped costs nothing. When he is done the behaviour leaves the script and he goes
back to following or holding.

IsOkToFragHereNow refuses a frag when the TEAM threw one in the last 30 s (FireTeamAI +0xEC, set
by ReportGrenadeUse) and when a friendly stands within 15 m of the point outdoors, or anywhere
in the same room indoors. The first is pacing for the AI's own grenades, so a ``frag`` order sets
the thrower's team clock to long ago (-9.98e8 s) when it queues the throw -- your order is
obeyed now; the throw itself stamps the clock again. The second is kept: a frag ordered next to
you or your teammates is not thrown. ``smoke`` marks the thrower in grsmoke's ring (smk_marks:
{SimHuman, until}, 4 slots, 10 s -- the mark grsmoke's running-for-cover smoke writes), so
grsmoke's hooks make his frag leave as smoke (smk_idx, at the release), skip the blast and arc
checks (smk_ok, smk_arc) and the team clock (smk_rep). grsmoke's 15 s / two-cloud gate is for the
AI's own smoke; an ordered smoke is the player's, like his own throws.

Online co-op: the host throws, every console sees it
----------------------------------------------------

The ordering console (host or joiner) already posts the move-to as AddWaypoint 0x20E with all
seven payloads {company, platoon, fireteam + 0x10, point, -1, 0.0, true}, to the consoles that
run the company and to the host (grcooporders co_order). With ``frag`` / ``smoke`` it posts the
same message with fireteam + 0x20 (TEAM_NADE); everything else about the message is unchanged
(the waypoint-statistics handler 0x00347E70 still reads payload 6 = true and skips it).

Only the host has FireTeamAI objects. On the host IkeAIMgr::HandleAddWaypoint (0x003F2DA0)
reads the payloads into s1 (company), s0 (platoon), s4 (fireteam, raw: 0x003F2E44 / 0x003F2E80
``move a3, s4``) and the point (sp+0x70), and its GetFireTeamAI call goes through grcooporders'
``disp``. In a grenade build ``disp`` looks the fireteam up by the low nibble (``andi a3, a3,
0xf`` for ``addiu a3, a3, -0x10``) and calls ``nade_disp`` here instead of ``mv``: s4 (callee-
saved, untouched by GetFireTeamAI) still holds the raw value, so fireteam + 0x10 goes on to
``mv`` (a move-to from a console built with ``move`` is still obeyed) and fireteam + 0x20 raises
the point 0.4 m (grcooporders' LIFT: FindLevel sees the floor from above, as mv does) and calls
``nade``. ``disp`` then returns 0, so no waypoint is added. On every other console the lookup
answers 0 (the joiner has no FireTeamAI: IkeAIMgr vt+0x14 is 0 for every fireteam) and ``nade``
returns at once: no console but the host changes anything.

What follows is the game's own AI throw, simulated on the host like every AI action: the
thrower's HumanMotion releases on the host, ControllerThrewItem goes to the master (the host
itself), the host creates the projectile, and the projectile reaches the joiners the way every
AI grenade does (enemy grenades online take this path). Nothing here draws a random number or
spawns anything: the choice of thrower is the nearest-distance rule on host state, the timers in
FragLocationBehavior are the host's own as for any AI grenade. A stock host ignores the order (no
fireteam 0x20+); a host built with ``move`` looks up fireteam 0x10+ft, finds none, and ignores it
too. Every console should carry the same settings, as for every co-op option.

Split screen
------------

grsquad's ``ord`` (the 0x22 handler's split-screen path) sends a long press to ``mv`` (FireTeamAI,
ordering SimHuman). In a grenade build that one call goes to ``nade_ss``, which finds the point
exactly as ``mv`` does -- RSSimRoom::FindLineCollision from the player's eye (SimHuman GR +0x478 /
JS +0x49C) along his look vector (+0x210) for 100 m, nothing nearer than 2 m, pulled back 0.75 m
from the surface and raised 0.4 m (grsquad MV_*) -- and calls ``nade``. No SetLocation: a grenade
needs no standing room, only a level, which FragLocationBehavior finds itself (no level: no
throw). Both players' orders reach only their own fireteam (grsquad's lookup by the avatar id).

The patch
---------

  grcooporders (online, JS): co_order's ``li s2, TEAM_MOVE`` -> ``li s2, TEAM_NADE``; disp's
  ``addiu a3, a3, -0x10`` -> ``andi a3, a3, 0xf`` and ``jal mv`` -> ``jal nade_disp``. Three
  words in caves grcooporders already owns; with ``move`` none of them changes.
  grsquad (split screen): ``ord``'s ``jal mv`` -> ``jal nade_ss``. One word in grsquad's orders
  cave; with ``move`` none changes.
  This module: ``nade`` (+ ``nade_disp`` in JS) in the first cave, ``nade_ss`` in the second.

Caves (unreferenced from live code: no jal/j, branch, pointer or lui+low-half pair reaches them, in
the image or, for JS, either overlay, except from functions that are themselves dead -- the rest of
the same library family, which only dead code calls; no other option writes them):

  JS 0x001770B0..0x00177314  the head of sceDevFontRefDirectImage + sceDevFontRefStrN (twins of GR's,
                             below); referenced from 0x001762BC, 0x00176414, 0x001765C0 (sceDevCons*),
                             0x00177848 (sceDevFont, grsplat's cave) and RefStrN's own tail
                             (0x00177330, 0x00177358).
  JS 0x00181C00..0x00181D34  the head of _sceSifLoadModuleBuffer's twin; referenced from 0x001821D8 /
                             0x001821F8 in the dead sceSifLoadModuleBuffer wrappers.
  GR 0x0040E800..0x0040EA34  the head of sceDevFontRefDirectImage + sceDevFontRefStrN; referenced from
                             sceDevConsRef / Draw / DrawS (0x0040DA0C, 0x0040DB64, 0x0040DD10),
                             sceDevFont (0x0040EF98) and RefStrN's tail (0x0040EA80, 0x0040EAA8).
  GR 0x00418EF0..0x00419024  the head of _sceSifLoadModuleBuffer; referenced from sceSifLoadModuleBuffer
                             / sceSifLoadStartModuleBuffer (0x004194C8, 0x004194E8).

Verified in the RAM interpreter over savestates -- see the report; not yet played.
"""

from __future__ import annotations

import struct

from .grasm import assemble
from .model import CHOICE, Choice, Setting

MODES = ("move", "frag", "smoke")
TEAM_NADE = 0x20        # added to the fireteam index of an online AddWaypoint that means "grenade there"
LIFT = 0.40             # m: the online point is raised as grcooporders' mv raises it
NEAR_BIG = 0x7F7F       # upper half of the first "nearest so far" distance^2 (3.4e38)
LONG_AGO = 0xCE6E       # upper half of -9.98e8 s: the team's last grenade, for an ordered frag
MARK_LIFE = 0x4120      # upper half of 10.0 s: a smoke mark, as grsmoke's own


def _hi(x):
    return struct.unpack("<I", struct.pack("<f", x))[0] >> 16


# ---- per game ---------------------------------------------------------------------------------
G = {
    "JS": dict(
        CAVE=0x001770B0, CAVE_END=0x00177314,          # nade (+ nade_disp): 153 words at most (smoke)
        CAVE2=0x00181C00, CAVE2_END=0x00181D34,        # nade_ss: 77 words
        NEW=0x00103470, FRAGCTOR=0x001B0720, ADDELEM=0x001B6E10, HASLAUNCHER=0x003EA140,
        CLOCK=0x00684768, THROWN_VT=0x005A75B0, FLC=0x004C40E0,
        INV=0x514, CNT=0x18, VOUT=0x29C, FRAG=4, SMOKE=9, EYE=0x49C, LOOK=0x210, VEC=0x10,
    ),
    "GR": dict(
        CAVE=0x0040E800, CAVE_END=0x0040EA34,          # nade: 141 words at most (smoke)
        CAVE2=0x00418EF0, CAVE2_END=0x00419024,        # nade_ss: 77 words
        NEW=0x00102DB0, FRAGCTOR=0x001B4650, ADDELEM=0x001BAEC0, HASLAUNCHER=0x0019A180,
        CLOCK=0x005DFC20, THROWN_VT=0x00597E60, FLC=0x004D8540,
        INV=0x4F4, CNT=0x10, VOUT=0x298, FRAG=3, SMOKE=8, EYE=0x478, LOOK=0x210, VEC=0x0C,
    ),
}

# ---- nade: a0 = FireTeamAI (0: none), a1 = the aim point. Picks the thrower, queues the throw.
SRC_NADE = """
nade:
    addiu sp, sp, -0x80
    sd    ra, 0x70(sp)
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s2, 0x20(sp)
    sq    s3, 0x30(sp)
    sq    s4, 0x40(sp)
    sq    s5, 0x50(sp)
    move  s0, a0
    beqz  s0, n_out                   ; no fireteam here (a joiner, or none): nothing
    move  s1, a1
    move  s2, zero                    ; member index
    move  s3, zero                    ; the thrower so far
    lui   t0, {NEAR_BIG:#x}
    sw    t0, 0x60(sp)                ; his distance^2 to the point
n_loop:
    lw    t0, 0x18(s0)                ; member count
    slt   t0, s2, t0
    beqz  t0, n_pick
    lw    t1, 0x14(s0)                ; RSArray<HumanAI*> data
    sll   t0, s2, 2
    addu  t1, t1, t0
    lw    s4, 0(t1)                   ; HumanAI
    beqz  s4, n_loop
    addiu s2, s2, 1
    lw    s5, 0x14(s4)                ; its SimHuman
    beqz  s5, n_loop
    nop
    lw    t1, 0x138(s5)               ; control type: 1 = AI (not you, not the other player)
    li    t2, 1
    bne   t1, t2, n_loop
    nop
    lw    t9, 0(s5)
    lw    t9, {VOUT:#x}(t9)           ; IsOutOfAction()
    jalr  t9
    move  a0, s5
    bnez  v0, n_loop
    sw    zero, 0x64(sp)              ; grenades of the kind he carries
    sw    zero, 0x68(sp)              ; inventory slot (0 and 1, as GetNumGrenades counts)
n_slot:
    lw    t9, {INV:#x}(s5)            ; the inventory: vt+0x2C GetItem(slot)
    lw    a1, 0x68(sp)
    lw    t9, 0x2c(t9)
    jalr  t9
    addiu a0, s5, {INV:#x}
    beqz  v0, n_next
    lui   t0, %hi(THROWN_VT)
    addiu t0, t0, %lo(THROWN_VT)
    lw    t1, 0(v0)
    bne   t1, t0, n_next              ; not a thrown item
    lhu   t1, 8(v0)                   ; its projectile
    lw    t2, {CNT:#x}(v0)            ; how many
    li    t0, {FRAG}
    beq   t1, t0, n_add
    li    t0, {OTHER}                 ; frag: only frags count; smoke: smoke too
    bne   t1, t0, n_next
    nop
n_add:
    lw    t0, 0x64(sp)
    addu  t0, t0, t2
    sw    t0, 0x64(sp)
n_next:
    lw    t0, 0x68(sp)
    addiu t0, t0, 1
    sltiu t1, t0, 2
    bnez  t1, n_slot
    sw    t0, 0x68(sp)
    jal   HASLAUNCHER
    move  a0, s4
    andi  v0, v0, 0xff
{LAUNCHER}
    lw    t0, 0x64(sp)
    blez  t0, n_loop                  ; no grenade of the kind
    nop
n_dist:
    lwc1  $f0, 0x2c(s4)               ; his position
    lwc1  $f3, 0(s1)
    sub.s $f0, $f0, $f3
    lwc1  $f1, 0x30(s4)
    lwc1  $f3, 4(s1)
    sub.s $f1, $f1, $f3
    lwc1  $f2, 0x34(s4)
    lwc1  $f3, 8(s1)
    sub.s $f2, $f2, $f3
    mul.s $f0, $f0, $f0
    mul.s $f1, $f1, $f1
    mul.s $f2, $f2, $f2
    add.s $f0, $f0, $f1
    add.s $f0, $f0, $f2               ; his distance^2 to the point
    lwc1  $f1, 0x60(sp)
    c.lt.s $f0, $f1
    bc1f  n_loop                      ; not nearer than the best so far
    nop
    swc1  $f0, 0x60(sp)
    b     n_loop
    move  s3, s4                      ; the nearest so far
n_pick:
    beqz  s3, n_out                   ; nobody carries one: no order at all
    nop
    jal   NEW
    li    a0, 0x34
    beqz  v0, n_out
    nop
    jal   FRAGCTOR                    ; FragLocationBehavior (state 0, level 0: found at the throw)
    move  a0, v0
    move  s4, v0
    lw    t0, 0(s1)
    lw    t1, 4(s1)
    lw    t2, 8(s1)
    sw    t0, 0x1c(s4)                ; aimed at the point
    sw    t1, 0x20(s4)
    sw    t2, 0x24(s4)
    lw    a0, 0xc(s3)                 ; his script:
    jal   ADDELEM                     ;   on top -- he throws, then goes back to what he was doing
    move  a1, s4
{AFTER}
n_out:
    ld    ra, 0x70(sp)
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    lq    s3, 0x30(sp)
    lq    s4, 0x40(sp)
    lq    s5, 0x50(sp)
    jr    ra
    addiu sp, sp, 0x80
"""

_LAUNCHER = {
    "frag": "    bnez  v0, n_dist                  ; a launcher with rounds: he fires it at the point\n"
            "    nop",
    "smoke": "    bnez  v0, n_loop                  ; a launcher would fire a live round, not smoke\n"
             "    nop",
}
_AFTER = {
    "frag": """
    lw    t1, 0xa4(s3)                ; his fireteam: its last grenade long ago, so the 30 s
    beqz  t1, n_out                   ;   wait for the AI's own grenades does not hold the order
    lui   t0, {LONG_AGO:#x}
    sw    t0, 0xec(t1)
""",
    "smoke": """
    lui   t0, %hi(CLOCK)              ; mark him for smoke in grsmoke's ring for 10 s (his own,
    lw    t0, %lo(CLOCK)(t0)          ;   an expired or slot 0, as grsmoke marks its own)
    lwc1  $f0, 0xd4(t0)               ; now
    lw    s5, 0x14(s3)                ; marks are kept by SimHuman
    lui   t1, %hi(MARKS)
    addiu t1, t1, %lo(MARKS)
    move  t4, t1
    li    t2, 4
nm_slot:
    lw    t3, 0(t1)
    beq   t3, s5, nm_put
    lwc1  $f1, 4(t1)
    c.lt.s $f1, $f0
    bc1t  nm_put                      ; expired (or never used)
    addiu t2, t2, -1
    bnez  t2, nm_slot
    addiu t1, t1, 8
    move  t1, t4
nm_put:
    lui   t0, {MARK_LIFE:#x}
    mtc1  t0, $f1
    sw    s5, 0(t1)
    add.s $f1, $f0, $f1
    swc1  $f1, 4(t1)
""",
}

# ---- nade_disp (JS online, the host): disp's call in place of mv
SRC_DISP = """
nade_disp:                            ; a0 = the fireteam (0: none), a1 = the point (HandleAddWaypoint's
    sltiu t0, s4, {TEAM_NADE:#x}      ;   sp+0x70); s4 = the raw fireteam payload (0x10+ or 0x20+)
    bnez  t0, nd_move
    nop
    lwc1  $f0, 8(a1)
    lui   at, {LIFT_HI:#x}
    mtc1  at, $f1
    nop
    add.s $f0, $f0, $f1
    j     nade                        ; raised, so FindLevel sees the floor from above
    swc1  $f0, 8(a1)
nd_move:
    j     MV                          ; fireteam + 0x10: a move-to, as before
    nop
"""

# ---- nade_ss (split screen): the point mv would find, then nade
SRC_SS = """
nade_ss:                              ; a0 = FireTeamAI, a1 = the ordering player's SimHuman
    addiu sp, sp, -{F:#x}
    sd    ra, 0x60(sp)
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    move  s0, a0
    move  s1, a1
    lw    a0, 0x38(s1)                   ; RSSimController::GetSimRoom
    beqz  a0, ns_out
    lw    t0, {EYE:#x}(s1)               ; RSLine3: the eye, along the look vector
    lw    t1, {EYE4:#x}(s1)
    lw    t2, {EYE8:#x}(s1)
    sw    t0, {LINE:#x}(sp)
    sw    t1, {LINE4:#x}(sp)
    sw    t2, {LINE8:#x}(sp)
    lw    t0, {LOOK:#x}(s1)
    lw    t1, {LOOK4:#x}(s1)
    lw    t2, {LOOK8:#x}(s1)
    sw    t0, {LV:#x}(sp)
    sw    t1, {LV4:#x}(sp)
    sw    t2, {LV8:#x}(sp)
    addiu a1, sp, {LINE:#x}
    addiu a2, sp, {INFO:#x}              ; RSLineCollisionInfo
    move  a3, zero                       ; no shooter
    addiu t0, zero, 0x81a                ; kIsGunshot | kLineIgnoreAllControllers
    addiu t1, zero, 1                    ; kGunshotTransparent
    move  t2, zero
    lui   at, {REACH_HI:#x}
    mtc1  at, $f12
    jal   FLC                            ; RSSimRoom::FindLineCollision
    move  t3, zero
    andi  v0, v0, 0xff
    beqz  v0, ns_out                     ; nothing within reach: no order
    lwc1  $f0, {HIT:#x}(sp)              ; hit point (info+0x10)
    lwc1  $f1, {HIT4:#x}(sp)
    lwc1  $f2, {HIT8:#x}(sp)
    lwc1  $f3, {LINE:#x}(sp)             ; eye
    lwc1  $f4, {LINE4:#x}(sp)
    lwc1  $f5, {LINE8:#x}(sp)
    lwc1  $f6, {LV:#x}(sp)               ; look
    lwc1  $f7, {LV4:#x}(sp)
    lwc1  $f8, {LV8:#x}(sp)
    sub.s $f0, $f0, $f3
    sub.s $f1, $f1, $f4
    sub.s $f2, $f2, $f5
    mul.s $f0, $f0, $f6
    mul.s $f1, $f1, $f7
    mul.s $f2, $f2, $f8
    add.s $f0, $f0, $f1
    add.s $f0, $f0, $f2                  ; t = distance along the ray
    lui   at, {MINT_HI:#x}
    mtc1  at, $f9
    lui   at, {BACK_HI:#x}
    mtc1  at, $f10
    c.lt.s $f0, $f9
    nop
    bc1t  ns_out                         ; closer than MIN_T: not an order
    sub.s $f0, $f0, $f10                 ; pulled back from the surface
    mul.s $f6, $f6, $f0
    mul.s $f7, $f7, $f0
    mul.s $f8, $f8, $f0
    lui   at, {LIFT_HI:#x}
    mtc1  at, $f9
    add.s $f3, $f3, $f6
    add.s $f4, $f4, $f7
    add.s $f5, $f5, $f8
    add.s $f5, $f5, $f9                  ; and lifted, so the floor lookup sees it from above
    swc1  $f3, {PT:#x}(sp)
    swc1  $f4, {PT4:#x}(sp)
    swc1  $f5, {PT8:#x}(sp)
    move  a0, s0
    jal   NADE                           ; the throw
    addiu a1, sp, {PT:#x}
ns_out:
    ld    ra, 0x60(sp)
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    jr    ra
    addiu sp, sp, {F:#x}
"""


def _ss_src(g):
    from . import grsquad as q
    V = g["VEC"]
    F, LINE, INFO, PT = q._MV_F, q._MV_LINE, q._MV_INFO, q._MV_PT
    return SRC_SS.format(
        F=F, LINE=LINE, LINE4=LINE + 4, LINE8=LINE + 8, LV=LINE + V, LV4=LINE + V + 4, LV8=LINE + V + 8,
        INFO=INFO, HIT=INFO + 0x10, HIT4=INFO + 0x14, HIT8=INFO + 0x18, PT=PT, PT4=PT + 4, PT8=PT + 8,
        EYE=g["EYE"], EYE4=g["EYE"] + 4, EYE8=g["EYE"] + 8,
        LOOK=g["LOOK"], LOOK4=g["LOOK"] + 4, LOOK8=g["LOOK"] + 8,
        REACH_HI=_hi(q.MV_REACH), MINT_HI=_hi(q.MV_MIN_T), BACK_HI=_hi(q.MV_BACK), LIFT_HI=_hi(q.MV_LIFT))


def _marks(game):
    """grsmoke's mark ring for the game (its address does not depend on any smoke setting)."""
    from . import grsmoke
    if game == "JS":
        return grsmoke.assemble_ai()[1]["smk_marks"]
    return grsmoke.gr_assemble()[1]["smk_marks"]


def _nade_src(game, mode):
    g = G[game]
    return SRC_NADE.format(
        NEAR_BIG=NEAR_BIG, VOUT=g["VOUT"], INV=g["INV"], CNT=g["CNT"], FRAG=g["FRAG"],
        OTHER=g["FRAG"] if mode == "frag" else g["SMOKE"], LAUNCHER=_LAUNCHER[mode],
        AFTER=_AFTER[mode].format(LONG_AGO=LONG_AGO, MARK_LIFE=MARK_LIFE))


def build(game, mode):
    """{base: words}, labels for the game's grenade order (mode 'frag' or 'smoke')."""
    if mode not in ("frag", "smoke"):
        raise ValueError("grenade order mode %r" % mode)
    g = G[game]
    syms = {k: g[k] for k in ("NEW", "FRAGCTOR", "ADDELEM", "HASLAUNCHER", "CLOCK", "THROWN_VT", "FLC")}
    if mode == "smoke":
        syms["MARKS"] = _marks(game)
    src1 = (SRC_DISP.format(TEAM_NADE=TEAM_NADE, LIFT_HI=_hi(LIFT)) if game == "JS" else "") \
        + _nade_src(game, mode)
    if game == "JS":
        from . import grcooporders
        syms["MV"] = grcooporders.build()[3]["mv"]
    w1, l1 = assemble(src1, g["CAVE"], dict(syms, NADE=g["CAVE"]))
    w2, l2 = assemble(_ss_src(g), g["CAVE2"], dict(syms, NADE=l1["nade"]))
    if g["CAVE"] + 4 * len(w1) > g["CAVE_END"]:
        raise ValueError("%s grenade order: %d words, room %d" % (game, len(w1), (g["CAVE_END"] - g["CAVE"]) // 4))
    if g["CAVE2"] + 4 * len(w2) > g["CAVE2_END"]:
        raise ValueError("%s grenade order (split screen): %d words, room %d"
                         % (game, len(w2), (g["CAVE2_END"] - g["CAVE2"]) // 4))
    return {g["CAVE"]: w1, g["CAVE2"]: w2}, dict(l1, **l2)


#: entry points (fixed: each sits at the start of its cave, whatever the mode)
JS_NADE_DISP = G["JS"]["CAVE"]
JS_NADE_SS = G["JS"]["CAVE2"]
GR_NADE_SS = G["GR"]["CAVE2"]


def _mode(v, p, smoke_key, smoke_ai_key):
    m = v.get(p + "r2_hold", "move")
    if m not in MODES:
        return "move"
    if m == "smoke" and not (v.get(smoke_key) and v.get(smoke_ai_key, "all") != "off"):
        return "move"          # no smoke grenade (or no smoke marks): the hold stays a move-to
    return m


def js_mode(v: dict) -> str:
    """The hold's effective order for Jungle Storm: 'move', 'frag' or 'smoke'."""
    return _mode(v, "js_", "js_smoke", "js_smoke_ai")


def gr_mode(v: dict) -> str:
    """The hold's effective order for Ghost Recon split screen."""
    return _mode(v, "gr_", "gr_smoke", "gr_smoke_ai")


def _ss_on(v, p):
    return bool(v.get(p + "ss_orders") and v.get(p + "ss_fireteams") and v.get(p + "ss_handoff"))


def _edits(game, mode, parts):
    blocks, labels = build(game, mode)
    g = G[game]
    st = JS_STOCK if game == "JS" else GR_STOCK
    out = []
    w1 = blocks[g["CAVE"]]
    if "disp" in parts or "nade" in parts:
        start = 0 if "disp" in parts else (labels["nade"] - g["CAVE"]) // 4
        out += [(g["CAVE"] + 4 * i, w, st[g["CAVE"] + 4 * i],
                 "grenade order: %s picks the nearest teammate with one and queues the throw" % mode)
                for i, w in enumerate(w1) if i >= start]
    if "ss" in parts:
        out += [(g["CAVE2"] + 4 * i, w, st[g["CAVE2"] + 4 * i],
                 "grenade order: split screen's aim point (as the move-to finds it)")
                for i, w in enumerate(blocks[g["CAVE2"]])]
    return out


def js_edits(v: dict) -> list:
    """(va, value, stock, note): the routines for js_r2_hold; [] for 'move' or with no quick orders on.
    grcooporders.js_edits(v) and grsquad.js_edits(..., r2_hold=js_mode(v)) carry the call sites."""
    mode = js_mode(v)
    if mode == "move":
        return []
    parts = set()
    if v.get("js_coop_orders"):
        parts |= {"disp", "nade"}
    if _ss_on(v, "js_"):
        parts |= {"ss", "nade"}
    return _edits("JS", mode, parts) if parts else []


def gr_edits(v: dict) -> list:
    """(va, value, stock, note) for gr_r2_hold; grsquad.gr_edits(..., r2_hold=gr_mode(v)) carries the call."""
    mode = gr_mode(v)
    if mode == "move" or not _ss_on(v, "gr_"):
        return []
    return _edits("GR", mode, {"ss", "nade"})


# ---- stock words (read from SLUS_208.20 / SLUS_206.13) -----------------------------------------

def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


_JS_CAVE_HEX = (   # sceDevFontRefDirectImage + sceDevFontRefStrN twins, 0x001770B0..0x00177398
    "27BDFF60 FFB20020 FFB10010 0100902D FFB00000 00A0882D FFBF0090 0080802D "
    "FFBE0080 FFB70070 FFB60060 FFB50050 FFB40040 12400048 FFB30030 00063400 "
    "3C020004 00C21021 0009183C 0002103C 3C040058 0002103E 0006B03C 0003ADFA "
    "0222882F 249E1078 0007A03C 24130007 241700C2 324200FF 0016183E 304200FF "
    "0223882D 1040002F 0012923A 000210C0 0200202D 005E1021 3C05C400 0005283C "
    "34A58000 0C05DD34 DC460000 0200202D 0C065982 02B72825 0200202D 0C065982 "
    "0014283E 0200202D 0C065982 0220282D 0200202D 0C065982 66250010 0200202D "
    "0C065982 66250020 0200202D 0C065982 66250030 0200202D 0C065982 66250040 "
    "0200202D 0C065982 66250050 0200202D 0C065982 66250060 0200202D 0C065982 "
    "66250070 0200202D 0C065982 66250080 0200202D 0C065982 66250090 0C065958 "
    "0200202D 3C02FFFF 2673FFFF 3442FFFF 1662FFC9 324200FF DFBF0090 DFBE0080 "
    "DFB70070 DFB60060 DFB50050 DFB40040 DFB30030 DFB20020 DFB10010 DFB00000 "
    "03E00008 27BD00A0 27BDFF50 FFBE0090 FFB70080 0000F02D FFB40050 0080B82D "
    "FFB30040 FFB20030 FFB10020 00A0902D FFB00010 0120882D FFBF00A0 0100802D "
    "FFB60070 0000282D FFB50060 2631FFFF 8E420010 8E560008 AFA20000 8E42000C "
    "00D64018 8E430000 0000302D 00E25018 8E490004 0000382D 00689821 0C06591C "
    "012AA021 3C02FFFF 3442FFFF 12220029 03C0102D 96020000 26100002 304500FF "
    "10A00023 00021A02 0014A83C 26540020 30620007 3C060058 24C30868 000528C0 "
    "00A32821 0013203C 00021080 0004203E 00151C3A DCA80000 00832025 02821021 "
    "2405FFFF 0005283C 8C470000 00852825 8E490014 8FA60000 02E0202D 02769821 "
    "0C05DC2C 27DE0001 2631FFFF 3C02FFFF 3442FFFF 12220007 03C0102D 96020000 "
    "26100002 304500FF 14A0FFE1 00021A02 03C0102D DFBF00A0 DFBE0090 DFB70080 "
    "DFB60070 DFB50060 DFB40050 DFB30040 DFB20030 DFB10020 DFB00010 03E00008 "
    "27BD00B0 00000000 "
)
_JS_CAVE2_HEX = (  # _sceSifLoadModuleBuffer's twin, 0x00181C00..0x00181E08
    "27BDFF70 FFB60070 FFB30040 00E0B02D FFB10020 0080982D FFB00010 00A0882D "
    "FFBF0080 00C0802D FFB50060 FFB40050 0C06068E FFB20030 04400069 3C02FFFF "
    "0C0606CE 00000000 10400004 3C140062 3C02FFFE 10000062 3442FFFC 0280A82D "
    "269289C0 1200004A AE9389C0 2A2200FD 14400042 0200282D 26440104 02041025 "
    "30420007 1040001A 0200382D 260200E0 3C050062 68E30007 6CE30000 68E6000F "
    "6CE60008 68E80017 6CE80010 68E9001F 6CE90018 B0830007 B4830000 B086000F "
    "B4860008 B0880017 B4880010 B089001F B4890018 24E70020 24840020 00000000 "
    "14E2FFEC 00000000 10000010 00000000 260200E0 3C050062 DCEA0000 DCE30008 "
    "DCE60010 DCE80018 FC8A0000 FC830008 FC860010 FC880018 24E70020 24840020 "
    "00000000 14E2FFF4 00000000 68E90007 6CE90000 68EA000F 6CEA0008 68E60017 "
    "6CE60010 88E8001B 98E80018 B0890007 B4890000 B08A000F B48A0008 B0860017 "
    "B4860010 A888001B 26A389C0 240200FC B8880018 10000008 AC620004 26440104 "
    "0C05A8D6 0220302D 10000002 AE510004 AE400004 3C050062 26B089C0 24A48BC0 "
    "AFA00000 24050006 0000302D 0200382D 24080200 0200482D 240A0008 0C05F5AA "
    "0000582D 04430004 8E030004 3C02FFFE 10000003 3442FFFF 8E8289C0 AEC30000 "
    "DFBF0080 DFB60070 DFB50060 DFB40050 DFB30040 DFB20030 DFB10020 DFB00010 "
    "03E00008 27BD0090 "
)
_GR_CAVE_HEX = (   # sceDevFontRefDirectImage + sceDevFontRefStrN, 0x0040E800..0x0040EAE8
    "27BDFF60 FFB20020 FFB10010 0100902D FFB00000 00A0882D FFBF0090 0080802D "
    "FFBE0080 FFB70070 FFB60060 FFB50050 FFB40040 12400048 FFB30030 00063400 "
    "3C020004 00C21021 0009183C 0002103C 3C040058 0002103E 0006B03C 0003ADFA "
    "0222882F 249E6FE8 0007A03C 24130007 241700C2 324200FF 0016183E 304200FF "
    "0223882D 1040002F 0012923A 000210C0 0200202D 005E1021 3C05C400 0005283C "
    "34A58000 0C103B08 DC460000 0200202D 0C10ACBE 02B72825 0200202D 0C10ACBE "
    "0014283E 0200202D 0C10ACBE 0220282D 0200202D 0C10ACBE 66250010 0200202D "
    "0C10ACBE 66250020 0200202D 0C10ACBE 66250030 0200202D 0C10ACBE 66250040 "
    "0200202D 0C10ACBE 66250050 0200202D 0C10ACBE 66250060 0200202D 0C10ACBE "
    "66250070 0200202D 0C10ACBE 66250080 0200202D 0C10ACBE 66250090 0C10AC94 "
    "0200202D 3C02FFFF 2673FFFF 3442FFFF 1662FFC9 324200FF DFBF0090 DFBE0080 "
    "DFB70070 DFB60060 DFB50050 DFB40040 DFB30030 DFB20020 DFB10010 DFB00000 "
    "03E00008 27BD00A0 27BDFF50 FFBE0090 FFB70080 0000F02D FFB40050 0080B82D "
    "FFB30040 FFB20030 FFB10020 00A0902D FFB00010 0120882D FFBF00A0 0100802D "
    "FFB60070 0000282D FFB50060 2631FFFF 8E420010 8E560008 AFA20000 8E42000C "
    "00D64018 8E430000 0000302D 00E25018 8E490004 0000382D 00689821 0C10AC58 "
    "012AA021 3C02FFFF 3442FFFF 12220029 03C0102D 96020000 26100002 304500FF "
    "10A00023 00021A02 0014A83C 26540020 30620007 3C060058 24C367D8 000528C0 "
    "00A32821 0013203C 00021080 0004203E 00151C3A DCA80000 00832025 02821021 "
    "2405FFFF 0005283C 8C470000 00852825 8E490014 8FA60000 02E0202D 02769821 "
    "0C103A00 27DE0001 2631FFFF 3C02FFFF 3442FFFF 12220007 03C0102D 96020000 "
    "26100002 304500FF 14A0FFE1 00021A02 03C0102D DFBF00A0 DFBE0090 DFB70080 "
    "DFB60070 DFB50060 DFB40050 DFB30040 DFB20030 DFB10020 DFB00010 03E00008 "
    "27BD00B0 00000000 "
)
_GR_CAVE2_HEX = (  # _sceSifLoadModuleBuffer, 0x00418EF0..0x004190F8
    "27BDFF70 FFB60070 FFB30040 00E0B02D FFB10020 0080982D FFB00010 00A0882D "
    "FFBF0080 00C0802D FFB50060 FFB40050 0C10634A FFB20030 04400069 3C02FFFF "
    "0C10638A 00000000 10400004 3C14005F 3C02FFFE 10000062 3442FFFC 0280A82D "
    "2692F640 1200004A AE93F640 2A2200FD 14400042 0200282D 26440104 02041025 "
    "30420007 1040001A 0200382D 260200E0 3C05005F 68E30007 6CE30000 68E6000F "
    "6CE60008 68E80017 6CE80010 68E9001F 6CE90018 B0830007 B4830000 B086000F "
    "B4860008 B0880017 B4880010 B089001F B4890018 24E70020 24840020 00000000 "
    "14E2FFEC 00000000 10000010 00000000 260200E0 3C05005F DCEA0000 DCE30008 "
    "DCE60010 DCE80018 FC8A0000 FC830008 FC860010 FC880018 24E70020 24840020 "
    "00000000 14E2FFF4 00000000 68E90007 6CE90000 68EA000F 6CEA0008 68E60017 "
    "6CE60010 88E8001B 98E80018 B0890007 B4890000 B08A000F B48A0008 B0860017 "
    "B4860010 A888001B 26A3F640 240200FC B8880018 10000008 AC620004 26440104 "
    "0C100E4C 0220302D 10000002 AE510004 AE400004 3C05005F 26B0F640 24A4F840 "
    "AFA00000 24050006 0000302D 0200382D 24080200 0200482D 240A0008 0C10531C "
    "0000582D 04430004 8E030004 3C02FFFE 10000003 3442FFFF 8E82F640 AEC30000 "
    "DFBF0080 DFB60070 DFB50060 DFB40050 DFB30040 DFB20030 DFB10020 DFB00010 "
    "03E00008 27BD0090 "
)



def _claimed(game, *hexes):
    """the stock words of the claimed part of each cave (the hex tables hold the whole dead functions)"""
    g = G[game]
    out = {}
    for (base, end), hexwords in zip(((g["CAVE"], g["CAVE_END"]), (g["CAVE2"], g["CAVE2_END"])), hexes):
        out.update({va: w for va, w in _stock_words(base, hexwords).items() if va < end})
    return out


#: stock words of every word this module may write
JS_STOCK = _claimed("JS", _JS_CAVE_HEX, _JS_CAVE2_HEX)
GR_STOCK = _claimed("GR", _GR_CAVE_HEX, _GR_CAVE2_HEX)
assert len(JS_STOCK) == (0x00177314 - 0x001770B0 + 0x00181D34 - 0x00181C00) // 4
assert len(GR_STOCK) == (0x0040EA34 - 0x0040E800 + 0x00419024 - 0x00418EF0) // 4

#: words read but not written: the engine code the routines rely on (checked by selftest)
JS_CONTEXT = {
    0x001B0740: 0xAE020000,      # FragLocationBehavior ctor: sw v0 (vtable 0x5A3550), 0(s0)
    0x001B074C: 0xAE00002C,      #   level = 0 (found at the throw)
    0x001B0858: 0x2665001C,      # Process: FindLevel(scene, this + 0x1C), the aim
    0x001B08F4: 0x8E4300A0,      # state 0: HumanAI +0xA0 (+8 = 3: take the grenade)
    0x001B0A38: 0x8E4400A4,      # IsOkToFragHereNow(HumanAI +0xA4 = his fireteam, ...)
    0x003E0AAC: 0xC48100EC,      # IsOkToFragHereNow: lwc1 f1, 0xec(a0) -- the team's last grenade
    0x003EA090: 0x8C590514,      # GetNumGrenades: inventory at SimHuman +0x514, vt+0x2C
    0x003EA094: 0x8F39002C,
    0x003EA0C4: 0x8E620018,      #   a thrown item's count at +0x18
    0x003F2E44: 0x0040A02D,      # HandleAddWaypoint: move s4, v0 (the fireteam payload)
    0x003F2E80: 0x0280382D,      #   move a3, s4 -- s4 still holds it at disp's call
    0x00339628: 0x0C067DD4,      # HandleThrowItem: jal SendMaster (ControllerThrewItem to the host)
    0x00339678: 0x0C0CE5BC,      #   jal ThrownItem::DecrementCount -- the grenade is spent here
    0x0033970C: 0x8E030018,      #   DecrementCount: the count at +0x18 goes down
    0x003E0BF4: 0x3C034361,      # IsOkToFragHereNow: 225 = 15 m squared, the friendly radius outdoors
}
GR_CONTEXT = {
    0x001B466C: 0xAE020000,      # FragLocationBehavior ctor stores its vtable
    0x001B42A8: 0x2665001C,      # Process: FindLevel(scene, this + 0x1C)
    0x001B44B4: 0x8E4400A4,      # ReportGrenadeUse(HumanAI +0xA4, ...)
    0x001902B8: 0xC48100EC,      # IsOkToFragHereNow: the team's last grenade at +0xEC
    0x0019A0D0: 0x8C5904F4,      # GetNumGrenades: inventory at SimHuman +0x4F4
    0x0019A104: 0x8E620010,      #   a thrown item's count at +0x10
    0x0035D9E8: 0x0C0BF1D4,      # HandleThrowItem: jal SendMaster
    0x0035DA38: 0x0C0D76AC,      #   jal ThrownItem::DecrementCount
    0x0019041C: 0x3C024361,      # IsOkToFragHereNow: 225 = 15 m squared
}


# ---- the card ---------------------------------------------------------------------------------

def cards(prefix: str = "js_", group: str = "Online") -> list:
    """The one setting: js_r2_hold (Jungle Storm: online co-op and split screen) or gr_r2_hold (Ghost Recon
    split screen). Suggested groups: "Online" next to js_coop_orders, "Split Screen" next to gr_ss_orders."""
    js = prefix == "js_"
    where = ("online co-op (with 'Online co-op: quick orders for your own AI') and in split screen "
             "(with 'Team orders and soldier switching'). The button is R2 (R3 on the third button "
             "layout)" if js else
             "split screen (with 'Team orders and soldier switching'). The button is R3 on Ghost "
             "Recon's own layout, R2 with Jungle Storm's ('Controls')")
    frag_opt = "'Enemies throw grenades'" if js else "'Enemies throw grenades more readily'"
    return [
        Setting(prefix + "r2_hold", "Hold the quick order: move there or throw a grenade", CHOICE, "move",
                group, confidence="experimental",
                requires={} if js else {"gr_ss_orders": True},
                choices=[
                    Choice("move", "Move there (as now)",
                           "Your fireteam's AI go to the spot and hold there."),
                    Choice("frag", "Frag grenade there",
                           "The AI teammate nearest the spot who has a frag throws it there; one "
                           "with a grenade launcher fires the launcher at it instead."),
                    Choice("smoke", "Smoke grenade there",
                           "The AI teammate nearest the spot who has a hand grenade (frag or "
                           "smoke) and no launcher throws smoke there. Needs 'Smoke grenades' "
                           "with 'AI throws smoke' not set to Never; without them this is "
                           "'Move there'."),
                ],
                help="What HOLDING the quick-order button and letting go does, in " + where + ". "
                     "A tap still switches your fireteam between Hold and Advance. With a grenade "
                     "choice, of your fireteam's AI the one standing nearest the spot you aimed "
                     "at" + (" (online: where the marker shows)" if js else "") + " who has that kind "
                     "of grenade turns, "
                     "throws it there and goes back to following or holding; the throw uses up "
                     "one of his grenades. If nobody has one, nothing happens -- nobody is sent "
                     "to the spot. He will not throw a frag where a friendly (you included) "
                     "stands within 15 m of the spot, or anywhere in the same room indoors: the "
                     "game's own safety check. The team's 30 s wait between grenades does not "
                     "hold up your order, and an ordered smoke does not count against the AI's "
                     "own smoke limits." + (" Online the order goes to the host, whose AI "
                                            "throws, so everyone sees the same grenade." if js else ""),
                caution=("Checked in the RAM interpreter on savestates (the order, who throws, the "
                         "queued throw reaching the trigger, the grenade used up, smoke coming out "
                         "as smoke, online delivery to the host); never played." if js else
                         "Checked in the RAM interpreter on a Ghost Recon savestate (who throws, the "
                         "queued throw, the smoke mark; the throw itself on Jungle Storm's twin "
                         "code); never played.") +
                        " A hand throw carries about 36 m, farther with the range of " + frag_opt +
                        ". The throw is dropped when its first 10 m are blocked (4 m with " +
                        frag_opt + " on, never for smoke) -- common in thick cover."
                        + (" In co-op AI backup the AI were seen carrying a rifle with a grenade "
                           "launcher or no grenade at all: there Frag means the grenadier fires "
                           "his launcher, and Smoke finds nobody unless a kit carries grenades "
                           "('Smoke grenade kits'). Every console online needs the same choice: a "
                           "console built with 'Move there' ignores a grenade order from one built "
                           "with a grenade." if js else "")),
    ]


# ---- checks -----------------------------------------------------------------------------------

def selftest(gr_elf=None, js_elf=None, ai2=None) -> list:
    """[] = pass. Every mode and part combination assembles inside its caves, no VA twice, every written
    word has a stock word; with the executables, the stock and context words; with `ai2` (the
    shared scratch folder), the caves inside this module's claims and no word another option writes."""
    import json
    import os
    fails = []
    combos = []
    for mode in ("frag", "smoke"):
        combos.append(("JS", _edits("JS", mode, {"disp", "nade", "ss"})))
        combos.append(("JS", _edits("JS", mode, {"disp", "nade"})))
        combos.append(("JS", _edits("JS", mode, {"ss", "nade"})))
        combos.append(("GR", _edits("GR", mode, {"ss", "nade"})))
    for game, e in combos:
        st = JS_STOCK if game == "JS" else GR_STOCK
        if len({va for va, *_ in e}) != len(e):
            fails.append("%s duplicate VA" % game)
        for va, _w, s, _n in e:
            if st.get(va) != s:
                fails.append("%s %08x: no stock word" % (game, va))
    # entry points stay where grsquad / grcooporders call them
    for mode in ("frag", "smoke"):
        _b, lj = build("JS", mode)
        _b, lg = build("GR", mode)
        if lj["nade_disp"] != JS_NADE_DISP or lj["nade_ss"] != JS_NADE_SS or lg["nade_ss"] != GR_NADE_SS:
            fails.append("entry point moved (%s)" % mode)
    # 'move' writes nothing, whatever else is on
    full = {"js_r2_hold": "move", "js_coop_orders": True, "js_ss_orders": True, "js_ss_fireteams": True,
            "js_ss_handoff": True, "js_smoke": True, "js_smoke_ai": "all",
            "gr_r2_hold": "move", "gr_ss_orders": True, "gr_ss_fireteams": True, "gr_ss_handoff": True}
    if js_edits(full) or gr_edits(full):
        fails.append("'move' writes words")
    if js_mode(dict(full, js_r2_hold="smoke", js_smoke=False)) != "move" \
            or js_mode(dict(full, js_r2_hold="smoke", js_smoke_ai="off")) != "move":
        fails.append("smoke without smoke grenades is not 'move'")
    for elf, stock, ctx, delta in ((js_elf, JS_STOCK, JS_CONTEXT, 0x100), (gr_elf, GR_STOCK, GR_CONTEXT, 0x80)):
        if elf is None:
            continue
        for table in (stock, ctx):
            for va, want in table.items():
                got = struct.unpack_from("<I", elf, va - 0x00100000 + delta)[0]
                if got != want:
                    fails.append("stock %08x: disc %08x, recorded %08x" % (va, got, want))
    if ai2:
        claims = {"js": [], "gr": []}
        for ln in open(os.path.join(ai2, "caves_claimed.txt")):
            p = ln.split()
            if len(p) >= 3 and "-" in p[2] and p[1] in claims:
                a, b = (int(x, 16) for x in p[2].split("-"))
                claims[p[1]].append((p[0], a, b))
        for game, key in (("JS", "js"), ("GR", "gr")):
            used = set(int(x, 16) for x in json.load(open(os.path.join(ai2, key + "_used.json"))))
            for mode in ("frag", "smoke"):
                for va, *_ in _edits(game, mode, {"disp", "nade", "ss"} if game == "JS" else {"nade", "ss"}):
                    if va in used:
                        fails.append("%s %08x written by another option" % (game, va))
                    own = [c for c in claims[key] if c[1] <= va <= c[2]]
                    if not own or any(c[0] != "O" for c in own):
                        fails.append("%s %08x outside O's claims (or inside another's)" % (game, va))
    return fails

"""Gunshot hearing and heard-shot watching: Jungle Storm (SLUS-20820).

Why far enemies stay oblivious. Every round fired ends in IkeSimulationMgr::
HandleGunshot (JS 0x00370EA0), which sends ControllerFiredWeapon (JS message
0x1EA) to the AwarenessMgr. Its handler (JS 0x003D5DC0, GR HandleController-
FiredWeapon 0x003F5FD0) hands the shot to SoundPropagationManager::PropagateForAI
(position, room, sound, shooter, AwarenessTarget 5) -- and PropagateForAI is an
empty stub in both PS2 games (JS 0x003D23D0, GR 0x003F2960: `jr ra; nop`). So no
soldier ever *hears* a gunshot. What remains:

  * bullet whiz (IkeSimulationMgr::GunshotAlert, JS 0x00370C50): soldiers of
    another company within 10 m of a bullet's path (3 m for a suppressed gun)
    get a heard awareness of the shooter (HandleBulletWhiz, JS 0x003D64A0,
    target 7) and treat it as being shot at;
  * explosions (ExplosionAlert -> HandleExplosion, target 3);
  * sight, and the fireteam sharing what one member sees (ReportEnemyContact).
    Moving soldiers are heard only from inside CheckLineOfSight (movement
    noise, IkeConstants levels, a few metres). Dead friends alert only when
    seen (HumanAIAwareness::CountDeadFriends); death cries are not propagated.

Everything downstream of the stub is intact and waits for target-5 awarenesses:
HumanAIAwareness::Update (JS 0x003EDA80) takes the first unprocessed entry on a
soldier's sound list (DoIHearGunshots, JS 0x003EE050: target 5, 7 or 3, older
than his reaction delay +0x3C -- 0.03-0.5 s in JS) and makes him glance at the
shooter, raises him to Alert, and then either reports being under fire (target
7, or the shot within 20 m: 0x0057ABC0 = 400 m^2) or calls FireTeamAI::
ReportHeardGunshots (JS 0x003DAE50). That one stores the shooter's position on
the team and flags it (+0xAD); FireTeamAI::Update (JS 0x003DE4F8) then starts a
TeamInvestigationBehavior toward it -- but only for a team that has patrolled
(+0xC0, set by TeamPath / TeamPatrolZone), whose leader is outdoors, whose
script is idle (empty, TeamPath, PatrolZone, DefendZone or 0x31), and when the
sound is under 20 s old and 150 m away (or a coin flip said so). Sound entries
live 2 s (AwarenessMgr::AgeSoundLists).

  * hearing: PropagateForAI's `jr ra` becomes `j hear`. The routine walks the
    simulation's controller list (as GunshotAlert does) and, for every hostile
    soldier (SimHuman::IsEnemy) not on the shooter's side (AwarenessMgr::
    CheckSameSide), not disabled or out of action, within R of the shot (R/4
    when the shooter's current firearm is suppressed, the test GunshotAlert
    uses), calls the engine's own HandleBulletWhiz and retags the entry it
    appends from target 7 to 5 -- a heard gunshot, the input the rest of the
    engine was written for. At most one per listener per second (the newest
    sound entry is checked), so automatic fire and shotgun pellets do not
    flood the awareness pool. Players and the AI squad are not listeners: the
    investigation would pull a player-ordered team off its orders.
  * comrades (js_hear_allies, needs hearing): a shot by a hostile soldier used
    to reach nobody (all listeners are his own side). With this, a hostile
    shooter who has a current threat (his HumanAI +0x64 id, +0x68 the point he
    is engaging -- set by EngageThreat; a soldier only spraying at a spot has
    none) makes the same loop run with that threat as the awareness's source
    and the engaged point as where it was heard, for hostile soldiers within
    R of the shot who are not fighting yet (alert < 3): they glance at the
    threat, go on alert, and a patrolling team investigates the threat's
    position (ReportHeardGunshots reads the source's live position). At most
    one such shot every 0.25 s map-wide (a stamp word at the end of the hear
    cave; a stamp in the future -- the clock restarts each mission -- does not
    block). A dropped comrade shot costs ~70 instructions, a spread one ~10k.
    The shooter classification (open / suppressed / comrade) lives in a third
    routine, `who`.
  * watching (needs hearing): HumanAIAwareness::Update's call to
    ReportHeardGunshots (JS 0x003EDDC4) goes through a routine that makes the
    call and then, for a soldier of a team that never patrols (+0xC0 == 0 --
    posted guards; the engine will not send them), who is idle (own script
    empty) and not already in combat, starts the soldier's own scan
    (HumanAI::StartScanning, JS 0x003E8AE0 -- what CoverArea / RunForCover
    use) centred on the horizontal direction to the shot, +-45 degrees every
    3 s. Stock left such a guard facing his post or whatever he last glanced
    at (savestate 9C04BFE8.02: 2 idle Alert guards with a team flag set 4-7
    minutes earlier that no code would ever act on).

Online co-op: the AI runs on the host, so only the host's disc matters. A
joiner's console also runs the routine for shots it processes, but that only
adds 2-second entries to its local awareness lists, which its AwarenessMgr
ages out every frame (joiner savestates show it updating).

Checked in the interpreter on savestate RAM (scratchpad agent_aware/t_*.py):
real players firing where they stand; the routine gives exactly one fresh
target-5 entry to every enemy inside the radius and nothing to anyone beyond
it (split-screen J0x save: two patrolling teams at 66-80 m -- none at 60 m;
at 80 m all 9 hear, go Bored -> Alert, glance at the shooter, and both teams
switch TeamPath / TeamPatrolZone -> TeamInvestigationBehavior toward him;
stock: nothing). A player whose gun really is suppressed reaches nobody at
47-57 m (radius/4); the same shot unsuppressed reaches all 6. An enemy's shot
reaches no enemy; a second shot within 1 s adds nothing, one 1.2 s later adds
one. Watch: posted guards 75 m away scan +-45 degrees around the level bearing
of the shot and keep to that sector through HumanAI::UpdateFocus for 30 s
(stock: they keep looking 83-86 degrees away); nothing else differs from the
stock report in combat, busy, patrolling or too-close cases. Not yet played.

Caves: 0x00177DB8..0x00177FF0 (hear, 113 words, the stamp in its last word),
0x00181858..0x001819B4 (who, 86 of 87) and 0x001969D8..0x00196AB8 (watch, 53
of 56): dead libdev / SIF RPC / VU0 helpers with no reference in the ELF or
either overlay, used by no other option.

Comrade fire checked the same way (t_allies.py): real engaged enemies in
three co-op/single-player firefights -- the idle teams 26-37 m away (posted)
hear it, glance at the player he is shooting at (0.0 m from the player's
aim point, ~85 m from the shooter), go on alert and scan toward him; those
fighting, beyond R, and your side get nothing; stock and comrades-off:
nothing, every soldier ends identical. A patrol member set to engage the
player (split-screen save): his own team and a patrol 35-41 m away switch to
TeamInvestigationBehavior toward the player 77 m off.

Ghost Recon (SLUS-20613, `gr_edits`): the same engine and the same three
routines, with GR's addresses and IkeSimController vtable slots (4 bytes
lower). The stub is GR PropagateForAI 0x003F2960 (`jr ra; nop`; its only
caller is AwarenessMgr::HandleControllerFiredWeapon 0x003F5FD0, which gets
HandleGunshot's ControllerFiredWeapon, message 0x191). The watch hook is
HumanAIAwareness::Update's `jal ReportHeardGunshots` at 0x0019DFBC. Two engine
differences: GR's "shooting at me" radius (kHesShootingAtMeThreshold2) starts
at 20 m and drops to 10 m once a soldier of the player's own fire team updates
(four of five soldier savestates read 100 m^2; the fifth, 7 s into a
mission, has not set it yet). And a team investigates only from an
empty, 0x2A or 0x1F script. Caves: 13 of the 16 identical, unreferenced
RSArray<RSArray<RSMemoryPoolNode<T>>*> destructors at 0x00139140 + 0x70 * i,
24 words each, named only by their exception-index records. A routine runs
across its islands with a `j` to the next one: hear takes 6 (the stamp is the
sixth island's last word), who takes 4 and watch takes 3.

Checked in the interpreter on GR savestate RAM (scratchpad grport/A,
t_hear/t_cases/t_watch.py). Each shot went through the real
HandleControllerFiredWeapon, with only the payload getters stubbed. In the
88-soldier firefight (3D55F8ED.01), the player's shot reached exactly the
hostiles inside R: none at 40 m, 3 at 60 m, 7 at 80 m, 19 at 120 m. Three
out-of-action soldiers were skipped, and nobody was reached in stock. 0.6 s
later the Bored listeners went Alert, glanced, and set their team's point on
the player. An allied soldier's shot in 1458AB4E.01 reached the 10 hostiles
within 40 m (14 within 80 m), and at 40 m both patrols there switched to
TeamInvestigationBehavior. With his gun flagged suppressed in RAM, the 80 m
setting reached only the 7 within 20 m. A second shot 0.5 s later added
nothing; one 1.2 s later added one entry each. An enemy's shot reached
nobody. With comrades on, it reached the idle hostiles in R, naming his
threat (a squad member 0.9 m from his aim point). At 120 m that was 24
soldiers, 22 of whom went from Bored to Alert, and two patrols 135-160 m from
the player started investigating. `who` spread nothing at the same instant or
0.1 s after a spread, and spread again after 0.3 s and after a clock restart.
Watch: the 4 idle posted guards who heard the shot began scanning +-45
degrees, every 3 s, level, within 0.1 degree of the bearing to the shot.
Busy, fighting and patrolling listeners did not, and stock nobody
did. Not yet played.
"""

from __future__ import annotations

from .grasm import Asm, assemble
from .model import BOOL, CHOICE, Choice, Setting

# PropagateForAI stub (jr ra; nop) -> j hear
PROP = 0x003D23D0
PROP_STOCK = 0x03E00008
# HumanAIAwareness::Update: jal FireTeamAI::ReportHeardGunshots (a0 team, a1 HumanAI, a2 awareness)
REPORT_HOOK = 0x003EDDC4
REPORT_STOCK = 0x0C0F6B94
REPORT = 0x003DAE50

HEAR_CAVE, HEAR_END = 0x00177DB8, 0x00177FF0
WATCH_CAVE, WATCH_END = 0x001969D8, 0x00196AB8
WHO_CAVE, WHO_END = 0x00181858, 0x001819B4
STAMP = HEAR_END - 4             # data: when a comrade's shot last spread (seconds, f32)

SYMS = dict(
    simmgr=0x0062B8C8,          # IkeSimulationMgr*
    clock=0x00684768,           # RSClock*, +0xD4 = seconds
    silenced=0x002206E0,        # Firearm::IsSilenced
    isenemy=0x003BC050,         # SimHuman::IsEnemy
    sameside=0x003D3CD0,        # AwarenessMgr::CheckSameSide(mgr, a, b)
    disabled=0x003577F0,        # IkeSimController::IsDisabled
    distsq=0x0010A830,          # DistanceSquared(a, b)
    ndx=0x003429E0,             # IkeSimController::GetAwarenessNdx
    brain=0x003429B0,           # AwarenessMgr::GetBrain(mgr, ndx) -> MentalImage
    whiz=0x003D64A0,            # AwarenessMgr::HandleBulletWhiz(mgr, listener, shooter, &pos)
    report=REPORT,
    isempty=0x001B7180,         # RSScript::IsEmpty
    scan=0x003E8AE0,            # HumanAI::StartScanning(ai, &dir, half angle, period)
    aimgr=0x001225D0,           # IkeAIMgr::Get
    humanai=0x003F17D0,         # IkeAIMgr::GetHumanAI(mgr, SimHuman)
    objmgr=0x0062B748,          # IkeObjectMgr*
    getctl=0x00340F30,          # IkeObjectMgr::GetAFreakinIkeSimController(mgr, id)
    who=WHO_CAVE,
    stamp=STAMP,
)
#: IkeSimController vtable slots the routines call (Ghost Recon's sit 4 bytes lower)
JS_VT = dict(vt_pos=0x238, vt_issim=0x260, vt_ooa=0x29C, vt_view=0x250, vt_item=0x2F8)

# Ghost Recon: dead RSArray destructors, 24 words each with a live 4-word constructor between two
GR_ISLANDS = [0x00139140 + 0x70 * i for i in range(13)]
GR_HEAR = [(a, a + 0x60) for a in GR_ISLANDS[0:6]]
GR_WHO = [(a, a + 0x60) for a in GR_ISLANDS[6:10]]
GR_WATCH = [(a, a + 0x60) for a in GR_ISLANDS[10:13]]
GR_STAMP = GR_HEAR[-1][1] - 4
GR_HEAR[-1] = (GR_HEAR[-1][0], GR_STAMP)
GR_SYMS = dict(
    simmgr=0x005EACE8,          # IkeSimulationMgr::mIkeSimulationMgr
    clock=0x005DFC20,           # RSClock::mClockMgr
    silenced=0x00220960,
    isenemy=0x003DC850,
    sameside=0x003F3E00,
    disabled=0x0037A070,
    distsq=0x001142E0,
    ndx=0x00367250,
    brain=0x00367230,
    whiz=0x003F66D0,
    report=0x0018A380,
    isempty=0x001BAA40,
    scan=0x00198A60,
    aimgr=0x003663A0,
    humanai=0x001A1890,
    objmgr=0x005EAB20,          # IkeObjectMgr::mIkeObjectMgr
    getctl=0x00365830,
    who=GR_WHO[0][0],
    stamp=GR_STAMP,
)
GR_VT = dict(vt_pos=0x234, vt_issim=0x25C, vt_ooa=0x298, vt_view=0x24C, vt_item=0x2F4)

HEAR_SRC = """
hear:                           ; PropagateForAI(a0 = AwarenessMgr+0x10, a1 = &shot, a2 room,
    addiu sp, sp, -0x90         ;   a3 sound, t0 = shooter, t1 = 5)
    sd    ra, 0x80(sp)
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s2, 0x20(sp)
    sq    s3, 0x30(sp)
    sq    s4, 0x40(sp)
    sq    s5, 0x50(sp)
    swc1  f20, 0x60(sp)
    move  s2, a1
    addiu s5, a0, -0x10         ; AwarenessMgr
    move  a0, t0
    jal   {who}                 ; -> v0 whom the shot is "of", v1 the heard point,
    move  a1, s2                ;    a3 = 1: only soldiers not yet fighting, f0 = radius^2
    beqz  v0, out
    move  s3, v0
    sw    v1, 0x68(sp)
    sw    a3, 0x64(sp)
    mov.s f20, f0
    lui   v0, %hi({simmgr})
    lw    s4, %lo({simmgr})(v0)
    lw    s0, 0x230(s4)         ; controller list
loop:                           ; cheapest tests first: most controllers are out of range
    addiu v1, s4, 0x290
    beq   s0, v1, out
    nop
    jal   {disabled}
    move  a0, s0
    bnez  v0, next
    nop
    lw    t9, 0(s0)
    lw    t9, {vt_pos}(t9)      ; GetWorldPosition
    jalr  t9
    move  a0, s0
    move  a1, v0
    jal   {distsq}              ; from the shot
    move  a0, s2
    c.lt.s f0, f20
    bc1f  next
    nop
    lw    t9, 0(s0)
    lw    t9, {vt_issim}(t9)    ; IsSimHuman
    jalr  t9
    move  a0, s0
    beqz  v0, next
    nop
    jal   {isenemy}             ; hostile soldiers only
    move  a0, s0
    beqz  v0, next
    move  a0, s5
    move  a1, s3
    jal   {sameside}            ; not on the side of whom the shot is "of"
    move  a2, s0
    bnez  v0, next
    nop
    lw    t9, 0(s0)
    lw    t9, {vt_ooa}(t9)      ; IsOutOfAction
    jalr  t9
    move  a0, s0
    bnez  v0, next
    lw    v0, 0x64(sp)
    beqz  v0, brain
    lw    v0, 0x174(s0)         ; alert level
    slti  v0, v0, 3
    beqz  v0, next              ; a comrade's shot: those already fighting are busy
    nop
brain:
    jal   {ndx}
    move  a0, s0
    move  a1, v0
    jal   {brain}               ; the listener's MentalImage
    move  a0, s5
    beqz  v0, next
    move  s1, v0
    lw    v0, 8(s1)             ; sound list
    beqz  v0, heard
    lw    v1, 0x10(s1)          ; its newest entry
    lhu   v0, 0x28(v1)
    andi  v0, v0, 0x1E0
    xori  v0, v0, 0xA0
    bnez  v0, heard             ; not a heard gunshot
    lui   v0, %hi({clock})
    lw    v0, %lo({clock})(v0)
    lwc1  f1, 0xD4(v0)
    lwc1  f2, 0x1C(v1)
    sub.s f1, f1, f2
    lui   v0, 0x3F80
    mtc1  v0, f2
    c.lt.s f1, f2               ; heard one less than a second ago
    bc1t  next
    nop
heard:
    move  a0, s5
    move  a1, s0
    move  a2, s3
    jal   {whiz}                ; appends an awareness of s3 at the heard point
    lw    a3, 0x68(sp)
    lw    v1, 0x10(s1)          ; ... the entry just appended
    beqz  v1, next
    addiu t0, zero, -0x1E1
    lhu   v0, 0x28(v1)
    and   v0, v0, t0
    ori   v0, v0, 0xA0          ; target 7 (bullet whiz) -> 5 (heard gunshot)
    sh    v0, 0x28(v1)
next:
    b     loop
    lw    s0, 0x150(s0)
out:
    lwc1  f20, 0x60(sp)
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    lq    s3, 0x30(sp)
    lq    s4, 0x40(sp)
    lq    s5, 0x50(sp)
    ld    ra, 0x80(sp)
    jr    ra
    addiu sp, sp, 0x90
"""

# Whom a shot is "of" and where it was heard. a0 = the shooter, a1 = &shot.
# Out: v0 = the controller the heard awareness names (0 = nobody hears it), v1 = the heard
# point, a3 = 1 when only soldiers not yet fighting should hear, f0 = radius^2.
#   * not hostile: the shooter himself at the shot; a quarter of the radius when his current
#     firearm is suppressed (GunshotAlert's own test);
#   * hostile, with comrade fire on: his current threat (HumanAI +0x64 id, +0x68 the point he
#     is engaging), at most one such shot every 0.25 s across the whole map;
#   * hostile otherwise: nobody.
WHO_SRC = """
who:
    addiu sp, sp, -0x30
    sd    ra, 0x20(sp)
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    move  s0, a0
    sw    a1, 0x2C(sp)          ; &shot
    lui   v0, {r2}
    beqz  s0, none
    sw    v0, 0x28(sp)          ; radius^2, open fire
    lw    t9, 0(s0)
    lw    t9, {vt_issim}(t9)    ; IsSimHuman(shooter)
    jalr  t9
    move  a0, s0
    beqz  v0, plain
    nop
    jal   {isenemy}
    move  a0, s0
    bnez  v0, {hostile}
    nop
    lw    t9, 0(s0)
    lw    t9, {vt_view}(t9)     ; his SimHuman view
    jalr  t9
    move  a0, s0
    lw    t9, 0(v0)
    lw    t9, 0xB8(t9)          ; current inventory slot
    jalr  t9
    move  a0, v0
    move  a1, v0
    lw    t9, 0(s0)
    lw    t9, {vt_item}(t9)     ; GetInventoryItem(slot)
    jalr  t9
    move  a0, s0
    beqz  v0, plain
    move  s1, v0
    lw    t9, 0(s1)
    lw    t9, 0x20(t9)          ; a firearm?
    jalr  t9
    move  a0, s1
    beqz  v0, plain
    nop
    jal   {silenced}
    move  a0, s1
    beqz  v0, plain
    lui   v0, {r2s}
    sw    v0, 0x28(sp)          ; suppressed: radius/4, squared
plain:
    move  v0, s0
    lw    v1, 0x2C(sp)          ; heard at the shot
    b     ret
    move  a3, zero
hostile:
    lui   v0, %hi({clock})
    lw    v0, %lo({clock})(v0)
    lwc1  f1, 0xD4(v0)          ; now
    lui   v1, %hi({stamp})
    lwc1  f2, %lo({stamp})(v1)
    sub.s f2, f1, f2
    mtc1  zero, f3
    c.lt.s f2, f3               ; clock went back (new mission): go
    bc1t  fresh
    lui   v0, 0x3E80
    mtc1  v0, f3
    c.lt.s f2, f3               ; a comrade's shot spread less than 0.25 s ago: skip
    bc1t  none
    nop
fresh:
    swc1  f1, %lo({stamp})(v1)
    jal   {aimgr}               ; IkeAIMgr::Get
    nop
    move  a0, v0
    jal   {humanai}             ; IkeAIMgr::GetHumanAI(mgr, soldier)
    move  a1, s0
    beqz  v0, none
    addiu s1, v0, 0x68          ; the point he is engaging
    lw    a1, 0x64(v0)          ; his current threat
    bltz  a1, none
    lui   v0, %hi({objmgr})
    jal   {getctl}              ; GetAFreakinIkeSimController(mgr, id)
    lw    a0, %lo({objmgr})(v0)
    move  v1, s1
    b     ret
    addiu a3, zero, 1
none:
    move  v0, zero
ret:
    lwc1  f0, 0x28(sp)
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    ld    ra, 0x20(sp)
    jr    ra
    addiu sp, sp, 0x30
"""

WATCH_SRC = """
watch:                          ; replaces jal ReportHeardGunshots(a0 team, a1 HumanAI, a2 awareness)
    addiu sp, sp, -0x50
    sd    ra, 0x40(sp)
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s2, 0x20(sp)
    move  s0, a0
    move  s1, a1
    jal   {report}              ; the stock report first
    move  s2, a2
    beqz  s0, done
    nop
    lbu   v0, 0xC0(s0)          ; a team that patrols is the engine's to investigate
    bnez  v0, done
    lw    v0, 0x14(s1)          ; SimHuman
    lw    v0, 0x174(v0)         ; alert level
    slti  v0, v0, 3
    beqz  v0, done              ; in combat: his behaviours aim him
    nop
    jal   {isempty}
    lw    a0, 0xC(s1)           ; his own script
    beqz  v0, done              ; busy
    lwc1  f0, 0x10(s2)          ; heard at
    lwc1  f1, 0x2C(s1)          ; standing at
    sub.s f0, f0, f1
    lwc1  f2, 0x14(s2)
    lwc1  f3, 0x30(s1)
    sub.s f2, f2, f3
    mul.s f4, f0, f0
    mul.s f5, f2, f2
    add.s f4, f4, f5
    lui   v0, 0x3F80
    mtc1  v0, f5
    c.lt.s f4, f5               ; under a metre away: nothing to face
    bc1t  done
    sqrt.s f4, f4
    div.s f0, f0, f4
    div.s f2, f2, f4
    swc1  f0, 0x30(sp)
    swc1  f2, 0x34(sp)
    sw    zero, 0x38(sp)        ; level: no staring at the sky or the floor
    move  a0, s1
    addiu a1, sp, 0x30
    lui   v0, 0x3F49
    mtc1  v0, f12               ; +-45 degrees
    lui   v0, 0x4040
    jal   {scan}
    mtc1  v0, f13               ; a new look every ~3 s
done:
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    ld    ra, 0x40(sp)
    jr    ra
    addiu sp, sp, 0x50
"""

#: hearing radius (m) -> (radius^2, (radius/4)^2) as the upper halves of floats
RADII = {"40": (0x44C8, 0x42C8), "60": (0x4561, 0x4361), "80": (0x45C8, 0x43C8),
         "120": (0x4661, 0x4461)}

_HEAR_STOCK_HEX = (   # 0x00177DB8..0x00177FF0, dead libdev helpers
    "27BDFFC0FFB000000080802DFFB20020FFB1001000C0902DFFBF00300C05DE7000A0202D0040882D"
    "0C05DE320200202D3C02FFFF8E0300103442FFFF54620001AE1100108E0200002403FFF3AE120020"
    "00431024DFBF003034420101DFB20020AE020000DFB10010DFB0000003E0000827BD004000000000"
    "27BDFFC0FFB000000080802DFFB20020FFB1001000C0902DFFBF00300C05DE7000A0202D0040882D"
    "0C05DE320200202D3C02FFFF8E0300103442FFFF54620001AE1100108E0200002403FFF3AE120020"
    "00431024DFBF003034420109DFB20020AE020000DFB10010DFB0000003E0000827BD004000000000"
    "27BDFFE0FFB00000FFBF00100C05DE320080802D8E0200002403FFF32404FFFEAE00002000431024"
    "DFBF0010344200040044102434420100AE020000DFB0000003E0000827BD002027BDFFC0FFB00000"
    "0080802DFFB20020FFB1001000C0902DFFBF00300C05DE7000A0202D0040882D0C05DE320200202D"
    "3C02FFFF8E0300103442FFFF54620001AE1100108E0200002403FFF32404FFFEAE12002000431024"
    "DFBF003000441024DFB2002034420100DFB10010AE020000DFB0000003E0000827BD004000000000"
    "27BDFFC0FFB000000080802DFFB20020FFB1001000C0902DFFBF00300C05DE7000A0202D0040882D"
    "0C05DE320200202D3C02FFFF8E0300103442FFFF54620001AE1100108E0200002403FFF32404FFFE"
    "AE12002000431024DFBF003034420008DFB2002000441024DFB1001034420100AE020000DFB00000"
    "03E0000827BD0040"
)
_WHO_STOCK_HEX = (    # 0x00181858..0x001819B4, dead SIF RPC wrappers
    "3C02005727BDFFD08C435008FFBF002004610003FFB00010100000110000102D3C0400623C100062"
    "24848800AFA00000240500060000302D0000382D0000402D26098840240A00040C05F5AA0000582D"
    "044300038E0288403C02FFFF3442FFFFDFBF0020DFB0001003E0000827BD00303C02005727BDFFD0"
    "8C435008FFBF002004610003FFB00010100000110000102D3C0400623C10006224848800AFA00000"
    "240500070000302D0000382D0000402D26098840240A00040C05F5AA0000582D044300038E028840"
    "3C02FFFF3442FFFFDFBF0020DFB0001003E0000827BD00303C03005727BDFFD08C6250080080282D"
    "FFBF002004410003FFB00010100000130000102D3C0700623C040062ACE588803C10006224848800"
    "24E78880AFA00000240500080000302D2408000426098840240A00040C05F5AA0000582D04430003"
    "8E0288403C02FFFF3442FFFFDFBF0020DFB0001003E0000827BD0030"
)
_WATCH_STOCK_HEX = (  # 0x001969D8..0x00196AB8, dead VU0 helpers
    "27BDFFC0FFB10010FFB000000080882DE7B4003000A0802DFFBF00200C060CC846006506DA040000"
    "4408A00048A828004A6503BC4A0003BF4BE0211CFA24000010400006DFBF0020DFB10010DFB00000"
    "C7B4003008060CDE27BD0040DFB10010DFB00000C7B4003003E0000827BD004027BDFFC0FFB10010"
    "FFB000000080882DE7B4003000A0802DFFBF00200C060CC846006506DA0400004408A00048A82800"
    "4A6503BC4A0003BF4BC0211CFA24000010400006DFBF0020DFB10010DFB00000C7B4003008060CDE"
    "27BD0040DFB10010DFB00000C7B4003003E0000827BD0040"
)


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())            # fixed 8-digit words, never .split() alone
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


JS_STOCK = _stock_words(HEAR_CAVE, _HEAR_STOCK_HEX)
JS_STOCK.update(_stock_words(WATCH_CAVE, _WATCH_STOCK_HEX))
JS_STOCK.update(_stock_words(WHO_CAVE, _WHO_STOCK_HEX))
JS_STOCK[PROP] = PROP_STOCK
JS_STOCK[REPORT_HOOK] = REPORT_STOCK
assert len([a for a in JS_STOCK if HEAR_CAVE <= a < HEAR_END]) == (HEAR_END - HEAR_CAVE) // 4
assert len([a for a in JS_STOCK if WATCH_CAVE <= a < WATCH_END]) == (WATCH_END - WATCH_CAVE) // 4
assert len([a for a in JS_STOCK if WHO_CAVE <= a < WHO_END]) == (WHO_END - WHO_CAVE) // 4

_GR_ISLAND_HEX = (    # every GR island, 0x00139140 + 0x70 * i: RSArray<RSArray<...>*>::~RSArray
    "27BDFFD0 FFBF0020 7FB10010 7FB00000 70808E28 1220000C 70A08628 8E240000"
    "10800004 0010143C 0C040AF8 00000000 0010143C 0002143F 18400004 72201628"
    "0C040B14 72202628 72201628 DFBF0020 7BB10010 7BB00000 03E00008 27BD0030"
)
GR_PROP = 0x003F2960                # PropagateForAI: jr ra; nop
GR_REPORT_HOOK = 0x0019DFBC         # HumanAIAwareness::Update: jal FireTeamAI::ReportHeardGunshots
GR_REPORT_STOCK = 0x0C0628E0
GR_STOCK = {}
for _a in GR_ISLANDS:
    GR_STOCK.update(_stock_words(_a, _GR_ISLAND_HEX))
GR_STOCK[GR_PROP] = PROP_STOCK
GR_STOCK[GR_REPORT_HOOK] = GR_REPORT_STOCK

GAMES = {
    "js": dict(STOCK=JS_STOCK, SYMS=SYMS, VT=JS_VT, HEAR=[(HEAR_CAVE, STAMP)], WHO=[(WHO_CAVE, WHO_END)],
               WATCH=[(WATCH_CAVE, WATCH_END)], STAMP=STAMP, PROP=PROP, REPORT_HOOK=REPORT_HOOK,
               REPORT_STOCK=REPORT_STOCK),
    "gr": dict(STOCK=GR_STOCK, SYMS=GR_SYMS, VT=GR_VT, HEAR=GR_HEAR, WHO=GR_WHO, WATCH=GR_WATCH,
               STAMP=GR_STAMP, PROP=GR_PROP, REPORT_HOOK=GR_REPORT_HOOK, REPORT_STOCK=GR_REPORT_STOCK),
}

_BRANCH = {"b", "beq", "bne", "beqz", "bnez", "blez", "bgtz", "bltz", "bgez", "bc1f", "bc1t",
           "j", "jal", "jr", "jalr"}


def _spread(src, caves, what):
    """Assemble `src` over `caves` [(start, end), ...]: where one fills, a `j` to the next (never
    between a branch and its delay slot). -> [(va, word)], labels."""
    items = Asm._items(src)
    left = sum(1 for kind, _ in items if kind == "ins")
    caves = list(caves)
    pc, end = caves.pop(0)
    placed, labels, pending, slot = [], {}, [], False
    for kind, x in items:
        if kind == "label":
            pending.append(x)
            continue
        need = 2 if x.split()[0] in _BRANCH else 1
        if not slot and pc + 4 * left > end and pc + 4 * (need + 2) > end:
            if not caves:
                raise ValueError("%s routine outgrows its caves" % what)
            placed += [(pc, "j %#x" % caves[0][0]), (pc + 4, "nop")]
            pc, end = caves.pop(0)
        labels.update((p, pc) for p in pending)
        pending = []
        placed.append((pc, x))
        pc, left, slot = pc + 4, left - 1, need == 2
    if pc > end:
        raise ValueError("%s routine outgrows its caves" % what)
    return [(va, assemble(x, va, labels)[0][0]) for va, x in placed], labels


def _fmt(g):
    return {k: "%#x" % v for k, v in dict(g["SYMS"], **g["VT"]).items()}


def hear_words(radius: str, game: str = "js"):
    g = GAMES[game]
    return _spread(HEAR_SRC.format(**_fmt(g)), g["HEAR"], "hearing")


def who_words(radius: str, allies: bool = False, game: str = "js"):
    g = GAMES[game]
    r2, r2s = RADII[radius]
    return _spread(WHO_SRC.format(r2="%#x" % r2, r2s="%#x" % r2s, hostile="hostile" if allies else "none",
                                  **_fmt(g)), g["WHO"], "who")


def watch_words(game: str = "js"):
    g = GAMES[game]
    return _spread(WATCH_SRC.format(**_fmt(g)), g["WATCH"], "watch")


def edits(radius: str = "off", watch: bool = False, allies: bool = False, game: str = "js"):
    """(va, value, stock, note). `watch` and `allies` act on heard gunshots, so they need a radius."""
    g = GAMES[game]
    st = g["STOCK"]
    out = []
    if radius in (None, "", "off"):
        return out
    w, _ = hear_words(radius, game)
    out += [(va, x, st[va], "hearing: gunshots reach soldiers within %s m" % radius) for va, x in w]
    w, _ = who_words(radius, allies, game)
    out += [(va, x, st[va], "hearing: whom a shot is of, and how far it carries") for va, x in w]
    if allies:
        out.append((g["STAMP"], 0, st[g["STAMP"]], "hearing: time a comrade's shot last spread (starts at 0)"))
    out.append((g["PROP"], assemble("j %#x" % g["HEAR"][0][0], g["PROP"])[0][0], PROP_STOCK,
                "hearing: SoundPropagationManager::PropagateForAI stub -> the routine"))
    if watch:
        w, _ = watch_words(game)
        out += [(va, x, st[va], "hearing: posted guards watch the shot's direction") for va, x in w]
        out.append((g["REPORT_HOOK"], assemble("jal %#x" % g["WATCH"][0][0], g["REPORT_HOOK"])[0][0],
                    g["REPORT_STOCK"], "hearing: ReportHeardGunshots through the watch routine"))
    return out


def js_edits(v: dict):
    return edits(v.get("js_hear_gunshots", "off"), bool(v.get("js_heard_watch")),
                 bool(v.get("js_hear_allies")))


def gr_edits(v: dict):
    return edits(v.get("gr_hear_gunshots", "off"), bool(v.get("gr_heard_watch")),
                 bool(v.get("gr_hear_allies")), "gr")


def cards(prefix: str = "js_", group: str = "Enemies") -> list:
    gr = prefix == "gr_"     # GR's "shooting at me" radius drops to 10 m once the player's fire team updates
    return [
        Setting(prefix + "hear_gunshots", "Enemies hear gunfire", CHOICE, "off", group,
                confidence="experimental",
                choices=[
                    Choice("off", "Off (as shipped)", "Only bullets passing within 10 m alert anyone."),
                    Choice("40", "40 m", ""),
                    Choice("60", "60 m", "Covers a fight about 50 m from the next group."),
                    Choice("80", "80 m", ""),
                    Choice("120", "120 m", "Most of a %smap section hears a firefight." % ("" if gr else "jungle ")),
                ],
                help="The game has code for enemies hearing gunshots, but the step that "
                     "delivers the sound to them is an empty stub, so a firefight 50 m "
                     "away goes unnoticed. With this, every shot fired by you, your squad "
                     "or allies reaches enemy soldiers within the chosen distance (a "
                     "quarter of it for a suppressed gun). The game's own reaction then "
                     "runs: each one looks toward the shooter and goes on alert, anyone "
                     "within %s m reacts as if under fire, and a fire team that patrols "
                     "comes to investigate if it is outdoors and within 150 m. Guards "
                     "posted at a fixed spot stay there. Walls do not muffle it. Enemy "
                     "shots alert other enemies only with 'Enemies come to help'. Your "
                     "squad does not hear anything new (an investigation would pull it "
                     "off your orders)." % ("10" if gr else "20"),
                caution="Never played. Makes missions harder: shooting draws nearby "
                        "patrols, and they head for your position at the time of the "
                        "shot. Online co-op: only the host's disc counts."),
        Setting(prefix + "heard_watch", "Guards watch where shots came from", BOOL, False, group,
                confidence="experimental",
                requires={prefix + "hear_gunshots": ("40", "60", "80", "120")},
                help="A posted guard who hears a shot keeps facing his post, or whatever "
                     "he last looked at, which is often a wall. With this, an idle guard "
                     "(one whose team never patrols) who hears gunfire and is not already "
                     "fighting scans a 90-degree arc toward the shot, eyes level, with a "
                     "new look about every 3 s. He stays at his post and is ready when "
                     "you come around the corner.",
                caution="Never played. Needs 'Enemies hear gunfire'. Online co-op: only "
                        "the host's disc counts."),
        Setting(prefix + "hear_allies", "Enemies come to help when a comrade fires", BOOL, False,
                group, confidence="experimental",
                requires={prefix + "hear_gunshots": ("40", "60", "80", "120")},
                help="An enemy firing at you is heard by his own side too: enemy soldiers "
                     "within the hearing distance of him who are not fighting yet -- his "
                     "own fire team included -- look toward what he is shooting at (you, "
                     "not him) and go on alert, and a patrolling team comes to investigate "
                     "that spot, under the same rules as for your shots. Guards at posts "
                     "turn to watch it when 'Guards watch where shots came from' is on. "
                     "Only a soldier who knows his target spreads the word (not one "
                     "spraying at a spot), and only one comrade's shot every quarter "
                     "second across the map is passed on, so a big firefight costs little.",
                caution="Never played. Fights grow: nearby teams join in. Online co-op: "
                        "only the host's disc counts."),
    ]


def selftest(js_elf: bytes, gr_elf: bytes = None):
    """Every stock word against the executable(s), no address twice. [] = pass."""
    bad = []
    for game, st, elf, d in (("js", JS_STOCK, js_elf, 0x100), ("gr", GR_STOCK, gr_elf, 0x80)):
        for va, w in st.items() if elf is not None else ():
            off = va - 0x100000 + d
            if int.from_bytes(elf[off:off + 4], "little") != w:
                bad.append("%s %08X" % (game, va))
        for r in RADII:
            e = edits(r, True, True, game)
            if len({va for va, *_ in e}) != len(e):
                bad.append("%s duplicate VA (%s)" % (game, r))
            if any(va not in st for va, *_ in e):
                bad.append("%s VA without a stock word (%s)" % (game, r))
    return bad

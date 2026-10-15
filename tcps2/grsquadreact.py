"""Your AI team-mates react to being shot at: Jungle Storm (SLUS-20820) and Ghost Recon (SLUS-20613).

Two options for the AI soldiers in a fireteam that a human player is in: online
co-op's AI backup and split screen's fireteams (grsquad) in Jungle Storm, split
screen in Ghost Recon -- and, by the same test, your own fireteam in single
player. Enemies, all-AI fireteams (co-op's Charlie, a fireteam whose player has
left it) and the players' own soldiers are left exactly as stock.

How the game tells a soldier he is being shot at
------------------------------------------------

Every round ends in IkeSimulationMgr::GunshotAlert (JS 0x00370C50, GR 0x003933C0,
called by HandleWorldShot, HandleControllerShot -- a hit on a soldier -- and
HandleGunshotMissed). It walks the simulation's controllers and, for each soldier
of another company (not disabled, not out of action) nearer the muzzle than the
round's length plus 10 m (3 m for a suppressed gun) whose 10 m (3 m) sphere the
line of fire crosses, calls AwarenessMgr::HandleBulletWhiz (JS 0x003D64A0, GR
0x003F66D0): an awareness of the shooter, "target 7", heard where he fired from.
That soldier's HumanAIAwareness::Update then (after his reaction delay) glances at
the shooter (HumanAI::GlanceAt: he turns to look at the shooter's eye point and
keeps looking back at it now and then for ~20 s), goes on alert, and calls
FireTeamAI::ReportUnderFire (JS 0x003DA970, GR 0x00189F60): the team's danger
level goes to 3 -- the level at which HumanAI::UpdateCombat (JS 0x003E4720, GR
0x001944C0) puts EngageThreatBehavior on a member for whatever he sees, whatever
the combat ROE -- and the shooter goes on the team's enemy list (AddEnemy, with
his position). Then HumanAI::YouAreBeingShotAt.

So a team-mate reacts only to rounds passing within 10 m of himself. When the
enemy shoots at you, nobody reacts on your behalf: your soldier is not AI-driven.
A team-mate 15 m away while you are pinned, or holding a spot you ordered, or the
other team-mates when one is hit, carry on as if nothing happened (savestate
FA828984.01: the host shot at from 27 m -- his team-mate 3.7 m away gets the
alert, the one 17 m away nothing).

And none of them takes cover. A player's fireteam runs TeamWingmanBehavior (GR
Process 0x001C44F0, JS 0x001C1400 -- vtable slot +0x38 in both): FollowPlayer
gives each AI a MoveInFormation behind you; only after you have stood still for
5 s with them near you does it call FireTeamAI::CoverForward (a CoverArea each,
facing your forward, 60 degrees, no end). Under fire a team-mate who has reached
his formation slot stands there with nothing on his script.

What the options do
-------------------

  * Return fire (js_/gr_squad_return_fire). GunshotAlert's call to
    HandleBulletWhiz goes through `rf`: the stock call first; then, if the
    listener (the soldier the round passed) is in a fireteam that has a player
    in it (FireTeamAI::GetPlayerAI, the test TeamWingman itself uses -- a
    network player counts, as he does for TeamWingman), every other AI soldier
    of that fireteam gets the same HandleBulletWhiz -- the same shooter, the
    same "fired from" point -- and so reacts exactly as the game makes a
    soldier react to rounds cracking past him: turns to look at the shooter,
    goes on alert, puts him on the team's enemy list, raises the team to
    combat. Engaging is the game's own: a team-mate who then sees the shooter
    (sight is unchanged) gets UpdateCombat's EngageThreatBehavior. Skipped:
    players (never touched), disabled or out-of-action soldiers, the listener
    himself, a team-mate GunshotAlert alerts itself for this round (its two
    tests are repeated with GunshotAlert's own registers -- the radius and the
    reach in f20/f21, the direction in s2 -- so nobody counts one round twice),
    and a team-mate whose newest sound is a bullet whiz or a heard gunshot under
    a second old: automatic fire passes on one alert per team-mate per second.
  * Take cover (js_/gr_squad_cover). HumanAIAwareness::Update's call to
    ReportUnderFire goes through `uf`: the stock report first; then, for an
    AI-controlled soldier of a fireteam with a player in it who is accepting orders
    (HumanAI::AcceptingOrders) and is standing (empty script) or following
    (MoveInFormation on top), the game's own CoverAreaBehavior goes on top of
    his script: facing the shooter's position, a 45-degree arc, ending 6 s
    after the shot. That is what grtactics gives enemies as "hold cover": he
    crouches at his spot and peeks (CoverAreaBehavior::UpdatePeek), scans the
    arc, looks at the team's known enemy in it, and UpdateCombat puts
    EngageThreat on top of the cover when he sees someone. Every further shot
    at him he notices pushes the end out to 6 s after it, so he stays down
    while the fire lasts. When it ends the behaviour under it resumes --
    MoveInFormation (he follows you again) or the empty script of a Hold or a
    reached move-to spot. A soldier already fighting, moving to an ordered spot
    (LocationBehavior), in the game's own cover (CoverForward's, a fight's),
    riding, fleeing etc. is left alone. A new order (Hold/Advance, move-to,
    you walking off from a CoverForward stop -- TeamWingman's FollowPlayer)
    clears his script and the cover with it, as it clears any behaviour. Our
    cover is told from the game's by its arc, 0x3F490F5D (0.7853907 rad =
    45.0 degrees, 126 ulps below the game's pi/4): no data word, no `ori` of
    that low half after a `lui 0x3F49`, in either executable or overlay.
  * Both on: the whole fireteam takes cover when any member (you included) is
    shot at.

Online co-op: only the host runs the AI. A joiner's console has no FireTeamAI
objects (IkeAIMgr vt+0x14 answers 0 for every fireteam, read in joiner RAM in
grcooporders' work), so IkeAIMgr::GetHumanAI answers 0 for every soldier there:
`rf` returns after the stock call and `uf` never runs (there are no HumanAI
updates). All the options change is host AI state -- awareness entries, team
danger and enemy list, a behaviour on a script -- and the soldiers' resulting
movement, stance and fire reach the joiners as they always do. The routines draw
no random numbers; GlanceAt / CoverArea's own ones are the host's, as before. A
stock host with a patched joiner, or the reverse, simply has the options off.

The patch
---------

  JS 0x00370E04 / GR 0x00393578  GunshotAlert's `jal HandleBulletWhiz`
       (0x0C0F5928 / 0x0C0FD9B4) -> `jal rf`          (return fire)
  JS 0x003EDD8C / GR 0x0019DF6C  HumanAIAwareness::Update's
       `jal ReportUnderFire` (0x0C0F6A5C / 0x0C0627D8) -> `jal uf`  (cover)

Both routines make the replaced call first with the caller's arguments and return
to the instruction after it; s0-s6, ra and f20-f31 come back intact.

Caves (dead library code: no jal/j, no branch from outside, no lui/low-half pair
and no aligned word anywhere in the executable or the JS overlays refers to them;
no RAM word equals their start in 8 JS / 4 GR savestates, where the same count
finds CoverArea::Process's vtable entry; no other option writes them). A routine
runs across its islands with a `j` to the next one:

  JS rf (128 words): 0x001692A8..0x0016932F, 0x0016B648..0x0016B6B7, 0x0016C2B8..0x0016C31B,
         0x0016D450..0x0016D4D7, 0x0016DD80..0x0016DD9B -- unreferenced newlib functions
  JS uf (88): 0x001819B8..0x00181A37 (a SIF RPC wrapper), 0x00183EF0..0x00183F6F,
         0x00197AD8..0x00197B37 (a VU0 helper)
  GR rf (122): sceMcDelete 0x00421BC0..0x00421CE7, sceMcGetEntSpace 0x004221A8..0x00422267
  GR uf (86): sceCdInitEeCB 0x0040C398..0x0040C46B, sceDmaWatch 0x0040F9B8..0x0040FA3B
  (the stock tables cover the whole functions; only these words are written)

Checked in the RAM interpreter on real savestates (co-op host, split screen,
single player; agent T's scratch vjs.py): the real GunshotAlert, each team-mate's
real HumanAIAwareness::Update (sight and voices stubbed), his real
RSScript::Process over time. Not yet played.
"""

from __future__ import annotations

import struct

from .grasm import Asm, assemble
from .model import BOOL, Setting

HOLD = 6.0                 # s after the last noticed shot before a team-mate gets up again
ARC = 0x3F490F5D           # 45 degrees, our mark

GAMES = {
    "js": dict(
        RF_HOOK=0x00370E04, RF_STOCK=0x0C0F5928,
        UF_HOOK=0x003EDD8C, UF_STOCK=0x0C0F6A5C,
        RF=[(0x001692A8, 0x00169330), (0x0016B648, 0x0016B6B8), (0x0016C2B8, 0x0016C320),
            (0x0016D450, 0x0016D4D8), (0x0016DD80, 0x0016DE00)],
        UF=[(0x001819B8, 0x00181A38), (0x00183EF0, 0x00183F70), (0x00197AD8, 0x00197B58)],
        SYMS=dict(
            whiz=0x003D64A0,      # AwarenessMgr::HandleBulletWhiz(mgr, listener, shooter, &from)
            aimgr=0x001225D0,     # IkeAIMgr::Get
            humanai=0x003F17D0,   # IkeAIMgr::GetHumanAI(mgr, SimHuman)
            playerai=0x003DD160,  # FireTeamAI::GetPlayerAI
            member=0x003DF0F0,    # FireTeamAI::GetHumanAI(team, i)
            disabled=0x003577F0,  # IkeSimController::IsDisabled
            ndx=0x003429E0,       # IkeSimController::GetAwarenessNdx
            brain=0x003429B0,     # AwarenessMgr::GetBrain(mgr, ndx)
            clock=0x00684768,     # RSClock*, +0xD4 seconds
            ruf=0x003DA970,       # FireTeamAI::ReportUnderFire(team, HumanAI, shooter id, bool)
            accept=0x003E4260,    # HumanAI::AcceptingOrders
            objmgr=0x0062B748,    # IkeObjectMgr*
            getctl=0x00340F30,    # IkeObjectMgr::GetAFreakinIkeSimController(mgr, id)
            addelem=0x001B6E10,   # RSScript::AddElement
            distsq=0x0010A830,    # DistanceSquared(a, b)
            intersect=0x0010CB40, # IntersectLineWithSphere(point, unit dir, centre, f12 radius, &t1, &t2)
            vt_ooa=0x29C,         # IkeSimController::IsOutOfAction
            vt_pos=0x238,         # IkeSimController::GetWorldPosition
        ),
        # GunshotAlert's registers at the hook: f20 = (length + radius)^2, f21 = radius
        THR="f20", RAD="f21",
        # IkeAIMgr::GetPoolCoverAreaBehavior (0x003F1BE0) with the manager at 0x0062C6F8
        POOL="    lui   at, 0x63\n    jal   0x3f1be0\n    lw    a0, -0x3908(at)\n",
    ),
    "gr": dict(
        RF_HOOK=0x00393578, RF_STOCK=0x0C0FD9B4,
        UF_HOOK=0x0019DF6C, UF_STOCK=0x0C0627D8,
        RF=[(0x00421BC0, 0x00421CE8), (0x004221A8, 0x004222C0)],
        UF=[(0x0040C398, 0x0040C46C), (0x0040F9B8, 0x0040FA88)],
        SYMS=dict(
            whiz=0x003F66D0, aimgr=0x003663A0, humanai=0x001A1890, playerai=0x0018C930,
            member=0x0018EAD0, disabled=0x0037A070, ndx=0x00367250, brain=0x00367230,
            clock=0x005DFC20, ruf=0x00189F60, accept=0x00193F80, objmgr=0x005EAB20,
            getctl=0x00365830, addelem=0x001BAEC0, vt_ooa=0x298, vt_pos=0x234,
            distsq=0x001142E0, intersect=0x0010EEF0,
        ),
        THR="f21", RAD="f20",
        # IkeAIMgr::GetPoolCoverAreaBehavior (0x001A1CC0) with the manager at 0x005E5778
        POOL="    lui   at, 0x5e\n    jal   0x1a1cc0\n    lw    a0, 0x5778(at)\n",
    ),
}

# GunshotAlert's HandleBulletWhiz call: a0 AwarenessMgr, a1 the listener, a2 the shooter, a3 &where he fired from
RF_SRC = """
rf:
    addiu sp, sp, -0x90
    sd    ra, 0x80(sp)
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s2, 0x20(sp)          ; (GunshotAlert's s2: the shot's unit direction -- read back below)
    sq    s3, 0x30(sp)
    sq    s4, 0x40(sp)
    sq    s5, 0x50(sp)
    sq    s6, 0x60(sp)
    move  s0, a0
    move  s1, a1
    move  s2, a2
    jal   {whiz}                ; the stock alert for the listener
    move  s3, a3
    jal   {aimgr}               ; IkeAIMgr::Get
    nop
    move  a0, v0
    jal   {humanai}             ; the listener's HumanAI: none where the AI does not run
    move  a1, s1
    beqz  v0, rf_out
    nop
    lw    s4, 0xa4(v0)          ; his fireteam
    beqz  s4, rf_out
    nop
    jal   {playerai}            ; a player in it?
    move  a0, s4
    beqz  v0, rf_out            ; no: an enemy or an all-AI team, nothing more
    move  s5, zero
rf_loop:
    lw    v0, 0x18(s4)          ; members
    slt   v0, s5, v0
    beqz  v0, rf_out
    move  a0, s4
    jal   {member}              ; FireTeamAI::GetHumanAI(team, i)
    move  a1, s5
    beqz  v0, rf_next
    nop
    lw    s6, 0x14(v0)          ; his SimHuman
    beqz  s6, rf_next
    nop
    beq   s6, s1, rf_next       ; the listener has his alert
    nop
    lw    t9, 0x100(s6)
    lw    t9, 0xf8(t9)          ; AI-controlled? (GetPlayerAI's own test: 0 = a player)
    jalr  t9
    addiu a0, s6, 0x100
    beqz  v0, rf_next           ; players are never touched
    nop
    jal   {disabled}
    move  a0, s6
    bnez  v0, rf_next
    nop
    lw    t9, 0(s6)
    lw    t9, {vt_ooa}(t9)      ; IsOutOfAction
    jalr  t9
    move  a0, s6
    bnez  v0, rf_next
    nop
    lw    t9, 0(s6)
    lw    t9, {vt_pos}(t9)      ; GetWorldPosition
    jalr  t9
    move  a0, s6
    sw    v0, 0x70(sp)
    move  a1, v0
    jal   {distsq}              ; GunshotAlert's own two tests: is he a listener of this round too?
    move  a0, s3
    c.lt.s f0, {thr}
    bc1f  rf_far
    move  a0, s3
    lw    a1, 0x20(sp)          ; the direction
    lw    a2, 0x70(sp)
    mov.s f12, {rad}
    addiu a3, sp, 0x74
    jal   {intersect}
    addiu t0, sp, 0x78
    bnez  v0, rf_next           ; yes: GunshotAlert alerts him itself
    nop
rf_far:
    jal   {ndx}
    move  a0, s6
    move  a1, v0
    jal   {brain}               ; his MentalImage
    move  a0, s0
    beqz  v0, rf_next
    nop
    lw    v1, 8(v0)             ; sound list
    beqz  v1, rf_tell
    lw    v1, 0x10(v0)          ; (delay) its newest entry
    lhu   v0, 0x28(v1)
    andi  v0, v0, 0x1e0
    xori  t0, v0, 0xe0          ; a bullet whiz
    beqz  t0, rf_age
    xori  t0, v0, 0xa0          ; (delay) a heard gunshot
    bnez  t0, rf_tell
    nop
rf_age:
    lui   v0, %hi({clock})
    lw    v0, %lo({clock})(v0)
    lwc1  f1, 0xd4(v0)
    lwc1  f2, 0x1c(v1)
    sub.s f1, f1, f2
    lui   v0, 0x3f80
    mtc1  v0, f2
    c.lt.s f1, f2               ; under a second old: he is already reacting
    bc1t  rf_next
    nop
rf_tell:
    move  a0, s0
    move  a1, s6
    move  a2, s2
    jal   {whiz}                ; the same alert: shot at, from where the shooter fired
    move  a3, s3
rf_next:
    b     rf_loop
    addiu s5, s5, 1
rf_out:
    ld    ra, 0x80(sp)
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    lq    s3, 0x30(sp)
    lq    s4, 0x40(sp)
    lq    s5, 0x50(sp)
    lq    s6, 0x60(sp)
    jr    ra
    addiu sp, sp, 0x90
"""

# HumanAIAwareness::Update's ReportUnderFire call: a0 fireteam, a1 HumanAI, a2 shooter id, a3 0
UF_SRC = """
uf:
    addiu sp, sp, -0x50
    sd    ra, 0x40(sp)
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s2, 0x20(sp)
    move  s0, a0
    move  s1, a1
    jal   {ruf}                 ; the stock report first
    move  s2, a2
    beqz  s0, uf_out
    nop
    jal   {playerai}            ; a players' fireteam?
    move  a0, s0
    beqz  v0, uf_out            ; no: enemies and all-AI teams stay stock
    nop
    beq   v0, s1, uf_out        ; (the player himself)
    lw    v0, 0x14(s1)          ; (delay) his SimHuman
    beqz  v0, uf_out
    nop
    lw    t9, 0x100(v0)
    lw    t9, 0xf8(t9)          ; AI-controlled? (GetPlayerAI's own test: 0 = a player -- a second
    jalr  t9                    ;   human in the same fireteam is never touched either)
    addiu a0, v0, 0x100
    beqz  v0, uf_out
    nop
    jal   {accept}              ; HumanAI::AcceptingOrders
    move  a0, s1
    beqz  v0, uf_out
    lui   at, %hi({clock})
    lw    v0, %lo({clock})(at)
    lwc1  f0, 0xd4(v0)          ; now
    lui   v0, {hold_hi}
    mtc1  v0, f1
    add.s f0, f0, f1            ; + the hold: when he gets up again
    lw    v0, 0xc(s1)           ; his script
    lw    v0, 4(v0)             ; its top behaviour
    beqz  v0, uf_new            ; standing with nothing to do: take cover
    lui   t1, {arc_hi}          ; (delay)
    lw    v1, 4(v0)             ; its type
    addiu t0, v1, -3
    beqz  t0, uf_new            ; following (MoveInFormation): take cover
    addiu t0, v1, -0x13
    bnez  t0, uf_out            ; anything else (fighting, moving, ...): as stock
    ori   t1, t1, {arc_lo}      ; (delay)
    lw    t0, 0x34(v0)          ; a CoverArea: ours (the marked arc)?
    bne   t0, t1, uf_out        ; the game's own cover: leave it
    nop
    b     uf_out
    swc1  f0, 0x40(v0)          ; ours: stay down until the hold after this shot
uf_new:
    swc1  f0, 0x30(sp)
    lui   v0, %hi({objmgr})
    lw    a0, %lo({objmgr})(v0)
    jal   {getctl}              ; the shooter
    move  a1, s2
    beqz  v0, uf_out
    nop
    lw    t9, 0(v0)
    lw    t9, {vt_pos}(t9)      ; GetWorldPosition
    jalr  t9
    move  a0, v0
    move  s2, v0
{pool}    lwc1  f0, 0(s2)
    swc1  f0, 0x1c(v0)          ; face the shooter
    lwc1  f0, 4(s2)
    swc1  f0, 0x20(v0)
    lwc1  f0, 8(s2)
    swc1  f0, 0x24(v0)
    lui   t1, {arc_hi}
    ori   t1, t1, {arc_lo}
    sw    t1, 0x34(v0)          ; a 45-degree arc, marked as ours
    lwc1  f0, 0x30(sp)
    swc1  f0, 0x40(v0)          ; until the hold after this shot
    lw    a0, 0xc(s1)
    jal   {addelem}             ; on top of his script: when it ends, his order resumes
    move  a1, v0
uf_out:
    ld    ra, 0x40(sp)
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    jr    ra
    addiu sp, sp, 0x50
"""

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
    f = {k: "%#x" % v for k, v in g["SYMS"].items()}
    f.update(hold_hi="%#x" % (struct.unpack("<I", struct.pack("<f", HOLD))[0] >> 16),
             arc_hi="%#x" % (ARC >> 16), arc_lo="%#x" % (ARC & 0xFFFF), pool=g["POOL"],
             thr=g["THR"], rad=g["RAD"])
    return f


def rf_words(game="js"):
    g = GAMES[game]
    return _spread(RF_SRC.format(**_fmt(g)), g["RF"], "return-fire")


def uf_words(game="js"):
    g = GAMES[game]
    return _spread(UF_SRC.format(**_fmt(g)), g["UF"], "cover")


_JS_ISLAND_HEX = {
    0x001692A8: (
        "27BDFFC0 24030001 FFB10028 00A0882D FFB20030 00C0902D FFB00020 02518018"
        "AFA40010 00E0202D 27A20010 03A0282D FFBF0038 AFA20000 AFA30004 AFB00014"
        "0C05A38C AFB00008 54400003 8FA20008 10000006 0240102D 52200001 000001CD"
        "02021023 0051001B 00001012 DFB00020 DFB10028 DFB20030 DFBF0038 03E00008"
        "27BD0040 00000000"
    ),
    0x0016B648: (
        "27BDFFF0 FFB00000 0080802D 2A020018 3404FFC0 000423BC 10400007 FFBF0008"
        "001018C0 3C020058 00431021 DC42FB68 1000000C DFB00000 1A000008 00000000"
        "34058048 00052BFC 0C067866 2610FFFF 0040202D 1E00FFFA 00000000 0080102D"
        "DFB00000 DFBF0008 03E00008 27BD0010"
    ),
    0x0016C2B8: (
        "27BDFFE0 FFB00000 3C100057 FFB10008 00A0882D FFB20010 0080902D FFBF0018"
        "26108E00 0C05A974 8E040000 8E040000 0240282D 0C05B0C8 0220302D 8E040000"
        "0C05A994 0040882D 0220102D DFB00000 DFB10008 DFB20010 DFBF0018 03E00008"
        "27BD0020 00000000"
    ),
    0x0016D450: (
        "27BDFF40 3C027FFF 00A0182D 00C0282D AFA40054 03A0202D 3442FFFF 240C0208"
        "27A60098 FFBF0060 AFA30010 AFA30000 FFA70098 FFA800A0 FFA900A8 FFAA00B0"
        "FFAB00B8 E7AC0078 E7AD007C E7AE0080 E7AF0084 E7B00088 E7B1008C E7B20090"
        "E7B30094 A7AC000C AFA20014 0C05C332 AFA20008 8FA30000 DFBF0060 A0600000"
        "03E00008 27BD00C0"
    ),
    0x0016DD80: (
        "90880000 0100102D 1040001A 0080482D 00A0302D 80C30000 10600012 90C70000"
        "00021600 00021603 1043000C 00081600 00021603 24C60001 80C30000 10600009"
        "90C70000 00000000 00000000 00000000 00000000 5443FFF8 24C60001 14E00005"
        "00000000 24840001 90820000 1440FFE8 0040402D 03E00008 00891023 00000000"
    ),
    0x001819B8: (
        "3C030057 27BDFFD0 8C625008 0080282D FFBF0020 04410003 FFB00010 10000013"
        "0000102D 3C070062 3C040062 ACE58880 3C100062 24848800 24E78880 AFA00000"
        "24050009 0000302D 24080004 26098840 240A0004 0C05F5AA 0000582D 04430003"
        "8E028840 3C02FFFF 3442FFFF DFBF0020 DFB00010 03E00008 27BD0030 00000000"
    ),
    0x00183EF0: (
        "27BDFFE0 FFB00000 FFBF0010 0C060CC8 00000000 0040802D 3C021000 34421010"
        "8C420000 30430080 14600007 00000000 1200000E 0000102D 0C060CDE 00000000"
        "1000000A 0000102D 3C04FFFF 3484F37F 0C060F00 00442024 12000004 24020001"
        "0C060CDE 00000000 24020001 DFBF0010 DFB00000 03E00008 27BD0020 00000000"
    ),
    0x00197AD8: (
        "27BDFFE0 FFB00000 FFBF0010 0C060CC8 0080802D 4BE0012C 3C034580 00031C38"
        "34634580 00031C38 DA070000 48A33000 48C08000 4BA4396C 4B87316C 4A0002FF"
        "4A0002FF 4A0002FF 4A0002FF 4A0002FF 48438000 306300C0 10400003 0060802D"
        "0C060CDE 00000000 0200102D DFBF0010 DFB00000 03E00008 27BD0020 00000000"
    ),
}
_GR_ISLAND_HEX = {
    0x00421BC0: (     # sceMcDelete
        "27BDFF80 FFB50060 FFB20030 0080A82D 3C120057 FFB40050 FFB10020 00A0A02D"
        "8E44F014 00C0882D FFBF0070 FFB30040 0C1046CC FFB00010 04410003 3C02005F"
        "10000030 2402FF38 24530B40 8E630024 14600005 00000000 0C1046C0 8E44F014"
        "10000028 2402FF9C 12200004 00000000 82220000 14400005 3C10005F 0C1046C0"
        "8E44F014 1000001F 2402FF2E 0220282D 26100C04 240603FF 0C101C9C 0200202D"
        "2603FFEC AE15FFEC AC740004 3C09005F A0600413 0260202D AC600008 0060382D"
        "25292100 2405000F AFA00000 24060001 24080414 240A0004 0C10531C 0000582D"
        "0040802D 16000004 3C030057 2402000F 10000003 AC62F010 0C1046C0 8E44F014"
        "0200102D DFBF0070 DFB50060 DFB40050 DFB30040 DFB20030 DFB10020 DFB00010"
        "03E00008 27BD0080"
    ),
    0x004221A8: (     # sceMcGetEntSpace
        "27BDFF90 FFB30040 FFB10020 0080982D 3C110057 FFB20030 FFB00010 00A0902D"
        "8E24F014 00C0802D FFBF0060 0C1046CC FFB40050 04410003 3C02005F 1000002E"
        "2402FF38 24540B40 8E830024 14600005 00000000 0C1046C0 8E24F014 10000026"
        "2402FF9C 12000004 00000000 82020000 14400005 3C02005F 0C1046C0 8E24F014"
        "1000001D 2402FF2E 0200282D 24500BF0 AC530BF0 AE120004 26040014 0C101C9C"
        "240603FF A2000413 3C09005F 0200382D 0280202D 25292100 24050012 AFA00000"
        "24060001 24080414 240A0004 0C10531C 0000582D 0040802D 16000004 3C030057"
        "24020012 10000003 AC62F010 0C1046C0 8E24F014 0200102D DFBF0060 DFB40050"
        "DFB30040 DFB20030 DFB10020 DFB00010 03E00008 27BD0070"
    ),
    0x0040C398: (     # sceCdInitEeCB
        "27BDFFA0 FFB40040 FFB10010 3C140056 0080882D FFB30030 FFB20020 24130001"
        "FFB00000 00A0902D 8E841D94 00C0802D 1480001C FFBF0050 0C104674 00000000"
        "3C03005F 3C05005F AC62B590 0040202D 0C104678 24A5B598 3C03005F 3C02005E"
        "3C050041 2463B5C8 24426CF0 24A5C2D8 AC70000C 0060202D AC620010 AC650004"
        "AC720008 0C104638 AC710014 0000282D AE821D94 0C104640 0040202D 10000005"
        "0260102D 0220282D 0C10465C 0000982D 0260102D DFBF0050 DFB40040 DFB30030"
        "DFB20020 DFB10010 DFB00000 03E00008 27BD0060"
    ),
    0x0040F9B8: (     # sceDmaWatch
        "27BDFFB0 24020001 FFB20020 FFB10010 00A0902D FFB00000 0080882D FFBF0040"
        "00E0802D 14C20004 FFB30030 8E220010 10000020 0052102B 8E220010 3C030100"
        "0052102B 1040001A 0070800A 3C130058 2610FFFF 00000000 06010011 00000000"
        "0C0403CC 266477E8 8E240000 00041202 30420001 1040000A 00000000 2405FEFF"
        "00851824 0000102D 0060202D 00000000 00000000 1440FFFA 00000000 AE230000"
        "8E220010 0052102B 1440FFEB 2610FFFF 0000102D DFBF0040 DFB30030 DFB20020"
        "DFB10010 DFB00000 03E00008 27BD0050"
    ),
}


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())            # fixed 8-digit words: adjacent literals join
    if len(words) % 8:
        raise ValueError("stock table is not a whole number of words")
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


def _stock(islands, hook_words):
    st = {}
    for base, hx in islands.items():
        st.update(_stock_words(base, hx))
    st.update(hook_words)
    return st


JS_STOCK = _stock(_JS_ISLAND_HEX, {GAMES["js"]["RF_HOOK"]: GAMES["js"]["RF_STOCK"],
                                   GAMES["js"]["UF_HOOK"]: GAMES["js"]["UF_STOCK"]})
GR_STOCK = _stock(_GR_ISLAND_HEX, {GAMES["gr"]["RF_HOOK"]: GAMES["gr"]["RF_STOCK"],
                                   GAMES["gr"]["UF_HOOK"]: GAMES["gr"]["UF_STOCK"]})
for _g, _st in (("js", JS_STOCK), ("gr", GR_STOCK)):
    for _lo, _hi in GAMES[_g]["RF"] + GAMES[_g]["UF"]:
        assert all(a in _st for a in range(_lo, _hi, 4)), (_g, hex(_lo))


def edits(return_fire=False, cover=False, game="js"):
    """(va, value, stock, note); [] when both options are off."""
    g = GAMES[game]
    st = JS_STOCK if game == "js" else GR_STOCK
    out = []
    if return_fire:
        w, lab = rf_words(game)
        out += [(va, x, st[va], "squad: team-mates hear rounds aimed at any of their fireteam") for va, x in w]
        out.append((g["RF_HOOK"], assemble("jal %#x" % lab["rf"], g["RF_HOOK"])[0][0], g["RF_STOCK"],
                    "squad: GunshotAlert's HandleBulletWhiz through the return-fire routine"))
    if cover:
        w, lab = uf_words(game)
        out += [(va, x, st[va], "squad: team-mates under fire hold cover facing the shooter") for va, x in w]
        out.append((g["UF_HOOK"], assemble("jal %#x" % lab["uf"], g["UF_HOOK"])[0][0], g["UF_STOCK"],
                    "squad: ReportUnderFire through the cover routine"))
    return out


def js_edits(v: dict):
    return edits(bool(v.get("js_squad_return_fire")), bool(v.get("js_squad_cover")), "js")


def gr_edits(v: dict):
    return edits(bool(v.get("gr_squad_return_fire")), bool(v.get("gr_squad_cover")), "gr")


def cards(prefix: str = "js_", group: str = "Squad") -> list:
    gr = prefix == "gr_"
    where = ("split screen, and your own fireteam in single player" if gr else
             "online co-op's AI backup, split screen, and your own fireteam in single player")
    online = "" if gr else " Online co-op: the host's disc does it."
    return [
        Setting(prefix + "squad_return_fire", "Team-mates react when the fireteam is shot at", BOOL, False,
                group, confidence="experimental",
                help="The game only alerts an AI team-mate when bullets crack past him. "
                     "When an enemy shoots at you, or at one of them, the others carry on "
                     "as if nothing happened. With this, any shot at a soldier of your "
                     "fireteam (you included) reaches every AI team-mate in it: each one "
                     "turns to look at the shooter, goes on alert, the shooter goes on "
                     "the team's enemy list and the team goes to combat, so a team-mate "
                     "who can see the shooter fires back whatever the combat ROE. It is "
                     "the game's own reaction to being shot at, passed to the whole "
                     "fireteam. Only the AI in a fireteam with a player in it (%s); "
                     "enemies and all-AI teams are unchanged, and your own soldier is "
                     "never touched." % where,
                caution="Never played. Team-mates do not see through walls: one who "
                        "cannot see the shooter only turns toward him. Under automatic "
                        "fire each team-mate is alerted at most once a second. Recon ROE "
                        "stealth ends once the fireteam is shot at (as it already did "
                        "when a team-mate was)." + online),
        Setting(prefix + "squad_cover", "Team-mates take cover under fire", BOOL, False, group,
                confidence="experimental",
                help="Your AI team-mates keep standing at their spot behind you while "
                     "rounds come in. With this, a team-mate who is shot at while "
                     "following you or standing (on Hold, or at a move-to spot) holds a "
                     "firing position where he is: he crouches, faces the shooter, peeks "
                     "and fires at what he sees in that direction -- the "
                     "'hold cover' the game gives enemy soldiers. 6 seconds after the "
                     "last shot at him he gets up and goes back to his order (follows "
                     "you again, keeps holding). A new order (Hold/Advance, move-to) "
                     "ends it at once. Team-mates already "
                     "fighting or moving to an ordered spot are left alone. With "
                     "'Team-mates react when the fireteam is shot at' the whole fireteam "
                     "takes cover when any of you is shot at.",
                caution="Never played. While the fire continues they stay down, so "
                        "they fall behind if you keep moving under fire, and catch up "
                        "when it stops." + online),
    ]


def selftest(gr_elf: bytes = None, js_elf: bytes = None, used: dict = None, claims: list = None):
    """Stock words against the executables, no VA twice, every routine fits its islands and stays
    inside them, no word outside the stock table. Optionally `used` = {"gr": set, "js": set} of
    addresses other options write (ints or "%08x" strings) -- none may be ours -- and `claims` =
    [(agent, game, lo, hi inclusive), ...] -- every word we write must lie in a claim of agent "T"
    and in nobody else's. [] = pass."""
    bad = []
    for game in ("js", "gr"):
        ours = {va for va, *_ in edits(True, True, game)}
        if used is not None:
            other = {int(x, 16) if isinstance(x, str) else x for x in used.get(game, ())}
            for va in sorted(ours & other):
                bad.append("%s %08X is written by another option" % (game, va))
        if claims is not None:
            for va in sorted(ours):
                mine = [c for c in claims if c[1] == game and c[2] <= va <= c[3] and c[0] == "T"]
                theirs = [c for c in claims if c[1] == game and c[2] <= va + 3 and va <= c[3] and c[0] != "T"]
                if not mine or theirs:
                    bad.append("%s %08X outside our claims or inside another's" % (game, va))
    for game, st, elf, delta in (("js", JS_STOCK, js_elf, 0x100), ("gr", GR_STOCK, gr_elf, 0x80)):
        if elf is not None:
            for va, w in st.items():
                off = va - 0x100000 + delta
                if int.from_bytes(elf[off:off + 4], "little") != w:
                    bad.append("%s stock %08X" % (game, va))
        for rf in (False, True):
            for cv in (False, True):
                try:
                    e = edits(rf, cv, game)
                except ValueError as ex:
                    bad.append("%s %s/%s: %s" % (game, rf, cv, ex))
                    continue
                if not rf and not cv and e:
                    bad.append("%s: off writes words" % game)
                if len({va for va, *_ in e}) != len(e):
                    bad.append("%s duplicate VA (%s/%s)" % (game, rf, cv))
                for va, value, stock, _ in e:
                    if va not in st or st[va] != stock:
                        bad.append("%s %08X has no / a wrong stock word" % (game, va))
        g = GAMES[game]
        for what, fn, isl in (("rf", rf_words, g["RF"]), ("uf", uf_words, g["UF"])):
            w, _ = fn(game)
            if not all(any(lo <= va < hi for lo, hi in isl) for va, _ in w):
                bad.append("%s %s leaves its islands" % (game, what))
    return bad

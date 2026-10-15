"""Shuffled missions: Jungle Storm (SLUS-20820) and Ghost Recon (SLUS-20613).

Every campaign and tactical mission places its enemies the same way every time:
the `<Units>` of a `.MIS` give each soldier a fixed spot, each fire team a
fixed plan (patrol path, zone to defend, cover to hold) and each soldier a fixed
kit. This reshuffles those three things every time a mission loads, so a replay
of the same mission plays differently:

  * posts      every enemy fire team stands at the start spot of another enemy
               team of the same size in its own platoon (all its soldiers:
               position, height and facing), drawn at random;
  * patrols    the fire teams' plans -- patrol routes, zones to defend or
               patrol, cover points, or no plan at all (stand guard) -- are
               dealt out again at random among the enemy teams;
  * loadouts   the enemies' kit files are dealt out again at random among the
               enemy soldiers.

How it hooks. IkeSimulationMgr::HandleLoadMission (GR 0x00387340, JS 0x00365090)
fetches the mission's parsed data -- MissionFile::GetSetupFileData -- just
before its loop that creates every company. That one call is replaced by a call
to the routine below, which makes the same call and then, before handing the
data back, deals the posts, plans and kits again inside it. Nothing else in the
game changes: the creation loop then builds the soldiers from the reshuffled
entries exactly as it always does (CreateCompany > CreatePlatoon > CreateTeam
> CreateHuman, which reads the actor entry's position +0x30, facing +0x40 and
kit +0x20, and BuildFireTeamAIPlan with the team entry's plan +0x1C/+0x20).

Why the shuffle cannot make online consoles disagree. Every soldier in the
game is created by the console that is master of the simulation, and only
there: CreateHuman builds one creation message per soldier -- name, model,
POSITION, facing -- and its inventory messages, and sends each with
IRSGameMessageMgr::MasterSendAll, which goes through MasterSend (GR 0x001280A0,
JS 0x0049AE50). MasterSend sends nothing unless IRSGameRulesMgr::IsMaster(1)
(rules vtable +0x48) is true. In the two online co-op RAM dumps of a joiner
(pcsx2-coop2, G04, 9C04BFE8 and FA828984) IsMaster is 0 for every system, the
joiner holds the 103 soldiers as SimHumans and has ZERO HumanAI objects, while
the host dumps of the same sessions show IsMaster 1 and 103 HumanAI objects. So
a joiner never builds an enemy from its own copy of the mission: it is sent
each one, already placed and already armed, by the host. AI plans only ever run
on the host. The routine therefore shuffles on the master only (it asks
IsMaster(1) itself and leaves a joiner's copy stock), with the game's own
random number generator (RSRandom::Int on the global RSRandom, the one the
quick-mission spawner already uses for its random enemy positions and kits;
seeded from the EE timer at boot): a new layout each time a mission loads, the
same layout on every console because every console is shown the host's.

What may move, and where. Only enemy companies (not Allied, name not starting
'_' -- the players' squads and the engine-made quick-mission forces). A fire
team takes part in posts and patrols only if every one of its soldiers has a
placed position, none is hidden until a script spawns him (reinforcements keep
their scripted entry points), none carries noweapon.kit (a captive or a man to
capture: Priego, Abreu), and its plan -- if it has one -- has no step tied to
something else: Animation, DestroyTarget, EnterVehicle, ExitVehicle, Follow,
ToggleAI or (Jungle Storm) UnloadVehicle; vehicle crews, escorts and scripted
set pieces stay as built. So do grreinforce's dormant alarm reserves (teams
"RF1"/"RF2", ids 0x7F00..0x7F0F, soldiers "RF", ids 0x7E00..0x7EFF, added to
the parsed mission at HandleLoadMap, before this runs): a reserve team, or any
team with a reserve soldier, neither gives nor takes a post or a plan, and no
reserve soldier's kit is dealt. Posts only change hands between teams of the same
size, member for member, so every soldier lands where a soldier of this mission
was placed by its designers -- on a floor the game has already found for that
spot (AdjustHeightsOverFloors runs on the entries when the map loads, before
this), inside the level, out of the geometry -- and the set of occupied spots is
the set the mission shipped with, so no enemy can start nearer the players'
insertion than the nearest one already did.

And only between teams of the same PLATOON. A mission script switches a whole
platoon's AI off and on (the responses PlatoonAIOff / PlatoonAIOn: PlatoonAI
+0x44, GR 0x00376450 / 0x00376460, JS 0x00353E00 / 0x00353E10), and
PlatoonAI::Update (GR 0x001A9AC0, JS 0x003FAD00) runs none of its teams while
it is off: no HumanAI::Update, so no awareness, no reaction, the soldiers stand
in their idle animation (smokers keep smoking). Jungle Storm J02 (G04_TRAIN)
starts with Platoon 1 (the station, smokers included) and Platoon 2 off and
switches them on from its station triggers. Dealt across platoons, a Platoon 1
team took Platoon 0's post at the insertion and stood there frozen 1-3 m from
the players (savestate EB2C54E6.01: its PlatoonAI +0x44 = 0, the three men
Bored with the player in their seen lists; running the real PlatoonAI::Update
with +0x44 = 1 put them in combat within 0.6 s). Kept inside its platoon, every
post holds a team of the platoon the designers put there, so it is asleep or
awake exactly when it would have been. The team list carries each team's
platoon (PLATS bytes after its slot) through the filter's compaction to the
posts routine. Plans and kits are still dealt across the whole enemy force
(neither freezes anyone: a team's plan runs whenever its platoon is on).

Kits move only between soldiers whose Idle animation is not 1-4 (smoking,
drinking: those kits carry the cigarette or the can) and never to or from
noweapon.kit, so every kit dealt is
one the mission already gives its enemies (with the other options' kit edits --
sidearms, launchers -- already in those files).

Quick missions (Firefight, Recon, Defend) need none of this: their enemies are
not in the mission file at all. The game type's "Spawn enemy force" script step
makes them in code (JS 0x00352F80/0x003507A0, GR CallResponse 0x00374380),
drawing each soldier's model and kit at random (opposing_force_jungle_N.atr /
opposing_force_N.kit in Jungle Storm) and his spot at random among the map's
36 "Map Point" zones (FindHumanStartLocationRandom, GR 0x0038CE50, no closer
than 3 m to another soldier) -- already a fresh layout every play, made on the
host the same way. They then hunt freely; there is no patrol to shuffle. If a
game type loads a mission's own companies as well, those are shuffled like a
campaign mission's.

A post is the entry's +0x30..+0x40: x, y, z (already set on the floor by
AdjustHeightsOverFloors), Lvl and Facing -- read by SetupFileData::
ProcessTeamMembers (GR 0x001E5840) from Pos, Lvl and Facing. Stance (+0x44),
Idle (+0x48), model and kit stay with the soldier.

Caves. Jungle Storm: 0x00198398..0x00198A17 -- the LZO library's start-up
self-test (_lzo_config_check and the assert reporter only it calls; its one
caller, __lzo_init2 at 0x00198A18, has no reference at all) -- one block.
Ghost Recon: 0x00411BA0 (entry), 0x0042B07C (filter + the RNG helper, scePad
twins), 0x00420CBC (posts), 0x0042BED0 (deal) -- four blocks (the platoon rule
grew the first three into the rest of the same dead functions: 0x00411D58,
0x0042B2BC, 0x00420E34; claimed by agent D). Every block has
no reference from live code in the loaded image (Jungle Storm's: nor from the
online/offline overlays), holds no word any other option writes, and is
claimed in the shared cave list.
"""

from __future__ import annotations

from .grasm import assemble

# ---------------------------------------------------------------------------
# addresses
# ---------------------------------------------------------------------------

GAMES = {
    "js": dict(
        HOOK=0x00365278, HOOK_STOCK=0x0C04C518,      # jal MissionFile::GetSetupFileData
        SYMS={
            "GET_SFD": 0x00131460,       # MissionFile::GetSetupFileData (lw v0,0xfc(a0))
            "RULES_GET": 0x00124BC0,     # IRSGameRulesMgr::Get
            "PLATOON_BY_ID": 0x001DE3B0, # SetupFileData::GetPlatoonFromId
            "TEAM_BY_ID": 0x001DE2F0,    # SetupFileData::GetTeamFromId
            "ACTOR_BY_ID": 0x001DE230,   # SetupFileData::GetActorFromId
            "PLAN_BY_ID": 0x0035C840,    # SetupFileData::GetPlanFromId
            "RAND_INT": 0x00112A30,      # RSRandom::Int(lo, hi, file, line)
            "RNG": 0x00613510,           # the global RSRandom
        },
        # (base, end, label of the first routine placed there)
        CAVES=[(0x00198398, 0x00198A18, "shuf_entry")],
    ),
    "gr": dict(
        HOOK=0x0038752C, HOOK_STOCK=0x0C0DA804,
        SYMS={
            "GET_SFD": 0x0036A010,
            "RULES_GET": 0x00387C60,
            "PLATOON_BY_ID": 0x0038EEE0,
            "TEAM_BY_ID": 0x0038EAA0,
            "ACTOR_BY_ID": 0x0038E620,
            "PLAN_BY_ID": 0x0037F220,
            "RAND_INT": 0x00113C60,
            "RNG": 0x005DF770,
        },
        CAVES=[(0x00411BA0, 0x00411D60, "shuf_entry"),
               (0x0042B07C, 0x0042B2D0, "shuf_filter"),
               (0x00420CBC, 0x00420E68, "shuf_posts"),
               (0x0042BED0, 0x0042BF8C, "shuf_deal")],
    ),
}

OPT_POSTS, OPT_PLANS, OPT_KITS = 1, 2, 4

#: plan steps that tie a team to something it cannot take with it (step type
#: = SetupFilePlanEntry::*Step::GetType, read from both executables' vtables):
#: 0 Animation, 10 DestroyTarget, 12 EnterVehicle, 13 ExitVehicle, 14 Follow,
#: 22 ToggleAI, 27 UnloadVehicle (Jungle Storm only). Any type >= 32 is refused too.
TIED_STEPS = (1 << 0) | (1 << 10) | (1 << 12) | (1 << 13) | (1 << 14) | (1 << 22) | (1 << 27)

#: grreinforce's dormant alarm reserves, added to the parsed mission at HandleLoadMap
#: (before this runs): teams "RF1"/"RF2" with ids 0x7F00.., soldiers "RF" with ids
#: 0x7E00..; they must stay where they were put and keep no plan, so a team with
#: such an id, or with such a soldier, takes no part in posts or patrols and its
#: soldiers' kits are not dealt. [lo, hi) ranges.
RF_TEAMS = (0x7F00, 0x7F10)
RF_ACTORS = (0x7E00, 0x7F00)

MAX_TEAMS = 64        # enemy teams looked at (Jungle Storm's most: 39)
MAX_KITS = 256        # soldiers whose kit is dealt (more are left as they are)
FRAME = 0x690         # entry frame: saves 0x90, teams 0x100, their platoons 0x100, kit soldiers 0x400
TEAMS_AT, PLATS_AT, KITS_AT = 0x90, 0x190, 0x290
PLATS = PLATS_AT - TEAMS_AT   # a team's platoon entry, at this offset from its slot in the team list


def _srlv(rd, rt, rs):
    R = {"t1": 9, "v0": 2}
    return ".word 0x%08X" % ((R[rs] << 21) | (R[rt] << 16) | (R[rd] << 11) | 0x06)


def _save(n, ra_at):
    s = "".join("    sq    s%d, 0x%x(sp)\n" % (i, 16 * i) for i in range(n))
    return s + "    sd    ra, 0x%x(sp)\n" % ra_at


def _restore(n, ra_at, frame):
    s = "    ld    ra, 0x%x(sp)\n" % ra_at
    s += "".join("    lq    s%d, 0x%x(sp)\n" % (i, 16 * i) for i in range(n))
    return s + "    jr    ra\n    addiu sp, sp, 0x%x\n" % frame


def _entry(flags):
    return f"""
shuf_entry:
    addiu sp, sp, -{FRAME:#x}
{_save(8, 0x80)}    jal   GET_SFD                   ; the call this replaces (a0 = the mission file)
    nop
    beqz  v0, e_out
    move  s0, v0                    ; SetupFileData
    jal   RULES_GET
    nop
    lw    t9, 0(v0)
    move  a0, v0
    lw    t9, 0x48(t9)              ; IsMaster(system)
    jalr  t9
    li    a1, 1                     ; system 1: the simulation
    andi  v0, v0, 0xff
    beqz  v0, e_out                 ; a joiner never builds an enemy: leave its copy alone
    move  s4, zero                  ; enemy teams found
    lw    s1, 0x18(s0)              ; companies.count
e_comp:
    addiu s1, s1, -1
    bltz  s1, e_found
    sll   t1, s1, 3
    sll   t2, s1, 5
    addu  t1, t1, t2                ; * 40
    lw    t0, 0x14(s0)              ; companies.data
    addu  s2, t0, t1
    lbu   t0, 0x24(s2)              ; Allied
    bnez  t0, e_comp
    lw    t0, 0x10(s2)              ; name (delay)
    beqz  t0, e_named
    nop
    lw    t0, 4(t0)
    beqz  t0, e_named
    nop
    lbu   t0, 0(t0)
    li    t1, 0x5f                  ; '_': a players' squad or an engine-made force
    beq   t0, t1, e_comp
    nop
e_named:
    lw    s3, 0x18(s2)              ; platoon ids.count
e_plat:
    addiu s3, s3, -1
    bltz  s3, e_comp
    lw    t0, 0x14(s2)              ; (delay) platoon ids.data
    sll   t1, s3, 2
    addu  t0, t0, t1
    lw    a1, 0(t0)
    jal   PLATOON_BY_ID
    move  a0, s0
    beqz  v0, e_plat
    move  s6, v0
    lw    s5, 0x18(s6)              ; team ids.count
e_team:
    addiu s5, s5, -1
    bltz  s5, e_plat
    lw    t0, 0x14(s6)              ; (delay) team ids.data
    sll   t1, s5, 2
    addu  t0, t0, t1
    lw    a1, 0(t0)
    jal   TEAM_BY_ID
    move  a0, s0
    beqz  v0, e_team
    sltiu t0, s4, {MAX_TEAMS}
    beqz  t0, e_team
    sll   t1, s4, 2
    addu  t1, t1, sp
    sw    v0, {TEAMS_AT:#x}(t1)
    sw    s6, {PLATS_AT:#x}(t1)        ; and its platoon: posts change hands only inside one
    b     e_team
    addiu s4, s4, 1
e_found:
    move  a0, s0
    addiu a1, sp, {TEAMS_AT:#x}
    move  a2, s4
    jal   shuf_filter               ; v0 = teams that may move (front of the list), v1 = kit soldiers
    addiu a3, sp, {KITS_AT:#x}
    move  s4, v0
    move  s5, v1
    li    s7, {flags}
    andi  t0, s7, {OPT_POSTS}
    beqz  t0, e_noposts
    move  a0, s0
    addiu a1, sp, {TEAMS_AT:#x}
    jal   shuf_posts
    move  a2, s4
e_noposts:
    andi  t0, s7, {OPT_PLANS}
    beqz  t0, e_noplans
    addiu a0, sp, {TEAMS_AT:#x}
    move  a1, s4
    jal   shuf_deal
    move  a2, zero
e_noplans:
    andi  t0, s7, {OPT_KITS}
    beqz  t0, e_out
    addiu a0, sp, {KITS_AT:#x}
    move  a1, s5
    jal   shuf_deal
    li    a2, 1
e_out:
    move  v0, s0
{_restore(8, 0x80, FRAME)}"""


def _filter():
    hi, lo = TIED_STEPS >> 16, TIED_STEPS & 0xFFFF
    return f"""
; shuf_filter(sfd, teams, n, kitlist) -> v0 = teams that may move, compacted to
; the front of `teams` (each with its platoon, {PLATS:#x} bytes on); v1 = soldiers
; whose kit may be dealt, written to kitlist
shuf_filter:
    addiu sp, sp, -0xb0
{_save(8, 0x80)}    move  s0, a0
    move  s1, a1
    move  s2, a2
    move  s3, a3
    move  s4, zero                  ; i
    move  s5, zero                  ; teams kept
    move  s6, zero                  ; kit soldiers
f_team:
    beq   s4, s2, f_done
    sll   t0, s4, 2
    addu  t0, s1, t0
    lw    s7, 0(t0)                 ; the team
    lw    t0, 4(s7)                 ; its id
    addiu t0, t0, -{RF_TEAMS[0]:#x}
    sltiu t0, t0, {RF_TEAMS[1] - RF_TEAMS[0]:#x}
    bnez  t0, f_next                ; a dormant reserve team: neither gives nor takes anything
    lw    t0, 0x18(s7)              ; (delay) members
    addiu t0, t0, -1
    sltiu t0, t0, 8                 ; 1..8
    xori  t0, t0, 1
    sw    t0, 0x90(sp)              ; refused?
    lbu   t0, 0x1c(s7)              ; has a plan
    beqz  t0, f_members
    lw    a1, 0x20(s7)              ; (delay) its id
    jal   PLAN_BY_ID
    move  a0, s0
    beqz  v0, f_tied
    nop
    lw    t0, 0x18(v0)              ; steps: RSList at plan+0x14, sentinel at +4
    sw    t0, 0x94(sp)
    lw    t1, 4(t0)                 ; first node
f_step:
    lw    t0, 0x94(sp)
    beq   t1, t0, f_members
    sw    t1, 0x98(sp)
    lw    a0, 0(t1)                 ; the step
    lw    t9, 4(a0)                 ; its vtable
    lw    t9, 0xc(t9)               ; GetType
    jalr  t9
    nop
    sltiu t0, v0, 32
    beqz  t0, f_tied
    lui   t1, {hi:#x}
    ori   t1, t1, {lo:#x}
    {_srlv("t1", "t1", "v0")}
    andi  t1, t1, 1
    bnez  t1, f_tied
    lw    t1, 0x98(sp)
    b     f_step
    lw    t1, 4(t1)                 ; next node
f_tied:
    li    t0, 1
    sw    t0, 0x90(sp)
f_members:
    sw    zero, 0x9c(sp)            ; m
f_mem:
    lw    t0, 0x9c(sp)
    lw    t1, 0x18(s7)
    slt   t2, t0, t1
    beqz  t2, f_judge
    lw    t1, 0x14(s7)              ; (delay)
    sll   t2, t0, 2
    addu  t1, t1, t2
    addiu t0, t0, 1
    sw    t0, 0x9c(sp)
    lw    a1, 0(t1)
    jal   ACTOR_BY_ID
    move  a0, s0
    beqz  v0, f_refuse
    nop
    lw    t0, 4(v0)                 ; his id
    addiu t0, t0, -{RF_ACTORS[0]:#x}
    sltiu t0, t0, {RF_ACTORS[1] - RF_ACTORS[0]:#x}
    bnez  t0, f_refuse              ; a reserve soldier: stays as built, and so does his team
    lbu   t0, 0x2c(v0)              ; (delay) placed
    lbu   t1, 0x50(v0)              ; hidden until a script spawns him
    sltiu t0, t0, 1
    or    t0, t0, t1
    beqz  t0, f_kit
    li    t1, 1
    sw    t1, 0x90(sp)
f_kit:
    lw    t0, 0x24(v0)              ; kit name
    beqz  t0, f_mem
    nop
    lw    t0, 4(t0)
    beqz  t0, f_mem
    nop
    lbu   t1, 0(t0)                 ; "now": noweapon.kit, a captive or a man to capture
    li    t2, 0x6e
    bne   t1, t2, f_armed
    lbu   t1, 1(t0)
    li    t2, 0x6f
    bne   t1, t2, f_armed
    lbu   t1, 2(t0)
    li    t2, 0x77
    bne   t1, t2, f_armed
    nop
f_refuse:
    li    t1, 1
    b     f_mem
    sw    t1, 0x90(sp)              ; his whole team stays as built
f_armed:
    lw    t0, 0x48(v0)              ; Idle 1..4: the kit carries his cigarette or can
    addiu t0, t0, -1
    sltiu t0, t0, 4
    bnez  t0, f_mem
    sltiu t0, s6, {MAX_KITS}
    beqz  t0, f_mem
    sll   t1, s6, 2
    addu  t1, s3, t1
    sw    v0, 0(t1)
    b     f_mem
    addiu s6, s6, 1
f_judge:
    lw    t0, 0x90(sp)
    bnez  t0, f_next
    sll   t1, s5, 2
    addu  t1, s1, t1
    sw    s7, 0(t1)                 ; kept teams move to the front (kept <= i)
    sll   t0, s4, 2
    addu  t0, s1, t0
    lw    t0, {PLATS:#x}(t0)
    sw    t0, {PLATS:#x}(t1)        ; its platoon goes with it
    addiu s5, s5, 1
f_next:
    b     f_team
    addiu s4, s4, 1
f_done:
    move  v0, s5
    move  v1, s6
{_restore(8, 0x80, 0xb0)}
; shuf_rand(n) -> 0..n-1 from the game's own RSRandom
shuf_rand:
    addiu a2, a0, -1
    lui   a0, %hi(RNG)
    addiu a0, a0, %lo(RNG)
    move  a1, zero
    move  a3, zero
    j     RAND_INT
    move  t0, zero
"""


def _posts():
    return f"""
; shuf_posts(sfd, teams, n): Fisher-Yates within each team size of each platoon;
; a swap trades every member's post (x y z, Lvl, facing) with the same member of
; the other team. Platoon: the mission script switches a whole platoon's AI on and
; off (PlatoonAIOn/Off); a team moved into another platoon's ground would stand
; there with its own platoon's state -- frozen, if that platoon is still off.
shuf_posts:
    addiu sp, sp, -0xa0
{_save(8, 0x80)}    move  s0, a0
    move  s1, a1
    addiu s2, a2, -1                ; i
p_outer:
    blez  s2, p_done
    sll   t0, s2, 2
    addu  t0, s1, t0
    lw    s6, 0(t0)                 ; team i
    lw    t3, {PLATS:#x}(t0)        ; its platoon
    lw    s3, 0x18(s6)              ; its size
    sw    t3, 0x98(sp)
    move  s4, zero                  ; how many of 0..i have both
    move  s5, zero                  ; k
p_cnt:
    sll   t0, s5, 2
    addu  t0, s1, t0
    lw    t2, {PLATS:#x}(t0)
    lw    t0, 0(t0)
    lw    t0, 0x18(t0)
    bne   t0, s3, p_cnt2
    slt   t1, s5, s2                ; (delay) k < i
    bne   t2, t3, p_cnt2
    nop
    addiu s4, s4, 1
p_cnt2:
    bnez  t1, p_cnt
    addiu s5, s5, 1
    jal   shuf_rand
    move  a0, s4
    move  s4, v0                    ; r: take the r-th team of that size and platoon
    move  s5, zero
    lw    t3, 0x98(sp)
p_find:
    sll   t0, s5, 2
    addu  t0, s1, t0
    lw    s7, 0(t0)
    lw    t2, {PLATS:#x}(t0)
    lw    t1, 0x18(s7)
    bne   t1, s3, p_find2
    nop
    bne   t2, t3, p_find2
    nop
    beqz  s4, p_found
    addiu s4, s4, -1
p_find2:
    b     p_find
    addiu s5, s5, 1
p_found:
    beq   s7, s6, p_next            ; drew itself
    sw    zero, 0x90(sp)            ; m
p_swap:
    lw    t0, 0x90(sp)
    slt   t1, t0, s3
    beqz  t1, p_next
    sll   t0, t0, 2
    lw    t1, 0x14(s6)
    addu  t1, t1, t0
    lw    a1, 0(t1)
    jal   ACTOR_BY_ID
    move  a0, s0
    sw    v0, 0x94(sp)
    lw    t0, 0x90(sp)
    sll   t0, t0, 2
    lw    t1, 0x14(s7)
    addu  t1, t1, t0
    lw    a1, 0(t1)
    jal   ACTOR_BY_ID
    move  a0, s0
    lw    t2, 0x94(sp)
    beqz  v0, p_m
    nop
    beqz  t2, p_m
    li    t3, 5                     ; +0x30 x, y, z, +0x3C Lvl, +0x40 facing
    addiu t4, t2, 0x30
    addiu t5, v0, 0x30
p_w:
    lw    t0, 0(t4)
    lw    t1, 0(t5)
    sw    t1, 0(t4)
    sw    t0, 0(t5)
    addiu t3, t3, -1
    addiu t4, t4, 4
    bgtz  t3, p_w
    addiu t5, t5, 4
p_m:
    lw    t0, 0x90(sp)
    addiu t0, t0, 1
    b     p_swap
    sw    t0, 0x90(sp)
p_next:
    b     p_outer
    addiu s2, s2, -1
p_done:
{_restore(8, 0x80, 0xa0)}
; shuf_deal(list, n, what): Fisher-Yates over a list of entries.
;   what 0: teams -- trade the has-plan byte (+0x1C) and the plan id (+0x20)
;   what 1: soldiers -- trade the kit's RSFilename string (+0x24, +0x28)
shuf_deal:
    addiu sp, sp, -0x40
{_save(3, 0x30)}    move  s0, a0
    addiu s1, a1, -1
    move  s2, a2
d_loop:
    blez  s1, d_done
    nop
    jal   shuf_rand
    addiu a0, s1, 1
    sll   t0, s1, 2
    addu  t0, s0, t0
    lw    t0, 0(t0)
    sll   t1, v0, 2
    addu  t1, s0, t1
    lw    t1, 0(t1)
    beq   t0, t1, d_next
    nop
    bnez  s2, d_kit
    nop
    lbu   t2, 0x1c(t0)
    lbu   t3, 0x1c(t1)
    sb    t3, 0x1c(t0)
    sb    t2, 0x1c(t1)
    lw    t2, 0x20(t0)
    lw    t3, 0x20(t1)
    sw    t3, 0x20(t0)
    b     d_next
    sw    t2, 0x20(t1)
d_kit:
    lw    t2, 0x24(t0)
    lw    t3, 0x24(t1)
    sw    t3, 0x24(t0)
    sw    t2, 0x24(t1)
    lw    t2, 0x28(t0)
    lw    t3, 0x28(t1)
    sw    t3, 0x28(t0)
    sw    t2, 0x28(t1)
d_next:
    b     d_loop
    addiu s1, s1, -1
d_done:
{_restore(3, 0x30, 0x40)}"""


def _parts(game, flags):
    """[(base, end, source)] in cave order."""
    caves = GAMES[game]["CAVES"]
    if len(caves) == 1:
        base, end, _ = caves[0]
        return [(base, end, _entry(flags) + _filter() + _posts())]
    posts = _posts()
    cut = posts.index("; shuf_deal(")
    src = {"shuf_entry": _entry(flags), "shuf_filter": _filter(),
           "shuf_posts": posts[:cut], "shuf_deal": posts[cut:]}
    return [(base, end, src[first]) for base, end, first in caves]


def assemble_game(game, flags):
    """[(base, words)] and the labels of every routine, cross-cave calls resolved."""
    syms = dict(GAMES[game]["SYMS"])
    parts = _parts(game, flags)
    # first pass: every routine label at some address in the same 256 MB segment,
    # so a call into another cave assembles; the second pass uses the real ones
    labels = {k: parts[0][0] for k in ("shuf_entry", "shuf_filter", "shuf_rand",
                                       "shuf_posts", "shuf_deal")}
    for _ in range(2):          # two passes so each part sees the others' labels
        out = []
        for base, end, src in parts:
            words, lab = assemble(src, base, dict(syms, **labels))
            if base + 4 * len(words) > end:
                raise ValueError("%s shuffle routine at %08X outgrows its cave (%d words, room %d)"
                                 % (game, base, len(words), (end - base) // 4))
            out.append((base, words))
            labels.update(lab)
    return out, labels


def _jal(target):
    return 0x0C000000 | ((target >> 2) & 0x3FFFFFF)


def edits(game: str, posts: bool = False, plans: bool = False, kits: bool = False):
    """(va, value, stock, note). All off: nothing."""
    flags = (OPT_POSTS if posts else 0) | (OPT_PLANS if plans else 0) | (OPT_KITS if kits else 0)
    if not flags:
        return []
    g = GAMES[game]
    st = GR_STOCK if game == "gr" else JS_STOCK
    blocks, labels = assemble_game(game, flags)
    out = []
    for base, words in blocks:
        out += [(base + 4 * i, w, st[base + 4 * i], "shuffle: deal enemy posts, plans and kits at mission load")
                for i, w in enumerate(words)]
    out.append((g["HOOK"], _jal(labels["shuf_entry"]), g["HOOK_STOCK"],
                "shuffle: HandleLoadMission fetches the mission data through the shuffle"))
    return out


def js_edits(v: dict):
    return edits("js", bool(v.get("js_shuffle_positions")), bool(v.get("js_shuffle_patrols")),
                 bool(v.get("js_shuffle_loadouts")))


def gr_edits(v: dict):
    return edits("gr", bool(v.get("gr_shuffle_positions")), bool(v.get("gr_shuffle_patrols")),
                 bool(v.get("gr_shuffle_loadouts")))


def cards(prefix: str = "js_", group: str = "Enemies") -> list:
    from .model import BOOL, Setting
    gr = prefix == "gr_"
    co = ("Online co-op: the host deals the layout and every console is sent the host's soldiers "
          "already placed and armed, so all players see the same mission.")
    return [
        Setting(prefix + "shuffle_positions", "Shuffle enemy start positions", BOOL, False, group,
                confidence="experimental",
                help="Each time a mission loads, every enemy fire team starts at the post of another "
                     "enemy team of the same size in its own platoon, picked at random -- the lone "
                     "sentry on the tower may now be the one by the gate, the pair at the hut "
                     "somewhere else in that group's ground. "
                     "Every spot is one the mission already uses, so nobody starts in a wall, off "
                     "the map or closer to your insertion than the mission's own nearest enemy. "
                     "Staying inside the platoon keeps every post with the group the mission wakes "
                     "up there: a mission can keep a platoon switched off until its own script "
                     "wakes it, and a switched-off team moved next to your start would just stand "
                     "there (smoking, in Jungle Storm's Railroad Junction). "
                     "Teams with a patrol or zone still walk to it from their new start. Soldiers "
                     "a script brings in later, vehicle crews, captives and men you must capture "
                     "stay where they are. Campaign and tactical missions; Firefight, Recon and "
                     "Defend already place their enemies at random every time. " + co,
                caution="Never played. A mission script that waits for a team to reach its spot "
                        "may fire later or not at all. Missions made of many one-team platoons "
                        "change less. Applies on the next mission load."),
        Setting(prefix + "shuffle_patrols", "Shuffle enemy patrol routes", BOOL, False, group,
                confidence="experimental",
                help="Each time a mission loads, the enemy fire teams' orders -- patrol routes, "
                     "zones to patrol or defend, cover to hold, or simply standing guard -- are "
                     "dealt out again at random, so a different team (bigger, smaller, armed "
                     "differently) walks each route and guards each post. Routes are the "
                     "mission's own. Vehicle crews, escorts, reinforcements and captives keep "
                     "their orders. Together with the start positions this changes where the "
                     "fights happen. " + co,
                caution="Never played. Teams may cross the map at the start to reach their new "
                        "route. A script waiting on a particular team's route may behave "
                        "differently. Applies on the next mission load."),
        Setting(prefix + "shuffle_loadouts", "Shuffle enemy loadouts", BOOL, False, group,
                confidence="experimental",
                help="Each time a mission loads, the enemies' kits are dealt out again among "
                     "them at random, so the sniper rifle or %s may be with someone else. "
                     "Only kits that mission already gives its enemies are used (with any "
                     "sidearm or launcher option already in them); smokers and drinkers keep "
                     "their cigarette or can, and unarmed captives stay unarmed. " % (
                         "machine gun" if gr else "light machine gun") + co,
                caution="Never played. Applies on the next mission load."),
    ]


# ---------------------------------------------------------------------------
# stock words of every cave word and the hook (read from the retail ELFs)
# ---------------------------------------------------------------------------

_JS_CAVE_STOCK_HEX = (   # 00198398..001989C3
    "27BDFFF0 FFBF0000 0C05A8B0 00000000 DFBF0000 03E00008 27BD0010 00000000 "
    "27BDFFF0 FFBF0000 0C05A8D6 00000000 DFBF0000 03E00008 27BD0010 00000000 "
    "27BDFFF0 FFBF0000 0C05A902 00000000 DFBF0000 03E00008 27BD0010 00000000 "
    "27BDFFF0 FFBF0000 0C05A944 00000000 DFBF0000 03E00008 27BD0010 00000000 "
    "27BDFFF0 3C020057 8C438E00 0080382D FFBF0000 3C020058 00A0302D 8C64000C "
    "0C05A08E 24452FD8 DFBF0000 0000102D 03E00008 27BD0010 03E00008 24020001 "
    "03E00008 24020001 27BDFF10 FFB700D0 27A2004F FFB20080 27B70030 FFB10070 "
    "27B20050 FFB00060 24110001 FFBF00E0 2410001F FFB600C0 FFB500B0 FFB400A0 "
    "FFB30090 00000000 A0500000 2610FFFF 00000000 00000000 00000000 0601FFFA "
    "2442FFFF 03A0202D 0C066046 24050008 03A2A021 029D8023 06010007 0280A82D "
    "3C040058 24050402 0C066106 24843000 10000002 02228824 32310001 2A020008 "
    "54400006 32310001 3C040058 24050403 0C066106 24843008 02228824 0240202D "
    "240500FF 0C05A944 24060008 97A30050 3402FFFF 10620006 3C040058 24050406 "
    "0C066106 24843028 10000002 02228824 32310001 3C02FFFF 8FA30050 3442FFFF "
    "10620006 3C040058 24050407 0C066106 24843040 10000002 02228824 32310001 "
    "DFA30050 2402FFFF 10620006 3C040058 24050408 0C066106 24843058 10000002 "
    "02228824 32310001 3C02FFFF 8FA30050 3442FFFF 10620006 3C040058 24050409 "
    "0C066106 24843070 10000002 02228824 32310001 24020001 56220011 FFA00050 "
    "3C160058 0280982D 02A0902D 24100007 12530005 26C43090 0C066106 2405040E "
    "10000002 02228824 32310001 26730004 2610FFFF 0601FFF6 26520004 FFA00050 "
    "8FA20050 10400006 3C040058 24050412 0C066106 248430E8 10000002 02228824 "
    "32310001 8FA20050 10400006 3C040058 24050413 0C066106 24843100 10000002 "
    "02228824 32310001 32310001 24020001 56220075 0220102D 26A40004 24100009 "
    "26A20024 00000000 AC540000 2610FFFF 00000000 00000000 00000000 0601FFFA "
    "2442FFFC 0000282D 0C05A944 24060020 8EA30000 10740006 3C040058 2405041A "
    "0C066106 24843118 10000002 02228824 32310001 3C130058 26B20004 24100007 "
    "8E420000 10400005 26643130 0C066106 2405041C 10000002 02228824 32310001 "
    "2610FFFF 0601FFF6 26520004 8EA20024 10540006 3C040058 2405041D 0C066106 "
    "24843140 10000002 02228824 32310001 24020001 16220044 0220102D 27A40031 "
    "24050004 0C066046 0080982D 24500001 02F09021 32420003 10400005 2405042A "
    "3C040058 0C066106 24843158 30510001 56000006 32310001 3C040058 24050430 "
    "0C066106 24843178 02228824 0253102B 10400006 3C040058 24050432 0C066106 "
    "24843180 10000002 02228824 32310001 2E020005 54400006 32310001 3C040058 "
    "24050434 0C066106 24843190 02228824 27A20035 0242102B 54400006 32310001 "
    "3C040058 24050436 0C066106 24843198 02228824 24020001 16220013 0220102D "
    "02F01021 03B01821 8C440000 14800006 8C700034 3C040058 2405043D 0C066106 "
    "248431A8 30510001 56000006 32310001 3C040058 2405043E 0C066106 248431B0 "
    "02228824 0220102D DFBF00E0 DFB700D0 DFB600C0 DFB500B0 DFB400A0 DFB30090 "
    "DFB20080 DFB10070 DFB00060 03E00008 27BD00F0 00000000 27BDFFB0 FFB00020 "
    "FFBF0040 0C066114 FFB10030 0C066116 30500001 02028024 24020001 12020003 "
    "24110001 1000003A 2402FFFF 2403001F 27A2001F 00000000 A0430000 2463FFFF "
    "00000000 00000000 00000000 0461FFFA 2442FFFF 0220802D 24020001 1602002A "
    "3A030001 0C066268 00000000 10400005 240504B7 3C040058 0C066106 248431B8 "
    "30500001 16110020 3A030001 3C020057 0000182D 8C4268D0 1040000A 3C040062 "
    "0040302D 2485DFF0 2462FFFD ACA20000 24630001 0066102B 00000000 1440FFFA "
    "24A50004 0C066276 2484DFF0 10400006 3C040058 240504C2 0C066106 248431D0 "
    "10000002 02028024 32100001 24020001 16020005 3A030001 0C066118 00000000 "
    "30500001 3A030001 2402FFFF 0003100A DFBF0040 DFB10030 DFB00020 03E00008 "
    "27BD0050 00000000 27BDFFF0 3C020058 244631E8 68C30007 6CC30000 8CC40008 "
    "B3A30007 B7A30000 AFA40008 "
)
_GR_ENTRY_STOCK_HEX = (   # 00411BA0..00411D57
    "2403004C 0000000C 03E00008 00000000 2403004D 0000000C 03E00008 00000000 "
    "2403004E 0000000C 03E00008 00000000 2403004F 0000000C 03E00008 00000000 "
    "24030050 0000000C 03E00008 00000000 24030051 0000000C 03E00008 00000000 "
    "24030052 0000000C 03E00008 00000000 2403FFAD 0000000C 03E00008 00000000 "
    "24030054 0000000C 03E00008 00000000 2403FFAB 0000000C 03E00008 00000000 "
    "24030056 0000000C 03E00008 00000000 24030057 0000000C 03E00008 00000000 "
    "2403FFA8 0000000C 03E00008 00000000 24030059 0000000C 03E00008 00000000 "
    "2403FFA6 0000000C 03E00008 00000000 2403005B 0000000C 03E00008 00000000 "
    "2403005C 0000000C 03E00008 00000000 2403FFA4 0000000C 03E00008 00000000 "
    "2403005D 0000000C 03E00008 00000000 2403FFA3 0000000C 03E00008 00000000 "
    "2403005E 0000000C 03E00008 00000000 2403FFA2 0000000C 03E00008 00000000 "
    "2403005F 0000000C 03E00008 00000000 2403FFA1 0000000C 03E00008 00000000 "
    "24030060 0000000C 03E00008 00000000 24030061 0000000C 03E00008 00000000 "
    "24030062 0000000C 03E00008 00000000 24030063 0000000C "
)
_GR_FILTER_STOCK_HEX = (   # 0042B07C..0042B2BB
    "00000000 27BDFFD0 3C02005F FFB00010 24060014 24502580 FFBF0020 AE040004 "
    "3C03005F AC462580 24050001 24642340 AFA00000 0000302D 0200382D 24080080 "
    "0200482D 240A0080 0C10531C 0000582D 04430002 8E020008 0000102D DFBF0020 "
    "DFB00010 03E00008 27BD0030 AC850000 AC800008 03E00008 AC850004 8C820004 "
    "AC800008 03E00008 AC820000 8C850000 30A2000C 10400008 8C860008 ACA00000 "
    "24A50004 30A2000C 00000000 00000000 1440FFFA 00000000 10C00006 00A61023 "
    "8CC30000 00021103 2442FFFF 00621821 ACC30000 AC800008 00A0102D 03E00008 "
    "AC850000 27BDFFB0 FFB10010 0080882D FFB30030 FFB20020 00C0982D FFB00000 "
    "00A0902D FFBF0040 0C10AC42 00E0802D 8E230000 3C041000 02048025 AE220008 "
    "AC700000 24630004 DFBF0040 2462000C AC720004 AE220000 AC730008 DFB30030 "
    "DFB20020 DFB10010 DFB00000 AC600000 03E00008 27BD0050 00000000 27BDFFB0 "
    "FFB10010 0080882D FFB30030 FFB20020 00C0982D FFB00000 00A0902D FFBF0040 "
    "0C10AC42 00E0802D 8E230000 3C047000 02048025 AE220008 AC700000 24630004 "
    "DFBF0040 2462000C AC720004 AE220000 AC730008 DFB30030 DFB20020 DFB10010 "
    "DFB00000 AC600000 03E00008 27BD0050 00000000 0080482D 24050002 8D28000C "
    "8D2A0000 DD070000 01481023 000210C3 00071EBE 2446FFFE 30630003 00062042 "
    "38620001 1065000B 0082300B 0007173E 24040010 0082100A 00C21821 50400001 "
    "000001CD 2463FFFF 0062001B 00001812 0060302D 0006103C 0140282D 0002103E "
)
_GR_POSTS_STOCK_HEX = (   # 00420CBC..00420E33
    "00000000 3C06005F 3C020057 24C62100 2442F010 AC860000 ACA20000 3C040057 "
    "3C02005F 8C83F014 24420B40 03E00008 ACC3003C 27BDFFC0 FFB10020 FFB00010 "
    "3C110057 0080802D FFBF0030 0C1046CC 8E24F014 04410003 3C02005F 1000001D "
    "2402FF38 24440B40 8C830024 14600005 3C07005F 0C1046C0 8E24F014 10000015 "
    "2402FF9C 3C09005F 24E70BC0 25292100 ACF00014 24050014 AFA00000 24060001 "
    "24080030 240A0004 0C10531C 0000582D 0040802D 16000004 3C030057 24020014 "
    "10000003 AC62F010 0C1046C0 8E24F014 0200102D DFBF0030 DFB10020 DFB00010 "
    "03E00008 27BD0040 00000000 27BDFFB0 FFB10020 FFB00010 3C110057 0080802D "
    "FFBF0040 8E24F014 0C1046CC FFB20030 04410003 3C02005F 1000001E 2402FF38 "
    "24440B40 8C830024 14600005 3C07005F 0C1046C0 8E24F014 10000016 2402FF9C "
    "3C12005F 24E70BC0 24050015 ACF00004 0000302D AFA00000 24080030 26492100 "
    "240A0004 0C10531C 0000582D 0040802D 12000005 00000000 "
)
_GR_DEAL_STOCK_HEX = (   # 0042BED0..0042BF8B
    "4BE0012C 3C024580 00021438 34424580 00021438 D8870000 48A23000 48C08000 "
    "4BA4396C 4B87316C 4A0002FF 4A0002FF 4A0002FF 4A0002FF 4A0002FF 48428000 "
    "03E00008 304200C0 4BE0012C 3C024580 00021438 34424580 00021438 D8860000 "
    "D8A80000 D8C90000 48A23800 48C08000 4BA4316C 4B86396C 4BA4416C 4B88396C "
    "4BA4496C 4B89396C 4A0002FF 4A0002FF 4A0002FF 4A0002FF 4A0002FF 48428000 "
    "03E00008 304200C0 D8E80000 D8C40000 D8C50010 D8C60020 D8C70030 "
)

# the platoon rule's room: the rest of each block, past the words above (agent D's claims)
_JS_CAVE2_STOCK_HEX = (   # 001989C4..00198A17 (the LZO self-test block's tail; __lzo_init2 starts at 00198A18)
    "8FA20000 2C420001 03E00008 27BD0010 00000000 8C830000 2402FFFD 14620009 "
    "0000282D 8C830004 2402FFFE 54620006 24050001 8C830008 2402FFFF 10620002 "
    "00000000 24050001 03E00008 00A0102D 00000000 "
)
_GR_ENTRY2_STOCK_HEX = "03E00008 00000000 "                                       # 00411D58..00411D5F
_GR_FILTER2_STOCK_HEX = "AD20000C 00E2102D 30A3000C 10600008 FD020000 "           # 0042B2BC..0042B2CF
_GR_POSTS2_STOCK_HEX = (   # 00420E34..00420E67
    "0C1046C0 8E24F014 10000004 0200102D 0C1046C0 8E24F014 8E422100 DFBF0040 "
    "DFB20030 DFB10020 DFB00010 03E00008 27BD0050 "
)


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


JS_STOCK = _stock_words(0x00198398, _JS_CAVE_STOCK_HEX)
JS_STOCK.update(_stock_words(0x001989C4, _JS_CAVE2_STOCK_HEX))
JS_STOCK[GAMES["js"]["HOOK"]] = GAMES["js"]["HOOK_STOCK"]
GR_STOCK = {}
for _base, _hex in ((0x00411BA0, _GR_ENTRY_STOCK_HEX), (0x0042B07C, _GR_FILTER_STOCK_HEX),
                    (0x00420CBC, _GR_POSTS_STOCK_HEX), (0x0042BED0, _GR_DEAL_STOCK_HEX),
                    (0x00411D58, _GR_ENTRY2_STOCK_HEX), (0x0042B2BC, _GR_FILTER2_STOCK_HEX),
                    (0x00420E34, _GR_POSTS2_STOCK_HEX)):
    GR_STOCK.update(_stock_words(_base, _hex))
GR_STOCK[GAMES["gr"]["HOOK"]] = GAMES["gr"]["HOOK_STOCK"]


def selftest(gr_elf: bytes = None, js_elf: bytes = None, ai2: str = None):
    """Stock words against the executables, no address twice, every written VA has a
    stock word, all options off = nothing, every routine inside its cave; with `ai2`
    (the shared cave folder) also: every word inside X's claims and no word another
    option writes. [] = pass."""
    import json
    import os
    bad = []
    for game in ("gr", "js"):
        blocks, labels = assemble_game(game, 7)
        caves = GAMES[game]["CAVES"]
        for (base, words), (cbase, cend, first) in zip(blocks, caves):
            if base != cbase or base + 4 * len(words) > cend or labels.get(first) != cbase:
                bad.append("%s routine %s outside its cave" % (game, first))
    if ai2:
        claims = {"js": [], "gr": []}
        for ln in open(os.path.join(ai2, "caves_claimed.txt")):
            p = ln.split()
            if len(p) >= 3 and "-" in p[2] and p[1] in claims:
                a, b = (int(x, 16) for x in p[2].split("-"))
                claims[p[1]].append((p[0], a, b))
        for game in ("gr", "js"):
            used = set(int(x, 16) for x in json.load(open(os.path.join(ai2, game + "_used.json"))))
            for va, *_ in edits(game, True, True, True):
                if va in used:
                    bad.append("%s %08X written by another option" % (game, va))
                own = [c for c in claims[game] if c[1] <= va <= c[2]]
                if not own or any(c[0] not in ("X", "D") for c in own):      # D: the platoon rule's words
                    bad.append("%s %08X outside X's/D's claims (or inside another's)" % (game, va))
    for game, st, elf, d in (("gr", GR_STOCK, gr_elf, 0x80), ("js", JS_STOCK, js_elf, 0x100)):
        if elf is not None:
            for va, w in st.items():
                off = va - 0x100000 + d
                if int.from_bytes(elf[off:off + 4], "little") != w:
                    bad.append("%s %08X stock" % (game, va))
        if edits(game):
            bad.append("%s: all options off still writes" % game)
        for f in range(1, 8):
            e = edits(game, bool(f & 1), bool(f & 2), bool(f & 4))
            if len({va for va, *_ in e}) != len(e):
                bad.append("%s duplicate VA (%d)" % (game, f))
            if any(va not in st for va, *_ in e):
                bad.append("%s VA without a stock word (%d)" % (game, f))
            if any(s != st[va] for va, _v, s, _n in e):
                bad.append("%s stock column disagrees (%d)" % (game, f))
    return bad

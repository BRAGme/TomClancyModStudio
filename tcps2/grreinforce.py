"""Alarm reinforcements: Jungle Storm (SLUS-20820) and Ghost Recon (SLUS-20613).

What the player gets
--------------------

Being seen costs you. Every mission whose enemies come from the mission file gets
one (or two) extra enemy fire teams of four, standing beside the hostile team
farthest from your insertion zone -- the enemy's reserve. They wait there and
fight only what comes to them. The first time any enemy fire team adds one of
your squad to its list of enemies -- a sentry sees you, or a team comes under
your fire, or loses a man to it and learns where the shot came from -- the
alarm is up: the reserve runs to where you were seen. Every later sighting
(at most one every 15 s) sends it on to the newest spot. Being quiet still
works: kill a lone sentry and nobody is left to raise it.

What "the alarm" is
-------------------

Neither game has a general alarm. Jungle Storm's sirens (gralarm) are two
missions' scripts playing a sound; Ghost Recon has nothing. So the alarm is the
AI's own moment of detection, the same in both games and on every mission:
FireTeamAI::AddEnemy returning a new EnemyStruct (the team had not counted him
yet) about a soldier whose own fire team is a players' team (FireTeamAI +0xD9
"script controlled" = 0: Alpha, Bravo, Charlie -- you, your AI squad mates
and, online, the other player). Only an enemy team ever counts one of those as
its enemy. An allied NPC (rebels, hostages, Ghost Recon's friendly companies)
being seen does not count: his fire team is AI-only (+0xD9 = 1, like every
enemy team). Checked over real RAM: the fire team IkeAIMgr finds for each
soldier's company (+0x178), platoon (+0x444) and fireteam (+0x448) has +0xD9 =
0 for exactly the squad (6 single player, 9 online with AI backup, both players
and their AI in split screen) and 1 for every enemy and every ally.

AddEnemy has two callers that matter: ReportEnemyContact (an AI becomes aware
of an enemy: GR 0x0018A880, JS 0x003DB310) and ReportUnderFire (shot at, or a
team mate killed: GR 0x00189F60, JS 0x003DA970). Jungle Storm's ReportUnderFire
never calls AddEnemy for a silenced shot; Ghost Recon's does. The reporting
team must still have a living member (FireTeamAI::GetNumLivingMembers).

The reserve
-----------

Created with the mission, on every console, the way total war makes its
copies: in the mission's parsed SetupFileData, before anything is created from
it. IkeSimulationMgr::HandleLoadMap calls AdjustHeightsOverFloors(SetupFileData)
(GR 0x00389058, JS 0x00366B10) once the map is loaded and before
HandleLoadMission creates the companies (it creates them only if HandleLoadMap
has set SimMgr +0x474, which it does right before that call). That call goes
through rf_setup first, which:

  * picks the template: every company that is not Allied (no mission file holds
    the players' squad), every platoon of it, every team of
    that platoon with at least one original soldier on the map (Hidden = 0, id
    below 0x7E00: never a total-war copy, never a reserve soldier -- so the
    first reserve is never the second one's template); the one whose first such soldier
    stands farthest from the first zone marked Insertion (its Pos0);
  * appends four soldiers to the actor list: copies (SetupFileActorEntry
    assignment, the game's own) of that team's originals in turn, each 1-2 m
    beside the one it copies, IgorId 0x7E00 + 16 k + j (file ids stop at 1673,
    total war's copies start at 0x10000), named "RF" (scripts find soldiers by
    name: a named officer keeps his objective), never Hidden, never a platoon
    leader, on every difficulty;
  * appends a team "RF1" (id 0x7F00 + k) with those four as members and no
    plan, and puts its id last in the template team's platoon;
  * with "two teams", does it again from the next-farthest team;
  * then makes the call it replaced.

Each copy's spot goes through the floor lookup AdjustHeightsOverFloors itself
makes (RSSimScene planning level count, then SimMgr vt+0x34 with the level, or
vt+0x30); the original's spot too. No floor under either, or floors more than
1 m apart, and the copy takes the original's exact spot -- the case total war's
height check exists for (a copy over no floor is created with no room and no
level, and the first collision update dereferences it).

The rest is the game's own: CreatePlatoon walks the platoon's team list,
CreateTeam makes the FireTeamAI and the four soldiers (CreateHuman broadcasts
each to every console with MasterSendAll), and with no plan the team gets an
empty script -- it stands where it was put and fights what it sees. A setup
that already holds a reserve team is left as it is (no second copy if the same
data is loaded twice).

Waking it up
------------

CreateTeam's call to FireTeamAI::SetScriptControlled (GR 0x0038E498, JS
0x0036C1C4; the FireTeamAI in a0, the team entry in s5) goes through rf_note:
it does what SetScriptControlled does (+0xD9 = the flag) and, for a reserve
team, keeps its company, platoon, fireteam and FireTeamAI. On a console that
runs no AI (an online joiner: no FireTeamAI objects at all) CreateTeam returns
before that call, so nothing is noted there.

The alarm (rf_alarm, in place of both `jal AddEnemy`): AddEnemy runs first and
its result goes back unchanged. Then, for a new enemy, a reporting team with
someone alive, a soldier whose fire team is a players' team, and a
reserve this mission: the first time, or 15 s after the last time, each reserve
team still found where rf_note saw it made (IkeAIMgr's fireteam lookup returns
the same FireTeamAI) is sent to the spot where the enemy was seen (the
EnemyStruct's position), or -- when RSSimScene::FindLevel finds no walkable
level there (much of Jungle Storm's jungle) -- to where the spotting team's
leader stands:

  * not while it is already fighting (danger level +0x30 > 0);
  * it gets a formation leader if it has none (+0xE4: the first member alive,
    FireTeamAI::SetFormationLeader) -- TeamInvestigationBehavior::Process
    reads it unconditionally;
  * an investigation already on top of its script (type 0x1E) is pointed at
    the new spot the way FireTeamAI::InvestigateThisNow re-points one (+0x18
    the spot, +0x24 = 0: plan again); otherwise a new
    TeamInvestigationBehavior goes on top (new 0x28, the constructor, the spot
    at +0x18, RSScript::AddElement) exactly as FireTeamAI::Update builds one --
    without Update's gates (150 m, 20 s, an outdoor leader), which keep the
    stock investigations local.

TeamInvestigationBehavior is the stock "go and look": every member gets run
speed and a TeamLocationBehavior to the spot; the team fights whatever it
meets on the way and goes quiet at the spot if it finds nobody, until the next
sighting moves it on.

Online co-op
------------

The AI runs on the host only; the alarm, the note and the investigation are
host-side AI code (a joiner has no FireTeamAI objects, so neither hook does
anything there). The reserve soldiers are created by the host's CreateHuman,
which sends each soldier to every console like every other mission soldier;
their movement reaches the joiners the way all AI movement does. rf_setup is
deterministic -- same mission data, same picks, same ids on every console --
so a console that creates the units from its own parse builds the same reserve
(the same holds for total war's copies). Nothing random, nothing host-only
that joiners would lack.

Memory: four soldiers per team, about 100 KB (total war measured about 25 KB
per extra soldier); "two teams" about 200 KB, on every console.

Total war
---------

Total war copies a team's actors as each team is parsed; the reserve is added
after the whole parse, so total war never copies it, and its copies never
become templates (only ids below 0x7E00 are; total war's start at 0x10000) --
no copy of a copy, no id used twice. With total war on, the reserve stands
beside a team total war has already grown. Total war's height check
skips the reserve (its ids are below 0x10000); rf_setup's own check covers
them. Four soldiers stay inside FireTeamAI::Update's limit of six.

Game modes
----------

Any mode whose enemies are units of the mission file: the campaign missions
and the Mission / Firefight / Recon types played on them (single player,
split screen, online co-op) -- 21 of Jungle Storm's 45 .MIS files and 28 of
Ghost Recon's 46. Jungle Storm's Defend and Siege, its CP and DP maps and the
MP maps of both games build their enemies at run time from script (the
opposing-force generator; no <Actor> in the .MIS): there is no hostile team to
copy, so no reserve -- those modes already send waves. Ghost Recon's training
maps hold no hostile team either.

The patch
---------

  GR 0x00389058 / JS 0x00366B10  HandleLoadMap `jal AdjustHeightsOverFloors` -> `jal rf_setup`
  GR 0x0038E498 / JS 0x0036C1C4  CreateTeam `jal SetScriptControlled` -> `jal rf_note`
  GR 0x0018A8F0 / JS 0x003DB380  ReportEnemyContact `jal AddEnemy` -> `jal rf_alarm`
  GR 0x0018A0E4 / JS 0x003DAC08  ReportUnderFire `jal AddEnemy` -> `jal rf_alarm`

Every delay slot is kept. The routines live in unreferenced caves (see
CAVES): no jump, branch, pointer or address formation reaches them from live
code in the executable or (Jungle Storm) either overlay -- the only references
into them come from code that is itself unreferenced -- and no other option
writes them.

Verified in a RAM interpreter (never played)
--------------------------------------------

  * The setup: for every .MIS of both games, a SetupFileData built in RAM with
    the game's own array and string code (stock JS and GR saves), rf_setup run
    with the real AdjustHeightsOverFloors after it and floors from a model with
    a hole and a 3 m step under two copies: the template is the one an
    independent reading of the .MIS picks, the reserve team, its members, its
    platoon, the copies' fields and spots are as described, the two copies over
    the hole and the step stand on their original's spot, every original ends
    where a stock run puts it, and a second pass adds nothing. Also with
    total-war copies in every team. 42 reserve teams (JS) and 56 (GR) built.
  * The real CreateTeam over a reserve team: CreateHuman gets the four copies,
    no plan is built, rf_note keeps the fire team and lowers the alarm; a stock
    team goes through with its plan and leaves the slots alone.
  * The alarm, with the real AddEnemy, over online-host (JS), single-player
    (JS stock) and single-player (GR) saves: a squad soldier reported by a
    hostile team puts an investigation of his spot on top of a dormant team
    (which gets a formation leader), and the real TeamInvestigationBehavior::
    Process then gives every member that spot as his destination (284 m and
    251 m away); an ally reported, a known enemy, a dead reporting team, a
    stale slot, no reserve, a fighting reserve: nothing; a second sighting
    inside 15 s changes nothing, after 16 s it re-points the same
    investigation; no level at the spot: the spotters' leader's spot.
  * Joiner saves (mode 3): not one of 103 soldiers has a FireTeamAI; the same
    session's host save: 103 of 103.
  * Breaking each test in the routines (ally, throttle, leader, spot, stale,
    fighting, living, level fallback; Allied, idempotency, floor, step,
    originals, Hidden, farthest, platoon, difficulty, the note) makes the
    matching check fail.
"""

from __future__ import annotations

from .grasm import assemble

RF_TEAM = 0x7F00          # reserve team ids 0x7F00 + k
RF_ACTOR = 0x7E00         # reserve soldier ids 0x7E00 + 16 k + j
RF_SIZE = 4               # soldiers per reserve team
REAIM_HI = 0x4170         # 15.0 s between two re-aims (float high half)
OFFS = ((0xBF800000, 0xBF800000), (0x3F800000, 0xBF800000),     # -1,-1   1,-1
        (0xBF800000, 0x3F800000), (0x00000000, 0xC0000000))     # -1, 1   0,-2   (m)
CHOICES = ("off", "one team", "two teams")
NTEAMS = {"off": 0, "one team": 1, "two teams": 2}

GAMES = {
    "gr": dict(
        HOOKS={0x00389058: ("setup", 0x0C0E2FDC, "HandleLoadMap jal AdjustHeightsOverFloors"),
               0x0038E498: ("note", 0x0C0E39B8, "CreateTeam jal SetScriptControlled"),
               0x0018A8F0: ("alarm", 0x0C062D6C, "ReportEnemyContact jal AddEnemy"),
               0x0018A0E4: ("alarm", 0x0C062D6C, "ReportUnderFire jal AddEnemy")},
        ZSTRIDE=0x4C, C="s4", P="s6", T="s7", DEAD=0x298,
        SYMS=dict(ADJUST=0x0038BF70, IncActors=0x001EDC70, CopyEntry=0x001E5E70,
                  StrSetC=0x0053EA60, IncUi=0x001343F0, IncTeams=0x001EC4E0,
                  SCENE_GET=0x00359760, LVLCOUNT=0x0036A1C0, LVLID=0x0036A190,
                  ADDENEMY=0x0018B5B0, GETLIVING=0x0018BE40, OBJMGR=0x005EAB20,
                  GETCTRL=0x00365830, SIMHUMAN=0x005A1BF0, AIMGR=0x005E5778,
                  GETFT=0x001A17E0, CLOCK=0x005DFC20, SCENE=0x006376D0,
                  FINDLEVEL=0x00504690, GETHUMANAI=0x0018EAD0, SETLEADER=0x0018CFA0,
                  NEW=0x00102DB0, TIBCTOR=0x001BF860, ADDELEM=0x001BAEC0),
    ),
    "js": dict(
        HOOKS={0x00366B10: ("setup", 0x0C0DA684, "HandleLoadMap jal AdjustHeightsOverFloors"),
               0x0036C1C4: ("note", 0x0C0DB0C8, "CreateTeam jal SetScriptControlled"),
               0x003DB380: ("alarm", 0x0C0F6FB4, "ReportEnemyContact jal AddEnemy"),
               0x003DAC08: ("alarm", 0x0C0F6FB4, "ReportUnderFire jal AddEnemy")},
        ZSTRIDE=0x58, C="s4", P="s3", T="s7", DEAD=0x29C,
        SYMS=dict(ADJUST=0x00369A10, IncActors=0x001EAD40, CopyEntry=0x001D9240,
                  StrSetC=0x003FF4A0, IncUi=0x001EAE80, IncTeams=0x001E9910,
                  SCENE_GET=0x002474D0, LVLCOUNT=0x003455F0, LVLID=0x003455D0,
                  ADDENEMY=0x003DBED0, GETLIVING=0x003DC740, OBJMGR=0x0062B748,
                  GETCTRL=0x00340F30, SIMHUMAN=0x005B56D0, AIMGR=0x0062C6F8,
                  CLOCK=0x00684768, SCENE=0x00689E30,
                  FINDLEVEL=0x004EB6B0, GETHUMANAI=0x003DF0F0, SETLEADER=0x003DD600,
                  NEW=0x00103470, TIBCTOR=0x001BB860, ADDELEM=0x001B6E10),
    ),
}

# ---------------------------------------------------------------------------
# The routines. Each is placed whole in one cave; they call each other by name.
#
# rf_setup's frame (no inner routine moves sp: they all work in this frame):
#   0x00-0x7f s0..s7, 0x80 ra, 0x88 the simulation manager, 0x8c k,
#   0x90/0x94 the insertion point, 0x98 template team id, 0x9c m, 0xa0 its platoon,
#   0xa4-0xbb E[6] (template actor indices), 0xbc ra of rf_add, 0xc0-0xcb the copy's
#   point, 0xcc ra of rf_floor, 0xd0-0xdb the original's point, 0xdc found, 0xe0 ra of
#   rf_pick / rf_look, 0xe4 rf_look's point, 0xe8 its level, 0xec ra of rf_pteam.
# s0 = SetupFileData throughout.
# ---------------------------------------------------------------------------
ROUTINES = {}

ROUTINES["rf_setup"] = """
rf_setup:
    addiu sp, sp, -0x100
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s2, 0x20(sp)
    sq    s3, 0x30(sp)
    sq    s4, 0x40(sp)
    sq    s5, 0x50(sp)
    sq    s6, 0x60(sp)
    sq    s7, 0x70(sp)
    sd    ra, 0x80(sp)
    sw    a0, 0x88(sp)
    move  s0, a1                    ; SetupFileData
    lui   t0, %hi(rf_data)
    addiu t0, t0, %lo(rf_data)
    sw    zero, 0x0c(t0)            ; a new mission: no reserve seen made yet,
    sw    zero, 0x1c(t0)
    sw    zero, 0x20(t0)            ; and the alarm is down
    lw    t1, 0x5c(s0)              ; teams
    lw    t2, 0x60(s0)
su_idem:
    blez  t2, su_ins
    nop
    lw    t3, 4(t1)
    addiu t3, t3, -{RF_TEAM}
    sltiu t3, t3, 4
    bnez  t3, su_x                  ; this setup holds its reserve already
    addiu t2, t2, -1
    b     su_idem
    addiu t1, t1, 0x24
su_ins:
    mtc1  zero, f0
    mtc1  zero, f1
    lw    t1, 0x74(s0)              ; zones: the first marked Insertion (its Pos0)
    lw    t2, 0x78(s0)
su_zone:
    blez  t2, su_zdone
    nop
    lbu   t3, 0x38(t1)
    bnez  t3, su_zhit
    addiu t2, t2, -1
    b     su_zone
    addiu t1, t1, {ZSTRIDE}
su_zhit:
    lwc1  f0, 0x18(t1)
    lwc1  f1, 0x1c(t1)
su_zdone:
    swc1  f0, 0x90(sp)
    swc1  f1, 0x94(sp)
    sw    zero, 0x8c(sp)            ; k
    li    t0, -1
    j     rf_setup2
    sw    t0, 0x98(sp)              ; no template used yet
su_x:
    j     rf_adj
    nop
"""

ROUTINES["rf_setup2"] = """
rf_setup2:
    lw    t0, 0x8c(sp)
    slti  t0, t0, {NTEAMS}
    beqz  t0, rf_adj
    nop
    jal   rf_pick                   ; v0 = template team id (-1: none), 0xa0 its platoon
    nop
    bltz  v0, rf_adj
    sw    v0, 0x98(sp)
    jal   rf_add
    nop
    lw    t0, 0x8c(sp)
    addiu t0, t0, 1
    b     rf_setup2
    sw    t0, 0x8c(sp)
rf_adj:
    lw    a0, 0x88(sp)
    jal   ADJUST                    ; the call the hook replaced
    move  a1, s0
    ld    ra, 0x80(sp)
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    lq    s3, 0x30(sp)
    lq    s4, 0x40(sp)
    lq    s5, 0x50(sp)
    lq    s6, 0x60(sp)
    lq    s7, 0x70(sp)
    jr    ra
    addiu sp, sp, 0x100
"""

# rf_pick: companies (0x28 each, +0x14 platoon ids, +0x24 Allied) that are not Allied; each
# platoon of them -> rf_pteam. -> v0 best team id (-1), 0xa0 its platoon.
ROUTINES["rf_pick"] = """
rf_pick:
    sw    ra, 0xe0(sp)
    li    v0, -1
    lui   t0, 0xbf80
    mtc1  t0, f3                    ; best distance^2 so far: -1
    lw    s1, 0x18(s0)              ; companies
    lw    s2, 0x14(s0)
pk_comp:
    blez  s1, pk_done
    nop
    lbu   t0, 0x24(s2)              ; Allied (no mission file holds the players' squad)
    bnez  t0, pk_cnext
    nop
    lw    s3, 0x18(s2)              ; its platoon ids
    lw    s4, 0x14(s2)
pk_plat:
    blez  s3, pk_cnext
    nop
    lw    t0, 0(s4)
    addiu a0, s0, 0x3c              ; platoons, 0x1c each
    jal   rf_find
    li    a3, 0x1c
    beqz  a2, pk_pnext
    nop
    jal   rf_pteam
    move  s7, a2
pk_pnext:
    addiu s3, s3, -1
    b     pk_plat
    addiu s4, s4, 4
pk_cnext:
    addiu s1, s1, -1
    b     pk_comp
    addiu s2, s2, 0x28
pk_done:
    lw    ra, 0xe0(sp)
    jr    ra
    nop
"""

# rf_pteam: s7 = a platoon: each team of it (but the one already used) with an original on the
# map; the farthest from the insertion point so far becomes the best (v0, f3, 0xa0 = s7).
ROUTINES["rf_pteam"] = """
rf_pteam:
    sw    ra, 0xec(sp)
    lw    s5, 0x18(s7)              ; its team ids
    lw    s6, 0x14(s7)
pt_team:
    blez  s5, pt_done
    nop
    lw    t0, 0(s6)
    lw    t1, 0x98(sp)
    beq   t0, t1, pt_next           ; the first reserve's template
    addiu a0, s0, 0x5c
    jal   rf_find
    li    a3, 0x24
    beqz  a2, pt_next
    nop
    jal   rf_elig
    nop
    blez  v1, pt_next
    nop
    jal   rf_act
    lw    a0, 0xa4(sp)              ; the first of them
    lwc1  f0, 0x30(a0)
    lwc1  f2, 0x90(sp)
    sub.s f0, f0, f2
    mul.s f0, f0, f0
    lwc1  f1, 0x34(a0)
    lwc1  f2, 0x94(sp)
    sub.s f1, f1, f2
    mul.s f1, f1, f1
    add.s f0, f0, f1
    c.lt.s f3, f0
    bc1f  pt_next                   ; not farther
    nop
    mov.s f3, f0
    lw    v0, 0(s6)
    sw    s7, 0xa0(sp)
pt_next:
    addiu s5, s5, -1
    b     pt_team
    addiu s6, s6, 4
pt_done:
    lw    ra, 0xec(sp)
    jr    ra
    nop
"""

# Leaves (no calls, no stack; none touches v0, f3 or an s register):
#   rf_find: a0 = &RSArray {data, count}, t0 = an id, a3 = the stride -> a2 = entry (0: none)
#   rf_elig: a2 = a team entry -> v1 = how many of its members are originals (id < RF_ACTOR: no
#            total-war copy, no reserve soldier) on the map (not Hidden), at most 6, their actor indices in E[] (0xa4)
#   rf_act:  a0 = an actor index -> a0 = its entry (0x5c each)
ROUTINES["rf_find"] = """
rf_find:
    lw    t1, 0(a0)
    lw    t2, 4(a0)
fd_l:
    blez  t2, fd_none
    nop
    lw    a2, 4(t1)
    beq   a2, t0, fd_hit
    addiu t2, t2, -1
    b     fd_l
    addu  t1, t1, a3
fd_none:
    jr    ra
    move  a2, zero
fd_hit:
    jr    ra
    move  a2, t1
rf_act:
    sll   v1, a0, 1
    addu  v1, v1, a0
    sll   v1, v1, 3
    subu  v1, v1, a0                ; 23 i
    sll   v1, v1, 2                 ; 0x5c i
    lw    a0, 0xc(s0)
    jr    ra
    addu  a0, a0, v1
"""

ROUTINES["rf_elig"] = """
rf_elig:
    lw    t2, 0x18(a2)
    lw    t3, 0x14(a2)
    move  v1, zero
el_mem:
    blez  t2, el_done
    nop
    lw    t4, 0(t3)
    sltiu t5, t4, {RF_ACTOR}
    beqz  t5, el_next               ; a total-war copy or a reserve soldier: originals only
    nop
    lw    t5, 0xc(s0)
    lw    t6, 0x10(s0)
    move  a0, zero
el_find:
    beq   a0, t6, el_next
    nop
    lw    a1, 4(t5)
    beq   a1, t4, el_hit
    nop
    addiu a0, a0, 1
    b     el_find
    addiu t5, t5, 0x5c
el_hit:
    lbu   a1, 0x50(t5)              ; Hidden: a script brings him in later
    bnez  a1, el_next
    sll   a1, v1, 2
    addu  a1, a1, sp
    sw    a0, 0xa4(a1)
    addiu v1, v1, 1
    slti  a1, v1, 6
    beqz  a1, el_done
    nop
el_next:
    addiu t2, t2, -1
    b     el_mem
    addiu t3, t3, 4
el_done:
    jr    ra
    nop
"""

# rf_add: reserve team k (0x8c) from template team 0x98: RF_SIZE copies of its originals in turn.
# s1 j, s2 the source index, s3 the new index, s4 the copy.
ROUTINES["rf_add"] = """
rf_add:
    sw    ra, 0xbc(sp)
    lw    t0, 0x98(sp)
    addiu a0, s0, 0x5c
    jal   rf_find
    li    a3, 0x24
    jal   rf_elig                   ; E[], v1 = m (>= 1: rf_pteam checked)
    nop
    sw    v1, 0x9c(sp)
    move  s1, zero
ad_j:
    move  t0, s1                    ; j mod m
    lw    t1, 0x9c(sp)
ad_mod:
    slt   t2, t0, t1
    bnez  t2, ad_m
    nop
    b     ad_mod
    subu  t0, t0, t1
ad_m:
    sll   t0, t0, 2
    addu  t0, t0, sp
    lw    s2, 0xa4(t0)              ; the soldier to copy
    lw    s3, 0x10(s0)              ; the copy's index
    addiu a0, s0, 0xc
    jal   IncActors
    addiu a1, s3, 1
    jal   rf_act                    ; (the array moved)
    move  a0, s3
    move  s4, a0
    jal   rf_act
    move  a0, s2
    move  a1, a0
    jal   CopyEntry
    move  a0, s4
    lw    t0, 0x8c(sp)
    sll   t0, t0, 4
    addu  t0, t0, s1
    addiu t0, t0, {RF_ACTOR}
    sw    t0, 4(s4)                 ; IgorId
    lui   t1, 0x0101
    ori   t1, t1, 0x0101
    sw    t1, 0x4c(s4)              ; on every difficulty
    sb    zero, 0x50(s4)            ; on the map from the start
    sb    zero, 0x58(s4)            ; never a platoon leader
    sll   t2, s1, 3
    lui   t3, %hi(rf_offs)
    addiu t3, t3, %lo(rf_offs)
    addu  t3, t3, t2
    lwc1  f0, 0x30(s4)
    lwc1  f1, 0(t3)
    add.s f0, f0, f1
    swc1  f0, 0x30(s4)
    lwc1  f0, 0x34(s4)
    lwc1  f1, 4(t3)
    add.s f0, f0, f1
    jal   rf_floor
    swc1  f0, 0x34(s4)
    lui   a1, %hi(rf_name)
    addiu a1, a1, %lo(rf_name)
    jal   StrSetC
    addiu a0, s4, 0xc
    addiu s1, s1, 1
    slti  t0, s1, {RF_SIZE}
    bnez  t0, ad_j
    nop
    j     rf_add2
    nop
"""

# rf_add2: the team (id RF_TEAM + k, "RFk", no plan, the four as members), its id last in the
# template team's platoon (0xa0).
ROUTINES["rf_add2"] = """
rf_add2:
    lw    s3, 0x60(s0)
    addiu a0, s0, 0x5c
    jal   IncTeams
    addiu a1, s3, 1
    lw    t0, 0x5c(s0)
    sll   t1, s3, 3                 ; *0x24
    addu  t1, t1, s3
    sll   t1, t1, 2
    addu  s4, t0, t1
    lw    t0, 0x8c(sp)
    addiu t1, t0, {RF_TEAM}
    sw    t1, 4(s4)
    sb    zero, 0x1c(s4)            ; no plan: it waits
    sll   t0, t0, 2
    lui   a1, %hi(rf_tname)
    addiu a1, a1, %lo(rf_tname)
    addu  a1, a1, t0
    jal   StrSetC
    addiu a0, s4, 0xc
    addiu a0, s4, 0x14
    jal   IncUi
    li    a1, {RF_SIZE}
    lw    t0, 0x14(s4)
    lw    t1, 0x8c(sp)
    sll   t1, t1, 4
    addiu t1, t1, {RF_ACTOR}
    addiu t2, t1, {RF_SIZE}
ad_mid:
    sw    t1, 0(t0)
    addiu t1, t1, 1
    bne   t1, t2, ad_mid
    addiu t0, t0, 4
    lw    s5, 0xa0(sp)              ; the platoon
    lw    s3, 0x18(s5)
    addiu a0, s5, 0x14
    jal   IncUi
    addiu a1, s3, 1
    lw    t0, 0x14(s5)
    sll   t1, s3, 2
    addu  t0, t0, t1
    lw    t1, 0x8c(sp)
    addiu t1, t1, {RF_TEAM}
    sw    t1, 0(t0)
    lw    ra, 0xbc(sp)
    jr    ra
    nop
"""

# rf_floor: s4 the copy (moved), s2 its original's index; a soldier the loop does not place
# (+0x2C = 0) is left alone, like his original.
ROUTINES["rf_floor"] = """
rf_floor:
    sw    ra, 0xcc(sp)
    lbu   t0, 0x2c(s4)
    beqz  t0, fl_out
    nop
    jal   rf_act
    move  a0, s2
    move  s5, a0                    ; the original
    addiu a0, sp, 0xd0
    jal   rf_look
    move  a1, s5
    sw    v0, 0xdc(sp)
    addiu a0, sp, 0xc0
    jal   rf_look
    move  a1, s4
    lw    t0, 0xdc(sp)
    and   v0, v0, t0
    beqz  v0, fl_rev                ; no floor under one of them
    lwc1  f0, 0xd8(sp)
    lwc1  f1, 0xc8(sp)
    sub.s f0, f0, f1
    lui   t0, 0x3f80
    mtc1  t0, f1
    c.lt.s f1, f0
    bc1t  fl_rev                    ; his floor more than 1 m above
    neg.s f0, f0
    c.lt.s f1, f0
    bc1f  fl_out                    ; or below
    nop
fl_rev:
    lw    t0, 0x30(s5)
    sw    t0, 0x30(s4)
    lw    t0, 0x34(s5)
    sw    t0, 0x34(s4)
    lw    t0, 0x38(s5)
    sw    t0, 0x38(s4)
fl_out:
    lw    ra, 0xcc(sp)
    jr    ra
    nop
"""

# rf_look: a0 = a point in the frame, a1 = an actor entry: his point copied there and put through
# the loop's floor lookup -> v0 found.
ROUTINES["rf_look"] = """
rf_look:
    sw    ra, 0xe0(sp)
    lw    t0, 0x30(a1)
    sw    t0, 0(a0)
    lw    t0, 0x34(a1)
    sw    t0, 4(a0)
    lw    t0, 0x38(a1)
    sw    t0, 8(a0)
    sw    a0, 0xe4(sp)
    lw    t0, 0x3c(a1)
    jal   SCENE_GET
    sw    t0, 0xe8(sp)
    jal   LVLCOUNT
    move  a0, v0
    beqz  v0, lk_flat
    nop
    jal   SCENE_GET
    nop
    move  a0, v0
    jal   LVLID
    lw    a1, 0xe8(sp)
    mov.s f12, f0
    lw    a0, 0x88(sp)
    lw    t9, 0(a0)
    lw    t9, 0x34(t9)
    jalr  t9
    lw    a1, 0xe4(sp)
    b     lk_out
    nop
lk_flat:
    lw    a0, 0x88(sp)
    lw    t9, 0(a0)
    lw    t9, 0x30(t9)
    jalr  t9
    lw    a1, 0xe4(sp)
lk_out:
    lw    ra, 0xe0(sp)
    jr    ra
    nop
"""

# CreateTeam's `jal SetScriptControlled` (a0 FireTeamAI, a1 the flag; s5 the team entry).
ROUTINES["rf_note"] = """
rf_note:
    sb    a1, 0xd9(a0)              ; SetScriptControlled
    lw    t0, 4(s5)                 ; the team entry's id
    addiu t0, t0, -{RF_TEAM}
    sltiu t1, t0, {NTEAMS}
    beqz  t1, nt_out
    sll   t1, t0, 4
    lui   t2, %hi(rf_data)
    addiu t2, t2, %lo(rf_data)
    addu  t1, t2, t1
    sw    {C}, 0(t1)                ; company, platoon, fireteam
    sw    {P}, 4(t1)
    sw    {T}, 8(t1)
    sw    a0, 0xc(t1)               ; and the FireTeamAI
    sw    zero, 0x20(t2)            ; the alarm is down
nt_out:
    jr    ra
    nop
"""

# Both `jal AddEnemy` (a0 FireTeamAI, a1 enemy id, a2 bool). s0 the team, s1 the id, s2 the
# EnemyStruct AddEnemy returns (0: not new), s3 the point.
ROUTINES["rf_alarm"] = """
rf_alarm:
    addiu sp, sp, -0x50
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s2, 0x20(sp)
    sq    s3, 0x30(sp)
    sd    ra, 0x40(sp)
    move  s0, a0
    jal   ADDENEMY                  ; the call the hook replaced
    move  s1, a1
    sd    v0, 0x48(sp)
    beqz  v0, al_out                ; nobody new for this team
    move  s2, v0
    lui   t0, %hi(rf_data)
    addiu t0, t0, %lo(rf_data)
    lw    t1, 0x0c(t0)
    lw    t2, 0x1c(t0)
    or    t1, t1, t2
    beqz  t1, al_out                ; no reserve this mission
    nop
    jal   GETLIVING
    move  a0, s0
    blez  v0, al_out                ; nobody left in the team to raise it
    lui   a0, %hi(OBJMGR)
    lw    a0, %lo(OBJMGR)(a0)
    jal   GETCTRL
    move  a1, s1
    beqz  v0, al_out
    nop
    lw    t0, 0(v0)
    lui   t1, %hi(SIMHUMAN)
    addiu t1, t1, %lo(SIMHUMAN)
    bne   t0, t1, al_out            ; not a soldier
    nop
    lw    a1, 0x178(v0)             ; his company, platoon, fireteam
    lw    a2, 0x444(v0)
    jal   rf_ft
    lw    a3, 0x448(v0)
    beqz  v0, al_out
    nop
    lbu   t0, 0xd9(v0)
    bnez  t0, al_out                ; an AI-only team (allies): not your squad
    nop
    j     rf_alarm2
    nop
al_out:
    ld    v0, 0x48(sp)
    ld    ra, 0x40(sp)
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    lq    s3, 0x30(sp)
    jr    ra
    addiu sp, sp, 0x50
"""

ROUTINES["rf_alarm2"] = """
rf_alarm2:
    lui   t0, %hi(CLOCK)
    lw    t0, %lo(CLOCK)(t0)
    lwc1  f0, 0xd4(t0)              ; game time
    lui   t0, %hi(rf_data)
    addiu t0, t0, %lo(rf_data)
    lw    t1, 0x20(t0)
    beqz  t1, a2_go                 ; the first sighting: the alarm
    lwc1  f1, 0x24(t0)
    sub.s f1, f0, f1
    lui   t1, {REAIM_HI}
    mtc1  t1, f2
    c.lt.s f1, f2
    bc1t  a2_out                    ; told them less than 15 s ago
    nop
a2_go:
    li    t1, 1
    sw    t1, 0x20(t0)
    swc1  f0, 0x24(t0)
    addiu s3, s2, 4                 ; where the enemy was seen
    lui   a0, %hi(SCENE)
    lw    a0, %lo(SCENE)(a0)
    jal   FINDLEVEL
    move  a1, s3
    bnez  v0, a2_tgt                ; walkable: there
    lw    t0, 0xe4(s0)              ; else where the spotters' leader stands
    beqz  t0, a2_tgt
    nop
    addiu s3, t0, 0x2c
a2_tgt:
    move  s2, zero
a2_slot:
    lui   t1, %hi(rf_data)
    addiu t1, t1, %lo(rf_data)
    sll   t0, s2, 4
    addu  s1, t1, t0
    lw    t0, 0xc(s1)
    beqz  t0, a2_next
    lw    a1, 0(s1)
    lw    a2, 4(s1)
    jal   rf_ft
    lw    a3, 8(s1)
    lw    t0, 0xc(s1)
    bne   v0, t0, a2_next           ; not the team rf_note saw made (another mission's)
    move  a0, v0
    jal   rf_go
    move  a1, s3
a2_next:
    addiu s2, s2, 1
    slti  t0, s2, {NTEAMS}
    bnez  t0, a2_slot
    nop
a2_out:
    j     al_out
    nop
"""

# rf_go: a0 = a reserve FireTeamAI, a1 = the point.
ROUTINES["rf_go"] = """
rf_go:
    addiu sp, sp, -0x40
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s2, 0x20(sp)
    sd    ra, 0x30(sp)
    move  s0, a0
    lw    t0, 0x30(s0)
    bgtz  t0, go_out                ; already fighting
    move  s1, a1
    lw    t0, 0xe4(s0)
    bnez  t0, go_led                ; it has a formation leader
    move  s2, zero
go_m:
    lw    t0, 0x18(s0)
    slt   t0, s2, t0
    beqz  t0, go_out                ; nobody left
    move  a0, s0
    jal   GETHUMANAI
    move  a1, s2
    addiu s2, s2, 1
    beqz  v0, go_m
    nop
    lw    a0, 0x14(v0)              ; his SimHuman
    beqz  a0, go_m
    sw    v0, 0x38(sp)
    lw    t9, 0(a0)
    lw    t9, {DEAD}(t9)
    jalr  t9
    nop
    bnez  v0, go_m                  ; dead
    move  a0, s0
    jal   SETLEADER
    lw    a1, 0x38(sp)
go_led:
    lw    t0, 0xc(s0)               ; its script: an investigation on top?
    lw    t1, 4(t0)
    beqz  t1, go_new
    nop
    lw    t2, 4(t1)
    li    t3, 0x1e
    bne   t2, t3, go_new
    nop
    move  v0, t1                    ; point it at the new spot, plan again
    b     go_pt
    sb    zero, 0x24(t1)
go_new:
    jal   NEW
    li    a0, 0x28
    beqz  v0, go_out
    nop
    jal   TIBCTOR
    move  a0, v0
    lw    a0, 0xc(s0)
    jal   ADDELEM
    move  a1, v0
    lw    t0, 0xc(s0)
    lw    v0, 4(t0)                 ; the one just added
go_pt:
    lw    t2, 0(s1)
    sw    t2, 0x18(v0)
    lw    t2, 4(s1)
    sw    t2, 0x1c(v0)
    lw    t2, 8(s1)
    sw    t2, 0x20(v0)
go_out:
    ld    ra, 0x30(sp)
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    jr    ra
    addiu sp, sp, 0x40
"""

FT = {
    "gr": """
rf_ft:
    lui   a0, %hi(AIMGR)
    j     GETFT
    lw    a0, %lo(AIMGR)(a0)
""",
    "js": """
rf_ft:
    lui   a0, %hi(AIMGR)
    lw    a0, %lo(AIMGR)(a0)
    lw    t9, 0(a0)
    lw    t9, 0x14(t9)
    jr    t9
    nop
""",
}

# rf_data: 0x00 slot 0 {company, platoon, fireteam, FireTeamAI}, 0x10 slot 1, 0x20 alarm up,
# 0x24 when the reserve was last sent; then the offsets and the names.
DATA = """
rf_data:
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
    .word 0
rf_offs:
{OFFS}rf_name:
    .asciiz "RF"
rf_tname:
    .asciiz "RF1"
    .asciiz "RF2"
"""


def _fmt(game, nteams):
    g = GAMES[game]
    return dict(RF_TEAM=RF_TEAM, RF_ACTOR=RF_ACTOR, RF_SIZE=RF_SIZE, NTEAMS=nteams,
                ZSTRIDE=g["ZSTRIDE"], REAIM_HI=REAIM_HI, C=g["C"], P=g["P"], T=g["T"],
                DEAD=g["DEAD"],
                OFFS="".join("    .word %#x\n    .word %#x\n" % xy for xy in OFFS))


def sources(game, nteams=2):
    """{piece name: assembly source}; every piece is placed whole in one cave."""
    f = _fmt(game, nteams)
    out = {name: src.format(**f) for name, src in ROUTINES.items()}
    out["rf_ft"] = FT[game]
    out["rf_data"] = DATA.format(**f)
    return out


# ---------------------------------------------------------------------------
# Where the pieces go: (first, last byte, pieces in order). Every range is code
# no jump, branch, pointer or address formation reaches from live code (the
# executable and, for Jungle Storm, both overlays), written by no other option,
# and claimed for this module in the shared cave list.
# ---------------------------------------------------------------------------
CAVES = {
    "gr": (
        (0x00419748, 0x004198B7, ("rf_add", "rf_setup2")),    # sceSifLoadStartModule.._sceSifLoadElfPart
        (0x00421E30, 0x00421F77, ("rf_go", "rf_note")),       # sceMcSetFileInfo past total war's height check
        (0x00412B58, 0x00412C6F, ("rf_alarm", "rf_ft")),      # iRotateThreadReadyQueue..iSuspendThread
        (0x00419D38, 0x00419E1F, ("rf_alarm2",)),             # SetTLBHandler, SetDebugHandler
        (0x00428A18, 0x00428AE7, ("rf_setup",)),              # sceMpegGetPictureRAW8..sceMpegGetDecodeMode
        (0x004220E0, 0x004221A7, ("rf_add2",)),               # sceMcUnformat
        (0x00406498, 0x0040654F, ("rf_pteam",)),              # __sigtramp_r
        (0x0040E610, 0x0040E6B7, ("rf_floor",)),              # sceDevConsFrame
        (0x004028B0, 0x00402957, ("rf_look",)),               # _getenv_r, _setlocale_r
        (0x00428C50, 0x00428CEF, ("rf_elig",)),               # sceMpegSetDefaultPtsGap..sceSetPtm
        (0x00415938, 0x004159C7, ("rf_pick",)),               # scePowerOffHandler
        (0x00406318, 0x004063A7, ("rf_find",)),               # _signal_r
        (0x00411730, 0x004117BF, ("rf_data",)),               # _ExecPS2..SetVInterruptHandler
    ),
    "js": (
        (0x0017A3A0, 0x0017A55F, ("rf_add", "rf_add2")),      # GetGsHParam.. syscall stub twins
        (0x0018C630, 0x0018C7FF, ("rf_go", "rf_alarm2")),     # mceStorePwd's twin
        (0x00195F10, 0x00196077, ("rf_setup", "rf_pteam")),   # scePadGetFrameCount.. twins
        (0x00173450, 0x00173567, ("rf_look", "rf_elig")),
        (0x00193B28, 0x00193C07, ("rf_alarm",)),
        (0x00175528, 0x001755F7, ("rf_pick", "rf_note")),
        (0x0018BA20, 0x0018BADF, ("rf_floor", "rf_ft")),
        (0x001846D8, 0x00184787, ("rf_setup2",)),
        (0x001694C8, 0x00169577, ("rf_find", "rf_data")),
    ),
}


def _measure(src, syms):
    """(words, labels) of `src` at base 0, any symbol it lacks standing in as 0."""
    import re
    from .grasm import AsmError
    syms = dict(syms)
    while True:
        try:
            return assemble(src, 0, syms)
        except AsmError as ex:
            m = re.search(r"unknown symbol '(.+)'", str(ex))
            if not m or m.group(1) in syms:
                raise
            syms[m.group(1)] = 0


def build(game, nteams):
    """{va: word} for every cave word and hook, for 1 or 2 reserve teams."""
    g = GAMES[game]
    src = sources(game, nteams)
    sizes, rel = {}, {}
    for name, s in src.items():
        w, lab = _measure(s, g["SYMS"])
        sizes[name] = len(w)
        rel[name] = lab
    base, syms = {}, dict(g["SYMS"])
    for lo, hi, names in CAVES[game]:
        at = lo
        for name in names:
            base[name] = at
            at += 4 * sizes[name]
        if at > hi + 1:
            raise ValueError("%s cave %08X outgrown by %s" % (game, lo, "+".join(names)))
    if set(base) != set(src):
        raise ValueError("%s pieces without a cave: %s" % (game, sorted(set(src) ^ set(base))))
    for name, lab in rel.items():
        for k, v in lab.items():
            if k in syms and syms[k] != base[name] + v:
                raise ValueError("label %s defined twice" % k)
            syms[k] = base[name] + v
    out = {}
    for name, s in src.items():
        words, _ = assemble(s, base[name], syms)
        for i, w in enumerate(words):
            out[base[name] + 4 * i] = w
    for va, (piece, _stock, _note) in g["HOOKS"].items():
        out[va] = 0x0C000000 | ((syms["rf_" + piece] >> 2) & 0x3FFFFFF)
    return out, syms


# ---------------------------------------------------------------------------
# Stock words of every word this module can write (read from the retail ELFs; selftest re-reads).
# Adjacent string literals join with no separator, so they are parsed as fixed 8-digit words.
# ---------------------------------------------------------------------------
_GR_STOCK_HEX = {   # first word of each cave piece run: its stock words
    0x00419748: (   # rf_add + rf_setup2
        "27BDFFF0 FFBF0000 0C106540 0000402D DFBF0000 03E00008 27BD0010 00000000"
        "27BDFF90 FFB40050 FFB30040 00C0A02D FFB20030 00E0982D FFB00010 00A0902D"
        "FFBF0060 0080802D 0C10634A FFB10020 0440002C 3C02FFFF 0C10638A 00000000"
        "50400004 3C02005F 3C02FFFE 10000025 3442FFFC 0200282D 2451F648 240600FC"
        "0220202D 0C101C9C 2630FFF8 0240282D A2000103 262400FC 0C101C9C 240600FC"
        "3C04005F A20001FF 0260282D 2484F840 AFA00000 0000302D 0200382D 24080200"
        "0200482D 240A0010 0C10531C 0000582D 04430004 8E22FFF8 3C02FFFE 10000009"
        "3442FFFF 54400004 AE820000 3C02FFFE 10000004 3442FFFD 0000102D 8E030004"
        "AE830004 DFBF0060 DFB40050 DFB30040 DFB20030 DFB10020 DFB00010 03E00008"
        "27BD0070 00000000 27BDFFF0 FFBF0000 0C1065DA 24070001 DFBF0000 03E00008"
        "27BD0010 00000000 00A0302D 27BDFFF0 3C050058 FFBF0000 24A57C68 0C1065DA"
        "24070001 DFBF0000 03E00008 27BD0010"),
    0x00421E30: (   # rf_go + rf_note
        "8E84F014 10000045 2402FF2E 32310007 24500BF0 AC550BF0 AE130004 3C02005F"
        "AE110008 24430B80 26040014 0240282D 24490B80 6AC60007 6EC60000 6AC7000F"
        "6EC70008 6AC80017 6EC80010 B1260007 B5260000 B127000F B5270008 B1280017"
        "B5280010 6AC6001F 6EC60018 6AC70027 6EC70020 6AC8002F 6EC80028 B126001F"
        "B5260018 B1270027 B5270020 B128002F B5280028 6AC60037 6EC60030 6AC7003F"
        "6EC70038 B1260037 B5260030 B127003F B5270038 AE030010 0C101C9C 240603FF"
        "A2000413 0C104758 0000202D 3C09005F 0200382D 02E0202D 25292100 AFA00000"
        "2405000E 24060001 24080414 240A0004 0C10531C 0000582D 0040802D 16000004"
        "3C030057 2402000E 10000003 AC62F010 0C1046C0 8E84F014 0200102D DFBF0090"
        "DFB70080 DFB60070 DFB50060 DFB40050 DFB30040 DFB20030 DFB10020 DFB00010"
        "03E00008 27BD00A0"),
    0x00412B58: (   # rf_alarm + rf_ft
        "27BDFFE0 FFB00000 0080802D 2E020080 10400005 FFBF0010 3C020057 8C43E120"
        "14600003 3C03005F 10000010 2402FFFF 3C05005F 2463BD88 8CA4BD80 8C620004"
        "24070001 304201FF 00023040 24420001 00662821 AC620004 A0A70008 00A0182D"
        "0C1046C4 A0700009 0200102D DFBF0010 DFB00000 03E00008 27BD0020 00000000"
        "27BDFFE0 FFBF0010 FFB00000 2403FFD1 0000000C 0040802D 12040005 2E020100"
        "0C104698 00000000 10000018 DFBF0010 10400004 3C020057 8C43E120 14600003"
        "3C03005F 10000010 2402FFFF 3C05005F 2463BD88 8CA4BD80 8C620004"),
    0x00419D38: (   # rf_alarm2
        "27BDFFD0 3C020057 FFB00000 FFB10010 3C100042 2610A240 0080882D AC51E510"
        "0200282D FFBF0020 0C1045E4 24040001 0200282D 0C1045E4 24040002 0200282D"
        "0C1045E4 24040003 0220102D DFBF0020 DFB10010 DFB00000 03E00008 27BD0030"
        "0080302D 27BDFFE0 24C4FFFF FFBF0010 2C82000D 14400004 FFB00000 3C02FFFF"
        "10000014 3442FFFF 3C020057 00061880 2442E518 2C840003 00621821 8C700000"
        "10800007 AC650000 3C050042 00C0202D 0C1045E4 24A5A480 10000006 0200102D"
        "3C050042"),
    0x00428A18: (   # rf_setup
        "27BDFFF0 3C020FFF FFBF0000 3442FFFF 00A22824 3C032000 8C870040 00A32825"
        "ACE600E4 ACE500D8 ACE000DC ACE000B0 0C10A36C ACE000E0 DFBF0000 03E00008"
        "27BD0010 00000000 27BDFFF0 3C020FFF FFBF0000 00C74018 3442FFFF 00063100"
        "00A22824 8C830040 3C022000 00073900 00A22825 AC6700E0 AC6500D8 AC6800E4"
        "AC6600DC 0C10A36C AC6000B0 DFBF0000 03E00008 27BD0010 8C820040 AC47009C"
        "AC450094 03E00008 AC460098 00000000 8C880040 8D020094 ACA20000 8D030098"
        "ACC30000"),
    0x004220E0: (   # rf_add2
        "27BDFFB0 FFB20030 FFB10020 0080902D 3C110057 FFB00010 8E24F014 FFBF0040"
        "0C1046CC 00A0802D 04410003 3C02005F 1000001F 2402FF38 24440B40 8C830024"
        "14600005 3C02005F 0C1046C0 8E24F014 10000017 2402FF9C 3C09005F 24420BC0"
        "25292100 AC500008 0040382D AC520004 24050011 AFA00000 24060001 24080030"
        "240A0004 0C10531C 0000582D 0040802D 16000004 3C030057 24020011 10000003"
        "AC62F010 0C1046C0 8E24F014 0200102D DFBF0040"),
    0x00406498: (   # rf_pteam
        "27BDFFD0 FFB10010 FFB00000 00A0882D FFBF0020 2E220020 10400008 0080802D"
        "8E0401D4 14800008 00112880 0C1018AA 0200202D 50400003 8E0401D4 10000019"
        "2402FFFF 00112880 00A41021 8C430000 10600014 24020001 1C600006 00000000"
        "2402FFFF 10620007 00A41021 10000009 8C430000 10620005 00A41021 10000005"
        "8C430000 10000007 24020002 10000005 24020003 0220202D 0060F809 AC400000"),
    0x0040E610: (   # rf_floor
        "27BDFF80 24E7FFFF FFB60060 2508FFFF FFB20020 00A0B02D 00C0902D FFB50050"
        "FFB40040 02C7A821 FFB10010 0248A021 0080882D FFB00000 FFBF0070 FFB30030"
        "240700F9 24080007 0C103AE2 26D00001 0220202D 02A0282D 0240302D 240700F5"
        "0C103AE2 24080007 0220202D 02C0282D 0280302D 240700FA 0C103AE2 24080007"
        "0220202D 02A0282D 0280302D 240700F6 0C103AE2"),
    0x004028B0: (   # rf_look
        "27BDFFE0 FFBF0010 0C1009E4 03A0302D DFBF0010 03E00008 27BD0020 00000000"
        "27BDFFB0 FFB20020 FFB10010 00A0902D FFB00000 0080882D FFBF0040 00C0802D"
        "1200000F FFB30030 3C130058 0200202D 0C101B32 26655B10 10400006 3C050058"
        "0200202D 0C101B32 24A55B00 14400006 0000102D AE300034 10000002 AE320030"
        "3C130058 26625B10 DFBF0040 DFB30030"),
    0x00428C50: (   # rf_elig
        "8C820040 24030001 FC450078 03E00008 AC430070 00000000 8C820040 FC400078"
        "03E00008 AC400070 8C820040 03E00008 AC4500D8 00000000 8C830040 03E00008"
        "8C6200CC 00000000 8C830040 03E00008 8C6200D0 00000000 8C820040 03E00008"
        "244200B4 00000000 8C820040 03E00008 244200B4 00000000 8C830040 8C6200E8"
        "03E00008 AC6500E8"),
    0x00415938: (   # rf_pick
        "27BDFFA0 FFB30030 FFB20020 0080982D FFB40040 00A0902D FFB10010 2404001B"
        "FFBF0050 3C11005F FFB00000 0C10563E 2634F440 3C020057 8C43E1C0 14600003"
        "00000000 0C10567E 00000000 0C106968 00000000 8E30F440 AE920004 0C10697A"
        "AE33F440 0C10564A 00000000 0200102D DFBF0050 DFB40040 DFB30030 DFB20020"),
    0x00406318: (   # rf_find
        "27BDFFC0 FFB10010 FFB20020 00A0882D FFB00000 00C0902D FFBF0030 2E220020"
        "14400006 0080802D 24030016 3C02FFFF AE030000 1000000F 3442FFFF 8E0201D4"
        "14400009 00111880 0C1018AA 0200202D 50400004"),
    0x00411730: (   # rf_data
        "24030007 0000000C 03E00008 00000000 24030008 0000000C 03E00008 00000000"
        "24030009 0000000C 03E00008 00000000 2403000A 0000000C 03E00008 00000000"
        "2403000B 0000000C 03E00008 00000000 2403000C"),
}
_JS_STOCK_HEX = {   # first word of each cave piece run: its stock words
    0x0017A3A0: (   # rf_add + rf_add2
        "2403004C 0000000C 03E00008 00000000 2403004D 0000000C 03E00008 00000000"
        "2403004E 0000000C 03E00008 00000000 2403004F 0000000C 03E00008 00000000"
        "24030050 0000000C 03E00008 00000000 24030051 0000000C 03E00008 00000000"
        "24030052 0000000C 03E00008 00000000 2403FFAD 0000000C 03E00008 00000000"
        "24030054 0000000C 03E00008 00000000 2403FFAB 0000000C 03E00008 00000000"
        "24030056 0000000C 03E00008 00000000 24030057 0000000C 03E00008 00000000"
        "2403FFA8 0000000C 03E00008 00000000 24030059 0000000C 03E00008 00000000"
        "2403FFA6 0000000C 03E00008 00000000 2403005B 0000000C 03E00008 00000000"
        "2403005C 0000000C 03E00008 00000000 2403FFA4 0000000C 03E00008 00000000"
        "2403005D 0000000C 03E00008 00000000 2403FFA3 0000000C 03E00008 00000000"
        "2403005E 0000000C 03E00008 00000000 2403FFA2 0000000C 03E00008 00000000"
        "2403005F 0000000C 03E00008 00000000 2403FFA1 0000000C 03E00008 00000000"
        "24030060 0000000C 03E00008 00000000 24030061 0000000C 03E00008 00000000"
        "24030062 0000000C 03E00008 00000000 24030063"),
    0x0018C630: (   # rf_go + rf_alarm2
        "27BDFFC0 FFB10010 FFBF0030 0080882D FFB20020 12200015 FFB00000 3C120062"
        "3C022000 2643CAC0 00628025 0C05B780 0200202D 2C420400 50400004 241003FF"
        "0C05B780 0200202D 0040802D 2642CAC0 3C052000 00452825 0220202D 0C05A8D6"
        "0200302D 02301821 A0600000 3C020057 DFBF0030 8C446638 DFB20020 DFB10010"
        "DFB00000 0805E8C4 27BD0040 00000000 27BDFF60 3C020062 FFB70080 FFB60070"
        "2457C500 FFB40050 00E0B02D FFB30040 00A0A02D FFB20030 0080982D FFBF0090"
        "FFB50060 FFB10020 FFB00010 8EE20024 14400003 00C0902D 10000032 2402FF9C"
        "3C150057 0C05E8CC 8EA46634 0440002D 2402FF38 12400004 00000000 82420000"
        "14400005 3C020062 0C05E8C0 8EA46634 10000024 2402FF2E 3C100062 2451C5B0"
        "2610CAC0 AC53C5B0 0240282D AE300010 26240014 AE340004 0C05B8F2 240603FF"
        "0200202D A2200413 0C05F324 24050400 3C090062 3C0B0019 AFB60000 02E0202D"
        "0220382D 2529DAC0 256BC630 2405000C 24060001 24080414 0C05F5AA 240A0004"
        "0040802D 16000004 3C030057 2402000C 10000003 AC626630 0C05E8C0 8EA46634"
        "0200102D DFBF0090 DFB70080 DFB60070 DFB50060 DFB40050 DFB30040 DFB20030"
        "DFB10020 DFB00010 03E00008"),
    0x00195F10: (   # rf_setup + rf_pteam
        "0080302D 24030070 2404001C 70C31818 00A42018 27BDFFF0 3C020062 FFBF0000"
        "2442DD50 00832021 00441021 8C430010 1060001D 0000102D 0C065564 00C0202D"
        "0040302D 24030001 90C20072 50430003 90C20064 10000014 0000102D 2C420002"
        "14400011 0000102D 90C20066 2C420002 1440000D 0000102D 90C5007A 90C4007C"
        "90C3007B 00052A38 90C20079 00042638 00031C38 0044102D 0065182D 0043102D"
        "0002103C 0002103F DFBF0000 03E00008 27BD0010 00000000 27BDFFB0 3C020062"
        "FFB00010 2403000A 2450DF40 FFB20030 FFB10020 0080902D FFBF0040 00A0882D"
        "AE06000C 3C040062 AC43DF40 2484DD00 AE120004 24050001 AE110008 0000302D"
        "AFA00000 0200382D 24080080 0200482D 240A0080 0C05F5AA 0000582D 04430003"
        "8E030010 1000000A 0000102D 24020001 14620007 0060102D 0240202D 0220282D"
        "0C065616 24060002 8E030010 0060102D DFBF0040 DFB20030 DFB10020 DFB00010"
        "03E00008"),
    0x00173450: (   # rf_look + rf_elig
        "27BDFF90 24020208 FFB00060 00C0802D 2603FFFF AFA40054 0010180A 0100302D"
        "03A0202D 00A0402D 00E0282D FFBF0068 A7A2000C AFA80010 AFA30014 AFA80000"
        "0C05C332 AFA30008 12000002 8FA30000 A0600000 DFB00060 DFBF0068 03E00008"
        "27BD0070 00000000 3C020057 27BDFF90 8C488E00 24020208 3C037FFF 0080382D"
        "3463FFFF 03A0202D FFBF0060 AFA30014 AFA30008 A7A2000C AFA70010 AFA80054"
        "0C05C332 AFA70000 8FA30000 DFBF0060 A0600000 03E00008 27BD0070 00000000"
        "27BDFF90 3C037FFF 00A0402D 00C0282D 3463FFFF AFA40054 00E0302D 24020208"
        "03A0202D FFBF0060 AFA30014 AFA30008 A7A2000C AFA80010 0C05C332 AFA80000"
        "8FA30000 DFBF0060 A0600000 03E00008 27BD0070 00000000"),
    0x00193B28: (   # rf_alarm
        "27BDFFF0 3C020FFF FFBF0000 3442FFFF 00A22824 3C032000 8C870040 00A32825"
        "ACE600FC ACE500F0 ACE000F4 ACE000C8 0C064FC8 ACE000F8 DFBF0000 03E00008"
        "27BD0010 00000000 27BDFFF0 3C020FFF FFBF0000 00C74018 3442FFFF 00063100"
        "00A22824 8C830040 3C022000 00073900 00A22825 AC6700F8 AC6500F0 AC6800FC"
        "AC6600F4 0C064FC8 AC6000C8 DFBF0000 03E00008 27BD0010 8C830040 24020001"
        "03E00008 AC6210A0 8C820040 AC4700B4 AC4500AC 03E00008 AC4600B0 00000000"
        "8C880040 8D0200AC ACA20000 8D0300B0"),
    0x00175528: (   # rf_pick + rf_note
        "27BDFFE0 FFB00000 FFBF0010 0C05D57E 0000802D 0040182D 28620004 10400008"
        "0200102D 18600007 DFBF0010 0C05D594 24100001 0C05D590 0040202D 0200102D"
        "DFBF0010 DFB00000 03E00008 27BD0020 4843E000 24020001 14820003 00000000"
        "10000004 34630400 3C02FFFF 3442FBFF 00621824 48C3E000 03E00008 00000000"
        "4843E000 24020001 14820003 00000000 10000004 34630800 3C02FFFF 3442F7FF"
        "00621824 48C3E000 03E00008 00000000 4842E000 00021282 03E00008 30420001"),
    0x0018BA20: (   # rf_floor + rf_ft
        "27BDFFB0 3C030062 FFB10020 FFB00010 2471C500 FFBF0040 FFB20030 8E220024"
        "14400003 0080802D 1000001E 2402FF9C 3C120057 0C05E8CC 8E446634 04410003"
        "3C070062 10000017 2402FF38 3C090062 24E7C580 3C0B0019 ACF00014 0220202D"
        "2529DAC0 256BBA10 AFA00000 24050014 24060001 24080030 0C05F5AA 240A0004"
        "0040802D 16000004 3C030057 24020014 10000003 AC626630 0C05E8C0 8E446634"
        "0200102D DFBF0040 DFB20030"),
    0x001846D8: (   # rf_setup2
        "3C020057 244365F8 8C620008 04410004 00000000 3C028000 03E00008 34428001"
        "10800003 00000000 8C620010 AC820000 10A00005 00000000 8C630010 24020080"
        "00431023 ACA20000 03E00008 0000102D 27BDFFC0 FFB10010 FFB00000 00A0882D"
        "FFB20020 FFBF0030 0C060CC8 0080802D"),
    0x001694C8: (   # rf_find + rf_data
        "27BDFFE0 FFBF0010 0C05A4E0 03A0302D DFBF0010 03E00008 27BD0020 00000000"
        "27BDFFD0 FFB00000 00C0802D FFB10008 0080882D FFB20010 00A0902D FFB30018"
        "0200202D 12000010 FFBF0020 3C130058 0C05B6C8 2665FB50 3C050058 24A5FB40"
        "10400005 0200202D 0C05B6C8 00000000 14400007 0000102D AE300034 10000003"
        "AE320030 00000000 3C130058 2662FB50 DFB00000 DFB10008 DFB20010 DFB30018"
        "DFBF0020 03E00008"),
}


def _stock(table, hooks):
    out = {}
    for base, hexwords in table.items():
        words = "".join(hexwords.split())
        for i in range(len(words) // 8):
            out[base + 4 * i] = int(words[8 * i:8 * i + 8], 16)
    for va, (_piece, stock, _note) in hooks.items():
        out[va] = stock
    return out


GR_STOCK = _stock(_GR_STOCK_HEX, GAMES["gr"]["HOOKS"])
JS_STOCK = _stock(_JS_STOCK_HEX, GAMES["js"]["HOOKS"])
STOCK = {"gr": GR_STOCK, "js": JS_STOCK}

NOTES = {"rf_setup": "alarm reinforcements: build the reserve into the mission setup",
         "rf_setup2": "alarm reinforcements: one reserve team per pick, then the height pass",
         "rf_pick": "alarm reinforcements: the hostile team farthest from the insertion zone",
         "rf_pteam": "alarm reinforcements: the teams of one platoon",
         "rf_find": "alarm reinforcements: an entry by id; an actor's entry by index",
         "rf_elig": "alarm reinforcements: a team's original soldiers on the map",
         "rf_add": "alarm reinforcements: copy four soldiers",
         "rf_add2": "alarm reinforcements: the reserve team, last in its platoon",
         "rf_floor": "alarm reinforcements: a copy over no floor takes its original's spot",
         "rf_look": "alarm reinforcements: the height pass's own floor lookup",
         "rf_note": "alarm reinforcements: note the reserve's fire team when CreateTeam makes it",
         "rf_alarm": "alarm reinforcements: a hostile team adds one of your squad",
         "rf_alarm2": "alarm reinforcements: send the reserve (first sighting, then every 15 s)",
         "rf_go": "alarm reinforcements: an investigation of the spot on top of the reserve",
         "rf_ft": "alarm reinforcements: IkeAIMgr's fireteam lookup",
         "rf_data": "alarm reinforcements: state (reserve slots, alarm, last time), offsets, names"}


def edits(game, choice="off"):
    """(va, value, stock, note) for "off" / "one team" / "two teams"."""
    if choice not in NTEAMS:
        raise ValueError("alarm reinforcements: %r" % (choice,))
    n = NTEAMS[choice]
    if not n:
        return []
    words, syms = build(game, n)
    st = STOCK[game]
    starts = sorted((syms[name], name) for _lo, _hi, names in CAVES[game] for name in names)
    hooks = GAMES[game]["HOOKS"]
    out = []
    for va in sorted(words):
        if va in hooks:
            note = "alarm reinforcements: %s -> jal rf_%s" % (hooks[va][2], hooks[va][0])
        else:
            note = NOTES[[nm for a, nm in starts if a <= va][-1]]
        out.append((va, words[va], st[va], note))
    return out


def js_edits(v: dict):
    return edits("js", v.get("js_alarm_reinforce", "off"))


def gr_edits(v: dict):
    return edits("gr", v.get("gr_alarm_reinforce", "off"))


def cards(prefix: str = "js_", group: str = "Enemies") -> list:
    from .model import CHOICE, Choice, Setting
    gr = prefix == "gr_"
    quiet = ("" if gr else "; and Jungle Storm's own rule stays: shots from a suppressed weapon never give "
                           "you away by themselves, only being seen does")
    modes = ("Ghost Recon's multiplayer and training maps have no enemies to copy" if gr else
             "Defend, Siege, the co-op CP/DP maps and the MP maps build their enemies by script and get no reserve")
    return [
        Setting(prefix + "alarm_reinforce", "Alarm reinforcements", CHOICE, "off", group,
                confidence="experimental",
                choices=[
                    Choice("off", "Off (as shipped)", "No reserve: being seen costs what it always did."),
                    Choice("one team", "One team (4 soldiers)", "One reserve fire team per mission."),
                    Choice("two teams", "Two teams (8 soldiers)",
                           "Two reserve teams, beside the two hostile teams farthest from your insertion."),
                ],
                help="Being spotted costs you. Each mission gets an enemy reserve: four soldiers (or "
                     "two teams of four), copies of the hostile team posted farthest from your "
                     "insertion zone, waiting beside it. They stay there and fight only what comes to "
                     "them -- until the alarm: the first time any enemy team notices one of your squad "
                     "(a sentry sees you, a team comes under your fire, or loses a man to it and works "
                     "out where the shot came from). Then the reserve runs to where you were seen, and "
                     "every later sighting (at most every 15 s) sends it on to the newest spot. Kill a "
                     "lone sentry quietly and nobody is left to raise it%s. Allies being seen do not "
                     "count. Works on every mission whose enemies are in the mission file (the "
                     "campaign, and Firefight / Recon / Mission played on campaign maps); %s." % (quiet, modes),
                caution=("Never played. Adds 4 (or 8) soldiers to every mission, about 100 KB per team "
                         "(total war's measure of 25 KB a soldier). The copies keep their original's "
                         "script id, as total war's copies do." if gr else
                         "Never played. Adds 4 (or 8) soldiers to every mission on every console, about "
                         "100 KB per team (total war's measure of 25 KB a soldier) -- 32 MB online "
                         "joiners already run short at mission end. The copies keep their original's "
                         "script id, as total war's copies do. Online co-op: the host's AI raises the "
                         "alarm and sends the reserve; put the same setting on every disc so every "
                         "console builds the same mission.")),
    ]


def selftest(gr_elf: bytes = None, js_elf: bytes = None, used: dict = None) -> list:
    """Stock words against the retail ELFs, every variant inside its caves, no address twice, every
    written word in the stock table, the hooks present, off = nothing, and (given {game: set of VAs})
    no word another option writes. [] = pass."""
    bad = []
    for game, elf, d in (("gr", gr_elf, 0x80), ("js", js_elf, 0x100)):
        st = STOCK[game]
        if elf is not None:
            for va, w in st.items():
                off = va - 0x100000 + d
                if int.from_bytes(elf[off:off + 4], "little") != w:
                    bad.append("%s stock %08X" % (game, va))
        if edits(game, "off"):
            bad.append("%s: off writes words" % game)
        caves = [(lo, hi) for lo, hi, _n in CAVES[game]]
        for choice in ("one team", "two teams"):
            e = edits(game, choice)
            vas = [va for va, *_ in e]
            if len(set(vas)) != len(vas):
                bad.append("%s %s: duplicate VA" % (game, choice))
            for va, _w, s, _note in e:
                if st.get(va) != s:
                    bad.append("%s %s: %08X has no stock word" % (game, choice, va))
                if va not in GAMES[game]["HOOKS"] and not any(lo <= va <= hi for lo, hi in caves):
                    bad.append("%s %s: %08X outside the caves" % (game, choice, va))
                if used and va in used.get(game, ()):
                    bad.append("%s %s: %08X is written by another option" % (game, choice, va))
            for va in GAMES[game]["HOOKS"]:
                if va not in vas:
                    bad.append("%s %s: hook %08X missing" % (game, choice, va))
    return bad

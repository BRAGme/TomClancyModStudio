"""Total war: Ghost Recon (SLUS-20613) and Jungle Storm (SLUS-20820).

Every enemy is an <Actor> in Company > Platoon > Team of a mission file, and
every Team becomes one FireTeamAI with a leader and followers in formation --
most enemies are already small teams (Ghost Recon on Hard: 198 alone, 72
pairs, 170 threes). SetupFileData::ProcessTeamMembers (GR 0x001E5840, JS
0x001E1AE0) reads one team's actors; at its end a routine appends copies of
that team's own actors to the same team, so the game's own team AI makes them
followers. Scripts that call CreateTeam mid-mission (reinforcements) go
through the same reader, so they get their copies too.

  * enemy teams (company not allied, name not starting '_'): each visible
    actor gets (multiplier - 1) copies -- x3 makes a lone sentry a leader
    with two followers, x6 a team of six. Actors a script hides until later are never copied,
    so no invisible copy can hold up a "kill everyone" objective;
  * the players' squad ("_Company"): each AI soldier (Owner -1) gets
    (multiplier - 1) copies; the players' own soldiers are never copied. The
    squad is built in memory by the platoon screen or the split-screen
    chooser, not read from a file, so a second routine runs where those
    builders finish (see "the squad pass" below);
  * a team never grows past 6: FireTeamAI::Update (GR 0x0018DD0C) runs no AI
    at all for a team of 7 or more.

Copies stand 1 m beside their original, get ids above any file id
((k + 1) << 16 | the original's index: file ids stop at 1673), are never
platoon leaders, and are named "TW" (enemies) or "_Reserve" (friendlies) --
scripts find soldiers by name, so a named officer keeps his objective and his
copies are plain soldiers.

A copy 1 m beside its original can stand where there is no floor (off a
ledge, inside a wall). IkeSimulationMgr::AdjustHeightsOverFloors (GR
0x0038BF70, JS 0x00369A10) then finds none: z becomes 0 and the soldier is
created with no room and no level, and the first collision update calls
RSLevel::CheckForLevelChange on a null level (Jungle Storm G03: TLB miss at
0x6C). The height check runs after each actor's floor lookup: a copy whose
lookup failed, or whose floor is more than 1 m from its original's, takes its
original's exact position instead (the id names the original).

Three fixed tables would overflow with more soldiers:

  * the radar holds 30 contacts within 65 m and adds without a bound check
    (GR +0x178 / count +0x448, JS +0x318 / +0x5E8); on the lowest difficulty
    it lists enemies too -- the clamp stops adding at 30;
  * single player's debrief has 6 soldier rows (AfterAction::
    SetIndividualData, GR 0x00340AF0, JS 0x002E6830, row index unchecked) --
    the clamp drops rows 7 and up;
  * the per-frame soldier draw sort has 30 slots per model per view (GR
    0x00454600, JS 0x0041C040), unchecked -- Jungle Storm C03 at x4 froze
    loading in. It is rewritten without the limit (see grdrawlist), so every
    soldier is still drawn.

Memory is the real ceiling: about 25 KB per extra soldier. Savestates show
3.8-7.5 MB free in Ghost Recon missions and 2.6-5.9 MB in Jungle Storm, so
x3 fits Ghost Recon and x2 is the safe choice for Jungle Storm. The heap
option moves the game heap into PCSX2's 128 MB mode (0x02000000, 95 MB) for
the bigger multipliers.

Caves: GR 0x00417330-0x00417998 (sceAddDrv..sceGetstat) and 0x00421DA0
(sceMcSetFileInfo), JS 0x00196078 and 0x00195910 (twins of the unused scePad
info functions), 0x0017F990 (twins of sceRemove..sceDopen; the squad pass,
then the height check at 0x0017FC84) and 0x0019B888 (sceScfGetAspect's twin),
none referenced from the loaded image or Jungle Storm's online/offline
overlays. The routine was run in an interpreter against a mock of the parsed
mission data (team sizes, hidden actors, allied companies, the squad file,
unique ids and the original each names, member lists, no copy from a moved
array, registers and stack); the squad pass and the clamps likewise. The
height check ran inside the real AdjustHeightsOverFloors loop of each ELF
against stubbed floor lookups, compared word for word with the unpatched loop.
"""

from __future__ import annotations

from . import grdrawlist
from .grasm import assemble

GAMES = {
    "gr": dict(
        HOOK=0x001E5E44, HOOK_STOCK=0x00000000,   # nop after the actor loop
        RESUME=0x001E5E48,                        # ld ra,112(sp): the epilogue
        CAVE=0x00417330, CAVE_END=0x00417998,
        SETUP="s5", TEAM="s6", MODE="s4",
        SCR=0xF0,                                 # dead stack entry of the frame
        SYMS={"IncActors": 0x001EDC70, "CopyEntry": 0x001E5E70,
              "StrSetC": 0x0053EA60, "IncUi": 0x001343F0},
        RADAR_HOOK=0x002CF4AC, RADAR_HOOK_STOCK=0x8FA30180,    # lw v1,0x180(sp)
        RADAR_HOOK2=0x002CF4B0, RADAR_HOOK2_STOCK=0x8C640448,  # lw a0,0x448(v1): its slot
        DEBRIEF_HOOK=0x00340B20, DEBRIEF_HOOK_STOCK=0x128001B9,  # beqz s4,0x341208
    ),
    "js": dict(
        HOOK=0x001E1F64, HOOK_STOCK=0xDFBF0090,   # ld ra,144(sp); slot lq fp is harmless
        RESUME=0x001E1F68,
        CAVE=0x00196078, CAVE_END=0x00196328,
        RADAR_CAVE=0x00195910, RADAR_END=0x00195B84,
        SETUP="s5", TEAM="s4", MODE="s6",
        SCR=0x100, TMP=0xA0,                      # the loop's own dead stack entry
        SYMS={"EntryCtor": 0x001D9310, "EntryAssign": 0x001D9240,
              "EntryDtor": 0x001D7050, "ActorPush": 0x001E1FA0,
              "UiPush": 0x001E1800, "StrSetC": 0x003FF4A0},
        RADAR_HOOK=0x0029E298, RADAR_HOOK_STOCK=0x8E4305E8,    # lw v1,0x5e8(s2)
    ),
}

ONE = 0x3F800000
MONE = 0xBF800000
OFFS = [(ONE, 0), (MONE, 0), (0, ONE), (0, MONE), (ONE, ONE)]   # metres, x / y

CHOICES_ENEMIES = ("1", "2", "3", "4", "6")
CHOICES_ALLIES = ("1", "2", "3")


def _prologue(g, emul, fmul):
    S, T, M = g["SETUP"], g["TEAM"], g["MODE"]
    return f"""
cave:
    lw    t0, 0x18({S})             ; companies.count
    blez  t0, out
    lw    t1, 0x14({S})             ; companies.data (delay)
    addiu t0, t0, -1
    sll   t2, t0, 5                 ; *0x28
    sll   t0, t0, 3
    addu  t0, t0, t2
    addu  t0, t1, t0                ; the company being parsed = the last one
    lbu   t1, 0x24(t0)              ; Allied="1"
    bnez  t1, out
    move  {M}, zero                 ; (delay) hostile
    lw    t1, 0x10(t0)              ; company Name: RSString rep
    beqz  t1, hostile
    nop
    lw    t1, 4(t1)                 ; char*
    beqz  t1, hostile
    nop
    lb    t1, 0(t1)
    addiu t1, t1, -0x5f             ; '_' = the player's squad ("_Company")
    bnez  t1, hostile
    nop
    li    {M}, 1
    b     setmul
    li    t3, {fmul}                ; friendly multiplier (delay)
hostile:
    li    t3, {emul}                ; enemy multiplier
setmul:
    addiu t3, t3, -1                ; copies per source
    blez  t3, out
    lw    s0, 0x18({T})             ; n = members
    blez  s0, out
    lw    t0, 0x10({S})             ; actors.count (delay)
    subu  s1, t0, s0                ; base: this team's actors are the last n
    lw    t6, 0xc({S})              ; actors.data
    move  t4, zero                  ; eligible sources
    move  t5, zero                  ; i
cnt:
    addu  t7, s1, t5
    sll   t8, t7, 4                 ; *0x5c
    sll   t9, t7, 3
    addu  t8, t8, t9
    subu  t8, t8, t7
    sll   t8, t8, 2
    addu  t8, t6, t8
    bnez  {M}, cntf
    lbu   t9, 0x50(t8)              ; Hidden (delay, harmless on the friendly path)
    bnez  t9, cntnext
    nop
    b     cntnext
    addiu t4, t4, 1
cntf:
    lw    t9, 0x54(t8)              ; Owner
    addiu t9, t9, 1
    bnez  t9, cntnext
    nop
    addiu t4, t4, 1
cntnext:
    addiu t5, t5, 1
    slt   t9, t5, s0
    bnez  t9, cnt
    nop
    blez  t4, out
    move  s2, zero                  ; (delay) add = sources * (MUL-1)
mul:
    addu  s2, s2, t4
    addiu t3, t3, -1
    bgtz  t3, mul
    nop
room:
    li    t9, 6                     ; FireTeamAI::Update ignores teams of 7+
    subu  t9, t9, s0
    blez  t9, out
    slt   t8, t9, s2                ; (delay)
    beqz  t8, go
    nop
    move  s2, t9
go:
    move  s3, zero                  ; cursor
    sw    zero, {g['SCR']:#x}(sp)          ; k
find:
    lw    t6, 0xc({S})
    addu  t7, s1, s3
    sll   t8, t7, 4
    sll   t9, t7, 3
    addu  t8, t8, t9
    subu  t8, t8, t7
    sll   t8, t8, 2
    addu  t8, t6, t8                ; &actors[base+cursor]
    addiu s3, s3, 1                 ; advance the cursor, wrapping at n
    slt   t9, s3, s0
    bnez  t9, nowrap
    nop
    move  s3, zero
nowrap:
    bnez  {M}, findf
    lbu   t9, 0x50(t8)              ; (delay)
    bnez  t9, find                  ; hidden: a script owns him, skip
    nop
    b     picked
    nop
findf:
    lw    t9, 0x54(t8)
    addiu t9, t9, 1
    bnez  t9, find                  ; a player's own soldier: skip
    nop
picked:
    sw    t7, {g['SCR'] + 8:#x}(sp)        ; source index
"""


def _gr_source(emul, fmul):
    g = GAMES["gr"]
    SCR = g["SCR"]
    return _prologue(g, emul, fmul) + f"""
    lw    t0, 0x10(s5)              ; new index = actors.count
    sw    t0, {SCR + 4:#x}(sp)
    addiu a0, s5, 0xc
    jal   IncActors
    addiu a1, t0, 1
    lw    v0, 0xc(s5)               ; actors.data, re-read: the array may have moved
    lw    t0, {SCR + 4:#x}(sp)
    sll   t8, t0, 4
    sll   t9, t0, 3
    addu  t8, t8, t9
    subu  t8, t8, t0
    sll   t8, t8, 2
    addu  t8, v0, t8                ; dst
    lw    t0, {SCR + 8:#x}(sp)
    sll   t9, t0, 4
    sll   t1, t0, 3
    addu  t9, t9, t1
    subu  t9, t9, t0
    sll   t9, t9, 2
    addu  a1, v0, t9                ; src
    sw    t8, {SCR + 12:#x}(sp)
    jal   CopyEntry
    move  a0, t8
    lw    a0, {SCR + 12:#x}(sp)     ; dst
    lw    t0, {SCR:#x}(sp)          ; k
    addiu t0, t0, 1
    sll   t0, t0, 16
    lw    t1, {SCR + 8:#x}(sp)      ; source index
    or    t1, t1, t0                ; IgorId = (k+1)<<16 | source: unique, >= 0x10000,
    sw    t1, 4(a0)                 ;   and it names the source for the height check
    sw    t1, {SCR + 4:#x}(sp)
    sb    zero, 0x58(a0)            ; never a platoon leader
    beqz  s4, pos
    nop
    sb    zero, 0x51(a0)            ; friendly: not a campaign soldier
pos:
    lw    t2, {SCR:#x}(sp)          ; k
    sll   t3, t2, 3
    lui   t4, %hi(offs)
    addiu t4, t4, %lo(offs)
    addu  t4, t4, t3
    lwc1  $f0, 0x30(a0)
    lwc1  $f1, 0(t4)
    add.s $f0, $f0, $f1
    swc1  $f0, 0x30(a0)
    lwc1  $f0, 0x34(a0)
    lwc1  $f1, 4(t4)
    add.s $f0, $f0, $f1
    swc1  $f0, 0x34(a0)
    lui   a1, %hi(nameE)
    beqz  s4, setname
    addiu a1, a1, %lo(nameE)
    lui   a1, %hi(nameF)
    addiu a1, a1, %lo(nameF)
setname:
    jal   StrSetC
    addiu a0, a0, 0xc               ; (delay) &dst.name
    lw    t0, 0x18(s6)              ; team members.count
    sw    t0, {SCR + 8:#x}(sp)
    addiu a0, s6, 0x14
    jal   IncUi
    addiu a1, t0, 1
    lw    t0, {SCR + 8:#x}(sp)
    lw    v0, 0x14(s6)
    sll   t0, t0, 2
    addu  v0, v0, t0
    lw    t1, {SCR + 4:#x}(sp)
    sw    t1, 0(v0)                 ; members[count] = IgorId
    lw    t2, {SCR:#x}(sp)
    addiu t2, t2, 1
    sw    t2, {SCR:#x}(sp)
    addiu s2, s2, -1
    bgtz  s2, find
    nop
out:
    j     {g['RESUME']:#x}
    nop
""" + _tail()


def _js_source(emul, fmul):
    g = GAMES["js"]
    SCR, TMP = g["SCR"], g["TMP"]
    return _prologue(g, emul, fmul) + f"""
    addiu a0, sp, {TMP:#x}
    jal   EntryCtor                 ; a live entry to build the copy in
    nop
    lw    t0, {SCR + 8:#x}(sp)      ; source index
    lw    v0, 0xc(s5)
    sll   t9, t0, 4
    sll   t1, t0, 3
    addu  t9, t9, t1
    subu  t9, t9, t0
    sll   t9, t9, 2
    addu  a1, v0, t9
    jal   EntryAssign               ; tmp = source (tmp is outside the array)
    addiu a0, sp, {TMP:#x}
    lw    t0, {SCR:#x}(sp)          ; k
    addiu t0, t0, 1
    sll   t0, t0, 16
    lw    t1, {SCR + 8:#x}(sp)      ; source index
    or    t1, t1, t0                ; IgorId = (k+1)<<16 | source
    sw    t1, {TMP + 4:#x}(sp)
    sw    t1, {SCR + 4:#x}(sp)
    sb    zero, {TMP + 0x58:#x}(sp)
    beqz  s6, pos
    nop
    sb    zero, {TMP + 0x51:#x}(sp)
pos:
    lw    t2, {SCR:#x}(sp)
    sll   t3, t2, 3
    lui   t4, %hi(offs)
    addiu t4, t4, %lo(offs)
    addu  t4, t4, t3
    lwc1  $f0, {TMP + 0x30:#x}(sp)
    lwc1  $f1, 0(t4)
    add.s $f0, $f0, $f1
    swc1  $f0, {TMP + 0x30:#x}(sp)
    lwc1  $f0, {TMP + 0x34:#x}(sp)
    lwc1  $f1, 4(t4)
    add.s $f0, $f0, $f1
    swc1  $f0, {TMP + 0x34:#x}(sp)
    lui   a1, %hi(nameE)
    beqz  s6, setname
    addiu a1, a1, %lo(nameE)
    lui   a1, %hi(nameF)
    addiu a1, a1, %lo(nameF)
setname:
    jal   StrSetC
    addiu a0, sp, {TMP + 0xc:#x}
    addiu a0, s5, 0xc
    jal   ActorPush                 ; actors.push_back(tmp)
    addiu a1, sp, {TMP:#x}
    addiu a0, s4, 0x14
    jal   UiPush                    ; members.push_back(id)
    addiu a1, sp, {SCR + 4:#x}
    addiu a0, sp, {TMP:#x}
    jal   EntryDtor
    li    a1, -1
    lw    t2, {SCR:#x}(sp)
    addiu t2, t2, 1
    sw    t2, {SCR:#x}(sp)
    addiu s2, s2, -1
    bgtz  s2, find
    nop
out:
    ld    ra, 0x90(sp)              ; the epilogue word the hook replaced
    j     {g['RESUME']:#x}
    nop
""" + _tail()


def _tail():
    s = "offs:\n"
    for dx, dy in OFFS:
        s += f"    .word {dx:#x}\n    .word {dy:#x}\n"
    s += 'nameE: .asciiz "TW"\nnameF: .asciiz "_Reserve"\n'
    return s


GR_DEBRIEF_SRC = """
    beqz  s4, bail                  ; stock test: no soldier
    sltiu at, s3, 6                 ; (delay) row < 6 ?
    beqz  at, bail
    nop
    j     0x340b28
    nop
bail:
    j     0x341208
    nop
"""
GR_RADAR_SRC = """
    lw    v1, 0x180(sp)
    lw    a0, 0x448(v1)             ; contacts so far
    slti  at, a0, 30                ; the array holds 30
    beqz  at, skip
    nop
    j     0x2cf4b4
    nop
skip:
    j     0x2cf510
    nop
"""
JS_RADAR_SRC = """
    lw    v1, 0x5e8(s2)
    slti  at, v1, 30
    beqz  at, skip
    nop
    j     0x29e2a0
    nop
skip:
    j     0x29e2dc
    nop
"""


# ---- the squad pass ------------------------------------------------------
# The players' squad is never parsed from a file: the single-player platoon
# screen (GR SPPlatoonScreen::CreateTOEFile 0x00307180, JS 0x002C7B20) and the
# split-screen chooser (GR 0x003358A0, JS 0x002E1FE0) build IkeDataMgr's
# TOEFile in memory and end with the same IIkeStateMgr call (``jalr t9``). That
# call becomes ``jal squad``: the routine makes it, keeps its v0, and copies the
# AI members (Owner -1) of every team of the built squad, by the rules above.
# grsquad's roster additions run earlier in the same functions.
TOE = {
    "gr": dict(
        CAVE=0x00417650, CAVE_END=0x00417998,      # rest of the total-war block
        HOOKS={0x00307974: "SPPlatoonScreen::CreateTOEFile",
               0x00336308: "PS2MultiplayerSplitScreenChooseSoldier::CreateTOEFile"},
        HOOK_STOCK=0x0320F809,                       # jalr t9 (delay slot: nop)
        # both builders keep the TOEFile at 0xac(sp); SetupFileData = TOEFile+0x1c.
        # (the split-screen builder reuses s2 for a platoon entry, so no register)
        SETUP="    lw    t0, {AC}(sp)\n    lw    s5, 0x1c(t0)\n",
        SYMS={"IncActors": 0x001EDC70, "CopyEntry": 0x001E5E70,
              "StrSetC": 0x0053EA60, "IncUi": 0x001343F0},
    ),
    "js": dict(
        CAVE=0x0017F990, CAVE_END=0x0017FFF8,      # twins of GR sceRemove..sceDopen, unreferenced
        HOOKS={0x002C7EA8: "SP platoon screen CreateTOEFile twin (0x2C7B20)",
               0x002E23F4: "split-screen chooser CreateTOEFile twin (0x2E1FE0)"},
        HOOK_STOCK=0x0320F809,                       # jalr t9 (delay slot: move a0,v0)
        SETUP="    move  s5, s3\n",                 # both keep SetupFileData in s3
        SYMS={"IncActors": 0x001EAD40, "CopyEntry": 0x001D9240,
              "StrSetC": 0x003FF4A0, "IncUi": 0x001EAE80},
    ),
}
FRAME = 0x90   # 0x00 s0..s5 (sq), 0x60 ra, 0x68 v0, 0x70 k, 0x74 cursor, 0x78 src,
               # 0x7c new, 0x80 dst, 0x84 count, 0x88 copies per soldier


def _squad_source(game, fmul):
    t = TOE[game]
    setup = t["SETUP"].replace("{AC}", "%#x" % (FRAME + 0xAC))
    return f"""
squad:
    addiu sp, sp, -{FRAME:#x}
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s2, 0x20(sp)
    sq    s3, 0x30(sp)
    sq    s4, 0x40(sp)
    sq    s5, 0x50(sp)
    sd    ra, 0x60(sp)
    jalr  t9                        ; the call the hook replaced (a0 from its delay slot)
    nop
    sd    v0, 0x68(sp)
{setup}    li    t3, {fmul}                ; allies multiplier
    addiu t3, t3, -1
    blez  t3, done
    sw    t3, 0x88(sp)              ; (delay) copies per AI soldier
    lw    s0, 0x60(s5)              ; teams.count (never grows here)
    move  s1, zero
team:
    slt   t0, s1, s0
    beqz  t0, done
    nop
    lw    t0, 0x5c(s5)              ; teams.data, stride 0x24
    sll   t1, s1, 3
    addu  t1, t1, s1
    sll   t1, t1, 2
    addu  s2, t0, t1                ; this team
    lw    s3, 0x18(s2)              ; n = members before any copy
    move  t4, zero                  ; AI members
    move  t5, zero
count:
    slt   t0, t5, s3
    beqz  t0, counted
    nop
    lw    t0, 0x14(s2)
    sll   t1, t5, 2
    addu  t0, t0, t1
    jal   findact
    lw    a0, 0(t0)                 ; (delay) member id
    addiu t5, t5, 1
    beqz  v0, count
    nop
    lw    t0, 0x54(v0)              ; Owner
    addiu t0, t0, 1
    bnez  t0, count                 ; a player's soldier
    nop
    b     count
    addiu t4, t4, 1
counted:
    blez  t4, next
    move  s4, zero                  ; (delay) add = AI * (MUL-1)
    lw    t3, 0x88(sp)
mul:
    addu  s4, s4, t4
    addiu t3, t3, -1
    bgtz  t3, mul
    nop
    li    t9, 6                     ; FireTeamAI::Update ignores teams of 7+
    subu  t9, t9, s3
    blez  t9, next
    slt   t8, t9, s4                ; (delay)
    beqz  t8, go
    nop
    move  s4, t9
go:
    sw    zero, 0x70(sp)            ; k
    sw    zero, 0x74(sp)            ; cursor over the first n members
clone:
    blez  s4, next
    nop
pick:
    lw    t0, 0x74(sp)
    lw    t1, 0x14(s2)              ; members.data: re-read, it grows below
    sll   t2, t0, 2
    addu  t1, t1, t2
    lw    a0, 0(t1)
    addiu t0, t0, 1
    slt   t2, t0, s3
    bnez  t2, nowrap
    nop
    move  t0, zero
nowrap:
    jal   findact
    sw    t0, 0x74(sp)              ; (delay)
    beqz  v0, pick
    nop
    lw    t0, 0x54(v0)
    addiu t0, t0, 1
    bnez  t0, pick                  ; never copy a player's soldier
    nop
    sw    v1, 0x78(sp)              ; source index
    lw    t0, 0x10(s5)              ; new index = actors.count
    sw    t0, 0x7c(sp)
    addiu a0, s5, 0xc
    jal   IncActors
    addiu a1, t0, 1
    lw    v0, 0xc(s5)               ; actors.data after the move
    lw    t0, 0x7c(sp)
    sll   t8, t0, 4
    sll   t9, t0, 3
    addu  t8, t8, t9
    subu  t8, t8, t0
    sll   t8, t8, 2
    addu  t8, v0, t8                ; dst
    lw    t0, 0x78(sp)
    sll   t9, t0, 4
    sll   t1, t0, 3
    addu  t9, t9, t1
    subu  t9, t9, t0
    sll   t9, t9, 2
    addu  a1, v0, t9                ; src
    sw    t8, 0x80(sp)
    jal   CopyEntry
    move  a0, t8
    lw    a0, 0x80(sp)
    lw    t0, 0x7c(sp)
    lui   t1, 1
    addu  t1, t1, t0
    sw    t1, 4(a0)                 ; IgorId 0x10000 + index
    sb    zero, 0x58(a0)            ; not a platoon leader
    sb    zero, 0x51(a0)            ; not a campaign soldier
    lw    t2, 0x70(sp)
    sll   t3, t2, 3
    lui   t4, %hi(soffs)
    addiu t4, t4, %lo(soffs)
    addu  t4, t4, t3
    lwc1  $f0, 0x30(a0)
    lwc1  $f1, 0(t4)
    add.s $f0, $f0, $f1
    swc1  $f0, 0x30(a0)
    lwc1  $f0, 0x34(a0)
    lwc1  $f1, 4(t4)
    add.s $f0, $f0, $f1
    swc1  $f0, 0x34(a0)
    lui   a1, %hi(sname)
    addiu a1, a1, %lo(sname)
    jal   StrSetC
    addiu a0, a0, 0xc               ; (delay) &dst.name
    lw    t0, 0x18(s2)
    sw    t0, 0x84(sp)
    addiu a0, s2, 0x14
    jal   IncUi
    addiu a1, t0, 1
    lw    t0, 0x84(sp)
    lw    v0, 0x14(s2)
    sll   t0, t0, 2
    addu  v0, v0, t0
    lw    t1, 0x7c(sp)
    lui   t2, 1
    addu  t1, t1, t2
    sw    t1, 0(v0)                 ; members[count] = IgorId
    lw    t2, 0x70(sp)
    addiu t2, t2, 1
    sw    t2, 0x70(sp)
    b     clone
    addiu s4, s4, -1
next:
    b     team
    addiu s1, s1, 1
done:
    ld    v0, 0x68(sp)              ; the replaced call's result
    ld    ra, 0x60(sp)
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    lq    s3, 0x30(sp)
    lq    s4, 0x40(sp)
    lq    s5, 0x50(sp)
    jr    ra
    addiu sp, sp, {FRAME:#x}
findact:                            ; a0 = IgorId -> v0 = &actor (0 = none), v1 = index
    lw    t6, 0x10(s5)
    lw    t7, 0xc(s5)
    move  v1, zero
fa:
    slt   t8, v1, t6
    beqz  t8, fanone
    nop
    lw    t8, 4(t7)
    beq   t8, a0, fahit
    nop
    addiu v1, v1, 1
    b     fa
    addiu t7, t7, 0x5c
fanone:
    jr    ra
    move  v0, zero
fahit:
    jr    ra
    move  v0, t7
soffs:
""" + "".join(f"    .word {dx:#x}\n    .word {dy:#x}\n" for dx, dy in OFFS) + 'sname: .asciiz "_Reserve"\n'


# ---- Jungle Storm's debrief clamp ------------------------------------------
# AfterAction::SetIndividualData's twin (0x002E6830) takes the row unchecked,
# like Ghost Recon's; its row arrays hold 6. Split screen's debrief
# (MPPCAfterAction_PS2) wraps its row at 2 in both games, so only single
# player needs this. The delay slot at 0x002E6864 (swc1 f20) is kept.
JS_DEBRIEF = dict(HOOK=0x002E6860, HOOK_STOCK=0x1280013E, CAVE=0x0019B888)
JS_DEBRIEF_SRC = """
    beqz  s4, bail                  ; stock test: no soldier
    sltiu at, s3, 6                 ; (delay) row < 6 ?
    beqz  at, bail
    nop
    j     0x2e6868
    nop
bail:
    j     0x2e6d5c
    nop
"""
JS_DEBRIEF_STOCK = (0x27BDFFE0, 0xFFBF0010, 0x0C066DF2, 0x00000000,
                    0x10400003, 0x3C030057, 0x10000006, 0x906268EA)

# ---- Jungle Storm's quick order (R2) with copied allies ----------------------
# The quick order goes to "the other fireteam", and Jungle Storm decides which
# that is by comparing the player's soldier with members 0, 1 and 2 of Alpha
# (the handler at JS 0x00285DA0, IkeRulesMgr::GetTeamMember three times). A
# copy is member 3 or later, so playing a copy in Alpha sent every order to
# your own team. It now reads the soldier's own fireteam index (SimHuman
# +0x448; s4 holds the SimHuman at +0x1B0) -- Alpha orders Bravo, anyone else
# orders Alpha, as before for the originals. Found in a save state where every
# original was dead and the player was a copy.
JS_QUICK_ORDER = (
    (0x002861B0, 0x12130005, "lw    s0, 0x298(s4)"),       # beq s0,s3 -> the player's fireteam
    (0x002861B4, 0x00000000, "b     0x2861d4"),            # its delay slot -> skip the id tests
    (0x002861B8, 0x12120003, "sltiu s0, s0, 1"),           # (delay) Alpha -> order Bravo
)
JS_QUICK_ORDER_STOCK = {va: st for va, st, _src in JS_QUICK_ORDER}

# ---- the heap in PCSX2's 128 MB mode -----------------------------------------
# The game heap is one malloc'd block ending at a hard-coded 0x01F98000. These
# put it at 0x02000000 with 0x05F00000 bytes; the kernel stack sits at the top of
# 128 MB. Without the emulator's 128 MB setting the first allocation fails.
HEAP = {
    "gr": ((0x001019E4, 0x0C100B5C, 0x3C020200),    # jal malloc -> lui v0, 0x200
           (0x003F968C, 0x00623023, 0x3C0605F0)),   # subu a2 -> lui a2, 0x5f0
    "js": ((0x00102AC4, 0x0C05A5E2, 0x3C020200),
           (0x0015B7D0, 0x00629023, 0x3C1205F0)),   # subu s2 -> lui s2, 0x5f0
}

# ---- the height check -------------------------------------------------------
# IkeSimulationMgr::AdjustHeightsOverFloors drops each placed actor onto a floor
# (SetHeightAtPoint, vtable +0x30, or +0x34 with the actor's planning level:
# both return 1 = found / 0 = none; on none the +0x34 form sets z = 0) and adds
# 0.01. The word after the lookup becomes ``jal height``. For a copy (id >= 0x10000,
# low 16 bits = its original's index, which the loop has already placed): no
# floor, or a floor more than 1 m from the original's, and the copy takes the
# original's x, y, z. Everyone else is untouched. The only caller passes the
# mission's SetupFileData (s0); actors are 0x5C bytes at +0xC.
HEIGHT = {
    "gr": dict(HOOK=0x0038C034, HOOK_STOCK=0x3C023C23,   # lui v0,0x3c23; slot ori v0,v0,0xd70a runs
               CAVE=0x00421DA0),                          # sceMcSetFileInfo, unreferenced
    "js": dict(HOOK=0x00369AD4, HOOK_STOCK=0xE6800038,   # swc1 f0,0x38(s4); slot addiu s3,s3,1 runs
               CAVE=0x0017FC84),                          # after the squad pass, same unreferenced block
}
_HEIGHT_CHECK = """
    lw    t1, 4(s4)                 ; IgorId
    srl   t2, t1, 16
    beqz  t2, keep                  ; not a copy
    andi  t3, t1, 0xffff            ; (delay) its original's index
    lw    t4, 0xc(s0)               ; actors.data
    sll   t5, t3, 4                 ; *0x5c
    sll   t6, t3, 3
    addu  t5, t5, t6
    subu  t5, t5, t3
    sll   t5, t5, 2
    beqz  t0, revert                ; no floor under the copy
    addu  t5, t4, t5                ; (delay) the original's entry
    lwc1  $f2, 0x38(t5)             ; the original's final z
    lwc1  $f3, 0x38(s4)             ; the copy's floor
    sub.s $f2, $f2, $f3
    lui   t6, 0x3f80                ; 1.0 m
    mtc1  t6, $f3
    c.lt.s $f3, $f2                 ; original more than 1 m above
    bc1t  revert
    neg.s $f2, $f2
    c.lt.s $f3, $f2                 ; or more than 1 m below
    bc1t  revert
    nop
    b     keep
    nop
"""
HEIGHT_SRC = {
    # Ghost Recon: v0 = found | 0xd70a (the hook's slot ran); f1 = the found z.
    "gr": """
height:
    andi  t0, v0, 1                 ; found
""" + _HEIGHT_CHECK + """
keep:
    lui   v0, 0x3c23                ; the words the hook took: v0 = 0.01f
    jr    ra                        ; back to 0x38C03C: z = f1 + 0.01
    ori   v0, v0, 0xd70a
revert:
    lw    t6, 0x30(t5)              ; the original's x, y, z
    sw    t6, 0x30(s4)
    lw    t6, 0x34(t5)
    sw    t6, 0x34(s4)
    lw    t6, 0x38(t5)
    j     0x38c04c                  ; past the loop's own store
    sw    t6, 0x38(s4)
""",
    # Jungle Storm: v0 = found; f0 = floor + 0.01, not yet stored.
    "js": """
height:
    swc1  $f0, 0x38(s4)             ; the word the hook took
    move  t0, v0                    ; found
""" + _HEIGHT_CHECK + """
keep:
    jr    ra                        ; back to 0x369ADC
    nop
revert:
    lw    t6, 0x30(t5)              ; the original's x, y, z
    sw    t6, 0x30(s4)
    lw    t6, 0x34(t5)
    sw    t6, 0x34(s4)
    lw    t6, 0x38(t5)
    b     keep
    sw    t6, 0x38(s4)
""",
}
_GR_HEIGHT_STOCK_HEX = (   # sceMcSetFileInfo, 0x00421DA0..
    "27BDFF60 FFB50060 FFB40050 0080A82D 3C140057 FFB60070 FFB30040 00E0B02D "
    "FFB20030 00A0982D FFB10020 00C0902D 8E84F014 0100882D FFBF0090 FFB70080 "
    "0C1046CC FFB00010 04410003 3C02005F 10000056 2402FF38 24570B40 8EE30024 "
    "14600005 00000000 0C1046C0 8E84F014 1000004E 2402FF9C 12400004 00000000 "
    "82420000 14400005 3C02005F 0C1046C0")

_GR_CAVE_STOCK_HEX = (   # sceAddDrv..sceGetstat, 0x00417330..0x00417998
    "27BDFF70 FFB10050 0080882D FFB30070 FFB00040 2404000F FFBF0080 3C13005F"
    "FFB20060 0C10563E 2670E100 3C030057 8C62E1C0 54400004 AE11000C 0C10567E"
    "00000000 AE11000C 24020001 AFA20014 27A40010 AFA00018 0C1046B8 AFA00024"
    "0040882D 27A30030 3C02005F AE71E100 2452ED40 3C04005F 24020004 AE030004"
    "AE020008 2484F3C0 0200382D 2405000F AFA00000 0000302D 24080010 0240482D"
    "240A0004 0C10531C 0000582D 04410007 3C022000 0C1046BC 0220202D 0C10564A"
    "00000000 1000000F 2402FFFF 02421025 0C10564A 8C500000 16000005 00000000"
    "0C1046BC 0220202D 10000006 2402FFFF 0C1046C8 0220202D 0C1046BC 0220202D"
    "8FA20030 DFBF0080 DFB30070 DFB20060 DFB10050 DFB00040 03E00008 27BD0090"
    "27BDFFF0 FFBF0000 0C105B4A 24050010 DFBF0000 03E00008 27BD0010 00000000"
    "27BDFFC0 FFB00000 0080802D FFBF0030 FFB20020 24040009 0C10563E FFB10010"
    "3C030057 8C62E1C0 14400003 00000000 0C10567E 00000000 0C10564A 00000000"
    "0C1054FC 00000000 0040902D 16400003 0200202D 10000016 2402FFED 0C105B4A"
    "24050009 0040882D 06210006 3C100057 0C1046C8 8E04E1C8 AE400004 10000009"
    "8E04E1C8 0C1046C8 8E04E1C8 3C03005F AE510000 2463F1C0 8E04E1C8 02431823"
    "00038903 0C1046C0 00000000 0220102D DFBF0030 DFB20020 DFB10010 DFB00000"
    "03E00008 27BD0040 27BDFF60 FFB40080 FFB20060 3C14005F FFB00040 2692E100"
    "FFBF0090 FFB30070 0C10551E FFB10050 0040802D 0C10563E 2404000A 3C030057"
    "8C62E1C0 14400005 00000000 0C10564A 00000000 1000003E 2402FFFF 12000004"
    "00000000 8E020004 54400005 8E030000 0C10564A 00000000 10000035 2402FFF7"
    "24020001 AFA20014 27A40010 AE43000C AFA00018 0C1046B8 AFA00024 0040882D"
    "27A30030 3C02005F AE91E100 2453ED40 3C04005F 24020004 AE430004 AE420008"
    "2484F3C0 0240382D 2405000A AFA00000 0000302D 24080014 0260482D 240A0004"
    "0C10531C 0000582D 04430007 AE000004 0C1046BC 0220202D 0C10564A 00000000"
    "10000013 2402FFF5 3C022000 02621025 0C10564A 8C500000 16000005 00000000"
    "0C1046BC 0220202D 10000009 2402FFF5 0C1046C8 0220202D 0C1046BC 0220202D"
    "8FA20030 2403FFFF 0062182A 0003100B DFBF0090 DFB40080 DFB30070 DFB20060"
    "DFB10050 DFB00040 03E00008 27BD00A0 27BDFF70 FFB10050 FFB30070 00A0882D"
    "FFB20060 3C13005F FFB00040 FFBF0080 0C10551E 2672E100 0040802D 0C10563E"
    "2404000B 3C020057 8C43E1C0 14600005 00000000 0C10564A 00000000 1000003B"
    "2402FFFF 12000004 00000000 8E020004 54400005 8E020000 0C10564A 00000000"
    "10000032 2402FFF7 24030001 AE510010 27A40010 AE42000C AFA30014 AFA00018"
    "0C1046B8 AFA00024 0040882D 27A30030 3C02005F AE71E100 2450ED40 3C04005F"
    "24020004 AE430004 AE420008 2484F3C0 0240382D 2405000B AFA00000 0000302D"
    "24080020 0200482D 240A0004 0C10531C 0000582D 04410007 3C022000 0C1046C8"
    "0220202D 0C10564A 00000000 1000000F 2402FFF5 02021025 0C10564A 8C500000"
    "16000005 00000000 0C1046BC 0220202D 10000006 2402FFF5 0C1046C8 0220202D"
    "0C1046BC 0220202D 8FA20030 DFBF0080 DFB30070 DFB20060 DFB10050 DFB00040"
    "03E00008 27BD0090 27BDFF30 FFB10050 FFB600A0 0080882D FFB700B0 00A0B02D"
    "FFB20060 2404000C FFBF00C0 3C17005F FFB50090 26F2E100 FFB40080 FFB30070"
    "0C10563E FFB00040 3C020057 8C43E1C0 54600004 92220000 0C10567E 00000000"
    "92220000 0000802D 0040182D 1060000E A2420010 27B30030 3C15005F 3C14005F"
    "26100001 2A020400 1040000A 02301021 02502021 90430000 1460FFF9 A0830010"
    "10000005 24020400 27B30030 3C15005F 3C14005F 24020400 56020004 AE56000C"
    "A240040F 241003FF AE56000C 24020001 AFA20014 27A40010 AFA00018 2694ED40"
    "0C1046B8 AFA00024 0040882D AE530004 24020004 AE510000 AE420008 26A4F3C0"
    "26E7E100 26080011 AFA00000 2405000C 0000302D 0280482D 240A0004 0C10531C"
    "0000582D 04410007 3C022000 0C1046BC 0220202D 0C10564A 00000000 1000000F"
    "2402FFF5 02821025 0C10564A 8C500000 16000005 00000000 0C1046BC 0220202D"
    "10000006 2402FFF5 0C1046C8 0220202D 0C1046BC 0220202D 8FA20030 DFBF00C0"
    "DFB700B0 DFB600A0 DFB50090 DFB40080 DFB30070 DFB20060 DFB10050 DFB00040"
    "03E00008 27BD00D0"
)
_JS_CAVE_STOCK_HEX = (   # scePad info twins, 0x00196078..0x00196328
    "0080302D 24030070 2404001C 70C31818 00A42018 27BDFFF0 3C020062 FFBF0000"
    "2442DD50 00832021 00441021 8C430010 10600007 0000102D 0C0657C4 00C0202D"
    "3C030003 3463FFFF 00431026 2C420001 DFBF0000 03E00008 27BD0010 00000000"
    "0080302D 24030070 2404001C 70C31818 00A42018 27BDFFF0 3C020062 FFBF0000"
    "2442DD50 00832021 00441021 8C430010 14600003 00C0202D 10000003 0000102D"
    "0C0657F2 24060FFF DFBF0000 03E00008 27BD0010 00000000 0080302D 24030070"
    "2404001C 70C31818 00A42018 27BDFFF0 3C020062 FFBF0000 2442DD50 00832021"
    "00441021 8C430010 14600003 00C0202D 10000003 0000102D 0C0657F2 0000302D"
    "DFBF0000 03E00008 27BD0010 00000000 27BDFFB0 3C020062 FFB20030 2403000B"
    "FFB00010 0080902D 2450DF40 FFB10020 FFBF0040 00A0882D AE120004 3C040062"
    "AC43DF40 2484DD00 AE110008 24080080 68C20007 6CC20000 88C3000B 98C30008"
    "B2020013 B602000C AA030017 BA030014 0200482D 24050001 AFA00000 0000302D"
    "0200382D 240A0080 0C05F5AA 0000582D 04430003 8E03001C 1000000A 0000102D"
    "24020001 14620007 0060102D 0240202D 0220282D 0C065616 24060002 8E03001C"
    "0060102D DFBF0040 DFB20030 DFB10020 DFB00010 03E00008 27BD0050 00000000"
    "27BDFFD0 3C020062 FFB00010 2403000C 2450DF40 3C040062 FFBF0020 2484DD00"
    "AC43DF40 24050001 AFA00000 0000302D 0200382D 24080080 0200482D 240A0080"
    "0C05F5AA 0000582D 04430002 8E02000C 0000102D DFBF0020 DFB00010 03E00008"
    "27BD0030 00000000 27BDFFD0 3C020062 FFB00010 2406000D 2450DF40 FFBF0020"
    "AE040004 3C030062 AC46DF40 24050001 2464DD00 AFA00000 0000302D 0200382D"
    "24080080 0200482D 240A0080 0C05F5AA 0000582D 04430002 8E02000C 0000102D"
    "DFBF0020 DFB00010 03E00008 27BD0030"
)
_JS_RADAR_STOCK_HEX = (  # scePad info twins, 0x00195910..0x00195B84
    "2C820004 10400008 3C020058 3C020057 00041880 24426878 00A0202D 00621821"
    "0805B71A 8C650000 90432F30 03E00008 A0A30000 00000000 0080402D 24030070"
    "2404001C 71031818 00A42018 27BDFFD0 3C020062 FFB10010 FFB00000 2442DD50"
    "FFBF0020 00C0882D 00832021 00441021 8C430010 10600032 00E0802D 0C065564"
    "0100202D 0040202D 90850072 24020001 14A2002C 0000102D 90820064 2C420002"
    "14400028 0000102D 9083006A 0223102A 10400023 2402FFFF 16220003 24020002"
    "10000020 0060102D 12020011 2A020003 10400005 24020003 12050009 0000102D"
    "10000019 DFBF0020 1202000D 24020004 1202000F 0000102D 10000013 DFBF0020"
    "00111880 00831821 1000000E 90620030 00111880 00831821 1000000A 90620031"
    "00111880 00831821 10000006 90620032 00111880 00831821 10000002 90620033"
    "0000102D DFBF0020 DFB10010 DFB00000 03E00008 27BD0030 0080402D 24030070"
    "2404001C 71031818 00A42018 27BDFFD0 3C020062 FFB10010 FFB00000 2442DD50"
    "FFBF0020 00C0882D 00832021 00441021 8C430010 10600031 00E0802D 0C065564"
    "0100202D 0040202D 90830072 24020001 1462002B 0000102D 90820064 2C420002"
    "14400027 0000102D 2405FFFF 16250003 9082006B 10000023 DFBF0020 0222102A"
    "5040001F 0000102D 52000011 00111880 1E000005 00000000 12050009 0000102D"
    "10000018 DFBF0020 1203000C 24020002 1202000E 0000102D 10000012 DFBF0020"
    "00111880 00831821 1000000D 90620040 00831821 1000000A 90620041 00111880"
    "00831821 10000006 90620042 00111880 00831821 10000002 90620043 0000102D"
    "DFBF0020 DFB10010 DFB00000 03E00008 27BD0030"
)
_JS_SQUAD_STOCK_HEX = (  # sceRemove..sceDopen twins, 0x0017F990..0x0017FFF8
    "27BDFFF0 FFBF0000 0C05FDFA 24050006 DFBF0000 03E00008 27BD0010 00000000"
    "27BDFF30 FFB10050 FFB600A0 0080882D FFB700B0 00A0B02D FFB20060 24040007"
    "FFBF00C0 3C170061 FFB50090 26F27000 FFB40080 FFB30070 0C05F8CC FFB00040"
    "3C020057 8C434FEC 54600004 92220000 0C05F918 00000000 92220000 0000802D"
    "00021E00 10600011 A2420010 27B30030 3C150062 3C140061 26100001 00000000"
    "2A020400 1040000C 02301021 02502021 90430000 A0830010 00031E00 5460FFF8"
    "26100001 10000005 24020400 27B30030 3C150062 3C140061 24020400 56020004"
    "AE56000C A240040F 241003FF AE56000C 24020001 AFA20014 27A40010 AFA00018"
    "26947C40 0C05E8B8 AFA00024 0040882D AE530004 24020004 AE510000 AE420008"
    "26A48700 26E77000 26080011 AFA00000 24050007 0000302D 0280482D 240A0004"
    "0C05F5AA 0000582D 04410007 3C022000 0C05E8BC 0220202D 0C05F8D8 00000000"
    "1000000F 2402FFF5 02821025 0C05F8D8 8C500000 16000005 00000000 0C05E8BC"
    "0220202D 10000006 2402FFF5 0C05E8C8 0220202D 0C05E8BC 0220202D 8FA20030"
    "DFBF00C0 DFB700B0 DFB600A0 DFB50090 DFB40080 DFB30070 DFB20060 DFB10050"
    "DFB00040 03E00008 27BD00D0 00000000 27BDFFF0 FFBF0000 0C05FDFA 24050008"
    "DFBF0000 03E00008 27BD0010 00000000 27BDFF30 FFB00040 FFB600A0 0080802D"
    "FFB20060 00C0B02D FFB10050 00A0902D FFB700B0 00E0882D FFB30070 2404000E"
    "FFBF00C0 3C170061 FFB50090 26F37000 0C05F8CC FFB40080 3C020057 8C434FEC"
    "54600004 92020000 0C05F918 00000000 92020000 0000282D 00021E00 1060000F"
    "A262000C 2A270401 24A50001 00000000 28A20400 1040000A 02051021 02652021"
    "90430000 A083000C 00031E00 5460FFF8 24A50001 10000003 24020400 2A270401"
    "24020400 50A20001 A260040B 56400003 92420000 10000014 A260040C 0000282D"
    "00021E00 1060000D A262040C 2666040C 24A50001 00000000 28A20400 10400007"
    "02451021 00C52021 90430000 A0830000 00031E00 5460FFF8 24A50001 24020400"
    "50A20001 A260080B 14E00005 00000000 0C05F8D8 00000000 10000045 2402FFF9"
    "1A20000F 0000282D 2666080C 27B20030 3C150062 3C140061 02C51021 00C52021"
    "90430000 24A50001 00B1102A A0830000 1440FFF9 00000000 10000005 AE710C0C"
    "27B20030 3C150062 3C140061 AE710C0C 24020001 AFA20014 27A40010 AFA00018"
    "26F07000 AFA00024 0C05E8B8 26947C40 0040882D 0200202D 24020004 AE720004"
    "AE620008 24050C10 0C05F324 AE710000 26A48700 0200382D AFA00000 2405000E"
    "0000302D 24080C10 0280482D 240A0004 0C05F5AA 0000582D 04410007 3C022000"
    "0C05E8BC 0220202D 0C05F8D8 00000000 1000000F 2402FFF5 02821025 0C05F8D8"
    "8C500000 16000005 00000000 0C05E8BC 0220202D 10000006 2402FFF5 0C05E8C8"
    "0220202D 0C05E8BC 0220202D 8FA20030 DFBF00C0 DFB700B0 DFB600A0 DFB50090"
    "DFB40080 DFB30070 DFB20060 DFB10050 DFB00040 03E00008 27BD00D0 00000000"
    "27BDFF70 FFB10050 0080882D FFB30070 FFB00040 2404000F FFBF0080 3C130061"
    "FFB20060 0C05F8CC 26707000 3C030057 8C624FEC 54400004 AE11000C 0C05F918"
    "00000000 AE11000C 24020001 AFA20014 27A40010 AFA00018 0C05E8B8 AFA00024"
    "0040882D 27A30030 3C020061 AE717000 24527C40 3C040062 24020004 AE030004"
    "AE020008 24848700 0200382D 2405000F AFA00000 0000302D 24080010 0240482D"
    "240A0004 0C05F5AA 0000582D 04410007 3C022000 0C05E8BC 0220202D 0C05F8D8"
    "00000000 1000000F 2402FFFF 02421025 0C05F8D8 8C500000 16000005 00000000"
    "0C05E8BC 0220202D 10000006 2402FFFF 0C05E8C8 0220202D 0C05E8BC 0220202D"
    "8FA20030 DFBF0080 DFB30070 DFB20060 DFB10050 DFB00040 03E00008 27BD0090"
    "27BDFFF0 FFBF0000 0C05FDFA 24050010 DFBF0000 03E00008 27BD0010 00000000"
    "27BDFFC0 FFB00000 0080802D FFBF0030 FFB20020 24040009 0C05F8CC FFB10010"
    "3C030057 8C624FEC 14400003 00000000 0C05F918 00000000 0C05F8D8 00000000"
    "0C05F78C 00000000 0040902D 16400003 0200202D 10000016 2402FFED 0C05FDFA"
    "24050009 0040882D 06210006 3C100057 0C05E8C8 8E044FF8 AE400004 10000009"
    "8E044FF8 0C05E8C8 8E044FF8 3C030062 AE510000 24638500 8E044FF8 02431823"
    "00038903 0C05E8C0 00000000 0220102D DFBF0030 DFB20020 DFB10010 DFB00000"
    "03E00008 27BD0040"
)


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


GR_STOCK = _stock_words(GAMES["gr"]["CAVE"], _GR_CAVE_STOCK_HEX)
JS_STOCK = _stock_words(GAMES["js"]["CAVE"], _JS_CAVE_STOCK_HEX)
JS_STOCK.update(_stock_words(GAMES["js"]["RADAR_CAVE"], _JS_RADAR_STOCK_HEX))
JS_STOCK.update(_stock_words(TOE["js"]["CAVE"], _JS_SQUAD_STOCK_HEX))
GR_STOCK.update(_stock_words(HEIGHT["gr"]["CAVE"], _GR_HEIGHT_STOCK_HEX))
GR_STOCK[HEIGHT["gr"]["HOOK"]] = HEIGHT["gr"]["HOOK_STOCK"]
JS_STOCK[HEIGHT["js"]["HOOK"]] = HEIGHT["js"]["HOOK_STOCK"]   # its cave is inside the squad block
JS_STOCK.update({JS_DEBRIEF["CAVE"] + 4 * i: w for i, w in enumerate(JS_DEBRIEF_STOCK)})
JS_STOCK[JS_DEBRIEF["HOOK"]] = JS_DEBRIEF["HOOK_STOCK"]
for _st, _g in ((GR_STOCK, "gr"), (JS_STOCK, "js")):
    for _k in ("HOOK", "RADAR_HOOK", "RADAR_HOOK2", "DEBRIEF_HOOK"):
        if _k in GAMES[_g]:
            _st[GAMES[_g][_k]] = GAMES[_g][_k + "_STOCK"]
    for _va in TOE[_g]["HOOKS"]:
        _st[_va] = TOE[_g]["HOOK_STOCK"]
    for _va, _s, _n in HEAP[_g]:
        _st[_va] = _s
GR_STOCK.update(grdrawlist.GR_STOCK)
JS_STOCK.update(grdrawlist.JS_STOCK)
JS_STOCK.update(JS_QUICK_ORDER_STOCK)


def _j(target):
    return 0x08000000 | ((target >> 2) & 0x3FFFFFF)


def _jal(target):
    return 0x0C000000 | ((target >> 2) & 0x3FFFFFF)


def edits(game: str, enemies: int = 1, allies: int = 1, heap: bool = False):
    """(va, value, stock, note). enemies 1-6, allies 1-3; 1 = off."""
    g = GAMES[game]
    st = GR_STOCK if game == "gr" else JS_STOCK
    if not 1 <= enemies <= 6 or not 1 <= allies <= 3:
        raise ValueError("total war: enemies %r allies %r" % (enemies, allies))
    out = []
    if heap:
        out += [(va, n, s, "total war: game heap in PCSX2's 128 MB") for va, s, n in HEAP[game]]
    if enemies == 1 and allies == 1:
        return out
    # the mission pass: enemy teams, and squads read from a file
    src = (_gr_source if game == "gr" else _js_source)(enemies, allies)
    words, _labels = assemble(src, g["CAVE"], g["SYMS"])
    end = g["CAVE"] + 4 * len(words)
    out += [(g["CAVE"] + 4 * i, w, st[g["CAVE"] + 4 * i], "total war: copy each team's soldiers")
            for i, w in enumerate(words)]
    out.append((g["HOOK"], _j(g["CAVE"]), g["HOOK_STOCK"],
                "total war: ProcessTeamMembers ends in the copier"))
    # the debrief and radar clamps
    if game == "gr":
        dw, _ = assemble(GR_DEBRIEF_SRC, end)
        out += [(end + 4 * i, w, st[end + 4 * i], "total war: debrief keeps to 6 rows")
                for i, w in enumerate(dw)]
        out.append((g["DEBRIEF_HOOK"], _j(end), g["DEBRIEF_HOOK_STOCK"],
                    "total war: SetIndividualData checks the row"))
        end += 4 * len(dw)
        rbase, rend = end, g["CAVE_END"]
        rw, _ = assemble(GR_RADAR_SRC, rbase)
        end = rbase + 4 * len(rw)
    else:
        rbase, rend = g["RADAR_CAVE"], g["RADAR_END"]
        rw, _ = assemble(JS_RADAR_SRC, rbase)
        d = JS_DEBRIEF
        dw, _ = assemble(JS_DEBRIEF_SRC, d["CAVE"])
        if len(dw) != len(JS_DEBRIEF_STOCK):
            raise ValueError("JS debrief clamp outgrows its cave")
        out += [(d["CAVE"] + 4 * i, w, st[d["CAVE"] + 4 * i], "total war: debrief keeps to 6 rows")
                for i, w in enumerate(dw)]
        out.append((d["HOOK"], _j(d["CAVE"]), d["HOOK_STOCK"],
                    "total war: SetIndividualData checks the row"))
    if rbase + 4 * len(rw) > rend:
        raise ValueError("total war radar clamp outgrows its cave")
    out += [(rbase + 4 * i, w, st[rbase + 4 * i], "total war: radar keeps to 30 contacts")
            for i, w in enumerate(rw)]
    out.append((g["RADAR_HOOK"], _j(rbase), g["RADAR_HOOK_STOCK"],
                "total war: radar asks before adding a contact"))
    if "RADAR_HOOK2" in g:
        out.append((g["RADAR_HOOK2"], 0x00000000, g["RADAR_HOOK2_STOCK"],
                    "total war: (the jump's delay slot)"))
    # the height check (copies that would stand over no floor)
    h = HEIGHT[game]
    hw, _ = assemble(HEIGHT_SRC[game], h["CAVE"])
    if game == "js" and h["CAVE"] + 4 * len(hw) > TOE["js"]["CAVE_END"]:
        raise ValueError("total war height check outgrows its cave")
    out += [(h["CAVE"] + 4 * i, w, st[h["CAVE"] + 4 * i], "total war: copies stand on a floor")
            for i, w in enumerate(hw)]
    out.append((h["HOOK"], _jal(h["CAVE"]), h["HOOK_STOCK"],
                "total war: AdjustHeightsOverFloors checks each copy's floor"))
    # the draw sort (more than 30 soldiers of one model in view)
    out += grdrawlist.edits(game)
    # the squad pass
    if allies > 1:
        t = TOE[game]
        sw, _ = assemble(_squad_source(game, allies), t["CAVE"], t["SYMS"])
        if (t["CAVE"] + 4 * len(sw) > t["CAVE_END"] or (game == "gr" and t["CAVE"] < end)
                or (game == "js" and t["CAVE"] + 4 * len(sw) > HEIGHT["js"]["CAVE"])):
            raise ValueError("total war squad pass outgrows its cave")
        out += [(t["CAVE"] + 4 * i, w, st[t["CAVE"] + 4 * i], "total war: copy the squad's AI")
                for i, w in enumerate(sw)]
        for va, where in t["HOOKS"].items():
            out.append((va, _jal(t["CAVE"]), t["HOOK_STOCK"],
                        "total war: %s ends in the squad copier" % where))
        if game == "js":
            for va, stock, src in JS_QUICK_ORDER:
                out.append((va, assemble(src, va)[0][0], stock,
                            "total war: the quick order finds the player's fireteam by index"))
    return out


def gr_edits(v: dict):
    return edits("gr", int(v.get("gr_tw_enemies", "1")), int(v.get("gr_tw_allies", "1")),
                 bool(v.get("gr_tw_heap128")))


def js_edits(v: dict):
    return edits("js", int(v.get("js_tw_enemies", "1")), int(v.get("js_tw_allies", "1")),
                 bool(v.get("js_tw_heap128")))


def selftest(gr_elf: bytes, js_elf: bytes):
    """Every stock word against the executables, no address twice. [] = pass."""
    bad = []
    for game, st, elf, d in (("gr", GR_STOCK, gr_elf, 0x80), ("js", JS_STOCK, js_elf, 0x100)):
        for va, w in st.items():
            off = va - 0x100000 + d
            if int.from_bytes(elf[off:off + 4], "little") != w:
                bad.append("%s %08X" % (game, va))
        for e_ in (1, 2, 3, 4, 6):
            for a_ in (1, 2, 3):
                e = edits(game, e_, a_, True)
                if len({va for va, *_ in e}) != len(e):
                    bad.append("%s duplicate VA x%d/x%d" % (game, e_, a_))
                if any(va not in st for va, *_ in e):
                    bad.append("%s VA without a stock word" % game)
    return bad

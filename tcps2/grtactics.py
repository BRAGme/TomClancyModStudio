"""Enemy fire-team tactics in an open fight: Jungle Storm (SLUS-20820).

How a Jungle Storm fire team fights
-----------------------------------

When a fire team learns of an enemy (FireTeamAI::UpdateEnemyList) it puts a
TeamEngagementBehavior on top of its plan. That picks the fight: a
DefendVehicle / DefendZone for escort and zone plans, an Attack- or
DefendStructure when someone is indoors, and for everything else -- nearly
every fight in the jungle -- an OpenFightBehavior (JS Process 0x001B4DD0, the
same code as Ghost Recon's 0x001B87D0). OpenFight hands each member a
soldier behaviour: RunForCover (run to a cover point away from the threat),
CoverArea (hold the spot: crouch, face the threat, peek, fire at what is in
the arc), Suppress (2-5 s of fire at the enemy's spot) or Probe (advance up to
15 m toward the enemy by hops between cover points, pausing 2 s every 5 m to
watch, stopping as soon as he sees someone). Whatever the member sees he
engages himself (EngageThreatBehavior on top, at most 10 s at a time; when
sight is lost he side-steps and looks at the spot -- "clearing LOS").

After the opening, OpenFight re-plans every 2-5 s ("state 3"), member by
member, from the member's distance d to the closest enemy the team knows of
(the position where that enemy was last reported, not where he is now):

  * d < 15 m: suppress him;
  * busy (anything but CoverArea on top) and d <= 50 m: suppress (or, one time
    in d+2, hold a CoverArea) -- hostile soldiers only;
  * otherwise a roll r in [-1, difficulty] (0 Recruit, 1 Veteran, 2 Elite): if
    r = -1 and d < 75 m, Probe toward the enemy; if not, run for cover -- but
    each member runs for cover ONCE per fight (a flag per member,
    OpenFight +0x2C + 4 i), so after that nothing at all happens.

So a member advances on one re-plan in 2 (Recruit), 3 (Veteran) or 4 (Elite),
and never when the enemy is 75 m or more away. Savestates from two co-op
firefights (killlog_host / orders_host, Veteran) show what that does: of the
engaged enemy teams, those 80-210 m from the enemy they knew of had every
member standing with an empty script, their one run for cover used up --
dozens of soldiers who knew where the fight was and did nothing. Ghost
Recon's code is the same apart from the numbers (probe only under 50 m; Jungle
Storm raised it to 75 m and pooled the probes).

What this changes (hostile soldiers only)
-----------------------------------------

One hook: OpenFight's state-3 roll, ``jal RSRandom::Int`` at 0x001B56D0. For a
soldier who is not hostile (SimHuman::IsEnemy's own test, SimHuman +0x458 ->
+0xB7 -- your AI team-mates run the same code) the routine makes exactly the
stock roll and returns to the stock compare. For a hostile soldier:

  * js_ai_advance ("more" / "aggressive"): the roll becomes [-2, difficulty] /
    [-3, difficulty], so he advances on 2 re-plans in 3 / 3 in 4 (Recruit),
    1 in 2 / 3 in 5 (Veteran), 2 in 5 / 1 in 2 (Elite) instead of 1 in 2 / 3
    / 4, and the range becomes 150 / 300 m instead of 75: teams that know
    where the fight is close in on it, 15 m per probe, by the game's own
    bounding (cover-point hops where there are cover points, a 2 s pause every
    5 m), and stop to fight as soon as they see someone. "stock" keeps both.
  * whenever the routine is on: no second probe is put on top of one he is
    still carrying out (stock stacks them -- nine deep in one savestate, each
    new one searching cover points again); the next re-plan after it ends
    gives him a fresh one toward the newest report.
  * js_ai_flank: the probe aims 8 m to the side of the enemy's reported
    position, perpendicular to the soldier's line of approach -- members with
    an even index one side, odd the other, so pairs come at you from both
    sides and bigger teams spread across your front; from 30 m that is a 15
    degree approach, from 15 m 28 degrees. Only where there is ground there:
    Jungle Storm's walkable floor is a network of trails and clearings
    (RSSimScene::FindLevel, JS 0x004EB6B0, finds no level for most of the
    jungle between them), so the routine asks FindLevel for the bent point and
    goes straight at the enemy when it has none -- the check LocationBehavior::
    SetLocation itself makes first. In the two co-op fights above, 19 of 47 and 10
    of 27 engaged soldiers had ground on their side (at 15 m: 6 and 8).
  * js_ai_hold_cover: a member whose script is empty and who has already had
    his one run for cover (the stock "nothing happens" case) is given the
    stock CoverArea at his spot facing the enemy (the same block OpenFight
    uses, 0x001B58F4): he crouches, watches the arc, peeks and fires at what
    is in it instead of standing in the open. It lasts until a probe or the
    end of the fight replaces it; it is never stacked on itself.

The advance goes to where the team last had the enemy reported, so an enemy who
loses sight of you comes to find you there (and suppresses the spot when he
gets within 15 m) instead of standing; when the team forgets you (no report
for a while) the engagement ends 20 s later and the team goes back to its
plan, as before.

What it does not do
-------------------

Only fire teams in an open fight: DefendZone / DefendStructure / DefendVehicle
/ AttackStructure fights, Jungle Storm's own "hold the area" team behaviour
(type 0x30, vtable 0x005A3D60, built by the mission scripts: members rotate
between CoverArea spots) and scripted guards (Hold, empty plans) are left as
the mission made them, so a post the mission wants held stays held. It does not
make anyone learn of you sooner (sight, and hearing -- grawareness) or pass
contacts between teams. RunForCover still happens once per member per fight,
with the stock 30 m cover search (0x00583D68, read only by OpenFight -- for
both sides, so not changed here). Probe, RunForCover, CoverArea, Suppress and
EngageThreat are the game's own behaviours, unchanged. No mission data is
edited: plans, MoveROE / CombatROE and alertness stay as the .MIS files say.

Cost: every probe runs ProbeBehavior::GenerateTripPlan (up to 11 cover-point
searches between the soldier and the target) and a flanked one a FindLevel;
"aggressive" makes most engaged enemies do that every few seconds -- watch the
frame rate in big fights. Online co-op: the host runs all AI, so the host's
disc decides; a joiner's disc changes nothing.

The patch
---------

  0x001B56D0  `jal 0x00112A30` (RSRandom::Int, a0 rng 0x00613510, a1 -1,
              a2 difficulty = IkeRulesMgr vt+0x178, GR's GetDifficultyLevel)
              -> `jal tac_roll`. Returns to the stock compare (0x001B56D8)
              with the roll (not hostile: exactly stock; hostile and staying:
              0, the stock run-for-cover-once path), or goes straight into the
              stock probe block (0x001B56F4, `lui at, 0x63`; the probe's target
              is f23/f22/f21) or the stock CoverArea block (0x001B58F4, with at
              = 0x00630000 as that block expects). Both blocks end at the
              loop's next member (0x001B5944), as the stock branches do.

Registers at the site (OpenFight state 3, member loop): s0 HumanAI, s1 member
index, s5 the OpenFight, f20 distance, f23/f22/f21 the target x/y/z. s2 is dead
there (every path after the roll writes it before reading it, and OpenFight's
epilogue restores the caller's), so it carries "hostile" across the RandomInt
call; f22/f23 are bent on purpose for the probe (they are reloaded for the next
member); everything else the routine touches is caller-saved.

Cave: 0x00553A98..0x00553B87 (60 words: lgAudPrepareForReboot's twin and its
padding word -- the second copy of the lgAud library, like grsprintspeed's,
grcamera's, grcooporders' and grcoopctl's caves around it). No jump, branch,
pointer or address formation reaches it from the executable or either overlay
(a lui 0x55 / low-half search at any distance included), and no other option
writes it. The biggest variant fills all 60 words. (The two 16-word comparators
at 0x0052FCD0 / 0x0052FD10 look unreferenced to a 15-instruction lui/addiu scan
but are handed to a sort from 0x0052FDA8 / 0x0052FF44, 21 instructions after
their lui -- not free.)

Verified in the RAM interpreter (scratchpad agent_tactics/emu_tactics.py,
emu_tactics_generic.py, emu_probe.py) on host RAM from two co-op firefights
(killlog_host, orders_host; Veteran) and a single-player save (9C04BFE8.02),
running the game's own OpenFight state-3 re-plan with the roll scripted: stock
leaves the 80-210 m teams idle; with the options they probe toward the last
report inside 150 / 300 m and not beyond; the roll bound is -2 / -3 for hostile
and -1 for everyone else; a not-hostile team's RAM after the re-plan is byte
for byte the unpatched result in every variant and roll; no probe on a probe;
flank offsets exactly 8 m sideways, 0 along, z kept, and straight exactly where
an independent FindLevel finds no ground; hold gives CoverArea (45 degree arc,
no end time) only to idle members whose cover run is used, never twice; each new
probe's first tick (ProbeBehavior::Process) builds a Location with a level,
flanked or not; sp, s0-s7, fp and f20-f30 come back intact in every variant and
roll. Not yet played.

Ghost Recon (SLUS-20613)
------------------------

The same three options (gr_ai_advance, gr_ai_flank, gr_ai_hold_cover). Ghost
Recon's OpenFightBehavior::Process (0x001B87D0) is the code Jungle Storm
inherited, with its own numbers: a soldier probes only under 50 m (Jungle
Storm 75 m), so "stock" keeps 50 m; "more" / "aggressive" are the same 150 /
300 m and [-2 / -3, difficulty] rolls. The hook is the state-3 roll, ``jal
RSRandom::Int`` (0x00113C60) at 0x001B91FC. Ghost Recon's registers differ:
s3 the HumanAI, s2 the member index (s1 = 4 x it, so the run-for-cover flag
is OpenFight + 0x2C + s1), s5 the OpenFight, f23 the distance, f20/f21/f22
the target x/y/z. s0 is the dead register that carries "hostile" (every path
after the roll writes it before reading it). The probe block is 0x001B9224
(new 0x4C, ProbeBehavior, AddElement), the CoverArea block 0x001B9440 (the
45 degree CoverArea at the target); both end at the loop's next member
(0x001B9498). Flank asks RSSimScene::FindLevel (0x00504690, scene pointer
0x006376D0) like Jungle Storm. Ghost Recon's AcceptingOrders passes a HumanAI
whose SimHuman is gone, so the GR routine treats a missing SimHuman as not
hostile (the stock roll). Behaviour type ids (probe 0x14, OpenFight 0x29,
CoverArea 0x13), SimHuman +0x458 -> +0xB7 (IsEnemy) and the script layout are
the same as Jungle Storm's.

Cave: sceMcChdir (0x004219A8..0x00421AF8, 84 words), unreferenced (no jump,
branch, pointer or lui/low-half pair reaches it or the word before it) and
written by no other option at any value.
"""

from __future__ import annotations

import struct

from .grasm import assemble
from . import grcallouts

HOOK, HOOK_STOCK = 0x001B56D0, 0x0C044A8C       # jal RSRandom::Int (delay: move t0, zero)
CAVE, CAVE_END = 0x00553A98, 0x00553B88          # lgAudPrepareForReboot twin + padding, 60 words
FRAG_CAVE, FRAG_CAVE_END = 0x00180728, 0x001808A8  # unused tail after callouts' contact routine
PROBE = 0x001B56F4                               # lui at, 0x63; jal ProbePool ... (stock probe block)
COVER = 0x001B58F4                               # jal CoverAreaPool; lw a0, -0x3908(at) (stock CoverArea block)
RANDINT = 0x00112A30
FRAG_DECIDE = 0x00180160
FRAG_HELPER_CAVE = CAVE
NEXT_MEMBER = 0x001B5944
FLAG_READ, FLAG_READ_STOCK = 0x001B572C, 0x8C63002C  # OpenFight's per-member run-for-cover flag
FLAG_WRITE, FLAG_WRITE_STOCK = 0x001B5768, 0xAE420000

# js_ai_advance: (K, advance range in m) -- a hostile soldier's roll is RSRandom::Int(-K, difficulty)
ADVANCE = {"stock": (1, 75.0), "more": (2, 150.0), "aggressive": (3, 300.0)}
FLANK_OFFSET = 8.0                               # m beside the enemy's position
SCENE, FINDLEVEL = 0x00689E30, 0x004EB6B0        # the scene pointer; RSSimScene::FindLevel(scene, &point)


def _hi(f):
    b = struct.unpack("<I", struct.pack("<f", f))[0]
    assert b & 0xFFFF == 0, f
    return b >> 16


# movz t1, s5, t1 (R5900 special 0x0A; grasm has no movz): an idle soldier's "top behaviour" becomes the
# OpenFight itself, whose type (0x29) is readable and is not a probe
MOVZ_T1_S5_T1 = (21 << 21) | (9 << 16) | (9 << 11) | 0x0A

# The member loop of OpenFight state 3 calls this for its roll (a0 rng, a1 -1, a2 difficulty, a3/t0 0).
# s2 is dead at this point in OpenFight (every path after the roll writes it before reading it; the
# epilogue restores the caller's), so it carries "hostile" across the call.
SRC = """
tac_roll:
    addiu sp, sp, -0x20
    sd    ra, 0x10(sp)
    lw    s2, 0x14(s0)              ; his SimHuman (non-null: AcceptingOrders passed)
    lw    s2, 0x458(s2)
    lbu   s2, 0xb7(s2)              ; SimHuman::IsEnemy's own test: 1 hostile, 0 not
{CHANCE}    beqz  s2, tr_ret                ; not hostile: the stock roll, back to the stock compare
    ld    ra, 0x10(sp)              ; (delay)
    bgez  v0, tr_stay               ; the roll says stay
    lui   t1, {RANGE}               ; (delay)
    mtc1  t1, f0
    lw    t1, 0xc(s0)               ; his script
    c.lt.s f20, f0
    bc1f  tr_stay                   ; too far to advance
    lw    t1, 4(t1)                 ; (delay) its top behaviour, 0 when idle
    .word {MOVZ}                    ; idle: read the OpenFight's own type (0x29) instead
    lw    t1, 4(t1)
    addiu t1, t1, -0x14
    beqz  t1, tr_stay               ; already probing: not a second one on top
{GO}    j     PROBE                     ; the stock probe block, target f23/f22/f21
    addiu sp, sp, 0x20
tr_stay:
{HOLD}    move  v0, zero                  ; the stock path: run for cover once, else nothing
tr_ret:
    jr    ra
    addiu sp, sp, 0x20
"""

# This larger entry lives after callouts' contact routine. The high three bits of each existing
# per-member run-for-cover word count OpenFight replans; bit 11 of member zero reserves the team's
# one pending grenade. The low byte remains the stock boolean, so its stock read/write use byte ops.
SRC_FRAG = """
tac_roll:
    addiu sp, sp, -0x20
    sd    ra, 0x10(sp)
    lw    s2, 0x14(s0)
    lw    s2, 0x458(s2)
    lbu   s2, 0xb7(s2)
    beqz  s2, tr_rng
    nop
    lw    t1, 0xc(s0)
    lw    t1, 4(t1)
    addiu t1, t1, -0x17
    beqz  t1, tr_skip              ; FragLocation is already on top; let it run
    nop
tr_rng:
{CHANCE}    beqz  s2, tr_ret
    nop
    sw    v0, 0xc(sp)
    jal   FRAG_HELPER_CAVE
    nop
    bnez  v0, tr_skip
    nop
    lw    v0, 0xc(sp)
    bgez  v0, tr_stay
    lui   t1, {RANGE}
    mtc1  t1, f0
    lw    t1, 0xc(s0)
    c.lt.s f20, f0
    bc1f  tr_stay
    lw    t1, 4(t1)
    .word {MOVZ}
    lw    t1, 4(t1)
    addiu t1, t1, -0x14
    beqz  t1, tr_stay
{GO}    j     PROBE
    addiu sp, sp, 0x20
tr_stay:
{HOLD}    move  v0, zero
tr_ret:
    ld    ra, 0x10(sp)
    jr    ra
    addiu sp, sp, 0x20
tr_skip:
    ld    ra, 0x10(sp)
    addiu sp, sp, 0x20
    j     NEXT_MEMBER
    nop
"""

FRAG_HELPER = """
frag_replan:
    addiu sp, sp, -0x20
    sd    ra, 0x10(sp)
    addiu t0, s5, 0x2c             ; member zero carries the fireteam reservation
    lw    t1, 0(t0)
    andi  t2, t1, 0x800
    bnez  t2, fr_done               ; one FragLocation queued for this OpenFight
    move  v0, zero
    sll   t0, s1, 2
    addu  t0, s5, t0
    addiu t0, t0, 0x2c
    lw    t1, 0(t0)
    srl   t2, t1, 8
    andi  t2, t2, 7
    sltiu t3, t2, {AFTER}
    beqz  t3, fr_try_frag
    nop
    addiu t2, t2, 1
    sll   t3, t2, 8
    andi  t1, t1, 0xf8ff
    or    t1, t1, t3
    sw    t1, 0(t0)
    sltiu t3, t2, {AFTER}
    bnez  t3, fr_done
    move  v0, zero
fr_try_frag:
    swc1  f23, 0(sp)
    swc1  f22, 4(sp)
    swc1  f21, 8(sp)
    move  a0, zero
    move  a1, s0
    move  a2, sp
    lui   a3, 0x3f81                ; always ask; grfrag keeps its safety checks
    jal   FRAG_DECIDE
    nop
    beqz  v0, fr_done
    nop
    lw    t0, 0x2c(s5)
    ori   t0, t0, 0x800             ; reserve against simultaneous team members
    sw    t0, 0x2c(s5)
fr_done:
    ld    ra, 0x10(sp)
    jr    ra
    addiu sp, sp, 0x20
"""

def frag_helper(after=4):
    """The re-plan counter's helper; `after` re-plans (1..7, the counter's 3 bits) before it asks for a throw."""
    if not 1 <= after <= 7:
        raise ValueError("re-plans before a throw must be 1..7, not %r" % after)
    words, labels = assemble(FRAG_HELPER.replace("{AFTER}", str(after)), FRAG_HELPER_CAVE,
                             dict(FRAG_DECIDE=FRAG_DECIDE))
    if FRAG_HELPER_CAVE + 4 * len(words) > CAVE_END:
        raise ValueError("grenade helper outgrows its cave (%d of %d words)"
                         % (len(words), (CAVE_END - FRAG_HELPER_CAVE) // 4))
    return words, labels

# the roll: a1 = -1 - s2 * (K - 1); the last instruction fills the jal's delay slot
SRC_CHANCE = {
    1: "    jal   RANDINT\n    nop\n",
    2: "    jal   RANDINT\n    subu  a1, a1, s2              ; (delay) hostile: -2\n",
    3: "    sll   t1, s2, 1\n    jal   RANDINT\n    subu  a1, a1, t1              ; (delay) hostile: -3\n",
}

# js_ai_flank: bend the target (f23 x, f22 y) FLANK_OFFSET m to the side of the approach line -- even member
# indices one side, odd the other -- if the bent point lies on a level (else straight at them, as stock)
SRC_FLANK = """    lwc1  f0, 0x2c(s0)              ; (delay of the beqz above; harmless there) his x
    lwc1  f1, 0x30(s0)              ; his y
    sub.s f0, f23, f0               ; dx
    sub.s f1, f22, f1               ; dy
    lui   t1, {OFFSET}
    sll   t2, s1, 31                ; odd members: the other side
    or    t1, t1, t2
    mtc1  t1, f2
    div.s f2, f2, f20               ; +-offset / distance
    mul.s f1, f1, f2
    mul.s f0, f0, f2
    sub.s f1, f23, f1               ; x - dy * k
    add.s f0, f22, f0               ; y + dx * k
    swc1  f1, 0(sp)
    swc1  f0, 4(sp)
    swc1  f21, 8(sp)
    lui   a0, %hi(SCENE)
    lw    a0, %lo(SCENE)(a0)
    jal   FINDLEVEL                 ; is there ground there at all
    move  a1, sp                    ; (delay)
    beqz  v0, tf_done               ; no: straight at them
    nop
    lwc1  f23, 0(sp)
    lwc1  f22, 4(sp)
tf_done:
"""

# js_ai_hold_cover: nothing to do and his run for cover used up -> the stock CoverArea at his spot
SRC_HOLD = """    lw    t1, 0xc(s0)
    lw    t1, 4(t1)
    bnez  t1, th_no                 ; he is doing something: as stock
    sll   t1, s1, 2                 ; (delay)
    addu  t1, s5, t1
    lw    t1, 0x2c(t1)              ; ran for cover already?
    beqz  t1, th_no                 ; not yet: the stock run for cover
    lui   at, 0x63                  ; (delay) what the CoverArea block expects in at
    j     COVER
    addiu sp, sp, 0x20
th_no:
"""


def routine(advance="stock", flank=False, hold=False, frag_after=0):
    """(words, labels) of the cave for these settings."""
    k, rng = ADVANCE[advance]
    cave = FRAG_CAVE if frag_after else CAVE
    end = FRAG_CAVE_END if frag_after else CAVE_END
    src = (SRC_FRAG if frag_after else SRC).format(
        CHANCE=SRC_CHANCE[k], RANGE=hex(_hi(rng)), MOVZ=hex(MOVZ_T1_S5_T1),
        GO=SRC_FLANK.format(OFFSET=hex(_hi(FLANK_OFFSET))) if flank else "    nop\n",
        HOLD=SRC_HOLD.replace("lw    t1, 0x2c(t1)", "lbu   t1, 0x2c(t1)") if frag_after and hold
             else SRC_HOLD if hold else "")
    words, labels = assemble(src, cave, dict(RANDINT=RANDINT, PROBE=PROBE, COVER=COVER, SCENE=SCENE,
                                             FRAG_DECIDE=FRAG_DECIDE, NEXT_MEMBER=NEXT_MEMBER,
                                             FRAG_HELPER_CAVE=FRAG_HELPER_CAVE, FINDLEVEL=FINDLEVEL))
    if cave + 4 * len(words) > end:
        raise ValueError("tactics routine outgrows its cave (%d of %d words)"
                         % (len(words), (end - cave) // 4))
    return words, labels


_CAVE_STOCK_HEX = (   # 0x00553A98..0x00553B87: lgAudPrepareForReboot twin + one word of padding
    "27BDFFD0 3C020058 FFB00010 2450C614 FFB20020 2412FFFF FFB10018 3C028000"
    "FFBF0028 8E030000 1072002A 3442000A 24040001 0C155366 0000282D 3C04005A"
    "10400007 2484F810 0C05ADDE 00000000 3C028000 1000001F 34420008 00000000"
    "0C05E8C8 8E040000 3C030058 2471C60C 3C040069 8E270000 24841240 24050014"
    "0000302D ACF2000C 24080020 00E0482D 240A0020 0000582D 0C05F5AA AFA00000"
    "14400007 3C04005A 8E220000 8E040000 0C05E8C0 8C500000 10000006 0200102D"
    "0C05ADDE 2484F850 0C05E8C0 8E040000 3C028000 DFB00010 DFB10018 DFB20020"
    "DFBF0028 03E00008 27BD0030 00000000"
)


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


JS_STOCK = _stock_words(CAVE, _CAVE_STOCK_HEX)
JS_STOCK.update({va: grcallouts.JS_STOCK[va] for va in range(FRAG_CAVE, FRAG_CAVE_END, 4)})
JS_STOCK[HOOK] = HOOK_STOCK
JS_STOCK[FLAG_READ] = FLAG_READ_STOCK
JS_STOCK[FLAG_WRITE] = FLAG_WRITE_STOCK
assert len(JS_STOCK) == ((CAVE_END - CAVE) // 4
                         + (FRAG_CAVE_END - FRAG_CAVE) // 4 + 3)


def enabled(v: dict) -> bool:
    return (v.get("js_ai_advance", "stock") != "stock" or bool(v.get("js_ai_flank"))
            or bool(v.get("js_ai_hold_cover") or (v.get("js_enemy_grenades")
                                                    and v.get("js_enemy_frag_replan", True))))


def edits(advance="stock", flank=False, hold=False, frag_after=0):
    """(va, value, stock, note); [] when every setting is stock."""
    if advance == "stock" and not flank and not hold and not frag_after:
        return []
    words, labels = routine(advance, flank, hold, frag_after)
    what = ", ".join(x for x, on in (("advance %s" % advance, advance != "stock"), ("flank", flank),
                                     ("hold cover", hold)) if on)
    cave = FRAG_CAVE if frag_after else CAVE
    out = [(cave + 4 * i, w, JS_STOCK[cave + 4 * i], "enemy tactics: open-fight re-plan (%s)" % what)
           for i, w in enumerate(words)]
    if frag_after:
        helper, _ = frag_helper(frag_after)
        out.extend((FRAG_HELPER_CAVE + 4 * i, w, JS_STOCK[FRAG_HELPER_CAVE + 4 * i],
                    "enemy tactics: count re-plans and ask the grenade routine")
                   for i, w in enumerate(helper))
    out.append((HOOK, assemble("jal %#x" % labels["tac_roll"], HOOK)[0][0], HOOK_STOCK,
                "enemy tactics: OpenFight's re-plan roll goes through the tactics routine"))
    if frag_after:
        out.append((FLAG_READ, 0x9063002C, FLAG_READ_STOCK,
                    "enemy tactics: the re-plan counter preserves the run-for-cover flag"))
        out.append((FLAG_WRITE, 0xA2420000, FLAG_WRITE_STOCK,
                    "enemy tactics: the run-for-cover flag preserves the re-plan counter"))
    return out


def js_edits(v: dict):
    frag_after = (int(v.get("js_enemy_frag_replans", "4"))
                  if v.get("js_enemy_grenades") and v.get("js_enemy_frag_replan", True) else 0)
    return edits(v.get("js_ai_advance", "stock"), bool(v.get("js_ai_flank")),
                 bool(v.get("js_ai_hold_cover")), frag_after)


# ---------------------------------------------------------------------------
# Ghost Recon (SLUS-20613)
# ---------------------------------------------------------------------------

GR_HOOK, GR_HOOK_STOCK = 0x001B91FC, 0x0C044F18   # jal RSRandom::Int (delay: move t0, zero)
GR_CAVE, GR_CAVE_END = 0x004219A8, 0x00421AF8      # sceMcChdir, 84 words
GR_PROBE = 0x001B9224                              # addiu a0, zero, 0x4c; jal new ... (stock probe block)
GR_COVER = 0x001B9440                              # lui at, 0x5e; jal GetPoolCoverAreaBehavior ... (CoverArea)
GR_RANDINT = 0x00113C60
#: gr_ai_advance: (K, advance range in m); Ghost Recon's own range is 50 m
GR_ADVANCE = {"stock": (1, 50.0), "more": (2, 150.0), "aggressive": (3, 300.0)}
GR_SCENE, GR_FINDLEVEL = 0x006376D0, 0x00504690

# OpenFight state 3's member loop calls this for its roll (a0 rng, a1 -1, a2 difficulty, a3/t0 0).
# s3 HumanAI, s2 member index, s1 = 4 x index, s5 OpenFight, f23 distance, f20/f21/f22 target.
# s0 is dead here (every path after the roll writes it before reading it), so it carries "hostile".
GR_SRC = """
tac_roll:
    addiu sp, sp, -0x20
    sd    ra, 0x10(sp)
    lw    s0, 0x14(s3)              ; his SimHuman
    beqz  s0, tr_nh                 ; none: not hostile, the stock roll
    nop
    lw    s0, 0x458(s0)
    lbu   s0, 0xb7(s0)              ; SimHuman::IsEnemy's own test: 1 hostile, 0 not
tr_nh:
{CHANCE}    beqz  s0, tr_ret                ; not hostile: the stock roll, back to the stock compare
    ld    ra, 0x10(sp)              ; (delay)
    bgez  v0, tr_stay               ; the roll says stay
    lui   t1, {RANGE}               ; (delay)
    mtc1  t1, f0
    lw    t1, 0xc(s3)               ; his script
    c.lt.s f23, f0
    bc1f  tr_stay                   ; too far to advance
    lw    t1, 4(t1)                 ; (delay) its top behaviour, 0 when idle
    .word {MOVZ}                    ; idle: read the OpenFight's own type (0x29) instead
    lw    t1, 4(t1)
    addiu t1, t1, -0x14
    beqz  t1, tr_stay               ; already probing: not a second one on top
{GO}    j     PROBE                     ; the stock probe block, target f20/f21/f22
    addiu sp, sp, 0x20
tr_stay:
{HOLD}    move  v0, zero                  ; the stock path: run for cover once, else nothing
tr_ret:
    jr    ra
    addiu sp, sp, 0x20
"""

GR_SRC_CHANCE = {
    1: "    jal   RANDINT\n    nop\n",
    2: "    jal   RANDINT\n    subu  a1, a1, s0              ; (delay) hostile: -2\n",
    3: "    sll   t1, s0, 1\n    jal   RANDINT\n    subu  a1, a1, t1              ; (delay) hostile: -3\n",
}

# gr_ai_flank: bend the target (f20 x, f21 y) FLANK_OFFSET m to the side of the approach line -- even
# member indices one side, odd the other -- if the bent point lies on a level (else straight at them)
GR_SRC_FLANK = """    lwc1  f0, 0x2c(s3)              ; (delay of the beqz above; harmless there) his x
    lwc1  f1, 0x30(s3)              ; his y
    sub.s f0, f20, f0               ; dx
    sub.s f1, f21, f1               ; dy
    lui   t1, {OFFSET}
    sll   t2, s2, 31                ; odd members: the other side
    or    t1, t1, t2
    mtc1  t1, f2
    div.s f2, f2, f23               ; +-offset / distance
    mul.s f1, f1, f2
    mul.s f0, f0, f2
    sub.s f1, f20, f1               ; x - dy * k
    add.s f0, f21, f0               ; y + dx * k
    swc1  f1, 0(sp)
    swc1  f0, 4(sp)
    swc1  f22, 8(sp)
    lui   a0, %hi(SCENE)
    lw    a0, %lo(SCENE)(a0)
    jal   FINDLEVEL                 ; is there ground there at all
    move  a1, sp                    ; (delay)
    beqz  v0, tf_done               ; no: straight at them
    nop
    lwc1  f20, 0(sp)
    lwc1  f21, 4(sp)
tf_done:
"""

# gr_ai_hold_cover: nothing to do and his run for cover used up -> the stock CoverArea at his spot
GR_SRC_HOLD = """    lw    t1, 0xc(s3)
    lw    t1, 4(t1)
    bnez  t1, th_no                 ; he is doing something: as stock
    addu  t1, s5, s1                ; (delay) s1 = 4 x his index
    lw    t1, 0x2c(t1)              ; ran for cover already?
    beqz  t1, th_no                 ; not yet: the stock run for cover
    nop
    j     COVER                     ; the block loads its own at
    addiu sp, sp, 0x20
th_no:
"""


def gr_routine(advance="stock", flank=False, hold=False):
    """(words, labels) of the Ghost Recon cave for these settings."""
    k, rng = GR_ADVANCE[advance]
    src = GR_SRC.format(CHANCE=GR_SRC_CHANCE[k], RANGE=hex(_hi(rng)), MOVZ=hex(MOVZ_T1_S5_T1),
                        GO=GR_SRC_FLANK.format(OFFSET=hex(_hi(FLANK_OFFSET))) if flank else "    nop\n",
                        HOLD=GR_SRC_HOLD if hold else "")
    words, labels = assemble(src, GR_CAVE, dict(RANDINT=GR_RANDINT, PROBE=GR_PROBE, COVER=GR_COVER,
                                                SCENE=GR_SCENE, FINDLEVEL=GR_FINDLEVEL))
    if GR_CAVE + 4 * len(words) > GR_CAVE_END:
        raise ValueError("GR tactics routine outgrows its cave (%d of %d words)"
                         % (len(words), (GR_CAVE_END - GR_CAVE) // 4))
    return words, labels


_GR_CAVE_STOCK_HEX = (   # sceMcChdir, 0x004219A8..0x00421AF8
    "27BDFF60 FFB50060 FFB30040 0080A82D 3C130057 FFB60070 FFB40050 00E0B02D"
    "FFB20030 00A0A02D 8E64F014 00C0902D FFBF0090 FFB70080 FFB10020 0C1046CC"
    "FFB00010 04410003 3C02005F 10000035 2402FF38 24570B40 8EE30024 14600005"
    "00000000 0C1046C0 8E64F014 1000002D 2402FF9C 12400004 00000000 82420000"
    "14400005 3C02005F 0C1046C0 8E64F014 10000024 2402FF2E 3C10005F 24510BF0"
    "26101100 AC550BF0 0240282D AE300010 26240014 AE340004 0C101C9C 240603FF"
    "0200202D A2200413 0C1050E0 24050400 3C09005F 3C0B0042 AFB60000 02E0202D"
    "0220382D 25292100 256B1920 2405000C 24060001 24080414 0C10531C 240A0004"
    "0040802D 16000004 3C030057 2402000C 10000003 AC62F010 0C1046C0 8E64F014"
    "0200102D DFBF0090 DFB70080 DFB60070 DFB50060 DFB40050 DFB30040 DFB20030"
    "DFB10020 DFB00010 03E00008 27BD00A0"
)


GR_STOCK = _stock_words(GR_CAVE, _GR_CAVE_STOCK_HEX)
GR_STOCK[GR_HOOK] = GR_HOOK_STOCK


def gr_enabled(v: dict) -> bool:
    return (v.get("gr_ai_advance", "stock") != "stock" or bool(v.get("gr_ai_flank"))
            or bool(v.get("gr_ai_hold_cover")))


def gr_edits_for(advance="stock", flank=False, hold=False):
    """Ghost Recon (va, value, stock, note); [] when every setting is stock."""
    if advance == "stock" and not flank and not hold:
        return []
    words, labels = gr_routine(advance, flank, hold)
    what = ", ".join(x for x, on in (("advance %s" % advance, advance != "stock"), ("flank", flank),
                                     ("hold cover", hold)) if on)
    out = [(GR_CAVE + 4 * i, w, GR_STOCK[GR_CAVE + 4 * i], "enemy tactics: open-fight re-plan (%s)" % what)
           for i, w in enumerate(words)]
    out.append((GR_HOOK, assemble("jal %#x" % labels["tac_roll"], GR_HOOK)[0][0], GR_HOOK_STOCK,
                "enemy tactics: OpenFight's re-plan roll goes through the tactics routine"))
    return out


def gr_edits(v: dict):
    return gr_edits_for(v.get("gr_ai_advance", "stock"), bool(v.get("gr_ai_flank")),
                        bool(v.get("gr_ai_hold_cover")))


def selftest(gr_elf: bytes, js_elf: bytes):
    """Every stock word against the executables, no address twice, every variant fits. [] = pass."""
    bad = []
    for va, w in JS_STOCK.items():
        off = va - 0x100000 + 0x100
        if int.from_bytes(js_elf[off:off + 4], "little") != w:
            bad.append("js %08X" % va)
    for va, w in GR_STOCK.items():
        off = va - 0x100000 + 0x80
        if int.from_bytes(gr_elf[off:off + 4], "little") != w:
            bad.append("gr %08X" % va)
    for game, fn, st in (("js", edits, JS_STOCK), ("gr", gr_edits_for, GR_STOCK)):
        for adv in ADVANCE:
            for fl in (False, True):
                for ho in (False, True):
                    try:
                        e = fn(adv, fl, ho)
                    except ValueError as ex:
                        bad.append("%s %s/%s/%s: %s" % (game, adv, fl, ho, ex))
                        continue
                    if len({va for va, *_ in e}) != len(e):
                        bad.append("%s duplicate VA" % game)
                    if any(va not in st for va, *_ in e):
                        bad.append("%s VA without a stock word" % game)
    return bad

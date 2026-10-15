"""Online co-op with AI backup: order your own fireteam's AI (Jungle Storm, SLUS-20820).

What the player gets
--------------------

In an online co-op game whose fireteams are filled with AI (roster writer 0x00377180, the AI-backup
fill), each human leads his own fireteam: the joiner Alpha, the host Bravo. With this option the
quick-order button (R2 in Jungle Storm's layout; keycode 0x81, message QuickOrder 0x153) works
online again, on both consoles, with split screen's scheme (grsquad 'orders'):

* **tap** (under 0.4 s): your fireteam's two AI switch between **Hold** (they stay where they are)
  and **Advance** (they follow you again);
* **hold and release** (0.4 s or longer): your two AI go to the spot under the crosshair -- the
  first on it, the second 1.5 m beside it -- and hold there even when you walk away. Tap to call
  them back (Advance).

The quick order's click comes with the marker instead of with the press: it plays once, on the
first frame the marker shows, and the release of a move-to plays the "setup" sound as in single
player. A tap plays no button sound at all -- the AI's answer is the feedback. The in-world marker
(the arrow on a disc) appears only once the button has been held 0.4 s -- the moment a release would
be a move-to -- follows the aim while you keep holding, and stays where the order sends them,
fading after 3 s; a tap shows none. Nothing changes outside online co-op.

Why it did nothing online
-------------------------

The button is bound online as in single player (RSInput table 0x0061E120: key 0x81 -> 0x153, flags
0x320, read out of both consoles' RAM), but nothing listens. CommandMap::RegisterMessageHandlers
(0x00280D80) registers its handlers in three steps and gives up at two gates::

    0x00280E88  bnez  (InSplitScreenMode)   -> skip the rest
    0x00280EDC  bnez  (InMultiplayerMode)   -> skip the rest   <- online stops here

Everything after the second gate is the whole order interface: QuickOrder 0x153 (handler
0x00285DA0, GR's CommandMap::SetAnotherTeam), the SELECT quick-select 0x241 (0x002823C0), the ROE,
waypoint, Follow Alpha/Bravo/Charlie, grid, pan and slot messages. In both consoles' RAM the message
table (manager 0x00D1CAE8, table +0xE8) holds only the three pre-gate CommandMap handlers
(0x242, 0x24C, 0x245); 0x153 has none. UnregisterMessageHandlers (0x002813D0) has the same gate at
0x00281520. The L1 map (0x242 -> 0x002829E0) does open online, but as a hold-to-view overlay
(map +0x14 = 1 in multiplayer or split screen) with no order input.

Behind the gate, SetAnotherTeam itself is single-player code: it picks "the other fireteam" by
checking whether your id is one of Alpha's members 0-2, and in multiplayer or split screen it
branches (0x00286188 / 0x002861A8 -> 0x0028637C) to a path that only clears that other team's
waypoint list. It could never order your own AI: with a human in the fireteam, the team's move
behaviour makes the human the formation leader (GR TeamLocationBehavior::Process, GetPlayerAI ->
SetFormationLeader) and the AI follow him, so a waypoint moves nobody. What the fireteam AI does
take from its own leader's side is the movement rule of engagement, FireTeamAI::
SetDesiredMovementROE (0x003DF600, fireteam +0x24: 0 Hold, 1 Advance, 2 Advance at all costs) --
the same call split screen's Hold/Advance (grsquad 'orders') uses.

How the order reaches the host
------------------------------

Only the host runs the AI: the joiner has no FireTeamAI objects at all (IkeAIMgr 0x0062C6F8
vt+0x14 answers 0 for every fireteam in the joiner's RAM), his fireteam's AI are network copies. The
order therefore travels as the message single player already sends for "set a fireteam's movement
ROE": SetMovementROE 0x20C with {company, platoon, fireteam} as RSUInt and the ROE as RSInt,
targeted exactly like SetAnotherTeam's own copy of it -- IkeRulesMgr vt+0xE8(company, 1) (the
consoles that run the company) plus RSGameMessage::AddTargetMaster (0x00499730, the host) -- and
posted (0x00149540). On the host IkeAIMgr::HandleSetMovementROE (0x003F2B40) finds the fireteam
(vt+0x14) and calls SetDesiredMovementROE; on the joiner the same handler finds no fireteam and does
nothing (it tests for 0). No new network message, no new handler.

The ROE sent is -1, "toggle": only the host knows the fireteam's current ROE, so the host resolves
it -- in HandleSetMovementROE's call to SetDesiredMovementROE, -1 becomes "Hold if it is not Hold,
else Advance" (split screen's toggle). No stock sender uses -1 (SetDesiredMovementROE would store
-1 % 3 = -1). Both consoles must run a disc with this option: a stock host would store -1.

Move to (a long press)
----------------------

A waypoint cannot move the AI of a human-led fireteam (see above), so split screen gives every AI
member his own order, as TeamLocationBehavior::GiveMoveOrders gives a leader: ClearScript, a
pooled LocationBehavior (IkeAIMgr 0x003F1BC0) placed with SetLocation (0x001B2760: finds the level,
moves the point off obstacles), AddElement, and the member's destination fields (HumanAI
+0x8C..+0x98); the fireteam gets TeamHoldBehavior on top of its script, marked initialised
(+0x19) so its first Process does not clear those orders, and desired ROE Hold; the human's own
HumanAI gets no destination, so TeamHold::IsPlayerDoingHisPart stays true wherever he walks. That
is grsquad's 'mv', here run on the host for a point that arrives by message.

The point is the stock handler's own ground point under the reticle (CaculateGroundPosition,
0x002857D0, at the handler's sp+0xA8 -- where the marker goes), computed on the console that
ordered. It travels as the game's AddWaypoint message 0x20E with all seven payloads the command
map sends (0x0029ADC0): {company, platoon, fireteam + 0x10, point, -1, 0.0, true}, addressed like
the toggle. All seven matter: the host also runs a waypoint-statistics handler for 0x20E
(0x00347E70, object 0x00D9E550) that reads the bool at payload 6. The first build sent four; on the
host that read ran past the payload array and jumped into garbage -- the freeze on disc 55EBB12A
(frozen main thread: 0x00347E70 -> 0x00141FA0 -> 0x00131480, under the local dispatch 0x0049B1C0
of the post from 0x00286444). With payload 6 true the statistics skip the order. On the host IkeAIMgr::HandleAddWaypoint (0x003F2DA0) looks the
fireteam up (vt+0x14) before FireTeamAI::AddWaypoint; that lookup goes through ``disp``: a fireteam
index of 0x10 or more is ours -- the real fireteam is looked up, the move-to runs, and 0 comes back
so no waypoint is added. Real waypoints (single player's command map, fireteams 0..2) pass straight
through. A stock host finds no fireteam 0x10+ and does nothing. The joiner's own copy of the
message finds no fireteam either (mv returns at once).

Grenade there instead (js_r2_hold 'frag' / 'smoke', tcps2/grnadeorder.py): the long press posts the
same AddWaypoint with fireteam + 0x20 (TEAM_NADE); on the host ``disp`` looks the fireteam up by its
low nibble and hands the point to grnadeorder's ``nade_disp`` (fireteam + 0x10 still goes on to
``mv``). Three words differ (_NADE_SUBS); with 'move' none does. The tap is unchanged.

The press time is noted by a hook on the press path's `jal 0x1255E0` (0x00285F34; also runs in
single player, where it only writes the word); the release and the per-frame preview compare the
game clock (RSClock 0x00684768 +0xD4) with it, against the one threshold TAP (0.4 s).

The marker. CaculateGroundPosition keeps a preview marker of its own: every successful lookup adds
one (IndicatorManagerPS2 AddOneIndicator, life 10000 s, no fade) into the map's +0x6BC, or moves the
one already there; a failed lookup kills it (0x00285C14..0x00285D24). The stock per-frame
quick-order update (0x002864A0, while +0x6B4 == 1) runs that lookup at 0x002865B8, so the preview
shows from the press; the release block kills it and drops the 3 s fading marker. The first
marker build (disc BDBB7C5C) drew its own marker per frame and, on release, set +0x6BC to -1
without killing what was there: the stock per-frame lookup still showed the preview from the
press, and each tap's preview lost its handle and stayed for its 10000 s -- the markers on a short
press and the ones spamming left on the ground (seen in that disc's host RAM). Now online the
per-frame lookup is skipped until the press is TAP old (``pregate``), and a tap's release kills
the preview its own lookup made (``mkgate``); from TAP on the stock preview and release run
unchanged.

The patch
---------

  0x00280EC4  RegisterMessageHandlers' `jal 0x125880` (the state manager, fetched for the
              InMultiplayerMode test) -> `jal reg`: the same state manager comes back, and online
              in a co-op lobby (game info = state manager +0x1110, lobby type +0x2CC == 2) it first
              registers 0x153 on this map through the stock list's own helper 0x00281320. The stock
              gate then skips the rest as before, so SELECT and the other map messages stay as
              they are.
  0x00281508  UnregisterMessageHandlers' twin `jal 0x125880` -> `jal unreg`: online, unregister
              0x153 for this map (the manager's unregister 0x0049ACB0 walks the list and does
              nothing when it is not there).
  0x0028637C  SetAnotherTeam's multiplayer branch (the handler never runs online or in split
              screen in stock, so these 57 words are dead): time the press; a tap posts the toggle
              (0x20C, ROE -1), a long press the move-to (0x20E, fireteam + 0x10, the point), for
              your own fireteam (SimHuman +0x448); leave through the handler's epilogue.
  0x003F2C3C  HandleSetMovementROE's `jal 0x3DF600` -> `jal tog`: -1 = toggle.
  0x00285F34  SetAnotherTeam's press path `jal 0x1255E0` (the sound manager, for the click
              i_ui2.wav) -> `jal press`: note the game time; online, skip the click (resume at
              0x00285F5C, the path's own branch to its exit) and mark it still to come (``clicked``
              = 0); single player: ``clicked`` = 1 and the call and click as before.
  0x003F2E98  HandleAddWaypoint's `jalr t9` (GetFireTeamAI) -> `jal disp`: fireteam 0x10+ = move-to.
  0x002865B8  the per-frame quick-order update's `jal 0x2857D0` (CaculateGroundPosition) ->
              `jal pregate`: online, while the press is younger than TAP, return to 0x00286668
              (after the lookup and the hint icons), so no preview marker is made; otherwise, and
              in single player, the lookup as before -- and online, the first lookup that finds
              ground (the frame the marker appears) plays the click the press skipped, once.
  0x002860A4  the release's `jal 0x1255E0` (the sound manager for i_setup1.wav, right before the
              marker block 0x002860CC) -> `jal mkgate`: online after a tap (``clicked`` still 0
              and the press younger than TAP), no setup sound;
              kill the preview in +0x6BC (the release's own lookup just made it), set -1, and go
              straight to the order (co_order); a long press and single player run the replaced
              call and the stock code (setup sound, preview killed, 3 s fading marker, the order).

Everything up to the multiplayer branch is the stock handler: it ignores the press while the map
is open (+0x34C) or you are dead, clicks on press and acts on release (+0x6B4), needs a ground point
under the reticle (0x002857D0), plays i_setup1.wav and drops the marker.

Caves
-----

* The twin of the sound library's lgAudAWrite, 0x00553D00..0x00553E83 (97 words, all used): no
  reference in the executable or either overlay, inside the RWX load segment 0x00100000..0x00612900,
  written by no other option.
* SetAnotherTeam's dead multiplayer branch, 0x0028637C..0x0028645F (56 of 57 words), entered only
  by that function's own two branches.
* Dead NewPS2Shortcut code, 0x002A2A9C..0x002A2DCF (204 of its 205 words; the last used word,
  0x002A2DC8, is the ``clicked`` flag): the padding after
  RelinkBravo (grsquad has 0x002A23E0..0x002A2A28, grcamera 0x002A2A2C..0x002A2A98), 0x002A2AA0
  (52 words), the leaf 0x002A2B60, 0x002A2B70, 0x002A2BE0 and the callback 0x002A2D80 (reached only
  by lui/addiu pairs inside 0x002A2B70 / 0x002A2BE0). The only references from outside are jal's
  from 0x0029FB20 (NewPS2Shortcut::Update), 0x002A0930, 0x0029F6C0 and 0x002A07E0, and every chain
  up from those ends in one of three roots: Update
  (called only at 0x0025C5A4, behind `beqz` on the getter 0x0023A260 of mInstance 0x00629278),
  Draw 0x0029FD70 (called only from the HUD at 0x002385FC, behind the same getter's `beqz` at
  0x002385D4 / 0x002385EC) and the destructor 0x0029F5F0 (does nothing for this == 0; called only
  from 0x0023AD40 with mInstance). mInstance is loaded at 0x0023A268 and 0x0023AD3C and stored only
  at 0x0023AD4C, with zero; no overlay touches it or the region; it reads 0 in every co-op save.
  grsquad's orders cave rests on the same fact.

Not done (design only): the command map / menu online. It needs the rest of the gate lifted
(minus SELECT, 0x241, which the take-over work owns), the map made interactive (0x002829E0 sets
+0x14 = 1 online: hold-to-view), and the menu's orders (0x005587F0: SetMovementROE/SetCombatROE for
Alpha 0x154, Bravo 0x158 or both, already sent with AddTargetMaster) checked online. The move-to
spaces the second AI along world X, not to the right of the aim as split screen does (no look
vector reaches the host; the point is validated either way).

Verified in the RAM interpreter (scratchpad ``agent_orders/emu_orders.py``, ``emu_post.py``,
``emu_moveto.py``, ``emu_freeze.py``, ``emu_preview.py``, ``emu_click.py``, ``mutants2.py``,
``mutants5.py``) over
both consoles' RAM from the AI-backup
co-op tests (discs 9C04BFE8, FA828984, 55EBB12A, BDBB7C5C): gate, toggle, tap/hold timing, the posted messages,
their delivery through the host's own local dispatch (every 0x20E handler, the statistics too: the
four-payload message fails there on the frozen host's RAM, the seven-payload one passes), TeamHold
initialised, desired ROE Hold, a LocationBehavior per AI at the point and 1.5 m beside it, the
human's destination cleared, the recall by a tap, a stock waypoint untouched; the markers, per
frame through the stock update 0x002864A0 with CaculateGroundPosition's marker handling modelled:
none while a tap is held or after it, none left after five taps, one preview from the 0.4 s frame
on that follows the aim, one 3 s marker at the order's point after the release and nothing 3.1 s
later; single player unchanged (preview from the press, the 3 s marker on release); the click:
online none on the press or for a tap, once on the frame the marker first shows (0.4 s, or later
when the ground is found later), not again when the ground is lost and found; single player on the
press only.
The tap toggle was played (FA828984: the AI answer "holding" / "affirmative"); the move-to froze
the host on 55EBB12A (fixed as above); BDBB7C5C showed the markers described above (fixed as
above). Not yet replayed.
"""

from __future__ import annotations

import struct

from .grasm import assemble
from .model import BOOL, Setting

CAVE, CAVE_END = 0x00553D00, 0x00553E84          # lgAudAWrite twin, 97 words
CAVE_B, CAVE_B_END = 0x002A2A9C, 0x002A2DD0      # dead NewPS2Shortcut code, 205 words
BRANCH, BRANCH_END = 0x0028637C, 0x00286460      # SetAnotherTeam's dead multiplayer branch

HOOK_REG = 0x00280EC4        # jal 0x125880 in CommandMap::RegisterMessageHandlers
HOOK_UNREG = 0x00281508      # jal 0x125880 in CommandMap::UnregisterMessageHandlers
HOOK_TOG = 0x003F2C3C        # jal 0x3DF600 in IkeAIMgr::HandleSetMovementROE
HOOK_PRESS = 0x00285F34      # jal 0x1255E0 in SetAnotherTeam's press path
HOOK_DISP = 0x003F2E98       # jalr t9 (GetFireTeamAI) in IkeAIMgr::HandleAddWaypoint
HOOK_PREV = 0x002865B8       # jal 0x2857D0 in the command map's per-frame quick-order preview
HOOK_MARK = 0x002860A4       # jal 0x1255E0: SetAnotherTeam's release, its setup sound (then the marker block)

#: split screen's timing and spacing (grsquad MV_TAP, MV_LIFT, MV_SPACE)
TAP = 0.40      # s: a shorter press is a tap (Hold/Advance), a longer one is "move to"
LIFT = 0.40     # m: the point is raised, so the floor lookup sees it from above
SPACE = 1.5     # m: each further AI stands this much further along world X (then validated)
TEAM_MOVE = 0x10    # added to the fireteam index of an AddWaypoint that means "move to"


def _hi(x):
    return struct.unpack("<I", struct.pack("<f", x))[0] >> 16


SYMS = dict(
    SMGR=0x00125880,             # IRSGameStateMgr (vt+0x9C InMultiplayerMode, +0x1110 game info)
    REGONE=0x00281320,           # CommandMap: register one {id, PMF} from the stock list
    ID_QUICKORDER=0x0058BD38,    # u16 0x153, the stock list's own constant
    PMF_QUICKORDER=0x00578950,   # {0, -1, 0x285DA0}: CommandMap::SetAnotherTeam
    SETMOVE=0x003DF600,          # FireTeamAI::SetDesiredMovementROE
    SETMOVEROE=0x003DF640,       # FireTeamAI::SetMovementROE (pushes TeamHold for Hold)
    MSG_CREATE=0x00498FD0,       # RSGameMessage::Create(id)
    ADD_UINT=0x00124BD0,         # AddPayload(RSUInt)
    ADD_INT=0x00136A20,          # AddPayload(RSInt)
    ADD_VEC=0x0014E0E0,          # AddPayload(RSVector3)
    ADD_FLOAT=0x00157AB0,        # AddPayload(RSFloat), the value in f12
    ADD_BOOL=0x001256A0,         # AddPayload(RSBool)
    CGPOS=0x002857D0,            # CommandMap::CaculateGroundPosition(point*, float*)
    PREVIEW_SKIP=0x00286668,     # the per-frame preview, after its ground lookup and hint icons
    PRESS_SKIP=0x00285F5C,       # SetAnotherTeam's press path, after its click (b to the exit)
    CLICK_WAV=0x0058BF30,        # "i_ui2.wav", the press click
    CLICK_VOL=0x0058BF90,        # 0.7, its volume
    EFFMGR=0x00422F50,           # EffMgrPS2
    INDMGR=0x00285D80,           # its IndicatorManagerPS2 (+0x6270)
    KILLIND=0x00432390,          # IndicatorManagerPS2::KillIndicator(i)
    RULES=0x00124610,            # IIkeRulesMgr::Get
    SET_TARGET=0x00207D40,       # message target mask
    ADD_MASTER=0x00499730,       # RSGameMessage::AddTargetMaster
    POST=0x00149540,             # post
    RELEASE=0x00124AE0,          # release our reference
    EPILOGUE=0x00286460,         # SetAnotherTeam's epilogue
    SNDMGR=0x001255E0,           # the call HOOK_PRESS replaces
    CLOCK=0x00684768,            # RSClock*, +0xD4 game time (s)
    AIMGR=0x0062C6F8,            # IkeAIMgr*
    SETLOC=0x001B2760,           # LocationBehavior::SetLocation (finds the level, moves off obstacles)
    POOLLOC=0x003F1BC0,          # IkeAIMgr::GetPoolLocationBehavior
    ACCEPT=0x003E4260,           # HumanAI::AcceptingOrders
    CLEAR=0x001B7140,            # RSScript::ClearScript
    ADDELEM=0x001B6E10,          # RSScript::AddElement
    TAP_HI=_hi(TAP), LIFT_HI=_hi(LIFT), SPACE_HI=_hi(SPACE),
    TEAM_MOVE=TEAM_MOVE,
    HOLDINIT=0x19,               # TeamHoldBehavior: initialised byte
)

# ---- cave A (0x00553D00): registration, toggle, press time, the AddWaypoint dispatcher
SRC = """
reg:                                  ; RegisterMessageHandlers (s0 = the map)
    addiu sp, sp, -0x20
    sd    ra, 0x10(sp)
    jal   SMGR                        ; the state manager, as the replaced call
    nop
    sw    v0, 0x00(sp)
    lw    t9, 0(v0)
    lw    t9, 0x9c(t9)                ; InMultiplayerMode
    jalr  t9
    move  a0, v0
    beqz  v0, reg_out                 ; single player: stock registers 0x153 itself
    lw    t0, 0x00(sp)
    lw    t0, 0x1110(t0)              ; the local game info (state manager vt+0x150)
    beqz  t0, reg_out
    li    t1, 2
    lw    t0, 0x2cc(t0)               ; lobby type: 2 = co-op
    bne   t0, t1, reg_out
    lui   a1, %hi(ID_QUICKORDER)
    addiu a1, a1, %lo(ID_QUICKORDER)
    lui   a2, %hi(PMF_QUICKORDER)
    addiu a2, a2, %lo(PMF_QUICKORDER)
    move  a0, s0
    jal   REGONE                      ; QuickOrder -> SetAnotherTeam, as single player
    move  a3, zero
reg_out:
    lw    v0, 0x00(sp)                ; the state manager, for the caller's own test
    ld    ra, 0x10(sp)
    jr    ra
    addiu sp, sp, 0x20

unreg:                                ; UnregisterMessageHandlers (s0 = message manager, s1 = the map)
    addiu sp, sp, -0x20
    sd    ra, 0x10(sp)
    jal   SMGR
    nop
    sw    v0, 0x00(sp)
    lw    t9, 0(v0)
    lw    t9, 0x9c(t9)                ; InMultiplayerMode
    jalr  t9
    move  a0, v0
    beqz  v0, unreg_out               ; single player: stock unregisters it
    lw    t9, 0(s0)
    lw    t9, 0x28(t9)                ; UnregisterMessageHandler(0x153, map): no-op if never registered
    move  a0, s0
    li    a1, 0x153
    jalr  t9
    move  a2, s1
unreg_out:
    lw    v0, 0x00(sp)
    ld    ra, 0x10(sp)
    jr    ra
    addiu sp, sp, 0x20

tog:                                  ; HandleSetMovementROE (a0 = fireteam, a1 = ROE)
    li    t0, -1
    bne   a1, t0, tog_set
    lw    t1, 0x24(a0)                ; desired movement ROE: 0 Hold, 1 Advance, 2 at all costs
    sltiu a1, t1, 1                   ; -1 = toggle: Hold -> Advance, anything else -> Hold
tog_set:
    j     SETMOVE
    nop

press:                                ; SetAnotherTeam, button down: note the time
    lui   at, %hi(CLOCK)
    lw    t0, %lo(CLOCK)(at)
    lw    t0, 0xd4(t0)                ; game time, s
    lui   at, %hi(press_t)
    j     press_b                     ; (cave B) the click, or not
    sw    t0, %lo(press_t)(at)

disp:                                 ; HandleAddWaypoint's GetFireTeamAI (t9; a1..a3 = company,
    sltiu t0, a3, TEAM_MOVE           ;   platoon, fireteam; the point at the caller's sp+0x70)
    beqz  t0, disp_move
    addiu t1, sp, 0x70
    jr    t9                          ; a stock waypoint: as before
    nop
disp_move:
    addiu sp, sp, -0x20
    sd    ra, 0x10(sp)
    sw    t1, 0x00(sp)
    jalr  t9                          ; the fireteam
    addiu a3, a3, -0x10
    move  a0, v0
    jal   mv
    lw    a1, 0x00(sp)
    ld    ra, 0x10(sp)
    move  v0, zero                    ; the handler adds no waypoint
    jr    ra
    addiu sp, sp, 0x20

mv_tail:                              ; (mv, continued) the member's destination, for TeamHold
    lw    t0, 0x18(s5)
    lw    t1, 0x1c(s5)
    lw    t2, 0x20(s5)
    sw    t0, 0x8c(s4)
    sw    t1, 0x90(s4)
    sw    t2, 0x94(s4)
    lui   t0, 0x4973
    ori   t0, t0, 0xa710              ; 998001.0 = 999^2, the engine's "far"
    sw    t0, 0x98(s4)
    j     mv_loop
    addiu s3, s3, 1                   ; one more member ordered
mv_out:
    ld    ra, 0x60(sp)
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    lq    s3, 0x30(sp)
    lq    s4, 0x40(sp)
    lq    s5, 0x50(sp)
    jr    ra
    addiu sp, sp, 0x80
press_t:
    .word 0
"""

# ---- cave B (0x002A2A9C): split screen's move-to (grsquad 'mv') for a point that arrives by message
SRC_B = """
mv:                                   ; a0 = the fireteam (0: none), a1 = the point (caller's local)
    addiu sp, sp, -0x80
    sd    ra, 0x60(sp)
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s2, 0x20(sp)
    sq    s3, 0x30(sp)
    sq    s4, 0x40(sp)
    sq    s5, 0x50(sp)
    move  s0, a0
    beqz  s0, mv_b_out
    move  s1, a1
    lwc1  $f0, 8(s1)
    lui   at, LIFT_HI
    mtc1  at, $f1
    move  s2, zero                    ; (TeamHold pushed yet?)
    add.s $f0, $f0, $f1
    swc1  $f0, 8(s1)                  ; raised, so the floor lookup sees it from above
th:                                   ; the fireteam holds: TeamHoldBehavior on top of its script
    lw    t0, 0xc(s0)
    lw    t0, 4(t0)
    beqz  t0, th_push
    li    t2, 0x24
    lw    t1, 4(t0)
    beq   t1, t2, th_hold
    nop
th_push:
    bnez  s2, desired                 ; pushed, and still no TeamHold on top: leave it
    li    s2, 1
    sw    s2, 0x1c(s0)                ; not Hold, so the setter acts
    move  a0, s0
    jal   SETMOVEROE                  ; SetMovementROE(Hold): drops a fight, pushes TeamHold
    move  a1, zero
    b     th
    nop
th_hold:
    li    t1, 1
    sb    t1, HOLDINIT(t0)            ; initialised: its first Process would clear the orders below
desired:
    move  a0, s0
    jal   SETMOVE                     ; SetDesiredMovementROE(Hold): UpdateMovementROE leaves it
    move  a1, zero
    move  s2, zero                    ; member index
    move  s3, zero                    ; members ordered so far
mv_loop:
    lw    t0, 0x18(s0)                ; member count
    slt   t0, s2, t0
    beqz  t0, mv_b_out
    lw    t1, 0x14(s0)                ; RSArray<HumanAI*> data
    sll   t0, s2, 2
    addu  t1, t1, t0
    lw    s4, 0(t1)                   ; HumanAI
    beqz  s4, mv_loop
    addiu s2, s2, 1
    lw    t0, 0x14(s4)                ; its SimHuman
    beqz  t0, mv_loop
    nop
    lw    t1, 0x138(t0)               ; control type: 1 = AI here
    li    t2, 1
    beq   t1, t2, mv_ai
    lui   t1, 0x4973
    sw    zero, 0x8c(s4)              ; a player (this console's or a network copy): no
    sw    zero, 0x90(s4)              ;   destination, so TeamHold::IsPlayerDoingHisPart
    sw    zero, 0x94(s4)              ;   stays true wherever he walks
    ori   t1, t1, 0xa710
    b     mv_loop
    sw    t1, 0x98(s4)
mv_ai:
    jal   ACCEPT                      ; HumanAI::AcceptingOrders
    move  a0, s4
    beqz  v0, mv_loop
    nop
    lw    a0, 0xc(s4)                 ; what GiveMoveOrders gives a leader: ClearScript,
    jal   CLEAR
    nop
    lui   at, %hi(AIMGR)
    jal   POOLLOC                     ; a pooled LocationBehavior,
    lw    a0, %lo(AIMGR)(at)
    move  s5, v0
    lwc1  $f0, 0(s1)                  ; his spot: the point, SPACE m further along X per
    mtc1  s3, $f1                     ;   member already ordered
    lui   at, SPACE_HI
    mtc1  at, $f2
    cvt.s.w $f1, $f1
    lw    t0, 4(s1)
    mul.s $f1, $f1, $f2
    lw    t1, 8(s1)
    add.s $f0, $f0, $f1
    sw    t0, 0x74(sp)
    sw    t1, 0x78(sp)
    swc1  $f0, 0x70(sp)
    move  a0, s5
    jal   SETLOC                      ; SetLocation there,
    addiu a1, sp, 0x70
    bnez  v0, mv_add
    move  a0, s5
    jal   SETLOC                      ; or, if there is no room, at the point itself
    move  a1, s1
    beqz  v0, mv_loop                 ; no floor there: no order (as GiveMoveOrders drops it)
    nop
mv_add:
    lw    a0, 0xc(s4)
    jal   ADDELEM                     ; AddElement,
    move  a1, s5
    j     mv_tail
    nop
mv_b_out:
    j     mv_out                      ; (the epilogue is in the first cave)
    nop

press_b:                              ; (press, continued; ra = the press path, 0x285F3C)
    addiu sp, sp, -0x10
    sd    ra, 0x00(sp)
    jal   SMGR
    nop
    lw    t9, 0(v0)
    lw    t9, 0x9c(t9)                ; InMultiplayerMode
    jalr  t9
    move  a0, v0
    ld    ra, 0x00(sp)
    sltiu t0, v0, 1                   ; clicked: 1 in single player (its click is now), 0 online
    lui   at, %hi(clicked)            ;   (pregate plays it when the preview first shows)
    sw    t0, %lo(clicked)(at)
    bnez  v0, pb_quiet
    addiu sp, sp, 0x10
    j     SNDMGR                      ; single player: the call it replaced, and the click
    nop
pb_quiet:
    j     PRESS_SKIP                  ; online: no click on the press; on to the handler's exit
    nop

pregate:                              ; the stock per-frame quick-order preview (0x002864A0) asks
    lui   at, %hi(CLOCK)              ;   for the ground point while the button is down
    lw    t0, %lo(CLOCK)(at)
    lwc1  $f0, 0xd4(t0)               ; now
    lui   at, %hi(press_t)
    lwc1  $f1, %lo(press_t)(at)       ; pressed at
    lui   at, TAP_HI
    mtc1  at, $f2
    sub.s $f0, $f0, $f1
    c.lt.s $f0, $f2
    nop
    bc1f  pg_held                     ; held TAP or longer: the preview, as stock
    lui   at, %hi(clicked)
    lw    t0, %lo(clicked)(at)        ; still a tap: 1 = single player, 0 = online
    bnez  t0, pg_held                 ; single player: the lookup, as stock (its click came with
    nop                               ;   the press, so pg_held plays none)
    j     PREVIEW_SKIP                ; online and still a tap: no ground lookup (so no preview
    nop                               ;   marker) and no hint icon; resume after both
pg_held:
    addiu sp, sp, -0x20
    sd    ra, 0x10(sp)
    jal   CGPOS                       ; the lookup (a0..a2 as given): adds / moves the preview
    nop
    lui   at, %hi(clicked)
    beqz  v0, pg_ret                  ; no ground: no preview, no click yet
    lw    t0, %lo(clicked)(at)
    bnez  t0, pg_ret                  ; clicked already (or single player, clicked on the press)
    li    t0, 1
    jal   SNDMGR                      ; online: the preview's first frame -- the press click
    sw    t0, %lo(clicked)(at)        ;   now, once
    lw    t9, 0(v0)
    lui   at, %hi(CLICK_VOL)
    lwc1  $f12, %lo(CLICK_VOL)(at)
    lui   a1, %hi(CLICK_WAV)
    addiu a1, a1, %lo(CLICK_WAV)
    lw    t9, 0x14(t9)                ; play(name, volume), as the press path does
    jalr  t9
    move  a0, v0
    li    v0, 1                       ; the lookup's answer: found
pg_ret:
    ld    ra, 0x10(sp)
    jr    ra
    addiu sp, sp, 0x20

mkgate:                               ; SetAnotherTeam's release, after its ground lookup, before
    lui   at, %hi(clicked)            ;   its setup sound (s5 = the map; ra = 0x2860AC)
    lw    t0, %lo(clicked)(at)
    bnez  t0, mk_sp                   ; single player, or online after the move-to's click: stock
    lw    s6, 0x6bc(s5)               ; the preview's handle (s6 is free until 0x2860CC reloads it)
    lui   at, %hi(CLOCK)
    lw    t0, %lo(CLOCK)(at)
    lwc1  $f0, 0xd4(t0)
    lui   at, %hi(press_t)
    lwc1  $f1, %lo(press_t)(at)
    lui   at, TAP_HI
    mtc1  at, $f2
    sub.s $f0, $f0, $f1
    c.lt.s $f0, $f2
    nop
    bc1f  mk_sp                       ; held: stock -- the setup sound, the preview goes, the 3 s
    li    t0, -1                      ;   fading marker, and the stock test sends it on to co_order
    beq   s6, t0, mk_tap              ; a tap: no setup sound; the preview the release's own lookup
    sw    t0, 0x6bc(s5)               ;   left goes, and nothing is placed
    jal   EFFMGR
    nop
    jal   INDMGR
    move  a0, v0
    move  a0, v0
    jal   KILLIND
    move  a1, s6
mk_tap:
    j     co_order
    nop
mk_sp:
    j     SNDMGR                      ; the replaced call; back at 0x2860AC it plays i_setup1.wav
    nop

vecpay:                               ; a0 = the message, a1 = the point: payloads 3..6 of an
    addiu sp, sp, -0x20               ;   AddWaypoint, all of them, as the command map sends it
    sd    ra, 0x10(sp)                ;   (0x0029ADC0). Every handler of 0x20E reads its own:
    jal   ADD_VEC                     ;   the host's waypoint statistics (0x00347E70) read the
    sw    a0, 0x00(sp)                ;   bool at 6 -- a 4-payload message froze the host there.
    lw    a0, 0x00(sp)
    jal   ADD_INT
    li    a1, -1
    lw    a0, 0x00(sp)
    jal   ADD_FLOAT
    mtc1  zero, $f12
    lw    a0, 0x00(sp)
    jal   ADD_BOOL
    li    a1, 1                       ; true: the statistics skip this one
    ld    ra, 0x10(sp)
    jr    ra
    addiu sp, sp, 0x20
clicked:                              ; this press's click: 0 = online and not played yet
    .word 0
"""

# ---- the quick order's dead multiplayer branch (0x0028637C): tap = toggle, hold = move to
BODY = """
co_order:                             ; s5 = the map, s4 = your SimHuman + 0x1B0; sp+0xA8 = the
    lui   at, %hi(CLOCK)              ;   ground point under the reticle (stock, the marker's)
    lw    t0, %lo(CLOCK)(at)
    lwc1  $f0, 0xd4(t0)               ; now
    lui   at, %hi(press_t)
    lwc1  $f1, %lo(press_t)(at)       ; when the button went down
    lui   at, TAP_HI
    mtc1  at, $f2
    sub.s $f0, $f0, $f1               ; held for
    li    s1, 0x20c                   ; a tap: SetMovementROE, toggle
    c.lt.s $f0, $f2
    li    s2, 0
    bc1t  co_send
    nop
    li    s1, 0x20e                   ; held: AddWaypoint to the point, fireteam + TEAM_MOVE
    li    s2, TEAM_MOVE
co_send:
    jal   MSG_CREATE
    move  a0, s1
    move  s0, v0
    lw    a1, 0x38c(s5)               ; company
    jal   ADD_UINT
    move  a0, s0
    lw    a1, 0x390(s5)               ; platoon
    jal   ADD_UINT
    move  a0, s0
    lw    a1, 0x298(s4)               ; your fireteam (SimHuman +0x448)
    move  a0, s0
    jal   ADD_UINT
    addu  a1, a1, s2
    li    t0, 0x20c
    beq   s1, t0, co_tog
    move  a0, s0
    jal   vecpay                      ; the point, and the rest of AddWaypoint's payloads
    addiu a1, sp, 0xa8
    b     co_post
    nop
co_tog:
    jal   ADD_INT
    li    a1, -1                      ; toggle, resolved where the fireteam lives
co_post:
    jal   RULES
    nop
    lw    t9, 0(v0)
    move  a0, v0
    lw    a1, 0x38c(s5)
    lw    t9, 0xe8(t9)                ; the consoles that run this company
    jalr  t9
    li    a2, 1
    move  a1, v0
    jal   SET_TARGET
    move  a0, s0
    jal   ADD_MASTER                  ; and the host, which runs the AI
    move  a0, s0
    jal   POST
    move  a0, s0
    jal   RELEASE
    move  a0, s0
    b     EPILOGUE
    nop
"""


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


_CAVE_STOCK_HEX = (   # lgAudAWrite twin, 0x00553D00..0x00553E84
    "27BDFFB0 3C030058 FFB00010 2470C614 FFB20020 00E0902D FFB30028 00C0982D "
    "FFB40030 0080A02D FFB50038 00A0A82D FFB10018 3C028000 FFB60040 2408FFFF "
    "FFBF0048 8E030000 10680044 3442000A 16600003 3C04005A 1000000A 2484F930 "
    "12400006 3C020058 8E440000 8C43C604 0064182A 10600008 3C020069 3C04005A "
    "2484F958 0C05ADDE 00000000 3C028000 10000032 34420004 24561240 0C05F628 "
    "02C0202D 10400006 3C04005A 0C05ADDE 2484F988 3C028000 10000028 34420008 "
    "8E040000 3C100058 2610C60C 0C05E8C8 3C110069 8E020000 263113F0 0260282D "
    "AC54000C 8E430000 A0550012 AC430020 AE330000 AE320004 8E040000 8C860020 "
    "0C05A8D6 24840030 8E070000 8E480000 3C0B0055 02C0202D 256B4EA0 2508003F "
    "24050009 00084103 24060001 00084100 00E0482D 240A0030 0C05F5AA AFB10000 "
    "50400007 DFB00010 AE400000 3C04005A 0C05ADDE 2484F9C8 3C028000 DFB00010 "
    "DFB10018 DFB20020 DFB30028 DFB40030 DFB50038 DFB60040 DFBF0048 03E00008 "
    "27BD0050 "
)
_CAVE_B_STOCK_HEX = (  # dead NewPS2Shortcut code, 0x002A2A9C..0x002A2DD0
    "00000000 27BDFFE0 24050002 FFBF0010 2406000D 7FB00000 0080802D 8C840024 "
    "0C0A81BC 24070003 8E040024 24050002 2406000E 0C0A81BC 24070003 8E040024 "
    "24050002 2406000F 0C0A81BC 24070003 8E040024 24050002 2406000E 0C0A8230 "
    "24070003 8E040024 24050002 2406000A 0C0A81BC 00A0382D 8E040024 24050002 "
    "2406000B 0C0A81BC 00A0382D 8E040024 24050002 2406000C 0C0A81BC 00A0382D "
    "8E040024 24050002 2406000B 0C0A8230 00A0382D DFBF0010 7BB00000 03E00008 "
    "27BD0020 AC800004 0080102D 03E00008 AC800000 27BDFFD0 FFBF0020 7FB10010 "
    "7FB00000 0080882D 1220000D 00A0802D 8E240000 10800005 0010143C 3C05002A "
    "0C045900 24A52D80 0010143C 0002143F 18400004 0220102D 0C040D54 0220202D "
    "0220102D DFBF0020 7BB10010 7BB00000 03E00008 27BD0030 00000000 00000000 "
    "00000000 27BDFFA0 FFBF0050 7FB40040 7FB30030 0080A02D 7FB20020 00A0982D "
    "7FB10010 06610002 7FB00000 0000982D 8E820004 00531026 0002102B 1040002C "
    "00000000 1260002A 00000000 00131080 00531021 00021080 0C040D48 24440010 "
    "3C05002A 3C06002A 0040202D 24A52D50 24C62D80 24070014 0C045990 0260402D "
    "0040902D 16400003 00000000 10000023 0000102D 8E900004 0213082A 0261800A "
    "10000009 0000882D 8E820000 00111880 00711821 00031880 02432021 0C0A8B48 "
    "00432821 26310001 0230102A 1440FFF6 00000000 8E840000 10800004 00000000 "
    "3C05002A 0C045900 24A52D80 AE920000 16600008 00000000 8E840000 10800004 "
    "00000000 3C05002A 0C045900 24A52D80 AE800000 AE930004 24020001 DFBF0050 "
    "7BB40040 7BB30030 7BB20020 7BB10010 7BB00000 03E00008 27BD0060 00000000 "
    "00000000 8CA30000 0080102D AC830000 C4A30004 C4A20008 C4A1000C C4A00010 "
    "E4830004 E4820008 E481000C 03E00008 E4800010 2403FFFF 0000282D AC830000 "
    "00051080 00821021 24A50001 AC430004 28A20004 1440FFFB 00051080 03E00008 "
    "0080102D 27BDFFE0 FFBF0010 7FB00000 0080802D 12000008 0200102D 0005143C "
    "0002143F 18400003 00000000 0C040D54 00000000 0200102D DFBF0010 7BB00000 "
    "03E00008 27BD0020 00000000 00000000 00000000 "
)
_BRANCH_STOCK_HEX = (  # SetAnotherTeam's multiplayer branch, 0x0028637C..0x00286460
    "0C049578 00000000 8C590000 3C010059 3C050059 0040202D C42CBF90 8F390014 "
    "0320F809 24A5BF40 12130005 00000000 12120003 00000000 16110004 0000902D "
    "10000002 24120001 0000902D 0C049184 00000000 8E990000 0040882D 8F39006C "
    "0320F809 0280202D 8E990000 0040802D 8F3900A8 0320F809 0280202D 8E390000 "
    "0200282D 0220202D 0040302D 0240382D 8F39011C 0320F809 0000402D 0C0529F8 "
    "0040802D 8C590000 0200282D 8F390038 0320F809 0040202D 10400002 00000000 "
    "2442FE50 10400003 00000000 0C0EF848 0040202D 00121140 02A21021 0C0A6784 "
    "244403A0 "
)

#: stock words of every word this module may write (read from SLUS_208.20)
JS_STOCK = _stock_words(CAVE, _CAVE_STOCK_HEX)
JS_STOCK.update(_stock_words(CAVE_B, _CAVE_B_STOCK_HEX))
JS_STOCK.update(_stock_words(BRANCH, _BRANCH_STOCK_HEX))
JS_STOCK.update({
    HOOK_REG: 0x0C049620,        # jal 0x125880
    HOOK_UNREG: 0x0C049620,      # jal 0x125880
    HOOK_TOG: 0x0C0F7D80,        # jal 0x3DF600
    HOOK_PRESS: 0x0C049578,      # jal 0x1255E0 (slot: sw v0, 0x6b4(s5))
    HOOK_DISP: 0x0320F809,       # jalr t9 (slot: move a0, s3)
    HOOK_PREV: 0x0C0A15F4,       # jal 0x2857D0 (slot: addiu a2, sp, 0x3c)
    HOOK_MARK: 0x0C049578,       # jal 0x1255E0 (slot: nop), the sound manager for i_setup1.wav
})
#: words read but not written: the branches into the dead regions, exits, the hooks' neighbours
JS_CONTEXT = {
    0x00286188: 0x1440007C,      # bnez v0, 0x28637C (InMultiplayerMode)
    0x002861A8: 0x14400074,      # bnez v0, 0x28637C (InSplitScreenMode)
    0x00286460: 0xDFBF0070,      # ld ra, 0x70(sp): the epilogue
    0x00280ED0: 0x8F39009C,      # lw t9, 0x9c(t9): the caller's own gate test follows the hook
    0x00280EDC: 0x1440010A,      # bnez v0, 0x281308
    0x00281514: 0x8F39009C,
    0x00281520: 0x144000FD,      # bnez v0, 0x281918
    0x00578958: 0x00285DA0,      # PMF_QUICKORDER's function: CommandMap::SetAnotherTeam
    0x003F2C34: 0x10800003,      # beqz a0: the handler skips a missing fireteam (the joiner)
    0x00285F30: 0x24020001,      # li v0, 1
    0x00285F38: 0xAEA206B4,      # sw v0, 0x6b4(s5): the press state, in HOOK_PRESS's slot
    0x003F2E94: 0x8F390014,      # lw t9, 0x14(t9): IkeAIMgr::GetFireTeamAI
    0x003F2E9C: 0x0260202D,      # move a0, s3 (HOOK_DISP's slot)
    0x003F2EA4: 0x10800003,      # beqz a0: no fireteam -> no waypoint (disp returns 0)
    0x003F2EA8: 0x27A50070,      # addiu a1, sp, 0x70: the point
    0x003F2EAC: 0x0C0F7CC0,      # jal FireTeamAI::AddWaypoint
    0x0029FCCC: 0x0C0A8AA8,      # jal 0x2A2AA0  } CAVE_B's callers: NewPS2Shortcut::Update
    0x0029FD40: 0x0C0A89D0,      # jal 0x2A2740  } (0x29FB20) ...
    0x0025C594: 0x10400009,      # beqz v0: ... runs only when mInstance (0x629278) is set
    0x002A093C: 0x0C0A8AD8,      # jal 0x2A2B60 (0x2A0930 <- 0x2A0320 <- 0x29F720 <- Draw)
    0x002A0808: 0x0C0A8AF8,      # jal 0x2A2BE0 (0x2A07E0 <- 0x2A06F0 / 0x2A0930 <- the above)
    0x002385D4: 0x1040000E,      # beqz v0: the HUD draws NewPS2Shortcut (0x29FD70) only when
    0x002385EC: 0x10400007,      #   mInstance is set
    0x0029F6DC: 0x0C0A8ADC,      # jal 0x2A2B70 (0x29F6C0 <- 0x29F680 <- its destructor)
    0x0029F604: 0x12200016,      # beqz s1: the destructor does nothing for mInstance == 0
    0x0023AD4C: 0xAC209278,      # sw zero, mInstance: the only store to it
    0x00285F4C: 0xC42CBF90,      # lwc1 f12, CLICK_VOL: the press path's click volume
    0x00285F58: 0x24A5BF30,      # addiu a1, CLICK_WAV: its sound name
    0x00285F5C: 0x1000000B,      # b 0x285F8C: PRESS_SKIP, past the click to the exit test
    0x00285F60: 0x8EA406B4,      #   lw a0, 0x6b4(s5) (its slot: 1 -> the handler returns)
    0x002865BC: 0x27A6003C,      # addiu a2, sp, 0x3c (HOOK_PREV's slot)
    0x002865C0: 0x10400016,      # beqz v0, 0x28661C: the preview's "no ground" hint
    0x00286668: 0x8E0406B4,      # lw a0, 0x6b4(s0): PREVIEW_SKIP
    0x00285C14: 0x8EA306BC,      # lw v1, 0x6bc(s5): CaculateGroundPosition keeps the preview marker
    0x00285C90: 0x0C10C87C,      #   (life 10000 s, no fade) at +0x6BC, moves it, kills it on failure
    0x0028609C: 0x104000F0,      # beqz v0, 0x286460: the release's lookup found no ground -> exit
    0x002860A8: 0x00000000,      # nop (HOOK_MARK's slot)
    0x002860C8: 0x24A5BF40,      # addiu a1, "i_setup1.wav": the sound mk_sp's call leads to
    0x002860CC: 0x8EB606BC,      # lw s6, 0x6bc(s5): the marker block after it (stock again)
    0x002860D0: 0x2402FFFF,      # addiu v0, zero, -1
    0x002860D4: 0x12C2000A,      # beq s6, v0, 0x286100
    0x00286168: 0x0C10C87C,      # jal 0x4321F0: the release's 3 s marker (a long press keeps it)
}
#: u16 message ids read by the routines
JS_IDS = {0x0058BD38: 0x0153}    # ID_QUICKORDER


def _labels(src):
    out = set()
    for ln in src.splitlines():
        head = ln.split(";")[0]
        if ":" in head:
            name = head.split(":")[0].strip()
            if name.isidentifier():
                out.add(name)
    return out


#: grnadeorder (js_r2_hold 'frag' / 'smoke'): the three words that make a long press a grenade order.
#: The order goes out as fireteam + TEAM_NADE; on the host disp looks the fireteam up by its low nibble
#: and hands the point to grnadeorder's nade_disp, which passes fireteam + 0x10 on to mv as before.
TEAM_NADE = 0x20
_NADE_SUBS = (
    ("BODY", "    li    s2, TEAM_MOVE\n", "    li    s2, TEAM_NADE\n"),
    ("SRC", "    addiu a3, a3, -0x10\n", "    andi  a3, a3, 0xf\n"),
    ("SRC", "    jal   mv\n    lw    a1, 0x00(sp)\n", "    jal   NADE_DISP\n    lw    a1, 0x00(sp)\n"),
)


def build(r2_hold: str = "move"):
    """(cave words, cave-B words, branch words, labels). Two passes: the first sizes each piece
    with every other piece's labels standing in at its base, the second resolves them.
    `r2_hold`: 'move' (as always) or 'frag' / 'smoke' (grnadeorder: three words differ)."""
    srcs = {"SRC": SRC, "SRC_B": SRC_B, "BODY": BODY}
    syms_extra = {}
    if r2_hold != "move":
        from .grnadeorder import JS_NADE_DISP
        for piece, old, new in _NADE_SUBS:
            assert srcs[piece].count(old) == 1, old
            srcs[piece] = srcs[piece].replace(old, new)
        syms_extra = dict(TEAM_NADE=TEAM_NADE, NADE_DISP=JS_NADE_DISP)
    pieces = (("SRC", srcs["SRC"], CAVE, CAVE_END), ("SRC_B", srcs["SRC_B"], CAVE_B, CAVE_B_END),
              ("BODY", srcs["BODY"], BRANCH, BRANCH_END))
    stand_in = {}
    for _name, src, base, _end in pieces:
        for lab in _labels(src):
            stand_in[lab] = base
    labels = dict(stand_in)
    for _ in range(2):
        out, new = {}, {}
        for name, src, base, end in pieces:
            own = _labels(src)
            syms = dict(SYMS, **syms_extra)
            syms.update({k: v for k, v in labels.items() if k not in own})
            words, lab = assemble(src, base, syms)
            if base + 4 * len(words) > end:
                raise ValueError("co-op orders: %s is %d words, room %d"
                                 % (name, len(words), (end - base) // 4))
            out[name] = words
            new.update(lab)
        labels = new
    return out["SRC"], out["SRC_B"], out["BODY"], labels


def edits(r2_hold: str = "move") -> list:
    """(va, value, stock, note). `r2_hold` as build()."""
    cave, cave_b, body, labels = build(r2_hold)
    out = [(CAVE + 4 * i, w, JS_STOCK[CAVE + 4 * i], "co-op orders: routines")
           for i, w in enumerate(cave)]
    out += [(CAVE_B + 4 * i, w, JS_STOCK[CAVE_B + 4 * i],
             "co-op orders: move to where you aimed (split screen's per-member orders)")
            for i, w in enumerate(cave_b)]
    out += [(BRANCH + 4 * i, w, JS_STOCK[BRANCH + 4 * i],
             "co-op orders: quick order = tap Hold/Advance, hold = move to, sent to the host")
            for i, w in enumerate(body) if w != JS_STOCK[BRANCH + 4 * i]]
    for va, label, note in (
            (HOOK_REG, "reg", "register the quick order online in co-op"),
            (HOOK_UNREG, "unreg", "unregister it again"),
            (HOOK_TOG, "tog", "the host resolves ROE -1 as Hold/Advance toggle"),
            (HOOK_PRESS, "press", "note when the quick-order button went down; online, no click yet"),
            (HOOK_DISP, "disp", "an AddWaypoint for fireteam + 0x10 is a move-to order"),
            (HOOK_PREV, "pregate", "online, no preview marker until the press is a move-to")):
        out.append((va, assemble("jal %#x" % labels[label], va)[0][0], JS_STOCK[va],
                    "co-op orders: " + note))
    out.append((HOOK_MARK, assemble("jal %#x" % labels["mkgate"], HOOK_MARK)[0][0],
                JS_STOCK[HOOK_MARK], "co-op orders: online, a tap's release: no sound, no marker"))
    if r2_hold != "move":            # name the words that make the long press a grenade order
        move = {va: w for va, w, _s, _n in edits()}
        if set(move) != {va for va, *_ in out}:
            raise ValueError("co-op orders: the grenade build writes other words than the move build")
        out = [(va, w, s, n if move[va] == w else
                "co-op orders: hold = a teammate throws a grenade there (%s), on the host" % r2_hold)
               for va, w, s, n in out]
    return out


def js_edits(v: dict) -> list:
    """With js_coop_orders; js_r2_hold (grnadeorder.js_mode) picks what a long press sends."""
    if not v.get("js_coop_orders"):
        return []
    from .grnadeorder import js_mode
    return edits(js_mode(v))


def cards(prefix: str = "js_", group: str = "Online") -> list:
    return [
        Setting(prefix + "coop_orders", "Online co-op: quick orders for your own AI", BOOL,
                False, group, confidence="experimental", requires={prefix + "coop_ai": [True]},
                help="Online, the quick-order button does nothing: the command map registers its "
                     "order handlers only outside multiplayer. With AI backup filling the "
                     "fireteams, this brings the quick order back in co-op games for your own "
                     "fireteam, as in split screen: aim at the ground and TAP it, and your two AI "
                     "switch between Hold (they stay put) and Advance (they follow you); HOLD it "
                     "and the marker appears after 0.4 s and follows your aim -- let go, and they "
                     "go to it and hold there, even when you walk away; tap to call them back. "
                     "A tap shows no marker and plays no button sound (the AI answer); the "
                     "click comes with the marker, not with the press. It works "
                     "for the host and the joiner alike: the order travels to the host as the "
                     "game's own 'set movement ROE' / 'add waypoint' messages. Single player and "
                     "other online modes are untouched.",
                caution="The tap was played (the AI answer 'holding' / 'affirmative'); the move-to "
                        "is not yet. Every player needs a disc with this option: a stock host "
                        "ignores the move-to and would not understand the toggle. The command "
                        "map (L1) stays view-only online."),
    ]


def selftest(js_elf=None) -> list:
    """[] = pass: stock table vs the executable, no VA twice, every edit has a stock word."""
    import struct
    fails = []
    for hold in ("move", "frag"):
        e = edits(hold)
        if len({va for va, *_ in e}) != len(e):
            fails.append("duplicate VA")
        for va, _w, s, _n in e:
            if JS_STOCK.get(va) != s:
                fails.append("%08x: edit stock %08x, table %s" % (va, s, JS_STOCK.get(va)))
    if js_elf is not None:
        for table in (JS_STOCK, JS_CONTEXT):
            for va, want in table.items():
                got = struct.unpack_from("<I", js_elf, va - 0x00100000 + 0x100)[0]
                if got != want:
                    fails.append("stock %08x: disc %08x, recorded %08x" % (va, got, want))
        for va, want in JS_IDS.items():
            got = struct.unpack_from("<H", js_elf, va - 0x00100000 + 0x100)[0]
            if got != want:
                fails.append("id %08x: disc %04x, expected %04x" % (va, got, want))
    return fails

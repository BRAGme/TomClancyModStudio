"""Online co-op with AI backup: take over your fireteam's AI (Jungle Storm, SLUS-20820).

What the player gets
--------------------

In an online co-op game whose fireteams are filled with AI (the roster writer 0x00377180 with the
AI-backup fill), each human leads his own fireteam: the joiner Alpha, the host Bravo, Charlie is all
AI. With this option, on both consoles:

* **Death.** When your soldier dies you carry on as the next living AI of your own fireteam, as in
  single player and in ModStudio's split screen, instead of respawning at the insertion zone. When
  your fireteam has nobody left you take a living AI of a fireteam that has no human in it
  (Charlie); only when there is none does the lobby's rule apply (respawn if it allows it, otherwise
  you watch). You never take the other human's fireteam -- those are his backup.
* **SELECT** switches you to the next living AI of your fireteam (member order, wrapping), alive or
  lying dead before the automatic hand-over. With nobody free it does nothing.
* **SELECT on a teammate** (option `js_coop_select_aim`): when the HUD is naming a living AI of your
  fireteam under your reticle, SELECT takes him instead of the next in order.

Your fireteam is the one your soldier is in: after inheriting Charlie, Charlie is your fireteam
(SELECT cycles it, R2 orders it, its AI follow you). The soldier you leave becomes an AI of the host's
again; the one you take is yours on both consoles. Nothing changes outside online co-op (lobby type 2).

Why it did not happen online
----------------------------

The engine already moves a soldier between consoles, and both consoles already agree on it -- the
original developers built it for exactly this (GR has it under its symbol names; JS kept the code):

  SwitchFollowActor (IkeSimulationMgr vt+0x158, 0x003760C0)
      sends RequestControlAvatar 0x19 {char console, int new id, int old id} to the host.
  the host, HandleNewAvatar 0x19 (0x0036D960)
      takes it only if the new soldier is AI-controlled on the host (vt+0xF8, control type 1), and
      broadcasts AssignControlAvatar 0x1A to every console (MasterSendAll).
  every console, HandleNewAvatar 0x1A
      new soldier: owner = requesting console, control 0 there / 2 (network copy) elsewhere;
      old soldier: owner = host, control 1 (AI) on the host / 2 elsewhere; the requester sends
      itself LocalControlAvatar 0x1B (the state manager's avatar id, the camera's FollowHuman 0x1D);
      then ActivateUpdates 0x55, which recomputes every object's update interest from its owner
      (RSGameObjectMgr 0x0049E900 -> InitializeInterest 0x0049CC20), so the new owner starts
      sending that soldier's state and the host stops.

Three things kept it from running online:

1. **Death.** HandleFollowNextTeamMember (0x003744D0, the message 0x21 the dead soldier sends
   himself six seconds after dying) asks CheckForRespawn (0x00375070) first: with lobby respawns the
   player is respawned at the insertion zone and the take-over is never reached. Without respawns it
   goes on to FindNextTeamMember(AI only), which walks the whole platoon from the next fireteam on --
   Charlie for the host, but the host's fireteam for the joiner.
2. **SELECT.** SELECT is keycode 0x70 -> message 0x241 (quick select), whose only handler (the
   command map's, 0x002823C0) is never registered online: CommandMap::RegisterMessageHandlers stops
   at its multiplayer gate (0x00280EDC). Both consoles' RAM: key 0x70 -> 0x241, flags 0x120, and no
   handler object for 0x2823C0 on the heap.
3. **A latent crash in the hand-over itself.** Online, the host's RequestControlAvatar case adds
   one display-name payload (bool 1 + the old soldier's name: 5 payloads) but the AssignControlAvatar
   case reads two names, payload 4 and payload 5 (0x0036DE10: GetPayloadObject(5), no bounds check).
   The sixth pointer is past the end of the payload array; run on the host's RAM it is 0 and the
   RSUIString copy dereferences address 0xC. Split screen's own AssignControlAvatar sender (0x00367098)
   adds both names; single player and split screen (grsquad B5) send no names.

The patch
---------

  0x0036DA78  RequestControlAvatar case: `bnez v0, 0x36daa4` (InMultiplayerMode -> add names) ->
              nop. Online now sends "no names" (bool 0), as single player does; AssignControlAvatar
              then never reads payload 4 or 5. Only the online path changes (single player and split
              screen never took that branch).
  0x003745B4  HandleFollowNextTeamMember: `jal CheckForRespawn` -> `jal cd`. In online co-op, for
              my soldier (avatar 0 -- the one this console controls, whatever the camera shows), when
              the message is SELECT (payload 0 true: the key message's "pressed" flag) or he is out of
              action (payload 0 false: the death message): [SELECT with js_coop_select_aim: the AI
              under the reticle, `aim`] else the next living AI of his fireteam, through
              SwitchFollowActor, and return 1 (the handler then leaves, as after a respawn). SELECT
              with nobody left does nothing. Death with nobody left runs `lastman`: a living AI of a
              fireteam with no human (every member's 0x0037E330 == 1), else CheckForRespawn (the
              lobby's respawn), else ActivateObserverMode and return 0 -- the stock search that runs
              next then only watches (SwitchFollowActor sends RequestObserve 0x25 in observer mode).
              Outside online co-op, in observer mode, with no avatar, or a "death" message while my
              soldier is up: stock (CheckForRespawn with the handler's own soldier).
  0x00141B64  IkeInputMgr::MapInputForAction: `jal 0x125880` (after the last key binding) ->
              `jal csel`: online co-op binds keycode 0x70 (SELECT, every pad layout) to 0x21 with
              flags 0x180 -- exactly how the stock key 0xC3 is bound to 0x21 (on press, with the
              pressed bool) -- then makes the call it replaced.

"Next living AI of the fireteam" is the rules manager's fireteam (IIkeRulesMgr vt+0x134 with the
soldier's company +0x178, platoon +0x444, fireteam +0x448; members {id, active} at +0x0C, count
+0x10), walked from the soldier's member index (+0x44C) + 1, wrapping, skipping himself: active == 1
and IkeSimulationMgr's 0x0037E330 == 1 (AI-controlled here: on the joiner a host-owned network copy
that is not the host's avatar SimMgr+0x650). That is the test FindNextTeamMember makes.

"Under the reticle" (`aim`) is IkeSimulationMgr vt+0xA4 (0x0037AE80), the pick the HUD label
(0x00238A58) and single player's SELECT (0x002824E8) call: the soldier the HUD names -- in split
screen the per-player cache of it (SimMgr +0xA04 / +0xA08), online a fresh FindLineCollision from the
soldier's eye (+0x53C) along his look (+0x210), 0.75 x 60 m = 45 m (longer when zoomed). In third
person (grcamera) the camera looks along the same look from above his shoulder, so the soldier the
name label shows is the one SELECT takes. The target must be in my company, platoon and fireteam,
in action (SimHumanState +0x88 still FLT_MAX) and 0x0037E330 == 1; anything else -- nobody, an
enemy, the other player, a Charlie soldier, a dead one -- falls back to the next-in-order cycle.

Which soldiers: your own fireteam by SELECT (cycle or aim) and by death; Charlie (a fireteam with no
human) only when your fireteam is gone, which makes it yours; never the other human's fireteam (his
backup, and his fireteam AI take the first human in member order as their leader). Charlie is not
offered to SELECT, so switching never leaves your own AI leaderless; a death puts you in Charlie
only when your own fireteam is all down, so nobody is left behind. There Charlie's FireTeamAI takes
you as its human (its AI follow you) and R2 (grcooporders, from your soldier's +0x448) orders
Charlie. Once one player has Charlie it has a human, so the other never takes it. Respawns come
after Charlie: a respawn drops you at the insertion zone while backup soldiers are still standing.
Stock JS (and this module before the rule) took the next fireteam in platoon order: Charlie for
the host (hudbug_host.bin, disc 6C2F39B0), but the host's Bravo for the joiner.

Caves (inside the RWX load segment 0x00100000..0x00612900; written by no other option):
  0x00553E88..0x0055400B  lgAudAWriteVag's twin (97 words; no jump, branch, pointer or lui/addiu
                          pair reaches it in the executable or either overlay): `lastman`
  0x001849A0..0x00184A6B  a kernel-library routine's twin (51 words; likewise unreferenced):
                          `coop_on`, `csel`
  0x002A1190..0x002A140F  the last 160 words of the dead NewPS2Shortcut function 0x002A0970 (680
                          words): `aimnext` (0x002A1190, fixed), `aim`, `cd` (0x002A1270). Its one
                          reference is a jal from other NewPS2Shortcut code, and every chain up ends
                          in Update / Draw / the destructor, which run only with mInstance 0x00629278
                          set -- it is only ever stored with zero (grcooporders' and grsquad's proof;
                          scratchpad agent_takeover/deadnps.py redoes the reachability).

Both consoles should run a disc with this option. A patched host with a stock joiner is safe (the
joiner just keeps stock online rules); a stock host would still broadcast the name payloads.

Split screen: grsquad's handoff cave calls FindNextTeamMember(own fireteam, AI only) for both the
death hand-over and SELECT (grsquad 'orders' binds SELECT to 0x21 with the avatar id). With
`js_ss_select_aim` that call becomes `aimnext` (grsquad.js_edits(select_aim=...)), which for SELECT
(the handler's payload 0 true) asks `aim` first. Single player needs nothing: its SELECT is the
command map's quick select, which already takes the soldier under the reticle (the same pick).

GR note: IkeRulesMgr::HandleAIBackupRequest / IkeStateMgr::HandleAIBackupAssign (GR 0x0017B0D0 /
0x00185880, messages 0x128 / 0x129) are not a take-over: they are the lobby handshake for the AI
Backup option (the host approves or denies a player's request and broadcasts GameInfo +0x3BF). GR's
take-over online is the same RequestControlAvatar / AssignControlAvatar pair used here
(IkeSimulationMgr::SwitchFollowActor 0x00398450, HandleNewAvatar 0x0038FEE0), with the same
one-name-short request.

Verified in the RAM interpreter (scratchpad agent_takeover/emu_takeover.py, emu_autorespawn.py,
emu_mutants.py, emu_follow.py, emu_aim.py) over online host/joiner RAM and split-screen RAM. The take-
over itself played online 2026-09-29 (SELECT switching confirmed); the reticle pick and the Charlie
rule are not played yet.
"""

from __future__ import annotations

from .grasm import assemble
from .model import BOOL, Setting

CAVE, CAVE_END = 0x00553E88, 0x0055400C          # lgAudAWriteVag twin, 97 words: lastman
CAVE2, CAVE2_END = 0x001849A0, 0x00184A6C        # kernel-library twin, 51 words: coop_on, csel
CAVE_N, CAVE_N_END = 0x002A1190, 0x002A1410      # dead NewPS2Shortcut code, 160 words: aimnext, aim, cd
AIMNEXT = CAVE_N                                 # fixed entry point (grsquad's handoff cave calls it)
AIM_WORDS = 56                                   # aimnext + aim; cd follows at a fixed address
CD = CAVE_N + 4 * AIM_WORDS

HOOK_DEATH, HOOK_DEATH_STOCK = 0x003745B4, 0x0C0DD41C   # jal 0x375070 CheckForRespawn (slot: move a1, s2)
HOOK_MAP, HOOK_MAP_STOCK = 0x00141B64, 0x0C049620       # jal 0x125880 (slot: nop)
NAMES, NAMES_STOCK = 0x0036DA78, 0x1440000A             # bnez v0, 0x36daa4 (online: add names)

SYMS = dict(
    STATE=0x00124620,        # IIkeStateMgr::Get (vt+0x9C InMultiplayerMode, +0xA4 observer, +0x150 game
                             #   info, +0x120 ActivateObserverMode)
    STATE_RS=0x00125880,     # IRSGameStateMgr::Get: the call MapInputForAction makes at the hook
    RULES=0x00124610,        # IIkeRulesMgr::Get (vt+0x114 fireteams in a platoon, vt+0x134 GetFireTeam)
    INPUT=0x0019B0A0,        # RSInput::GetInputHandler (vt+0x30 MapKey(key, msg, flags, alt))
    AVATAR=0x0036D5B0,       # IkeSimulationMgr: SimHuman of avatar a1 (0 = mine), or 0
    FREE=0x0037E330,         # IkeSimulationMgr: 1 = AI-controlled here (free to take), 0 me, 2 another human
    CHECKRESPAWN=0x00375070,
    FINDNEXT=0x003746F0,     # IkeSimulationMgr::FindNextTeamMember (split screen's own-fireteam search)
    FLTMAX=0x005973F8,       # FLT_MAX: SimHumanState +0x88 while the soldier is in action
    KEY_SELECT=0x70, MSG_FOLLOWNEXT=0x21, KEY_FLAGS=0x180,
)

SRC_CD = """
; ---- cd: HandleFollowNextTeamMember's CheckForRespawn(a0 = IkeSimulationMgr, a1 = the soldier)
cd:
    addiu sp, sp, -0x80
    sd    ra, 0x70(sp)
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s2, 0x20(sp)
    sq    s3, 0x30(sp)
    sq    s4, 0x40(sp)
    sq    s5, 0x50(sp)
    sq    s6, 0x60(sp)
    move  s0, a0                    ; IkeSimulationMgr
    sw    a1, 0x7c(sp)              ; the handler's soldier (its camera's leader), for the stock call
    jal   coop_on
    lbu   s5, 0xef(sp)              ; the handler's payload 0 (its sp+0x6F): 1 SELECT, 0 death
    beqz  v0, cd_stock
    lw    t9, 0(v1)
    lw    t9, 0xa4(t9)              ; observer mode: stock (it follows other players)
    jalr  t9
    move  a0, v1
    bnez  v0, cd_stock
    move  a0, s0
    jal   AVATAR                    ; my soldier: avatar 0, wherever the camera is
    move  a1, zero
    beqz  v0, cd_stock
    move  s1, v0
    bnez  s5, cd_sel                ; SELECT: alive or dead
    lw    t9, 0(s1)
    lw    t9, 0x29c(t9)             ; IsOutOfAction
    jalr  t9
    move  a0, s1
    beqz  v0, cd_stock              ; a "death" for a soldier who is up: stock
    nop
{DEATH_SKIP}
cd_sel:
{AIM_CALL}
cd_find:
    jal   RULES
    nop
    lw    t9, 0(v0)
    move  a0, v0
    lw    a1, 0x178(s1)             ; company
    lw    a2, 0x444(s1)             ; platoon
    lw    t9, 0x134(t9)             ; the fireteam
    jalr  t9
    lw    a3, 0x448(s1)             ; fireteam
    beqz  v0, cd_none
    lw    s2, 0x10(v0)              ; members
    lw    s3, 0x0c(v0)              ; {id, active} x members
    lw    s4, 0x44c(s1)             ; my member index
    li    s6, 1                     ; steps past me
cd_loop:
    sltu  t0, s6, s2
    beqz  t0, cd_none               ; round the fireteam: nobody
    addu  t1, s4, s6
    sltu  t0, t1, s2
    bnez  t0, cd_m
    sll   t2, t1, 3
    subu  t1, t1, s2                ; wrap
    sll   t2, t1, 3
cd_m:
    addu  t2, s3, t2
    lbu   t0, 4(t2)                 ; active
    li    t3, 1
    bne   t0, t3, cd_next
    lw    a1, 0(t2)                 ; his id
    sw    a1, 0x78(sp)
    jal   FREE
    move  a0, s0
    li    t0, 1
    beq   v0, t0, cd_take           ; AI-controlled here: free
    lw    a1, 0x78(sp)
cd_next:
    b     cd_loop
    addiu s6, s6, 1
cd_take:
    lw    t9, 0(s0)
    lw    a2, 0x128(s1)             ; my id
    lw    t9, 0x158(t9)             ; SwitchFollowActor: RequestControlAvatar to the host
    jalr  t9
    move  a0, s0
    b     cd_out
    li    v0, 1
cd_none:
    bnez  s5, cd_out                ; SELECT with nobody free: nothing
    li    v0, 1
    move  a0, s0                    ; death, my fireteam is gone: Charlie, respawn, watch
    lw    a1, 0x7c(sp)
    jal   lastman
    move  a2, s1
    b     cd_out
    nop
cd_stock:
    move  a0, s0
    jal   CHECKRESPAWN              ; the call this replaced; its answer is ours
    lw    a1, 0x7c(sp)
cd_out:
    ld    ra, 0x70(sp)
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    lq    s3, 0x30(sp)
    lq    s4, 0x40(sp)
    lq    s5, 0x50(sp)
    lq    s6, 0x60(sp)
    jr    ra
    addiu sp, sp, 0x80
"""

#: SELECT with js_coop_select_aim: the soldier under the reticle before the cycle
AIM_CALL = """
    move  a0, s0
    jal   AIM                       ; the living AI of my fireteam under my reticle, first
    move  a1, s1
    bgez  v0, cd_take
    move  a1, v0
"""
DEATH_SKIP = """
    b     cd_find                   ; (a death does not aim)
    nop
"""

SRC_LASTMAN = """
; ---- lastman(a0 = IkeSimulationMgr, a1 = the handler's soldier, a2 = me): I died and my fireteam
;      has no living AI. A fireteam without a human (Charlie) first, then the lobby's respawn
;      (CheckForRespawn), then watch -- never another human's fireteam.
lastman:
    addiu sp, sp, -0x80
    sd    ra, 0x70(sp)
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s2, 0x20(sp)
    sq    s3, 0x30(sp)
    sq    s4, 0x40(sp)
    sq    s5, 0x50(sp)
    sq    s6, 0x60(sp)
    move  s0, a0                    ; IkeSimulationMgr
    sw    a1, 0x78(sp)              ; the handler's soldier
    jal   RULES
    move  s1, a2                    ; me
    move  s2, v0                    ; the rules manager
    lw    t9, 0(v0)
    lw    t9, 0x114(t9)             ; fireteams in my platoon
    move  a0, v0
    lw    a1, 0x178(s1)
    jalr  t9
    lw    a2, 0x444(s1)
    move  s3, v0                    ; fireteam index, counted down
lm_team:
    addiu s3, s3, -1
    bltz  s3, lm_none
    lw    t0, 0x448(s1)
    beq   s3, t0, lm_team           ; mine: nobody left there
    lw    t9, 0(s2)
    lw    t9, 0x134(t9)             ; the fireteam
    move  a0, s2
    lw    a1, 0x178(s1)
    lw    a2, 0x444(s1)
    jalr  t9
    move  a3, s3
    beqz  v0, lm_team
    lw    s4, 0x10(v0)              ; members, counted down
    lw    s5, 0x0c(v0)              ; {id, active} x members
    li    s6, -1                    ; a living AI of this fireteam
lm_mem:
    addiu s4, s4, -1
    bltz  s4, lm_got
    sll   t0, s4, 3
    addu  t0, s5, t0
    lw    a1, 0(t0)                 ; his id
    lbu   t1, 4(t0)                 ; active
    sw    a1, 0x7c(sp)
    sw    t1, 0x74(sp)
    jal   FREE
    move  a0, s0
    li    t0, 1
    bne   v0, t0, lm_team           ; a human in this fireteam: it is his, not mine
    lw    t0, 0x74(sp)
    beqz  t0, lm_mem                ; dead
    nop
    b     lm_mem
    lw    s6, 0x7c(sp)
lm_got:
    bltz  s6, lm_team
    lw    t9, 0(s0)
    lw    t9, 0x158(t9)             ; SwitchFollowActor: RequestControlAvatar to the host
    move  a0, s0
    move  a1, s6
    jalr  t9
    lw    a2, 0x128(s1)
    b     lm_out
    li    v0, 1
lm_none:
    move  a0, s0
    jal   CHECKRESPAWN              ; the lobby's respawn
    lw    a1, 0x78(sp)
    bnez  v0, lm_out
    nop
    jal   STATE
    nop
    lw    t9, 0(v0)
    lw    t9, 0x120(t9)             ; ActivateObserverMode: the stock search that follows only watches
    jalr  t9
    move  a0, v0
    move  v0, zero
lm_out:
    ld    ra, 0x70(sp)
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    lq    s3, 0x30(sp)
    lq    s4, 0x40(sp)
    lq    s5, 0x50(sp)
    lq    s6, 0x60(sp)
    jr    ra
    addiu sp, sp, 0x80
"""

SRC_AIM = """
; ---- aimnext(a0 = IkeSimulationMgr, a1 = &id, a2): split screen's FindNextTeamMember call in
;      grsquad's handoff cave (whose sp is the handler's; the soldier is the handler's s2). For
;      SELECT (the handler's payload 0 true) the soldier under the reticle first.
aimnext:
    addiu sp, sp, -0x20
    sd    ra, 0x10(sp)
    sw    a0, 0x00(sp)
    lbu   t0, 0x8f(sp)              ; the handler's sp+0x6F: 1 SELECT, 0 death
    beqz  t0, an_next
    sw    a1, 0x04(sp)
    jal   aim
    move  a1, s2
    bltz  v0, an_next
    lw    a1, 0x04(sp)
    sw    v0, 0(a1)
    b     an_out
    li    v0, 1
an_next:
    lw    a0, 0x00(sp)
    lw    a1, 0x04(sp)
    jal   FINDNEXT
    li    a2, 2                     ; own fireteam, AI only (grsquad B3)
an_out:
    ld    ra, 0x10(sp)
    jr    ra
    addiu sp, sp, 0x20

; ---- aim(a0 = IkeSimulationMgr, a1 = my soldier): v0 = id of the soldier the HUD names under my
;      reticle (IkeSimulationMgr vt+0xA4, the pick the label and single player's SELECT use) when
;      he is a living AI of my own fireteam, else -1
aim:
    addiu sp, sp, -0x30
    sd    ra, 0x20(sp)
    sw    a0, 0x00(sp)
    sw    a1, 0x04(sp)
    lw    t9, 0(a0)
    lw    t9, 0xa4(t9)              ; the reticle pick: his SimHuman + 0x148, or 0
    addiu a1, a1, 0x148
    addiu a2, sp, 0x08              ; same company (unused)
    jalr  t9
    addiu a3, sp, 0x0c              ; distance (unused)
    beqz  v0, aim_no
    lw    t2, 0x04(sp)              ; me
    lw    t0, 0x30(v0)              ; his company (+0x178)
    lw    t1, 0x178(t2)
    bne   t0, t1, aim_no
    lw    t0, 0x2fc(v0)             ; platoon (+0x444)
    lw    t1, 0x444(t2)
    bne   t0, t1, aim_no
    lw    t0, 0x300(v0)             ; fireteam (+0x448)
    lw    t1, 0x448(t2)
    bne   t0, t1, aim_no
    lw    t0, 0xf4(v0)              ; SimHumanState +0x88: FLT_MAX while he is up
    lui   at, %hi(FLTMAX)
    lw    t1, %lo(FLTMAX)(at)
    bne   t0, t1, aim_no
    lw    a1, -0x20(v0)             ; his id (+0x128)
    lw    a0, 0x00(sp)
    jal   FREE                      ; 1: AI-controlled here (not me, not a human)
    sw    a1, 0x10(sp)
    li    t0, 1
    beq   v0, t0, aim_out
    lw    v0, 0x10(sp)
aim_no:
    li    v0, -1
aim_out:
    ld    ra, 0x20(sp)
    jr    ra
    addiu sp, sp, 0x30
"""

SRC_AUX = """
; ---- coop_on: v0 = 1 in an online co-op game (InMultiplayerMode, lobby type 2); v1 = IkeStateMgr
coop_on:
    addiu sp, sp, -0x20
    sd    ra, 0x10(sp)
    sq    s0, 0x00(sp)
    jal   STATE
    nop
    move  s0, v0
    lw    t9, 0(v0)
    lw    t9, 0x9c(t9)              ; InMultiplayerMode
    jalr  t9
    move  a0, s0
    beqz  v0, co_out
    lw    t9, 0(s0)
    lw    t9, 0x150(t9)             ; game info
    jalr  t9
    move  a0, s0
    lw    v0, 0x2cc(v0)             ; lobby type
    xori  v0, v0, 2
    sltiu v0, v0, 1                 ; 2 = co-op
co_out:
    move  v1, s0
    ld    ra, 0x10(sp)
    lq    s0, 0x00(sp)
    jr    ra
    addiu sp, sp, 0x20

; ---- csel: MapInputForAction's last `jal 0x125880`; online co-op: SELECT -> FollowNextTeamMember
csel:
    addiu sp, sp, -0x10
    sd    ra, 0x00(sp)
    jal   coop_on
    nop
    beqz  v0, cs_out
    nop
    jal   INPUT
    nop
    lw    t9, 0(v0)
    lw    t9, 0x30(t9)              ; MapKey(key, msg, flags, alt)
    move  a0, v0
    li    a1, KEY_SELECT
    li    a2, MSG_FOLLOWNEXT
    li    a3, KEY_FLAGS             ; on press, with the pressed bool (as stock binds key 0xC3)
    jalr  t9
    li    t0, -1
cs_out:
    ld    ra, 0x00(sp)
    j     STATE_RS                  ; the call this replaced (v0 = the state manager)
    addiu sp, sp, 0x10
"""

_CAVE_STOCK_HEX = (   # 0x00553E88..0x0055400B, lgAudAWriteVag twin (after grcooporders' cave)
    "27BDFFB0 3C030058 FFB00010 2470C614 FFB20020 00E0902D FFB30028 00C0982D"
    "FFB40030 0080A02D FFB50038 00A0A82D FFB10018 3C028000 FFB60040 2408FFFF"
    "FFBF0048 8E030000 10680044 3442000A 16600003 3C04005A 1000000A 2484F9E8"
    "12400006 3C020058 8E440000 8C43C604 0064182A 10600008 3C020069 3C04005A"
    "2484FA18 0C05ADDE 00000000 3C028000 10000032 34420004 24561240 0C05F628"
    "02C0202D 10400006 3C04005A 0C05ADDE 2484FA50 3C028000 10000028 34420008"
    "8E040000 3C100058 2610C60C 0C05E8C8 3C110069 8E020000 263113F0 0260282D"
    "AC54000C 8E430000 A0550012 AC430020 AE330000 AE320004 8E040000 8C860020"
    "0C05A8D6 24840030 8E070000 8E480000 3C0B0055 02C0202D 256B4EA0 2508003F"
    "24050015 00084103 24060001 00084100 00E0482D 240A0030 0C05F5AA AFB10000"
    "50400007 DFB00010 AE400000 3C04005A 0C05ADDE 2484FA90 3C028000 DFB00010"
    "DFB10018 DFB20020 DFB30028 DFB40030 DFB50038 DFB60040 DFBF0048 03E00008"
    "27BD0050"
)
_CAVE2_STOCK_HEX = (  # 0x001849A0..0x00184A6B, a kernel-library routine twin (calls 0x183320/0x183378)
    "27BDFFB0 FFB10010 0080882D FFB20020 FFB00000 00111282 FFB30030 00A0902D"
    "FFBF0040 0C060CC8 00028180 06200009 0040982D 8E030008 322203FF 14430005"
    "3C020057 244265F8 8C43001C 54710007 8E02000C 12600016 2402FFFF 0C060CDE"
    "00000000 10000012 2402FFFF 30420001 10400009 DE110018 0C061118 00000000"
    "DE030010 FE120018 0043182F FE020010 10000002 0223882D FE120018 12600004"
    "0220102D 0C060CDE 00000000 0220102D DFBF0040 DFB30030 DFB20020 DFB10010"
    "DFB00000 03E00008 27BD0050"
)
_CAVE_N_STOCK_HEX = (  # 0x002A1190..0x002A140F, the last 160 words of the dead NewPS2Shortcut
                       # function 0x002A0970 (680 words; reached only from dead code)
    "0C10D82C 00A0402D 0C07F308 00000000 0040882D 0C04D674 27A40178 0220202D"
    "0040282D 4600AB06 27A600D0 4600A346 0280382D 0000402D 0000482D 0C08657C"
    "0000502D 27A400D0 0C10D84C 2405FFFF 1000003F 8EA40024 0C0A7C08 0200282D"
    "10400028 26A40030 240500FF 27A400C0 00A0302D 0000382D 0C10D82C 00A0402D"
    "26A40030 0260282D 0C09AE4C 27A600C0 27A400C0 0C10D84C 2405FFFF 240500FF"
    "27A400B0 00A0302D 0000382D 0C10D82C 00A0402D 0C07F308 00000000 0040882D"
    "0C04D674 27A40178 0220202D 0040282D 4600AB06 27A600B0 4600A346 0280382D"
    "0000402D 0000482D 0C08657C 0000502D 27A400B0 0C10D84C 2405FFFF 10000013"
    "00000000 0260282D 0C09AE4C 27A60150 0C07F308 00000000 0040882D 0C04D674"
    "27A40178 0220202D 0040282D 4600AB06 27A60150 4600A346 0280382D 0000402D"
    "0000482D 0C08657C 0000502D 8EA40024 0C0A7F58 00000000 16420008 0200282D"
    "3C023F80 26A40030 44826000 0C09AD50 0260282D 10000027 00000000 0C0A7B84"
    "24040001 10400008 3C010059 3C010059 26A40030 C42CD288 0C09AD50 0260282D"
    "1000001C 00000000 26A40030 C42CD290 0C09AD50 0260282D 10000016 00000000"
    "0C0A7F58 8EA40024 16420008 3C010059 3C023F80 26A40030 44826000 0C09AD50"
    "0260282D 1000000B 00000000 26A40030 C42CD288 0C09AD50 0260282D 10000005"
    "00000000 26A40030 C42CD288 0C09AD50 0260282D 27A40178 0C1005B4 2405FFFF"
    "26730001 2A620032 1440FD9D 02A0202D 27A40150 0C10D84C 2405FFFF 27A40160"
    "0C10D84C 2405FFFF DFBF00A0 C7B50004 7BBE0090 C7B40000 7BB70080 7BB60070"
    "7BB50060 7BB40050 7BB30040 7BB20030 7BB10020 7BB00010 03E00008 27BD0180"
)


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


JS_STOCK = _stock_words(CAVE, _CAVE_STOCK_HEX)
JS_STOCK.update(_stock_words(CAVE2, _CAVE2_STOCK_HEX))
JS_STOCK.update(_stock_words(CAVE_N, _CAVE_N_STOCK_HEX))
JS_STOCK[HOOK_DEATH] = HOOK_DEATH_STOCK
JS_STOCK[HOOK_MAP] = HOOK_MAP_STOCK
JS_STOCK[NAMES] = NAMES_STOCK

_ENDS = {CAVE: CAVE_END, CAVE2: CAVE2_END, CAVE_N: CD, CD: CAVE_N_END}


def _fit(base, words, what):
    if base + 4 * len(words) > _ENDS[base]:
        raise ValueError("%s outgrows the cave at %#x (%d words, room %d)"
                         % (what, base, len(words), (_ENDS[base] - base) // 4))
    return words


def aim_routines():
    """[(base, words)], labels: aimnext + aim at CAVE_N (fixed; grsquad calls AIMNEXT)."""
    words, labels = assemble(SRC_AIM, CAVE_N, SYMS)
    assert labels["aimnext"] == AIMNEXT and len(words) == AIM_WORDS, len(words)
    return [(CAVE_N, _fit(CAVE_N, words, "aimnext/aim"))], labels


def takeover_routines(select_aim: bool = False):
    """[(base, words)], labels: cd (CD, after the aim routines), lastman (CAVE), coop_on + csel
    (CAVE2)."""
    aux, la = assemble(SRC_AUX, CAVE2, SYMS)
    lm, ll = assemble(SRC_LASTMAN, CAVE, SYMS)
    _w, lai = assemble(SRC_AIM, CAVE_N, SYMS)
    src = SRC_CD.replace("{AIM_CALL}", AIM_CALL if select_aim else "").replace(
        "{DEATH_SKIP}", DEATH_SKIP if select_aim else "")
    cd, lc = assemble(src, CD, dict(SYMS, coop_on=la["coop_on"], lastman=ll["lastman"], AIM=lai["aim"]))
    return ([(CD, _fit(CD, cd, "cd")), (CAVE, _fit(CAVE, lm, "lastman")),
             (CAVE2, _fit(CAVE2, aux, "coop_on/csel"))], dict(lc, **ll, **la))


def edits(takeover: bool = True, coop_aim: bool = False, aim: bool = None):
    """(va, value, stock, note). `takeover`: the online co-op take-over; `coop_aim`: its SELECT
    asks the reticle first; `aim`: the aim routines (default: whenever coop_aim) -- split screen
    needs them too (grsquad.js_edits(select_aim=True) calls AIMNEXT)."""
    out = []
    if aim is None:
        aim = coop_aim
    if takeover:
        pieces, labels = takeover_routines(select_aim=coop_aim)
        for base, words in pieces:
            out += [(base + 4 * i, w, JS_STOCK[base + 4 * i], "co-op take-over: routine")
                    for i, w in enumerate(words)]
        out.append((HOOK_DEATH, assemble("jal %#x" % labels["cd"], HOOK_DEATH)[0][0], HOOK_DEATH_STOCK,
                    "co-op take-over: on death / SELECT, the next living AI of your fireteam first"))
        out.append((HOOK_MAP, assemble("jal %#x" % labels["csel"], HOOK_MAP)[0][0], HOOK_MAP_STOCK,
                    "co-op take-over: online co-op binds SELECT to FollowNextTeamMember"))
        out.append((NAMES, 0x00000000, NAMES_STOCK,
                    "co-op take-over: online RequestControlAvatar sends no names (AssignControlAvatar "
                    "read one past them)"))
    if aim:
        pieces, _labels = aim_routines()
        for base, words in pieces:
            out += [(base + 4 * i, w, JS_STOCK[base + 4 * i], "SELECT takes the teammate under the "
                     "reticle: routine") for i, w in enumerate(words)]
    return out


def coop_aim_enabled(v: dict, prefix: str = "js_") -> bool:
    return bool(v.get(prefix + "coop_takeover") and v.get(prefix + "coop_select_aim"))


def ss_aim_enabled(v: dict, prefix: str = "js_") -> bool:
    """Split screen's SELECT-to-reticle: needs grsquad's handoff and orders (which bind SELECT)."""
    return bool(v.get(prefix + "ss_select_aim") and v.get(prefix + "ss_orders")
                and v.get(prefix + "ss_handoff") and v.get(prefix + "ss_fireteams"))


def js_edits(v: dict):
    return edits(takeover=bool(v.get("js_coop_takeover")), coop_aim=coop_aim_enabled(v),
                 aim=coop_aim_enabled(v) or ss_aim_enabled(v))


def cards(prefix: str = "js_", group: str = "Online") -> list:
    return [
        Setting(prefix + "coop_takeover", "Online co-op: take over your AI on death, SELECT switches",
                BOOL, False, group, confidence="experimental",
                requires={prefix + "coop_ai": [True]},
                help="With AI backup filling the fireteams, a player who dies online still "
                     "respawns at the insertion zone (or just watches), and SELECT does nothing. "
                     "With this option, when your soldier dies you carry on as the next living AI "
                     "of your own fireteam, as in single player; SELECT switches you between your "
                     "fireteam's living soldiers. When your fireteam has nobody left you take over "
                     "an AI of the all-AI fireteam (Charlie), which then follows you and takes your "
                     "orders; only when that is gone too does the lobby's respawn rule apply. You "
                     "never take the other player's soldiers. It works for the host and the joiner: "
                     "the switch goes through the game's own 'request / assign control' messages, "
                     "so both consoles agree who controls which soldier. Single player, split "
                     "screen and other online modes are untouched.",
                caution="SELECT switching confirmed online 2026-09-29; the Charlie rule is new and "
                        "not played. Every player needs a disc with this option: it also fixes a "
                        "hand-over message that read past its end online."),
        Setting(prefix + "coop_select_aim", "Online co-op: SELECT takes the teammate you aim at",
                BOOL, False, group, confidence="experimental",
                requires={prefix + "coop_takeover": [True]},
                help="Point your reticle at one of your own fireteam's AI -- the one the HUD is "
                     "naming -- and SELECT switches straight to him. Not aiming at one (nobody, an "
                     "enemy, the other player, a Charlie soldier, a dead man), SELECT cycles your "
                     "fireteam as before. The target is the soldier the name label shows, up to "
                     "45 m (further when zoomed), in first and third person.",
                caution="Not played. Checked by running the game's own reticle pick over online RAM."),
    ]


#: jungle_storm.py's split-screen card (the Split Screen group lives there, beside js_ss_orders)
SS_CARD = dict(key="js_ss_select_aim", label="SELECT takes the teammate you aim at",
               group="Split Screen", requires={"js_ss_orders": True},
               help="With Team orders: point your crosshair at one of your own fireteam's Ghosts "
                    "-- the one the HUD is naming -- and SELECT switches straight to him. Not "
                    "aiming at one (nobody, an enemy, the other player or his fireteam, a dead "
                    "man), SELECT switches to the next living Ghost as before. Death hand-offs "
                    "are unchanged.",
               caution="Checked in the RAM interpreter on two split-screen savestates, both "
                       "players; never played.")


def selftest(js_elf=None) -> list:
    """Every stock word against the executable, no address twice, the hooks' targets. [] = pass."""
    import struct
    fails = []
    for combo in ((True, False, False), (True, True, None), (False, False, True), (True, False, True)):
        e = edits(*combo)
        if len({va for va, *_ in e}) != len(e):
            fails.append("duplicate VA %s" % (combo,))
        for va, _w, stock, _n in e:
            if JS_STOCK.get(va) != stock:
                fails.append("%08x: edit stock %08x, table %s" % (va, stock, JS_STOCK.get(va)))
    if js_elf is not None:
        for va, want in JS_STOCK.items():
            got = struct.unpack_from("<I", js_elf, va - 0x00100000 + 0x100)[0]
            if got != want:
                fails.append("stock %08x: disc %08x, recorded %08x" % (va, got, want))
    return fails

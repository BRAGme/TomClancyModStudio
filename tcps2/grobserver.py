"""Split-screen observer: Jungle Storm (SLUS-20820) and Ghost Recon (SLUS-20613).

With "One life" (grsquad's handoff) a dead player carries on as a living
Ghost from his own fireteam. When that fireteam has nobody left, the handoff
finds no one and returns: the fade clears after six seconds, the camera stays
on the body and every button is ignored until the mission ends. This option
turns that half of the screen into an observer instead:

  - it follows a living soldier of the platoon -- either fireteam, the other
    player's soldier and every AI, total-war copies included -- in squad order
    (fireteam * 8 + member, as grselcopy orders them), starting after the dead
    player's own soldier;
  - X moves it on to the next living soldier (the reload and next-item
    messages, so X on every layout, and square too);
  - when the watched soldier dies, it moves on by itself;
  - the half reads "Player N : OBSERVER MODE" (the stock "Player N : Dead"
    label with the word changed; that label only ever appears here, because
    the handoff's B7 skips the code that set it before).

Only that player's view moves. The camera change is the stock split-screen
one: FollowHuman (0x1D) for player 1 or FollowHuman2 (0x1E) for player 2 with
the soldier's id, the message stock split screen sends after every change of
soldier (IkeSimulationMgr::HandleNewAvatar, 0x0036D960). Its handlers act on
one player only: SimCamera::HandleFollowHuman (0x0038AFC0) sets the leader of
the camera with that index (+0x1A8) and nothing else in split screen, the
state manager keeps the watched id per player (0x004A4230, read back as
GetObserverID), the HUD panel keeps one per player (0x00269110). The online
observer mode is not used: its global flag (state manager +0x1F4) takes the
controls from both players and its HUD is full-screen and player 1's.

Control stays with the dead soldier: the input layer tags a press with that
player's avatar id, and the dead soldier's SimHuman::ProcessMessage drops
every message but fire (0x003A5C3C) -- that drop is where X is caught. No
state lives outside the mission's own objects: "watching" is SimHuman +0x634
on the dead player's soldier (the "out for good" flag the label reads,
zeroed by the constructor, set in split screen only by the code B7 skips),
and the dead soldier's +0x63C says whose he was (1 or 2, set at death).

Hooks (none written by any other option):

  0x00199B2C  grsquad's handoff cave, "nobody left" -> obs_enter (in grsquad)
  0x003A5C44  ProcessMessage, dead soldier, not fire: b 0x3a730c -> j obs_key
  0x00387904  SimCamera::UpdateMovement: jal IsObserver -> jal obs_tick
  0x003BE38C  the split-screen status label: token "Dead" -> "OBSERVER MODE"
  0x003BE43C  (its player-2 twin)

Caves: three SIF RPC wrappers that no code, pointer, address pair or overlay
reaches (0x001816F8 60 words, 0x00198A18 56, 0x001815E0 32) and the three
words of the dead lzo1x_decompress_safe after grsquad's handoff cave
(0x00199B54). The squad walk tries 32 keys (four fireteams) because the
rules manager's GetFireTeam answers 0 past the last one.

Checked in the RAM interpreter on eight split-screen savestates, both
players (scratchpad agent_obs2/test_all.py): the wipe-out, X cycling, the
watched soldier dying, the other half untouched. Not yet played.

Ghost Recon: the same routines, below the Jungle Storm half (no label; see
there). No Ghost Recon split-screen savestate exists, so they were checked
on a single-player mission save turned into split screen the way the game
builds it (agent_obs2/gr_test.py): the same scenarios, both players.
"""

from __future__ import annotations

from .grasm import assemble

CAVE_A, CAVE_A_END = 0x001816F8, 0x001817E8      # unreferenced SIF RPC wrapper, 60 words
CAVE_B, CAVE_B_END = 0x00198A18, 0x00198AF8      # 56 words
CAVE_C, CAVE_C_END = 0x001815E0, 0x00181660      # 32 words
CAVE_D, CAVE_D_END = 0x00199B54, 0x00199B60      # lzo1x_decompress_safe, after grsquad's handoff cave

#: grsquad's handoff cave branches here when the dead player's fireteam has nobody left
ENTER = CAVE_D

HOOK_KEY, HOOK_KEY_STOCK = 0x003A5C44, 0x100005B1      # b 0x3a730c (delay: ld ra, 0x50(sp))
HOOK_TICK, HOOK_TICK_STOCK = 0x00387904, 0x0C0E1FA8    # jal 0x387ea0 (IsObserver)
LABEL = ((0x003BE38C, 0x34460250), (0x003BE43C, 0x34460250))   # ori a2, v0, 0x250 ("Dead")
LABEL_NEW = 0x344602E5                                          # ori a2, v0, 0x2e5 ("OBSERVER MODE")

SYMS = dict(
    RULES=0x00124610,       # IIkeRulesMgr::Get
    OBJMGR=0x0014A7E0,      # IIkeObjectMgr::Get (vt+0x38: SimHuman + 0x1B0 for an id, 0 for -1)
    STATEP=0x00684A78,      # IRSGameStateMgr*; GetAvatarID(i) reads +0x200 + 4i of it
    SIMMGR=0x0062B8D0,      # IkeSimulationMgr*; cameras at +0x444 (player 1) / +0x448 (player 2)
    COMPANY=0x0057A1C8, PLATOON=0x0057A1D0,   # the players' squad
    CREATE=0x00498FD0,      # RSGameMessage::Create(Us)
    ADDINT=0x00136A20,      # RSGameMessage::AddPayload(int)
    SENDLOC=0x002077D0,     # IRSGameMessageMgr::SendLocal(Uc, msg) -- HandleNewAvatar's call
    RELEASE=0x00124AE0,     # RSObject::Release
    GETBOOL=0x00141FA0,     # RSGameMessage::GetPayload(i, bool&)
    ISOBS=0x00387EA0,       # the call obs_tick stands in for
    HOF_RET=0x003746D0,     # HandleFollowNextTeamMember's epilogue
    PM_RET=0x003A7308,      # SimHuman::ProcessMessage's epilogue (ld ra ...)
)

#: squad keys walked: fireteam * 8 + member for up to four fireteams. The
#: rules manager's GetFireTeam answers 0 past the platoon's last fireteam
#: (an unsigned bounds check, 0x0012ACF0), and no fireteam grows past 6.
KEYS = 32

# obs_advance: a0 = player (0/1), a1 = the soldier to start after. Points that
# player's camera at the next living platoon soldier after him in squad order,
# round the platoon once (himself last); nothing when nobody is alive. Living
# is the rules manager's active flag, the one FindNextTeamMember tests.
SRC_A = """
obs_advance:
    addiu sp, sp, -0x50
    sd    ra, 0x40(sp)
    sq    s0, 0x00(sp)
    sq    s2, 0x10(sp)
    sq    s3, 0x20(sp)
    sq    s4, 0x30(sp)
    move  s4, a0                    ; player
    lw    t0, 0x448(a1)             ; his fireteam
    lw    t1, 0x44c(a1)             ; his member
    sll   t0, t0, 3
    jal   RULES
    addu  s3, t0, t1                ; s3 = his key
    move  s0, v0                    ; s0 = the rules manager
    li    s2, KEYS                  ; s2 = keys left to try
oa_step:
    addiu s3, s3, 1
    slti  t0, s3, KEYS
    bnez  t0, oa_key
    addiu s2, s2, -1
    move  s3, zero                  ; round again
oa_key:
    bltz  s2, oa_out                ; once round: nobody alive
    lw    t9, 0(s0)
    lw    t9, 0x134(t9)             ; the fireteam (0 past the last one)
    lui   at, %hi(COMPANY)
    lw    a1, %lo(COMPANY)(at)
    lw    a2, %lo(PLATOON)(at)
    srl   a3, s3, 3
    jalr  t9
    move  a0, s0
    beqz  v0, oa_step
    andi  t1, s3, 7
    lw    t0, 0x10(v0)              ; members.count
    sltu  t0, t1, t0
    beqz  t0, oa_step
    lw    t0, 0xc(v0)               ; members: {id, active}, 8 bytes each
    sll   t1, t1, 3
    addu  t0, t0, t1
    lbu   t1, 4(t0)
    li    t2, 1
    bne   t1, t2, oa_step           ; not active: down
    lw    t3, 0(t0)                 ; (delay) his id
    move  s2, t3
    jal   CREATE
    addiu a0, s4, 0x1d              ; FollowHuman (player 1) / FollowHuman2 (player 2)
    move  s0, v0
    move  a0, v0
    jal   ADDINT
    move  a1, s2
    li    a0, 1
    jal   SENDLOC
    move  a1, s0
    jal   RELEASE
    move  a0, s0
oa_out:
    ld    ra, 0x40(sp)
    lq    s0, 0x00(sp)
    lq    s2, 0x10(sp)
    lq    s3, 0x20(sp)
    lq    s4, 0x30(sp)
    jr    ra
    addiu sp, sp, 0x50
"""

# obs_tick: a0 = camera, every frame from SimCamera::UpdateMovement. When the
# soldier the camera follows is down and the camera's player is watching (his
# own soldier carries obs_enter's mark), move on. Then the stock call.
# obs_enter2: the rest of obs_enter.
SRC_B = """
obs_tick:
    addiu sp, sp, -0x30
    sd    ra, 0x20(sp)
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    move  s0, a0
    lw    a0, 4(s0)                 ; the soldier this camera follows
    beqz  a0, ot_tail
    lw    s1, 0x1a8(s0)             ; (delay) camera index = player
    lw    t9, 0(a0)
    lw    t9, 0x29c(t9)
    jalr  t9                        ; out of action?
    nop
    sltiu t0, s1, 2
    and   t0, t0, v0
    beqz  t0, ot_tail               ; alive (every frame of normal play)
    sll   t0, s1, 2
    lui   at, %hi(STATEP)
    lw    t1, %lo(STATEP)(at)
    addu  t1, t1, t0
    jal   OBJMGR
    lw    a1, 0x200(t1)             ; (delay) GetAvatarID(player), -1 for none
    lw    t9, 0(v0)
    lw    t9, 0x38(t9)
    jalr  t9                        ; his SimHuman + 0x1B0
    move  a0, v0
    beqz  v0, ot_tail
    move  a0, s1
    lw    t0, 0x484(v0)             ; +0x634: obs_enter's mark, the player is watching
    beqz  t0, ot_tail
    nop
    jal   obs_advance
    lw    a1, 4(s0)                 ; (delay) from the fallen soldier
ot_tail:
    move  a0, s0
    ld    ra, 0x20(sp)
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    j     ISOBS
    addiu sp, sp, 0x30

obs_enter2:
    sltiu t0, s4, 2
    beqz  t0, oe_out                ; not a player's soldier: a SELECT with nobody to switch to
    li    t0, 1
    sw    t0, 0x634(s2)             ; watching (and the label reads OBSERVER MODE)
    move  a0, s4
    jal   obs_advance
    move  a1, s2
oe_out:
    j     HOF_RET
    nop
"""

# obs_key: from SimHuman::ProcessMessage (a0 = message id, s0 = message, s1 =
# the dead soldier; the hooked branch's delay slot has reloaded ra). X on a
# watching player's soldier: his camera moves on.
SRC_C = """
obs_key:
    li    t0, 0x139                 ; reload: X on layouts 1 and 3
    beq   a0, t0, ok_x
    li    t0, 0x137                 ; next item: X on layout 2
    bne   a0, t0, ok_ret
ok_x:
    lw    t0, 0x634(s1)             ; (delay) watching?
    beqz  t0, ok_ret
    lw    t0, 0x28(s0)              ; (delay) payloads: {avatar id, pressed}
    sltiu t0, t0, 2
    bnez  t0, ok_ret
    move  a0, s0
    li    a1, 1
    jal   GETBOOL
    addiu a2, sp, 0x7f              ; ProcessMessage's own bool slot, as its fire path uses it
    lbu   t0, 0x7f(sp)
    beqz  t0, ok_ret                ; let go
    lw    a0, 0x63c(s1)             ; (delay) player number, 1 or 2 (obs_enter marks no one else)
    addiu a0, a0, -1
    sll   t0, a0, 2
    lui   at, %hi(SIMMGR)
    lw    t1, %lo(SIMMGR)(at)
    addu  t1, t1, t0
    lw    t1, 0x444(t1)             ; that player's camera
    beqz  t1, ok_ret
    nop
    lw    a1, 4(t1)                 ; the soldier it follows
    beqz  a1, ok_ret
    nop
    jal   obs_advance
    nop
ok_ret:
    j     PM_RET
    nop
"""

# obs_enter: from grsquad's handoff cave when FindNextTeamMember found nobody
# in the dead player's fireteam. s1 = his id, s2 = his SimHuman, s3 =
# IkeSimulationMgr; HOF_RET restores s0-s4 and ra.
SRC_D = """
obs_enter:
    lw    s4, 0x63c(s2)             ; the player he died as: 1, 2 (0 = none)
    j     obs_enter2
    addiu s4, s4, -1
"""

PIECES = ((CAVE_A, CAVE_A_END, SRC_A), (CAVE_B, CAVE_B_END, SRC_B),
          (CAVE_C, CAVE_C_END, SRC_C), (CAVE_D, CAVE_D_END, SRC_D))

_STOCK_HEX = {
    CAVE_A: (
        "3C020057 27BDFFD0 8C435008 0080302D FFBF0020 04610003 FFB00010 10000030"
        "0000102D 90C20000 3C070062 24E388C0 A0620004 00021600 10400011 0000402D"
        "3C090062 3C100062 25080001 00000000 290200FC 1040000C 00C81021 24E388C0"
        "90440000 00681821 A0640004 00042600 5480FFF7 25080001 10000004 240200FC"
        "3C090062 3C100062 240200FC 55020005 ACE588C0 24E288C0 240800FB A04000FF"
        "ACE588C0 24E288C0 25248800 A04000FF 0040382D 25080005 AFA00000 24050003"
        "0000302D 26098840 240A0004 0C05F5AA 0000582D 04410002 8E028840 2402FFFF"
        "DFBF0020 DFB00010 03E00008 27BD0030"),
    CAVE_B: (
        "27BDFFF0 3C030057 24020001 FFBF0000 AC6268D4 8FAC0010 1080002A 8FAD0018"
        "2403FFFF 10A30004 0000202D 24020002 14A20022 00000000 10C30003 24020004"
        "14C2001E 00000000 10E30003 24020008 14E2001A 00000000 11030003 24020004"
        "15020016 00000000 11230003 24020004 15220012 00000000 11430003 24020004"
        "1542000E 00000000 11630003 24020004 1562000A 00000000 11830003 24020004"
        "15820006 00000000 11A30003 24020004 15A20002 00000000 24040001 14800003"
        "00000000 10000003 2402FFFF 0C06621C 00000000 DFBF0000 03E00008 27BD0010"),
    CAVE_C: (
        "3C020057 27BDFFD0 8C435008 0080382D FFBF0020 FFB00010 04600015 0000102D"
        "3C020062 3C040062 24438880 AC458880 AC670004 3C100062 AC660008 24848800"
        "0060382D 24050004 AFA00000 0000302D 2408000C 26098840 240A0004 0C05F5AA"
        "0000582D 04410002 8E028840 0000102D DFBF0020 DFB00010 03E00008 27BD0030"),
    CAVE_D: "2402FFF9 24020001 12420006",
}


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


JS_STOCK = {}
for _base, _hex in _STOCK_HEX.items():
    JS_STOCK.update(_stock_words(_base, _hex))
JS_STOCK[HOOK_KEY] = HOOK_KEY_STOCK
JS_STOCK[HOOK_TICK] = HOOK_TICK_STOCK
JS_STOCK.update(dict(LABEL))


def _local(src):
    return {ln.split(":")[0].strip() for ln in src.splitlines()
            if ln.strip() and not ln.startswith(" ") and ln.rstrip().endswith(":")}


def _build(pieces, syms):
    """({cave: words}, labels) for pieces [(cave, end, source)], labels resolved across caves."""
    labels = {}
    for base, _end, src in pieces:          # first pass: every label at its cave's start
        for name in _local(src):
            labels[name] = base
    for _ in range(2):                      # sizes are fixed, so the second pass is exact
        words, new = {}, {}
        for base, _end, src in pieces:
            others = {k: v for k, v in labels.items() if k not in _local(src)}
            w, lab = assemble(src, base, dict(syms, **others))
            words[base] = w
            new.update(lab)
        labels = new
    for base, end, _src in pieces:
        if base + 4 * len(words[base]) > end:
            raise ValueError("observer routine outgrows the cave at %#x (%d words, room %d)"
                             % (base, len(words[base]), (end - base) // 4))
    return words, labels


def build():
    """Jungle Storm: ({cave: words}, labels)."""
    words, labels = _build(PIECES, dict(SYMS, KEYS=KEYS))
    if labels["obs_enter"] != ENTER:
        raise ValueError("obs_enter moved: grsquad branches to %#x" % ENTER)
    return words, labels


def edits():
    """Jungle Storm (va, value, stock, note) -- the routines, the X and per-frame hooks, the
    label. The branch into obs_enter is grsquad's (js_edits(..., observer=True))."""
    words, labels = build()
    out = []
    for base, _end, _src in PIECES:
        out += [(base + 4 * i, w, JS_STOCK[base + 4 * i], "observer: routine")
                for i, w in enumerate(words[base])]
    out.append((HOOK_KEY, assemble("j %#x" % labels["obs_key"], HOOK_KEY)[0][0], HOOK_KEY_STOCK,
                "observer: X on a watching player's dead soldier moves his camera on"))
    out.append((HOOK_TICK, assemble("jal %#x" % labels["obs_tick"], HOOK_TICK)[0][0],
                HOOK_TICK_STOCK, "observer: the watched soldier went down -> next one"))
    for va, stock in LABEL:
        out.append((va, LABEL_NEW, stock, "observer: 'Player N : OBSERVER MODE'"))
    return out


def enabled(v: dict) -> bool:
    """The observer needs the handoff (and so the fireteams): grsquad must be
    told the same answer, js_edits(..., observer=enabled(v))."""
    return bool(v.get("js_ss_observer") and v.get("js_ss_handoff") and v.get("js_ss_fireteams"))


def js_edits(v: dict):
    return edits() if enabled(v) else []


# ---------------------------------------------------------------------------
# Ghost Recon (SLUS-20613)
# ---------------------------------------------------------------------------
#
# The same three routines under GR's names (research/code/symbols_gr.txt and the ELF's
# DWARF). Differences from Jungle Storm:
#
#   - no status label: GR's dead-player fade code (SimHuman::TriggleForBlackCamera,
#     0x003DEB70, driven by +0x608 mBlackScreenFlag, which Update sets on every dead
#     soldier) has no "Player N : Dead" line to reword, so the half just shows the view;
#   - the mark is SimHuman +0x634 mMachineGunFlag: zeroed by the constructor and read or
#     written by nothing else in the image (the live flag is +0x60C mMachineGunFalg);
#   - player number at death is +0x610 mMyAvatarID (ApplyDamage 0x003D5C78 / 0x003D5CA8);
#   - the squad walk takes company (+0x178) and platoon (+0x444) from the soldier it starts
#     after; GetFireTeam is IIkeRulesMgr vt+0x12C (0 past the last fireteam, 0x0017C580);
#   - X is reload 0xE1 / SelectNextItem 0xDF (MapInputForAction binds both for both pads);
#   - hooks: SimHuman::ProcessMessage's dead-soldier drop 0x003C7054 (b 0x3c8468),
#     SimCamera::UpdateMovement's second IsObserver call 0x003A7CA4, and grsquad's GR
#     handoff cave, whose "nobody left" word (j 0x396874 at 0x004309C4) jumps here instead.
#     At that word HandleFollowNextTeamMember (0x00396630) holds the dead soldier in s0,
#     his id in s1, IkeSimulationMgr in s3; its epilogue 0x00396874 restores s0-s4.
#
# Caves: seven of the ten RSArray<P RSArray<RSMemoryPoolNode<...Effect>>> destructors at
# 0x003FA850..0x003FAB50, 24 words each (each followed by a live 4-word constructor). No
# jal, j, branch, lui pair or data word reaches them except each one's own entry in the
# exception index (0x005DCE80.., {start, size, 0x6002}), which only describes the range.

GR_CAVES = (0x003FA850, 0x003FA8C0, 0x003FA930, 0x003FA9A0, 0x003FAA10, 0x003FAA80, 0x003FAAF0)
GR_CAVE_WORDS = 24
GR_DTOR_HEX = ("27BDFFD0 FFBF0020 7FB10010 7FB00000 70808E28 1220000C 70A08628 8E240000"
               "10800004 0010143C 0C040AF8 00000000 0010143C 0002143F 18400004 72201628"
               "0C040B14 72202628 72201628 DFBF0020 7BB10010 7BB00000 03E00008 27BD0030")
GR_HOOK_KEY, GR_HOOK_KEY_STOCK = 0x003C7054, 0x10000504      # b 0x3c8468 (delay: ld ra, 0x40(sp))
GR_HOOK_TICK, GR_HOOK_TICK_STOCK = 0x003A7CA4, 0x0C0EA088    # jal 0x3a8220 (IsObserver)
#: grsquad's GR handoff cave jumps here when the dead player's fireteam has nobody left
GR_ENTER = GR_CAVES[6]

GR_SYMS = dict(
    RULES=0x0035FD20,       # IIkeRulesMgr::Get
    OBJMGR=0x00366CE0,      # IIkeObjectMgr::Get (vt+0x38: SimHuman + 0x1B0 for an id, 0 for -1)
    STATEP=0x005DFF40,      # IRSGameStateMgr::mIStateMgr; GetAvatarID(i) reads +0x1F8 + 4i
    SIMMGR=0x005EACE8,      # IkeSimulationMgr::mIkeSimulationMgr; cameras at +0x444 / +0x448
    CREATE=0x00126A20,      # RSGameMessage::Create(Us)
    ADDINT=0x00359680,      # RSGameMessage::AddPayload(int)
    SENDLOC=0x0038A6A0,     # IRSGameMessageMgr::SendLocal(Uc, msg)
    RELEASE=0x0035DB20,     # RSObject::Release
    GETBOOL=0x0036CD30,     # RSGameMessage::GetPayload(i, bool&)
    ISOBS=0x003A8220,       # SimCamera::IsObserver, the call gobs_tick stands in for
    HOF_RET=0x00396874,     # HandleFollowNextTeamMember's epilogue
    PM_RET=0x003C8464,      # SimHuman::ProcessMessage's epilogue (ld ra ...)
    KEYS=KEYS,
)

GR_SRC = (
    # gobs_advance: a0 = player (0/1), a1 = the soldier to start after
    """
gobs_advance:
    addiu sp, sp, -0x60
    sd    ra, 0x40(sp)
    sq    s0, 0x00(sp)
    sq    s2, 0x10(sp)
    sq    s3, 0x20(sp)
    sq    s4, 0x30(sp)
    move  s4, a0                    ; player
    lw    t0, 0x178(a1)             ; his company
    sw    t0, 0x48(sp)
    lw    t0, 0x444(a1)             ; his platoon
    sw    t0, 0x4c(sp)
    lw    t0, 0x448(a1)             ; his fireteam
    lw    t1, 0x44c(a1)             ; his member
    sll   t0, t0, 3
    jal   RULES
    addu  s3, t0, t1                ; s3 = his key
    move  s0, v0                    ; s0 = the rules manager
    li    s2, KEYS                  ; s2 = keys left to try
ga_step:
    addiu s3, s3, 1
    slti  t0, s3, KEYS
    bnez  t0, ga_key
    addiu s2, s2, -1
    b     ga_key
    move  s3, zero                  ; round again
""",
    """
ga_key:
    bltz  s2, ga_out                ; once round: nobody alive
    lw    t9, 0(s0)
    lw    t9, 0x12c(t9)             ; the fireteam (0 past the last one)
    lw    a1, 0x48(sp)
    lw    a2, 0x4c(sp)
    srl   a3, s3, 3
    jalr  t9
    move  a0, s0
    beqz  v0, ga_step
    andi  t1, s3, 7
    lw    t0, 0x10(v0)              ; members.count
    sltu  t0, t1, t0
    beqz  t0, ga_step
    lw    t0, 0xc(v0)               ; members: {id, active}, 8 bytes each
    sll   t1, t1, 3
    addu  t0, t0, t1
    lbu   t1, 4(t0)
    li    t2, 1
    bne   t1, t2, ga_step           ; not active: down
    lw    t3, 0(t0)                 ; (delay) his id
    b     ga_found
    move  s2, t3
""",
    """
ga_found:
    jal   CREATE
    addiu a0, s4, 0x1d              ; FollowHuman (player 1) / FollowHuman2 (player 2)
    move  s0, v0
    move  a0, v0
    jal   ADDINT
    move  a1, s2
    li    a0, 1
    jal   SENDLOC
    move  a1, s0
    jal   RELEASE
    move  a0, s0
ga_out:
    ld    ra, 0x40(sp)
    lq    s0, 0x00(sp)
    lq    s2, 0x10(sp)
    lq    s3, 0x20(sp)
    lq    s4, 0x30(sp)
    jr    ra
    addiu sp, sp, 0x60
""",
    # gobs_tick: a0 = camera, every frame from SimCamera::UpdateMovement
    """
gobs_tick:
    addiu sp, sp, -0x30
    sd    ra, 0x20(sp)
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    move  s0, a0
    lw    a0, 4(s0)                 ; the soldier this camera follows
    beqz  a0, gt_tail
    lw    s1, 0x1a0(s0)             ; (delay) camera index = player
    lw    t9, 0(a0)
    lw    t9, 0x298(t9)
    jalr  t9                        ; out of action?
    nop
    sltiu t0, s1, 2
    and   t0, t0, v0
    beqz  t0, gt_tail               ; alive (every frame of normal play)
    sll   t0, s1, 2
    lui   at, %hi(STATEP)
    lw    t1, %lo(STATEP)(at)
    addu  t1, t1, t0
    jal   OBJMGR
    lw    a1, 0x1f8(t1)             ; (delay) GetAvatarID(player), -1 for none
    b     gt_2
    lw    t9, 0(v0)
""",
    """
gt_2:
    lw    t9, 0x38(t9)
    jalr  t9                        ; his SimHuman + 0x1B0
    move  a0, v0
    beqz  v0, gt_tail
    move  a0, s1
    lw    t0, 0x484(v0)             ; +0x634: gobs_enter's mark, the player is watching
    beqz  t0, gt_tail
    nop
    jal   gobs_advance
    lw    a1, 4(s0)                 ; (delay) from the fallen soldier
gt_tail:
    move  a0, s0
    ld    ra, 0x20(sp)
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    j     ISOBS
    addiu sp, sp, 0x30
""",
    # gobs_key: SimHuman::ProcessMessage, a dead soldier's message other than fire
    # (v0 = message id -- GR's hooked branch follows a delay slot that put the message in a0 --
    # s0 = message, s1 = the dead soldier; ra reloaded by the delay slot)
    """
gobs_key:
    li    t0, 0xe1                  ; reload
    beq   v0, t0, gk_x
    li    t0, 0xdf                  ; next item
    bne   v0, t0, gk_ret
gk_x:
    lw    t0, 0x634(s1)             ; (delay) watching?
    beqz  t0, gk_ret
    lw    t0, 0x28(s0)              ; (delay) payloads: {avatar id, pressed}
    sltiu t0, t0, 2
    bnez  t0, gk_ret
    move  a0, s0
    li    a1, 1
    jal   GETBOOL
    addiu a2, sp, 0x6f              ; ProcessMessage's own bool slot, as its fire path uses it
    lbu   t0, 0x6f(sp)
    beqz  t0, gk_ret                ; let go
    lw    a0, 0x610(s1)             ; (delay) player number, 1 or 2 (gobs_enter marks no one else)
    addiu a0, a0, -1
    sll   t0, a0, 2
    lui   at, %hi(SIMMGR)
    lw    t1, %lo(SIMMGR)(at)
    addu  t1, t1, t0
    b     gk_2
    lw    t1, 0x444(t1)             ; (delay) that player's camera
""",
    # gobs_enter: from grsquad's GR handoff cave, nobody left in the dead player's fireteam
    """
gobs_enter:
    lw    s4, 0x610(s0)             ; the player he died as: 1, 2 (0 = none)
    addiu s4, s4, -1
    sltiu t0, s4, 2
    beqz  t0, ge_out                ; not a player's soldier: a switch with nobody to switch to
    li    t0, 1
    sw    t0, 0x634(s0)             ; watching
    move  a0, s4
    jal   gobs_advance
    move  a1, s0
ge_out:
    j     HOF_RET
    nop
gk_2:
    beqz  t1, gk_ret
    nop
    lw    a1, 4(t1)                 ; the soldier it follows
    beqz  a1, gk_ret
    nop
    jal   gobs_advance
    nop
gk_ret:
    j     PM_RET
    nop
""",
)
GR_PIECES = tuple((c, c + 4 * GR_CAVE_WORDS, s) for c, s in zip(GR_CAVES, GR_SRC))

GR_STOCK = {}
for _c in GR_CAVES:
    GR_STOCK.update(_stock_words(_c, GR_DTOR_HEX))
GR_STOCK[GR_HOOK_KEY] = GR_HOOK_KEY_STOCK
GR_STOCK[GR_HOOK_TICK] = GR_HOOK_TICK_STOCK


def gr_build():
    """Ghost Recon: ({cave: words}, labels)."""
    words, labels = _build(GR_PIECES, GR_SYMS)
    if labels["gobs_enter"] != GR_ENTER:
        raise ValueError("gobs_enter moved: grsquad jumps to %#x" % GR_ENTER)
    return words, labels


def gr_edit_list():
    """Ghost Recon (va, value, stock, note); grsquad.gr_edits(..., observer=True) makes the
    handoff cave's "nobody left" word jump to gobs_enter."""
    words, labels = gr_build()
    out = []
    for base, _end, _src in GR_PIECES:
        out += [(base + 4 * i, w, GR_STOCK[base + 4 * i], "observer: routine")
                for i, w in enumerate(words[base])]
    out.append((GR_HOOK_KEY, assemble("j %#x" % labels["gobs_key"], GR_HOOK_KEY)[0][0],
                GR_HOOK_KEY_STOCK, "observer: X on a watching player's dead soldier moves his camera on"))
    out.append((GR_HOOK_TICK, assemble("jal %#x" % labels["gobs_tick"], GR_HOOK_TICK)[0][0],
                GR_HOOK_TICK_STOCK, "observer: the watched soldier went down -> next one"))
    return out


def gr_enabled(v: dict) -> bool:
    """Ghost Recon: grsquad.gr_edits(..., observer=gr_enabled(v)) must get the same answer."""
    return bool(v.get("gr_ss_observer") and v.get("gr_ss_handoff") and v.get("gr_ss_fireteams"))


def gr_edits(v: dict):
    return gr_edit_list() if gr_enabled(v) else []


def _check(elf, stock, delta, key, fn):
    bad = []
    for va, w in stock.items():
        off = va - 0x100000 + delta
        if int.from_bytes(elf[off:off + 4], "little") != w:
            bad.append("%s %08X" % (key, va))
    try:
        e = fn()
    except ValueError as ex:
        return bad + ["%s: %s" % (key, ex)]
    if len({va for va, *_ in e}) != len(e):
        bad.append("%s duplicate VA" % key)
    if any(va not in stock for va, *_ in e):
        bad.append("%s VA without a stock word" % key)
    return bad


def selftest(*elfs):
    """Stock words, sizes, no address twice, for each executable given (Ghost Recon's
    SLUS_206.13 and/or Jungle Storm's SLUS_208.20, in any order). [] = pass."""
    bad = []
    for elf in elfs:
        if elf is None:
            continue
        gr = int.from_bytes(elf[GR_HOOK_KEY - 0x100000 + 0x80:][:4], "little") == GR_HOOK_KEY_STOCK
        js = int.from_bytes(elf[HOOK_KEY - 0x100000 + 0x100:][:4], "little") == HOOK_KEY_STOCK
        if gr:
            bad += _check(elf, GR_STOCK, 0x80, "gr", gr_edit_list)
        elif js:
            bad += _check(elf, JS_STOCK, 0x100, "js", edits)
        else:
            bad.append("an executable that is neither retail GR nor retail JS")
    return bad

"""Enemy pistols, and when an enemy draws his: Jungle Storm (SLUS-20820).

What enemies carry
------------------
No enemy in Jungle Storm carries a sidearm. Every hostile actor in the
campaign and TAC missions names one of 20 kits (`Kit = "..."` in the .MIS),
and none of them has a pistol: DEFAULT.KIT (382 soldiers: AK-47, 3 magazines,
6 frag grenades), VZ58_ONLY (358: vz.58 + 1 frag), Z84_ONLY (71: Z-84 SMG +
2 frags), DEGTYAREV_ONLY (31: RPD + 2 frags), DRAGUNOV ONLY (31 snipers, rifle
only), RP46_ONLY (26: RP-46 + 2 frags), the AK-47 / AK-74 / vz.58 kits with 1-2
frags or a cigarette or beer can in slot 1, SR25_ONLY (G02's 3 snipers),
RPK74 (+ grenades). The one pistol an enemy holds is TAC02's single M1911
ONLY soldier, and that pistol is his only weapon. The online co-op, split
screen and single-player savestates agree: every enemy SimHuman's inventory
is primary + (grenades | prop | nothing), slots 2-4 empty.

So the AI never switches to a sidearm, and with 'Enemies can run out of
magazines' a dry enemy keeps his empty rifle: Jungle Storm's
GetNonEmptyMagazineCount (0x00220470) counts an empty current magazine as one,
so BestInventoryItem never finds the rifle unusable and CheckForMagazineChange
will not reload without a spare.

How the AI picks a weapon
-------------------------
HumanAIInventory::Update (0x003EFC20, for every AI soldier) asks
CheckSelectedItem (0x003EFDF0), which asks BestInventoryItem (0x003EFEB0) for
a slot and, when it differs from the soldier's own (SimHuman +0x1E7) and the
weapon is not locked (HumanAI +0x130), writes it into the AI's desired
SimHumanState (HumanAI +0x1C, mSelectedItem +0x33) through
HumanAI::SelectInventoryItem (0x003EAC40; script-controlled teams may pick any
slot). HumanAI::SendInventoryMessages (0x003EB2B0) turns that into the
select-slot key message 0x132 + slot (slot 2 = 0x134), the same message a
player's button sends; the SimHuman's handler starts the change (pending flag
+0x50A + slot, 'jw_equipchg.wav'). Then Update runs CheckROF and
CheckForMagazineChange (0x003F0820), which reloads through
HumanAI::ChangeMagazine (0x003EACA0, the desired state's action bit 2):
engaged, only an empty magazine with a spare; otherwise at 25 % or less.
BestInventoryItem looks at slots 0 and 1 only, by a mode (+8): 1 normal,
2 sniper, 3 grenade, 4 binoculars, 5 launcher. The grenade throws of
'Enemies throw grenades' switch slots this way (mode 3).

Online co-op: only the host runs the AI. The soldier's own SimHumanState
carries mSelectedItem in every UpdateSimHuman message (0x1AD:
SimHumanState::UpdateInto writes +0x33 at 0x003C1E40, UpdateFrom reads it at
0x003C1F84), and the joiner's network copy draws what it says: in the
co-op savestates every host AI soldier holding slot 1 is a copy holding
slot 1 on the joiner, with the joiner's render object drawing slot 1. A
switch made here goes the same way.

Giving them one (js_enemy_pistols)
----------------------------------
Kits allow slots 0-4 (Inventory::Load, 0x0021E440 `sltiu 5`), but
IkeSimulationMgr::CreateInventoryForHuman (0x0036B590), which turns the kit
into the soldier's inventory, sends AddInventoryItem (0x9A) for slots 0 and 1
only (`slti v0, s2, 2` at 0x0036B7E4). The option makes that 3: slot 2 goes out
like the others -- to every console, from the host (MasterSendAll) -- and a
kit with no slot 2 sends the game's own "empty slot" filler (class 0x43),
which HandleAddInventoryItem (0x003B7B30) turns into DeleteItem on an empty
slot: nothing. Everything after that already handles slot 2: the inventory
array has 5 entries, the render object 3 weapon models (+0x2FC..+0x304,
+0x308 the one drawn), SelectInventorySlot2 sets +0x50C, SendInventoryMessages
sends 0x134.

The pistol is the M9 (M9.GUN, gun index 35), two magazines, in slot 2 of 17
of the hostile kits (KITS: not NOWEAPON, not M1911 ONLY, and not AK47 ONLY --
see below; its 8 soldiers in G04 and U02 stay as they are). The M9 because its
sound is sure to play: a gun's shot is audible only if some gun in the level
pulled in its weapon bank (sndAddWeapon 0x00255A90 on each AddInventoryItem,
11 banks at most), and the M9's bank 44 is the one the M9 and M9 SD share --
the sidearm of many Ghost kits, so often already loaded. The Makarov has a
model but no shot sound anywhere on the disc; the M1911's is in TAC02's level
bank only. Cost: one Firearm object and two magazines per enemy, the M9 model
once, bank 44 if no Ghost carries an M9, and +1.2 kg in the soldier's
inventory weight.

Each kit keeps its exact length (its archive slot has 0-15 bytes of slack), so
the VersionNumber lines go and, where needed, indentation and line breaks (the
XML lexer, 0x00404380, skips space, tab, CR and LF alike); the rest pads with
spaces before </KitFile>. What the soldier ends up with does not change: the
kit's own VersionNumber is read and dropped; an item's is the kit number
(bits 20-21 the kit texture) that the message after each item (0x1E0) hands
the soldier, last one kept (SimHuman Inventory +0x24: 0x90004 on every
DEFAULT.KIT soldier in the savestates, 0x360004 on the RP-46 gunners), so the
pistol, now the last item, carries the old last item's number. AK47 ONLY
(0xA1000) has no room for that even on one line, so it is left alone.

With just this option, an enemy whose rifle is out of rounds (every magazine
empty -- only with 'Enemies can run out of magazines') draws the pistol;
nothing else changes. BestInventoryItem is rewritten in place: the stock
rules, the same passes in the same order (the function repeated one loop
eight times; the rewrite runs one), then the pistol rules below, in 332 (405
with js_enemy_sidearm) of its 508 words.

When he draws it (js_enemy_sidearm)
-----------------------------------
For a soldier in mode 1 or 2, weapon not locked, with a loaded pistol in slot 2:

  * he holds his rifle and it has no rounds at all -> pistol (no roll);
  * he holds his rifle, has seen his target (HumanAI +0x64/+0x68: set every
    frame the engagement has sight, EngageThreatBehavior 0x001AD9E8) within
    the last second, and
      (b) the target is within 4 m: a roll, fixed per soldier and target;
      (a) the magazine in the rifle is empty and the reload has not begun,
          the target within 12 m: a roll, once per empty magazine (the
          pistol's padding byte +0x21 remembers the magazine it rolled for);
    a failed roll leaves him to reload as before;
  * holding the pistol, he keeps it while he has seen his target in the last
    5 s and it is not beyond 24 m -- then (or when the pistol is dry) the
    stock answer brings the rifle back and CheckForMagazineChange reloads it.

Checked in the RAM interpreter (session scratchpad agent_sidearm): the rewrite
answers as the shipped function in 20,040 cases over every soldier of eight
savestates and 374,464 synthetic inventories (every gun, dry, silenced,
launcher, grenade and hand-held item, modes 0-7, both ROEs); the game's own
AddInventoryItem handler puts the M9 in slot 2 and its model in the render
object; HumanAIInventory::Update draws it on the rules above (38 checks, seven
savestates), SendInventoryMessages sends 0x134 then 0x132, and the soldier's
UpdateSimHuman state carries the slot; 15 of the 17 kits read back through the
game's XML parser and kit loader as stock + the M9 with the same kit number
(DEGTYAREV_ONLY and VZ58_BEER: no savestate has their guns loaded).
Not yet played.
"""

from __future__ import annotations

import re
import struct

from .grasm import assemble

BEST, BEST_END = 0x003EFEB0, 0x003F06A0          # HumanAIInventory::BestInventoryItem, 508 words
LOOP, LOOP_STOCK, LOOP_NEW = 0x0036B7E4, 0x2A420002, 0x2A420003   # slti v0, s2, 2 -> 3

SYMS = dict(
    NONEMPTY=0x00220470, MOTION=0x002206A0, SILENCED=0x002206E0, HELDTYPE=0x0021D890,
    FIREARM_VT=0x005A7820, RandomFloat=0x001129C0, RNG=0x00613510, CLOCK=0x00684768,
)

#: js_enemy_sidearm -> (upper half of the float the reload roll must come under, hash threshold /256)
CHANCES = {"off": None, "25": (0x3E80, 64), "50": (0x3F00, 128), "75": (0x3F40, 192), "100": (0x3F81, 256)}
CLOSE, RELOAD, FAR = 4.0, 12.0, 24.0      # m: (b), (a), and the far give-up
SEEN, SAFE = 1.0, 5.0                     # s since the target was last in sight
PISTOL_SLOT = 2

#: the kits hostile actors name in the missions (census of every .MIS); NOWEAPON and M1911 ONLY excluded,
#: AK47 ONLY too (no room for the pistol and its kit number)
KITS = ("DEFAULT", "VZ58_ONLY", "Z84_ONLY", "DEGTYAREV_ONLY", "DRAGUNOV ONLY", "RP46_ONLY", "VZ58_CIGS",
        "VZ58_BEER", "AK47_1 GRENADE", "AK47_2 GRENADES", "AK74_CIG", "AK74_DRINKING",
        "SR25_ONLY", "AK47 AND CIGARETTE", "AK47 AND BEERCAN", "RPK74", "RPK74 AND GRENADES")
PISTOL_FILE, PISTOL_MAGS = "m9.gun", 2
KIT_PATTERN = r"/(%s)\.KIT$" % "|".join(re.escape(k) for k in KITS)

# ------------------------------------------------------------------------------------------------
# BestInventoryItem, rewritten. a0 = the HumanAIInventory (+4 HumanAI, +8 mode); v0 = the slot.
# `scan` is the stock loop (slots 0 and 1, first match): a1 = the test, a2/a3 its motion range.
#   0 firearm, a non-empty magazine (0x00220470), motion type in [a2, a2+a3) (a3 > 0) or not in
#     [a2, a2-a3) (a3 < 0);  1 firearm + magazine;  2 firearm + magazine + silenced;
#   3 thrown item with a count (+0x18);  4 hand-held item of type 3.
# ------------------------------------------------------------------------------------------------
SRC = """
best:
    addiu sp, sp, -0x70
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s2, 0x20(sp)
    sq    s3, 0x30(sp)
    sq    s4, 0x40(sp)
    sq    s5, 0x50(sp)
    sd    ra, 0x60(sp)
    move  s0, a0
    lw    v1, 8(s0)                 ; the mode
    beqz  v1, st_3
    li    at, 4
    bne   v1, at, st_m3
    move  a0, s0
    jal   scan                      ; mode 4: binoculars
    li    a1, 4
    bgez  v0, st_out
    li    at, 1
    sw    at, 8(s0)
st_m3:
    lw    v1, 8(s0)
    li    at, 3
    bne   v1, at, st_m5
    lw    v0, 4(s0)
    lw    v0, 0xa4(v0)
    lw    v0, 0x20(v0)              ; the team's combat ROE
    bnez  v0, st_m3b
    move  a0, s0
    li    a1, 0
    li    a2, 4
    jal   scan                      ; mode 3: a gun that is not a launcher (ROE 0 only)
    li    a3, -2
    bgez  v0, st_out
    move  a0, s0
st_m3b:
    li    a1, 0
    li    a2, 4
    jal   scan                      ; a launcher (motion type 4)
    li    a3, 1
    bgez  v0, st_out
    move  a0, s0
    jal   scan                      ; a grenade
    li    a1, 3
    bgez  v0, st_out
    li    at, 1
    sw    at, 8(s0)
st_m5:
    lw    v1, 8(s0)
    li    at, 5
    bne   v1, at, st_m2
    move  a0, s0
    li    a1, 0
    li    a2, 5
    jal   scan                      ; mode 5: motion type 5
    li    a3, 1
    bgez  v0, st_out
    move  a0, s0
    jal   scan                      ; any gun
    li    a1, 1
    b     st_out
    nop
st_m2:
    li    at, 2
    bne   v1, at, st_m1
    move  a0, s0
    li    a1, 0
    li    a2, 2
    jal   scan                      ; mode 2: a sniper rifle (motion type 2 or 3)
    li    a3, 2
    bgez  v0, st_out
    nop
    lw    v0, 4(s0)
    lw    v0, 0xa4(v0)
    lw    v0, 0x20(v0)
    bnez  v0, st_any
    move  a0, s0
    jal   scan                      ; a silenced gun (ROE 0 only)
    li    a1, 2
    bgez  v0, st_out
    move  a0, s0
st_any:
    jal   scan                      ; any gun
    li    a1, 1
    b     st_out
    nop
st_m1:
    li    at, 1
    bne   v1, at, st_3
    lw    v0, 4(s0)
    lw    v0, 0xa4(v0)
    lw    v0, 0x20(v0)
    bnez  v0, st_m1b
    move  a0, s0
    jal   scan                      ; mode 1: a silenced gun (ROE 0 only)
    li    a1, 2
    bgez  v0, st_out
    move  a0, s0
st_m1b:
    li    a1, 0
    li    a2, 2
    jal   scan                      ; a rifle or pistol (not motion type 2-5)
    li    a3, -4
    bgez  v0, st_out
    move  a0, s0
    jal   scan                      ; any gun
    li    a1, 1
    bgez  v0, st_out
    nop
st_3:
    li    v0, 3
st_out:
    bgez  v0, st_ok                 ; a scan that found nothing: 3, as the stock code answers
    nop
    li    v0, 3
st_ok:
{SIDE}
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    lq    s3, 0x30(sp)
    lq    s4, 0x40(sp)
    lq    s5, 0x50(sp)
    ld    ra, 0x60(sp)
    jr    ra
    addiu sp, sp, 0x70

scan:
    addiu sp, sp, -0x70
    sq    s0, 0x00(sp)
    sq    s1, 0x10(sp)
    sq    s2, 0x20(sp)
    sq    s3, 0x30(sp)
    sq    s4, 0x40(sp)
    sq    s5, 0x50(sp)
    sd    ra, 0x60(sp)
    move  s0, a0
    move  s3, a1
    move  s4, a2
    move  s5, a3
    move  s1, zero
sc_loop:
    lw    v0, 4(s0)
    lw    v0, 0x14(v0)              ; the SimHuman
    lw    t9, 0x514(v0)
    lw    t9, 0x2c(t9)              ; Inventory::GetItem
    move  a1, s1
    jalr  t9
    addiu a0, v0, 0x514
    beqz  v0, sc_next
    move  s2, v0
    lw    t9, 0(s2)
    li    at, 3
    beq   s3, at, sc_thrown
    li    at, 4
    beq   s3, at, sc_held
    nop
    lw    t9, 0x20(t9)              ; IsFirearm
    jalr  t9
    move  a0, s2
    andi  v0, v0, 0xff
    li    at, 1
    bne   v0, at, sc_next
    nop
    jal   NONEMPTY
    move  a0, s2
    andi  v0, v0, 0xffff
    beqz  v0, sc_next
    li    at, 1
    beq   s3, at, sc_hit
    li    at, 2
    bne   s3, at, sc_motion
    nop
    jal   SILENCED
    move  a0, s2
    andi  v0, v0, 0xff
    li    at, 1
    beq   v0, at, sc_hit
    nop
    b     sc_next
    nop
sc_motion:
    jal   MOTION
    move  a0, s2
    bltz  s5, sc_notin
    subu  v0, v0, s4
    sltu  v1, v0, s5
    bnez  v1, sc_hit
    nop
    b     sc_next
    nop
sc_notin:
    subu  t0, zero, s5
    sltu  v1, v0, t0
    beqz  v1, sc_hit
    nop
    b     sc_next
    nop
sc_thrown:
    lw    t9, 0x24(t9)              ; IsThrownItem
    jalr  t9
    move  a0, s2
    andi  v0, v0, 0xff
    li    at, 1
    bne   v0, at, sc_next
    nop
    lw    v0, 0x18(s2)              ; count
    bnez  v0, sc_hit
    nop
    b     sc_next
    nop
sc_held:
    lw    t9, 0x28(t9)              ; IsHandHeldItem
    jalr  t9
    move  a0, s2
    andi  v0, v0, 0xff
    li    at, 1
    bne   v0, at, sc_next
    nop
    jal   HELDTYPE
    move  a0, s2
    li    at, 3
    beq   v0, at, sc_hit
    nop
sc_next:
    addiu s1, s1, 1
    slti  at, s1, 2
    bnez  at, sc_loop
    nop
    b     sc_out
    li    v0, -1
sc_hit:
    move  v0, s1
sc_out:
    lq    s0, 0x00(sp)
    lq    s1, 0x10(sp)
    lq    s2, 0x20(sp)
    lq    s3, 0x30(sp)
    lq    s4, 0x40(sp)
    lq    s5, 0x50(sp)
    ld    ra, 0x60(sp)
    jr    ra
    addiu sp, sp, 0x70

; rounds: a0 = a Firearm -> v0 = the rounds in all its magazines (leaf)
rounds:
    lhu   t0, 0x18(a0)
    lw    t1, 0x1c(a0)
    beqz  t1, rd_out
    move  v0, zero
rd_loop:
    beqz  t0, rd_out
    nop
    lhu   t2, 0(t1)
    addu  v0, v0, t2
    addiu t1, t1, 2
    b     rd_loop
    addiu t0, t0, -1
rd_out:
    jr    ra
    nop

; seen: a0 = the HumanAI -> v0 = 1 when he has had a target, f0 = seconds since it was last in
; sight, f1 = its distance squared then (leaf)
seen:
    lw    t0, 0x64(a0)              ; the last threat's id, -1 none
    addiu t0, t0, 1
    beqz  t0, sn_out
    move  v0, zero
    lui   t1, %hi(CLOCK)
    lw    t1, %lo(CLOCK)(t1)
    lwc1  $f0, 0xd4(t1)             ; now
    lwc1  $f1, 0x74(a0)
    sub.s $f0, $f0, $f1
    lwc1  $f1, 0x68(a0)
    lwc1  $f2, 0x2c(a0)
    sub.s $f1, $f1, $f2
    mul.s $f1, $f1, $f1
    lwc1  $f2, 0x6c(a0)
    lwc1  $f3, 0x30(a0)
    sub.s $f2, $f2, $f3
    mul.s $f2, $f2, $f2
    add.s $f1, $f1, $f2
    lwc1  $f2, 0x70(a0)
    lwc1  $f3, 0x34(a0)
    sub.s $f2, $f2, $f3
    mul.s $f2, $f2, $f2
    add.s $f1, $f1, $f2
    li    v0, 1
sn_out:
    jr    ra
    nop
"""

# The pistol rules, after the stock answer (v0). s0 = the inventory; s1 the stock answer, s2 the HumanAI,
# s3 the SimHuman, s4 the pistol, s5 the stock weapon.
SIDE = """
    move  s1, v0
    lw    s2, 4(s0)
    lw    v1, 8(s0)
    addiu v1, v1, -1
    sltiu v1, v1, 2                 ; mode 1 or 2
    beqz  v1, sd_done
    lbu   v1, 0x130(s2)             ; weapon locked
    bnez  v1, sd_done
    lw    s3, 0x14(s2)
    lw    v1, 0x528(s3)             ; inventory slots
    slti  v1, v1, 3
    bnez  v1, sd_done
    lw    v1, 0x524(s3)
    lw    s4, 8(v1)                 ; slot 2
    beqz  s4, sd_done
    lui   v1, %hi(FIREARM_VT)
    lw    v0, 0(s4)
    addiu v1, v1, %lo(FIREARM_VT)
    bne   v0, v1, sd_done
    nop
    jal   rounds
    move  a0, s4
    beqz  v0, sd_done               ; the pistol is dry
    move  s5, zero
    slti  at, s1, 2
    beqz  at, sd_pistol             ; nothing usable in slots 0-1: the pistol
    lw    v1, 0x524(s3)
    sll   at, s1, 2
    addu  v1, v1, at
    lw    s5, 0(v1)                 ; the stock weapon
    beqz  s5, sd_pistol
    lui   v1, %hi(FIREARM_VT)
    lw    v0, 0(s5)
    addiu v1, v1, %lo(FIREARM_VT)
    bne   v0, v1, sd_done           ; not a gun: leave it to the game
    nop
    jal   rounds
    move  a0, s5
    move  t3, v0                    ; its rounds, all magazines
    lw    v1, 0x1c(s2)
    lb    v1, 0x33(v1)              ; the slot he wants
    li    at, {SLOT}
    beq   v1, at, sd_hold
    lb    v1, 0x1e7(s3)             ; the slot he has
    beq   v1, at, sd_hold
    nop
    beqz  t3, sd_pistol             ; his rifle is out of rounds
    nop
{ROLLS}
    b     sd_done
    nop
sd_hold:
    beqz  t3, sd_pistol             ; nothing to go back to
    nop
    jal   seen
    move  a0, s2
    beqz  v0, sd_done               ; no target: back to the rifle
    lui   at, {SAFE_HI}
    mtc1  at, $f2
    nop
    c.lt.s $f2, $f0
    bc1t  sd_done                   ; out of sight 5 s: back to the rifle
    lui   at, {SEEN_HI}
    mtc1  at, $f2
    nop
    c.lt.s $f2, $f0
    bc1t  sd_pistol                 ; out of sight for now: keep it
    lui   at, {FAR_HI}
    mtc1  at, $f2
    nop
    c.lt.s $f2, $f1
    bc1t  sd_done                   ; in sight but beyond 24 m: back to the rifle
    nop
sd_pistol:
    li    s1, {SLOT}
sd_done:
    move  v0, s1
"""

# The two rolls, only when js_enemy_sidearm is on. t3 = the stock weapon's rounds (non-zero here).
ROLLS = """
    lb    v1, 0x1e7(s3)
    bne   v1, s1, sd_done           ; not holding it (mid-switch)
    nop
    jal   seen
    move  a0, s2
    beqz  v0, sd_done
    lui   at, {SEEN_HI}
    mtc1  at, $f2
    nop
    c.lt.s $f2, $f0
    bc1t  sd_done                   ; not in sight this last second
    lui   at, {CLOSE_HI}
    mtc1  at, $f2
    nop
    c.lt.s $f1, $f2
    bc1f  sd_reload
    lw    t0, 0x64(s2)              ; (b) within 4 m: this soldier's roll against this target
    sll   t1, t0, 16
    xor   t0, t0, t1
    xor   t0, t0, s2
    sll   t1, t0, 13
    xor   t0, t0, t1
    srl   t1, t0, 17
    xor   t0, t0, t1
    sll   t1, t0, 5
    xor   t0, t0, t1
    sll   t1, t0, 13
    xor   t0, t0, t1
    srl   t1, t0, 17
    xor   t0, t0, t1
    sll   t1, t0, 5
    xor   t0, t0, t1
    srl   t0, t0, 24
    sltiu t0, t0, {CH8}
    bnez  t0, sd_pistol
    nop
sd_reload:
    lui   at, {RELOAD_HI}
    mtc1  at, $f2
    nop
    c.lt.s $f1, $f2
    bc1f  sd_done                   ; (a) within 12 m
    lhu   t0, 0x1a(s5)              ; the magazine in the rifle
    lw    t1, 0x1c(s5)
    sll   t2, t0, 1
    addu  t1, t1, t2
    lhu   t1, 0(t1)
    bnez  t1, sd_done               ; not empty
    lw    t1, 0x1c(s2)
    lbu   t1, 0x32(t1)
    andi  t1, t1, 2
    bnez  t1, sd_done               ; reload asked for
    lbu   t1, 0x1e6(s3)
    andi  t1, t1, 2
    bnez  t1, sd_done               ; reloading
    andi  t0, t0, 0x7f
    ori   t0, t0, 0x80
    lbu   t1, 0x21(s4)              ; the magazine rolled for last (padding byte of the pistol)
    beq   t1, t0, sd_done           ; rolled for this one already
    sb    t0, 0x21(s4)
    lui   a0, %hi(RNG)
    addiu a0, a0, %lo(RNG)
    move  a1, zero
    move  a2, zero
    mtc1  zero, $f12
    lui   v0, 0x3f80
    jal   RandomFloat               ; 0..1
    mtc1  v0, $f13
    lui   at, {CHANCE_HI}
    mtc1  at, $f1
    nop
    c.lt.s $f0, $f1
    bc1t  sd_pistol
    nop
"""


def _hi(x):
    b = struct.unpack("<I", struct.pack("<f", x))[0]
    assert b & 0xFFFF == 0, x
    return hex(b >> 16)


def _source(chance="off"):
    k = dict(SLOT=PISTOL_SLOT, SAFE_HI=_hi(SAFE), SEEN_HI=_hi(SEEN), FAR_HI=_hi(FAR * FAR),
             CLOSE_HI=_hi(CLOSE * CLOSE), RELOAD_HI=_hi(RELOAD * RELOAD))
    ch = CHANCES[chance]
    rolls = "" if ch is None else ROLLS.format(CHANCE_HI=hex(ch[0]), CH8=ch[1], **k)
    side = SIDE.format(ROLLS=rolls, **k)
    return SRC.replace("{SIDE}", side)


def assemble_best(chance="off"):
    words, labels = assemble(_source(chance), BEST, SYMS)
    if labels["best"] != BEST or BEST + 4 * len(words) > BEST_END:
        raise ValueError("BestInventoryItem outgrows itself (%d words, room %d)"
                         % (len(words), (BEST_END - BEST) // 4))
    return words, labels


# ------------------------------------------------------------------------------------------------
# stock words
# ------------------------------------------------------------------------------------------------
_BEST_STOCK_HEX = (    # BestInventoryItem as shipped, 0x003EFEB0..0x003F06A0
    "27BDFFC0 FFBF0030 7FB20020 7FB10010 7FB00000 8C830008 14600003 0080802D 100001EC"
    "24020003 24020004 14620023 0000882D 1000001E 2E220002 8E020004 00112E3C 00052E3F"
    "8C420014 8C590514 8F39002C 0320F809 24440514 0040902D 12400011 00000000 8E590000"
    "8F390028 0320F809 0240202D 304300FF 24020001 14620009 0240202D 0C087624 00000000"
    "24030003 14430004 00000000 0011163C 100001CC 0002163F 26310001 2E220002 1440FFE2"
    "24020001 AE020008 8E030008 24020003 14620077 00000000 8E020004 8C4200A4 8C420020"
    "1440002D 0000882D 10000027 0000882D 8E020004 00112E3C 00052E3F 8C420014 8C590514"
    "8F39002C 0320F809 24440514 0040902D 1240001B 00000000 8E590000 8F390020 0320F809"
    "0240202D 304300FF 24020001 14620013 0240202D 0C08811C 00000000 3042FFFF 1840000E"
    "0240202D 0C0881A8 00000000 24030005 10430009 0240202D 0C0881A8 00000000 24030004"
    "10430004 00000000 0011163C 10000197 0002163F 26310001 2E220002 1440FFD8 00000000"
    "0000882D 10000023 2E220002 8E020004 00112E3C 00052E3F 8C420014 8C590514 8F39002C"
    "0320F809 24440514 0040902D 12400016 00000000 8E590000 8F390020 0320F809 0240202D"
    "304300FF 24020001 1462000E 0240202D 0C08811C 00000000 3042FFFF 18400009 0240202D"
    "0C0881A8 00000000 24030004 14430004 00000000 0011163C 10000170 0002163F 26310001"
    "2E220002 1440FFDD 00000000 1000001A 0000882D 8E020004 00112E3C 00052E3F 8C420014"
    "8C590514 8F39002C 0320F809 24440514 0040902D 1240000E 00000000 8E590000 8F390024"
    "0320F809 0240202D 304300FF 24020001 14620006 00000000 8E420018 10400003 0011163C"
    "10000152 0002163F 26310001 2E220002 1440FFE5 24020001 AE020008 8E030008 24020005"
    "14620048 0000882D 10000023 2E220002 8E020004 00112E3C 00052E3F 8C420014 8C590514"
    "8F39002C 0320F809 24440514 0040902D 12400016 00000000 8E590000 8F390020 0320F809"
    "0240202D 304300FF 24020001 1462000E 0240202D 0C08811C 00000000 3042FFFF 18400009"
    "0240202D 0C0881A8 00000000 24030005 14430004 00000000 0011163C 10000127 0002163F"
    "26310001 2E220002 1440FFDD 00000000 1000001D 0000882D 8E020004 00112E3C 00052E3F"
    "8C420014 8C590514 8F39002C 0320F809 24440514 0040902D 12400011 00000000 8E590000"
    "8F390020 0320F809 0240202D 304300FF 24020001 14620009 0240202D 0C08811C 00000000"
    "3042FFFF 18400004 00000000 0011163C 10000106 0002163F 26310001 2E220002 1440FFE2"
    "00000000 8E030008 24020002 14620078 0000882D 10000026 2E220002 8E020004 00112E3C"
    "00052E3F 8C420014 8C590514 8F39002C 0320F809 24440514 0040902D 12400019 00000000"
    "8E590000 8F390020 0320F809 0240202D 10400013 0240202D 0C08811C 00000000 3042FFFF"
    "1840000E 0240202D 0C0881A8 00000000 24030002 10430006 0240202D 0C0881A8 00000000"
    "24030003 14430004 00000000 0011163C 100000D9 0002163F 26310001 2E220002 1440FFDA"
    "00000000 8E020004 8C4200A4 8C420020 14400029 0000882D 10000023 0000882D 8E020004"
    "00112E3C 00052E3F 8C420014 8C590514 8F39002C 0320F809 24440514 0040902D 12400017"
    "00000000 8E590000 8F390020 0320F809 0240202D 304300FF 24020001 1462000F 0240202D"
    "0C08811C 00000000 3042FFFF 1840000A 0240202D 0C0881B8 00000000 304300FF 24020001"
    "14620004 00000000 0011163C 100000AD 0002163F 26310001 2E220002 1440FFDC 00000000"
    "0000882D 1000001E 2E220002 8E020004 00112E3C 00052E3F 8C420014 8C590514 8F39002C"
    "0320F809 24440514 0040902D 12400011 00000000 8E590000 8F390020 0320F809 0240202D"
    "304300FF 24020001 14620009 0240202D 0C08811C 00000000 3042FFFF 18400004 00000000"
    "0011163C 1000008B 0002163F 26310001 2E220002 1440FFE2 00000000 8E030008 24020001"
    "14620083 24020003 8E020004 8C4200A4 8C420020 14400029 0000882D 10000023 0000882D"
    "8E020004 00112E3C 00052E3F 8C420014 8C590514 8F39002C 0320F809 24440514 0040902D"
    "12400017 00000000 8E590000 8F390020 0320F809 0240202D 304300FF 24020001 1462000F"
    "0240202D 0C08811C 00000000 3042FFFF 1840000A 0240202D 0C0881B8 00000000 304300FF"
    "24020001 14620004 00000000 0011163C 1000005B 0002163F 26310001 2E220002 1440FFDC"
    "00000000 0000882D 10000030 2E220002 8E020004 00112E3C 00052E3F 8C420014 8C590514"
    "8F39002C 0320F809 24440514 0040902D 12400023 00000000 8E590000 8F390020 0320F809"
    "0240202D 1040001D 0240202D 0C08811C 00000000 3042FFFF 18400018 0240202D 0C0881A8"
    "00000000 24030002 10430013 0240202D 0C0881A8 00000000 24030003 1043000E 0240202D"
    "0C0881A8 00000000 24030005 10430009 0240202D 0C0881A8 00000000 24030004 10430004"
    "00000000 0011163C 10000027 0002163F 26310001 2E220002 1440FFD0 00000000 1000001D"
    "0000882D 8E020004 00112E3C 00052E3F 8C420014 8C590514 8F39002C 0320F809 24440514"
    "0040902D 12400011 00000000 8E590000 8F390020 0320F809 0240202D 304300FF 24020001"
    "14620009 0240202D 0C08811C 00000000 3042FFFF 18400004 00000000 0011163C 10000006"
    "0002163F 26310001 2E220002 1440FFE2 00000000 24020003 DFBF0030 7BB20020 7BB10010"
    "7BB00000 03E00008 27BD0040 00000000"
)


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


JS_STOCK = _stock_words(BEST, _BEST_STOCK_HEX)
JS_STOCK[LOOP] = LOOP_STOCK


def edits(chance="off"):
    """(va, value, stock, note): slot 2 reaches the soldier, and BestInventoryItem with the pistol rules."""
    words, _labels = assemble_best(chance)
    what = ("the pistol when his rifle is dry" if CHANCES[chance] is None else
            "the pistol when dry, up close (%s%%) and instead of a reload near you" % chance)
    out = [(LOOP, LOOP_NEW, LOOP_STOCK, "enemy pistols: a kit's slot 2 reaches the soldier (AddInventoryItem)")]
    out += [(BEST + 4 * i, w, JS_STOCK[BEST + 4 * i], "enemy pistols: BestInventoryItem, stock rules + " + what)
            for i, w in enumerate(words)]
    return out


def js_edits(v: dict):
    if not v.get("js_enemy_pistols"):
        return []
    chance = str(v.get("js_enemy_sidearm", "off"))
    return edits(chance if chance in CHANCES else "off")


# ------------------------------------------------------------------------------------------------
# data: the M9 into slot 2 of the hostile kits, each kit kept at its length
# ------------------------------------------------------------------------------------------------
class SidearmError(ValueError):
    pass


def _pistol_lines(version=None):
    head = [b'<Firearm SlotNumber = "%d">' % PISTOL_SLOT]
    if version:
        head.append(b"<VersionNumber>%s</VersionNumber>" % version)
    return head + [b"<ItemFileName>%s</ItemFileName>" % PISTOL_FILE.encode(),
                   b"<MagazineCount>%d</MagazineCount>" % PISTOL_MAGS, b"</Firearm>"]


def _zero(v: bytes) -> bool:
    try:
        return int(float(v)) == 0
    except ValueError:
        return False


def add_pistol(plain: bytes):
    """(new kit bytes, 1): the pistol in slot 2, same length.

    The VersionNumbers go to make room, and nothing the soldier ends up with changes. The kit's own is
    read with atof and dropped (Inventory::Load). An item's lands in the kit-file item only
    (+0xC, 0x0021F540); CreateInventoryForHuman never sends it with the item, only in the message
    after it (0x1E0: the kit texture its bits 20-21 pick -- kit-assault / -demo / -sniper /
    -support.rsb -- and the number itself, SimHuman 0x003B7E90 -> Inventory vt+0x88 / vt+0x94, one
    stored value each), one per item in slot order, so the last item's number is the one the soldier
    keeps. The pistol is the last item now: it carries that number (none when it is 0, which is what
    the item constructor leaves). Then indentation and line breaks go too, as far as needed (the
    lexer, 0x00404380, skips space, tab, CR and LF). Raises on a kit that already has a slot 2 or has
    no room even on one line."""
    if re.search(rb'SlotNumber\s*=\s*"%d"' % PISTOL_SLOT, plain):
        raise SidearmError("kit already has a slot %d" % PISTOL_SLOT)
    lines = [ln.strip() for ln in plain.replace(b"\r\n", b"\n").split(b"\n") if ln.strip()]
    if not lines or lines[-1] != b"</KitFile>" or lines[0] != b"<KitFile>":
        raise SidearmError("not a kit file")
    body, depth, item, last = [lines[0]], 0, None, None
    for ln in lines[1:-1]:
        m = re.fullmatch(rb"<VersionNumber>([^<]*)</VersionNumber>", ln)
        if m:
            if depth:
                item = None if _zero(m.group(1)) else m.group(1)
            continue
        if re.match(rb"<(Firearm|ThrownItem|HandHeldItem)\b", ln):
            depth, item = depth + 1, None
        elif re.match(rb"</(Firearm|ThrownItem|HandHeldItem)>", ln):
            depth, last = depth - 1, item          # the last item's number is the one kept
        body.append(ln)
    if depth:
        raise SidearmError("unbalanced kit")
    body += _pistol_lines(last) + [lines[-1]]
    for sep in (b"\r\n", b"\n", b""):
        new = sep.join(body) + sep
        if len(new) <= len(plain):
            pad = len(plain) - len(new)
            # spaces before </KitFile> (the lexer skips them), the file's own ending kept
            head, tail = new.rsplit(b"</KitFile>", 1)
            return head + b" " * pad + b"</KitFile>" + tail, 1
    raise SidearmError("no room for the pistol (%d bytes)" % len(plain))


def _op_sidearm_kit(plain, params):
    return add_pistol(plain)


def _register():
    from . import dataedit
    dataedit.OPS.setdefault("sidearm_kit", _op_sidearm_kit)


_register()


def data_edits(v: dict, prefix: str = "js_") -> list:
    if prefix != "js_" or not v.get(prefix + "enemy_pistols"):
        return []
    from .model import FileEdit
    return [FileEdit("sidearm_kit", KIT_PATTERN, "GR.IMG", {},
                     "an M9 in slot 2 of every hostile kit (%d kits)" % len(KITS))]


# ------------------------------------------------------------------------------------------------
def _kit_items(plain: bytes):
    """[(tag, slot, file, count, version)] of a kit, whitespace-blind like the game's XML lexer
    (0x00404380); version as the item loader stores it (an int, 0 when absent)."""
    out = []
    for m in re.finditer(rb'<(Firearm|ThrownItem|HandHeldItem)\s+SlotNumber\s*=\s*"(\d+)"\s*>(.*?)</\1\s*>', plain, re.S):
        f = re.search(rb"<ItemFileName>\s*([^<\s]+)\s*</ItemFileName>", m.group(3))
        c = re.search(rb"<(?:MagazineCount|Count)>\s*([^<\s]+)\s*</(?:MagazineCount|Count)>", m.group(3))
        v = re.search(rb"<VersionNumber>\s*([^<\s]+)\s*</VersionNumber>", m.group(3))
        out.append((m.group(1).decode(), int(m.group(2)), f.group(1).decode().lower() if f else None,
                    c.group(1).decode() if c else None, int(float(v.group(1))) if v else 0))
    return out


def selftest(js_elf: bytes, kit_plain=None):
    """Every stock word against the executable, no address twice, every kit rewrite read back.
    `kit_plain` = {name: stock bytes} of the kits (optional). [] = pass."""
    bad = []
    for va, w in JS_STOCK.items():
        off = va - 0x100000 + 0x100
        if int.from_bytes(js_elf[off:off + 4], "little") != w:
            bad.append("js %08X" % va)
    for chance in CHANCES:
        e = edits(chance)
        if len({va for va, *_ in e}) != len(e):
            bad.append("js duplicate VA (%s)" % chance)
        if any(va not in JS_STOCK for va, *_ in e):
            bad.append("js VA without a stock word (%s)" % chance)
    for name, plain in (kit_plain or {}).items():
        try:
            new, _n = add_pistol(plain)
        except SidearmError as exc:
            bad.append("%s: %s" % (name, exc))
            continue
        if len(new) != len(plain):
            bad.append("%s: length %d -> %d" % (name, len(plain), len(new)))
        old = _kit_items(plain)
        # the soldier keeps the last item's number (kit texture, Inventory +0x24): now the pistol's
        want = [it[:4] + (0,) for it in old] + [("Firearm", PISTOL_SLOT, PISTOL_FILE, str(PISTOL_MAGS),
                                                  old[-1][4] if old else 0)]
        if _kit_items(new) != want or new.count(b"<") != new.count(b">"):
            bad.append("%s: reads back as %s" % (name, _kit_items(new)))
        if not re.fullmatch(rb"\s*<KitFile>.*</KitFile>\s*", new, re.S):
            bad.append("%s: not one KitFile" % name)
    return bad

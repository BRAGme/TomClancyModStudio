"""Rainbow Six 3 (PS2, SLUS-20883) -- profile.

Every address below is a virtual address in the decompressed `SP.SOZ` overlay,
which the EE loads at a fixed base of 0x00100000. All stock words are asserted
before anything is written, so a mismatched disc revision fails loudly instead
of corrupting the image.

Provenance of the wave numbers, briefly, because they are not obvious:

  * `m_iNbToSpawn` is computed at zone init as `min + rand % (max - min + 1)`;
    replacing the `addu` that forms it with a `li` gives every deployment zone
    the same budget.
  * The wave advance returns early unless `liveCount <= m_iNextWaveTrigger`, so
    the trigger -- not the wave size -- is the real population cap. Steady state
    per zone is roughly `trigger + release`.
  * The advance is gated on `bStasis == 0`, and UE2 clears stasis for actors
    whose zone contains a player. So the shipped rule is literally "feed the
    zone the player is standing in". Inverting that test (`beq` -> `bne`) makes
    the zones the player has left do the feeding instead.
  * A wave draws only from its own `m_aSpawningPoint` array, and those points
    sit next to the zone. Widening the pool to every `R6DZonePoint` in the level
    takes a code cave, which is the one thing here that cannot be baked into the
    disc -- see `build_pnach`.
"""

from __future__ import annotations

import re
import struct

from ..model import (BOOL, CHOICE, INT, Choice, FileEdit, GameProfile,
                     Overlay, Setting, WordEdit, li, S0, V0, V1)
from . import r6_3_slus20883_sig, r6tuning, xboxbuild
from .. import (rseaicover, rsecanon, rseclark, rsedebrief, rsefragwarn, rsechatter, rsedraw, rsekits, rseloadout,
                rsedeadpath, rsefov, rsehudteam, rsemandown, rsemuzzle,
                rsesplice, rsesquad, rseswitch,
                rserescue, rseteam,
                rseviewmodel, rserpg, rseshadow, rsesidearm,
                rsescope,
                rseorders, rsewheel, rsecallouts, rseflashlight, rsehands, rsecarry,
                rsedowncall, rseroguecall, rsethuntai, rsegadget,
                rsehostagerun, rseflashcost, rsecorpsehit, rsegunaudio,
                rsethirdperson,
                rseclaymore, rseff,
                rsedecal, rseaihunt, rsesmoke, rseuzilight, rsepuffs,
                rseviewport, rsespectate, rsetracer, rseslomo,
                rsepenetrate,
                rsemirror, rseaifire, rseburstsnd, rsesoundgate,
                rsefollowleg,
                rsemolotov)

BASE = 0x00100000
NOP = 0x00000000

SP = Overlay(
    name="SP.SOZ",
    iso_pattern=r"/SP\.SOZ$",
    base_va=BASE,
    kind="soz",
    image_size=5585280,
    image_sha1="e9bb12138a1e69d551ac9f6b958114e5b2e830da",
)

# -- stock words, all read back out of a pristine SP.SOZ -------------------
STOCK = {
    # sw $v0, -0x7f78($gp) -- renderer init writing g_PresentDivider = 2
    # (0x00653778). The vblank pacing ISR at 0x0019F700 counts vblanks and
    # only releases a flip once the count reaches this divider, so 2 means
    # one presented frame per two NTSC fields: 29.97 Hz. See PRESENT_DIVIDER.
    # addiu $a1, $zero, 8 -- R6DecalGroup m_MaxSize for the GRENADE ring. The
    # five rings are 32 footsteps, 32 wall hits, 16 blood splats, 8 blood
    # baths and 8 grenade marks; 96 pooled R6Decal actors in total, which is
    # exactly what a savestate holds. `decal_ring` patches 0x00379B30, whose
    # one register feeds footsteps AND wall hits -- it never touched this.
    0x00379B38: 0x24050008,
    0x002F10C8: 0x3C0240A0,   # lui v0, 0x40A0 = 5.0f  flashbang screen effect
    0x001AE478: 0xAF828088,
    # R6DZoneWave::Tick's release loop. Stock it calls SpawnOne exactly n
    # times and ignores the return; a NULL return means the engine built
    # nothing (the template roll failed, or the class would not resolve), so
    # the remaining calls are certain to fail too. `movz $s1,$s0,$v0` forces
    # the counter to the bound on NULL and the loop exits; the increment
    # moves into the branch delay slot, which runs on both paths, so a
    # successful release still runs exactly n times. MOVZ is already used by
    # this function at 0x0040A8B0.
    0x0040A8D4: 0x26310001,   # addiu s1, s1, 1      release-loop counter
    0x0040A8E0: 0x00000000,   # nop                  its branch delay slot
    0x0040AF58: 0x02221021,   # addu v0, s1, v0      m_iNbToSpawn
    0x0040A8A8: 0x02028021,   # addu s0, s0, v0      released per wave
    0x0040AFDC: 0x02231821,   # addu v1, s1, v1      m_iNextWaveTrigger seed
    0x0040A874: 0x02021021,   # addu v0, s0, v0      m_iNextWaveTrigger rearm
    0x0040AF4C: 0x00000000,   # pad nop
    0x0040AF50: 0x00000000,   # pad nop
    0x0040AF54: 0x00001010,   # mfhi v0  (dead once 0x40af58 is a constant)
    0x0040A790: 0x10400003,   # beq v0, zero, +3     the bStasis gate
    0x003F1934: 0x1440004F,   # bne v0, zero, skip   static-world impact decal
    0x003F1BB4: 0x14400084,   # bne v0, zero, skip   actor-attached impact decal
    0x003F250C: 0x14400014,   # bne v0, zero, skip   impact emitter spawn
    0x003531D0: 0x14400053,   # bne v0, zero, skip   rain/snow weather
    0x003A14B8: 0x14400015,   # bne v0, zero, skip   blood-effect update
    0x002375E0: 0xA2420065,   # sb v0, 0x65(s2)      Disabled = m_bHideInSplitScreen
    0x00302DA8: 0xAF8080CC,   # sw zero, -0x7f34(gp) g_bDrawFirstPersonWeapon = 0
    0x00317570: 0x1460001D,   # bne v1, zero, +29    body despawn path 1
    0x003175F4: 0x1460000B,   # bne v1, zero, +11    body despawn path 2
    0x00317600: 0x3C034040,   # lui v1, 0x4040       3.0f despawn window
    0x00379B30: 0x24060020,   # addiu a2, zero, 32   R6DecalGroup m_MaxSize
    0x0040ACA0: 0x0C051B7C,   # jal rand             SpawnATerrorist point pick
    # The substituted delta is built as a lui/ori pair and then moved into the
    # register, so the constant itself is patchable without touching the branch:
    #   lui v1, 0x3D4C ; ori v1, v1, 0xCCCD  ->  0x3D4CCCCD == 0.05f
    0x00142040: 0x3C033D4C,   # lui v1, 0x3D4C      high half of the constant
    0x00142044: 0x3463CCCD,   # ori v1, v1, 0xCCCD  low half
    0x00142048: 0x4483A800,   # mtc1 v1, $f21       player 2's input dt := 0.05f
    0x0019AE40: 0x14A000C6,   # bnez a1, 0x19b15c   the scope-overlay gate
    0x0019AE44: 0x3C010004,   # lui at, 0x4        its delay slot, and NOT
                              #                    filler: the gate's target
                              #                    opens `ori at, at, 0x17e8`
    0x00446EA8: 0x30420001,   # andi v0, v0, 1      the shadow-pass gate
}

# Scaffolding from the research build that produced this profile: a tracing stub
# in the function-end padding at 0x0011d8c4 and the two-word hijack that reached
# it. This tool never writes them, but knowing their stock values means it can
# clean a disc that still carries them instead of refusing to touch it.
RESEARCH_LEFTOVERS = dict(
    [(va, 0x00000000) for va in range(0x0011D8C4, 0x0011D900, 4)]
    + [(0x0017F530, 0x27BDFCF0), (0x0017F534, 0xFFBF0090)]
)
STOCK.update(RESEARCH_LEFTOVERS)

#: The dead-path cave and every site the two split-screen HUD fixes
#: touch. These used to be cheat words, which never went through
#: STOCK at all; on the disc each one is asserted against the shipped
#: word before it is written, like every other patch site here.
HUD_STOCK = {
    0x0019AE40: 0x14A000C6,
    0x0019AE48: 0x82030000,
    0x0019AE4C: 0x00031EBC,
    0x0019AE50: 0x00031FFF,
    0x0019AE54: 0x106001B5,
    0x0019AE58: 0x348317E0,
    0x0019AE5C: 0x02031821,
    0x0019AE60: 0x8C630000,
    0x0019AF34: 0x8E0207C4,
    0x0019AF38: 0x04410003,
    0x0019AF3C: 0x00023843,
    0x0019AF40: 0x24420001,
    0x0019AF44: 0x00023843,
    0x0019AF48: 0x8E0807C8,
    0x0019AF68: 0x8E0207C4,
    0x0019AF6C: 0x04410003,
    0x0019AF70: 0x0002B043,
    0x0019AF74: 0x24420001,
    0x0019AF78: 0x0002B043,
    0x0019AFD0: 0x8E0807C8,
    0x0019B0A8: 0x8E0207C4,
    0x0019B0AC: 0x04410003,
    0x0019B0B0: 0x00023843,
    0x0019B0B4: 0x24420001,
    0x0019B0B8: 0x00023843,
    0x0019B0BC: 0x8E0807C8,
    0x0019B0DC: 0x8E0207C4,
    0x0019B0E0: 0x04410003,
    0x0019B0E4: 0x0002B043,
    0x0019B0E8: 0x24420001,
    0x0019B0EC: 0x0002B043,
    0x0019B144: 0x8E0807C8,
    0x0019B15C: 0x342117E8,
    0x0019B160: 0x02011821,
    0x0019B164: 0x00651821,
    0x0019B168: 0x90630000,
    0x0019B16C: 0x106000EF,
    0x0019B170: 0x00000000,
    0x0019B174: 0x348417EC,
    0x0019B178: 0x00051880,
    0x0019B17C: 0x02042021,
    0x0019B180: 0x00831821,
    0x0019B184: 0x8C630000,
    0x0019B188: 0x106000E8,
    0x0019B18C: 0x00000000,
    0x0019B190: 0x24040001,
    0x0019B194: 0x0C064808,
    0x0019B198: 0x0000282D,
    0x0019B19C: 0x3C010004,
    0x0019B1A0: 0x02010821,
    0x0019B1A4: 0x8C2309FC,
    0x0019B1A8: 0x3C010004,
    0x0019B1AC: 0x00031880,
    0x0019B1B0: 0x342117EC,
    0x0019B1B4: 0x02011021,
    0x0019B1B8: 0x00431021,
    0x0019B1BC: 0x8C440000,
    0x0019B1C0: 0x8C990000,
    0x0019B1C4: 0x8F3900A4,
    0x0019B1C8: 0x0320F809,
    0x0019B1CC: 0x00000000,
    0x0019B1D0: 0x0040A02D,
    0x0019B1D4: 0x0200202D,
    0x0019B1D8: 0x0280282D,
    0x0019B1DC: 0x0000302D,
    0x0019B1E0: 0x0000382D,
    0x0019B1E4: 0x0C06A474,
    0x0019B1E8: 0x0000402D,
    0x0019B1EC: 0x0040282D,
    0x0019B1F0: 0x0200202D,
    0x0019B1F4: 0x0000302D,
    0x0019B1F8: 0x0000382D,
    0x0019B1FC: 0x0000402D,
    0x0019B200: 0x27898DAC,
    0x0019B204: 0x0C06A124,
    0x0019B208: 0x0000502D,
    0x0019B20C: 0x8F868DAC,
    0x0019B210: 0x24020080,
    0x0019B214: 0x0002183C,
    0x0019B218: 0x24020089,
    0x0019B21C: 0x00431825,
    0x0019B220: 0x24020042,
    0x0019B224: 0x24C50010,
    0x0019B228: 0xAF858DAC,
    0x0019B22C: 0xFCC30000,
    0x0019B230: 0xFCC20008,
    0x0019B234: 0x8E990000,
    0x0019B238: 0x8F390024,
    0x0019B23C: 0x0320F809,
    0x0019B240: 0x0280202D,
    0x0019B244: 0x8E990000,
    0x0019B248: 0x2456FFFF,
    0x0019B24C: 0x8F390028,
    0x0019B250: 0x0320F809,
    0x0019B254: 0x0280202D,
    0x0019B258: 0xFFB30000,
    0x0019B25C: 0x2443FFFF,
    0x0019B260: 0xFFB60008,
    0x0019B264: 0x3C020004,
    0x0019B268: 0xFFA30010,
    0x0019B26C: 0x34430A00,
    0x0019B270: 0xFFA00018,
    0x0019B274: 0x02032021,
    0x0019B278: 0xFFA00020,
    0x0019B27C: 0x34430A04,
    0x0019B280: 0xFFA00028,
    0x0019B284: 0x34420A08,
    0x0019B288: 0x02031821,
    0x0019B28C: 0x02021021,
    0x0019B290: 0x8C420000,
    0x0019B294: 0x04410003,
    0x0019B298: 0x00023843,
    0x0019B29C: 0x24420001,
    0x0019B2A0: 0x00023843,
    0x0019B2A4: 0x3C020004,
    0x0019B2A8: 0x8C850000,
    0x0019B2AC: 0x34420A0C,
    0x0019B2B0: 0x8C660000,
    0x0019B2B4: 0x02021021,
    0x0019B2B8: 0x02A0482D,
    0x0019B2BC: 0x8C480000,
    0x0019B2C0: 0x0220502D,
    0x0019B2C4: 0x0240582D,
    0x0019B2C8: 0x0C067130,
    0x0019B2CC: 0x0200202D,
    0x0019B2D0: 0x3C010004,
    0x0019B2D4: 0x02010821,
    0x0019B2D8: 0x8C220A08,
    0x003F4BF4: 0xC7828D18,
    0x003F4BF8: 0xC7818D24,
    0x003F4BFC: 0xC7808D28,
    0x003F5524: 0xC7828D18,
    0x003F5528: 0xC7818D24,
    0x003F552C: 0xC7808D28,
    0x00438000: 0x8FA32A14,
    0x00438080: 0x00000000,
    0x004380E4: 0x460073C6,
    0x0043811C: 0x460073C6,
    0x00438158: 0x460073C6,
    0x0043819C: 0x460073C6,
    0x00438284: 0x0C11A628,
    0x004382C4: 0x0C11A628,
    0x00438404: 0x0C11A628,
    0x00438448: 0x0C11A628,
    0x0043873C: 0x0C0D25B4,
    0x004387D0: 0x0C0D25B4,
    0x0043888C: 0x00000000,
    0x00438AC4: 0x0C0D25B4,
    0x00438B58: 0x0C0D25B4,
    0x00438C0C: 0x00000000,
    0x00438E34: 0x0C0D25B4,
    0x00438EC8: 0x0C0D25B4,
    0x00438F88: 0x00000000,
    0x004391BC: 0x0C0D25B4,
    0x00439250: 0x0C0D25B4,
    0x00439304: 0x00000000,
    # the wheel marker's left/right cases -- jal 0x00469a10
    0x00438340: 0x0C11A684,
    0x004383B0: 0x0C11A684,
    0x004384E4: 0x0C11A684,
    0x00438540: 0x0C11A684,
}
# The wheel's label text: its two hooks -- one in the shared string drawer,
# one after the fourth label -- and its words in the dead path past word 96,
# which this table predates.
HUD_STOCK[rsewheel.LABEL_TEXT_HOOK] = rsewheel.LABEL_TEXT_STOCK
HUD_STOCK[rsewheel.LABEL_UNARM_HOOK] = rsewheel.LABEL_UNARM_STOCK
for _i in range(96, 113):
    HUD_STOCK[rsedeadpath.CAVE + 4 * _i] = rsedeadpath.STOCK_WORDS[_i]
# ...and the split-screen team panel's: six hooks, dead-path words 113-238
# (160-169 held the first names cave and are stock again).
for _va, _stock, _new, _note in rsehudteam.HOOKS:
    HUD_STOCK[_va] = _stock
for _i in range(113, 239):
    HUD_STOCK[rsedeadpath.CAVE + 4 * _i] = rsedeadpath.STOCK_WORDS[_i]
STOCK.update(HUD_STOCK)
# The third-person flash test split_muzzle corrects -- see rsemuzzle.
STOCK[rsemuzzle.THIRD_PERSON_TEST] = rsemuzzle.TP_STOCK
# The game-mode test in the lookup Clark's voice lines go through -- see
# rseclark.
for _va, _stock, _new, _note in rseclark.EDITS:
    STOCK[_va] = _stock
# The debriefing's operative rows (rsedebrief) and the team panel's speaking
# flash, whose cave sits in the padding that ends the code section.
for _va, _stock, _new, _note in rsedebrief.EDITS:
    STOCK[_va] = _stock
for _va, _word, _stock, _note in rsehudteam.speak_words():
    STOCK[_va] = _stock
# Part A -> part B carry-over by player, not by slot (rsecarry).
for _va, _stock, _new, _note in rsecarry.WORDS:
    STOCK[_va] = _stock
# The shrapnel-decal cave (rsedecal) hooks the explosion native's epilogue.
# The cave itself is a cheat-file thing; only the hijack is an overlay word.
STOCK[rsedecal.HIJACK_AT] = rsedecal.HIJACK_STOCK
# Its disc words patch R6DecalGroup::Init's explosion branch in place: four
# to give it the wall-hit look, four to cap the incidence angle that was
# letting marks smear, and one for its own DrawScale.
for _va, _stock, _new in rsedecal.BRANCH_WORDS + rsedecal.INCIDENCE_WORDS:
    STOCK[_va] = _stock
#: The withdrawn first attempt at the same feature. It repointed the decal
#: type dispatch at the wall-hit branch, which worked but handed the ring the
#: bullet holes' own DrawScale, so making explosion marks bigger enlarged
#: those too. Patching the ring's own branch replaced it. Registered here and
#: written by nothing, so a disc that still carries the old word is
#: recognised and put back -- without this a previously applied disc reports
#: as carrying changes this tool does not know, and cannot be used as a
#: source of stock data.
STOCK[0x00378B44] = 0x106200AD
#: The penetration gate. The model ships complete and switched OFF --
#: every material on the disc has m_iPenetration 0, which means
#: impenetrable -- so these words open it rather than tune it.
STOCK.update(rsepenetrate.stock_words())
# Terrain projection for decal groups. Stock, the GRENADE group has
# bit 1 CLEAR -- explosion marks never projected on terrain. The patch
# that gave them the bullet-hole look switched it on, and each mark
# then gathered against every terrain sector of every zone, with the
# AABB test at the leaf and no hierarchical rejection. See rsedecal.
for _grp in (rsedecal.TERRAIN_OFF_SHRAPNEL, rsedecal.TERRAIN_OFF_BLOOD,
             rsedecal.TERRAIN_OFF_HOLES, rsedecal.TERRAIN_KILL):
    for _va, _st, _nw in _grp:
        STOCK[_va] = _st
STOCK[rsedecal.DRAWSCALE] = rsedecal.DRAWSCALE_STOCK
# And the per-frame hook the impact stagger uses, in UGameEngine::Tick.
STOCK[rsedecal.STAGGER_HOOK] = rsedecal.STAGGER_HOOK_STOCK
# The blood-splatter cave (rsedecal) hooks the one word that ends the PAWN
# branch of the bullet trace native. Like the shrapnel cave, only the hook is
# an overlay word; the cave itself lives below the ELF load base.
STOCK[rsedecal.BLOOD_HOOK] = rsedecal.BLOOD_HOOK_STOCK
# And the BloodSplats ring size, which is a plain disc word.
STOCK[rsedecal.BLOOD_RING] = rsedecal.BLOOD_RING_STOCK
# The loadout-mirror cave hooks the `jr $ra` that ends
# execGetMissionDescription; its delay slot, `addiu $sp,$sp,0x20`, runs
# either way, so the cave starts with the frame already popped. Only the
# hook is an overlay word and even that is delivered as a cheat row, but
# it is registered here so a disc that somehow carries it is recognised
# and put back.
STOCK.update(rsemirror.stock_words())
# How hard the squad shoots: three `addiu` immediates inside
# R6RainbowAI::Tick that set the trigger-hold envelope. No cave and no
# hook -- the burst length is not a data value on PS2, it is rolled from
# these literals every attack cycle. The divisor is registered but never
# changed; it keeps the 0.05 s quantum.
STOCK[rseaifire.MOD_AT] = rseaifire.MOD_STOCK
STOCK[rseaifire.FLOOR_AT] = rseaifire.FLOOR_STOCK
STOCK[rseaifire.DIV_AT] = rseaifire.DIV_STOCK
# The tracer VISIBILITY gates -- independent of the colour work above.
# The game stamps each tracer with the firing player's viewport and then
# refuses to draw it in that same viewport, so nobody ever sees his own;
# and AI fire is cone-gated to two degrees. See rsetracer.
STOCK.update(rsetracer.visible_stock_words())
# Three-round burst plays m_BurstFireStereoSnd, which is None on all 30
# weapons and whose recording is not on the disc -- so burst fires
# silently. One word repoints it at m_SingleFireStereoSnd. See
# rseburstsnd.
STOCK.update(rseburstsnd.stock_words())
# Being flashbanged re-runs the whole deafening routine every frame for
# six seconds, because one line in UGameEngine::Tick clears the latch
# that says it already ran. See rseflashcost.
STOCK.update(rseflashcost.stock_words())
STOCK.update(rsethirdperson.stock_words())
# Molotovs and flashbangs for the terrorists. ONE overlay word: the hook
# in PickGrenadeClass, delivered as a cheat row. Its delay slot is
# deliberately NOT registered -- `lui $at, 0x005e` is the top half of an
# overlay address, every entry here becomes a relocation signature, and
# relocate() can never confirm such a word because a rebuilt data segment
# changes that immediate. Registering it for documentation made the whole
# option undeliverable on any other pressing. See rsemolotov.
STOCK.update(rsemolotov.stock_words())

# The claymore proximity cave (rseclaymore), delivered in the cheat file. Only
# the hijack is an overlay word; the cave itself lives in RAM below the ELF
# load base, which is not part of the image and so has no stock value.
STOCK[rseclaymore.HIJACK[0]] = rseclaymore.HIJACK_STOCK
# Projectors in split screen: the level render's split-screen skip (rseshadow).
STOCK[rseshadow.PROJECTOR_BRANCH] = rseshadow.PROJECTOR_BRANCH_STOCK
# Team orders: each viewport's interactions drawn only in its own pass.
for _va, _stock, _new, _note in rseorders.PASS_WORDS:
    STOCK[_va] = _stock
# The split-screen aim branch ss_accuracy removes: beqz $v0 on the flag at
# 0x006546F4, which is 1 in split screen and 0 in single player.
SS_AIM_BRANCH = 0x003F3D90
STOCK[SS_AIM_BRANCH] = 0x10400011      # beqz $v0, 0x003F3DD8
SS_AIM_ALWAYS = 0x10000011             # b    0x003F3DD8 -- same target
STOCK[rseteam.BUDGET] = rseteam.BUDGET_STOCK

BODY_TIMERS = {
    "stock": None,
    "15": 0x3C034170,     # lui v1, 0x4170 = 15.0f
    "30": 0x3C0341F0,     # lui v1, 0x41f0 = 30.0f
    "60": 0x3C034270,     # lui v1, 0x4270 = 60.0f
}

WAVE_GATES = {
    "stock": 0x10400003,  # beq  -- feed only the zone the player is in
    "always": 0x10000003, # b    -- every zone feeds, all the time
    "away": 0x14400003,   # bne  -- feed only the zones the player has left
}

# The map-wide spawn-point picker: 67 words of cave plus one hijack. Assembled
# and verified as a PCSX2 cheat; it cannot be baked into the disc because the
# 0x005ba488 zero run is not preserved through a level load, while a cheat file
# rewrites it every frame.
CAVE_HIJACK = (0x0040ACA0, 0x0816E922)   # j 0x005ba488, replacing `jal rand`
CAVE_WORDS = [
    (0x005BA488, 0x3C01005C), (0x005BA48C, 0xAC3FA5F8), (0x005BA490, 0x0C051B7C),
    (0x005BA494, 0x00000000), (0x005BA498, 0x30517FFF), (0x005BA49C, 0x3C01005C),
    (0x005BA4A0, 0x8C3FA5F8), (0x005BA4A4, 0x8EA802E4), (0x005BA4A8, 0x1100002E),
    (0x005BA4AC, 0x00000000), (0x005BA4B0, 0x8D09002C), (0x005BA4B4, 0x8D0A0030),
    (0x005BA4B8, 0x1120002A), (0x005BA4BC, 0x00000000), (0x005BA4C0, 0x19400028),
    (0x005BA4C4, 0x00000000), (0x005BA4C8, 0x3C0B0061), (0x005BA4CC, 0x356BE2F0),
    (0x005BA4D0, 0x00006021), (0x005BA4D4, 0x00006821), (0x005BA4D8, 0x000C7080),
    (0x005BA4DC, 0x012E7021), (0x005BA4E0, 0x8DCF0000), (0x005BA4E4, 0x11E00005),
    (0x005BA4E8, 0x00000000), (0x005BA4EC, 0x8DF80000), (0x005BA4F0, 0x170B0002),
    (0x005BA4F4, 0x00000000), (0x005BA4F8, 0x25AD0001), (0x005BA4FC, 0x258C0001),
    (0x005BA500, 0x018A082A), (0x005BA504, 0x1420FFF4), (0x005BA508, 0x00000000),
    (0x005BA50C, 0x11A00015), (0x005BA510, 0x00000000), (0x005BA514, 0x022D001A),
    (0x005BA518, 0x00000000), (0x005BA51C, 0x00000000), (0x005BA520, 0x00007010),
    (0x005BA524, 0x00006021), (0x005BA528, 0x000C7880), (0x005BA52C, 0x012F7821),
    (0x005BA530, 0x8DF80000), (0x005BA534, 0x13000007), (0x005BA538, 0x00000000),
    (0x005BA53C, 0x8F190000), (0x005BA540, 0x172B0004), (0x005BA544, 0x00000000),
    (0x005BA548, 0x11C0000F), (0x005BA54C, 0x00000000), (0x005BA550, 0x25CEFFFF),
    (0x005BA554, 0x258C0001), (0x005BA558, 0x018A082A), (0x005BA55C, 0x1420FFF2),
    (0x005BA560, 0x00000000), (0x005BA564, 0x8EA80484), (0x005BA568, 0x11000004),
    (0x005BA56C, 0x00000000), (0x005BA570, 0x8D040000), (0x005BA574, 0x10000005),
    (0x005BA578, 0x00000000), (0x005BA57C, 0x00008021), (0x005BA580, 0x08102B6E),
    (0x005BA584, 0x00000000), (0x005BA588, 0x03002021), (0x005BA58C, 0x08102B31),
    # THE FIX for the spawn runaway. Both paths into the point's spawn call
    # funnel through the `j 0x0040ACC4` above, so this shared branch delay
    # slot is the last instruction to run before it -- and it is the cave's
    # own word, so the cave does not grow. `sw $s5, 0x480($a0)`: store the
    # REQUESTING zone into the chosen point's owner field, so the new enemy
    # is credited to the zone that asked instead of to the point's owner
    # (NULL on 14 of Shipyard's 18 points). $s5 holds the zone for all of
    # R6DZoneWave::SpawnOne and no cave word writes it.
    (0x005BA590, 0xAC950480),
]

#: Counted from the recovered export table, which names each object's class --
#: not from a byte search, which also counts the class name itself and reads
#: one high on every level. 41 wave actors and 541 spawn points across the 27
#: campaign parts. See research/rs3ai/zones.md.
WAVE_MAPS = (
    "Waves are a campaign thing. 24 of the game's 27 mission parts place "
    "deployment zones -- 41 zones and 541 spawn points between them -- and the "
    "settings on this page reach every one of them at once. To move a single "
    "mission instead, use the Missions page.\n\n"
    "Widest choice of spawn points, which is what map-wide spawning feeds on:\n"
    "  TRIESTE A         3 zones, 29 points\n"
    "  IMPORT/EXPORT B   3 zones, 29 points\n"
    "  OIL REFINERY A    3 zones, 27 points\n"
    "  OFFICE COMPLEX A  1 zone,  27 points\n"
    "  PARADE B          2 zones, 26 points\n"
    "  SHIPYARD A        2 zones, 18 points -- the only level with fighting "
    "from the first minute, since its zones wrap the insertion point.\n\n"
    "No zones, so nothing here changes them: Alpine Village A, Import/Export "
    "A, Penthouse A.\n"
    "No zones anywhere in multiplayer or training either -- every MP and "
    "training package places zero, so adversarial modes are untouched.\n\n"
    "Withdrawn: \"Match player 2's look speed to player 1\". The clamp it "
    "targeted is real -- at 0x00142048 the routine forces its frame delta to "
    "0.05 whenever the true frame is under 33 ms -- but play-testing it made "
    "player 2 about four times more sensitive with no acceleration ramp at "
    "all, which is not parity. Two things are settled and worth keeping: that "
    "delta is computed at 0x00141d54 as a timer over 2^32, capped at 0.04 for "
    "a long frame, so it IS a real frame time; and the clamp raises it, which "
    "at 60 fps makes it three times larger than player 1's rather than "
    "smaller. The card used to claim the opposite. What is still unknown is "
    "the path from that register to the camera: inside its own routine it "
    "feeds an accumulator at gp-32008 and a countdown at +0x304, both plain "
    "`+= dt` / `-= dt`, neither of them a look rate. Until that path is "
    "traced there is nothing honest to switch on.\n\n"
    "PARKING GARAGE: a correction. An earlier version of this note said "
    "Garage was broken in split screen ON THE RETAIL DISC. It is not. Its "
    "two mission INIs were corrupted on the working disc by an earlier edit "
    "of this tool, sometime after 15 September: GARAGE_A.INI kept its first "
    "144 bytes and became 10,373 NUL bytes after them, losing its skin, "
    "camo-face and loadout settings, and GARAGE_B.INI lost its first 57 "
    "bytes, section header included -- one contiguous zeroed run across the "
    "two files, identical in all three archives. Every other copy of the "
    "disc (the November pristine image and three backups from August and "
    "September) has both files intact.\n\n"
    "That is what made Garage crawl and fail. With no m_Skins the loader "
    "skips the texture Garage's recording was made with and reads the next "
    "one from the wrong bytes, which is the retained engine error \"Texture "
    "R6Characters_T.Rainbow.R6RChaveshead: SERIAL SIZE MISMATCH: GOT "
    "1110226955\" -- ASCII read as a length. The 'stock' test that seemed to "
    "prove otherwise was not stock: the tool's backup store had recorded the "
    "already-damaged files as originals, so RESTORE DISC put the damage back "
    "faithfully. The store now holds the pristine copies, and the next apply "
    "writes them to the disc.\n\n"
    "Withdrawn: \"Give split screen the full streaming budget\". The routine "
    "at 0x00472160 really does return 3 in split screen and 6 in single "
    "player, and it really is the only constant in the overlay that differs "
    "by mode -- but it is not the level streaming budget. Following its one "
    "caller outwards, 0x004ca230 forwards it to 0x004e3490, which compares it "
    "against a counter at 0x006f0a60 that is incremented on acquire and "
    "decremented on release, runs only when the pool is FULL, and formats a "
    "message into an 0x840-byte stack buffer. The strings that message is "
    "built from name the subsystem: \"SStream Error: Not enough memory to "
    "create streaming source\", \"->Res 0x%x cannot be started because \", "
    "and the IMA-ADPCM decoder's own errors. It is the cap on simultaneous "
    "streaming AUDIO sources -- six in single player, three in split screen, "
    "because two viewports leave less memory for sound. Raising it asks the "
    "audio system for sources it has no memory for, which is the crash the "
    "first attempt produced. It was never going to affect AI teammates.\n\n"
    "No weapons page, and this one is settled rather than untried. Ghost "
    "Recon, Jungle Storm and The Sum of All Fears all get one, because they "
    "ship a .GUN file per weapon in plain XML. This disc keeps its weapons in "
    "COMMON.LIN, and the package at 0x1ad818 really is the weapons package -- "
    "877 exports including R6Weapons, R6MachineGun, R6SubMachineGun and "
    "R6BlackHawkGun. But Unreal only serialises a property that DIFFERS from "
    "its class default, and the weapon stats are the defaults. A float "
    "locator built for this (upackage.float_properties, and it works -- see "
    "the tests) finds exactly TWO m_fRateOfFire sites and six fBaseAccuracy "
    "sites in that entire package, for a game with about forty weapons. Two "
    "overrides is not a dial.\n\n"
    "The 33 m_iPenetration sites that look promising at first are false "
    "positives inside a texture package: their values run to 84,607,257 and "
    "their neighbouring properties are UBits, VBits, USize and ZPlane. The "
    "real values live in the compiled class defaults inside the overlay, not "
    "in the data. Ghost Recon 2 and Advanced Warfighter were checked the same "
    "way and answer the same."
)


#: The campaign, as the disc actually lays it out: a stem, the name the game
#: uses for it, and which parts exist. Most missions are two levels; Island,
#: Penthouse and Trieste are one. Every part ships twice -- `<STEM>OFF.LIN` and
#: `<STEM>_SS.LIN` -- and both have to be edited or half the copies stay stock.
#:
#: `waves` is the number of R6DZoneWave actors the level places, read off the
#: recovered export table rather than estimated; see research/rs3ai/zones.md.
#: The campaign in the order it is played, given by the person who has played
#: it. The disc does not state it anywhere readable: `RavenShieldCampaign.ini`
#: is a Raven Shield list the PS2 build inherited -- it names Bank,
#: MeatPacking_Day, Island_Dawn and Airport_Night, none of which are on this
#: disc, and omits four that are -- and the per-map `m_fStoryMapELO` is a
#: difficulty rating with ties, not a running order. Ordering by either put Oil
#: Refinery first, which is wrong.
#:
#: "Crespo Foundation" is the mission's own name for the OFFICE_COMPLEX
#: package; the display names live in the packed .LNG bundle, so the word
#: "Crespo" appears nowhere on the disc as text.
#:
#: Training and the Parking Garage come first because neither is in mission
#: selection -- they are chosen separately from the main menu.
#:
#: (stem, title, parts, wave zones, kind). An empty `parts` means the level is
#: a single package with no A/B suffix, which is how the training levels ship.
MISSIONS = (
    ("TRAINING_BASICS", "Training: Basics", "", 0, "training"),
    ("TRAINING_SHOOTING", "Training: Shooting", "", 0, "training"),
    ("TRAINING_TEAM", "Training: Team", "", 0, "training"),
    ("ALPINES", "Alpine Village", "AB", 2, "campaign"),
    ("MOUNTAIN_HIGHWAY", "Mountain Highway", "AB", 3, "campaign"),
    ("OIL_REFINERY", "Oil Refinery", "AB", 5, "campaign"),
    ("ISLAND", "Island Estate", "A", 2, "campaign"),
    ("SHIPYARD", "Shipyard", "AB", 3, "campaign"),
    ("OFFICE_COMPLEX", "Crespo Foundation", "AB", 3, "campaign"),
    ("OLDCITY", "Old City", "AB", 2, "campaign"),
    ("ALCATRAZ", "Alcatraz", "AB", 3, "campaign"),
    ("IMPORT_EXPORT", "Import/Export", "AB", 3, "campaign"),
    ("PENTHOUSE", "Penthouse", "A", 0, "campaign"),
    ("MEATPACKING", "Meat Packing Plant", "AB", 4, "campaign"),
    ("TRIESTE", "Trieste", "A", 3, "campaign"),
    ("GARAGE", "Parking Garage", "AB", 2, "bonus"),
    ("PARADE", "Parade", "AB", 3, "campaign"),
    ("AIRPORT", "Airport", "AB", 3, "campaign"),
)

MISSION_GROUP = "Missions"
TEAM_GROUP = "Teammates"


def mission_art_for(key):
    """The art base names for a mission dial, so its card shows the real thing."""
    for stem, _title, parts, _waves, _kind in MISSIONS:
        if key == mission_key(stem):
            return ["%s_%s" % (stem, p) for p in parts] if parts else [stem]
    return []


def mission_key(stem):
    return "mission_" + stem.lower()


def mission_select(stem, parts):
    """A regex matching every package this mission ships, both copies.

    Each level part ships twice, `<STEM>OFF.LIN` and `<STEM>_SS.LIN`, and both
    have to match or half the copies stay stock. The training levels have no
    A/B suffix at all, which is what the empty-`parts` branch is for.
    """
    if not parts:
        return r"/%s(OFF|_SS)\.LIN$" % stem
    return r"/%s_[%s](OFF|_SS)\.LIN$" % (stem, parts)


def _mission_settings():
    """One enemy-count dial per mission.

    These are the counts the designers authored into the level itself, so
    unlike everything on the Enemy Waves page they move one mission and leave
    the rest of the campaign alone. What they scale is every authored spawner
    count in that level -- the wave zones and the story spawners both -- which
    is why the label says enemies rather than waves.
    """
    out = []
    for stem, title, parts, waves, kind in MISSIONS:
        where = ("part A and B" if len(parts) == 2
                 else "one part" if parts else "a single level")
        zones = ("%d deployment zone%s" % (waves, "" if waves == 1 else "s")
                 if waves else "no deployment zones -- story spawners only")
        note = {"training": " Not in mission selection: training is chosen "
                            "separately from the main menu.",
                "bonus": " Not in mission selection -- the Parking Garage "
                         "is picked separately from the main menu.",
                }.get(kind, "")
        # The training levels author no spawner counts at all -- nothing to
        # scale -- so the dial is off rather than present and inert. Their
        # cards still carry the game's own art, which is why they are here.
        live = kind != "training"
        out.append(Setting(
            mission_key(stem), title, INT, 100, MISSION_GROUP,
            minimum=25, maximum=400, unit="%",
            # A comma, not a semicolon, inside the brackets: the card's
            # one-line summary ends a sentence at "; " and would cut there.
            help="Scales every enemy count authored into %s (%s, %s). "
                 "100%% leaves it exactly as it shipped.%s"
                 % (title, where, zones, note) if live else
                 "%s, and it authors no spawner counts -- there is nothing "
                 "here to scale.%s" % (where.capitalize(), note),
            touches="data", enabled=live,
            disabled_reason=("" if live else
                             "The training levels place no authored enemy "
                             "counts, so a dial would have nothing to change. "
                             "The card is here for the level's own artwork."),
            confidence="applied" if live else "broken"))
    return out


#: Every option whose edit RE-ASSEMBLES UnrealScript bytecode, rather than
#: poking bytes in place. All of them are withdrawn together, because the
#: evidence says the fault is the rewrite path and not the individual features.
#: Delete this list to put them back once `uscode` is understood.
#: Still out: these two were bisected to a hang ON THE DISC, one each, with
#: removing them loading fine. That is direct evidence, not association.
REASSEMBLED = ("ss_man_down",)

#: Re-enabled 2026-09-15 once `uscode` stopped shrinking the declared memory
#: size -- see REASSEMBLED_REASON for what that was and why it mattered. They go
#: back on the list as "untested", because the fix is reasoned and measured but
#: has not yet been through a level load. `canon_team` stays out: it is the one
#: with four earlier hangs behind it as well, so it is the last to be retried,
#: not the first.

REASSEMBLED_REASON = (
    "UPDATE 2026-09-24: the mismatch is found, by reading, not yet by a "
    "load. It adds `new R6PriceVoices` to PlaySoundDamage, which makes that "
    "function the first place the split-screen package touches the "
    "R6PriceVoices class -- earlier than the stock stream does. The loader "
    "creates, and then reads from the recording, a package's own objects "
    "in the order their first references are serialized, so the class is "
    "read where the recording holds something else. That is the same kind "
    "of change that hung Oil Refinery on 2026-09-23, and the suite now "
    "checks every edit for it.\n\n"
    "UPDATE 2026-09-22. canon_team, withdrawn beside this under the same "
    "reasoning, turned out to hang for a reason that is now measured: a "
    "split-screen level file is a RECORDING of what one load read, and its "
    "script asked for a class that recording never read. It is back on "
    "offer. The leading explanation for this one is the same kind of "
    "mismatch in the split-screen package itself -- its retained error, "
    "'Bad name index -511/6500', carries R6Engine's own name and import "
    "counts -- but that is inferred, not measured, so it stays off. The "
    "history below is kept as it was written.\n\n"
    "Withdrawn 2026-09-15, and RE-CONFIRMED 2026-09-19 on a disc carrying "
    "this option and nothing else -- so unlike some of its neighbours it "
    "was not convicted by a confounded bisect. What the retry added, from "
    "reading the console rather than watching the screen: the EE sits at "
    "pc=0x00081fc0 in the kernel, `eret`, with ra and sp both zero, "
    "identical across captures four seconds apart. Of 128 MB of EE RAM, "
    "628 bytes change in that time and every one of them is below "
    "0x00022000 -- kernel timers. Nothing in the game's own memory moves "
    "at all, the IOP is equally idle (429 bytes of 8 MB), and the level "
    "name buffer still reads 'menu', so it wedges BEFORE the mission load "
    "names its level. Every game thread is blocked, waiting on something "
    "that never arrives; it is not a slow load and it is not a spin.\n\n"
    "The 2026-09-15 reasoning is kept below, but note the rule it rests "
    "on no longer holds: ai_sidearm re-assembles 360 bytes across 17 runs "
    "and was played through Parade on 2026-09-19, and ai_cover pokes five "
    "bytes and was withdrawn the same day on a disc that also had wave "
    "mode on, then put back when the console showed its edit live in RAM. "
    "So 're-assembling hangs, poking does not' is retired. THIS option "
    "still hangs; the reason is simply not the one recorded.\n\n"
    "Withdrawn 2026-09-15. Every edit that RE-ASSEMBLES bytecode hangs the "
    "level load, and this is one of them.\n\n"
    "Bisected on the disc twice: canon_team alone froze the split-screen load "
    "on Island Estate, and ss_man_down alone froze the initial load with "
    "removing it loading fine. Against that, all four options that merely poke "
    "bytes in place -- the equipment wheel, the draw animation, the RPG speed "
    "and the scope overlay -- work, and split_scope was watched working the "
    "same day. Two of two against four of four is not a coincidence about the "
    "features; it is the rewrite path.\n\n"
    "Measured and cleared, so the next attempt need not redo it: the assembler "
    "is faithful -- 6,726 of the package's 6,789 script blocks round-trip "
    "byte-identically through it with zero wrong byte streams and zero wrong "
    "declared sizes, the 63 misses being the block scanner's own false "
    "positives. The LIN container is faithful -- every edit repacks to the "
    "same length AND decompresses back to exactly the bytes put in. The "
    "archive layout is clean -- no file moves, no size changes. And there is "
    "no second copy of the script size beside the block being missed.\n\n"
    "What all of them have in common, and the byte-poke edits never do, is "
    "that the block's declared MEMORY size shrinks -- ss_man_down -10, "
    "canon_team -3, ai_sidearm -3, ss_chatter -28 -- while the disk length is "
    "held fixed by padding with EX_Nothing.\n\n"
    "THAT WAS TESTED AND IS NOT THE CAUSE. The padding now mixes EX_Nothing "
    "with an EX_LocalVariable carrying one of the block's own refs -- compact "
    "on disk, four bytes in RAM -- so both the disk length and the memory size "
    "land on their original values exactly, measured for all four edits. "
    "ss_man_down was rebuilt that way, put on a disc reading mem=375 disk=283 "
    "against a stock 375/283, and STILL hung the initial load. So the declared "
    "size is not it either.\n\n"
    "THE CHUNK PADDING WAS NOT IT EITHER. The disc's own packer never "
    "leaves a byte after a compressed stream -- zero such chunks in any "
    "shipped COMMON package -- while this rebuild zero-padded any chunk "
    "that re-deflated smaller than its slot, 167 bytes for ss_man_down. "
    "lin._deflate_exact now fills the slot exactly; ss_man_down went onto "
    "a disc with zero trailing bytes anywhere and hung just the same. And "
    "rpg_speed, which works, pads 163 bytes, so the correlation was "
    "already broken before the test.\n\n"
    "Where that leaves it: the bytes reaching the console are provably the "
    "bytes intended (assembler round-trips 6,726 of 6,789 blocks byte-exactly, "
    "container decompresses back identically, archive layout unchanged, "
    "declared sizes now identical), and the console still will not load them. "
    "Static inspection has run out. The next step is a savestate taken DURING "
    "the hang, or PCSX2 EE breakpoints -- not another theory.")


#: Back on offer, but the padding fix has not yet survived a level load.
#: Put back at the player's request. None of these was ever bisected to a hang
#: itself -- they were withdrawn because they share the re-assembly path with
#: the two that were. That is a real reason to suspect them and not a reason to
#: hide them, so they are selectable again and marked for what they are.
RETRY = ("ai_sidearm", "ai_sidearm_contact", "ai_say_dry")

#: Options whose patch has been written to a disc and READ BACK from it
#: -- so the bytes are known to land -- but whose effect has not been
#: watched in play. That is what the "applied" badge means, and leaving
#: these at "experimental" understated 34 options at once (1.0 pass).
#: Promotion only: nothing here is ever demoted by this table.
PROVEN_APPLIED = frozenset(('ai_hunt', 'ai_hunt_fire', 'ai_hunt_run', 'ai_trigger_hold', 'blast_decal_size', 'blast_stagger', 'breach_stun', 'burst_fire_sound', 'claymore_prox', 'dead_flashlight', 'decal_terrain', 'ff_player_victim', 'ff_retaliate', 'ff_rogue_side', 'flashbang_cost', 'fps_uncap', 'grenade_decals', 'hostage_rainbow_voice', 'impact_puffs', 'keep_viewport', 'mirror_launcher', 'mirror_scope', 'penetration', 'rogue_tango', 'slomo', 'smoke_ramp', 'spectate_no_wait', 'split_carry', 'split_down_callouts', 'split_hands', 'split_shadows', 'split_team_orders', 'split_thunt_ai', 'ss_accuracy'))


#: A second pass on 2026-09-28: the player played split screen with all
#: of these on and reported the Split Screen, Weapons and Teammates
#: groups working. `mirror_loadout` is in here on a direct retraction --
#: it was reported NOT matching earlier the same night, then confirmed
#: working after the installer and its guard were rebuilt.
#:
#: Held back deliberately, and why:
#:   spectate_enable/_no_wait  the camera still does not open for him
#:   ai_sidearm, ai_say_dry    in RETRY, which already says re-check
#:   gun_audio_fix             applied minutes earlier; no M16 or M4
#:                             has actually been heard yet
PLAYED_SPLIT_SCREEN = frozenset(('ai_trigger_hold', 'breach_stun', 'burst_fire_sound', 'claymore_prox', 'ff_player_victim', 'ff_retaliate', 'ff_rogue_side', 'keep_viewport', 'mirror_launcher', 'mirror_loadout', 'mirror_scope', 'penetration', 'rogue_tango', 'smoke_ramp', 'split_carry', 'split_down_callouts', 'split_hands', 'split_shadows', 'split_team_orders', 'split_thunt_ai', 'split_wheel_labels', 'ss_accuracy', 'ss_clark'))


#: Watched working in the running game, and what was seen:
#:   blast_decals       marks counted in a savestate, 5 of 6 rays placed
#:   blood_splats       a splat on the floor beside a body, on camera
#:   corpse_hitbox      rounds registering on a body, on camera
#:   stun_flash         the flashbang effect running -- it cost frames
#:   terrorist_grenades an enemy seen throwing a flashbang
#:   tracer_calibre     tracers seen, reported working
#:   wave_enable        the enemies it adds, reported and seen
#: Watched working in play. The 2026-09-29 session added ai_hunt, the two
#: decal options, the dead terrorist's weapon light and third person
#: (camera and reticule; see RETEST_IN_PLAY for the eye/zoom half).
PROVEN_IN_GAME = frozenset((
    'ai_hunt', 'blast_decal_size', 'blast_decals', 'blood_splats',
    'corpse_hitbox', 'dead_flashlight', 'decal_ring',
    'stun_flash', 'terrorist_grenades', 'tracer_calibre', 'tp_camera',
    'tp_reticle', 'wave_enable'))


#: Played and found wanting. These keep their badge but gain a note,
#: because "untested" would be a kinder claim than the truth.
#: `mirror_loadout` used to sit here. It was confirmed working in play on
#: 2026-09-28 after its installer was rebuilt, so the note came off rather
#: than being left to contradict its own badge.
RETEST_IN_PLAY = {
    'ai_weapon_sound':
        "Partly confirmed. An MP5A4 case was reported fixed, but "
        "enemies carrying a UMP45 and a MAC-11 were still silent on "
        "2026-09-28. Both of those are silenced weapons, which the "
        "MP5A4 is not.",
    'spectate_enable':
        "Reported not working in play on 2026-09-28, before the no-wait "
        "option existed. Re-test before trusting it: the action is Joy8 "
        "in PSX2USER.INI, and there is no HUD while spectating.",
    'tp_keep_eye':
        "Failed in play on 2026-09-29, then fixed the same day. Re-test "
        "it. The first version pointed PlayerTick's gate at "
        "m_bFixCamera on the claim that nothing wrote it; it has a live "
        "writer and CalcBehindView reads it, so the gate could close "
        "for good rather than never close. It now points at "
        "m_bCameraGhost, which was measured inert: no writer, no "
        "reader, and no class-defaults entry anywhere in the package "
        "set.\n\n"
        "Three things ride on this one gate, because the weapon recoil "
        "shake lives inside SetEyeLocation with the eye write: the eye "
        "position the auto-aim traces from, the FOV interpolation every "
        "zoom needs, and the shake. Play reported all three missing, "
        "which is what identified the gate.",
}


#: Withdrawn 2026-09-24 without ever being played: the same first-touch
#: change as ss_man_down, found by the suite's creation-order check.
FIRST_TOUCH = ("ss_chatter_kill", "ss_chatter_hostage")

FIRST_TOUCH_REASON = (
    "Withdrawn 2026-09-24 before it was ever played. It adds `new "
    "R6PriceVoices` to PlaySoundInflictedDamage, which makes that function "
    "the first place the split-screen package touches the R6PriceVoices "
    "class -- earlier than the stock stream does. The loader creates, and "
    "then reads from the recording, a package's own objects in the order "
    "their first references are serialized, so this change reads the "
    "recording out of step. The death call-out makes the same change in "
    "PlaySoundDamage and hung the load on a disc carrying nothing else, and "
    "the same kind of change hung Oil Refinery on 2026-09-23. It returns "
    "when the line can be spoken without moving that first reference.")

RETRY_NOTE = (
    "RISKY. This edit RE-ASSEMBLES UnrealScript rather than poking bytes in "
    "place, and that path has frozen this disc's level load twice -- once on "
    "the initial load, once in split screen. Those two were different options, "
    "not this one, and this one has never been bisected to a hang on its own. "
    "It is switchable because suspicion by association is not proof, not "
    "because it is known to be safe.\n\n"
    "What is known: the assembler is faithful (6,726 of 6,789 script blocks "
    "round-trip byte-identically), the container repacks to the same length "
    "and decompresses back to exactly the bytes put in, the archive layout "
    "does not move, and the declared memory size now lands on its original "
    "value exactly. Three separate theories of the cause -- the shrinking "
    "memory size, the chunk padding, the declared size -- were each tested and "
    "each cleared. The cause is still not known.\n\n"
    "So: expect it to work, be ready for it not to. If a load hangs, this is "
    "the first thing to turn off, and RESTORE DISC puts the disc back exactly "
    "as it shipped.")


#: How far each enemy card is from the Xbox build, measured 2026-09-23 from the
#: pristine PS2 disc and the stock Xbox `xboxdynamic.umd`: the global INI keys,
#: all 118 PS2 / 114 Xbox terrorist templates, the pawn and AI class defaults,
#: the 29 terrorist weapons' accuracy fields and the sight/aim code. The two
#: builds differ in exactly three places -- the Recruit skill multiplier, the
#: templates (99 of the 108 both ship were retuned for PS2), and a PS2-only
#: distance factor on enemy shot spread (`R6Weapons.GetFiringDirection`,
#: FloatConsts 0.5 / 0.5 / 1.0 at plain 0x1DDCE0 / 0x1DDCF3 / 0x1DDCF9).
XBOX_NOTES = {
    "terro_skill": (
        "Xbox ships 0.40 / 0.70 / 1.25 -- only Recruit differs (0.20 here). "
        "To match it, set Recruit to 0.40: no choice on this card does that, "
        "but 'Play it the way the Xbox build does' > Enemies writes exactly "
        "that key."),
    "xbox_tuning": (
        "Enemies writes the one enemy key the two INIs disagree on (Recruit "
        "skill 0.20 -> 0.40). It cannot reach the rest of the difference: the "
        "PS2 port retuned 99 of the 108 enemy templates both discs ship, and "
        "only the PS2 build scales enemy shot spread with distance. So Veteran "
        "and Elite enemies stay PS2-tuned -- on Elite they settle their aim "
        "about 1.5x faster than the Xbox's do."),
    "enemy_aim": (
        "Xbox templates are lower but far more random: on average Assault 54, "
        "SelfControl 54 and Observation 66, and 48 of them add a 0-50 roll to "
        "every skill at each spawn. PS2 averages 69 / 63 / 77, and 93 of its "
        "118 templates roll only 0-10. After the roll PS2 enemies still lead "
        "by about 7 Assault, 4 Observation and 1 SelfControl, with much less "
        "spread. One value here cannot reproduce that."),
    "sight": (
        "Xbox ships the same 5000 and the same observation scaling -- leave "
        "it. The difference is the Observation skill in the templates: Xbox "
        "enemies see about 9% farther on Recruit, PS2's about 2% farther on "
        "Veteran and Elite."),
    "spotting": (
        "Xbox ships the same four movement factors (0.8 / 0.6, 1.2 / 1.4). "
        "Leave it at Stock."),
    "perfect_dist": (
        "Xbox ships the same 500. Past it, only the PS2 build scales an "
        "enemy's shot spread with distance: tighter than Xbox from 5 to 17 m, "
        "up to 1.5x looser beyond 50 m. No card changes that factor yet."),
    "fire_delay": (
        "Xbox ships the same 1.0 s and 0.5 s, and no delay on Elite. Leave it "
        "at Stock."),
    "enemy_loadout": (
        "37 enemy templates carry a different gun on Xbox -- Airport's G3A3, "
        "M249 and TAR21 are L85A1s here, Oil Refinery's P90, SR2 and M1 are "
        "AUGs or PSG1s. Every gun's accuracy stats are identical on both "
        "discs, so this is which gun, not how well a gun shoots."),
    "search_time": "Same value on the Xbox build.",
    "speed": "Same value on the Xbox build.",
    "toughness": "Same value on the Xbox build.",
}


#: Cards whose value lives in `R6GameplaySettings`, an UnrealScript class whose
#: `config` properties are read from `R6GAMESETTINGS.INI` ONCE, at boot. The
#: caution used to sit on `toughness` alone; it applies to all of these, and
#: two are worse than "restart" -- `m_fSightRadius` is copied into each pawn's
#: `SightRadius` when it spawns, and the difficulty skill multiplier is baked
#: in `R6Terrorist.CommonInit`, so those need a NEW MISSION, not just a fresh
#: boot. Measured 2026-09-25, and named as the most likely reason someone
#: decides one of these sliders does nothing.
INI_BACKED = ("grenade_dist", "grenade_delay", "terro_skill", "perfect_dist",
              "fire_delay", "sight", "search_time", "speed", "spotting",
              "toughness", "xbox_tuning", "player_mags", "sens_boost")
INI_BACKED_NOTE = (
    "The game reads this once, when it starts. Apply to the disc, then "
    "restart the emulator -- changing it while the game is running does "
    "nothing.")
#: The two that are not merely boot-time: they are copied per pawn at spawn.
INI_PER_MISSION = ("sight", "terro_skill", "xbox_tuning")
INI_PER_MISSION_NOTE = (
    "This one is copied onto each enemy as it spawns, so a mission already "
    "in progress keeps the old value even after a restart -- start the "
    "mission again to see it.")


#: Cards word their not-played warning half a dozen ways -- "Not yet
#: played.", "Never played.", "NOT YET PLAYED -- ...". Pinning the strip
#: to one literal left two verified cards still telling the reader they
#: had never been played, which is worse than not badging them at all.
_UNPLAYED = re.compile(
    r"^\s*(not yet played|never played|not play-tested)\b[^.]*\.\s*",
    re.I)


def _drop_unplayed_claim(caution):
    """Remove a leading 'never played' sentence from a caution."""
    out = _UNPLAYED.sub("", caution or "", count=1)
    return out.strip()


def _settings():
    import dataclasses

    out = _build_settings()
    for s in out:
        if s.key in INI_BACKED and s.enabled:
            note = INI_BACKED_NOTE
            if s.key in INI_PER_MISSION:
                note += " " + INI_PER_MISSION_NOTE
            if note not in (s.caution or ""):
                s.caution = (s.caution + "\n\n" if s.caution else "") + note
    for s in out:
        if s.key in RETRY and s.enabled:
            s.confidence = "untested"
            s.caution = RETRY_NOTE + ("\n\n" + s.caution if s.caution else "")
        if s.key in REASSEMBLED and s.enabled:
            s.enabled = False
            s.confidence = "broken"
            s.disabled_reason = REASSEMBLED_REASON
        if s.key in FIRST_TOUCH and s.enabled:
            s.enabled = False
            s.confidence = "broken"
            s.disabled_reason = FIRST_TOUCH_REASON
    # 1.0: badges that match the evidence. Promotion only, and the
    # "Not yet played." line is stripped from anything that HAS been
    # played, because leaving it there contradicts its own badge.
    for s in out:
        if not s.enabled:
            continue
        if s.key in PROVEN_APPLIED and s.confidence == "experimental":
            s.confidence = "applied"
        if s.key in PROVEN_IN_GAME or s.key in PLAYED_SPLIT_SCREEN:
            s.confidence = "verified"
            s.caution = _drop_unplayed_claim(s.caution)
        # A card cannot claim it was watched working while its own caution
        # OPENS by saying it was not. The caution is the deliberate
        # sentence; the badge may simply be a default nobody chose. Mid-text
        # is left alone on purpose -- `split_wheel_labels` says the option
        # works and that one NEWER PART of it has not been played, which is
        # a real distinction worth keeping.
        if s.confidence == "verified" and _UNPLAYED.match(s.caution or ""):
            s.confidence = "applied"
        note = RETEST_IN_PLAY.get(s.key)
        if note and note not in (s.caution or ""):
            c = (s.caution or "").replace("Not yet played.", "").strip()
            s.caution = note + ("\n\n" + c if c else "")
    # Copies, not edits: several of these cards come from builders the other
    # Unreal-family profiles share.
    return [dataclasses.replace(
                s, help=(s.help + "\n\n" if s.help else "")
                + "Compared with the Xbox build: " + XBOX_NOTES[s.key])
            if s.key in XBOX_NOTES else s for s in out]


def _build_settings():
    return [
        # ---- wave mode -------------------------------------------------
        Setting("wave_enable", "Enable wave mode", BOOL, False, "Enemies",
                help="Rainbow Six 3 already ships a terrorist deployment-zone "
                     "system that the campaign uses and Terrorist Hunt never "
                     "triggers. This switches it on and hands you its dials.",
                caution="Split-screen Terrorist Hunt and split-screen "
                        "practice have both been played with this on "
                        "(Shipyard, 2026-09-25) and both load. That "
                        "supersedes the older note that Terrorist Hunt would "
                        "not finish loading, which was measured on Parade "
                        "while the map-wide spawn option's cheat file was "
                        "being written to a PCSX2 the game was not launched "
                        "from -- a disc patched for waves WITHOUT that cheat "
                        "file asks the shipped spawn picker for far more "
                        "points than one zone can serve. So keep the cheat "
                        "file and the disc in step. Single-player Terrorist "
                        "Hunt has not been retried since.",
                confidence="verified"),
        Setting("wave_gate", "Where waves feed", CHOICE, "always", "Enemies",
                choices=[
                    Choice("always", "Every zone, all the time",
                           "Loudest option. Every deployment zone runs from the "
                           "moment the level starts."),
                    Choice("away", "Only zones you have left",
                           "The far zone feeds and pushes you back, and the zone "
                           "you walk out of starts up behind you. Needs a map "
                           "whose zones are far enough apart to be in different "
                           "engine zones -- Trieste shows it, Alcatraz cannot."),
                    Choice("stock", "Only where you are standing (stock rule)",
                           "The shipped behaviour. Enemies appear on top of you."),
                ],
                help="The engine gates the wave advance on the zone's stasis "
                     "flag, and it clears that flag for the zone containing a "
                     "player. This picks which way the test runs.",
                requires={"wave_enable": True}, confidence="verified"),
        Setting("wave_total", "Enemies each zone owes", INT, 30, "Enemies",
                minimum=1, maximum=250, unit="enemies",
                help="Total a single deployment zone will release before it is "
                     "spent. A map with three zones triples this.",
                requires={"wave_enable": True}, confidence="verified"),
        Setting("wave_size", "Released per wave", INT, 1, "Enemies",
                minimum=1, maximum=8, unit="enemies",
                help="How many come out each time a wave fires. The game ships "
                     "these zones set to release 1 or 2. Capped by the number "
                     "of spawn points the zone can reach, so on most maps "
                     "anything above 2-4 does nothing -- and each release the "
                     "zone cannot place still costs the console a whole enemy "
                     "to build and throw away, so a high number here is the "
                     "most expensive setting on this page.",
                requires={"wave_enable": True}, confidence="verified"),
        Setting("wave_trigger", "Alive before the next wave", INT, 2, "Enemies",
                minimum=0, maximum=12, unit="enemies",
                help="THE VOLUME DIAL. A zone tops itself up until more than "
                     "this many of its enemies are alive, so steady state per "
                     "zone is about this number plus the release size. The game "
                     "ships these zones set to 1. Set this first, then the wave "
                     "size, then the total.",
                requires={"wave_enable": True}, confidence="verified"),
        Setting("wave_hunt", "Enemies hunt you from the start", BOOL, False,
                "Enemies", enabled=False,
                disabled_reason=(
                    "Withdrawn 2026-09-26: measured inert. It set "
                    "m_bHuntFromStart on the WAVE actor, and the only code "
                    "that reads that flag reads it from the SPAWN POINT "
                    "instead -- a wave never spawns anything itself, it picks "
                    "a point and calls that point's spawner, so the bit it "
                    "set was never looked at. Use \"Enemies hunt you\" "
                    "instead, which reaches the same enemies through script."),
                help="Withdrawn. It claimed to make wave-released enemies "
                     "start out hunting, and it did nothing at all.\n\n"
                     "What it wrote was correct in itself -- three "
                     "instructions setting the hunt flag as the wave zone "
                     "starts up. The flag was simply on the wrong object. "
                     "A wave zone does not create enemies; it picks one of "
                     "the level's spawn points and asks that point to do it, "
                     "and the code that decides whether a new enemy hunts "
                     "reads the flag off the point it came from. The wave's "
                     "own copy is read by nothing.\n\n"
                     "The behaviour it promised is real and is now delivered "
                     "by \"Enemies hunt you\" in the same group, which "
                     "rewrites the decision itself rather than a flag feeding "
                     "it -- and reaches the wave-released enemies too, who "
                     "skip that decision entirely because of a separate "
                     "latch the wave sets on their controller.",
                caution="Nothing here ever let anyone see through walls; the "
                        "engine has no such flag.",
                requires={"wave_enable": True}, confidence="broken"),
        Setting("wave_mapwide", "Spawn across the whole map", BOOL, True,
                "Enemies", pnach_only=True,
                help="Stock, a wave can only use the two or three spawn points "
                     "sitting next to it, so every enemy walks out of one corner. "
                     "This redirects the picker at every deployment point in the "
                     "level, which also brings a real spread of enemy types.",
                caution="Delivered as a PCSX2 cheat file, not written to the "
                        "disc. A code cave baked into the overlay does not "
                        "survive a level load.\n\n"
                        "This used to bring the game to a crawl, and that is "
                        "fixed as of 2026-09-25 -- but the fix is in the "
                        "cheat file, so SAVE A FRESH ONE after updating. The "
                        "game credits each new enemy to the spawn point's "
                        "owning zone rather than to the zone that asked, and "
                        "most points have no owner (on Shipyard, 14 of 18), "
                        "so enemies were built and placed correctly while "
                        "nobody was credited -- leaving the zone below its "
                        "refill threshold and releasing another batch every "
                        "single frame. Measured on Shipyard: 2,492 enemies "
                        "in 132 seconds, about two frames a second. The cave "
                        "now hands the point to the zone that asked, so the "
                        "count advances.\n\n"
                        "Two things follow. A zone's \"keep this many alive\" "
                        "becomes \"keep this many of mine alive ANYWHERE on "
                        "the map\", so the pressure is global rather than "
                        "local and the zone next to you goes quiet once its "
                        "quota is alive elsewhere. And zones now genuinely "
                        "spend their budget and fall silent when it is gone, "
                        "which is what \"enemies each zone owes\" was always "
                        "meant to mean -- so raise that number if you want "
                        "waves to keep coming. Turning this option off is "
                        "best followed by reloading the level.",
                requires={"wave_enable": True}, confidence="verified"),


        # ---- enemy behaviour, straight out of R6GAMESETTINGS.INI ---------
        Setting("grenade_carry", "How many enemies carry a grenade", INT, 20,
                "Enemy Behaviour", minimum=0, maximum=100, unit="%",
                confidence="applied", touches="data",
                help="This is the real grenade dial. What a terrorist spawns "
                     "holding is a weighted roll made once, at spawn, over a "
                     "small table in his template -- and sixteen of the "
                     "templates roll a grenade against nothing at somewhere "
                     "between 15 and 30 percent. This sets that share.",
                caution="There is no *throw* chance anywhere in the game. Once "
                        "a terrorist is holding a grenade the decision to use "
                        "it is deterministic, gated by the two settings below. "
                        "So this is how many of them can throw, and those are "
                        "when."),
        Setting("grenade_dist", "How close enemies will throw grenades", INT,
                500, "Enemy Behaviour", minimum=25, maximum=900,
                unit="units", confidence="applied", touches="data",
                help="The game will not let an NPC throw a grenade at anything "
                     "nearer than this. It ships at 500. Lower it and they use "
                     "grenades in close quarters instead of only lobbing them "
                     "across a room; raise it and grenades become a long-range "
                     "answer only."),
        Setting("grenade_delay", "How long they think about it first", CHOICE,
                "stock", "Enemy Behaviour", confidence="applied", touches="data",
                choices=[
                    Choice("stock", "Stock (1.0s recruit, 0.5s veteran)", ""),
                    Choice("quick", "Quicker (0.5s / 0.25s)",
                           "Roughly twice as many grenades in the same fight."),
                    Choice("instant", "Barely any (0.1s / 0.05s)",
                           "They throw the moment they have a reason to."),
                ],
                help="The reaction delay before an NPC commits to a throw. "
                     "Shortening it is the closest thing this game has to a "
                     "throw-chance dial."),
        Setting("molotov_everywhere", "Molotovs on every level", BOOL, False,
                "Enemy Behaviour", enabled=False, confidence="broken",
                touches="data",
                disabled_reason=(
                    "Withdrawn. An earlier build of this tool switched on a "
                    "per-map weapon table -- WS[43], R6MolotovGadget, shipped "
                    "true on Alcatraz only -- and that table is dead data on "
                    "PS2: the words bUsing, weaponname and sndName0 appear "
                    "ZERO times in the overlay, the boot executable and every "
                    "level package, so nothing can read those lines. Two maps "
                    "already ship it true and have no molotov enemies. It is a "
                    "leftover of the Xbox and PC sound-bank system."),
                help="Which enemies carry a molotov is decided by the terrorist "
                     "templates in COMMON, and only four of the 118 offer one. "
                     "Giving it to the others means replacing a class name with "
                     "a longer one, which a LIN package cannot take, so this "
                     "needs a different technique rather than a bigger number."),
        Setting("terro_skill", "Enemy skill", CHOICE, "stock",
                "Enemy Behaviour", confidence="applied", touches="data",
                choices=[
                    Choice("stock", "Stock (0.20 / 0.70 / 1.25)", ""),
                    Choice("up", "Sharper (+40%)", ""),
                    Choice("elite", "Everyone near-elite",
                           "All three tiers at 1.25, so recruits shoot like "
                           "elites do."),
                    Choice("down", "Softer (-40%)", ""),
                ],
                help="The per-difficulty multiplier the AI scales its aim and "
                     "its reactions by."),
        Setting("perfect_dist", "Range at which enemies never miss", INT, 500,
                "Enemy Behaviour", minimum=50, maximum=3000, unit="units",
                confidence="applied", touches="data",
                help="`m_fDistanceForPerfectAccuracy`, which the disc ships "
                     "at 500. It is the distance inside which the game marks "
                     "a shot as point-blank.\n\n"
                     "TRACED AND FOUND INERT (2026-09-25): the only code "
                     "that reads this sets a flag on the enemy, and nothing "
                     "reads that flag back -- all 53 uses of it were "
                     "classified. The spread maths never consults it, and "
                     "the distance term in the aim cone is a fixed 5000 that "
                     "no setting can reach. So this almost certainly does "
                     "nothing. The claim it used to carry here -- that "
                     "lowering it is the most direct way to make enemies "
                     "less lethal up close -- was not supported by the "
                     "code. Use the aim slider or the difficulty "
                     "multiplier instead."),

        # ---- shared with the other two Unreal-family discs ---------------
    ] + r6tuning.cards(
        ["fire_delay", "sight", "search_time", "speed", "spotting",
         "toughness"],
        "", "Enemy Behaviour",
    ) + xboxbuild.cards(xboxbuild.R6_3, "", "Enemy Behaviour") \
      + rseloadout.cards("r6_3_slus20883", "", "Enemy Behaviour") \
      + [rseloadout.flashlight_card("", "Enemy Behaviour")] \
      + [rserpg.card("", "Enemy Behaviour")] \
      + r6tuning.cards(["player_grenades", "player_mags"], "", "Loadout") + [

        # ---- teammates ---------------------------------------------------
        Setting("ai_finite_ammo", "AI teammates run out of ammunition", BOOL,
                False, TEAM_GROUP, confidence="verified", touches="data",
                help="The disc ships `m_bUnlimitedRainbowMagazines=true`, so "
                     "Price, Weber and Loiselle never spend a magazine no "
                     "matter how long a fight runs. This turns it off, and "
                     "they carry what the mission planner says they carry.\n\n"
                     "It is also the switch that puts their ammunition "
                     "callout back. \"No ammo, sir\" and \"Weapon's dry\" are "
                     "recorded in all three operatives' voice banks and wired "
                     "to a live event -- they simply never fire, because a "
                     "man with unlimited magazines is never dry. Turn this on "
                     "and you start hearing them.",
                caution="Their weapons deplete for the whole mission and "
                        "there is no way to pick one up off the ground, so a "
                        "long fight ends with the team on sidearms. That is "
                        "the point of the option, but it is a real change to "
                        "how a level plays. Trieste is the exception worth "
                        "knowing about: of the 567 teammate loadouts on the "
                        "disc, every one fills the secondary slot, but 21 of "
                        "Trieste's put a breaching charge or a flashbang "
                        "there instead of a pistol -- so on that level they "
                        "have nothing to fall back on."),
        Setting("ai_dry_rounds", "Rounds left in a weapon that has run dry",
                INT, 5, TEAM_GROUP, minimum=0, maximum=30, unit="rounds",
                confidence="applied", touches="data",
                requires={"ai_finite_ammo": True},
                help="`m_iNbOfBulletWhenEmpty`, which the disc ships at 5 and "
                     "describes in its own comment as \"bullets to put in "
                     "primary weapon when all clips are empty\". It is the "
                     "reserve a teammate falls back on once the magazines are "
                     "gone, and with unlimited magazines on it is unreachable "
                     "-- so the shipped 5 has never done anything.\n\n"
                     "Set it to 0 and running out means running out.",
                caution="A non-zero reserve appears to be re-granted rather "
                        "than issued once, which would mean they are never "
                        "permanently dry and the callout stays rare. That "
                        "reading comes from the key's comment and its name, "
                        "not from watching the code, so 0 is the setting to "
                        "use if you want the line reliably."),
    ] + rsesidearm.cards("", TEAM_GROUP) + rsekits.cards("", TEAM_GROUP) + [
        # `team_match_player` just above rewrites the map INI, so the AI
        # copy the kit the mission HANDS the player. These copy what the
        # player actually chose in the gear room this run, in RAM, and
        # they are applied later -- so with both on, these win. See
        # rsemirror.
        *rsemirror.cards("", TEAM_GROUP),
        rseaifire.card("", TEAM_GROUP),
        rseburstsnd.card("", "Weapons"),
        rsesoundgate.card("", TEAM_GROUP),
        rsefollowleg.card("", TEAM_GROUP),

        # ---- controls ----------------------------------------------------
        Setting("sens_steps", "Look sensitivity ceiling", INT, 10, "Controls",
                minimum=10, maximum=30, unit="steps", confidence="applied",
                touches="data",
                help="The in-game sensitivity slider stops at 10. This raises "
                     "how far it goes, so there are faster settings to pick "
                     "than the game normally offers.",
                caution="This lifts the ceiling for BOTH players. It does not "
                        "by itself make player 2 match player 1 -- why player 2 "
                        "is slower at the same number is a separate question, "
                        "and it is still being investigated."),
        Setting("sens_boost", "Look speed at each step", INT, 100, "Controls",
                minimum=50, maximum=400, unit="%", confidence="applied",
                touches="data",
                help="Scales the sensitivity multiplier and the per-step "
                     "increment together, so every notch on the slider moves "
                     "the camera further. 100% is stock."),

        # ---- split screen ----------------------------------------------
        Setting("viewmodel", "Show your weapon in split screen", BOOL, True,
                "Split Screen",
                help="The engine switches the first-person weapon off the moment "
                     "it detects split screen, through a global with exactly one "
                     "writer in the whole overlay. This removes that write.",
                confidence="verified"),
        Setting("fx_impact", "Bullet impact decals", BOOL, True, "Split Screen",
                help="Two branches skip the bullet-hole decal in split screen: "
                     "one for hits on the static world, one for hits on actors.",
                confidence="verified"),
        Setting("fx_emitters", "Bullet impact puffs and sparks", BOOL, True,
                "Split Screen",
                help="The dust/spark emitter that goes with an impact is skipped "
                     "in split screen by a third branch.",
                confidence="verified"),
        Setting("fx_blood", "Blood effects", BOOL, True, "Split Screen",
                confidence="verified",
                help="Restores the blood-effect position update."),
        rsewheel.card("", "Split Screen"),
        rsewheel.cycle_card("", "Split Screen"),
        rsewheel.label_card("", "Split Screen"),
        rseorders.card("", "Split Screen"),
        rsecallouts.card("", "Split Screen"),
        rsedowncall.card("", "Split Screen"),
        *rseviewport.cards("", "Split Screen"),
        *rsespectate.cards("", "Split Screen"),
        rseroguecall.card("", "Split Screen"),
        rsethuntai.card("", "Split Screen"),
        rsegadget.card("", "Weapons"),
        rseclaymore.card("", "Weapons"),
        rseclaymore.arc_card("", "Weapons"),
        *rsedecal.cards("", "World"),
        *rsepuffs.cards("", "World"),
        rsehostagerun.card("", "World"),
        rsecorpsehit.card("", "World"),
        rseflashcost.card("", "World"),
        rsegunaudio.card("", "Weapons"),
        *rsethirdperson.cards("", "Controls"),
        *rsetracer.cards("", "Weapons"),
        *rseslomo.cards("", "World"),
        *rsepenetrate.cards("", "Weapons"),
        *rseaihunt.cards("", "Enemies"),
        rsemolotov.card("", "Enemies"),
        rsesmoke.card("", "Weapons"),
        rseuzilight.card("", "Weapons"),
    ] + rseff.cards("", "Teammates") + [
        rsehands.card("", "Split Screen"),
        rsecarry.card("", "Split Screen"),
        rsescope.card("", "Split Screen"),
        rsedraw.card("", "Split Screen"),
        rseviewmodel.card("", "Split Screen"),
        rseviewmodel.turn_card("", "Split Screen"),
        rsefov.card("", "Split Screen"),
        rsemuzzle.card("", "Split Screen"),
        rseswitch.card("", "Weapons"),
        rsesquad.card("", "Split Screen"),
        rsehudteam.card("", "Split Screen"),
        rseclark.card("", "Split Screen"),
        rseteam.card("", "Split Screen"),
        rserescue.card("", "Split Screen"),
        rseshadow.card("", "Split Screen"),
        Setting("fx_weather", "Rain and snow", BOOL, True, "Split Screen",
                confidence="applied",
                help="Weather is gated off in split screen by a single branch."),
        Setting("fx_hidden_emitters", "Fire, water and scenery emitters", BOOL,
                True, "Split Screen",
                help="Levels flag a handful of emitters `HideInSplitScreen` and "
                     "the engine disables exactly those -- six per level, and "
                     "they are always the fire and water next to the players.",
                confidence="verified"),
        Setting("p2_look_speed", "Player 2 look speed", INT, 1, "Split Screen",
                minimum=1, maximum=256, unit="x", confidence="verified",
                help="Player 2 turns more slowly than player 1, and the cause "
                     "is one instruction. The input routine computes its own "
                     "frame delta, then at 0x00142048 substitutes 0.05 s for "
                     "it -- but only for pad index 1, and only when the real "
                     "frame is under 33 ms, which at any playable frame rate "
                     "is always. The look rate is `20.0 / delta`, so a delta "
                     "that has been made larger is a look rate that has been "
                     "made slower.\n\n"
                     "Nothing else differs. All 503 properties of the two "
                     "player controllers, both input objects and both 3 KB "
                     "viewport structs were compared from a savestate of both "
                     "players turning: every term in the look formula -- the "
                     "sensitivity steps, the option bits, the base rates, the "
                     "global multiplier, the acceleration terms -- is "
                     "byte-identical. The only thing that is not the same is "
                     "that register.\n\n"
                     "This dial does not remove the clamp. It rewrites the "
                     "lui/ori pair that builds the constant, so the "
                     "substituted delta becomes 0.05 / x. 1 leaves the disc "
                     "alone; 2 doubles player 2's look speed, 4 quadruples it, "
                     "and so on.",
                caution="3 is parity. Calculated, then confirmed in play. "
                        "Was: calculated rather than "
                        "guessed. Stock substitutes 0.05 s, which at 60 fps "
                        "is exactly three frames -- so player 2 turns at a "
                        "third of player 1's rate, which is the complaint. "
                        "3 makes the substituted value one real frame.\n\n"
                        "Do not try to match player 1's own delta. Measured "
                        "from a savestate of both players turning at full "
                        "stick, player 1's was 0.00032 s: the routine runs "
                        "more than once a frame, and player 1's rate is "
                        "applied over a correspondingly short interval, so "
                        "it self-corrects. Player 2's is a CONSTANT applied "
                        "over whatever the real interval turns out to be, so "
                        "it does not. That is why the earlier version of this "
                        "card -- a switch that removed the clamp outright -- "
                        "play-tested as an instant top turn rate, and why 32 "
                        "play-tested as far too fast: 32 leaves player 2 a "
                        "rate meant for a tenth of a frame.\n\n"
                        "Values above about 4 are for players who want player "
                        "2 faster than parity, not for matching. One cheap "
                        "check on the whole chain: the same clamp divides "
                        "player 2's MOVEMENT axes too, so if walking speed "
                        "shifts with this, the mechanism is confirmed end to "
                        "end."),
        Setting("p2_settings_persist", "Keep player 2's settings between "
                "missions", BOOL, False, "Split Screen", enabled=False,
                confidence="broken",
                disabled_reason=(
                    "Not shipped, and not for want of looking: eight "
                    "persistence layers and sixteen store sites were traced and "
                    "every one is symmetric between the two players. The one "
                    "remaining candidate -- that the level-start settings copy "
                    "runs once per level rather than once per player -- cannot "
                    "be settled without watching it run, and if it is right the "
                    "fix is a code cave rather than a changed word. The "
                    "obvious-looking one-word version would stamp the "
                    "single-player defaults onto both controllers every frame "
                    "and break player 1 as well."),
                help="Player 2's sensitivity resets at the start of every "
                     "mission while player 1's survives."),
        Setting("ss_accuracy", "Match enemy accuracy to single player", BOOL,
                False, "Split Screen", confidence="experimental",
                touches="words",
                help="In split screen every terrorist fires along the direction "
                     "his head is facing instead of at you -- the path single "
                     "player reserves for an enemy blinded by smoke. This "
                     "makes them aim at their target, as they do in single "
                     "player.",
                caution=(
                    "One word. The native bullet-direction routine at "
                    "0x003F36F0, run for every AI shot, reads a flag at "
                    "0x006546F4 that is 1 in every split-screen mission and 0 "
                    "in every single-player one (64 and 5 savestates). When "
                    "it is set, any terrorist takes his direction from his "
                    "view rotation -- the eye bone -- instead of the aimed "
                    "rotation toward Target.Location. The branch at "
                    "0x003F3D90 becomes unconditional, so only a genuinely "
                    "smoke-blinded terrorist, tested one instruction earlier, "
                    "still aims along his head.\n\n"
                    "Single player cannot change: its flag is 0, so the "
                    "original branch was always taken, and the new one takes "
                    "the same path.\n\n"
                    "This card used to say there was nothing to switch. That "
                    "study enumerated every code path that tests split screen "
                    "and found none in aim code, which was true -- this flag "
                    "is not the split-screen flag, and it was assumed to be 0 "
                    "on retail. Comparing the live enemies found it instead: "
                    "difficulty, skill multipliers, every terrorist property "
                    "and every weapon table are identical between the modes, "
                    "and this is the one thing that is not.\n\n"
                    "Not yet play-tested, so how much sharper they get is "
                    "unmeasured. Idle guards' view directions sat 2.7 to 15.7 "
                    "degrees off their body facing, and a standing player at "
                    "10 m is about 2.2 degrees wide, so it should be very "
                    "noticeable.")),
    ] + rseaicover.cards("", "Enemies") + [rseflashlight.card("", "Enemies")] + rsefragwarn.cards("", TEAM_GROUP) + rsechatter.cards("", TEAM_GROUP) + [
        rsemandown.card("", "Split Screen"),
        rsecanon.card("", "Split Screen"),
        Setting("teammates", "AI teammates: the first attempt", BOOL, False,
                "Split Screen", enabled=False, confidence="broken",
                disabled_reason="Retired, and superseded by \"AI teammates in split screen\" above. Four attempts re-enabled the team script call and all hung the level load identically. The cause is now known and was never the script: a split-screen level file is a RECORDING of what one boot read, that boot never created the operatives, so their classes were read from the wrong bytes. Trieste works on the retail disc because its split-screen recording was made on a boot that did create them. The newer option pairs its team code with split-screen level files that read the operatives.",
                help="Split screen deliberately builds a one-man team."),

        # ---- world ------------------------------------------------------
        Setting("stun_flash", "Flashbang screen effect", CHOICE, "stock",
                "World",
                choices=[
                    Choice("stock", "Full (as it shipped)",
                           "Five seconds of white-out, and five seconds at "
                           "about a third of the frame rate."),
                    Choice("4", "Four seconds", "A fifth shorter."),
                    Choice("3", "Three seconds", "Noticeably shorter."),
                    Choice("2", "Two seconds",
                           "Still clearly a flashbang, and the slow window "
                           "drops to well under half."),
                    Choice("1.5", "One and a half seconds",
                           "About as short as it can be and still read as a "
                           "flash."),
                    Choice("off", "No screen effect at all",
                           "You are still blinded in every way that matters "
                           "to the game, but you can see. That is an "
                           "advantage, so it is not the recommended setting."),
                ],
                help="Getting flashbanged starts a full-screen wash that the "
                     "renderer redraws every frame for five seconds, and it "
                     "is the whole reason the game crawls while you are "
                     "stunned -- measured at about 12 frames a second against "
                     "30 the instant before. Nothing else about the stun is "
                     "expensive: the blindness itself is a handful of "
                     "instructions. This shortens the effect, or removes it.",
                caution="Not yet played. It does not change the stun itself. "
                        "You are blinded for the same six seconds, the enemy "
                        "AI reacts the same way, and the sound is unchanged -- "
                        "only the screen effect's length moves. Turning it "
                        "off entirely lets you see through a flashbang, which "
                        "is a real advantage in a co-op game, so a middle "
                        "value is the fairer choice.",
                confidence="experimental"),
        Setting("fps_uncap", "Let the game present 60 frames a second",
                BOOL, False, "World",
                help="Single player presents one frame per two NTSC fields, "
                     "so it tops out at 30. Split-screen Terrorist Hunt "
                     "reaches 60 -- not by design, but because split screen "
                     "builds its renderer twice and registers the frame-pacing "
                     "interrupt twice with it, which makes the counter reach "
                     "its target in half the time. This removes the limit "
                     "everywhere, so single player can present 60 too.",
                caution="Not yet played. The limit is a FLOOR on frame time, "
                        "not a lock: scenes that already run below 30 are "
                        "unaffected, so this does not fix a slow level. What "
                        "it can cost is steadiness -- light scenes run at 60 "
                        "and heavy ones drop to 30 or lower, and the switching "
                        "is visible, where a held 30 looks even. Game speed "
                        "should not change, because the engine times itself "
                        "from a measured clock rather than counting frames, "
                        "and split screen already runs this same engine at 60. "
                        "Online play is untouched.",
                confidence="experimental"),
        Setting("grenade_decals", "Explosion marks kept on screen", INT, 8,
                # 128 slots is 180 KB against a worst-observed 1.37 MiB of
                # contiguous free heap -- 12.6%, measured. The hard encoding
                # limit is 0x7FFF, because addiu sign-extends.
                "World", minimum=8, maximum=128, unit="marks",
                confidence="experimental",
                help="Blast marks live in their own ring, separate from bullet "
                     "holes, and the game only keeps EIGHT of them -- against "
                     "32 each for footprints and bullet holes. One grenade can "
                     "fill that on its own, and the next one wipes it. This "
                     "raises the ring.\n\n"
                     "Worth raising if you turn on scattered shrapnel marks, "
                     "since a single blast then spends most of the ring.",
                caution="Not yet played. The pool is built once when a level "
                        "loads, so this only takes effect on a fresh level -- "
                        "and it costs about 1.4 KB of console memory per "
                        "extra mark.\n\n"
                        "The oldest mark is dropped silently when the ring is "
                        "full; nothing fails, so a number too low just means "
                        "marks vanish sooner than you expect."),
        Setting("decal_ring", "Bullet holes kept on screen", INT, 32, "World",
                minimum=32, maximum=160, unit="decals",
                help="Footprints and wall hits share a fixed-size ring buffer, "
                     "32 each by default. Raising it is the only way to keep "
                     "more bullet holes visible -- it cannot be made unlimited.",
                caution="Each extra decal is a real actor. 96 was measured as "
                        "128 extra actors and was backed out again on the "
                        "heaviest level, so raise this one step at a time.",
                confidence="applied"),
        Setting("bodies", "How long bodies stay", CHOICE, "stock", "World",
                choices=[
                    Choice("stock", "Stock (about 3 seconds)", ""),
                    Choice("15", "15 seconds", ""),
                    Choice("30", "30 seconds", ""),
                    Choice("60", "60 seconds", ""),
                    Choice("never", "Never disappear",
                           "Unbounded. Measured to collapse the framerate far "
                           "enough that world geometry stopped drawing at some "
                           "angles."),
                ],
                help="Two separate paths hide and destroy a corpse. The timed "
                     "options skip the first and widen the second's window.",
                confidence="verified"),
    ] + _mission_settings()


#: Where the frame-pacing divider is written, and the word that writes zero
#: there instead of 2 (`sw $zero` rather than `sw $v0`).
#:
#: Single player is capped at 30 by design; split screen reaches 60 BY
#: ACCIDENT. The renderer is constructed twice in split screen and each
#: construction calls `AddIntcHandler(2, 0x0019F700, 0)`, with no matching
#: `RemoveIntcHandler` anywhere in the renderer, so the pacing ISR body runs
#: twice per vblank and the counter meets the divider after a single field.
#: Measured across 65 savestates: single player holds 1 registration, split
#: screen 2 (and 3-4 after reloads, from the same leak).
#:
#: Zero rather than one because the counter is reset at the present and
#: incremented BEFORE the compare, so `slt(1, 0)` and `slt(1, 1)` are both
#: false -- they release on the same vblank, and zero is reachable in one word.
#:
#: Deliberately NOT patched: 0x001AE464 (`addiu $v0, $zero, 2`), whose
#: register also becomes the INTC cause argument at 0x001AE490 -- changing it
#: moves the handler off vblank and destroys all pacing.
#:
#: Only `SP.SOZ` is patched. `MP.SOZ` carries the same ISR and the same write
#: at 0x001A2598, but this profile does not list that overlay.
#: Where the grenade decal ring's size is set, and how to write a new one.
#: `R6DecalGroup::Init` spawns exactly `m_MaxSize` actors into its array and
#: the cursor wraps at `m_MaxSize`, so this MUST be a disc word: raising it at
#: runtime would index past the array it was built with. Each extra slot costs
#: about 1.4 KB of `R6Decal` defaults.
GRENADE_DECALS = 0x00379B38


def grenade_decal_word(n: int) -> int:
    """`addiu $a1, $zero, n`."""
    return 0x24050000 | (int(n) & 0xFFFF)


#: `lui $v0, 0x40A0` -- the 5.0f handed to StartScreenEffect when a flashbang
#: goes off near the local player. Only the low halfword matters, and it is the
#: HIGH half of an IEEE float, so the duration is graded by rewriting it.
#: StartScreenEffect returns immediately on `duration <= 0`, so 0.0 costs
#: nothing per frame rather than running a zero-strength pass.
STUN_FLASH_SECONDS = 0x002F10C8
STUN_FLASH_WORDS = {
    "stock": 0x3C0240A0,   # 5.0
    "4": 0x3C024080,       # 4.0
    "3": 0x3C024040,       # 3.0
    "2": 0x3C024000,       # 2.0
    "1.5": 0x3C023FC0,     # 1.5
    "off": 0x3C020000,     # 0.0
}

PRESENT_DIVIDER = 0x001AE478
PRESENT_DIVIDER_FREE = 0xAF808088      # sw $zero, -0x7f78($gp)


def build_edits(v: dict) -> list:
    """Turn a settings dict into the words to bake into SP.SOZ."""
    e = []

    def w(va, value, note):
        e.append(WordEdit(va, value, STOCK[va], note))

    if v.get("tp_camera") and v.get("tp_peek"):
        # The lean roll UpdateRotation drops in behind view. One
        # branch to a nop; first person never took it. See
        # rsethirdperson.
        w(rsethirdperson.PEEK_AT, rsethirdperson.PEEK_NEW,
          "third person: peeking leans the camera")
    if v.get("flashbang_cost"):
        # One redundant store. Removing it makes the deafen block run
        # once instead of sixty times a second. It is written to the
        # disc rather than the cheat file because its page holds
        # UGameEngine::Tick, and a row re-applied every vsync would
        # keep the recompiler rebuilding it. See rseflashcost.
        w(rseflashcost.LATCH_CLEAR_AT, rseflashcost.LATCH_CLEAR_NEW,
          "flashbang: deafen once, not every frame")
    if v.get("wave_enable"):
        w(0x0040AF58, li(V0, int(v["wave_total"])),
          "wave: each zone owes %d" % v["wave_total"])
        w(0x0040A8A8, li(S0, int(v["wave_size"])),
          "wave: %d released per wave" % v["wave_size"])
        w(0x0040AFDC, li(V1, int(v["wave_trigger"])),
          "wave: next-wave trigger = %d (seed)" % v["wave_trigger"])
        w(0x0040A874, li(V0, int(v["wave_trigger"])),
          "wave: next-wave trigger = %d (rearm)" % v["wave_trigger"])
        # `wave_hunt` used to write three words here, setting
        # m_bHuntFromStart (bit 0x40 of +0x388) on the WAVE actor, in the
        # three instructions the m_iNbToSpawn constant above makes dead.
        #
        # It was inert, and the disassembly of the pristine overlay says
        # exactly why. The flag is read in ONE place --
        # AR6DeploymentZone::InitTerrorist at 0x00386B88, which sets
        # m_eStrategy = 3 (HuntRainbow) when bit 0x40 is set and bit 0x20
        # (m_bHuntDisallowed) is clear. It reads that word off `this`, and
        # `this` is never the wave: AR6DZoneWave overrides the "spawn at
        # init" slot with a stub returning 0 (0x0040AF00), and its
        # SpawnATerrorist picks a point out of m_aSpawningPoint and calls
        # THAT point's spawner through vtable+0x188 at 0x0040ACCC. So `this`
        # is the R6DZonePoint all the way down to InitTerrorist, which is
        # also what pawn->m_DZone is set to at 0x00386B04. Confirmed the
        # other way too: across 0x0040AB60..0x0040AFE0 there is not one load
        # or store of offset 0x388 at all.
        #
        # The behaviour it promised is delivered by rseaihunt's `case_wave`
        # region, which repoints R6TerroristAI.NoThreat's wave branch at
        # HuntRainbow. That is also the only thing that CAN work for these
        # enemies: the wave latches m_bSpawnedByWave on the controller at
        # 0x0040AD5C, and NoThreat tests that latch before it ever reads
        # m_eStrategy, so the strategy byte this used to aim at is computed
        # and then thrown away.
        gate = v.get("wave_gate", "always")
        if gate != "stock":
            w(0x0040A790, WAVE_GATES[gate], "wave: stasis gate = %s" % gate)

    _pen = str(v.get("penetration", rsepenetrate.DEFAULT)
               or rsepenetrate.DEFAULT)
    for _va, _stock, _new in rsepenetrate.words(_pen):
        w(_va, _new, "penetration: %s" % _pen)
    if v.get("ss_accuracy"):
        w(SS_AIM_BRANCH, SS_AIM_ALWAYS,
          "split screen: enemies aim at their target, not along their head")
    if v.get("ss_clark"):
        for va, value, _stock, note in rseclark.words():
            w(va, value, note)
    if v.get("split_muzzle"):
        # The overlay half of the muzzle fix: without it player 2 gets the
        # third-person flash as well as the first-person one, on his own
        # gun. Only ever emitted together with the COMMON attach edit.
        for va, value, _stock, note in rsemuzzle.words():
            w(va, value, note)
    if v.get("viewmodel"):
        w(0x00302DA8, NOP, "keep the first-person weapon in split screen")
        if v.get("split_sway"):
            for va, value, _stock, note in rseviewmodel.words(
                    right_too=bool(v.get("split_sway_turn")), freed=True):
                w(va, value, note)
    # One switch, three edits. They were three cards until it became clear
    # they are not independently useful: without the viewport fit the overlay
    # draws at full-screen size over both halves, and without the owner gate
    # it appears in BOTH halves the moment either player aims. Nobody wants
    # two of the three. Single player is unaffected -- measured, on a
    # single-player savestate taken from a disc carrying all three.
    scope = bool(v.get("split_scope"))
    fit = scope
    labels = bool(v.get("split_wheel")) and bool(v.get("split_wheel_labels"))
    team = bool(v.get("split_squad")) and bool(v.get("split_team_panel"))
    if scope:
        for va, value in rsescope.SCOPE_GUARD:
            w(va, value, "split screen: let the scope overlay draw, but only "
                         "once the renderer exists")
    elif (fit or labels or team
          or (v.get("viewmodel") and v.get("split_sway"))):
        # Something wants the cave but the scope option is off, so the dead
        # path still has its entry. Point that branch at the function's own
        # epilogue instead: split screen still branches away and still draws
        # nothing, exactly as stock, and the block is free.
        w(rsedeadpath.ENTRY, rsedeadpath.FREE_BRANCH,
          "split screen: retire the branch into the dead path")
    if fit:
        for va, value, _stock, note in rsescope.viewport_words(freed=True):
            w(va, value, note)
    if scope:
        for va, value, _stock, note in rsescope.owner_words():
            w(va, value, note)
    if team:
        for va, value, _stock, note in rsehudteam.words(freed=True):
            w(va, value, note)
        for va, value, _stock, note in rsehudteam.speak_words():
            w(va, value, note)
    if v.get("split_squad"):
        for va, value, _stock, note in rsedebrief.words():
            w(va, value, note)
    if v.get("split_carry"):
        # needs the layout block's restore-after-move order (split_squad)
        for va, value, _stock, note in rsecarry.words():
            w(va, value, note)
    if v.get("split_team_orders"):
        for va, value, _stock, note in rseorders.pass_words():
            w(va, value, note)
    if labels:
        for va, value, _stock, note in rsewheel.label_words(freed=True):
            w(va, value, note)
        for va, value, _stock, note in rsewheel.owner_words(freed=True):
            w(va, value, note)
    if v.get("stun_flash", "stock") != "stock":
        w(STUN_FLASH_SECONDS, STUN_FLASH_WORDS[v["stun_flash"]],
          "flashbang: screen effect lasts %s"
          % ("no time at all" if v["stun_flash"] == "off"
             else v["stun_flash"] + "s instead of 5s"))
    if v.get("wave_enable"):
        w(0x0040A8D4, 0x0202880A, "wave: a release that built nothing stops "
                                  "the rest of the batch (movz)")
        w(0x0040A8E0, 0x26310001, "wave: its counter moves to the delay slot")
    if int(v.get("grenade_decals", 8) or 8) != 8:
        n = int(v["grenade_decals"])
        w(GRENADE_DECALS, grenade_decal_word(n),
          "explosion marks: %d kept on screen instead of 8" % n)
    if int(v.get("blast_decals", 0) or 0) > 0:
        # AddDecal never writes the projector bools, so the ring keeps
        # whatever Init gave it -- and Init gives the explosion ring an
        # opaque, hard-edged, floor-only scorch. These give its own branch
        # the wall-hit look instead, which leaves its DrawScale free.
        for _va, _stock, _new in rsedecal.BRANCH_WORDS:
            w(_va, _new, "shrapnel marks: explosion decals look like "
                         "bullet holes")
        # sin(90) is sine's maximum, so the pooled decals' minProjectAngle of
        # 90 can never win the min() that builds the acceptance threshold --
        # every surface up to 89.5 degrees off square was being accepted.
        for _va, _stock, _new in rsedecal.INCIDENCE_WORDS:
            w(_va, _new, "shrapnel marks: marks stop stretching across "
                         "surfaces they barely graze")
        _dsz = float(v.get("blast_decal_size", "1.25") or 1.25)
        if _dsz != 8.0:
            w(rsedecal.DRAWSCALE, rsedecal.drawscale_word(_dsz),
              "shrapnel marks: each mark is %g x a bullet hole" % _dsz)
    _bring = int(v.get("blood_ring", 16) or 16)
    if v.get("blood_splats") and _bring != 16:
        w(rsedecal.BLOOD_RING, rsedecal.blood_ring_word(_bring),
          "blood marks: %d kept on screen instead of 16" % _bring)
    if v.get("fps_uncap"):
        w(PRESENT_DIVIDER, PRESENT_DIVIDER_FREE,
          "frame pacing: present every field, not every second field")
    if v.get("split_shadows"):
        w(rseshadow.PROJECTOR_BRANCH, rseshadow.PROJECTOR_BRANCH_OPEN,
          "split screen: draw projectors (the level render's split-screen skip)")
    if v.get("fx_impact"):
        w(0x003F1934, NOP, "split screen: static-world impact decal")
        w(0x003F1BB4, NOP, "split screen: actor-attached impact decal")
    if v.get("fx_emitters"):
        w(0x003F250C, NOP, "split screen: impact emitter")
    if v.get("fx_blood"):
        w(0x003A14B8, NOP, "split screen: blood effect")
    if v.get("fx_weather"):
        w(0x003531D0, NOP, "split screen: rain and snow")
    if v.get("fx_hidden_emitters"):
        w(0x002375E0, NOP, "split screen: stop disabling flagged emitters")
    # Player 2's look speed. The routine clamps ITS OWN frame delta to 0.05 s
    # for pad index 1 only, and the look rate is `20.0 / delta`, so the smaller
    # the substituted delta the faster player 2 turns. This does not remove the
    # clamp -- the earlier card did, and it overshot badly -- it re-aims it, by
    # rewriting the lui/ori pair that builds the constant. The clamp still
    # fires (any substituted value is far below the 0.033 s test), it stays
    # player-2-only, and the result is a dial rather than a switch.
    speed = int(v.get("p2_look_speed", 1))
    if speed > 1:
        bits = struct.unpack("<I", struct.pack("<f", 0.05 / speed))[0]
        w(0x00142040, 0x3C030000 | (bits >> 16),
          "player 2 look: x%d, delta = %g s (high)" % (speed, 0.05 / speed))
        w(0x00142044, 0x34630000 | (bits & 0xFFFF),
          "player 2 look: x%d (low)" % speed)

    ring = int(v.get("decal_ring", 32))
    if ring != 32:
        w(0x00379B30, 0x24060000 | (ring & 0xFFFF), "decal ring = %d" % ring)

    bodies = v.get("bodies", "stock")
    if bodies == "never":
        w(0x00317570, 0x1000001D, "bodies: skip despawn path 1")
        w(0x003175F4, 0x1000001D, "bodies: skip despawn path 2")
    elif bodies in BODY_TIMERS and BODY_TIMERS[bodies]:
        w(0x00317570, 0x1000001D, "bodies: skip despawn path 1")
        w(0x00317600, BODY_TIMERS[bodies], "bodies: despawn after %ss" % bodies)

    return e


SKILL_SETS = {
    "stock": ("0.20", "0.70", "1.25"),
    "up":    ("0.28", "0.98", "1.75"),
    "elite": ("1.25", "1.25", "1.25"),
    "down":  ("0.12", "0.42", "0.75"),
}
GRENADE_DELAYS = {
    "stock":   ("1.0", "0.5"),
    "quick":   ("0.5", "0.25"),
    "instant": ("0.1", "0.05"),
}
#: shipped values the percentage dial scales
SENS_BASE = {"x_mult": 0.70, "y_mult": 0.60, "x_step": 0.15, "y_step": 0.15}


def build_data(v: dict) -> list:
    """Rainbow Six 3 keeps its AI tuning and its control curve in plain text.

    `R6GAMESETTINGS.INI` ships three identical copies, one per vokes archive,
    and all three are rewritten -- the game reads whichever answers first.
    Unlike the Ghost Recon mission files these are not inside the chunked
    compressor, so the edits do not have to preserve length.
    """
    out = []

    # One edit per mission whose dial has been moved. These rewrite counts
    # inside the level packages themselves, so they reach one mission only --
    # everything else on this profile is a global code patch.
    for stem, title, parts, _waves, kind in MISSIONS:
        # training authors no counts, so its dial is disabled and must never
        # emit an edit even if a saved config carries a value for it
        if kind == "training":
            continue
        pct = int(v.get(mission_key(stem), 100))
        if pct == 100:
            continue
        out.append(FileEdit("zone_counts", mission_select(stem, parts), "",
                            {"factor": pct / 100.0},
                            note="%s: enemy counts to %d%%" % (title, pct)))

    ini = {}
    # First, so that any dial the player has set themselves overwrites
    # the Xbox value for that key rather than the other way round.
    ini.update(xboxbuild.ini_updates(xboxbuild.R6_3,
                                     v.get("xbox_tuning", "stock"),
                                     bool(v.get("xbox_extra"))))

    if int(v.get("grenade_dist", 500)) != 500:
        ini["m_fMinDistToThrowGrenade"] = int(v["grenade_dist"])
    delay = v.get("grenade_delay", "stock")
    if delay != "stock":
        rec, vet = GRENADE_DELAYS[delay]
        ini["m_fGrenadeReactionDelayRecruit"] = rec
        ini["m_fGrenadeReactionDelayVeteran"] = vet
    skill = v.get("terro_skill", "stock")
    if skill != "stock":
        rec, vet, eli = SKILL_SETS[skill]
        ini["m_fTerroristSkillMultiplierRecruit"] = rec
        ini["m_fTerroristSkillMultiplierVeteran"] = vet
        ini["m_fTerroristSkillMultiplierElite"] = eli
    if int(v.get("perfect_dist", 500)) != 500:
        ini["m_fDistForPerfectAccuracyTerro"] = "%.1f" % float(v["perfect_dist"])
    # The two keys sit together in the file under "the following is for
    # rainbow AI only", and they only make sense together: the reserve is what
    # a teammate falls back on once his magazines are gone, which cannot
    # happen while the magazines are unlimited. So the reserve is written only
    # when the switch is on, and never on its own.
    if v.get("ai_finite_ammo"):
        ini["m_bUnlimitedRainbowMagazines"] = "false"
        rounds = int(v.get("ai_dry_rounds", 5))
        if rounds != 5:
            ini["m_iNbOfBulletWhenEmpty"] = rounds
    # the dials this disc shares with Ghost Recon 2 and Advanced Warfighter.
    # The keys that overlap with the lines above resolve to the same value, so
    # merging is idempotent rather than a second opinion.
    ini.update(r6tuning.ini_updates("", v))
    steps = int(v.get("sens_steps", 10))
    if steps != 10:
        ini["m_iXSensitivityMaxSteps"] = steps
        ini["m_iYSensitivityMaxSteps"] = steps
    boost = int(v.get("sens_boost", 100)) / 100.0
    if abs(boost - 1.0) > 0.001:
        ini["m_fXSensitivityMultiplier"] = "%.3f" % (SENS_BASE["x_mult"] * boost)
        ini["m_fYSensitivityMultiplier"] = "%.3f" % (SENS_BASE["y_mult"] * boost)
        ini["m_fXSensitivityStepIncrement"] = "%.3f" % (SENS_BASE["x_step"] * boost)
        ini["m_fYSensitivityStepIncrement"] = "%.3f" % (SENS_BASE["y_step"] * boost)

    if ini:
        out.append(FileEdit("ini_values", r"/R6GAMESETTINGS\.INI$", "",
                            {"values": ini}, "AI and control settings"))
    g1 = v.get("team_gadget_1", "stock")
    g2 = v.get("team_gadget_2", "stock")
    mine = bool(v.get("team_match_player"))
    per = {}
    for who in rsekits.OPERATIVES:
        slots = {}
        for suffix, field, _what in rsekits._SLOTS:
            pick = v.get("%s_%s" % (who.lower(), suffix), "stock")
            if pick != "stock":
                slots[field] = pick
        if slots:
            per[who] = slots
    if g1 != "stock" or g2 != "stock" or mine or per:
        # Every campaign map has its own INI. Multiplayer and menu INIs
        # carry no squad kits, so the transform reports zero on them and
        # leaves them byte-identical -- which is what makes one broad
        # selector safe here.
        out.append(FileEdit("team_gadget", r"/MAPS/[^/]+\.INI$", "",
                            {"primary": g1, "secondary": g2, "match": mine,
                             "per": per},
                            "teammate gadgets"))
    if v.get("split_rescue_flag"):
        # Mission PARTS only -- a single trailing letter, which is how the
        # disc names the 27 playable level files (ISLAND_A, PARADE_B ...).
        # Trieste declares the flag on TRIESTE_A and NOT on TRIESTE.INI, so
        # the part file is what the game reads for a mission. The same
        # pattern excludes `_MP` (two letters), the `TRAINING_*` maps and
        # AUTOPLAY/DEMO/_DEBUG, none of which are rescues.
        #
        # Three maps are skipped by name, and the reason originally given for
        # it was WRONG. It rested on `m_aStartingPoint` being absent from
        # their cooked name tables -- but that name is dead everywhere: it
        # appears in 48 of 54 level builds and its encoded name index occurs
        # in no package body at all, so no actor authors a starting point on
        # ANY map and its presence or absence distinguishes nothing.
        #
        # The exclusion is kept anyway, on its one surviving fact: Alpine
        # Village A is the only map where this option has actually been
        # tested, and it wedged. The other two are the maps that share its
        # one measured peculiarity -- all three place zero deployment zones.
        # That is a weak reason, and it is recorded as weak. The remaining 23
        # maps have never been tried.
        out.append(FileEdit("rescue_flag",
                            r"/MAPS/(?!ALPINES_A\.|IMPORT_EXPORT_A\.|"
                            r"PENTHOUSE_A\.)[^/]+_[A-Z]\.INI$", "",
                            {"enable": True},
                            "every mission declares itself a rescue"))
    if v.get("split_rescue_team"):
        out.append(FileEdit("split_rescue_team",
                            r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"enable": True},
                            "split screen: build the two AI operatives"))
    if v.get("split_squad"):
        # Two halves that only work together. The team code makes a
        # split-screen boot create the operatives; the level recordings
        # give that boot the bytes it will then read. Either alone wedges
        # the load, in opposite directions -- see rsesquad and rsesplice.
        # COMMON_SS.LIN only: it is the package split screen loads, and
        # both edits sit where only split screen reaches anyway.
        # With canon_team too, this edit applies canon's first (canon lifts
        # the roster tests this one rewrites) and points those tests at
        # Price so player 2's operative is not built again as AI.
        out.append(FileEdit("squad", r"/COMMON_SS\.LIN$", "",
                            {"enable": True,
                             "canon": bool(v.get("canon_team"))},
                            "split screen: fill the team with AI"))
    if v.get("split_squad") or v.get("canon_team"):
        # The level recordings both options need, disjoint per level -- see
        # rsesplice.plan for which level reads which operatives in what order.
        for select, order in rsesplice.plan(bool(v.get("split_squad")),
                                            bool(v.get("canon_team"))):
            out.append(FileEdit("team_recording", select, "",
                                {"enable": True, "order": order},
                                "split screen: level files that read %s"
                                % " then ".join({"L": "Loiselle",
                                                 "W": "Weber"}[g]
                                                for g in order)))
    if v.get("split_muzzle"):
        # All three COMMON files. The edit cannot change single
        # player or online: the call it restores already runs there
        # through the guard's other arm. Patching all three means
        # nobody has to be right about which file split screen
        # loads, which is the only guess the change would carry.
        out.append(FileEdit("muzzle", r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"enable": True},
                            "split screen: flash on the first-person weapon"))
    rate = int(v.get("switch_rate", rseswitch.STOCK))
    if rate != rseswitch.STOCK:
        # All three COMMON files: the rate is one class default with
        # no per-mode copy, so the choice applies everywhere either
        # way. Writing all three keeps the modes consistent.
        out.append(FileEdit("switch_rate", r"/COMMON(OFF|_SS)?\.LIN$",
                            "", {"percent": rate},
                            "weapon switch animation: %d%%" % rate))
    fov = int(v.get("fov", 90))
    if fov != int(rsefov.STOCK):
        # COMMON_SS.LIN ONLY. The disc ships three script packages --
        # COMMON (online), COMMONOFF (offline) and COMMON_SS (split
        # screen) -- and the level-name buffer carries the matching
        # suffix, so split screen reads its own copy. Writing only
        # that copy keeps the campaign at the stock 90.
        out.append(FileEdit("fov", r"/COMMON_SS\.LIN$", "",
                            {"degrees": fov},
                            "field of view: %d degrees, split screen only" % fov))
    carry = int(v.get("grenade_carry", 20))
    if carry != 20:
        out.append(FileEdit("grenade_carry", r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"percent": carry},
                            "%d%% of two-entry templates carry a grenade" % carry))
    out += rseloadout.edits(v, "", r"/COMMON(OFF|_SS)?\.LIN$")
    # Withdrawn: it grows a cooked package by 107 bytes and the game then
    # will not boot. `effective()` already neutralises a disabled setting, but
    # the build site guards too rather than depending on the caller having
    # normalised -- which is the belt-and-braces the model docstring asks for,
    # and this option is the reason it is not theoretical.
    if v.get("frag_warning") and PROFILE.setting("frag_warning").enabled:
        out.append(FileEdit("frag_warning", r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"enable": True},
                            "teammates warn you about their own frag"))
    lamp = str(v.get("dead_flashlight", "stock"))
    if lamp != "stock":
        # Offline and split screen: online hides the dropped gun anyway.
        out.append(FileEdit("dead_flashlight", r"/COMMON(OFF|_SS)\.LIN$", "",
                            {"mode": lamp},
                            "a dead terrorist's weapon light stays on his gun (%s)"
                            % lamp))
    cover = str(v.get("ai_cover", "stock"))
    if cover != "stock":
        out.append(FileEdit("ai_cover", r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"set": cover},
                            "enemies fight from cover: %s"
                            % rseaicover.SHARES.get(cover, cover)))
    speed = int(v.get("rpg_speed", 1))
    if speed != 1:
        out.append(FileEdit("rpg_speed", r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"speed": speed},
                            "RPG troops ready a rocket %dx faster" % speed))
    # Gated on the ammunition switch, not merely paired with it on the page:
    # while magazines are unlimited the clip count is pinned at 1 and the
    # branch this reaches is unreachable, so writing the byte alone would be a
    # change to the disc that could not do anything.
    # The sidearm roll needs finite ammunition to be reachable at all; the
    # reload call-out does not -- it sits in the branch that runs either way.
    sidearm = int(v.get("ai_sidearm", 0)) if v.get("ai_finite_ammo") else 0
    say = int(v.get("ai_say_dry", 0))
    if sidearm or say:
        contact = bool(v.get("ai_sidearm_contact", True))
        notes = []
        if sidearm:
            notes.append("%d%% chance of drawing the pistol instead of "
                         "reloading%s"
                         % (sidearm, " while in contact" if contact else ""))
        if say:
            notes.append("%d%% chance of calling out a reload" % say)
        out.append(FileEdit("ai_sidearm", r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"chance": sidearm, "in_contact": contact,
                             "say_chance": say},
                            "; ".join(notes)))
    # A guarded hostage who has already seen a Rainbow operative says
    # nothing when one turns up -- the take exists and finished, and the
    # console build deleted its caller. Two length-neutral blocks in
    # R6HostageAI put it back. See rsehostagerun.
    # The PS2 build drops a corpse out of collision entirely, where the
    # Xbox build keeps it shootable. Four one-byte opcode swaps put the
    # Xbox behaviour back. See rsecorpsehit.
    if v.get("corpse_hitbox"):
        out.append(FileEdit("corpse_hitbox",
                            r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"enable": True},
                            "dead bodies can still be shot"))
    if v.get("hostage_rainbow_voice"):
        out.append(FileEdit("hostage_rainbow_voice",
                            r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"enable": True},
                            "hostages react out loud when Rainbow "
                            "arrives"))
    chatter = int(v.get("ss_chatter_kill", 0))
    if chatter:
        # COMMON_SS.LIN only, same reason as the canon team below.
        out.append(FileEdit("ss_chatter", r"/COMMON_SS\.LIN$", "",
                            {"chance": chatter,
                             "hostage": bool(v.get("ss_chatter_hostage", True))},
                            "split screen: %d%% chance player 2 calls out a kill"
                            % chatter))
    if v.get("canon_team"):
        # COMMON_SS.LIN only: that IS the split-screen package, which is what
        # keeps single player untouched by construction. Split-screen Terrorist
        # Hunt shares this package AND the level recordings, so it gets the
        # canon team too; keeping Price there hung the load (2026-09-24).
        out.append(FileEdit("canon_team", r"/COMMON_SS\.LIN$", "",
                            {"enable": True},
                            "split screen: player 2 is the mission's operative"))
    if v.get("ss_man_down"):
        out.append(FileEdit("ss_man_down", r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"enable": True},
                            "split screen: restore the death call-out"))
    if v.get("split_wheel"):
        out.append(FileEdit("split_wheel", r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"enable": True},
                            "split screen: open the equipment wheel on L1"))
    if v.get("split_draw_once"):
        out.append(FileEdit("split_draw", r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"enable": True},
                            "split screen: draw the weapon once, not twice"))
    if v.get("split_cycle"):
        out.append(FileEdit("split_cycle", r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"enable": True},
                            "split screen: a tap of L1 toggles two weapons"))
    if v.get("split_hands"):
        # COMMON_SS.LIN only: in the other two copies the region is live
        # single-player code. See rsehands.
        out.append(FileEdit("split_hands", r"/COMMON_SS\.LIN$", "",
                            {"enable": True},
                            "split screen: player 2's arms in the mission outfit"))
    if v.get("split_callouts"):
        # COMMON_SS.LIN only: three split-screen script functions, see rsecallouts.
        out.append(FileEdit("split_callouts", r"/COMMON_SS\.LIN$", "",
                            {"enable": True},
                            "split screen: teammates call out downs and kills"))
    if v.get("split_down_callouts"):
        # COMMON_SS.LIN only, and after "squad" above: it rewrites the
        # split-screen branch of TeamMemberDead that squad adds. See
        # rsedowncall.
        out.append(FileEdit("split_down_callouts", r"/COMMON_SS\.LIN$", "",
                            {"enable": True},
                            "split screen: teammates call out a downed player"))
        if v.get("rogue_tango"):
            # Strictly after the edit above: it rewrites two of the three
            # runs rsedowncall leaves in the file. See rseroguecall.
            out.append(FileEdit("rogue_tango", r"/COMMON_SS\.LIN$", "",
                                {"enable": True},
                                "split screen: a traitor's death is called "
                                "\"Tango down\""))
    if int(v.get("breach_stun", 10) or 10) != int(round(rsegadget.STOCK_METRES)):
        # The 60 single-player and co-op level containers -- the gadget classes
        # are not in COMMON at all. See rsegadget.
        out.append(FileEdit("breach_stun", rsegadget.SELECT, "",
                            {"metres": int(v["breach_stun"])},
                            "breaching charge: stun reach %d m"
                            % int(v["breach_stun"])))
    # Which damage state ends the mission. Both settings rewrite the downed
    # arm of the same handler the trigger dial wants, so the dial stays
    # mutually exclusive with them by `requires` -- which costs nothing on
    # "kill", the dial's own default, because that emits no dial region.
    _fail = ("fail_on_kill" if str(v.get("ff_fail_when", "kill")) == "kill"
             else "fail_on_hit")
    # "retaliate" no longer has regions of its own: the team change in the
    # trigger region IS the whole feature, and the mark-based edits it used
    # to carry were writing a flag IsEnemy never reads.
    _ff_note = {"fail_on_kill": "killing one fails the mission",
                "fail_on_hit": "wounding one fails the mission"}
    _ff = [(_fail, _ff_note[_fail])] if v.get("ff_fail_mission") else []
    # Every setting including "5" (a kill) now writes the mark from the AI's
    # own damage handler. It used to lean on SetTeamKillerPenalty for a kill,
    # and that function is never entered in Terrorist Hunt -- measured: after
    # a team kill neither player gained a bit anywhere near R6Pawn's own
    # properties, so no mark was being written and the squad never turned.
    # ...but not while the mission-failure option is on: both write the SAME
    # region of the damage handler, which is why `requires` greys the dial
    # out. That never mattered before, because a kill emitted nothing.
    if v.get("ff_retaliate") and not v.get("ff_fail_mission"):
        _lvl = str(v.get("ff_trigger", "5"))
        _side = str(v.get("ff_rogue_side", "terrorists"))
        _ff.append(("trigger:%s:%s" % (_lvl, _side),
                    "the squad turns on you at hurt level " + _lvl))
        if v.get("ff_player_victim"):
            # The shipped regions live in the AI's own damage handler, so
            # shooting the OTHER PLAYER ran none of them and the squad never
            # turned -- reported from play. These write the same mark from
            # R6Pawn.R6Died and R6PlayerController.PlaySoundDamage, the two
            # places a human casualty does go through. See rseff.
            _ff.append(("playerkill:%s:%s" % (_lvl, _side),
                        "killing the other player turns the squad too"))
        if _side == "noside":
            # The team change alone leaves him NEUTRAL, and the bullet path
            # zeroes damage against a neutral unless the shooter can fire on
            # one -- which Rainbow cannot. These two bytes are what make him
            # shootable at all, not decoration. See rseff.
            _ff.append(("noside", "a traitor is on nobody's side"))
    for _which, _note in _ff:
        # COMMONOFF + COMMON_SS only: offline and split screen. The online
        # package is left alone on purpose -- see rseff.
        out.append(FileEdit("friendly_fire", rseff.SELECT, "",
                            {"which": _which, "enable": True},
                            "friendly fire: " + _note))
    # Terrorists that hunt you: repoint the strategy switch's non-hunt cases
    # at HuntRainbow, which the game already ships and never enters.
    # `case_wave` is NOT one of the switch's arms -- it is the
    # `if (m_bSpawnedByWave)` branch that runs BEFORE the switch and skips it,
    # which is how about half the enemies on a level were missing the feature
    # altogether. A wave enemy has no authored patrol to preserve, so it
    # belongs to the gentler setting as well as to the loud one.
    _hunt = str(v.get("ai_hunt", "off"))
    _hunt_which = {"guard": ["case_guardpoint", "case_wave"],
                   "all": ["case_patrolpath", "case_patrolarea",
                           "case_guardpoint", "case_wave"]}.get(_hunt, [])
    for _w in _hunt_which:
        out.append(FileEdit("ai_hunt", rseaihunt.SELECT, "", {"which": _w},
                            "enemies hunt you: %s"
                            % _w.replace("case_", "").replace("_", " ")))
    if _hunt_which and v.get("ai_hunt_run"):
        out.append(FileEdit("ai_hunt", rseaihunt.SELECT, "",
                            {"which": "pace_run"},
                            "enemies hunt you: at a run"))
    if _hunt_which and v.get("ai_hunt_fire"):
        out.append(FileEdit("ai_hunt", rseaihunt.SELECT, "",
                            {"which": "fire_on_move"},
                            "enemies hunt you: firing while they close"))
    if v.get("uzi_flashlight"):
        # 60 of the 69 payloads carry the SR-2 mesh, two copies each; the
        # module leaves the other nine alone rather than failing on them.
        # This one GROWS the payload, so it repacks through lin.rebuild_exact
        # -- which is safe here because it adds no name, import or export:
        # the tag is an inline literal and the array's own count byte is what
        # keeps the recorded read stream in step.
        out.append(FileEdit("uzi_flashlight", r"\.LIN$", "", {},
                            "the SR-2 gets the flashlight mount it never had"))
    _smoke = str(v.get("smoke_ramp", "off"))
    if _smoke != "off":
        # One record per level container; COMMON carries only the weapon
        # package's header, so the edit is per-level by nature.
        out.append(FileEdit("smoke_ramp", rsesmoke.SELECT, "",
                            {"seconds": _smoke},
                            "smoke blinds in %s seconds instead of thirty"
                            % _smoke))
    # A MAXIMUM, not a minimum -- the comparison is `<`, disassembled and
    # cross-checked against the engine source's `native(176) ... bool < `.
    # Raising it is what produces more grenades. See rseaihunt.
    _gr = str(v.get("ai_grenade_range", "off"))
    if _gr != "off":
        out.append(FileEdit("ai_hunt", rseaihunt.SELECT, "",
                            {"which": "range:" + _gr},
                            "enemy grenades: never thrown"
                            if _gr == "0" else
                            "enemy grenades: thrown from up to %g m away"
                            % (int(_gr) / 100.0)))
    # The genuine floor, and it is not bytecode at all: the refusal in
    # R6TerroristAI.ThrowingGrenade.CheckDistance reads this straight out of
    # the settings file and adds 50 units to it.
    _gm = str(v.get("ai_grenade_min", "off"))
    if _gm != "off":
        out.append(FileEdit("ini_values", r"/R6GAMESETTINGS\.INI$", "",
                            {"values": {"m_fMinDistToThrowGrenade": _gm}},
                            "enemy grenades: thrown from as close as %g m"
                            % ((int(_gm) + 50) / 100.0)))
    # DeployCharacters hands viewport 0 to whoever leads the team after the
    # squad is rebuilt, and never unbinds the previous owner -- so a dead
    # player 1 ends up sharing player 2's controller, and player 1's buttons
    # fire on player 2's weapon. Two bytes redirect the assignment at an
    # unused local. See rseviewport.
    if v.get("keep_viewport"):
        out.append(FileEdit("keep_viewport", rseviewport.SELECT, "",
                            {"enable": True},
                            "split screen: a dead player keeps his own "
                            "screen"))
    # A dead player in split screen already has a spectator camera, and it
    # already knows how to find a living teammate. The action button that
    # opens it is disarmed EVERY FRAME by a check in PlayerTick written for
    # a network game -- offline the server state is never RSS_InGame, so the
    # ready flag is stamped false and the whole path has never been
    # reachable. `spectate_enable` is that one byte. See rsespectate.
    for _k, _note in (
            ("spectate_enable",
             "split screen: a dead player can watch a living teammate"),
            ("spectate_headcam",
             "split screen: a dead player spectates in first person"),
            ("spectate_cycle",
             "split screen: the action button changes who you watch"),
            ("spectate_no_wait",
             "split screen: no wait before the spectator camera opens")):
        if v.get(_k):
            out.append(FileEdit("spectate", rsespectate.SELECT, "",
                                {"which": _k, "enable": True}, _note))
    # Teammates are silent with some weapons because the PS2 port added
    # first-person-only sound properties and only substitutes them when
    # the pawn is a PLAYER. For guns whose third-person sample was never
    # made -- the TMP among them -- an AI gets a null and you hear the
    # trigger click and no shot. One byte retargets the gate past the Log
    # so everyone gets the override. See rsesoundgate.
    # Ten of the fifteen hostage voice sets resolve "follow me" to a
    # random container with a kind-15 NULL leg, so the acknowledgement is
    # silence one roll in three -- one in two on the Penthouse. Four bytes
    # per set re-point the NULL leg at the take beside it. No weight is
    # touched, because how the runtime reads a weight is unresolved. See
    # rsefollowleg.
    # Two shipped defects in the third-person weapon banks: the M16's
    # fire events are the only ones on the disc at 0.707 volume, and the
    # M4's are the only ones with a 3.5/4.0/60.0 distance triple instead
    # of 10.0/10.5/70.0. See rsegunaudio.
    # Three two-byte edits, offline packages only. The camera itself is
    # already written and live -- see rsethirdperson.
    for _tp in ("tp_camera", "tp_keep_eye", "tp_reticle"):
        if v.get(_tp):
            out.append(FileEdit("third_person", rsethirdperson.SELECT, "",
                                {"which": _tp, "enable": True},
                                "third person: %s" % _tp))
    if v.get("gun_audio_fix"):
        out.append(FileEdit("gun_audio_fix", rsegunaudio.SELECT, "",
                            {"enable": True},
                            "the M16 and M4 fire at the volume and range "
                            "every other weapon uses"))
    if v.get("hostage_follow_voice"):
        out.append(FileEdit("hostage_follow_voice", rsefollowleg.SELECT,
                            "", {"enable": True},
                            "hostages always answer \"follow me\""))
    if v.get("ai_weapon_sound"):
        out.append(FileEdit("ai_weapon_sound", rsesoundgate.SELECT, "",
                            {"enable": True},
                            "teammates fire with the first-person gunshots"))
    if v.get("split_thunt_ai"):
        # COMMON_SS.LIN only, and after "squad" (which applies canon first):
        # it rewrites the forms those two leave in CreatePlayerTeam. See
        # rsethuntai.
        out.append(FileEdit("split_thunt_ai", r"/COMMON_SS\.LIN$", "",
                            {"enable": True},
                            "split screen: Terrorist Hunt on the canon maps "
                            "adds the other two operatives"))
    if v.get("split_team_orders"):
        # COMMON_SS.LIN only: it rewrites a single-player arm that this copy
        # never reaches, which the other two copies do.
        out.append(FileEdit("split_team_orders", r"/COMMON_SS\.LIN$", "",
                            {"enable": True},
                            "split screen: the team order icon and wheel"))
    return out


def build_pnach(v: dict) -> list:
    out = []
    if v.get("wave_enable") and v.get("wave_mapwide"):
        out.append(WordEdit(CAVE_HIJACK[0], CAVE_HIJACK[1],
                            STOCK[CAVE_HIJACK[0]],
                            "map-wide spawn points: hijack the point picker"))
        out += [WordEdit(va, word, 0, "map-wide spawn points: cave")
                for va, word in CAVE_WORDS]
    if v.get("claymore_prox", "off") != "off":
        # A separate cave, in the one clean zero run in the overlay. It does
        # not touch the map-wide cave's words or its hijack.
        out.append(WordEdit(rseclaymore.HIJACK[0], rseclaymore.HIJACK[1],
                            STOCK[rseclaymore.HIJACK[0]],
                            "claymore proximity: hook the actor tick"))
        # The blast's own cone lives in the level containers as a float
        # (rsegadget's "cone"), and the cave's trigger arc is COMPUTED from
        # it rather than pinned, so the two cannot disagree. No card changes
        # it today, so the shipped value is right; if one is ever added, read
        # it off the disc and pass it here.
        front = bool(v.get("claymore_arc", True))
        out += [WordEdit(va, word, 0, "claymore proximity: cave")
                for va, word in rseclaymore.words(
                    v["claymore_prox"], front_arc=front,
                    cone_cos=rsegadget.STOCK["cone"])]
    _terr = str(v.get("decal_terrain") or rsedecal.TERRAIN_DEFAULT)
    if _terr != "stock":
        out += [WordEdit(va, new, stock,
                         "marks on open ground: %s" % _terr)
                # terrain_words yields (va, STOCK, NEW) -- unpacking it as
                # (va, new, stock) wrote the stock value back and made the
                # whole option a silent no-op.
                for va, stock, new in rsedecal.terrain_words(_terr)]
    if int(v.get("blast_decals", 0) or 0) > 0:
        # A third cave, well clear of the other two: the map-wide picker sits
        # in the overlay and the claymore one at 0x000F0000..0x000F0800.
        out.append(WordEdit(rsedecal.HIJACK_AT, rsedecal.HIJACK,
                            STOCK[rsedecal.HIJACK_AT],
                            "shrapnel marks: hook the explosion epilogue"))
        _stag = bool(v.get("blast_stagger"))
        out += [WordEdit(va, word, 0, "shrapnel marks: cave")
                for va, word in rsedecal.words(int(v["blast_decals"]), _stag)]
        if _stag:
            # A second hook, in UGameEngine::Tick rather than ULevel::Tick --
            # that one runs twice a frame, which is fine for the claymore's
            # proximity check and wrong for anything that counts frames.
            out.append(WordEdit(rsedecal.STAGGER_HOOK,
                                rsedecal.STAGGER_HOOK_JUMP,
                                STOCK[rsedecal.STAGGER_HOOK],
                                "shrapnel marks: hook the frame tick"))
            # The queue's own RAM is deliberately absent: a pnach row rewrites
            # its address every frame, which would reset the queue forever.
            out += [WordEdit(va, word, 0, "shrapnel marks: stagger")
                    for va, word in rsedecal.stagger_words()]
    # Blood on the surfaces behind whoever you shoot. A fourth cave, clear of
    # the other three and of the puff pool. Nothing here is runtime state --
    # the roll is hashed from the wound and the surface point -- so unlike the
    # stagger queue every word of it belongs in the cheat file.
    if v.get("blood_splats"):
        out.append(WordEdit(rsedecal.BLOOD_HOOK, rsedecal.BLOOD_HOOK_JUMP,
                            STOCK[rsedecal.BLOOD_HOOK],
                            "blood marks: hook the pawn-hit branch"))
        _breach = float(v.get("blood_reach", rsedecal.BLOOD_REACH_DEFAULT)
                        or rsedecal.BLOOD_REACH_DEFAULT)
        out += [WordEdit(va, word, 0, "blood marks: cave")
                for va, word in rsedecal.blood_words(_breach)]
    # Slow time when the last enemy goes down. The lever is one float --
    # LevelInfo.TimeDilation at +0x458, which multiplies into m_dT at +0x47C
    # and is clamped to [0.0005, 0.4] -- and the trigger is the game's own
    # count of living terrorists. NOT hooked in ULevel::Tick, which runs up
    # to THREE times a frame; this rides once-per-frame in UGameEngine::Tick.
    # The sound does not slow with it, which is measured, not feared. See
    # rseslomo.
    if v.get("slomo"):
        out += [WordEdit(va, word, 0, "slow motion: %s, %s"
                         % (v.get("slomo_strength", rseslomo.PRESET_DEFAULT),
                            v.get("slomo_when", rseslomo.THRESHOLD_DEFAULT)))
                for va, word in rseslomo.words(
                    str(v.get("slomo_strength") or rseslomo.PRESET_DEFAULT),
                    str(v.get("slomo_when") or rseslomo.THRESHOLD_DEFAULT))]
    # Teammates carry the loadout the player actually picked. The cave still
    # hooks the `jr $ra` of execGetMissionDescription (0x00273200); all twelve
    # authored AI equipment blocks are written, because CreateTeamMember picks
    # among the plain, silenced and terrorist-hunt variants at runtime. The
    # guard is a five-word once-per-level identity costing 23 instructions on
    # a call that does nothing, and 0x000F67F8 counts every entry.
    #
    # HOT-PAGE FIX 2026-09-27. THERE IS DELIBERATELY NO ROW FOR HOOK_AT. A
    # pnach row is re-applied every vsync, and page 0x00273000 holds eleven
    # UnrealScript natives -- the hottest code there is during a level load --
    # so rewriting that one word sixty times a second made the emulator throw
    # away and rebuild the whole page continuously, and the load stalled with
    # the audio breaking up. Proven by bisect IN PLAY: the 254 cave words alone
    # load clean, the hook word alone stalls it. The hook word is now installed
    # by the game, once per level load, from the ten-word installer at
    # 0x000F6900 hooked into UGameEngine::LoadMap at 0x002F8CE4 -- a page whose
    # every instruction belongs to LoadMap and to nothing else. See rsemirror.
    if v.get("mirror_loadout"):
        out.append(WordEdit(rsemirror.ARM_AT, rsemirror.ARM_NEW,
                            STOCK[rsemirror.ARM_AT],
                            "loadout mirror: install the hook once per level"))
        out += [WordEdit(va, word, 0, "loadout mirror: installer")
                for va, word in rsemirror.arm_words()]
        _mscope = str(v.get("mirror_scope") or rsemirror.SCOPE_DEFAULT)
        _mlaunch = str(v.get("mirror_launcher") or rsemirror.LAUNCHER_DEFAULT)
        out += [WordEdit(va, word, 0,
                         "loadout mirror: %s, %s" % (_mscope, _mlaunch))
                for va, word in rsemirror.words(_mscope, _mlaunch)]
    # How hard the squad shoots. Two plain `addiu` immediates -- no cave, no
    # hook, no delay slot. The terrorist fire loop is UnrealScript and the
    # Rainbow one is native, so this does not port their code; it widens the
    # trigger-hold envelope the native tick rolls from, taking the squad's
    # duty cycle from 35% towards the terrorists' 77%. See rseaifire for why
    # a single long magazine dump is NOT reachable and why the 0.5 s attack
    # cycle is a hard ceiling.
    _fire = str(v.get("ai_trigger_hold") or rseaifire.PRESET_DEFAULT)
    if _fire != rseaifire.PRESET_DEFAULT:
        out += [WordEdit(va, word, STOCK[va],
                         "trigger discipline: %s" % _fire)
                for va, word in rseaifire.words(_fire)]
    # Tracer colour from the cartridge. The game already picks a colour PAIR
    # per tracer, out of R6GameplaySettings by the record's team flag -- but
    # all four slots hold the same 0x00FFFF80, so every gun fires the same
    # yellow. The four picks are repointed at two spare fields in the tracer
    # record itself, and the cave fills them when the record is created.
    #
    # Calibre is not a field anywhere -- the HUD's "(5.56MM)" is a
    # localisation string with no numeric key. What IS per-cartridge is
    # `m_pEmptyShells` at weapon +0x544, a class pointer to one of eighteen
    # R6Shell* classes, whose FName index is load-stable where the weapon
    # class names are not. See rsetracer.
    if v.get("tracer_calibre"):
        _pal = str(v.get("tracer_palette", rsetracer.PALETTE_DEFAULT)
                   or rsetracer.PALETTE_DEFAULT)
        _thin = int(v.get("tracer_every", rsetracer.THIN_DEFAULT)
                    or rsetracer.THIN_DEFAULT)
        for _va, _stock, _new in rsetracer.COLOUR_WORDS:
            out.append(WordEdit(_va, _new, _stock,
                                "tracers: colour comes from the record"))
        out += [WordEdit(va, word, 0, "tracers: %s" % _pal)
                for va, word in rsetracer.words(palette=_pal, thin=_thin)]
    # Whose tracers get drawn at all. Separate from the colour: the
    # record is created either way, and these two words decide whether
    # the renderer is allowed to show it. Independent of tracer_calibre.
    # Burst fire has no gunshot sample on this build. One word points the
    # burst handler at the single-shot one, which every weapon has. The
    # AI never reach it -- they are always full auto -- so this is for
    # the player's own weapon. See rseburstsnd.
    if v.get("burst_fire_sound"):
        out += [WordEdit(va, new, stock,
                         "burst fire: use the single-shot gunshot")
                for va, new, stock in rseburstsnd.words(True)]
    _tvis = str(v.get("tracer_visible") or rsetracer.VISIBLE_DEFAULT)
    if _tvis != rsetracer.VISIBLE_DEFAULT:
        out += [WordEdit(va, new, stock, "tracers visible: %s" % _tvis)
                for va, new, stock in rsetracer.visible_words(_tvis)]
    # Independent of the marks: the engine keeps ONE timer for impact dust and
    # skips any burst inside half a second of the last one, anywhere. The
    # sound is played upstream of that test, which is why several impacts are
    # audible and one is visible. A cheat row rather than a disc word because
    # it lives in the overlay and is a single branch.
    #
    # It is MUTUALLY EXCLUSIVE with the puff pool below, and not merely
    # redundant with it: with the limit gone, every shot re-fires the game's
    # ONE shared actor for that material, and re-firing a busy emitter runs
    # it through Init -> Reset, which zeroes the live particles. That is the
    # "puff stops and jumps to the newest hit" the pool exists to cure, so
    # leaving this on alongside the pool reintroduces it. `requires` keeps
    # the card greyed out, and this guard is the belt to that braces.
    if v.get("blast_puffs") and not v.get("impact_puffs"):
        out.append(WordEdit(rsedecal.BURST_GATE, rsedecal.BURST_GATE_OFF,
                            rsedecal.BURST_GATE_STOCK,
                            "impact dust: every impact raises its own"))
    # A private ring of emitter actors, so consecutive impacts stop sharing
    # one. Hooked at the last instruction before the impact visual tests the
    # material for a spark class, where the pooled effect actor's Location
    # and Rotation are already written -- so one word serves every bullet,
    # ricochet, exit wound and material, AND the shrapnel cave's own
    # impacts, which the placer-side hooks would have missed. See rsepuffs.
    if v.get("impact_puffs"):
        _pn = int(v.get("impact_puff_count", rsepuffs.COUNT_DEFAULT)
                  or rsepuffs.COUNT_DEFAULT)
        # A puff lives for its SPAWN WINDOW, not its declared lifetime: the
        # engine retires it the moment the last sprite is out, because
        # RespawnDeadParticles is false. At the shipped MaxParticles of 3
        # that is 3/60 = 0.05 s, which is why no ring size could ever show
        # two at once. See rsepuffs.
        _pl = int(v.get("impact_puff_length", rsepuffs.MAXPART_DEFAULT)
                  or rsepuffs.MAXPART_DEFAULT)
        out += [WordEdit(va, word, 0,
                         "impact dust: %d puffs, %.2f s each"
                         % (_pn, rsepuffs.visible_seconds(_pl)))
                for va, word in rsepuffs.words(_pn, particles=_pl)]
    # Molotovs and flashbangs for the terrorists. 62 words at
    # 0x000F6C00..0x000F6CF8 plus two dial words at 0x000F6FE0, clear of
    # every other cave and of the loadout mirror's installer at 0x000F6900.
    #
    # The hook is at 0x003C9374, where PickGrenadeClass's two paths
    # converge and $s0 still holds the raw UClass* -- so the substitution
    # is ONE register store and the game builds the name string itself
    # afterwards. That is why this route has none of the padding problem
    # that withdrew the data edit: no string in any package changes length.
    #
    # The hook IS a plain pnach row, unlike the loadout mirror's, because
    # page 0x003C9000 holds nine ORDINARY functions, none in the native
    # dispatch table, eight with exactly one static caller each. The
    # mirror's 0x00273000 held nine natives reached only by jalr from the
    # bytecode interpreter -- the hottest code in a level load.
    #
    # words() yields TWO-tuples, (va, word). The hook is delivered
    # separately so it cannot be mistaken for a cave word.
    _tgren = str(v.get("terrorist_grenades") or rsemolotov.PRESET_DEFAULT)
    if _tgren != "off":
        out.append(WordEdit(rsemolotov.HOOK_AT, rsemolotov.HOOK_NEW,
                            STOCK[rsemolotov.HOOK_AT],
                            "terrorist grenades: hook the grenade picker"))
        out += [WordEdit(va, word, 0, "terrorist grenades: %s" % _tgren)
                for va, word in rsemolotov.words(_tgren)]
    # The two split-screen HUD caves used to be emitted here. They are
    # disc words now, living in the scope draw's dead path -- see
    # rsedeadpath for why a cheat file could not hold them.
    return out


def combination_warnings(v: dict) -> list:
    """Settings that are fine alone and run the console out of memory together.

    The PS2 has 32 MB and no way to ask for more. Each of these on its own is
    survivable; the combination is what fills it.

    It bites hardest on RESTART. The report this was written from is a freeze
    in the mission-fail menu on the third or fourth retry from insertion, not
    during play -- so what runs the console out is the teardown-and-reload
    path, with each attempt leaving more behind than the last. That is also
    what makes it so hard to attribute: nothing goes wrong while you are
    alive, and the switch that caused it was set several sessions ago.
    """
    out = []

    # The explosion decal ring wraps silently at its size, so a blast that
    # asks for more marks than the ring holds overwrites its own earlier ones
    # in the same frame. Nothing fails and nothing is logged -- the marks
    # simply are not there, which is indistinguishable from the feature not
    # working. Said whenever the numbers disagree, not only in combination.
    _marks = int(v.get("blast_decals", 0) or 0)
    _ring = int(v.get("grenade_decals", 8) or 8)
    if _marks > _ring:
        out.append(
            "Shrapnel marks are set to %d per explosion but only %d "
            "explosion marks are kept on screen, so each blast overwrites "
            "its own marks as it places them and you would see %d. Raise "
            "\"Explosion marks kept on screen\" to at least %d -- two or "
            "three times that if you want one blast's marks to survive the "
            "next one." % (_marks, _ring, _ring, _marks))
    elif _marks and _ring < 2 * _marks:
        out.append(
            "Shrapnel marks (%d) fit the explosion ring (%d) exactly once, "
            "so the next blast erases the last one's marks completely. That "
            "works; %d or more would let a couple of blasts stay on the "
            "walls together." % (_marks, _ring, 2 * _marks))

    # Said every time wave mode is on, not just in combination.
    #
    # Turning the DEFAULT off does nothing for anyone who already has it
    # stored: a saved profile carries the old value and goes on applying it,
    # which is exactly how this was missed. The reporter's profile still said
    # True hours after the default changed, so every apply they made through
    # the window carried wave mode -- and that sent one investigation after
    # an option that turned out to be innocent. A default is advice to new
    # discs; a warning is the only thing that reaches an old profile.
    # The spawn runaway, measured on Shipyard 2026-09-25. R6DZonePoint's
    # SpawnOne credits the new pawn to the POINT's owner zone (point +0x480,
    # m_pWave) -- NOT to the zone that asked. 14 of Shipyard's 18 points have
    # a NULL owner, so a map-wide pick builds and places the enemy fine and
    # credits nobody. The requesting zone's live list and m_iNbSpawned never
    # move, it stays under its trigger, and it releases again next frame,
    # forever. The release size only scales the waste; the picker is the bug.
    if v.get("wave_enable") and v.get("wave_mapwide"):
        out.append(
            "\"Spawn across the whole map\" carries its fix in the CHEAT "
            "FILE, not on the disc, so save a fresh one from this window "
            "after applying. An older cheat file sends each wave to spawn "
            "points whose enemies are credited to nobody, which leaves the "
            "zone releasing another batch every frame -- measured on "
            "Shipyard as 2,492 enemies in 132 seconds and about two frames a "
            "second.")

    if v.get("wave_enable") and not v.get("wave_mapwide"):
        out.append(
            "Wave mode is on with the map-wide spawn points off, so every "
            "wave asks one deployment zone for all its spawn points. That is "
            "the combination that hung Terrorist Hunt on Parade. With the "
            "map-wide option on -- and its cheat file saved into the PCSX2 "
            "you actually launch -- split-screen Terrorist Hunt and practice "
            "both load (Shipyard, 2026-09-25). Turn the map-wide option on, "
            "or lower how much each zone owes.")

    feeding = (v.get("wave_enable")
               and v.get("wave_gate", "stock") != "stock")
    forever = v.get("bodies", "stock") == "never"
    owed = int(v.get("wave_total", 0) or 0)
    trigger = int(v.get("wave_trigger", 99) or 99)
    ring = int(v.get("decal_ring", 32) or 32)

    if forever and feeding:
        out.append(
            "Bodies never despawning AND every deployment zone feeding is the "
            "combination that fills the console's 32 MB: the level keeps "
            "spawning and nothing is ever removed. It shows up on RESTART "
            "rather than during play -- retry a mission three or four times "
            "from insertion and it can freeze on the fail screen. Set bodies "
            "back to a timer, or let only the player's zone feed.")
    if forever and ring > 64:
        out.append(
            "Bodies never despawning with a decal ring of %d holds every "
            "corpse and %dx the stock number of bullet holes at once. Either "
            "alone is fine; together they are a lot of memory." % (ring, ring // 32))
    # Only worth saying alongside something that makes the population
    # unbounded: continuous spawning on its own is what this page is FOR, and
    # warning about the defaults on every plan would be noise.
    if forever and feeding and owed >= 20 and trigger <= 3:
        out.append(
            "%d enemies owed per zone with a refill whenever %d or fewer are "
            "alive means a zone never stops producing. With every zone feeding "
            "at once that is a continuous spawn for the whole mission."
            % (owed, trigger))
    return out


PROFILE = GameProfile(
    id="r6_3_slus20883",
    title="Tom Clancy's Rainbow Six 3",
    short="Rainbow Six 3",
    serial="SLUS-20883",
    boot="SLUS_208.83",
    volume_hint="SLUS_20883",
    pcsx2_crc="21CC1EC3",
    # Other pressings this tool has been shown. A disc CRC is an XOR over the
    # BOOT executable, so a later manufacturing run can read a different one with
    # SP.SOZ -- the only file any of these options patch -- untouched. Adding a
    # CRC here is only ever a claim about WHICH GAME the disc is; whether its
    # addresses are usable is decided by `sig_table` and the overlay hash, not
    # by this list.
    also_crcs=(),
    sig_table=r6_3_slus20883_sig.SIGS,
    stock_words=STOCK,
    overlays=[SP],
    settings=_settings(),
    build_edits=build_edits,
    build_pnach=build_pnach,
    build_data=build_data,
    archive_pattern=r"/VOKES\d\.IMG$",
    notes=WAVE_MAPS,
    combination_warnings=combination_warnings,
    mission_art_for=mission_art_for,
    ui_art={
        "archive": "iso",
        "fbz": [r"/NTSC_CD/LE/SC\.FBZ$", r"/NTSC_CD/LE/LANG_BG\.FBZ$",
                r"/NTSC_CD/LE/PAD_ENG\.FBZ$", r"/NTSC_CD/LE/MCARD/.*\.FBZ$"],
    },
)

"""Shrapnel marks: explosions pit the surfaces around them.

Three things had to be true at once, and none of them was obvious.

1. THE EXPLOSION DECAL RING IS BORN FLOOR-ONLY. `R6DecalGroup::Init` sets
   `m_bProjectOnlyOnFloor` on all eight pooled grenade decals, and
   `R6DecalManager::AddDecal` never writes the projector bools, so a decal
   placed through it marks floors and NOTHING else. One word clears it --
   the `daddiu $a1,$zero,4` at 0x00378E44, whose 4 is the bit-2 value for
   decal+0x37D. The bool bitfield is one DWORD at decal+0x37C holding
   Projector's sixteen bools in declaration order, bit i = bool i:
   bProjectBSP 0, bProjectTerrain 1, bProjectStaticMesh 2,
   bProjectParticles 3, bProjectActor 4, bLevelStatic 5, bClipBSP 6,
   m_bClipStaticMesh 7, m_bRelative 8, m_bProjectTransparent 9,
   m_bProjectOnlyOnFloor 10, m_bIsGrenadeDecalProjector 11,
   bProjectOnUnlit 12, bGradient 13, bProjectOnAlpha 14,
   bProjectOnParallelBSP 15. Read off AProjector::Attach, which gates the
   BSP gather on bit 0, the terrain AABB gather on bit 1, the static-mesh
   sweep on bit 2, the frustum clip of a BSP poly on bit 6, the
   transparent-material reject on bit 9, the "plane normal Z < 0.5 ->
   reject" test on bit 10 and the GradientTexture path on bit 13.

2. THE SHIPPED GRENADE DECAL PATH IS DEAD. `m_GrenadeDecalClass` is None in
   all ten grenade-derived class defaults and on every live instance, so
   `R6Grenade.Explode` never spawns the decal actor and the placer at the end
   of the chain never runs. Raising the ring size alone changes nothing --
   but it also means the whole ring is free, with nothing competing for it.

3. SO A CAVE PLACES THE MARKS, hooked into the explosion native's single
   epilogue, calling `AddDecal` directly and skipping the dead script path.

How a mark gets where it goes
-----------------------------

Every mark TRACES outward from the blast along its own scatter ray, as far as
the blast radius. If it hits nothing it is skipped -- no projector, no
allocation. If it hits, the mark is placed just off the surface it struck,
facing the way the fragment arrived.

The first version skipped the trace and hung each projector in mid-air on its
ray. That is what produced long black smears instead of marks: a projector
that never meets a surface squarely stretches its texture across whatever it
does reach. Tracing is also what makes the count honest -- a grenade in the
open leaves a few marks, one in a corridor leaves all of them.

The texture is the game's own BULLET-HOLE set, not the blast's smoke sprite,
and it is THE SET FOR WHAT THE FRAGMENT HIT. The level builds a 22-slot impact
cache at load: `0x006DD7A0[i]` the `R6*Effect` class keys, `0x006DD6C0[i]` one
live `R6WallHit`-derived instance each, count at `0x0065526C`. Each instance
carries `m_DecalTexture`, 3 to 8 variants -- brick holes on brick, hard-metal
holes on metal, glass on glass, and nothing at all on water, dirt, snow or
blood, where the game leaves no bullet hole either.

A mark finds its slot the way the game's own impact does. `AActor::Trace`
already hands the cave the `UMaterial` it hit, in the `$t3` out-parameter, and
`Material.m_pHitEffect` at +0x50 is a `class<R6WallHit>`; the entry point at
`0x003F08C0` matches that class against the key table by **FName index**, not
by pointer, and uses the slot it lands on. The cave now does the same, per
mark, and takes `m_DecalTexture` off that slot's instance.

Until this was done the cave picked ONE array per blast -- the first slot with
a usable one, measured as slot 0, `R6BrickEffect` -- so every shrapnel mark in
the game was a brick hole whatever it struck, while the impact sound and dust
beside it were already correct.

A mark the ENGINE could not name falls back to `R6GenericEffect`
(GenericHole001..003), found by name, not by index: the cave carries the text
`r6genericeffect` in its own frame and walks the key table comparing each key
class's FName TEXT through `FName::Names` at 0x00686060, case-folded. If that
slot is unusable in a level it falls back once more to the first slot with a
non-empty `m_DecalTexture`; if there is none, the mark is skipped.

A mark the MATERIAL ITSELF disowns still skips, and that distinction is the
whole of the fix's safety. `m_pHitEffect` being None is how the sky presents:
71 of alpines_b's 234 BSP surfaces are `Package0.Backdrop`, PF_FakeBackdrop,
`m_pHitEffect` None -- and with TRACE_MULT 3.0 a fragment's ray reaches 1500
units, so outdoors it gets there. Zone portals and `Color.Black` are the same.
So a NULL Material, or a registered slot with an empty array, takes the
generic hole; a material that names no hit effect at all, or names one this
level never registered, is skipped as before.

That fallback is not cosmetic -- without it a grenade on open ground leaves no
marks on the ground at all, which is what the first play test showed. Two
independent reasons, both measured:

* THE GROUND IS OFTEN TERRAIN, and terrain carries no material. `ULevel::
  MultiLineCheck` (vtable +0xDC, 0x00213250) pre-zeroes `FCheckResult+0x3C`
  for all 128 of its stack results at 0x00213330 and then delegates: BSP to
  `UModel::LineCheck` (0x0027F0D0), which fills Material from
  `Surfs[Nodes[Item].iSurf].Material` at 0x0027F570 whenever TRACE_Material
  (0x1000) is set -- the cave's trace does set it; actors to
  `ActorLineCheck` (0x0037C7F0), which reaches each actor's primitive through
  `AActor::GetPrimitive` (vtable +0xC0) and its `LineCheck` (primitive vtable
  +0x70), and `UStaticMesh::LineCheck` (0x0036CD70) fills Material
  unconditionally from `GetSkin(Owner, tri.MaterialIndex)` at 0x0036D678 and
  0x0036DE60; and terrain to 0x002CF5A0, which does not reference offset
  0x3C anywhere in its 577 instructions. So a terrain hit reports
  Material == NULL.
* AND SNOW AND DIRT SHIP NO HOLE. 8 of the 22 slots have an empty
  `m_DecalTexture` -- blood, chain, DIRT, water, meat, metal fence, plush and
  SNOW. That is deliberate and correct for a BULLET, which leaves no hole in
  loose ground. An EXPLOSION scars both, so the cave wants a mark where the
  bullet path wants none. The bullet path is untouched.

The trace also STARTS above the epicentre now, by `TRACE_LIFT_UNITS`. A
grenade at rest sits a few units off the floor, so every downward ray used to
hit inside the cave's own 20-unit degenerate-trace guard and be discarded
while the upward half hit nothing: 9.6 of 48 rays survived, half of them
within 0.38 m of the crater. Lifting only the START -- the scatter origin and
the epicentre the guard measures from are unchanged -- gives 23.2 of 48 at a
0.80 m median radius. One up-probe per blast keeps the lifted start out of a
ceiling: if anything is overhead within the lift, the lift shrinks to the
clearance less `TRACE_LIFT_MARGIN` and floors at zero, so under a low
overhang it degrades to the old behaviour instead of stamping marks overhead.

Fixed global bases with per-load pointers inside, so nothing is hard-coded --
which matters, because UObject addresses move every load.

What it reads off the detonating actor: only `Actor::Level`
-----------------------------------------------------------

The hooked native is `Engine.Actor.ExplosionDamage`, declared on **Actor**,
and `R6ExplodingBarel.Explode` calls it too. On a barrel the grenade field
offsets mean something else entirely, in bounds and silently wrong. So the
radius comes off the native's own `fDamageRange` parameter, still on the
stack at the epilogue and correct for every caller, and the only field read
off the actor is `Actor::Level` (+0x104), which every actor has.

The scatter is trig-free: the game ships a 16384-entry sine table at
`0x0068A8F0` (in the MAIN ELF, not the overlay). `z` is sampled directly
rather than the pitch angle, because a uniform pitch is not uniform on a
sphere -- measured, it put 41% of the marks in 20% of the area. The seed is
hashed from the epicentre's own float bits, so the same blast in the same
place always scatters the same way and no state is kept anywhere.

TERRAIN, AND WHY A GRENADE COSTS SO MUCH ON ALPINE VILLAGE
----------------------------------------------------------

`AProjector::Attach` is at **0x00257C90**, 497 instructions, and it clocks six
of the game's own named stat slots -- `AttachProjector`,
`  AttachProjectorCalcMatrix`, `  AttachProjectorMalloc`,
`  AttachProjectorTerrain`, `  AttachProjectorBSP`,
`  AttachProjectorStaticMesh` -- whose literals are at 0x005E64C0..0x005E6512.
So the function is named by the binary, not guessed.

Bit 1 of `decal+0x37C` gates the terrain gather at 0x00257DA4::

    0x00257D98  lbu    $v0, 0x37C($s5)
    0x00257D9C  dsll32 $v0, $v0, 30        ; isolate bit 31-30 = bit 1
    0x00257DA0  dsrl32 $v0, $v0, 31
    0x00257DA4  beqz   $v0, 0x00257F44     ; clear -> skip 0x00257DA8..0x00257F40

**The gather has no hierarchical rejection.** It is a three-level nest --
`XLevel+0x7B00` zones, `AZoneInfo+0x39C` TerrainInfos, `ATerrainInfo+0x13B4`
sectors -- and each bound is a plain `TArray.Num`. The AABB test is at the
*leaf*: every sector of every TerrainInfo of every listed zone is loaded and
its `FBox` at `UTerrainSector+0x50` compared against the projector's box at
`this+0x480`/`+0x490`. A rejected sector costs 22 instructions; an accepted one
costs 37 plus the 98-instruction `UTerrainSector::AttachProjector`
(0x002D8C00), which appends an `FTerrainSectorProjectorInfo` to that sector's
own list. **It is O(total sectors), unconditionally.**

Sector counts are `ceil(TerrainMap.USize/8) * ceil(TerrainMap.VSize/8)`, from
the rebuild at 0x002D5B68. Counted from the 82 decompressed level packages in
`scratch-2026-09-23\\bomb\\levels\\`:

===========================  ========  ===========  =============
level                        ZoneInfo  TerrainInfo  TerrainSector
===========================  ========  ===========  =============
ALPINES_A (Alpine Village)         33            2             80
SANDSTORM_MP_C                      1            1             64
TRAINING_SHOOTINGOFF               12            1             64
every other level (76 of 82)        -            0              0
===========================  ========  ===========  =============

**76 of the 82 level blobs ship no terrain at all**, including ALPINES_B and
every other campaign map, so on those maps the whole terrain branch costs 5
instructions and cannot be the cause of anything. Alpine Village is the one
campaign map with terrain. And the figure of "320 sectors" in the plan is wrong
by four: it is **80** -- 64 under TerrainInfo0 (8x8) and 16 under TerrainInfo1
(4x4), cross-checked against a raw `b"TerrainSector"` count of 65 name hits.

WHAT THAT COSTS, HONESTLY
-------------------------

On Alpine Village, one decal placement with every sector rejected is
`12 + 1 zone x 17 + 2 info x 16 + 80 sectors x 22 = 1,821` instructions, plus
135 for each sector the mark actually overlaps. BSP (bit 0) costs about 1,093
instructions on EVERY call whatever the map. So terrain is roughly 60% of a
placement on Alpine Village and nothing anywhere else -- **it is not the
dominant cost of `Attach` in general**, and twelve shrapnel marks' worth of
gather is only about 22,000 instructions, which is well under a millisecond and
**cannot by itself explain 2 fps**.

What the gather also does is *attach* the mark to every terrain sector it
overlaps, and the terrain renderer then draws that mark again for each of those
sectors, every frame, for the mark's whole life. That recurring per-frame cost
is the plausible explanation for a sustained drop, and it is the part that is
**NOT measured here**. Both disappear when bit 1 is clear, so the fix is the
same either way -- but the magnitude is reasoned, not counted.

WHERE THE BOOLS ARE ACTUALLY SET
--------------------------------

Not in a table, and not per placement. `R6DecalGroup::Init` (0x00378A60) runs
once per level load, loops over the group's whole ring, and for each spawned
`Engine.R6Decal` runs the arm of a five-way switch on the group's `+0x370`
type byte::

    0x00378B44  beq $v1,$v0,0x00378DFC   type 4  grenade / shrapnel
    0x00378B4C  beq $v1,$t5,0x00378D74   type 3  BloodBaths
    0x00378B54  beq $v1,$v0,0x00378CB8   type 2  BloodSplats
    0x00378B60  beq $v1,$v0,0x00378C04   type 1  bullet holes
    0x00378B68  beqz $v1,0x00378B78      type 0

Each arm is a chain of `lbu / and mask / or value / sb` against `+0x37C` and
`+0x37D`. **There is no `li 0xA1C7` anywhere** -- the word is the `R6Decal`
class default (from the `.u` package) with per-type bits read-modify-written
over it. So "clear bit 1" means widening an existing AND mask whose paired OR
value does not put the bit back, and the mask to widen is the one belonging to
the **last** write to byte 0 in that arm, because that write is immune to
whatever the earlier ones did.

WHAT STOCK ACTUALLY DOES, AND WHAT WE DID TO IT
-----------------------------------------------

=====  ==============  ==============  ==================================
type   stock           + BRANCH_WORDS  what it is
=====  ==============  ==============  ==================================
1      0xA3C7 bit1=1   0xA3C7 bit1=1   bullet holes -- terrain ON in stock
2      0xA1C7 bit1=1   0xA1C7 bit1=1   BloodSplats -- ring never fed in stock
4      0x8C85 bit1=0   0xA3C7 bit1=1   grenade -- terrain OFF in stock
=====  ==============  ==============  ==================================

**The M203 regression is ours.** Type 4 clears bit 1 in stock, explicitly, at
0x00378E14/0x00378E2C/0x00378E6C. `BRANCH_WORDS` turns 0x00378E14 from
`andi $a0,$zero,1` (= 0) into `ori $a0,$zero,1` (= 1), and `$a0` feeds bit 1,
bit 6 and bit 13 through three `sll`s -- so the patch that gave explosion marks
the bullet-hole look also switched their terrain projection on. `INCIDENCE_WORDS`
then removes the dedicated bit-1 clear at 0x00378E6C entirely (it becomes
`sw $t5,0x384($s3)`), which is harmless on its own because it had already
widened 0x00378E20's mask to `~0x42`, but leaves nothing to undo the `or`.

Blood is different: bit 1 is the class default and the arm never touches it --
but the type-2 ring is **fed by nothing in stock**, so no type-2 decal has ever
been placed in an unmodified game and there is no stock behaviour to preserve.

Bullet holes are the one group where terrain projection is behaviour the player
has always seen, which is why the default leaves them alone.

Where it lives
--------------

The cave rides in the PCSX2 cheat file, like the claymore one, because a cave
baked into the overlay does not survive a level load. It sits at `0x000F1000`,
clear of the claymore cave's `0x000F0000..0x000F0800`. The two disc words are
ordinary overlay edits and go into the ISO.

Blood splatter on surfaces
--------------------------

The other half of this module: when a bullet damages a person, put a blood
mark on whatever is behind them.

Everything needed was already on the disc and correctly configured. The one
thing missing was a caller.

* `R6DecalManager::AddDecal` is native 2900 and takes the decal type as a
  plain argument, so nothing has to be repointed. Its REGISTER contract is
  not the shape of its script argument list, and is read straight off the
  native's own script thunk at 0x00379738: $a0 manager, $a1 &position,
  $a2 &rotator, $a3 the texture, $t0 the type, $t1 iFov, $f12 duration,
  $f13 start time, $f14 max trace distance. A null texture makes the placer
  return without taking a decal, so $a3 is mandatory.
* `DECAL_BloodSplats` is type 2 and resolves to R6DecalManager+0x378. Its
  ring is built on every level load and fed by NOTHING: measured across six
  live EE images, 16 non-null decals, the group's enable bit set, projector
  bools 0xA1C7 -- BSP, terrain and static mesh, clipped, relative, and NOT
  floor-only -- and minProjectAngle already the useful -15.0, with
  ProjTexture NULL on all sixteen. So no disc word is needed to make it
  look right and nothing competes for the slots.
* `DECAL_BloodBaths` (type 3) was rejected. Its minProjectAngle is the
  useless 90.0 -- sin(90) is sine's maximum, the same trap INCIDENCE_WORDS
  above exists to fix -- it carries neither bClipBSP nor m_bClipStaticMesh
  nor m_bRelative, the placer special-cases it at 0x00378488, and it is the
  ring the game's own corpse pool uses.
* The bullet-hole distance/LOD gate inside AddDecal (0x003797E0..0x00379908)
  is guarded on type == 1, so a blood decal is never discarded for being far
  from the camera.

WALLS AND FLOORS ARE THE SAME CODE PATH. The ring is not floor-restricted,
so a level shot marks the wall behind the victim and a downward shot marks
the ground. There is no second pass for floors. When nothing at all is
within reach along the shot -- someone shot in mid-air, or across open
ground -- the cave looks straight DOWN instead, 250 units, which is the
number the game's own corpse pool uses in R6Pawn.R6DeadEndedMoving.

WHERE IT HOOKS. One word: 0x003F1EF0, the `b 0x003F2560` that ends the PAWN
branch of the bullet trace native, becomes `j BLOOD_CAVE`. The jump's delay
slot (0x003F1EF4 `cvt.s.w $f21,$f0`) is not a branch and still runs, so
nothing is displaced and no word has to be replayed. The resume point reads
only $f21 and $s2.

Unlike the shrapnel cave above, that hook is MID-function, so this cave may
not touch $s0-$s7, $fp, $gp or $f20-$f31 -- and neither may anything it
calls. AActor::Trace, FVector::Rotation and AddDecal were each checked for
unsaved writes to those and all three are clean.

The two friendly-fire tests above the hook bail to 0x003F2584 instead of
reaching it, so a shot friendly fire rejects leaves no blood -- which is the
behaviour co-op wants and costs nothing to get.

NO RUNTIME STATE. Every word of this cave is safe in the cheat file. The
roll angle is hashed from the wound and the surface point, so the same shot
in the same place always lands the same way and nothing is remembered --
unlike the stagger queue above, whose RAM must stay out of the pnach.

NOTHING IS HARD-CODED. The manager comes off the weapon's own
Actor::Level +0x104 -> +0x548. The texture comes from *(0x00655DE4), the
static UClass* slot for the native class R6BloodSplat, then +0x148 Defaults
-> +0x370 m_BloodSplatTexture = Texture'Inventory_t.BloodSplats.BloodSplat'.
That VA is the only one, out of five live EE images, that holds the class
pointer in all of them. Every dereference is null- and alignment-checked and
a null anywhere just means no blood this shot.

Not established
~~~~~~~~~~~~~~~
* How it looks. Nothing here has been played.
* The skybox. The cave cannot do the PF_FakeBackdrop test the shipped bullet
  path does at 0x003F1AD8, because AActor::Trace drops FCheckResult.Item.
  The only thing keeping blood off a sky poly is that the ray is short, which
  is why "How far blood carries" exists and why its default is 3 metres.
* Explosions leave none: they go through a different native entirely.

Not established
---------------

* How it looks. Bullet-hole textures on traced surfaces is the reasoning; a
  screenshot is the proof.
* GS fill rate with a dozen extra projectors in one frame, and the cost of a
  dozen traces, which is arithmetic but not measured in play.
"""

from __future__ import annotations

import struct


class DecalError(Exception):
    pass


# --------------------------------------------------------------- disc words

#: R6DecalGroup::Init builds the explosion ring as an opaque, hard-edged,
#: floor-only SCORCH: measured, its branch leaves the projector bool word at
#: +0x37C as 0x8C85 where the wall-hit branch leaves 0xA3C7, plus
#: FrameBufferBlendingOp 1 against 3.
#:
#: An earlier fix simply repointed the type dispatch at 0x00378B44 so the
#: explosion ring borrowed the wall-hit branch. That got the look exactly
#: right and cost one word -- but it also handed the ring the wall-hit
#: branch's DrawScale, which is the same 1.0 the game's own bullet holes use,
#: so making explosion marks bigger would have enlarged bullet holes too.
#:
#: So the dispatch is left stock and the ring's OWN branch is patched in
#: place instead, to produce bit-for-bit the same bools and blend op while
#: keeping its own DrawScale constant. All four are independently necessary
#: (brute-forced over every subset), and the result was checked by emulating
#: all five branches and reproducing the bool words, blend ops and DrawScales
#: measured in two EE dumps.
BRANCH_WORDS = (
    (0x00378E14, 0x30040001, 0x34040001),   # andi
    (0x00378E30, 0x24080001, 0x24080003),   # addiu
    (0x00378E44, 0x64050004, 0x64050000),   # daddiu
    (0x00378E50, 0x64030008, 0x64030001),   # daddiu
)

#: `lui $v0, 0x4100` -- the 8.0f DrawScale the scorch wanted. Only the TOP
#: half of the float is written, which still leaves a 7-bit mantissa: 128
#: steps per octave, so any sensible size is expressible.
#: Size = DrawScale x decal+0x250 x ProjTexture.USize, and +0x250 is 1.0 on
#: every pooled decal, so this is a plain linear multiplier.
DRAWSCALE = 0x00378E00
DRAWSCALE_STOCK = 0x3C024100


def drawscale_word(scale: float) -> int:
    """`lui $v0, hi16(scale)`, refusing a size the top half cannot carry."""
    bits = struct.unpack("<I", struct.pack("<f", float(scale)))[0]
    if bits & 0xFFFF:
        raise DecalError("DrawScale %r needs a low half this word cannot carry"
                         % scale)
    return 0x3C020000 | (bits >> 16)


DRAWSCALES = (1.0, 1.25, 1.5, 2.0, 3.0, 4.0)

#: Why the marks smeared, and it is not the reach.
#:
#: AttachProjector builds THRESH = min(sin(FOV/2), sin(minProjectAngle)) and
#: accepts a BSP node when dot(normal, forward) < THRESH. sin(90 deg) = 1.0 is
#: sine's global MAXIMUM, so a minProjectAngle of 90 can never win that min()
#: -- THRESH stays sin(0.5 deg) = 0.0087 and every surface up to 89.5 degrees
#: off square is accepted. That is the smear, and it is why the pooled
#: decals' apparently strict 90.0 does nothing at all.
#:
#: A NEGATIVE angle is what caps it: max incidence = 90 + minProjectAngle.
#: The game does this itself -- the blood-splat branch writes -15.0.
#:
#: It only caps BSP. The terrain gather (an AABB overlap) and the static-mesh
#: gather (a collision hash) have no angle test at all, so a mark beside a
#: crate or a pipe can still stretch and only a shorter projector reach helps
#: there.
#:
#: WHERE THE TWO WORDS GO, AND WHY THEY ARE FREE
#:
#: An earlier version of this list claimed that patching 0x00378E14 left the
#: three instructions after it dead, and overwrote 0x00378E68..0x00378E74.
#: That was wrong. Those four words are a read-modify-write of bit 1 of
#: decal+0x37C -- `bProjectTerrain` -- and they are the ONLY writer of that
#: bit anywhere in Init. They are FED by 0x00378E14, they are not replaced
#: by it: $t3 = $a0 << 1 is the bit-1 value, so setting $a0 is what makes
#: them write a 1.
#:
#: The branch really does have two dead words, but they have to be MADE dead.
#: The bit-6 sequence just above already reads the byte, clears a bit and
#: stores it:
#:
#:     0x00378E20  addiu $t1, $zero, -0x41     ; ~0x40
#:     0x00378E54  lbu   $t5, 0x37c($s3)
#:     0x00378E5C  and   $t1, $t5, $t1         ; clear bit 6
#:     0x00378E60  or    $t1, $t1, $t4         ; set it from $a0
#:     0x00378E64  sb    $t1, 0x37c($s3)
#:     0x00378E68  lbu   $t1, 0x37c($s3)       ; reload what we just wrote
#:     0x00378E6C  and   $t1, $t1, $t2         ; clear bit 1
#:     0x00378E70  or    $t1, $t1, $t3         ; set it from $a0
#:     0x00378E74  sb    $t1, 0x37c($s3)
#:
#: Widening that first mask to -0x43 clears bit 1 as well, so the byte stored
#: at 0x00378E64 -- still live in $t1 -- is already what the reload and the
#: second mask were there to produce. The reload and the mask become dead,
#: the `or`/`sb` stay STOCK, and bit 1 is still written from $a0. Nothing
#: reads decal+0x37C between the two stores and no call intervenes, so the
#: byte's transient state is unobservable.
#:
#: $t5 carries the constant: it is dead from 0x00378E5C onward and is read
#: nowhere else in the function, including around the loop back-edge. The
#: whole branch 0x00378DFC..0x00378EB8 is entered only by the `beq` at
#: 0x00378B44, so none of this is reachable for any other decal type.
INCIDENCE_WORDS = (
    (0x00378E20, 0x2409FFBF, 0x2409FFBD),   # mask ~0x40 -> ~0x42
    (0x00378E68, 0x9269037C, 0x3C0DC1F0),   # lui $t5, 0xC1F0
    (0x00378E6C, 0x012A4824, 0xAE6D0384),   # sw  $t5, 0x384($s3)
    (0x00378E70, 0x012B4825, 0x012B4825),   # or  $t1, $t1, $t3   (stock)
    (0x00378E74, 0xA269037C, 0xA269037C),   # sb  $t1, 0x37c($s3) (stock)
)

#: Clearing bit 1 (`bProjectTerrain`) on one decal group. Each is the mask of
#: the LAST write to byte 0 of `decal+0x37C` in that group's arm of
#: `R6DecalGroup::Init`, widened from `~0x80` to `~0x82` so it clears bit 1 as
#: well as bit 7 while the paired OR value (`0x80`) still puts bit 7 back.
#: Being last is what makes each one immune to BRANCH_WORDS and
#: INCIDENCE_WORDS; verified in every combination of the two.
#:
#: (va, stock, new), the same shape as BRANCH_WORDS and INCIDENCE_WORDS.
TERRAIN_OFF_SHRAPNEL = ((0x00378E34, 0x2406FF7F, 0x2406FF7D),)   # 0xA3C7->0xA3C5
TERRAIN_OFF_BLOOD = ((0x00378CE4, 0x2409FF7F, 0x2409FF7D),)      # 0xA1C7->0xA1C5
TERRAIN_OFF_HOLES = ((0x00378C30, 0x2408FF7F, 0x2408FF7D),)      # 0xA3C7->0xA3C5

#: The sledgehammer: `beqz $v0,0x00257F44` -> `b 0x00257F44`, the bit-1 gate in
#: AProjector::Attach itself. One word, same branch offset (103), and the delay
#: slot `lui $a0,0x6F` is harmless because the stat clock it feeds is skipped
#: along with the unclock. It kills the terrain gather for EVERY AProjector in
#: the game, not just decals -- character shadows included.
TERRAIN_KILL = ((0x00257DA4, 0x10400067, 0x10000067),)

#: cumulative, each a prefix of the next
TERRAIN_SCOPES = ("stock", "shrapnel", "shrapnel_blood", "every_mark",
                  "every_projector")
#: Defaults must emit NOTHING -- the suite checks that an untouched
#: profile produces an empty cheat file, and a non-stock default here
#: broke 21 of those checks. The useful value is "shrapnel_blood";
#: it is opted into, not assumed.
TERRAIN_DEFAULT = "stock"


def terrain_words(scope: str = TERRAIN_DEFAULT):
    """((va, stock, new), ...) for the chosen scope.

    Cumulative: each scope is a superset of the one before it.
    """
    if scope not in TERRAIN_SCOPES:
        raise DecalError("no such terrain scope: %r" % (scope,))
    out = ()
    if scope != "stock":
        out += TERRAIN_OFF_SHRAPNEL
    if scope in ("shrapnel_blood", "every_mark", "every_projector"):
        out += TERRAIN_OFF_BLOOD
    if scope in ("every_mark", "every_projector"):
        out += TERRAIN_OFF_HOLES
    if scope == "every_projector":
        out += TERRAIN_KILL
    return out

# -------------------------------------------------------------- the cave ---

#: `ld $ra, 0xa0($sp)` -- the first word of the explosion native's epilogue.
HIJACK_AT = 0x00268BC4
HIJACK_STOCK = 0xDFBF00A0
#: `j 0x000F1000`
HIJACK = 0x0803C400

CAVE = 0x000F1000
#: Where the `ori $s6, $s6, N` that carries the mark count sits. The `lui`
#: before it is zero, so N is a plain 16-bit immediate.
COUNT_AT = 0x000F10D0
COUNT_MAX = 0xFFFF

#: How far above the blast the rays START, in world units (100 = 1 metre). A
#: grenade at rest sits about 8 units up, so without this every downward ray
#: lands inside the 20-unit degenerate-trace guard and is thrown away. Only
#: the trace START moves; the scatter origin and the epicentre the guard
#: measures from do not. 0.0 turns it off.
TRACE_LIFT_UNITS = 40.0
#: Kept clear of whatever the once-per-blast up-probe finds overhead, so the
#: lifted start is never ON the surface above it. Under a lower overhang the
#: lift shrinks to (clearance - this) and floors at zero.
#:
#: Both are baked into _WORDS above; they are recorded here so a rebuild knows
#: what the words were generated with.
TRACE_LIFT_MARGIN = 10.0

#: How a mark's texture is chosen, per mark, without hard-coding a
#: pointer:
#:
#:     mat = *(FCheckResult.Material)      Trace's $t3 out-parameter
#:     cls = mat->+0x50                    Material.m_pHitEffect
#:     find i in 0..*(0x0065526C)-1 with
#:         (*(0x006DD7A0 + 4i))->+0x20 == cls->+0x20     FName equality
#:     inst = *(0x006DD6C0 + 4i)           the pooled R6*Effect
#:     tex  = inst->+0x388 / +0x38C        m_DecalTexture Data / Num
#:
#: FName equality rather than pointer equality because that is what
#: 0x003F08C0 itself compares, at 0x003F0924/0x003F092C -- two
#: identically named classes from different packages would both match
#: there too, so the cave agrees with the game rather than being
#: stricter than it.
#:
#: Every dereference is null- and alignment-checked, which is already
#: stricter than 0x003F08C0, whose own key-table walk does
#: `lw $a2, 0x20($a2)` with no null check at all.
#:
#: When the ENGINE could not name the surface -- Material NULL, which
#: is what every TERRAIN hit gives, because 0x002CF5A0 never writes
#: FCheckResult+0x3C -- or when it named a slot whose m_DecalTexture is
#: empty, the mark uses the R6GenericEffect slot instead. A material
#: that names NO hit effect keeps skipping: that is the sky
#: (PF_FakeBackdrop), the zone portals and Color.Black, and a mark
#: there would hang on the skybox. Resolved ONCE per blast, into two
#: frame slots, by walking the same key table and comparing each key
#: class's FName TEXT (FName::Names 0x00686060, entry text at +0x0D)
#: against the literal `r6genericeffect` the cave builds into its own
#: frame. Not an index and not a pointer: a re-ordered impact
#: cache would still find it, and nothing here survives a reload.
#: Second chance is the first slot with a non-empty m_DecalTexture --
#: the shipped cave's own rule -- and then the mark is skipped.
#:
#: The trace START is raised by TRACE_LIFT_UNITS, which is the only
#: thing the lift touches: TraceStart.z. The epicentre the
#: degenerate-trace guard measures from, and the scatter origin the ray
#: directions come off, are both unchanged.
_WORDS = (
    0x8E910104, 0x12200201, 0x00000000, 0x32210003,
    0x142001FE, 0x00000000, 0x3C010200, 0x0221082B,
    0x102001FA, 0x00000000, 0x8E310548, 0x122001F7,
    0x00000000, 0x32210003, 0x142001F4, 0x00000000,
    0x3C010200, 0x0221082B, 0x102001F0, 0x00000000,
    0x3C010065, 0x8C2C526C, 0x198001EC, 0x00000000,
    0x27BDFF40, 0xAFA0000C, 0xAFA0001C, 0xC7A3052C,
    0x44800000, 0x46001836, 0x00000000, 0x450101E2,
    0x00000000, 0xE7A3002C, 0xC7A00170, 0xE7A00020,
    0xE7A00060, 0xC7A10174, 0xE7A10024, 0xE7A10064,
    0xC7A20178, 0xE7A20028, 0xE7A20068, 0xAFA0006C,
    0x44170000, 0x44080800, 0x44091000, 0x00084040,
    0x00094880, 0x02E8B826, 0x02E9B826, 0x3C160000,
    0x36D6000C, 0x0000A821, 0x00008021, 0xAFA0007C,
    0xAFA00070, 0xAFA00074, 0x3C026567, 0x34423672,
    0xAFA20080, 0x3C026972, 0x3442656E, 0xAFA20084,
    0x3C026666, 0x34426563, 0xAFA20088, 0x3C020074,
    0x34426365, 0xAFA2008C, 0x3C010065, 0x8C2C526C,
    0x19800051, 0x00000000, 0x0000C021, 0x130C004E,
    0x00000000, 0x00181080, 0x3C01006E, 0x00220821,
    0x8C39D7A0, 0x27180001, 0x1320FFF8, 0x00000000,
    0x33210003, 0x1420FFF5, 0x00000000, 0x8F2F0020,
    0x05E0FFF2, 0x00000000, 0x3C010068, 0x8C2E6064,
    0x01EE082B, 0x1020FFED, 0x00000000, 0x3C010068,
    0x8C2E6060, 0x11C00038, 0x00000000, 0x31C10003,
    0x14200035, 0x00000000, 0x000F1080, 0x01C27021,
    0x8DCE0000, 0x11C0FFE1, 0x00000000, 0x31C10003,
    0x1420FFDE, 0x00000000, 0x25CE000D, 0x27AD0080,
    0x3C0B0000, 0x356B0028, 0x1160FFD8, 0x00000000,
    0x256BFFFF, 0x91C20000, 0x91A30000, 0x25CE0001,
    0x25AD0001, 0x10600007, 0x00000000, 0x34420020,
    0x34630020, 0x1043FFF4, 0x00000000, 0x1000FFCB,
    0x00000000, 0x1440FFC9, 0x00000000, 0x2718FFFF,
    0x00181080, 0x3C01006E, 0x00220821, 0x8C39D6C0,
    0x13200011, 0x00000000, 0x33210003, 0x1420000E,
    0x00000000, 0x8F220388, 0x1040000B, 0x00000000,
    0x30410003, 0x14200008, 0x00000000, 0x8F23038C,
    0x18600005, 0x00000000, 0xAFA20070, 0xAFA30074,
    0x10000020, 0x00000000, 0x8FA10070, 0x1420001D,
    0x00000000, 0x3C010065, 0x8C2C526C, 0x19800019,
    0x00000000, 0x00006821, 0x11AC0016, 0x00000000,
    0x000D1080, 0x3C01006E, 0x00220821, 0x8C2ED6C0,
    0x25AD0001, 0x11C0FFF8, 0x00000000, 0x31C10003,
    0x1420FFF5, 0x00000000, 0x8DC20388, 0x1040FFF2,
    0x00000000, 0x30410003, 0x1420FFEF, 0x00000000,
    0x8DC3038C, 0x1860FFEC, 0x00000000, 0xAFA20070,
    0xAFA30074, 0x3C014220, 0x34210000, 0x44816000,
    0xE7AC00BC, 0xC7A00020, 0xE7A00050, 0xC7A10024,
    0xE7A10054, 0xC7A20028, 0x460C1080, 0xE7A20058,
    0xAFA0005C, 0x02802021, 0x27A50030, 0x27A60040,
    0x27A70050, 0x27A80060, 0x3C090000, 0x35290000,
    0x3C0A005D, 0x254A5680, 0x00005821, 0x0C09BBA0,
    0x00000000, 0x10400011, 0x00000000, 0xC7A00038,
    0xC7A10028, 0x46010001, 0x3C014120, 0x34210000,
    0x44816000, 0x460C0001, 0x44800800, 0x46010034,
    0x00000000, 0x45010004, 0x00000000, 0xE7A000BC,
    0x10000002, 0x00000000, 0xAFA000BC, 0xC7A00028,
    0xC7A100BC, 0x46010000, 0xE7A00068, 0x12B6011A,
    0x00000000, 0x3C010019, 0x3421660D, 0x02E10018,
    0x0000B812, 0x3C013C6E, 0x3421F35F, 0x02E1B821,
    0x00175202, 0x314AFFFF, 0x3C010019, 0x3421660D,
    0x02E10018, 0x0000B812, 0x3C013C6E, 0x3421F35F,
    0x02E1B821, 0x00171242, 0x30427FFF, 0x44827800,
    0x46807BE0, 0x3C013800, 0x34210000, 0x44816000,
    0x460C7BC2, 0x3C014000, 0x34210000, 0x44816000,
    0x460C7BC2, 0x3C013F80, 0x34210000, 0x44816000,
    0x460C7BC1, 0x460F7902, 0x3C013F80, 0x34210000,
    0x44816000, 0x46046101, 0x46040104, 0x25424000,
    0x00021082, 0x30423FFF, 0x00021080, 0x3C010069,
    0x00220821, 0xC426A8F0, 0x000A1082, 0x30423FFF,
    0x00021080, 0x3C010069, 0x00220821, 0xC427A8F0,
    0x46062202, 0x46072242, 0xE7A80080, 0xE7A90084,
    0xE7AF0088, 0xC7A3002C, 0x3C014040, 0x34210000,
    0x44816000, 0x460C18C2, 0x46034202, 0x46034A42,
    0x46037BC2, 0xC7A00020, 0xC7A10024, 0xC7A20028,
    0x46004200, 0x46014A40, 0x46027BC0, 0xE7A80050,
    0xE7A90054, 0xE7AF0058, 0xAFA0005C, 0x02802021,
    0x27A50030, 0x27A60040, 0x27A70050, 0x27A80060,
    0x3C090000, 0x35290000, 0x3C0A005D, 0x254A5680,
    0xAFA00078, 0x27AB0078, 0x0C09BBA0, 0x00000000,
    0x104000BE, 0x00000000, 0xC7A00030, 0xC7A10034,
    0xC7A20038, 0xC7A40020, 0xC7A50024, 0xC7A60028,
    0x46040001, 0x46050841, 0x46061081, 0x46000002,
    0x46010842, 0x46021082, 0x46010000, 0x46020000,
    0x3C0143C8, 0x34210000, 0x44816000, 0x460C0034,
    0x00000000, 0x450100A9, 0x00000000, 0xC7A40040,
    0xC7A50044, 0xC7A60048, 0x3C014140, 0x34210000,
    0x44816000, 0x460C2202, 0x460C2A42, 0x460C33C2,
    0xC7A00030, 0xC7A10034, 0xC7A20038, 0x46080200,
    0x46090A40, 0x460F13C0, 0xE7A80000, 0xE7A90004,
    0xE7AF0008, 0x46002107, 0x46002947, 0x46003187,
    0xE7A40090, 0xE7A50094, 0xE7A60098, 0xAFA0009C,
    0x27A40010, 0x27A50090, 0x0C05B7B0, 0x00000000,
    0x8FAD0078, 0x11A00034, 0x00000000, 0x31A10003,
    0x14200031, 0x00000000, 0x8DAE0050, 0x11C00083,
    0x00000000, 0x31C10003, 0x14200080, 0x00000000,
    0x8DCF0020, 0x3C010065, 0x8C2C526C, 0x19800026,
    0x00000000, 0x0000C021, 0x130C0078, 0x00000000,
    0x00181080, 0x3C01006E, 0x00220821, 0x8C39D7A0,
    0x27180001, 0x1320FFF8, 0x00000000, 0x33210003,
    0x1420FFF5, 0x00000000, 0x8F210020, 0x142FFFF2,
    0x00000000, 0x2718FFFF, 0x00181080, 0x3C01006E,
    0x00220821, 0x8C39D6C0, 0x1320000F, 0x00000000,
    0x33210003, 0x1420000C, 0x00000000, 0x8F330388,
    0x12600009, 0x00000000, 0x32610003, 0x14200006,
    0x00000000, 0x8F32038C, 0x1A400003, 0x00000000,
    0x10000007, 0x00000000, 0x8FB30070, 0x12600053,
    0x00000000, 0x8FB20074, 0x1A400050, 0x00000000,
    0x0212082B, 0x14200002, 0x00000000, 0x00008021,
    0x00101080, 0x02620821, 0x8C270000, 0x26100001,
    0x16120002, 0x00000000, 0x00008021, 0x10E00043,
    0x00000000, 0x02202021, 0x27A50000, 0x27A60010,
    0x3C080000, 0x35080004, 0x3C090000, 0x35290001,
    0x3C010000, 0x34210000, 0x44816000, 0x3C010000,
    0x34210000, 0x44816800, 0x3C0141A0, 0x34210000,
    0x44817000, 0x0C0DE5E0, 0x00000000, 0x8FAC007C,
    0x3C010000, 0x34210003, 0x0181082A, 0x1020002B,
    0x00000000, 0x8FAD0078, 0x11A00028, 0x00000000,
    0x31A10003, 0x14200025, 0x00000000, 0x8DAE0050,
    0x11C00022, 0x00000000, 0x31C10003, 0x1420001F,
    0x00000000, 0x0000C021, 0x130C0009, 0x00000000,
    0x00180880, 0x03A10821, 0x8C3900B0, 0x132E0017,
    0x00000000, 0x27180001, 0x1000FFF7, 0x00000000,
    0x000C0880, 0x03A10821, 0xAC2E00B0, 0x27A400A0,
    0x27A50040, 0x0C05B7B0, 0x00000000, 0x8FA50078,
    0x8CA50050, 0x02802021, 0x27A60030, 0x27A700A0,
    0x00004821, 0x00005021, 0x0C0FC230, 0x00000000,
    0x8FAC007C, 0x258C0001, 0xAFAC007C, 0x26B50001,
    0x1000FEE6, 0x00000000, 0x27BD00C0, 0xDFBF00A0,
    0x0809A2F3, 0x00000000,
)

#: The count the table was assembled with.
COUNT_DEFAULT = 12


def words(n_marks: int = COUNT_DEFAULT, stagger: bool = False):
    """[(va, word)] for the cave, with the mark count patched in.

    `stagger` swaps the one word that decides whether an impact fires now or
    is queued for a later frame.
    """
    n = int(n_marks)
    if not 1 <= n <= COUNT_MAX:
        raise DecalError("mark count %r is outside 1..%d" % (n_marks, COUNT_MAX))
    out = []
    for i, w in enumerate(_WORDS):
        va = CAVE + 4 * i
        if va == COUNT_AT:
            w = (w & 0xFFFF0000) | n
        if va == IMPACT_CALL_AT:
            assert w == IMPACT_CALL_NOW, "the impact call moved"
            w = IMPACT_CALL_QUEUED if stagger else IMPACT_CALL_NOW
        out.append((va, w))
    return out


def reads(word_at) -> bool:
    """True if `word_at(va)` shows the hijack in place."""
    return word_at(HIJACK_AT) == HIJACK


# ---------------------------------------------------- the impact stagger ---

#: Three impacts in one frame read as a single thud. This defers them so you
#: hear separate strikes, which is what shrapnel sounds like.
#:
#: `lw $a0, 0x45c($s0)` inside UGameEngine::Tick, four instructions before the
#: engine ticks the game level. It runs exactly ONCE per rendered frame --
#: measured, not assumed: the main loop holds one Engine->Tick call, that
#: vtable slot resolves to this function in two EE dumps, this word is on
#: every path to the single return and on no cycle, and one loop iteration
#: was measured as one present (60.57/s against the loop's own 60.96/s).
#:
#: NOT inside ULevel::Tick, which the claymore cave hooks: that runs TWICE
#: per frame, because GEngine+0x460 is a second live ULevel, and it is not on
#: every path through the function either. Harmless for a proximity check;
#: fatal for anything counting frames.
STAGGER_HOOK = 0x002EA97C
STAGGER_HOOK_STOCK = 0x8E04045C
#: `j 0x000F2000`. The jump's delay slot (`addiu $a1,$zero,2`) still runs, so
#: the consumer re-does the displaced load into $a0, re-supplies that $a1 and
#: returns to 0x002EA984.
STAGGER_HOOK_JUMP = 0x0803C800

#: Where the existing cave's `jal` to the impact entry point sits, and the two
#: words it can hold. The enqueue helper takes the identical register
#: contract and tail-calls the impact entry point when it cannot queue, so
#: staggering degrades to today's behaviour rather than to silence.
IMPACT_CALL_AT = 0x000F17E8
IMPACT_CALL_NOW = 0x0C0FC230
IMPACT_CALL_QUEUED = 0x0C03C900

CONSUMER = 0x000F2000
ENQUEUE = 0x000F2400
#: The queue itself is RUNTIME STATE and is deliberately NOT emitted. A pnach
#: row rewrites its address every frame, so putting these bytes in the cheat
#: file would reset the queue every frame and nothing would ever fire.
QUEUE = 0x000F2800
QUEUE_END = 0x000F2A50


# ------------------------------------------------- the impact-burst gate ---

#: Why only one puff of dust ever appears, however many impacts fire.
#:
#: It is not the pooled impact actor, which was the first suspect. It is a
#: rate limit in the visual half of the impact -- ONE float for the whole
#: engine, holding when any burst last played, with a half-second window:
#:
#:     0x0056E3E4  lui     $v1, 0x3F00          ; 0.5f
#:     0x0056E3E8  lwc1    $f1, -0x5794($gp)    ; when a burst last fired,
#:     0x0056E3EC  mtc1    $v1, $f0             ;   ANYWHERE
#:     0x0056E3F0  lwc1    $f2, 0xB0($a0)       ; now
#:     0x0056E3F4  sub.s   $f1, $f2, $f1        ; elapsed
#:     0x0056E3F8  c.ole.s $f1, $f0             ; elapsed <= 0.5 ?
#:     0x0056E400  bc1t    0x0056E520           ; yes -> skip the whole burst
#:
#: Every word read back off the disc as written here. The stamp's global has
#: three references in the whole 5.5 MB overlay and all of them sit inside
#: this window, so there is nothing else to reset it.
#:
#: That also explains the asymmetry: the impact SOUND is played upstream of
#: this gate and is not throttled, which is why three impacts are audible
#: while one is visible.
#:
#: Removing the branch lets every burst play. It is engine-wide, so ordinary
#: gunfire gets its dust back too, which is the point and also the cost.
BURST_GATE = 0x0056E400
BURST_GATE_STOCK = 0x45010047
#: `nop`. The delay slot is already a `nop`, so nothing else moves.
BURST_GATE_OFF = 0x00000000

_CONSUMER_WORDS = (
    0x8E08045C, 0x3C09000F, 0x25292800, 0x11000004,
    0x00000000, 0x8D2A0000, 0x1148000C, 0x00000000,
    0xAD280000, 0xAD200004, 0xAD200008, 0x252B0010,
    0x240C000C, 0xAD60002C, 0x258CFFFF, 0x1D80FFFD,
    0x256B0030, 0x1100002E, 0x00000000, 0x8D0A002C,
    0x1140002B, 0x00000000, 0x8D4A0000, 0x11400028,
    0x00000000, 0xC544045C, 0xC5250004, 0x46052034,
    0x00000000, 0x4501FFEA, 0x00000000, 0xE5240004,
    0x252B0010, 0x240C000C, 0x8D6D002C, 0x11A00019,
    0x00000000, 0xC5650020, 0x46052034, 0x00000000,
    0x45010014, 0x00000000, 0xAD60002C, 0x8D650024,
    0x10A00013, 0x00000000, 0x8D640028, 0x14800005,
    0x00000000, 0x8D04002C, 0x8C840000, 0x1080000C,
    0x00000000, 0x25660000, 0x25670010, 0x00004821,
    0x00005021, 0x0C0FC230, 0x00000000, 0x10000004,
    0x00000000, 0x258CFFFF, 0x1D80FFE3, 0x256B0030,
    0x8E04045C, 0x080BAA61, 0x24050002,
)

_ENQUEUE_WORDS = (
    0x3C08000F, 0x25082800, 0x8D0B0000, 0x1160004C,
    0x00000000, 0x250C0010, 0x240D000C, 0x8D8E002C,
    0x11C00006, 0x00000000, 0x25ADFFFF, 0x1DA0FFFB,
    0x258C0030, 0x10000042, 0x00000000, 0x8CCE0000,
    0xAD8E0000, 0x8CCE0004, 0xAD8E0004, 0x8CCE0008,
    0xAD8E0008, 0xAD80000C, 0x8CEF0000, 0xAD8F0010,
    0x8CEF0004, 0xAD8F0014, 0x8CEF0008, 0xAD8F0018,
    0xAD80001C, 0xAD850024, 0xAD800028, 0x8D78002C,
    0x1300002F, 0x00000000, 0x8F180000, 0x1300002C,
    0x00000000, 0xC704045C, 0xC5050008, 0x46052034,
    0x00000000, 0x4500000D, 0x00000000, 0x3C013F19,
    0x3421999A, 0x44813000, 0x460621C0, 0x46053834,
    0x00000000, 0x45010003, 0x00000000, 0x10000005,
    0x46002906, 0x10000003, 0x46003906, 0x10000013,
    0x00000000, 0x8D8E0000, 0x8D8F0004, 0x01CF7026,
    0x8D8F0008, 0x01CF7026, 0x000E71C2, 0x31CE0003,
    0x448E4000, 0x46804220, 0x3C013D19, 0x3421999A,
    0x44814800, 0x46094202, 0x3C013E19, 0x3421999A,
    0x44814800, 0x46094200, 0x46082100, 0xE5840020,
    0xE5040008, 0x240E0001, 0x03E00008, 0xAD8E002C,
    0x080FC230, 0x00000000,
)


def stagger_words():
    """[(va, word)] for the two stagger routines. Never includes the queue."""
    out = [(CONSUMER + 4 * i, w) for i, w in enumerate(_CONSUMER_WORDS)]
    out += [(ENQUEUE + 4 * i, w) for i, w in enumerate(_ENQUEUE_WORDS)]
    assert all(va < QUEUE or va >= QUEUE_END for va, _w in out)
    return out


# ------------------------------------------------- blood splatter on walls --

#: 0x003F1EF0 `b 0x003F2560`, the last word of the PAWN branch of the bullet
#: trace native 0x003F1180. Reached by fallthrough only, on every bullet that
#: actually damages a person; the two friendly-fire checks above it
#: (0x003F1E34, 0x003F1E60) bail to 0x003F2584 instead.
#:
#: The jump's delay slot, 0x003F1EF4 `cvt.s.w $f21,$f0`, is not a branch and
#: still runs, so the damage-remaining value is correct before the cave is
#: entered and nothing is displaced.
#:
#: The five branches that route round the game's own actor-attached decal
#: (0x003F1B60, 0x003F1BB4, 0x003F1BC0, 0x003F1BCC, 0x003F1BD8) all converge
#: at 0x003F1DC8, which is UPSTREAM of this word -- so the "Impact decals"
#: split-screen card, which NOPs 0x003F1BB4, cannot stop the cave being
#: reached, and neither can split screen itself.
BLOOD_HOOK = 0x003F1EF0
BLOOD_HOOK_STOCK = 0x1000019B
#: `j 0x000F3400`
BLOOD_HOOK_JUMP = 0x0803CD00
BLOOD_RESUME = 0x003F2560

#: Fresh space above every block already taken: claymore 0x000F0000..0800,
#: shrapnel 0x000F1000..153C, stagger 0x000F2000/2400, its queue
#: 0x000F2800..2A50, the puff ring and cave 0x000F2C00..3400 (highest word
#: actually used, measured, 0x000F30CC). 0x000F3400..0x000F4400 reads ZERO in
#: all six EE images.
BLOOD_CAVE = 0x000F3400

#: How far past the victim to look for something to mark, in game units
#: (100 units = 1 metre). Short means blood only appears when they were near a
#: surface; long means it nearly always finds one. It is also the only thing
#: keeping a mark off a skybox, because the cave cannot reach
#: FCheckResult.Item to test PF_FakeBackdrop.
BLOOD_REACH_DEFAULT = 300.0
BLOOD_REACH_CHOICES = (120.0, 300.0, 700.0)

_BLOOD_WORDS = (
    0x27BDFF80, 0x8E280104, 0x11000096, 0x00000000,
    0x31010003, 0x14200093, 0x00000000, 0x8D080548,
    0x11000090, 0x00000000, 0x31010003, 0x1420008D,
    0x00000000, 0xAFA80070, 0x3C010065, 0x8C295DE4,
    0x11200088, 0x00000000, 0x31210003, 0x14200085,
    0x00000000, 0x8D290148, 0x11200082, 0x00000000,
    0x31210003, 0x1420007F, 0x00000000, 0x8D290370,
    0x1120007C, 0x00000000, 0x31210003, 0x14200079,
    0x00000000, 0xAFA90074, 0x8E4A0010, 0xAFAA0040,
    0x8E4A0014, 0xAFAA0044, 0x8E4A0018, 0xAFAA0048,
    0xAFA0004C, 0xC7A401E0, 0xC7A501E4, 0xC7A601E8,
    0x3C014396, 0x34210000, 0x44816000, 0x460C2202,
    0x460C2A42, 0x460C3282, 0xC7A00040, 0xC7A10044,
    0xC7A20048, 0x46080200, 0x46090A40, 0x460A1280,
    0xE7A80050, 0xE7A90054, 0xE7AA0058, 0xAFA0005C,
    0x02202021, 0x27A50020, 0x27A60030, 0x27A70050,
    0x27A80040, 0x24090000, 0x3C0A005D, 0x254A5680,
    0x00005821, 0x0C09BBA0, 0x00000000, 0x14400019,
    0x00000000, 0xC7A00040, 0xC7A10044, 0xC7A20048,
    0x3C01C37A, 0x34210000, 0x44816000, 0x460C1080,
    0xE7A00050, 0xE7A10054, 0xE7A20058, 0xAFA0005C,
    0x02202021, 0x27A50020, 0x27A60030, 0x27A70050,
    0x27A80040, 0x24090000, 0x3C0A005D, 0x254A5680,
    0x00005821, 0x0C09BBA0, 0x00000000, 0x10400039,
    0x00000000, 0xC7A40030, 0xC7A50034, 0xC7A60038,
    0x3C014140, 0x34210000, 0x44816000, 0x460C2202,
    0x460C2A42, 0x460C3282, 0xC7A00020, 0xC7A10024,
    0xC7A20028, 0x46080200, 0x46090A40, 0x460A1280,
    0xE7A80000, 0xE7A90004, 0xE7AA0008, 0xAFA0000C,
    0x46002107, 0x46002947, 0x46003187, 0xE7A40060,
    0xE7A50064, 0xE7A60068, 0xAFA0006C, 0x27A40010,
    0x27A50060, 0x0C05B7B0, 0x00000000, 0x8FAC0020,
    0x8FAD0024, 0x8FAE0028, 0x018D6026, 0x018E6026,
    0x8FAD0040, 0x8FAE0048, 0x018D6026, 0x018E6026,
    0x000C6B42, 0x018D6026, 0x318CFFFF, 0xAFAC0018,
    0x8FA40070, 0x27A50000, 0x27A60010, 0x8FA70074,
    0x24080002, 0x24090001, 0x44806000, 0x44806800,
    0x3C0141A0, 0x34210000, 0x44817000, 0x0C0DE5E0,
    0x00000000, 0x27BD0080, 0x080FC958, 0x00000000,
)


def blood_words(reach: float = BLOOD_REACH_DEFAULT):
    """[(va, word)] for the blood cave, with the reach patched in.

    The reach is carried by the `lui`/`ori` pair that builds the float, so it
    is two words and no re-assembly.
    """
    import struct as _s
    bits = _s.unpack("<I", _s.pack("<f", float(reach)))[0]
    lui_w = 0x3C010000 | ((bits >> 16) & 0xFFFF)
    ori_w = 0x34210000 | (bits & 0xFFFF)
    out = []
    for i, w in enumerate(_BLOOD_WORDS):
        va = BLOOD_CAVE + 4 * i
        if va == BLOOD_REACH_AT[0]:
            w = lui_w
        elif va == BLOOD_REACH_AT[1]:
            w = ori_w
        out.append((va, w))
    return out


#: Where that pair sits. Asserted against the table rather than searched for,
#: so a re-assembled table that moved it fails loudly instead of silently
#: ignoring the card.
BLOOD_REACH_AT = (0x000F34B0, 0x000F34B4)
assert _BLOOD_WORDS[(BLOOD_REACH_AT[0] - BLOOD_CAVE) // 4] == 0x3C014396
assert _BLOOD_WORDS[(BLOOD_REACH_AT[1] - BLOOD_CAVE) // 4] == 0x34210000

#: R6DecalManager builds the BloodSplats ring 16 deep. `addiu $a2,$zero,0x10`
#: at 0x00379C50 is stored into m_BloodSplats->+0x374 at 0x00379C64, which is
#: the size R6DecalGroup::Init then allocates -- the same shape as the
#: `decal_ring` word at 0x00379B30 and the `grenade_decals` word at
#: 0x00379B38. A disc word, not a cheat row.
BLOOD_RING = 0x00379C50
BLOOD_RING_STOCK = 0x24060010
#: addiu sign-extends, so this is the hard encoding limit.
BLOOD_RING_MAX = 0x7FFF


def blood_ring_word(n: int) -> int:
    """`addiu $a2, $zero, n` -- how many blood marks the ring keeps."""
    n = int(n)
    if not 1 <= n <= BLOOD_RING_MAX:
        raise DecalError("blood ring %r is outside 1..%d" % (n, BLOOD_RING_MAX))
    return 0x24060000 | (n & 0xFFFF)


# ------------------------------------------------------------------ cards --
def cards(prefix, group):
    from .model import BOOL, CHOICE, Choice, INT, Setting

    return [
        Setting(
            prefix + "blood_splats", "Blood marks on walls and floors",
            BOOL, False, group,
            confidence="experimental", touches="ram",
            help="Shoot someone and the shot carries on into whatever is "
                 "behind them, leaving a blood mark there -- on the wall if "
                 "they were standing against one, on the ground if you were "
                 "firing downward. The game already builds a ring of sixteen "
                 "blood marks on every level and never once uses it; this "
                 "feeds it.\n\n"
                 "The mark is the game's own blood texture, placed square "
                 "against the surface it lands on, and turned a different way "
                 "each time so a firefight does not leave the same stamp over "
                 "and over. Friendly fire that the game refuses never leaves "
                 "a mark, and neither does a shot with nothing within reach "
                 "behind or below.",
            caution="Not yet played. It rides in the cheat file, so save a "
                    "fresh one and restart the emulator.\n\n"
                    "Only bullets leave blood. A grenade kill goes through "
                    "different code entirely and leaves none.\n\n"
                    "Sixteen marks is not many: a shotgun can place most of a "
                    "trigger pull's worth at once, and in split screen two "
                    "players fill the ring twice as fast, so raise \"Blood "
                    "marks kept on screen\" alongside this."),
        Setting(
            prefix + "blood_reach", "How far blood carries", CHOICE,
            "300", group,
            requires={prefix + "blood_splats": [True]},
            choices=[Choice("120", "Only right behind them",
                            "About a metre. Blood appears when they were "
                            "close to a wall and otherwise not at all -- the "
                            "most restrained setting, and the safest."),
                     Choice("300", "Across the room",
                            "About three metres, which is the wall of the "
                            "room you are standing in."),
                     Choice("700", "Almost always finds something",
                            "About seven metres. More marks, and the one "
                            "setting where an outdoor shot could put a mark "
                            "on the sky.")],
            confidence="experimental", touches="ram",
            help="How far past the person the shot is followed before the "
                 "game gives up looking for something to mark.\n\n"
                 "If nothing is found within this distance the game looks "
                 "straight down instead, so someone shot over open ground "
                 "still marks the ground under them."),
        Setting(
            prefix + "blood_ring", "Blood marks kept on screen", INT, 16,
            group, minimum=16, maximum=64, unit="marks",
            requires={prefix + "blood_splats": [True]},
            confidence="experimental", touches="data",
            help="Blood marks live in their own ring of sixteen, separate "
                 "from bullet holes and from explosion marks. One firefight "
                 "fills it, and then the oldest mark is dropped for each new "
                 "one. This raises the ring.",
            caution="Not yet played. The ring is built once when a level "
                    "loads, so this only takes effect on a fresh level, and "
                    "each extra mark is a real actor costing about 1.4 KB of "
                    "console memory."),
        Setting(
            prefix + "decal_terrain", "Marks on open ground", CHOICE,
            TERRAIN_DEFAULT, group, touches="data",
            confidence="experimental",
            choices=[
                Choice("stock", "Leave it alone",
                       "Every kind of mark projects onto open ground. On "
                       "Alpine Village this is what makes a grenade "
                       "expensive."),
                Choice("shrapnel", "Not explosion marks",
                       "Puts explosion marks back to what the unmodified game "
                       "did -- it never put them on open ground. Costs you "
                       "the explosion marks on Alpine Village's snow and "
                       "dirt."),
                Choice("shrapnel_blood", "Not explosion marks or blood",
                       "Also stops blood marks. The unmodified game never "
                       "placed a blood mark at all, so there is nothing here "
                       "you are losing that the original had."),
                Choice("every_mark", "No marks on open ground at all",
                       "Bullet holes too. This one DOES take away something "
                       "the original game showed you."),
                Choice("every_projector", "Nothing projects on open ground",
                       "Character shadows as well. One word, the biggest "
                       "saving, and the most visible change."),
            ],
            help="A frame-rate option, not a look-and-feel one, and it "
                 "only does anything on three levels.\n\n"
                 "Alpine Village, the multiplayer map Sandstorm and the "
                 "shooting range are the only levels on the disc that have "
                 "terrain. The other seventy-six have none at all, so "
                 "there this setting changes nothing whatsoever -- their "
                 "open ground is ordinary floor and marks it as "
                 "usual.\n\n"
                 "Where there IS terrain, a mark on it costs far more than "
                 "a mark on a wall. The game tests the mark against every "
                 "square of the terrain grid one at a time with no "
                 "shortcut -- eighty squares on Alpine Village, sixty-four "
                 "on each of the other two -- and then every square it "
                 "landed on redraws it again each frame until it "
                 "fades.\n\n"
                 "Walls, floors, crates, doors and every other ordinary "
                 "surface keep their marks on every setting. Only open "
                 "terrain ground is affected.",
            caution="WHICH ONE TO PICK: \"Not explosion marks or blood\" is "
                    "the usual answer. It gives the frame rate back on "
                    "Alpine Village and costs you only the explosion and "
                    "blood marks on its snow and dirt -- the unmodified "
                    "game never placed a blood mark on open ground at all, "
                    "and never put explosion marks there either, so "
                    "neither is something the original showed you. Marks "
                    "on the walls, buildings, crates and indoor floors are "
                    "untouched.\n\n"
                    "\"Nothing projects on open ground\" is the one to be "
                    "careful with: it switches the terrain check off "
                    "inside the engine's projector code itself, so "
                    "character shadows stop landing on open ground "
                    "too.\n\n"
                    "Not yet played, and the SIZE of the saving is "
                    "reasoned rather than counted. The shape of the work "
                    "is measured -- eighty squares tested one at a time "
                    "per mark, 1,821 instructions minimum on Alpine "
                    "Village, the mark redrawn once per square per frame "
                    "afterwards -- but twelve shrapnel marks' worth of "
                    "that testing is well under a millisecond, so the cost "
                    "must be in the redrawing, and that part was not "
                    "timed.\n\n"
                    "These are disc edits: they need the ISO written and "
                    "only take effect on a fresh level load."),
        Setting(
            prefix + "blast_puffs", "Let every impact raise its own dust",
            BOOL, False, group,
            requires={prefix + "impact_puffs": [False]},
            confidence="experimental", touches="ram",
            help="The game will only play one burst of impact dust every half "
                 "second, anywhere in the level, from a single timer it keeps "
                 "for the whole engine. That is why a grenade throws several "
                 "pieces of shrapnel, you hear all of them hit, and you see "
                 "one puff -- the sound is played before the limit is "
                 "checked and the dust after it.\n\n"
                 "This removes the limit.",
            caution="Not yet played. It is not specific to shrapnel: ordinary "
                    "gunfire gets its dust back as well, so a heavy firefight "
                    "raises far more of it than the game was built to draw."),
        Setting(
            prefix + "blast_decal_size", "How big each mark is", CHOICE,
            "1.25", group,
            requires={prefix + "blast_decals": tuple(range(1, 49))},
            choices=[Choice("1.0", "A bullet hole",
                            "Exactly the size of the marks your rifle makes."),
                     Choice("1.25", "Slightly larger"),
                     Choice("1.5", "Half again"),
                     Choice("2.0", "Twice"),
                     Choice("3.0", "Three times"),
                     Choice("4.0", "Four times")],
            confidence="experimental", touches="data",
            help="Shrapnel marks now have their own size again, separate from "
                 "bullet holes -- the explosion ring is built by its own code "
                 "rather than borrowing the one that makes bullet holes, so "
                 "raising this leaves your rifle's marks alone.",
            caution="Not yet played. It only takes effect on a freshly loaded "
                    "level, because the ring is built once when a level "
                    "starts."),
        Setting(
            prefix + "blast_stagger", "Spread the impact sounds out", BOOL,
            False, group,
            requires={prefix + "blast_decals": tuple(range(1, 49))},
            confidence="experimental",
            help="An explosion's impacts all land in the same frame, so three "
                 "of them arrive as one thud. This spaces them a fraction of "
                 "a second apart, which is what a spray of fragments striking "
                 "things actually sounds like.\n\n"
                 "The first strike still lands immediately, so the blast keeps "
                 "its punch; the others follow.",
            caution="Not yet played. It rides in the cheat file, so save a "
                    "fresh one and restart the emulator.\n\n"
                    "The game has 22 pooled impact actors and re-uses one per "
                    "material without checking whether it is busy. Holding a "
                    "strike back widens the window in which ordinary gunfire "
                    "on the same surface can take it over, from about one "
                    "frame to about fifteen, so in a heavy firefight the odd "
                    "deferred strike may be lost."),
        Setting(
            prefix + "blast_decals", "Shrapnel marks per explosion", INT, 0,
            group, minimum=0, maximum=48, unit="marks",
            confidence="experimental",
            help="Every frag, claymore and breaching charge throws scattered "
                 "marks across whatever is around it, the way shrapnel "
                 "actually pits a wall. Each mark is the mark for what that "
                 "fragment hit -- metal on metal, glass on glass -- the same "
                 "hole your rifle leaves on the same surface. The spread is "
                 "sized by the blast itself, so a claymore marks a wider area "
                 "than a breaching "
                 "charge, and marks only appear where there is something to "
                 "mark -- a grenade in the open leaves fewer than one in a "
                 "corridor. A fragment that lands on snow, dirt, grass or "
                 "any other surface your rifle leaves no hole in gets a "
                 "generic scorch instead of nothing, because an explosion "
                 "scars loose ground even where a bullet does not.\n\n"
                 "The pattern is fixed by WHERE the blast went off, so the "
                 "same grenade in the same doorway always pits the wall the "
                 "same way. Zero turns it off.",
            caution="Not yet played. It rides in the cheat file, so save a "
                    "fresh one after changing this and restart the "
                    "emulator.\n\n"
                    "It shares the explosion decal ring with nothing -- the "
                    "game's own grenade decal never fires -- but the ring "
                    "still wraps, so set \"explosion marks kept on screen\" "
                    "to at least this number, and ideally two or three times "
                    "it, or one blast erases the last one's marks."),
    ]

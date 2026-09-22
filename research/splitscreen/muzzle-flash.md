# The muzzle flash is not one of the split-screen branches

Every other split-screen effect this tool restores turned out to be one
instruction the game executes only when a second viewport exists, and the fix
was to nop it. Five are shipped: the impact decals, the impact emitter, blood,
rain and snow, and the flagged-emitter disable.

**The muzzle flash is not a sixth.** Searched and refuted rather than assumed.

## What was enumerated

`GameInfo::m_bIsSplitScreen` is a bool at `GameInfo+0x3A0` mask `0x200000`,
which is byte `0x3A2` bit 5. There are exactly **26** `lbu *,0x3a2(*)` sites in
the overlay; **20** extract bit 5, and the other six extract bit 0
(`m_bGameOver`) or bit 4 (`m_bUseMultiplayerDamageSystem`).

All 20 are accounted for: five are the shipped patches, the rest are sound
panning, actor relevance, two-player loop bounds, a split-only HUD pass, and
alternate effect paths. **None touches the muzzle flash.**

The one site inside the fire routine, the `beq` at `0x003F6944`, does not
suppress anything -- both arms reach the same
`Emitters[7]->vtable[0x90](1)`. The split-screen arm simply drops a
"shooter is the local player" test, because that test compares against
viewport 0's controller and is meaningless with two. Split screen gets MORE
flash there, not less. Nopping it would look plausible and do nothing.

## What the flash actually is

Measured from the property tables in a savestate, calibrated against the two
offsets already in `docs/PATCHES.md`:

======  ==============================  ===============================
offset  property                        what
======  ==============================  ===============================
0x394   `m_FPMuzzleFlashTexture`        object
0x4fc   `m_MuzzleScale`                 float
0x53c   `m_pMuzzleFlashEmitter`         the spawned flash actor
0x548   `m_pMuzzleFlash`                the class to spawn
======  ==============================  ===============================

The flash actor's `Emitters` array is at `actor+0x378` (data) `/+0x37c`
(count). Across three savestates, four weapons and both players:

* `Emitters[0]` and `[1]` carry bit 29 of the bools at `+0x64` --
  `m_iDrawWeaponPreDisplay` -- and the fire routine triggers them
  unconditionally. **These are the first-person flash.**
* `Emitters[2..6]` do not, and are skipped exactly when the shooter is the
  local player looking forward. Those are the third-person flash.
* `Emitters[k]+0x65 == 0` on every emitter in split screen, so neither
  `m_bHideInSplitScreen` nor `Disabled` is set. The `0x002375E0` patch family
  is irrelevant here.

## Why there is no native fix

**Nothing in the overlay reads `m_iDrawWeaponPreDisplay`.** Every
`lbu/lb *,0x67(*)` and every single-bit extraction of bit 29 was scanned
across `0x00100000..0x005B0000`: zero hits. The weapon pre-display pass that
honours the flag is driven from UnrealScript, not native code.

Corroborating: in a split-screen savestate the flash actor sits at the
THIRD-person muzzle, not the first-person one -- pawn z = -1685.0, first-person
weapon z = -1612.4, flash actor z = -1713.4. Something repositions it for the
first-person view and that something is the pre-display pass.

And it is not gated by the view-model flag. `g_bDrawFirstPersonWeapon` at
`0x006537BC` has exactly two accesses in the whole overlay, the writer at
`0x00302DA8` and the reader at `0x0030E318`, so the view-model patch cannot
have restored the flash as a side effect. The savestates confirm the
condition: `*(0x006537BC) == 1` and `g_bSplitScreen == 1` at once, which is
only reachable with `0x00302DA8` nopped -- the weapon visible, the flash
missing.

## Where to look next

The script side, on the weapon class: `SetEmitters`,
`AttachEmittersTo3rdWeapon`, `SetFPWeapons`, `LoadFirstPersonWeapon`,
`RemoveFirstPersonWeapon`, `PostRender`. `COMMONOFF.LIN` and `COMMON_SS.LIN`
are byte-identical, so any difference is a runtime branch rather than
authored data.

## A disassembler trap this uncovered

`dsll32 rd,rt,sa` followed by `dsrl32/dsra32 rd,rd,31` is a BITFIELD EXTRACT
of bit `31 - sa`. Printing those without the shift amount makes every such
pair look like the same test, and it is how a read of
`m_bUseMultiplayerDamageSystem` (sa=27, bit 4) becomes indistinguishable from
`m_bIsSplitScreen` (sa=26, bit 5). Any tool used on this overlay must decode
`sa` on the 64-bit shifts.

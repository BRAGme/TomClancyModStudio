# Rainbow Six 3 PS2 — per-map wave zones

Where this stands: the authored per-zone values **are** reachable and editable.
What is not finished is attributing a property block to a specific actor class,
which is what a per-map UI would need before it could label anything.

## What the disc actually places

Counted by decompressing every `OFF` level package and tallying the placement
names, not recalled:

* **24 of the 27 campaign mission parts** place deployment zones, 568
  `R6DZonePoint`s between them.
* The three with none are **Alpine Village A, Import/Export A, Penthouse A**.
* **Multiplayer places zero** wave actors across all twelve maps. Training
  places a few zone *points* but no wave actor to use them, which is the likely
  source of the older claim that it had zones.

This corrects a note that had named five levels as the only ones with zones.

## The package format

A `.LIN` level is ~107 cooked Unreal packages end to end, file version 123,
licensee 22. `tcps2/upackage.py` reads them.

**The recorded table offsets are relaid by the PS2 cooker and cannot be used.**
On Shipyard A both `exportOffset` and `importOffset` land in float data, whether
read package-relative or absolute. The *name* offset is still good.

That is enough, because Unreal serialises a property as

    compactIndex(nameIndex)  infoByte  [size]  value

so a property can be found by searching for its own name index followed by an
info byte — `0x22` for a four-byte int — with no export table involved.

## The authored values

Each spawner carries `m_iMinTerrorist` and `m_iMaxTerrorist` as int properties.
Shipyard A, validated by walking each property list to its terminator:

| site | max | the properties that follow it |
|---|---|---|
| ×2 | 5, 5 | `m_TerroristAITag`, several `m_Template`, **`m_eTerroristHunt`**, `m_eCoopTerroristHunt` |
| ×6 | 4,4,3,3,4,2 | `m_TerroristAITag`, one `m_Template`, **`m_eStoryMode`**, `m_eCoopStoryMode` |

Two hunt-gated spawners and six story-mode ones — and Shipyard A's name table
holds exactly two `R6DZoneWave` instances and six `R6DZoneRandomPoints`, so on
this level the split is exact.

## What editing is allowed

Values already authored can be rewritten in place: an int32 stays an int32, so
`lin.substitute`'s equal-length rule is satisfied.

**A value that is not authored cannot be added.** Unreal omits any property
equal to its class default, so a zone shipping the default count has no property
to rewrite, and inserting one would move every byte after it. This is why the
counts differ per level — on Shipyard A eight actors author a max but only five
author a min.

## What is still open

The export table names the classes, but it does **not** say where an object's
property bytes are. Its recorded serial offsets describe the layout *before*
cooking -- data sitting between the name table and the imports -- and that is
not where the data ended up:

* The offsets are perfectly contiguous, 80490..1070234 across 3144 boundaries
  with no gaps, and 1070234 is exactly the summary's `importOffset`. So they
  are internally consistent, just describing a layout that no longer exists.
* Summing every package's export sizes gives 18.8 MB inside an 11.8 MB file,
  and the packages sit back to back with no gaps, so the data cannot simply
  follow the tables.
* Searching 159000..200000 for a single base that makes blocks end exactly on
  their recorded sizes found nothing -- 0 of 60 probes at every offset.

So `export -> property bytes` is unsolved, and with it the last of the actor
attribution.

### Length-matching, and why it also failed

Tried, since the export table gives each wave actor's serial size:

* **Matching a block's length to a wave export's size.** For every validated
  `m_iMaxTerrorist` site, walk forward to the terminator for the end, then try
  every start in the preceding 800 bytes that walks to exactly that end, and
  keep one whose length equals a wave size. Shipyard A wants 221 or 226:
  **0 matches**.
* **Chaining blocks forward.** If blocks were contiguous, the end of one would
  begin the next. Walking from the terminator at +690010 parses **no** further
  block, so they are not contiguous there either.

So a serial size is not simply the length of a property list, and the data
region is not a plain run of them. Something frames or pads the objects, and
that framing is the real unknown.

### Per-map does not actually need any of this

Worth stating plainly, because it changes what is blocked. Per-map means per
`.LIN`, and each level is already its own file: editing the counts inside
`SHIPYARD_AOFF.LIN` touches Shipyard A and nothing else. Attribution is only
needed to name an individual zone, or to tell a wave zone from a story spawner
within one level.

What that would tune is every authored spawner count in a mission, wave and
story alike -- which is arguably the more useful knob, but it should be
labelled as what it is.

### The 148, explained

They were not misreads. **Every one of them is exactly `0`**, and zero occurs
nowhere else in the distribution:

| value | 0 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 10 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|
| sites | 148 | 36 | 83 | 89 | 57 | 32 | 5 | 4 | 2 | 2 |

The bound was the bug, not the locator. A count of zero sits beside
`m_bDontHearPlayer`, `m_bNotSurrender` and `m_aActionSpot` -- an individual
terrorist rather than a group spawner -- so it is authored, meaningful, and no
business of a numeric filter.

The real misreads are all rejected by structure alone. Of 498 candidates across
the campaign the `m_TerroristAITag` test keeps 458 and drops 40, and **all
eight implausible values are among the 40**. The 458 it keeps run 0..15. So no
plausibility bound is needed at all, and adding one would have thrown away 148
real values to catch eight that were already gone.

### Editing works end to end

Shipyard A, in memory, nothing written to a disc:

* 13 authored counts found, values 2..5
* scaled x2 -> all 13 changed, length identical
* handed back to `lin.substitute` -> 2 chunks re-deflated, container
  4,894,341 bytes before and after, and it decompresses to exactly the edited
  bytes

So per-map spawner tuning is done as a mechanism. What it tunes is every
authored count in one mission, wave zones and story spawners alike, which is a
per-map knob of real use even without per-zone attribution.

## The equipment wheel in split screen (open)

Rainbow Six 3 opens an equipment wheel when you hold L1. In split screen it
does not: L1 cycles one item per press instead, which costs time in a
firefight. What is known so far, so this is not restarted from nothing:

**The switch is named.** `COMMON.LIN`'s script package at `0x86a7f` exports
`m_bUseWheel` as a **BoolProperty** (export #388 of that package), with
`m_OpeningWheelSound` and `m_ClosingWheelSound` as ObjectProperties beside it.
That is a class member declaration, not an authored value.

**Ruled out:**

* It is not a config variable. `m_bUseWheel` does not appear in
  `R6GAMESETTINGS.INI` on any of the three Unreal-engine discs, nor in the
  Xbox build's `xboxdynamic.umd`. Nothing named `*Wheel*` or `*Split*` is a
  settable key on any of them, so there is no plain-text edit to make.
* It has no Function export named for it. Searching that package's 2,061
  `Function` exports for `wheel` returns nothing; the nearest relatives are
  `GadgetOne`, `GadgetTwo`, `ResetGadgetGroup`, `EquipWeapon`, `EquipHands`.
* The three byte patterns matching `EX_InstanceVariable + compact(388)` at
  `0x1dcab7`, `0x209c1d` and `0x209c5f` are **probably not** bytecode reads.
  Their neighbourhoods look like table data (runs of aligned u32s), none of
  the expected names sit within 900 bytes of them, and a three-byte pattern in
  a 5 MB package is around the rate chance alone predicts. Do not build on
  these without a real disassembler.

**The promising lead is native, not script.** Split-screen behaviour on this
disc runs through a flags word. At `0x00302D90` the routine that already
carries one of our patches does:

    00302d90  lw   $v0, -0x6ffc($gp)     ; a mode-flags global
    00302d94  or   $v0, $v1, $v0         ; ORed into
    00302d98  sw   $v0, 0x4e4($s1)       ; the object's flags word
    00302d9c  lw   $v0, 0x4e4($s1)
    00302da0  beqz $v0, 0x302dac
    00302da4  nop
    00302da8  sw   zero, -0x7f34($gp)    ; g_bDrawFirstPersonWeapon = 0
                                         ; (this is the patch we already ship)

So `s1+0x4e4` is a split-screen mode-flags word assembled from gp-relative
globals, and the first-person-weapon suppression we already undo is one
consumer of it. The wheel suppression is very likely another, either as a
second bit in the same word or a sibling store in the same routine.

**Two ways to finish it, either of which is bounded:**

1. A UnrealScript (UE2) bytecode disassembler for these packages. It would
   settle whether `m_bUseWheel` is read in script at all, and it would serve
   the weapon-pickup question too, which is stuck on the same missing tool.
2. Two savestates from a player -- one single-player, one split screen, both
   in a mission -- and `research/code/p2s.py diff` between them. The flag is a
   byte that differs between the two and does not differ between two states of
   the same mode. That is one afternoon's difference narrowed to a handful of
   addresses in one command, and it does not need any new tooling.

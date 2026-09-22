# The disc ships three builds of every level, and they do not explain the teammates

## What the disc actually contains

Rainbow Six 3 does not load one cooked file per map. The level-name buffer at
`0x006B95E0` carries a mode suffix, which savestates show directly:

| savestate | level buffer         | `g_bSplitScreen` |
| --------- | -------------------- | ---------------- |
| slot 20   | `Parade_aoff`        | 0                |
| slot 77   | `Island_a_ss`        | 1                |

and the archives match, for every map on the disc:

```
/ISLAND_AOFF.LIN     5,525,609     offline / single player
/ISLAND_A_SS.LIN     5,523,070     split screen
/COMMON.LIN          1,783,423     online
/COMMONOFF.LIN       1,780,692     offline
/COMMON_SS.LIN       1,780,784     split screen
```

This looked, at first, like the answer to why split screen builds a two-man
team: a separately cooked level with the AI operatives left out. It is not.
Both halves of that idea were measured and both are false.

## The level pair has identical content

`ISLAND_AOFF.LIN` and `ISLAND_A_SS.LIN` were decompressed and compared:

* **Name tables identical.** 5,305 distinct names each, nothing present in one
  and absent from the other, and every name used by the same number of
  packages in both.
* **Export tables identical.** 102 packages in each, 4,249 exports in each,
  4,143 distinct (class, object) pairs in each, the same count in every
  package, and no class whose total differs by even one.
* **Byte-identical for the first 4 MB.** The first difference falls at
  `0x003dcd2b`, well past the tables, in bulk data.

Actor placements are exports in a cooked Unreal level. A level missing an AI
operative would be missing an export. Neither build is missing anything the
other has, so the split-screen level is the same level: the ~2.5 KB it loses
is bulk data, which is what a memory-budget recook looks like. Note too that
the split-screen build is not uniformly smaller -- `AIRPORT_A_SS` is 1,183
bytes *larger* than `AIRPORT_AOFF`, `GARAGE_B_SS` 2,282 bytes larger. That
alone rules out "content removed".

## The script pair is literally the same file

The team code is UnrealScript, and it lives in COMMON, so the interesting
comparison is `COMMONOFF.LIN` against `COMMON_SS.LIN`:

```
COMMONOFF      5,094,061 bytes plain   sha1 635a7d60d1cf39fde13a6a9eb3c4cc87f6d58978
COMMON_SS      5,094,061 bytes plain   sha1 635a7d60d1cf39fde13a6a9eb3c4cc87f6d58978
COMMON         5,102,267 bytes plain   sha1 9dca587d57cbbdb2d56cd4a6aa3f4c492a4bad60
```

**The offline and split-screen script packages decompress to identical bytes.**
Only the online build differs, by 8,206 bytes. `R6RainbowTeam`,
`CreatePlayerTeam`, `RescureTeamStartingPoint`, `m_CoverSpots` and every
operative class name appear the same number of times in both.

So `CreatePlayerTeam` is the *same bytecode* whether you are playing single
player or split screen. It cannot be the case that Ubisoft shipped a different
team routine for split screen, because they shipped the same one.

## What this rules out, and what it leaves

Ruled out, by measurement rather than by argument:

* the split-screen level is missing the operative actors -- it is not;
* the split-screen level is missing the rescue starting point or cover group
  -- it is not, the exports are identical;
* the split-screen script builds a smaller team because it is a different
  script -- it is the same script, byte for byte.

What remains is that the difference between the two modes is **entirely at
runtime**: the same script, reading the same level, taking a different path
because of `g_bSplitScreen` and the gametype. That puts the cause back in the
overlay, and it sharpens the one hypothesis that was never actually tested.

## The one per-mode number in the overlay is the audio stream cap

There is exactly one constant in the whole overlay that differs by mode, at
`0x00472160`:

```
lw    $a0, -0x7050($gp)   ; g_bSplitScreen at 0x006546a0
addiu $v0, $zero, 3
addiu $v1, $zero, 6
jr    $ra
movz  $v0, $v1, $a0       ; delay slot: split ? 3 : 6
```

An earlier attempt (`split_stream_budget`, withdrawn) read this as the level
streaming budget and tried to give split screen the full six. It crashed with
`PC: 0xffffffff`, and the explanation recorded at the time -- "a returned value
was a size another site trusted" -- is **not supported by the code**. The one
caller, `0x004ca230`, does nothing but gate it behind two readiness flags and
forward it.

Following it outwards identifies it properly.

`0x004ca230` has two callers. The first, `0x004e3490`, is the interesting one:

```
004e34a4  jal   0x4ca230           ; limit = 3 or 6
004e34b0  lw    $v1, 0xa60($at)    ; active count at 0x006f0a60
004e34b4  sltu  $v1, $v1, $v0      ; active < limit ?
004e34b8  bnez  $v1, 0x4e35fc      ; yes -> return 0
...                                ; no  -> format a message, return 1
```

`0x006f0a60` is a plain counter: three writes, `+1` at `0x004e3444` paired
with `sw $v0(=1), 0x40(obj)` and `-1` at `0x004e31dc` and `0x004e369c`, each
paired with `sw $zero, 0x40(obj)`. Acquire and release of a fixed pool, with
`0x40(obj)` as the in-use flag.

So `0x004e3490` runs **only when the pool is full**, builds a string in an
0x840-byte stack buffer, and returns 1. It is an error reporter. The strings it
uses settle what the pool is:

```
0x005f1ded  '->Res 0x%x cannot be started because '
0x005f1e20  '0x%x'
0x005f1e28  ', 0x%x'
0x005f1e30  ' and 0x%x'
0x005f1e60  'SStream Error: Not enough memory to create streaming source.'
0x005f1d00  'ND_fn_eSynchStreamAsyncSnd.'
0x005f1ec0  'TImaAdpcm: IMA-ADPCM version seems to be too old (res id 0x%x).'
```

`0x00472160` is the cap on **simultaneous streaming audio sources**. Six in
single player, three in split screen, because two viewports leave less memory
for sound. The message is the engine naming which resources hold the slots when
a new one cannot start.

This has nothing to do with AI teammates. It also explains the crash: raising
split screen's cap to six asks the audio system to create streaming sources it
has no memory for, which is the failure the string above is printed for.

**`split_stream_budget` is withdrawn permanently**, and the sixth explanation
is now refuted like the other five -- not by a failed test, but by finding out
what the number actually controls.

## Where the teammate question stands

Every explanation tried so far is accounted for:

| # | explanation | verdict |
| - | ----------- | ------- |
| 1 | the bytecode edit is wrong | refuted -- a 4-byte version hangs identically |
| 2 | the operative classes will not load | refuted -- Trieste builds the same operatives and runs |
| 3 | the gametype is wrong | refuted -- Practice hangs too |
| 4 | the spawn point is wrong | refuted -- changing `m_CoverSpots[0]` changed nothing |
| 5 | split screen has a smaller streaming budget | refuted -- that number is the audio stream cap |
| 6 | the split-screen level or script is missing content | refuted -- identical name tables, identical export tables, identical script bytes |

What is left is narrow and worth stating plainly: the two modes run the **same
script** over the **same level data**, and diverge only on runtime state --
`g_bSplitScreen`, the gametype, and whatever the team code reads from them. The
next honest step is not another patch but a runtime comparison: the same map,
loaded once in single player and once in split screen, with the team object
read out of both savestates. That is what to do next.

## Incidental, but worth writing down

The property is spelled **`m_bRescureRainbow`** in the package name table
(capital R), while `MAPS/TRIESTE_A.INI` writes `m_brescureRainbow=true`
(lower-case r). Trieste works on the retail disc, so the engine's INI key
matching is case-insensitive, confirmed by the disc against itself.
`tcps2/rserescue.py` copies Trieste's spelling exactly for that reason.

## Addendum: the rescue flag was tested, on the worst possible map

`split_rescue_flag` was built and play-tested on **Alpine Village** split
screen. It wedged: one attempt froze mid-load and took PCSX2 down with it, a
second reached the familiar infinite load. No bytecode was patched -- the only
change was one line of INI text -- which is itself worth recording, because
every previous wedge involved a bytecode edit and this one did not.

But the map was a bad choice, and the choice was mine.

Every cooked mission level was scanned for the name `m_aStartingPoint`. In a
cooked Unreal package a property name only reaches the name table when some
object serialises that property, and a property only serialises when it
differs from its class default -- so the name's presence means at least one
actor authors a starting point, and its absence means none does.

**24 of 27 carry it. The three that do not are `ALPINES_A`,
`IMPORT_EXPORT_A` and `PENTHOUSE_A`** -- exactly the three this tool already
records elsewhere as placing zero deployment zones. They are a structurally
thinner trio, and Alpine Village A is one of them.

So the honest reading is narrow:

* the name does **not** explain Trieste -- 24 maps have it and only Trieste
  builds AI operatives, so it is not the distinguishing feature;
* but asking a map with no authored starting point to run the rescue arm is
  asking it to place operatives nowhere, and that is a sufficient explanation
  for the Alpine Village wedge on its own;
* therefore the Alpine Village result says nothing about the other 23 maps,
  and the flag is **not refuted**.

The selector now skips those three by name, so the same mistake cannot be made
twice. Island Estate is the map to test next: it authors a starting point, and
it is the map the original hand-off named before Alpine Village was chosen for
an unrelated reason (a single-player/split-screen savestate comparison).

## Resolved: it was one jump

`R6RainbowTeam.CreatePlayerTeam` was read whole, from the package at plain
`0x086a7f`, script block `0x1470a3`, disk 1346 / memory 1775. It is a fork:

```
0x0150: CreateTeamMember(0, p_playerStartingPoint, True, PC)      ; player 1
0x0162: JumpIfNot(-> 0x357, Level.Game.m_bIsSplitScreen)          ; the fork
0x01c4:   CreateTeamMember(1, m_CoverSpots[0], True, PC, ...)     ; player 2
0x01f9:   if (aMissionDescription.m_bRescureRainbow)              ; Trieste only
0x02b9:     CreateTeamMember(2, m_CoverSpots[1], False, PC, False)
0x0300:     CreateTeamMember(3, m_CoverSpots[2], False, PC, False)
0x0354:   Jump(-> 0x688)                        ; <-- over the whole AI section
0x0357: ...single player creates AI members 1, 2 and 3...
0x0688: end
```

Split screen builds player 2 as member 1 and then jumps to the end of the
function. **That unconditional `Jump` at memory `0x0354`, disk `0x147326`,
bytes `06 88 06`, is the entire reason there are no AI teammates.** Not a
flag, not a budget, not missing content.

It also explains six failures at once. Every previous attempt retargeted the
`JumpIfNot` at memory `0x01f9`, disk `0x14721d` -- forcing the **rescue** arm.
That arm spawns at `m_CoverSpots[1]` and `[2]`, filled from
`RescureTeamStartingPoint`, and carries no fallback when they are null. The
single-player arm does carry one:

```
0x04d1: if (... && m_CoverSpots[1] != None)
0x054f:   CreateTeamMember(2, m_CoverSpots[1], False, PC, bTerroHunt)
0x056d: else CreateTeamMember(2, teamStartingPoint, False, PC, bTerroHunt)
```

`teamStartingPoint` is assigned at `0x0028`/`0x0036` from the function's own
parameters, so it always exists. Forcing the rescue arm on a map with no
authored starting point asks it to spawn operatives nowhere -- which is the
wedge, and why Alpine Village reproduced it with one line of INI and no code
patched at all.

`tcps2/rsesquad.py` retargets the `0x0354` jump to `0x0420` instead: past the
`m_bMissionPrice` check (whose `RemoveMember` would delete player 2, the most
recently added member, on maps where Price is absent) and into the arm that
creates members 2 and 3 with the null-safe fallback. Two bytes, token width
unchanged, `ScriptSize` untouched.

It goes to all three COMMON files on a stronger argument than the muzzle fix
has: memory `0x0354` is only reachable through the `m_bIsSplitScreen` branch
at `0x0162`, so in single player and online the instruction is not merely
harmless, it is never executed.

Untested on hardware at the time of writing.

## Tested: the jump was right, the load is the wall

`split_squad` was built and play-tested on Alpine Village split screen. It
wedged -- and it is the first attempt that got far enough to leave evidence.

**The AI operatives start being built.** Comparing a working split-screen
savestate against the wedged one:

| string | working SS | wedged SS |
| --- | --- | --- |
| `R6RainbowLoiselle` | 4 | **8** |
| `R6RainbowWeber` | 4 | **7** |
| `R6RainbowPrice` | 27 | 31 |

So the retargeted jump lands correctly and the team-building code runs. Every
previous attempt produced byte-identical hang states with no such movement.

**Where it stops.** The wedged state has the EE parked in the kernel
(`pc = 0x80001578`) with two game return addresses on the kernel stack:
`0x00161854`, which is the UnrealScript VM's opcode dispatch
(`jr $v1` through a table at `0x005d5340`), and `0x00148f70`, a virtual call
at vtable+0x7c inside a list walk. The hang is inside script execution.

**What it hung on.** `CreateTeamMember` (block `0x146058`, disk 2977 / memory
3840) resolves the pawn class with a switch on the member index, and every arm
is a dynamic load:

```
case 0/1: DynamicLoadObject("R6Characters.R6RainbowPrice[Winter]", Class)
case 2:   DynamicLoadObject("R6Characters.R6RainbowLoiselle[Winter]", Class)
case 3:   DynamicLoadObject("R6Characters.R6RainbowWeber[Winter]", Class)
```

Members 0 and 1 load the Price class, which split screen already has -- which
is precisely why player 2 is created successfully and the AI are not. Members
2 and 3 pull two character classes out of the `R6Characters` package during
level init, and that is the load that never completes. It is the same "IOP
frozen re-reading one chunk" signature this project has been chasing since the
beginning, and it finally has a cause rather than a symptom.

`bUseWinterMesh` is computed at `0x0072` from `m_Skins.missionTeam == 11 || ==
12`, and Alpine Village's INI sets `missionTeam=SKIN_WinterCamo` (12), so the
Winter variants are the ones requested.

**Why Trieste is the exception.** Its cooked level references `R6Characters`
**39** times; Alpine Village's references it 15 and Island's 17. Trieste ships
with the operatives its rescue arm needs. Other maps do not, and no amount of
code routing conjures them.

So the problem has changed shape, which is progress. It is no longer "why does
the code not run" -- the code runs. It is "how do the character classes become
resident in split screen before the team is built". That is an asset question,
and the honest options are narrow: preload them, or accept that this works
only on maps that already carry them.

`split_squad` stays in the tool, defaulted off, because the diagnosis is worth
keeping and the edit is correct as far as it goes.

## CORRECTIONS

Two claims made earlier in this document are wrong and are retracted here
rather than quietly edited, because both were stated confidently and both were
used to justify decisions.

### 1. "Trieste's level references R6Characters 39 times" — RETRACTED

The counts were real; the reading was not. **Every one of Trieste's 39 hits is
the substring inside `R6Characters_T`**, which is a TEXTURE package, not the
character package:

```
TRIESTE_A_SS.LIN     R6Characters=39   of which R6Characters_T=39   bare=0
ALPINES_A_SS.LIN     R6Characters=15   of which R6Characters_T=13   bare=2
ISLAND_A_SS.LIN      R6Characters=17   of which R6Characters_T=15   bare=2
```

Trieste has **zero** bare references where Alpine Village and Island have two
each — the opposite of what was claimed. `R6RainbowLoiselle` occurs 0 times in
all three. No level on the disc carries an operative class: `R6Characters` is
a single cooked package embedded in `COMMON*.LIN` at plain `0x4151a6`
(`0x4171b4` in `COMMON.LIN`), 5,427 bytes, 171 names / 103 imports / 84
exports, and it exists nowhere else. So "Trieste ships with the operatives its
rescue arm needs" is false. Trieste ships nothing of the kind.

What is actually Trieste-unique is the INI flag and its cover data
(`m_CoverGroup` sites: Trieste 28, Alpines 11, Island 0).

### 2. "24 of 27 maps author m_aStartingPoint" — RETRACTED

The name is in 48 of 54 level name tables, but its **encoded name index occurs
in no package body at all**. It is a dead name-table string. No actor on any
map authors a starting point, so the name's presence or absence distinguishes
nothing, and it cannot explain the Alpine Village wedge. `RescureTeamStarting
Point` does not exist as a class on the disc either (0 occurrences in all 54
builds).

The three-map exclusion in `rserescue` is kept, but its stated reason is now
the honest one: Alpine Village is simply the map that was tested.

## What the wedge actually is

Not an infinite load. **The console is parked in the engine's fatal error
handler, and the wedged savestate still holds the message.** The retained
error buffer at `0x005b9070`:

| slot | contents |
| --- | --- |
| 1 (Alpine SP, works) | `General protection fault!` — the pristine default |
| 2 (Alpine SS stock, works) | same |
| 91 (Trieste SS with AI, works) | same |
| 92 (Parade SP, works) | same |
| **3 (Alpine SS wedged)** | **`Script serialization mismatch: Got 0, expected -184945406`** |

Only slot 3 carries FORMATTED linker errors rather than bare format strings --
`failed to alloc 50331656 bytes` (`0x03000008`, a length read from garbage),
`SERIAL SIZE MISMATCH`, `BAD IMPORT INDEX`. The denominators in the unformatted
variants match `R6Characters` exactly (103 imports, 171 names, measured from
disc).

So the package load *starts*, the deserializer desyncs, `UStruct::Serialize`
reads a garbage `ScriptSize`, and `appError` parks the EE. Every "infinite
load" this project has chased may be this, and it is checkable in one command
on any future wedge.

`DynamicLoadObject` is not the wall: `LoadMissionRainbowSkins`, called
unconditionally from `CreatePlayerTeam` in BOTH modes, already does four
`R6Characters` class loads (`R6RChavesC`, `R6RPriceC`, `R6RLoiselleC`,
`R6RWeberC`) on every map. Retail split screen loads out of that package on
every level init.

## The better explanation for the squad wedge

`CreateTeamMember` ends:

```
0x0ead: if (Level.Game != None && Level.Game.m_bIsSplitScreen)
0x0ede:     m_iMemberCount = 1          <-- hard RESET, not an increment
0x0ee8: else m_iMemberCount++
```

The rescue arm compensates by setting the count explicitly around each call
(`0x020b`=2, `0x02cf`=3, `0x0317`=4, `0x034d`=1). **The single-player arm at
`0x0420` does not.** So retargeting `0x0354 -> 0x0420` runs AI creation with
the count stuck at 1: both operatives are written into `m_Team[1]`,
overwriting player 2, and `iSpawnTry` (assigned `m_iMemberCount` at mem
`0x0067`) starts from 1 instead of 0.

That is a far better fit for a serialization fault than a missing asset, and
it means the next attempt is about making the count track the members, not
about preloading anything.

Also ruled out without booting: retargeting `0x0354 -> 0x020b` (the rescue
arm) makes `0x0688` unreachable, because that arm falls through to `0x0354`
which would now jump back to `0x020b`. Infinite loop. Do not.

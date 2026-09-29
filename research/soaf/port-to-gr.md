# Porting Sum of All Fears content into Ghost Recon (PS2)

**Verdict: plausible, and better founded than any other route to multiplayer
SOAF content.** The two discs are the same engine with the same asset formats;
248 files are already byte-identical between them. The work is repacking and
one texture-version conversion, not reverse engineering.

This supersedes LAN as the thing to chase — see §4.

---

## 1. Why this came up

SOAF has co-op and multiplayer *content* (6 `MP*.MIS` maps, 13 `.GTF` game
types, `MP Actor Files`, `.KIL` kit restrictions) and no way to reach it: no
lobby screens exist as data, and its transport is i.Link, which needs two real
PS2s and a FireWire cable (`network.md`). On PCSX2 that is unreachable in
principle, not merely hard.

Ghost Recon and Jungle Storm, on the same engine, already have working split
screen and (Jungle Storm) online, and this project already patches both
heavily. So: move the content to the engine that can play it.

## 2. The formats are the same

File-type census across the two archives — **every type is shared, none is
exclusive to either disc**:

| ext | SOAF | GR | | ext | SOAF | GR |
|---|---|---|---|---|---|---|
| `.ATR` | 479 | 1193 | | `.MIS` | 23 | 46 |
| `.RSB` | 218 | 638 | | `.MAZ` | 12 | 38 |
| `.BMZ` | 331 | 307 | | `.ENV` | 12 | 39 |
| `.CHA` | 251 | 321 | | `.AOL` | 12 | 36 |
| `.KIT` | 132 | 141 | | `.MOL` | 12 | 36 |
| `.POB` | 131 | 141 | | `.POL` | 12 | 36 |
| `.QOB` | 121 | 148 | | `.SHT` | 12 | 36 |

SOAF holding exactly 12 of `.MAZ` / `.ENV` / `.AOL` / `.MOL` / `.POL` / `.SHT`
says a level is a named set of those files, one set per level, 12 levels.

**Header comparison, with Ghost Recon's files LZO-decompressed first:**

| ext | verdict |
|---|---|
| `.MAZ` | **same** — both start `f6 ff ff ff`, then per-level counts |
| `.ENV` | **same** — both plain `<EnvironmentFile` |
| `.MOL` | **same** — `04 00 00 00 01 00 00 00`, then a size |
| `.SHT` | **same** — `4a 0c 3a 40 00 00 80 3f`, then a size |
| `.MIS` | **same** — both plain `<MissionFile>\r\n\t` |
| `.QOB` | **same** — `0b 00 00 00 "BeginModel"` |
| `.CHA` | **same** — `15 00 00 00 01 00 00 00 ...` |
| `.AOL`, `.POL` | **same format** — only the leading size word differs, then `0a/09 00 00 00  08 00 00 00 "Vers..."` identically |

> **Trap worth recording.** Compared naively this table reads "everything
> differs". Ghost Recon stores most archive members LZO-compressed behind a
> 9-byte header (`u32 packed size`, `u32 chunk size` — `0x4000` throughout —
> and a byte), while `soafimg.read_file` already decompresses. The first pass
> compared SOAF's *decompressed* bytes against Ghost Recon's *raw* bytes and
> concluded the formats were incompatible. They are not. Decompress with
> `tcps2.rselzo` before comparing anything across these two discs.

## 3. They already share assets

Of 2,420 SOAF files and 4,004 Ghost Recon files, **677 share a filename and 248
are byte-for-byte identical**, including `203_ROUND.QOB`, `AKMS.QOB`,
`BEERCAN.QOB`, `ARROW.RSB`, `AT4_BLAST.POB` and the `BILLBOARD_EFFECT*.BMZ`
family. Red Storm shipped one asset library across both titles.

So a SOAF level dropped into `GR.IMG` would already find a large part of its
supporting cast present.

## 4. What the port actually requires

Known and tractable:

1. **Texture version.** SOAF ships `.RSB` **version 8**, Ghost Recon version 6;
   v8 is v6 with seven bytes inserted after the height, putting pixels at
   `+35`. The tool already decodes both (`tcps2/rsb.py`, `research/soaf/soafart.py`),
   so this is a rewrite of a header, not a decode problem.
2. **Archive record size.** SOAF uses 40-byte records, Ghost Recon 48.
   `tcps2/vokes.py` handles both already (`REC_SIZES`).
3. **Compression.** Members must go into `GR.IMG` LZO-packed with the 9-byte
   header. `tcps2/rselzo.py` has `compress` and `repack`.
4. **Registration.** The level has to be reachable — Ghost Recon's mission list
   and whatever indexes `.MAZ`/`.ENV` by name.

Not yet established, and each could sink it:

* Whether the `.MAZ` payload past the shared magic is version-compatible, or
  merely the same *shape*. Same first words is necessary, not sufficient.
* Whether SOAF levels reference shaders, materials or effect ids that Ghost
  Recon's build does not define.
* Whether Ghost Recon's level loader hard-codes its own level names.
* Whether the 429 same-named-but-differing files are benign (different content,
  same format) or represent incompatible revisions of shared assets. That
  number is worth an afternoon on its own: if `ICA_US_DEMOLITION.CHA` is
  identical but some other shared name is not, the differences tell you what
  changed between the two builds.

## 5. The first probe

Take the smallest SOAF level set, convert its `.RSB`s to v6, LZO-pack the set,
add it to a copy of `GR.IMG` under a Ghost-Recon-style name, and point one
existing Ghost Recon mission at it. If it loads at all — even to a broken or
untextured scene — the format question is answered and everything after that is
detail. If the loader rejects it, the `.MAZ` payload is where to look first.

Do this on a copy. `GR.IMG` is 1.5 GB and the tool's revert only restores what
it wrote.

## 6. The cheap adjacent win, unrelated to porting

SOAF's own `.GTF` game types are gated by a single digit:

| `LobbyCfg` | meaning | files |
|---|---|---|
| 1 | single player | `(SP) FIREFIGHT`, `(SP) LONE WOLF` |
| 2 | co-op | `(COOP) FIREFIGHT`, `(COOP) RECON` |
| 3 | solo multiplayer | `(SOLO) CATS_AND_MOUSE`, `HAMBURGER HILL`, `LAST MAN STANDING`, `SHARPSHOOTER` |
| 4 | team | `(TEAM) DOMINATION`, `HAMBURGER HILL`, `LAST MAN STANDING`, `SEARCH AND RESCUE`, `SIEGE` |

Exactly two game types carry `LobbyCfg` 1, and the shell has
`QUICK_MISSION_PS2` and `QUICK_MISSION_PARAMETER_PS2` screens — consistent with
Quick Mission listing the `LobbyCfg == 1` types. If that is the filter, rewriting
another type's digit to `1` should make it appear there: a single character,
length-preserving, exactly the kind of edit `tcps2.transforms` already does
safely.

**Untested.** It assumes the filter is `LobbyCfg` and that a co-op game type
can run with one player. Both are cheap to find out and neither risks the disc.

---

## 7. The first probe, built (2026-09-28)

Built and ready to boot; **not yet run**, so this section records method and
measurements, not an outcome.

**What was swapped.** Sum of All Fears' `TRAINING` level set replaced Ghost
Recon's `M01_CAVES` inside a copy of the Ghost Recon ISO. `M01_CAVES` was
chosen because it is the first campaign mission -- one menu selection to reach
-- and because its slots fit:

| file | GR M01_CAVES slot | SOAF TRAINING, LZO-packed | |
|---|---|---|---|
| `.MAZ` | 496,120 | 401,587 | in place |
| `.MOL` | 504,107 | 350,239 | in place |
| `.SHT` | 432,283 | 327,914 | in place |
| `.AOL` | 65,692 | 11,334 | in place |
| `.POL` | 1,019 | 2,215 | **relocated** (+1,196) |
| `.ENV` | 510 | 245 | in place |

SOAF's files are stored decompressed, Ghost Recon's LZO-packed, so each was
packed with `tcps2.rselzo.compress` first (38 s for the `.MAZ`; the whole set
is about 100 s in pure Python). Packed ratios ran 19-53%.

Only the six level-asset files were replaced. `M01_CAVES.MIS` is **untouched**,
so Ghost Recon's own mission script, actors and objectives run on top of Sum of
All Fears' geometry. That is deliberate: the question this probe asks is
whether the engine loads the level at all, and leaving the mission alone keeps
one variable in play instead of three.

**Verified after writing:** all six files read back and decompress to their
original lengths and leading bytes (`.MAZ` `f6 ff ff ff`, `.ENV`
`<EnvironmentFile`, and so on), and `GR.IMG` still lists all 4,004 files.

**Level fit across the whole disc**, for reuse: every Ghost Recon level fits
SOAF's `TRAINING` except for `.POL`, which overflows everywhere. The cheapest
targets are `M06_CASTLE` (+776 bytes), `M01_CAVES` (+1,196), `M09_SWAMP`
(+1,208) and `D03_DEPOT` (+1,212).

**What the result will mean:**

* *Loads, recognisable geometry* -- the formats are compatible and the rest is
  detail: textures, collision, spawn points, then the mission script.
* *Loads, but garbled or untextured* -- the `.MAZ` is being parsed, so the
  container is right and the difference is in what it references. Good outcome.
* *Hangs or drops back to the menu* -- the `.MAZ` payload past the shared
  header is not version-compatible after all, and §2's "same format" reading
  was too optimistic. That is where to look first.

One caveat found while preparing it: these level files reference almost nothing
by filename -- a scan turned up three references in the whole set, of which one
(`M09_BANK_SKYBOX.POB`, named in the `.ENV`) is absent from Ghost Recon. So
asset binding is by index or some other handle, and how SOAF's indices land in
Ghost Recon's tables is unknown. That is a likely source of garbling and cannot
be predicted from the outside.

The probe disc is `E:/PS2 Games/GR_SOAF_probe (throwaway).iso`, built from an
untouched copy. Nothing on the real discs was modified.

### 7a. Result: stuck at loading -- and why the probe was under-built

Booted 2026-09-28. **The mission hangs on the loading screen.** It does not
crash or fall back to the menu; it simply never finishes.

Before blaming the format, the probe itself was wrong, and the mistake is
instructive. **A level is about fourteen files, not six.** The six swapped were
the ones sharing an extension between the two discs, which is not the same
thing as the level's full set:

| | Ghost Recon `M01_CAVES` | SOAF `TRAINING` |
|---|---|---|
| swapped | `.AOL` `.ENV` `.MAZ` `.MOL` `.POL` `.SHT` | same six |
| **left mismatched** | `.BMZ` **2,153,061** | `.BMZ` **2,638,992** |
| also present, GR only | `.PAK` `.RSB` `.POB` `_GRASS.BMZ` `_SKY.BMZ` `_SKY.POZ` | -- |
| also present, SOAF only | -- | `.BMB` `.BMH` `.COZ` `.SDP` `.TOE` `.XML` |

So the disc booted Sum of All Fears' geometry against Ghost Recon's 2 MB
texture bundle, its `.PAK`, its sky and its grass. Geometry that indexes into a
bundle it was not built for is reason enough to hang, with nothing wrong with
the `.MAZ` at all.

**The `.MAZ` format is, separately, looking fine.** Compared 32 words deep,
Sum of All Fears and Ghost Recon agree on structure: magic `-10`, then a
repeating four-word record whose fourth word is always `1`, at every matching
index in both files. The container is the same; §2's reading holds for this
file at least.

**What §2 got wrong.** "Every file type is shared, none exclusive to either
disc" was drawn from the twenty-eight most common extensions. It does not hold
per level: `.BMB`, `.BMH`, `.COZ` and `.SDP` are SOAF's level packaging and
`.PAK` is Ghost Recon's. The *asset* formats match; the *level packaging* does
not, and that is the harder half.

**Next probe, if this is picked up again.** Swap the full overlapping set --
above all `.BMZ`, the texture bundle -- and find out what Ghost Recon's loader
does about the files Sum of All Fears has no counterpart for. Two things to
settle first, both static:

1. What `.BMZ` actually is in each game, and whether SOAF's packs into Ghost
   Recon's 2,153,061-byte slot at all.
2. Whether Ghost Recon's loader requires `<level>.PAK`, which Sum of All Fears
   never ships. If it does, and new entries cannot be added to `GR.IMG` (the
   writer replaces files, it does not grow the entry or name tables), then a
   level port needs a donor level whose own `.PAK` is acceptable, or the
   loader patched not to want one.

**A dead end that was tried:** reading the hung PC out of the savestate. A scan
of `PCSX2 Internal Structures.dat` for values in Ghost Recon's text range
returns page-aligned recompiler bookkeeping (`0x230000`, `0x5b0000`, ...), not
program counters, and mapping those to symbols produces confident nonsense.
Getting a real PC needs PCSX2's `cpuRegisters` layout for this build; do not
repeat the scan-and-symbolise approach.

## 8. The two blocking questions, answered (2026-09-28)

### 8a. `.PAK` is not a level requirement

`.pak` appears in Ghost Recon as four literals -- `common.pak`, `menu.pak`,
`loading.pak`, `action.pak` -- and one suffix at `0x0058C1EF`, appended to a
built name at `0x0051B76C`. All of it belongs to a single function,
`LoadingTexturePak__12UITextureMgrFiPCc` (`0x0051B660`), whose callers are:

    IkeRootContainer::HandleGameStateChange  (x3)
    IkeUIMgr::Initialize (x2), PreInit, Create
    SPBriefing::SetVisible

Every one is a UI or briefing path. `<level>.PAK` is loading-screen and
briefing artwork, **not level data**, so a ported level does not need a `.PAK`
counterpart and Ghost Recon's own can stay in place. This was the question that
could have sunk the whole idea -- new entries cannot be added to `GR.IMG`,
since the writer replaces files and does not grow the entry or name tables.
It does not sink it.

### 8b. `.BMZ` is a texture bundle, same format, and it fits

Header, both games:

| word | SOAF `TRAINING` | GR `M01_CAVES` | |
|---|---|---|---|
| 0 | 1250 | 694 | texture count |
| 1 | **-4** | **-4** | version, identical |
| 2 | 72 | 40 | header or record size, **differs** |
| 4,5 | 256, 256 | 512, 512 | dimensions of the first texture |
| 16 | **0x20000006** | **0x20000006** | identical marker |

Same family, same version word, same per-entry marker; word 2 differs and is
the one thing to resolve if entries ever need rewriting rather than wholesale
replacement.

Packed with `rselzo`, SOAF's `TRAINING.BMZ` is **2,095,691** bytes against
`M01_CAVES.BMZ`'s **2,153,061**-byte slot, so it **fits with 57 KB spare**.
Ten of Ghost Recon's 117 level `.BMZ` slots would take it. (404 s to compress
in pure Python -- cache the result.)

### 8c. Probe 2, built

`E:/PS2 Games/GR_SOAF_probe2 (throwaway).iso`. Same swap as §7 plus the texture
bundle -- seven files now, `.MAZ` `.MOL` `.SHT` `.AOL` `.POL` `.ENV` `.BMZ`,
all into `M01_CAVES`. Only `.POL` relocates; the rest fit in place. All seven
read back and decompress to their original lengths. `GR.IMG` still lists 4,004
files. `M01_CAVES.MIS` remains Ghost Recon's, as before.

Still mismatched, and the next things to suspect if it still hangs: Ghost
Recon's `M01_CAVES.RSB`, `.POB`, `_GRASS.BMZ`, `_SKY.BMZ` and `_SKY.POZ`, none
of which Sum of All Fears' `TRAINING` has a counterpart for, and Sum of All
Fears' `.BMB`, `.BMH`, `.COZ`, `.SDP`, `.TOE` and `.XML`, which have nowhere to
go in a Ghost Recon level.

## 9. Probe 2 also hangs -- what the savestate says, and a controlled test

### 9a. Probe 2 result

Adding the texture bundle changed nothing: **still stuck on the loading
screen.**

### 9b. The savestate, read properly

`PCSX2 Internal Structures.dat` is a tagged stream. The `cpuRegs` tag sits at
`0x142` in a 32-byte field; the GPRs follow at `+0x20`, sixteen bytes each, then
`HI`, `LO`, 32 `CP0` words (confirmed by `Status=70030c11`, `PRId=2e20` -- the
R5900), then `sa`, `IsDelaySlot`, and the **PC at tag+`0x2C8`**. (The next tag,
`Cycles`, is at `0x117C`.) This replaces the scan in §7a, which read
recompiler bookkeeping.

The snapshot is self-consistent -- `$t9` is the callee, `$ra` and the PC are
both its return point:

    main+0x3a0
     > IkeGameMgr::Update+0x34
        > RSInputMgr::Update+0x6c
           > RSInputImpl::Update+0x3dc          PC = 0x0054E52C
              > IkeStateMgr::InSplitScreenMode  (vtable slot 0xA0, just returned)

**The main loop is alive,** polling input every frame on the loading screen.
Nothing crashed and nothing is spinning inside a level parser. The load is
waiting on something that never completes. One snapshot is one thread at one
instant, so the loader may be blocked on another thread -- but this rules out
the simplest reading of "the format is wrong".

Also visible: `$sp = 0x07FFFB20`, above 32 MB, so this PCSX2 has
**128 MB RAM mode** enabled. Stock Ghost Recon boots under it; noted as an
uncontrolled variable, not a suspect.

### 9c. A concern that was checked and refuted

The control disc showed `M01_CAVES.POL` stored **raw**, and the probes had
LZO-packed every file written. If the loader did not sniff per file, a packed
`.ENV` or `.POL` would be garbage to it. Across every Ghost Recon level:

| | LZO | raw |
|---|---|---|
| `.MAZ` `.MOL` `.SHT` `.AOL` `.BMZ` | all | none |
| `.POL` | 16 | 20 |
| `.ENV` | 8 | 31 |

Both `.POL` and `.ENV` ship both ways, so the loader must detect compression
per file. Packing them was harmless; the rest are always LZO, so packing was
correct. Not the cause.

### 9d. The controlled experiment

The one thing probes 1 and 2 had in common that stock discs never do: **a
relocated level file** -- `.POL` did not fit and moved. If the engine locates
level files through anything but the archive records at runtime, it would read
`.POL`'s old slot, which the writer zeroes. Two discs separate that from "the
SOAF data does not load":

* **A -- `GR_control_POLmoved (throwaway).iso`.** Stock Ghost Recon, stock
  data. Only `M01_CAVES.POL` moved (`0x389CBD0 -> 0x28F8A810`, 1,019 bytes,
  identical content, old slot zeroed). Tests relocation alone.
* **B -- `GR_SOAF_probe3 (throwaway).iso`.** Probe 2 without the `.POL` swap:
  SOAF's `.MAZ` `.MOL` `.SHT` `.AOL` `.ENV` `.BMZ`, all in place, Ghost
  Recon's own `.POL` untouched. **Nothing relocated.** Differs from probe 2 in
  that one file.

| A | B | reading |
|---|---|---|
| loads | loads | relocation (or SOAF's `.POL`) was the problem |
| loads | hangs | the SOAF level data itself does not load in Ghost Recon |
| hangs | -- | Ghost Recon cannot take a relocated level file; every port must fit in place |

## 10. The controlled experiment, answered (2026-09-28)

| disc | result |
|---|---|
| A, stock GR with `M01_CAVES.POL` relocated | **loads and plays normally** |
| B, six SOAF files in place, nothing relocated | **stuck at loading** |

So **relocation is fine** -- Ghost Recon reads a moved level file without
complaint, which is also good news for every data edit this tool makes on that
disc. And **Sum of All Fears' level data is what Ghost Recon will not finish
loading**, independent of where it sits.

### 10a. What the game is doing while it waits

Two savestates from disc B, read with the method in §9b:

    slot 1   VSync <- sceGsSyncV <- IkeUIMgr::CheckingLoadingLoop+0xE8 <- main
    slot 2   RSInputImpl::Update <- RSInputMgr::Update <- IkeGameMgr::Update <- main

`CheckingLoadingLoop` is the loading screen's own loop: each frame it tests
the load state at `this+0xB0`, waits a vsync (or `WaitSema` on the semaphore
at `0x005E7C80`), and goes round again. **The main thread is healthy and
waiting.** The loader runs on another thread and never signals completion.
Neither snapshot shows that thread, because a savestate's `cpuRegs` is only
the thread that was running.

**Next step:** read the loader thread's saved context from the EE kernel's
thread table in `eeMemory.bin` -- its PC will be inside whatever SOAF data it
failed on, and Ghost Recon's symbols will name it.

### 10b. On retargeting to Jungle Storm

Jungle Storm is the right *final* target for multiplayer: its networking is
TCP/IP over the PS2 network adapter, which PCSX2 emulates, where Sum of All
Fears uses i.Link, which it does not. (Jungle Storm has no LAN mode as such --
its online is a Ubi.com lobby, which needs a stand-in server; see
`js_skip_dnas`.)

It is not the right place to *debug* the load. Ghost Recon ships a symbol
table and Jungle Storm does not, and Sum of All Fears' code matched Ghost
Recon more closely than Jungle Storm (§4 of `code.md`), so its data is if
anything less likely to load in Jungle Storm. Find why it will not load in
Ghost Recon, fix that, then carry the fix across.

## 11. Root cause of all three hangs: the `.ENV` names the map by path

### 11a. The thread table, and a correction

The EE kernel keeps its thread control blocks in the first 512 KB of RAM,
which a savestate captures. Every Ghost Recon thread carries the same `$gp`
(`0x005E6CF0`), so the table can be found by that signature without knowing
the BIOS's address for it. Probe 3, slot 2:

| thread | priority | state | stack |
|---|---|---|---|
| main | -- | running | the frame loop (§10a) |
| 2 | 0 | `WaitSema` 2 | `topThread` |
| 3 | 20 | `WaitSema` 10 | `LoadingPageThread` |

**There is no loader thread.** §10a said "the loader runs on another thread
and never signals"; that was wrong. The only other game threads are an idle
thread and the one that animates the loading screen. The level loads **on the
main thread**, one step per frame, as a chain of messages --
`HandleLoadMission` -> `HandleLoadEnvironment` -> `HandleLoadMap` ->
`HandleLoadSkybox` (all `IkeSimulationMgr`), each posting the next. A step that
fails posts nothing, and the loading screen waits for good.

(In these control blocks the word at `+0x0C` is where the thread is parked --
`WaitSema+0x8` for the blocked ones -- not its entry point.)

### 11b. What the `.ENV` actually says

| | Ghost Recon `M01_CAVES.ENV` | Sum of All Fears `TRAINING.ENV` |
|---|---|---|
| `MapFileName` | `m01_caves\m01_caves.map` | `training\training.map` |
| `SkyboxFileName` | `m01_caves.pob` | `m09_bank_skybox.pob` -- **absent from Ghost Recon** |
| `CMBitmap`, `CMOffsetX/Y`, `CMBasePlanningLevel` | present (the command map) | **absent** |
| fog | near 10, far 180, sand (249,239,205) | near 190, far 240, night (13,13,15) |

The `.ENV` is the level's master pointer, and it names the map **by path**.
Every probe so far swapped Sum of All Fears' `.ENV` in, which told Ghost
Recon's loader to load a level called `training` -- whose files do not exist
in `GR.IMG` under that name, because Sum of All Fears' data had been written
under `M01_CAVES` names -- and a Bank skybox that is not on the disc.

**So the geometry was never tested.** The loader never asked for the files the
probes had replaced. Probes 1-3 say nothing about whether Sum of All Fears'
`.MAZ` loads in Ghost Recon; they only say that an `.ENV` naming files that do
not exist hangs the load. §7a's "hangs because the texture bundle was
mismatched" and §10's "Sum of All Fears' level data is what will not load" are
both withdrawn.

### 11c. Probe 4

`E:/PS2 Games/GR_SOAF_probe4 (throwaway).iso`. Sum of All Fears' `.MAZ`
`.MOL` `.SHT` `.AOL` `.POL` `.BMZ` under the `M01_CAVES` names (`.POL`
relocates, which §10 showed is harmless), and **Ghost Recon's own `.ENV` left
as shipped**, so the loader asks for `m01_caves` and is handed Sum of All
Fears' data. All six read back to their original lengths; `GR.IMG` still lists
4,004 files. This is the first probe that actually tests the geometry.

Expect Ghost Recon's sand-coloured fog, its cave skybox and its command map over
Sum of All Fears' training ground -- all cosmetic, and all from the `.ENV`.
If it loads, the next step is an `.ENV` carrying Sum of All Fears' fog and far
plane with Ghost Recon's map name, skybox and command-map fields.

## 12. Probe 4: still stuck -- the load dies in `LoadPortals`

Probe 4 (Ghost Recon's own `.ENV`, Sum of All Fears' six geometry and texture
files) **also sticks at loading**, so the `.ENV` was a real fault (§11) but not
the only one.

### 12a. The loader's order

`MAPLoader::LoadWithSim` (`0x0047C9F0`), traced call by call:

    LoadFromMol     .mol    models and rooms
    LoadPortals     .pol    portals between rooms
    CGraphicSystem::LoadMissionMap   .MAZ / .SHT / .BMZ
    LoadObjects     .aol    placed objects

### 12b. How far it got, from what is left in RAM

Probe 4's savestate (slot 3), searched for each file's bytes:

| | in RAM |
|---|---|
| Ghost Recon's sky textures, command-map bitmap, briefing art (named by the `.ENV`) | **yes** -- resident |
| SOAF `.MOL` | its last 110 bytes only, in stack-area memory |
| SOAF `.POL` | its first 21 bytes only (chunk header + `Version`), in stack-area memory |
| SOAF `.MAZ` `.SHT` `.BMZ` `.AOL` | **nothing, not even headers** |

Read against 12a: the `.MOL` was streamed through to its end, the `.POL`'s header
was read, and nothing after that was touched. **The load dies in `LoadFromMol`'s
tail or, more likely, `LoadPortals`.** The two fragments are small and sit in
stack memory, so treat this as strong circumstantial evidence rather than proof;
it is, however, exactly the pattern 12a predicts.

The game prints nothing about its load (checked `emulog.txt`), so the log
cannot confirm it.

### 12c. Ruled out, each checked rather than assumed

* **Version records** -- identical: `.AOL` v5 `ObjectList`, `.POL` v1
  `PortalList`, `.MOL` v9, `.SHT` `RoomData`.
* **Object classes** -- every class Sum of All Fears places (`n`, `door`,
  `glass`, `target`, `dyn`, `forest`, `spotlight`) is used by some Ghost Recon
  level.
* **An object-count cap** -- `LoadObjects` checks the chunk id is `0xA`, reads a
  count and loops with no upper bound. (SOAF's training ground places 85
  objects to Ghost Recon's maximum of 53, but the load never reaches objects.)
* **Portal name prefixes** -- `p`, `pd`, `pt`, `pwt` all occur in Ghost Recon.
* **Capacity** -- texture count, room counts, portal count, and every file size
  are inside the range Ghost Recon's own levels already use.

### 12d. What `LoadPortal` does with each portal

`MAPLoader::LoadPortal` (`0x0047B8A0`, 1,816 bytes): reads a chunk header,
builds the portal's name with `sprintf("%d")`, reads vertices, ints and a
string, then turns each of the portal's two room numbers into a string with
`itoa` and searches the `RSArray<Room>` for a room of that name, and finally
calls `RSModelManager::FindModel` for the portal's geometry. The rooms come
from `LoadFromMol`, which ran just before. Neither game's `.MOL` registers
models under portal names -- not even Ghost Recon's own -- so the name
`FindModel` is given comes from the portal record itself, not yet identified.

### 12e. Next step

Mirror `LoadPortal`'s reads in Python, run it over Ghost Recon's `.POL` and
Sum of All Fears', and find the first field where Sum of All Fears' records
stop parsing the way Ghost Recon's code expects. Deterministic, and needs no
more boots.

### 12f. A better donor, found along the way

Ghost Recon has its own `TRAINING` level, and it is a close relative of Sum of
All Fears': both have **exactly 17** `pwt` portals and **exactly 62** `target`
objects. If room numbering carries over between the two, `TRAINING` is a far
better slot than `M01_CAVES` for this level.

## 13. Probe 5: Sum of All Fears' training ground in Ghost Recon's `TRAINING` slot

### 13a. Why this slot

Ghost Recon's own `TRAINING.ENV` already reads `<MapFileName>training\training.map`
-- Sum of All Fears' map name exactly -- and shares its far plane (250) and fog
distances (190 / 240). With §12f's 17 `pwt` portals and 62 targets in both, the
two are the same level in two generations. So Ghost Recon's `.ENV` stays, and
there is no name to reconcile at all. Seven missions load it: `T01`-`T07.MIS`
(plus `TRAINING_MP.MIS`), all via `training.env`.

### 13b. The space problem, and a probe-only workaround

All six Sum of All Fears files are larger than Ghost Recon's `TRAINING` slots,
the texture bundle by 337 KB. `GR.IMG` has no **blank** free run of 2.1 MB:
the allocator found large unclaimed runs, but they hold data, and it refuses to
overwrite unclaimed non-zero bytes (correctly -- unreferenced is not the same as
unused). `GR.IMG` cannot simply grow either: `MENU.IMG` begins at the exact
byte `GR.IMG` ends.

For this throwaway disc, `MP06_CASTLE.BMZ` (a multiplayer map's texture bundle,
2,233,124 bytes) was blanked and its record set to zero length, handing its
slot to the allocator; everything else went through `Vokes.write` and its
blank-check as normal. The texture bundle landed in the donor slot, and
`.SHT`, `.MOL` and `.AOL` in the space it vacated; `.MAZ` and `.POL` grew in
place into blank runs freed behind them. All six read back to their original
lengths. The only file that changed in the listing is `MP06_CASTLE.BMZ`, which a
zero-length record drops from it; `TRAINING.ENV` is byte-identical to the
shipped one. **Multiplayer map MP06 (Castle) is broken on this disc.**

**For a real port tool** this workaround is not acceptable: it needs a way to
make room -- most likely moving `MENU.IMG` to the end of the image, updating
its ISO directory record, and growing `GR.IMG` into the space. Every serious
level port will need more room than the level it replaces.

### 13c. What to run

`E:/PS2 Games/GR_SOAF_probe5_training (throwaway).iso` -- Ghost Recon's
Training, first mission (`T01`).

## 14. Probe 5 result: a crash, not a hang

Training `T01` on probe 5 no longer sits on the loading screen: PCSX2 stops
with **"R5900 Exception: Jump to unaligned address (PC: 0xCDCDCDCD)"** after
about 17 s of loading (`emulog.txt`, 2277 s). `0xCDCDCDCD` is a fill pattern:
code called through a pointer in memory that was allocated and never written.
The behaviour changed with the slot, so the `TRAINING` slot got the loader
doing something the `M01_CAVES` slot did not.

### 14a. What the savestate (slot 4) can and cannot say

**Can:** stale frames below the stack pointer, most recent first:
`HandleLoadEnvironment` -> (message dispatch) -> `HandleLoadMap` ->
`RSSimMAPLoader` / `MAPLoader` / `ROBLoader` constructors; older still,
`RSModelManager::LoadModel` -> `RSQOBLoader::Load`. Stale frames are call
history, not one guaranteed chain, but they put the crash inside the map load
that `HandleLoadMap` starts.

**Cannot:** the faulting registers. The state was saved after the CPU had
entered the BIOS exception path -- `$sp` is a kernel stack, `$ra` and `EPC` are
BIOS code (`0x00081FEC` / `0x00081FF4`, a `jalr $v1; ... syscall` callback
trampoline), and `$v1` no longer holds `0xCDCDCDCD`. No `0xCDCDCDCD` remains in
kernel memory. The kernel's handler table (`0x80019484`) is intact. Do not try
to recover the fault from a state saved after the dialog.

### 14b. Checked and ruled out

* **`0xCDCDCDCD` baked into SOAF's files** (a PC debug-build exporter writing
  uninitialised fields to disk): **no** -- zero occurrences in any of the six
  geometry files; a couple in texture pixels, which Ghost Recon's own files
  have too. The bad pointer is runtime memory.
* **Unknown surface ids in collision groups:**
  `IkeSurfacePropertiesMgr::FindPropertyForID` knows ids -1..26 and returns 0
  for anything else, not garbage. Not this.
* **Missing model files:** the numeric prefixes on placed objects
  (`308_<door>killhouse01`) are **room numbers**, not model files -- Ghost
  Recon's own `TRAINING.AOL` shows the same "no file" pattern for 14 of 15
  prefixes and loads fine.

### 14c. A correction to §12b

§12b located the M01_CAVES stall in `LoadPortals` from a 110-byte `.MOL` tail
and a 21-byte `.POL` header found in stack memory. Sampling 40 chunks of each
file in both probes finds **none** of them resident in either -- these files are
parsed as they stream and discarded, so residency cannot measure progress. The
fragments were real but thin; `LoadPortals` is a hypothesis, not a finding.

### 14d. The decisive next step: breakpoints on the loader

Ghost Recon's symbols give every load step's address. Break on each in PCSX2's
debugger (Debug -> Open Debugger -> Breakpoints) and start `T01`; the last one
that fires before the exception is the step that fails:

| step | address |
|---|---|
| `IkeSimulationMgr::HandleLoadMap` | `0x00388D60` |
| `MAPLoader::LoadWithSim` | `0x0047C9F0` |
| `MAPLoader::LoadFromMol` | `0x0047C340` |
| `MAPLoader::LoadPortals` | `0x0047C020` |
| `CGraphicSystem::LoadMissionMap` | `0x0044D890` |
| `MAPLoader::LoadObjects` | `0x0047B730` |
| `IkeSimulationMgr::HandleLoadSkybox` | `0x003991E0` |

After that, the failing function can be mirrored in Python over SOAF's file
and Ghost Recon's to find the field that differs.

## 15. Breakpoints settle it: the load fails in `LoadFromMol`

### 15a. The run

The seven load steps from §14d were set as execute breakpoints
(`research/pcsx2-debugger/SLUS-20613_3E571E95.json`) and probe 5 was booted
into Training `T01`. Hit counts:

| # | step | hits |
|---|---|---|
| 1 | `HandleLoadMap` | **1** |
| 2 | `MAPLoader::LoadWithSim` | **1** |
| 3 | `MAPLoader::LoadFromMol` | **1** |
| 4 | `MAPLoader::LoadPortals` | 0 |
| 5 | `CGraphicSystem::LoadMissionMap` | 0 |
| 6 | `MAPLoader::LoadObjects` | 0 |
| 7 | `HandleLoadSkybox` | 0 |

**The load enters `LoadFromMol` and never reaches `LoadPortals`.** This comes
from breakpoints, not inference. It supersedes the residue-based guesses in
§12b and §14c, and it fits the model-loading frames (`RSModelManager` /
`RSQOBLoader`) left in probe 5's crash state.

After step 3 the game showed EE 98% at 8% speed. With the debugger attached
this is probably the same load crawling toward the `0xCDCDCDCD` crash seen
without it, not a separate hang. It was not run to completion under the
debugger.

### 15b. What slot 5 could not show

That state was saved mid-grind, but it caught the CPU inside an interrupt
handler's system call (`EPC = iSignalSema+0x8`, kernel stack). The only saved
game-register block in kernel memory (`0x78000`) is a stale debug-print frame
(`$ra = kputs`). So it cannot show where in `LoadFromMol` the time goes. A
savestate taken at a random moment does not reliably land in the game thread.
The debugger's **Pause** button with the Stack tab open would.

### 15c. What `LoadFromMol` does

`MAPLoader::LoadFromMol` (`0x0047C340`, 1,404 bytes):

1. opens the `.mol`, reads an 8-byte preamble (`04 00 00 00 01 00 00 00` in
   both games)
2. reads the top chunk header
3. for each model chunk: reads its header, lower-cases the name, calls
   `RSModelManager::FindModel(name)`, wraps the chunk's bytes in a
   `strstreambuf`, and hands them to **`ROBLoader::LoadGeometryChunk`**; then
   `RSModel::CalculateBoundingSpheres` and a run of virtual calls, then skips
   the rest of the chunk.

So a `.MOL` is a list of models, and the failure is inside one model's geometry
load or the virtual calls after it.

**Chunk header** (`RSQOBLoader::ReadChunkHeader`, `0x0047E390`):
`u32 size, u32 type, name` with length-prefixed, NUL-terminated names. If the
name is `Version`, a `u32` version and the real name follow. `size` counts the
payload after the whole header. Checked against the file: Sum of All Fears'
top chunk declares 664,715 payload bytes. The 8-byte preamble plus the 33-byte
header plus 664,715 is exactly the file's 664,756 bytes.

### 15d. Pending

A walk of every chunk in Sum of All Fears' `TRAINING.MOL` against every chunk
in all 36 Ghost Recon `.MOL` files is running, looking for a chunk type or
version Sum of All Fears uses that Ghost Recon never does. That is the prime
suspect for a handler Ghost Recon's loader lacks, which is how a call through
never-written memory (`0xCDCDCDCD`) would arise. No result is recorded here
until it finishes.

**Resolved in §16c:** Sum of All Fears uses no chunk type or version that
Ghost Recon does not, and the whole file parses exactly under Ghost Recon's
reader.

### 15e. Tooling note

PCSX2 1.7.5641 reads debugger settings from **`inis\debuggersettings\`**, not
the top-level `debuggersettings\`. The first copy of this breakpoint file went
to the wrong folder, following an existing Rainbow Six 3 file that had never
been loaded from there. `research/pcsx2-debugger/README.md` has the format,
checked against PCSX2's source (`X` is the enabled flag, `TYPE 8` is an
execute breakpoint).

## 16. Probe 6, and the defect under every probe: stale unpacked sizes

### 16a. Probe 6: the helper-name renames change nothing

Probe 6 is probe 5 with 24 `lighthalo` helpers renamed `xighthalo` and 58
`pathpoint` helpers renamed `xathpoint` (same length, structure re-checked).
Booted with the §15 breakpoints it stopped at 1, 2 and 3 and never reached 4,
exactly like probe 5, then froze. Neither helper kind is the cause.

### 16b. How `LoadFromMol` really reads a model (corrects §15c)

§15c said each chunk is wrapped in a `strstreambuf` and handed to
`ROBLoader::LoadGeometryChunk`. The call is real, but it reads nothing:

* The `strstreambuf` is a **20-byte dummy**. `LoadGeometryChunk` is called with
  version **9**, and at 9 it only calls the sim-load callback
  (`RSSimModel::LoadSimModel`, `0x004EABA0`), which builds an empty
  `RSSimModel` and returns before touching the stream.
* The chunk is read by **`RSModel::ReadCollisionBinary`** (`0x004B86D0`,
  model vtable `+0x5C`) off the **file** stream, which then hands the rest to
  `RSSimModel::ReadBinary` (`0x004EB2C0`) through
  `mSimModelReadBinaryCallback`.
* `LoadFromMol` then reads the next chunk header **directly**. It never seeks
  to the end of the chunk, so one field of drift corrupts every model after it.

So the plan to mirror `RSQOBLoader::LoadGeometryChunk` / `LoadMesh` had the
wrong target. The full layout of what is actually read is in the docstring of
`research/code/molcheck.py`.

Also a correction to §15a: PCSX2 keeps **no hit count for execute
breakpoints** (its Hits column shows `--`). The "hits" there are the stops
observed, which is the same information.

### 16c. The .MOL is valid by the reader's own rules

`molcheck.py` mirrors that reader. Run over all 36 Ghost Recon `.MOL` files
and Sum of All Fears' `TRAINING.MOL`:

| check | Ghost Recon | Sum of All Fears |
|---|---|---|
| models whose parse consumes exactly the declared chunk size | 864 / 864 | 57 / 57 |
| collision faces whose group, mesh, face and vertex all resolve | 966,106 / 966,106 | 17,472 / 17,472 |
| render faces whose vertices are in range | all | all |

Every total (vertices, faces, sim vertices, groups, helpers, room numbers) is
inside Ghost Recon's range. The one outlier is the model count, 57 against
Ghost Recon's 55 (`M13_AIRBASE`), and it does not matter: `RSModelManager`
keeps models in a 223-bucket string hash of growable arrays. No name repeats
within the file. A map with no `general_type_49` (bird) helper, which every
Ghost Recon map has exactly one of, is guarded: the only reader checks for a
count of zero, and it runs during play, not load.

The file is not the problem. What the game is **told about** the file is.

### 16d. Root cause: the record's second size

Every archive record carries two sizes. For an LZO-packed file the second is
the **unpacked** length. Checked on every record of the stock discs:

| archive | packed files with size2 = unpacked length | plain files with size2 = size |
|---|---|---|
| Ghost Recon `GR.IMG` | 1,452 / 1,452 | 2,552 / 2,552 |
| Ghost Recon `MENU.IMG` | 212 / 212 | 474 / 474 |
| Jungle Storm `GR.IMG` | 1,197 / 1,197 | 1,819 / 1,819 |
| Sum of All Fears `SOAF.IMG` | 1,487 / 1,487 | 933 / 933 |
| Sum of All Fears `MENU.IMG` | 187 / 187 | 144 / 144 |

**The game uses it as the end of the file.** `idistream`'s constructor
(`0x0054D0F0`) asks the IOP for the file's info (`diGetFileInfo`, RPC
`0x80010015`) and keeps a length at `+0x28`. `diinputbuf::underflow`
(`0x0054D5A0`) compares that against the unpacked bytes produced so far and
returns EOF when they meet, decoding whole 16 KiB chunks.

`tcps2/vokes.py` kept the old second size unless the caller passed one, and
its in-place path ignored it even then. Its comment claimed the two sizes are
equal in the Ghost Recons, which is only true of plain files. Every swapped
packed file on probes 5 and 6 carried Ghost Recon's old length:

| file | size2 on the probe | real unpacked size |
|---|---|---|
| `TRAINING.MOL` | 506,088 | 664,756 |
| `TRAINING.POL` | 5,198 | 7,178 |
| `TRAINING.MAZ` | 893,552 | 1,048,508 |
| `TRAINING.SHT` | 615,686 | 817,978 |
| `TRAINING.BMZ` | 2,381,824 | 2,638,992 |
| `TRAINING.AOL` | 35,816 | 59,538 |

The game therefore sees the `.MOL` end after 31 chunks, **507,904 of 664,756
bytes**, 8,805 bytes into model 18 of 57 (room `224`). `istream::read` at EOF
leaves its destination untouched, so from there every count `LoadFromMol` reads
is whatever was on the stack. That fits both symptoms: a runaway loop (the hang
under the debugger) and a call through never-written memory (`0xCDCDCDCD`
without it). **This is reasoned from the code, not yet observed at run time.**

Probes 1 to 4 swapped packed files the same way, so they carried the same
fault. The `.ENV` path mismatch of §11 was a separate, real defect: the
`.ENV` is a plain file and its sizes were right.

**Shipped options were not affected.** `dataedit.apply_data` refuses any
edit that changes a packed container's length (the only exceptions are two
Rainbow Six 3 `.LIN` ops), and it is the only code that writes archive
entries. Only the probe builds, which call `Vokes.write` directly, and the
planned "patch SOAF into GR" feature could hit this.

**Fixed.** `Vokes._set_entry` now takes the second size from the data
whenever the record already holds a packed file, and all five callers pass it.
Rainbow Six 3, whose two sizes are always equal, takes the unchanged path.
`tests/run_tests.py` gains `run_vokes_unpacked_size`. It **fails on the old
code** (in place and relocated both kept the stale length) and passes on the
new.

### 16e. Probe 7

`E:/PS2 Games/GR_SOAF_probe7_sizes (throwaway).iso` is probe 5 (Sum of All
Fears' files unmodified, no renames) with **only the six size2 words
corrected**. Re-read from disc: every swapped file's second size equals its
unpacked length, and the six packed files are byte-identical to probe 5's.

If Training `T01` loads, §16d was the cause. If it still fails, the breakpoint
file now holds 14 stops inside `LoadFromMol` and `LoadWithSim` (see
`research/pcsx2-debugger/README.md`), which show whether the model loop
finishes, which failure exit is taken, and roughly which model it stops on.

### 16f. Probe 7 result: the load completes; a new crash after it

Booted into Training `T01` with the 14 `.MOL` breakpoints. The screenshots show
MOL 01 to MOL 05 stopping, with `s0 = 0x24` in the registers at MOL 05. The
user continued through every stop and reports that loading finished, then a
black screen, a freeze, and the emulator closing. `emulog.txt` agrees:

* **Ten pause/resume pairs** between 2056 s and 2113 s. The success path has
  exactly ten stops (MOL 01 to MOL 10); a failure path cannot reach ten. So
  the model loop finished, `LoadFromMol` returned success and `LoadPortals`
  was reached. This is inferred from the count; only 01 to 05 are on screen.
* **The mission started.** At 2117.02 the game ran
  `RSGameStateMgr::SaveGame` with `map name = t01.mis`, and at 2118.36
  `SetListenerEnvironment: type=open space`.
* **60 ms later the EE ran data as code.** At 2118.42 the recompiler reports
  56 unknown opcodes, almost all floats near 1000.0 (`0x447A0000`,
  `0x4479FB74`, `0x447A1B80`, ...), plus `0xC9472CAA` and `0xC15B3332`. A jump
  landed in a float array. The run does not appear in any of the swapped
  files, so it is runtime memory, not level data copied verbatim.

Probe 7 differs from probe 5 only in the six size2 words. Probe 5 never
reached `LoadPortals`; probe 7 loads through to mission start. **§16d was the
cause of the load failure.** What remains is a separate fault in the first
moments of the mission, and it has not been located yet.

### 16g. What runs after the load, and the breakpoints for it

**The last log line is not an error.** `+++SetListenerEnvironment: type=open
space, id=19` comes from `IkeSoundMgr::UpdateListener` (`0x00263C70`), run
when the camera reports a new position. It looks the listener's room up **by
value** in the mission's `SetupFileRoomEntry` list and falls back to
environment `0x13` (19, open space) when the room is not listed. Ghost Recon's
T01 setup does not list Sum of All Fears' rooms, so the fallback is expected
and handled.

**The frame loop** is in `main` (`0x003F996C` to `0x003F9B64`). Each frame
calls `CGraphicSystem::Render`, then `IkeGameMgr::Update`, which calls every
"runnable" (`this+0x38`, count at `+0xB8`, vtable `+0x0C`). Only when
`IkeStateMgr::InActionPhase()` is true does it go on to
`SceneCamera::DetermineVisibility`, `PreMainFrame`, the effects pre-render,
`MainFrame`, the effects render and `EndOneFrame`.

**The mission gate.** `InActionPhase` is true when the top byte of the
game-state word, `[[0x005DFF48] + 0x1DC]`, is 6. On nine savestates every
in-mission one reads 6 and every stuck-loading one reads 5.

**The run.** `EndLoading` logged at 2117.04 and the crash came at 2118.42,
about 80 frames later, so the stops cannot simply sit in the frame loop.
POST 0 is on `SetListenerEnvironment`, 60 ms before the crash. At that stop,
save a state and tick POST 1 to 5, the frame loop's call sites. The last one
to stop before the crash names the stage that crashed. POST 6 splits
`IkeGameMgr::Update` by runnable, for a second pass. The full table is in
`research/pcsx2-debugger/README.md`.

The state saved at POST 0 is taken in the game thread before the fault, so,
unlike §14a's, it can be searched for the float run the CPU jumped into and for
whatever points at it.

### 16h. The first-frame crash: a character outside every room

The run with the §16g breakpoints stopped at POST 0 and then POST 1 to 4 as
expected, and the user reports POST 4 as the last stop. It then failed with
"Jump to unmapped recLUT page (PC: 0x1a820000)". The slot 7 state was saved at
that dialog, not at POST 0. Its registers are garbage with the low 16 bits
clear (`ra = 0x1D940000`, `sp = 0x62500000`), which is what `lui` produces:
floats between about 0.008 and 2.0 decode as `lui`. So the CPU ran through
float data before landing on `0x1A820000`, as in §16f.

**The stack says the simulation, not drawing.** Memory is intact, so the
stale frames were unwound level by level. At each level the step is accepted
only when the callee's frame size puts its return-address slot exactly on a
word holding a return into the caller, and the callee's saved registers are
checked against the caller's live values.

| level | function | check |
|---|---|---|
| 0 | `main` frame loop | slot `0x07FFFD00` = return after `IkeGameMgr::Update` |
| 1 | `IkeGameMgr::Update` | |
| 2 | runnable #3, `IkeSimulationMgr::Update` | saved `s0 = 3`, `s1 = 0x00773F40` (the game manager) |
| 3 | `SimHuman::Update` | saved `s0 = 0x00797E80`, the object being updated |
| 4 | `SimHuman::UpdateCameraLocation` | saved `s0` = the same `SimHuman` |
| 5 | `SimHuman::FindRoom` | saved `s0` = the same `SimHuman` |
| 6 | `RSSimRoom::FindLineCollisionWithPortal` (`0x004D7980`) | saved `s0`, `s1`, `s2` = `FindRoom`'s live values |
| 7 | the inner overload (`0x004D7570`) | saved `s4` = the room = **0** |

Nearly every function `main` calls in its frame loop saves its return address
in slot `0x07FFFD00`, including `DetermineVisibility`, `MainFrame` and
`EndOneFrame`. It holds the return from `Update`, so none of them ran after the
last `Update`. That contradicts "last stop POST 4", unless POST 1 and 2 did not
stop in the crashing frame; the memory evidence is the stronger of the two.
Level 7 never got past its first virtual call. The local it writes right after
(`sp+0xC0`) still holds stale data.

**The fault.** `SimHuman 0x00797E80` has no room (`[+0x38] = 0`) and stands at
**(1000.0, 1000.0, 1000.0)**. `FindRoom` casts a line from it toward its camera
through the current room's portals, so the portal code runs on a NULL room. It
reads `room->0xA8` from low kernel memory and calls a virtual method through
it. 1000.0 is `0x447A0000`, the float that dominated the executed data in
§16f.

Of the 86 sim objects, it is the only one without a room. The 41 doors, 31
targets, 8 panes of glass, 2 guns and the other three humans are all in SOAF
rooms. The player stands in T01's insertion zone at (-11.40, -14.77), and two
more humans are at (-12.08, 1.90) and (-12.28, -0.50).

Checked and ruled out:

* **A missing room number.** SOAF's training ground is Ghost Recon's Ft. Bragg
  course, extended. All 21 of Ghost Recon's room numbers exist in SOAF's map,
  which adds 120-124 and 300-309.
* **A holding room at 1000.** No room in any of the 37 maps (36 Ghost Recon
  plus SOAF's) contains that point.
* **Map-side spawn markers.** Ghost Recon's `TRAINING.MOL` has no helper points
  at all, and its `.AOL` has no character markers. `T01.MIS` lists zones,
  rooms, two objects and a compiled script, but no characters.
* **A NULL room always crashing.** A stock mission save (`1458AB4E`, modded
  ELF) has six active humans with no room at real positions. `FindRoom` only
  runs the portal test when the camera is offset from the character, and
  otherwise returns the room directly.

**Open:** who the fourth human is, and where stock Ghost Recon's T01 puts it.
A stock T01 savestate taken just after the mission starts would answer that.

### 16i. Root cause of the first-frame crash: a rifleman 0.0000017 too low

A stock T01 savestate (slot 8) has the same four humans. The player is at the
insertion zone, and three riflemen stand in room 113 at (-12.08, 1.90),
(-12.28, -0.50) and **(-13.88, 1.90)**. In the port, the first two were placed
(at z 0.1) and the third was left at the default (1000, 1000, 1000).

**Where they come from.** `TRAINING.TOE`, Ghost Recon's actor setup for the
map, which the port keeps. Team `_Bravo` has three riflemen with fixed
positions, all at z `-0.00`. The unplaced one is `_Trent Norris` (IgorId 8).

**How placement fails.** `SimHuman::InitializeFromMessage` (`0x003C88C0`)
loads the character, then calls `RSSimScene::FindRoom(position)`. **If that
returns NULL it returns early**, skipping `SetActorPosition` and the room
setup. The character stays active, at the default position, with no room, and
its first camera update (§16h) crashes. `FindRoom` takes each room whose box
contains the point and asks `RSSimRoom::FindLevelPointIsOver` for a floor.
That goes through `RSVoxel2dManager::GetFloorHeight` (`0x004F27D0`), which
accepts a floor face only if **floor − point.z < 0.1f** (`0x3DCCCCCD`): an
actor may step up at most 10 cm. `RSFloorFace::GetFloorHeight` computes the
height from the collision face's stored plane, −(nx·x + ny·y + d)/nz, with the
normal quantised to 1/4096.

**Why it differs.** In Ghost Recon all three spots are room 113's open floor at
z 0.0. SOAF built its killhouse there: a ground floor at z 0.1 in rooms 302
and 303, a second storey at 3.4 (306, 307), and room 113 at 6.6 as the roof.
With the TOE's z = 0, the ground floor sits exactly on the 10 cm limit.
Emulated from the planes in SOAF's `.MOL` (same result with nearest and
toward-zero rounding):

| rifleman | floor | stored height | floor − z < 0.1? |
|---|---|---|---|
| A (-12.08, 1.90) | room 302 | 0.09999876 | yes, placed |
| B (-12.28, -0.50) | room 302 | 0.09999978 | yes, placed |
| C (-13.88, 1.90) | room 303 | **0.10000172** | **no**, unplaced |

This matches both savestates exactly.

**Probe 8** (`E:/PS2 Games/GR_SOAF_probe8_toe (throwaway).iso`) is probe 7
with only the three TOE positions raised from `-0.00` to `0.100`. That is the
same unpacked length, and the file stayed in its slot. Emulated at z = 0.1,
all three accept the ground floor (floor − z ≤ 0.0000017) and reject the
second storey and roof. Only `TRAINING.TOE` differs from probe 7 in `GR.IMG`.

**For a real port tool.** A SOAF map keeps Ghost Recon's `.TOE` and missions,
whose positions assume Ghost Recon's floors. Every fixed actor position should
be checked with this exact floor test against the ported map, and raised onto
the floor where it fails. The ports' `.MOL` planes are enough to do that
offline.

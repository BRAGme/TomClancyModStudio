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

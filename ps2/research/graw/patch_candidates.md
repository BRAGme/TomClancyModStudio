# GRAW PS2 — candidate word patches

**None of these has been tested.** No emulator was launched, no ISO was written.
Every "current word" below was read back out of the extracted `SP.IMG` with a
script and is reproduced here exactly as the file has it — see the verification
note at the end.

**Anchor before writing anything.** `/SP.IMG`, LBA 268011, 6,507,824 bytes,
SHA-1 `a79e35322e1192a9ac6883f653b1e4f5505a1bcc`. A patcher should refuse to run
if that hash does not match.

**The easy part:** unlike Rainbow Six 3's `SP.SOZ`, GRAW's `SP.IMG` is a **plain
uncompressed ELF** ([loadmap.md](loadmap.md)). A word patch is a byte-for-byte
in-place write at a fixed disc offset — no re-deflate, no extent budget, no
directory rebuild.

Address conversions used throughout:

```
SP.IMG   file offset = VA - 0x000FF800
         disc byte   = 268011 * 2048 + file offset
                     = 548886528 + file offset
```

Risk letters:

* **A** — one self-contained constant, effect is bounded, trivially reversible.
* **B** — changes behaviour for every level, but the code path is fully understood.
* **C** — the code path is understood but the *consumer* is UnrealScript we cannot
  read, so the outcome is a hypothesis.
* **D** — known to be able to break the mission script or stall the game. Only for
  experiments, never for a shipped tool default.

---

## 1. Survival / scripted-spawn pacing — the two numbers the overlay owns

Background in [survival.md](survival.md) §2. `0x0058E430` is the Tick of the
`ScriptSpawnTerrorists` latent command; it is the only place in either overlay
that owns a spawn number.

| # | VA | file off | disc byte | current word | proposed | effect | risk |
|---|---|---|---|---|---|---|---|
| 1.1 | `0x0058E4BC` | `0x48ECBC` | 553665724 | `0x3C023F80` | `0x3C023F00` | spawn interval 1.0 s → **0.5 s** (double rate) | A |
| 1.2 | `0x0058E4BC` | `0x48ECBC` | 553665724 | `0x3C023F80` | `0x3C023E80` | spawn interval → **0.25 s** (4× rate) | A |
| 1.3 | `0x0058E4BC` | `0x48ECBC` | 553665724 | `0x3C023F80` | `0x3C024000` | spawn interval → **2.0 s** (half rate) | A |
| 1.4 | `0x0058E4BC` | `0x48ECBC` | 553665724 | `0x3C023F80` | `0x3C020000` | interval → **0.0 s**: one enemy released *every frame* until the count is met | D |
| 1.5 | `0x0058E508` | `0x48ED08` | 553665800 | `0x24020001` | `0x2402000N` | enemies released **per interval**: 1 → N | C |
| 1.6 | `0x0058E3DC` | `0x48EBDC` | 553665500 | `0x8FA20038` | `0x2402000N` | override the script's own total: **every** `ScriptSpawnTerrorists`, in every level, owes exactly N | B |
| 1.7 | `0x0058E540` | `0x48ED40` | 553665856 | `0x2442FFFF` | `0x24420000` | `remaining--` becomes `remaining += 0` → **never-ending spawn** | D |
| 1.8 | `0x0058E4D8` | `0x48ECD8` | 553665752 | `0x4501001E` | `0x00000000` | delete the rate limiter entirely (equivalent to 1.4 but removes the float compare) | D |

Notes, in order:

* **1.1–1.4** are all the same instruction, `lui $v0, 0x3F80`, whose immediate is
  the upper half of an IEEE float. Useful values:
  `0x3F80` = 1.0, `0x3F00` = 0.5, `0x3E80` = 0.25, `0x3E00` = 0.125,
  `0x4000` = 2.0, `0x4040` = 3.0, `0x4120` = 10.0, `0x0000` = 0.0.
  Only the high 16 bits are settable this way, which is fine — every interval
  worth choosing is exactly representable.
* **1.5** writes the `int` parameter that is handed to the UnrealScript function
  `ScriptSpawnTerrorists`. The overlay does not implement that function, so
  whether it interprets the parameter as "spawn this many" or ignores it beyond
  a non-zero test **is not established from the overlay**. Marked C for that
  reason. Prefer 1.1–1.3 to raise pressure until 1.5 is tested.
* **1.6** replaces the load of script argument 2 with a literal. Argument 2 is
  still evaluated one instruction earlier (`0x0058E3A0`), so any side effect of
  evaluating it is preserved; only the stored value changes. This is the closest
  GRAW analogue to Rainbow Six 3's `0x0040AF58` "enemies each zone owes" patch.
* **1.7 and 1.8 can hang a mission.** The command is *latent*: it returns
  "still running" until `remaining` hits zero, and the mission script waits on
  it. Freeze the counter and the script waits forever. Do not put these behind a
  friendly toggle.

---

## 2. Difficulty — health regeneration

Background in [survival.md](survival.md) §5. GRAW's difficulty byte
(GameInfo `+0x414`, 0 = Recruit, 1 = Ghost/"Veteran", 2 = Elite, 3 = Ghost
Leader) has exactly three readers in the whole overlay, and two of them are the
same `difficulty < 2` regeneration gate.

| # | VA | file off | disc byte | current word | proposed | effect | risk |
|---|---|---|---|---|---|---|---|
| 2.1 | `0x004701C0` | `0x3709C0` | 552493504 | `0x28410002` | `0x28410004` | player/teammate health top-up now applies on **all four** difficulties | A |
| 2.2 | `0x00459688` | `0x359E88` | 552400520 | `0x28410002` | `0x28410004` | the matching regen tick, likewise on all four | A |
| 2.3 | `0x004701C0` | `0x3709C0` | 552493504 | `0x28410002` | `0x28410000` | `slti $at,$v0,0` is never true → **no regeneration on any difficulty** | A |
| 2.4 | `0x00459688` | `0x359E88` | 552400520 | `0x28410002` | `0x28410000` | same, for the tick | A |
| 2.5 | `0x004701D8` | `0x3709D8` | 552493528 | `0x28410078` | `0x2841NNNN` | the "is health below the floor?" test; **must** be changed together with 2.6 | B |
| 2.6 | `0x004701E0` | `0x3709E0` | 552493536 | `0x24020078` | `0x2402NNNN` | the regeneration floor itself, 0x78 = 120 hit points | B |

2.1 + 2.2 together are "easy mode on every difficulty"; 2.3 + 2.4 together are
"hardcore". Applying only one of each pair leaves the two regeneration paths
disagreeing — always patch them as a pair.

**There is deliberately no "difficulty scales enemy count" entry in this
table.** It does not exist in GRAW: the only other difficulty reader,
`0x003DC338`, picks one of four *authored floats* off GameInfo
(`+0x4D0`/`+0x4D4`/`+0x4D8`/`+0x4DC`) and those are level/config data, not code.
Rainbow Six 3's `m_NbToAddInVeteran` / `m_NbToAddInElite` have no counterpart to
patch.

---

## 3. Things the tool should *not* try, and why

Recording these so nobody spends an evening rediscovering them.

* **Porting the Rainbow Six 3 wave patches.** `0x0040AF58`, `0x0040A8A8`,
  `0x0040AFDC`, `0x0040A874` and the `bStasis` gate at `0x0040A790` address code
  that is **not present** in GRAW — see [survival.md](survival.md) §3 for the
  shape-match results and the archive-wide name search that back that up. Writing
  those words at those VAs in `SP.IMG` would corrupt unrelated functions.
* **Repointing the level-name table at `0x00671720`** to make a Survival slot
  load a campaign map. It looks tempting and it does nothing useful: the table
  has exactly one consumer, `0x0053A580` (`LevelNameToIndex`, 8 call sites), and
  every one of those uses the result only to index the Survival record array at
  `0x007B5EA8` or the EnemyHunt record array at `0x007B5E50`. Nothing loads a
  level from this table; repointing an entry only mis-files the high score.
* **Patching the Survival or EnemyHunt records.** `0x007B5EA8` and `0x007B5E50`
  are above `0x00734380`, i.e. in BSS. They are zeroed at load and filled from
  the save. There are no bytes in the image to change.
* **Patching the difficulty default.** `0x007B5F64` / `0x007B60F8` are also BSS.
  The menu handler at `0x004AF160` is where the values 1–4 are written; changing
  those immediates changes what each menu button *means*, not what the game
  starts on.

---

## 4. Split-screen effect suppression — a precise negative

Rainbow Six 3 suppresses bullet decals, impact effects, rain, blood and the
first-person weapon in split screen, and `docs/PATCHES.md` lists seven words that
undo it. **I could not find the GRAW equivalent, and here is exactly what was
searched.**

1. **Shape-matched all seven R6 3 sites** into both GRAW overlays — the view-model
   gate at `0x00302D9C`, the three impact gates `0x003F1934` / `0x003F1BB4` /
   `0x003F250C`, rain/snow `0x003531D0`, blood `0x003A14B8`, and the
   `m_bHideInSplitScreen` test at `0x002375B0` — at 12- and 8-instruction windows
   with `j`/`jal` targets, all immediates and all load/store offsets masked out.
   **Zero hits in `SP.IMG`, zero in `MP.IMG`.**
2. **Searched both overlays for the property name.** `SP.IMG`'s complete `m_*`
   property-name inventory is **27** distinct strings — 22 game-mode booleans
   (`m_bSurvivalGame`, `m_bTerroristHuntGame`, `m_bCoopStoryModeGame`,
   `m_bTeam_Siege`, …) plus `m_DebugInfo`, `m_MaxNbOfPlayersAdvListen`,
   `m_MaxNbOfPlayersTeamAdvListen`, `m_UniqueAndSequentialID_MP` and
   `m_UniqueAndSequentialID_SP`. **`m_bHideInSplitScreen` is not among them**,
   and the substring `HideInSplit` does not occur in either image.
3. **Searched for the exact substring "Split" in both overlays.** `SP.IMG` has
   **eight** occurrences, and here is every one of them:
   `intAGameInfoexecSynchSplitScreenSetting` (`0x00689640`),
   `IsSplitScreenCoopGame` (`0x0068AF60` and `0x0069B4E0`),
   `L_Split` (`0x00695B68`), `AGR3AmbianceSplitter` (`0x00696D60`),
   `P_SplitMenu` (`0x00698670` and `0x006A5A18`), and
   `R6Game.R6SplitPracticeModeGame` (`0x00699170`). The `IsSplitScreenCoopGame`
   pair are `FName`s reachable only from script; the rest are menu, audio or a
   class path. Nothing names a render-side suppression flag.

Caveat, stated plainly: this establishes that **R6 3's specific mechanism — the
`m_bHideInSplitScreen` property and the six hard-coded effect gates — is not in
GRAW**. It does not establish that GRAW has no split-screen effect degradation at
all; a rewritten renderer could degrade effects through a different, unnamed
path. Finding that would need a running capture, which is out of scope here.

Two anchors for whoever picks this up: the split-screen menu page is
`P_SplitMenu` (`0x00698670`), reached from function `0x004F9BB0` at site
`0x004FC5DC`; and entering a two-player mode writes `2` to the BSS word
`0x007B6084` and sets the `$gp`-relative byte at `-0x6924` (both at
`0x004B9D08`–`0x004B9D18`). The renderer-side flag, if there is one, is
downstream of those.

---

## Verification note

Every "current word" in the tables above was read from the `SP.IMG` extracted
from the retail ISO at LBA 268011 and disassembled in place. The command that
produced the table rows reads the word at `VA - 0x000FF800` in the segment-0
bytes and prints it alongside the decoded instruction; the decoded mnemonic in
each row's description is that tool's output, not a transcription. Spot-checked
rows and their decodes:

```
| `0x0058E3DC` | `0x8FA20038` | lw    $v0, 0x38($sp)      |
| `0x0058E4BC` | `0x3C023F80` | lui   $v0, 0x3f80         |
| `0x0058E4D8` | `0x4501001E` | bc1t  0x58e554            |
| `0x0058E508` | `0x24020001` | addiu $v0, $zero, 1       |
| `0x0058E540` | `0x2442FFFF` | addiu $v0, $v0, -1        |
| `0x00459688` | `0x28410002` | slti  $at, $v0, 2         |
| `0x004701C0` | `0x28410002` | slti  $at, $v0, 2         |
| `0x004701D8` | `0x28410078` | slti  $at, $v0, 0x78      |
| `0x004701E0` | `0x24020078` | addiu $v0, $zero, 0x78    |
```

No patch in this document has been applied to any file, and no emulator was run.

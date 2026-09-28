# RS3 PS2 (SLUS-20883) — split-screen enemy accuracy: native-code investigation

**Question.** Enemy accuracy is noticeably worse in split screen than in single
player. Find the split-screen-conditional code that degrades AI aim, dispersion,
reaction or observation, and give the 32-bit word that makes split-screen
accuracy match single player.

**Answer: a precise negative.** There is no split-screen-conditional AI-accuracy
code in the SP overlay. Every native channel by which the game can know it is in
split screen has been enumerated exhaustively (four channels, 82 accesses in
total, listed below). Not one of them lies in weapon, aim, dispersion,
line-of-sight, observation, reaction-timer, damage or AI-controller code. The
accuracy model itself is proven to be UnrealScript: its tuning constants live in
`[Engine.R6GameplaySettings]` and the native singleton for that class is read at
~100 distinct offsets, none of which is in the accuracy/skill/observation block.

Everything below is derived from `sp.bin`
(SHA-1 `e9bb12138a1e69d551ac9f6b958114e5b2e830da`, 5,585,280 bytes, re-verified
with `sha1sum` this session; file offset = VA − 0x00100000).

> **Every "current 32-bit word" quoted in this document was read out of `sp.bin`
> with `r6.w(va)` during this session.** None is copied from a prior document or
> reconstructed from a disassembly listing. The verification table is in
> section 6; the patch-candidate table in section 7 quotes only words that
> appear there.

---

## 1. Method

The flag `GameInfo->m_bIsSplitScreen` is bit 5 of the byte at `+0x3a2`. This
build extracts booleans with a `dsll32`/`dsra32` pair, never `andi` with a mask
(CONTEXT trap 2), so a test site is:

```
lbu     $rX, 0x3a2($rY)
dsll32  $rX, $rX, 26        ; capstone prints .word 0x000216bc / 0x00031ebc
dsra32  $rX, $rX, 31        ; capstone prints .word 0x000217fe / 0x00031ffe
beq/bne $rX, $zero, <target>
```

`dsll32 sa=26` shifts left by 32+26 = 58, putting bit 5 in bit 63; `dsra32 31`
then shifts right 63. Bit index = `31 − sa`, so `sa = 26` gives **bit 5**.

**Correction to the shared facts: there are 21 test sites, not 20.** The
previously documented count of 20 missed `0x0043155c`, where the compiler
interleaved unrelated instructions between the `lbu`, the shift pair and the
branch:

```
0043155c  lbu    $v0, 0x3a2($a1)        ; word 0x90a203a2
00431560  lw     $v1, 0x39c($v1)        ; <-- interleaved, breaks a naive scan
00431564  .word  0x000216bc             ; dsll32 $v0,$v0,26
00431568  addu   $a3, $a0, $v1          ; <-- interleaved
0043156c  .word  0x000217fe             ; dsra32 $v0,$v0,31
00431570  .word  0x00e0b82d             ; daddu $s7,$a3,$zero
00431574  beqz   $v0, 0x431580          ; word 0x10400002
```

A scanner that requires the three instructions to be adjacent finds 20. A
scanner that allows up to 5 intervening instructions and matches on register
liveness finds 21. The split is **14 `beq`** (block runs only in split screen)
and **7 `bne`** (block skipped in split screen) — not 13/7.

The same `0x3a2` byte carries other booleans, which a bare-offset scan also
turns up and which must not be confused with the split-screen bit:

| VA | extraction | bit | note |
|---|---|---|---|
| `0x001fb324` | `andi $v0,$v0,1` | 0 | different bool |
| `0x003a0dec` | `andi $v0,$v0,1` | 0 | different bool |
| `0x003a1018` | `andi $v0,$v0,1` | 0 | different bool |
| `0x003a0dc4` | `dsll32 ...,30` | 1 | different bool |
| `0x003cd110` | `dsll32 ...,27` | 4 | different bool |
| `0x005a6214` | — | — | not code; matches inside data |

`sb`/`sh`/`sw` to `+0x3a2`: **zero sites**. Native code never writes
`m_bIsSplitScreen`; it is set from the script/property side only.

---

## 2. All 21 `m_bIsSplitScreen` test sites, re-triaged

Each row was read from disassembly this session, not inherited from the
2026-09-13 triage. The final column answers the assignment's question directly:
does this site touch weapon aim, dispersion/spread, a random roll, a skill
multiplier, a reaction timer, or a line-of-sight/observation test?

| # | test VA | branch | sense | What the guarded code actually does | Aim / dispersion / skill / LOS? |
|---|---|---|---|---|---|
| 1 | `0x002007c4` | `0x002007d0` `beqz` | SS-only | Analogue-stick magnitude / deadzone evaluation on a `PlayerController`. Loads threshold `cfg+0x264` from the `R6GameplaySettings` singleton `*(gp-0x6700)`; in SS it picks the **per-player** stick axes from BSS (`0x00654404/08/0c/10`, chosen by `controller+0x4d0` player index), in SP the global pair. Result is `abs(x)`, `abs(y)` compared via the software-double `fabs` triple (`0x411e40` f→d, `0x126928` fabs, `0x4128d8` d→f), written to `pawn+0x37e` (signed byte) and `controller+0x370` / `pawn+0x3b8` bit 1. **Player input, not AI.** | No |
| 2 | `0x0021d9ec` | `0x0021d9f8` `beqz` | SS-only | Per-player input settings copy. SS branch copies `*(gp-0x6704)+0x31/0x32` (P1 X/Y look step) or `+0x33/0x34` (P2) into `controller+0x4a1/0x4a2`, `+0x4c`/`+0x50` button scheme into `+0x4a0`, and the `+0xcc/+0xcd` option bits into `+0x4d8`. (The 2026-09-13 triage called this "the Xbox Live path"; it is not.) | No |
| 3 | `0x0029c13c` | `0x0029c148` `beqz` | SS-only | Pad rumble. SS → `0x001aca50(f12 = v/255.0, a0 = player index)`; SP → `0x001acb60(f12)` with no index. Both write the rumble globals at `gp-0x66a4`/`gp-0x66b0` and gate on `gp-0x5b14`. | No |
| 4 | `0x00317564` | `0x00317570` `bnez` | SS-skips | **Animation/mesh LOD gate** inside the 13.6 KB per-actor render+animate function `0x003171b8..0x0031a6e4`. Reached only for actors with `0x3bd` bit 4 set and `0x378 != 1`; `0x3bd` bit 5 means "already updated this frame". SP rule: full update iff `(*(int64*)0x00653748 − actor->0x2d8) < 61` (frame counter; `0x2d8` is stamped at `0x0031a698` on a full pass). SS rule: full update iff `LevelInfo->0x45c (TimeSeconds) − actor->0x454 (LastRenderTime) <= 3.0`. The cheap path (`0x003175a0` / `0x00317624`) sets `0x3bd` bit 5, calls vtable `+0xa4` on `actor->0x2e4`, and skips the rest of the pass. **This is the only one of the 21 with any conceivable indirect bearing on aim** (stale bone transforms), and the SS window is the *more* permissive of the two. No aim, dispersion, skill or LOS term appears anywhere in either branch. | Indirect at best; **no** aim math |
| 5 | `0x003a0f58` | `0x003a0f64` `beqz` | SS-only | Pad rumble again: SS → `0x001ac980(0.6, 2.0, a0 = player index)`, SP → `0x001acad0(0.6, 2.0)`. Constants `0x3f19999a` = 0.6, `0x40000000` = 2.0. | No |
| 6 | `0x003a14ac` | `0x003a14b8` `bnez` | SS-skips | Audio-listener update. SP writes listener position `0x1b0..0x1bc` and orientation `0x1c0..0x1c8` into the global at `0x006dd6c8`, then calls `0x0056e610`. Skipped in SS (two listeners cannot share one global). | No |
| 7 | `0x003a4978` | `0x003a4984` `bnez` | SS-skips | Terminates the walk of `LevelInfo->0x528` (controller list, `next` at `+0x3b0`) after the first entry when in SS. The loop body builds a parameter block and calls a script event by FName (`gp-0x5f84`) through `0x00184170` + vtable `+0x18` (ProcessEvent) — a broadcast/notification. | No |
| 8 | `0x003b6194` | `0x003b61a0` `beqz` | SS-only | Head of the HUD per-player loop `0x003b6160..0x003b6b38`. SS: `$fp = 2`. SP: `$fp = PlayerList->0x37c` (`0x78c($s4)` then `+0x37c`). `$fp` is the loop bound for the per-player HUD draw. | No |
| 9 | `0x003b6ae0` | `0x003b6aec` `bnez` | SS-skips | Bottom of the same loop: SP does `$s2--` before the `$s2++`, SS does not — the SP pass repeats the entry, the SS pass advances. Pure HUD iteration control. | No |
| 10 | `0x003b6c14` | `0x003b6c20` `beqz` | SS-only | Second HUD loop (`0x003b6ba4`). SS: `$s7 = 2`. SP: `$s7 = PlayerList->0x37c + PlayerList->0x39c`. Feeds `0x0013c3d0` timing-bar writes into the `gp-0x66e4 + 0x54` float array. | No |
| 11 | `0x003cc6d8` | `0x003cc6e4` `beqz` | SS-only | Pad rumble, third instance, reached from the UnrealScript token executor (`jal 0x161810` immediately before). SS → `0x001aca50(f, playerIdx)`, SP → `0x001acb60(f)`. | No |
| 12 | `0x003e23ec` | `0x003e23f8` `beqz` | SS-only | Scene-render entry `0x003e22d8..0x003e49d0`. In SS it additionally requires `PlayerController->0x4d9` bit 5 clear before rendering; the whole function is already gated on `*(gp-0x6704)+0xcd` bit 5. Pure render gating. | No |
| 13 | `0x003e24bc` | `0x003e24c8` `beqz` | SS-only | Same function: SS calls viewport vtable `+0x74` and `+0x94` with `(0, 0, 0x280, 0x1e0)` and then sets `s4+0x524 = width/640.0`, `s4+0x528 = height/480.0` — HUD/render scale factors for a half-height viewport. | No |
| 14 | `0x003e4938` | `0x003e4944` `beqz` | SS-only | Tail of the same function: SS calls viewport vtable `+0x78` (the matching "end" of the `+0x74` above) before `0x0034a6d0`. | No |
| 15 | `0x003e7cb0` | `0x003e7cbc` `beqz` | SS-only | Top of the 34 KB render function `0x003e7488..0x003efa7c`. In SS it calls `0x003dbfd0` and returns, skipping `0x003e7cec..0x003efa34` entirely. `0x003dbfd0` is the split-viewport renderer — it reads `controller->0x4d0` and computes `idx*2 − 1` (−1 for player 0, +1 for player 1), the half-screen offset. | No |
| 16 | `0x003f1928` | `0x003f1934` `bnez` | SS-skips | Render function `0x003f1180..0x003f33ac`; SS skips a block additionally gated on `gp-0x72bc` and a `0x80` flag bit on a material record. Rendering. | No |
| 17 | `0x003f1ba8` | `0x003f1bb4` `bnez` | SS-skips | Same function, second skipped render block (calls vtable `+0x90` on `0x12c` of an object with type byte `0x2f == 2`). | No |
| 18 | `0x003f2500` | `0x003f250c` `bnez` | SS-skips | Same function, third skipped render block (`0x003f08c0` with two vectors and a mode `2`). | No |
| 19 | `0x003f6938` | `0x003f6944` `beqz` | SS-only | Render function `0x003f6018..0x003f6ad0`. SS and SP take structurally identical paths that differ only in an extra `$s0 == $s1` test (is this the viewport's own player) in the SP path before calling vtable `+0x90`. First-person/third-person model selection per viewport. | No |
| 20 | `0x00407918` | `0x00407924` `beqz` | SS-only | Proximity trigger actor, function `0x004075c8..0x00407c10`. Every `0x67c` seconds (reset to 0.5) it tests whether any player pawn is inside radius `actor->0x698->0x394`. SS path reads local players `[0]` and `[1]` from `*(gp-0x6f44)->0x44->0x30`; SP path walks `PlayerList->0x78c` with count `+0x37c`. Both compute the same squared-distance test and fire the same script event (`gp-0x5a7c`). Functionally equivalent; SS is just a fixed 2-entry unroll. | No |
| 21 | `0x0043155c` | `0x00431574` `beqz` | SS-only | **The site the previous pass missed.** End-of-round / stats screen, function `0x004314c4..0x00431ef0`. SS: `$s7 = 2`. SP: `$s7 = PlayerList->0x37c + PlayerList->0x39c`. It then copies up to 4 `0x3c0` player records into `s1->0x78c`, and later computes a percentage `(score*5*5*4)/total` clamped to 100 — a stats bar. | No |

**Result: 21 of 21 are input, rumble, HUD, audio-listener, render/viewport,
stats, actor-iteration or animation-LOD. None reads or writes a weapon, aim,
dispersion, skill, reaction or observation quantity.**

---

## 3. All 13 reads of `GameEngine->m_SplitScreenMode` (+0x4e4)

Derived with `r6.scan_mem({0x23,0x24,0x25,0x20,0x21}, 0x4e4)`.

| VA | shape | What it gates |
|---|---|---|
| `0x0023758c` | `beqz` then set 1 | engine init flag |
| `0x00238bc4` | `beqz` then set 1 | engine init flag (sibling of the above) |
| `0x0027b2ec` | `beqz` then set 1 | engine init flag |
| `0x002e84d4` | value used directly | viewport/client setup |
| `0x002e8870` | `beqz` | writes `s6+0x56c` — viewport setup |
| `0x002f0764` | `bnez` then skip vtable `+0x84` | client |
| `0x002f6924` | `beqz` then skip | client |
| `0x002fa190` | `== 1`? | **gametype substitution**: mode 1 sets mode byte `*(gp-0x66e4)+0x31 = 11` and URL `GAME=R6Game.R6PracticeModeGameForSplitScreen` |
| `0x002fa3f4` | `beqz` then skip | same path, second stage |
| `0x00302d8c` | OR with `gp-0x6ffc`, store back | `m_SplitScreenMode` is *written* here from the URL options `SSC`→1 / `SST`→2 (`0x00302d58/84/88`) |
| `0x00302d9c` | `beqz` | clears `gp-0x7f34` |
| `0x00304104` | `bnez` | level-load path |
| `0x00351e68` | `beqz` then byte flag | audio |

Mode 2 is handled at `0x002fa238` (`== 2` sets mode byte 10 and URL
`GAME=R6Game.R6TerroristHuntGameForSplitScreen`).

Every one of these is below `0x00352000`, i.e. in engine/client/URL code.
**None is in the 0x0038xxxx–0x0046xxxx game/AI/weapon band.**

---

## 4. Two further split-screen channels the shared facts did not list

The bit-5 flag and `+0x4e4` are not the only ways native code can know it is in
split screen. Two more exist, plus a game-mode byte, and all are now enumerated.

### 4a. `g_bSplitScreen` at `gp-0x7050` = `0x006546a0`

Set once at boot (`0x001bca0c..0x001bca6c`): true if the command line contains
`-sst` **or** `-ssc`, unless `gp-0x6ffc` (`-splitscreen`) overrides. **Exactly
6 accesses (1 store, 5 loads):**

| VA | Use |
|---|---|
| `0x001bca6c` | the store |
| `0x001bca70` | selects the script package filename: `common_ss.lin` vs `commonoff.lin` (`0x001bca7c` / `0x001bca98`) |
| `0x001c6d64` | boot-time mode/config selection |
| `0x002f7b5c` | appends `_S` to a level package name |
| `0x002f7bd4` | appends `_ss` vs `off` to a level package name |
| `0x00472160` | **leaf function**: `return g_bSplitScreen ? 3 : 6;` |

`0x00472160` is the only place in the overlay where split screen selects a
*different numeric constant*, so it was chased to the end. Its single caller is
`0x004ca230`, whose callers are `0x004e34a4` and `0x004e3868`, and whose format
string is at `0x005f1da0`:

> `There are currently more than %d Streaming Source playing at the same time !`

It is the **audio streaming voice budget**: 3 concurrent streaming sources in
split screen, 6 in single player. Not accuracy.

(Note also: prior verified work established that `COMMONOFF.LIN` and
`COMMON_SS.LIN` are byte-identical, so the `common_ss` / `commonoff` selection
changes only the registered package name, not any data.)

### 4b. `-splitscreen` developer override at `gp-0x6ffc` = `0x006546f4`

Set at `0x001c4ff4` from `ParseParam(cmdline, "splitscreen")` (string at
`0x005dbd40`). 38 accesses. Its only gameplay-visible effect is at `0x002fa1a4`
and `0x002fa244`, where a non-zero value **suppresses** the `ForSplitScreen`
gametype substitution; the remaining reads are menu/HUD/front-end
(`0x0043xxxx`, `0x0048xxxx`, `0x004bxxxx`, `0x0056xxxx`). Retail never passes
the parameter, so it is 0 in play.

### 4c. Game-mode byte `*(gp-0x66e4)+0x31`

Split screen sets this to 10 (`SST`) or 11 (`SSC`); single player uses other
values. It has only **4 read sites**: `0x002fa490` and `0x002fa554` (both in the
URL-building path, comparing against 11) and `0x0040ba74`, `0x0040bb50` (both
comparing against **1**, a HUD path). Nothing in AI code reads it.

**Channel total: 21 + 13 + 6 + 38 + 4 = 82 accesses across four channels, none
of them in aim, dispersion, skill, reaction or line-of-sight code.**

---

## 5. Working backwards from the accuracy model: it is UnrealScript

### 5a. The tuning constants are config properties of one native singleton

`config/R6GAMESETTINGS.INI` has a single `[Engine.R6GameplaySettings]` section
holding `m_fDistForPerfectAccuracyTerro/Rainbow=500.0`,
`m_fBaseObservationSkillFactor=0.75`, `m_fObservationSkillRange=0.5`,
`m_fTerroristSkillMultiplierRecruit/Veteran/Elite=0.20/0.70/1.25`,
`m_fReactionTimeForFiringRecruit/Veteran`, `m_fSightRadius=5000.0` and the
spotter/target/light penalty factors. **There is no split-screen section and no
split-screen variant of any of those keys.** The file has only six sections:
`Engine.R6GameplaySettings`, `R6Abstract.R6AbstractHUD`, `R6Game.R6HUD`,
`R6Engine.R6InteractionRoseDesVents`,
`R6Engine.R6InteractionCircumstantialAction`, `Engine.R6AbstractGameManager`.

`r6.find_float()` confirms the literals are not in the overlay's data: 500.0
gives 0 hits; 0.75 gives 0 hits; 0.20 gives 1 hit at `0x005cc860`; 0.70 gives 1
hit at `0x005f5ef0`; 1.25 gives 1 hit at `0x005be6ac` — and no `lui`/`lwc1` pair
addresses any of those three. The two `lui $v0, 0x43fa` (= 500.0) immediates at
`0x0041f1f4` and `0x0041f404` are a debris-scatter speed (`500 + 500*FRand()`)
inside a vtable-only function that normalises a per-fragment velocity — not the
perfect-accuracy distance.

### 5b. The singleton is `*(gp-0x6700)` = `*(0x00654ff0)`, and native code never reads the accuracy block from it

126 `lw rX, -0x6700($gp)` sites were followed one hop to the field actually
loaded. That yields the complete native view of `R6GameplaySettings`: about 100
distinct offsets in `+0x000 .. +0x350`. Every one resolves to camera, viewport,
HUD, reticle, recoil-display or render code:

* `+0x108`, `+0x208..+0x280` — the per-viewport look/camera copy at `0x0013fe38`
  and the look computation at `0x001430e8` / `0x001432d8`;
* `+0x154..+0x178` — view/recoil display (`0x0039d9d0`, `0x003a9ed8`,
  `0x003aa238`, `0x003aa270`, `0x003f5xxx`);
* `+0x064..+0x0a0`, `+0x1a4..+0x1b8`, `+0x2a0..+0x2c8`, `+0x30c..+0x328` —
  HUD/reticle (`0x003ccxxx`, `0x003cdxxx`, `0x003f6cxx`, `0x0042ccxx`);
* `+0x2fc` (8 reads at `0x003a19ac..0x003a1b6c`) — an 8-element view table.

**None of the accuracy, sight-radius, observation-skill, terrorist-skill or
reaction-time properties is read by any native instruction.** They are
script-only, so the dispersion formula that consumes them is script-only too.

### 5c. The AI's combat verbs are script names, not native functions

The overlay's FName string pool carries the AI combat vocabulary as *script*
identifiers, invoked through `0x00184170` (FindFunction by FName) plus vtable
`+0x18` (ProcessEvent): `StartAttack`, `StopAttack`, `AttackTimer`,
`IsBeingAttacked`, `GotoStateEngageByThreat`, `GotoPointToAttack`,
`GotoStateAttackActionSpot`, `ReloadAttack`, `ReplicateBulletHit`,
`WhichBodyPartWasHit`, `EnemyNotVisible`, `GetSkill`, `Action_Engage`. The only
*native* combat entry points are the `exec` thunks
`intAControllerexecCanSee` (`0x005dcf90`),
`intAControllerexecLineOfSightTo` (`0x005dcf70`) and
`intAPawnexecIsEnemy` (`0x005dcdb0`) — i.e. script asks native for a raw
visibility answer and does the skill/accuracy arithmetic itself.

`COMMON.LIN` (decompressed to 5,102,267 bytes with `tools/lin.py`) confirms it:
the name table carries `m_fDistForPerfectAccuracyTerro`,
`m_fDistForPerfectAccuracyRainbow`, `m_fBaseObservationSkillFactor`,
`m_fObservationSkillRange`, `m_fTerroristSkillMultiplierRecruit/Veteran/Elite`,
`m_fRainbowSkillMultiplier`, `m_fTerroSkillMultiplier`, `m_fFiringReactionTime`,
`m_fReactionTimeForFiringRecruit/Veteran`, `SetAccuracyOnHit`,
`IsAtBestAccuracy`, `GetSkill`, `SKILL_Observation` — **and** `m_bIsSplitScreen`,
`m_bSplitScreen`, `m_bHideInSplitScreen`, `mSplitScreenMode`. Both halves of the
question live in the same script package.

The `..\Template\*.tpt` operative-template parser strings
(`Observation=`, `SelfControl=`, `Leadership=`, `Stealth=`, `Assault=`,
`PSniper=`, `Coward=`, `SuicideBomber=`, `NbOfSeePlayerEvent=`,
`NbOfHearPlayerEvent=`, at `0x005e4ed8..0x005e5000`) are present in the overlay
but **have no code reference at all** — no `lui`/`addiu` pair anywhere forms
those addresses, and a raw scan for the immediate `0x4f80` finds only `ori`
instructions unrelated to `0x5e0000`. The PC-side template parser was stripped;
the PS2 build reads skills from cooked script data.

### 5d. The native dispersion-looking code that does exist is the player's view recoil, not AI aim

`0x003b8854..0x003b8d9c` is the one native function that generates a random
angular offset. It maintains, on its `$a0` object:

```
+0x764  secondary recovery timer        +0x76c  error magnitude (decays)
+0x768  primary error timer             +0x770  time to next re-roll
+0x774  base re-roll interval           +0x7ac/+0x7b0/+0x7b4  current offsets
```

At `0x003b8b30..0x003b8bb0` it re-rolls each offset as
`(int)(-m + 2*m*FRand())` with `m = +0x76c`, then at `0x003b8ba8` sets
`+0x770 = +0x774 * FRand()`. The offsets are consumed at `0x003f4f0c`,
`0x003f4f1c`, `0x003f4f2c` and `0x003f583c`, `0x003f584c`, `0x003f585c` — both
inside the **view/camera** code. `+0x764` and `+0x7ac..+0x7b4` are also written
by `0x003aa268..0x003aa28c`, which scales the kick by `R6GameplaySettings+0x158`
and sets `+0x764 = 0.2f`. The whole group is copied in from an archetype at
`0x002ad864..0x002ad888` (`+0x694..+0x6a8` → `+0x764..+0x774`) and at
`0x002bb978..0x002bb9b4`. It is weapon recoil applied to the view. It is
frame-rate-correct (everything is scaled by the `f12` delta-time argument) and
**contains no split-screen test** — which follows automatically from section 2
being exhaustive.

### 5e. The difficulty selector is not a split-screen channel either

`GameInfo+0x4c8` (1 = Recruit, 2 = Veteran, 3 = Elite) has 11 read sites:
`0x00265d10`, `0x002ef4b0`, `0x003af1fc`, `0x0040af68`, `0x0054a834`,
`0x0054a890`, `0x0059a090`, `0x0059a398`, `0x0059a3ec`, `0x0059b0c0`,
`0x0059b0e4`. The two in game code are `0x0040af68` (`AR6DZoneWave` init at
`0x0040af08` — adds `+0x470` or `+0x474` to the wave count for Veteran/Elite)
and `0x003af1fc` (scales a noise/stimulus magnitude by `difficulty*2`, then
`0.5 + that`). Neither is reached from any split-screen branch.

Reads of `GameInfo` fields generally are sparse: following all 161
`lw rX, 0x520(rY)` sites one hop gives only `+0x000, +0x370, +0x371, +0x374,
+0x388, +0x39c, +0x3a2, +0x3bc, +0x4c8, +0x4cc, +0x4d0, +0x4ec`. There is no
native read of a per-skill accuracy field on `GameInfo`.

### 5f. The `ForSplitScreen` gametype classes are already a refuted mechanism

Split screen does substitute a different GameInfo class name into the URL
(`0x002fa1b8` → `R6Game.R6PracticeModeGameForSplitScreen`, `0x002fa258` →
`R6Game.R6TerroristHuntGameForSplitScreen`, plus
`R6Game.R6SharpShooterGameForSplitScreen`). Prior work
(`SPLITSCREEN_HANDOFF.md`, tested 2026-09-01) overwrote all five occurrences of
each `ForSplitScreen` name in both overlays with the single-player name and
booted: split-screen behaviour was unchanged. So the class name is **not** what
selects split-screen behaviour; the mechanism is the `m_bIsSplitScreen` flag
read from UnrealScript. That is consistent with everything above, and it is why
patch candidate P3 below is not recommended.

---

## 6. Machine verification of every quoted word

All of the following were read with `r6.w(va)` from `sp.bin` **this session**:

| `lbu` site | word | branch site | word | disassembly |
|---|---|---|---|---|
| `0x002007c4` | `0x904203a2` | `0x002007d0` | `0x1040000b` | `beqz $v0, 0x200800` |
| `0x0021d9ec` | `0x904203a2` | `0x0021d9f8` | `0x10400054` | `beqz $v0, 0x21db4c` |
| `0x0029c13c` | `0x904203a2` | `0x0029c148` | `0x1040000d` | `beqz $v0, 0x29c180` |
| `0x00317564` | `0x906303a2` | `0x00317570` | `0x1460001d` | `bnez $v1, 0x3175e8` |
| `0x003a0f58` | `0x904203a2` | `0x003a0f64` | `0x1040000a` | `beqz $v0, 0x3a0f90` |
| `0x003a14ac` | `0x904203a2` | `0x003a14b8` | `0x14400015` | `bnez $v0, 0x3a1510` |
| `0x003a4978` | `0x906303a2` | `0x003a4984` | `0x1460002c` | `bnez $v1, 0x3a4a38` |
| `0x003b6194` | `0x906303a2` | `0x003b61a0` | `0x10600003` | `beqz $v1, 0x3b61b0` |
| `0x003b6ae0` | `0x906303a2` | `0x003b6aec` | `0x14600002` | `bnez $v1, 0x3b6af8` |
| `0x003b6c14` | `0x904203a2` | `0x003b6c20` | `0x10400003` | `beqz $v0, 0x3b6c30` |
| `0x003cc6d8` | `0x904203a2` | `0x003cc6e4` | `0x1040000a` | `beqz $v0, 0x3cc710` |
| `0x003e23ec` | `0x906303a2` | `0x003e23f8` | `0x10600006` | `beqz $v1, 0x3e2414` |
| `0x003e24bc` | `0x904203a2` | `0x003e24c8` | `0x10400030` | `beqz $v0, 0x3e258c` |
| `0x003e4938` | `0x904203a2` | `0x003e4944` | `0x10400008` | `beqz $v0, 0x3e4968` |
| `0x003e7cb0` | `0x904203a2` | `0x003e7cbc` | `0x1040000b` | `beqz $v0, 0x3e7cec` |
| `0x003f1928` | `0x904203a2` | `0x003f1934` | `0x1440004f` | `bnez $v0, 0x3f1a74` |
| `0x003f1ba8` | `0x904203a2` | `0x003f1bb4` | `0x14400084` | `bnez $v0, 0x3f1dc8` |
| `0x003f2500` | `0x904203a2` | `0x003f250c` | `0x14400014` | `bnez $v0, 0x3f2560` |
| `0x003f6938` | `0x906303a2` | `0x003f6944` | `0x10600019` | `beqz $v1, 0x3f69ac` |
| `0x00407918` | `0x904203a2` | `0x00407924` | `0x1040006b` | `beqz $v0, 0x407ad4` |
| `0x0043155c` | `0x90a203a2` | `0x00431574` | `0x10400002` | `beqz $v0, 0x431580` |

Supporting words, also read with `r6.w()` this session:

| VA | word | disassembly |
|---|---|---|
| `0x003175f4` | `0x1460000b` | `bnez $v1, 0x317624` (bit 6 of `0x3bd`, SS branch) |
| `0x0031761c` | `0x45010013` | `bc1t 0x31766c` (SS: `TimeSeconds − LastRenderTime <= 3.0`) |
| `0x0047216c` | `0x03e00008` | `jr $ra` |
| `0x00472170` | `0x0064100a` | `movz $v0, $v1, $a0` (delay slot: 3 if SS else 6) |
| `0x002fa198` | `0x14620027` | `bne $v1, $v0, 0x2fa238` (`m_SplitScreenMode == 1`?) |
| `0x002fa238` | `0x14620024` | `bne $v1, $v0, 0x2fa2cc` (`m_SplitScreenMode == 2`?) |

---

## 7. Patch candidates

There is **no word that is known to make split-screen enemy accuracy match
single player**, because no native instruction makes them differ. The following
are offered only as the strongest available probes; each is labelled with what
it is actually known to do, and every "current word" appears in section 6.

| # | VA | Current word | Proposed word | Effect | Risk |
|---|---|---|---|---|---|
| P1 | `0x00317570` | `0x1460001d` | `0x00000000` (`nop`) | Makes split screen use the **single-player animation-LOD rule** (frames since last full pass < 61) instead of the LastRenderTime rule. The only one of the 21 sites with any path, however indirect, to AI aim (stale bone transforms giving stale muzzle/target positions). **Not proven to affect accuracy.** | Medium. Changes how often skeletal meshes animate in split screen; can cost frame time or visibly freeze distant animation. Purely diagnostic — if enemy accuracy is unchanged, the animation-LOD hypothesis is dead. |
| P2 | `0x00472170` | `0x0064100a` | `0x0060102d` (`daddu $v0,$v1,$zero`, always 6) | Restores the single-player **audio streaming voice budget** (6 instead of 3) in split screen. Listed for completeness because it is the only place in the overlay where split screen selects a different number. **It is audio, proven by the format string at `0x005f1da0`; it is not an accuracy fix.** | Low functionally, but it raises streaming-voice memory/bandwidth on the mode that was deliberately budgeted down — can cause audio dropouts or streaming stalls. |
| P3 | `0x002fa238` | `0x14620024` | `0x10000024` (`beq $zero,$zero,0x2fa2cc`) | Stops the split-screen Terrorist Hunt gametype substitution, so split screen runs `R6TerroristHuntGame` and inherits the single-player GameInfo defaults. | **High, and probably pointless.** The equivalent name-swap experiment was run on 2026-09-01 and was inert, so the class is not what carries the behaviour; and if `m_bIsSplitScreen` is a default of the `ForSplitScreen` class, clearing it would disable all 21 sites at once — HUD layout, rumble routing, audio listener and the split-viewport renderer — while the screen still splits (that is driven by `m_SplitScreenMode`, set independently from the URL). Do not ship. |

**The honest recommendation is none of the above.** The next probe should be on
the script side (section 8).

---

## 8. What the next probe should be

1. **Find the `m_bIsSplitScreen` tests in UnrealScript.** `COMMON.LIN`
   decompresses cleanly (`tools/lin.py`, 312 zlib chunks, 5,102,267 bytes) and
   its first sub-package parses: version 123, licensee 22, 6219 names, 83
   imports, 7476 declared exports, with `m_bIsSplitScreen` at name index 3280.
   The blocker is the documented one: the LIN is a concatenation of roughly
   110–136 cooked sub-packages and `upkg.Package` locks onto the first magic
   (at `0x9e17`), so `exportOff` (`0x133bbe`) points past the end of that
   sub-package's own data and the export records decode to garbage (export 6
   yields `size = -17179869183`). **Fix that first:** walk every
   `C1 83 2A 9E` magic in the decompressed blob, parse each sub-package header
   independently, and locate the one whose name table contains
   `m_bIsSplitScreen`. Then resolve its export index and scan every
   `UStruct`-class export's bytecode for `EX_InstanceVariable` /
   `EX_DefaultVariable` referencing that index. The set of functions that test
   it is the complete answer to this question, and it will be small.
2. **Cross-check against the accuracy side.** In the same sub-package, do the
   same for `m_fDistForPerfectAccuracyTerro` (name 5843),
   `m_fTerroSkillMultiplier` (2325), `m_fFiringReactionTime` (5848) and
   `SetAccuracyOnHit` (2118) / `IsAtBestAccuracy` (2172). Any function that
   appears in both sets is the site.
3. **If step 1 finds no split-screen test in the accuracy path**, the remaining
   explanation is emergent rather than authored: split screen roughly halves the
   frame rate, and any part of the AI decision loop that is per-Tick rather than
   per-second runs at half rate. That is testable statically by checking whether
   the script's firing-reaction and aim-error updates consume `DeltaTime` — the
   native recoil decay at `0x003b8854` does, correctly; the script need not.

---

## 9. Corrections and additions to the shared facts in `CONTEXT.md`

* **`m_bIsSplitScreen` has 21 native test sites, not 20.** The extra one is
  `0x0043155c` (end-of-round stats screen); the scan signature must tolerate
  instructions interleaved between the `lbu`, the `dsll32`/`dsra32` pair and the
  branch. The split is 14 `beq` / 7 `bne`, not 13/7.
* **Native code never writes byte `+0x3a2`** — zero `sb`/`sh`/`sw` sites. The
  flag is set entirely from the script/property side.
* **There are two further split-screen channels** not previously listed:
  `g_bSplitScreen` at `gp-0x7050` = `0x006546a0` (set from `-sst`/`-ssc` at
  `0x001bca6c`; 5 readers, including the `common_ss.lin`/`commonoff.lin` choice
  and the audio streaming-budget leaf `0x00472160` returning 3 vs 6), and the
  `-splitscreen` developer override at `gp-0x6ffc` = `0x006546f4` (38 readers;
  when set it *suppresses* the `ForSplitScreen` gametype substitution). A third,
  the game-mode byte `*(gp-0x66e4)+0x31` (10 = SST, 11 = SSC), has only 4
  readers, none in AI code.
* **`*(gp-0x6700)` = `0x00654ff0` is `Engine.R6GameplaySettings`**, the object
  configured by the `[Engine.R6GameplaySettings]` section of
  `R6GAMESETTINGS.INI` — not merely "a global tuning-config object". Native code
  reads about 100 of its offsets in `+0x000..+0x350`, all camera / HUD /
  reticle / recoil-display; the accuracy, skill and observation properties are
  script-only. `+0x158` is the view-recoil scale (`0x003aa238`, `0x003aa270`),
  `+0x264` a stick threshold.
* **`0x00146d90` is `FRand()`** — `rand()/2^31` via `0x0012d5c8`; 165 callers.
  `0x00146df0` is the integer `Rand()`.
* **`0x00411e40` / `0x00126928` / `0x004128d8` are software-double helpers**
  (float→double, `fabs`, double→float). A `jal 0x411e40; jal 0x126928;
  jal 0x4128d8` triple is `fabs(x)`, not a game computation. Worth knowing
  before mis-reading `0x00200760`.
* **`0x003b8854..0x003b8d9c` is the weapon/view recoil-and-sway tick**
  (`+0x764/+0x768/+0x76c/+0x770/+0x774` timers and magnitude,
  `+0x7ac/+0x7b0/+0x7b4` current angular offsets, consumed by the view code at
  `0x003f4f0c` and `0x003f583c`). It is **not** AI shot dispersion.
* **`0x003171b8..0x0031a6e4` is the per-actor render + animation pass**, not a
  level tick loop: it stamps the global frame counter at `0x00653748` into
  `actor->0x2d8` at `0x0031a698` on a full pass, uses `actor->0x454` as
  LastRenderTime, `actor->0x2e4` as the mesh instance (animation update is
  vtable `+0xa4`), and `actor->0x3bd` bits 4/5/6 as the LOD flags.
* **`0x003dbfd0` is the split-viewport renderer** (`controller->0x4d0 * 2 − 1`
  gives −1/+1, the half-screen selector); `0x003e7488` delegates to it at
  `0x003e7cc4` and skips its own 34 KB body in split screen.
* The 2026-09-13 triage's label "the Xbox Live path" for `0x0021d9ec` is wrong;
  it is the per-player input-settings copy, confirmed independently here from
  `0x0021da10..0x0021da8c`.
* The `..\Template\*.tpt` skill-parser strings at `0x005e4ed8..0x005e5000`
  (`Observation=`, `SelfControl=`, `Leadership=`, `Stealth=`, ...) are **dead
  data**: no instruction in the overlay forms any of those addresses. Do not use
  them as an anchor.

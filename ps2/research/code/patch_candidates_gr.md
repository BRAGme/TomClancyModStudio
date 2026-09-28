# Patch candidates — Ghost Recon (PS2, SLUS-20613)

**None of these were tested.** No emulator was launched. Every "current word" below was
read out of `SLUS_206.13` with a tool this session and every proposed word was
hand-assembled; the *effect* column is an inference from the surrounding
disassembly, which is given in `features_gr.md`. Treat each row as a hypothesis with
a known-good address and a known-good current value.

The ELF is `ET_EXEC` with absolute addresses and the PS2 loader ignores the section
table, so **virtual address == pnach address**. Serial for the pnach filename is
`SLUS-20613`; the CRC must come from PCSX2's console log for the user's dump.

Risk key: **L** = single word, local, reversible; **M** = changes a size/limit that
other code reads back correctly but costs memory or performance; **H** = changes
control flow that other subsystems depend on, likely to have side effects.

---

## A. Decals / bullet impact marks

| # | VA | current | proposed | risk | effect |
|---|---|---|---|---|---|
| A1 | `0x0046D9D0` | `24050014` | `240500C8` | M | `BulletHoleManagerPS2` array sized 20 → **200** holes. Must be applied with A2. Costs 200×48 = 9,600 B of heap instead of 960 B. |
| A2 | `0x0046D9EC` | `24020014` | `240200C8` | M | the matching clear-loop bound 20 → 200. Applying A1 without A2 leaves 180 entries with an uninitialised active flag. |
| A3 | `0x00249638` | `3C0341F0` | `3C03447A` | L | default bullet-hole lifetime `30.0f` → `1000.0f`. Holes persist until the pool wraps. |
| A4 | `0x00249740` | `3C024000` | `3C02447A` | L | lifetime for surface types `0x12`, `0x13`, `0x16` `2.0f` → `1000.0f`. Same idea for the short-lived surface class. |
| A5 | `0x002496EC` | `1000001B` | `00000000` | M | removes the "unknown surface type → no decal at all" early-out in `DisplayBullethole`. Execution falls through to `0x002496F4`, which selects decal texture 0 at the default size, so **every** surface gets a bullet hole. |
| A6 | `0x00249648` | `3C033ECC` | `3C033F00` | L | default decal size `0.4f` → `0.5f`. Pair with A7 (the low half). |
| A7 | `0x0024964C` | `3463CCCD` | `34630000` | L | low half of A6. Apply A6+A7 together or not at all. |

Shrink instead of grow: A1/A2 = `24050004`/`24020004` gives a 4-hole pool (a cheap
way to prove the pool size is the thing you think it is).

```
// A. decals
patch=1,EE,0046D9D0,word,240500C8
patch=1,EE,0046D9EC,word,240200C8
patch=1,EE,00249638,word,3C03447A
patch=1,EE,00249740,word,3C02447A
patch=1,EE,002496EC,word,00000000
```

---

## B. Split-screen effect suppression (the highest-value finding)

`CGraphicSystem + 0x2880` is the split-screen boolean — proved by
`IsEnableSplitScreen__14CGraphicSystemFv` at `0x003ADE90`, which is nothing but
`jr $ra; lbu $v0,0x2880($a0)`, and `EnableSplitScreen__14CGraphicSystemFb` at
`0x0044EBB0`, which is `jr $ra; sb $a1,0x2880($a0)`.

The effects code branches on it in ten places. In `EffMgrPS2::Render` the split
branch skips an entire block that contains **bullet holes, foliage, birds** and the
hot-air/sorted-object collection; the reduced split-screen block further down re-runs
indicators, water ripples, LCD, muzzle flashes, tracers, haloes, static light,
billboards, sorted objects and blood pools, but **never** bullet holes, foliage or
birds. This is the same suppression pattern as the Rainbow Six 3 split-screen
problem, located statically in the sister engine.

Complete gate list (all read `0x2880`; branch taken == split screen unless noted):

| VA | word | function | what is skipped |
|---|---|---|---|
| `0x0024C8B8` | `14400009` | `IkeEffectsMgr::AddGeneralEffects+0xa44` | 9 instructions |
| `0x0024EF38` | `14E0006A` | `IkeEffectsMgr::CreateGeneralEffect+0x10d4` | **106 instructions (424 B)** — the biggest single FX-creation skip |
| `0x00252A8C` | `14400033` | `IkeEffectsMgr::DrawEffects+0x778` | 51 instructions, two `EffMgrPS2::Get()` calls |
| `0x0045E058` | `1440000B` | `EffMgrPS2::PreRender+0x24` | 11 instructions |
| `0x0045E1B8` | `14400003` | `EffMgrPS2::Render+0x54` | `CollectSortedObjectToHotAir` |
| **`0x0045E1D4`** | `14400035` | `EffMgrPS2::Render+0x70` | **the whole full-effect block: bullet holes, foliage, birds, LCD, indicators, water ripples, muzzle flashes, tracers, haloes, static light, billboards, sorted objects, blood pool** |
| `0x0045E3C4` | `14400025` | `EffMgrPS2::Render+0x260` | `HotAirPS2::Render` + 36 instructions |
| `0x0045F210` | `14400085` | `EffMgrPS2::RenderNightVision+0x1c` | 133 instructions |
| `0x004600B0` | `14400026` | `EffMgrPS2::RenderMask+0x1c` | 38 instructions |
| `0x004626DC` | `10400005` | `SnowEffectPS2::SnowEffectPS2+0x58` | **inverted** — `beqz`, taken when NOT split screen |
| `0x0045DF68` / `0x0045DFDC` | `1460002A` / `1060000D` | `EffMgrPS2::SetWeather+0x34` / `+0xa8` | weather selection differs per mode |

| # | VA | current | proposed | risk | effect |
|---|---|---|---|---|---|
| B1 | `0x0044EBB4` | `A0852880` | `A0802880` | **H** | `EnableSplitScreen(b)` always stores 0, so `IsEnableSplitScreen()` is permanently false and **every** gate above takes the single-screen path. One word, trivially reversible, and the fastest way to prove the mechanism. **But** `CGraphicSystem::MainFrame`, `PreMainFrame` and `GetCurrentCamera` read the same byte, so viewport setup will almost certainly be wrong — expect one full-screen view instead of two. Diagnostic patch, not a shippable one. |
| B2 | `0x0045E1D4` | `14400035` | `00000000` | **H** | forces `EffMgrPS2::Render` down the full-effect block in split screen. The full block ends with an unconditional `b 0x0045E3B8` at `0x0045E288`/`0x0045E2A4`, so the reduced block **and both `SetSplitScreenDrawArea` calls are skipped** — second viewport will not be set up. Restores the effects but likely at the cost of the second view. |
| B3 | `0x0024EF38` | `14E0006A` | `00000000` | M | stops `CreateGeneralEffect` skipping its 424-byte block in split screen. This one is creation-side, not viewport-side, so it is the *safest* of the three to try first. |
| B4 | `0x00252A8C` | `14400033` | `00000000` | M | same idea in `IkeEffectsMgr::DrawEffects`. |
| B5 | `0x0024C8B8` | `14400009` | `00000000` | L | same idea in `AddGeneralEffects`. |

The properly-correct fix for split-screen decals is not a word patch: it is to add
the three missing `jal`s (`BulletHoleManagerPS2::Render` `0x0046DC20`,
`FoliageManagerPS2::Render` `0x00469880`, `BirdManagerPS2::Render` `0x0046AA70`)
into the reduced block at `0x0045E2DC`–`0x0045E32C`, which has no spare slots and so
needs a code cave. That is a build step, not a pnach.

```
// B. split-screen effects - try these ONE AT A TIME, B3 first
patch=1,EE,0024EF38,word,00000000
patch=1,EE,00252A8C,word,00000000
patch=1,EE,0024C8B8,word,00000000
// diagnostic only, expect broken viewports:
// patch=1,EE,0044EBB4,word,A0802880
// patch=1,EE,0045E1D4,word,00000000
```

---

## C. Particles / weather density

These are real `RSArray` caps, not auto-extending pools. Lowering them is a safe
performance experiment; raising them costs heap and fill rate.

| # | VA | current | proposed | risk | effect |
|---|---|---|---|---|---|
| C1 | `0x00257C80` | `24050FA0` | `24051F40` | M | `IkeRainEffect` raindrops 4000 → 8000. `240503E8` gives 1000 instead. |
| C2 | `0x002584FC` | `240509C4` | `24051388` | M | `IkeSnowEffect` snowflakes 2500 → 5000. |
| C3 | `0x00460420` | `2405012C` | `24050258` | M | `RainEffectPS2` raindrops 300 → 600. |
| C4 | `0x004627D0` | `24050064` | `240500C8` | M | `SnowEffectPS2::CreateData` 100 → 200. |
| C5 | `0x0046375C` | `240501F4` | `240503E8` | M | `StaticLightPS2` segments 500 → 1000. |
| C6 | `0x0045D120` | `24070050` | `240700A0` | M | `BillboardEffectManagerPS2` first pool arg 80 → 160. Pair with C7. |
| C7 | `0x0045D128` | `24080040` | `24080080` | M | second pool arg 64 → 128. |
| C8 | `0x00471A58` | `240500C8` | `24050190` | M | `RSCamera` occluder array 200 → 400 (culling, not FX — included because it is in the same table). |

To switch a whole effect class **off**, NOP its `jal` in `EffMgrPS2::Render`. Note
every entry below that also appears in the reduced split-screen block needs **both**
words NOP-ed.

| effect | single-screen call | split-screen call |
|---|---|---|
| indicators | `0x0045E1DC` | `0x0045E2DC` |
| water ripples | `0x0045E1E4` | `0x0045E2E4` |
| **bullet holes** | `0x0045E1EC` | *(none — see section B)* |
| LCD | `0x0045E1F4` | `0x0045E2EC` |
| **foliage** | `0x0045E1FC` | *(none)* |
| **birds** | `0x0045E204` | *(none)* |
| muzzle flashes | `0x0045E20C` | `0x0045E2F4` |
| tracers | `0x0045E214` | `0x0045E2FC` |
| light haloes | `0x0045E21C` | `0x0045E304` |
| static light | `0x0045E224` | `0x0045E30C` |
| billboards | `0x0045E22C` | `0x0045E314` |
| sorted objects | `0x0045E234` | `0x0045E31C` |
| blood pools | `0x0045E23C` | `0x0045E324` |
| lens flare | `0x0045E25C` | `0x0045E344` |
| rain | `0x0045E280` | `0x0045E374` |
| snow | `0x0045E29C` | `0x0045E398` |
| hot air | `0x0045E3CC` | — |
| night vision | `0x0045E404` | `0x0045E494` |
| screen blur | `0x0045E414`, `0x0045E424` | `0x0045E4AC` |

Each of those is a `jal` word; NOP = `00000000`. The delay slot immediately after it
loads the argument and is harmless to leave running.

```
// C. example: turn tracers off entirely (both viewports)
patch=1,EE,0045E214,word,00000000
patch=1,EE,0045E2FC,word,00000000
// example: double the rain
patch=1,EE,00257C80,word,24051F40
patch=1,EE,00460420,word,24050258
```

---

## D. First-person camera

Background and the enum are in `features_gr.md` section (c). `SimCamera + 0x70` holds
the camera view; 0 = first person.

| # | VA | current | proposed | risk | effect |
|---|---|---|---|---|---|
| D1 | `0x003A8C0C` | `AC850070` | `AC800070` | **H** | `SetCurrentCameraView` stores 0 regardless of its argument — the camera is pinned to first person. Also hits the cinema/scripted camera path (`HandleChangeCameraScript`, `UpdateMovement`), so cutscenes will be affected. |
| D2 | `0x003A8B44` | `24420001` | `00001021` | M | `ToggleCameraView` computes `view = 0` instead of `view + 1`, so the camera-cycle input can never leave first person while scripted camera changes still work. Narrower than D1. |
| D3 | `0x003A80F4` | `10400010` | `10000010` | L | `CameraBeginScene` never takes the first-person branch, so `RSSimController::Hide()` is never called — **your own soldier stays visible in first person**. This is the direct test of "is there a view model?": with D1 or D2 plus D3 you see the third-person body drawn from the eye position, and nothing else. |
| D4 | `0x003A8B88` | `28420003` | `28420006` | L | raises `ToggleCameraView`'s normal wrap from 3 to 6, unlocking `chase camera` (3) and `ghost camera` (4) on the ordinary camera-cycle input without needing the `IkeConstants` flag. |

```
// D. first person
patch=1,EE,003A8B44,word,00001021
patch=1,EE,003A80F4,word,10000010
// unlock chase + ghost cameras on the normal cycle:
// patch=1,EE,003A8B88,word,28420006
```

---

## E. Spawning / respawn

| # | VA | current | proposed | risk | effect |
|---|---|---|---|---|---|
| E1 | `0x0017F310` | `27BDFF80` | `03E00008` | **H** | with E2, turns `IkeRulesMgr::CanRespawn` into `return true` — unlimited respawns regardless of respawn type or count. Safe on the stack because nothing has been pushed yet. |
| E2 | `0x0017F314` | `FFBF0050` | `24020001` | **H** | the delay slot for E1. **E1 and E2 must be applied together**; E1 alone leaves `sd $ra,80($sp)` executing below an un-adjusted `$sp`. |
| E3 | `0x0017F314` | `FFBF0050` | `24020000` | **H** | the inverse: `return false`, respawning disabled entirely. Also requires E1. |
| E4 | `0x0017F3CC` | `14600006` | `10000006` | M | in `CanRespawn`, always take the "respawnType != 0" branch, so a mission configured for no respawns is treated as if it had one. Much narrower than E1/E2 — it leaves the count check intact. |
| E5 | `0x0015B0C8` | `24030005` | `24030063` | L | `Company::Company` seeds field `+0x30` with 5; raising it to 99. GUESS: this is the default respawn allowance. Unverified — it is written at `0x0015B0EC` (`sw $v1,0x30($v0)`) and this agent did not find the reader. |

```
// E. unlimited respawns (apply E1+E2 as a pair)
patch=1,EE,0017F310,word,03E00008
patch=1,EE,0017F314,word,24020001
// narrower: treat "no respawn" missions as respawn-enabled
// patch=1,EE,0017F3CC,word,10000006
```

---

## What is deliberately NOT here

* **Weapon stats, ballistics, AI skill, difficulty, enemy counts, mission rosters.**
  All of these are read from data files: `IkeConstants::IkeConstants(const char*)`
  takes a filename, the `k*NodeName` globals at `0x0055C418`+ are XML node names, and
  `Company::AddPlatoon` / `Platoon::AddFireTeam` grow their arrays by one with no cap
  test anywhere. There is no word in this ELF to patch for any of them.
* **The cheat handlers** (`HandleToggleSuperman` `0x00178000`,
  `HandleSetNoHumanDamage` `0x001781B0`, `HandleToggleInfiniteAmmo` `0x00178200`,
  `HandleToggleShadow` `0x00177FC0`). They are `RSGameMessage` handlers — they only
  run when something posts the message. Reaching them needs code injection that
  posts the message, not a static word patch.
* **Anything in `offline.bin` / `online.bin`.** Those belong to Jungle Storm; see
  `patch_candidates_js.md` and `mwo3.py`.

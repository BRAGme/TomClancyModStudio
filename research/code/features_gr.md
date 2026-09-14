# Feature map — Ghost Recon (PS2, SLUS-20613), `SLUS_206.13`

Every address here is a **virtual address**, which for this ELF equals
`file_offset + 0x00100000 - 0x80`. Every fact below came from a tool result this
session (symbol table, disassembly, string scan, or `jal`-target scan). Guesses are
labelled GUESS.

## The thing that makes this whole binary easy

`SLUS_206.13` is an **unstripped debug build**. It carries 19,496 `STT_FUNC` symbols
with correct sizes and 17,386 `STT_OBJECT` symbols, all Metrowerks-mangled C++ with
class names, plus 26.8 MB of DWARF 1. You almost never have to guess what a function
is. Full dump: `symbols_gr.txt`. Source tree layout: `source_paths_gr.txt`.
Tooling used throughout: `rsetool.py` (`sym`, `dis`, `xref`, `callers`, `grepstr`).

Relevant `.cpp` translation units (recovered from the 644 `__sinit_*` symbols):

| feature | source files |
|---|---|
| decals | `decaleffect.cpp` `ikedecaleffect.cpp` `bullethole_ps2.cpp` `bloodpool_ps2.cpp` `tracer_ps2.cpp` `brassprojectile.cpp` `breakingglass.cpp` `debrisprojectile.cpp` |
| particles / FX | `particleeffect.cpp` `ikeparticleeffect.cpp` `triparticleeffect.cpp` `iketriparticleeffect.cpp` `effectmanager.cpp` `effmgr.cpp` `effmgr_render.cpp` `effmgr_scissor.cpp` `rsparticlesystem.cpp` `shockwaveeffect.cpp` `beameffect.cpp` `billboardeffect.cpp` `lighthaloeffect.cpp` `ikeraineffect.cpp` `ikesnoweffect.cpp` `ikeweathereffect.cpp` `raineffect_ps2.cpp` `snow_ps2.cpp` `rainemitter.cpp` `windemitter.cpp` `projectileeffect.cpp` `effectprojection.cpp` |
| camera / view | `simcamera.cpp` `scenecamera.cpp` `dialogscenecamera.cpp` `reticule.cpp` `reticuledisplay.cpp` |
| AI / spawning | `company.cpp` `companyai.cpp` `platoon.cpp` `platoonai.cpp` `fireteam.cpp` `fireteamai.cpp` `actor.cpp` `actorfile.cpp` `ai.cpp` `humanai.cpp` `awarenessmgr.cpp` `teamrestartplan.cpp` `vehiclerestartplan.cpp` `teampatrolzonebehavior.cpp` `ikerulesmgr.cpp` `ikescriptmgr.cpp` + 25 `*behavior.cpp` files |

---

## (a) DECALS / bullet impact marks

### Two separate systems, and only one of them is live on PS2

1. **`DecalEffect1` … `DecalEffect10`** — the PC-heritage decal-effect classes.
   Ten near-identical classes at `0x002912f0`–`0x002945a0`, each with
   `ReadDecalEffectN`, `AllocDecalEffectN`, `RegisterResources`, `Initialize`.
   `RegisterResources__12DecalEffect1FUiUi+0x40` at **`0x002943b4`** loads
   `"decal_effect1.rsb"` (string at `0x0057b9a0`); `decal_effect2..10.rsb` sit at
   `0x0057b980 … 0x0057b8b0`. Allocation goes through
   `RSMemoryPool<DecalEffect>` (`InitStatic__Fv` site `0x003f9254`, initial
   count 1, auto-extending).

2. **`BulletHolePS2` / `BulletHoleManagerPS2`** (`bullethole_ps2.cpp`) — the
   **actual PS2 bullet-hole renderer**, and the one to patch.

### The live bullet-hole call chain (verified by `callers`)

```
kMsgID_DisplayBullethole  (u16 global at 0x00579c10)
  -> IkeEffectsMgr::HandleDisplayBullethole   0x00249d50  (1460 B)
       calls at 0x00249ed4 and 0x00249f10
  -> IkeEffectsMgr::DisplayBullethole         0x00249610  (480 B)
       call at 0x002497c4
  -> BulletHoleManagerPS2::AddOneBulletHole   0x0046dac0  (348 B)
  -> BulletHolePS2::Generate                  0x0046dce0
render:
  EffMgrPS2::Render+0x8c 0x0045e1ec -> BulletHoleManagerPS2::Render 0x0046dc20
       -> BulletHolePS2::TestVisible 0x0046dd70 -> Render 0x0046dd80 -> Update 0x0046dd40
```

### `BulletHolePS2` struct (recovered from `Generate` / `Update` / the `__vc__` stride)

Stride is 48 bytes (`__vc__24RSArray<13BulletHolePS2>Fi` at `0x0046dfe0` computes
`((i*2)+i)<<4`).

| offset | type | meaning |
|---|---|---|
| `+0x00` | u8 | active flag (`Generate` writes 1, `Update` writes 0 on expiry) |
| `+0x04` | float | scale / size (arg `$f13`) |
| `+0x08..0x10` | vec3 | world position |
| `+0x14..0x1c` | vec3 | surface normal |
| `+0x20` | int | decal texture index 0..3 |
| `+0x24` | float | lifetime in seconds (arg `$f12`) |
| `+0x28` | float | spawn time |
| `+0x2c` | float | last-update time |

`Update` at `0x0046dd40` is literally
`if (curTime <= spawnTime + lifetime) lastUpdate = curTime; else active = 0;`

### The hardcoded numbers

**Pool size = 20 holes**, set twice in `BulletHoleManagerPS2::BulletHoleManagerPS2`
(`0x0046d9b0`):

```
0046d9cc  jal  IncreaseToSize_Array<BulletHolePS2>   (0x0046e000)
0046d9d0  addiu $a1, $zero, 0x14      <-- array size = 20
...
0046d9ec  addiu $v0, $zero, 0x14      <-- clear-loop bound = 20
```

`AddOneBulletHole` reads the live count from the RSArray header (`lw $v0,4($s4)`),
so it follows whatever the array was sized to — both immediates must be changed
together and nothing else needs touching.

**Lifetime and size, and the surface-type switch**, all inside
`IkeEffectsMgr::DisplayBullethole` (`0x00249610`), signature
`(const RSVector3& pos, const RSVector3& normal, unsigned surfaceType, RSNode*)`:

| site | word | constant | meaning |
|---|---|---|---|
| `0x00249638` | `3c0341f0` | `lui $v1,0x41f0` = **30.0f** | default decal lifetime (seconds) |
| `0x00249648/4c` | `3c033ecc` / `3463cccd` | **0.4f** | default decal size |
| `0x00249704/08` | `3d8f5c29` | **0.07f** | size for surface type 3 |
| `0x00249724/28` | `3da3d70a` | **0.08f** | size for surface types 4, 0xC, 0xD |
| `0x00249740` | `3c024000` | **2.0f** | lifetime for surface types 0x12, 0x13, 0x16 |

Surface-type dispatch (`$a3`, spilled to `sp+0xc0`) — the texture index passed on as
`$a1`:

| surfaceType | decal texture idx | notes |
|---|---|---|
| 0, 1, 2, 5, 0x0B | 0 | default size 0.4, lifetime 30 s |
| 3 | 1 | size 0.07 |
| 4, 0x0C, 0x0D | 2 | size 0.08 |
| 0x12, 0x13, 0x16 | 3 | lifetime cut to 2.0 s |
| **anything else** | — | **`0x002496ec  b 0x0024975c` → function returns, NO decal at all** |

That default branch at `0x002496ec` is the single biggest "why is there no bullet
hole here" gate in the game.

### Other impact effects found

| symbol | VA | note |
|---|---|---|
| `BloodPoolPS2::AddNewBloodPool` | `0x004621d0` | blood decals, separate pool |
| `BloodPoolPS2::DeleteAllBloodPool` | `0x004622d0` | |
| `IkeEffectsMgr::HandleBloodPoolEffect` | `0x00247ad0` | |
| `IkeEffectsMgr::AttachExplosionDecal` | `0x00247e60` | 16-byte thunk |
| `IkeEffectsMgr::HandleSpawnBrass` | `0x0024a3b0` | shell casings |
| `IkeEffectsMgr::HandleSpawnDebrisProjectile` | `0x0024a7c0` | |
| `TracerManagerPS2` ctor | `0x0046be80` | tracers |
| `IkeSimulationMgr::DisplayTracer` | `0x00399530` | |
| `SimHuman::ShouldDisplayTracer` | `0x003d3940` | per-shot tracer gate |
| `GunFile::GetTracerFrequency` | `0x003d3a40` | data-driven, from the gun file |
| `IkeEffectsMgr::StartMuzzleFlash` / `StopMuzzleFlash` | `0x00246080` / `0x00245dc0` | |
| `EffMgrPS2::AddNewMuzzleFlash` / `RenderAllMuzzleFlashes` | `0x0045fd20` / `0x0045fdb0` | |

**Negative result:** the strings `decal_type1` / `decal_type2` / `decal_type3`
(`0x00579880`, `0x00579890`, `0x005798a0`) have **zero code cross-references**.
`rsetool.py xref gr 579880` returns nothing for all three. They are XML/script tag
names compared by string at load time against data files, not constants the code
reaches for. Same for `host0:P:\Ike\release\new_data\new\bulletholes_sfx.bmz`
(`0x00589f10`) — a build-time asset path left in the pool.

---

## (b) PARTICLE / EFFECT SYSTEMS

### Careful: `Emitter` is the SOUND class

`emitter.cpp` / class `Emitter` (`0x002220c0`–`0x002367b0`, ~50 methods:
`SetEmitterVolume`, `CalculateEffectiveVolume`, `LoadSound`, `Propagate`,
`SetObstruction`) is the **3D audio** emitter. It is not a particle emitter. Anyone
grepping "emitter" for FX work will waste hours here.

### Effect object pools (`RSMemoryPool<T>`, initial count 1, auto-extending)

All created by `InitStatic__Fv` around `0x003f8f70`–`0x003f9408`:
`TriParticleEffect`, `AnimatedMultiTextureEffect`, `AnimatedTextureEffect`,
`AnimatedVertexColorEffect`, `BeamEffect`, `ColorEffect`, `DecalEffect`,
`ProjectileEffect`, `ProjectileLightEffect`, `ShockWaveEffect`. Plus:

| pool | init site | initial / grow |
|---|---|---|
| `RSMemoryPool<ParticleEffect>` | `InitPool__14ParticleEffectFv` @ `0x004afb70` | 16 |
| `RSMemoryPool<BillboardEffect>` | `InitPool__15BillboardEffectFv` @ `0x004a57ec` | (a1 not literal) |
| `RSMemoryPool<LightHaloEffect>` | `InitPool__15LightHaloEffectFv` @ `0x004ac5c0` | 16 / 8 |
| `RSMemoryPool<EffectProjection>` | `InitializePool__16EffectProjectionFv` @ `0x004a9de0` | 16 / 8 |
| `RSMemoryPool<RSMuzzleFlash>` | `InitializeSpecialEffects__13IkeEffectsMgrFv` @ `0x0024ad70` | 16 / 16 / 4 |
| `RSMemoryPool<LimbAnchor>` | `InitPool__14LimbAnchorListFv` @ `0x00431a7c` | 16 / 8 |

Because `ExtendPool__*` exists for every one of these, **none of them is a hard cap**
— they grow on demand. Patching these changes allocation granularity, not the
maximum effect count. That is the useful negative here.

### The real hardcoded particle counts (fixed `RSArray`, *are* hard caps)

Found by scanning every `jal` to `IncreaseToSize_Array`/`SetSize_Array` and reading
back the literal in `$a1`:

| count | site VA | word | array |
|---|---|---|---|
| **4000** | `0x00257c80` | `24050fa0` | `IkeRainEffect::IkeRainEffect` → `RSArray<IkeRainDrop>` |
| **2500** | `0x002584fc` | `240509c4` | `IkeSnowEffect::IkeSnowEffect` → `RSArray<IkeSnowFlake>` |
| **500** | `0x0046375c` | `240501f4` | `StaticLightPS2` → `RSArray<StaticLightPS2::Segment>` |
| **300** | `0x00460420` | `2405012c` | `RainEffectPS2::RainEffectPS2` → `RSArray<RainDrop>` |
| **200** | `0x00471a58` | `240500c8` | `RSCamera` → `RSArray<RSOccluder*>` |
| **200** | `0x004b6590` | `240500c8` | `BucketSortObjectAccumulator` → `RSArray<RSAccumulatedObject*>` |
| **100** | `0x004627d0` | `24050064` | `SnowEffectPS2::CreateData` → `RSArray<RSVector3>` |
| **100** | `0x0024d460`, `0x0024da14` | `24050064` | `IkeEffectsMgr::AddGeneralEffects` → `RSArray<RSHelperPoint*>` |
| **100** | `0x00489c40` | `24050064` | `Scene` → `RSArray<SceneImageEntry*>` |
| **32** | `0x004b6558` | `24050020` | `BucketSortObjectAccumulator` → `RSArray<Bucket>` |
| **20** | `0x0046d9d0` | `24050014` | `BulletHoleManagerPS2` (see above) |
| **80 / 64** | `0x0045d120` / `0x0045d128` | `24070050` / `24080040` | `BillboardEffectManagerPS2` ctor, args `$a3`/`$t0` |

(The scan also produced fifteen `65535` rows; those are `addiu $a1,$zero,-1` picked
up by the 6-instruction lookback window and are **false positives** — the R6 3
warning about bare-immediate searches, reproduced exactly.)

### PS2 effect renderers and their master switch

`EffMgrPS2` (singleton, `_instance__9EffMgrPS2` at `0x00630d68`, `Get()` at
`0x0045d400`) owns every PS2 effect renderer. Its constructor `0x0045d480` news and
constructs, in order:

| sub-manager | ctor VA |
|---|---|
| `BillboardEffectManagerPS2` | `0x0045d0f0` |
| `LensflareManagerPS2` | `0x004618c0` |
| `BloodPoolPS2` | `0x00462120` |
| `StaticLightManagerPS2` | `0x00464660` |
| `HotAirPS2` | `0x00467640` |
| `SkyPS2` | `0x004688b0` |
| `FoliageManagerPS2` | `0x00469560` |
| `BirdManagerPS2` | `0x0046a800` |
| `WaterRippleManagerPS2` | `0x0046b320` |
| `IndicatorManagerPS2` | `0x0046e130` |
| **`BulletHoleManagerPS2`** | `0x0046d9b0` |
| `TracerManagerPS2` | `0x0046be80` |
| `ScreenBlurPS2` ×3 | `0x0046c6e0` |

`EffMgrPS2::Render` at `0x0045e160` (952 B) is the single dispatch point — each
sub-system's `Render` is one `jal` in there, so an individual effect class can be
switched off by NOP-ing one call (see `patch_candidates_gr.md`).

Other useful entry points: `EffMgrPS2::SetWeather` `0x0045df30`,
`RenderNightVision` `0x0045f1f0`, `RenderSortedObject` `0x0045e7c0`,
`SetScreenMotionBlur` `0x00460010`, `RenderAllHaloes` `0x0045fc60`.

---

## (c) FIRST PERSON / VIEW MODEL — the user's question, answered

**Ghost Recon PS2 does have a first-person camera. It does not have a first-person
view model, and in first person it hides the player's entire avatar.** Evidence:

### The camera-view enum is in the binary as literal strings

`SimCamera::SetCurrentCameraView(CameraViewType)` at `0x003a8c00` logs the name of
the view it switches to. The dispatch at `0x003a8c94`–`0x003a8d30` gives the enum
exactly:

| value | string VA | string |
|---|---|---|
| **0** | `0x00584320` | **`first person camera`** |
| 1 | `0x00584340` | `third person camera` |
| 2 | `0x00584358` | `cinema camera` |
| 3 | `0x00584368` | `chase camera` |
| 4 | `0x00584378` | `ghost camera` |

These five are the only camera-view strings in the pool.

### Where the value lives and how it is tested

`SimCamera::IsFirstPersonCamera() const` at `0x0039ba00` is four instructions:

```
0039ba00  lw    $v0, 0x70($a0)
0039ba04  xor   $v0, $v0, $zero
0039ba08  jr    $ra
0039ba0c  sltiu $v0, $v0, 1        ; return (this->m_cameraView == 0)
```

So **`SimCamera + 0x70` is the current camera view**, and 0 means first person.
`IkeSimulationMgr::IsFirstPersonView()` at `0x0039fa80` is a thin wrapper that calls
a virtual to fetch the SimCamera and forwards to it.

### First person is reachable in normal play

`SimCamera::ToggleCameraView()` at `0x003a8b30` is called from
`SimCamera::ProcessMessage+0x6b8` (`0x003a8968`) — i.e. it is driven by a game
message, so it is on the player's camera-cycle input. It does
`m_cameraView++`, then:

* if a config flag matches (`this+0x38` compared against an `IkeConstants` byte at
  `0x003a8b50`–`0x003a8b64`), it wraps only at 6 — all five views cyclable;
* otherwise `0x003a8b88  slti $v0, $v0, 3` → **wrap at 3**, so the normal cycle is
  first person → third person → cinema → first person.

`SetCurrentCameraView` also publishes a global: `0x003a8c30` stores
`(m_cameraView >= 3)` to the byte at **`0x005eb0b8`**. That byte is read fifteen
times in `SimHuman::ProcessMessage` and `SimHuman::HandleAnalogZoom` /
`DoAStepOfCircleZooming` / `AttachToVehicle` (full list from
`rsetool.py xref gr 5eb0b8`) — it is the "camera is detached from the soldier" flag
that suppresses player input routing.

### What first person actually does to the rendering

`SimCamera::CameraBeginScene()` at `0x003a80e0`:

```
003a80ec  jal IsFirstPersonCamera
003a80f4  beqz $v0, 0x3a8138          ; not first person -> skip the whole block
          ... GetLeader() ...
003a8124  sb   $v0, 0xc($s0)          ; remember prior hidden state
003a8130  jal  0x003a8170             ; RSSimController::Hide()
```

`0x003a8170` is `Hide__15RSSimControllerCFv` — it fetches `this->m_drawObject`
(`+0x34`) and calls vtable slot `+0x0c` with argument 1. `CameraEndScene()` at
`0x003a81e0` has the mirrored `IsFirstPersonCamera` guard.

So entering first person **hides the player's whole `RSSimController` draw object**
— body, kit and the weapon that is attached to it — and nothing is drawn in its
place.

**Negative results, stated precisely.** Searching all 38,722 symbols for
`viewmodel|ViewModel|firstperson|FirstPerson|1stPerson|WeaponView|hands|arms|fpp`
returns exactly two hits, both listed above (`IsFirstPersonCamera`,
`IsFirstPersonView`). There is no `m_bUseFirstPersonWeapon` analogue (the Rainbow
Six 3 property), no view-model class, no view-model draw call, and no separate
weapon-model node in the camera path. The only first-person-specific rendering code
in the binary is the *hide* above and a first-person special case in
`IkeSimulationMgr::LightHaloBlocked+0xe8` (`0x0039b918`).

The user's belief is therefore **confirmed, with the refinement that the first-person
*camera* is fully implemented and reachable — it is only the weapon/hands model that
does not exist.** GUESS (not verified by running anything): the on-screen weapon in
first person is the `ReticuleDisplay` HUD (`0x0027d190` `Draw`, with
`SetupSniperFrame` / `SetupBinocularFrame` / `SetupAT4Frame`) plus the muzzle flash
sprite, and nothing else.

---

## (d) ENEMY SPAWNING / REINFORCEMENT

### The unit hierarchy is Company → Platoon → FireTeam → HumanAI

Data side (`company.cpp`, `platoon.cpp`, `fireteam.cpp`):

| function | VA |
|---|---|
| `Company::Company` | `0x0015b070` |
| `Company::AddPlatoon(unsigned, const RSString&)` | `0x0015b1e0` |
| `Company::AddHuman(const HumanCompanyMember&, bool)` | `0x0015b260` |
| `Company::AddVehicle` | `0x0015b410` |
| `Company::SetHumanActiveState(u,u,u,i,b)` | `0x0015b360` |
| `Company::ReadBin` | `0x0015b550` |
| `Platoon::AddFireTeam` | `0x001875b0` |
| `FireTeam::AddHuman(unsigned, int)` | `0x0015bef0` |
| `FireTeam::ReplaceHuman` | `0x0015bf70` |
| `FireTeam::SetHumanActiveState` | `0x0015bfe0` |

AI side (`companyai.cpp`, `fireteamai.cpp`):

| function | VA |
|---|---|
| `CompanyAI::CreatePlatoonAI` | `0x00188940` |
| `CompanyAI::CreateFireTeamAI` | `0x001889e0` |
| `CompanyAI::CreateHumanAI` | `0x00188a50` |
| `CompanyAI::CreateGroundVehicleAI` | `0x00188ad0` |
| `CompanyAI::CreateAirVehicleAI` | `0x00188b80` |
| `FireTeamAI::CreateHumanAI` | `0x0018eb10` |
| `FireTeamAI::Update` | `0x0018d930` (4468 B — the AI main loop) |
| `FireTeamAI::AddEnemy` / `UpdateEnemyList` | `0x0018b5b0` / `0x0018b840` |

**Important negative: there is no hardcoded unit cap in the executable.**
`Company::AddPlatoon` (`0x0015b1e0`) and `Platoon::AddFireTeam` (`0x001875b0`) both
`operator new` a fixed-size object (0x58 and 0x14 bytes) and then grow an `RSArray`
by exactly one (`addiu $a1, $s1, 1`). There is no comparison against a maximum
anywhere in either function. Roster size is entirely data-driven — it comes from the
mission/company files in the archives, which this agent does not own.
`Company::Company` does seed one constant: `sw $v1, 0x30($v0)` with `$v1 = 5` at
`0x0015b0c8`/`0x0015b0ec`. GUESS: default respawn allowance.

### Respawn / reinforcement is in `IkeRulesMgr`

| function | VA | size |
|---|---|---|
| `IkeRulesMgr::CanRespawn(ISimHuman*)` | `0x0017f310` | 640 |
| `IkeRulesMgr::HandleRespawnTypeRequest` | `0x0017a190` | 668 |
| `IkeRulesMgr::HandleRespawnCountRequest` | `0x0017a960` | 912 |
| `IkeRulesMgr::HandleIncCompanyRespawns` | `0x0017f070` | **8 — an empty stub** |
| `IkeStateMgr::HandleRespawnTypeAssign` | `0x001852e0` | 140 |
| `IkeStateMgr::HandleRespawnCountAssign` | `0x00185640` | 140 |
| `IkeRulesMgr::HandleAIBackupRequest` | `0x0017b0d0` | 1172 |
| `IkeRulesMgr::HandleRandomZonesRequest` | `0x0017acf0` | 764 |
| `IkeRulesMgr::HandleDifficultyRequest` | `0x0017a5e0` | 884 |
| `IkeRulesMgr::HandleAddCompany / AddPlatoon / AddFireTeam / AddHumanToFireTeam` | `0x00178bc0` / `0x00178cc0` / `0x00178db0` / `0x00178ef0` | |
| `IkeRulesMgr::HandleAddVehicleToCompany` | `0x001790f0` | |

`CanRespawn` decompiles (from `0x0017f310`) to roughly:

```
if (!g_something->vfn_A0())           // 0x005e4ff8 singleton, vtable +0xa0
    return g_something->vfn_90() ? false : <fallthrough>;
respawnType = <objptr>->[0x2b8]                 // read at 0x0017f3c8
if (respawnType == 0)  return false;            // 0x0017f3cc branch
if (respawnType == 1) {                         // 0x0017f3e8 branch
    limit = (*(void**)0x005eace8)->[0xa6c];     // 0x0017f44c / 0x0017f490
    if (teamKills(side0) >= limit) return false;
    if (teamKills(side1) >= limit) return false;
}
... further per-human checks (vtable +0x120, +0x6c, +0xa8) ...
return true;
```

So `respawnType` lives at offset `0x2b8` of the rules object, the **respawn count
limit is at `[0x005eace8] + 0xa6c`**, and `0x005eace8` is the game-manager singleton
pointer (also read by `HumanAIAwareness`, `FireTeamAI::ReportEnemyContact`,
`GroundVehicleAI::CalcCoverPoints`, and cleared by `IkeGameMgr::ReleaseOther` at
`0x001445fc`).

`IkeStateMgr::HandleRespawnCountAssign` (`0x00185640`) stores the network-assigned
value with `sw $v0, 0x3b8($a0)` at `0x001856ac`, where `$a0 = this->[0x1110]`.

### Plans, restarts and patrols

| symbol | VA |
|---|---|
| `TeamRestartPlan::Process(FireTeamAI*, bool&, Behavior*&)` | `0x001c3480` (16 B — a thunk) |
| `TeamRestartPlan::ReadBin` / `WriteBin` | `0x001c3440` / `0x001c3400` |
| `VehicleRestartPlan::Process` | `0x001c7c90` |
| `SetupFilePlanEntry::RestartStep` dtor / `GetType` / `MakeCopy` | `0x001ea820` / `0x001ea880` / `0x001ea890` |
| `IkeRootContainer::BeginRestart` / `EndRestart` / `RestartThread` | `0x0020b4c0` / `0x0020b3d0` / `0x0020b780` |
| `RSGameStateMgr::GetRestartTime` / `IkeStateMgr::GetRestartTime` | `0x00130930` / `0x001865f0` |

`SetupFilePlanEntry` has a `RestartStep` step type — mission plans are step lists
read from the setup file, and "restart" (i.e. respawn a team at its insertion point)
is one of the step kinds. The *content* of those plans is in the data archives.

### Cheat / rules toggles found along the way (bonus, all message handlers)

`HandleToggleSuperman` `0x00178000`, `HandleToggleTeamSuperman` `0x00178070`,
`HandleSetNoHumanDamage` `0x001781b0`, `HandleToggleInfiniteAmmo` `0x00178200`,
`HandleToggleShadow` `0x00177fc0`, `HandleToggleTeamShadow` `0x00177fe0`,
`HandleArcadeModeRequest` `0x0017b000`, `HandleKitRestrictRequest` `0x0017b580`.
These are reachable only by posting the matching `RSGameMessage`, so they are levers
for a trainer/ASI, not for a static word patch.

---

## Where the tuning data actually lives (important scoping result)

`IkeConstants::IkeConstants(const char*)` at `0x0015c8c0` takes a **filename**, and
every tuning value the AI uses is a getter on that object — e.g.
`IkeConstants::GetMaxInaccuracy` `0x003a3690`, `GetIFFLookRange` `0x0039d5e0`,
`DefaultFieldOfView` `0x0039d5c0`, `WussGrenadeVelocity`/`ManlyGrenadeVelocity`
`0x0035dbf0`/`0x0035dc00`, `MinHearingIntensity` `0x00382ba0`,
`HeadDmgStabilizationModifier` `0x003a42d0`. Likewise the `k*NodeName` string
globals (`0x0055c418` onward: `kBallisticHeadFactorNodeName`, `kTopSpeedNodeName`,
`kShowRadar`, `kThreatIndicatorEnabled`, `kIFFEnabled`, …) are **XML node names**
used to parse config files.

**Consequence for the mod tool:** ballistics, AI skill, weapon stats and
difficulty are *not* patchable in the ELF — they are read from the archives. What
*is* patchable in the ELF is exactly what this document lists: pool sizes, hardcoded
lifetimes/scales, the surface-type dispatch, render-call dispatch, and hard-coded
branches.

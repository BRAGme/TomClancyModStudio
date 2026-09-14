# Ghost Recon: Jungle Storm (PS2, SLUS-20820) — feature/string map of the three images

Static analysis only, via `rsetool.py` (address models `js` / `offline` / `online`).
Every address below is an in-game **VA**. Nothing under `E:\PS2 Games\` was modified.
Anything not backed by a tool result in this session is labelled GUESS.

---

## 0. Image summary

| image | file | size | VA range | printable strings (>=4) | real (non-noise) strings |
|---|---|---|---|---|---|
| `js` boot ELF | `SLUS_208.20` | 5,319,720 | `0x00100000`–`0x00612900` | 9772 | ~4474 (pool) + 40 (`>=0x005c0000`) |
| `offline.bin` | overlay id 2 | 313,216 | `0x00692700`–`0x006dee80` | 160 | **10** |
| `online.bin` | overlay id 3 | 707,840 | `0x00692700`–`0x0073f400` | 998 | **613** |

### MWo3 overlay header (verified by reading the first 32 bytes of each .bin)

```
off  0   4   'MWo3'
off  4   4   overlay id        offline=0x00000002   online=0x00000003
off  8   4   load VA           both = 0x00692700
off  C   4   text size         offline=0x000484c0   online=0x0009d6c0
off 10   4   data size         offline=0x00004280   online=0x0000f600
off 14   4   bss size          offline=0x0007ac00   online=0x00025300
off 18   4   static-ctor list start   offline=0x006dee70   online=0x0073f400
off 1C   4   static-ctor list end     offline=0x006dee74   online=0x0073f400
```
text+data ≈ file size in both cases (`0x484c0+0x4280 = 0x4c740` vs file `0x4c780`;
`0x9d6c0+0xf600 = 0xaccc0` vs file `0xacd00`). Offline has exactly one static ctor
(`0x006dee70` → `0x006dee00`, whose first word is a `addiu $sp,$sp,-0x10` prologue);
online's ctor list is empty.

Both overlays load at the same VA and are therefore **mutually exclusive**. The loader is
`0x00118d60(char* path)`, called from eight sites; the two that name the overlays are

| site | string | VA |
|---|---|---|
| `0x00307b38` | `host:offline.bin` | `0x00592a30` |
| `0x00307c24` | `host:online.bin`  | `0x00592a90` |

`cdrom0:\OFFLINE.BIN;1` (`0x00592a50`) and `cdrom0:\ONLINE.BIN;1` (`0x00592aa0`) exist in
the pool with **zero** code xrefs — the retail path is presumably reached through a
prefix-substituting file layer (GUESS; not traced).

---

## 1. String inventories

### 1a. `js` (boot ELF)

The real string pool is **`0x0055c000`–`0x005c0000`** (4474 strings ≥4 chars).
The 9772 raw hits include ~5250 false positives: printable byte runs inside MIPS code
below `0x0055c000` (e.g. `0x00115b9b "' 7c$07B$"`). Filtering to minlen 6 leaves only 81
hits below `0x0055c000`, all noise. A small genuine tail lives in the data segment at
`0x006125b8`–`0x006127f8` (40 strings, all Ubi.com/GameService tokens that also appear in
`online.bin`: `clData`, `GSFAIL`, `CHATALL`, `JOINNEW`, `SQLSET`, `PEERMSG`, `IRCIP%d`,
`Servers`).

Composition of the 4474 pool strings:

| kind | count | example |
|---|---|---|
| UPPER_ID (menu widget / localisation key) | 1273 | `0x0058df00 CAMPAIGN_MISSION`, `0x00592148 RESPAWN_CTRL` |
| identifier / script keyword | 1248 | `0x005855c8 Platoon`, `0x00585810 Patrol` |
| other / prose / short noise | 919 | `0x0059ae77 [unnamed mission]` |
| asset filename | 771 | `0x0058b490 particle_effect01.pob` |
| printf format | 171 | `0x00594f00 opposing_force_jungle_%i.atr` |
| absolute path | 92 | `0x005993e8 host0:P:\Ike\release\new_data\new\billboard_effect_blood_balpha.bmz` |

Notable sub-pools:

* **Build paths** `0x0057ac6f`–`0x0057ace0`: `host0:p:/Ike/release/new_data/` — the engine
  is still "Ike" internally, matching the Ghost Recon PS2 symbol names.
* **Mission table** `0x0057c630`–`0x0057d200+`, record stride **0x54 bytes**, each record
  = `<file>.mis` then `<display name>`:
  `c01_plantation.mis / C01 Watchful Yeoman` … `c08_mountain_stronghold.mis / C08 Righteous Archer`,
  then `mp01..mp05`, `dp01..dp05`, `cp01..cp05`, then the Jungle-Storm-specific
  `g03_the_rock.mis / J01 Totem Ground`, `g04_train.mis / J02 Vapor Knife`,
  `u05_rail.mis / J03 Ocelot Desert`, … `u03_rescue.mis / J07 Whisper Shadow`.
  Note the J-missions reuse **g\*/u\*** file names from the original Ghost Recon PS2 data set.
* **Interned-keyword ("atom") table** `0x00576880`–`0x0057be78`, **606 entries of 8 bytes**
  (`char* name`, then a zeroed 4-byte slot that is filled with the hash/id at runtime).
  This is the parser vocabulary for `.mis` / `.atr` / `.kit` / `.toe` files — see §2d.
* **Effect-type name table** `0x00578190`–`0x00578328`, 103 `char*` slots — see §2b.
* IJG libjpeg error strings (`0x0059cd73 Sampling factors too large…`) and Fonix ASR
  language-model names (`0x0059fdf0 asr16v220_enu200_float_4b.lng`) are present, i.e. the
  ELF also contains a JPEG decoder and the speech-recognition *wrapper*.

### 1b. `offline.bin`

150 of the 160 raw hits are code noise. The complete real inventory is **10 strings**:

```
0x00692720  offline.bin
0x006dad80  Game Speech API V2.02.01 for Sony PlayStation2
0x006dae18    [ASRSPI %d.%02d.%04d]
0x006dae50  <VOID>
0x006dae58  <NULL>
0x006dcc30  Version : ASRSPI16 Version RLS_ASRSPI16_2.03.00
0x006de4ba  EBefZB23oB
0x006deb28  Version : CTXDATA Version RLS_CTXDATA_2.00.04
0x006debc0  Version : LANGDATA.FLOAT Version RLS_LANGDATA.FLOAT_2.00.05
0x006ded50  Version : TOS Version RLS_TOS_2.00.06
```

`offline.bin` is the **Fonix/ASRSPI speech-recognition engine** (ASR = automatic speech
recognition; CTXDATA = grammar contexts; LANGDATA.FLOAT = acoustic model; TOS = text-to-
orthography). It contains **no** game logic, no filenames, no class names.

### 1c. `online.bin`

613 strings ≥6 chars containing a word. Composition:

| kind | count | example |
|---|---|---|
| C++ RTTI / template constructor names | 205 | `0x0072fe50 std::list<clData *, ExtAlloc::Allocator<clData *>>` |
| protocol opcode (UPPER) | 138 | `0x00732ef8 PLAYERINFO` |
| other (std exception text, config keys, ethernet) | 270 | `0x00736620 RouterIP%d` |

`online.bin` is the **Ubi.com "GameService" (GS) lobby/matchmaking client**:

* Message vocabulary `0x00732e30`–`0x007337a0`: `STILLALIVE`, `NEWUSERREQUEST`,
  `CONNECTIONREQUEST`, `CREATESESSION`, `JOINSESSION`, `LOGINARENA`, `BEGINCLIENTHOSTGAME`,
  `SQLQUERY`, `PLAYERKICK`, `PLAYERMUTE`, `ADDFRIEND`, `LOGINCLANMANAGER`,
  `EVENT_NEWMASTER`, `SENDTOALLPLAYERS`, … (~120 opcodes).
* Crypto stack `0x00734218`–`0x00734830`: `PKCModule_RSA`, `CipherModule_Blowfish`,
  `CipherModule_GSXor`, `HashModule_MD5`, `HashModule_SHA1`, `PRNGModule_MGF1`,
  `SecureHashAlgorithm1`, `GenerateSessionKey() -> `, `GenerateGlobalKeyPair() -> `.
* Config keys `0x00736620`–`0x007366b0`: `RouterIP%d`, `RouterPort%d`, `CDKeyServerIP%d`,
  `ProxyIP%d`, `NATServerIP%d`, `IRCPort%d`.
* Ladder/stats `0x00736770`–`0x007374b0`: `CLadderRequest`, `CLadderResults::CLadderEntry`,
  `CLadderResults::VersionMismatch`, `clPersistentCallbacks`, `persistantdata`.
* PS2 network IOP modules `0x00732330 PsIIlibeenet2800`, `0x00732740 PsIIeenetctl2800`;
  PHY strings `100baseTX-FDX/Flow`, `10baseT` at `0x00737690`.

**The RTTI-looking block the task asked about, `0x0072fe00`**, is exactly this and nothing
more:

```
0x0072fe00  clPointerList<clData *>
0x0072fe20  ExtAlloc::OverrideAllocOperators
0x0072fe50  std::list<clData *, ExtAlloc::Allocator<clData *>>
0x0072fe90  ExtAlloc::list<clData *>
0x0072feb0  clPlayerResults
0x0072fec0  string constructor: n > max_size
0x0072ff30  std::length_error  /  0x0072ff48 std::exception  /  0x0072ff60 std::logic_error
0x007300b8  clMatchResults
```

`clPlayerResults` / `clMatchResults` are the **end-of-match score upload** containers for
the Ubi.com ladder — they are serialisation DTOs, not gameplay. No spawn, decal, particle
or camera vocabulary appears anywhere in either overlay (see §2 for the measured zero).

---

## 2. Feature string map

Measured match counts (regex over the real string pools only):

| family | js | offline | online |
|---|---|---|---|
| decals / impacts | 75 | **0** | **0** |
| particles / effects | 130 | **0** | **0** |
| first-person / view / camera | 8 | **0** | **0** |
| spawning / reinforcement | 160 | **0** | **0** |

### 2a. DECALS / bullet impact marks — all in `js`

| VA | string | xref |
|---|---|---|
| `0x00589180` | `decal_type1` | data ptr `0x00578308` (effect-name table idx 98) |
| `0x00589190` | `decal_type2` | data ptr `0x0057830c` |
| `0x005891a0` | `decal_type3` | data ptr `0x00578310` |
| `0x0058b370` | `decal_effect1.rsb` | code `0x00273ad4` |
| `0x0058b3a0`…`0x0058b460` | `decal_effect3/4/5/6/7/9/10.rsb` | **no xref, no data ptr** |
| `0x0059951b` | `host0:P:\Ike\release\new_data\new\decal_effect10.bmz` | — |
| `0x00599550` | `host0:P:\Ike\release\new_data\new\bulletholes_sfx.bmz` | — |
| `0x005993e8` | `…\billboard_effect_blood_balpha.bmz` | — |
| `0x00589580` | `MuzzleFlashPool` | code `0x00244a94` |
| `0x00589590` | `muzzle_flash.qob` | — |
| `0x005890f8` | `shell_casings` | data ptr `0x005782f4` |
| `0x00588450` | `iw_brass.qob` | — |
| `0x00599728` | `tracer_effect` | data ptr `0x0057b26c` |
| `0x00584bb0` / `0x00584bd0` | `MuzzleFlashScale` / `TracerFrequency` | atom table `0x005770d8` / `0x005770e0` (config keys) |
| `0x0057f288` | `BloodOn` | code `0x001442b8`, `0x00144990` (config read/write) |
| `0x00590a90` / `0x00590ae0` | `BLOOD` / `BLOOD_T` | menu widget ids |
| `0x00589950`–`0x00589dc0` | 27 `e_bullet_*.wav` impact/ricochet sounds (`_dirt`, `_wood`, `_water`, `_con`, `_hmet`, `_lmet`, `_ric1/2`, `_wric2/3`, `_sric1/2`, `_mric1/2/3`, `_dric/1/2`, `_wiz1..4`) | — |

**Verified negative:** the Ghost Recon PS2 symbol names (`BulletHolePS2`,
`BulletHoleManagerPS2`, `IkeEffectsMgr::DisplayBullethole`, `BloodPoolPS2`, `EffMgrPS2`)
do **not** appear as strings anywhere in Jungle Storm — SLUS_208.20 is stripped, so class
names survive only where the code passes them as data. The named `decal_type1..3` entries in
the effect table are the moddable handle.

Key code site — `0x00273ac0` is a CodeWarrior static-init function (registered via the
`(init, ?, dtor)` triple at `0x00273aa0` which tail-jumps to the registrar `0x0026d460`).
It loads `decal_effect1.rsb` through the resource manager at `0x0067e7f8` and stores the
handle in the global at `0x00628618`; sibling globals `0x00628630`, `0x00628638` are filled
a few instructions later. GUESS: the remaining `decal_effect*.rsb` names are reached by
pointer arithmetic from `0x0058b370` (they are **not** uniformly strided — `decal_effect2`
and `decal_effect8` are absent from the pool entirely, and the gap `0x0058b370→0x0058b3a0`
is 0x30 while all later gaps are 0x20). Not traced further.

### 2b. PARTICLE / effect systems — all in `js`

**The single highest-value structure found for this family** is the master effect-type
name table:

```
base   0x00578190      slot i -> char*   (103 slots, last at 0x00578328)
read by:  0x00242b34 , 0x00243818 , 0x002458f4
          all three are  sll $v1,$sX,2 ; addiu $v0,$v0,-0x7e70 ; addu ; lw  -> name = tbl[index]
```

Contents, in index order:

| idx | names |
|---|---|
| 0–8 | `fire_{small,medium,large}_type{1,2,3}` |
| 9–17 | `smoke_{small,medium,large}_type{1,2,3}` |
| 18–67 | `general_type01` … `general_type50` |
| 68–85 | `explosion_{small,medium,large}_type{1,2,3}`, `_electrical`, `_dirt`, `_water` |
| 86–88 | `debris_type1/2/3` |
| 89 | `shell_casings` |
| 90–92 | `shock_wave_type1/2/3` |
| 93 | `spotlight_type1` |
| 94–96 | `decal_type1/2/3` |
| 97–99 | `lighthalo_type1/2/3` |
| 100 | `foliagesetup` |
| 101 | NULL |
| 102 | `damage` |

(Index arithmetic derived from `(VA - 0x00578190)/4`; the table starts at `0x00578190`
because `0x0057818c` holds `0x00000000` and `0x00578188` holds `0x00000101`.)

Asset name blocks (contiguous, no individual xrefs — loaded by index/base arithmetic):

| VA range | contents |
|---|---|
| `0x0058b490`–`0x0058ba90`+ | `particle_effect01.pob` … `particle_effect59.pob` (59 files, stride 0x20) |
| `0x0058b2d0`–`0x0058b350` | `billboard_effect2/3/7/8/10.rsb` |
| `0x0058bbf0` / `0x0058bc10` / `0x0058bc60` | `projectile_effect1.rsb`, `projectile_light_effect1.rsb`, `ProjectileLightEffect5.rsb` (code xref `0x0027d3d4` on the first) |
| `0x005991a0`–`0x00599550` | the `host0:P:\Ike\release\new_data\new\*.bmz` source-build paths for every billboard/particle/snowflake/decal atlas |
| `0x0059964c` / `0x0059967c` / `0x0059968e` | `ike_fx_dust`, `ike_fx_firesparks`, `ike_fx_hit_spark` |
| `0x00599784` | `smoke_dark_optimize` |
| `0x00594f40` | `smoke_small_type1(1000000)` — a literal spawn command, referenced inside the big function at `0x00352358` |

Config/weather keys in the atom table: `0x00585268 Rain`, `0x00585270 Snow`,
`0x00585278 Weather`, `0x005853b8 WeatherIndex` (atom entries `0x005772f8`, `0x00577300`,
`0x00577308`, `0x005773a0`); `0x00585ce8 effects.xml` / `0x00585d88 effects.xbs`
(`0x00577960` / `0x00577990`) — the effects database is an XML file compiled to `.xbs`.
`0x0058b290 sphere_billboard.qob` has a direct code xref at `0x0026cbc0`.

**Verified negative:** `IkeParticleEffect`, `IkeTriParticleEffect`, `RSParticleSystem`,
`EffectManager`, `Emitter`, `RainEmitter`, `WindEmitter` — none present as strings.

### 2c. FIRST-PERSON / VIEW MODEL — **answered**

Only 8 view-family strings exist in the whole ELF, and 6 of them are the camera-view enum:

```
0x00595d50  first person camera
0x00595d70  third person camera
0x00595d88  cinema camera
0x00595d98  chase camera
0x00595da8  ghost camera
0x00595dc0  cinematics camera
0x005965b8  CameraPoint          (model attach-point name, in the <gun> locator block)
0x00586268  Interview            (unrelated)
```

All six are materialised in one function. `xref js` gives the second half of each pair:
`0x00388a90`, `0x00388aa8`, `0x00388ac0`, `0x00388ad8`, `0x00388af0`, `0x00388b08`.

#### The function: `0x003889d0` — `SetCameraView(this, mode)`

```
003889d0  addiu  $sp, $sp, -0x30
003889e0  sw     $a1, 0x70($a0)          <-- STORE the view mode into this+0x70
003889e4  lw     $v0, 0x70($a0)
003889e8  slti   $v0, $v0, 3
003889ec  xori   $v0, $v0, 1             <-- v0 = (mode >= 3)
003889f0  sb     $v0, -0x4340($at)       <-- global byte 0x0062bcc0 = (mode >= 3)
003889f4  lw     $v0, 0x70($a0)
003889f8  slti   $at, $v0, 3
003889fc  beqz   $at, 0x388a1c
00388a04  jal    0x387ea0
00388a14  lui    $v0, 0x3f80             <-- 1.0f
00388a18  sw     $v0, 0xb0($s0)          <-- this+0xb0 = 1.0f  (only when mode < 3)
00388a1c  sw     $zero, 0xc0($s0)        <-- this+0xc0 = 0
00388a40  lui    $at, 0x63
00388a44  lbu    $v1, -0x4560($at)       <-- debug flag byte 0x0062baa0
00388a48  beqz   $v1, 0x388b68           <-- if clear, skip the on-screen label entirely
00388a58  lw     $v0, 0x70($s0)
00388a5c  sltiu  $at, $v0, 7             <-- 7 cases
00388a68  lui    $v1, 0x59
00388a70  addiu  $v1, $v1, 0x5de0        <-- jump table at 0x00595de0
00388a7c  jr     $v0
```

#### Answers

* **Struct offset holding the current view: `+0x70`** (a 32-bit int) on the camera/
  sim-controller object. `sw $a1, 0x70($a0)` at `0x003889e0` is the only writer in this
  function, and every reader (`0x00387944`, `0x00388754`, `0x0038876c`, `0x003889b0`,
  `0x0038b400`) uses the same offset on the same object.
* **The enum value for first person is `0`.** Verified from the jump table at `0x00595de0`:

| value | jump target | string materialised there |
|---|---|---|
| **0** | `0x00388a84` | **`first person camera`** |
| 1 | `0x00388a9c` | `third person camera` |
| 2 | `0x00388ab4` | `cinema camera` |
| 3 | `0x00388acc` | `chase camera` |
| 4 | `0x00388ae4` | `ghost camera` |
| 5 | `0x00388b0c` | (falls through to the common exit — **no label**, unused/reserved) |
| 6 | `0x00388afc` | `cinematics camera` |

  (`0x00595de8` = 4 and `0x00595dfc` = 8 are outside the `sltiu … ,7` guard; the word at
  index 8, `0x00389ccc`, belongs to a different table.)

* **`mode < 3` means "attached to a player"**: the setter only writes the 1.0f at
  `this+0xb0` for modes 0/1/2, and it publishes the boolean `(mode >= 3)` to the global
  byte at **`0x0062bcc0`**, which is read from 12 sites in `0x003a6414`–`0x003bb924`
  (rendering/HUD) and written from three (`0x003886b4`, `0x003886d0`, `0x003889f0`).
  That global is the practical "is the camera detached from the soldier" flag.
* **Forcing first person**: two sites already do it directly —
  `0x00388768  sw $zero, 0x70($s1)` and `0x003889ac  sw $zero, 0x70($s0)`, each immediately
  followed by `lw $a1,0x70($sX); jal 0x003889d0`. GUESS (untested): writing 0 to `+0x70`
  and calling `0x003889d0` is sufficient to force first-person.
* **`0x0062baa0`** gates the on-screen camera-mode label — it is a debug/dev flag; when 0
  the whole switch is skipped. This is why the six enum strings are dead in retail.
* The camera object itself is held in the global **`0x0062baa8`** (written at `0x0015acb8`,
  cleared at `0x0015ae4c`, read from ~25 sites in `0x0038b260`–`0x0038b4b0`).
* **Weapon-attached first-person camera**: the `<gun>` model locator block at `0x00596590`
  is `MuzzleFlashPoint` / **`CameraPoint`** / `BrassEjectionPoint`; a second block at
  `0x005966e0` is `MuzzleFlashPoint` / `BrassEjectionPoint` / `BackBlastPoint` /
  `RightHandPoint`. So the first-person camera is positioned from a named locator on the
  weapon `.qob`.

**Verified negative:** there is no view-model / "hands" / "arms" / FOV vocabulary anywhere
in the pool — `grepstr js '(?i)fov|viewangle|^View|SimCamera|Hide'` returns only
`CameraPoint`. `RSSimController::Hide` from the sister title is not present. The
first-person view reuses the soldier model; there is no separate 1P arms asset.

### 2d. ENEMY SPAWNING / REINFORCEMENT — highest value, all in `js`

#### The mission-script vocabulary (atom table at `0x00576880`, 606 × 8 bytes)

Entity types (`0x00577478`–`0x005774c0`):
`Actor, Team, Platoon, Company, Vehicle, Plan, Zone, Object, Effect, Tag`.

Plan/behaviour verbs (`0x00577528`–`0x005776c8`, alphabetical — this is the `Plan` grammar):
`Actor, AddZone, Alertness, Ambush, Animation, ClearRoom, CombatROE, Company, Cover,
DefendZone, DestroyTarget, Disengage, Effect, EffectList, EnterVehicle, ExitVehicle,
Follow, Formation, Grenades, MoveROE, Note, NoteList, Object, ObjectList, Orientation,
Pace, Path, Patrol, Plan, PlanList, Platoon, Point, Restart, Room, RoomList, Sound,
SoundList, Speed, Stance, Station, StationList, Team, ToggleAI, Units, UnloadVehicle,
Vehicle, Voice, Wait, Waypoint, WaypointList, WeaponSelect, Zone, ZoneList`.

Attribute vocabulary (`0x005776d0`–`0x005778f0`): `Action, Allied, Assigned, Available,
Base, CampaignLoad, CentralArea, Change, Cold, DisableProp, Driver, Easy, Enabled, EnvTag,
Extraction, Facing, File, Flee, Grounded, Hard, Height, Hidden, Idle, IgorId, Insertion,
Interior, Is3D, 3D, Kit, Lvl, Links, MaxPeriod, MaxPlays, MinPeriod, Name, Normal, Owner,
PlatoonLeader, Plan, Platoon, Point, Pos0, Pos1, Pos, Priority, Range, Rate, ReconIn,
ReconOut, Room, ScriptId, Sound, Speed, Stance, Startup, State, Target, Text, TextId, Time,
Type, Vehicle, Volume, NeverStop, AssaultPlatoon, CoopBase`.

Actor-file schema (`0x00577a78`–`0x00577af8`): `ActorFile, VersionNumber, ModelName,
BlinkFaceName, ModelFace, LOD2, LOD3, LOD4, Weapon, Stamina, Stealth, Leadership,
BonusLead, ActorName, ClassName, KitPath, ArmorLevel`.

Kit schema (`0x00577eb8`–`0x00577f10`): `KitTexture, KitFile, Firearm, ThrownItem,
HandHeldItem, SlotNumber, ItemFileName, Count, MagazineCount, ExtraAmmo, GrenadeLauncher`.

Wildcards used to enumerate content at load time:
`0x0057ec38 actor\*.atr` (code `0x0012feb4`, `0x001341e0`, `0x00134240`),
`0x0057ec58 actor\*.vcl`, `0x0057ec88 mission\*.gtf`, `0x0057ec98 mission\*.mis`
(code `0x00130fd4`), and MP rosters
`0x0057ed80 actor\MP Actor Files\Platoon 1\*.atr` … `Platoon 4\*.atr` (code `0x00138074`),
plus class rosters `0x0058eea0 actor\rifleman\*.atr`, `actor\demolitions\*.atr`,
`actor\sniper\*.atr`, `actor\heavy-weapons\*.atr`.

#### The three named spawn-plan classes

`VehicleRestartPlan`, `TeamPatrolZone`, `TeamRestartPlan` appear **twice each**, in two
parallel tables — a name and (GUESS) a factory/RTTI list:

| VA | string | code xref |
|---|---|---|
| `0x005980d0` | `VehicleRestartPlan` | `0x005d42e8` (static-init region) |
| `0x00598198` | `TeamPatrolZone` | `0x005d4588` |
| `0x00598280` | `TeamRestartPlan` | `0x005d4858` |
| `0x00598890` / `0x00598958` / `0x00598a40` | same three names | `0x005d5398` for `TeamVoice` at `0x00598a20`, same block |

These are the sister title's `TeamRestartPlan` / `VehicleRestartPlan` /
`TeamPatrolZoneBehavior`. **This is the only AI-respawn mechanism named in the build.**

#### The opposing-force generator — `0x00349f50`

One very large function, `0x00349f50`–`0x00353c40` (frame `0x11d0` bytes, referenced from a
vtable slot at `0x005b2908`, no direct `jal` caller). It contains the entire runtime enemy
construction. Verified sequence:

```
0035057c  sprintf(buf, "opposing_force_jungle_%i.atr", $s2)   ; 0x00594f00
00350588  jal 0x0016d4d8            (sprintf)
0035059c  jal 0x003ff1b0            (file-exists / open test)
003505c8  addiu $s2,$s2,1  ; loop back to 0x0035057c
                       -> $s2 = number of opposing_force_jungle_N.atr present

003505d4  sprintf(buf, "opposing_force_%i.kit", $s1)          ; 0x00594f20
00350620  addiu $s1,$s1,1  ; loop back to 0x003505d4
                       -> $s1 = number of opposing_force_N.kit present

00350638  lw  $a1, 0x005797f8       -> "_Opposing Company"    ; 0x00594e10
00350658  jal 0x0036c640            (create Company)
0035066c  lw  $a1, 0x00579800       -> "_Opposing Platoon"    ; 0x00594e30
00350690  jal 0x0036c330            (create Platoon)
00350698  addiu $s5, $s2, -1        ; max actor index
0035069c  addiu $s6, $s1, -1        ; max kit index
003506bc  lw  $a2, 0x00579808       -> "_Opposing Team"       ; 0x00594e48
003506c4  addiu $a1, $a1, 0x4f38    -> "%s%i"                 ; 0x00594f38
003506c8  jal 0x0016d4d8            sprintf  -> "_Opposing Team1", "_Opposing Team2", ...
```

So the opposing force is built at runtime as
`_Opposing Company` → `_Opposing Platoon` → `_Opposing Team%i` → actors picked from
`opposing_force_jungle_%i.atr` with kits from `opposing_force_%i.kit`, and the counts are
**discovered by probing the filesystem**, not hardcoded. A fourth name,
`0x00594e60 _Opposing Human`, exists in the same atom block (`0x00579810`, `0x00579830`).

The same function also builds the debug/editor-spawned hierarchy:

| VA | string | code site |
|---|---|---|
| `0x00594e98` | `_Spawned Actor` | `0x0034f6ac` |
| `0x00594ea8` | `_Spawned Team` | `0x0034f8d4` |
| `0x00594ec0` | `_Spawned Platoon` | `0x0034fa48` |
| `0x00594ee0` | `_Spawned Company` | `0x0034fb6c` |

and issues `smoke_small_type1(1000000)` at `0x00352358` (string `0x00594f40`) — a literal
effect-spawn command string with an explicit lifetime, confirming the effect system takes
`name(param)` text commands.

Other spawning-adjacent tables:
`0x005959d8 \Company%d.toe` (code `0x0037c940`) — the TO&E (table of organisation and
equipment) file per company; `0x005959e8 _Platoon%d`; `0x00590d70`–`0x00590da0`
`_Company`, `_Company2`, `_Platoon`, `_Platoon2` (the two player platoons).

#### Verified negatives for this family (precise, and important)

* `grepstr js '(?i)spawn|reinforc|respawn'` returns **only 7 hits**, and **none is an AI
  reinforcement system**: `RESPAWN_CTRL` (`0x00592148`) and `EDRESPAWN`
  (`0x00592768`, `0x00593750`) are **multiplayer lobby widget ids** — verified by
  disassembling their neighbours: `0x002f7b2c MAPNAME_CTRL`, `0x002f7b40 TIMELIMIT_CTRL`,
  `0x002f7b54 RESPAWN_CTRL`, `0x002f7b68 LANGUAGE_CTRL`; and `0x00303734 EDDIFFICULTY`,
  `0x00303750 EDRESPAWN`, `0x0030376c EDTYPE`. The other four are the `_Spawned *` names
  above.
* `grepstr js '(?i)wave'` returns **only** `shock_wave_type1/2/3` — there is **no
  reinforcement-wave system** in Jungle Storm.
* `grepstr js '(?i)squad|fireteam|fire team'` returns **nothing**. The sister title's
  `FireTeam` / `FireTeamAI` vocabulary is absent; the hierarchy here is
  Company → Platoon → **Team** → Actor.
* `Company`/`CompanyAI`/`PlatoonAI`/`HumanAI`/`AwarenessMgr`/`IkeRulesMgr`/`IkeScriptMgr`
  do not appear as strings (stripped build).

---

## 3. Which image owns what

**The boot ELF owns 100% of the gameplay. Neither overlay contains any game logic.**

Evidence, in order of strength:

1. **Feature-string census is a clean zero.** Across decals, particles, camera/view and
   spawning, `offline.bin` and `online.bin` score **0 matches each**, against 75/130/8/160
   in the ELF. The overlays contain no `.mis`, `.atr`, `.kit`, `.rsb`, `.qob`, `.pob`,
   `.wav` or `.bmz` filename, no mission name, no menu id, no effect name.

2. **What the overlays actually are:**
   * `offline.bin` = the **Fonix ASRSPI speech-recognition engine** (10 real strings, all
     library version banners). Its only ELF entry points are 13 functions in
     `0x00693ff8`–`0x00695750`, and **every caller lives in one 3 KB ELF module,
     `0x0055758c`–`0x0055806c`** — the ASR wrapper. That wrapper also owns
     `0x00557f50 CTX`, `0x00557f8c WRD`, `0x00557fc8 GCD` (grammar file tags),
     `0x00558158 GR_5_`, and the small word-normalisation table `goto/go to`,
     `atall/at all`, `cost/costs` at `0x005575d0`–`0x00557648`. The acoustic models it
     loads are named in the **ELF** pool: `asr16v220_{enu200,frf200,spe300,iti300,ged300}_float_4b.lng`
     at `0x0059fda0`–`0x0059ff70` (xrefs `0x00559be8`, `0x00559e38`, `0x0055b2e8`,
     `0x0055b578`, `0x0055b808`). Related ELF-side UI: `0x0058d7e0 HELP_VOICECOMMAND`,
     `0x0058d8e8 VOICE COMMANDE`, `0x00589e40 i_voicechk.wav`, `0x00593040 FL_VOICE`,
     `0x00593120 GL_VOICE_%d`.
   * `online.bin` = the **Ubi.com GameService lobby/matchmaking/crypto/ladder client**
     plus the PS2 `eenet` TCP stack (see §1c). Its ELF entry points are 96 functions; the
     callers cluster in two ELF modules, `0x0019e000`–`0x001a8000` (protocol glue) and
     `0x00531000`–`0x00542000` (lobby UI glue).

3. **Call-direction analysis.** Counting every `jal` word:

   | | total jal | internal to overlay | into boot ELF | distinct ELF targets |
   |---|---|---|---|---|
   | offline.bin | 2947 | 1614 | 1333 | **42** |
   | online.bin | 11368 | 9232 | 2136 | **102** |

   Only **42** and **102** distinct ELF functions are ever called back. The heaviest are
   `0x00558480` (×378), `0x00558350` (×154), `0x00558390` (×85) for offline — the
   CodeWarrior soft-float/helper block immediately adjacent to the ASR wrapper — and
   `0x0016a510` (×283), `0x001a54d0` (×249), `0x001a5490` (×197), `0x0016d4d8` (×192,
   `sprintf`), `0x0016dc68`, `0x0016e3c8`, `0x001188d0` for online — i.e. **CRT/allocator/
   string helpers**. No overlay calls any of the gameplay functions identified in §2.

4. **The ELF is statically linked against overlay addresses**, and it is linked against
   *both*. Of the 122 distinct overlay-region targets reachable from ELF text
   (`0x00100000`–`0x0055c000`), 96 are function prologues in `online.bin` only, 13 are
   prologues in `offline.bin` only, 1 in both, 11 in neither (jump-table/thunk entries).
   Verified by comparing the same VA in both images, e.g. `0x006cd898` is
   `addiu $sp,$sp,-0x30` (prologue) in online but mid-function in offline; the ELF call at
   `0x00531940` is therefore an **online** call. Both overlays load at `0x00692700` and
   are swapped: `0x00307b34` loads `host:offline.bin` immediately before touching the
   menu id `0x00592a70 PS2_MULTI_SPLITSCREEN`, and `0x00307c20` loads `host:online.bin`.

**Conclusion for the mod tool:** target **`SLUS_208.20`** for every gameplay feature —
decals, particles, camera/view, AI, spawning, missions, kits, actors, menus and
localisation. `offline.bin` is only worth touching to alter voice-command recognition;
`online.bin` is only worth touching for Ubi.com network behaviour (and the service is dead).
Neither overlay should be in scope for gameplay modding.

---

## 4. What I could not determine, and the next probe

| open question | why it stalled | next probe |
|---|---|---|
| How `decal_effect3..10.rsb` / `particle_effect02..59.pob` / `billboard_effect*.rsb` are selected | Only the first name of each block has a `lui/addiu` xref; the rest have neither a code xref nor a data pointer. Names are **not** uniformly strided (`decal_effect2` and `decal_effect8` do not exist at all), so a simple `base + i*0x20` index cannot be the whole story. | Disassemble `0x00273ac0`–`0x00273c40` (decal init), `0x002769f4`'s enclosing function (particle init) and `0x0026cbc0` fully; look for a `.bmz` archive-directory read that maps ordinal→name, since every one of these names also exists as a `host0:P:\Ike\release\new_data\new\*.bmz` build path. |
| What object type owns `+0x70` (the camera-view field) | The build is stripped, the object is reached via the global `0x0062baa8`, and the allocation site was not traced. Field layout observed so far: `+0x70` view enum (int), `+0xb0` float set to 1.0f when view < 3, `+0xc0` int cleared on every view change. | `xref js 0062baa8` → the writer at `0x0015acb8`; walk back to the `new`/placement site to get the allocation size, then diff the layout against the Ghost Recon PS2 symbol `SimCamera` (`rsetool.py sym SimCamera`) which retains full C++ names. |
| Whether writing 0 to `+0x70` genuinely forces first person in-game | Static analysis only; no emulator was used per the brief. | Patch `0x0038879c`-adjacent input handler, or set `0x0062baa0` (the debug label flag) to 1 first so the mode is observable on screen, then run under PCSX2. |
| The `.mis` binary record layout that carries `TeamRestartPlan` / `Insertion` | The keyword table proves the vocabulary but not the on-disc encoding; all mission data lives in `gr.img`, which is out of scope for this agent. | Extract one `.mis` (e.g. `c01_plantation.mis`) from `gr.img` and match its token ids against the 606-entry atom table at `0x00576880` — the zeroed second word of each atom entry is the runtime id slot, so the parser at the `0x0012feb4`/`0x00130fd4` wildcard sites will show how ids are assigned (likely sequential on registration). |
| Whether `opposing_force_jungle_%i.atr` files actually ship | Only the probe loop was verified; the file set lives in `gr.img`. | List `actor\` in `gr.img` and count `opposing_force_jungle_*.atr` / `opposing_force_*.kit`. Adding files there would increase enemy variety with **no code patch**, since the count is discovered by probing. |
| The 11 ELF→overlay targets that are prologues in neither image | Probably PLT-style thunks or data-relative entries. | `word js <target>` on each and check whether they sit inside the overlay's data range (`>= load VA + text size`). |

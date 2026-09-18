# Rainbow Six Vegas (PC) — moddable surfaces dossier

Install: `D:\SteamLibrary\steamapps\common\Rainbow Six Vegas`
Build: UE3 (Ubisoft Montreal "Keller" branch). Exe `Binaries\R6Vegas_Game.exe`, 30,572,544 bytes, 2024-03-27 (Steam).
Everything below was read this session. Guesses are labelled GUESS.

---

## Config precedence

### Answer first

**A mod tool must write to `KellerGame\Config\PC\Keller<Name>.ini`.**
It must **leave the trailing `[Internal] CRC=0x...` line exactly as found** (do not recompute it).
It must **not** touch `KellerGame\Config\Default*.ini` or `KellerGame\Config\PC\Default*.ini` unless it deliberately wants a full regeneration.
`KellerGame\Config\PCKeller<Name>.ini` (the files at the Config root) are **dead shipped snapshots** — the running game neither reads nor writes them.

### Evidence

**1. The exe hard-codes the `PC\` config directory.**
Extracted ASCII+UTF-16 strings from `Binaries\R6Vegas_Game.exe` (script at `…\scratchpad\exestr.py`, dump at `…\scratchpad\exe_strings.txt`). Relevant literals:

```
..\KellerGame\Config\
..\KellerGame\Config\PC\
..\KellerGame\Config\PC\AgoraConfig.lua
..\KellerGame\Config\MovieLoading.ini
%sKeller%s.ini
%s%s%s%s.ini
%s%s%sGame.ini          %s%s%sEngine.ini       %s%s%sEditor.ini
%s%s%sInput.ini          %s%s%sJoysticks.ini    %s%s%sAIActionTypeConfig.ini
%s%sServerOptions.ini    %s%sAIActionTypeConfig.ini
```
`exe_strings.txt` lines 29373–29376. The format `%sKeller%s.ini` fed with the directory `..\KellerGame\Config\PC\` produces exactly `..\KellerGame\Config\PC\Keller<Name>.ini`. The paths are relative to `Binaries\`, which is the working directory when `R6Vegas_Game.exe` runs.
`..\KellerGame\Config\PC\AgoraConfig.lua` exists on disk (`KellerGame\Config\PC\AgoraConfig.lua`, 1403 bytes), which independently confirms `Config\PC\` is the live config directory, not a template stash.

**2. Only the `PC\Keller*.ini` files have been written since install.** All 4 config directories were laid down by Steam on 2024‑03‑27. Four files carry later mtimes, and they are all in `Config\PC\`:

| file | mtime |
|---|---|
| `KellerGame\Config\PC\KellerEngine.ini` | 2024‑08‑15 |
| `KellerGame\Config\PC\KellerGame.ini` | 2024‑12‑11 |
| `KellerGame\Config\PC\KellerConsole.ini` | 2024‑12‑11 |
| `KellerGame\Config\PC\KellerServerOptions.ini` | 2024‑12‑11 |

Nothing under `KellerGame\Config\*.ini` (root), `KellerGame\Config\PC\Default*.ini`, or `Engine\Config\` has a post‑install mtime.

**3. The content of those files is this user's own runtime state.** `diff KellerGame\Config\PCKellerServerOptions.ini KellerGame\Config\PC\KellerServerOptions.ini`:

```
PC\KellerServerOptions.ini:35-63   m_iMap=60
                                   m_iSelectedMaps[0]=60 … m_iSelectedMaps[19]=92
                                   m_fstrLANName=BRAGME
                                   m_eHostileDensity=GAMEHOSTILEDENSITY_HIGH
                                   m_bPunkBusterSv=False / m_bPunkBusterCl=False
                                   m_iChatDisplayDuration=5
PCKellerServerOptions.ini:35-55    m_iMap=-1
                                   m_iSelectedMaps[0..19]=-1   (all -1, i.e. never used)
                                   (m_fstrLANName / m_eHostileDensity / m_bPunkBuster* absent entirely)
```
`m_fstrLANName=BRAGME` matches `Binaries\User` line 3 `Name=BRAGME`. The `PC\` copy also has **keys the shipped copy does not have at all** — the runtime added them. This is conclusive: `Config\PC\Keller*.ini` is the read/write layer.

`KellerGame\Config\PC\KellerConsole.ini` lines 6–21 are `History[0]=` … `History[15]=` (a console scrollback array) and line 22 `bEnableUI=False` — more runtime-written state. The template `KellerGame\Config\DefaultConsole.ini` is 3 lines long (`[R6Game.R6Console]` / `TypeKey=F12`) and the live file says `TypeKey=RightBracket`, i.e. the live file is NOT a copy of the template.

**4. The layer set is not symmetrical.** `Config\PC\` has generated `KellerCharacter.ini` and `KellerEditor.ini`; the Config root has no `PCKellerCharacter.ini` / `PCKellerEditor.ini`. The `PC\` set is the complete one.

### The `[Internal] CRC=` line — cracked

25 ini files carry a trailing block:
```
[Internal]
CRC=0x<8 hex>
```
(14 in `Config\PC\`, 11 at the Config root — full list from `grep -rn "^CRC=" KellerGame\Config`.)

**Algorithm: UE3 `appMemCrc`** — non-reflected CRC-32, polynomial `0x04C11DB7`, init `0xFFFFFFFF`, final XOR `0xFFFFFFFF`, MSB-first (`crc = (crc<<8) ^ T[(crc>>24) ^ byte]`). Not zlib CRC-32 (reflected) — zlib does not match any of them. Verified script: `…\scratchpad\crc3.py`.

**What it is computed over: the raw bytes of the corresponding `Default<Name>.ini` template — NOT of the file it sits in.** Confirmed matches:

| generated file | stored CRC | = appMemCrc(raw bytes of) |
|---|---|---|
| `PC\KellerWeaponsConfig.ini` | `0x9ccab51a` | `KellerGame\Config\PC\DefaultWeaponsConfig.ini` |
| `PC\KellerAIActionTypeConfig.ini` | `0xb09dead2` | `Default(PC\Default)AIActionTypeConfig.ini` |
| `PC\KellerDamageTypesConfig.ini` | `0x13058609` | `Default(PC\Default)DamageTypesConfig.ini` |
| `PC\KellerExplosivesConfig.ini` | `0x5faece2b` | `Default(PC\Default)ExplosivesConfig.ini` |
| `PC\KellerGadgetsConfig.ini` | `0x14b455cb` | `Default(PC\Default)GadgetsConfig.ini` |
| `PC\KellerProjectilesConfig.ini` | `0x20eb1992` | `Default(PC\Default)ProjectilesConfig.ini` |
| `PC\KellerCharacter.ini` | `0x71efca1a` | `Default(PC\Default)Character.ini` |
| `PC\KellerJoysticks.ini` | `0x933d416e` | `Default(PC\Default)Joysticks.ini` |

(Where the row says "Default(PC\Default)", root and `PC\` templates are byte-identical so both match; `cmp` says only `DefaultEngine.ini`, `DefaultServerOptions.ini` and `DefaultWeaponsConfig.ini` differ between root and `PC\`. For WeaponsConfig **only `PC\DefaultWeaponsConfig.ini` matches** — see the decimal-separator note below. That makes `KellerGame\Config\PC\Default*.ini` the real template layer and the root `Default*.ini` a leftover.)

Six generated files did not resolve to a single-file CRC — `PC\KellerGame.ini`, `KellerEngine.ini`, `KellerInput.ini`, `KellerEditor.ini`, `KellerConsole.ini`, and `PCKeller*` copies of the same. GUESS: those four have a `BasedOn=` merge chain (`Engine\Config\BaseGame.ini` → `Engine\Config\PC\PCGame.ini` → `KellerGame\Config\DefaultGame.ini`), so the CRC covers the merged buffer rather than one file on disk. I tried raw/stripped/CRLF/LF/concatenation variants and none hit (`…\scratchpad\crc4.py`).

**Practical consequence for a mod tool (the important part):**
- The CRC is a **staleness fingerprint of the template**, not a tamper check on the generated file — it cannot be, since it does not cover itself. GUESS (strong, mechanism is standard UE3/Ubisoft): at startup the game recomputes `appMemCrc(Default<X>.ini)`; if it differs from the stored value it regenerates `PC\Keller<X>.ini` from the template, discarding edits; if it matches it keeps the file as-is.
- Therefore: **edit `PC\Keller<X>.ini` in place, leave `[Internal] CRC=` untouched, and do not modify `Default<X>.ini`.** Edits survive.
- The inverse strategy also works and is arguably safer for a "reset to stock" button: edit `PC\Default<X>.ini`, and delete the `[Internal]` block (or the whole file) from `PC\Keller<X>.ini` to force regeneration. Cost: it wipes user settings stored in the same file (key bindings, server options).
- The exe does contain `CRC check failed` / `CRC error` strings (`exe_strings.txt` lines 104558–104559), but I could not tie them to the config system — they may belong to the archive/patch code. **Not verified**, so a tool should be conservative and preserve the line.

### Decimal separator — the prompt's premise is half wrong

The task brief said values use a decimal **comma** (`m_fSuppressorDamageModifier=0,8`). That is true of **exactly one file**, and it is the dead one:

| file | lines matching `=…<digit>,<digit>` |
|---|---|
| `KellerGame\Config\DefaultWeaponsConfig.ini` (root) | **2243** |
| `KellerGame\Config\PC\KellerEditor.ini` | 1 |
| every other ini under `KellerGame\Config` and `Engine\Config` | 0 |

The **live** file `KellerGame\Config\PC\KellerWeaponsConfig.ini` has **zero** comma-decimals — it uses a decimal point:
```
PC\KellerWeaponsConfig.ini:6    m_fSuppressorDamageModifier=0.8
DefaultWeaponsConfig.ini:6      m_fSuppressorDamageModifier=0,8
```
The root `DefaultWeaponsConfig.ini` is a stale export from a French/European-locale dev machine. It differs from the live file in **values as well as format**, so it is not just a reformat:
```
DefaultWeaponsConfig.ini:19   m_iInitialBulletSpread=60        vs  PC\Keller…:19  =220
DefaultWeaponsConfig.ini:27   m_iMovementBulletSpreadMinSpread=110  vs  =220
DefaultWeaponsConfig.ini:29   m_fMovementBulletSpreadMinMoveSpeed=250 vs =150
```
**Rule for an editor:** do NOT normalise decimal separators. Round-trip byte-for-byte whatever the file uses. If it ever writes the root `DefaultWeaponsConfig.ini` it must emit commas; for the live `PC\` files it must emit points.

### Other formatting an editor must round-trip

Checked in `KellerGame\Config\PC\KellerWeaponsConfig.ini`:
- **`f` suffixes on floats**: 684 lines end in a literal `f`, e.g. line 59 `m_fWeaponLength=65.0f`, line 142 `m_fReloadTacticTime=2.666f`. Adjacent lines have no suffix (line 148 `m_fTPReloadTacticalUpdateAmmoTimer=2.3`). Both parse; preserve the original form.
- **Struct literals**: line 71 `m_vFirstPersonMeshTranslation=(X=-2.0f,Y=7.5f,Z=-1.5f)`, line 72 `m_rFirstPersonMeshRotation=(Pitch=200,Yaw=200,Roll=-100)`.
- **Repeated keys are arrays, not duplicates**: lines 236–239 are four consecutive `m_fireModeAvailability=` lines (`false,false,false,true`). A naive dict-based ini parser will collapse these and break every weapon's fire modes. Same pattern in `PC\KellerCharacter.ini` (`m_sIdlesKnifeFPAnims=` twice, lines 2–3).
- **Indexed keys**: `m_iSelectedMaps[0]=…` in ServerOptions; `History[0]=` in Console.
- **Line endings are CRLF** and files end with a blank line after the `[Internal]` block.
- A few keys use spaces around `=`: `KellerGame\Config\DefaultGame.ini` tail — `m_fVoiceRadius = 1500`.

### Files a mod tool should NOT bother with
- `Binaries\User` — 4 lines, `[DefaultPlayer] TEAM=-1 / Name=BRAGME / Class=`. Player name only; not a config layer.
- `%USERPROFILE%\Documents\Ubisoft\R6Vegas\` — contains only binary blobs, **no ini at all**: `R6GameConfig.bin` (846 B), `R6_EquipEquipmentTemplate` (489 B), `R6_ProfileOPTIONS` (97 B), `R6_SaveCHECKPOINT` (500 B), all 2025‑02‑10. Video/audio/control options and the save live here in binary. Not a text layer; would need its own format work.
- `Engine\Config\Base*.ini` — the engine floor. `BaseGame.ini` is 952 B and generic UE3 (`GameDifficulty=+1.0`, `[Engine.Pawn] Bob=0.0060`, `[Engine.PlayerController] DesiredFOV=85.000000`). Fully overridden by the Keller layer (`PC\KellerGame.ini:6 GameDifficulty=GAMEDIFFICULTY_VETERAN`). Editing it is pointless.
- `Engine\Config\PC\PCGame.ini`, `PCEditor.ini`, `PCInput.ini` — 61–63 bytes each, a single `[Configuration] BasedOn=..\%GAME%Game\Config\Default<X>.ini` redirect. `PCEngine.ini` (562 B) is the only one with real content (`[URL] Port=5437`, `[Core.System] +Extensions=uppc/+Extensions=rmpc`, `RenderDeviceClass=D3DDrv.D3DRenderDevice`).

### Resulting layer order (lowest → highest)

```
Engine\Config\Base<X>.ini                    engine floor, shipped
Engine\Config\PC\PC<X>.ini                   platform redirect (BasedOn=)
KellerGame\Config\Default<X>.ini             STALE leftover (comma-locale weapons file lives here)
KellerGame\Config\PC\Default<X>.ini          <-- real template; CRC source
KellerGame\Config\PCKeller<X>.ini            shipped snapshot, inert
KellerGame\Config\PC\Keller<X>.ini           <-- LIVE. game reads and writes this. EDIT HERE.
%USERPROFILE%\Documents\Ubisoft\R6Vegas\*    binary profile/save, separate problem
```

---

## Levers

All paths relative to `D:\SteamLibrary\steamapps\common\Rainbow Six Vegas\KellerGame\Config\`.
File column gives the **live** file to edit. Line numbers are from the live file unless stated.

### Top tier — the ones a mod manager should ship on day one

| name | file | section | key | stock | effect | conf |
|---|---|---|---|---|---|---|
| Global difficulty | `PC\KellerGame.ini` | `[Engine.GameInfo]` | `GameDifficulty` | `GAMEDIFFICULTY_VETERAN` (L6) | Campaign/default difficulty. Enum: `_NORMAL`, `_VETERAN`, `_ELITE` | high |
| **Terrorist Hunt count** | `PC\KellerServerOptions.ini` | `[Engine.R6ServerOptions]` | `m_eHostileDensity` | `GAMEHOSTILEDENSITY_HIGH` (L62) | T-Hunt enemy population. Enum `_LOW/_MEDIUM/_HIGH` documented at `PC\R6VegasServerConfig.ini:73-75`. **This key exists in NO other config file** — verified by grep: only `PC\KellerServerOptions.ini:62` and `PC\R6VegasServerConfig.ini:76` | high |
| Civilian-kill fail limit | `PC\KellerGame.ini` | `[R6Game.R6ObjectiveKillCivilians]` | `m_iMaxCivilsKilledForGameOver` | `3` (L67) | Kill 3 civilians = mission over | high |
| **Coop leashing (dead feature)** | `PC\KellerGame.ini` | `[R6Game.R6CooperativeGame]` | `m_bUseCoopLeashing` | `false` (L139) | A complete, fully-parameterised coop tether system shipped switched OFF. Its five params are live: `m_LeaderAssignmentZoneRadiusInM=5`, `m_RelocWarningDistFromLeaderInM=20`, `m_RelocDistFromLeaderInM=30`, `m_fCoopLeashRelocationDelayInS=5` (L134-137) | high (value present); effect **unverified** (needs a run) |
| Aim assist | `PC\KellerGame.ini` | `[Engine.PlayerController]` | `bAimingHelp` | `false` (L43) | Master aim-assist switch, off on PC | high |
| **Teammate formation** | `DefaultRainbow.ini` | `[R6Game.R6RainbowManager]` | `m_iFormationAngle` / `m_fFormationDistance` | `4200` / `400` (L2-3) | The *entire* squad-positioning surface for Michael + Jung is these two numbers. Angle is Unreal rotator units (65536 = 360°, so 4200 ≈ 23.1°); distance is UU (~4 m). **This file is 3 lines long and has NO `Keller`/`PCKeller` generated layer — it is the only copy, so edit it directly** | high |
| T-Hunt round rules | `PC\KellerGame.ini` | `[R6Game.R6CoopTerroristHuntGame]` | `MaxLives` / `m_bAllowRespawn` / `m_iTimeBetweenRound` | `0` / `True` / `10` (L129-131) | `MaxLives=0` = unlimited. Note: **no terrorist count here** — that's `m_eHostileDensity` | high |
| FOV | `PC\KellerGame.ini` | `[Engine.PlayerController]` | `DesiredFOV` / `DefaultFOV` | `85.000000` (L44-45 area) | Field of view | med |
| Gravity | `PC\KellerGame.ini` | `[Engine.WorldInfo]` | `DefaultGravityZ` / `RBPhysicsGravityScaling` | `-750.0` / `1.3` | Ragdolls/physics props fall 30% faster than pawns | high |
| Weapon bob | `PC\KellerGame.ini` | `[Engine.Pawn]` | `bWeaponBob` / `Bob` | `true` / `0.0060` | | high |
| Screen shake master | `PC\KellerDamageTypesConfig.ini` | every `[…R6DmgType*]` | `m_fCameraShakeStrength` | `1` | Set 0 in all 35 sections = screen shake off. The 8 shake keys are copy-pasted identically into every weapon section | high |
| Mod content path | `PC\KellerEngine.ini` | `[Core.System]` | `Paths` (additive) | `Paths=..\KellerGame\Content` (L86), `Paths=..\KellerGame\Script` (L87) | **The supported mod-injection point.** `Paths=` is an additive array — append `Paths=..\KellerGame\Mods\<name>`. `Extensions=` (L73-74, L90-93: `upk`,`u`,`rsm`,`rmpc`,`uppc`,`uc`) gates which file types the loader considers | high |
| Allow server downloads | `PC\KellerEngine.ini` | `[IpDrv.TcpNetDriver]` | `AllowDownloads` | `False` | Blocks client-side package download; must be True for custom-content servers | med |
| Startup map | `PC\KellerEngine.ini` | `[URL]` | `MapRetail` / `LocalMapRetail` | `Menu.rmpc` (L11-12) | The `*Retail` trio is what a shipped build actually uses; `Map=Menu.rsm` (L4) is the uncooked equivalent | med |
| Menu/HUD class swap | `PC\KellerEngine.ini` | `[Engine.Engine]` | `MenuInteraction`, `InGameMenuInteraction`, `InGameMPMenuInteraction`, `InGameSplitMenuInteraction`, `PecMenuInteraction` | `R6Game.R6MagmaInteraction*` (L52-56) | Cleanest hook for a total UI replacement | med |

### Weapons — `PC\KellerWeaponsConfig.ini` (8103 lines)

**35 weapon sections**, in file order:
```
Pistols   (6)  ConfigR6PistolMK23 L1 · PistolUSP40 L241 · Pistol92FS L481 · PistolGlock18 L721
               · PistolDesertEagle L958 · PistolRagingBull L1184
SMGs      (6)  SubMP5N L1410 · SubMP7A1 L1654 · SubUMP45 L1901 · SubP90 L2145
               · SubMP9 L2392 · SubMAC11 L2639
Assault   (9)  AssaultSCARHCQC L2883 · AssaultM8 L3127 · AssaultAUGA3 L3371 · AssaultG3KA4 L3615
               · Assault552Commando L3859 · AssaultG36C L4103 · AssaultMTAR21 L4347
               · AssaultFamas L4594 · AssaultAK47 L4838
LMGs      (5)  LMGMK46 L5082 · LMG21E L5293 · LMGM249SPW L5507 · LMGMG36 L5721
               · FixedLMGM249 L5933   (turret-mounted; also present in the weapon list)
Shotguns  (4)  ShotgunM3 L6144 · ShotgunSpas12 L6372 · Shotgun870MCS L6600 · ShotgunXM26LSS L6828
Snipers   (4)  SniperPSG1 L7054 · SniperM40A1 L7267 · SniperSV98 L7492 · SniperScoutTactical L7719
Other     (1)  ConfigR6Shield L7944
               [Internal] L8101
```
All names are prefixed `R6Game.Config` (e.g. `[R6Game.ConfigR6PistolMK23]`).

**Schema shape:** 146 keys appear in all 35 sections; the rest are per-class extras. A GUI can use one 146-key form plus five conditional blocks:
- `m_f*WithShield*` / `m_*IronSightsShield*` (6 keys) — **pistols only**, because only pistols pair with the ballistic shield.
- `m_fIKRecoilBolt*` (28 keys) — **pump shotguns + bolt snipers only** (M3, Spas12, 870MCS, M40A1, SV98, ScoutTactical).
- `m_fChamberReload*` / `m_f*ChamberReload*Time` (6 keys) — **tube-fed shotguns only** (M3, Spas12, 870MCS): shell-at-a-time reload.
- `m_fAIReloadTacticTime` / `m_fAIReloadEmptyTime` (2 keys) — **LMGs only**.
- `m_fFPShootIKBlend*` (2 keys) — **SniperSV98 only** (an authoring oversight, GUESS).

**Full key inventory for `[R6Game.ConfigR6PistolMK23]` (lines 1-239), grouped:**

*Damage by range* (L2-8) — four hard range stops, linearly interpolated GUESS
```
m_iDamageAt0M=35   m_iDamageAt5M=30   m_iDamageAt20M=25   m_iDamageAt50M=15
m_fOptimalRangeLowerBound=300   m_fOptimalRangeUpperBound=1000     (UU; ~3 m / ~10 m)
```
*Suppressor* (L6, L110, L119, L138, L223)
```
m_fSuppressorDamageModifier=0.8      damage × 0.8 when suppressed
m_fRecoilSuppressorModifier=0.5      recoil halved
m_fSuppressedFireSoundRadius=200     vs m_fFireSoundRadius=5000 — a 25× AI-alert reduction
m_fRecoilAnimationSuppressed=0.5
m_bSupportsSoundSuppressor=true      whether the attachment is offered at all
```
*Burst behaviour — AI fire discipline* (L9-16)
```
m_iShortBurstMinNbBullets=2    m_iShortBurstMaxNbBullets=3
m_iMediumBurstMinNbBullets=4   m_iMediumBurstMaxNbBullets=4
m_iLongBurstMinNbBullets=5     m_iLongBurstMaxNbBullets=8
m_fMinBurstPauseLength=0.1     m_fMaxBurstPauseLength=0.5
```
*Accuracy* (L17-18, L43)
```
m_fAccuracyMultiplier=1.5   m_fBaseAccuracy=42   m_fLaserAccuracyModifier=1.3
```
*Bullet spread — base cone* (L19-26)
```
m_iInitialBulletSpread=220        m_fBulletSpreadPerBullet=50     m_iMaxBulletSpread=8000
m_fBulletSpreadRecoveryTime=0.35
m_fBulletSpreadPatternMinAngle=0  m_fBulletSpreadPatternMidAngle=0
m_fBulletSpreadPatternMaxAngle=0  m_fBulletSpreadPatternZoneBProbability=0
```
*Spread from movement* (L27-31) and *from turning* (L32-36)
```
m_iMovementBulletSpreadMinSpread=220   m_iMovementBulletSpreadMaxSpread=1200
m_fMovementBulletSpreadMinMoveSpeed=150  m_fMovementBulletSpreadMaxMoveSpeed=400
m_fMovementBulletSpreadInterpSpeed=6
m_iRotationBulletSpreadMinSpread=220   m_iRotationBulletSpreadMaxSpread=1200
m_iRotationBulletSpreadMinRotSpeed=1000  m_iRotationBulletSpreadMaxRotSpeed=32000
m_fRotationBulletSpreadInterpSpeed=6
```
*Stance modifiers* (L41-42): `m_fWalkingModifier=0.05`, `m_fCrouchModifier=1`
*Blind fire* (L38-40): `m_iBlindFireMinBulletSpreadAngle=3000`, `m_fBlindFireBulletSpreadModifier=1.2`, `m_fBlindFireAutoAimModifier=0`; plus `m_fRecoilBlindFireMod=1.5` (L112)
*Auto-aim* (L37): `m_bAllowAutoAim=true`
*Rate of fire & mags* (L44-47): `m_iFireRateSingle=60`, `m_iRealFireRate=200`, `m_iNormalMagSize=12`, `m_iHighCapacityMagSize=15`
*Ammo — per difficulty* (L48-56)
```
m_iDefaultAmmunitionNormal=200  m_iDefaultAmmunitionVeteran=200  m_iDefaultAmmunitionElite=200
m_iMaxAmmunitionNormal=200      m_iMaxAmmunitionVeteran=160      m_iMaxAmmunitionElite=120
m_iDefaultAmmunitionMP=200      m_iMaxAmmunitionMP=200
m_bUnlimitedAmmo=true
```
*Fire mode* (L57, L236-239): `m_u8DefaultFireMode=3`; then a 4-entry **repeated-key array** `m_fireModeAvailability=false / false / false / true`
*Recoil* (L101-119)
```
m_fRecoilYawMin=30      m_fRecoilYawMax=100     m_fRecoilYawRecoveryTime=0.1
m_fRecoilPitchMin=250   m_fRecoilPitchMax=400   m_fRecoilPitchRecoveryTime=0.1
m_bRecoilModifyPitch=1  m_fRecoilModifyPitchAccel=4000  m_fRecoilModifyPitchMaxSpeed=4000
m_fRecoilControlStockModifier=0.85   m_fRecoilBlindFireMod=1.5
m_fRecoilIronSightsModifier=0.8   m_fRecoilReflexSightsModifier=0.8
m_fRecoilACOGScopeModifier=0.8    m_fRecoilRifleScopeModifier=0.1
m_fRecoilSniperScopeModifier=0.1  m_fRecoilAnimation=0.5
m_fRecoilControllerRumble=1 (L70)
```
*Attachments* (L218-223): `m_eAttachmentBuiltIn=EAttachment_None`, `m_eAttachmentOption1=EAttachment_Laser`, `m_eAttachmentOption2=EAttachment_HighCapacityMag`, `Option3`/`Option4=EAttachment_None` — **this is the per-weapon attachment whitelist; adding options here is the "unlock attachments" lever**
*Menu stat bars* (L60-62): `m_iDamageMenuStat=5`, `m_iRecoilMenuStat=3`, `m_iAccuracyMenuStat=6` — cosmetic 0-10 bars in the loadout UI, independent of the real numbers
*Handling / weight* (L59, L73-74): `m_fWeaponLength=65.0f`, `m_fWeight=30`, `m_strWeaponIconName=ic_weapon_pistol_MK23`
*Look limits* (L75-86): `m_iMinYawLook=-332` … `m_vScopeLookPivotOffset=(X=0.0f,Y=50.0f,Z=0.0f)`
*Sound radii — AI alerting* (L136-141): `m_fFireSoundRadius=5000`, `m_fSuppressedFireSoundRadius=200`, `m_fNoAmmoSoundRadius=200`, `m_fEquipSoundRadius=200`, `m_fReloadSoundRadius=400`, `m_fFireModeChangeSoundRadius=50`
*Reload timings* (L142-155), *motion blur* (L63-68), *critical ammo warning* (L69), *IK / animation blend* (L120-217, ~100 keys) — cosmetic/anim, low mod value
*Mesh offsets per sight* (L224-235) — first-person model placement for each scope type

**Interesting per-weapon values (verified across all 35 sections):**
- `m_bUnlimitedAmmo=true` on **exactly** the 6 pistols + the Shield; `false` on all 28 other weapons. That is the secondary-weapon rule encoded in config.
- `m_iMaxAmmunitionElite` is a clean class ladder: pistols 120, SMGs 300, assault 270, LMGs 700, shotguns 80, snipers 50, Shield 200.
- Damage spread at 0 m: lowest `ConfigR6Shield`=0, `ShotgunXM26LSS`=26 (per pellet), `PistolGlock18`=25; highest `SniperM40A1`/`SniperSV98`/`SniperScoutTactical`=107, `PistolRagingBull`=90, `PistolDesertEagle`=80.

### AI behaviour — `PC\KellerAIActionTypeConfig.ini` (1262 lines)

**35 action sections**, all with an identical 34-key schema, so this renders as a 35 × 34 grid with no special-casing:
`AimShootFromCover` L1 · `BlindShootFromCover` L37 · `StandAndShoot` L73 · `HideInCover` L109 · `MoveFromCoverToCoverLOS` L145 · `TauntEnemy` L181 · `RunToCoverShoot` L217 · `RunToCoverNoShoot` L253 · `ChargeEnemy` L289 · `MakeCover` L325 · `TurnOffLight` L361 · `ShootOutLight` L397 · `TurnOnLight` L433 · `ThrowFrag` L469 · `ThrowFlash` L505 · `ThrowEMP` L541 · `ThrowGas` L577 · `ThrowSmoke` L613 · `ThrowMolotov` L649 · `ThrowIncendiary` L685 · `RollIntoCover` L721 · `SlideIntoCover` L757 · `BlockPathWithObject` L793 · `KickBarrelAtEnemy` L829 · `UsePursuitDeterrent` L865 · `UseKeyObjectAsCover` L901 · `PushHostageIntoOpen` L937 · `Retreat` L973 · `Surrender` L1009 · `ShootCamera` L1045 · `FastRopeShoot` L1081 · `FastRopeNoShoot` L1117 · `UseFixedWeapon` L1153 · `MoveToShoot` L1189 · `PeekFromCover` L1225.
(All prefixed `R6Game.R6ActionType`.)

**The scoring model.** Each action is a utility row. Two postures — `m_iScoreOffensive*` (16 keys) and `m_iScoreDefensive*` (16 keys) — over the same 16 world-state predicates:
`SelfLowHealth`, `SelfRecentDamage`, `SelfIsAlone`, `SelfInCover`, `SelfHasDrop`, `WeaponLowAmmo`, `WeaponLocalAvailable`, `TargetIsVisible`, `TargetIsAimingAtMe`, `TargetIsInEffectiveWeaponRange`, `TargetLowHealth`, `TargetInCover`, `TargetRecentlyGaveDamageTo`, `TargetRecentlyRecievedDamageFrom` *(sic, misspelled in the shipped file — an editor must match it exactly)*, `Mobile`, `NonMobile`.
Every observed weight is `-1`, `0` or `+1`. The AI sums the weights of the satisfied predicates and picks the highest-scoring action. Sanity check that the reading is right: `[R6Game.R6ActionTypeSurrender]` has an all-zero offensive row and a defensive row of `SelfLowHealth=1`, `SelfIsAlone=1`, `SelfInCover=-1`, `SelfHasDrop=-1`, `WeaponLocalAvailable=-1` (L1028-1034) — surrender only when hurt, alone, exposed, outgunned, with no weapon in reach. That is exactly the retail behaviour.
Plus two scalars: `m_iRepeatLimit` (0 = may repeat forever — all shoot/cover actions; 1 = one-shot — Charge, MakeCover, Retreat, Surrender, lights, most throws; 2 = Taunt, ThrowFrag, Roll/SlideIntoCover) and `m_iGroupOffset` (flat 0-4 bias; `MoveFromCoverToCoverLOS=4` is highest, `MakeCover=3`, then 2 for StandAndShoot/RunToCoverShoot/ChargeEnemy/ShootOutLight/UseKeyObjectAsCover/Retreat/ShootCamera).

Preset ideas this directly supports: "aggressive AI" = raise `m_iGroupOffset` on `ChargeEnemy` and `MoveFromCoverToCoverLOS`; "grenade spam" = raise the `ThrowFrag`/`ThrowFlash` rows and their `m_iRepeatLimit`; "no surrender" = zero the `Surrender` defensive row.

### Gadgets — `PC\KellerGadgetsConfig.ini` (140 lines, 14 sections)

Per-throwable schema: `m_iMaxAmmoNormal` / `m_iMaxAmmoVeteran` / `m_iMaxAmmoElite` / `m_iMaxAmmoMP`, plus `m_bCanUseInTakeCover`, `m_bOnlyOneAllowed`, `m_bSelectable`, `m_strGadgetIcon`.
Stock throwable ladder is uniform: **Normal 6 → Veteran 3 → Elite 2**. MP is 3, except Frag and Incendiary which are 2.
Exceptions worth surfacing in a GUI:
- `[R6Game.R6GadgetSnakeCam]` (L81) — no ammo keys at all; `m_bOnlyOneAllowed=true`. Persistent tool.
- `[R6Game.R6GadgetMotionSensor]` (L87) — `3/3/3`, the only throwable that does **not** scale with difficulty.
- `[R6Game.R6GadgetHeatSignature]` (L97) and `[R6Game.R6GadgetRadarJam]` (L109) — MP tac-aids, `10` on all four tiers, with two unique keys: `m_fEffectDuration=10` and `m_fRadius=2500`.
- `[R6Game.R6GadgetGasMask]` (L121), `[R6Game.R6GasMaskSF10]` (L127), `[R6Game.R6MedKit]` (L133) — all three `m_bSelectable=false`. **Flipping `m_bSelectable=true` on `[R6Game.R6MedKit]` is the most interesting single-bit unlock in the config tree**: it would put a normally auto-only medkit in the gadget wheel. Effect unverified (needs a run).

### Projectiles — `PC\KellerProjectilesConfig.ini` (51 lines, 7 classes)

`FlashbangGrenade` L1 · `FragGrenade` L8 · `IncendiaryGrenade` L15 · `MolotovGrenade` L22 · `SmokeGrenade` L29 · `TearGasGrenade` L36 · `R6DeterrentExplosive` L43. Five keys each: `Speed`, `m_fPlayerDelayExplosion`, `m_fTerroDelayExplosion`, `m_fDampFactor`, `m_fDampFactorParallel`.

**The single best find in this file:** the fuse is *asymmetric by faction*. Terrorist-thrown grenades always cook exactly 1.0 s longer than player-thrown ones — frag is player `2.5` vs terro `3.5`; flash/smoke/gas are `1.5` vs `2.5`. That is a hidden, config-exposed difficulty handicap in the player's favour, and equalising it is a one-line "realistic" preset. Molotov is `0/0` (detonates on impact). `Speed=1300` for all grenades, `2000` for the deterrent explosive. `m_fDampFactor` = bounce energy loss, `m_fDampFactorParallel` = roll friction — raise both to stop grenades rolling back at you.

### Damage types — `PC\KellerDamageTypesConfig.ini` (386 lines, 36 sections)

**Contains no damage numbers** (those are in the weapons file). It holds ragdoll impulse + camera shake. The only key that varies is `KDamageImpulse`: SMGs `600`, pistols `800`, assault `900`, LMGs `1000`, snipers `1500`, **shotguns `175`** (lowest by 3.4×, because it's applied per pellet). The 8 camera-shake keys are identical in all 35 weapon sections (`Duration=0.3`, `Strength=1`, `Roll/Pitch/YawFreq=15`, `Roll/Pitch/YawAmp=100`). `[Engine.R6DamageTypeExplosive]` (L375) is the only distinct profile: `Duration=0.8`, `Strength=1.5`, `RollFreq=500`, `PitchFreq=700`, `YawFreq=500`, `RollAmp=150`, `PitchAmp=800`, `YawAmp=400`.

### Explosives — `PC\KellerExplosivesConfig.ini` (11 lines)

Three sections, three live keys. `[R6Game.R6ExplosiveDemolition]` (L1) is an **empty section header** — C4 exposes nothing. `[R6Game.R6ExplosiveBreaching]`: `m_fImpulseOnDoor=1500`. `[R6Game.R6MotionSensor]`: `m_fLaserTimer=3.0f`, `m_fLaserMaxLength=10000.f` (note the `10000.f` form — no leading zero on the fraction; another round-trip trap).

### Civilians — `DefaultCivil.ini` (no generated layer; edit directly)

Single section `[R6Game.R6CivilManager]`. Emotion index convention documented in-file at L2-4: `0 = Curiosity, 1 = Heroic, 2 = Panicked`. Event profiles: `m_LightEventProfile` = `0.2/0/0`, `m_MediumEventProfile` = `0.2/0.2/0.2`, `m_HeavyEventProfile` = `0/0.4/0.6`. **Contagion** is the interesting part: `m_OtherCivilPanickedEventProfile[2]=0.4` (panic spreads), `m_OtherCivilCuriousEventProfile[0]=0.2`, `m_OtherCivilHeroicEventProfile[1]=0.4` (raise this for civilians that gang up). Four archetype structs `m_Coward_Profile`, `m_Curious_Profile`, `m_Heroic_Profile`, `m_Custom_Profile`, each `[0..2]`, with fields `m_fDecayValue`, `m_fEmotionThreshold`, `m_EmotionsImpact[0..2]`, `m_fCurrentEmotionTimer` etc. `m_Custom_Profile[0]` is a **neutered free slot** (threshold `1.0`, decay `1.0`, all impacts zero) — a mod could claim it.

### Characters — `PC\KellerCharacter.ini` (53 lines)

Cosmetic only: idle-animation name pools. Sections `[R6Game.R6Character]`, `[R6Game.R6RainbowPawnMichael]`, `[R6Game.R6RainbowPawnJung]`, `[R6Game.R6CivilPawn]`. All keys are repeated-key string arrays (`m_sIdlesAnims=` ×7, `m_sIdlesTcAnims=` ×5, etc.). No stats. The only place the two named AI teammates are addressed by class name.

### Multiplayer rules — `PC\KellerGame.ini`

- `[R6Game.R6MultiPlayerGame]` L69-86: `MaxLives=1`, `m_bAllowRespawn=false`, `m_bAllowJoinInProgress=true`, `m_iKitRestrictionIDs[0..4]=-1` (weapon/gadget ban slots), then a complete tunable **spawn-safety scoring system**: `m_iBestRating=100`, `m_iWorstRating=0`, `m_iRatingForInvalidPoints=-1`, `m_iPenaltyForLastStartingPosition=20`, `m_iPenaltyPerMeter=5`, `m_bDoVisibilityCheck=TRUE`, `m_iVisibilityPenalty=20`. Good target for an anti-spawn-camp mod.
- `[R6Game.R6DeathmatchGame]` L87: `m_iTimeLimitSeconds=180`, `m_iGoalKills=0` (no frag limit), `m_iRounds=3`, `m_iTimeMatchStarting=5`.
- `[R6Game.R6TeamDeathmatchGame]` L96: `m_bBalanceTeams=true`, `m_bLockTeams=false`, `m_bFriendlyFire=false`, `m_bAllowTeamKillerPenalty=true`, `m_byTeamKillerPenaltyMax=5`.
- `[R6Game.R6AttackDefendGame]` L106: `m_iTimeLimitSeconds=900`, `m_bAllowRespawn=true`, `MaxLives=0`.
- `[R6Game.R6RetrievalGame]` L111: `m_fCanisterTimeOut=30.0`.
- `[R6Game.R6ObjectiveExtractionItem]`: `m_fItemTimeOut=30.0`. `[R6Game.R6ObjectiveHostageRescue]`: `m_fHostageTimeOut=30.0`.
- **`[R6Game.R6SinglePlayerGame]` does not exist as a section anywhere.** `R6Game.R6SinglePlayerGame` appears only as a class *reference* (`DefaultGame=` at `PC\KellerGame.ini:2`). Campaign rules are not ini-exposed — they live in the per-map `.ini` files under `KellerGame\Content\CookedPc\Maps\<map>\`. Dead end for a config GUI.

### Dedicated-server whitelists — `PC\R6VegasServerConfig.ini`

This is the **best documentation in the game** — a heavily commented reference file. A GUI should mine it for dropdown contents rather than hard-coding:
- All 10 game modes (L31-40): `GAMEMODE_ATTACKANDDEFEND`, `_DEATHMATCH`, `_SHARPSHOOTER`, `_TEAMDEATHMATCH`, `_TEAMSHARPSHOOTER`, `_RETRIEVAL`, `_STORY`, `_TERROHUNT`, `_CONQUEST`, `_ASSASSINATION`.
- Legal value sets to enforce: `m_iRoundDuration` ∈ {180,300,600,900,1200} (L47); `m_iBriefingTimer` ∈ {5,10,20,30,40,50,60} (L51); `m_iTimeBetweenRound` ∈ {0,15,30,45,60} (L55); `m_iRoundCount` ∈ {1,3,5,10,15,20} (L59); `m_iMaxLives` ∈ {0,1,3,5,10} (L82); `m_iAutoKickTeamKillers` ∈ {0,1,3,5,10} (L98); `m_iGamePointLimit` ∈ {0,10,20,30,40,50} (L102); `m_iConquestGamePointLimit` ∈ {1000,2000,3000,5000,8000} (L106); `m_iMaxPlayers` 0-16 (L43).
- **How to discover item IDs** (L110-116): run a server, set restricted items in-game, quit, read the IDs back from `KellerGame\Config\PC\KellerServerOptions.ini`. **How to discover map IDs** (L124-133): open the map's `.ini` under `KellerGame\Content\CookedPc\Maps\<map>\`, check its `m_eGameMode=` for mode compatibility, read `m_iId=`. A mod manager can automate both and build the map picker itself.

### Dev console and cheat bindings — **shipped in retail, but gated**

`PC\KellerConsole.ini` live values: `TypeKey=RightBracket` (L2), `bEnableUI=False` (L22), plus an `[Engine.Console]` block **after** the `[Internal]` CRC block with `ConsoleKey=Tilde` (L28), `AlternativeConsoleKey=Quote` (L29), `MaxScrollbackSize=1024` (L31). The template `DefaultConsole.ini` is 3 lines and says `TypeKey=F12`.
The same three bindings are mirrored at `PC\KellerInput.ini:152-155`. The console class is wired at `PC\KellerEngine.ini:18` — `ConsoleClassName=R6Game.R6Console`.

`[R6Game.R6CheatInput]` is a 67-binding debug keymap at `PC\KellerInput.ini:162-229`. **It is stock, not a user modification** — I verified the same bindings ship in the template at `DefaultInput.ini:87+` in `!Bindings=` form (e.g. `DefaultInput.ini:113 !Bindings=(Name="F10",Command="ToggleGhost")`), which the generated file materialises as plain `Bindings=`. Highlights: `F10` ToggleGhost (noclip), `Ctrl+F10` Stealth (AI ignores you), `Ctrl+F5` FreeCam, `_`/`=` CheatCycleWeaponUp/Down, `Ctrl+_`/`Ctrl+=` CheatCycleCharacterUp/Down, `8`/`9` CheatCycleGadgetUp/Down, `7` CheatCycleAttachment, `,`/`.`/`/` Slomo / Slomo 1 / Slomo 3, `T` EnableRainbow, `Space` ToggleCyclePawns, `+`/`-` Increase/DecreaseEditableProp (live property editing), `Ctrl+F9`/`Alt+F9` SUBMITBUG/SUBMITBUGQC (Ubisoft-internal bug reporting still bound), NumPad block for an in-game first-person weapon-position editor.
The exe confirms the classes exist: `UR6CheatManager`, `UR6CheatInput`, `UR6KellerCheats`, `UR6CameraNodeCheat`, and script thunks `intUR6CheatManagerexecAddExperience`, `…execReloadConfigFiles`, `…execToggle3DHud`, `…execToggleTutorial`, `…execFreeCamSet`, `…execSetRumble`, `intUR6AbstractGameManagerexecEnableCheat`, `intAPlayerControllerexecAddCheats` (`exe_strings.txt` lines 153186-154373, 197787-199381).
**`intUR6CheatManagerexecReloadConfigFiles` is directly useful to a mod tool** — if reachable, it is a live config hot-reload, so a GUI could apply weapon tweaks without a restart.
**Caveat, and it is a real one:** `[R6Game.R6CheatInput]` is a *separate* config class from `[Engine.PlayerInput]` (verified: `PC\KellerInput.ini` section list is `[Engine.PlayerInput]` L1, `[Editor.EditorViewportInput]` L79, `[Engine.Console]` L152, `[Configuration]` L159, `[R6Game.R6CheatInput]` L162, `[Internal]` L231). In UE3 the active `PlayerInput` subclass is chosen by the PlayerController's script default, not by ini. So GUESS: these bindings are inert in a retail build unless cheats are enabled by some other means. I searched the exe strings for a gate (`bCheatsEnabled`, `AllowCheats`, `-devmode`, etc.) and found nothing conclusive. **Unverified — do not promise this works.**

### Miscellaneous flags found in the shipped config

| file:line | value | note |
|---|---|---|
| `PC\KellerGame.ini:35` | `bShowHud=false` | This is the *legacy UT* `[Engine.HUD]`, not the game HUD — R6 Vegas draws its own Magma/Scaleform UI (`MenuInteraction=R6Game.R6MagmaInteractionMain`). Expose with a warning. |
| `PC\KellerGame.ini:141-143` | `[Engine.R6FPPWalkthroughConfig]` `m_FPPMap=05_Dantes_FPP_03`, `m_iQuitWaitTime=5`, `m_bShowExitScreen=false` | Internal first-person-playthrough demo harness, still shipped |
| `PC\KellerEngine.ini:212-213` | `[DemoSP]` `DemoSPModeEnabled=0`, `Map=99_HeliRides_DemoSPNear` | Kiosk/attract-loop mode, shipped off. Set 1 to try it. |
| `PC\KellerEngine.ini:57` | `ShowNotes=true` | Developer annotation display left enabled |
| `PC\KellerEngine.ini:227` | `URL=http://keller-dashboard/index.php` | Ubisoft-internal dev dashboard URL left in retail |
| `PC\KellerEngine.ini:218` | `SoundScriptDir=x:\perforce\keller\SourceData\Sounds\` | Build-machine Perforce path left in retail |
| `PC\KellerEngine.ini:233` | `m_fstrConfigFile=..\KellerGame\Config\PC\AgoraConfig.lua` | Matchmaking backend config is a **Lua script** (1403 bytes) — a scriptable surface, not ini |
| `PCKellerEngine.ini:180` | `GodMode=True` | Inside `[Editor.EditorEngine]` — editor play-in-editor god mode, **not** the game. Do not surface as a cheat. |

---

## Difficulty

### The enum: three playable tiers, and the UI lies about their names

Nothing in any `.ini` enumerates the enum. It lives in the name table of
`KellerGame\Content\CookedPc\Engine.uppc` (`Enum EGameDifficulty`). Complete set:
```
GAMEDIFFICULTY_NONE
GAMEDIFFICULTY_NORMAL
GAMEDIFFICULTY_VETERAN
GAMEDIFFICULTY_ELITE
GAMEDIFFICULTY_MAX     (sentinel)
```
**There is no `RECRUIT` and no `REALISTIC` enum value.** "REALISTIC" is only a display label. From `KellerGame\Localization\INT\R6Menus.int`:
- L534-535 `[ServerOptions]`: `DifficultyVeteran=NORMAL`, `DifficultyElite=REALISTIC` — direct proof that the two options the player sees as "Normal" and "Realistic" are internally **VETERAN** and **ELITE**.
- L107-108 `[MainMenu]`: `Difficulty1=NORMAL`, `Difficulty2=REALISTIC` — only two.
- L150-152 `[HuntMenu]`: `DiffEasy=EASY`, `DiffNormal=NORMAL`, `DiffHard=REALISTIC` — **three**. `DiffEasy` is an orphan label.
- `KellerGame\Config\PC\R6VegasServerConfig.ini:65-69` comments the legal coop values as only `GAMEDIFFICULTY_VETERAN` and `GAMEDIFFICULTY_ELITE`; `_NORMAL` is deliberately not listed.

So `GAMEDIFFICULTY_NORMAL` is a fully implemented but unexposed easiest tier — it has a label (`DiffEasy`), an enum value, and its own data in every config object. **Exposing it is a legitimate mod-manager feature**: set `GameDifficulty=GAMEDIFFICULTY_NORMAL` in `PC\KellerGame.ini:6` and `m_eDifficulty=GAMEDIFFICULTY_NORMAL` in `PC\KellerServerOptions.ini:29`. (Not runtime-verified — I did not launch the game.)
Corroboration: `Engine.uppc` export 14404 `TerroHuntMissionDifficultyInfo` is `{ int m_iMissionOrderId; struct m_VeteranInfo; struct m_EliteInfo }` — **only two tiers of per-mission Terrorist Hunt data**, so NORMAL was never wired up for T-Hunt specifically.

### Where difficulty actually lives: a THIRD config system nobody mentioned

**In ini, difficulty scales exactly one thing: ammunition.** A full scan of every key under `KellerGame\Config` and `Engine\Config` matching Normal/Veteran/Elite/Realistic/Recruit yields only three key families:
`m_iDefaultAmmunition{Normal,Veteran,Elite}` and `m_iMaxAmmunition{Normal,Veteran,Elite}` (per weapon, weapons ini) and `m_iMaxAmmo{Normal,Veteran,Elite}` (per gadget, gadgets ini).
e.g. `PC\KellerWeaponsConfig.ini:52-54` MK23 max ammo **200 / 160 / 120**; gadgets uniformly **6 / 3 / 2**.
Anyone who tells you to edit an ini to change AI reaction time, health, or damage on this game is wrong.

Everything else lives in **`KellerGame\Content\CookedPc\Packages\GameConfig\`** — a second, cooked config system of 22 UE3 packages:
```
AIConfig.uppc          AccuracyConfig.uppc    ConfigsManager.uppc    ControlsConfig.uppc
DamageConfig.uppc      FPPWalkthroughConfig.uppc  GadgetsConfig.uppc HandSignalsConfig.uppc
HealthConfig.uppc      ImpactConfig.uppc      InteractLengthsConfig.uppc
InteractLocationsConfig.uppc  MiscConfig.uppc PostEffectsConfig.uppc
RS5CharacterAITemplate.uppc   RadarConfig.uppc RappelConfig.uppc
SoundPriorityConfig.uppc      TakeCoverConfig.uppc VisualConfig.uppc WeaponsConfig.uppc
```
`ConfigsManager.uppc` is the root — it holds `m_DifficultyConfig`, `m_HealthConfig`, `m_DamageConfig`, `m_AccuracyConfig`, `m_AIConfig`, `m_RainbowConfig`, `m_WeaponsConfig`, `m_GadgetsConfig`, `m_TakeCoverConfig`, `m_CameraConfig`, `m_MiscConfig`, `m_RadarConfig`, `m_VisualConfig`, `m_ImpactConfig`, `m_ControlsConfig`, `m_HandSignalsConfig`, `m_RapellingConfig`, `m_InteractLengthsConfig`, `m_InteractLocationsConfig`, `m_SoundPriorityConfig`, `m_FPPConfig`, `m_PostProcessConfigCollection`, `m_MassiveConfig`, `m_PlayerOptionsManager`.

**None of these classes has an ini section.** Grepped `KellerGame\Config` + `Engine\Config` for `DifficultyConfig` / `HealthConfig` / `DamageConfig` / `AccuracyConfig`: zero hits. They are serialized object data inside `.uppc`.

### Format cracked — you can read and write these

The packages parse. Header layout for this Ubisoft UE3 build (`FileVersion 241 / LicenseeVersion 66`), verified against `HealthConfig.uppc`:
```
0x00  u32   tag = 0x9E2A83C1
0x04  u16   FileVersion = 241
0x06  u16   LicenseeVersion = 66
0x08  FString FolderName (empty here, so 4 zero bytes)
      u32   PackageFlags
      u32   <extra Ubisoft dword>     <-- NOT in stock UE3; skip it or the header mis-parses
      u32   NameCount, NameOffset, ExportCount, ExportOffset, ImportCount, ImportOffset
      FGuid (16 bytes), GenerationCount, then per-generation {ExportCount, NameCount}
Name entry  = int32 length, ASCII incl. NUL, then 8 bytes of flags
Export entry = 40 bytes; SerialSize / SerialOffset sit at dword indices 6 and 7
Tagged property = int32 NameIndex, int32 TypeNameIndex, int32 Size, int32 ArrayIndex, value
                  (FName here is a bare int32 — no Number field, unlike stock UE3)
Struct value  = int32 struct-type NameIndex, then nested properties
Array value   = int32 count, then per-element properties
Property list terminates on NameIndex resolving to "None"
```
Working parser: `…\scratchpad\uppc3.py`. Run as `python uppc3.py <file.uppc>`.
That extra dword at offset 0x10 is the trap — stock UE3 parsers read `NameCount=9 / NameOffset=64` and walk off the end of the file.

### Stock values, read out of the shipped packages this session

These are the **instance** objects that `ConfigsManager` loads. Only properties that differ from the class default get serialized, so absent properties fall back to the CDO in `Engine.uppc`.

`KellerGame\Content\CookedPc\Packages\GameConfig\HealthConfig.uppc`
```
m_iMaxHealthPlayerNormal   = 105      m_iMaxHealthRainbowNormal  = 130
m_iMaxHealthPlayerVeteran  = 105      m_iMaxHealthRainbowVeteran = 130
m_iMaxHealthPlayerElite    =  50      m_iMaxHealthRainbowElite   =  70
m_iMaxHealthPlayerMP       = 130
m_iIncapacitatedHealth     =  80      m_iMaxHealthHostage   =  50
m_iMaxHealthNPC            =  50      m_iMaxHealthHostageMP = 200
m_iMaxHealthCivil          =  50      m_aTerroMaxHealth[1].m_iHealth = 90
```
**Normal and Veteran are identical (105).** The difficulty step is entirely at Elite, which more than halves player health (105 → 50) and drops teammates 130 → 70. Your AI teammates are tougher than you on every tier.

`…\GameConfig\AccuracyConfig.uppc`
```
m_fPlayerAccuracyModifierNormal = 1        m_fPlayerAccuracyModifierElite = 0.5
m_iInnerMagnetRange = 5    m_iOuterMagnetRange = 20    m_fMaxAutoAimDistance = 5000
m_fAccuracyInterpSpeed = 2 m_fBlindFireBulletSpreadInterpSpeed = 8
m_pawnAutoAimBones (7 entries) — first is m_szBoneName='R65_BA_Head', m_fWeight=0.8
  (the other bones named in the name table: R65_BA_Spine2, R65_BA_R_Forearm,
   R65_BA_L_Forearm, R65_BA_Pelvis, R65_BA_L_Calf, R65_BA_R_Calf)
m_ZoomModifiers (9 entries) — per zoom type: m_fBulletSpreadModifier,
  m_fAutoAimRadiusModifier, m_bShowReticle, m_bShowReticleInTakeCover
```
There is **no Veteran key** — GUESS: Veteran is the unmodified 1.0 baseline. Elite halves player accuracy.

`…\GameConfig\DamageConfig.uppc`
```
m_fOverallDamageModifierToTerroNormal = 1
m_fOverallDamageModifierToTerroElite  = 1        <-- both 1.0 in the shipped instance
m_fExplosiveDamageOnObjectModifier    = 4
m_damageMultipliersTerro[0].m_fMultiplier = 2
```
Also declared in this class (not overridden in the instance, so they sit at CDO values): `m_damageMultipliersRainbow`, `m_damageMultipliersAdversarialPlayer`, `m_fTCExposedPlayerModifier`, `m_fTCNotExposedPlayerModifier`, `m_fTCExposedRainbowModifier`, `m_fTCNotExposedRainbowModifier`, `m_fRappellingDamageModifier`, `m_iDamageByFire`.

**Conflict, stated honestly.** A parallel pass over the *class defaults* (`Default__R6HealthConfig`, `Default__R6DamageConfig`, `Default__R6AccuracyConfig`, `Default__R6DifficultyConfig`) inside `Engine.uppc` reported a different, tidier table: player/teammate health `200 / 160 / 120`, damage-to-terro `1.5 / 1.0 / 0.75`, player accuracy `1.5 / 1.0 / 0.75`, wounded/critical recovery `4 / 6 / 8 s`, and `R6DifficultyConfig` AI timers `m_fSustainedVisionTimer` / `m_fLockTimer` / `m_fDefensiveTimerInputs` / `m_fDefensiveTimerCap` all `2.0 / 1.0 / 0.5`.
Those are the **CDO** values. The numbers I read above are the **instance** values from `Packages\GameConfig\`, and the instance overrides the CDO for every property it serializes. Since `ConfigsManager` holds object references to these instances, **I believe the instance values are what the game runs** — most visibly, the shipped instance flattens damage-to-terro to 1.0 on both tiers, where the CDO would have given Elite a 0.75 penalty. I did not run the game, so treat the "which wins" call as reasoned, not observed. The `R6DifficultyConfig` AI-timer table (2.0 / 1.0 / 0.5) has no instance override I found, so it stands as-is — and **that flat 2× / 1× / 0.5× on AI acquisition, lock and reaction time is the entire "AI skill" system.** There is no per-terrorist accuracy or aim-error table keyed on difficulty anywhere.

### Summary: what each difficulty actually changes

| | NORMAL (hidden) | VETERAN (shown as "Normal") | ELITE (shown as "Realistic") |
|---|---|---|---|
| Player max health | 105 | 105 | **50** |
| Teammate max health | 130 | 130 | **70** |
| Player accuracy modifier | 1.0 | 1.0 (implied) | **0.5** |
| Damage you do to terrorists | ×1.0 | ×1.0 | ×1.0 (CDO would say 0.75) |
| AI vision / lock / reaction timers | ×2.0 (slower AI) | ×1.0 | **×0.5 (twice as fast)** |
| Weapon max ammo (MK23) | 200 | 160 | 120 |
| Gadget carry count | 6 | 3 | 2 |

`R6DifficultyConfig`'s 15 accessors (`GetPlayerMaxHealth`, `GetRainbowMaxHealth`, `GetDamageToTerroModifier`, `GetPlayerAccuracyModifier`, `GetPlayerRecoveryTimerWounded` / `Critical`, `GetRainbowRecoveryTimer*`, `GetWeaponDefaultAmmo`, `GetWeaponMaxAmmo`, `GetGadgetMaxAmmo`, `GetCurrentLockTimer`, `GetCurrentSustainedVisionTimer`, `GetCurrentDefensiveTimerInputs` / `Cap`) are all 48-53 byte native stubs with no script bytecode (`exe_strings.txt` lines 199439-199453), so the *selection* logic is native C++ in `R6Vegas_Game.exe`. The *data* is not, which is why the table above can be exact.

### Other high-value values in the cooked layer

`…\GameConfig\AIConfig.uppc` — **this is the real teammate-AI surface**, far richer than the 2-line `DefaultRainbow.ini`:
```
m_fFormationDistanceLeash = 300     m_fTakeCoverSpacing = 104
m_fCatchupStartDistance   = 600     m_fCatchupStopDistance = 300
m_fDistToLeaderBeforeMoving = 100   m_fDistLeaderMovedBeforeChangingPosition = 75
m_fMinDistanceForDeadlock = 500     m_fThreatBoostToTaggedEnemy = 500
m_fTHPriorityThreshold = 0.75       m_fTimeBeforeHuntingHighBound = 3
m_iMinimumStandingPeekBorderAngle = 24576   m_fCosineMinimum… = -0.707107
m_fExposedLineTestDepth = 100       m_fNavigation_ObstacleOnFireAvoidDist = 100
m_fDelayToStartMoveTo = 0.25        m_fMaximumDistanceToConsiderEffect = 2000
m_iDistanceConsideredFar = 1500     m_fPassiveCommunicationDistance = 700
idle-chatter: m_fMinimumTimeBetweenIdleDialogGuardAware/Unaware = 20 / 20,
              …PatrolAware/Unaware = 10 / 10,
              m_iDistanceFromTeamateOkToStartIdleDialog = 600,
              m_fTimeIntervalForReportingNothingFound = 20
look behaviour: m_fActionProbTeamMates_{Calm,Nervous,Guilty,Basic} = 0.2 each,
                m_fActionProbLookRandom_{same four} = 0.8 each
```
Plus **24 per-teammate breach abort timers** — `m_fMikeAbortTime*` and `m_fJungAbortTime*`, one per (Stack|TakeCover) × (Left|Right) × (Left|Mid|Right) combination, values 1.15-2.03 s. Michael and Jung have individually hand-tuned breach timing. `m_VBLogan`, `m_VBMichael`, `m_VBJung`, `m_VBKan`, `m_VBGabriel` are object refs to the five `FPP*VoiceBank` objects.

`…\GameConfig\GadgetsConfig.uppc` — throwing physics, which the ini does not cover:
```
m_fThrowSpeed = 1200         m_fThrowSpeedTc = 1200      m_fThrowSpeedTcBfSide/Up = 1200
m_fThrowMaxSpeed = 1300      m_fThrowMaxSpeedExplosives = 700
m_fC4Speed = 1000            m_fThrowTimeClose = 0.933
m_iPitchModifier = 1820      m_iPitchModifierTc = 1820   m_iPitchForAdjustingVel = 2730
m_fBreachDettachStacked = 4.6   m_fBreachDropWeaponStacked = 3
m_fIKOffsetNear = -10        m_fIKOffsetFar = 0
```

**Implication for the mod manager:** a config GUI limited to `.ini` can reach weapons, AI action scoring, gadget counts, game-mode rules and server options — but it can reach **none** of health, damage multipliers, accuracy, auto-aim, teammate AI, or difficulty scaling. To cover those you need a `.uppc` property patcher. Good news: the values are fixed-size scalars (int32/float32) written in place, so a patcher can rewrite a value **without changing file size or relocating anything** — no re-serialization, no offset fixups, no CRC. That makes it a genuinely tractable second tier for the tool.

---

## Art

**Bottom line: `.mgb` does not need cracking. Every pixel of menu art is already loose on disk** as plain `.tga` / `.dds` / `.png` that Pillow reads directly — 745 images under `Content\MenusPC\Textures\`, 93 more under `KellerGame\Slide\`, 38 under `KellerGame\ImageMap\`, 8 under `KellerGame\Startup\`.

All PNGs below were decoded this session into
`C:\Users\Tristan\AppData\Local\Temp\claude\C--Users-Tristan-Documents-GitHub\b43643a5-e58c-4ad6-b2d1-027eccd6e355\scratchpad\art\`.
I opened the two picks and confirmed them by eye.

### Backdrop — pick

`D:\SteamLibrary\steamapps\common\Rainbow Six Vegas\KellerGame\Slide\Locations\03_Fremont_01.dds`
- **1024 × 1024, DDS / DXT1, 524,416 bytes, 0 mipmaps, no alpha.**
- Decoded: `…\scratchpad\art\slide_03_Fremont_01.png` (raw) and `…\scratchpad\art\BACKDROP_PICK_Fremont_852x480.png` (aspect-corrected).
- **Verified by viewing.** Neon Fremont Street at night already wearing the game's full menu chrome: angled bevel panels with hairline strokes, the RAINBOW SIX VEGAS badge top-left, the white operator silhouette top-right, and — critically — **two large empty dark panels bottom-centre and bottom-left that map straight onto a mod-manager's list pane and detail pane**. This is as close to a free GUI chassis as the game ships.
- Caveat: the native 852×480 art was non-uniformly squeezed into a 1024² DXT1 square. Resample to 852×480 or 1704×960 to restore the intended aspect.
- Dominant colours (8-colour octree): `#080301` 86.5%, `#561B05` 7.0%, `#A05716` 1.9%, `#972B03` 1.5%, `#5D5957` 1.0%, `#D2630A` 0.9%, `#6C4A27` 0.6%, `#E19522` 0.6%.

### Backdrop — runners-up

1. **The actual SP main-menu plate**, chrome-free pure atmosphere (Vegas Strip at night). Ships as two halves that composite to exactly **852 × 480** — the game's native menu canvas:
   `…\Content\MenusPC\Textures\SinglePlayer\BackLeftSP_Temp.dds` (512×512 DXT5, alpha, 6.2% transparent)
   `…\Content\MenusPC\Textures\SinglePlayer\BackRightSP_Temp.dds` (512×512 DXT5, alpha, 37.7% transparent; only the left 340 px carry image)
   → `…\scratchpad\art\composite_SP_menu_backdrop.png`. **Verified by viewing** — deep crimson/amber Strip skyline, heavily bloomed, with faint HUD scanline furniture at the edges. Use this if you want atmosphere without the game's panel chrome. Palette: `#150504` 54.2%, `#5B2119` 22.9%, `#A76150` 6.1%, `#933126` 6.1%, `#9C4A36` 4.5%, `#D8A896` 3.0%.
2. `…\KellerGame\Slide\Locations\04_Tower_02.dds` — 1024×1024 DXT1, no alpha. Same chrome layout, cold teal/blue instead of orange. Palette `#01080A` 77.2%, `#115263` 7.1%, `#02354B` 6.3%, `#5B98A8` 3.6%. → `…\scratchpad\art\BACKDROP_RUNNERUP_Tower_852x480.png`
3. `…\KellerGame\Slide\default_mp_splash_screen.dds` — 1024×1024 DXT1, no alpha, clean textless in-game screenshot. Neutral plate. → `…\scratchpad\art\backdrop_G_default_mp_splash.png`

### Logo / wordmark — pick (keyable)

`D:\SteamLibrary\steamapps\common\Rainbow Six Vegas\KellerGame\Content\MenusPC\Textures\SinglePlayer\RSVegas_Logo.tga`
- **504 × 249, TGA, 32-bit uncompressed (image type 2, 8 alpha bits), 502,028 bytes.**
- **Alpha: yes — a real straight-alpha channel.** 53.8% fully transparent, 22.6% fully opaque, 23.5% partial.
- **Alpha cleanliness: excellent, and I verified it.** I viewed `…\scratchpad\art\logo_A_keyed_on_green.png` — composited over pure green there is **no halo, no matte fringe and no DXT block fringing**, because the source is uncompressed TGA rather than a DXT copy. The 23.5% partial-alpha band is the logo's intentional soft glow/drop shadow, not an artifact. Non-zero-alpha bbox is (2, 0, 493, 230) inside the 504×249 canvas, so the margins are clean.
- Content: "TOM CLANCY'S" + operator glyph, "RAINBOW**SIX**" in white/crimson, "VEGAS" in white on crimson chip-style lozenges, with a red spraypaint crosshair motif behind.
- This TGA is the canonical master — `…\Textures\MosaicFiles\CommonTex.mos.xml` lists it as the source packed into `CommonTex_0.dds` at X=0 Y=0 W=504 H=249, so the DDS copy is strictly a DXT5-degraded version.
- **Use `…\scratchpad\art\logo_A_RSVegas_Logo_trimmed.png` (491 × 230, alpha-trimmed)** in a GUI. Full-canvas version at `…\scratchpad\art\logo_A_RSVegas_Logo.png`. Key proofs on white/green/grey/vegasred alongside.
- Dominant colours ignoring the transparent field: crimson `#981F1F` 8.9%, off-white `#F9F7F7` 8.3%, deep maroon `#681616` 4.0%.

### Logo — runners-up

1. `…\Textures\MosaicFiles\CommonTex_0.dds` — 512×1024 DXT5, alpha. Same wordmark top-left plus a second smaller RSV **title-card** variant lower down with a baked dark-blue background. Keyable but DXT5-blocky. → `…\scratchpad\art\mosaic_CommonTex_0.png`
2. `…\Textures\Community\UbiLogo.dds` — 180×64 DXT5, clean alpha (66.7% transparent). Publisher lockup if you want one. → `…\scratchpad\art\logo_D_UbiLogo.png`
3. The badge baked into the top-left of every `Slide\Locations\*.dds` — correct style but **not keyable** (fused into the backdrop).
4. `…\KellerGame\ImageMap\SP_VOID.dds` — 128×128 DXT1, **no alpha**. Too small and not keyable; listed only so nobody wastes time on it.

### Proposed GUI palette

| role | hex | source |
|---|---|---|
| Window / canvas background | `#0C090B` | 80.6% of `…\LoadingScreens\BackgroundDante.tga` |
| Panel fill (raised surface) | `#150504` | 54.2% of the SP menu composite |
| Primary brand / accent | `#981F1F` | 8.9% of `RSVegas_Logo.tga` |
| Accent pressed / border | `#681616` | 4.0% of `RSVegas_Logo.tga` |
| Secondary surface, warm | `#5B2119` | 22.9% of the SP menu composite |
| Highlight / hover glow | `#A76150` | 6.1% of the SP menu composite |
| Primary text | `#F9F7F7` | 8.3% of `RSVegas_Logo.tga` |
| Cold accent (selection) | `#22285B` | 4.4% of `BackgroundDante.tga` |
| Disabled / hairline chrome | `#5F525E` | 4.2% of `BackgroundDante.tga` |

Swatch rendered at `…\scratchpad\art\palette_swatch.png`.

**Typeface:** the game's UI face is **Eurostile / Eurostile Extended** — `…\Content\MenusPC\Fonts\EurostileBold 26 0.tga` and `Eurostile Extended 22 0.tga`, both 256×256 32-bit alpha atlases with `.mft` metric sidecars. Match headings to Eurostile Extended.

### `.mgb` — what they are, and why you can ignore them

22 `.mgb` files, all under `KellerGame\Content\MenusPC\` (19 at root, 3 in `Widescreen\`), 522 B – 89,849 B. First 64 bytes of `…\Content\MenusPC\common.mgb`:
```
4d 41 47 4d 41 ab 00 00  cd 00 00 00 15 00 00 00   MAGMA...........
00 06 63 6f 6d 6d 6f 6e  03 54 01 e0 00 6a 00 00   ..common.T...j..
00 00 00 a1 00 00 00 08  eb 9c 24 07 00 00 00 25   ..........$....%
5c 74 65 78 74 75 72 65  73 5c 4d 6f 73 61 69 63   \textures\Mosaic
```
- Magic `MAGMA` confirmed. Byte 5 `0xAB` is a format tag; then LE dwords `0x000000CD` (version) and `0x00000015` (section count). **These six values are byte-identical across all 22 files.**
- At 0x10, a **big-endian uint16 length-prefixed string** holds the menu name (`00 06` + `common`; `00 0A` + `SP_RSMenus`; `00 07` + `Loading`). Same pattern every file.
- Then `03 54 01 E0` = **852 × 480** — the canonical menu canvas, matching `BackgroundDante.tga`, `Videos\Loading.tga` and the SP left+right composite exactly.
- The rest is a tree of length-prefixed strings interleaved with 4-byte ids/offsets, holding **relative paths to external texture files** (`\textures\MosaicFiles\…`).
- **No embedded image data at all.** Scanned all 22 files for `DDS `, `\x89PNG`, `BM6`, `DXT1`, `DXT5` — **zero hits**. Across all 22 there are only 32 distinct texture references, every one a bare filename resolving to a loose file already on disk. The largest `.mgb` is 88 KB while one atlas it points at is 1 MB.

**So: `.mgb` are menu layout / widget-definition scripts, not archives. Skip them.** You would only crack one to reproduce the game's exact widget coordinates — and even then the `.mos.xml` mosaic manifests in `…\Textures\MosaicFiles\` are plain readable XML giving per-sprite X/Y/W/H inside each atlas, which is easier.

### Where the good large art actually lives

`…\Content\MenusPC\Textures\LoadingScreens\` is nearly empty — 3 files, only one real image (`BackgroundDante.tga`, 852×480 32-bit, 1,635,884 B). The real loading screens are in **`KellerGame\Slide\`**: 93 `.dds`, nearly all 1024×1024 DXT1 @ 524,416 B —
`Locations` 35, `Tactics` 22, `Equipments` 13, `MP` 6, `GameModeTips` 5, `Controls` 1, plus 11 at root.
**Watch out: only ~12 of the 35 `Locations` files are unique** — md5 shows heavy duplication (`05_Dantes_01` = `05_Dantes_04` = `05_Dantes_06` = `99_HeliRides_05InNear`; `02_Casino_02/03/05/06` = `99_HeliRides_02InNear`; `03_Fremont_01/02/03B` = `99_HeliRides_03InNear`). Dedupe before building a backdrop rotation.
Also note `…\KellerGame\Slide\startup.dds` is a 1:1 upscale of `…\LoadingScreens\BackgroundDante.tga` — same image; prefer the TGA for the unstretched original.

Other notable plates: `…\Textures\SinglePlayer\BGD_MissionSuccessE3.tga` (852×480, 24-bit, no alpha — warmest/most cinematic TGA); `…\Slide\default.dds` (1024×512 DXT5 **with** alpha, the only wide-aspect root plate); `…\Slide\demo_splash_screen.dds` (1024×1024 DXT1, 11 mipmaps, heavy pre-order marketing text — period reference, bad backdrop).

`KellerGame\ImageMap\` is 38 `.dds`, **all exactly 8,320 bytes = 128×128 DXT1, no mips, no alpha** — per-level menu thumbnails only (`SP_*` ×27, `MP_*` ×11, plus `SP_VOID.dds`). Contact sheet at `…\scratchpad\art\imagemap_contactsheet.png`. Fine as map thumbnails in a GUI, useless as chrome.

---

## Cut content

### Headline: `MP_Tower_01` "RED LOTUS" — a complete MP map with no level data

Everything except the geometry ships, and it is still wired up as the **default** server map. Verified by hand this session:

- `KellerGame\Config\DefaultServerOptions.ini:7` → `m_fstrMap=MP_Tower_01`
- `KellerGame\Config\DefaultServerOptions.ini:8` → `m_fstrSelectedMaps=MP_Casino_01,MP_Dantes_01,MP_Hoover_01,MP_LVU_01,MP_Mexico_01,MP_Tower_01`
- `KellerGame\Localization\INT\MP_Tower_01.int` (603 bytes) is a **complete** map localization: `LocationName=RED LOTUS`, `MissionName=RED LOTUS`, `MissionDescriptionMP=RECOMMENDED PLAYERS: 16 / MAX. PLAYERS: 16`, a written blurb ("THE RED LOTUS CASINO IS A CHINESE-THEMED CASINO LOCATED IN THE HEART OF LAS VEGAS…"), and four named spawn zones — `R6TeamSpawnZone_5` DEAD DISCO BAR, `_7` NINJA CHOP SUSHI, `_8` CASINO ROOFTOP, `_10` RED LOTUS CASINO.
- Localized into **all seven** shipped languages: `DEU\MP_Tower_01.deu`, `ESP`, `FRA`, `ITA`, `POL`, `RUS` + `INT`.
- Art present in three places: `KellerGame\ImageMap\MP_Tower.dds`, `KellerGame\Content\MenusPC\Textures\MapThumbnails\MP\MP_Tower.dds` **and** `.tga`, `KellerGame\Slide\Locations\MP_Tower_01.dds` (a full 1024×1024 loading screen).
- **Missing:** `KellerGame\Content\CookedPc\Maps\` has no `MP_Tower` folder (the MP dirs are `MP_Casino, MP_Dantes, MP_HooverDam, MP_KillHouseDouble, MP_LVU, MP_LVU2, MP_Mexico, MP_Streets`), and `find KellerGame -iname "MP_Tower*"` returns only the 11 art/localization files above — **no `.rmpc`, `.uppc`, `.shaders` or `.ini` anywhere.**

ID-gap corroboration, from the per-map `.ini` files under `Content\CookedPc\Maps\MP_*\`:
- `m_iAchievementID`: 21-29, **30 missing**, 31 (Killhouse)
- `m_iCoopHuntID`: 34,35,36, **37 missing**, 38-43, **44,45,46 missing**, 47
- `m_iFavMapKillsID` (stride 3): 0,3,6,…,24, **27 missing** — a 10th slot in an 18-map leaderboard block
- `m_iId`: 2-10 and 28; **1 is never used**

The name survives as a *story* chapter: `KellerGame\Localization\INT\99_HeliRides_03InNear.int:3` `MissionName=RED LOTUS`, and `KellerGame\Localization\INT\R6Objective.int:39` `MP_FREMONT_OBJ_01=ELIMINATE TERRORISTS FROM THE RED LOTUS CASINO`. GUESS: the MP map was carved out of the Fremont/Red Lotus singleplayer geometry and cut late.
Related leftover: `KellerGame\Content\MenusPC\Textures\Minimaps\` contains **only** `TowerE3\Tower_01…07.tga` — an E3-demo minimap set is the entire on-disk footprint of the minimap system.

### Orphan thumbnails: 8 `.dds` in `ImageMap\` with no map entry

Diffed every `m_fstrImage=` across all 61 map `.ini` files against the 38 files in `KellerGame\ImageMap\`. All 30 `m_fstrImage` values resolve; eight `.dds` resolve to nothing:

| orphan | name found in localization |
|---|---|
| `MP_Tower.dds` | see above |
| `SP_Dam1.dds` | `99_HeliRides_06In.int:7` `DamScene2=THE DAM` |
| `SP_Doctors.dds` | `99_HeliRides_06In.int:10` `DamScene5=THE DOCTORS` |
| `SP_Irena.dds` | `99_HeliRides_06In.int:11` `DamScene6=IRENA` |
| `SP_PrimeTime.dds` | `99_HeliRides_02InNear.int:8` `CasinoScene3=PRIME TIME` |
| `SP_Gabe.dds` | `99_HeliRides_05InNear.int:7` `DantesScene2=GABE` |
| `SP_Terrasse.dds` | no hit anywhere |
| `SP_VOID.dds` | no hit — RSV title-card placeholder |

These are **missing Terrorist Hunt entries, not missing levels.** `PC\KellerServerOptions.ini:36-55` lists the 20 shipped T-Hunt maps as ids `60,65,66,67,68,69,71,72,74,75,77,79,81,82,83,84,86,87,89,92`. The gaps at **70, 76, 80, 85, 88, 90, 91** line up one-for-one with the orphan thumbnails. The underlying story levels *do* ship (`02_Casino_04.ini`, `05_Dantes_02.ini`, `06_Dam_03/05/06.ini` all exist) but carry only `m_iCoopStoryID` / `m_iCurrentPart` — no `m_iId`, no `m_fstrImage`, no `[GameModeN]` block. **They were built and then never wired up as standalone T-Hunt maps.** GUESS, but a well-supported one: adding the missing `m_iId` / `m_fstrImage` / `[GameModeN]` keys to those map inis is a plausible "restore cut Terrorist Hunt maps" mod. Not verified.

Asymmetry worth noting: `MapThumbnails\MP\` has 10 maps but no `MP_KillhouseDouble`, while `ImageMap\MP_KillhouseDouble.dds` exists. GUESS: Killhouse was added after the source thumbnail folder was frozen; `ImageMap\` is the runtime folder, `MapThumbnails\` the stale source.

### Game modes

Full enum from the `Engine.uppc` name table — 21 values:
```
GAMEMODE_NONE, _ALL, _MAX, _BASEMP, _OBJECTIVE, _GYM, _LOCATION,
_MENU_MAIN, _MENU_OUTFITTING, _MENU_CHARACTERCREATION,
_STORY, _MISSION, _TERROHUNT,
_DEATHMATCH, _TEAMDEATHMATCH, _SHARPSHOOTER, _TEAMSHARPSHOOTER,
_ATTACKANDDEFEND, _RETRIEVAL, _CONQUEST, _ASSASSINATION
```
`GAMETYPEMP_PLAYERMATCH`, `_RANKEDMATCH`, `_MAX` — no LAN or ClanMatch value (clan is the separate `m_bClanGame` bool).

Maps declare 12 of these across 149 `[GameModeN]` blocks: MP `DEATHMATCH, TEAMDEATHMATCH, SHARPSHOOTER, TEAMSHARPSHOOTER, ATTACKANDDEFEND, RETRIEVAL, CONQUEST, ASSASSINATION, TERROHUNT`; SP `STORY, MISSION, LOCATION`.

**Cut modes:**
- **`GAMEMODE_OBJECTIVE`** — has a real class `R6ObjectiveGame`, an ini section (`PC\KellerGame.ini:116`), a localization section `[R6ObjectiveGame]` in `R6Game.int`, and a menu description at `R6Menus.int:454` which is the **untranslated placeholder `GameModeObjectivesDesc=OBJECTIVE MODE DESCRIPTION`**. No map declares it. Cut.
- **`GAMEMODE_GYM`** — zero references in any ini, localization, or class. (The string `Gymnasium` in the exe is an EAX reverb preset — false positive.)
- `_BASEMP`, `_ALL`, `_NONE`, `_MAX`, `_MENU_*` are internal sentinels, not content.

Class-level oddity: `R6SharpshooterGame` / `R6TeamSharpshooterGame` have localization sections in `R6Game.int` but **no such class exists** — `Sharpshooter` is absent from both package name tables and both exes, appearing only as two `StrProperty` values inside `R6Game.uppc`. So Sharpshooter is Deathmatch-with-different-rules, not its own class. Shipped game classes: `R6MultiPlayerGame, R6SinglePlayerGame, R6DeathmatchGame, R6TeamDeathmatchGame, R6AttackDefendGame, R6RetrievalGame, R6ConquestGame, R6AssassinationGame, R6ObjectiveGame, R6TerroristHuntGame, R6CoopTerroristHuntGame, R6CoopStoryGame, R6CooperativeGame`.

### Cut weapons and gadgets

`KellerGame\Localization\INT\R6Game.int` names items that have **no section in the weapons or gadgets ini**, and each is a real class with an export in `Content\CookedPc\R6Game.uppc` — implemented then cut, not typos:

| localization section | display name | class exists | ini section |
|---|---|---|---|
| `[R6LauncherRPG7]` | RPG-7 ROCKET LAUNCHER | yes | **none** |
| `[R6GadgetExplosiveClaymore]` | CLAYMORE | yes | **none** |
| `[R6GadgetExplosiveDetector]` | EXPLOSIVE DETECTOR | yes | **none** |
| `[R6GadgetExplosiveTripWire]` | TRIPWIRE | yes | **none** |
| `[R6GadgetGrenadeBlackOilMolotov]` | BLACK OIL MOLOTOV | yes | **none** |
| `[R6GadgetGrenadeMolotov]` | MOLOTOV | yes | has an ini section, but is **not in the MP outfitting list** |

The MP outfitting list is closed and enumerable — `R6Menus.int:1213-1225` has exactly 13 `Default__R6*` description keys (Shield, HeatSignature, RadarJam, MotionSensor, ExplosiveDemolition, ExplosiveBreaching, GrenadeFrag, GrenadeFlashbang, GrenadeTearGas, GrenadeSmoke, GrenadeIncendiary, GasMask, GasMaskSF10). Molotov, Claymore, Tripwire, Explosive Detector, RPG-7, Black Oil Molotov, SnakeCam and MedKit are **not** in it. Conversely `[R6Game.R6MedKit]` has an ini section but **no `ItemName` in `R6Game.int` at all**.

**Firearms are clean** — all 35 weapon sections have a matching `R6Game.int` `ItemName` and vice versa (the only exception is `ConfigR6FixedLMGM249`, the mounted turret, which is expected). No cut guns.

### Other dead and leftover references

- **Demo-build levels still shipped:** `Content\CookedPc\Maps\05_Dantes\05_Dantes_02_demo.*`, and `Localization\INT\99_HeliRides_DemoSPNear.int` (`LocationName=DEMO`, `MissionName=RS5-DEMO`). Reachable via `[DemoSP] DemoSPModeEnabled=1` in `PC\KellerEngine.ini:212`.
- **`[Engine.R6FPPWalkthroughConfig] m_FPPMap=05_Dantes_FPP_03`** (`PC\KellerGame.ini:141`) points at a map that **does not exist on disk**.
- **`MovieLoading.ini` is entirely dangling on PC.** Lines 4, 13, 22, 29, 37 point at `..\KellerGame\Content\Menus\Videos\*.bik`, but `Content\Menus` does not exist — the real folder is `Content\MenusPC\Videos`, which holds only `logos_PC.bik`, `SplashScreen.bik`, `Loading.tga`. So `LoadingE3.bik` / `LoadingE3_suite.bik` are references to E3-era loading movies that were never shipped.
- **`06_HooverDam` skips `Dam_07`** (has 01-06 and 08).
- `Content\CookedPc\Maps\PEC_HQ\PEC_HQ_Map.ini` starts `[Tests]` / `DISABLED=TRUE` and has no `[R6Game.R6MissionConfig]` and no `m_eGameMode`.
- `Content\CookedPc\Maps\03_Fremont\Medias\03_Tower_03_Cubemaps.uppc` — a Tower cubemap package misfiled in the Fremont folder.
- **`KellerGame\Localization\JPN\` is an empty directory** (0 files). DEU/ESP/FRA/ITA/POL have 41, RUS 42, INT 44. No language folder contains a string INT lacks, so there are no locale-exclusive strings.
- `Slide\Locations\` has loading screens for `02_Casino_02` and `03_Fremont_01` (sub-part levels with no mission config) and for the non-existent `MP_Tower_01`.

---

## Open questions

Ranked by how much they would change the tool's design.

1. **Does the game regenerate `PC\Keller<X>.ini` when the `[Internal] CRC` mismatches?** I proved the CRC is `appMemCrc` over the `Default<X>.ini` template, which rules out a self-tamper-check, and the regeneration model is the only mechanism that makes sense of that. But I did not launch the game, so the failure mode is unobserved. **One 10-minute experiment settles it:** copy the install's `Config` tree aside, change one harmless value in `PC\KellerWeaponsConfig.ini` (e.g. `m_iDamageMenuStat`), launch, quit, and diff. If the edit survives, the whole write strategy is confirmed. Worth doing before writing a line of GUI code.
2. **Are the `[R6Game.R6CheatInput]` bindings live in retail?** The 67 bindings are stock (they ship in `DefaultInput.ini` as `!Bindings=`), the `UR6CheatInput` / `UR6CheatManager` / `UR6KellerCheats` classes exist in the exe, and the console is wired at `PC\KellerEngine.ini:18`. But `R6CheatInput` is a *separate config class* from `[Engine.PlayerInput]`, and in UE3 the active PlayerInput subclass comes from script defaults, not ini. I searched the exe strings for a gate (`bCheatsEnabled`, `AllowCheats`, `-devmode`) and found nothing. **Unverified — do not ship a "cheats" tab until someone presses F10 in-game.**
3. **Is `intUR6CheatManagerexecReloadConfigFiles` reachable?** If it is, the tool gets live config hot-reload and the whole UX changes (apply-without-restart). Needs (2) answered first.
4. **Instance vs CDO — which difficulty table does the game actually use?** I read the `Packages\GameConfig\*.uppc` instance values (player health 105/105/50); the `Engine.uppc` class defaults say 200/160/120. My reasoning says the instance wins because `ConfigsManager` holds object references to them, but the two tables disagree on whether Elite penalises your damage to terrorists (instance says no, CDO says ×0.75). **Resolvable in-game**: shoot a terrorist on Veteran and on Elite and count hits.
5. **Can a `.uppc` scalar be rewritten in place safely?** The property values are fixed-width int32/float32 with no length prefix to fix up and no checksum I found, so an in-place patcher should work without re-serializing. I did not test a write (read-only session). If it works, tier 2 of the tool is cheap; if the package has a hash I missed, it is a rewrite.
6. **Does setting `GameDifficulty=GAMEDIFFICULTY_NORMAL` actually expose the hidden easy tier?** All the data exists (enum value, `DiffEasy=EASY` label, per-difficulty values in every config object). But `R6VegasServerConfig.ini` deliberately omits it from the legal coop values, and `TerroHuntMissionDifficultyInfo` only carries Veteran and Elite structs — so T-Hunt at NORMAL may fall back or fail. Untested.
7. **Can the cut Terrorist Hunt maps be restored by adding `m_iId` / `m_fstrImage` / `[GameModeN]` to the existing story-level inis?** The levels ship, the thumbnails ship, and the id gaps (70, 76, 80, 85, 88, 90, 91) match the orphan thumbnails exactly. This is the most promising "restore cut content" lead in the whole install, and it is pure ini editing. Untested.
8. **`MP_Tower_01` cannot be restored** — the level data simply is not on the disc. Dead end; do not waste time. The only route would be rebuilding it from the Fremont SP geometry, which is a level-design project, not a mod-manager feature.
9. **The `R6GameConfig.bin` / `R6_ProfileOPTIONS` / `R6_SaveCHECKPOINT` binaries** in `%USERPROFILE%\Documents\Ubisoft\R6Vegas\` are unexamined. Video/audio/control options and campaign progress live there. If the tool ever wants a "unlock all levels" or "reset progress" button it has to crack those. 846 / 97 / 500 bytes — small enough to be tractable, but out of scope this session.
10. **`AgoraConfig.lua`** (`KellerGame\Config\PC\AgoraConfig.lua`, 1403 bytes) is a plain-text Lua matchmaking config referenced at `PC\KellerEngine.ini:233`. I did not read it. Likely relevant only to anyone reviving online play.
11. **`.mgb` widget coordinates** — I established the container is a layout script with no embedded art, and read enough of the header to confirm the 852×480 canvas. I did not map the widget tree. Only needed if someone wants to *replace the game's own menus*, which is a different project from skinning a mod manager.

### Dead ends, stated plainly

- **Scanning the exe for `GAMEDIFFICULTY_` / `GAMEMODE_` / `GAMETYPEMP_` returns nothing.** Zero hits in both `R6Vegas_Game.exe` and `R6VegasServer.exe`. UnrealScript enum literals live in cooked package name tables. Do not repeat this search.
- **`[R6Game.R6SinglePlayerGame]` does not exist.** Campaign rules are not ini-exposed; they are in the per-map inis under `Content\CookedPc\Maps\`.
- **The terrorist count is not in `[R6Game.R6CoopTerroristHuntGame]`.** It is `m_eHostileDensity`, and that key exists in only two files on the whole disk.
- **`KellerGame\Config\Default*.ini` (the Config root) is not the template layer** — `KellerGame\Config\PC\Default*.ini` is. The root copy of `DefaultWeaponsConfig.ini` is a stale European-locale export with both different formatting *and* different values. Editing it does nothing.
- **`KellerGame\Config\PCKeller*.ini` are inert.** Shipped snapshots. Nothing reads or writes them.
- **`strings` is not installed on this machine.** Use Python for binary scanning.

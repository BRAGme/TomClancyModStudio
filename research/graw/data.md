# GRAW PS2 (SLUS-21422) — archive data inventory

Static analysis of `E:\PS2 Games\Tom Clancy's Ghost Recon - Advanced Warfighter (USA).iso`
(ISO9660 volume id `GR3`, 143 directory entries). Read-only; nothing on `E:` was modified.

All facts below come from tool runs in this session. Anything not machine-verified is
labelled **GUESS**.

Reader used: `tcps2.iso.Iso` + `tcps2.vokes.Vokes` (unmodified).

---

## 0. Correction to the brief: there are FIVE vokes archives, not three

The brief named `/VOKES0.IMG`, `/VOKES2.IMG`, `/MENU.IMG`. Those three parse, but
`/GR3_1.IMG` and `/GR3_2.IMG` are **also** valid vokes archives and they hold every
single-player level package, including all ten Survival / EnemyHunt levels. They are
missed by the default `open_archives` pattern `/(VOKES\d|GR|MENU)\.IMG$` because
`GR3_1` / `GR3_2` do not match `GR`.

`/SP.IMG` and `/MP.IMG` are **not** archives — both start `7F 45 4C 46` (`\x7fELF`),
i.e. they are the PS2 ELF executables (single-player and multiplayer builds).

Every archive's ISO-declared size happened to match its own header word[0] on this disc
(no bogus-size trap fired here), but the header value is what the reader used.

| archive | ISO lba | ISO-declared size | header filesize | records | files | sum of file sizes |
|---|---:|---:|---:|---:|---:|---:|
| `/VOKES0.IMG` | 204728 | 110 898 610 | 110 898 610 | 147 | **130** | 110 796 149 |
| `/VOKES2.IMG` | 56348 | 303 880 562 | 303 880 562 | 284 | **267** | 303 768 425 |
| `/MENU.IMG` | 277257 | 680 059 380 | 680 059 380 | 116 | **111** | 679 964 409 |
| `/GR3_1.IMG` | 609318 | 1 498 264 864 | 1 498 264 864 | 404 | **399** | 1 498 150 988 |
| `/GR3_2.IMG` | 1340893 | 1 371 962 544 | 1 371 962 544 | 382 | **377** | 1 371 848 724 |

Header u32[0..5] as read (all five have the entry table at 0x800, so all five are
well-formed):

```
MENU.IMG  : 0x2888e1f4 0x6dbb 0x800 0x1dc0 0x6720 0x7000
VOKES0.IMG: 0x069c2db2 0x7517 0x800 0x2390 0x6cf0 0x7800
VOKES2.IMG: 0x121cd972 0x9804 0x800 0x3d40 0x86a0 0xa000
GR3_1.IMG : 0x594db520 0xb6a8 0x800 0x53c0 0x9d20 0xb800
GR3_2.IMG : 0x51c67cb0 0xb167 0x800 0x4fa0 0x9900 0xb800
```

Full listings written to this folder:
`filelist_vokes0.txt`, `filelist_vokes2.txt`, `filelist_menu.txt`,
`filelist_gr3_1.txt`, `filelist_gr3_2.txt`.

---

## 1. Inventory by file extension

There are **no** `.CFG`, `.TXT`, `.DEF` or `.LST` files and **no** extension-less files
in any of the five archives (checked programmatically).

### `/VOKES0.IMG` — 130 files, 110 796 149 bytes
| ext | count | bytes |
|---|---:|---:|
| SS1 | 1 | 53 026 816 |
| LS1 | 10 | 39 939 068 |
| FBZ | 36 | 14 080 150 |
| LIN | 2 | 3 114 763 |
| **INI** | **50** | **283 990** |
| ICO | 4 | 261 744 |
| SB1 | 12 | 61 036 |
| WAV | 6 | 15 468 |
| SP1 | 1 | 12 288 |
| SCC | 8 | 826 |

### `/VOKES2.IMG` — 267 files, 303 768 425 bytes
| ext | count | bytes |
|---|---:|---:|
| SS1 | 2 | 210 448 384 |
| LS1 | 10 | 39 939 068 |
| LIN | 12 | 33 288 795 |
| FBZ | 36 | 14 080 150 |
| SB1 | 138 | 5 437 712 |
| **INI** | **50** | **283 990** |
| ICO | 4 | 261 744 |
| WAV | 6 | 15 468 |
| SP1 | 1 | 12 288 |
| SCC | 8 | 826 |

### `/MENU.IMG` — 111 files, 679 964 409 bytes
| ext | count | bytes |
|---|---:|---:|
| PSS | 8 | 313 360 416 |
| PKG | 1 | 252 154 496 |
| LS1 | 3 | 79 443 968 |
| DMP | 1 | 11 381 704 |
| M2V | 5 | 9 816 803 |
| LAZ | 1 | 5 509 082 |
| SS1 | 1 | 3 555 328 |
| SND | 2 | 1 613 280 |
| DMG | 1 | 1 227 128 |
| SB1 | 4 | 746 288 |
| INT | 50 | 371 739 |
| FRA | 14 | 311 588 |
| ESP | 14 | 308 468 |
| ICO | 4 | 135 319 |
| SP1 | 1 | 16 384 |
| **INI** | **1** | **12 418** |

### `/GR3_1.IMG` — 399 files, 1 498 150 988 bytes
| ext | count | bytes |
|---|---:|---:|
| PKG | 2 | 553 258 368 |
| LS1 | 54 | 344 647 680 |
| DMP | 17 | 337 927 496 |
| SS1 | 17 | 147 300 352 |
| LAZ | 17 | 61 471 940 |
| SB1 | 158 | 24 848 608 |
| DMG | 17 | 20 861 176 |
| WPN | 33 | 5 078 597 |
| SND | 2 | 1 613 280 |
| INT | 50 | 371 739 |
| FRA | 14 | 311 588 |
| ESP | 14 | 308 468 |
| ICO | 3 | 135 312 |
| SP1 | 1 | 16 384 |
| **INI** | **0** | **0** |

### `/GR3_2.IMG` — 377 files, 1 371 848 724 bytes
| ext | count | bytes |
|---|---:|---:|
| PKG | 2 | 553 258 368 |
| LS1 | 48 | 299 184 128 |
| DMP | 15 | 288 886 072 |
| SS1 | 15 | 129 957 888 |
| LAZ | 15 | 51 974 284 |
| SB1 | 150 | 22 345 680 |
| DMG | 15 | 18 406 936 |
| WPN | 33 | 5 078 597 |
| SND | 2 | 1 613 280 |
| INT | 50 | 371 739 |
| FRA | 14 | 311 588 |
| ESP | 14 | 308 468 |
| ICO | 3 | 135 312 |
| SP1 | 1 | 16 384 |
| **INI** | **0** | **0** |

**Format notes (observed, not guessed):**
- `.INI` — plain ASCII, Unreal-style `[Section]` / `key=value`.
- `.INT` / `.ESP` / `.FRA` — Unreal localisation files, **UTF-16LE** (printable-byte
  fraction measured at ~0.50 for every one of them). `.INT` = English, `.ESP` = Spanish,
  `.FRA` = French.
- `.DMG` / `.DMP` / `.LAZ` / `.SS1` — per-level package quadruple. `.DMG` is exactly
  **1 227 128 bytes in every level and in MENU** — a fixed-size table (contains the
  engine name table + class list). `.DMP` is the bulk level data (11–21 MB).
- `.SCC` — Visual SourceSafe `vssver.scc` leftovers (binary, ~10–144 bytes).
- `.WPN` — 33 weapon definition files, identical set in GR3_1 and GR3_2.
- `.LIN` — Magma/menu layout. `.FBZ` — compressed loading-screen images. `.PSS`/`.M2V`
  — video. `.SB1`/`.LS1`/`.SS1`/`.SP1` — DARE audio banks/streams.

**VOKES0 vs VOKES2:** every one of the 50 INI files (and 7 of 8 `.SCC`) is
**byte-identical** between the two archives (MD5-compared, 57 identical / 1 differing —
the differing one is `/VCDATA/VSSVER.SCC`). VOKES2 is VOKES0's config+menu set plus the
12 multiplayer level `.LIN` files and the full SFX bank.

---

## 2. Complete list of plainly-textual config files

### INI — `/VOKES0.IMG` and `/VOKES2.IMG` (identical 50-file set, byte-for-byte)

| archive | path | size |
|---|---|---:|
| VOKES0 + VOKES2 | `/ANIMATION.INI` | 437 |
| VOKES0 + VOKES2 | `/DARE.INI` | 141 |
| VOKES0 + VOKES2 | `/DEFAULT.INI` | 7879 |
| VOKES0 + VOKES2 | `/DEFAULTXBOX.INI` | 6118 |
| VOKES0 + VOKES2 | `/DEFUNREALED.INI` | 2603 |
| VOKES0 + VOKES2 | `/DEFUSER.INI` | 9706 |
| VOKES0 + VOKES2 | `/MANIFEST.INI` | 37848 |
| VOKES0 + VOKES2 | `/MAPS/AUTOPLAY.INI` | 2073 |
| VOKES0 + VOKES2 | `/MAPS/DEMO.INI` | 4511 |
| VOKES0 + VOKES2 | `/MAPS/MP_01.INI` | 2073 |
| VOKES0 + VOKES2 | `/MAPS/MP_02.INI` | 2073 |
| VOKES0 + VOKES2 | `/MAPS/MP_10.INI` | 2073 |
| VOKES0 + VOKES2 | `/MAPS/MP_11.INI` | 2073 |
| VOKES0 + VOKES2 | `/MAPS/MP_DLC1.INI` | 2073 |
| VOKES0 + VOKES2 | `/MAPS/MP_DLC2.INI` | 2073 |
| VOKES0 + VOKES2 | `/MAPS/MP_DLC3.INI` | 2073 |
| VOKES0 + VOKES2 | `/MAPS/MP_DLC4.INI` | 2073 |
| VOKES0 + VOKES2 | `/MAPS/MP_EX1.INI` | 2073 |
| VOKES0 + VOKES2 | `/MAPS/MP_EX2.INI` | 2073 |
| VOKES0 + VOKES2 | `/MAPS/OLDCITY.INI` | 10470 |
| VOKES0 + VOKES2 | `/MAPS/OLDCITY_A.INI` | 10484 |
| VOKES0 + VOKES2 | `/MAPS/OLDCITY_B.INI` | 10407 |
| VOKES0 + VOKES2 | `/MAPS/OLDCITY_MP.INI` | 1931 |
| VOKES0 + VOKES2 | `/MAPS/R6MENU.INI` | 1904 |
| VOKES0 + VOKES2 | `/MAPS/RAVENSHIELDCAMPAIGN.INI` | 1846 |
| VOKES0 + VOKES2 | `/MAPS/TRAINING2_MP.INI` | 2233 |
| VOKES0 + VOKES2 | `/MAPS/TRAINING_BASICS.INI` | 4887 |
| VOKES0 + VOKES2 | `/MAPS/TRAINING_MP.INI` | 2228 |
| VOKES0 + VOKES2 | `/MAPS/TRAINING_SHOOTING.INI` | 4951 |
| VOKES0 + VOKES2 | `/MAPS/TRAINING_TEAM.INI` | 10872 |
| VOKES0 + VOKES2 | `/MAPS/_DEBUG.INI` | 465 |
| VOKES0 + VOKES2 | `/NAMES.INI` | 2398 |
| VOKES0 + VOKES2 | `/PSX2GAME.INI` | 24963 |
| VOKES0 + VOKES2 | `/PSX2USER.INI` | 7980 |
| VOKES0 + VOKES2 | `/R6CREDITS.INI` | 27429 |
| VOKES0 + VOKES2 | `/R6ESCORTPILOTGAME.INI` | 125 |
| VOKES0 + VOKES2 | `/R6GAMESETTINGS.INI` | 18486 |
| VOKES0 + VOKES2 | `/RAINBOWSIX3.INI` | 8509 |
| VOKES0 + VOKES2 | `/RAVENSHIELD.INI` | 8632 |
| VOKES0 + VOKES2 | `/SERVER.INI` | 2283 |
| VOKES0 + VOKES2 | `/SETUPWARFARE.INI` | 10952 |
| VOKES0 + VOKES2 | `/SETUPWARFAREPSX2.INI` | 708 |
| VOKES0 + VOKES2 | `/SETUPWARFAREPSX2LINS.INI` | 368 |
| VOKES0 + VOKES2 | `/SETUPWARFAREUMOD.INI` | 407 |
| VOKES0 + VOKES2 | `/SETUPWARFAREXBOX.INI` | 413 |
| VOKES0 + VOKES2 | `/SETUPWARFAREXBOXSHIP.INI` | 1732 |
| VOKES0 + VOKES2 | `/SOUND.INI` | 882 |
| VOKES0 + VOKES2 | `/USER.INI` | 10750 |
| VOKES0 + VOKES2 | `/WINDOWSPOS.INI` | 2002 |
| VOKES0 + VOKES2 | `/XME.INI` | 247 |

### INI — `/MENU.IMG`

| archive | path | size |
|---|---|---:|
| MENU | `/BRIEFING.INI` | 12418 |

### INI — `/GR3_1.IMG`, `/GR3_2.IMG`

**None.** Zero `.INI` files in either level archive.

### Other textual files

`.INT` (50 per archive, UTF-16LE English localisation) exist in MENU, GR3_1 and GR3_2
— identical byte counts across all three (371 739 total). Same for the 14 `.ESP` and
14 `.FRA`. These are dialogue/menu strings, not gameplay config, with the one
gameplay-adjacent exception of `GR3WEAPONS.INT` (see §5).

---

## 3. Does GRAW keep R6 3's `/MAPS/<NAME>.INI` and `R6GAMESETTINGS.INI`?

**`R6GAMESETTINGS.INI` — PRESENT**, unchanged in role.
Path: `/R6GAMESETTINGS.INI`, 18 486 bytes, in both `/VOKES0.IMG` (offset 0x000000f8c0)
and `/VOKES2.IMG` (offset 0x00000120c0), byte-identical. 488 lines, sections
`[Engine.R6GameplaySettings]`, `[R6Abstract.R6AbstractHUD]`, `[R6Game.R6HUD]`,
`[R6Engine.R6InteractionRoseDesVents]`,
`[R6Engine.R6InteractionCircumstantialAction]`, `[Engine.R6AbstractGameManager]`.
The level packages reference it by name: the literal ASCII string `R6GAMESETTINGS.ini`
appears inside `/SURVIVAL_03B.DMP`. So it is live, not dead weight.

**`/MAPS/<NAME>.INI` — the MECHANISM is present but there is NO per-map INI for any
GRAW level.**

- The engine still builds the path: the format strings `..\Maps\%s.ini` and `%s.ini`
  are present in **every** level `.DMG` (34 hits in GR3_1, 30 in GR3_2, 2 in MENU.DMG —
  exactly 2 per `.DMG`, i.e. one occurrence of each string per level package).
- The per-map INI **filename** is baked into each level's `.DMP`: `SURVIVAL_03B.INI`
  appears once in `/SURVIVAL_03B.DMP`, `ENEMYHUNT_01B.INI` once in
  `/ENEMYHUNT_01B.DMP`, `S01_A.INI` once in `/S01_A.DMP`.
- But the `/MAPS/` directory that ships on disc contains **only Rainbow Six 3 Raven
  Shield map names**: `AUTOPLAY`, `DEMO`, `MP_01`, `MP_02`, `MP_10`, `MP_11`,
  `MP_DLC1..4`, `MP_EX1`, `MP_EX2`, `OLDCITY`, `OLDCITY_A`, `OLDCITY_B`, `OLDCITY_MP`,
  `R6MENU`, `RAVENSHIELDCAMPAIGN`, `TRAINING2_MP`, `TRAINING_BASICS`, `TRAINING_MP`,
  `TRAINING_SHOOTING`, `TRAINING_TEAM`, `_DEBUG`.
- There is **no** `MAPS/S01_A.INI`, no `MAPS/SURVIVAL_*.INI`, no `MAPS/ENEMYHUNT_*.INI`
  anywhere on the disc, and `/GR3_1.IMG` and `/GR3_2.IMG` have no `MAPS/` directory at
  all.

Concrete answer: **`R6GAMESETTINGS.INI` yes, at `/R6GAMESETTINGS.INI` in VOKES0 and
VOKES2. Per-map `/MAPS/<NAME>.INI` yes as a directory and as an engine code path, but
populated only with inherited Raven Shield maps — every GRAW campaign, Survival and
EnemyHunt level has its mission description compiled into its `.DMP` package instead.**

Two further INI names are referenced from inside the level packages but **do not exist
as files in any archive**: `GR3XBoxAI.ini` (17 hits in GR3_1, 15 in GR3_2, 1 in MENU —
one per level package) and `TWeapon.ini` (same distribution). **GUESS:** these are
Xbox-build leftovers whose contents were compiled in for the PS2 release.

---

## 4. Gameplay key/value lines, quoted verbatim

### `/SERVER.INI` (VOKES0 + VOKES2, 2283 bytes) — the densest enemy-count file

```ini
[Engine.R6ServerInfo]
MaxPlayers=16
NbTerro=25
RoundTime=300
BetweenRoundTime=0
BombTime=45
...
FriendlyFire=True
Autobalance=True
TeamKillerPenalty=True
AllowRadar=True
ServerName=Rainbow Six 3 ADVER
...
RoundsPerMatch=30
ForceFPersonWeapon=True
UseAdminPassword=False
DiffLevel=2
DedicatedServer=False
AIBkp=False
RotateMap=False
...
m_iNumReservedSlots=0
FragLimit=0
AllowFragLimit=False
MapListClass=Engine.R6MapListAdversarial
```

The rest of the file is `[Engine.R6MapListAdversarial]` / `[Engine.R6MapList]` with
`GameType[0..15]` and `Maps[0..15]` arrays naming Raven Shield MP maps
(`Oldcity_MP`, `Warehouse_MP`, `Presidio_MP`, `Peaks_MP`, `Streets_MP`, `Training_MP`,
`Airport_MP`, `Meatpacking_MP`, `Parade_MP`, `Airport2_MP`, `Import_Export_MP`,
`Garage_MP`).

### `/PSX2GAME.INI` (VOKES0 + VOKES2, 24 963 bytes) — the shipped PS2 config

Terrorist count and difficulty selectors (lines 1083–1092):

```ini
[R6Menu.R6MenuCustomMissionNbTerroSelect]
CustomMissionNbTerro=20

[R6Menu.R6MenuDiffCustomMissionSelect]
CustomMissionDifficultiLevel=21

[R6Menu.R6MenuCustomMissionWidget]
CustomMissionGameType=2
CustomMissionMap=Oil_Refinery
```

Server block (lines 1093 onward) — note `NbTerro=-1` here versus `25` in `SERVER.INI`:

```ini
[Engine.R6ServerInfo]
MaxPlayers=16
NbTerro=-1
RoundTime=1800
BetweenRoundTime=15
BombTime=45
...
RoundsPerMatch=10
...
DiffLevel=2
DedicatedServer=False
AIBkp=False
RotateMap=False
```

```ini
[Engine.GameInfo]
bChangeLevels=False
GoreLevel=0
bLocalLog=True
bWorldLog=True
GameSpeed=1.000000
```

**GUESS:** `CustomMissionMap=Oil_Refinery` is a Raven Shield map, so this whole
custom-mission block is inherited state, not a GRAW-authored default.

### `/DEFAULTXBOX.INI` (VOKES0 + VOKES2, 6118 bytes) — the one spawn-count INI key

```ini
[R6Game.R6GameInfo]
bNoMonsters=False
bHumansOnly=False
bCoopWeaponMode=False
bClassicDeathMessages=False
bLowGore=False
bVeryLowGore=False
m_iNumberOfMembersToSpawn=0


[R6Game.R6AdversarialMode]
m_fTimeLimit=0
```

`/DEFAULT.INI` has the same `[Engine.GameInfo]` block but **no** `[R6Game.R6GameInfo]`
section and therefore no `m_iNumberOfMembersToSpawn` — that key exists only in the
Xbox default file.

### `/R6GAMESETTINGS.INI` — AI skill, difficulty multipliers, team size, timers

Terrorist skill scaling by difficulty tier, verbatim:

```ini
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
; 	TERRORIST SETTINGS
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
m_fTerroristSkillMultiplierRecruit=0.20
m_fTerroristSkillMultiplierVeteran=0.70
m_fTerroristSkillMultiplierElite=1.25

m_iChanceToKillHostageModifierRecruit=-20
m_iChanceToKillHostageModifierElite=20

m_fGrenadeReactionDelayRecruit=1.0
m_fGrenadeReactionDelayVeteran=0.5

m_fReactionTimeForFiringRecruit=1.0
m_fReactionTimeForFiringVeteran=0.5

; max distance to find action point (cm)
m_iMaxDistanceForActionSpot=2000

m_iDefaultSearchTime=30
m_fMinDistToThrowGrenade=500

m_fTerroristRelaxSpeed=+116.0
m_fTerroristWalkingSpeed=+170.0
m_fTerroristRunningSpeed=+518.0 
m_fTerroristCrouchedRunningSpeed=+410.0
m_fTerroristCrouchedWalkingSpeed=+140.0
```

**Team size — the explicit terrorist-hunt squad count:**

```ini
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
; 	RAINBOW SETTINGS
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
m_iNbOfRainbow=4	; used for terrorist hunt mode

m_iRainbowFormationDistance=100
m_fRainbowMovementReticulePenaltyFactor=0.2

m_fRainbowWalkingSpeed=+250.0
m_fRainbowRunningSpeed=+400.0 
m_fRainbowCrouchedWalkingSpeed=+125.0
m_fRainbowCrouchedRunningSpeed=+250.0
```

AI sight / detection:

```ini
; Base Sight Distance (cm) 50m / 5000cm
m_fSightRadius=5000.0

; observation skill factor : 0.75 ... 1.25  (range = 0.5) ;   0.75 + 0.5*ObservationSkill
m_fBaseObservationSkillFactor=0.75
m_fObservationSkillRange=0.5

m_fSpotterMovingWalkPenaltyFactor=0.8
m_fSpotterMovingRunPenaltyFactor=0.6
m_fTargetMovingWalkPenaltyFactor=1.2
m_fTargetMovingRunPenaltyFactor=1.4
m_fLowLightPenaltyFactor=0.5
m_fMediumLightPenaltyFactor=0.75

; Dist at witch NPC will have 100% accuracy (no dispertion on bullets)
m_fDistForPerfectAccuracyTerro=500.0
m_fDistForPerfectAccuracyRainbow=500.0
```

Health / damage (this is the health-per-character-type table):

```ini
m_iMPPlayerMaximumWounds=20
m_iPlayerMaximumWounds=60
m_iRainbowMaximumWounds=40
m_iTerroristMaximumWounds=10
m_iArmouredTerroristMaximumWounds=15
m_iHostageMaximumWounds=10

; Threshold : above this value the target is wounded, below this value : no effect
m_iHeadWoundThreshold=0
m_iTorsoWoundThreshold=30
m_iArmsLegsWoundThreshold=40

m_fRangeAdjustedEnergyFactor=500.0000

; Wound Multiplier by Character Type
m_iMPPlayerWoundMultiplier=2
m_iPlayerWoundMultiplier=2
m_iRainbowWoundMultiplier=1
m_iArmouredTerroristWoundMultiplier=1
m_iTerroristWoundMultiplier=1
```

Ammo by difficulty tier:

```ini
m_PlayerMagazineMultiplierRecruit=3
m_PlayerMagazineMultiplierVeteran=2
m_PlayerMagazineMultiplierElite=2

m_PlayerGrenadeMultiplierRecruit=1
m_PlayerGrenadeMultiplierVeteran=1
m_PlayerGrenadeMultiplierElite=1

; the following is for rainbow AI only
m_bUnlimitedRainbowMagazines=true

; Bullets to put in primary weapon when all clips are empty
m_iNbOfBulletWhenEmpty=5
```

Co-op scoring by difficulty and player count, plus round timers:

```ini
;		COOP STATISTICS
m_fStatsRecruitMultiplier=0.75f
m_fStatsVeteranMultiplier=1.0f
m_fStatsEliteMultiplier=1.25f
m_fStats1PlayerMultiplier=1.0f
m_fStats2PlayersMultiplier=1.0f
m_fStats3PlayersMultiplier=0.75f
m_fStats4PlayersMultiplier=0.5f
m_fStatsFriendlyFireMultiplier=0.75f

m_fReconSatelliteTerrosPosUpdateTime=2.0f
m_fReconSatelliteTerrosPosFadeTime=1.0f

m_fTimeBetweenCompleteAndNewObj=3.0f

;		SERVER TIMERS
m_fWaitingForOtherPlayersTimer=15.0f
m_fPreGameTimer=3.5f
```

Cheat flags at the top of the file:

```ini
m_bCheatChavezNoDie=false
m_bCheatPriceNoDie=false
m_bCheatLoiselleNoDie=false
m_bCheatWeberNoDie=false
```

The remainder of `R6GAMESETTINGS.INI` is non-gameplay: bullet tracer colours, Karma
physics factors, minimap zoom, falling-damage heights, the large gamepad
sensitivity/auto-aim block (`m_fXSensitivityMultiplier`, `m_afRotationControlPoints[0..10]`,
`m_fAimDamping`, XIII-controller lock constants), HUD noise/blood-stain/reticule
colours, voice-engine confidence thresholds, multiplayer nameplate distances, and
minimap team colours. `[R6Abstract.R6AbstractHUD]`, `[R6Game.R6HUD]` and the two
`[R6Engine.R6Interaction*]` sections are purely HUD colours and blink rates.
`[Engine.R6AbstractGameManager]` holds one line: `m_fELOCte=24.0f`.

### `/MAPS/*.INI` — mode availability and terrorist-hunt loadouts

Every map INI is an `[Engine.R6MissionDescription]` block. The mode-availability flag
set is the key part. From `/MAPS/_DEBUG.INI` (465 bytes, complete file):

```ini
[Engine.R6MissionDescription]
version=2
m_MapName=rooms
LocalizationFile=R6Debug

; Availability of Game Modes
m_bPracticeModeGame=true
m_bStoryModeGame=true
m_bCoopStoryModeGame=true
m_bTerroristHuntGame=true
m_bTerroristHuntCoopGame=true
m_bSurvivalGame=true
m_bTeamSurvivalGame=true
m_bSharpShooterGame=true
m_bNoRulesGame=true

m_MaxNbOfPlayersAdv=8
m_Skins=(Package=R6Characters,green=R6RainbowMediumBlue,red=R6RainbowMediumDesertCamo)
```

`/MAPS/OLDCITY.INI` (line 20) carries a matchmaking rating for terrorist hunt:

```ini
m_bTerroristHuntGame=true
m_bTerroristHuntCoopGame=true
...
m_fTerroHuntMapELO=1650
```

and the per-operative terrorist-hunt loadouts:

```ini
; Terrorist Hunt Default Loadout
m_PriceEquipmentTerroHunt=(szPrimaryWeapon="R63rdWeapons.AssaultL85A1",szSecondaryWeapon="R63rdWeapons.Pistol92FS",szPrimaryItem="R6Weapons.R6FlashBangGadget",szSecondaryItem="R6Weapons.R6BreachingChargeGadget")
m_WeberEquipmentTerroHunt=(szPrimaryWeapon="R63rdWeapons.AssaultG36K",...)
m_LoiselleEquipmentTerroHunt=(szPrimaryWeapon="R63rdWeapons.AssaultFAMASG2",...)

; Terrorist Hunt Silenced Loadout
m_PriceSilencedEquipmentTerroHunt=(szPrimaryWeapon="R63rdWeapons.SubUMP",...)
m_WeberSilencedEquipmentTerroHunt=(szPrimaryWeapon="R63rdWeapons.SubTMP",...)
m_LoiselleSilencedEquipmentTerroHunt=(szPrimaryWeapon="R63rdWeapons.SubMP5SD5",...)
```

The `MP_*.INI` files (all exactly 2073 bytes) use the **adversarial** flag set instead
and have no terrorist-hunt keys at all. `/MAPS/MP_01.INI` in full for the mode block:

```ini
[Engine.R6MissionDescription]
version=3
m_MapName=ST10_MAP
m_ShortName=ST10_MAP
LocalizationFile=R6Mission
...
; Availability of Game Modes
m_bAssaultGame=true
m_bSabotageGame=true
m_bOnslaughtGame=true
m_bLastManStandingGame=true
m_bNoRulesGame=true

m_MaxNbOfPlayersAdv=16
m_MaxNbOfPlayersTeamAdv=16
```

followed by `m_bUseCamoFaces`, `m_Skins=(...)`, `m_PlayerEquipment=(...)` and
`m_MultiplayMapWeapon[0..15]`.

The terrorist-hunt maps cap at `m_MaxNbOfPlayersAdv=8`; the adversarial maps at 16.

### Other INIs — no gameplay numbers found

```ini
; /R6ESCORTPILOTGAME.INI (125 bytes, complete file)
[R6Game.R6EscortPilotGame]
EnablePilotPrimaryWeapon=False
EnablePilotSecondaryWeapon=True
EnablePilotTertiaryWeapon=True
```

```ini
; /DEFUSER.INI
[Engine.PlayerController]
...
EnemyTurnSpeed=45000
...
[R6Engine.R6PlayerController]
EnemyTurnSpeed=100000
m_fTeamMoveToDistance=6000.000000
m_bUseFirstPersonWeapon=TRUE
```

`ANIMATION.INI` is an anim-notify name list. `NAMES.INI` is an input action name list.
`DARE.INI`, `SOUND.INI`, `XME.INI`, `WINDOWSPOS.INI` are audio/window plumbing.
`R6CREDITS.INI` (27 429 bytes) is credits text. `MANIFEST.INI` (37 848 bytes) is a
`File=(Src=...,Master=...,Size=...)` asset manifest — it names
`Animations\R6Terrorist_UKX.ukx` but carries no counts.
The six `SETUPWARFARE*.INI` files are build/packaging config. `RAINBOWSIX3.INI` and
`RAVENSHIELD.INI` are `[URL]` / `[Engine.Engine]` boot config (`EXEName=RainbowSix3.exe`,
`DefaultGame=R6Game.R6NoRules`). `DEFUNREALED.INI` is editor config.

### `/MENU.IMG/BRIEFING.INI` — mission briefing sequencing

23 sections, `[Briefing.default]` plus `[Briefing.S01_a_Big]` … `[Briefing.S12_B_Big]`.
Each is camera path + `.bik` video + sound cue lists, e.g.:

```ini
[Briefing.default]
Path_X=447
Path_X=300
Path_X=300
Path_Y=278
Path_Y=278
Path_Y=200
MovingSpeed=50
RotateSpeed=180.0
IconAppearSpeed=2
ScanLineSpeed=0.5
TextDrawingSpeed=60
TargetDirection=NotSpecify
AlphaTeamDirection=NotSpecify
ZoomInSpeed=2.0
TargeSquareType=0
TargetSquareWidth=64
TargetSquareHeight=64
MinVoiceLength=15
MovieInterval=0.4
```

No enemy counts. **Notable absence:** the sections run
`S01_a`, `S01_b`, `S02_a`, `S02_b`, `S03_a`, `S03_b`, `S04_a`, `S04_b`, `S05_a`,
`S05_b`, `S06_a`, `S06_b`, **`S08_a`**, … `S12_B` — **there is no `S07` briefing**, and
no `Survival_*` or `EnemyHunt_*` briefing.

---

## 5. Survival / EnemyHunt mode and level hunt

### All ten named levels exist on disc as complete level packages

Each level ships as a four-file set `<NAME>.DMG` + `<NAME>.DMP` + `<NAME>.LAZ` +
`<NAME>.SS1`.

**`/GR3_1.IMG`** — 17 levels: `ENEMYHUNT_01B`, `ENEMYHUNT_02A`, `ENEMYHUNT_04B`,
`ENEMYHUNT_06B`, `ENEMYHUNT_10A`, plus campaign `S01_A`, `S01_B`, `S02_A`, `S02_B`,
`S03_A`, `S03_B`, `S04_A`, `S04_B`, `S05_A`, `S05_B`, `S06_A`, `S06_B`.

**`/GR3_2.IMG`** — 15 levels: `SURVIVAL_03B`, `SURVIVAL_05B`, `SURVIVAL_09A`,
`SURVIVAL_S11B`, `SURVIVAL_S12A`, plus campaign `S08_A`, `S08_B`, `S09_A`, `S09_B`,
`S10_A`, `S10_B`, `S11_A`, `S11_B`, `S12_A`, `S12_B`.

Sizes for example: `/ENEMYHUNT_01B.DMG` 1 227 128 @ 0x00148b7b20,
`/ENEMYHUNT_01B.DMP` 19 735 528 @ 0x00135e5730, `/ENEMYHUNT_01B.LAZ` 3 246 963 @
0x00149e34a0.

**`S07` is absent from every archive** — no `S07_A`/`S07_B` level package and no
`[Briefing.S07_*]` section. **GUESS:** mission 7 was cut.

### Where each searched name appears

| name | appears as | where |
|---|---|---|
| `Survival` | substring | 24 hits in VOKES0, 24 in VOKES2, 164 in MENU, 841 in GR3_1, 774 in GR3_2 |
| `SurvivalMode` | menu widget + game-mode name | `/MENU.DMG` (menu tree), `/MENU.DMP`; 102 GR3_1 / 90 GR3_2 |
| `B_SurvivalMode` | menu button id | `/MENU.DMG` at 0x8bd288 and 0x8be988; 51 GR3_1 / 45 GR3_2 / 4 MENU |
| `EnemyHunt` | mode + level prefix | 112 MENU, 548 GR3_1, 466 GR3_2 |
| `HuntMode` | menu screen + `RGM_*TerroristHuntMode` enum | `/MENU.DMG`, `/MENU.DMP`; 221 GR3_1 / 195 GR3_2 |
| `TERROHUNT` | filter enum `EFILTER_TERROHUNT` + localisation key | `/MENU.DMG` 0x8bfaa0, `/MENU.DMP` 0xaeeea8; 51 GR3_1 / 45 GR3_2 |
| `SHOOTHUNT` | localisation key next to `ID_MISSION_ORDER` | `/MENU.DMG` 0x8bfad0, `/MENU.DMP` 0x12aebe0; 34 GR3_1 / 30 GR3_2 |
| `Survival_03b` / `_05b` / `_09A` / `_S11B` / `_S12A` | level names | file names in GR3_2; string lists in MENU/GR3_1/GR3_2; `GR3WEAPONS.INT` sections |
| `EnemyHunt_01b` / `_02a` / `_04b` / `_06b` / `_10a` | level names | file names in GR3_1; string lists; `GR3WEAPONS.INT` sections |

### Verbatim context, `/MENU.DMG`

The main-menu button tree (offset 0x8bd288), ASCII with `.` for non-printable:

```
........B_Multiplayer...B_XboxLive......B_SurvivalMode..........B_EnemyHuntMode.B_SystemLink....B_Profiles......SurvivalMode....QuickMission....HuntMode........Options.Credit..
```

and at 0x8be988:

```
B_Credit........B_BACK..B_Confirm.......B_SurvivalMode..........B_EnemyHuntMode.P_GR3Campaign_selection.........GR3Campaign_selection...B_SoloCampaign..........
```

The `Maps\%s.ini` loader and the two hunt tokens, `/MENU.DMG` 0x8bfaa0:

```
System..FAB.....Engine..Core....PC USER.TERROHUNT.......ID_MISSION_ORDER........R6Menu..SHOOTHUNT.........\Maps\%s.ini..................Engine.R6MissionDescript
```

Game-mode enum in `/MENU.DMP` 0xaf1e9d:

```
oopStoryMode...........!...RGM_TerroristHuntMode.......!...RGM_CoopTerroristHuntMode...!...RGM_DeathmatchMode..........!...RGM_TeamDeathmatchMode......!...RGM_SharpShooterMode........!...RGM_TeamC
```

Server-browser filters in `/MENU.DMP` 0xaeeea8:

```
EFILTER_SURVIVAL............!...EFILTER_TERROHUNT...........!...EFILTER_MISSION.................
```

### `GR3WEAPONS.INT` — per-level loadout tables for all ten modes

Present identically in `/MENU.IMG`, `/GR3_1.IMG` and `/GR3_2.IMG` (`/GR3WEAPONS.INT`,
35 421 bytes). Lines 473–530, verbatim (the file is UTF-16LE; decoded here):

```ini
[Survival_03b]
SLOT3=W_CryeCarbine
SLOT2=FragGrenadeGadget
SLOT1=W_SR25
SLOT4=W_M92_FS

[Survival_05b]
SLOT3=W_ScarLCarbine
SLOT2=FragGrenadeGadget
SLOT1=W_XM109
SLOT4=ChaffGrenadeGadget

[Survival_09a]
SLOT3=W_CryeCarbine
SLOT2=FragGrenadeGadget
SLOT1=W_SR25
SLOT4=W_M92_FS

[Survival_S11b]
SLOT3=W_CryeCarbine
SLOT2=FragGrenadeGadget
SLOT1=W_XM109
SLOT4=W_M92_FS

[Survival_S12A]
SLOT3=W_Crye_NGL
SLOT2=W_CryeGrenadier
SLOT1=W_XM109
SLOT4=C4Gadget

[EnemyHunt_01b]
SLOT3=W_CryeCarbine
SLOT2=FragGrenadeGadget
SLOT1=W_SR25
SLOT4=W_M92_FS

[EnemyHunt_02a]
SLOT3=W_CryeCarbine
SLOT2=FragGrenadeGadget
SLOT1=W_SR25
SLOT4=W_M92_FS

[EnemyHunt_04b]
SLOT3=W_CryeCarbine
SLOT2=FragGrenadeGadget
SLOT1=W_SR25
SLOT4=W_M92_FS

[EnemyHunt_06b]
SLOT3=W_CryeCarbine
SLOT2=FragGrenadeGadget
SLOT1=W_SR25
SLOT4=W_M92_FS

[EnemyHunt_10a]
SLOT3=W_CryeCarbine
SLOT2=FragGrenadeGadget
SLOT1=W_SR25
SLOT4=W_M92_FS
```

These sections are followed by `[s01_a]`, `[s01_b]`, … for the campaign. This is the
only place on the disc where the ten mode levels have authored, human-readable,
per-level **gameplay data**.

### `XBOXLIVE.INT` — mode display names (MENU, GR3_1, GR3_2)

```ini
ECM_Survival=CONQUEST SURVIVAL
L_Survival=SURVIVAL
L_Teamsurvival=TEAM SURVIVAL
TypeAdvSurvival=SURVIVAL
TypeAdvTeamsurvival=TEAM SURVIVAL
SurvivalEntry1=ROUNDS
SurvivalEntry2=WINS
SurvivalEntry3=PERFECTS
SurvivalEntry4=BEST TIME
GameTypeTeamSurvival=TEAM SURVIVAL
```

---

## 6. Raw byte hunt across all archives

Method: each archive streamed from the ISO in 16 MiB chunks with a (needle_len − 1)
byte overlap carried between chunks, so a match spanning a chunk boundary is still
found. Bytes scanned: VOKES0 110 898 610, VOKES2 303 880 562, MENU 680 059 380,
GR3_1 1 498 264 864, GR3_2 1 371 962 544 — **3 965 065 960 bytes total**. Hit offsets
are relative to each archive's own byte 0, and each hit is attributed to the file entry
whose `[offset, offset+size)` range contains it.

Scripts: `<scratchpad>/rawhunt.py` (first needle set) and
`<scratchpad>/rawhunt2.py` (second set). Both run as
`python rawhunt.py` with no arguments; the ISO path and needle list are literals in the
source.

### Requested needles — results

| needle | VOKES0 | VOKES2 | MENU | GR3_1 | GR3_2 |
|---|---:|---:|---:|---:|---:|
| `m_iNbToSpawn` | 0 | 0 | 0 | 0 | 0 |
| `m_NumberInWave` | 0 | 0 | 0 | 0 | 0 |
| `m_bHuntFromStart` | 0 | 0 | 0 | 0 | 0 |
| `NbToSpawn` | 0 | 0 | 0 | 0 | 0 |
| `NumberInWave` | 0 | 0 | 0 | 0 | 0 |
| `HuntFromStart` | 0 | 0 | 0 | 0 | 0 |
| `R6DZoneWave` | 0 | 0 | 0 | 0 | 0 |
| `GR3DZoneWave` | 0 | 0 | 0 | 0 | 0 |
| `DZoneWave` | 0 | 0 | 0 | 0 | 0 |
| `ScriptSpawnTerrorists` | 0 | 0 | **2** | **34** | **30** |
| `SpawnTerrorists` | 0 | 0 | **5** | **85** | **75** |
| `DeploymentZone` | 0 | 0 | **5** | **92** | **96** |

**Precise negative:** the nine Rainbow Six 3 wave-system identifiers `m_iNbToSpawn`,
`m_NumberInWave`, `m_bHuntFromStart`, `NbToSpawn`, `NumberInWave`, `HuntFromStart`,
`R6DZoneWave`, `GR3DZoneWave` and `DZoneWave` appear **zero times** in all
3 965 065 960 bytes of all five vokes archives. GRAW PS2 did not inherit R6 3's
`R6DZoneWave` naming.

### Context for the three that do hit

`DeploymentZone` always appears as the class name **`GR3DeploymentZone`** (the GRAW
rename of R6's deployment zone), and `SpawnTerrorists` always as part of
**`ScriptSpawnTerrorists`**, `Vehicle_SpawnTerrorists` or
`LatentVehicle_SpawnTerrorists`. Every hit is inside a `.DMG` or `.DMP` level package;
none are inside any INI.

`/MENU.IMG` at offset 0x8b9144, file `/MENU.DMG`:

```
em..R6Engine........Core............AGR3DeploymentZone......System..FAB.....Engine..Core............No Squad AI set for %s..........Patrol Actors not enough in 
```

`/MENU.IMG` at offset 0xa77df3, file `/MENU.DMP`:

```
.....p.?.........................!...GR3DeploymentZone...........A....%m..,..0......`.;....................@.....P3...X..PP.. T..A....(m..,n"p......`.:.........
```

`/MENU.IMG` at offset 0x8c3750, file `/MENU.DMG`:

```
lWithEnemy......StartForceMove..........ScriptSpawnTerrorists...........ScriptIsInLatent........Exploded................SpawnDamageSmoke........FireAt..StopVehi
```

`/GR3_1.IMG` at offset 0x5b8760, file `/S02_B.DMP`:

```
....!...StartForceMove..............!...ScriptSpawnTerrorists.......!...ScriptIsInLatent................Exploded....!...SpawnDamageSmoke................FireAt..
```

`/GR3_1.IMG` at offset 0x4440e3, file `/S02_B.DMP`:

```
.....p.?.........................!...GR3DeploymentZone...........A....%m..,..0Q..D..`.;...9................@.....Pi......P... ...A....(m..,n"pS..D..`.:...;.....
```

The pattern is identical in every level package: `ScriptSpawnTerrorists` occurs once in
each `.DMG` and once in each `.DMP` (2 per level × 17 levels = 34 in GR3_1, × 15 = 30 in
GR3_2, plus 2 in MENU), i.e. it is a deduplicated **name-table entry**, not per-instance
data.

`GR3DeploymentZone` is different — it occurs **once per `.DMG`** but a **varying** number
of times per `.DMP`, which is the count of named deployment-zone instances in that
level:

| level | `.DMP` hits | | level | `.DMP` hits |
|---|---:|---|---|---:|
| `/S09_A.DMP` | 10 | | `/SURVIVAL_09A.DMP` | 9 |
| `/S09_B.DMP` | 8 | | `/ENEMYHUNT_01B.DMP` | 6 |
| `/S03_A.DMP` | 5 | | all other levels | 2 |
| `/MENU.DMP` | 2 | | | |

### Second needle set — the GRAW-native names found by string-mining

Having established the R6 names are absent, the Survival level package was mined for
what replaced them. `/SURVIVAL_03B.DMP` (18 354 936 bytes, pulled from `/GR3_2.IMG`)
yields these, then re-searched across all five archives:

| needle | VOKES0 | VOKES2 | MENU | GR3_1 | GR3_2 |
|---|---:|---:|---:|---:|---:|
| `m_iNbOfTerroristToSpawn` | 0 | 0 | 1 | 17 | 15 |
| `m_iNbOfTerro` | 0 | 0 | 2 | 34 | 30 |
| `m_bHuntMode` | 0 | 0 | 1 | 17 | 15 |
| `m_CanSpawnTerrorist` | 0 | 0 | 1 | 17 | 15 |
| `LatentVehicle_SpawnTerrorists` | 0 | 0 | 1 | 17 | 15 |
| `Vehicle_SpawnTerrorists` | 0 | 0 | 2 | 34 | 30 |
| `ScriptTakeDeploymentZone` | 0 | 0 | 1 | 17 | 15 |
| `AutomaticInitialSpawning` | 0 | 0 | 1 | 287 | 264 |
| `m_iRespawnLimit` | 0 | 0 | 1 | 17 | 15 |
| `m_iRespawnTimes` | 0 | 0 | 1 | 17 | 15 |
| `LevelDifficulty` | 0 | 0 | 1 | 17 | 15 |
| `m_eMissionDifficulty` | 0 | 0 | 1 | 17 | 15 |
| `SurvivalMissionName` | 0 | 0 | 4 | 68 | 60 |
| `HuntMissionName` | 0 | 0 | 4 | 68 | 60 |
| `m_bSurvivalGame` | 12 | 12 | 2 | 34 | 30 |
| `m_bTerroristHuntGame` | 12 | 12 | 3 | 51 | 45 |
| `GR3XBoxAI.ini` | 0 | 0 | 1 | 17 | 15 |
| `TWeapon.ini` | 0 | 0 | 1 | 17 | 15 |
| `..\Maps\%s.ini` | 0 | 0 | 2 | 34 | 30 |
| `GR3DZ_Endure_Wave` | 0 | 0 | 0 | 0 | **20** |
| `GR3SquadAI_Wave` | 0 | 0 | 0 | 0 | **1** |
| `SY_DeathCounter_Wave` | 0 | 0 | 0 | 0 | **2** |
| `SY_DeathConter_Wave` (sic) | 0 | 0 | 0 | 0 | **2** |
| `SURVIVAL_03B.INI` | 0 | 0 | 0 | 0 | **1** |
| `ENEMYHUNT_01B.INI` | 0 | 0 | 0 | **1** | 0 |
| `S01_A.INI` | 0 | 0 | 0 | **1** | 0 |

**`m_iNbOfTerroristToSpawn` is the GRAW equivalent of R6 3's `m_iNbToSpawn`.** It is
present exactly once per level package (17 + 15 + 1 = 33 = the number of `.DMP` files).
Context, `/GR3_2.IMG` file `/SURVIVAL_03B.DMP` at 0x286d10:

```
wn...\s..\s....l!...BroadcastGameMsg.\s..\s.g.......GetNewTeam..!...SheetBuilder.....\s..\s. ...!...m_iNbOfTerroristToSpawn.....!...RemoveObjective..\s..\s..S.N!...RawMaterialFactory...\s. .......Loop
```

`m_bHuntMode`, `/SURVIVAL_03B.DMP` at 0x306b20:

```
e.O.................eClothes........eFace...........strMiddle.......strEnd..........MaxStamina......m_bHuntMode.!...HuntModeBestTime.\s..\s.plic....iIterator.......szMapId.ions....szMapName...!..._pla
```

### The wave system is called "Endure", and only `SURVIVAL_03B` has a full 10-wave set

`GR3DZ_Endure_Wave` hits 20 times, **all inside `/GR3_2.IMG` file `/SURVIVAL_03B.DMP`**
— `GR3DZ_Endure_Wave1_A` through `GR3DZ_Endure_Wave10_B`, i.e. 10 waves × 2 zones.
Context at 0x93c740:

```
!...SY_EndurePanhard_3rd.RINT.
B!...GR3_Treebase0....\s..\s.. RE!...GR3_Treebase01_colmesh..0...!...GR3DZ_Endure_Wave1_A.\s.tB2.....FifthWave..
!...GR3DZ_Endure_Wave8_A.\s. GOG!...GR3DZ_Endure_Wave3_B
```

and at 0x93cf20:

```
_Wave8_B.\s.AME ....ThirdWave.it!...GR3DZ_Endure_Wave3_A.\s.TEL !...GR3DZ_Endure_Wave5_B.\s. GRE!...GR3SquadAI_Wave..\s..\s. EXP....S03_B_Dirt0.
```

The wave death counters, `/SURVIVAL_03B.DMP` at 0x948b10:

```
!...SM_US_Embassy_3flag_B_.35.OF!...SM_Road_cenotaph_Base_N_.7..!...SY_DeathConter_Wave0.\s.>..
!...SY_DeathCounter_Wave0.s.<COL1...CM_PS_HFA15x15S_AV1_blockplayer_.....
```

(Both the typo'd `SY_DeathConter_Wave0` and the correct `SY_DeathCounter_Wave0` are
present — two separate actor names.)

Debug log format strings, `/SURVIVAL_03B.DMP` at 0x9d1b1f:

```
..$...p[....p[..&....++++++ Wave1 Counter.9S.p[......%..`.......02.....Wave1 Counter=.9S.p[..../20
```

The full set `++++++ Wave1 Counter` … `++++++ Wave10 Counter` and
`Wave1 Counter=` … `Wave10 Counter=` is present, plus the state labels `SecondWave`,
`ThirdWave`, `FourthWave`, `FifthWave`, `SixthWave`, `SeventhWave`, `EighthWave`,
`NinthWave`, `TenthWave`.

Per-level census of Endure/wave/deployment-zone actor names across all 32 level `.DMP`
files (every level was read and string-scanned):

| level | Endure / wave actor names found |
|---|---|
| `SURVIVAL_03B` | `GR3DZ_Endure_Wave1_A`…`Wave10_B` (20), `GR3SquadAI_Wave`, `SY_DeathCounter_Wave`, `SY_DeathConter_Wave`, `GR3VPanhard_Endure`, `SY_EndurePanhard`, `SY_EndurePanhard_2nd`, `SY_EndurePanhard_3rd` |
| `S03_B` | `GR3SquadAI_Endure_Wave`, `GR3SquadAI_Endure_Additional`, `SY_DeathCounter_FirstWave/SecondWave/ThirdWave`, `Endure_Tank_A/B/C`, `SY_EndureController`, `SY_EndureArpacheController`, `SY_EndureBHController`, `SY_EndureHeliController`, `SY_EndurePanhardController`, `SY_EndureFirstTank/SecondTank/ThirdTank`, `SY_EndureSucceedChecker`, `EndureBravoSavePresident`, `GR3EndureVBL_0`, `SurvivedEndure` |
| `S01_B` | `M01_EndureDeathCounter`, `Pocket4Endure`, `EndureCounter=`, `Endure death counter current value =` |
| `S06_B`, `ENEMYHUNT_06B` | `Add_Endure`, `EndureC`, `EndurePawn`, `EndurePawnA`, `Finish_Endure`, `HangerEndureA/B/C`, `isStartEndure` |
| `S06_A` | `EndureA_`, `EndureB_`, `isStartEndure` |
| `S09_B` | `GR3DeploymentZone_Endure0`, `Endure_Start`, `S09B_Endure_2ndRound` |
| `SURVIVAL_09A` | `S09AEndure_Logic`, `S09AEndure_Logic0` |
| `S03_A` | `SY_ConvoySpawn_DeathCounter` |
| `S10_B` | `NoEndure` |
| all 32 levels | `GR3DeploymentZone`, `GR3SquadAI`, `M09_Obj02_EndureTheReinforcement`, `m_IsPlayerInEndureMode` |

`SURVIVAL_05B`, `SURVIVAL_S11B`, `SURVIVAL_S12A`, `ENEMYHUNT_01B`, `ENEMYHUNT_02A`,
`ENEMYHUNT_04B` and `ENEMYHUNT_10A` have only the four universal names — **no
level-specific Endure/wave actors at all**. **GUESS:** those levels drive their spawning
from generic `GR3DeploymentZone` instances plus the compiled-in
`m_iNbOfTerroristToSpawn` value rather than from an authored wave ladder, and
`SURVIVAL_03B` (built on the `UsEmbassyF_B` / `S03_B` map) is the only fully hand-scripted
10-wave Endure level. This is a strong pattern but has not been confirmed by decoding
the `.DMP` property blocks.

### Other spawn/difficulty identifiers present in `/SURVIVAL_03B.DMP`

Found by string extraction, not yet value-decoded:

```
m_iNbOfTerroristToSpawn   m_iNbOfTerro            m_CanSpawnTerrorist
ScriptSpawnTerrorists     Vehicle_SpawnTerrorists LatentVehicle_SpawnTerrorists
GR3DeploymentZone         GR3DeploymentZone0      ScriptTakeDeploymentZone
Vehicle_TakeDeploymentZone                        AutomaticInitialSpawning
m_iRespawnLimit           m_iRespawnTimes         m_bAllowRespawn
m_bDelayedRespawn         MinRespawnTime          ForceRespawnTime
RespawnLimit              IsAllowedToRespawn      bShowRespawnCountDown
fCountDownRespawnTime     fCountDownForceRespawnTime
LevelDifficulty           m_eMissionDifficulty    m_eDifficulty
EMissionDifficulty        eGameDifficulty         p_byMissionDifficulty
eLastCampaignDifficulty   eCustomMissionLastDifficulty
TerroristCount            iTakeByTerroristCount   m_iNbWeaponsTerro
m_iNbDeaths               m_iNbKills              m_iNbOfRestart
RaibowTeamMustSurvive (sic)                       SurvivalModeBestKill
TeamsurvivalSuddenDeath   TieBreakSurvivor        m_iNbOfRainbow
```

The level's own map asset is `UsEmbassyF_B_Survival` / `SM_UsEmbassyF_B_Survival_`, and
the level package carries its own launch URL as a literal string:
`map=Survival_03b -host -savemem -nomovie`. Every level `.DMG` carries the equivalent
line (`map=s01_a -host -savemem -nomovie`, `map=EnemyHunt_01b -host -savemem -nomovie`,
…) together with ` INI=psx2game.ini USERINI=psx2user.ini`.

---

## 7. Where to go next

1. **`m_iNbOfTerroristToSpawn` values are in the `.DMP` property blocks**, not in any
   text file. Decoding the `.DMP` container (Unreal-style name table + object export
   table, judging by the `!...` separators and the deduplicated name lists) is the only
   path to the actual enemy counts.
2. `/SP.IMG` and `/MP.IMG` are PS2 ELFs — `SP.IMG` is 6 507 824 bytes. Static defaults
   for `m_iNbOfTerroristToSpawn`, the difficulty multipliers and the Endure wave logic
   will be in there as class default properties.
3. `GR3XBoxAI.ini` and `TWeapon.ini` are referenced but absent — worth checking whether
   the Xbox release of GRAW ships them as loose files.


---

## 8. Addendum — corroborated against the `SP.IMG` overlay

Added after the archive survey, from static analysis of the executables
(full working in [survival.md](survival.md)). Everything in this section was
read out of `/SP.IMG` or `/MP.IMG` with a disassembler.

### 8.1 `..\Maps\<MAP>.ini` really is read at runtime — this is a live data channel

The format string `"..\Maps\%s.ini"` is at `SP.IMG` VA `0x00699090` (second
copy `0x0069DEF8`) and is used by **seven** functions. The reads go through
`GConfig` against section **`[Engine.R6MissionDescription]`**:

```
0056d558  lui   $at, 0x77
0056d560  lw    $a0, -0x6c8($at)      ; GConfig
0056d568  addiu $a1, ...              ; "Engine.R6MissionDescription"
0056d56c  addiu $a2, ...              ; "m_bSurvivalGame"
0056d574  lw    $t9, 8($t9)           ; GConfig->GetBool
0056d578  jalr  $t9
```

Keys queried inside `0x0056D010` alone: `m_bTerroristHuntGame`,
`m_bTerroristHuntCoopGame`, `m_bSurvivalGame`, `m_bTeamSurvivalGame`.
Function `0x005063A0` uses the same file for `LocalizationFile` when it builds
the mission list.

So §3's finding — that the loader looks for `MAPS/<LEVEL>.INI` files GRAW never
shipped — is confirmed from the code side, and the reading machinery is intact.
**Untested guess:** adding `/MAPS/SURVIVAL_03B.INI` with an
`[Engine.R6MissionDescription]` section may therefore be a code-free way to set
mode booleans. Nothing here proves the retail build tolerates a file it never
had, and the game was not run.

### 8.2 Why the enemy counts cannot be in any INI

Searched both overlays for the GRAW-native property names this survey found in
the `.DMP` packages:

| string | in `SP.IMG` | in `MP.IMG` |
|---|---|---|
| `m_iNbOfTerroristToSpawn` | absent | absent |
| `Endure` | absent | absent |
| `GR3DZ` | absent | absent |
| `GR3SquadAI_Wave` | absent | absent |
| `m_iNbOfRainbow` | absent | absent |
| `m_fTerroristSkillMultiplier` | absent | absent |
| `GR3DeploymentZone` | `0x006926F1` (as `AGR3DeploymentZone`) | absent |
| `R6GAMESETTINGS` | absent | `0x005AD0D0` |
| `DiffLevel` | absent | `0x005B16E8` |

The overlay reads these properties **by offset, never by name** — which is why
the values live in the level package's property block and nowhere else. That
also means `R6GAMESETTINGS.INI`'s per-difficulty AI keys are consumed by
`MP.IMG`, not by the single-player overlay.

### 8.3 The single-player level list, straight from the executable

`SP.IMG` carries a flat 32-entry name-pointer table at VA `0x00671720`,
consumed only by `0x0053A580` (`LevelNameToIndex`, 8 call sites):

```
 0..21  s01_a s01_b s02_a s02_b s03_a s03_b s04_a s04_b s05_a s05_b
        s06_a s06_b s08_a s08_b s09_a s09_b s10_a s10_b s11_a s11_b s12_a s12_b
22..26  Survival_03b Survival_05b Survival_09A Survival_S11B Survival_S12A
27..31  EnemyHunt_01b EnemyHunt_02a EnemyHunt_04b EnemyHunt_06b EnemyHunt_10a
```

This **independently confirms §5's finding that mission S07 is cut**: the
executable's own level table jumps `s06_b` → `s08_a`, exactly as `BRIEFING.INI`
does. Two artefacts, produced by different pipelines, agree.

The index is used only to select a record slot — `idx-22` into the Survival
record array at `0x007B5EA8`, `idx-27` into the EnemyHunt time array at
`0x007B5E50`. Both arrays are in BSS, so they are savegame state, not editable
data.

### 8.4 Difficulty, from the code side

The menu writes 1=`B_Recruit`, 2=`B_Ghost`, 3=`B_Elite`, 4=`B_GhostLeader`
(handler `0x004AF160`), which `0x004F13A0` converts to a 0-based byte on
GameInfo `+0x414`. That byte has exactly **three** readers in the whole overlay:
two health-regeneration gates (`if difficulty < 2`) and one selector that picks
one of four authored floats at GameInfo `+0x4D0`/`+0x4D4`/`+0x4D8`/`+0x4DC`.

`R6GAMESETTINGS.INI`'s `m_fTerroristSkillMultiplier` supplies **three** values
(Recruit / Veteran / Elite) for a **four**-tier menu, so it cannot be a
one-to-one feed for those four floats. Whether it feeds them at all is **not
established** — treat any such mapping as a guess until someone traces the
GameInfo property load.

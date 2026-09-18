# Rainbow Six 3: Raven Shield (PC) — moddable-surface dossier

Target: `D:\SteamLibrary\steamapps\common\Rainbow Six 3 Gold\` (referred to below as `<GAME>`).
Engine: Unreal Engine 2, package **version 118 / licensee 14** (verified, §U1).
Everything below was read this session. Nothing in `<GAME>` was written.

Supporting artefacts generated this session (all in this scratchpad):
`upc.py` (UE2 v118/14 package reader), `props.py` + `dumpcls.py` (class default-property
extractor with struct recursion), `findprop.py` (validated property locator),
`cfg2.py` (`config`/`globalconfig` variable extractor), `weapontable.py`,
`rs3_weapons.csv` (197 weapon classes × tunables × byte offsets),
`rs3_ammo.csv` (61 ammo classes), `rs3_descbars.json` (57 menu stat-bar entries),
`cfgall.txt` (full config-variable census).

---

## Headline

Raven Shield has **four** independently addressable tiers, and a GUI should treat them
as four different write strategies:

| Tier | Medium | Write strategy | Reversible |
|---|---|---|---|
| 1. `config` variables | `.ini` text | write ini keys | trivially |
| 2. AI templates | `template\*.tpt` / `.tph` plain text | rewrite text file | trivially (backup) |
| 3. Mod descriptors | `Mods\*.mod`, `Mods\*.game` ini | **generate a new drop-in mod** | delete the file |
| 4. Class defaults | `.u` tagged property lists | **equal-width binary patch** | byte-for-byte restore |

Tier 4 is the one that decides the product, and the answer is **yes**: RS3 PC `.u`
packages are uncompressed, carry valid export tables, and store class
`defaultproperties` as ordinary UE2 tagged property lists that can be rewritten in
place at identical width. Worked examples with offsets in §U3–U5.

---

## Levers

Confidence key: **V** = verified by reading the bytes/lines this session; **L** = likely
(structure verified, semantics inferred from naming + cross-reference); **G** = explicit guess.

### A. Enemy count, difficulty, AI

| Name | File | Section/key or offset | Stock | What it does | Conf |
|---|---|---|---|---|---|
| Terrorist count (MP/COOP) | `<GAME>\system\ServerCOOP.ini` | `[Engine.R6ServerInfo] NbTerro` L3 | `25` (COOP) / `0` (`Server.ini`) | AI terrorists spawned per round | V |
| Terrorist count (SP custom / T-Hunt) | `<GAME>\Save\Profiles\user.ini` | `[R6Menu.R6MenuCustomMissionNbTerroSelect] CustomMissionNbTerro` | `50` live, `20` in `DefUser.ini:700` | Terrorist count for custom missions | V |
| Difficulty | `Server.ini` / `ServerCOOP.ini` L29; `user.ini` `[R6Menu.R6MenuDiffCustomMissionSelect]` | `DiffLevel` / `CustomMissionDifficultyLevel` | `2` | **0=recruit, 1=veteran, 2=elite.** `R6Mnu.int:755-757` states it verbatim: elite = "Terrorists take less time before shooting". It is a *reaction-time* knob only | V |
| AI backup teammates | `ServerCOOP.ini` L31 | `[Engine.R6ServerInfo] AIBkp` | `True` (COOP) / `False` (ADVER) | Fills empty COOP slots with AI | L |
| Friendly fire | `Server.ini` | `[Engine.R6ServerInfo] FriendlyFire` | `True` | MP only — **no SP equivalent exists** | V |
| **Per-template AI skill (8 stats)** | `<GAME>\template\*.tpt` (218 files) | `Assault / Demolitions / Electronics / SSniper / Stealth / SelfControl / Leadership / Observation`, plus `RndVariation` | `50` in `A_Normal.tpt`, `75` in `Airport-1.tpt` | **The real AI difficulty surface.** Plain text, no recompile | V (syntax) / L (per-stat effect) |
| Terrorist personality mix | `template\*.tpt` | `Coward / DeskJockey / Normal / Hardened / SuicideBomber / PSniper` (must sum to 100) | `10/5/50/20/10/5` | Behaviour archetype distribution. Enum confirmed in `R6Engine.u` as `PERSO_Coward` … `PERSO_SuicideBomber` | V (names) / L (effect) |
| Terrorist weapon/grenade/pawn pools | `template\*.tpt` | `NbOfWeapon` + weighted `NNN, Package.Class` lines | per template | What each terrorist carries and looks like | V |
| Terrorist gear chance | `template\*.tpt` | `Flashlight / Glasses / Sunglasses / Helmet` | `33/10/50/0` | Percent chance. `Helmet` is armour-relevant | V (syntax) / L (helmet=damage) |
| Hostage behaviour | `template\*.tph` (47 files) | `Coward / Normal / Brave / Bait`, `Kneeling / Standing`, `StartAsCivilian` | varies | Hostage AI | V |
| Teammate follow distance | `user.ini` | `[R6Engine.R6PlayerController] m_fTeamMoveToDistance` | `6000.0` | AI teammate move-to range. **Confirmed `config`** (`cfgall.txt`, R6Engine.u) | V |
| Door-open speed | `user.ini` | `[R6Engine.R6PlayerController] m_iDoorSpeed` / `m_iFastDoorSpeed` | `20` / `100` | Tactical pacing. Confirmed `config` | V |

### B. Stealth / detection economy (`Sound.ini` is misnamed — it is the AI hearing model)

| Name | File | Key | Stock | What it does | Conf |
|---|---|---|---|---|---|
| Player footstep audibility | `<GAME>\system\Sound.ini` | `[R6Game.R6NoiseMgr] m_Rainbow` | `fStandSlow=300, fStandFast=800, fCrouchSlow=200, fCrouchFast=400, fProne=400` | How far AI hears **you**, per posture+speed. The core stealth knob | V (key) / L (semantics) |
| Reload noise | `Sound.ini` | `m_SndReload` | `fSndDist=500, eType=NOISE_Investigate` | Halve for silent reloads | L |
| Gunshot/explosion alert radius | `Sound.ini` | `m_SndBulletImpact` `1100`, `m_sndExplosion` `3000` | — | Alert propagation | L |
| Door / talking / screaming / death noise | `Sound.ini` | `m_SndDoor` `1000`, `m_SndTalking` `1000`, `m_SndScreaming` `2000`, `m_SndDead` `600` | — | — | L |
| Terrorist / hostage audibility | `Sound.ini` | `m_Terro`, `m_Hostage` | `1000/1500/1500/2000/2000` | How far **you** hear them | L |

All 15 `R6NoiseMgr` keys are **verified `config`-flagged** in `R6Game.u` by `cfg2.py`
(`cfgall.txt`), which is why they work from ini. **Anomaly, unresolved:** for
`m_Terro`/`m_Hostage`, prone (2000) is louder than standing-slow (1000). Either the
struct field order differs from `m_Rainbow` or terrorists are deliberately easy to
hear. Do not expose these as "posture sliders" until tested in-game.

### C. HUD, tactical aids, aim assist (all `user.ini`, all verified `config` in `Engine.u`)

| Key | Section | Stock | What it does | Conf |
|---|---|---|---|---|
| `HUDShowReticule` | `[Engine.R6GameOptions]` | `True` | Crosshair on/off | V |
| `HUDShowCharacterInfo` / `HUDShowCurrentTeamInfo` / `HUDShowOtherTeamInfo` / `HUDShowWeaponInfo` / `HUDShowWaypointInfo` / `HUDShowActionIcon` / `HUDShowPlayersName` / `HUDShowFPWeapon` | same | `True` | Individual HUD element toggles — a complete "hardcore HUD" preset | V |
| `ShowRadar` | same | `True` | Motion tracker | V |
| `AutoTargetSlider` | same | `0` live; `DefUser.ini:662` ships `1` | Aim assist strength. Bound to `F2=ToggleAutoAim` | L |
| `HideDeadBodies` | same | `FALSE` | Corpse persistence | V |
| `WantTriggerLag` | same | `False` | Simulated trigger delay | G |
| `Hide3DView` | same | `False` | Suppresses the 3D view | L |
| `m_Color` | `[R6Weapons.R6Reticule]` | `(R=255,G=0,B=0)` | Crosshair colour. Verified `config` in `R6Weapons.u` — the **only** config var in that entire package | V |
| `m_reticuleFriendColour` | `[Engine.R6GameOptions]` | `(G=255)` | Friendly-target reticule | V |
| `FieldOfView` | `<GAME>\system\openrvs.ini` `[OpenRVS.OpenFOV]` | `95` | Actual in-game FOV; overrides `DesiredFOV=90` | V |
| `bUnlimited` | `openrvs.ini` `[OpenRVS.OpenOptionsGame]` | `False` | Unlimited ammo/gear | L |
| `NewCheatManagerClass` | `openrvs.ini` `[OpenRVS.OpenFOV]` | *(empty)* | Cheat-manager injection point. **The only ini-level cheat door in the game** — needs a `.u` supplying the class | L |

### D. Loadout / kit restriction — *undocumented, never written to disk*

`cfg2.py` on `<GAME>\system\Engine.u` found **ten `config` arrays on `R6ServerInfo`
that appear in no shipped ini file** (`grep -rn Restricted <GAME>\system\*.ini` → zero hits):

| Key | Element type | Conf |
|---|---|---|
| `RestrictedPrimary`, `RestrictedSecondary`, `RestrictedMiscGadgets` | **string** array | V |
| `RestrictedAssultRifles` *(sic)*, `RestrictedSubMachineGuns`, `RestrictedMachineGuns`, `RestrictedMachinePistols`, `RestrictedPistols`, `RestrictedShotGuns`, `RestrictedSniperRifles` | **class** array | V |

Element types read from each `ArrayProperty`'s `Inner` export in `Engine.u`. This is a
pure-ini weapon-restriction system — exactly the "kit lock" lever a mod manager wants —
that ships unused. **Exact ini value syntax is untested (G):** the class arrays almost
certainly want `RestrictedPistols=class'R63rdWeapons.NormalPistol92FS'` and the string
arrays a bare `Package.Class`. First thing to verify in-game.

Loadout defaults (per slot, up to 4 operatives) are fully ini-driven in
`<GAME>\system\StartWithLauncher.ini`: `ArmorName[0..3]`, `PrimaryWeaponName[0..3]`,
`PrimaryWeaponGadgetName[0..3]`, `PrimaryBulletType[0..3]`, secondary equivalents,
`FirstGadgetName[0..3]`, `SecondGadgetName[0..3]` (`R6Weapons.R6HBSGadget` = heartbeat
sensor), `NumberOfMembers`, `PlayerTeam`. **V.**

### E. Class-swap levers (`Mods\*.mod`, `[Engine.R6Mod]`, all verified `config` in `Engine.u`)

| Key | Stock | What it does | Conf |
|---|---|---|---|
| `m_DefaultLightPawn` / `m_DefaultMediumPawn` / `m_DefaultHeavyPawn` | `R6Characters.R6Rainbow{Light,Medium,Heavy}` | Player pawn class = the health/armour model | V |
| `m_DefaultRainbowAI` | `R6Engine.R6RainbowAI` | **Replace this and you replace all teammate AI** | V |
| `m_PlayerCtrlToSpawn` | `R6Engine.R6PlayerController` | Player controller | V |
| `m_HostageMgrToSpawn` / `m_GlobalHUDToSpawn` | — | Hostage manager, HUD class | V |
| `m_szGameTypes` ×N | 13 `RGM_*` entries | **Which game modes appear in menus** | V |
| `m_aReticuleList` | 11 reticule classes | Crosshair set | V |
| `m_szCampaignIniFile` / `m_szServerIni` / `m_szUserIni` / `m_szMenuDefinesFile` | `RavenShieldCampaign` / `server` / `user` / `R6ClassDefines` | Which ini files the mod reads | V |
| `m_aExtraPaths` | — | Appends asset search paths | V |
| `m_szBackgroundRootDir` / `m_szVideosRootDir` / `m_szIniFilesDir` | `Backgrounds` / `Videos` / — | Art + config redirect roots | V |

Campaign roster: `<GAME>\maps\RavenShieldCampaign.ini` `[R6Game.R6Campaign]` —
`missions=` ×15 (L3-17), `m_OperativeClassName=` ×29 (L18-46). All verified `config`
in `R6Game.u`. **Adding a campaign mission is a one-line ini edit.**

### F. Weapon tuning — `.u` binary patch (see §U3 for the mechanism)

Every field below is a 4-byte int or float inside a class default-property list and is
**rewritable at identical width**. Full table for all 197 classes with byte offsets:
`rs3_weapons.csv`. 138 classes carry a complete stat block — these are the
`Normal*` / `CMag*` / `Silenced*` / `Slug*` / `Buck*` variants the loadout menu actually
instantiates; the 16 bare `AssaultM4`-style parents carry only attachment caps.

Worked example — **`NormalAssaultM4`** in `<GAME>\system\R63rdWeapons.u` (export 180, class serial @0x0dea2):

| Field | Offset | Type | Stock |
|---|---|---|---|
| `m_iClipCapacity` | `0x00defe` | int32 | 30 |
| `m_iNbOfClips` | `0x00df04` | int32 | 6 |
| `m_iNbOfExtraClips` | `0x00df0a` | int32 | 3 |
| `m_fMuzzleVelocity` | `0x00df10` | float | 55260 |
| `m_fFireSoundRadius` | `0x00df1c` | float | 3684 |
| `m_fRateOfFire` | `0x00df22` | float | 0.072727 (s/round → 825 RPM) |
| `fBaseAccuracy` | `0x00df2f` | float | 1.25958 |
| `fShuffleAccuracy` | `0x00df35` | float | 1.74254 |
| `fWalkingAccuracy` | `0x00df3b` | float | 2.61382 |
| `fWalkingFastAccuracy` | `0x00df41` | float | 10.782 |
| `fRunningAccuracy` | `0x00df47` | float | 10.782 |
| `fReticuleTime` | `0x00df4d` | float | 0.49 |
| `fAccuracyChange` | `0x00df53` | float | 7.33177 (**recoil per shot**) |
| `fWeaponJump` | `0x00df59` | float | 11.4244 (**muzzle climb**) |
| `m_fFireAnimRate` | `0x00df6a` | float | 1.375 |

Compare `CMagAssaultM4` (export 66, @0x0a120): same fields, `m_iClipCapacity=100`
@`0x00a17c`, `fReticuleTime=0.7525`, `fWeaponJump=7.65217` — so the C-Mag is *steadier*
but slower to settle. All in `rs3_weapons.csv`.

**Recoil naming, resolved:** there is no property literally named `recoil` anywhere in
`R6Weapons.u`'s 1403-entry name table. Recoil is `fAccuracyChange` + `fWeaponJump`
inside the `stAccuracyType` struct. **L** (structural position + the fact that
`R6Description.u`'s `m_ARecoilPercent` display bar tracks them; see §I).

### G. Damage — lives on the **ammo**, not the weapon

`<GAME>\system\R6Weapons.u` defines 61 ammo classes with an energy/penetration model.
Full table: `rs3_ammo.csv`.

| Field | Meaning | `ammo9mmParabellumNormalJHP` (export 1063) | Offset |
|---|---|---|---|
| `m_iEnergy` | int32, the damage/energy term | 567 | `0x019c26` |
| `m_iPenetrationFactor` | int32 | 4 | `0x019c2c` |
| `m_fKillStunTransfer` | float | 0.5 | `0x019c32` |
| `m_fRangeConversionConst` | float | 0.065746 | `0x019c38` |
| `m_fRange` | float | 85.5368 | `0x019c3e` |

Base class `R6Bullet` (export 1, @0x07135) defaults: `m_iEnergy=100` @`0x0072a4`,
`m_iPenetrationFactor=1` @`0x0072aa`, `m_fRange=100` @`0x0072bc`. **V** — decoded
byte-for-byte in §U4.

Spread for reference: `ammo556mmNATONormalFMJ` energy 1442, `ammo762mmNATONormalFMJ`
2547, `ammo9mmParabellumNormalFMJ` 567.

### H. Weapon attachment caps — a real "unlock" lever, with one hard limit

Each weapon's `m_stWeaponCaps` struct is a nested tagged property list of 4-byte ints:
`bSingle`, `bThreeRound`, `bFullAuto`, `bCMag`, `bSilencer`, `bLight`, `bMiniScope`,
`bHeatVision`. Example, `AssaultM4` (export 25, `<GAME>\system\R63rdWeapons.u`):

```
bSingle    @0x007e7e = 1      bSilencer  @0x007e90 = 1
bFullAuto  @0x007e84 = 1      bLight     @0x007e96 = 1
bCMag      @0x007e8a = 1      bMiniScope @0x007e9d = 1
```
(no `bThreeRound` → the M4 has no burst mode). **V.**

**The limit:** UE2 only serialises a property whose value differs from its class
default. `R6AssaultRifle` (export 898) and `R6Weapons` (export 15) carry **no**
`m_stWeaponCaps` at all, so every cap defaults to 0 and every `1` you see is authored.
You can therefore **turn a cap off in place, but you cannot add one**, because inserting
a property would shift every byte after it. **V.**

**The workaround (V, mechanism verified; G, that the game accepts it):** you can *rename*
an existing cap tag, because the tag is a compact name index and several are the same
width. In `R63rdWeapons.u`: 1-byte tags `bSingle=0x37`, `bFullAuto=0x3e`, `bCMag=0x3d`,
`bSilencer=0x3c`, `bLight=0x2a` are mutually interchangeable; 2-byte tags
`bThreeRound=0x5401`, `bMiniScope=0x4701`, `bHeatVision=0x6401` are mutually
interchangeable. So "give the M4 a thermal scope" = rewrite its `bMiniScope` tag bytes
`47 01` → `64 01` at `0x007e9b`. Zero size change.

### I. Menu stat bars — patch these too or the UI lies

`<GAME>\system\R6Description.u` holds 57 loadout-menu entries. Each has five int arrays
indexed by variant, aligned with `m_WeaponTags`:

`R6DescAssaultM4` (export 112, @0x05389), `m_WeaponTags = [NORMAL, CMAG, SILENCED]`,
`m_WeaponClasses = [R63rdWeapons.NormalAssaultM4, .CMagAssaultM4, .SilencedAssaultM4]`:

| Array | Offset (first element) | Values |
|---|---|---|
| `m_ARangePercent` | `0x0053e4` | 39, 39, 19 |
| `m_ADamagePercent` | `0x0053f4` | 56, 56, 28 |
| `m_AAccuracyPercent` | `0x005404` | 49, 49, 59 |
| `m_ARecoilPercent` | `0x005414` | 47, 66, 99 |
| `m_ARecoveryPercent` | `0x005424` | 96, 92, 92 |

**These are display only.** They are not read by the ballistics code — nothing in
`R6Description.u` is `config`-flagged and the values are percentages, not units. A GUI
that changes damage in `R6Weapons.u` must also rewrite `m_ADamagePercent` here or the
menu bars will disagree with the gun. Full data: `rs3_descbars.json`. **V** (data),
**L** (display-only role — inferred from the `Percent` naming, the 0-100 range, and the
separate real values in §F/§G).

`m_WeaponClasses` is also the **kit-unlock list**: it is what the menu offers per weapon
entry. It is an array of length-prefixed strings, so editing it changes total size —
**not** in-place patchable. Use `RestrictedPistols` etc. (§D) to subtract instead.

### J. Cut / unlisted content

| Finding | Evidence | Conf |
|---|---|---|
| **Defend and Recon game modes are fully compiled and unlisted** | `<GAME>\system\R6Game.u` contains classes `R6DefendGame` (export 728), `R6DefendCoopGame` (2761), `R6ReconGame` (1761), `R6ReconCoopGame` (2106). `Engine.u`'s `RGM_*` enum has 31 tokens; no shipped `.mod` `m_szGameTypes` lists `RGM_DefendMode`, `RGM_DefendCoopMode`, `RGM_ReconMode`, `RGM_ReconCoopMode`. `RavenShield.ini:276` still carries server-browser filters `bDefend=True, bRecon=True` | V |
| Squad Deathmatch / Squad Team Deathmatch classes exist | `R6Game.u` exports `R6SquadDeathmatch` (1799), `R6SquadTeamDeathmatch` (1755); `RGM_SquadDeathmatch` unlisted; filters `bSquadDeathMatch=True` | V |
| **Five operatives cut** | `maps\RavenShieldCampaign.ini:47-51` references `R6Game.R6Operative30..34`; `R6Game.u` contains only `R6Operative1..29`, and `R6Operatives.int` has no sections for them | V |
| Three debug maps cut | `<GAME>\system\R6Debug.int` fully describes `[Rooms]`, `[allhostage]`, `[ladder]` with `ID_LOCATION=Montreal, Canada`, `ID_DATETIME=Today`, unique key `ID_OBJECTIVES=Debug Game Play`. No `rooms.rsm` / `allhostage.rsm` / `ladder.rsm` in `<GAME>\maps\` | V |
| Two shipped maps have broken name tables | `teamciahq.rsm` but `teamcia.int:1` says `[test1]`; `BetaCruiseship2.rsm` but `BetaCruiseship2.int:1` says `[Cruiseship2]` | V |
| `bDebugGameMode=True` filter exists | `RavenShield.ini:276` and `:411` | V |
| `Ammo200.ini` is dead | references packages `Ammo200` and `ASIWGuns`; neither `system\Ammo200.u` nor `Mods\ASIWGuns\` exists | V |
| `GrenadeDropMod` installed but never loaded | `system\GrenadeDropMod.u` + `.ini` exist; no `ServerActors=`/`ServerPackages=` line anywhere references it | V |

**Turning Defend/Recon back on is a `.mod` text edit** — add `m_szGameTypes=RGM_DefendMode`
etc. to a generated `.mod`. That is the single highest-value "unlock cut content"
button available, and it needs no binary patching. **L** — the classes compile and are
referenced by the enum, but nobody has confirmed they run.

### K. Mod system — how a GUI should ship changes

**Verdict: generate a drop-in mod. Do not edit base-game files.**

Discovery is a wildcard scan, not a fixed list: `<GAME>\system\Engine.u` contains the
literal run `RAVENSHIELD.MOD` / `IRONWRATH.MOD` / `ATHENASWORD.MOD` / `..\Mods\` / `mod`
at byte offsets 327027-327077, next to the identifiers `FindExtraMods`, `GetExtraMods`,
`GetNbMods`, `IsOfficialMod`. The three uppercase names are only the "official badge"
comparison set. **V.**

Proof both ways: `SupplyDrop` is third-party, appears in the selector, and is absent
from both `system\R6Mod.int` and `system\R6Info.ini`. `Mods\NewOperative\` is a folder
with no sibling `.mod` and never appears.

Minimum to write:
```
<GAME>\Mods\<Keyword>.mod      ← descriptor, SIBLING of the folder
<GAME>\Mods\<Keyword>\         ← payload
```
Required `[Engine.R6Mod]` keys (intersection of all four shipped `.mod` files):
`Version` / `MinorVersion` / `BuildVersion` (mismatch → `R6Mod.int:4 VersionMM=Version Mismatch`),
`m_szKeyword`, `m_fPriority` (1=base, 2=expansion), `m_ConfigClass=Engine.R6ModConfig`,
`m_szCampaignIniFile`, `m_szServerIni`, `m_szUserIni`, `m_bUseCustomOperatives`,
`m_aDescriptionPackage`, `m_szGameTypes` ×N. Plus an `[Engine.GameEngine]` section
copied from `Mods\RavenShield.mod:67-81`.

Override model is **explicit redirect, not a VFS overlay** — each key names a path or a
file stem. Backgrounds are a **partial merge**: `Mods\AthenaSword\Backgrounds\` mirrors
the base tree minus `ModSelector\` and `Main_menu_06.tga`, and the missing files fall
through to the base folder (`Mods\SupplyDrop` drops `Multiplayer\` and `Training\`
entirely, matching its `readme.txt:88`). **V.**

Two extra drop-in channels with no base-game edits:
- **Map names**: `system\<anything>.int` (ASCII) with `[<rsm_basename>]` + `ID_MENUNAME`
  etc. 19 community maps already do this. Get the section name exactly right — see the
  two shipped failures in §J.
- **New game modes** (needs OpenRVS, which is installed): `Mods\<Name>.game` with
  `[OpenRVS.OpenCustomMissionWidget]` + `GameType=`, `ParentGameType=`, `ButtonText=`,
  `HelpString=`, duplicated under `[SupplyDropSP.OpenCustomMissionWidget]`. Six shipped
  examples. Discovery is `..\Mods\` + `game` inside `OpenRVS.u`'s `LoadNewGameTypes`.

**The one thing a mod cannot supply drop-in:** its display name. `ModName`/`ModInfo`
come from `system\R6Mod.int`, which has no `.mod` override key. Either accept the raw
keyword (SupplyDrop ships that way) or append a section to `R6Mod.int` — **that file is
UTF-16LE with BOM and CRLF, and a UTF-8 write silently corrupts every existing string in
it.** Most `R6*.int` files are UTF-16LE; a GUI must sniff the BOM. **V.**

**Environment warning:** `system\openrvs.ini:9` sets `ForceStartMod=SupplyDrop` even
though `RavenShield.ini:63` says `CurrentMod=RavenShield`, and SupplyDrop swaps the pawn,
AI and player-controller classes (`Mods\SupplyDrop.mod:18-22`). This install is **not**
running stock classes. Any GUI must read `openrvs.ini` before assuming otherwise. **V.**

---

## The `.u` mechanism (why tier 4 works)

### U1. Header

All 21 `.u` in `<GAME>\system\` are magic `0x9E2A83C1`, **version 118, licensee 14**
(PS2 build is 123/22; Xbox is 118/21 — so `tcps2` was written for a *different* pair).
Summary: 36-byte fixed header + 16-byte GUID + generation count + one generation record
(export count, name count) + one trailing dword, name table at offset 68.

`R63rdWeapons.u`: `names=1152@0x44, exports=456@0x4b380, imports=412@0x4b09c`.
`R6Weapons.u`: `names=1403@0x44, exports=1601@0x353b2, imports=551@0x34081`.

**Uncompressed, and the recorded table offsets are valid** — the import table ends
exactly at `o_exports` and the export table ends exactly at EOF for all six packages
tested. This is the key difference from the PS2 build, where `tcps2/upackage.py:7-16`
documents that the cooker relaid the offsets into float data and the tables have to be
found by walking. **On PC you can seek.**

**No content hash anywhere.** The only integrity-ish fields are the GUID (static) and
the generation record's export/name **counts**, which an equal-length value edit does not
change. So an in-place patch is invisible to the loader. It will of course mismatch a
multiplayer server that checks package GUIDs against a clean install — **flag every
binary patch as SP-only in the GUI.** (Second sentence is **L**.)

### U2. Can `tcps2` / `rs3-ue2fixes` be pointed at these?

- `C:\Users\Tristan\Documents\GitHub\TomClancyPS2-ModStudio\tcps2\upackage.py` — **reusable
  with one change.** `compact_index`, `encode_compact`, `walk_properties`, `find_int_props`
  and the `INFO_INT32=0x22` / `INFO_FLOAT=0x24` constants are all correct for PC. The
  `Package` summary struct `"<IHHIIIIIII"` parses PC files unmodified. What must change is
  the *strategy*: `tables()` walks from the name table because the PS2 offsets are junk;
  on PC you should seek to `o_imports` / `o_exports` instead. My `upc.py` does exactly
  that and parses all six packages cleanly. One further gap: `walk_properties` does not
  recurse into struct payloads, and on RS3 PC every weapon tunable lives inside
  `m_stWeaponCaps` / `m_stAccuracyValues`, so recursion is mandatory (`props.deep`).
- `tcps2/uscode.py` — not needed for the levers in this dossier; every value found here is
  a `defaultproperty`, not bytecode.
- `tcps2/utexture.py` — **verified working unmodified** on RS3 PC `.utx` (reads
  `R6MenuTextures.utx` as v118/14, 73 Texture exports, correct names/formats/mips). It
  only decodes DXT1; the menu art is mostly DXT5 and RGBA8, so it needs ~30 lines of
  extra decoders. Proven this session by doing it.
- `C:\Users\Tristan\Documents\GitHub\rs3-ue2fixes` — a C++/premake5 project (`src`, `deps`,
  `premake5.lua`, `generate-buildfiles_vs22.bat`), not a package-reading library. Nothing
  to reuse for this task.

### U3. Where class defaults live, and how to find them

A `Class` export's serial range ends with its `defaultproperties` as an ordinary UE2
tagged property list terminated by the name index of `None` (index 0). Locate it by
scanning forward inside `[off, off+size)` for the first position whose property walk
terminates exactly at `off+size`. `props.py` does this; it resolved every class tried.

Struct-typed properties (`m_stWeaponCaps`, `m_stAccuracyValues`, `m_HUDTexturePos`) are
**nested tagged property lists**, so the walk recurses — that is where all the weapon
tuning actually is, and it is why a flat name-index search misses it.

Property encoding: `compactIndex(nameIndex)` `infoByte` `[size]` `value`, where
`info = type | sizeCode<<4 | array<<7`. Struct properties insert a `compactIndex(structType)`
after the info byte. Bools carry their value in bit 7 of the info byte with no payload.

### U4. Worked example, byte-for-byte

`<GAME>\system\R6Weapons.u`, bytes `0x19c1c`-`0x19c33`:

```
04 01 05 02 03 89 04 00 | 06 22 37 02 00 00 | 0d 22 04 00 00 00 | 07 24 00 00
                          ^^ ^^ ^^^^^^^^^^^   ^^ ^^ ^^^^^^^^^^^   ^^ ^^
```
- `06` = compact name index 6 = `m_iEnergy`; `22` = info byte (type 2 = int, sizeCode 2 = 4 bytes);
  `37 02 00 00` = **567** at offset `0x19c26`.
- `0d` = index 13 = `m_iPenetrationFactor`; `22`; `04 00 00 00` = 4 at `0x19c2c`.
- `07` = index 7 = `m_fKillStunTransfer`; `24` = float, 4 bytes.

Owner: class `ammo9mmParabellumNormalJHP`, export 1063, serial @0x19bc9.
**Writing `E7 03 00 00` at `0x19c26` sets 9mm JHP energy to 999. Same width, same tag,
no table shifts, no checksum.**

### U5. Which variables are `config` (ini-overridable without touching `.u`)

`cfg2.py` parses `UProperty` records — layout at v118/14 is
`[None] SuperField Next ArrayDim(u32) PropertyFlags(u32) Category [RepOffset(u16) if CPF_Net]`,
verified byte-for-byte against `m_iClipCapacity` (export @0x87c0 in `R6Weapons.u`, 15 bytes,
flags `0x21` = Edit|Net, category `R6Clip`, RepOffset 39). `CPF_Config=0x4000`,
`CPF_GlobalConfig=0x40000`.

**Self-validation:** the extractor independently reproduces the exact key sets of
`Sound.ini` (all 15 `R6NoiseMgr` keys), `R6EscortPilotGame.ini` (all 3),
`RavenShieldCampaign.ini` (`missions`, `m_OperativeClassName`, `m_OperativeBackupClassName`,
`LocalizationFile`) and `user.ini`'s `[R6Weapons.R6Reticule] m_Color`. Counts:

| Package | config vars |
|---|---|
| `Engine.u` | 260 (incl. all of `R6ServerInfo`, `R6GameOptions`, `R6Mod`, `R6MissionDescription`, `R6GameColors`, `R6MapList`) |
| `R6Game.u` | 22 (`R6NoiseMgr` 15, `R6EscortPilotGame` 3, `R6Campaign` 4) |
| `R6GameService.u` | 15 |
| `OpenRVS.u` | 15 |
| `GrenadeDropMod.u` | 6 |
| `R6Engine.u` | **5** (`R6PlayerController` only) |
| `R6Weapons.u` | **1** (`R6Reticule.m_color`) |
| `R6Abstract.u` | 1 |
| `Gameplay.u`, `R6Description.u` | **0** |

Full list in `cfgall.txt`.

**Definitive answer to the obvious hope:** `m_fTerroSkillMultiplier` and
`m_fRainbowSkillMultiplier` exist in `R6Engine.u` but are **NOT** `config`-flagged, and
neither are any of the eight `m_fSkill*` properties. There is no global AI-skill scalar
reachable from any ini. Per-template `.tpt` editing (§A) is the only text-level route,
and a `.u` patch is the only global one. **V.**

---

## Art

Full survey: 16 TGAs in `<GAME>\backgrounds\`, **all 640×480, 24 bpp, image type 2
(uncompressed truecolour), 921,644 bytes, bottom-left origin, with a TGA 2.0
`TRUEVISION-XFILE.` footer**. The brief's premise is confirmed for the base game.

Files: `Main_menu_01.tga` … `Main_menu_06.tga`, plus one `*_BG.tga` in each of
`CampNew\`, `CampResume\`, `CreateGame\`, `Credits\`, `ModSelector\`, `Multiplayer\`,
`Option\`, `OtherMission\`, `PracticeMission\`, and `Training\Training.tga`.

**Do not assume 24 bpp globally:** `Mods\IronWrath\Backgrounds\Main_menu_0*.tga` are
**32 bpp** (descriptor 0x08, 1,228,844 bytes). `Mods\AthenaSword\Backgrounds\` (14 files)
and `Mods\SupplyDrop\backgrounds\` (9 files) are 24 bpp — SupplyDrop spells it
`Main_Menu_01.tga`, capital M.

### Recommended GUI background
`D:\SteamLibrary\steamapps\common\Rainbow Six 3 Gold\backgrounds\Option\Option_BG.tga`

640×480, 24 bpp. Carries the full Raven Shield visual language — dark blue-grey grid
field, ghosted world map, top scan-line rail, rounded centre panel — with **zero baked-in
branding and zero photographic content**. `backgrounds\ModSelector\ModSelector_BG.tga` is
the same art with a small R6 plate composited top-left, if you want the logo pre-placed.
`backgrounds\Main_menu_01.tga` (wordmark + reticule vignette of a stacked entry team +
Ubi Soft / Red Storm logos) is a splash/about screen, not a working background.

### Recommended logo/emblem
**Blunt answer: there is no loose, full-size, true-alpha RAINBOW emblem or RAVEN SHIELD
wordmark anywhere in the game folder.** Every full-size wordmark is baked into an opaque
24-bit TGA or BMP over photographic art, and `textures\R6MenuTextures.utx` — which holds
the entire menu GUI chrome, 73 Texture objects — contains **no logo object at all**.

Best available, in order:

1. `D:\SteamLibrary\steamapps\common\Rainbow Six 3 Gold\Videos\~R6logo3a.bik` — 100×100,
   120 frames, the spinning RAINBOW globe-and-laurel emblem in silver/white on a
   **measured pure `#000000`** background (3,714–3,717 of 10,000 pixels exactly (0,0,0)
   on every frame sampled). Screen-blend it, or key `alpha = max(R,G,B)`. Clean cut-out
   because the emblem has no dark interior detail. Already extracted to
   `scratchpad\R6_emblem_100_black.png`, `..._keyed.png`, `..._200_black.png`.
2. `<GAME>\textures\R6Characters_T.utx` → texture object `R6armpatch` — same emblem,
   64×64 DXT1, also on pure black. Lower res, DXT-blocky.
3. `<GAME>\RavenShield.ico` — 32×32 + 16×16, 4 bpp, **genuine AND-mask transparency**
   (570/1024 transparent at 32×32). Red crosshair ring + black "RS". Fine as a window
   icon, useless at any larger size. (`RavenShieldEd.ico` is the same shape but **fully
   opaque** — 0 transparent pixels.)

Dead ends checked: `system\EdSplash.bmp` (640×374 palettised — wordmark sits on a busy
photo, not keyable); `system\Res\` (13 patch-launcher button BMPs only);
`system\EditorRes\` (40 UnrealEd toolbar icons); `armpatches\` (23 × 64×64 24-bpp clan
decals, **no R6 emblem** — the only corporate ones are `Ubisoft.tga` and `RedStorm.tga`);
all 131 `textures\*.utx` name tables searched for
`logo|rainbow|emblem|wordmark|title|splash|ubi|redstorm|banner|shield|insignia|crest|badge`
— every `LOGO`-ish hit is in-world level signage (`Bank_Shader.utx`, `Warehouse_TSM.utx`,
`Boiler_T.utx`, …).

### Sampled colours

Dominant colours, 8-way median cut, from the actual pixels:

| File | mean | top bands |
|---|---|---|
| `backgrounds\Main_menu_01.tga` | `#2E2C37` | `#131622` 18.8%, `#3B3A45` 18.1%, `#1D212D` 17.8%, `#8E8C93` 7.7% |
| `backgrounds\ModSelector\ModSelector_BG.tga` | `#30313B` | `#41434E` 16.5%, `#1F212C` 15.9%, `#292B36` 14.8%, `#696B75` 8.6% |
| `backgrounds\Option\Option_BG.tga` | `#343844` | `#4A4E5A` 15.3%, `#1C1F2B` 13.6%, `#373C49` 13.4%, `#727782` 10.0% |
| `backgrounds\Multiplayer\Multiplayer_BG.tga` | `#353946` | `#4B4F5B` 16.3%, `#2F3644` 13.9%, `#222633` 13.0% |
| `backgrounds\Credits\Credits_BG.tga` | `#333642` | `#4B4E5A` 15.3%, `#2C303C` 13.5%, `#1B1E2A` 13.2% |

Every backdrop is the same navy-charcoal family; means cluster in `#2B2934`–`#373A45`.

**Recommended palette** (each value is a sampled pixel, not an invention):

```
background    #131621   Main_menu_01 empty right field — darkest true game field
panel         #262831   ModSelector_BG panel interior
panel-raised  #2F313C   Option_BG panel interior
border/rail   #4E505C   ModSelector_BG panel top rail
accent        #84D3F7   R6MenuTextures.Gui_01 icon cyan — the game's interactive colour
accent-alt    #B00E27   Raven Shield banner red — branding/destructive only
text          #FFFFFF
text-muted    #8E8C93   the light band in Main_menu_01
```

The cyan/red split is genuine to the game: **cyan is interactive** (every menu icon atlas
in `R6MenuTextures.utx` is cyan-on-transparent), **red is branding only** (wordmark
banner `#B00E27`, Red Storm logo `#9C1C23`). Do not use red for hover states.

If you want authentic chrome rather than a flat scheme, `R6MenuTextures.utx` has the
three-slice bezel (`Gui_00L` / `GUI_00C_a00..a07` / `Gui_00R`, RGBA8 with true alpha),
the icon atlases (`Gui_01/02/03`, `Tab_Icon00`, DXT5), `Gui_BoxScroll`, `MouseCursor`,
and the UI typeface pages in `textures\R6Font.utx` (`Rainbow6_12pt` … `36pt`).
Extracting these needs the DXT5/DXT3/RGBA8 additions to `utexture.py` described in §U2 —
proven working this session, output in `scratchpad\gui\*.png`.

---

## Open questions / dead ends

**Not reachable — be blunt about these in the GUI:**

- **No wave / respawn system exists.** Grep of `R6Engine.u` and `R6Game.u` name tables for
  `respawn` / `wave` returns nothing usable — the one hit, `fWaveTime`, is unrelated.
  RVS terrorists spawn once per round. A "terrorist hunt wave mode" like the PS2 title's
  would have to be *written* as a new game class, not configured. **V by absence.**
- **No per-zone enemy count.** SP campaign terrorist counts and the mapping of spawn
  points to `.tpt` templates are embedded in `maps\*.rsm` (`R6Engine.u`:
  `m_szUsedTemplate`, `m_bUseTerroristTemplate`, `m_TerroristTemplate`, `C_NB_Template`).
  `maps\Oil_Refinery.ini` has no count key. Only MP (`NbTerro`) and custom missions
  (`CustomMissionNbTerro`) are exposed. Per-zone control needs an `.rsm` reader that does
  not exist yet.
- **No friendly-fire toggle in single player.** `FriendlyFire` exists only on
  `R6ServerInfo`.
- **No global AI skill multiplier from ini.** Settled in §U5.
- **No numeric operative stats.** `R6Operatives.int` is prose + `ID_HEIGHT=186cm` /
  `ID_WEIGHT=81kg` strings. There is no aim/health/stealth field. It is not a lever.
- **`.int` files do not gate content.** Only 10 of 58 have a `[Public]` section and all
  ten register renderers/audio/commandlets, never missions, modes, weapons or operatives.
  Every `R6*.int` is a pure localisation string table. Gating lives in `.ini` and `.mod`.
- **No numeric data in `R6Weapons.int` / `R6Ammo.int` / `R6Armor.int` / `R6Gadgets.int`.**
  Display names and descriptions only — `R6Ammo.int:2-3` *describes* penetration in prose
  and encodes nothing.
- **God mode is not exposed.** `GodMode=True` at `RavenShield.ini:203` and `:295` is
  UnrealEd only. `InGodMode` exists in `R6Engine.u` with no ini key. The only ini-level
  cheat door is `openrvs.ini:13 NewCheatManagerClass=`, and it needs a `.u` to supply the
  class.
- **You cannot add a property to a class default in place.** Only overwrite existing ones
  at equal width, or rename a tag to a same-width sibling (§H).
- **`m_WeaponClasses` (the per-weapon variant list) is length-prefixed strings** — editing
  it resizes the package. Subtract with `Restricted*` instead of editing it.

**Genuinely open — worth one test each before shipping a GUI feature:**

1. **`Restricted*` ini syntax (§D).** Types verified (string vs class arrays), value format
   untested. This is the difference between a working "kit lock" feature and a no-op.
2. **Do `RGM_DefendMode` / `RGM_ReconMode` actually run?** The classes exist. Add them to a
   generated `.mod`'s `m_szGameTypes` and see. Highest-value cut-content restore available.
3. **`Sound.ini` `m_Terro` / `m_Hostage` field order.** Prone reads louder than standing;
   either the struct order differs from `m_Rainbow` or it is deliberate. Do not ship
   posture sliders until resolved.
4. **Does a `.u` binary patch survive MP?** Packages carry a GUID but no content hash, so
   the loader will not object; a server doing a clean-install comparison might. Treat
   binary patches as SP-only until tested.
5. **`m_szModInfo` in a `.mod`** — `Engine.u` has the identifier but no shipped `.mod` sets
   it. If it works, a generated mod can supply its own subtitle without touching the
   UTF-16 `R6Mod.int`. There is no evidence of a matching `m_szModName`.
6. **Is `m_ADamagePercent` truly display-only?** Inferred, not proven. If wrong, the whole
   §I sync argument inverts.
7. **This install is not stock.** `openrvs.ini:9` forces `SupplyDrop`, which swaps pawn,
   AI and controller classes. Every in-game test above must be run with that accounted for.

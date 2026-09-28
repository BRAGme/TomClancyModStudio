# Rainbow Six 3: Lockdown (PC) — mod-lever dossier

Game root: `E:\SteamLibrary\steamapps\common\Rainbow Six Lockdown`
All paths below are relative to that root unless absolute. Everything was read; nothing in the game folder was written.

> ### Read this before designing the GUI
>
> **The brief's premise is wrong: Lockdown ships a real mod-folder system.** `lockdown.exe` contains a complete `RSModsMgr` — a `mods/` root scanned with `\*.*`, a per-mod manifest `ModsCont.txt` with the fields `NAME`, `AUTHOR`, `SUPPORT`, `VERSION`, `MULTIPLAYER`, `ICON`, `CLIENT-SIDE`, `SERVER-SIDE`, an active-mod list file `ModsSet.txt` written by `RSModsMgr::SaveModsSettings` under the header `// MODS SETTINGS - LIST OF MODS ACTIVE ON THIS SYSTEM`, a loader `RSModsMgr::LoadSettings` with the error `"RSModsMgr::LoadSettings: Could not find specified mod settings file "`, a command-line switch **`-modset`**, and a full multiplayer mod-negotiation UI in the string table (`Available Mods`, `Add Mod`, `Remove Mod`, `kMainMenu_Mods`, `"THE SERVER HAS A MOD THAT YOU DON'T HAVE"`). All of it verified by me directly in `lockdown.exe` (`mods/` at file offset `0x50e694`, `ModsCont.txt` at `0x50e518`, `ModsSet.txt` at `0x50e478`, `-modset` at `0x511fa8`).
>
> No `mods\` directory ships with the install, so the format of a mod folder's *contents* is unproven — but `readme.txt:151` confirms the game detects modified equipment ("modifying or adding new equipment (.itm, .gun, .prj files) will report your game server is using modified data"). **Resolve this before committing to in-place editing.** A GUI that writes `mods\MyMod\` + `ModsSet.txt` would be non-destructive and MP-aware; one that edits `data\` in place is neither.

**Scope note on counts.** `data\equip\` has 108 files (86 `.gun` + 1 `.GUN` + 13 `.prj` + 7 `.itm` + `CmbtModl.xml`). `data\kits\` has 79 `.wsf` + 1 `.waf`. `data\character\` is 465 `.chr` + 71 `.skl` **recursively** (the "79" in the brief is the top level only). `data\actor\` is 160 `.cms` + 39 `.cgs` + 1 `.nsf`. `data\mission\` is 101 `.mis` + 101 `.rsc` + 101 `.script` + 48 `.esf` + 4 `.acm` + `campaignfile.xml`.

**All the gameplay data is loose, unpacked, tab-indented pseudo-XML with CRLF.** It is *not* valid XML — attributes repeat (`data\actor\names.nsf` has nine `name=` attributes on one element) and numbers are used as element names (`<60>…</60>` in `.cms`). A GUI must use a tolerant tag-soup reader/writer, not `ElementTree`, or it will destroy files on save.

---

## Levers

| name | file glob | tag / attribute | stock value | effect | confidence |
|---|---|---|---|---|---|
| **Enemy weapon damage** | `data\equip\e_*.gun` (45 files) | `<WeaponData damageMin/damageMax>` | `2` / `4` on every `e_*` gun | Damage enemies do to you. Player-side copies of the same guns are `10`/`12`. This is the single biggest difficulty dial in the game. | **High** — read in `e_M8Compact.gun`, `e_MEU45.gun`, and tabulated across all 45 |
| **Player weapon damage** | `data\equip\*.gun` (42 non-`e_` files) | `<WeaponData damageMin/damageMax>` | rifle `10`/`12`, pistol `9`/`11`, shotgun `4`/`6`, W2000 `14`/`16`, RPG `1`/`3` | Per-weapon lethality. Present once per attachment variant (`Default`, `RedDot`, `Scope`, `HiCapMag`, `Suppressor`), so a GUI must write all variants or offer per-variant fields. | **High** |
| **Enemy AI marksmanship (weapon side)** | `data\equip\e_*.gun` | `<Common><AIAccuracy><Accuracy BaseAccuracy Recoil>` | `BaseAccuracy="15" Recoil="-5"` — **identical in 42 of 45 `e_*` files** | One value, 42 files. Raise to 50 and every enemy shoots like a Rainbow operator. Perfect "global enemy skill" slider. | **High** — grouped all distinct `<AIAccuracy>` blocks; 42 are byte-identical |
| **Enemy AI movement penalty** | `data\equip\e_*.gun` | `<AIAccuracy><Movement ShooterShuffle/ShooterWalk/ShooterRun>` | `-10 / -20 / -30` on the same 42 files | Accuracy penalty while the shooter moves. | **High** |
| **Enemy AI fire-mode penalty** | `data\equip\e_*.gun` | `<AIAccuracy><MethodOfFire Overhead/Wild>` | `-30 / -40` | Penalty for blind/overhead and suppressive fire. | **High** |
| **Ammo carried** | `data\equip\*.gun` | `<ReloadData maxAmmo>` | player `250`–`999`, **every `e_*` gun `999`** | Reserve rounds. | **High** |
| **Magazine size** | `data\equip\*.gun` | `<ReloadData clipSize>` | e.g. M8 Compact `30`, HiCapMag variant `100`; MEU45 `7`, HiCapMag `14` | Rounds per magazine, per attachment variant. | **High** |
| **Rate of fire / fire modes** | `data\equip\*.gun` | `<RateOfFire><SingleShot|Burst|FullAuto available roundsPerMinute>` | M8: SS `1`@`300`, Burst `0`@`0`, FA `1`@`750` | `available="0→1"` unlocks a fire mode the weapon does not ship with (e.g. give the MEU45 full-auto). Range across all guns 0–1200 rpm. | **High** |
| **Recoil (player)** | `data\equip\*.gun` | `<PlayerAccuracy><Recoil Attack/Value/Decay>` | M8 `50 / 12 / 200`; MEU45 `100 / 18 / 150`; W2000 Value `35` | Value = kick magnitude, Decay = recovery rate. Range of `Value` across guns 0–35. | **High** |
| **Aim cone floor/ceiling** | `data\equip\*.gun` | `<PlayerAccuracy><Accuracy GAmin GAmax>` | M8 `2.000`/`50.000`; MEU45 `5`/`60`; PSG1 `1`/`100`; **every `e_*` gun `1`/`100`** | `GAmin` is the best-case cone, `GAmax` the worst. Set `GAmax = GAmin` for a laser. | **High** |
| **Stance / movement sway** | `data\equip\*.gun` | `<PlayerAccuracy><Standing|Crouching><Still|Walk|Run Attack/Value/Decay>` | M8 standing Still `0/1/250`, Walk `0/4/250`, Run `0/35/500`; crouching is lower | 24 numbers per attachment variant. Zero the `Value`s for arcade handling. | **High** |
| **Turn / lean sway** | `data\equip\*.gun` | `<PlayerAccuracy><Turning><Turning|Leaning>` | M8 Turning `0/20/250`, Leaning `100/2/250` | Per-weapon; the **global** counterpart is `CmbtModl.xml`. | **High** |
| **Effective range** | `data\equip\*.gun` | `<WeaponData range killRange>` | rifle `150`, pistol/SMG/LMG `100`, shotgun `50`, W2000 `300`, `e_AS12`/`e_M73E` `1000` | Two `e_*` guns have `range="1000"` — almost certainly a data bug (the rest are `100`). Flagged below. | **High** |
| **Shotgun spread / pellets** | `data\equip\*.gun` | `<WeaponData spreadAngle pelletCount>` | `SW12` `0.2`/`6`, `MG7` `0.3`/`4`, `M1S90` `0.15`/`8` | `spreadAngle` is radians on `e_*` files (`0.174533` = 10°) but degrees-looking small decimals on player files. Mixed units — verify before shipping a slider. | Medium |
| **Blast force (ragdoll shove)** | `data\equip\*.gun` | `<WeaponData blastForce>` | `4` typical, range 1–6.5 | | High |
| **Zoom levels** | `data\equip\*.gun` | `<RenderData><Zoom numLevels level0 modifier0 level1 modifier1>` | M8 Default `2 / 1 / 1 / 2 / 0.75`; Scope variant `level1="4"`; W2000 SniperScope up to `30` | `modifierN` scales the aim cone at that zoom. `level1="30"` exists — max magnification on disc. | High |
| **Which weapons the player may carry** | `data\equip\*.gun` | `<Default usableBy>` | `rainbow` (14), `mercenary` (14), `all` (14), `enemy` (45) | Change an enemy-only weapon to `all` to give it to the player. Present per attachment variant. | **High** |
| **Weapon availability per game mode** | `data\equip\*.gun`, `*.prj`, `*.itm` | `<UsableInGameModes spCampaign spTerroristHunt spInfiltrator spLoneRush spSniper mpTeamAdversarial mpRivalry mpRetrieval mpOneOnOne mpCoOpMission mpTerroristHunt>` | mostly all `1`; **`c4.itm` and `claymore.itm` are `0` for every SP mode** | Flipping `c4.itm`/`claymore.itm` SP flags to `1` is a genuine "unlock cut kit" lever — the items exist, are fully statted, and are MP-only on disc. | **High** — read `c4.itm` and `claymore.itm` in full |
| **Weapon availability per MP class** | `data\equip\*.gun` etc. | `<UsableByMPClasses clsAssault clsSniper clsRecon clsDemo>` | M8 Default `1/0/1/0` | Per attachment variant — e.g. only `clsRecon` may take the M8 Scope. | High |
| **UI stat bars** | `data\equip\*.gun` | `<UIData damage accuracy recoil maneuverability sights>` | 0–2 integers (M8 `1/1/2/2/0`) | Cosmetic bars in the outfitting screen only; they do **not** drive ballistics. | High |
| **Weapon display name & blurb** | `data\shell\<lang>\strings.txt` | `"WPN_M8_Compact"  "M8 Compact"` | line 5 of `data\shell\english\strings.txt` | The `.gun`'s `<Common name>` and `<UIData descriptionTag>` are lookup keys into this file. `strings.txt` is referenced by name inside `lockdown.exe`, so it is loaded at runtime. 329 lines, 6 sections. | **High** |
| **Grenade / projectile lethality** | `data\equip\*.prj` (13) | `<ExplosionData killRange maxRange blastForce baseDamageMin baseDamageMax isStunOnly isDirectional>` | `frag.prj`: `2.0 / 7.0 / 200.0 / 7 / 15`; `flashbang.prj`: `5.0 / 8.0 / 0.0 / 0 / 1`, `isStunOnly="1"` | | **High** |
| **Grenades carried** | `data\equip\*.prj`, `*.itm` | `<GeneralSettings count>` | `frag.prj` `3`, `flashbang.prj` `5`, `c4.itm` `3`, `claymore.itm` `3` | Straight "how many do I start with". | **High** |
| **Fuse timer / impact detonation** | `data\equip\*.prj` | `<GeneralSettings detonationDelay detonateOnImpact velocity>` | `2.000000` / `0` / `20.000000` | | **High** |
| **Virus-bomb behaviour** | `data\equip\*.prj` | `<VirusBombData killRadius effectRadius warningRadius dissipationTime spreadTime>` | all `0` in `frag.prj`/`flashbang.prj` | Non-zero only on `virus_grenade.prj` (not read this session — flagged as an open question). | Medium |
| **Claymore blast shape** | `data\equip\claymore.itm` | `<ExplosionData isDirectional blastPlateWidth blastPlateHeight horizSpreadAngle vertSpreadAngle>` | `1 / 0.25 / 1.0 / 1.221730 / 0.349066` | Radians: 70° horizontal, 20° vertical cone. Only directional explosive on disc. | **High** |
| **Global player handling (turn & lean sway)** | `data\equip\CmbtModl.xml` | `<GlobalData><Turning><Turning Attack/Value/Decay>` | `0.000 / 60.000 / 200.000` | Applies to everyone, all weapons. See "Global combat model". | **High** |
| **Global wound penalties** | `data\equip\CmbtModl.xml` | `<GlobalData><Wounded><Head|Chest|LeftArm|RightArm|LeftLeg|RightLeg>` | every part `Attack=100 Value=0 Decay=200` | **Shipped inert.** Raising `Value` makes wounds degrade aim. See below. | **High** |
| **Enemy kit contents** | `data\kits\*.wsf` (79) | `<Primary|Secondary|Item1|Item2><Firearm file chance>` / `<ThrownItem …>` / `<HandHeldItem …>` | `Mercenary_1_Auto_Rifle.wsf` → `e_A2Para.gun @ 100` | Free-form: any `.gun`/`.prj`/`.itm` filename, any slot. `chance` sums to 100 across entries in a slot. | **High** |
| **Enemy kit weapon roulette** | `data\kits\*.wsf` | multiple `<Firearm>` in one slot with `chance` | `mercenary_2_generic_sniper.wsf` = 4× `@25`; `terrorist_3_generic_sniper.wsf` = 5× `@20`; `Mercenary_1_Grenade_Smoke.wsf` = 2× `@50` | Proof that multi-entry weighted slots work. A GUI can add entries freely. | **High** |
| **Rainbow operator loadouts** | `data\kits\r_*_default.wsf` (14) | same | `r_chavez_default.wsf` = `m36c.gun`, `m9.gun`, `frag.prj`, `flashbang.prj` | Per-operator starting kit. | **High** |
| **Enemy AI skill (character side)** | `data\actor\*.cgs` (39) | `<AICGSData><Accuracy AISkillLevel Darkness>` | terrorist 32/35/40, militia 27/29/33, mercenary 40/44/46, `default.cgs` 50, Rainbow ops 100 | 0–100. Combines with the weapon's `BaseAccuracy`. | **High** |
| **Enemy hitpoints per body part** | `data\actor\*.cgs` | `<DamageModel><Hitpoints head chest leftarm rightarm leftleg rightleg>` | Chavez SP `8/20/20/20/20/20`; `_coop` variants `6/8/9/9/9/9` | The `_coop` files are a stock, shipped "hardcore" preset — ~2.5× squishier Rainbow. | **High** |
| **Wound-induced accuracy loss (per character)** | `data\actor\*.cgs` | `<AICGSData><Wounds Arm Chest Head Leg>` | Chavez `-10 / -5 / -15 / -5`; range across files `-31…0` | | **High** |
| **AI team accuracy / difficulty** | `data\mission\*.acm` (4) | `<AITeamAccuracyData><Difficulty Normal Challenge>` and `<Combat …>` | `badguys.acm` `Normal="29" Challenge="50"`, `ForcedMiss="-100"`, `PointBlank="100"` | **The real difficulty file.** `rainbow.acm` has `ForcedMiss="1"` — your teammates never deliberately miss. Four files, thirteen numbers. | **High** |
| **Which AI combat model a spawn uses** | `data\mission\*.mis` | `AICombatModelFile="…"` | `badguys.acm` ×1100, `long_distance.acm` ×18, `rainbow.acm` ×4 | | **High** |
| **Per-spawn difficulty gate** | `data\mission\*.mis` | `Difficulty="2"` / `"3"` on `<ActorSpawnData>` | `2` ×178, `3` ×2467 | Spawns are filtered by the chosen difficulty — this is where enemy *count* effectively changes. | **High** |
| **Enemy pool size (literal enemy count)** | `data\mission\*.mis` | `<Pool Size="…" Name="…" ModelFile GameFile WeaponFile>` | `<Pool Size="9" Name="Pistol Enemies" …>` in `m01_sec_01.mis`; `Size` appears 55 times | Direct integer enemy count per named pool. | **High** |
| **Enemy roster size (literal, per mission)** | `data\mission\*.mis` | count of `<Actor IgorId=…>` inside `<Units>` | campaign sections 26–59; **every one of the 32 `_th_*` maps is exactly 30** | Deleting or duplicating `<Actor>` blocks is the direct "more/fewer enemies" edit. Each carries its own `<ActorPositions><Position Pos Facing/>`. | **High** |
| **Wave size and respawn budget** | `data\mission\*.mis` (21 files) | `<SpawnArea … SpawnCount TeamSize …>` | `SpawnCount="2" TeamSize="2"` in `m01_sec_01.mis` L956 | `SpawnCount` = total bodies the area may emit; `TeamSize` = concurrent alive. The literal wave system. | **High** |
| **Enemy model / stats / kit binding** | `data\mission\*.mis` | `<ActorSpawnData ModelFile GameFile WeaponFile …>` (2956 each) | `ModelFile="e_militia_01.cms" GameFile="militia-01.cgs" WeaponFile="militia_1_semi-auto_rifle.wsf"` | The one element that wires `.cms` + `.cgs` + `.wsf` together. Re-kitting an entire mission is a find/replace on `WeaponFile`. | **High** |
| **Enemy appearance roulette** | `data\actor\*.cms` | numeric weight elements, e.g. `<20>…</20>` inside `<Body>` | `e_terr_random.cms` body weights `20/10/15/20/15/20` (=100) | Cosmetic only (models, head morphs, texture swaps, attachments). | **High** |
| **Difficulty (player-facing default)** | `data\options.xml` | `<game difficulty="1">` | `1` | | **High** |
| **HUD theme** | `data\options.xml` | `<game hudTheme="0">` | `0` | Rainbow vs Mercenary HUD skin (`hud01..04` vs `hud_merc01..04` textures). | Medium |
| **HUD / assist toggles** | `data\options.xml` | `<game enableFirstPersonWeapon displayReticule showDeadBodies alwaysRun autoReloading enableblood enableGunfireCameraShake displayHints spAlternateMovementSpeed>` | `true/true/true/false/true/true/true/true/false` | `displayReticule="false"` = crosshair off. `enableGunfireCameraShake` and `displayHints` are the two most mod-worthy. | **High** |
| **Default rate of fire** | `data\options.xml` | `<game defaultROF="2">` | `2` | | High |
| **HUD theme colours** | `data\options.xml` | `<game hudThemeBG0..5 hudThemeFG0..5>` | 12 RGBA colour strings | Direct HUD recolouring without touching any texture. Strong, cheap lever. | **High** |
| **Developer instrumentation** | `data\options.xml` | `<debug showPlayerPosition showFrameRate showGameCounters showSceneCounter showUICounter showOnlyHighGameCounters showGameCountersAsPercent showAllGameCounters showRendererCounters updateGravy enableScriptLog enableGameLog enableNetworkLog>` | all `false` except `enableGameLog="true"` | **Ships live and is parsed by retail** — the 13 names are a byte-for-byte match for the exe's attribute table at file `0x51977c`–`0x519868`. `showFrameRate` and `showPlayerPosition` are the useful ones. | **High** |
| **Mouse / look feel** | `data\options.xml` | `<input useMouseInput mouseLookReverseY mouseLookSensitivity lookHorizontalSensitivity lookVerticalSensitivity normalThreshold fastThreshold mouseRadiansPerPixel sniperZoomMultiplier>` | `true/false/5/1/1/0.1/0.6/0.008727/5` | `mouseRadiansPerPixel` is the raw-sensitivity knob; `sniperZoomMultiplier="5"` is a gameplay lever. | **High** |
| **Video / audio settings** | `data\options.xml` | `<graphics …>`, `<video …>`, `<audio …>` | e.g. `useHDR="true"`, `mipMapLODBias="-0.5"`, `maxBulletHoles="100"`, `eaxEnabled="true"` | Not gameplay. `maxBulletHoles` is the one worth exposing. | **High** |
| **Key bindings** | `data\keys.xml` | 44 `<…  key=… key2=…>` entries | e.g. `fire_weapon` `key_left_mouse`, `quick_save` `key_f5` | Only 6 actions have a `key2`. Human-readable labels live in `data\shell\english\strings.txt` lines 111–298. **Two actions exist in the engine and in `strings.txt` but are absent from `keys.xml`: `toggle_scoreboard` and `holding_breath` ("Steady Sniper Rifle") — adding them is a genuine unlock.** | **High** |
| **Menu / loading art** | `data\shell\art\*.rsb` (65) | binary RSB v9/v10 | see "Art" | | **High** |

### What the shipped readme says about modding

`readme.txt` in the game root, §3.1 (line 151): *"modifying or adding new equipment (.itm, .gun, .prj files) will report your game server is using modified data, and prevent you from creating a ranked server."* So Ubisoft anticipated exactly the edits in the table above, and the consequence is confined to ranked MP. §3.4 and §4.1/4.2 tell players to hand-edit `gameSyncTimeout`, `levelTextureDetail`, `characterTextureDetail` and `UseWinMM` in `options.xml` — note the readme says `data/save/options.xml` while this install has it at `data\options.xml`. §4.4 is the `~`/Esc unmappable-keys note. **No command-line switches, no console and no dev mode are documented.**

`artifacts_readme.txt` is NVIDIA RTX Remix boilerplate. `steam_appid.txt` is `15000`. `camera_proxy.ini` is your own RTX Remix FFP camera-proxy config for `RS_Lockdown_FFP.asi` (currently parked in `_asi_disabled\`) — not game data.

### Two probable data bugs worth surfacing in a GUI

* `data\equip\rpg7.GUN` line 25 and `rpg7sniper.gun` spell the attribute **`descriptionTasg`** instead of `descriptionTag` (`descriptionTasg = "WPN_RPG_DESC"`). The RPG therefore has no in-game description. A one-character fix.
* `data\equip\e_AS12.gun` and `e_M73E.gun` carry `range="1000"` where every other `e_*` gun is `range="100"`, together with `GAmin="10.000"` and `Recoil Value="0.000"` — two enemy weapons with ten times the reach of the rest.
* `data\kits\RPG_Virus.wsf` references `rpg7virus.gun`, **which does not exist** anywhere in `data\equip\`. Broken kit.

---

## Global combat model

`data\equip\CmbtModl.xml` is 38 lines, complete, and is the whole file:

```
<CombatModelFile>
	<GlobalData>
		<Turning>
			<Turning  Attack = "0.000"   Value = "60.000"  Decay = "200.000"/>
			<Leaning  Attack = "100.000" Value = "2.000"   Decay = "500.000"/>
		</Turning>
		<Wounded>
			<Head      Attack = "100.000" Value = "0.000"   Decay = "200.000"/>
			<Chest     Attack = "100.000" Value = "0.000"   Decay = "200.000"/>
			<LeftArm   Attack = "100.000" Value = "0.000"   Decay = "200.000"/>
			<RightArm  Attack = "100.000" Value = "0.000"   Decay = "200.000"/>
			<LeftLeg   Attack = "100.000" Value = "0.000"   Decay = "200.000"/>
			<RightLeg  Attack = "100.000" Value = "0.000"   Decay = "200.000"/>
			<Damage    Attack = "0.000"   Value = "100.000" Decay = "0.000"/>
		</Wounded>
	</GlobalData>
</CombatModelFile>
```

Structure: two sections only, `Turning` and `Wounded`. Every leaf is the same `Attack / Value / Decay` triple used throughout `<PlayerAccuracy>` in the `.gun` files, which is what identifies it as the same aim-cone contribution system: `Value` is how much aim-cone the condition adds, `Attack` is how fast it ramps in, `Decay` how fast it bleeds off.

**The interesting part is that `<Wounded>` ships inert.** All six body parts are `Value="0"` — being shot in the arm costs you nothing globally. Only `<Damage>` is non-zero (`Value="100"`). So the honest read is:

* `CmbtModl.xml` is a *global*, weapon-independent baseline: its `<Turning Value="60">` sits alongside each weapon's own `<Turning Value="20">`.
* It is **not** the game's difficulty file. The difficulty file is `data\mission\*.acm` (4 files) plus `data\actor\*.cgs` (39 files). `CmbtModl.xml` is a good global *player-handling* lever ("realistic sway" / "arcade") and a good *"enable wound penalties"* toggle, because the six zeros are a ready-made feature switch nobody turned on.

**Caveat I could not resolve:** I did not verify at runtime that the `<Wounded>` values are read at all. They may be dead code. Label any GUI switch built on them as experimental.

### Complete `.itm` and `.prj` table (all 20 files)

`.itm` is `<HandHeldItemFile>` (version 1.2/1.3), `.prj` is `<ProjectileFile>` (version 3.1). Both share `<GeneralSettings>`, `<ExplosionData>`, `<UIData>`; `.prj` adds `<VirusBombData>`, `.itm` adds `exclusive` and `simModelSet`.

| file | class | count | usableBy | SP modes | killRange | maxRange | blastForce | dmg min–max | notes |
|---|---|---|---|---|---|---|---|---|---|
| `frag.prj` | frag | 3 | all | all 1 | 2.0 | 7.0 | 200 | 7–15 | |
| `flashbang.prj` | flash | 5 | Rainbow | all 1 | 5.0 | 8.0 | 0 | 0–1 | `isStunOnly="1"` |
| `Smoke.prj` | smoke | 5 | Rainbow | all 1 | 0 | 0 | 0 | 0–0 | |
| `WhitePh.prj` | phosphorous | 3 | Rainbow | all 1 | 4.0 | 7.0 | 75 | 7–15 | |
| `breach_hammer.itm` | ram | 1 | *(no attr)* | all 1 | 0 | 0 | 0 | 0–0 | `exclusive="1"` — only item with it |
| `breaching_charge.itm` | breaching_charge | 3 | rainbow | all 1 | 2.0 | 7.0 | 150 | 2–10 | directional, 15° horiz |
| `high_frag.prj` | frag | 3 | enemy | **all 0** | 2.0 | 7.0 | 200 | 7–15 | |
| `low_frag.prj` | frag | 3 | enemy | **all 0** | 2.0 | 7.0 | 200 | 7–15 | identical to `high_frag` — the names are a lie |
| `Stun.prj` | stun | 5 | enemy | **all 0** | 3.0 | 3.0 | 0 | 0–1 | |
| `virus_grenade.prj` | virus | 3 | mercenary | **all 0** | 0 | 0 | 0 | 0–0 | `VirusBombData killRadius="3" effectRadius="5" warningRadius="9" dissipationTime="4" spreadTime="3"` — **the only non-zero `<VirusBombData>` on disc** |
| `SmokeMulti.prj` | smoke | 5 | Mercenary | **all 0** | 0 | 0 | 0 | 0–0 | |
| `rpg7.prj` | not grenade | 1 | enemy | **all 0** | 0 | 7.0 | 150 | 3–8 | |
| `rpg7_sniper.prj` | not grenade | 1 | enemy | **all 0** | 0 | 7.0 | 150 | 3–8 | |
| `40mmGLgrenade.prj` | frag | 1 | enemy | **all 0** | 2.0 | 8.0 | 175 | 4–10 | |
| `20mmGLgrenade.prj` | not grenade | 1 | enemy | **all 0** | 2.0 | 7.0 | 150 | 4–7 | |
| `c4.itm` | c4 | 3 | rainbow | **all 0** | 4.0 | 7.0 | 175 | 9–17 | |
| `claymore.itm` | claymore | 3 | mercenary | **all 0** | 4.0 | 7.0 | 175 | 9–17 | directional, 70°×20° |
| `laser_tripmine.itm` | laser_tripmine | 2 | mercenary | **all 0** | 3.0 | 6.0 | 80 | 6–12 | |
| `lock_fuser.itm` | lock_fuser | 3 | mercenary | **all 0** | 2.0 | 7.0 | 150 | 2–10 | |
| `proximity_flash_mine.itm` | proximity_mine | 3 | rainbow | **all 0** | 3.0 | 6.0 | 0 | 0–1 | `isStunOnly="1"` |

**Six items are fully statted, MP-only, and in no kit** — `c4`, `claymore`, `laser_tripmine`, `lock_fuser`, `proximity_flash_mine`, and `SmokeMulti.prj`. Flipping their five `sp*` flags to `1` and adding them to an `.wsf` is the cleanest "unlock cut equipment" feature in the game. (`lock_fuser.itm` is also referenced by name inside `lockdown.exe`, so the class is live code.)

**`high_frag.prj` and `low_frag.prj` are byte-identical in every stat** (`killRange 2.0`, `maxRange 7.0`, `blastForce 200`, `baseDamageMin 7`, `baseDamageMax 15`) despite being used as the "high-yield" and "low-yield" enemy grenades in `Terrorist_3_Grenade_HY.wsf` / `_LY.wsf` and `Mercenary_*_Grenade.wsf`. Either a copy-paste bug or a deliberately abandoned distinction — and an easy, high-visibility mod.

---

## Characters & actors

**`data\actor\` is flat — no subfolders.** 160 `.cms` + 39 `.cgs` + `names.nsf`. All three are TEXT.

* **`.cgs` = `<CharacterGameSetFile>`, the AI stats file, and there are only 39 of them because they are archetypes, not per-model.** Complete tag set: `VersionNumber, Type, Name, AICGSData, Accuracy, Wounds, DamageModel, Hitpoints, Dossier, Class, Nationality, Male`. Complete attribute set: `first/last`; `AISkillLevel/Darkness`; `Arm/Chest/Head/Leg`; `head/chest/leftarm/rightarm/leftleg/rightleg` (note the case split — capitalised on `<Wounds>`, lowercase on `<Hitpoints>`). `data\actor\ding_chavez.cgs` in full:

```xml
<CharacterGameSetFile>
	<VersionNumber>1.000000</VersionNumber>
	<Type>Rainbow</Type>
	<Name first = "DING" last = "CHAVEZ"/>
	<AICGSData>
		<Accuracy AISkillLevel = "100" Darkness = "0"/>
		<Wounds Arm = "-10" Chest = "-5" Head = "-15" Leg = "-5"/>
	</AICGSData>
	<DamageModel>
		<Hitpoints head = "6" chest = "8" leftarm = "9" rightarm = "9" leftleg = "9" rightleg = "9"/>
	</DamageModel>
	<Dossier>
		<Class>command</Class>
		<Nationality>american</Nationality>
		<Male>TRUE</Male>
	</Dossier>
</CharacterGameSetFile>
```

  Stock `AISkillLevel` by archetype: terrorist-01/02/03 = 32/35/40, militia-01/02/03 = 27/29/33, mercenary-01/02/03 = 40/44/46, `default.cgs` = 50, Rainbow operators = 100. Outliers: `deiter_weber` 70, `gign_sniper` 99, `gign_operative` 60, `paris_cell_leader` 30, `ampolice_m02` 11 (the lowest in the game). `<Type>` values: Rainbow (21), Terrorist (6), Mercenary (6), Mob (3), Hostage (3).

  **The `_coop` variants are a shipped hardcore preset.** Nine operators have a `<name>.cgs` and a `<name>_coop.cgs`; the SP files are `head=8 chest=20 limbs=20` and every `_coop` file is `head=6 chest=8 limbs=9`, with `AISkillLevel` unchanged at 100. Co-op Rainbow are ~2.5× squishier. Copying those numbers over the SP files is a one-click "realistic damage" mod.

* **`.cms` = `<CharacterModelSetFile>`, cosmetic only.** Tags: `Head, Body, ModelName, FPModelName, Morph, TextureReplaceEntry, AttachmentEntry, AttachmentName` plus **numeric elements used as percentage weights** — `<0> <10> <15> <20> <23> <24> <25> <30> <33> <34> <35> <40> <45> <50> <52> <54> <60> <65> <67> <70> <80> <85> <90> <100>`. In `e_terr_random.cms` the `<Body>` weights are `20/10/15/20/15/20`, summing to 100. Attachment slots seen: `head_attachment`, `chest_attachment`, `stomach_attachment`. Attributes: `maxTarget/midTarget/minTarget/rangeMax/rangeMin` on `<Morph>`, `key/value/percentage` on `<TextureReplaceEntry>`.

* **`names.nsf` = `<NameSetFile>`** — nine first names and nine surnames, all as repeated `name=` attributes on two elements. This is the file that proves a strict XML parser is unusable.

**`data\character\` = 465 `.chr` + 71 `.skl`, and both are binary — a dead end for tuning.**

| folder | contents |
|---|---|
| `character\` (root) | 4 `.chr` (`morph_head_a..d`) + all 71 `.skl` |
| `character\allied\` | 378 `.chr` — **misnamed.** 293 are `fpw_*.chr` first-person weapon viewmodels; the rest are 35 `r_*`, 22 `npc_*`, ~24 `<operator>_leftarm.chr`/`_rightarm.chr` pairs, plus `cloth`, `clothhi`, `flag`, `fastrope`, `rope`, `sensor*` |
| `character\enemy\` | 70 `.chr` — enemy body meshes (`e_terr_*`, `e_terr_elite_*`, `e_samerc_*`, `e_morocmilit_*`, `e_merccom`, `e_mercdisg`) plus named bosses: `billings, burke, devereaux, grivenko, harrell, kaltenbach, kreiger, meredith, vanderwaal, wells` |
| `character\customizations\` | exactly 12 — a 2×2×3 grid, `{e,r}_custom[_f]_01_{small,medium,large}_a.chr`: enemy/rainbow × male/female × three body sizes |
| `character\ui\` | 1 (`ui_character.chr`) |

`.chr` opens with float `6.0` then length-prefixed `BeginModel\0`, `Version`, `MaterialList`, material names (e.g. `<PPS> Chavez`), then float streams — geometry and materials, **no AI or gameplay data**. `.skl` opens with float `1.0` then `Version` then bone names (`root_pelvis`, `L_thigh`) each followed by 7 floats (quaternion + position) — skeleton only.

**"Elite" is an enemy type, not a difficulty tier.** There is no recruit/veteran/elite naming anywhere in `actor\` or `character\`.

**Nothing in `actor\` or `character\` references a `.wsf` or a `.gun`** — verified by grep. The binding happens one level up in `data\mission\*.mis`, on a single element: `ModelFile` → `.cms`, `GameFile` → `.cgs`, `WeaponFile` → `.wsf`, `AICombatModelFile` → `.acm`.

**Blunt limitation:** the only AI knobs in `actor\` are the six numbers in `.cgs`. There is **no** reaction time, vision range, hearing range, aggression, morale, obedience, follow distance, fire discipline or ROE attribute — the tag inventory above is exhaustive across all 200 text files. Teammate *behaviour* is not a data field; it lives in the `.mis` `<Plan>` system (`FollowStep`, `CombatROEStep`, `MoveROEStep`, `TakeCoverFromStep`, `StanceStep`, `PatrolStep`, `GrenadesStep`, `SniperStep`, `WeaponSelectStep`, `ToggleAIStep` — the plan-step type names are in `lockdown.exe`) and in the `.script` graph. That is a mission-editor surface, not a slider.

---

## Missions & campaign

### What is text and what is not

| ext | n | verdict | first bytes |
|---|---|---|---|
| `.mis` | 101 | **TEXT**, tag-soup XML, CRLF | `<MissionFile>\r\n` |
| `.script` | 101 | **TEXT** | `<ScriptSource version = "6">\r\n` |
| `.esf` | 48 | **TEXT** | `<EnvironmentalSoundFile>\r\n` |
| `.acm` | 4 | **TEXT** | `<AICombatModelFile>\r\n` |
| `campaignfile.xml` | 1 | **TEXT** | `<CampaignFile>\r\n` |
| `.rsc` | 101 | **BINARY** | LE u32 `0x80000006`, all 101 |

### `campaignfile.xml` — 1603 bytes, complete

```xml
<CampaignFile>
	<Campaign filename="m01_sec_01.mis" filename="m01_sec_03.mis" filename="m01_sec_02.mis" missionNumber="1"/>
	<Campaign filename="m11_sec_01.mis" filename="m11_sec_02.mis" missionNumber="2"/>
	<Campaign filename="m12_sec_01.mis" filename="m12_sec_02.mis" filename="m12_sec_03.mis" missionNumber="3"/>
	<Campaign filename="m02_sec_02.mis" filename="m02_sec_03.mis" missionNumber="4"/>
	<Campaign filename="m03_sec_01.mis" filename="m03_sec_02.mis" missionNumber="5"/>
	<Campaign filename="m04_sec_02.mis" filename="m04_sec_03.mis" missionNumber="6"/>
	<Campaign filename="m07_sec_01.mis" filename="m07_sec_02.mis" filename="m07_sec_03.mis" missionNumber="7"/>
	<Campaign filename="m05_sec_01.mis" filename="m05_sec_02.mis" filename="m05_sec_03.mis" missionNumber="8"/>
	<Campaign filename="m06_sec_01.mis" filename="m06_sec_02.mis" missionNumber="9"/>
	<Campaign filename="m08_sec_02.mis" filename="m08_sec_03.mis" missionNumber="10"/>
	<Campaign filename="m09_sec_02.mis" filename="m09_sec_03.mis" missionNumber="11"/>
	<Campaign filename="m10_sec_01.mis" filename="m10_sec_02.mis" missionNumber="12"/>
	<Campaign filename="m14_sec_01.mis" filename="m14_sec_02.mis" missionNumber="13"/>
	<Campaign filename="m13_sec_01.mis" filename="m13_sec_03.mis" missionNumber="14"/>
	<Campaign filename="m15_sec_01.mis" filename="m15_sec_02.mis" filename="m15_sec_03.mis" missionNumber="15"/>
	<Campaign filename="m16_sec_01.mis" filename="m16_sec_03.mis" filename="m16_sec_04.mis" missionNumber="16"/>
	<Training filename="tr_target_range.mis" missionNumber="1"/>
</CampaignFile>
```

It carries **only** `filename` (1–3 repeats per element) and `missionNumber`. No briefing, no difficulty, no mode, no next-mission pointer. Those live in each `.mis`: `<MissionTransition>`, `<Shell SinglePlayerMissionType MultiPlayerMissionType>`, `<MapName>`, `<Location>`, `<Date>`. `missionNumber` is display order and does not match the folder number (m11 is mission 2, m02 is mission 4, m13 is mission 14). Verified: for all 16 entries the attribute order matches the `<MissionTransition>` chain exactly.

**Can you re-enable a cut mission by editing this file?** The format allows it trivially — add a `filename=` or a whole `<Campaign>` line. But **there is nothing to point it at.** See below.

### The cut-content set difference, done properly

101 `.mis` on disc; `campaignfile.xml` names 39. The 62-file gap is **not** cut content:

* 32 are terrorist-hunt variants (`*_th_nor`, `*_th_rev`). Not listed because `lockdown.exe` hard-codes the literals `_th_rev.mis` and `_th_nor.mis` (file offsets 5297132 / 5297144) and finds them by suffixing the base name.
* 30 are multiplayer maps (`mp01cl_*` … `mp09_*`), found by mode. The mode names `Free-for-All`, `Team Adversarial`, `Retrieval`, `Rivalry`, `Lone Rush`, `Infiltrator` are all literals in `lockdown.exe` around offset 5283552.

**Single-player base missions on disc: 38, plus `tr_target_range` = 39. All 39 are referenced. Zero orphan `.mis` files.**

**The real cut mission is `m13_sec_02`, and the map survived while the mission files did not.** `data\map\m13_sec_02_pc\` is the only genuinely orphaned map folder of 49 (cross-checked every folder's `.env` name against every `<Environment>` tag in all 101 `.mis`; the other apparent orphans are folder-name/`.env`-name mismatches such as folder `m10_sec_01_PC` holding `m10_pc_sec_01.env`). It is a complete, 31 MB, shippable level:

* `m13_sec_02_pc.map`, 9,400,296 bytes, header `0c000000 "BeginMapv5.1"` — same header format as the shipping `m13_sec_01_pc.map`
* `m13_sec_02_pc.nvm`, 9,892 bytes — the AI navmesh
* `m13_sec_02_pc.env` — full environment file (`SkyboxFileName` `m09_sky.pob`, `FarPlane` 500, `ColorRemap RemapDefault="m13_sec_02.remap"`)
* ~75 level-specific textures (`m13_s2_PC_mansionbot`, `m13_s2_PC_fountaintrim`, `m13_s2_bronco`, `m13_sec02_car34`, …)

The smoking gun is that the chain was re-pointed around it: `m13_sec_01.mis` contains `<MissionTransition>m13_sec_03.mis</MissionTransition>`, and mission 14 in `campaignfile.xml` lists only sections 01 and 03. There is no `m13_sec_02.mis`, `.script`, `.rsc` or `_amb.esf`, and grep across `data\mission`, `data\shell` and `data\*.xml` finds **zero** references to `m13_sec_02`.

Also absent entirely (no map, no mission): `m02_sec_01`, `m03_sec_03`, `m04_sec_01`, `m06_sec_03`, `m08_sec_01`, `m09_sec_01`, `m10_sec_03`, `m11_sec_03`, `m16_sec_02`.

**So: editing `campaignfile.xml` alone restores nothing.** Restoring `m13_sec_02` means authoring `.mis` + `.script` + `.rsc` from scratch against the surviving map and navmesh. That is a mission-editor job, not a mod-manager job.

### `_th_nor` vs `_th_rev` vs base

16 missions have TH variants (`m01_sec_01, m02_sec_03, m03_sec_02, m04_sec_02, m05_sec_01, m06_sec_02, m07_sec_03, m08_sec_03, m09_sec_03, m10_sec_02, m11_sec_01, m12_sec_02, m13_sec_03, m14_sec_02, m15_sec_02, m16_sec_03`), each with one `_th_nor` and one `_th_rev`.

Sizes for `m04_sec_02`: `.mis` 145,480 → 110,641 / 110,654; `.script` 39,710 → 18,784 / 18,726; `.rsc` 2,925 → 1,753 / 1,729.

**base → `_th_nor`:** mode flips to `<Shell SinglePlayerMissionType = "Terrorist Hunt" MultiPlayerMissionType = "Terrorist Hunt">`; `<Location>` and `<Date>` are emptied; `<GameTypes>` is removed; `<MissionTransition>` becomes the literal `not set`; `<SpawnPools>` is emptied. Roster drops from 40 Actors / 21 Teams to 30 Actors / 14 Teams. The `.script` collapses from 9 block groups (`area01/02/03`, `cine01`, `cine02`, `co-op`, `sound`, `sound - dialog`, `<Default>`) to **one** — all cinematics, dialogue and objective logic stripped.

**`_th_nor` → `_th_rev` is purely a start-point flip.** 722 diff lines, ~6 substantive changes: the shown platoon swaps 3↔1, the "hidden platoon" counter swaps area 03↔01, insertion-zone tag ids shuffle, and in the `.mis` the insertion zone physically moves to the far end of the map (`Pos0 = "-111.85;74.07;4.00;"` → `"25.89;24.32;0.00;"`). Sorting both cover-point lists leaves only two differing lines — the 371 `CoverPoint`/`Position` entries are the same set, reordered.

**Every one of the 32 terrorist-hunt maps has exactly 30 `<Actor>` elements** (verified across all 16 pairs). That is the cleanest possible "TH enemy count" slider.

### Enemy count, waves and respawns — all of it is in the text

**Authored roster.** `.mis` holds `<Units>` → `Company` → `PlatoonList` → `Platoon` → `Team` → `Actor`. One `<Actor>` is one enemy body; `grep -c '<Actor IgorId'` gives the count. Campaign sections run 26–59.

```xml
<Team IgorId="1199" ScriptId="63" Name="Team - Floor 4 PG" AICombatModelFile="badguys.acm">
  <Actor IgorId="16364" ScriptId="220" Name="A - Floor 4 PG Enemy 01" Hidden="0" Grounded="1">
    <ActorSpawnData>
      <ActorSpawnData ModelFile="e_militia_01.cms" GameFile="militia-01.cgs"
                      WeaponFile="militia_1_semi-auto_rifle.wsf" Difficulty="3" SpawnSet="A"/>
```
(`data\mission\m01_sec_01.mis`, lines 37–45)

**Reinforcement pools.** `<SpawnPools><Pool Size="…" Name="…" ModelFile GameFile WeaponFile/>`. `m04_sec_02.mis` lines 28–35 hold 7 pools totalling 17 bodies; `m01_sec_01.mis` has `<Pool Size = "9" Name = "Pistol Enemies" …/>`.

**Waves and respawn budget.** `<SpawnArea … SpawnCount="2" TeamSize="2" …>` in `data\mission\m01_sec_01.mis` lines 956–961. `SpawnCount` is the total this area may emit, `TeamSize` how many live at once. 21 `.mis` files have `<SpawnArea>`. Scripts trigger them with `SpawnTeamFromSpawnArea` (51 uses) and can override both numbers at runtime via `SpawnAreaSetTeamSize` / `SpawnAreaSetSpawnLimit` — used only in `m03_sec_02.script` and `m10_sec_02.script`, inside blocks whose `group` is literally `"CHALLENGE"`.

**Difficulty scaling, three mechanisms:**
1. `Difficulty="3"` (2467 occurrences) / `"2"` (178) on every `<ActorSpawnData>`. **GUESS:** a bitmask of tiers the actor appears on (3 = both, 2 = harder only). The exe code that reads it was not located.
2. Script branching on the `DifficultyChallenge` (10 uses) and `DifficultyNormal` (5) queries.
3. `data\mission\*.acm` — the per-difficulty AI accuracy table. `badguys.acm` is `Normal="29" Challenge="50"`, `long_distance.acm` is `24`/`39`, `rainbow.acm` and `default.acm` are `0`/`0`.

**Bluntly:** enemy count is fully data-visible and directly editable. Objective and hostage *counts* are not — they are emergent from the script graph (`ObjectiveAdd` ×94, `ObjectiveComplete` ×83, `HostageTeamOn` ×9), so a GUI can list objective *text* (`<Objective ScriptId Text StringId>` in `.mis`, 99 entries across 101 files) but cannot offer "number of hostages" as a field.

### `.script` is readable — and probably inert on its own

`<ScriptSource version="6">` is a serialised visual event graph: `StringTable` → `Constants` → `Tags` (named handles grouped by 25 `TagType` kinds, referenced by integer with the name echoed) → `Blocks`. Each `Block` is one `Trigger` plus an ordered `Responses` list. `Query` nodes are nestable expressions. Control flow is **flat and stack-based** — `If` / `Else` / `EndIf` / `ContinueIf` / `StopIf` / `RedirectIf` are themselves Responses in the linear list.

Vocabulary across all 101 files: **29 trigger types**, **123 response types**, **46 query types**. The mod-relevant ones:

* Spawning/counts: `SpawnTeamFromSpawnArea(51)`, `SpawnTeamFromSpawnAreaInSet(3)`, `SpawnAreaSetSpawnLimit(6)`, `SpawnAreaSetTeamSize(2)`, `DisplayEnemyCount(64)`, `GetCurrentCompanySize(128)`, `GetCurrentPlatoonSize(72)`, `GetCurrentTeamSize(32)`
* Cheat-shaped: `InvincibilityOnActor(7)`, `InvincibilityOnTeam(4)`, `InvincibilityOnPlatoon(6)`, `SetInvincibilityTeamToCompany(7)`, `InvisibilityOnPlatoon(10)`, `InvisibilityOnTeam(6)`, `ToggleAIAwareness(47)`, `TeamAIOff(3)`, `KillActor(40)`, **`ConsoleCommand(3)`**
* Difficulty: `DifficultyChallenge(10)`, `DifficultyNormal(5)`, `CoOpModeOn(87)`, `TrainingModeOn(4)`

**`ConsoleCommand` is a real response type used three times in shipping scripts** — worth chasing for a developer console.

**The catch.** `.rsc` is the compiled counterpart and it is what the runtime consumes. Its first chunk (`u32 0x80000006`, `u32 count`, then `count` × `{u32 stringId, u32 length, bytes}`) is byte-for-byte the `.script`'s `<StringTable>` — verified across all 101 pairs, the `.rsc` count equals the `<String>` element count with zero mismatches. Later chunks (`0x80000021`, `0x80000033`, `0x8000002f`, …) are the compiled trigger/response bytecode; size tracks block count. **Editing a `.script` without recompiling the `.rsc` is very likely a no-op.** Treat script editing as out of scope for a first GUI.

### `.esf`, `.acm`, `.rsc`

* **`.esf` = `<EnvironmentalSoundFile>`**, plain XML ambient-sound layout, one per base level (48), shared by that level's TH and MP variants. Bound from `.mis` via `<EnvironmentalSoundFile>m01_sec_01_amb.esf</EnvironmentalSoundFile>`. All 101 references resolve; zero dangling, zero orphans. Tags: `LoadBank(91)`, `Sound(1339)`, `Point(1433)`, `SoundZone(1105)`, `SoundObstructionZone(84)`, `StreamSound(11)`.
* **`.acm` = `<AICombatModelFile>`**, four files of 452–458 bytes. See the Levers table.
* **`.rsc`** — compiled script, described above.

### Dangling references found in the mission data

* `data\mission\m03_sec_02.mis` references `WeaponFile = "terrorist-01_smg_sa_lowfrag.wsf"`, which **does not exist** in `data\kits\` under any casing. 64 of the 65 distinct `WeaponFile` values resolve; this one does not.
* Every campaign `.mis` references `"r_price _default.wsf"` with an embedded space in the Slot 2 Rainbow entry. The file on disc is also named with the space (`r_price _default.wsf`, `r_price _civ.wsf`, `r_murad _default.wsf`, `r_losielle _default.wsf`), so it works — but a GUI that normalises filenames will break it. Note also `r_losielle` (mission/kit spelling) vs `louis_loiselle.cgs` (actor spelling) vs `r_loiselle_01.cms` (model spelling): three spellings of one operator.

---

## Art

### Format

Lockdown's `data\shell\art\` holds RSB **versions 5, 6, 9 and 10** — not "all version 9" as briefed. Breakdown of the 65 files: v9 ×32, v10 ×31, v6 ×1 (`eax_logo.rsb`), v5 ×1 (`video.rsb`).

**Which decoder works:** the Xbox one, `C:\Users\Tristan\Documents\GitHub\TomClancyXbox-ModStudio\tcxbox\rsb.py`, is the right base — its `HEADER = 35` and `TRAILER = {8: 66, 9: 74}` are exactly right for Lockdown's v9 (`background00.rsb` is 524397 bytes = 35 + 1024×1024×0.5 + 74, closing to the byte). The PS2 decoder `C:\Users\Tristan\Documents\GitHub\TomClancyPS2-ModStudio\tcps2\rsb.py` handles the two stragglers (v5/v6, 28-byte header) unmodified.

**Three changes were needed.** My working copy is `<scratchpad>\lockdown_rsb.py`.

1. **Version 10 exists and the Xbox module rejects it.** `parse_header` raises on anything not in `TRAILER`. v10 is the same 35-byte header; only the trailer grew. v9's trailer is a fixed 74 bytes; **v10's is `74 + 4 + 4·N`**, where a leading `u32` count is followed by N property words — observed 122 bytes (N=11, `goggle texture.rsb`) and 130 bytes (N=13, `hud-icons.rsb`). Because the trailer is variable, I stopped deriving the body size from the trailer and derive it from the front instead: pick the largest of 4 / 2 / 1 / 0.5 bytes-per-pixel for which `w·h·bpp ≤ len − 35 − 74`.
2. **1 byte per pixel is a real encoding here and the Xbox module has no case for it.** `hud_mercpda.rsb`, `hud_mercpdaframe.rsb` and `hud_mpicons.rsb` are exactly `w·h` bytes — DXT5/BC3 (`Image.frombytes(..., "bcn", 3)`). The Xbox games only ever showed 0.5, 2, 3 and 4.
3. **32-bit pixels are stored A, R, G, B — not B, G, R, A.** This is the one that matters and it is the *PS2* module that is right ("32bpp is the one direct format stored A,R,G,B"), not the Xbox one, which uses `"raw","BGRA"`. Proof, first eight pixels of `lockdown_large.rsb` at offset 35: `ffffffff ffffffff 00ffffff 00ffffff 00ffffff …` — byte 0 alternates `ff`/`00` while bytes 1–3 stay `ff`. That is an alpha mask over white, so byte 0 is alpha. Decoded as `BGRA` the whole page comes out chrome-yellow (the alpha byte lands in blue, and a transparent region reads as R=G=255, B=0); decoded as `ARGB` it is the correct logo on a transparent page. I rendered all four permutations side by side to settle it.

Some files carry mipmap chains after the top level (`pcfont_lg.rsb` leaves 174722 bytes over, ≈ the 1/4, 1/16 … chain). Decoding the top level and ignoring the remainder is correct.

**65 of 65 files in `data\shell\art\` decode, plus `data\shell\briefing\m01_01.rsb`.** PNGs are in `<scratchpad>\rsb_png\`, contact sheet at `<scratchpad>\contact_sheet.png`, key art at `<scratchpad>\key_art.png`.

### What is in the folder

`data\shell\briefing\` contains exactly **one** file, `m01_01.rsb` (1024×512, v9, 32-bit) — a briefing map for mission 1. The other 54 briefing maps live in `data\textures\briefing_maps\`, not here.

`data\splash.bmp` is a plain uncompressed 640×480 24-bit Windows BMP, 921656 bytes — no decoder needed.

| file | size | fmt | what it is |
|---|---|---|---|
| `background00.rsb` … `background16.rsb` | 1024×1024 | v9 DXT1 | **17 menu backdrops.** Desaturated blue-grey in-game screenshots with a faint UN emblem watermark top-left and an HUD-ring overlay. Picture occupies the top 1024×772; the rest of the page is black. |
| `r6lockdown.rsb` | 512×256 | v9 ARGB32 | **The RAINBOW SIX / LOCKDOWN wordmark.** Confirmed as the game's logo asset — see the key table below. Art bbox 421×204, transparent page. |
| `lockdown_large.rsb` | 512×256 | v10 ARGB32 | Same wordmark, larger art (bbox 439×256). |
| `lockdown_small.rsb` | 256×256 | v10 ARGB32 | Same wordmark, small. |
| `shelllogo.rsb` | 256×128 | v9 ARGB32 | Same wordmark again, smallest. |
| `shell01.rsb` | 128×512 | v9 ARGB32 | Tall menu chrome strip (side rail / button plates). |
| `shell1.rsb`, `shell2.rsb` | 256×128 | v10 ARGB32 | Menu widget plates and a PS2 face-button sheet. |
| `shellextra.rsb` | 512×256 | v10 ARGB32 | **A full PlayStation 2 DualShock controller diagram.** Console-port leftover shipped in the PC build. |
| `hud01..04`, `hud_merc01..04` | 128×128 | v9/v10 | The two HUD themes (`hudTheme` in `options.xml`). |
| `hud_foreground/background/radar/sniper/hitindicator` | 256×256 | v9 ARGB32 | HUD plates and the icon sheet (biohazard, skull, R6 mark, arrows). |
| `icon_r6.rsb`, `hud_r6_teamgraphic.rsb` | 128×128 / 64×64 | v9 | The R6 laurel-wreath roundel — the cleanest single emblem in the folder for a GUI app icon. |
| `icon_mercs.rsb`, `hud_merc_teamgraphic.rsb` | | v9 | Mercenary skull emblem. |
| `insignias1/2/3.rsb` | 256×256 | v10 | Three sheets of player-badge glyphs. |
| `pcfont_lg/sm.rsb` | 512×256 / 256×128 | v10 + mips | The PC bitmap fonts. |
| `ps2font_debug.rsb` | 256×128 | v10 | **The PS2 debug font**, shipped in the retail PC build. Keyed as `kFontDebug`. |
| `eax_logo.rsb` | 512×128 | v6 RGB565 | Creative EAX splash. |
| `video.rsb` | 1024×512 | v5 RGB565 | Video-playback target texture. |
| `merc_pda.rsb`, `hud_mercpda*.rsb` | | v9/v10 | Mercenary PDA frame and glyph sheet. |

### Which file the game asks for, by name

`data\shell\english\strings.rsres` is a two-block string table — 3645 strings, values first then keys, paired at a constant offset. The asset block is unambiguous:

```
mask_sr.rsb          -> kSniperMask         (MISSING from data\shell\art)
ps2font_debug.rsb    -> kFontDebug
pcfont_sm.rsb        -> kFont
ps2font_lg.rsb       -> kFontLarge          (MISSING)
white.rsb            -> kWhite              (MISSING)
gear guns.rsb        -> kGearGuns           (MISSING)
r6lockdown.rsb       -> kLogo
generic_loading.rsb  -> kGenericLoading     (MISSING)
shell01.rsb          -> kShell_1
icon_r6.rsb          -> kIconRainbow
icon_mercs.rsb       -> kIconMercenary
background00.rsb     -> kLoadingBackground
```

So: **`r6lockdown.rsb` is the logo** and **`background00.rsb` is the loading backdrop**. `background01`–`16` are named nowhere on disc — but `lockdown.exe` at offset `0x5324f8` holds the format string **`background%.2d.rsb`**, sitting between `Official_suppliers01-Logo_splash.rsb` and `shell_gear/` / `shell_char/`. The set is therefore indexed at runtime, presumably per mission.

**I could not prove which file is the *main-menu* backdrop as opposed to the loading backdrop.** Only `background00` has a key, and it is `kLoadingBackground`. GUESS: the main menu uses the same indexed set.

### Dominant UI colours (measured over opaque pixels, quantised to 16 levels)

| source | hex |
|---|---|
| `background00` menu backdrop | `#607080` 14%, `#506070` 11%, `#405060` 9%, `#708090` 6%, `#304050` 4% (plus 25% `#000000` letterbox) |
| `background05` (darker interior) | `#405060` 12%, `#304050` 10%, `#506070` 7% |
| `shell01` menu chrome | `#304050` 12%, `#305060` 10%, `#203040` 8%, `#506070` 5% |
| `shellextra` | `#101010` 32%, then a saturated accent `#4060b0` 6% |
| `lockdown_large` wordmark | `#d0d0d0` 8%, `#d04040` 5%, `#e0e0e0` 4%, `#802020` 3% |
| `hud_foreground` HUD icons | `#e0e0e0` 21%, `#d0d0d0` 20%, `#f0f0f0` 15% |

**A faithful skin palette:** page `#0a0e14`, panel `#203040`, panel-light `#405060`, border/rule `#607080`, muted text `#708090`, body text `#d0d0d0`, bright text `#f0f0f0`, accent `#4060b0`, danger/brand accent `#d04040`. In one line: cold desaturated steel blue with a single red accent from the wordmark.

### Art beyond `data\shell\`

`data\textures\` holds the rest of the menu art a GUI would want, and the brief did not mention it:

| folder | files | contents |
|---|---|---|
| `textures\suppliers\` | 25 | `Official_suppliers01-Logo_splash.rsb` … `23-TCI_A.rsb` — the boot-up sponsor reel (Blackhawk, DynamicEntry, Eagle, Oakley, Paraclete, Safariland, TCI). Named individually in `lockdown.exe`. |
| `textures\mission_sshots\` | 17 | `m01.rsb`…`m16.rsb` + `t01.rsb` — mission-select thumbnails. `t01` has no `m` sibling. |
| `textures\briefing_maps\` | 55 | `m01_sec_01.rsb`, `m01_sec_01_th.rsb`, … — per-section briefing maps, including `_th` terrorist-hunt variants. |
| `textures\mp_loading\` | 9 | `mp01.rsb`…`mp08.rsb` + one more. |
| `textures\equip_icons\` | 65 | The weapon/equipment icons the `.gun` files' `gunpicture` attribute points at. |
| `textures\shell_gear\` | 34 | See "Cut content" — an entirely unreferenced weapon-icon set. |
| `textures\shell_char\` | 127 | Character portraits (`E_Burke_01_head.rsb`, etc.). |

---

## Cut content

Reported honestly: there is real unused material, but it is leftovers and dead references rather than playable hidden content.

**1. An entire unused weapon-icon folder, and it names guns that are not in the game.** `data\textures\shell_gear\` holds 34 `.rsb` icons. **Not one of them is referenced by any `.gun`, `.prj` or `.itm` file** (cross-checked every `gunpicture` value against the folder). Several depict weapons with no data file at all on disc:

```
3p_r_aks47_128.rsb      3p_r_fnfal_128.rsb      3p_mg_pkm_128x128.rsb
3p_r_groza_128.rsb      3p_r_m16_128.rsb        3p_r_oicw_128.rsb
3p_r_g36_128x128.rsb    3p_r_sar21_128x128.rsb  3p_smg_ak74su_128x128.rsb
3p_smg_bizon_128.rsb    3p_smg_p90_128x128.rsb  3p_smg_spectreM4_128x128.rsb
3p_smg_ump9_128x128.rsb 3p_smg_uzi_128.rsb      3p_sg_usas12_128x128.rsb
```

There are no `.gun` files for the AKS-47, FN FAL, PKM, Groza, M16, OICW, G36, SAR-21, AK-74SU, Bizon, P90, Spectre M4, UMP9, Uzi or USAS-12 — so this is icon art for a weapon roster that was cut or inherited from an earlier build. **The art is there; the stats are not.** A GUI could offer "revive" by cloning an existing `.gun` and pointing `gunpicture` at one of these, but there is no 3D model reference to go with it.

**2. Eleven unused equipment icons** in `data\textures\equip_icons\`: `att_highcap.rsb`, `att_highcap_p.rsb`, `att_none.rsb`, `att_reddot.rsb`, `att_scope.rsb`, `att_suppressor.rsb` (attachment icons — probably drawn by code rather than by `gunpicture`), plus `eq_dummy.rsb`, `p_dummy.rsb`, `smg_dummy.rsb`, `eq_motionsens.rsb`, `eq_survpda.rsb`. The motion sensor and survey PDA have 1st-person textures too (`data\textures\1p_ex_motionsens_128.rsb`, `1p_ex_survPDA_128.rsb`) but **no `.itm` file** — cut equipment.

**3. Twenty-one dead `gunpicture` references.** Every `e_*.gun` and both RPGs point at a `00_*.rsb` icon (`00_r_m8.rsb`, `00_p_meu45.rsb`, `00_rpg7.rsb`, …) that exists **nowhere under `data\`**. Twenty-one distinct names. Benign — enemy weapons never appear in the outfitting UI — but it means the RPG has no icon either.

**4. Five shell textures the string table asks for and the disc does not have:** `mask_sr.rsb` (`kSniperMask`), `ps2font_lg.rsb` (`kFontLarge`), `white.rsb` (`kWhite`), `gear guns.rsb` (`kGearGuns`), `generic_loading.rsb` (`kGenericLoading`). Plus `shell_controller.rsb`, which `data\shell\english\preload_textures.rsres` lists for preloading and which is also absent.

**5. Console leftovers in the retail PC build:** `ps2font_debug.rsb` (keyed `kFontDebug`), `shellextra.rsb` (a DualShock 2 button diagram), `shell2.rsb` (PS2 face-button glyphs), and the `.psx` string next to the shell asset names in `lockdown.exe`.

**6. Two unreferenced equipment items that are fully statted:** `c4.itm` and `claymore.itm` are complete files with real `<ExplosionData>`, but every single-player mode flag is `0` and **no `.wsf` kit references them**. They are MP-only on disc. Also unreferenced by any kit: `laser_tripmine.itm`, `lock_fuser.itm`, `proximity_flash_mine.itm`, `smokemulti.prj`, `20mmGLgrenade.prj`, `rpg7.prj`, `rpg7_sniper.prj`.

**7. Two broken kit references:** `data\kits\RPG_Virus.wsf` → `rpg7virus.gun`, which does not exist in `data\equip\`. And `data\mission\m03_sec_02.mis` → `WeaponFile = "terrorist-01_smg_sa_lowfrag.wsf"`, which does not exist in `data\kits\` (64 of the 65 distinct `WeaponFile` values resolve; this one does not).

**7b. One entire cut mission whose map shipped.** `data\map\m13_sec_02_pc\` — 31 MB, a complete level with `.map`, `.nvm`, `.env` and ~75 textures, and the only orphaned map folder of 49. The `.mis`/`.script`/`.rsc` were deleted and `m13_sec_01.mis`'s `<MissionTransition>` re-pointed to `m13_sec_03.mis` to skip it. Detail in "Missions & campaign". This is the biggest cut-content find on the disc, and it is **not** re-enableable by editing `campaignfile.xml` — the mission files would have to be authored from scratch.

**8. A mod system — not cut at all, just unused.** See the box at the top. UI vocabulary in `data\shell\english\strings.rsres`: `'Mods'`, `'Mod Info'`, `'Available Mods'`, `'Game Session Mods'`, `'Add Mod'`, `'Remove Mod'`, `'Activate and Deactivate Player Created Mods'`, `'Select a Player Created Mod to Activate'`, `'Decativate All Active Mods'` (sic), `"THE SERVER HAS A MOD THAT YOU DON'T HAVE"`, `'Server has modified data!'`, `'You are not allowed to create a ranked game with mods enabled'`; keys `kMods`, `kModInfo`, `kModListPanel_AvailableModList`, `kModListPanel_AddMod`, `kModListPanel_GameModList`, `kModListPanel_RemoveMod`, `kModListPanel_ClearAll`, `kMainMenu_Mods`. Engine side, all verified in `lockdown.exe`: `RSModsMgr::LoadSettings` / `RSModsMgr::SaveModsSettings`, `mods/` + `\*.*`, `ModsCont.txt`, `ModsSet.txt`, manifest fields `NAME AUTHOR SUPPORT VERSION MULTIPLAYER ICON CLIENT-SIDE SERVER-SIDE`, and the `-modset` switch. No `mods\` folder ships.

**8b. There is a full Red Storm developer console compiled into retail, with 27 commands and 67 variables — including `god`.**

It is a text console (`RSConsole`), not a menu. Infrastructure strings sit contiguously in `.rdata` at file `0x522698`–`0x522a8c`:

```
0x522698  [?] ALIAS <aliasname> <command string>
0x5226c0  Unknown variable/cmd: %s
0x5226f4  Access to %s is restricted
0x522728  listcmds
0x52291c  [?] EXEC filename.cfg
0x522a40  RSConsoleString
0x522a6c  Alias / Listvars / Listcmds / Listtypes
```

The input-state enum at file `0x512794`–`0x512840` includes both **`modeConsole`** and **`modeUICheat`**.

**The 27 commands**, recovered from the static-initialiser registry in `.text` (ctor `0x6347e0`), name → handler VA:

```
god 0x55e190        suicide 0x4f2c40      suicidesp 0x4f2c40    boom 0x67ea40
rcon 0x527910       screenshot 0x594bc0   flushtexture 0x5f79a0 counters 0x5f3d80
timers 0x5f4080     spewobs 0x682e30      spewprop 0x682d70     spewpropai 0x682db0
spewproppath 0x682df0                     toggleLOSNudge 0x406000
toggleSpotlightChase 0x405ff0             togglebreathing 0x6e0420
exagerrateDangerAreas 0x4063f0 (sic)      dynamicgamma 0x60ea20 saveluminance 0x60ea60
JournalRecordStart/Stop 0x55e210/0x55e2c0 JournalPlayStart/Stop 0x55e310/0x55e3c0
play_voice_cue 0x6f7d90                   oceanShader1_1 0x878ff0  oceanShader2_0 0x879000
water1 0x543e10
```

`god`'s handler at `0x55e190` was disassembled: it toggles a player byte and echoes `"god On"` / `"god Off"` via the format `"%s %s"` at VA `0x90ee70` — it really is god mode. Only `suicide` and `rcon` carry the restricted-access flag.

**The 67 variables** (ctor `0x634820`, typed `float`/`bool`/`int`/`RSVector4`) include live debug visualisers `showShadowMap`, `showPlayerTracers`, `debugGamma`, plus whole families that are directly useful for RTX Remix work — `bloom*` (9), `remap*` colour-grading (9), `shadowMap*` (5), `ocean*` (12), `gamma*` (3), `heatScale`/`heatTile`/`parallaxBias`/`alphaMod`, and AI tuning at runtime: `RainbowReconSightMod`, `RainbowReconSoundMod`, `corpseReactionDelay_{Mercenary,Mob,Neutral,Rainbow,Terrorist}`, `corpseReportDelay_{…}`.

**How to open it is unproven.** GUESS, on three pieces of circumstantial evidence: (a) `modeConsole` exists; (b) the exe's 103-entry `key_*` table has no tilde or escape entry; (c) `readme.txt:204` says "there are a few keys that cannot be remapped to different functions, such as ~ and Esc". That points at `~`, but nobody ran the game to check.

**8c. `ConsoleCommand` is a `.script` response type, and the shipping missions use it.** This is the route to the console that does *not* need a keybind:

```
data\mission\m10_sec_02.script:1129   <Response statement = "117" type = "ConsoleCommand">
                              1130     <Literal type = "String" value = "44" string = "god"/>
data\mission\m12_sec_03.script:524    <Literal type = "String" value = "9"  string = "boom"/>
data\mission\m12_sec_03.script:542    <Literal type = "String" value = "10" string = "boom"/>
```

(`m10_sec_02` turns on `god` immediately before `TeleportObjectToZone` on Chavez — a scripted invulnerable extraction.) Both literals are present in `lockdown.exe`: `god` at offset `0x519433`, inside a command table alongside **`camerashake`, `smokeBlockScale`, `JournalRecordStart`, `JournalRecordStop`, `JournalPlayStart`, `JournalPlayStop`**; `boom` at `0x52f1c3`, next to **`showPlayerTracers`, `MentalImage`, `RainbowReconSoundMod`, `RainbowReconSightMod`, `SimHumanStateUpdate`**. A console command vocabulary demonstrably exists. **How to reach it from the retail build is unproven** — no console key binding or command-line switch was located from my side.

**8d. A `"God!Mode"`-keyed obfuscated blob behind the console command `water1`.** `.data` at VA `0x9d65f0` holds an 8-slot, 128-byte-stride table. Slots 0 and 4 are readable keys, the rest are ciphertext:

```
0x9d65d8  NimitzFlags!$
0x9d65f0  RedStorm Entertainment_
0x9d6670  gguy7846238dfuigifuefa79fy89
0x9d66f0  fnsvnddkyawe73ibqrye8cbg43g78f43
0x9d6770  fhshifhwe8923472389uhi
0x9d67f0  God!Mode
0x9d6870  ruersfnfwetwehfnjkfsjsbnd3
0x9d68f0  nhjkaahofhaio498238hruwer893f
0x9d6970  vnklsdhfadsh89429809437hwfeh89
```

The only code that touches them is the handler at VA `0x543e10`, which is the one registered for the console command **`water1`**. It builds one keystream from `"RedStorm Entertainment_"` and another from `"God!Mode"` (XORed against the 32-byte constant `ha7874aks$5,5&96esfe_+q!v#1c$b.;` at `0x917870`), then on `water1 1` or `water1 2` decodes the corresponding blob with `dst[i] = src[i] - key[i % keylen]` and prints two lines.

**Honest limit: the cipher was emulated in Python and did not produce readable plaintext.** The model of the keystream tail is evidently slightly wrong. So the command and the `"God!Mode"` key are proven; what it prints is **not recovered**. Do not report this as "a cheat code was found" — report it as an unopened box.

**9. The negative results, stated plainly.**

* **No debug or developer *menu* exists.** Every `*Menu` / `*Screen` / `*Panel` identifier in the exe was enumerated (`ActionTextPanel`, `CharacterEditPanel`, `LanMenu`, `ReadyGameMenu`, `SinglePlayerMenu`, `TeamOrdersPanel`, …) — all shipping UI. The developer surface is the text console plus the `<debug>` block in `options.xml`.
* **No cheat/unlock flag in `options.xml` or `keys.xml`.** The exe's full XML-attribute string table (file `0x51977c`–`0x519fbc`) is a 1:1 match for what `options.xml` already contains — there are no hidden extra options.
* **No `-dev` / `-debug` / `-console` / `-cheat` command-line switch.** The two real switch tables are: `.rdata` VA `0x911fa4`–`0x91203c` — `-modset -autoserve -reportErrors -exportXML -splitscreen -password -rainbowteamsize -client -server -nwmsgdump -exit -buildbinary -mission`; and a WinMain-path parser at VA `0x544160`–`0x544380` — `memdump -autoserve -mission -demo -exit -testrandom -language {french|spanish|german|italian}`. The only `-debug` string in the file is inside the bundled Bink filter's usage text.
* **No cheat/debug text in any of the five `strings.txt` files** (grepped case-insensitively for debug|cheat|unlock|dev|console|god|invinc — zero hits).
* **No `recruit`/`veteran`/`elite` difficulty tiers.** `recruit` appears only in a *class* list (`recruit, sniper, electronics, demolitions, recon, assault, command`). The engine constructs just four classes — `clsAssault, clsSniper, clsRecon, clsDemo` — so `electronics`, `command` and `recruit` are vestigial. Difficulty is two-tier: `NormalDifficultyModifier` / `ChallengeDifficultyModifier`.
* **No extra game modes in the exe.** The mode token block at `.rdata` file `0x50e028`–`0x50e0c4` holds exactly the 11 tokens that appear in the `.gun` files, no more.
* **No hidden mission art.** Of the 146 `.rsb` names in the exe, only 12 are absent from disc and all 12 are cubemap-face suffixes (`_bk`, `_dn`, `_fr`, `_lf`, `_rt`, `_up`, `_snapshot`) plus `2d.rsb`, `sniper_stub.rsb`, `ike_fx_fire_type3.rsb`, `tZ9rocket_smoke.rsb`, `Ehud_merc_teamgraphic.rsb`.

**10. Dead subsystems and build leftovers in the retail exe.**

* **A replay system that ships dead:** `JournalRecordStart/Stop`, `JournalPlayStart/Stop`, `JournalPlayer`, `defaultReplay.rpf`, path `data/save/replay/`. **No `.rpf` file and no `data\save\replay\` directory exist on disc.** `.rpf` is the only file extension the exe names that has zero instances on disc.
* **Directories the exe expects that are absent:** `data\save\custom`, `data\save\logs`, `data\save\replay`, `data\save\script`, `data\temp`, `data\patch.tmp`. Only `game` and `loadouts` exist.
* **Loadout slots:** the exe names 10 (`{rainbow,mercenary}_{assault,demo,noclass,recon,sniper}.load`); only `rainbow_assault.load` and `rainbow_noclass.load` exist — the rest are created at runtime.
* **Build paths in retail:** `c:\CCBuilds\NimitzPC\NimitzPC\nimitz\Release\NimitzFastr.pdb`, `C:/develop/nimitz/nimitz/release/`, and ~12 `c:\ccbuilds\nimitzpc\...\code\{ai,main,simulation}\*.cpp` assert paths. The engine codename is **Nimitz**.
* **`host0:`** (file `0x51967c`) — a PS2 devkit path prefix left in the PC build, alongside the PS2 font, PS2 controller art and `.psx` string already noted.
* **`data\model\ExportDebug.txt`** — a NED exporter debug log shipped in retail (`[DEBUG | WriteMap::PostProcessModelGeometry | 1681] Chunk: 3p_sn_psg1`).
* **`testapp.exe` is byte-identical to `lockdown.exe`** (both md5 `e237456d7a43d13f11d63bca377ddffa`). Build `v4.0.18.135 Retail`. Despite the Steam `.bind` section, `.text` is not encrypted (entropy 6.47, readable code at `0x1000`).

**11. Two bindable actions that ship unbound.** `toggle_scoreboard` (exe file `0x50c9fc`; `strings.txt:148` `"toggle_scoreboard" "Scoreboard"`, line 195 `"Display the scoreboard for current Multiplayer game"`) and `holding_breath` (exe file `0x50cb28`; `strings.txt:129` `"holding_breath" "Steady Sniper Rifle"`). Both exist in the engine and in the localisation table but appear nowhere in `data\keys.xml`. The reverse check is clean — every action in `keys.xml` is named in `strings.txt`. **Adding these two to `keys.xml` is the cheapest real feature-unlock in the whole dossier.**

**12. Script responses that exist but no shipped mission uses.** The exe registers 174 `ScriptResponses::*` and 36 `ScriptQueries::*` in named categories (file `0x52b080`–`0x52b18c`), and the last category is literally **`Cheats`**. Available and unused: `AmmoUnlimited` / `AmmoLimited`, and the full `Set/ClearInvincibility{Team,Platoon,Company,Actor}To{…}` cross-product (12 pairs) beyond the handful the missions use. Nine shipped scripts already use Invincibility (`m02_sec_02, m03_sec_02, m06_sec_01, m08_sec_03, m10_sec_02, m12_sec_03, m16_sec_03, m16_sec_04, tr_target_range`). Caveat from the mission section: `.rsc` is what the runtime consumes, so editing a `.script` alone is very likely inert.

**13. Cut mode × map combinations.** MP map filenames follow `<map>_<mode>_<name>.mis` with `f4a` = free-for-all, `ta` = team adversarial, `rt` = retrieval, `rv` = rivalry. `mp01cl_747` and `mp02cl_mint` ship only `f4a` + `ta`; `mp03cl_bunkers` and `mp09_wastland` ship `f4a` + `rt` + `ta` but **no `rv`**. `mp04`–`mp08` ship all four. Rivalry is missing on 4 of 9 maps, Retrieval on 2 of 9.

---

## Open questions

Ordered by how much they should change the GUI's design.

1. **What goes inside a `mods\<name>\` folder, and does it override `data\`?** The loader is proven (`RSModsMgr`, `ModsCont.txt`, `ModsSet.txt`, `-modset`, the whole MP negotiation UI), but no mod folder ships, so the directory layout and the override semantics are unknown. **This is architectural.** Cheapest test: create `mods\Test\ModsCont.txt` with `NAME`/`AUTHOR`/`VERSION`, launch with `-modset`, and see whether the Mods menu lists it. That test needs the game run, which was out of scope here.
2. **How is the developer console opened?** GUESS `~`, from `modeConsole` + the tilde/Esc gap in the 103-entry key table + `readme.txt:204`. If it opens, `god`, `showPlayerTracers`, `showShadowMap` and 67 tunable variables become a runtime companion to the file editor. Needs one launch.
3. **Does editing a `.script` do anything without recompiling the `.rsc`?** The `.rsc` is the compiled form the runtime consumes; its string table matches the `.script`'s 101 times out of 101. If `.script` is inert, the entire scripting surface — including `ConsoleCommand`, `AmmoUnlimited` and the Invincibility family — is out of reach without a compiler. Assume inert until proven otherwise.
4. **`spreadAngle` units are inconsistent.** Player shotguns use `0.15`–`0.3`; `e_*` shotguns use `0.10472`, `0.139626`, `0.174533`, `0.261799` — exactly 6°, 8°, 10°, 15° in radians. Either the player files use different units or they are mis-authored. Do not ship a degrees slider until this is settled.
5. **Is `CmbtModl.xml`'s `<Wounded>` block live?** All six values ship at `0`, so it cannot be tested from data alone. Needs a runtime test or a look at the parser.
6. **What does `Difficulty="2"` vs `"3"` on `<ActorSpawnData>` actually mean?** GUESS: a bitmask of tiers (3 = both, 2 = harder only), consistent with the two-tier `Normal`/`Challenge` model. The reading code was not located. It matters because it is the mechanism behind "more enemies on hard".
7. **What does `water1 1` / `water1 2` print?** The command, the `"God!Mode"` key and the `dst[i] = src[i] - key[i % keylen]` decoder are all proven; the Python re-implementation did not yield readable text. Unfinished, not empty.
8. **`data\shell\*.rsres` (32 files) are an undocumented container.** `strings.rsres` and `preload_textures.rsres` were read by string-scraping — which worked well enough to recover the asset-key table — but the record structure is unparsed. `briefings.rsres`, `credits.rsres`, `eula.rsres`, `filtered.rsres`, `nimitz.rsres`, `font.rsres` are unopened. `nimitz.rsres` (321 KB) holds the bulk of the UI text.
9. **RSB *writing* is unimplemented.** Everything here is read-only decode. Re-encoding DXT1/DXT5 and rebuilding the v10 variable-length trailer is unsolved, so "re-skin the game's menus" is not yet possible — only "skin the GUI with the game's art".
10. **Which background is the main menu?** Only `background00` has a string key and it is `kLoadingBackground`; the rest come from the `background%.2d.rsb` format string at exe offset `0x5324f8`. The indexing rule is unproven.
11. **`NED Guide.doc`** (1.26 MB in the game root) is the level-editor manual. ~34 KB of text was extracted from the OLE stream with no hits for console/cheat/debug/command-line, but the file is fast-saved and needs a real `.doc` parser. It is the most likely place the mod-folder layout is documented.

### Resolved along the way

`virus_grenade.prj`'s `<VirusBombData>` (item 4 of the earlier draft) — read; it is the only non-zero instance on disc. The `.itm` inventory — exhausted, all seven files. Whether extra game modes or difficulty tiers hide in the exe — no, verified against the token tables. Whether `strings.txt` is live — yes, `lockdown.exe` names it.

---

## Suggested build order for the GUI

Ranked by value ÷ risk, all from findings above.

1. **Weapon editor** — `data\equip\*.gun`. Biggest surface, cleanest schema, per-attachment-variant tabs. Split the list into Player (42) and Enemy (45) tabs; the `e_` prefix and `usableBy` make that automatic.
2. **Global difficulty panel** — four sliders that fan out over many files: enemy `BaseAccuracy` (writes 42 identical `e_*.gun` blocks), enemy `damageMin`/`damageMax` (45 files), `badguys.acm` `Normal`/`Challenge`, and `.cgs` `AISkillLevel` by archetype. This is the "Tom Clancy Mod Studio" headline feature and it is all one screen.
3. **Kit editor** — `data\kits\*.wsf`. Four slots, a weighted list per slot, a dropdown populated from `data\equip\`. Trivial schema, high visible impact. Ship the two broken references (`rpg7virus.gun`, `terrorist-01_smg_sa_lowfrag.wsf`) as a validation warning.
4. **Unlock toggles** — a checkbox page: the six MP-only items into SP, `toggle_scoreboard` and `holding_breath` into `keys.xml`, `usableBy` promotions, `<UsableInGameModes>` flips, and the `descriptionTasg` typo fix.
5. **Options / HUD panel** — `options.xml`, including the `<debug>` block and the 12 `hudTheme*` colours.
6. **Mission enemy-count editor** — `<Actor>` counts, `<Pool Size>`, `<SpawnArea SpawnCount TeamSize>`. Higher risk: the `.mis` files are large and the tag soup must round-trip byte-exactly.
7. **Not yet:** anything touching `.script`/`.rsc`, RSB writing, or restoring `m13_sec_02`.

Whatever order it ships in: **back up `data\` before the first write, use a tolerant tag-soup reader that preserves repeated attributes and CRLF, and resolve open question 1 first** — a `mods\` folder would make the whole backup-and-restore design unnecessary.

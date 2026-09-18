# Ike-engine mod-lever dossier — Ghost Recon (2001) + The Sum of All Fears

Scope: `E:\SteamLibrary\steamapps\common\Ghost Recon` (GR) and
`E:\SteamLibrary\steamapps\common\The Sum of All Fears` (SOAF).
Read-only session. Every claim below cites a file read this session.
Anything not directly observed is marked **GUESS**.

---

## Mod system

### How the game finds a mod

`GhostRecon.exe` string blob at file offset 0x4bcbc0 (byte scan this session)
contains, contiguously:

```
ModsSet.txt ; \modscont.txt ; \*.* ; mods ; \mods\mp2 ; \mods\mp1 ; RSMods
// MODS SETTINGS - LIST OF MODS ACTIVE ON THIS SYSTEM
```

So the loader enumerates `\mods\*.*`, reads `<dir>\modscont.txt` in each
candidate, and persists the active set to `ModsSet.txt` in the game root, whose
header literal is the same string. `\mods\mp1` and `\mods\mp2` are baked-in
defaults.

`Ghost Recon\modsset.txt`:
```
// MODS SETTINGS - LIST OF MODS ACTIVE ON THIS SYSTEM
"\mods\mp1"
"\mods\mp2"
"\mods\heroes unleashed"
"\mods\ps2accuracy"
```
`The Sum of All Fears\modsset.txt` holds only the comment line — no mods active.

**Order = priority, last wins.** Evidence:
`Ghost Recon\Mods\Heroes Unleashed\OPERATORS MANUAL.HTML` instructs: *"Make sure
ACTIVE MODS now look like below, with Heroes Unleashed as the last entry"*. The
activation UI is Options -> Mods tab -> ACTIVATE (same file). `Mods\Origmiss` is
never listed in modsset.txt — it is the implicit base layer.

### `ModsCont.txt` — the manifest

Exactly five keys. `Data\ModsCont.txt` (both games, identical):
```
// Mods Contents
NAME		"Ike Base Data"
AUTHOR		"Red Storm Entertainment"
SUPPORT		"http://www.redstorm.com/"
VERSION		"1.00"
MULTIPLAYER	"Server-Client"
```
`GhostRecon.exe` @0x4bd2b0 carries the parser's key table verbatim:
`CLIENT-SIDE . SERVER-SIDE . ModsCont.txt . MULTIPLAYER . VERSION . SUPPORT . AUTHOR . NAME`.

Observed `MULTIPLAYER` values in shipped files: `"Server-Client"` (Origmiss, Mp1,
Mp2, Heroes Unleashed, all three SOAF HRT mods) and `"Server-Only"`
(`Mods\PS2Accuracy\ModsCont.txt`).

### Minimum viable mod — ground truth

`Ghost Recon\Mods\PS2Accuracy` is the user's own working mod. Whole contents:
**51 files** = `ModsCont.txt` + `Equip\` only. No Actor, no Mission, no Model, no
Textures.

```
// Mods/PS2Accuracy/ModsCont.txt
NAME		"PS2 Accuracy - Reduced Enemy Accuracy"
AUTHOR		"Mod"
SUPPORT		""
VERSION		"1.0"
MULTIPLAYER	"Server-Only"
```

**A mod is a sparse overlay. It does not have to be complete.** Minimum = a
folder under `Mods\` containing `ModsCont.txt` plus whatever subset of the
Origmiss folder tree you want to shadow, at the same relative path.

### The PS2Accuracy technique (copy this pattern)

It does not overwrite stock guns. It does two things:

1. Adds **new** `*_npc.gun` files that are copies of the stock gun with every
   accuracy field multiplied by 4. Stock `Mods\Origmiss\Equip\ak47.gun` vs
   `Mods\PS2Accuracy\Equip\ak47_npc.gun`:

   | field | stock | PS2Accuracy | ratio |
   |---|---|---|---|
   | RunStandAccuracy | 1200 | 4800 | 4x |
   | RunCrouchAccuracy | 1500 | 6000 | 4x |
   | RunProneAccuracy | 500 | 2000 | 4x |
   | WalkStandAccuracy | 120 | 480 | 4x |
   | WalkCrouchAccuracy | 200 | 800 | 4x |
   | ShuffleStandAccuracy | 72 | 288 | 4x |
   | StationaryStandAccuracy | 24 | 96 | 4x |
   | StationaryCrouchAccuracy | 20 | 80 | 4x |
   | StationaryProneAccuracy | 15 | 60 | 4x |

   Every other tag is identical. **Higher number = worse accuracy** (wider cone).

2. Shadows the **kit** files the enemies use so they point at the new guns.
   `Mods\Origmiss\Equip\ak47 only.kit` has `<ItemFileName>ak47.gun`;
   `Mods\PS2Accuracy\Equip\ak47 only.kit` has `<ItemFileName>ak47_npc.gun`.

This is the correct generic recipe for "nerf/buff the enemy only": the player's
kits live in `Kits\<class>\*.kit`, the enemies' kits live in `Equip\*.kit`, so
redirecting `Equip\*.kit` hits enemies without touching the player.

### How Mp1 / Mp2 / Heroes Unleashed differ

| mod | ModsCont NAME | folders | file count | what it is |
|---|---|---|---|---|
| `Mods\Origmiss` | "Ghost Recon" | Actor Briefings Character CommandMaps Equip Kits Map Mission Model Save Sound Temp Textures Video | ~5000 | base campaign, implicit, never in modsset.txt |
| `Mods\Mp1` | "Desert Siege" | same + Shell | full | standalone campaign (d01..d08, dp01..dp05), own `Shell\strings.txt`, own `Equip\CmbtModl.xml` |
| `Mods\Mp2` | "Island Thunder" | same + Attachments + Shell | full | standalone campaign (c01..c08, cp01..cp05); only stock data using `Hard="0"` (16 occurrences) |
| `Mods\Heroes Unleashed` | "HU - Brighter Night Vision" | actor attachments briefings character commandmaps equip kits map mission model motion save shell sound textures video + XTRAS | **~136,000 files** (equip alone 71,504) | total conversion; also ships `OPERATORS MANUAL.HTML`, `QUICK START.HTML`, and an `XTRAS` archive of the GR demo/manual/media/modding tools |
| `Mods\PS2Accuracy` | user mod | Equip only | 51 | sparse overlay |

Note `Mods\Origmiss` (GR) has **no** `Shell` folder — GR's shell lives in
`Data\Shell`. Mp1/Mp2/HU each ship their own `Shell\strings.txt`, i.e. a mod
overrides menu text by shadowing `Shell\strings.txt`.

### SOAF's `HRT_ACU` / `HRT_Camo` / `HRT_Urban`

All three have an identical file list (`Mods\HRT_*`), 18 files each:
```
Character/Team Members/Black Team.rsb
Equip/benelli_m1.gun  Equip/jackhammer.gun
Equip/sawed_off_sg.gun  Equip/underbarrel_sg.gun
ModsCont.txt
Shell/Art/main_menu-01.rsb .. main_menu-05.rsb
Textures/billboard_effect7_01.rsb .. _07.rsb
```
ModsCont: `NAME "HRT Uniform Mod(ACU)" / AUTHOR "Wildcat" /
SUPPORT "wildyjpn@hotmail.com" / VERSION "1.0" / MULTIPLAYER "Server-Client"`.
They are mostly re-skins (one character texture + the five main-menu backdrops +
shotgun muzzle billboards) — **but they are also a stealth weapon buff.** All
three shadow the same four shotgun `.gun` files, with identical changes. Diffed
`Mods\Origmiss\Equip\jackhammer.gun` vs `Mods\HRT_ACU\Equip\jackhammer.gun`:

| tag | stock | HRT_* |
|---|---|---|
| `MaxRange` | 50.0 | **80.0** |
| `VelocityCoefficient0` | 250 | **450** |
| `KillCoefficient1` | 0.1 | **0.8** |
| `KillCoefficient2` | 0.004 | **0.005** |
| `ProjectileCount` | 6 | **8** |
| `MuzzleFlashScale` | 2.5 (benelli 3) | 5 |

`benelli_m1.gun` shows the same deltas. This is a good cautionary example for the
GUI: a mod advertised as a uniform pack silently changes ballistics, so the
manager should diff-report what a mod actually touches, not trust its NAME.

It also pins down `<ProjectileCount>` as the **shot-pellet count** — in GR every
stock gun has `ProjectileCount` 1 with `ProjectileSpread` 0, so the tag looked
inert there; SOAF's shotguns prove it is live.

SOAF's data layout differs from GR: **all** of SOAF's game data is under
`Mods\Origmiss\` (including `Shell\strings.txt` and `Outfits\`); `Data\` holds
only Model / Motion / Save / Shell / Temp / Textures / Video.

---

## Levers

Value ranges below are measured across the whole shipped corpus by script
(`scratchpad\script\agg.py`, `atrsum.py`, `miscount.py`), not sampled.

### A. Which fields the engine actually reads

Method: byte-search for each NUL-terminated tag literal in `GhostRecon.exe` and
`SOAF.exe`. Selected results:

| tag | GhostRecon.exe | SOAF.exe |
|---|---|---|
| ArmorLevel, Weapon, Stamina, Stealth, Leadership, KitPath, ActorName | yes | yes |
| ClassName | yes | **no** |
| VoiceType | **no** | yes |
| Class0..Class5, MapSize | yes | **no** |
| AvailableOutfits, KitFileName, DescriptionToken, UnlockedOutfits | **no** | yes |
| UnlockedHeroes | yes | **no** |
| Easy, Normal, **Hard**, Allied, Hidden, Stance, Idle, Lvl, Plan | yes | yes |
| all `.gun` / `.kit` / `.prj` / `.itm` tags tested | yes | yes |
| `FolderName` (in GR .atr), `Female` (in SOAF .atr) | **absent from both exes AND from igor.exe** | — |

Two consequences: `<FolderName>` and `<Female>` are **dead tags** — present in
shipped data, parsed by nothing. And `Hard="0"` **is** supported by
GhostRecon.exe even though no base-GR mission uses it, so a manager may add it.

### B. Telling enemies from the player's squad from allies

| | Ghost Recon | Sum of All Fears |
|---|---|---|
| player squad actors | `Actor\rifleman\`, `Actor\demolitions\`, `Actor\heavy-weapons\`, `Actor\sniper\` (76/59/60/40 files) + `Actor\hero\` (12) | `Actor\Team Members\*.atr` (23 files) |
| tell | `<KitPath>` non-empty (`rifleman`, `heavy-weapons`, `demolitions`, `sniper`, `hero\<name>`) and `<ActorName>` is a real person's name | `<KitPath>team</KitPath>`, real names ("Daniel Hsu"), stats 5/5/5 |
| enemies | `Actor\*.atr` at the root (562 files) | `Actor\*.atr` at the root (448 files) |
| tell | `<KitPath/>` empty, `<ActorName>` = "a Russian" (x496) / "a Georgian Rebel" (x52); filename encodes tier `mNN_rec_` / `mNN_vet_` / `mNN_eli_` = recruit/veteran/elite | `<ActorName>` is a `@TOKEN` (`@SOLDIERNAME` x143, `@MILITIANAME` x67, `@SMUGGLERNAME` x31 …), no `<KitPath>` |
| MP | `Actor\MP Actor Files\Platoon 1..4` (4 each) | `Actor\MP Actor Files\Platoon 1..4` (2 each) |
| allies in a mission | `Allied="1"` on a Company/Platoon/Team in the `.mis`, Company `Name` literally "Friendlies" | same |

**`ClassName` is NOT the discriminator.** Of GR's 825 `.atr`, 624 say
`demolitions` — including nearly every enemy. The four values are `demolitions`,
`rifleman`, `support`, `sniper`. SOAF `.atr` has no `ClassName` at all.

### C. The lever table

| name | game | file glob | tag/attribute | stock value(s) | effect | confidence |
|---|---|---|---|---|---|---|
| Enemy count per difficulty | both | `Mods\*\Mission\*.mis` | `<Actor ... Easy="0" Normal="0" Hard="0">` | GR base 759 actors; 437 Easy / 654 Normal / 759 Hard | `="0"` removes that actor at that difficulty; absent attribute = present. Easy/Normal/Hard = **Recruit/Veteran/Elite** in the UI (`Data\Shell\STRINGS.RES` @128873: `Difficulty: / Recruit / Veteran / Elite`) | high |
| Enemy roster (add/remove/move) | both | `*.mis` | `<Company>/<Platoon>/<Team>/<Actor>` | see table in section D | full order of battle in plain text: `File="m01_vet_ak47_6.atr" Kit="ak47 only.kit" Pos="-31.48;-151.60;8.65;" Facing="0.02"` | high |
| Enemy AI plan | both | `*.mis` | `Plan="262"` on `<Team>` | 244 occurrences in GR base | indexes the mission's `<PlanList>` | medium |
| Enemy start pose / idle | both | `*.mis` | `Stance="1..3"`, `Idle="0..11"`, `Hidden="1"` | Stance 1 x16, 2 x3, 3 x1; Hidden x12 | — | medium |
| Enemy skill (per actor) | both | `Actor\*.atr` | `<Weapon> <Stamina> <Stealth> <Leadership>` | integer **1..7**. GR Weapon dist 1:147 2:265 3:203 4:150 5:56 6:2 7:2. SOAF skews higher: Weapon 5:173 7:59 | AI competence | high |
| Enemy toughness | both | `Actor\*.atr` | `<ArmorLevel>` | **0..3**. GR 0:5 1:297 2:311 3:210. SOAF 0:108 1:126 2:239 3:6 | indexes `BallisticArmoredChestFactor0..3` | high |
| Enemy model / face | both | `Actor\*.atr` | `<ModelName> <LOD2> <LOD3> <ModelFace> <BlinkFaceName>` | GR 71 distinct models; SOAF 57 | re-skin without touching textures | high |
| Global hit-location lethality | both | `Mods\*\Equip\CmbtModl.xml` | `Ballistic{Head,Chest,Abdomen,UpperArm,LowerArm,UpperLeg,LowerLeg}Factor` | GR Origmiss 10/100/400/700/1000/500/800 | lower = more lethal. Heroes Unleashed ships `BallisticHeadFactor -1.0` and 1350/2050/900/1800 limbs | high |
| Armour effectiveness | GR Mp1/Mp2 + SOAF | `Equip\CmbtModl.xml` | `BallisticArmoredChestFactor0..3` | Mp1/Mp2 0/150/350/**750**; SOAF 0/150/350/**550**; HU 0/400/750/950. **Absent from GR Origmiss** but parsed by GhostRecon.exe | per-ArmorLevel chest lethality | high |
| **Global difficulty multipliers** | **SOAF only** | `Mods\Origmiss\Equip\CmbtModl.xml` | 11 tags, see below | — | see below | high |
| Weapon accuracy (12 fields) | both | `Equip\*.gun` | `{Run,Walk,Shuffle,Stationary}{Stand,Crouch,Prone}Accuracy` | GR across 63 guns: Run/Stand 300..3000; Walk/Stand 45..1000; Shuffle/Stand 30..400; Stationary/Stand 2..50; Stationary/Prone 0.5..20 | dispersion, **higher = worse**. The axis PS2Accuracy uses | high |
| Recoil | both | `Equip\*.gun` | `<Recoil>` | 1.5..120 (AK47 68, M9SD 90) | per-shot kick | high |
| Rate of fire / fire modes | both | `Equip\*.gun` | `<Selective><SelectiveOption RateOfFire RoundsPerPull IsFullAuto StartSound EndSound/>` | RateOfFire 30..1800 (600 x36, 700 x23, 650 x13); RoundsPerPull 1/2/3; IsFullAuto 1 | each `<SelectiveOption>` = one selector position; add/remove to add/remove burst | high |
| Magazine size | both | `Equip\*.gun` | `<MagazineCapacity>` | 1..30000 (30 x23, 1 x9, 20 x6, 100 x3, **30000 x2**) | 30000 = mounted/vehicle gun | high |
| Range & ballistics | both | `Equip\*.gun` | `<MaxRange>`, `<VelocityCoefficient0/1/2>` | MaxRange 1..500 (475 x17, 373 x11); V0 1..930.571 | muzzle velocity vs distance, V(d)=V0+V1·d+V2·d² — **GUESS** on the polynomial form (V0=713 for 7.62x39 is physically right) | medium |
| Lethality per weapon | both | `Equip\*.gun` | `<KillCoefficient1>`, `<KillCoefficient2>` | K1 ∈ {-0.6,-0.1,0.2,0.5,1}; K2 ∈ {0.002,0.004,0.015,1} | pistols K1=-0.1, rifles 0.2, 7.62/grenade 0.5 | medium |
| Zoom / optics | both | `Equip\*.gun` | `<ZoomSettings><Zoom>` repeated | 1..15 (1 x80, 2 x24, 5 x9, 10 x4, 15 x2) | each `<Zoom>` = one magnification step | high |
| Silencer / tracers / flash | both | `Equip\*.gun` | `<Silenced>` 0/1, `<TracerFrequency>` 0..5, `<MuzzleFlashScale>` 0..4 | Silenced=1 on 4 of 63 GR guns | — | medium |
| Handling / sway | both | `Equip\*.gun` | `<TurnBandVelocity1..5>` / `<TurnBandMultiplier1..5>`, `<StabilizationTime>` | V5 always 100000, M1 always 1; StabilizationTime 0.1..1.5 | sway penalty bands vs turn rate; settle time | medium |
| Underbarrel launcher | both | `Equip\*.gun` | `<HasUnderbarrelWeapon>` + `<UnderbarrelWeaponName>` | 6 guns: gp25, m203, glforoicw, gp25_for_an94, gp25_for_groza, player_gp25 | — | high |
| Reticle art + pip geometry | both | `Equip\*.gun` | `<ReticuleTextureName>` + 9 `Reticule*` numbers | 8 distinct textures (reticle_ar / car / sr / gl / lmg / pistol …) | HUD crosshair per weapon | high |
| Loadout contents | both | `Equip\*.kit`, `Kits\**\*.kit` | `<Firearm SlotNumber>`, `<HandHeldItem SlotNumber>`, `<ThrownItem SlotNumber>`, each with `<ItemFileName>` | GR slots 0..1; **SOAF slots 0..3** | add / remove / replace items freely — just add another element | high |
| Ammo carried | both | `*.kit` | `<MagazineCount>`, `<Count>`, `<ExtraAmmo>` | GR MagazineCount 2..20 (10 x45, 2 x28, 5 x24); Count 1..6; ExtraAmmo 2..15. SOAF MagazineCount 1..30, Count 1..20 | mags for firearms, units for thrown/handheld | high |
| GL flag | GR | `*.kit` | `<GrenadeLauncher>1</GrenadeLauncher>` | 6 kits | pairs slot 0 rifle with slot 1 launcher | high |
| Kit icon | both | `*.kit` | `<KitTexture>` | `kit_rifleman-01.rsb` etc.; SOAF uses it once | menu thumbnail | high |
| Squad roster & size | both | `Mission\*.toe` | `<Company>/<Platoon>/<Team>/<Actor File= Kit= Owner= Pos=>` | GR `M_avatar.toe`: Alpha 3 + Bravo 2 + Charlie 1 = **6** | the player's order of battle. `Owner="0"` marks the avatar. `IgorScripting.txt`: *"No fire team can have more than six actors"* | high |
| Squad-member stats | both | `Actor\<class>\*.atr` (GR), `Actor\Team Members\*.atr` (SOAF) | same 4 skills + ArmorLevel | SOAF team members Weapon/Stamina/Stealth 5/5/5, Leadership 2, ArmorLevel 2 | player-side skills | high |
| Per-mission kit-class allowance | GR only | `*.mis` `<Shell>` | `<Class0>..<Class5>`, `<CombatPoints>` | Class0=1 and Class1=1 on every campaign mission; Class2..5 ∈ {1,2,3} or absent; CombatPoints 1,1,2,2,2,3,3,4,4,5,5,6,6,7,7 across m01..m15 | **GUESS**, unresolved — see Open questions | low |
| Per-mission loadout allowance | SOAF only | `*.mis` `<Engine><AvailableOutfits><OutfitFile>` | m01: hrt_stealth / hrt_assault / hrt_breach (143 entries over 18 missions) | restricts which outfits the mission offers | high |
| Outfit definition | SOAF only | `Mods\Origmiss\Outfits\*.off` | `<NameToken> <DescriptionToken> <KitFileName>` (x3) | `hrt_assault.off` -> `hrt_assault.kit` listed three times | 15 outfits shipped | high |
| MP kit-restriction presets | GR | `Kits\*.kil` | `<KitRestriction Name="..."><Actor Name="..."><Kit Name="..."/>` | `grenades_only`, `no_explosvies` *(sic)*, `no_restrictions`, `no_sensors`, `pistols_only`, `primaries_only` | maps every MP actor to a forced kit. SOAF has 7 `.kil` | high |
| Mission unlocks | both | game root `unlocked_missions.xml` | `<UnlockedMissions><Mission>` | GR 18 entries; SOAF only 4 | **save state, not a ship-time gate** — see the caveat below the table | high |
| Hero unlocks | GR only | game root `unlocked_heroes.xml` | `<UnlockedHeroes><Hero>` | 3 of 12: nigel_tunney, jack_stone, buzz_gordon | save state; 12 heroes exist in `Actor\hero\` | high |
| Outfit unlocks | SOAF only | game root `unlocked_outfits.xml` | `<UnlockedOutfits><Outfit>` | 9 listed, 15 `.off` present | save state | high |
| Menu/mission text by numeric ID | both | `Data\Shell\STRINGS.RES` (binary) | `NameId = (groupIndex << 20) \| entryIndex` | GR 148,084 B / 83 groups; SOAF 128,949 B / 46 groups | every `<NameId> <MapNameId> <LocationId> <DateId> <TimeId> <BriefingId>` in a `.mis` resolves here. Format below | high |
| Campaign order / hero award | GR | `Mission\campaign.xml` | `<Mission><Filename>` + `<Hero>` | 15 missions; m13/m14/m15 have **no** `<Hero>` | reorder or extend the campaign | high |
| Campaign order / intel unlocks | SOAF | `Mission\campaign.xml` | `<Mission><Filename>` + `<IntelEntry Bitmap NameToken DescriptionToken/>` | 11 missions, 20 IntelEntry rows (m01 has 1, m03 has 3, rest 2) | a collectible intel/news dossier system keyed to `Shell\strings.txt` tokens (`M03_INTEL_2_NAME` …) and `Briefings\*.rsb` art. `training.mis` and `t01..t07` are **not** in campaign.xml | high |
| Grenade / explosive tuning | both | `Equip\*.prj` | `<BlastRadius> <DelayTime> <DetonateOnImpact> <AirResistanceConstant> <CombatCoefficientV0/V1/V2/K1/K2>` | frag.prj: radius 10.0, delay 4.0, V0 930.571, K1 0.5, K2 0.002 | — | high |
| Handheld items | both | `Equip\*.itm` | `<Type> <Weight> <BlastRadius> <CombatCoefficient*>` | GR: beercan, binoculars, bomb, cigarette, claymore, pda, sensor | — | high |
| HUD / gameplay toggles | both | game root `options.xml` | `<ThreatIndicatorEnabled> <IFFType> <ScaleHUD> <ScaleCommandMap> <ShowFrameRate> <BloodOn> <ShowDeadBodies> <AutoAssignStats> <InitialRateOfFire> <AlwaysRun> <ReticuleColorR/G/B> <ReticuleIFFColorR/G/B>` | GR IFFType=RETICULE; SOAF IFFType=OFF plus `<AutoReloadOn> <UseDefaultPlan> <AutoTarget> <HeartbeatAlwaysOn>` | player settings, per-install not per-mod | high |
| Menu backdrop selection | both | `options.xml` | `<ShellBackgroundIndex>` | GR 2, SOAF 4 | picks one of the five `main_menu-0N` / `shell_bgd-0N` sets | medium |
| Menu text / weapon names | both | `Shell\strings.txt` | `"TOKEN"  "display text"` | GR `Data\Shell\strings.txt` 242 lines; SOAF `Mods\Origmiss\Shell\strings.txt` 178 lines | `<NameToken>WPN_AK47</NameToken>` in a `.gun` resolves here. SOAF also has `WPN_*_desc` entries with full paragraph descriptions | high |
| Shot pellet count | SOAF (live), GR (present, inert) | `Equip\*.gun` | `<ProjectileCount>`, `<ProjectileSpread>` | GR: 1 / 0 on all 25 guns that have it. SOAF shotguns: 6, buffed to 8 by the HRT mods | pellets per trigger pull | high |
| Weapon menu icon | SOAF | `Mods\*\Shell\Equip\<name>.rsb` | (image) | 36 icons, one per weapon/item, + `no_item.rsb`, `no_weap.rsb` | a new weapon needs an icon here or the loadout screen has a hole | high |
| Vehicles | both | `Actor\*.vcl` | (not parsed this session) | GR 9 (`apc_bmp.vcl`, `humvee.vcl`, …), SOAF 2 | — | low |

#### Caveat: the three `unlocked_*.xml` are SAVE STATE, not content gates

`unlocked_missions.xml` (GR, modified 2026-03-02), `unlocked_heroes.xml` (GR,
2026-01-25) and `unlocked_outfits.xml` (SOAF, 2026-03-03) carry recent
modification times, against a uniform 2024-12-21 / 2025-10-31 date on every
shipped data file. They record **this install's campaign progress**. A GUI may
still write them as an "unlock everything" button, but must not present their
contents as evidence of what the game shipped locked. It also means GR's
`unlocked_missions.xml` listing `bb01_woods_day.mis` / `bb02_woods_night.mis` is
a trace of a Heroes Unleashed playthrough, not of cut retail content — see
Cut content.

#### `STRINGS.RES` binary format (cracked)

```
u32 groupCount
per group:  u32 nameLen; char name[nameLen]; u8 NUL; u32 entryCount;
            per entry: u32 len; char s[len]; u8 NUL; u8 pad;
            u32 trailer(0)
```
`NameId = (groupIndex << 20) | entryIndex`. Verified against
`Mods\Origmiss\Mission\m01_caves.mis`: `<MapNameId>17825793</MapNameId>` =
`0x1100001` -> group 17 (`Mission17`) entry 1 = `'M01 Caves'`, and
`<NameId>17825794</NameId>` -> entry 2 = `'M01 - Iron Dragon'`.
Group names are `GameType<N>`, `Mission<N>`, plus GR-only `String` (632 entries),
`Resource` (22), `ShellScenes` (1), `ActionKeys` (52), `Credits` (261),
`PowellCredits` (243), `KincadeCredits` (246), `CreditsImages` (25),
`Options` (100), `UISounds` (6). Full dumps in
`scratchpad\cut\GR_strings_res.txt` and `SOAF_strings_res.txt`.

(`PowellCredits` and `KincadeCredits` are Desert Siege's and Island Thunder's
internal codenames, preserved as group names.)

#### SOAF-only global difficulty block

`The Sum of All Fears\Mods\Origmiss\Equip\CmbtModl.xml` (`<VersionNumber>1.100000`):

```
<ArcadeModeKillChanceFactor>0.500000</ArcadeModeKillChanceFactor>
<RecruitFriendlyKillChanceFactor>0.500000</RecruitFriendlyKillChanceFactor>
<RecruitFriendlySkillAdjustment>2</RecruitFriendlySkillAdjustment>
<RecruitEnemySkillAdjustment>-3</RecruitEnemySkillAdjustment>
<EliteFriendlySkillAdjustment>-2</EliteFriendlySkillAdjustment>
<EliteEnemySkillAdjustment>2</EliteEnemySkillAdjustment>
<RecruitEnemyDelayFactor>1.250000</RecruitEnemyDelayFactor>
<VeteranEnemyDelayFactor>1.050000</VeteranEnemyDelayFactor>
<EliteEnemyDelayFactor>0.750000</EliteEnemyDelayFactor>
<RecruitEnemyAimFactor>1.350000</RecruitEnemyAimFactor>
<EliteEnemyAimFactor>0.750000</EliteEnemyAimFactor>
```

Skill adjustments are added to the 1..7 `.atr` skill values (**GUESS** on the
exact arithmetic, but the sign and magnitude are unambiguous: Recruit gives the
player +2 and the enemy -3). `*AimFactor` multiplies the weapon accuracy cone
(>1 = worse). `*DelayFactor` scales enemy reaction delay.

These eleven tags are **the single best global-difficulty lever in either game,
and they exist only in SOAF.** Verified by byte-scan: all 11 literals are present
in `SOAF.exe` and **all 11 are absent from `GhostRecon.exe`**. Adding them to a
GR `CmbtModl.xml` would be a silent no-op.

### D. Enemy population, measured

Counted by script over `<Units>` blocks. "hard" counts actors without `Hard="0"`.

| mission set | missions with units | total actors | Easy/Recruit | Normal/Veteran | Hard/Elite |
|---|---|---|---|---|---|
| GR `Mods\Origmiss` | 16 | 759 | 437 | 654 | 759 |
| GR `Mods\Mp1` (Desert Siege) | 8 | 332 | 211 | 282 | 332 |
| GR `Mods\Mp2` (Island Thunder) | 8 | 420 | 287 | 341 | **404** |
| SOAF `Mods\Origmiss` | 18 (11 campaign + 7 training) | 476 | 307 | 367 | **446** |

GR Origmiss per-mission (total / easy / normal): m01 43/21/28, m02 41/18/33,
m03 43/19/32, m04 43/21/34, m05 56/26/49, m06 52/36/48, m07 48/30/44,
m08 54/38/51, m09 43/21/39, m10 47/21/43, m11 45/26/40, m12 **64**/40/55,
m13 37/28/33, m14 53/42/51, m15 56/33/47, mp06_castle 34/17/27.

SOAF per-mission (total / easy / normal / hard): m01 41/30/31/36, m02 49/26/28/44,
m03 46/21/30/41, m04 43/28/34/41, m05 47/26/34/45, m06 36/25/34/36,
m07 36/25/27/32, m08 40/27/35/38, m09 36/21/27/36, m10 32/19/21/27,
m11 28/17/24/28. Training t01..t07 are 6 actors each.

The five GR `mp0*` maps and all `t0*` training maps have **zero** `<Actor>`
entries — their populations come from the game type instead.

**There is no global "enemy count multiplier" file in either game.** Single-player
enemy population is per-actor placement in `.mis`, full stop. For MP/co-op the
count comes from a script response, see the next section.

### E. Reinforcement waves — how they actually work

There is no wave/respawn *count* field. A "wave" is **pre-placed actors parked
off-map in a dedicated Team, activated by the mission script.** In
`Mods\Origmiss\Mission\m01_caves.mis` the `<Units>` block contains:

```
<Team Name = "Team - Reinforcements 1 (Camp)"> ... <Team Name = "Team - Reinforcements 2 (Caves)">
<Actor Name = "Reinforcement Camp 1" File = "m01_rec_ak47_1.atr" Kit = "ak47 only.kit" Pos = "5.98;-108.59;9.32;" Facing = "3.18"/>
<Actor Name = "Reinforcement Camp 3" ... Easy = "0" Normal = "0"/>
<Actor Name = "Reinforcement Camp 2" ... Easy = "0"/>
```
6 Camp + 6 Caves reinforcements in m01 alone, each with its own difficulty gate.
The decoded `<ScriptSource>` of the same file names the block
`Let baddies respawn from camp zone` and lists matching zones
`Shack and Camp attack Caves zone`.

`Hidden="1"` marks actors that exist but are not shown until a script
`ShowThing`. In all of GR base that is exactly 7 actors: `Refugee 1..6` plus
`R Reinforcements T1 G4`.

So the GUI's "more/fewer reinforcements" control = duplicate or delete `<Actor>`
lines inside the `Team - Reinforcements *` teams, or flip their Easy/Normal/Hard
flags. No script edit needed.

### F. The 12 GR heroes (the specialist roster)

`Mods\Origmiss\Actor\hero\*.atr`, with `Kits\hero\<name>\*.kit` alongside.
Only 3 of the 12 are in `unlocked_heroes.xml`.

| file | ActorName | ClassName | Armor | Weapon | Stamina | Stealth | Leadership | awarded by (campaign.xml) |
|---|---|---|---|---|---|---|---|---|
| `will_jacobs.atr` | Will Jacobs | rifleman | 2 | 3 | 2 | 2 | 3 | m01_caves |
| `henry_ramirez.atr` | Henry Ramirez | rifleman | 2 | 3 | 3 | 2 | 3 | m02_farm |
| `nigel_tunney.atr` | Nigel Tunney | demolitions | 2 | 4 | 3 | 3 | 2 | m03_rrbridge |
| `jack_stone.atr` | Jack Stone | sniper | 1 | 4 | 3 | 5 | 1 | m04_village |
| `guram_osadze.atr` | Guram Osadze | support | 3 | 5 | 5 | 1 | 3 | m05_embassy |
| `susan_grey.atr` | Susan Grey | rifleman | 2 | 3 | 5 | 5 | 2 | m06_castle |
| `klaus_henkel.atr` | Klaus Henkel | demolitions | 2 | 4 | 4 | 4 | 4 | m07_river |
| `buzz_gordon.atr` | Buzz Gordon | rifleman | 2 | 5 | 4 | 3 | 5 | m08_battlefield |
| `lindy_cohen.atr` | Lindy Cohen | rifleman | 2 | 6 | 3 | 4 | 5 | m09_swamp |
| `astra_galinksy.atr` | Astra Galinsky | sniper | 1 | **6** | 4 | **6** | 3 | m10_ruined_city |
| `scott_ibrahim.atr` | Scott Ibrahim | sniper | 1 | **7** | 4 | **7** | 2 | m11_pow_camp |
| `dieter_munz.atr` | Dieter Munz | support | 3 | **7** | **7** | 1 | 6 | m12_docks |

Notes for the GUI:
- The heroes are where the rare 6s and 7s in the skill distribution come from.
- **Shipped filename typo**: the file is `astra_galink**s**y.atr` but its
  `<KitPath>hero\astra_galinsky</KitPath>` and its kit folder
  `Kits\hero\astra_galinsky\` use the correct spelling. `campaign.xml` references
  the typo'd filename, so it resolves — do not "fix" the filename without also
  fixing `campaign.xml`.
- `ClassName` `support` maps to the folder name `heavy-weapons`
  (`quick_missions.qmk` lists Dieter Munz and Guram Osadze under
  `<Actor Name="heavy-weapons">`).
- `Kits\quick_missions.qmk` grants hero kits in Quick Mission for **10** of the 12
  heroes. **Will Jacobs and Buzz Gordon are absent from it** — see Cut content.

### G. Generation recipes for the GUI

Each of these is a complete, self-contained mod folder the manager can emit.
All are sparse overlays — copy the stock file, change the listed tags, write it
to `Mods\<name>\<same relative path>`, and ship a `ModsCont.txt`.

| GUI control | files to emit | edit |
|---|---|---|
| "Enemy accuracy" slider | `Equip\*_npc.gun` (new) + `Equip\*.kit` (shadow) | multiply the 12 `*Accuracy` fields; re-point `<ItemFileName>`. Exactly PS2Accuracy's shape |
| "Enemy count" slider | `Mission\*.mis` (shadow) | add / remove `Easy="0" Normal="0" Hard="0"` on `<Actor>`; or delete `<Actor>` lines outright |
| "Enemy skill" slider | `Actor\*.atr` (shadow, root folder only) | clamp `<Weapon> <Stamina> <Stealth> <Leadership>` into 1..7 |
| "Enemy armour" slider | `Actor\*.atr` root folder | set `<ArmorLevel>` 0..3 |
| "Lethality" preset | `Equip\CmbtModl.xml` (one file) | scale the 7–11 `Ballistic*Factor` values. Use HU's file as the "hardcore" preset |
| "Difficulty multipliers" (SOAF only) | `Equip\CmbtModl.xml` | the 11 Recruit/Veteran/Elite tags |
| "Squad size" | `Mission\*.toe` | add / remove `<Actor>` inside `<Team>`; max 6 per team |
| "Unlock everything" | game-root `unlocked_missions.xml`, `unlocked_heroes.xml` (GR), `unlocked_outfits.xml` (SOAF) | **not** a mod folder — these live in the game root and are save state. Back up before writing |
| "Loadout unlocks" | `Kits\**\*.kit`, `Equip\*.kit`, SOAF `Outfits\*.off`, SOAF `.mis` `<AvailableOutfits>` | add `<Firearm>` / `<ThrownItem>` elements; add `<OutfitFile>` lines |
| "Unlimited ammo" | `*.kit` | raise `<MagazineCount>` / `<Count>` / `<ExtraAmmo>` |
| "Weapon tuning" | `Equip\*.gun` | the whole 60-tag schema |
| "Menu re-skin" | GR `Data\Shell\Art\` -> `Mods\<name>\Shell\Art\`; SOAF `Mods\<name>\Shell\Art\` | replace `main_menu-0N.rsb`, `shell_bgd-0N.rsb`. **Write RSB v6 24bpp 1024x512 with the art in the top-left 640x480** |
| "Rename weapons / menu text" | `Shell\strings.txt` | `"TOKEN"  "text"` pairs |

Two traps for the generator:

- **GR base `Mods\Origmiss` has no `Shell\` folder.** A GR shell mod creates
  `Mods\<name>\Shell\...` from scratch, copying the source out of `Data\Shell`.
- **Filenames contain spaces and parentheses** (`ak47 only.kit`,
  `(coop) firefight.gtf`, `Actor\MP Actor Files\Platoon 1\`) and case is
  inconsistent (`.GUN` vs `.gun`, `.RSB` vs `.rsb` — GR Equip has 14 `.GUN` and
  18 `.gun`). Do not assume lowercase or shell-safe names.

---

## The `.gtf` / `.mis` script encoding — CRACKED

`<ScriptCompiled>` and `<ScriptSource>` appear in every `.gtf` (10 in GR base,
13 in SOAF) and every `.mis` (29 in GR base, 25 in SOAF).

**Encoding: one byte = two characters, LOW nibble first, each nibble as `'A'+n`
(A=0 … P=15).** Worked out by hand from `(sp) firefight.gtf`:
`HF JG OG AC EF FG IH EH` -> 0x57 0x69 0x6E 0x20 0x54 0x65 0x78 0x74 -> `"Win Text"`.
`PPPPPPPP` = FF FF FF FF. `BAAAAAAA` = 01 00 00 00.

Decoders written this session:
`scratchpad\script\gtfdec.py`, `gtfdec2.py`, `gtfhex.py`, `gtfstr.py`, `gtffloat.py`.
The encoding was derived twice independently in this session, by two separate
passes, reaching the identical rule (`CEFGIGFGNGPGEHIG` -> `Behemoth` in the
second pass). Treat it as settled.

**It does NOT decode to readable script text.** It decodes to a little-endian
**u32 token stream** with inline length-prefixed strings (strings are not padded,
so alignment shifts after each one). What you get is a serialised Igor
node-graph: node labels, variable names and display strings are readable; the
logic is opcode integers.

Real decode, `Mods\Origmiss\Mission\(coop) recon.gtf` `<ScriptSource>`, 1050 bytes:
```
Loss Text / Win Text / CompanyRef / Opposing Company / Objective / Objective 1
Counter / Player Count / Flag / Game Over
01: Spawn enemy force / 02: Initialize / 04: Failure condition
05: Victory condition / 03: Free hunting / 06: Update leaderboard
```
`(solo) hamburger hill.gtf` yields 38 labels including `04: Is there 1 king?`,
`08: Find high score`, `07c: End condition - 1 player left`, `12c: Assign ties`.
`<ScriptCompiled>` of the same file yields the runtime message strings:
`?Defeat!`, `?Victory!`, `?You are now king.`, `?The game has ended in a draw.`

**Editable today without an opcode table:** the embedded strings (victory/defeat
text, objective text) and the embedded float constants.

Float constants recovered from `<ScriptCompiled>` (`gtffloat.py`):

| file | floats (byte offset = value) |
|---|---|
| GR `(sp) firefight.gtf` | @33=1, **@253=15** |
| GR `(coop) firefight.gtf` | @33=1, **@253=15**, @285=1 |
| GR `(sp) recon.gtf` / `(coop) recon.gtf` | @10=764, @217=1, @385=1, **@569=15** |
| SOAF `(sp) firefight.gtf` | @33=1, @269=1 |
| SOAF `(coop) recon.gtf` | @10=764, **@605=15** |
| GR `(team) hamburger hill.gtf` | @10=764, @1202=512, @1366=128, @1910=32768, @2154=2, @2155=48 |
| GR/SOAF `(team) domination.gtf` | @10=764, @1836=512, @2080=128, @2688=32768, @6563=10 |

In `(sp) firefight.gtf` the 15.0 sits at byte 0x0f9 right after tokens
`4c 00 00 00` / `ff ff ff ff`, and the source labels that file's first block
`01: Spawn enemy force`. `IgorScripting.txt` documents
`SpawnOpposingPatrolForce — "Spawn an opposing patrol force with <size> members."`
**GUESS (medium): that 15.0 is the default enemy count for Firefight / Recon**,
overridable by the lobby (`<LobbyCfg>1</LobbyCfg>` in the same file). Not
verified in-game.

### The scripting vocabulary is documented

`Ghost Recon\IgorScripting.txt` (35 KB, "Last updated 06/25/02") is the full
trigger/response reference. Responses relevant to a mod GUI:

- `SpawnOpposingAssaultForce` — *"Spawn an opposing assault force with `<size>`
  members … No more than six humans will be assigned to a single fire team and
  spawn zone. The spawned humans will use the actor and kit files
  `opposing_force_*.*`"* — PreAction blocks only.
- `SpawnOpposingPatrolForce` — same, randomly scattered, uses map "point" zones.
- `SpawnActor` / `SpawnTeam` / `SpawnPlatoon` / `SpawnCompany` — PreAction only,
  *"No fire team can have more than six actors."*
- `UnlockHeroCharacter` — *"Unlock the next hero character in the campaign."*
- `SpottingDistanceChange`, `AmmoUnlimited` / `AmmoLimited`, `ReplenishInventory`,
  `InvincibilityOn{Actor,Team,Platoon,Company}`, `Invisibility*`, `Panic*`,
  `TeamAIOn/Off`, `PlatoonAIOn/Off`, `CaptiveActorOn`, `HostageActorOn`,
  `AwardDecoration*`, `KillActor`, `WeatherChange`, `FogOn/Off`,
  `ObjectiveAdd/Remove/Complete/Failed`, `Respawn` trigger,
  `DisableAutoendNoPlayers`, `DisableAutoendTimer`, `CompanyScoreSet`.

**Because `opposing_force_*.*` is the fixed naming convention for script-spawned
enemies, a mod that ships `Equip\opposing_force_*.kit` and
`Actor\opposing_force_*.atr` retunes every co-op and MP spawn at once** — without
editing a single script blob. That is the highest-leverage MP lever found, and
the file set is tiny:

| mod | opposing_force files |
|---|---|
| GR `Mods\Origmiss` | **12** — `Actor\opposing_force_0..6.atr` + `Equip\opposing_force_0..4.kit` |
| GR `Mods\Mp1`, `Mods\Mp2` | 14 each |
| GR `Mods\Heroes Unleashed` | **1722** (`actor\special\opposing_force\opposing_force_0..*.atr`) |
| SOAF `Mods\Origmiss` | 12 — `Actor\opposing_force_0..6.atr` + `Kits\mercenaries\opposing_force_0..4.kit` (plus 7 `.bak`) |

`Ghost Recon\Mods\Origmiss\Actor\opposing_force_0.atr`: ArmorLevel 3,
Weapon 4 / Stamina 3 / Stealth 4 / Leadership 3.

**Dev tuning leftover:** SOAF ships `opposing_force_0..6.atr.bak` beside the live
files. Diffed **all seven**: each differs from its `.bak` in exactly one line —
`<Weapon>2</Weapon>` shipped vs `<Weapon>4</Weapon>` in the backup. Red Storm
nerfed the MP spawn archetypes' weapon skill from 4 to 2 before ship and left the
originals on the disc. Restoring the `.bak` values is a ready-made
"original / harder MP AI" preset.

The eighth `.bak`, `Mods\Origmiss\Equip\30-06.gun.bak`, also differs in exactly
one line: shipped `RateOfFire = "35"` vs backup `RateOfFire = "600"` — a
bolt-action cadence fix applied late.

### Dead end, stated plainly

The opcode-to-name table is **not** in `GhostRecon.exe`, `igor.exe`,
`ScriptEd.dll`, `Data\Shell\IKE.RES` or `Data\Shell\STRINGS.RES`. Byte-searched
this session, ASCII and UTF-16, for `SpawnActor`, `DeathActor`, `ProximityActor`,
`BlockPreserve`, `ObjectiveComplete`, `UnlockHeroCharacter`,
`SpawnOpposingPatrolForce` and for the sentence templates (`"Spawn an opposing"`,
`"opposing patrol force"`, `"has been killed"`): **zero hits in every binary**,
except one incidental ASCII `has been killed` in STRINGS.RES.

So: the container is fully cracked, string and numeric constants are editable
in place today, but **re-authoring script logic would require reversing
`igor.exe` in a disassembler.** Do not promise a script editor in v1.

---

## Art

Decoded read-only to PNG in the scratchpad. Full run in
`scratchpad\art\png\` (`gr\` 96, `soaf\` 47, `gr_mods\` 14, `onblack\` 10).

### Where the art actually lives

`Mods\Origmiss\Shell\Art\` does **not** exist in either game. Real locations:

- GR: `Ghost Recon\Data\Shell\Art\` — 31 files + `credits\` (27 more)
- SOAF: `The Sum of All Fears\Data\Shell\Art\` — 34 files
- GR mods with their own menu art: `Mods\Mp1\Shell\Art`, `Mods\Mp2\Shell\Art`,
  `Mods\Heroes Unleashed\shell\art\main` and `...\backdrop`
- SOAF `Mods\HRT_*\Shell\Art\` carry replacement `main_menu-0N.rsb` only

RSB version census across each install: GR = {v9: 36209, v6: 2366, v5: 1045,
v8: 728, v4: 257, v1: 21, v2: 5}; SOAF = {v8: 1597, v5: 389, v4: 261, v6: 73,
v1: 44, v2: 5}.

### Does `tcps2\rsb.py` work unmodified? No — it fails on exactly these files

Ran unmodified (`from tcps2 import rsb; rsb.parse(data)`):

| file | result |
|---|---|
| GR `main_menu-01..05`, `shell_bgd-01..05`, `pda_bgd-01` | **`RsbError: unhandled bit mask (8, 8, 8, 0) (bpp=24)`** |
| SOAF `main_menu-01..05`, `pda_bgd-01` | **`RsbError: v8 bpp 24 (8,8,8,0) not handled`** |
| GR `pda-lcd-02`, `reticle_misc` | **`RsbError: unhandled RSB version 9 (flag 0)`** |
| GR/SOAF 16bpp and v4/5/6 32bpp | parse OK, pixels correct |
| SOAF v8 **32bpp** (`decorations`, `hud`, `pda-lcd-02`, `soaf_command_bkgrnd`, all `reticle_*`) | parses without error but **colours are wrong** |

Three causes — none of them swizzle, palette or endianness:

1. **24bpp is not implemented.** Every 1024x512 menu page in both games is
   `(8,8,8,0)` direct colour. `rsb.py` falls through to the final `else` in
   `parse()` and to the `bpp not in (16,32)` guard in `parse_v8`.
2. **Version 9 is unknown to it.** v9 = the v8 header plus 8 more bytes (0xFF
   filler in every sample), so pixels start at **+43**. Proved arithmetically:
   GR `reticle_misc.rsb` (v9) and SOAF `reticle_misc.rsb` (v8) have byte-identical
   66-byte trailers, and 131181 − 256·128·4 − 66 = 43.
3. **`parse_v8`'s 32bpp channel order is the PS2 one and is wrong on PC.** It
   reads `r,g,b,a` and doubles alpha; the PC files are `A,R,G,B` with alpha
   already 0–255. `soaf_command_bkgrnd.rsb` decodes to clean greyscale under
   ARGB and to cyan-clipped garbage (`#25FFFF`, `#40FFFF`) under RGBA. The v4/5/6
   32bpp path (`a,r,g,b`) in `rsb.py` is already correct.

Everything else in `rsb.py` holds exactly on PC: the 28-byte v<=6 header, the
35-byte v8 header, the ARGB4444 / R5G6B5 bit layouts, and the
`{4:53, 5:61, 6:65}` trailer table. Pixel bases confirmed independently by
scoring candidate bases 26–38 on mean horizontal neighbour difference — base 28
(v6) and base 35 (v8) were the minimum on every file tested.

### Header fields as they actually appear

```
v6  GR main_menu-01: 06000000 00040000 00020000 08000000 08000000 08000000 00000000
    -> ver 6, w 1024, h 512, R8 G8 B8 A0, pixels @28, trailer 65
v8  SOAF main_menu-01: 08000000 00040000 00020000 | 00000000 000000 | ..08 ..08 ..08 ..00 | 000000
    -> ver 8, w 1024, h 512, depths at +19/+23/+27/+31, pixels @35, trailer 66
v9  GR pda-lcd-02: same as v8 + 8x FF -> pixels @43, trailer 66
```

Channel layouts, determined empirically:

- **24bpp = R,G,B bytes.** Decisive test: the US flag on SOAF `main_menu-01` has
  a blue canton and red stripes under `rgb`, red canton and blue stripes under
  `bgr`. GR's jungle is green under `rgb`, cyan under `bgr`.
- **32bpp = A,R,G,B bytes (v6 and v8 alike).** GR `cmi.rsb` gives a red X and
  yellow triangle under `argb`, blue X and cyan triangle under `abgr`.
- **16bpp** `(5,6,5,0)` = R5G6B5 red-high; `(4,4,4,4)` = A4R4G4B4 alpha-high.

### Decoded results

All 1024x512 pages carry a **640x480 content region in the top-left**; the rest
is black filler (measured bounding box). Dominant colours are over the 640x480
content only.

| file | size | format | content (viewed, not guessed) | top colours |
|---|---|---|---|---|
| GR `main_menu-01` | 1024x512 (640x480 art) | v6 24bpp RGB | **Main-menu backdrop 1** — jungle, 3 Ghosts; **"Tom Clancy's GHOST RECON" wordmark baked in, top-left** | `#141A19` 16%, `#293435` 12%, `#222A29` 12%, `#1C2424` 8% |
| GR `main_menu-02` | 1024x512 | v6 24bpp | Backdrop 2 — night, moon, soldier at brick wall; same wordmark | `#151618` 19%, `#060607` 18%, `#242629` 15% |
| GR `main_menu-03` | 1024x512 | v6 24bpp | Backdrop 3 — interior window, sniper; same wordmark | `#040201` 37%, `#29231A` 6%, `#46443B` 6% |
| GR `main_menu-04` | 1024x512 | v6 24bpp | Backdrop 4 — swamp/creek, 3 Ghosts; same wordmark | `#243837` 8%, `#030604` 8%, `#496567` 4% |
| GR `main_menu-05` | 1024x512 | v6 24bpp | Backdrop 5 — rain-soaked ruined street, AT4 team; same wordmark | `#474A55` 12%, `#383A43` 12%, `#25262A` 10%, `#555A67` 9% |
| GR `shell_bgd-01..05` | 1024x512 | v6 24bpp | Sub-menu versions of the same five photos — **no wordmark**, darkened, horizontal rule bars top and bottom | -01 `#141918` 30%, `#1B2323` 11% |
| GR `shell_bgd-panel` | **16x512** | v5 16bpp A4R4G4B4 | thin vertical grey edge strip | `#444444` 50%, `#DDDDDD` 26%, `#000000` 23% |
| GR `decorations` | 256x128 | v5 32bpp ARGB | medal/ribbon sheet: Bronze Star, Purple Heart, Medal of Honor, Silver Star | `#000000` 75%, `#313131` 11% |
| GR `pda_bgd-01` | 1024x512 | v6 24bpp | blue in-game PDA bezel + button bar (full page used) | `#282828` 39%, `#162539` 20%, `#1A2B42` 12% |
| GR `cmi` | 512x128 | v6 32bpp ARGB | command-map icon sheet: red X, move arrows, zoom glyphs, team numerals 1-5 | `#000000` 68%, `#BEBEBE` 8% |
| GR `pda-lcd-02` | 256x256 | **v9** 32bpp | PDA LCD overlay: circled A/B/C team markers | `#000000` 29%, `#282828` 22%, `#474747` 16% |
| GR `reticle_misc` | 256x128 | **v9** 32bpp | vision icon, stance + equipment glyphs, stamina arc | `#000000` 75%, `#191919` 8% |
| GR `new_font_revised` | 256x256 | v6 32bpp | bitmap font atlas, full Latin-1 | `#000000` 48%, `#A5A5A5` 29% |
| GR `load_icon` | 128x128 | v5 16bpp 565 | circular GHOST RECON loading badge — the only other place the wordmark appears | `#000000` 49%, `#282728` 19% |
| GR `load-screen` | 1024x512 | v5 16bpp 4444 | loading frame chrome only, 97.9% empty | `#000000` 98% |
| GR `video` | 1024x512 | v5 16bpp 565 | **100.0% `#000000`** — an empty video surface placeholder, not a decode failure | — |
| GR `credits\01..25` | 1024x512 | v5 16bpp 565 | 25 credit photo slides | varied |
| SOAF `main_menu-01` | 1024x512 (640x480) | **v8** 24bpp RGB | **Main-menu backdrop 1** — US flag left, operator firing through chain-link; **"THE SUM OF ALL FEARS" gold wordmark baked in, top-left** | `#040508` 22%, `#272627` 10%, `#171619` 10%, `#0A0B14` 8% |
| SOAF `main_menu-02..05` | 1024x512 | v8 24bpp | Backdrops 2–5, same flag + gold wordmark (-03 catwalk, -05 tunnel) | -05 `#090706` 28%, `#191715` 16% |
| SOAF `shell_bgd-01..05` | 1024x512 | **v8 16bpp R5G6B5** | sub-menu backgrounds, no wordmark, gold rule bars. **`-03` and `-05` are byte-identical duplicates** (md5 `23c88277…`) | -01 `#010304` 30%, `#131414` 22% |
| SOAF `soaf_command_bkgrnd` | 512x128 | v8 32bpp ARGB | grey rounded 3-cell command-bar panel, alpha-masked. **Not a wordmark.** | `#000000` 81%, `#252525` 8%, `#404040` 8%, `#FEFEFE` 3% |
| SOAF `decorations` | 256x256 | v8 32bpp | larger medal sheet (~16 medals + ribbon bars) | `#000000` 78%, `#333333` 6% |
| SOAF `hud` | 256x256 | v8 32bpp | HUD glyph sheet: stance icons, firing-mode icons, soldier silhouettes | `#000000` 68%, `#4C4C4C` 8% |
| SOAF `pda_bgd-01` | 1024x512 | v8 24bpp | **amber/orange** PDA bezel (GR's is blue) | `#000000` 39%, `#372506` 9%, `#271A05` 9% |
| SOAF `shell_bgd-panel`, `threat`, `load-screen`, `video`, `mp_misc`, `cmi`, `eax_logo`, `new_font_revised`, `reticle_at4` | — | v5/v6 | **byte-identical to GR's** — SOAF reuses GR's shell assets wholesale | — |
| GR `Mods\Mp1\...\main_menu-01` | 1024x512 | v6 24bpp | GHOST RECON **DESERT SIEGE** wordmark, desert firefight | `#738AA5` 6%, `#6D86A2` 4% |
| GR `Mods\Mp2\...\main_menu-01` | 1024x512 | v6 24bpp | GHOST RECON **ISLAND THUNDER** wordmark, jungle | `#172619` 3%, `#677688` 2% |
| GR `Mods\Heroes Unleashed\...\main_menu-01` | 1024x512 | **v9** 24bpp | GHOST RECON **HEROES UNLEASHED** (red sub-title), silhouettes under storm clouds | `#141927` 7%, `#1C2335` 4% |
| GR `Mods\Heroes Unleashed\...\mainmenu_backdrop_shot` | **1024x1024** | v9 24bpp | in-engine pine-forest screenshot | `#F4F5F4` 21%, `#EBEDED` 11% |

### Answers to the three named questions

- **Main-menu backdrop:** `main_menu-01..05.rsb` in both games — five alternates,
  selected by `<ShellBackgroundIndex>` in `options.xml`. `shell_bgd-01..05.rsb`
  are the matching *sub-menu* backgrounds (same photos, darkened, wordmark
  removed, rule bars added).
- **"GHOST RECON" wordmark:** there is **no standalone wordmark .rsb**. It is
  baked into all five `main_menu-0N.rsb`, and small and circular into
  `load_icon.rsb`.
- **"SUM OF ALL FEARS" wordmark:** likewise baked into all five of SOAF's
  `main_menu-0N.rsb`. `soaf_command_bkgrnd.rsb` is a plain grey command-bar panel,
  not a wordmark.

### UI palette for skinning the GUI

Both games are near-black backdrops with a single accent:
- GR shell greys: `#141A19`, `#1C2424`, `#222A29`, `#293435`, `#474A55`, `#555A67`
- SOAF shell greys: `#040508`, `#0A0B14`, `#171619`, `#191826`, `#272627`
- GR accent (reticle, from `options.xml`): `ReticuleColor` **255,214,17 = `#FFD611`**;
  `ReticuleIFFColor` **160,200,255 = `#A0C8FF`** — identical in both games' `options.xml`
- GR PDA blue: `#162539` / `#1A2B42`; SOAF PDA amber: `#372506` / `#271A05`

### Decoder deliverable

`scratchpad\art\decoder\rsb_pc.py` (numpy + Pillow). Handles v0/1/4/5/6/8/9 at
4/8/16/24/32 bpp; prints version, dims, mask, bpp, trailer and 5 dominant colours.
Usage: `py -3 rsb_pc.py -o <dir> [--thumb N] [--order rgb|bgr|argb|abgr] <files...>`.
`tcps2\rsb.py` was **not** modified and nothing was written to either game folder.

**What did not decode: nothing.** All 34 SOAF and all 58 GR shell files plus the
mod sets decoded with zero failures. The only "empty" result is `video.rsb`,
which genuinely contains 1024x512 of pure black.

Caveat from the decode run: the scratchpad `art\` root already held unrelated
files from other work, including a stray `inspect.py` that shadows the stdlib
module and breaks `import numpy` for anything run from that directory — hence
the decoder living in `art\decoder\`.

---

## Cut content

Two independent passes: my own targeted checks plus a full reference-graph
census (every `Kit=` / `File=` / `<ItemFileName>` / `<ModelName>` / `<LOD2>` /
`<LOD3>` / `<ModelFace>` / `<BlinkFaceName>` across all `.mis .gtf .atr .kit .kil
.toe .xml .qmk .gun .itm .prj`, **including the decoded script bytecode**, which
removed 3 GR `.atr` and 6 SOAF `.kit` false positives).

### Headline: two cut Island Thunder multiplayer maps

Mapping every `STRINGS.RES` group index against the `NameId` values actually used
by retail `.mis`/`.gtf` gives a perfect 1:1 match for groups 1–70. **Groups 71 and
72 are referenced by nothing:**

```
group[71] Mission71 (7 entries)
  [71:0] id=74448896  'CP06 Underground'
  [71:1] id=74448897  'CP06 - Underground Test'
  [71:2..6]           ''
group[72] Mission72 (7 entries)
  [72:0] id=75497472  'CP07 Untitled'
  [72:1..6]           ''
```

A 7-entry group is the Island Thunder MP-map shape — compare `group[66]` =
`'CP01 Hunting Lodge'` / `'CP01 Hunting Lodge'` / `'Camaguey Province, Cuba'` /
`'April 17, 2010'` / `'14:45'` / `''` / `'12 to 24'`. Island Thunder ships
CP01–CP05. **CP06 "Underground" and CP07 "Untitled" got string-table slots and
nothing else.** Verified absent: no `cp06*` / `cp07*` / `*underground*` file
anywhere in `Mods\Mp2`, `Mods\Origmiss`, `Mods\Mp1` or `Data`; `Mods\Mp2\Map\`
holds only C01–C08 and CP01–CP05. CP06's subtitle still reads
**"Underground Test"** — cut while carrying its working title.

The same analysis on SOAF's 46-group `STRINGS.RES` finds **no unreferenced
mission or gametype group**. SOAF's string table is fully accounted for.

### CORRECTION: `bb01_woods_day.mis` / `bb02_woods_night.mis` are NOT retail

`Ghost Recon\unlocked_missions.xml` lists both between `m09_swamp` and
`m10_ruined_city`. They exist **only** in the fan mod:
`Mods\Heroes Unleashed\mission\bb01_woods_day.mis` / `bb02_woods_night.mis`, with
full terrain (`map\bb01_woods_day\*.map/.env/.sht` + dozens of `.rsb`),
briefings, commandmaps and video. Their shells read
`MapName="012 - Woods (M)"` / `Name='012 - "Swift Hatchet"'` and
`MapName="011 - Woods Night (M)"` / `Name='011 - "Brazen Eagle"'`. They are named
only in `Mods\Heroes Unleashed\mission\campaign.xml` lines 43/47. HU also ships a
third variant, `map\bb03_woods_day_snow\`, with **no mission entry anywhere** —
cut content inside the fan mod.

### Genuine unused content — Ghost Recon

**1. A legacy dev-weapon cluster still on disc, using a pre-release schema.**

`Mods\Origmiss\Equip\test.GUN`, `sniper.GUN` and `at4.kit` are the only three
files in GR that use the **old accuracy schema** — `<ProneAccuracy>`,
`<CrouchAccuracy>`, `<StandAccuracy>`, `<ShuffleMultiplier>`, `<WalkMultiplier>`,
`<RunMultiplier>` — instead of the shipped 12-field
`{Run,Walk,Shuffle,Stationary}{Stand,Crouch,Prone}Accuracy` set. Both guns have
`<Recoil>3</Recoil>` (every shipped weapon is 40–120 except the 1.5 launchers).

- `test.GUN` — M16 model, `<MagazineCapacity>3000</MagazineCapacity>`,
  full-auto only, no reticle tags. **Referenced by nothing** (grepped all of
  Origmiss + Mp1 + Mp2). A developer test/cheat rifle.
- `sniper.GUN` — M16 model, NameToken `WPN_M16`, 3 fire modes, `Recoil 3`,
  `ZoomSettings` 1/5/1. Referenced only by `Equip\at4.kit`.
- `at4.kit` — `<ItemFileName>sniper.gun</ItemFileName>` in slot 0 and
  `at4.gun` in slot 1. **Referenced by no mission** in Origmiss, Mp1 or Mp2.

So the whole cluster is unreachable in the shipped game. Restoring it is a
one-line kit edit. Two more unreferenced guns in the same bucket:
`Mods\Origmiss\Equip\50calMG.gun` (MagazineCapacity **30000**, Recoil 50, M82
model) and `Mods\Mp1\Equip\50calMG_S.gun`. Also `Equip\sample pda.kit` (a dev
sample pairing `m16.gun` with `pda.itm` — and `pda.itm` is referenced by nothing
else).

**2. The explosive chicken and squirrel — fully built, fully cut.**

`Mods\Origmiss\Equip\chicken.prj` and `squirrel.prj` are complete throwable
projectiles: weight 0.180, initial velocity 85, **`<BlastRadius>7.000000</BlastRadius>`**,
full ballistic coefficient block. **The art ships too:**
`Mods\Origmiss\Model\chicken.qob`, `Model\squirrel.qob`,
`Textures\chicken.rsb`, `Textures\Squirrel.rsb`, `Textures\squirrel_leaf.rsb`.
Nothing in the game — no `.kit`, no `.gun`, no script — references either.
Modelled, textured, ballistically tuned, and unreachable. (SOAF ships the same
two `.prj`, also orphaned, but **without** the `.qob` models.)
Also orphaned: `howitzershell.prj`, `shell.prj`.

**3. 258 of 562 mission-enemy `.atr` in GR base are never placed by any `.mis`.**

Enemies were authored roughly five-per-type-per-mission (`_1`…`_5`) and designers
placed a subset. Unlike the player-roster folders (which the engine enumerates),
mission enemies are named by filename, so an orphan here really is never spawned.
Notable complete unplaced sets:

- **Tank crew:** `m08_eli_tank_1/2`, `m08_rec_tank_1/2`, `m08_vet_tank_1/2` — all
  six use `rs_north_tank.chr`, which **exists** at
  `Mods\Origmiss\Character\RS_north\rs_north_tank.chr`.
- **Civilian refugees:** `oldman_refugee_1.atr` (`man_old01.chr`),
  `youngman_refugee_2.atr` (`man_young02.chr`) — models exist under
  `Character\Refugees\`.
- **Officers:** `m06_officer_1..5`, `m12_officer_4/5`, `m14_officer_1..5`
  (`rs_north_foff.chr`, exists).
- **Ten complete 5-man sniper squads:** `mNN_rec_sniper_1..5.atr` for
  m03, m04, m05, m06, m07, m08, m09, m12, m13, m15.
- Mp1: `m08_overkill_1d..4f` (12 "overkill" actors), `m03_sam_2A`,
  `m03_elite_1A..1F`, `m06_elite_1a..1f`. Mp2: `c03_i_1b`, `c03_i_1c`.

Per-directory (total / orphan): `Mods\Origmiss\Actor` 562/258,
`Mods\Mp1\Actor` 364/39, `Mods\Mp2\Actor` 434/16.

**4. Island Thunder ships 7 single-weapon kits nobody equips:**
`Mods\Mp2\Kits\hk4_only`, `m240_only`, `mm1_only`, `sa25_only`, `sopmodm4_only`,
`sr25_only`, `sr25SD_only.kit`.

**5. Shipped XML bug in five Island Thunder kits.** `Mods\Mp2\Kits\behemoth0..3.kit`
and `mouse.kit` are byte-identical and all five contain
`<KitTexture>kit_ramirez-03.rsb</VersionNumber>` — opening tag `KitTexture`,
closing tag `VersionNumber`. `behemoth0/1` are referenced from decoded script
inside `Mods\Mp2\Mission\(solo) behemoth.gtf`; `behemoth2/3` are not.

**6. An orphaned hero kit folder for a hero the expansion doesn't have.**
`Mods\Mp1\Kits\hero\klaus_henkel\klaus_henkel-01.kit` exists in Desert Siege,
but Desert Siege has no `d_klaus_henkel.atr` — its five heroes are Dieter Munz,
Jodit Haile, Lindy Cohen, Nigel Tunney, Scott Ibrahim. (Mp1's
`d_jodit_haile-01..04.kit` are likewise orphaned.)

**7. GR heroes: 12 exist, 3 unlocked, 10 in Quick Mission.**

All 12 `Actor\hero\*.atr` ship with a full 4-kit folder in `Kits\hero\<name>\`
(48 kit files). `unlocked_heroes.xml` unlocks 3 (nigel_tunney, jack_stone,
buzz_gordon). `Kits\quick_missions.qmk` grants hero kits for 10 of the 12 —
**Will Jacobs and Buzz Gordon are listed nowhere in it**, although both have
`will_jacobs-01..04.kit` and `buzz_gordon-01..04.kit` on disc. Their kits are
unreachable from Quick Mission. Data inconsistency in the same file:
`susan_grey.atr` declares `ClassName = rifleman` but `quick_missions.qmk` files
her under `demolitions`. Mp1's `.qmk` lists only generic `*-05..12` kits (no hero
names at all); Mp2's mixes generics `*-13..25` with hero kits for
`henry_ramirez-5..8`, `klaus_henkel-5..8`, `jack_stone-5..8` only —
`c_buzz_gordon`, `c_susan_grey`, `c_will_jacobs` get none.

Heroes have **no string-table entry at all** — zero hits for any hero name in
`Data\Shell\strings.txt`, Mp1/Mp2 `strings.txt`, or the full parsed
`STRINGS.RES`. Hero names come straight from `<ActorName>`. That is engine
design, not cut content.

**8. Dangling references — GR has exactly two.**

| kind | missing target | referenced from |
|---|---|---|
| `<BlinkFaceName>` | `ice_rebel_leader_1ver_blink.rsb` | `Mods\Origmiss\Actor\m02_leader_1.atr` line 8 |
| `Kit=` (dev path) | `c:\documents and settings\garys\desktop\ghost recon\mods\origmiss\kits\rifleman\rifleman-01.kit` | `Mods\Origmiss\Mission\training.toe`, 7 `<Actor>` lines |

The blink-face is a shipped typo: what exists is
`Mods\Origmiss\Textures\GR\ICE_Rebel_Leader_head_1ver_blink.rsb` (note `_head_`).
The dev path is the **only absolute path in the entire retail GR data tree**; the
sibling `M_avatar.toe` uses clean relative names.

**9. Shipped filename typo.** `Actor\hero\astra_galinksy.atr` vs the correctly
spelled `Kits\hero\astra_galinsky\`. `campaign.xml` references the typo'd name,
so nothing is broken — but it will trip any tool that derives one from the other.

**10. Other GR dev leftovers.**

- `Mods\Origmiss\Sound\M_Voice_3\tmp_*.wav` — an entire placeholder-named voice
  bank (100+ files: `tmp_detected1.wav`, `tmp_detect_tank1.wav`,
  `tmp_enemy_retreat1.wav`, `tmp_expl_first.wav` …) shipped with `tmp_` intact.
- `treetest07B.rsb` / `LODtreetest07B.rsb` — a "test" tree texture shipped into
  nine maps (m01, m07, m09, m11, m14, m15, mp01, mp03, mp04).
- `Mods\Origmiss\Kits\no_explosvies.kil` — filename misspelled; identical typo in
  Mp1 and Mp2. The internal `Name="No Explosives"` is correct.
- **Unresolved string tokens:** `@MP_atr_sup`, `@MP_atr_snip`, `@MP_atr_rif`,
  `@MP_atr_demo` are the `<ActorName>` of the 12 MP platoon actors in
  `Actor\MP Actor Files\Platoon 1-4\`. **None resolves** — not in any
  `strings.txt`, not in `STRINGS.RES`.
- **Dangling UI string:** `Data\Shell\strings.txt` declares
  `"Standard Kits"  "Standard Kits"` under `// Kit restriction files`, but no
  `standard_kits.kil` exists in Origmiss/Mp1/Mp2 (only in Heroes Unleashed).
- **Inverse:** `no_sensors.kil` ships in all three retail mods with
  `<KitRestriction Name = "No Sensors">`, but there is **no "No Sensors" string**
  anywhere — 0 hits in every `strings.txt` and in the full `STRINGS.RES` dump.
- Mp1 is missing `grenades_only.kil` and `pistols_only.kil`, which Origmiss and
  Mp2 both ship.
- `Mods\Mp2\Mission\cp03_jungle_prison.mis` and `cp05_market.mis` ship
  `<Name>Custom Mission</Name>` — placeholder naming left in retail.
- `Mods\Origmiss\Mission\mp06_castle.mis` is the only `mp0*` file with
  `SinglePlayer=1` **and** `Coop=1` in its `<Shell>`; the other five have neither.
  Playable solo/co-op but outside `campaign.xml`.

### Genuine unused content — Sum of All Fears

**11. Dressler, the campaign's named antagonist, is never placed.**

`Mods\Origmiss\Actor\dressler.atr`: `<ActorName>Dressler</ActorName>`, unique
model `mm_dressler.chr` (exists: `Character\masterminds\mm_dressler.chr`), unique
face `dressler_face.rsb` (exists: `Textures\mastermind_faces\dressler_face.rsb`),
stats Weapon 7 / Stamina 7 / Stealth 2 / Leadership 6, VoiceType 6.
**`Mission\m11_dresslers_estate.mis` never places him** — it spawns only generic
`m11_masterminds_1a..10a.atr`, `m11_elite_guard_*`, `m11_garage_*`. He survives in
text only, at `Shell\strings.txt:177`
`"M11_INTEL_1_NAME"  "Dressler, Richard"`.

**12. Other unplaced SOAF actors (24 orphans total).**

- `m03_cop_1A/1B/1C.atr` — Israeli police, `<ActorName>@ISRAELCOPNAME</ActorName>`
  ("an Israeli Police Officer"), dedicated model `israeli_police.chr` + 2 LODs
  (all exist under `Character\civilian\`). Never placed in `m03_warehouse.mis`.
- `m08_support_team_3A/3B/3C.atr` — female support team, `@SUPPORTNAME`,
  `black_team_female.chr` + 2 LODs (exist). Never placed.
- Also unplaced: `m03_1st_floor_2A`, `m03_alarm_guards_S_1C`,
  `m03_fire_escape_3A/4A`, `m03_front_door_2A`, `m08_recruit_1a/1b/2a/3a/3b`.

**13. The briefcase gun.** `Mods\Origmiss\Equip\mp5case.gun` —
`<NameToken>Briefcase Gun</NameToken>`, `<ModelFileName>w_thomascase.qob</ModelFileName>`.
Referenced by exactly one orphan kit (`Kits\mercenaries\mp5briefcase.kit`) and
nothing else. The whole `Kits\mercenaries\` tree is orphaned (20 kits:
`30-06_and_cigs`, `benelli_only`, `jackhammer_only`, `mouse_kit`, `mp5briefcase`,
`opposing_force_0..4`, `sawedoff_only`, `swdshtgn_and_cigs`, …).

**14. A fully-configured OICW+GL that no kit equips.**
`Mods\Origmiss\Equip\OICWGL.gun` has `<HasUnderbarrelWeapon>1</HasUnderbarrelWeapon>`
and `<UnderbarrelWeaponName>glforoicw.gun</UnderbarrelWeaponName>`. Orphaned.
(`stationarygun.gun` is the other orphan `.gun`.)

**15. Cat-and-Mouse is Behemoth with the labels left in.** Decoding
`Mods\Origmiss\Mission\(solo) cats_and_mouse.gtf` shows SOAF's mode was built from
Island Thunder's **Behemoth** script and never renamed. Its variables still read
`Behemoth`, `Behemoth Actor`, `Behemoth Has Kit 2/3/4/5`,
`Loop Behemoth Actors to set Behemoth Kit`, `Reset Death Behemoth Counter`,
`Current Behemoth Score` — while the only kit it assigns is `mouse_kit.kit`. The
kit-2-through-5 escalation logic is still in there with nothing to feed it.

**16. SOAF ships 8 `.bak` files that are a difficulty-tuning audit trail.**
`Actor\opposing_force_0..6.atr.bak` each differ from the live file in exactly one
line (`Weapon` 4 -> 2); `Equip\30-06.gun.bak` differs in exactly one line
(`RateOfFire` 600 -> 35). Detail above under the script section.

**17. SOAF outfits: 15 on disc, 9 in `unlocked_outfits.xml`.** Not listed:
`cqb_assault`, `cqb_breach`, `cqb_recon`, `field_sniper`, `full_assault`,
`military_breach`. All six are **fully authored** — the `.off` exists, the `.kit`
it points at exists under `Kits\team\`, and both name and description strings
exist in `Shell\strings.txt`. These are progression-locked, not cut.

**18. SOAF dev leftovers.**
- `Mission\mp06_artgallery.mis` lines 110, 113, 116–118 carry live door objects
  named with a developer's placeholder: `<Door Door = "09_<n><door>testjohn01" …/>`,
  `…testjohn03`, `…testjohn02`, `…testjohn01`, `…testjohn`.
- `Map\MP01_RSE\treetest07B.rsb` and `LODtreetest07B.rsb` — the same "test" tree.
- `Textures\civilain_faces\` — misspelled directory name, shipped and live.

### Where the census found nothing

- **SOAF has zero dangling references.** Every referenced `.atr`, `.kit`, `.chr`,
  `.rsb`, `.gun`, `.itm`, `.prj` resolves.
- No absolute dev paths in SOAF at all; exactly one in GR (`training.toe`).
- No cut mission or gametype string group in SOAF's `STRINGS.RES`.
- No `.bak` / `.old` / `.orig` anywhere in GR's data tree — the 8 `.bak` are
  SOAF-only.
- No `tmp*` / `unused*` / `debug*` / `xxx*` data files in SOAF (GR's `tmp_*.wav`
  voice bank has no SOAF equivalent).
- No CP06/CP07 assets of any kind — not a map, not a `.mis`, not a texture, not a
  briefing. String-table slots only.

### Orphan counts, with the honest caveat

| ext | GR orphan / total | SOAF orphan / total |
|---|---|---|
| `.atr` | 531 / 1666 | 41 / 479 |
| `.kit` | 26 / 217 | 20 / 132 |
| `.gun` | 3 / 63 | 2 / 35 |
| `.prj` | 4 | 2 |
| `.mis` | 24 / 55 | 14 / 25 |
| `.gtf` | 16 / 16 | 13 / 13 |
| `.kil` | 18 / 18 | 7 / 7 |
| `.qmk` | 3 / 3 | — |
| `.toe` | 6 | 6 |
| **total** | **631** | **105** |

**Do not report these raw.** `.gtf`, `.kil`, `.qmk` and the MP/training `.mis` are
100% orphaned *by design* — the engine enumerates those directories and never
names the files. Same for `Actor\hero\`, `Actor\MP Actor Files\` and the
player-roster pools (`Actor\rifleman` 76/65, `heavy-weapons` 60/57,
`demolitions` 59/58, `sniper` 40/38). The signal is in items 1–18 above.

---

## Open questions

1. **`Class0..Class5` semantics (GR).** Parsed by `GhostRecon.exe` (the literal
   `Class0` is in the binary), absent from `SOAF.exe`. Every campaign mission has
   `Class0=1` and `Class1=1`; `Class2..Class5` are 1, 2, 3 or absent.
   `<CombatPoints>` climbs monotonically 1->7 across m01..m15, and
   `Data\Shell\STRINGS.RES` @117198 contains
   `PLATOON SETUP / STANDARD / SPECIALIST / Combat Points = `. Best guess:
   per-class specialist availability plus a campaign point award. Not resolved.
2. **Exact damage formula.** `VelocityCoefficient0..2`, `KillCoefficient1..2`,
   `Ballistic*Factor` and `ArmorLevel` clearly combine, but the composition is
   inferred from naming and magnitudes only.
3. **Is the 15.0 in `(sp)/(coop) firefight.gtf` really the spawn count?** Needs an
   in-game test (out of scope — no launching). Note the `.gtf` script opcode
   stream is a u32 token stream; identifying which token is the
   `SpawnOpposingPatrolForce` parameter slot would settle it without launching,
   but requires the opcode table (see Dead end).
4. **`@MP_atr_rif` / `_demo` / `_snip` / `_sup` resolve to nothing** in either
   `strings.txt` or `STRINGS.RES`. Either a fifth string source exists, or the MP
   platoon actor names genuinely render as raw tokens.
5. **Mp1/Mp2 `<ExtraStatPoints>`** (4 in Desert Siege, 5 in Island Thunder,
   absent from base GR's `campaign.xml`) is probably the same system as
   `Class0..5` / `CombatPoints`. Unresolved.
6. **Does `<Silenced>1</Silenced>` change AI hearing or only audio?** Not
   determined from files.
7. **Mod layer precedence for *additive* files.** PS2Accuracy proves a mod can
   both shadow an existing path and add a new filename. Whether two active mods
   shadowing the same path resolve last-wins at file or folder granularity is
   inferred from the HU manual's wording, not tested.

### Resolved during the session (kept for the record)

- `Mods\Origmiss\Shell\Equip` (SOAF) = 36 `.rsb` weapon icons for the loadout
  menu, one per `.gun`/`.prj`/`.itm`, plus `no_item.rsb` and `no_weap.rsb`.
  A new weapon needs a matching icon here.
- SOAF `HRT_*` `.gun` overrides = a shotgun buff, not a model re-point.
  See Mod system.
- `bb01/bb02_woods_*.mis` = Heroes Unleashed content, not cut retail.
  See Cut content.
- `STRINGS.RES` binary format and the `NameId` bit layout. See Levers.

---

## Artefacts produced this session

All read-only; nothing was written inside either game folder.

| path (under `…\scratchpad\`) | what |
|---|---|
| `dossier-gr-soaf.md` | this file |
| `script\gtfdec.py`, `gtfdec2.py`, `gtfhex.py`, `gtfstr.py`, `gtffloat.py` | `.gtf`/`.mis` script blob decoders |
| `script\agg.py`, `atrsum.py`, `guntable.py` | schema/range aggregators for `.gun` `.kit` `.atr` |
| `script\miscount.py` | per-mission enemy counts by difficulty |
| `script\tagsinexe.py`, `exescan.py` | which XML tags each game binary actually parses |
| `art\decoder\rsb_pc.py` | RSB v0/1/4/5/6/8/9 decoder for the PC files |
| `art\png\gr\`, `soaf\`, `gr_mods\`, `onblack\` | 167 decoded menu/HUD PNGs |
| `cut\GR_strings_res.txt`, `SOAF_strings_res.txt` | full `STRINGS.RES` dumps |

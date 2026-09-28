# Sum of All Fears (PS2, SLES-511.80) — what is editable

**Short answer: everything Ghost Recon exposes, plus two things Ghost Recon
does not have.** The grammar is identical, the transform code in
`tcps2/transforms.py` runs on these files unmodified, and every edit stays
byte-length-preserving so the archive slot never moves.

The two new levers are `CMBTMODL.XML`, a single file holding the whole
difficulty and wound model as plain named floats, and `.GTF` script variable
tables that are actually **populated** — 11 of 13, where all 46 Ghost Recon
missions shipped theirs empty.

---

## 1. Enemies — identical to Ghost Recon, down to the spaces

`<Units>` / `<Company>` / `<Platoon>` / `<Team>` / `<Actor>`, exactly. A real
line, from `M05_PRISON.MIS`:

```xml
<Actor IgorId = "118" ScriptId = "54" Name = "Entrance Patrol 2E" File = "m05_entrance_patrol_2e.atr" Kit = "ak74_only.kit" Pos = "-476.94;-355.86;-20.00;" Facing = "4.56" Easy = "0" Normal = "0"/>
```

`Easy = "0"` / `Normal = "0"` / `Hard = "0"`, spaces around the `=`, one
`<Actor>` per soldier, the flag removing that soldier at that difficulty. Run
verified, not assumed: `tcps2.transforms.strip_difficulty` on
`M05_PRISON.MIS` blanks 36 flags and returns 78,706 bytes in and 78,706 out.

Attribute census over 496 `<Actor>` tags in the 23 `.MIS` files and both
`.TOE`s:

| attribute | count | what |
|---|---|---|
| `IgorId`, `ScriptId`, `Name`, `File`, `Kit` | 468 each | on every actor |
| `Pos` | 464 | `x;y;z;` |
| `Facing` | 210 | radians |
| `Lvl` | 173 | **new in this game** — every occurrence in retail is `"1"` |
| `Easy` | 169 | |
| `Normal` | 109 | |
| `Hard` | 30 | |
| `Idle` | 94 | idle animation index |
| `Tag` / `Id` | 28 each | script handles, only on scripted actors |
| `Hidden` | 12 | all twelve in `M09_BANK.MIS` |
| `Stance` | 6 | |
| `CampaignLoad` / `Owner` | 3 / 2 | `.TOE` only — the player's own squad |

Enemy count per campaign mission, and how many survive on Hard:

| mission | actors | `Easy="0"` | `Normal="0"` | `Hard="0"` | present on Hard |
|---|---|---|---|---|---|
| M01 TV Station | 43 | 11 | 10 | 5 | 38 |
| M02 Militia | 51 | 23 | 21 | 5 | 46 |
| M03 Warehouse | 52 | 25 | 16 | 5 | 47 |
| M04 Weaponfac | 44 | 15 | 9 | 2 | 42 |
| M05 Prison | 48 | 21 | 13 | 2 | 46 |
| M06 Mercenary | 37 | 11 | 2 | 0 | 37 |
| M07 Diamond Mine | 38 | 11 | 9 | 4 | 34 |
| M08 Olson Estate | 42 | 13 | 5 | 2 | 40 |
| M09 Bank | 36 | 15 | 9 | 0 | 36 |
| M10 Corporate HQ | 33 | 13 | 11 | 5 | 28 |
| M11 Dressler's Estate | 33 | 11 | 4 | 0 | 33 |
| T01–T05 (training) | 7 each | 0 | 0 | 0 | 7 |

The six `MP*.MIS` multiplayer maps and `TRAINING.MIS` carry **no `<Actor>` at
all** — their populations come from the `.GTF`, which is how Jungle Storm's
Defend works.

`M09_BANK.MIS` is the one mission with despawned actors: twelve
`Hidden = "1"` guards named `Alarm 1A`..`1F` and `Alarm 2A`..`2F`, i.e. the
reinforcements the alarm script spawns. `tcps2.transforms.reveal_hidden` targets exactly that
attribute and is the only place in the game it fires.

## 2. `.ATR` skill templates — identical

```xml
<ActorFile>
    <ArmorLevel>1</ArmorLevel>
    <Weapon>4</Weapon>
    <Stamina>4</Stamina>
    <Stealth>1</Stealth>
    <Leadership>1</Leadership>
    ...
</ActorFile>
```

(`M05_ENTRANCE_GUARD_1R.ATR`, 708 bytes.) `read_atr_stats` returns
`{'ArmorLevel': 1, 'Weapon': 4, 'Stamina': 4, 'Stealth': 1, 'Leadership': 1}`
and `bump_atr_stats(+1)` changes five values and returns 708 bytes for 708 —
single digits in, single digits out, slot untouched.

510 `.ATR` files, 479 of them in `SOAF.IMG`. `M05_PRISON.MIS` alone references
41 distinct templates, so per-mission retuning is real rather than notional.

SOAF adds fields Ghost Recon's `.ATR` does not have and which the existing
transforms leave alone: `ModelFace`, `BlinkFaceName`, `ModelName` + `LOD2`/`LOD3`,
`HeadAttachment` / `NeckAttachment` / `SpineLowAttachment`, `ScaleX/Y/Z`,
`Female`, `VoiceType`.

## 3. `.GTF` game types — the A..P encoding, and it has real variables

26 `.GTF` files (13 unique, mirrored in both archives). Same shape as Ghost
Recon: `<ScriptCompiled>` and `<ScriptSource>` are the A..P nibble encoding,
two characters per byte, low nibble first, and `research/rsescript.py` and
`tcps2/transforms.py` decode them with no changes.

**This is where SOAF differs.** Ghost Recon shipped 46 missions with an empty
variable table and Jungle Storm 44 of 45. Here 11 of 13 `.GTF`s have a
populated one:

| game type | vars |
|---|---|
| `(TEAM) DOMINATION.GTF` | 11 — `Lose Text` 32, `Win Text` 37, `Draw Text` 71, `Begin Control 1..4` 67/81/82/83, `End Control 1..4` 68/75/76/77 |
| `(TEAM) SEARCH AND RESCUE.GTF` | 9 — `Captive Kit` 3, `Captive Class A/B/C` 16/17/18, plus the text ids |
| `(TEAM) SIEGE.GTF` | 7 — `Defender win/lose text` 2/3, `Attacker win/lose text` 4/5, **`Capture time` 5**, `Attacker notification` 18, `Defender notification` 19 |
| `(SOLO) HAMBURGER HILL.GTF` | 5 — `Begin King` 67, `End King` 68, plus text |
| `(SOLO) LAST MAN STANDING.GTF`, `(TEAM) LAST MAN STANDING.GTF`, `(SOLO) SHARPSHOOTER.GTF` | 3 each |
| `(COOP) RECON.GTF`, `(SP) LONE WOLF.GTF` | 2 each |
| `(COOP) FIREFIGHT.GTF`, `(SP) FIREFIGHT.GTF` | 1 each |
| `(SOLO) CATS_AND_MOUSE.GTF`, `(TEAM) HAMBURGER HILL.GTF` | **0** |

`Capture time` in Siege is the one that is plainly a gameplay number rather
than a string id. Most of the rest are localisation ids, so raising them does
nothing useful — read the name before writing the value.

The tables live in `<ScriptSource>`, not `<ScriptCompiled>` — Siege's compiled
blob is 3,309 payload bytes with **0** variables and its source blob is 4,484
bytes with 7. Because the encoding is fixed width, rewriting a value in place
keeps the payload, the XML and the archive slot identical byte-for-byte.

**Still not cracked, same as Ghost Recon:** the compiled node graph past the
variable table. A constant typed straight into a designer node is out of reach.

`.MIS` files carry `<ScriptCompiled>` / `<ScriptSource>` too, and **all 23 have
an empty variable table** — same negative as Ghost Recon, so mission wave
timing is no more reachable here than there.

## 4. `CMBTMODL.XML` — the one genuinely new lever

1,505 bytes, plain XML, in both archives. This is the entire wound and
difficulty model as named floats. Verbatim:

```xml
<CombatModelFile>
    <VersionNumber>1.100000</VersionNumber>
    <BallisticHeadFactor>10.000000</BallisticHeadFactor>
    <BallisticChestFactor>100.000000</BallisticChestFactor>
    <BallisticArmoredChestFactor0>0.000000</BallisticArmoredChestFactor0>
    <BallisticArmoredChestFactor1>150.000000</BallisticArmoredChestFactor1>
    <BallisticArmoredChestFactor2>350.000000</BallisticArmoredChestFactor2>
    <BallisticArmoredChestFactor3>550.000000</BallisticArmoredChestFactor3>
    <BallisticAbdomenFactor>400.000000</BallisticAbdomenFactor>
    <BallisticUpperArmFactor>700.000000</BallisticUpperArmFactor>
    <BallisticLowerArmFactor>1000.000000</BallisticLowerArmFactor>
    <BallisticUpperLegFactor>500.000000</BallisticUpperLegFactor>
    <BallisticLowerLegFactor>800.000000</BallisticLowerLegFactor>
    <ArcadeModeKillChanceFactor>0.500000</ArcadeModeKillChanceFactor>
    <RecruitFriendlyKillChanceFactor>0.500000</RecruitFriendlyKillChanceFactor>
    <RecruitFriendlySkillAdjustment>2</RecruitFriendlySkillAdjustment>
    <RecruitEnemySkillAdjustment>-2</RecruitEnemySkillAdjustment>
    <EliteFriendlySkillAdjustment>-2</EliteFriendlySkillAdjustment>
    <EliteEnemySkillAdjustment>2</EliteEnemySkillAdjustment>
    <RecruitEnemyDelayFactor>1.250000</RecruitEnemyDelayFactor>
    <VeteranEnemyDelayFactor>1.050000</VeteranEnemyDelayFactor>
    <EliteEnemyDelayFactor>0.750000</EliteEnemyDelayFactor>
    <RecruitEnemyAimFactor>1.250000</RecruitEnemyAimFactor>
    <EliteEnemyAimFactor>0.750000</EliteEnemyAimFactor>
</CombatModelFile>
```

Note the difficulty names: **Recruit / Veteran / Elite**, which is a *different*
axis from the `Easy` / `Normal` / `Hard` attributes on `<Actor>`. The actor
flags change who is on the map; these factors change how well they shoot.
`ArcadeModeKillChanceFactor` implies an arcade mode exists as a setting.

Every value here is `%f`-formatted to six decimals or a small signed integer,
so a length-preserving rewrite is easy (pad with the digits you have, or keep
the same field width). This file is the single highest-value knob in the game
and it needs no new format work at all.

## 5. Weapons, projectiles, kits, outfits, restrictions

All plain XML, all length-preservable, all directly editable.

`.GUN` (70 files) — `M4.GUN` has 59 fields: `MagazineCapacity`, `MaxRange`,
`VelocityCoefficient0/1/2`, `KillCoefficient1/2`, `ProjectileCount`,
`ProjectileSpread`, `Selective`, `Recoil`, `StabilizationTime`, `Silenced`,
`ZoomSettings` + two `Zoom`, `MuzzleFlashScale`, `TracerFrequency`, the whole
reticle rect, and a 3×3 accuracy matrix
(`Run|Walk|Shuffle|Stationary` × `Stand|Crouch|Prone`), plus five
`TurnBandVelocity`/`TurnBandMultiplier` pairs.

`.PRJ` (12) — `Type`, `DetonateOnImpact`, `DelayTime`, `InitialVelocity`,
`BlastRadius`, `IsStunOnly`, `DamageThroughWalls`, `IsDirectional`,
`VisualExplosionType`, `AirResistanceConstant`, and a `CombatCoefficient*`
family mirroring the gun coefficients.

`.KIT` (132) — `<Firearm SlotNumber = "0">` with `ItemFileName` and
`MagazineCount`. `.OFF` (30) — an outfit is a `NameToken` plus three
`KitFileName` lines. `.KIL` (14) — `<KitRestriction Name="No Explosives">`
listing the kits each multiplayer actor may take; this is the multiplayer
weapon-restriction system and it is pure data.

`.TOE` (2) — `AVATAR.TOE` is the player's own three-man Alpha team in exactly
the `<Units>` grammar, with `CampaignLoad = "1"` and `Owner = "0"` marking the
one you control.

`CAMPAIGN.XML` — mission order plus the intel/news gallery bindings.
`BEST_TIMES.XML` — four par times, uncompressed, 362 bytes.
`MODSCONT.TXT` — a mod manifest (`NAME`, `AUTHOR`, `SUPPORT`, `VERSION`,
`MULTIPLAYER "Server-Client"`), the same one Ghost Recon PC mods use, so the
engine has a mod concept.
`SCREEN.TXT` — the 19 menu screen names (`MAIN_PS2`, `OPTIONSGAME_PS2`,
`QUICK_MISSION_PARAMETER_PS2`, …).

## 6. Precise negatives

* **`EFFECTS.XML` is not an effects file.** It is `<SoundVolFile>` with 386
  `<Entry Filename="…wav" Length Min Max Rolloff Ambient>` rows. So are
  `BRIEFINGS.XML`, `TRAINING.XML`, `MUSIC.XML` and every `*_VOICE.XML`. There
  is no XML particle or decal configuration in either archive.
* **No `.MIS` has a non-empty script variable table** — all 23 checked.
* `(SOLO) CATS_AND_MOUSE.GTF` and `(TEAM) HAMBURGER HILL.GTF` have empty
  variable tables, unlike their siblings, so those two game types cannot be
  retuned this way.
* Every retail `Lvl` attribute is `"1"`. Whatever it selects, the shipped data
  never uses a second value, so its meaning is a guess from the name alone.

## 7. What a tool should ship first

1. `CMBTMODL.XML` — one file, named floats, whole-game difficulty. Nothing else
   comes close for effort-to-effect.
2. Per-mission `Easy`/`Normal`/`Hard` stripping, which already works through
   `tcps2.transforms` unmodified.
3. `.ATR` skill bumping, likewise already working.
4. `(TEAM) SIEGE.GTF` `Capture time`, as the proof that GTF variable editing
   lands.
5. `.GUN` / `.PRJ` tuning, which is a UI problem rather than a format problem.

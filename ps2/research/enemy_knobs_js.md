# Enemy population and spawning -- Ghost Recon Jungle Storm (PS2, SLUS-20820)

Everything here was read out of the retail `gr.img` with `grimg.py` +
`rselzo.py` + `rsescript.py` in this same folder. Nothing is inferred from the
PC version of the game.

## Headline numbers

Counting every `<Actor>` inside every non-`Allied` `<Company>` of every mission
that has an order of battle (21 missions; the remaining ones are training and
multiplayer maps with no enemy company at all):

| difficulty | enemy soldiers placed, all missions |
|---|---:|
| Easy | **657** |
| Normal | **804** |
| Hard / Elite | **955** |

That spread is produced entirely by the per-actor `Easy="0"` / `Normal="0"` /
`Hard="0"` suppression attributes described below.


## How enemy population is expressed

Everything below is **plain latin-1 XML** once the file is pulled out of the archive
with `grimg.py` (which LZO-decompresses automatically). No binary editing is needed
for any of it.

### 1. `<Units>` inside a `.MIS` -- the order of battle (THE main knob)

```
<Units>
  <Company IgorId="3" ScriptId="2" Name="Enemies">
    <Platoon IgorId="4" ScriptId="3" Name="Platoon - Patrollers">
      <Team IgorId="8" ScriptId="7" Name="Team - Patrol #1" Plan="396">
        <Actor IgorId="9"  ScriptId="8"  Name="Patrol #1-B"
               File="m02_rec_ak47_2.atr" Kit="ak47_2 grenades.kit"
               Pos="170.93;11.86;12.20;"/>
        <Actor IgorId="21" ScriptId="20" Name="Patrol #2-B"
               File="m02_rec_ak47_7.atr" Kit="ak47_2 grenades.kit"
               Pos="93.29;79.07;6.78;" Easy="0"/>
```

A `<Company>` carrying `Allied="1"` is friendly; every other Company is hostile.
Nesting is always Company > Platoon > Team > Actor. One `<Actor>` == one soldier.

**Editable attributes on `<Actor>`:**

| attribute | what it does |
|---|---|
| `File` | the `.atr` template = model + skill tier |
| `Kit` | the `.kit` loadout file |
| `Pos` | `x;y;z;` spawn position |
| `Facing` | initial yaw, radians |
| `Easy="0"` | **soldier is REMOVED on Easy** |
| `Normal="0"` | **soldier is REMOVED on Normal** |
| `Hard="0"` | **soldier is REMOVED on Hard/Elite** |
| `Hidden="1"` | starts despawned; a script spawns him in later |
| `Idle` | idle-animation index; values 1..17 observed |
| `Stance` | 1 / 2 / 3 — a posture index. Which value is stand / crouch / prone was **not** verified. |
| `Lvl` | always `"1"` in the retail data; **guess:** a building floor index |

The difficulty attributes are **suppression flags, and their value is always `"0"`** --
there is no `"1"` form anywhere in either game. Absence of the attribute means
"present at this difficulty". So:

* make a soldier appear on every difficulty -> delete his `Easy`/`Normal`/`Hard` attributes
* remove a soldier from one difficulty only -> add `Easy = "0"` etc.
* add a soldier -> copy a whole `<Actor .../>` element, give it a fresh unique
  `IgorId`/`ScriptId`, and move `Pos`

This is the highest-leverage knob in the game: it is how the shipping title does
its own difficulty scaling.

`<Vehicle>` elements sit alongside `<Actor>` in the same tree and accept `Easy`,
`Hidden`, `NeverStop` and `Plan` as well.

### 2. `<PlanList>` inside a `.MIS` -- AI behaviour

A `<Team>` points at a `<Plan>` by `Plan="<IgorId>"`. A Plan is an ordered list of
verbs the team executes:

```
<Plan IgorId="379" ScriptId="17" Name="Path Plan - Patrol #2" Assigned="1">
  <Path IgorId="380">
    <Point Pos="92.53;83.01;7.08;"/>
    <Point Pos="79.39;104.95;9.69;"/>
  </Path>
  <Grenades Available="1" IgorId="634"/>
  <Cover Pos0="78.29;106.40;9.71;" Pos1="77.64;107.91;9.85;" Time="7.00" IgorId="381"/>
  <Restart IgorId="595"/>
</Plan>
```

`<Restart>` makes the plan loop forever -- that is what turns a plan into a
perpetual patrol. Full verb vocabulary present in this game:


| verb | x | attributes seen |
|---|---:|---|
| `<Point>` | 1583 | `Pos`, `Altitude` |
| `<Plan>` | 608 | `Assigned` |
| `<Path>` | 324 | `Action` 1/2 |
| `<Alertness>` | 263 | `State` 1/2, `Change` |
| `<MoveROE>` | 178 | `State` 1/2 |
| `<AddZone>` | 168 | `Type` |
| `<CombatROE>` | 139 | `State` 1/2 |
| `<Stance>` | 138 | `Type` 1/2/3 |
| `<Pace>` | 127 | `Type` 1/2 |
| `<DefendZone>` | 92 | -- (**not present in Ghost Recon**) |
| `<Patrol>` | 81 | -- |
| `<Cover>` | 81 | `Pos0`, `Pos1`, `Time` 3.00 |
| `<Speed>` | 46 | `Rate` 1.50..11.00 |
| `<Wait>` | 31 | `Time` 1.00..20.00 |
| `<EnterVehicle>` | 19 | `Target`, `Driver` |
| `<Formation>` | 12 | `Type` 1/2 |
| `<UnloadVehicle>` | 11 | -- (**not in GR**) |
| `<Follow>` | 6 | `Target`, `Range` |
| `<ExitVehicle>` | 4 | -- |
| `<Grenades>` | 4 | `Available` |
| `<ToggleAI>` | 3 | -- (**not in GR**) |
| `<Restart>` | 1 | -- (loop the plan forever) |


### 3. `.ATR` -- enemy skill template

`.ATR` is plain XML and is what `<Actor File="...">` points at. The
gameplay-relevant part is five integers:

```
<ArmorLevel>1</ArmorLevel>     damage soaked
<Weapon>2</Weapon>             weapon skill / accuracy
<Stamina>1</Stamina>           stamina
<Stealth>1</Stealth>           how hard he is to spot
<Leadership>1</Leadership>     leadership
```

### 4. `.KIT` / `.KIL` / `.GUN` / `.PRJ` -- loadout

All plain XML. `.KIT` is what `<Actor Kit="...">` points at, `.GUN` is a weapon
definition, `.PRJ` a projectile, `.KIL` a kit-restriction list used by the
multiplayer lobby. `.TOE` (20 files, identical in both games) is the *player's*
order of battle, same Company/Platoon/Team/Actor grammar as `<Units>`.

### 5. `.GTF` -- game type, and its script variable table

A `.GTF` is a shell (name, comment, lobby config, objectives) plus two script
blobs, `<ScriptCompiled>` and `<ScriptSource>`. Those blobs are **not base64** --
they are an A..P nibble encoding (see `rsescript.py`): each payload byte becomes
two ASCII characters in `A`..`P`, low nibble first.

The decoded payload opens with the script's **variable table**, which is where the
designer-named tuning numbers live:

```
u32 variableCount
u32 1
u32 2
repeat variableCount times:
    u32   nameLen
    char  name[nameLen]          (no NUL)
    u32   value        <- int for counts, IEEE float BITS for durations/ranges
    u32   id
    u32   0
```

Because the A..P encoding is fixed-width, changing a `value` in place keeps the
payload byte length, the XML text length, and therefore the archive slot size.


Jungle Storm is the interesting one: its `DEFEND` game type carries the enemy
counts as named, directly editable script variables. This is the closest thing
either game has to a built-in 'enemy wave size' dial, and single-player and co-op
carry different values (20/25/35 vs 30/40/50).

The `*_Text` / `*Id` values are **string ids**, not numbers to tune. They index
the string table that the file's `<ScriptCompiled>` blob opens with
(`rsescript.strings()`), so they resolve:

```
Lose Text = 8   ->  "?Your base has been captured...  Defeat!"
```

`rsescript.py` run on a `.GTF` prints both tables and does that cross-reference
for you.

Every `.GTF` variable table in this game:

**`(COOP) DEFEND.GTF`**

```
Lose Text                  = 8
Recruit enemy count        = 30
Veteran enemy count        = 40
Elite enemy count          = 50
Proximity shrink rate      = 10
Capture time               = 11
Proximity initial range    = 100
Proximity start time       = 300 (float)
Death timeout              = 20 (float)
Proximity min range        = 30
Win Retreat Text           = 9
Win Kills Text             = 10
Win Time Text              = 11
```

**`(COOP) FIREFIGHT.GTF`**

```
Win Text                   = 4
Lose Text                  = 31
```

**`(COOP) RECON.GTF`**

```
Loss Text                  = 1
Win Text                   = 2
Lose Time Text             = 24
```

**`(SOLO) LAST MAN STANDING.GTF`**

```
Win Text                   = 4
Loss Text                  = 5
Draw Text                  = 9
```

**`(SOLO) MOUSE HUNT.GTF`**

```
Mouse Kit                  = 5
Mouse Sound                = 7
Score for kill as mouse    = 5
Score for becoming mouse   = 2
Mouse Sound 3D             = 29
Invincibility Time         = 5 (float)
temps partie               = 180
penalite                   = 10
Lose Text                  = 206
Win Text                   = 216
TimeBeforeRandomMouse      = 30
```

**`(SOLO) SHARPSHOOTER.GTF`**

```
Lose Text                  = 1
Win Text                   = 3
Draw Text                  = 4
```

**`(SP) DEFEND.GTF`**

```
Lose Text                  = 8
Recruit enemy count        = 20
Veteran enemy count        = 25
Elite enemy count          = 35
Proximity shrink rate      = 10
Capture time               = 11
Proximity initial range    = 100
Proximity start time       = 300 (float)
Death timeout              = 20 (float)
Proximity min range        = 30
Win Retreat Text           = 9
Win Kills Text             = 10
Win Time Text              = 11
```

**`(SP) FIREFIGHT.GTF`**

```
Win Text                   = 4
Lose Text                  = 8
```

**`(SP) RECON.GTF`**

```
Loss Text                  = 1
Win Text                   = 2
```

**`(TEAM) DOMINATION.GTF`**

```
Lose Text                  = 32
Win Text                   = 37
Draw Text                  = 71
End Control 1              = 76
End Control 2              = 77
Begin Control 1            = 82
Begin Control 2            = 83
Begin Control 3            = 115
End Control 3              = 116
```

**`(TEAM) HAMBURGER HILL.GTF`**

```
Lose Text                  = 32
Win Text                   = 37
Begin King                 = 67
End King                   = 68
Draw Text                  = 71
```

**`(TEAM) LAST MAN STANDING.GTF`**

```
Win Text                   = 4
Loss Text                  = 5
Draw Text                  = 9
```

**`(TEAM) SEARCH AND RESCUE.GTF`**

```
Captive Kit                = 3
Capture Text               = 13
Uncapture Text             = 15
Captive Class A            = 16
Captive Class B            = 17
Captive Class C            = 18
Win Text                   = 427
Loss Text                  = 428
Draw Text                  = 429
```

**`(TEAM) SIEGE.GTF`**

```
Defender win text          = 2
Defender lose text         = 3
Attacker win text          = 4
Attacker lose text         = 5
Capture time               = 11
Attacker notification      = 18
Defender notification      = 19
```

Note `(SOLO) MOUSE HUNT.GTF` carries two variables named in French --
`temps partie` (game time, 180) and `penalite` (10). Jungle Storm's extra
multiplayer modes were evidently authored by a French-speaking team; Ghost
Recon's `.GTF` set has no French names.

### 6. `.ATR` skill tiers in this game

**Jungle Storm flattened the enemy skill system.** Weighted by how often each
template is actually placed in a mission (1000 placed enemy actors drawn from 298
distinct `.ATR` files):

| field | distribution across placed enemies |
|---|---|
| `ArmorLevel` | **0 x986**, 1 x5, 2 x2, 3 x7 |
| `Weapon` | **1 x997**, 2 x2, 4 x1 |
| `Stamina` | **1 x989**, 2 x9, 3 x2 |
| `Stealth` | **1 x997**, 2 x2, 4 x1 |
| `Leadership` | **1 x999**, 3 x1 |

There is no `_rec_/_vet_/_eli_` naming in Jungle Storm at all; templates are named
for their clothing (`_g_regularcuba_blacksuit.atr`). So in Jungle Storm mission
difficulty is almost **purely a head-count**, driven by the `Easy`/`Normal`/`Hard`
suppression flags. That also means the `.ATR` skill fields are a large *untouched*
lever here -- essentially every enemy in the game currently sits at the floor value.

### 7. Where enemies are NOT

`.AOL` (object list) is world props and doors, `.POL` is visibility portals and
`.MOL` is level geometry -- despite the "object list" name, **none of them place
a soldier**. Verified by decompressing every file in both archives and searching
for `<Actor`: outside `.MIS`, the only file in either game with a positioned
`<Actor>` is `/TRAINING.TOE`, which places the *player's* training squad.

Every enemy in this game is in a `.MIS`, in `<Units>`. See FORMATS.md S3.1.

## Per-mission enemy head-count

| mission | Easy | Normal | Hard/Elite | enemy teams | plans |
|---|---:|---:|---:|---:|---:|
| C01_PLANTATION               |   35 |   42 |   48 |   21 |   20 |
| C02_MILITARY_CAMP            |   31 |   37 |   50 |   29 |   26 |
| C03_HIGH_SIERRA              |   24 |   33 |   42 |   25 |   32 |
| C04_SWAMP_AIRFIELD           |   27 |   37 |   55 |   28 |   36 |
| C05_BRIDGES                  |   34 |   41 |   48 |   24 |   37 |
| C06_POLLING_CENTER           |   33 |   39 |   45 |   25 |   28 |
| C07_BEACH_RESORT             |   36 |   43 |   50 |   31 |   30 |
| C08_MOUNTAIN_STRONGHOLD      |   39 |   48 |   52 |   37 |   40 |
| G02_VILLAGE                  |   41 |   45 |   50 |   32 |   63 |
| G03_THE_ROCK                 |   24 |   40 |   59 |   26 |   25 |
| G04_TRAIN                    |   44 |   55 |   64 |   36 |   48 |
| G05_DOCK                     |   39 |   49 |   56 |   29 |   33 |
| TAC01_SHOOTING               |   15 |   15 |   15 |    5 |    6 |
| TAC02_RESCUE                 |   15 |   21 |   21 |    6 |    5 |
| TAC03_DEMOLITION             |   23 |   23 |   23 |    9 |    9 |
| TAC04_ANTIVEHICLE            |    6 |    6 |    6 |    4 |    8 |
| TAC05_DEFEND                 |   26 |   31 |   31 |   10 |   10 |
| U01_TRANSMISSION             |   49 |   56 |   65 |   39 |   70 |
| U02_RIVER                    |   37 |   47 |   54 |   21 |   29 |
| U03_RESCUE                   |   28 |   44 |   67 |   24 |   24 |
| U05_RAIL                     |   51 |   52 |   54 |   25 |   29 |


## What I did NOT crack -- stated plainly

* **The compiled script node graph.** Past the variable table the payload is a node
  graph I did not decode. I can read every designer node name and comment out of it
  (that is how the wave logic above was located) and I can read and rewrite the
  variable table, but I cannot re-wire node connections, nor read a constant that
  was typed straight into a node instead of into a variable.
* **Consequence:** mission-level wave *timing* is not reachable as a named variable.
  I checked every mission in both games: 44 of the 45 of the `.MIS` files carry a script
  variable table with zero entries; the single exception is `C06_POLLING_CENTER.MIS`, which has exactly one,
  `JeepProxility = 5.0`. So a timer like
  "Camp Wave 2 Timer" in `M01_CAVES.MIS` exists as a node with its constant baked
  into the graph, and changing it needs the node format.
* **Next probe if that is wanted:** `(SP) DEFEND.GTF` and `(COOP) DEFEND.GTF` in
  Jungle Storm are a near-perfect structural pair -- 2390 vs 2381 payload bytes,
  identical variable names, and they differ only in the three enemy counts. Diffing
  those two decoded payloads is the cleanest available alignment target for mapping
  node records. A second pair is `(SOLO)` vs `(TEAM) LAST MAN STANDING.GTF`.

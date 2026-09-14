# Enemy population and spawning -- Ghost Recon (PS2, SLUS-20613)

Everything here was read out of the retail `gr.img` / `menu.img` with `grimg.py` +
`rselzo.py` + `rsescript.py` in this same folder. Nothing is inferred from the
PC version of the game.

## Headline numbers

Counting every `<Actor>` inside every non-`Allied` `<Company>` of every mission
that has an order of battle (28 missions; the remaining ones are training and
multiplayer maps with no enemy company at all):

| difficulty | enemy soldiers placed, all missions |
|---|---:|
| Easy | **678** |
| Normal | **959** |
| Hard / Elite | **1099** |

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
| `Idle` | idle-animation index (1..17 observed) |
| `Stance` | 1/2/3 (stand / crouch / prone) |
| `Lvl` | building floor index |

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
| `<Point>` | 2446 | `Pos`, `Lvl` |
| `<Plan>` | 593 | `Assigned` |
| `<Path>` | 357 | `Action` 1/2 |
| `<Alertness>` | 267 | `State` 1/2, `Change` |
| `<Cover>` | 197 | `Pos0`, `Pos1`, `Time` (7.00 / 10.00 / 15.00 / 20.00 / 45.00) |
| `<CombatROE>` | 187 | `State` 1/2 |
| `<MoveROE>` | 155 | `State` 1/2 |
| `<AddZone>` | 147 | `Type`, `Lvl` |
| `<Pace>` | 111 | `Type` 1/2 |
| `<Patrol>` | 90 | -- |
| `<Speed>` | 88 | `Rate` 1.50..20.00 |
| `<Grenades>` | 83 | `Available` |
| `<Stance>` | 56 | `Type` 1/2/3 |
| `<DestroyTarget>` | 36 | `Target`, `Vehicle` |
| `<EnterVehicle>` | 31 | `Target`, `Driver` |
| `<Wait>` | 28 | `Time` 1.00..30.00 |
| `<Formation>` | 25 | `Type` 1/2 |
| `<Orientation>` | 14 | `Facing` |
| `<Follow>` | 5 | `Target`, `Range` |
| `<Restart>` | 4 | -- (loop the plan forever) |
| `<ExitVehicle>` | 2 | -- |
| `<WeaponSelect>` | 1 | `Type` |


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


Ghost Recon's `.GTF` variable tables are thin -- they hold text-string ids plus a
couple of Siege / Hamburger-Hill timers. GR does its enemy scaling entirely through
the per-actor difficulty flags in the mission files, not through game-type variables.

Every `.GTF` variable table in this game:

**`(COOP) FIREFIGHT.GTF`**

```
Win Text                   = 4
```

**`(COOP) RECON.GTF`**

```
Loss Text                  = 1
Win Text                   = 2
```

**`(SOLO) HAMBURGER HILL.GTF`**

```
Lose Text                  = 32
Win Text                   = 37
Begin King                 = 67
End King                   = 68
Draw Text                  = 71
```

**`(SOLO) LAST MAN STANDING.GTF`**

```
Win Text                   = 4
Loss Text                  = 5
Draw Text                  = 9
```

**`(SOLO) SHARPSHOOTER.GTF`**

```
Lose Text                  = 1
Win Text                   = 3
Draw Text                  = 4
```

**`(SP) FIREFIGHT.GTF`**

```
Win Text                   = 4
```

**`(SP) RECON.GTF`**

```
Loss Text                  = 1
Win Text                   = 2
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
Win Text                   = 10
Lose Text                  = 11
Capture Text               = 13
Uncapture Text             = 15
Captive Class A            = 16
Captive Class B            = 17
Captive Class C            = 18
Draw Text                  = 23
```

**`(TEAM) SIEGE.GTF`**

```
Defender win text          = 2
Defender lose text         = 3
Attacker win text          = 4
Attacker lose text         = 5
Capture time               = 5
Attacker notification      = 18
Defender notification      = 19
```

### 6. `.ATR` skill tiers in this game

Ghost Recon ships a genuine three-tier enemy ladder, and the filename says which
tier an actor is: `m02_rec_ak47_1.atr` / `m02_vet_ak47_3.atr` / `m02_eli_ak47_2.atr`.
Measured over the 1193 `.ATR` files in `gr.img`:

| tier | files | ArmorLevel | Weapon | Stamina | Stealth | Leadership |
|---|---:|---|---|---|---|---|
| `_rec_` | 241 | 1 | 1-3 | 1-3 | 1-3 | 1-3 |
| `_vet_` | 157 | 2 (3 files at 3) | 2-4 | 2-4 | 2-4 | 2-4 |
| `_eli_` | 124 | 3 (3 files at 1) | 3-5, 3 at 8 | 3-5, 3 at 8 | 3-5, 3 at 8 | 3-5, 3 at 8 |

So in Ghost Recon you can raise difficulty **either** by adding actors **or** by
repointing `File=` at the `_eli_` variant of the same model.

## Per-mission enemy head-count

| mission | Easy | Normal | Hard/Elite | enemy teams | plans |
|---|---:|---:|---:|---:|---:|
| D01_BEACH                    |   25 |   36 |   42 |   17 |   14 |
| D02_REFINERY                 |   26 |   32 |   38 |   21 |   30 |
| D03_TRAINDEPOT               |   26 |   34 |   40 |   13 |   14 |
| D04_RIVERBED                 |   22 |   32 |   38 |   12 |   16 |
| D05_AURORA                   |   23 |   35 |   42 |   19 |   19 |
| D06_GHOSTTOWN                |   31 |   38 |   38 |   27 |   32 |
| D07_ROADBLOCK                |   27 |   38 |   44 |   23 |   25 |
| D08_TANK                     |   26 |   31 |   44 |   17 |   23 |
| M01_CAVES                    |   26 |   32 |   47 |   27 |   32 |
| M02_FARM                     |   16 |   31 |   39 |   20 |   22 |
| M03_RRBRIDGE                 |   12 |   21 |   25 |   11 |   16 |
| M04_VILLAGE                  |   19 |   32 |   41 |   17 |   21 |
| M05_EMBASSY                  |   22 |   43 |   49 |   20 |   23 |
| M06_CASTLE                   |   36 |   48 |   52 |   22 |   26 |
| M07_RIVER                    |   30 |   44 |   48 |   18 |   18 |
| M08_BATTLEFIELD              |   32 |   45 |   48 |   26 |   32 |
| M09_SWAMP                    |   21 |   39 |   43 |   14 |   16 |
| M10_RUINED_CITY              |   21 |   43 |   47 |   22 |   42 |
| M11_POW_CAMP                 |   23 |   37 |   42 |   18 |   10 |
| M12_DOCKS                    |   40 |   55 |   64 |   38 |   30 |
| M13_AIRBASE                  |   28 |   33 |   37 |   15 |   18 |
| M14_MOUNTAIN                 |   36 |   45 |   47 |   28 |   48 |
| M15_RED_SQUARE               |   25 |   39 |   48 |   20 |   29 |
| TAC01_SHOOTING               |   15 |   15 |   15 |    5 |    6 |
| TAC02_RESCUE                 |   15 |   21 |   21 |    6 |    5 |
| TAC03_DEMOLITION             |   23 |   23 |   23 |    9 |    9 |
| TAC04_ANTIVEHICLE            |    6 |    6 |    6 |    4 |    7 |
| TAC05_DEFEND                 |   26 |   31 |   31 |   10 |   10 |


## What I did NOT crack -- stated plainly

* **The compiled script node graph.** Past the variable table the payload is a node
  graph I did not decode. I can read every designer node name and comment out of it
  (that is how the wave logic above was located) and I can read and rewrite the
  variable table, but I cannot re-wire node connections, nor read a constant that
  was typed straight into a node instead of into a variable.
* **Consequence:** mission-level wave *timing* is not reachable as a named variable.
  I checked every mission in both games: all 46 of the `.MIS` files carry a script
  variable table with zero entries. So a timer like
  "Camp Wave 2 Timer" in `M01_CAVES.MIS` exists as a node with its constant baked
  into the graph, and changing it needs the node format.
* **Next probe if that is wanted:** `(SP) DEFEND.GTF` and `(COOP) DEFEND.GTF` in
  Jungle Storm are a near-perfect structural pair -- 2390 vs 2381 payload bytes,
  identical variable names, and they differ only in the three enemy counts. Diffing
  those two decoded payloads is the cleanest available alignment target for mapping
  node records. A second pair is `(SOLO)` vs `(TEAM) LAST MAN STANDING.GTF`.

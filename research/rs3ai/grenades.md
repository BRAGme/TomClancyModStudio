# RS3 PS2 (SLUS-20883) — enemy grenade and molotov use

Static analysis only. Sources used:

* `E:\PS2 Games\Tom Clancy's Rainbow Six 3 (USA).iso.orig` (pristine retail image, Nov 2025).
  The working ISO `…(USA).iso` is **already modded** — do not read stock values from it.
* `scratchpad/rs3/sp.bin` — decompressed SP overlay, 5,585,280 bytes,
  SHA-1 `e9bb12138a1e69d551ac9f6b958114e5b2e830da`. File offset = VA − 0x00100000.
* All 85 `.LIN` packages decompressed with `r6patch.lin_decompress`.

Every instruction word quoted below was machine-read out of `sp.bin` with `r6.w()` in this
session; the raw words are printed in §6. **No overlay word patch is proposed** — every edit
recommended here is a data edit.

---

## 0. Short answers

| | Question | Answer |
|---|---|---|
| **(a)** | Does a throw *chance* exist? | **Only one probability exists in the whole pipeline, and it is a *carry* roll, not a *throw* roll.** It is the 3-digit `%03d` field in the `NbOfGrenade=` table of an AI template. It is rolled **once, at spawn**, by `PickGrenadeClass` at VA `0x003c92e0`. There is no per-throw probability anywhere in code or data — `CanThrowGrenade` is a deterministic tactical test (distance / LOS / nav-point / reaction delay). |
| **(b)** | What decides whether a terrorist carries a molotov? | Purely the template the spawn point names. A terrorist carries `R6Weapons.R6MolotovGadget` **iff** the template body that his spawn point references lists that class in its `NbOfGrenade=` table and the spawn-time roll lands on it. Stock, exactly **4 of 118** template bodies list a molotov, and only 2 of those are referenced by any level (both on Alcatraz). |
| **(c)** | Is `WS[43].bUsing=true` sufficient? | **No — and it is not even necessary. `WS[n]` is dead data on PS2.** The names `WS`, `bUsing`, `weaponname`, `sndName0..3` and the literal `"WS["` appear in **zero** places in the SP overlay, in all 85 decompressed `.LIN` packages, in `SLUS_208.83`, in `mp.soz`, or in `OVL/`/`IRX/`/`NTSC_CD/`. Nothing on the disc can parse those lines. They are a leftover of the Xbox/PC `MultiBank_SoundLoad` system (the INI even labels them `//{sxd MultiBank_SoundLoad 2003/10/28`). |

---

## 1. Where the data actually lives

`.TPT` files do not exist on the disc, and the literal text `NbOfGrenade=` does **not** occur
anywhere in the raw ISO (full 2.6 GB byte scan: 0 hits). The template bodies ship **only**
inside the three COMMON packages, as one contiguous run of 118 plain-text `.tpt` bodies
concatenated with no separators and no per-file header:

| package | decompressed size | blob start | blob length | blob SHA-1 |
|---|---|---|---|---|
| `/COMMON.LIN` | 5,102,267 | `0x2A8675` | 50,266 | `4acb4971e942223c3d9bce022ea2d8f0419cbaab` |
| `/COMMONOFF.LIN` | 5,094,061 | `0x2A866A` | 50,266 | `4acb4971e942223c3d9bce022ea2d8f0419cbaab` |
| `/COMMON_SS.LIN` | 5,094,061 | `0x2A866A` | 50,266 | `4acb4971e942223c3d9bce022ea2d8f0419cbaab` |

The three blobs are **byte-identical**; `COMMONOFF`/`COMMON_SS` are simply shifted by
**−0x0B** relative to `COMMON`. Any tool must patch all three (`grenades.py` already does).

COMMON also carries, at `0x21 … 0x8FAB`, an embedded **build directory** of 846 rows — the
compiled form of `/MANIFEST.INI`:

```
<lenByte> <path>\0 <u32 masterOffset> <u32 size> <u32 0>
  e.g.  0E "System\Core.u" 00  00000000  00011E15  00000000
```

Offsets are contiguous over a 586 MB master image (`psx2game.umd`), so they are **build-time**
addresses, not offsets into the LIN. 121 of the rows are `Template\*.tpt` with their exact
byte sizes. That size table is the only thing that names the bodies; there is **no
name→offset index for the blob inside the package** (searching COMMON for the u32s
`0x2A8675`, `0x2A886D`, `0x2A8F21`, `0x2B3DE7` and for a u32/u16 size array `504,428,432,428`
returns nothing). **Consequence for a mod tool: treat every blob edit as byte-length-locked.**
If the loader reconstructs the association by consuming the directory's `Size` fields in
order, a single changed length desynchronises every later template.

Three of the 121 manifest templates have no body in the blob. Multiset difference of the
121 manifest sizes against the 118 block sizes gives exactly: **one 431-byte template, one
428-byte template, and `Template\Normal.tpt` (556)**. (`Normal` is named by spawn points in
ALCATRAZ_A, GARAGE_B, PARADE_B and TRIESTE_A — either those points are broken, or `spawns.py`'s
structural matcher is picking up a different string field there. Unresolved; flagged as a guess.)

---

## 2. (a) The chance — what it is, and exactly where the bytes are

### 2.1 The file format

The parser is **native**, in the SP overlay at `0x003CA964 … 0x003CBB78`. Its literals sit at
`0x005E4FA0…0x005E51C0`:

```
0x005e4fa0  "..\Template\"     0x005e4fb0  ".tpt"
0x005e4fb8  "Version="         0x005e4fc8  "Type="
0x005e4fd0  "NbOfPawn="        0x005e4fe0  "NbOfWeapon="
0x005e4ff0  "%03d, %s"         0x005e5000  "R63rdWeapons."
0x005e5040  "None.None"        0x005e5050  "NbOfGrenade="
0x005e5060  "GasMask="         0x005e5080  "Class %s in template %s doesn't exist."
0x005e5130  "Total weapon chance is %d%% in template %s"
0x005e5160  "Total grenade chance is %d%% in template %s"
0x005e5190  "Total personality chance is %d%% in template %s"
```

Each grenade line is read into a 0x200-byte line buffer and handed to **sscanf**
(`0x0012E308`, confirmed sscanf by its other 19 call sites: `"%d"`, `"%f"`, `"%d %d %d %d"`,
`"%x%x%s%s%s%s"`) with the format `"%03d, %s"` at `0x003CB258…0x003CB268`.

Note the `3` in `%03d` is a **scanf field width**, not a printf flag — the chance is a
**fixed-width 3-digit decimal**. That is why `grenades.py`'s digit-for-digit rewrite is the
correct shape of edit.

### 2.2 The parsed struct

Parse result, from the store sites:

| template field | meaning | evidence |
|---|---|---|
| `+0x50` | weapon array (8-byte entries `{u32 chance, UClass*}`) | `addiu $a0,$s0,0x50` @ `0x003CB190` |
| `+0x54` | weapon count | |
| `+0x5C` | **grenade array**, 8-byte entries `{u32 chance, UClass*}` | `addiu $a0,$s0,0x5c` @ `0x003CB348` |
| `+0x60` | **grenade count** | `lw $v0,0x60($s0)` @ `0x003CB9B8` |
| `+0x10 … +0x24` | personality (Coward / DeskJockey / Normal / Hardened / SuicideBomber / PSniper) | `0x003CB9F8…` |

`None.None` is special-cased at `0x003CB288…0x003CB2A8`: the class pointer is stored as `-1`
rather than being looked up. Anything else goes through `StaticLoadClass`, and a bad name
prints `Class %s in template %s doesn't exist.` and leaves the entry null.

After parsing, the per-entry chances are **converted in place into a prefix sum** and the
total is validated against 100 (`addiu $v0,$zero,0x64` / `beq $a2,$v0` at
`0x003CB9C4`/`0x003CB9C8`); a mismatch only prints `Total grenade chance is %d%% in template %s`.

### 2.3 The roll — `PickGrenadeClass`, VA `0x003C92E0`

```
003c92e0  addiu   $sp, $sp, -0x70
003c92f8  jal     0x146df0            ; RNG
003c9300  addiu   $v1, $zero, 0x64    ; 100
003c9304  lw      $a2, 0x60($s0)      ; grenade count
003c9308  div     $zero, $v0, $v1
003c9314  mfhi    $v1                 ; $v1 = rand % 100
003c9320  lw      $v0, 0x5c($s0)      ; grenade array
003c9328  lw      $v0, ($v0)          ; cumulative chance[i]
003c932c  slt     $v0, $v1, $v0       ; roll < cum[i] ?
003c9330  bnez    $v0, 0x3c934c
003c935c  lw      $v0, 0x5c($s0)
003c936c  lw      $s0, 4($v0)         ; -> UClass* for the chosen entry
```

Behaviour worth knowing for a mod tool:

* The roll is `rand() % 100` against a **prefix sum**, so the list must total **100**.
  If it totals less, the fall-through leaves the class null = *no grenade* (the loop exits
  with `$a0 == $a2` and `$s0` is zeroed at `0x003C9370`).
* `-1` (from `None.None`) and `0` both mean "carry nothing".
* This runs **once per pawn at spawn**. Nothing re-rolls it.

### 2.4 There is no second, per-throw chance

* `sp.bin` contains **no** grenade-probability constant (`m_fMinDistToThrowGrenade` and
  `m_fGrenadeReactionDelay*` resolve through package name tables, not overlay literals).
* Scanning every `.LIN` package for any name containing `hance` yields:
  `m_iChance`, `iChance`, `fChance`, `m_iBlindFireChance`, `m_HostageShootChance`,
  `iShootingChance`, `iLookBackChance`, `m_AnimChance`, `m_fActions1..3Chance`,
  `GetCurrentChanceToHit`, `fNeededChanceToHit`, `m_iChanceToDetectShooter`,
  `GetKillingHostageChance`, `m_iChanceToKillHostageModifier*`.
  **Nothing grenade-related.**
* The AI throw path is UnrealScript in COMMON and is deterministic:
  `CanThrowGrenade`, `CanThrowGrenadeIntoRoom`, `FindRandomNavPointToThrowGrenade`,
  `GetGrenadeDirection`, `InitGrenadeForThrow`, `PENDING_ThrowGrenade`,
  `R6ACTION_ThrowGrenade`, `GrenadeWasThrown`, `NoGrenadeLeft`, gated by
  `m_fMinDistToThrowGrenade` and `m_fGrenadeReactionDelay{Recruit,Veteran}`.

**So "make enemies throw more" has exactly two data knobs: the carry chance in the template,
and `m_fMinDistToThrowGrenade` in `/R6GAMESETTINGS.INI`.**

### 2.5 Stock `/R6GAMESETTINGS.INI` (plain text, 3 identical copies)

Verified against the pristine ISO, all three vokes copies, size 17,267 bytes each:

```
m_fGrenadeReactionDelayRecruit=1.0
m_fGrenadeReactionDelayVeteran=0.5
m_fMinDistToThrowGrenade=500
m_PlayerGrenadeMultiplierRecruit=1
m_PlayerGrenadeMultiplierVeteran=1
m_PlayerGrenadeMultiplierElite=1
```

> The stock value is **500**, not 200. The working ISO already carries a 200 edit (file size
> 17,230 there). Any tool that reads "current" values must read `.iso.orig`.

### 2.6 Worked example — the exact text block, in situ

`/COMMON.LIN` block 0, file offset `0x2A8675`, **504 bytes**, uniquely size-matched to
`Template\Alcatraz_THT.tpt` (504) in the embedded directory. Shown with `\r\n` made visible;
the file has no LF-only line endings and no trailing newline before the next block:

```
0x2A8675  Version=8\r\n
          \r\n
          Type=Terrorist\r\n
          \r\n
          NbOfWeapon=3\r\n
          025, R63rdWeapons.AssaultL85A1\r\n
          025, R63rdWeapons.PistolUSP\r\n
          050, R63rdWeapons.SubMP5A4\r\n
          \r\n
          NbOfGrenade=2\r\n
0x2A870C  020, R6Weapons.r6fraggrenadegadget\r\n     <-- the chance:  3 digits at 0x2A870C
0x2A8730  080, None.None\r\n                        <-- the "no grenade" complement at 0x2A8730
          \r\n
          NbOfTag=0\r\n
          \r\n
          NbOfSeePlayerEvent=0\r\n
          \r\n
          NbOfHearPlayerEvent=0\r\n
          \r\n
          Coward=0\r\n  DeskJockey=0\r\n  Normal=0\r\n
          Hardened=100\r\n  SuicideBomber=0\r\n  PSniper=0\r\n
          \r\n
          RndVariation=10\r\n  Assault=70\r\n  Demolitions=50\r\n  Electronics=50\r\n
          SSniper=50\r\n  Stealth=70\r\n  SelfControl=70\r\n  Leadership=50\r\n
          Observation=90\r\n
          \r\n
          Flashlight=0\r\n
          GasMask=0
0x2A886D  <next block begins immediately: "Version=8\r\n...">
```

To raise this template's frag-carry rate from 20 % to 90 %:

| file | byte offset | current | new |
|---|---|---|---|
| `/COMMON.LIN` | `0x2A870C` | `"020"` | `"090"` |
| `/COMMON.LIN` | `0x2A8730` | `"080"` | `"010"` |
| `/COMMONOFF.LIN` | `0x2A8701` | `"020"` | `"090"` |
| `/COMMONOFF.LIN` | `0x2A8725` | `"080"` | `"010"` |
| `/COMMON_SS.LIN` | `0x2A8701` | `"020"` | `"090"` |
| `/COMMON_SS.LIN` | `0x2A8725` | `"080"` | `"010"` |

(Offsets are into the **decompressed** package; write back through
`r6patch.lin_rebuild` + `Vokes.put`, which preserves the compressed length.)

### 2.7 Census of the 118 template bodies

Gadget classes referenced across all 118 `NbOfGrenade` tables:

| class string | entries |
|---|---|
| `None.None` | 87 |
| `R6Weapons.r6fraggrenadegadget` | 41 |
| `R6Weapons.R6MolotovGadget` | **4** |
| `R6Weapons.r6smokegrenadegadget` | 2 |
| `R6Weapons.r6teargasgrenadegadget` | 1 |
| `R6Weapons.r6flashbanggadget` | 1 |

`grenades.py`'s regex
`NbOfGrenade=2\r\n(\d{3}), R6Weapons\.(\w+)\r\n(\d{3}), None\.None`
matches the **16 two-entry tables** per package (48 across the three packages) — i.e. the
"carry a frag or carry nothing" shape only. The other 25 frag entries are `100,` single-entry
tables (already guaranteed) and the multi-gadget tables. That is consistent with the earlier
note "16 templates in each of 3 COMMON packages", and the note is **confirmed from the data**.

---

## 3. (b) What puts a molotov in a terrorist's hands

### 3.1 The chain

```
level .LIN spawn point
   └─ string property: template NAME (e.g. "E3-H-Mp5-Mc")   + u32 m_iChance
        └─ COMMON*.LIN template body  "…\NbOfGrenade=1\r\n100, R6Weapons.R6MolotovGadget…"
             └─ StaticLoadClass  (0x003CB2B0…0x003CB2F4)
                  └─ PickGrenadeClass  0x003C92E0   (rand%100 vs prefix sum)
```

Nothing else is involved. In particular the map INI is **not** in this chain, and
`R6Weapons.R6MolotovGadget` lives in `R6Weapons.u` inside COMMON (name found at COMMON
offset `0x1AF005`), which is loaded on **every** map. The class is globally available
everywhere already.

### 3.2 The four molotov templates, stock

| block | `/COMMON.LIN` offset | size | chance-digit offset | body | identification |
|---|---|---|---|---|---|
| 1 | `0x2A886D` | 428 | `0x2A88CB` = `100` | `L85A1` + `100, R6Weapons.R6MolotovGadget` | `E3-H-M16-Mc` (E3 group; size 428) |
| 5 | `0x2A8F21` | 424 | `0x2A8F7B` = `100` | `SubMP5A4` + `100, R6Weapons.R6MolotovGadget` | `E3-H-Mp5-Mc` (E3 group; size 424) |
| 110 | `0x2B3DE7` | 426 | `0x2B3E44` = `100` | `AssaultAK47` + `100, R6Weapons.R6MolotovGadget` | `Trieste-G-AK47` (Trieste group; size 426) |
| 111 | `0x2B3F91` | 424 | `0x2B3FEC` = `100` | `SubMac119` + `100, R6Weapons.R6MolotovGadget` | `Trieste-G-SubMac119` (Trieste group; size 424) |

Subtract `0x0B` for the same blocks in `COMMONOFF.LIN` / `COMMON_SS.LIN`.

Two traps found here:

* **The `-Mc` suffix is not reliable.** `Template\Island-H-M60-Mc.tpt` is 425 bytes, and 425 is
  a **globally unique** size among the 121 manifest templates, so block 31 (`0x2ABA4F`,
  425 bytes) *is* that template. Its body is
  `100, R63rdWeapons.SubUMP` + `100, R6Weapons.r6fraggrenadegadget` — **frag, not molotov**.
  `Island-H-Mac-Mc` (428) is likewise a frag body. So Island's "molotov" enemies throw frags.
* **`Trieste-G-*` are unreachable.** No level package's spawn table names them (see §3.3).

Template names in the manifest are historically stale in other ways too (e.g. `Island-H-M60`
carries a `SubUMP`, `Island-N-92Fs` carries a `PistolMk23`, `Air-H-Mac119-G` carries a
`SubMP5A4`). **Identify templates by body content + unique byte size, never by name.**

Identification confidence: the 16 rows in §7 are *rigorous* (globally unique size, so the
size alone pins the name). The four rows above rely on unique size **within a level group**,
where the group boundaries are anchored by those rigorous rows. I rate blocks 1/5 as certain
(ALCATRAZ_A really does reference `E3-H-M16-Mc` and `E3-H-Mp5-Mc`, and there are exactly two
molotov bodies in that group) and blocks 110/111 as high-confidence-but-inferred.

### 3.3 Which levels reference which templates (stock)

Derived with `spawns.py` over every decompressed level package. `*OFF` and `*_SS` variants are
identical, so only one is listed.

| level | spawn pts | templates referenced (count) |
|---|---|---|
| ALCATRAZ_A | 30 | `E3-N-M16` 13, `E3-N-Mp5` 4, **`E3-H-Mp5-Mc` 4**, `Alcatraz_THT` 4, **`E3-H-M16-Mc` 2**, **`E3-H-M16-MC` 1**, `E3-H-Mp5-FB` 1, `Normal` 1 |
| ALCATRAZ_B | 0 | — |
| GARAGE_A | 19 | `Garage-H-Ump` 7, `Garage-H-Usas` 4, `Garage-B-G3A3-G` 3, `Garage-H-DEagle` 3, `Garage-B-G3A3` 2 |
| GARAGE_B | 17 | `Garage-H-Ump` 5, `Garage-H-DEagle` 3, `Garage-H-Usas` 3, `Garage-B-G3A3` 3, `Garage-B-G3A3-G` 2, `Normal` 1, `Garage-Veron` 1 |
| IMPORT_EXPORT_B | 31 | `Import-N-AK47` 15, `Import-H-AK47-G` 7, `Import-H-AK47-FL` 4, `Import-N-Mac` 2, `Import-S-PSG` 2, `Import-H-AK47-N` 1 |
| ISLAND_A | 31 | `Island-H-M60` 12, `Island-N-Mac` 12, `Island-N-92Fs` 3, `Island-H-Mac-Mc` 3, `Island-H-M60-Mc` 3, `Island-N-M1` 2, `Island-H-Mac` 1 |
| MEATPACKING_A | 33 | `Meat-H-Galil` 9, `Meat-H-SubMac119` 7, `Meat-H-MP5SD5-G` 6, `Meat_THT` 5, `Meat-H-MP5SD5` 3, `Meat-H-G3A3` 2, `Meat-H-SubMac119-G` 1 |
| MOUNTAIN_HIGHWAY_A | 18 | `Mountain-N-Ak47-G` 8, `Mountain_THT` 4, `Mountain-N-Ak47` 3, `Mountain-N-92Fs-G` 3, `Mountain-N-92Fs` 1, `Mountain-N-P90-G` 1 |
| MOUNTAIN_HIGHWAY_B | 27 | `Mountain-N-Ak47-G` 15, `Mountain-N-Ak47` 15, `Mountain_THT` 5, `Mountain-N-P90-G` 4, `Mountain-N-92Fs-G` 1 |
| OFFICE_COMPLEX_A | 19 | `Office-H-Tar` 7, `office-H-Ump` 5, `Office-H-Ump` 4, `Office-H-Mk23` 3 |
| OFFICE_COMPLEX_B | 10 | `Office-H-Tar` 6, `Office-H-Mk23` 2, `Office-S-Psg1` 1, `Office-H-Ump` 1 |
| OIL_REFINERY_A | 32 | `Oil-N-P90` 14, `Oil-N-MAC911P` 7, `Oil-N-M1` 5, `Oil_THT` 5, `Oil-N-SR2` 1 |
| OIL_REFINERY_B | 23 | `Oil-N-P90` 11, `Oil-N-SR2` 4, `Oil_THT` 3, `Oil-N-MAC911P` 2, `Oil-N-M1` 2, `Oil-H-RPG-N` 1 |
| OLDCITY_A | 31 | `OldC-N-AK47` 13, `OldC-N-Galil` 6, `OldCity_THT` 5, `OldC-N-HighG-AK47-01-G` 4, `OldC-N-M1` 2, `OldC-N-HighG-AK47-01` 1, `OldC-H-Galil` 1 |
| OLDCITY_B | 30 | `OldC-N-M1` 11, `OldC-N-AK47` 10, `OldC-N-SubTMP` 4, `OldCity_THT` 4, `OldC-N-HighG-AK47-01-G` 2, `OldC-H-AK47-CrazyJoe` 2, `OldC-N-HighG-AK47-01` 1 |
| PARADE_B | 23 | `Parade-H-M16A2-G` 18, `Parade-S-G3A3` 2, `Parade-H-USAS12` 2, `Normal` 1 |
| PENTHOUSE_A | 22 | `Penthouse-N-Deagle` 9, `Penthouse_THT` 9, `Penthouse-N-Mac` 4 |
| SHIPYARD_A | 27 | `None` 14, `Ship-N-Ak47` 9, `Shipyard_THT` 6, `Ship-H-MP5A4` 5, `Ship-N-SR2-G` 4, `Ship-N-M1` 3, `Ship-S-M82A1` 1 |
| SHIPYARD_B | 26 | `None` 19, `Ship-N-Ak47` 7, `Ship-H-MP5A4` 5, `Ship-N-M1` 5, `Shipyard_THT` 4, `Ship-N-SR2-G` 2, `Ship-S-M82A1` 1 |
| TRIESTE_A | 39 | `OldC-N-SubTMP` 10, `OldC-N-HighG-AK47-01-G` 9, `OldC-N-AK47` 7, `OldC-N-M1` 6, `OldCity_THT` 6, `OldC-N-HighG-AK47-01` 5, `Normal` 2, `OldC-H-AK47-CrazyJoe` 2, `Trieste-H-M1` 2, `Office-S-Psg1` 1 |
| AIRPORT_A/B, ALPINES_A/B, ALCATRAZ_B, IMPORT_EXPORT_A, MEATPACKING_B, PARADE_A, all `*_MP_*`, all `TRAINING_*` | 0 | no spawn tables of this shape |

Note that `TRIESTE_A` is populated almost entirely with `OldC-*` templates and never touches
`Trieste-G-AK47` / `Trieste-G-SubMac119` — which is exactly why the two finished molotov
bodies in the Trieste group are dead content.

---

## 4. (c) `WS[43]` — what it really is

`/MAPS/<NAME>.INI` is `[Engine.R6MissionDescription]` config. The `WS[n]` table sits under
its own marker comment:

```
;//{sxd MultiBank_SoundLoad 2003/10/28
m_bArab=false
WS[0]=(bUsing=false,weaponname="Pistol92FS",sndName0="CommonPistols",sndName1="Pistol_92FS_Reloads",…)
…
WS[43]=(bUsing=true,weaponname="R6MolotovGadget",sndName0="Foley_FragGrenade",sndName1="Grenade_Frag",sndName2="X_Gadget_Molotov")
;//}sxd MultiBank_SoundLoad 2003/10/28
```

Every field except `bUsing` and `weaponname` is a sound-bank name. Structurally it is a
*sound-bank residency list*: "this map uses weapon X, so keep these banks loaded".

### 4.1 It is inert on PS2

| probe | scope | hits |
|---|---|---|
| `"WS["` | `sp.bin` (decompressed SP overlay, 5.3 MB) | 0 |
| `"bUsing"` / `"sndName"` / `"weaponname"` | `sp.bin` | 0 |
| `"sndName"` | all 85 decompressed `.LIN` packages | 0 |
| name-table entry `\x03WS\x00` | all 85 decompressed `.LIN` packages | 0 |
| `"bUsing\0"` / `"weaponname"` | all 85 decompressed `.LIN` packages | 0 |
| `"sndName"`, `"WS["`, `"bUsing"`, `"weaponname"`, `"MultiBank"` | `SLUS_208.83`, `mp.soz`, `sp.soz`, `OVL/*`, `IRX/*`, `NTSC_CD/*` | 0 |

Unreal's config importer resolves struct member names through the package name table. Since
`WS`, `bUsing`, `sndName0..3` and `weaponname` are in **no** name table on the disc, and no
native code contains the literals either, nothing can read those lines. (Caveat: `mp.soz` /
`sp.soz` are compressed, so the raw scan of *those two* is weak — but `sp.bin` is the
decompressed SP overlay and is clean, and the package-name-table result is decisive for the
script side.)

### 4.2 The data also disproves it directly

`WS[43].bUsing=true` ships on exactly five map INIs:

| INI | WS[43] | molotov in any template that map uses? |
|---|---|---|
| `/MAPS/ALCATRAZ.INI` | true | — (parent INI) |
| `/MAPS/ALCATRAZ_A.INI` | true | **yes** (`E3-H-M16-Mc`, `E3-H-Mp5-Mc`) |
| `/MAPS/ALCATRAZ_B.INI` | true | no spawn points at all |
| `/MAPS/MEATPACKING.INI` | true | **no** — no `Meat-*` template lists a molotov |
| `/MAPS/OLDCITY.INI` | true | **no** — no `OldC-*` template lists a molotov |

All other 37 map INIs carry `WS[43].bUsing=false`, and `/MAPS/TRIESTE.INI` has no `WS[43]`
line at all. So `true` demonstrably does not create molotovs (Meatpacking, OldCity), and the
templates that *do* carry molotovs are not tied to a `true` (Trieste).

**Answer to (c): `WS[43].bUsing=true` is neither sufficient nor necessary. It gates nothing on
PS2. Setting it costs nothing and can be left in a mod as documentation, but the gadget must
come from the template.**

*(One residual unknown: because nothing loads sound banks from `WS[n]`, this analysis says
nothing about whether a molotov thrown on a non-Alcatraz map will have audio. The molotov's
sounds are referenced by name from the gadget's own script/SFX package, not from the map INI,
so it most likely does — but that is a guess and can only be settled by running the game.)*

---

## 5. Patch / data-edit candidates for a mod tool

### 5.1 Raise the enemy grenade carry chance — SAFE, length-preserving

Regex over the decompressed COMMON packages (this is exactly what
`E:\PS2 Games\R6_3_PS2_CutContent\tools\grenades.py` does, and it is correct):

```python
BLOCK = re.compile(rb"(NbOfGrenade=2\r\n)(\d{3})(, R6Weapons\.[A-Za-z0-9]+\r\n)(\d{3})(, None\.None)")
new   = BLOCK.sub(lambda m: m[1] + b"090" + m[3] + b"010" + m[5], plain)
assert len(new) == len(plain)     # non-negotiable
```

* 16 matches per package × 3 packages.
* The digits are a fixed 3-wide scanf field, so `000`–`100` are all legal and the length never
  changes.
* The two values **must still sum to 100**, otherwise `PickGrenadeClass` falls off the end of
  the prefix sum and the pawn silently carries nothing.
* Apply to `/COMMON.LIN`, `/COMMONOFF.LIN`, `/COMMON_SS.LIN`, then `r6patch.lin_rebuild` +
  `Vokes.put` (all three vokes copies).

### 5.2 Shorten the throw stand-off — SAFE, plain-text INI

| file | key | stock | suggested |
|---|---|---|---|
| `/R6GAMESETTINGS.INI` (×3 vokes copies) | `m_fMinDistToThrowGrenade` | `500` | `200` (already applied on the working ISO) |
| " | `m_fGrenadeReactionDelayRecruit` | `1.0` | lower = AI reacts sooner to *incoming* grenades |
| " | `m_fGrenadeReactionDelayVeteran` | `0.5` | " |

Use `r6patch.py ini-set`; the vokes record carries an explicit size so growth/shrink is fine.

### 5.3 Molotovs on an arbitrary map — three routes, ranked

| route | mechanism | length-safe? | coverage | risk |
|---|---|---|---|---|
| **A. retarget the spawn point** | byte-substitute the template **name string** in the level `.LIN` for an equal-length molotov name (`E3-H-M16-Mc` / `E3-H-Mp5-Mc`, both 11 chars) — `r6patch.py lin-sub` | yes, trivially | **only 6 level packages** have an 11-char name to sacrifice | lowest |
| **B. edit the template body in place, padded** | in a template that already has a gadget entry, rewrite `R6Weapons.r6fraggrenadegadget` (29) → `R6Weapons.R6MolotovGadget` (25) and absorb the 4 bytes as spaces **after the comma**: `100,␠␠␠␠␠R6Weapons.R6MolotovGadget` | yes — line and file length unchanged | **every map**, if it works | medium — **unverified** |
| **C. let the blob change length** | free-form text edit, `lin_rebuild` fixes the chunk header | no | every map | high — the blob has no in-package index, so a length change may desynchronise the loader |

Route A, per level (names of length 11 that are *not* already molotov templates):

| level package | substitutable name | occurrences |
|---|---|---|
| `OLDCITY_AOFF` / `_SS` | `OldC-N-AK47` | 13 |
| `OLDCITY_BOFF` / `_SS` | `OldC-N-AK47` | 10 |
| `TRIESTE_AOFF` / `_SS` | `OldC-N-AK47` | 7 |
| `SHIPYARD_AOFF` / `_SS` | `Ship-N-Ak47` | 9 |
| `SHIPYARD_BOFF` / `_SS` | `Ship-N-Ak47` | 7 |
| `ISLAND_AOFF` / `_SS` | `Island-N-M1` | 2 |
| `MEATPACKING_AOFF` / `_SS` | `Meat-H-G3A3` | 2 |
| `OIL_REFINERY_BOFF` / `_SS` | `Oil-H-RPG-N` | 1 |
| GARAGE, IMPORT_EXPORT, MOUNTAIN_HIGHWAY, OFFICE_COMPLEX, OIL_REFINERY_A, PARADE, PENTHOUSE | — | **no 11-char name — route A impossible** |

(`OldCity_THT` and `Mountain_THT` are also 11 chars but are the map's random-mix templates;
substituting them removes the mix, so avoid unless that is intended.)

Route B rationale and caveat, stated plainly:

* `sscanf("%03d, %s")` — a space in a scanf format matches *zero or more* whitespace, and
  `%s` itself skips leading whitespace, so extra spaces **between the comma and the class
  name** are consumed and the parsed class token is clean.
* `grenades.py`'s own docstring records that *"both whitespace-padded attempts hung the
  loader"*. It does not say where the padding was placed. Padding placed **after** the class
  name would leave sscanf's `%s` clean too, so the recorded failure is not explained by the
  parser as read here — it may have been a different edit (the docstring also mentions a
  gadget-class *substitution* attempt). **Treat route B as a candidate that has one prior
  negative result against it and has not been re-tested. It must be tried in an emulator
  before shipping.**
* If route B works, the general recipe is: for every template body that contains
  `R6Weapons.r6fraggrenadegadget` (41 entries across the 118 bodies), replace with
  `100,␠␠␠␠␠R6Weapons.R6MolotovGadget` style padding; assert the rebuilt blob is still
  exactly 50,266 bytes and the three packages stay byte-identical to each other.

### 5.4 Do not bother with

| edit | why not |
|---|---|
| `WS[43].bUsing=true` on other maps | nothing on the disc parses `WS[n]` (§4) |
| Renaming `Island-H-M60-Mc` / `Island-H-Mac-Mc` to "fix" Island | those names are already in use; the *bodies* carry frags, so fix the body, not the name |
| Overlay word patches | none are needed; the entire pipeline is data |

---

## 6. Machine-verified words (read from `sp.bin` this session with `r6.w()`)

```
0x003c92e0  27bdff90  addiu  $sp, $sp, -0x70      ; PickGrenadeClass entry
0x003c92f8  0c051b7c  jal    0x146df0             ; RNG
0x003c9300  24030064  addiu  $v1, $zero, 0x64
0x003c9304  8e060060  lw     $a2, 0x60($s0)       ; grenade count
0x003c9308  0043001a  div    $zero, $v0, $v1
0x003c9314  00001810  mfhi   $v1                  ; rand % 100
0x003c9320  8e02005c  lw     $v0, 0x5c($s0)       ; grenade array
0x003c9328  8c420000  lw     $v0, ($v0)
0x003c932c  0062102a  slt    $v0, $v1, $v0
0x003c9330  14400006  bnez   $v0, 0x3c934c
0x003c935c  8e02005c  lw     $v0, 0x5c($s0)
0x003c936c  8c500004  lw     $s0, 4($v0)          ; chosen UClass*
0x003cb264  27a63680  addiu  $a2, $sp, 0x3680     ; &chance
0x003cb268  0c04b8c2  jal    0x12e308             ; sscanf("%03d, %s")
0x003cb190  26040050  addiu  $a0, $s0, 0x50       ; weapon array
0x003cb348  2604005c  addiu  $a0, $s0, 0x5c       ; grenade array
0x003cb9b8  8e020060  lw     $v0, 0x60($s0)
0x003cb9c4  24020064  addiu  $v0, $zero, 0x64
0x003cb9c8  10c2000b  beq    $a2, $v0, 0x3cb9f8   ; total == 100 ?
```

I confirm every "current" word above was read out of `sp.bin` with `r6.w()` in this session.
No word patch is proposed anywhere in this document.

---

## 7. Rigorous template identifications (unique byte size ⇒ unambiguous name)

These 16 blocks have a size that is unique both among the 121 manifest templates and among
the 118 blob blocks, so name↔offset is proved, not inferred. They are the anchors that fix
the level-group boundaries used in §3.2. Offsets are `/COMMON.LIN`; subtract `0x0B` for
`COMMONOFF` / `COMMON_SS`.

| block | offset | size | name | grenade table |
|---|---|---|---|---|
| 11 | `0x2A98F3` | 447 | `Airport_THT` | `025` frag / `075` none |
| 13 | `0x2A9C4C` | 482 | `Air-H-Mac119-G` | `010` frag / `010` teargas / `080` none |
| 18 | `0x2AA4C2` | 505 | `OldCity_THT` | `020` frag / `080` none |
| 28 | `0x2AB53B` | 471 | `Island_THT` | `020` frag / `080` none |
| 31 | `0x2ABA4F` | 425 | `Island-H-M60-Mc` | `100` **frag** (not molotov) |
| 44 | `0x2ACFD3` | 538 | `Parade_THT` | `020` frag / `080` none |
| 51 | `0x2ADBAF` | 450 | `Penthouse_THT` | `020` frag / `080` none |
| 54 | `0x2AE0AE` | 407 | `Penthouse-N-M1` | `100` none |
| 56 | `0x2AE3E6` | 501 | `Shipyard_THT` | `020` frag / `080` none |
| 57 | `0x2AE5DB` | 443 | `Ship-H-MP5A4` | `025` frag / `075` none |
| 68 | `0x2AF7DC` | 551 | `Garage_THT` | `015` frag / `085` none |
| 77 | `0x2B070C` | 547 | `Import_THT` | `020` frag / `080` none |
| 82 | `0x2B0FB5` | 444 | `Import-H-Mac-G` | `030` frag / `070` none |
| 86 | `0x2B163F` | 480 | `Meat_THT` | `020` frag / `080` none |
| 87 | `0x2B181F` | 415 | `Meat-H-G3A3` | `100` none |
| 109 | `0x2B3C55` | 402 | `Mission00-01` | `100` none |

---

## 8. Open items / explicit guesses

1. **How the loader maps a template *name* to a body in the blob is not established.** No
   name→offset table exists in the decompressed package. Until that is found, every blob edit
   must be byte-length-preserving.
2. **Route B (space padding) is untested.** One prior negative result exists with unknown
   placement.
3. **`Template\Normal.tpt` (556 bytes) has no body in COMMON**, yet spawn points in
   ALCATRAZ_A, GARAGE_B, PARADE_B and TRIESTE_A name `Normal`. Either those points fail to
   resolve, or `spawns.py` is matching a different string field there. Unresolved.
4. **Two more templates (one 431-byte, one 428-byte) are also missing from the blob.** Most
   likely `Air-H-M249-G` (428) plus an `Air-*` 431, since the Airport group holds only 6 of
   its 8 manifest entries — but the group-boundary inference and the global multiset
   difference disagree by one entry, so the exact pair is a guess.
5. **Audio for a molotov on a non-Alcatraz map is unverified** (see §4.2 note).
6. Template *names* are stale relative to their bodies in several cases. Any tool that
   surfaces template names to a user should show the body's real weapon/gadget alongside.

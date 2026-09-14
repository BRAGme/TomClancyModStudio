# Ghost Recon PS2 / Ghost Recon Jungle Storm PS2 — file formats

Reverse-engineered from the retail data, September 2026. Everything in this
document was verified against real bytes from at least one of:

| game | disc | archives |
|---|---|---|
| Ghost Recon | SLUS-20613 | `gr.img` (1,550,563,328 B), `menu.img` (58,300,882 B) |
| Ghost Recon Jungle Storm | SLUS-20820 | `gr.img` (1,104,291,830 B) |

Both are Red Storm Engine, same family as Ghost Recon PC, Sum of All Fears and
Rainbow Six 3 PS2.

Tools in this folder:

| file | what it does |
|---|---|
| `grimg.py` | the `.img` archive (loose file or straight out of an ISO) |
| `rselzo.py` | the chunked-LZO compression layer |
| `rsescript.py` | the A..P script encoding and the script variable table |
| `rsb.py` | `.RSB` textures to PNG |

---

## 1. The `.img` archive

Identical in layout to Rainbow Six 3 PS2's `vokes*.img`. All fields are
little-endian.

### 1.1 Header, 64 bytes at offset 0

| off | type | value / meaning |
|---|---|---|
| 0x00 | u32 | **total file size.** Matches the real file size exactly on all three archives. Use it as the format's magic-number substitute. |
| 0x04 | u32 | name-table length-ish; not needed |
| 0x08 | u32 | **entry-table offset** — `0x800` on all three |
| 0x0C | u32 | **entry-table end** |
| 0x10 | u32 | **name-table offset** |
| 0x14 | u32 | **data start** |
| 0x18 | u32 | 1 |
| 0x20 | u32 | a secondary table offset, between entry-table end and name-table offset. Not needed to read the archive; purpose unknown. |
| 0x24..0x3F | — | zero |

`recordCount = (entryTableEnd - entryTableOffset) / 48`

Measured: GR `gr.img` 0x800..0x30350 = **4071** records; GR `menu.img`
0x800..0x88D0 = **687**; JS `gr.img` 0x800..0x24F80 = **3112**.

### 1.2 Entry record, 48 bytes, 12 × u32

| off | field | notes |
|---|---|---|
| 0x00 | `nameOffset` | byte offset into the name table; NUL-terminated ASCII |
| 0x04 | `next` | **TRAP — see below** |
| 0x08 | `parent` | record index of the containing directory; 0 = root |
| 0x0C | `firstChild` | |
| 0x10 | ? | |
| 0x14 | `isFile` | 1 = file, 0 = directory |
| 0x18 | `size` | |
| 0x1C | `size2` | equal to `size` on every record observed |
| 0x20 | `dataOffset` | absolute byte offset within the archive |
| 0x24..0x2C | ? | |

### 1.3 THE TRAP

**Field +0x04 is not a sibling pointer.** It is the `next` link of *one globally
name-sorted list spanning every record in the archive*. Walking it from record 1
as if it were a per-directory sibling chain silently drops most of the archive.

Always enumerate the record array `0 .. recordCount-1` and rebuild each path by
climbing the `parent` chain.

Verification that this is right: enumerating the array accounts for
**99.5 %** of GR `gr.img`, **99.6 %** of GR `menu.img` and **100.0 %** of JS
`gr.img` by bytes, with **zero** records whose `dataOffset + size` falls outside
the file and zero records with an empty path.

### 1.4 Both games' archives are flat

Every record except record 0 is a file; there is exactly **1 directory** (the
root) in each of the three archives. Paths are therefore always `/NAME.EXT`.
(Rainbow Six 3's discs *do* use subdirectories, so a shared reader must still
handle the parent chain.)

### 1.5 Inside a retail ISO

Both ISOs are plain ISO9660. The `.IMG` files sit at their directory record's
LBA × 2048.

Unlike the Rainbow Six 3 disc — where the directory record lies and claims
`VOKES0.IMG` is 1 byte — **on both Ghost Recon discs the ISO9660 directory
record size agrees exactly with the image's own header field [0]**. Verified on
`GR.IMG`, `MENU.IMG` and JS `GR.IMG`.

### 1.6 GR's `menu.img` is a strict subset of `gr.img`

All **686** files in `menu.img` also exist in `gr.img`. 677 are byte-identical.
A mod tool must patch **every copy** of a logical file.

The 9 that differ are genuinely different revisions:

| path | in `gr.img` | in `menu.img` |
|---|---:|---:|
| `/DE_SPECIAL_FEATURE.XML` | 55308 | 55340 |
| `/EN_SPECIAL_FEATURE.XML` | 49710 | 49700 |
| `/EN_STRINGS.RES` | 47619 | 47570 |
| `/ES_SPECIAL_FEATURE.XML` | 54283 | 54323 |
| `/EXPORT_PREPARE.CONFIG` | 889 | 900 |
| `/FR_SPECIAL_FEATURE.XML` | 53196 | 53241 |
| `/IT_SPECIAL_FEATURE.XML` | 51886 | 51902 |
| `/M12_DOCKS.MIS` | 19138 | 19156 |
| `/M15_RED_SQUARE.MIS` | 18696 | 18539 |

Two shipping missions exist in two different builds on the same disc. Nobody has
looked at what differs between them; that is an open lead.

There are **no** files in `menu.img` that are absent from `gr.img`.

### 1.7 A file cannot grow in place

Data blocks are packed back to back at **16-byte alignment** with almost no
padding:

| archive | files | min gap | median gap | total slack |
|---|---:|---:|---:|---:|
| GR `gr.img` | 4070 | 0 | **7 B** | 6,769,708 B (0.44 %) |
| GR `menu.img` | 686 | 0 | **8 B** | 110,613 B (0.19 %) |
| JS `gr.img` | 3111 | 0 | **7 B** | 105,609 B (0.01 %) |

Offset alignment histogram for GR `gr.img`: 2886 files at 16-byte alignment,
763 at 64, 226 at 256, 195 at 2048.

So the practical rule for an in-place patcher is the same as Rainbow Six 3's:
**a replacement file must be smaller than or equal to the original.** Write the
new bytes at the existing `dataOffset`, zero-fill the slack, and rewrite both
`size` (+0x18) and `size2` (+0x1C) in the record. Anything larger needs a full
archive rebuild.

Nearly all of GR `gr.img`'s 6.7 MB of "slack" is a single 6,291,456-byte
(exactly 6 MiB) gap; every other gap in every archive is tiny. That one block is
unexplained.

---

## 2. The compression layer (`rselzo.py`)

Most data files in these archives are compressed. There is **no magic number**.

### 2.1 Chunk framing

```
repeat until EOF:
    u32  compressedSize     (little-endian)
    u32  rawSize            (little-endian, always <= 0x4000)
    u8   blob[compressedSize]
```

* `rawSize` is `0x4000` (16384) for every chunk except the last.
* **`compressedSize == rawSize` means the chunk is STORED, not compressed** —
  copy the bytes verbatim. Feeding a stored chunk to the LZO decoder produces a
  bad back-reference within the first ~50 bytes; that is the tell.
* Note the field order is **(compressed, raw)** — the *opposite* of the
  `(raw, compressed)` order used by Rainbow Six 3 PS2's `.LIN` packages.

Sniff test, since there is no magic: walk the chain and require it to land
*exactly* on EOF with every `rawSize <= 0x4000`. Files that ship as plain text
start with `<` and fail the walk immediately.

### 2.2 Payload = stock LZO1X

Each non-stored blob is an ordinary **LZO1X** stream — precisely what the
reference `lzo1x_decompress` eats. Nothing about the bitstream is
Red-Storm-specific; only the framing above is. `rselzo.py` contains a faithful
pure-Python port of the reference control flow.

Identification walk-through, chunk 0 of `AVATAR.TOE`:

```
2F           0x2F > 17 -> "first literal run" of 0x2F - 17 = 30 bytes:
             "<TOEFile>\r\n\t<VersionNumber>2.0"
82 00        t = 0x82 >= 64  ->  copy (t>>5)+1 = 5 bytes from
             dist = 1 + ((t>>2)&7) + (0x00<<3) = 1            -> "00000"
             then ip[-2] & 3 = 2 trailing literals            -> "</"
2C 5C 00     t = 0x2C in [32,64) -> copy (t&31)+2 = 14 from
             dist = 1 + (0x005C >> 2) = 24                    -> "VersionNumber>"
```

Two details of the reference decoder that are easy to get wrong and which
*will* corrupt output if missed:

* after a match, the trailing-literal count is `ip[-2] & 3` — the byte two
  before the current pointer — **not** the token byte;
* the M1 case reached from `first_literal_run` uses a fixed `0x800` distance
  base and copies **3** bytes, unlike the M1 case reached from `match`, which
  copies 2.

### 2.3 Verification

`grimg.py --sweep` runs the whole pipeline over every file in an archive:

| game | files | LZO-decoded clean | already plain | failures |
|---|---:|---:|---:|---:|
| Ghost Recon (`gr.img` + `menu.img`) | 4756 | 1664 | 3092 | **0** |
| Jungle Storm (`gr.img`) | 3111 | 1197 | 1914 | **0** |

Every chunk's decoded length also matches its header's `rawSize` exactly; that
check is in `rselzo.decompress` and is not disabled.

---

## 3. Extension census

Both archives are flat, so this is the whole content inventory.

### Ghost Recon — `gr.img` + `menu.img`, 4756 files

```
.ATR 1460   .RSB  660   .BMZ 340   .CHA 321   .KIT 250   .QOB 148
.POB  141   .CHZ  140   .GUN  98   .MIS  92   .SB   89   .SH   89
.SS    86   .QOZ   79   .DIR  71   .PSS  66   .POZ  57   .ENV  39
.MAZ   38   .XML   37   .AOL  36   .MOL  36   .POL  36   .SHT  36
.IDC   36   .PAK   35   .VCL  34   .GTF  22   .TOE  20   .BMB  19
.BMH   19   .TXT   18   .PRJ  18   .RES  15   .ITM  14   .KIL  12
.ANM    7   .THC    3   .ICO   3   .SCN   3   .CSF_BIN 3  .AUD  3
(+ .LST .SAV .CSF .PSF .PSF_BIN .MPG .TM .M2V .CONFIG .MAB .MAH
   .KEYS .BUT .ASS .RPF .BAT .LOG .SDF at 1-2 each)
```

### Jungle Storm — `gr.img`, 3111 files

```
.ATR  766   .BMZ 299   .RSB 199   .KIT 191   .POB 183   .QOB 177
.SB   101   .SH  101   .QOZ 101   .SS  101   .CHA  66   .GUN  66
.XBG   66   .CHZ  65   .POZ  62   .MIS  45   .PSS  42   .PAK  40
.DIR   37   .ENV  37   .IDC  35   .AOL  32   .MAZ  32   .MOL  32
.POL   32   .SHT  32   .TOE  20   .GTF  14   .XML  11   .PRJ  10
.XBS    9   .RES   8   .TXT   8   .ANM   7   .VCL   7   .ITM   7
.LNG    6   .CTX   6   .GCD   6   .WRD   6   .WAV   5   .THC   4
(+ ~20 singletons)
```

Note the GR `.MIS` count of 92 is 46 missions × 2 archives.

### What each extension is

| ext | verified as |
|---|---|
| `.MIS` | **mission** — plain XML. Order of battle, AI plans, objectives, briefing, script. |
| `.GTF` | **game type** — plain XML + two script blobs. |
| `.ATR` | **actor template** — plain XML. Model + 5 skill integers. |
| `.KIT` `.KIL` `.GUN` `.PRJ` `.ITM` `.VCL` `.ENV` | plain XML: loadout, kit restriction, weapon, projectile, hand-held item, vehicle, environment. |
| `.TOE` | **table of equipment** — the *player's* order of battle, same Company/Platoon/Team/Actor grammar as a mission's `<Units>`. |
| `.XML` | plain XML (`<BestTimes/>`, special-feature text). |
| `.RSB` | texture. See §5. |
| `.BMZ` `.BMB` `.BMH` | bitmap banks. See §5. |
| `.DIR` `.LST` `.TXT` `.SDF` `.CONFIG` `.BAT` `.LOG` | plain text (file manifests, voice lists, script notes). |
| `.RES` `.CTX` `.WRD` `.GCD` `.LNG` | localisation string tables (binary, not decoded here). |
| `.CHA` `.CHZ` `.CHR` | character models. |
| `.QOB` `.QOZ` `.POB` `.POZ` `.MOL` `.SOB` | geometry. RSE templates for these exist in AlexKimov/RSE-file-formats. |
| `.MAZ` `.SHT` `.AOL` `.POL` `.IDC` `.PAK` | level data (map, shadow, object lists). Not decoded here. |
| `.SS` `.SB` `.SH` `.PSS` `.AUD` `.WAV` | audio / FMV. `.PSS` begins `00 00 01 BA`, an MPEG-2 program-stream pack header — it is Sony's standard PS2 MPEG-PS container. |

**The `Z`-suffixed geometry is *not* a compressed copy of the `B`-suffixed
file.** That is the obvious guess and it is wrong: after decompressing both,
`/203_ROUND.QOZ` is 792 bytes while `/203_ROUND.QOB` is 2385,
`/CIG.QOZ` is 344 vs `/CIG.QOB` 1042, and so on — checked on four pairs, none
equal. They are separate, much smaller meshes, most plausibly a reduced LOD
(that is a **guess**; the geometry format was not decoded).
| `.XBG` `.XBS` | Jungle Storm only; small binary, not decoded. |

---

## 4. Mission / game-type XML, and the script encoding

The gameplay content is covered in detail in `enemy_knobs_gr.md` and
`enemy_knobs_js.md`. Format facts only, here:

### 4.1 `.MIS` skeleton

```
<MissionFile>
  <VersionNumber>2.000000</VersionNumber>
  <Shell>      ... map name, which game modes it supports, unlock flags
  <Engine>
    <Wind> <LocationText> <DateText> <TimeText> <BriefingText>
    <WeatherIndex> <Class0..Class5>            see note below
    <Units>          ... Company > Platoon > Team > Actor  (the order of battle)
    <ZoneList> <PlanList> <WaypointList> <SoundList> <RoomList>
    <StationList> <DependencyList>
    <ScriptCompiled>  ... A..P encoded
    <Objectives>
  </Engine>
  <Editor><ScriptSource>  ... A..P encoded, the editor-side copy
</MissionFile>
```

**These files are well-formed XML and a strict parser handles almost all of
them.** Measured by feeding every decompressed text data file to Python's
`xml.etree.ElementTree`:

| ext | GR ok / fail | JS ok / fail |
|---|---|---|
| `.MIS` | 46 / 0 | 45 / 0 |
| `.GTF` | 11 / 0 | 14 / 0 |
| `.TOE` | 20 / 0 | 20 / 0 |
| `.ATR` | 1191 / **2** | 766 / 0 |
| `.KIT` | 91 / **50** | 191 / 0 |
| `.ENV` `.GUN` `.PRJ` `.ITM` `.KIL` `.VCL` | all ok | all ok |
| `.XML` | 15 / **5** | 6 / **5** |

The failures are **shipping bugs in the retail data**, not a format quirk. The
50 bad Ghost Recon `.KIT` files all carry a mismatched closing tag:

```xml
<KitTexture>kit_galinsky-01.rsb</VersionNumber>
```

`/PILOT_1VER.ATR` has the same class of defect, and the five
`*_SPECIAL_FEATURE.XML` files contain raw un-escaped characters. The engine's
own parser is evidently lenient about close-tag names.

Two consequences for a mod tool:

* use a lenient/recovering parser, or special-case these files;
* on write-back, **preserve the malformed close tags** rather than "fixing"
  them — the shipping game works with them as they are, and normalising the
  text changes the byte length.

One more surface detail: attributes are written with spaces around the `=`
(`IgorId = "9"`), so byte-level search-and-replace must allow for that.

`<Class0>`..`<Class5>` are six small integers in `<Engine>` (e.g. M02_FARM has
1/1/3/1/-/2). They are **almost certainly** how many soldiers of each class the
player may field, since `.ATR` `<ClassName>` takes exactly four values
(`rifleman`, `demolitions`, `support`, `sniper`) and the shell UI offers a squad
builder — but that mapping was **not verified** and the index-to-class order is
unknown. Treat it as a guess.

"Igor" is the name of Red Storm's in-house level editor; `IgorId` is the
editor's object id and `ScriptId` is the id the compiled script refers to.

### 4.2 The A..P script encoding — NOT base64

`<ScriptCompiled>` and `<ScriptSource>` look like base64 at a glance. They are
not. Each payload byte is written as **two ASCII characters in `A`..`P`, low
nibble first**:

```
byte = (c0 - 'A') | ((c1 - 'A') << 4)
```

So `PDEFIGFGACAFJGMGPGEHACEEJGFGEG` decodes to `?The Pilot Died`.

The encoding is fixed-width, so an edit that preserves the payload byte length
preserves the XML text length, and therefore the archive slot size.

### 4.3 The script variable table

The decoded payload opens with the script's variable table:

```
u32 variableCount
u32 1
u32 2
repeat variableCount times:
    u32   nameLen
    char  name[nameLen]        (no NUL terminator)
    u32   value
    u32   id
    u32   0
```

`value` is a **union**: read it as an int for counts, and as IEEE-754 float
*bits* for durations and ranges. Rule of thumb: anything above ~1e8 is a float
bit pattern. e.g. `1133903872` = `0x43960000` = `300.0f` for
`"Proximity start time"`, while `"Recruit enemy count"` is a plain `30`.

`id` is a script node reference and is **not** unique — two variables in
Jungle Storm's `DEFEND.GTF` both carry id 3.

Worked example, JS `(SP) DEFEND.GTF`:

```
0D 00 00 00   13 variables
01 00 00 00
02 00 00 00
09 00 00 00 "Lose Text"             value 8    id 2
13 00 00 00 "Recruit enemy count"   value 20   id 3
13 00 00 00 "Veteran enemy count"   value 25   id 4
11 00 00 00 "Elite enemy count"     value 35   id 7
15 00 00 00 "Proximity shrink rate" value 10   id 8
0C 00 00 00 "Capture time"          value 11   id 9
```

`(COOP) DEFEND.GTF` is the same file with 30 / 40 / 50.

### 4.4 What is NOT decoded: the node graph

Past the variable table the payload is a compiled node graph that has **not**
been decoded. What *is* available from it:

* every designer node name and comment, by harvesting printable runs
  (`rsescript.comments()`). This is how the spawn/wave logic in both games was
  located — e.g. `01a: Spawn enemies (recruit)`, `Camp Wave 2 Timer`,
  `When Reinforcements 2 dies, send in Reinforcements 3`.
* the variable table, readable and rewritable.

What is *not* available: node wiring, and any constant typed directly into a
node rather than into a named variable. Mission scripts are the casualty —
**all 46** GR missions and **44 of 45** JS missions carry a variable table with
zero entries, so mission wave timings are all baked into node constants.

Next probe for anyone continuing: JS `(SP) DEFEND.GTF` (2390 payload bytes) and
`(COOP) DEFEND.GTF` (2381) are a near-perfect structural pair — same variable
names, differing only in three numbers. Diffing those two decoded payloads is
the cleanest available alignment target for mapping node records.

---

## 5. Textures

*(filled in below)*

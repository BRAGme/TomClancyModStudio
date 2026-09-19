# Formats, and how each fact was settled

Everything below was read out of the retail installations on this machine. Where
a claim was settled by decoding rather than by reasoning, the experiment is
given, because that is the part worth keeping.

The raw per-game dossiers this was distilled from are in `research/`.

---

## 1. Red Storm `.RSB` bitmaps (Ghost Recon, Sum of All Fears, Lockdown)

Four versions across the three games, in two header layouts.

```
v4 / v5 / v6      u32 version, u32 width, u32 height,
                  u32 redBits, u32 greenBits, u32 blueBits, u32 alphaBits
                  pixels at 28

v8 / v9 / v10     u32 version, u32 width, u32 height, u32 ?
                  four u32 slots whose LAST byte is the channel depth
                  (so depths are at 0x13, 0x17, 0x1B, 0x1F)
                  pixels at 35  (v8)
                  pixels at 43  (v9, v10)
```

### The pixel offset differs between v8 and v9, and getting it wrong is invisible

v9 and v10 insert eight more header bytes than v8 does. Reading a v9 at offset
35 *works*: it decodes, and it looks fine, because eight bytes is two pixels of
a 32-bit raster or one block of a DXT1 one — the image just slides a few pixels
sideways with a couple of stray white pixels in the corner.

It was settled from the bytes. In `r6lockdown.rsb`, from offset 43 onwards the
data falls into clean four-byte groups `00 0b 0b 0b`, `00 0c 0c 0c` —
transparent near-black, an image's border. From 35 it does not; bytes 35–42 are
`ff ff ff ff ff ff ff ff`. Across the three games, 19 of 39 v9 files and all 25
v10 files have eight `0xFF` there, and `background00.rsb` has
`ff ff ff ff 00 00 00 00`, which is what proves it is a header field carrying
data rather than pixels.

### The declared bit depth does not always describe the storage

`background01.rsb` declares 8/8/8/8 for a 1024×1024 page. That would be four
megabytes; the file is half a megabyte. Half a byte per pixel is DXT1.

So the decoder does not trust the header. It tries the declared depth, then
DXT5, then DXT1, and takes the first whose pixel data fits inside the file with
a small trailer left over. That also removes any need for a table of trailer
sizes — the measured ones are 61 and 65 (Ghost Recon), 66 (Sum of All Fears),
74 and 122 (Lockdown), and they are simply ignored.

### Channel order: 24-bit is RGB, 32-bit is ARGB

Both were settled by looking, not by reasoning, and they are **not** the same
as the PS2 and Xbox builds of the same games, which store blue first.

* **24-bit is RGB.** Read as BGR, Ghost Recon's main menu has cyan faces on
  soldiers in blue-grey woodland camouflage. Read as RGB it is skin, green
  jungle and the right camouflage.
* **32-bit is ARGB** — alpha comes *first*, so it is not the 24-bit order with
  a channel appended. Read as RGBA, Lockdown's logo is cyan and pink on an
  opaque block; read as ARGB it is red and white on transparency with bullet
  holes. Confirmed independently in both header families: Ghost Recon's
  `decorations.rsb` is a sheet of medals, and only ARGB gives them red, blue
  and gold ribbons.

Undecodable after all this: four files in Lockdown (`pcfont_lg`, `pcfont_sm`,
`ps2font_debug`, `merc_pda`) and none in the other two.

### Where each game's menu art is

| | backdrop | wordmark |
|---|---|---|
| Raven Shield | `backgrounds\Main_menu_01.tga` (640×480, 24-bit, uncompressed) | same file, top right — keyed |
| Ghost Recon | `Data\Shell\Art\main_menu-01.rsb` | same file, upper left — contrast-stretched then keyed |
| Sum of All Fears | `Data\Shell\Art\main_menu-01.rsb` | same file, top left — keyed |
| Lockdown | `data\shell\art\background00.rsb` | `data\shell\art\r6lockdown.rsb` — **already cut out** |
| Vegas | `KellerGame\Slide\Locations\03_Fremont_01.dds` | `...\MenusPC\Textures\SinglePlayer\RSVegas_Logo.tga` — **already cut out** |

Two traps worth writing down. `soaf_command_bkgrnd.rsb` sounds like the Sum of
All Fears logo and is a flat cyan command-bar plate with no lettering on it.
And Ghost Recon and Sum of All Fears draw a 640×480 menu into a 1024×512 page
and pad the rest with black — trimming that is not cosmetic, because the
backdrop is scaled to *cover* the window and a page that is 38% empty gets the
real picture blown up and pushed off the side.

Always look for a real cut-out before keying one out of a composited screen.
Lockdown's logo appears in `splash.bmp` composited over a pale gradient, which
needs an inverted key and then a morphological close to fill the white
lettering punched through its black block — and `r6lockdown.rsb` is the same
logo with its own alpha, sitting in the same folder.

---

## 2. Red Storm pseudo-XML (all three Red Storm games)

Two dialects. Ghost Recon and Sum of All Fears put the value in the element
text; Lockdown puts it in an attribute, one per line, with spaces around `=`:

```xml
<ActorFile>                     <GunFile
    <ArmorLevel>2</ArmorLevel>      version = "4">
    <Stealth>3</Stealth>            <Common
</ActorFile>                            name = "WPN_AN-94"
                                        isPrimary = "1">
```

**It is not read by an XML parser at the other end.** Red Storm's loader is
hand-rolled, and the files are not valid XML anyway: `names.nsf` has nine
`name=` attributes on one element, and Lockdown's `.cms` files use numbers as
element names (`<60>…</60>`). Round-tripping through `ElementTree` re-quotes,
re-indents and re-orders everything to satisfy a standard nothing here follows.
So `rsexml.py` holds the document as its original text and replaces exactly the
span of the value being changed.

### A weapon file holds the same block once per attachment

`M8Compact.gun` carries `Default`, `RedDot`, `Scope`, `HiCapMag` and
`Suppressor`, each with its own `<WeaponData>` and `<ReloadData>` — 142 nodes
against the enemy copy's 34. Writing only the first one changes the gun's
damage until the player fits a red dot sight, at which point it silently
reverts. So every edit writes all of them.

And anything proportional scales **each one from its own value**. A rifle's
`clipSize` is 30 on the Default variant and 100 on HiCapMag; "half magazines"
has to mean 15 and 50, not 15 and 15, or the option quietly deletes the
extended magazine.

### Enemies and the player are told apart by location, not by content

* Ghost Recon / Sum of All Fears: enemy actors are loose in `Actor\`; the
  player's squad is in subfolders of it (`rifleman\`, `demolitions\`,
  `heavy-weapons\`, `sniper\`, `hero\`, and `Team Members\` in Sum of All
  Fears).
* Lockdown: the enemy's weapons are `data\equip\e_*.gun` and the player's are
  the other 42 files **in the same folder**.
* Player kits: Ghost Recon `Kits\<class>\`, Sum of All Fears `Kits\team\`,
  while the enemy's are `Equip\*.kit` and `Kits\mercenaries\` respectively.

The obvious-looking discriminator does not work: `<ClassName>` says
`demolitions` on 624 of Ghost Recon's 825 actor files, enemies included, and
Sum of All Fears has no `<ClassName>` at all.

**This is why `engine.expand` does not use `fnmatch`.** `fnmatch`'s `*` crosses
a directory separator, so `Actor/*.atr` — which reads as "the enemy actors" —
would also match `Actor/rifleman/*.atr` and apply "make enemies tougher" to the
player's own riflemen. Here `*` stops at a separator and `**` is the one that
crosses it.

---

## 3. Unreal `.ini` (Raven Shield, Vegas)

`configparser` is the wrong tool three times over:

* **Duplicate keys are meaningful.** Unreal reads a repeated key as an array
  (`Paths=`, `EditPackages=`, and Vegas's four consecutive
  `m_fireModeAvailability=` lines per weapon). `configparser` keeps the last and
  deletes the rest of the list.
* **The formatting is data** — comments, blank-line grouping, key order.
* **Vegas's stale export uses a decimal comma.** `m_fSuppressorDamageModifier=0,8`
  is eight tenths, not a two-element list.

So `inifile.py` is line-oriented: a write replaces the one line it is changing.

### A variable is only read from an ini if it was compiled `config`

This is the fact that makes Raven Shield tractable. Some keys this tool writes
are not in the shipped file at all — they are compiled-in defaults, and adding
the key is the supported way to override one. Every key written here was
confirmed flagged in the packages.

### Struct literals

Raven Shield's entire AI hearing model is five fields under one key:

```
m_Rainbow=(fStandSlow=300.000000,fStandFast=800.000000,fCrouchSlow=200.000000,
           fCrouchFast=400.000000,fProne=400.000000,eType=NOISE_Investigate)
```

so "how far the AI hears you walking" is a field inside a value, not a key.
`inifile.set_field` rewrites one field and leaves the others alone. The
lookbehind in its pattern matters: these names nest (`fStandSlow` contains
`Slow`, as does `fCrouchSlow`).

### `template\*.tpt` has no section header at all

266 files of bare `Assault=80`. Rather than write a second parser that would
have to make all the same decisions about whitespace and line endings again,
`Ini` treats an empty section name as "the keys before the first `[header]`",
which for these files is the whole file.

### Numbers keep the file's own spelling

An integer-spelled stock value is taken as evidence that the engine field is an
integer, so a scaled value is *rounded* — halving a damage of 35 gives 18, not
`17.5`, which is at best truncated. A six-place float stays six places:
`fSndDist=1100.000000` becomes `550.000000`, not `550`. Unreal would read `550`
perfectly well, but a file whose own convention has changed is a file nobody can
diff against the original.

### Vegas: which ini actually wins

Vegas ships three copies of nearly every config file and **two of them are
inert**. The live layer is `KellerGame\Config\PC\Keller<X>.ini`:

* the executable carries `..\KellerGame\Config\PC\` together with `%sKeller%s.ini`;
* only files in that folder have modification times later than the install —
  `KellerGame.ini` and `KellerConsole.ini` are December 2024, `KellerEngine.ini`
  August 2024, against a March 2024 install date on everything else;
* `PC\KellerServerOptions.ini` holds this installation's own runtime state.

The `PCKeller*.ini` at the Config root are snapshots (same values, install-date
mtimes); the root `Default*.ini` are stale templates with *different* values —
`m_iInitialBulletSpread` is 60 there against the live 220. A tool that edited
either would do nothing, very convincingly.

The decimal comma is real but it is in the dead file: the root
`DefaultWeaponsConfig.ini` has 2,243 comma-spelled floats and the live
`PC\KellerWeaponsConfig.ini` has none. `inifile` handles both regardless, which
costs nothing and means the tool cannot be broken by whichever copy it is
pointed at.

Two files have no `Keller` layer above them and are edited where they sit:
`DefaultRainbow.ini` — three lines holding the whole squad formation behaviour
— and anything else the `PC\` folder does not shadow.

The `[Internal] CRC=` line is **not** a tamper check: it is a checksum of the
corresponding `Default<X>.ini`, a *different file*, so it fingerprints template
staleness rather than content. The tool leaves it alone.

---

## 4. Mod folders

### Ghost Recon and Sum of All Fears

`GhostRecon.exe` enumerates `\mods\*.*`, reads each folder's `modscont.txt` and
writes `ModsSet.txt`. A mod is a **sparse overlay** over `Mods\Origmiss\` — it
only needs the files it changes. The `PS2Accuracy` mod already in this Ghost
Recon is the ground truth for the minimum: 51 files, a `ModsCont.txt` and an
`Equip\` folder.

```
// Mods Contents
NAME        "Mod Studio"
AUTHOR      "Tom Clancy PC Mod Studio"
SUPPORT     ""
VERSION     "1.00"
MULTIPLAYER "Server-Client"
```

Verified on the real installation: building the mod wrote 682 files into
`Mods\ModStudio\` and modified **0** of the 5,063 files under `Mods\Origmiss\`,
checked by comparing every modification time before and after.

### Lockdown has one too, and nobody has used it

`lockdown.exe` contains a complete `RSModsMgr`: a `mods/` root, a manifest with
the fields `NAME AUTHOR SUPPORT VERSION MULTIPLAYER ICON CLIENT-SIDE
SERVER-SIDE`, an active-list `ModsSet.txt`, a `-modset` command-line switch and
the full multiplayer mod-negotiation UI in the string table. No `mods\` folder
ships, so the layout a mod folder must have is unproven — which is the only
reason this profile edits `data\` in place instead. If it were proven, it should
switch.

The shipped `readme.txt` says modifying `.itm`, `.gun` or `.prj` files makes
your server report modified data and stops you hosting a ranked game. That is
the only documented consequence, and it is confined to ranked multiplayer.

### Raven Shield

Discovery is a wildcard scan of `..\Mods\`, not a fixed list — the three
uppercase names in `Engine.u` are only the "official badge" comparison set. A
mod is a `Mods\<Keyword>.mod` descriptor **beside** a `Mods\<Keyword>\` folder,
and the override model is explicit redirect (each key names a path or file stem)
rather than a filesystem overlay. This tool does not use it yet; see
`tcpc/games/ravenshield.py` for what that would unlock.

---

## 5. What is mapped but not implemented

* **Raven Shield's cut game modes.** `R6DefendGame`, `R6DefendCoopGame`,
  `R6ReconGame` and `R6ReconCoopGame` are fully compiled and no shipped `.mod`
  lists their mode names. Re-enabling them is a text edit to a generated `.mod`.
* **Ghost Recon enemy accuracy, separated from the player's.** Both sides read
  the same `Equip\*.gun`. The technique for splitting them is the one
  `PS2Accuracy` uses: add `<weapon>_npc.gun` with different numbers, then shadow
  the `Equip\*.kit` enemy kits to point at them.
* **Vegas difficulty.** Not in ini at all. Player health, teammate health,
  accuracy multipliers and the AI vision-and-lock timers live in 22 cooked UE3
  packages under `Content\CookedPc\Packages\GameConfig\`. Normal and Veteran
  share the same player health; only Elite really differs.
* **Vegas's cut terrorist-hunt maps.** Seven hunt map ids are missing and their
  thumbnails are still on disk, matching story levels that do ship. Wiring them
  up is pure ini editing.

---

## 6. GRIN Diesel `.bundle` archives (Advanced Warfighter 1 and 2)

Both GRAW games keep essentially everything in `Bundles\quick.bundle` and
`Bundles\patch.bundle`: 3.8 GB and 3.7 GB, 21,356 and 25,052 files. Format,
little-endian, and this is the whole of it:

```
0x00  "BNDL"
0x04  u32  version            2 in both games
0x08  u64  index_end          the index runs from 0x10 to here

records until index_end:
  0x01  push directory   u8 marker (always 1), NUL-terminated name
  0x02  file             u64 offset, u32 size,
                         u8 marker (always 1), NUL-terminated name
  0x03  pop directory
  0x00  end of index
```

File data is stored **uncompressed**, contiguously and in index order: each
entry's offset is the previous one's offset plus its size, which is what
confirmed the field widths. The grammar was settled by parsing rather than
guessed — all four indexes consume to exactly `index_end` with nothing left
over, and not one of the 47,674 entries points past the end of its file.

**`patch.bundle` wins over `quick.bundle`.** 695 paths in GRAW 1 and 571 in
GRAW 2 appear in both, and reading the wrong one silently gives the pre-patch
values: `data/anims/anims.xmb` is 481,239 bytes in the patch and 464,542 in the
original.

### Why nothing here writes a bundle

Diesel looks a file up **on disk before it looks in the archive**, so a change
is delivered as a loose file and the archives are never opened for writing.

That is not a guess about how it ought to work. This Advanced Warfighter
installation has 764 files under `Data\textures\...` dated 2023 — ten times the
size of the archived versions of the same paths — which are somebody's
high-resolution replacements, working by exactly this mechanism. The 326 loose
files dated 2006 are what shipped.

A bundle path is written where the archive says it belongs, because **the
bundle's root is the install root**: the archives hold `context.xml` and
`settings\...` next to `data\...`, and those are the same `context.xml` and
`Settings\` folder that sit loose beside the executable. The one special case
is the leading `data`, which maps to the install's real `Data\` folder.

### The data is plain XML, addressed by name

A weapon does not have elements named for its fields. It has a flat list:

```xml
<stats block="weapon_data">
    <var name="clip_max"      value="30"/>
    <var name="spread_normal" value="1.87"/>   <!-- + mods affect this -->
    <var name="fire_modes"    value="2"/>      <!-- 1=semi 2=+auto 3=+burst -->
</stats>
```

which is why `rsexml` grew a predicate on the last path segment:
`var[name=spread_normal]` selects the element whose `name` says so. A weapon
file usually defines several units — the rifle, its grenade-launcher variant,
the husk left when it is dropped — so a name repeats within a file, and an edit
writes all of them, scaling each from its own value.


### Is the plain `.xml` live, or is the compiled form the authority?

**The compiled form wins, and getting this backwards makes every option a
no-op.** Both games ship each data file twice — `.xml` plus `.xml.bin` (GRAW 1)
or `.xmb` (GRAW 2) — and 100% of the `.xml` in both bundles has a twin: 5,672
of 5,674 and 7,984 of 7,985.

The decisive evidence is inside the game. `quick.bundle` accidentally ships
`temp_merged_log.xml`, a recorded GRIN engine session with **9,508
`<open path="...">` records**. Where both forms of a file exist, it opened:

| | count |
|---|---|
| the compiled `.xml.bin` | **3,029** |
| the plain `.xml` | **2** |

(The two are `tunnel_wave.xml` and `tunnel_sound.xml`, which have no twin.)
Disassembly agrees: the loader builds `<base>.bin`, probes both, and compares
file times with `CompareFileTime` — ties go to the compiled file.

So this tool writes **both** forms. `tcpc/xmlbin.py` is a reader and writer for
the compiled format, verified by re-encoding every compiled file in both games:
5,674 of 5,674 and 7,984 of 7,985 come back byte-identical, the one exception
being `hud_palett.xmb`, which is not a compiled XML at all.

The compiled format, little-endian:

```
"XML"
u32   string count, then that many NUL-terminated strings
node                                       (the root)
u32   include count, then that many NUL-terminated paths

node:
  1  element  u32 name, u32 attr count, (u32 key, u32 value) pairs,
              u32 child count, that many nodes -- all indices into the table
  2  text     u32 index
  4  macro    an xdefine: inline NUL-terminated name, u32 param count and
              names, u32 count and that many u32s, inline body, ONE pad byte
```

Edits are applied to the parsed tree rather than by recompiling the edited
source, because the tree is what round-trips exactly. Regenerating would mean
writing an XML-to-compiled compiler and hoping it agreed with GRIN's about
string-table order; this only has to agree with itself.

**A mod bundle is the other way round**, which is worth stating because both
facts are true and they sound contradictory. GRIN's own
`public_toolsundlerundle.bat` runs `compile-scripts` and `quick-bundle`
and never `compile-xml`, so a mod bundle built the documented way contains
plain `.xml` with no twins — and there the source is what loads. The rule is
not "source or compiled", it is "the twin if there is one".

### The palettes are authored text, not something to sample

Both games state their interface colours with the roles named, which is worth
knowing because sampling the backdrop measures the wrong thing entirely: an
Advanced Warfighter menu is a 3D scene, and averaging it gives the colour of a
Mexican street at dusk.

* GRAW 1 — `data/gui/interface_items.xml` in the bundle, an `xdefine` block the
  whole GUI references as `@base_color` and friends: base `#1D8997` at alpha
  150, darker base `#006C7A`, frame `#17C5C0`, selected `#40B0BF`, hover
  `#329CAB`, and a hot orange highlight `#FF6C00` that is easy to miss in a
  family this teal.
* GRAW 2 — `Settings\hud_palett_2.xml`, loose on disk and commented in English:
  `#001717` ground, `#023D40` and `#047E80` panels, `#06C2C5` rules, `#96F7F8`
  text, amber `#E6AB40` accent. The same file carries a complete second scheme
  in brown that nothing selects, and its own header explains that switching
  means copying one block over the other — which is what this tool's "HUD
  colour scheme" option does.

**GRAW 2's wordmark is THREE tint masks, not a picture.** `sp_logo_h.dds` opens as neon
primaries, and the file is fine — you are looking at masks. Its red, green and
blue channels are three separate coverage masks and its alpha is the outline;
`data/objects/gui/hud_new/materials.xml` names the material `GRAW_logo` and
binds `red_color`/`green_color`/`blue_color` to the palette entries X1, X2 and
X3, which `Settings\hud_palett_2.xml` labels "logo dark", "logo mid" and "logo
bright". Painting each mask in its colour and adding them gives the real
white-and-teal wordmark. Every plain channel order was tried first and none of
them produces anything but neon.

GRAW 1's `logos_diffuse/h_1600x1200.dds` is an ordinary RGBA cut-out and needs
none of this. GRAW 2's bundle still carries GRAW 1's entire logo family as dead
leftovers, so picking by filename alone gets you the wrong game's wordmark.

### Enemy counts are encoded in a NAME, not a number

A world file does not place soldiers. It places squads:

```xml
<unit name="group_unit" group="mex_guerilla_patrol2" group_id="patrol01">
  <order order="Sniper" .../>
  <position pos_x="-14707.789" pos_y="22192.504" pos_z="850"/>
</unit>
```

and the trailing digit is the squad's size. A group declared `split="true"` is
expanded by the group manager into sub-groups `<name>1` … `<name>N`, where N is
its full roster and `<name>K` is that roster cut to K.

So "more enemies" is not a value to scale — it is a **rename**, to a different
string per placement, and only the names the generator makes exist. That is
what `XmlAttr.remap` was added for: a per-element map from old value to new,
which leaves alone any element whose value is not a key.

Checked before being trusted, across all 44 GRAW 1 world files:

| | |
|---|---|
| distinct group references | 86 |
| …suffixed | 58 |
| …bare (and every one is a declared group) | 28 |
| references whose base group is undefined | **0** |
| references asking for a K larger than the base roster | **0** |

So raising K to the roster stays strictly inside the range the shipped game
already uses. **No shipped world references a `split` group bare**, which is
why the tool raises the suffix instead of stripping it — stripping would have
relied on a form the game never demonstrates.

The roster table comes from each game's own **compiled** `group_manager`, not
its source: GRAW 2 generates most of its groups from `xdefine` macros, and only
the compiled copy has them expanded. Source versus compiled for GRAW 2:
9 literal `skill_shooting` values against **132** once expanded.

Measured effect, mission 1: 45 → 83 enemies in GRAW 1, 46 → 212 in GRAW 2. The
difference is that GRAW 2's patrol squads hold eight men where GRAW 1's hold
four. Across GRAW 1's whole campaign, 1,053 → 2,600.

Friendly squads are named `friendly*`, `us_marines_*` and `loyalists*`, are not
in the table, and so cannot be caught by the rename — asserted by a test.

### Enemy skill, and why a blanket scale is safe there but not for health

`skill_shooting` sits on the soldier templates. Every one of the 34 in GRAW 1
and 132 in GRAW 2 belongs to a `mex_*` or `ag_*` soldier — established by
walking the tree and reading each node's owning `<soldier>` rather than by
trusting the file's layout — so scaling all of them cannot reach the player's
squad. `overall_enemy_precision` in `sb_global` is the global multiplier on
top, and it lives in a `default` attribute rather than a `value` one.

`damage_points` is different. GRAW 1 keeps living enemies at 4, two special
NPCs at 8, and the **husks** — the bodies left behind — at 16, all in the same
files. A blanket scale would make corpses harder to shoot apart, so health is a
remap of the living values only.

### There are no enemy waves

Worth stating because it is the obvious next thing to look for. Enemies are
**placed, then activated** — never created. Across both campaigns the mission
scripts call `ActivateGroup` and `RemoveGroup`; `CreateUnit` exists and spawns
props, weapons and vehicles, never soldiers. The only trace of a wave anywhere
is a dead default in `sb_group_unit.xml`: `var[group_name]/@default="wave_a"`.

### One bug this found in the ini editor

Advanced Warfighter 2 ships `Support\Detection\interpreter_local.ini` as
**UTF-16 LE**. `cp1252` decodes it perfectly happily — every byte maps to some
character — and the result is a string full of NULs whose lone carriage returns
the line-ending normaliser then rewrote as line feeds, corrupting the file on
save. The round-trip check caught it. `inifile` now recognises every byte-order
mark before the 8-bit fallback gets a look, and keeps each line's own
terminator beside it rather than normalising and rejoining. That also makes it
safe on a classic-Mac file, which nothing here ships but which cost nothing to
get right once the structure was there.

---

## 7. Unreal Engine 2 packages (Raven Shield `system\*.u`)

Raven Shield's weapon and ammunition statistics are not configuration. They are
compiled UnrealScript class defaults, and reaching them is the only binary
writing this tool does. The packages are **version 118 / licensee 14**,
uncompressed, with valid name, import and export tables and no checksum over
the bytes being changed — the summary carries a GUID and the table counts, and
neither depends on a property's value.

### The rule that shapes everything

**Values can be rewritten. Properties cannot be added.** Unreal serialises a
property only where its value differs from its class default, so a class that
ships the default has nothing to overwrite, and inserting a tag would move every
byte after it and invalidate the export table. Every edit is therefore
equal-width — four bytes for an int or a float, one bit inside an existing tag
byte for a bool — and the engine refuses an edit that changes the file length.

In practice this costs nothing for the options that exist: all **139 weapons the
loadout menu offers** resolve a value for every property used, through their own
defaults or an ancestor's. The 57 classes that do not are abstract bases like
`AssaultAK47`, which the menu never offers and whose `Normal`/`CMag`/`Silenced`
children inherit from, so an edit to the parent reaches them anyway.

### Finding a property: why searching for one is unsafe

A property is serialised as `compactIndex(nameIndex) infoByte [size] value`, so
a name index plus an info byte looks like a findable signature. **This was the
first implementation and it was wrong.** A name index is often a single byte,
and one byte followed by a plausible info byte occurs by accident inside the
*value* of an earlier property.

The concrete case: searching `NormalLMGRPD` for `fRunningAccuracy` (name index
16, so the needle is the single byte `0x10`) finds a hit at `0x00e95d`, 53 bytes
before the real one at `0x00e992`. The bytes there are the middle of
`m_fMuzzleVelocity`'s float — `0b 24 | 00 10 24 47`, which is name 11, type
float, value 41999.06. Nothing about the hit looks wrong locally, and a write to
it would have silently corrupted the muzzle velocity of one weapon.

That search agreed with the independently produced `research/rs3_weapons.csv` on
1,808 of 1,809 offsets. One disagreement in eighteen hundred was the only sign
anything was wrong, which is the argument for chasing it rather than tolerating
it.

### So the list is parsed from its start

Which means finding the start, which means walking the whole class header:

```
UField   SuperField(ci)  Next(ci)
UStruct  ScriptText(ci)  Children(ci)  FriendlyName(ci)
         Line(u32)  TextPos(u32)  ScriptSize(u32)  script[...]
UState   ProbeMask(u64)  IgnoreMask(u64)  LabelTableOffset(u16)  StateFlags(u32)
UClass   ClassFlags(u32)  ClassGuid(16)
         Dependencies    count(ci) x { Class(ci)  Deep(u32)  ScriptTextCRC(u32) }
         PackageImports  count(ci) x ci
         ClassWithin(ci)  ClassConfigName(ci)
         HideCategories  count(ci) x ci
         Defaults        tagged property list, terminated by the name "None"
```

`UClass` extending **`UState`** is the part worth writing down. Between the
script and the class flags sit 22 bytes belonging to the state machine, and
reading `ClassFlags` too early lands on the low half of `ProbeMask` — which
reads as a believable `0x0202` flags word and puts everything after it 22 bytes
out. That mistake produces a header parse that looks plausible and is useless.

The parse is checked rather than trusted: the walk must consume the class's
serial range **exactly**, ending on `None` at its final byte. 535 of Raven
Shield's 541 weapon, first-person and description classes do.

### The six classes that are refused

`ScriptSize` is the length the bytecode occupies **in memory**, not on disk, so
a class that still carries compiled script cannot be skipped past by
arithmetic. Six classes in `R6Weapons.u` are in that position — `R6Weapons`
itself plus five gadget classes. None is a weapon or an ammunition type. They
are refused rather than guessed at: a property that cannot be located exactly
is one that will not be written, because the alternative is a four-byte write at
an arbitrary offset inside executable bytecode.

### Property tags

```
infoByte = type | (sizeCode << 4) | (arrayFlag << 7)
```

Type is the low nibble: 1 byte, 2 int, 3 bool, 4 float, 5 object, 6 name,
7 string, 8 class, 9 array, 10 struct, 11 vector, 12 rotator, 13 str, 14 map,
15 fixed array. Size codes 0-4 mean 1, 2, 4, 12 and 16 bytes; 5, 6 and 7 mean
the real size follows as a `u8`, `u16` or `u32`. A struct writes its own type
name as a compact index before the size.

Two details that will each let a wrong reader look correct:

* **A bool has no value bytes at all.** Bit 7 is the array flag for every other
  type; for a bool it *is* the value. An earlier version of this reader treated
  bools as type 1 with a one-byte value and was simply wrong about all of them —
  which went unnoticed because the first cross-check only covered ints and
  floats.
* **The array index is not a compact index.** It is one byte under 128, two when
  the top bits are `10`, four when they are `11`. It agrees with a compact index
  for indices under 64 — exactly the range that hides the bug.
* **A `b`-prefixed name is not necessarily a bool.** Raven Shield's weapon caps
  are spelled `bSingle`, `bThreeRound`, `bFullAuto`, `bCMag`, `bSilencer`,
  `bLight`, `bMiniScope`, `bHeatVision` and every one of them is an **int32**
  (`info=0x22`, four bytes) holding 0 or 1, on the 57 classes that author them.
  Asking for them as `kind="bool"` gets nothing back. Counted across all four
  packages there are 113 genuinely bool-typed properties — `m_bIsSilenced` on
  46 classes is the common one — so both types are really present and the name
  tells you nothing about which you have.

### Values live inside structs, and inside arrays

The accuracy numbers are not top-level properties. They sit in
`m_stAccuracyValues`, a 49-byte struct whose value is itself a tagged property
list, so the walk recurses and the eight accuracy fields are reached by path
(`m_stAccuracyValues.fBaseAccuracy`). That nesting is also why the old byte
search appeared to work at all.

The loadout menu's stat bars are `ArrayProperty`: a count followed by the
elements, reached as `m_ADamagePercent[0]`. The element *type* is not in the tag
— it lives on the property's `Inner`, a separate export — so the width is
derived from the count, and only a four-byte width is exposed, read as `int32`.
That inference is deliberately narrow: a four-byte float array would be misread,
so nothing offers to write one.

### Which way the numbers point

Three of the five weapon knobs are inverted, which is the reason the profile
carries measurements rather than assertions.

* **Accuracy is dispersion.** `fBaseAccuracy` is a cone, so bigger is worse.
  `NormalAssaultM4` reads 1.26 standing, 1.74 shuffling, 2.61 walking and 10.78
  running — the number climbs as the stance gets worse, which is the proof.
* **Recoil is two numbers.** `fAccuracyChange` is accuracy lost per shot,
  `fWeaponJump` is muzzle climb. Moving one alone gives a weapon that climbs as
  far as before but recovers at a different rate.
* **`fReticuleTime` is a delay.** Lower settles faster.
* **Damage is not on the weapon.** It is `m_iEnergy` on the ammunition, which is
  why a silenced weapon and its plain twin hit equally hard. 5.56 NATO is 1442,
  7.62 NATO 2547, 9mm Parabellum 567, .50 BMG 15,825.

`m_iEnergy` is also carried by frag grenades, flashbangs, claymores, breaching
charges and remote charges, so "bullets hit harder" is scoped to class names
matching `ammo*` plus the `R6Bullet` base. Doubling a breaching charge is not
what anyone means by that option.

### The menu would otherwise lie

`R6Description.u` holds the loadout menu's five stat bars as int arrays of up to
three entries — one per variant (NORMAL, CMAG, SILENCED); 35 weapons have three,
15 have two and 8 have one. They are *authored percentages*, not anything the
game computes, so a retuned gun keeps its original bars unless they are
rewritten too.

The bars run the **opposite** way to the values behind them. Measured across the
139 equippable weapons rather than assumed:

| bar | underlying value | correlation |
|---|---|---|
| `m_ARecoilPercent` | `fWeaponJump` | -0.980 |
| `m_AAccuracyPercent` | `fBaseAccuracy` | -0.933 |
| `m_ARecoveryPercent` | `fReticuleTime` | **-1.000** |
| `m_ARangePercent` | `m_fMuzzleVelocity` | +0.812 |

A higher bar is a better gun, so halving recoil has to move the recoil bar *up*
and the mirror scales by the reciprocal. It is a proportional mirror and not the
game's own formula: bars clamp at 100, and a bar already at 0 stays at 0.

### How it is checked

Three independently produced datasets, all in `research/`, are compared against
what the parser computes — on every run, against the real installation:

| source | what it covers | result |
|---|---|---|
| `rs3_weapons.csv` | 197 weapon classes | 2,073 offsets **and values** agree |
| `rs3_ammo.csv` | 61 ammunition classes | 273 agree |
| `rs3_descbars.json` | 57 menu entries | 700 array elements agree |

Zero disagreements. The apply itself is then checked on a sandbox copy: every
package keeps its exact length, and **every single changed byte lies inside a
property value** — nothing in a header, a name table or an export table moves.

### Two caveats that are not about the format

A Steam file verification restores the stock packages without saying so, and a
server running stock packages may reject a client whose do not match. Both are
stated on the options themselves. Revert puts every byte back.

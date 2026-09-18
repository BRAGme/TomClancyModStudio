# GRAW 1 / GRAW 2 modding dossier (GRIN Diesel engine)

Scope: `D:\Tom Clancy's Ghost Recon - Advanced Warfighter` (GRAW1, `GRAW.exe` 2007-04-16)
and `D:\Tom Clancy's Ghost Recon - Advanced Warfighter 2` (GRAW2, `graw2.exe` 2022-09-01 rebuild).
Everything below is from files read in this session. Guesses are labelled GUESS.

Tools written this session (scratchpad, reusable):
- `bndl.py` — BNDL v2 index parser + `Game(root)` with patch-over-quick overlay.
  Verified: GRAW1 = 21,356 unique paths, GRAW2 = 25,052.
- `xmlbin.py` — full reader **and writer** for the compiled-XML format (see below).

### Which binary to analyse — read this first

**`GRAW.exe` (6,140,928 B, 2007-04-16) is PACKED. Do not string-scan or patch it.**
PE section table: 3 sections named `rr01` / `rr02` / `.rsrc`, no `.text`/`.rdata`/`.reloc`,
`rr01` is a 77 MB virtual-only section with **RawSize 0**, entry point RVA `0x04f22f90`
sits outside the first section. Of 84,968 extracted strings it contains `.xml` **once**,
`data/` **zero** times, `Diesel` **zero**, `.bundle` **zero**; the long strings are
ciphertext. The import table is intact and normal (KERNEL32, d3d9, binkw32, PhysXLoader,
OpenAL32, libcurl, NxCooking), so it is an in-place encrypted image, not a stub packer.

**Use `GRAW-standalone.exe` (8,171,520 B, 2006-10-19) for all GRAW1 binary work.**
Clean `.text`/`.rdata`/`.data`/`.tls`/`.rsrc`/`.reloc`, imagebase `0x400000`, same engine,
**full MSVC RTTI decorated names in the `dsl` namespace** preserved.

**`graw2.exe` (12,382,336 B, linked 2007-11-13) is clean and not packed.** Same RTTI bonus.

All exe offsets in this dossier are **file offsets** unless prefixed `VA:`.

---

## The .xml vs .bin question

**Answer: the plain `.xml` is live. Editing it is NOT inert.** The compiled form
(`.xml.bin` in GRAW1, `.xmb` in GRAW2) is a load-time optimisation / fallback, not
the authoritative copy. Four independent pieces of evidence, strongest first.

### Evidence 1 — GRIN's own mod pipeline never produces a compiled XML (GRAW2, decisive)

`D:\...GRAW 2\public_tools\bundler\bundle.bat` is the entire official mod build:

```
@bundler.exe compile-scripts %1
@bundler.exe quick-bundle -r %1 %1 -D %1.bundle
```

It calls `compile-scripts` (`.dsf` → `.dxe`) and then bundles. It **never calls
`compile-xml`**, which is a separate command that does exist
(`bundler.exe` @0x0009dd80: `bundler compile-xml [options] file1 [file2] ...`,
@0x0009dcac: `Compiles the listed .xml files into .xml.bin files.`, and the
`.xmb` literal at @0x0009dc40).

So every mod bundle built with the shipped, documented, GRIN-authored batch file
contains **plain `.xml` and zero `.xmb`**. GRIN shipped this as *the* modding path
(`mods\readme.txt`, `public_tools\bundler\readme.txt`). If the engine required the
compiled form, the official tool would produce dead mods.

(Note `public_tools\bundler\readme.txt` says "That will compile all xml and scripts" —
that sentence is wrong about xml, or it refers to an older bundle.bat. The batch file
is what actually runs.)

### Evidence 2 — the engine reads a loose `.xml` while a stale `.xml.bin` sits next to it (GRAW1, decisive)

`D:\...GRAW\Settings\` holds both forms of the same file:

| file | mtime | content |
|---|---|---|
| `defaults.xml` | 2025-03-02 00:03:40 | `<profile active="/settings/profiles/graw_profile_bragme"/>` |
| `defaults.xml.bin` | 2006-04-15 01:53:44 | `<profile active="/settings/profiles/graw_profile_default"/>` |

(`.bin` content is from decompiling it with `xmlbin.py` this session.)

`Settings\profiles\` contains exactly one profile directory, `graw_profile_bragme`,
holding `profile.xml`, `savegame_1.dsl`, `savegame_2.dsl` and three screenshots —
i.e. the game has been reading and writing that profile. `graw_profile_default`
does not exist on disk. The only file naming `graw_profile_bragme` is the `.xml`.
**The engine resolved the profile from the `.xml` and ignored the 19-year-old `.bin`.**

Supporting: `Settings\ctrl_set_def.xml` (2006-06-08, 3891 B) is two months **newer**
than `ctrl_set_def.xml.bin` (2006-04-15, 2626 B), and their decompiled trees differ.

### Evidence 3 — the compiled form is a real fallback, so it must be in the lookup chain (GRAW1)

Two `.xml.bin` files in GRAW1 have **no `.xml` twin at all**:

- `data/objects/beings/ghost_lead/ghost_lead.xml.bin` (quick.bundle @106836968, 18329 B)
- `data/objects/beings/mex_mp/mex_mp.xml.bin`

`ghost_lead` is the **player model**. `data/units/beings/u_player.xml:7`, `:81`, `:100`,
`:153`, `:170`, `:222` all say `<model file="/beings/ghost_lead/ghost_lead.xml"/>`;
`u_multiplayer.xml:8,:65` and `u_ghost.xml:12,:60` too. `mex_mp` is the MP enemy body
(`u_multiplayer.xml:83,:140`). The game obviously renders both. Since the requested
`.xml` does not exist, the loader must have fallen through to `<path>.bin`.

Combined with Evidence 2 (where the `.xml` wins over a present `.bin`), the order is:
**try `.xml` first, fall back to the compiled form.** GUESS on the exact mechanism —
it could also be newest-mtime-wins on disk, but that cannot apply inside a bundle,
and the ghost_lead case only works with a fallback.

### Evidence 3b — the extension literal lives in the XML loader, not the bundler

From the executables (see the binary notes below for which binary):

- GRAW1 `GRAW-standalone.exe` file offset `0x0056ce64` = `".bin"`
- GRAW2 `graw2.exe` file offset `0x005ebed8` = `".xmb"`

Both sit inside the XML parser's own string neighbourhood, surrounded by
`<XMLNodeIterator>`, `<XMLNode>`, `num_children`, `child`, `parameter_map`,
`has_parameter`, `xpointer`, `xi:include`, `xdefine`, `ISO-8859-1`, `UTF-8`,
`XML parser: expected -->`. That is the **loader**, not the offline compiler. An
extension swap performed at load time would live exactly there. Together with the
ghost_lead case it is hard to read any other way.

(Honest caveat: no log/diagnostic string like "using compiled version" exists in either
binary, so the *order* is not yet proven from disassembly — see Open questions.)

### Evidence 4 — what `<compile .../>` in context.xml actually means

`D:\...GRAW\context.xml` (last 3 lines):
```
	<!-- Enable this for bundled versions. -->
	<compile xml="false" scripts="false" mopps="false" texture_db="false"/>
```
`D:\...GRAW 2\context.xml`:
```
	<!-- Set all compile flags to false when running bundled version -->
	<compile xml="false" texture_db="false" mopps="false" scripts="false" />
```

Confirmed at the binary level: these four attribute names are adjacent literals inside
the context.xml key-name table in both exes (`installer`, `bundler`, `camera_shakes`,
`base`, `compress`, `make_logs`, `settings`, `renderer_config`, **`compile`**,
`instance_struct_config`, …) —

| string | GRAW1 `GRAW-standalone.exe` | GRAW2 `graw2.exe` |
|---|---|---|
| `compile` | `0x00549c94` | `0x005dc980` |
| `xml` / `mopps` / `scripts` / `texture_db` | `0x00549e10` / `0x00549e18` / `0x00549e24` | `0x005dcbd0` / `0x005dcbd8` / `0x005dcbe4` |
| `bundler` | `0x00549ba4` | `0x005dc89c` |

These are **compile-on-load** switches, not prefer-compiled switches. The flag names
map one-for-one onto the bundler's commands (`compile-xml`, `compile-scripts`,
mopps, texture_db). With `xml="true"` a dev build parses an `.xml` and writes the
`.xml.bin` cache beside it — which is exactly how the stale 2006-dated `.bin` files
in `Settings\` and `local\` came to exist on disk. With `xml="false"` (retail) the
engine does no compiling; it just loads. Nothing here says "prefer the compiled copy".

### Cross-check: the two forms agree

Decompiled every compiled file and compared it against its `.xml` for the subset with
no macros (`xdefine`/`$`/`xi:include`), tag-and-attribute exact:

| game | macro-free pairs compared | semantically identical | divergent |
|---|---|---|---|
| GRAW1 | 4,111 | 4,106 | 5 |
| GRAW2 | 5,729 | 5,716 | 13 |

The divergences are all preprocessing or encoding artefacts, not different data, e.g.
`data/gui/frame_items.xml` has `alpha="@base_alpha"` / `skip="@fade_out_time"` where
`frame_items.xml.bin` has `alpha="150"` / `skip="175"`; `data/gui/menu_base.xml` (GRAW2)
has `uv_rect="@div(238, 512) @div(318, 512) ..."` where `menu_base.xmb` has
`uv_rect="0.464844 0.621094 0.007813 0.027344"`. The compiled form is the same document
with macros already expanded, `xi:include` already resolved, and comments dropped.

**Practical consequence:** edit the `.xml`. If you want belt-and-braces (and for any file
where you cannot rule out the compiled path being taken), also rewrite the compiled twin —
`xmlbin.py` can do that, see next.

### The compiled format, decoded (and it is writable)

Magic `"XML\x01"`. Same format in both games; only the extension differs
(`foo.xml` → `foo.xml.bin` in GRAW1, → `foo.xmb` in GRAW2).

```
0x00  'X','M','L',0x01
0x04  u32  n_strings
0x08  n_strings * NUL-terminated latin-1 strings      (the string table)
      one root node
      u32  n_includes
      n_includes * NUL-terminated source paths        e.g. "data\settings\palett.xml"

node :=
  u32 kind
  kind 1  ELEMENT : u32 name_idx
                    u32 n_attr,  n_attr * (u32 key_idx, u32 val_idx)
                    u32 n_child, n_child * node
  kind 2  TEXT    : u32 text_idx
  kind 4  MACRO   : cstr macro_name ("@name")
                    u32 n_param,  n_param * cstr ("$param")
                    u32 n_extra,  n_extra * u32
                    cstr raw_body            <-- the xdefine body kept as literal XML text
                    u8  pad
```
The string table is in first-seen depth-first order; re-emitting in that order reproduces
the file exactly.

Verification run this session over every compiled file in both bundles:

| game | compiled files | parsed to exact EOF | **re-encoded byte-identical** |
|---|---|---|---|
| GRAW1 `.xml.bin` | 5,674 | 5,674 (100%) | **5,674 (100%)** |
| GRAW2 `.xmb` | 7,985 | 7,984 | **7,984** (1 file is not `XML\x01`) |

So yes — a full decompiler *and* recompiler exists and is proven round-trip clean.
A tool can therefore edit either form safely.

Counts, for reference: GRAW1 = 5,674 `.xml` + 5,674 `.xml.bin` + 84 other `.bin`
(e.g. `data/levels/*/xml/massunit.bin`, `ambient_cubes.bin` — different formats).
GRAW2 = 7,985 `.xml` + 7,985 `.xmb`, 1:1.

---

## Loose file override

**GRAW1: yes — `<install>\Data\...` shadows `data/...` in the bundle.**

### The mechanism, from the executables

Both binaries carry a full layered virtual filesystem, visible as intact MSVC RTTI
decorated names in the `dsl` (Diesel) namespace:

| class | GRAW1 | GRAW2 |
|---|---|---|
| `.?AVFileSystem@dsl@@` | `0x006b7518` | `0x00771c58` |
| `.?AVVirtualFileSystem@dsl@@` (a `Singleton<>`) | `0x006b9604` | `0x00774d7c` |
| `.?AVDiskFileSystem@dsl@@` | `0x006bcea4` | `0x00772048` |
| `.?AVBundleFileSystem@dsl@@` | `0x006bcec8` | `0x0078b6c4` |
| `.?AVDiskFileSystemWithFileTree@dsl@@` | `0x006bceec` | `0x0078b6e8` |
| `.?AVVFSReferenceFileSystem@dsl@@` | `0x006d6a18` | `0x007960d8` |

`DiskFileSystemWithFileTree` pre-indexes a directory tree from disk — and the tree
walker skips `.svn` (GRAW2 `0x005dc5f4`, referenced from `VA:005d4c68` and `VA:00730a9b`).
You only build a disk file tree if you intend to resolve asset names against disk.

Resolution is **forward iteration, first filesystem that answers wins** —
GRAW2 VFS vtable `0x009c05b8` slot 4 = `VA:0072eef0`:
```
0072ef40  mov  eax,[esp+0x24]      ; _Mysize
0072ef44  mov  ecx,[esp+0x20]      ; _Myoff
0072ef56  cmp  esi,eax
0072ef58  jae  0x72f020            ; exhausted -> fail
0072ef84  call dword ptr [eax+4]   ; child FS vtable slot 1
0072ef87  test al,al
0072ef8e  jne  0x72efed            ; HIT -> return this one
0072efe5  add  esi,1               ; next candidate
0072efe8  jmp  0x72ef40
```
The container is an MSVC `std::deque` (`_Myoff`/`_Mysize` + map-block indirection).
`deque` is chosen when you need `push_front` as well as `push_back` — i.e. later mounts
go to the front and therefore win. That is consistent with `patch.bundle` being mounted
after `quick.bundle` and, by definition, overriding it.

Mount order, from the one function that references all seven mount strings
(GRAW2 `0x005bf798`–`0x005bf7d8`, GRAW1 `0x00544a58`–`0x00544a98`):
```
VA:00431fc8  "bundles/quick.bundle"
VA:00431fd0  "bundles/patch.bundle"    ; 2-iteration loop, call 0x4122e0
VA:00432070  extra bundles (vector<std::string>), same call 0x4122e0
VA:004320d3  "local"                   ; requires local/<lang>/<sub>, 2 slashes
VA:0043228f  "movies"  VA:004322d3 "strings"  VA:00432317 "sound"  VA:00432357 "fonts"
```
→ `quick.bundle` → `patch.bundle` → mod / custom-level bundles → `local/<lang>/{movies,strings,sound,fonts}`.

### The corroboration that settles it in practice

Beyond the 764 user-added 2023 textures, **the 2006 retail installer itself lays down
loose files that duplicate bundle paths**:

| ext | loose in `GRAW1\Data\` | sampled | found inside `quick.bundle` | mtime |
|---|---|---|---|---|
| `.dds` | 764 | 10 | 10 | 2023 (user texture pack) |
| `.bik` | 171 | 10 | 10 | **2006 (retail installer)** |
| `.bank` | 154 | 10 | 9 | **2006 (retail installer)** |

Shipping 171 movies and 154 sound banks loose *on top of* identical bundle entries only
makes sense if the disk copy is the one served. The user's texture pack sits in exactly
the same relationship.

Remaining gap: I verified the VFS is layered and first-hit-wins, and that shipped loose
files duplicate bundle paths — I did **not** disassemble the specific registration call
that ranks the disk FS against the bundles in the deque. See Open questions.

### Where the root is, and how to move it

The root is the **install directory (the one containing the exe)**, not a `Data\`
subfolder — `Data` is just the first path component, exactly like `Settings`, `local`
and `custom_levels`. From the GRAW1 usage block:
```
0x005bbcc7    -d <dir>
0x005bbd0e        Use <dir> as start directory
0x005bbd9c        (You can also specify the start directory with a file named
0x005bbde3        'data_directory' in the directory of the application or with
0x005bbe2a        the EngineDataDirectory environment variable.)
```
Literals: GRAW1 `0x0054237c` `data_directory`, `0x00542358` `EngineDataDirectory`;
GRAW2 `0x005bf808` `base_path`, `0x005bf7fc` `start_exe`. Plus `context.xml`'s
`<script base="data" .../>`.

### Case and separators

GUESS (strong): paths are lower-cased and slash-normalised before lookup.
- Bundle index paths are all lowercase with backslashes, while the installer writes
  mixed case on disk (`Data/movies/API_COMIN_STR_SRI.BIK`) — a working install therefore
  *requires* case-insensitive matching.
- Both separators appear at different call sites for the same asset:
  `bundles/quick.bundle` (GRAW1 `0x00544a98`) vs `bundles\quick.bundle` (`0x0056851c`);
  `/data/` (`0x005497af`) vs `\data\` (GRAW2 `0x005dc7ec`).
- The `local/` scanner counts `0x2f` (`/`) after building the path (`VA:0043222b`), so
  paths are forward-slash by that point.

### File census

Confirmed by file census, not by exe strings alone.

`D:\...GRAW\Data\` holds 1,092 files:

| mtime year | count |
|---|---|
| 2006 | 326 |
| **2023** | **764** |
| 2025 | 1 |
| 2026 | 1 |

764 of them have paths that **exactly match** bundle paths (case-folded, `\`→`/`), and
they are far bigger than the bundled originals — this is an installed HD texture pack:

| path | loose size | bundle size |
|---|---|---|
| `data/textures/atlas_vehicles/panhard/diffuse/diffuse_set0/atlas.dds` | 134,217,856 | 2,796,368 |
| `data/textures/atlas_vehicles/stryker/diffuse/diffuse_set0/stryker_int_df.dds` | 134,217,856 | 2,796,368 |
| `data/textures/atlas_props/atlas_dirt/atlas_dirt_temp/atlas0/atlas.dds` | 67,109,012 | 5,592,560 |

The remaining 328 are loose-only and are demonstrably read: `Data\movies\*.bik` exists
only on disk, and `data/gui/menu/sections.xml:3` references
`<video name="video_main" video="/data/movies/menu_main.bik" .../>` — the main menu's
animated panel. So the loose `Data\` root is definitely on the search path, and 764
duplicate paths sit on top of bundle entries.

Path mapping: bundle key `data/textures/...` ↔ disk `<install>\Data\textures\...`.
Lower-cased, separator-insensitive. The install root is the base, and `Data` is just
the first path element — same as `Settings\`, `local\`, `custom_levels\`.

Other loose roots that are read (all GRAW1, none overlap the bundle):
- `Settings\` — 14 files. `defaults.xml`, `ctrl_set_def.xml`, `default_mp_weapon_kits.xml`,
  `servers_shared.xml`, `weapon_ids.txt`, `MPID.txt`, `profiles\<name>\profile.xml`.
- `local\<language>\` — 108 files: `french|german|italian|polish|spanish` ×
  `strings\*.xml` and `sound\voices\*`. Selected by `context.xml`
  `<script ... language="english"/>`.
- `custom_levels\` — level bundles.

**GRAW2: no loose override in evidence.** `D:\...GRAW 2\Data\` has 116 files, all 2007,
and **zero** overlap with bundle paths (it is only `Data\movies\*.bik`). GRAW2's
`Settings\` (7 files) likewise doesn't shadow anything. GRAW2's intended override
mechanism is `mods\*.bundle` instead.

**So the tool can mod GRAW 1 with loose files and never write a bundle.** For GRAW 2
it must write a bundle.

---

## Mod systems

### GRAW 2 — a real, documented mod system

`D:\...GRAW 2\mods\readme.txt` (verbatim):
> Add your mod bundles here, edit context.xml add the line `<mod_bundle name="modname"/>` where modname is the bundle filename.
> So if you have a mod called new_weapons.bundle the context.xml line should be: `<mod_bundle name="new_weapons"/>`.
> You can not enable more than one mod at the same time.

`public_tools\bundler\readme.txt` gives the layout — a directory mirroring the game tree:
```
my_mod/
    data/
        lib/managers/{aihivebrain,guiscreens,hudmanager}.dsf
        lib/units/ai/aidetection.dsf
        settings/mod_version.xml
```
then `bundle.bat My_Mod` → `My_Mod.bundle` → copy to `<install>\mods\`.

`mod_version.xml` (shipped example, `public_tools\bundler\mod_version.xml`):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<mod_version>
     <mod id="My_Mod" version="1.0"/>
</mod_version>
```
It gates multiplayer joins — clients with the wrong version are refused. Confirmed in
data: the only file in either bundle containing `mod_version` is
`data/lib/script_network/networkmanager.dxe`, i.e. it is a network-layer check.

Custom levels are a separate path: bundle into `<install>\custom_levels\`, and
**"custom levels are not allowed to have override files in them"** — every file inside
a custom-level bundle must be unique to it. Mods may override; custom levels may not.

`bundler.exe` (GRAW2, 836,096 B) commands, from its own help strings:
`quick-bundle`, `bundle`, `compile-xml`, `compile-scripts`, `extract`, `list`, `make-patch`.
`extract` and `list` mean a tool can shell out to it instead of reimplementing the reader.
Also present: `atlasgen.exe`, `maxexporter.dle`, and three PDFs
(`GRAW2_Editor.pdf`, `GRAW2_GameModes.pdf`, `GRAW2_Scripting.pdf`).

Bundle discovery is one function, GRAW2 `VA:005d58c0`–`005d5a48`:
```
VA:005d58d2  "patch"          VA:005d58e0  "bundles"
VA:005d5977  "-mod"           <- command-line switch, same effect as <mod_bundle>
VA:005d59dc  "mods"
VA:005d5a48  "*.bundle"       <- custom_levels enumeration
```
with the string cluster at `0x005dc550`:
```
Could not load context.xml /  contains an invalid file path / Custom level bundle 
.bundle / custom_levels / *.bundle / mods / -mod / bundles / patch / init_game / .svn
```
So `graw2.exe -mod <name>` is a command-line equivalent of the `<mod_bundle>` line —
useful for a tool that wants to launch with a mod without editing `context.xml`.

### GRAW 1 — no mod-bundle system

GRAW1 has the **identical string cluster at `0x00549898` minus `mods`, `-mod`,
`bundles`, `patch` and `.svn`**. The mod system was added in GRAW2. GRAW2 also adds the
context.xml keys `filesystem` (`0x005dc9f8`) and `mod_bundle` (`0x005dca04`), neither of
which exists in GRAW1.

- No `mods\` folder.
- `context.xml` has no `<mod_bundle>` line and the comment block in it only offers the
  editor/menu swap.
- `mod_bundle`, `mod_version`, `mods_dir` and `/mods/` appear in **zero** bundle files
  (searched all 21,356, including `.dxe`).
- `custom_levels\Readme.txt` is for maps only: *"To play custom maps, share only your
  .bundle map file with others, or put their .bundle files of other maps in here."*
- `Bundles\init_game.xml` is not a mod hook — it is a **filesystem access log**, 17 lines
  all `<open path="context.xml" flags="r" />`. It is produced when `context.xml` has
  `<bundler make_logs="true"/>` (emitter literals GRAW2 `0x005eb934` `   <open path="`,
  `0x005eb944` `" flags="`, `0x005eb950` `" />`) and consumed by
  `bundler bundle [options] file_log1 ...` to order a bundle for streaming locality.
  Turning `make_logs` on is a legitimate way to observe exactly which files a session
  touches, in order — useful for a modding tool, and it answers "is my file being read?"
  without a debugger.
- GRAW1 does ship its own bundler at `tools\bundler.exe` (2,861,568 B, 2006-06-08), but
  its command set is smaller: `quick-bundle`, `bundle`, `compile-xml`, `compile-scripts`,
  `merge-logs` — **no `extract`, no `list`, no `make-patch`**.

**So for GRAW 1 the route is loose files under `Data\` (and `Settings\`, `local\`), not a
mod bundle.** Which is fortunate, because that is also the easier route.

### Developer surface worth knowing (both games)

**Command line.** GRAW1: `-h`, `-c <file>` (context file), `-d <dir>` (start directory),
`-o <file>`, `-u` (unit-test mode), `-q`, `-s`; plus `lightmap_slave`, `lightmap_server`,
`XCMD`. GRAW2 adds `-mod <name>`, `-delayedstart`, `-crash` (undocumented, GUESS: a
deliberate-crash test hook), `-reset` (resets rendering settings), `-restart_mc`,
`-network_index`, `-network_ip`, `-network_list`, and from shipped files
`-dedicated_game_info <game_info>` and `-port <n>` (`script_params.txt`).
`graw2_editor.bat` is literally `graw2.exe -o context-editor.xml -path %1`.

**Editor.** Not a switch — a `context.xml` attribute. Both games ship a working
`context-editor.xml`:
`<script base="data" exec="levels/editor/editor" editor="true" editable="true" enforce_texture_sets="false" override_allow_autoload="true"/>`
and GRAW1's retail `context.xml` ships the identical line commented out with
*"exchange this line with the one under the comment to start in editor mode"*.
So GRAW1's editor is one uncommented line away, with no mod system needed.

**In-game console command groups** (string tables in both):
`fx`, `Network`, `Animation`, `Unit`, `Physics`, `Search`; GRAW1 also `Novodex`. Examples:
```
unit disable [pattern]    -- disable all units matching pattern
unit enable  [pattern]
unit script  [pattern] [script]   -- run script on units matching pattern
unit kill_mover [pattern]
unit profiler [reset/report/above/autoreset/peak]
tweaks                    -- list all tweaks
tweak [level] par val     -- set a tweak value
search show {map/graph} [color]   /  search debug  /  search debug-cluster
simulate [latency] [loss] [order] -- simulate packet latency (ms), loss (%), reordering
```
Script-exposed engine entry points include `screenshot`, `console_command`, `version`,
`stats`, `render_info`, `triangle_count`, `batch_count`, `texture_switches`,
`last_camera_position`, `set_gamma_ramp`, `set_brightness`; GRAW2 adds
`cpulog_start` / `cpulog_stop`.

**Filesystem script API** (available to `.dsf` scripts, so available to a mod):
`open`, `read`, `write`, `printf`, `print`, `gets`, `puts`, `close`, `at_end`,
`can_write_to`, `copy_file`, `delete_file`, `make_dir`, `parse_xml`, `list`, `full_path`,
`system_path`, `is_dir`, `exists`. GRAW2 adds `list_config_files` and `config_exists`.
Note **`parse_xml`** — scripts can parse XML at runtime, another reason plain `.xml` has
to stay live.

**Not present in either binary:** `-devmode`, a `developer` flag, `cheat`, `godmode`,
`noclip`, `invulnerable`, `unlimited_ammo`, `debug_menu`. There is no shipped cheat menu.

**GRAW2 anti-tamper:** `The game executable is corrupted, please reinstall.`
(`0x005bc748`), `Corrupted executable!`, `DXProtection` / `DX Protection`,
mutexes `Global\GRAW2` and `Global\GRAW2_Running`, and
`The application cannot be started remotely, exiting...`. Patching `graw2.exe` bytes is
likely to trip a self-check — another reason to stay in data-land.

Terminology trap: in GRAW data, "mod" means **weapon attachment**, not game mod.
`data/strings/mods.xml` is a list of `mod_sniper_scope`, `mod_barrett_bipod`,
`mod_silencer_primary`, `mod_eglm`, `mod_aimpoint`, … Don't grep for "mod" and think
you found a mod loader.

---

## Levers

### Where the per-user settings actually live (GRAW2)

`Settings\hud_palett_2.xml` documents this itself, in a comment:
> Note: To change the crosshair color go to `data\settings\profiles\"profile name"\settings.xml`
> and change the `ret_color` value to the preferred color, Vista users will find their
> `data\settings` folder under: `C:\Users\"computer username"\AppData\Local\GRAW2\settings\`

So on this machine GRAW2's live per-user settings are under
`%LOCALAPPDATA%\GRAW2\settings\profiles\<profile>\settings.xml`, **not** in the install
folder. GRAW1 keeps its profiles in the install folder instead
(`<install>\Settings\profiles\<name>\profile.xml` — confirmed, `graw_profile_bragme`
is there with two savegames). A tool must handle both locations.

_(gameplay-data sweep below)_

---

## Art

**`data/gui/` contains no images in either game** — it is 143 `.xml`/`.xml.bin` entries in
GRAW1 and the equivalent in GRAW2. All menu art is under `data/textures/`, and the two
games use different trees:

- GRAW1 → `data/textures/atlas_interface/menu/` (42) + `data/textures/gui/` (45)
- GRAW2 → `data/textures/atlas_gui/` (67) + `data/textures/gui/` (43)

GRAW2 still ships the GRAW1 `atlas_interface/menu/` tree, unreferenced — dead leftovers.

### Wordmarks (both have real alpha)

| game | bundle path | size | dims / format | alpha |
|---|---|---|---|---|
| GRAW1 | `data/textures/atlas_interface/menu/logos_diffuse/h_1600x1200.dds` | 2,097,280 B (quick.bundle @2579883272) | 2048×256 A8R8G8B8, 0 mips | 256 distinct values; 73.4% transparent, 18.7% opaque, 7.9% partial |
| GRAW2 | `data/textures/atlas_gui/general_gfx/sp_logo_h.dds` | 262,272 B (quick.bundle @917483112) | 512×128 A8R8G8B8 | 256 distinct; 46.3% transparent, 17.1% opaque, 36.6% partial |

GRAW1's is teal "TOM CLANCY'S · GHOST RECON / ADVANCED WARFIGHTER™" with the ghost skull
in the O. It is resolution-switched at runtime by the `show_horizontal_logo` /
`show_vertical_logo` callbacks in `data/gui/menu/sections.xml` (lines 127, 239, 267, 613),
which pick between `h_640x480` … `h_1600x1200` and the `v_*` vertical lockups. Take
`h_1600x1200.dds` as the highest-fidelity source. Also `menu_loading_logo.dds` (512×64,
131,200 B).

GRAW2's is referenced at `data/gui/gui_screens.xml:514` and `data/gui/briefing.xml:2272`
as `<bitmap name="logo" material="GRAW_logo" … size="512 128" />`.

### Backdrops — neither game has one as a file

**GRAW1** builds the menu background procedurally in `data/gui/menu_bg.xml`
(quick.bundle @2935407328, 4,365 B): a full-screen rect at `color="@base_color" alpha="255"`,
then `menu_hexagon_df` tiled 42×29 at `color="0 0 0" alpha="60"`, then `menu_overlay_fade`
at `size="1.5 1.5" color="0 0 0" alpha="255"`, plus 3D units `menu_globe` / `menu_badge`.
The wordmark blocks in that file are commented out (lines 15–25). The animated panel is
Bink video, not a texture: `data/gui/menu/sections.xml:3` →
`<video name="video_main" video="/data/movies/menu_main.bik" video_size="696 261" loop="true"/>`,
loose on disk at 22,165,000 B (warm desaturated tan footage of a helmeted Ghost).

**GRAW2** is flat palette colour plus frame pieces cut from
`data/textures/atlas_gui/main_menu/menu_back.dds` (1,048,704 B, quick.bundle @277098608,
1024×256), sliced at `data/gui/hud_interface_elements.xml:211-215`
(`bottom_frame_left/middle/right/stripe`, `menu_ghost_skull`, explicit uv_rects).
Nearest full-frame art is `atlas_gui/mission_gfx/load_sp_m01.dds` (2048×2048 DXT1, 2,097,280 B).

GRAW1's 9-slice panel chrome is `data/textures/gui/interface_items.dds` (128×128 DXT5,
16,512 B, patch.bundle @53450356) — authored white/grey *specifically to be tinted*, with
uv_rects enumerated at `interface_items.xml:88-99`.

### The GRAW2 RGB trap

GRAW2's `atlas_gui` textures decode to pure `#00FF00` / `#FF0000` / `#0000FF` because
**RGB carries three tint masks, not colour**.
`data/objects/gui/hud_new/materials.xml` (patch.bundle @26351880, 94,609 B) line 869:
```xml
<material name="GRAW_logo" src="hud_tint">
  <variable name="red_color" type="vector3" value="@X1"/>  … @X2 … @X3
```
R→`red_color`, G→`green_color`, B→`blue_color`, resolved from the palette. If you open
these in an image viewer and see neon primaries, the file is fine — you are looking at masks.

### Palettes — the cyan/teal belief is CORRECT for both, but they are different teals

Both palettes ship as authored text, so these are read values, not quantisation guesses.

**GRAW1** — `data/gui/interface_items.xml` (patch.bundle @752938544, 33,747 B):

| role | hex | source (verified line numbers) |
|---|---|---|
| bg | `#1D8997` = `29 137 151`, default alpha 150 | L27 `base_color`, L30 `base_alpha`; applied via the `set_color_base` trigger L33-35 |
| panel | `#006C7A` = `0 108 122` @ a255 | L28 `darker_base_color`, L31 `darker_base_alpha`, trigger L46-48 |
| edge / rule | `#17C5C0` @ a120 | `hud_lib.xml:6` `frame_color`; `interface_items.xml:9` `frame_alpha` = 120 |
| text | `#FFFFFF` (credits `#F0F0F0`) | `menu/base.xml:15-19` |
| accent | `#FF6C00` = `255 108 0` @ a150 | L65-66 `highlight_hud_color` / `highlight_hud_alpha`, trigger L67-69 |
| selected row | `#40B0BF` = `64 176 191` @ a220 | L59-60 `selected_color` / `selected_alpha`, trigger L61-63 |
| hover row | `#329CAB` = `50 156 171` @ a190 | L53-54 `highlight_color` / `highlight_alpha` |
| disabled | alpha 70 | L37 `disabled_alpha` |

Bonus levers in the same file: `move_color` `0 255 0` (L20), `attack_color` `200 0 0` (L21),
`cover_color` `0 0 200` (L22), `objective_color` `127 244 127` (L25) — the squad-order
marker colours. Note the file is an `xdefine` block, so the values are referenced as
`@base_color` etc. throughout the GUI and changing them here recolours everything at once.

**GRAW2** — `D:\...GRAW 2\Settings\hud_palett_2.xml` (loose on disk, self-documented,
section `<HUD>` labelled "Official GRAW2 GUI setup"):

| role | hex | palette key |
|---|---|---|
| bg | `#001717` | `B2` blue_darker |
| panel | `#023D40` / mid `#047E80` | `B1` / `C` |
| edge / rule | `#06C2C5` | `D1` blue_light |
| text | `#96F7F8`; white `#FFFFFF` | `D2` / `I` |
| accent | `#E6AB40` amber | `A` orange |
| selected row | fill `#023D40` + text `#D8F8F9` | `B1` + `D3` |
| logo tint | `#013338` / `#009BA6` / `#FCFDFD` | `X1` / `X2` / `X3` |

Two pixel cross-checks that the palette is the real one:
`atlas_gui/main_menu/loadbar.dds` decodes to a flat `#E6A93F` (= `A`, `#E6AB40`), and
`menu_back.dds` pixel (990,200) is exactly `(6,194,197)` = `D1`.

**Summary of the difference:** GRAW1 = mid teal `#1D8997` used as a translucent tint over
the whole frame, hot-orange accent `#FF6C00`. GRAW2 = darker and colder, near-black panels
`#001717`/`#023D40`, brighter cyan `#06C2C5`/`#96F7F8` for lines and text, and the orange
swapped for a softer amber `#E6AB40`. GRAW2 also ships a complete alternate brown scheme
(`<HUD_alt1>`) in the same file, unused by default — `hud_palett_2.xml` being a loose,
editable file makes recolouring GRAW2's entire HUD a one-file edit.

Extracted assets + PNG conversions: `scratchpad\art\graw1\`, `scratchpad\art\graw2\`.

---

## Cut content

Brief, as asked.

**GRAW1 — mission07 does not exist.** Campaign level dirs run `mission01`–`mission06`,
`mission08`–`mission12`. The string `mission07` appears in **zero** of the 21,356 bundle
files (searched all text assets and `.dxe`). Contrast GRAW2, which has both
`data/levels/mission07/` and `data/strings/mission07.xml`.

**GRAW1 — `mission05_ogr` (7,025,365 B, 23 files) and `mission06_ogr` (19,915,404 B,
25 files)** are full-weight extra levels referenced only from `data/lib/utils/guimenu.dxe`,
`data/lib/script_network/gametype/gametypempcoop.dxe` and `data/strings/menu.xml` — i.e.
co-op-only variants of campaign maps, reachable from the MP co-op list rather than the
campaign. Same for `mpc01` (2,921,004 B).

**GRAW1 — `data/levels/prebundle/`** (885,132 B, 13 files) is referenced by nothing in
gui/settings/lib/strings. A build artefact. `template/` (884,984 B) is the editor's blank
level.

**GRAW2 — `data/levels/ogr_hacienda/`** (3,465,316 B, 16 files) is a complete level whose
name appears only in texture-database entries (`data/textures/gui/tdb_texture_set.xml`,
`data/textures/lightmaps/ogr_hacienda/atlas0/tdb_atlas_set.xml`, `texture_db.bin`) —
never in a menu, script or string file. Unreachable in the shipped game.

**GRAW2 — `ageia_bonus_mission`** (5,797,815 B) is the PhysX promotional bonus level; it
*is* wired up (`data/strings/ageia_bonus_mission.xml`, `data/strings/mission.xml`,
`data/settings/physics_settings.xml`), so it is unusual but not cut.

**Both — `data/textures/atlas_interface/menu/`** survives in GRAW2 with nothing referencing it.

**GRAW1 — 2 orphan compiled files** with no `.xml` source shipped:
`data/objects/beings/ghost_lead/ghost_lead.xml.bin` and
`data/objects/beings/mex_mp/mex_mp.xml.bin`. Not cut content — see Evidence 3 above —
but they are the only two places where the plain XML is genuinely unavailable, so a tool
that only edits `.xml` will silently fail to touch the player and MP-enemy models.

---

## Open questions

1. **Exact `.xml`-vs-compiled lookup order, proven from disassembly.** The evidence is
   one-directional and consistent (`.xml` wins when both exist; compiled is used when the
   `.xml` is absent), and the extension literal lives in the XML loader — but no
   instruction-level trace is in hand yet. Two ways to close it:
   - **The cheap empirical test, no debugger:** set `<bundler make_logs="true"/>` in
     `context.xml`, run once, read the generated access log. It records every `<open
     path="..."/>` in order. That answers "does it open `foo.xml` or `foo.xml.bin`"
     directly. (This edits `context.xml` inside the game folder, so it needs your
     go-ahead — I have not done it.)
   - Disassembly of the xref sites for `".bin"` (GRAW1 `0x0056ce64`) and `".xmb"`
     (GRAW2 `0x005ebed8`).

   **This does not block the tool.** The safe play is to write **both** forms on every
   edit; `xmlbin.py` re-encodes byte-identically, so that costs nothing and is correct
   under either order.
2. **Disk-vs-bundle rank in the VFS deque.** The VFS is confirmed layered and
   first-hit-wins, mount order for the bundles is confirmed, and both the retail installer
   (171 `.bik` + 154 `.bank`, 2006) and the user's texture pack (764 `.dds`, 2023) ship
   loose files duplicating bundle paths. What is *not* disassembled is the registration
   call that ranks `DiskFileSystem` against `BundleFileSystem`.
3. **GRAW2 loose-file override.** Untested — GRAW2 ships no loose files that collide with
   the bundle, so there is nothing to observe. GUESS: it probably works, same engine. If
   it does, GRAW2 modding gets much easier and the bundler becomes optional.
4. **Case-folding / slash normalisation** is inferred from the mixed-case installer vs
   all-lowercase bundle index, not proven.
5. **`.dxe` script constants.** Anything living in compiled script rather than XML is
   outside the reach of an XML-editing tool. See the Levers section for how far that goes.

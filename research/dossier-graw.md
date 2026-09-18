# GRAW 1 / GRAW 2 modding dossier (GRIN Diesel engine)

Scope: `D:\Tom Clancy's Ghost Recon - Advanced Warfighter` (GRAW1, `GRAW.exe` 2007-04-16)
and `D:\Tom Clancy's Ghost Recon - Advanced Warfighter 2` (GRAW2, `graw2.exe` 2022-09-01 rebuild).
Everything below is from files read in this session. Guesses are labelled GUESS.

Tools written this session (scratchpad, reusable, all verified):
- `bndl.py` — BNDL v2 index reader + `Game(root)` with patch-over-quick overlay.
  Verified: GRAW1 = 21,356 unique paths, GRAW2 = 25,052.
- `bndlw.py` — BNDL v2 **writer**, incl. deletion tombstones. Verified by re-packing
  40 real GRAW2 files with 0 byte mismatches on read-back.
- `xmlbin.py` — full reader **and writer** for the compiled-XML format. Verified
  byte-identical on 5,674/5,674 GRAW1 `.xml.bin` and 7,984/7,985 GRAW2 `.xmb`.

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

### Read this first — the blunt version

**For anything already inside a bundle, the COMPILED form is what loads. Editing the
bundled `.xml` and leaving its compiled twin in place is INERT.** This is the Lockdown
`.rsc`-vs-`.script` trap and it is real here.

Ground truth, not inference: GRAW1's own `quick.bundle` ships a recorded engine
filesystem trace at bundle path **`temp_merged_log.xml`** (857,485 B, quick.bundle
@2317890536) — a real GRIN session captured with `<bundler make_logs="true"/>`. It
contains **9,508 `<open path="..."/>` records**:

| extension opened | count |
|---|---|
| `.mopp` | 4,330 |
| **`.xml.bin`** | **3,034** |
| `.diesel` | 895 |
| `.dds` | 881 |
| `.dxe` | 277 |
| `.bin` (other) | 33 |
| `.bundle` | 18 |
| **`.xml`** | **13** |
| `.abc` / `.gph` / `.tga` / `.dsf` | 12 / 11 / 3 / 1 |

Restricting to paths where **both** forms exist in the shipped bundle:
**`.xml.bin` chosen 3,029 times, `.xml` chosen 2 times.**

All 13 plain-`.xml` opens are the expected exceptions — files with no compiled twin, or a
newer source:
```
context.xml                                     <- loose, root, has no .bin
settings\defaults.xml                           <- loose, .xml (2025) newer than .bin (2006)
settings\profiles\default\profile.xml
settings\profiles\graw_profile_default\profile.xml
data\objects\effect_spawners\materials_sam.xml
data\objects\brush\debris\physx_{stone,pipe,half_brick,bricks}.xml
data\sound\environment\tunnel\{tunnel_wave,tunnel_sound}.xml          <- see note
data\sound\environment\building_collapse\{..._wave,..._sound}.xml
```
The two tunnel files are the *only* two opens in the whole trace where both forms exist
in the shipped bundle and the `.xml` still won. GUESS: on the machine that produced the
trace their `.xml` was newer than the `.xml.bin`, i.e. the `jl` branch — which is exactly
what a mod does deliberately.

**So: you can still mod everything, but not by editing a bundled `.xml` in place.**
Three routes that do work, in order of preference:

1. **Loose `.xml` on disk with a current mtime.** Beats the bundled compiled form via the
   timestamp rule below. Best route for GRAW1. Confirmed mechanism, and the engine trace
   shows exactly this happening for `settings\defaults.xml`.
2. **A mod bundle containing only `.xml`, no compiled twin** (GRAW2). With no compiled
   file present the loader takes the `.xml` branch. This is precisely what GRIN's own
   `bundle.bat` produces — it runs `compile-scripts` but never `compile-xml`.
3. **Rewrite the compiled form too.** `xmlbin.py` re-encodes byte-identically
   (5,674/5,674 and 7,984/7,985), so this is cheap and always correct.

One file is always safe to edit in place: **`context.xml` is never in a bundle and has no
compiled twin.** GRAW1's bundle root holds `context-editor.xml`, `context-standalone.xml`
and three `context.xml.{editor,lightmap_server,lightmap_slave}` variants — but **not
`context.xml`**; GRAW2's bundle root holds only `context-standalone.xml` and `si.bin`.
The engine trace's very first record is `<open path="context.xml"/>`, reading the loose
disk copy. So the `<mod_bundle name="..."/>` edit (GRAW2) and the editor-mode swap (both)
are guaranteed to take.

### The rule

**The engine arbitrates the two by `CompareFileTime`. Settled by disassembly.**

```
                    compiled (.xml.bin / .xmb)
                    exists?          missing?
source .xml  exists  -> CompareFileTime  -> .xml
             missing  -> compiled        -> (nothing)

CompareFileTime(mtime(source), mtime(compiled)):
    compiled OLDER than source  -> load the .xml
    compiled newer OR EQUAL     -> load the compiled form      <-- ties go to compiled
```
Plus: if `context.xml` has `<compile xml="true"/>` the whole probe is skipped — it loads
the `.xml` and *writes* the compiled form back out. Retail ships `xml="false"`.

**What this means in practice:**

| situation | what loads | so… |
|---|---|---|
| loose `.xml` on disk, present-day mtime; compiled twin only in the bundle | **your `.xml`** | ✅ reliable route, both games |
| mod bundle containing only `.xml`, no compiled twin | **your `.xml`** | ✅ what `bundle.bat` produces |
| you edit a bundled `.xml`, compiled twin left in place | **the compiled twin** | ❌ **inert — 3,029 : 2 in the engine trace** |
| compiled-only asset (`ghost_lead.xml.bin`) | compiled | a loose `.xml` with a newer mtime still beats it |

One consequence worth stating explicitly: **to override a compiled-only asset such as
`ghost_lead` in GRAW1, dropping a loose `ghost_lead.xml` is enough.** Once both forms
exist the timestamp branch runs, and a present-day mtime beats the 2006-era bundled
`.xml.bin`. You do not need to produce a `.xml.bin` at all.

Caveat, unverified: what timestamp `BundleFileSystem` reports through VFS `+0x30` for a
bundled entry (the bundle file's own mtime, a stored per-entry time, or zero). Any of
those loses to a present-day mtime, so the conclusion holds — but note that **equal
timestamps go to the compiled form**, which is why in-bundle pairs resolve to the
compiled file 3,029 times out of 3,031.

### The disassembly

**GRAW1, `GRAW-standalone.exe`.** `".bin"` at file offset `0x0056CE64` → `VA:0096DA64`
(.rdata raw `0x541400` / VA `0x542000` / imagebase `0x400000`). Exactly **3 xrefs
image-wide, all inside one function at `VA:006CF720`**.

Helpers, all thin wrappers on the `VirtualFileSystem` singleton at `0x00AE3440`:

| address | vtable slot | role |
|---|---|---|
| `0x0061B340` | VFS `+0x14` | full-path transform |
| `0x0040AF50` | VFS `+0x18` | `open(path, mode)` |
| `0x0040AFB0` | VFS `+0x30` | modified-time(path), FILETIME in `edx:eax` |
| — | VFS `+0x04` | `exists(path)`, called inline |
| `0x004063B0` | — | string concat |
| `0x006D10D0` | — | XML parse entry |

Flow:
1. `006CF791 call [eax+4]` = `exists(original)` — this only chooses which base string to
   derive from; **both arms then build `<base>` + `".bin"`** (`006CF7A7` and `006CF81E`).
   GRAW1 **appends**, so `foo.xml` → `foo.xml.bin`.
2. `006CF86D cmp byte ptr [ecx+0x144], bl` / `jne 006CFB18` — the `<compile xml=…>` flag.
   Set ⇒ jump straight to the `.xml` path (parse, then write the `.bin`).
3. Retail (flag clear) runs the probe tree:
   - compiled exists **and** original does not → `006CF8B1 je 006CF930` = **open the `.bin`**
   - both exist → `006CF8F5..006CF92A`:
     ```
     006CF8F6  call 0x40AFB0          ; get_time(.xml)
     006CF908  call 0x40AFB0          ; get_time(.bin)
     006CF922  call dword [0x9421C0]  ; KERNEL32!CompareFileTime  (via the import table)
     006CF92A  jl   006CFB18          ; compiled OLDER than source -> take the .xml
     ```
     fall-through (compiled newer **or equal**) → `006CF930` = take the `.bin`
   - compiled missing → `006CFB18` = `.xml`
4. `006CF930` = `open(.bin, "r")` — mode literal at `0x00943CE0` (byte `0x72`).
5. `006CFB18` = `open(.xml, "r")` → parse at `0x6D10D0` → if global flag `[0x00AF14F8]`
   is set, rebuild `<base>.bin` (the third xref, `006CFBD9`) and open it mode `"w"`
   (literal `0x009467EC` = `0x77`). That is the write-back that created the stale `.bin`
   files sitting on disk.

**GRAW2, `graw2.exe`** — same design, refactored, and the extension is **replaced, not
appended**. `".xmb"` at file offset `0x005EBED8` → `VA:009ED0D8`, 6 xrefs across 4
functions (`0073D270`, `0073D3A0`, `00744410`, `00745B90`). VFS singleton `0x00BAB9E0`;
`CompareFileTime` IAT slot `0x009BC254`. The loader twin of `006CF720` is `00745B90`:
```
745C65  call 0x40CCD0    ; substr(name, 0, len-4)   <- strips ".xml"
745C6A  push 0x9ED0D8    ; ".xmb", then concat 0x406DD0
745CDB  cmp byte [edx+0x148] / jne 745F6D   ; compile flag (moved from +0x144)
745CF4/745D04/745D18/745D2C   VFS[+4] exists() probes
745D09  je  745D82       ; xmb exists && xml missing -> open xmb
745D74  call [0x9BC254]  ; CompareFileTime
745D7C  jl  745F6D       ; -> .xml path
745D82  open .xmb, mode "r" (0x009BCC30)
746000  cmp byte [0x00BC93D4]  ; gates the write-back that rebuilds "<base>.xmb" at 74603C
```
`0073D3A0` is a *separate* helper: it strips either `".xml"` (`0x009C81D8`) or `".xmb"`
and returns `max(mtime(.xml), mtime(.xmb))` — a staleness/dependency probe, not the loader.

**All of this runs through the VFS**, so the arbitration happens across the **merged
bundle + disk view**, not per-mount. Every `exists` / `get-time` / `open` above is a VFS
singleton vtable call, and the resolver (GRAW2 `VA:0072EEF0`, forward first-hit-wins over
the mount container) sits one level *below*, invoked once per candidate name. That is
precisely why a newer loose `.xml` on disk beats a bundled compiled file.

### The corroborating evidence, and what each piece does and does not prove

### Evidence 0 — GRIN's own final patch moved a file OUT of the bundle and shipped it as loose plain XML (GRAW2)

Follow the chain — it shows GRIN deliberately using the loose-disk route to make
something player-editable, which is route 1 above:

1. `quick.bundle` originally shipped the HUD palette **both ways**:
   `settings/hud_palett.xml` (5,545 B @52486928) and `settings/hud_palett.xmb`
   (2,962 B @2248308552).
2. `patch.bundle` contains exactly **three zero-length entries** — the bundle format's
   deletion tombstone (cf. `bundler extract -d, --allow_delete  … bundle remove files
   and directories will be removed from target!`). All three are that palette:
   `settings/hud_palett.xml` (0 B), `settings/hud_palett.xmb` (0 B),
   `settings/hud_palett_dev.tga` (0 B). GRAW1's `patch.bundle` has **zero** tombstones,
   so this was a deliberate, one-off removal.
3. In their place the patch installs, **loose on disk and as plain XML only**:
   `D:\...GRAW 2\Settings\hud_palett_2.xml` (5,819 B, 2022-09-01) and
   `hud_palett_dev_2.tga`. There is **no `hud_palett_2.xmb` anywhere** — not on disk,
   not in either bundle.
4. That loose file is written *for the player*. Its own opening comment:
   > Material files for the main GUI include the colors from the `<HUD>` include below.
   > To change colors, copy desired setup into the HUD tag or just change the color values (R G B)
5. The consumer is a bundled file — `data/objects/gui/hud_new/materials.xml:3`
   (patch.bundle @26351880, 94,609 B):
   ```xml
   <xi:include href="/settings/hud_palett_2.xml#xpointer(/include/HUD/*)"/>
   ```
   and `data/sb_templates/global/sb_global.xml:671` does the same for `/include/HUD_script/*`.
6. **The compiled twin has the palette baked in.** Decompiling
   `data/objects/gui/hud_new/materials.xmb` (patch.bundle @26296080, 55,798 B): its
   299-string table contains the literal resolved values `0.9 0.67 0.25`, `0 0.09 0.09`,
   `0.008 0.24 0.25`, `0.015 0.494 0.501`, `0.024 0.76 0.773`, … — every `<HUD>` value
   from `hud_palett_2.xml` — and contains **no `@A`, `@B1`, `@D1` …** references at all
   (1 unresolved `@`-string total, `@C1`, out of 299).

**An unresolved tension, stated honestly.** `materials.xml` and `materials.xmb` are *both*
in `patch.bundle`, so by the tie-goes-to-compiled rule the `.xmb` should win — and then the
baked palette would be frozen and `Settings\hud_palett_2.xml` would be inert, which would
mean GRIN's final patch shipped a documented, player-facing, permanently dead file. Two
readings, and I cannot separate them without running the game:

- **GUESS (favoured).** The trailing include list is a *runtime* staleness check. The
  GRAW2 helper at `VA:0073D3A0` strips either `".xml"` or `".xmb"` and returns
  `max(mtime(.xml), mtime(.xmb))` — exactly the primitive you need to ask "is any
  declared include newer than this compiled file?". If `hud_palett_2.xml` (loose, 2022)
  is newer than the bundled `materials.xmb`, the loader falls back to `materials.xml` and
  re-resolves the include. This makes the feature work and explains why the list is
  stored at all.
- **Alternative.** The list is only a build-dependency record for
  `bundler compile-xml -m/--only-if-modified`, and the palette feature is simply broken
  in the shipped patch.

Either way the practical guidance above is unchanged. Flagged in Open questions.

A second, smaller instance of the same pattern: the bundle holds
`settings/hud_visibility.xmb` (683 B, patch.bundle) with **no `.xml` twin in the bundle**,
while disk holds `Settings\hud_visibility.xml` (1,952 B, plain, heavily commented, listing
every HUD element and its alpha). Head to head, loose `.xml` vs bundled `.xmb`, and the
loose one is the one GRIN documents for the player.

### Evidence 1 — GRIN's own mod pipeline never produces a compiled XML, so `.xml`-only bundles are the supported path (GRAW2)

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

### Evidence 2 — a live worked example of the timestamp rule (GRAW1)

**Correction to an earlier read of mine:** this is a **disk-vs-disk** comparison, not
disk-vs-bundle. `defaults.xml.bin` is *also* loose on disk, and `settings/defaults.xml`
is **not an indexed entry in either bundle** — verified: zero bundle keys start with
`settings/`, and the raw strings `graw_profile_default` / `ghost_recon_defaults` occur in
`quick.bundle` only inside `temp_merged_log.xml` and
`data/lib/managers/profilemanager.dxe`. So this proves the `CompareFileTime` arbitration
cleanly, and proves nothing about disk-vs-bundle. Do not over-claim it (I did, first time).

`D:\...GRAW\Settings\` holds both forms of the same file:

| file | mtime | content |
|---|---|---|
| `defaults.xml` | 2025-03-02 00:03:40 | `<profile active="/settings/profiles/graw_profile_bragme"/>` |
| `defaults.xml.bin` | 2006-04-15 01:53:44 | `<profile active="/settings/profiles/graw_profile_default"/>` |

(`.bin` content is from decompiling it with `xmlbin.py` this session.)

`Settings\profiles\` contains **exactly one** profile directory, `graw_profile_bragme`,
and it is demonstrably live:

| file | size | mtime |
|---|---|---|
| `profile.xml` | 3,823 | 2026-06-27 05:31:43 |
| `savegame_1.dsl` | 131,180 | 2025-03-10 12:20:22 |
| `savegame_2.dsl` | 169,839 | 2025-03-10 12:25:12 |
| `screenshot_1..3.tga` | 8,294,418 each | 2026-06-27 05:59–06:01 |

`profile.xml` opens `<ghost_recon_3_profile name="BRAGme">` — the name matches the
directory, and the engine has rewritten it as recently as 2026-06-27. There is **no**
`graw_profile_default` directory. The only file on the whole disk naming
`graw_profile_bragme` is `defaults.xml`.
**The engine resolved the profile from the `.xml` and ignored the 19-year-old `.bin`** —
which is `CompareFileTime` taking the `jl` branch, exactly as disassembled.

And the engine trace confirms the same file is on the `.xml` path: `temp_merged_log.xml`
records `<open path="settings\defaults.xml"/>` — plain `.xml`, one of only 13 in 9,508
opens.

Supporting: `Settings\ctrl_set_def.xml` (2006-06-08, 3891 B) is two months **newer**
than `ctrl_set_def.xml.bin` (2006-04-15, 2626 B), and their decompiled trees differ.

### Evidence 3 — two assets ship compiled-only, which is the "source absent" branch (GRAW1)

Two `.xml.bin` files in GRAW1 have **no `.xml` twin at all**:

- `data/objects/beings/ghost_lead/ghost_lead.xml.bin` (quick.bundle @106836968, 18329 B)
- `data/objects/beings/mex_mp/mex_mp.xml.bin`

`ghost_lead` is the **player model**. `data/units/beings/u_player.xml:7`, `:81`, `:100`,
`:153`, `:170`, `:222` all say `<model file="/beings/ghost_lead/ghost_lead.xml"/>`;
`u_multiplayer.xml:8,:65` and `u_ghost.xml:12,:60` too. `mex_mp` is the MP enemy body
(`u_multiplayer.xml:83,:140`). The game obviously renders both. Since the requested
`.xml` does not exist, the loader must have fallen through to `<path>.bin`.

This is the `006CF8B1 je 006CF930` branch — compiled exists, source does not, open the
compiled file. It is also the one case a tool must handle specially: **a tool that only
rewrites `.xml` files inside the bundle will silently miss the player and MP-enemy
models**, because there is no `.xml` there to rewrite. The fix is either to write a new
loose `data\objects\beings\ghost_lead\ghost_lead.xml` (a present-day mtime beats the
bundled 2006 `.bin`) or to rewrite `ghost_lead.xml.bin` itself with `xmlbin.py`.

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

Both turned out to be in the loader function analysed above (GRAW1 `VA:006CF720`, GRAW2
`VA:00745B90`). Worth recording because it was the clue that sent me to disassemble
rather than keep stacking circumstantial evidence: no log or diagnostic string like
"using compiled version" exists in either binary, so string scanning alone could never
have settled this.

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

Registration mechanics, for completeness: `0x00731440` is the VFS mount registration —
it assigns an incrementing id at `[0x00BC9370]` and appends the record via `0x0072F730`,
a plain `std::vector` `push_back` (element size `0x28`) into the container at `VFS+0x24`.
The filesystem setup function is `0x005D46F0`; it constructs and registers **two**
`DiskFileSystem`s (ctor `0x00408880` at `005D4D24` and `005D4DFB`, each followed by
`call 0x00731440` at `005D4D70` / `005D4E62`) and references `init_game` at `005D4E95`.

Remaining gap: the candidate **emission direction** out of `0x0072EA20` (a path-keyed
`std::map` find at `0x722480` plus a longest-prefix walk over the `0x28`-byte records)
was not reversed, so the disk-vs-bundle *ordering* is not settled statically. The
empirical evidence below stands on its own. See Open questions for the one experiment
that would close it.

Note also that the disk-vs-bundle ordering matters less than it looks, because the
`CompareFileTime` arbitration described in the previous section runs **across the merged
view**: a loose `.xml` with a present-day mtime beats a bundled compiled file regardless
of mount rank.

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

**You do not need `bundler.exe` to write a mod bundle.** I wrote `bndlw.py` (scratchpad)
this session and verified it two ways with the independent reader:
- synthetic 5-file mod bundle + 1 tombstone → all payloads byte-identical on read-back;
- re-packed 40 real `data/settings/*` files out of GRAW2's bundles into a fresh
  434,741-byte bundle → 40/40 entries, **0 byte mismatches**.

One format detail the writer has to get right: the real bundles emit a trailing `0x03`
(pop) at depth 0 after the last record rather than an explicit `0x00` terminator, and
`index_end` points just past it. A reader that pops unconditionally will underflow on
every stock bundle.

Caveat: `bundler.exe compile-scripts` is still required if the mod contains `.dsf`
scripts, because `.dxe` is a compiled format I have not decoded.

Custom levels are a separate path: bundle into `<install>\custom_levels\`, and
**"custom levels are not allowed to have override files in them"** — every file inside
a custom-level bundle must be unique to it. Mods may override; custom levels may not.

**A bundle can delete as well as override.** A zero-length entry is a tombstone. GRAW2's
`patch.bundle` uses exactly three (`settings/hud_palett.xml`, `settings/hud_palett.xmb`,
`settings/hud_palett_dev.tga`), and `bundler extract` documents the semantics:
`-d, --allow_delete   If specified, bundle remove files and directories will be removed
from target!`. So a mod bundle can suppress a stock file, not only replace it.

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

Exact whole-string test on `GRAW-standalone.exe` — all four are **ABSENT**:
`"mods"`, `"-mod"`, `"mod_bundle"`, `".svn"`. GRAW2 has all four
(`0x005DC5C8`, `0x005DC5D0`, `0x005DCA04`, `0x005DC5F4`) plus the context.xml key
`filesystem` (`0x005DC9F8`). **State it flatly: GRAW1 has no mod-bundle system; GRAW2
added it.**

(Correcting an earlier over-read of mine: `"bundles"` and `"patch"` *do* exist in GRAW1,
at `0x00567BAC` and `0x00568504` — they are just not part of a mod cluster. So do
`"custom_levels"` (`0x005498F4`) and `"*.bundle"` (`0x00549904`). GRAW1's only override
routes are the loose disk tree and `custom_levels\*.bundle`.)

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
folder. GRAW1 keeps its profiles in the install folder instead:
`<install>\Settings\profiles\<name>\profile.xml`, with the active one named by
`<install>\Settings\defaults.xml`. A tool must handle both locations.

GRAW1 `profile.xml` is plain, unencrypted, per-user, and has no compiled twin — the
easiest write target in either game. Levers read from
`Settings\profiles\graw_profile_bragme\profile.xml` this session:

| element | stock value here | effect | confidence |
|---|---|---|---|
| `<difficulty value>` | `normal` | campaign difficulty | HIGH |
| `<ret_color value>` | `29 137 151` | crosshair colour — note this is *exactly* `@base_color` `#1D8997` | HIGH |
| `<mouse_sens value>` | `0.40000001` | mouse sensitivity | HIGH |
| `<mouse_sens_gui value>` | `1` | menu cursor speed | HIGH |
| `<invert_mouse value>` | `false` | | HIGH |
| `<auto_reload value>` | `true` | | HIGH |
| `<zoom_toggle value>` | `true` | ADS hold vs toggle | HIGH |
| `<sticky_peek value>` | `true` | lean hold vs toggle | HIGH |
| `<classic_crosshair value>` | `false` | | HIGH |
| `<show_markers value>` | `true` | HUD markers | HIGH |
| `<network_speed value>` | `512` | | HIGH |
| `<volume_music>` / `<volume_sfx>` | `-8` / `-8` | dB | HIGH |
| `<campaign_last_event value>` | `7361766567616d65` | hex ASCII for `"savegame"` | HIGH |

The whole `<controller_config><buttons>` block is here too, in the same
`<button id="..." binding="..." device="keyboard|mouse"/>` form as
`Settings\ctrl_set_def.xml` (the defaults template).

### How the data is layered

Values live in **three tiers**, and knowing which tier a number is in tells you whether
you can edit it:

1. **`data/sb_templates/sb_*.xml`** — the *schema with defaults* for every
   `<stats block="...">`. This is where inherited defaults live; nothing else declares
   block defaults. A `<stats block="base_data"/>` with no children means "use these".
2. **`data/units/**/u_*.xml`** — per-unit overrides, `<var name= value=>`.
3. **`data/lib/**/*.dxe`** — compiled bytecode. **The per-difficulty numbers live only
   here** (recovered below anyway).

**Units are centimetres.** `u_ghost` mover `size="50 50 160"` = a 160 cm human;
`materials.xml` clip plane `15000` = 150 m.

**Every value below is in a bundle, so the compiled-twin rule at the top of this dossier
applies:** editing the bundled `.xml` in place will not take. Write the value as a loose
`.xml` on disk (GRAW1), or into an `.xml`-only mod bundle (GRAW2), or rewrite the
compiled twin with `xmlbin.py`. The exceptions — files that are already loose and plain,
and so are safe to edit directly — are GRAW1's `Settings\profiles\<name>\profile.xml`,
`Settings\ctrl_set_def.xml`, `Settings\default_mp_weapon_kits.xml`, and GRAW2's
`Settings\hud_visibility.xml` and `Settings\hud_palett_2.xml`, plus `context.xml` in both.

### Weapons

Defaults: `data/sb_templates/sb_weapon_data.xml(.bin)` / `sb_weapon_data.xmb`, ~180 vars.

| name | game | file | attribute | stock | effect | conf |
|---|---|---|---|---|---|---|
| clip_max | both | `sb_weapon_data` | `var clip_max` | 20 | magazine default | HIGH |
| damage | both | `sb_weapon_data` | `var damage` | 1 | | HIGH |
| spread_normal / spread_zoom | both | `sb_weapon_data` | | 1.0 / 0.05 | hip / ADS cone | HIGH |
| recoil_normal / recoil_zoom | both | `sb_weapon_data` | | 0.05 / 1.0 | | HIGH |
| zoom_fov / zoom_fov_speed | both | `sb_weapon_data` | | 40 / 6 | **the ADS FOV lever** | HIGH |
| fire_rate_semi/auto/burst | both | `sb_weapon_data` | | 0.1 | seconds between shots | HIGH |
| weapon_max_range / gun_range | both | `sb_weapon_data` | | 15000 / 12000 | 150 m / 120 m | HIGH |
| ai_precision / ai_reload_delay | both | `sb_weapon_data` | | 1 / 3 | | HIGH |
| max_penetration / penetration_chance | GRAW2 | `sb_weapon_data.xmb` | | 10 / 2 | | HIGH |
| is_shotgun / num_pellets_shotgun / spread_shotgun | GRAW2 | `sb_weapon_data.xmb` | | false / 5 / 5 | | HIGH |
| spread_*_no_tripod / recoil_*_no_tripod | GRAW2 | `sb_weapon_data.xmb` | | 2.0 | bipod penalty | HIGH |

**Blunt: there is no bullet-speed or ballistics lever in either game.** No `velocity`,
`gravity` or `drop` var exists in `sb_weapon_data`. The `velocity="870 m/s"` in
`weapon_data.xml` is a display string for the shop screen.

GRAW1 representative weapons (`data/units/weapons/u_*.xml.bin`, patch.bundle, block
`weapon_data`):

| var | scar_light AR | mp5sd SMG | barrett sniper | saw LMG | beretta pistol |
|---|---|---|---|---|---|
| ammo_type | 556 | 9mm | 127 | 556_saw | 9mm |
| clip_max | 30 | 30 | 1 | 180 | 16 |
| **damage** | 2 | 1 | **10** | 2 | 1 |
| spread_normal / zoom | 1.87 / 0.35 | 2.5 / 1.0 | 8.0 / 0.05 | 1.85 / 0.92 | 2.8 / 0.7 |
| recoil_normal / zoom | 0.4 / 0.8 | 0.25 / 0.5 | 1.5 / 1.5 | 0.1 / 0.3 | 0.45 / 0.8 |
| fire_rate_semi / auto | 0.140 / 0.0833 | 0.110 / 0.075 | 0.1 / 0.0833 | 0.1 / 0.080 | 0.100 / 0.100 |
| fire_modes / burst_count | 2 / 3 | 3 / 3 | 1 / 1 | 4 / 3 | 1 / 3 |
| weapon_min / max_range | 1000 / 25000 | 0 / 3500 | 1000 / 15000 | 500 / 15000 | -1600 / 2200 |
| ai_precision | 1.0 | 1.4 | 0.05 | 1.30 | 1.2 |
| stability / weight | 0.8 / 2 | 1 / 1 | 1 / 3 | 0.5 / 3 | 1 / 0.5 |
| fire_sound / suppressed | 1.3 / 1.2 | 0.35 / 0.35 | 5 / 5 | 1.4 / 1.4 | 1.2 / 0.3 |

**GRAW1 ships no shotgun** — `is_shotgun` does not exist in its schema.

GRAW2 (`data/units/weapons/u_*.xmb`):

| var | m416 AR | mp5a4 SMG | msg90 sniper | m240 LMG | glock | m1014 shotgun |
|---|---|---|---|---|---|---|
| clip_max | 30 | 30 | 20 | 100 | 19 | 7 |
| **damage** | 1.4 | 1.2 | 1.85 | 1.75 | 1 | 0.8 |
| spread_normal / zoom | 1.5 / **0.1** | 1.5 / 0.55 | 1.5 / **0.001** | 2.5 / 1.25 | 3.5 / 2.0 | 1 / 0.08 |
| recoil_normal / zoom | 1.0 / 0.3 | 0.5 / 0.25 | **3.5** / 1.0 | 0.9 / 0.4 | 0.55 / 0.3 | 2.0 / 0.8 |
| ai_precision | 1 | 1.4 | 0.08 | 1.45 | 1.5 | 1 |

**Cross-game headline:** GRAW1 damage is integer (1/2/3/10), GRAW2 fractional
(1.2/1.4/1.85). GRAW2 tightened zoom spread ~3.5× (0.35 → 0.1) and roughly doubled recoil.

**Ammo pools differ structurally.** GRAW1 `sb_inventory_data.xml.bin`:
`ammo_max_556=10`, `ammo_max_556_saw=4`, `ammo_max_9mm=4`, `ammo_max_762=10`,
`ammo_max_127=20`, `ammo_max_40mm=4` (+ an MP set `ammo_max_multi_556=6` etc.).
**GRAW2 removed every `ammo_max_*` var** (0 hits game-wide) in favour of per-weapon
`<stats clips= max_clips=>` in `data/lib/managers/xml/weapon_data.xmb` — m416
`capacity=30 clips=5 max_clips=12`, barrett `1/20/20`, m240 `100/5/10`.

**Scope zoom** — `data/units/weapons/u_addons.xml.bin` / `.xmb`, block `addon_data`:

| scope | fov_zoomed | sway_amp | zoom_mouse_sensitivity |
|---|---|---|---|
| `sniper_scope` | **5** | 0.05 | 0.1 |
| `aimpoint` | 25 | 0.1 | 0.2 |
| `m8_/crye_combatsight` | 35 | 0.1 | 0.2 |
| ironsights | 40 | 0.1 | 0.3 |

**Gotcha:** in GRAW1 the shop `damage` in `data/lib/managers/xml/weapon_data.xml`
disagrees with the unit `weapon_data/damage` for three weapons — barrett 7 vs **10**,
crye 1 vs **2**, m8_compact 1 vs **2**. GRAW2's agree exactly. GUESS: the unit var is
what `BulletWeapon` reads and the shop value only drives the store screen.

**Dead ends, stated plainly:** `data/gui/weapons.xml` and `data/gui/weapon_list.xml` are
**pure HUD/menu presentation — zero gameplay tunables**. `mod_data.xml` carries only
`price` and cosmetic `<bar_stats>`; the real attachment effects are in `u_addons`.
`Settings\weapon_ids.txt` (GRAW1) is a plain-text documentation list, no values.
`Settings\default_mp_weapon_kits.xml` (GRAW1) defines 4 MP kits. **GRAW2 has neither
loose file** — they moved into the bundles.

### Player and AI health

**The var is `damage_points`, not `hitpoints`** — which is why searching for "hitpoints"
comes up empty. Block `damage_data`, defaults in `sb_damage_data.xml`
(`damage_points=2`, `damage_points_max=2`, `god_mode=false`).

| value | GRAW1 who | GRAW2 who |
|---|---|---|
| 2.75 | — | mex_mercenary, mex_sf_heavy/light |
| 3 | — | MP ghost_domination_player; all husks |
| **4** | **every enemy** (all 16 mex_* variants) | loyalist, us_marines, us_tank_crew |
| **5** | — | **`teammate_*_player` = the player** |
| 6 | MP ghost/mex_domination | — |
| **7** | **`ghost_player` = the player** (`u_player.xml:43`) | — |
| 8 | blackhawk pilots, mex_president, us_general | new_pilot |
| 16 | husks, `ghost` | — |
| **24** | AI teammates (`u_teammates.xml:70`) | AI teammates |

Player : enemy ratio — GRAW1 7/4 = 1.75, GRAW2 5/2.75 = 1.82.

**Correction to the `macro_common.xml` find.** In
`data/units/beings/macro_common.xml` only `player_hitpoints_domination` (=6) is actually
consumed, by `u_multiplayer.xml`. **`player_hitpoints_campaign` (5) and
`ai_teammates_hitpoints` (24) are defined but referenced by nothing** — checked against
all 5,674 GRAW1 `.xml`. The live campaign value is the literal `7` in `u_player.xml`;
teammates are the literal `24` in `u_teammates.xml`. Editing the macros does nothing.
**GRAW2 has no `macro_common.xml` and no `u_player.xml`** — its player unit is
`teammate_mitchell_player` in `u_teammates.xmb`.

### AI skill, accuracy and difficulty

`ghost_ai_data/skill_shooting` is set in two places and **the `group_manager.xml`
soldier template wins** (applied per-soldier at spawn):

| | GRAW1 | GRAW2 |
|---|---|---|
| unit-level `u_mex_*` | mex_inf 1.0, mex_gue 1.1, mex_sf 1.9 | mex_sf 1.8, mercenary 1.0, loyalist 1.8 |
| **soldier template** | 1.2 ×11, 1.0 ×11, 0.85 ×11, 0.30 ×1 | **2.5 ×124**, 2.0 ×8 |
| ghost / teammates | ghost 0.5, teammates 1 | teammates 1 |

**GRAW2 enemies ship at `skill_shooting=2.5` against GRAW1's 0.85–1.2 — roughly double.**

**GRAW2-only `acc_*` hit-chance system** (165 occurrences; GRAW1 has **0**), block
`human_data`. GUESS on semantics: the chance an AI shooting *at this unit* connects, and
how long it must track first — i.e. the player's effective armour. The single most
impactful GRAW2 difficulty lever that is plain XML:

| var | schema default | on the player unit |
|---|---|---|
| `acc_chance_to_hit_near` | 0.9 | **0.3** |
| `acc_chance_to_hit_far` | 0.7 | **0.2** |
| `acc_min_time_to_acc_near` / `_far` | 0.3 / 0.7 | 1 / 2 |
| `acc_min_time_between_hits` | 0.0 | 2 |
| `acc_hit_chance_cover_mod` / `_time_cover_mod` | 0.5 / 2 | 0.5 / 2 |

**Global difficulty** — `data/sb_templates/global/sb_global.xml(.bin)` / `.xmb`.
Common to both: `level_difficulty=1.0`, `overall_enemy_precision=1.0`,
`overall_friendly_precision=0.8`, `overall_enemy_tactical_difficulty=0.2`,
`overall_friendly_tactical_difficulty=0.6`, `weapon_recoil=0.6`,
`weapon_noice=1.3` / `weapon_noice_silenced=0.30`, `tac_cover_bonus=0.3`.
GRAW1-only: `player_precision=1.0`, `player_precision_zoomed=0.8`.
GRAW2-only: the `difficulty_chance_to_hit_*` / `difficulty_time_to_hit_*` family (1.0 each)
and `mounted_burst_length=10`.

**But these `sb_global` values are only declared defaults — the real per-difficulty
numbers are written over them from `.dxe` at profile load**, and were recovered from the
bytecode. Both files have four blocks: `hardcore`, `hard`, `easy`, and an unlabelled
else-branch = **normal**.

`data/lib/utils/profileutils.dxe` (GRAW2, 7,307 B):

| constant | hardcore | hard | normal | easy |
|---|---|---|---|---|
| `difficulty_chance_to_hit_near_player` | 0.99 | 0.9 | 0.75 | 0.55 |
| `difficulty_chance_to_hit_far_player` | 0.9 | 0.7 | 0.4 | 0.3 |
| `difficulty_time_to_hit_near_player` | 0.0 | 0.0 | 0.2 | 0.5 |
| `difficulty_time_to_hit_far_player` | 0.0 | 0.75 | 2.0 | 3.0 |
| `difficulty_time_between_hits_player` | 0.5 | 1.5 | 2.0 | 2.0 |
| `difficulty_chance_to_hit_near_teammates` | 0.7 | 0.45 | 0.35 | 0.3 |
| `difficulty_chance_to_hit_far_teammates` | 0.6 | 0.35 | 0.25 | 0.15 |
| `overall_enemy_precision` | 0.6 | 0.6 | 1.0 | 1.0 |
| `overall_enemy_tactical_difficulty` | 0.3 | 0.3 | 0.4 | 0.4 |
| `player_health_multiplier` | 1.0 | 1.0 | 1.0 | 1.0 |

`data/lib/managers/profilemanager.dxe` (GRAW1, 19,087 B) — **no chance/time-to-hit table
exists; that system is GRAW2-only**:

| constant | hardcore | hard | normal | easy |
|---|---|---|---|---|
| `overall_enemy_precision` | 0.3 | 0.6 | 1.0 | 1.0 |
| `overall_enemy_tactical_difficulty` | 0.2 | 0.3 | 0.4 | 0.4 |
| `overall_friendly_tactical_difficulty` | 1.0 | 0.5 | 0.5 | 0.5 |
| `player_health_multiplier` | 1.0 | 1.0 | 1.0 | **1.5** |

GRAW1's easy block branches on `multiplayer_settings.game_mode == "MPCoop"` and writes
`player_health_multiplier = 3.0` for co-op vs `1.5` for single-player easy (raw bytes at
`0x2e47` / `0x2e6f`).

**Difficulty changes AI accuracy and player health. It does not change enemy counts.**

**Detection / vision / hearing** — `sb_global`, both games (centimetres):

| var | GRAW1 | GRAW2 |
|---|---|---|
| `ad_distance_sight` | 15000 | 15000 |
| `ad_view_cone_inner / _outer / _outer_combat_bonus` | 30 / **90** / 10 | 30 / **50** / 50 |
| `ad_distance_hear_weapon_ls / _nls` | **15000 / 6000** | **8000 / 4000** |
| `ad_auto_detect_distance` | 250 | 300 |
| `ga_detection_inc_speed / _dec_speed` | 0.3 / 0.04 | 0.2 / 0.08 |
| `det_see_zone1..4` | — | 800 / 2500 / 5000 / 14000 |
| `det_hear_zone1..4` | — | 500 / 2000 / 4000 / 14000 |
| `det_see_cone_zone1 / _zone234` | — | 110 / 45 |
| `det_player_sprint_mul / _prone_sprint_mul / _stand_mul` | — | 1.0 / 0.4 / 0.5 |
| `det_memory_see / det_memory_hear` | — | 10 / 5 |
| `det_smoke_spread_mul` | — | 8 |

(GRAW2 duplicates the whole `det_*` block as `*_ghosts` for the player team.)

**Things with the word but no tunables — blunt:** `data/units/ai/` **does not exist** in
either game (AI logic is `.dxe` under `data/lib/units/ai/`). `actor_manager*.xml` is
cutscene/radio dialogue sequencing only. `cover_manager.xml` is level-geometry metadata.
Most of `sb_ai_data.xml` is runtime scratch state (`current_state`, `last_shot_at_time`).
**No `armor`/`armour`/`vision`/`hearing` var exists in either game's XML**, and "morale"
exists only as GRAW2's `xp_morale`.

### Enemy counts and spawns

**Enemy counts are 100% editable XML. Nothing about them is compiled into a `.dxe`** —
subject only to the compiled-twin rule at the top of this dossier.

Placement lives in `data/levels/<name>/xml/world.xml` → `<human>`, and every entry is a
**squad, not a man**:
```xml
<unit name="group_unit" group="mex_guerilla_rpg" group_id="rpg01" crew="false">
  <order order="Sniper" patrol_type="moveguard_recon" .../>
  <position pos_x="-14707.789" pos_y="22192.504" pos_z="850"/>
</unit>
```
`group=` names a template in `data/lib/managers/xml/group_manager.xml`. A numeric suffix
(`mex_guerilla_patrol2`) is generated at load: `GroupManager:parse_groups` expands a
`split="true"` group of N into sub-groups 1..N, sub-group K being the roster resized to K.
That resolves every group name in every world file in both games with zero unresolved
(GRAW1: 80 distinct, GRAW2: 71).

**So: enemy count = (group_unit placements in `world.xml`) × (soldiers per group in
`group_manager.xml`). Both are plain XML.**

- GRAW1 `group_manager.xml.bin`: 66 groups, 81 soldier templates. `mex_guerilla_patrol` = 4.
- GRAW2 `group_manager.xmb` (patch.bundle): 63 groups, **406 soldier templates**.
  `mex_special_forces_patrol` = **8**. Soldier templates also carry `xp_*` skills,
  `has_explosive=1` (228 of them), `bomb_planting_time`, `tag_type`, `tag_radius`.
- **GRAW2 ships `data/lib/managers/xml/extra_groups.xml` containing literally
  `<extra_groups/><extra_soldiers/>` — an empty, uncompiled modding extension point.**
- Enemy vs friendly: GRAW2 groups carry `side="1"` / `side="2"`; **GRAW1's have no `side`
  attribute** — classify by the `mex_*` prefix.

Campaign enemy-soldier totals (groups / enemy groups / enemy soldiers):

| GRAW1 | | GRAW2 | |
|---|---|---|---|
| m01 | 35 / 27 / **45** | m01 | 35 / 34 / **46** |
| m02 | 123 / 112 / **199** | m02 | 48 / 41 / 48 |
| m03 | 61 / 55 / 112 | m03 | 63 / 55 / 78 |
| m04 | 82 / 73 / 94 | m04 | 137 / 121 / **155** |
| m05 | 60 / 53 / 97 | m05 | 51 / 44 / 118 |
| m06 | 76 / 68 / 112 | m06 | 51 / 41 / 79 |
| m08 | 96 / 85 / 112 | m07 | 45 / 40 / 53 |
| m09 | 83 / 78 / 102 | m08 | 59 / 55 / 124 |
| m10 | 70 / 60 / 105 | m09 | 92 / 90 / 112 |
| m11 | 38 / 33 / 56 | m10 | 107 / 98 / 123 |
| m12 | 72 / 62 / 107 | ogr_dam | 118 / 118 / **194** |

**All GRAW1 `dm*` / `tdm*` / `hh*` / `mp0*` levels: 0 — MP worlds place no humans at all.**

**There are no enemy waves or reinforcements.** Enemies are placed, then *activated* —
never created. Mission-script census: GRAW1 `ActivateGroup` 922 / `RemoveGroup` 477;
GRAW2 544 / 248 plus `ActivateRandomGroup` 111 (picks one of several **already-placed**
groups). `AlterGroupStats` (GRAW2, 169 uses) tweaks placed groups at runtime, e.g.
`<element type="AlterGroupStats" group_id="insert_crew" max_health="5000" health="5000"/>`.
`CreateUnit` (60 uses) spawns props, weapons and vehicles, never soldiers.
`AllowSpawn` / `ForceSpawn` / `GiveLife` are **player** respawn and live in
`data/levels/common/{coop,dm,tdm,hh,s,rvsa}_rules.xml`, all `side="1"`.

Per-level settings: GRAW2 uses plain `data/levels/<name>/world_info.xml` (`mission_time`,
`<campaign>` with `<candidate>` and `<block_weapon>` lists), chaining to
`data/levels/common/campaign_settings.xml` (`has_tacmap`, `has_xcom`, `awa_distance=15000`).
**GRAW1 has no such file** — `mission_name`, `mission_camera_height=83500`, `mission_time`
and `level_difficulty` are compiled into `mission01.dxe`.

`.gph` is the binary AI navigation graph: `u32 version(=2)`, `u32 node_count`, then per
node `u8 flag, u8 link_count, float x,y,z`, then 5-byte link records. It holds the same
data as `world.xml`'s `<ai_graph>` plus auto-generated nodes (GRAW1 mission01: 1,494
`<node>` in XML vs 11,798 in `ai.gph`). **Editing enemy counts does not require touching
it.**

### `data/settings/*.xml`

| file | what it controls | notable stock values |
|---|---|---|
| `graphic_quality` | 3 presets × 21 (G1) / 24 (G2) vars, values only `high`/`medium`/`low` — **no numbers** | **GRAW2 caps `texture_quality_props_bump` at `medium` even on High** — easiest free-quality edit. GRAW1 duplicates that key inside `graphic_setting_high` (shipped bug) |
| `camera_settings` | 42 rigs; G1/G2 differ in 6 lines | `third_behind` boom `distance=250`, other `third_*` 300; `car_third` 700/height 300; `person` `sphere_cast_radius=10` |
| `physics_settings` | **G1 = Havok, G2 = PhysX** | solver globals identical (`collision_tolerance=15`, `friction=0.8`, `restitution=0.5`) but the element is `<havok>` vs `<physics>`. G1: 25 densities (`human=1010`, `iron=7300`), 16 body templates. G2: 30 templates, `foliage collides_with_ray_bodies="false"` (**foliage doesn't stop bullets**), `<pool size="400" low_size="250" high_size="1200"/>` |
| `network` | wire protocol; the `min`/`max`/`step` are hard caps | `maxplayers` ceiling **63**; `position ±400000 step=1` (±4 km at 1 cm); `condition` (health sync) `0..1 step=0.04` = **25 discrete steps**; GRAW1-only `max_ai` capped at **3** and `move_without_ack_time` — both removed in GRAW2 |
| `post_effects` | 59 presets (G1) / 32 (G2) | `default` byte-identical across games: `sepia_opacity=0.7` = **the master grade strength, set 0 for raw output**; `bright_pass=0.518`. **GRAW1's `reset` is a true identity grade** — copy it over `default` to see the game ungraded; GRAW2's is not. `grain_amount`/`grain_speed` authored everywhere and **0 in every preset** |
| `materials` | global material params | `clip_base clip_plane="0 0 -1 15000"` = **150 m world clip, the biggest draw-distance number**; `lightmap_tint=1.5 1.5 1.5`; `parallax_scale=0.035`; GRAW2 pushes the far LOD fade band 90/95 m → 150/155 m |
| `layers` | render targets | **GRAW1 hard-codes `shadow_depth width=1024 height=1024`; GRAW2 binds it to a `shadow_map_size` param**; both `particles w_scale=0.25 h_scale=0.25` (quarter-res particles) |
| `skies` (**GRAW1 only**) | 28 lighting presets × 30 children | `ambient_multiplier` 1.0–1.7; `sun_color 2.0 1.19 0.61` (HDR); `shadow_color 0.75 0.75 0.65` (shadows lifted to 75% grey); `lightmap_exposure=2.22` in 25 of 28 |
| `scenes` | 6 (G1) / 5 (G2) | the **crosscom viewport runs only `crosscom_processor`, all four other post-processors `false`** — why drone/buddy feeds look flat |
| `camera_effects` | 28 / 31 named shakes as math expressions in `t` | `headbob amplitude=20 frequency=8` |
| `instance_structs` | GPU batch sizes | `world_tm=60` down to `world_tm_ambient_cube_3_bones=10` |
| `palett` | 444 (G1) / 273 (G2) colour `xdefine` macros | a swatch library, no tunables |
| `video_texture_pool` | one line | 256×128 (G1) → **512×256** (G2) |
| `gui` | **empty in both — a single `<gui/>` tag, 32 bytes** | nothing to tune |
| `brush_frequency` (G2) | 436 rows of `min_probability` | **every value is 0** |

Byte-identical between the games: `effect_spawners`, `set_texture_scope_editor` (GRAW2
shipped GRAW1's stale copy, still naming Mexico City `city`/`ghetto` groups),
`static_texture_scope`.

### HUD visibility

**GRAW2 `Settings\hud_visibility.xml` is a direct, loose, uncompiled HUD switch list** —
a full no-HUD preset is 14 edits in one plain file with no bundle work.
`alpha` 0.0–1.0 on `health`, `health_background`, `xcom`, `compass`, `awa`, `ammo`,
`ammo_background`, `crosshair`, `narcom`, `tag_data`, `multiplayer_map` (all stock `1.0`);
`visible` true/false on `markers_enemy`, `markers_friendly`, `markers_objective`.
The file notes the narcom video-feed **audio stays on regardless** of alpha.

**GRAW1 has no equivalent** — its only toggle is all-or-nothing: `sb_global`
`show_hud=true` / `show_hud_windows=false`, plus per-unit `human_data/hud_visible`.

### Scripts: `.dsf`, `.dxe`, `.diesel`, `.dsl`

**There is no `.dsf` source anywhere** — 0 hits across all 46,408 bundle entries in both
games and 0 in the loose trees. The compiler ships (`bundler compile-scripts`), the
source does not. GRIN's own readme names `aihivebrain.dsf`, `guiscreens.dsf`,
`hudmanager.dsf`, `aidetection.dsf` — none of them are in the game.

**`.dxe` is tokenised bytecode with a fully recoverable string table.** Verified across
all 684 files: magic `DXE\0`; `u32@+4` = filesize − 16 (0 mismatches); `u32@+8` = 0
always; `u32@+12` nonzero in every GRAW1 file and zero in every GRAW2 file. Then a tagged
NUL-terminated symbol table — `01` import, `02` global/member, `03`+u32 function name +
entry offset, `04` class, `00` end. Numeric literals are inline with no constant pool
(`06 <float32>` number, `07 <cstr>` string, `2c <cstr>` field access, `23` compare,
`2b <u32>` jump-if-false, `29 <u32>` jump, `0c` store). 38,339 names + 28,088 floats were
recovered from GRAW2's 299 files and 36,636 + 26,116 from GRAW1's 385 — which is how the
difficulty tables above were obtained.

Distribution: GRAW1 (385) — `lib/units/` 208, `lib/managers/` 42, `lib/utils/` 40,
`lib/script_network/` 32, and **59 under `data/levels/` across 48 level dirs**.
GRAW2 (299) — `lib/units/` 173, `lib/managers/` 54, `lib/utils/` 35, and **essentially
none per-level** (one file, `levels/editor/editor.dxe`); GRAW2 moved per-level logic into
mission XML, which makes it the more moddable of the two in that respect.

**Correcting the brief's premise: `.diesel` files are not scripts.** All 3,135 in GRAW1
are binary model/animation containers — `data/anims/` 1,976, `data/objects/` 1,085,
`data/levels/` 66, `data/shaders/` 7. Header as read from
`data/anims/2a42/2a42_idle.diesel` (13,496 B):
```
1a 00 00 00              u32 = 26            (chunk count)
b8 11 c0 5d b0 70 d1 04  u64 type id         (constant across every .diesel sampled)
1a 00 00 00              u32 = 26
41 6e 69 6d 61 74 69 6f 6e 44 61 74 61 00    "AnimationData"
```
Printable-byte ratio 29.5%. Not text, not script.

**`.dsl` files are binary too, and unrelated.** `level_snapshot.dsl` and
`Settings\profiles\<name>\savegame_{1,2}.dsl` (GRAW1 only; GRAW2 has none) are 31–36%
printable, header `u32 version=1` then two u32s, no `DXE` magic, and ASCII extraction
yields nothing meaningful. Not Lua, not S-expressions, not any text syntax.
GUESS: bit-packed object-state serialisation (repeating 12-byte `flags + u32 name-hash +
float` records), plausibly the network-sync writer. **The extension is a coincidence of
the engine's name ("Diesel") — it is not the `.dsf`/`.dxe` language.**

### The ten highest-leverage single edits

1. GRAW2 `Settings\hud_visibility.xml` — 14 HUD switches, loose file, no repack.
2. `group_manager.xml` `<group>` soldier lists — multiplies every enemy in the game.
3. `world.xml` `<human>` `group_unit` placements — per-level enemy counts.
4. `damage_points` on the player unit — `u_player.xml` (GRAW1, 7) /
   `u_teammates.xmb` `teammate_mitchell_player` (GRAW2, 5).
5. `skill_shooting` in `group_manager.xml` soldier templates (GRAW2 = 2.5 on 124 of them).
6. GRAW2 `acc_chance_to_hit_near` / `_far` on the player unit (0.3 / 0.2).
7. `sb_global` `ad_*` / `det_*` detection ranges and cones.
8. `post_effects.xml` `default/sepia_opacity=0.7` — the game's entire colour look.
9. `layers.xml` `shadow_depth 1024×1024` and `particles w_scale/h_scale=0.25`.
10. `materials.xml` `clip_base` clip plane `15000` — the 150 m draw distance.

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

**GRAW1 — `temp_merged_log.xml`** (857,485 B, quick.bundle @2317890536) is a GRIN
developer artefact that shipped by accident: a complete recorded engine filesystem trace,
9,508 `<open path="..."/>` records from a real session. It is one of only two `.xml` files
in the bundle with no compiled twin (the other is `install.xml`), which is itself the tell
that it was never meant to be data. It is also, as it happens, the single most useful file
in either game for answering the `.xml`-vs-compiled question — see the top section. It
still names `graw_profile_default` and `settings\profiles\default\profile.xml`, i.e. the
developer's own machine state.

**GRAW2 — `data/levels/ogr_hacienda/`** (3,465,316 B, 16 files) is a complete level whose
name appears only in texture-database entries (`data/textures/gui/tdb_texture_set.xml`,
`data/textures/lightmaps/ogr_hacienda/atlas0/tdb_atlas_set.xml`, `texture_db.bin`) —
never in a menu, script or string file. Unreachable in the shipped game.

**GRAW2 — `ageia_bonus_mission`** (5,797,815 B) is the PhysX promotional bonus level; it
*is* wired up (`data/strings/ageia_bonus_mission.xml`, `data/strings/mission.xml`,
`data/settings/physics_settings.xml`), so it is unusual but not cut.

**No cut weapons in either game — negative result, checked.** Parsed every
`data/units/weapons/*.xml` for `<unit type="weapon" name="...">` (GRAW1: 28 files,
32 declared units; GRAW2: 44 files, 33 units) and searched the whole rest of each bundle
for each name. The only units with no external reference are internal variants —
`*_3rd` (third-person models) and `*_husk` (destroyed wrecks) — which are spawned by
code, not by name in data. Nothing that looks like a dropped weapon.

**GRAW1 — the bundle root is GRIN's build machine.** GRAW1's `quick.bundle` has 23
root-level entries; GRAW2's has 2 (`context-standalone.xml`, `si.bin`). The GRAW1 set is
almost entirely developer infrastructure that shipped by mistake:
`bootlog.txt` (a profiler dump: `LEVEL: levels\mp05\mp05`, `Application::start_script
1 21.0713`), `fpslog.txt`, `default_debug.pdb`, `temp_merged_log.xml`,
`lightmap_client.rb` / `lightmap_server.rb` / `lightmap_sync.rb` / `lightmap_sync.bat`,
`process_texture_list.rb`, `run_unit_tests.bat`, `unit_test`, `unit_test_report` (Ruby),
`phys_x_installation.txt`, and the three `context.xml.{editor,lightmap_server,lightmap_slave}`
variants. The batch/Ruby files contain studio-internal build-server paths, a
source-control database path and environment variables for credentials, plus an internal
email address and SMTP host in the unit-test mailer — I am not reproducing those here;
they are in the files if you need them.

**GRAW1 — a `techroom.bundle` that does not exist.** `install.xml` (184 B, bundle root)
is an install manifest whose entire body is commented out:
```xml
<install>
<!--
	<dir path="/bundles/techroom.bundle"/>
	<dir path="/data/sound"/>
	<dir path="/data/movies"/>
-->
</install>
```
No `techroom.bundle` ships. `context.xml` disables the feature outright with
`<installer use="false"/>`. `install.xml` is also one of only two `.xml` files in the
GRAW1 bundle with no compiled twin.

**Both — `data/textures/atlas_interface/menu/`** survives in GRAW2 with nothing referencing it.

**GRAW1 — 2 orphan compiled files** with no `.xml` source shipped:
`data/objects/beings/ghost_lead/ghost_lead.xml.bin` and
`data/objects/beings/mex_mp/mex_mp.xml.bin`. Not cut content — see Evidence 3 above —
but they are the only two places where the plain XML is genuinely unavailable, so a tool
that only edits `.xml` will silently fail to touch the player and MP-enemy models.

---

## Open questions

1. ~~Lookup order~~ — **CLOSED.** `CompareFileTime` arbitration, disassembled in both
   binaries, and independently confirmed by GRIN's own 9,508-record engine trace
   (`temp_merged_log.xml`): compiled wins 3,029 : 2 for in-bundle pairs. See the top
   section.
2. **Does the `xi:include` dependency list in a compiled file trigger a runtime fallback?**
   This is the one live question and it decides whether GRAW2's shipped
   `Settings\hud_palett_2.xml` actually recolours the HUD (Evidence 0). The helper at
   GRAW2 `VA:0073D3A0` returning `max(mtime(.xml), mtime(.xmb))` looks purpose-built for
   it, but I did not trace its callers to the loader.
   **Cheapest test, no debugger:** set `<bundler make_logs="true"/>` in GRAW2's
   `context.xml`, launch to the menu, and read the generated access log — if it records
   `data\objects\gui\hud_new\materials.xml` (not `.xmb`) the fallback is real. This edits
   `context.xml` inside the game folder and launches the game, so it needs your go-ahead;
   I have done neither.
3. **Disk-vs-bundle rank in the VFS mount container.** The VFS is confirmed layered and
   first-hit-wins, bundle mount order is confirmed, the registration call is located
   (`0x00731440`, `std::vector` push_back, two `DiskFileSystem`s registered at
   `0x005D46F0`), and both the retail installer (171 `.bik` + 154 `.bank`, 2006) and the
   user's texture pack (764 `.dds`, 2023) ship loose files duplicating bundle paths.
   What is *not* reversed is the candidate emission direction out of `0x0072EA20`.
   **The one experiment:** fully reverse `0x0072EA20` and record whether it emits matching
   mount records in ascending or descending mount-id order into the container that
   `0x0072EEF0` scans forward.
   Low practical impact — the `CompareFileTime` rule runs across the merged view anyway.
3. **GRAW2 loose-file override.** Untested — GRAW2 ships no loose files that collide with
   the bundle, so there is nothing to observe. GUESS: it probably works, same engine. If
   it does, GRAW2 modding gets much easier and the bundler becomes optional.
4. **Case-folding / slash normalisation** is inferred from the mixed-case installer vs
   all-lowercase bundle index, not proven.
5. **`.dxe` script constants.** Anything living in compiled script rather than XML is
   outside the reach of an XML-editing tool. See the Levers section for how far that goes.

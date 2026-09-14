# The Sum of All Fears (SLES-511.80)

Boot ELF `SLES_511.80`, 4,872,624 bytes, MIPS R5900 little-endian, PAL. `SYSTEM.CNF`
says `BOOT2 = cdrom0:\SLES_511.80;1`, `VER = 1.02`, `VMODE = PAL` — all three are
confirmed by literal strings inside the ELF itself (see below).

**Outcome up front:** this build is stripped exactly like Jungle Storm (`.symtab`
present, `sh_size = 0`) but compiled with Metrowerks like Ghost Recon — so
stripped-vs-unstripped does not track compiler choice across these three games.
Zero named functions survive. There is no DWARF. Everything below was recovered
from strings and from two purpose-built cross-reference scans (pointer-table scan
and `lui`/`addiu` immediate-pair scan), not from a symbol table. **No safe,
machine-verified immediate-word patch candidate was found this pass** — see
"Patch candidates" for why and for the concrete next probe. What *was* established
is a precise load map, a full string-driven survey with real code cross-references
for several hits, and one genuinely interesting discovery: SOAF's boot code
contains a live, byte-exact reference to `host0:ike/gr.elf` — Ghost Recon's own
boot filename — left over from a shared Red Storm ("Ike") devkit boot harness.

---

## 1. Load map

Parsed directly from the file with `struct`, no external tools.

**ELF header**

| field | value |
|---|---|
| `EI_CLASS` / `EI_DATA` | 1 (ELFCLASS32) / 1 (little-endian) |
| `e_type` / `e_machine` | 2 (EXEC) / 8 (MIPS) |
| `e_entry` | `0x0029CF68` |
| `e_phoff` / `e_phnum` / `e_phentsize` | `0x34` / 2 / 32 |
| `e_shoff` / `e_shnum` / `e_shentsize` | `0x4A5870` / 8 / 40 |
| `e_flags` | `0x20924000` |

**Program headers**

| # | type | offset | vaddr=paddr | filesz | memsz | flags | align |
|---|---|---|---|---|---|---|---|
| 0 | LOAD | `0x80` | `0x00100000` | `0x4A5780` (4,872,064) | `0x4DA600` (5,088,768) | RWX (7) | `0x80` |
| 1 | LOAD | `0x4A5800` | `0x005DA600` | `0x0` | `0x0` | RW (6) | `0x10` |

Segment 1 is a **zero-length** LOAD entry whose vaddr (`0x005DA600`) lands exactly
on segment 0's bss end (`0x00100000 + 0x4DA600`). It contributes nothing — most
likely a linker artifact/boundary marker, not a second real load.

**VA → file offset formula (this executable):**

```
file_offset = VA - 0x00100000 + 0x80
```

Same additive constant as Ghost Recon (`0x80`); Jungle Storm used `0x100`.

**BSS:** VA `0x005A5780` – `0x005DA600`, size `0x34E80` (216,704 bytes) —
`memsz − filesz` of segment 0.

**Section headers** (all 8; this is a minimal, post-link, stripped table)

| # | name | type | addr | offset | size | notes |
|---|---|---|---|---|---|---|
| 0 | *(none)* | NULL | — | — | — | |
| 1 | `.shstrtab` | STRTAB | 0 | `0x4A5800` | `0x2D` | |
| 2 | `.strtab` | STRTAB | 0 | `0x0` | `0x0` | **empty** |
| 3 | `.symtab` | SYMTAB | 0 | `0x0` | `0x0`, entsize 16 | **empty — stripped** |
| 4 | *(none)* | PROGBITS | `0x00100000` | `0x80` | `0x4A5780` | == segment 0 exactly (text+rodata+data merged) |
| 5 | *(none)* | PROGBITS | `0x005DA600` | `0x4A5800` | `0x0` | == segment 1 (empty) |
| 6 | `.comment` | PROGBITS | 0 | `0x4A582D` | `0x2B` | compiler ident, see below |
| 7 | `.reginfo` | `0x70000006` (MIPS_REGINFO) | 0 | `0x4A5858` | `0x18` | standard MIPS ABI reginfo |

**Symbol table:** `.symtab` and `.strtab` are both present as sections but
`sh_size = 0` for both — **0 symbols recovered**, same situation as Jungle Storm,
not Ghost Recon. Nothing below was found "by name"; all of it came from string
content and cross-reference scans.

**DWARF:** none. Only 8 sections total and none of them is `.debug_*`.

**Compiler:** `.comment` contains, verbatim:

```
MW MIPS C Compiler (2.4.1.01)\0PlayStation2\0
```

So SOAF is a **Metrowerks** build — the same toolchain as Ghost Recon — despite
being stripped like Jungle Storm. Compiler choice and stripped/unstripped status
are independent variables across this trio of Red Storm PS2 titles; don't assume
one predicts the other.

---

## 2. String-driven hunt

47,904 printable runs (≥4 chars, `[\x20-\x7e]`) extracted from the loadable
segment with their virtual addresses. Every VA below is machine-computed from the
formula in §1 and was re-read from the file to confirm the string, so these are
not guesses.

### Decals / bullet holes

| hits | term |
|---|---|
| 12 | `decal` |
| 5 | `bullethole` |
| 0 | `bullet_hole` |
| 1 | `impact` |
| 0 | `scorch` |
| 0 | `splat` |
| 15 | `mark` (all false positives — JPEG-decoder marker-parsing strings and one RPC-command string; **no decal/mark terminology found**) |

Interesting hits:

| VA | string |
|---|---|
| `005428B0` | `decal_type1` |
| `005428C0` | `decal_type2` |
| `005428D0` | `decal_type3` |
| `0053B34F` | `BulletHoleMax` |
| `00542910` | `bullethole` |
| `00552E12` | `bullethole` |
| `0055337A` | `bullethole` |
| `0053F190` | `DetonateOnImpact` |
| `00556130`…`00556469` | `decal_effect1/3/4/5/6/7/9/10.rsb` (asset filenames) |
| `0055649E` | `host0:P:\Ike\release\new_data\new\bulletholes_sfx.bmz` (dev asset path) |

**Re-testing the Ghost Recon negative** ("`decal_type1/2/3` have zero code
cross-references — they're data-tag names, not engine switches"): **does not hold
verbatim here.** A `lui`/`addiu` immediate-pair scan (see §3 method) found exactly
one code reference to each of `decal_type1`, `decal_type2`, `decal_type3`, all at
VA `0x0057B850`, `0x0057B88C`, `0x0057B8C8`. Disassembling that region shows a
repeating 4-instruction pattern per name: `jal 0x00119B80` (unknown, likely an
allocator/constructor), then `lui/addiu` to build the name string pointer into
`$a1`, then `jal 0x004DBD10` (unknown). The second operand each time resolves to
an **empty string** at an address that falls inside the BSS span from §1 (e.g.
`0x005AA9F8`), not a printable string — i.e. these calls are passing `(name,
&someBssSlot)`, consistent with **registering `decal_type1/2/3` as named
variables backed by storage slots**, not branching on them. So the *conclusion*
from Ghost Recon — these are not engine `if/switch` logic — still looks right in
spirit, but the specific claim "zero code cross-references" is **false for SOAF**
and should not be repeated as a cross-game fact. Functions `0x00119B80` and
`0x004DBD10` are unnamed; a real answer requires decompiling them (see §3).

`BulletHoleMax` is not called through a function — it sits as entry #17 of a flat
**51-entry, 8-byte-stride pointer table** at VA `0x005256B8`–`0x00525850`
(`{const char* name; u32 0}` per entry, second word verified zero for every
entry). The full table, in file order:

```
Lang, Gamma, DefaultMipMapping, MipMapLODBias, MouseRadiansPerPixel,
UseMouseInput, MoveShuffleThreshold, MoveNormalThreshold, MoveFastThreshold,
MouseLookReverseY, DefaultKeyMappingFilename, ShellBackgroundIndex,
HumanShadowDetail, VehicleShadowDetail, ParticleDetail, ShowDeadBodies,
CharVertexWeight, BulletHoleMax, ReticuleColorR, ReticuleColorG, ReticuleColorB,
ReticuleIFFColorR, ReticuleIFFColorG, ReticuleIFFColorB, UITextureDetail,
LevelTextureDetail, CharacterTextureDetail, EffectTextureDetail, ZBufferBits,
TreeModelDetail, CharacterModelDetail, Gameplay, RecordGame, ShowIntro,
InitialRateOfFire, AlwaysRun, IFFType, AutoReloadOn, AutoTarget, UseDefaultPlan,
ThreatIndicatorEnabled, HeartbeatAlwaysOn, PadOptions, Sensitivity,
MaxTurningSpeed, PADScheme, PADVibration, BloodOn, SurroundSound, ScreenOffsetX,
ScreenOffsetY
```

This reads as the game's **named options/profile schema** — it mixes clearly
PS2-relevant entries (`ScreenOffsetX/Y` = TV overscan, `BloodOn`, `PADVibration`,
shadow/texture-detail knobs) with PC-only-looking ones (`MouseRadiansPerPixel`,
`UseMouseInput`, `DefaultKeyMappingFilename`) that make no sense on a PS2 pad,
confirming this table is compiled in from a codebase shared across platforms
rather than authored per-SKU. No pointer anywhere in the file references the
table's own base address (`0x005256B8`) — it is walked, if it is walked at all,
via an inline `lui`/`addiu`-computed bound rather than a stored table pointer, so
the reader/loader function was not located this pass.

### Split screen

| term | hits |
|---|---|
| `splitscreen` / `split_screen` / `split` | 0 |
| `viewport` | 0 |
| `twoplayer` / `2player` | 0 |

**Clean, total negative** — nothing resembling split-screen terminology exists
anywhere in the string pool. For contrast, `Coop` (1), `\coop_avatar.toe` (1),
`Multiplayer`/`MULTIPLAYER` (2) and ` mMultiplayerGameType = ` (1) **do** exist,
so SOAF has network co-op/multiplayer but the string evidence says it does not
have local split-screen at all — a real architectural difference from Ghost Recon
and Jungle Storm, which both ship split-screen code (with the shared bug
documented in `docs/PATCHES-GHOSTRECON.md`). This is a negative worth trusting:
Ghost Recon's own split-screen accessor and dispatch functions have no string
literals either, so the absence of *code-level* split-screen support can't be
proven this way — but the absence of a single UI/config string for it (no
"Player 2", no "second controller" prompt, nothing) is still meaningful.

### Camera

| VA | string |
|---|---|
| `00551C90` | `first person camera` |
| `00551CA4` | `third person camera` |
| `00551CB8` | `cinema camera` |
| `00551CC6` | `chase camera` |
| `00551CD3` | `ghost camera` |
| `00552741` | `CameraPoint` |

**Identical five-name list to Ghost Recon**, byte-for-byte the same strings (GR
carries them at `00584320`). Strong confirmation this is the same "Ike" camera
enum/state-name table reused across titles.

### Engine class names

| term | hits |
|---|---|
| `CGraphicSystem` | 0 |
| `EffMgr` | 0 |
| `RSSimController` | 0 |
| `RSArray` | 0 |
| `RSMemoryPool` | 0 |
| `Emitter` | 0 |

All six explicitly-requested class names return **zero** hits as string literals.
That's expected for a build with no symbol table and no RTTI-name strings for
these particular classes — it says nothing about whether the classes exist in
code, only that nothing here names them in a printable string.

What *does* survive as literal `RS`-prefixed identifiers (all networking/message
related, apparently type names for a message-serialization system):

```
RSAddress, RSBool, RSChar, RSConnection, RSDouble, RSFloat, RSGameInfo,
RSGameMessage, RSGameMessageMgr, RSGameObjectMgr, RSInt, RSLong, RSPlayerInfo,
RSRunnable, RSShort, RSStr, RSUChar, RSUIStr, RSUInt, RSULong, RSUShort,
RSVoidPtr, RSVoxelControllerLink
```

So the `RS` naming convention is alive in this build, just not applied to the six
specific class names asked for.

`Ike` itself: 48 hits, all either (a) dev/asset paths —
`host0:p:/Ike/release/new_data/`, `C:\develop\ike\release`, `host0:ike/gr.elf`,
`p:\ike\release` — or (b) the `ike_fx_*` particle/effect name prefix
(`ike_fx_hit_spark`, `ike_fx_dust`, `ike_fx_fire_type2/3`, `ike_fx_smoke*`,
`ike_fx_breath`). Confirms **"Ike" is Red Storm's internal project/engine
codename** (shared with Ghost Recon), not a C++ class-name prefix as the
`RSSimController`-style guess assumed.

### Difficulty

| term | hits |
|---|---|
| `Easy` | 4 (`Easy`, `Easy`, `EASY`, `EASY`) |
| `Normal` | 4 |
| `Hard` | 4 |
| `Recruit` | 0 |
| `Veteran` | 0 |
| `Elite` | 0 |

SOAF uses a plain **3-tier Easy/Normal/Hard** difficulty (with `Difficulty` /
`DIFFICULTY` / `DIFFICULTY_SUBBOX` UI strings nearby). Ghost Recon's
Recruit/Veteran/Elite naming is **absent** — a genuine negative, not a search
miss.

### Asset extensions (loader confirmation)

| ext | hits | verdict |
|---|---|---|
| `.MIS` | 100 | real — `mission\*.mis` |
| `.ATR` | 29 | real — `actor\MP Actor Files\Platoon N\*.atr` |
| `.GTF` | 1 | real — `mission\*.gtf` |
| `.KIT` | 32 | real — `kits\*.kil`, `KitIndex`, `\data\kits`, `rifleman-01.kit` |
| `.GUN` | 6 | real — `equip\*.gun`, `GunFile`, `<gun>` |
| `.PRJ` | 3 | real — `equip\*.prj`, `chicken.prj`, `squirrel.prj` |
| `.RSB` | 60 | real — many `*.rsb` UI/texture asset names |
| `.PAK` | 4 | real — `common.pak`, `menu.pak`, `loading.pak`, `action.pak` |
| `.TOE` | 18 | real, **after filtering** — raw count was polluted by `RToe`/`LToe` (skeleton bone names); the literal `\.toe\b` search gives 12 clean hits: `avatar.toe` (x4), `Training.toe`, `\Company%d.toe`, `\Red_Avatar.toe`, `\Green_Avatar.toe`, `\Blue_Avatar.toe`, `\Gold_Avatar.toe`, `\coop_avatar.toe` |
| `.OFF` | 10 | real — `Outfits\*.off` (plus `ScreenOffsetX/Y` false positives in the raw count) |
| `.KIL` | 26 | real — `kits\*.kil`, `no_restrictions.kil` |
| `.CHA` | 68 raw, **0 real** | **false positive** — every raw hit is `std::char_traits<...>` / `std::basic_*<wchar_t, ...>` STL RTTI strings. A literal `\.cha\b` search returns **zero** — `.CHA` is not a real asset extension in this build. |
| `.POB` | 64 | real — `particle_effect*.pob` |
| `.QOB` | 5 | real — `iw_brass.qob`, `muzzle_flash.qob`, `rainsplash.qob`, `sphere_billboard.qob` |

So of the fourteen extensions in the brief, thirteen are confirmed real loaders
and **`.CHA` is a confirmed negative** (raw grep noise from C++ STL strings, not
a file type SOAF loads).

### Source tree / dev paths

| VA | string |
|---|---|
| `0054B580` | `C:\develop\ike\release` |
| `00535830`/`00535850`/`00548A40` | `host0:p:/Ike/release/new_data/` |
| `00553FA1` | `host0:p:/ike/release/uitexture/` |
| `00556009` | `p:\ike\release` |
| `0053DBC0` | `update_ps2.cpp` |
| `00553FEC` | `UITexture.cpp` |

`assert` (4 hits) are all generic format strings (`assertion "%s" failed: file
"%s", line %d`, `rpcAssert failed: %s[%d]`, `LZO assertion failed in line %u:
'%s'`) — the actual filename/line are runtime `%s`/`%d` substitutions, not baked
into the binary, so they don't reveal more of the tree than the two `.cpp` names
above.

### The `gr.elf` finding

Three boot-path strings sit together in the string pool:

| VA | string |
|---|---|
| `0053A500` | `cdrom0:\SLES_511.80;1` (matches `SYSTEM.CNF` `BOOT2` exactly) |
| `0053A520` | `host0:ike/gr.elf` |
| `0053A538` | `soaf` |
| `0053A540` | `host0:soaf/soaf.elf` |

A `lui`/`addiu` scan for the `host0:ike/gr.elf` address found it built at VA
`0x001174BC`/`0x001174C0` (two `lui`s target the same halfword, one is dead/
redundant code from instruction scheduling) and consumed at `0x001174C4`, inside
a small function at
`0x00117480`–`0x0011751C`. Disassembly of that function:

```
00117480  lui  at, 0x52
00117484  lw   v0, 18008(at)        ; global flag at VA 0x00524658
00117488  beq  v0, zero, 0x001174AC ; if flag==0, take the cdrom0: path
...
001174B0  jal  0x002BE780           ; unknown call, checks host0: availability
001174B4  addiu a1, v0, -23272      ; a1 = &"gr"   (the 2-char device tag at 0053A518)
001174B8  bne  v0, zero, 0x001174DC ; check failed -> skip to the soaf branch
001174BC  lui  v0, 0x54             ; (0x001174C0 repeats it -- scheduling)
001174C4  addiu a0, v0, -23264      ; a0 = &"host0:ike/gr.elf"
001174C8  addiu a1, zero, 14
001174CC  jal  0x002AFFA8           ; the loader
...
001174E0  jal  0x002BE780           ; same check again
001174E4  addiu a1, v0, -23240      ; a1 = &"soaf"  (then host0:soaf/soaf.elf follows)
```

Read plainly: this is a **generic "try a host-mounted devkit filesystem before
falling back to disc" boot selector**, and the fallback list it was built from
includes Ghost Recon's own `gr.elf` filename verbatim. On a retail PS2 there is
no `host0:` device, so the `beq`/`bne` checks fail closed and the code falls
through to `cdrom0:\SLES_511.80;1` — meaning items 2 and 3 are dead on real
hardware, but the presence of `gr.elf` proves SOAF's boot harness is a
copy/derivative of Ghost Recon's, sharing engineering (not just an engine
codebase) between the two titles. Functions `0x002BE780`, `0x002AFFA8` and the
flag at `0x00524658` are unnamed; not pursued further this pass since they don't
touch gameplay.

---

## 3. Patch candidates

**None found and machine-verified this pass.** Here's why, plainly: every
mechanism uncovered in §2 turned out to be **name-driven, not
immediate-constant-driven**. `BulletHoleMax` is a table *key*, not a value —
its numeric default lives behind whatever code reads the 51-entry option table,
which was not located (no pointer anywhere in the file references the table's
own base address, so the reader loop must compute its bounds via a `lui`/`addiu`
pair that a plain byte scan can't distinguish from thousands of unrelated ones).
`decal_type1/2/3` are registered as named variables backed by BSS storage slots
through two unnamed functions (`0x00119B80`, `0x004DBD10`) — again, no immediate
constant sits next to the string the way Ghost Recon's `24050014` pool-size word
did. The two remaining `bullethole` literal strings and `DetonateOnImpact` have
either zero or one code cross-reference each, none of which is a numeric
immediate load.

This is a real, structural difference from Ghost Recon/Jungle Storm, not a
failure to search hard enough: those two games hard-code tunables as MIPS
immediates next to the code that uses them, which is why the Ghost Recon doc
could hand over 4-byte stock words directly. SOAF (at least for the handful of
tunables the strings expose) routes them through a named-property system
instead, so the same trick doesn't apply — the number you'd want to patch is
sitting in memory at runtime, set by whatever parses the option table or the
registration calls, not baked into an instruction stream.

**What was established, concretely, and can be trusted:**

- The exact load map and VA→offset formula (§1) — every future SOAF address
  should be converted with `file_offset = VA - 0x00100000 + 0x80`.
- The build is Metrowerks, stripped, no DWARF — decompilation will need to work
  from signatures, the way Jungle Storm's did against Ghost Recon.
- The 51-entry named-option table at VA `0x005256B8` (§2), with `BulletHoleMax`
  as verified entry #17.
- The `decal_type1/2/3` registration call sites at VA `0x0057B850` / `0x0057B88C`
  / `0x0057B8C8`, all calling the same two unnamed functions.
- `.CHA` is confirmed not a real extension; split-screen has zero string
  footprint while co-op/multiplayer strings exist.

**The single next probe, concretely:** disassemble function `0x004DBD10`
(entered from all three `decal_type1/2/3` call sites, and likely from many more
of the option-table names too, since the calling convention — `a1` = name
string, second arg = a BSS slot address — matches a general "register named
variable" pattern rather than anything decal-specific) far enough to learn what
it does with its arguments, and check whether it or its caller also takes a
**default value** as a third argument. If it does, walking every call site to
that one function is very likely to recover the real default values for
`BulletHoleMax` and everything else in the option table in one pass, the same
way Jungle Storm's addresses were recovered by walking out from Ghost Recon
signature matches rather than a symbol table. That is real disassembly work
(Ghidra, not a byte scanner) and was not attempted here — this file only used
`struct`-level ELF parsing and two hand-rolled cross-reference scans (a raw
4-byte pointer scan and a `lui`/`addiu` immediate-pair scan), both included
below for reuse.

---

## Method notes (for reuse)

Two small, self-contained scans did all the cross-referencing above, no
disassembler dependency:

1. **Pointer scan** — for a target VA, search the loadable segment for the
   4-byte little-endian encoding of that VA. Finds anything stored as a literal
   pointer (jump tables, `{name, value}` arrays like the option table).
2. **`lui`/`addiu` scan** — for a target VA, compute the standard MIPS
   `la`-expansion `hi16`/`lo16` pair (`hi16 = ((VA>>16) + (lo16&0x8000 ? 1 : 0))
   & 0xFFFF`), then scan the segment as a stream of 32-bit words for a `lui`
   with that `hi16` whose destination register is consumed by an `addiu` with
   that `lo16` within the next ~10 instructions. Finds addresses built inline in
   code, which is how MIPS compilers normally materialize a string/global
   address — this is what found the `decal_type1/2/3` and `gr.elf` references
   that the pointer scan missed.

Neither scan understands jump tables, `$gp`-relative (`lw $reg, off($gp)`)
addressing, or delay-slot reordering beyond a flat 10-instruction lookahead, so
a "0 xrefs" result from these two scans is a real negative for *this method*,
not proof the address is never referenced — `$gp`-relative loads in particular
would be invisible to both and were not checked for.

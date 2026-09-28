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
machine-verified immediate-word patch candidate was found by *that* method** —
see "Patch candidates" for why and for the concrete next probe. **§4, added
2026-09-28, carries out that probe by a different route and recovers twelve,
all now shipping as options**: signature-matching Ghost Recon's unstripped
build into this one, which turns out to fit SOAF more closely than it fits
Jungle Storm. What *was* established
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

> **Health warning, 2026-09-28.** Everything in this section was produced with
> a version of `rsetool.strings` that emitted a run **only when a NUL
> terminated it**, silently dropping every run ending in any other byte — which
> on this engine means every `printf`-style debug string, because they end in
> `\n`. The old rule found 18,864 runs here; the corrected one finds 48,670.
> **61% of the string pool was missing**, including the whole i.Link transport
> layer (see `network.md`). The tool is fixed. Treat every "0 hits, therefore
> absent" claim below as unsafe until re-run; two have already been corrected
> in place, and the split-screen negative was re-tested and **holds**
> (`splitscreen` / `viewport` / `2player` are still 0 under the fixed scanner).

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

> **Corrected 2026-09-28 — see §5.** The string negative below is real, but the
> conclusion drawn from it ("does not have local split-screen at all") is wrong.
> The engine's split-screen state machine *is* compiled into SOAF; it is the
> game-side UI and per-player support that is absent. The caveat this section
> already records — that Ghost Recon's split-screen accessors have no string
> literals either — is exactly why, and it should have blocked the conclusion.

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
| `Recruit` | ~~0~~ **8** |
| `Veteran` | ~~0~~ **4** |
| `Elite` | ~~0~~ **7** |

SOAF uses a plain **3-tier Easy/Normal/Hard** difficulty for the `<Actor>`
flags (with `Difficulty` / `DIFFICULTY` / `DIFFICULTY_SUBBOX` UI strings
nearby).

> **Corrected 2026-09-28.** This section originally recorded 0 hits for
> Recruit/Veteran/Elite and called it "a genuine negative, not a search miss".
> It was a search miss — the scanner bug above. The real counts are 8 / 4 / 7,
> and they are the `unlocked_missions.xml` medal grid (5 ranks x {Mission,
> Firefight, Recon}), registered at `0x00527090`+. Note this was *already*
> contradicted by `knobs.md` §4, which documents `RecruitEnemyAimFactor` /
> `VeteranEnemyDelayFactor` / `EliteEnemySkillAdjustment` in `CMBTMODL.XML` —
> and those names are what `rstuning.soaf_cards()` already ships options for.
> Two documents in this folder disagreed and neither was reconciled.

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
| `.CHA` | 68 raw | ~~**0 real** — not a real asset extension~~ **WRONG, corrected 2026-09-28: `.CHA` is real — 251 files in `SOAF.IMG`** (`ICA_US_DEMOLITION.CHA`, …). The raw ELF hits genuinely *are* STL RTTI noise and the ELF never names the extension, but the conclusion drawn from that — that the file type does not exist — was never checked against the archive, which lists 251 of them. A negative about **what is on the disc** has to be tested against the disc, not against the executable's string pool. |
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

## 3. Patch candidates — the string-driven pass

> **Superseded in part, 2026-09-28.** The conclusion below ("none found") is
> correct *for the method used in this section* — string scanning plus two
> cross-reference scans — and the reasoning about name-driven registration
> still holds for the option table. But the paragraph saying there is nothing
> honest to offer was read too broadly. §4 recovers twelve patch sites by
> signature-matching Ghost Recon's unstripped build into this one, which is the
> approach this very section's "next probe" pointed at, and all twelve are now
> shipping options. Read §3 as "the strings do not hand you the numbers" and §4
> as what to do instead.

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

## 4. Signature port from Ghost Recon (2026-09-28)

This is §3's own "single next probe", answered a different way. Rather than
decompiling SOAF's registration functions to find its defaults, take the
defaults from the game that shipped its symbol table and find the *same
compiled code* here.

**Why it works.** Ghost Recon PS2 (`SLUS_206.13`) and SOAF are both Metrowerks
MW MIPS C 2.4.1.01 builds of the same Red Storm "Ike" tree. `research/code/portsig.py`
masks the fields a relocation legitimately changes — `lui` immediates, `j`/`jal`
targets — and slides the result over the target image. SOAF matches Ghost Recon
**more closely than Jungle Storm does**:

| Ghost Recon symbol | words | SOAF VA | match |
|---|---|---|---|
| `__ct__20BulletHoleManagerPS2Fv` | 23 | `0x004FD410` | 23/23 (100%) |
| `Clear__20BulletHoleManagerPS2Fv` | 18 | `0x004FD470` | 18/18 (100%) |
| `AddOneBulletHole__20BulletHoleManagerPS2F…` | 87 | `0x004FD4C0` | 87/87 (100%) |
| `Update__13BulletHolePS2Ff` | 12 | `0x004FD740` | 12/12 (100%) |
| `DisplayBullethole__13IkeEffectsMgrF…` | 120 | `0x00240430` | 98% |
| `__ct__13IkeRainEffectFv` | 45 | `0x0024E390` | 98% |
| `__ct__13IkeSnowEffectFv` | 51 | `0x0024ECD0` | 99% |
| `__ct__13RainEffectPS2Fv` | 25 | `0x004EF6B0` | 100% |
| `SetParameters__18BillboardEffectPS2F…` | 155 | `0x004EC000` | 92% |
| `ShouldIFrag__…` | 84 | `0x001A64C0` | 94% |

The constructor was checked by eye, instruction for instruction: identical to
Ghost Recon's apart from three `jal` targets. The array indexer
(`RSArray<BulletHolePS2>::operator[]`, SOAF `0x004FD990`) is byte-identical to
Ghost Recon's, giving a measured **48-byte** bullet-hole record here too.

**The twelve decal, weather and blood sites**, every stock word re-read out of `SLES_511.80`
and then confirmed a second time by applying them to a disc and reading the
patched image back through its MODE2/2352 sectors:

| SOAF VA | stock word | what |
|---|---|---|
| `0x004FD430` | `24050014` | bullet-hole ring size (20) |
| `0x004FD44C` | `24020014` | its constructor's clear-loop bound |
| `0x004FD498` | `24030014` | `Clear()`'s bound — the quick-load / restart wipe |
| `0x00240458` | `3C0341F0` | 30.0f default decal lifetime |
| `0x00240560` | `3C024000` | 2.0f short-lived surfaces |
| `0x0024050C` | `1000001B` | branch: unknown surface → no decal |
| `0x00539D4C` | `00000020` | hole vertex alpha (colour struct at `0x00539D40`) |
| `0x0024E440` | `24050FA0` | `IkeRainEffect` 4,000 drops |
| `0x0024ED9C` | `240509C4` | `IkeSnowEffect` 2,500 flakes |
| `0x004EF710` | `2405012C` | `RainEffectPS2` 300 |
| `0x004F17D0` | `24050064` | `SnowEffectPS2` 100 |
| `0x004EC0BC` | `3C023F00` | blood spray lifetime, 0.5 s |

`SuppressBehavior::ShouldIFrag` came over as a sixth option (five more words,
applied and read back the same way). Ghost Recon's copy is at `0x001BD020`; this
game's is at `0x001A64C0`, and it is **live** — one caller, at `0x001A61CC`,
which sets up its arguments identically to Ghost Recon's
(`a0` = this, `a1` = the target, `a2` = this+0x34) and tests the result with the
same `beqz`:

| SOAF VA | stock | what |
|---|---|---|
| `0x001A65C0` | `14400003` | thrower-must-be-outdoors test |
| `0x001A65F0` | `14400004` | target-must-be-outdoors test |
| `0x001A6610` | `3C024361` | minimum range, 225.0f = 15 m squared |
| `0x001A6674` | `3C0244C8` | maximum range, 1600.0f = 40 m squared |
| `0x001A66BC` | `3C023F40` | 0.75f throw roll |

Worth recording precisely because it cuts against the pattern above:
`SuppressBehavior::Process`, the behaviour that *calls* it, does **not** match
at 0.85 — Metrowerks reallocated its registers (`s1`/`s0` in Ghost Recon,
`s2`/`s1` here), which is exactly the failure mode `portsig` cannot see through.
So a "no match" on a caller says nothing about the callee, and the three float
constants being self-describing (15², 40², 0.75) is what makes these five safe
without the enclosing function. It also means how often this game reaches the
decision was not established, only what it answers.
Jungle Storm, by contrast, dropped the decision entirely and needed injected
code (`grfrag`) to get it back; SOAF kept it.

The vertex colour was found by aligning the two copies of
`BulletHolePS2::Render` (delta `0x8FA10`) and reading the pointer SOAF builds at
`0x004FD8E8`: `lui $v0, 0x54` / `addiu $v0, $v0, -0x62C0` → `0x00539D40`, holding
`{0x40, 0x40, 0x40, 0x20}`, byte-identical to Ghost Recon's at `0x0056FED0`.

**Clean negatives from this pass** — real absences, not search misses, and each
one blocks a Ghost Recon option from coming over:

* `CheckingLoadingLoop__8IkeUIMgrFb` (Ghost Recon's frame-rate cap, 94 words):
  **no candidate down to a 0.45 match ratio.** SOAF's main loop is not a
  recognisable relative of it, so the 60 FPS patch needs its own research —
  find this game's own vblank wait.
* `ShowDeadBodies__10IkeOptionsCFv` is a **2-word** function. It is not that it
  is missing; a 2-word signature cannot be matched at all. `ShowDeadBodies` is
  entry #16 of the option table in §2, so this disc likely exposes it as a
  normal game option anyway.
* `SimCamera` (`ToggleCameraView`, `SetCurrentCameraView`, `__ct__`,
  `CameraBeginScene`), `SimHuman::Update`, `HandleBloodPoolEffect`,
  `HandleBloodyHumanEffect`, `CheckLineOfSight`, `CalculateTargetPoint` and the
  total-war sites: **no match at 0.90**. These are the large, gameplay-heavy
  functions where an earlier build genuinely differs. Third-person camera,
  enemy sight and draw distance, total war and "blood always on" are therefore
  *not* ported by this pass and should not be assumed portable.
* Split screen: **not the total negative §2 called it.** See §5 — the engine's
  split-screen mode state machine *is* compiled in and matches Ghost Recon
  instruction for instruction. What is missing is everything above it.

**Reusable harness:** `research/code/portmap.py` takes every VA in Ghost
Recon's `STOCK` table, groups them by containing function, signature-matches
each function into a target image and prints the ported VA plus whether the
stock word survived (`exact`, `lui`/`jal` field differs, or `WORD DIFFERS`).

```
python research/code/portmap.py soaf [min_ratio]
```

It reports 1,023 of 3,615 Ghost Recon sites porting with the stock word intact,
but that headline number is not meaningful on its own: most of it is one large
`lzo1x_decompress_safe` region, and what matters is whether *every* site an
individual option needs ported, which is why the twelve above were picked by
hand and then verified one at a time.

---

## 5. Split screen: the engine has it, the game does not (2026-09-28)

§2 read the zero string hits as "SOAF does not have local split screen at all",
while noting in the same breath that Ghost Recon's own split-screen accessors
carry no string literals either. That caveat was the right one and it was
under-weighted. Checked properly by signature, **the engine-level state machine
is present in SOAF**:

| Ghost Recon symbol | GR VA | SOAF VA | match |
|---|---|---|---|
| `ActivateSplitScreenMode__14RSGameStateMgrFv` | `0x00131280` | `0x00363580` | 89% |
| `DeactivateSplitScreenMode__14RSGameStateMgrFv` | `0x00131160` | `0x00363460` | 89% |
| `InSplitScreenMode__14RSGameStateMgrCFv` | `0x00131D70` | `0x00364060` | (2 words; found via the flag) |
| `SplitScreenMode__11IkeRulesMgrFv` | `0x0017FD30` | `0x0014A700` | 91% |

`ActivateSplitScreenMode` was read side by side and is the same function
instruction for instruction: same prologue, the same `addiu $v0, zero, 1` /
`sb $v0` writing a flag byte into the state manager, the same
`lw $t9,($a0)` / `lw $t9,0x50($t9)` / `jalr $t9` vtable dispatch through slot
`0x50`. Three fields shifted, all consistent with an earlier build: the flag
byte is at `this+0x1ED` (Ghost Recon `+0x1E9`, so the struct grew 4 bytes) and
the message id passed is `0x4C` (Ghost Recon `0x4D`).

The flag is read from exactly one instruction in each game —
`lbu $v0, 0x1ED($a0)` at SOAF `0x00364064`, `lbu $v0, 0x1E9($a0)` at Ghost Recon
`0x00131D74` — i.e. the accessor, with everything else going through the
vtable. **Direct-caller counting therefore cannot measure how wired split screen
is in either game**, and any conclusion drawn that way is worthless. Noted
because it is an easy trap here.

A useful negative control: **Jungle Storm scores worse than SOAF on these same
signatures** (`none` below a 0.60 ratio) despite definitely having working split
screen. That inversion is not a false positive in SOAF — it is Jungle Storm
having reworked this area. It is a standing warning that a low portsig score
means "this build diverged", never "this feature is absent".

**What is missing is everything above the engine.** These are reliable, and the
first is data rather than inference:

* `MENU.IMG/SCREEN.TXT` lists the game's **entire** menu system — 19 screens:
  `GAMEINFO_MAIN_PS2`, `GAMEINFO_PS2`, `MAIN_PS2`, `OPTIONSCONTROL_PS2`,
  `OPTIONSGAME_PS2`, `OPTIONSSCREEN_PS2`, `OPTIONSSOUND_PS2`,
  `PS2_PRESS_START`, `SELECTLANGUAGE_PS2`, `SF3DMODEL_PS2`, `SFMUSIC_PS2`,
  `SFPICTURE_PS2`, `SINGLE_BRIEFING_PS2`, `SPECIALFEATURE_PS2`,
  `NEW_CAMPAIGN_PS2`, `QUICK_MISSION_PS2`, `QUICK_MISSION_PARAMETER_PS2`,
  `RESUMECAMPAIGN_PS2`, `TRAINING_PS2`. Every one is single player. There is no
  multiplayer, co-op, split-screen, lobby or soldier-chooser screen on the disc.
* `IkeRulesMgr::SplitScreenMode` ports but has **zero callers**.
* `PS2MultiplayerSplitScreenChooseSoldier` — the whole second-player soldier
  setup screen in Ghost Recon — does not match, nor do `ActionPanel::SetSplitNumber`
  or `ReticuleDisplay::ReticuleSetSplitNumber`, the per-player HUD splitters.
  Weak evidence on its own (these are large functions, see the warning above),
  but it agrees with the menu list, which is not weak.
* `ActionPanel::Rebuild` *does* match (`0x002237A0`, 94%), so the HUD class
  itself is present — it is the split-number support that is not in evidence.

**Verdict.** Split screen here would be *built*, not unlocked — but §5a
narrows that a long way: the renderer already loops over two viewports, so the
hardest part is present and the missing piece is the switch plus the game layer.
The mode switch exists and nothing reaches it; there is no menu to reach it
from, no second-player soldier setup and no per-player HUD path. For scale:
Jungle Storm *shipped* working split screen and
still needed substantial injected code (`grsquad`, per-viewport bullet holes,
hit blur, orders, handoff) to fill its gaps; SOAF would need all of that plus
the parts Jungle Storm already had, with no working reference in the same
binary to copy offsets from.

### 5a. The viewport probe, run — the renderer loops over two viewports

The question §5 left open ("can the renderer draw the world twice in a frame?")
is **answered: yes.** The probe did not need a scissor hunt. Ghost Recon's
`EffMgrPS2::Render` has a full-screen block and a per-viewport split loop and
calls `WaterRippleManagerPS2::Render` from *both* (`grsquad.py` documents this),
so the call count is the test.

| | Ghost Recon | SOAF |
|---|---|---|
| `EffMgrPS2::Render` | `0x0045E160` | `≈0x004ED338` |
| graphics-system pointer | `0x00630B40` | `0x005B2270` |
| split-screen render flag | `g_graphic_sys+0x2880` | `g_graphic_sys+0x18BC` |
| `WaterRippleManagerPS2::Render` | `0x0046B4E0`, called **2x** | `0x004FB570`, called **2x** (`0x004ED3BC`, `0x004ED4B8`) |
| `BulletHoleManagerPS2::Render` | `0x0046DC20`, called **1x** | `0x004FD620`, called **1x** (`0x004ED3C4`) |
| per-viewport draw-area setup | `0x0044EBC0`, `0x0044F090` | `0x002D25D0`, `0x002D2C40` |

SOAF's structure is Ghost Recon's:

```
004ed3a0  lui  at, 0x5b
004ed3a4  lw   v0, 0x2270(at)      ; g_graphic_sys
004ed3a8  lbu  v0, 0x18bc(v0)      ; the split-screen flag
004ed3ac  bnez v0, 0x4ed488        ; set -> take the per-viewport path
004ed3b0  move s1, zero            ;   (delay slot) viewport index = 0
...
004ed488  lui  at, 0x5b            ; <- top of the per-viewport block
004ed48c  lw   a0, 0x2270(at)
004ed490  jal  0x2d25d0            ; set THIS viewport's draw area
004ed494  move a1, s1              ;   (index)
...                                ; the effect renders, per viewport
004ed580  addiu s1, s1, 1
004ed584  slti  v0, s1, 2          ; while (i < 2)
004ed588  bnez  v0, 0x4ed488       ; back-edge
```

A genuine loop over **exactly two** viewports, each with its own draw area. The
render path is parameterised, not hard-wired — so split screen here is **not a
renderer rewrite**. Ten instructions across the renderer, camera and HUD paths
read that flag (`0x00243770`, `0x002D13C4`, `0x002D13F8`, `0x002D159C`,
`0x002D25A0`, `0x002DF100`, `0x002E0340`, `0x004ED274`, `0x004ED3A8`,
`0x004ED598`), so the awareness is spread through the engine rather than
isolated in one function.

**But nothing can turn it on.** The flag has exactly two writers in SOAF and
both store zero:

```
0025fcac  sb zero, 0x18bc(a1)
002d3448  sb zero, 0x18bc(v0)
```

Ghost Recon has four writers, one of them `RSDisplayMgr::EnableSplitScreen` at
`0x0044EBB4` — `sb $a1, 0x2880($a0)`, i.e. the setter that can write 1. **SOAF
has no such setter.** The flag is only ever cleared. That is the single reason
the dormant machinery never runs, and it makes forcing the flag to 1 the obvious
first experiment rather than a guess.

Calibrate the optimism: Ghost Recon reads this flag at 26 sites, SOAF at 10. So
roughly 40% of the paths that Ghost Recon teaches about split screen are
present here, and the missing 60% is where a forced flag would show its seams
(HUD, reticle, sound, pad). Together with §5's menu finding — no screen to
select it from, no second-player soldier setup — the honest position is: the
engine can draw it, nothing asks it to, and the game layer above is absent.

**Tried, observed, withdrawn (2026-09-28).** A diagnostic option forced the
flag on. It was applied to a disc and **booted in PCSX2**, and the answer to
§5a's own question is: **the renderer really does split, and the two halves
show different views — not a clone of one camera.** The world drew twice, top
and bottom.

It was then removed, because working is not the same as usable:

* the HUD is laid out for one screen — the reticle sits on the boundary
  between the halves, and the name, map, weapon and ammo panels run across the
  bottom of the lower view rather than being drawn per player;
* there is no second player, pad or soldier for the second view to belong to;
* the game has no menu entry that could ever reach it (§5), so it is on
  always or not at all, menus included.

Shipping that as an option would have offered something that looks like split
screen and is not one. The addresses stay here; the switch does not.

**Do not treat this as a lead to pick back up.** The two-viewport path is this
engine's *older* split-screen implementation — the one Ghost Recon and Jungle
Storm moved on from — and building on it would be harder than the approach the
project already takes for split screen on those discs. It is recorded here
because it is genuinely present and genuinely runs, which is surprising and
would otherwise cost someone a day to rediscover, not because it is the way in.

For the record, the patch was: both initialisers rewritten to store 1, using
the spare pointer reload that follows each store:

```
0025fca8  lw    a1, 0x10(sp)        kept: a1 is the object
0025fcac  addiu at, zero, 1         was: sb zero, 0x18bc(a1)
0025fcb0  sb    at, 0x18bc(a1)      was: lw v0, 0x10(sp)
0025fcb4  sb    zero, 0x1910(a1)    was: sb zero, 0x1910(v0)   same pointer

002d3440  lw    v0, 0x3c(sp)        kept
002d3444  lui   v1, 0x3f80          kept: 1.0f, still read at 002d3458
002d3448  addiu at, zero, 1         was: sb zero, 0x18bc(v0)
002d344c  sb    at, 0x18bc(v0)      was: lw v0, 0x3c(sp)
002d3450  sw    zero, 0x18c0(v0)    unchanged, v0 still the object
```

`$at` is unused in both windows, no field loses its initialisation
(`+0x1910` and `+0x18C0` are still zeroed), and the register each rewrite drops
is reloaded by the next field's own `lw` before it is read again. Both are
patched because which initialiser runs last was not established; since the flag
has no other writer, it is 1 from startup onwards either way.

**Answered by the boot:** the second viewport draws a *different* view, so a
second camera exists in this build and is positioned somewhere of its own. The
renderer and the camera are therefore both further along than the string
evidence in §2 suggested; what is absent is the game and UI layer above them.

**A side finding worth keeping:** SOAF has Ghost Recon's split-screen
bullet-hole gap too — holes render only in the full-screen block. If split
screen is ever reached, `grsquad`'s fix ports directly: hook the ripple call at
`0x004ED4B8` and have the cave also call `0x004FD620` with
`lw a0, 0x2a3c(s0)` (bullet holes sit at manager slot `+0x2A3C`, ripples at
`+0x2A38`).

**Method warning, paid for here.** `portsig` put
`BulletHoleManagerPS2::Render` at `0x004FC0F0` with a **98%** match. That was a
false positive — a different effect manager's render, called from manager slot
`+0x2A40`. The real one is `0x004FD620`, which is where the *layout order*
(constructor, `Clear`, `AddOneBulletHole`, `Render`, `Generate`, `Update`,
`TestVisible`) predicted it. A high score on a mid-sized function is not proof;
cross-check it against the function's position in its own translation unit, or
against who calls it and with which field.

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

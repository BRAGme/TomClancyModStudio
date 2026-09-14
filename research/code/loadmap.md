# Load map — Ghost Recon PS2 & Ghost Recon Jungle Storm PS2

Everything below was measured from the retail files with a tool this session. Where
something is inferred rather than measured it says so.

Both executables are little-endian MIPS (EE, R5900) ELF32 `ET_EXEC`, `e_machine = 8`,
`e_entry = 0x00100008`, `e_flags = 0x20924000`. Both were built by the **same toolchain**:

```
.comment = "MW MIPS C Compiler (2.4.1.01)\0PlayStation2\0"
```

i.e. Metrowerks CodeWarrior for PS2, not `ee-gcc`. That matters for every later step —
see "Compiler consequences" at the bottom.

---

## 1. Ghost Recon (USA), SLUS-20613 — `SLUS_206.13`

37,453,732 bytes. **Only 5.1 MB of that is the game.** The other 32 MB is retained
debug information that was never stripped.

### Program headers (2)

| # | type | file off | file size | VA | mem size | flags |
|---|------|----------|-----------|----|----------|-------|
| 0 | PT_LOAD | `0x00000080` | `0x004ded00` (5,106,944) | `0x00100000` | `0x0054be80` (5,553,792) | RWX |
| 1 | PT_LOAD | `0x004ded80` | `0` | `0x0064be80` | `0` | RW |

So the whole loadable image is one segment:

```
VA 0x00100000 .. 0x005ded00   file-backed   (file 0x80 .. 0x4ded80)
VA 0x005ded00 .. 0x0064be80   .bss (zero fill, not in file)
VA 0x0064be80                 "heap" marker / start of the runtime heap
```

**VA <-> file conversion: `VA = file_offset + 0x00100000 - 0x80`.**

### Section headers (12) — this is where the 37 MB went

| # | name | type | file off | size | what it is |
|---|------|------|----------|------|------------|
| 1 | `.shstrtab` | STRTAB | `0x004ded80` | 85 | |
| 2 | `.strtab` | STRTAB | `0x004dede0` | 1,302,937 | symbol name strings |
| 3 | `.symtab` | SYMTAB | `0x0061cf80` | 619,552 | **38,722 symbols** |
| 4 | `main` | PROGBITS | `0x00000080` | 5,106,944 | the loadable image |
| 5 | `.relmain` | REL | `0x02230480` | 1,603,840 | 200,480 relocations |
| 6 | `heap` | PROGBITS | `0x004ded80` | 0 | |
| 7 | `.mwcats` | `0xca2e0002` | `0x0220add0` | 153,260 | Metrowerks "catalogue"; mostly `{u16 tag=2, u16 size, u32 addr}` records matching the function list, but the section is not an exact multiple of 8 so there are variable records in it. Not needed. |
| 8 | `.debug` | `0x70000005` | `0x006b43a0` | **26,845,384** | DWARF 1 |
| 9 | `.line` | `0x70000005` | `0x0204e470` | 1,821,010 | DWARF 1 line table |
| 10 | `.comment` | PROGBITS | `0x023b7d80` | 43 | compiler ident |
| 11 | `.reginfo` | MIPS_REGINFO | `0x023b7dac` | 24 | |

**Answer to "what is in the 37 MB": a full unstripped debug build.** 26.8 MB of DWARF 1
(`.debug`) + 1.8 MB of line numbers + 1.9 MB of symbol table and strings + 1.6 MB of
relocations.

### Symbol table — dumped to `symbols_gr.txt`

38,722 entries, `st_shndx = 4` (`main`) for 38,719 of them.

* 19,496 `STT_FUNC` — VA `0x001000d0` .. `0x005c865c`
* 17,386 `STT_OBJECT` — VA `0x0041a340` .. `0x0064be10` (globals, vtables, statics, BSS)
* 350 `STT_SECTION`, 1,490 `STT_NOTYPE`

Names are **Metrowerks/cfront-mangled C++** with full class names, e.g.
`AddDecal__14CDecalEffectMgrFRC9RSVector3` style. Vtables appear as `__vt__<len><Class>`.
Static-initialiser thunks are named `__sinit_<sourcefile>.cpp`, which recovers the
**complete source file list: 644 translation units** (see `symbols_gr.txt`, grep
`__sinit_`).

### `.debug` (DWARF 1) — original source tree

891 distinct absolute source paths survive in `.debug`, rooted at:

```
F:\GR_SOURCE\PS2\Ike\...       (453 paths)  — the game / UI / presentation layer
F:\GR_SOURCE\PS2\common\...    (434 paths)  — the RSE engine ("rs*" files)
D:\Program Files\Metrowerks\CodeWarrior\PS2 Support\...   (MSL runtime)
D:\USR\local\sce\EE\lib\crt0.s
```

Full list in `source_paths_gr.txt`. `.debug` also carries C++ **type and struct member**
information (class names such as `CCharacterModel` appear alongside member names), so
struct layouts are recoverable from it if a later step needs field offsets. Not parsed
in this pass.

### Region map (measured by `jr $ra` density per 4 KiB page, cross-checked against symbol addresses)

| VA range | contents |
|---|---|
| `0x00100000` – `0x0054ffff` | main `.text` — 19,150 of the 19,496 functions |
| `0x00550000` – `0x0056cfff` | read-only data, string pool starts |
| `0x0056d000` – `0x0056efff` | small code island inside the data (30 `jr $ra`) |
| `0x0056f000` – `0x005a6fff` | read-only data / string pool |
| `0x005a7000` – `0x005c865c` | second code block: the `__sinit_*` static-init thunks and late-linked objects (~344 functions) |
| `0x005c8660` – `0x005ded00` | initialised data (end of file-backed image) |
| `0x005ded00` – `0x0064be80` | `.bss` |
| `0x0064be80` – | heap |

There is no overlay mechanism in Ghost Recon PS2: two program headers, one loadable
segment, the whole game in one ELF. Confirmed — the string `MWo3` does not occur in
`SLUS_206.13` (searched, 0 hits).

---

## 2. Ghost Recon: Jungle Storm (USA), SLUS-20820 — `SLUS_208.20`

5,319,720 bytes. **Stripped**: `.symtab` and `.strtab` are present in the section table
but have `sh_size = 0` and `sh_offset = 0`. No `.debug`, no `.line`, no `.relmain`.
There are **no symbols in Jungle Storm.** This is the single biggest asymmetry between
the two targets.

### Program headers (5)

| # | file off | file size | VA | mem size | flags | what it is |
|---|----------|-----------|----|----------|-------|------------|
| 0 | `0x00000100` | `0x00512900` (5,318,912) | `0x00100000` | `0x00592700` | RWX | the boot ELF: text+data, then `.bss` to `0x00692700` |
| 1 | `0x00512a00` | `0` | `0x01e00000` | `0x00118400` (1,147,904) | RWX | zero-filled 1.1 MB region at `0x01e00000` — reserved, nothing in the file |
| 2 | `0x00512a00` | `0` | `0x00692700` | `0x000c7380` (816,000) | RWX | **overlay slot, `offline.bin`** |
| 3 | `0x00512a00` | `0` | `0x00692700` | `0x000d2000` (860,160) | RWX | **overlay slot, `online.bin`** |
| 4 | `0x00512a00` | `0` | `0x00764700` | `0` | RW | heap marker, placed after the *larger* of the two overlays |

**VA <-> file conversion for the boot ELF: `VA = file_offset + 0x00100000 - 0x100`.**

Headers 2 and 3 are two alternative uses of the same address range — that is the overlay
declaration. Their `p_memsz` values reproduce the MWo3 headers exactly (see
`mwo3.py` and section 3 below); this is what proves the load address rather than
assuming it.

### Region map (same method as GR; no symbols to cross-check against)

| VA range | contents |
|---|---|
| `0x00100000` – `0x0055bfff` | main `.text` |
| `0x0055c000` – `0x00574fff` | read-only data / string pool |
| `0x00575000` – `0x00576fff` | small code island inside the data |
| `0x00577000` – `0x005bffff` | read-only data / string pool (all the game's C strings live in `0x0057xxxx`–`0x005a0xxx`) |
| `0x005c0000` – `0x005e2000` | second code block: static-init thunks |
| `0x005e2000` – `0x00612900` | initialised data (end of file-backed image) |
| `0x00612900` – `0x00692700` | `.bss` |
| `0x00692700` – `0x00764700` | **overlay window** (one of `offline.bin` / `online.bin`) |
| `0x00764700` – | heap |
| `0x01e00000` – `0x01f18400` | reserved zero region (purpose not determined) |

The structure is the same shape as Ghost Recon's, shifted up ~48 KiB — Jungle Storm is a
later build of the same codebase, not a different engine.

---

## 3. The overlays (see `mwo3.py` for the full spec and the unpacker)

`offline.bin` (313,216 B, version 2) and `online.bin` (707,840 B, version 3) are
**uncompressed flat memory images**, Metrowerks `MWo3` containers. Load address
`0x00692700`, header included, so `VA = 0x00692700 + file_offset` for every byte.
Payload is MIPS EE code + data + a BSS request. Details and the evidence are in the
docstring of `mwo3.py`; the short version:

```
filesize == 0x40 + textSize + dataSize      (exact, both files)
0x40 + textSize + dataSize + bssSize == the matching ELF PT_LOAD p_memsz  (exact, both)
```

---

## Compiler consequences (carry these into every later step)

1. **Metrowerks, not GCC.** Register allocation, the shape of switch tables and the
   boolean-extraction idiom all differ from the GCC-built PS2 titles. The R6 3 note that
   this family extracts booleans with `dsll32`/`dsra32` pairs rather than `andi` applies
   here too — both games are MW 2.4.1.01.
2. **Capstone in `CS_MODE_MIPS32` stops dead on R5900-only opcodes** (`lq` op 0x1e,
   `sq` op 0x1f, and the 128-bit MMI group op 0x1c). Metrowerks emits `sq $ra` /
   `lq` in prologues in the Jungle Storm overlays, so a naive capstone loop silently
   truncates a function after one instruction. Use the `eedis.py` pattern from the
   R6 3 toolbox (decode op 0x1e/0x1f by hand, hand the rest to capstone).
3. Ghost Recon's symbol table gives exact function boundaries (`st_size` is populated),
   which removes all guesswork about where a function starts and ends in that binary.
   Jungle Storm has none, so every Jungle Storm address in later deliverables is
   established by string cross-reference and disassembly, not by symbol.

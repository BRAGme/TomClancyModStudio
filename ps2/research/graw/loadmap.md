# GRAW PS2 — load map of the boot ELF and the two overlays

Target: `Tom Clancy's Ghost Recon - Advanced Warfighter (USA).iso`, SLUS-21422,
ISO9660 volume id **`GR3`**. Everything below was read out of the image with
`tcps2.iso.Iso` and a hand-written ELF header parser; nothing is inferred from
file naming.

`SYSTEM.CNF` (verbatim, 57 bytes):

```
BOOT2 = cdrom0:\SLUS_214.22;1
VER = 1.00
VMODE = NTSC
```

## The "plain uncompressed ELF" claim — CONFIRMED

All three images begin `7F 45 4C 46 01 01 01 00` and parse as little-endian
32-bit ELF, `e_type = 2` (ET_EXEC), `e_machine = 8` (EM_MIPS),
`e_entry = 0x00100008`. There is no `.SOZ`-style `u32 rawSize + zlib` wrapper
(Rainbow Six 3's `SP.SOZ` has one; these do not — `zlib.decompress` is never
involved, the bytes are read straight off the disc and indexed).

| file | LBA | size on disc | SHA-1 of the extracted extent |
|---|---|---|---|
| `/SLUS_214.22` | 438 | 152,240 | `2b3d43d58f2b4962cf7ca37f0380c30ecfba8b43` |
| `/SP.IMG` | 268011 | 6,507,824 | `a79e35322e1192a9ac6883f653b1e4f5505a1bcc` |
| `/MP.IMG` | 265332 | 5,486,424 | `cf27683fc7586d66ffa032c63d8aaf95ec65cf9d` |

All three carry the same `.comment`:

```
MW MIPS C Compiler (2.4.1.01)\0PlayStation2\0
```

i.e. Metrowerks CodeWarrior for PS2 — the same toolchain that built Rainbow
Six 3 PS2, which is why its compiler idioms (`dsll32`/`dsra32` boolean
extraction, `sq`/`lq` register saves) transfer.

## Program headers

### `/SP.IMG` — single-player overlay

`e_phoff=52  e_phnum=2  e_phentsize=32`

| # | type | file offset | vaddr | filesz | memsz | flags |
|---|---|---|---|---|---|---|
| 0 | PT_LOAD | `0x00000800` | `0x00100000` | `0x00634380` | `0x006e0700` | RWX |
| 1 | PT_LOAD | `0x00634b80` | `0x007e0700` | `0` | `0` | RW |

* **VA → file offset: `off = VA - 0x000FF800`**  (equivalently `VA = off + 0x000FF800`)
* Loaded code/data: `VA 0x00100000 .. 0x00734380` (6,505,344 bytes on disc).
* BSS: `VA 0x00734380 .. 0x007E0700` (=`memsz-filesz`, 705,920 bytes, not on disc).
  Anything you see the code touch above `0x00734380` is zero-initialised
  runtime state, **not** patchable in the image.

### `/MP.IMG` — multiplayer overlay

`e_phoff=52  e_phnum=3  e_phentsize=32`

| # | type | file offset | vaddr | filesz | memsz | flags |
|---|---|---|---|---|---|---|
| 0 | PT_LOAD | `0x00000100` | `0x00100000` | `0x0053B480` | `0x00686180` | RWX |
| 1 | PT_LOAD | `0x0053B580` | `0x01DCE400` | `0` | `0x00111E00` | RWX |
| 2 | PT_LOAD | `0x0053B580` | `0x00786180` | `0` | `0` | RW |

* **VA → file offset: `off = VA - 0x000FFF00`**
* Loaded code/data: `VA 0x00100000 .. 0x0063B480` (5,485,696 bytes on disc).
* BSS #1: `VA 0x0063B480 .. 0x00786180`.
* BSS #2: a **second, detached** zero region at `VA 0x01DCE400 .. 0x01EE0200`
  (1,121,280 bytes). SP.IMG has no equivalent. Guess, not verified: the
  network/lobby scratch buffers, placed high to stay clear of the level heap.

### `/SLUS_214.22` — boot ELF

`e_phoff=52  e_phnum=2  e_phentsize=32`

| # | type | file offset | vaddr | filesz | memsz | flags |
|---|---|---|---|---|---|---|
| 0 | PT_LOAD | `0x00000080` | `0x00100000` | `0x00025080` | `0x0002D700` | RWX |
| 1 | PT_LOAD | `0x00025100` | `0x0012D700` | `0` | `0` | RW |

* **VA → file offset: `off = VA - 0x000FFF80`**
* The boot ELF and both overlays all claim `0x00100000` and entry `0x00100008`,
  so the boot ELF is a small loader stub that is *replaced in memory* by
  whichever `.IMG` overlay is loaded. Only 152 KB — it is not where gameplay
  lives, and it is not worth patching.

## Symbol tables — NONE SURVIVE

Each file has a section header table, and each declares a `.symtab`/`.strtab`
pair, but **both are `sh_offset = 0, sh_size = 0`**: the tables were stripped
and only the empty headers remain.

`/SP.IMG` sections (`e_shoff=6507504 e_shnum=8`):

| # | name | type | addr | offset | size |
|---|---|---|---|---|---|
| 0 | | NULL | 0 | 0 | 0 |
| 1 | `.shstrtab` | STRTAB | 0 | `0x634b80` | `0x2d` |
| 2 | `.strtab` | STRTAB | 0 | **0** | **0** |
| 3 | `.symtab` | SYMTAB | 0 | **0** | **0** |
| 4 | *(unnamed)* | PROGBITS | `0x00100000` | `0x800` | `0x634380` |
| 5 | *(unnamed)* | PROGBITS | `0x007e0700` | `0x634b80` | `0` |
| 6 | `.comment` | PROGBITS | 0 | `0x634bad` | `0x2b` |
| 7 | `.reginfo` | MIPS_REGINFO | 0 | `0x634bd8` | `0x18` |

`/MP.IMG` (`e_shnum=9`) and `/SLUS_214.22` (`e_shnum=8`) have the identical
shape, with `.symtab`/`.strtab` likewise empty.

## What replaces the symbol table: the Metrowerks unwind table

There is no symbol table, but the linker left a complete **function extent
table** in the loaded data: an ascending array of 12-byte records
`{ u32 funcStartVA, u32 funcByteSize, u32 saveMaskOrPtr }`.

| overlay | table VA | records | first func | last func |
|---|---|---|---|---|
| `SP.IMG` | `0x0071709C` | 9,946 | `0x001002C0` | `0x006CF930` |
| `MP.IMG` | `0x00613EA0` | 13,226 | `0x00100230` | `0x005DF350` |

Verified spot-check: the record `{0x0058E430, 0x175, 0x8002}` matches the
function whose `jr $ra` sits at `0x0058E59C` (`0x58E430 + 0x174 = 0x58E5A4`,
the instruction after the delay slot). The third word is a small register-save
mask for leaf-ish functions and a pointer into `0x0071xxxx` for larger ones.

This table is how every "which function am I in?" attribution in
`survival.md` and `patch_candidates.md` was made. It is worth keeping: for a
stripped overlay it is the next best thing to symbols.

## Practical VA↔offset cheat sheet

```python
SP_DELTA   = 0x000FF800   # SP.IMG   : off = VA - SP_DELTA
MP_DELTA   = 0x000FFF00   # MP.IMG   : off = VA - MP_DELTA
BOOT_DELTA = 0x000FFF80   # SLUS_214.22

# and on the disc:
SP_LBA, MP_LBA, BOOT_LBA = 268011, 265332, 438
disc_byte = LBA * 2048 + off
```

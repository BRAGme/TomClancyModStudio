# Porting Sum of All Fears content into Ghost Recon (PS2)

**Verdict: plausible, and better founded than any other route to multiplayer
SOAF content.** The two discs are the same engine with the same asset formats;
248 files are already byte-identical between them. The work is repacking and
one texture-version conversion, not reverse engineering.

This supersedes LAN as the thing to chase — see §4.

---

## 1. Why this came up

SOAF has co-op and multiplayer *content* (6 `MP*.MIS` maps, 13 `.GTF` game
types, `MP Actor Files`, `.KIL` kit restrictions) and no way to reach it: no
lobby screens exist as data, and its transport is i.Link, which needs two real
PS2s and a FireWire cable (`network.md`). On PCSX2 that is unreachable in
principle, not merely hard.

Ghost Recon and Jungle Storm, on the same engine, already have working split
screen and (Jungle Storm) online, and this project already patches both
heavily. So: move the content to the engine that can play it.

## 2. The formats are the same

File-type census across the two archives — **every type is shared, none is
exclusive to either disc**:

| ext | SOAF | GR | | ext | SOAF | GR |
|---|---|---|---|---|---|---|
| `.ATR` | 479 | 1193 | | `.MIS` | 23 | 46 |
| `.RSB` | 218 | 638 | | `.MAZ` | 12 | 38 |
| `.BMZ` | 331 | 307 | | `.ENV` | 12 | 39 |
| `.CHA` | 251 | 321 | | `.AOL` | 12 | 36 |
| `.KIT` | 132 | 141 | | `.MOL` | 12 | 36 |
| `.POB` | 131 | 141 | | `.POL` | 12 | 36 |
| `.QOB` | 121 | 148 | | `.SHT` | 12 | 36 |

SOAF holding exactly 12 of `.MAZ` / `.ENV` / `.AOL` / `.MOL` / `.POL` / `.SHT`
says a level is a named set of those files, one set per level, 12 levels.

**Header comparison, with Ghost Recon's files LZO-decompressed first:**

| ext | verdict |
|---|---|
| `.MAZ` | **same** — both start `f6 ff ff ff`, then per-level counts |
| `.ENV` | **same** — both plain `<EnvironmentFile` |
| `.MOL` | **same** — `04 00 00 00 01 00 00 00`, then a size |
| `.SHT` | **same** — `4a 0c 3a 40 00 00 80 3f`, then a size |
| `.MIS` | **same** — both plain `<MissionFile>\r\n\t` |
| `.QOB` | **same** — `0b 00 00 00 "BeginModel"` |
| `.CHA` | **same** — `15 00 00 00 01 00 00 00 ...` |
| `.AOL`, `.POL` | **same format** — only the leading size word differs, then `0a/09 00 00 00  08 00 00 00 "Vers..."` identically |

> **Trap worth recording.** Compared naively this table reads "everything
> differs". Ghost Recon stores most archive members LZO-compressed behind a
> 9-byte header (`u32 packed size`, `u32 chunk size` — `0x4000` throughout —
> and a byte), while `soafimg.read_file` already decompresses. The first pass
> compared SOAF's *decompressed* bytes against Ghost Recon's *raw* bytes and
> concluded the formats were incompatible. They are not. Decompress with
> `tcps2.rselzo` before comparing anything across these two discs.

## 3. They already share assets

Of 2,420 SOAF files and 4,004 Ghost Recon files, **677 share a filename and 248
are byte-for-byte identical**, including `203_ROUND.QOB`, `AKMS.QOB`,
`BEERCAN.QOB`, `ARROW.RSB`, `AT4_BLAST.POB` and the `BILLBOARD_EFFECT*.BMZ`
family. Red Storm shipped one asset library across both titles.

So a SOAF level dropped into `GR.IMG` would already find a large part of its
supporting cast present.

## 4. What the port actually requires

Known and tractable:

1. **Texture version.** SOAF ships `.RSB` **version 8**, Ghost Recon version 6;
   v8 is v6 with seven bytes inserted after the height, putting pixels at
   `+35`. The tool already decodes both (`tcps2/rsb.py`, `research/soaf/soafart.py`),
   so this is a rewrite of a header, not a decode problem.
2. **Archive record size.** SOAF uses 40-byte records, Ghost Recon 48.
   `tcps2/vokes.py` handles both already (`REC_SIZES`).
3. **Compression.** Members must go into `GR.IMG` LZO-packed with the 9-byte
   header. `tcps2/rselzo.py` has `compress` and `repack`.
4. **Registration.** The level has to be reachable — Ghost Recon's mission list
   and whatever indexes `.MAZ`/`.ENV` by name.

Not yet established, and each could sink it:

* Whether the `.MAZ` payload past the shared magic is version-compatible, or
  merely the same *shape*. Same first words is necessary, not sufficient.
* Whether SOAF levels reference shaders, materials or effect ids that Ghost
  Recon's build does not define.
* Whether Ghost Recon's level loader hard-codes its own level names.
* Whether the 429 same-named-but-differing files are benign (different content,
  same format) or represent incompatible revisions of shared assets. That
  number is worth an afternoon on its own: if `ICA_US_DEMOLITION.CHA` is
  identical but some other shared name is not, the differences tell you what
  changed between the two builds.

## 5. The first probe

Take the smallest SOAF level set, convert its `.RSB`s to v6, LZO-pack the set,
add it to a copy of `GR.IMG` under a Ghost-Recon-style name, and point one
existing Ghost Recon mission at it. If it loads at all — even to a broken or
untextured scene — the format question is answered and everything after that is
detail. If the loader rejects it, the `.MAZ` payload is where to look first.

Do this on a copy. `GR.IMG` is 1.5 GB and the tool's revert only restores what
it wrote.

## 6. The cheap adjacent win, unrelated to porting

SOAF's own `.GTF` game types are gated by a single digit:

| `LobbyCfg` | meaning | files |
|---|---|---|
| 1 | single player | `(SP) FIREFIGHT`, `(SP) LONE WOLF` |
| 2 | co-op | `(COOP) FIREFIGHT`, `(COOP) RECON` |
| 3 | solo multiplayer | `(SOLO) CATS_AND_MOUSE`, `HAMBURGER HILL`, `LAST MAN STANDING`, `SHARPSHOOTER` |
| 4 | team | `(TEAM) DOMINATION`, `HAMBURGER HILL`, `LAST MAN STANDING`, `SEARCH AND RESCUE`, `SIEGE` |

Exactly two game types carry `LobbyCfg` 1, and the shell has
`QUICK_MISSION_PS2` and `QUICK_MISSION_PARAMETER_PS2` screens — consistent with
Quick Mission listing the `LobbyCfg == 1` types. If that is the filter, rewriting
another type's digit to `1` should make it appear there: a single character,
length-preserving, exactly the kind of edit `tcps2.transforms` already does
safely.

**Untested.** It assumes the filter is `LobbyCfg` and that a co-op game type
can run with one player. Both are cheap to find out and neither risks the disc.

---

## 7. The first probe, built (2026-09-28)

Built and ready to boot; **not yet run**, so this section records method and
measurements, not an outcome.

**What was swapped.** Sum of All Fears' `TRAINING` level set replaced Ghost
Recon's `M01_CAVES` inside a copy of the Ghost Recon ISO. `M01_CAVES` was
chosen because it is the first campaign mission -- one menu selection to reach
-- and because its slots fit:

| file | GR M01_CAVES slot | SOAF TRAINING, LZO-packed | |
|---|---|---|---|
| `.MAZ` | 496,120 | 401,587 | in place |
| `.MOL` | 504,107 | 350,239 | in place |
| `.SHT` | 432,283 | 327,914 | in place |
| `.AOL` | 65,692 | 11,334 | in place |
| `.POL` | 1,019 | 2,215 | **relocated** (+1,196) |
| `.ENV` | 510 | 245 | in place |

SOAF's files are stored decompressed, Ghost Recon's LZO-packed, so each was
packed with `tcps2.rselzo.compress` first (38 s for the `.MAZ`; the whole set
is about 100 s in pure Python). Packed ratios ran 19-53%.

Only the six level-asset files were replaced. `M01_CAVES.MIS` is **untouched**,
so Ghost Recon's own mission script, actors and objectives run on top of Sum of
All Fears' geometry. That is deliberate: the question this probe asks is
whether the engine loads the level at all, and leaving the mission alone keeps
one variable in play instead of three.

**Verified after writing:** all six files read back and decompress to their
original lengths and leading bytes (`.MAZ` `f6 ff ff ff`, `.ENV`
`<EnvironmentFile`, and so on), and `GR.IMG` still lists all 4,004 files.

**Level fit across the whole disc**, for reuse: every Ghost Recon level fits
SOAF's `TRAINING` except for `.POL`, which overflows everywhere. The cheapest
targets are `M06_CASTLE` (+776 bytes), `M01_CAVES` (+1,196), `M09_SWAMP`
(+1,208) and `D03_DEPOT` (+1,212).

**What the result will mean:**

* *Loads, recognisable geometry* -- the formats are compatible and the rest is
  detail: textures, collision, spawn points, then the mission script.
* *Loads, but garbled or untextured* -- the `.MAZ` is being parsed, so the
  container is right and the difference is in what it references. Good outcome.
* *Hangs or drops back to the menu* -- the `.MAZ` payload past the shared
  header is not version-compatible after all, and §2's "same format" reading
  was too optimistic. That is where to look first.

One caveat found while preparing it: these level files reference almost nothing
by filename -- a scan turned up three references in the whole set, of which one
(`M09_BANK_SKYBOX.POB`, named in the `.ENV`) is absent from Ghost Recon. So
asset binding is by index or some other handle, and how SOAF's indices land in
Ghost Recon's tables is unknown. That is a likely source of garbling and cannot
be predicted from the outside.

The probe disc is `E:/PS2 Games/GR_SOAF_probe (throwaway).iso`, built from an
untouched copy. Nothing on the real discs was modified.

### 7a. Result: stuck at loading -- and why the probe was under-built

Booted 2026-09-28. **The mission hangs on the loading screen.** It does not
crash or fall back to the menu; it simply never finishes.

Before blaming the format, the probe itself was wrong, and the mistake is
instructive. **A level is about fourteen files, not six.** The six swapped were
the ones sharing an extension between the two discs, which is not the same
thing as the level's full set:

| | Ghost Recon `M01_CAVES` | SOAF `TRAINING` |
|---|---|---|
| swapped | `.AOL` `.ENV` `.MAZ` `.MOL` `.POL` `.SHT` | same six |
| **left mismatched** | `.BMZ` **2,153,061** | `.BMZ` **2,638,992** |
| also present, GR only | `.PAK` `.RSB` `.POB` `_GRASS.BMZ` `_SKY.BMZ` `_SKY.POZ` | -- |
| also present, SOAF only | -- | `.BMB` `.BMH` `.COZ` `.SDP` `.TOE` `.XML` |

So the disc booted Sum of All Fears' geometry against Ghost Recon's 2 MB
texture bundle, its `.PAK`, its sky and its grass. Geometry that indexes into a
bundle it was not built for is reason enough to hang, with nothing wrong with
the `.MAZ` at all.

**The `.MAZ` format is, separately, looking fine.** Compared 32 words deep,
Sum of All Fears and Ghost Recon agree on structure: magic `-10`, then a
repeating four-word record whose fourth word is always `1`, at every matching
index in both files. The container is the same; §2's reading holds for this
file at least.

**What §2 got wrong.** "Every file type is shared, none exclusive to either
disc" was drawn from the twenty-eight most common extensions. It does not hold
per level: `.BMB`, `.BMH`, `.COZ` and `.SDP` are SOAF's level packaging and
`.PAK` is Ghost Recon's. The *asset* formats match; the *level packaging* does
not, and that is the harder half.

**Next probe, if this is picked up again.** Swap the full overlapping set --
above all `.BMZ`, the texture bundle -- and find out what Ghost Recon's loader
does about the files Sum of All Fears has no counterpart for. Two things to
settle first, both static:

1. What `.BMZ` actually is in each game, and whether SOAF's packs into Ghost
   Recon's 2,153,061-byte slot at all.
2. Whether Ghost Recon's loader requires `<level>.PAK`, which Sum of All Fears
   never ships. If it does, and new entries cannot be added to `GR.IMG` (the
   writer replaces files, it does not grow the entry or name tables), then a
   level port needs a donor level whose own `.PAK` is acceptable, or the
   loader patched not to want one.

**A dead end that was tried:** reading the hung PC out of the savestate. A scan
of `PCSX2 Internal Structures.dat` for values in Ghost Recon's text range
returns page-aligned recompiler bookkeeping (`0x230000`, `0x5b0000`, ...), not
program counters, and mapping those to symbols produces confident nonsense.
Getting a real PC needs PCSX2's `cpuRegisters` layout for this build; do not
repeat the scan-and-symbolise approach.

# The Xbox containers, and how each one was settled

Everything below was cracked against the extracted discs themselves and is
exercised by `tests\run_tests.py`. Counts are from the seven games on the
reference shelf.

A theme runs through all four formats: **where a length field could be trusted
or checked, it was checked.** A size or an offset that is nearly right is worse
than one that is absent, because it parses the opening of a file convincingly
and then walks off the end of it somewhere in the middle — which is exactly what
happened twice while writing this.

---

## `.GLB` — Red Storm's glob

`tcxbox/globfile.py`. The packed form of the loose game data in Ghost Recon,
Island Thunder, Ghost Recon 2 and Summit Strike. Flat, sequential, **no index**:
the only way to find the tenth file is to walk the first nine.

```
u32 version                     2 on every glob in all four games
u32 count
[u32 dataBytes, u32 reserved]   Ghost Recon 2 and Summit Strike only
repeat count times:
    u32 nameLength              includes the terminating NUL
    u8  name[nameLength]
    u32 storedSize              bytes actually in the file
    u32 packed                  1 = LZO, 0 = stored verbatim
    u32 rawSize                 == storedSize when packed is 0
    u8  data[storedSize]
```

**The three size words are (stored, flag, raw), not (raw, flag, stored).** They
are indistinguishable on a stored entry, where both sizes are equal, and every
glob's opening entries are stored — so the wrong order reads the first dozen
files correctly and then fails in the middle of the file. The tell is a packed
entry: `ike_x_water.rsb` has 1,752 bytes on disk and 4,205 when expanded, and
reading the pair the other way round claims a compressor that expanded its
input 2.4x.

**Two header shapes**, 8 bytes and 16, and they do not follow the game: Ghost
Recon's `ikedata.glb` uses 8 and its own `xm01_caves.glb` uses 16. So `parse`
tries both and accepts the one that walks to exactly the end of the file. A
per-game table would only be the same test written twice.

**Empty globs exist.** Ghost Recon 2's `opposing_force.glb` is 16 bytes: a
header, a count of zero, nothing else.

**No decompressor is needed for anything this tool edits.** Across the 254 globs
and 20,490 entries on the shelf, the packed entries are only `.rsb`, `.sht`,
`.map` and `.xmap`. Every XML data file — `.mis`, `.atr`, `.cgs`, `.gun`,
`.wsf`, `.gtf`, `.prj`, `.itm`, `.vcl` — is stored verbatim.

**Writing is length-preserving**, because a glob has no index and every entry's
position is implied by the length of the one before it.

---

## `.UMD` — Rainbow Six 3's bundle

`tcxbox/umd.py`. This is the format that makes retail Rainbow Six 3 moddable.

From the file tree that game looks like a dead end: `System\` holds 98 cooked
`.lin` packages and exactly two ini files. `System\xboxdynamic.umd` is a 2.4 MB
bundle holding **536 files**, and among them are

* `System\R6GAMESETTINGS.ini`, 16,690 bytes — the entire gameplay tuning table,
  240 keys, the same file GRAW ships loose;
* all **115** `Template\*.tpt` terrorist templates;
* 37 more ini files, including per-map ones;
* and a **second, different** `system\RainbowSix3Xbox.ini` — 5,155 bytes against
  the loose file's 5,393.

```
[ file data, back to back, each padded to a 16-byte boundary ]
[ index: repeat { u8 nameLength (counts the NUL), name,
                  u32 offset, u32 size, u32 zero } ]
[ footer: u32 hash, u32 indexOffset, u32 fileLength, u32 2, u32 magic ]
```

**The footer's `indexOffset` lands one or two bytes before the first index
entry** — one in `xboxufiles.umd`, two in `xboxdynamic.umd`, and neither gap is
an alignment. So the index start is found by parsing: a walk is accepted only
when it lands exactly on the footer.

Writing is in place and length-preserving, even though the index carries
explicit offsets and relocation would be easy. The reason is those unexplained
slack bytes and the unidentified hash in the footer's first word: writing only
inside a slot leaves every one of them exactly as the game shipped them, and
costs nothing, because everything this tool edits is text.

---

## `.RSB` versions 8 and 9 — Red Storm bitmaps

`tcxbox/rsb.py`. Ghost Recon and Island Thunder. The PS2 decoder is no use:
those discs ship versions 4 to 6 with a palette, these ship 8 and 9 with none.

```
0x00  u32 version          8 or 9
0x04  u32 width
0x08  u32 height
0x0C  u32 ?                always 0
0x13  u8  redBits          (and 0x17 green, 0x1B blue, 0x1F alpha)
0x23  pixels
...   a fixed trailer: 66 bytes on version 8, 74 on version 9
```

**35 bytes of header, not 36.** An odd header is unusual enough to be worth the
arithmetic: `shell_bgd-01.rsb` is 1,048,685 bytes for 1024 × 512 × 2, leaving
109 for header and trailer together. It was settled by decoding rather than by
counting fields — at 36 the menu backdrop comes out sheared and at 35 it is the
game's blue HUD ring, sharp.

**The bit depths do not always describe the storage.** `main_menu-01.rsb` says
8/8/8/0 and holds 262,144 bytes for 524,288 pixels: half a byte each, which is
DXT1. So the encoding is decided by dividing the body by the pixel count. Across
the two games 0.5, 2, 3 and 4 bytes per pixel are all real.

**One loose end, recorded rather than papered over.** Island Thunder's
`main_menu-01.rsb` is the only 24-bit raster in either game, and it decodes with
its true colours one byte *earlier* than the 16- and 32-bit ones do. With a
single sample there is no way to say whether the header is a byte shorter there
or the channel order is rotated, so the code does what was observed and says so.

---

## `.XPR` — Xbox Packed Resources

`tcxbox/xpr.py`. Ghost Recon 2 and Summit Strike replaced `.RSB` with the
console's own container. It is a D3D resource written straight out of memory, so
nothing in it is a picture format in its own right.

```
0x00  'XPR0'
0x04  u32 totalSize
0x08  u32 headerSize      where the pixels begin; 0x800 in practice
0x18  u32 Format          the packed D3D format word:
                            bits  8..15  D3DFMT code
                            bits 16..19  mip levels
                            bits 20..23  log2 width
                            bits 24..27  log2 height
```

Ghost Recon 2's UI folder comes out as 52 A8R8G8B8, 16 R5G6B5, 11 DXT1 and one
DXT5. **The two uncompressed formats are swizzled** — Xbox stores an
uncompressed texture in Morton order, so a naive read gives a picture assembled
out of correctly coloured 4 × 4 tiles in the wrong places. Morton order is
separable, so the inverse is two lookup tables and one gather rather than a
per-pixel bit loop, which matters when the menu backdrop is half a million
pixels. Compressed formats are never swizzled: a DXT block is already a tile.

---

## `.XBE` — the executable, read only far enough to identify a game

`tcxbox/xbe.py`. A PE with an Xbox header on the front. The certificate carries
a 32-bit title id and a 40-character UTF-16 title name, and every pointer in the
header is a *virtual* address, so the image's base has to come off before it can
be used as a file offset.

The title id is what a profile keys on: it is the same four bytes on every copy
of a given game, it is what an emulator and the console's dashboard identify a
title by, and unlike a folder name nobody renames it.

| Title id | Name in the certificate |
| --- | --- |
| `55530005` | Ghost Recon 2 |
| `55530006` | Ghost Recon |
| `55530007` | GR Island Thunder |
| `55530013` | RainbowSix 3 |
| `55530037` | Rainbow Six White Release E:\XBox\Folder |
| `5553004D` | GR2: Summit Strike |
| `55530054` | Ghost Recon: Advanced Warfighter |

Black Arrow's prototype disc is a demo *installer*: its `default.xbe` is
Microsoft's stub with title id `FFFFFF00`, and the game sits under
`Files\Black_Arrow_XBOX_media` with its executable still called
`RainbowSix3_Release.xbe` and its title name still reading like a developer's
working folder.

---

## Where each game keeps what

| | Ghost Recon / Island Thunder | Ghost Recon 2 / Summit Strike | Rainbow Six 3 | Black Arrow proto | GRAW |
| --- | --- | --- | --- | --- | --- |
| Order of battle | `.MIS` `<Units>`, loose **and** in `ikedata.glb` | none — Igor objects only | — | — | — |
| Enemy stats | `.ATR`, only in `*_chars.glb` | in the engine | `.TPT` in the bundle | `.TPT` loose | ini |
| Weapons | `.GUN` in globs | `.GUN` in globs | — | — | `TWeapon.ini` |
| Hit model | `CMBTMODL.XML` in `ikedata.glb` | the same, **loose and packed** | `R6GameSettings.ini` | the same, loose | the same, loose |
| Rules | — | `script\*.ass`, loose | `RainbowSix3Xbox.ini` ×2 | loose | loose |
| Teammate AI | — | — | — | — | `GR3XBoxAI.ini` |

## One honest caveat on the Unreal three

`GR3XBoxAI` and `TWeapon` both appear as strings inside GRAW's cooked
`System\Common.lin`, which is the shipped build naming them as its config files.
`R6GameSettings` does **not** appear there in either game. What it does carry is
its own comment, above the gamepad block:

> All the attributes in this section can be refreshed
> in-game by opening the console and typing REFRESHGAMESETTINGS

That is the shipped build saying it reads this file at run time, which is why
the pages it drives are badged *measured* rather than *untested*. If an option
on the Enemies or Feel page does nothing while the teammate and enemy-weapon
pages work, that difference is where to look first.

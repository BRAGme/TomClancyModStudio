# Sum of All Fears (PS2, SLES-511.80) — menu artwork

**The tool can skin itself from this game.** Two textures carry everything a
shell needs and both decode cleanly:

| use | file | where | size on the page | content |
|---|---|---|---|---|
| **best background** | `MAIN_MENU_PS2.RSB` | `SOAF.IMG` | 1024×512 page, 640×480 picture | the shipped PS2 main menu — flag, two operators, and the gold wordmark already on it |
| **best logo / wordmark** | the same file, cropped | | | `THE SUM OF ALL FEARS` in gold with the ™ |

Exported PNGs are in `research/soaf/art/`. Every one of them was opened and
looked at; nothing below is inferred from a size check alone.

## The logo, and its crop box

The wordmark is not shipped on its own anywhere useful. `LOAD_ICON.RSB` is a
standalone 128×128 stacked lockup (`Tom Clancy's / The Sum of All Fears`) but it
is tiny and it is **white-on-black**, so it looks like clip art at any size a
shell would want. The usable wordmark is the wide gold one baked into the two
title screens.

Fractional crop box on the **exported** PNG (`art/MAIN_MENU_PS2.png`, 640×480),
including 8 px of breathing room:

```
left = 0.0375   top = 0.0896   right = 0.7047   bottom = 0.2208
```

which is pixels `(24, 43) .. (451, 106)`; the ink itself is `(32, 51) .. (443, 98)`.
Saved out as `art/MAIN_MENU_PS2_LOGOCROP.png` — 427×63.

`START_BG_PS2.RSB` carries the same wordmark lower down the frame, with the
Ubi Soft and Red Storm marks and a `2002 UBI SOFT ENTERTAINMENT/ RED STORM`
line underneath. Its box on `art/START_BG_PS2.png` is

```
left = 0.0375   top = 0.2333   right = 0.6813   bottom = 0.3604
```

**Bright-on-dark.** Not dark-on-dark. The glyphs run ~200–255 across the red
channel; the plate they sit on measures mean luminance 50 / median 43 out of
255. So key it the bright-on-dark way: the logo will drop onto a dark chrome
without a knockout, and it needs a dark plate, not a light one, behind it.

## Everything exported

`research/soaf/art/` — 41 PNGs. The ones worth a shell:

| file | page | picture | note |
|---|---|---|---|
| `MAIN_MENU_PS2` | 1024×512 | 640×480 | the pick |
| `START_BG_PS2` | 1024×512 | 640×480 | press-start screen, with publisher marks |
| `SHELL_BGD`, `SHELL_BGD-01`..`-05` | 1024×512 | 640×480 | six menu-page backgrounds, same flag-and-operator treatment, progressively different crops |
| `STANDARD_BG`, `MAIN_MENU`, `MAIN_MENU-01` | 1024×512 | 640×405 / 640×480 | earlier/alternate title treatments; `MAIN_MENU-01`..`-05` are the version-8 pages |
| `BRIEFING_BG`, `BRIEFING_BG_SPECIAL` | 1024×512 | 640×405 | briefing screen |
| `PDA_BGD-01` | 1024×512 | 640×480 | in-game PDA panel |
| `SHELL_BGD-PANEL` | 16×512 | 16×399 | a 16-pixel vertical strip — this is the panel chrome, tiled horizontally |
| `SOAF_COMMAND_BKGRND` | 512×128 | 480×115 | the command-bar plate |
| `DECORATIONS` | 256×256 | | medal and ribbon sheet |
| `NEWSOAF_COUNTERPARTS`, `PDA_COUNTERPARTS` | 256×256 | | button glyphs, arrows, PRESS START BUTTON |
| `PAK_new_font_revised` | 512×512 | | the whole Latin-1 font atlas, two sizes |
| `THREAT`, `MP_MISC`, `ARROW`, `CMI` | small | | reticle, A/B/C markers, cursor, control legend |
| `MUS_LOGO`, `DMG_LOGO`, `DOLBYPLII_LOGO`, `EAX_LOGO` | | | third-party marks — do not reuse these in a tool |
| `LANGUAGE_SELECT` | 256×256 | 221×255 | the six-flag language picker |

## Formats

### `.RSB` — 234 files, all 234 decode

`tcps2.rsb` takes 224 of them unchanged. It already handles versions 1 (8-bit
paletted, the bulk — 158 files), 3 (a whole JPEG, 28 files: the 25 special-
feature screenshots and three third-party logos), 4, 5 and 6.

The other ten needed new code, which is in `research/soaf/soafart.py`.

**Version 8** (8 files — `DECORATIONS`, `LOAD_ICON`, `MAIN_MENU-01`..`-05`,
`SOAF_COMMAND_BKGRND`). It is the 28-byte version-6 header with **seven extra
bytes inserted after `height`**:

```
+0   u32 version = 8
+4   u32 width
+8   u32 height
+12  7 bytes, not identified
+19  u32 rBits          <- unaligned, and that is really where they are
+23  u32 gBits
+27  u32 bBits
+31  u32 aBits
+35  pixels
end  66-byte trailer
```

`35 + width*height*bpp/8 + 66 == filesize` closes **exactly** on all eight.

The odd pixel base is the trap, and it was measured, not guessed. Rendering
`MAIN_MENU-01` at every candidate base from 28 to 43 and scoring each by mean
horizontal colour difference gave ~88 for every **even** base and ~16 for every
**odd** one: the 16-bit words genuinely begin on an odd byte. At an even base
the picture is structurally perfect and violently mis-coloured, which is exactly
the failure that looks like a working decoder if you never open the PNG.

Colour is then ordinary RGB565 with **red in the high bits** — same as
`tcps2.rsb`'s existing `(5,6,5)` branch — confirmed by the US flag in
`MAIN_MENU-01` coming out red/white/blue rather than blue/white/red. The 32-bit
version-8 files are R,G,B,A in that order (the `DECORATIONS` ribbons come out
red and bronze, not cyan), with alpha on the PS2's 0–128 scale, doubled to 0–255
on export.

**The named shape** (1 file, `LANGUAGE_SELECT.RSB`). Starts with a name instead
of a version: `u32 0`, `u32 nameLen`, the name, a NUL, then a version-8-style
header whose `version` field is 0 and whose width/height read 256×256, then
32-bit RGBA. Note `nameLen` here **excludes** the NUL, unlike the `.PAK`
records below, where it includes it — the NUL ends up being the low byte of the
`version` field. Whether that is deliberate or a happy accident is a guess.

### `.PAK` — four files, a flat chain of named texture sheets

No header, no index; records run end to end and you find the next one by
scanning:

```
u32   flags        0 = stored, 2 = compressed
u32   nameLen      includes the NUL
char  name[nameLen]
u32   0x13         constant on all 133 records in all four PAKs
u32   width
u32   height
flags == 0:  u32 0x410, u32 0x8040, u32 0x08000000, u32 0, u32 0
             then a 1024-byte B,G,R,A palette, width*height 8-bit indices,
             and a ~20-byte trailer
flags == 2:  u32 firstChunkSize, u32 0x410, then the chunk chain
```

| pak | bytes | records | stored | compressed |
|---|---|---|---|---|
| `MENU.PAK` | 5,440,497 | 64 | 2 | 62 |
| `COMMON.PAK` | 396,522 | 3 | 3 | 0 |
| `LOADING.PAK` | 1,533,646 | 19 | 0 | 19 |
| `ACTION.PAK` | 184,991 | 47 | 0 | 47 |

The stored ones decode and are exported (`PAK_*.png`), including the font atlas.

**The `flags == 2` codec is not cracked, and it does not block anything.**
What is known about it: the payload is a chain where each link is
`size` bytes of which the **last four are the size of the next link**, so
`size0` from the header plus the trailing pointers walks the chain to the record
end exactly — verified byte-exactly on `no_item` (32 + 33 = 65 payload bytes),
`no_weap` (32 + 38 = 70) and `reticle_pistol` (41 + 33 = 74). The blobs share a
seven-byte prefix `80 00 02 68 17 10 8a` across every record in every PAK. It is
**not** LZO1X and it is not the `tcps2.rselzo` framing: the first byte 0x80 would
mean a 111-byte opening literal run into a 37-byte blob.

It does not matter, because **every compressed PAK record's picture is reachable
elsewhere**. Checked mechanically: of 128 compressed records, 114 have a
same-named standalone `.RSB` in `SOAF.IMG`. The 14 that do not are
`load-circle`, `hud`, `reticle_ar/at4/car/gl/lmg/misc/pistol/sg/smg/sr`, and two
`soaf_180x160y_290w225h_ngc/_ps2` pads — all HUD furniture, none of it menu
artwork. No background, no logo, no panel chrome is behind that codec.

If someone does want the reticles: the best lever is that `no_item` and
`no_weap` exist **both** as compressed PAK records and as plain `NO_ITEM.RSB` /
`NO_WEAP.RSB`, so there is a byte-exact known-plaintext pair for a 64×32 and a
128×32 image. That is where to start, not on the big files.

### Not present

There are **no `.FBZ` files** anywhere — not in either archive and not loose on
the disc. `.FBZ` is a Rainbow Six 3 format; `tcps2.art.fbz_to_image` has nothing
to do here. The screen artwork in this game is all `.RSB` and `.PAK`.

`MENU.IMG` also carries `LOGO.TM` (1,581,056 B) and `INTRO.TM` (24,698,880 B),
both stored uncompressed, plus `LOGOUBI_PAL.PSS`, `LOGOREDSTORM_PAL.PSS`,
`INTRO_PAL.PSS` and eleven `.M2V` files. Those are MPEG video, not stills, and
were not decoded.

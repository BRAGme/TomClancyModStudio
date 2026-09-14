# GRAW PS2 — where the menu artwork is, and what is actually usable

77 PNGs were decoded into `research/graw/art/`. **I opened them and looked at
them**; everything below is what the images show, not what the filenames
promise. The per-file decode statistics (dimensions, bpp, inflate result,
entropy check) are in [art_decode_log.md](art_decode_log.md).

## The two headline answers

* **Best background: `art/GR3_2.png`** — 512×512, a dark teal-graded Mexico City
  street with a crouched Ghost on the left and most of the right-hand two thirds
  usable as empty space. It is the darkest of the three GRAW panels and the one
  with the least competing detail behind text.
  Runner-up if you want more empty space and no GRAW branding at all:
  **`art/VOKES0_DI_LE_LANG_BG.png`** — 640×480, near-black, with a subtle world
  map and angled chrome bars. It is Rainbow Six chrome, not GRAW, and it has
  "TEENS" and "MATURE" baked into the middle.

* **Best logo: crop `art/GR3_2.png`** to the fractional box
  **`(left 0.560, top 0.050, right 1.000, bottom 0.355)`** — that is
  `(286, 25) – (512, 181)` in pixels, 226×156. It yields the complete
  *Tom Clancy's / GHOST RECON / ADVANCED WARFIGHTER* lockup with the skull
  device, on a dark background with no subject bleeding into it.
  I have saved that crop for you as **`art/_LOGO_graw_wordmark.png`**.
  `GR3_2` is the right source because in `GR3_1` and `GR3_3` a soldier's helmet
  and weapon push up under the wordmark, so a crop there carries clutter.

## The decode itself works — with one real bug and one gotcha

The decoder in `tcps2/art.py` inflated all 77 files cleanly and every one
produced exactly the byte count its header's `rawSize` declares. Nothing
produced noise. Two caveats found while doing it:

1. **`art.decode_fbz` mis-decodes every 32-bpp FBZ.** The dispatch reads
   `if bpp == 24 or stride >= width*3:` *before* `if bpp == 32 or stride >=
   width*4:`. For a 32-bpp file `stride == width*4`, which is always
   `>= width*3`, so the first branch always wins and the RGBA branch is dead
   code — RGBA pixels get read as RGB triples and shear one byte per pixel.
   Affects `ACCEPT`, `LANG_AR`, `LANG_FG`, `LANG_TT`, `RETICULE`. **The fix is to
   test `bpp == 32` first.** `art.py` was not modified; those five were decoded
   with a corrected local copy, and they are correct in `art/`.
2. **The 32-bpp files use PS2 GS alpha, where `0x80` means fully opaque.**
   Measured maxima: `ACCEPT` 128, `LANG_AR` 128, `LANG_FG` 150, but `LANG_TT`
   255 and `RETICULE` 255. The PNGs carry the raw bytes, so the 0–128 ones look
   half-transparent in a normal viewer and need alpha doubled and clamped; the
   0–255 ones must be left alone. `RETICULE` looking pale green rather than white
   is this, not a colour bug.

Channel order is **RGB, not BGR** — verified on `GR3_3.png`, which shows an
uncovered face: RGB gives natural skin tone and a B/R swap gives blue skin. The
teal cast on the GRAW panels is real branding, not a swapped channel.

## What each group of files actually contains

77 files, **46 distinct images** (dedup by decoded pixel hash).

### Genuine GRAW artwork — three panels, all 512×512

| file | what I see |
|---|---|
| `GR3_1.png` | Ghost in goggles with rifle, foreground left; Chinook and a second figure receding into teal haze; cyan corner brackets framing the panel. GRAW lockup top right. |
| `GR3_2.png` | Mexico City street, burning vehicles, a crouched Ghost bottom left, wide open dark area right of centre. **The background pick.** |
| `GR3_3.png` | Three Ghosts in a diagonal stack, the front one's face uncovered and lit warm. The most "hero art" of the three. |

Each of the three has a **near-duplicate** in `VOKES0.IMG` that is
pixel-different but visually the same image:

* `VOKES0_DI_LE_LOADING_*_PAD_CFG1/2/3.png` — 15 identical copies, the `GR3_1`
  composition.
* `VOKES0_DI_LE_LOADING_*_LOADING_ASSAULT/LASTMAN/SUPREMACY.png` — 15 identical
  copies, the `GR3_3` composition.
* `VOKES0_DI_LE_LOADING_MENU_ONLINE.png` — one copy, the `GR3_2` composition.

So the disc ships the same three paintings about thirty times over for
localisation and for loading screens, and the `/CD/LE/GR3_1..3.FBZ` versions are
the ones to take.

### Not GRAW at all — shipped leftovers

* **`PAD_*.png` (5) and `MCARD_*.png` (17)** — all 512×512, all carrying a
  **Ghost Recon 2** wordmark over an olive-green soldier collage. These are the
  "controller not detected" and "insufficient memory card space" screens, reused
  from the previous game and never re-skinned. Do not use them for a GRAW tool.
* **`SC.png` / `VOKES0_DI_LE_SC.png`** — 640×448, the **Splinter Cell** 2003 legal
  screen verbatim, NSA seal and "© 2003 Ubi Soft Entertainment" and all. Present
  both loose on the disc and inside VOKES0/VOKES2.
* **`LANG_BG.png`** (the `/CD/LE/` one, 512×512) — a cracked-plaster wall with
  "STONEWALL" stencilled on it and five country flags. Nothing to do with either
  Ghost Recon or Rainbow Six.
* **`VOKES0_DI_LE_LANG_BG.png`** (640×480) — the Rainbow Six language-select
  plate: near-black, world map, angled chrome bars, the Rainbow UN emblem at the
  bottom, "TEENS" and "MATURE" in the middle. Good chrome, wrong franchise.

### UI sprites — small, useful for buttons

| file | size | contents |
|---|---|---|
| `ACCEPT.png` | 192×320 | Five circular ✕-button glyphs with the word "Accept" in five languages. |
| `LANG_TT.png` | 256×256 | Five embossed language-name plates (ENGLISH / FRANÇAIS / DEUTSCH / ITALIANO / ESPAÑOL) on white chips. |
| `VOKES0_DI_LE_LOADING_RETICULE.png` | 256×512 | A 16-cell sprite sheet of crosshair reticles, white on transparent (reads pale green until the alpha is normalised). |
| `LANG_AR.png`, `LANG_FG.png` | 64×64 | Tiny arrow / focus chips. |
| `LOADING_??_LDLG.png` | 128×64 | Five one-word "Loading" strips. |
| `ESRB_ESRB_*.png` | 512×512 | The five localised ESRB rating screens. |

## Where GRAW's *in-game* menu chrome is — and it is not FBZ

`/MENU.IMG` contains **111 files and zero images**: localisation `.INT`/`.ESP`/
`.FRA`, eight `.PSS` and five `.M2V` videos, four `.ICO`, sound banks, and three
opaque blobs — `MENU.DMG`, `MENU.DMP` (11.4 MB) and `MENU.LAZ` (5.5 MB). Every
file was tested both by extension and by an FBZ header probe; none matched.

`/VOKES2.IMG`'s 36 FBZ files are a byte-identical duplicate set of VOKES0's (all
36 SHA-1s match), so nothing new is there.

**Guess, not verified:** the real menu chrome — the panel frames, button states
and mode icons the player sees in the shell — is inside `MENU.DMP` or
`MENU.LAZ`. Neither format was investigated. If a tool wants authentic in-game
GRAW UI furniture rather than splash art, that is where to dig next.

## Practical recommendation for skinning the tool

1. Background: `art/GR3_2.png`, scaled up and darkened, or tiled behind a
   translucent panel. Its right two thirds are quiet enough to hold a form.
2. Header: `art/_LOGO_graw_wordmark.png` (the crop named above), placed top-left
   or top-centre.
3. Accent colour: the panels' own teal frame. Measured by bucketing every
   teal-leaning pixel in `GR3_2.png` (10,506 of them), the two dominant accent
   values are **`#208080`** and **`#389090`**; the dark ground behind them
   buckets to **`#141C1C`** with the deepest corners at **`#080808`**. The logo
   glow itself peaks at near-white `#C4EEED`.
4. Button glyphs: `art/ACCEPT.png` for a ✕/confirm affordance, after doubling the
   alpha channel.

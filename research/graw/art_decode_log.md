# GRAW PS2 (SLUS-21422) — FBZ art decode log

ISO: `E:\PS2 Games\Tom Clancy's Ghost Recon - Advanced Warfighter (USA).iso`  
Volume id `GR3`, 143 ISO directory entries. Read-only; nothing on E: was written.  
Output folder: `C:\Users\Tristan\Documents\GitHub\TomClancyPS2-ModStudio\research\graw\art\`

## Decoder used

`tcps2/art.py::fbz_to_image` for every 24-bpp file (verified correct).
**`art.decode_fbz` mis-decodes every 32-bpp FBZ** — see the bug note at the
bottom — so the five 32-bpp files were decoded with a corrected RGBA path and
saved as RGBA PNGs. Everything else came straight out of `art.fbz_to_image`.

## Sanity statistics

Per image, over the RGB channels: `mean`, `std` (stddev), `uniq` (distinct
colours / pixel count) and `hΔ` (mean |luma difference| between horizontally
adjacent pixels, sampled every 4th row). `hΔ` is the noise detector: real
artwork sits at 1–13, uniform random noise would sit near 85. Nothing in this
run exceeded 13 except the small alpha-masked sprites once they were decoded
correctly (their pre-fix, mis-decoded values were 50–76 — that is what the
statistic was there to catch, and it did).

## Results

| # | source | file | w×h | bpp | inflate | mean | std | uniq | hΔ | verdict | PNG |
|---|--------|------|-----|-----|---------|------|-----|------|----|---------|-----|
| 1 | ISO | `/CD/LE/ACCEPT.FBZ` | 192x320 | 32 | OK | 6.7 | 29.0 | 0.0103 | 4.64 | OK | `ACCEPT.png` |
| 2 | ISO | `/CD/LE/ESRB/ESRB_ENG.FBZ` | 512x512 | 24 | OK | 2.1 | 20.4 | 0.001 | 1.41 | OK | `ESRB_ESRB_ENG.png` |
| 3 | ISO | `/CD/LE/ESRB/ESRB_FRE.FBZ` | 512x512 | 24 | OK | 2.6 | 22.3 | 0.001 | 1.64 | OK | `ESRB_ESRB_FRE.png` |
| 4 | ISO | `/CD/LE/ESRB/ESRB_GER.FBZ` | 512x512 | 24 | OK | 3.5 | 25.8 | 0.001 | 2.27 | OK | `ESRB_ESRB_GER.png` |
| 5 | ISO | `/CD/LE/ESRB/ESRB_ITA.FBZ` | 512x512 | 24 | OK | 2.9 | 23.7 | 0.001 | 1.92 | OK | `ESRB_ESRB_ITA.png` |
| 6 | ISO | `/CD/LE/ESRB/ESRB_SPA.FBZ` | 512x512 | 24 | OK | 3.0 | 24.0 | 0.001 | 1.87 | OK | `ESRB_ESRB_SPA.png` |
| 7 | ISO | `/CD/LE/GR3_1.FBZ` | 512x512 | 24 | OK | 101.0 | 86.6 | 0.3199 | 7.24 | OK | `GR3_1.png` |
| 8 | ISO | `/CD/LE/GR3_2.FBZ` | 512x512 | 24 | OK | 79.7 | 65.9 | 0.2504 | 6.27 | OK | `GR3_2.png` |
| 9 | ISO | `/CD/LE/GR3_3.FBZ` | 512x512 | 24 | OK | 71.5 | 71.6 | 0.2324 | 6.48 | OK | `GR3_3.png` |
| 10 | ISO | `/CD/LE/LANG_AR.FBZ` | 64x64 | 32 | OK | 252.4 | 11.8 | 0.0063 | 0.37 | OK | `LANG_AR.png` |
| 11 | ISO | `/CD/LE/LANG_BG.FBZ` | 512x512 | 24 | OK | 113.6 | 46.4 | 0.0507 | 5.02 | OK | `LANG_BG.png` |
| 12 | ISO | `/CD/LE/LANG_FG.FBZ` | 64x64 | 32 | OK | 255.0 | 0.0 | 0.0002 | 0.0 | ALPHA-ONLY | `LANG_FG.png` |
| 13 | ISO | `/CD/LE/LANG_TT.FBZ` | 256x256 | 32 | OK | 56.8 | 70.3 | 0.0052 | 2.04 | OK | `LANG_TT.png` |
| 14 | ISO | `/CD/LE/LOADING/DE_LDLG.FBZ` | 128x64 | 24 | OK | 8.6 | 28.1 | 0.0038 | 5.92 | OK | `LOADING_DE_LDLG.png` |
| 15 | ISO | `/CD/LE/LOADING/EN_LDLG.FBZ` | 128x64 | 24 | OK | 5.0 | 21.6 | 0.0038 | 3.73 | OK | `LOADING_EN_LDLG.png` |
| 16 | ISO | `/CD/LE/LOADING/ES_LDLG.FBZ` | 128x64 | 24 | OK | 6.5 | 24.6 | 0.0038 | 4.54 | OK | `LOADING_ES_LDLG.png` |
| 17 | ISO | `/CD/LE/LOADING/FR_LDLG.FBZ` | 128x64 | 24 | OK | 8.0 | 27.1 | 0.0038 | 5.32 | OK | `LOADING_FR_LDLG.png` |
| 18 | ISO | `/CD/LE/LOADING/IT_LDLG.FBZ` | 128x64 | 24 | OK | 8.1 | 27.2 | 0.0038 | 5.81 | OK | `LOADING_IT_LDLG.png` |
| 19 | ISO | `/CD/LE/MCARD/1_01_ENG.FBZ` | 512x512 | 24 | OK | 52.9 | 53.8 | 0.118 | 11.83 | OK | `MCARD_1_01_ENG.png` |
| 20 | ISO | `/CD/LE/MCARD/1_01_FRE.FBZ` | 512x512 | 24 | OK | 52.9 | 54.2 | 0.1167 | 12.07 | OK | `MCARD_1_01_FRE.png` |
| 21 | ISO | `/CD/LE/MCARD/1_01_GER.FBZ` | 512x512 | 24 | OK | 53.4 | 54.9 | 0.1201 | 12.82 | OK | `MCARD_1_01_GER.png` |
| 22 | ISO | `/CD/LE/MCARD/1_01_ITA.FBZ` | 512x512 | 24 | OK | 52.9 | 54.2 | 0.1183 | 12.09 | OK | `MCARD_1_01_ITA.png` |
| 23 | ISO | `/CD/LE/MCARD/1_01_SPA.FBZ` | 512x512 | 24 | OK | 53.1 | 54.4 | 0.1198 | 12.14 | OK | `MCARD_1_01_SPA.png` |
| 24 | ISO | `/CD/LE/MCARD/1_01_USA.FBZ` | 512x512 | 24 | OK | 52.9 | 53.9 | 0.1181 | 11.84 | OK | `MCARD_1_01_USA.png` |
| 25 | ISO | `/CD/LE/MCARD/1_02_ENG.FBZ` | 512x512 | 24 | OK | 53.8 | 54.3 | 0.1266 | 11.42 | OK | `MCARD_1_02_ENG.png` |
| 26 | ISO | `/CD/LE/MCARD/1_02_FRE.FBZ` | 512x512 | 24 | OK | 53.0 | 54.6 | 0.1167 | 12.6 | OK | `MCARD_1_02_FRE.png` |
| 27 | ISO | `/CD/LE/MCARD/1_02_GER.FBZ` | 512x512 | 24 | OK | 53.4 | 54.9 | 0.12 | 12.99 | OK | `MCARD_1_02_GER.png` |
| 28 | ISO | `/CD/LE/MCARD/1_02_ITA.FBZ` | 512x512 | 24 | OK | 52.9 | 54.1 | 0.1185 | 12.13 | OK | `MCARD_1_02_ITA.png` |
| 29 | ISO | `/CD/LE/MCARD/1_02_SPA.FBZ` | 512x512 | 24 | OK | 53.1 | 54.4 | 0.1196 | 12.42 | OK | `MCARD_1_02_SPA.png` |
| 30 | ISO | `/CD/LE/MCARD/1_02_USA.FBZ` | 512x512 | 24 | OK | 53.8 | 54.3 | 0.1265 | 11.43 | OK | `MCARD_1_02_USA.png` |
| 31 | ISO | `/CD/LE/MCARD/7_02_ENG.FBZ` | 512x512 | 24 | OK | 52.4 | 51.8 | 0.1171 | 9.3 | OK | `MCARD_7_02_ENG.png` |
| 32 | ISO | `/CD/LE/MCARD/7_02_FRE.FBZ` | 512x512 | 24 | OK | 51.8 | 51.7 | 0.108 | 9.85 | OK | `MCARD_7_02_FRE.png` |
| 33 | ISO | `/CD/LE/MCARD/7_02_GER.FBZ` | 512x512 | 24 | OK | 52.0 | 52.0 | 0.1083 | 10.04 | OK | `MCARD_7_02_GER.png` |
| 34 | ISO | `/CD/LE/MCARD/7_02_ITA.FBZ` | 512x512 | 24 | OK | 51.9 | 51.8 | 0.1075 | 9.7 | OK | `MCARD_7_02_ITA.png` |
| 35 | ISO | `/CD/LE/MCARD/7_02_SPA.FBZ` | 512x512 | 24 | OK | 51.9 | 51.8 | 0.1074 | 9.59 | OK | `MCARD_7_02_SPA.png` |
| 36 | ISO | `/CD/LE/PAD_DEU.FBZ` | 512x512 | 24 | OK | 51.6 | 51.2 | 0.1067 | 9.02 | OK | `PAD_DEU.png` |
| 37 | ISO | `/CD/LE/PAD_ENG.FBZ` | 512x512 | 24 | OK | 52.4 | 51.7 | 0.1163 | 9.2 | OK | `PAD_ENG.png` |
| 38 | ISO | `/CD/LE/PAD_ESP.FBZ` | 512x512 | 24 | OK | 51.6 | 51.2 | 0.1069 | 9.1 | OK | `PAD_ESP.png` |
| 39 | ISO | `/CD/LE/PAD_FRA.FBZ` | 512x512 | 24 | OK | 51.6 | 51.3 | 0.1077 | 9.27 | OK | `PAD_FRA.png` |
| 40 | ISO | `/CD/LE/PAD_ITA.FBZ` | 512x512 | 24 | OK | 51.5 | 51.0 | 0.1064 | 8.91 | OK | `PAD_ITA.png` |
| 41 | ISO | `/CD/LE/SC.FBZ` | 640x448 | 24 | OK | 27.1 | 51.9 | 0.0531 | 4.07 | OK | `SC.png` |
| 42 | VOKES0.IMG | `/DI/LE/ACCEPT.FBZ` | 192x320 | 32 | OK | 6.7 | 29.0 | 0.0103 | 4.64 | OK | `VOKES0_DI_LE_ACCEPT.png` |
| 43 | VOKES0.IMG | `/DI/LE/LANG_AR.FBZ` | 64x64 | 32 | OK | 252.4 | 11.8 | 0.0063 | 0.37 | OK | `VOKES0_DI_LE_LANG_AR.png` |
| 44 | VOKES0.IMG | `/DI/LE/LANG_BG.FBZ` | 640x480 | 24 | OK | 29.1 | 17.2 | 0.0185 | 1.68 | OK | `VOKES0_DI_LE_LANG_BG.png` |
| 45 | VOKES0.IMG | `/DI/LE/LOADING/DE/LOADING_ASSAULT.FBZ` | 512x512 | 24 | OK | 69.1 | 73.5 | 0.2471 | 6.51 | OK | `VOKES0_DI_LE_LOADING_DE_LOADING_ASSAULT.png` |
| 46 | VOKES0.IMG | `/DI/LE/LOADING/DE/LOADING_LASTMAN.FBZ` | 512x512 | 24 | OK | 69.1 | 73.5 | 0.2471 | 6.51 | OK | `VOKES0_DI_LE_LOADING_DE_LOADING_LASTMAN.png` |
| 47 | VOKES0.IMG | `/DI/LE/LOADING/DE/LOADING_SUPREMACY.FBZ` | 512x512 | 24 | OK | 69.1 | 73.5 | 0.2471 | 6.51 | OK | `VOKES0_DI_LE_LOADING_DE_LOADING_SUPREMACY.png` |
| 48 | VOKES0.IMG | `/DI/LE/LOADING/DE/PAD_CFG1.FBZ` | 512x512 | 24 | OK | 97.2 | 90.1 | 0.319 | 7.04 | OK | `VOKES0_DI_LE_LOADING_DE_PAD_CFG1.png` |
| 49 | VOKES0.IMG | `/DI/LE/LOADING/DE/PAD_CFG2.FBZ` | 512x512 | 24 | OK | 97.2 | 90.1 | 0.319 | 7.04 | OK | `VOKES0_DI_LE_LOADING_DE_PAD_CFG2.png` |
| 50 | VOKES0.IMG | `/DI/LE/LOADING/DE/PAD_CFG3.FBZ` | 512x512 | 24 | OK | 97.2 | 90.1 | 0.319 | 7.04 | OK | `VOKES0_DI_LE_LOADING_DE_PAD_CFG3.png` |
| 51 | VOKES0.IMG | `/DI/LE/LOADING/EN/LOADING_ASSAULT.FBZ` | 512x512 | 24 | OK | 69.1 | 73.5 | 0.2471 | 6.51 | OK | `VOKES0_DI_LE_LOADING_EN_LOADING_ASSAULT.png` |
| 52 | VOKES0.IMG | `/DI/LE/LOADING/EN/LOADING_LASTMAN.FBZ` | 512x512 | 24 | OK | 69.1 | 73.5 | 0.2471 | 6.51 | OK | `VOKES0_DI_LE_LOADING_EN_LOADING_LASTMAN.png` |
| 53 | VOKES0.IMG | `/DI/LE/LOADING/EN/LOADING_SUPREMACY.FBZ` | 512x512 | 24 | OK | 69.1 | 73.5 | 0.2471 | 6.51 | OK | `VOKES0_DI_LE_LOADING_EN_LOADING_SUPREMACY.png` |
| 54 | VOKES0.IMG | `/DI/LE/LOADING/EN/PAD_CFG1.FBZ` | 512x512 | 24 | OK | 97.2 | 90.1 | 0.319 | 7.04 | OK | `VOKES0_DI_LE_LOADING_EN_PAD_CFG1.png` |
| 55 | VOKES0.IMG | `/DI/LE/LOADING/EN/PAD_CFG2.FBZ` | 512x512 | 24 | OK | 97.2 | 90.1 | 0.319 | 7.04 | OK | `VOKES0_DI_LE_LOADING_EN_PAD_CFG2.png` |
| 56 | VOKES0.IMG | `/DI/LE/LOADING/EN/PAD_CFG3.FBZ` | 512x512 | 24 | OK | 97.2 | 90.1 | 0.319 | 7.04 | OK | `VOKES0_DI_LE_LOADING_EN_PAD_CFG3.png` |
| 57 | VOKES0.IMG | `/DI/LE/LOADING/ES/LOADING_ASSAULT.FBZ` | 512x512 | 24 | OK | 69.1 | 73.5 | 0.2471 | 6.51 | OK | `VOKES0_DI_LE_LOADING_ES_LOADING_ASSAULT.png` |
| 58 | VOKES0.IMG | `/DI/LE/LOADING/ES/LOADING_LASTMAN.FBZ` | 512x512 | 24 | OK | 69.1 | 73.5 | 0.2471 | 6.51 | OK | `VOKES0_DI_LE_LOADING_ES_LOADING_LASTMAN.png` |
| 59 | VOKES0.IMG | `/DI/LE/LOADING/ES/LOADING_SUPREMACY.FBZ` | 512x512 | 24 | OK | 69.1 | 73.5 | 0.2471 | 6.51 | OK | `VOKES0_DI_LE_LOADING_ES_LOADING_SUPREMACY.png` |
| 60 | VOKES0.IMG | `/DI/LE/LOADING/ES/PAD_CFG1.FBZ` | 512x512 | 24 | OK | 97.2 | 90.1 | 0.319 | 7.04 | OK | `VOKES0_DI_LE_LOADING_ES_PAD_CFG1.png` |
| 61 | VOKES0.IMG | `/DI/LE/LOADING/ES/PAD_CFG2.FBZ` | 512x512 | 24 | OK | 97.2 | 90.1 | 0.319 | 7.04 | OK | `VOKES0_DI_LE_LOADING_ES_PAD_CFG2.png` |
| 62 | VOKES0.IMG | `/DI/LE/LOADING/ES/PAD_CFG3.FBZ` | 512x512 | 24 | OK | 97.2 | 90.1 | 0.319 | 7.04 | OK | `VOKES0_DI_LE_LOADING_ES_PAD_CFG3.png` |
| 63 | VOKES0.IMG | `/DI/LE/LOADING/FR/LOADING_ASSAULT.FBZ` | 512x512 | 24 | OK | 69.1 | 73.5 | 0.2471 | 6.51 | OK | `VOKES0_DI_LE_LOADING_FR_LOADING_ASSAULT.png` |
| 64 | VOKES0.IMG | `/DI/LE/LOADING/FR/LOADING_LASTMAN.FBZ` | 512x512 | 24 | OK | 69.1 | 73.5 | 0.2471 | 6.51 | OK | `VOKES0_DI_LE_LOADING_FR_LOADING_LASTMAN.png` |
| 65 | VOKES0.IMG | `/DI/LE/LOADING/FR/LOADING_SUPREMACY.FBZ` | 512x512 | 24 | OK | 69.1 | 73.5 | 0.2471 | 6.51 | OK | `VOKES0_DI_LE_LOADING_FR_LOADING_SUPREMACY.png` |
| 66 | VOKES0.IMG | `/DI/LE/LOADING/FR/PAD_CFG1.FBZ` | 512x512 | 24 | OK | 97.2 | 90.1 | 0.319 | 7.04 | OK | `VOKES0_DI_LE_LOADING_FR_PAD_CFG1.png` |
| 67 | VOKES0.IMG | `/DI/LE/LOADING/FR/PAD_CFG2.FBZ` | 512x512 | 24 | OK | 97.2 | 90.1 | 0.319 | 7.04 | OK | `VOKES0_DI_LE_LOADING_FR_PAD_CFG2.png` |
| 68 | VOKES0.IMG | `/DI/LE/LOADING/FR/PAD_CFG3.FBZ` | 512x512 | 24 | OK | 97.2 | 90.1 | 0.319 | 7.04 | OK | `VOKES0_DI_LE_LOADING_FR_PAD_CFG3.png` |
| 69 | VOKES0.IMG | `/DI/LE/LOADING/IT/LOADING_ASSAULT.FBZ` | 512x512 | 24 | OK | 69.1 | 73.5 | 0.2471 | 6.51 | OK | `VOKES0_DI_LE_LOADING_IT_LOADING_ASSAULT.png` |
| 70 | VOKES0.IMG | `/DI/LE/LOADING/IT/LOADING_LASTMAN.FBZ` | 512x512 | 24 | OK | 69.1 | 73.5 | 0.2471 | 6.51 | OK | `VOKES0_DI_LE_LOADING_IT_LOADING_LASTMAN.png` |
| 71 | VOKES0.IMG | `/DI/LE/LOADING/IT/LOADING_SUPREMACY.FBZ` | 512x512 | 24 | OK | 69.1 | 73.5 | 0.2471 | 6.51 | OK | `VOKES0_DI_LE_LOADING_IT_LOADING_SUPREMACY.png` |
| 72 | VOKES0.IMG | `/DI/LE/LOADING/IT/PAD_CFG1.FBZ` | 512x512 | 24 | OK | 97.2 | 90.1 | 0.319 | 7.04 | OK | `VOKES0_DI_LE_LOADING_IT_PAD_CFG1.png` |
| 73 | VOKES0.IMG | `/DI/LE/LOADING/IT/PAD_CFG2.FBZ` | 512x512 | 24 | OK | 97.2 | 90.1 | 0.319 | 7.04 | OK | `VOKES0_DI_LE_LOADING_IT_PAD_CFG2.png` |
| 74 | VOKES0.IMG | `/DI/LE/LOADING/IT/PAD_CFG3.FBZ` | 512x512 | 24 | OK | 97.2 | 90.1 | 0.319 | 7.04 | OK | `VOKES0_DI_LE_LOADING_IT_PAD_CFG3.png` |
| 75 | VOKES0.IMG | `/DI/LE/LOADING/MENU_ONLINE.FBZ` | 512x512 | 24 | OK | 75.9 | 69.4 | 0.2472 | 6.06 | OK | `VOKES0_DI_LE_LOADING_MENU_ONLINE.png` |
| 76 | VOKES0.IMG | `/DI/LE/LOADING/RETICULE.FBZ` | 256x512 | 32 | OK | 86.5 | 102.1 | 0.0 | 0.45 | OK | `VOKES0_DI_LE_LOADING_RETICULE.png` |
| 77 | VOKES0.IMG | `/DI/LE/SC.FBZ` | 640x448 | 24 | OK | 27.1 | 51.9 | 0.0531 | 4.07 | OK | `VOKES0_DI_LE_SC.png` |

`inflate` = OK means zlib inflated without error **and** produced exactly the
byte count the header's `rawSize` declares. That held for all 77 files.

## Verdict key

- **OK** — inflated to rawSize, statistics consistent with artwork, PNG written.
- **ALPHA-ONLY** — `LANG_FG` only. Its RGB planes are constant `ff ff ff`
  (stddev 0.0, verified by a per-lane histogram: lane0/1/2 have exactly 1
  distinct value each, lane3 has 140). All the picture is in the alpha
  channel, which runs 0–150 and draws a soft-edged rounded panel. The decode
  is correct; the flat statistic is a property of the asset, not a failure.

No file failed. No file produced noise.

## Archives

`/MENU.IMG` (lba 277257, 680,059,380 bytes) opens as a vokes archive with
**111 files and zero images**. Both tests were applied to all 111: no `.FBZ`
extension, and no file whose bytes 8..11 give plausible w/h with a `0x78`
zlib byte at offset 16. Its contents are 50 `.INT`/`.ESP`/`.FRA` localisation
ini files, 8 `.PSS` and 5 `.M2V` videos (intro, credits, ESRB, the GRAW
attract movie), 4 `.ICO`, sound banks, and the three opaque menu blobs
`MENU.DMG` / `MENU.DMP` / `MENU.LAZ`. **GRAW's own in-game menu art is not
FBZ** — if it is anywhere it is inside `MENU.DMP` (11.4 MB) or `MENU.LAZ`
(5.5 MB), whose formats were not investigated. That is a guess, not a finding.

`/VOKES0.IMG` (lba 204728, 110,898,610 bytes) has 130 files, **36 of them
FBZ**, all under `/DI/LE/`. All 36 were decoded (within the 40 budget).

`/VOKES2.IMG` was also opened (267 files, 36 FBZ). Its FBZ set is
**byte-identical to VOKES0's** — same 36 names, all 36 SHA-1s equal — so it
was not decoded again.

`/GR3_1.IMG`, `/GR3_2.IMG`, `/MP.IMG`, `/SP.IMG` and `/IRX_ON/DNAS300.IMG`
are **not** vokes archives (`open_archives` rejected them: no entry table at
0x800). Not sampled.

## What the art actually is

- `GR3_1/2/3.FBZ` — three 512x512 GRAW cover/splash panels with the
  "Tom Clancy's Ghost Recon Advanced Warfighter" lockup on a teal-accented
  frame. These are the best skin material on the disc.
- `PAD_*.FBZ`, `MCARD/*.FBZ` — 512x512 system-message screens. Their art and
  wordmark are **Ghost Recon 2**, not GRAW: the logo reads "GHOST RECON 2"
  over an olive-green soldier collage. Asset reuse left in the shipped game.
- `SC.FBZ` — the **Splinter Cell** 2003 legal screen, verbatim, complete with
  "(c) 2003 Ubi Soft Entertainment". Another leftover; present both in the
  ISO tree and inside VOKES0/VOKES2.
- `VOKES0:/DI/LE/LOADING/**` — Rainbow Six 3 era paths (`LOADING_ASSAULT`,
  `LOADING_LASTMAN`, `LOADING_SUPREMACY`, `PAD_CFG1..3`, `MENU_ONLINE`) but
  the images are GRAW artwork, duplicated once per language folder
  (DE/EN/ES/FR/IT).
- `RETICULE.FBZ` — a 256x512 RGBA sprite sheet of 16 green reticules.
- `LANG_AR/FG/TT`, `ACCEPT` — small RGBA UI pieces (arrow glyph, soft panel,
  language-button strip, per-language "Accept" rows with the PS2 cross icon).

### Duplicate images

Identical source bytes (SHA-1 of the FBZ), so the PNGs are identical too:

- `VOKES0_DI_LE_LOADING_DE_LOADING_ASSAULT`, `VOKES0_DI_LE_LOADING_DE_LOADING_LASTMAN`, `VOKES0_DI_LE_LOADING_DE_LOADING_SUPREMACY`, `VOKES0_DI_LE_LOADING_EN_LOADING_ASSAULT`, `VOKES0_DI_LE_LOADING_EN_LOADING_LASTMAN`, `VOKES0_DI_LE_LOADING_EN_LOADING_SUPREMACY`, `VOKES0_DI_LE_LOADING_ES_LOADING_ASSAULT`, `VOKES0_DI_LE_LOADING_ES_LOADING_LASTMAN`, `VOKES0_DI_LE_LOADING_ES_LOADING_SUPREMACY`, `VOKES0_DI_LE_LOADING_FR_LOADING_ASSAULT`, `VOKES0_DI_LE_LOADING_FR_LOADING_LASTMAN`, `VOKES0_DI_LE_LOADING_FR_LOADING_SUPREMACY`, `VOKES0_DI_LE_LOADING_IT_LOADING_ASSAULT`, `VOKES0_DI_LE_LOADING_IT_LOADING_LASTMAN`, `VOKES0_DI_LE_LOADING_IT_LOADING_SUPREMACY`
- `SC`, `VOKES0_DI_LE_SC`
- `LANG_AR`, `VOKES0_DI_LE_LANG_AR`
- `VOKES0_DI_LE_LOADING_DE_PAD_CFG1`, `VOKES0_DI_LE_LOADING_DE_PAD_CFG2`, `VOKES0_DI_LE_LOADING_DE_PAD_CFG3`, `VOKES0_DI_LE_LOADING_EN_PAD_CFG1`, `VOKES0_DI_LE_LOADING_EN_PAD_CFG2`, `VOKES0_DI_LE_LOADING_EN_PAD_CFG3`, `VOKES0_DI_LE_LOADING_ES_PAD_CFG1`, `VOKES0_DI_LE_LOADING_ES_PAD_CFG2`, `VOKES0_DI_LE_LOADING_ES_PAD_CFG3`, `VOKES0_DI_LE_LOADING_FR_PAD_CFG1`, `VOKES0_DI_LE_LOADING_FR_PAD_CFG2`, `VOKES0_DI_LE_LOADING_FR_PAD_CFG3`, `VOKES0_DI_LE_LOADING_IT_PAD_CFG1`, `VOKES0_DI_LE_LOADING_IT_PAD_CFG2`, `VOKES0_DI_LE_LOADING_IT_PAD_CFG3`
- `ACCEPT`, `VOKES0_DI_LE_ACCEPT`

## Bug found in `tcps2/art.py`

`decode_fbz` dispatches with:

```python
stride = raw_size // height
if bpp == 24 or stride >= width * 3:      # <-- 32-bpp falls in here
    ... read width*3 bytes per row as RGB ...
if bpp == 32 or stride >= width * 4:      # <-- unreachable for bpp==32
```

For any 32-bpp file `stride == width * 4`, which is always `>= width * 3`, so
the first branch always wins and the RGBA branch below it is **dead code**.
The result is that RGBA pixels are read as RGB triples: channels shear by one
byte every pixel and only 3/4 of each row is consumed. Concretely, before the
fix `LANG_TT.FBZ` came out as magenta-and-green vertical striping (hΔ 53.4);
after it, grey-blue buttons with embossed language names (hΔ 8.6).

Affected on this disc: `ACCEPT.FBZ`, `LANG_AR.FBZ`, `LANG_FG.FBZ`,
`LANG_TT.FBZ` (ISO + VOKES copies) and `VOKES0:/DI/LE/LOADING/RETICULE.FBZ`.
Reordering the two tests (check `bpp == 32` first) fixes it. `art.py` was
**not** modified — this run is read-only outside the art folder.

## Two things a consumer of these PNGs must know

1. **Channel order is RGB, not BGR.** Confirmed on `GR3_3.FBZ`, which shows an
   uncovered human face: RGB order gives natural skin tone, a B/R swap gives
   blue skin. The teal frame is deliberate GRAW branding, not a swapped channel.
2. **The 32-bpp files use the PS2 GS alpha convention where 0x80 = fully
   opaque.** Measured alpha maxima: `ACCEPT` 128, `LANG_AR` 128, `LANG_FG` 150,
   but `LANG_TT` 255 and `RETICULE` 255. The PNGs carry the raw byte, so the
   0..128 ones will look ~50%% transparent in a normal viewer and need their
   alpha doubled and clamped. The 0..255 ones must not be touched.

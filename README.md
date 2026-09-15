# Tom Clancy Xbox Mod Studio

A windowed mod tool for the Tom Clancy games on the original Xbox. Point it at
a folder an Xbox disc was extracted into, pick options off pages skinned in that
game's own artwork, and press **Apply to game**. Every file it changes is copied
first, and **Restore folder** puts every one of them back at the byte it came
from.

It is the sibling of [Tom Clancy PS2 Mod Studio][ps2] — same window, same
declarative model, same two safety rules — with the disc image replaced by a
folder and the MIPS disassembly replaced by the fact that these games keep
almost everything interesting in plain text.

[ps2]: https://github.com/BRAGme/TomClancyPS2-ModStudio

## Games

| Game | Title id | Where its options come from |
| --- | --- | --- |
| Ghost Recon | `55530006` | mission XML, enemy templates, 48 weapons, combat model |
| Ghost Recon: Island Thunder | `55530007` | the same, over its eight Cuban missions |
| Ghost Recon 2 | `55530005` | combat model, 114 weapons, dedicated-server rules |
| Ghost Recon 2: Summit Strike | `5553004D` | the same, 162 weapons |
| Rainbow Six 3 | `55530013` | the gameplay table and 115 terrorist templates, inside `xboxdynamic.umd` |
| Rainbow Six 3: Black Arrow (prototype) | `55530037` | the same, loose, plus per-map ini |
| Ghost Recon: Advanced Warfighter | `55530054` | the shared gameplay table, plus teammate AI and enemy weapon tables |

The game is identified by the **title id in its own executable**, not by the
folder's name, so a renamed folder still works and a folder holding some other
game is never mistaken for one of these. Black Arrow's prototype disc is a demo
installer whose payload sits three levels down; point the tool at the folder you
downloaded and it walks down to find the game.

## Running it

```bash
python ModStudio.py
```

Or, without a window:

```bash
python ModStudio.py --cli scan "E:\XBOX Classic Games"
python ModStudio.py --cli show "E:\XBOX Classic Games\Tom Clancy's Ghost Recon (USA)"
python ModStudio.py --cli plan "...\Ghost Recon (USA)" --preset 2
python ModStudio.py --cli apply "...\Ghost Recon (USA)" --set gr_all_difficulties=true --set gr_tier=up1
python ModStudio.py --cli revert "...\Ghost Recon (USA)"
```

`python build_exe.py` produces a single `dist\ModStudio.exe` that serves both
modes — the windowed build attaches to the console it was started from when it
sees `--cli`.

Needs Python 3.10+ and Pillow. Tkinter ships with Python on Windows.

## What it actually changes

Nothing is patched into an executable. Every option rewrites the game's own
data, and every transform keeps the file's length, which is not a style choice:

* A `.GLB` glob has **no index**. Each entry's position is implied by the length
  of the one before it, so a file that grew by a byte would move every file
  after it.
* Rainbow Six 3's `.UMD` bundle *does* have an index, but the tool writes inside
  a slot anyway, so the bundle stays byte-identical everywhere the edit did not
  reach.

Where a file has to grow — a terrorist skill going from `50` to `100` is one
character longer — the difference is taken out of the file's own blank lines,
which no line-oriented parser reads.

**The same file often exists twice.** Ghost Recon's mission XML sits loose under
`mission\` *and* inside `globs\ikedata.glb`, byte for byte identical, while the
enemy templates those missions name sit only inside the per-level `*_chars.glb`.
Ghost Recon 2 ships its combat model both loose and packed. Rainbow Six 3 ships
two *different* copies of `RainbowSix3Xbox.ini`, 5,393 bytes loose and 5,155
inside the bundle. The folder index keys every copy and writes all of them, so
"I edited the file and nothing happened" is not a failure mode here.

## The two rules that make it safe to run twice

1. **Every apply starts from the file as it shipped**, never from what is in the
   folder now. The originals are on disk in the backup folder, so applying twice
   gives the same result as applying once, and clearing an option really removes
   it — an apply puts back every file it touched before that no longer matches
   an edit.
2. **Everything replaced is copied first**, into
   `<parent>\.tcxms-backup\<game folder>\`, so a mod can be undone a month
   later.

## How far each option is proven

Every card carries a badge, and this build is honest about the fact that none of
them says *verified in game*:

* **measured, not play-tested** — the files are confirmed rewritten and read
  back. This is 181 of the 195 options.
* **untested** — reasoned from the data, never tried. Seven options.
* **not working** — shipped visible and disabled with the reason written on the
  card, because "why is that missing" is worth answering in the interface. Seven
  options, and each one names what was looked at: Ghost Recon has no wave dial
  because reading all 28 script variables in every `.gtf` in the game turns up
  text ids and capture timers and no enemy count; Ghost Recon 2 has no
  difficulty-flag strip because its mission files carry Igor placement objects
  rather than an order of battle.

## What was reverse-engineered for this

Four container formats, all cracked against the real discs and all covered by
the test suite:

* **`.GLB` globs** — `tcxbox/globfile.py`. Two header shapes, told apart by
  parsing rather than by the game; 254 globs and 20,490 entries on this shelf,
  and the three size words read *(stored, flag, raw)*, which is the detail that
  parses the first few entries convincingly either way and then walks off the
  end of the file.
* **`.UMD` bundles** — `tcxbox/umd.py`. This is what makes Rainbow Six 3
  moddable at all: 536 files including the gameplay table and every terrorist
  template.
* **`.RSB` bitmaps, versions 8 and 9** — `tcxbox/rsb.py`. 35 bytes of header,
  not 36, and the bit depths in the header do not always describe the storage.
* **`.XPR` packed resources** — `tcxbox/xpr.py`, including the Morton deswizzle
  the uncompressed formats need.

Plus `tcxbox/xbe.py`, which reads enough of an Xbox executable to get the title
id and the section map.

## Tests

```bash
python tests\run_tests.py "E:\XBOX Classic Games"
python tests\gui_smoke.py "E:\XBOX Classic Games"
```

The first runs eleven checks against the real extracted discs — every container
parses and round-trips, every edit keeps its file's length, the two sides of the
war are separable where the data allows it, and every preset on every game
applies and then reverts to a byte-identical folder. **Nothing retail is ever
opened for writing**: the apply/revert cycle copies what it needs into the
system temp folder and works there.

The second opens the real window on every game and walks every page, which is
how a broken card or a missing palette colour is found.

## Artwork

None is redistributed. Each game's backdrop and dashboard logo are read out of
your own extracted disc when it is loaded and cached under `%LOCALAPPDATA%`.

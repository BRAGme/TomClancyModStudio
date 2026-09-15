# Tom Clancy Xbox Mod Studio

A windowed mod tool for the Tom Clancy games on the original Xbox. Point it at
a game -- **the `.iso` itself**, or a folder one was extracted into -- pick
options off pages skinned in that game's own artwork, and press **Apply to
game**. Every file it changes is copied first, and **Restore folder** puts every
one of them back at the byte it came from.

Disc images are edited **in place**. XDVDFS gives every file a whole number of
2 KB sectors, so a file can grow into its own padding and the directory entry's
size field is a 32-bit write away -- nothing is rebuilt, relocated or
re-authored, and a 4 GB image is opened, changed and closed in about a second.

It is the sibling of [Tom Clancy PS2 Mod Studio][ps2] — same window, same
declarative model, same two safety rules — with the disc image replaced by a
folder and the MIPS disassembly replaced by the fact that these games keep
almost everything interesting in plain text.

[ps2]: https://github.com/BRAGme/TomClancyPS2-ModStudio

![Ghost Recon, the Missions page](docs/screens/ghost-recon-missions.png)

## Games

| Game | Title id | Where its options come from |
| --- | --- | --- |
| Ghost Recon | `55530006` | mission XML, enemy templates, 48 weapons, combat model |
| Ghost Recon: Island Thunder | `55530007` | the same, over its eight Cuban missions |
| Ghost Recon 2 | `55530005` | combat model, 114 weapons, dedicated-server rules |
| Ghost Recon 2: Summit Strike | `5553004D` | the same, 162 weapons |
| Rainbow Six 3 | `55530013` | the gameplay table and 115 terrorist templates, inside `xboxdynamic.umd` |
| Rainbow Six 3: Black Arrow | `55530037` | the same bundle, 120 templates and 42 ini files |
| Ghost Recon: Advanced Warfighter | `55530054` | the shared gameplay table, plus teammate AI and enemy weapon tables |
| Rainbow Six: Critical Hour | `5553005F` | **nothing yet** -- recognised, and the page says why |

Point it at a game, **or at the folder your games live in**. A folder with more
than one game under it is a shelf rather than a game, so it fills the picker
instead of the tool choosing one of them. The two fields read as the two
questions in order -- **Games folder**, then **Game** -- and the top one keeps
holding the folder after a game loads, so trying the next game is one click
rather than another trip through a file dialog.

![Sixteen games on one shelf](docs/screens/shelf-picker.png)

The game is identified by the **title id in its own executable**, not by its
file name, so a renamed disc still works and one holding some other game is
never mistaken for these. Black Arrow's prototype disc carries the same title id
as retail and is an installer whose payload sits three levels down; point the
tool at either and it finds the game.

Critical Hour is listed because it is on the shelf and the tool loads it, and it
has no options because it has nothing to offer: all 19,085 entries on that disc
were enumerated and **not one of them is text** -- no ini files, no terrorist
templates, no globs, and 146 cooked-binary mission files where every other Red
Storm game here ships XML. That census is on its About page rather than in a
footnote, because a page of dials that quietly did nothing would be worse.

## Running it

```bash
python XboxModStudio.py
```

Or, without a window:

```bash
python XboxModStudio.py --cli scan "E:\XBOX Classic Games"
python XboxModStudio.py --cli show "E:\XBOX Classic Games\Tom Clancy's Ghost Recon (USA).xiso.iso"
python XboxModStudio.py --cli plan "...\Ghost Recon (USA).xiso.iso" --preset 2
python XboxModStudio.py --cli apply "...\Ghost Recon (USA).xiso.iso" --set gr_all_difficulties=true --set gr_tier=up1
python XboxModStudio.py --cli revert "...\Ghost Recon (USA).xiso.iso"
```

Every one of those takes a disc image or a folder; `scan` lists both.

`python build_exe.py` produces a single `dist\XboxModStudio.exe` that serves
both modes — the windowed build attaches to the console it was started from when it
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
* A loose file is the exception and may change length -- in a folder it is just
  rewritten, and inside a disc image it grows into the sector padding XDVDFS
  already gave it. That is checked per file, not globally, which is what lets
  the `.ASS` server scripts be rewritten with values of a different width.

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

## The skins are the Xbox ones

Each game wears its own menu, and the colours were sampled out of its own shell
art rather than inherited from the PS2 tool -- which matters, because they are
not the same games' skins. The PS2 Ghost Recon shell is gold on navy; the Xbox
one is **steel blue** (`#384878`, measured off `shell_bgd-01.rsb`). The full
set, ground and accent: Ghost Recon `#081028`/`#384878`, Island Thunder
`#001008`/`#306858`, Ghost Recon 2 `#000000`/`#60c030`, Summit Strike the same
shell iced to `#58a0d8`, Rainbow Six 3 `#080808`/`#b01f22`, Black Arrow
`#181010`/`#a84830`, GRAW `#000808`/`#38c0b8`, Critical Hour `#300000`/`#682020`.

The wordmarks are each game's own, at its own resolution -- `STARTscreen.rsb` is
512 x 128, `Splash.xpr` is 512 x 512, the Rainbow Six splashes are 640 x 480 --
lifted out by finding the brightest mass in the picture and keying the plate
behind it away over a soft ramp. The first version used the 64-pixel dashboard
icons and it showed.

![GRAW, the enemy weapons page](docs/screens/graw-enemy-weapons.png)

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
  back. This is 181 of the 196 options.
* **untested** — reasoned from the data, never tried. Seven options.
* **not working** — shipped visible and disabled with the reason written on the
  card, because "why is that missing" is worth answering in the interface. Eight
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
* **XDVDFS**, the filesystem on the disc images — `tcxbox/xiso.py`. A directory
  is a binary search tree of the *file names*, so a folder with a few thousand
  files is one chain thousands deep and has to be walked iteratively; and the
  volume descriptor sits at a global offset that differs between a plain xiso
  rip and a redump image, so it is searched for rather than assumed.

Plus `tcxbox/xbe.py`, which reads enough of an Xbox executable to get the title
id and the section map.

## Tests

```bash
python tests\run_tests.py "E:\XBOX Classic Games"
python tests\gui_smoke.py "E:\XBOX Classic Games"
```

The first runs thirteen checks against the real discs — every container parses,
every edit keeps its file's length, the two sides of the war are separable where
the data allows it, and every preset on every game applies and then reverts to a
byte-identical folder. **Nothing retail is ever opened for writing**: the
apply/revert cycle copies what it needs into the system temp folder and works
there, and the disc-image writer is exercised against a small XDVDFS image built
by `tests/make_xiso.py` rather than a 4 GB retail one.

One of those checks is worth naming. Six of these games are on the shelf twice,
as an image and as an extracted folder, and the suite reads both through their
two completely independent readers and compares: 580 files byte-identical. That
is the only real evidence that the two paths agree.

The second opens the real window on every game and walks every page, which is
how a broken card or a missing palette colour is found.

## Artwork

None is redistributed. Each game's backdrop, wordmark and per-mission briefing
art are read out of your own disc when it is loaded, and cached under
`%LOCALAPPDATA%`.

Every Ghost Recon and Island Thunder mission card carries the game's own
pictures: the briefing's tactical map from `commandmaps\`, then two of the four
screenshots off that mission's briefing sheet in `briefings\`. The sheet is one
512 x 256 page holding a 2 x 2 grid, so it is content-cropped and quartered. The
sheet's name comes from the mission file's own `<MapShots>` rather than from its
stem, because the two do not always agree -- `m10_ruined_city.mis` asks for
`m10_vilnius_shots`. All 26 cards across the two games have all three pictures.

## The icon

`python assets\make_icon.py` redraws it. It is the PS2 tool's reticle -- they
are siblings and should look it -- in **teal instead of green**, inside the four
corner brackets Ghost Recon prints around every briefing screenshot. Hue and
silhouette are the two things that tell icons apart at 16 pixels, and both
differ.

The sizes under 32 pixels are drawn again rather than downsampled from the 256.
A big drawing resampled that far turns the ring into a smudge and the brackets
into four dirty pixels, and a smudge reads as "some icon" rather than as this
one, which is the entire job at taskbar size.

The binary is `XboxModStudio.exe`, not `ModStudio.exe` -- that is what the PS2
tool builds, and two identically named files with similar icons in one Downloads
folder is the confusion this is all meant to avoid. It also sidesteps Windows'
icon cache, which is keyed on the path: rebuild a new icon into the same
`ModStudio.exe` and Explorer keeps showing the old one, which looks exactly like
the icon not having changed. If you ever do need to clear it:

```bash
ie4uinit.exe -show
```

# Tom Clancy PC Mod Studio

A skinned mod manager for seven Tom Clancy games on PC. Same window as the
[PS2](../TomClancyPS2-ModStudio) and [Xbox](../TomClancyXbox-ModStudio) Mod
Studios — it wears each game's own menu art, read out of your installation at
run time — but aimed at PC installs rather than disc images.

| Game | Engine | How changes are delivered |
|---|---|---|
| Rainbow Six 3: Raven Shield | Unreal Engine 2 | edits `.ini` and `template\*.tpt` in place, and patches weapon and ammunition defaults in the compiled `system\*.u` packages |
| Ghost Recon | Red Storm Ike | **builds a mod folder** — nothing retail is touched |
| The Sum of All Fears | Red Storm Ike | **builds a mod folder** |
| Rainbow Six 3: Lockdown | Red Storm Nimitz | edits `data\` in place |
| Rainbow Six: Vegas | Unreal Engine 3 | edits `KellerGame\Config\PC\*.ini` in place |
| Ghost Recon Advanced Warfighter | GRIN Diesel | **writes loose files over the `.bundle` archives**, source and compiled twin |
| GRAW 2 | GRIN Diesel | **writes loose files over the `.bundle` archives**, source and compiled twin |

```
python ModStudio.py                    the window
python ModStudio.py --preview          look at the options without owning the games
python ModStudio.py --cli find         list the games on this machine
python ModStudio.py --cli preview "<game folder>" enemy_accuracy=45
python ModStudio.py --cli apply   "<game folder>" enemy_accuracy=45
python ModStudio.py --cli restore "<game folder>"
```

Needs Python 3.9+, Pillow and Tk. `python build_exe.py` makes a single-file
`dist\ModStudio.exe`.

## What makes it safe to run twice

Two invariants, carried over from the PS2 tool:

**Every apply rebuilds from pristine.** Nothing is ever edited on top of an
earlier edit. In-place games restore each touched file from the copy taken the
first time it was written and apply the whole set to that; mod-folder games
delete the generated folder and rebuild it from the stock mod; the two
Advanced Warfighter games undo their loose files and re-derive them from
the archive. So applying
twice equals applying once, and clearing an option really removes it instead of
leaving behind the last value it happened to hold.

**Every edit states the value it expects to find.** The stock value is checked
before the write and reported when it does not match, because a stock value
that is not there means the option was worked out against a different build of
the game.

On top of those:

* **Preview changes** does the entire apply without writing a byte and prints
  every value that would move. Worth using first: on these games one slider can
  rewrite four hundred files.
* Backups live in `<game>\.tcpc-backup\`, with a manifest and a pristine copy
  of each file. **Restore** puts them all back.
* A generated mod folder carries a `.tcpc-generated` marker, and the tool will
  **refuse** to delete a folder that does not have one — so a hand-made mod
  that happens to share the name is safe.
* Advanced Warfighter's `.bundle` archives are only ever read. Restore
  removes exactly the loose files the tool added and puts back any it wrote
  over; it never deletes `Data\`, which is shared with your own texture
  replacements.
* A mod build is reproducible: the same settings against the same stock data
  produce byte-identical output.

## Honesty about what works

Every option is badged with how far it has actually been proven:

* **verified in game** — watched working in the running game
* **written and read back** — the edit lands in the file correctly; the effect
  has not been independently observed
* **untested** — reasoned from the data, never run
* **not working** — shipped visible and disabled with the reason on the card

**Almost everything here is currently "untested".** The file formats, the
values and the round-trips are all verified by the test suite against the real
games; what has not happened yet is someone launching each game and watching
the option do what it says. The About page for each game says what is missing
and why.

## Tests

```
python tests\run_tests.py       149 checks against the real games
python tests\gui_smoke.py       open the real window on every game, walk every page
```

`run_tests.py` never opens a retail file for writing: the editors are exercised
read-only against the installations, and anything that writes happens in a
sandbox copy under the temporary directory. The Advanced Warfighter archives
are far too big to copy, so that test builds its own `BNDL` archive from the
real weapon definitions, which doubles as the check that the format was
understood rather than pattern-matched into working. It checks that hundreds of real
`.ini`, `.tpt` and pseudo-XML files load and save byte-identically, that
applying twice equals applying once, that clearing every option returns the
tree to stock, and that restore returns every byte.

`gui_smoke.py --shots <dir>` saves a PNG of each page. It renders the window
into an off-screen bitmap with `PrintWindow` rather than grabbing the screen,
so it captures this window and nothing else that happens to be on the desktop.

## How it is put together

```
tcpc/
  model.py      Setting + five edit kinds (IniEdit, XmlAttr, XmlText, PropEdit,
                FileCopy)
  inifile.py    Unreal .ini editing that preserves formatting; also reads .tpt
  rsexml.py     Red Storm pseudo-XML, edited one value at a time
  rsb.py        Red Storm .rsb bitmaps, versions 4-10
  bundle.py     GRIN Diesel .bundle archives, read-only
  xmlbin.py     Diesel compiled XML (.xml.bin / .xmb), read and write
  upackage.py   Unreal Engine 2 .u packages: class defaults, read and rewritten
                in place at identical width
  art.py        each game's own menu art and wordmark, plus finding the installs
  install.py    which game a folder holds
  engine.py     planning, applying, verifying, reverting
  games/        one declarative profile per game
gui/            the window: skins, chrome painters, controls, cards
docs/FORMATS.md what was reverse-engineered, and how it was settled
```

The GUI is the PS2 tool's, re-aimed: same chrome painters, same setting cards,
same badges. The palettes are **not** the console ones recoloured — each was
sampled from the PC game's own menu page, which is how Ghost Recon ended up
pale-grey-on-slate here rather than the gold-on-navy it wears on PS2. Advanced
Warfighter's teal came from its wordmark rather than its backdrop, because its
menu is a 3D scene and averaging that gives the colour of a Mexican street.

## Credit

The reverse-engineering behind the option catalogues is written up in
`docs/FORMATS.md`, with the raw dossiers in `research/`. Ghost Recon's
enemy-accuracy technique is lifted from the `PS2Accuracy` mod already installed
in this Ghost Recon, which is the reference implementation for separating the
enemy's weapons from the player's.

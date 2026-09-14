# Tom Clancy PS2 Mod Studio

A Windows tool that patches **Tom Clancy PlayStation 2 disc images in place** and
gives you switches for things the games shipped with turned off.

Point it at an ISO, move some sliders, press **Apply to disc**. Nothing is
rebuilt and no ISO tools are needed — every edit is the same number of bytes it
replaces, so a stock emulator boots the result unchanged. A pristine copy of
what it overwrote is kept next to the ISO, and **Restore disc** puts it back
byte for byte.

![the Enemy Waves page](docs/screens/enemy-waves.png)

---

## What it does today

| Disc | Serial | Status |
|---|---|---|
| Rainbow Six 3 | SLUS-20883 | **Full support** — every option below |
| Ghost Recon | SLUS-20613 | Disc reads, artwork extracts, **no gameplay options yet** |
| Ghost Recon: Jungle Storm | SLUS-20820 | Disc reads, artwork extracts, **no gameplay options yet** |

Ghost Recon and Jungle Storm run Red Storm's own engine. Rainbow Six 3 PS2 runs
an Unreal build. They share a disc-archive format and nothing else, so none of
the Rainbow Six 3 work transfers to them. Their entries are in the tool because
it reads their discs correctly and skins itself with their art; the gameplay
switches are still being reverse-engineered, and the tool says so on their
pages rather than offering controls that do nothing.

### Rainbow Six 3 — enemy wave mode

The game already contains a terrorist deployment-zone system. The campaign uses
it. Terrorist Hunt never triggers it. This turns it on and hands you its dials.

* **Where waves feed** — every zone all the time, only the zones you have left
  (so the far side of the map pushes you back and the corner you vacate starts
  up behind you), or the stock rule, which is literally "spawn where the player
  is standing".
* **Enemies each zone owes** — 1 to 250. Multiply by the number of zones on the
  map.
* **Released per wave** — 1 to 8, capped in practice by how many spawn points
  the zone can reach.
* **Alive before the next wave** — the real volume dial. A zone tops itself up
  until more than this many of its enemies are alive, so steady state per zone
  is about this number plus the release size. **Set this first**, then the
  release size, then the total.
* **Waves hunt you from the start** — without it a zone waits for a level script
  trigger that Terrorist Hunt never fires.
* **Spawn across the whole map** — stock, a wave can only use the two or three
  spawn points beside it, so every enemy walks out of one corner. This picks
  from every deployment point in the level instead, which also brings a real
  mix of enemy types. *Delivered as a PCSX2 cheat file — see below.*

Which level you pick matters more than any slider:

| Level | Zones | Spread | Spawn points | Verdict |
|---|---|---|---|---|
| **Shipyard** | 2 | 111 × 114 m, wraps the insertion point | 27 | **best** — fighting from the first minute |
| **Alcatraz** | 2 | 19 m apart | 6 | best wave quality, indoors, cheap to draw |
| **Trieste** | 3 | 54–83 m | 4 | only real triangle, heaviest level in the game |
| Island | 2 | 6 m apart | 5 | every zone sits past the halfway point |
| Oil Refinery | 3 | two clusters | 4 | a thin trickle whatever you set |

Alpine Village A, Import/Export A, Penthouse and Training have no zones at all.

### Rainbow Six 3 — split screen

Split screen deliberately switches a pile of things off. These put them back.

* **Your weapon model.** The engine zeroes a global the moment it sees split
  screen, and that global has exactly one writer in the whole overlay.
* **Bullet impact decals** — two branches, one for hits on the world and one for
  hits on people.
* **Impact puffs and sparks**, **blood effects**, **rain and snow**.
* **Fire, water and scenery emitters.** Levels flag a handful of emitters
  "hide in split screen" and the engine disables exactly those — six per level,
  and they are always the fire and the water next to the players.

**AI teammates in split screen is shipped disabled.** Four separate attempts all
hang the level load and the four hang states are byte-identical, so the cause is
upstream of every edit tried. The option is visible with that written on it
rather than quietly missing.

### Rainbow Six 3 — world

* **Bullet holes kept on screen** — 32 to 160. Footprints and wall hits share a
  fixed-size ring buffer; this is the only way to keep more, and it cannot be
  made unlimited. Each extra decal is a real actor, so raise it one step at a
  time.
* **How long bodies stay** — stock (about 3 seconds), 15, 30, 60, or never.

---

## Using it

1. Download `ModStudio.exe`. No install, no Python.
2. **Close your emulator** — it keeps the ISO locked.
3. Browse to your disc image. The tool identifies it from `SYSTEM.CNF` and
   checks the disc CRC against the build the options were measured on; if it
   does not match you get a warning and the code options are refused, because
   patching addresses on a different revision corrupts it.
4. Pick a preset or set things by hand, then **Apply to disc**.

Every option carries a badge saying how far it has actually been proven:

* **verified in game** — watched working in the running game.
* **patch confirmed, effect untested** — the word is confirmed in the disc, but
  the visible result was not independently checked.
* **not working** — shipped disabled, with the reason.

### The cheat file

One option — map-wide spawn points — cannot go into the disc. It is a code cave,
and a cave written once into the overlay image does not survive a level load;
a cheat file rewrites it every frame, which is what makes it work. **Save cheat
file…** writes a `.pnach` named after the disc CRC.

Drop it in your PCSX2 `cheats` folder, enable cheats for the game, and
**restart the emulator** so the file is read. The patch lines are deliberately
unlabelled: a named `[section]` added while the game is already running never
enters PCSX2's enabled set, and there is nothing in the UI to tell you.

### Undoing it

**Restore disc** rewrites the original bytes from `.tcms-backup` next to the
ISO and checks the result against the stock hash. The backup is taken
automatically the first time the tool sees an untouched disc, so take a look at
a stock ISO once before you start experimenting.

You can also just re-apply with different settings — every write rebuilds from
the pristine image, never from whatever is on the disc now, so turning an
option off really removes it.

---

## Command line

The same binary, same engine:

```
ModStudio.exe --cli info   "R6 3.iso"
ModStudio.exe --cli list   "R6 3.iso"
ModStudio.exe --cli plan   "R6 3.iso" --preset heavy
ModStudio.exe --cli apply  "R6 3.iso" --set wave_trigger=4 --set wave_size=2
ModStudio.exe --cli cheat  "R6 3.iso" --out 21CC1EC3.pnach
ModStudio.exe --cli revert "R6 3.iso"
ModStudio.exe --cli files  "Ghost Recon.iso" --grep "\.GTF$"
ModStudio.exe --cli art    "R6 3.iso" --out .\art
```

`plan` shows exactly which words would change and prints nothing to the disc.

---

## Building from source

```
pip install pillow pyinstaller
python ModStudio.py            # run the window
python build_exe.py            # produce dist\ModStudio.exe
python tests\run_tests.py      # the end-to-end suite
```

Python 3.10+. The test suite builds a small synthetic disc from a stock
overlay and exercises apply, re-apply and restore against it, so it never
touches a retail ISO.

---

## How it works

* `tcps2/iso.py` — ISO9660 directory and raw sector access.
* `tcps2/soz.py` — the `.SOZ` overlay container: `u32 size` + one zlib stream in
  a fixed extent, loading at a fixed address, so a virtual address is a file
  offset minus a constant.
* `tcps2/vokes.py` — the read-only archive used by Rainbow Six 3's `VOKES*.IMG`
  and by Ghost Recon's `GR.IMG` / `MENU.IMG`.
* `tcps2/art.py` — `.FBZ` screens, used to skin the window with the game's own
  artwork.
* `tcps2/games/*.py` — one profile per disc: the options, and the stock word at
  every address it will touch.
* `tcps2/engine.py` — plan, apply, verify, restore.

Every patch site's stock word is asserted before anything is written, and after
writing the overlay is read straight back out of the disc and the words counted.
If they do not match, the tool says so instead of claiming success.

`docs/PATCHES.md` lists every address, what is at it, and why.

## Credits and scope

This edits your own legally-obtained disc image. No game data is redistributed.

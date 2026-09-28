# Tom Clancy Mod Studio

Three tools that change 23 Tom Clancy games on **PlayStation 2**, **original
Xbox** and **PC**. Point one at a game you already own, pick what you want, and
it edits in place while keeping a full backup of everything it replaces.

No game data is included. You supply your own games.

| | games | source |
|---|---|---|
| **PS2** | Rainbow Six 3, Ghost Recon, Jungle Storm, Ghost Recon 2, Advanced Warfighter, Sum of All Fears, Lockdown | [`ps2/`](ps2/) |
| **Xbox** | Rainbow Six 3, Black Arrow, Critical Hour, Ghost Recon, Island Thunder, Ghost Recon 2, Summit Strike, GRAW | [`xbox/`](xbox/) |
| **PC** | Raven Shield, Vegas, Ghost Recon, Lockdown, Sum of All Fears, GRAW, GRAW 2 | [`pc/`](pc/) |

Downloads are on the [releases page](../../releases).

## Every option says how far it has been proven

This is the part worth reading, and it is why the tools look the way they do.

| badge | what it means |
|---|---|
| **VERIFIED IN GAME** | Someone watched it working. |
| **NOT PLAY-TESTED** | The change was written and read back, so the bytes are known to land — but nobody has confirmed what it looks like in play. |
| **UNTESTED** | Worked out from the game's code. Never applied, never tried. |

Options known *not* to work are hidden rather than shipped as traps. They stay
in the source with the reason they fail, so the next person does not spend a
night re-deriving the same dead end.

For Rainbow Six 3 on PS2 that is 148 options: 54 verified, 55 measured but not
played, 39 untested.

## Before you start

- It edits your game **in place**, keeping a full backup beside it. Anything it
  does can be undone from inside the tool. Back your game up anyway.
- **PS2: close PCSX2 before you apply.** Windows will happily let the tool
  rewrite a disc image the emulator still has open, and the running game then
  streams from a file that no longer matches what it booted. The tool refuses
  to run while it can see PCSX2, but do not lean on that.
- If two cheat files for the same game sit in your PCSX2 `cheats` folder,
  **both are applied**. A downloaded cheat pack next to this one can quietly
  change the game underneath you, and some write executable code every frame.

## Why three trees and not one

They share filenames and lineage, not code. `engine.py` differs by 829 lines
between PS2 and Xbox and 1,661 between PS2 and PC — and it should: the PS2 one
rewrites archives inside an ISO and a compressed overlay, the PC one patches an
installed game folder, the Xbox one works on XISO. Merging them into a single
engine would be a rewrite, not a tidy-up, so each tree keeps its own `gui`,
`engine` and test suite.

Each folder builds and tests on its own:

```
cd ps2  && python tests/run_tests.py --iso "<your R6 3 iso>"
cd xbox && python tests/run_tests.py
cd pc   && python tests/run_tests.py
```

## History

This repository is the merge of three that were released separately as 1.0.
All three histories are preserved — the subtree merges keep every original
commit reachable, including each tree's root.

- `BRAGme/TomClancyPS2-ModStudio` → [`ps2/`](ps2/)
- `BRAGme/TomClancyXbox-ModStudio` → [`xbox/`](xbox/)
- `BRAGme/TomClancyPC-ModStudio` → [`pc/`](pc/)

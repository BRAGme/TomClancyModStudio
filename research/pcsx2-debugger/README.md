# PCSX2 debugger breakpoint files

Copies of the per-game debugger settings used in this research, kept here so
they are versioned. PCSX2 does not read them from this folder.

## Where they go

Copy a file into PCSX2's **`inis\debuggersettings\`** folder, keeping its name.
In this install that is
`E:\Emulators\pcsx2-v1.7.5641-windows-x64-Qt\inis\debuggersettings\`.

Not the top-level `debuggersettings\` folder. PCSX2 never reads that one, and
the Rainbow Six 3 file sat there unloaded until 2026-09-28. When no file is
found, PCSX2 logs the path it tried in `logs\emulog.txt`
(`Debugger Settings Manager: No Debugger Settings file found for game at: ...`).
That line is the authoritative answer for any build.

The name is `SERIAL_CRC.json` and must match the running disc exactly. The CRC
is taken over the boot executable, so a disc whose boot ELF was patched has a
different CRC and will not pick the file up.

PCSX2 loads the file when the debugger opens with the game running, or when a
game starts with the breakpoint list empty. To reload by hand, right-click the
Breakpoints list and choose **Load from Settings**.

## Format

Checked against `pcsx2-qt/Debugger/Breakpoints/BreakpointModel.cpp`:

| field | meaning |
|---|---|
| `X` | **enabled**: `"1"` on, `"0"` off |
| `TYPE` | `"8"` = execute breakpoint (`MEMCHECK_INVALID`); 1-4 are memory checks |
| `OFFSET` | address, hex, no `0x` |
| `SIZE / LABEL` | memory checks only: the length |
| `CONDITION` | optional expression |

The importer inserts each breakpoint at row 0, so the list shows them in
reverse file order.

## Files

### `SLUS-20613_3E571E95.json`: Ghost Recon, SOAF level-port `.MOL` load

Fourteen execute breakpoints, all enabled, inside `MAPLoader::LoadFromMol` and
the `LoadWithSim` code around it. Used to find where a ported Sum of All Fears
level fails. See `research/soaf/port-to-gr.md` §15 and §16.

| label | address | condition | fires when |
|---|---|---|---|
| MOL 01 | `0047C340` | | `LoadFromMol` is entered |
| MOL 02 | `0047C47C` | `s0 == 0x0` | model 1 of 57 starts |
| MOL 03 | `0047C494` | `s0 == 0xc` | model 13 starts |
| MOL 04 | `0047C4A0` | `s0 == 0x18` | model 25 starts |
| MOL 05 | `0047C4BC` | `s0 == 0x24` | model 37 starts (all 36 rooms done) |
| MOL 06 | `0047C4C4` | `s0 == 0x2e` | model 47 starts |
| MOL 07 | `0047C4D4` | `s0 == 0x38` | model 57, the last, starts |
| MOL 08 | `0047C880` | | the model loop finished |
| MOL FAIL A | `0047C3D8` | | the `.MOL` would not open |
| MOL FAIL B | `0047C44C` | | the top chunk is not type 7 |
| MOL FAIL C | `0047C628` | | a model's geometry load returned 0 |
| MOL 09 | `0047CB04` | | `LoadWithSim`: `LoadFromMol` succeeded |
| MOL FAIL D | `0047CCE8` | | `LoadWithSim` abandons the map |
| MOL 10 | `0047C020` | | `LoadPortals` is reached |

`s0` is `LoadFromMol`'s model index for the whole loop body, so the six model
checkpoints sit on six different instructions of it. PCSX2 allows one
breakpoint per address. No address is in a branch delay slot. Conditions are
parsed by PCSX2's expression parser, which reads bare numbers as **hex**, so
they are written with `0x`. The model numbers assume Sum of All Fears'
57-model `TRAINING.MOL`.

The earlier set, seven stops at the entry of each map-load step
(`HandleLoadMap`, `LoadWithSim`, `LoadFromMol`, `LoadPortals`,
`LoadMissionMap`, `LoadObjects`, `HandleLoadSkybox`), is in git history.

**These also stop stock Ghost Recon.** The SOAF probe discs keep Ghost Recon's
boot ELF, so they share its CRC, and every mission load on a normal disc will
stop at them. Untick them or remove the file when not in use.

"Load from Settings" clears the list before loading, and PCSX2 writes this file
back only on "Save to Settings".

### `SLUS-20883_21CC1EC3.json`: Rainbow Six 3, first-person weapon and zone waves

Eight breakpoints and seven saved addresses from earlier Rainbow Six 3 work:
the first-person weapon update (vtable slots `0x174` / `0x170`), the `DZoneWave`
wave logic, and the `mp.soz` Blowfish routines. **Every breakpoint is saved
disabled.** Tick the ones you want. `21CC1EC3` is the main Rainbow Six 3
build. The `29CA5FE0` and `19AA24CC` builds need a copy under their own CRC.

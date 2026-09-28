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

### `SLUS-20613_3E571E95.json`: Ghost Recon, SOAF level-port load steps

Seven execute breakpoints, all enabled, one per step of Ghost Recon's map load.
Each address was checked against Ghost Recon's symbol table, and PCSX2's
debugger resolved the same function names when the file loaded. Used to find
where a ported Sum of All Fears level fails. See
`research/soaf/port-to-gr.md` §15.

| # | address | function |
|---|---|---|
| 1 | `00388D60` | `IkeSimulationMgr::HandleLoadMap` |
| 2 | `0047C9F0` | `MAPLoader::LoadWithSim` |
| 3 | `0047C340` | `MAPLoader::LoadFromMol` |
| 4 | `0047C020` | `MAPLoader::LoadPortals` |
| 5 | `0044D890` | `CGraphicSystem::LoadMissionMap` |
| 6 | `0047B730` | `MAPLoader::LoadObjects` |
| 7 | `003991E0` | `IkeSimulationMgr::HandleLoadSkybox` |

**These also stop stock Ghost Recon.** The SOAF probe discs keep Ghost Recon's
boot ELF, so they share its CRC, and every mission load on a normal disc will
stop seven times. Untick them or remove the file when not in use.

### `SLUS-20883_21CC1EC3.json`: Rainbow Six 3, first-person weapon and zone waves

Eight breakpoints and seven saved addresses from earlier Rainbow Six 3 work:
the first-person weapon update (vtable slots `0x174` / `0x170`), the `DZoneWave`
wave logic, and the `mp.soz` Blowfish routines. **Every breakpoint is saved
disabled.** Tick the ones you want. `21CC1EC3` is the main Rainbow Six 3
build. The `29CA5FE0` and `19AA24CC` builds need a copy under their own CRC.

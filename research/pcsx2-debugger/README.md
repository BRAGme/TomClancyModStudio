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

### `SLUS-20613_3E571E95.json`: Ghost Recon, SOAF level-port first frames

Seven execute breakpoints for the crash that follows a completed load of a
ported Sum of All Fears level. See `research/soaf/port-to-gr.md` §16f and
§16g. Only POST 0 is ticked when the file loads.

| label | address | ticked | fires when |
|---|---|---|---|
| POST 0 | `0050A210` | yes | `RSSoundMgrPS2::SetListenerEnvironment`: the last log line, ~60 ms before the crash |
| POST 1 | `003F9998` | no | frame start, about to call `CGraphicSystem::Render` |
| POST 2 | `003F99E8` | no | about to call `IkeGameMgr::Update` (simulation, scripts, AI, sound) |
| POST 3 | `003F9A30` | no | about to call `SceneCamera::DetermineVisibility` |
| POST 4 | `003F9AC8` | no | about to call `CGraphicSystem::MainFrame` |
| POST 5 | `003F9B4C` | no | about to call `CGraphicSystem::EndOneFrame` |
| POST 6 | `0014655C` | no | inside `IkeGameMgr::Update`, about to update runnable `s0` (object in `a0`) |

POST 1 to 5 are the call sites in `main`'s frame loop, in the order a frame
runs them. The loop runs in menus and on the loading screen too, so they start
unticked: tick them at the POST 0 stop, and each frame then stops five times.
The last one to stop before the crash names the stage that crashed.

POST 6 carries the condition `([[0x005dff48]+0x1dc] >> 0x18) == 0x6`, which
is `RSGameStateMgr::InActionPhase`: the top byte of the game-state word is 6
during a mission. Checked on nine Ghost Recon savestates: every in-mission
state reads 6 (`0x06011A00`) and every loading state reads 5 (`0x05010000`).
The pointer is read through the global because the object moves between runs
(`0x0065EA30`, `0x0065B710`).

None of the addresses is in a branch delay slot. The two earlier sets are in
git history: the seven map-load steps, and the fourteen `.MOL` stops (commit
`fdf65a8`).

**These also stop stock Ghost Recon.** The SOAF probe discs keep Ghost Recon's
boot ELF, so they share its CRC, and POST 0 will stop in any mission whenever
the listener's sound environment changes. Untick it or remove the file when
not in use.

"Load from Settings" clears the list before loading, and PCSX2 writes this file
back only on "Save to Settings".

### `SLUS-20883_21CC1EC3.json`: Rainbow Six 3, first-person weapon and zone waves

Eight breakpoints and seven saved addresses from earlier Rainbow Six 3 work:
the first-person weapon update (vtable slots `0x174` / `0x170`), the `DZoneWave`
wave logic, and the `mp.soz` Blowfish routines. **Every breakpoint is saved
disabled.** Tick the ones you want. `21CC1EC3` is the main Rainbow Six 3
build. The `29CA5FE0` and `19AA24CC` builds need a copy under their own CRC.

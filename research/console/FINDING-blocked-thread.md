# The COMMON.LIN load hang: the sound engine asks the IOP for something that never comes back

Measured 2026-09-19/20 on `canon_team`, from PCSX2 savestates and a Ghidra
database, rather than from watching the screen. Five previous attempts on
this family ended at "the bytes are provably correct and the console still
will not load them". This names the mechanism.

## What the console is doing

Two captures four seconds apart, on a disc carrying `canon_team` and nothing
else — audited with `discaudit.py`, not taken on trust from the build script:

| | wedged | control, same phase |
|---|---|---|
| EE `pc` | `0x00081fc0`, `eret` | in game code |
| `ra` / `sp` | both zero | real |
| EE RAM changing | ~165 bytes/s | 3–5 **MB**/s |
| changing bytes | all below `0x00022000` (kernel timers) | throughout |
| IOP | 429 bytes of 8 MB | busy |
| level name buffer | `Island_a_ss`, never advances | advances |

`ra` and `sp` both zero with `pc` in the kernel means **no runnable thread**.
Not a slow load — nothing is arriving. Not a spin — no game code is running.

## The blocked thread

`syscalls.py` finds every EE syscall stub by its exact shape
(`addiu v1,zero,N ; syscall ; jr ra`), which gives a resume address per kernel
call; a thread blocked in one has that address saved in its control block. So
blocked threads are found without knowing the TCB layout, and every hit is
provably a saved return into a named kernel call.

* wedged: **5** threads parked in `WaitSema`
* control: **4**, at the same kernel slots bar one

The extra one is identical in both wedged captures and in neither control:

```
kernel 0001ac58  = 00114c68   resume address inside WaitSema (syscall 68)
kernel 0001ac5c  = 01ff2b10   that thread's stack
kernel 0001ac4c  = 8001fa98   the object it waits on
```

Its call chain, read off its own stack and identical across both captures:

```
001d0004 -> 00190d04 -> 00101e54 -> 001d3d00 -> 001d6c28
         -> 0050e534 -> 0050d9bc -> 00117fe8 -> WaitSema
```

## What the two ends are

Named from strings their functions actually reference — Ghidra's resolved
references only, see the correction below.

**`0x00117fe8` is a Sony SDK synchronous-request helper.** It calls
`CreateSema`, then `WaitSema`, then `DeleteSema`: issue a request, block until
it completes, tear down. Its neighbourhood (`0x00114000`–`0x0011d000`) is the
SDK kernel layer — `DelayThread`, `TTY: receive error`, and the whole EE
syscall stub table at `0x00114800`.

**`0x0050d790` and `0x0050e470` are inside the DARE sound engine.** The region
`0x004f0000`–`0x00520000` is unambiguous:

```
SndManager.cpp
Error while allocating SPU memory: no more free cluster.
Not enough SPU memory available.
Problem while Allocating memory for Bank %s.
The version of the bank %s is incorrect.
Problem while opening the bank file %s.
Unexpected return value %d of SND_fn_eSynchStreamAsyncSnd.
CEventNameConverter::bGetEventListOffsetAndNbOfEvent> Map %s not found.
ERROR: Cannot find the following event in the *.et? table!
```

## So: what is proven, and what is inferred

**Proven.** A thread is blocked in `WaitSema` that is not blocked on a working
disc. Its chain runs from the sound engine into an SDK create/wait/delete
helper. The IOP is idle at the same moment — 429 bytes of 8 MB.

**Inferred, and consistent with all of it.** The sound engine makes a
synchronous request to the IOP — that is what this helper shape is for, and
`SND_fn_eSynchStreamAsyncSnd` is the DARE call for synchronising an async
sound — and the reply never comes, so the semaphore never signals and the load
never finishes.

**The discriminator this suggests**, which fits every data point and is worth
testing next:

| edit | touches a sound event or bank? | result |
|---|---|---|
| `rpg_speed` | no | works |
| `split_wheel` | no | works |
| `ai_cover` | no | works |
| `ai_sidearm` | reuses an EXISTING event | works |
| `ss_man_down` | a "man down" callout | hangs |
| `canon_team` | changes the operative, so the voice bank | hangs |

That is a better rule than the one it replaces. "Re-assembling bytecode
hangs" is dead — `ai_sidearm` re-assembles 360 bytes across 17 runs and
plays. A semaphore that never signals was never a malformed-bytecode story.

`ss_man_down` wedges at the same kernel address but EARLIER: its level-name
buffer still reads `menu` and not one byte of game memory changes. Same
mechanism, different distance travelled.

## Two corrections worth keeping

**A first pass read `0x001181a0` as a call to `DeleteSema`.** It is the
RETURN ADDRESS from `WaitSema` — the `jal` sits eight bytes earlier. Reading
the whole stack caught it; reading one word did not.

**A first pass at naming the functions was wrong and confidently so.** A
script paired `lui` with the following `addiu` itself to rebuild addresses.
That produced three "hits" at three different offsets into the SAME string
and a conclusion that the function was a file loader keyed on extension. The
string was `_pictureSpatialScalableExtension is not supported`, sitting in
Sony's MPEG decoder, and "Extension" there is an MPEG-2 bitstream extension
header. Ghidra's MIPS Constant Reference Analyzer already resolves those
pairs properly; `RealRefs.java` uses only what it resolved, and anything it
did not resolve is not evidence.

## Tooling note

Stock Ghidra cannot disassemble EE code — `lq`/`sq` (`0x1E`/`0x1F`) appear in
nearly every prologue and MIPS32 stops there, giving 8,864 "functions" of 4
and 8 bytes. With `chaoticgd/ghidra-emotionengine-reloaded` (language
`r5900:LE:32:default`) the same image yields 10,085 functions with real sizes
and real cross-references. Everything above depends on that.

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

---

# Update 2026-09-20: both hangs are ONE bug, in the sound engine's IOP RPC

`ss_man_down` and `canon_team` were treated as two faults that happened to
look alike. They are the same fault.

## The test

Phase-independent, because the two wedge at different points — `ss_man_down`
with the level buffer still reading `menu`, `canon_team` after `Island_a_ss`.
What is comparable is the SHAPE of the stall: which kernel call each blocked
thread sits in, and which subsystems its stack walks through.

| capture | 5th WaitSema thread | sound frames in its stack |
|---|---|---|
| `ss_man_down` wedged | kernel `0001ac58` | `0050d9bc`, `0050e370` |
| `canon_team` wedged | kernel `0001ac58` | `0050d9bc`, `0050e534` |
| control, loading | **absent** | **none, in any thread** |

Same kernel slot, the same sound frame `0x0050d9bc` in both, and the working
disc has no blocked sound thread at all. The two edits enter through
different callers — `0050e370` against `0050e534` — which is why one wedges
before the level is named and the other after. Same bug, different trigger.

## What the call actually is

`FUN_0050d790` decompiles to a SIF RPC wrapper:

```c
do { lVar1 = FUN_001181e0(0x5cccd0); } while (lVar1 != 0);   // channel busy?
FlushCache(0);                                                // let the IOP see it
FUN_00117fe8(DAT_005cccd0, uStack_48, 0, 0x6f0c80, uStack_58, uVar4, uStack_54, 0);
```

That argument list is `sceSifCallRpc(clientData, fno, mode, sendBuf, sendSize,
recvBuf, recvSize, endFunc)` with **mode 0 — blocking**. So `FUN_00117fe8` is
`sceSifCallRpc`, which is why it is built from CreateSema / WaitSema /
DeleteSema, and `FUN_0050d790` is "send a sound command to the IOP and wait".
The command is a packed word dispatched on `& 0xfff0000`.

**So the level load stalls on a blocking sound RPC to the IOP, and the IOP is
idle at the same moment — 429 bytes of 8 MB changing.**

## What was ruled OUT along the way

**It is not a missing sound bank.** The obvious reading of `ss_man_down` is
that it skips `Init()`, whose only job is `AddSoundBankName("X_Voices_Price")`,
so the bank is never registered. Measured instead of assumed: the voice-bank
names are resident identically in the wedged and working split-screen
captures — same counts, same addresses, for `X_Voices_Price`, `_Weber`,
`_Loiselle`. Bank residency is not the discriminator.

**The specific stuck request is NOT identified.** The send buffer at the fixed
address `0x006f0c80` is reused, so it holds the last request written rather
than the stalled one — the wedged `canon_team` capture and the working control
both hold near-identical `PistolUSP` requests, with identical
`sceSifClientData` at `0x005cccd0`. Anyone continuing should get the request
from the blocked thread's own frame, not from that buffer.

## Where that leaves it

Proven: one bug, not two; it is in the sound engine; it is a blocking IOP RPC
that does not come back; the working disc never blocks there.

Not proven: which request, and why the IOP does not answer it. The next step
is the blocked thread's own arguments — `uStack_48` (the command word) and the
send size are on its stack at a known offset from `sp = 0x01ff12a0`
(`ss_man_down`) and `0x01ff2b10` (`canon_team`).

---

# Update: the stuck command word, read off the blocked thread

| | `ss_man_down` | `canon_team` |
|---|---|---|
| command (`fno`) | **`0x80020012`** | **`0x80020010`** |
| send buffer | `0x006f0c80` | `0x006f0c80` |
| send size | `0x10` | `0x20` |
| receive buffer | `0` (no reply wanted) | `0x006f0d00` |
| WaitSema semaphore | `0x13` | `0x14` |

## How it was read, and why the first attempt was wrong

The first attempt located `FUN_0050d790`'s frame from a return address on the
stack and read `frame+0x78` (where `sw a0,0x78(sp)` puts the command). It gave
`0` — and the same frozen thread reported the return address at two different
places four seconds apart, which a stopped thread cannot do. Those were stale
copies, stack litter, not the live frame. A zero read from the wrong place is
not a measurement.

The registers are the right source, because `FUN_00117fe8` moves its arguments
into callee-saved `s` registers, which survive the wait. The EE kernel pushes
a 32-entry, 128-bit-stride register context at the blocked thread's `sp`;
`zero` reads 0 and `ra` reads `0x001181a0` — the return from the `WaitSema`
call site — which confirms the base and stride.

Identified by three values that were already known independently: `s1 =
0x006ed990` is the `sceSifClientData` (matches `DAT_005cccd0`), `s5 =
0x006f0c80` is the send buffer (matches `addiu a3,a3,0xc80`), leaving `s6` as
`fno`.

**The clincher is the size arithmetic.** The marshaller `FUN_0050e9e0` sets
send/receive sizes per command — `0x80020012` gets 8 and 0, `0x80020010` gets
`0x14` and 4 — and `FUN_0050d790` then rounds each up to 16:

```c
uStack_58 = uStack_58 + 0xf & 0xfffffff0;
```

`8 -> 0x10` and `0x14 -> 0x20`, which is exactly what the live `s2` holds in
each capture. And `ss_man_down`'s zero receive size explains its `s4 = 0`
against `canon_team`'s `0x006f0d00`. Every value agrees.

## What it means

Both are ordinary `0x20000`-class sound commands, marshalled by the same
function, differing only in the low byte. Neither is malformed. Note
especially that `ss_man_down`'s command asks for **no reply at all** — receive
size 0 — and the thread is still parked in `WaitSema`, because mode 0 makes
`sceSifCallRpc` wait for the RPC to complete whether or not it returns data.

So the question is no longer "what did it ask for". It is **why the IOP does
not complete an otherwise normal request** — and the IOP is idle, not busy.
The next thing to check is whether the IOP-side sound RPC server is bound and
alive at that moment, since an unbound or dead server would park every caller
exactly like this regardless of which command it sent.

# The COMMON.LIN load hang is a semaphore that never signals

Measured 2026-09-20 on `canon_team`, from PCSX2 savestates rather than from
watching the screen. The five previous attempts on this family all ended at
"the bytes are provably correct and the console still will not load them";
this is the first time the hang itself has been characterised.

## What the console is doing

Two captures four seconds apart, on a disc carrying `canon_team` and nothing
else (audited with `discaudit.py`, not taken on trust from the build script):

| | wedged | control, same phase |
|---|---|---|
| EE `pc` | `0x00081fc0`, `eret` | in game code |
| `ra` / `sp` | both zero | real |
| EE RAM changing | ~165 bytes/s | 3–5 **MB**/s |
| changing bytes | all below `0x00022000` (kernel timers) | throughout |
| IOP | 429 bytes of 8 MB | busy |
| level name buffer | `Island_a_ss`, never advances | advances |

`ra` and `sp` both zero with `pc` in the kernel means **no runnable thread**.
It is not a slow load — nothing is arriving. It is not a spin — no game code
is running.

## The blocked thread

`syscalls.py` finds every EE syscall stub in the overlay by its exact shape
(`addiu v1,zero,N ; syscall ; jr ra`), which gives a resume address per kernel
call; a thread blocked in a kernel call has that address saved in its control
block. Comparing the two discs:

* wedged: **5** threads parked in `WaitSema`
* working: **4**, at the same kernel slots minus one

The extra one is the same in both wedged captures and in neither working
capture:

```
kernel 0001ac58  = 00114c68   resume address inside WaitSema (syscall 68)
kernel 0001ac5c  = 01ff2b10   that thread's stack
kernel 0001ac4c  = 8001fa98   the object it is waiting on
```

Its call chain, identical across both captures, read off its stack:

```
001d0004 -> 00190d04 -> 00101e54 -> 001d3d00 -> 001d6c28
         -> 0050e534 -> 0050d9bc -> 00117fe8 -> WaitSema
```

`0x00117fe8` calls `CreateSema`, then `WaitSema`, then `DeleteSema`. That is a
synchronous "issue a request and block until it completes" helper, and the
thread is stuck in its wait. **Something the load asks for never reports
completion.** `0x0050d790` and `0x0050e470` are the game-side callers above
it and are the next thing to identify.

## What this rules out

The long-standing theory was about the *rewrite path* — that edits which
re-assemble bytecode hang and edits which poke bytes do not. That is retired:
`ai_sidearm` re-assembles 360 bytes across 17 runs and plays. A hang that is
a semaphore never signalling is not a malformed-bytecode story at all; it is
a request that goes out and never comes back.

`ss_man_down` wedges at the same kernel address but EARLIER — its level-name
buffer still reads `menu` and not one byte of game memory changes. Same
mechanism, different distance travelled.

## The tooling gap to close next

Stock Ghidra cannot disassemble past the first `lq`/`sq` (opcodes `0x1E`/
`0x1F`), which the Emotion Engine uses in nearly every prologue, so
auto-analysis truncates functions to one or two instructions across the whole
image — 8,864 "functions" of size 4 and 8. `eedis.py` decodes enough to answer
"what does this call, does it reach a syscall, where does it end", which is
what produced everything above, but it is not a substitute.

A real Emotion Engine processor module for Ghidra would make
`0x0050d790` and `0x0050e470` readable, and those two names are probably the
whole answer. That needs downloading and installing an extension, so it is a
decision to take deliberately rather than a step to slip in.

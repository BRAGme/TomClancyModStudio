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

---

# Update: is the IOP server bound? Not the fault — but not fully answered either

## What was checked

`0x005cccd0` holds a POINTER; the `sceSifClientData` is at `0x006ed990`.
Dumped whole across seven captures — three working, four wedged — every field
is identical except:

| field | working | wedged |
|---|---|---|
| `+0x00` packet in flight | `00000000` | `20657880` |
| `+0x08` semaphore id | `14` | `14` / `13` |
| `+0x14` | `0009e178` | `0009e178` — **the same** |

`+0x14` is an IOP address and it is **identical in wedged and working
captures**, so whatever the EE is bound to, it is bound to the same thing when
it works and when it hangs. **An unbound server is not the fault.**

## The in-flight packet, and an independent confirmation

`+0x00` is the in-flight packet: `0x20657880`, the uncached view of EE
`0x00657880`. Read there, the layout matches ps2sdk's `SifRpcPktHeader_t`
exactly — a 16-byte `sif_cmd_header`, then `rec_id`, `pkt_addr`, `rpc_id` —
because `+0x14` reads back `20657880`, its own address.

That gives a **second, independent reading of the command word**, from a
different structure than the register context:

```
+0x20 command   80020010 (canon_team)      80020012 (ss_man_down)
+0x24 send size 00000020                   00000010
+0x28 recv buf  006f0d00                   00000000
+0x2c recv size 00000010                   00000000
```

Every value agrees with what the blocked thread's `s` registers held. The
command-word identification is now confirmed twice over.

`rec_id` at `+0x10` reads **4 in both working captures and 5 in all four
wedged ones** — the packet is outstanding rather than completed. That
confirms the RPC is stuck; it does not explain why.

## A wrong turn, recorded

`+0x14` was read as the server-record pointer, and the IOP memory at
`0x0009e178` dumped expecting a `SifRpcServerData`. It is not one — it is a
buffer, holding the request payload as text: `\PistolUSP.bfz` and `.SB1` for
`canon_team`, `WRD...enu.bfz` for `ss_man_down`. Useful in itself (the sound
RPC is a bank load BY NAME, `.SB1` being the DARE bank extension) but it is
not a server struct, so "the server is bound" cannot be concluded from it.

## Honest status

**Answered:** the binding is not the discriminator. The EE is talking to the
same IOP address when it works and when it hangs, the packet is addressed
there in both, and the command itself is ordinary and correctly marshalled.

**Not answered:** whether the IOP-side server object still exists and its
thread is alive and servicing. That needs the IOP's RPC service registry,
which has not been located — the address in the client data leads to a
buffer, not the registry. Until that is found, "the IOP never answers" is
where the evidence stops.

---

# Update: the request REACHES the IOP and is never serviced

## The solid finding

The RPC packet is present in IOP RAM at `0x00005e58` in every wedged capture
and absent in every working one:

| capture | packet in IOP low memory |
|---|---|
| SP in-game (works) | no |
| SS loading (works) | no |
| SS loading, earlier (works) | no |
| `canon_team` wedged | **yes**, `0x005e5c` |
| `canon_team` +4s | **yes** |
| `ss_man_down` wedged | **yes**, `0x005e5c` |
| `ss_man_down` +4s | **yes** |

Four of four wedged, zero of three working, across BOTH bugs. And it is
unmistakably the same request the EE sent — every field matches the EE-side
packet and the blocked thread's registers:

```
005e58  psize      00002000 / 00001000
005e5c  dest buff  0009e178
005e68  rec_id     00000005      (outstanding)
005e6c  pkt_addr   20657880
005e74  client     006ed990
005e78  COMMAND    80020010 / 80020012
005e7c  send size  00000020 / 00000010
005e80  recv buff  006f0d00 / 00000000
```

**So the EE sends it, the IOP receives it, and it is never completed** — while
the IOP sits idle, 429 bytes of 8 MB changing. This is not a lost message and
not a busy IOP. The request arrives and nothing services it.

## The registry was NOT found, and the attempts are recorded

Three structural identifications were tried and all three were wrong. They are
written down so nobody repeats them:

1. **EE client data `+0x14`** (`0x0009e178`) read as the server-record
   pointer. It is a BUFFER — the IOP memory there holds the request payload as
   text (`\PistolUSP.bfz`, `.SB1`).
2. **IOP words pointing at that buffer** read as `SifRpcServerData_t` records.
   They are copies of the RPC packet, not server records.
3. **`0x00005e38+0x08`** read as a `SifRpcDataQueue_t` link because it differs
   between working (`1`) and wedged (`0x0001ce3c`). `0x0001ce3c` contains MIPS
   code — `addiu v0,zero,1`, `lw ra,0x84(sp)`, `jr ra` — and is byte-identical
   in the working capture, because code does not change. It is a code address,
   most likely a saved return, not a queue link.

The pattern in all three: a plausible ps2sdk layout was assumed and the bytes
were read through it. Each time the data said otherwise, and each time the
tell was the same — a field that "should" be a pointer resolving to something
that is not the right kind of object.

**Blind layout-matching against IOP structures has reached its limit here.**
The next tool is the IOP's own module list, or disassembling the IOP image as
its own target, rather than another guess at a struct offset reached through
an EE pointer.

---

# Update: the IOP module map, and the SPU-stall idea refuted

## What is loaded on the IOP

From name strings in the IOP image — no layout assumptions:

```
0x01be70  IOP_SIF_manager        / PsIIsifman
0x01e2c0  IOP_SIF_rpc_interface  / PsIIsifcmd / "SIFCMD/RPC"
0x0222c4  LGAUD.IRX                            <- the game's audio IRX
0x030714  RPC.IRX
0x088690  Sound_Device_Library   / PsIIlibsd
0x098800  SPU driver data (E_SPU_DMA_TRANSFER_IDLE / _RUNNING,
                           SND_C_INVALID_SPU_TRANSFER_HANDLE)
```

## The state diff, wedged against working

289,549 bytes differ overall — two different discs at different moments, so
most of that is bank data legitimately differing. The useful part is how
SMALL the differences are inside the modules that matter:

| region | differing bytes |
|---|---|
| sifman + sifcmd/RPC | **33** |
| LGAUD.IRX + RPC.IRX | **2** |
| libsd + SPU driver | **15** |

## An idea that looked right and is not

The SPU driver holds a transfer state and a handle, and at first reading they
looked like the answer:

```
working   state 0   handle ffffffff   (SND_C_INVALID_SPU_TRANSFER_HANDLE)
wedged    state 1   handle 01076651   (a live transfer)
```

A sound bank DMA that starts and never finishes would explain everything. It
is wrong. Checked across all seven captures, the handle CHANGES between the
two wedged captures of the same hang (`01076651` then `0106ff55`), and
`ss_man_down` reads idle in one capture and running in the next. Transfers are
completing and new ones starting.

**So the IOP sound driver is alive and doing work.** The request is not
unserviced because the driver is dead, and the SPU DMA is not stuck.

The one stable discriminator in that region is a counter at `0x099f58`:
**4 in all three working captures, 6 in all four wedged ones.** What it counts
is not yet known.

## Status

Still standing, and now with the driver's health established: the EE sends an
ordinary sound command, the IOP receives it — the packet is in IOP low memory
in four of four wedged captures and none of three working — the IOP sound
driver is alive and transferring, and the request is still never completed.

The registry hunt is not finished. The IOP image is now a Ghidra target in its
own right (MIPS:LE:32, base 0), which is the tool that was missing: with
`LGAUD.IRX` and `sifcmd` located, the RPC registration can be found in code
rather than guessed at from EE-side pointers.

---

# Update: the sound RPC service, found — and it is bound in every capture

## The registration

IRX modules declare their imports in tables with magic `0x41E00000`, a
**20-byte** header (name at `+0x0c`, stubs from `+0x14`), then 8-byte stubs of
`j <target>` / `li $0, <function id>`. That makes every imported call findable
exactly. In `sifcmd`: 14 is `InitRpc`, 15 `BindRpc`, 16 `CallRpc`,
**17 `RegisterRpc`**, 19 `SetRpcQueue`.

Twenty-one `sceSifRegisterRpc` call sites exist in the image. The sound one is
identified without ambiguity, because `a3` is the server buffer and the buffer
was already known:

```
call 0008efec   a1 = 12345678   a3 = 0009e178   <- the sound service
```

`0x0008efec` is inside `Sound_Device_Library` / `PsIIlibsd` (`0x088690`), so
the service is registered by the sound device library. **The service id is
`0x12345678`** — a placeholder, which is worth noting for what it says about
the module.

## The server record, in all seven captures

Searching for that sid finds the `SifRpcServerData_t` at IOP `0x007e169c`, at
the same address in every capture:

```
sid   12345678
func  0008f00c    the handler, in the sound library
buff  0009e178
size  0x20 (canon_team) / 0x10 (ss_man_down)
...   client 006ed990, pkt 20657880, command 80020010 / 80020012
```

**The server is registered, bound, and its handler pointer is intact in the
wedged captures exactly as in the working ones.** The record even holds the
in-flight request.

`0x007e169c` is also the value in the EE client data at `+0x24` — the server
pointer was in there all along. Earlier attempts tested `+0x14` and `+0x1c`
and missed it, which is what sent three structural guesses astray.

## What is now excluded

* the server is not unbound
* the server record is not missing or corrupted
* the handler pointer is intact
* the request reaches the IOP (packet present, 4/4 wedged, 0/3 working)
* the IOP sound driver is alive (SPU transfer handles change between captures)

Everything on the path exists and is correct. The request is delivered to a
registered server with a valid handler, and is not completed.

**What is left** is the server's own thread: whether the RPC loop that should
dispatch to `0x0008f00c` is running, blocked or dead. That is an IOP thread
question, and it is the next thing to look at.

---

# RESOLVED TO A FUNCTION: the IOP sound handler never returns

The `SifRpcDataQueue_t` for the sound service sits at IOP `0x007e1684` — its
`link` and `end` both point at the server record at `0x007e169c`, which is what
identifies it. Its `active` flag is unanimous across every capture:

| | thread_id | active |
|---|---|---|
| SP in-game (works) | `01076651` | **0** |
| SS loading (works) | `01076651` | **0** |
| SS loading, earlier (works) | `01076651` | **0** |
| `canon_team` wedged | `01076651` | **1** |
| `canon_team` +4s | `01076651` | **1** |
| `ss_man_down` wedged | `01076651` | **1** |
| `ss_man_down` +4s | `01076651` | **1** |

Same thread id and same queue links throughout. `active` is set when the loop
has taken a request and is servicing it, and cleared when the handler returns.

**So the RPC loop thread is not idle and not waiting for work. It dequeued the
request, dispatched to the handler, and never came back.**

## The chain, end to end

1. The DARE sound engine issues a **blocking** `sceSifCallRpc` (mode 0),
   command `0x80020010` (`canon_team`) or `0x80020012` (`ss_man_down`),
   from `FUN_0050d790`.
2. The EE thread blocks in `WaitSema` — TCB `0x0001ac58`, a fifth blocked
   thread the working disc never has.
3. The packet reaches the IOP: present in IOP low memory in 4 of 4 wedged
   captures, 0 of 3 working.
4. The IOP service is registered and intact — sid `0x12345678`, handler
   `0x0008f00c`, registered at `0x0008efec` in the sound device library.
5. The RPC loop thread `0x01076651` dequeues it and sets `active`.
6. **The handler never returns.** `active` stays 1, no reply is sent, the EE
   thread waits forever, and the level load never finishes.

## Where the fault is

Inside `0x0008f00c` — the sound library's RPC handler — or something it
calls. Everything upstream of it has been measured and is correct.

That is a single function in `Sound_Device_Library` / `PsIIlibsd`, and the IOP
image is now imported as its own Ghidra target (`MIPS:LE:32`, base 0), so it
can be read directly rather than inferred.

## Why it took so long, in one line

Every wrong turn in this file came from assuming a struct layout and reading
bytes through it. Every correct step came from anchoring on a value already
known independently — the buffer address, the send size arithmetic, the
service id — and letting that identify the structure instead.

---

# Update: the handler decompiled, and an attractive answer refuted

## The path, all the way down

```
0x0008f00c   the registered RPC handler
             if (fno > 0xffff) -> next;  our fno is 0x8002001x, so always
0x00091f20   large-fno path, dispatches on & 0x0fff0000 -- the SAME split
             the EE side uses (0x40000 / 0x20000 / 0x10000)
0x00093778   the 0x20000 class
   -0x7ffdfff0  canon_team  (0x80020010): reads 5 words, then a size/bounds
                calculation against FUN_000934f4
   -0x7ffdffee  ss_man_down (0x80020012): reads 2 words, then
                FUN_00094220 / FUN_00095940 / FUN_00095828 / FUN_00098488
```

Both are ordinary, well-formed command handlers.

## The answer that looked certain and is wrong

Walking the call graph from `0x00093778`, only four blocking sites are
reachable, all funnelling through `FUN_000955c0`, which is:

```c
FUN_00092130();                                   // lock
while (puVar1 = PTR_DAT_00099f78, PTR_DAT_00099f78 == 0) {
    FUN_00092220();                               // unlock
    FUN_0008fca8(1000);                           // delay
    FUN_00092130();                               // lock
}
PTR_DAT_00099f78 = *(void **)(PTR_DAT_00099f78 + 0x30);
```

A free-list allocator of 0x34-byte records with **no timeout and no failure
path**. If the pool is exhausted it spins for ever, the handler never
returns, the queue stays `active`, and the EE waits on its semaphore
permanently. It explains the idle IOP (a delay loop, not a hot spin), the
still-working SPU transfers, and why two different edits hang the same way --
each adding one more concurrent sound than the pool holds.

**It is wrong.** The free-list head was measured in all seven captures:

| | free-list head | counter `0x099f58` |
|---|---|---|
| works (3) | `000cb434` / `000cb468` | 4 |
| wedged (4) | `000cb468` / `000cb434` | **6** |

The list is **not empty** when wedged — the same values as working. The
handler is not sitting in that loop.

The reachability analysis that pointed there is also weaker than it looked:
it follows only direct `jal` edges inside the sound library, and this code
uses function pointers, so "only four blocking sites are reachable" is an
underestimate rather than a proof.

## Where it actually stands

The handler path is mapped and both command branches are identified. The one
stable discriminator in the sound driver's data remains the counter at
`0x099f58` — **4 in all three working captures, 6 in all four wedged** — and
what it counts is still unknown. That is the next thread to pull, and it is a
measurement, not a theory.

---

# Update: 0x00099f58 is the streaming thread's flag word, and bit 1 is stuck

Not a counter. It is a flag word belonging to `FUN_00094954`, the sound
driver's service thread, whose first act is to test it:

```c
if ((DAT_00099f58 & 1) != 0) { DAT_00099f58 &= ~1; return 0; }   // bit 0 = exit
```

Every access to it was located by resolving `lui` + offset pairs: **5 writes,
12 reads**, all inside `0x094c00`–`0x095b00`, and all within that thread's own
code:

```
094cec  and v0,v1,-3     CLEARS bit 1
094d30  ori v0,v0,0x2    SETS bit 1   (and sets a local flag to 1)
094d4c  ori v0,v0,0x2    SETS bit 1   (same)
095330  and v1,a0,-2     clears bit 0, the exit request
```

So bit 1 is set and cleared by the thread itself — a "work still pending"
flag. And the measured values say it never clears:

| | value | bit 1 |
|---|---|---|
| works (3 captures) | **4** = `0b100` | clear |
| wedged (4 captures) | **6** = `0b110` | **set** |

## What that thread does

The same loop seeks and reads in 16 KB chunks:

```c
FUN_0008fb08(DAT_00099f94, *(uint *)(pcVar7 + 0x28) & 0xffffc000, 0);   // seek
iVar4 = FUN_0008faf8(DAT_00099f94, (&PTR_DAT_00099f9c)[...], 0x4000);   // read
```

`DAT_00099f94` is a file handle. This is the **bank streaming loop** — which
is exactly the work the stuck RPC command asked for, and matches the request
payloads seen earlier (`\PistolUSP.bfz`, `.SB1`).

## Where this leaves it

The chain now reads: the sound engine asks the IOP to load a bank; the RPC
handler hands the work to the streaming thread; the streaming thread's
"pending" bit is set and never cleared; the handler never returns; the EE
waits on its semaphore for ever.

**Not yet proven** is why the pending work never completes — whether the file
read blocks, or the loop's completion condition is never met. That is the next
measurement: the file handle `DAT_00099f94` and the chunk state at
`0x00099f84` / `0x00099fac`, compared across the captures.

Given four attractive answers have already been refuted here by exactly this
kind of check, that comparison should be made before anything is claimed.

---

# The measurement: the flag claims work that does not exist

The whole streaming-thread state block, all seven captures:

| address | meaning | works (3) | wedged (4) |
|---|---|---|---|
| `0x099f58` | flags | **4** (`0b100`) | **6** (`0b110`) |
| `0x099f84` | pending work list | `0` | **`0`** |
| `0x099f94` | file handle | `ffffffff` | **`ffffffff`** |
| `0x099f88` | free list | `000cb258` | `000cb258` |
| `0x099f5c` | semaphore | `01072217` | `01072217` |

**The flags word is the ONLY stable discriminator in the block.** Everything
else that differs — `0x099f78`, `0x099f98`, `0x099fa4/a8`, `0x099fac` — varies
per capture rather than by wedged-versus-working, so none of them is the
fault.

## What that combination means

Measured, not inferred:

* bit 1 of the flags — the thread's own "work still pending" bit — is set in
  all four wedged captures and clear in all three working ones
* the pending work list is **empty**, in the wedged captures too
* the file handle is **invalid** (`ffffffff`), in the wedged captures too
* the free list is healthy and the semaphore id is unchanged

So the streaming thread is claiming outstanding work while holding no work
item and no open file. Its loop waits on `FUN_0008fd04(DAT_00099f5c)`, then
drains `0x099f84` — which is empty — so there is nothing for it to do and
nothing that will clear the bit.

**Inferred from that:** it is a lost wakeup, or a flag set by a producer whose
enqueue never happened. Either way the bit can never clear by itself, the RPC
handler that waits on it never returns, and the EE waits on its semaphore for
ever.

## What this rules out, finally

Not the bytes being edited. Not the LIN container, the package rebuild, the
chunk packing or the declared sizes — all of which were tested and cleared
over five earlier attempts. Not a missing bank, not an unbound RPC server, not
a dead sound driver, not an exhausted pool, not a stalled SPU DMA. The edits
are delivered intact and the request is well-formed; the sound driver's own
bookkeeping goes inconsistent and the wait never ends.

That is why "the bytes are provably correct and the console still will not
load them" was true every time it was written. It was true. The fault was
never in the bytes.

---

# CORRECTION: bit 1 is a cache-hit flag, not "work pending"

The previous section read bit 1 of `0x00099f58` as "work still pending" and
concluded that the thread was claiming work it did not have. **That is wrong.**
Reading the branches that actually set and clear it:

```c
        DAT_00099f58 = DAT_00099f58 & 0xfffffffd;   // CLEARED after a real read
        ...
      else if ((puVar10 == 0) && (-1 < iVar8)) {
        DAT_00099fac = (byte)iVar8;
        DAT_00099f58 = DAT_00099f58 | 2;            // SET when no read was done
      }
      else {
        DAT_00099f58 = DAT_00099f58 | 2;            // SET when no read was done
      }
      ...
      if ((DAT_00099f58 & 2) != 0) goto LAB_00094f18;   // take the buffered path
```

Bit 1 means **"this chunk came from a buffer, not from disc"** — a cache-hit
flag. The thread sets it precisely in the branches where it skipped the read.

So `4` versus `6` says the last streaming operation was served from the buffer
in the wedged captures and from a real read in the working ones. That is
consistent with a stall, but it is a **symptom**, not the fault, and the
earlier reading inverted its meaning.

What survives the correction: bit 1 is written only by this thread, in its own
loop, at `0x094d30` and `0x094d4c`, and cleared at `0x094cec`. Nothing outside
the thread touches it. The 4-versus-6 split is still a perfectly stable
discriminator across all seven captures and both bugs — it is the meaning that
was misread, not the measurement.

## Why a breakpoint was not used

PCSX2's debugger is GUI-only, and driving it is out of scope here. PINE has no
breakpoint opcode, and its memory reads go through `vtlb_ramRead`, which is
EE-side — it cannot read IOP RAM at all. So the dynamic evidence has to come
from savestate sampling: capture repeatedly through a load that works and one
that hangs, and find the first capture where the state diverges.

That is the honest next step, and it needs a boot rather than more static
reading.

---

# THE TIMELINE: the load runs fine, then retries one chunk for ever

Sampled a hanging Island Estate split-screen load every 1.5s from the moment
it started (slots 40-53), against the working series captured the same way
(slots 30-35). Disc audited off the disc first: 7 overlay words, all
split-screen fixes, 3 data files, `COMMON_SS.LIN` only.

```
slot  level         flags qactive  EE churn / 1.5s
40    Entry         4     1        -
41    island_a      4     0        4,014,720
42    island_a      6     0        4,499,264
43    Island_a_ss   4     0        6,614,144
44    Island_a_ss   4     0        6,099,456
45    Island_a_ss   4     0        6,419,904     <- last healthy
46    Island_a_ss   6     1          481,728     <- THE COLLAPSE
47    Island_a_ss   6     1            3,200
48-53 Island_a_ss   6     1        ~2,000        <- dead
```

**The load runs normally for seven and a half seconds and about 20 MB of work,
then stops dead in a single 1.5s step**, with the RPC queue's `active` flag
going 0 -> 1 at exactly that step. The request that never returns is issued
AT the collapse; it was not pending all along.

## What is frozen, and what is not

The 16 bytes that changed across the collapse point at one thing:

```
099fa4   ffffffff -> 03864000    the streaming buffer address
```

Through the healthy phase that address advances at every capture --
`005cc000`, `006dc000`, `034c4000`, `036b4000` -- and from the collapse it
reads `03864000` in **eight consecutive captures over twelve seconds**.

Meanwhile the SPU transfer state at `0x099a78` **oscillates** after the
collapse: RUNNING, idle, RUNNING, RUNNING, idle... with the handle changing
between `0106ff55` and `01076651`. Transfers really are starting and
completing.

**So the driver is not stalled. It is alive, transferring, and re-transferring
the SAME buffer indefinitely without ever advancing to the next chunk.**

## Two earlier claims corrected by this

**The stalled SPU DMA is confirmed NOT the cause** — the earlier refutation
was right, and the timeline shows why: transfers cycle throughout the hang.

**The 4-versus-6 flags discriminator is retired.** `flags` reads 6 at slot 42,
mid-load, in a perfectly healthy stretch, and returns to 4. It is a normal
transient, and the apparent "stable discriminator" was an artifact of only
ever sampling end states. `pend` and `fhandle` never move in either series, so
they were never relevant either.

That is three leads closed by one properly sampled timeline, which is the
argument for sampling through a failure rather than photographing its
aftermath.

---

# THE CHUNK: it dies on the final partial chunk of a bank

Tracking the streaming offset and length through both series:

| | offset `0x09e180` | length `0x09e184` |
|---|---|---|
| working, 31-35 | advancing: `0e0000`, `010000`, `180000`, `2c0000`, `400000` | **`00010000`** every capture |
| hanging, healthy 43-45 | advancing: `190000`, `380000`, `4b0000` | **`00010000`** |
| hanging, collapse 46 | `00540000` | **`00004680`** |
| hanging, dead 47-53 | `00540000` frozen | **`00004680`** frozen, 8 captures |

**The normal streaming length is `0x10000` — 64 KB. At the collapse it becomes
`0x4680`, which is 18,048 bytes and NOT a multiple of the `0x4000` read unit.**
That is a short, unaligned remainder: the final partial chunk of the file. The
offset freezes at `0x540000`, so the bank ends at `0x544680`, about 5.52 MB.

It also matches the clamp already decompiled on the EE side, in the caller of
the RPC wrapper:

```c
iVar4 = FUN_000934f4(local_34);                       // the file's size
if (iVar4 < (int)(local_30 + local_2c)) {             // request runs past it
    local_2c = (iVar4 - local_30) + 0xfU & 0xfffffff0;  // clamp to the tail
```

So both sides agree this is the read-the-tail path.

## What is proven, and what is inferred

**Proven.** The streaming length is `0x10000` in every healthy capture of both
series, and `0x4680` in all eight captures after the collapse. The offset
advances throughout the healthy phase and is frozen afterwards. SPU transfers
continue to start and complete during the hang, so the driver is alive and
repeating the same short read.

**Inferred.** That the short final chunk is what it cannot complete —
consistent with every measurement, but the failing arithmetic inside the loop
has not been read.

This is the first explanation that accounts for the SHAPE of the failure
rather than only its end state: why the load runs normally for 7.5 seconds and
20 MB, why it stops at one specific instant, why the driver stays alive, and
why nothing about the edited bytes is wrong. The edits change WHICH bank is
asked for. A bank whose length leaves this particular remainder hits a tail
case the streaming loop does not get past.

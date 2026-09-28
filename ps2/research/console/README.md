# Asking the console instead of the screen

Three questions came up over and over while chasing the COMMON.LIN load
hangs, and none of them could be answered by looking at the game:

* **What is actually on this disc?** — `discaudit.py`
* **Is it wedged, or just slow?** — `pine.py` + `p2s.py`
* **Where was it when it stopped?** — `p2s.py`

Every one of them was, at some point, answered wrongly by reasoning instead
of measuring. An option was withdrawn on a disc that turned out to carry a
second edit nobody accounted for; a hang was called a slow load; a default
was changed and read as though it had taken effect while a saved profile went
on applying the old value. These scripts exist so those are one command each.

## discaudit.py

Diffs every overlay word and every archive file of a built disc against the
pristine image and prints what really differs.

Run it on any disc you are about to draw a conclusion from. A single-variable
test is only single-variable if the disc says so — the build script's
intentions are not evidence, and that is not a hypothetical: a "one option"
disc built from a saved profile carries every setting that profile stored.

## pine.py

Talks to a running PCSX2 over its PINE socket — read memory, take a
savestate, ask what is running. Needs `EnablePINE = true` in that build's
`PCSX2.ini`.

Useful addresses for Rainbow Six 3 (SLUS-20883):

| address      | what |
|--------------|------|
| `0x006B95E0` | level name buffer, as text (`'menu'`, `'Parade_aoff'`, `'Island_a_ss'`) |
| `0x0065500C` | pointer to the game-mode block; the mode byte is at `+0x31` |

The level buffer is the cheapest progress signal there is. `'menu'` means the
mission load has not named its level yet; a name means it got that far.

## p2s.py

Reads a `.p2s` savestate: the EE CPU state, and the raw memory images.

The register layout is taken from the emulator's own `SaveStateBase::
FreezeInternals`, which writes a 32-byte `"cpuRegs"` tag followed by the
`cpuRegisters` struct — `GPR[32]` at 16 bytes each, then `HI`, `LO`, `CP0`,
`sa`, `IsDelaySlot`, and `pc` 680 bytes in. Check `r0` is zero; if it is not,
the layout has moved and nothing below it is trustworthy.

### Telling a wedge from a slow load

Measured on this game, over a one-second window:

| state | EE RAM changing | EE pc | ra / sp |
|-------|-----------------|-------|---------|
| loading normally | 3–5 **MB**/s | in game code | real |
| wedged | ~165 **bytes**/s | `0x00081fc0`, `eret` | both zero |

Three orders of magnitude apart, so this is not a judgement call. `ra` and
`sp` both zero means there is no runnable thread at all — the kernel is
ticking timers over threads that are all blocked. On a wedge, check where the
changing bytes are: below `0x00022000` is kernel housekeeping and means the
game is doing nothing whatsoever.

### Catching a phase that goes past too quickly

The interesting moment in a load that works can be over in a second. Poll the
level buffer hard and fire savestates the moment it changes, rather than
trying to press a key at the right time. Slots 30+ avoid the ones people
actually use.

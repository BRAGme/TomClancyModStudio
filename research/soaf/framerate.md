# Sum of All Fears (PS2, SLES-51180) — why it feels slow in PCSX2

**Short answer: it is almost certainly not the emulator. The game presents one
new image every two vsyncs — 25 fps on PAL — while PCSX2 runs it at full
speed.** That is the same shape as Ghost Recon's and Jungle Storm's 30 fps cap
(60 Hz NTSC, one extra vblank wait); this disc is PAL, so the same cap lands at
25.

A second, genuinely expensive thing is also happening during video playback and
is documented below, but it is not what makes the game *feel* laggy at full
speed.

Evidence: one GS dump,
`Pictures/PCXS2 Snaps/The Sum of All Fears/..._20260928115540.gs.zst`,
CRC `4691F6F7` (matches the profile), internal resolution 640x480, captured at
the Ubisoft logo. Parsed with the tooling in
`Documents/tcms-research/scratch-2026-09-28/decaltex/` (`gsparse.py`, `gsmem.py`).

---

## 1. The cadence: two vsyncs per rendered image

The dump holds four vsync-delimited frames and they strictly alternate:

| frame | GIF transfers | bytes | what it does |
|---|---|---|---|
| 0 | 1 | 368 | clears a buffer, `FRAME_1` FBP=`0x00` |
| 1 | 2,052 | 1,114,400 | uploads a 1 MiB image, draws 2 sprites |
| 2 | 1 | 368 | clears a buffer, `FRAME_1` FBP=`0x80` |
| 3 | 2,052 | 1,114,400 | uploads a 1 MiB image, draws 2 sprites |

The 368-byte frames are not idle — they are a full-buffer clear: `PRIM=6`
(sprite) with two `XYZ2` at `0x7000`/`0x9000`, which against `XYOFFSET`
`0x7000` is a 512x512 sprite covering the whole buffer, plus the usual
`TEST_1` / `ZBUF` juggling around it.

`FRAME_1` alternating `0x00` / `0x80` is double buffering. So the cycle is
**clear, then draw, then flip** across *two* vsyncs, and a new image reaches the
screen at half the display rate: **25 fps on a 50 Hz PAL output**.

## 2. Why this reads as "emulation is slow" when it is not

PCSX2's own counters during play, from the status bar:

| where | FPS | EE | VU | GS |
|---|---|---|---|---|
| main menu | 50.00 [P] | 10% | 0% | 7% |
| in a mission | 50.00 [P] | 32% | 19% | 24% |

`50.00 [P]` is full PAL speed, and none of the three chips is near saturation.
An emulator that is struggling shows a *falling* FPS number and a pegged EE or
GS. This one is keeping up comfortably and still looks stuttery, which is what
a 25 fps game on a 50 Hz output looks like.

**The menus being "just as laggy" is the decisive observation.** The menus
upload no video and draw almost nothing (7% GS), so nothing about §3 applies to
them. The one thing the menus, the logo and gameplay all share is the
presentation cadence. A cost that only appears during video cannot explain a
menu that feels identical.

## 3. The FMV upload path — real, expensive, but a separate problem

Each *rendered* frame of the logo does this:

| | |
|---|---|
| `BITBLTBUF` | written **once** — DBP=`0x0000`, DBW=8, DPSM=`PSMCT32` |
| `TRXREG` | written **once** — 16x16 |
| `TRXPOS` + `TRXDIR` | written **1,024 times each**, every one `dir=0` (host->local) |
| IMAGE payload | 1,048,576 B — exactly 1 MiB, as 1,024 chunks of 1 KiB |
| drawing | **2 primitives** |

1,024 tiles of 16x16 is 512x512, so the video player pushes each frame into
VRAM as a 512x512 `PSMCT32` texture **one 16x16 block at a time**, then blits it
with two sprites. At 25 rendered frames a second that is **~25,600 host->local
transfers per second**.

The rasterising is nothing — two primitives. The cost is entirely upload, and
in the hardware renderer every host->local transfer runs texture-cache
invalidation whose price rises with the upscale factor. At the 6x
(3072x3072) this machine was set to, that bookkeeping is paid 25,600 times a
second. If the logo ever does drop below full speed, this is why, and the
standard remedy is to let FMVs run on the software renderer, or to lower the
upscale.

This does **not** explain the menus (§2), and on the evidence here it was not
costing full speed either — the dump was taken at 50.00 fps.

## 4. What has NOT been established

* The dump covers **the intro FMV only**. The 2-vsync cadence is measured
  there and nowhere else. It is consistent with the menu and gameplay reports
  but not proven for them — a dump taken in a menu and one in a mission would
  settle it, and each is one keypress.
* No vblank-wait site has been located in this executable yet. §5 is a
  prediction from the cadence, not a disassembled fact.
* Nothing here measures the cost of the options added on 2026-09-28. A decal
  pool of 200 with permanent lifetime, "bullet holes on every surface", and
  doubled weather particles (8,000 raindrops / 5,000 flakes) are all real
  extra work and none has been benchmarked. If a gameplay dump shows a fill
  or upload problem, check those first by turning them off.

## 5. The fix worth pursuing, and why it is not free

Ghost Recon and Jungle Storm both cap gameplay by waiting an extra vblank per
frame, and both profiles lift it (`gr_fps`, `js_fps`) by patching one or three
words in `IkeUIMgr::CheckingLoadingLoop`. The measured cadence here says Sum of
All Fears does the same thing.

It does not port. `CheckingLoadingLoop__8IkeUIMgrFb` (94 words) was
signature-matched from Ghost Recon into this disc and produced **no candidate
down to a 0.45 match ratio** (`code.md` §4) — the main loop is not a
recognisable relative. So this needs its own search rather than an address
carried across.

**Concrete next probe.** Find where this game waits on the vsync counter:

1. In Ghost Recon, the wait reads a field of the graphics system
   (`g_graphic_sys`, the pointer at `0x00630B40`); Jungle Storm's equivalent
   reads its vsync count at `+0x342C`. This disc's graphics system is the
   pointer at **`0x005B2270`** — already known from the split-screen work
   (`code.md` §5a) — so scan for loads off that object and look for a field
   that is read in a tight loop and compared against a previously stored
   value.
2. Cross-check against the PS2 syscall side: `sceGsSyncV` / the vsync handler
   installed at boot, and any `WaitSema`/`SleepThread` pair inside the frame
   loop.
3. The frame loop itself can be anchored from the dump: whatever writes
   `FRAME_1` alternately as `0x00080000` and `0x00080080` is the flip, and the
   wait is adjacent to it.

Expected payoff: 50 fps instead of 25, on menus, FMV and gameplay alike. The
same caution as the other two games applies — game logic is timed by the
measured clock rather than by frames, so lifting the cap should not speed the
game up, but that was verified on Ghost Recon and Jungle Storm, not here.

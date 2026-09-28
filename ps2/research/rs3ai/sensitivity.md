# Look sensitivity in split screen — Rainbow Six 3 (PS2, SLUS-20883)

All addresses are virtual addresses inside the decompressed `SP.SOZ` overlay,
loaded at `0x00100000`. File offset = VA − `0x00100000`.

Source of truth for every word quoted here: the stock overlay decompressed this
session from
`E:\PS2 Games\.tcms-backup\Tom Clancy's Rainbow Six 3 (USA)\SP.SOZ.orig`,
5,585,280 bytes, SHA-1 `e9bb12138a1e69d551ac9f6b958114e5b2e830da` — matches the
documented stock hash. **Every "current word" in this document and in
`patch_candidates.md` was read back out of that image programmatically, not
transcribed.**

---

## Answer in one paragraph

Player 2 is slower because of **one instruction**. The native per-frame input
routine computes a frame delta `dt` once, then loops over the four pad slots.
Inside the loop, for **pad index 1 only**, it throws away the real `dt` and
substitutes a hardcoded `0.05` whenever the real `dt` is under `0.033` s. Both
look axes are then divided by that `dt` (`20.0 / dt`), so player 2's look rate is
scaled by `dt_real / 0.05` relative to player 1's. At a 60 Hz input tick
(`dt ≈ 0.0167`) that is exactly **one third** of player 1's speed, and no menu
setting can recover it because the step multiplier is applied before the
division. The instruction is

```
00142048   4483a800   mtc1  $v1, $f21        ; dt := 0.05f, player index 1 only
```

and the word that makes the two players equal is `00142048 → 00000000`.

---

## 1. The look pipeline, end to end

### 1.1 Where the settings live

Two global singletons, both reached through `$gp` (`$gp = 0x0065b6f0`, recovered
in earlier work and consistent with everything below):

| pointer | object | fields found |
|---|---|---|
| `*(gp-0x6704)` = `*(0x00654fec)` | game settings | `+0x2f` default X step, `+0x30` default Y step, `+0x31`/`+0x32` **player 1** X/Y step, `+0x33`/`+0x34` **player 2** X/Y step, `+0x4c` P1 button scheme, `+0x50` P2 button scheme, `+0xcc`/`+0xcd` option bitfield (invert look, vibration, …) |
| `*(gp-0x6700)` = `*(0x00654ff0)` | tuning config | `+0x208` global look multiplier, `+0x258` deadzone, `+0x260` FOV-scale term, `+0x27c` X look base, `+0x280` Y look base |

The tuning config is copied into each viewport by `0x0013fe38`:

```
0013ff70   swc1 $f0, 0x270($a0)    viewport.deadzone   = cfg+0x258
0013ff34   swc1 $f0, 0x228($a0)    viewport.fovScale   = cfg+0x260
0013ffac   swc1 $f0, 0xaa0($a0)    viewport.lookBaseX  = cfg+0x27c
0013ffbc   swc1 $f0, 0xaa4($a0)    viewport.lookBaseY  = cfg+0x280
```

`viewport+0xaa0` and `viewport+0xaa4` have **exactly one writer each** in the
whole overlay, and it is this one, from a **global** config object. So the two
players' look base scales cannot differ. That closes the first obvious
"player 2 gets a different multiplier" hypothesis.

`XAxisSensitivity` / `YAxisSensitivity` are the only sensitivity strings in the
overlay (12 occurrences across four blocks: `0x005edf00`, `0x005eeec0`,
`0x005fb7d0`, `0x005fc780`). The `m_f*Sensitivity*` names from
`R6GAMESETTINGS.INI` do **not** appear — they are UnrealScript config properties,
as expected.

### 1.2 Settings → PlayerController

`PlayerController` carries `+0x4a0` button scheme, `+0x4a1` X step, `+0x4a2` Y
step, `+0x4d0` player index, `+0x4d8` option bits.

**At level start**, inside the big travel/spawn routine that begins at
`0x0021c3e4`:

```
0021d918  sw   $a1, 0x4d0($v0)        PC->PlayerIndex
0021d920  lbu  $a1, 0x30(settings)    default Y
0021d928  sb   $a1, 0x4a2($v0)
0021d930  lbu  $a1, 0x2f(settings)    default X
0021d938  sb   $a1, 0x4a1($v0)
0021d948  sb   $a1, 0x4a0($v0)        scheme, from *(gp-0x66e4)+0x2f
          ... invert bits from settings+0xcc into PC+0x4d8 ...
0021d9e8  lw   $v0, 0x520($v0)        Level->Game
0021d9ec  lbu  $v0, 0x3a2($v0)        m_bIsSplitScreen (bit 5)
0021d9f8  beqz $v0, 0x21db4c          NOT split screen -> done
0021da04  lw   $v0, 0x4d0($v0)        player index
0021da08  bnez $v0, 0x21dab0
          index 0 -> PC->0x4a1 = settings+0x31 ; PC->0x4a2 = settings+0x32
                     PC->0x4a0 = settings+0x4c - 1
          index 1 -> PC->0x4a1 = settings+0x33 ; PC->0x4a2 = settings+0x34
                     PC->0x4a0 = settings+0x50 - 1
```

> Correction to earlier research: `SPLITSCREEN_HANDOFF.md` lists site
> `0x0021d9ec` in its 20-site table as "Xbox Live path (XGAMERTAG=/XUID=
> strings)". It is not. It is the per-player controller-settings copy. The
> XGAMERTAG strings are elsewhere in the same very large function. Treat the
> rest of that table as triage, not ground truth.

The two branches are **structurally identical** — same fields, same order, same
instruction shapes, only the source offsets differ. There is no asymmetry here.

**Every frame**, inside the input routine:

```
001428b8  lw   $v0, -0x6ffc($gp)      split-screen flag
001428bc  bnez $v0, 0x14295c          split screen -> skip
001428dc  lbu  $a0, 0x30(settings)    else re-apply the DEFAULT pair
001428e0  sb   $a0, 0x4a2($a1)
001428ec  lbu  $a1, 0x2f(settings)
001428f0  sb   $a1, 0x4a1($a0)
```

i.e. in single player the defaults are stamped onto the controller every frame;
in split screen they are not, so the per-player values written at level start (and
by the pause menu) survive. Again symmetric between the two players.

**Live, from the options menu**, `0x004bc394` (P1) and `0x004bc470` (P2) do the
same copy into the respective controller, selected by `*(gp-0x59d0)`. Symmetric.

### 1.3 The per-frame computation

The whole thing is one enormous native function, `0x00141cc4 .. 0x001453b0`. It
is reached only through a vtable — there is no `jal` to it anywhere — which is
why no earlier static pass found it.

Shape:

```
00141d10..00141d54   dt  = (now - last) in seconds                -> $f21
00141d60..00141d74   if (dt > 1.0)  dt = 0.04                      (hitch clamp)
00141d88            store 'now' back
00141d8c            $s2 = 0
                    ---- per-pad loop, $s2 = 0..3 ----------------
00141d9c            find the viewport whose +0x1fc == $s2          -> $s1
                    ($s1->0x34 is that viewport's PlayerController)
00142018..00142048  >>> THE PLAYER-2 CLAMP, see below <<<
00142960            left  stick: pad bytes +0x2a2 / +0x2a3         (movement)
00142e38            right stick: pad bytes +0x2a0 / +0x2a1         (look)
00142fa0..00143134  X look curve and scaling
00143190..00143388  Y look curve and scaling  (same shape)
00144f30..00144f54  $s2++ ; loop while $s2 < 4
```

Pad-slot base is `$s0 + 0x90*$s2` (kept in `0xd0($sp)`, advanced by `0x90` each
iteration at `0x00144f38`), so `$s2` really is the pad/player index, and the
viewport is matched by `viewport->+0x1fc == $s2`. `PC->+0x4d0` is written from
that same `+0x1fc` at `0x0021d918`, so **player index 1 is split screen's
player 2.**

Raw axis conversion (X shown; Y at `0x00142ed0` is identical):

```
00142e38  lbu $a0, 0x2a0($s3)           raw byte 0..255
          a0 <  0x60 : f23 = -( (96.0 - a0) / 96.0 )
          a0 >= 0x96 : f23 =  ( 106.0 - (255 - a0) ) / 106.0
          else       : f23 = 0                    (deadzone 0x60..0x95)
```

Then the curve and the scaling, `0x00142fa0 .. 0x00143134`:

```
f5 = x*x ; f3 = |x| ; f4 = |x*x|
sign = (x>0) ? 1 : (x<0) ? -1 : 0
f1  = viewport->0xaa0 * (float)sign                      ; look base X
f0  = 1.0 - f4
      mula.s  f5, f0        ACC  = x^2 * (1 - x^2)       (EE COP1 funct 0x1A)
      madd.s  f0, f3, f2    f0   = ACC + |x| * x^2       (EE COP1 funct 0x1C)
001430b0  mul.s $f20, $f1, $f0
          => f20 = lookBaseX * sign(x) * ( x^2 + |x|^3 - x^4 )

001430b4  lbu   $v0, 0x4a1($a0)         the sensitivity STEP  <-- only per-player term
          f1 = (float)step
001430e4  lw    $v0, -0x6700($gp)
001430e8  lwc1  $f0, 0x208($v0)         global look multiplier
001430ec  mul.s $f0, $f1, $f0           step * multiplier
001430f0  mul.s $f20, $f20, $f0

00143100  lbu   $v0, 0x4d8($a0)  ; bit 1 set ->
00143114    f1 = PC->0x530                       (FOV / zoom term)
0014311c    f2 = viewport->0x228
0014312c    f0 = (f2 * f1) / 90.0
00143130    f20 *= f0

00143138..00143180
0014316c  div.s $f0, $f0, $f21           f0 = 20.0 / dt
00143178  mul.s $f0, $f20, $f0
00143180  swc1  $f0, 0x518($v0)          PC->LookRateX
```

Y is the same code with `viewport->0xaa4`, `PC->0x4a2`, and
`00143364 div.s $f0,$f0,$f21` storing to `PC->0x51c` at `0x00143378`.

The menu stores the step as **index + 1** (`0x004b95f4 addiu $a0,$s1,1`), so a
slider at 0 stores 1 and a slider at 10 stores 11. That is why the step can be
used as a bare multiplier without producing zero at the lowest setting.

`PC+0x518`/`+0x51c` are written **only** by this function (the other apparent
writers, `0x003e49f4` / `0x003e4ac4` / `0x003e4b00` and the `+0x51c` group at
`0x003dee8c`, are a different class at a colliding offset). They have no genuine
native readers — `0x003a3740` looked like one but reads `+0x510/+0x514/+0x518` as
a three-float vector and normalises it, which a PlayerController look rate is not.
They sit in a four-float group with `+0x520`/`+0x524`, which this same function
fills with the movement axes at `0x00142d2c`/`0x00142d38`.
**Inference (not directly proven):** `+0x518`/`+0x51c` are UnrealScript
properties on `PlayerController` and the script's rotation update integrates
them. That is the only consumer consistent with one native writer, no native
readers, and a "rate" scaling of `20/dt`.

---

## 2. The asymmetry

Everything above is byte-for-byte symmetric between player 1 and player 2 —
same settings struct, same copy code, same curve, same base constants. I checked
all of it: the eight writers and eight readers of `settings+0x31..+0x34`, the
level-start copy, the per-frame copy, the pause-menu copy, and the memory-card
record. Exactly **one** site in the entire overlay behaves differently for
player index 1:

```
00142018  3c033d07   lui     $v1, 0x3d07
0014201c  34632b02   ori     $v1, $v1, 0x2b02     ; 0x3d072b02 = 0.032999999f
00142020  44830000   mtc1    $v1, $f0
00142028  4600a834   c.olt.s $f21, $f0            ; dt < 0.033 ?
00142030  45000006   bc1f    0x0014204c           ; no  -> skip
00142034  24030001   addiu   $v1, $zero, 1
00142038  16430004   bne     $s2, $v1, 0x0014204c ; player index != 1 -> skip
0014203c  00000000   nop
00142040  3c033d4c   lui     $v1, 0x3d4c
00142044  3463cccd   ori     $v1, $v1, 0xcccd     ; 0x3d4ccccd = 0.05f
00142048  4483a800   mtc1    $v1, $f21            ; dt := 0.05
0014204c  00000000   nop
```

In C:

```c
if (dt < 0.033f && padIndex == 1)
    dt = 0.05f;
```

`$f21` is the shared frame delta, computed once before the loop. After this
substitution, player index 1 carries a *different* `dt` through the rest of its
iteration, and `dt` divides into both look axes (`0x0014316c`, `0x00143364`) and
into the movement rate (`0x00142ba8`, `60.0 / dt`).

Effect on the look rate, with `R = dt_real`:

| real frame time | player 1 gets `20/R` | player 2 gets `20/0.05` | P2 / P1 |
|---|---|---|---|
| 1/60 = 0.0167 | 1200 | 400 | **0.333** |
| 1/50 = 0.020  | 1000 | 400 | 0.400 |
| 1/40 = 0.025  |  800 | 400 | 0.500 |
| 1/30.3 = 0.0330 | 606 | 400 | 0.660 |
| 1/30 = 0.0333 |  600 | 600 | 1.000 (clamp does not fire) |

So player 2 is between one third and two thirds of player 1 whenever the input
tick runs faster than ~30.3 Hz, and identical to player 1 at or below that rate.

**Why this explains "max 10 still doesn't match player 1 at 10".** The step
multiplier is applied at `0x001430ec`, *before* the `20/dt` division at
`0x0014316c`. The two scalings multiply, so the clamp's factor is constant across
the whole slider range: whatever player 2 selects, it lands at the same fraction
of player 1's equivalent setting. At a 60 Hz tick, player 2 at 10 feels like
player 1 at about 3.

**The one thing I could not verify statically** is the real value of `dt`. It is
computed from a hardware timer (`0x00190ca0` → `0x00411b90` → `0x00101e40`) and
there is no static way to read it. If the game's input tick is locked to 30 Hz,
`dt = 0.03333 > 0.032999` and this clamp never fires — in which case this is not
the cause and the finding is only "the sole per-player asymmetry in the look
path, dormant". Two things argue it does fire: the developers would not have
written a rule keyed on "faster than 30 fps" for a case that cannot occur, and PS2
engines of this generation typically tick input every vblank (~59.94 Hz) even when
rendering at 30. **If the patch is applied and nothing changes, the next probe is
to bake a stub that records `$f21` at `0x0014204c` into scratch and read it from a
savestate** — the exact technique already proven by `tools/bakevm.py` /
`tools/readvm.py`, using the 60-byte code padding at `0x0011d8c4`.

### Side effect, stated plainly

Removing the clamp also restores player 2's **movement** rate term at
`0x00142ba8` (`60.0/dt`), which today is cut by the same factor. Whether player 2's
walk speed is actually built from that term or from a separate script path was not
established. If player 2 currently moves at normal speed, then either that term
does not drive locomotion, or the clamp is not firing at all (see above). Watch
for player 2 moving faster after the patch; if that happens the fix should be
narrowed by saving and restoring `$f21` around the look block instead, which needs
a code cave rather than a word.

---

## 3. Hypotheses tested and refuted

| hypothesis | how it was tested | result |
|---|---|---|
| Player 2 gets a different sensitivity multiplier | `viewport+0xaa0`/`+0xaa4` have exactly one writer each (`0x0013ffac`, `0x0013ffbc`), sourced from a single global config object | refuted — cannot differ per player |
| Player 2's step value is stored or read from the wrong slot | traced all 8 writers and 8 readers of `settings+0x31..+0x34`; level start, per-frame, pause menu and memory-card paths all pair P1→`+0x31/+0x32`, P2→`+0x33/+0x34` | refuted — symmetric |
| The menu clamps player 2 to a lower maximum | both write `listIndex + 1` through the same code shape (`0x004b95f4` / `0x004b9604`) | refuted — same range |
| A viewport size / aspect term scales player 2 down | the only geometric term is `viewport+0x228 * PC->0x530 / 90.0` at `0x00143114..0x00143130`; `viewport+0x228` is copied from the same global for every viewport at `0x0013ff34` | refuted as a *per-player* cause; it is a shared FOV term. (It could still make **both** split-screen players slower than single player if `PC->0x530` differs by mode — not investigated, and not what was asked.) |
| The split-screen bool gates the look path | no read of `+0x3a2` and no read of `GameEngine+0x4e4` occurs anywhere inside `0x00141cc4..0x001453b0` | refuted — the look code is mode-blind |
| Player 2's raw stick is read through a different conversion | both players run the same `lbu +0x2a0/+0x2a1` conversion from their own pad block at `$s0 + 0x90*index` | refuted |

Two other per-player branches exist in the function and are **not** defects:
`0x0014338c` (`bne $s2,1`) selects a second set of input key ids for player 2's
buttons, and `0x00142d54` / `0x00142a94` select a second set of movement key ids.
Those are how two players get separate bindings.

---

## 4. Patches

Primary — makes player 2 identical to player 1:

| VA | current | proposed | effect |
|---|---|---|---|
| `00142048` | `4483a800` | `00000000` | drop the `dt := 0.05` store; player index 1 keeps the real frame delta |

Equivalent alternative (pick one, not both):

| VA | current | proposed | effect |
|---|---|---|---|
| `00142038` | `16430004` | `10000004` | `bne` → `b`, so the substitution is never reached |

Optional dial, if the tool wants a "player 2 look speed" slider rather than
parity. The clamp value is a plain float built by a `lui`/`ori` pair; smaller
makes player 2 **faster**:

| VA | current | meaning |
|---|---|---|
| `00142040` | `3c033d4c` | `lui $v1, <hi16 of float>` |
| `00142044` | `3463cccd` | `ori $v1,$v1,<lo16 of float>` |

`0.05 = 3d4ccccd` (stock), `1/30 = 3d088889`, `0.025 = 3ccccccd`,
`1/60 = 3c888889`. Both words must be written together. This is strictly worse
than the primary patch for achieving parity, because the result still does not
track the real framerate — offer it only as a tuning knob.

---

## 5. Related facts worth keeping

- `*(gp-0x6ffc)` = `0x006546f4` is the **split-screen flag** used by the input
  and menu layers. `0x00302d90` ORs it into `GameEngine->m_SplitScreenMode`
  (`+0x4e4`), which is how the two representations stay consistent.
- `*(gp-0x59d0)` = `0x00655d20` selects which player the options menu is editing
  (0 = player 1, non-zero = player 2).
- `PC+0x4d8` bit 2 = invert look (negates the Y axis at `0x00142f9c`), bit 1
  enables the FOV term at `0x0014310c`.
- The raw look axes are also written to the globals `gp-0x72dc` / `gp-0x72d8`
  (`0x00142f68`/`0x00142f6c`) and read only by the first-person weapon update at
  `0x003f4bf8` and `0x003f5528`. Those are **globals, not per-viewport**, so in
  split screen whichever pad the loop processed last drives both players' weapon
  sway. That is a separate, genuine split-screen defect and is not fixed here.

---

# Question 2 — why player 2's sensitivity resets at the start of every mission

## What the persistence layer actually looks like

There are three independent stores. All were traced to their instructions.

### (a) `PSX2USER.INI` — one pair only, and it is the *default* pair

The config parser at `0x0057b850` matches the literal keys and writes:

```
0057be4c  "XAxisSensitivity"   -> 0057be80  a043002f  sb $v1, 0x2f($v0)
0057be98  "YAxisSensitivity"   -> 0057becc  a0430030  sb $v1, 0x30($v0)
```

**Nothing in the overlay ever reads or writes `settings+0x31..+0x34` from a text
config.** The INI carries exactly one X/Y pair, and it lands in the *default*
slots `+0x2f`/`+0x30` — the pair single player uses. The four split-screen
per-player slots are invisible to the INI.

### (b) The memory-card profile record — carries all four, symmetrically

Record builder `0x0057100c`:

```
record+0x24 <- settings+0x31   P1 X       record+0x2c <- settings+0x33   P2 X
record+0x28 <- settings+0x32   P1 Y       record+0x30 <- settings+0x34   P2 Y
```

Record applier `0x00571214`, two branches selected by a player argument:

```
005712e8  sb $v1, 0x31($v0)   P1 X <- record+0x24   |  005713f8  sb $v1, 0x33($v0)   P2 X <- record+0x2c
005712f4  sb $v1, 0x32($v0)   P1 Y <- record+0x28   |  00571404  sb $v1, 0x34($v0)   P2 Y <- record+0x30
```

and each branch then notifies through `jal 0x00587c50` with `$a1` = 1 or 2 and
`$a2` = the field id, so both players are persisted under their own player tag.
This layer is symmetric — no defect here.

### (c) The RAM singleton is created once, at boot

`*(gp-0x6704)` is assigned only at `0x00207918` / `0x00207940` (an init
function) and nulled at `0x00204f24` (teardown). **It is not re-created per
level**, so `settings+0x31..+0x34` survive a mission load on their own.

### The "reset to defaults" routine, and why it is not the cause

`0x00588d70` resets one player's control settings:

```
$a1 == 1 -> settings+0x31 = 5, +0x32 = 5, +0x4c = 1, invert/vibration bits cleared
$a1 == 2 -> settings+0x33 = 5, +0x34 = 5, +0x50 = 1, invert/vibration bits cleared
            (both branches guarded by  *(gp-0x6fe0) == 0)
```

It is called from `0x0058c28c` with `$a1 = 1` and `0x0058c298` with `$a1 = 2` —
**both players, back to back** — and the caller then sets the guard to 1 at
`0x0058c2a8` so the routine is inert afterwards. `0x0049c12c` clears the guard
again. So this is a one-shot "apply factory defaults when no profile is present",
it treats the two players identically, and it cannot produce a player-2-only
reset. Worth recording anyway: **the factory default step is 5**, written as
`addiu $a0,$zero,5` at `0x00588db0` / `0x00588eb8`.

## The negative result, stated precisely

**I could not find any native asymmetry in the save/restore of the per-player
control settings.** I traced every instruction that touches
`settings+0x31/+0x32` and `settings+0x33/+0x34`:

| layer | player 1 | player 2 | symmetric? |
|---|---|---|---|
| menu list selection, X | `004b95fc` `sb $a0,0x31` | `004b960c` `sb $a0,0x33` | yes |
| menu list selection, Y | `004b9658` `sb $a0,0x32` | `004b9668` `sb $a0,0x34` | yes |
| menu commit | `004bc870` / `004bc880` | `004bc8d4` / `004bc8e4` | yes |
| memory card, save | `0057109x` | `005710b0` / `005710bc` | yes |
| memory card, restore | `005712e8` / `005712f4` | `005713f8` / `00571404` | yes |
| factory defaults | `00588ddc` / `00588de4` | `00588ee4` / `00588eec` | yes |
| apply to controller, level start | `0021da34` / `0021da24` | `0021dad4` / `0021dac4` | yes |
| apply to controller, live | `004bc45c` / `004bc46c` | `004bc52c` / `004bc53c` | yes |

Eight layers, sixteen sites, identical shapes. Whatever causes the reset is not a
lopsided store, and **there is no word patch for it in the persistence layer.**

## The one remaining native candidate, and the probe that settles it

`PlayerController+0x4a1` (X step) has exactly **six** writers in the whole
overlay, and `+0x4a2` the same six:

```
001428f0 / 001428e0   per-frame re-apply  — gated OFF in split screen at 001428bc
0021d938 / 0021d928   level start, default pair
0021da34 / 0021da24   level start, split screen, player index 0
0021dad4 / 0021dac4   level start, split screen, player index 1
004bc45c / 004bc46c   options menu, player 1
004bc52c / 004bc53c   options menu, player 2
```

The level-start block lives in the function starting at `0x0021c3e4`, and the
controller it configures is a **single** local, `0xc0($sp)`, assigned once at
`0x0021c88c`. I checked every backward branch in `0x0021c3e4..0x0021dc88`: the
last loop closes at `0x0021d8e4`, well before the settings block at
`0x0021d900`. **So one call to this function configures exactly one
PlayerController.**

That leaves a fork I cannot resolve statically:

* **If the function is called once per local player** — its `$a1` argument and the
  `jal 0x001f56e0` that yields the player index from `+0x1fc` both point that way —
  then player 2 *is* configured at level start, the native path is innocent, and
  the reset lives in UnrealScript, most plausibly a `PlayerController`
  `PostBeginPlay` / `InitInputSystem` that re-stamps a script config default over
  the native value for the second player.
* **If it is called once per level** (it is a 6.4 KB function that also does
  package loading, i.e. `LoadMap`-shaped), then **player 2's controller is never
  given its sensitivity at level start.** It would hold the class default until
  player 2 opens the pause menu and moves the slider — which is exactly the
  reported symptom, and would independently make player 2 feel slow.

The function has **no `jal` callers** (vtable dispatch), so static cross-reference
cannot decide it. 

**The probe that decides it**, using the technique already proven in this project
by `tools/bakevm.py` / `tools/readvm.py`: bake a stub into the 60-byte code
padding at `0x0011d8c4`, hooked at `0x0021d918` (`sw $a1, 0x4d0($v0)` — a plain
store, not a branch and not in a delay slot, so it is legal to displace under the
rule this project established after the `jal`-displacement incident). Record a
call counter and the successive values of `$a1`. Boot split screen, save a state
once the level has loaded, read the words back.

* counter = 2, `$a1` seen as 0 then 1 → per-player entry; the reset is in script.
* counter = 1 → **player 2 is never configured at level start. That is the bug.**

## If the counter comes back 1 — what the fix would take

There is **no single-word fix**, and it is worth being plain about that rather
than offering a plausible-looking one.

The per-frame re-apply at `0x001428b0` is the only other place that stamps these
fields, and it applies the *default* pair `settings+0x2f`/`+0x30` to whatever
controller it is looking at. Making it unconditional
(`001428bc  14400027 -> 00000000`) would indeed give player 2 a sensitivity every
frame — but it would also overwrite **player 1's** per-player value with the
default pair every frame, and would make the split-screen options sliders appear
to do nothing for either player. That is a regression, not a fix.

The correct repair is a code cave of roughly a dozen instructions hooked at
`0x001428bc` that reads `PC->0x4d0` and selects `settings+0x31/+0x32` or
`+0x33/+0x34` instead of `+0x2f/+0x30` — the same three-way choice the level-start
block already makes at `0x0021da00`, executed per frame. The 60-byte padding at
`0x0011d8c4` is fifteen words and would just fit, but it is the only such run in
the code region and it is currently this project's probe scratch, so the two uses
are mutually exclusive. Standing warning from this project's history applies with
full force: **such a cave must be baked into the overlay image, never applied by a
cheat file** — `0x001428bc` sits inside the hottest per-frame function in the game,
and rewriting a hot loop's code every frame took PCSX2 down once already.

## Bearing on question 1

The two questions are independent. The timestep clamp at `0x00142048` explains
"player 2 is far too slow even at maximum" on its own, and it is a real, verified,
player-index-1-only instruction. If the `0x0021d918` probe also returns
counter = 1, the two defects compound: player 2 would be running a class-default
step *and* a one-third timestep, which is consistent with how large the reported
difference is.

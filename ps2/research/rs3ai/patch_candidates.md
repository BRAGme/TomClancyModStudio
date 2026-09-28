# Patch candidates — Rainbow Six 3 (PS2, SLUS-20883), `SP.SOZ` overlay

Virtual addresses. File offset = VA − `0x00100000`.

## Verification statement

Every value in the **current word** column was read programmatically out of the
decompressed stock overlay during this session, not transcribed from a
disassembly listing. The image used was
`E:\PS2 Games\.tcms-backup\Tom Clancy's Rainbow Six 3 (USA)\SP.SOZ.orig`
unpacked with the repo's own `tcps2.soz.SozImage`:

```
length 5,585,280 bytes
SHA-1  e9bb12138a1e69d551ac9f6b958114e5b2e830da      (matches docs/PATCHES.md stock)
```

The verification script is
`research/rs3ai/verify.py` (with `research/rs3ai/r6.py` beside it; point `r6.py` at an
unpacked stock `sp.bin`); it prints `VA | word | disassembly` for every site
listed below and was run against that image. **Any tool applying these patches
should re-check the current word before writing, exactly as the existing tool
already does for the wave and split-screen patches.**

Risk letters: **A** = provably inert outside the targeted case;
**B** = single behaviour change, side effects understood and stated;
**C** = behaviour change with an unverified assumption behind it.

---

## Group 1 — Player 2 look sensitivity (split screen)

Apply **one** of the first two rows, never both. They are two ways of disabling
the same three-instruction sequence.

| VA | current word | proposed word | effect | risk |
|---|---|---|---|---|
| `00142048` | `4483a800` | `00000000` | **Primary.** Removes `dt := 0.05f` for pad index 1. Player 2's look (and movement) timestep becomes the same real frame delta player 1 uses, so the two players' sensitivity curves become identical at every slider setting. | A |
| `00142038` | `16430004` | `10000004` | *Alternative to the row above* — turns `bne $s2,$v1,0x14204c` into an unconditional branch so the substitution is never reached. Identical outcome; choose one. | A |

Why risk A: the substituted value is only ever used by the loop iteration for pad
index 1, and pad index 1 only has a viewport in split screen. In single player the
patched instruction's result is consumed by an iteration with no player attached.
Nothing outside `0x00141cc4..0x001453b0` reads `$f21`.

Stated side effect: the same `dt` also divides the movement-rate term at
`0x00142ba8` (`60.0/dt`) and advances the button auto-repeat timers at
`0x00142490` / `0x00142544` / `0x00142754` / `0x0014289c`, all for player 2 only.
Restoring the real `dt` makes those match player 1 too, which is the intended
behaviour — but if player 2's movement speed visibly changes after the patch,
that is why.

Optional tuning dial instead of parity — **both words must be written together**,
and this is mutually exclusive with the two rows above:

| VA | current word | proposed word | effect | risk |
|---|---|---|---|---|
| `00142040` | `3c033d4c` | `3c03<hi16>` | high half of the player-2 timestep constant | B |
| `00142044` | `3463cccd` | `3463<lo16>` | low half of the same constant | B |

`0.05 = 3d4ccccd` (stock, slowest), `1/30 = 3d088889`, `0.025 = 3ccccccd`,
`1/60 = 3c888889` (fastest of these). Smaller constant ⇒ player 2 looks faster.
This does **not** make player 2 framerate-independent the way the primary patch
does, so prefer the primary patch unless a deliberate offset is wanted.

**Caveat that applies to the whole group.** The substitution is guarded by
`if (dt < 0.033f)`. `dt` is read from a hardware timer and cannot be evaluated
statically. If the game's input tick is locked at or below 30 Hz the guard never
passes, the clamp is dormant, and these patches will change nothing. See
`sensitivity.md` §2 for the probe that settles it.

---

## Group 2 — Player 2 settings not surviving a mission load

**No patch is offered.** Eight persistence layers and sixteen store sites were
traced and all are symmetric between the two players (`sensitivity.md`,
question 2). The one remaining native candidate — that the level-start settings
copy at `0x0021d900` runs once per level rather than once per player, leaving
player 2's controller unconfigured — cannot be decided by static analysis, and if
it is true the fix is a ~12-instruction code cave, not a word. Writing
`001428bc → 00000000` *looks* like a fix and is not: it would stamp the
single-player default pair onto **both** controllers every frame and break
player 1 as well.

The probe to run first is described in `sensitivity.md` question 2: hook
`0x0021d918` into the padding at `0x0011d8c4` and record a call counter plus `$a1`.

---

## Group 3 — Enemy accuracy in split screen

See `accuracy.md`.

---

## Group 4 — Enemy grenades and molotovs

See `grenades.md`.

---

## Dependencies between groups

Group 1's two primary rows are mutually exclusive with each other and with the
tuning-dial pair. Nothing in group 1 depends on, or is depended on by, any other
group.

None of the patches in this document touch any address already used by the
shipped patch set in `docs/PATCHES.md` (wave system `0x0040A7xx`/`0x0040AFxx`,
split-screen effects `0x003F1xxx`/`0x003531D0`/`0x003A14B8`/`0x002375E0`,
view model `0x00302DA8`, world `0x00379B30`/`0x00317xxx`), nor the probe padding
at `0x0011D8C4`–`0x0011D8FC`.

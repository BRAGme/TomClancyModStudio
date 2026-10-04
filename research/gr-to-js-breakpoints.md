# Porting a Ghost Recon level into Jungle Storm: what actually hangs it

**SOLVED 2026-10-04.** Ghost Recon's `M01_CAVES` plays in Jungle Storm's
`CP01_HUNTING_LODGE` slot in split screen. The cause of every hang was
**storage form**: Ghost Recon stores some files plain that the Jungle Storm
slot stores packed, and the loader hangs with no error when handed an unpacked
file where it expects a packed one. It bit three times separately --
`_SKY.POZ`, the `.MIS`, and `.POL`.

**Derive the storage form from the SLOT's existing file, never from the source
game.** `research/soaf/port-to-gr.md` 19a states it: "all seven CP01 level
files are packed, the .POL included".

## Which screen you are stuck on tells you which half is wrong

* **"Please wait", the startup screen after the logos** -- the game parses
  EVERY mission at startup to build its lists, so a bad `.MIS` hangs here,
  before any menu.
* **the level's own loading screen** -- a bad terrain file hangs here.

## Which file, from a savestate, with no debugger

Probe each level file's bytes against EE RAM. The loader order is
`LoadFromMol (.mol)` -> `LoadPortals (.pol)` -> `LoadMissionMap (.MAZ/.SHT/
.BMZ)` -> `LoadObjects (.aol)`. The last file fully resident with nothing after
it names the step: `.POL` resident and no `.MAZ/.SHT/.BMZ` meant `LoadPortals`,
and `.POL` was the file stored in the wrong form.

A `.MOL` that is NOT resident is normal -- it is consumed into model structures
rather than kept.

## The recipe

1. grow `GR.IMG` (`tcps2/discgrow.py`);
2. the six terrain files into the slot, **each in the slot's own storage form**;
3. rescale every `.MOL` plane normal 4096 -> 32000, re-pack (see
   port-to-gr.md 19c -- read at Jungle Storm's scale an unscaled floor sits
   7.8125x too high);
4. `.MIS` = the slot's Shell verbatim + the donor's `RoomList` and `ZoneList`,
   minus `EnvTag`/`Extraction`/`Sound`/`Type` on zones, plus one `CoopBase`
   zone at the donor's insertion point -- **packed**;
5. `.ENV` = the slot's names with the donor's lighting -- plain;
6. keep the slot's `.PAK`, `.RSB`, `.POB`, skybox and grass.

**CP02 and CP04 are hidden from the offline map list on a stock disc** -- a
Jungle Storm quirk, not something a port breaks.

---

# Appendix: the texture-manager breakpoint (a dead end here)


**One breakpoint answers it: `0x00501F4C`, then read `$s1` as a string.**

That address is reached *only* when a texture failed to open. `$s1` holds the
name. Everything below is why, and what to do with the answer.

Written 2026-10-04, after `GR M01_CAVES -> JS CP01_HUNTING_LODGE` hung at
"Please wait" through seventeen play tests. The mechanism is the one
`research/soaf/port-to-gr.md` §19b found for the SOAF port; the disassembly
here is new and pins the exact instruction.


## 1. Why the game hangs rather than failing

Jungle Storm loads a level **on the main thread**, one step per frame, as a
chain of messages: `HandleLoadMission` -> `HandleLoadEnvironment` ->
`HandleLoadMap` -> `HandleLoadSkybox`. A step that fails posts nothing, so the
loading screen spins for ever. The EE sits at 99% — it is the frame loop, not a
deadlock, so "EE 99%" is not evidence of a busy wait in the loader itself.

The usual cause is the UI texture manager (vtable `0x005B7788`). Its
get-or-load takes a lock and **returns without releasing it when the file
cannot be opened**, so the next texture request waits for ever. That is a bug
in Jungle Storm, not in the port; any missing texture name triggers it.


## 2. The function, annotated

`0x00501EC0`, the manager's get-or-load. Read off the retail `SLUS_208.20`:

    0x00501EC0  addiu $sp, $sp, -96
    0x00501ED0  daddu $s2, $a0, $zero      $s2 = the manager (this)
    0x00501ED4  daddu $s1, $a1, $zero      $s1 = THE NAME            <<<<<<
    0x00501EDC  jal   0x0014e6b0           validate the name
    0x00501EE4  bne   $v0, $zero, 0x501EF4
    0x00501EEC  beq   $zero,$zero,0x501FAC early-out, lock NOT taken (safe)
    0x00501EF4  jal   0x00101b90           TAKE the lock
    0x00501EF8  addiu $a0, $a0, -23904     $a0 = 0x0068A2A0 (semaphore 6)
    0x00501F20  jal   0x00501dc0           look the name up
    0x00501F2C  bne   $s0, $zero, 0x501F84 already loaded -> release path
    0x00501F38  jal   0x00501cb0           CREATE: opens the file (diOpen 0x4911F0)
    0x00501F3C  daddu $a0, $s2, $zero        with $a1 = $s1 = the name
    0x00501F44  bne   $s0, $zero, 0x501F68 created OK -> release path
    0x00501F4C  jal   0x003ff440           FAILURE PATH STARTS HERE  <<<<<<
    0x00501F64  daddu $v0, $zero, $zero    return 0 ...
    0x00501FBC  jr    $ra                  ... and the lock is never released

    0x00501F84  lui   $a0, 0x69            the success path
    0x00501F88  jal   0x00101bb0           RELEASE the lock
    0x00501F8C  addiu $a0, $a0, -23904     0x0068A2A0

`0x00501F4C` is reached from exactly one place — the `bne` at `0x00501F44`
falling through because the create returned 0. Nothing else branches there.
`$s1` is set at `0x00501ED4` and not touched in between, so at `0x00501F4C` it
still points at the name whose open failed.


## 3. The session

1. Boot the disc in PCSX2, but **do not load the level yet**.
2. `Debug` -> `Breakpoints` -> add an **execute** breakpoint at `0x00501F4C`.
3. Load the level (CP01 Hunting Lodge, split screen).
4. When it breaks, open `Memory` and go to the value in **`$s1`**. The ASCII
   string there is the texture that could not be opened. Write it down.
5. Resume. If it breaks again, note each name — the loader asks for several and
   only the first failure matters, because after it the lock is gone.

If it never breaks, the hang is **not** this bug, and the next question is which
load step died — see §4.


## 3a. Result, 2026-10-04: it never fires

Run on `JS_GR_M01_planes_packed.iso` into CP01, execute breakpoint at
`0x00501F4C` on the R5900 tab. **The breakpoint was never hit.** The VIF
assertion (`FQC = 0 on VIF FIFO READ`) came up first and the load never
reached a failed texture open.

**So the texture-manager lock leak is NOT the cause of this hang**, even
though the savestate fingerprint matched it -- `icons_interface` resident, the
manager's vtable on the main thread's stack, the list ending at
`pda_counterparts`. That fingerprint is necessary but not sufficient: a load
that stops early leaves the manager mid-sequence whatever the reason, so it
looks like the leak without being it. Treat §19b's signature as suggestive, not
diagnostic, and confirm with this breakpoint before acting on it.

The dialog's `Retry` ("break to debugger") did not give a usable break either --
the emulator closed instead. `Abort` loses the state. That leaves `Ignore`, and
the open question of whether the assertion is survivable.

## 4. If `0x00501F4C` never fires

Add an execute breakpoint at `0x00501EC0` instead and read `$a1` at each hit to
log every texture requested. A stock load ends with `pda_counterparts` and then
the map's own `CMBitmap`. Whatever is missing from that sequence relative to a
stock load tells you where it stopped.

Independently, a savestate at the hang says which load step was reached, with no
debugger at all: probe each level file's bytes against EE RAM. If no byte of
`.MOL/.POL/.MAZ/.SHT/.BMZ/.AOL` is resident, the load never reached geometry and
the fault is in the mission or environment step.

    thread control blocks   0x4C apart from 0x1AC4C
    $gp                     0x0061A4F0 (marks the game's own threads)
    +0x0C park, +0x10 saved context, +0x1C wait type, +0x20 semaphore
    register n              ctx + 0x10*n

Wait type 0 = running. The texture-manager fingerprint is: the manager's list
(entries linked at `+0`, name at `+0x38`) ending at `pda_counterparts` with no
`CMBitmap` entry above it, and `icons_interface` resident in RAM.


## 5. What to do with the name

Three fixes, cheapest first:

* **The name exists on the disc under a different spelling.** Repoint whatever
  references it — usually the `.ENV`'s `CMBitmap` or a `.rsb` named in the
  `.MIS` — at the slot's own texture. Porter rule: never let a Jungle Storm
  `.ENV` name an image that is not on the disc, and never leave `CMBitmap`
  empty.
* **The name is a ported level's own texture.** Write it into the slot under a
  name the slot already has, and repoint the reference.
* **Nothing names it in the data.** Then it is derived in code from the room or
  zone records, and the fix is in those — this is the case the GR port is
  believed to be in, because bisecting showed GR's `RoomList` alone *or* its
  `ZoneList` alone is enough to trigger the hang, with the `.ENV`
  field-identical to a working port's.


## 6. State of the GR -> JS port when this was written

Established:

* GR terrain **does** load in Jungle Storm — a terrain-only swap reached the
  level and failed later, in rendering.
* The hang happens **before any geometry**: not one byte of the six level files
  is in EE RAM.
* Mission and environment **are** read — the ported mission's own zone names are
  resident.
* The archive takes no collateral damage; unpacked lengths are correct; plane
  normals are rescaled to 32000; the `.MOL` is packed.

Ruled out: `discgrow` (growing a verified disc and changing nothing else still
loads), the `.PAK`, slot size, chunk granularity, mission size, `MapSize`,
`HeroFile`, `CoopBase`, `Lvl`, and room `EnvTag` values.

Related: `research/soaf/port-to-gr.md` (the SOAF port, §19b for this bug and
§19c for the plane-normal scale), and the `reference_gr_to_js_level_port`
memory.

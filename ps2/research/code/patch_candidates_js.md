# Patch candidates — Ghost Recon: Jungle Storm (PS2, SLUS-20820)

**None of these were tested.** No emulator was launched. Every "current word" below was
read out of `SLUS_208.20` with a tool this session and machine-verified in a batch
(23/23 exact matches, 0 mismatches); every proposed word was hand-assembled. The
*effect* column is an inference from the disassembly.

Companion documents: `features_js.md` (string-driven map, produced independently),
`features_gr.md` (the symbol-rich sister title), `loadmap.md`, `mwo3.py`.

## How these addresses were obtained — Jungle Storm has no symbols

`SLUS_208.20` is stripped: `.symtab` and `.strtab` exist in the section table with
`sh_size = 0`. So every named function below was located by **masked code-signature
matching against Ghost Recon**, using `portsig.py`, then confirmed by
disassembly and by call-graph position. The signature masks `lui` immediates and
`jal` targets and slides the rest over the target image, anchoring on the rarest
interior word rather than the prologue.

That anchoring detail matters: **Jungle Storm was compiled with different Metrowerks
codegen settings.** Ghost Recon emits the MMI 128-bit `paddub rd,rs,$zero` as its
register-move idiom; Jungle Storm emits the 64-bit `daddu rd,rs,$zero`. Loop shapes
differ too (`addiu $v0,$zero,N` + `bne` in GR vs `slti $v0,$s0,N` in JS). Because of
this, whole-function signatures match only for the small, arithmetic-dominated
functions — 3 of 11 attempts succeeded — and the rest were reached by following the
call graph from those. `BulletHolePS2::Generate` matched at 95.7 %,
`ToggleCameraView` at 86.5 %, `IsFirstPersonCamera` at 100 %; from those three
anchors the whole decal and camera chain fell out.

Also: Jungle Storm uses `dsll32` / `dsra32` pairs for boolean extraction (seen at
`0x00431994`), exactly as the Rainbow Six 3 notes warn. Do not search for `andi`.

VA ↔ file for the boot ELF: `VA = file_offset + 0x00100000 - 0x100`.
pnach serial: `SLUS-20820`. CRC must come from PCSX2's log for the user's dump.

---

## Function map recovered (Jungle Storm ← Ghost Recon)

| function | Ghost Recon VA | **Jungle Storm VA** | how confirmed |
|---|---|---|---|
| `BulletHolePS2::Generate` | `0x0046DCE0` | **`0x00431C30`** | signature 22/23 words; identical struct offsets `+0x08` pos, `+0x14` normal, `+0x20` tex, `+0x24` life, `+0x28` spawn, `+0x2C` last-update |
| `BulletHoleManagerPS2::AddOneBulletHole` | `0x0046DAC0` | **`0x00431A20`** | sole caller of Generate |
| `BulletHoleManagerPS2::Render` | `0x0046DC20` | **`0x00431B70`** | same body shape, called from `EffMgrPS2::Render` |
| `BulletHoleManagerPS2` ctor | `0x0046D9B0` | **`0x00431910`** | calls the array-grow helper with 20, then a 20-iteration clear loop |
| `IkeEffectsMgr::DisplayBullethole` | `0x00249610` | **`0x00245E40`** | sole caller of `AddOneBulletHole`; identical surface-type switch |
| `EffMgrPS2::Render` | `0x0045E160` | **`0x00423C10`** | encloses the BulletHole render call at `0x00423C98` |
| `CGraphicSystem::EnableSplitScreen` | `0x0044EBB0` | **`0x004152B0`** | `jr $ra; sb $a1,0x2880($a0)` — byte-identical, **same field offset `+0x2880`** |
| `CGraphicSystem::IsEnableSplitScreen` | `0x003ADE90` | **`0x0015BE80`** | `jr $ra; lbu $v0,0x2880($a0)` |
| `SimCamera::IsFirstPersonCamera` | `0x0039BA00` | **`0x00379880`** | 4/4 words identical |
| `SimCamera::ToggleCameraView` | `0x003A8B30` | **`0x00388900`** | 45/52 words |
| `SimCamera::SetCurrentCameraView` | `0x003A8C00` | **`0x003889D0`** | tail call from ToggleCameraView; stores to `+0x70` |
| "camera detached" global (`view >= 3`) | `0x005EB0B8` | **`0x0062BCC0`** | written at `0x003889F0` |

Jungle Storm keeps the decal float constants in a data pool rather than as `lui`/`ori`
pairs, and the values are **identical to Ghost Recon**:

| VA (JS) | value | used for |
|---|---|---|
| `0x00589600` | `3ECCCCCD` = 0.4 | default decal size |
| `0x005895F8` | `3D8F5C29` = 0.07 | surface type 3 |
| `0x005895F0` | `3DA3D70A` = 0.08 | surface types 4, 0x0C, 0x0D |
| `0x005895E8` | `3CA3D70A` = 0.02 | position offset along the normal |

---

## A. Decals / bullet impact marks

Jungle Storm's `DisplayBullethole` at `0x00245E40` has the same shape as Ghost
Recon's: default lifetime 30 s, 2 s for surface types `0x12`/`0x13`/`0x16`, a
texture index 0–3 chosen by surface type, and **the same "unknown surface type →
return without a decal" early-out**.

| # | VA | current | proposed | risk | effect |
|---|---|---|---|---|---|
| A1 | `0x00431930` | `24050014` | `240500C8` | M | bullet-hole array 20 → **200**. Apply with A2. |
| A2 | `0x0043194C` | `2A020014` | `2A0200C8` | M | the matching clear-loop bound (`slti $v0,$s0,0x14` → `0xC8`). Note this is a **different instruction form** from Ghost Recon's, so do not copy the GR word. |
| A3 | `0x00245E4C` | `3C0341F0` | `3C03447A` | L | default decal lifetime `30.0f` → `1000.0f`. |
| A4 | `0x00245F28` | `3C024000` | `3C02447A` | L | lifetime for surface types `0x12`/`0x13`/`0x16` `2.0f` → `1000.0f`. |
| A5 | `0x00245EF8` | `1000000F` | `00000000` | M | removes the unknown-surface-type early-out, so every surface gets a decal. Falls through to `0x00245F00`, which sets texture index 0 and joins the normal path. |
| A6 | `0x00589600` | `3ECCCCCD` | `3F000000` | L | default decal size `0.4f` → `0.5f`. **This is a data word, not an instruction** — it is a float in the constant pool, so a single write is enough (no lui/ori pair). |

```
// A. Jungle Storm decals
patch=1,EE,00431930,word,240500C8
patch=1,EE,0043194C,word,2A0200C8
patch=1,EE,00245E4C,word,3C03447A
patch=1,EE,00245F28,word,3C02447A
patch=1,EE,00245EF8,word,00000000
```

---

## B. Split-screen effect suppression

The same mechanism as Ghost Recon, at the same struct offset. `CGraphicSystem+0x2880`
is the split-screen boolean; sixteen sites in the boot ELF branch on it, and
**zero** sites in either overlay (scanned both; `offline.bin` and `online.bin`
contain no reference to the field at all — consistent with the finding that they hold
no rendering code).

The `EffMgrPS2::Render` dispatch has the same two-block structure. Comparing the
call lists directly:

| position | single-screen block | split-screen block |
|---|---|---|
| 1 | `0x00423C88` → `0x004323B0` | `0x00423D70` → `0x004323B0` |
| 2 | `0x00423C90` → `0x0042F2E0` | `0x00423D78` → `0x0042F2E0` |
| 3 | `0x00423C98` → `0x00431B70` **BulletHoleManagerPS2::Render** | **absent** |
| 4 | `0x00423CA0` → `0x0042E7A0` | **absent** |
| 5 | `0x00423CA8` → `0x00425870` | `0x00423D80` → `0x00425870` |
| 6 | `0x00423CB0` → `0x0042FEF0` | `0x00423D88` → `0x0042FEF0` |
| 7 | `0x00423CB8` → `0x00425730` | `0x00423D90` → `0x00425730` |
| 8 | `0x00423CC0` → `0x00429CA0` | `0x00423D98` → `0x00429CA0` |
| 9 | `0x00423CC8` → `0x00422DF0` | `0x00423DA0` → `0x00422DF0` |
| 10 | `0x00423CD0` → `0x00424250` | `0x00423DA8` → `0x00424250` |
| 11 | `0x00423CD8` → `0x00427790` | `0x00423DB0` → `0x00427790` |
| 12 | `0x00423CE0` → `0x0042C1A0` | `0x00423DB8` → `0x0042C1A0` |

**So Jungle Storm, like Ghost Recon, never renders bullet holes in split screen.**
Ten of the twelve renderers are re-issued for the second viewport; bullet holes
(`0x00431B70`) and foliage (`0x0042E7A0`) are not. See the manager table below for
how those two were identified.

### The effect managers, identified by construction order and allocation size

`EffMgrPS2`'s constructor is at **`0x00422FC0`** in Jungle Storm (found as the sole
caller of the confirmed `BulletHoleManagerPS2` ctor) and at `0x0045D480` in Ghost
Recon. Both are a straight run of `operator new(size)` + constructor pairs, and the
sizes line up almost exactly, which pins the identities:

| # | Ghost Recon ctor | size | Jungle Storm ctor | size | identification |
|---|---|---|---|---|---|
| 1 | `0x0045D0F0` `BillboardEffectManagerPS2` | `0x1404` | `0x00422C70` | `0x1404` | size + position |
| 2 | `0x004618C0` `LensflareManagerPS2` | `0x8` | `0x00426D90` | `0x8` | position |
| 3 | `0x00462120` `BloodPoolPS2` | `0x644` | `0x00427630` | `0x644` | size + position |
| 4 | `0x00464660` `StaticLightManagerPS2` | `0x8` | `0x00429C10` | `0x8` | position |
| 5 | `0x00467640` `HotAirPS2` | `0x14` | `0x0042CB60` | `0x1c` | position (struct grew by 8 bytes) |
| 6 | `0x004688B0` `SkyPS2` | `0x28` | `0x0042DD00` | `0x28` | size + position |
| 7 | `0x00460270` `RSArray<LCDPS2>` | `0x8` | — | — | **absent in Jungle Storm** |
| 8 | `0x00469560` `FoliageManagerPS2` | `0x10` | **`0x0042E540`** | `0x10` | size + position |
| 9 | `0x0046A800` `BirdManagerPS2` | `0x10` | — | — | **absent in Jungle Storm** |
| 10 | `0x0046B320` `WaterRippleManagerPS2` | `0x8` | `0x0042F130` | `0x8` | position |
| 11 | `0x0046E130` `IndicatorManagerPS2` | `0x8` | `0x00432110` | `0x8` | position |
| 12 | `0x0046D9B0` `BulletHoleManagerPS2` | `0x8` | **`0x00431910`** | `0x8` | **directly verified** via the Generate/AddOne/Render chain |
| 13 | `0x0046BE80` `TracerManagerPS2` | `0x8` | `0x0042FD30` | `0x8` | position (last before ScreenBlur) |
| 14–16 | `0x0046C6E0` `ScreenBlurPS2` ×3 | `0x210` | `0x00430680` ×3 | `0x210` | size + count + position |

Only entry 12 is directly verified; the rest are a deduction from the size-and-order
alignment, which is unambiguous except for the 0x8-sized entries. The two absentees
fall out of it: Ghost Recon constructs thirteen managers, Jungle Storm eleven, and
the only sizes that do not appear in the Jungle Storm run are one `0x8` and one
`0x10` from the LCD/Foliage/Bird band — with Foliage's `0x10` present, the missing
pair must be `RSArray<LCDPS2>` and `BirdManagerPS2`.

`0x0042E7A0` lies inside the code block bounded by the `0x0042E540` constructor and
the next class's constructor at `0x0042F130`, so it is a `FoliageManagerPS2` method —
and by its position in the render dispatch, `FoliageManagerPS2::Render`. **This makes
the two games' split-screen behaviour identical: Ghost Recon drops bullet holes,
foliage and birds; Jungle Storm has no bird manager at all, so it drops bullet holes
and foliage.**

Full gate list in the boot ELF (branch taken == split screen unless marked inverted):

| VA | word | skips | Ghost Recon counterpart |
|---|---|---|---|
| `0x004152C4` | `10400002` | 2 | `GetCurrentCamera` (inverted) |
| `0x00415C50` | `10600012` | 18 | `CGraphicSystem::MainFrame` (inverted) |
| `0x00415E28` | `10400006` | 6 | `PreMainFrame` (inverted) |
| `0x00415E5C` | `10600009` | 9 | `PreMainFrame` (inverted) |
| `0x0041FED8` | `10600006` | 6 | `CProjectShadow::RestoreFrameBuffer` (inverted) |
| `0x00421658` | `10600006` | 6 | `CFullScreenAA::RestoreFrameBuffer` (inverted) |
| `0x00422A34` | `10400003` | 3 | `BillboardEffectPS2::Render` (inverted) |
| `0x00423A18` | `1460002A` | 42 | `EffMgrPS2::SetWeather+0x34` |
| `0x00423A8C` | `1060000D` | 13 | `EffMgrPS2::SetWeather+0xa8` (inverted) |
| `0x00423B08` | `1440000B` | 11 | `EffMgrPS2::PreRender+0x24` |
| `0x00423C64` | `14400003` | 3 | `EffMgrPS2::Render+0x54` (hot-air collection) |
| **`0x00423C80`** | `14400031` | **49** | **`EffMgrPS2::Render+0x70` — the full-effect block** |
| `0x00423E60` | `14400024` | 36 | `EffMgrPS2::Render+0x260` (hot air) |
| `0x00424D70` | `1440007C` | 124 | `EffMgrPS2::RenderNightVision+0x1c` |
| `0x00425B70` | `14400026` | 38 | `EffMgrPS2::RenderMask+0x1c` |
| `0x00427BA4` | `10400005` | 5 | `SnowEffectPS2` ctor (inverted) |

| # | VA | current | proposed | risk | effect |
|---|---|---|---|---|---|
| B1 | `0x004152B4` | `A0852880` | `A0802880` | **H** | `EnableSplitScreen()` always stores 0, so every gate above takes the single-screen path. Diagnostic only: `MainFrame`, `PreMainFrame` and `GetCurrentCamera` read the same byte, so viewport setup will be wrong. |
| B2 | `0x00423C80` | `14400031` | `00000000` | **H** | forces `EffMgrPS2::Render` down the full-effect block in split screen. Restores bullet holes and `0x0042E7A0`, but the single-screen block ends by branching past the second viewport's setup, so expect one viewport instead of two. |
| B3 | `0x00423B08` | `1440000B` | `00000000` | M | `PreRender` does its full-screen work in split screen too. Creation/update side, not viewport side — the safest of these to try first. |
| B4 | `0x00423E60` | `14400024` | `00000000` | M | hot-air / heat-haze rendered in split screen. |
| B5 | `0x00424D70` | `1440007C` | `00000000` | M | full night-vision path in split screen. |
| B6 | `0x00427BA4` | `10400005` | `10000005` | L | `SnowEffectPS2` constructor takes its **non**-split-screen path unconditionally (this one is inverted, so the fix is an unconditional branch, not a NOP). |

Same caveat as Ghost Recon: restoring split-screen bullet holes *properly* means
adding a `jal 0x00431B70` into the second block at `0x00423D70`–`0x00423DB8`, which
has no spare slot and needs a code cave.

```
// B. Jungle Storm split-screen effects - one at a time, B3 first
patch=1,EE,00423B08,word,00000000
patch=1,EE,00423E60,word,00000000
patch=1,EE,00424D70,word,00000000
// diagnostic only, expect broken viewports:
// patch=1,EE,004152B4,word,A0802880
// patch=1,EE,00423C80,word,00000000
```

### Turning an effect class off

NOP the `jal` — and remember **both** blocks for anything that appears twice:

| target | single-screen | split-screen |
|---|---|---|
| `0x004323B0` | `0x00423C88` | `0x00423D70` |
| `0x0042F2E0` | `0x00423C90` | `0x00423D78` |
| `0x00431B70` `BulletHoleManagerPS2::Render` | `0x00423C98` | — |
| `0x0042E7A0` `FoliageManagerPS2::Render` | `0x00423CA0` | — |
| `0x00425870` | `0x00423CA8` | `0x00423D80` |
| `0x0042FEF0` | `0x00423CB0` | `0x00423D88` |
| `0x00425730` | `0x00423CB8` | `0x00423D90` |
| `0x00429CA0` | `0x00423CC0` | `0x00423D98` |
| `0x00422DF0` | `0x00423CC8` | `0x00423DA0` |
| `0x00424250` | `0x00423CD0` | `0x00423DA8` |
| `0x00427790` | `0x00423CD8` | `0x00423DB0` |
| `0x0042C1A0` | `0x00423CE0` | `0x00423DB8` |

Cross-reference the manager table above to name a given target: each `Render` lives
in the code block that starts at its class's constructor and ends at the next class's
constructor.

---

## C. First-person camera

`SimCamera + 0x70` holds the camera view and **0 is first person**, exactly as in
Ghost Recon. Confirmed here two independent ways: the `IsFirstPersonCamera` body at
`0x00379880` (`lw $v0,0x70($a0); xor; sltiu $v0,$v0,1` — 4/4 words identical to GR),
and the enum-string dispatch reached from `SetCurrentCameraView` at `0x003889D0`
(`first person camera` at `0x00595D50`, `third person camera` at `0x00595D70`,
`cinema camera` at `0x00595D88`, …).

| # | VA | current | proposed | risk | effect |
|---|---|---|---|---|---|
| C1 | `0x003889E0` | `AC850070` | `AC800070` | **H** | `SetCurrentCameraView` stores 0 regardless of argument — camera pinned to first person. Also hits the scripted/cinema camera path. |
| C2 | `0x00388914` | `24420001` | `00001021` | M | `ToggleCameraView` computes `view = 0` instead of `view + 1` — the camera-cycle input can never leave first person, while scripted camera changes still work. Narrower than C1. |
| C3 | `0x00388958` | `28420003` | `28420006` | L | raises `ToggleCameraView`'s normal wrap from 3 to 6, unlocking the chase and ghost cameras on the ordinary cycle input. |

**The Ghost Recon "hide your own body in first person" patch has no counterpart
here yet.** `SimCamera::CameraBeginScene` did not match by signature and was not
located in Jungle Storm in this pass; see "Next probes" below.

```
// C. Jungle Storm first person
patch=1,EE,00388914,word,00001021
// unlock chase + ghost cameras:
// patch=1,EE,00388958,word,28420006
```

---

## D. Spawning / respawn

**No patch candidates. This is a negative result, and it is the useful kind.**

`IkeRulesMgr::CanRespawn` did not match by signature (160 words, heavy virtual
dispatch, and the JS build's different move idiom breaks the signature) and was not
located. More importantly, the independent string analysis in `features_js.md` found
that Jungle Storm builds its opposing force **at runtime by probing the filesystem**:
the routine at `0x00349F50` counts `opposing_force_jungle_%i.atr` and
`opposing_force_%i.kit` files and constructs `_Opposing Company` → `_Opposing Platoon`
→ `_Opposing Team%i` from whatever it finds. There is no hardcoded enemy count to
patch — **adding actor and kit files to the archive increases enemy variety with no
code change at all.** That is a data-side lever, and the archives belong to the other
agent.

Likewise there is no reinforcement-wave system to gate: "wave" in the string pool
matches only `shock_wave_type1/2/3`, and `RESPAWN_CTRL` / `EDRESPAWN` are
multiplayer-lobby widget ids, not gameplay flags.

---

## E. The overlays: nothing to patch

`offline.bin` and `online.bin` are **not gameplay overlays**. Both were unpacked with
`mwo3.py` and scanned:

* neither contains a single reference to the split-screen field `+0x2880`;
* neither contains any decal, particle, camera or spawning vocabulary (feature-string
  census 0/0/0/0 in both, versus 75/130/8/160 in the boot ELF);
* `offline.bin` is the Fonix ASRSPI speech-recognition engine;
* `online.bin` is the Ubi.com GameService lobby/crypto/ladder client plus PS2 eenet;
* their calls back into the boot ELF reach only 42 and 102 distinct functions, all C
  runtime / soft-float / `sprintf` helpers.

**A render or gameplay mod tool should target `SLUS_208.20` exclusively.** This
answers the question the brief raised — unlike Rainbow Six 3 on PS2, Jungle Storm's
game logic is *not* in the overlay.

---

## Next probes, if this needs to go further

1. **Locate `SimCamera::CameraBeginScene` in Jungle Storm** to get the C3 equivalent
   of Ghost Recon's D3 (stop hiding the player's body in first person). Route: find
   the Jungle Storm `RSSimController::Hide` by signature from GR `0x003A8170` (a
   6-word function — small enough that a signature should hold), then take its
   callers and look for the one guarded by a call to `0x00379880`.
2. **Confirm the deduced manager identities** in the table above by a behavioural
   test — NOP one `Render` call and see which effect disappears. The deduction is
   sound but only entry 12 is directly verified.
3. **`IkeRulesMgr::CanRespawn`.** Signature matching will not find it. Route: the
   lobby widget ids `RESPAWN_CTRL` / `EDRESPAWN` in the string pool → `xref` → the
   handler that reads the widget → the field offset it writes → search for loads of
   that offset.

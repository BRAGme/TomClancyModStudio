# Every address this tool touches -- Rainbow Six 3

Ghost Recon and Jungle Storm are a different engine and live in
[PATCHES-GHOSTRECON.md](PATCHES-GHOSTRECON.md).

All addresses are virtual addresses inside the decompressed `SP.SOZ` overlay of
**Rainbow Six 3 (PS2, SLUS-20883)**, which the EE loads at a fixed base of
`0x00100000`. File offset = VA − `0x00100000`.

Stock overlay: 5,585,280 bytes decompressed,
SHA-1 `e9bb12138a1e69d551ac9f6b958114e5b2e830da`, container extent 1,878,483
bytes at LBA 1821. The tool checks the hash before it writes anything.

---

## Enemy waves

The engine class is `AR6DZoneWave`, deriving from `AR6DeploymentZone`. Both are
native C++ in the overlay — a UFunction's serial size gives it away, since the
deployment-zone functions are 27–43 bytes with no bytecode while real script
functions in the same package run to hundreds.

### The zone's init, `0x0040AF28`, with `$s0` = the actor

```
m_iNbSpawned (0x478) = m_aTerrorist.Count (0x3f4)
m_iNbToSpawn (0x47c) = min(0x380) + rand % (max(0x384) - min + 1)
difficulty from obj+0x104 -> +0x520 -> +0x4c8:
    3 = Elite    adds m_NbToAddInElite   (0x474)
    2 = Veteran  adds m_NbToAddInVeteran (0x470)
    1 = Recruit  adds nothing
m_iNextWaveTrigger (0x480) = RandRange(m_RemainingTrigger .Min 0x4a4 / .Max 0x4a8)
```

### The advance, `0x0040A780`, with `$s2` = the actor

```
return if m_iNbSpawned >= m_iNbToSpawn
walk m_aTerrorist[] and remove anything that fails IsAlive
return if m_iNextWaveTrigger < liveCount
else rearm m_iNextWaveTrigger and release
     n = min(RandRange(m_NumberInWave), m_iNbToSpawn - m_iNbSpawned)
```

So **authored** = min/max terrorists, the difficulty bonuses,
`m_RemainingTrigger` and `m_NumberInWave`; **derived at run time** =
`m_iNbToSpawn`, `m_iNextWaveTrigger`, `m_iNbSpawned`. Replacing the instruction
that forms a derived value with a `li` sets it for every zone in the game.

| VA | stock | becomes | option |
|---|---|---|---|
| `0040AF58` | `02221021` `addu v0,s1,v0` | `addiu v0,zero,N` | enemies each zone owes |
| `0040A8A8` | `02028021` `addu s0,s0,v0` | `addiu s0,zero,M` | released per wave |
| `0040AFDC` | `02231821` `addu v1,s1,v1` | `addiu v1,zero,T` | trigger, seeded at init |
| `0040A874` | `02021021` `addu v0,s0,v0` | `addiu v0,zero,T` | trigger, rearmed each wave |

Both trigger sites must be set together, or the shipped `RandRange` comes back
the first time a wave fires.

### The stasis gate — the one that matters

The advance opens with an EE bit-extract, not an `andi`:

```
0040A784  lbu    $v0, 0x6f($a0)     byte holding bits 24..31 of the Actor bool word at +108
0040A788  dsll32 $v0, $v0, 27
0040A78C  dsra32 $v0, $v0, 31       => bit 4 of that byte = 0x10000000 = bStasis
0040A790  beqz   $v0, continue      set -> return immediately
```

`bStasis` is engine-managed: Unreal 2 re-marks an actor in stasis every frame
its zone holds no player, so clearing the flag at init never sticks — an
init-time write to it was measured being overwritten. **Patch the test, not the
flag.**

| `0040A790` | meaning |
|---|---|
| `10400003` | stock `beq` — only the zone the player is standing in feeds |
| `10000003` | `b` — every zone feeds, always |
| `14400003` | `bne` — only zones the player is *not* in feed |

This single word is what made wave mode work at all. Everything tried before it
was chasing a value the engine owns.

### Hunt from start

`m_bHuntFromStart` is bit `0x40` of the `R6DeploymentZone` bool word at actor
`+904`. The three instructions used to set it are ones the `m_iNbToSpawn`
constant above makes dead — two pad nops and the `mfhi` whose result it
overwrites — so **this option requires the total to be set**, and the tool
enforces that.

| VA | stock | becomes |
|---|---|---|
| `0040AF4C` | `00000000` | `8E010388` `lw at,0x388(s0)` |
| `0040AF50` | `00000000` | `34210040` `ori at,at,0x40` |
| `0040AF54` | `00001010` `mfhi v0` | `AE010388` `sw at,0x388(s0)` |

The full bool map at `+904`, for reference: DontSeePlayer `0x1`, DontHearPlayer
`0x2`, HearNothing `0x4`, AllowLeave `0x8`, PreventCrouching `0x10`,
HuntDisallowed `0x20`, **HuntFromStart `0x40`**, UseRocketLauncher `0x80`,
IsTargetable `0x100`, DeleteTerrosWhenDead `0x200`, GrabHostage `0x400`,
HitHostage `0x800`, NotSurrender `0x1000`, AlreadyInitialized `0x8000`.

### Map-wide spawn points — cheat file only

`AR6DZoneWave::SpawnATerrorist` is wave vtable `0x00623380` slot `+0x188` →
`0x0040AB60`. It walks `m_aSpawningPoint` (data `0x484` / count `0x488`),
filters for eligibility, picks one at random, and calls that point's own spawn.
The wave's release loop calls it `n` times, so `n` is **not** capped there —
the cap is the number of eligible points, and every one of them sits beside its
zone. Island's two waves have 2 and 3 points and released exactly 2 and 3.

A 67-instruction cave at `0x005BA488` replaces the random pick with a scan of
the level's whole actor list for `R6DZonePoint`:

* `AActor::XLevel` is at **+0x2e4** (the `Level`/`ALevelInfo` at +0x104 is not
  the `ULevel`)
* `ULevel::Actors` data **+0x2c**, count **+0x30**
* type-test with the `R6DZonePoint` **instance vtable `0x0061E2F0`**, a fixed
  overlay address — not the `UClass` pointer, which is a heap allocation and
  moves between runs
* hijack: `0040ACA0` `0c051b7c` (`jal rand`) → `0816E922` (`j 0x005ba488`)
* no match falls back to `m_aSpawningPoint[0]`; nothing at all returns 0 through
  the existing cleanup path

**This cannot be baked into the disc.** Written once into the overlay image, the
cave region is gone by the time the level finishes loading and the game hangs on
the jump into zeros — measured, and reverted. A cheat file rewrites it every
frame, so it is always intact when called. (Corollary, learned the hard way:
never put a cheat-file patch on a *hot* loop either — rewriting code memory every
frame forces the recompiler to rebuild that block continuously and it took the
emulator down.)

---

## Split screen

| VA | stock | becomes | effect |
|---|---|---|---|
| `00302DA8` | `AF8080CC` `sw zero,-0x7f34(gp)` | `00000000` | first-person weapon |
| `003F1934` | `1440004F` `bne` | `00000000` | impact decal on world geometry |
| `003F1BB4` | `14400084` `bne` | `00000000` | impact decal on actors |
| `003F250C` | `14400014` `bne` | `00000000` | impact emitter |
| `003531D0` | `14400053` `bne` | `00000000` | rain and snow |
| `003A14B8` | `14400015` `bne` | `00000000` | blood effect update |
| `002375E0` | `A2420065` `sb v0,0x65(s2)` | `00000000` | `m_bHideInSplitScreen` |

### The view model

```
00302D9C  lw   $v0, 0x4e4($s1)      GameEngine->m_SplitScreenMode
00302DA0  beqz $v0, 0x302dac        not split screen -> leave the flag alone
00302DA8  sw   $zero, -0x7f34($gp)  else g_bDrawFirstPersonWeapon = 0
```

That global has exactly **one writer and one reader** in the entire overlay, and
it ships as `1` at `0x006537BC`. The reader gates the first-person update inside
the render pass:

```
0030E2C0  m_bAllow3DRendering                           passes in both
0030E2E0  viewport->+0x34->+0x57c->+0x3d8 non-null      passes in both
0030E2F4  +0x4d8 bit 6 clear                            passes in both
0030E308  +0x4d9 bit 5 clear                            passes in both
0030E318  -0x7f34(gp) non-zero       1 in SP, 0 in SS   FAILS in split screen
0030E32C  pawn->+0x468 equipped weapon non-null         passes in both
0030E360  jalr weapon vtable[0x170] = 0x003F53B0        the update
```

Static cross-referencing could never have found this: the caller gets the weapon
from `pawn+0x468` four instructions before the dispatch, but through a value
returned by a call, so no offset-window search matches.

### `m_bHideInSplitScreen`

`ParticleEmitter`'s bool word is at offset 100; the flag is `0x0200` and
`Disabled` is `0x2000`. At `0x002375B0`:

```
if (splitScreen && emitter->m_bHideInSplitScreen) emitter->Disabled = true;
```

Measured on a level with one player facing fire and the other facing water: 532
emitters, 6 flagged, 6 disabled, 6 both, 0 disabled without the flag. The actors
were always there — only their spawning was switched off.

**Counting flags across states proves nothing here.** The flag is authored data
and is identical in single player and split screen. What matters is the one site
that acts on it.


### Player 2's look speed in split screen

Player 2's input timestep is clamped. At `0x00142028`:

```
00142028  c.lt.s $f21, <0.033f>        is the real frame delta under 33 ms?
00142030  bc1f   +6                    no -> leave it alone
00142034  addiu  $v1, $zero, 1
00142038  bne    $s2, $v1, +4          pad index != 1 -> leave it alone
00142040  lui    $v1, 0x3d4c
00142044  ori    $v1, $v1, 0xcccd      $v1 = 0.05f
00142048  mtc1   $v1, $f21             player 2's dt := 0.05 s
```

So whenever the game runs faster than 30 fps, **player 2 alone** gets a fixed
0.05-second timestep while player 1 keeps the true delta. At 60 fps that is
three times slower for the same slider setting, which is exactly the reported
symptom -- player 2 at 10 never matching player 1 at 10.

| VA | stock | becomes | effect |
|---|---|---|---|
| `00142048` | `4483A800` | `00000000` | player 2 keeps the real frame delta |

Removing the store is enough: `$f21` already holds the true delta, since that is
what the compare two instructions earlier tested. The same value also drives
player 2's movement rate and button auto-repeat, so those become correct too.

Six other explanations were tested and refuted before this one: a different
multiplier per player (both viewport fields have exactly one writer each, from a
single global), a wrong settings slot (all eight writers and eight readers pair
P1 and P2 symmetrically), a lower menu maximum (same code shape for both), a
viewport or aspect term (the only geometric term is a shared FOV value), the
split-screen bool gating the look path (nothing in the whole look routine reads
it), and a different stick conversion (both run the same one).

**Player 2's settings not surviving a mission load is a separate problem and has
no patch.** Eight persistence layers and sixteen store sites are symmetric
between the players. The one remaining candidate -- that the level-start
settings copy runs once per level rather than once per player -- cannot be
settled statically, and if true needs a code cave rather than a word. The
one-word version that looks like a fix would stamp the single-player defaults
onto both controllers every frame and break player 1 too.

---

## World

| VA | stock | becomes | effect |
|---|---|---|---|
| `00379B30` | `24060020` `addiu a2,zero,32` | `addiu a2,zero,N` | decal ring size |
| `00317570` | `1460001D` `bne` | `1000001D` `b` | skip body despawn path 1 |
| `003175F4` | `1460000B` `bne` | `1000001D` `b` | skip body despawn path 2 |
| `00317600` | `3C034040` `lui v1,0x4040` | `lui v1,<float>` | despawn window |

`R6DecalManager` builds five `R6DecalGroup`s at `0x00379A90`:

| group | type | `m_MaxSize` | set at |
|---|---|---|---|
| footsteps | 0 | 32 | `00379B44` |
| wall hits | 1 | 32 | `00379B4C` |
| grenade decals | 4 | 8 | `00379B54` |
| blood splats | 2 | 16 | `00379C64` |
| blood baths | 3 | 8 | `00379C6C` |

Footsteps and wall hits share the register loaded at `00379B30`, which is why
one word moves both. Each group is a ring of that many `R6Decal` actors at 1,099
bytes each, recycled in place — it cannot be made unlimited by construction.

Body timer constants for `00317600`: 15.0s `3C034170`, 30.0s `3C0341F0`,
60.0s `3C034270`. The comparison is against `LevelInfo.TimeSeconds`, so the
constant really is seconds.

---

## Things this tool knows how to clean but never writes

`0x0011D8C4`–`0x0011D8FC` is genuine function-end padding, and `0x0017F530`–
`0x0017F534` is a function prologue. A tracing stub from the research that
produced this profile lived there. The tool carries their stock values so it can
return a disc that still has them to stock, rather than refusing to touch it.

---

## Not shipped: AI teammates in split screen

Recorded because the negative result is worth as much as the patches.

`R6RainbowTeam.CreatePlayerTeam` at package offset `0x0014721D` opens with
`JumpIfNot(0x0354, …)`, and `0x04d1` is the single-player branch that builds
members 2 and 3. Retargeting those two bytes is a legal, length-preserving edit
— proven by a control that retargets them to a semantically identical address
and loads fine.

Four attempts, four **byte-identical** hang states — 23,969 live objects,
`m_Team = [PriceWinter0, PriceWinter1, None, None]`, `m_iMemberCount = 1`, both
Loiselle and Weber classes loaded, no pawn instance of either:

1. plain retarget
2. plus passing player 1's controller to the AI calls, since the split-screen
   branch reassigns the local to player 2 and never restores it
3. plus `bNoCollisionFail = True` on the spawn
4. plus neutralising `RemoveMember`

The outcome is invariant to every downstream edit, so the cause is upstream of
all of them and is still unidentified. Two models were built and both refuted:
the spawn loop is **bounded** (24 tries, then it logs and returns), and
`RemoveMember` was never destroying anything.

Useful constraint for anyone continuing: in these packages an object or name
reference is a 1–5 byte compact index that the loader rewrites into a flat
4-byte pointer, but `Jump`/`JumpIfNot` targets are written at compile time as
offsets into the **expanded memory** layout. So a replacement must preserve a
statement's *memory* length, not its file length. Retargeting a jump is safe;
deleting a statement is not, and padding with `EX_Nothing` does not work because
N file bytes expand to N memory bytes while the original occupied more.

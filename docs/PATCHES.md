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
0040A78C  dsrl32 $v0, $v0, 31       => bit 4 of that byte = 0x10000000 = bStasis
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
The wave's release loop calls it `n` times, so `n` is **not** capped there — and
it is **not** capped by the eligible count either. When the filtered list comes
back empty the picker falls through: `0040AC94 bnez $v0` takes the filtered
array at `$sp+0x98` only when its count is non-zero, and `0040AC9C addiu $s0,
$s5, 0x484` otherwise hands it the whole of `m_aSpawningPoint`. The release
proceeds regardless. Island's two waves have 2 and 3 eligible points and
released exactly 2 and 3, which is what the earlier reading was built on, but
that is a coincidence of those waves rather than a cap.

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

---

## Enemy grenades, and two things that are not what they look like

**There is no throw chance anywhere in the game.** What a terrorist spawns
holding is a weighted roll made once, at spawn, over a table in his template:

```
NbOfGrenade=2
020, R6Weapons.r6fraggrenadegadget
080, None.None
```

The native parser reads those lines with a `"%03d, %s"` scanf, converts the
weights to a prefix sum and checks they total 100; the picker rolls
`rand() % 100` once and nothing re-rolls. Once a terrorist is carrying a
grenade the decision to use it is deterministic, gated only by
`m_fMinDistToThrowGrenade` and the per-difficulty reaction delays. So "how
often do enemies throw grenades" is really two separate questions -- how many
of them have one, and when they are allowed to use it -- and the tool exposes
both.

The 118 templates sit as one contiguous plain-text run inside each COMMON
package. Sixteen of them use the two-entry shape above, at weights between 15
and 30; the rest are `100, <grenade>` (always) or `100, None.None` (never).
Only the sixteen are adjustable, because a digit-for-digit edit is the only
kind a LIN package will take -- see `tcps2/lin.py`.

### `WS[43]` is dead data -- do not use it

Each `/MAPS/<NAME>.INI` carries a table that looks exactly like the answer:

```
WS[43]=(bUsing=true,weaponname="R6MolotovGadget",sndName0="Foley_FragGrenade",...)
```

It ships `true` on the Alcatraz maps and `false` elsewhere, which is a very
persuasive coincidence. **Nothing reads it.** `bUsing`, `weaponname`,
`sndName0` and the literal `WS[` appear **zero** times in the overlay, in the
boot executable, and in every decompressed level package. Unreal's config
importer resolves struct members through the package name table, so a member
name that is absent from every name table cannot be imported. It is a leftover
of the Xbox and PC `MultiBank_SoundLoad` system.

The data agrees: `MEATPACKING.INI` and `OLDCITY.INI` both ship `WS[43]` true,
and no `Meat-*` or `OldC-*` template lists a molotov. An earlier build of this
tool offered "molotovs on every level" on the strength of that table; it was
withdrawn.

Only four of the 118 templates offer a molotov at all. Giving one to the others
means replacing `r6fraggrenadegadget` with `R6MolotovGadget` -- a shorter name,
so it would need padding after the comma, and a previous whitespace-padded
attempt on these packages hung the loader. Untested, not shipped.

### "Man down" in split screen: no Rainbow voice can play at all

Worth recording because the obvious fix is real, reachable, and useless on its
own. `R6PlayerController.PlaySoundDamage`, death case:

```
JumpIfNot(@0xa1, !Level.Game.m_bIsSplitScreen)         <-- the gate
JumpIfNot(@0xa1, m_TeamManager.m_iMemberCount > 0 && m_Team[1] != None)
m_Team[1].Controller.PlaySoundCurrentAction(23)        <-- "Lead down"
```

Voice action 23 is `m_sndLeadDown`; 24, 25 and 26 are Loiselle, Price and
Weber, and `R6RainbowAI.PlaySoundDamage` picks between them on
`m_iOperativeID` when an AI teammate goes down.

Three things stand in the way, and only the first is a gate:

1. That `!m_bIsSplitScreen` test. Removable.
2. The speaker is `m_Team[1].Controller`, hardcoded. The array really does hold
   both players in split screen -- measured, slots are
   `[R6RainbowPriceWinter0, R6RainbowPriceWinter1, None, None]` -- so slot 1 is
   the other player, and `R6PlayerController` does not override
   `PlaySoundCurrentAction`. The inherited `Controller.PlaySoundCurrentAction`
   is two bytes: `Return(Nothing)`.
3. It could not speak even then. **`PlayRainbowVoices` has exactly one caller in
   the entire loaded script** -- `R6RainbowAI.PlaySoundCurrentAction` -- and it
   reads `R6RainbowAI.m_VoicesMgr`, which only an `R6RainbowAI` ever creates
   (`New(..., R6PriceVoices / R6LoiselleVoices / R6WeberVoices)` then `Init`).

And split screen has no `R6RainbowAI` at all. Measured across savestates:

| | R6RainbowAI | voices-manager instances | player controllers |
|---|---|---|---|
| single player | 3 | 3 (Price, Weber, Loiselle) | 1 |
| split screen | 0 | **0** | 2 |

`m_iMemberCount` reads 1 in both, so that guard is not what differs.

So the call-out is not suppressed in split screen -- **no Rainbow voice line of
any kind can play there**, because the only thing in the game that owns a voice
is the AI teammate.

**Shipped, experimental.** `tcps2/rsemandown.py` drops the gate and replaces the
dead call with one that builds its own voice:

```
if (True)
    if (m_iMemberCount > 0 && m_Team[1] != None)
        new R6PriceVoices.PlayRainbowVoices(m_Team[1], 23)
```

Both halves are lifted from shipped code rather than invented -- the
`New(Nothing, Nothing, Nothing, ObjectConst(R6Engine.R6PriceVoices))` is copied
out of `R6RainbowAI.Possess`, and the `PlayRainbowVoices` name index (1207) off
its one existing caller. `Init()` is deliberately skipped: all it does is
`AddSoundBankName("X_Voices_Price")`, and all three operative voice packages are
already live `Package` objects in a split-screen savestate.

It fits the function's 283 disk bytes **exactly**, with nothing spare, which is
what the two limitations come from. It always plays line 23, so player 2 going
down is announced as the lead rather than as Price; and the speaker is team slot
1, which the game hardcodes, so in split screen that is player 2's own pawn --
when player 2 is the one who died the line comes from a dead man and may not
play at all. Both are fixed by giving player 2 a real operative identity.

Locating it needed care and the note is worth keeping: this function has no
string constants, so it cannot be found by its own text, and the obvious anchor
-- the block's `ScriptSize` word -- is changed BY the edit. Diffing the block
before against after leaves only two byte runs untouched; the anchor is the long
one, and it starts two bytes into the bytecode because byte 1 is the low half of
the opening jump's target, which moves.

### Split-screen enemy accuracy: there is nothing to switch

Every channel by which native code can learn it is in split screen was
enumerated -- 82 accesses across four of them -- and not one lies in weapon,
aim, dispersion, line-of-sight, observation, reaction-timer or damage code. The
21 `m_bIsSplitScreen` tests are three pad-rumble, two input-settings, five
HUD loop bounds, one audio listener, one controller broadcast, one proximity
trigger, seven render/viewport and one animation LOD. The accuracy model itself
lives in one `[Engine.R6GameplaySettings]` INI section with no split-screen
variant, and the AI's combat verbs are UnrealScript rather than native.

The one place split screen picks a different number is a leaf returning 3
instead of 6 -- traced to its format string, that is the **audio streaming voice
budget**.

## Teammate ammunition, and the callout it unlocks

Two keys in `R6GAMESETTINGS.INI`, sitting together under the file's own comment
`; the following is for rainbow AI only`:

```ini
m_bUnlimitedRainbowMagazines=true
; Bullets to put in primary weapon when all clips are empty
m_iNbOfBulletWhenEmpty=5
```

The first is why Price, Weber and Loiselle never run dry, and therefore why
their ammunition line never plays. Both are shipped values, read off
`Tom Clancy's Rainbow Six 3 (USA).iso.orig`, where all three VOKES copies of
the file are byte-identical.

### The voice banks say what does and does not exist

`X_Voices_Price.LS1` and its Weber and Loiselle twins hold 125 clips each, the
same script in three voices. Clip 20 is "No ammo, sir" and clip 21 is "Weapon's
dry". **There is no reload line, and this is not a gap in the transcript -- it
is a gap in the game.** Two independent inventories agree:

* The DARE event names are recoverable from the decompressed `COMMON.LIN`. Price
  has **101** `Play_Price_*` events, and exactly one of them is about
  ammunition: `Play_Price_Ammo_Out`. There is no `Play_Price_Reload`, no
  magazine event, no weapon-switch event. Weber and Loiselle have the same 101
  -- note Loiselle's prefix is `Play_Lois_`, not `Play_Loiselle_`. The name
  list appears TWICE in `COMMON.LIN`; the first block holds only 97 of them, so
  read the second or you will undercount by four.
  The only reload and switch events anywhere in the game's 209 sound banks are
  weapon foley: `Play_Shotgun_Reload`, `Play_GrenadeLauncherReload`,
  `Play_GrenadeLauncherSwitch`.
* The script side matches. Every voice and sound slot on the pawn and AI classes
  is an `m_snd<Something>` property, and the complete list -- **185** distinct
  names, from `m_sndAccessingComputer` to `m_sndWoundedSevere` -- contains
  exactly one ammunition entry, `m_sndAmmoOut`. No `m_sndReload` of any
  spelling exists, and the only other name matching ammunition, clips,
  magazines, reloading, bullets or weapon-switching is `m_sndBulletFizzSound`,
  which is a round going past your head.

So "restore the reloading dialogue" has no subject. What CAN be restored is the
line that was recorded, wired and then made unreachable by a single `true`.

### The bank format, corrected

The research parser these banks were first read with
(`R6_3_PS2_CutContent/tools/bankmap.py`, outside this repo) gets the right
answers but its documented field offsets are `+4` out: it bases each resource
record at `name - 0x44` when the record starts at `name - 0x40`, and the two
errors cancel. Anyone reusing those offsets on a different bank will be wrong.
The real layout, re-derived and checked against
the header arithmetic (`28 + 101*72 + 155*108 + 672 = 24712` = the exact file
size):

```
resource record, 108 bytes
  +0x00 u16 id / u16 bank tag   +0x04 kind   +0x08 length or child count
  +0x0c tail offset (kind 10)   +0x10 stream offset   +0x18 child count
  +0x2c sample rate             +0x30 sample count    +0x40 char[40] stream name
```

`kind` is **1** for a stream (125 of them), **10** for a weighted random
container (24) and **15** for a null (6). A container's children live in the
672-byte tail as 12-byte `(resource id, weight, 0)` records whose weights sum to
`0x10000`.

The event record's four words at `+0x1c..+0x28` are **not** variant slots, which
is what an earlier note recorded. Across all 209 banks, 3,853 of 5,775 event
records carry non-`-2` values there, and the values are 16.16 fixed point --
3.0, 3.5, 0.5, 1.0, 10.0, 10.5, 20.0, 25.0, 30.0, 50.0 -- with `-2`, `-1` and
`0` as sentinels. They are distance or range parameters, not alternate takes.

### 29 recorded lines are wired to nothing

Of the 125 clips in each operative bank, **96 are reachable from an event and 29
are not** -- 33.6 seconds of finished, recorded dialogue that can never play.
The cause is 12 random containers (`133, 138, 145, 154, 157, 162, 165, 168, 171,
172, 173, 177`) that nothing references: the audio was recorded and authored
into containers, and the event table was never re-pointed at them. The three
banks are logically identical, so it is the same 29 lines in all three voices.

They are a coherent late block rather than scattered offcuts -- the whole
fire-reaction set, the whole "Ding" encouragement set, the smoke callouts and
the in-position calls:

> Taking fire · Take cover · Use the smoke as cover · The smoke will give us
> cover · That's nasty stuff · Burn them out · Light them up · Nice shot · Take
> them out, Ding · Ding, you're taking hits · Make them pay, Ding · **I'm
> burning** · **I'm on fire** · **Fire's out, I'm good to go** · **I'm alright,
> the fire's out** · Already in position · In position · Holding position and
> waiting for orders · Still waiting for orders · Still can't, sir · Lost our
> breaching charges, sir -- can't complete order · Files downloaded · Escorting
> hostage · ...precious cargo · Security deactivated · Taking lock · Roger,
> secure terrorist on Zulu · Roger, electro up · Roger, open frag and clear

**This retracts an earlier note** which reasoned that because molotovs are live
in the game, the on-fire reactions (clips 115-118) were probably reachable. They
are not: all four are orphaned. A teammate set alight by a molotov says nothing.

The same break shows from the other side. **17 of the 101 events resolve to no
audio at all** -- 15 name a resource id that has no record (`0, 27-31, 39-43,
50, 69, 118, 119`) and 2 point at a kind-15 null (events 37 and 94). Six further
ids are missing but are still cited as container children (`26, 38, 44, 45,
120, 121`), so several live containers are random picks with a silent leg: the
"Flashbang out" container 35 is a 2-way with one dead branch, and so are 56, 63
and 145. So the bank is unfinished in both directions -- events that play
nothing, and finished recordings nothing plays. Re-pointing the dead events at
the orphaned containers would restore most of it, and is blocked on the same
unknown: which event is which.

### The ammunition cue is half-wired, and it is not obvious how to fix it

The two ammo takes never play as a pair. Resolved exhaustively over all 101
events and all 24 containers:

```
clip 20 "No ammo, sir."     = resource 34 <- event 21, directly
clip 21 "Weapon's dry."     = resource 33 <- container 51 <- event 31
clip 19 "Roger, I'm on it." = resource 32 <- container 51 <- event 31
container 51: 2 children, resource 32 at weight 0x8001, resource 33 at 0x7fff
```

So **"Weapon's dry" only ever plays on a coin-flip against "Roger, I'm on it"**,
a line that belongs to acknowledging an order. Identical in all three banks, at
the same file offset (`0x5ea8`).

Aligning the event-name list against the clip order by content makes the
recording script's intent fairly clear -- names 5..14 map onto clips 11..25 with
no gaps, putting `Order_FromLead` on clip 19 and `Ammo_Out` on clips 20 **and**
21 -- which reads as an off-by-one when container 51 was authored: it took
resources `{32, 33}` where the script implies `{34, 33}`.

**No switch is shipped for this**, because the two readings of the same data
call for opposite edits and nothing static separates them:

* **Event 31 is `Ammo_Out`.** Then the ammo cue is a coin-flip that says "Roger,
  I'm on it" half the time, and the fix is to repoint container 51's first child
  from resource 32 to resource 34.
* **Event 21 is `Ammo_Out`** (which is what the content alignment above
  implies). Then `Order_FromLead` is the container, a teammate says "Weapon's
  dry" while acknowledging an order, and the fix is the other way round.

Resource 32 is referenced by container 51 and by nothing else, so the first fix
orphans "Roger, I'm on it" -- trading one silent line for another. And the
name-to-event-ID binding is genuinely unknown: the positional fits fail (the lag
between name index and event row runs 1 -> 19 -> 14, so it is not a constant
offset), and a 105-member `RV_*` enum fitted against the clip text over all 28
offsets peaks at 27% with plain contradictions.

**The test that settles it costs one playthrough.** Repoint container 51's two
children at two clips that could never be confused -- say resource 65
("Murphy. Murphy.") and resource 85 ("Fire in the hole.") -- and note when they
come out of a teammate's mouth: on an order, or on an empty weapon. Four bytes
at file offset `0x5ea8` in each bank, same offset in all three. Once that is
known the real edit is the same four bytes.

### What the tool does with that

The **Teammates** page carries two cards, both plain INI edits:

| card | key | shipped | what turning it on does |
|---|---|---|---|
| AI teammates run out of ammunition | `m_bUnlimitedRainbowMagazines` | `true` | writes `false`, so the team spends magazines and can reach "Weapon's dry" |
| Rounds left in a weapon that has run dry | `m_iNbOfBulletWhenEmpty` | `5` | writes the chosen reserve; `0` means dry is dry |

The reserve is only written when the switch is on, because a reserve reached
only when the magazines are gone is meaningless while they are unlimited.

One caveat specific to a disc that was hand-edited before this tool ever saw
it. Every data edit is applied to `store.original(...)` -- the backup store --
rather than to the live file, so that applying twice gives the same disc and
clearing a card really undoes it. But the backup store records what was on the
disc the first time this tool touched it. On a disc where someone had already
set `m_bUnlimitedRainbowMagazines=false` by hand, *clearing* this card restores
`false`, not the shipped `true`. To get the shipped values back on such a disc,
apply to a pristine image, or set the card on and the reserve to 5 and read the
difference as deliberate rather than stock.

**Every teammate always has something in the secondary slot**, so a dry primary
is not the end of the fight: across the 48 map INIs that declare teammate
loadouts there are 567 entries and not one leaves `szSecondaryWeapon` empty.
534 of them are an actual pistol (92FS, Mk23 or USP). The exception is
**Trieste** -- 21 of its entries put a breaching charge, flashbang or smoke
grenade in the secondary-weapon slot instead of a sidearm, so on that level the
team has nothing to fall back on. (`/MAPS/DEMO.INI` does the same for all 12 of
its entries, but no campaign mission loads it.)

### Drawing the sidearm: the decision is script, and it is dead on retail

`R6RainbowAI.RainbowReloadWeapon` is where a teammate chooses between reloading
and switching. **It is UnrealScript, so there is no word in `SP.SOZ` to patch.**
That was settled from the live `UFunction` layout, not from naming: `+0x78`
holds the C++ entry point, and 3,699 of the 4,357 loaded UFunctions carry
`0x0014f200` there, which is `UObject::ProcessInternal` -- the script VM.
`SwitchWeapon`, `RainbowReloadWeapon`, `NeedToReload`, `R6Weapons.HasAmmo` and
`CanReload` are all in that set, and `R6Rainbow` has no natives at all. The
whole native surface of `R6RainbowAI` is ten functions, none of them about
weapons.

```
if (Pawn.EngineWeapon.m_iCurrentNbOfClips > 0)        <-- THE GATE
    ... ReloadWeapon();
else if (m_iCurrentWeapon == 0 && m_WeaponsCarried[1].HasAmmo())
    SwitchWeapon(1);                                  <-- rifle -> pistol
else if (m_iCurrentWeapon == 1 && m_WeaponsCarried[0].HasAmmo())
    SwitchWeapon(0);
else if (!m_bWeaponsDry) { m_bWeaponsDry = true; PlaySoundCurrentAction(12); }
```

**On a stock disc that switch branch cannot be reached at all.**
`R6Weapons.PostBeginPlay` gives every AI Rainbow weapon
`m_bUnlimitedClip = true; m_iCurrentNbOfClips = 1` whenever
`m_bUnlimitedRainbowMagazines` is set, and
`R6Weapons::execNativeServerFireBullet` (VA `0x003f0a40`) then takes its
`unlimited && clips == 1` path forever and never reaches `clips--`. So the clip
count is pinned at 1 for the whole mission and the gate is always true. Turning
the ammunition switch off is a prerequisite for any of this, which is why the
sidearm card requires it.

The magazine is already the trigger by the time this function runs --
`NeedToReload()` returns true on `m_iNbBulletsInWeapon == 0`, and `AttackTimer`
only calls it then -- so the one thing between "magazine empty" and "draw the
pistol" is that clip comparison.

Two one-byte edits were considered before the tool below existed, and both are
recorded because they are cheap and might be wanted again. `EX_IntZero` ->
`EX_IntOne` at plain offset `0x12fb04` turns `clips > 0` into `clips > 1`, so a
teammate on his last magazine draws the pistol instead of loading it -- but once
BOTH weapons are on their last magazine each still reports ammunition and
neither will reload, so they can swap back and forth without firing. Swapping
the operator instead at `0x12faf4`, `0x97` (`Greater_IntInt`) -> `0x96`
(`Less_IntInt`), makes the test never true -- and this is the only reload path
Rainbow AI has, so they would never reload again. The shipped option does
neither; it puts a roll on the gate.

### The chance, and the bytecode tool it needed

A *chance* of switching is not a byte edit. It needs `if (Rand(100) < N)`
inserted at the gate, and inserting bytecode into a cooked package means solving
the thing that makes these files awkward: **a script block's jump operands are
offsets into the LOADED image, and the file is shorter than the loaded image.**

```
<u32 ScriptSize> <bytecode ...>
```

`ScriptSize` is the **memory** length. The loader runs
`while (iCode < ScriptSize) SerializeExpr(...)` and converts as it reads: an
object, property, function or name reference is a 1-to-5 byte `FCompactIndex` in
the file and a flat 4 bytes once loaded. Across this package, 503,021 disk bytes
become 688,623 in memory -- a factor of 1.369. So an inserted byte moves every
downstream jump by the *memory* delta while the file grows by the *disk* delta,
and the two are never the same number.

`tcps2/uscode.py` is that tool. Three things it has to get right, each of which
would corrupt a function if guessed:

* `EX_Jump`, `EX_JumpIfNot`, the "next case" word of `EX_Case`, `EX_Iterator`
  and the DWORDs of an `EX_LabelTable` are **absolute memory offsets** and are
  re-based.
* `EX_Context`, `EX_ClassContext` and `EX_Skip` carry a **size**, not a target,
  and are re-measured. The two contexts store the guarded expression's length;
  `EX_Skip` stores one MORE than its expression. That is measured, not assumed
  -- 13,900 contexts and 2,428 skips across the package agree -- and about
  seventy of the disc's own skips store something else again, short-circuit
  chains where the compiler jumped somewhere shorter, so the tool **adjusts each
  word by however much its expression actually moved** rather than recomputing
  it. An untouched skip therefore comes back byte-identical whatever it held.
* `EX_Assert`'s word is a source line number and is left alone.

**How it was checked.** A PCSX2 savestate holds the loaded image of every script
struct (`UFunction +0x40` is the Script pointer, `+0x44` its length), so the disk
parse can be checked against what the console actually has. Rebuilding the
in-memory image from the file and comparing byte for byte -- ignoring only the
4-byte reference slots, which hold heap pointers -- **3,710 live script structs
reconstruct exactly, with zero non-reference bytes differing.** The residue is
656 one and two-byte stubs too short to locate unambiguously, plus classes that
live in another package. The test suite re-proves the weaker half without a
savestate: of 6,801 script blocks found in `COMMON.LIN`, **6,738 round-trip
parse -> assemble to identical bytes and 63 are refused. None is mangled.**

**The edit.** The gate becomes

```
clips > 0 && (Enemy == None || Rand(100) < 100 - chance)
```

so that percentage of dry magazines falls through to the sidearm branch, and
only while the teammate is actually in contact -- one with nobody shooting at
him always reloads, which is what he should do. The contact test is the game's
own: this function already checks `Enemy != None` to decide whether to break off
an attack before reloading, and the reference is **lifted from that statement**
rather than hardcoded or resolved through the import table, so it stays correct
on a disc whose tables number things differently. (Confirmed against live RAM:
the operand resolves to `Controller.Enemy`.) The contact half is a switch of its
own, so it can be turned off.

The shapes of both operators are taken from shipped code rather than assumed --
every one of the package's 877 `OrOr_BoolBool` has an `EX_Skip` as its second
argument, and `(InstanceVariable, NoObject)` is the commonest of the 208
`EqualEqual_ObjectObject`. The disk length
is held fixed by reclaiming the dead `if (bShowLog) Log(" needs to reload
weapon")` pair -- `bShowLog` reads False on all three live teammate AIs -- and
padding the remainder with `EX_Nothing` after the final return, which is valid
bytecode the loader will decode and execution never reaches. The block's memory
length drops 579 -> 573 without the contact test and 579 -> 576 with it, and the
`ScriptSize` word in front of it is rewritten to match. The result is read back through the same parser before it is written.

### Calling out a reload, since there is no reload line

There is no reloading dialogue on this disc (see above), so the nearest honest
thing is to play the line that does exist. The dry branch ends with
`PlaySoundCurrentAction(12)`, and 12 is the only argument anywhere in the loaded
script that reaches `m_sndAmmoOut`. A second, rolled copy of that call is
inserted at the end of the RELOAD branch:

```
... ServerSwitchReloadingWeapon(True); ReloadWeapon();
if (Rand(100) < say) PlaySoundCurrentAction(12);
```

The branch's closing `Jump` is found structurally rather than by offset -- the
reload gate's own target is the first `else if`, so the statement in front of it
closes the branch -- and the new test jumps to that same statement when the roll
fails. The function name is lifted from the shipped call, like `Enemy` is.
Nothing else changes: `m_bWeaponsDry` is not set, so it is purely audible.

This one needs no other setting. It sits in the branch that runs either way, so
it works on a stock disc -- where teammates reload constantly, which is why the
card says to start low. Its bytes come from a second dead log,
`" needs to switch to secondary weapon"`, so the two options never compete for
the same budget.

One thing is genuinely unknown and is on the card: the ammunition event resolves
to "No ammo, sir", but the only other event reaching an ammunition take is a
50/50 against "Roger, I'm on it", and which of the two `m_sndAmmoOut` is could
not be pinned down.

The card is capped at 90%. A teammate who never reloads would sit between two
weapons that both still report ammunition and neither of which ever gets loaded.

Still true, and the reason the whole page hangs together: none of this is
reachable until `m_bUnlimitedRainbowMagazines` is off, because the clip count is
pinned at 1 while it is on.

Two related facts, both from the same decode. `m_bWeaponsDry` is written in
exactly one place in the entire loaded script, the final else-branch above; and
`PlaySoundCurrentAction(12)` on the line after it is **the only call with
argument 12 anywhere in the script dump**, reaching `m_sndAmmoOut` through
`R6RainbowVoices.PlayRainbowVoices`. So the ammunition line marks *both weapons
dry*, not the transition -- **nothing is spoken when a teammate draws his
pistol**.

### Correction: these are not Xbox differences

An earlier version of this tool listed both keys as things the **Xbox** build
does differently, on the "...including the Xbox ammunition rules" card. That was
wrong in both directions, and the way it went wrong is worth recording because
the module had already warned against it once.

The Xbox comparison needs the PS2 side read off a **pristine** image. A first
pass read a played disc and absorbed twelve of the player's edits. The fix was
to read the backup store instead -- but the backup store holds what was on the
disc before *this tool* touched it, which says nothing about a disc hand-edited
in an earlier session. Three values got in that way:

| key | recorded PS2 | real PS2 | real Xbox |
|---|---|---|---|
| `m_fMinDistToThrowGrenade` | 200 | **500** | 500 |
| `m_bUnlimitedRainbowMagazines` | false | **true** | true |
| `m_iNbOfBulletWhenEmpty` | 0 | **5** | 5 |

None of the three is a difference between the builds at all. A full key-by-key
diff of the pristine PS2 INI against the Xbox `System/xboxdynamic.umd` gives 239
keys in common and **18** that differ; the seven the tool writes are the seven
that change how the game plays, and the other eleven are tracer colours, HUD
text colour, voice-chat recording, the ELO constant and reticle precision. All
three bad keys are gone, Rainbow Six 3's third group is now empty so it offers
no second card, and the test compares the **two discs against each other**
rather than either against a recorded number.

---

# Ghost Recon 2 (PS2, SLUS-21105) -- what is here and what is not

Ghost Recon 2 is not a Ghost Recon disc in the engine sense. It is laid out
exactly like Rainbow Six 3:

| | Rainbow Six 3 | Ghost Recon 2 | Ghost Recon / Jungle Storm |
|---|---|---|---|
| overlays | `SP.SOZ`, `MP.SOZ` | `SP.SOZ`, `MP.SOZ` | none -- one plain ELF |
| archives | `VOKES0/1/2.IMG` | `GR2.IMG`, `VOKES0.IMG`, `VOKES2.IMG` | `GR.IMG`, `MENU.IMG` |
| packages | `.LIN` (chunked zlib) | `.LIN` (chunked zlib) | `rselzo` (LZO1X) |
| tuning | `R6GAMESETTINGS.INI` | `R6GAMESETTINGS.INI` | `.MIS` / `.ATR` XML |

Boot ELF `SLUS_211.05`, 148,528 bytes, two program headers; the loaded one maps
file `+0x80` to `0x01400000` for `0x24200` bytes. PCSX2 CRC `82E1D0EA`
(volume `GHOSTRECON2`, `VER = 1.02`).

## The data surface, measured

`R6GAMESETTINGS.INI` ships **three** copies -- one in `GR2.IMG` (11,646 bytes)
and one in each of `VOKES0.IMG` and `VOKES2.IMG` (18,273 bytes). Every key the
tool writes ships at the same value Rainbow Six 3 ships it at:

```
m_fMinDistToThrowGrenade            = 500
m_fGrenadeReactionDelayRecruit      = 1.0      Veteran = 0.5
m_fReactionTimeForFiringRecruit     = 1.0      Veteran = 0.5
m_fTerroristSkillMultiplierRecruit  = 0.20     Veteran = 0.70   Elite = 1.25
m_fDistForPerfectAccuracyTerro      = 500.0
m_fSightRadius                      = 5000.0
m_iXSensitivityMaxSteps             = 10       Y = 10
m_fXSensitivityMultiplier           = 0.70     Y = 0.60
m_fXSensitivityStepIncrement        = 0.15     Y = 0.15
```

`COMMON.LIN` is 1,730,200 bytes packed and 5,115,413 plain, identical in
`VOKES0.IMG` and `VOKES2.IMG`. It carries 73 `NbOfGrenade` tables, of which
**eight** are the two-entry weighted form the grenade dial edits, shipping
`20, 15, 25, 20, 30, 20, 20, 20`. `GR2.IMG`'s `COMMONOFF.LIN` has none, so it is
left alone.

## Why there are no code options

Rainbow Six 3's wave, render and split-screen patches are virtual addresses
inside **its** `SP.SOZ`. Ghost Recon 2's overlay is a different build from a
year later; the same offsets point at different instructions. Nothing here has
been mapped, so nothing is offered. `R6DZoneWave` appears once in
`COMMON.LIN` -- the class exists -- but no shipped mission places one, so even
a mapped wave patch would have nothing to switch on.

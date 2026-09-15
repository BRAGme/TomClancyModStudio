# Rainbow Six 3 PS2 — per-map wave zones

Where this stands: the authored per-zone values **are** reachable and editable.
What is not finished is attributing a property block to a specific actor class,
which is what a per-map UI would need before it could label anything.

## What the disc actually places

Counted by decompressing every `OFF` level package and tallying the placement
names, not recalled:

* **24 of the 27 campaign mission parts** place deployment zones, 568
  `R6DZonePoint`s between them.
* The three with none are **Alpine Village A, Import/Export A, Penthouse A**.
* **Multiplayer places zero** wave actors across all twelve maps. Training
  places a few zone *points* but no wave actor to use them, which is the likely
  source of the older claim that it had zones.

This corrects a note that had named five levels as the only ones with zones.

## The package format

A `.LIN` level is ~107 cooked Unreal packages end to end, file version 123,
licensee 22. `tcps2/upackage.py` reads them.

**The recorded table offsets are relaid by the PS2 cooker and cannot be used.**
On Shipyard A both `exportOffset` and `importOffset` land in float data, whether
read package-relative or absolute. The *name* offset is still good.

That is enough, because Unreal serialises a property as

    compactIndex(nameIndex)  infoByte  [size]  value

so a property can be found by searching for its own name index followed by an
info byte — `0x22` for a four-byte int — with no export table involved.

## The authored values

Each spawner carries `m_iMinTerrorist` and `m_iMaxTerrorist` as int properties.
Shipyard A, validated by walking each property list to its terminator:

| site | max | the properties that follow it |
|---|---|---|
| ×2 | 5, 5 | `m_TerroristAITag`, several `m_Template`, **`m_eTerroristHunt`**, `m_eCoopTerroristHunt` |
| ×6 | 4,4,3,3,4,2 | `m_TerroristAITag`, one `m_Template`, **`m_eStoryMode`**, `m_eCoopStoryMode` |

Two hunt-gated spawners and six story-mode ones — and Shipyard A's name table
holds exactly two `R6DZoneWave` instances and six `R6DZoneRandomPoints`, so on
this level the split is exact.

## What editing is allowed

Values already authored can be rewritten in place: an int32 stays an int32, so
`lin.substitute`'s equal-length rule is satisfied.

**A value that is not authored cannot be added.** Unreal omits any property
equal to its class default, so a zone shipping the default count has no property
to rewrite, and inserting one would move every byte after it. This is why the
counts differ per level — on Shipyard A eight actors author a max but only five
author a min.

## What is still open

The export table names the classes, but it does **not** say where an object's
property bytes are. Its recorded serial offsets describe the layout *before*
cooking -- data sitting between the name table and the imports -- and that is
not where the data ended up:

* The offsets are perfectly contiguous, 80490..1070234 across 3144 boundaries
  with no gaps, and 1070234 is exactly the summary's `importOffset`. So they
  are internally consistent, just describing a layout that no longer exists.
* Summing every package's export sizes gives 18.8 MB inside an 11.8 MB file,
  and the packages sit back to back with no gaps, so the data cannot simply
  follow the tables.
* Searching 159000..200000 for a single base that makes blocks end exactly on
  their recorded sizes found nothing -- 0 of 60 probes at every offset.

So `export -> property bytes` is unsolved, and with it the last of the actor
attribution.

### Length-matching, and why it also failed

Tried, since the export table gives each wave actor's serial size:

* **Matching a block's length to a wave export's size.** For every validated
  `m_iMaxTerrorist` site, walk forward to the terminator for the end, then try
  every start in the preceding 800 bytes that walks to exactly that end, and
  keep one whose length equals a wave size. Shipyard A wants 221 or 226:
  **0 matches**.
* **Chaining blocks forward.** If blocks were contiguous, the end of one would
  begin the next. Walking from the terminator at +690010 parses **no** further
  block, so they are not contiguous there either.

So a serial size is not simply the length of a property list, and the data
region is not a plain run of them. Something frames or pads the objects, and
that framing is the real unknown.

### Per-map does not actually need any of this

Worth stating plainly, because it changes what is blocked. Per-map means per
`.LIN`, and each level is already its own file: editing the counts inside
`SHIPYARD_AOFF.LIN` touches Shipyard A and nothing else. Attribution is only
needed to name an individual zone, or to tell a wave zone from a story spawner
within one level.

What that would tune is every authored spawner count in a mission, wave and
story alike -- which is arguably the more useful knob, but it should be
labelled as what it is.

### The 148, explained

They were not misreads. **Every one of them is exactly `0`**, and zero occurs
nowhere else in the distribution:

| value | 0 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 10 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|
| sites | 148 | 36 | 83 | 89 | 57 | 32 | 5 | 4 | 2 | 2 |

The bound was the bug, not the locator. A count of zero sits beside
`m_bDontHearPlayer`, `m_bNotSurrender` and `m_aActionSpot` -- an individual
terrorist rather than a group spawner -- so it is authored, meaningful, and no
business of a numeric filter.

The real misreads are all rejected by structure alone. Of 498 candidates across
the campaign the `m_TerroristAITag` test keeps 458 and drops 40, and **all
eight implausible values are among the 40**. The 458 it keeps run 0..15. So no
plausibility bound is needed at all, and adding one would have thrown away 148
real values to catch eight that were already gone.

### Editing works end to end

Shipyard A, in memory, nothing written to a disc:

* 13 authored counts found, values 2..5
* scaled x2 -> all 13 changed, length identical
* handed back to `lin.substitute` -> 2 chunks re-deflated, container
  4,894,341 bytes before and after, and it decompresses to exactly the edited
  bytes

So per-map spawner tuning is done as a mechanism. What it tunes is every
authored count in one mission, wave zones and story spawners alike, which is a
per-map knob of real use even without per-zone attribution.

## The equipment wheel in split screen (SOLVED, pending play-test)

Rainbow Six 3 opens an equipment wheel when you hold L1. In split screen it
does not: L1 cycles one item per press instead, which costs time in a
firefight.

### CORRECTION: `m_bUseWheel` is a DOOR, not the equipment wheel

Everything previously written here rested on `m_bUseWheel` being the switch.
**It is not.** Resolved from a live savestate, `m_bUseWheel` is declared on
`R6IORotatingDoor`, and its siblings on that class are:

    m_bIsDoorClosed      m_bIsDoorLocked     m_DoorActorA / m_DoorActorB
    m_LockPickSound      m_bIsOpeningClockWise
    m_OpeningWheelSound  m_ClosingWheelSound

It is the handwheel on a valve door, and the two "wheel sounds" are the sound
of turning it. That is why it is in no INI, why no `Function` export is named
for it, and why the three `EX_InstanceVariable + compact(388)` candidates
decoded as garbage -- they were never anything else. A name collision sent the
whole first investigation down the wrong hole.

### The real class is `R6InteractionRoseDesVents`

*Rose des vents* is French for compass rose; the studio was Ubisoft Montreal.
Its members, read out of memory:

    DrawRoseDesVents     DisplayMenu         HideInteraction
    ActionKeyPressed     ActionKeyReleased   m_bActionKeyDown
    ItemClicked          ItemRightClicked    NoItemSelected
    SetMenuChoice        MenuItemEnabled     m_iCurrentMnuChoice
    m_bShowMenu          m_Player            m_RoseOpenSnd  m_RoseSelectSnd
    states: MenuDisplayed, s_ItemSelected

The four directions are native input commands, registered in the name->id
table at `0x00201e50`:

    RoseDesVents_Up 208   RoseDesVents_Down 209
    RoseDesVents_Left 210 RoseDesVents_Right 211

The class-name string `UR6InteractionRoseDesVents` sits at `0x005e51f0` but no
code builds that address, so the interaction is created from script, not
natively.

### Why the savestates could not finish it

`R6InteractionRoseDesVents` has **zero instances in both** a split-screen and a
single-player savestate: it is created while L1 is held and destroyed after.
Both states were captured with the wheel shut, so neither shows it. The control
that proves the counting works is `R6InteractionCircumstantialAction`, which is
one per player -- 2 instances in the split state, 1 in the single.

### The anchors that ARE now nailed down

* **`$gp = 0x0065b6f0`**, solved against three constraints and confirmed:
  `$gp - 0x7ff0 = 0x653700`, exactly where the overlay image ends and small
  data begins, which is the standard MIPS `_gp` placement.
* **split-screen mode** is the word at `0x006546f4` (`-0x6ffc($gp)`): 0 in all
  four single-player states, 1 in the split-screen one.
* **first-person weapon** is `0x006537bc` (`-0x7f34($gp)`): 1 in every
  single-player state, 0 in split -- the suppression the toolkit already
  undoes, now confirmed from RAM rather than inferred.
* The wheel is **not** a `$gp` global. Every boolean in the whole `$gp`
  window was compared across the five states; six flip the right way, and all
  six are accounted for -- one is the first-person weapon, three at
  `0x001ad75c` are lazy-init guards (`if (!flag) { value = N; flag = 1; }`
  with N = 110/140/230), and two more at `0x003e832c`/`0x003e85d4` have the
  same shape. None is a feature switch.
* There is **no sibling suppression** in the split-screen routine at
  `0x00302d90`. It contains exactly one store of zero to a `$gp` global, the
  one already patched. That hypothesis is dead.

### Name resolution is solved, and it did not need the disassembler

A PS2 `UObject` in memory is laid out, relative to the object's start:

    +0x00  vtable        +0x18  Outer (the declaring class, for a property)
    +0x1c  ObjectFlags   +0x24  Class
    +0x28  Name -- a direct `char*`, NOT an FName index

`UProperty` adds a byte `Offset` and, for bools, a `BitMask` (both powers of
two were observed: `m_bUseWheel` bit 0x8, `m_bFiringRunning` bit 0x100).

So any name, its kind, and the class that declares it can be read straight out
of a savestate. That is the missing half of the UnrealScript disassembler and
of the weapon-pickup work, and it costs one savestate rather than a solved
export-data mapping.

### SOLVED: it is `R6InteractionInventoryMnu`, not the rose

Three savestates the player captured -- single player with the wheel OPEN,
split screen switching, and split screen with L1 HELD -- settled it.

`R6InteractionRoseDesVents` has **zero instances even with the wheel on
screen**, so it is not the class that draws it. Sweeping for classes that DO
have live instances at that moment found `R6InteractionInventoryMnu`:

===========================  ==========  ==============
state                        instances   m_bCycleWeapon
===========================  ==========  ==============
single player, wheel OPEN    1           **0**
split screen, switching      2           0
split screen, L1 HELD        2           **1** (player 1)
===========================  ==========  ==============

The object exists for both players in split screen. Holding L1 sets
`m_bCycleWeapon` and starts `m_fCycleTimer` at 0.3s, taking the cycle path.
The class declares exactly two properties of its own: `m_bCycleWeapon`
(offset 0xa8, bit 0x1) and `m_fCycleTimer` (offset 0xac).

`ActionKeyPressed` reads `m_Player.Level.Game.m_bIsSplitScreen` and branches on
it. Its bytecode was found on the disc -- via the string constants `eAction`
and `fDelta` that its neighbour `KeyEvent` embeds, which survive into the file
unchanged -- at plain offset `0x15ec08`, exactly once in each of `COMMON.LIN`,
`COMMONOFF.LIN` and `COMMON_SS.LIN`::

    07 3d 00                   EX_JumpIfNot +0x3d
    84 19 01 0d 06 00 04       m_Player
    2d 01 c9 02 18 25 00 f2    bOnlySpectator
    19 19 19 01 0d 05 00 04    m_Player
    01 8f 05 00 04             .Level
    01 a6 06 00 04             .Game
    2d 01 ed 01                .m_bIsSplitScreen
    27 16 16 04 0b

`EX_JumpIfNot` (0x07) -> `EX_Jump` (0x06) takes that branch unconditionally.
Shipped as `tcps2/rsewheel.py`. It is **a no-op in single player** -- the
condition is already false there, so the jump already happens -- which bounds
the risk: only split screen can behave differently. Not yet play-tested.

### The chunk that no edit could touch, and the fix

The one-byte wheel edit was refused at first, and for a reason that had nothing
to do with the edit: `COMMON.LIN`'s chunk at plain `0x15c000` occupies 5640
compressed bytes on the disc, and `zlib -9` cannot get its **untouched**
contents below 5658. The game's own packer beat zlib by 18 bytes, so that chunk
could never be edited at all, whatever the change.

**zopfli** packs the same bytes into 5488 -- 152 bytes of room -- as ordinary
deflate any inflater reads. `lin._deflate_within` now falls back to it when
zlib cannot fit, verifying the result by inflating it before trusting it, and
degrading cleanly when zopfli is not installed. It also bought back loadout
changes that were being given up: Ghost Recon 2's sniper mode went from 95
applied changes to 110, and Rainbow Six 3's "anything goes" from 224 to 238.

### A side finding worth keeping

`R6MissionDescription` declares `m_SplitPrimaryGadget1P`,
`m_SplitPrimaryGadget2P`, `m_SplitSecondaryGadget1P` and
`m_SplitSecondaryGadget2P` -- split-screen-specific gadget assignments, which
is also the first reachable thread on team-mate loadouts.

## Weapon pickup: what Ghost Recon 2 has that Rainbow Six 3 does not

This supersedes an earlier conclusion in this project that the pickup could
not be ported because Rainbow Six 3 lacked the input action. **That was
wrong**, and the mistake is worth recording: the check enumerated ONE package's
name table and stopped, when `COMMON.LIN` holds 132. A raw byte search over
the whole decompressed package is the reliable way to ask "is this name on the
disc", and it says:

    BTN_QuickWeaponSwitch   RS3 COMMON.LIN / COMMONOFF.LIN / COMMON_SS.LIN: 1 each
                            (all three VOKES archives, nine files, every one)

So Rainbow Six 3 already has the button.

`S_Pickup`, cited earlier as shared pickup vocabulary, is also a red herring:
it resolves to a **Texture** export in both games -- the stock UnrealEd sprite
(`S_Pickup.pcx`). Its presence means nothing.

### The actual difference

`R6IOGroundWeapon` -- a script class, present in Ghost Recon 2 and absent from
Rainbow Six 3:

    R6IOGroundWeapon   GR2 GR2.IMG/COMMONOFF.LIN (single player)  2
                       GR2 VOKES0+2/COMMON.LIN   (multiplayer)    1
                       RS3 any COMMON package                     0

Around it, in Ghost Recon 2's single-player package only:

* `AlterWeapon` x12, plus `AlterWeaponClass`, `AlterWeaponNum`,
  `NewAlterWeapon`, `m_nAlterWeaponNum`, `m_pOldWeapon` -- the swap itself
* `m_iNbBulletsInWeapon2`, `m_iCurrentNbOfClips2`, `m_iNbOfClips2`,
  `m_iTotalRemainingBulletNum2` -- a second weapon slot's ammunition state,
  where Rainbow Six 3 has only the unsuffixed slot-1 versions
* `R6GetCircumstantialActionTexID`, `R6GetCircumstantialActionID`,
  `CanAcceptActionKey` -- the on-screen prompt

Ghost Recon 2's MULTIPLAYER half implements pickup a second, different way,
with the stock Unreal `Inventory`/`Pickup` pattern (`R6PickUp`, `State Pickup`,
`ReadyToPickup`, `AnnouncePickup`). None of that is in Rainbow Six 3 either.

### It is script, not native -- measured

The native overlays carry an `IMPLEMENT_CLASS` string table, and it settles it:

    RS3 SP.SOZ:  AR6IOObject, AR6InteractiveObject, AR6IORotatingDoor
    GR2 SP.SOZ:  AR6IOObject, AR6InteractiveObject
    GR2 MP.SOZ:  AR6IOObject, AR6InteractiveObject

`AR6IOGroundWeapon` is in none of them, while `AR6IORotatingDoor` proves
native IO subclasses DO appear in that table when they exist. So
`R6IOGroundWeapon` is an UnrealScript subclass of a native base that Rainbow
Six 3 already ships.

### What Rainbow Six 3 already has

* the input action -- `BTN_QuickWeaponSwitch`
* the native base -- `AR6IOObject` / `AR6InteractiveObject`
* the prompt system -- 25 `Circumstantial*` names against Ghost Recon 2's 25,
  differing only by Ghost Recon 2's two `R6GetCircumstantialAction*ID`
  accessors; 9 of the 10 `ActionKey` names, missing only `CanAcceptActionKey`
* a richer action enum than Ghost Recon 2's -- 45 `CA_*` members to its 19

### The real blocker, and it is not the one previously given

Everything missing is script, and script lives in a cooked `.LIN`. The
container is a chain of chunks with fixed compressed slots, and
`lin.substitute` refuses any edit that changes the decompressed length:

    "a LIN edit must preserve length exactly"
    "chunk re-deflates larger than its N-byte slot; the container length
     cannot move"

Adding a class export, four ammunition properties and a texture accessor grows
the package. So the obstacle is not that the feature is native, and not that
the button is missing -- it is that **this tool can only make same-length
edits to these packages**, and adding exports is not one.

Two routes, neither attempted:

1. Find equal-length room -- repurpose an existing unused script class rather
   than adding one. Rainbow Six 3 has script-only IO subclasses already
   (`R6IOAlarmSystem`, `R6IOBomb`, `R6IODevice`); whether any is dead weight
   on this disc is unknown and checkable.
2. Rebuild the container instead of substituting into it, which means writing
   a `.LIN` writer that can relocate chunks, and re-cooking an export table
   whose offsets this project already knows the PS2 cooker relaid.

### Route 1 tested: is there dead script to repurpose?

**The three IO classes asked about are not all dead, and the one that is, is
tiny.** Scanning all 80 level packages for each name:

    R6IORotatingDoor   named by 62 of 80 levels   (native anyway)
    R6IOBomb           named by 14 of 80          895 bytes, alive
    R6IODevice         named by  6 of 80          386 bytes, alive
    R6IOAlarmSystem    named by  0 of 80          119 bytes, dead

119 bytes against the ~1,103 Ghost Recon 2's `R6IOGroundWeapon` occupies. So
that particular idea fails on size.

**But widening the question pays off.** `COMMON.LIN` declares 805 classes; 554
are named by no level at all, and 453 of those are script rather than native.
"No level names it" is a weak test on its own -- a class can still be reached
by code -- so the survivors were checked against the native overlay and the
menu package as well:

    class                              SP.SOZ  COMMON  MENU   bytes
    R6XboxReticule                          0       1     0    1298
    R6RainbowVoices                         0       1     0    1019
    R6ConsoleXbox                           0       1     0     664
    R6XboxGadgetReticule                    0       1     0     617
    R6XboxGrenadeReticule                   0       1     0     563
    R6IOAlarmSystem                         0       1     0     119

One occurrence in `COMMON.LIN` is the declaration itself. Zero in the overlay
and zero in `MENU.LIN` means nothing on the disc can reach them. The four
`Xbox*` ones are leftovers from the Xbox build sitting unused on a PS2 disc,
which is exactly the shape of dead weight worth having.

That is **4,280 bytes** of genuinely unreachable script, the largest single
item 1,298 -- more than the 1,103 the class alone would need.

Ones that looked promising and are NOT free, for the record: `R6HudTextures`
(4 hits in the overlay), `R6TrainingTextures` (4), `R6PackageWeaponsList` (2),
`R6SharpShooterGameForSplitScreen` (1), `R6InteractionCircumstantialAction`
(3 in COMMON, referenced by other script).

### So route 1 is not blocked on space -- but space was never the whole problem

Two things stand between this and a working pickup, and both are worth stating
before anyone spends a weekend on it:

1. **The class is not all that is missing.** Ghost Recon 2 also carries four
   slot-2 ammunition properties, a dozen `AlterWeapon*` names and a texture
   accessor, each its own export. 4,280 bytes may or may not cover the lot;
   nobody has added it up.

2. **A dead class is dead because nothing spawns it** -- which is the catch.
   Making the pickup work needs a call site in the pawn-death path that
   creates the object, and that is more script surgery in the same
   length-locked container. Repurposing the bytes is the easy half.

There is also a smaller, concrete constraint: name table entries are
length-prefixed and the package length cannot move, so a repurposed class
keeps its original name. `R6XboxReticule` is 14 characters and
`R6IOGroundWeapon` is 16; the class would have to go on being called
`R6XboxReticule` and simply behave differently.

### The export budget, added up

Every export in Ghost Recon 2's pickup cluster, measured from its own package
(`GR2.IMG/COMMONOFF.LIN`, the single-player half) and checked against Rainbow
Six 3's `COMMON.LIN` to see what already exists. Script:
`research/code/pickup_budget.py`.

**39 exports match the cluster; 7 already exist in Rainbow Six 3.** The seven
are worth naming, because they are free: `S_Pickup` (the editor texture),
`R6GetCircumstantialActionVoiceID`, `R6GetCircumstantialActionString`,
`R6GetCircumstantialActionProgress`, `m_SplitPrimaryWeapon2P`,
`m_SplitSecondaryWeapon2P`, `m_bChangeWeaponBackward`.

The big items:

    R6IOFixedGun                       Class            1154 bytes
    R6IOGroundWeapon                   Class            1103
    GetPrimaryWeapon                   Function          540
    R6GetCircumstantialActionID        Function          217
    IsInteractiveObject                Function          108
    CanAcceptActionKey                 Function          107
    AdjustWeaponType                   Function          101
    NeedSwitchToPrimaryWeapon          Function           91
    R6GetCircumstantialActionTexID     Function           36
    ...then 30 properties at 10-13 bytes each

`R6IOFixedGun` is a sibling feature -- mounted guns -- that shares the `R6IO`
prefix, and `m_TrainingWeapon2` matched on "weapon2" but is a training
variable. Neither belongs to picking a weapon off the ground, so both figures
are given:

                          objects  rows  names   total   vs 4,280 available
    everything matched       3719   524    761    5004   SHORT by 724
    minimal pickup set       2540   474    702    3716   fits by 564

### And that is where it stops being about bytes

The object data half fits: 2,540 bytes into 4,280 bytes of unreachable class
data, in six separate holes, which is fine because objects are addressed by
offset and can live anywhere there is room.

**The tables are the problem.** The name table and the export table are
contiguous runs; growing either shifts every byte after it, and the container
cannot change length. The only way to add a row without growing the table is
to overwrite one that is already there -- and the six unreachable classes give
exactly six rows and six names:

    export rows needed    29   reusable  6   short by 23
    name entries needed   29   reusable  6   short by 23

So route 1 does not fail on data space. It fails on **table slots**, by 23 of
each. Reusing more would mean finding 23 further exports that nothing on the
disc reaches -- plausible, since 453 script classes are unnamed by any level,
but each one has to survive the same overlay-and-menu check the six did, and
a name can only be overwritten by a name of the same length.

That is on top of the problem already recorded: **a dead class is dead because
nothing spawns it**, so even a perfectly placed `R6IOGroundWeapon` needs a
call site in the pawn-death path that does not exist yet.

Verdict: not a dead end, but not a weekend either. The next concrete step, if
anyone wants it, is to run the same overlay-and-menu reachability test across
all 453 unnamed script classes and see how many table slots are genuinely
free. That is one script and it answers the whole question.

### The reachability test, run across all 453 -- and a correction

**Correction first.** The earlier figure of "4,280 bytes from six unreachable
classes" was too high. `R6ConsoleXbox` (664 bytes) is named in `DEFAULT.INI`,
`DEFAULTXBOX.INI` and `PSX2GAME.INI`, which the six-class check never looked
at. The real figure for those six is 3,616.

That is exactly the failure mode this pass was built to catch, so the test was
tightened three times, each time on a name that looked wrong:

1. **Level name tables.** 453 classes are named by no level and are not
   implemented natively. Checking each against the overlay, `MENU.LIN` and
   `COMMON.LIN` itself leaves **238**.
2. **Level raw bytes.** A level can name a class in a string without the name
   ever entering its name table. Searching all 80 level packages raw removes
   **36 more** -- the `R61stHands*` first-person weapon classes among them.
   Leaves 202.
3. **Everything that is not a `.LIN`.** `R6MObjRescueHostage` being called
   unreachable on a disc with hostage missions was the tell. Searching every
   INI, DAT and loose ISO file removes **9 more**: `R6ConsoleXbox`,
   `R6MolotovGadget` and `R6PhosphorusGrenade` (named in `MAPS/*.INI`), the
   four `R6MapList*` classes (`SERVER.INI`, `USER.INI`),
   `R6RainbowChavezWinter` and `R6THeadAttachment`.

**Final: 193 classes, 30,881 bytes, that nothing on the disc can reach.**
Script: `research/code/free_classes.py`.

### Route 1 has enough of everything

    needed                    available
    29 export rows            193
    3,057 object bytes        30,881
    29 name entries           28 of 29 matchable at their own length

The one that does not match is `R6GetCircumstantialActionTexID` at 30
characters, and there is no free 30-character name. That is not a blocker:
the name is ours to choose -- nothing outside the code we would be writing
refers to it -- so it can be called something 29 or 31 characters long and
take one of those slots instead.

So the resource question is settled. Route 1 is viable on rows, on bytes and
on name lengths.

### What is left is the thing that was never about space

A dead class is dead because nothing spawns it. Every byte above can be found
and the pickup still will not happen until something in the pawn-death path
creates an `R6IOGroundWeapon` where the body fell. That call site does not
exist in Rainbow Six 3, and adding it means editing the bytecode of a function
that does exist -- in place, at the same length.

That is the next question worth answering, and it is a different kind of
question from this one: not "is there room" but "is there a function whose
bytecode has room for a spawn call". Nothing so far has needed an
UnrealScript disassembler; that one does.

## The disassembler: stalled, and where

Attempted, not delivered. The blocker is one step earlier than expected and is
worth recording precisely, because three of the four findings below contradict
what this file previously assumed.

**1. The per-export offsets are NOT garbage.** This file says the cooker
relaid the summary's table offsets, which is true and is why `tables()` walks.
But the *per-export* `offset` fields in `COMMON.LIN` are perfectly
self-consistent: across the 7,364 exports of the script package, **7,363 of
7,363 consecutive pairs satisfy `offset + size == next offset`**, and the sizes
sum to exactly the span, 2,321,838 bytes. That is not something that happens by
accident. The offsets describe a real, contiguous layout.

**2. The package contains no data.** Walking that package's header, name,
import and export tables ends at `0xc895d`, which is exactly where the next
package signature begins. So the script package is header-and-tables only, and
its 2.3 MB of object data lives somewhere else in the file.

**3. The offsets are relative to a base that has not been found.** Reading at
the offsets as written gives content that cannot be what the export table says
it is. `R6IOAlarmSystem`, a Class of 119 bytes, reads as

    03 02 02 02 01 01 01 01 ... 07 07 08 08 08 08

a smooth 0-8 ramp -- an envelope or a curve, not a default-property list.

**4. The obvious bases do not work.** Scoring a stock UE2 `UFunction` layout
(SuperField, Next, ScriptText, Children, Line, TextPos, ScriptSize, script)
across all 2,061 Functions, at every candidate base -- end of file, immediately
before each of the 132 package signatures, and zero -- fits **under 20% at
every one**. Either the base is somewhere not yet guessed, or this cook's
UFunction layout differs from stock, or both. `research/code/exportdata.py`
holds the search so it can be rerun with new candidates.

### What that means for the pickup

It does not change the resource arithmetic -- those numbers came from the
export TABLE, which parses cleanly and is what the budget was measured from.
It does mean the remaining question, "is there a function whose bytecode has
room for a spawn call", cannot be answered until object data can be located.

So the order of work has changed. It is no longer "write a disassembler"; it
is:

1. **Find the export data region.** The strongest lead is that the offsets
   tile exactly, so the region is contiguous and 2,321,838 bytes long. Finding
   one object whose content is recognisable -- a Texture with a known size, a
   Sound, a StrProperty whose string is readable -- pins the base immediately,
   and then every other object follows from the tiling.
2. Only then, fit the `UFunction` header and write the opcode table.

Step 1 is a search with a strong constraint and a self-checking answer: get
the base right and 7,364 objects land correctly at once, which is a much
better position than fitting a bytecode layout blind.

## Where the export data went -- solved, and a correction

**Correction.** The previous entry said "the per-export offsets are NOT
garbage" and framed that as contradicting this file's note about relaid
offsets. That was half right and the framing was wrong. The offsets are
perfectly self-consistent -- and they describe a file that is not this one.

The package header reads out cleanly and settles it:

    +04  version        0x0016007b   = 123 / 22, as this file already recorded
    +0c  nameCount      6500
    +10  nameOffset     0x44
    +14  exportCount    7364
    +18  exportOffset   0x25b5da
    +1c  importCount    1582
    +20  importOffset   0x257e56

`importOffset` is **exactly** where the export data span ends -- the highest
`offset + size` across all 7,364 exports is `0x257e56` to the byte. So the
original package was laid out

    [header][names 0x44 .. 0x210a8][DATA 0x210a8 .. 0x257e56][imports][exports]

and every number in the table agrees with every other. It is a complete,
correct description of the **uncooked** package.

**What the cook did** was lift the data region out and close the gap. That is
why walking the tables in the `.LIN` ends exactly on the next package
signature: names, imports and exports are now adjacent, with the 2,321,838
bytes that used to sit between them gone. And it is why no gap in the file is
big enough to hold that region contiguously -- the data was not moved as a
block, it was redistributed.

It is still in the file. The gaps between packages hold 4,155,953 bytes, and
sampling them finds exactly what object data looks like: property lists walk
cleanly at 206 of 2,062 probe positions, and the readable strings are
`BeginState`, `EndState`, `BeginHere`, `SpawnAI`, `SpawnAIandInitGoInGame`,
`PlayDeathAnimEnd`, `DisableVoiceChat`.

**So the index is what is missing, not the data.** Nothing in the package
header or tables points at where an object ended up. That is the single reason
this project has always had to find things by byte search rather than by
seeking -- `actor_properties`, `find_int_props` and the zone-count locator are
all consequences of this, and now there is a reason on record for why they had
to be written that way.

### The next step is concrete

`BeginState`, `EndState` and `BeginHere` are **label table entries**, and a
label table sits at the end of a state's bytecode with a known shape: pairs of
(name index, u32 offset) terminated by the `None` name. Those are findable by
content without knowing a single opcode, and each one found is a pointer to
the *end* of a real bytecode block.

That inverts the chicken-and-egg problem. Instead of needing the opcode table
to find bytecode, find the label tables first, then walk backwards from each
one to recover the block it terminates -- and derive the opcode table from
blocks whose boundaries are already known.

`research/code/lingaps.py` maps the gaps and verifies all 132 magic hits are
real packages, which is the groundwork for that search.

## The disassembler: built and measured

`research/code/uscript.py`. It works, and the number that says so is a control
rather than a look at the output.

**Finding the code.** Two idioms in the stream are unmistakable, and the first
is self-delimiting, which makes it a synchronisation point:

    1F "BeginHere::BeginState" 00      EX_StringConst, NUL-terminated ASCII
    16 04 0B                           EndFunctionParms, Return, Nothing

`anchors()` finds every string constant; the byte after each terminator is
guaranteed to be the start of a token, whatever came before it. That is what
sidesteps the missing index entirely -- the code does not have to be located
through a table that no longer points anywhere.

**Checking the opcode table.** Decoding forward from an anchor either survives
or desynchronises. Over `COMMON.LIN`:

    region                       anchors  6 tokens  12 tokens  24 tokens
    the four inter-package gaps     3106     75.1%      49.3%      25.2%
    a package's NAME TABLE            41      2.4%       2.4%         --

Thirty-fold separation against a control drawn from the same file. The decay
with depth is expected: an anchor lands mid-block, so a deeper decode is
likelier to walk off the end of it.

**A decoded sample**, `COMMON.LIN` at 0x001015ec:

    LocalVariable(#7)
    IntConst(2449550592)
    VirtualFunction(#1, (StringConst("::BeginState")))
    LetBool(BoolVariable(InstanceVariable(#1066)), True)
    Return(Nothing)

`Log("::BeginState"); bSomething = true; return;` -- a state entry announcing
itself and setting a flag. That is real code, read out of a file whose index
was thrown away.

### What it cannot do yet

**Resolve names.** `#1066` is a compact index into the name table of whichever
package owns that code, and the cook destroyed the object-to-data mapping, so
nothing says which package that is. The indices are real and internally
consistent; they are simply unlabelled.

That is a tractable next problem and it is statistical rather than structural:
a block calling `VirtualFunction(#n)` where `#n` resolves to a plausible
function name in exactly one package's name table is strong evidence for that
package, and a few such hits pin the whole block.

Which is also what the equipment wheel needs. `m_bUseWheel` is name #4557 in
the script package; once blocks can be attributed to packages, searching for
`InstanceVariable(#4557)` finds every read and write of it, and the
split-screen gate with them.

## Enemy loadouts are a weighted roll, in plain text

Rainbow Six 3 and Ghost Recon 2 keep every enemy archetype as a CRLF text
block in `COMMON.LIN`, and it already describes a roll rather than a fixed kit:
`NbOfWeapon=3` followed by three `NNN, Class` lines whose weights total 100.

Measured, from the backup store:

| disc | templates | table sizes | snipers present |
|---|---|---|---|
| Rainbow Six 3 | 118 | 1:106 2:4 3:5 4:3 | PSG1 x2, M82A1 x2 |
| Ghost Recon 2 | 73 | 1:67 2:2 3:3 4:1 | PSG1 x2, M82A1 x2 |
| Advanced Warfighter | 0 | -- | none, the table does not exist |

That 12 of Rainbow Six 3's tables ship with more than one entry is the proof
the roll really runs; it is not a dormant field. RS3 carries the identical 118
in `COMMON.LIN`, `COMMONOFF.LIN` and `COMMON_SS.LIN`.

**Correction to an earlier survey.** A subagent reported that "no `Sniper*`
class appears in GR2's terrorist tables at all". That is wrong. GR2 has four
single-entry sniper templates, at plain `0x223f04`, `0x224fa9`, `0x225b0f` and
`0x226051`, each `100, R63rdWeapons.SniperPSG1` or `...SniperM82A1`.

### Two constraints, not one

Equal decompressed length is necessary but **not sufficient**. Every chunk must
also still deflate back into the byte count its original occupied, and variety
is precisely the removal of the redundancy that made the stock text pack well.
A full-strength rewrite is the same length and still fails.

The slack is wildly uneven, which is what makes a per-chunk answer right. On
Ghost Recon 2 the templates straddle three chunks:

| chunk | plain | compressed | ratio |
|---|---|---|---|
| 135 | 0x21c000 +16384 | 5289 | 0.323 -- mostly other data, no room |
| 136 | 0x220000 +16384 | 1006 | 0.061 -- almost all template text |
| 137 | 0x224000 +16384 | 2351 | 0.143 |

Turning one dial down over the whole file to satisfy chunk 135 throws away
everything chunks 136 and 137 would have taken. `rseloadout.fit_to_lin` instead
gives up only the templates overlapping a failing chunk. Measured gain on RS3
`varied`: 22 changes under a global back-off, **64** per chunk. GR2 `snipers`
went from failing outright to 95 changes.

### What is reachable

A class name may only become one of the same byte length. Grouped that way the
roster's 43 classes put a sniper in three groups:

    len 23  AssaultAUG  Pistol92FS  PistolMk23  -> SniperPSG1
    len 24  AssaultAK47 AssaultG36K AssaultG3A3 -> SniperM82A1
    len 27  AssaultFAMASG2                      -> SniperAWCovert

`AssaultAK47` alone is 21 of RS3's weapon lines. Applied: RS3 4 -> 12 sniper
lines, GR2 4 -> 10.

### The Rainbow side is still shut

All 118 blocks are `Type=Terrorist`; there is no team-mate equivalent. The
player and team-mate kits are `m_PlayerEquipment`, `m_LoiselleEquipment`,
`m_PriceEquipment`, `m_WeberEquipment` -- name-table entries at `0x1f00d`
whose *values* live in export data, still unindexed. The multiplayer defaults
ARE reachable, as `EX_StringConst` operands in script at `0x1ca0ce`
(`R6MultiPlayerGameInfo::PostLogin`) and `0x1ce002` (`R6NoRules::Login`), each
a four-slot kit; they are recorded in `rseloadout.MP_DEFAULTS` but not wired to
an option.

## Correction: the COMMON.LIN header directory is NOT the missing index

The head of `COMMON.LIN` does carry a directory -- 784 entries of
`<len><"System\NAME.u">< NUL><u32 offset><u32 size>` from offset ~0xac. It is
**not** the package index. Its offsets run to 0x22dee600 (583 MB), far past the
5 MB file, and its sizes describe the *uncooked* build layout -- the same
layout the stale header `importOffset` points into. Matching its sizes against
the gaps between the 132 package signatures in the file hits 3 of the first 20,
which is coincidence at that sample size. It names files; it does not locate
cooked data. The export-data mapping remains unsolved.

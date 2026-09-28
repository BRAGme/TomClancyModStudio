"""Teammates carry the loadout the player actually picked.

REBUILT 2026-09-27: THE GUARD WAS THE BUG
-----------------------------------------

The first build of this cave made the game **stutter and skip audio through a
mission load**. Proven by bisect, both directions, in play: with this cave's
rows out of the cheat file and nothing else changed, loading is clean; with
them in, it stutters.

**The copy was never the problem -- the guard was.** Two savestates twenty
minutes apart both showed the run counter at 1, so the forty-eight-slot copy
really did happen once per session. But the guard ran on *every* call to the
hooked native and cost 557 instructions in one player and 1,098 in split
screen, because it byte-summed every source loadout string before deciding to
do nothing.

The first build's own report named this as its one unmeasured number -- "how
often script asks for the mission description is not measured, so the per-frame
cost is not known -- it is the one number in this module that is a guess". The
guess was wrong. `execGetMissionDescription` is called far more often through a
mission load than "18 script call sites, none per-frame" suggested.

So that this is never a guess again, the STATE band now carries a **call
counter** at `0x000F67F8` (`STATE + ST_CALLS`) which increments on every entry
before any other work, fast-path returns included. Read it out of a savestate
and the real call frequency is a measurement.

Two things to know when reading it. Nothing ever zeroes it -- no pnach row
touches the STATE band, by design -- so it counts from the emulator's last
**hard** boot, not from the mission and not across a soft reset, which leaves
the band intact. And `ST_COPIES` beside it counts only the calls that did the
forty-eight-slot copy, so `ST_CALLS - ST_COPIES` is exactly how many times the
fast path earned its keep.

The guard now keys on a once-per-level **identity** instead of on the content
of the strings, and costs **23 instructions** (25 issued, delay slots counted)
in both one player and split screen -- 24.2x cheaper than 557, 47.7x cheaper
than 1,098. Every number in this paragraph is printed by the verifier, which
runs the old cave and the new one through the same interpreter under the same
counter.

WHAT THIS IS NOT
----------------

It is not `team_match_player` (`rsekits.match_card`, wired through
`rsekits.cards` in `games/r6_3.py`).
That card rewrites the **map INI on the disc**, so the AI copies the kit the
mission *hands* you before you touch anything. This one runs in RAM and copies
what you **chose in the gear room this run**. They are genuinely different
values: in the `headcam` EE dump -- a split-screen session, two
`R6PlayerController`s -- `m_PrimaryWeapon` still held Alpines' INI kit,
`SubMP5A4 | GrenadeLauncherRP | Frag | Smoke`, while the player's own
`m_SplitPrimaryWeapon1P` block held what he was actually carrying,
`SubMP5SD5 | GrenadeLauncherHE | Frag | Frag`.

The cave writes after the INI has already been parsed into the object, so with
both switched on **this one wins** and the old card becomes redundant.

WHERE THE PLAYER'S CHOICE LIVES
-------------------------------

`R6MissionDescription`, a boot singleton reached from `gp-0x66DC`
(`0x00655014`). Every offset below comes from the live UProperty objects in the
EE dumps (`Offset` at property+0x44), not from counting::

    +0x320  m_PrimaryWeapon          StrProperty   the one-player kit, and
    +0x32C  m_SecondaryWeapon                      the seed for both split kits
    +0x338  m_PrimaryGadget
    +0x344  m_SecondaryGadget
    +0x410  m_SplitPrimaryWeapon1P   ... +0x434    player one, split screen
    +0x440  m_SplitPrimaryWeapon2P   ... +0x464    player two, split screen
    +0x0B8  m_PriceEquipment         48-byte struct = four FStrings
    ...     twelve of them, contiguous, stride 0x30, up to +0x2C8

Which pair to read is `GameEngine.mSplitScreenMode` at `GEngine+0x4E4`
(`gp-0x6F44`), named from the live property table. **Measured**: it reads 1 in
every dump that has two `R6PlayerController`s with `m_ViewportIndex` 0 and 1,
and 0 in the one dump that has a single controller. The split fields are seeded
from `m_PrimaryWeapon` by the engine itself at `0x0058B0FC`, which is why they
are empty until a split session has run.

THE TWELVE BLOCKS, AND WHY ALL TWELVE
-------------------------------------

Price / Loiselle / Weber, each in four authored variants -- plain, silenced,
terrorist hunt, silenced terrorist hunt. `CreateTeamMember` picks among them at
runtime off `m_bMissionModeUseSilencedEquipment` and the hunt flags, so a cave
that wrote only the plain three would silently do nothing on a silenced
mission. All twelve are written; it costs one loop counter.

THE HOT PAGE, AND WHY THE HOOK WORD LEFT THE CHEAT FILE
-------------------------------------------------------

REBUILT AGAIN 2026-09-27 (second pass). The guard rebuild above fixed the
guard's *cost* and the game still stalled through a mission load, with audio
breaking up. Bisected in play, both directions: emitting the 254 cave words
**without** the hook word loads perfectly; adding back that one word stalls it.
So the cave, its size and its address are innocent. The hook's PAGE was the
whole problem.

A `.pnach` row is re-applied by PCSX2 every vsync, and every write into a page
of EE RAM holding recompiled code throws that code away and makes the emulator
build it again -- `engine.write_pnach` says so in as many words. `0x00273200`
sits in page `0x00273000`, which holds ELEVEN UnrealScript native functions and
nothing else::

    0x00272F90  execGetAnimGroup          (80 ins)  "GetAnimGroup: Sequence ..."
    0x002730D0                            (52 ins)
    0x002731A0  execGetMissionDescription (28 ins)  <- the hook
    0x00273210                           (156 ins)  "Engine.Server"
    0x00273480  0x002734F0  0x002735C0  0x002738A0  0x00273900
    0x00273E10  0x00273E80

Nine of the eleven have **zero `jal` sites** -- nothing in the overlay calls
them directly, which is what a script native looks like: it is reached only
through the interpreter's function-pointer dispatch, and
`execGetMissionDescription`'s own address appears in the image as a DATA word
(at `0x005BC538` and `0x0064728C`), never as a jump target. Script natives are
the hottest code there is during a level load, so the page was being discarded
and rebuilt sixty times a second while the recompiler was already saturated.

THE FIX IS NOT TO MOVE THE MIRROR. It is to stop the cheat file writing that
word. The word is now installed **once per level load, by the game itself**,
from a ten-word installer cave -- `ARM` below -- hooked into
`UGameEngine::LoadMap`. The hot page is dirtied once per load instead of sixty
times a second, and the mirror's hook, its guard, its ordering and its
self-healing are untouched: not one of the 254 cave words changed.

WHY THE MIRROR WAS NOT MOVED TO A COLD PAGE INSTEAD
---------------------------------------------------

Two reasons, and the second is the one that decides it.

The candidate that was put forward, `0x00300E68` `sw $v0,0x45C($s4)`, is **not**
where the live `ULevel*` is installed. Its own two instructions are::

    0x00300E64  lw  $v0, 0x460($s4)      ; GEntry, the menu level
    0x00300E68  sw  $v0, 0x45C($s4)      ; GLevel = GEntry

It is in `UGameEngine::Browse` (`0x003005F0`, literals `InvalidUrl`,
`AbortToEntry`, `%s/Game%i.usa`) and it is the **abort-to-entry** path -- the
same shape as `0x002EA348`/`0x002EA350`, which this module's own notes already
identified as the return-to-menu path. A mission level never comes through it.

The real install is `0x002F8C54`, in `UGameEngine::LoadMap` (`0x002F7A20`,
literals `..\\Maps\\`, `.rsm`, `GAMETYPE=`, `Briefing`)::

    0x002F8C1C  sw    $zero, 0x45C($s3)              ; GLevel = NULL
    0x002F8C44  addiu $a1, $a1, "MyLevel"
    0x002F8C4C  jal   0x00304F30                     ; load the level object
    0x002F8C54  sw    $v0, 0x45C($s3)                ; GLevel = the new ULevel

`$s3` is `this`, set once at `0x002F7A54` (`daddu $s3,$a0,$zero`) and never
rewritten before `0x002F8C54`. Page `0x002F8000` is genuinely cold: **every one
of its 1024 instructions belongs to `LoadMap` and to nothing else**, and
`LoadMap` runs once per level load and never during play.

And that is still the wrong place for the mirror's logic, for a reason that has
nothing to do with page temperature. At `0x002F8C54` the level package has only
just been loaded; the mission INI has not yet been parsed over the twelve AI
equipment blocks. A copy made there is **overwritten** by that parse. The
existing design survives that ordering only because it hooks a native that is
called thousands of times through a load and re-copies whenever the destination
canary moves -- the self-healing the guard section above describes. A
once-per-load hook has no second call to heal with, and the window it would
have to land in (after the INI parse, before `CreateTeamMember`) is inside
UnrealScript bytecode, which cannot be pinned from the MIPS.

So the hook stays exactly where it is, and only its *delivery* changes.

THE ALTERNATIVE THAT WAS REJECTED
---------------------------------

Letting an existing cave install the word -- the claymore's in `ULevel::Tick`
(page `0x00223000`), the shrapnel stagger's in `UGameEngine::Tick` (page
`0x002EA000`) -- would cost no new dirtied page at all, because those pages are
already written every vsync in shipped, played configurations. It was rejected
because it couples two unrelated switches: turn claymores off and the mirror
silently stops working, with nothing in the interface to say so. The installer
below is the same idea without the coupling, and it costs one new dirtied page
whose only contents are `LoadMap`.

Baking the hook word into the overlay **on the disc** was also rejected. It
would cost zero runtime writes, which is strictly better -- and it is a footgun:
the cave body can only come from the cheat file, so a disc carrying the hook
plus a session without the cheats would jump into whatever happens to be lying
at `0x000F6000`. `model.py` keeps caves out of the disc for exactly this reason.

WHERE THE INSTALLER HOOKS
-------------------------

`0x002F8CE4`, stock `0x8F8290C4` (`lw $v0,-0x6F3C($gp)`), inside `LoadMap` and
after the level install at `0x002F8C54`::

    0x002F8CE4  lw    $v0, -0x6F3C($gp)    <- replaced by `j ARM`
    0x002F8CE8  lui   $a1, 0x5E            <- delay slot, runs either way
    0x002F8CEC  addiu $a1, $a1, 10936      <- where the cave returns

* **Reached on every level load.** Exactly one branch anywhere in `LoadMap`
  targets the range `0x002F8CE4..0x002F8CF0`, and it is `0x002F8CC8
  bnez $v0,0x002F8CE4` -- it lands ON the hook word, not past it. Nothing skips
  it. (`0x002F8C1C` was the first candidate and was rejected: `0x002F8B64
  beqz $v0,0x002F8C20` jumps straight over it when there is no old level to
  tear down.)
* **`0x002F8C54` itself cannot be hooked.** Its delay slot, `0x002F8C58
  lw $v0,-0x6424($gp)`, destroys the `ULevel*` the displaced store needs, and
  `0x002F8C58`'s own successor is a branch, so neither word can carry a jump.
* **Delay-slot safety.** `0x002F8CE8` is `lui $a1,0x5E`, not a branch; it runs
  before the cave and its result is still live, so the cave preserves `$a1` and
  returns to `0x002F8CEC`, not to `0x002F8CE8`.
* **Live registers.** The cave writes `$v0` (the displaced load, which is the
  point) and `$t0`, `$t1`, `$t2`. Walking forward from the hook, `$t1` is next
  written at `0x002F8D4C` and `$t0` at `0x002F8D50`, both before any read;
  `$t2` and `$at` are never used again in the function. Nothing else is
  touched: the cave opens no frame, saves nothing, and writes exactly one word
  of memory outside its own compare.
* **How it returns.** `j 0x002F8CEC`. It is not a call and takes no stack.
* **It runs before script.** The hook word is in place before any actor in the
  new level begins play, so `execGetMissionDescription` is already diverted for
  every call the rest of the load makes.
* **It cannot be undone later in the same load.** `LoadMap` is executing out of
  the overlay, so the overlay's own code cannot be re-read while it runs.

The installer's guard is one compare: it reads `0x00273200` and writes only if
the word is not already `j CAVE`. So whether or not the overlay survives a level
load, the hot page is written at most once per load -- and on a session where
the overlay does survive, at most once per boot.

WHERE IT HOOKS
--------------

`0x00273200`, the `jr $ra` that ends `execGetMissionDescription`. The delay slot
`0x00273204` is `addiu $sp,$sp,0x20` and runs either way, so the cave starts
with `$sp` popped, `$ra` reloaded (`0x002731F8`) and `$s0` restored
(`0x002731FC`). The native is `void` and its only output was already stored to
`*Result` at `0x002731F4`, so every caller-saved register is dead.

The **fast path opens no frame at all**. It touches only `$at`, `$v0`, `$v1`,
`$t0`-`$t3` and `$t8`, every one of them dead at the hook, and leaves through a
bare `jr $ra`. The verifier proves it: it runs the fast path with distinctive
128-bit values in all eight `$s` registers and `$fp`, and checks them plus
`$sp`, `$gp`, `$ra` and the 512 bytes around `$sp` for bit-identity afterwards.

Only the **slow path** opens a frame, saves all eight `$s` registers with `sq`
(128-bit -- the build treats them as quadword-live, which is why the displaced
epilogue used `lq`) plus `$ra` with `sd`, and leaves through the displaced
`jr $ra`.

`$gp` is live and correct at the hook -- the function itself used
`lw $v1,-0x66dc($gp)` four instructions earlier -- so both globals cost one
instruction each.

THE COPY, WHICH IS THE GAME'S OWN
---------------------------------

An FString is `{char* Data; INT Num; INT Max}` with `Num == Max == strlen+1` on
every field measured. The one thing that must never happen is a destination
taking the source's `Data` pointer: two fields would own one buffer and the
next `LoadConfig` would double-free it. So the cave reproduces the sequence the
gear room itself uses at `0x004883D0..0x004883FC`, and that the engine uses to
seed the split kits at `0x0058B110..0x0058B154`::

    dst->Max = src->Num
    dst->Num = src->Num
    FArray::Realloc(dst, 1, 0)        0x001727D0 -- resizes dst's OWN buffer
    if (dst->Num) appStrcpy(dst->Data, src->Data)      0x00146C10

`dst->Data` is only ever written by `Realloc`. Where the game would then hand a
null `Data` to `appStrcpy` via its empty-string literal, the cave instead
**skips the slot entirely** when the source is empty or null -- blanking an AI's
weapon class name is a worse outcome than leaving its own.

THE M203
--------

The launcher is a separate `R6Gadget` class sitting in the player's
`szSecondaryWeapon` slot. Copied verbatim into an AI's slot 1 it files under the
pawn's *gadget* inventory group, because `ServerGivesWeaponToClient` keys on the
weapon's own `m_InventoryGroup` -- so the teammate ends up with no sidearm at
all, and no AI block anywhere on the disc has ever held a launcher.

The game already ships the fix. `R6GameInfo.IsWeaponAllowed`
(`0x00487F68..0x00488204`) degrades each launcher to the grenade it throws, as
four pairs of consecutive overlay literals::

    0x005EC1C0 R6GrenadeLauncherHE    (29) -> 0x005EC1E0 R6FragGrenadeGadget       (29)
    0x005EC200 R6GrenadeLauncherCS    (29) -> 0x005EC220 R6TearGasGrenadeGadget    (32)
    0x005EC250 R6GrenadeLauncherRP    (29) -> 0x005EC270 R6PhosphorusGrenadeGadget (35)
    0x005EC2A0 R6GrenadeLauncherSmoke (32) -> 0x005EC2D0 R6SmokeGrenadeGadget      (30)

Detection is `Num in {30, 33}` **and** `Data[21:25] == "unch"`. The length test
alone is not enough -- `R6FragGrenadeGadget` is also Num 30 and
`R6TearGasGrenadeGadget` is also Num 33 -- and the pair together matches exactly
these four literals and nothing else in the overlay, which was checked by
scanning every NUL-terminated printable run in the image.

The substitute is keyed off `Data[27]`, which is `'H'`, `'C'`, `'R'`, `'S'`.
**The research pass named the fourth one `'o'`; that is wrong.** `Data+27` of
`R6Weapons.R6GrenadeLauncherSmoke` is `S`; `o` is at `+29`. A launcher whose
`+27` matches none of the four is copied verbatim rather than guessed at.

Because the four substitutes are fixed overlay literals, their lengths are
compile-time constants and the cave does **not** call `appStrlen` (`0x00146AD0`)
the way `IsWeaponAllowed` has to. The constants are checked against the literals
in the pristine overlay by the verifier.

THE GUARD
---------

Eight words at `0x000F67E0`, **never emitted** -- a pnach row rewrites its
address every frame, and rewriting the guard every frame would re-run the
forty-eight reallocs every frame::

    +0x00  ST_MD       identity    the R6MissionDescription pointer
    +0x04  ST_MODE     identity    GameEngine.mSplitScreenMode
    +0x08  ST_SUM      recorded    the source byte-sum -- NEVER a veto
    +0x0C  ST_COPIES   diagnostic  how many times the 48-slot copy has run
    +0x10  ST_LEVEL    identity    the live ULevel*
    +0x14  ST_DSTPTR   identity    [md+0x0B8], the destination canary's Data
    +0x18  ST_CALLS    diagnostic  how many times the cave has been ENTERED
    +0x1C  ST_DSTNUM   identity    [md+0x0BC], the canary's Num

Five words of identity. All five match -> `jr $ra`, 23 instructions, no frame,
no store but the call counter's. Any of them differs -> the copy.

**The requirement is "once per level load."** The gear-room choice can only
change across a level load, and `CreateTeamMember` -- the only thing that reads
these blocks -- runs at level load. So the identity is the level, not the
strings.

`GEngine+0x45C` is the live `ULevel*`. **Measured** in the nine EE dumps: it is
a UObject of class `Level` in all eight dumps that have a level; the ninth has
a null `GEngine` and a null md, which is why both null checks stay in the fast
path. In the one session that spans four maps -- ShipYard, Alpines, Alcatraz,
Import_Export -- it holds a **different pointer on every map**, and the same
pointer in two dumps taken on the same level. `GEngine+0x460` is also a `Level`
but is one object per session (the menu level, UObject index 18756 in every
dump), so `+0x45C` is the live one. The ULevel's UObject *index* is recycled
across level loads (19439 served both Alcatraz and Import_Export), so the index
would have been the wrong identity; the pointer is the right one.

The canary is a **destination**, and it is there because a level load re-parses
the mission INI over all twelve AI blocks. That is measured, not assumed: in
that same four-map session the authored `AI[0].szPrimaryWeapon` is
`AssaultL85A1` on ShipYard, `SubMP5A4` on Alpines, `AssaultFAMASG2` on Alcatraz
and `AssaultTAR21` on Import_Export. Its `Data` pointer alone is not enough --
`0x00F37590` served both ShipYard and Alcatraz -- which is why `Num` is
compared too; `0x00F37590` is `Num` 26 on one and 28 on the other.

WHY THE BYTE-SUM IS RECORDED AND NOT CONSULTED
-----------------------------------------------

The byte-sum is still computed, once per copy, and still stored at `+0x08`, so
a savestate shows it and a same-length rename is still visible in it. It is
**never** read back. A byte-sum over the SOURCES, placed after the identity
test, cannot do the job the first build asked of it, and as a veto it is
actively wrong:

* It **cannot** see a `ULevel` reallocated at the previous level's address. In
  that case the identity MATCHES and the byte-sum is never reached at all. The
  canary covers that case instead -- soundly, for two instructions, because it
  is a destination and the destination is what gets re-parsed.
* As a veto it **breaks the requirement**. A mission restarted with an
  unchanged kit re-parses the INI, so every destination is reset while every
  source string stays byte-identical. A byte-sum veto skips the copy and the
  mirror silently does not apply. The verifier runs exactly that case through
  the first build's cave and shows it skipping, and through this one and shows
  it copying.

The one thing this costs: a source change with **no** level load is no longer
detected. It cannot happen in play -- the gear room commits and then the level
loads -- and the only sound way to detect it would be the full byte-sum on
every call, which is the defect being fixed. Comparing source pointers and
lengths instead is not sound and never was: `FArray::Realloc` returns the same
buffer for a same-length name, so `AssaultTAR21` -> `AssaultL85A1` is invisible
to it. The verifier asserts this deliberate miss explicitly rather than leaving
it to be discovered.

WHY THE GUARD IS WRITTEN AFTER THE COPY
----------------------------------------

The canary is a destination the copy has just rewritten. A guard stored *before*
the copy would hold the pre-copy canary, mismatch on the very next call, and
the cave would re-copy forever -- forty-eight reallocs per call, far worse than
the defect being fixed. So all five identity words, the byte-sum and the copy
counter are written at the end, after the loops, from globals re-read at that
point. The verifier checks that every store to an identity word sits at or past
the `store` label.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------

* It does not touch `m_PlayerEquipment` (+0x058) or
  `m_PlayerSilencedEquipment` (+0x088). Those are the player's own blocks.
* It does not write the pawns. It rewrites the description the spawn code
  reads, so it only takes effect at the next `CreateTeamMember` -- which in
  practice means the next mission start or the next reinforcement, not
  mid-firefight.
* It does not call script and keeps no state outside its own eight STATE
  words. The only memory it allocates is the destination buffers, through the
  game's own `FArray::Realloc`, exactly as the gear room does -- and the fast
  path allocates nothing at all, which the verifier proves by checking that the
  heap did not grow and that all forty-eight destination FStrings are
  bit-identical across a repeat call.
* It does not validate the weapon against the AI's third-person models. See
  the caution.

HONEST LIMITATIONS
------------------

* **Never played.** Everything here is reasoned from the disassembly and from
  eight EE dumps, and the copy is proven only against a simulator.
* The one-player source (`m_PrimaryWeapon`) is pinned by static evidence -- the
  gear-room commit at `0x004883A4` writes it, and the engine seeds the split
  kits from it at `0x0058B0FC` -- not by a positive measurement of a
  one-player gear-room change. Only one of the eight dumps was a one-player
  session, and in it the player's kit happened to equal the map default, so the
  two cannot be told apart from that dump alone.
* **The first build's cost was a guess and the guess was wrong.** Its guard
  byte-summed four source strings (one player) or eight (split screen) on every
  single call: 557 and 1,098 instructions, against 2,428 and 3,089 for the one
  call that did the copying. In play that stuttered and skipped audio through a
  mission load. This build's guard costs **23** in both modes (25 issued),
  against 2,439 and 3,100 for the copy. The call frequency is still not
  measured -- but `ST_CALLS` now measures it, so the next person does not have
  to guess.
* **The trigger moved from "the sources changed" to "the level changed."** It
  fires no later than the old one did. `GEngine+0x45C` is written from C++, not
  from script -- script on this disc is bytecode, not MIPS. `sw rt,0x45C(rs)`
  occurs 27 times in the overlay, 15 off a base that is not `$sp`, and two of
  those 15 are the ones that matter: `0x00300E68` (`sw $v0,0x45C($s4)`, in the
  function carrying the `InvalidUrl` and `AbortToEntry` literals --
  Browse/LoadMap) and `0x002EA348`/`0x002EA350`, which clear it and then set it
  from `+0x460` beside the literal `Entry`, the return-to-menu path. The other
  thirteen were not chased. And the mission level can only be *ticked* through
  `+0x45C` -- `+0x460` holds the Entry level, UObject index 18756 in all nine
  dumps -- so any script native called from a mission actor necessarily runs
  with `+0x45C` already pointing at that mission's level. The old guard, by
  contrast, had to wait for the mission INI re-parse to move the byte-sum.

  What is still **not** proven: that a call lands between the level being
  installed and `CreateTeamMember` running. That ordering was not walked in the
  bytecode. The defect itself is the evidence that this native is called many
  times through a load.
* **A false skip is possible in principle.** If a level load put the new
  `ULevel` at the previous one's address AND left `[md+0x0B8]` with the same
  `Data` and the same `Num`, that mission would not be mirrored. Not a crash,
  not corruption, and the next level load would clear it. Nothing like it
  appears in the dumps: six gameplay levels, six distinct `ULevel` pointers,
  and the one `Data` repeat carries a different `Num`.
* Delivered as an emulator cheat file, not written to the disc, for the same
  reason every other cave here is: a code cave baked into the overlay does not
  survive a level load.
"""

from __future__ import annotations


class MirrorError(Exception):
    pass


#: `jr $ra` ending execGetMissionDescription. Its delay slot,
#: `addiu $sp,$sp,0x20`, runs either way.
HOOK_AT = 0x00273200
HOOK_STOCK = 0x03E00008
HOOK_NEW = 0x0803D800          # j 0x000F6000

CAVE = 0x000F6000
SPAN_END = 0x000F6800

# --------------------------------------------------------------------------
# THE INSTALLER ("arm"). The hook word above is NOT a pnach row any more -- a
# pnach row rewrites it every vsync, and page 0x00273000 holds eleven script
# natives, the hottest code there is during a level load. These ten words put
# the hook word in place once per level load instead, from inside
# UGameEngine::LoadMap. See "THE HOT PAGE" in the docstring.
# --------------------------------------------------------------------------
#: `lw $v0,-0x6F3C($gp)` in UGameEngine::LoadMap, after the level install at
#: 0x002F8C54 and before any actor in the new level begins play. Its delay slot
#: 0x002F8CE8 is `lui $a1,0x5E` -- not a branch, and still live -- so the cave
#: preserves $a1 and returns past it.
ARM_AT = 0x002F8CE4
ARM_STOCK = 0x8F8290C4
ARM_NEW = 0x0803DA40           # j 0x000F6900
#: the installer's own cave. It sits in the SAME 4 KB page as the main cave, so
#: it adds no new pnach-dirtied page on the cave side, and clear of STATE.
ARM_CAVE = 0x000F6900
ARM_SPAN_END = 0x000F6A00
#: where it returns: past the delay slot, which has already run.
ARM_RETURN = 0x002F8CEC
#: how many words `arm_words()` returns
ARM_WORD_COUNT = 10
#: eight words of runtime state. **Never emitted** -- a pnach row rewrites its
#: address every frame, and rewriting the guard every frame would re-run the
#: forty-eight reallocs every frame.
STATE = 0x000F67E0
STATE_END = 0x000F6800
#: the STATE band word by word. Five are the guard's identity, three are
#: diagnostics to read out of a savestate. THE ONE TO READ FIRST is ST_CALLS:
#: it counts every entry to the cave, which is how often script really asks for
#: the mission description -- the number the first build had to guess.
ST_MD = 0x00        # identity: the R6MissionDescription pointer
ST_MODE = 0x04      # identity: GameEngine.mSplitScreenMode
ST_SUM = 0x08       # diagnostic: the source byte-sum, recorded, never a veto
ST_COPIES = 0x0C    # diagnostic: how many times the 48-slot COPY has run
ST_LEVEL = 0x10     # identity: the live ULevel*
ST_DSTPTR = 0x14    # identity: [md+0x0B8], the destination canary's Data
ST_CALLS = 0x18     # diagnostic: how many times the cave has been ENTERED
ST_DSTNUM = 0x1C    # identity: [md+0x0BC], the canary's Num
#: the eight emitted data words -- two pairing rows and two source-offset
#: tables -- sit here, just below STATE. The dials move the two rows.
TABLE = 0x000F67C0

#: how many of the four slots are mirrored. The three scopes are prefixes of
#: each other (0b0001 / 0b0011 / 0b1111), so the mask reaches the cave as a
#: single slot count -- the bound of the slot loop.
SCOPES = ("primary", "primary_secondary", "weapons_gadgets")
SCOPE_DEFAULT = "weapons_gadgets"
SCOPE_MASK = {"primary": 0b0001, "primary_secondary": 0b0011,
              "weapons_gadgets": 0b1111}
#: what to do with a grenade launcher sitting in the player's sidearm slot.
LAUNCHERS = ("degrade", "keep_own", "verbatim")
LAUNCHER_DEFAULT = "degrade"

#: which player each operative copies. Index is the operative -- 0 Price,
#: 1 Loiselle, 2 Weber -- and the value is 0 (leave that operative's authored
#: kit alone), 1 (player one) or 2 (player two). In one-player mode both 1 and
#: 2 resolve to m_PrimaryWeapon, because there is only one player.
#:
#: Price keeps a 1 in the split row rather than a 0 because it is harmless
#: either way: if he is the second human his block is never read, and if he is
#: not he should mirror player one like Loiselle. Set the first byte to 0 to
#: leave him alone regardless -- `words()` takes the table, so no regeneration
#: is needed.
AI_TO_PLAYER_SINGLE = (1, 1, 1)
AI_TO_PLAYER_SPLIT = (1, 1, 2)
PAIRING_DEFAULT = (AI_TO_PLAYER_SINGLE, AI_TO_PLAYER_SPLIT)

#: the R6MissionDescription offsets, all from live UProperty objects
MD_GPOFF = -0x66DC         # gp-relative R6MissionDescription*
GE_GPOFF = -0x6F44         # gp-relative GEngine*
SPLIT_MODE = 0x4E4          # GameEngine.mSplitScreenMode
LEVEL_OFF = 0x45C          # GameEngine's live ULevel* -- the guard's trigger
SRC_SP, SRC_P1, SRC_P2 = 0x320, 0x410, 0x440
SLOT = (0x00, 0x0C, 0x18, 0x24)
#: Price, Loiselle, Weber, then the same three silenced, then terrorist hunt,
#: then silenced terrorist hunt. Twelve 48-byte structs, contiguous, stride
#: 0x30 -- which is why the cave needs no table for them, only a counter.
AI_BLOCK = (0x0B8, 0x0E8, 0x118,  0x148, 0x178, 0x1A8,
            0x1D8, 0x208, 0x238,  0x268, 0x298, 0x2C8)

#: the two helpers the cave calls. appStrlen at 0x00146AD0 is NOT called: the
#: four substitute literals have compile-time lengths.
FARRAY_REALLOC = 0x001727D0
APPSTRCPY = 0x00146C10

#: (discriminator at Data+27, substitute literal, its strlen+1). The plan this
#: was built from named the fourth key 'o'; the overlay says 'S'.
SUBSTITUTES = (
    (0x48, 0x005EC1E0, 30),
    (0x43, 0x005EC220, 33),
    (0x52, 0x005EC270, 36),
    (0x53, 0x005EC2D0, 31),
)
LAUNCH_NUMS = (30, 33)
LAUNCH_TAG_AT = 21
LAUNCH_TAG = b'unch'
LAUNCH_KEY_AT = 27

#: how many words `words()` returns, code plus tables
WORD_COUNT = 254

#: the three words the dials patch, and the two table rows
_SCOPE_AT = 0x000F62BC
_GATE_AT = 0x000F60E8
_ACTION_AT = 0x000F6144
_SCOPE_WORD = {'primary': 0x2E810001, 'primary_secondary': 0x2E810002, 'weapons_gadgets': 0x2E810004}
#: `b plain` -- verbatim skips the whole launcher detector
_GATE_WORD = {'degrade': 0x00000000, 'keep_own': 0x00000000, 'verbatim': 0x1000005F}
#: `b slot_next` -- keep_own leaves the AI's own sidearm in place
_ACTION_WORD = {'degrade': 0x00000000, 'keep_own': 0x1000005A, 'verbatim': 0x00000000}

_VAS = (
    0x000F6000, 0x000F6004, 0x000F6008, 0x000F600C,
    0x000F6010, 0x000F6014, 0x000F6018, 0x000F601C,
    0x000F6020, 0x000F6024, 0x000F6028, 0x000F602C,
    0x000F6030, 0x000F6034, 0x000F6038, 0x000F603C,
    0x000F6040, 0x000F6044, 0x000F6048, 0x000F604C,
    0x000F6050, 0x000F6054, 0x000F6058, 0x000F605C,
    0x000F6060, 0x000F6064, 0x000F6068, 0x000F606C,
    0x000F6070, 0x000F6074, 0x000F6078, 0x000F607C,
    0x000F6080, 0x000F6084, 0x000F6088, 0x000F608C,
    0x000F6090, 0x000F6094, 0x000F6098, 0x000F609C,
    0x000F60A0, 0x000F60A4, 0x000F60A8, 0x000F60AC,
    0x000F60B0, 0x000F60B4, 0x000F60B8, 0x000F60BC,
    0x000F60C0, 0x000F60C4, 0x000F60C8, 0x000F60CC,
    0x000F60D0, 0x000F60D4, 0x000F60D8, 0x000F60DC,
    0x000F60E0, 0x000F60E4, 0x000F60E8, 0x000F60EC,
    0x000F60F0, 0x000F60F4, 0x000F60F8, 0x000F60FC,
    0x000F6100, 0x000F6104, 0x000F6108, 0x000F610C,
    0x000F6110, 0x000F6114, 0x000F6118, 0x000F611C,
    0x000F6120, 0x000F6124, 0x000F6128, 0x000F612C,
    0x000F6130, 0x000F6134, 0x000F6138, 0x000F613C,
    0x000F6140, 0x000F6144, 0x000F6148, 0x000F614C,
    0x000F6150, 0x000F6154, 0x000F6158, 0x000F615C,
    0x000F6160, 0x000F6164, 0x000F6168, 0x000F616C,
    0x000F6170, 0x000F6174, 0x000F6178, 0x000F617C,
    0x000F6180, 0x000F6184, 0x000F6188, 0x000F618C,
    0x000F6190, 0x000F6194, 0x000F6198, 0x000F619C,
    0x000F61A0, 0x000F61A4, 0x000F61A8, 0x000F61AC,
    0x000F61B0, 0x000F61B4, 0x000F61B8, 0x000F61BC,
    0x000F61C0, 0x000F61C4, 0x000F61C8, 0x000F61CC,
    0x000F61D0, 0x000F61D4, 0x000F61D8, 0x000F61DC,
    0x000F61E0, 0x000F61E4, 0x000F61E8, 0x000F61EC,
    0x000F61F0, 0x000F61F4, 0x000F61F8, 0x000F61FC,
    0x000F6200, 0x000F6204, 0x000F6208, 0x000F620C,
    0x000F6210, 0x000F6214, 0x000F6218, 0x000F621C,
    0x000F6220, 0x000F6224, 0x000F6228, 0x000F622C,
    0x000F6230, 0x000F6234, 0x000F6238, 0x000F623C,
    0x000F6240, 0x000F6244, 0x000F6248, 0x000F624C,
    0x000F6250, 0x000F6254, 0x000F6258, 0x000F625C,
    0x000F6260, 0x000F6264, 0x000F6268, 0x000F626C,
    0x000F6270, 0x000F6274, 0x000F6278, 0x000F627C,
    0x000F6280, 0x000F6284, 0x000F6288, 0x000F628C,
    0x000F6290, 0x000F6294, 0x000F6298, 0x000F629C,
    0x000F62A0, 0x000F62A4, 0x000F62A8, 0x000F62AC,
    0x000F62B0, 0x000F62B4, 0x000F62B8, 0x000F62BC,
    0x000F62C0, 0x000F62C4, 0x000F62C8, 0x000F62CC,
    0x000F62D0, 0x000F62D4, 0x000F62D8, 0x000F62DC,
    0x000F62E0, 0x000F62E4, 0x000F62E8, 0x000F62EC,
    0x000F62F0, 0x000F62F4, 0x000F62F8, 0x000F62FC,
    0x000F6300, 0x000F6304, 0x000F6308, 0x000F630C,
    0x000F6310, 0x000F6314, 0x000F6318, 0x000F631C,
    0x000F6320, 0x000F6324, 0x000F6328, 0x000F632C,
    0x000F6330, 0x000F6334, 0x000F6338, 0x000F633C,
    0x000F6340, 0x000F6344, 0x000F6348, 0x000F634C,
    0x000F6350, 0x000F6354, 0x000F6358, 0x000F635C,
    0x000F6360, 0x000F6364, 0x000F6368, 0x000F636C,
    0x000F6370, 0x000F6374, 0x000F6378, 0x000F637C,
    0x000F6380, 0x000F6384, 0x000F6388, 0x000F638C,
    0x000F6390, 0x000F6394, 0x000F6398, 0x000F639C,
    0x000F63A0, 0x000F63A4, 0x000F63A8, 0x000F63AC,
    0x000F63B0, 0x000F63B4, 0x000F63B8, 0x000F63BC,
    0x000F63C0, 0x000F63C4, 0x000F63C8, 0x000F63CC,
    0x000F63D0, 0x000F63D4, 0x000F67C0, 0x000F67C4,
    0x000F67C8, 0x000F67CC, 0x000F67D0, 0x000F67D4,
    0x000F67D8, 0x000F67DC,
)

_WORDS = (
    0x3C18000F, 0x8F0267F8, 0x24420001, 0xAF0267F8,
    0x8F889924, 0x110000D8, 0x8F8990BC, 0x112000D6,
    0x8F0267E0, 0x1448000D, 0x8D2A04E4, 0x8F0367E4,
    0x146A000A, 0x8D2B045C, 0x8F0267F0, 0x144B0007,
    0x8D0300B8, 0x8F0267F4, 0x14430004, 0x8D0300BC,
    0x8F0267FC, 0x104300C8, 0x00000000, 0x27BDFF70,
    0x7FB00000, 0x7FB10010, 0x7FB20020, 0x7FB30030,
    0x7FB40040, 0x7FB50050, 0x7FB60060, 0x7FB70070,
    0xFFBF0080, 0x271667C0, 0x11400003, 0x271767C8,
    0x271667C4, 0x271767D4, 0x241200B8, 0x00009821,
    0x02D34021, 0x91090000, 0x11200087, 0x00094880,
    0x02E94821, 0x8D350000, 0x12A00083, 0x0000A021,
    0x8F889924, 0x01128021, 0x01158821, 0x8E280004,
    0x11000077, 0x8E290000, 0x11200075, 0x3A810001,
    0x14200061, 0x00000000, 0x00000000, 0x00000000,
    0x2501FFE2, 0x10200003, 0x2501FFDF, 0x1420005A,
    0x00000000, 0x91220015, 0x38410075, 0x14200056,
    0x00000000, 0x91220016, 0x3841006E, 0x14200052,
    0x00000000, 0x91220017, 0x38410063, 0x1420004E,
    0x00000000, 0x91220018, 0x38410068, 0x1420004A,
    0x00000000, 0x00000000, 0x00000000, 0x9122001B,
    0x38410048, 0x1020000C, 0x00000000, 0x38410043,
    0x10200017, 0x00000000, 0x38410052, 0x10200022,
    0x00000000, 0x38410053, 0x1020002D, 0x00000000,
    0x10000039, 0x00000000, 0x2402001E, 0xAE020008,
    0xAE020004, 0x02002021, 0x24050001, 0x0C05C9F4,
    0x00003021, 0x8E040000, 0x10800041, 0x3C05005F,
    0x0C051B04, 0x24A5C1E0, 0x1000003D, 0x00000000,
    0x24020021, 0xAE020008, 0xAE020004, 0x02002021,
    0x24050001, 0x0C05C9F4, 0x00003021, 0x8E040000,
    0x10800033, 0x3C05005F, 0x0C051B04, 0x24A5C220,
    0x1000002F, 0x00000000, 0x24020024, 0xAE020008,
    0xAE020004, 0x02002021, 0x24050001, 0x0C05C9F4,
    0x00003021, 0x8E040000, 0x10800025, 0x3C05005F,
    0x0C051B04, 0x24A5C270, 0x10000021, 0x00000000,
    0x2402001F, 0xAE020008, 0xAE020004, 0x02002021,
    0x24050001, 0x0C05C9F4, 0x00003021, 0x8E040000,
    0x10800017, 0x3C05005F, 0x0C051B04, 0x24A5C2D0,
    0x10000013, 0x00000000, 0x8E220004, 0xAE020008,
    0xAE020004, 0x02002021, 0x24050001, 0x0C05C9F4,
    0x00003021, 0x8E060004, 0x10C00009, 0x00000000,
    0x8E250000, 0x10A00006, 0x00000000, 0x8E040000,
    0x10800003, 0x00000000, 0x0C051B04, 0x00000000,
    0x26940001, 0x2610000C, 0x2631000C, 0x2E810004,
    0x1420FF82, 0x00000000, 0x26520030, 0x26730001,
    0x24010003, 0x16610002, 0x00000000, 0x00009821,
    0x2E4102F8, 0x1420FF6E, 0x00000000, 0x3C18000F,
    0x8F889924, 0x8F8990BC, 0x8D2A04E4, 0x8D2B045C,
    0xAF0867E0, 0xAF0A67E4, 0xAF0B67F0, 0x8D0C00B8,
    0xAF0C67F4, 0x8D0C00BC, 0xAF0C67FC, 0x00006821,
    0x8EEE0004, 0x0C03D8E0, 0x8EEF0008, 0x11EE0003,
    0x01E07021, 0x0C03D8E0, 0x00000000, 0xAF0D67E8,
    0x8F0267EC, 0x24420001, 0xAF0267EC, 0x7BB00000,
    0x7BB10010, 0x7BB20020, 0x7BB30030, 0x7BB40040,
    0x7BB50050, 0x7BB60060, 0x7BB70070, 0xDFBF0080,
    0x03E00008, 0x27BD0090, 0x03E00008, 0x00000000,
    0x010E2021, 0x24850030, 0x000D3140, 0x00CD6823,
    0x8C860004, 0x01A66821, 0x8C870000, 0x10E00009,
    0x00000000, 0x10C00007, 0x00000000, 0x00E63021,
    0x90E20000, 0x24E70001, 0x01A26821, 0x14E6FFFC,
    0x00000000, 0x2484000C, 0x1485FFEF, 0x00000000,
    0x03E00008, 0x00000000, 0x00010101, 0x00020101,
    0x00000000, 0x00000320, 0x00000320, 0x00000000,
    0x00000410, 0x00000440,
)


def _pairword(row):
    if len(row) != 3 or any(v not in (0, 1, 2) for v in row):
        raise MirrorError("a pairing row is three values from 0, 1, 2: %r" % (row,))
    return (row[0] & 0xFF) | ((row[1] & 0xFF) << 8) | ((row[2] & 0xFF) << 16)


def words(scope: str = SCOPE_DEFAULT, launcher: str = LAUNCHER_DEFAULT,
          pairing=PAIRING_DEFAULT):
    """[(va, word)] for the cave, with the scope, the launcher policy and the
    operative-to-player pairing patched in."""
    if scope not in SCOPES:
        raise MirrorError("no such mirror scope: %r" % (scope,))
    if launcher not in LAUNCHERS:
        raise MirrorError("no such launcher policy: %r" % (launcher,))
    single, split = pairing
    patch = {_SCOPE_AT: _SCOPE_WORD[scope],
             _GATE_AT: _GATE_WORD[launcher],
             _ACTION_AT: _ACTION_WORD[launcher],
             TABLE + 0x00: _pairword(single),
             TABLE + 0x04: _pairword(split)}
    out = []
    for va, w in zip(_VAS, _WORDS):
        if STATE <= va < STATE_END:
            raise MirrorError("the cave's own guard must never be emitted")
        out.append((va, patch.get(va, w)))
    return out


#: the installer, word for word. $t0/$t1/$t2 are dead at ARM_AT and $at is
#: never used again in LoadMap; $v0 is the displaced load's own destination.
_ARM_WORDS = (
    0x8F8290C4,     # 0x000F6900  lw    $v0, -0x6F3C($gp)   the displaced word
    0x3C080803,     # 0x000F6904  lui   $t0, 0x0803
    0x3508D800,     # 0x000F6908  ori   $t0, $t0, 0xD800    $t0 = `j CAVE`
    0x3C090027,     # 0x000F690C  lui   $t1, 0x0027
    0x8D2A3200,     # 0x000F6910  lw    $t2, 0x3200($t1)    the hook word now
    0x110A0002,     # 0x000F6914  beq   $t0, $t2, +2        already ours: skip
    0x00000000,     # 0x000F6918  nop
    0xAD283200,     # 0x000F691C  sw    $t0, 0x3200($t1)    install it
    0x080BE33B,     # 0x000F6920  j     0x002F8CEC
    0x00000000,     # 0x000F6924  nop
)


def arm_words():
    """[(va, word)] for the installer cave.

    Ten words, no frame, no call, one store. Emitted whenever the mirror is on;
    `HOOK_AT` itself is deliberately NOT emitted -- that is the whole point.
    """
    out = [(ARM_CAVE + 4 * i, w) for i, w in enumerate(_ARM_WORDS)]
    if len(out) != ARM_WORD_COUNT:
        raise MirrorError("the installer is %d words, not %d"
                          % (len(out), ARM_WORD_COUNT))
    if out[-1][0] + 4 > ARM_SPAN_END:
        raise MirrorError("the installer overran its span")
    if any(CAVE <= va < SPAN_END for va, _w in out):
        raise MirrorError("the installer must not land in the main cave")
    return out


def reads(word_at) -> bool:
    """True if `word_at(va)` shows the installer in place.

    Keyed on ARM_AT, not on HOOK_AT: the hook word is written by the game at
    level-load time and is not in the cheat file at all, so a stock HOOK_AT
    means nothing either way.
    """
    return word_at(ARM_AT) != ARM_STOCK


def stock_words():
    """{va: stock} for every overlay word this module touches.

    Two: the installer's hook, which IS emitted, and the description native's
    `jr $ra`, which is not -- it is registered anyway so the address has a
    recorded stock value wherever one is looked up.
    """
    return {ARM_AT: ARM_STOCK, HOOK_AT: HOOK_STOCK}


def cards(prefix, group):
    from .model import BOOL, CHOICE, Choice, Setting

    return [
        Setting(
            prefix + "mirror_loadout",
            "Teammates carry what you actually picked", BOOL, False, group,
            touches="ram", confidence="experimental", pnach_only=True,
            help="Price, Loiselle and Weber take the kit you chose on the gear "
                 "screen for this run, instead of the one the level author gave "
                 "them.\n\n"
                 "This is NOT the same as \"Teammates carry your loadout\" "
                 "further up. That one edits the map file on the disc, so they "
                 "copy the kit the mission HANDS you before you change "
                 "anything. This one reads what you actually walked in with. "
                 "They really are different: on Alpines the map hands you an "
                 "MP5A4 with an RP launcher, a frag and smoke, and the save "
                 "this was built against had the player carrying a silenced "
                 "MP5SD5 with an HE launcher and two frags.\n\n"
                 "It is applied later than the disc edit, so if you switch both "
                 "on this one wins and the older option has no effect -- you "
                 "can leave it off.\n\n"
                 "All four silenced, terrorist-hunt and silenced-hunt variants "
                 "of each teammate's kit are written too, so it works whichever "
                 "kind of mission you start. In split screen player two's "
                 "choice goes to Weber and player one's to the other two.",
            caution="Never played. Everything here is read out of the "
                    "disassembly and out of savestates.\n\n"
                    "THE REAL RISK is a weapon no Rainbow teammate ever "
                    "carries. The AI have only ever been given assault rifles, "
                    "submachine guns and pistols; hand one a shotgun, a machine "
                    "gun or a sniper rifle and it is being given something it "
                    "may have no third-person model or animation set for, which "
                    "is what crashed the game when the enemy weapon tables "
                    "were first re-rolled. If you pick one of those for "
                    "yourself, expect this to be the option that breaks.\n\n"
                    "A mirrored weapon may also turn out to be SILENT in a "
                    "teammate's hands on some maps -- if the map has not loaded "
                    "that weapon's sound bank, nothing will play it. That is a "
                    "possible consequence to listen for in play, not a "
                    "mechanism anyone has established: an earlier session's "
                    "explanation for a related silence was investigated and "
                    "withdrawn.\n\n"
                    "Delivered as a PCSX2 cheat file, not written to the disc, "
                    "because a code cave does not survive a level load. Save a "
                    "fresh cheat file after changing this and restart the "
                    "emulator so it is re-read.\n\n"
                    "FIXED 2026-09-27: this used to stall the mission load and "
                    "break up the audio. The cheat file was rewriting one word "
                    "of the game's script-dispatch code sixty times a second, "
                    "and the emulator threw away and rebuilt that whole page of "
                    "code every time it did. The game now writes that word "
                    "itself, once, as each level loads. If you still have an "
                    "older cheat file with a hand-written line for address "
                    "00273200 in it, DELETE THAT LINE -- a leftover copy "
                    "outside the managed block keeps the stall alive.\n\n"
                    "It changes the description the spawn code reads, not the "
                    "teammates themselves, so a change only shows up the next "
                    "time a teammate is created -- normally the next mission "
                    "start."),
        Setting(
            prefix + "mirror_scope", "How much of your kit they copy", CHOICE,
            SCOPE_DEFAULT, group, touches="ram", confidence="experimental",
            pnach_only=True,
            requires={prefix + "mirror_loadout": [True]},
            choices=[
                Choice("primary", "Primary weapon only",
                       "The safest of the three: it is the slot the AI already "
                       "share with you on every map measured."),
                Choice("primary_secondary", "Primary and sidearm",
                       "Also replaces their pistol, which is where a grenade "
                       "launcher would land."),
                Choice("weapons_gadgets", "Weapons and both gadgets",
                       "Everything. They lose their flashbangs and breaching "
                       "charges and carry your grenades instead."),
            ],
            help="Their four slots are primary weapon, sidearm, first gadget, "
                 "second gadget, in that order, and this copies the first one, "
                 "the first two, or all four.\n\n"
                 "Worth knowing: the AI normally carry a flashbang and a "
                 "breaching charge between them -- on every map measured Loiselle "
                 "and Weber each carry one. Copying all four slots takes both "
                 "away, so doors you were expecting the squad to blow will have "
                 "to be opened another way."),
        Setting(
            prefix + "mirror_launcher", "If you are carrying a grenade launcher",
            CHOICE, LAUNCHER_DEFAULT, group, touches="ram",
            confidence="experimental", pnach_only=True,
            requires={prefix + "mirror_loadout": [True]},
            choices=[
                Choice("degrade", "Give them the grenade instead",
                       "An HE launcher becomes a frag, CS becomes tear gas, RP "
                       "becomes phosphorus, smoke becomes smoke. This is the "
                       "game's own substitution, used by the same table that "
                       "decides which weapons a mode allows."),
                Choice("keep_own", "Leave their own sidearm alone",
                       "They keep their pistol and only the other slots are "
                       "mirrored."),
                Choice("verbatim", "Give them the launcher itself",
                       "Untested and the one that can plausibly hang a level "
                       "load."),
            ],
            help="The launcher is not a weapon as far as the game is concerned "
                 "-- it is a gadget that happens to sit in your sidearm slot. "
                 "Handed to a teammate it files under their gadgets, which "
                 "leaves them with no sidearm at all, and no teammate anywhere "
                 "on the disc has ever been given one.\n\n"
                 "So the first two options are the honest ones. The third is "
                 "there because someone will want to try it.",
            caution="\"Give them the launcher itself\" is the one setting here "
                    "that can plausibly hang a level load: it puts a class in a "
                    "slot the spawn code has never been asked to fill, and the "
                    "spawn runs during the load. If a mission stops loading "
                    "after you turn this on, this is the first thing to put "
                    "back."),
    ]

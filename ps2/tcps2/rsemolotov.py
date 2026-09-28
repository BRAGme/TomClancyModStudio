"""Molotovs and flashbangs for the terrorists.

What the game ships
-------------------

Every terrorist's grenade is a string in his pawn template, and
`R6Terrorist`'s native template applier (`0x003867D0`) resolves it once, at
spawn, by handing it to `UObject::StaticLoadObject`. Of the 118 shipped
templates, 41 name `R6Weapons.r6fraggrenadegadget`, four name
`R6Weapons.R6MolotovGadget`, four name a flashbang, a handful name smoke or
tear gas, and the rest name `None.None` -- no grenade at all. The molotov is
therefore a real, finished, shipped weapon that four of 118 templates ever
hand out, and in practice you meet it on the Alcatraz maps and nowhere else.

The lever
---------

`PickGrenadeClass` (`0x003C92E0`, 544 bytes) is the native that turns a
terrorist's weighted grenade table into the string written to
`m_szGrenadeWeapon` (pawn `+0x9A0`). It rolls `rand() % 100` over the
template's table, then converges on ONE word::

    003c9370  move  $s0, $zero          ; nothing matched
    003c9374  beq   $s0, $zero, 0x3c9388   <-- HOOK_AT
    003c9378  lui   $at, 0x5e              <-- delay slot: not a branch, still runs
    003c937c  addiu $v0, $zero, -1
    003c9380  bne   $s0, $v0, 0x3c93f0  ; a real class -> stringify it
    003c9384  nop
    003c9388  lb    $v0, 0x4f90($at)    ; RET_EMPTY: strlen of the empty name
    003c938c  beqz  $v0, 0x3c93a8
    003c9390  sw    $s1, 0x68($sp)      ; delay slot: spill the sret FString*
    ...
    003c93a8  move  $v0, $zero          ; RET_ZERO: length 0 -> build ""
    003c93f0  lw    $v0, 0x18($s0)      ; RET_CLASS: build Outer.Name "." Class.Name

At `0x003C9374` the chosen grenade is still a raw `UClass*` in `$s0` -- 0, -1
or a real pointer -- and the game's own stringifier has not run yet. **So the
substitution is one register store, `move $s0, $v0`.** No FString is built,
resized, copied or freed by the cave; the game builds the string afterwards
from whatever object `$s0` names, exactly as it would for a terrorist who had
carried that template all along.

Coming back, the cave re-runs the same two tests and enters at `RET_CLASS` or
at `RET_ZERO` -- one instruction past the pair that needs `$at`. It skips them
because in the shipped build they cannot do anything else: `0x005E4F90` is a
single NUL, so `lb`/`beqz` always branches, the `strlen` call at `0x003C9398`
is dead code, and the whole of `RET_EMPTY` reduces to "length 0". The cave
replays `0x003C9390`'s spill (`sw $s1, 0x68($sp)`, the identical word) because
that sits in the skipped branch's delay slot and `0x003C93AC` reads it back.

Entering at `RET_ZERO` rather than `RET_EMPTY` is not a micro-optimisation --
it is what makes the option survive onto another pressing of the disc. See
"Carrying onto another pressing" below, which is the reason this tail is
written the way it is rather than the obvious way.

Why NOT the data edit
---------------------

`docs/PATCHES.md`, "`WS[43]` is dead data -- do not use it", stands unchanged
and this module does not revisit it. Two separate things were withdrawn there
and both stay withdrawn:

* The `WS[43]=(bUsing=true,weaponname="R6MolotovGadget",...)` table in every
  `/MAPS/<NAME>.INI`. Nothing reads it. `bUsing`, `weaponname`, `sndName0`
  and the literal `WS[` appear zero times in the overlay, in the boot
  executable and in every decompressed level package, and Unreal's config
  importer cannot import a struct member whose name is absent from every name
  table. An earlier build of this tool offered "molotovs on every level" on
  the strength of that table; it was withdrawn and it is not coming back.

* Rewriting the template text. Handing a molotov to a frag terrorist means
  replacing `r6fraggrenadegadget` with `R6MolotovGadget` inside the template
  run -- a SHORTER name, so it needs padding after the comma, and a previous
  whitespace-padded attempt on these packages hung the loader. A LIN package
  only takes digit-for-digit edits (`tcps2/lin.py`).

The cave has neither problem, and that is the whole reason it exists: it never
touches the template text, so no string ever changes length. The only string
work is two read-only literals the cave carries itself, and they are
byte-identical to strings the retail game already resolves --
`R6Weapons.R6MolotovGadget` and `R6Weapons.r6flashbanggadget` both appear
verbatim in the shipped template run of all three COMMON packages.

What the cave does
------------------

62 words at `0x000F6C00`, in EE RAM below the ELF load base::

    roll = (rand() >> 5) & 0x3FF          ; 0..1023, so 1024 == 100%
    roll <  P_MOLO                        -> "R6Weapons.R6MolotovGadget"
    P_MOLO <= roll < P_FLASH              -> "R6Weapons.r6flashbanggadget"
    otherwise                             -> the stock pick, untouched

`P_FLASH` is CUMULATIVE: the flashbang's own share is `P_FLASH - P_MOLO`.
`rand()` is `0x00146DF0`, the same wrapper `PickGrenadeClass` itself calls
four instructions into its prologue; it returns the top 32 bits of a 64-bit
LCG masked to `0x7FFFFFFF`, so bits 5..14 are as good as any and `>> 5`
merely avoids the low-bit correlation `% 100` would expose.

The name is resolved with `UObject::StaticLoadObject` (`0x0017EA10`) using
byte-for-byte the argument setup the game's own template parser uses at
`0x003CB118..0x003CB130`::

    a0 = gp-0x7cdc            ; cached UClass* for class 'Class'
    a1 = NULL                 ; InOuter
    a2 = the name
    a3 = NULL                 ; Filename
    t0 = 2                    ; LoadFlags
    t1 = NULL                 ; Sandbox   (in the jal's delay slot)

Arguments five and six go in `$t0`/`$t1`, not on the stack: this build is
EABI, confirmed at `0x0017EA30`/`0x0017EA40` where the callee does
`move $s6, $t1` and `move $s4, $t0` before touching anything else, and spills
`$a1`/`$a2` into its OWN frame at `0xa8($fp)`/`0xac($fp)`. That is why the
cave's `sd $ra, 0x10($sp)` is safe -- the callee never reads its caller's
`0x10($sp)`.

Every failure degrades to the stock pick and nothing else:

* `gp-0x7cdc` still zero (the template parser has not run yet) -> `stock`.
* `StaticLoadObject` returns NULL -> `stock`. It cannot do anything else:
  `LoadFlags = 2` is never tested anywhere in the function (only `0x40` and
  `0x4000` are), there is no `appError` on the path, and both failure exits
  return `$s2`, which is zeroed in the prologue.
* `$s0` still 0 or -1 after the roll -> `RET_ZERO`, the game's own "" result.

The returned pointer is not re-cast. The game's parser passes its result
through `Cast<UClass>` (`0x001686C0`) and the cave deliberately does not,
because the cast is redundance rather than protection here:
`StaticLoadObject` only ever assigns its result from calls that take the
wanted class and filter on it (`StaticFindObject` at `0x00182430`, twice, and
the linker's export creator at `0x00164FE0`), so a non-NULL return is already
a `UClass*`.

TUPLE ORDER
-----------

**`words(preset)` yields two-tuples, `(va, word)`** -- not `(va, stock, new)`
and not `(va, new, stock)`. There is no stock value to carry: every word is
in RAM below the ELF load base, which is not part of the overlay image. The
one overlay word this feature touches is the hook, and it is delivered
separately from `HOOK_AT` / `HOOK_NEW` / `HOOK_STOCK` so it cannot be
confused with a cave word.

This is spelled out because it has already cost a whole feature once: a
module returning `(va, stock, new)` was unpacked as `(va, new, stock)`, which
wrote the stock value back, made the option a silent no-op, and passed every
check. `tests/run_tests.py` asserts the arity, asserts that no yielded address
is an overlay address at all, and asserts the hook row's stock is the real
stock word.

Why the hook can be a plain pnach row
-------------------------------------

A `.pnach` row is re-applied every vsync, so it dirties its 4 KB page sixty
times a second and PCSX2 throws away every recompiled block in that page each
time. The loadout mirror was broken by exactly this at `0x00273000` and had
to install its hook from a cold page instead (`rsemirror.ARM_AT`).

`0x003C9000` is not that kind of page, and the difference is structural
rather than a guess:

* Nine functions have a body in `0x003C9000..0x003C9FFF`. **None of the nine
  is in the engine's native-dispatch table** at `0x005BBC10..0x005BCFF0`
  (318 records of `{name=0, iNative=-1, Func, 0}`, 288 distinct functions).
  All nine have a static `jal` caller -- eight of them exactly one.
* The rejected page `0x00273000` holds eleven functions, and **nine of them
  ARE in that table** -- and those same nine have ZERO static `jal` callers,
  because the only thing that calls them is `jalr` out of the UnrealScript
  bytecode interpreter. That is what made the page hot during a load, and
  what makes this one cold. (The mirror's own note calls all eleven natives;
  nine is the exact count, the other two are ordinary functions with static
  callers. The conclusion is unchanged.)
* The hooked function has exactly one caller, `0x003867D0`, which is
  `R6Terrorist`'s template applier -- it writes `m_szUsedTemplate` (+0x988),
  `m_szPrimaryWeapon` (+0x994) and `m_szGrenadeWeapon` (+0x9A0). It runs once
  per terrorist, not once per frame. The call at `0x00386A7C` is
  unconditional: no branch in the 684 bytes before it jumps over it, so every
  terrorist rolls.

Carrying onto another pressing
------------------------------

`tcps2/revision.py` relocates every word this tool can write onto a rebuilt
overlay, and it refuses two things. A bare `lui` whose immediate is the top
half of an overlay address cannot be moved, because the bottom half lives in a
different instruction and is not recoverable from that word. And an address
whose own stock word is such a `lui` cannot even be SIGNED for, because
`relocate` verifies the stock word at the position it finds and a rebuilt data
segment legitimately changes that immediate (`tests_revision._rebuild` models
exactly that with `perturb_lui`).

**Both traps were walked into, in order, and the tests caught both.**

1. The first cave rebuilt `$at` itself with `lui $at, 0x005e` before entering
   `RET_EMPTY`. Unrelocatable by construction: the low half is in the GAME's
   `lb $v0, 0x4f90($at)`.
2. The second deleted that word and re-entered `0x003C9378` -- the hooked
   branch's delay slot -- to let the game load `$at`. That moved the same
   problem one level out: `0x003C9378` IS a `lui` of an overlay half, so it
   could never relocate as a jump target.
3. The third, shipped, tail needs no `$at` at all. It enters at `RET_ZERO`
   (`0x003C93A8`, `move $v0, $zero`) or `RET_CLASS` (`0x003C93F0`,
   `lw $v0, 0x18($s0)`) -- both ordinary words -- and replays the spill from
   the skipped delay slot.

Every address-bearing word left in the cave is now either a `lui`/`lw` PAIR
(`CLASSCLS`), a `lui` below the overlay base (the cave's own literals, which
do not move), or a `j`/`jal` the relocator re-encodes. The table gains exactly
three rows: `0x0017EA10`, `0x003C93A8` and `0x003C93F0` are the reachable
ones, plus the hook. **Re-run `tools/make_sigtable.py` when applying this.**

So: never put a bare `lui` of an overlay high half in a cave, and never jump
to one either. Load the pair, or re-enter a word that is not one.

The honest per-map risk
-----------------------

**The flashbang is safe everywhere. The molotov is not, and it is not
symmetric.**

`r6flashbanggadget` is an already-created `UClass` on every map -- present in
8 of 9 EE dumps, the ninth mid-load -- so the flashbang half is a hash hit
inside `StaticLoadObject` with no disc access at all.

The molotov is NOT resident on every map. Measured: present on ALCATRAZ_A and
SHIPYARD_A, and completely absent -- bytes, names and all -- on
IMPORT_EXPORT_B and two others. On those maps the name misses the object hash
and `StaticLoadObject` falls through to `ResolveName`, which may try to
demand-load the package through the `.LIN` reader. If that fails it returns
NULL and the cave takes `stock`, which is handled. If it HANGS, nothing in
the cave can help, and the retail game has never exercised that path: the
four molotov templates are only parsed on maps that carry the asset, which is
why the FName is absent from the others rather than merely unresolved.

That asymmetry is the entire reason `flash_only` is the recommended value and
the reason the default is `off`.

A find-only variant using `StaticFindObject` (`0x00182430`) directly would
remove the hang outright, and it was considered and not taken: the game only
calls it with `ANY_PACKAGE` on a conditional arm whose runtime predicate
(`gp-0x7418`) cannot be read without running the game, and with `ANY_PACKAGE`
it is not established that a dotted `Package.Class` name is resolved at all.
Using the call the game demonstrably makes for 48 of its own templates on
every map is the better bet than a call it makes only on a branch that may
never be taken.

Already-latent bug, hit more often
----------------------------------

`R6MolotovGrenade.SelfDestroy()` dereferences `m_pLight` unguarded, and
`m_pLight` is only ever assigned in `InitGrenadeForThrow()`, which the DROP
path never calls. So a terrorist shot dead mid-throw hits an accessed-None.

This is not new and it is not caused by the cave: it already ships live on
Alcatraz, and Alcatraz does not crash. The exposure is "the same latent bug,
more often" -- which is a real cost of the heavier presets and is why the
caution text names it.

Not established
---------------

* Nothing here has been played. Not one preset.
* Whether a terrorist whose template said `None.None` actually starts
  THROWING. `m_bHaveAGrenade` is a bool on `R6Terrorist` declared immediately
  after `m_szGrenadeWeapon`, and a live dump put it in the bitfield at
  `+0x95C`. It is set from UnrealScript, not natively: the template applier
  writes bits 1, 3, 4, 5, 6 and 7 of `+0x95C` and there is no store to
  `+0x95C` anywhere in the overlay that touches bit 2. So "the string
  switches his grenade AI on for free" is a live-RAM observation, not
  something the disassembly confirms. If it is wrong, the feature still
  works -- it just only changes WHICH grenade the 48 already-armed templates
  throw, instead of also arming the other 70.
* Whether the molotov's fire actually hurts anyone when a terrorist throws
  it. The four shipped templates prove the engine does it; nothing here
  measures the damage.
"""

from __future__ import annotations


class MolotovError(Exception):
    pass


#: `beq $s0, $zero, 0x003C9388` in PickGrenadeClass, where both the
#: "nothing matched" and "a class was picked" paths converge and `$s0` still
#: holds the raw `UClass*`.
HOOK_AT = 0x003C9374
HOOK_STOCK = 0x12000004
HOOK_NEW = 0x0803DB00           # j 0x000F6C00

#: The hooked branch's delay slot, `lui $at, 0x005e`. NOT a branch, so it
#: still runs harmlessly after the `j`. The cave does NOT re-enter here, and
#: this address is NOT in `stock_words()` -- a `lui` of an overlay high half
#: can never be relocated, as a jump target, a written word, or a registered
#: stock word. Checked against the image by the tests; never declared.
DELAY_AT = 0x003C9378
DELAY_STOCK = 0x3C01005E

CAVE = 0x000F6C00
CAVE_END = 0x000F6CF8           # 62 words: code plus the two literals
#: The two patchable dial words, at the end of the span.
CONST = 0x000F6FE0
CONST_END = 0x000F6FE8
SPAN_END = 0x000F7000
#: There is NO runtime state anywhere in this cave -- the roll is drawn fresh
#: from the engine's own `rand()` on every call and nothing is remembered --
#: so unlike the slow-motion and shrapnel-stagger caves every single word of
#: it belongs in the cheat file.
HAS_RUNTIME_STATE = False

#: Engine entry points the cave calls or re-enters.
RAND = 0x00146DF0               # the rand() PickGrenadeClass itself calls
STATICLOAD = 0x0017EA10         # UObject::StaticLoadObject
CLASSCLS = 0x00653A14           # gp-0x7cdc, cached UClass* for class 'Class'
RET_CLASS = 0x003C93F0          # builds Outer.Name "." Class.Name
RET_ZERO = 0x003C93A8           # `move $v0, $zero` -> builds ""
#: The head of that same "" path. Documented, never jumped to: its first
#: instruction is the one that needs `$at`, and the `lb`/`beqz` pair there is
#: dead in the shipped build because EMPTY_NAME holds a single NUL.
RET_EMPTY = 0x003C9388
EMPTY_NAME = 0x005E4F90
#: The spill in the skipped branch's delay slot, which the cave replays.
SPILL_AT = 0x003C9390
SPILL_WORD = 0xAFB10068         # sw $s1, 0x68($sp)
#: Considered and not used -- see the docstring. Recorded so the next person
#: does not have to find them again.
STATICFIND = 0x00182430         # UObject::StaticFindObject
CASTCLASS = 0x001686C0          # Cast<UClass>

#: The two literals the cave carries, and where they land.
STR_MOLOTOV = "R6Weapons.R6MolotovGadget"
STR_FLASHBANG = "R6Weapons.r6flashbanggadget"
STR_MOLOTOV_AT = CAVE + 0x00C0
STR_FLASHBANG_AT = CAVE + 0x00DC

#: The roll's denominator. `(rand() >> 5) & 0x3FF`, so 1024 is 100%.
ROLL_SCALE = 1024

PRESETS = ('off', 'flash_only', 'rare', 'mixed', 'heavy', 'molotov_only')
#: `off` is the PROFILE default, so an untouched profile emits nothing at all.
PRESET_DEFAULT = "off"
#: `flash_only` is the RECOMMENDED value, and it is not the default on
#: purpose: the flashbang is resident on every map and the molotov is not, so
#: the molotov half is the unproven one and the user opts into it.
PRESET_RECOMMENDED = "flash_only"

#: (P_MOLO, P_FLASH) out of 1024. P_FLASH is cumulative.
_CONST_VAS = (CONST + 0x00, CONST + 0x04)

_CONST = {
    "flash_only": (0, 256),         # molotov  0%,  flashbang 25%
    "rare": (51, 205),              # molotov  5%,  flashbang 15%
    "mixed": (154, 410),            # molotov 15%,  flashbang 25%
    "heavy": (307, 614),            # molotov 30%,  flashbang 30%
    "molotov_only": (256, 256),     # molotov 25%,  flashbang  0%
}

_VAS = (
    0x000F6C00, 0x000F6C04, 0x000F6C08, 0x000F6C0C,
    0x000F6C10, 0x000F6C14, 0x000F6C18, 0x000F6C1C,
    0x000F6C20, 0x000F6C24, 0x000F6C28, 0x000F6C2C,
    0x000F6C30, 0x000F6C34, 0x000F6C38, 0x000F6C3C,
    0x000F6C40, 0x000F6C44, 0x000F6C48, 0x000F6C4C,
    0x000F6C50, 0x000F6C54, 0x000F6C58, 0x000F6C5C,
    0x000F6C60, 0x000F6C64, 0x000F6C68, 0x000F6C6C,
    0x000F6C70, 0x000F6C74, 0x000F6C78, 0x000F6C7C,
    0x000F6C80, 0x000F6C84, 0x000F6C88, 0x000F6C8C,
    0x000F6C90, 0x000F6C94, 0x000F6C98, 0x000F6C9C,
    0x000F6CA0, 0x000F6CA4, 0x000F6CA8, 0x000F6CAC,
    0x000F6CB0, 0x000F6CB4, 0x000F6CB8, 0x000F6CBC,
    0x000F6CC0, 0x000F6CC4, 0x000F6CC8, 0x000F6CCC,
    0x000F6CD0, 0x000F6CD4, 0x000F6CD8, 0x000F6CDC,
    0x000F6CE0, 0x000F6CE4, 0x000F6CE8, 0x000F6CEC,
    0x000F6CF0, 0x000F6CF4,
    0x000F6FE0, 0x000F6FE4,
)

_WORDS = (
    # -- prologue -------------------------------------------------------
    0x27BDFFE0,  # addiu sp, sp, -0x20
    0xFFBF0010,  # sd    ra, 0x10(sp)
    0x0C051B7C,  # jal   0x00146DF0            rand()
    0x00000000,  # nop
    # -- roll = (rand() >> 5) & 0x3FF ------------------------------------
    0x00021942,  # srl   v1, v0, 5
    0x306303FF,  # andi  v1, v1, 0x3FF
    0x3C01000F,  # lui   at, 0x000F            below the overlay: PLAIN
    0x8C246FE0,  # lw    a0, 0x6FE0(at)        P_MOLO
    0x3C01000F,  # lui   at, 0x000F
    0x8C256FE4,  # lw    a1, 0x6FE4(at)        P_FLASH
    0x0064102A,  # slt   v0, v1, a0
    0x14400006,  # bnez  v0, want_molo
    0x00000000,  # nop
    0x0065102A,  # slt   v0, v1, a1
    0x14400007,  # bnez  v0, want_flash
    0x00000000,  # nop
    0x10000013,  # b     stock
    0x00000000,  # nop
    # -- want_molo  (0x000F6C48) ----------------------------------------
    0x3C06000F,  # lui   a2, 0x000F
    0x24C66CC0,  # addiu a2, a2, 0x6CC0        str_molo
    0x10000003,  # b     resolve
    0x00000000,  # nop
    # -- want_flash (0x000F6C58) ----------------------------------------
    0x3C06000F,  # lui   a2, 0x000F
    0x24C66CDC,  # addiu a2, a2, 0x6CDC        str_flash
    # -- resolve    (0x000F6C60) ----------------------------------------
    0x3C010065,  # lui   at, 0x0065            paired with the lw below
    0x8C243A14,  # lw    a0, 0x3A14(at)        UClass* 'Class' (gp-0x7cdc)
    0x10800009,  # beqz  a0, stock             parser has not run yet
    0x00000000,  # nop
    0x0000282D,  # move  a1, zero              InOuter  = NULL
    0x0000382D,  # move  a3, zero              Filename = NULL
    0x24080002,  # li    t0, 2                 LoadFlags = 2 (EABI arg 5)
    0x0C05FA84,  # jal   0x0017EA10            StaticLoadObject
    0x0000482D,  # move  t1, zero              Sandbox  = NULL (EABI arg 6)
    0x10400002,  # beqz  v0, stock             not found -> leave stock alone
    0x00000000,  # nop
    0x0040802D,  # move  s0, v0                ---- THE SUBSTITUTION ----
    # -- stock      (0x000F6C90) ----------------------------------------
    0xDFBF0010,  # ld    ra, 0x10(sp)
    0x27BD0020,  # addiu sp, sp, 0x20
    0x2402FFFF,  # li    v0, -1                the game's own sentinel
    0x12020005,  # beq   s0, v0, to_empty
    0x00000000,  # nop
    0x12000003,  # beqz  s0, to_empty
    0x00000000,  # nop
    0x080F24FC,  # j     0x003C93F0            RET_CLASS
    0x00000000,  # nop
    # -- to_empty   (0x000F6CB4) ----------------------------------------
    0xAFB10068,  # sw    s1, 0x68(sp)          replays SPILL_AT's delay slot
    0x080F24EA,  # j     0x003C93A8            RET_ZERO, no $at needed
    0x00000000,  # nop
    # -- str_molo   (0x000F6CC0) "R6Weapons.R6MolotovGadget" ------------
    0x65573652, 0x6E6F7061, 0x36522E73, 0x6F6C6F4D,
    0x47766F74, 0x65676461, 0x00000074,
    # -- str_flash  (0x000F6CDC) "R6Weapons.r6flashbanggadget" ----------
    0x65573652, 0x6E6F7061, 0x36722E73, 0x73616C66,
    0x6E616268, 0x64616767, 0x00746567,
    # -- the two dial words, patched per preset by words() --------------
    0x00000000,  # P_MOLO
    0x00000000,  # P_FLASH
)


def shares(preset: str = PRESET_RECOMMENDED):
    """(molotov, flashbang, stock) as percentages, for the card and the tests."""
    if preset == "off":
        return (0.0, 0.0, 100.0)
    if preset not in _CONST:
        raise MolotovError("no such terrorist-grenade preset: %r" % (preset,))
    molo, flash = _CONST[preset]
    if not 0 <= molo <= flash <= ROLL_SCALE:
        raise MolotovError(
            "preset %r is not a cumulative pair inside 0..%d: %r"
            % (preset, ROLL_SCALE, (molo, flash)))
    return (100.0 * molo / ROLL_SCALE,
            100.0 * (flash - molo) / ROLL_SCALE,
            100.0 * (ROLL_SCALE - flash) / ROLL_SCALE)


def words(preset: str = PRESET_DEFAULT):
    """[(va, word)] for the cave, with the preset's two dial words patched in.

    TWO-TUPLES, `(va, word)`. See the TUPLE ORDER section of the module
    docstring; there is no stock value because none of these addresses is an
    overlay word. The hook is NOT included -- it is the one overlay word this
    feature touches and it is delivered from `HOOK_AT` / `HOOK_NEW` /
    `HOOK_STOCK` so the two can never be confused.

    `off` returns [] so an untouched profile writes an empty cheat file.
    """
    if preset not in PRESETS:
        raise MolotovError("no such terrorist-grenade preset: %r" % (preset,))
    if preset == "off":
        return []
    shares(preset)                      # validates the pair
    const = dict(zip(_CONST_VAS, _CONST[preset]))
    out = []
    for va, w in zip(_VAS, _WORDS):
        if not (CAVE <= va < CAVE_END or CONST <= va < CONST_END):
            raise MolotovError("0x%08X is outside the molotov cave's span" % va)
        out.append((va, const.get(va, w)))
    return out


def stock_words():
    """{va: stock} for the overlay words this module touches. Exactly one.

    **`DELAY_AT` is deliberately NOT here**, even though registering it for
    documentation is the obvious thing to do. `revision.signature_addresses`
    builds a relocation signature for every entry in `stock_words`, and
    `0x003C9378`'s word is `lui $at, 0x005e` -- a `lui` of an overlay high
    half, which `relocate()` can never confirm, because it re-reads the stock
    word where a signature matches and a rebuilt data segment legitimately
    changes that immediate. Registering it made the whole option undeliverable
    on any other pressing. The delay slot is still pinned as a constant and
    still checked against the image by the tests; it just must not be
    declared as a word this tool knows the stock value of.
    """
    return {HOOK_AT: HOOK_STOCK}


def reads(word_at) -> bool:
    """True if `word_at(va)` shows the hook in place."""
    return word_at(HOOK_AT) != HOOK_STOCK


def card(prefix, group):
    from .model import CHOICE, Choice, Setting

    def _pct(p):
        m, f, _s = shares(p)
        return "About %d%% molotov, %d%% flashbang." % (round(m), round(f))

    return Setting(
        prefix + "terrorist_grenades", "Terrorists throw molotovs and flashbangs",
        CHOICE, PRESET_DEFAULT, group, pnach_only=True,
        choices=[
            Choice("off", "Off (as the game ships)",
                   "Terrorists throw whatever their template says, which for "
                   "most of them is nothing at all."),
            Choice("flash_only", "Flashbangs only (recommended)",
                   "About a quarter of terrorists get a flashbang and no one "
                   "gets a molotov. The only option that is safe on every "
                   "map -- see the warning."),
            Choice("rare", "Occasional molotov",
                   _pct("rare") + " Mostly still frags and empty hands."),
            Choice("mixed", "Mixed",
                   _pct("mixed") + " You will meet both most missions."),
            Choice("heavy", "Heavy",
                   _pct("heavy") + " Three in five terrorists throw "
                   "something unusual. Loud."),
            Choice("molotov_only", "Molotovs only",
                   _pct("molotov_only") + " The riskiest choice: no "
                   "flashbangs to fall back on, so on a map that does not "
                   "carry the molotov this does nothing at all."),
        ],
        help="The molotov is a finished, shipped terrorist weapon that only "
             "four of the game's 118 enemy templates ever hand out, so in "
             "practice you meet it on the Alcatraz maps and nowhere else. "
             "The flashbang is nearly as rare. This rolls a dice as each "
             "terrorist is created and hands him one instead of whatever his "
             "template said -- including the seventy templates that carry no "
             "grenade at all.\n\n"
             "It swaps the weapon at the moment the game chooses it, before "
             "the name is even written down, so the result is "
             "indistinguishable from a terrorist who was always meant to "
             "carry it. Nothing in the game's own data files is changed.",
        caution="\"Flashbangs only\" has been played (2026-09-28): enemies throw "
                "them often enough to notice. NO MOLOTOV PRESET has been "
                "tested in the running game.\n\n"
                "THE FLASHBANG IS SAFE EVERYWHERE; THE MOLOTOV IS NOT. The "
                "flashbang already exists on every map, so asking for one is "
                "a lookup that cannot fail. The molotov does NOT exist on "
                "every map: it was found on Alcatraz and Shipyard and was "
                "completely absent from Import/Export and two others. On "
                "those maps asking for it makes the game go and look for it "
                "on the disc. If that comes back empty the terrorist just "
                "keeps his normal grenade, which is handled -- but if it "
                "stalls instead, nothing here can rescue it. That is why "
                "\"Flashbangs only\" is the recommendation and why this ships "
                "switched off.\n\n"
                "The molotov also carries a bug the game already ships: a "
                "terrorist shot dead in the middle of throwing one touches a "
                "light that was never created. It happens on Alcatraz today "
                "and Alcatraz does not crash, so this is not new -- but the "
                "heavier presets will hit the same latent bug more often.\n\n"
                "Delivered as a PCSX2 cheat file, not written to the disc, "
                "because a code cave does not survive a level load. Save a "
                "fresh cheat file after changing this and restart the "
                "emulator so it is re-read.",
        confidence="experimental")

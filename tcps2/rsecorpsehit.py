"""Dead bodies have no hitbox. Bullets pass through them. Four bytes.

THE DEFECT, AND IT IS A CONSOLE REGRESSION
------------------------------------------

`R6Pawn.state Dead` calls `SetCollision(false, false, false)` -- twice, once in
`BeginState()` and once at the `Begin:` label. **The Xbox build passes `true`
for the first argument; the PlayStation 2 build passes `false`.** That one
argument is the whole bug.

`bCollideActors = false` takes the corpse out of the collision hash altogether.
In `AActor::SetCollision` (`0x001DF5F0`) the three bits are written at
`0x001DF924/34/44`, and then `0x001DF948` re-reads the *new* `bCollideActors`
and only calls the hash-add (`XLevel(+0x2e4)->Hash(+0x3a74)`, vtable `+0x10`)
if it is set. It never touches `bProjTarget` at all -- which is why the
`bProjTarget = true` on the line above it is dead code as shipped.

And `bProjTarget` is precisely what the bullet path tests. The per-pellet
impact handler at `0x003F157C` evaluates

    bProjTarget || bWorldGeometry || m_bIsSoftBody

on the actor it hit and, failing all three, branches past the entire actor-hit
path. A corpse fails all three, so the pellet does not register -- no impact,
no blood, no sound.

The shipped `Dead:Begin:` block decodes to::

    Acceleration = vect(0,0,0); Velocity = vect(0,0,0);
    m_bWantsToPeek = false;
    bProjTarget = true;                        <- inert, SetCollision ignores it
    SetCollision(false,false,false);           <- THE BUG
    SetCollisionSize(1.5*default.CollisionRadius, 1.0*default.CollisionHeight);
    SetTimer(0.5,false);
    ...

There are exactly four `bProjTarget` writes in the container: `Dead:Begin:`
(true), `Dead.Timer` (false, at t+0.5 s), `R6Died` (false) and
`R6DeadEndedMoving` (false). The last three are what re-kill the corpse after
`Dead:Begin:` has set it, so three of them have to turn round as well.

WHAT THE EDIT DOES
------------------

Four one-byte opcode swaps, `EX_False (0x28)` -> `EX_True (0x27)`. Both opcodes
are one byte on disk **and** one byte in memory, so neither the disk length nor
`ScriptSize` moves and no jump target is re-based. No new name, import or
export is introduced, and no object reference changes, so the order in which
the package first touches its own exports is untouched.

===================================  ==========================================
site                                 why
===================================  ==========================================
`Dead:Begin:` SetCollision arg 1     required -- puts the corpse back in the hash
`Dead.Timer` bProjTarget             required -- otherwise it dies again at t+0.5 s
`R6DeadEndedMoving` bProjTarget      required -- otherwise it dies when the body settles
`Dead.BeginState()` SetCollision     belt and braces, same call on the other entry
===================================  ==========================================

`R6Died`'s `bProjTarget = false` is deliberately left alone: `Dead:Begin:` runs
straight afterwards and sets it back.

Each site is located by a 25-byte window that is **unique in the file** and
byte-identical in `COMMON.LIN`, `COMMONOFF.LIN` and `COMMON_SS.LIN`, with the
opcode at index 12. Nothing here uses a stored offset -- an offset edit has
corrupted a healthy file in this project before.

WHAT DOES *NOT* CHANGE: THE BODY IS STILL NOT SOLID
---------------------------------------------------

Worth stating plainly, because it is the obvious fear. Movement blocking is
decided by `SourceActor->IsBlockedBy(this)` reading `bBlockActors` and
`bBlockPlayers`, and both of those stay `false`. **Nothing can be physically
blocked by a corpse** -- no blocked doorways, no tripping over bodies, no
change to pathing.

This engine revision has no `bBlockZeroExtentTraces` / `bBlockNonZeroExtentTraces`
split; `AActor::ShouldTrace` (`0x001DBDC0`, vtable `+0xBC`) takes only
`(this, SourceActor, TraceFlags)` and the extent reaches only `prim->LineCheck`
(`0x0037F0A8`), so it decides *where* a hit lands, never *whether* the actor is
considered at all. What this build has instead is Ubisoft's trace-purpose bits,
and `TRACE_OnlyProjActor` (`0x20`) accepts on `bProjTarget || (bBlockActors &&
bBlockPlayers)` -- so setting `bProjTarget` alone is exactly the "shootable but
not solid" state, and it is what Xbox ships.

THE BLOOD COMES FOR FREE
------------------------

The visible impact effect is native and is **not** gated on the victim being
alive. At `0x003F21AC` the code loads `m_pHitEffect` (`Material+0x50`, a
`class<R6WallHit>`) from the hit surface's material and calls the spawner at
`0x003F08C0` with the hit actor, location and normal -- *before* the
`m_bBulletGoThrough` penetration test at `0x003F21BC`. So once the corpse is
traceable again, a flesh impact appears from the body's own skin material with
no further edit.

KNOWN LIMITATIONS
-----------------

* **The hitbox is an upright cylinder on a prone body.** The corpse keeps
  1.5x the default radius and the full default height, centred on the actor's
  Location, while the mesh lies flat. Shots into that pillar register; shots
  at the far end of the visible body may miss, and shots into the air above it
  may hit. Per-bone tracing cannot rescue it -- TraceFlags `0x10000` is set
  from the **tracing** actor's `m_bDoPerBoneTrace` (`0x0026EFC0`,
  `0x002174AC`), not the target's. This is what Xbox ships too.
* **AI can no longer see through bodies.** `R6Trace(..., TF_TraceActors, ...)`
  maps to TraceFlags `0xBF`, which includes `TRACE_OnlyProjActor`, so corpses
  become line-of-sight and cover obstructions. Retail Xbox behaviour, but it
  is a real change: an enemy may decline a shot through a body.
* **Touch and trigger events resume.** Back in the hash means the corpse
  generates Touch/UnTouch against volumes and triggers, so a body that falls
  inside an objective zone could fire it. Xbox tolerates this, so the level
  data presumably does.
* **Online only:** after two seconds multiplayer corpses get `bHidden = true`,
  and `bHidden` only rejects traces under TraceFlags `0x2000`, which `0xBF`
  does not include -- so online you would get an invisible but shootable body.
  Single player never hides them (`Dead.Timer`'s hide is behind
  `Level.NetMode != NM_Standalone`).
* Bodies persist for the whole single-player level -- there is **no**
  `LifeSpan` assignment anywhere in the container and no destroy timer -- so
  trace candidates accumulate as a level goes on.

NOT ESTABLISHED
---------------

* Never played.
* No savestate in hand contained a corpse, so the runtime flag values were
  never read out of a running game; the whole corpse path is established from
  bytecode plus the native code above.
* The PS2 `R6TakeDamage` body was not located, so whether its `!IsAlive()`
  early return survives is unconfirmed. That affects only the *script* blood
  decal, not the native impact effect described above.
* There is no Karma in this build at all -- `SpawnRagDoll`, `m_bUseRagdoll`,
  `KAddImpulse` and `SetPhysics` are all absent, and `R6Died` calls
  `InitDeathAnim()` instead -- so no physics path is touched by any of this.
"""

from __future__ import annotations

H = bytes.fromhex


class CorpseHitError(Exception):
    pass


#: Byte at this index inside each window is the one that flips.
_OP = 12

EX_FALSE = 0x28
EX_TRUE = 0x27

#: (name, stock window). Each is unique in the file and identical in all three
#: COMMON packages. The opcode sits at index `_OP`; everything either side is
#: there only to make the window unique.
SITES = (
    ("dead_begin_setcollision",
     H("01570428142d01f20527610628282816611bab1e0000c03f02")),
    ("dead_beginstate_setcollision",
     H("73746174652e2e2e0016610628282816611bab1e0000c03f02")),
)

#: DELIBERATELY NOT PATCHED, and the reason is a regression this module
#: shipped with on 2026-09-28 and then walked back the same night.
#:
#: `Dead.Timer` (plain 0x000F3A36) and `R6DeadEndedMoving` (plain 0x000FB1D9)
#: both clear `bProjTarget`. Setting them kept a corpse a valid bullet target
#: for as long as it lay there -- and because `Dead:Begin:` also gives it
#: 1.5x radius at FULL standing height, that is a 150-unit invisible column
#: where the body fell, while the mesh lies flat. `FireBullets` stopped on
#: that column, so a body on the floor SHIELDED a live enemy standing behind
#: it. Measured in play: a full 30-round magazine into an enemy at close
#: range with a corpse at his feet registered nothing, on a stock wound pool
#: where one torso hit kills.
#:
#: Left alone, the shipped sequence is: `Dead:Begin:` sets `bProjTarget`
#: (stock, always did), `Dead.Timer` clears it half a second later, and
#: `R6DeadEndedMoving` clears it again when the body settles. So a fresh
#: corpse is shootable for that half second and is transparent afterwards.
#:
#: Transparent, not solid: an actor failing `FireBullets`' three target tests
#: at 0x003F157C..0x003F15B0 branches to 0x003F2578, which is
#: `lw $s2,($s2)` / `bne $s2,$zero` -- the hit-chain walk. The pellet carries
#: on to whatever is behind. Keeping `SetCollision(true, ...)` is what puts
#: the corpse in the hash in the first place, and that is all this module
#: now does.
#:
#: It also restores AI vision: `R6Trace(..., TF_TraceActors)` is flags 0xBF,
#: which includes TRACE_OnlyProjActor (0x20), and `ShouldTrace` accepts on
#: `bProjTarget || (bBlockActors && bBlockPlayers)`. With all three clear a
#: corpse is skipped by those traces too, so enemies can see and shoot past
#: bodies again.
PROJTARGET_LEFT_STOCK = (
    ("dead_timer_projtarget",
     H("a602004b000000142d01f205280749009b393a19018f050001")),
    ("dead_ended_moving_projtarget",
     H("77000083010000142d01f205280781019b393a19018f050001")),
)

#: Where they sit in a pristine COMMON.LIN, for the tests only -- the edit
#: itself never uses an offset.
KNOWN_OFFSETS = (0x000F38FC, 0x000F3BF5)

#: where the two untouched bProjTarget writes sit, for the tests
STOCK_PROJTARGET_OFFSETS = (0x000F3A36, 0x000FB1D9)


def _patched(win: bytes) -> bytes:
    return win[:_OP] + bytes((EX_TRUE,)) + win[_OP + 1:]


for _n, _w in SITES + PROJTARGET_LEFT_STOCK:
    if len(_w) != 2 * _OP + 1 or _w[_OP] != EX_FALSE:
        raise CorpseHitError("bad window for %s" % _n)
del _n, _w


def _find(plain: bytes, win: bytes, name: str) -> int:
    """The one offset of `win`, or -1 if the file already carries it patched."""
    n = plain.count(win)
    if n == 1:
        return plain.index(win)
    if n == 0 and plain.count(_patched(win)) == 1:
        return -1
    raise CorpseHitError(
        "%s: expected exactly one stock window, found %d stock and %d patched"
        % (name, n, plain.count(_patched(win))))


def reads(plain: bytes) -> bool:
    """True if this file already carries all four sites patched."""
    try:
        return all(_find(plain, w, n) == -1 for n, w in SITES)
    except CorpseHitError:
        return False


def apply(plain: bytes, enable: bool = True):
    """All four sites. Returns (plain, changed). The length never moves."""
    if not enable:
        return plain, 0
    out = bytearray(plain)
    changed = 0
    for name, win in SITES:
        at = _find(bytes(out), win, name)
        if at < 0:
            continue
        if out[at + _OP] != EX_FALSE:
            raise CorpseHitError("%s: not EX_False at the flip" % name)
        out[at + _OP] = EX_TRUE
        changed += 1
    if len(out) != len(plain):
        raise CorpseHitError("length moved")
    return bytes(out), changed


def revert(plain: bytes):
    """Put the shipped bytes back. Returns (plain, changed)."""
    out = bytearray(plain)
    changed = 0
    for name, win in SITES:
        new = _patched(win)
        if out.count(new) == 1:
            at = bytes(out).index(new)
            out[at + _OP] = EX_FALSE
            changed += 1
    return bytes(out), changed


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "corpse_hitbox", "Dead bodies can still be shot", BOOL,
        False, group, confidence="experimental", touches="data",
        help="Shoot a body on the floor and the rounds go straight through "
             "it -- no impact, no blood, no sound.\n\n"
             "The PlayStation 2 version removes a corpse from collision "
             "entirely the moment it dies. The Xbox version does not, and the "
             "difference is a single argument in the death code. This puts "
             "that back, so a man you have just dropped still takes hits and "
             "bleeds.\n\n"
             "It lasts about half a second, which is the window while the body "
             "is still falling. After that the game stops treating it as a "
             "target and your rounds pass through again. That is deliberate: "
             "a body that stays a target is an invisible pillar standing where "
             "it died, and it will soak the shots you meant for the man behind "
             "it.\n\n"
             "Bodies never become solid. You cannot trip over one or be "
             "blocked by one in a doorway.",
        caution="Played 2026-09-28.\n\n"
                "An earlier version of this option kept bodies shootable for "
                "as long as they lay there, and that cost a mission: a full "
                "magazine into an enemy standing behind a corpse registered "
                "nothing. If you ever see rounds vanishing into empty air near "
                "a body, turn this off and say so.\n\n"
                "While the window is open the target area is an upright "
                "cylinder where the man fell rather than the shape of the body "
                "on the floor, so hits near the middle register and hits at "
                "the feet may not.")

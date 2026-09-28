"""How hard your team shoots: the Rainbow AI trigger hold.

Two words. That is the whole feature -- there is no cave, and there does not
need to be one.

WHAT THE TWO SIDES ACTUALLY DO
------------------------------

They are not the same code with different numbers. They are two different
implementations living at two different layers, and only one of them is in
the overlay.

The TERRORIST fire loop is UnrealScript: `R6TerroristAI.state Attack`, label
`Fire:`. It holds the trigger with explicit latent sleeps --
`Sleep(RandRange(0.2, 1.5))` on a full-auto weapon, then
`Sleep(RandRange(0, 0.5))` -- or, on a non-auto weapon, `rand(4)+2` separate
taps of `RandRange(0.1, 0.2)`. `ATTACK_SprayFireNoStop` (mode **4** on
console; the PC build numbers it 3) additionally stops refreshing `Focus`
while the target is unseen, so the terrorist keeps shooting the last place he
looked. That is the door-shooting.

The RAINBOW fire loop is NATIVE, and it has no spray concept at all.
`R6RainbowAI` declares no `m_eAttackMode`, no `m_bSprayFire` and **no attack
state** -- 21 states, none of them combat. Firing is a timer in
`R6RainbowAI::Tick` at **0x003BDA20**, decoded word by word:

    Rate    = m_fAttackTimerRate    (+0x558)   measured 0.5 s, every instance
    Counter = m_fAttackTimerCounter (+0x55C)
    Burst   = m_fFiringAttackTimer  (+0x560)   measured 0.10/0.15/0.20/0.25
    bFire   (+0x371)  Controller.bFire
    Enemy   (+0x3D0)  Controller.Enemy

    Counter += DeltaTime
    if (Counter < Rate) goto STOPCHECK
    Counter = fmod(Counter, Rate)                  # cycle boundary
    if (Enemy || bFire) ProcessEvent(AttackTimer)   # the script event
    if (bFire) { Burst = ((rand() % 6) + 1) / 20.0; goto DONE }
  STOPCHECK:
    if (!bFire) goto DONE
    if (Counter < Burst) goto DONE
    ProcessEvent(StopAttack)                       # -> StopFiring()
  DONE:
    Super::Tick(DeltaTime)

So a teammate holds the trigger for `Burst` seconds out of every `Rate`
seconds. Stock that is a mean of 0.175 s out of 0.5 -- a **35% duty cycle**,
which is the two-and-three-round tapping you hear.

WHY THE PACKAGE DEFAULT IS A RED HERRING
----------------------------------------

The leaked PC 1.56 `R6RainbowAI` ships `m_fAttackTimerRate=0.500000` and
`m_fFiringAttackTimer=0.200000` in `defaultproperties`, and neither float is
ever assigned in UnrealScript in either build. The 0.5 survives and is what
every live instance reads. **The 0.2 does not**: the native tick above
overwrites it at every cycle boundary with `((rand()%6)+1)/20`. So the burst
length is not a data value at all on PS2 -- it is three literals in the
overlay, and two of them are enough.

    0x003BDAEC  addiu a0,zero,6   the modulus M
    0x003BDAF0  lui   v1,0x41A0   the divisor, 20.0f -- LEFT ALONE
    0x003BDB04  addiu v0,v0,1     the floor term K

Burst = ((rand() % M) + K) / 20 seconds. Keeping the divisor at 20 keeps the
quantum at 0.05 s and keeps both edits to a single `addiu` immediate.

THE HALF-SECOND CLIFF, WHICH IS THE ONLY REAL TRAP
--------------------------------------------------

`Burst` must stay **below** `Rate`. Read the tick again: `Counter` is reset by
`fmod` at every boundary, so if `Burst >= Rate` the `Counter < Burst` test can
never fail and `StopAttack` never fires mid-cycle. Control then falls to the
boundary, where `AttackTimer` sees `bFire == 1`, takes its `else` branch and
calls `StopFiring()` anyway -- and the re-roll is skipped. The result is fire
one cycle, silent the next: a **50% duty cycle, less aggressive than 0.45**.

So `M + K - 1 <= 9` is a hard ceiling, not a taste. Every preset below obeys
it and `words()` refuses anything that does not.

WHY THE GAP IS NOT OFFERED AS A DIAL
------------------------------------

`Rate` is reachable -- it is a class default in the package, like the edits
`rseaihunt` and `rseaicover` make. It is deliberately not exposed. `Rate` is
not just the pause between bursts; it is how often `AttackTimer` runs, and
`AttackTimer` is also where a teammate notices his target died, notices his
clip is empty and reloads, and re-checks line of sight. Raising it to buy
longer bursts buys a teammate who takes up to that long to reload or to stop
shooting a corpse. Lowering it lowers the burst ceiling with it. The shipped
0.5 is the right number and moving it only trades.

WHAT THIS DOES ABOUT SHOOTING WHERE YOU WERE
--------------------------------------------

Nothing directly, and it does not need to. The console `AttackTimer` gates
each burst on `AClearShotIsAvailable(enemy, ...)` -- a per-burst line-of-sight
trace that the PC build does not have; PC called `SetRateOfFire(ROF_FullAuto)`
there instead, and `SetRateOfFire` does not exist in the console tree at all.
But that gate is consulted **only at the cycle boundary**, never mid-burst,
and `event EnemyNotVisible` ignores the first 0.5 s of lost sight
(`if(Level.TimeSeconds - LastSeenTime < 0.5) return;`). So a burst already in
progress runs to completion through a target ducking into cover.

Lengthening the burst is therefore exactly the mechanism that produces the
few extra rounds into your last position -- and it is self-limiting, because
the burst cannot exceed 0.45 s and the grace window is 0.5 s. Teammates get a
tail, not a licence to empty a magazine into a wall.

FRIENDLY FIRE: MEASURED SAFE, AND WHY
-------------------------------------

The bullet trace native `0x003F1180` aborts damage at 0x003F1E34 on
`IsFriendly(victim, shooter)` -- `0x0023C100`, decoded as
`(victim->m_iFriendlyTeams & (1 << shooter->m_iTeam)) || same team` -- unless
`m_bCanFireFriends` is set. That flag and `m_bCanFireNeutrals` are the bits
the trace extracts from `+0x3BE`, the third byte of `Pawn`'s bool bitfield at
`+0x3BC`, and Rainbow's defaults leave both clear. Rainbow carries
`m_iTeam = 2` and `m_iFriendlyTeams = 12` (bits 2,3 = Alpha + Bravo), so
`1 << 2 = 4` is inside 12: **a teammate's round cannot damage you or another
teammate, however many of them there are.**

The exception is `rseff`. Its `noside` regions widen both enemy masks to
include bit 4 and put the marked player on team 4, at which point he IS a
valid target and more rounds in the air is more rounds that can find him.
That is a compounding risk, not an independent one, and the card says so.

AMMUNITION
----------

Stock, this costs nothing: `m_bUnlimitedRainbowMagazines` pins every AI
weapon at `m_iCurrentNbOfClips = 1` with `m_bUnlimitedClip` set, and
`R6Weapons::execNativeServerFireBullet` (0x003f0a40) never reaches `clips--`.
Teammates reload forever.

With `ai_finite_ammo` on it costs real magazines, and roughly doubles the
burn at the top preset. That is the one combination worth thinking about
before playing, and the presets are ordered so the aggressive ones are the
ones the caution names.

NOTHING CAPS THE BURST BUT THE MAGAZINE
---------------------------------------

The one thing that could have made this feature inert is a mechanical
three-round limiter. It is not that.

`eRateOfFire` is `ROF_Single 0, ROF_ThreeRound 1, ROF_FullAuto 2`, and
`GetNbOfRoundsForROF()` returns `m_iNbBulletsInWeapon` -- the whole magazine --
for `ROF_FullAuto`. `m_iNbOfRoundsInBurst` is animation state and gates
nothing. `state NormalFire`'s `Timer()` re-tests only
`m_iNbOfRoundsToShoot > 0 && Controller.bFire == 1`, so the burst ends on
trigger release or an empty clip and nothing else.

Measured: `m_eRateOfFire` reads **2 on every AI weapon in every dump**, and
`m_iNbOfRoundsToShoot` reads 21 and 25 live -- the remaining clip, not 3.
`ROF_ThreeRound` is unreachable dead code on console: no class default is 1
and `SetRateOfFire` does not exist. Every one of the 544 squad kits across the
96 mission INIs carries an SMG, assault rifle or LMG, so every AI primary is
full-auto; no teammate ever carries a sniper rifle as a primary.

Rounds per hold is `1 + floor(H / m_fRateOfFire)` -- the first round fires
immediately in `StartFiring()`, the rest on a repeating `SetTimer`. For the
`SubMP5SD5` (0.075 s/shot; the most common AI primary, 146 of 544 kits):

    stock      0.05-0.30 s -> 1-5 rounds
    steady     0.15-0.35 s -> 3-5
    aggressive 0.25-0.45 s -> 4-7
    relentless 0.35-0.45 s -> 5-7

Faster weapons give more: `AssaultFAMASG2` (0.0545) gives 1-6 stock and 7-9 at
`relentless`. Treat every figure as +/-1: the hold clock and the shot clock are
independent accumulators and are not phase-locked.

A FULL MAGAZINE IN ONE PULL IS NOT REACHABLE -- BUT THE VOLUME IS
-----------------------------------------------------------------

Emptying a 30-round magazine in a single hold needs about 2.2 s, and the
attack cycle caps a hold at 0.45 s. So the terrorist's one-long-pull magazine
dump cannot be reproduced, and this module does not claim to.

What is reproduced is the weight of fire. Over a three-second engagement a
`relentless` teammate spends 6 x 0.40 = 2.4 s on the trigger -- about 32
rounds from an MP5SD5, a magazine's worth, delivered as six pulls instead of
one. Stock spends 6 x 0.175 = 1.05 s, about 14 rounds. The sustained rate
matches the terrorist's (80% duty against 77%); only the rhythm differs.

NOT ESTABLISHED
---------------

* `AClearShotIsAvailable` is `native(2222)` with no body in either source tree
  and no comment at either call site, so whether it considers friendlies as
  well as geometry is unknown. It does not matter for safety (below) but it
  does mean the stale-decision window is what lengthens here.
* Whether a friendly in the path absorbs the round or it passes through is
  `rsepenetrate`'s territory; the damage abort at 0x003F2584 was not traced
  far enough to say.
* Which overlay split-screen co-op loads. If it loads MP.SOZ these two rows
  land on unrelated code -- see the last bullet.
* MP.SOZ is a different build -- it shares 1.42% of its words with SP.SOZ and
  holds unrelated code at all three addresses. Like every other pnach module
  in this project, this is SP.SOZ only.
"""

from __future__ import annotations


class AiFireError(Exception):
    pass


#: `addiu a0,zero,6` -- the modulus fed to `div v0,a0`, whose remainder is the
#: random part of the burst length. Read back from the pristine SP.SOZ.
MOD_AT = 0x003BDAEC
MOD_STOCK = 0x24040006

#: `addiu v0,v0,1` -- the floor added to that remainder.
FLOOR_AT = 0x003BDB04
FLOOR_STOCK = 0x24420001

#: `lui v1,0x41A0` -- the 20.0f divisor. Never written; listed so the stock
#: word is registered and a disc carrying anything else is noticed.
DIV_AT = 0x003BDAF0
DIV_STOCK = 0x3C0341A0
#: The quantum the divisor implies. Burst lengths are whole multiples of it.
QUANTUM = 1.0 / 20.0

#: `m_fAttackTimerRate`, measured 0.5 s on 15 live R6RainbowAI instances
#: across 8 EE dumps, and the PC 1.56 class default. The burst must stay
#: strictly below it -- see the docstring's cliff section.
RATE = 0.5
#: `M + K - 1`, the longest burst a preset may roll, in quanta.
MAX_QUANTA = 9

#: (modulus, floor). Burst = ((rand() % M) + K) / 20 seconds.
PRESETS = ("stock", "steady", "aggressive", "relentless")
PRESET_DEFAULT = "stock"
_PRESET = {
    "stock":      (6, 1),
    "steady":     (5, 3),
    "aggressive": (5, 5),
    "relentless": (3, 7),
}


def envelope(preset: str):
    """(shortest, longest, mean, duty) in seconds / fraction, for a preset."""
    if preset not in _PRESET:
        raise AiFireError("no such trigger-hold preset: %r" % (preset,))
    m, k = _PRESET[preset]
    lo, hi = k * QUANTUM, (m - 1 + k) * QUANTUM
    mean = (lo + hi) / 2.0
    return lo, hi, mean, mean / RATE


def words(preset: str = PRESET_DEFAULT):
    """[(va, word)] -- the two `addiu` immediates, and nothing else.

    Returns an empty list for "stock" so that selecting it emits no rows at
    all rather than writing the shipped words back over themselves every
    vsync.
    """
    if preset not in _PRESET:
        raise AiFireError("no such trigger-hold preset: %r" % (preset,))
    if preset == "stock":
        return []
    m, k = _PRESET[preset]
    if not 1 <= m <= 0x7FFF or not 1 <= k <= 0x7FFF:
        raise AiFireError("modulus and floor must be positive 16-bit values")
    if m + k - 1 > MAX_QUANTA:
        raise AiFireError(
            "preset %r rolls up to %.2f s, at or past the %.2f s attack cycle; "
            "past the cycle the stop test can never fire and the duty cycle "
            "HALVES" % (preset, (m + k - 1) * QUANTUM, RATE))
    return [(MOD_AT, (MOD_STOCK & 0xFFFF0000) | m),
            (FLOOR_AT, (FLOOR_STOCK & 0xFFFF0000) | k)]


def reads(word_at) -> str:
    """Which preset `word_at(va)` shows in place, or "" if nothing known is."""
    if word_at(MOD_AT) >> 16 != MOD_STOCK >> 16:
        return ""
    if word_at(FLOOR_AT) >> 16 != FLOOR_STOCK >> 16:
        return ""
    m = word_at(MOD_AT) & 0xFFFF
    k = word_at(FLOOR_AT) & 0xFFFF
    for name, mk in _PRESET.items():
        if mk == (m, k):
            return name
    return ""


def card(prefix, group):
    from .model import CHOICE, Choice, Setting

    return Setting(
        prefix + "ai_trigger_hold", "How hard your team shoots", CHOICE,
        PRESET_DEFAULT, group, pnach_only=True,
        choices=[
            Choice("stock", "Stock (short taps)",
                   "As shipped. One to five rounds a pull, a third of the "
                   "time."),
            Choice("steady", "Longer bursts",
                   "Three to five rounds. Mainly removes the single taps."),
            Choice("aggressive", "Aggressive",
                   "Four to seven rounds, and twice the stock volume of "
                   "fire."),
            Choice("relentless", "As hard as the terrorists",
                   "Five to nine rounds a pull, on the trigger 80% of the "
                   "time -- the sustained rate a spraying terrorist puts "
                   "out."),
        ],
        help="Your teammates tap the trigger; terrorists lean on it. This is "
             "why, and it is one number.\n\n"
             "A teammate runs an attack cycle every half second and holds the "
             "trigger for part of it. Stock that part averages 0.175 s, so "
             "about a third of the time -- one to five rounds, then a wait. A "
             "terrorist spraying on full auto holds for 0.2 to 1.5 s with "
             "almost no pause, roughly 77% of the time. The top preset here "
             "puts a teammate at 80%.\n\n"
             "One long magazine dump is not on offer: the half-second cycle "
             "caps a single pull at 0.45 s, and stretching the cycle would "
             "also delay the moment a teammate notices he needs to reload or "
             "that his target is already dead. What you get instead is the "
             "same weight of fire in more frequent pulls -- about a magazine "
             "over a three-second firefight rather than fourteen rounds.\n\n"
             "The line-of-sight check happens once per cycle, before the "
             "burst, never during it -- so a longer hold is also what makes a "
             "teammate put a few more rounds into the spot you just left. "
             "That tail cannot run past 0.45 s.",
        caution="Not yet played.\n\n"
                "Stock, this cannot hurt anyone. An AI teammate is spawned "
                "with friendly fire switched off at the bullet, so his rounds "
                "are discarded before they do damage to you or to each other, "
                "however many there are. It is safe to turn up.\n\n"
                "That stops being true with the friendly-fire options on. Once "
                "a marked player is on a team both sides read as hostile, more "
                "rounds in the air are more rounds that can find him -- and "
                "nothing re-checks the line of fire once a burst has started.\n\n"
                "With 'AI teammates run out of ammunition' on, the aggressive "
                "presets roughly halve how long a loadout lasts. Pair them "
                "with the sidearm option: a teammate down to his pistol is "
                "unaffected by this setting, because a pistol fires one round "
                "per pull however long the trigger is held.",
        confidence="experimental")

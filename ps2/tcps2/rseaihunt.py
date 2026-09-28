"""Terrorists that hunt you, and grenades they will throw at close range.

The hunt is not new behaviour -- the game already ships it
--------------------------------------------------------

`R6TerroristAI` has a state `HuntRainbow`, and its whole loop is

    SetEnemy(GetClosestEnemy())
    MoveTarget = FindPathToward(Enemy)
    GotoStateMovingTo(..., MT_DontCheckLeave)
    Sleep(1.0); repeat

`GetClosestEnemy()` is a raw distance sweep over every `R6Rainbow` actor:
**no line-of-sight test, no sight radius, no range cap and no memory**. So a
terrorist in this state always knows where you are, and `FindPathToward` is a
full navigation-graph search, so it comes to you from anywhere on the map.

`R6TerroristAI.NoThreat` ends in a gate and then a switch, and the gate is
the part that matters:

    if (m_bSpawnedByWave) {
        m_pawn.m_bAllowLeave = True;
        GotoStateAttackActionSpot(None, None);      <- case_wave
    } else switch (m_pawn.m_eStrategy) {
        0: GotoState('PatrolPath')                  <- case_patrolpath
        1: GotoState('PatrolArea')                  <- case_patrolarea
        2: GotoState('GuardPoint')                  <- case_guardpoint
        3: GotoState('HuntRainbow')
        default:                                    (STRATEGY_Test, unused)
    }

The switch has exactly those four arms -- there is no fifth to find. The
shipped default is 2 and no level overrides it: 98 of 98 live terrorists
across four EE dumps read `m_eStrategy == 2`, and the property name is absent
from all 6,270 package name tables in the 60 per-level containers, so no
placed actor could carry an override even in principle. That makes
`case_patrolpath` and `case_patrolarea` dead arms in practice, and "the ones
standing guard" all but identical to "every enemy". The one shipped writer of
3 is `R6Terrorist.StartHunting`, called only when a single terrorist is left
alive -- and itself vetoed by a per-zone `m_DZone.m_bHuntDisallowed`, which is
set on a third to a half of the zone actors on a level.

**The gate is why some enemies never hunt.** `m_bSpawnedByWave` is a
write-once latch on the CONTROLLER, never cleared, with two writers:

  * `AR6DZoneWave::SpawnATerrorist` sets it NATIVELY and unconditionally at
    `0x0040AD5C` (`controller+0x554 |= 0x20`) the instant a wave builds a
    terrorist, then drives `GotoStateAttackActionSpot(None, None)` by name
    through `ProcessEvent` at `0x0040AD84` -- which pre-empts the controller's
    `auto state Configuration` before its `Begin:` runs a single instruction.
    So a wave-RELEASED enemy is latched from birth and lands directly in
    `AttackActionSpot`; it never reaches the switch even once.
  * `R6TerroristAI.GotoStateAttackActionSpot` sets it in script when the
    pawn's deployment zone is an `R6DZonePoint` tied to a wave. That catches
    the enemies the DESIGNERS placed on those same wave spawn points: they
    hunt at level start, then latch the first time they engage, and hold a
    spot forever after.

A latched controller skips the switch entirely and goes to
`AttackActionSpot`, which walks it to a fixed spot and holds it there. On a
stock disc that is 47 of 98 live terrorists (48%) across four EE dumps --
and all 17 of the terrorists caught sitting inside `NoThreat` at dump time.
`case_wave` repoints that arm at `HuntRainbow` too, which is why it belongs
to BOTH settings rather than only to "every enemy": a latched enemy has no
authored patrol to preserve.

It also makes the strategy byte moot for those enemies, which is worth
knowing before anyone tries to reach them any other way.
`AR6DeploymentZone::InitTerrorist` computes a wave enemy's `m_eStrategy`
from the SPAWN POINT's flags at `0x00386B88` -- `m_bHuntFromStart &&
!m_bHuntDisallowed` gives 3, else the zone class decides -- and then the
latch means the switch never reads it. `R6Terrorist.StartHunting` has the
same problem: it writes 3 and calls `GotoStateNoThreat`, which for a latched
controller just bounces it back to `AttackActionSpot`.

What it costs, beyond the note below: repointing `case_guardpoint` removes
the only route a sniper has into the `Sniping` state at level start, because
`GuardPoint` is where `m_ePersonality == PERSO_Sniper` is tested. Snipers
charge instead. `EnemyNotVisible` can still put one back into `Sniping` after
it has engaged and lost you, so they are not gone, just never in position
first. Do not repoint case 3, which is already the hunt, and there is nothing
else in this switch worth leaving alone.

Raven Shield's VIP-defend mode, which is where this idea came from, is
literally `m_huntedPawn = VIP; m_eStrategy = 3` per terrorist. `R6DefendGame`
is not on the PS2 disc, but everything it drives is.

So the edit repoints the switch instead of chasing the strategy value: each
non-hunt case jumps to `HuntRainbow` instead. `HuntRainbow` is already name
810 in the package and already referenced by that block, so no name and no
export is added -- it is a pure byte poke, the edit family that works here.

The deployment-zone clamp, which was the real risk
--------------------------------------------------

`GotoStateMovingTo` can pin a destination inside the terrorist's own
deployment zone, which would have made "hunt" mean "shuffle about at home".
It does not apply: `MT_DontCheckLeave` is 0x02 on this build and
`HuntRainbow` passes exactly that, so the clamp is skipped and they cross the
map.

What it costs
-------------

Every mission becomes a rush. `R6Engine` lives in the COMMON packages, so
there is no per-map or per-mode scoping available. Authored patrol and guard
design is discarded wherever the edit applies, and **hostage missions are the
real casualty**: terrorists leave for the hunt at spawn, so execution and
human-shield behaviour largely stops happening. Your own squad is untouched,
and so are scripted terrorists.

That is why the narrow setting exists: repointing only the guard-point case
leaves maps that author real patrol paths alone, while still turning every
terrorist on a map where they all guard -- which was all 28 of them on the
level this was measured against.

Close-range grenades -- READ THIS BEFORE TOUCHING THE DIAL
---------------------------------------------------------

**The comparison runs the other way from what this module was built on, and
every `ai_grenade_range` choice therefore does the opposite of its label.**

`R6TerroristAI.Attack` throws one behind a test that was read as
`dist(Enemy) > 1500` -- a fifteen-metre MINIMUM, the thing stopping a
point-blank throw. It is not. Disassembled on 2026-09-26, the comparison
opcode in that statement is `0xB0`, and the game's own engine source
declares

    native(176) static final operator(24) bool  <  ( float A, float B );

so the shipped statement is

    if (m_pawn.m_bHaveAGrenade
        && VSize(Enemy.Location - m_pawn.Location) < 1500.0)
        GotoStateThrowingGrenade(Enemy, 'Attack', 'Fire');

1500 is a MAXIMUM. Enemies throw grenades at anything INSIDE fifteen metres
and stop bothering beyond it. So lowering this dial narrows the window
rather than widening it, and its bottom setting -- captioned "any range at
all", "point blank" -- writes `dist < 0`, which is never true and switches
AI grenades off completely. Read on the live disc, where it was set.

The statement is at disk `0x16520F` (47 bytes) / memory `0xBA9` (64) inside
block `0x1648CF`, and the pinned run occurs exactly once in each of the
three COMMON packages, at `0x165232` in COMMON_SS. The constant is an
`EX_IntConst` inside an int-to-float conversion, fixed width, so any
threshold is still a digit-for-digit rewrite of the same 13-byte window --
only the direction of the test was wrong, never the mechanics.

A genuine MINIMUM does exist, in a different function:
`R6TerroristAI.ThrowingGrenade.CheckDistance` (block `0x16A33C`) refuses to
throw when `fDist < settings.m_fMinDistToThrowGrenade + 50`, which is 550
units -- 5.5 metres -- because the INI ships `m_fMinDistToThrowGrenade=500`.
That is the constant a "how close before they throw" dial has to target.
It also settles a tension recorded elsewhere in this project between "the
INI says 500" and "the script says 1500": they are two different gates, a
5.5-metre floor and a 15-metre ceiling.

NOT established: whether a grenade thrown at point-blank range kills the
thrower. Answerable in one play-test and not from reading.

This module had no test coverage at all, which is how the inversion
shipped.
"""

from __future__ import annotations

import struct

H = bytes.fromhex


class AiHuntError(Exception):
    pass


#: Offline single player and split screen. The online package is deliberately
#: left alone, as everywhere else in this profile.
SELECT = r"/COMMON(OFF|_SS)\.LIN$"

#: Every region is pinned by CONTENT and BOTH runs are unique in all three
#: COMMON packages -- the stock run so the edit lands in the right place, and
#: the replacement run so reading it back and reverting cannot match a second
#: site. COMMON.LIN carries the same bytecode 8,206 bytes further along, so an
#: offset table would not survive it.
REGIONS = {
    "case_patrolpath": ("case_patrolpath",
     H(
         "00712150061606ed"),
     H(
         "0071216a0c1606ed")),
    "case_patrolarea": ("case_patrolarea",
     H(
         "017121640c1606ed"),
     H(
         "0171216a0c1606ed")),
    "case_guardpoint": ("case_guardpoint",
     H(
         "027121600c1606ed"),
     H(
         "0271216a0c1606ed")),
    #: The wave arm, which is NOT part of the switch -- see the docstring.
    #: `VirtualFunction 'GotoStateAttackActionSpot' NoObject NoObject
    #: EndFunctionParms` becomes `GotoState('HuntRainbow')` plus one
    #: `EX_Nothing`, which is the VM's own no-op and is unreachable behind
    #: the GotoState in any case. 6 disk and 8 memory bytes both ways.
    "case_wave": ("case_wave",
     H(
         "1b7f052a2a16"),
     H(
         "71216a0c160b")),
    "pace_run": ("pace_run",
     H(
         "8c2403216a"),
     H(
         "8c2404216a")),
    "fire_on_move": ("fire_on_move",
     H(
         "1224021f48"),
     H(
         "12240a1f48")),
}

#: How far away an enemy will still bother throwing a grenade, in world
#: units -- a MAXIMUM, not a minimum; see the module docstring. 100 units is
#: a metre, so the shipped 1500 is fifteen metres, and a lower number here
#: means FEWER grenades, not more. Zero switches them off entirely.
GATE_STOCK_UNITS = 1500
#: The 13-byte window the constant sits in. `EX_IntConst` is fixed width, so
#: the threshold is a straight splice: the four bytes between these halves
#: are a little-endian int. Both halves together occur exactly once in each
#: of the three COMMON packages.
GATE_HEAD = H("8c1616393f1d")
GATE_TAIL = H("16161b")

#: Offered ceilings, in world units. Above the shipped 1500 they widen the
#: window -- enemies throw from further out, so you see more grenades, which
#: is the direction this dial was always meant to go. Below it they narrow
#: it, and 0 switches AI grenades off entirely.
GATE_UNITS = (750, 1500, 2500, 3000, 4000, 6000, 10000)


def gate_run(units: int) -> bytes:
    """The 13-byte window carrying `units` as its threshold."""
    n = int(units)
    if not 0 <= n <= 0x7FFFFFFF:
        raise AiHuntError("grenade range %r is outside 0..2147483647" % units)
    return GATE_HEAD + struct.pack("<i", n) + GATE_TAIL


def gate_region(units: int):
    """(name, stock bytes, new bytes) for one ceiling."""
    n = int(units)
    if n == GATE_STOCK_UNITS:
        raise AiHuntError("grenade range %r is what the game ships" % units)
    return ("range_%d" % n, gate_run(GATE_STOCK_UNITS), gate_run(n))


def _table(which: str):
    if which.startswith("range:"):
        return [gate_region(int(which.split(":", 1)[1]))]
    if which not in REGIONS:
        raise AiHuntError("no such hunt option: %r" % which)
    return [REGIONS[which]]


def _sites(plain: bytes, which: str):
    out = []
    for name, stock, new in _table(which):
        want = new if plain.count(new) else stock
        if plain.count(want) != 1:
            raise AiHuntError("%s: %s" % (name, "not found" if not
                              plain.count(want) else "found %d times"
                              % plain.count(want)))
        out.append((name, plain.index(want), stock, new))
    return out


def reads(plain: bytes, which: str) -> bool:
    """True when every region of `which` is present in its edited form."""
    try:
        return all(plain.count(new) == 1 for _n, _st, new in _table(which))
    except AiHuntError:
        return False


def apply(plain: bytes, which: str, enable: bool = True):
    """Returns (bytes, regions changed)."""
    want_new = bool(enable)
    out, n = bytearray(plain), 0
    for name, at, stock, new in _sites(bytes(plain), which):
        target = new if want_new else stock
        if bytes(out[at:at + len(target)]) == target:
            continue
        out[at:at + len(target)] = target
        n += 1
    return bytes(out), n


# ------------------------------------------------------------------ cards --
def cards(prefix, group):
    from .model import BOOL, CHOICE, Choice, Setting

    return [
        Setting(
            prefix + "ai_hunt", "Enemies hunt you down", CHOICE, "off", group,
            choices=[
                Choice("off", "Off",
                       "As shipped: they patrol, guard a post, and only come "
                       "for you once they know you are there."),
                Choice("guard", "The ones standing guard",
                       "Enemies posted to guard a spot come after you "
                       "instead. Maps that give their enemies real patrol "
                       "routes keep them."),
                Choice("all", "Every enemy on the map",
                       "Nobody patrols and nobody guards. Everyone comes, "
                       "including the ones a wave releases."),
            ],
            confidence="experimental", touches="data",
            help="The enemies already have this behaviour -- the game just "
                 "never turns it on. In it they pick the nearest Rainbow "
                 "operative with no sight check at all and path to you across "
                 "the whole map, which is how Rainbow Six 3 on PC runs its "
                 "VIP defence mode.\n\n"
                 "It is the difference between clearing a building and being "
                 "hunted through one.\n\n"
                 "About half the enemies on a level are attached to a wave "
                 "spawn point, and the game routes those down a different "
                 "branch that this setting used to miss entirely. The ones "
                 "standing there when the level loads would come for you "
                 "once and then go back to holding a spot; the ones a wave "
                 "releases never came at all. Both settings now cover them.",
            caution="Not yet played. Offline and split screen only.\n\n"
                    "This discards the level designers' work: every mission "
                    "becomes a rush, and there is no way to scope it to one "
                    "map or one mode because the code is shared by all of "
                    "them.\n\n"
                    "HOSTAGE MISSIONS SUFFER MOST. Enemies leave their posts "
                    "the moment the level starts, so the hostage execution "
                    "and human-shield behaviour mostly stops happening. "
                    "\"The ones standing guard\" is the gentler setting, but "
                    "only just: every terrorist measured on this disc is a "
                    "guard, so in practice the two settings do nearly the "
                    "same thing.\n\n"
                    "SNIPERS STOP SNIPING. A sniper takes up position from "
                    "the guard-point state, so repointing it sends him at "
                    "you with the rest."),
        Setting(
            prefix + "ai_hunt_run", "They run rather than walk", BOOL, False,
            group, requires={prefix + "ai_hunt": ("guard", "all")},
            confidence="experimental", touches="data",
            help="Hunting enemies move at a walk out of the box, which gives "
                 "you a long time to hear them coming. This sends them at a "
                 "run.",
            caution="Not yet played. Expect considerably less warning."),
        Setting(
            prefix + "ai_hunt_fire", "They shoot while advancing", BOOL,
            False, group, requires={prefix + "ai_hunt": ("guard", "all")},
            confidence="experimental", touches="data",
            help="By default a hunting enemy closes the distance without "
                 "firing. This lets them shoot on the move.",
            caution="Not yet played."),
        Setting(
            prefix + "ai_grenade_range",
            "How far out enemies will throw a grenade", CHOICE, "off", group,
            choices=[Choice("off", "Fifteen metres (as shipped)",
                            "They stop bothering beyond that.")]
            + [Choice(str(u), "%g metres" % (u / 100.0),
                      "Fewer grenades than the game ships."
                      if u < GATE_STOCK_UNITS else "")
               for u in GATE_UNITS if u != GATE_STOCK_UNITS]
            + [Choice("0", "Never", "Switches AI grenades off altogether.")],
            confidence="experimental", touches="data",
            help="How far away an enemy will still bother throwing a grenade "
                 "at you. The game stops at fifteen metres, so you see them "
                 "in the open and almost never across a long approach.\n\n"
                 "Raising this is what gives you MORE grenades. Lowering it "
                 "narrows the window, and \"never\" switches them off.\n\n"
                 "This is not what decides whether one lands at your feet -- "
                 "that is the separate close-range setting below, which "
                 "works on the game's own refusal to throw at someone too "
                 "near.",
            caution="Not yet played. Offline and split screen only.\n\n"
                    "This dial was previously labelled the other way round: "
                    "it was described as a minimum, so every setting did the "
                    "opposite of what it said and its bottom notch silently "
                    "switched AI grenades off. The comparison was "
                    "disassembled and the labels now match the game."),
        Setting(
            prefix + "ai_grenade_min",
            "How close they will still throw one", CHOICE, "off", group,
            choices=[Choice("off", "Five and a half metres (as shipped)",
                            "Nearer than that and they will not throw.")]
            + [Choice(str(u), "%g metres" % ((u + 50) / 100.0),
                      "At your feet." if not u else "")
               for u in (250, 100, 0)],
            confidence="experimental", touches="data",
            help="Enemies refuse to throw a grenade at anyone too close, "
                 "which is why it almost never happens in a room. The refusal "
                 "is a single number in the game's own settings file, and "
                 "the check adds half a metre to it, so the shipped 500 is a "
                 "five-and-a-half-metre floor.\n\n"
                 "Lowering it is what turns a grenadier into something like "
                 "a suicide run: they close the distance and drop one where "
                 "they are standing.",
            caution="Not yet played, and one thing is genuinely unknown: "
                    "whether a grenade thrown at point-blank range kills the "
                    "thrower. That is exactly what the lowest setting is "
                    "for, and no amount of reading the game settles it.\n\n"
                    "The grenade is THROWN, not dropped, so at contact range "
                    "the arc may carry it past you -- in which case you get "
                    "an aggressive grenadier rather than a bomber.\n\n"
                    "This one is a settings-file value, so unlike the dial "
                    "above it applies everywhere, online included."),
    ]

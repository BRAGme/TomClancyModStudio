"""Several impact puffs at once: a private pool of emitter actors.

Why one puff was all you ever saw, and why removing the limit was not enough.

1. THE ENGINE RATE-LIMITS IMPACT DUST TO ONE BURST EVERY HALF SECOND, from a
   single float it keeps for the whole game. `rsedecal.BURST_GATE` removes
   that limit, and then the second wall shows.

2. THERE IS EXACTLY ONE POOLED EMITTER ACTOR PER MATERIAL. The game keeps 22
   of them, built at level load, and an impact re-fires the one that matches
   what it hit. Re-firing an emitter that is still playing runs it through
   `Init` -> `Reset`, which zeroes ActiveParticles -- so the burst already on
   screen is deleted and replaced. Rapid fire at one wall therefore cancels
   its own dust, which is exactly what it looks like in play: the puff stops
   and jumps to the newest hit.

3. SO THE CAVE KEEPS ITS OWN POOL and hands out a different actor per impact,
   round robin. It spawns them once per level from the lightest emitter class
   the level has -- found by scanning the game's own table, never hard-coded,
   because UObject addresses move every load -- parks them with the same six
   stores the game's own builder uses, and thereafter re-fires one in about
   forty instructions with no call at all.

THE POOL IS A RING, AND THAT IS THE POINT. N is a hard ceiling on how many
puffs can be alive at once, whatever the rate of fire, however many people are
shooting, however many grenades overlap. The cost does not scale with the
firefight; it saturates.

WHERE IT HOOKS. One word, at the last instruction before the impact visual
tests whether the material has a spark class. At that point the pooled effect
actor's Location and Rotation have already been written with the hit point and
the surface rotator, so one hooked word serves every impact in the game --
every bullet, every ricochet, every exit wound, every material, and the
shrapnel cave's own impacts -- with no per-weapon work. It also sits upstream
of the half-second gate, so the pool does not care whether that gate is on.

Blood, meat and plush are skipped: a generic dust puff on a body shot looks
wrong. Their slots in the table are fixed by a rodata name list, so the three
indices are stable across loads and levels.

Not established
---------------
* How it looks. Sixteen small smoke puffs at ~2-3 units is the reasoning; a
  screenshot is the proof.
* GS fill rate with a ring of puffs alive during sustained automatic fire.
* Whether every map builds the impact table with a one-emitter class in it.
  The scan degrades safely -- it picks the lightest present, and does nothing
  at all if the table is empty.
"""


from __future__ import annotations


class PuffError(Exception):
    pass


# ------------------------------------------------------- the hook ---

#: `swc1 $f0, 0x4c($sp)` -- a dead store to the impact visual's own
#: frame, and the last word before it tests the material's spark
#: class. It is hooked rather than the test itself because a jump's
#: delay slot must not be a branch, and the next word is one.
HOOK_AT = 0x0056E3B0
HOOK_STOCK = 0xE7A0004C
#: `j 0x000F3080`
HOOK = 0x0803CC20
RESUME = 0x0056E3B8

#: The pool's RAM. RUNTIME STATE -- deliberately NOT emitted, for the
#: same reason the stagger queue is not: a pnach row rewrites its
#: address every frame, which here would clear the level stamp every
#: frame and respawn the whole pool forever.
POOL_RAM = 0x000F2C00
POOL_RAM_END = 0x000F2CC0

FIRE = 0x000F2CC0
BUILD = 0x000F2DC0
TRAMPOLINE = 0x000F3080
BLOCK_END = 0x000F3400

#: `slti $at, $t0, N` -- the ring size, and the hard ceiling on how
#: many puffs can be alive at once.
COUNT_AT = 0x000F2E34
COUNT_DEFAULT = 16
COUNT_MAX = 32        # PP_POOL is 32 words wide

#: `addiu $v1, $zero, N`, feeding `sw $v1, 0x3C($t4)` -- MaxParticles on our
#: OWN sub-emitters, and the reason the first attempt looked like it had not
#: worked at all.
#:
#: A puff is visible for `MaxParticles / InitialParticlesPerSecond`, NOT for
#: its `LifetimeRange`. The engine sets `AllParticlesDead` (+0x318 bit 3) as
#: soon as the spawn window closes, because `RespawnDeadParticles` (+0x65
#: bit 2) is false -- measured in a savestate with the flag set and three
#: particles still counted. `AEmitter::Tick` then re-parks the actor, and a
#: parked actor neither simulates nor draws.
#:
#: At the shipped 3 and an InitialPPS of 60 that is 3/60 = 0.05 s: two
#: frames. It is why the game's own impact dust was always a flicker, and it
#: is why no ring size could ever show two puffs at once -- at 18 rounds a
#: second, 0.05 s of life averages 0.9 puffs alive.
#:
#: 12 gives 0.20 s. InitialPPS is left alone deliberately: lowering it would
#: stretch the window too, but it would also put 167 ms between the bullet
#: and any dust. `Init` reads this, sets MaxActiveParticles from it and grows
#: the particle array once per actor on first fire.
MAXPART_AT = 0x000F2EE4
MAXPART_DEFAULT = 12
MAXPART_MAX = 32
#: Sprites per second, fixed by the class default. Visible life is
#: `MaxParticles / SPRITES_PER_SECOND`.
SPRITES_PER_SECOND = 60.0


def visible_seconds(particles: int = MAXPART_DEFAULT) -> float:
    """How long one puff is actually on screen."""
    return int(particles) / SPRITES_PER_SECOND

#: `slti $at, $t6, K` -- spawns allowed per call, so no single frame
#: pays for the whole pool.
BUDGET_AT = 0x000F2E40
BUDGET_DEFAULT = 4

_POOL_WORDS = (
    0x3C0D000F, 0x8DA22C04, 0x18400035, 0x8DA32C08,
    0x0062302A, 0x14C00002, 0x00000000, 0x00001821,
    0x00033080, 0x01A63021, 0x8CC72C10, 0x24630001,
    0xADA32C08, 0x10E0002A, 0x00000000, 0x8C880000,
    0x8C890004, 0x8C8A0008, 0xACE801B0, 0xACE901B4,
    0xACEA01B8, 0xACE001BC, 0x10A00006, 0x00000000,
    0x8CA80000, 0x8CA90004, 0x8CAA0008, 0x10000004,
    0x00000000, 0x00004021, 0x00004821, 0x00005021,
    0xACE801C0, 0xACE901C4, 0xACEA01C8, 0x90E80370,
    0x310800F7, 0xA0E80370, 0xACE003A4, 0x8CE90378,
    0x8CEA037C, 0x1120000E, 0x00005821, 0x016A082A,
    0x1020000B, 0x00000000, 0x8D2C0000, 0x11800004,
    0x00000000, 0x91810318, 0x302100FE, 0xA1810318,
    0x25290004, 0x256B0001, 0x1000FFF4, 0x00000000,
    0x03E00008, 0x00000000, 0x27BDFFE0, 0xFFBF0010,
    0x3C0D000F, 0x8DA32C9C, 0x14600055, 0x00000000,
    0x24030001, 0xADA32C9C, 0x8C8202E4, 0x14400004,
    0x00000000, 0xADA02C04, 0x1000004B, 0xADA02C00,
    0x8DA32C00, 0x10620008, 0x00000000, 0xADA02C04,
    0xADA02C08, 0xADA02C0C, 0xADA22C00, 0x0C03CBCD,
    0x00000000, 0x3C0D000F, 0x8DA22C0C, 0x1040003E,
    0x00000000, 0x00007021, 0x8DA82C04, 0x29010010,
    0x10200039, 0x00000000, 0x29C10004, 0x10200036,
    0x00000000, 0x8DA42C00, 0x8DA52C0C, 0x00003021,
    0x3C07005D, 0x24E75680, 0x00E04021, 0x00004821,
    0x240A0001, 0x00005821, 0xFFA00000, 0xFFA00008,
    0x0C087C0C, 0x00000000, 0x3C0D000F, 0x10400026,
    0x00000000, 0xA040002E, 0x90480370, 0x35080008,
    0x310800FC, 0xA0480370, 0xAC4003A4, 0xAC400094,
    0x9048006D, 0x35080020, 0xA048006D, 0x8C490378,
    0x8C4A037C, 0x00005821, 0x016A082A, 0x1020000D,
    0x00000000, 0x8D2C0000, 0x11800006, 0x00000000,
    0x91810065, 0x302100F7, 0xA1810065, 0x2403000C,
    0xAD83003C, 0x25290004, 0x256B0001, 0x1000FFF2,
    0x00000000, 0x8DA82C04, 0x00080880, 0x01A10821,
    0xAC222C10, 0x25080001, 0xADA82C04, 0x25CE0001,
    0x1000FFC5, 0x00000000, 0x3C0D000F, 0xADA02C9C,
    0xDFBF0010, 0x03E00008, 0x27BD0020, 0x3C080065,
    0x8D08526C, 0x19000040, 0x00000000, 0x29010041,
    0x1020003D, 0x00000000, 0x3C0E006E, 0x25CED730,
    0x240F7FFF, 0x0000C021, 0x00004821, 0x0128082A,
    0x10200028, 0x00000000, 0x00090880, 0x01C10821,
    0x8C2A0000, 0x11400020, 0x00000000, 0x31410003,
    0x1420001D, 0x00000000, 0x8D4B0378, 0x8D4C037C,
    0x11600019, 0x00000000, 0x19800017, 0x00000000,
    0x00002021, 0x00002821, 0x00AC082A, 0x1020000B,
    0x00000000, 0x00050880, 0x01610821, 0x8C260000,
    0x10C00003, 0x00000000, 0x8CC7003C, 0x00872021,
    0x24A50001, 0x1000FFF4, 0x00000000, 0x000C0A00,
    0x00240821, 0x002F202A, 0x10800003, 0x00000000,
    0x00207821, 0x0140C021, 0x25290001, 0x1000FFD7,
    0x00000000, 0x1300000C, 0x00000000, 0x3C0D000F,
    0x8F010024, 0xADA12C0C, 0x3C0E006E, 0x25CED6C0,
    0x8DC10008, 0xADA12C90, 0x8DC10034, 0xADA12C94,
    0x8DC10044, 0xADA12C98, 0x03E00008, 0x00000000,
    0xE7A0004C, 0x02402021, 0x0C03CB70, 0x00000000,
    0x3C0D000F, 0x8DA12C90, 0x1032000A, 0x00000000,
    0x8DA12C94, 0x10320007, 0x00000000, 0x8DA12C98,
    0x10320004, 0x00000000, 0x264401B0, 0x0C03CB30,
    0x264501C0, 0x8E430384, 0x0815B8EE, 0x00000000,
)

#: The VA of _POOL_WORDS[i].
_VAS = (
    0x000F2CC0, 0x000F2CC4, 0x000F2CC8, 0x000F2CCC, 0x000F2CD0, 0x000F2CD4,
    0x000F2CD8, 0x000F2CDC, 0x000F2CE0, 0x000F2CE4, 0x000F2CE8, 0x000F2CEC,
    0x000F2CF0, 0x000F2CF4, 0x000F2CF8, 0x000F2CFC, 0x000F2D00, 0x000F2D04,
    0x000F2D08, 0x000F2D0C, 0x000F2D10, 0x000F2D14, 0x000F2D18, 0x000F2D1C,
    0x000F2D20, 0x000F2D24, 0x000F2D28, 0x000F2D2C, 0x000F2D30, 0x000F2D34,
    0x000F2D38, 0x000F2D3C, 0x000F2D40, 0x000F2D44, 0x000F2D48, 0x000F2D4C,
    0x000F2D50, 0x000F2D54, 0x000F2D58, 0x000F2D5C, 0x000F2D60, 0x000F2D64,
    0x000F2D68, 0x000F2D6C, 0x000F2D70, 0x000F2D74, 0x000F2D78, 0x000F2D7C,
    0x000F2D80, 0x000F2D84, 0x000F2D88, 0x000F2D8C, 0x000F2D90, 0x000F2D94,
    0x000F2D98, 0x000F2D9C, 0x000F2DA0, 0x000F2DA4, 0x000F2DC0, 0x000F2DC4,
    0x000F2DC8, 0x000F2DCC, 0x000F2DD0, 0x000F2DD4, 0x000F2DD8, 0x000F2DDC,
    0x000F2DE0, 0x000F2DE4, 0x000F2DE8, 0x000F2DEC, 0x000F2DF0, 0x000F2DF4,
    0x000F2DF8, 0x000F2DFC, 0x000F2E00, 0x000F2E04, 0x000F2E08, 0x000F2E0C,
    0x000F2E10, 0x000F2E14, 0x000F2E18, 0x000F2E1C, 0x000F2E20, 0x000F2E24,
    0x000F2E28, 0x000F2E2C, 0x000F2E30, 0x000F2E34, 0x000F2E38, 0x000F2E3C,
    0x000F2E40, 0x000F2E44, 0x000F2E48, 0x000F2E4C, 0x000F2E50, 0x000F2E54,
    0x000F2E58, 0x000F2E5C, 0x000F2E60, 0x000F2E64, 0x000F2E68, 0x000F2E6C,
    0x000F2E70, 0x000F2E74, 0x000F2E78, 0x000F2E7C, 0x000F2E80, 0x000F2E84,
    0x000F2E88, 0x000F2E8C, 0x000F2E90, 0x000F2E94, 0x000F2E98, 0x000F2E9C,
    0x000F2EA0, 0x000F2EA4, 0x000F2EA8, 0x000F2EAC, 0x000F2EB0, 0x000F2EB4,
    0x000F2EB8, 0x000F2EBC, 0x000F2EC0, 0x000F2EC4, 0x000F2EC8, 0x000F2ECC,
    0x000F2ED0, 0x000F2ED4, 0x000F2ED8, 0x000F2EDC, 0x000F2EE0, 0x000F2EE4,
    0x000F2EE8, 0x000F2EEC, 0x000F2EF0, 0x000F2EF4, 0x000F2EF8, 0x000F2EFC,
    0x000F2F00, 0x000F2F04, 0x000F2F08, 0x000F2F0C, 0x000F2F10, 0x000F2F14,
    0x000F2F18, 0x000F2F1C, 0x000F2F20, 0x000F2F24, 0x000F2F28, 0x000F2F2C,
    0x000F2F30, 0x000F2F34, 0x000F2F38, 0x000F2F3C, 0x000F2F40, 0x000F2F44,
    0x000F2F48, 0x000F2F4C, 0x000F2F50, 0x000F2F54, 0x000F2F58, 0x000F2F5C,
    0x000F2F60, 0x000F2F64, 0x000F2F68, 0x000F2F6C, 0x000F2F70, 0x000F2F74,
    0x000F2F78, 0x000F2F7C, 0x000F2F80, 0x000F2F84, 0x000F2F88, 0x000F2F8C,
    0x000F2F90, 0x000F2F94, 0x000F2F98, 0x000F2F9C, 0x000F2FA0, 0x000F2FA4,
    0x000F2FA8, 0x000F2FAC, 0x000F2FB0, 0x000F2FB4, 0x000F2FB8, 0x000F2FBC,
    0x000F2FC0, 0x000F2FC4, 0x000F2FC8, 0x000F2FCC, 0x000F2FD0, 0x000F2FD4,
    0x000F2FD8, 0x000F2FDC, 0x000F2FE0, 0x000F2FE4, 0x000F2FE8, 0x000F2FEC,
    0x000F2FF0, 0x000F2FF4, 0x000F2FF8, 0x000F2FFC, 0x000F3000, 0x000F3004,
    0x000F3008, 0x000F300C, 0x000F3010, 0x000F3014, 0x000F3018, 0x000F301C,
    0x000F3020, 0x000F3024, 0x000F3028, 0x000F302C, 0x000F3030, 0x000F3034,
    0x000F3038, 0x000F303C, 0x000F3040, 0x000F3044, 0x000F3080, 0x000F3084,
    0x000F3088, 0x000F308C, 0x000F3090, 0x000F3094, 0x000F3098, 0x000F309C,
    0x000F30A0, 0x000F30A4, 0x000F30A8, 0x000F30AC, 0x000F30B0, 0x000F30B4,
    0x000F30B8, 0x000F30BC, 0x000F30C0, 0x000F30C4, 0x000F30C8, 0x000F30CC,
)


def words(count: int = COUNT_DEFAULT, budget: int = BUDGET_DEFAULT,
          particles: int = MAXPART_DEFAULT):
    """[(va, word)] for the cave, with the ring size and puff length in."""
    if not 1 <= int(count) <= COUNT_MAX:
        raise PuffError('pool size %r is outside 1..%d'
                        % (count, COUNT_MAX))
    if not 1 <= int(budget) <= COUNT_MAX:
        raise PuffError('spawn budget %r is outside 1..%d'
                        % (budget, COUNT_MAX))
    if not 1 <= int(particles) <= MAXPART_MAX:
        raise PuffError('puff length %r is outside 1..%d'
                        % (particles, MAXPART_MAX))
    out = []
    for va, w in zip(_VAS, _POOL_WORDS):
        if va == COUNT_AT:
            w = (w & 0xFFFF0000) | int(count)
        elif va == BUDGET_AT:
            w = (w & 0xFFFF0000) | int(budget)
        elif va == MAXPART_AT:
            w = (w & 0xFFFF0000) | int(particles)
        out.append((va, w))
    out.append((HOOK_AT, HOOK))
    return out


def reads(word_at) -> bool:
    """True if `word_at(va)` shows the hook in place."""
    return word_at(HOOK_AT) == HOOK


def cards(prefix, group):
    from .model import BOOL, CHOICE, Choice, Setting

    return [
        Setting(
            prefix + 'impact_puffs',
            'Every impact raises its own dust, and they overlap',
            BOOL, False, group,
            confidence='experimental', touches='ram',
            help='The game keeps one puff of dust per material and '
                 'moves it to whatever was hit last, so firing quickly '
                 'at a wall keeps cancelling the puff you are already '
                 'looking at.\n\n'
                 'This gives the game a small pool of its own, so each '
                 'hit gets a puff that is allowed to finish. The pool '
                 'is a fixed size, which is also the limit on how many '
                 'can be on screen at once.',
            caution='Not yet played. It adds particles to every shot '
                    'anyone fires, so a heavy firefight draws more '
                    'than the game was built to draw.'),
        Setting(
            prefix + 'impact_puff_count', 'How many can overlap',
            CHOICE, str(COUNT_DEFAULT), group,
            requires={prefix + 'impact_puffs': (True,)},
            choices=[Choice('12', 'A few'),
                     Choice('16', 'Several'),
                     Choice('24', 'Enough that yours never cut short'),
                     Choice('32', 'As many as it will hold')],
            help='The pool size. It is a hard limit: no matter how '
                 'fast anyone fires, this is the most dust that can '
                 'be alive at one time, so it is also the cost.\n\n'
                 'Sixteen is enough that a rifle never cuts its own '
                 'dust short, and it absorbs a shotgun pull, which '
                 'asks for nine at once. Larger costs a single '
                 'shooter nothing and only raises the ceiling for a '
                 'firefight.'),
        Setting(
            prefix + 'impact_puff_length', 'How long each one lasts',
            CHOICE, str(MAXPART_DEFAULT), group,
            requires={prefix + 'impact_puffs': (True,)},
            choices=[Choice('3', 'As the game draws it (a flicker)',
                            'Two frames. This is why the shipped dust '
                            'is so easy to miss.'),
                     Choice('6', 'Brief'),
                     Choice('12', 'Long enough to see'),
                     Choice('24', 'Lingering')],
            help='A puff lasts for as long as it is still spawning '
                 'sprites, not for the second its own settings claim '
                 '-- the engine retires it the moment the last one is '
                 'out. So this is really the length of the puff: at '
                 'the game\'s own value of three it is on screen for '
                 'five hundredths of a second.\n\n'
                 'It does not delay anything. The first sprite still '
                 'appears on the frame the bullet lands.',
            caution='Longer puffs are the thing most likely to cost '
                    'frames, because they overlap: the cost is how '
                    'many are alive at once, which is this multiplied '
                    'by how fast people are shooting, up to the pool '
                    'size above.'),
    ]

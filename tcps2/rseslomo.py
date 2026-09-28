"""Slow motion when a room goes quiet.

The lever is one float. `LevelInfo.TimeDilation` (+0x458) multiplies into the
delta time at `0x00223998`, and the product is stored as `LevelInfo.m_dT`
(+0x47C) at `0x00223A84`, **clamped to [0.0005, 0.4] seconds** at
`0x00223A30..0x00223A7C`. `m_dT` is what reaches `AEmitter::Tick`, so dilation
scales particle spawning and ageing equally -- it is a real global time scale,
not a rendering trick. Measured stock: `TimeDilation` is 1.0 in all six EE
dumps.

THE TRIGGER
-----------

The live terrorist count, `R6GameInfo.m_listAllTerrorists.ArrayNum`, reached
as `[[[[GEngine+0x45C]+0x2C]+0]+0x520]+0x56C`. Measured 16/16/8/13/20/8 across
six dumps on six levels, `ArrayMax >= ArrayNum` every time, every live entry
resolving to a terrorist pawn class, and the offset pinned by its two
neighbours landing exactly where the shipped source's declaration order says.

It is the only candidate that is both O(1) and correct in split screen. The
obvious alternative -- "the squad is down to one" -- is dead as written:
`m_iMemberCount == 1` is ALREADY true in retail split screen, because player 2
sits outside the count.

WHERE IT HOOKS, AND WHY NOT ULevel::Tick
----------------------------------------

`ULevel::Tick` (`0x00223770`) runs **up to three times per frame**:
`UGameEngine::Tick` (`0x002EA600`) ticks `GEngine+0x45C`, `+0x460`, and a
third through `+0x44`. Anything counting frames there counts wrong -- the
claymore cave survives it only because a proximity test does not care.

So this hooks `jal 0x001805B0` at `0x002EA7A4` instead: once per frame,
before all three level ticks, 472 bytes clear of the stagger cave's own site,
with a `nop` delay slot. The displaced function is `void(void)`, so the cave
tail-calls it and needs no thunk.

THE SOUND DOES NOT SLOW, AND THAT IS MEASURED
----------------------------------------------

`GEngine+0x4C` is a `DareAudioSubsystem`, and `UGameEngine::Tick` updates it
at `0x002EA79C` with the **undilated** delta -- whose only use in the whole
221-word function at `0x00473350` is a `frame <= 0.2 s` hitch guard. There is
no pitch route either: `PlaySound` was cut to two arguments under a `// R6CODE`
marker, `SoundPitch` has no declaration, and DARE's three pitch entry points
have no caller anywhere in 128 MB.

So gunfire and music keep normal speed and pitch over a slowed picture. At
about a second that reads as stylised; it is the reason the presets cap the
hold at 0.9 s rather than running longer.

WHY NOTHING SLOWER IS OFFERED
------------------------------

`m_dT` is floored at 0.0005 s. At split screen's measured 60 Hz that is a
dilation of 0.030, and below it the picture stops getting slower and starts
depending on frame rate instead.
"""

from __future__ import annotations


class SlomoError(Exception):
    pass


#: `jal 0x001805B0` in UGameEngine::Tick -- once per frame, before every
#: ULevel::Tick, delay slot already a nop.
HOOK_AT = 0x002EA7A4
HOOK_STOCK = 0x0C06016C

CAVE = 0x000F3C00
SPAN_END = 0x000F4000
#: Runtime state. **Never emitted** -- a pnach row rewrites its address every
#: frame, which would reset the beat every frame and nothing would ever run.
STATE = 0x000F3FE0
STATE_END = 0x000F4000

#: How slow, and for how long.
PRESETS = ('gentle', 'normal', 'heavy')
PRESET_DEFAULT = "normal"
#: Which kill starts a beat.
THRESHOLDS = ('last', 'final_two', 'any_kill')
THRESHOLD_DEFAULT = "last"

#: The eight words the dials move. Everything else is fixed.
_CONST_VAS = (0x000F3FC0, 0x000F3FC4, 0x000F3FC8, 0x000F3FCC, 0x000F3FD0, 0x000F3FD4, 0x000F3FD8, 0x000F3FDC,)

_CONST = {
    ("gentle", "last"): (0x3F000000, 0x41055555, 0x3DF5C28F, 0x3EF0A3D7, 0x400E38E4, 0x3F6B851F, 0x00000001, 0xBF000000,),
    ("gentle", "final_two"): (0x3F000000, 0x41055555, 0x3DF5C28F, 0x3EF0A3D7, 0x400E38E4, 0x3F6B851F, 0x00000002, 0xBF000000,),
    ("gentle", "any_kill"): (0x3F000000, 0x41055555, 0x3DF5C28F, 0x3EF0A3D7, 0x400E38E4, 0x3F6B851F, 0x7FFFFFFF, 0xBF000000,),
    ("normal", "last"): (0x3E99999A, 0x40D55555, 0x3E19999A, 0x3F333333, 0x3FD55555, 0x3FA66666, 0x00000001, 0xBF333333,),
    ("normal", "final_two"): (0x3E99999A, 0x40D55555, 0x3E19999A, 0x3F333333, 0x3FD55555, 0x3FA66666, 0x00000002, 0xBF333333,),
    ("normal", "any_kill"): (0x3E99999A, 0x40D55555, 0x3E19999A, 0x3F333333, 0x3FD55555, 0x3FA66666, 0x7FFFFFFF, 0xBF333333,),
    ("heavy", "last"): (0x3E3851EC, 0x40A00000, 0x3E4CCCCD, 0x3F8CCCCD, 0x3FA00000, 0x3FF33333, 0x00000001, 0xBF51EB85,),
    ("heavy", "final_two"): (0x3E3851EC, 0x40A00000, 0x3E4CCCCD, 0x3F8CCCCD, 0x3FA00000, 0x3FF33333, 0x00000002, 0xBF51EB85,),
    ("heavy", "any_kill"): (0x3E3851EC, 0x40A00000, 0x3E4CCCCD, 0x3F8CCCCD, 0x3FA00000, 0x3FF33333, 0x7FFFFFFF, 0xBF51EB85,),
}

_VAS = (
    0x000F3C00, 0x000F3C04, 0x000F3C08, 0x000F3C0C,
    0x000F3C10, 0x000F3C14, 0x000F3C18, 0x000F3C1C,
    0x000F3C20, 0x000F3C24, 0x000F3C28, 0x000F3C2C,
    0x000F3C30, 0x000F3C34, 0x000F3C38, 0x000F3C3C,
    0x000F3C40, 0x000F3C44, 0x000F3C48, 0x000F3C4C,
    0x000F3C50, 0x000F3C54, 0x000F3C58, 0x000F3C5C,
    0x000F3C60, 0x000F3C64, 0x000F3C68, 0x000F3C6C,
    0x000F3C70, 0x000F3C74, 0x000F3C78, 0x000F3C7C,
    0x000F3C80, 0x000F3C84, 0x000F3C88, 0x000F3C8C,
    0x000F3C90, 0x000F3C94, 0x000F3C98, 0x000F3C9C,
    0x000F3CA0, 0x000F3CA4, 0x000F3CA8, 0x000F3CAC,
    0x000F3CB0, 0x000F3CB4, 0x000F3CB8, 0x000F3CBC,
    0x000F3CC0, 0x000F3CC4, 0x000F3CC8, 0x000F3CCC,
    0x000F3CD0, 0x000F3CD4, 0x000F3CD8, 0x000F3CDC,
    0x000F3CE0, 0x000F3CE4, 0x000F3CE8, 0x000F3CEC,
    0x000F3CF0, 0x000F3CF4, 0x000F3CF8, 0x000F3CFC,
    0x000F3D00, 0x000F3D04, 0x000F3D08, 0x000F3D0C,
    0x000F3D10, 0x000F3D14, 0x000F3D18, 0x000F3D1C,
    0x000F3D20, 0x000F3D24, 0x000F3D28, 0x000F3D2C,
    0x000F3D30, 0x000F3D34, 0x000F3D38, 0x000F3D3C,
    0x000F3D40, 0x000F3D44, 0x000F3D48, 0x000F3D4C,
    0x000F3D50, 0x000F3D54, 0x000F3D58, 0x000F3D5C,
    0x000F3D60, 0x000F3D64, 0x000F3D68, 0x000F3D6C,
    0x000F3D70, 0x000F3D74, 0x000F3D78, 0x000F3D7C,
    0x000F3D80, 0x000F3D84, 0x000F3D88, 0x000F3D8C,
    0x000F3D90, 0x000F3D94, 0x000F3D98, 0x000F3D9C,
    0x000F3DA0, 0x000F3DA4, 0x000F3DA8, 0x000F3DAC,
    0x000F3DB0, 0x000F3DB4, 0x000F3DB8, 0x000F3DBC,
    0x000F3DC0, 0x000F3DC4, 0x000F3DC8, 0x000F3DCC,
    0x000F3DD0, 0x000F3DD4, 0x000F3DD8, 0x000F3DDC,
    0x000F3DE0, 0x000F3DE4, 0x000F3DE8, 0x000F3DEC,
    0x000F3DF0, 0x000F3FB0, 0x000F3FB4, 0x000F3FB8,
    0x000F3FBC, 0x000F3FC0, 0x000F3FC4, 0x000F3FC8,
    0x000F3FCC, 0x000F3FD0, 0x000F3FD4, 0x000F3FD8,
    0x000F3FDC, 0x002EA7A4,
)

_WORDS = (
    0x8E04045C, 0x10800079, 0x00000000, 0x30810003,
    0x14200076, 0x00000000, 0x3C010200, 0x0081082B,
    0x10200072, 0x00000000, 0x8C85002C, 0x10A0006F,
    0x00000000, 0x30A10003, 0x1420006C, 0x00000000,
    0x3C010200, 0x00A1082B, 0x10200068, 0x00000000,
    0x8CA60000, 0x10C00065, 0x00000000, 0x30C10003,
    0x14200062, 0x00000000, 0x3C010200, 0x00C1082B,
    0x1020005E, 0x00000000, 0x8CC70520, 0x10E0005B,
    0x00000000, 0x30E10003, 0x14200058, 0x00000000,
    0x3C010200, 0x00E1082B, 0x10200054, 0x00000000,
    0x8CE9056C, 0x05200051, 0x00000000, 0x3C08000F,
    0x25083FE0, 0xC60000B0, 0x8D0A0004, 0x8D0B0000,
    0xAD070004, 0xAD090000, 0x11470004, 0x00000000,
    0xAD000010, 0x10000010, 0x00000000, 0x012B082A,
    0x1020000D, 0x00000000, 0x8D0CFFF8, 0x0189082A,
    0x14200009, 0x00000000, 0x8D010010, 0x14200005,
    0x00000000, 0xC4C10458, 0xE5010014, 0x24010001,
    0xAD010010, 0xE5000008, 0x8D010010, 0x10200033,
    0x00000000, 0xC5020008, 0x46020081, 0xC503FFD0,
    0x46031034, 0x00000000, 0x45010029, 0x00000000,
    0xC504FFF4, 0x46041034, 0x00000000, 0x45000024,
    0x00000000, 0xC505FFE8, 0x46051034, 0x00000000,
    0x4501000B, 0x00000000, 0xC506FFEC, 0x46061034,
    0x00000000, 0x4501000A, 0x00000000, 0x460221C1,
    0xC508FFF0, 0x460839C2, 0x10000006, 0x00000000,
    0xC508FFE4, 0x460811C2, 0x10000002, 0x00000000,
    0xC507FFD4, 0xC509FFD4, 0xC50AFFD8, 0xC50BFFDC,
    0x46075282, 0x460A5AC1, 0x46073A02, 0x460B4202,
    0xC506FFFC, 0x46083182, 0x46093180, 0xC5050014,
    0x46053182, 0xE4C60458, 0x10000004, 0x00000000,
    0xC5050014, 0xE4C50458, 0xAD000010, 0x0806016C,
    0x00000000, 0x00000000, 0x3F800000, 0x40000000,
    0x40400000, 0x3E99999A, 0x40D55555, 0x3E19999A,
    0x3F333333, 0x3FD55555, 0x3FA66666, 0x00000001,
    0xBF333333, 0x0C03CF00,
)


def words(preset: str = PRESET_DEFAULT, threshold: str = THRESHOLD_DEFAULT):
    """[(va, word)] for the cave, with the preset and trigger patched in."""
    if preset not in PRESETS:
        raise SlomoError("no such slow-motion preset: %r" % (preset,))
    if threshold not in THRESHOLDS:
        raise SlomoError("no such slow-motion trigger: %r" % (threshold,))
    const = dict(zip(_CONST_VAS, _CONST[(preset, threshold)]))
    out = []
    for va, w in zip(_VAS, _WORDS):
        if STATE <= va < STATE_END:
            raise SlomoError("the cave's own state must never be emitted")
        out.append((va, const.get(va, w)))
    return out


def reads(word_at) -> bool:
    """True if `word_at(va)` shows the hook in place."""
    return word_at(HOOK_AT) != HOOK_STOCK


def cards(prefix, group):
    from .model import BOOL, CHOICE, Choice, Setting

    return [
        Setting(
            prefix + "slomo", "Slow time when a room goes quiet", BOOL,
            False, group, confidence="experimental", touches="ram",
            help="When the last enemy in an area goes down, time slows for "
                 "about a second and eases back.\n\n"
                 "It is the engine's own time scale, so everything slows "
                 "together -- bodies, smoke, your own movement -- rather "
                 "than the picture alone.",
            caution="Not yet played.\n\n"
                    "The sound does NOT slow with it. The audio system is "
                    "updated with the undilated clock and the game has no "
                    "pitch control left in it, so gunfire and music keep "
                    "normal speed over a slowed picture. For about a second "
                    "that reads as stylised; it is why nothing longer is "
                    "offered.\n\n"
                    "In split screen the clock is shared, so both players "
                    "slow down together."),
        Setting(
            prefix + "slomo_strength", "How slow, and for how long", CHOICE,
            PRESET_DEFAULT, group,
            requires={prefix + "slomo": [True]},
            choices=[Choice("gentle", "Gentle", "Half speed, briefly."),
                     Choice("normal", "Normal"),
                     Choice("heavy", "Heavy",
                            "Down to about a fifth. The most the clamp "
                            "usefully allows.")],
            help="Nothing slower is offered because the engine floors its "
                 "own delta time: past this point the picture stops getting "
                 "slower and starts depending on the frame rate instead."),
        Setting(
            prefix + "slomo_when", "Which kill starts it", CHOICE,
            THRESHOLD_DEFAULT, group,
            requires={prefix + "slomo": [True]},
            choices=[Choice("last", "The last enemy alive"),
                     Choice("final_two", "The last two"),
                     Choice("any_kill", "Every kill",
                            "Constant, and almost certainly too much.")],
            help="It reads the game's own list of living terrorists, so it "
                 "counts everyone still up in the level rather than only "
                 "the ones you can see."),
    ]

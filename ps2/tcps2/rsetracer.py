"""Tracer rounds coloured by the cartridge they came from.

The game already draws tracers, and it does it natively -- not with a particle
emitter. One manager hangs off `ULevel + 0x7AD8`; it holds a plain array of
64-byte records, each one a 3.6-metre dash that leaves the muzzle and travels
along the bullet's own ray at 60 m/s until it reaches the impact point. The
manager is ticked from `ULevel::Tick` and drawn from the render walk, and the
dash is drawn as a two-point line with a colour at each end.

Why every gun looks the same
----------------------------

Not because the colour is a constant in the draw. The renderer picks a pair of
colours out of `Engine.R6GameplaySettings` according to whether the shooter is
Rainbow or a terrorist -- `m_BulletTracersRainbowHeadColor` and its three
siblings -- and **all four of them hold the same value**, the dword 0x00FFFF80,
which in this engine's byte order is R=255 G=255 B=128: pale yellow. So the
machinery to vary the colour is already there and nothing varies.

What this does
--------------

Each record has two words nothing in the game ever touches. They become the
record's own colour pair, and four one-word edits in the renderer point it at
them instead of at the global pair. One hooked word in the add wrapper fills
them in, and it is the right place to hook because all four of the game's
tracer-add sites go through that wrapper with the firing weapon in `$a0`.

Where the cartridge comes from
------------------------------

There is no calibre field anywhere in this build -- the HUD's "FAMAS G2
(5.56MM)" is a localisation string with no number beside it. What there IS is
`m_pEmptyShells`, the shell-casing class, set on every firearm and set PER
CARTRIDGE: nineteen `R6Shell*` classes, one per round. Its name index is the
calibre, and unlike the weapon class names those indices are the same in every
load, measured across four images from three different maps.

A weapon whose cartridge is not in the table -- and every grenade and gadget,
which carry none at all -- falls back to the pair the game would have used, so
nothing regresses and nothing new can be silently wrong.

What it costs
-------------

Nothing to draw. It adds no tracer, no record, no heap and no per-frame work;
the four renderer edits are the same instruction with a different base. The
only new code runs once per tracer as it is created, which at a rifle's rate of
fire is a few dozen instructions a frame.

The cadence, and a thing worth knowing
--------------------------------------

The game CREATES a tracer record for every round, but three filters decide
which of them you ever see, and the biggest one hides your own.

`m_u8BulletPerTracer` is an on/off switch, not a frequency. The "one round in
N" modulo lives in a block gated on `NetMode == 3`, i.e. network clients only,
so it never runs on PS2 -- measured: NetMode (`LevelInfo +0x422`) is 0 in all
eight loaded EE dumps, six of them SPLIT SCREEN, and the timestamp that block
writes, `m_fLastBulletTracerTime` (`R6Weapons +0x4F8`), reads zero on all 322
live weapons. The field itself is only ever 1 or 2 -- a pure function of
`m_eWeaponType` -- and 0 on every grenade and launcher, so it could not be a
one-in-thirty frequency even if the block ran.

What thins them is elsewhere, and it is three separate gates:

* **You never see your own.** The add stamps the firing player's local
  viewport index into the record at `+0x34` (`0x00406C3C`), and the line draw
  at `0x00195110` refuses a line whose stamp matches the viewport being drawn
  -- or refuses it outright when the current viewport tag is 0, which is what
  single player reports. Measured: tag 0 in both single-player dumps, 2 in all
  six split-screen ones. So in split screen each player sees only the OTHER
  player's tracers. `tracer_visible` zeroes the stamp.
* **AI fire is cone-gated to 2.00 degrees.** On the non-player path only, the
  round must leave within `cos 2.0013` of the shooter pawn's forward axis or
  no record is added at all (`0x003F3098`). That is an effective minimum range
  of roughly 6-15 metres and it fails whenever an AI is turning while firing.
  `tracer_visible` can remove it or widen it to 15 degrees.
* **A range floor.** The start is pushed 100 units down the ray and the add
  refuses anything shorter than `m_fBulletTracersLength` (360), so the round
  must land past 4.6 m. Left alone: it is a live `R6GameplaySettings` float,
  so it is a config change rather than a word edit.

Thinning further needs the three calls in the bullet path redirected, which
`tracer_every` does. Of those three, `0x003F32D0` is the `NetMode != 0` arm
and is dead on PS2.

Not established
---------------
* How the colours read in motion. The dash is short and fast and the engine
  already halves the brightness of every other one.
* No savestate caught a tracer alive, so the record layout is read off the
  three functions that write, update and draw it rather than off live data.
* The cartridge key is a name index. It is the same in four images, but if a
  future load ever shifted the name table a weapon would take a neighbour's
  colour, or fall back to yellow. It cannot crash and it cannot go quiet.
"""


from __future__ import annotations


class TracerError(Exception):
    pass


# ------------------------------------------------------- the hook ---
#: `sd $ra, 0($sp)` -- the add wrapper's own return-address save, and
#: the first word after it opens its frame. The cave replays it, so the
#: wrapper is bit-exact rather than relying on the store being dead.
HOOK_AT = 0x00406D14
HOOK_STOCK = 0xFFBF0000
#: `j 0x000F4400`
HOOK = 0x0803D100

#: The four renderer words. Each was `addiu $a0, $v0, <settings
#: colour>` and becomes `addiu $a0, $s0, <record colour>`; `$s0` is
#: the renderer's record cursor and is provably untouched across all
#: four sites. Nothing else in the renderer moves, so the brightness
#: alternation and the distance fade still apply.
COLOUR_WORDS = (
    (0x004063D4, 0x24440344, 0x26040038),
    (0x00406424, 0x24440340, 0x2604003C),
    (0x0040647C, 0x2444034C, 0x26040038),
    (0x004064CC, 0x24440348, 0x2604003C),
)

#: The three tracer-add calls inside the bullet path. Redirected only
#: when the cadence is thinned; left alone at one tracer per round.
THIN_WORDS = (
    (0x003F3150, 0x0C101B44, 0x0C03D150),
    (0x003F3210, 0x0C101B44, 0x0C03D150),
    (0x003F32D0, 0x0C101B44, 0x0C03D150),
)

BLOCK = 0x000F4400
BLOCK_END = 0x000F5000
ADD_CAVE = 0x000F4400
THIN_CAVE = 0x000F4540
PALETTE_AT = 0x000F4580
INDEX_AT = 0x000F4600

#: One tracer every N rounds. 1 is what the game does today.
THIN_AT = 0x000F454C
THIN_DEFAULT = 1
THIN_MAX = 255

#: `m_pEmptyShells` name index -> palette slot. The band is tight:
#: 12980..13088, 109 slots, and every one of the nineteen cartridges is in it.
FN_BASE = 12980
FN_SPAN = 109
SHELLS = {
    12980: (5, 'R6Shell545mm7N6'),
    13028: (3, 'R6Shell556mmNATO'),
    13029: (3, 'R6Shell57mm'),
    13030: (5, 'R6Shell762mmm43'),
    13031: (4, 'R6Shell762mmNATO'),
    13033: (4, 'R6Shell762mmNATO_B'),
    13034: (2, 'R6Shell765mmAuto'),
    13043: (1, 'R6Shell9mmParabellum'),
    13044: (1, 'R6Shell9mmSP6'),
    13045: (1, 'R6Shell9x21mmR'),
    13056: (2, 'R6Shell10mmAuto'),
    13069: (6, 'R6Shell12GaugeBuck'),
    13076: (6, 'R6Shell12GaugeSlug'),
    13077: (2, 'R6Shell357calMagnum'),
    13078: (2, 'R6Shell40calAuto'),
    13080: (2, 'R6Shell45calAuto'),
    13082: (7, 'R6Shell50calM33'),
    13088: (2, 'R6Shell50calPistol'),
}

PALETTES = {
    'calibre': {
        0: (0x00FFFF80, 0x00FFFF80),
        1: (0x00FFFF80, 0x00FFFF80),
        2: (0x00FFB030, 0x00FFB030),
        3: (0x00FF7030, 0x00FF7030),
        4: (0x00FF4030, 0x00FF4030),
        5: (0x0070FF70, 0x0070FF70),
        6: (0x00FFE8C8, 0x00FFE8C8),
        7: (0x0090C8FF, 0x0090C8FF),
    },
    'natosoviet': {
        0: (0x00FFFF80, 0x00FFFF80),
        1: (0x00FFFF80, 0x00FFFF80),
        2: (0x00FFFF80, 0x00FFFF80),
        3: (0x00FF5030, 0x00FF5030),
        4: (0x00FF5030, 0x00FF5030),
        5: (0x0070FF70, 0x0070FF70),
        6: (0x00FFE8C8, 0x00FFE8C8),
        7: (0x00FF5030, 0x00FF5030),
    },
    'red': {
        0: (0x00FF4830, 0x00FF4830),
        1: (0x00FF4830, 0x00FF4830),
        2: (0x00FF4830, 0x00FF4830),
        3: (0x00FF4830, 0x00FF4830),
        4: (0x00FF4830, 0x00FF4830),
        5: (0x00FF4830, 0x00FF4830),
        6: (0x00FF4830, 0x00FF4830),
        7: (0x00FF4830, 0x00FF4830),
    },
    'green': {
        0: (0x0078FF78, 0x0078FF78),
        1: (0x0078FF78, 0x0078FF78),
        2: (0x0078FF78, 0x0078FF78),
        3: (0x0078FF78, 0x0078FF78),
        4: (0x0078FF78, 0x0078FF78),
        5: (0x0078FF78, 0x0078FF78),
        6: (0x0078FF78, 0x0078FF78),
        7: (0x0078FF78, 0x0078FF78),
    },
    'white': {
        0: (0x00F0F8FF, 0x00F0F8FF),
        1: (0x00F0F8FF, 0x00F0F8FF),
        2: (0x00F0F8FF, 0x00F0F8FF),
        3: (0x00F0F8FF, 0x00F0F8FF),
        4: (0x00F0F8FF, 0x00F0F8FF),
        5: (0x00F0F8FF, 0x00F0F8FF),
        6: (0x00F0F8FF, 0x00F0F8FF),
        7: (0x00F0F8FF, 0x00F0F8FF),
    },
}
PALETTE_DEFAULT = 'calibre'

#: Measured: the dword all four shipped tracer colours hold.
SHIPPED_YELLOW = 0x00FFFF80

_WORDS = (
    0xFFBF0000, 0xAFA40008, 0x27A90010, 0x78A20000,
    0x27A30020, 0x7D220000, 0x0120282D, 0x78C20000,
    0x7C620000, 0x8C8202E4, 0x1040003E, 0x0060302D,
    0x8C447AD8, 0x1080003B, 0x00000000, 0x8C8A001C,
    0xAFAA000C, 0x0C101A98, 0x00000000, 0x8FA40008,
    0x8C8202E4, 0x10400033, 0x00000000, 0x8C437AD8,
    0x10600030, 0x00000000, 0x8C6A001C, 0x8FAB000C,
    0x114B002C, 0x00000000, 0x1940002A, 0x00000000,
    0x8C6C0018, 0x11800027, 0x254AFFFF, 0x000A6980,
    0x018D6021, 0x8C8E0544, 0x11C00015, 0x00000000,
    0x31C10003, 0x14200012, 0x00000000, 0x8DCF0020,
    0x25EFCD4C, 0x2DE1006D, 0x1020000D, 0x00000000,
    0x3C18000F, 0x030FC021, 0x93194600, 0x13200008,
    0x00000000, 0x0019C8C0, 0x3C18000F, 0x0319C021,
    0x8F0A4580, 0x8F0B4584, 0x1000000C, 0x00000000,
    0x8F989900, 0x1300000B, 0x8D99002C, 0x13200005,
    0x00000000, 0x8F0A0344, 0x8F0B0340, 0x10000003,
    0x00000000, 0x8F0A034C, 0x8F0B0348, 0xAD8A0038,
    0xAD8B003C, 0xDFBF0000, 0x03E00008, 0x27BD0030,
    0x908A04D0, 0x1140000C, 0x908B04D1, 0x240C0001,
    0x11800009, 0x00000000, 0x016C001B, 0x00000000,
    0x00000000, 0x00006810, 0x15A00003, 0x00000000,
    0x08101B44, 0x00000000, 0x03E00008, 0x00000000,
    0x00FFFF80, 0x00FFFF80, 0x00FFFF80, 0x00FFFF80,
    0x00FFB030, 0x00FFB030, 0x00FF7030, 0x00FF7030,
    0x00FF4030, 0x00FF4030, 0x0070FF70, 0x0070FF70,
    0x00FFE8C8, 0x00FFE8C8, 0x0090C8FF, 0x0090C8FF,
    0x00000005, 0x00000000, 0x00000000, 0x00000000,
    0x00000000, 0x00000000, 0x00000000, 0x00000000,
    0x00000000, 0x00000000, 0x00000000, 0x00000000,
    0x04050303, 0x00020400, 0x00000000, 0x01000000,
    0x00000101, 0x00000000, 0x00000000, 0x00000002,
    0x00000000, 0x00000000, 0x00000600, 0x00000000,
    0x00020206, 0x00070002, 0x00000000, 0x00000002,
)

#: The VA of _WORDS[i].
_VAS = (
    0x000F4400, 0x000F4404, 0x000F4408, 0x000F440C, 0x000F4410, 0x000F4414,
    0x000F4418, 0x000F441C, 0x000F4420, 0x000F4424, 0x000F4428, 0x000F442C,
    0x000F4430, 0x000F4434, 0x000F4438, 0x000F443C, 0x000F4440, 0x000F4444,
    0x000F4448, 0x000F444C, 0x000F4450, 0x000F4454, 0x000F4458, 0x000F445C,
    0x000F4460, 0x000F4464, 0x000F4468, 0x000F446C, 0x000F4470, 0x000F4474,
    0x000F4478, 0x000F447C, 0x000F4480, 0x000F4484, 0x000F4488, 0x000F448C,
    0x000F4490, 0x000F4494, 0x000F4498, 0x000F449C, 0x000F44A0, 0x000F44A4,
    0x000F44A8, 0x000F44AC, 0x000F44B0, 0x000F44B4, 0x000F44B8, 0x000F44BC,
    0x000F44C0, 0x000F44C4, 0x000F44C8, 0x000F44CC, 0x000F44D0, 0x000F44D4,
    0x000F44D8, 0x000F44DC, 0x000F44E0, 0x000F44E4, 0x000F44E8, 0x000F44EC,
    0x000F44F0, 0x000F44F4, 0x000F44F8, 0x000F44FC, 0x000F4500, 0x000F4504,
    0x000F4508, 0x000F450C, 0x000F4510, 0x000F4514, 0x000F4518, 0x000F451C,
    0x000F4520, 0x000F4524, 0x000F4528, 0x000F452C, 0x000F4540, 0x000F4544,
    0x000F4548, 0x000F454C, 0x000F4550, 0x000F4554, 0x000F4558, 0x000F455C,
    0x000F4560, 0x000F4564, 0x000F4568, 0x000F456C, 0x000F4570, 0x000F4574,
    0x000F4578, 0x000F457C, 0x000F4580, 0x000F4584, 0x000F4588, 0x000F458C,
    0x000F4590, 0x000F4594, 0x000F4598, 0x000F459C, 0x000F45A0, 0x000F45A4,
    0x000F45A8, 0x000F45AC, 0x000F45B0, 0x000F45B4, 0x000F45B8, 0x000F45BC,
    0x000F4600, 0x000F4604, 0x000F4608, 0x000F460C, 0x000F4610, 0x000F4614,
    0x000F4618, 0x000F461C, 0x000F4620, 0x000F4624, 0x000F4628, 0x000F462C,
    0x000F4630, 0x000F4634, 0x000F4638, 0x000F463C, 0x000F4640, 0x000F4644,
    0x000F4648, 0x000F464C, 0x000F4650, 0x000F4654, 0x000F4658, 0x000F465C,
    0x000F4660, 0x000F4664, 0x000F4668, 0x000F466C,
)


def words(thin: int = THIN_DEFAULT, palette: str = PALETTE_DEFAULT):
    """[(va, word)] for the cave, with the cadence and the palette in."""
    if not 1 <= int(thin) <= THIN_MAX:
        raise TracerError('tracer cadence %r is outside 1..%d'
                          % (thin, THIN_MAX))
    if palette not in PALETTES:
        raise TracerError('unknown tracer palette %r' % (palette,))
    pal = PALETTES[palette]
    out = []
    for va, w in zip(_VAS, _WORDS):
        if va == THIN_AT:
            w = (w & 0xFFFF0000) | int(thin)
        elif PALETTE_AT <= va < PALETTE_AT + 8 * len(pal):
            i, half = divmod((va - PALETTE_AT) // 4, 2)
            w = pal[i][half]
        out.append((va, w))
    out.append((HOOK_AT, HOOK))
    return out


def disc_words(thin: int = THIN_DEFAULT):
    """[(va, new, stock)] -- the game words, for WordEdit."""
    out = [(va, new, stock) for va, stock, new in COLOUR_WORDS]
    if int(thin) > 1:
        out += [(va, new, stock) for va, stock, new in THIN_WORDS]
    return out


def reads(word_at) -> bool:
    """True if `word_at(va)` shows the hook and the renderer edits in place."""
    if word_at(HOOK_AT) != HOOK:
        return False
    return all(word_at(va) == new for va, _, new in COLOUR_WORDS)


# ------------------------------------------------- the visibility gates ---

#: The add stamps the firing player's local viewport index into the record,
#: and the line draw then refuses that line in that same viewport -- so a
#: player never sees his own tracers, and in single player, where the current
#: viewport tag reads 0, they are dropped outright.
#:
#: `0x00406C3C` is the delay slot of `beqz $s2, 0x00406C58` at `0x00406C38`.
#: A delay-slot instruction runs on both paths, the branch tests `$s2` which
#: this store does not write, and `record+0x34` is not read again inside the
#: add -- its only reader in the whole overlay is `lw $t1,0x34($s0)` at
#: `0x004068B8`. So zeroing the stamp is safe and makes every record
#: viewport-agnostic.
OWNTRACER_AT = 0x00406C3C
OWNTRACER_STOCK = 0xAE110034        # sw $s1, 0x34($s0)
OWNTRACER = 0xAE000034              # sw $zero, 0x34($s0)

#: A 2.00-degree cone on the NON-player path only: the round must leave
#: within `cos 2.0013` of the shooter pawn's forward axis or no record is
#: added. Its delay slot `0x003F309C` is already a `nop`, so the branch can
#: simply go away; the `c.ole.s` above it still runs and its result is then
#: unused. `$f0..$f3` are scratch and the player path reloads from
#: `0x003F30A0`.
#:
#: The gate exists because an AI's tracer is drawn from its VISIBLE
#: third-person muzzle, so a round well off the barrel axis looks slightly
#: misaligned with the model. `wide` is the middle course: the same test at
#: 15 degrees instead of 2.
AICONE_AT = 0x003F3098
AICONE_STOCK = 0x4501008F           # bc1t 0x003F32D8
AICONE_OFF = 0x00000000             # nop
#: `cos 15 deg` = 0.9659258, in the lui/ori pair that builds the constant.
AICONE_WIDE = (
    (0x003F3068, 0x3C023F7F, 0x3C023F77),
    (0x003F3070, 0x3442D806, 0x344246EA),
)

VISIBLE = ("stock", "own", "own_and_ai_wide", "own_and_ai")
VISIBLE_DEFAULT = "stock"


def visible_words(mode: str = VISIBLE_DEFAULT):
    """[(va, new, stock)] for the visibility gates."""
    if mode not in VISIBLE:
        raise TracerError("no such tracer visibility mode: %r" % (mode,))
    if mode == "stock":
        return []
    out = [(OWNTRACER_AT, OWNTRACER, OWNTRACER_STOCK)]
    if mode == "own_and_ai":
        out.append((AICONE_AT, AICONE_OFF, AICONE_STOCK))
    elif mode == "own_and_ai_wide":
        out += [(va, new, stock) for va, stock, new in AICONE_WIDE]
    return out


def visible_stock_words():
    """{va: stock} for every word any visibility mode touches."""
    out = {OWNTRACER_AT: OWNTRACER_STOCK, AICONE_AT: AICONE_STOCK}
    out.update({va: stock for va, stock, _new in AICONE_WIDE})
    return out


def cards(prefix, group):
    from .model import BOOL, CHOICE, Choice, Setting

    return [
        Setting(
            prefix + "tracer_visible", "Whose tracers you can see", CHOICE,
            VISIBLE_DEFAULT, group, confidence="experimental",
            touches="code", pnach_only=True,
            choices=[
                Choice("stock", "As shipped",
                       "You never see your own; in split screen you see "
                       "only the other player's."),
                Choice("own", "Your own as well",
                       "One word. Nothing else changes."),
                Choice("own_and_ai_wide", "Your own, and more from the AI",
                       "Also widens the AI firing cone from 2 degrees "
                       "to 15."),
                Choice("own_and_ai", "Your own, and all of the AI's",
                       "Removes the AI cone entirely."),
            ],
            help="The game draws a tracer for every round fired, then "
                 "hides most of them from you.\n\n"
                 "It stamps each tracer with the viewport of whoever "
                 "fired it, and then refuses to draw it in that same "
                 "viewport -- so you never see your own. In split screen "
                 "that means each of you only ever sees the other's.\n\n"
                 "Separately, a tracer from an AI is only drawn if the "
                 "round leaves within two degrees of the way the shooter "
                 "is facing, which throws away most of their fire at "
                 "close range and all of it while they are turning.",
            caution="Not yet played.\n\n"
                    "The AI cone is there for a reason: their tracer is "
                    "drawn from the visible third-person muzzle, so a "
                    "round well off the barrel line can look slightly "
                    "misaligned with the model. The 15-degree setting is "
                    "the middle course if the full removal looks "
                    "wrong.\n\n"
                    "More tracers drawn is more lines on screen. If the "
                    "frame rate suffers in a heavy firefight, thin them "
                    "out with the option below."),
        Setting(
            prefix + 'tracer_calibre',
            'Tracer rounds are coloured by the cartridge',
            BOOL, False, group,
            confidence='experimental', touches='none',
            help='The game already draws tracers, and every gun draws the '
                 'same pale yellow. That is not a colour baked into the '
                 'draw: the renderer picks from four settings according to '
                 'who fired, and all four hold the same value.\n\n'
                 'This gives each cartridge its own colour, taken from the '
                 'shell casing the weapon ejects -- which is the only thing '
                 'in the game that actually knows what round it fires. '
                 'Nine millimetre is left exactly as it is now.',
            caution='Nothing new is drawn, so it costs no frame rate. A '
                    'weapon whose cartridge is not in the table keeps '
                    'today\'s yellow rather than going wrong.'),
        Setting(
            prefix + 'tracer_palette', 'Which colours',
            CHOICE, PALETTE_DEFAULT, group,
            requires={prefix + 'tracer_calibre': (True,)},
            choices=[Choice('calibre', 'One per cartridge'),
                     Choice('natosoviet', 'Two sides: NATO red, Soviet green'),
                     Choice('red', 'All red'),
                     Choice('green', 'All green'),
                     Choice('white', 'All white')],
            help='One per cartridge is the point of the change. The other '
                 'four are there because one colour for everything is still '
                 'better than yellow for everything, and they cost exactly '
                 'the same.'),
        Setting(
            prefix + 'tracer_every', 'How often a round is a tracer',
            CHOICE, '1', group,
            requires={prefix + 'tracer_calibre': (True,)},
            choices=[Choice('1', 'Every round, as the game does now'),
                     Choice('2', 'Every second round'),
                     Choice('3', 'Every third round'),
                     Choice('5', 'Every fifth round')],
            help='Real tracer belts carry one in four or five. In single '
                 'player this game puts one on every round -- the cadence '
                 'it has for that only runs on a network client, so single '
                 'player never reaches it.\n\n'
                 'Thinning them out is the difference between a light show '
                 'and a firefight, and it is also fewer lines to draw.',
            caution='This one redirects three calls in the bullet path '
                    'rather than changing a constant, so it is the more '
                    'invasive of the two.'),
    ]

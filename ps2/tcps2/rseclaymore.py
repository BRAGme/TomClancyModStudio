"""The claymore as a proximity mine, as a PCSX2 code cave.

What the game ships
-------------------

A placed claymore does nothing until the player presses the detonator:
`R6DemolitionsGadget.ServerDetonate` clears `m_bDetonator` and calls
`BulletActor.Explode()`, and `R6DemolitionsUnit.Explode()` is
`Super.Explode(); SelfDestroy();`. There is no proximity anywhere -- the
strings `Proximity`, `Tripwire`, `Sensor`, `Mine` and `Alarm` do not appear in
the overlay at all, and `R6ClaymoreUnit` has exactly ONE member function in
its package (`HurtPawns`): no Tick, no Timer, no Touch, no state.

Why this needs no script edit
-----------------------------

The class already LISTENS for a timer. `FStateFrame::ProbeMask` on a placed
claymore reads `0x0000000000000B00` -- bits 8/9/11, Timer, HitWall, Landed
(measured on the live instance, not just the class default). And
`R6Grenade.Timer` is five bytes of bytecode, `1b 10 16 04 0b` =
`Explode(); return;`.

So the cave never calls script. It writes two floats into the actor::

    TimerRate    (+0x8C) = 0.01     AActor::UpdateTimers -> NAME_Timer
    TimerCounter (+0x90) = 1.0      -> R6Grenade.Timer() -> Explode()

and the engine does the rest, down exactly the path the detonator uses. The
manual detonator is untouched: `MyUnitIsDestroyed` -> `ClientMyUnitIsDestroyed`
already clears `m_bDetonator`, `m_bDetonated` and `m_bChargeInPosition` and
re-enters `NoChargesLeft`/`GetNextCharge`, so the player's own gadget cleans
itself up whichever way the charge went off.

What the cave does each frame
-----------------------------

Hooks the group-2 actor-tick call in `ULevel::Tick` at `0x00223B84` (a `jal`
whose return value is dead -- `$v0` is rewritten at `0x00223B8C` -- so the cave
rebuilds `$ra` by hand and jumps to the displaced `0x00224140` with `$a0`-`$a3`
and `$f12` untouched). Then it walks `ULevel.Actors` for an actor whose
`Class->Name` is FName **16272** (`R6ClaymoreUnit`), skips one already armed,
clears the dormancy bit, and walks `LevelInfo.ControllerList` testing SQUARED
distance against live pawns whose `m_ePawnType` is 2 (PAWN_Terrorist).

**That last filter is load-bearing, not a nicety.** Measured on the user's
savestate 3: the nearest terrorist was 15.09 m away, but a Rainbow teammate
was **1.72 m** from the charge and the player himself 3.00 m. Without the
filter, a 2 m or 3 m trigger would have killed the team.

Cost, counted over that real actor array (1,869 actors, 41 controllers):
**18,389 instructions in the frame**, about 1.1 M/s at 60 fps -- 0.37% of a
294 MHz EE at one instruction per cycle.

Where it lives, and the trap that moved it
------------------------------------------

`0x000F0000`, in EE RAM **below** the ELF load base. `0x000CAA18..0x00100000`
is zero in all 89 savestate files across three boot CRCs; the highest non-zero
byte below the load base is `0x00083FFF`, leaving 0x6C000 of margin, and the
allocator grows UP from `0x00100000` so it cannot reach down.

It was first placed at `0x005C2A40` -- the only run in the overlay with no
code reference, no data reference, and all-zero contents in the image and in
every savestate. **That was still wrong**, and the reason is worth keeping:
`0x004D3068` indexes an audio pan table based at `0x005C2940` with
`andi $t1, $a1, 0xff`, and that table has 64 non-zero entries followed by 65
zero ones. The "clean run" was simply the tail of a table the game indexes at
runtime, so a pan index of 0 would have read a cave word as a dB value --
silent audio corruption, not a crash.

**So "no static references" is not sufficient for image data.** Any zero run
inside the image can be reached by a runtime index off a nearby base. The same
trap was then found at `0x005B4344` (immediately after a buffer base a
selector at `0x0013422C` returns) and at `0x005B2620`. RAM below the load base
has no such base pointer near it.

Also do not use the `0x005BA488` run that `wave_mapwide` occupies -- the
command-line parser builds its resolved boot path at `0x005BA500`, inside it.

Delivered as a cheat file, not written to the disc, for the same reason the
map-wide picker is: a code cave baked into the overlay does not survive a
level load.

Not established
---------------

* ~~That PCSX2 applies a pnach row below `0x00100000`.~~ **CONFIRMED IN
  PLAY 2026-09-25**: a claymore placed in front of a closed door
  self-detonated, which it can only do if this cave executed. Low RAM is
  a working cave home, and space there is effectively unlimited.
* That the timer actually fires for a claymore the player has walked away
  from. The dormancy bit at `+0x6F` reads CLEAR on the live instance, so the
  cave's clear of it is a no-op today; it is kept as three words of insurance
  against the one failure mode ("stops working once off-screen") that would be
  near-impossible to diagnose from play.
* The trigger is a SPHERE. The blast keeps its own 40-degree forward cone, so
  a terrorist approaching from behind sets it off and survives. A real cone
  test needs trigonometry that does not fit in the three spare words.
"""

from __future__ import annotations

import struct

#: `jal 0x00224140` in ULevel::Tick -> `j 0x000F0000`
HIJACK = (0x00223B84, 0x0803C000)
HIJACK_STOCK = 0x0C089050

#: The all-round build: a plain sphere, 65 words. This is what shipped first
#: and what the user played -- kept because it is the smaller, simpler cave and
#: someone may prefer a mine that cannot be walked around.
ALLROUND_WORDS = [
    (0x000F0000, 0x8E88002C), (0x000F0004, 0x8E890030),
    (0x000F0008, 0x1100003B), (0x000F000C, 0x3C18471C),
    (0x000F0010, 0x19200039), (0x000F0014, 0x8D0A0000),
    (0x000F0018, 0x37184000), (0x000F001C, 0x11400036),
    (0x000F0020, 0x44985000), (0x000F0024, 0x8D4A0528),
    (0x000F0028, 0x11400033), (0x000F002C, 0x240B3F90),
    (0x000F0030, 0x8D0C0000), (0x000F0034, 0x25080004),
    (0x000F0038, 0x1180002E), (0x000F003C, 0x2529FFFF),
    (0x000F0040, 0x8D8D0024), (0x000F0044, 0x8DAD0020),
    (0x000F0048, 0x15AB002A), (0x000F004C, 0x8D8D008C),
    (0x000F0050, 0x15A00028), (0x000F0054, 0x918E006F),
    (0x000F0058, 0x31CE00EF), (0x000F005C, 0xA18E006F),
    (0x000F0060, 0xC58001B0), (0x000F0064, 0xC58101B4),
    (0x000F0068, 0xC58201B8), (0x000F006C, 0x254F0000),
    (0x000F0070, 0x11E00020), (0x000F0074, 0x24030002),
    (0x000F0078, 0x8DF903AC), (0x000F007C, 0x1320001B),
    (0x000F0080, 0x00000000), (0x000F0084, 0x93220378),
    (0x000F0088, 0x14430018), (0x000F008C, 0x9322037D),
    (0x000F0090, 0x2C430004), (0x000F0094, 0x10600015),
    (0x000F0098, 0xC72301B0), (0x000F009C, 0xC72401B4),
    (0x000F00A0, 0xC72501B8), (0x000F00A4, 0x460018C1),
    (0x000F00A8, 0x46012101), (0x000F00AC, 0x46022941),
    (0x000F00B0, 0x46031982), (0x000F00B4, 0x460421C2),
    (0x000F00B8, 0x46073180), (0x000F00BC, 0x460529C2),
    (0x000F00C0, 0x460731C0), (0x000F00C4, 0x460A3834),
    (0x000F00C8, 0x00000000), (0x000F00CC, 0x45000007),
    (0x000F00D0, 0x00000000), (0x000F00D4, 0x3C023C23),
    (0x000F00D8, 0x3442D70A), (0x000F00DC, 0xAD82008C),
    (0x000F00E0, 0x3C023F80), (0x000F00E4, 0x10000003),
    (0x000F00E8, 0xAD820090), (0x000F00EC, 0x1000FFE0),
    (0x000F00F0, 0x8DEF03B0), (0x000F00F4, 0x1D20FFCE),
    (0x000F00F8, 0x3C1F0022), (0x000F00FC, 0x08089050),
    (0x000F0100, 0x37FF3B8C)
]

#: The front-arc build: 94 words of code plus a 256-entry cosine table at
#: 0x000F0400. Bigger, and that costs nothing now -- low RAM is proven and
#: effectively unlimited.
CONE_WORDS = [
    (0x000F0000, 0x8E88002C), (0x000F0004, 0x8E890030),
    (0x000F0008, 0x11000058), (0x000F000C, 0x3C18471C),
    (0x000F0010, 0x19200056), (0x000F0014, 0x8D0A0000),
    (0x000F0018, 0x37184000), (0x000F001C, 0x11400053),
    (0x000F0020, 0x44985000), (0x000F0024, 0x8D4A0528),
    (0x000F0028, 0x11400050), (0x000F002C, 0x240B3F90),
    (0x000F0030, 0x8D0C0000), (0x000F0034, 0x25080004),
    (0x000F0038, 0x1180004B), (0x000F003C, 0x2529FFFF),
    (0x000F0040, 0x8D8D0024), (0x000F0044, 0x8DAD0020),
    (0x000F0048, 0x15AB0047), (0x000F004C, 0x8D8D008C),
    (0x000F0050, 0x15A00045), (0x000F0054, 0x918E006F),
    (0x000F0058, 0x31CE00EF), (0x000F005C, 0xA18E006F),
    (0x000F0060, 0x8D9801C4), (0x000F0064, 0x3C01000F),
    (0x000F0068, 0x0018C202), (0x000F006C, 0x331900FF),
    (0x000F0070, 0x0019C880), (0x000F0074, 0x00390821),
    (0x000F0078, 0xC4280400), (0x000F007C, 0x2719FFC0),
    (0x000F0080, 0x3C01000F), (0x000F0084, 0x333900FF),
    (0x000F0088, 0x0019C880), (0x000F008C, 0x00390821),
    (0x000F0090, 0xC4290400), (0x000F0094, 0x3C013F16),
    (0x000F0098, 0x34213A1A), (0x000F009C, 0x44817000),
    (0x000F00A0, 0x44807800), (0x000F00A4, 0xC58001B0),
    (0x000F00A8, 0xC58101B4), (0x000F00AC, 0xC58201B8),
    (0x000F00B0, 0x254F0000), (0x000F00B4, 0x11E0002C),
    (0x000F00B8, 0x24030002), (0x000F00BC, 0x8DF903AC),
    (0x000F00C0, 0x13200027), (0x000F00C4, 0x00000000),
    (0x000F00C8, 0x93220378), (0x000F00CC, 0x14430024),
    (0x000F00D0, 0x9322037D), (0x000F00D4, 0x2C430004),
    (0x000F00D8, 0x10600021), (0x000F00DC, 0xC72301B0),
    (0x000F00E0, 0xC72401B4), (0x000F00E4, 0xC72501B8),
    (0x000F00E8, 0x460018C1), (0x000F00EC, 0x46012101),
    (0x000F00F0, 0x46022941), (0x000F00F4, 0x46031982),
    (0x000F00F8, 0x460421C2), (0x000F00FC, 0x46073180),
    (0x000F0100, 0x460529C2), (0x000F0104, 0x460731C0),
    (0x000F0108, 0x460A3834), (0x000F010C, 0x00000000),
    (0x000F0110, 0x45000013), (0x000F0114, 0x00000000),
    (0x000F0118, 0x46081AC2), (0x000F011C, 0x46092342),
    (0x000F0120, 0x460D5AC0), (0x000F0124, 0x460F5836),
    (0x000F0128, 0x00000000), (0x000F012C, 0x4501000C),
    (0x000F0130, 0x460B5AC2), (0x000F0134, 0x460E3342),
    (0x000F0138, 0x460D5834), (0x000F013C, 0x00000000),
    (0x000F0140, 0x45000007), (0x000F0144, 0x00000000),
    (0x000F0148, 0x3C023C23), (0x000F014C, 0x3442D70A),
    (0x000F0150, 0xAD82008C), (0x000F0154, 0x3C023F80),
    (0x000F0158, 0x10000003), (0x000F015C, 0xAD820090),
    (0x000F0160, 0x1000FFD4), (0x000F0164, 0x8DEF03B0),
    (0x000F0168, 0x1D20FFB1), (0x000F016C, 0x3C1F0022),
    (0x000F0170, 0x08089050), (0x000F0174, 0x37FF3B8C),
    (0x000F0400, 0x3F800000), (0x000F0404, 0x3F7FEC43),
    (0x000F0408, 0x3F7FB10F), (0x000F040C, 0x3F7F4E6D),
    (0x000F0410, 0x3F7EC46D), (0x000F0414, 0x3F7E1324),
    (0x000F0418, 0x3F7D3AAC), (0x000F041C, 0x3F7C3B28),
    (0x000F0420, 0x3F7B14BE), (0x000F0424, 0x3F79C79D),
    (0x000F0428, 0x3F7853F8), (0x000F042C, 0x3F76BA07),
    (0x000F0430, 0x3F74FA0B), (0x000F0434, 0x3F731447),
    (0x000F0438, 0x3F710908), (0x000F043C, 0x3F6ED89E),
    (0x000F0440, 0x3F6C835E), (0x000F0444, 0x3F6A09A7),
    (0x000F0448, 0x3F676BD8), (0x000F044C, 0x3F64AA59),
    (0x000F0450, 0x3F61C598), (0x000F0454, 0x3F5EBE05),
    (0x000F0458, 0x3F5B941A), (0x000F045C, 0x3F584853),
    (0x000F0460, 0x3F54DB31), (0x000F0464, 0x3F514D3D),
    (0x000F0468, 0x3F4D9F02), (0x000F046C, 0x3F49D112),
    (0x000F0470, 0x3F45E403), (0x000F0474, 0x3F41D870),
    (0x000F0478, 0x3F3DAEF9), (0x000F047C, 0x3F396842),
    (0x000F0480, 0x3F3504F3), (0x000F0484, 0x3F3085BB),
    (0x000F0488, 0x3F2BEB4A), (0x000F048C, 0x3F273656),
    (0x000F0490, 0x3F226799), (0x000F0494, 0x3F1D7FD1),
    (0x000F0498, 0x3F187FC0), (0x000F049C, 0x3F13682A),
    (0x000F04A0, 0x3F0E39DA), (0x000F04A4, 0x3F08F59B),
    (0x000F04A8, 0x3F039C3D), (0x000F04AC, 0x3EFC5D27),
    (0x000F04B0, 0x3EF15AEA), (0x000F04B4, 0x3EE63375),
    (0x000F04B8, 0x3EDAE880), (0x000F04BC, 0x3ECF7BCA),
    (0x000F04C0, 0x3EC3EF15), (0x000F04C4, 0x3EB8442A),
    (0x000F04C8, 0x3EAC7CD4), (0x000F04CC, 0x3EA09AE5),
    (0x000F04D0, 0x3E94A031), (0x000F04D4, 0x3E888E93),
    (0x000F04D8, 0x3E78CFCC), (0x000F04DC, 0x3E605C13),
    (0x000F04E0, 0x3E47C5C2), (0x000F04E4, 0x3E2F10A2),
    (0x000F04E8, 0x3E164083), (0x000F04EC, 0x3DFAB273),
    (0x000F04F0, 0x3DC8BD36), (0x000F04F4, 0x3D96A905),
    (0x000F04F8, 0x3D48FB30), (0x000F04FC, 0x3CC90AB0),
    (0x000F0500, 0x248D3132), (0x000F0504, 0xBCC90AB0),
    (0x000F0508, 0xBD48FB30), (0x000F050C, 0xBD96A905),
    (0x000F0510, 0xBDC8BD36), (0x000F0514, 0xBDFAB273),
    (0x000F0518, 0xBE164083), (0x000F051C, 0xBE2F10A2),
    (0x000F0520, 0xBE47C5C2), (0x000F0524, 0xBE605C13),
    (0x000F0528, 0xBE78CFCC), (0x000F052C, 0xBE888E93),
    (0x000F0530, 0xBE94A031), (0x000F0534, 0xBEA09AE5),
    (0x000F0538, 0xBEAC7CD4), (0x000F053C, 0xBEB8442A),
    (0x000F0540, 0xBEC3EF15), (0x000F0544, 0xBECF7BCA),
    (0x000F0548, 0xBEDAE880), (0x000F054C, 0xBEE63375),
    (0x000F0550, 0xBEF15AEA), (0x000F0554, 0xBEFC5D27),
    (0x000F0558, 0xBF039C3D), (0x000F055C, 0xBF08F59B),
    (0x000F0560, 0xBF0E39DA), (0x000F0564, 0xBF13682A),
    (0x000F0568, 0xBF187FC0), (0x000F056C, 0xBF1D7FD1),
    (0x000F0570, 0xBF226799), (0x000F0574, 0xBF273656),
    (0x000F0578, 0xBF2BEB4A), (0x000F057C, 0xBF3085BB),
    (0x000F0580, 0xBF3504F3), (0x000F0584, 0xBF396842),
    (0x000F0588, 0xBF3DAEF9), (0x000F058C, 0xBF41D870),
    (0x000F0590, 0xBF45E403), (0x000F0594, 0xBF49D112),
    (0x000F0598, 0xBF4D9F02), (0x000F059C, 0xBF514D3D),
    (0x000F05A0, 0xBF54DB31), (0x000F05A4, 0xBF584853),
    (0x000F05A8, 0xBF5B941A), (0x000F05AC, 0xBF5EBE05),
    (0x000F05B0, 0xBF61C598), (0x000F05B4, 0xBF64AA59),
    (0x000F05B8, 0xBF676BD8), (0x000F05BC, 0xBF6A09A7),
    (0x000F05C0, 0xBF6C835E), (0x000F05C4, 0xBF6ED89E),
    (0x000F05C8, 0xBF710908), (0x000F05CC, 0xBF731447),
    (0x000F05D0, 0xBF74FA0B), (0x000F05D4, 0xBF76BA07),
    (0x000F05D8, 0xBF7853F8), (0x000F05DC, 0xBF79C79D),
    (0x000F05E0, 0xBF7B14BE), (0x000F05E4, 0xBF7C3B28),
    (0x000F05E8, 0xBF7D3AAC), (0x000F05EC, 0xBF7E1324),
    (0x000F05F0, 0xBF7EC46D), (0x000F05F4, 0xBF7F4E6D),
    (0x000F05F8, 0xBF7FB10F), (0x000F05FC, 0xBF7FEC43),
    (0x000F0600, 0xBF800000), (0x000F0604, 0xBF7FEC43),
    (0x000F0608, 0xBF7FB10F), (0x000F060C, 0xBF7F4E6D),
    (0x000F0610, 0xBF7EC46D), (0x000F0614, 0xBF7E1324),
    (0x000F0618, 0xBF7D3AAC), (0x000F061C, 0xBF7C3B28),
    (0x000F0620, 0xBF7B14BE), (0x000F0624, 0xBF79C79D),
    (0x000F0628, 0xBF7853F8), (0x000F062C, 0xBF76BA07),
    (0x000F0630, 0xBF74FA0B), (0x000F0634, 0xBF731447),
    (0x000F0638, 0xBF710908), (0x000F063C, 0xBF6ED89E),
    (0x000F0640, 0xBF6C835E), (0x000F0644, 0xBF6A09A7),
    (0x000F0648, 0xBF676BD8), (0x000F064C, 0xBF64AA59),
    (0x000F0650, 0xBF61C598), (0x000F0654, 0xBF5EBE05),
    (0x000F0658, 0xBF5B941A), (0x000F065C, 0xBF584853),
    (0x000F0660, 0xBF54DB31), (0x000F0664, 0xBF514D3D),
    (0x000F0668, 0xBF4D9F02), (0x000F066C, 0xBF49D112),
    (0x000F0670, 0xBF45E403), (0x000F0674, 0xBF41D870),
    (0x000F0678, 0xBF3DAEF9), (0x000F067C, 0xBF396842),
    (0x000F0680, 0xBF3504F3), (0x000F0684, 0xBF3085BB),
    (0x000F0688, 0xBF2BEB4A), (0x000F068C, 0xBF273656),
    (0x000F0690, 0xBF226799), (0x000F0694, 0xBF1D7FD1),
    (0x000F0698, 0xBF187FC0), (0x000F069C, 0xBF13682A),
    (0x000F06A0, 0xBF0E39DA), (0x000F06A4, 0xBF08F59B),
    (0x000F06A8, 0xBF039C3D), (0x000F06AC, 0xBEFC5D27),
    (0x000F06B0, 0xBEF15AEA), (0x000F06B4, 0xBEE63375),
    (0x000F06B8, 0xBEDAE880), (0x000F06BC, 0xBECF7BCA),
    (0x000F06C0, 0xBEC3EF15), (0x000F06C4, 0xBEB8442A),
    (0x000F06C8, 0xBEAC7CD4), (0x000F06CC, 0xBEA09AE5),
    (0x000F06D0, 0xBE94A031), (0x000F06D4, 0xBE888E93),
    (0x000F06D8, 0xBE78CFCC), (0x000F06DC, 0xBE605C13),
    (0x000F06E0, 0xBE47C5C2), (0x000F06E4, 0xBE2F10A2),
    (0x000F06E8, 0xBE164083), (0x000F06EC, 0xBDFAB273),
    (0x000F06F0, 0xBDC8BD36), (0x000F06F4, 0xBD96A905),
    (0x000F06F8, 0xBD48FB30), (0x000F06FC, 0xBCC90AB0),
    (0x000F0700, 0xA553C9CA), (0x000F0704, 0x3CC90AB0),
    (0x000F0708, 0x3D48FB30), (0x000F070C, 0x3D96A905),
    (0x000F0710, 0x3DC8BD36), (0x000F0714, 0x3DFAB273),
    (0x000F0718, 0x3E164083), (0x000F071C, 0x3E2F10A2),
    (0x000F0720, 0x3E47C5C2), (0x000F0724, 0x3E605C13),
    (0x000F0728, 0x3E78CFCC), (0x000F072C, 0x3E888E93),
    (0x000F0730, 0x3E94A031), (0x000F0734, 0x3EA09AE5),
    (0x000F0738, 0x3EAC7CD4), (0x000F073C, 0x3EB8442A),
    (0x000F0740, 0x3EC3EF15), (0x000F0744, 0x3ECF7BCA),
    (0x000F0748, 0x3EDAE880), (0x000F074C, 0x3EE63375),
    (0x000F0750, 0x3EF15AEA), (0x000F0754, 0x3EFC5D27),
    (0x000F0758, 0x3F039C3D), (0x000F075C, 0x3F08F59B),
    (0x000F0760, 0x3F0E39DA), (0x000F0764, 0x3F13682A),
    (0x000F0768, 0x3F187FC0), (0x000F076C, 0x3F1D7FD1),
    (0x000F0770, 0x3F226799), (0x000F0774, 0x3F273656),
    (0x000F0778, 0x3F2BEB4A), (0x000F077C, 0x3F3085BB),
    (0x000F0780, 0x3F3504F3), (0x000F0784, 0x3F396842),
    (0x000F0788, 0x3F3DAEF9), (0x000F078C, 0x3F41D870),
    (0x000F0790, 0x3F45E403), (0x000F0794, 0x3F49D112),
    (0x000F0798, 0x3F4D9F02), (0x000F079C, 0x3F514D3D),
    (0x000F07A0, 0x3F54DB31), (0x000F07A4, 0x3F584853),
    (0x000F07A8, 0x3F5B941A), (0x000F07AC, 0x3F5EBE05),
    (0x000F07B0, 0x3F61C598), (0x000F07B4, 0x3F64AA59),
    (0x000F07B8, 0x3F676BD8), (0x000F07BC, 0x3F6A09A7),
    (0x000F07C0, 0x3F6C835E), (0x000F07C4, 0x3F6ED89E),
    (0x000F07C8, 0x3F710908), (0x000F07CC, 0x3F731447),
    (0x000F07D0, 0x3F74FA0B), (0x000F07D4, 0x3F76BA07),
    (0x000F07D8, 0x3F7853F8), (0x000F07DC, 0x3F79C79D),
    (0x000F07E0, 0x3F7B14BE), (0x000F07E4, 0x3F7C3B28),
    (0x000F07E8, 0x3F7D3AAC), (0x000F07EC, 0x3F7E1324),
    (0x000F07F0, 0x3F7EC46D), (0x000F07F4, 0x3F7F4E6D),
    (0x000F07F8, 0x3F7FB10F), (0x000F07FC, 0x3F7FEC43)
]

#: Squared trigger radius, as two halves of an IEEE float. Same two addresses
#: in both builds.
RADIUS_AT = (0x000F000C, 0x000F0018)
RADIUS_WORDS = {
    "1": (0x3C18461C, 0x37184000),   # R^2 = 10000 -> 1.00 m
    "2": (0x3C18471C, 0x37184000),   # R^2 = 40000 -> 2.00 m
    "3": (0x3C1847AF, 0x3718C800),   # R^2 = 90000 -> 3.00 m
}

#: `lui $at, hi16(cos^2 halfAngle)` -- the cone test's constant, front-arc
#: build only. Only the float's high half is stored, which costs about 0.015
#: of a degree and is far inside the cosine table's own 1.40625 degree step.
CONE_K_AT = 0x000F0094


def cone_word(cone_cos: float) -> int:
    """The `lui` that carries cos^2 of the blast's own half-angle.

    Computed rather than pinned, so the trigger arc cannot drift away from the
    blast arc. `rsegadget` reads the blast's own cosine out of the level
    containers; pass that here and the two always agree.
    """
    k = struct.unpack("<I", struct.pack("<f", float(cone_cos) ** 2))[0]
    return 0x3C010000 | ((k >> 16) & 0xFFFF)


def words(radius: str, front_arc: bool = True, cone_cos: float = 0.766):
    """[(va, word)] for the cave: trigger radius in metres, and whether it
    fires only inside the blast's forward arc."""
    src = CONE_WORDS if front_arc else ALLROUND_WORDS
    hi, lo = RADIUS_WORDS[radius]
    patch = {RADIUS_AT[0]: hi, RADIUS_AT[1]: lo}
    if front_arc:
        patch[CONE_K_AT] = cone_word(cone_cos)
    return [(va, patch.get(va, w)) for va, w in src]


def arc_card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "claymore_arc", "...and only when it is facing them", BOOL,
        True, group, pnach_only=True,
        requires={prefix + "claymore_prox": ["1", "2", "3"]},
        help="A claymore fires its blast in a 40-degree arc straight ahead, "
             "so an enemy walking past BEHIND it would set it off and then "
             "walk away unhurt -- the charge wasted. This only lets it "
             "trigger when the enemy is inside that same arc, so when it goes "
             "off it does damage.\n\n"
             "Turn it off for a mine that cannot be walked around, at the "
             "cost of wasting itself on people it cannot hurt.",
        caution="The trigger arc is taken from the blast's own angle, so the "
                "two cannot drift apart. It is accurate to about a degree, "
                "measured across the full circle.",
        confidence="experimental")


def card(prefix, group):
    from .model import CHOICE, Choice, Setting

    return Setting(
        prefix + "claymore_prox", "Claymore trips on its own", CHOICE, "off",
        group, pnach_only=True,
        choices=[
            Choice("off", "Off (detonator only)",
                   "As the game ships it: the claymore waits for you to press "
                   "the detonator."),
            Choice("1", "One metre",
                   "Practically a contact trigger. Hardest to set off by "
                   "accident."),
            Choice("2", "Two metres", "A doorway's width."),
            Choice("3", "Three metres",
                   "Trips early. On a narrow corridor it will catch anyone "
                   "coming through."),
        ],
        help="The claymore normally sits there until you press the detonator. "
             "This makes it go off by itself when a terrorist walks within "
             "range, and the detonator still works as it always did. Only "
             "terrorists set it off -- your teammates and hostages walk past "
             "safely, which matters more than it sounds: in the save this was "
             "built against, a teammate was standing 1.7 metres from the "
             "charge while the nearest enemy was 15 metres away.",
        caution="CONFIRMED WORKING in play (2026-09-25): a claymore placed "
                "in front of a closed door went off by itself. What has "
                "not been tested is every map and every angle.\n\n"
                "Delivered as a PCSX2 cheat file, not written to the disc, "
                "because a code cave does not survive a level load. Save a "
                "fresh cheat file after changing this, and restart the "
                "emulator so it is re-read.\n\n"
                "The trigger is a circle around the charge, but the BLAST "
                "keeps its 40-degree forward cone, so an enemy walking up "
                "from behind will set it off and survive it. Costs about a "
                "third of one percent of the console's processor.",
        confidence="experimental")

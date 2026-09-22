"""Rainbow Six 3 (PS2, SLUS-20883) -- profile.

Every address below is a virtual address in the decompressed `SP.SOZ` overlay,
which the EE loads at a fixed base of 0x00100000. All stock words are asserted
before anything is written, so a mismatched disc revision fails loudly instead
of corrupting the image.

Provenance of the wave numbers, briefly, because they are not obvious:

  * `m_iNbToSpawn` is computed at zone init as `min + rand % (max - min + 1)`;
    replacing the `addu` that forms it with a `li` gives every deployment zone
    the same budget.
  * The wave advance returns early unless `liveCount <= m_iNextWaveTrigger`, so
    the trigger -- not the wave size -- is the real population cap. Steady state
    per zone is roughly `trigger + release`.
  * The advance is gated on `bStasis == 0`, and UE2 clears stasis for actors
    whose zone contains a player. So the shipped rule is literally "feed the
    zone the player is standing in". Inverting that test (`beq` -> `bne`) makes
    the zones the player has left do the feeding instead.
  * A wave draws only from its own `m_aSpawningPoint` array, and those points
    sit next to the zone. Widening the pool to every `R6DZonePoint` in the level
    takes a code cave, which is the one thing here that cannot be baked into the
    disc -- see `build_pnach`.
"""

from __future__ import annotations

import struct

from ..model import (BOOL, CHOICE, INT, Choice, FileEdit, GameProfile,
                     Overlay, Setting, WordEdit, li, S0, V0, V1)
from . import r6tuning, xboxbuild
from .. import (rseaicover, rsecanon, rsefragwarn, rsechatter, rsedraw, rsekits, rseloadout,
                rsedeadpath, rsefov, rsemandown, rseviewmodel, rserpg, rseshadow, rsesidearm,
                rsescope,
                rsewheel)

BASE = 0x00100000
NOP = 0x00000000

SP = Overlay(
    name="SP.SOZ",
    iso_pattern=r"/SP\.SOZ$",
    base_va=BASE,
    kind="soz",
    image_size=5585280,
    image_sha1="e9bb12138a1e69d551ac9f6b958114e5b2e830da",
)

# -- stock words, all read back out of a pristine SP.SOZ -------------------
STOCK = {
    0x0040AF58: 0x02221021,   # addu v0, s1, v0      m_iNbToSpawn
    0x0040A8A8: 0x02028021,   # addu s0, s0, v0      released per wave
    0x0040AFDC: 0x02231821,   # addu v1, s1, v1      m_iNextWaveTrigger seed
    0x0040A874: 0x02021021,   # addu v0, s0, v0      m_iNextWaveTrigger rearm
    0x0040AF4C: 0x00000000,   # pad nop
    0x0040AF50: 0x00000000,   # pad nop
    0x0040AF54: 0x00001010,   # mfhi v0  (dead once 0x40af58 is a constant)
    0x0040A790: 0x10400003,   # beq v0, zero, +3     the bStasis gate
    0x003F1934: 0x1440004F,   # bne v0, zero, skip   static-world impact decal
    0x003F1BB4: 0x14400084,   # bne v0, zero, skip   actor-attached impact decal
    0x003F250C: 0x14400014,   # bne v0, zero, skip   impact emitter spawn
    0x003531D0: 0x14400053,   # bne v0, zero, skip   rain/snow weather
    0x003A14B8: 0x14400015,   # bne v0, zero, skip   blood-effect update
    0x002375E0: 0xA2420065,   # sb v0, 0x65(s2)      Disabled = m_bHideInSplitScreen
    0x00302DA8: 0xAF8080CC,   # sw zero, -0x7f34(gp) g_bDrawFirstPersonWeapon = 0
    0x00317570: 0x1460001D,   # bne v1, zero, +29    body despawn path 1
    0x003175F4: 0x1460000B,   # bne v1, zero, +11    body despawn path 2
    0x00317600: 0x3C034040,   # lui v1, 0x4040       3.0f despawn window
    0x00379B30: 0x24060020,   # addiu a2, zero, 32   R6DecalGroup m_MaxSize
    0x0040ACA0: 0x0C051B7C,   # jal rand             SpawnATerrorist point pick
    # The substituted delta is built as a lui/ori pair and then moved into the
    # register, so the constant itself is patchable without touching the branch:
    #   lui v1, 0x3D4C ; ori v1, v1, 0xCCCD  ->  0x3D4CCCCD == 0.05f
    0x00142040: 0x3C033D4C,   # lui v1, 0x3D4C      high half of the constant
    0x00142044: 0x3463CCCD,   # ori v1, v1, 0xCCCD  low half
    0x00142048: 0x4483A800,   # mtc1 v1, $f21       player 2's input dt := 0.05f
    0x0019AE40: 0x14A000C6,   # bnez a1, 0x19b15c   the scope-overlay gate
    0x0019AE44: 0x3C010004,   # lui at, 0x4        its delay slot, and NOT
                              #                    filler: the gate's target
                              #                    opens `ori at, at, 0x17e8`
    0x00446EA8: 0x30420001,   # andi v0, v0, 1      the shadow-pass gate
}

# Scaffolding from the research build that produced this profile: a tracing stub
# in the function-end padding at 0x0011d8c4 and the two-word hijack that reached
# it. This tool never writes them, but knowing their stock values means it can
# clean a disc that still carries them instead of refusing to touch it.
RESEARCH_LEFTOVERS = dict(
    [(va, 0x00000000) for va in range(0x0011D8C4, 0x0011D900, 4)]
    + [(0x0017F530, 0x27BDFCF0), (0x0017F534, 0xFFBF0090)]
)
STOCK.update(RESEARCH_LEFTOVERS)

#: The dead-path cave and every site the two split-screen HUD fixes
#: touch. These used to be cheat words, which never went through
#: STOCK at all; on the disc each one is asserted against the shipped
#: word before it is written, like every other patch site here.
HUD_STOCK = {
    0x0019AE40: 0x14A000C6,
    0x0019AE48: 0x82030000,
    0x0019AE4C: 0x00031EBC,
    0x0019AE50: 0x00031FFF,
    0x0019AE54: 0x106001B5,
    0x0019AE58: 0x348317E0,
    0x0019AE5C: 0x02031821,
    0x0019AE60: 0x8C630000,
    0x0019AF34: 0x8E0207C4,
    0x0019AF38: 0x04410003,
    0x0019AF3C: 0x00023843,
    0x0019AF40: 0x24420001,
    0x0019AF44: 0x00023843,
    0x0019AF48: 0x8E0807C8,
    0x0019AF68: 0x8E0207C4,
    0x0019AF6C: 0x04410003,
    0x0019AF70: 0x0002B043,
    0x0019AF74: 0x24420001,
    0x0019AF78: 0x0002B043,
    0x0019AFD0: 0x8E0807C8,
    0x0019B0A8: 0x8E0207C4,
    0x0019B0AC: 0x04410003,
    0x0019B0B0: 0x00023843,
    0x0019B0B4: 0x24420001,
    0x0019B0B8: 0x00023843,
    0x0019B0BC: 0x8E0807C8,
    0x0019B0DC: 0x8E0207C4,
    0x0019B0E0: 0x04410003,
    0x0019B0E4: 0x0002B043,
    0x0019B0E8: 0x24420001,
    0x0019B0EC: 0x0002B043,
    0x0019B144: 0x8E0807C8,
    0x0019B15C: 0x342117E8,
    0x0019B160: 0x02011821,
    0x0019B164: 0x00651821,
    0x0019B168: 0x90630000,
    0x0019B16C: 0x106000EF,
    0x0019B170: 0x00000000,
    0x0019B174: 0x348417EC,
    0x0019B178: 0x00051880,
    0x0019B17C: 0x02042021,
    0x0019B180: 0x00831821,
    0x0019B184: 0x8C630000,
    0x0019B188: 0x106000E8,
    0x0019B18C: 0x00000000,
    0x0019B190: 0x24040001,
    0x0019B194: 0x0C064808,
    0x0019B198: 0x0000282D,
    0x0019B19C: 0x3C010004,
    0x0019B1A0: 0x02010821,
    0x0019B1A4: 0x8C2309FC,
    0x0019B1A8: 0x3C010004,
    0x0019B1AC: 0x00031880,
    0x0019B1B0: 0x342117EC,
    0x0019B1B4: 0x02011021,
    0x0019B1B8: 0x00431021,
    0x003F4BF4: 0xC7828D18,
    0x003F4BF8: 0xC7818D24,
    0x003F4BFC: 0xC7808D28,
    0x003F5524: 0xC7828D18,
    0x003F5528: 0xC7818D24,
    0x003F552C: 0xC7808D28,
    0x0043888C: 0x00000000,
    0x00438C0C: 0x00000000,
    0x00438F88: 0x00000000,
    0x00439304: 0x00000000,
}
STOCK.update(HUD_STOCK)

BODY_TIMERS = {
    "stock": None,
    "15": 0x3C034170,     # lui v1, 0x4170 = 15.0f
    "30": 0x3C0341F0,     # lui v1, 0x41f0 = 30.0f
    "60": 0x3C034270,     # lui v1, 0x4270 = 60.0f
}

WAVE_GATES = {
    "stock": 0x10400003,  # beq  -- feed only the zone the player is in
    "always": 0x10000003, # b    -- every zone feeds, all the time
    "away": 0x14400003,   # bne  -- feed only the zones the player has left
}

# The map-wide spawn-point picker: 67 words of cave plus one hijack. Assembled
# and verified as a PCSX2 cheat; it cannot be baked into the disc because the
# 0x005ba488 zero run is not preserved through a level load, while a cheat file
# rewrites it every frame.
CAVE_HIJACK = (0x0040ACA0, 0x0816E922)   # j 0x005ba488, replacing `jal rand`
CAVE_WORDS = [
    (0x005BA488, 0x3C01005C), (0x005BA48C, 0xAC3FA5F8), (0x005BA490, 0x0C051B7C),
    (0x005BA494, 0x00000000), (0x005BA498, 0x30517FFF), (0x005BA49C, 0x3C01005C),
    (0x005BA4A0, 0x8C3FA5F8), (0x005BA4A4, 0x8EA802E4), (0x005BA4A8, 0x1100002E),
    (0x005BA4AC, 0x00000000), (0x005BA4B0, 0x8D09002C), (0x005BA4B4, 0x8D0A0030),
    (0x005BA4B8, 0x1120002A), (0x005BA4BC, 0x00000000), (0x005BA4C0, 0x19400028),
    (0x005BA4C4, 0x00000000), (0x005BA4C8, 0x3C0B0061), (0x005BA4CC, 0x356BE2F0),
    (0x005BA4D0, 0x00006021), (0x005BA4D4, 0x00006821), (0x005BA4D8, 0x000C7080),
    (0x005BA4DC, 0x012E7021), (0x005BA4E0, 0x8DCF0000), (0x005BA4E4, 0x11E00005),
    (0x005BA4E8, 0x00000000), (0x005BA4EC, 0x8DF80000), (0x005BA4F0, 0x170B0002),
    (0x005BA4F4, 0x00000000), (0x005BA4F8, 0x25AD0001), (0x005BA4FC, 0x258C0001),
    (0x005BA500, 0x018A082A), (0x005BA504, 0x1420FFF4), (0x005BA508, 0x00000000),
    (0x005BA50C, 0x11A00015), (0x005BA510, 0x00000000), (0x005BA514, 0x022D001A),
    (0x005BA518, 0x00000000), (0x005BA51C, 0x00000000), (0x005BA520, 0x00007010),
    (0x005BA524, 0x00006021), (0x005BA528, 0x000C7880), (0x005BA52C, 0x012F7821),
    (0x005BA530, 0x8DF80000), (0x005BA534, 0x13000007), (0x005BA538, 0x00000000),
    (0x005BA53C, 0x8F190000), (0x005BA540, 0x172B0004), (0x005BA544, 0x00000000),
    (0x005BA548, 0x11C0000F), (0x005BA54C, 0x00000000), (0x005BA550, 0x25CEFFFF),
    (0x005BA554, 0x258C0001), (0x005BA558, 0x018A082A), (0x005BA55C, 0x1420FFF2),
    (0x005BA560, 0x00000000), (0x005BA564, 0x8EA80484), (0x005BA568, 0x11000004),
    (0x005BA56C, 0x00000000), (0x005BA570, 0x8D040000), (0x005BA574, 0x10000005),
    (0x005BA578, 0x00000000), (0x005BA57C, 0x00008021), (0x005BA580, 0x08102B6E),
    (0x005BA584, 0x00000000), (0x005BA588, 0x03002021), (0x005BA58C, 0x08102B31),
    (0x005BA590, 0x00000000),
]

#: Counted from the recovered export table, which names each object's class --
#: not from a byte search, which also counts the class name itself and reads
#: one high on every level. 41 wave actors and 541 spawn points across the 27
#: campaign parts. See research/rs3ai/zones.md.
WAVE_MAPS = (
    "Waves are a campaign thing. 24 of the game's 27 mission parts place "
    "deployment zones -- 41 zones and 541 spawn points between them -- and the "
    "settings on this page reach every one of them at once. To move a single "
    "mission instead, use the Missions page.\n\n"
    "Widest choice of spawn points, which is what map-wide spawning feeds on:\n"
    "  TRIESTE A         3 zones, 29 points\n"
    "  IMPORT/EXPORT B   3 zones, 29 points\n"
    "  OIL REFINERY A    3 zones, 27 points\n"
    "  OFFICE COMPLEX A  1 zone,  27 points\n"
    "  PARADE B          2 zones, 26 points\n"
    "  SHIPYARD A        2 zones, 18 points -- the only level with fighting "
    "from the first minute, since its zones wrap the insertion point.\n\n"
    "No zones, so nothing here changes them: Alpine Village A, Import/Export "
    "A, Penthouse A.\n"
    "No zones anywhere in multiplayer or training either -- every MP and "
    "training package places zero, so adversarial modes are untouched.\n\n"
    "Withdrawn: \"Match player 2's look speed to player 1\". The clamp it "
    "targeted is real -- at 0x00142048 the routine forces its frame delta to "
    "0.05 whenever the true frame is under 33 ms -- but play-testing it made "
    "player 2 about four times more sensitive with no acceleration ramp at "
    "all, which is not parity. Two things are settled and worth keeping: that "
    "delta is computed at 0x00141d54 as a timer over 2^32, capped at 0.04 for "
    "a long frame, so it IS a real frame time; and the clamp raises it, which "
    "at 60 fps makes it three times larger than player 1's rather than "
    "smaller. The card used to claim the opposite. What is still unknown is "
    "the path from that register to the camera: inside its own routine it "
    "feeds an accumulator at gp-32008 and a countdown at +0x304, both plain "
    "`+= dt` / `-= dt`, neither of them a look rate. Until that path is "
    "traced there is nothing honest to switch on.\n\n"
    "No weapons page, and this one is settled rather than untried. Ghost "
    "Recon, Jungle Storm and The Sum of All Fears all get one, because they "
    "ship a .GUN file per weapon in plain XML. This disc keeps its weapons in "
    "COMMON.LIN, and the package at 0x1ad818 really is the weapons package -- "
    "877 exports including R6Weapons, R6MachineGun, R6SubMachineGun and "
    "R6BlackHawkGun. But Unreal only serialises a property that DIFFERS from "
    "its class default, and the weapon stats are the defaults. A float "
    "locator built for this (upackage.float_properties, and it works -- see "
    "the tests) finds exactly TWO m_fRateOfFire sites and six fBaseAccuracy "
    "sites in that entire package, for a game with about forty weapons. Two "
    "overrides is not a dial.\n\n"
    "The 33 m_iPenetration sites that look promising at first are false "
    "positives inside a texture package: their values run to 84,607,257 and "
    "their neighbouring properties are UBits, VBits, USize and ZPlane. The "
    "real values live in the compiled class defaults inside the overlay, not "
    "in the data. Ghost Recon 2 and Advanced Warfighter were checked the same "
    "way and answer the same."
)


#: The campaign, as the disc actually lays it out: a stem, the name the game
#: uses for it, and which parts exist. Most missions are two levels; Island,
#: Penthouse and Trieste are one. Every part ships twice -- `<STEM>OFF.LIN` and
#: `<STEM>_SS.LIN` -- and both have to be edited or half the copies stay stock.
#:
#: `waves` is the number of R6DZoneWave actors the level places, read off the
#: recovered export table rather than estimated; see research/rs3ai/zones.md.
#: The campaign in the order it is played, given by the person who has played
#: it. The disc does not state it anywhere readable: `RavenShieldCampaign.ini`
#: is a Raven Shield list the PS2 build inherited -- it names Bank,
#: MeatPacking_Day, Island_Dawn and Airport_Night, none of which are on this
#: disc, and omits four that are -- and the per-map `m_fStoryMapELO` is a
#: difficulty rating with ties, not a running order. Ordering by either put Oil
#: Refinery first, which is wrong.
#:
#: "Crespo Foundation" is the mission's own name for the OFFICE_COMPLEX
#: package; the display names live in the packed .LNG bundle, so the word
#: "Crespo" appears nowhere on the disc as text.
#:
#: Training and the Parking Garage come first because neither is in mission
#: selection -- they are chosen separately from the main menu.
#:
#: (stem, title, parts, wave zones, kind). An empty `parts` means the level is
#: a single package with no A/B suffix, which is how the training levels ship.
MISSIONS = (
    ("TRAINING_BASICS", "Training: Basics", "", 0, "training"),
    ("TRAINING_SHOOTING", "Training: Shooting", "", 0, "training"),
    ("TRAINING_TEAM", "Training: Team", "", 0, "training"),
    ("ALPINES", "Alpine Village", "AB", 2, "campaign"),
    ("MOUNTAIN_HIGHWAY", "Mountain Highway", "AB", 3, "campaign"),
    ("OIL_REFINERY", "Oil Refinery", "AB", 5, "campaign"),
    ("ISLAND", "Island Estate", "A", 2, "campaign"),
    ("SHIPYARD", "Shipyard", "AB", 3, "campaign"),
    ("OFFICE_COMPLEX", "Crespo Foundation", "AB", 3, "campaign"),
    ("OLDCITY", "Old City", "AB", 2, "campaign"),
    ("ALCATRAZ", "Alcatraz", "AB", 3, "campaign"),
    ("IMPORT_EXPORT", "Import/Export", "AB", 3, "campaign"),
    ("PENTHOUSE", "Penthouse", "A", 0, "campaign"),
    ("MEATPACKING", "Meat Packing Plant", "AB", 4, "campaign"),
    ("TRIESTE", "Trieste", "A", 3, "campaign"),
    ("GARAGE", "Parking Garage", "AB", 2, "bonus"),
    ("PARADE", "Parade", "AB", 3, "campaign"),
    ("AIRPORT", "Airport", "AB", 3, "campaign"),
)

MISSION_GROUP = "Missions"
TEAM_GROUP = "Teammates"


def mission_art_for(key):
    """The art base names for a mission dial, so its card shows the real thing."""
    for stem, _title, parts, _waves, _kind in MISSIONS:
        if key == mission_key(stem):
            return ["%s_%s" % (stem, p) for p in parts] if parts else [stem]
    return []


def mission_key(stem):
    return "mission_" + stem.lower()


def mission_select(stem, parts):
    """A regex matching every package this mission ships, both copies.

    Each level part ships twice, `<STEM>OFF.LIN` and `<STEM>_SS.LIN`, and both
    have to match or half the copies stay stock. The training levels have no
    A/B suffix at all, which is what the empty-`parts` branch is for.
    """
    if not parts:
        return r"/%s(OFF|_SS)\.LIN$" % stem
    return r"/%s_[%s](OFF|_SS)\.LIN$" % (stem, parts)


def _mission_settings():
    """One enemy-count dial per mission.

    These are the counts the designers authored into the level itself, so
    unlike everything on the Enemy Waves page they move one mission and leave
    the rest of the campaign alone. What they scale is every authored spawner
    count in that level -- the wave zones and the story spawners both -- which
    is why the label says enemies rather than waves.
    """
    out = []
    for stem, title, parts, waves, kind in MISSIONS:
        where = ("part A and B" if len(parts) == 2
                 else "one part" if parts else "a single level")
        zones = ("%d deployment zone%s" % (waves, "" if waves == 1 else "s")
                 if waves else "no deployment zones -- story spawners only")
        note = {"training": " Not in mission selection: training is chosen "
                            "separately from the main menu.",
                "bonus": " Not in mission selection -- the Parking Garage "
                         "is picked separately from the main menu.",
                }.get(kind, "")
        # The training levels author no spawner counts at all -- nothing to
        # scale -- so the dial is off rather than present and inert. Their
        # cards still carry the game's own art, which is why they are here.
        live = kind != "training"
        out.append(Setting(
            mission_key(stem), title, INT, 100, MISSION_GROUP,
            minimum=25, maximum=400, unit="%",
            help="Scales every enemy count authored into %s (%s; %s). "
                 "100%% leaves it exactly as it shipped.%s"
                 % (title, where, zones, note) if live else
                 "%s, and it authors no spawner counts -- there is nothing "
                 "here to scale.%s" % (where.capitalize(), note),
            touches="data", enabled=live,
            disabled_reason=("" if live else
                             "The training levels place no authored enemy "
                             "counts, so a dial would have nothing to change. "
                             "The card is here for the level's own artwork."),
            confidence="applied" if live else "broken"))
    return out


#: Every option whose edit RE-ASSEMBLES UnrealScript bytecode, rather than
#: poking bytes in place. All of them are withdrawn together, because the
#: evidence says the fault is the rewrite path and not the individual features.
#: Delete this list to put them back once `uscode` is understood.
#: Still out: these two were bisected to a hang ON THE DISC, one each, with
#: removing them loading fine. That is direct evidence, not association.
REASSEMBLED = ("canon_team", "ss_man_down")

#: Re-enabled 2026-09-15 once `uscode` stopped shrinking the declared memory
#: size -- see REASSEMBLED_REASON for what that was and why it mattered. They go
#: back on the list as "untested", because the fix is reasoned and measured but
#: has not yet been through a level load. `canon_team` stays out: it is the one
#: with four earlier hangs behind it as well, so it is the last to be retried,
#: not the first.

REASSEMBLED_REASON = (
    "Withdrawn 2026-09-15, and RE-CONFIRMED 2026-09-19 on a disc carrying "
    "this option and nothing else -- so unlike some of its neighbours it "
    "was not convicted by a confounded bisect. What the retry added, from "
    "reading the console rather than watching the screen: the EE sits at "
    "pc=0x00081fc0 in the kernel, `eret`, with ra and sp both zero, "
    "identical across captures four seconds apart. Of 128 MB of EE RAM, "
    "628 bytes change in that time and every one of them is below "
    "0x00022000 -- kernel timers. Nothing in the game's own memory moves "
    "at all, the IOP is equally idle (429 bytes of 8 MB), and the level "
    "name buffer still reads 'menu', so it wedges BEFORE the mission load "
    "names its level. Every game thread is blocked, waiting on something "
    "that never arrives; it is not a slow load and it is not a spin.\n\n"
    "The 2026-09-15 reasoning is kept below, but note the rule it rests "
    "on no longer holds: ai_sidearm re-assembles 360 bytes across 17 runs "
    "and was played through Parade on 2026-09-19, and ai_cover pokes five "
    "bytes and was withdrawn the same day on a disc that also had wave "
    "mode on, then put back when the console showed its edit live in RAM. "
    "So 're-assembling hangs, poking does not' is retired. THIS option "
    "still hangs; the reason is simply not the one recorded.\n\n"
    "Withdrawn 2026-09-15. Every edit that RE-ASSEMBLES bytecode hangs the "
    "level load, and this is one of them.\n\n"
    "Bisected on the disc twice: canon_team alone froze the split-screen load "
    "on Island Estate, and ss_man_down alone froze the initial load with "
    "removing it loading fine. Against that, all four options that merely poke "
    "bytes in place -- the equipment wheel, the draw animation, the RPG speed "
    "and the scope overlay -- work, and split_scope was watched working the "
    "same day. Two of two against four of four is not a coincidence about the "
    "features; it is the rewrite path.\n\n"
    "Measured and cleared, so the next attempt need not redo it: the assembler "
    "is faithful -- 6,726 of the package's 6,789 script blocks round-trip "
    "byte-identically through it with zero wrong byte streams and zero wrong "
    "declared sizes, the 63 misses being the block scanner's own false "
    "positives. The LIN container is faithful -- every edit repacks to the "
    "same length AND decompresses back to exactly the bytes put in. The "
    "archive layout is clean -- no file moves, no size changes. And there is "
    "no second copy of the script size beside the block being missed.\n\n"
    "What all of them have in common, and the byte-poke edits never do, is "
    "that the block's declared MEMORY size shrinks -- ss_man_down -10, "
    "canon_team -3, ai_sidearm -3, ss_chatter -28 -- while the disk length is "
    "held fixed by padding with EX_Nothing.\n\n"
    "THAT WAS TESTED AND IS NOT THE CAUSE. The padding now mixes EX_Nothing "
    "with an EX_LocalVariable carrying one of the block's own refs -- compact "
    "on disk, four bytes in RAM -- so both the disk length and the memory size "
    "land on their original values exactly, measured for all four edits. "
    "ss_man_down was rebuilt that way, put on a disc reading mem=375 disk=283 "
    "against a stock 375/283, and STILL hung the initial load. So the declared "
    "size is not it either.\n\n"
    "THE CHUNK PADDING WAS NOT IT EITHER. The disc's own packer never "
    "leaves a byte after a compressed stream -- zero such chunks in any "
    "shipped COMMON package -- while this rebuild zero-padded any chunk "
    "that re-deflated smaller than its slot, 167 bytes for ss_man_down. "
    "lin._deflate_exact now fills the slot exactly; ss_man_down went onto "
    "a disc with zero trailing bytes anywhere and hung just the same. And "
    "rpg_speed, which works, pads 163 bytes, so the correlation was "
    "already broken before the test.\n\n"
    "Where that leaves it: the bytes reaching the console are provably the "
    "bytes intended (assembler round-trips 6,726 of 6,789 blocks byte-exactly, "
    "container decompresses back identically, archive layout unchanged, "
    "declared sizes now identical), and the console still will not load them. "
    "Static inspection has run out. The next step is a savestate taken DURING "
    "the hang, or PCSX2 EE breakpoints -- not another theory.")


#: Back on offer, but the padding fix has not yet survived a level load.
#: Put back at the player's request. None of these was ever bisected to a hang
#: itself -- they were withdrawn because they share the re-assembly path with
#: the two that were. That is a real reason to suspect them and not a reason to
#: hide them, so they are selectable again and marked for what they are.
RETRY = ("ai_sidearm", "ai_sidearm_contact", "ai_say_dry",
         "ss_chatter_kill", "ss_chatter_hostage")

RETRY_NOTE = (
    "RISKY. This edit RE-ASSEMBLES UnrealScript rather than poking bytes in "
    "place, and that path has frozen this disc's level load twice -- once on "
    "the initial load, once in split screen. Those two were different options, "
    "not this one, and this one has never been bisected to a hang on its own. "
    "It is switchable because suspicion by association is not proof, not "
    "because it is known to be safe.\n\n"
    "What is known: the assembler is faithful (6,726 of 6,789 script blocks "
    "round-trip byte-identically), the container repacks to the same length "
    "and decompresses back to exactly the bytes put in, the archive layout "
    "does not move, and the declared memory size now lands on its original "
    "value exactly. Three separate theories of the cause -- the shrinking "
    "memory size, the chunk padding, the declared size -- were each tested and "
    "each cleared. The cause is still not known.\n\n"
    "So: expect it to work, be ready for it not to. If a load hangs, this is "
    "the first thing to turn off, and RESTORE DISC puts the disc back exactly "
    "as it shipped.")


def _settings():
    out = _build_settings()
    for s in out:
        if s.key in RETRY and s.enabled:
            s.confidence = "untested"
            s.caution = RETRY_NOTE + ("\n\n" + s.caution if s.caution else "")
        if s.key in REASSEMBLED and s.enabled:
            s.enabled = False
            s.confidence = "broken"
            s.disabled_reason = REASSEMBLED_REASON
    return out


def _build_settings():
    return [
        # ---- wave mode -------------------------------------------------
        Setting("wave_enable", "Enable wave mode", BOOL, False, "Enemies",
                help="Rainbow Six 3 already ships a terrorist deployment-zone "
                     "system that the campaign uses and Terrorist Hunt never "
                     "triggers. This switches it on and hands you its dials.",
                caution="Terrorist Hunt will not finish loading with this on. "
                        "Measured on Parade: stock loads, a stock-plus-defaults "
                        "patch hangs on the load screen, and the same patch with "
                        "this off loads. The campaign is unaffected. Which of "
                        "the dials does it is not yet known, so treat the whole "
                        "feature as campaign-only for now.",
                confidence="verified"),
        Setting("wave_gate", "Where waves feed", CHOICE, "always", "Enemies",
                choices=[
                    Choice("always", "Every zone, all the time",
                           "Loudest option. Every deployment zone runs from the "
                           "moment the level starts."),
                    Choice("away", "Only zones you have left",
                           "The far zone feeds and pushes you back, and the zone "
                           "you walk out of starts up behind you. Needs a map "
                           "whose zones are far enough apart to be in different "
                           "engine zones -- Trieste shows it, Alcatraz cannot."),
                    Choice("stock", "Only where you are standing (stock rule)",
                           "The shipped behaviour. Enemies appear on top of you."),
                ],
                help="The engine gates the wave advance on the zone's stasis "
                     "flag, and it clears that flag for the zone containing a "
                     "player. This picks which way the test runs.",
                requires={"wave_enable": True}, confidence="verified"),
        Setting("wave_total", "Enemies each zone owes", INT, 30, "Enemies",
                minimum=1, maximum=250, unit="enemies",
                help="Total a single deployment zone will release before it is "
                     "spent. A map with three zones triples this.",
                requires={"wave_enable": True}, confidence="verified"),
        Setting("wave_size", "Released per wave", INT, 1, "Enemies",
                minimum=1, maximum=8, unit="enemies",
                help="How many come out each time a wave fires. Capped by the "
                     "number of spawn points the zone can reach, so on most maps "
                     "anything above 2-4 does nothing.",
                requires={"wave_enable": True}, confidence="verified"),
        Setting("wave_trigger", "Alive before the next wave", INT, 2, "Enemies",
                minimum=0, maximum=12, unit="enemies",
                help="THE VOLUME DIAL. A zone tops itself up until more than "
                     "this many of its enemies are alive, so steady state per "
                     "zone is about this number plus the release size. Set this "
                     "first, then the wave size, then the total.",
                requires={"wave_enable": True}, confidence="verified"),
        Setting("wave_hunt", "Enemies hunt you from the start", BOOL, True,
                "Enemies",
                help="This is the switch for enemies who come looking for you "
                     "rather than waiting to see you. Every enemy a wave "
                     "releases starts already hunting, so they cross the map "
                     "toward you instead of holding a patrol -- turn it off "
                     "and a zone waits to be triggered by the level's own "
                     "script, which in Terrorist Hunt never happens, so "
                     "nothing comes at all. Pair it with \"Spawn across the "
                     "whole map\" and the pressure arrives from every "
                     "direction rather than one corner.",
                caution="It reaches the enemies the wave system releases, not "
                        "the ones the designers placed by hand. Those keep "
                        "their authored behaviour and still have to see or "
                        "hear you first -- their strategy is chosen at "
                        "runtime and is not in the level file, so there is "
                        "nothing to edit for them short of rewriting script. "
                        "And nothing here lets anyone see through walls; the "
                        "engine has no such flag.",
                requires={"wave_enable": True}, confidence="verified"),
        Setting("wave_mapwide", "Spawn across the whole map", BOOL, True,
                "Enemies", pnach_only=True,
                help="Stock, a wave can only use the two or three spawn points "
                     "sitting next to it, so every enemy walks out of one corner. "
                     "This redirects the picker at every deployment point in the "
                     "level, which also brings a real spread of enemy types.",
                caution="Delivered as a PCSX2 cheat file, not written to the "
                        "disc. A code cave baked into the overlay does not "
                        "survive a level load.",
                requires={"wave_enable": True}, confidence="verified"),


        # ---- enemy behaviour, straight out of R6GAMESETTINGS.INI ---------
        Setting("grenade_carry", "How many enemies carry a grenade", INT, 20,
                "Enemy Behaviour", minimum=0, maximum=100, unit="%",
                confidence="applied", touches="data",
                help="This is the real grenade dial. What a terrorist spawns "
                     "holding is a weighted roll made once, at spawn, over a "
                     "small table in his template -- and sixteen of the "
                     "templates roll a grenade against nothing at somewhere "
                     "between 15 and 30 percent. This sets that share.",
                caution="There is no *throw* chance anywhere in the game. Once "
                        "a terrorist is holding a grenade the decision to use "
                        "it is deterministic, gated by the two settings below. "
                        "So this is how many of them can throw, and those are "
                        "when."),
        Setting("grenade_dist", "How close enemies will throw grenades", INT,
                500, "Enemy Behaviour", minimum=25, maximum=900,
                unit="units", confidence="applied", touches="data",
                help="The game will not let an NPC throw a grenade at anything "
                     "nearer than this. It ships at 500. Lower it and they use "
                     "grenades in close quarters instead of only lobbing them "
                     "across a room; raise it and grenades become a long-range "
                     "answer only."),
        Setting("grenade_delay", "How long they think about it first", CHOICE,
                "stock", "Enemy Behaviour", confidence="applied", touches="data",
                choices=[
                    Choice("stock", "Stock (1.0s recruit, 0.5s veteran)", ""),
                    Choice("quick", "Quicker (0.5s / 0.25s)",
                           "Roughly twice as many grenades in the same fight."),
                    Choice("instant", "Barely any (0.1s / 0.05s)",
                           "They throw the moment they have a reason to."),
                ],
                help="The reaction delay before an NPC commits to a throw. "
                     "Shortening it is the closest thing this game has to a "
                     "throw-chance dial."),
        Setting("molotov_everywhere", "Molotovs on every level", BOOL, False,
                "Enemy Behaviour", enabled=False, confidence="broken",
                touches="data",
                disabled_reason=(
                    "Withdrawn. An earlier build of this tool switched on a "
                    "per-map weapon table -- WS[43], R6MolotovGadget, shipped "
                    "true on Alcatraz only -- and that table is dead data on "
                    "PS2: the words bUsing, weaponname and sndName0 appear "
                    "ZERO times in the overlay, the boot executable and every "
                    "level package, so nothing can read those lines. Two maps "
                    "already ship it true and have no molotov enemies. It is a "
                    "leftover of the Xbox and PC sound-bank system."),
                help="Which enemies carry a molotov is decided by the terrorist "
                     "templates in COMMON, and only four of the 118 offer one. "
                     "Giving it to the others means replacing a class name with "
                     "a longer one, which a LIN package cannot take, so this "
                     "needs a different technique rather than a bigger number."),
        Setting("terro_skill", "Enemy skill", CHOICE, "stock",
                "Enemy Behaviour", confidence="applied", touches="data",
                choices=[
                    Choice("stock", "Stock (0.20 / 0.70 / 1.25)", ""),
                    Choice("up", "Sharper (+40%)", ""),
                    Choice("elite", "Everyone near-elite",
                           "All three tiers at 1.25, so recruits shoot like "
                           "elites do."),
                    Choice("down", "Softer (-40%)", ""),
                ],
                help="The per-difficulty multiplier the AI scales its aim and "
                     "its reactions by."),
        Setting("perfect_dist", "Range at which enemies never miss", INT, 500,
                "Enemy Behaviour", minimum=50, maximum=3000, unit="units",
                confidence="applied", touches="data",
                help="Inside this distance an NPC's shots have no dispersion at "
                     "all. It ships at 500. Lowering it is the most direct way "
                     "to make enemies less lethal up close; raising it does the "
                     "opposite."),

        # ---- shared with the other two Unreal-family discs ---------------
    ] + r6tuning.cards(
        ["fire_delay", "sight", "search_time", "speed", "spotting",
         "toughness"],
        "", "Enemy Behaviour",
    ) + xboxbuild.cards(xboxbuild.R6_3, "", "Enemy Behaviour") \
      + rseloadout.cards("r6_3_slus20883", "", "Enemy Behaviour") \
      + [rseloadout.flashlight_card("", "Enemy Behaviour")] \
      + [rserpg.card("", "Enemy Behaviour")] \
      + r6tuning.cards(["player_grenades", "player_mags"], "", "Loadout") + [

        # ---- teammates ---------------------------------------------------
        Setting("ai_finite_ammo", "AI teammates run out of ammunition", BOOL,
                False, TEAM_GROUP, confidence="verified", touches="data",
                help="The disc ships `m_bUnlimitedRainbowMagazines=true`, so "
                     "Price, Weber and Loiselle never spend a magazine no "
                     "matter how long a fight runs. This turns it off, and "
                     "they carry what the mission planner says they carry.\n\n"
                     "It is also the switch that puts their ammunition "
                     "callout back. \"No ammo, sir\" and \"Weapon's dry\" are "
                     "recorded in all three operatives' voice banks and wired "
                     "to a live event -- they simply never fire, because a "
                     "man with unlimited magazines is never dry. Turn this on "
                     "and you start hearing them.",
                caution="Their weapons deplete for the whole mission and "
                        "there is no way to pick one up off the ground, so a "
                        "long fight ends with the team on sidearms. That is "
                        "the point of the option, but it is a real change to "
                        "how a level plays. Trieste is the exception worth "
                        "knowing about: of the 567 teammate loadouts on the "
                        "disc, every one fills the secondary slot, but 21 of "
                        "Trieste's put a breaching charge or a flashbang "
                        "there instead of a pistol -- so on that level they "
                        "have nothing to fall back on."),
        Setting("ai_dry_rounds", "Rounds left in a weapon that has run dry",
                INT, 5, TEAM_GROUP, minimum=0, maximum=30, unit="rounds",
                confidence="applied", touches="data",
                requires={"ai_finite_ammo": True},
                help="`m_iNbOfBulletWhenEmpty`, which the disc ships at 5 and "
                     "describes in its own comment as \"bullets to put in "
                     "primary weapon when all clips are empty\". It is the "
                     "reserve a teammate falls back on once the magazines are "
                     "gone, and with unlimited magazines on it is unreachable "
                     "-- so the shipped 5 has never done anything.\n\n"
                     "Set it to 0 and running out means running out.",
                caution="A non-zero reserve appears to be re-granted rather "
                        "than issued once, which would mean they are never "
                        "permanently dry and the callout stays rare. That "
                        "reading comes from the key's comment and its name, "
                        "not from watching the code, so 0 is the setting to "
                        "use if you want the line reliably."),
    ] + rsesidearm.cards("", TEAM_GROUP) + rsekits.cards("", TEAM_GROUP) + [

        # ---- controls ----------------------------------------------------
        Setting("sens_steps", "Look sensitivity ceiling", INT, 10, "Controls",
                minimum=10, maximum=30, unit="steps", confidence="applied",
                touches="data",
                help="The in-game sensitivity slider stops at 10. This raises "
                     "how far it goes, so there are faster settings to pick "
                     "than the game normally offers.",
                caution="This lifts the ceiling for BOTH players. It does not "
                        "by itself make player 2 match player 1 -- why player 2 "
                        "is slower at the same number is a separate question, "
                        "and it is still being investigated."),
        Setting("sens_boost", "Look speed at each step", INT, 100, "Controls",
                minimum=50, maximum=400, unit="%", confidence="applied",
                touches="data",
                help="Scales the sensitivity multiplier and the per-step "
                     "increment together, so every notch on the slider moves "
                     "the camera further. 100% is stock."),

        # ---- split screen ----------------------------------------------
        Setting("viewmodel", "Show your weapon in split screen", BOOL, True,
                "Split Screen",
                help="The engine switches the first-person weapon off the moment "
                     "it detects split screen, through a global with exactly one "
                     "writer in the whole overlay. This removes that write.",
                confidence="verified"),
        Setting("fx_impact", "Bullet impact decals", BOOL, True, "Split Screen",
                help="Two branches skip the bullet-hole decal in split screen: "
                     "one for hits on the static world, one for hits on actors.",
                confidence="applied"),
        Setting("fx_emitters", "Bullet impact puffs and sparks", BOOL, True,
                "Split Screen",
                help="The dust/spark emitter that goes with an impact is skipped "
                     "in split screen by a third branch.",
                confidence="applied"),
        Setting("fx_blood", "Blood effects", BOOL, True, "Split Screen",
                confidence="applied",
                help="Restores the blood-effect position update."),
        rsewheel.card("", "Split Screen"),
        rsewheel.cycle_card("", "Split Screen"),
        rsewheel.label_card("", "Split Screen"),
        rsescope.card("", "Split Screen"),
        rsedraw.card("", "Split Screen"),
        rsescope.viewport_card("", "Split Screen"),
        rsescope.owner_card("", "Split Screen"),
        rseviewmodel.card("", "Split Screen"),
        rseviewmodel.turn_card("", "Split Screen"),
        rsefov.card("", "Split Screen"),
        rseshadow.card("", "Split Screen"),
        Setting("fx_weather", "Rain and snow", BOOL, True, "Split Screen",
                confidence="applied",
                help="Weather is gated off in split screen by a single branch."),
        Setting("fx_hidden_emitters", "Fire, water and scenery emitters", BOOL,
                True, "Split Screen",
                help="Levels flag a handful of emitters `HideInSplitScreen` and "
                     "the engine disables exactly those -- six per level, and "
                     "they are always the fire and water next to the players.",
                confidence="verified"),
        Setting("p2_look_speed", "Player 2 look speed", INT, 1, "Split Screen",
                minimum=1, maximum=256, unit="x", confidence="verified",
                help="Player 2 turns more slowly than player 1, and the cause "
                     "is one instruction. The input routine computes its own "
                     "frame delta, then at 0x00142048 substitutes 0.05 s for "
                     "it -- but only for pad index 1, and only when the real "
                     "frame is under 33 ms, which at any playable frame rate "
                     "is always. The look rate is `20.0 / delta`, so a delta "
                     "that has been made larger is a look rate that has been "
                     "made slower.\n\n"
                     "Nothing else differs. All 503 properties of the two "
                     "player controllers, both input objects and both 3 KB "
                     "viewport structs were compared from a savestate of both "
                     "players turning: every term in the look formula -- the "
                     "sensitivity steps, the option bits, the base rates, the "
                     "global multiplier, the acceleration terms -- is "
                     "byte-identical. The only thing that is not the same is "
                     "that register.\n\n"
                     "This dial does not remove the clamp. It rewrites the "
                     "lui/ori pair that builds the constant, so the "
                     "substituted delta becomes 0.05 / x. 1 leaves the disc "
                     "alone; 2 doubles player 2's look speed, 4 quadruples it, "
                     "and so on.",
                caution="3 is parity. Calculated, then confirmed in play. "
                        "Was: calculated rather than "
                        "guessed. Stock substitutes 0.05 s, which at 60 fps "
                        "is exactly three frames -- so player 2 turns at a "
                        "third of player 1's rate, which is the complaint. "
                        "3 makes the substituted value one real frame.\n\n"
                        "Do not try to match player 1's own delta. Measured "
                        "from a savestate of both players turning at full "
                        "stick, player 1's was 0.00032 s: the routine runs "
                        "more than once a frame, and player 1's rate is "
                        "applied over a correspondingly short interval, so "
                        "it self-corrects. Player 2's is a CONSTANT applied "
                        "over whatever the real interval turns out to be, so "
                        "it does not. That is why the earlier version of this "
                        "card -- a switch that removed the clamp outright -- "
                        "play-tested as an instant top turn rate, and why 32 "
                        "play-tested as far too fast: 32 leaves player 2 a "
                        "rate meant for a tenth of a frame.\n\n"
                        "Values above about 4 are for players who want player "
                        "2 faster than parity, not for matching. One cheap "
                        "check on the whole chain: the same clamp divides "
                        "player 2's MOVEMENT axes too, so if walking speed "
                        "shifts with this, the mechanism is confirmed end to "
                        "end."),
        Setting("p2_settings_persist", "Keep player 2's settings between "
                "missions", BOOL, False, "Split Screen", enabled=False,
                confidence="broken",
                disabled_reason=(
                    "Not shipped, and not for want of looking: eight "
                    "persistence layers and sixteen store sites were traced and "
                    "every one is symmetric between the two players. The one "
                    "remaining candidate -- that the level-start settings copy "
                    "runs once per level rather than once per player -- cannot "
                    "be settled without watching it run, and if it is right the "
                    "fix is a code cave rather than a changed word. The "
                    "obvious-looking one-word version would stamp the "
                    "single-player defaults onto both controllers every frame "
                    "and break player 1 as well."),
                help="Player 2's sensitivity resets at the start of every "
                     "mission while player 1's survives."),
        Setting("ss_accuracy", "Match enemy accuracy to single player", BOOL,
                False, "Split Screen", enabled=False, confidence="broken",
                disabled_reason=(
                    "There is nothing to switch. Every channel by which native "
                    "code can learn it is in split screen was enumerated -- 82 "
                    "accesses across four of them -- and not one lies in "
                    "weapon, aim, dispersion, line-of-sight, observation, "
                    "reaction-timer or damage code. The 21 split-screen tests "
                    "are rumble, input settings, HUD loop bounds, the audio "
                    "listener, a proximity trigger, seven render paths and one "
                    "animation LOD. The accuracy model itself is script-side "
                    "and has no split-screen variant."),
                help="If enemies feel less accurate with two players, the "
                     "shipped code does not say so. The Enemy Behaviour page "
                     "raises their skill and their never-miss range for both "
                     "modes at once, which is the lever that does exist."),
    ] + rseaicover.cards("", "Enemies") + rsefragwarn.cards("", TEAM_GROUP) + rsechatter.cards("", TEAM_GROUP) + [
        rsemandown.card("", "Split Screen"),
        rsecanon.card("", "Split Screen"),
        Setting("teammates", "AI teammates in split screen", BOOL, False,
                "Split Screen", enabled=False, confidence="broken",
                disabled_reason=(
                    "Not shipped: four separate attempts all hang the level "
                    "load, and the four hang states are byte-identical, so the "
                    "cause is upstream of every edit tried. Re-enabling the "
                    "script call is provably not sufficient."),
                help="Split screen deliberately builds a one-man team."),

        # ---- world ------------------------------------------------------
        Setting("decal_ring", "Bullet holes kept on screen", INT, 32, "World",
                minimum=32, maximum=160, unit="decals",
                help="Footprints and wall hits share a fixed-size ring buffer, "
                     "32 each by default. Raising it is the only way to keep "
                     "more bullet holes visible -- it cannot be made unlimited.",
                caution="Each extra decal is a real actor. 96 was measured as "
                        "128 extra actors and was backed out again on the "
                        "heaviest level, so raise this one step at a time.",
                confidence="applied"),
        Setting("bodies", "How long bodies stay", CHOICE, "stock", "World",
                choices=[
                    Choice("stock", "Stock (about 3 seconds)", ""),
                    Choice("15", "15 seconds", ""),
                    Choice("30", "30 seconds", ""),
                    Choice("60", "60 seconds", ""),
                    Choice("never", "Never disappear",
                           "Unbounded. Measured to collapse the framerate far "
                           "enough that world geometry stopped drawing at some "
                           "angles."),
                ],
                help="Two separate paths hide and destroy a corpse. The timed "
                     "options skip the first and widen the second's window.",
                confidence="verified"),
    ] + _mission_settings()


def build_edits(v: dict) -> list:
    """Turn a settings dict into the words to bake into SP.SOZ."""
    e = []

    def w(va, value, note):
        e.append(WordEdit(va, value, STOCK[va], note))

    if v.get("wave_enable"):
        w(0x0040AF58, li(V0, int(v["wave_total"])),
          "wave: each zone owes %d" % v["wave_total"])
        w(0x0040A8A8, li(S0, int(v["wave_size"])),
          "wave: %d released per wave" % v["wave_size"])
        w(0x0040AFDC, li(V1, int(v["wave_trigger"])),
          "wave: next-wave trigger = %d (seed)" % v["wave_trigger"])
        w(0x0040A874, li(V0, int(v["wave_trigger"])),
          "wave: next-wave trigger = %d (rearm)" % v["wave_trigger"])
        if v.get("wave_hunt"):
            # Three instructions that the m_iNbToSpawn constant above makes
            # dead: two pad nops and the mfhi whose result it overwrites.
            w(0x0040AF4C, 0x8E010388, "wave: m_bHuntFromStart |= 0x40 (lw)")
            w(0x0040AF50, 0x34210040, "wave: m_bHuntFromStart |= 0x40 (ori)")
            w(0x0040AF54, 0xAE010388, "wave: m_bHuntFromStart |= 0x40 (sw)")
        gate = v.get("wave_gate", "always")
        if gate != "stock":
            w(0x0040A790, WAVE_GATES[gate], "wave: stasis gate = %s" % gate)

    if v.get("viewmodel"):
        w(0x00302DA8, NOP, "keep the first-person weapon in split screen")
        if v.get("split_sway"):
            for va, value, _stock, note in rseviewmodel.words(
                    right_too=bool(v.get("split_sway_turn")), freed=True):
                w(va, value, note)
    scope = bool(v.get("split_scope"))
    fit = scope and bool(v.get("split_scope_fit"))
    labels = bool(v.get("split_wheel")) and bool(v.get("split_wheel_labels"))
    if scope:
        for va, value in rsescope.SCOPE_GUARD:
            w(va, value, "split screen: let the scope overlay draw, but only "
                         "once the renderer exists")
    elif fit or labels or (v.get("viewmodel") and v.get("split_sway")):
        # Something wants the cave but the scope option is off, so the dead
        # path still has its entry. Point that branch at the function's own
        # epilogue instead: split screen still branches away and still draws
        # nothing, exactly as stock, and the block is free.
        w(rsedeadpath.ENTRY, rsedeadpath.FREE_BRANCH,
          "split screen: retire the branch into the dead path")
    if fit:
        for va, value, _stock, note in rsescope.viewport_words(freed=True):
            w(va, value, note)
    if scope and v.get("split_scope_owner"):
        for va, value, _stock, note in rsescope.owner_words():
            w(va, value, note)
    if labels:
        for va, value, _stock, note in rsewheel.label_words(freed=True):
            w(va, value, note)
    if v.get("split_shadows"):
        w(rseshadow.SHADOW_GATE, rseshadow.SHADOW_GATE_FORCED,
          "split screen: let the shadow pass run")
    if v.get("fx_impact"):
        w(0x003F1934, NOP, "split screen: static-world impact decal")
        w(0x003F1BB4, NOP, "split screen: actor-attached impact decal")
    if v.get("fx_emitters"):
        w(0x003F250C, NOP, "split screen: impact emitter")
    if v.get("fx_blood"):
        w(0x003A14B8, NOP, "split screen: blood effect")
    if v.get("fx_weather"):
        w(0x003531D0, NOP, "split screen: rain and snow")
    if v.get("fx_hidden_emitters"):
        w(0x002375E0, NOP, "split screen: stop disabling flagged emitters")
    # Player 2's look speed. The routine clamps ITS OWN frame delta to 0.05 s
    # for pad index 1 only, and the look rate is `20.0 / delta`, so the smaller
    # the substituted delta the faster player 2 turns. This does not remove the
    # clamp -- the earlier card did, and it overshot badly -- it re-aims it, by
    # rewriting the lui/ori pair that builds the constant. The clamp still
    # fires (any substituted value is far below the 0.033 s test), it stays
    # player-2-only, and the result is a dial rather than a switch.
    speed = int(v.get("p2_look_speed", 1))
    if speed > 1:
        bits = struct.unpack("<I", struct.pack("<f", 0.05 / speed))[0]
        w(0x00142040, 0x3C030000 | (bits >> 16),
          "player 2 look: x%d, delta = %g s (high)" % (speed, 0.05 / speed))
        w(0x00142044, 0x34630000 | (bits & 0xFFFF),
          "player 2 look: x%d (low)" % speed)

    ring = int(v.get("decal_ring", 32))
    if ring != 32:
        w(0x00379B30, 0x24060000 | (ring & 0xFFFF), "decal ring = %d" % ring)

    bodies = v.get("bodies", "stock")
    if bodies == "never":
        w(0x00317570, 0x1000001D, "bodies: skip despawn path 1")
        w(0x003175F4, 0x1000001D, "bodies: skip despawn path 2")
    elif bodies in BODY_TIMERS and BODY_TIMERS[bodies]:
        w(0x00317570, 0x1000001D, "bodies: skip despawn path 1")
        w(0x00317600, BODY_TIMERS[bodies], "bodies: despawn after %ss" % bodies)

    return e


SKILL_SETS = {
    "stock": ("0.20", "0.70", "1.25"),
    "up":    ("0.28", "0.98", "1.75"),
    "elite": ("1.25", "1.25", "1.25"),
    "down":  ("0.12", "0.42", "0.75"),
}
GRENADE_DELAYS = {
    "stock":   ("1.0", "0.5"),
    "quick":   ("0.5", "0.25"),
    "instant": ("0.1", "0.05"),
}
#: shipped values the percentage dial scales
SENS_BASE = {"x_mult": 0.70, "y_mult": 0.60, "x_step": 0.15, "y_step": 0.15}


def build_data(v: dict) -> list:
    """Rainbow Six 3 keeps its AI tuning and its control curve in plain text.

    `R6GAMESETTINGS.INI` ships three identical copies, one per vokes archive,
    and all three are rewritten -- the game reads whichever answers first.
    Unlike the Ghost Recon mission files these are not inside the chunked
    compressor, so the edits do not have to preserve length.
    """
    out = []

    # One edit per mission whose dial has been moved. These rewrite counts
    # inside the level packages themselves, so they reach one mission only --
    # everything else on this profile is a global code patch.
    for stem, title, parts, _waves, kind in MISSIONS:
        # training authors no counts, so its dial is disabled and must never
        # emit an edit even if a saved config carries a value for it
        if kind == "training":
            continue
        pct = int(v.get(mission_key(stem), 100))
        if pct == 100:
            continue
        out.append(FileEdit("zone_counts", mission_select(stem, parts), "",
                            {"factor": pct / 100.0},
                            note="%s: enemy counts to %d%%" % (title, pct)))

    ini = {}
    # First, so that any dial the player has set themselves overwrites
    # the Xbox value for that key rather than the other way round.
    ini.update(xboxbuild.ini_updates(xboxbuild.R6_3,
                                     v.get("xbox_tuning", "stock"),
                                     bool(v.get("xbox_extra"))))

    if int(v.get("grenade_dist", 500)) != 500:
        ini["m_fMinDistToThrowGrenade"] = int(v["grenade_dist"])
    delay = v.get("grenade_delay", "stock")
    if delay != "stock":
        rec, vet = GRENADE_DELAYS[delay]
        ini["m_fGrenadeReactionDelayRecruit"] = rec
        ini["m_fGrenadeReactionDelayVeteran"] = vet
    skill = v.get("terro_skill", "stock")
    if skill != "stock":
        rec, vet, eli = SKILL_SETS[skill]
        ini["m_fTerroristSkillMultiplierRecruit"] = rec
        ini["m_fTerroristSkillMultiplierVeteran"] = vet
        ini["m_fTerroristSkillMultiplierElite"] = eli
    if int(v.get("perfect_dist", 500)) != 500:
        ini["m_fDistForPerfectAccuracyTerro"] = "%.1f" % float(v["perfect_dist"])
    # The two keys sit together in the file under "the following is for
    # rainbow AI only", and they only make sense together: the reserve is what
    # a teammate falls back on once his magazines are gone, which cannot
    # happen while the magazines are unlimited. So the reserve is written only
    # when the switch is on, and never on its own.
    if v.get("ai_finite_ammo"):
        ini["m_bUnlimitedRainbowMagazines"] = "false"
        rounds = int(v.get("ai_dry_rounds", 5))
        if rounds != 5:
            ini["m_iNbOfBulletWhenEmpty"] = rounds
    # the dials this disc shares with Ghost Recon 2 and Advanced Warfighter.
    # The keys that overlap with the lines above resolve to the same value, so
    # merging is idempotent rather than a second opinion.
    ini.update(r6tuning.ini_updates("", v))
    steps = int(v.get("sens_steps", 10))
    if steps != 10:
        ini["m_iXSensitivityMaxSteps"] = steps
        ini["m_iYSensitivityMaxSteps"] = steps
    boost = int(v.get("sens_boost", 100)) / 100.0
    if abs(boost - 1.0) > 0.001:
        ini["m_fXSensitivityMultiplier"] = "%.3f" % (SENS_BASE["x_mult"] * boost)
        ini["m_fYSensitivityMultiplier"] = "%.3f" % (SENS_BASE["y_mult"] * boost)
        ini["m_fXSensitivityStepIncrement"] = "%.3f" % (SENS_BASE["x_step"] * boost)
        ini["m_fYSensitivityStepIncrement"] = "%.3f" % (SENS_BASE["y_step"] * boost)

    if ini:
        out.append(FileEdit("ini_values", r"/R6GAMESETTINGS\.INI$", "",
                            {"values": ini}, "AI and control settings"))
    g1 = v.get("team_gadget_1", "stock")
    g2 = v.get("team_gadget_2", "stock")
    mine = bool(v.get("team_match_player"))
    per = {}
    for who in rsekits.OPERATIVES:
        slots = {}
        for suffix, field, _what in rsekits._SLOTS:
            pick = v.get("%s_%s" % (who.lower(), suffix), "stock")
            if pick != "stock":
                slots[field] = pick
        if slots:
            per[who] = slots
    if g1 != "stock" or g2 != "stock" or mine or per:
        # Every campaign map has its own INI. Multiplayer and menu INIs
        # carry no squad kits, so the transform reports zero on them and
        # leaves them byte-identical -- which is what makes one broad
        # selector safe here.
        out.append(FileEdit("team_gadget", r"/MAPS/[^/]+\.INI$", "",
                            {"primary": g1, "secondary": g2, "match": mine,
                             "per": per},
                            "teammate gadgets"))
    fov = int(v.get("fov", 90))
    if fov != int(rsefov.STOCK):
        out.append(FileEdit("fov", r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"degrees": fov},
                            "field of view: %d degrees" % fov))
    carry = int(v.get("grenade_carry", 20))
    if carry != 20:
        out.append(FileEdit("grenade_carry", r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"percent": carry},
                            "%d%% of two-entry templates carry a grenade" % carry))
    out += rseloadout.edits(v, "", r"/COMMON(OFF|_SS)?\.LIN$")
    if v.get("frag_warning"):
        out.append(FileEdit("frag_warning", r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"enable": True},
                            "teammates warn you about their own frag"))
    cover = str(v.get("ai_cover", "stock"))
    if cover != "stock":
        out.append(FileEdit("ai_cover", r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"set": cover},
                            "enemies fight from cover: %s"
                            % rseaicover.SHARES.get(cover, cover)))
    speed = int(v.get("rpg_speed", 1))
    if speed != 1:
        out.append(FileEdit("rpg_speed", r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"speed": speed},
                            "RPG troops ready a rocket %dx faster" % speed))
    # Gated on the ammunition switch, not merely paired with it on the page:
    # while magazines are unlimited the clip count is pinned at 1 and the
    # branch this reaches is unreachable, so writing the byte alone would be a
    # change to the disc that could not do anything.
    # The sidearm roll needs finite ammunition to be reachable at all; the
    # reload call-out does not -- it sits in the branch that runs either way.
    sidearm = int(v.get("ai_sidearm", 0)) if v.get("ai_finite_ammo") else 0
    say = int(v.get("ai_say_dry", 0))
    if sidearm or say:
        contact = bool(v.get("ai_sidearm_contact", True))
        notes = []
        if sidearm:
            notes.append("%d%% chance of drawing the pistol instead of "
                         "reloading%s"
                         % (sidearm, " while in contact" if contact else ""))
        if say:
            notes.append("%d%% chance of calling out a reload" % say)
        out.append(FileEdit("ai_sidearm", r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"chance": sidearm, "in_contact": contact,
                             "say_chance": say},
                            "; ".join(notes)))
    chatter = int(v.get("ss_chatter_kill", 0))
    if chatter:
        # COMMON_SS.LIN only, same reason as the canon team below.
        out.append(FileEdit("ss_chatter", r"/COMMON_SS\.LIN$", "",
                            {"chance": chatter,
                             "hostage": bool(v.get("ss_chatter_hostage", True))},
                            "split screen: %d%% chance player 2 calls out a kill"
                            % chatter))
    if v.get("canon_team"):
        # COMMON_SS.LIN only: that IS the split-screen package, which is what
        # keeps single player and Terrorist Hunt untouched by construction.
        out.append(FileEdit("canon_team", r"/COMMON_SS\.LIN$", "",
                            {"enable": True},
                            "split screen: player 2 is the mission's operative"))
    if v.get("ss_man_down"):
        out.append(FileEdit("ss_man_down", r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"enable": True},
                            "split screen: restore the death call-out"))
    if v.get("split_wheel"):
        out.append(FileEdit("split_wheel", r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"enable": True},
                            "split screen: open the equipment wheel on L1"))
    if v.get("split_draw_once"):
        out.append(FileEdit("split_draw", r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"enable": True},
                            "split screen: draw the weapon once, not twice"))
    if v.get("split_cycle"):
        out.append(FileEdit("split_cycle", r"/COMMON(OFF|_SS)?\.LIN$", "",
                            {"enable": True},
                            "split screen: a tap of L1 toggles two weapons"))
    return out


def build_pnach(v: dict) -> list:
    out = []
    if v.get("wave_enable") and v.get("wave_mapwide"):
        out.append(WordEdit(CAVE_HIJACK[0], CAVE_HIJACK[1],
                            STOCK[CAVE_HIJACK[0]],
                            "map-wide spawn points: hijack the point picker"))
        out += [WordEdit(va, word, 0, "map-wide spawn points: cave")
                for va, word in CAVE_WORDS]
    # The two split-screen HUD caves used to be emitted here. They are
    # disc words now, living in the scope draw's dead path -- see
    # rsedeadpath for why a cheat file could not hold them.
    return out


def combination_warnings(v: dict) -> list:
    """Settings that are fine alone and run the console out of memory together.

    The PS2 has 32 MB and no way to ask for more. Each of these on its own is
    survivable; the combination is what fills it.

    It bites hardest on RESTART. The report this was written from is a freeze
    in the mission-fail menu on the third or fourth retry from insertion, not
    during play -- so what runs the console out is the teardown-and-reload
    path, with each attempt leaving more behind than the last. That is also
    what makes it so hard to attribute: nothing goes wrong while you are
    alive, and the switch that caused it was set several sessions ago.
    """
    out = []

    # Said every time wave mode is on, not just in combination.
    #
    # Turning the DEFAULT off does nothing for anyone who already has it
    # stored: a saved profile carries the old value and goes on applying it,
    # which is exactly how this was missed. The reporter's profile still said
    # True hours after the default changed, so every apply they made through
    # the window carried wave mode -- and that sent one investigation after
    # an option that turned out to be innocent. A default is advice to new
    # discs; a warning is the only thing that reaches an old profile.
    if v.get("wave_enable"):
        out.append(
            "Wave mode is on, and Terrorist Hunt will not finish loading "
            "with it. Measured on Parade: stock loads, stock plus this hangs "
            "on the load screen, and turning this one setting off loads "
            "again. The campaign is unaffected. Turn it off under Enemies if "
            "you are playing Terrorist Hunt.")

    feeding = (v.get("wave_enable")
               and v.get("wave_gate", "stock") != "stock")
    forever = v.get("bodies", "stock") == "never"
    owed = int(v.get("wave_total", 0) or 0)
    trigger = int(v.get("wave_trigger", 99) or 99)
    ring = int(v.get("decal_ring", 32) or 32)

    if forever and feeding:
        out.append(
            "Bodies never despawning AND every deployment zone feeding is the "
            "combination that fills the console's 32 MB: the level keeps "
            "spawning and nothing is ever removed. It shows up on RESTART "
            "rather than during play -- retry a mission three or four times "
            "from insertion and it can freeze on the fail screen. Set bodies "
            "back to a timer, or let only the player's zone feed.")
    if forever and ring > 64:
        out.append(
            "Bodies never despawning with a decal ring of %d holds every "
            "corpse and %dx the stock number of bullet holes at once. Either "
            "alone is fine; together they are a lot of memory." % (ring, ring // 32))
    # Only worth saying alongside something that makes the population
    # unbounded: continuous spawning on its own is what this page is FOR, and
    # warning about the defaults on every plan would be noise.
    if forever and feeding and owed >= 20 and trigger <= 3:
        out.append(
            "%d enemies owed per zone with a refill whenever %d or fewer are "
            "alive means a zone never stops producing. With every zone feeding "
            "at once that is a continuous spawn for the whole mission."
            % (owed, trigger))
    return out


PROFILE = GameProfile(
    id="r6_3_slus20883",
    title="Tom Clancy's Rainbow Six 3",
    short="Rainbow Six 3",
    serial="SLUS-20883",
    boot="SLUS_208.83",
    volume_hint="SLUS_20883",
    pcsx2_crc="21CC1EC3",
    stock_words=STOCK,
    overlays=[SP],
    settings=_settings(),
    build_edits=build_edits,
    build_pnach=build_pnach,
    build_data=build_data,
    archive_pattern=r"/VOKES\d\.IMG$",
    notes=WAVE_MAPS,
    combination_warnings=combination_warnings,
    mission_art_for=mission_art_for,
    ui_art={
        "archive": "iso",
        "fbz": [r"/NTSC_CD/LE/SC\.FBZ$", r"/NTSC_CD/LE/LANG_BG\.FBZ$",
                r"/NTSC_CD/LE/PAD_ENG\.FBZ$", r"/NTSC_CD/LE/MCARD/.*\.FBZ$"],
    },
)

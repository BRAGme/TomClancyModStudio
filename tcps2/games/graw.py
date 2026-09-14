"""Ghost Recon Advanced Warfighter (PS2, SLUS-21422) -- profile.

It carries the Ghost Recon name, but this is **not** the Red Storm engine the
other two Ghost Recons run. It is Rainbow Six 3's: volume id `GR3`, Rainbow Six
3's disc layout down to `VOKES*.IMG` and `GVS.DAT`, and an overlay carrying
Rainbow Six 3's class names.

It does **not**, however, inherit Rainbow Six 3's deployment-zone wave system,
and that was worth establishing properly rather than assuming: a scan of all
five archives finds zero occurrences of `m_iNbToSpawn`, `m_NumberInWave`,
`m_bHuntFromStart` or `R6DZoneWave`, and in a package-serialised engine a
property that is never named in a package was never authored. So none of the
Rainbow Six 3 wave patches port. What replaced it is `GR3DeploymentZone` with
`m_iNbOfTerroristToSpawn`, and a wave set called "Endure" that exists in exactly
one file on the disc.

The overlay itself owns exactly **two** spawn numbers, both inside the Tick of
the `ScriptSpawnTerrorists` latent command at `0x0058E430` -- how often it
releases, and how many it releases each time. Everything else about a Survival
round lives in per-level data that has not been decoded. Those two are the dials
below.

`SP.IMG` is a plain uncompressed ELF, so a word patch is an in-place write with
no container to rebuild. Note its PT_LOAD sits at file offset **0x800**, not the
0x80 the other games use -- that was measured from the program header, and
getting it wrong writes 0x780 bytes off target.
"""

from __future__ import annotations

from ..model import CHOICE, INT, Choice, GameProfile, Overlay, Setting, WordEdit

BOOT = "SLUS_214.22"

#: the single-player overlay: a plain ELF, unlike Rainbow Six 3's packed one
SP = Overlay(
    name="SP.IMG",
    iso_pattern=r"/SP\.IMG$",
    base_va=0x00100000,
    kind="raw",
    file_delta=0x800,
    file_span=0x00634380 + 0x800,
)

STOCK = {
    0x0058E4BC: 0x3C023F80,   # lui v0, 0x3f80  -- 1.0s between releases
    0x0058E508: 0x24020001,   # addiu v0, zero, 1 -- one enemy per release
}

#: the upper half of an IEEE float; only these bits are settable by `lui`
INTERVALS = {
    "stock": 0x3F80,   # 1.0s
    "0.5": 0x3F00,
    "0.25": 0x3E80,
    "2.0": 0x4000,
}

NOTES = (
    "Advanced Warfighter reads correctly and the tool wears its artwork.\n\n"
    "Despite the name this is Rainbow Six 3's engine, not Ghost Recon's -- same "
    "volume id, same disc layout, same class names. But it did not inherit "
    "Rainbow Six 3's deployment-zone wave system: none of the property names "
    "that system needs appears anywhere in the five archives, so none of that "
    "work carries over.\n\n"
    "Its spawner is a mission-script command that releases one enemy per second "
    "until the script's count is used up. Those two numbers are the only spawn "
    "values the executable owns, and they are what the options here change. How "
    "many enemies a given Survival wave asks for lives in the level's own data, "
    "in a container that has not been decoded yet.\n\n"
    "One thing that is NOT here: difficulty does not scale enemies at all. The "
    "difficulty setting has three readers in the whole overlay -- two health "
    "regeneration gates and one picking between four authored floats. There is "
    "nothing to patch because there is nothing there.\n\n"
    "Mission S07 is cut. The executable's level table jumps from s06_b straight "
    "to s08_a, and the briefing list does the same."
)


def _settings():
    return [
        Setting("graw_interval", "How often Survival releases an enemy", CHOICE,
                "stock", "Enemy Waves", confidence="applied",
                choices=[
                    Choice("stock", "Stock -- one per second", ""),
                    Choice("0.5", "Twice as often", ""),
                    Choice("0.25", "Four times as often", ""),
                    Choice("2.0", "Half as often", ""),
                ],
                help="The scripted spawner drips enemies in one at a time on a "
                     "timer. This is that timer, and it is one of only two "
                     "spawn numbers the executable owns."),
        Setting("graw_per_release", "Enemies released each time", INT, 1,
                "Enemy Waves", minimum=1, maximum=8, unit="enemies",
                confidence="experimental",
                help="How many come out on each tick of the timer above. "
                     "Raising it multiplies the arrival rate without touching "
                     "the total a level asks for.",
                caution="The count is handed to UnrealScript, which has not "
                        "been read, so what a level does with more than one at "
                        "a time is a reasonable guess rather than a measured "
                        "fact. Try it one step at a time."),
    ]


def build_edits(v: dict) -> list:
    e = []
    interval = v.get("graw_interval", "stock")
    if interval != "stock":
        word = 0x3C020000 | INTERVALS[interval]
        e.append(WordEdit(0x0058E4BC, word, STOCK[0x0058E4BC],
                          "Survival spawn interval = %ss" % interval))
    n = int(v.get("graw_per_release", 1))
    if n != 1:
        e.append(WordEdit(0x0058E508, 0x24020000 | (n & 0xFFFF),
                          STOCK[0x0058E508],
                          "%d enemies per release" % n))
    return e


PROFILE = GameProfile(
    id="graw_slus21422",
    title="Tom Clancy's Ghost Recon Advanced Warfighter",
    short="Advanced Warfighter",
    serial="SLUS-21422",
    boot=BOOT,
    volume_hint="GR3",
    pcsx2_crc="433B0342",
    overlays=[SP],
    settings=_settings(),
    build_edits=build_edits,
    build_pnach=lambda v: [],
    build_data=lambda v: [],
    # GR3_1 and GR3_2 hold every single-player level package and are easy to
    # miss -- this disc has five archives, not the three the others have.
    archive_pattern=r"/(VOKES\d|MENU|GR3_\d)\.IMG$",
    stock_words=STOCK,
    notes=NOTES,
    ui_art={"archive": "iso", "fbz": [r"/CD/LE/GR3_\d\.FBZ$"]},
)

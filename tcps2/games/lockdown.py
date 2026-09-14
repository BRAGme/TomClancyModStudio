"""Rainbow Six: Lockdown (PS2, SLUS-21144) -- profile.

The odd one out on this shelf twice over. It is neither the Red Storm engine of
the Ghost Recons nor the Unreal build Rainbow Six 3 and Advanced Warfighter
share: it is Red Storm's **Nimitz** engine, and the paths baked into the
executable say so -- `C:/develop/Nimitz/NimitzPS2/Nimitz/Release/`.

**There are no overlays.** The whole game is one 7.2 MB boot ELF with a single
PT_LOAD at file +0x1000 mapping to 0x00100000. Nothing is paged in, so there is
no `SP.SOZ` to patch.

**There is no vokes archive either.** Data lives in one logical 3.94 GB stream
split across four ISO files -- `PS2DATA.PAK`, `.PA1`, `.PA2`, `.PA3` -- with no
header of its own. The index is the separate `PS2DATA.BIN`, and `tcps2.nimitz`
parses it: 173 directories, 4,671 files, and the parse consumes all 150,048
bytes with nothing left over, which is the check that it is right rather than
merely plausible. Sizes come from consecutive offsets; the parallel `sizes`
array agrees for every ordinary file but sets bit 31 on streamed video.

None of the three index files -- `PS2DATA.BIN`, `PS2DATA.BHS` or the
byte-identical duplicate `ZCDPADD.INN` -- carries a content hash. So an edit
that keeps a file's length needs no index repair, and one that does not keep it
is refused outright: the archive is never relocated.

What that buys, concretely, is the two cooked databases:

  * `nimitz.cgsb` -- 72 AI profiles, each with a faction, a name, six signed
    modifiers and six skills. The shipped difficulty ladder is right there in
    the data: `terrorist_super_easy` is all 1s, `terrorist-01/02/03` run
    12/12/16, `militia-01/02/03` run 1/8/12, `mercenary-01/02/03` run 14/18/20,
    and there are dedicated Terrorist Hunt profiles -- `th_terrorist`,
    `th_militia`, `th_merc`.

  * `nimitz.guns` -- 48 weapons, with magazine capacity and rate of fire at
    fixed offsets in a variable-length stat block.

**Not offered, and why.** Enemy COUNT is not a data edit: each enemy is a
discrete actor record inside a cooked `.mis` file, and the property names live
only in the executable, so the values are positional in a layout that has not
been decoded. Look sensitivity was not found at all -- the ELF contains no
`Sensitiv*` string. Split screen has no data knob, only a `-splitscreen`
command-line switch.
"""

from __future__ import annotations

from ..model import CHOICE, INT, Choice, FileEdit, GameProfile, Overlay, Setting

BOOT = "SLUS_211.44"

#: the boot ELF. One PT_LOAD, file +0x1000 -> 0x00100000, filesz 0x006D13D0.
ELF = Overlay(
    name=BOOT,
    iso_pattern=r"/SLUS_211\.44$",
    base_va=0x00100000,
    kind="raw",
    file_delta=0x1000,
    file_span=0x006D13D0 + 0x1000,
)

STOCK = {}

CGSB = r"/PS2DATA/BINARY/NIMITZ\.CGSB$"
GUNS = r"/PS2DATA/BINARY/NIMITZ\.GUNS$"

NOTES = (
    "Lockdown runs Red Storm's Nimitz engine -- not the Red Storm engine of "
    "the 2001 Ghost Recon, and not the Unreal build Rainbow Six 3 uses. The "
    "developer paths in the executable name it outright.\n\n"
    "It has no overlays: the whole game is one 7.2 MB boot ELF. And it has no "
    "vokes archive: its data is a single 3.94 GB stream split across "
    "PS2DATA.PAK, .PA1, .PA2 and .PA3, with the index in a separate file, "
    "PS2DATA.BIN. That index parses to 173 directories and 4,671 files and "
    "consumes every one of its 150,048 bytes, which is what makes it "
    "trustworthy rather than merely plausible.\n\n"
    "No index file carries a content hash, so an in-place edit needs no repair "
    "-- and an edit that would change a file's length is refused, because this "
    "archive is never relocated.\n\n"
    "The options here edit the two cooked databases. nimitz.cgsb holds 72 AI "
    "profiles whose difficulty ladder is visible in the data itself: "
    "terrorist_super_easy is all 1s, the three campaign terrorist tiers run "
    "12/12/16, militia runs 1/8/12, mercenaries run 14/18/20, and Terrorist "
    "Hunt has its own three profiles. nimitz.guns holds 48 weapons.\n\n"
    "What is NOT here. Enemy count is not a data edit -- each enemy is a "
    "discrete actor inside a cooked mission file whose field names live only "
    "in the executable, so the values are positional in a layout nobody has "
    "decoded. Look sensitivity was searched for and is absent: the executable "
    "contains no Sensitiv* string anywhere. Split screen has no data knob.\n\n"
    "On the look: the palette is measured off this disc's own loading frame -- "
    "a flat black ground, a cold steel blue clustered at hue 208-210, white "
    "lettering and the crimson from the wordmark. The SHAPE of the chrome is "
    "NOT copied from the game, because its shell textures could not be "
    "decoded: the .psx container splits exactly (a 70-byte header, a 1,024-byte "
    "palette, then one byte per pixel) and the palette is plainly right -- the "
    "game's reds and steels come out -- but the pixel order is a swizzle that "
    "resisted every variant tried, so the menus themselves were never seen.

"
    "One caveat worth stating plainly: none of this has been run in the game. "
    "The record layouts were established from the disc, and the skill reading "
    "was checked against every ordering the shipped profile names imply -- six "
    "independent ladder checks, none of which failed -- but that is static "
    "analysis, not play-testing."
)


def _settings():
    return [
        Setting("ld_enemy_skill", "Enemy skill", INT, 0, "Enemies",
                minimum=-8, maximum=8, unit="points", confidence="applied",
                touches="data",
                help="Every AI profile carries six skill values on a 1-20 "
                     "scale. This shifts them for the hostile factions only -- "
                     "terrorists, militia and mercenaries -- and leaves the "
                     "Rainbow operatives exactly as they ship. For scale: the "
                     "campaign's three terrorist tiers sit at 12, 12 and 16, "
                     "militia at 1, 8 and 12, and mercenaries at 14, 18 and "
                     "20, so +4 makes a militia grunt fight like a terrorist.",
                caution="70 of the 72 profiles decode; two -- mp_default and "
                        "deiter_weber_sniper -- use a variant this tool does "
                        "not read and are left alone. Values clamp at 20, so "
                        "the mercenaries barely move."),
        Setting("ld_hunt_only", "Only change Terrorist Hunt", CHOICE, "all",
                "Enemies", confidence="broken", touches="data",
                choices=[
                    Choice("all", "Every hostile profile", ""),
                    Choice("hunt", "Terrorist Hunt profiles only",
                           "th_terrorist, th_militia and th_merc -- the three "
                           "the Hunt modes draw from."),
                ],
                help="Terrorist Hunt draws from its own three profiles, so the "
                     "mode can be retuned without touching the campaign.",
                enabled=False,
                disabled_reason=(
                    "Not wired up yet. The three th_* profiles are identified "
                    "and editable, but restricting an edit to a named subset "
                    "needs a scope mechanism this archive does not have yet, "
                    "and shipping it as a switch that silently does the same "
                    "thing as the option above would be worse than leaving it "
                    "off.")),
        Setting("ld_mag_size", "Magazine capacity", INT, 100, "Weapons",
                minimum=25, maximum=400, unit="%", confidence="experimental",
                touches="data",
                help="Scales every weapon's magazine. The field was located by "
                     "scoring each candidate offset against real magazine "
                     "capacities -- the winner explains the Glock at 17, the "
                     "M9 at 15, the MEU at 7, the P90 at 50, the M249 at 200 "
                     "and the M870 at 5, where the next best offset explains "
                     "two weapons in nineteen.",
                caution="Weapons are shared: this is the enemy's magazine as "
                        "much as yours. Untested in game."),
        Setting("ld_fire_rate", "Rate of fire", INT, 100, "Weapons",
                minimum=25, maximum=300, unit="%", confidence="experimental",
                touches="data",
                help="Scales every weapon's rounds per minute. The shipped "
                     "values are clean -- 300 for pistols, 450 for the M870, "
                     "750 for the UMP and SPAS, 800 for the M249, 1000 for the "
                     "PKM -- on 44 of the 48 weapons; the four that read zero "
                     "are the RPG variants and the grenade launcher, and they "
                     "are skipped.",
                caution="Shared with the enemy, like the magazine. Untested."),
    ]


def build_data(v: dict) -> list:
    out = []
    steps = int(v.get("ld_enemy_skill", 0))
    if steps:
        out.append(FileEdit("nimitz_skills", CGSB, "",
                            {"steps": steps, "hostile_only": True},
                            "%+d skill on every hostile AI profile" % steps))
    mag = int(v.get("ld_mag_size", 100)) / 100.0
    rpm = int(v.get("ld_fire_rate", 100)) / 100.0
    if abs(mag - 1.0) > 0.001 or abs(rpm - 1.0) > 0.001:
        out.append(FileEdit("nimitz_guns", GUNS, "",
                            {"mag": mag, "rpm": rpm},
                            "magazines %d%%, rate of fire %d%%"
                            % (mag * 100, rpm * 100)))
    return out


PROFILE = GameProfile(
    id="lockdown_slus21144",
    title="Tom Clancy's Rainbow Six: Lockdown",
    short="Lockdown",
    serial="SLUS-21144",
    boot=BOOT,
    volume_hint="",
    pcsx2_crc="A80FBAAC",
    overlays=[ELF],
    settings=_settings(),
    build_edits=lambda v: [],
    build_pnach=lambda v: [],
    build_data=build_data,
    archive_pattern=r"/PS2DATA\.PAK$",
    archive_kind="nimitz",
    stock_words=STOCK,
    notes=NOTES,
    ui_art={"archive": "iso", "raw": [r"/PS2DATA/VIDEO/LOADING\.RAW$"]},
)

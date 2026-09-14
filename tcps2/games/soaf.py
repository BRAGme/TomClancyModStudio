"""The Sum of All Fears (PS2, SLES-51180) -- profile.

Red Storm's engine again, the same family as Ghost Recon PS2 and Jungle Storm,
but an earlier build and the odd one out on this shelf in three ways.

**It ships as a CD image, not a DVD.** The retail rip is MODE2/2352, so the
2,048 bytes of user data sit 24 bytes into each 2,352-byte sector. `tcps2.iso`
detects that and presents a flat logical view, which is what lets everything
else work unchanged.

**Its archives use 40-byte records, not 48** -- same fields up to +0x24, one
trailing word instead of three. Two of those fields are better than the later
games': +0x10 is an explicit `compressed` flag and the two sizes are (stored,
raw), so nothing has to be sniffed.

**Its textures are RSB version 8**, which is version 6 with seven bytes inserted
after the height, putting the pixels at the odd offset +35.

What it shares is the part that matters: the mission grammar is byte-for-byte
the one Ghost Recon uses, down to the spaces around `Easy = "0"`, so the same
transforms run on it unmodified.
"""

from __future__ import annotations

from ..model import BOOL, INT, FileEdit, GameProfile, Overlay, Setting
from . import rseweapons, rstuning

BOOT = "SLES_511.80"

ELF = Overlay(
    name=BOOT,
    iso_pattern=r"/SLES_511\.80$",
    base_va=0x00100000,
    kind="raw",
    file_delta=0x80,
    file_span=0x004A5780 + 0x80,
)

STOCK = {}

NOTES = (
    "The Sum of All Fears reads correctly -- 2,751 files across SOAF.IMG and "
    "MENU.IMG, with every one of its 1,674 compressed files decoding to exactly "
    "the length it declares -- and the tool wears its artwork.\n\n"
    "Its missions use the same grammar as Ghost Recon's, so the enemy options "
    "here are the same edits, running on this game unmodified.\n\n"
    "It has no render patches. Unlike Ghost Recon, which shipped an unstripped "
    "debug build, this executable is stripped, and it routes its tunables "
    "through name-driven registration tables rather than the instruction "
    "immediates that made Ghost Recon patchable -- so there is nothing "
    "honest to offer there yet.\n\n"
    "Two levers it has that Ghost Recon does not, both still to be wired up: "
    "CMBTMODL.XML holds the entire wound and difficulty model as named floats, "
    "and its game-type script tables are populated where all of Ghost Recon's "
    "missions shipped theirs empty."
)


def _settings():
    return [
        Setting("soaf_all_difficulties", "Every soldier on every difficulty",
                BOOL, False, "Enemies", confidence="applied", touches="data",
                help="The same per-actor Easy/Normal/Hard suppression flags "
                     "Ghost Recon uses. Deleting them puts the full "
                     "Hard-difficulty force into every mission at every "
                     "setting.",
                caution="Rewrites the mission files inside SOAF.IMG."),
        Setting("soaf_reveal_hidden", "Spawn the script-held reinforcements",
                BOOL, False, "Enemies", confidence="experimental",
                touches="data",
                help="Actors that ship Hidden=\"1\" wait for a mission script. "
                     "This puts them on the map from the start.",
                caution="An actor a script expects to spawn later may behave "
                        "oddly when it is already there."),
        Setting("soaf_skill", "Extra enemy skill", INT, 0, "Enemies",
                minimum=0, maximum=4, unit="points", confidence="applied",
                touches="data",
                help="Adds to armour, weapon skill, stamina, stealth and "
                     "leadership in every hostile template. Only templates used "
                     "by non-allied companies are touched, so your own side is "
                     "left alone."),
    ] + rstuning.cards("soaf_") + rstuning.soaf_cards()



#: Every mission with an order of battle, in the order the disc plays it.
#:
#: `CAMPAIGN.XML` gives the eleven-mission campaign; the five training levels
#: are not in it and are listed after it. Each `.MIS` names itself, and this
#: disc is inconsistent about how: the campaign writes "M01 Hostage Rescue
#: Operation" with no separator while the training writes "T01 - Movement", in
#: the same file set, which is why `rsemissions.codename` splits on the leading
#: mission number rather than on a dash.
#:
#: The last field is the briefing's overhead map. Unlike Ghost Recon, this disc
#: keeps the name its `.MIS` asks for, so `<MapShots>` resolves -- but that tag
#: points at a strip of six screenshots 923 pixels wide, which would swamp a
#: card, so the cards show the square `_BRIEFING` map beside it instead.
#:
#: (stem, number, title, place, date, time, soldiers, held back on Easy, map)
MISSIONS = (
    ("M01_TV STATION", "M01", "Hostage Rescue Operation", "Charleston, WV", "December 31, 2001", "22:00", 43, 11, "M01_TV STATION_BRIEFING"),
    ("M02_MILITIA", "M02", "Agent Recovery Operation", "Rural West Virginia", "January 5, 2002", "07:45", 51, 23, "M02_MILITIA_BRIEFING"),
    ("M03_WAREHOUSE", "M03", "Barren Garden", "Haifa, Israel", "January 31, 2002", "03:00", 52, 25, "M03_WAREHOUSE_BRIEFING"),
    ("M04_WEAPONFAC", "M04", "Janus Knife", "Near Tyre, Lebanon", "February 2, 2002", "06:00", 44, 15, "M04_WEAPONFAC_BRIEFING"),
    ("M05_PRISON", "M05", "Tiger Shell", "Near Tyre, Lebanon", "February 5, 2002", "14:00", 48, 21, "M05_PRISON_BRIEFING"),
    ("M06_MERCENARY", "M06", "Jagged Hammer", "Near Klaserie, South Africa", "February 8, 2002", "15:00", 37, 11, "M06_MERCENARY_BRIEFING"),
    ("M07_DIAMOND_MINE", "M07", "Glacier Rift", "South African Coast", "February 8, 2002", "20:00", 38, 11, "M07_DIAMOND_MINE_BRIEFING"),
    ("M08_OLSON_ESTATE", "M08", "Lightning Field", "Near Souillac, Mauritius", "February 10, 2002", "06:00", 42, 13, "M08_OLSON_ESTATE_BRIEFING"),
    ("M09_BANK", "M09", "Hollow Serpent", "Vienna, Austria", "February 12, 2002", "21:00", 36, 15, "M09_BANK_BRIEFING"),
    ("M10_CORPORATE_HQ", "M10", "Broken Chain", "Vienna, Austria", "February 13, 2002", "08:00", 33, 13, "M10_CORPORATE_HQ_BRIEFING"),
    ("M11_DRESSLERS_ESTATE", "M11", "Razor Scythe", "Vienna, Austria", "February 13, 2002", "14:00", 33, 11, "M11_DRESSLERS_ESTATE_BRIEFING"),
    ("T01", "T01", "Movement", "Fort Bragg, NC", "October 20, 2001", "23:00", 7, 0, "TRAINING_BRIEFING"),
    ("T02", "T02", "Small Arms", "Fort Bragg, NC", "October 20, 2001", "23:00", 7, 0, "TRAINING_BRIEFING"),
    ("T03", "T03", "Grenades", "Fort Bragg, NC", "October 20, 2001", "23:00", 7, 0, "TRAINING_BRIEFING"),
    ("T04", "T04", "Objects", "Fort Bragg, NC", "October 20, 2001", "23:00", 7, 0, "TRAINING_BRIEFING"),
    ("T05", "T05", "Killhouse", "Fort Bragg, NC", "October 20, 2001", "23:00", 7, 0, "TRAINING_BRIEFING"),
)

MISSION_GROUP = "Missions"


def mission_key(stem):
    return "mission_" + stem.lower().replace(" ", "_")


def mission_art_for(key):
    """The briefing map this mission's card should show."""
    for mission in MISSIONS:
        if key == mission_key(mission[0]):
            return [mission[8]]
    return []


def mission_select(stem):
    """A regex matching just this mission's script inside the archive.

    `re.escape` because one of them really is called `M01_TV STATION.MIS`,
    space and all.
    """
    import re
    return r"/%s\.MIS$" % re.escape(stem)


def _mission_settings():
    """One switch per mission: put that mission's full force into every
    difficulty, without touching any other mission.

    The same machinery as Ghost Recon's page, because it is the same mission
    grammar -- and the figures are counted off this disc, not carried over.
    The five training levels place seven actors each and suppress none of them,
    so their cards say so and their switches are off.
    """
    out = []
    for stem, number, title, place, date, time, actors, held, _map in MISSIONS:
        when = ", ".join(x for x in (place, date, time) if x)
        if held:
            help_text = ("%s. %d soldiers placed, %d of them removed below "
                         "Hard. This puts the full Hard force into this "
                         "mission at every difficulty, and nothing else moves."
                         % (when, actors, held))
        else:
            help_text = ("%s. %d soldiers placed, none of them suppressed on "
                         "any difficulty -- this level already turns out in "
                         "full at every setting." % (when, actors))
        out.append(Setting(
            mission_key(stem), "%s  %s" % (number, title), BOOL, False,
            MISSION_GROUP, help=help_text, touches="data",
            enabled=bool(held),
            disabled_reason=("" if held else
                             "Nothing to release: this level authors no "
                             "difficulty suppression flags at all, so every "
                             "soldier already turns out at every setting."),
            confidence="measured"))
    return out


def build_data(v: dict) -> list:
    out = []
    # Per-mission first, and skipped entirely when the global switch
    # is on: that one already strips every .MIS, so a per-mission edit
    # on top would be a second pass over a file with nothing left in
    # it to strip.
    if not v.get("soaf_all_difficulties"):
        for mission in MISSIONS:
            if v.get(mission_key(mission[0])):
                out.append(FileEdit(
                    "strip_difficulty", mission_select(mission[0]),
                    "SOAF.IMG",
                    note="every soldier in %s %s"
                         % (mission[1], mission[2])))
    if v.get("soaf_all_difficulties"):
        out.append(FileEdit("strip_difficulty", r"\.MIS$", "SOAF.IMG",
                            note="every soldier on every difficulty"))
    if v.get("soaf_reveal_hidden"):
        out.append(FileEdit("reveal_hidden", r"\.MIS$", "SOAF.IMG",
                            note="spawn the script-held reinforcements"))
    skill = int(v.get("soaf_skill", 0))
    if skill:
        out.append(FileEdit("bump_stats", r"\.ATR$", "SOAF.IMG",
                            {"steps": skill},
                            "+%d to every hostile template's skills" % skill,
                            scope="enemy_templates"))
    out += rseweapons.edits('soaf_', v, 'SOAF.IMG')
    out += rstuning.edits("soaf_", v, "SOAF.IMG")
    out += rstuning.soaf_edits(v)
    return out


PROFILE = GameProfile(
    id="soaf_sles51180",
    title="Tom Clancy's The Sum of All Fears",
    short="Sum of All Fears",
    serial="SLES-51180",
    boot=BOOT,
    volume_hint="SOAF",
    pcsx2_crc="4691F6F7",
    overlays=[ELF],
    settings=(_settings() + rseweapons.cards('soaf_')
              + _mission_settings()),
    build_edits=lambda v: [],
    build_pnach=lambda v: [],
    build_data=build_data,
    archive_pattern=r"/(SOAF|MENU)\.IMG$",
    stock_words=STOCK,
    mission_art_for=mission_art_for,
    notes=NOTES,
    ui_art={"archive": "vokes", "patterns": [r"\.RSB$"]},
)

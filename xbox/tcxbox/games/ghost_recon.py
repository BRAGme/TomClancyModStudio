"""Ghost Recon and Ghost Recon: Island Thunder on Xbox.

One module for two games because they are one game twice: Island Thunder is a
Ghost Recon build with eight Cuban missions bolted on, it reuses three of the
original maps outright, and every file format, tag name and skill scale is
identical. Everything below is driven off a per-game census measured out of the
folders rather than shared constants, so the two profiles say true things about
themselves and not about each other.

**The enemies live in data, not code.** A mission's `<Units>` block is the order
of battle and one `<Actor>` is one soldier. The shipping game scales difficulty
by removing soldiers, with a per-actor suppression flag:

    <Actor ... File = "m02_rec_ak47_2.atr" Easy = "0" Normal = "0"/>

`Easy = "0"` means *this soldier is not there on Easy*. There is no `"1"` form
anywhere in either game and absence of the attribute means present, so deleting
the attributes puts the full Hard-difficulty force into every difficulty. That
is the single biggest lever available: Ghost Recon's campaign goes from 507
soldiers on Easy to all 834, and Island Thunder's from 371 to 566.

**Where the files actually are.** This is the trap that makes the Xbox port
different from the PS2 one. The mission XML sits loose under `mission\\` *and*
inside `globs\\ikedata.glb`, byte for byte identical, while the `.atr` templates
those missions name sit *only* inside the per-level `*_chars.glb`. Editing the
loose copy alone is a real way to produce a mod that does nothing. The folder
index in `gamedir` keys every copy and writes all of them, so a selector like
`\\.MIS$` reaches both and they cannot drift apart.

**What is not here.** There is no wave-count dial, for the same reason there is
none on the PS2 disc: reading every `.gtf` in both games turns up 28 named
script variables and not one of them is an enemy count -- they are text ids,
capture timers and control-point indices. The card that says so is shipped
disabled rather than left out, because "why is there no wave option" is a
question worth answering in the interface.
"""

from __future__ import annotations

from ..model import (BOOL, CHOICE, INT, Choice, FileEdit, GameProfile, Marker,
                     Setting)
from . import rseweapons, rstuning

MISSION_GROUP = "Missions"

#: (stem, actors placed, actors carrying a difficulty flag, actors that ship
#: Hidden, codename, place, date, time, briefing sheet, tactical map) --
#: counted and read out of the games themselves, campaign missions only.
#: Multiplayer and Defend variants place no order of battle at all and are left
#: off the page rather than listed as empty.
#:
#: The last two fields are the mission's own artwork. The sheet name is taken
#: from the mission file's `<MapShots>` rather than derived, because it does not
#: always follow the stem: `m10_ruined_city.mis` asks for `m10_vilnius_shots`.
#: An empty map field means the disc ships no tactical map for that mission --
#: four of Ghost Recon's fifteen, and the card simply shows the screenshots.
GR_MISSIONS = (
    ("M01_CAVES", 52, 25, 0, "Iron Dragon", "South Ossetia", "04/16/08", "05:45", "m01_caves_shots", "M01_CAVES"),
    ("M02_FARM", 50, 17, 0, "Eager Smoke", "South Ossetia", "04/24/08", "02:15", "m02_farm_shots", "M02_FARM"),
    ("M03_RRBRIDGE", 54, 21, 0, "Stone Bell", "South Ossetia", "05/02/08", "10:00", "m03_rrbridge_shots", "M03_RRBRIDGE"),
    ("M04_VILLAGE", 58, 29, 15, "Black Needle", "Republic of Georgia", "05/07/08", "15:00", "m04_village_shots", "M04_VILLAGE"),
    ("M05_EMBASSY", 67, 34, 0, "Gold Mountain", "Tbilisi, Georgia", "05/14/08", "09:00", "m05_embassy_shots", "M05_EMBASSY"),
    ("M06_CASTLE", 53, 30, 0, "Witch Fire", "Izborsk, Russia", "06/06/08", "02:00", "m06_castle_shots", "M06_CASTLE"),
    ("M07_RIVER", 47, 18, 0, "Paper Angel", "Lubana River, Latvia", "06/17/08", "06:00", "m07_river_shots", "M07_RIVER"),
    ("M08_BATTLEFIELD", 63, 37, 0, "Zebra Straw", "Venta, Lithuania", "06/24/08", "16:00", "m08_battlefield_shots", "M08_BATTLEFIELD"),
    ("M09_SWAMP", 62, 43, 0, "Blue Storm", "Nereta Swamp, Latvia", "07/03/08", "09:00", "m09_swamp_shots", ""),
    ("M10_RUINED_CITY", 49, 22, 0, "Fever Claw", "Vilnius, Lithuania", "09/01/08", "18:00", "m10_vilnius_shots", ""),
    ("M11_POW_CAMP", 63, 36, 0, "Dream Knife", "Ljady, Russia", "09/16/08", "03:00", "m11_pow_camp_shots", ""),
    ("M12_DOCKS", 52, 28, 0, "Ivory Horn", "Murmansk, Russia", "09/22/08", "02:00", "m12_docks_shots", "M12_DOCKS"),
    ("M13_AIRBASE", 47, 22, 0, "Arctic Sun", "Arkhangel'sk, Russia", "10/03/08", "04:00", "m13_airbase_shots", "M13_AIRBASE"),
    ("M14_MOUNTAIN", 53, 18, 0, "Willow Bow", "Toropec, Russia", "10/23/08", "13:00", "m14_mountain_shots", "M14_MOUNTAIN"),
    ("M15_RED_SQUARE", 64, 31, 3, "White Razor", "Moscow, Russia", "11/10/08", "11:00", "m15_red_square_shots", ""),
)

IT_MISSIONS = (
    ("XC01_PLANTATION", 45, 15, 0, "Watchful Yeoman", "Punta Tabacal", "03/20/10", "06:30", "xc01_shots", "XC01_PLANTATION"),
    ("XC02_MILITARY_CAMP", 45, 15, 0, "Angel Rage", "Pinar del Rio", "04/03/10", "19:30", "xc02_shots", "XC02_MILITARY_CAMP"),
    ("XC03_HIGH_SIERRA", 47, 15, 0, "Jaguar Maze", "Sierra de los Organos", "04/12/10", "11:20", "xc03_shots", "XC03_HIGH_SIERRA"),
    ("XC04_SWAMP_AIRFIELD", 45, 15, 0, "Hidden Spectre", "Isla de la Juventud", "04/21/10", "10:40", "xc04_shots", "XC04_SWAMP_AIRFIELD"),
    ("XC05_BRIDGES", 47, 15, 0, "Rapid Python", "Matanzas Province", "04/27/10", "01:00", "xc05_shots", "XC05_BRIDGES"),
    ("XC06_POLLING_CENTER", 54, 15, 0, "Liberty Storm", "Cienfuegos", "05/12/10", "06:45", "xc06_shots", "XC06_POLLING_CENTER"),
    ("XC07_BEACH_RESORT", 49, 15, 0, "Ocean Forge", "Near Dimas", "05/19/10", "06:45", "xc07_shots", "XC07_BEACH_RESORT"),
    ("XC08_MOUNTAIN_STRONGHOLD", 51, 15, 0, "Righteous Archer", "Sierra de los Organos", "06/06/10", "20:20", "xc08_shots", "XC08_MOUNTAIN_STRONGHOLD"),
    # The three Ghost Recon maps Island Thunder ships again, unchanged.
    ("M05_EMBASSY", 67, 34, 0, "Gold Mountain", "Tbilisi, Georgia", "05/14/08", "09:00", "m05_embassy_shots", "M05_EMBASSY"),
    ("M06_CASTLE", 53, 30, 0, "Witch Fire", "Izborsk, Russia", "06/06/08", "02:00", "m06_castle_shots", "M06_CASTLE"),
    ("M08_BATTLEFIELD", 63, 37, 0, "Zebra Straw", "Venta, Lithuania", "06/24/08", "16:00", "m08_battlefield_shots", "M08_BATTLEFIELD"),
)


def _totals(missions):
    placed = sum(m[1] for m in missions)
    flagged = sum(m[2] for m in missions)
    hidden = sum(m[3] for m in missions)
    return placed, flagged, hidden


def mission_key(prefix, stem):
    return "%smis_%s" % (prefix, stem.lower())


def mission_select(stem):
    """Both copies of one mission -- the loose file and the packed one."""
    return r"/%s\.MIS$" % stem


def notes_for(name, missions, guns):
    placed, flagged, hidden = _totals(missions)
    return (
        "%s keeps its enemies in data, so everything on the Enemies page "
        "rewrites the game's own mission files rather than patching code. The "
        "originals are copied beside the game folder before the first change "
        "and “Restore folder” puts every one of them back at the byte "
        "it came from.\n\n"
        "Counted out of this folder: %d soldiers placed across %d campaign "
        "missions, %d of them carrying a flag that removes them below Hard, "
        "and %d that ship despawned waiting for a script. %d weapons.\n\n"
        "Every mission file exists twice -- loose under mission\\ and inside "
        "globs\\ikedata.glb -- and the enemy templates exist only inside the "
        "per-level *_chars.glb. This tool writes every copy of a file it "
        "changes, which is the difference between a mod that works and one "
        "that appears to do nothing."
        % (name, placed, len(missions), flagged, hidden, guns))


CAMPAIGN_FILE = r"/MISSION/CAMPAIGN\.XML$"

#: Ghost Recon ships 47 mission files and its campaign names 15. Fifteen of the
#: rest are the `_defend` twin of each campaign map -- the same terrain with the
#: mission turned round, you holding ground instead of taking it -- and nine are
#: the multiplayer maps. None of the 32 is referenced by `campaign.xml`.
GR_DEFEND = (
    "m01_caves_defend.mis",
    "m02_farm_defend.mis",
    "m03_rrbridge_defend.mis",
    "m04_village_defend.mis",
    "m05_embassy_defend.mis",
    "m06_castle_defend.mis",
    "m07_river_defend.mis",
    "m08_battlefield_defend.mis",
    "m09_swamp_defend.mis",
    "m10_ruined_city_defend.mis",
    "m11_pow_camp_defend.mis",
    "m12_docks_defend.mis",
    "m13_airbase_defend.mis",
    "m14_mountain_defend.mis",
    "m15_red_square_defend.mis",
)

GR_MP = (
    "mp01_river.mis",
    "mp02_nightbattle.mis",
    "mp03_railroad.mis",
    "mp04_valley.mis",
    "mp05_docks.mis",
    "mp06_castle.mis",
    "mp07_stronghold.mis",
    "mp08_creekbed.mis",
    "mp09_wilderness.mis",
)

#: Island Thunder names 8 of its 27. Three of the unlisted ones are complete
#: GHOST RECON missions sitting on the Island Thunder disc -- Embassy, Castle
#: and Battlefield -- which is the one find here that is genuinely content from
#: another game rather than a variant of this one.
IT_GHOST_RECON = (
    "m05_embassy.mis",
    "m06_castle.mis",
    "m08_battlefield.mis",
)

IT_COOP = (
    "xcp01_hunting_lodge.mis",
    "xcp02_island.mis",
    "xcp03_prison.mis",
    "xcp04_island_village.mis",
    "xcp05_market.mis",
)

IT_DEFEND = (
    "xd01_beach.mis",
    "xd03_traindepot.mis",
    "xd06_ghosttown.mis",
)

CAMPAIGN = "Campaign"

#: {choice: (label, help, missions)} per game. Keyed by prefix because the two
#: games share this file and have nothing else in common here.
CAMPAIGN_SETS = {
    "gr_": (
        ("defend", "Play the Defend campaign instead",
         "The same fifteen maps with the mission reversed -- holding ground "
         "rather than taking it.", GR_DEFEND, True),
        ("mp", "Play the multiplayer maps as a campaign",
         "The nine adversarial maps, in order.", GR_MP, True),
    ),
    "it_": (
        ("ghost_recon", "Add the three Ghost Recon missions",
         "Embassy, Castle and Battlefield, complete on this disc.",
         IT_GHOST_RECON, False),
        ("coop", "Add the co-op maps", "All five.", IT_COOP, False),
        ("defend", "Add the Defend maps", "All three.", IT_DEFEND, False),
        ("all", "Add all eleven", "",
         IT_GHOST_RECON + IT_COOP + IT_DEFEND, False),
    ),
}


def _campaign_card(prefix):
    sets = CAMPAIGN_SETS[prefix]
    total = len({m for _v, _l, _h, ms, _r in sets for m in ms})
    swaps = all(r for _v, _l, _h, _m, r in sets)
    tail = ("\n\nThese choices SWAP the campaign rather than lengthening it. A "
            "disc image can only grow a file into its own sector padding, and "
            "a doubled campaign does not fit; one of the same length always "
            "does."
            if swaps else
            "\n\nThe extra missions go on the end, after the last shipped one, "
            "in the order shown.")
    return Setting(
        prefix + "campaign", "Missions in the campaign", CHOICE, "stock",
        CAMPAIGN,
        choices=[Choice("stock", "As shipped", "")]
                + [Choice(v, label, help_text)
                   for v, label, help_text, _m, _r in sets],
        confidence="experimental",
        help="The campaign is one file: Mission\\campaign.xml, a flat list of "
             "mission filenames. This disc ships %d mission files the list "
             "never names, and they are complete -- same format, same folder, "
             "loaded the same way.%s" % (total, tail),
        caution="Experimental. A mission written as a multiplayer or Defend "
                "map has no briefing, and may have no ending condition a "
                "single player can reach. Nothing here can damage a disc -- "
                "Restore game puts the original list back exactly.")


def _campaign_edits(prefix, v):
    choice = v.get(prefix + "campaign", "stock")
    for value, label, _help, missions, replace in CAMPAIGN_SETS[prefix]:
        if choice == value:
            return [FileEdit("campaign", CAMPAIGN_FILE,
                             {"add": list(missions), "replace": replace},
                             "%s (%d mission(s))"
                             % (label.lower(), len(missions)))]
    return []


def _settings(prefix, missions, has_env):
    placed, flagged, hidden = _totals(missions)
    out = [
        Setting(prefix + "no_wave_dial", "Wave-count dial", BOOL, False,
                "Enemies", enabled=False, confidence="broken",
                disabled_reason=(
                    "There is nothing to put here. Reading every .gtf in the "
                    "game turns up 28 named script variables and not one of "
                    "them is an enemy count -- they are text ids, capture "
                    "timers and control-point indices. All of this game's "
                    "enemy scaling is done with the placed order of battle, "
                    "which is what the options below edit."),
                help="Where a wave-size number would go if the game had one."),

        Setting(prefix + "all_difficulties", "Every soldier on every difficulty",
                BOOL, False, "Enemies", confidence="applied",
                help="The game removes soldiers on lower difficulties with "
                     "per-actor Easy/Normal/Hard flags. Deleting them puts the "
                     "full Hard-difficulty force into every mission at every "
                     "setting -- %d of the %d soldiers in the campaign carry "
                     "one." % (flagged, placed),
                caution="Rewrites every campaign mission, in both the loose "
                        "copy and the one inside ikedata.glb."),

        Setting(prefix + "reveal_hidden", "Spawn the script-held reinforcements",
                BOOL, False, "Enemies",
                confidence="experimental" if hidden else "broken",
                enabled=bool(hidden),
                disabled_reason=("" if hidden else
                                 "No actor in this game's campaign ships with "
                                 "Hidden=\"1\" -- there is nothing held back "
                                 "for a script to bring in."),
                help="%d actors ship with Hidden=\"1\" and wait for a mission "
                     "script to bring them in. This puts them on the map from "
                     "the start." % hidden,
                caution="An actor a script expects to spawn later may behave "
                        "oddly when it is already there."),

        Setting(prefix + "tier", "Enemy skill tier", CHOICE, "stock", "Enemies",
                confidence="applied",
                choices=[
                    Choice("stock", "As shipped", ""),
                    Choice("up1", "One tier tougher",
                           "Recruits become veterans, veterans become elites."),
                    Choice("elite", "Everyone elite",
                           "Armour 3 and skills 3-5 across the board."),
                    Choice("down1", "One tier softer", ""),
                ],
                help="Every enemy is named by skill tier in the mission file "
                     "-- m02_rec_ak47_2.atr -- and the three tiers really are "
                     "different numbers. This repoints each one at the tier "
                     "above or below without moving anybody. All three markers "
                     "are five characters, so nothing changes length."),

        Setting(prefix + "skill", "Extra enemy skill", INT, 0, "Enemies",
                minimum=0, maximum=4, unit="points", confidence="applied",
                help="Adds to armour, weapon skill, stamina, stealth and "
                     "leadership in every hostile template. Only templates a "
                     "non-allied company actually uses are touched, so your own "
                     "squad is left alone.",
                caution="Two points already puts recruits above shipped elites."),
    ]
    out += rseweapons.cards(prefix)
    out += [c for c in rstuning.cards(prefix)
            if has_env or not c.key.endswith("spot")]
    out += [_campaign_card(prefix)]
    out += _mission_settings(prefix, missions)
    return out


def _mission_settings(prefix, missions):
    """One switch per mission: the global "every soldier on every difficulty"
    aimed at a single file, with that mission's own numbers on the card."""
    out = []
    for (stem, actors, held, hidden, codename, place, date, time,
         _shots, _map) in missions:
        when = ", ".join(x for x in (place, date, time) if x)
        if held:
            help_text = ("%s. %d soldiers placed, %d of them removed below "
                         "Hard. This puts the full Hard force into this "
                         "mission at every difficulty, and nothing else moves."
                         % (when, actors, held))
        else:
            help_text = ("%s. %d soldiers placed, none of them suppressed on "
                         "any difficulty -- this mission already turns out in "
                         "full at every setting." % (when, actors))
        label = stem.split("_")[0].lstrip("X")
        out.append(Setting(
            mission_key(prefix, stem), "%s  %s" % (label, codename), BOOL, False,
            MISSION_GROUP, help=help_text, enabled=bool(held),
            disabled_reason=("" if held else
                             "Nothing to release: this mission authors no "
                             "difficulty suppression flags at all."),
            confidence="applied"))
    return out


def _mission_art_for(prefix, missions):
    """key -> the pictures its card should show, most informative first.

    Three, because that is what a card has room for: the briefing's tactical
    map, then two of the four screenshots off the mission's own briefing sheet.
    A mission with no map on the disc gets a third screenshot instead, so every
    card is the same shape whether or not its map was drawn.
    """
    by_key = {}
    for m in missions:
        stem, shots, tactical = m[0], m[8], m[9]
        names = []
        if tactical:
            names.append(tactical)
        if shots:
            names += ["%s#%d" % (shots, n)
                      for n in range(3 - len(names) + 1)][:3 - len(names)]
        by_key[mission_key(prefix, stem)] = names

    def lookup(key):
        return by_key.get(key, ())

    return lookup


def _build_data(prefix, missions):
    def build(v: dict) -> list:
        out = _campaign_edits(prefix, v)
        # Per-mission switches are skipped entirely when the global one is on:
        # that already strips every .MIS, so a second pass over a file with
        # nothing left in it to strip would only be work.
        if not v.get(prefix + "all_difficulties"):
            for m in missions:
                if v.get(mission_key(prefix, m[0])):
                    out.append(FileEdit("strip_difficulty", mission_select(m[0]),
                                        note="every soldier in %s" % m[4]))
        else:
            out.append(FileEdit("strip_difficulty", r"\.MIS$",
                                note="every soldier on every difficulty"))
        if v.get(prefix + "reveal_hidden"):
            out.append(FileEdit("reveal_hidden", r"\.MIS$",
                                note="spawn the script-held reinforcements"))
        tier = v.get(prefix + "tier", "stock")
        steps = {"up1": 1, "down1": -1, "elite": 2}.get(tier)
        if steps:
            out.append(FileEdit("bump_tier", r"\.MIS$", {"steps": steps},
                                "enemy tier %+d" % steps))
        skill = int(v.get(prefix + "skill", 0))
        if skill:
            out.append(FileEdit("bump_stats", r"\.ATR$", {"steps": skill},
                                "+%d to every hostile template" % skill,
                                scope="enemy_templates"))
        out += rseweapons.edits(prefix, v)
        out += rstuning.edits(prefix, v)
        return out
    return build


GHOST_RECON = GameProfile(
    id="ghost_recon_xbox",
    title="Tom Clancy's Ghost Recon",
    short="Ghost Recon",
    title_id="55530006",
    markers=[Marker("mission", "the campaign's mission files"),
             Marker("globs", "the packed copies the engine reads"),
             Marker("actor", "the squad and enemy templates")],
    settings=_settings("gr_", GR_MISSIONS, has_env=True),
    build_data=_build_data("gr_", GR_MISSIONS),
    mission_art_for=_mission_art_for("gr_", GR_MISSIONS),
    notes=notes_for("Ghost Recon", GR_MISSIONS, 48),
    ui_art={"backdrop": "shell/art/shell_bgd-01.rsb",
            # The 512 x 128 wordmark off the start screen, not the 64-pixel
            # dashboard disc: same logo, eight times the pixels.
            "emblem": "shell/art/STARTscreen.rsb"},
)

ISLAND_THUNDER = GameProfile(
    id="island_thunder_xbox",
    title="Tom Clancy's Ghost Recon: Island Thunder",
    short="Island Thunder",
    title_id="55530007",
    markers=[Marker("mission", "the campaign's mission files"),
             Marker("globs", "the packed copies the engine reads"),
             Marker("actor", "the squad and enemy templates")],
    settings=_settings("it_", IT_MISSIONS, has_env=True),
    build_data=_build_data("it_", IT_MISSIONS),
    mission_art_for=_mission_art_for("it_", IT_MISSIONS),
    notes=notes_for("Island Thunder", IT_MISSIONS, 61),
    ui_art={"backdrop": "shell/art/shell_bgd-01.rsb",
            # Island Thunder's start screen carries the plain Ghost Recon
            # wordmark, so its own subtitle comes off the main menu page --
            # the box art crop, top-left of a 1024 x 512 sheet.
            "emblem": "shell/art/main_menu-01.rsb",
            "emblem_box": (0.02, 0.03, 0.66, 0.26),
            # the wordmark sits on a mid-grey plate here, not on black
            "emblem_key": (105, 205)},
)

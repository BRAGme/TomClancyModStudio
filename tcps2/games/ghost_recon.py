"""Tom Clancy's Ghost Recon (PS2, SLUS-20613) -- profile.

Ghost Recon PS2 is Red Storm's own engine, not the Unreal build Rainbow Six 3
runs on, so nothing from that profile transfers. Two things make it tractable
anyway.

**Its enemies live in data, not code.** A mission's `<Units>` block is the order
of battle and one `<Actor>` is one soldier. Nothing in the executable caps the
number of them -- `Company::AddPlatoon` and `Platoon::AddFireTeam` grow their
arrays by one with no maximum test. The shipping game scales difficulty purely
with three suppression attributes on those actors, so the biggest lever in the
game is simply deleting them.

**The disc is an unstripped debug build.** `SLUS_206.13` is 37 MB because it
still carries a full Metrowerks symbol table -- 19,496 named functions with
sizes -- which is how the render-side addresses below were identified by name
rather than guessed at.

Honesty about the code patches: every stock word here was machine-checked
against the retail executable, so they will land where they are aimed. Their
*effect* has not been watched in a running game, and they are labelled
accordingly in the interface.
"""

from __future__ import annotations

from ..model import (BOOL, CHOICE, INT, Choice, FileEdit, GameProfile, Overlay,
                     Setting, WordEdit)
from . import rseweapons, rstuning

BASE = 0x00100000
FILE_DELTA = 0x80          # ELF PT_LOAD: VA 0x00100000 lives at file 0x80
FILE_SPAN = 0x004DED00 + FILE_DELTA
NOP = 0x00000000

ELF = Overlay(
    name="SLUS_206.13",
    iso_pattern=r"/SLUS_206\.13$",
    base_va=BASE,
    kind="raw",
    file_delta=FILE_DELTA,
    file_span=FILE_SPAN,
)

STOCK = {
    # bullet-hole pool and lifetime
    0x0046D9D0: 0x24050014,   # addiu a1, zero, 20   BulletHoleManagerPS2 size
    0x0046D9EC: 0x24020014,   # addiu v0, zero, 20   its clear-loop bound
    0x00249638: 0x3C0341F0,   # lui v1, 0x41f0       30.0f default lifetime
    0x00249740: 0x3C024000,   # lui v0, 0x4000       2.0f short-lived surfaces
    0x002496EC: 0x1000001B,   # b                    unknown surface -> no decal
    # split-screen effect gates
    0x0024EF38: 0x14E0006A,   # bne  CreateGeneralEffect, skips 424 bytes
    0x00252A8C: 0x14400033,   # bne  DrawEffects
    0x0024C8B8: 0x14400009,   # bne  AddGeneralEffects
    # weather density
    0x00257C80: 0x24050FA0,   # addiu a1, zero, 4000  IkeRainEffect drops
    0x002584FC: 0x240509C4,   # addiu a1, zero, 2500  IkeSnowEffect flakes
    0x00460420: 0x2405012C,   # addiu a1, zero, 300   RainEffectPS2
    0x004627D0: 0x24050064,   # addiu a1, zero, 100   SnowEffectPS2
    # camera
    0x003A80F4: 0x10400010,   # beq   CameraBeginScene first-person branch
    0x003A8B88: 0x28420003,   # slti  ToggleCameraView wrap
}

DECAL_LIFETIMES = {
    "stock": None,
    "30": 0x3C0341F0,     # 30.0f
    "120": 0x3C0342F0,    # 120.0f
    "1000": 0x3C03447A,   # 1000.0f -- holes last until the pool wraps
}
SHORT_LIFETIMES = {
    "stock": None,
    "30": 0x3C0241F0,
    "120": 0x3C0242F0,
    "1000": 0x3C02447A,
}

NOTES = (
    "Ghost Recon keeps its enemies in data, so the population options here "
    "rewrite the game's own mission files rather than patching code. The "
    "originals are copied beside the ISO first and “Restore disc” puts "
    "every one of them back at the byte it came from.\n\n"
    "Shipping enemy totals across all 28 missions with an order of battle: "
    "678 on Easy, 959 on Normal, 1,099 on Hard and Elite. That whole spread is "
    "the difficulty suppression flags, which is what the first option removes.\n\n"
    "The render options patch the boot executable. Their addresses were read "
    "out of the game's own symbol table and every stock word is checked before "
    "anything is written, but none of them has been watched working in a "
    "running game, so treat them as experiments and turn one on at a time."
)


def _settings():
    return [
        # ---- why there is no wave dial here -----------------------------
        Setting("gr_no_wave_dial", "Wave-count dial", BOOL, False,
                "Enemies", enabled=False, confidence="broken", touches="data",
                disabled_reason=(
                    "Ghost Recon has no Defend mode, and none of its eleven "
                    "game types carries an enemy count as a named script "
                    "variable -- their variable tables hold text ids and two "
                    "Siege timers, nothing else. Jungle Storm added Defend "
                    "along with Recruit/Veteran/Elite enemy counts, which is "
                    "why that game gets a wave page and this one does not."),
                help="Where Jungle Storm's wave numbers would be. Ghost Recon "
                     "does all of its enemy scaling through the placed order of "
                     "battle instead, which is what the options below edit."),

        # ---- enemies ----------------------------------------------------
        Setting("gr_all_difficulties", "Every soldier on every difficulty", BOOL,
                False, "Enemies", confidence="applied",
                help="The game removes soldiers on lower difficulties with "
                     "per-actor Easy/Normal/Hard flags. Deleting them puts the "
                     "full Hard-difficulty force into every mission at every "
                     "setting -- 678 enemies becomes 1,099 across the campaign.",
                caution="Rewrites 25 mission files inside GR.IMG.", touches="data"),
        Setting("gr_reveal_hidden", "Spawn the script-held reinforcements", BOOL,
                False, "Enemies", confidence="experimental",
                help="Some actors ship with Hidden=\"1\" and wait for a mission "
                     "script to bring them in. This puts them on the map from "
                     "the start.",
                caution="An actor a script expects to spawn later may behave "
                        "oddly when it is already there.", touches="data"),
        Setting("gr_tier", "Enemy skill tier", CHOICE, "stock", "Enemies",
                confidence="applied",
                choices=[
                    Choice("stock", "As shipped", ""),
                    Choice("up1", "One tier tougher",
                           "Recruits become veterans, veterans become elites."),
                    Choice("elite", "Everyone elite",
                           "Armour 3 and skills 3-5 across the board."),
                    Choice("down1", "One tier softer", ""),
                ],
                help="Ghost Recon names each enemy template by skill tier -- "
                     "m02_rec_ak47_2.atr -- and the three tiers really are "
                     "different numbers. This repoints every hostile actor at "
                     "the tier above or below without moving anybody.", touches="data"),
        Setting("gr_skill", "Extra enemy skill", INT, 0, "Enemies",
                minimum=0, maximum=4, unit="points", confidence="applied",
                help="Adds to armour, weapon skill, stamina, stealth and "
                     "leadership in every hostile template. Applies only to "
                     "templates used by non-allied companies -- your own squad "
                     "is untouched, and the two sets do not overlap anywhere in "
                     "the game.",
                caution="Two points already puts recruits above shipped elites.",
                touches="data"),

        # ---- bullet holes -----------------------------------------------
        Setting("gr_decal_pool", "Bullet holes kept on screen", INT, 20,
                "Bullet Holes", minimum=20, maximum=400, unit="holes",
                confidence="experimental",
                help="BulletHoleManagerPS2 ships a 20-entry ring. Raising it "
                     "sets both the array size and the matching clear-loop "
                     "bound, which have to move together or the extra entries "
                     "start with an uninitialised active flag.",
                caution="Each hole is 48 bytes of heap."),
        Setting("gr_decal_life", "How long bullet holes last", CHOICE, "stock",
                "Bullet Holes", confidence="experimental",
                choices=[
                    Choice("stock", "Stock (30 seconds)", ""),
                    Choice("120", "2 minutes", ""),
                    Choice("1000", "Until the pool wraps", ""),
                ]),
        Setting("gr_decal_short", "Also extend the short-lived surfaces", BOOL,
                False, "Bullet Holes", confidence="experimental",
                help="Three surface types get a 2-second hole instead of 30. "
                     "This gives them the same lifetime as everything else.",
                requires={"gr_decal_life": ("120", "1000")}),
        Setting("gr_decal_everywhere", "Bullet holes on every surface", BOOL,
                False, "Bullet Holes", confidence="experimental",
                help="DisplayBullethole bails out early on a surface type it "
                     "does not recognise and draws nothing. Removing that "
                     "early-out falls through to the default texture and size, "
                     "so every surface marks.",
                caution="Untested. It is the most invasive of the decal "
                        "options -- try it on its own."),

        # ---- split screen -----------------------------------------------
        Setting("gr_ss_effects", "Restore split-screen effects", BOOL, False,
                "Split Screen", confidence="experimental",
                help="The engine keeps two render paths and the split-screen "
                     "one leaves out bullet holes, foliage and birds. These "
                     "three branches are the creation-side gates, which are the "
                     "safe half: they let the effects be built without touching "
                     "how the two viewports are set up.",
                caution="The render-side gate was deliberately left out of this "
                        "tool. Forcing it also skips both viewport-setup calls "
                        "and would almost certainly cost you the second screen."),

        # ---- weather ----------------------------------------------------
        Setting("gr_weather", "Rain and snow density", CHOICE, "stock", "World",
                confidence="experimental",
                choices=[
                    Choice("stock", "As shipped", ""),
                    Choice("half", "Lighter", "Half the particles."),
                    Choice("double", "Heavier", "Twice the particles."),
                ],
                help="Four fixed-size particle arrays: 4,000 raindrops and "
                     "2,500 flakes in the general effect, 300 and 100 in the "
                     "PS2-specific one.",
                caution="These are real allocations, not pools that grow."),

        # ---- camera -----------------------------------------------------
        Setting("gr_first_person_body", "Show your soldier in first person",
                BOOL, False, "World", confidence="experimental",
                help="Ghost Recon has a first-person camera on the normal "
                     "camera cycle but no view model: entering it calls Hide() "
                     "on your own soldier and draws nothing in its place. This "
                     "skips the Hide, so you see your own body from eye height. "
                     "It is the closest this game has to a weapon model.",
                caution="There is no first-person arms or weapon mesh anywhere "
                        "in the game -- a search of all 38,722 symbols finds "
                        "only the two IsFirstPerson predicates. Expect to see "
                        "the third-person body, not a proper view model."),
        Setting("gr_extra_cameras", "Unlock the chase and ghost cameras", BOOL,
                False, "World", confidence="experimental",
                help="The camera cycle wraps at 3 of the 5 camera modes the "
                     "engine defines. This raises the wrap so chase and ghost "
                     "join the rotation."),
    ] + rstuning.cards("gr_")


def build_edits(v: dict) -> list:
    e = []

    def w(va, value, note):
        e.append(WordEdit(va, value, STOCK[va], note))

    pool = int(v.get("gr_decal_pool", 20))
    if pool != 20:
        w(0x0046D9D0, 0x24050000 | (pool & 0xFFFF), "bullet-hole pool = %d" % pool)
        w(0x0046D9EC, 0x24020000 | (pool & 0xFFFF), "bullet-hole clear loop = %d" % pool)

    life = v.get("gr_decal_life", "stock")
    if DECAL_LIFETIMES.get(life):
        w(0x00249638, DECAL_LIFETIMES[life], "bullet-hole lifetime")
        if v.get("gr_decal_short"):
            w(0x00249740, SHORT_LIFETIMES[life], "short-lived surfaces too")

    if v.get("gr_decal_everywhere"):
        w(0x002496EC, NOP, "draw a hole on unrecognised surfaces too")

    if v.get("gr_ss_effects"):
        w(0x0024EF38, NOP, "split screen: CreateGeneralEffect")
        w(0x00252A8C, NOP, "split screen: DrawEffects")
        w(0x0024C8B8, NOP, "split screen: AddGeneralEffects")

    weather = v.get("gr_weather", "stock")
    if weather in ("half", "double"):
        f = 2 if weather == "double" else 0.5
        for va, rt, stock_n in ((0x00257C80, 5, 4000), (0x002584FC, 5, 2500),
                                (0x00460420, 5, 300), (0x004627D0, 5, 100)):
            n = max(16, min(0x7FFF, int(stock_n * f)))
            w(va, 0x24000000 | (rt << 16) | n, "weather particles = %d" % n)

    if v.get("gr_first_person_body"):
        w(0x003A80F4, 0x10000010, "never hide your own soldier")
    if v.get("gr_extra_cameras"):
        w(0x003A8B88, 0x28420006, "camera cycle wraps at 6, not 3")

    return e



#: Every mission with an order of battle, in the order the disc plays it.
#:
#: `CAMPAIGN.XML` inside the archive lists the campaign in play order, and each
#: `.MIS` names itself in its own `<Shell>` and `<Engine>` blocks -- codename,
#: location, date and time. Here that order is also the file order, m01 through m15 and then the eight Desert Siege missions, and the dates climb with it.
#:
#: The last field is the briefing's tactical map, which the port renamed when it
#: cooked it: `m09_swamp.mis` asks for `M09_SWAMPS.RSB`. So the image name is
#: recorded rather than derived, and a test checks every one of them is really
#: in the archive.
#:
#: (stem, number, codename, place, date, time, soldiers, held back on Easy, map)
MISSIONS = (
    ("M01_CAVES", "M01", "Iron Dragon", "South Ossetian Autonomous Region", "April 16, 2008", "05:45", 63, 33, "M01_CAVES"),
    ("M02_FARM", "M02", "Eager Smoke", "South Ossetian Autonomous Region", "April 24, 2008", "02:15", 45, 23, "M02_FARM"),
    ("M03_RRBRIDGE", "M03", "Stone Bell", "South Ossetian Autonomous Region", "May 2, 2008", "10:00", 33, 17, "M03_RRBRIDGE"),
    ("M04_VILLAGE", "M04", "Black Needle", "Republic of Georgia", "May 7, 2008", "15:00", 48, 22, "M04_VILLAGE"),
    ("M05_EMBASSY", "M05", "Gold Mountain", "Tbilisi, Republic of Georgia", "May 14, 2008", "09:00", 64, 30, "M05_EMBASSY"),
    ("M06_CASTLE", "M06", "Witch Fire", "Izborsk, Russia", "June 6, 2008", "02:00", 52, 16, "M06_CASTLE"),
    ("M07_RIVER", "M07", "Paper Angel", "Lubana River, Latvia", "June 10, 2008", "06:00", 48, 18, "M07_RIVER"),
    ("M08_BATTLEFIELD", "M08", "Zebra Straw", "Venta, Lithuania", "June 24, 2008", "16:00", 56, 16, "M08_BATTLEFIELD"),
    ("M09_SWAMP", "M09", "Blue Storm", "Nereta Swamp, Latvia", "July 3, 2008", "09:00", 44, 22, "M09_SWAMPS"),
    ("M10_RUINED_CITY", "M10", "Fever Claw", "Vilnius, Lithuania", "September 1, 2008", "18:00", 47, 27, "M10_RUINEDCITY"),
    ("M11_POW_CAMP", "M11", "Dream Knife", "Ljady, Russia", "September 16, 2008", "03:00", 47, 19, "M11_POWCAMP"),
    ("M12_DOCKS", "M12", "Ivory Horn", "Murmansk, Russia", "September 22, 2008", "02:00", 64, 24, "M12_DOCKS"),
    ("M13_AIRBASE", "M13", "Arctic Sun", "Arkhangel'sk, Russia", "October 3, 2008", "04:00", 37, 9, "M13_AIRBASE"),
    ("M14_MOUNTAIN", "M14", "Willow Bow", "Toropec, Russia", "October 23, 2008", "13:00", 53, 11, "M14_MOUNTAIN"),
    ("M15_RED_SQUARE", "M15", "White Razor", "Moscow, Russia", "November 10, 2008", "11:00", 56, 23, "M15_REDSQUARE"),
    ("D01_BEACH", "D01", "Burning Sands", "Samhar Awraja, Eritrea", "May 16, 2009", "03:00", 42, 17, "D01_BEACH"),
    ("D02_REFINERY", "D02", "Flame Pillar", "Massawa, Eritrea", "May 23, 2009", "11:00", 48, 13, "D02_REFINERY"),
    ("D03_TRAINDEPOT", "D03", "Cold Steam", "Southern Denakil Awraja, Eritrea", "May 29, 2009", "15:30", 40, 14, "D03_DEPOT"),
    ("D04_RIVERBED", "D04", "Quiet Angel", "Tigray Kilil, Ethiopia", "June 4, 2009", "16:00", 44, 16, "D04_RIVERBED"),
    ("D05_AURORA", "D05", "Gamma Dawn", "Denakil Desert, Ethiopia", "June 11, 2009", "23:00", 44, 19, "D05_AURORA"),
    ("D06_GHOSTTOWN", "D06", "Spectre Wind", "Adi K'eyih, Eritrea", "June 16, 2009", "19:05", 39, 7, "D06_GHOSTTOWN"),
    ("D07_ROADBLOCK", "D07", "Subtle Keep", "Akale Guzay Awraja, Eritrea", "June 22, 2009", "18:00", 46, 17, "D07_ROADBLOCK"),
    ("D08_TANK", "D08", "Torn Banner", "Mereb Wenz crossing, near Adi Kwala, Eritrea", "June 25, 2009", "11:00", 46, 18, "D08_TANK"),
    ("TAC01_SHOOTING", "TAC01", "Shooting", "", "", "10:00", 15, 0, "TAC01_SHOOTING"),
    ("TAC02_RESCUE", "TAC02", "Rescue", "", "", "15:00", 23, 6, "TAC02_RESCUE"),
    ("TAC03_DEMOLITION", "TAC03", "Demolition", "", "", "09:00", 23, 0, "TAC03_DEMOLITION"),
    ("TAC04_ANTIVEHICLE", "TAC04", "Anti Vehicle", "", "", "02:15", 6, 0, "TAC04_ANTIVEHICLE"),
    ("TAC05_DEFEND", "TAC05", "Defend", "", "", "18:00", 31, 5, "TAC05_DEFEND"),
)

MISSION_GROUP = "Missions"


def mission_key(stem):
    return "mission_" + stem.lower()


def mission_art_for(key):
    """The briefing map this mission's card should show."""
    for mission in MISSIONS:
        if key == mission_key(mission[0]):
            return [mission[8]]
    return []


def mission_select(stem):
    """A regex matching just this mission's script inside the archive."""
    return r"/%s\.MIS$" % stem


def _mission_settings():
    """One switch per mission: put that mission's full force into every
    difficulty, without touching any other mission.

    This is the global "every soldier on every difficulty" switch aimed at one
    file. The figures on each card are counted out of the disc: how many actors
    the mission places, and how many of them carry a flag that removes them
    below Hard. A mission with no flags gets a card that says so and a switch
    that is off, because there is nothing there to release.
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
                         "any difficulty -- this mission already turns out in "
                         "full at every setting." % (when, actors))
        out.append(Setting(
            mission_key(stem), "%s  %s" % (number, title), BOOL, False,
            MISSION_GROUP, help=help_text, touches="data",
            enabled=bool(held),
            disabled_reason=("" if held else
                             "Nothing to release: this mission authors no "
                             "difficulty suppression flags at all, so every "
                             "soldier already turns out at every setting."),
            confidence="measured"))
    return out


def build_data(v: dict) -> list:
    out = []
    # Per-mission first, and skipped entirely when the global
    # switch is on: that one already strips every .MIS, so a
    # per-mission edit on top would be a second pass over a file
    # with nothing left in it to strip.
    if not v.get("gr_all_difficulties"):
        for mission in MISSIONS:
            if v.get(mission_key(mission[0])):
                out.append(FileEdit(
                    "strip_difficulty", mission_select(mission[0]),
                    "GR.IMG",
                    note="every soldier in %s %s"
                         % (mission[1], mission[2])))
    if v.get("gr_all_difficulties"):
        out.append(FileEdit("strip_difficulty", r"\.MIS$", "GR.IMG",
                            note="every soldier on every difficulty"))
    if v.get("gr_reveal_hidden"):
        out.append(FileEdit("reveal_hidden", r"\.MIS$", "GR.IMG",
                            note="spawn the script-held reinforcements"))
    tier = v.get("gr_tier", "stock")
    if tier == "up1":
        out.append(FileEdit("bump_tier", r"\.MIS$", "GR.IMG", {"steps": 1},
                            "enemies one tier tougher"))
    elif tier == "down1":
        out.append(FileEdit("bump_tier", r"\.MIS$", "GR.IMG", {"steps": -1},
                            "enemies one tier softer"))
    elif tier == "elite":
        out.append(FileEdit("bump_tier", r"\.MIS$", "GR.IMG", {"steps": 2},
                            "every enemy elite"))
    skill = int(v.get("gr_skill", 0))
    if skill:
        out.append(FileEdit("bump_stats", r"\.ATR$", "GR.IMG", {"steps": skill},
                            "+%d to every hostile template's skills" % skill,
                            scope="enemy_templates"))
    out += rseweapons.edits('gr_', v, 'GR.IMG')
    out += rstuning.edits("gr_", v, "GR.IMG")
    return out


PROFILE = GameProfile(
    id="ghost_recon_slus20613",
    title="Tom Clancy's Ghost Recon",
    short="Ghost Recon",
    serial="SLUS-20613",
    boot="SLUS_206.13",
    volume_hint="GHOST_RECON",
    pcsx2_crc="3E571E95",
    overlays=[ELF],
    settings=(_settings() + rseweapons.cards('gr_')
              + _mission_settings()),
    build_edits=build_edits,
    build_pnach=lambda v: [],
    build_data=build_data,
    archive_pattern=r"/(GR|MENU)\.IMG$",
    stock_words=STOCK,
    mission_art_for=mission_art_for,
    notes=NOTES,
    ui_art={"archive": "vokes", "patterns": [r"\.RSB$"]},
)

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

from ..model import (BOOL, CHOICE, INT, Choice, FileEdit, GameProfile, Overlay,
                     Setting, WordEdit)
from . import rseweapons, rstuning

BOOT = "SLES_511.80"
NOP = 0x00000000

ELF = Overlay(
    name=BOOT,
    iso_pattern=r"/SLES_511\.80$",
    base_va=0x00100000,
    kind="raw",
    file_delta=0x80,
    file_span=0x004A5780 + 0x80,
)

#: Code sites, every one recovered by signature-matching Ghost Recon's
#: unstripped build into this stripped one and then confirmed by reading the
#: word back out of `SLES_511.80` (see `research/soaf/code.md` §4).
#:
#: This is the same method Jungle Storm's addresses came from, and it works
#: better here: SOAF's bullet-hole and effects code is instruction-for-
#: instruction identical to Ghost Recon's apart from `jal` targets and `lui`
#: halves, where Jungle Storm's had drifted. `__ct__20BulletHoleManagerPS2Fv`
#: matches 23 of 23 words, `AddOneBulletHole` 87 of 87.
STOCK = {
    # bullet-hole ring: the array size and the two clear-loop bounds that have
    # to move with it (one in the constructor, one in Clear())
    0x004FD430: 0x24050014,   # addiu a1, zero, 20   BulletHoleManagerPS2 size
    0x004FD44C: 0x24020014,   # addiu v0, zero, 20   its constructor clear loop
    0x004FD498: 0x24030014,   # addiu v1, zero, 20   Clear() -- load / restart
    # IkeEffectsMgr::DisplayBullethole
    0x00240458: 0x3C0341F0,   # lui v1, 0x41f0       30.0f default lifetime
    0x00240560: 0x3C024000,   # lui v0, 0x4000       2.0f short-lived surfaces
    0x0024050C: 0x1000001B,   # b                    unknown surface -> no decal
    # BulletHolePS2::Render's vertex colour {0x40, 0x40, 0x40, 0x20} at
    # 0x00539D40, materialised only at 0x004FD8E8; the last word is the alpha
    0x00539D4C: 0x00000020,
    # weather particle counts: four fixed-size arrays, as in Ghost Recon
    0x0024E440: 0x24050FA0,   # addiu a1, zero, 4000  IkeRainEffect drops
    0x0024ED9C: 0x240509C4,   # addiu a1, zero, 2500  IkeSnowEffect flakes
    0x004EF710: 0x2405012C,   # addiu a1, zero, 300   RainEffectPS2
    0x004F17D0: 0x24050064,   # addiu a1, zero, 100   SnowEffectPS2
    # blood spray lifetime: BillboardEffectPS2::SetParameters, type-7 branch
    0x004EC0BC: 0x3C023F00,   # lui v0, 0x3f00 (0.5 s)
}

#: SuppressBehavior::ShouldIFrag, this game's copy at 0x001A64C0. The five
#: words are Ghost Recon's own grenade option, ported site for site; each one
#: is the same instruction with the same encoding at the same offset into the
#: function, and the single call site matches Ghost Recon's argument for
#: argument (a0 = this, a1 = the target, a2 = this+0x34).
GRENADES = (
    (0x001A65C0, 0x14400003, 0x10000003),   # thrower need not be outdoors
    (0x001A65F0, 0x14400004, 0x10000004),   # target need not be outdoors
    (0x001A6610, 0x3C024361, 0x3C0242C8),   # minimum 15 m -> 10 m (distance^2)
    (0x001A6674, 0x3C0244C8, 0x3C024561),   # maximum 40 m -> 60 m
    (0x001A66BC, 0x3C023F40, 0x3C023F80),   # 75% roll -> always
)
STOCK.update({va: s for va, s, _n in GRENADES})

#: Split screen was tried and withdrawn, 2026-09-28.
#:
#: The engine's machinery is real: `EffMgrPS2::Render` tests a flag at
#: `g_graphic_sys+0x18BC` and, when it is set, loops over exactly two
#: viewports, each with its own draw area. Nothing on this disc sets that flag,
#: so an option forced it on by rewriting the two initialisers that clear it.
#:
#: It worked, and that is the point: the game booted and the world really did
#: draw twice, top and bottom, with the two halves showing different views. But
#: it is not a feature and cannot be made into one from here -- the HUD is laid
#: out for one screen and straddles the boundary, there is no second player,
#: pad or soldier, and the game has no menu entry to reach it. The option was
#: removed rather than shipped as something that looks like split screen and is
#: not. `research/soaf/code.md` §5a keeps the addresses and the result.

#: 0x49740000 is 999,424 s (11.5 days), not the float maximum, for the reason
#: Ghost Recon's table records: a full ring reuses the hole with the least life
#: left, and at 3.39e38 every hole reads the same remaining life, so slot 0
#: took every new hole. At 1e6 the oldest goes first.
DECAL_LIFE = {"stock": None, "120": 0x3C0342F0, "1000": 0x3C03447A,
              "perm": 0x3C034974}
SHORT_LIFE = {"stock": None, "120": 0x3C0242F0, "1000": 0x3C02447A,
              "perm": 0x3C024974}
DECAL_ALPHA = {"stock": None, "50": 0x40, "75": 0x60, "100": 0x80}
BLOOD_SPRAY = {"2": 0x3C024000, "5": 0x3C0240A0}

NOTES = (
    "The Sum of All Fears reads correctly -- 2,751 files across SOAF.IMG and "
    "MENU.IMG, with every one of its 1,674 compressed files decoding to exactly "
    "the length it declares -- and the tool wears its artwork.\n\n"
    "Its missions use the same grammar as Ghost Recon's, so the enemy options "
    "here are the same edits, running on this game unmodified.\n\n"
    "It now has render patches. This executable is stripped, so searching it "
    "for its own tunables by name found only registration tables and no "
    "numbers worth writing -- but the bullet-hole and effects code is the "
    "same Red Storm source as Ghost Recon's, and Ghost Recon shipped its "
    "symbol table. Matching Ghost Recon's compiled functions against this "
    "disc recovered the addresses: 23 of 23 words for the bullet-hole "
    "manager's constructor, 87 of 87 for AddOneBulletHole -- a closer match "
    "than Jungle Storm gives. Every stock word below was then read back out "
    "of SLES_511.80 to confirm it, and is checked again before anything is "
    "written. All eight were applied to a disc and read back out of the "
    "patched image on 2026-09-28 -- through this game's MODE2/2352 sectors, "
    "which is the part that is unique to it -- so they land where they are "
    "aimed. None has been watched working in a running game.\n\n"
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
        Setting("soaf_enemy_grenades", "Enemies throw grenades more readily",
                BOOL, False, "Enemies", confidence="applied",
                help="An enemy throws only when both rooms are outdoors, the "
                     "target is 15-40 m away and a 75% roll passes. This "
                     "allows indoor throws at 10-60 m every time the other "
                     "checks pass; the check that keeps grenades off nearby "
                     "friendlies stays. This game kept Ghost Recon's "
                     "suppressive-fire grenade decision -- Jungle Storm is the "
                     "one that dropped it -- so this is Ghost Recon's own "
                     "option, site for site.",
                caution="Never played. Throws at the far end may fall short: "
                        "the throw speed is unchanged. The function that asks "
                        "the question is Ghost Recon's; the behaviour that "
                        "calls it had drifted too far to match, so how often "
                        "this game asks at all was not established."),

        # ---- bullet holes -----------------------------------------------
        Setting("soaf_decal_pool", "Bullet holes kept on screen", INT, 20,
                "Bullet Holes", minimum=20, maximum=400, unit="holes",
                confidence="applied",
                help="A 20-entry ring, the same one Ghost Recon has. Raising it "
                     "sets the array size and both clear-loop bounds that have "
                     "to move with it -- one in the constructor, one in the "
                     "clear a quick load or restart runs -- or the extra "
                     "entries start with an uninitialised active flag.",
                caution="Each hole is 48 bytes of heap, measured off this "
                        "disc's own array indexer, not assumed from Ghost "
                        "Recon."),
        Setting("soaf_decal_life", "How long bullet holes last", CHOICE,
                "stock", "Bullet Holes", confidence="applied",
                choices=[Choice("stock", "Stock (30 seconds)", ""),
                         Choice("120", "2 minutes", ""),
                         Choice("1000", "About 17 minutes", ""),
                         Choice("perm", "Permanent",
                                "Holes never expire; the oldest is reused only "
                                "when the 'kept on screen' cap is full.")],
                help="Holes do not fade -- they are drawn at full strength "
                     "until their lifetime runs out or the ring reuses their "
                     "slot. Pair 'Permanent' with a higher cap."),
        Setting("soaf_decal_short", "Also extend the short-lived surfaces",
                BOOL, False, "Bullet Holes", confidence="applied",
                requires={"soaf_decal_life": ("120", "1000", "perm")},
                help="Three surface types get a 2-second hole instead of 30. "
                     "This gives them the same lifetime as everything else."),
        Setting("soaf_decal_everywhere", "Bullet holes on every surface", BOOL,
                False, "Bullet Holes", confidence="applied",
                help="DisplayBullethole bails out early on a surface type it "
                     "does not recognise and draws nothing. Removing that "
                     "early-out falls through to the default texture and size, "
                     "so every surface marks.",
                caution="Untested, and the most invasive of the decal options "
                        "-- try it on its own."),
        Setting("soaf_decal_strength", "How dark bullet holes are", CHOICE,
                "stock", "Bullet Holes", confidence="applied",
                choices=[Choice("stock", "Stock (faint, 25%)", ""),
                         Choice("50", "50%", ""),
                         Choice("75", "75%", ""),
                         Choice("100", "Full strength", "")],
                help="Every hole is drawn with one fixed colour, RGB 0x40 and "
                     "alpha 0x20 -- a quarter of full opacity, which is why "
                     "they look faint. This raises that alpha. The colour sits "
                     "at 0x00539D40 and the hole renderer is the only thing "
                     "that reads it."),

        # ---- world ------------------------------------------------------
        Setting("soaf_weather", "Rain and snow density", CHOICE, "stock",
                "World", confidence="applied",
                choices=[Choice("stock", "As shipped", ""),
                         Choice("half", "Lighter", "Half the particles."),
                         Choice("double", "Heavier", "Twice the particles.")],
                help="Four fixed-size particle arrays, the same four Ghost "
                     "Recon has and at the same shipped counts: 4,000 "
                     "raindrops and 2,500 flakes in the general effect, 300 "
                     "and 100 in the PS2-specific one.",
                caution="These are real allocations, not pools that grow."),
        Setting("soaf_blood_spray", "Blood spray lasts", CHOICE, "stock",
                "World", confidence="applied",
                choices=[Choice("stock", "Half a second (as shipped)", ""),
                         Choice("2", "2 seconds", ""),
                         Choice("5", "5 seconds", "")],
                help="A bullet hit on a soldier throws a small blood spray "
                     "that lasts half a second, which is easy to miss. This "
                     "keeps it on screen longer. Unlike Jungle Storm, this "
                     "game does not hide its Blood setting, so the spray is "
                     "there as shipped once Blood is on in the game's own "
                     "options.",
                caution="The spray is drawn where the bullet hit and does not "
                        "follow the soldier, so a long one hangs in the air "
                        "after he moves -- 5 seconds looked wrong in play on "
                        "Ghost Recon. For spotting hits, not for normal play."),
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


#: The rest of each mission's briefing kit: an intel photograph and a
#: newspaper clipping, both 256x256 like the map itself.
#:
#: These have to be spelled out rather than derived, because the disc does NOT
#: name them consistently with the briefing. `M02`'s map is `M02_MILITIA` while
#: its intel is `M02_MILITIA_COMPOUND`; `M04` splits `WEAPONFAC` from
#: `WEAPONS_RESEARCH`; `M08` and `M11` keep an apostrophe the map drops; and
#: `M01` is spelled both `TV STATION` and `TVSTATION` on the same disc. Every
#: name below was read off the archive and decoded.
#:
#: `M01` is the one mission with no newspaper clipping, so its first objective
#: photograph takes the third slot instead.
EXTRA_ART = {
    "M01": ["M01_TVSTATION_INTEL_01", "M01_TV STATION_OBJ_0"],
    "M02": ["M02_MILITIA_COMPOUND_INTEL_01", "M02_MILITIA_COMPOUND_NEWS_01"],
    "M03": ["M03_WAREHOUSE_INTEL_01", "M03_WAREHOUSE_NEWS_01"],
    "M04": ["M04_WEAPONS_RESEARCH_INTEL_01", "M04_WEAPONS_RESEARCH_NEWS_01"],
    "M05": ["M05_PRISON_INTEL_01", "M05_PRISON_NEWS_01"],
    "M06": ["M06_MERCENARY_COMPOUND_INTEL_01", "M06_MERCENARY_COMPOUND_NEWS_01"],
    "M07": ["M07_DIAMOND_MINE_INTEL_01", "M07_DIAMOND_MINE_NEWS_01"],
    "M08": ["M08_OLSON'S_ESTATE_INTEL_01", "M08_OLSON'S_ESTATE_NEWS_01"],
    "M09": ["M09_BANK_INTEL_01", "M09_BANK_NEWS_01"],
    "M10": ["M10_CORPORATE_HQ_INTEL_01", "M10_CORPORATE_HQ_NEWS_01"],
    "M11": ["M11_DRESSLER'S_ESTATE_INTEL_01", "M11_DRESSLER'S_ESTATE_NEWS_01"],
}

#: `TRAINING_SHOTS` is deliberately not used. It decodes, but it is a five-frame
#: filmstrip 923x138, and beside a square map it would render as a smear.


def mission_art_for(key):
    """The mission's briefing kit: the map, then the intel and the clipping.

    The five training levels share one map and have no kit of their own, so
    they still get a single picture.
    """
    for mission in MISSIONS:
        if key == mission_key(mission[0]):
            return [mission[8]] + EXTRA_ART.get(mission[1], [])
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


def build_edits(v: dict) -> list:
    """The code patches, all of them in the boot ELF.

    Every write goes through `w`, which carries the stock word along so the
    engine refuses the site if the disc does not hold what this table says it
    holds -- which is what makes a signature-ported address safe to ship.
    """
    e = []

    def w(va, value, note):
        e.append(WordEdit(va, value, STOCK[va], note))

    pool = int(v.get("soaf_decal_pool", 20))
    if pool != 20:
        w(0x004FD430, 0x24050000 | (pool & 0xFFFF),
          "bullet-hole pool = %d" % pool)
        w(0x004FD44C, 0x24020000 | (pool & 0xFFFF),
          "bullet-hole clear loop = %d" % pool)
        w(0x004FD498, 0x24030000 | (pool & 0xFFFF),
          "bullet holes cleared on load / restart = %d" % pool)

    life = v.get("soaf_decal_life", "stock")
    if DECAL_LIFE.get(life):
        w(0x00240458, DECAL_LIFE[life], "bullet-hole lifetime")
        if v.get("soaf_decal_short"):
            w(0x00240560, SHORT_LIFE[life], "short-lived surfaces too")

    if v.get("soaf_decal_everywhere"):
        w(0x0024050C, NOP, "draw a hole on unrecognised surfaces too")

    alpha = DECAL_ALPHA.get(v.get("soaf_decal_strength", "stock"))
    if alpha:
        w(0x00539D4C, alpha, "bullet-hole alpha (0x80 = opaque)")

    weather = v.get("soaf_weather", "stock")
    if weather in ("half", "double"):
        f = 2 if weather == "double" else 0.5
        for va, stock_n in ((0x0024E440, 4000), (0x0024ED9C, 2500),
                            (0x004EF710, 300), (0x004F17D0, 100)):
            n = max(16, min(0x7FFF, int(stock_n * f)))
            w(va, 0x24050000 | n, "weather particles = %d" % n)

    spray = BLOOD_SPRAY.get(v.get("soaf_blood_spray", "stock"))
    if spray:
        w(0x004EC0BC, spray, "blood spray lasts longer")

    if v.get("soaf_enemy_grenades"):
        for va, _stock, new in GRENADES:
            w(va, new, "enemies throw grenades more readily")

    return e


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
    build_edits=build_edits,
    build_pnach=lambda v: [],
    build_data=build_data,
    archive_pattern=r"/(SOAF|MENU)\.IMG$",
    stock_words=STOCK,
    mission_art_for=mission_art_for,
    notes=NOTES,
    ui_art={"archive": "vokes", "patterns": [r"\.RSB$"]},
)

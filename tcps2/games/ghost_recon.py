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
    ]


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


def build_data(v: dict) -> list:
    out = []
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
    settings=_settings(),
    build_edits=build_edits,
    build_pnach=lambda v: [],
    build_data=build_data,
    archive_pattern=r"/(GR|MENU)\.IMG$",
    stock_words=STOCK,
    notes=NOTES,
    ui_art={"archive": "vokes", "patterns": [r"\.RSB$"]},
)

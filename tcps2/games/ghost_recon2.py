"""Ghost Recon 2 (PS2, SLUS-21105) -- profile.

The name says Ghost Recon, but the disc says Rainbow Six 3. This is not the Red
Storm engine the 2001 Ghost Recon and Jungle Storm run on: it is the same
Unreal-derived PS2 build Rainbow Six 3 and Advanced Warfighter use, and it shows
in every part of the layout -- `SP.SOZ` and `MP.SOZ` compressed overlays, vokes
archives, `.LIN` packages, and an `R6GAMESETTINGS.INI` whose keys and shipped
values are Rainbow Six 3's to the decimal place.

That is why this profile exists at all, and also why it is smaller than Rainbow
Six 3's. Everything here is **data**, not code:

  * `R6GAMESETTINGS.INI` ships three copies across the vokes archives and holds
    the AI tuning and the control curve in plain text. Same keys, same stock
    numbers, so Rainbow Six 3's transforms run on it unmodified.

  * `COMMON.LIN` holds the enemy templates, and the grenade picture in it was
    counted rather than assumed. Of the 73 `NbOfGrenade` tables: 43 always come
    up empty, **18 always spawn a frag grenade**, 8 roll one against nothing at
    20/15/25/30 percent, 2 always carry a molotov, 1 a smoke, and 1 rolls 10
    percent frag against 10 percent tear gas. So yes -- enemies throw grenades
    in this game, and 21 of the 73 templates are holding one every time.
    The 8 rolled tables are the ones with a number in them to change, and they
    use the same three-digit weighted form Rainbow Six 3 uses, so the same
    digit-for-digit edit works.

What is **not** here is the wave system, the render switches and the split-screen
fixes. Those are virtual addresses inside Rainbow Six 3's `SP.SOZ`, and this is
a different overlay from a different build a year later. Reusing them would
write into whatever happens to sit at those offsets. Ghost Recon 2's own overlay
has not been mapped, so the tool offers nothing that pretends to.
"""

from __future__ import annotations

from ..model import (BOOL, CHOICE, INT, Choice, FileEdit, GameProfile, Overlay,
                     Setting)

BOOT = "SLUS_211.05"

#: the boot ELF, for detection and for the CRC check. Two program headers; the
#: loaded one is at file +0x80 and maps to 0x01400000.
ELF = Overlay(
    name=BOOT,
    iso_pattern=r"/SLUS_211\.05$",
    base_va=0x01400000,
    kind="raw",
    file_delta=0x80,
    file_span=0x00024200 + 0x80,
)

STOCK = {}

#: read out of this disc's own R6GAMESETTINGS.INI, not assumed from Rainbow Six
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
FIRE_DELAYS = {
    "stock": ("1.0", "0.5"),
    "quick": ("0.5", "0.25"),
    "snap":  ("0.15", "0.1"),
}
SENS_BASE = {"x_mult": 0.70, "y_mult": 0.60, "x_step": 0.15, "y_step": 0.15}

NOTES = (
    "Ghost Recon 2 is a Rainbow Six 3 disc wearing a Ghost Recon badge. It has "
    "SP.SOZ and MP.SOZ overlays, vokes archives and .LIN packages -- the "
    "Rainbow Six 3 layout exactly, and nothing like the Red Storm engine the "
    "2001 Ghost Recon and Jungle Storm run on.\n\n"
    "Because of that, its R6GAMESETTINGS.INI is Rainbow Six 3's file: the same "
    "keys, shipping the same numbers, in three copies across the archives. Its "
    "COMMON.LIN carries 73 weapon-and-grenade tables in the same format. Both "
    "read and write correctly here, which is what the Enemies and Controls "
    "pages are built on.\n\n"
    "There are no code options. Rainbow Six 3's wave, render and split-screen "
    "patches are addresses inside ITS overlay; this is a different build and "
    "those offsets mean something else in it. This disc's overlay has not been "
    "mapped, so there is nothing honest to put on a Waves page yet.\n\n"
    "Everything on the two pages here is a plain-text edit to a file inside the "
    "archives, backed up before it is written and reversible from Restore disc."
)


def _settings():
    return [
        # ---- enemies -----------------------------------------------------
        Setting("gr2_grenade_carry", "How many enemies carry a grenade", INT,
                20, "Enemies", minimum=0, maximum=100, unit="%",
                confidence="applied", touches="data",
                help="What an enemy spawns holding is a weighted roll made "
                     "once, at spawn, over a small table in his template. "
                     "Eight of this disc's 73 tables roll a frag grenade "
                     "against nothing, at 20, 15, 25 and 30 percent. This sets "
                     "that share. A further 21 templates always carry "
                     "something -- 18 a frag, 2 a molotov, 1 smoke -- and are "
                     "not affected by this.",
                caution="There is no separate throw chance. Once he is holding "
                        "one, whether he uses it is decided by the two settings "
                        "below."),
        Setting("gr2_grenade_dist", "How close enemies will throw grenades",
                INT, 500, "Enemies", minimum=25, maximum=900, unit="units",
                confidence="applied", touches="data",
                help="The game will not let an enemy throw at anything nearer "
                     "than this. It ships at 500. Lower it and grenades turn up "
                     "in close quarters; raise it and they become a long-range "
                     "answer only."),
        Setting("gr2_grenade_delay", "How long they think about it first",
                CHOICE, "stock", "Enemies", confidence="applied",
                touches="data",
                choices=[
                    Choice("stock", "Stock (1.0s recruit, 0.5s veteran)", ""),
                    Choice("quick", "Quicker (0.5s / 0.25s)",
                           "Roughly twice as many grenades per fight."),
                    Choice("instant", "Barely any (0.1s / 0.05s)",
                           "They throw the moment they have a reason to."),
                ],
                help="The reaction delay before an enemy commits to a throw."),
        Setting("gr2_fire_delay", "How fast they open fire", CHOICE, "stock",
                "Enemies", confidence="applied", touches="data",
                choices=[
                    Choice("stock", "Stock (1.0s recruit, 0.5s veteran)", ""),
                    Choice("quick", "Quicker (0.5s / 0.25s)", ""),
                    Choice("snap", "Almost instant (0.15s / 0.1s)",
                           "They shoot as soon as they see you. Hard."),
                ],
                help="The pause between an enemy acquiring you and pulling the "
                     "trigger. This is the biggest single lever on how "
                     "dangerous a firefight feels."),
        Setting("gr2_skill", "Enemy skill", CHOICE, "stock", "Enemies",
                confidence="applied", touches="data",
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
        Setting("gr2_perfect_dist", "Range at which enemies never miss", INT,
                500, "Enemies", minimum=50, maximum=3000, unit="units",
                confidence="applied", touches="data",
                help="Inside this distance an enemy's shots have no dispersion "
                     "at all. It ships at 500."),
        Setting("gr2_sight", "How far enemies can see you", INT, 5000,
                "Enemies", minimum=500, maximum=15000, unit="units",
                confidence="applied", touches="data",
                help="The spotting radius every enemy searches inside. It ships "
                     "at 5000. Raising it makes open ground genuinely "
                     "dangerous; lowering it makes stealth much easier.",
                caution="This is the raw radius. The movement penalties still "
                        "apply on top of it, so the practical distance is "
                        "shorter when you are still and longer when you run."),

        # ---- your loadout ------------------------------------------------
        Setting("gr2_player_grenades", "Grenades you carry", INT, 1, "Loadout",
                minimum=1, maximum=10, unit="x", confidence="applied",
                touches="data",
                help="The AMMO MULTIPLIERS block scales what you start a "
                     "mission holding. Grenades ship at 1x on all three "
                     "difficulties -- the loadout you picked and nothing more. "
                     "Raising it multiplies every grenade in that loadout.",
                caution="This multiplies the loadout, so it does nothing for a "
                        "kit you sent out with no grenades in it."),

        # ---- controls ----------------------------------------------------
        Setting("gr2_sens_steps", "Look sensitivity ceiling", INT, 10,
                "Controls", minimum=10, maximum=30, unit="steps",
                confidence="applied", touches="data",
                help="The in-game sensitivity slider stops at 10. This raises "
                     "how far it goes, so there are faster settings to pick "
                     "than the game normally offers."),
        Setting("gr2_sens_boost", "Look speed at each step", INT, 100,
                "Controls", minimum=50, maximum=400, unit="%",
                confidence="applied", touches="data",
                help="Scales the sensitivity multiplier and the per-step "
                     "increment together, so every notch on the slider moves "
                     "the camera further. 100% is stock."),
    ]


def build_data(v: dict) -> list:
    """Ghost Recon 2 keeps its AI tuning and its control curve in plain text."""
    out = []
    ini = {}

    if int(v.get("gr2_grenade_dist", 500)) != 500:
        ini["m_fMinDistToThrowGrenade"] = int(v["gr2_grenade_dist"])
    delay = v.get("gr2_grenade_delay", "stock")
    if delay != "stock":
        rec, vet = GRENADE_DELAYS[delay]
        ini["m_fGrenadeReactionDelayRecruit"] = rec
        ini["m_fGrenadeReactionDelayVeteran"] = vet
    fire = v.get("gr2_fire_delay", "stock")
    if fire != "stock":
        rec, vet = FIRE_DELAYS[fire]
        ini["m_fReactionTimeForFiringRecruit"] = rec
        ini["m_fReactionTimeForFiringVeteran"] = vet
    skill = v.get("gr2_skill", "stock")
    if skill != "stock":
        rec, vet, eli = SKILL_SETS[skill]
        ini["m_fTerroristSkillMultiplierRecruit"] = rec
        ini["m_fTerroristSkillMultiplierVeteran"] = vet
        ini["m_fTerroristSkillMultiplierElite"] = eli
    if int(v.get("gr2_perfect_dist", 500)) != 500:
        ini["m_fDistForPerfectAccuracyTerro"] = "%.1f" % float(v["gr2_perfect_dist"])
    if int(v.get("gr2_sight", 5000)) != 5000:
        ini["m_fSightRadius"] = "%.1f" % float(v["gr2_sight"])
    mult = int(v.get("gr2_player_grenades", 1))
    if mult != 1:
        for tier in ("Recruit", "Veteran", "Elite"):
            ini["m_PlayerGrenadeMultiplier" + tier] = mult
    steps = int(v.get("gr2_sens_steps", 10))
    if steps != 10:
        ini["m_iXSensitivityMaxSteps"] = steps
        ini["m_iYSensitivityMaxSteps"] = steps
    boost = int(v.get("gr2_sens_boost", 100)) / 100.0
    if abs(boost - 1.0) > 0.001:
        ini["m_fXSensitivityMultiplier"] = "%.3f" % (SENS_BASE["x_mult"] * boost)
        ini["m_fYSensitivityMultiplier"] = "%.3f" % (SENS_BASE["y_mult"] * boost)
        ini["m_fXSensitivityStepIncrement"] = "%.3f" % (SENS_BASE["x_step"] * boost)
        ini["m_fYSensitivityStepIncrement"] = "%.3f" % (SENS_BASE["y_step"] * boost)

    if ini:
        out.append(FileEdit("ini_values", r"/R6GAMESETTINGS\.INI$", "",
                            {"values": ini}, "AI and control settings"))
    carry = int(v.get("gr2_grenade_carry", 20))
    if carry != 20:
        out.append(FileEdit("grenade_carry", r"/COMMON(OFF)?\.LIN$", "",
                            {"percent": carry},
                            "%d%% of two-entry templates carry a grenade" % carry))
    return out


PROFILE = GameProfile(
    id="gr2_slus21105",
    title="Tom Clancy's Ghost Recon 2",
    short="Ghost Recon 2",
    serial="SLUS-21105",
    boot=BOOT,
    volume_hint="GHOSTRECON2",
    pcsx2_crc="82E1D0EA",
    overlays=[ELF],
    settings=_settings(),
    build_edits=lambda v: [],
    build_pnach=lambda v: [],
    build_data=build_data,
    archive_pattern=r"/(VOKES\d|GR2)\.IMG$",
    stock_words=STOCK,
    notes=NOTES,
    ui_art={"archive": "iso", "fbz": [r"/DI/LE/LOADING/EN/.*\.FBZ$"]},
)

r"""Rainbow Six: Vegas (PC) -- Unreal Engine 3.

**Which ini wins is the only question that matters here**, because Vegas ships
three copies of nearly every config file and two of them are inert. The live
layer is `KellerGame\Config\PC\Keller<X>.ini`. Three independent things say so:

* the executable carries the literal path `..\KellerGame\Config\PC\` together
  with the format string `%sKeller%s.ini`;
* only files in that folder have modification times later than the install --
  the game writes there and nowhere else;
* `PC\KellerServerOptions.ini` holds this installation's own runtime state,
  including a server name the user typed, and six keys the copy at the Config
  root does not have at all.

So `PCKeller*.ini` at the Config root are snapshots, and the root `Default*.ini`
are stale templates. A tool that edited those would do nothing at all, very
convincingly.

**The decimal comma is real but it is in the dead file.** The root
`DefaultWeaponsConfig.ini` was exported by a build running under a European
locale and writes `m_fSuppressorDamageModifier=0,8`; the live
`PC\KellerWeaponsConfig.ini` has no commas anywhere, and different values
besides. `inifile` handles both spellings regardless, which costs nothing and
means the tool cannot be broken by whichever copy it is pointed at.

**Difficulty is not in ini at all.** It is in 22 cooked packages under
`Content\CookedPc\Packages\GameConfig\`, which is where player health, AI
vision timers and accuracy multipliers actually live. The ini layer scales
ammunition and rules, not competence -- so this profile does not pretend to
offer a difficulty slider it cannot deliver.
"""

from ..model import (BOOL, CHOICE, Choice, GameProfile, INPLACE, INT, IniEdit, IniLines, Layout, Setting)

LAYOUT = Layout(
    signature=[
        "KellerGame/Config/DefaultWeaponsConfig.ini",
        "KellerGame/Config/PC/KellerWeaponsConfig.ini",
        "KellerGame/Config/PC/KellerGame.ini",
    ],
    exe="Binaries/R6Vegas_Game.exe",
    config_dir="KellerGame/Config/PC",
    data_dir="KellerGame",
)

GAME = "KellerGame/Config/PC/KellerGame.ini"
GADGETS = "KellerGame/Config/PC/KellerGadgetsConfig.ini"
DAMAGE_TYPES = "KellerGame/Config/PC/KellerDamageTypesConfig.ini"

#: Three gadgets ship complete -- icon, rules, the lot -- and unselectable.
#: The other twelve in the same file are all `m_bSelectable=true`.
LOCKED_GADGETS = ("R6Game.R6GadgetGasMask", "R6Game.R6GasMaskSF10",
                  "R6Game.R6MedKit")

#: A shipped typo. The damage-type section for the Raging Bull is spelled
#: `PistoRagingBull`; the class in `R6Game.uppc` is `PistolRagingBull`, and
#: the misspelling appears in no package at all -- so that whole section is
#: read by nothing and the weapon has no damage-type configuration.
BULL_TYPO = "R6Game.R6DmgTypePistoRagingBull"
BULL_REAL = "R6Game.R6DmgTypePistolRagingBull"
SERVER = "KellerGame/Config/PC/KellerServerOptions.ini"
WEAPONS = "KellerGame/Config/PC/KellerWeaponsConfig.ini"
DAMAGE = "KellerGame/Config/PC/KellerDamageTypesConfig.ini"
#: The only copy there is -- this one has no `Keller` layer above it, so it is
#: edited where it sits at the Config root.
RAINBOW = "KellerGame/Config/DefaultRainbow.ini"

#: Every weapon section, so a proportional edit can name them all. The list is
#: written out rather than globbed because the file also contains an
#: `[Internal]` section that is not a weapon.
WEAPON_SECTIONS = [
    "R6Game.ConfigR6PistolMK23", "R6Game.ConfigR6PistolUSP40",
    "R6Game.ConfigR6Pistol92FS", "R6Game.ConfigR6PistolGlock18",
    "R6Game.ConfigR6PistolDesertEagle", "R6Game.ConfigR6PistolRagingBull",
    "R6Game.ConfigR6SubMP5N", "R6Game.ConfigR6SubMP7A1",
    "R6Game.ConfigR6SubUMP45", "R6Game.ConfigR6SubP90",
    "R6Game.ConfigR6SubMP9", "R6Game.ConfigR6SubMAC11",
    "R6Game.ConfigR6AssaultSCARHCQC", "R6Game.ConfigR6AssaultM8",
    "R6Game.ConfigR6AssaultAUGA3", "R6Game.ConfigR6AssaultG3KA4",
    "R6Game.ConfigR6Assault552Commando", "R6Game.ConfigR6AssaultG36C",
    "R6Game.ConfigR6AssaultMTAR21", "R6Game.ConfigR6AssaultFamas",
    "R6Game.ConfigR6AssaultAK47", "R6Game.ConfigR6LMGMK46",
    "R6Game.ConfigR6LMG21E", "R6Game.ConfigR6LMGM249SPW",
    "R6Game.ConfigR6LMGMG36", "R6Game.ConfigR6FixedLMGM249",
    "R6Game.ConfigR6ShotgunM3", "R6Game.ConfigR6ShotgunSpas12",
    "R6Game.ConfigR6Shotgun870MCS", "R6Game.ConfigR6ShotgunXM26LSS",
    "R6Game.ConfigR6SniperPSG1", "R6Game.ConfigR6SniperM40A1",
    "R6Game.ConfigR6SniperSV98", "R6Game.ConfigR6SniperScoutTactical",
]

#: The 35 damage-type sections all carry the same eight camera-shake keys.
SHAKE_SECTIONS_NOTE = ("every [R6Game...DmgType*] section in "
                       "KellerDamageTypesConfig.ini")

DAMAGE_KEYS = ("m_iDamageAt0M", "m_iDamageAt5M", "m_iDamageAt20M",
               "m_iDamageAt50M")

SETTINGS = [
    # -- Rules -----------------------------------------------------------
    Setting(
        "difficulty", "Default difficulty", CHOICE, "GAMEDIFFICULTY_VETERAN",
        group="Rules",
        help="What the campaign starts on. Worth knowing before you move it: "
             "the real differences between the tiers are NOT in any ini -- "
             "player health, AI reaction timers and accuracy multipliers live "
             "in cooked packages -- and Normal and Veteran carry the same "
             "player health. Elite is where the numbers actually change.",
        choices=[
            Choice("GAMEDIFFICULTY_NORMAL", "Normal", ""),
            Choice("GAMEDIFFICULTY_VETERAN", "Veteran", "The shipped default."),
            Choice("GAMEDIFFICULTY_ELITE", "Elite",
                   "Half the player health and half the accuracy."),
        ],
        confidence="experimental", touches="config"),
    Setting(
        "hostile_density", "Terrorist hunt population", CHOICE,
        "GAMEHOSTILEDENSITY_HIGH", group="Rules",
        help="How many hostiles a terrorist hunt spawns. This key exists in "
             "exactly one live file and nowhere else, which is why it is "
             "worth having a button for.",
        choices=[
            Choice("GAMEHOSTILEDENSITY_LOW", "Low", ""),
            Choice("GAMEHOSTILEDENSITY_MEDIUM", "Medium", ""),
            Choice("GAMEHOSTILEDENSITY_HIGH", "High", "The shipped default."),
        ],
        confidence="experimental", touches="config"),
    Setting(
        "civilian_limit", "Civilians you may kill before failing", INT, 3,
        group="Rules", minimum=0, maximum=20, unit=" civilians",
        confidence="experimental", touches="config"),
    Setting(
        "hunt_respawn", "Respawning in terrorist hunt", BOOL, True,
        group="Rules",
        help="Stock co-op terrorist hunt has unlimited lives and respawning "
             "on. Turning it off makes a hunt one life each.",
        confidence="experimental", touches="config"),
    Setting(
        "round_gap", "Seconds between rounds", INT, 10, group="Rules",
        minimum=0, maximum=60, unit=" seconds",
        confidence="experimental", touches="config"),
    Setting(
        "coop_leash", "Keep co-op players together", BOOL, False,
        group="Rules",
        help="A complete co-op tether -- a leader-assignment radius, a "
             "warning distance, a relocation distance and a delay -- that "
             "ships fully parameterised and switched OFF. The four numbers "
             "behind it are live and sensible: warn at 20 m, relocate at 30, "
             "after 5 seconds.",
        caution="Shipped off, so nobody has seen it run. If it does nothing, "
                "that is the most likely reason.",
        confidence="experimental", touches="config"),

    # -- Weapons ---------------------------------------------------------
    Setting(
        "weapon_damage", "Weapon damage", CHOICE, "stock", group="Weapons",
        help="Each weapon states its damage at four ranges -- point blank, "
             "5 m, 20 m and 50 m. Scaling all four keeps each weapon's own "
             "falloff curve and moves only how hard it hits. It applies to "
             "every weapon, so enemies hit harder too.",
        choices=[
            Choice("stock", "Stock", "A pistol is 35 at point blank, 15 at "
                                     "50 m."),
            Choice("x1.5", "Harder hitting", ""),
            Choice("x2", "Double", "Close to one-shot for a rifle."),
            Choice("x0.6", "Softer", ""),
        ],
        confidence="experimental", touches="config"),
    Setting(
        "accuracy", "Weapon accuracy", CHOICE, "stock", group="Weapons",
        help="The base bullet spread every weapon starts a burst from. LOWER "
             "is tighter, so this is inverted to read the way you expect.",
        choices=[
            Choice("stock", "Stock", ""),
            Choice("tight", "Tighter", "Initial spread halved."),
            Choice("loose", "Looser", "Doubled."),
        ],
        confidence="experimental", touches="config"),
    Setting(
        "movement_spread", "Spread from moving and turning", CHOICE, "stock",
        group="Weapons",
        help="Vegas adds spread for how fast you are moving and how fast you "
             "are turning, on top of the base cone. These are the numbers "
             "that make running-and-gunning ineffective.",
        choices=[
            Choice("stock", "Stock", ""),
            Choice("x0.5", "Halved", "Run and gun becomes viable."),
            Choice("none", "None", "Movement costs you no accuracy at all."),
            Choice("x1.5", "Heavier", ""),
        ],
        confidence="experimental", touches="config"),
    Setting(
        "suppressors", "How much a suppressor costs you", CHOICE, "stock",
        group="Weapons",
        help="A suppressor multiplies damage by 0.8 and recoil by 0.5, and "
             "cuts the radius at which the AI hears the shot from 5000 to "
             "200 -- a twenty-five-fold reduction, which is the real reason "
             "to fit one.",
        choices=[
            Choice("stock", "Stock", "Damage x0.8."),
            Choice("free", "No damage penalty", "Damage x1.0."),
            Choice("harsh", "Heavier penalty", "Damage x0.6."),
        ],
        confidence="experimental", touches="config"),

    # -- Feel ------------------------------------------------------------
    Setting(
        "aim_assist", "Aim assist", BOOL, False, group="Feel",
        help="Off on PC as shipped.",
        confidence="experimental", touches="config"),
    Setting(
        "fov", "Field of view", INT, 85, group="Feel",
        minimum=60, maximum=120, unit=" degrees",
        confidence="experimental", touches="config"),
    Setting(
        "camera_shake", "Camera shake when you are hit", BOOL, True,
        group="Feel",
        help="Eight shake keys are copy-pasted identically into all 35 "
             "damage-type sections. Turning this off zeroes the strength in "
             "every one of them.",
        confidence="experimental", touches="config"),
    Setting(
        "weapon_bob", "Weapon bob while walking", BOOL, True, group="Feel",
        confidence="experimental", touches="config"),
    Setting(
        "squad_spacing", "How close your squad follows", INT, 400,
        group="Feel", minimum=100, maximum=1500, unit=" units",
        help="Michael and Jung's whole formation behaviour is two numbers in "
             "a three-line file: an angle and this distance. 400 units is "
             "about four metres.",
        confidence="experimental", touches="config"),
    Setting(
        "game_speed", "Game speed", CHOICE, "stock", group="Feel",
        help="Global time dilation -- everything in the world runs at this "
             "rate, including you. Vegas ships it at 1.0 in the live config "
             "and never exposes it.",
        caution="Anything away from 1.0 changes animation and reload timing "
                "too, not just movement.",
        choices=[
            Choice("stock", "Normal", "1.0."),
            Choice("0.85", "Slower", "A more deliberate pace."),
            Choice("0.7", "Slow motion", ""),
            Choice("1.15", "Faster", ""),
        ],
        confidence="experimental", touches="config"),
    Setting(
        "interact_distance", "Reach for doors and objects", INT, 512,
        group="Feel", minimum=64, maximum=2048, unit=" units",
        help="How close you have to be before a door, ladder or objective "
             "can be used.",
        confidence="experimental", touches="config"),
    Setting(
        "bob_amount", "Weapon bob amount", CHOICE, "stock", group="Feel",
        help="How far the weapon swings as you walk. The existing weapon-bob "
             "option is on or off; this sets how much.",
        choices=[
            Choice("stock", "Stock", "0.006."),
            Choice("0.5", "Half", ""),
            Choice("2", "Double", ""),
        ],
        confidence="experimental", touches="config"),
    Setting(
        "voice_radius", "How far your voice carries", INT, 1500,
        group="Rules", minimum=100, maximum=10000, unit=" units",
        help="The radius other players hear you speak within.",
        confidence="experimental", touches="config"),
    Setting(
        "unlock_gadgets", "Offer the three locked gadgets", BOOL, False,
        group="Rules",
        help="The gas mask, the SF10 gas mask and the medic kit ship complete "
             "-- icon, rules, carry limits -- and marked unselectable, while "
             "the other twelve gadgets in the same file are selectable. This "
             "offers them in the loadout.",
        caution="Shipped finished but switched off, which usually means they "
                "were cut for a reason. Nothing here has been watched in a "
                "running game.",
        confidence="experimental", touches="config"),
    Setting(
        "gunfire_radius", "How far gunfire carries to the AI", CHOICE, "stock",
        group="Rules",
        help="The radius a shot alerts AI within. Thirty-four of the "
             "thirty-five weapons ship at 5000 and one at 1500, so this is "
             "effectively one number for the whole game and it is what "
             "decides whether a firefight in one room pulls the next one.",
        choices=[
            Choice("stock", "Stock", "5000."),
            Choice("x0.5", "Quieter", "Half."),
            Choice("x0.25", "Much quieter", "A quarter -- rooms fight alone."),
            Choice("x2", "Louder", ""),
        ],
        confidence="experimental", touches="config"),
    Setting(
        "fix_ragingbull", "Fix the Raging Bull's damage type", BOOL, False,
        group="Rules",
        help="Vegas spells that revolver's damage-type section "
             "PistoRagingBull; the class it is meant to configure is "
             "PistolRagingBull, and the misspelling appears in no game "
             "package at all. The section has therefore been read by nothing "
             "since release. This corrects the spelling.",
        confidence="experimental", touches="config"),
]


def build_edits(values):
    out = []
    v = values

    # -- rules ------------------------------------------------------------
    if v["difficulty"] != "GAMEDIFFICULTY_VETERAN":
        out.append(IniEdit(GAME, section="Engine.GameInfo",
                           key="GameDifficulty", value=v["difficulty"],
                           stock="GAMEDIFFICULTY_VETERAN",
                           note="default difficulty"))
    if v["hostile_density"] != "GAMEHOSTILEDENSITY_HIGH":
        out.append(IniEdit(SERVER, section="Engine.R6ServerOptions",
                           key="m_eHostileDensity", value=v["hostile_density"],
                           stock="GAMEHOSTILEDENSITY_HIGH",
                           note="terrorist hunt population"))
    if v["civilian_limit"] != 3:
        out.append(IniEdit(GAME, section="R6Game.R6ObjectiveKillCivilians",
                           key="m_iMaxCivilsKilledForGameOver",
                           value=v["civilian_limit"], stock="3",
                           note="civilian kill limit"))
    if not v["hunt_respawn"]:
        out.append(IniEdit(GAME, section="R6Game.R6CoopTerroristHuntGame",
                           key="m_bAllowRespawn", value="False", stock="True",
                           note="hunt respawning"))
        out.append(IniEdit(GAME, section="R6Game.R6CoopTerroristHuntGame",
                           key="MaxLives", value="1", stock="0",
                           note="hunt lives"))
    if v["round_gap"] != 10:
        out.append(IniEdit(GAME, section="R6Game.R6CoopTerroristHuntGame",
                           key="m_iTimeBetweenRound", value=v["round_gap"],
                           stock="10", note="seconds between rounds"))
    if v["coop_leash"]:
        out.append(IniEdit(GAME, section="R6Game.R6CooperativeGame",
                           key="m_bUseCoopLeashing", value="true",
                           stock="false", note="co-op leashing"))

    # -- weapons ----------------------------------------------------------
    dmg = {"x1.5": 1.5, "x2": 2.0, "x0.6": 0.6}.get(v["weapon_damage"])
    if dmg:
        for section in WEAPON_SECTIONS:
            for key in DAMAGE_KEYS:
                out.append(IniEdit(WEAPONS, section=section, key=key,
                                   scale=dmg, minimum=1, maximum=1000,
                                   absent="skip", note="weapon damage"))

    spread = {"tight": 0.5, "loose": 2.0}.get(v["accuracy"])
    if spread:
        for section in WEAPON_SECTIONS:
            out.append(IniEdit(WEAPONS, section=section,
                               key="m_iInitialBulletSpread", scale=spread,
                               minimum=0, absent="skip",
                               note="initial bullet spread"))

    move = {"x0.5": 0.5, "none": 0.0, "x1.5": 1.5}.get(v["movement_spread"])
    if move is not None:
        for section in WEAPON_SECTIONS:
            for key in ("m_iMovementBulletSpreadMinSpread",
                        "m_iMovementBulletSpreadMaxSpread",
                        "m_iRotationBulletSpreadMinSpread",
                        "m_iRotationBulletSpreadMaxSpread"):
                out.append(IniEdit(WEAPONS, section=section, key=key,
                                   scale=move, minimum=0, absent="skip",
                                   note="movement spread"))

    supp = {"free": "1.0", "harsh": "0.6"}.get(v["suppressors"])
    if supp:
        for section in WEAPON_SECTIONS:
            out.append(IniEdit(WEAPONS, section=section,
                               key="m_fSuppressorDamageModifier", value=supp,
                               absent="skip", note="suppressor damage"))

    # -- feel -------------------------------------------------------------
    if v["aim_assist"]:
        out.append(IniEdit(GAME, section="Engine.PlayerController",
                           key="bAimingHelp", value="true", stock="false",
                           note="aim assist"))
    if v["fov"] != 85:
        for key in ("DesiredFOV", "DefaultFOV"):
            out.append(IniEdit(GAME, section="Engine.PlayerController",
                               key=key, value="%.6f" % v["fov"],
                               note="field of view"))
    if not v["camera_shake"]:
        out.append(IniEdit(DAMAGE, section="*",
                           key="m_fCameraShakeStrength", value="0",
                           absent="skip", note="camera shake off"))
    if not v["weapon_bob"]:
        out.append(IniEdit(GAME, section="Engine.Pawn", key="bWeaponBob",
                           value="false", stock="true", note="weapon bob"))
    if v["squad_spacing"] != 400:
        out.append(IniEdit(RAINBOW, section="R6Game.R6RainbowManager",
                           key="m_fFormationDistance",
                           value=v["squad_spacing"], stock="400",
                           note="squad spacing"))
    # -- feel, from keys the live config ships and no menu exposes --------
    if v["game_speed"] != "stock":
        out.append(IniEdit(GAME, section="Engine.GameInfo", key="GameSpeed",
                           value=v["game_speed"], stock="1.000000",
                           note="game speed"))
    if v["interact_distance"] != 512:
        out.append(IniEdit(GAME, section="Engine.PlayerController",
                           key="InteractDistance",
                           value=v["interact_distance"], stock="512",
                           note="interaction reach"))
    if v["bob_amount"] != "stock":
        out.append(IniEdit(GAME, section="Engine.Pawn", key="Bob",
                           scale=float(v["bob_amount"]), stock="0.0060",
                           note="weapon bob amount"))
    if v["voice_radius"] != 1500:
        out.append(IniEdit(GAME, section="R6Game.R6VoiceChatManagerInterface",
                           key="m_fVoiceRadius", value=v["voice_radius"],
                           stock="1500", note="voice radius"))
    if v["unlock_gadgets"]:
        for section in LOCKED_GADGETS:
            out.append(IniEdit(GADGETS, section=section, key="m_bSelectable",
                               value="true", stock="false",
                               note="offer " + section.rsplit(".", 1)[-1]))
    radius = {"x0.5": 0.5, "x0.25": 0.25, "x2": 2.0}.get(v["gunfire_radius"])
    if radius:
        out.append(IniEdit(WEAPONS, section="*", key="m_fFireSoundRadius",
                           scale=radius, minimum=1, absent="skip",
                           note="gunfire alert radius"))
    if v["fix_ragingbull"]:
        out.append(IniLines(DAMAGE_TYPES, section=BULL_TYPO,
                            rename=BULL_REAL,
                            note="Raging Bull damage-type section name"))
    return out


def combination_warnings(values):
    out = []
    if values["weapon_damage"] == "x2" and values["accuracy"] == "tight":
        out.append("Doubled damage with halved spread applies to every weapon "
                   "in the game, and the enemies carry most of them.")
    if values["movement_spread"] == "none" and \
            values["difficulty"] == "GAMEDIFFICULTY_ELITE":
        out.append("Elite halves your accuracy in a cooked package this tool "
                   "does not edit, so removing movement spread here will not "
                   "fully offset it.")
    return out


NOTES = r"""
Vegas ships three copies of nearly every config file and only one set is live.
The live one is KellerGame\Config\PC\Keller<X>.ini. The PCKeller*.ini files at
the Config root are inert snapshots and the root Default*.ini are stale
templates -- editing either does nothing, very convincingly. Three separate
things agree on this: the executable's own path string, the fact that only the
PC\ folder has files with post-install modification times, and the fact that
PC\KellerServerOptions.ini contains this installation's own runtime state.

Two files break that pattern and are edited where they sit, because they have
no Keller layer above them at all: DefaultRainbow.ini, which is three lines and
holds your squad's entire formation behaviour, and the root Default*.ini for
anything the PC folder does not shadow.

The [Internal] CRC= line at the bottom of some of these files is not a tamper
check. It is a checksum of the corresponding Default<X>.ini -- a different file
-- so it fingerprints template staleness, not content. This tool leaves it
alone, which is the correct thing to do.

WHAT IS NOT HERE, AND WHY

A difficulty slider that means anything. The three difficulty tiers are not
implemented in ini. Player health, teammate health, player accuracy and the AI
vision-and-lock timers all live in 22 cooked UE3 packages under
Content\CookedPc\Packages\GameConfig\. Normal and Veteran even share the same
player health; the only tier that really differs is Elite. The ini layer scales
ammunition and rules, so the option above sets which tier you start on and does
not pretend to change what a tier means.

Restoring the cut terrorist-hunt maps. Seven map ids are missing from the
hunt list and their thumbnails are still on disk, matching story levels that DO
ship. Wiring them up is pure ini editing and is the best cut-content lead here.
It is not built yet. The other famous absence, the MP_Tower_01 map called RED
LOTUS, is complete in every respect except the level data and cannot be
restored at all.

Nothing in this profile has been watched working in a running game. Before
trusting any of it, the one thing worth doing is copying the Config tree aside,
changing one value, launching, quitting and diffing -- that settles whether the
game regenerates these files on exit, which is the single assumption everything
here rests on.
"""

PROFILE = GameProfile(
    id="vegas",
    title="Tom Clancy's Rainbow Six: Vegas",
    short="Vegas",
    layout=LAYOUT,
    delivery=INPLACE,
    settings=SETTINGS,
    build_edits=build_edits,
    combination_warnings=combination_warnings,
    notes=NOTES,
)

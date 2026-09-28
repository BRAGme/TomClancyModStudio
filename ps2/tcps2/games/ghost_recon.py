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

from .. import (grcallouts, grcamera, grcontrols, grextras, grhitblur, grshrapnel,
               grhu, grhuspot, grsight, grsplat, grsquad, grtotalwar, grtrigger)
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
    0x0046DA98: 0x24030014,   # addiu v1, zero, 20   BulletHoleManagerPS2::Clear (load)
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
# split-screen fireteams: the hook plus the whole cave region
STOCK.update(grsquad.GR_STOCK)
STOCK.update(grextras.GR_STOCK)
STOCK.update(grshrapnel.GR_STOCK)
STOCK.update(grcamera.GR_STOCK)
STOCK.update(grhitblur.GR_STOCK)
STOCK.update(grcontrols.GR_STOCK)
STOCK.update(grcallouts.GR_STOCK)
STOCK.update(grtotalwar.GR_STOCK)
STOCK.update(grsight.GR_STOCK)
STOCK.update(grtrigger.GR_STOCK)
STOCK.update(grsplat.GR_STOCK)
STOCK.update(grhuspot.GR_STOCK)
# blood: both blood handlers read BloodOn (IkeOptions+0xA3) themselves
STOCK[0x00247B24] = 0x926300A3  # lbu v1, 0xa3(s3)   HandleBloodPoolEffect
STOCK[0x00247D24] = 0x92A300A3  # lbu v1, 0xa3(s5)   HandleBloodyHumanEffect
# blood spray lifetime: the billboard setup's type-7 branch delay slot
STOCK[0x0045CBEC] = 0x3C023F00  # lui v0, 0x3f00 (0.5 s)
BLOOD_SPRAY = {"2": 0x3C024000, "5": 0x3C0240A0}
# dead bodies: IkeOptions::ShowDeadBodies returns the profile byte
STOCK[0x003CADA4] = 0x9082007C  # lbu v0, 0x7c(a0)
# frame rate: IkeUIMgr::CheckingLoadingLoop waits a second vblank in gameplay
STOCK.update({
    0x00271F14: 0x1040000E,     # beqz v0 (not in the action phase -> no second wait)
    0x00271F28: 0x3C010063,     # lui at, 0x63
    0x00271F2C: 0x8C220B40,     # lw  v0, 0xb40(at)   g_graphic_sys (already in v0)
})

DECAL_LIFETIMES = {
    "stock": None,
    "30": 0x3C0341F0,     # 30.0f
    "120": 0x3C0342F0,    # 120.0f
    "1000": 0x3C03447A,   # 1000.0f, about 17 minutes
    # 0x49740000 = 999,424 s, 11.5 days: never expires in play. Not 3.39e38:
    # a full ring recycles the slot with the least life left
    # (AddOneBulletHole), and at 3.39e38 every hole has the same float
    # remaining, so slot 0 was reused for every new hole. At 1e6 the float
    # step is 1/16 s, so the oldest hole goes first.
    "perm": 0x3C034974,
}
#: BulletHolePS2::Render's vertex colour is {0x40, 0x40, 0x40, 0x20} at
#: 0x0056FED0 (read only there); the last word is the alpha
DECAL_ALPHA = {"stock": None, "50": 0x40, "75": 0x60, "100": 0x80}
STOCK[0x0056FEDC] = 0x00000020
SHORT_LIFETIMES = {
    "stock": None,
    "30": 0x3C0241F0,
    "120": 0x3C0242F0,
    "1000": 0x3C02447A,
    "perm": 0x3C024974,
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

        Setting("gr_enemy_ammo", "Enemies can run out of magazines", BOOL,
                False, "Enemies", confidence="experimental",
                help="Every enemy fireteam is script-controlled, and the game "
                     "gives script-controlled soldiers infinite magazines -- "
                     "your own squad already spends theirs. This stops the "
                     "exemption, so enemies carry only what their kit says.",
                caution="Never played. What an enemy does once dry is "
                        "untested."),
        Setting("gr_enemy_grenades", "Enemies throw grenades more readily",
                BOOL, False, "Enemies", confidence="experimental",
                help="An enemy throws only when both rooms are outdoors, the "
                     "target is 15-40 m away and a 75% roll passes. This "
                     "allows indoor throws at 10-60 m every time the other "
                     "checks pass; the check that keeps grenades off nearby "
                     "friendlies stays. The Rainbow Six 3 'only beyond 15 m, "
                     "never indoors' problem again.",
                caution="Never played. Throws at the far end may fall short: "
                        "the throw speed is unchanged."),
        Setting("gr_enemy_sight_all", "Enemies see at full strength on "
                "every difficulty", BOOL, False, "Enemies",
                confidence="experimental",
                help="Recruit, Veteran and Elite enemies see 0.5, 0.56 and "
                     "0.61 of the level's spotting distance. This sets all "
                     "three to 1.0. Values the game hard-codes at boot, not "
                     "data files."),

        Setting("gr_enemy_sight_mult", "How far enemies can see (multiplier)",
                CHOICE, "1", "Enemies", confidence="experimental",
                choices=[
                    Choice("1", "Stock", ""),
                    Choice("1.25", "x1.25", ""),
                    Choice("1.5", "x1.5", ""),
                    Choice("2", "x2", "On Elite about 1.2x the level's own distance."),
                    Choice("3", "x3", ""),
                ],
                help="An enemy's sight has a hard cap: the level's spotting "
                     "distance times a difficulty factor (0.5 / 0.56 / 0.61 on "
                     "Recruit / Veteran / Elite) times your stance -- at most "
                     "76 m in stock. Scopes, alertness, light and movement only "
                     "matter inside it. This multiplies that difficulty factor "
                     "for hostile soldiers only; allied teams are untouched. "
                     "Unlike the level-file card it has no 99 limit, and it "
                     "stacks with it and with 'full strength'.",
                caution="Never played. Past about 80 m enemies can see you "
                        "before the game draws them -- raise 'How far away "
                        "soldiers are drawn' to match."),
        Setting("gr_sniper_sight", "Enemy snipers see farther", CHOICE, "1",
                "Enemies", confidence="experimental",
                choices=[
                    Choice("1", "Stock", ""),
                    Choice("1.5", "x1.5", ""),
                    Choice("2", "x2", ""),
                    Choice("3", "x3", ""),
                    Choice("4", "x4", ""),
                ],
                help="Nothing in the AI treats snipers specially except the "
                     "gun: a scope only sharpens their eyes inside the same "
                     "cap as everyone else. This multiplies the sight cap "
                     "again for hostiles whose current gun is a sniper rifle "
                     "(SVD, PSG1, M82, M98, M24, L96A1, SR25), on top of the "
                     "option above. Engagement itself has no range limit, and "
                     "bullets fly about 500 m.",
                caution="Never played. Draw distance matters even more here; "
                        "foliage still blocks sight (each layer cuts 40%)."),
        Setting("gr_sniper_precision", "Enemy snipers lose the built-in miss",
                BOOL, False, "Enemies", confidence="experimental",
                help="Every enemy's aim point carries a deliberate 0.10-0.25 m "
                     "miss on top of his skill-based error (+-0.10 m), scaled "
                     "up to full at 50 m. This drops the deliberate miss for "
                     "hostile snipers only.",
                caution="Never played. Their aim error and weapon spread "
                        "remain."),
        Setting("gr_soldier_draw", "How far away soldiers are drawn", CHOICE,
                "80", "Enemies", confidence="experimental",
                choices=[
                    Choice("80", "80 m (as shipped)", ""),
                    Choice("120", "120 m", ""),
                    Choice("160", "160 m", ""),
                    Choice("240", "240 m", ""),
                ],
                help="The game stops drawing soldiers beyond 80 m (more when "
                     "you look through a scope), per split-screen view. With "
                     "longer enemy sight -- including 'full strength' on the "
                     "open maps -- you can be shot by someone who is not drawn. "
                     "Set this at least as far as the enemies can see.",
                caution="Never played. Costs frame rate with many soldiers in "
                        "view; the map's own fog still hides far soldiers."),

        # ---- bullet holes -----------------------------------------------
        Setting("gr_decal_pool", "Bullet holes kept on screen", INT, 20,
                "Bullet Holes", minimum=20, maximum=400, unit="holes",
                confidence="experimental",
                help="BulletHoleManagerPS2 ships a 20-entry ring. Raising it "
                     "sets both the array size and the matching clear-loop "
                     "bound, which have to move together or the extra entries "
                     "start with an uninitialised active flag, and the bound of "
                     "the clear a loaded game runs (missing before 2026-09-28, "
                     "so holes past the 20th outlived a quick load).",
                caution="Each hole is 48 bytes of heap."),
        Setting("gr_decal_life", "How long bullet holes last", CHOICE, "stock",
                "Bullet Holes", confidence="experimental",
                choices=[
                    Choice("stock", "Stock (30 seconds)", ""),
                    Choice("120", "2 minutes", ""),
                    Choice("1000", "About 17 minutes", ""),
                    Choice("perm", "Permanent",
                           "Holes never expire; the oldest is reused only when "
                           "the 'kept on screen' cap is full."),
                ],
                help="Holes do not fade -- they are drawn at full strength "
                     "until their lifetime runs out or the ring reuses their "
                     "slot. Pair 'Permanent' with a higher cap."),
        Setting("gr_decal_short", "Also extend the short-lived surfaces", BOOL,
                False, "Bullet Holes", confidence="experimental",
                help="Three surface types get a 2-second hole instead of 30. "
                     "This gives them the same lifetime as everything else.",
                requires={"gr_decal_life": ("120", "1000", "perm")}),
        Setting("gr_decal_everywhere", "Bullet holes on every surface", BOOL,
                False, "Bullet Holes", confidence="experimental",
                help="DisplayBullethole bails out early on a surface type it "
                     "does not recognise and draws nothing. Removing that "
                     "early-out falls through to the default texture and size, "
                     "so every surface marks.",
                caution="Untested. It is the most invasive of the decal "
                        "options -- try it on its own."),
        Setting("gr_decal_strength", "How dark bullet holes are", CHOICE,
                "stock", "Bullet Holes", confidence="experimental",
                choices=[
                    Choice("stock", "Stock (faint, 25%)", ""),
                    Choice("50", "50%", ""),
                    Choice("75", "75%", ""),
                    Choice("100", "Full strength", ""),
                ],
                help="Every hole is drawn with one fixed colour, RGB 0x40 and "
                     "alpha 0x20 -- a quarter of full opacity, which is why "
                     "they look faint. This raises that alpha. The colour "
                     "is read only by the hole renderer."),
        Setting("gr_shrapnel", "Shrapnel marks from explosions", INT, 0,
                "Bullet Holes", minimum=0, maximum=grshrapnel.MAX_N,
                unit="marks", confidence="experimental",
                help="Explosions leave no mark at all. This traces the given "
                     "number of fragment rays from every grenade, 40 mm, rocket "
                     "and placed charge. Half go out in every direction as far "
                     "as the blast radius (up to 16 m), marking walls, beams "
                     "and anything overhead; the other half aim at points "
                     "spread over a circle of that radius on the ground under "
                     "the blast, so even a grenade that bursts in the air "
                     "scatters marks across the ground. Each hit gets the "
                     "surface's own hole and the impact a bullet makes there "
                     "-- a dust puff (with sparks on hard surfaces) or a "
                     "splash -- and may play the bullet's impact sound. 0 is "
                     "off; 12 is a good start. Smoke and flashbangs mark "
                     "nothing, and the same blast always leaves the same "
                     "pattern.",
                caution="Never played. The marks share the bullet-hole ring, so "
                        "raise 'Bullet holes kept on screen' to at least three "
                        "times this number or one blast will recycle your "
                        "bullet holes. Split screen draws them only with "
                        "'Bullet holes in split screen' on. Every ray is one "
                        "line test on the frame the blast goes off."),

        # ---- split screen -----------------------------------------------
        Setting("gr_shrapnel_size", "Shrapnel mark size", CHOICE, "1",
                "Bullet Holes", confidence="experimental",
                choices=[
                    Choice("1", "Same as a bullet hole", ""),
                    Choice("1.5", "1.5x", ""),
                    Choice("2", "2x", ""),
                    Choice("3", "3x", ""),
                ],
                help="A bullet hole's size depends on the surface: about 40 cm "
                     "scuffs on dirt-like ground, 7-8 cm holes on concrete, "
                     "rock and metal. This scales the shrapnel marks only; "
                     "bullets keep their size."),
        Setting("gr_ss_effects", "Restore split-screen effects", BOOL, False,
                "Split Screen", confidence="experimental",
                help="The engine keeps two render paths and the split-screen "
                     "one leaves out bullet holes, foliage and birds. These "
                     "two branches are creation-side gates that only suppress "
                     "effects in split screen. (A third word this option used "
                     "to include, in DrawEffects, turned out to choose the "
                     "per-player path -- nopping it left player 2's weather "
                     "and night vision stale -- and has been removed. Bullet "
                     "holes have their own split-screen option.)",
                caution="The render-side gate was deliberately left out of this "
                        "tool. Forcing it also skips both viewport-setup calls "
                        "and would almost certainly cost you the second screen."),
        Setting("gr_ss_fireteams", "AI fireteams for both players", BOOL,
                False, "Split Screen", confidence="experimental",
                help="Split screen gives each player one nameless soldier. "
                     "This adds two named Ghosts to each player's fireteam -- "
                     "Vernon Jefferson and Jon Snyder with player 1, Horace "
                     "Dominguez and Robbie Chukitus with player 2, mission "
                     "one's own squad -- created as AI, the way single player "
                     "creates your squadmates. The co-op roster writer runs "
                     "its soldier loop twice; one jump after it adds the four "
                     "entries before the teams are sealed.",
                caution="Never played. Each soldier is a rifleman or support "
                        "Ghost from the campaign roster with a standard kit; "
                        "player 2's soldiers only appear when player 2 is in "
                        "the game. Dying still respawns you -- taking over a "
                        "teammate is a separate change."),
        Setting("gr_fps", "Frame rate", CHOICE, "stock", "World",
                confidence="verified",
                choices=[
                    Choice("stock", "30 (as shipped)", ""),
                    Choice("60", "60",
                           "Gameplay stops waiting for a second vblank."),
                    Choice("60sp", "60 in single player, 30 in split screen",
                           "Split screen keeps the steady 30 instead of "
                           "alternating when a frame runs long."),
                ],
                help="Gameplay is capped at 30 by one extra vblank wait per "
                     "frame; menus already run at 60. Game logic is timed by "
                     "the measured clock, not by frames, so lifting the cap "
                     "does not speed the game up. This is the same word as "
                     "the long-standing 60 FPS cheat, baked into the disc so "
                     "it survives the CRC change every other patch causes.",
                caution="Ghost Recon renders serially and may not hold 60 on "
                        "a real PS2 or without the emulator's EE overclock. "
                        "Load from a cold boot: a savestate brings back "
                        "whatever code was in memory when it was taken."),
        Setting("gr_callouts", "Everyone calls out", BOOL, False, "World",
                confidence="experimental",
                help="Players' soldiers speak the team call-outs too. A player "
                     "is always his fireteam's leader, and the leader voices "
                     "the team's lines -- but split screen drops most of them "
                     "(a radio line plays only if it is tagged with player "
                     "1's soldier, and the tag ends every frame as player 2), "
                     "'under fire' is skipped for any fireteam with a player "
                     "in it, and a soldier left alone goes quiet. This lets "
                     "all of them through, and makes 'tango down' the "
                     "killer's own line, in his voice, with the game's own "
                     "2-second team cooldown.",
                caution="Never played. In split screen both players hear both "
                        "fireteams' radio lines. There is no reloading line "
                        "in the game to add."),
        Setting("gr_callouts_contact", "Players call 'contact'", BOOL, False,
                "World", confidence="experimental",
                requires={"gr_callouts": True},
                help="A player who spots a new enemy says 'contact' himself, "
                     "at most every 15 seconds per fireteam (the timer the "
                     "game uses for 'grenade!'). Enemy teams, AI teammates "
                     "and faint sightings are left as they are.",
                caution="Never played."),
        Setting("gr_callouts_respawn", "'Rock and roll' on a takeover", BOOL,
                False, "Split Screen", confidence="experimental",
                requires={"gr_ss_handoff": True},
                help="In split screen, taking over a soldier -- the one-life "
                     "handoff or SELECT switching -- plays 'rock and roll' "
                     "after single player's takeover blip. The line is on "
                     "every mission's sound bank and nothing in the game "
                     "plays it.",
                caution="Never played. Recorded in one voice only, so it may "
                        "not match the soldier you take over. Single player "
                        "keeps only the blip."),
        Setting("gr_blood", "Blood always on", BOOL, False, "World",
                confidence="experimental",
                help="Ghost Recon draws a spray when a soldier is hit and a "
                     "pool under a body, gated only by the Blood option: it "
                     "is on unless the game runs in German (which also hides "
                     "the option) or a saved profile turned it off. Split "
                     "screen already sends, creates and draws both in each "
                     "half -- nothing there checks for split screen. This "
                     "makes both blood handlers ignore the option. Pools also "
                     "need bodies ('Always keep dead bodies').",
                caution="Never played. Only needed if blood is missing; on "
                        "an English console with Blood on it changes "
                        "nothing."),
        Setting("gr_blood_splatter", "Blood splatter on walls and ground", BOOL, False,
                "World", confidence="experimental", requires={"gr_blood": True},
                help="The only blood a hit leaves is the spray, and a body "
                     "later leaves its pool. This follows each bullet on from "
                     "the wound, tilted a little down, for about 3 m with the "
                     "game's own line test: a wall, floor or anything else it "
                     "meets takes a splatter (0.5 m); if it meets nothing, the "
                     "ground under the wound takes a smaller one (0.4 m). The "
                     "splatter is the blood pool's own picture and colour -- "
                     "dark red, half see-through -- kept as a bullet hole: it "
                     "shares their ring and lasts as long as 'How long bullet "
                     "holes last' says, and split screen draws it too.",
                caution="Never played. Splatters take bullet-hole slots, so a "
                        "long fight replaces the oldest holes and splatters "
                        "sooner; a bigger bullet-hole pool helps."),
        Setting("gr_blood_spray", "Blood spray lasts", CHOICE, "stock", "World",
                confidence="experimental",
                choices=[
                    Choice("stock", "Half a second (as shipped)", ""),
                    Choice("2", "2 seconds", ""),
                    Choice("5", "5 seconds", ""),
                ],
                help="A bullet hit on any soldier -- enemy, AI teammate or "
                     "player; nothing in the code checks sides -- throws a "
                     "small blood spray that lasts half a second, which is easy "
                     "to miss, especially on your own soldier or a teammate. "
                     "This keeps it on screen longer. Only bullet hits spray; "
                     "grenade and scripted deaths do not, for anyone.",
                caution="The spray is drawn where the bullet hit and does not "
                        "follow the soldier, so a long one hangs in the air "
                        "after he moves -- 5 seconds looked wrong in play "
                        "(2026-09-27). For spotting hits, not for normal play."),
        Setting("gr_keep_bodies", "Always keep dead bodies", BOOL, False,
                "World", confidence="experimental",
                help="Bodies flash for about a second and vanish when the "
                     "game's Dead Body option is off -- it is forced off on "
                     "one language build and can be off in a saved profile. "
                     "This makes the game read the option as on everywhere, "
                     "single player and split screen. The menu still shows "
                     "and toggles its own copy, which no longer matters.",
                caution="Never played. Only the two readers of the option "
                        "change. Respawn modes still clear a respawned "
                        "soldier's old body after 15 seconds; that is a "
                        "separate timer, and keeping it stops bodies piling "
                        "up without limit."),
        Setting("gr_ss_stealth", "Crouch and prone hide you in split screen",
                BOOL, False, "Split Screen", confidence="experimental",
                help="An enemy's sight range shrinks to 3/4 when you crouch and "
                     "1/2 prone -- in single player. The check reads player "
                     "1's stance, so split screen skips it and stance buys "
                     "neither player anything. This uses the stance of the "
                     "soldier actually being looked at, in both modes.",
                caution="Never played. In single player an enemy looking at "
                        "one of your AI teammates now weighs that teammate's "
                        "stance instead of yours."),
        Setting("gr_ss_rain", "Rain in split screen", BOOL, False,
                "Split Screen", confidence="experimental",
                help="Split screen refuses to create rain and mutes the rain "
                     "sound, though a second rain slot and its per-player "
                     "draw are already in the engine (snow gets its second "
                     "instance). This creates rain for both halves, keeps the "
                     "rain sound, and gives each half the full 1,000 "
                     "snowflakes instead of 500.",
                caution="Never played. Two rain systems of 300 drops each."),
        Setting("gr_ss_briefing", "Mission briefing in split screen", BOOL,
                False, "Split Screen", confidence="experimental",
                help="Split screen's Mission mode goes straight from the menu "
                     "to choosing your soldier. This puts single player's "
                     "briefing screen -- mission text, objectives, map -- in "
                     "between. Split screen already loads the mission and its "
                     "objectives the same way single player does before that "
                     "point, so the briefing has everything it reads. Accept "
                     "continues to the soldier screen; Back returns to the "
                     "split-screen menu. Other split-screen game types are "
                     "unchanged.",
                caution="Never played. Only player 1's pad is expected to "
                        "drive the briefing, as with the split-screen menu. "
                        "The main menu now clears the split-screen flag, which "
                        "stock Ghost Recon left set after Split Screen -> "
                        "Back."),
        Setting("gr_ss_teammates", "Single player's roster: P1 leads Alpha, "
                "P2 leads Bravo", BOOL, False, "Split Screen",
                confidence="experimental",
                requires={"gr_ss_briefing": True},
                help="Split-screen Mission plays like single player: after the "
                     "briefing comes single player's platoon screen, where you "
                     "pick up to six Ghosts and their kits, and GO launches "
                     "the mission -- no split-screen soldier screen. Player 1 "
                     "is Alpha's first Ghost, player 2 is Bravo's first, and "
                     "everyone else is AI in his own fireteam, with his real "
                     "name. Single player's own roster writer builds the "
                     "team. The PS2 platoon screen has only Alpha and Bravo; "
                     "if you leave one empty, it borrows the other team's "
                     "last Ghost. Other split-screen modes keep the soldier "
                     "screen (and the fixed fireteams, if that option is on).",
                caution="Never played. Pick at least two Ghosts: with one, GO "
                        "does nothing. Only player 1's pad drives the menus. "
                        "The HUD still labels the players 1P and 2P."),
        Setting("gr_ss_hitblur", "Hit blur in split screen", BOOL, False,
                "Split Screen", confidence="experimental",
                help="Getting hit in single player blurs the screen for five "
                     "seconds, with a few dark blotches. Split screen starts "
                     "the same effect but its per-player draw loop never draws "
                     "it, and there is only one blur for both players. This "
                     "gives each player their own blur, drawn on their own "
                     "half only, at single player's strength.",
                caution="Never played. Each blurred half costs about half of "
                        "single player's blur while it lasts. About half of the "
                        "blotches show, since they are placed over the whole "
                        "screen and clipped to your half."),
        Setting("gr_ss_bulletholes", "Bullet holes in split screen", BOOL,
                False, "Split Screen", confidence="experimental",
                help="Split screen creates bullet holes and never draws them: "
                     "the effect renderer's per-viewport loop calls the water "
                     "ripples but not the bullet holes, which only the "
                     "full-screen block draws. This makes the loop call both, "
                     "after each viewport's own draw area is set, so each "
                     "player sees the holes from their own camera.",
                caution="Never played. The render gate and the viewport setup "
                        "are untouched."),
        Setting("gr_ss_orders", "Team orders and soldier switching", BOOL,
                False, "Split Screen", confidence="experimental",
                requires={"gr_ss_handoff": True},
                help="Each player commands and switches within their own "
                     "fireteam. d-pad LEFT: switch to the next living Ghost "
                     "in your fireteam. R3: tap for Hold / Advance; hold it "
                     "half a second and let go to send your teammates to the "
                     "spot under your crosshair, where they hold. "
                     "Player 1 d-pad RIGHT, player 2 SELECT: cycle Recon / "
                     "Assault / Suppress. With Jungle Storm's controls: "
                     "SELECT switches, R2 is Hold / Advance and move to, and "
                     "L2 cycles the ROE, for both players. Player 2's buttons only ever reach "
                     "player 2's soldiers -- the game attaches player 2's "
                     "avatar only to pad 2's input. Switching uses the same "
                     "path as the death handoff.",
                caution="Never played. No order HUD in split screen: the "
                        "fireteam's voice and hand signals are the "
                        "confirmation. Single player's command map and quick "
                        "orders are unchanged."),
        Setting("gr_ss_handoff", "One life: take over a teammate on death",
                BOOL, False, "Split Screen", confidence="experimental",
                requires={"gr_ss_fireteams": True},
                help="Single player's rule in split screen: no respawns, and "
                     "when your soldier dies you carry on as a living Ghost "
                     "from your own fireteam. Split screen already runs single "
                     "player's handoff code on death and bails one branch "
                     "early; this lets it finish, keeps the search inside the "
                     "dead player's fireteam, and routes player 2's handoff to "
                     "pad 2.",
                caution="Never played. Respawns are off in every split-screen "
                        "mode while this is on, though the HUD still shows the "
                        "lobby's respawn count; the handoff happens whatever "
                        "that count is. When a player's whole fireteam "
                        "is down, that half of the screen stays dark, as it "
                        "does in stock split screen when respawns run out, and "
                        "the mission fails when everyone is down."),

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
        Setting("gr_tp_camera", "Third-person camera", CHOICE, "off", "World",
                confidence="verified",
                choices=[
                    Choice("off", "Off (first person, as shipped)", ""),
                    Choice("centered", "Raised, centred",
                           "0.35 m above the eye, 2.75 m back."),
                    Choice("ots", "Over the right shoulder",
                           "0.2 m up, 0.45 m right, 2.25 m back."),
                    Choice("ots_left", "Over the left shoulder",
                           "0.2 m up, 0.45 m left, 2.25 m back."),
                ],
                help="Ghost Recon's third-person camera only ever runs for a "
                     "spectator: the game forces a live player back to first "
                     "person every frame. This lets you play in it -- you "
                     "start every mission in third person, with the reticle, "
                     "zoom panel and action menu shown. The camera sweeps "
                     "from your eye like the stock one, so walls pull it in, "
                     "and it stays 0.25 m above the floor. Every shot starts "
                     "on the camera's centre line, so rounds go where the "
                     "reticle is. Zooming stays in third person (the zoom "
                     "narrows the view), except a sniper rifle: its scope "
                     "uses first person from the start of the zoom until it "
                     "has zoomed back out. Mounted guns use first "
                     "person. Your own soldier is drawn -- the game never "
                     "draws the soldier a camera follows, in any view, and "
                     "this limits that to first person and to a camera "
                     "pushed into his head. Works per player in split "
                     "screen. His weapon is held up in the aiming "
                     "poses and his muzzle flash is drawn: the game gives "
                     "those only to soldiers that zoom in (the AI does when it "
                     "aims) and never draws a player's own flash, since it "
                     "takes a player's view to be first person.",
                caution="Played 2026-09-27. No pad button toggles the view, so "
                        "this is third person all the time except when "
                        "on a mounted gun. The sweep ignores characters: the camera can "
                        "sit inside a teammate standing behind you. Shots "
                        "start up to 0.5 m from your eye, so you can fire "
                        "past cover your eye is behind -- the AI still sees "
                        "you where you are. Spectators also get the HUD. The aiming pose and your "
                        "muzzle flash (2026-09-28) are not yet played."),
        Setting("gr_smooth_anim", "Distant soldiers animate smoothly", BOOL, False,
                "World", confidence="experimental",
                help="Every soldier updates on his own clock: SimHuman::UpdateVisibility gives "
                     "each one an interval and SimHuman::Update runs his whole "
                     "update -- movement and animation -- only once that much time "
                     "has built up, then advances by all of it. A soldier in view "
                     "gets 0.0225 s per (his distance / the near distance), so far "
                     "soldiers move a few times a second and their running looks "
                     "choppy; at 60 fps even near ones step every other frame. This "
                     "makes the interval 0 for every soldier in view, so he updates "
                     "every frame. Soldiers out of view keep their slow rate.",
                caution="Never played. More soldiers updated per frame costs emulated CPU; with total war multipliers PCSX2 may need its EE cycle rate raised."),
        Setting("gr_show_soldiers", "Soldiers stay visible after you leave "
                "them", BOOL, False, "World", confidence="experimental",
                help="In first person the game hides the soldier you are looking "
                     "through, and means to show him again after drawing your "
                     "view -- but that half of the code was compiled out, so he "
                     "stays hidden for good. Savestates show the result: in "
                     "split screen neither player ever sees the other's "
                     "soldier, and every Ghost you have switched away from is "
                     "invisible. This shows him again once your own view is "
                     "drawn. The third-person camera always includes it.",
                caution="Never played. You are still hidden from your own "
                        "first-person view, as before."),
        Setting("gr_tp_distance", "Third person: camera distance", CHOICE,
                "preset", "World", confidence="experimental",
                requires={"gr_tp_camera": ("centered", "ots", "ots_left")},
                choices=[
                    Choice("preset", "As the camera choice says", ""),
                    Choice("1.75", "1.75 m", ""),
                    Choice("2.0", "2 m", ""),
                    Choice("2.25", "2.25 m", ""),
                    Choice("2.5", "2.5 m", ""),
                    Choice("2.75", "2.75 m", ""),
                    Choice("3.0", "3 m", ""),
                ],
                help="How far behind your eye the camera sits (walls still "
                     "pull it in). The centred camera is 2.75 m by default, "
                     "the shoulder cameras 2.25 m."),
        Setting("gr_tp_aim_eye", "Third person: shots start from the eye",
                BOOL, False, "World", confidence="experimental",
                requires={"gr_tp_camera": ("centered", "ots", "ots_left")},
                help="Keeps every free shot starting at the soldier's eye, as "
                     "in stock, instead of on the camera's line. Nothing "
                     "can be shot around cover, but rounds land a fixed "
                     "0.2-0.5 m below and beside the reticle. Locked-on shots "
                     "stay exact either way."),
        Setting("gr_extra_cameras", "Unlock the chase and ghost cameras", BOOL,
                False, "World", confidence="experimental",
                help="The camera cycle wraps at 3 of the 5 camera modes the "
                     "engine defines. This raises the wrap so chase and ghost "
                     "join the rotation. It only matters while spectating: a "
                     "live player is held in first person (see 'Third-person "
                     "camera'). It used to wrap at 6, which let the cycle "
                     "reach a sixth view with no camera update and froze the "
                     "picture."),

        Setting("gr_tw_enemies", "Enemy followers", CHOICE, "1", "Total War",
                confidence="verified",
                choices=[
                    Choice("1", "Off (as shipped)", ""),
                    Choice("2", "x2", "A lone sentry gets a follower, a pair becomes 4."),
                    Choice("3", "x3", "A lone sentry leads two; pairs and threes become 6."),
                    Choice("4", "x4", "A lone sentry leads three; everything else becomes 6."),
                    Choice("6", "x6", "Every enemy team becomes 6."),
                ],
                help="Every enemy team -- most are one to three soldiers -- "
                     "gets copies of its own soldiers when the mission loads, "
                     "so the game's own team AI makes them followers in "
                     "formation. Reinforcements a script brings in later get "
                     "theirs too. No team grows past 6 (the game runs no AI "
                     "for a team of 7). Soldiers a script keeps hidden until "
                     "later are not copied, so no copy can hold up a 'kill "
                     "everyone' objective; named officers keep their "
                     "objectives and their followers are plain soldiers. The "
                     "radar is clamped to its 30 contacts. The draw sort, which held "
                     "30 soldiers of one kind in view and froze Jungle Storm "
                     "C03 at x4, is rewritten without that limit. x3 fits every mission; x4 fits most.",
                caution="Played at x2-x4 2026-09-27; the draw-sort rewrite played "
                        "in Jungle Storm (C03 at x4), not yet here. About 25 KB of memory per "
                        "extra soldier: missions keep 3.8-7.5 MB free: x3 adds about 1.5-2.2 MB, x4 up to 2.8 MB (tight in M12), x6 up to 4 MB -- use the 128 MB option for x6. Frame rate drops with the "
                        "number of soldiers. Vehicle crews' extra members "
                        "stay on foot."),
        Setting("gr_tw_allies", "More AI teammates", CHOICE, "1", "Total War",
                confidence="experimental",
                choices=[
                    Choice("1", "Off (as shipped)", ""),
                    Choice("2", "x2", "Each AI Ghost brings one more: a fireteam "
                                      "of you and 2 becomes you and 4."),
                    Choice("3", "x3", "Every fireteam becomes 6."),
                ],
                help="Each AI Ghost in your squad gets copies in the same "
                     "fireteam, in single player and split screen; the "
                     "soldiers the players control are never copied. The "
                     "squad is built by the platoon screen (or the split-screen "
                     "soldier chooser), so the copies are made right where "
                     "it finishes. No fireteam grows past 6. The copies are "
                     "named '_Reserve' and are not campaign soldiers. Single "
                     "player's debrief has 6 soldier rows and does not check; "
                     "it now lists the first 6.",
                caution="Never played. Memory and frame rate as for enemy "
                        "followers. Kits are copied from the original soldier."),
        Setting("gr_tw_heap128", "Use PCSX2's 128 MB of RAM", BOOL, False,
                "Total War", confidence="experimental",
                help="The game keeps soldiers, textures and sounds in one "
                     "heap that ends at a fixed address near 32 MB, which is "
                     "what limits the multipliers above. This moves the heap "
                     "to 32 MB and gives it 95 MB, for PCSX2's 128 MB mode "
                     "(Settings > Advanced > 'Enable 128MB RAM (Dev Console)').",
                caution="Needs that PCSX2 setting: without it the game crashes "
                        "the moment it starts. Never booted. Does not work on a "
                        "real PS2."),

        # ---- controls ---------------------------------------------------
        Setting("gr_controls", "Controller layout", CHOICE, "stock", "Controls",
                confidence="experimental",
                choices=[
                    Choice("stock", "Ghost Recon (as shipped)", ""),
                    Choice("jungle_storm", "Jungle Storm",
                           "Jungle Storm's buttons, click zoom and stick feel."),
                    Choice("jungle_storm_buttons",
                           "Jungle Storm buttons, Ghost Recon sticks",
                           "Buttons and click zoom only; the right stick "
                           "turns as in Ghost Recon."),
                ],
                help="Jungle Storm's pad layout in Ghost Recon, for all three "
                     "pad configurations in Options. Configuration 1: R2 "
                     "quick order, R3 zoom one click at a time (1x, 4x, the "
                     "weapon's most, back to 1x), d-pad LEFT / RIGHT peek, "
                     "SELECT next soldier, L2 previous soldier (Jungle "
                     "Storm's Quick Select and headset buttons, which Ghost "
                     "Recon has not got), L3 nothing. Configurations 2 and 3 "
                     "get Jungle Storm's configurations 2 and 3. The Options "
                     "controller diagram shows the new buttons. 'Jungle Storm' "
                     "also takes its right stick: a smaller dead zone (25 "
                     "instead of 32) and half Ghost Recon's turn speed. Both "
                     "players get the layout in split screen.",
                caution="Never played. Text elsewhere in the game (tutorial, "
                        "hints) still names Ghost Recon's buttons. Zoom out "
                        "has no button of its own: click through to 1x."),
        Setting("gr_quick_trigger", "Quick trigger taps always fire", BOOL, False,
                "Weapons", confidence="experimental",
                help="Let go of R1 and press it again quickly and the game "
                     "throws the new press away if it comes within one "
                     "round's time of the last shot (60 / rounds per minute: "
                     "67-100 ms for most rifles) -- and it never looks at R1 "
                     "again while you hold it, so the gun stays silent until "
                     "you let go and press once more. This keeps the press "
                     "for the players' own soldiers. Ghost Recon already fires a new burst's first round one round's time after the press, so no gun fires faster than its rate. The AI keeps the "
                     "rule as shipped.",
                caution="Never played. Semi-automatic and burst fire can be "
                        "tapped as fast as the gun's own rate of fire, which "
                        "the rule held to roughly half."),
        Setting("gr_hu_all", "Heroes Unleashed (PS2): everything below", BOOL, False,
                "Heroes Unleashed", confidence="experimental",
                help="Heroes Unleashed is a PC realism mod for Ghost Recon. This "
                     "turns on every part of it these discs can take; each part "
                     "also has its own switch below. What it cannot bring over: "
                     "its new maps, missions, game types and weapons, its "
                     "400-800 m draw distances, and the AI noticing dead bodies.",
                caution="Never played as a set."),
        Setting("gr_hu_spot", "Heroes Unleashed spotting distances", BOOL, False,
                "Heroes Unleashed", confidence="experimental",
                help="How far enemies can notice you is capped by each level's "
                     "spotting distance. The PS2 games ship the PC's own numbers "
                     "(40-125 m); Heroes Unleashed corrected them on every map, "
                     "mostly to 150 m, a few dense ones to 45-100 m. This uses "
                     "its number for every map it has, and the stock number "
                     "x1.67 (its median change, at most 150 m) for maps it does "
                     "not ship. The difficulty factor on top is unchanged, as "
                     "on PC.",
                caution="Never played. Enemies see you from much further; past "
                        "80 m they can see you before the game draws them -- "
                        "raise 'How far away soldiers are drawn' to match. "
                        "Replaces the level-file spotting card on the maps it "
                        "knows."),
        Setting("gr_hu_damage", "Heroes Unleashed damage model", BOOL, False,
                "Heroes Unleashed", confidence="experimental",
                help="Heroes Unleashed's hit model: every head hit kills, "
                     "chest as stock, abdomen deadlier (300 vs 400), arms and "
                     "legs survivable (1350 / 2050 / 900 / 1800 vs 700 / 1000 / "
                     "500 / 800), armour stronger (0 / 400 / 750 / 950 vs 0 / "
                     "150 / 350 / 750). Lower numbers mean deadlier hits.",
                caution="Never played. It cuts both ways: your head is as "
                        "fragile as theirs. Replaces 'How much punishment a "
                        "body takes' while on."),
        Setting("gr_hu_weapons", "Heroes Unleashed weapons", CHOICE, "off",
                "Heroes Unleashed", confidence="experimental",
                choices=[
                    Choice("off", "Off (as shipped)", ""),
                    Choice("you", "Tuned for you",
                           "Shared guns take HU's player numbers: yours handle "
                           "like HU's, and the AI carrying them is sharper too."),
                    Choice("ai", "Tuned for the AI",
                           "Shared guns take HU's AI numbers: the AI is as "
                           "inaccurate as in HU, and so are you."),
                ],
                help="Every gun with a Heroes Unleashed counterpart (AK47 -> "
                     "AK-47, M16 -> M16A4, M4 -> M4A1, OICW, M249 SAW, ...) "
                     "takes its ballistics, weight and magazine, recoil, all "
                     "twelve stance and movement accuracies, turn and settle "
                     "times, exactly as HU writes them. HU gives the AI its own, "
                     "far less accurate copy of each gun; on these discs most "
                     "guns are one file shared by you and the AI, so this picks "
                     "whose numbers they get. Fire modes, zoom levels "
                     "and reticles stay as shipped, and so do the stationary "
                     "guns and the few with no HU counterpart.",
                caution="Never played. The all-in-one switch picks 'Tuned for "
                        "you'. Replaces any gun edits from other cards on the "
                        "same guns."),
        Setting("gr_hu_skills", "Heroes Unleashed enemy marksmanship", BOOL, False,
                "Heroes Unleashed", confidence="experimental",
                help="Heroes Unleashed rewrites every soldier on its own 25-255 "
                     "scale; this engine reads skills as whole numbers clamped "
                     "to 0-8, so those numbers would make every enemy the "
                     "worst possible shot and every soldier a perfect sneak. "
                     "This ports HU's stated aim instead -- no enemies with "
                     "super-human accuracy: every hostile soldier's weapon "
                     "skill two steps lower (never below 1). Your squad is "
                     "untouched.",
                caution="Never played. Stacks with 'extra skill' and "
                        "marksmanship dials."),
    ] + rstuning.cards("gr_")


STOCK[0x003DFCAC] = 0x344351EC  # ori v1, v0, 0x51ec: 0.045 s (halved), the in-view update interval


def build_edits(v: dict) -> list:
    e = []

    def w(va, value, note):
        e.append(WordEdit(va, value, STOCK[va], note))

    pool = int(v.get("gr_decal_pool", 20))
    if pool != 20:
        w(0x0046D9D0, 0x24050000 | (pool & 0xFFFF), "bullet-hole pool = %d" % pool)
        w(0x0046D9EC, 0x24020000 | (pool & 0xFFFF), "bullet-hole clear loop = %d" % pool)
        w(0x0046DA98, 0x24030000 | (pool & 0xFFFF), "bullet holes cleared on load = %d" % pool)

    life = v.get("gr_decal_life", "stock")
    if DECAL_LIFETIMES.get(life):
        w(0x00249638, DECAL_LIFETIMES[life], "bullet-hole lifetime")
        if v.get("gr_decal_short"):
            w(0x00249740, SHORT_LIFETIMES[life], "short-lived surfaces too")

    if v.get("gr_decal_everywhere"):
        w(0x002496EC, NOP, "draw a hole on unrecognised surfaces too")

    alpha = DECAL_ALPHA.get(v.get("gr_decal_strength", "stock"))
    if alpha:
        w(0x0056FEDC, alpha, "bullet-hole alpha (0x80 = opaque)")

    if v.get("gr_ss_effects"):
        w(0x0024EF38, NOP, "split screen: CreateGeneralEffect")
        # 0x00252A8C (DrawEffects) is NOT here: that branch chooses the
        # per-player path, which writes both players' weather anchors and
        # night-vision flags; nopping it leaves player 2's stale
        w(0x0024C8B8, NOP, "split screen: AddGeneralEffects")

    for va, value, stock, note in grextras.gr_edits(v):
        e.append(WordEdit(va, value, stock, note))

    weather = v.get("gr_weather", "stock")
    if weather in ("half", "double"):
        f = 2 if weather == "double" else 0.5
        for va, rt, stock_n in ((0x00257C80, 5, 4000), (0x002584FC, 5, 2500),
                                (0x00460420, 5, 300), (0x004627D0, 5, 100)):
            n = max(16, min(0x7FFF, int(stock_n * f)))
            w(va, 0x24000000 | (rt << 16) | n, "weather particles = %d" % n)

    fps = v.get("gr_fps", "stock")
    if fps == "60":
        w(0x00271F14, 0x1000000E, "60 FPS: gameplay never waits a second vblank")
    elif fps == "60sp":
        w(0x00271F28, 0x90412880, "60 FPS outside split screen: read the split flag")
        w(0x00271F2C, 0x10200008, "60 FPS outside split screen: skip the second wait")

    spray = BLOOD_SPRAY.get(v.get("gr_blood_spray", "stock"))
    if spray:
        w(0x0045CBEC, spray, "blood spray lasts longer")

    if v.get("gr_blood"):
        w(0x00247B24, 0x24030001, "blood pools ignore the Blood option")
        w(0x00247D24, 0x24030001, "blood spray ignores the Blood option")

    if v.get("gr_keep_bodies"):
        w(0x003CADA4, 0x24020001, "ShowDeadBodies always answers yes")

    for va, value, stock, note in grsquad.gr_edits(
            fireteams=bool(v.get("gr_ss_fireteams")),
            handoff=bool(v.get("gr_ss_fireteams") and v.get("gr_ss_handoff")),
            bullet_holes=bool(v.get("gr_ss_bulletholes")),
            briefing=bool(v.get("gr_ss_briefing")),
            teammates=bool(v.get("gr_ss_teammates")),
            orders=bool(v.get("gr_ss_orders")),
            js_controls=v.get("gr_controls", "stock") != "stock"):
        e.append(WordEdit(va, value, stock, note))

    if v.get("gr_first_person_body"):
        w(0x003A80F4, 0x10000010, "never hide your own soldier")
    if v.get("gr_smooth_anim"):
        w(0x003dfcac, 0x00001825, "soldiers in view update every frame (interval 0)")
    if v.get("gr_extra_cameras"):
        # 5, not 6: view 5 has no camera update and freezes the picture
        w(0x003A8B88, 0x28420005, "camera cycle wraps at 5, not 3")

    for va, value, stock, note in grshrapnel.gr_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grhitblur.gr_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grcamera.gr_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grcontrols.gr_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grcallouts.gr_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grtotalwar.gr_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grsight.gr_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grtrigger.gr_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grsplat.gr_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grhuspot.gr_edits(v):
        e.append(WordEdit(va, value, stock, note))

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


#: The extras gallery is keyed by mission number, so it doubles as per-mission
#: artwork. Measured on the disc: sketches exist for Georgia `G01`-`G15` and
#: Desert Siege `D01`-`D08`, and Desert Siege alone also has an in-engine
#: screenshot `D01`-`D08`. All 31 decode at 640x480. The five TAC training
#: levels have neither, which is why they still get one picture.
SKETCH_GEORGIA = 15
SKETCH_DESERT = 8


def mission_art_for(key):
    """Every picture this mission's card can show, best first.

    The tactical map comes first because it is the one that says where you are
    going; the concept sketch and, on Desert Siege, the screenshot follow. A
    name that is not on the disc costs nothing -- the caller drops anything
    that fails to decode -- but these ranges were counted rather than guessed.
    """
    for mission in MISSIONS:
        if key != mission_key(mission[0]):
            continue
        out = [mission[8]]
        code = mission[1]
        number = code[1:] if code[:1] == "M" else code[1:]
        if code[:1] == "M" and number.isdigit() \
                and int(number) <= SKETCH_GEORGIA:
            out.append("SF_SKETCH_GROUP_G%02d" % int(number))
        elif code[:1] == "D" and number.isdigit() \
                and int(number) <= SKETCH_DESERT:
            out.append("SF_SKETCH_GROUP_D%02d" % int(number))
            out.append("SF_BACKGROUND_GROUP_D%02d" % int(number))
        return out
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
    out += rstuning.edits("gr_", grhu.without_overridden("gr_", v), "GR.IMG")
    out += grhu.data_edits("gr_", v)
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

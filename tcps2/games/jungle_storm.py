"""Tom Clancy's Ghost Recon: Jungle Storm (PS2, SLUS-20820) -- profile.

The same Red Storm engine as Ghost Recon PS2, with a smaller boot ELF and two
overlay blobs in an `MWo3` container. Those overlays turned out to be the Fonix
speech-recognition engine and the Ubi.com lobby client -- no gameplay in either
-- so unlike Rainbow Six 3 the thing to patch here is the boot executable.

Jungle Storm is the one game of the three with a **named, editable enemy count**.
Its Defend game type carries `Recruit enemy count`, `Veteran enemy count` and
`Elite enemy count` as script variables, shipping at 20/25/35 single player and
30/40/50 in co-op. That is the closest thing either Ghost Recon has to a
built-in wave-size dial, and it is a direct edit rather than a code patch.

Two differences from Ghost Recon worth knowing, both measured:

  * Jungle Storm's executable is **stripped** -- the symbol table is present but
    empty -- so its addresses were recovered by matching code signatures against
    the unstripped Ghost Recon build and walking the call graph from there.
  * It **flattened the skill ladder**. Ghost Recon names templates by tier
    (`_rec_`/`_vet_`/`_eli_`); Jungle Storm names them by appearance and leaves
    almost every placed enemy at the bottom of the stat range. So tier promotion
    does not exist here and the skill dial edits the numbers directly.
"""

from __future__ import annotations

from .. import (grcallouts, grcamera, grextras, grhitblur, grshrapnel, grsight, grsquad,
               grdeathmusic, grfrag, grhu, grhuspot, grpierce, grselcopy, grsmoke, grsplat, grsuppress,
               grtotalwar, grtrigger, grsprint, grshotgun, grshotsound, grlan)
from ..model import (BOOL, CHOICE, INT, Choice, FileEdit, GameProfile, Overlay,
                     Setting, WordEdit)
from . import rseweapons, rstuning

BASE = 0x00100000
FILE_DELTA = 0x100         # ELF PT_LOAD: VA 0x00100000 lives at file 0x100
FILE_SPAN = 0x00512900 + FILE_DELTA
NOP = 0x00000000

ELF = Overlay(
    name="SLUS_208.20",
    iso_pattern=r"/SLUS_208\.20$",
    base_va=BASE,
    kind="raw",
    file_delta=FILE_DELTA,
    file_span=FILE_SPAN,
)

STOCK = {
    0x00431930: 0x24050014,   # addiu a1, zero, 20   bullet-hole array
    0x0043194C: 0x2A020014,   # slti  v0, s0, 20     its clear-loop bound
    0x004319F8: 0x2A030014,   # slti  v1, s0, 20     BulletHoleManagerPS2::Clear (load, restart)
    0x00245E4C: 0x3C0341F0,   # lui v1, 0x41f0       30.0f decal lifetime
    0x00245F28: 0x3C024000,   # lui v0, 0x4000       2.0f short-lived surfaces
    0x00245EF8: 0x1000000F,   # b                    unknown surface -> no decal
    0x00423B08: 0x1440000B,   # bne  EffMgrPS2::PreRender
    0x00423E60: 0x14400024,   # bne  hot air / heat haze
    0x00424D70: 0x1440007C,   # bne  night vision
    0x00427BA4: 0x10400005,   # beq  SnowEffectPS2 ctor (inverted sense)
    0x00388958: 0x28420003,   # slti ToggleCameraView wrap
    # dead bodies: split screen / multiplayer clear the ShowDeadBodies result
    0x003A9F54: 0x0000882D,   # move s1, zero   SimHuman::Update
    0x003BE608: 0x0000802D,   # move s0, zero   SimHuman::Render
    # frame rate: the main loop's frame wait (0x00159D80) adds a second vblank
    0x00159E9C: 0x1040000B,   # beqz v0 (not in the action phase)
    0x00159EA0: 0x00000000, 0x00159EA4: 0x3C010068, 0x00159EA8: 0x24020001,
    0x00159EAC: 0x8C23CF40, 0x00159EB0: 0x8C64342C, 0x00159EB8: 0x00831823,
    0x00159EBC: 0x14620003, 0x00159EC0: 0x00000000,
}

#: 60 in single player, 30 kept in split screen: the "== 1 vblank" test now
#: also needs the split-screen flag (g_graphic_sys+0x2880); a0 is rewritten
#: before its next read at 0x00159EF0
FPS_SP_ONLY = {
    0x00159EA0: 0x3C010068,   # lui  at, 0x68
    0x00159EA4: 0x8C23CF40,   # lw   v1, -0x30c0(at)
    0x00159EA8: 0x90622880,   # lbu  v0, 0x2880(v1)
    0x00159EAC: 0x8C64342C,   # lw   a0, 0x342c(v1)   vsync count
    0x00159EB0: 0x10400006,   # beqz v0, 0x159ecc     not split: no second wait
    0x00159EB8: 0x24630001,   # addiu v1, v1, 1       (0x159eb4 loads the previous count)
    0x00159EBC: 0x14830003,   # bne  a0, v1, 0x159ecc
    0x00159EC0: 0x0000202D,   # move a0, zero
}
# split-screen fireteams: the hook plus the whole cave region
STOCK.update(grsquad.JS_STOCK)
STOCK.update(grextras.JS_STOCK)
STOCK.update(grshrapnel.JS_STOCK)
STOCK.update(grcamera.JS_STOCK)
STOCK.update(grhitblur.JS_STOCK)
STOCK.update(grcallouts.JS_STOCK)
STOCK.update(grtotalwar.JS_STOCK)
# Four in-place sites. The cave's own stock words are already recorded
# by grsquad, which owns the whole lzo block grsprint rents a hole in.
STOCK.update(grsprint.JS_STOCK)
STOCK.update(grsight.JS_STOCK)
STOCK.update(grtrigger.JS_STOCK)
STOCK.update(grsplat.JS_STOCK)
STOCK.update(grhuspot.JS_STOCK)
STOCK.update(grfrag.JS_STOCK)
STOCK.update(grpierce.JS_STOCK)
STOCK.update(grdeathmusic.JS_STOCK)
STOCK.update(grsuppress.JS_STOCK)
STOCK.update(grselcopy.JS_STOCK)
STOCK.update(grsmoke.JS_STOCK)

# "perm" loads 0x7F7F0000 (3.39e38 s): spawn + life never overflows or expires,
# so a hole goes only when the ring reuses its slot -- Render never fades them
# "perm" is 999,424 s (11.5 days), not the float maximum: a full ring reuses
# the hole with the least life left, and at 3.39e38 every hole has the same
# float remaining, so slot 0 took every new hole. At 1e6 the oldest goes first.
DECAL_LIFE = {"stock": None, "120": 0x3C0342F0, "1000": 0x3C03447A, "perm": 0x3C034974}
SHORT_LIFE = {"stock": None, "120": 0x3C0242F0, "1000": 0x3C02447A, "perm": 0x3C024974}
# the hole renderer's vertex colour {0x40, 0x40, 0x40, 0x20} at 0x0057B710
# (read only at 0x00431E48); the last word is the alpha
DECAL_ALPHA = {"stock": None, "50": 0x40, "75": 0x60, "100": 0x80}
STOCK[0x0057B71C] = 0x00000020
# online: the online manager's DNAS launch (0x00556970, message 0x125)
DNAS_SKIP = (
    (0x00556A90, 0x0C0C200C, 0x0C1263F4),   # jal RSGameMessage::Create
    (0x00556A94, 0x24040001, 0x24040126),   #  li a0, 0x126 (DNAS passed)
    (0x00556A98, 0x0C040270, 0x0040802D),   # move s0, v0
    (0x00556A9C, 0x0040802D, 0x0C0492C8),   # jal post
    (0x00556AA0, 0x1440000B, 0x0200202D),   #  move a0, s0
    (0x00556AA4, 0x0000202D, 0x0C0492B8),   # jal release
    (0x00556AA8, 0x3C04005A, 0x0200202D),   #  move a0, s0
    (0x00556AAC, 0x0200282D, 0x10000012),   # b epilogue
    (0x00556AB0, 0x0C046358, 0x00000000),   #  nop
)
STOCK.update({va: s for va, s, _n in DNAS_SKIP})
# blood: the options' BloodOn getter (IkeOptions+0xA3), read by both blood handlers
STOCK[0x00247344] = 0x908200A3  # lbu v0, 0xa3(a0)
# blood spray lifetime: the billboard setup's type-7 branch delay slot
STOCK[0x0042278C] = 0x3C023F00  # lui v0, 0x3f00 (0.5 s)
BLOOD_SPRAY = {"2": 0x3C024000, "5": 0x3C0240A0}

NOTES = (
    "Jungle Storm keeps its enemies in data. The population options rewrite the "
    "game's own mission and game-type files; the originals are copied beside the "
    "ISO first and “Restore disc” puts every one back at the byte it "
    "came from.\n\n"
    "Shipping totals across the 21 missions with an order of battle: 657 enemies "
    "on Easy, 804 on Normal, 955 on Hard and Elite. That spread is the per-actor "
    "difficulty suppression flags.\n\n"
    "Defend is the mode with a real enemy-count dial -- the game type names its "
    "three counts as script variables, 20/25/35 solo and 30/40/50 in co-op.\n\n"
    "The render options patch the boot executable. Its symbol table is stripped, "
    "so those addresses were recovered by matching code against the unstripped "
    "Ghost Recon build; every stock word is checked before anything is written, "
    "but none has been watched working in a running game."
)


def _settings():
    return [
        # ---- defend waves -----------------------------------------------
        Setting("js_defend_enable", "Set the Defend enemy counts", BOOL, False,
                "Enemy Waves", confidence="applied",
                help="Defend is the one mode in either Ghost Recon whose enemy "
                     "counts are named, editable numbers rather than placed "
                     "actors. Ships at 20/25/35 for single player and 30/40/50 "
                     "for co-op.", touches="data"),
        Setting("js_defend_recruit", "Recruit difficulty", INT, 20, "Enemy Waves",
                minimum=5, maximum=200, unit="enemies", confidence="applied",
                requires={"js_defend_enable": True}, touches="data"),
        Setting("js_defend_veteran", "Veteran difficulty", INT, 25, "Enemy Waves",
                minimum=5, maximum=200, unit="enemies", confidence="applied",
                requires={"js_defend_enable": True}, touches="data"),
        Setting("js_defend_elite", "Elite difficulty", INT, 35, "Enemy Waves",
                minimum=5, maximum=200, unit="enemies", confidence="applied",
                requires={"js_defend_enable": True},
                caution="These are total enemies for the whole round. Raising "
                        "all three a long way has not been tested for framerate.",
                touches="data"),

        # ---- enemies ----------------------------------------------------
        Setting("js_all_difficulties", "Every soldier on every difficulty", BOOL,
                False, "Enemies", confidence="applied",
                help="The game removes soldiers on lower difficulties with "
                     "per-actor Easy/Normal/Hard flags. Deleting them puts the "
                     "full Hard force into every mission at every setting -- "
                     "657 enemies becomes 955 across the campaign.",
                caution="Rewrites 18 mission files inside GR.IMG.", touches="data"),
        Setting("js_reveal_hidden", "Spawn the script-held reinforcements", BOOL,
                False, "Enemies", confidence="experimental",
                help="Actors that ship with Hidden=\"1\" wait for a mission "
                     "script. This puts them on the map from the start.",
                caution="An actor a script expects to spawn later may behave "
                        "oddly when it is already there.", touches="data"),
        Setting("js_skill", "Extra enemy skill", INT, 0, "Enemies",
                minimum=0, maximum=4, unit="points", confidence="applied",
                help="Adds to armour, weapon skill, stamina, stealth and "
                     "leadership in every hostile template. Jungle Storm leaves "
                     "almost every placed enemy at the bottom of the range, so "
                     "this has more room here than it does in Ghost Recon. Only "
                     "templates used by non-allied companies are touched.",
                caution="Two points is already a large jump from the shipped "
                        "values.", touches="data"),

        # ---- bullet holes -----------------------------------------------
        Setting("js_decal_pool", "Bullet holes kept on screen", INT, 20,
                "Bullet Holes", minimum=20, maximum=400, unit="holes",
                confidence="experimental",
                help="A 20-entry ring, with two clear loops that have to move "
                     "with it: one when the ring is built, one when a quick "
                     "load or restart wipes it (missing before 2026-09-28, so "
                     "holes past the 20th outlived a reload). The bounds are "
                     "different instructions here than in Ghost Recon, so the "
                     "two games genuinely need different words."),
        Setting("js_decal_life", "How long bullet holes last", CHOICE, "stock",
                "Bullet Holes", confidence="experimental",
                choices=[Choice("stock", "Stock (30 seconds)", ""),
                         Choice("120", "2 minutes", ""),
                         Choice("1000", "About 17 minutes", ""),
                         Choice("perm", "Permanent",
                                "Holes never expire; the oldest is reused only "
                                "when the 'kept on screen' cap is full.")],
                help="Holes do not fade -- they are drawn at full strength "
                     "until their lifetime runs out or the ring reuses their "
                     "slot. Pair 'Permanent' with a higher cap."),
        Setting("js_decal_short", "Also extend the short-lived surfaces", BOOL,
                False, "Bullet Holes", confidence="experimental",
                requires={"js_decal_life": ("120", "1000", "perm")},
                help="Three surface types get a 2-second hole instead of 30."),
        Setting("js_decal_everywhere", "Bullet holes on every surface", BOOL,
                False, "Bullet Holes", confidence="experimental",
                help="Removes the early-out that draws nothing on a surface "
                     "type the decal code does not recognise.",
                caution="Untested, and the most invasive of the decal options."),
        Setting("js_decal_strength", "How dark bullet holes are", CHOICE,
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
        Setting("js_shrapnel", "Shrapnel marks from explosions", INT, 0,
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
        Setting("js_shrapnel_size", "Shrapnel mark size", CHOICE, "1",
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
        Setting("js_ss_effects", "Full snow in split screen", BOOL, False,
                "Split Screen", confidence="experimental",
                help="The snow constructor builds a reduced snowfall in split "
                     "screen; this gives it the single-player one. (This "
                     "option used to also nop three more split-screen "
                     "branches -- pre-render, heat haze, night vision -- which "
                     "turned out to choose the per-player path, not suppress "
                     "anything, and would have broken player 2's sky, night "
                     "vision and darkened-screen state. They have been "
                     "removed. Bullet holes have their own option.)"),
        Setting("js_ss_stealth", "Crouch and prone hide you in split screen",
                BOOL, False, "Split Screen", confidence="experimental",
                help="An enemy's sight range shrinks to 3/4 when you crouch and "
                     "1/2 prone -- in single player. The check reads player "
                     "1's stance, so split screen skips it and stance buys "
                     "neither player anything. This uses the stance of the "
                     "soldier actually being looked at, in both modes.",
                caution="Never played. In single player an enemy looking at "
                        "one of your AI teammates now weighs that teammate's "
                        "stance instead of yours."),
        Setting("js_ss_rain", "Rain in split screen", BOOL, False,
                "Split Screen", confidence="experimental",
                help="Split screen refuses to create rain, though a second rain "
                     "slot and its per-player draw are already in the engine. "
                     "This creates rain for both halves.",
                caution="Never played. Jungle Storm's rain-sound switch was not "
                        "located, so the rain may be silent in split screen."),
        Setting("js_enemy_ammo", "Enemies can run out of magazines", BOOL,
                False, "Enemies", confidence="experimental",
                help="Every enemy fireteam is script-controlled, and the game "
                     "gives script-controlled soldiers infinite magazines. "
                     "This stops the exemption.",
                caution="Never played. What an enemy does once dry is "
                        "untested."),
        Setting("js_enemy_grenades", "Enemies throw grenades",
                BOOL, False, "Enemies", confidence="experimental",
                help="Ghost Recon's soldiers decide under suppressive fire "
                     "whether to throw a grenade at the spot instead of "
                     "spraying it; Jungle Storm dropped that decision, so its "
                     "enemies only ever throw while investigating a spot 20-30 "
                     "m away. This puts Ghost Recon's decision back, with the "
                     "rules of Ghost Recon's 'throw more readily' option: "
                     "indoors too, 10-35 m (75 m with a launcher). Asked every "
                     "time a soldier would lay down suppressive fire, on one "
                     "engagement in three, and one time in two when he loses "
                     "sight of you (you went behind cover, where the fighting "
                     "is close: engagements themselves start 50-150 m out, "
                     "beyond a throw). A throw also needs only 4 m of clear arc "
                     "instead of 10 m, which the jungle almost never gave. The "
                     "game's own check that keeps grenades off nearby "
                     "friendlies stays, and so does its 30 s wait between a "
                     "fireteam's grenades. Soldiers in your own fireteam never "
                     "decide it themselves; your other fireteam can, as in "
                     "Ghost Recon.",
                caution="Not yet seen in play: a 2026-09-28 savestate showed "
                        "295 engagement starts and no throw, all at 50-270 m; "
                        "the loss-of-sight ask is new since. A grenade may "
                        "bounce off foliage beyond the first 4 m. No enemy in "
                        "that savestate carried a grenade launcher."),
        Setting("js_enemy_suppress", "Enemies suppress when they lose sight of you",
                BOOL, False, "Enemies", confidence="experimental",
                help="Jungle Storm's soldiers seldom lay down suppressive fire: "
                     "only a few team behaviours start it. With this, a soldier "
                     "who loses sight of the enemy he is engaging -- you went "
                     "behind cover -- fires at the spot for 3-7 s, one time in "
                     "two, the same suppression the game's own team code uses "
                     "and only where it agrees he can put rounds. Then he "
                     "carries on as before. With 'Enemies throw grenades' on, "
                     "the grenade is asked first, and a throw replaces the "
                     "suppression. Your AI teammates do it too.",
                caution="Never played. More suppressive fire means more "
                        "ammunition spent; soldiers may run dry sooner."),
        Setting("js_enemy_sight_all", "Enemies see at full strength on "
                "every difficulty", BOOL, False, "Enemies",
                confidence="experimental",
                help="Recruit, Veteran and Elite enemies see 0.5, 0.56 and "
                     "0.61 of the level's spotting distance. This sets all "
                     "three to 1.0."),
        Setting("js_enemy_sight_mult", "How far enemies can see (multiplier)",
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
        Setting("js_sniper_sight", "Enemy snipers see farther", CHOICE, "1",
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
        Setting("js_sniper_precision", "Enemy snipers lose the built-in miss",
                BOOL, False, "Enemies", confidence="experimental",
                help="Every enemy's aim point carries a deliberate 0.10-0.25 m "
                     "miss on top of his skill-based error (+-0.10 m), scaled "
                     "up to full at 50 m. This drops the deliberate miss for "
                     "hostile snipers only.",
                caution="Never played. Their aim error and weapon spread "
                        "remain."),
        Setting("js_soldier_draw", "How far away soldiers are drawn", CHOICE,
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
        Setting("js_ss_fireteams", "AI fireteams for both players", BOOL,
                False, "Split Screen", confidence="verified",
                help="Split screen gives each player one nameless soldier -- "
                     "a split-screen savestate holds 1P, 2P and the enemy, "
                     "nobody else. This adds two named Ghosts to each "
                     "player's fireteam: Vernon Jefferson and Jon Snyder with "
                     "player 1, Horace Dominguez and Robbie Chukitus with "
                     "player 2, created as AI the way single player creates "
                     "your squadmates.",
                caution="Watched working 2026-09-26: all four spawn with their "
                        "names. Standard rifleman and support kits; player 2's "
                        "soldiers only appear when player 2 is in the game. "
                        "They cannot be ordered or switched to yet, and dying "
                        "still respawns you."),
        Setting("js_ss_bodies", "Keep dead bodies in split screen", BOOL,
                False, "Split Screen", confidence="experimental",
                help="Bodies flash and vanish about a second after a soldier "
                     "dies in split screen, but stay in single player. The "
                     "game's own Dead Body option decides it -- it is on -- "
                     "and split screen and multiplayer overwrite the answer "
                     "with 'off' right after reading it. This removes that "
                     "overwrite, so split screen honours the option like "
                     "single player does.",
                caution="Never played. Keeping a body frees and allocates "
                        "nothing -- the soldier exists for the whole mission "
                        "either way -- but each body in view is drawn once per "
                        "viewport, which may cost frame rate in a busy fight."),
        Setting("js_tw_enemies", "Enemy followers", CHOICE, "1", "Total War",
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
                     "C03 at x4, is rewritten without that limit. x2 is the safe choice here.",
                caution="Played at x2-x4 2026-09-27; the draw-sort rewrite played "
                        "on C03 at x4 2026-09-28. About 25 KB of memory per "
                        "extra soldier: the big missions keep only 2.6-3.0 MB free: x2 adds 1.2-1.5 MB, x3 and up 2.3-4.2 MB -- use the 128 MB option for x3 and up. Frame rate drops with the "
                        "number of soldiers. Vehicle crews' extra members "
                        "stay on foot."),
        Setting("js_tw_allies", "More AI teammates", CHOICE, "1", "Total War",
                confidence="verified",
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
                     "it now lists the first 6. Changing soldier: the L1 "
                     "command map stays the originals (Alpha 1-3, Bravo 1-3); "
                     "SELECT with nobody under the crosshair takes you to the "
                     "next living copy in squad order (Alpha 4-6, Bravo 4-6, "
                     "round again), also while you lie dead before the "
                     "automatic hand-off. SELECT on a soldier under the "
                     "crosshair takes him, as before.",
                caution="Played 2026-09-27. Memory and frame rate as for enemy "
                        "followers. Kits are copied from the original soldier. "
                        "The SELECT cycle (2026-09-28) is not yet played; "
                        "SELECT while dead may leave the death fade on until "
                        "the automatic hand-off's time (6 s)."),
        Setting("js_tw_heap128", "Use PCSX2's 128 MB of RAM", BOOL, False,
                "Total War", confidence="verified",
                help="The game keeps soldiers, textures and sounds in one "
                     "heap that ends at a fixed address near 32 MB, which is "
                     "what limits the multipliers above. This moves the heap "
                     "to 32 MB and gives it 95 MB, for PCSX2's 128 MB mode "
                     "(Settings > Advanced > 'Enable 128MB RAM (Dev Console)').",
                caution="Needs that PCSX2 setting: without it the game crashes "
                        "the moment it starts. Never booted. Does not work on a "
                        "real PS2."),
        Setting("js_squad_death_music", "Death music when any of your squad falls",
                BOOL, False, "World", confidence="experimental",
                help="Jungle Storm plays one of its six death tracks only when "
                     "player 1's own soldier dies. This plays one whenever any "
                     "soldier of your squad dies -- AI Ghosts, their total-war "
                     "copies, and player 2 in split screen. Enemies stay "
                     "silent.",
                caution="Never played. Each squad death starts a track, so "
                        "deaths close together restart it."),
        Setting("js_callouts", "Everyone calls out", BOOL, False, "World",
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
        Setting("js_callouts_contact", "Players call 'contact'", BOOL, False,
                "World", confidence="experimental",
                requires={"js_callouts": True},
                help="A player who spots a new enemy says 'contact' himself, "
                     "at most every 15 seconds per fireteam (the timer the "
                     "game uses for 'grenade!'). Enemy teams, AI teammates "
                     "and faint sightings are left as they are.",
                caution="Never played."),
        Setting("js_callouts_respawn", "'Rock and roll' on a takeover", BOOL,
                False, "Split Screen", confidence="experimental",
                requires={"js_ss_handoff": True},
                help="In split screen, taking over a soldier -- the one-life "
                     "handoff or SELECT switching -- plays 'rock and roll' "
                     "after single player's takeover blip. The line is on "
                     "every mission's sound bank and nothing in the game "
                     "plays it.",
                caution="Never played. Recorded in one voice only, so it may "
                        "not match the soldier you take over. Single player "
                        "keeps only the blip."),
        Setting("js_blood", "Blood", BOOL, False, "World",
                confidence="verified",
                help="Jungle Storm has Ghost Recon's whole blood system -- the "
                     "spray when a soldier is hit and the pool that spreads "
                     "under a body, with their textures on the disc -- and "
                     "ships with it switched off: the options start with "
                     "Blood off in every language, the Blood row in the game "
                     "options is hidden, and saved profiles keep it off. This "
                     "makes the game's Blood setting always answer yes, in "
                     "single player and split screen, where both halves "
                     "already draw blood. Pools under bodies in split screen "
                     "also need 'Keep dead bodies in split screen', since "
                     "split screen drops the body before its pool starts.",
                caution="Played 2026-09-27. One word: the getter both blood "
                        "handlers ask. Each body's pool is drawn once per "
                        "viewport in split screen, so it spreads twice as "
                        "fast there."),
        Setting("js_penetration", "Bullets go through thin cover", BOOL,
                False, "World", confidence="experimental",
                help="Each round is traced once and stops at the first thing "
                     "it meets, so a plank fence stops a rifle like a concrete "
                     "wall. This lets a round go on through scenery that its "
                     "energy beats: the gun's muzzle energy (Jungle Storm's "
                     "own kill coefficients: pistols about 500-900, 5.56 mm "
                     "3000, 7.62 mm 3900-6500, .50 32000) against a cost per "
                     "surface -- glass, leaves and grass 100, wood and drywall "
                     "300, thin metal 1500, metal 2500, heavy wood 3500, thick "
                     "metal 12000, concrete 20000 -- each surface passed "
                     "taking its cost off, up to 4. Ground, water, sand, "
                     "floors and roofs always stop it. Every surface passed "
                     "gets its bullet hole and sound; whoever is behind is hit "
                     "as if nothing were in the way.",
                caution="Never played. Damage is not reduced by what the round "
                        "went through. The surface numbers are Ghost Recon's "
                        "(from its debug information) and assumed the same in "
                        "Jungle Storm; a number past Ghost Recon's 27 stops "
                        "the round."),
        # L3 was left completely unbound by the game -- verified against
        # all three controller configurations -- so this steals nothing.
        # It is a walk/run switch, not a fourth gear: Jungle Storm has no
        # speed above running, and the numeric run factor the engine used
        # to multiply by is dead code in this build. See grsprint.
        grsprint.card("js_", "Controls"),
        Setting("js_skip_dnas", "Online: skip the DNAS check", BOOL, False,
                "Online", confidence="verified",
                help="Choosing ONLINE loads Sony's DNAS.BIN, whose servers "
                     "are gone, before the Ubi.com login; the network screen "
                     "waits for its 'passed' (message 0x126) or 'failed' "
                     "(0x127). This posts 'passed' straight away instead of "
                     "loading DNAS, the message DNAS.BIN itself sends on "
                     "success. First step towards online co-op without "
                     "Ubisoft: the Ubi.com lobby still needs a stand-in "
                     "server.",
                caution="Played 2026-09-27. Alone it only gets you as far as the "
                        "Ubi.com login, which fails without a lobby server."),
        Setting("js_blood_splatter", "Blood splatter on walls and ground", BOOL, False,
                "World", confidence="verified", requires={"js_blood": True},
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
                caution="Played 2026-09-28: splatters draw and clear on quick "
                        "load. Splatters take bullet-hole slots, so a "
                        "long fight replaces the oldest holes and splatters "
                        "sooner; a bigger bullet-hole pool helps."),
        Setting("js_blood_spray", "Blood spray lasts", CHOICE, "stock", "World",
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
                     "grenade and scripted deaths do not, for anyone. Needs 'Blood'.",
                caution="The spray is drawn where the bullet hit and does not "
                        "follow the soldier, so a long one hangs in the air "
                        "after he moves -- 5 seconds looked wrong in play "
                        "(2026-09-27). For spotting hits, not for normal play."),
        Setting("js_ss_briefing", "Mission briefing in split screen", BOOL,
                False, "Split Screen", confidence="verified",
                help="Split screen's Mission mode goes straight from the menu "
                     "to choosing your soldier. This puts single player's "
                     "briefing screen -- mission text, objectives, map -- in "
                     "between. Split screen already loads the mission and its "
                     "objectives the same way single player does before that "
                     "point. Accept continues to the soldier screen; Back "
                     "returns to the split-screen menu. Other split-screen "
                     "game types are unchanged.",
                caution="Watched working 2026-09-26: briefing shown, Accept "
                        "and Back route as described. Only player 1's pad "
                        "drives it, as with the split-screen menu."),
        Setting("js_ss_teammates", "Single player's roster: P1 leads Alpha, "
                "P2 leads Bravo", BOOL, False, "Split Screen",
                confidence="experimental",
                requires={"js_ss_briefing": True},
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
                        "The HUD still labels the players 1P and 2P. The "
                        "earlier version of this option went from the platoon "
                        "screen to the soldier screen; that is gone."),
        Setting("js_ss_hitblur", "Hit blur in split screen", BOOL, False,
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
        Setting("js_ss_bulletholes", "Bullet holes in split screen", BOOL,
                False, "Split Screen", confidence="verified",
                help="Split screen creates bullet holes and never draws them "
                     "-- a split-screen savestate holds two live holes that "
                     "were never once aged, because the render that ages them "
                     "never ran. The per-viewport loop calls the water ripples "
                     "but not the bullet holes; this makes it call both, "
                     "after each viewport's own draw area is set.",
                caution="Watched working 2026-09-26: holes show in both "
                        "halves (faint on the jungle ground), and a savestate "
                        "holds 11 live holes updated on the saved frame and 5 "
                        "that aged out after exactly 30 seconds. Single "
                        "player already runs "
                        "the hole render every frame; there the likelier gap is that "
                        "the jungle's grass, brush and water are surface "
                        "types the game refuses to mark, which is what "
                        "'Bullet holes on every surface' changes."),
        Setting("js_ss_orders", "Team orders and soldier switching", BOOL,
                False, "Split Screen", confidence="verified",
                requires={"js_ss_handoff": True},
                help="Each player commands and switches within their own "
                     "fireteam. SELECT: switch to the next living Ghost in "
                     "your fireteam. The quick-order button (R2 on the "
                     "default layouts, R3 on the third): tap to toggle your "
                     "fireteam between Hold and Advance; hold it for half a "
                     "second and let go to send your teammates to the spot "
                     "under your crosshair, where they hold even if you walk "
                     "away (tap back to Advance to recall them). Player 2's "
                     "buttons only ever reach player 2's soldiers. Switching "
                     "uses the same path as the death handoff.",
                caution="Watched working 2026-09-26: SELECT switches, R2 "
                        "toggles Hold / Advance. 'Move to' is new and never "
                        "played. Single player gives move orders on the "
                        "command map instead, which split screen lacks. The "
                        "tap now acts when you let go. Jungle Storm's d-pad "
                        "left/right are peek and L3 has no binding, hence "
                        "SELECT. No order HUD in split screen: voice and hand "
                        "signals confirm."),
        Setting("js_ss_handoff", "One life: take over a teammate on death",
                BOOL, False, "Split Screen", confidence="verified",
                requires={"js_ss_fireteams": True},
                help="Single player's rule in split screen: no respawns, and "
                     "when your soldier dies you carry on as a living Ghost "
                     "from your own fireteam. Split screen already runs single "
                     "player's handoff code on death and bails one branch "
                     "early; this lets it finish, keeps the search inside the "
                     "dead player's fireteam, and routes player 2's handoff to "
                     "pad 2.",
                caution="Watched working 2026-09-26; the savestate after it "
                        "shows 1P down and AI-controlled and his teammate "
                        "Vernon Jefferson under player 1's control, player 2 "
                        "untouched. Any lobby respawn setting works: the "
                        "handoff is sent even with None or with the count used "
                        "up (before, those left you on 'Player N: Dead' until "
                        "SELECT). Respawns are refused anyway, though the HUD "
                        "still shows the count. When a "
                        "player's whole fireteam is down, that half of the "
                        "screen stays dark until the mission fails."),

        Setting("js_fps", "Frame rate", CHOICE, "stock", "World",
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
                     "the long-standing 60 FPS cheat -- your split-screen "
                     "savestates taken with that cheat show 16-17 ms frames -- "
                     "baked into the disc so it survives the CRC change every "
                     "other patch causes.",
                caution="Load from a cold boot: a savestate brings back "
                        "whatever code was in memory when it was taken."),

        # ---- camera -----------------------------------------------------
        Setting("js_tp_camera", "Third-person camera", CHOICE, "off", "World",
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
                help="Jungle Storm's third-person camera only ever runs for a "
                     "spectator: the game forces a live player back to first "
                     "person every frame. This lets you play in it -- you "
                     "start every mission in third person and return to it "
                     "after a cutscene, with the reticle, zoom panel and "
                     "action menu shown. The camera sweeps from your eye like "
                     "the stock one, so walls pull it in, and it stays 0.25 m "
                     "above the floor. Every shot starts on the camera's "
                     "centre line, so rounds go where the reticle is. Zooming "
                     "stays in third person (the zoom narrows the view), "
                     "except a sniper rifle: its scope uses first person "
                     "from the start of the zoom until it has zoomed back "
                     "out. Mounted guns use first person. Your own soldier "
                     "is drawn -- the game never draws the soldier a camera "
                     "follows, in any view, and this limits that to first "
                     "person and to a camera pushed into his head. Works "
                     "per player in split screen. His weapon is held up in the aiming "
                     "poses and his muzzle flash is drawn: the game gives "
                     "those only to soldiers that zoom in (the AI does when it "
                     "aims) and never draws a player's own flash, since it "
                     "takes a player's view to be first person.",
                caution="Over the right shoulder watched working "
                        "2026-09-26 in split screen, both players' soldiers "
                        "drawn; the centred and left presets are the same "
                        "code with other offsets, not yet seen. No pad button "
                        "toggles the view, so "
                        "this is third person all the time except when "
                        "on a mounted gun. The sweep ignores characters: the camera can "
                        "sit inside a teammate standing behind you. Shots "
                        "start up to 0.5 m from your eye, so you can fire "
                        "past cover your eye is behind -- the AI still sees "
                        "you where you are. Spectators also get the HUD. The aiming pose and your "
                        "muzzle flash (2026-09-28) are not yet played."),
        Setting("js_smooth_anim", "Distant soldiers animate smoothly", BOOL, False,
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
        Setting("js_show_soldiers", "Soldiers stay visible after you leave "
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
        Setting("js_tp_distance", "Third person: camera distance", CHOICE,
                "preset", "World", confidence="experimental",
                requires={"js_tp_camera": ("centered", "ots", "ots_left")},
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
        Setting("js_tp_aim_eye", "Third person: shots start from the eye",
                BOOL, False, "World", confidence="experimental",
                requires={"js_tp_camera": ("centered", "ots", "ots_left")},
                help="Keeps every free shot starting at the soldier's eye, as "
                     "in stock, instead of on the camera's line. Nothing "
                     "can be shot around cover, but rounds land a fixed "
                     "0.2-0.5 m below and beside the reticle. Locked-on shots "
                     "stay exact either way."),
        Setting("js_extra_cameras", "Unlock the chase and ghost cameras", BOOL,
                False, "World", confidence="experimental",
                help="The camera cycle wraps at 3 of the 5 modes the engine "
                     "defines. This raises the wrap so chase and ghost join in. "
                     "It only matters while spectating: a live player is held "
                     "in first person (see 'Third-person camera'). It used to "
                     "wrap at 6, which let the cycle reach a sixth view with "
                     "no camera update and froze the picture."),
        Setting("js_smoke", "Smoke grenades", BOOL, False, "Weapons",
                confidence="experimental",
                help="Jungle Storm has no smoke grenade, only smoke effects "
                     "(burning wrecks, a few maps). With this, any soldier "
                     "carrying grenades can switch them: select the grenades "
                     "and press reload, and the slot changes between FRAG "
                     "and SMOKE (one count for both; the weapon panel shows "
                     "which). A smoke grenade pops 2 s after it lands into a "
                     "45 s cloud -- the game's own large smoke effect -- with "
                     "no blast. Nobody sees through a cloud from 2 s after it "
                     "pops until 5 s before it clears: a sight line passing "
                     "within 5 m of its centre stops the AI spotting, and an "
                     "engaged soldier loses his target (he may then suppress "
                     "or throw into it, with those options). Works for your "
                     "squad and the enemy alike. The grenade is the unused "
                     "SQUIRREL.PRJ rewritten; the label replaces the PC-only "
                     "'Toggle Console' line in every strings file.",
                caution="Played 2026-09-28: a smoke kit's grenade made a "
                        "cloud (large type 3). Switching with reload in the "
                        "field is not yet seen working in play. The AI side "
                        "is 'AI throws smoke' below."),
        Setting("js_smoke_kits", "Smoke grenade kits", CHOICE, "second", "Weapons",
                confidence="experimental",
                choices=[
                    Choice("none", "None (switch with reload)", ""),
                    Choice("second", "One per class",
                           "Rifleman MP5-SD, Heavy Weapons M240 and Sniper "
                           "M98 kits carry 6 smoke instead of 6 frag; the "
                           "M16, M249 and M24 grenade kits keep frags."),
                    Choice("all", "Every grenade kit",
                           "Every kit that carried frags (the classes', the "
                           "Demolitions Z84 and the heroes') carries smoke."),
                ],
                help="Kits in the kit screen that carry smoke grenades from "
                     "the start. The kit picture still shows grenades; the "
                     "item is named SMOKE. Reload still switches FRAG / SMOKE "
                     "in the field. Needs 'Smoke grenades'."),
        Setting("js_smoke_ai", "AI throws smoke", CHOICE, "all", "Weapons",
                confidence="experimental",
                choices=[
                    Choice("off", "Never", ""),
                    Choice("squad", "Your squad", ""),
                    Choice("enemies", "Enemies", "Everyone not in your squad."),
                    Choice("all", "Everyone", ""),
                ],
                help="When a soldier runs for cover (the game's own "
                     "RunForCover: an open fight, a hold or suppress order, "
                     "dodging a grenade) and his threat is 12-90 m away, "
                     "one time in two he first throws a smoke grenade 10 m "
                     "toward it, then runs. He must carry grenades (any "
                     "kit's frags do: the throw comes out as smoke) and no "
                     "grenade launcher, and his fireteam must not have used "
                     "a grenade in the last 30 s. Across the whole mission "
                     "the AI pops smoke at most once every 15 s and never "
                     "while 2 clouds are already up (frame rate: a cloud is "
                     "a lot of particles). A smoke throw ignores the check "
                     "for branches in its first metres. Needs 'Smoke "
                     "grenades'."),
        Setting("js_smoke_look", "Smoke grenade cloud", CHOICE, "round", "Weapons",
                confidence="experimental",
                choices=[
                    Choice("round", "Round cloud",
                           "A dome about 6 m across that billows up and out "
                           "from the grenade: ~60 puffs 3.5 m wide. Built "
                           "into an effect slot the game leaves empty."),
                    Choice("smoke_large_type1", "Large smoke, type 1", ""),
                    Choice("smoke_large_type2", "Large smoke, type 2", ""),
                    Choice("smoke_large_type3", "Large smoke, type 3",
                           "The waterfall mist two maps (a ravine, a river) "
                           "place: 75 sheets 9 m wide on a flat 24 x 8 m "
                           "patch. Looks flat and is heavy on frame rate."),
                ],
                help="What a smoke grenade's cloud looks like: the round "
                     "cloud made for it, or one of the game's three large "
                     "smoke effects. Needs 'Smoke grenades'."),
        Setting("js_shotgun", "Shotgun", BOOL, False, "Weapons", confidence="experimental",
                help="Adds a pump shotgun, built out of parts the disc already "
                     "carries: the unused M4 masterkey shotgun model, and the "
                     "G36 weapon slot, which is listed in the game's weapon "
                     "index but is in no kit and whose own model was cut. No "
                     "weapon is lost. One trigger pull throws a spread of "
                     "pellets, each aimed separately -- the engine's own "
                     "rounds-per-pull, which no shipped weapon uses for more "
                     "than one round. Short range, heavy hit up close."),
        Setting("js_shotgun_pellets", "Shotgun pellets", CHOICE, "9", "Weapons",
                confidence="experimental",
                choices=[Choice("6", "6 pellets", "Easier on ammo."),
                         Choice("8", "8 pellets", ""),
                         Choice("9", "9 pellets", "What Heroes Unleashed gives its shotguns.")],
                help="How many pellets one shell throws. The magazine holds "
                     "eight shells' worth, and the ammo counter counts "
                     "pellets, so it drops by this much per shot. Needs "
                     "'Shotgun'."),
        Setting("js_shotgun_sound", "Shotgun uses the Sum of All Fears blast", BOOL, False, "Weapons",
                confidence="experimental",
                help="Neither game has a shotgun sound, so the gun borrows a "
                     "rifle's. This copies the real shotgun blast out of a Sum "
                     "of All Fears disc -- the same engine -- over an unused "
                     "sample in the sound bank that every mission loads. "
                     "Needs that disc present, and 'Shotgun'."),
        Setting("js_shotgun_spread", "Shotgun pattern", CHOICE, "hu", "Weapons",
                confidence="experimental",
                choices=[Choice("hu", "Heroes Unleashed", "That mod's own shotgun accuracy, unchanged."),
                         Choice("medium", "Twice as open", ""),
                         Choice("wide", "Four times as open", "A scattergun.")],
                help="How far the pellets of one shell spread. Heroes "
                     "Unleashed gives its shotguns rifle-tight accuracy and "
                     "gets the pattern from a separate pellet-spread field "
                     "the PS2 game does not have, so here the accuracy cone "
                     "has to be both: open it too far and the gun stops "
                     "pointing where you aim. Needs 'Shotgun'."),
        Setting("js_shotgun_kits", "Kits carrying the shotgun", CHOICE, "some", "Weapons",
                confidence="experimental",
                choices=[Choice("none", "None", "The shotgun exists but no kit carries it."),
                         Choice("some", "A rifleman and a demolitions kit", ""),
                         Choice("all", "Six kits", "One per specialty, plus spares.")],
                help="Which single-player kits carry the shotgun in place of "
                     "their rifle. Needs 'Shotgun'."),
        Setting("js_quick_trigger", "Quick trigger taps always fire", BOOL, False,
                "Weapons", confidence="experimental",
                help="Let go of R1 and press it again quickly and the game "
                     "throws the new press away if it comes within one "
                     "round's time of the last shot (60 / rounds per minute: "
                     "67-100 ms for most rifles) -- and it never looks at R1 "
                     "again while you hold it, so the gun stays silent until "
                     "you let go and press once more. This keeps the press "
                     "for the players' own soldiers. Jungle Storm fires the first round at once, so a kept press is timed from the last shot instead: its first round leaves exactly one round's time after it, as if R1 had never been let go. The AI keeps the "
                     "rule as shipped.",
                caution="Never played. Semi-automatic and burst fire can be "
                        "tapped as fast as the gun's own rate of fire, which "
                        "the rule held to roughly half."),
        Setting("js_hu_all", "Heroes Unleashed (PS2): everything below", BOOL, False,
                "Heroes Unleashed", confidence="experimental",
                help="Heroes Unleashed is a PC realism mod for Ghost Recon. This "
                     "turns on every part of it these discs can take; each part "
                     "also has its own switch below. What it cannot bring over: "
                     "its new maps, missions, game types and weapons, its "
                     "400-800 m draw distances, and the AI noticing dead bodies.",
                caution="Never played as a set."),
        Setting("js_hu_spot", "Heroes Unleashed spotting distances", BOOL, False,
                "Heroes Unleashed", confidence="verified",
                help="How far enemies can notice you is capped by each level's "
                     "spotting distance. The PS2 games ship the PC's own numbers "
                     "(40-125 m); Heroes Unleashed corrected them on every map, "
                     "mostly to 150 m, a few dense ones to 45-100 m. This uses "
                     "its number for every map it has, and the stock number "
                     "x1.67 (its median change, at most 150 m) for maps it does "
                     "not ship. The difficulty factor on top is unchanged, as "
                     "on PC.",
                caution="Played 2026-09-28: a save state showed G04 Train loading "
                        "117 m (stock 70). The difficulty factor still cuts the "
                        "enemy's share (your squad never had it): add 'Enemies see "
                        "at full strength' for enemies that out-see your squad. Past "
                        "80 m they can see you before the game draws them -- "
                        "raise 'How far away soldiers are drawn' to match. "
                        "Replaces the level-file spotting card on the maps it "
                        "knows."),
        Setting("js_hu_damage", "Heroes Unleashed damage model", BOOL, False,
                "Heroes Unleashed", confidence="experimental",
                help="Heroes Unleashed's hit model: every head hit kills, "
                     "chest as stock, abdomen deadlier (300 vs 400), arms and "
                     "legs survivable (1350 / 2050 / 900 / 1800 vs 700 / 1000 / "
                     "500 / 800), armour stronger (0 / 400 / 750 / 950 vs 0 / "
                     "150 / 350 / 750). Lower numbers mean deadlier hits.",
                caution="Never played. It cuts both ways: your head is as "
                        "fragile as theirs. Replaces 'How much punishment a "
                        "body takes' while on."),
        Setting("js_hu_weapons", "Heroes Unleashed weapons", CHOICE, "off",
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
                     "whose numbers they get. Jungle Storm already keeps separate player copies of the AK family, which take HU's player numbers while the AI's copies take HU's AI numbers. Fire modes, zoom levels "
                     "and reticles stay as shipped, and so do the stationary "
                     "guns and the few with no HU counterpart. Written into "
                     "the compiled guns (.XBG) the game actually loads.",
                caution="Not yet played with the compiled guns: an earlier "
                        "build edited the .GUN text, which Jungle Storm never "
                        "reads, and changed nothing. The all-in-one switch "
                        "picks 'Tuned for you'."),
        Setting("js_hu_skills", "Heroes Unleashed enemy marksmanship", BOOL, False,
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
    ] + grlan.cards("js_", "Online") + rstuning.cards("js_")


STOCK[0x003BF6C0] = 0xC4207340  # lwc1 f0, 0x7340(at): 0.0225 s, the in-view update interval


def build_edits(v: dict) -> list:
    e = []

    def w(va, value, note):
        e.append(WordEdit(va, value, STOCK[va], note))

    pool = int(v.get("js_decal_pool", 20))
    if pool != 20:
        w(0x00431930, 0x24050000 | (pool & 0xFFFF), "bullet-hole pool = %d" % pool)
        w(0x0043194C, 0x2A020000 | (pool & 0xFFFF), "bullet-hole clear loop = %d" % pool)
        w(0x004319F8, 0x2A030000 | (pool & 0xFFFF), "bullet holes cleared on load / restart = %d" % pool)

    life = v.get("js_decal_life", "stock")
    if DECAL_LIFE.get(life):
        w(0x00245E4C, DECAL_LIFE[life], "bullet-hole lifetime")
        if v.get("js_decal_short"):
            w(0x00245F28, SHORT_LIFE[life], "short-lived surfaces too")
    if v.get("js_decal_everywhere"):
        w(0x00245EF8, NOP, "draw a hole on unrecognised surfaces too")
    alpha = DECAL_ALPHA.get(v.get("js_decal_strength", "stock"))
    if alpha:
        w(0x0057B71C, alpha, "bullet-hole alpha (0x80 = opaque)")

    if v.get("js_ss_effects"):
        # Only the snow word. 0x00423B08, 0x00423E60 and 0x00424D70 turned
        # out to choose the per-viewport path (sky per half, the per-half
        # draw-area / night-vision loop at 0x00423EF4); nopping them ran the
        # full-screen path once instead and broke player 2's view.
        # this one is inverted -- the fix is an unconditional branch, not a nop
        w(0x00427BA4, 0x10000005, "split screen: snow constructor")

    for va, value, stock, note in grextras.js_edits(v, grsquad.JS_STOCK):
        e.append(WordEdit(va, value, stock, note))

    fps = v.get("js_fps", "stock")
    if fps == "60":
        w(0x00159E9C, 0x1000000B, "60 FPS: gameplay never waits a second vblank")
    elif fps == "60sp":
        for va, word in FPS_SP_ONLY.items():
            w(va, word, "60 FPS outside split screen")

    if v.get("js_skip_dnas"):
        for va, _s, word in DNAS_SKIP:
            w(va, word, "online: skip DNAS, post 'passed'")

    for va, value, stock, note in grlan.edits(v, "js_"):
        e.append(WordEdit(va, value, stock, note))

    if v.get("js_blood"):
        w(0x00247344, 0x24020001, "the Blood setting always answers yes")
    spray = BLOOD_SPRAY.get(v.get("js_blood_spray", "stock"))
    if spray:
        w(0x0042278C, spray, "blood spray lasts longer")

    if v.get("js_ss_bodies"):
        w(0x003A9F54, NOP, "split screen keeps bodies: Update honours the option")
        w(0x003BE608, NOP, "split screen keeps bodies: Render honours the option")

    for va, value, stock, note in grsquad.js_edits(
            fireteams=bool(v.get("js_ss_fireteams")),
            handoff=bool(v.get("js_ss_fireteams") and v.get("js_ss_handoff")),
            bullet_holes=bool(v.get("js_ss_bulletholes")),
            briefing=bool(v.get("js_ss_briefing")),
            teammates=bool(v.get("js_ss_teammates")),
            orders=bool(v.get("js_ss_orders"))):
        e.append(WordEdit(va, value, stock, note))

    for va, value, stock, note in grsprint.js_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grshrapnel.js_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grhitblur.js_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grcamera.js_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grcallouts.js_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grtotalwar.js_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grsight.js_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grtrigger.js_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grsplat.js_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grhuspot.js_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grfrag.js_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grpierce.js_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grdeathmusic.js_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grsuppress.js_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grselcopy.js_edits(v):
        e.append(WordEdit(va, value, stock, note))
    for va, value, stock, note in grsmoke.js_edits(v):
        e.append(WordEdit(va, value, stock, note))

    if v.get("js_smooth_anim"):
        w(0x003bf6c0, 0x44800000, "soldiers in view update every frame (interval 0)")
    if v.get("js_extra_cameras"):
        # 5, not 6: view 5 has no camera update and freezes the picture
        w(0x00388958, 0x28420005, "camera cycle wraps at 5, not 3")
    return e



#: Every mission with an order of battle, in the order the disc plays it.
#:
#: `CAMPAIGN.XML` inside the archive lists the campaign in play order, and each
#: `.MIS` names itself in its own `<Shell>` and `<Engine>` blocks -- codename,
#: location, date and time. Here the two are NOT the same: the Colombia campaign is assembled out of the `G0x` and `U0x` files in a scrambled order, so J01 is `g03_the_rock.mis` and J03 is `u05_rail.mis`. Sorting the filenames would put the campaign in the wrong sequence outright. The `<Name>` numbering and the dates both agree with CAMPAIGN.XML instead.
#:
#: The last field is the briefing's tactical map, which the port renamed when it
#: cooked it: `m09_swamp.mis` asks for `M09_SWAMPS.RSB`. So the image name is
#: recorded rather than derived, and a test checks every one of them is really
#: in the archive.
#:
#: (stem, number, codename, place, date, time, soldiers, held back on Easy, map)
MISSIONS = (
    ("C01_PLANTATION", "C01", "Watchful Yeoman", "Punta Tabacal", "March 20, 2010", "06:30", 48, 13, "C01_PLANTATION"),
    ("C02_MILITARY_CAMP", "C02", "Angel Rage", "Pinar del Rio", "April 3, 2010", "19:30", 50, 19, "C02_MILITARY_CAMP"),
    ("C03_HIGH_SIERRA", "C03", "Jaguar Maze", "Sierra de los Organos", "Apr. 12, 2010", "11:20", 47, 19, "C03_HIGH_SIERRA"),
    ("C04_SWAMP_AIRFIELD", "C04", "Hidden Spectre", "Cabo Pepe, Isla de la Juventud", "Apr. 21, 2010", "10:40", 55, 28, "C04_SWAMP_AIRFIELD"),
    ("C05_BRIDGES", "C05", "Rapid Python", "Sierra de los Organos", "April 27, 2010", "01:00", 50, 14, "C05_BRIDGES"),
    ("C06_POLLING_CENTER", "C06", "Liberty Storm", "Cienfuegos", "May 12, 2010", "06:45", 51, 12, "C06_POLLING_CENTER"),
    ("C07_BEACH_RESORT", "C07", "Ocean Forge", "Northwest Cuba, Near Dimas", "May 19, 2010", "11:45", 54, 14, "C07_BEACH_RESORT"),
    ("C08_MOUNTAIN_STRONGHOLD", "C08", "Righteous Archer", "Sierra de los Organos", "June 6, 2010", "08:20", 55, 13, "C08_MOUNTAIN_STRONGHOLD"),
    ("G03_THE_ROCK", "J01", "Totem Ground", "Alta Magdalena", "Aug. 01, 2010", "15:20", 70, 36, "G03_THE_ROCK"),
    ("G04_TRAIN", "J02", "Vapor Knife", "Cienaga Grande", "August 13, 2010", "08:15", 72, 20, "G04_TRAIN"),
    ("U05_RAIL", "J03", "Ocelot Desert", "Tatacoa Desert", "Aug. 17, 2010", "22:00", 54, 3, "U05_RAIL"),
    ("G02_VILLAGE", "J04", "Ocean Hammer", "Buenaventura, Valle de Cauca", "Aug. 28, 2010", "09:00", 72, 9, "G02_VILLAGE"),
    ("G05_DOCK", "J05", "Titan Bolt", "Choco Department", "Sept. 03, 2010", "14:00", 57, 17, "G05_DOCK"),
    ("U02_RIVER", "J06", "Silver Spider", "Meta Department", "Sept. 11, 2010", "20:30", 64, 17, "U02_RIVER"),
    ("U03_RESCUE", "J07", "Whisper Shadow", "Huila Department", "Sept. 28, 2010", "07:45", 76, 39, "U03_RESCUE"),
    ("U01_TRANSMISSION", "J08", "Eagle Clarion", "Caqueta Department", "Oct. 13, 2010", "10:00", 78, 16, "U01_TRANSMISSION"),
    ("TAC01_SHOOTING", "TAC01", "Shooting", "Lubana River", "June 10, 2008", "10:00", 15, 0, "TAC01_SHOOTING"),
    ("TAC02_RESCUE", "TAC02", "Rescue", "South Ossetian Autonomous Region", "May 2, 2008", "15:00", 23, 6, "TAC02_RESCUE"),
    ("TAC03_DEMOLITION", "TAC03", "Demolition", "Severodvinsk, Russia", "Sept. 22, 2008", "09:00", 23, 0, "TAC03_DEMOLITION"),
    ("TAC04_ANTIVEHICLE", "TAC04", "Anti Vehicle", "Venta, Lithuania", "June 24, 2008", "02:15", 6, 0, "TAC04_ANTIVEHICLE"),
    ("TAC05_DEFEND", "TAC05", "Defend", "South Ossetian Autonomous Region", "April 16, 2008", "18:00", 31, 5, "TAC05_DEFEND"),
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
    if not v.get("js_all_difficulties"):
        for mission in MISSIONS:
            if v.get(mission_key(mission[0])):
                out.append(FileEdit(
                    "strip_difficulty", mission_select(mission[0]),
                    "GR.IMG",
                    note="every soldier in %s %s"
                         % (mission[1], mission[2])))
    if v.get("js_defend_enable"):
        out.append(FileEdit("gtf_variables", r"DEFEND\.GTF$", "GR.IMG",
                            {"values": {
                                "Recruit enemy count": int(v.get("js_defend_recruit", 20)),
                                "Veteran enemy count": int(v.get("js_defend_veteran", 25)),
                                "Elite enemy count": int(v.get("js_defend_elite", 35)),
                            }},
                            "Defend enemy counts"))
    if v.get("js_all_difficulties"):
        out.append(FileEdit("strip_difficulty", r"\.MIS$", "GR.IMG",
                            note="every soldier on every difficulty"))
    if v.get("js_reveal_hidden"):
        out.append(FileEdit("reveal_hidden", r"\.MIS$", "GR.IMG",
                            note="spawn the script-held reinforcements"))
    skill = int(v.get("js_skill", 0))
    if skill:
        out.append(FileEdit("bump_stats", r"\.ATR$", "GR.IMG", {"steps": skill},
                            "+%d to every hostile template's skills" % skill,
                            scope="enemy_templates"))
    out += rseweapons.edits('js_', v, 'GR.IMG')
    out += rstuning.edits("js_", grhu.without_overridden("js_", v), "GR.IMG")
    out += grhu.data_edits("js_", v)
    out += grsmoke.data_edits(v)
    out += grshotgun.data_edits(v)
    out += grshotsound.data_edits(v, "js_")
    return out


PROFILE = GameProfile(
    id="jungle_storm_slus20820",
    title="Tom Clancy's Ghost Recon: Jungle Storm",
    short="Jungle Storm",
    serial="SLUS-20820",
    boot="SLUS_208.20",
    volume_hint="SLUS_20820",
    pcsx2_crc="DE1E4DEE",
    overlays=[ELF],
    settings=(_settings() + rseweapons.cards('js_')
              + _mission_settings()),
    build_edits=build_edits,
    build_pnach=lambda v: [],
    build_data=build_data,
    archive_pattern=r"/GR\.IMG$",
    stock_words=STOCK,
    mission_art_for=mission_art_for,
    notes=NOTES,
    ui_art={"archive": "vokes", "patterns": [r"\.RSB$"]},
)

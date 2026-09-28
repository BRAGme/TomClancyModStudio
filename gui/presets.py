"""Starting points, tuned in the order that actually matters.

The population dial is the next-wave trigger, not the wave size: a zone tops
itself up until more than `trigger` of its enemies are alive, so steady state
per zone is roughly `trigger + release`. Set the trigger first, the release
second, and the total last -- the total only decides how long the mode lasts.

Multiply by the number of deployment zones on the map: one on the quiet levels,
two on Shipyard and Alcatraz, three on Trieste, Oil Refinery and Import/Export.
"""

#: The effects split screen throws away. These are all one-word code edits
#: that stop the game disabling something when a second viewport exists.
FX_ON = {
    "viewmodel": True,
    "fx_impact": True,
    "fx_emitters": True,
    "fx_blood": True,
    "fx_weather": True,
    "fx_hidden_emitters": True,
}

#: The HUD split screen throws away, which is a different kind of fix: the
#: wheel and the L1 tap are data edits, and the scope is a code edit plus a
#: cave. They were missing from every preset, so "Split-screen fixes only"
#: quietly delivered the effects and none of the interface -- the wheel stayed
#: shut and the scope stayed a bare reticule.
#:
#: `split_wheel_labels` is deliberately NOT here, though the reason has
#: changed. The wheel itself no longer spans the split -- that was the engine
#: running every viewport's interactions into one canvas, and it is fixed and
#: play-tested. What is still wrong is narrower: the label TEXT does not scale
#: with the viewport, only its position does. An option that is half right is
#: still an option the user should choose deliberately, not one a preset turns
#: on for them.
HUD_ON = {
    # The equipment wheel, and what a tap of L1 does once it is back.
    "split_wheel": True,
    "split_cycle": True,
    # The scope. One switch now: drawing it, fitting it to your half
    # and giving it only to the player who aimed were three cards,
    # and no combination of two of them is worth having.
    "split_scope": True,
    # The first-person weapon: sway to your own stick, and stop the turn
    # channel leaning both players' weapons at once.
    "split_sway": True,
    "split_sway_turn": True,
    # And play the draw animation once instead of twice.
    "split_draw_once": True,
    # Muzzle flashes on your own weapon. The flash was never missing in
    # split screen -- it stayed attached to the third-person weapon, because
    # the call that moves it onto the first-person one sits behind a
    # split-screen test. One byte of UnrealScript, and it cannot change
    # single player, where that call already runs through the guard's other
    # arm. Play-tested on Alpine Village: both players get their own flash
    # and it does not cross the split.
    "split_muzzle": True,
    # See the note above for why split_wheel_labels is not here.
}

FX_OFF = {k: False for k in FX_ON}
HUD_OFF = {k: False for k in HUD_ON}


def _wave(enable, gate, total, size, trigger, hunt=None, mapwide=True):
    # `hunt` is vestigial: wave_hunt was withdrawn on 2026-09-26 as measured
    # inert -- it set the hunt flag on the wave actor and the only code that
    # reads that flag reads it off the spawn POINT. The parameter stays so
    # the call sites below still read as they did, and is not emitted; a
    # preset carrying a withdrawn option is refused by the suite.
    return {"wave_enable": enable, "wave_gate": gate, "wave_total": total,
            "wave_size": size, "wave_trigger": trigger,
            "wave_mapwide": mapwide}


R6_3 = [
    ("Stock — nothing patched",
     dict(_wave(False, "stock", 30, 1, 2, False, False), **FX_OFF,
          **HUD_OFF,
          decal_ring=32, bodies="stock")),

    ("Split-screen fixes only",
     dict(_wave(False, "stock", 30, 1, 2, False, False), **FX_ON, **HUD_ON,
          decal_ring=32, bodies="stock")),

    ("Waves — light  (~3 per zone)",
     dict(_wave(True, "always", 20, 1, 2), **FX_ON, **HUD_ON,
          decal_ring=32, bodies="stock")),

    ("Waves — standard  (~5 per zone)",
     dict(_wave(True, "always", 30, 2, 3), **FX_ON, **HUD_ON,
          decal_ring=64, bodies="15")),

    ("Waves — heavy  (~7 per zone)",
     dict(_wave(True, "always", 60, 3, 4), **FX_ON, **HUD_ON,
          decal_ring=64, bodies="15")),

    ("Waves — flanking  (feeds from behind)",
     dict(_wave(True, "away", 40, 2, 3), **FX_ON, **HUD_ON,
          decal_ring=64, bodies="15")),

    ("Waves — onslaught  (Shipyard/Alcatraz)",
     dict(_wave(True, "always", 150, 4, 6), **FX_ON, **HUD_ON,
          decal_ring=96, bodies="stock")),

    # "They always know where you are." Not one switch -- the engine has no
    # omniscience flag -- but every dial that feeds awareness pushed at once:
    # sight to its ceiling, no penalty for spotting you while they move, the
    # longest hunt after they lose you, and the fastest reaction on contact.
    # Wave mode supplies the rest, because m_bHuntFromStart is set by the
    # spawner and so only reaches enemies the spawner released.
    #
    # It cannot make them see through walls. Line of sight is still line of
    # sight; what changes is that once you are in it, at any range on any map,
    # they react at once and keep coming for three minutes after you break it.
    ("Hunted — they come looking",
     dict(_wave(True, "always", 40, 2, 3, hunt=True, mapwide=True), **FX_ON, **HUD_ON,
          sight=15000, search_time=180, spotting="sharp", speed="fast",
          fire_delay="snap", terro_skill="up",
          decal_ring=64, bodies="15")),
]

# Ghost Recon and Jungle Storm scale difficulty with per-actor suppression
# flags, so "more enemies" is a data edit and "tougher enemies" is a separate
# dial. The render options are all experimental and stay off in every preset
# except the one that exists to try them.

GHOST_RECON = [
    ("Stock — nothing patched",
     dict(gr_all_difficulties=False, gr_reveal_hidden=False, gr_tier="stock",
          gr_skill=0, gr_accuracy=0, gr_lethality="stock", gr_spot=100, gr_decal_pool=20, gr_decal_life="stock",
          gr_decal_short=False, gr_decal_everywhere=False, gr_ss_effects=False,
          gr_weather="stock", gr_first_person_body=False,
          gr_extra_cameras=False)),

    ("Full count on every difficulty",
     dict(gr_all_difficulties=True, gr_reveal_hidden=False, gr_tier="stock",
          gr_skill=0, gr_accuracy=0, gr_lethality="stock", gr_spot=100, gr_decal_pool=20, gr_decal_life="stock",
          gr_decal_short=False, gr_decal_everywhere=False, gr_ss_effects=False,
          gr_weather="stock", gr_first_person_body=False,
          gr_extra_cameras=False)),

    ("Harder — full count, one tier up",
     dict(gr_all_difficulties=True, gr_reveal_hidden=False, gr_tier="up1",
          gr_skill=0, gr_accuracy=0, gr_lethality="stock", gr_spot=100, gr_decal_pool=20, gr_decal_life="stock",
          gr_decal_short=False, gr_decal_everywhere=False, gr_ss_effects=False,
          gr_weather="stock", gr_first_person_body=False,
          gr_extra_cameras=False)),

    ("Brutal — everything, elite",
     dict(gr_all_difficulties=True, gr_reveal_hidden=True, gr_tier="elite",
          gr_skill=1, gr_accuracy=2, gr_lethality="stock", gr_spot=100, gr_decal_pool=20, gr_decal_life="stock",
          gr_decal_short=False, gr_decal_everywhere=False, gr_ss_effects=False,
          gr_weather="stock", gr_first_person_body=False,
          gr_extra_cameras=False)),

    ("Bullet holes that stay",
     dict(gr_all_difficulties=False, gr_reveal_hidden=False, gr_tier="stock",
          gr_skill=0, gr_accuracy=0, gr_lethality="stock", gr_spot=100, gr_decal_pool=120, gr_decal_life="120",
          gr_decal_short=True, gr_decal_everywhere=False, gr_ss_effects=False,
          gr_weather="stock", gr_first_person_body=False,
          gr_extra_cameras=False)),

    ("Split-screen effects",
     dict(gr_all_difficulties=False, gr_reveal_hidden=False, gr_tier="stock",
          gr_skill=0, gr_accuracy=0, gr_lethality="stock", gr_spot=100, gr_decal_pool=20, gr_decal_life="stock",
          gr_decal_short=False, gr_decal_everywhere=False, gr_ss_effects=True,
          gr_weather="stock", gr_first_person_body=False,
          gr_extra_cameras=False)),
]

JUNGLE_STORM = [
    ("Stock — nothing patched",
     dict(js_defend_enable=False, js_all_difficulties=False,
          js_reveal_hidden=False, js_skill=0, js_accuracy=0, js_lethality="stock", js_spot=100, js_decal_pool=20,
          js_decal_life="stock", js_decal_short=False,
          js_decal_everywhere=False, js_ss_effects=False,
          js_extra_cameras=False)),

    ("Full count on every difficulty",
     dict(js_defend_enable=False, js_all_difficulties=True,
          js_reveal_hidden=False, js_skill=0, js_accuracy=0, js_lethality="stock", js_spot=100, js_decal_pool=20,
          js_decal_life="stock", js_decal_short=False,
          js_decal_everywhere=False, js_ss_effects=False,
          js_extra_cameras=False)),

    ("Defend — double the waves",
     dict(js_defend_enable=True, js_defend_recruit=40, js_defend_veteran=50,
          js_defend_elite=70, js_all_difficulties=False,
          js_reveal_hidden=False, js_skill=0, js_accuracy=0, js_lethality="stock", js_spot=100, js_decal_pool=20,
          js_decal_life="stock", js_decal_short=False,
          js_decal_everywhere=False, js_ss_effects=False,
          js_extra_cameras=False)),

    ("Defend — last stand",
     dict(js_defend_enable=True, js_defend_recruit=100, js_defend_veteran=140,
          js_defend_elite=200, js_all_difficulties=True,
          js_reveal_hidden=False, js_skill=1, js_accuracy=0, js_lethality="stock", js_spot=100, js_decal_pool=20,
          js_decal_life="stock", js_decal_short=False,
          js_decal_everywhere=False, js_ss_effects=False,
          js_extra_cameras=False)),

    ("Brutal — full count, skilled",
     dict(js_defend_enable=True, js_defend_recruit=50, js_defend_veteran=70,
          js_defend_elite=100, js_all_difficulties=True,
          js_reveal_hidden=True, js_skill=2, js_accuracy=0, js_lethality="stock", js_spot=100, js_decal_pool=20,
          js_decal_life="stock", js_decal_short=False,
          js_decal_everywhere=False, js_ss_effects=False,
          js_extra_cameras=False)),

    ("Bullet holes that stay",
     dict(js_defend_enable=False, js_all_difficulties=False,
          js_reveal_hidden=False, js_skill=0, js_accuracy=0, js_lethality="stock", js_spot=100, js_decal_pool=120,
          js_decal_life="120", js_decal_short=True,
          js_decal_everywhere=False, js_ss_effects=False,
          js_extra_cameras=False)),
]

PRESETS = {
    "r6_3_slus20883": R6_3,
    "graw_slus21422": [
        ("Stock — nothing patched",
         dict(graw_interval="stock", graw_per_release=1, graw_skill="stock",
              graw_fire_delay="stock", graw_perfect_dist=500, graw_sight=5000,
              graw_search_time=30, graw_speed="stock", graw_spotting="stock",
              graw_grenade_dist=500, graw_grenade_delay="stock")),
        ("Survival — twice the rate",
         dict(graw_interval="0.5", graw_per_release=1)),
        ("Survival — four times the rate",
         dict(graw_interval="0.25", graw_per_release=1)),
        ("Survival — relentless",
         dict(graw_interval="0.25", graw_per_release=2)),
        ("Enemies — sharper",
         dict(graw_skill="up", graw_fire_delay="quick", graw_perfect_dist=800,
              graw_sight=7000, graw_search_time=60, graw_speed="fast",
              graw_spotting="sharp", graw_grenade_dist=300,
              graw_grenade_delay="quick")),
        ("Enemies — brutal",
         dict(graw_skill="elite", graw_fire_delay="snap",
              graw_perfect_dist=1500, graw_sight=10000, graw_search_time=120,
              graw_speed="sprint", graw_spotting="sharp",
              graw_grenade_dist=150, graw_grenade_delay="instant")),
        ("Enemies — gentler",
         dict(graw_skill="down", graw_fire_delay="stock", graw_perfect_dist=200,
              graw_sight=3000, graw_search_time=10, graw_speed="slow",
              graw_spotting="blind", graw_grenade_dist=700,
              graw_grenade_delay="stock")),
    ],
    "soaf_sles51180": [
        ("Stock — nothing patched",
         dict(soaf_all_difficulties=False, soaf_reveal_hidden=False, soaf_skill=0, soaf_accuracy=0, soaf_lethality="stock", soaf_spot=100)),
        ("Full count on every difficulty",
         dict(soaf_all_difficulties=True, soaf_reveal_hidden=False, soaf_skill=0, soaf_accuracy=0, soaf_lethality="stock", soaf_spot=100)),
        ("Brutal — full count, skilled",
         dict(soaf_all_difficulties=True, soaf_reveal_hidden=True, soaf_skill=2,
              soaf_accuracy=2, soaf_lethality="stock", soaf_spot=100)),
        ("Lethal — one or two hits kill anyone",
         dict(soaf_all_difficulties=True, soaf_reveal_hidden=False,
              soaf_skill=1, soaf_accuracy=1, soaf_lethality="much_deadlier",
              soaf_spot=100, soaf_enemy_aim="stock", soaf_enemy_delay="stock",
              soaf_enemy_skill_adj="stock")),
        ("Sharper enemies — aim, reactions and reach",
         dict(soaf_all_difficulties=True, soaf_reveal_hidden=False,
              soaf_skill=0, soaf_accuracy=2, soaf_lethality="stock",
              soaf_spot=150, soaf_enemy_aim="sharp",
              soaf_enemy_delay="quick", soaf_enemy_skill_adj="up")),
    ],
    "gr2_slus21105": [
        ("Stock — nothing changed",
         dict(gr2_grenade_carry=20, gr2_grenade_dist=500,
              gr2_grenade_delay="stock", gr2_fire_delay="stock",
              gr2_skill="stock", gr2_perfect_dist=500, gr2_sight=5000,
              gr2_sens_steps=10, gr2_sens_boost=100)),
        ("Faster look, everything else stock",
         dict(gr2_grenade_carry=20, gr2_grenade_dist=500,
              gr2_grenade_delay="stock", gr2_fire_delay="stock",
              gr2_skill="stock", gr2_perfect_dist=500, gr2_sight=5000,
              gr2_sens_steps=20, gr2_sens_boost=180)),
        ("Sharper enemies",
         dict(gr2_grenade_carry=35, gr2_grenade_dist=350,
              gr2_grenade_delay="quick", gr2_fire_delay="quick",
              gr2_skill="up", gr2_perfect_dist=800, gr2_sight=7000,
              gr2_sens_steps=20, gr2_sens_boost=150)),
        ("Brutal — they shoot first",
         dict(gr2_grenade_carry=60, gr2_grenade_dist=200,
              gr2_grenade_delay="instant", gr2_fire_delay="snap",
              gr2_skill="elite", gr2_perfect_dist=1500, gr2_sight=10000,
              gr2_sens_steps=20, gr2_sens_boost=150)),
        ("Gentler — room to breathe",
         dict(gr2_grenade_carry=5, gr2_grenade_dist=700,
              gr2_grenade_delay="stock", gr2_fire_delay="stock",
              gr2_skill="down", gr2_perfect_dist=200, gr2_sight=3000,
              gr2_sens_steps=15, gr2_sens_boost=130)),
    ],
    # These carried `ld_mag_size` and `ld_fire_rate`, which are not settings
    # on this profile and never have been -- the real dials are split ally
    # and enemy. Every one of these presets was silently doing nothing for
    # those two values, which is what the preset tests now catch.
    "lockdown_slus21144": [
        ("Stock — nothing changed",
         dict(ld_enemy_skill=0, ld_ally_mag=100, ld_enemy_mag=100,
              ld_ally_rate=100, ld_enemy_rate=100)),
        ("Sharper enemies",
         dict(ld_enemy_skill=3, ld_ally_mag=100, ld_enemy_mag=100,
              ld_ally_rate=100, ld_enemy_rate=100)),
        ("Brutal — everyone fights like a mercenary",
         dict(ld_enemy_skill=8, ld_ally_mag=100, ld_enemy_mag=100,
              ld_ally_rate=100, ld_enemy_rate=100)),
        ("Gentler",
         dict(ld_enemy_skill=-4, ld_ally_mag=100, ld_enemy_mag=100,
              ld_ally_rate=100, ld_enemy_rate=100)),
        # The old name said only "Bigger magazines" over a dial that did not
        # exist, so there is no behaviour to preserve. Naming the side it
        # applies to is clearer than guessing the reader meant both.
        ("Bigger magazines — your squad",
         dict(ld_enemy_skill=0, ld_ally_mag=200, ld_enemy_mag=100,
              ld_ally_rate=100, ld_enemy_rate=100)),
    ],
    "ghost_recon_slus20613": GHOST_RECON,
    "jungle_storm_slus20820": JUNGLE_STORM,
}

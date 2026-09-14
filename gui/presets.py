"""Starting points, tuned in the order that actually matters.

The population dial is the next-wave trigger, not the wave size: a zone tops
itself up until more than `trigger` of its enemies are alive, so steady state
per zone is roughly `trigger + release`. Set the trigger first, the release
second, and the total last -- the total only decides how long the mode lasts.

Multiply by the number of deployment zones on the map: one on the quiet levels,
two on Shipyard and Alcatraz, three on Trieste, Oil Refinery and Import/Export.
"""

FX_ON = {
    "viewmodel": True,
    "fx_impact": True,
    "fx_emitters": True,
    "fx_blood": True,
    "fx_weather": True,
    "fx_hidden_emitters": True,
}

FX_OFF = {k: False for k in FX_ON}


def _wave(enable, gate, total, size, trigger, hunt=True, mapwide=True):
    return {"wave_enable": enable, "wave_gate": gate, "wave_total": total,
            "wave_size": size, "wave_trigger": trigger, "wave_hunt": hunt,
            "wave_mapwide": mapwide}


R6_3 = [
    ("Stock — nothing patched",
     dict(_wave(False, "stock", 30, 1, 2, False, False), **FX_OFF,
          decal_ring=32, bodies="stock")),

    ("Split-screen fixes only",
     dict(_wave(False, "stock", 30, 1, 2, False, False), **FX_ON,
          decal_ring=32, bodies="stock")),

    ("Waves — light  (~3 per zone)",
     dict(_wave(True, "always", 20, 1, 2), **FX_ON,
          decal_ring=32, bodies="stock")),

    ("Waves — standard  (~5 per zone)",
     dict(_wave(True, "always", 30, 2, 3), **FX_ON,
          decal_ring=64, bodies="15")),

    ("Waves — heavy  (~7 per zone)",
     dict(_wave(True, "always", 60, 3, 4), **FX_ON,
          decal_ring=64, bodies="15")),

    ("Waves — flanking  (feeds from behind)",
     dict(_wave(True, "away", 40, 2, 3), **FX_ON,
          decal_ring=64, bodies="15")),

    ("Waves — onslaught  (Shipyard/Alcatraz)",
     dict(_wave(True, "always", 150, 4, 6), **FX_ON,
          decal_ring=96, bodies="stock")),
]

# Ghost Recon and Jungle Storm scale difficulty with per-actor suppression
# flags, so "more enemies" is a data edit and "tougher enemies" is a separate
# dial. The render options are all experimental and stay off in every preset
# except the one that exists to try them.

GHOST_RECON = [
    ("Stock — nothing patched",
     dict(gr_all_difficulties=False, gr_reveal_hidden=False, gr_tier="stock",
          gr_skill=0, gr_decal_pool=20, gr_decal_life="stock",
          gr_decal_short=False, gr_decal_everywhere=False, gr_ss_effects=False,
          gr_weather="stock", gr_first_person_body=False,
          gr_extra_cameras=False)),

    ("Full count on every difficulty",
     dict(gr_all_difficulties=True, gr_reveal_hidden=False, gr_tier="stock",
          gr_skill=0, gr_decal_pool=20, gr_decal_life="stock",
          gr_decal_short=False, gr_decal_everywhere=False, gr_ss_effects=False,
          gr_weather="stock", gr_first_person_body=False,
          gr_extra_cameras=False)),

    ("Harder — full count, one tier up",
     dict(gr_all_difficulties=True, gr_reveal_hidden=False, gr_tier="up1",
          gr_skill=0, gr_decal_pool=20, gr_decal_life="stock",
          gr_decal_short=False, gr_decal_everywhere=False, gr_ss_effects=False,
          gr_weather="stock", gr_first_person_body=False,
          gr_extra_cameras=False)),

    ("Brutal — everything, elite",
     dict(gr_all_difficulties=True, gr_reveal_hidden=True, gr_tier="elite",
          gr_skill=1, gr_decal_pool=20, gr_decal_life="stock",
          gr_decal_short=False, gr_decal_everywhere=False, gr_ss_effects=False,
          gr_weather="stock", gr_first_person_body=False,
          gr_extra_cameras=False)),

    ("Bullet holes that stay",
     dict(gr_all_difficulties=False, gr_reveal_hidden=False, gr_tier="stock",
          gr_skill=0, gr_decal_pool=120, gr_decal_life="120",
          gr_decal_short=True, gr_decal_everywhere=False, gr_ss_effects=False,
          gr_weather="stock", gr_first_person_body=False,
          gr_extra_cameras=False)),

    ("Split-screen effects",
     dict(gr_all_difficulties=False, gr_reveal_hidden=False, gr_tier="stock",
          gr_skill=0, gr_decal_pool=20, gr_decal_life="stock",
          gr_decal_short=False, gr_decal_everywhere=False, gr_ss_effects=True,
          gr_weather="stock", gr_first_person_body=False,
          gr_extra_cameras=False)),
]

JUNGLE_STORM = [
    ("Stock — nothing patched",
     dict(js_defend_enable=False, js_all_difficulties=False,
          js_reveal_hidden=False, js_skill=0, js_decal_pool=20,
          js_decal_life="stock", js_decal_short=False,
          js_decal_everywhere=False, js_ss_effects=False,
          js_extra_cameras=False)),

    ("Full count on every difficulty",
     dict(js_defend_enable=False, js_all_difficulties=True,
          js_reveal_hidden=False, js_skill=0, js_decal_pool=20,
          js_decal_life="stock", js_decal_short=False,
          js_decal_everywhere=False, js_ss_effects=False,
          js_extra_cameras=False)),

    ("Defend — double the waves",
     dict(js_defend_enable=True, js_defend_recruit=40, js_defend_veteran=50,
          js_defend_elite=70, js_all_difficulties=False,
          js_reveal_hidden=False, js_skill=0, js_decal_pool=20,
          js_decal_life="stock", js_decal_short=False,
          js_decal_everywhere=False, js_ss_effects=False,
          js_extra_cameras=False)),

    ("Defend — last stand",
     dict(js_defend_enable=True, js_defend_recruit=100, js_defend_veteran=140,
          js_defend_elite=200, js_all_difficulties=True,
          js_reveal_hidden=False, js_skill=1, js_decal_pool=20,
          js_decal_life="stock", js_decal_short=False,
          js_decal_everywhere=False, js_ss_effects=False,
          js_extra_cameras=False)),

    ("Brutal — full count, skilled",
     dict(js_defend_enable=True, js_defend_recruit=50, js_defend_veteran=70,
          js_defend_elite=100, js_all_difficulties=True,
          js_reveal_hidden=True, js_skill=2, js_decal_pool=20,
          js_decal_life="stock", js_decal_short=False,
          js_decal_everywhere=False, js_ss_effects=False,
          js_extra_cameras=False)),

    ("Bullet holes that stay",
     dict(js_defend_enable=False, js_all_difficulties=False,
          js_reveal_hidden=False, js_skill=0, js_decal_pool=120,
          js_decal_life="120", js_decal_short=True,
          js_decal_everywhere=False, js_ss_effects=False,
          js_extra_cameras=False)),
]

PRESETS = {
    "r6_3_slus20883": R6_3,
    "graw_slus21422": [],
    "soaf_sles51180": [],
    "ghost_recon_slus20613": GHOST_RECON,
    "jungle_storm_slus20820": JUNGLE_STORM,
}

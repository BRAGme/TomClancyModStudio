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

    ("Waves — light  (~3 enemies per zone)",
     dict(_wave(True, "always", 20, 1, 2), **FX_ON,
          decal_ring=32, bodies="stock")),

    ("Waves — standard  (~5 per zone)",
     dict(_wave(True, "always", 30, 2, 3), **FX_ON,
          decal_ring=64, bodies="15")),

    ("Waves — heavy  (~7 per zone, expect a framerate cost)",
     dict(_wave(True, "always", 60, 3, 4), **FX_ON,
          decal_ring=64, bodies="15")),

    ("Waves — flanking  (feeds from where you are not)",
     dict(_wave(True, "away", 40, 2, 3), **FX_ON,
          decal_ring=64, bodies="15")),

    ("Waves — onslaught  (Shipyard or Alcatraz only)",
     dict(_wave(True, "always", 150, 4, 6), **FX_ON,
          decal_ring=96, bodies="stock")),
]

PRESETS = {
    "r6_3_slus20883": R6_3,
    "ghost_recon_slus20613": [],
    "jungle_storm_slus20820": [],
}

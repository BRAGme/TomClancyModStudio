r"""Named starting points, one list per game.

A preset is not a separate feature -- it just sets the ordinary controls, and
the card badges still say how far each of those has been proven. They exist
because the interesting combinations are combinations: "harder" on these games
means moving four or five things together in the same direction, and anyone
working that out from scratch gets the sign wrong on at least one of them.
(Ghost Recon's accuracy numbers are dispersion, so bigger is worse; Sum of All
Fears' AimFactor is the same; its DelayFactor is a reaction time. Three
adjacent numbers, three different directions.)

Every preset is reachable by hand. None of them turns on an option that the
game itself does not already ship the machinery for.
"""

PRESETS = {
    # -----------------------------------------------------------------
    "ravenshield": [
        ("Tactical realism — quiet, lethal, no HUD", {
            "terro_skill": "hard",
            "footsteps": "quiet",
            "quiet_reloads": True,
            "gunfire_alert": "x0.5",
            "reticule": False,
            "hud": False,
            "radar": False,
            "aim_assist": 0,
        }),
        ("Full house — 50 terrorists on Elite", {
            "terrorists": 50,
            "difficulty": "2",
            "terro_skill": "elite",
            "terro_helmets": "half",
            "terro_nerve": "fanatic",
        }),
        ("Ghost — they barely hear you", {
            "footsteps": "silent",
            "quiet_reloads": True,
            "gunfire_alert": "x0.5",
            "terro_skill": "stock",
        }),
        ("Retuned rifles — steadier and harder-hitting", {
            "weapon_recoil": "half",
            "weapon_accuracy": "tight",
            "weapon_settle": "fast",
            "ammo_damage": "x1.5",
            "weapon_magazines": 2,
        }),
        ("Ammunition actually matters", {
            "ammo_character": "realistic",
        }),
        ("Pick your round or pay for it", {
            "ammo_character": "extreme",
            "terro_helmets": "half",
        }),
        ("Everybody dies fast", {
            "ammo_damage": "x2",
            "ammo_penetration": "max",
            "terro_skill": "hard",
            "terro_helmets": "half",
        }),
        ("Approachable — learning the maps", {
            "difficulty": "0",
            "terrorists": 12,
            "terro_skill": "green",
            "terro_nerve": "timid",
            "aim_assist": 5,
        }),
        ("Stock", {}),
    ],

    # -----------------------------------------------------------------
    "ghost_recon": [
        ("PS2 accuracy — console handling", {
            "weapon_accuracy": "ps2",
            "recoil": "stock",
        }),
        ("Deadly on both sides", {
            "lethality": "brutal",
            "weapon_damage": "x1.5",
            "enemy_skill": "sharp",
            "enemy_armour": "none",
        }),
        ("Armour that actually stops bullets", {
            "armour_works": True,
            "armour_value": "x1.7",
            "enemy_armour": "up",
            "weapon_damage": "x1.5",
        }),
        ("Veteran opposition", {
            "enemy_skill": "sharp",
            "enemy_awareness": "up",
            "enemy_armour": "up",
        }),
        ("Sharpshooter — your guns steady, theirs not", {
            "npc_weapons": True,
            "weapon_accuracy": "tight",
            "recoil": "none",
            "npc_accuracy": "loose",
            "npc_recoil": "double",
        }),
        ("Outgunned — they shoot straighter than you", {
            "npc_weapons": True,
            "npc_accuracy": "tight",
            "npc_damage": "x1.5",
            "npc_mags": 4,
            "enemy_skill": "sharp",
            "weapon_accuracy": "loose",
        }),
        ("Range day — tight weapons, soft enemies", {
            "weapon_accuracy": "tight",
            "recoil": "none",
            "enemy_skill": "green",
            "spare_mags": 6,
        }),
        ("Stock", {}),
    ],

    # -----------------------------------------------------------------
    "soaf": [
        ("Sharpshooter — your guns steady, theirs not", {
            "npc_weapons": True,
            "weapon_accuracy": "tight",
            "recoil": "none",
            "npc_accuracy": "loose",
            "npc_recoil": "double",
        }),
        ("Outgunned — they shoot straighter than you", {
            "npc_weapons": True,
            "npc_accuracy": "tight",
            "npc_mags": 3,
            "enemy_skill": "sharp",
            "weapon_accuracy": "loose",
        }),
        ("Deadly on both sides", {
            "lethality": "brutal",
            "armour_value": "x1.7",
            "enemy_skill": "sharp",
        }),
        ("Wide tiers — Recruit gentle, Elite brutal", {
            "difficulty_curve": "wide",
        }),
        ("Flat tiers — difficulty stops cheating", {
            "difficulty_curve": "flat",
            "enemy_skill": "stock",
        }),
        ("Veteran opposition", {
            "enemy_skill": "sharp",
            "enemy_awareness": "up",
            "enemy_armour": "up",
            "difficulty_curve": "hard",
        }),
        ("Stock", {}),
    ],

    # -----------------------------------------------------------------
    "lockdown": [
        ("Fair fight — enemies shoot like you do", {
            "enemy_accuracy": 55,
            "enemy_damage": "x3",
            "enemy_skill": "up",
            "ai_team_accuracy": 50,
        }),
        ("Hardcore — the game's own co-op numbers", {
            "rainbow_hitpoints": "coop",
            "enemy_accuracy": 35,
            "enemy_damage": "x2",
            "reticule": False,
            "hints": False,
        }),
        ("Unlock the multiplayer kit", {
            "unlock_equipment": True,
            "grenades": "x2",
        }),
        ("Arcade — steady weapons, generous magazines", {
            "recoil": "none",
            "player_sway": "none",
            "magazines": "x2",
            "reserve_ammo": "x2",
            "player_damage": "x1.5",
        }),
        ("Stock", {}),
    ],

    # -----------------------------------------------------------------
    "graw": [
        ("Sharpshooter - your weapon steady, the AI's not", {
            "weapon_side": "player",
            "weapon_spread": "tight",
            "weapon_recoil": "none",
        }),
        ("Outgunned - the AI shoots straighter than you", {
            "weapon_side": "ai",
            "weapon_spread": "tight",
            "weapon_damage": "x1.5",
            "enemy_skill": "sharp",
        }),
        ("Everyone is fragile", {
            "weapon_damage": "x2",
            "enemy_health": "x0.5",
        }),
        ("Marksman - steady and precise", {
            "weapon_spread": "tight",
            "weapon_recoil": "x0.5",
        }),
        ("Arcade - no recoil, deep magazines", {
            "weapon_spread": "laser",
            "weapon_recoil": "none",
            "magazines": "x2",
            "fire_modes": "all",
        }),
        ("Unwieldy - everything harder to hold", {
            "weapon_spread": "loose",
            "weapon_recoil": "x1.5",
            "magazines": "x0.5",
        }),
        ("Full-strength opposition", {
            "enemy_squads": "full",
        }),
        ("Veteran enemies - better, not more", {
            "enemy_skill": "sharp",
            "enemy_health": "x2",
        }),
        ("Overrun - more of them, and sharper", {
            "enemy_squads": "full",
            "enemy_skill": "sharp",
        }),
        ("Stealth is worth it", {
            "enemy_senses": "dull",
            "enemy_squads": "full",
        }),
        ("Thinned out - a gentler campaign", {
            "enemy_squads": "thin",
            "enemy_skill": "green",
            "enemy_health": "x0.5",
        }),
        ("Stock", {}),
    ],

    # -----------------------------------------------------------------
    "vegas": [
        ("Room by room — gunfire does not carry", {
            "gunfire_radius": "x0.25",
            "difficulty": "GAMEDIFFICULTY_ELITE",
        }),
        ("Hardcore — one life, no help", {
            "difficulty": "GAMEDIFFICULTY_ELITE",
            "hunt_respawn": False,
            "aim_assist": False,
            "civilian_limit": 1,
        }),
        ("Crowded hunt", {
            "hostile_density": "GAMEHOSTILEDENSITY_HIGH",
            "hunt_respawn": True,
            "round_gap": 5,
        }),
        ("Run and gun", {
            "movement_spread": "none",
            "accuracy": "tight",
            "weapon_bob": False,
            "camera_shake": False,
        }),
        ("Lethal — everybody dies faster", {
            "weapon_damage": "x2",
            "accuracy": "tight",
        }),
        ("Stock", {}),
    ],
}

#: The two Advanced Warfighter games share an engine, a data layout and an
#: option list, so they share their presets too.
PRESETS["graw2"] = PRESETS["graw"]

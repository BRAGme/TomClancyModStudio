"""Starting points -- a few useful combinations per game, in a sensible order.

Every preset writes only keys that exist on that game's own pages, so choosing
one sets those controls and leaves everything else where you had it. The first
entry on every list is always the one that puts the game back to stock, because
the quickest way to undo an experiment is to pick it and apply again.

The names describe what you get, not how hard it is. "Everybody turns out" is
the difficulty-flag strip; "Ghosts" is the full realism stack.
"""

# ---------------------------------------------------------------------------
# Ghost Recon and Island Thunder -- the same options under two prefixes
# ---------------------------------------------------------------------------

def _rse(p):
    stock = {p + "all_difficulties": False, p + "reveal_hidden": False,
             p + "tier": "stock", p + "skill": 0, p + "accuracy": 0,
             p + "lethality": "stock", p + "spot": 100,
             p + "ally_mag": 100, p + "ally_rate": 100, p + "ally_recoil": 100,
             p + "ally_spread": 100, p + "enemy_mag": 100, p + "enemy_rate": 100,
             p + "enemy_recoil": 100, p + "enemy_spread": 100}

    def mix(**kw):
        out = dict(stock)
        out.update({p + k: v for k, v in kw.items()})
        return out

    return [
        ("Stock -- nothing changed", dict(stock)),

        ("Everybody turns out  (full force at every difficulty)",
         mix(all_difficulties=True)),

        ("Everybody turns out, and they are veterans",
         mix(all_difficulties=True, tier="up1")),

        ("Lethal  (two or three hits either way)",
         mix(lethality="much_deadlier", accuracy=1)),

        ("Ghosts  (full force, elite, lethal, and they see you coming)",
         mix(all_difficulties=True, reveal_hidden=True, tier="elite", skill=1,
             accuracy=2, lethality="much_deadlier", spot=160)),

        ("A softer campaign",
         mix(tier="down1", lethality="much_tougher", spot=70,
             enemy_spread=160, ally_mag=200)),

        ("Range day  (your weapons only)",
         mix(ally_mag=300, ally_rate=150, ally_recoil=25, ally_spread=50)),
    ]


# ---------------------------------------------------------------------------
# Ghost Recon 2 and Summit Strike
# ---------------------------------------------------------------------------

def _gr2(p):
    stock = {p + "lethality": "stock", p + "all_mag": 100, p + "all_rate": 100,
             p + "all_recoil": 100, p + "all_spread": 100,
             p + "invuln": 0, p + "difficulty": "stock"}
    for tag in ("friendlyfirelethal", "arcademode", "aibackup",
                "firstpersononly", "threatindicator", "allowobservers",
                "weaponswappingallowed", "randomzones"):
        stock[p + "rule_" + tag] = "stock"

    def mix(**kw):
        out = dict(stock)
        out.update({p + k: v for k, v in kw.items()})
        return out

    return [
        ("Stock -- nothing changed", dict(stock)),

        ("Lethal  (bodies stop soaking up magazines)",
         mix(lethality="much_deadlier")),

        ("Realism  (lethal, friendly fire on, no threat indicator)",
         mix(lethality="much_deadlier", rule_friendlyfirelethal="TRUE",
             rule_threatindicator="FALSE", all_spread=130)),

        ("First person, every mode", mix(rule_firstpersononly="TRUE")),

        ("Multiplayer with AI and random zones",
         mix(rule_aibackup="TRUE", rule_randomzones="TRUE", invuln=10)),

        ("Tanky  (long firefights)",
         mix(lethality="much_tougher", all_mag=200)),
    ]


# ---------------------------------------------------------------------------
# The Unreal-engine three
# ---------------------------------------------------------------------------

def _r6(p, templates=True):
    stock = {p + "terro_skill": "stock", p + "terro_react": "stock",
             p + "sight": "stock", p + "terro_speed": "stock",
             p + "terro_wounds": "stock", p + "player_wounds": "stock",
             p + "squad_speed": "stock", p + "ammo": "stock",
             p + "unlimited_teammate_ammo": "stock",
             p + "falling_damage": "stock", p + "zoom": "stock",
             p + "sensitivity": "stock", p + "reload": "stock",
             p + "ragdoll": "stock", p + "blood": "stock",
             p + "tracers": "stock", p + "texture_lod": "stock",
             p + "gore": "stock", p + "game_speed": 100, p + "console": "stock"}
    for who in ("chavez", "price", "loiselle", "weber"):
        stock[p + "cheat_" + who] = "stock"
    if templates:
        stock[p + "tpt_skill"] = 100
        stock[p + "grenades"] = 0

    def mix(**kw):
        out = dict(stock)
        out.update({p + k: v for k, v in kw.items()})
        return out

    out = [
        ("Stock -- nothing changed", dict(stock)),

        ("Sharper picture  (full-resolution textures)",
         mix(texture_lod="full")),

        ("Tango Hunt  (they are faster, sharper and react at once)",
         mix(terro_skill="more", terro_react="less", terro_speed="little_more",
             sight="little_more")),

        ("One-shot world  (everybody dies quickly, you included)",
         mix(terro_wounds="less", player_wounds="less", terro_react="less")),

        ("A gentler run",
         mix(terro_skill="less", terro_react="much_more", player_wounds="more",
             ammo="more", falling_damage="off")),

        ("Cinematic  (full textures, heavy ragdolls, long tracers)",
         mix(texture_lod="full", ragdoll="more", tracers="more", blood="more")),

        ("Every operator is invulnerable",
         mix(cheat_chavez="true", cheat_price="true", cheat_loiselle="true",
             cheat_weber="true")),
    ]
    if templates:
        out.insert(4, ("Grenadiers  (a fifth of them carry one, and they are "
                       "better shots)",
                       mix(grenades=20, tpt_skill=130)))
    return out


def _graw():
    out = _r6("graw_", templates=False)
    extra = {"graw_team_skill": "stock", "graw_team_spread": "stock",
             "graw_team_zones": "stock", "graw_team_ai": "stock",
             "graw_enemy_harm": "stock", "graw_enemy_delay": "stock",
             "graw_enemy_scatter": "stock", "graw_enemy_grenades": "stock",
             "graw_bcd": "stock"}
    for _name, values in out:
        for k, v in extra.items():
            values.setdefault(k, v)
    out.append(("Competent teammates  (they shoot straight and range wider)",
                dict(out[0][1], graw_team_skill="much_more",
                     graw_team_spread="less", graw_team_zones="little_more")))
    out.append(("Mexico hurts  (enemy damage and reactions up, difficulty "
                "director aiming higher)",
                dict(out[0][1], graw_enemy_harm="little_more",
                     graw_enemy_delay="less", graw_enemy_scatter="less",
                     graw_bcd="little_more")))
    return out


PRESETS = {
    "ghost_recon_xbox": _rse("gr_"),
    "island_thunder_xbox": _rse("it_"),
    "ghost_recon2_xbox": _gr2("gr2_"),
    "summit_strike_xbox": _gr2("ss_"),
    "rainbow_six_3_xbox": _r6("r63_"),
    "black_arrow_xbox": _r6("ba_"),
    "graw_xbox": _graw(),
}

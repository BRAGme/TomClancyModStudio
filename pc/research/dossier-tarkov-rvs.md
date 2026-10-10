# Tarkov's mechanics in Rainbow Six 3 — what works, what cannot, and in what order

Brief: play Escape from Tarkov's gunplay — limb damage, bleeding, fractures —
on Rainbow Six 3's maps, against Rainbow Six 3's own terrorist AI first.

Targets on the machine this was written for:
`E:\SteamLibrary\steamapps\common\Escape from Tarkov` and
`D:\SteamLibrary\steamapps\common\Rainbow Six 3 Gold`.
**Nothing in either folder was read or written to produce this.** Everything
below comes from `research/dossier-rs3.md` (which was produced by reading the
Raven Shield install), from OpenRVS's published source, and from published
figures. One of those two folders turns out not to be needed at all, which is
the first finding.

Confidence key, same as the Raven Shield dossier: **V** verified by reading
real bytes or real source this session; **L** likely — structure verified,
semantics inferred; **G** explicit guess.

---

## Headline

**The direction has to be Tarkov's mechanics into Raven Shield, not Raven
Shield's maps into Tarkov.** That is not a preference. The reverse is closed:

| | Escape from Tarkov | Rainbow Six 3: Raven Shield |
|---|---|---|
| Engine | Unity, 2017+ | Unreal Engine 2, package v118/14 **(V)** |
| Authority | server-side: health, ballistics and hit registration are decided by BSG **(V, by design)** | local **(V)** |
| Anti-cheat | BattlEye, kernel-level | none |
| Mod API | none | `ucc.exe` ships in `system\`, and the mod descriptor exposes four class pointers **(V)** |
| Map format | not importable | `.rsm`, and we do not need to touch it |

So the maps stay where they are. Raven Shield's 15 campaign maps plus the
expansions' are *already* the maps; the job is to move Tarkov's medical model
onto them. Which is the right half to move anyway — limb damage, bleeds and
fractures are what makes a Tarkov room feel the way it does, and they are the
part that is pure rules rather than content.

**The second finding is that most of it is already reachable.** Raven Shield
exposes exactly the four class pointers a health model needs to replace, and
there is a verified way to replace them without editing a single retail file.

---

## Where `universal-modder` fits, and where it does not

[`rehan-remade/universal-modder`](https://github.com/rehan-remade/universal-modder)
is a toolkit that lets an AI coding agent mod a PC game: twelve engine
playbooks (Unreal among them), a knowledge base of field notes, reverse-
engineering tooling (ILSpy, Cpp2IL, Ghidra, Frida, UE4SS, BepInEx), game
automation for launching and screenshotting and sending input, and fal-backed
generation for sprites, 3D, audio and video.

Two honest observations about using it here.

**It rules out the Tarkov side itself.** Its stated rules refuse to inject
into online games with anti-cheat and refuse to bypass anti-cheat or DRM. That
is the same conclusion the table above reaches, arrived at independently —
which is a good sign about the toolkit and a definitive one about the
direction.

**On the Raven Shield side its strongest contribution is the loop, not the
analysis.** The analysis is already done and better than a generic Unreal
playbook could manage: `research/dossier-rs3.md` has the package format at
byte level, 197 weapon and 61 ammunition classes with offsets, the config-
variable census, and the mod-discovery mechanism. What is genuinely missing
from this repository is everything after the edit — launch the game, get in a
firefight, screenshot the result, read it back, iterate. That is exactly what
universal-modder's game-automation and in-game-agent-bridge skills are for,
and it is the bottleneck: every option in `pc/` is badged *untested* for want
of somebody watching the game.

Its UE4SS/BepInEx tooling does not apply — those are for Unreal 4/5 and Unity.
Unreal Engine 2 is modded with its own compiler, which is simpler.

---

## The four ways into Raven Shield, and which one to use

| Route | Mechanism | Reaches | Verdict |
|---|---|---|---|
| 1. `config` ini keys | 260 `config` variables in `Engine.u` alone | HUD, noise model, difficulty, counts | **V** — already what `tcpc/games/ravenshield.py` uses |
| 2. `.u` class defaults | tagged property lists, rewritten in place at identical width | weapon and ammunition statistics | **V** — already what `tcpc/upackage.py` does |
| 3. **`ServerActors` + a script package** | `[Engine.GameEngine] ServerActors=`, an actor that rewrites the live mod's class pointers at `PreBeginPlay` | **pawn, AI, player controller, HUD** | **V** — OpenRVS's `OpenRenderFix/classes/OpenFix.uc` does precisely this |
| 4. `Mods\*.mod` descriptor | the same four pointers, named directly in text | same as route 3 | **V** — `Mods\RavenShield.mod` lines 15-22 |

Route 3 is the one. It is two lines in an ini, it *stacks* on whatever mod is
already running instead of replacing it, and uninstalling is deleting the two
lines. OpenRVS's own fix is proof the mechanism works on a real install:

```unrealscript
// OpenRenderFix/classes/OpenFix.uc -- GPL-3.0, quoted as evidence of the
// mechanism, not as code to reuse.
s = caps(class'Actor'.static.GetModMgr().m_pCurrentMod.m_GlobalHUDToSpawn);
if ( ( s == "" ) || ( s == "R6GAME.R6HUD" ) )
    class'Actor'.static.GetModMgr().m_pCurrentMod.m_GlobalHUDToSpawn = "OpenRenderFix.OpenRender";
```

The four pointers, with their stock values from `Mods\RavenShield.mod` **(V)**:

```
m_DefaultLightPawn=R6Characters.R6RainbowLight      the health model
m_DefaultMediumPawn=R6Characters.R6RainbowMedium
m_DefaultHeavyPawn=R6Characters.R6RainbowHeavy
m_DefaultRainbowAI=R6Engine.R6RainbowAI             teammate AI
m_PlayerCtrlToSpawn=R6Engine.R6PlayerController     input and commands
m_GlobalHUDToSpawn (stock blank, falls back to R6Game.R6HUD)
```

Terrorists are **not** in that list. Their pawn class is named in the AI
templates — `template\*.tpt` carries weighted `NNN, Package.Class` pool lines
**(V)** — so swapping the terrorist body is a text edit to 218 template files,
which is an edit kind `tcpc` already has. That is the key to the brief's "the
regular RS3 enemy AI first": replacing the terrorist *pawn* leaves
`m_DefaultRainbowAI` and every AI template skill, personality and reaction
timer exactly as shipped. You change the body, not the brain.

---

## Mechanic by mechanic

What Tarkov does, what it would take here, and where it stands.

| Tarkov mechanic | Route | Status |
|---|---|---|
| **Seven zone health pools**, 35/85/70/60/60/65/65 = 440 | script: pawn subclass + an owned `Info` | **written** — `mods/TarkovRvS/Classes/TarkovHealth.uc` |
| **Head or thorax at zero is death** | same | written |
| **Blacked limb; damage on it transfers to thorax** | same | written, transfer coefficients **G** |
| **Light and heavy bleeding** | same, ticked | written; rates are the published *Arena* figures, **L** for live |
| **Fractures, limbs only** | same | written, chance **G** |
| **Vital bled to zero leaves you one hit from dead** | same | written **(V** that the rule exists**)** |
| **Bandage / tourniquet / splint / surgical kit / painkillers, with use times, interrupted by being hit** | script: console commands on the controller subclass | written |
| **Limp from a damaged leg** | `Pawn.GroundSpeed`, a standard UE2 property | written |
| **Aim penalty from a damaged arm** | — | **not reachable yet.** Raven Shield's weapon sway is native and no script-side hook for it is known |
| **Limb panel HUD** | script: `R6HUD` subclass, text | written; declined automatically when another mod owns the HUD |
| **Damage spread across calibres** | `.u` class defaults, `m_iEnergy` | **shipped in the tool** — `tcpc/games/_rs3_tarkov.py` |
| **Recoil and sway discipline** | `.u`, `m_stAccuracyValues` | shipped in the tool |
| **Armour class versus penetration power** | script, needs the round's class at the hit | **open.** See below |
| **No crosshair, no radar** | `config` ini keys | already in the tool (`reticule`, `radar`, `hud`) |
| **Energy, hydration** | script, would need new HUD and consumables | out of scope |
| **Looting, inventory, insurance, raids, extraction** | — | out of scope: that is the *game* Tarkov is, not the mechanic |

### The one finding worth the whole ballistics option

Raven Shield's damage term is muzzle **energy**. Tarkov's is **wound damage**.
They do not have the same shape:

| | 9mm | 5.56 | 7.62x39 | 7.62x51 | 7.62x54R |
|---|---|---|---|---|---|
| Raven Shield `m_iEnergy` **(V)** | 567 | 1442 | 1008 | 2547 | 4008 |
| Tarkov damage **(V** for all five**)** | 54 | 54 | 61 | 80 | 81 |

Raven Shield's spread is **7.1x**; Tarkov's is **1.5x**. That is a units
disagreement, not a balance disagreement — muzzle energy goes up with the
square of velocity and what a bullet does to a person does not. It is also the
mechanical reason a rifle round in Raven Shield kills in one hit while in
Tarkov it takes two to the chest, and therefore the reason a limb model
dropped into stock Raven Shield would never get to matter: everything
one-shots, so there is nowhere new to aim.

Scaling every calibre to 10.5 energy per point of Tarkov damage — 9mm's own
stock ratio, 567/54, so 9mm is the fixed point and nothing gets stronger
except buckshot — gives:

| Calibre | Scale | | Calibre | Scale |
|---|---|---|---|---|
| 9mm Parabellum | **1.00** | | 7.62x39mm | 0.64 |
| 9x21mm | 0.98 | | 5.45x39mm | 0.43 |
| 9x39mm SP-6 | 0.97 | | 5.56x45mm | 0.39 |
| 5.7x28mm | 1.01 | | 7.62x51mm | 0.33 |
| .45 ACP | 1.04 | | 7.62x54mmR | 0.21 |
| .50 AE | 0.65 | | 12 gauge slug | 0.54 |
| .338 / .50 BMG | 0.26 / 0.18 | | 12 gauge buckshot | **1.76** |

**Every pistol and PDW calibre in the game is already Tarkov-shaped** — five of
them inside five percent, so the option emits no edit for them at all. What is
out of shape is the rifles. And buckshot is the one round in Raven Shield that
Tarkov rates *higher*, which is the correct answer: shotguns shred the
unarmoured.

The converted spread is 3.15x, which is exactly Tarkov's own spread over the
same calibres. `tests/run_tests.py` asserts that equality, and asserts every
stock figure in the table against `research/rs3_ammo.csv` — the dataset
produced by reading the packages — so the table cannot drift from the game.

**Penetration is deliberately not touched.** `m_iPenetrationFactor` is a
DIVISOR and the shipped values are already right; `_rs3_ammo.py` documents how
that was learned the hard way. Tarkov's penetration-versus-armour-class model
is the most Tarkov thing there is and the ini/`.u` lever is the wrong lever for
it. It belongs in the script, where armour can be read per hit — if it can.

---

## Open questions, and the one command that answers each

Five things are not known, and four of them fail loudly rather than quietly,
which is the only reason the mod could be written at all before they were
resolved.

1. **`R6TakeDamage`'s argument list.** That it is the per-pawn damage entry
   point is the Raven Shield modding community's position **(L)**; the five
   arguments are the Unreal Engine 2 standard **(G)**. A mismatch is a compile
   error that prints the real signature. → `make.bat`
2. **The terrorist pawn class name.** Not in any descriptor; it is in the
   templates. → `tools\rs3_probe.py <game> --pawns`
3. **What posture variable Raven Shield uses.** Zone resolution is geometric
   and the vertical bands collapse on a prone body. The detection hook is
   written and returns `False` until this is known. →
   `tools\rs3_probe.py <game> --grep "prone|crouch|posture|stance"`
4. **Whether armour is reachable from script at all.** The community's
   position is that it is native **(L)**. If any of it is a class default it is
   reachable, and Tarkov armour classes come back on the table. →
   `tools\rs3_probe.py <game> --grep "armor|armour|protect|resist"`
5. **What `DamageScale` should be** — whether the hook receives raw energy or
   something native armour already reduced. This one cannot be read off a
   file, so it is measured in game: `TarkovDebugDamage 1`, take one 9mm round,
   and the scale is 54 divided by what it prints. Thirty seconds.

`tools\rs3_probe.py` with no flags answers 2, 3 and 4 in one run. It reads;
it has no argument that could write.

---

## The order to do this in

**Tonight, no compiler.** In Mod Studio: *Tarkov ballistics* → "Tarkov's
damage spread", *Tarkov weapon handling* → "Tarkov", crosshair and radar off,
aim assist 0. The preset **"Tarkov — the ballistics and the handling"** is
those five settings. Terrorist hunt on a map you know well. What you should
notice: rifle fights last two or three hits instead of one, moving and
shooting stops working, and the shotgun becomes frightening. What you will
*not* get is anywhere new to aim — that is the next step, and feeling its
absence is a good way to understand why it is the step that matters.

**Then the probe.** `python tools\rs3_probe.py "D:\SteamLibrary\steamapps\common\Rainbow Six 3 Gold"`.
It answers three of the five open questions and takes seconds.

**Then build the health model.** `mods\TarkovRvS\make.bat "<game>"`, fix the
one or two signatures the compiler complains about, install the two
`ServerActors` lines, calibrate `DamageScale`, and play. Player side only at
first — the terrorists are still stock bodies with stock AI, which is a useful
asymmetry to test against: you bleed, they do not.

**Then the terrorists.** Rename the template class with the name the probe
found, rebuild, and point `template\*.tpt` at it. Raven Shield's own AI keeps
driving them.

**Then armour**, if question 4 came back positive. This is where Tarkov's
identity actually lives and it is the right thing to want next.

---

## Sources

Read this session:

* `research/dossier-rs3.md` and `research/rs3_ammo.csv` in this repository —
  the Raven Shield package format, the four tiers, the ammunition figures.
* [OpenRVS](https://github.com/OpenRVS-devs/OpenRVS), GPL-3.0 — read as an API
  reference for real class names and the server-actor injection route. No code
  from it is reused; `mods/TarkovRvS` is written from scratch and is not a
  derivative work.
* [`rehan-remade/universal-modder`](https://github.com/rehan-remade/universal-modder) — README and stated rules.
* [Raven Shield SDK and modding guides, ModDB](https://www.moddb.com/mods/raven-shield-software-development-kit) —
  the `R6TakeDamage` lead, and that armour is largely native.
* [Intro to Modding, Raven Shield wiki](https://ravenshield.fandom.com/wiki/Intro_to_Modding_1_-_Tools_and_File_Types) —
  `ucc`, `.uc` in a `Classes` folder, UTPT.
* Tarkov figures: [Arena health system](https://arena.tarkov.com/support/knowledge/532)
  (zone pools, bleed rates, the fracture and vital rules),
  [tarkovguide.net ammo chart](https://www.tarkovguide.net/ammo) and
  [kappaguide ammo guide](https://kappaguide.com/blog/ammo-guide)
  (damage and penetration per round). Of the fifteen calibre figures used,
  five are confirmed against those charts and ten are inferred; the table
  marks which.

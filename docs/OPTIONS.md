# Every option, and how far it has been proven

Badges on each card mean:

* **verified in game** — watched working in the running game
* **written and read back** — the edit lands in the file correctly; nobody has
  observed the effect
* **untested** — reasoned from the data, never run
* **not working** — shipped visible and disabled, with the reason on the card

As of this build, **nothing is "verified in game"**. Everything below is
"untested" except Lockdown's `options.xml` toggles and Raven Shield's weapon and
ammunition options, which are "written and read back" -- for the latter the
read-back is unusually strong, because the values are compared against three
independently produced datasets covering 3,046 offsets and values, and the
written packages are checked to be the same length with every changed byte
inside a property value. The formats, the values and the round-trips are all checked by
`tests\run_tests.py` against the real games; what has not happened is somebody
launching each game and watching each option do what it says.

Run `python ModStudio.py --cli show "<game folder>"` for the current list with
defaults and ranges, which is generated from the profiles and so cannot drift
from them.

## The shape of each game's catalogue

**Raven Shield** — Game modes (the four cut modes, which modes each map
allows, a shipped class-name typo), Difficulty (terrorist count, difficulty level, AI backup,
friendly fire), AI templates (competence across eight skill stats, the six-way
personality mix, helmets), Stealth (footstep audibility per posture, gunfire
alert radius, quiet reloads), Interface (crosshair, radar, the seven HUD
elements, aim assist, corpses, field of view), Weapons (recoil, accuracy in all
five stances, reticule settle time, extra magazines) and Ammunition (bullet
damage, penetration, and whether the loadout menu's stat bars are rewritten to
match what was changed).

The last two groups are the only ones in the whole tool that write binary: they
patch class defaults inside Raven Shield's compiled `system\*.u` packages at
identical width. See section 7 of `docs/FORMATS.md`.

**Ghost Recon** — Enemies (marksmanship and the other three skill rungs, body
armour, whether multiplayer enemies are included), Lethality (the seven
hit-location factors), Weapons (dispersion including a PS2-like setting, recoil,
magazines, spare magazines).

**Sum of All Fears** — the same, plus Difficulty (the eleven-tag tier model
Ghost Recon does not have) and how much body armour helps.

**Lockdown** — Difficulty (enemy marksmanship, enemy damage, enemy skill, squad
accuracy floor, whether enemies deliberately miss), Rainbow (the shipped co-op
hitpoints, wound penalties, sway), Weapons (damage, magazines, ammunition,
recoil), Equipment (unlock the six multiplayer-only items, grenade counts,
explosive power), Interface (crosshair, hints, camera shake, blood, bodies, and
two of the thirteen developer readouts that ship live).

**GRAW and GRAW 2** — Weapons (spread, recoil, magazine capacity, every fire
mode, rate of fire) and Enemies (squad size, marksmanship, global accuracy,
toughness, how far they see and hear). GRAW 2 adds its HUD colour scheme.

The squad-size option is the unusual one and worth understanding before you use
it. Advanced Warfighter's world files place SQUADS, not soldiers, and the
squad's size is the digit on the end of the name it references —
`mex_guerilla_patrol2` is that patrol cut to two men. So "more enemies" is a
rename rather than a number, and the tool only ever renames to a size the game
itself generates. It changes how many spawn without moving anybody: positions,
patrol routes and mission triggers are untouched.

Measured on the real campaigns: mission 1 goes 45 → 83 in GRAW 1 and
46 → 212 in GRAW 2, the difference being that GRAW 2's patrol squads hold
eight men where GRAW 1's hold four.

Note that each of these writes TWO files: the source XML and its compiled twin.
The retail engine reads the twin, so an edit that only touched the source would
do nothing at all.

**Vegas** — Rules (difficulty, terrorist-hunt population, civilian limit, hunt
respawning, round gap, the unused co-op leash), Weapons (damage by range,
accuracy, movement and turning spread, suppressor penalty), Feel (aim assist,
field of view, camera shake, weapon bob, squad spacing).

## Where the shipped data is simply wrong, and the tool says so

* **Raven Shield's two ammunition types differ in three ways the game never
  explains — and in none of the ways you would guess.** `R6Bullet` defaults its
  bullet type to `JHP` and the 33 ball classes override it to `FMJ`: a hollow
  point that hits a person is deactivated on the spot, while a ball round with
  energy left keeps flying and can hit the man behind. `m_iPenetrationFactor`
  is a **divisor**, so ball's inherited 1 against hollow point's 4 gives ball
  four times the budget — it goes through doors hollow point bounces off. And
  a hollow-point kill staggers harder (0.5 against 0.25).

  What they genuinely do NOT differ in is **damage and range**: the same number
  in 32 of the 33 calibres. "What the two ammunition types do" adds that
  contrast, and deliberately leaves penetration alone.

  This documentation previously said the opposite — that the rounds were
  undifferentiated and the penetration field ran backwards — and an option
  built on that reading would have made ball ammunition worse at the one
  thing it is already best at. Both are corrected.

## Options shipped visibly DISABLED, with the reason on the card

Two Advanced Warfighter options were found to do nothing and are shipped off
rather than quietly inert:

* **Global enemy accuracy** (both games). `apply_difficulty_settings` assigns
  `overall_enemy_precision` a literal on every difficulty tier including
  Normal, and runs every session — at profile load in the first game, at
  network init in the second. Whatever the file says is overwritten before it
  is read. Both games keep the variable in that same compiled script and
  nowhere else, which is how it was caught.
* **How far enemies see and hear** (Advanced Warfighter 2 only). The sequel's
  compiled scripts contain not one reference to any `ad_` key; the first
  game's `aidetection.dxe` does. The sequel uses a different family (`det_*`,
  108 references). The `ad_` keys are still in its data, which is exactly why
  this looked like it worked.

## Corrections to options that shipped wrong

* **Advanced Warfighter "Enemy marksmanship" ran backwards.** `skill_shooting`
  is a SPREAD, so a lower number is a better shot. The game's own ladder:
  GRAW 1 gives the boss `mex_carlos` 0.30, special forces 0.85, regular
  infantry 1.00 and guerillas 1.20; GRAW 2 gives the eight special-forces
  leaders 2.0 and all 124 other soldiers 2.5. "Elite" had been doubling the
  number. A test now rebuilds that ladder from the compiled data and asserts
  the option scales the same way the game's own tiering does.
* **Ghost Recon's "also apply to multiplayer and co-op enemies" hit the wrong
  side**, and was on by default. It pointed at `Actor\MP Actor Files\`, which
  holds the PLAYER's four multiplayer classes. The real script-spawned enemies
  are `opposing_force_*` in the Actor root and were already covered. Removed.
* **Sum of All Fears' enemy options reached 49 friendlies** — eleven support
  teams and a hostage — because "enemy" was scoped to a folder. An enemy is
  now an actor with no `<KitPath>`, which is a content test.
* **Lockdown's "enemies deliberately miss you" was half-written.** It set
  `ForcedMiss` but left `AdjustForcedMissSingleShot/Burst/FullAuto` at
  25/20/10; the game's own never-miss configuration sets all four.

## Where an option deliberately does less than its name suggests

* **Raven Shield "Difficulty level"** is a reaction timer, not a competence
  setting. The game's own text says so: on Elite, terrorists take less time
  before shooting. For competence, use the AI template options.
* **Vegas "Default difficulty"** sets which tier you start on. It does not
  change what a tier *means*, because that lives in cooked packages this tool
  does not edit.
* **"Weapon accuracy" moves both sides by default** in Ghost Recon and Sum of
  All Fears, because both sides read the same weapon files. Turning on **"Give
  the enemy its own weapons"** separates them, and the option then applies to
  the player's set alone. The two games need different mechanisms:
  * *Ghost Recon* separates by folder — the enemy's kits are loose in `Equip\`
    and the player's under `Kits\`, no path in common — so its 27 enemy kits
    are shadowed to point at `<weapon>_npc.gun` copies. Five of the thirteen
    guns the enemy carries are shared with the player.
  * *Sum of All Fears* has no enemy kit folder. 239 enemy placements wear
    `Kits\mercenaries\` kits, which are shadowed; 176 wear `multi_NN`
    loadouts out of the player's own `Kits	eam\`, which are **copied** and
    the campaign missions rewritten to name the copies. Safe because not one
    allied placement in 25 missions wears a borrowed loadout. **Nineteen** of
    the twenty-two guns the enemy carries are shared with the player here, so
    the split matters considerably more.
  * *Lockdown needs no split at all* — it ships one. 42 `e_*.gun` enemy
    weapons, each paired 1:1 with a player twin, and not one enemy-only
    weapon. The two sides were separate all along, so the work there was
    exposing the enemy half: every one of the 42 carries an identical
    `Common/AIAccuracy` model (base 15, recoil −5, movement −10/−20/−30,
    blind fire −30/−40) of which the tool previously touched one number.
  * One seam in each of the two Red Storm games, and it is the same seam: a single kit carried by both a
    few friendly NPCs and by enemies — `m1911 only.kit` in Ghost Recon,
    `m9_only.kit` in Sum of All Fears — so those friendlies get the enemy's
    pistol. Nothing in the file layout tells them apart.
* **Lockdown "Wounds spoil your aim"** switches on six values that ship at
  zero. Nothing in the data proves the engine still reads them.
* **Raven Shield "Friendly fire"** is multiplayer only. There is no
  single-player equivalent key.
* **Raven Shield's weapon and ammunition options** cannot switch a property ON
  that a weapon does not already carry. Unreal serialises a property only where
  it differs from its class default, so adding one would move every byte after
  it and invalidate the export table. Every weapon the loadout menu offers is
  still reached, through its own defaults or a parent's.
* **Raven Shield "Keep the loadout menu honest"** is a proportional mirror, not
  the game's own formula. The bars are authored percentages that clamp at 100,
  so several weapons sit at full once recoil is heavily reduced, and a bar
  already at 0 stays at 0.

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

**Raven Shield** — Difficulty (terrorist count, difficulty level, AI backup,
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

## Where an option deliberately does less than its name suggests

* **Raven Shield "Difficulty level"** is a reaction timer, not a competence
  setting. The game's own text says so: on Elite, terrorists take less time
  before shooting. For competence, use the AI template options.
* **Vegas "Default difficulty"** sets which tier you start on. It does not
  change what a tier *means*, because that lives in cooked packages this tool
  does not edit.
* **Ghost Recon "Weapon accuracy"** moves both sides, because both sides read
  the same weapon files. Separating them needs the `_npc.gun` technique — see
  `docs/FORMATS.md`.
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

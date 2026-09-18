# Every option, and how far it has been proven

Badges on each card mean:

* **verified in game** — watched working in the running game
* **written and read back** — the edit lands in the file correctly; nobody has
  observed the effect
* **untested** — reasoned from the data, never run
* **not working** — shipped visible and disabled, with the reason on the card

As of this build, **nothing is "verified in game"**. Everything below is
"untested" except Lockdown's `options.xml` toggles, which are "written and read
back". The formats, the values and the round-trips are all checked by
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
elements, aim assist, corpses, field of view).

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

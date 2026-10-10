# TarkovRvS — Tarkov's health model inside Raven Shield

UnrealScript source for a drop-in Raven Shield mod that replaces the game's
hit-points with Escape from Tarkov's: seven body zones totalling 440 points,
light and heavy bleeding, fractures, destroyed limbs that pass damage to the
chest, and bandages, tourniquets, splints, surgical kits and painkillers with
use times that a round landing on you cancels.

Raven Shield's own AI still drives the terrorists. Nothing about their brains
changes — only what happens when you shoot one, and what happens when one
shoots you.

**This is source, not a build.** It is not part of the Python tool in `pc/`;
it is a separate thing that happens to live in the same repository, because
the research that made it possible is in `pc/research/dossier-rs3.md`. Nothing
here has been compiled or run. See **How far this has actually been proven**.

---

## Why this direction and not the other one

The obvious reading of "Tarkov in Raven Shield maps" is to put the maps into
Tarkov. That does not work, and it is worth being exact about why rather than
discovering it over a weekend:

* Escape from Tarkov is server-authoritative. Health, ballistics and hit
  registration are decided on BSG's servers, so a client-side map or mechanic
  has nothing to attach to.
* It ships with BattlEye and no mod API. There is no supported extension
  point, and defeating an anti-cheat to make one is both the thing we will not
  help with and a ban.
* There is no map format to import into.

Raven Shield is the opposite of all three: a 2003 Unreal Engine 2 game with
`ucc.exe` in its own `system` folder, class defaults sitting in plain tagged
property lists, and four class pointers in a text descriptor that decide which
pawn, AI, controller and HUD the game runs.

So the maps stay where they are and the *mechanics* move. You end up playing
Raven Shield's maps with Tarkov's medical model — which is the part of Tarkov
that actually changes how a room feels.

---

## What is in here

| File | What it is |
|---|---|
| `Classes/TarkovConfig.uc` | Every number, as `config` variables. No balance figure is compiled in. |
| `Classes/TarkovZones.uc` | Which of the seven zones a hit landed in, from geometry alone — no bone names needed. |
| `Classes/TarkovHealth.uc` | The state machine: pools, bleeds, fractures, blackouts, the medical kit. |
| `Classes/TarkovPawn{Light,Medium,Heavy}.uc` | The player's three armour classes, with the damage hook. |
| `Classes/TarkovController.uc` | `TkBandage`, `TkTourniquet`, `TkSplint`, `TkSurgery`, `TkPills`, `TkStatus`. |
| `Classes/TarkovHUD.uc` | The limb panel. |
| `Classes/TarkovInjector.uc` | How it all gets loaded: one server-actor line. |
| `Classes/TarkovTerrorist.uc.template` | Enemies. Not compiled — one class name has to be confirmed first. |
| `TarkovRvS.ini` | The config file, with the defaults written out and commented. |
| `TarkovRvS.mod` | The fallback install route. |
| `make.bat` | Builds `TarkovRvS.u` with the game's own compiler. |

## The design in one paragraph

The pawn's damage hook does not deal damage. It asks `TarkovHealth` what the
hit means, and then calls the native damage path with either one point (so the
game's own flinch, hit sound and stagger still play — and then the native
health figure is put straight back) or a lethal figure (so the game's own
death, animation, scoring and mission logic all run untouched). Nothing in the
engine has to know a limb model exists. That is what makes this a weekend
project instead of a rewrite: the only thing that had to be understood is
*where damage arrives*, not what the game does with it afterwards.

---

## Building it

```
make.bat "D:\SteamLibrary\steamapps\common\Rainbow Six 3 Gold"
```

`ucc.exe` is already in your `system` folder — compiling needs no SDK. The
script copies the sources where `ucc` expects them, writes its own
`TarkovBuild.ini` so your `RavenShield.ini` is not touched, compiles, and
leaves `TarkovRvS.u` in `system`.

**If the build fails, read the error — it is doing its job.** Two things in
this mod are deliberate guesses, and a compiler error is the cheapest way to
find out what they should have been:

1. **`R6TakeDamage`'s argument list** (`TarkovPawnMedium.uc`). That this is the
   per-pawn damage entry point comes from the Raven Shield modding community;
   the argument list is the Unreal Engine 2 standard five. If it differs, the
   compiler prints the real signature. Paste it in and rebuild.
2. **The type of `m_pCurrentMod`** (`TarkovInjector.uc`). Every shipped
   descriptor uses the section `[Engine.R6Mod]`, so a class `R6Mod` exists;
   that the field is declared as that type is inference. OpenRVS avoids the
   question by chaining off `GetModMgr()` without naming a type, which is the
   fallback.

Neither guess can fail silently. That was the point of writing them as guesses
rather than as something defensive that compiles and does nothing.

### Reading the classes you are extending

To see the stock classes rather than guess at them, two routes:

* `tools\rs3_probe.py` in this repository reads your installed `.u` packages
  and prints the class tree and every class default it can find. It needs no
  SDK and writes nothing. Start here — it answers the terrorist pawn class
  question and the posture-variable question.
* `ucc batchexport R6Characters.u Class uc <dir>` exports stock classes as
  `.uc`. Whether a given retail build exports clean source or stubs varies;
  the fan-made Raven Shield SDK on ModDB exists because of that.

## Installing it

**Route A, the one to use.** Two lines in `<game>\system\RavenShield.ini`,
under `[Engine.GameEngine]`:

```
ServerPackages=TarkovRvS
ServerActors=TarkovRvS.TarkovInjector
```

Then copy `TarkovRvS.ini` into `<game>\system\`.

The injector rewrites the running mod's four class pointers before anything
spawns. This is the mechanism OpenRVS uses for its own weapon-FOV fix, and it
*stacks*: whatever mod you are running keeps running. Uninstalling is deleting
two lines.

**Route B, if route A does not fire.** Copy `TarkovRvS.mod` to `<game>\Mods\`,
create an empty `<game>\Mods\TarkovRvS\` beside it — the selector scans for
the pair — and pick it in the mod menu. This route *replaces* the running mod
rather than stacking on it.

### If another mod already owns these classes

The installation this was written against is not stock: `system\openrvs.ini`
sets `ForceStartMod=SupplyDrop`, and SupplyDrop replaces the pawn, AI and
player-controller classes itself. Our pawns extend the **stock** `R6Rainbow*`,
so taking the pointer off SupplyDrop would quietly discard whatever it
changed.

So the injector refuses, and says so in the log:

```
TarkovRvS: LEAVING medium pawn as 'SupplyDrop.SDRainbowMedium' -- another mod
owns it. Tarkov wounds will not apply to it.
```

Three ways forward: disable the other mod, set `bForceOverOtherMods=True` in
`TarkovRvS.ini` and accept the loss, or — the right fix — change the
`extends` line in the three pawn classes to that mod's pawns and rebuild. The
damage hook does not care what it inherits from.

## Calibrating it — do this first, it takes a minute

Raven Shield's damage term is bullet **energy**: 9mm Parabellum is 567, 5.56mm
NATO 1442, 7.62×51mm 2547. Whether that number reaches the script hook raw, or
already reduced by the native armour code, is the one thing in this mod that
cannot be worked out by reading files. So measure it:

```
TarkovDebugDamage 1
```

Take one unsilenced 9mm round. The console prints the raw figure. Then set

```
DamageScale = 54 / <that figure>
```

in `TarkovRvS.ini` — 54 being what 9mm Pst gzh does in Tarkov. If it printed
567, the shipped default of `0.0952` was already right.

## Turn on the ballistics option too — the two halves need each other

This mod and the **Tarkov** option group in the mod manager are not
alternatives. Each is nearly pointless without the other, and the arithmetic
says so plainly. Hits needed to black an 85-point thorax, at the shipped
`DamageScale`:

| Round | Raven Shield's own energy | With Tarkov ballistics | Tarkov |
|---|---|---|---|
| 9x19mm Pst gzh | 2 | 2 | 2 |
| 5.56x45mm M855 | **1** | 2 | 2 |
| 7.62x39mm PS | **1** | 2 | 2 |
| 7.62x51mm M80 | **1** | 2 | 2 |
| 7.62x54mmR LPS | **1** | 2 | 2 |
| .338 Lapua AP | 1 | 1 | 1 |

On stock energies every rifle round in the game one-shots a chest, so the
seven zones never get a chance to matter — you would have built a limb model
and then never used it. With the ballistics option the whole column lands on
Tarkov's own answer, including .338 still one-tapping and a 9mm still taking
two. Heads are one hit either way, which is also correct: 9mm Pst does 54 and
a head holds 35.

So: **Tarkov ballistics** → "Tarkov's damage spread" in the manager, then
build this. Conversely the ballistics option on its own makes firefights
longer without giving you anywhere new to aim, which is what this mod is for.

## Playing it

Bind one key per item in `Save\Profiles\user.ini` under `[Engine.Input]`:

```
F5=TkBandage auto
F6=TkTourniquet auto
F7=TkSplint auto
F8=TkPills
H=TkStatus
```

`auto` picks the zone that most needs that item — heaviest bleed first, vitals
before limbs — which is what makes this playable on one key per item instead of
eight. A zone name works too: `TkBandage lleg`.

## Enemies

`TarkovTerrorist.uc.template` is the terrorist body, and it is a template
because the terrorist pawn class name is not written down in any descriptor —
it lives in the AI templates (`template\*.tpt`, weighted `NNN, Package.Class`
lines). A wrong parent class stops `ucc make` for the whole package, which
would mean a guess about enemies blocking the player side from building at
all.

`tools\rs3_probe.py --pawns` prints the pawn classes your templates actually
spawn. Put the right one in the `extends` line, rename the file to `.uc`,
rebuild, and point the templates at `TarkovRvS.TarkovTerrorist`.

Raven Shield's own AI keeps driving them. This changes the body, not the
brain — which is what you wanted first: regular Raven Shield terrorist AI,
Tarkov wounds.

---

## How far this has actually been proven

This repository badges every option by how far it has been proven, and this
mod gets the same treatment. Nothing here is **verified in game**.

**Verified by reading real files or real source:**

* The four class pointers, their names and their stock values —
  `Mods\RavenShield.mod`.
* The server-actor injection route, including `GetModMgr().m_pCurrentMod` —
  OpenRVS's `OpenRenderFix/classes/OpenFix.uc` does exactly this.
* `R6HUD`, `R6PlayerController`, `R6Pawn`, `Level.m_bInGamePlanningActive`,
  and that a `config(<file>)` `Object` subclass is how Raven Shield mods carry
  tunables — all from OpenRVS source.
* That this install is not stock, and what SupplyDrop replaces.
* Raven Shield's ammunition energy figures, used for the calibration above.
* Tarkov's seven zone pools, 35/85/70/60/60/65/65.
* That head and thorax cannot be fractured, and that bleeding a vital to zero
  leaves you alive but one hit from dead.

**Reasoned, and the mod says so where it matters:**

* `R6TakeDamage`'s argument list, and the type of `m_pCurrentMod` — both fail
  loudly at compile time.
* The geometric zone bands. Chosen from a standing operative's collision
  height; they need one play-test with `TarkovDebugDamage 1` to confirm that
  shooting someone in the leg reports a leg.
* `DamageScale` — measure it, do not trust it.
* Bleed rates are the published Tarkov: **Arena** figures. Live Tarkov may
  differ. Light 0.8 per 6s, heavy 0.9 per 4s.
* Bleed, fracture and transfer chances. These are the numbers least anchored
  to anything, which is exactly why they are in an ini file.

**Not implemented, deliberately:**

* **Armour classes and penetration-versus-armour.** Tarkov's whole identity,
  and the one part that needs something not yet known: whether the hook
  receives the round's class, and whether native armour has already been
  applied. The probe answers the first.
* **Aim penalty from a damaged arm.** Raven Shield's weapon sway is native and
  no script-side hook for it is known. A blacked arm currently costs you
  nothing but the panel going red; legs do work, through `GroundSpeed`.
* **Prone zone resolution.** The vertical bands collapse on a horizontal body.
  The detection hook is written and returns `False` until somebody confirms
  what Raven Shield calls its posture variable.
* **Energy, hydration, looting, inventory, insurance, raids.** Those are the
  *game* Tarkov is, not the mechanic. A fixed medical kit per insertion is the
  smallest honest translation of the healing economy, and it is what is here.

//=============================================================================
// TarkovConfig -- every number this mod uses, in one ini-backed place.
//
// Nothing in this package hard-codes a balance figure. They all live here as
// `config` variables, which means:
//
//   * they are read from `system\TarkovRvS.ini` at start-up, so retuning the
//     health model does not need the SDK or a recompile, and
//   * Tom Clancy PC Mod Studio can edit them with the same `IniEdit` it uses
//     for every other Raven Shield option.
//
// The pattern is the one OpenRVS uses for `OpenFOV` -- an `Object` subclass
// with `config(<file>)`, read through `class'TarkovConfig'.default.<var>`.
// Verified against OpenRVS/classes/OpenFOV.uc.
//
// CONFIDENCE. The zone pools are the published Escape from Tarkov figures and
// are solid. The bleed rates are the published Tarkov: Arena figures, which
// may not match live. Everything marked INFERRED below is a reasoned guess
// that needs one play-test, and is a one-line ini edit when it turns out
// wrong -- which is the whole reason this file exists.
//=============================================================================
class TarkovConfig extends Object
	config(TarkovRvS);

// --- zone health pools -----------------------------------------------------
// Tarkov's seven zones, 440 points in total. Indexed by the ZONE_* constants
// in TarkovZones. These are the published values and are not inferred.
var config int ZoneHealth[7];           // 35, 85, 70, 60, 60, 65, 65

// --- how an incoming Raven Shield hit becomes Tarkov damage ---------------
// Raven Shield's damage term is bullet ENERGY (9mm Parabellum is 567, 5.56mm
// NATO 1442, 7.62x51mm 2547), and it is unknown whether `R6TakeDamage`
// receives that figure raw or something the native armour code has already
// reduced. So the conversion is a config scalar and the mod ships a console
// command that prints what it actually received:
//
//     TarkovDebugDamage 1
//
// Fire one unsilenced 9mm round into a terrorist, read the number off the
// screen, and set DamageScale to 54 / <that number> -- 54 being what 9mm
// Pst gzh does in Tarkov. That is a thirty-second calibration and it beats
// any guess this file could ship.
//
// The default assumes the raw energy figure reaches us: 54 / 567 = 0.0952.
var config float DamageScale;           // INFERRED -- calibrate in game
var config bool  bDebugDamage;          // print every hit's raw figures

// Damage handed to the native damage path when a hit is NOT lethal, so the
// game's own flinch, stagger and hit sound still play. 0 may be optimised
// away by native code; 1 is the safe choice.
var config int   NativeFlinchDamage;

// --- blacked-out limbs -----------------------------------------------------
// In Tarkov a hit on a destroyed limb is dealt to the thorax instead, scaled
// by a per-zone coefficient. Arms pass on less than legs do.
var config float TransferToThorax[7];   // INFERRED: 0,0,1.5,0.7,0.7,1.0,1.0

// Some Tarkov versions drain the thorax while a limb is blacked. Shipped off
// because it is the figure we are least sure of; set it to try it.
var config float BlackedLimbThoraxDps;

// Fraction of a limb's pool that a surgical kit gives back.
var config float SurgeryRestoreFraction;

// --- bleeding --------------------------------------------------------------
// Published Tarkov: Arena rates -- light 0.8 points every 6 seconds, heavy
// 0.9 every 4. Live Tarkov may differ; these are the ones with a citable
// source. A bleed damages the zone it is in; once that zone is blacked it
// damages the thorax, which is why an untreated heavy bleed in a dead leg
// still kills you.
var config float LightBleedDps;         // 0.8 / 6
var config float HeavyBleedDps;         // 0.9 / 4

// Chance per hit, before the damage weighting below. A hit that takes a lot
// of a zone's pool is likelier to open a bleed than a graze.
var config float LightBleedChance;      // INFERRED
var config float HeavyBleedChance;      // INFERRED
var config bool  bBleedChanceScalesWithDamage;

// --- fractures -------------------------------------------------------------
// Head and thorax cannot be fractured in Tarkov; limbs can. A fracture does
// what a blacked limb does until it is splinted.
var config float FractureChance;        // INFERRED
var config bool  bFractureOnBlackout;   // a destroyed limb is also broken

// --- the vital-organ rule --------------------------------------------------
// Bleeding a head or thorax to zero does not kill outright in Tarkov: it
// leaves you alive and one hit from dead. With this off, zero is death
// however it got there.
var config bool bVitalCriticalState;

// --- what being hurt costs you --------------------------------------------
// Movement speed multiplier with one and with both legs out of action, and
// the same for arms, which this version logs but does not yet apply --
// Raven Shield's weapon sway is native and the hook for it is not known
// yet. See README.md, "What is not implemented".
var config float SpeedOneLegDown;
var config float SpeedBothLegsDown;
var config float PainSpeedPenalty;      // while in pain and unmedicated

// --- the medical kit ------------------------------------------------------
// Tarkov's economy is looting and inventory, neither of which Raven Shield
// has. So you get a fixed kit per insertion, which is the smallest honest
// translation: a reason to spend a bandage carefully without inventing an
// inventory screen.
var config int   Bandages;              // clears a light bleed
var config int   Tourniquets;           // clears a heavy bleed
var config int   Splints;               // clears a fracture
var config int   SurgeryKits;           // un-blacks a limb
var config int   Painkillers;

// Seconds each takes. You are stationary and cannot fire while using one.
var config float BandageTime;
var config float TourniquetTime;
var config float SplintTime;
var config float SurgeryTime;
var config float PainkillerTime;
var config float PainkillerDuration;

// --- presentation ---------------------------------------------------------
// Draw the limb panel. Needs the HUD class swap, which is skipped when
// another mod already owns the HUD -- see TarkovInjector.
var config bool  bDrawHealthPanel;
var config float PanelX;                // fraction of screen width
var config float PanelY;
var config float PanelScale;
// Announce state changes as console messages. Independent of the panel, and
// the fallback when the HUD swap is declined.
var config bool  bAnnounceStateChanges;

defaultproperties
{
	// Published Tarkov zone pools: head, thorax, stomach, L arm, R arm,
	// L leg, R leg. 440 in total.
	ZoneHealth(0)=35
	ZoneHealth(1)=85
	ZoneHealth(2)=70
	ZoneHealth(3)=60
	ZoneHealth(4)=60
	ZoneHealth(5)=65
	ZoneHealth(6)=65

	DamageScale=0.0952
	bDebugDamage=False
	NativeFlinchDamage=1

	TransferToThorax(0)=0.0
	TransferToThorax(1)=0.0
	TransferToThorax(2)=1.5
	TransferToThorax(3)=0.7
	TransferToThorax(4)=0.7
	TransferToThorax(5)=1.0
	TransferToThorax(6)=1.0

	BlackedLimbThoraxDps=0.0
	SurgeryRestoreFraction=0.35

	LightBleedDps=0.1333
	HeavyBleedDps=0.2250
	LightBleedChance=0.35
	HeavyBleedChance=0.12
	bBleedChanceScalesWithDamage=True

	FractureChance=0.15
	bFractureOnBlackout=True

	bVitalCriticalState=True

	SpeedOneLegDown=0.55
	SpeedBothLegsDown=0.30
	PainSpeedPenalty=0.85

	Bandages=4
	Tourniquets=2
	Splints=2
	SurgeryKits=1
	Painkillers=2

	BandageTime=2.0
	TourniquetTime=4.0
	SplintTime=5.0
	SurgeryTime=9.0
	PainkillerTime=2.0
	PainkillerDuration=120.0

	bDrawHealthPanel=True
	PanelX=0.015
	PanelY=0.62
	PanelScale=1.0
	bAnnounceStateChanges=True
}

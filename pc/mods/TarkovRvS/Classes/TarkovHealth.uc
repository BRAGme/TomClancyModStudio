//=============================================================================
// TarkovHealth -- the state machine. One of these is attached to every pawn
// that plays by Tarkov's rules.
//
// WHY AN ACTOR AND NOT A PROPERTY BAG ON THE PAWN. Bleeding is time-based, so
// something has to tick. Putting the state on the pawn would mean copying the
// whole model into every pawn subclass -- player light, medium and heavy,
// plus the terrorists -- because UnrealScript has no mixins. An `Info` owned
// by the pawn ticks itself, so each pawn subclass needs three lines: spawn
// one, hand hits to it, and ask it whether the man is dead.
//
// WHAT IT IMPLEMENTS, AND WHAT TARKOV CALLS IT
//   * seven zone pools totalling 440 points
//   * a zone at zero is "blacked"; head or thorax blacked is death
//   * hits on a blacked limb are dealt to the thorax, scaled per zone
//   * light and heavy bleeding, which damage their own zone until it is
//     blacked and the thorax after that
//   * fractures on limbs, never on head or thorax
//   * the vital-organ rule: bleeding a head or thorax to zero leaves you
//     alive and one hit from dead
//   * bandages, tourniquets, splints, surgical kits and painkillers, each
//     with a use time that is interrupted by taking a hit
//
// Every figure comes from TarkovConfig, so none of this needs a recompile to
// retune.
//=============================================================================
class TarkovHealth extends Info;

// The zone indices. UnrealScript consts reach subclasses but not across
// unrelated class trees -- TarkovZones extends Object, this extends Info --
// so these mirror the canonical set there. TarkovZones is still the only
// place that decides WHICH zone a hit landed in.
const ZONE_HEAD    = 0;
const ZONE_THORAX  = 1;
const ZONE_STOMACH = 2;
const ZONE_ARM_L   = 3;
const ZONE_ARM_R   = 4;
const ZONE_LEG_L   = 5;
const ZONE_LEG_R   = 6;

const USE_NONE       = 0;
const USE_BANDAGE    = 1;
const USE_TOURNIQUET = 2;
const USE_SPLINT     = 3;
const USE_SURGERY    = 4;
const USE_PAINKILLER = 5;

const BLEED_NONE  = 0;
const BLEED_LIGHT = 1;
const BLEED_HEAVY = 2;

var Pawn  Host;

var int   Hp[7];
var int   MaxHp[7];
var int   Bleed[7];                     // BLEED_*
var bool  bFractured[7];
var bool  bBlacked[7];

// Fractional damage carried between ticks. Bleeding is well under a point a
// second and the pools are integers, so without this it would round to zero
// every tick and nobody would ever bleed out.
var float Carry[7];

var bool  bVitalCritical;               // alive, but the next hit is fatal
var bool  bDead;

var int   Bandages, Tourniquets, Splints, SurgeryKits, Painkillers;

var int   UseKind;
var int   UseZone;
var float UseRemaining;
var float PainkillerRemaining;

var float BaseGroundSpeed;

// ---------------------------------------------------------------------------
// set-up
// ---------------------------------------------------------------------------

function Init(Pawn P)
{
	local int i;

	Host = P;
	if (Host != None)
		BaseGroundSpeed = Host.GroundSpeed;

	for (i = 0; i < 7; i++)
	{
		MaxHp[i] = class'TarkovConfig'.default.ZoneHealth[i];
		Hp[i] = MaxHp[i];
		Bleed[i] = BLEED_NONE;
		bFractured[i] = false;
		bBlacked[i] = false;
		Carry[i] = 0.0;
	}
	bVitalCritical = false;
	bDead = false;

	Bandages    = class'TarkovConfig'.default.Bandages;
	Tourniquets = class'TarkovConfig'.default.Tourniquets;
	Splints     = class'TarkovConfig'.default.Splints;
	SurgeryKits = class'TarkovConfig'.default.SurgeryKits;
	Painkillers = class'TarkovConfig'.default.Painkillers;

	UseKind = USE_NONE;
	UseRemaining = 0.0;
	PainkillerRemaining = 0.0;
}

// ---------------------------------------------------------------------------
// taking a hit
// ---------------------------------------------------------------------------

// Returns true when this hit kills. The caller -- the pawn's own
// `R6TakeDamage` override -- then lets the native damage path run with a
// lethal figure, so the game's own death, ragdoll, scoring and mission logic
// all happen exactly as they always did. We only decide WHETHER, never HOW.
function bool Route(int RawDamage, Pawn InstigatedBy, vector HitLocation)
{
	local int zone;
	local float dmg;

	if (bDead)
		return true;

	zone = class'TarkovZones'.static.Resolve(Host, HitLocation);
	dmg = float(RawDamage) * class'TarkovConfig'.default.DamageScale;

	if (class'TarkovConfig'.default.bDebugDamage)
		Msg("[tarkov] raw=" $ RawDamage $ " scaled=" $ int(dmg) $ " zone="
			$ class'TarkovZones'.static.ZoneName(zone));

	// Using an item is interrupted by being shot at. Tarkov does this and it
	// is most of what makes a firefight tense rather than a pause button.
	if (UseKind != USE_NONE)
	{
		Msg("Interrupted.");
		UseKind = USE_NONE;
		UseRemaining = 0.0;
	}

	ApplyHit(zone, dmg, true, true);
	UpdateMovement();
	return bDead;
}

// Two flags, and they mean different things, which is worth being precise
// about because conflating them gets the lethality of a transferred hit wrong:
//
//   `bMayWound` -- may this hit open a bleed or break a bone? True only for a
//     round that landed on this zone directly. A bleed must not open a second
//     bleed, and a hit that transferred out of a destroyed arm must not
//     fracture the chest it transferred into.
//   `bDirect` -- is this a bullet at all, as opposed to bleeding out? A bullet
//     that zeroes a vital kills on the spot. Bleeding one to zero does not:
//     Tarkov leaves you alive and one hit from dead, and that one hit may well
//     be the next tick of the same bleed.
//
// A round through a blacked arm is therefore `bMayWound=false, bDirect=true`:
// it cannot break the thorax, and it can certainly kill it.
function ApplyHit(int zone, float dmg, bool bMayWound, bool bDirect)
{
	local float share;

	if (bDead || dmg <= 0.0)
		return;

	// A round into a limb that is already destroyed goes to the chest.
	if (bBlacked[zone] && !class'TarkovZones'.static.IsVital(zone))
	{
		share = class'TarkovConfig'.default.TransferToThorax[zone];
		if (share > 0.0)
			ApplyHit(ZONE_THORAX, dmg * share, false, bDirect);
		return;
	}

	// One hit away from dead, and this is the hit.
	if (bVitalCritical)
	{
		bDead = true;
		return;
	}

	if (bMayWound)
		RollWounds(zone, dmg);

	Hp[zone] = Hp[zone] - int(dmg);
	if (Hp[zone] > 0)
		return;

	Hp[zone] = 0;
	BlackOut(zone, bDirect);
}

function RollWounds(int zone, float dmg)
{
	local float weight, light, heavy, frac;

	weight = 1.0;
	if (class'TarkovConfig'.default.bBleedChanceScalesWithDamage
		&& MaxHp[zone] > 0)
	{
		// A graze rarely opens an artery; a round that takes half the limb
		// usually does. Clamped so a huge hit cannot exceed certainty.
		weight = FClamp(dmg / (0.5 * float(MaxHp[zone])), 0.15, 1.0);
	}

	heavy = class'TarkovConfig'.default.HeavyBleedChance * weight;
	light = class'TarkovConfig'.default.LightBleedChance * weight;

	if (FRand() < heavy)
		SetBleed(zone, BLEED_HEAVY);
	else if (FRand() < light)
		SetBleed(zone, BLEED_LIGHT);

	// Head and thorax cannot be fractured.
	if (!class'TarkovZones'.static.IsVital(zone) && !bFractured[zone])
	{
		frac = class'TarkovConfig'.default.FractureChance * weight;
		if (FRand() < frac)
			SetFracture(zone);
	}
}

function BlackOut(int zone, bool bFromBullet)
{
	if (bBlacked[zone])
		return;

	bBlacked[zone] = true;

	if (class'TarkovZones'.static.IsVital(zone))
	{
		// Shot to zero is death. Bled to zero, with the vital rule on, is
		// the critical state instead.
		if (bFromBullet || !class'TarkovConfig'.default.bVitalCriticalState)
		{
			bDead = true;
			return;
		}
		bVitalCritical = true;
		Announce(class'TarkovZones'.static.ZoneName(zone)
			$ " critical -- the next hit kills you.");
		return;
	}

	if (class'TarkovConfig'.default.bFractureOnBlackout)
		bFractured[zone] = true;

	Announce(class'TarkovZones'.static.ZoneName(zone) $ " destroyed.");
}

function SetBleed(int zone, int level)
{
	if (Bleed[zone] >= level)
		return;
	Bleed[zone] = level;
	if (level == BLEED_HEAVY)
		Announce("Heavy bleeding, " $ class'TarkovZones'.static.ZoneName(zone) $ ".");
	else
		Announce("Bleeding, " $ class'TarkovZones'.static.ZoneName(zone) $ ".");
}

function SetFracture(int zone)
{
	if (bFractured[zone])
		return;
	bFractured[zone] = true;
	Announce("Fracture, " $ class'TarkovZones'.static.ZoneName(zone) $ ".");
}

// ---------------------------------------------------------------------------
// time: bleeding, blacked-limb drain, use timers
// ---------------------------------------------------------------------------

event Tick(float DeltaTime)
{
	local int i;
	local float dps, drain;

	if (bDead || Host == None || Host.Health <= 0)
		return;

	for (i = 0; i < 7; i++)
	{
		if (Bleed[i] == BLEED_NONE)
			continue;

		if (Bleed[i] == BLEED_HEAVY)
			dps = class'TarkovConfig'.default.HeavyBleedDps;
		else
			dps = class'TarkovConfig'.default.LightBleedDps;

		Drip(i, dps * DeltaTime);
	}

	drain = class'TarkovConfig'.default.BlackedLimbThoraxDps;
	if (drain > 0.0)
	{
		for (i = 0; i < 7; i++)
		{
			if (bBlacked[i] && !class'TarkovZones'.static.IsVital(i))
				Drip(ZONE_THORAX, drain * DeltaTime);
		}
	}

	if (UseRemaining > 0.0)
	{
		UseRemaining -= DeltaTime;
		if (UseRemaining <= 0.0)
			FinishUse();
	}

	if (PainkillerRemaining > 0.0)
	{
		PainkillerRemaining -= DeltaTime;
		if (PainkillerRemaining <= 0.0)
		{
			Announce("The painkillers have worn off.");
			UpdateMovement();
		}
	}
}

// Sub-point damage, accumulated until it is worth a whole point. A bleed in a
// destroyed limb is paid by the thorax, which is why an untreated heavy bleed
// in a dead leg still kills you.
function Drip(int zone, float amount)
{
	local int target, whole;

	target = zone;
	if (bBlacked[zone] && !class'TarkovZones'.static.IsVital(zone))
		target = ZONE_THORAX;

	Carry[target] += amount;
	if (Carry[target] < 1.0)
		return;

	whole = int(Carry[target]);
	Carry[target] -= float(whole);
	ApplyHit(target, float(whole), false, false);
}

// ---------------------------------------------------------------------------
// treatment
// ---------------------------------------------------------------------------

function bool BeginUse(int kind, int zone)
{
	local float t;

	if (bDead)
		return false;
	if (UseKind != USE_NONE)
	{
		Msg("Already using something.");
		return false;
	}
	if (zone < 0 || zone >= 7)
	{
		Msg("No such body part.");
		return false;
	}

	switch (kind)
	{
		case USE_BANDAGE:
			if (Bandages <= 0)      { Msg("No bandages left."); return false; }
			if (Bleed[zone] == BLEED_NONE)
			{
				Msg("Nothing bleeding there."); return false;
			}
			t = class'TarkovConfig'.default.BandageTime;
			break;
		case USE_TOURNIQUET:
			if (Tourniquets <= 0)   { Msg("No tourniquets left."); return false; }
			if (Bleed[zone] != BLEED_HEAVY)
			{
				Msg("A bandage will do for that."); return false;
			}
			t = class'TarkovConfig'.default.TourniquetTime;
			break;
		case USE_SPLINT:
			if (Splints <= 0)       { Msg("No splints left."); return false; }
			if (!bFractured[zone])  { Msg("Nothing broken there."); return false; }
			t = class'TarkovConfig'.default.SplintTime;
			break;
		case USE_SURGERY:
			if (SurgeryKits <= 0)   { Msg("No surgical kit left."); return false; }
			if (!bBlacked[zone])    { Msg("That limb still works."); return false; }
			if (class'TarkovZones'.static.IsVital(zone))
			{
				Msg("A surgical kit cannot fix that."); return false;
			}
			t = class'TarkovConfig'.default.SurgeryTime;
			break;
		case USE_PAINKILLER:
			if (Painkillers <= 0)   { Msg("No painkillers left."); return false; }
			t = class'TarkovConfig'.default.PainkillerTime;
			break;
		default:
			return false;
	}

	UseKind = kind;
	UseZone = zone;
	UseRemaining = t;
	return true;
}

function FinishUse()
{
	local int kind, zone;

	kind = UseKind;
	zone = UseZone;
	UseKind = USE_NONE;
	UseRemaining = 0.0;

	switch (kind)
	{
		case USE_BANDAGE:
			Bandages--;
			Bleed[zone] = BLEED_NONE;
			Carry[zone] = 0.0;
			Msg("Bandaged " $ class'TarkovZones'.static.ZoneName(zone) $ ".");
			break;
		case USE_TOURNIQUET:
			Tourniquets--;
			Bleed[zone] = BLEED_NONE;
			Carry[zone] = 0.0;
			Msg("Tourniquet on " $ class'TarkovZones'.static.ZoneName(zone) $ ".");
			break;
		case USE_SPLINT:
			Splints--;
			bFractured[zone] = false;
			Msg("Splinted " $ class'TarkovZones'.static.ZoneName(zone) $ ".");
			break;
		case USE_SURGERY:
			SurgeryKits--;
			bBlacked[zone] = false;
			bFractured[zone] = false;
			Hp[zone] = Max(1, int(float(MaxHp[zone])
				* class'TarkovConfig'.default.SurgeryRestoreFraction));
			Msg("Operated on " $ class'TarkovZones'.static.ZoneName(zone) $ ".");
			break;
		case USE_PAINKILLER:
			Painkillers--;
			PainkillerRemaining = class'TarkovConfig'.default.PainkillerDuration;
			Msg("Painkillers taken.");
			break;
	}
	UpdateMovement();
}

// ---------------------------------------------------------------------------
// what being hurt costs you
// ---------------------------------------------------------------------------

function UpdateMovement()
{
	local int down;
	local float mult;

	if (Host == None || BaseGroundSpeed <= 0.0)
		return;

	down = 0;
	if (bBlacked[ZONE_LEG_L]
		|| bFractured[ZONE_LEG_L])
		down++;
	if (bBlacked[ZONE_LEG_R]
		|| bFractured[ZONE_LEG_R])
		down++;

	mult = 1.0;
	if (down >= 2)
		mult = class'TarkovConfig'.default.SpeedBothLegsDown;
	else if (down == 1)
		mult = class'TarkovConfig'.default.SpeedOneLegDown;

	// Painkillers mask the limp as well as the pain.
	if (InPain() && PainkillerRemaining <= 0.0)
		mult *= class'TarkovConfig'.default.PainSpeedPenalty;

	Host.GroundSpeed = BaseGroundSpeed * mult;
}

function bool InPain()
{
	local int i;

	for (i = 0; i < 7; i++)
	{
		if (bFractured[i] || bBlacked[i])
			return true;
	}
	return false;
}

function int TotalHp()
{
	local int i, sum;

	for (i = 0; i < 7; i++)
		sum += Hp[i];
	return sum;
}

// ---------------------------------------------------------------------------
// talking to the player
// ---------------------------------------------------------------------------

function Msg(string s)
{
	local PlayerController pc;

	if (Host == None)
		return;
	pc = PlayerController(Host.Controller);
	if (pc != None)
		pc.ClientMessage(s);
}

function Announce(string s)
{
	if (class'TarkovConfig'.default.bAnnounceStateChanges)
		Msg(s);
}

function string StatusLine(int zone)
{
	local string s;

	s = class'TarkovZones'.static.ZoneName(zone) $ " " $ Hp[zone] $ "/" $ MaxHp[zone];
	if (bBlacked[zone])
		s = s $ " [out]";
	if (bFractured[zone])
		s = s $ " [broken]";
	if (Bleed[zone] == BLEED_HEAVY)
		s = s $ " [heavy bleed]";
	else if (Bleed[zone] == BLEED_LIGHT)
		s = s $ " [bleeding]";
	return s;
}

defaultproperties
{
	bHidden=True
	bAlwaysTick=True
	RemoteRole=ROLE_None
}

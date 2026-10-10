//=============================================================================
// TarkovZones -- which part of a man a bullet hit.
//
// THE PROBLEM. Tarkov's health model needs to know which of seven body zones
// took the round. Raven Shield's own damage path is native below the point
// this mod can reach, and no bone or hit-zone name is documented anywhere in
// the modding surface -- `docs/FORMATS.md` and `research/dossier-rs3.md`
// between them cover the weapon, ammunition, AI-template and config surfaces
// and neither contains a skeleton.
//
// THE ANSWER THAT NEEDS NOTHING UNDOCUMENTED. A hit arrives with a world
// location. Put it in the pawn's own frame of reference and the zone falls
// out of geometry: height picks head / chest / stomach / legs, and lateral
// offset picks an arm. No bone names, no native calls, nothing to verify
// against a header -- it works on any UE2 pawn.
//
// `CollisionHeight` is half-height and Unreal shrinks it when a pawn crouches,
// so the bands follow a crouching man for free. Prone is the case this does
// NOT handle: a prone body is horizontal and the height bands collapse into
// each other. See `bProneUsesForwardAxis` and `IsProne` below -- the detection
// hook is written and deliberately returns False until somebody confirms what
// Raven Shield calls its posture variable.
//=============================================================================
class TarkovZones extends Object
	config(TarkovRvS);

const ZONE_HEAD     = 0;
const ZONE_THORAX   = 1;
const ZONE_STOMACH  = 2;
const ZONE_ARM_L    = 3;
const ZONE_ARM_R    = 4;
const ZONE_LEG_L    = 5;
const ZONE_LEG_R    = 6;
const ZONE_MAX      = 7;

// Band edges as a fraction of CollisionHeight, measured from the pawn's
// centre: +1 is the top of the collision cylinder, -1 the bottom. A standing
// Raven Shield operative is about 88 units of half-height, so 0.78 puts the
// neckline around 68 units up -- roughly chin height on a 176cm man.
var config float HeadBand;              // above this: head
var config float ThoraxBand;            // above this: thorax
var config float StomachBand;           // above this: stomach, below: legs

// How far out from the centre line, as a fraction of CollisionRadius, a hit
// has to land before it is an arm rather than the torso behind it.
var config float ArmBand;

// Prone handling -- see the class comment.
var config bool bProneUsesForwardAxis;

static function int Resolve(Pawn P, vector HitLocation)
{
	local vector rel, fwd, right;
	local rotator flat;
	local float h, side;

	if (P == None)
		return ZONE_THORAX;

	rel = HitLocation - P.Location;

	// The pawn's own frame, with pitch and roll thrown away: a man looking up
	// has not tipped his chest over, and keeping his pitch here would swing
	// the zone bands with his aim. `vector(rotator)` is an operator, so this
	// works inside a static function -- `GetAxes` does not, it is a non-static
	// native.
	flat = P.Rotation;
	flat.Pitch = 0;
	flat.Roll = 0;
	fwd = vector(flat);
	flat.Yaw += 16384;                  // a quarter turn: the pawn's right
	right = vector(flat);

	side = rel dot right;
	if (P.CollisionRadius > 0.0)
		side = side / P.CollisionRadius;

	if (default.bProneUsesForwardAxis && static.IsProne(P))
	{
		// Lying down, the body runs along the forward axis instead of the
		// vertical one. Head forward, legs behind.
		h = rel dot fwd;
		if (P.CollisionRadius > 0.0)
			h = h / P.CollisionRadius;
	}
	else
	{
		h = rel.Z;
		if (P.CollisionHeight > 0.0)
			h = h / P.CollisionHeight;
	}

	if (h >= default.HeadBand)
		return ZONE_HEAD;

	if (h >= default.StomachBand)
	{
		// Chest or belly -- unless the round landed wide, in which case it
		// went through the arm hanging in front of it.
		if (Abs(side) >= default.ArmBand)
		{
			if (side >= 0.0)
				return ZONE_ARM_R;
			return ZONE_ARM_L;
		}
		if (h >= default.ThoraxBand)
			return ZONE_THORAX;
		return ZONE_STOMACH;
	}

	if (side >= 0.0)
		return ZONE_LEG_R;
	return ZONE_LEG_L;
}

// VERIFY. Raven Shield certainly knows whether a pawn is prone -- the noise
// model scores a prone player separately (`Sound.ini`, `m_Rainbow.fProne`) --
// but the name of the variable or function that says so is not documented in
// anything this mod was written against, and guessing it would not compile.
// Run `tools\rs3_probe.py --pawn` against your install: it prints every
// property on the pawn classes, and whichever one means posture goes here.
// Until then this returns False and the vertical bands are always used, which
// is correct for standing and crouching and wrong for prone.
static function bool IsProne(Pawn P)
{
	return false;
}

static function string ZoneName(int zone)
{
	switch (zone)
	{
		case ZONE_HEAD:    return "head";
		case ZONE_THORAX:  return "thorax";
		case ZONE_STOMACH: return "stomach";
		case ZONE_ARM_L:   return "left arm";
		case ZONE_ARM_R:   return "right arm";
		case ZONE_LEG_L:   return "left leg";
		case ZONE_LEG_R:   return "right leg";
	}
	return "unknown";
}

static function bool IsVital(int zone)
{
	return (zone == ZONE_HEAD) || (zone == ZONE_THORAX);
}

static function bool IsLeg(int zone)
{
	return (zone == ZONE_LEG_L) || (zone == ZONE_LEG_R);
}

static function bool IsArm(int zone)
{
	return (zone == ZONE_ARM_L) || (zone == ZONE_ARM_R);
}

defaultproperties
{
	HeadBand=0.78
	ThoraxBand=0.30
	StomachBand=-0.10
	ArmBand=0.55
	bProneUsesForwardAxis=False
}

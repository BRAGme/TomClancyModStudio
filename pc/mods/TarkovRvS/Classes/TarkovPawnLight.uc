//=============================================================================
// TarkovPawnLight -- the light-armour Rainbow operative, playing by Tarkov's
// rules. Identical to TarkovPawnMedium.uc but for the parent class; the
// commentary on why the damage hook is shaped this way is there, and the
// `R6TakeDamage` signature to verify is the same one.
//
// UnrealScript has no mixins and these three have to extend three different
// Raven Shield classes, so the twelve lines below are repeated rather than
// shared. Everything with an opinion in it lives in TarkovHealth.
//=============================================================================
class TarkovPawnLight extends R6RainbowLight;

var TarkovHealth Wounds;

const LETHAL = 10000;

function PostBeginPlay()
{
	Super.PostBeginPlay();
	Wounds = Spawn(class'TarkovHealth', self);
	if (Wounds != None)
		Wounds.Init(self);
}

simulated function Destroyed()
{
	if (Wounds != None)
	{
		Wounds.Destroy();
		Wounds = None;
	}
	Super.Destroyed();
}

// VERIFY -- see the class comment.
function R6TakeDamage(int Damage, Pawn InstigatedBy, vector HitLocation,
	vector Momentum, class<DamageType> DamageType)
{
	local int saved;

	if (Wounds == None)
	{
		Super.R6TakeDamage(Damage, InstigatedBy, HitLocation, Momentum, DamageType);
		return;
	}

	if (Wounds.Route(Damage, InstigatedBy, HitLocation))
	{
		Super.R6TakeDamage(LETHAL, InstigatedBy, HitLocation, Momentum, DamageType);
		return;
	}

	saved = Health;
	Super.R6TakeDamage(class'TarkovConfig'.default.NativeFlinchDamage,
		InstigatedBy, HitLocation, Momentum, DamageType);
	if (Health > 0)
		Health = saved;
}

function TakeDamage(int Damage, Pawn InstigatedBy, vector HitLocation,
	vector Momentum, class<DamageType> DamageType)
{
	local int saved;

	if (Wounds == None)
	{
		Super.TakeDamage(Damage, InstigatedBy, HitLocation, Momentum, DamageType);
		return;
	}

	if (Wounds.Route(Damage, InstigatedBy, HitLocation))
	{
		Super.TakeDamage(LETHAL, InstigatedBy, HitLocation, Momentum, DamageType);
		return;
	}

	saved = Health;
	Super.TakeDamage(class'TarkovConfig'.default.NativeFlinchDamage,
		InstigatedBy, HitLocation, Momentum, DamageType);
	if (Health > 0)
		Health = saved;
}

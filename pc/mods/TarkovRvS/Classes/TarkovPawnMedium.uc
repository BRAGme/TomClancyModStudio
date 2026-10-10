//=============================================================================
// TarkovPawnMedium -- a medium-armour Rainbow operative that plays by
// Tarkov's rules. Light and Heavy are byte-identical but for the parent.
//
// HOW THE HOOK WORKS, AND WHY IT IS SHAPED LIKE THIS.
//
// This override does not deal damage. It decides, and then lets Raven
// Shield's own damage path do the work:
//
//   * survivable hit -> call Super with a single point of damage, so the
//     native flinch, hit sound and stagger all still play, then put the
//     native Health figure back where it was. The native bookkeeping is
//     undone; its side effects are kept.
//   * fatal hit -> call Super with a lethal figure, so the game's own death,
//     animation, scoring and mission logic run exactly as they always did.
//
// Nothing in the engine has to know that a limb model exists. That is what
// makes this survivable: the only thing we had to understand is where damage
// arrives, not what the game does with it afterwards.
//
// THE ONE THING TO VERIFY. `R6TakeDamage` is the name a Raven Shield mod
// author gave for the per-pawn damage entry point, and the armour maths below
// it is native. The ARGUMENT LIST is a reasoned guess at the Unreal Engine 2
// standard. If it is wrong, `ucc make` fails on this line and prints the real
// signature -- paste that in and rebuild. A compile error here is the cheapest
// possible way to find out, which is why this is shipped as a guess rather
// than as something that silently does nothing.
//
// `TakeDamage` below it is the stock Unreal entry point and its signature is
// not a guess. It catches explosions, falls and anything else that does not
// come down the bullet path, so even if `R6TakeDamage` has to be corrected,
// the mod is not inert in the meantime.
//=============================================================================
class TarkovPawnMedium extends R6RainbowMedium;

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

//=============================================================================
// TarkovInjector -- how this mod gets loaded at all.
//
// Raven Shield decides which pawn, AI, player-controller and HUD classes to
// use from the running mod's descriptor (`Mods\*.mod`, `[Engine.R6Mod]`). Two
// routes reach those four strings, and this mod ships both:
//
//   ROUTE A -- a server actor. One line in `[Engine.GameEngine]`:
//
//       ServerPackages=TarkovRvS
//       ServerActors=TarkovRvS.TarkovInjector
//
//     This actor then rewrites the live mod's class names before anything is
//     spawned. It is the route OpenRVS uses for its own weapon-FOV fix
//     (`OpenRenderFix.OpenFix`), verified in that project's source, and it is
//     better than editing a descriptor because it stacks: whatever mod is
//     running keeps running, and uninstalling is deleting two lines.
//
//   ROUTE B -- a descriptor of our own, `TarkovRvS.mod`, naming the classes
//     directly. Use it if route A does not fire. See README.md.
//
// THE OTHER-MOD PROBLEM, STATED HONESTLY. The installation this was written
// against is not stock: `system\openrvs.ini` carries
// `ForceStartMod=SupplyDrop`, and SupplyDrop replaces the pawn, teammate-AI
// and player-controller classes itself. Our pawn classes extend the STOCK
// `R6Rainbow*`, so replacing SupplyDrop's pawns with ours silently discards
// whatever SupplyDrop changed about them.
//
// So by default this refuses: it swaps a class only when what it finds is the
// stock name or blank, logs every decision it makes, and tells you what it
// found. `bForceOverOtherMods=True` overrides that, and the right fix if you
// want both is to re-parent the three pawn classes onto SupplyDrop's.
//=============================================================================
class TarkovInjector extends Actor
	config(TarkovRvS);

var config bool bReplacePawns;
var config bool bReplaceController;
var config bool bReplaceHUD;
var config bool bForceOverOtherMods;
var config bool bLogDecisions;

// What the stock descriptor holds, upper-cased. Anything else means another
// mod got there first. From `Mods\RavenShield.mod`, verified.
const STOCK_LIGHT  = "R6CHARACTERS.R6RAINBOWLIGHT";
const STOCK_MEDIUM = "R6CHARACTERS.R6RAINBOWMEDIUM";
const STOCK_HEAVY  = "R6CHARACTERS.R6RAINBOWHEAVY";
const STOCK_CTRL   = "R6ENGINE.R6PLAYERCONTROLLER";
const STOCK_HUD    = "R6GAME.R6HUD";

simulated function PreBeginPlay()
{
	// VERIFY, cheaply. `[Engine.R6Mod]` is the section every shipped
	// descriptor uses, so the class exists; that `m_pCurrentMod` is declared
	// as that type is the inference. If it is not, `ucc make` says so on this
	// line and names the real type. OpenRVS sidesteps the question by
	// chaining off `GetModMgr()` without ever naming the type -- do that if
	// this will not compile.
	local R6Mod m;

	Super.PreBeginPlay();

	m = class'Actor'.static.GetModMgr().m_pCurrentMod;
	if (m == None)
	{
		Log("TarkovRvS: no current mod -- nothing to hook. Use route B.");
		return;
	}

	if (bReplacePawns)
	{
		m.m_DefaultLightPawn  = Swap("light pawn", m.m_DefaultLightPawn,
			STOCK_LIGHT,  "TarkovRvS.TarkovPawnLight");
		m.m_DefaultMediumPawn = Swap("medium pawn", m.m_DefaultMediumPawn,
			STOCK_MEDIUM, "TarkovRvS.TarkovPawnMedium");
		m.m_DefaultHeavyPawn  = Swap("heavy pawn", m.m_DefaultHeavyPawn,
			STOCK_HEAVY,  "TarkovRvS.TarkovPawnHeavy");
	}

	if (bReplaceController)
		m.m_PlayerCtrlToSpawn = Swap("player controller",
			m.m_PlayerCtrlToSpawn, STOCK_CTRL, "TarkovRvS.TarkovController");

	if (bReplaceHUD && class'TarkovConfig'.default.bDrawHealthPanel)
		m.m_GlobalHUDToSpawn = Swap("HUD", m.m_GlobalHUDToSpawn,
			STOCK_HUD, "TarkovRvS.TarkovHUD");
}

// Returns what the field should now hold. Refuses, loudly, when another mod
// owns it -- the health model still works without the controller or the HUD,
// so a refusal degrades instead of breaking.
function string Swap(string what, string current, string stock, string ours)
{
	local string now;

	now = caps(current);

	if (now == caps(ours))
		return current;                 // already ours

	if ((now == "") || (now == stock) || bForceOverOtherMods)
	{
		if (bLogDecisions)
		{
			if (now == "")
				Log("TarkovRvS: " $ what $ " <- " $ ours $ " (was unset)");
			else
				Log("TarkovRvS: " $ what $ " <- " $ ours);
		}
		return ours;
	}

	Log("TarkovRvS: LEAVING " $ what $ " as '" $ current $ "' -- another mod"
		$ " owns it. Tarkov wounds will not apply to it. Either disable that"
		$ " mod, re-parent our class onto theirs, or set"
		$ " bForceOverOtherMods=True in system\\TarkovRvS.ini.");
	return current;
}

defaultproperties
{
	bReplacePawns=True
	bReplaceController=True
	bReplaceHUD=True
	bForceOverOtherMods=False
	bLogDecisions=True

	bHidden=True
	bAlwaysRelevant=True
	bAlwaysTick=True
	RemoteRole=ROLE_SimulatedProxy
}

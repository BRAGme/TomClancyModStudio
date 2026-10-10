//=============================================================================
// TarkovController -- the hands. Everything the player can do about being
// wounded is a console command here, so it works with or without the HUD and
// needs no new menu.
//
//     TkBandage    <zone|auto>   stops a light bleed
//     TkTourniquet <zone|auto>   stops a heavy bleed
//     TkSplint     <zone|auto>   sets a fracture
//     TkSurgery    <zone|auto>   brings a destroyed limb back, partly
//     TkPills                    painkillers
//     TkStatus                   print the seven zones
//     TarkovDebugDamage <0|1>    print what every hit actually arrives as
//
// `auto` picks the zone that most needs that item -- heaviest bleed, worst
// fracture, worst destroyed limb -- which is what makes this playable on one
// key per item instead of eight.
//
// Bind them in `Save\Profiles\user.ini` under `[Engine.Input]`:
//
//     F5=TkBandage auto
//     F6=TkTourniquet auto
//     F7=TkSplint auto
//     F8=TkPills
//     H=TkStatus
//
// Those five lines are `IniEdit`s, so Tom Clancy PC Mod Studio can write them
// -- see the `tarkov_keybinds` option in `tcpc/games/_rs3_tarkov.py`.
//
// Using anything takes time, you cannot move the clock along by shooting, and
// a round landing on you cancels it (TarkovHealth.Route). That interruption
// is most of what makes Tarkov's healing tense rather than a pause button, so
// it is in the model rather than here.
//=============================================================================
class TarkovController extends R6PlayerController;

// Mirrors of TarkovHealth's item kinds. A `case` label has to be a
// compile-time constant and UnrealScript consts do not cross unrelated class
// trees, so they are repeated here rather than reached for.
const USE_BANDAGE    = 1;
const USE_TOURNIQUET = 2;
const USE_SPLINT     = 3;
const USE_SURGERY    = 4;
const USE_PAINKILLER = 5;

var TarkovHealth Cached;

exec function TkBandage(optional string zone)
{
	Use(USE_BANDAGE, zone);
}

exec function TkTourniquet(optional string zone)
{
	Use(USE_TOURNIQUET, zone);
}

exec function TkSplint(optional string zone)
{
	Use(USE_SPLINT, zone);
}

exec function TkSurgery(optional string zone)
{
	Use(USE_SURGERY, zone);
}

exec function TkPills()
{
	Use(USE_PAINKILLER, "thorax");
}

exec function TkStatus()
{
	local TarkovHealth w;
	local int i;

	w = FindWounds();
	if (w == None)
	{
		ClientMessage("TarkovRvS: no wound model on this pawn."
			@ "Check the log for what TarkovInjector decided.");
		return;
	}

	for (i = 0; i < 7; i++)
		ClientMessage(w.StatusLine(i));
	ClientMessage("total" @ w.TotalHp() $ "/440   bandage" @ w.Bandages
		$ " tq" @ w.Tourniquets $ " splint" @ w.Splints
		$ " cms" @ w.SurgeryKits $ " pills" @ w.Painkillers);
}

// The calibration command. See the DamageScale comment in TarkovConfig.uc:
// turn this on, take one 9mm round, and the number it prints is what to
// divide 54 by.
exec function TarkovDebugDamage(optional int on)
{
	class'TarkovConfig'.default.bDebugDamage = (on != 0);
	class'TarkovConfig'.static.StaticSaveConfig();
	ClientMessage("TarkovRvS: damage debug"
		@ class'TarkovConfig'.default.bDebugDamage);
}

function Use(int kind, string zone)
{
	local TarkovHealth w;
	local int z;

	w = FindWounds();
	if (w == None)
	{
		ClientMessage("TarkovRvS: no wound model on this pawn.");
		return;
	}

	z = ResolveZone(w, kind, zone);
	if (z < 0)
	{
		ClientMessage("Nothing to treat.");
		return;
	}
	w.BeginUse(kind, z);
}

// A zone name, a zone index, or `auto`/empty for whatever needs it most.
function int ResolveZone(TarkovHealth w, int kind, string zone)
{
	local string s;

	s = caps(zone);

	if (s == "HEAD")                      return 0;
	if (s == "THORAX" || s == "CHEST")    return 1;
	if (s == "STOMACH" || s == "GUT")     return 2;
	if (s == "LARM" || s == "LEFTARM")    return 3;
	if (s == "RARM" || s == "RIGHTARM")   return 4;
	if (s == "LLEG" || s == "LEFTLEG")    return 5;
	if (s == "RLEG" || s == "RIGHTLEG")   return 6;

	if (s == "0") return 0;
	if (s == "1") return 1;
	if (s == "2") return 2;
	if (s == "3") return 3;
	if (s == "4") return 4;
	if (s == "5") return 5;
	if (s == "6") return 6;

	return Worst(w, kind);
}

// Which zone this item would do the most good on. Vitals first -- a bleeding
// thorax is what kills you, and a man will reach for his chest before his
// shin.
function int Worst(TarkovHealth w, int kind)
{
	local int i, best, bestScore, score;

	best = -1;
	bestScore = 0;

	for (i = 0; i < 7; i++)
	{
		score = 0;

		switch (kind)
		{
			case USE_BANDAGE:
				if (w.Bleed[i] > 0)
					score = 10 + w.Bleed[i];
				break;
			case USE_TOURNIQUET:
				if (w.Bleed[i] == 2)
					score = 10;
				break;
			case USE_SPLINT:
				if (w.bFractured[i] && !w.bBlacked[i])
					score = 10;
				break;
			case USE_SURGERY:
				if (w.bBlacked[i] && (i > 1))
					score = 10;
				break;
			case USE_PAINKILLER:
				return 1;
		}

		if (score <= 0)
			continue;

		// Vitals, then the rest in zone order.
		if (i <= 1)
			score += 5;

		if (score > bestScore)
		{
			bestScore = score;
			best = i;
		}
	}
	return best;
}

// Cached per pawn -- see the same function in TarkovHUD.uc for why this is
// `AllActors` and why that is cheap.
function TarkovHealth FindWounds()
{
	local TarkovHealth h;

	if (Pawn == None)
		return None;
	if (Cached != None && Cached.Host == Pawn)
		return Cached;

	foreach AllActors(class'TarkovHealth', h)
	{
		if (h.Host == Pawn)
		{
			Cached = h;
			return h;
		}
	}
	return None;
}

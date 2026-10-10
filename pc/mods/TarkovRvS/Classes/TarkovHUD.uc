//=============================================================================
// TarkovHUD -- the limb panel.
//
// Seven lines of text, colour-coded, in the corner: which zone, how much of
// it is left, and whether it is bleeding, broken or gone. Plus what is left
// in the medical kit.
//
// WHY TEXT AND NOT TARKOV'S LITTLE MAN. Drawing the silhouette would need a
// texture, and a texture would need a `.utx` of our own, which would need
// art, which would need the mod to ship binary assets before anybody has
// confirmed the health model works at all. Text needs the font the game
// already has. The silhouette is a better second version of this file; it is
// not a better first one.
//
// WHY THIS IS THE PART MOST LIKELY TO BE DECLINED. Only one class can own the
// HUD, and two of the things commonly installed alongside Raven Shield --
// OpenRVS's render fix and SupplyDrop -- own it to fix first-person weapon
// rendering. TarkovInjector refuses to take the HUD off another mod rather
// than silently undoing its fix, so on such an install this panel never
// appears and `bAnnounceStateChanges` carries the information as console
// messages instead. That is deliberate: a limb model you cannot see still
// works, a weapon that renders wrong is unplayable.
//
// To have both, make this class extend theirs instead of `R6HUD` -- the
// drawing below does not care what it inherits.
//=============================================================================
class TarkovHUD extends R6HUD
	config(TarkovRvS);

var TarkovHealth Cached;
var Font PanelFont;
var bool bFontTried;

simulated event PostRender(Canvas C)
{
	Super.PostRender(C);

	if (!class'TarkovConfig'.default.bDrawHealthPanel)
		return;
	if (Level.m_bInGamePlanningActive)
		return;

	DrawWoundPanel(C);
}

function DrawWoundPanel(Canvas C)
{
	local TarkovHealth w;
	local int i;
	local float x, y, line, scale;
	local color col;

	w = FindWounds();
	if (w == None || C == None)
		return;

	if (!bFontTried)
	{
		bFontTried = true;
		// The game's own UI typeface, from `textures\R6Font.utx`. MayFail is
		// set, so a renamed font costs us the panel and not the session.
		PanelFont = Font(DynamicLoadObject("R6Font.Rainbow6_12pt",
			class'Font', true));
	}
	if (C.Font == None)
	{
		if (PanelFont == None)
			return;
		C.Font = PanelFont;
	}

	scale = class'TarkovConfig'.default.PanelScale;
	if (scale <= 0.0)
		scale = 1.0;
	x = C.ClipX * class'TarkovConfig'.default.PanelX;
	y = C.ClipY * class'TarkovConfig'.default.PanelY;
	line = 14.0 * scale;

	for (i = 0; i < 7; i++)
	{
		col = ZoneColour(w, i);
		C.DrawColor = col;
		C.SetPos(x, y);
		C.DrawText(w.StatusLine(i), false);
		y += line;
	}

	col.R = 170; col.G = 170; col.B = 170; col.A = 255;
	C.DrawColor = col;
	C.SetPos(x, y + line * 0.4);
	C.DrawText("kit  bandage" @ w.Bandages $ "  tq" @ w.Tourniquets
		$ "  splint" @ w.Splints $ "  cms" @ w.SurgeryKits
		$ "  pills" @ w.Painkillers, false);

	if (w.UseRemaining > 0.0)
	{
		col.R = 255; col.G = 220; col.B = 90;
		C.DrawColor = col;
		C.SetPos(x, y + line * 1.6);
		C.DrawText("using... " $ int(w.UseRemaining * 10.0) / 10.0 $ "s", false);
	}

	if (w.bVitalCritical)
	{
		col.R = 255; col.G = 0; col.B = 0;
		C.DrawColor = col;
		C.SetPos(x, y + line * 2.8);
		C.DrawText("CRITICAL -- the next hit kills you", false);
	}
}

// Raven Shield's menu palette: cyan is interactive, red is for things that
// are wrong. Both sampled from the game's own art -- see the Art section of
// `research/dossier-rs3.md`.
function color ZoneColour(TarkovHealth w, int zone)
{
	local color c;
	local float frac;

	c.A = 255;

	if (w.bBlacked[zone])
	{
		c.R = 190; c.G = 20; c.B = 35;      // gone
		return c;
	}
	if (w.Bleed[zone] == 2)
	{
		c.R = 255; c.G = 60; c.B = 60;      // heavy bleed
		return c;
	}
	if (w.Bleed[zone] == 1 || w.bFractured[zone])
	{
		c.R = 255; c.G = 190; c.B = 70;     // bleeding or broken
		return c;
	}

	if (w.MaxHp[zone] > 0)
		frac = float(w.Hp[zone]) / float(w.MaxHp[zone]);
	else
		frac = 1.0;

	if (frac >= 0.999)
	{
		c.R = 132; c.G = 211; c.B = 247;    // untouched: the game's own cyan
		return c;
	}

	c.R = 255;
	c.G = 255 - int(110.0 * (1.0 - frac));
	c.B = 180 - int(150.0 * (1.0 - frac));
	return c;
}

// `AllActors` rather than `DynamicActors` because it exists in every Unreal
// Engine 2 build, and the result is cached per pawn, so the search runs when
// the player respawns rather than every frame.
function TarkovHealth FindWounds()
{
	local TarkovHealth h;
	local Pawn p;

	if (PlayerOwner == None)
		return None;

	p = Pawn(PlayerOwner.ViewTarget);
	if (p == None)
		p = PlayerOwner.Pawn;
	if (p == None)
		return None;

	if (Cached != None && Cached.Host == p)
		return Cached;

	foreach AllActors(class'TarkovHealth', h)
	{
		if (h.Host == p)
		{
			Cached = h;
			return h;
		}
	}
	return None;
}

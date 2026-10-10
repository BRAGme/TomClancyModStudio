; ROUTE B -- the descriptor route. Only needed if the server-actor route does
; not fire; see README.md. Copy to <game>\Mods\TarkovRvS.mod, SIBLING of a
; Mods\TarkovRvS\ folder (the folder may be empty, but it must exist, because
; the mod selector scans for the pair).
;
; This route REPLACES the running mod rather than stacking on it, so anything
; another mod changed about the pawn, AI, controller or HUD classes is gone
; while this is selected. The server-actor route does not have that problem,
; which is why it is route A.

[Engine.R6Mod]
Version=1
MinorVersion=60
BuildVersion=412
m_szKeyword=TarkovRvS
m_fPriority=1
m_szCampaignIniFile=RavenShieldCampaign
m_szServerIni=server
m_szUserIni=user
m_ConfigClass=Engine.R6ModConfig
m_bUseCustomOperatives=true

; The four class pointers this whole mod exists to change.
m_DefaultLightPawn=TarkovRvS.TarkovPawnLight
m_DefaultMediumPawn=TarkovRvS.TarkovPawnMedium
m_DefaultHeavyPawn=TarkovRvS.TarkovPawnHeavy
m_DefaultPilotPawn=R6Characters.R6RainbowPilot
m_DefaultRainbowAI=R6Engine.R6RainbowAI
m_PlayerCtrlToSpawn=TarkovRvS.TarkovController
m_GlobalHUDToSpawn=TarkovRvS.TarkovHUD

m_szBackgroundRootDir=Backgrounds
m_szVideosRootDir=Videos
m_szCreditsFile=R6Credits
m_szMenuDefinesFile=R6ClassDefines
m_aDescriptionPackage=R6Description

m_aReticuleList=(m_szReticuleId="WITHWEAPON",m_szReticuleClassName="R6Weapons.R6WithWeaponReticule")
m_aReticuleList=(m_szReticuleId="WITHWEAPONDOT",m_szReticuleClassName="R6Weapons.R6WithWeaponDotReticule")
m_aReticuleList=(m_szReticuleId="CROSS",m_szReticuleClassName="R6Weapons.R6CrossReticule")
m_aReticuleList=(m_szReticuleId="CIRCLE",m_szReticuleClassName="R6Weapons.R6CircleReticule")
m_aReticuleList=(m_szReticuleId="WRETICULE",m_szReticuleClassName="R6Weapons.R6WReticule")
m_aReticuleList=(m_szReticuleId="RIFLE",m_szReticuleClassName="R6Weapons.R6RifleReticule")
m_aReticuleList=(m_szReticuleId="SNIPER",m_szReticuleClassName="R6Weapons.R6SniperReticule")
m_aReticuleList=(m_szReticuleId="CIRCLEDOT",m_szReticuleClassName="R6Weapons.R6CircleDotReticule")
m_aReticuleList=(m_szReticuleId="CIRCLEDOTLINE",m_szReticuleClassName="R6Weapons.R6CircleDotLineReticule")
m_aReticuleList=(m_szReticuleId="DOT",m_szReticuleClassName="R6Weapons.R6DotReticule")
m_aReticuleList=(m_szReticuleId="GRENADE",m_szReticuleClassName="R6Weapons.R6GrenadeReticule")

; Terrorist hunt and the co-op modes first -- they are the ones worth playing
; with a limb model, and the campaign works too.
m_szGameTypes="RGM_StoryMode"
m_szGameTypes="RGM_PracticeMode"
m_szGameTypes="RGM_MissionMode"
m_szGameTypes="RGM_TerroristHuntMode"
m_szGameTypes="RGM_TerroristHuntCoopMode"
m_szGameTypes="RGM_HostageRescueMode"
m_szGameTypes="RGM_HostageRescueCoopMode"
m_szGameTypes="RGM_LoneWolfMode"

[Engine.GameEngine]
CacheSizeMegs=32
UseSound=True
ServerActors=IpDrv.UdpBeacon
ServerPackages=GamePlay
ServerPackages=R6Abstract
ServerPackages=R6Engine
ServerPackages=R6Characters
ServerPackages=R6GameService
ServerPackages=R6Game
ServerPackages=R61stWeapons
ServerPackages=R6Weapons
ServerPackages=R6WeaponGadgets
ServerPackages=R63rdWeapons
ServerPackages=TarkovRvS

import sys, os, json, bisect, collections
sys.path.insert(0, r"C:\Users\Tristan\Documents\GitHub\TomClancyPS2-ModStudio")
from tcps2.iso import Iso
from tcps2.vokes import Vokes, Region
ISO=r"E:\PS2 Games\Tom Clancy's Ghost Recon - Advanced Warfighter (USA).iso"
SCR=r"C:\Users\Tristan\AppData\Local\Temp\claude\C--Users-Tristan-Documents-GitHub\446a2afa-4d08-4557-ab15-203ebf4b9539\scratchpad"
TARGETS=[("vokes0","/VOKES0.IMG"),("vokes2","/VOKES2.IMG"),("menu","/MENU.IMG"),
         ("gr3_1","/GR3_1.IMG"),("gr3_2","/GR3_2.IMG")]
NEEDLES=[b"m_iNbOfTerroristToSpawn",b"m_iNbOfTerro",b"m_bHuntMode",b"GR3DZ_Endure_Wave",
         b"SY_DeathCounter_Wave",b"SY_DeathConter_Wave",b"GR3SquadAI_Wave",b"GR3DeploymentZone",
         b"ScriptTakeDeploymentZone",b"m_CanSpawnTerrorist",b"LatentVehicle_SpawnTerrorists",
         b"Vehicle_SpawnTerrorists",b"AutomaticInitialSpawning",b"m_iRespawnLimit",b"m_iRespawnTimes",
         b"LevelDifficulty",b"m_eMissionDifficulty",b"GR3XBoxAI.ini",b"TWeapon.ini",
         b"SURVIVAL_03B.INI",b"ENEMYHUNT_01B.INI",b"S01_A.INI",b"..\Maps\%s.ini",
         b"SurvivalMissionName",b"HuntMissionName",b"m_bSurvivalGame",b"m_bTerroristHuntGame"]
MAXN=max(len(n) for n in NEEDLES)
iso=Iso(ISO); hits=[]
for key,p in TARGETS:
    ent=iso.entries()[p]; base=ent.lba*2048
    v=Vokes(Region.from_iso(iso,ent))
    starts=sorted((e.offset,e.offset+e.size,e.path) for e in v.files.values())
    sk=[s[0] for s in starts]
    def owner(off):
        i=bisect.bisect_right(sk,off)-1
        return starts[i][2] if i>=0 and starts[i][0]<=off<starts[i][1] else None
    size=v.filesize; fh=open(ISO,"rb"); fh.seek(base)
    CH=1<<24; pos=0; tail=b""
    while pos<size:
        buf=fh.read(min(CH,size-pos))
        if not buf: break
        data=tail+buf; dbase=pos-len(tail)
        for nd in NEEDLES:
            i=data.find(nd)
            while i>=0:
                hits.append(dict(arch=key,needle=nd.decode('latin1'),off=dbase+i,file=owner(dbase+i)))
                i=data.find(nd,i+1)
        tail=data[-(MAXN-1):]; pos+=len(buf)
    fh.close(); print(key,"done, cumulative",len(hits),flush=True)
json.dump(hits,open(os.path.join(SCR,"rawhits2.json"),"w"))
c=collections.Counter((h["needle"],h["arch"]) for h in hits)
print("\n%-28s %-8s %s"%("needle","archive","hits"))
for (n,a),k in sorted(c.items()): print("%-28s %-8s %d"%(n,a,k))
print("\nZERO-HIT needles:", [n.decode() for n in NEEDLES if not any(h["needle"]==n.decode('latin1') for h in hits)])

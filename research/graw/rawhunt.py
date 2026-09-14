import sys, os, json, bisect
sys.path.insert(0, r"C:\Users\Tristan\Documents\GitHub\TomClancyPS2-ModStudio")
from tcps2.iso import Iso
from tcps2.vokes import Vokes, Region
ISO = r"E:\PS2 Games\Tom Clancy's Ghost Recon - Advanced Warfighter (USA).iso"
SCR = r"C:\Users\Tristan\AppData\Local\Temp\claude\C--Users-Tristan-Documents-GitHub\446a2afa-4d08-4557-ab15-203ebf4b9539\scratchpad"
TARGETS=[("vokes0","/VOKES0.IMG"),("vokes2","/VOKES2.IMG"),("menu","/MENU.IMG"),
         ("gr3_1","/GR3_1.IMG"),("gr3_2","/GR3_2.IMG")]
NEEDLES=[b"m_iNbToSpawn",b"m_NumberInWave",b"m_bHuntFromStart",b"NbToSpawn",b"NumberInWave",
         b"HuntFromStart",b"R6DZoneWave",b"GR3DZoneWave",b"DZoneWave",b"ScriptSpawnTerrorists",
         b"SpawnTerrorists",b"DeploymentZone",
         # item-5 extras
         b"Survival",b"SurvivalMode",b"B_SurvivalMode",b"EnemyHunt",b"HuntMode",b"TERROHUNT",b"SHOOTHUNT",
         b"Survival_03b",b"Survival_05b",b"Survival_09A",b"Survival_S11B",b"Survival_S12A",
         b"EnemyHunt_01b",b"EnemyHunt_02a",b"EnemyHunt_04b",b"EnemyHunt_06b",b"EnemyHunt_10a"]
MAXN=max(len(n) for n in NEEDLES)
iso = Iso(ISO)
hits=[]
for key,p in TARGETS:
    ent=iso.entries()[p]; base=ent.lba*2048
    v=Vokes(Region.from_iso(iso,ent))
    starts=sorted((e.offset,e.offset+e.size,e.path) for e in v.files.values())
    sk=[s[0] for s in starts]
    def owner(off):
        i=bisect.bisect_right(sk,off)-1
        if i>=0 and starts[i][0]<=off<starts[i][1]: return starts[i][2]
        return None
    size=v.filesize
    fh=open(ISO,"rb"); fh.seek(base)
    CH=1<<24; pos=0; tail=b""
    while pos<size:
        n=min(CH,size-pos); buf=fh.read(n)
        if not buf: break
        data=tail+buf; dbase=pos-len(tail)
        for nd in NEEDLES:
            i=data.find(nd)
            while i>=0:
                off=dbase+i
                hits.append(dict(arch=key,needle=nd.decode(),off=off,file=owner(off)))
                i=data.find(nd,i+1)
        tail=data[-(MAXN-1):] if MAXN>1 else b""
        pos+=len(buf)
    fh.close()
    print(key,"scanned",size,"bytes; cumulative hits",len(hits),flush=True)
json.dump(hits,open(os.path.join(SCR,"rawhits.json"),"w"))
import collections
c=collections.Counter((h["arch"],h["needle"]) for h in hits)
for k,n in sorted(c.items()): print(k,n)

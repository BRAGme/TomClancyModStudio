# The Sum of All Fears (SLES-511.80) — networking / LAN co-op feasibility

Companion to `code.md`. Same load map, same evidence rules: every VA below was
machine-computed with `file_offset = VA - 0x00100000 + 0x80` and re-read from the
file, every "0 hits" is labelled with the method that produced it, and nothing
here was inferred from a symbol table (SOAF has none).

**Outcome up front — answer to "can SOAF do LAN co-op with its own code?"**

The verdict is **(b) reachable only with new code injection, not by immediate-word
patching — but far less is missing than expected, and the target transport is
i.Link (IEEE-1394), not Ethernet.**

Nothing was compiled out of the middle of the stack. SOAF's executable contains a
complete, live, three-layer multiplayer stack: the Red Storm message bus, a
*concrete* network-manager singleton (not just an interface), a protocol-factory
registry that registers two transports, and an **i.Link packet transport with
fragmentation, an IOP RPC client, and the literal service tag `GRPS2`**. The
matching IOP-side modules (`ILINK.IRX`, `ILSOCK.IRX`) ship on the retail disc.

Three things are missing, all verified:

1. **The IOP side is never started.** All 24 `sceSifLoadModule` call sites in the
   entire executable were enumerated; they load six modules and none is a network
   module.
2. **The i.Link RPC client is never bound.** All 11 `sceSifBindRpc` call sites
   were enumerated; none binds the i.Link client, and `sceSifBindRpc`'s address
   appears in no data word anywhere in the file (so there is no indirect bind).
3. **The multiplayer menu screens do not exist as data.** `MULTI_PREGAME`,
   `MULTI_SERVER_SETUP`, `CLIENT_JOIN`, `MPAFTER_ACTION` and `CHATBAR` are live
   string literals in the ELF but occur **zero** times across all 2,751 files in
   `MENU.IMG` + `SOAF.IMG`.

There is **no IP/Ethernet path at all** — that half genuinely is absent, and
`DEV9.IRX`/`SMAP.IRX` are not on the disc.

---

## 0. A method correction that matters

`rsetool.py strings` only emits a printable run when the run is terminated by
`\0`. Every `printf`-style debug string in this engine ends in `\n`, so **every
one of them is invisible to `strings`/`grepstr`.** That is how an entire i.Link
transport layer survived a first-pass string hunt with zero hits for `ilink`.

All string evidence below was re-extracted with a corrected scan that treats
`\x09\x0a\x0d` as printable:

```python
re.finditer(rb'[\x20-\x7e\x09\x0a\x0d]{4,}', img.data)
```

48,670 runs, versus 18,864 from the NUL-terminated scan — **29,806 runs, 61 % of
the string pool, were missing.** Any earlier SOAF negative that rests on
`grepstr` alone should be re-tested with this scan before being trusted. (The
`code.md` negatives for split-screen and for `Recruit/Veteran/Elite` were
re-tested here and still hold; see §7.)

---

## 1. Question 1 — what network transport does the executable contain?

### 1.1 What ships in `MODULES/` on the disc

`E:/PS2 Games/Sum of All Fears, The (Europe) (En,Fr,De,Es,It)/MODULES/`, 22
files, all dated 10 Sep 2002. Identity strings read from each module's header:

| file | bytes | module name string | role |
|---|---|---|---|
| `ILINK.IRX` | 141,493 | `iLINK_Driver` | IEEE-1394 link-layer driver (`link1394`, `LinkLk.c`, `LinkPnp.c`, `LinkTr.c`, `NODE-ID: 0x%03x:%02x`, `PHY-PACKET(0x%08x)`, `link chip revision: %d`) |
| `ILSOCK.IRX` | 15,545 | `iLINK_Socket` | socket layer over i.Link (`sock_lock_init(): CreateEventFlag()failed %d`) |
| `ILSAMPLE.IRX` | 15,574 | `iLINK_Server` | exports `sceILsockInit/Open/Bind/Connect/Send/Recv/SendTo/RecvFrom/Close/Reset`, `sce1394SbNodeId`, `sceSifRegisterRpc` |
| `INET.IRX` | 118,005 | `INET_service` | SCE libnet IP stack |
| `INETCTL.IRX` | 18,653 | `INET_control` | libnet control |
| `NETCNF.IRX` | 47,373 | `NET_configuration` | network-config reader |
| `PPP.IRX` | 99,165 | *(none)* | dial-up PPP |
| `RPC.IRX` | 245,056 | *(imports only)* | **Red Storm's own** sound/disc IOP module — see §1.4 |
| `IOPRP242.IMG` | 252,409 | — | IOP replacement image (module manager + cdvdman + multi-threaded fileio) |
| others | — | `sio2man`, `mcman`, `mcserv`, `mcxman`, `mcxserv`, `padman`, `mtapman`, `libsd`, `sdr_driver`, `USB_driver`, `USB_module_loader`, `IOP_MSIF_rpc_interface` | standard SCE |

**Explicit negative:** `DEV9.IRX` and `SMAP.IRX`/`ENT_SMAP.IRX` are **not present**
in `MODULES/`. Those are mandatory for the PS2 Network Adaptor's Ethernet port,
so the Ethernet/IP path is not shippable from this disc even in principle.

**Explicit negative:** no `.irx`, `.elf` or `.bin` file exists anywhere inside
`SOAF.IMG` or `MENU.IMG`. A full extension census of all 2,751 archive entries
(`research/soaf/filelist.txt`) returns 54 distinct extensions, none of them
executable. So there is no Jungle-Storm-style `online.bin` overlay.

### 1.2 What the executable actually loads — all 24 sites enumerated

The boot module loader is a **fully unrolled straight-line sequence** at
`0x00116D90`–`0x001171E0`, not a table walk, and there is no
`"cdrom0:\MODULES\%s;1"` format string anywhere in the file.

The load wrapper (`sceSifLoadModule`) is at `0x002AED90`. `rsetool callers` gives
**exactly 24 call sites, and that is every module load in the whole ELF**:

| branch | sites | modules |
|---|---|---|
| `cdrom0:` (retail) | `0x116E3C`, `0x116E64`, `0x116E84`, `0x116EAC`, `0x116ECC`, `0x116EF4`, `0x116F14`, `0x116F3C`, `0x116F5C`, `0x116F84`, `0x116FA4`, `0x116FCC` | SIO2MAN, MCMAN, MCSERV, PADMAN, LIBSD, RPC — each with one retry |
| `host0:` (devkit) | `0x11703C` … `0x1171CC` | the same six, lowercase |

The IOP image is loaded separately at `0x00116DD8` and `0x00116FE8` via
`0x002AF290`, whose only two call sites those are:

| VA | string |
|---|---|
| `0053A190` | `cdrom0:\MODULES\IOPRP242.IMG;1` |
| `0053A1B0` | `cdrom0:\MODULES\SIO2MAN.IRX;1` |
| `0053A200` | `cdrom0:\MODULES\MCMAN.IRX;1` |
| `0053A250` | `cdrom0:\MODULES\MCSERV.IRX;1` |
| `0053A2A0` | `cdrom0:\MODULES\PADMAN.IRX;1` |
| `0053A2E0` | `cdrom0:\MODULES\LIBSD.IRX;1` |
| `0053A320` | `cdrom0:\MODULES\RPC.IRX;1` |
| `0053A360`–`0053A4B0` | the seven `host0:modules/...` equivalents |

Case-insensitive count of `irx` in the whole string pool: **12** — exactly the
six `.IRX` filenames × two device branches. `ILINK`, `ILSOCK`, `INET`, `INETCTL`,
`NETCNF`, `PPP`, `DEV9`, `SMAP` appear **nowhere** in the executable, as filenames
or otherwise (raw byte search of the loadable segment for `iLINK`, `INET`,
`ilsock`, `ilink`, `PPP`, `ppp`, `dev9`, `DEV9`, `smap`, `SMAP` — all 0).

**So: the network IRX modules on this disc are a devkit module-folder dump. The
game never loads them.** `MTAPMAN.IRX`, `USBD.IRX`, `MCXMAN.IRX`, `MCXSERV.IRX`
and `SDRDRV.IRX` are unreferenced too, which is what confirms the "whole folder
was copied" reading rather than "networking was cut late".

### 1.3 Contrast: Jungle Storm does load them

JS's main ELF carries a **second** module list that SOAF has no counterpart for:

| JS VA | string |
|---|---|
| `0059E2E0` | `cdrom0:\MODULES\ENT_DEVM.IRX` |
| `0059E300` | `cdrom0:\MODULES\NETCNF.IRX` |
| `0059E350` | `cdrom0:\MODULES\EENETCTL.IRX` |
| `0059E370` | `cdrom0:\MODULES\DEV9.IRX` |
| `0059E390` | `cdrom0:\MODULES\ENT_SMAP.IRX` |
| `0059E3B0` | `cdrom0:\MODULES\EZNETCNF.IRX` |
| `0059E3D0`–`0059E470` | the six `host0:\modules\...` equivalents |
| `0059E490` | `gsconnect.ubisoft.com` |
| `0057D690` | `cdrom0:\MODULES\DNAS280.IMG;1` |

and JS's `online.bin` overlay carries `%d.%d.%d.%d` (×3), `[inet_ntoa error]`,
`SENDTOALLPLAYERS`, `SENDTOOTHERPLAYERS`, `SENDTOPLAYERGROUP`, `SENDTOPLAYER`,
`SENDTOSERVER`. **None of those appears in SOAF.**

### 1.4 The one non-SCE IOP module SOAF does load is not networking

`RPC.IRX` is Red Storm's own module. Its source paths are all
`Q:\common\utility\rpc_iop\…` — `rpc_iop.c`, `sound_rpc_iop.c`, `sound_iop.c`,
`spu_iop.c`, `adl_iop.c`, `asd_iop.c`, `msx_iop.c`, `trk_iop.c`, `di_rpc_iop.c`,
`di_main.c`. Zero occurrences of `ilink`, `sock`, `inet` or `GRPS2`. It is the
audio-streaming and disc-I/O server, matched by the EE-side `rpc_ee.c`
(`0054A240`) and `sound_rpc_ee.c` (`0054A380`) strings.

### 1.5 The IP/Ethernet layer: clean total negative

Searched in the **corrected** 48,670-run string pool:

| term | hits |
|---|---|
| `sceInet`, `sceIfcfg`, `sceNet`, `libnet`, `ee_net`, `EENET`, `tcpip`, `lwip` | 0 |
| `socket`, `SOCK_`, `AF_INET`, `recvfrom`, `sendto`, `listen`, `inet_addr`, `gethostby` | 0 |
| `%d.%d.%d.%d`, `%u.%u.%u.%u`, `inet_ntoa` | 0 |
| `dev9`, `DEV9`, `smap`, `SMAP`, `DNAS`, `inetctl`, `netcnf` | 0 |

Ghost Recon, which has a full symbol table, also has **zero** symbols matching
`sceInet|sceIfcfg|sceNet|socket|inet_` — so no Red Storm PS2 title in this set
ever linked the SCE IP library into its main executable.

### 1.6 The i.Link transport that *is* there

This is the finding the first-pass string scan missed. Code at
**`0x00518500`–`0x005195B0`**, reachable from the network manager, with these
literals (all `\n`-terminated, hence invisible to `rsetool strings`):

| VA | string | referenced from |
|---|---|---|
| `00556EB0` | `ILink:Out of  IOBuffer\n` | `0x5188FC`, `0x518AFC` |
| `00556ED0` | `error, recv length too short %d %d\n` | `0x518554`, `0x51862C` |
| `00556F00` | `Recved nonfraged packet %d\n` | `0x5185E4` |
| `00556F20` | `Recved fraged packet %d %d %d\n` | `0x5187B4` |
| `00556F40` | `SendPacket %d\n` | `0x518880` |
| `00556F90` | `Recved %d\n` | `0x51912C` |
| `00539DC8` | `GRPS2` | `0x5191E8`, `0x519338`, `0x519458` |

`GRPS2` — "Ghost Recon PS2" — is the i.Link service/application tag, another
artefact of the shared engineering documented in `code.md` (`host0:ike/gr.elf`).

It talks to the IOP by SIF RPC. `sceSifBindRpc` and `sceSifCallRpc` were located
in SOAF by masked-signature matching from Ghost Recon's symbol table:

| GR symbol | GR VA | SOAF VA | match |
|---|---|---|---|
| `sceSifBindRpc` | `0x00414AA0` | `0x002AD7A0` | 79/80 (99 %) |
| `sceSifCallRpc` | `0x00414C70` | `0x002AD970` | 122/123 (99 %) |
| `sceSifCheckStatRpc` | `0x00414E60` | `0x002ADB60` | ≥92 % |

The i.Link layer issues **four** `sceSifCallRpc` calls — at `0x00519090`,
`0x005192A0`, `0x005193F4`, `0x00519514` — all on the same RPC client struct
`0x005DA220` with function number `0x80000B8C`, and polls with
`sceSifCheckStatRpc`.

**And it is wired to the network manager.** `0x00517550` (the transport object's
constructor, which installs vtables `0x005652E0` then `0x005658D0`) is called
from exactly two places, **both inside the network-manager implementation**:

```
00374bb0  jal  0x119140          ; operator new(0x20)
00374bc4  jal  0x517550          ; construct i.Link transport, arg2 = 1
...
0037c2bc  jal  0x517550          ; construct i.Link transport at obj+0x10
```

### 1.7 …but it can never run as shipped

Two independent enumerations, both exhaustive:

- **`sceSifBindRpc` (`0x002AD7A0`) has exactly 11 call sites in the whole ELF**,
  and the service ID at each was decoded from the `lui`/`ori` pair:

  | bind site | service ID | subsystem |
  |---|---|---|
  | `0x002AE0DC` | `0x80000003` | IOP heap |
  | `0x002AE3C4` | `0x80000006` | loadfile |
  | `0x002C4A54` | `0x80000592` | cdvdfsv |
  | `0x002C4904` | `0x80000593` | cdvdfsv |
  | `0x002C45EC` | `0x80000595` | cdvdfsv |
  | `0x002C42D4` | `0x80000597` | cdvdfsv |
  | `0x002C4D2C` | `0x8000059A` | cdvdfsv |
  | `0x002C5194` | `0x80000100` | mcserv |
  | `0x002C51E8` | `0x80000101` | mcserv |
  | `0x002C6460` | `0x80000400` | padman |
  | `0x0034C198` | `0x19740310` | Red Storm `RPC.IRX` (sound/disc) |

  **None of them is the i.Link service, and none of them passes `0x005DA220`.**
  The only eight references to `0x005DA220` in the entire file are the four
  `CallRpc` sites and their argument setup, all inside `0x519000`–`0x519600`.

- A 4-byte pointer scan for `0x002AD7A0` over the whole loadable segment returns
  **zero** data words, so `sceSifBindRpc` is not reachable through a function
  pointer either. (Ten byte-offset "hits" for the constant `0x80000B8C` were all
  unaligned coincidences inside instruction streams, at odd addresses.)

So at runtime: `ILINK.IRX`/`ILSOCK.IRX` are never loaded, the RPC client is never
bound, `sceSifCallRpc` on an unbound client fails, and every `SendPacket` is a
no-op. The layer is present and structurally complete; its two ends are not
connected.

---

## 2. Question 4 — which Ghost Recon networking functions are present in SOAF

`portsig.py` masked-signature matching, GR → SOAF. **Controls first**, to
calibrate what a match and a miss mean on this pair:

| GR symbol | GR VA | SOAF VA | match |
|---|---|---|---|
| `__ct__BulletHoleManagerPS2` | `0x46D9B0` | `0x004FD410` | **23/23 (100 %)** |
| `AddOneBulletHole__BulletHoleManagerPS2` | `0x46DAC0` | `0x004FD4C0` | **87/87 (100 %)** |
| `Render__BulletHoleManagerPS2` | `0x46DC20` | `0x004FD620` | 44/45 (98 %) |
| `DisplayBullethole__IkeEffectsMgr` | `0x249610` | `0x00240430` | 118/120 (98 %) |

### 2.1 PRESENT — the message bus, complete

Every one of the eleven `RSGameMessageMgr` methods probed matched, in one
contiguous block:

| GR symbol | GR VA | SOAF VA | match |
|---|---|---|---|
| `IsProcessorRegistered__RSGameMessageMgr` | `0x127A30` | `0x0035A580` | 43/43 (100 %) |
| `HandleBufferMessage__RSGameMessageMgr` | `0x127AE0` | `0x0035A630` | 56/56 (100 %) |
| `ForwardMessage__RSGameMessageMgr` | `0x127C80` | `0x0035A7D0` | 68/69 (99 %) |
| `Shutdown__RSGameMessageMgr` | `0x127E40` | `0x0035A990` | 55/55 (100 %) |
| `Update__RSGameMessageMgr` | `0x127F20` | `0x0035AA70` | 49/50 (98 %) |
| `MasterPost__RSGameMessageMgr` | `0x128010` | `0x0035AB60` | 32/35 (91 %) |
| `MasterSend__RSGameMessageMgr` | `0x1280A0` | `0x0035ABF0` | 22/24 (92 %) |
| `UnregisterMessageProcessor__RSGameMessageMgr` | `0x128100` | `0x0035AC50` | 51/51 (100 %) |
| `RegisterMessageHandler__RSGameMessageMgr` | `0x1281D0` | `0x0035AD20` | 93/93 (100 %) |
| `InitDefaultMessaging__RSGameMessageMgr` | `0x1283B0` | `0x0035AF00` | 140/154 (91 %) |
| `Initialize__RSGameMessageMgr` | `0x1286C0` | `0x0035B210` | 19/19 (100 %) |

### 2.2 PRESENT — session / mode / screen predicates

| GR symbol | GR VA | SOAF VA | match |
|---|---|---|---|
| `InMultiplayerMode__RSGameStateMgr` | `0x131D80` | `0x00364070` | **19/19 (100 %)** |
| `InMultiplayerClientMode__RSGameStateMgr` | `0x131DD0` | `0x003640C0` | **17/17 (100 %)** |
| `InMultiplayerServerMode__RSGameStateMgr` | `0x131E20` | `0x00364110` | **17/17 (100 %)** |
| `InMultiplayerJoinScreen__IkeStateMgr` | `0x183540` | `0x00167AA0` | **17/17 (100 %)** |
| `InMultiplayerSetupScreen__IkeStateMgr` | `0x183310` | `0x00167CD0` | **17/17 (100 %)** |
| `HandleConnectionMessage__RSGameMgr` | `0x119660` | `0x00351530` | 32/35 (91 %) |
| `InitDefaultMessaging__RSGameMgr` | `0x119A30` | `0x003518F0` | 187/211 (89 %) |
| `GetMissionLobby__IkeDataMgr` | `0x164800` | `0x001340C0` | 30/32 (94 %) |
| `GetGameTypeFile__IkeDataMgr` | `0x1647A0` | `0x00134340` | 15/16 (94 %) |
| `GetGameTypeFile__IkeRulesMgr` | `0x17F700` | `0x0014BCC0` | 39/47 (83 %) |
| `WriteText__RSPlayerInfo` | `0x1378C0` | `0x00369890` | 29/33 (88 %) |
| `ProcessLobby__MissionFile` | `0x1D72B0` | `0x001DC790` | 68/79 (86 %) |
| `ProcessShell__MissionFile` | `0x1D73F0` | `0x001DC8D0` | 166/241 (69 %) |
| `NumberOfMultiplayerActors__IkeDataMgr` | `0x16A280` | `0x0012EE70` | 17/21 (81 %) |
| `LoadMultiplayerActorFiles__IkeDataMgr` | `0x169D40` | `0x0012F360` | 37/49 (76 %) |

### 2.3 NOT FOUND by this method

| GR symbol | GR VA | words | result |
|---|---|---|---|
| `HandleLobbyConfigRequest__IkeRulesMgr` | `0x179B00` | 262 | no match at 0.45 |
| `UpdateHostInfo__MultiGameSelect` | `0x2FE0D0` | 357 | no match at 0.45 |
| `LoadLobby__MissionFile` | `0x1D8670` | 112 | no match at 0.45 |
| `GetPlatoonIndexByMultiplayerPlatoon__IkeRulesMgr` | `0x17F7D0` | 94 | no match at 0.45 |
| `DownloadMissionFile__IkeDataMgr` | `0x168FB0` | 82 | no match at 0.55 |
| `DownloadMissionLobbies__IkeDataMgr` | `0x168CD0` | 184 | no match at 0.55 |
| `HandleDownloadMissionFile__IkeDataMgr` | `0x163300` | 27 | no match at 0.55 |
| `HandleDownloadMissionLobbies__IkeDataMgr` | `0x1635F0` | 123 | no match at 0.55 |
| `IsHost__IkeDataMgr` | `0x167330` | 15 | best 8/15 (53 %) — too short to judge |
| `LoadGameTypes__IkeDataMgr` | `0x161800` | 202 | no match at 0.55 — **but see below** |
| `LoadMissionLobbies__IkeDataMgr` | `0x161B30` | 198 | no match at 0.55 |

**`LoadGameTypes` is the calibration case that stops these from being read as
absences.** SOAF's `.GTF` enumerator provably exists: `0x001373B0` is the
function that materialises `mission\*.gtf` (`0053AE22`) at `0x001373E4` and calls
the file-find helper `0x004E57F0`. Yet GR's `LoadGameTypes` scores below 55 %
against it. So for *game-specific* `Ike*Mgr` code, a portsig miss means "the two
games' source diverged", **not** "the function is gone". These rows are therefore
inconclusive, not negative. The high-confidence structural evidence is in §1.7
and §4, which does not depend on cross-title similarity.

### 2.4 Neither game has a concrete network manager *by GR's names* — but SOAF does

GR's symbol table contains only three `NetworkMgr` symbols, all plug-in points:

```
00147580   8 FUNC GLOBAL SetNetworkMgr__10IkeGameMgrFP14IIkeNetworkMgr
00147700   8 FUNC GLOBAL GetNetworkMgr__10IkeGameMgrFv
005E03F8   4 OBJECT GLOBAL mINetworkMgr__13IRSNetworkMgr
```

No implementation class, no `__vt__*Net*` vtable — Ghost Recon PS2's multiplayer
is split-screen over the local message bus with `mINetworkMgr == NULL`. GR also
has **no** `RSConnection` or `RSAddress` symbols at all, and no `RSConnection`/
`RSAddress` strings.

SOAF and Jungle Storm both **do** carry the `RSAddress`/`RSConnection` layer.
Byte-identical string sets in each:

| SOAF VA | JS VA | string |
|---|---|---|
| `00556CB8` | `0059E5D0` | `Non-Client ID` |
| `00556CD0` | `0059E600` | `Uninitialized RSAddress` |
| `00556CF0` | `0059E620` | `TCP/IP address of ` |
| `00556D08` | — | ` Port ` |
| `00556D20` | `0059E650` | `UDP address of ` |
| `00556D30` | `0059E660` | `Illegal RSAddress` |
| `00556D90` | `0059E780` | `RSConnection (` |
| `00556DB0` | — | `, Connecting to ` |
| `00556DD0` | — | `, Connected to ` |
| `00556E20` | — | `, Filtering to only allow messages from ` |
| `00556E80` | `0059E870` | `Uninitialized RSConnection Object` |

`RSAddress::ToString` is at **`0x0050EF20`** and its disassembly gives the class
layout outright: `+0x04` = address-type enum (`0` uninitialised → "Uninitialized
RSAddress", `1` → "TCP/IP address of ", `2` → "UDP address of ", anything else →
"Illegal RSAddress"), `+0x08` and `+0x0C` = address words / hostname pointer,
`+0x12` = `u16` port formatted with `%d` (`00556D10`). `RSConnection::ToString`
is at `0x00515C00`+.

---

## 3. Question 2 — are the multiplayer menu entries unreachable, or absent?

**Both, at different layers: the UI *states* are in code, the UI *screens* are
not on the disc, and the localised UI *text* survives.**

### 3.1 The screen-state name table in the ELF (`0x00540BAD`–`0x00540D91`)

| VA | string |
|---|---|
| `00540BAD` | `ACTION_INFO` |
| `00540BB9` | `HELP_INFO` |
| `00540BC4` | `ACTION_MENU_PS2` |
| `00540BD4` | `OPTIONS` |
| `00540BDC` | `SAVE_MENU` |
| `00540BE6` | `VARTUNE` |
| `00540BEE` | `DIALOG` |
| `00540BF5` | `MAIN_PS2` |
| `00540BFE` | `SINGLE_BRIEFING` |
| `00540C0E` | `AFTER_ACTION` |
| **`00540C1B`** | **`MPAFTER_ACTION`** |
| **`00540C2A`** | **`MULTI_PREGAME`** |
| `00540C38` | `SHELL_MENU` |
| **`00540C43`** | **`MULTI_SERVER_SETUP`** |
| `00540C56` | `SHELL_MENU2` |
| `00540C62` | `PS2MENU_HELPTEXT` |
| `00540C73` | `MAIN` |
| **`00540CFA`** | **`CLIENT_JOIN`** |
| **`00540D06`** | **`MPAFTER_ACTION_PS2`** |
| `00540D19` | `REPLAY` |
| `00540D20` | `AFTER_ACTION_RECORD_PS2` |
| `00540D38` | `AFTER_ACTION_PS2` |
| **`00540D49`** | **`CHATBAR`** |
| **`00540D51`** | **`MULTI_PREGAME_PS2`** |
| `00540D63` | `CONSOLE` |
| `00540D6B` | `ike.res` |
| `00540D73` | `PS2_PRESS_START` |
| `00540D83` | `GAME_OVER_PS2` |

### 3.2 The screen manifest on the disc has none of them

`SCREEN.TXT` (336 bytes, byte-identical in `MENU.IMG` and `SOAF.IMG` — same
`0x00013484` name hash), read out via `research/soaf/soafimg.py`, in full:

```
GAMEINFO_MAIN_PS2   GAMEINFO_PS2        MAIN_PS2            OPTIONSCONTROL_PS2
OPTIONSGAME_PS2     OPTIONSSCREEN_PS2   OPTIONSSOUND_PS2    PS2_PRESS_START
SELECTLANGUAGE_PS2  SF3DMODEL_PS2       SFMUSIC_PS2         SFPICTURE_PS2
SINGLE_BRIEFING_PS2 SPECIALFEATURE_PS2  NEW_CAMPAIGN_PS2    QUICK_MISSION_PS2
QUICK_MISSION_PARAMETER_PS2             RESUMECAMPAIGN_PS2  TRAINING_PS2
```

19 names, all single-player.

**Exhaustive archive search** — every one of the 331 files in `MENU.IMG` and 2,420
in `SOAF.IMG` was decompressed and byte-searched:

| needle | hits across all 2,751 files |
|---|---|
| `MULTI_PREGAME` | **0** |
| `MULTI_SERVER_SETUP` | **0** |
| `CLIENT_JOIN` | **0** |
| `MPAFTER_ACTION` | **0** |
| `CHATBAR` | **0** |
| `MULTIPLAYER` | 18 (in `*_STRINGS.RES`, `MODSCONT.TXT`, `EXPORT_PREPARE.CONFIG`) |
| `Multiplayer` | 10 |
| `Coop` | 36 |

So the multiplayer screens have no definition data anywhere on the disc. This is
the hard blocker on the UI side, and it cannot be fixed by patching the
executable.

### 3.3 The localised multiplayer text *does* survive

`EN_STRINGS.RES` (96,343 bytes) still contains, in the shipped shell string
table:

`MULTIPLAYER SETUP` · `SINGLEPLAYER SETUP` · `AFTER-ACTION` · `WAITING` ·
`Multiplayer` (a main-menu item, sitting between `Campaign` and `REPLAYS`) ·
`MULTIPLAYER` (an options tab, between `MODS` and `Sound`) ·
`QUICK MISSIONS AND MULTIPLAYER` · `Mission Coop` · `Firefight Coop` ·
`Last Man` · `Search and Rescue` · `Ready` · `Not Ready` · `Voice On` ·
`Voice Off`

Same in `DE_`, `ES_`, `FR_`, `IT_` and `STRINGS.RES`. `MODSCONT.TXT` declares
`MULTIPLAYER  "Server-Client"`.

And `LOADING13.TXT` states the shipped substitute outright:

> Multiplayer maps can also be played in Lone Wolf and Firefight modes. Simply go
> to the Quick Mission menu and select the Lone Wolf…

### 3.4 `GAME.LOG` — a PC debug log left on the retail PS2 disc

`SOAF.IMG:/GAME.LOG`, 175,961 bytes, from `f:\soaf\soaf_pc\code\soaf code\soaf\release\`,
`The Sum of All Fears (DEBUG)  version = 1.0.4.10(0)`, on a 550 MHz Pentium III /
GeForce 256 / Windows 2000 box. Relevant lines:

```
IkeDataMgr::LoadGameTypes: Loaded 13 items
IkeDataMgr::LoadMissionLobbies: Loaded 25 items
IkeDataMgr::LoadKitRestrictions: Loaded 7 items
MPPCSetup: Could not find key SOFTWARE\Ubi Soft\Game Service: 2
RSGameStateMgr: ChangeGameState() - Phase is Shell - Mode is SinglePlayer
RSNetworkMgr::GetPlayerInfoFromSystemID: Someone asked for the PlayerInfo for
    SystemID 0 but I don't have any such system id.
[ RSGameInfo:  mGameName = [unnamed game] mVersion = … mMapName = M02 Militia
    Compound … mMultiplayerGameType = Miss…
[ IkeGameInfo: ] … Dedicated Server: false … Lobby Configuration:
    kLobbyMultiplayerTeam  MOTD:  Respawn Type: 0  Time Limit: 900 …
    Server Setup Semaphore holder: -1 … Mission lobby index: 1
    Game Type File Index: None
RSNetworkMgr: RSNetworkMgr::Shutdown() IN
RSNetworkMgr: RSNetworkMgr::Shutdown() OUT
```

Three things this establishes: the class is called **`RSNetworkMgr`**; it is
instantiated and shut down **even in a single-player session**; and the
`RSGameInfo` dump format in that log is byte-for-byte the same string table that
sits in SOAF's PS2 ELF at `0x0054A822`–`0x0054A955` (` mGameName = `,
` mMultiplayerGameType = `, ` mMaxPlayers = `, `mPlayerName[`,
` mObserverPasswordRequired = ` …). `13 items` matches the 13 `.GTF` files on the
PS2 disc exactly.

### 3.5 The `<Multiplayer>` options block was removed from the PS2 serialiser

`SOAF.IMG:/OPTIONS.XML` (a PC options file shipped on the PS2 disc) contains:

```xml
<Multiplayer>
  <ChatMsg text = "" team = "false"/>    ... ×10
  <MPGameName>---</MPGameName>
  <MOTD>---</MOTD>
  <JoinPort>2346</JoinPort>
  <AnnouncePort>2347</AnnouncePort>
  <BehindFirewall>FALSE</BehindFirewall>
  <PreferredIP>DEFAULT</PreferredIP>
  <RemoteServerAccess>FALSE</RemoteServerAccess>
  <RemoteServerPasswd/>
  <GameSynchTimeout>600.000000</GameSynchTimeout>
  <CharIndex>0</CharIndex>
  <KitIndex>0</KitIndex>
  <IPAddress/>                           ... ×12
</Multiplayer>
<PlayerName>defPlayr</PlayerName>
```

All eleven of those tag names are present as string literals in the PS2 ELF:

| VA | tag |
|---|---|
| `0053B43F` | `IPAddress` |
| `0053B449` | `ChatMsg` (`+text` `0053B451`, `+team` `0053B456`) |
| `0053B45B` | `MPGameName` |
| `0053B466` | `MOTD` |
| `0053B46B` | `JoinPort` |
| `0053B474` | `InfoPort` |
| `0053B47D` | `AnnouncePort` |
| `0053B48A` | `BehindFirewall` |
| `0053B499` | `PreferredIP` |
| `0053B4A5` | `RemoteServerAccess` |
| `0053B4B8` | `RemoteServerPasswd` |
| `0053B4CB` | `GameSynchTimeout` |

**and every one of them is dead.** Zero `lui`/`addiu` code references and zero
4-byte pointers anywhere in the file.

The control that makes this a real negative rather than a method failure: SOAF
has a second name registry — an 8-byte-stride `{const char* name; u32 0}` table
at **`0x005362B0`–`0x00536380`**, walked out and read back in full:

```
options.xml, defPlayr, OptionsFile, XBoxMode, PlayerName, Graphics, FullScreen,
VideoResolution, Width, Height, BitDepth, ShowFrameRate, UsePrimaryDisplay,
UseDisplayDeviceGuid, DisplayDeviceGuid, CompressTextures, Sound, MasterSwitch,
EffectsSwitch, MusicSwitch, VoiceSwitch, MasterVolume, EffectsVolume,
MusicVolume, VoiceVolume, AlternateCache, UseEAX
```

**27 entries, and the table stops at `UseEAX`.** Every non-multiplayer XML tag
has exactly one pointer into it (`VideoResolution` → `0x5362E8`, `Sound` →
`0x536330`, `UseEAX` → `0x536380`, …) and, like the multiplayer names, **zero**
`lui`/`addiu` xrefs — so "no code xref" is normal for this whole class of string
and proves nothing on its own. What proves it is the table membership:
`Multiplayer` (`0054B489`) is **not in the table**, and neither are its eleven
children, while their immediate string-pool neighbours on both sides are in the
*other* registry (`BulletHoleMax` → `0x525740`, `CharacterModelDetail` →
`0x5257A8`, `ZBufferBits` → `0x525798`, `Gameplay` → `0x5257B0`, `RecordGame` →
`0x5257B8`, `ShowIntro` → `0x5257C0`, `IFFType` → `0x5257D8` — all in the
51-entry table at `0x005256B8` documented in `code.md`).

GR's symbol table names the functions that were dropped:
`WriteMultiplayerNodes__9RSOptions` / `ReadMultiplayerNode__9RSOptions`
(`0x1362A0` / `0x1368D0`) and `WriteMultiplayerNodes__10IkeOptions` /
`ReadMultiplayerNode__10IkeOptions` (`0x174B60` / `0x174B90`).

---

## 4. Question 3 — how the multiplayer game type is selected, and what gates it

### 4.1 The `RSGameInfo` dump, and the one xref to ` mMultiplayerGameType = `

`0x0054A88D` = ` mMultiplayerGameType = `, referenced from exactly one site,
`0x003582A0`, inside `RSGameInfo::WriteText` — sitting in the same string block
(`0x0054A7C0`–`0x0054A955`) as `[ RSGameInfo: `, ` mGameName = `,
` mMaxPlayers = `, `mPlayerName[`, ` mObserverPasswordRequired = `. This is the
debug serialiser, not the selector, and it matches the `GAME.LOG` line verbatim.

### 4.2 The `.GTF` loader exists and is reached

`0x0053AE22` = `mission\*.gtf`, referenced once, at `0x001373E4`, inside the
function starting at **`0x001373B0`**, which calls the archive file-find helper
`0x004E57F0` / `0x004E5720`. Its sibling `0x0053AE14` = `mission\*.mis` is
referenced at `0x00137164`. So both the mission enumerator and the game-type
enumerator are live code.

The `.GTF` XML tag names are registered in the tag table at `0x00526608`+
(`GameTypeFile` → `0x526608`), and the `MissionFile`/`Shell` tag names in the
block at `0x00526920`–`0x005269C0`:

| tag | VA | table slot |
|---|---|---|
| `Lobby` | `0053EDE0` | `0x526920` |
| `MissionFile` | `0053EDE8` | `0x526928` |
| `Shell` | `0053EDF8` | `0x526930` |
| `Bases` | `0053EE10` | `0x526940` |
| `CentralArea` | `0053EE18` | `0x526948` |
| **`Coop`** | **`0053EE28`** | **`0x526950`** |
| `GameTypes` | `0053EE50` | `0x526968` |
| `LobbyCfg` | `0053EE60` | `0x526970` |
| `Points` | `0053EE98` | `0x526998` |
| `Recon` | `0053EEA0` | `0x5269A0` |
| `SinglePlayer` | `0053EEA8` | `0x5269A8` |
| `Solo` | `0053EEB8` | `0x5269B0` |
| `Team` | `0053EEC0` | `0x5269B8` |
| `RequiresUnlocking` | `0053EED0` | `0x5269C0` |

**This is the sharpest contrast in the whole investigation.** The multiplayer
*mission metadata* tags — `Coop`, `GameTypes`, `LobbyCfg`, `SinglePlayer`,
`Solo`, `Team` — are all still registered and therefore still parsed. The
multiplayer *options* tags (§3.5) were all removed. Whoever cut multiplayer from
this port cut the options block and the screens, and left the mission/game-type
data pipeline intact.

### 4.3 What the data says the gate is: `LobbyCfg`

All 13 `.GTF` files read out of `SOAF.IMG`:

| file | `LobbyCfg` | `MaxNumberSinglePlayerMembers` | `Insertion` |
|---|---|---|---|
| `(SP) FIREFIGHT.GTF` | **1** | 3 | 2 |
| `(SP) LONE WOLF.GTF` | **1** | 1 | 2 |
| `(COOP) FIREFIGHT.GTF` | **2** | 3 | 2 |
| `(COOP) RECON.GTF` | **2** | 3 | 2 |
| `(SOLO) CATS_AND_MOUSE.GTF` | **3** | 3 | 0 |
| `(SOLO) HAMBURGER HILL.GTF` | **3** | 3 | 0 |
| `(SOLO) LAST MAN STANDING.GTF` | **3** | 3 | 0 |
| `(SOLO) SHARPSHOOTER.GTF` | **3** | 3 | 0 |
| `(TEAM) DOMINATION.GTF` | **4** | 3 | 1 |
| `(TEAM) HAMBURGER HILL.GTF` | **4** | 3 | 1 |
| `(TEAM) LAST MAN STANDING.GTF` | **4** | 3 | 1 |
| `(TEAM) SEARCH AND RESCUE.GTF` | **4** | 3 | 1 |
| `(TEAM) SIEGE.GTF` | **4** | 3 | 1 |

`LobbyCfg` 1 = single-player, 2 = co-op, 3 = free-for-all, 4 = team — and GR's
symbol table plus `GAME.LOG` confirm the enum name (`kLobbyMultiplayerTeam`,
`GetLobbyConfig__11IkeGameInfo`, `HandleLobbyConfigRequest__11IkeRulesMgr`,
`kMsgID_LobbyConfigRequest`, `kMsgID_LobbyConfigAssign`). The string
`LobbyConfig` exists in the PS2 ELF at `0x0054D8B3`.

**Explicit negative:** the literal prefixes `(COOP)`, `(SOLO)`, `(SP)`, `(TEAM)`
do not appear in the ELF at all (0 hits in the corrected string pool). The game
types are enumerated from the archive by wildcard, so the set offered is decided
by whatever code filters on `LobbyCfg` — which was not isolated this pass.

### 4.4 The six MP maps are marked neither single-player nor co-op

`MP01_RSE.MIS` `<Shell>` in full:

```xml
<Shell>
  <Environment>rse.env</Environment>   <MapShots>mp01_rse_shots.rsb</MapShots>
  <MapName>MP01 RSE Offices</MapName>  <MapNameId>25165824</MapNameId>
  <Name>MP01 RSE</Name>                <NameId>25165825</NameId>
  <GameTypes>1</GameTypes>             <Points>1</Points>
  <Bases>1</Bases>                     <CentralArea>1</CentralArea>
  <Recon>1</Recon>
</Shell>
```

No `<SinglePlayer>` and no `<Coop>` tag. Every one of the eleven campaign
missions (`M01_TV STATION.MIS` … `M11_DRESSLERS_ESTATE.MIS`) has both:
`<SinglePlayer>1</SinglePlayer>` and `<Coop>1</Coop>`.

So the campaign missions are all flagged co-op-capable in shipped data, and the
six MP maps advertise `GameTypes/Points/Bases/CentralArea/Recon` support without
claiming either mode. The six are `MP01_RSE`, `MP02_ATHLETE`, `MP03_KILLHOUSE`,
`MP04_PARKINGLOT`, `MP05_RESERVOIR`, `MP06_ARTGALLERY`, plus MP player models
`MP2_/MP3_/MP4_MALE`/`FEMALE` with LOD1/LOD2.

---

## 5. The network manager in SOAF: concrete, instantiated, and wired

This is the part that separates SOAF from Ghost Recon, and it was established
without any cross-title signature matching.

### 5.1 Locating the singleton slot by structural correspondence

GR's `MasterPost__16RSGameMessageMgr` (`0x00128010`) makes three virtual calls
through three named globals. SOAF's `0x0035AB60` is instruction-for-instruction
the same function with three different globals in the same three slots:

| slot | GR global | GR symbol name | SOAF global |
|---|---|---|---|
| 1st (`vt+0x48`) | `0x005DFF00` | `mIRulesMgr__15IRSGameRulesMgr` | `0x005B7A78` |
| 2nd (`vt+0x24`) | `0x005E03F8` | **`mINetworkMgr__13IRSNetworkMgr`** | **`0x005B8258`** |
| 3rd (`vt+0x18`) | `0x005DFDD8` | `mIMessageMgr__17IRSGameMessageMgr` | `0x005B7900` |

So **SOAF's `IRSNetworkMgr::mINetworkMgr` is at VA `0x005B8258`**, and a second
interface sub-object pointer sits at `0x005B8260`.

### 5.2 A real object is constructed and installed

`0x005B8258` has **64** references; 62 are loads and **two are stores**:

- `0x0016BF90` — `sw $a1, -0x7da8($at)`: a trivial setter (GR's
  `SetNetworkMgr__10IkeGameMgrFP14IIkeNetworkMgr`), one of three adjacent
  one-line setters that also write `0x005D7AD8` and `0x005B7900`.
- `0x00501094` — inside a **singleton factory at `0x00500FD0`**:

```
00500fe0  lw    $v0, 0x7ad0($at)      ; if (g_instance) return it
00500fe4  bnez  $v0, 0x501098
00500fec  jal   0x50a160
00500ff4  jal   0x119140              ; operator new(0x928 = 2344 bytes)
00500ff8  addiu $a0, $zero, 0x928
00501008  sw    0x00565570, ($s0)     ; base vtable
00501014  sw    0x0056E5A0, ($s0)     ;   then
0050101c  jal   0x378ab0              ; base ctor on (this+8)
0050102c  sw    0x0056E2D0, ($s0)     ; final vtable
00501038  sw    0x0056E35C, 8($s0)    ; MI sub-vtables
00501044  sw    0x0056E3D8, 0x10($s0)
00501050  sw    0x0056E428, 0x28($s0)
0050105c  sw    0x0056E498, 0x30($s0)
00501064  sh    -1, 0x920($s0)
00501068  sb    0,  0x922($s0)
00501070  sw    $s0, 0x7ad0($at)      ; g_instance  = 0x005D7AD0
00501084  sw    $v0, -0x7da0($at)     ; iface ptr    = 0x005B8260 (= this+8)
0050108c  sw    $s0, 0x7ad8($at)      ; 0x005D7AD8
00501094  sw    $s0, -0x7da8($at)     ; mINetworkMgr = 0x005B8258
```

A 2,344-byte object with a vtable at `0x0056E2D0` holding **38** function
pointers into `0x004FE780`–`0x005019B0` across `+0x08`…`+0xA0` (two reserved
zero words at `+0x00`/`+0x04`, and two null slots at `+0x8C`/`+0x90`). The
factory is called once, from
`0x0016D4D8`. The interface pointer `0x005B8260` is read from **64** sites,
clustered almost entirely in `0x00373000`–`0x00381000` — which is where the real
implementation lives; the `0x004FE780`–`0x004FEA90` vtable entries are thin
`addiu $a0,$a0,8; jal …` thunks into it.

This region is `RSNetworkMgr`, the class `GAME.LOG` names.

### 5.3 The transport plug-in point: field `+0xFC`

`RSNetworkMgr`'s send paths gate on a single pointer field:

```
; vtable+0x24 (the MasterPost network hook) -> 0x004FE9D0 -> 0x00376BE0
; vtable+0x28 -> 0x004FE9F0 -> 0x00377300:
00377300  addiu $sp, $sp, -0x10
00377308  lw    $a0, 0xfc($a0)
0037730c  beqz  $a0, 0x37731c        ; no transport -> return, silently
00377314  jal   0x37c030
```

There are exactly **seven** stores to `+0xFC` in `0x373000`–`0x382000`; six write
zero (construct / reset / shutdown) and **one** installs a transport:

```
00376858  lw    $v1, 0xf4($s0)       ; count of registered protocols
0037685c  addiu $s2, $v1, -1
00376860  bltz  $s2, 0x376898        ; none registered -> $v1 = 0 -> give up
00376868  addiu $a0, $s0, 0xec       ; the protocol-factory array
00376870  jal   0x379020             ;   element(array, index)
00376878  lbu   $v1, ($v0)           ;   record[0] = u8 protocol id
0037687c  bnel  $s1, $v1, …          ;   match against requested id
003768a0  beqz  $v1, 0x3768e4        ; not found -> never installs anything
003768b0  addiu $s1, $v0, -0x42c4    ; $s1 = 0x0054BD3C = "" (empty string)
003768bc  lw    $v0, 4($v0)          ; record[4] = factory function pointer
003768c0  lbu   $a1, 0x104($s0)
003768c4  jalr  $v0                  ; factory("", protoId)
003768cc  sw    $v0, 0xfc($s0)       ; <-- install transport
```

### 5.4 Two transports are registered

`RegisterProtocol` is at **`0x00376DE0`** — record stride `0x14`, layout
`+0x00` `u8` protocol id, `+0x04` factory fn ptr, `+0x08` `u16`, `+0x0A` `u16`;
it appends at `this+0xEC` and bumps the count at `this+0xF4` (`0x00376E98`).

It has exactly **two** call sites, both in one function at `0x00500970`:

| site | protocol id | factory | extra args | factory does |
|---|---|---|---|---|
| `0x00500994` | **3** | `0x00500A30` | `0x5E`, `0x5F` | `new(0x54 = 84 B)` then ctor `0x00506A00` |
| `0x005009B0` | **2** | `0x005009D0` | `0x60`, `0x61` | `new(0x158 = 344 B)` then ctor `0x004FE3A0` |

`0x00500970` is reachable only through a vtable slot at `0x0056E580` (part of a
dense function-pointer array ending at `0x0056E598`); no direct `jal` to it
exists. **Whether it is ever invoked at runtime was not determined** — that is an
open question, not a negative.

### 5.5 Neither connection class touches the IOP

Every `jal` target was collected from each class's code region and checked
against `sceSifBindRpc` (`0x002AD7A0`) / `sceSifCallRpc` (`0x002AD970`):

| region | external targets | SIF RPC calls | SCE-library-band targets |
|---|---|---|---|
| `0x004FE3A0`–`0x004FE780` (class A) | 6 | **0** | none |
| `0x00506A00`–`0x0050A200` (class B) | 43 | **0** | only `0x2B7858`, `0x2B9470`, `0x2BB618`, `0x2BB6B0`, `0x2BB760`, `0x2BB868` (libc `memcpy`/`memset`/`strlen` family) |
| `0x00373000`–`0x00382000` (`RSNetworkMgr`) | 157 | **0** | only `0x2B78B0`, `0x2BE8C8`, `0x2BE9E0` (libc) |
| `0x0050B000`–`0x00517000` (`RSAddress`/`RSConnection`) | 61 | **0** | only `0x2BB6B0`, `0x2BB760`, `0x2BB868`, `0x2BE198` (`sprintf`), `0x2BE780`, `0x2BE8C8`, `0x2BE9E0`, `0x2BED28` |
| `0x00517000`–`0x0051A000` (**i.Link**) | 25 | **`sceSifCallRpc` ×4, `sceSifCheckStatRpc`** | plus libc |

The i.Link layer is the *only* part of the networking stack that reaches the IOP
at all — and it only ever calls, never binds.

---

## 6. Question 5 — bottom line and the next probe

**(b) — reachable only with substantial new code injection.** Not (a), and
definitively not (c).

It is not (c) because nothing structural was compiled out of the transport chain.
The chain exists end to end in the shipped executable:

```
IkeStateMgr::InMultiplayer{Join,Setup}Screen  0x00167AA0 / 0x00167CD0   [100% sig]
RSGameStateMgr::InMultiplayer{,Client,Server}Mode  0x00364070/C0/110    [100% sig]
RSGameMessageMgr  (11/11 methods)             0x0035A580 – 0x0035B210   [91-100% sig]
   MasterPost/MasterSend -> mINetworkMgr      0x005B8258 / 0x005B8260
RSNetworkMgr  (2344-byte singleton)           0x00373000 – 0x00381000
   factory 0x00500FD0, registrar 0x00500970, RegisterProtocol 0x00376DE0
   transport slot this+0xFC, installed at 0x003768CC
   two protocols registered: id 3 -> 0x00500A30, id 2 -> 0x005009D0
RSAddress (TCP/IP | UDP | port)               0x0050EF20
RSConnection                                  0x00515C00
i.Link packet transport  ("GRPS2", fragmented send/recv)
                                              0x00518500 – 0x005195B0
   constructed from RSNetworkMgr at 0x00374BC4 and 0x0037C2BC
   sceSifCallRpc(client 0x005DA220, fno 0x80000B8C) ×4  +  sceSifCheckStatRpc
```

It is not (a) because a patch cannot supply what is missing:

| gap | evidence | patchable by immediate-word edit? |
|---|---|---|
| `ILINK.IRX` + `ILSOCK.IRX` never loaded | all 24 `sceSifLoadModule` sites enumerated | **No** — needs two new call sites and two new path strings; no spare list entries exist in the unrolled loader |
| i.Link RPC client never bound | all 11 `sceSifBindRpc` sites enumerated; 0 data pointers to `sceSifBindRpc` | **No** — needs a new `sceSifBindRpc` call |
| protocol registrar `0x00500970` reachable only by vtable | no direct `jal`; reachability unproven | unknown |
| `MULTI_PREGAME_PS2` / `MULTI_SERVER_SETUP` / `CLIENT_JOIN` / `CHATBAR` screens | 0 hits across all 2,751 archive files | **No** — this is missing *data*, not a disabled branch; these screens must be authored |
| `<Multiplayer>` options node | absent from the 27-entry registry at `0x005362B0` | needs new table entries + a reader |
| any IP/Ethernet path | 0 `sceInet`/socket/`%d.%d.%d.%d` strings; no `DEV9.IRX`/`SMAP.IRX` on disc | **No** — genuinely absent; i.Link is the only viable transport |

Practical consequence for the stated goal: **the only LAN co-op SOAF's own code
could ever do is two PS2s joined by an i.Link (IEEE-1394 / FireWire) cable, not
Ethernet and not over a router.** Emulator support for i.Link is effectively
nonexistent, so this is real-hardware-only, and it still needs hand-written MIPS
for the module loads, the RPC bind, and newly authored menu screens.

### The single most informative next probe

**Disassemble `0x00376780`–`0x003768F0` (the transport-selection function that
owns the `+0xFC` install at `0x003768CC`) together with the registrar
`0x00500970`, and determine which of the two registered protocol ids — 2 or 3 —
corresponds to the i.Link class, then trace who calls `0x00500970` through the
vtable slot at `0x0056E580`.**

That one function answers the two questions everything else depends on: (a) is
the i.Link transport the object the registry actually hands out, or is one of the
two protocols a loopback used for single-player message routing — resolvable by
checking which of the ctors `0x004FE3A0` / `0x00506A00` leads to the code at
`0x00518500`+ that references `ILink:Out of  IOBuffer`; and (b) does the
registrar ever execute, which decides whether the work is "add a module load and
a bind" or "add a module load, a bind, *and* force registration". If the answer
is that protocol 2 (the 344-byte class, ctor `0x004FE3A0`) is the i.Link path and
the registrar does run, then the minimum viable experiment is small and concrete:
append `ILINK.IRX` and `ILSOCK.IRX` to the boot module list and add one
`sceSifBindRpc` for the i.Link service, then watch for `SendPacket %d` on TTY.

---

## 7. Negatives re-tested against the corrected string scan

Because §0 showed 61 % of the string pool was previously invisible, the
`code.md` negatives that mattered here were re-run:

| claim | corrected-scan result |
|---|---|
| no split-screen strings | still **0** for `splitscreen`, `split_screen`, `viewport`, `twoplayer`, `2player`, `Player 2`, `second controller` — but `code.md` §5 already overturned the *conclusion* drawn from that, by signature: the split-screen state machine **is** in SOAF and carries no strings. The string negative is real; the inference from it was not |
| no `Recruit`/`Veteran`/`Elite` | **overturned** — `Recruit` ×8, `Veteran` ×4, `Elite` ×7. See below |
| `.CHA` is not a real extension | **needs revision** — still 0 hits for `\.cha\b` in the ELF even with the corrected scan, but 251 `.CHA` files exist in `SOAF.IMG` (e.g. `MP2_MALE.CHA`, `MP2_MALE_LOD1.CHA`), so `.CHA` *is* a real asset type; the ELF simply never names it in a string |

The `Recruit`/`Veteran`/`Elite` reversal does **not** change `code.md`'s
difficulty conclusion — SOAF's difficulty really is Easy/Normal/Hard — but the
strings that were missed are directly relevant to co-op. They are the medal-rank
schema of `unlocked_missions.xml`, a 5 × 3 grid, all fifteen registered in the
tag table at `0x00527090`–`0x005270F8`:

| | `Mission` | `Firefight` | `Recon` |
|---|---|---|---|
| `Recruit` | `0053FF38` | `0053FFA0` | `00540018` |
| `Veteran` | `0053FF48` | `0053FFC0` | `00540028` |
| `Elite` | `0053FF58` | `0053FFD8` | `00540038` |
| `Legendary` | `0053FF70` | `0053FFF0` | `00540048` |
| `Time` | `0053FF88` | `00540008` | `00540058` |

The three columns — **Mission, Firefight, Recon** — are exactly the three game
modes that have co-op GTFs (`(COOP) FIREFIGHT.GTF`, `(COOP) RECON.GTF`) and
co-op UI text (`Mission Coop`, `Firefight Coop` in `EN_STRINGS.RES`). A second
`Recruit*`/`Elite*`/`Veteran*` block at `0053DF90`–`0053E0B0`
(`RecruitEnemySkillAdjustment`, `EliteEnemyAimFactor`, `VeteranEnemyDelayFactor`,
…) is the AI difficulty-scaling table, also registered (`0x005264D8`+).
| `Coop` / `Multiplayer` / `MULTIPLAYER` exist | confirmed, plus the whole §1.6 i.Link block and §3.1 screen-state block that the old scan missed |

## 7a. Agreement with `code.md` §5 (split screen)

The two investigations were run independently and land in the same place, which
is worth recording because it raises confidence in both.

- **Same shape of answer.** §5 concluded split screen "would be *built*, not
  unlocked": the engine-level mode switch is present, nothing reaches it, and
  there is no menu to reach it from. LAN co-op is the same verdict one layer
  over: the transport is present, nothing binds it, and there is no menu.
- **Adjacent addresses, consistent layout.** §5 places
  `InSplitScreenMode__RSGameStateMgr` at SOAF `0x00364060`; this pass places
  `InMultiplayerMode__RSGameStateMgr` at `0x00364070`, with
  `InMultiplayerClientMode` / `InMultiplayerServerMode` at `0x003640C0` /
  `0x00364110`. Same class, same run of one-line predicates, in GR's order.
  Likewise §5's `SplitScreenMode__IkeRulesMgr` at `0x0014A700` is the address
  this pass's `IsHost__IkeDataMgr` probe returned as its (too short to trust)
  best hit — the two agree that `0x0014A700` is an `IkeRulesMgr`-family
  one-liner, and §5's identification is the better-supported one.
- **The portsig warning was independently reproduced.** §5 warns that "a low
  portsig score means *this build diverged*, never *this feature is absent*",
  using Jungle Storm scoring worse than SOAF on split-screen signatures as the
  control. This pass hit the same trap from the other side and needed the same
  correction: `LoadGameTypes__IkeDataMgr` scores below 55 % even though SOAF's
  `.GTF` loader provably exists at `0x001373B0` (§2.3). Every "not found" row in
  §2.3 must be read under that warning.
- **`SCREEN.TXT` is the load-bearing fact in both.** §5 already noted that its 19
  screens are all single-player and that there is "no multiplayer, co-op,
  split-screen, lobby or soldier-chooser screen on the disc". This pass
  strengthens that from a manifest observation to an exhaustive one: the five
  multiplayer screen-state names the ELF references occur **zero** times across
  all 2,751 files in both archives (§3.2), so they are absent from the disc
  entirely, not merely absent from the manifest.
- **One thing this pass adds to §5's ledger.** §5 lists what is missing above the
  engine for split screen. For network co-op the missing pieces are different and
  smaller in code terms — two module loads and one `sceSifBindRpc` (§1.7) — but
  strictly larger in *asset* terms, because split screen needs no new screens
  beyond a soldier chooser while LAN needs `MULTI_PREGAME`,
  `MULTI_SERVER_SETUP`, `CLIENT_JOIN`, `MPAFTER_ACTION` and `CHATBAR`, none of
  which exists in any form.

## 8. Method notes

- **Corrected string scan** (§0) — mandatory for this engine; `rsetool strings`
  silently drops every `\n`-terminated debug string.
- **`rsetool xref`** — `lui`+`addiu`/`lw`/`sw` pair scan. Blind to `$gp`-relative
  loads and to jump tables; a 0 here is a negative *for this method* only. The
  §3.5 conclusion does not rest on it — it rests on pointer-table membership.
- **Pointer scan** — 4-byte little-endian search for a VA. This is what found
  both name registries (`0x005256B8` from `code.md`, `0x005362B0` and
  `0x00526920` here) and what makes the multiplayer-options negative real.
- **Exhaustive `jal` enumeration** — decoding every `j`/`jal` in a VA range and
  in the whole segment. This produced the two airtight results: 24/24 module
  loads and 11/11 RPC binds. Indirect `jalr` through a register is invisible to
  it, which is why §1.7 also pointer-scans for `sceSifBindRpc`'s address (0 hits)
  before claiming no bind exists.
- **`portsig`** — validated on this pair by four controls at 98–100 % (§2). Trust
  a *match* on engine code. Do **not** read a *miss* on game-specific `Ike*Mgr`
  code as absence: `LoadGameTypes` is the counterexample (SOAF's GTF loader
  provably exists at `0x001373B0` yet scores <55 %).
- **Archive reads** — `research/soaf/soafimg.py`; all 2,751 entries in
  `MENU.IMG` + `SOAF.IMG` were decompressed and byte-searched for §3.2.
- Everything read-only. No disc image, ISO or `tcps2/` file was modified.

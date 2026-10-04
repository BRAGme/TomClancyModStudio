# Jungle Storm online, on your own network

Jungle Storm's ONLINE mode needs three things that no longer exist: Sony's DNAS, a Ubi.com lobby at
`gsconnect.ubisoft.com`, and (in an emulator) a way for the hosting console to be reached. This folder
replaces all three.

**Verified 2026-09-29:** two PCSX2 instances on one PC played online co-op end to end through this
server: login, lobby, room list, room join, launch handshake (`START_GAME` → `GAME_STARTED` →
`GAME_CONNECTED` ×2 → `GAME_READY` → `START_MATCH` → `MATCH_STARTED`), and both consoles loaded J02
Railroad and saw each other. Online co-op is the multiplayer game type: MP HUD, one soldier per human, no
AI backup. The third-person camera patch does apply online.

Ghost Recon (SLUS-20613) has no online mode at all, so all of this is Jungle Storm's alone.

## How the pieces fit

```
  joiner console ──TCP 10070 + UDP──▶  host console        (peer to peer once a game starts)
        │                                   │
        └──── HTTP 80 + GS 40000 ────▶ ubilobby.py ◀────┘   (login, rooms, launch)
```

* **The discs** point the ONLINE menu at the lobby server (ModStudio: *skip the DNAS check* +
  *lobby server on your own network*, see `tcps2/grlan.py`). The address is literal; no DNS is used.
* **`ubilobby.py`** is the stand-in lobby. Stdlib Python 3, no installs.
* **The hosting console must be reachable.** PCSX2's *Sockets* network mode cannot accept incoming TCP
  (its TCP sessions only start from the console; `pcsx2/DEV9/sockets.cpp` has no listen/accept), so a
  host in Sockets mode can never be joined. The host uses **TAP** instead. Joiners can stay in Sockets.
* **`relay.py`** lets a joiner on another network (Radmin) reach a TAP host.

## 1. One-time: a TAP adapter for the hosting PC

1. Get `dist.win10.zip` from the [tap-windows6 releases](https://github.com/OpenVPN/tap-windows6/releases)
   and use its **amd64** folder (the arm64 build will not run on an x64 PC).
2. In an **administrator** PowerShell, in that folder:
   `.\devcon.exe install OemVista.inf tap0901`. The files are signed by Microsoft's hardware
   compatibility publisher; Windows asks once to install the device software.
3. Give the new adapter ("TAP-Windows Adapter V9") a fixed address, e.g. in the same admin shell:
   `netsh interface ipv4 set address name="Local Area Connection" static 10.20.30.1 255.255.255.0`
   (use whatever name Windows gave the adapter).

## 2. PCSX2 network settings (per game, on the disc you boot)

**Host console:** Ethernet enabled · Device Type **TAP** · Device = the TAP adapter · Intercept DHCP on ·
PS2 Address **10.20.30.2** · Subnet Mask **255.255.255.0** · Gateway **10.20.30.254**.

> **Do not set the gateway to 10.20.30.1.** With the gateway on the PC's own TAP address, the console
> sent every frame for 10.20.30.1 to MAC `76:6D:F4:63:30:31` — PCSX2's internal virtual router — and
> Windows dropped them. It only "worked" while a packet capture had the adapter in promiscuous mode. Any
> unused address on the subnet fixes it; the console reaches 10.20.30.1 directly and needs no gateway.

**Joiner on the same PC:** Device Type **Sockets** · Device = the **TAP adapter** (Sockets mode sends from
the chosen adapter's address, and only the TAP side can reach the host console). Change the Device Type
first, then the Device — changing the type resets the device to "use global".

**Joiner on another PC over Radmin:** Device Type **Sockets** · Device = **Radmin VPN**. Allow that PCSX2
through its Windows Firewall on the Radmin network.

Only **one** PCSX2 may use a given TAP adapter. Start the host's PCSX2 before a same-PC joiner's.

## 3. Discs

Each console's disc must point at an address *that console* can reach the lobby at:

| console | lobby address on its disc |
| --- | --- |
| host (TAP) | the PC's TAP address, `10.20.30.1` |
| joiner on the same PC (Sockets on TAP) | `10.20.30.1` |
| joiner over Radmin | the host PC's Radmin address, e.g. `26.209.25.36` |

`config/` holds a 3 KB settings record a remote player drops beside his own disc and loads with
ModStudio's **Last applied** button (`config/READ-ME-FIRST.txt`), instead of anyone sending a disc image.

## 4. Running it

**Everyone on one PC** (host on TAP, joiner in Sockets on the TAP adapter):

```bash
python ubilobby.py --ip 10.20.30.1
```

**A joiner over Radmin** — on the hosting PC, both of these:

```bash
python ubilobby.py --ip 10.20.30.1 --advertise local --map 10.20.30.2=26.209.25.36 --map "*=10.20.30.1"
python relay.py --public 26.209.25.36 --inside 10.20.30.1 --console 10.20.30.2
```

* `--advertise local` gives each console the lobby's address *as it reached it*: the TAP console gets
  10.20.30.1, the Radmin joiner gets 26.209.25.36.
* `--map 10.20.30.2=26.209.25.36` tells the joiner the host console is at the relay.
* `--map "*=10.20.30.1"` tells the host console that every other player is at the relay's inside address.
* The relay carries the joiner's TCP 10070 in, and mirrors each of his UDP ports on the inside with the
  **same port number**, because the joiner's console reports its own port in-game and the host console
  answers that port. Measured: the joiner sends first, from P to host 10070 and from P+1 to host 10074;
  the host then streams UDP from 10070 to P at about 13 packets a second.

Both scripts log every connection. Stop them with Ctrl+C in a console window of their own.

## What to watch in the logs

* `GET /gsinit.php` from each console — it reached the lobby.
* `PEERPLAYER` → `PEERMSG` after a join — the host accepted the joiner as a room member.
* `GAME_STARTED`, then `MATCH_STARTED` — the match began.
* relay: `new joiner … -> inside … (mirrors its port)` and the periodic `up N down M` counts.

## Traps that cost time

* **Lobby introductions.** A console only keeps a member record for players it was told joined the
  *lobby*; without one, adding them to a room fails and each console lists only itself. The server now
  introduces lobby members to each other (found from both consoles' savestates, ELF `0x001A1130`).
* **Room counts.** A console counts a room's players itself from `MEMBER_JOIN`/`MEMBER_LEAVE`; the Join
  Game filter hides rooms below *Min Players*. The server sends those to lobby members outside the room.
  Do not use `--room-update readd`: re-adding a room resets its count.
* **Never run `fakeclient.py` or `--selftest` while a live server is up.** They bind the real ports 80
  and 40000 too, Windows lets both bind, and consoles land on whichever wins. `test_relay.py` uses
  loopback addresses only and is safe any time.
* Two servers can run at once without an error (`SO_REUSEADDR`). Check which process owns the ports
  before assuming a restart took.

## Tests

```bash
python ubilobby.py --selftest      # crypto vectors and captured frames
python fakeclient.py               # two scripted consoles through the whole flow
python test_relay.py               # the relay on loopback addresses
```

The fake client was written from the same disassembly as the server, so it agrees by construction; the
real consoles are what grade it.

Protocol credit: `michal-kapala/gsconnect` (MIT) for the public reverse engineering of GSXor, the message
header and the data-list format; everything here was re-verified against the Jungle Storm client.

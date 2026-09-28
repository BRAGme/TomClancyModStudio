# Jungle Storm online, on your own network

Jungle Storm's ONLINE mode needs two things that no longer exist: Sony's DNAS, and a Ubi.com lobby at
`gsconnect.ubisoft.com`. This replaces both — one patch on each disc and one Python script on one PC.
Nothing here needs the internet.

Ghost Recon (SLUS-20613) has no online mode at all — no `gsconnect`, no `gsinit.php`, no bootstrap —
so this is Jungle Storm's alone. Split screen is the only route there.

## 1. One PC runs the lobby

Standard library only, Python 3. On the machine both players can reach:

```bash
python tools/lan/ubilobby.py --ip 26.13.44.7
```

`--ip` is **the address the other player reaches this PC at** — the Radmin VPN address if you are
tunnelling, the LAN address if you are on one switch. It is not just a bind address: the server hands
it to the consoles as the lobby's address, and hands each console the *other* console's address when
a game starts, so it has to be the one they can actually route to.

It listens on TCP **80** (the directory) and TCP **40000** (router, wait module, lobby and the
ladder proxy, all recognised by message type on the one port). If something else on the PC owns port
80, use `--http-port 8080` and set the same number in the disc option below. Let it through Windows
Firewall for the Radmin adapter.

Every frame in and out is decoded and logged, to the console and to a log file.

## 2. Both discs get two options

In ModStudio, under **Online**, for each copy:

- **Online: skip the DNAS check** (`js_skip_dnas`) — on. Required; ONLINE loads DNAS.BIN before
  anything else and waits forever for servers that are gone.
- **Online: lobby server on your own network** (`js_lan`) — on, with the four address numbers set to
  the PC from step 1 (`26`, `13`, `44`, `7` for the example above). Leave the port at 80 unless you
  changed `--http-port`.

Both discs need the same address. See `tcps2/grlan.py` for what the patch does: the bootstrap calls
`inet_addr` on the name before it calls `gethostbyname`, so writing a plain address over
`gsconnect.ubisoft.com` means no name server is ever consulted — which is why a VPN address works
with nothing else configured.

## 3. Emulator networking

PCSX2 needs DEV9 enabled with an Ethernet device the consoles can route out of, and the in-game
network configuration has to be completed once per copy. That is the user's own PCSX2 setting; this
repo does not change it.

## What has been checked, and what has not

- The disc patch is verified against the shipped executable offline: stock words match, the patched
  field reads back as the address asked for and terminates inside its own 32 bytes, the GET line that
  follows is untouched. See the test in the session scratchpad (`net/test_lan.py`).
- The server is verified against itself: `--selftest` decodes captured Jungle Storm frames and checks
  the Blowfish, RSA and GSXor primitives; `fakeclient.py` drives two scripted consoles through login,
  key exchange, room create, join, ready, peer messages, START_GAME, MATCH_STARTED and leave, and
  passes every check.
- **Neither has been through a real console yet.** The fake client is built from the disassembly, so
  it agrees with the server by construction; only a real Jungle Storm can show whether the disassembly
  was read correctly.

## Useful switches when it does not work

| switch | why |
| --- | --- |
| `--hex` | hexdump every frame, not just the decode |
| `--map SEEN=ADVERTISED` | a console reaches the PC at one address but the other console needs another |
| `--proxy fail` | the ladder/persistent-data module gets a clean error instead of hanging |
| `--keepalive`, `--info-first`, `--room-info-fix`, `--room-update` | the behaviours that were uncertain in the disassembly, switchable rather than guessed |

Gameplay itself is peer-to-peer once a match starts: the host listens on TCP 10070 / UDP 10071 and the
joiner connects from UDP 10072 / TCP 10073, so those have to be routable between the two machines too.
The lobby is out of the loop from then on.

Protocol credit: `michal-kapala/gsconnect` (MIT) for the public reverse engineering of GSXor, the
message header and the data-list format; everything here was re-verified against the Jungle Storm
client.

# Ghost Recon (SLUS-20613) and Jungle Storm (SLUS-20820)

A different engine from Rainbow Six 3, with different rules. Addresses here are
virtual addresses in the **boot ELF**, which is not compressed: file offset =
VA − `0x00100000` + the program header's offset, `0x80` for Ghost Recon and
`0x100` for Jungle Storm.

Jungle Storm's `OFFLINE.BIN` and `ONLINE.BIN` are an `MWo3` container — an
uncompressed 0x40-byte header followed by MIPS code loading at `0x00692700`,
confirmed because `0x40 + text + data + bss` reproduces the ELF's `PT_LOAD`
`p_memsz` byte-exactly for both. They hold the Fonix speech-recognition engine
and the Ubi.com lobby client, so there is **no gameplay in either** and nothing
here targets them. Unlike Rainbow Six 3, the thing to patch is the boot ELF.

Ghost Recon's executable is 37 MB because it is an **unstripped debug build**: a
full Metrowerks symbol table with 19,496 named functions and their sizes, 26.8 MB
of DWARF, and the original source tree. Every Ghost Recon address below was
identified by name rather than guessed at. Jungle Storm is stripped — its symbol
table is present with `sh_size = 0` — so its addresses were recovered by matching
code signatures against the Ghost Recon build and walking the call graph out from
the anchors that matched.

**None of these has been watched working in a running game.** Every stock word
was machine-checked against the retail executable, so they land where they are
aimed, but their effect is inference from the disassembly. The interface labels
them accordingly.

---

## Bullet holes

| what | Ghost Recon | Jungle Storm |
|---|---|---|
| pool size | `0046D9D0` `24050014` | `00431930` `24050014` |
| clear-loop bound | `0046D9EC` `24020014` (`addiu`) | `0043194C` `2A020014` (`slti`) |
| default lifetime 30.0f | `00249638` `3C0341F0` | `00245E4C` `3C0341F0` |
| short-surface lifetime 2.0f | `00249740` `3C024000` | `00245F28` `3C024000` |
| unknown-surface early-out | `002496EC` `1000001B` | `00245EF8` `1000000F` |

The pool size and its clear-loop bound **must move together**: raising the array
without raising the loop leaves the extra entries with an uninitialised active
flag. Note the bound is a different instruction in each game, so the two words
are genuinely not interchangeable — copying Ghost Recon's word into Jungle Storm
would corrupt it.

The early-out is the interesting one. `DisplayBullethole` gives up on a surface
type it does not recognise and draws nothing at all; removing it falls through to
the path that selects decal texture 0 at the default size, so every surface
marks.

Float constants for the lifetimes: 120.0f is `3C0342F0` / `3C0242F0` and 1000.0f
is `3C03447A` / `3C02447A`, the two forms differing only in destination register.

## Split screen

`CGraphicSystem+0x2880` is the split-screen flag, proved by its two
two-instruction accessors. `EffMgrPS2::Render` keeps two dispatch blocks, and the
split-screen one **omits bullet holes, foliage and birds** in Ghost Recon, and
bullet holes and foliage in Jungle Storm, which has no bird manager. This is the
same defect as Rainbow Six 3's split-screen problem in a completely different
engine.

Exposed by the tool — the creation and update side, which does not touch how the
viewports are set up:

| Ghost Recon | Jungle Storm |
|---|---|
| `0024EF38` `14E0006A` — `CreateGeneralEffect`, skips a 424-byte block | `00423B08` `1440000B` — `PreRender` |
| `00252A8C` `14400033` — `DrawEffects` | `00423E60` `14400024` — heat haze |
| `0024C8B8` `14400009` — `AddGeneralEffects` | `00424D70` `1440007C` — night vision |
| | `00427BA4` `10400005` — snow constructor, **inverted**, so the fix is an unconditional branch rather than a nop |

**Deliberately not exposed**, written down so nobody spends a day rediscovering
it: forcing the main render gate (`0045E1D4` / `00423C80`) does restore the
effects, but the full-effect block ends in an unconditional branch past *both*
`SetSplitScreenDrawArea` calls, so the second viewport is never set up. Zeroing
the flag itself (`0044EBB4` / `004152B4`) has the same problem from the other
end: `MainFrame`, `PreMainFrame` and `GetCurrentCamera` all read that same byte.
Either one trades the effects for the second screen.

## Weather (Ghost Recon)

Four fixed-size particle arrays. Every effect `RSMemoryPool` in this engine
auto-extends, so pools are not caps — only the fixed `RSArray`s are, and these
are them.

| VA | stock | what |
|---|---|---|
| `00257C80` | `24050FA0` | `IkeRainEffect`, 4,000 raindrops |
| `002584FC` | `240509C4` | `IkeSnowEffect`, 2,500 flakes |
| `00460420` | `2405012C` | `RainEffectPS2`, 300 |
| `004627D0` | `24050064` | `SnowEffectPS2`, 100 |

## Camera, and the view-model question

Ghost Recon **does** have a first-person camera: enum value 0, with the strings
`first person camera` / `third person camera` / `cinema camera` / `chase camera`
/ `ghost camera` at `00584320`, reachable on the ordinary camera-cycle input.
What it does not have is a view model. `CameraBeginScene` calls
`RSSimController::Hide()` on the player's own draw object and puts nothing in its
place, and searching all 38,722 symbols for viewmodel / hands / arms / fpp
returns only the two `IsFirstPerson` predicates. The same structure is confirmed
in Jungle Storm at `00379880` / `003889D0`.

| VA | stock | becomes | effect |
|---|---|---|---|
| `003A80F4` (GR) | `10400010` | `10000010` | never take the first-person branch, so `Hide()` is never called and your own body stays drawn |
| `003A8B88` (GR) | `28420003` | `28420006` | camera cycle wraps at 6, unlocking chase and ghost |
| `00388958` (JS) | `28420003` | `28420006` | the same |

## Online, and the LAN redirect (Jungle Storm only)

Ghost Recon has no online mode at all: `SLUS_206.13` contains neither `gsconnect`
nor `gsinit.php`, and there is no bootstrap to redirect. Everything here is
Jungle Storm's.

`GSFetchServerList` at `0x00531830` turns a name into an address in two tries,
and the order is what makes the option possible:

| VA | word | what |
| --- | --- | --- |
| `0x00531864` | `jal 0x006d2bd8` | **`inet_addr`** on the name field — tried **first** |
| `0x00531870` | `beq v0, -1` | only a failure there falls through to DNS |
| `0x0053189c` | `jal 0x006d19e8` | `gethostbyname`, same `a0` |
| `0x005318e0` | `jal 0x006971b0` | `htons` |
| `0x005318e4` | `24040050` | `addiu a0, zero, 0x50` — port 80, the one hardcoded port |

Because `inet_addr` runs before the resolver, writing a dotted quad over the name
resolves with **no name server consulted at all** — which is what lets a VPN
address work with nothing else configured on either machine.

The name field is 32 bytes at VA `0x0059e490` (file `0x0049e590`):
`gsconnect.ubisoft.com` and eleven NUL bytes, ending exactly where the request
line begins at `0x0059e4b0`. A dotted quad is at most 15 characters, so the
replacement is written over the whole field with NUL fill and nothing is
displaced. The request line itself — `GET /gsinit.php?dp=GHOSTRECONIT_PS2
HTTP/1.1` with a `HOST: gsconnect.ubisoft.com` header at `0x0059e4e4` — is left
alone: the header is sent, not checked.

Of everything a real Ubi.com directory returned, `GSGetServerAddress`
(`0x006ffdc0`, one caller, type 0) reads exactly `[Servers] RouterIP0` and
`RouterPort0`, so a stand-in has one GET to answer. Gameplay after that is
peer-to-peer and not brokered: host TCP 10070 / UDP 10071, joiner UDP 10072 /
TCP 10073, hard cap 12 connections (`slti` at file `0x003b4328`).

`tcps2/grlan.py` writes the redirect; the port instruction is only touched when
the port is changed, and is capped at 32767 because that immediate sign-extends.
The option depends on the DNAS skip, since `DNAS.BIN` loads before any of this.
The stand-in lobby server lives in `tools/lan/`.

---

## Not code: the enemies

There is **no hardcoded enemy cap in either executable**. `Company::AddPlatoon`
and `Platoon::AddFireTeam` grow their arrays by one with no maximum test. Enemy
population, placement, skill and loadout are all data, so the tool edits data.

Two precise negatives, recorded so nobody re-derives them:

* `decal_type1/2/3` have **zero** code cross-references in Ghost Recon. They are
  data-file tag names, not engine switches.
* `Emitter` is the **sound** class in this engine, not a particle emitter.

---

# The archive, and why writing to it is safe

`GR.IMG` and `MENU.IMG` use the same read-only filesystem as Rainbow Six 3's
`VOKES*.IMG` — 48-byte records with an explicit offset and size — so a file can
be moved.

Most data files are wrapped in a container that was not documented anywhere:

```
repeat until EOF:
    u32  compressedSize
    u32  rawSize            (always <= 0x4000)
    u8   blob[compressedSize]
```

and the payload is **stock LZO1X**. Two rules matter:

* **`compressedSize == rawSize` means the chunk is stored, not compressed.**
  Feeding a stored chunk to the decoder produces a bad back-reference within
  about fifty bytes. That single rule is the difference between decoding every
  file in both games and failing on eighty-eight of them.
* The field order is `(compressed, raw)` — the **reverse** of Rainbow Six 3's
  `.LIN` packages.

Two details of the reference decoder are easy to get wrong and corrupt the output
silently: after a match, the trailing-literal count is `ip[-2] & 3`, the byte two
before the pointer rather than the token; and the M1 case reached from a first
literal run uses a fixed `0x800` distance base and copies three bytes, where the
M1 reached from a match copies two.

## Writing it back

Re-compressing is the hard half. A from-scratch encoder lands about 1.2–1.8%
above whatever Red Storm shipped with, which is enough to overflow a slot. Two
things close the gap:

* the encoder **refuses a match that does not pay for its own token** — a
  three-byte match too far away to use the short form costs three bytes to encode
  three bytes, so taking it makes the file bigger;
* every transform **preserves the file's byte length**, padding with spaces where
  it removes something, so `repack` copies untouched chunks across verbatim and
  only re-compresses the ones that actually changed.

What is left over is absorbed by relocation. Every archive ends with 64 KB of
zero padding; a file that no longer fits is moved there and its old run is zeroed
and released back into the pool, so in practice the first file takes the pad and
the rest recycle each other's slots. Rewriting all 25 of Ghost Recon's
flag-bearing missions costs 2.4 KB of the 64.

Two traps:

* **Allocate largest first.** Jungle Storm's biggest mission needs 34 KB, and if
  smaller files nibble the pad first there is no contiguous run left for it.
* **Unreferenced is not the same as free.** Ghost Recon's `GR.IMG` contains a
  6 MiB run that no entry points at and which is full of real data. Every
  candidate run is read and required to be all zeros before it is used.

## The data itself

| file | what |
|---|---|
| `.MIS` | the mission: `<Units>` order of battle, `<PlanList>` AI behaviour |
| `.ATR` | one enemy template — armour, weapon skill, stamina, stealth, leadership |
| `.KIT` / `.GUN` / `.PRJ` | loadout, weapon and projectile definitions |
| `.TOE` | the *player's* order of battle, same grammar as `<Units>` |
| `.GTF` | a game type: lobby config, objectives, and two script blobs |

A `.GTF`'s `<ScriptCompiled>` / `<ScriptSource>` blobs are **not base64** — they
are an A..P nibble encoding, each payload byte becoming two characters in `A`
through `P`, low nibble first. The decoded payload opens with the script's
variable table:

```
u32 variableCount
u32 1
u32 2
repeat variableCount times:
    u32   nameLen
    char  name[nameLen]        (no NUL)
    u32   value                (int, or IEEE float bits)
    u32   id
    u32   0
```

Because the encoding is fixed width, rewriting a value in place keeps the payload
length, the XML length and therefore the archive slot size identical. That is how
Jungle Storm's Defend enemy counts are edited.

**What is not cracked:** the compiled script node graph past that variable table.
Designer node names and comments are readable, and the variable table is readable
and writable, but a constant typed straight into a node is not. All 46 Ghost
Recon missions and 44 of 45 Jungle Storm missions carry an **empty** variable
table, so mission wave *timing* is out of reach. The cleanest way in, if anyone
wants it: `(SP) DEFEND.GTF` and `(COOP) DEFEND.GTF` in Jungle Storm are a nearly
perfect structural pair — 2,390 against 2,381 payload bytes, identical variable
names, differing only in the three enemy counts.

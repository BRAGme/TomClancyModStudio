# Notes for the next version

Everything below is in the working tree and built into `dist/`, but the version
string has not moved. `gui/app.py` still says `VERSION = "1.0"`; bump it there
and rebuild, since `build_exe.py` reads the number out of that file rather than
keeping its own.

Written 2026-09-28. The badges are the ones the cards actually carry.

## New: shotguns — `tcps2/grshotgun.py`

Both games. A data-only weapon built on the dead `G36` slot, using the unused
`w_m4_masterkey_shotgun.qob` model that ships on both discs.

* `{gr,js}_shotgun`, `_shotgun_pellets` (6/8/9), `_shotgun_spread`
  (hu/medium/wide), `_shotgun_kits` (none/some/all).
* Pellet counts **watched in game**: the HUD stepped 48 → 42 → 36 → 24 → 000 at
  six per pull. Badged verified.
* The spread numbers are Heroes Unleashed's M1014, because HU's own shotguns get
  their pattern from `ProjectileSpread`, which the PS2 build does not have.
* Trap worth keeping: **Jungle Storm loads `.XBG`, not `.GUN`.** Editing the XML
  alone did nothing and froze the level load on a missing model. Ghost Recon has
  no `.XBG` at all. `grhu.py` already said so; it cost a disc to rediscover.

## New: the shotgun's firing sound — `tcps2/grshotsound.py`

`{gr,js}_shotgun_sound`. Copies the Benelli single-shot sample out of a Sum of
All Fears disc into bank 0 over `W_AK47_SS.WAV`, a record no gun, kit or mission
in either game names. Bank 0 is the one bank loaded unconditionally.

The sample is confirmed **physically present in SPU RAM** at `0x7A8D4` in a
savestate, so the import works end to end. Whether it sounds right has not been
reported yet. Badged applied, not verified.

Two things that cost time: `_sf` is a sustained-fire loop and `_ss` is the single
shot (the first attempt used `_sf` and played seven rifle shots); and the `.SH`
header is **16 bytes, records at +16**, verified independently on `BNK_01.SH`
whose two records chain 0 → 6064 → 11648, exactly its `.SB` length. Two research
agents disagreed 12 vs 16; writing at +12 would have corrupted every bank.

## New: online without Ubisoft — `tcps2/grlan.py` + `tools/lan/`

Jungle Storm only; Ghost Recon has no online mode to redirect.

* `js_lan` + `js_lan_ip1..4` + `js_lan_port`, requiring the existing
  `js_skip_dnas`. Badged experimental — **never played**.
* Addresses and the reasoning are in
  [PATCHES-GHOSTRECON.md](PATCHES-GHOSTRECON.md#online-and-the-lan-redirect-jungle-storm-only).
  The short version: `inet_addr` runs before `gethostbyname`, so a dotted quad
  written over the hostname needs no name server anywhere.
* `tools/lan/` holds the stand-in Ubi.com lobby (stdlib only). `--selftest` and
  `fakeclient.py` both pass — the latter drives two scripted consoles through
  login, key exchange, rooms, ready, `START_GAME` and `MATCH_STARTED` with zero
  failures. The fake client was written from the same disassembly as the server,
  so it agrees by construction; a real console has not been through it.

The settings model has no text kind, which is why an address is four `INT` cards
rather than one box. If a `TEXT` kind is ever added, this is the first customer.

## New: sending a configuration instead of a disc image

`dist/JungleStorm-LAN-Config.zip`, 3.5 KB. ModStudio's **Last applied** button
reads `<iso dir>/.tcms-backup/<iso stem>/applied-settings.json`, so a settings
record can simply be dropped beside someone else's own copy and loaded from the
window. `applied.load` ignores a record whose `profile` does not match, and the
button enables on a non-empty `history`.

This is a capability the GUI already had and nothing advertised. Worth a real
Import/Export pair in the window rather than a zip and a readme.

## Changed: smoke grenades — `tcps2/grsmoke.py`

* `js_smoke_look` gains **round**, rebuilding the cloud from
  `smoke_medium_type2` so it reads as a volume rather than a billboard.
* The cloud now **holds where the grenade lands** instead of hanging in the air
  where it burst.
* The enemy grenade fix: AI were reporting smoke as a live frag, so the team sat
  out thirty seconds and nobody ever threw a real one. Counters after the fix —
  frags queued 26, **thrown 3**, previously 0. Watched in game.

## Also built, unplayed

Ghost Recon `[js parity]` (CRC `F2C130A8`) and Jungle Storm `[lan]`
(CRC `146FB10F`). 49 of the Jungle Storm disc's 60 live settings map onto `gr_`
keys unchanged.

## Still Jungle Storm only

No Ghost Recon addresses exist yet for smoke (4 options), penetration, enemy
suppression, squad death music, split-screen bodies, or the three `defend_*`
numbers. `grsmoke`, `grpierce`, `grsuppress` and `grdeathmusic` each expose only
`js_edits`, though each already has a `selftest(gr_elf, js_elf)` — Ghost Recon's
symbols built them, but its own hook and cave addresses were never found.

## Open

* The shotgun sound has not been confirmed audible.
* Blood on dead bodies: the gate (`andi v0, flags, 2`) is identical in both
  games, so the difference is upstream; `ApplyDamage` is virtual, so there are no
  direct callers to walk back from.
* The reload-toggle-to-smoke path has never been checked with grenades in hand.
* J03 freezing on load is **the stock game's**, reproduced on an unpatched disc.
  Suspects are the flagged-unsafe PCSX2 settings (EE cycle rate, extended RAM,
  fast CDVD), not anything this tool writes.

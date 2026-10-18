# Tom Clancy PS2 Mod Studio 1.01

47 changes since 1.0 (2026-09-28). Every card still carries the badge that says
how far it was proven: **verified** means watched in a running game; the rest
were checked against the retail executables (and, where said, in the RAM
interpreter over real savestates) but not played.

## Ghost Recon and Jungle Storm

- **Jungle Storm online co-op** (Jungle Storm). AI backup fills every fireteam
  in a co-op room; R2 gives your own AI quick orders (tap: follow/hold, hold:
  move-to); SELECT takes the teammate under the reticle; you take over your AI
  when you die; a squad HUD and map. Part of a 59-setting update (26 Ghost Recon,
  33 Jungle Storm), every option at every value built with no address written
  twice: 255 Ghost Recon builds, 294 Jungle Storm builds, 0 failures.
- **Play online without Ubisoft** (Jungle Storm). A stand-in Ubi.com lobby
  (`tools/lan/`, standard library only) and a relay so players on Radmin can
  join a TAP-hosted console. **Verified**: two consoles played J02 Railroad
  online co-op end to end through it. Re-applying over an earlier lobby patch no
  longer needs RESTORE DISC; a saved map index past the table no longer freezes
  the online Setup screen (verified).
- **Smarter squads and enemies.** Team-mates react when anyone in the fireteam is
  shot at and take cover while under fire; hold-R2 grenade orders (move there, or
  the nearest team-mate throws a frag/smoke or fires his launcher at the point);
  shuffled enemy loadouts, patrols and start positions.
- **Grenade throw arc** (Ghost Recon and Jungle Storm), **enemy grenade
  launchers**, and a **75 m enemy throw**. The arc draws the real two-speed
  throw (10 m/s under half a second, 25 m/s after).
- **Shotguns** (both games), a data-only weapon on the dead G36 slot using the
  unused shotgun model both discs ship. Pellets **verified** (HUD stepped six per
  pull). Its firing sound is copied from a Sum of All Fears disc (confirmed
  present in SPU RAM; not yet confirmed by ear).
- **Smoke grenades** reworked: a round cloud, held where the grenade lands, and
  the AI no longer reads smoke as a live frag (frags thrown went from 0 to 3 in
  the watched test).
- **Ghost Recon: the reticle shows when cover blocks your shot** in third person
  (amber, at the point the round would hit). The controller layout defaults to
  stock again.
- **Ghost Recon missions in Jungle Storm** ("GR -> JS"): Ghost Recon's M01 Caves
  plays in Jungle Storm's CP01 slot. Fixed while playing it: the port no longer
  overwrites the player's own specialists, and Ghost Recon's music is found in
  `MUSIC.TM` (it was never in the sound banks).
- **Split screen**: a teammate killed in part A stays dead in part B.

## Rainbow Six 3

- **Third person** (four options under Controls): the stock UE2 behind-view
  camera with your own body, muzzle flash and reticle. Camera and reticle
  **verified** in play.
- **Four things the disc shipped but could not reach**, including the developer
  console (117 cheat functions; the unlock test was already dead code).
- Fixed: the friendly-fire option silenced single player's "lead is down"
  call-out; the going-down line was on the wrong case; the message box can move.

## Sum of All Fears

- Quick Mission game types (with the revert bug they uncovered fixed).
- Research toward porting its content into Ghost Recon (`research/soaf/`); its
  training level loads in Ghost Recon's TRAINING slot. Not a user option yet.

## Fixes in the engine

- Data edits: a leftover restore no longer lands on another file's slot; a
  revert no longer destroys relocated files.
- The test suite no longer aborts in the Ghost Recon data section (which had
  hidden two failures), and now checks that every word the tool writes can be put
  back.

## Known open items

- The shotgun sound is not yet confirmed audible.
- Jungle Storm J03 freezing on load reproduces on an unpatched disc (stock game).

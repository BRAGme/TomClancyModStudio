# Rainbow Six 3 PS2 — per-map wave zones

Where this stands: the authored per-zone values **are** reachable and editable.
What is not finished is attributing a property block to a specific actor class,
which is what a per-map UI would need before it could label anything.

## What the disc actually places

Counted by decompressing every `OFF` level package and tallying the placement
names, not recalled:

* **24 of the 27 campaign mission parts** place deployment zones, 568
  `R6DZonePoint`s between them.
* The three with none are **Alpine Village A, Import/Export A, Penthouse A**.
* **Multiplayer places zero** wave actors across all twelve maps. Training
  places a few zone *points* but no wave actor to use them, which is the likely
  source of the older claim that it had zones.

This corrects a note that had named five levels as the only ones with zones.

## The package format

A `.LIN` level is ~107 cooked Unreal packages end to end, file version 123,
licensee 22. `tcps2/upackage.py` reads them.

**The recorded table offsets are relaid by the PS2 cooker and cannot be used.**
On Shipyard A both `exportOffset` and `importOffset` land in float data, whether
read package-relative or absolute. The *name* offset is still good.

That is enough, because Unreal serialises a property as

    compactIndex(nameIndex)  infoByte  [size]  value

so a property can be found by searching for its own name index followed by an
info byte — `0x22` for a four-byte int — with no export table involved.

## The authored values

Each spawner carries `m_iMinTerrorist` and `m_iMaxTerrorist` as int properties.
Shipyard A, validated by walking each property list to its terminator:

| site | max | the properties that follow it |
|---|---|---|
| ×2 | 5, 5 | `m_TerroristAITag`, several `m_Template`, **`m_eTerroristHunt`**, `m_eCoopTerroristHunt` |
| ×6 | 4,4,3,3,4,2 | `m_TerroristAITag`, one `m_Template`, **`m_eStoryMode`**, `m_eCoopStoryMode` |

Two hunt-gated spawners and six story-mode ones — and Shipyard A's name table
holds exactly two `R6DZoneWave` instances and six `R6DZoneRandomPoints`, so on
this level the split is exact.

## What editing is allowed

Values already authored can be rewritten in place: an int32 stays an int32, so
`lin.substitute`'s equal-length rule is satisfied.

**A value that is not authored cannot be added.** Unreal omits any property
equal to its class default, so a zone shipping the default count has no property
to rewrite, and inserting one would move every byte after it. This is why the
counts differ per level — on Shipyard A eight actors author a max but only five
author a min.

## What is still open

The export table names the classes, but it does **not** say where an object's
property bytes are. Its recorded serial offsets describe the layout *before*
cooking -- data sitting between the name table and the imports -- and that is
not where the data ended up:

* The offsets are perfectly contiguous, 80490..1070234 across 3144 boundaries
  with no gaps, and 1070234 is exactly the summary's `importOffset`. So they
  are internally consistent, just describing a layout that no longer exists.
* Summing every package's export sizes gives 18.8 MB inside an 11.8 MB file,
  and the packages sit back to back with no gaps, so the data cannot simply
  follow the tables.
* Searching 159000..200000 for a single base that makes blocks end exactly on
  their recorded sizes found nothing -- 0 of 60 probes at every offset.

So `export -> property bytes` is unsolved, and with it the last of the actor
attribution.

**The next thing to try** does not need offsets at all: the export table gives
each wave actor's serial SIZE (Shipyard A: 221 and 226). Property blocks can be
walked to their terminators wherever they are, and a block whose length matches
a wave export's size, in a level with that many wave exports, is very likely
that actor. Length-matching rather than offset-following.

A plausibility bound is needed regardless -- a few false positives survive the
property walk, giving values like `1660731008` on Trieste A and Parade B. Real
squad sizes on this disc are 1..15.

# Player 2's first-person hands are never skinned

## The defect, measured

In split screen, player 2's view-model arms render in the `R61stHands` mesh's
own built-in material -- dark gloves and sleeves -- instead of the map's
mission skin. The user described it as "eddie is wearing another suit for his
view model".

It is not a mesh problem and not a skin-selection problem. Both player pawns
are the same class with the same mesh and the same body texture. The whole
defect is one empty array:

```
P1 FPHands 01a96e90  class=R61stHandsGripMP5  Mesh=R61stHands  Skins(data=0193ae10 count=1 max=1)
P2 FPHands 01c39ff0  class=R61stHandsGripMP5  Mesh=R61stHands  Skins(data=00000000 count=0 max=0)
```

Reproduced on three maps, always viewport 1 (savestate slots 2 Alpine, 4
Mountain Highway, 91 Trieste). Single player (slot 1) has the override.

The third-person difference visible in the same screenshot is **stock**: same
mesh, same body texture, no cap on either player. Only the per-operative head
texture differs (`R6RChaveshead` vs `R6RPricehead`), which is by design from
`m_iOperativeID`.

## Where it comes from

`R6RainbowTeam.CreatePlayerTeam` ends:

```
0x06b5: UpdateTeamGadgetStatus()
0x06bb: LoadMissionRainbowSkins()
0x06c1: m_TeamLeader.SetFirstPersonHandsSkin(GetMissionDescription().m_Skins.missionTeam)
0x06e1: PlayerController.<native2098>()
0x06ed: Return
```

`SetFirstPersonHandsSkin` is applied to exactly one object, `m_TeamLeader`.
`CreateTeamMember` assigns `m_TeamLeader` only on the first member
(`if (m_TeamLeader == None) m_TeamLeader = Rainbow`, mem `0x0ce0`), so it is
member 0 -- player 1. Confirmed in slot 2: `m_TeamLeader = 01a98e70 =
R6RainbowPriceWinter0 = viewport 0`.

There is no second call. Every one of the 14 occurrences of
`R61stWeapons_T.Hands.` in the decompressed package is inside
`SetFirstPersonHandsSkin` itself, which has three real call sites:
`CreatePlayerTeam` (above), `SetClientFirstPersonHandsSkin` (the online
wrapper), and `ReceivedWeapons`.

The controller asymmetry at mem `0x017d` is **not** the cause. Both pawns are
genuine `R6RainbowPriceWinter` instances with correct third-person skins; the
only asymmetry that matters is which one is the team leader.

## Why it cannot be fixed the way everything else here is fixed

Every edit in this project is a same-width operand swap, because this engine
hangs on any edit that re-assembles bytecode. Three levers were checked and
all three fail:

1. **Retarget the property ref.** The statement's only same-width lever is the
   2-byte `InstanceVariable` ref for `m_TeamLeader`. No property of
   `R6RainbowTeam` holds player 2's pawn -- `m_Team` is a 4-element static
   array, so `InstanceVariable(m_Team)` yields element 0, which is player 1
   again. Reaching `m_Team[1]` needs an `ArrayElement` token: 5 bytes instead
   of 3, so `ScriptSize` moves.

2. **Invert the team-leader test** at `CreateTeamMember` mem `0x0ce0`
   (`native114` -> `native119`, one byte). This only moves the defect onto
   player 1, and on rescue maps lands the call on Weber, leaving both players
   wrong.

3. **Enable the `ReceivedWeapons` call.** It is gated
   `m_bIsPlayer && Level.NetMode != 0`, dead in split screen, and the gate is
   a one-byte operand (`native155` -> `native154`). This looked like the fix
   and is not, for two independent reasons measured at mem `0x02a8`:

   ```
   SetFirstPersonHandsSkin(
       Level.SelectTeamSkin(PlayerReplicationInfo.TeamID,
                            PlayerReplicationInfo.m_u8PlayerFace),
       True(), iWeaponIdx)
   ```

   The argument is the **adversarial team skin** derived from `TeamID`, not
   `m_Skins.missionTeam`; and the gate tests `m_bIsPlayer`, which is true for
   BOTH players, so enabling it would overwrite player 1's correct winter
   skin as well. It would make both players wrong instead of one.

There is also no dead `Log()` payload at the right point to overwrite with an
equal-length statement. `CreatePlayerTeam` carries ~89 memory bytes of dead
log behind `if (bShowLog)` at mem `0x004a`, but that is before any team member
exists. The tail from `0x0688` to `0x06ed` is all live code.

**Conclusion: cosmetic, precisely located, and not reachable without
re-assembling bytecode.** Recorded rather than fixed.

## A separate defect on Trieste, also not shipped

The AI rescue targets on Trieste appear in the wrong outfit and without
headgear. Different cause: `LoadMissionRainbowSkins` clamps its loop in split
screen.

```
0x080a: if (Level.Game.m_bIsSplitScreen)
0x0825:     iMemberCount = 2          <- IntConstByte(2), plain 0x147E11
0x0830: else iMemberCount = m_iMemberCount
0x0842: while (i < iMemberCount) { switch(m_Team[i].m_iOperativeID) { Skins[]; AttachCap(); } }
```

On Trieste `CreatePlayerTeam` builds members 0-3, so Loiselle at index 2 and
Weber at index 3 are never skinned. Measured in slot 91: both have `Skins`
count 0 and `m_Cap = None`.

A one-byte fix exists -- plain `0x147E11`, `02` -> `04` -- and it is NOT
shipped. On every other split-screen map `m_Team[2]` and `m_Team[3]` are
`None` at that moment, and the stock loop never sees a `None` member because
`RemoveMember` decrements `m_iMemberCount` in lockstep. With a `None` member
the switch falls to case 0 and writes through a null array, and on non-winter
maps `AttachCap` would `Spawn` an orphan cap actor at the origin. It would fix
one map and put the other 26 on a path stock code never takes.

## Incidental: the SKIN enum, verified from data

`ERainbowSkin` is a real export in package `0x044d9d`. Its recorded offset is
relaid by the PS2 cooker, but the serialised `TArray<FName>` was located by
searching for the encoded element run, at file offset `0x04caf8`:

```
0 SKIN_Black      4 SKIN_Flecktorn   8 SKIN_EuroCamo   12 SKIN_WinterCamo
1 SKIN_BlackCamo  5 SKIN_Blue        9 SKIN_CadPat
2 SKIN_MarPat     6 SKIN_BlueCamo   10 SKIN_Desert
3 SKIN_Russian    7 SKIN_Green      11 SKIN_Winter
```

Exactly one 13-element FName array built from the SKIN_ names exists in the
whole image, in declaration order -- so the INI comment's ordering is correct,
confirmed independently of the comment. `bUseWinterMesh` is
`missionTeam == 11 || missionTeam == 12`, and Alpine Village authors
`SKIN_WinterCamo` = 12.

Only two maps author a winter skin: `ALPINES*` (`SKIN_WinterCamo`) and
`MOUNTAIN_HIGHWAY*` (`SKIN_Winter`). Trieste authors `SKIN_CadPat` = 9.

`m_Skins` reaches the game through `Object.LoadConfig("maps\<name>")` from
`R6MissionDescription.Init`, which reads `[Engine.R6MissionDescription]` out
of the map INI and converts the enum tag to its ordinal. Every map INI is a
single shared file -- only `.LIN` and `.DAT` come in `OFF`/`_SS` pairs -- so
`missionTeam` cannot differ between single player and split screen.

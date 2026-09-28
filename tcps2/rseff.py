"""Friendly fire: kill your own and the squad hunts you.

WHAT THE FIRST FOUR ATTEMPTS GOT WRONG
--------------------------------------

They marked the killer with `R6Pawn.m_bSuicided` and taught
`R6RainbowAI.SeePlayer` and `IsBeingAttacked` to read that mark. Measured on
the live game, that could never have worked: **`IsEnemy` is a bitmask test
and never consults that bool**.

    +0x384 m_iTeam           terrorist 1   rainbow 2
    +0x388 m_iFriendlyTeams  terrorist 2   rainbow 12   (bits 2,3)
    +0x38C m_iEnemyTeams     terrorist 12  rainbow 2    (bit 1)

`IsEnemy(other)` is `(1 << other.m_iTeam) & this.m_iEnemyTeams`. Writing the
player's `m_iTeam = 1` by hand, in play, made the squad open fire at once.
The mark was being written correctly the whole time -- proven independently,
because the mission-failure option fired from the SAME arm of
`PlaySoundDamage` behind the same gates -- and the targeting simply never
looked at it.

WHAT IT DOES NOW
----------------

One region of `R6RainbowAI.PlaySoundDamage`: when a player's round leaves a
teammate at the chosen hurt level, `instigatedBy.m_iTeam = 1`. That is the
terrorists' team, which every Rainbow AI already carries in its enemy mask,
so the stock `IsEnemy` returns true with no other edit anywhere. `SeePlayer`,
`IsBeingAttacked` and `SetTeamKillerPenalty` are left completely alone.

WHOSE SIDE THE TRAITOR ENDS UP ON
---------------------------------

Team 1 is the terrorists, so by default the traitor joins them.

The alternative -- put him on a team NOBODY carries as a friend -- was
written off here as needing a cave. That was wrong, and the reason it was
wrong is worth recording: the masks are indeed 0 in the class defaults and
assigned at spawn, but they are assigned by a SCRIPT function whose
constants sit on the disc. `R6GameInfo.SetDefaultTeamFriendlies` switches on
`m_iTeam` and writes both masks from `GetTeamNumBit(n)`, which is `1 << n`.
Widening an enemy mask is one byte per arm.

    terrorist arm   m_iEnemyTeams  12 -> 28   (12 | 1 << 4)
    rainbow   arm   m_iEnemyTeams   2 -> 18   ( 2 | 1 << 4)

With those two bytes changed, `m_iTeam = 4` makes both sides hunt him.
Team 4 is not a free number chosen at random: it is the engine's own "could
not put this player on a team" value, written by
`R6TeamDeathMatchGame.ResetPlayerTeam`, which is adversarial-only and
overrides `SetPawnTeamFriendlies` anyway. So this edit cannot reach online
play even by accident.

The mask edit is not polish. A team-4 pawn with the stock masks is not
hostile, it is NEUTRAL, and the bullet path zeroes damage against a neutral
unless the shooter's `m_bCanFireNeutrals` is set -- which Rainbow's default
does not. Without the masks the traitor would come out bulletproof.

Two things this corrects about the notes above: hostages are team 0, not 3
(team 3 is Bravo, the second Rainbow element), and Rainbow's friendly mask
12 is Alpha + Bravo rather than "Rainbow + hostage".

What it costs: his own masks are not re-derived, because the function runs
once at `PostBeginPlay`. His reticle still calls his old squad friendly, and
frag credit is gated on `IsEnemy`, so he starts scoring for squad kills
after the first one. His death still counts as a Rainbow loss, because
mission-failure accounting keys on `m_ePawnType`, not on team.

THE ONE PIECE OF PADDING HERE THAT RUNS
---------------------------------------

Dropping the `GetTeamNumBit` call shortens the statement in MEMORY by more
than on disk -- an object reference is 1 disk byte and 4 in memory -- so the
slot has to be topped back up with a reference-bearing token. Every other
padded region in this module hides its filler behind the payload's own
unconditional jump. These two cannot: the arm's budget is 14 disk / 22
memory, the assignment needs 12/17, and the only token that fills exactly
2 disk and 5 memory is one one-byte reference. There is nowhere to put a
three-byte jump around it.

So the filler executes, once per pawn spawned, and it has to be a read that
cannot fault. It is `InstanceVariable(import -15)`, `Engine.Actor.Level`:
`R6GameInfo` is an Actor, so the offset is inside the object, and the value
is a 4-byte pointer copied into the interpreter's scratch buffer and thrown
away. Counted on the shipped package, the disc's own bytecode reads that
same property through that same opcode 939 times, which is what makes it a
known-good read rather than an assumption -- the game has 2,450 distinct
instance-variable references and this is the second commonest of them.

WHAT IT COSTS
-------------

Terrorists carry team 1 in their FRIENDLY mask, so they stop shooting the
traitor. You murder your squad and the enemy loses interest: odd, but
coherent, and it is one property write instead of a cave.

Not established: whether squad ORDERS still reach a hostile AI. Observed in
play that they do, which reads strangely and has no obvious cheap fix --
the order path does not consult teams.

Where they are written
----------------------

`COMMONOFF.LIN` and `COMMON_SS.LIN` only: offline and split screen.
`COMMON.LIN` (online) is deliberately untouched.

Every region keeps its exact disk AND memory length, and the packages'
creation order is unchanged.
"""

from __future__ import annotations

H = bytes.fromhex


class FriendlyFireError(Exception):
    pass


#: option -> [(name, stock bytes, new bytes)]. Each stock run is unique in
#: every COMMON package, so the sites are found by CONTENT -- COMMON.LIN
#: carries the same bytecode a byte further along, and offsets would not
#: survive that.
REGIONS = {
    "fail_on_hit": [
    ("fail_on_hit 1",
     H(
        "82829a393a192e02006f1c05000101bd393a2401161810001901090600041b55"
        "04161618090096a72c64162c32161619191a26190109050010010a0500040194"
        "0800001b03241d16"),
     H(
        "192e02006f1c0600042d01b7192ea919018f05000401a60600001b5b0d160691"
        "010161320161320161320b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"
        "0b0b0b0b0b0b0b0b")),
    ("fail_on_hit 2",
     H(
        "ef01821901090600041b55041618090096a72c64162c3216161b03241c160610"
        "02"),
     H(
        "100219006f1c0600042d01b706440101080b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"
        "0b")),
    ],
    "fail_on_kill": [
    ("fail_on_kill 1",
     H(
        "82829a393a192e02006f1c05000101bd393a2401161810001901090600041b55"
        "04161618090096a72c64162c32161619191a26190109050010010a0500040194"
        "0800001b03241d16"),
     H(
        "192e02006f1c0600042d01b707910197393a19010805000101fa012c04161919"
        "018f05000401a60600001b5b0d160691010161320161320b0b0b0b0b0b0b0b0b"
        "0b0b0b0b0b0b0b0b")),
    ],
    #: `R6GameInfo.SetDefaultTeamFriendlies`, the one place either mask is
    #: ever written. Each region turns `m_iEnemyTeams = GetTeamNumBit(n)`
    #: into a plain constant with bit 4 already in it, so team 4 -- nobody's
    #: team -- reads as an enemy to both sides. The call is five bytes and
    #: the constant is two, so the two spare bytes are the assignment the
    #: call used to need; nothing is named and nothing moves.
    "noside": [
    ("noside terrorists",
     H("0401d5011b082c0216a1190013"),
     H("0401d5012c1c018f0ba1190013")),
    ("noside rainbow",
     H("001305000401d5011b08261606bd020affffe770"),
     H("001305000401d5012c12018f06bd020affffe770")),
    ],
}

#: What team the traitor is moved to. 1 is the terrorists, who already carry
#: him in their friendly mask, so they stop shooting him. 4 is nobody's, and
#: only works with the `noside` regions above -- without them he is neutral
#: rather than hostile, and neutrals take no damage.
ROGUE_TEAM = {"terrorists": 1, "noside": 4}

#: `Let(instigatedBy.m_iTeam, IntConstByte(N))` at the end of every trigger
#: payload: the import reference for `m_iTeam`, then the constant opcode. The
#: byte after this run is the team.
_TEAM_LET = H("c3022c")


#: How far you have to hurt a teammate before the squad turns. The key is the
#: value of `m_eHealth` the victim must be driven to -- the same number the HUD
#: teammate bar shows -- so no counter has to be stored anywhere. That matters:
#: a true "count the shots" tally needs a per-player int that script already
#: references and nothing consumes, and NO property in the package satisfies
#: both. The two that read as purpose-built, `m_iBulletsFired` and
#: `m_iBulletsHit`, are referenced by nothing, so naming one would insert an
#: object into the package's creation order and desync the level load.
#:
#: "5" is a kill. It USED to write nothing here and lean on
#: `SetTeamKillerPenalty`, which was wrong in practice: measured after a team
#: kill in Terrorist Hunt, the killed AI lights up with its death bools and
#: NEITHER player gains anything near `R6Pawn`'s own property cluster around
#: +0x370..+0x3A0, where `m_ePawnType` and `m_eHealth` live. The mark was not
#: being written at all, so the squad never turned.
#:
#: The likely reason is that `SetTeamKillerPenalty` is declared on
#: `R6GameInfo` and reached BY NAME from the death path, so it runs only if
#: the live game class inherits `R6GameInfo` -- which a Terrorist Hunt game
#: need not. The patched function was correct and simply never entered.
#:
#: So "5" now writes the mark from `PlaySoundDamage` like every other
#: setting, which is the AI's own damage handler and demonstrably runs: it is
#: where the shipped "watch your fire" line comes from. The write is
#: idempotent with `SetTeamKillerPenalty`'s, so it is safe either way.
#:
#: Every setting ends at the same `instigatedBy.m_bSuicided = True`, so
#: `SeePlayer` and `IsBeingAttacked` are identical whichever is chosen.
#:
#: NOT a running total across the squad: N is how far ONE teammate has been
#: driven. At N >= 2 the earlier wounds need not all be yours -- the rule is
#: "your round landed, and it left him at that state or worse". At N = 1 there
#: is no ambiguity.
TRIGGER = {
    "1": [
        ("go rogue 1.1",
         H(
            "82829a393a192e02006f1c05000101bd393a240116181000190109060004"
            "1b5504161618090096a72c64162c32161619191a26190109050010010a05"
            "000401940800001b03241d16"),
         H(
            "192e02006f1c0600042d01b707910197393a19010805000101fa012c0016"
            "0f19006f1c05000401c3022c010691010161320161320161320161320b0b"
            "0b0b0b0b0b0b0b0b0b0b0b0b")),
        ("go rogue 1.2",
         H(
            "ef01821901090600041b55041618090096a72c64162c3216161b03241c16"
            "061002"),
         H(
            "100219006f1c0600042d01b706440101080b0b0b0b0b0b0b0b0b0b0b0b0b"
            "0b0b0b")),
    ],
    "2": [
        ("go rogue 2.1",
         H(
            "82829a393a192e02006f1c05000101bd393a240116181000190109060004"
            "1b5504161618090096a72c64162c32161619191a26190109050010010a05"
            "000401940800001b03241d16"),
         H(
            "192e02006f1c0600042d01b707910197393a19010805000101fa012c0116"
            "0f19006f1c05000401c3022c010691010161320161320161320161320b0b"
            "0b0b0b0b0b0b0b0b0b0b0b0b")),
        ("go rogue 2.2",
         H(
            "ef01821901090600041b55041618090096a72c64162c3216161b03241c16"
            "061002"),
         H(
            "100219006f1c0600042d01b706440101080b0b0b0b0b0b0b0b0b0b0b0b0b"
            "0b0b0b")),
    ],
    "3": [
        ("go rogue 3.1",
         H(
            "82829a393a192e02006f1c05000101bd393a240116181000190109060004"
            "1b5504161618090096a72c64162c32161619191a26190109050010010a05"
            "000401940800001b03241d16"),
         H(
            "192e02006f1c0600042d01b707910197393a19010805000101fa012c0216"
            "0f19006f1c05000401c3022c010691010161320161320161320161320b0b"
            "0b0b0b0b0b0b0b0b0b0b0b0b")),
        ("go rogue 3.2",
         H(
            "ef01821901090600041b55041618090096a72c64162c3216161b03241c16"
            "061002"),
         H(
            "100219006f1c0600042d01b706440101080b0b0b0b0b0b0b0b0b0b0b0b0b"
            "0b0b0b")),
    ],
    "4": [
        ("go rogue 4.1",
         H(
            "82829a393a192e02006f1c05000101bd393a240116181000190109060004"
            "1b5504161618090096a72c64162c32161619191a26190109050010010a05"
            "000401940800001b03241d16"),
         H(
            "192e02006f1c0600042d01b707910197393a19010805000101fa012c0316"
            "0f19006f1c05000401c3022c010691010161320161320161320161320b0b"
            "0b0b0b0b0b0b0b0b0b0b0b0b")),
    ],
    "5": [
        ("go rogue 5.1",
         H(
            "82829a393a192e02006f1c05000101bd393a240116181000190109060004"
            "1b5504161618090096a72c64162c32161619191a26190109050010010a05"
            "000401940800001b03241d16"),
         H(
            "192e02006f1c0600042d01b707910197393a19010805000101fa012c0416"
            "0f19006f1c05000401c3022c010691010161320161320161320161320b0b"
            "0b0b0b0b0b0b0b0b0b0b0b0b")),
    ],
}

#: The SAME mark, written when the victim is a human player.
#:
#: The shipped table above lives in `R6RainbowAI.PlaySoundDamage`, which is
#: the AI's own damage handler: a player pawn is not an `R6RainbowAI`, so
#: shooting the other player in split screen ran none of it and the squad
#: never turned. That was reported from play, and this is the fix.
#:
#: Two sites, because no single one serves every notch of the dial:
#:
#:   `R6Pawn.R6Died` (block 0x0F587F, 1069 disk / 1444 mem) is the death
#:   handler on the pawn itself and takes the killer as a local, so ONE
#:   region covers an AI squadmate and a human alike. It can only serve a
#:   KILL -- by the time it runs the victim is dead. Its budget is the two
#:   `Level.NetMode` blocks in the middle, an online-only death-message and
#:   stats path, so offline the edit costs nothing you can see or hear.
#:
#:   `R6PlayerController.PlaySoundDamage` (block 0x10B465, 283 / 375) is the
#:   sibling of the shipped AI hook and serves the wounded notches. Its
#:   budget is its two `!m_bIsSplitScreen` callout blocks, dead in split
#:   screen -- so this costs only the single-player "player is hit" lines.
#:
#: `R6Pawn.R6TakeDamage` was the obvious candidate and is NOT script on PS2:
#: it is 28 bytes that tail-call a native, and the whole damage body -- the
#: log lines that would have been ideal budget included -- is C++. That is
#: also why the dispatch never reached a player: `PlaySoundDamage` is
#: selected by a native virtual call on the victim's own controller.
#:
#: Keyed by the same `which` strings the dial uses, with the team already
#: baked in rather than substituted, because the two sites encode it
#: differently.
PLAYERKILL = {
    "trigger:1": [
    ("playerkill died",
     H(
        "07ee02849a393a19018f05000101a2393a2401161817009a393a19018f050001"
        "01a2393a2402161607ee02849b393a01720526161820009a393a1919018f0500"
        "0401a605000101f001393a24071616196a48160d00006b6200490900601016"),
     H(
        "07ee029a393a01bd393a24011607ee02770042072a1607ee0277004207171607"
        "ee02192e020042070600042d01b70f1900420705000401c3022c0106ee02018f"
        "0161320161320b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"),
    ),
    ("playerkill psd 1",
     H(
        "07a100811919018f05000401a60600042d01ed011607a1008297190120050004"
        "01162516181400771a26190120050010010a2a161619191a2619012005001001"
        "0a05000401940800001b03241716"),
     H(
        "07a1007700482e2a1607a100192e0200482e0600042d01b707a10097393a1901"
        "0b05000101fa012c00160f1900482e05000401c3022c0106a100018f01613201"
        "61320161320161320161320b0b0b"),
    ),
    ("playerkill psd 2",
     H(
        "076f01811919018f05000401a60600042d01ed0116076f018282827700482e2a"
        "161812009719012005000401162516161810001901200600041b550416161809"
        "0098a72c64162c0a161619191a26190120050010010a05000401940800001b03"
        "246616"),
     H(
        "076f017700482e2a16076f01192e0200482e0600042d01b7076f0197393a1901"
        "0b05000101fa012c00160f1900482e05000401c3022c01066f01016132016132"
        "0161320161320161320161320161320b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"
        "0b0b0b"),
    ),
    ],
    "trigger:1:noside": [
    ("playerkill died noside",
     H(
        "07ee02849a393a19018f05000101a2393a2401161817009a393a19018f050001"
        "01a2393a2402161607ee02849b393a01720526161820009a393a1919018f0500"
        "0401a605000101f001393a24071616196a48160d00006b6200490900601016"),
     H(
        "07ee029a393a01bd393a24011607ee02770042072a1607ee0277004207171607"
        "ee02192e020042070600042d01b70f1900420705000401c3022c0406ee02018f"
        "0161320161320b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"),
    ),
    ("playerkill psd 1 noside",
     H(
        "07a100811919018f05000401a60600042d01ed011607a1008297190120050004"
        "01162516181400771a26190120050010010a2a161619191a2619012005001001"
        "0a05000401940800001b03241716"),
     H(
        "07a1007700482e2a1607a100192e0200482e0600042d01b707a10097393a1901"
        "0b05000101fa012c00160f1900482e05000401c3022c0406a100018f01613201"
        "61320161320161320161320b0b0b"),
    ),
    ("playerkill psd 2 noside",
     H(
        "076f01811919018f05000401a60600042d01ed0116076f018282827700482e2a"
        "161812009719012005000401162516161810001901200600041b550416161809"
        "0098a72c64162c0a161619191a26190120050010010a05000401940800001b03"
        "246616"),
     H(
        "076f017700482e2a16076f01192e0200482e0600042d01b7076f0197393a1901"
        "0b05000101fa012c00160f1900482e05000401c3022c04066f01016132016132"
        "0161320161320161320161320161320b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"
        "0b0b0b"),
    ),
    ],
    "trigger:2": [
    ("playerkill died",
     H(
        "07ee02849a393a19018f05000101a2393a2401161817009a393a19018f050001"
        "01a2393a2402161607ee02849b393a01720526161820009a393a1919018f0500"
        "0401a605000101f001393a24071616196a48160d00006b6200490900601016"),
     H(
        "07ee029a393a01bd393a24011607ee02770042072a1607ee0277004207171607"
        "ee02192e020042070600042d01b70f1900420705000401c3022c0106ee02018f"
        "0161320161320b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"),
    ),
    ("playerkill psd 1",
     H(
        "07a100811919018f05000401a60600042d01ed011607a1008297190120050004"
        "01162516181400771a26190120050010010a2a161619191a2619012005001001"
        "0a05000401940800001b03241716"),
     H(
        "07a1007700482e2a1607a100192e0200482e0600042d01b707a10097393a1901"
        "0b05000101fa012c01160f1900482e05000401c3022c0106a100018f01613201"
        "61320161320161320161320b0b0b"),
    ),
    ("playerkill psd 2",
     H(
        "076f01811919018f05000401a60600042d01ed0116076f018282827700482e2a"
        "161812009719012005000401162516161810001901200600041b550416161809"
        "0098a72c64162c0a161619191a26190120050010010a05000401940800001b03"
        "246616"),
     H(
        "076f017700482e2a16076f01192e0200482e0600042d01b7076f0197393a1901"
        "0b05000101fa012c01160f1900482e05000401c3022c01066f01016132016132"
        "0161320161320161320161320161320b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"
        "0b0b0b"),
    ),
    ],
    "trigger:2:noside": [
    ("playerkill died noside",
     H(
        "07ee02849a393a19018f05000101a2393a2401161817009a393a19018f050001"
        "01a2393a2402161607ee02849b393a01720526161820009a393a1919018f0500"
        "0401a605000101f001393a24071616196a48160d00006b6200490900601016"),
     H(
        "07ee029a393a01bd393a24011607ee02770042072a1607ee0277004207171607"
        "ee02192e020042070600042d01b70f1900420705000401c3022c0406ee02018f"
        "0161320161320b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"),
    ),
    ("playerkill psd 1 noside",
     H(
        "07a100811919018f05000401a60600042d01ed011607a1008297190120050004"
        "01162516181400771a26190120050010010a2a161619191a2619012005001001"
        "0a05000401940800001b03241716"),
     H(
        "07a1007700482e2a1607a100192e0200482e0600042d01b707a10097393a1901"
        "0b05000101fa012c01160f1900482e05000401c3022c0406a100018f01613201"
        "61320161320161320161320b0b0b"),
    ),
    ("playerkill psd 2 noside",
     H(
        "076f01811919018f05000401a60600042d01ed0116076f018282827700482e2a"
        "161812009719012005000401162516161810001901200600041b550416161809"
        "0098a72c64162c0a161619191a26190120050010010a05000401940800001b03"
        "246616"),
     H(
        "076f017700482e2a16076f01192e0200482e0600042d01b7076f0197393a1901"
        "0b05000101fa012c01160f1900482e05000401c3022c04066f01016132016132"
        "0161320161320161320161320161320b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"
        "0b0b0b"),
    ),
    ],
    "trigger:3": [
    ("playerkill died",
     H(
        "07ee02849a393a19018f05000101a2393a2401161817009a393a19018f050001"
        "01a2393a2402161607ee02849b393a01720526161820009a393a1919018f0500"
        "0401a605000101f001393a24071616196a48160d00006b6200490900601016"),
     H(
        "07ee029a393a01bd393a24011607ee02770042072a1607ee0277004207171607"
        "ee02192e020042070600042d01b70f1900420705000401c3022c0106ee02018f"
        "0161320161320b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"),
    ),
    ("playerkill psd 1",
     H(
        "07a100811919018f05000401a60600042d01ed011607a1008297190120050004"
        "01162516181400771a26190120050010010a2a161619191a2619012005001001"
        "0a05000401940800001b03241716"),
     H(
        "07a1007700482e2a1607a100192e0200482e0600042d01b707a10097393a1901"
        "0b05000101fa012c02160f1900482e05000401c3022c0106a100018f01613201"
        "61320161320161320161320b0b0b"),
    ),
    ("playerkill psd 2",
     H(
        "076f01811919018f05000401a60600042d01ed0116076f018282827700482e2a"
        "161812009719012005000401162516161810001901200600041b550416161809"
        "0098a72c64162c0a161619191a26190120050010010a05000401940800001b03"
        "246616"),
     H(
        "076f017700482e2a16076f01192e0200482e0600042d01b7076f0197393a1901"
        "0b05000101fa012c02160f1900482e05000401c3022c01066f01016132016132"
        "0161320161320161320161320161320b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"
        "0b0b0b"),
    ),
    ],
    "trigger:3:noside": [
    ("playerkill died noside",
     H(
        "07ee02849a393a19018f05000101a2393a2401161817009a393a19018f050001"
        "01a2393a2402161607ee02849b393a01720526161820009a393a1919018f0500"
        "0401a605000101f001393a24071616196a48160d00006b6200490900601016"),
     H(
        "07ee029a393a01bd393a24011607ee02770042072a1607ee0277004207171607"
        "ee02192e020042070600042d01b70f1900420705000401c3022c0406ee02018f"
        "0161320161320b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"),
    ),
    ("playerkill psd 1 noside",
     H(
        "07a100811919018f05000401a60600042d01ed011607a1008297190120050004"
        "01162516181400771a26190120050010010a2a161619191a2619012005001001"
        "0a05000401940800001b03241716"),
     H(
        "07a1007700482e2a1607a100192e0200482e0600042d01b707a10097393a1901"
        "0b05000101fa012c02160f1900482e05000401c3022c0406a100018f01613201"
        "61320161320161320161320b0b0b"),
    ),
    ("playerkill psd 2 noside",
     H(
        "076f01811919018f05000401a60600042d01ed0116076f018282827700482e2a"
        "161812009719012005000401162516161810001901200600041b550416161809"
        "0098a72c64162c0a161619191a26190120050010010a05000401940800001b03"
        "246616"),
     H(
        "076f017700482e2a16076f01192e0200482e0600042d01b7076f0197393a1901"
        "0b05000101fa012c02160f1900482e05000401c3022c04066f01016132016132"
        "0161320161320161320161320161320b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"
        "0b0b0b"),
    ),
    ],
    "trigger:4": [
    ("playerkill died",
     H(
        "07ee02849a393a19018f05000101a2393a2401161817009a393a19018f050001"
        "01a2393a2402161607ee02849b393a01720526161820009a393a1919018f0500"
        "0401a605000101f001393a24071616196a48160d00006b6200490900601016"),
     H(
        "07ee029a393a01bd393a24011607ee02770042072a1607ee0277004207171607"
        "ee02192e020042070600042d01b70f1900420705000401c3022c0106ee02018f"
        "0161320161320b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"),
    ),
    ("playerkill psd 1",
     H(
        "07a100811919018f05000401a60600042d01ed011607a1008297190120050004"
        "01162516181400771a26190120050010010a2a161619191a2619012005001001"
        "0a05000401940800001b03241716"),
     H(
        "07a1007700482e2a1607a100192e0200482e0600042d01b707a10097393a1901"
        "0b05000101fa012c03160f1900482e05000401c3022c0106a100018f01613201"
        "61320161320161320161320b0b0b"),
    ),
    ],
    "trigger:4:noside": [
    ("playerkill died noside",
     H(
        "07ee02849a393a19018f05000101a2393a2401161817009a393a19018f050001"
        "01a2393a2402161607ee02849b393a01720526161820009a393a1919018f0500"
        "0401a605000101f001393a24071616196a48160d00006b6200490900601016"),
     H(
        "07ee029a393a01bd393a24011607ee02770042072a1607ee0277004207171607"
        "ee02192e020042070600042d01b70f1900420705000401c3022c0406ee02018f"
        "0161320161320b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"),
    ),
    ("playerkill psd 1 noside",
     H(
        "07a100811919018f05000401a60600042d01ed011607a1008297190120050004"
        "01162516181400771a26190120050010010a2a161619191a2619012005001001"
        "0a05000401940800001b03241716"),
     H(
        "07a1007700482e2a1607a100192e0200482e0600042d01b707a10097393a1901"
        "0b05000101fa012c03160f1900482e05000401c3022c0406a100018f01613201"
        "61320161320161320161320b0b0b"),
    ),
    ],
    "trigger:5": [
    ("playerkill died",
     H(
        "07ee02849a393a19018f05000101a2393a2401161817009a393a19018f050001"
        "01a2393a2402161607ee02849b393a01720526161820009a393a1919018f0500"
        "0401a605000101f001393a24071616196a48160d00006b6200490900601016"),
     H(
        "07ee029a393a01bd393a24011607ee02770042072a1607ee0277004207171607"
        "ee02192e020042070600042d01b70f1900420705000401c3022c0106ee02018f"
        "0161320161320b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"),
    ),
    ("playerkill psd 1",
     H(
        "07a100811919018f05000401a60600042d01ed011607a1008297190120050004"
        "01162516181400771a26190120050010010a2a161619191a2619012005001001"
        "0a05000401940800001b03241716"),
     H(
        "07a1007700482e2a1607a100192e0200482e0600042d01b707a10097393a1901"
        "0b05000101fa012c04160f1900482e05000401c3022c0106a100018f01613201"
        "61320161320161320161320b0b0b"),
    ),
    ],
    "trigger:5:noside": [
    ("playerkill died noside",
     H(
        "07ee02849a393a19018f05000101a2393a2401161817009a393a19018f050001"
        "01a2393a2402161607ee02849b393a01720526161820009a393a1919018f0500"
        "0401a605000101f001393a24071616196a48160d00006b6200490900601016"),
     H(
        "07ee029a393a01bd393a24011607ee02770042072a1607ee0277004207171607"
        "ee02192e020042070600042d01b70f1900420705000401c3022c0406ee02018f"
        "0161320161320b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"),
    ),
    ("playerkill psd 1 noside",
     H(
        "07a100811919018f05000401a60600042d01ed011607a1008297190120050004"
        "01162516181400771a26190120050010010a2a161619191a2619012005001001"
        "0a05000401940800001b03241716"),
     H(
        "07a1007700482e2a1607a100192e0200482e0600042d01b707a10097393a1901"
        "0b05000101fa012c04160f1900482e05000401c3022c0406a100018f01613201"
        "61320161320161320161320b0b0b"),
    ),
    ],
}


#: Offline single player and split screen. NOT the online package.
SELECT = r"/COMMON(OFF|_SS)\.LIN$"


def _reteam(new: bytes, team: int) -> bytes:
    """A trigger payload with a different team in its `m_iTeam` write.

    Payloads that carry no such write come back untouched -- each hurt level
    above 1 is two regions and only the first of them assigns the team.
    """
    at = new.find(_TEAM_LET)
    if at < 0:
        return new
    if new.find(_TEAM_LET, at + 1) >= 0:
        raise FriendlyFireError("a payload writes m_iTeam more than once")
    cut = at + len(_TEAM_LET)
    return new[:cut] + bytes([team]) + new[cut + 1:]


def _table(which: str):
    """The regions for an option name, or for a trigger setting `trigger:N`.

    A trigger may name the side as well -- `trigger:N:noside` -- which only
    changes the one byte holding the team.
    """
    if which.startswith("playerkill:"):
        _, key, side = (which + ":terrorists").split(":")[:3]
        if side not in ROGUE_TEAM:
            raise FriendlyFireError("no such side: %r" % side)
        # The team is baked into these, so they are keyed by the whole name
        # rather than substituted a byte at a time.
        name = "trigger:" + key + ("" if side == "terrorists" else ":" + side)
        if name not in PLAYERKILL:
            raise FriendlyFireError("no such trigger setting: %r" % key)
        return PLAYERKILL[name]
    if which.startswith("trigger:"):
        _, key, side = (which + ":terrorists").split(":")[:3]
        if key not in TRIGGER:
            raise FriendlyFireError("no such trigger setting: %r" % key)
        if side not in ROGUE_TEAM:
            raise FriendlyFireError("no such side: %r" % side)
        team = ROGUE_TEAM[side]
        return [(n if side == "terrorists" else n + " " + side,
                 stock, _reteam(new, team))
                for n, stock, new in TRIGGER[key]]
    if which not in REGIONS:
        raise FriendlyFireError("no such friendly-fire option: %r" % which)
    return REGIONS[which]


def _sites(plain: bytes, which: str):
    """[(offset, stock, new, state)] or raise."""
    out = []
    for name, stock, new in _table(which):
        hits = []
        for form, state in ((stock, "stock"), (new, "new")):
            at = plain.find(form)
            if at >= 0 and plain.find(form, at + 1) >= 0:
                raise FriendlyFireError("%s: found more than once" % name)
            if at >= 0:
                hits.append((at, state))
        if len(hits) != 1:
            raise FriendlyFireError(
                "%s: %s" % (name, "not found" if not hits
                            else "both forms present"))
        out.append((hits[0][0], stock, new, hits[0][1]))
    return out


def reads(plain: bytes, which: str) -> bool:
    try:
        return all(s[3] == "new" for s in _sites(plain, which))
    except FriendlyFireError:
        return False


def apply(plain: bytes, which: str, enable: bool = True):
    """Returns (bytes, changed). The length never moves."""
    if not _table(which):          # trigger:5 -- the kill default
        return plain, 0
    want_new = bool(enable)
    if reads(plain, which) == want_new:
        return plain, 0
    out = bytearray(plain)
    n = 0
    for at, stock, new, state in _sites(plain, which):
        want = new if want_new else stock
        if out[at:at + len(stock)] != want:
            out[at:at + len(stock)] = want
            n += 1
    if len(out) != len(plain):
        raise FriendlyFireError("a friendly-fire edit changed the file length")
    return bytes(out), n


def cards(prefix, group):
    from .model import BOOL, CHOICE, Choice, Setting

    return [
        Setting(
            prefix + "ff_trigger", "How far before they turn on you", CHOICE,
            "5", group,
            requires={prefix + "ff_retaliate": [True],
                      prefix + "ff_fail_mission": [False]},
            choices=[
                Choice("5", "Only if you kill one",
                       "They turn when a teammate actually dies, and not "
                       "for a wounding."),
                Choice("4", "If you put one down",
                       "A teammate dropped, but not killed."),
                Choice("3", "Badly wounded"),
                Choice("2", "Wounded"),
                Choice("1", "The first round that draws blood",
                       "One stray hit and the squad turns."),
            ],
            confidence="experimental", touches="data",
            help="How badly you have to hurt one of your own before the squad "
                 "turns on you. It reads the teammate's condition -- the same "
                 "bar you see beside their name -- rather than counting "
                 "shots, because the game has nowhere to keep a tally that "
                 "would survive between hits.\n\n"
                 "It is per teammate, not a running total across the squad. "
                 "From \"wounded\" onwards the earlier damage need not all "
                 "be yours: the rule is that your round landed and left him "
                 "at that condition or worse.",
            caution="Not yet played. It cannot be combined with the mission "
                    "failure option below -- both need the same piece of the "
                    "game's damage handling. That costs you nothing when the "
                    "mission fails on a KILL, because a kill is this dial's "
                    "own default and asks for no part of it.\n\n"
                    "Every setting costs the \"man down\" callout for a "
                    "friendly casualty, and everything below \"put one down\" "
                    "also costs the \"watch your fire\" line."),
        Setting(
            prefix + "ff_player_victim",
            "Killing the other player counts too", BOOL, False, group,
            requires={prefix + "ff_retaliate": [True],
                      prefix + "ff_fail_mission": [False]},
            confidence="experimental", touches="data",
            help="Shooting the other player in split screen did nothing, "
                 "because the squad's change of heart is written from the "
                 "AI's own damage handler and a player is not one of them. "
                 "This writes the same thing from the two places a human "
                 "casualty does go through: the pawn's own death handler, "
                 "which covers a kill, and the player controller's damage "
                 "handler, which covers the wounded settings.\n\n"
                 "It reads the same dial as the rest, so whatever you have "
                 "chosen above applies to both kinds of teammate.",
            caution="Not yet played. Offline and split screen only.\n\n"
                    "The kill setting is nearly free: the room it uses is an "
                    "online-only death-message path that cannot run offline "
                    "at all. The wounded settings cost the single-player "
                    "\"player is hit\" call-outs -- in split screen those "
                    "lines are already switched off, so there it costs "
                    "nothing either.\n\n"
                    "What no reading of the game can settle is whether the "
                    "killer recorded on a player-versus-player kill really "
                    "is the other player's pawn. If it is not, nothing is "
                    "written and you are back to where you started."),
        Setting(
            prefix + "ff_rogue_side", "Whose side he ends up on", CHOICE,
            "terrorists", group,
            requires={prefix + "ff_retaliate": [True],
                      prefix + "ff_fail_mission": [False]},
            choices=[
                Choice("terrorists", "He joins the terrorists",
                       "Your squad hunts him, and the terrorists stop "
                       "shooting at him."),
                Choice("noside", "Nobody's side",
                       "Both sides want him dead. Terrorists keep shooting "
                       "him, and so does his old squad."),
            ],
            confidence="experimental", touches="data",
            help="The game moves a traitor onto another team, and there are "
                 "only two it can use. The terrorists' team is the cheap "
                 "one, because every Rainbow operative already counts it as "
                 "an enemy -- but so do the terrorists count it as a friend, "
                 "so murdering your own squad buys you safe passage through "
                 "the enemy, which is not what anyone wants.\n\n"
                 "Nobody's side puts him on a team the game keeps for "
                 "players it could not place, and widens what both sides "
                 "treat as an enemy to include it. Two bytes, and everyone "
                 "in the level shoots him.",
            caution="Not yet played. Offline and split screen only -- the "
                    "team it uses is one the online modes assign their own "
                    "way, so this cannot reach them.\n\n"
                    "The traitor's own reading of the world does not change: "
                    "his reticle still calls his old squad friendly, and "
                    "once he is hostile the game starts giving him credit "
                    "for killing them."),
        Setting(
            prefix + "ff_retaliate",
            "Teammates turn on you if you kill one of them", BOOL, False,
            group, confidence="experimental", touches="data",
            help="Kill one of your own squad and the survivors treat you as "
                 "hostile -- the way SOCOM handles it. The one you shot turns "
                 "on you straight away; the others come for you when they see "
                 "you. It works by moving you onto another team, so the "
                 "game's own \"is this a friend\" test does all the deciding "
                 "and nothing new has to know who counts as a teammate.",
            caution="Not yet played. Offline and split screen only -- online "
                    "is deliberately untouched.\n\n"
                    "A teammate normally cannot hurt you at all; this switches "
                    "that off for one who has turned, so their rounds land. "
                    "What has not been seen is how they behave once hostile: "
                    "whether they path to you properly, and what your squad "
                    "orders do to a teammate who is trying to kill you."),
        Setting(
            prefix + "ff_fail_when", "What ends the mission", CHOICE,
            "kill", group, requires={prefix + "ff_fail_mission": [True]},
            choices=[
                Choice("kill", "Only if you kill one",
                       "A teammate has to actually die. Wounding one, or "
                       "putting one down, does not."),
                Choice("wound", "Any hit that wounds one",
                       "The first round that changes a teammate's condition "
                       "ends the run."),
            ],
            confidence="experimental", touches="data",
            help="Whether the run ends the moment you hurt one of your own, "
                 "or only once you have killed one.\n\n"
                 "A kill is the setting that leaves room for the squad to "
                 "turn on you first: wounding ends the mission on the first "
                 "stray round, before any of that can happen.",
            caution="Not yet played. The kill setting reads the teammate's "
                    "condition at the moment your round lands, so it needs "
                    "that round to be the one that kills him.\n\n"
                    "What no reading of the game can settle is whether a "
                    "fatal hit reports as dead or as down. If it reports as "
                    "down, nothing fires here and the mission ends the "
                    "ordinary way instead, through the squad-losses "
                    "objective most missions carry."),
        Setting(
            prefix + "ff_fail_mission",
            "The mission fails if you shoot a teammate", BOOL, False, group,
            confidence="experimental", touches="data",
            help="Hurting your own squad ends the mission, with the same "
                 "failure a dead operative causes. The setting above decides "
                 "whether that means killing one or merely wounding one.\n\n"
                 "Neither keys on a shot, because the game cannot see a near "
                 "miss -- nothing reports one.",
            caution="Not yet played. Offline and split screen only.\n\n"
                    "In split screen it counts the other player's AI "
                    "teammates too."),
    ]

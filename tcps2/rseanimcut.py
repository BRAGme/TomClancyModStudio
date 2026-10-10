r"""Animations Red Storm authored, shipped, and bound to nothing.

Rainbow Six 3 keeps its character animation in UE2 `MeshAnimation` containers.
`RainbowAnim` holds 207 sequences, and **seventeen of them are named by
nothing** -- absent from every script `EX_NameConst`, from the native overlay
string table, and from every serialised name property in all 132 package
tables of all three COMMON packages. They cannot be reached, because a name is
encoded as an index into the REFERRING package's table and no package outside
RainbowAnim's own host carries them.

THE THEME
---------

Every interactive animation ships an unused "begin" segment. The dispatcher
only ever plays the `_c` middle, on a loop::

    LoopAnim('StandLockPick_c', 2.0, 0.2, 1)

so the reach-to-the-lock motion (`_b`) never plays and the hold pose repeats
instead. Lock-pick, keypad, keyboard, bug and bomb all do this. The claymore
and the remote charge go further: both loop their placing pose forever and
their COMMIT beats, `CrouchClaymoreFire` and `CrouchC4Fire`, are played by
nothing. The shotgun is never seen to pump in third person, the LMG's tactical
reload is bound by no weapon class, and both 180-degree about-faces are unused.

THE EDIT
--------

The cut names cannot be referenced, so nothing can be repointed AT them.
Instead each swap exchanges the two-byte compact `Name` index between the
record the game already plays and the cut record, inside `RainbowAnim`'s own
`AnimSeqs` array. `Moves` is parallel to `AnimSeqs` by index, so the whole
sequence definition -- keyframes, frame count, rate, notifies -- travels with
the name. Two bytes against two bytes, so `lin.substitute`'s equal-length rule
holds and no name table grows.

A record is::

    +0        f32            an unidentified leading float (0.0 in 205 of 207)
    +4        compact index  Name          <-- the two bytes patched here
    then      compact count  Groups, then n compact FNames
    then      i32            StartFrame
    then      i32            NumFrames
    then      compact count  Notifys, then n x (f32 Time, compact Function, Object)
    then      f32            Rate

The array sits at plain 0x4BC76E in COMMON.LIN and 0x200E lower in COMMONOFF
and COMMON_SS, whose plain bytes are identical to each other. That shift was
measured per record across all 207, not assumed.

WHAT EACH LEVEL COSTS
---------------------

The risk is not uniform, and it turns on which native plays the clip. Decoded
from the gameplay package: `LoopAnim` is extended native 260, `PlayAnim` 259.

* **safe** -- the four LOW swaps and the one SAFE one. Both turns, the ladder
  dismount, the LMG reload, a second burn variation. All low stakes.
* **interactive** -- adds the eight `_b` begin segments and the shotgun pump.
  The begin swaps are all `LoopAnim`, which never blocks, so **nothing can get
  stuck**: the action's length is the game's own timer. The cost is cosmetic --
  seven of the eight cut clips are shorter than what they replace, so the loop
  cycles faster. The worst is the standing lock-pick, where a 0.60 s reach
  loops in place of a 3.00 s hold.
* **everything** -- adds the two plant commits, and these are the ones to look
  at first. Both are `PlayAnim`, one-shot: the clip now ENDS EARLY (1.00 s
  against 2.75 s) and UE2 holds the final frame, so the character completes the
  commit and then freezes on its last pose for the rest of the plant timer.
  Not stuck, but visibly frozen.

One swap was specified and dropped: `StandShotGunLow_nt` / `StandShotGunHigh_nt`.
The "High" name appears in a SECOND package's table, so the premise that
nothing can name it fails, and both sides are 2-frame poses that would show
nothing anyway. A second, `StandLadderSlide` / `StandLadderSlide_nt`, is left
out because its playing native could not be resolved.

NOT PLAY-TESTED. Every offset, every stock byte and every name index was read
back off the pristine packages -- 96 writes, zero mismatches -- and the playing
native was decoded per swap. That the swapped clip then renders is inferred
from UE2's `Moves`/`AnimSeqs` parallelism, not watched.
"""

from __future__ import annotations


class AnimError(Exception):
    pass


#: (swap id, package, plain offset, stock bytes, new bytes). Generated
#: from the verified spec; every row was read back off the pristine
#: packages before it was written here.
WRITES = (
    ( 1, "COMMON   ", 0x4BD2D9, "5002", "4b04"),
    ( 1, "COMMON   ", 0x4BD2ED, "4b04", "5002"),
    ( 1, "COMMONOFF", 0x4BB2CB, "5002", "4b04"),
    ( 1, "COMMONOFF", 0x4BB2DF, "4b04", "5002"),
    ( 1, "COMMON_SS", 0x4BB2CB, "5002", "4b04"),
    ( 1, "COMMON_SS", 0x4BB2DF, "4b04", "5002"),
    ( 2, "COMMON   ", 0x4BCA2A, "4203", "4a04"),
    ( 2, "COMMON   ", 0x4BCA3E, "4a04", "4203"),
    ( 2, "COMMONOFF", 0x4BAA1C, "4203", "4a04"),
    ( 2, "COMMONOFF", 0x4BAA30, "4a04", "4203"),
    ( 2, "COMMON_SS", 0x4BAA1C, "4203", "4a04"),
    ( 2, "COMMON_SS", 0x4BAA30, "4a04", "4203"),
    ( 3, "COMMON   ", 0x4BD0AE, "4f04", "6c03"),
    ( 3, "COMMON   ", 0x4BD0C2, "6c03", "4f04"),
    ( 3, "COMMONOFF", 0x4BB0A0, "4f04", "6c03"),
    ( 3, "COMMONOFF", 0x4BB0B4, "6c03", "4f04"),
    ( 3, "COMMON_SS", 0x4BB0A0, "4f04", "6c03"),
    ( 3, "COMMON_SS", 0x4BB0B4, "6c03", "4f04"),
    ( 4, "COMMON   ", 0x4BC9BA, "7602", "6b03"),
    ( 4, "COMMON   ", 0x4BC9CE, "6b03", "7602"),
    ( 4, "COMMONOFF", 0x4BA9AC, "7602", "6b03"),
    ( 4, "COMMONOFF", 0x4BA9C0, "6b03", "7602"),
    ( 4, "COMMON_SS", 0x4BA9AC, "7602", "6b03"),
    ( 4, "COMMON_SS", 0x4BA9C0, "6b03", "7602"),
    ( 5, "COMMON   ", 0x4BD0D6, "5004", "7103"),
    ( 5, "COMMON   ", 0x4BD0EA, "7103", "5004"),
    ( 5, "COMMONOFF", 0x4BB0C8, "5004", "7103"),
    ( 5, "COMMONOFF", 0x4BB0DC, "7103", "5004"),
    ( 5, "COMMON_SS", 0x4BB0C8, "5004", "7103"),
    ( 5, "COMMON_SS", 0x4BB0DC, "7103", "5004"),
    ( 6, "COMMON   ", 0x4BC9E2, "4103", "7003"),
    ( 6, "COMMON   ", 0x4BC9F6, "7003", "4103"),
    ( 6, "COMMONOFF", 0x4BA9D4, "4103", "7003"),
    ( 6, "COMMONOFF", 0x4BA9E8, "7003", "4103"),
    ( 6, "COMMON_SS", 0x4BA9D4, "4103", "7003"),
    ( 6, "COMMON_SS", 0x4BA9E8, "7003", "4103"),
    ( 7, "COMMON   ", 0x4BCBA2, "4403", "6e03"),
    ( 7, "COMMON   ", 0x4BCBB6, "6e03", "4403"),
    ( 7, "COMMONOFF", 0x4BAB94, "4403", "6e03"),
    ( 7, "COMMONOFF", 0x4BABA8, "6e03", "4403"),
    ( 7, "COMMON_SS", 0x4BAB94, "4403", "6e03"),
    ( 7, "COMMON_SS", 0x4BABA8, "6e03", "4403"),
    ( 8, "COMMON   ", 0x4BC902, "7f02", "6d03"),
    ( 8, "COMMON   ", 0x4BC916, "6d03", "7f02"),
    ( 8, "COMMONOFF", 0x4BA8F4, "7f02", "6d03"),
    ( 8, "COMMONOFF", 0x4BA908, "6d03", "7f02"),
    ( 8, "COMMON_SS", 0x4BA8F4, "7f02", "6d03"),
    ( 8, "COMMON_SS", 0x4BA908, "6d03", "7f02"),
    ( 9, "COMMON   ", 0x4BC8DA, "7503", "7c02"),
    ( 9, "COMMON   ", 0x4BC8EE, "7c02", "7503"),
    ( 9, "COMMONOFF", 0x4BA8CC, "7503", "7c02"),
    ( 9, "COMMONOFF", 0x4BA8E0, "7c02", "7503"),
    ( 9, "COMMON_SS", 0x4BA8CC, "7503", "7c02"),
    ( 9, "COMMON_SS", 0x4BA8E0, "7c02", "7503"),
    (10, "COMMON   ", 0x4BC89E, "7403", "7a02"),
    (10, "COMMON   ", 0x4BC8B2, "7a02", "7403"),
    (10, "COMMONOFF", 0x4BA890, "7403", "7a02"),
    (10, "COMMONOFF", 0x4BA8A4, "7a02", "7403"),
    (10, "COMMON_SS", 0x4BA890, "7403", "7a02"),
    (10, "COMMON_SS", 0x4BA8A4, "7a02", "7403"),
    (11, "COMMON   ", 0x4BD1B4, "4d02", "7603"),
    (11, "COMMON   ", 0x4BD1C8, "7603", "4d02"),
    (11, "COMMONOFF", 0x4BB1A6, "4d02", "7603"),
    (11, "COMMONOFF", 0x4BB1BA, "7603", "4d02"),
    (11, "COMMON_SS", 0x4BB1A6, "4d02", "7603"),
    (11, "COMMON_SS", 0x4BB1BA, "7603", "4d02"),
    (13, "COMMON   ", 0x4BD992, "4801", "4603"),
    (13, "COMMON   ", 0x4BD9A6, "4603", "4801"),
    (13, "COMMONOFF", 0x4BB984, "4801", "4603"),
    (13, "COMMONOFF", 0x4BB998, "4603", "4801"),
    (13, "COMMON_SS", 0x4BB984, "4801", "4603"),
    (13, "COMMON_SS", 0x4BB998, "4603", "4801"),
    (14, "COMMON   ", 0x4BD9BA, "4901", "4703"),
    (14, "COMMON   ", 0x4BD9CE, "4703", "4901"),
    (14, "COMMONOFF", 0x4BB9AC, "4901", "4703"),
    (14, "COMMONOFF", 0x4BB9C0, "4703", "4901"),
    (14, "COMMON_SS", 0x4BB9AC, "4901", "4703"),
    (14, "COMMON_SS", 0x4BB9C0, "4703", "4901"),
    (15, "COMMON   ", 0x4BD8E1, "7802", "7902"),
    (15, "COMMON   ", 0x4BD933, "7902", "7802"),
    (15, "COMMONOFF", 0x4BB8D3, "7802", "7902"),
    (15, "COMMONOFF", 0x4BB925, "7902", "7802"),
    (15, "COMMON_SS", 0x4BB8D3, "7802", "7902"),
    (15, "COMMON_SS", 0x4BB925, "7902", "7802"),
    (16, "COMMON   ", 0x4BCEF6, "4e04", "6501"),
    (16, "COMMON   ", 0x4BCF82, "6501", "4e04"),
    (16, "COMMONOFF", 0x4BAEE8, "4e04", "6501"),
    (16, "COMMONOFF", 0x4BAF74, "6501", "4e04"),
    (16, "COMMON_SS", 0x4BAEE8, "4e04", "6501"),
    (16, "COMMON_SS", 0x4BAF74, "6501", "4e04"),
    (17, "COMMON   ", 0x4BD351, "4504", "4503"),
    (17, "COMMON   ", 0x4BD365, "4503", "4504"),
    (17, "COMMONOFF", 0x4BB343, "4504", "4503"),
    (17, "COMMONOFF", 0x4BB357, "4503", "4504"),
    (17, "COMMON_SS", 0x4BB343, "4504", "4503"),
    (17, "COMMON_SS", 0x4BB357, "4503", "4504"),
)

#: swap id -> (risk, the clip that plays today, the cut clip, what it does)
SWAPS = {
     1: ("MEDIUM", "StandLockPick_b", "StandLockPick_c",
         "Standing lock-pick plays the authored start-of-pick motion instead of looping the hold pose."),
     2: ("MEDIUM", "CrouchLockPick_b", "CrouchLockPick_c",
         "Crouched lock-pick plays the authored start-of-pick motion instead of looping the hold pose."),
     3: ("MEDIUM", "StandKeyPad_b", "StandKeyPad_c",
         "Standing keypad use plays the authored reach-to-keypad motion instead of looping the hold pose."),
     4: ("MEDIUM", "CrouchKeyPad_b", "CrouchKeyPad_c",
         "Crouched keypad use plays the authored reach-to-keypad motion instead of looping the hold pose."),
     5: ("MEDIUM", "StandKeyboard_b", "StandKeyboard_c",
         "Standing keyboard use plays the authored reach-to-keyboard motion instead of looping the hold pose."),
     6: ("MEDIUM", "CrouchKeyboard_b", "CrouchKeyboard_c",
         "Crouched keyboard use plays the authored reach-to-keyboard motion instead of looping the hold pose."),
     7: ("MEDIUM", "CrouchPlaceBug_b", "CrouchPlaceBug_c",
         "Planting a bug plays the authored place motion instead of looping the hold pose."),
     8: ("MEDIUM", "CrouchDisarmBomb_b", "CrouchDisarmBomb_c",
         "Disarming a bomb plays the authored reach-in motion instead of looping the hold pose."),
     9: ("HIGH", "CrouchClaymoreFire", "CrouchClaymore",
         "Setting a claymore plays the commit motion instead of the looping placing pose."),
    10: ("HIGH", "CrouchC4Fire", "CrouchC4",
         "Setting C4 plays the commit motion instead of the looping placing pose."),
    11: ("LOW", "StandLadderSlide_Stop", "StandLadderSlide_e",
         "Leaving a ladder plays the slide-to-stop motion instead of the stock dismount."),
    13: ("LOW", "StandTurnLeft180", "StandTurnLeft",
         "A left turn plays the 180-degree about-face instead of the short turn."),
    14: ("LOW", "StandTurnRight180", "StandTurnRight",
         "A right turn plays the 180-degree about-face instead of the short turn."),
    15: ("LOW", "StandTacReloadLMG", "StandTacReloadSubGun",
         "A tactical reload plays the LMG reload instead of the sub-gun reload."),
    16: ("MEDIUM", "StandFireAndPumpShotGun", "StandFireShotGun",
         "Third-person shotgun fire plays the fire-and-pump motion instead of fire alone."),
    17: ("SAFE", "StandOnFire02", "StandOnFire01",
         "A burning character plays the second burn variation instead of the first."),
}


#: which risk bands each level turns on
LEVELS = {
    "stock": (),
    "safe": ("SAFE", "LOW"),
    "interactive": ("SAFE", "LOW", "MEDIUM"),
    "everything": ("SAFE", "LOW", "MEDIUM", "HIGH"),
}
DEFAULT = "stock"

#: all three COMMON packages carry RainbowAnim
SELECT = r"/COMMON(OFF|_SS)?\.LIN$"


def chosen(level=DEFAULT):
    """The swap ids a level turns on."""
    want = LEVELS.get(level, ())
    return tuple(i for i in sorted(SWAPS) if SWAPS[i][0] in want)


def writes_for(package, level=DEFAULT):
    """[(offset, stock, new)] for one package, as bytes."""
    ids = set(chosen(level))
    name = package.strip().upper()
    return [(off, bytes.fromhex(s), bytes.fromhex(n))
            for i, pkg, off, s, n in WRITES
            if i in ids and pkg.strip().upper() == name]


def apply(plain, package, level=DEFAULT):
    """Returns (bytes, changed). Refuses rather than writing a wrong offset."""
    todo = writes_for(package, level)
    if not todo:
        return plain, 0
    out, n = bytearray(plain), 0
    for off, stock, new in todo:
        here = bytes(out[off:off + len(stock)])
        if here == new:
            continue                        # already applied
        if here != stock:
            raise AnimError("%s +0x%06X holds %s, not the stock %s"
                            % (package, off, here.hex(), stock.hex()))
        out[off:off + len(new)] = new
        n += 1
    if len(out) != len(plain):
        raise AnimError("an animation swap changed the file length")
    return bytes(out), n


def apply_auto(plain, level=DEFAULT):
    """`apply` without being told which package this is.

    The data-edit dispatch hands an op the bytes and nothing else, so the
    package is identified by its own content: try each offset set and keep the
    one whose every stock byte is already in place. COMMONOFF and COMMON_SS
    are byte-identical so they share a set, and COMMON's offsets are 0x200E
    higher -- the two cannot both match, because a wrong set lands inside
    unrelated records.
    """
    if not chosen(level):
        return plain, 0
    for name in ("COMMON", "COMMONOFF", "COMMON_SS"):
        todo = writes_for(name, level)
        if not todo:
            continue
        if all(bytes(plain[o:o + len(s)]) in (s, n) for o, s, n in todo):
            return apply(plain, name, level)
    raise AnimError("this is not a COMMON package these swaps were measured "
                    "on: no offset set matches its stock bytes")


def selftest(packages):
    """`{name: plain bytes}` -> [] when every stock byte is where it should be."""
    bad = []
    for i, pkg, off, s, n in WRITES:
        plain = packages.get(pkg.strip().upper())
        if plain is None:
            continue
        stock = bytes.fromhex(s)
        if bytes(plain[off:off + len(stock)]) != stock:
            bad.append("%s +0x%06X" % (pkg.strip(), off))
        if len(s) != len(n):
            bad.append("%s +0x%06X changes length" % (pkg.strip(), off))
    return bad


def card(prefix, group):
    from .model import CHOICE, Choice, Setting

    return Setting(
        prefix + "anim_restore", "Animations that were never bound", CHOICE,
        DEFAULT, group, confidence="experimental", touches="data",
        choices=[
            Choice("stock", "None", "As it ships."),
            Choice("safe", "The low-risk ones",
                   "Both 180-degree turns, the ladder dismount, the LMG's "
                   "tactical reload and a second burning variation."),
            Choice("interactive", "...and the interactive ones",
                   "Lock-picking, keypads, keyboards, planting a bug and "
                   "disarming a bomb each play the authored reach-in motion "
                   "instead of repeating the hold pose, and the shotgun "
                   "pumps in third person."),
            Choice("everything", "...and the plant commits",
                   "Setting a claymore or a remote charge plays its commit "
                   "motion. Read the caution first -- those two hold their "
                   "last frame afterwards."),
        ],
        help="Sixteen animations in the Rainbow set are complete, shipped and "
             "bound to nothing at all. No script, no overlay and no property "
             "names them, in any of the 132 package tables on the disc.\n\n"
             "They are largely one omission repeated: every interactive "
             "action has a start-of-motion segment the game never plays, so "
             "your operative snaps to the hold pose instead of reaching for "
             "the lock. The claymore and the remote charge never play their "
             "commit beat at all.\n\n"
             "Each is restored by exchanging two bytes between the clip the "
             "game plays and the clip it does not, so nothing is added and "
             "no file grows.",
        caution="Not yet confirmed in play.\n\n"
                "The first two levels cannot leave a character stuck: those "
                "clips are played on a loop and the action's length is the "
                "game's own timer, so a shorter clip simply cycles faster. "
                "The standing lock-pick is the most noticeable -- a 0.6 "
                "second reach loops where a 3 second hold used to.\n\n"
                "\"The plant commits\" is different, and is why it is last. "
                "Those two play once and are about a second shorter than "
                "what they replace, so the operative finishes the motion and "
                "then holds his last pose for the rest of the plant. Expect "
                "to see that, and judge whether it reads better than the "
                "placing pose looping.")

"""The M16 fires at 70% volume and the M4 carries half the audible range.

Both are shipped defects in the third-person sound banks, and both are single
outliers against the other twenty-five weapons on the disc.

THE M16
-------

`ASSAULT_M16A2.SB1` gives its full-auto loop (`Play_M16A2_AutoShots`) and its
tail (`Play_M16A2_EndShots`) an event volume of **0.7071** where every other
third-person weapon event on the disc is **1.000**.

Measured across the 27 third-person weapon banks, exactly two carry 0.7071:
this one, and `SNIPER_AWCOVERT` -- the covert sniper, where a quiet report is
the point of the weapon. Nineteen of the 27 **first-person** banks carry it,
because 0.7071 is 1/sqrt(2), the standard power-sum compensation for playing a
two-channel asset. It does not belong on a mono third-person bank.

The practical result is an enemy M16 that is ~3 dB down on every other rifle,
which against the trigger click -- audible to 15 m, where the fire event is at
full volume out to 10 m -- reads as a gun that clicks and never fires.

THE M4
------

`ASSAULT_M4CARB.SB1` gives all three of its fire events a distance triple of
**3.5 / 4.0 / 60.0** metres where every other third-person weapon on the disc
is **10.0 / 10.5 / 70.0**. Rolloff therefore begins 6.5 m early and the sound
is cut off 10 m short. Its own `_1ST` twin carries the normal numbers, so this
is not a deliberate choice about the weapon.

It is the only third-person weapon bank on the disc containing either 3.5 or
60.0 as a distance.

WHAT THE EDIT DOES
------------------

Rewrites those values to the figures every other weapon already uses. The
fields are 16.16 fixed point, four bytes each, edited in place -- so every
bank keeps its length, its header, its event count and its payload offsets.

    M16A2   0.7071 -> 1.000     x2   (the auto loop and its tail)
    M4CARB  3.5    -> 10.0      x3
            4.0    -> 10.5      x3
            60.0   -> 70.0      x3

Each site is found by a byte window that is unique -- or, for the M4, that
occurs exactly three times and should be changed at all three. Nothing here
uses a stored offset.

WHAT THIS IS NOT
----------------

It is **not** the AI-gunshot fix that `rsesoundgate` claimed to be, and it
does not share that module's mistake. `rsesoundgate` was withdrawn because
its premise -- that some weapons have no third-person fire sample -- is false.
This module changes no sample and no property assignment: it corrects two
numbers in the game's own event tables, and it applies to the player's weapon
and the enemy's alike.

NOT ESTABLISHED
---------------

* Never played. The values are read out of the shipped banks and compared
  against the other twenty-five; the audible result is not observed.
* The M16A2 loop is also the only rifle loop on the disc sampled at 16000 Hz
  rather than 22050. That is left alone deliberately -- the rate is what the
  waveform was recorded at, so changing it would transpose the pitch rather
  than improve the quality.
* `SNIPER_AWCOVERT`'s single 0.7071 is left alone: it is a suppressed weapon
  and a quiet report may well be intended.
"""

from __future__ import annotations

H = bytes.fromhex


class GunAudioError(Exception):
    pass


#: The archive members this touches. Both live beside the other weapon banks.
SELECT = r"/SOUNDS/NONSTRM/ASSAULT_(M16A2|M4CARB)\.SB1$"

#: (name, stock window, patched window, how many times it must occur).
#:
#: M16A2: the volume word sits eight bytes into each window; the bytes either
#: side are there only to make the window unique, and the two differ in their
#: first byte (event 7 against event 8).
#:
#: M4CARB: one sixteen-byte window carries the whole distance triple --
#: min, a -1 sentinel, mid, max -- and occurs once per fire event, three
#: times in the file. All three are meant to change.
SITES = (
    ("m16a2_end_shots",
     H("05000000ae07000002b500000000000000000000"),
     H("05000000ae07000000000100" + "0000000000000000"), 1),
    ("m16a2_auto_shots",
     H("0a000000ae07000002b500000000000000000000"),
     H("0a000000ae07000000000100" + "0000000000000000"), 1),
    ("m4carb_distances",
     H("00800300ffffffff0000040000003c00"),
     H("00000a00ffffffff00800a0000004600"), 3),
)

#: Where they sit in a pristine bank, for the tests only -- the edit
#: itself never uses an offset.
KNOWN_OFFSETS = {"m16a2_end_shots": (0x006C,),
                 "m16a2_auto_shots": (0x00B4,),
                 "m4carb_distances": (0x0038, 0x0080, 0x00C8)}

for _n, _a, _b, _c in SITES:
    if len(_a) != len(_b) or _a == _b:
        raise GunAudioError("bad window pair for %s" % _n)
del _n, _a, _b, _c


def reads(plain: bytes) -> bool:
    """True if nothing this module knows about is left to correct.

    Note what this does NOT try to do: tell an already-corrected bank
    apart from one that was always right. It cannot, and neither can
    anything else -- the values written here are the values every healthy
    weapon bank already carries, so `ASSAULT_AK47` and a patched
    `ASSAULT_M16A2` look identical by content. An earlier draft guessed
    the bank from those values and cheerfully identified the AK47 as an
    M16. `SELECT` is what constrains this to the two banks that need it."""
    return all(plain.count(stock) == 0 for _, stock, _, _ in SITES)


def apply(plain: bytes, enable: bool = True):
    """Correct whatever stock values are present. Returns (plain, changed).

    A file with none of them is left exactly as it is rather than refused:
    that is what an already-correct bank looks like, and it is not an
    error. The length never moves."""
    if not enable:
        return plain, 0
    out, changed = plain, 0
    for name, stock, new, want in SITES:
        n = out.count(stock)
        if not n:
            continue
        if n != want:
            raise GunAudioError("%s: found %d windows, expected %d"
                                % (name, n, want))
        out = out.replace(stock, new)
        changed += n
    if len(out) != len(plain):
        raise GunAudioError("length moved")
    return out, changed


#: There is deliberately NO revert() here, and the reason is worth
#: keeping: a draft had one, and it would have corrupted the file it was
#: handed. The values this module writes are the values every healthy
#: bank already carries, so a content-matching revert cannot tell its own
#: work from the game's. Concretely, `ASSAULT_M16A2` contains the normal
#: 10.0/10.5/70.0 distance triple three times of its own accord -- so a
#: revert keyed on that triple would have rewritten the M16's healthy
#: distances into the M4's broken ones.
#:
#: Switching the option off restores the shipped bank from the backup
#: store, which is how every data edit in this tool is undone. Nothing
#: needs a module-side revert, and this one cannot have a safe one.


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "gun_audio_fix", "Fix the M16 and M4 gunshots", BOOL,
        False, group, confidence="measured", touches="data",
        help="Enemies carrying an M16 sound like they are dry-firing -- you "
             "get the trigger and no shot. The M4 goes quiet far sooner than "
             "any other weapon.\n\n"
             "Both are mistakes in the game's own sound tables. The M16's "
             "firing sound is set to about 70 per cent volume where every "
             "other weapon on the disc is at full, and the M4's is told to "
             "fade out from 3.5 metres and stop being audible at 60, where "
             "everything else fades from 10 and carries to 70.\n\n"
             "This sets both to the numbers the other twenty-five weapons "
             "already use. It changes no recordings -- only two numbers "
             "each -- and it applies to your own weapon as well as theirs.",
        caution="Not yet played.\n\n"
                "This is a different thing from the withdrawn option about "
                "teammates and first-person gunshots, and it does not share "
                "that one's mistake: no sample is swapped and nothing is "
                "given a sound it did not already have.")

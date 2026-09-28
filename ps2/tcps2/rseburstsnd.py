"""Three-round burst has no gunshot sound. One word puts it back.

THE DEFECT
----------

`R6SoundReplicationInfo::PlayWeaponSound`'s worker dispatches eleven weapon
sound events through a jump table at `0x005E4DD0`. Entry 5,
`WSOUND_PlayFireThreeBurst`, lands at `0x003C5410` and plays three things in
order: `m_TriggerSnd` (repinfo+0x380), then **`m_BurstFireStereoSnd`**
(repinfo+0x3B0), then `m_ShellBurstFireSnd` (repinfo+0x420, and only for a
real local player).

`m_BurstFireStereoSnd` is `None` on **all thirty** weapon classes -- sixteen
read off live class-default objects in the EE dumps, fourteen off the CDOs in
the `.LIN` packages, zero mismatches on the overlap. The asset does not exist
either: the PC build ships `Play_<Gun>_TripleShots` and assigns it, and the
string `TripleShots` occurs **zero** times in all three PS2 script packages
and in the live name table.

`DareAudioSubsystem::PlaySound` returns silently on a NULL `USound*`
(`0x004766A4` / `0x004766C8`). So a weapon in three-round burst plays the
trigger click and the brass, and no gunshot at all -- which reads as a dry
mechanical click, exactly like firing on empty.

WHAT THE EDIT DOES
------------------

Repoints the burst handler's property load from `m_BurstFireStereoSnd` to
`m_SingleFireStereoSnd`, which is assigned on all thirty weapons.

It is one word, and the proof that it is the right word is that the
single-shot handler is already byte-identical apart from it::

    0x003C52F0  02A0282D  move  $a1, $s5          ; single shot
    0x003C52F4  24070002  addiu $a3, $zero, 2
    0x003C52F8  24420390  addiu $v0, $v0, 0x390    <- m_SingleFireStereoSnd
    0x003C52FC  00531021  addu  $v0, $v0, $s3
    0x003C5300  8F39009C  lw    $t9, 0x9c($t9)     ; PlaySound

    0x003C5450  02A0282D  move  $a1, $s5          ; three-round burst
    0x003C5454  24070002  addiu $a3, $zero, 2
    0x003C5458  244203B0  addiu $v0, $v0, 0x3B0    <- m_BurstFireStereoSnd
    0x003C545C  00511021  addu  $v0, $v0, $s1
    0x003C5460  8F39009C  lw    $t9, 0x9c($t9)     ; PlaySound

Both index by `4 * m_CurrentWeapon` -- `$s3` in one, `$s1` in the other -- and
both hand slot 2 to the same vtable call. Only the property offset differs.

`addiu` is not a branch, and neither neighbour is, so there is no delay slot
to preserve and nothing is displaced. `$v0` is the `m_PawnRepInfo` loaded at
`0x003C5444` and `$s1` is `4 * m_CurrentWeapon` set at `0x003C541C`; the edit
moves only the immediate, so both keep their meaning.

It also costs nothing in SPU2: `m_SingleFireStereoSnd`'s bank is already
registered for every weapon, because it is the sample the single-shot case has
always played.

WHO THIS IS FOR: THE PLAYER, NOT THE AI
---------------------------------------

Worth stating plainly, because it is easy to assume otherwise. **The AI never
reach this handler.** `m_eRateOfFire` reads 2 (`ROF_FullAuto`) on every AI
weapon instance in every EE dump, `GetNbOfRoundsForROF()` returns the whole
magazine for full auto, and `ROF_ThreeRound` has no class default of 1 and no
setter anywhere in the console build. Confirmed in play: teammates do not fire
controlled bursts.

So this fixes the PLAYER's gun going quiet after pressing the rate-of-fire
button (`B` in `PSX2GAME.INI`), and it is unrelated to the separate defect
where AI teammates are silent with certain weapons -- that one is the
first-person sound assignment gate, and `rsesoundgate` covers it.

NOT ESTABLISHED
---------------

* Never played. The stock word and the single-shot comparison are read out of
  the pristine overlay; the audible result is not observed.
* `MP.SOZ` carries unrelated code at this address and is not patched. Every
  address in this project is an `SP.SOZ` virtual address.
* A richer alternative exists and is not taken: repointing the jump-table
  entry at `0x005E4DE4` from `0x003C5410` to `0x003C52B0` would give burst the
  single-shot handler entire, gaining the echo layer but trading away the
  burst-specific brass. One word either way; this one is the smaller change.
"""

from __future__ import annotations


class BurstSoundError(Exception):
    pass


#: The property load inside `WSOUND_PlayFireThreeBurst`'s handler.
#: `addiu $v0, $v0, 0x3B0` -> `addiu $v0, $v0, 0x390`.
BURST_SND_AT = 0x003C5458
BURST_SND_STOCK = 0x244203B0        # + m_BurstFireStereoSnd   (None on all 30)
BURST_SND_NEW = 0x24420390          # + m_SingleFireStereoSnd  (assigned on all 30)

#: The single-shot handler's equivalent word, which the new value is copied
#: from. Never written -- kept so the module can assert the shape it relies on.
SINGLE_SND_AT = 0x003C52F8
SINGLE_SND_WORD = 0x24420390


def words(enable: bool = True):
    """[(va, new, stock)] for the edit."""
    return [(BURST_SND_AT, BURST_SND_NEW, BURST_SND_STOCK)] if enable else []


def stock_words():
    """{va: stock} for the word this module touches."""
    return {BURST_SND_AT: BURST_SND_STOCK}


def reads(word_at) -> bool:
    """True if `word_at(va)` shows the edit in place."""
    return word_at(BURST_SND_AT) == BURST_SND_NEW


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "burst_fire_sound", "Three-round burst has a gunshot", BOOL,
        False, group, confidence="experimental", touches="code",
        pnach_only=True,
        help="Switch your weapon to three-round burst and it goes quiet -- "
             "you get the trigger click and the brass, and no shot. It sounds "
             "exactly like firing on empty.\\n\\n"
             "The sound burst mode asks for was never finished. It is unset on "
             "all thirty weapons and the recording is not on the disc at all; "
             "the PC version has it and the PlayStation 2 build does not. This "
             "points burst at the single-shot gunshot instead, which every "
             "weapon does have.\\n\\n"
             "This is for YOUR gun. Teammates never use burst -- they are "
             "always on full automatic -- so it will not change how they "
             "sound. That is a separate fault with its own option.",
        caution="Not yet played.\\n\\n"
                "Burst will sound like single shots fired quickly, because "
                "that is literally the sample it now uses. It is the same "
                "gunshot your weapon already makes on semi-automatic, so it "
                "will not sound wrong -- just not distinct from semi.")

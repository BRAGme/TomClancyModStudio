"""How often an AI teammate draws his sidearm instead of reloading.

The question this answers
------------------------

Stock, Price / Weber / Loiselle only ever reach for the pistol when the rifle is
completely spent. They never do the thing a real operator does -- run a magazine
dry mid-firefight and transition to the sidearm rather than reload.

Where the decision lives
------------------------

**It is UnrealScript, not native code**, so there is no word in `SP.SOZ` to
patch. That was established from the live `UFunction` layout rather than guessed:
`+0x78` holds the C++ entry point, and 3,699 of the 4,357 loaded UFunctions
carry `0x0014f200` there, which is `UObject::ProcessInternal` -- the script VM.
`R6Rainbow` has no native functions at all.

`R6RainbowAI.RainbowReloadWeapon`, decoded::

    if (m_pawn.m_bWeaponIsSecured)            return;
    if (m_bWeaponsDry)                        return;
    if (m_pawn.m_bReloadingWeapon)            return;

    if (Pawn.EngineWeapon.m_iCurrentNbOfClips > 0) {      <-- THE GATE
        ... stop firing, face front, ReloadWeapon()
    }
    else if (m_pawn.m_iCurrentWeapon == 0
             && Pawn.m_WeaponsCarried[1].HasAmmo()) {
        SwitchWeapon(1);                                  <-- rifle -> pistol
    }
    else if (m_pawn.m_iCurrentWeapon == 1
             && Pawn.m_WeaponsCarried[0].HasAmmo()) {
        SwitchWeapon(0);
    }
    else if (!m_bWeaponsDry) {
        m_bWeaponsDry = true;
        PlaySoundCurrentAction(12);                       <-- "Weapon's dry"
    }

By the time this runs the empty magazine is already the trigger --
`NeedToReload()` returns true on `m_iNbBulletsInWeapon == 0`, and `AttackTimer`
only calls it then -- so the gate is the whole decision. This module adds a roll
to it::

    if (clips > 0 && Rand(100) < 100 - chance) { ...reload... }

so `chance` percent of dry magazines fall through to the sidearm branch instead.
0 leaves the disc alone. The rifle keeps its magazines, so the teammate can come
back to it when the pistol empties, which is the third arm above.

Why the branch is dead on a stock disc
--------------------------------------

`R6Weapons.PostBeginPlay` gives every weapon an AI Rainbow carries
`m_bUnlimitedClip = true; m_iCurrentNbOfClips = 1` whenever
`m_bUnlimitedRainbowMagazines` is set, and
`R6Weapons::execNativeServerFireBullet` (VA 0x003f0a40) then takes its
`unlimited && clips == 1` path forever, never reaching `clips--`. So the clip
count is pinned at 1 for the whole mission and the gate is always true --
**the switch branch cannot be reached at all**. Turning the ammunition switch
off is a prerequisite, which is why this option requires it.

How the edit is made
--------------------

Not with a hex editor. Inserting bytecode moves every downstream jump, and a
script block's jump operands are offsets into the LOADED image, which is longer
than the file -- see `tcps2/uscode.py`, which does the parsing, re-measuring and
re-basing. The disk length is held fixed by reclaiming the dead
`if (bShowLog) Log(" needs to reload weapon")` pair -- `bShowLog` reads False on
all three live teammate AIs, so it is unreachable code -- and padding whatever
is left over with `EX_Nothing` after the final return.
"""

from __future__ import annotations

import struct

from . import uscode
from .uscode import END, Script, Tok, ScriptError, parse_expr

#: The one string in the package that is unique to this function and that this
#: module never touches, so the block can be located before AND after its own
#: edit. Exactly one occurrence in each COMMON container.
SIGNATURE = b"  BOTH WEAPONS ARE DRY?????!!!!! \x00"

#: The dead log lines whose bytes pay for the inserted code. `bShowLog` reads
#: False on all three live teammate AIs, so every `Log()` in this function is
#: unreachable. The `"  BOTH WEAPONS ARE DRY?????!!!!! "` one is deliberately
#: NOT in this list: it is the signature the block is found by.
DEAD_LOG = b" needs to reload weapon\x00"
DEAD_LOG_SECONDARY = b" needs to switch to secondary weapon\x00"

#: Native indices, read out of the game's own UFunction table rather than
#: remembered: 130 AndAnd_BoolBool, 132 OrOr_BoolBool, 114
#: EqualEqual_ObjectObject, 150 Less_IntInt, 167 Rand. All are above 0x70, so
#: each is a single opcode byte.
#:
#: The two boolean operators short-circuit, and the shipped code says how that
#: is spelled: every one of the package's 877 `OrOr_BoolBool` has an `EX_Skip`
#: as its second argument, and so does every `AndAnd_BoolBool`. The object
#: comparison's shape is taken the same way -- `(InstanceVariable, NoObject)` is
#: the most common of its 208 instances.
EX_AND_AND = 0x82
EX_OR_OR = 0x84
EX_EQ_OBJECT = 0x72
EX_NE_OBJECT = 0x77
EX_LESS_INT = 0x96
EX_RAND = 0xA7
EX_SKIP = 0x18
EX_INSTANCE_VAR = 0x01
EX_NO_OBJECT = 0x2A
EX_INT_CONST_BYTE = 0x2C
EX_END_PARMS = 0x16

#: Above this the teammates would almost never reload, and a pair of weapons
#: that both still report ammunition but never get loaded makes the AI swap back
#: and forth without firing. 90 still leaves one reload in ten.
MAX_CHANCE = 90


class SidearmError(Exception):
    pass


def find_block(plain: bytes) -> int:
    """Offset of the ScriptSize word of `R6RainbowAI.RainbowReloadWeapon`.

    Found by content, because a cooked package's export offsets do not point at
    anything (see `docs/PATCHES.md`). The signature string is located first,
    then the enclosing script block is the one whose declared length parses
    cleanly and whose extent covers it.
    """
    at = plain.find(SIGNATURE)
    if at < 0:
        raise SidearmError("the teammate reload function is not in this file")
    if plain.find(SIGNATURE, at + 1) >= 0:
        raise SidearmError("the teammate reload function appears more than "
                           "once; refusing to guess which one to change")
    found = []
    for size_at in range(at - 4, max(0, at - 3000), -1):
        n = struct.unpack_from("<I", plain, size_at)[0]
        if not (16 <= n <= 20000):
            continue
        try:
            script = Script.at(plain, size_at)
        except Exception:
            continue
        if size_at + 4 <= at < size_at + 4 + script.disk_len:
            found.append(size_at)
    if not found:
        raise SidearmError("found the function's text but no script block "
                           "around it")
    if len(found) > 1:
        raise SidearmError("more than one script block covers the signature")
    return found[0]


def _gate(script):
    """The `if (clips > 0)` statement, by shape rather than by offset."""
    for tok in script.toks:
        if tok.name != "JumpIfNot":
            continue
        cond = tok.parts[1][1]
        # stock: Greater_IntInt(clips, 0). Already edited: AndAnd(that, roll).
        if cond.op == 0x97:
            return tok
        if cond.op == EX_AND_AND:
            kids = cond.parts[0][1]
            if kids and kids[0].op == 0x97:
                return tok
    raise SidearmError("the clip-count gate is not in this function")


def _dead_log(script, text=None):
    """The `if (bShowLog) Log(...)` pair carrying `text`, as a pair."""
    text = DEAD_LOG if text is None else text
    for i, tok in enumerate(script.toks):
        for t in tok.walk():
            for kind, val in t.parts:
                if kind == "str" and val == text:
                    if i == 0:
                        raise SidearmError("the dead log has no guard")
                    guard = script.toks[i - 1]
                    if guard.name != "JumpIfNot":
                        raise SidearmError("the dead log's guard is a %s, not "
                                           "a JumpIfNot" % guard.name)
                    return guard, tok
    raise SidearmError("the reload branch's log line is not in this function")


def _enemy_ref(script):
    """The compact reference to `Controller.Enemy`, taken from this function.

    The function already tests `Enemy != None` to decide whether to break off
    an attack before reloading, so the reference is lifted from there rather
    than resolved through the package's import table or hardcoded. That keeps it
    correct on any disc revision whose tables number things differently -- the
    index always comes from the file being edited.
    """
    for tok in script.statements():
        if tok.op != EX_NE_OBJECT:
            continue
        args = tok.parts[0][1]
        if (len(args) == 2 and args[0].op == EX_INSTANCE_VAR
                and args[1].op == EX_NO_OBJECT):
            return args[0].parts[0][1]
    raise SidearmError("this function does not test Enemy against None, so "
                       "there is no reference to borrow")


def _skip(body):
    """`body` wrapped in the EX_Skip that a short-circuit operand needs."""
    return bytes([EX_SKIP]) + struct.pack("<H", len(body) + 1) + body


def _roll(chance, enemy_ref=None):
    """The condition to AND onto the reload gate.

    Without `enemy_ref`:  Rand(100) < 100 - chance
    With it:              Enemy == None || Rand(100) < 100 - chance

    so that a teammate with nobody shooting at him always reloads, and the roll
    only happens while he is actually in contact.
    """
    body = bytes([EX_LESS_INT,
                  EX_RAND, EX_INT_CONST_BYTE, 100, EX_END_PARMS,
                  EX_INT_CONST_BYTE, 100 - chance,
                  EX_END_PARMS])
    if enemy_ref is not None:
        body = (bytes([EX_OR_OR,
                       EX_EQ_OBJECT, EX_INSTANCE_VAR]) + enemy_ref
                + bytes([EX_NO_OBJECT, EX_END_PARMS])
                + _skip(body)
                + bytes([EX_END_PARMS]))
    tok = parse_expr(_skip(body))
    # Drop the authored skip words so the assembler measures them instead: a
    # value this module computed could be wrong in exactly the way that is
    # hardest to notice, and `uscode` already has to get this right for the
    # whole package.
    for t in tok.walk():
        if t.op == EX_SKIP:
            t.skip_base = None
    return tok


#: `PlaySoundCurrentAction`'s argument for the ammunition line. The dry branch
#: calls it with 12, and that is the ONLY call with 12 anywhere in the loaded
#: script, so it is what reaches `m_sndAmmoOut`.
AMMO_VOICE = 12

EX_JUMP_IF_NOT = 0x07
EX_VIRTUAL_FUNCTION = 0x1B
EX_BYTE_CONST = 0x24


def _voice_call(script):
    """The shipped `PlaySoundCurrentAction(12)` statement, to copy from.

    Its function name is a reference, and like `Enemy` it is lifted from the
    disc being edited rather than resolved or hardcoded.
    """
    for tok in script.statements():
        if tok.op != EX_VIRTUAL_FUNCTION:
            continue
        args = tok.parts[1][1]
        if (len(args) == 1 and args[0].op == EX_BYTE_CONST
                and args[0].parts[0][1][0] == AMMO_VOICE):
            return tok.parts[0][1]
    raise SidearmError("this function does not play the ammunition line, so "
                       "there is no call to copy")


def _say_dry(script, chance):
    """Insert `if (Rand(100) < chance) PlaySoundCurrentAction(12);` at the end
    of the reload branch.

    The branch ends with the `Jump` that skips the `else if` arms, and that
    jump is found structurally: the reload gate's own target is the first
    `else if`, so the statement in front of it is the jump that closes the
    branch. The new test jumps to that same statement when the roll fails, so a
    quiet reload simply falls through it.
    """
    ref = _voice_call(script)
    gate = _gate(script)
    after = gate.parts[0][1]
    if after is END:
        raise SidearmError("the reload gate jumps to the end of the function")
    i = script.toks.index(after)
    if i == 0 or script.toks[i - 1].name != "Jump":
        raise SidearmError("the reload branch does not end in a jump")
    closing = script.toks[i - 1]

    roll = parse_expr(bytes([EX_LESS_INT,
                             EX_RAND, EX_INT_CONST_BYTE, 100, EX_END_PARMS,
                             EX_INT_CONST_BYTE, chance,
                             EX_END_PARMS]))
    test = Tok(EX_JUMP_IF_NOT)
    test.parts = [("jump", closing), ("expr", roll)]

    say = Tok(EX_VIRTUAL_FUNCTION)
    say.parts = [("ref", ref),
                 ("exprs", [parse_expr(bytes([EX_BYTE_CONST, AMMO_VOICE]))])]

    script.toks[i - 1:i - 1] = [test, say]


def apply(plain: bytes, chance: int, in_contact: bool = True,
          say_chance: int = 0):
    """Give the reload gate a `chance` percent miss. Returns (plain, changed).

    `in_contact` restricts the roll to teammates who currently have an enemy,
    so one with nobody shooting at him always reloads.

    The file length never changes. The block's in-memory length does, and the
    `ScriptSize` word in front of it is updated to match.
    """
    chance, say_chance = int(chance), int(say_chance)
    if chance == 0 and say_chance == 0:
        return plain, 0
    if chance and not 1 <= chance <= MAX_CHANCE:
        raise SidearmError("chance must be between 1 and %d" % MAX_CHANCE)
    if not 0 <= say_chance <= 100:
        raise SidearmError("say_chance must be between 0 and 100")
    size_at = find_block(plain)
    script = Script.at(plain, size_at)
    gate = _gate(script)
    if gate.parts[1][1].op != 0x97:
        raise SidearmError("the gate is not the comparison this expects")
    enemy = _enemy_ref(script) if (chance and in_contact) else None

    # Each insertion is paid for out of its own dead log line, so turning one
    # option on does not quietly spend the other's budget.
    doomed = list(_dead_log(script))
    if say_chance:
        doomed += list(_dead_log(script, DEAD_LOG_SECONDARY))
    script.remove(doomed)

    if say_chance:
        _say_dry(script, say_chance)
    if chance:
        wrapped = Tok(EX_AND_AND)
        wrapped.parts = [("exprs", [gate.parts[1][1], _roll(chance, enemy)])]
        gate.parts[1] = ("expr", wrapped)

    out = bytearray(plain)
    script.write_into(out, size_at)
    if len(out) != len(plain):
        raise SidearmError("the sidearm edit changed the file length")
    # Read it back through the same parser, from the bytes actually written.
    Script.at(bytes(out), size_at)
    return bytes(out), 1


def reads(plain: bytes):
    """What this file currently encodes: (chance, inContact).

    (0, False) means stock. Both shapes are understood, because the contact
    test is optional and a disc may carry either.
    """
    try:
        script = Script.at(plain, find_block(plain))
        gate = _gate(script)
    except Exception:
        return 0, False
    cond = gate.parts[1][1]
    if cond.op != EX_AND_AND:
        return 0, False
    kids = cond.parts[0][1]
    if len(kids) != 2 or kids[1].op != EX_SKIP:
        return 0, False
    inner = kids[1].parts[1][1]
    contact = False
    if inner.op == EX_OR_OR:
        arms = inner.parts[0][1]
        if len(arms) != 2 or arms[0].op != EX_EQ_OBJECT or arms[1].op != EX_SKIP:
            return 0, False
        contact = True
        inner = arms[1].parts[1][1]
    if inner.op != EX_LESS_INT:
        return 0, False
    args = inner.parts[0][1]
    if len(args) != 2 or args[1].op != EX_INT_CONST_BYTE:
        return 0, False
    return 100 - args[1].parts[0][1][0], contact


def cards(prefix, group):
    """The three options this module offers."""
    from .model import BOOL, INT, Setting

    return [card(prefix, group), Setting(
        prefix + "ai_say_dry", "Chance of calling out a reload", INT, 0, group,
        minimum=0, maximum=100, unit="%", confidence="untested",
        touches="data",
        help="**There is no reloading line in this game.** All three "
             "operatives have 101 voice events each and exactly one is about "
             "ammunition; the only reload sounds on the disc are a shotgun and "
             "a grenade launcher. So this does the nearest honest thing: it "
             "plays the ammunition line -- \"No ammo, sir\" / \"Weapon's dry\" "
             "-- when a teammate reloads, this often.\n\n"
             "It is the game's own call, `PlaySoundCurrentAction(12)`, copied "
             "from the branch that fires when both weapons are spent and "
             "inserted into the reload branch behind a roll. Nothing else "
             "changes: `m_bWeaponsDry` is not set, so it is purely something "
             "you hear.",
        caution="Not play-tested, and one thing is genuinely unknown. The "
                "ammunition event resolves to \"No ammo, sir\", but the only "
                "other event that reaches an ammunition take is a 50/50 "
                "against \"Roger, I'm on it\" -- and which of the two "
                "`m_sndAmmoOut` is could not be pinned down. If you hear "
                "\"Roger, I'm on it\" on a reload, that is which one it is.\n\n"
                "This one needs no other setting: it works on a stock disc, "
                "where teammates reload constantly, so start low. 15-25% is "
                "about one call-out every few magazines."), Setting(
        prefix + "ai_sidearm_contact", "...only when they are in contact",
        BOOL, True, group, confidence="untested", touches="data",
        help="With this on, the roll only happens to a teammate who currently "
             "has an enemy -- one with nobody shooting at him always reloads, "
             "which is what he should do. The test is the game's own: this "
             "function already checks `Enemy != None` to decide whether to "
             "break off an attack before reloading, and the reference is "
             "lifted from there rather than hardcoded.\n\n"
             "Turn it off and they will transition to the sidearm on any dry "
             "magazine, in a firefight or not.",
        requires={prefix + "ai_sidearm": list(range(1, MAX_CHANCE + 1))})]


def card(prefix, group):
    """The percentage dial."""
    from .model import INT, Setting

    return Setting(
        prefix + "ai_sidearm", "Chance of drawing the pistol instead of "
        "reloading", INT, 0, group, minimum=0, maximum=MAX_CHANCE, unit="%",
        confidence="untested", touches="data",
        help="Stock, Price, Weber and Loiselle reach for the sidearm only when "
             "the rifle is completely spent -- they never transition mid-fight "
             "the way the animation and the loadout plainly expect. The "
             "decision is one test in `R6RainbowAI.RainbowReloadWeapon`, which "
             "reloads whenever any magazine remains and only falls through to "
             "`SwitchWeapon(1)` when none does.\n\n"
             "This adds a roll to that test, so this percentage of dry "
             "magazines end with the pistol coming out instead. The rifle keeps "
             "its magazines, so they come back to it when the pistol runs out. "
             "0% is the game exactly as it shipped.",
        caution="Not play-tested. This one rewrites script bytecode rather "
                "than flipping a byte -- the roll is inserted, every jump in "
                "the function is re-based around it, and the space is paid for "
                "by deleting a debug log line that cannot run. The result is "
                "read back through the same parser before it is written. It is "
                "capped at %d%% because a teammate who never reloads would "
                "swap between two weapons that both still report ammunition."
                % MAX_CHANCE,
        # The clip count is pinned at 1 for the whole mission while magazines
        # are unlimited, so the branch this reaches is unreachable without it.
        requires={prefix + "ai_finite_ammo": [True]})

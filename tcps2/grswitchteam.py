r"""SELECT cycles to the next teammate, instead of looking at one to take him.

Jungle Storm hands control of a squad member over only if you put him under
your crosshair and press SELECT. The quick-select handler (msg 0x241, handler
0x002823C0) asks `IkeSimulationMgr` vtable +0xA4 who the HUD is naming at
0x002824EC, and `beqz s3` four instructions later walks away when the answer is
nobody. There is no iteration anywhere in it: the candidate is whatever the
crosshair happens to hit, which is the whole complaint.

THE CYCLE IS ALREADY ON THE DISC
--------------------------------

Red Storm shipped it and Jungle Storm left it unreachable. Two messages, two
complete handlers, both registered:

    msg 0x21  FollowNextTeamMember  handler 0x003744D0  action-map key 0xC3
    msg 0x22  FollowLastTeamMember  handler 0x00374AF0  action-map key 0x67

`HandleFollowNextTeamMember` is the finished article: payload read, then
`CheckForRespawn` (0x00375070), then the split-screen return at 0x003745DC,
then `FindNextTeamMember` (0x003746F0) twice -- first within the fireteam
(`a2=1` at 0x00374658), then across fireteams (`a2=0` at 0x0037469C) -- and
finally `SwitchFollowActor`, vtable +0x158, the same slot quick-select calls.

The one thing missing is a button. **No Jungle Storm pad button produces
keycode 0xC3, 0x67 or 0xBE.** On Ghost Recon those are d-pad left and right;
Jungle Storm gave both d-pad sides to peek (keycodes 0x56 / 0x58) and never
rehoused the switch actions. Both games' action-map records, RSInput pushes and
flags for 0x21/0x22 are byte-identical, so this code is proven in a retail
title -- it is reachable on one disc and orphaned on the other.

WHAT THIS CHANGES
-----------------

Three `li` immediates. No cave, no displaced instruction, no opcode or register
field touched -- only the 16-bit immediate of three `addiu $r, $zero, imm`.

    0x0013FA64  li a1, 0xC3 -> 0x70    msg 0x21  (next) moves onto SELECT
    0x0013FA84  li a1, 0x70 -> 0xC3    msg 0x241 (quick-select) moves off it
    0x0019B38C  li t0, -1   -> 0x67    L3 stops being unassigned: msg 0x22

`a1` is the key field of the `(msg, key, alt)` record: the thunk at 0x00140000
does `a3 = a2; a2 = -1` and the binder at 0x001D28A0 stores `{a3, a1, a2}`,
which the lookup at 0x001D29E0 reads back as `{msg, key, alt}`.

The second word is what makes this airtight rather than order-dependent.
`RSInput::MapKey` (0x0019B6F0) keeps ONE binding per keycode in a flat array at
`this + key*12 + 0x100` and the last writer wins; msg 0x21 is pushed at
0x00141614, after msg 0x241 at 0x001414EC, so the first word alone would also
land SELECT on the cycle. Moving quick-select off 0x70 as well means the result
does not depend on that ordering.

WHAT IT COSTS
-------------

Look-at-and-confirm goes away: after the swap, msg 0x241 sits on a keycode no
button produces, so both its handlers (0x002823C0 and 0x00347DB0) are dead
code. Nothing in the image sends 0x241 from code -- the only other occurrences
of that immediate are the registration and unregistration pair at 0x00281548
and 0x0035AF74 -- so nothing else notices. To keep it instead of "previous
teammate", give L3 keycode 0xC3 rather than 0x67 and quick-select moves to L3.

The Options controller diagram still captions SELECT the old way. Jungle
Storm's caption table was not located (`grcontrols` names only Ghost Recon's,
at 0x00581670 / 0x005816F0), so nothing here tries to relabel it.

THE EDGE CASES ARE THE STOCK CODE'S, AND IT ALREADY HANDLES THEM
----------------------------------------------------------------

Pressing it while dead is the DESIGNED case, not an edge: the game itself
sends msg 0x21 on death from `SimHuman::UpdateAutoResPawn`. The handler calls
`CheckForRespawn` first and returns at 0x003745BC without switching when a
respawn is pending. With one squad member alive `FindNextTeamMember` fails both
passes and `bne a0, 1, 0x3746d0` takes a plain return, dereferencing nothing.
In split screen the handler returns at 0x003745DC. Cutscenes, briefings and
online share the same top-level gate (state manager vtable +0x9C) that
quick-select is already behind at 0x002823FC, so any mode where SELECT does
nothing today refuses the cycle too. START is a different layer entirely
(keycode 0x47 -> msg 0x237 -> 0x00207090) and is untouched.

Flags 0x0180 carry neither the 0x8000 nor the 0x4200 bit the input update
tests at 0x0019A548 / 0x0019A574, so this is the fire-once path rather than
auto-repeat -- and Ghost Recon ships msg 0x21 with those same flags on a d-pad
direction, which settles it.

Player 2 is unaffected: pad 2's keycodes are pad 1's plus 0xC5 (0x0019B46C),
and pad 2's SELECT (0x135) is unbound on a stock disc either way.
"""

from __future__ import annotations

#: (VA, stock word, patched word, what it does)
#:
#: Each is `addiu $r, $zero, imm` -- `li` -- so only the low half-word moves.
JS_HOOKS = (
    (0x0013FA64, 0x240500C3, 0x24050070,
     "next teammate (msg 0x21) moves onto SELECT"),
    (0x0013FA84, 0x24050070, 0x240500C3,
     "look-at quick-select (msg 0x241) moves off SELECT"),
    (0x0019B38C, 0x2408FFFF, 0x24080067,
     "L3 becomes previous teammate (msg 0x22)"),
)

#: the alternative third word: L3 carries look-at quick-select instead of
#: "previous teammate", keeping the stock behaviour on a different button
JS_KEEP_QUICKSELECT = 0x240800C3


def edits(keep_quickselect: bool = False):
    """(va, value, stock, note) for each word this option writes."""
    out = []
    for va, stock, new, what in JS_HOOKS:
        if va == 0x0019B38C and keep_quickselect:
            new = JS_KEEP_QUICKSELECT
            what = "L3 becomes look-at quick-select (msg 0x241)"
        out.append((va, new, stock, "switch teammate: " + what))
    return out


def js_edits(v: dict):
    if not v.get("js_switch_teammate"):
        return []
    return edits(bool(v.get("js_switch_keep_quickselect")))


def selftest(js_elf: bytes):
    """Every stock word against the executable. [] = pass."""
    bad = []
    for va, stock, _new, _what in JS_HOOKS:
        off = va - 0x100000 + 0x100
        if int.from_bytes(js_elf[off:off + 4], "little") != stock:
            bad.append("js %08X" % va)
    e = edits()
    if len({va for va, *_ in e}) != len(e):
        bad.append("duplicate VA")
    # every word must stay an `addiu $r, $zero, imm`: opcode and registers fixed
    for va, new, stock, _n in e:
        if (new & 0xFFFF0000) != (stock & 0xFFFF0000):
            bad.append("%08X changes more than the immediate" % va)
    return bad

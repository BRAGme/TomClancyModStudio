"""A hostage who acknowledges "follow me" plays nothing a third of the time.

What the game does now
----------------------

Hostage speech on the PS2 build is not a bank of its own. The fifteen
`X_Voices_Hostage*` packages the build manifest lists have no `.SB1` between
them; their cues were folded into the per-map localised-speech banks, as a
rigid seven-slot template of positional cues carrying event ids
{1, 6, 3, 4, 5, 10, 12}. Slot 3 -- event id 3, `m_sndRnbFollow` -- is the
acknowledgement a hostage gives when the player orders him to follow.

In ten of the fifteen hostage sets that event resolves to a **weighted random
container one of whose legs is a kind-15 NULL row**: a resource with no audio
at all. The roll therefore lands on "no sound" a measured fraction of the
time::

    nine sets   3 legs, weights 0x5556 / 0x5555 / 0x5555   -> silent 1 in 3
    Penthouse   2 legs, weights 0x8001 / 0x7fff            -> silent 1 in 2

This is the hostage line a player triggers most often, on every rescue, in
every one of those missions. Nothing else in the template is affected: in all
seven carrier files event 3 is the **only** event whose container has a NULL
leg (measured -- see "What was checked" below).

What this does
--------------

It re-points the NULL leg at the sibling take that sits beside it in the same
container. Four bytes per set -- one `u32` resource row index inside one
12-byte child record -- and nothing else. A three-leg container becomes a
three-way roll over two real takes, one of which comes up twice as often; the
two-leg Penthouse container becomes that one take, every time.

**No weight is touched**, and the measurements below say that is the right
call for a sharper reason than caution.

The runtime picker was read out of the EE image (`/SP.SOZ`, decompressed, based
at 0x00100000; the picker is at 0x004d24f0). It rolls against the **literal
constant 0x10000** -- `lui a0,0x0001` -- and walks the 12-byte child records
subtractively, taking the weight from each record's `+4`. Nothing anywhere in
the image ever sums the weights. So the weights are **ABSOLUTE**, not
normalised: a container whose weights fall short of 0x10000 really can roll
past every leg and play nothing.

That would make 358 of the 2327 containers on this disc look broken -- and they
are not. Each resource record carries a per-container **silence weight** at
`+0x1c`, and:

    sum(child weights) + record[0x1c] == 0x10000     for 2327 of 2327 containers

with no exceptions anywhere on the disc. Where a designer wanted a cue to
sometimes say nothing, that is the field they used. (The earlier audit's claim
that every container's weights sum to 0x10000 is wrong; the invariant it was
reaching for is this one.)

Which is what makes these ten containers stand out, and is the best evidence
that the NULL leg is a slip rather than a decision: **all ten have a silence
weight of exactly 0**. The format has a dedicated field for "sometimes say
nothing", the designers set it to zero here, and silence arrives anyway -- by a
kind-15 row sitting in the roll instead. Re-pointing that row removes the
accidental silence and leaves the authored silence mechanism untouched and
still at zero, which is what the data says was intended.

Why it costs nothing
--------------------

The take each NULL leg is re-pointed at is **already a leg of the same
container**, so it is already resident whenever that container can be rolled.
No new resource row, no new stream, no new bank, no new byte of ADPCM. The SPU2
pool measures 96.6-97.7% full in two of nine memory captures, so an edit that
added audio would be a real problem; this adds none.

Why it is length-neutral
------------------------

The edit writes four bytes over four bytes, in place, and the value written is
a **resource row index** -- not a length, not an offset, not a count. So every
field the loader uses to find anything is bit-identical to the disc:

* `nev` (u32 @0x04), `nres` (u32 @0x08) and the tail size (u32 @0x10) are not
  written, so the event table, the resource table and the tail all start and
  end exactly where they did.
* The 108-byte resource record of the container is not written at all, so its
  `nchild` and its tail offset are unchanged.
* The 12-byte child record keeps its stride and its position; only the row
  index inside it changes. Its weight word and its trailing zero are untouched.
* The appended SPU2/VAG payload is addressed as
  `28 + nev*72 + nres*108 + tailsz + 8`, all four terms unchanged, and its
  length word is not written. Every take stays byte-identical at the same
  offset.
* The row now referenced already existed and already had audio. The row that
  was referenced stays in the table, so `nres` still describes it.

File length is therefore identical by construction, not by arithmetic, and the
archive never has to relocate anything.

One consequence, stated plainly: the kind-15 row each set stops referencing
becomes unreferenced. That is not a new state for this format -- 142 of the 207
banks in `VOKES0.IMG` ship with unreachable resource rows, 334 of them kind-15
NULLs. The row itself is not removed, so nothing that indexes the table moves.

How the region is located
-------------------------

**Structurally, then sealed.** Not by searching for a byte run, and this
matters: the 36-byte child block of Mountain Highway's container is
byte-identical to Office Complex A's *and to Office Complex B's* -- and Office
Complex B's leg 0 is a healthy kind-1 stream. A module that found its region by
byte run would corrupt a working container. Penthouse's 24-byte block likewise
appears verbatim in the three `X_VOICES_*_SPU` banks.

So the walk is:

1. Parse the 28-byte header and require the file to CLOSE -- either
   `28 + nev*72 + nres*108 + tailsz == len` or that plus
   `u32 pad(=0) | u32 payload_len | payload_len bytes`. Anything else is
   refused, unparsed.
2. Read each 72-byte event row. `u16 @0x00` is the event index within its
   logical bank; `u16 @0x02` is the **logical bank id**, which is what
   identifies the hostage set and is unique to it across the whole disc.
   Event index 3 in a bank id this module knows is the only thing it acts on.
   Office Complex B's set is bank 576, which is not in `SETS`, so it is passed
   over untouched.
3. Resolve `u32 @0x08` as a row index into the resource table and require
   kind 10 (weighted random container), the shipped `nchild`, and the shipped
   tail offset.
4. Require the container's whole child block to equal the `seal` shipped for
   that bank id, in its stock form or in its already-edited form, and nothing
   else. A file that has been altered some other way is refused rather than
   patched.
5. Require the leg being re-pointed to resolve to kind 15 and the leg being
   pointed at to resolve to kind 1. Neither is assumed from the table.

TUPLE ORDER -- read this before touching `_sites`
-------------------------------------------------

A module in this project returned `(va, stock, new)` and a caller unpacked it
as `(va, new, stock)`. The stock value was written straight back: the row was
present, every self-check passed, and the feature did nothing. So both records
here are `NamedTuple`s, whose fields cannot be silently transposed, and the
order is stated once and asserted in the tests:

* ``Leg(carrier, bank, res, nchild, leg, stock_row, new_row, seal)``
* ``Site(at, stock, new, bank, state)`` -- **`stock` third-from-last, `new`
  second-from-last, in that order**. `stock` is the four bytes on the disc now;
  `new` is the four bytes this module writes.

What was checked, on the pristine disc
--------------------------------------

Read from `...(USA).iso.orig`, never the patched image:

* The three archives agree. All 31 `*_L.SB1` files are byte-identical in
  `VOKES0.IMG`, `VOKES1.IMG` and `VOKES2.IMG`, so the seven carriers have one
  set of bytes between them and the archive writer puts the same payload in all
  three.
* 16 sets carry event 3 as a container; exactly 10 have a kind-15 leg. The
  other five (Island x2, Oil Refinery, Office Complex B, Old City) have none
  and are not in `SETS`.
* In all seven carriers, event 3 is the only event whose container has a NULL
  leg. Every other slot is clean.
* No carrier has a spare take. Every resource row in all seven is reachable
  from an event or a container leg before the edit, so there is no unused
  recording to point at instead -- the sibling take is the only candidate, and
  for Penthouse that is why the result is one take rather than two.
* All seven carriers contain only kinds 1, 10 and 15, so that reachability
  walk is complete for them rather than approximate.
* Each container's tail span is disjoint from every other's, and the spans fill
  the declared tail size exactly.

Not established
---------------

* **Not played.** Nothing here has been heard in the game.
* **The slot-to-name mapping is an inference.** That event id 3 is
  `m_sndRnbFollow` comes from the PC-side cue ordering; the PS2 build strips
  every cue name, and a whole-ISO scan finds no `hostage`, `RnbFollow` or
  `WithRnb` anywhere on the disc. What is certain is that this is slot 3 of the
  seven-slot positional template in the localised-speech banks, that it is the
  only slot in it that can play silence, and that fixing it costs nothing.
  If the mapping is wrong, the line repaired is a different hostage bark in the
  same set -- not a wrong line, a wrongly-named one.
* **Old City / M07 is NOT a second bug, and this is now settled.** Its five
  containers do have single legs short of 0x10000 (`0xeadc`, `0xd422`, `0xeadc`,
  `0xe8ba`, `0xc4ec`) -- and every one of them carries the exact complement in
  its silence weight at `+0x1c`. Its hostage is *authored* to say nothing 8.3%
  of the time on one line, 23.1% on another and 17.1% on "follow me". That is a
  design decision, not a defect, so there is nothing there to repair and this
  module correctly leaves Old City and the byte-identical team-training bank
  alone.
* **What the picker does on a miss was read but is not relied on here.** It
  appears to clamp to child 0 unless child 0 is the one it must not repeat, in
  which case the cue plays nothing. None of the ten containers can miss -- they
  sum to 0x10000 with a zero silence weight -- so this edit never reaches that
  path either before or after.
"""

from __future__ import annotations

import struct
from typing import NamedTuple

H = bytes.fromhex

#: resource kinds, from the layout proof: 1 = stream, 10 = weighted random
#: container, 15 = NULL (a row with no audio)
K_STREAM, K_RANDOM, K_NULL = 1, 10, 15

#: `m_sndRnbFollow` is slot 3 of the seven-slot hostage template
FOLLOW_EVENT = 3

#: fixed strides and field offsets of the DARE .SB1 layout
HDR = 28
EV_STRIDE, RES_STRIDE, KID_STRIDE = 72, 108, 12
EV_INDEX, EV_BANK, EV_RES = 0x00, 0x02, 0x08
RES_KIND, RES_TAIL, RES_NCHILD = 0x04, 0x0c, 0x18
H_NEV, H_NRES, H_TAILSZ = 0x04, 0x08, 0x10


class FollowLegError(Exception):
    pass


class Leg(NamedTuple):
    """One set this edit repairs. Field order is the declaration order below
    and nothing here may be reordered: `stock_row` is the kind-15 NULL the
    container ships pointing at, `new_row` is the sibling take it is
    re-pointed to."""
    carrier: str        #: the file that carries it, for the report only
    bank: int           #: logical bank id -- this is what IDENTIFIES the set
    res: int            #: row index of the container itself
    nchild: int         #: how many legs it has
    leg: int            #: which leg is the NULL one
    stock_row: int      #: the row that leg points at now (kind 15)
    new_row: int        #: the row it is re-pointed at (kind 1)
    seal: bytes         #: the container's WHOLE child block, as shipped


class Site(NamedTuple):
    """One place to write. ORDER: at, stock, new, bank, state -- `stock` is
    what is on the disc, `new` is what gets written. Do not transpose."""
    at: int             #: file offset of the four bytes
    stock: bytes        #: the four bytes now
    new: bytes          #: the four bytes to write
    bank: int           #: which logical bank this is
    state: str          #: "stock" or "new"


#: The ten sets, measured off the pristine disc. Every field is derived, not
#: quoted: the container row, leg index and rows come from walking the bank,
#: and `seal` is the child block read back out of it.
#:
#: The five hostage sets that are ABSENT are absent on purpose -- their event 3
#: has no NULL leg: 566 Oil Refinery (2 legs), 567 and 575 Island (2 legs),
#: 569 Old City (1 leg), 576 Office Complex B (3 legs, all streams). 576 is the
#: one that makes a byte-run locator unsafe, because its child block is
#: identical to 565's and 568's.
SETS = (
    Leg("ALPINES_B_L.SB1", 564, 10, 3, 0, 11, 12,
        H("0b00000056550000000000000c00000055550000000000000d0000005555000000000000")),
    Leg("MOUNTAIN_HIGHWAY_B_L.SB1", 565, 8, 3, 0, 9, 10,
        H("0900000056550000000000000a00000055550000000000000b0000005555000000000000")),
    Leg("OFFICE_COMPLEX_A_L.SB1", 568, 8, 3, 0, 9, 10,
        H("0900000056550000000000000a00000055550000000000000b0000005555000000000000")),
    Leg("ALCATRAZ_B_L.SB1", 570, 25, 3, 0, 26, 27,
        H("1a00000056550000000000001b00000055550000000000001c0000005555000000000000")),
    Leg("PENTHOUSE_A_L.SB1", 571, 7, 2, 0, 8, 9,
        H("08000000018000000000000009000000ff7f000000000000")),
    Leg("MEATPACKING_A_L.SB1", 572, 7, 3, 0, 8, 9,
        H("0800000056550000000000000900000055550000000000000a0000005555000000000000")),
    Leg("ALPINES_B_L.SB1", 573, 28, 3, 0, 29, 30,
        H("1d00000056550000000000001e00000055550000000000001f0000005555000000000000")),
    Leg("MOUNTAIN_HIGHWAY_B_L.SB1", 574, 26, 3, 0, 27, 28,
        H("1b00000056550000000000001c00000055550000000000001d0000005555000000000000")),
    Leg("ALCATRAZ_B_L.SB1", 577, 7, 3, 0, 8, 9,
        H("0800000056550000000000000900000055550000000000000a0000005555000000000000")),
    Leg("MEATPACKING_B_L.SB1", 578, 9, 3, 0, 10, 11,
        H("0a00000056550000000000000b00000055550000000000000c0000005555000000000000")),
)

BY_BANK = {s.bank: s for s in SETS}

#: the seven carriers, and only those. The other 24 `*_L.SB1` banks hold no
#: set with a NULL leg, so matching them would be work with nothing to do --
#: and Office Complex B, which a byte run WOULD match, is kept out here too.
SELECT = (r"/SOUNDS/NONSTRM/INT/(ALCATRAZ_B|ALPINES_B|MEATPACKING_A"
          r"|MEATPACKING_B|MOUNTAIN_HIGHWAY_B|OFFICE_COMPLEX_A"
          r"|PENTHOUSE_A)_L\.SB1$")


class Bank:
    """Just enough of the .SB1 layout to walk to one child record.

    The layout is not assumed: `__init__` refuses any file that does not close
    on one of the two shipped forms, so a mis-sniffed or truncated file raises
    here rather than being written at a computed offset.
    """

    def __init__(self, d: bytes):
        if len(d) < HDR:
            raise FollowLegError("not a sound bank: %d bytes" % len(d))
        self.d = d
        self.nev = struct.unpack_from("<I", d, H_NEV)[0]
        self.nres = struct.unpack_from("<I", d, H_NRES)[0]
        self.tailsz = struct.unpack_from("<I", d, H_TAILSZ)[0]
        self.resbase = HDR + self.nev * EV_STRIDE
        self.tailbase = self.resbase + self.nres * RES_STRIDE
        short = self.tailbase + self.tailsz
        if short > len(d):
            raise FollowLegError(
                "sound bank does not close: nev=%d nres=%d tailsz=%d needs "
                "%d bytes, file is %d" % (self.nev, self.nres, self.tailsz,
                                          short, len(d)))
        if short == len(d):
            self.payload = 0
        else:
            if short + 8 > len(d):
                raise FollowLegError(
                    "sound bank does not close: %d trailing bytes is too few "
                    "for a payload header" % (len(d) - short))
            pad, plen = struct.unpack_from("<II", d, short)
            if pad != 0 or short + 8 + plen != len(d):
                raise FollowLegError(
                    "sound bank does not close: pad=%d payload_len=%d would "
                    "end at %d, file is %d"
                    % (pad, plen, short + 8 + plen, len(d)))
            self.payload = plen

    def event(self, i):
        o = HDR + i * EV_STRIDE
        return (struct.unpack_from("<H", self.d, o + EV_INDEX)[0],
                struct.unpack_from("<H", self.d, o + EV_BANK)[0],
                struct.unpack_from("<I", self.d, o + EV_RES)[0])

    def kind(self, row):
        if not 0 <= row < self.nres:
            return None
        return struct.unpack_from("<I", self.d,
                                  self.resbase + row * RES_STRIDE + RES_KIND)[0]

    def container(self, row):
        """(tail offset, nchild) for a kind-10 row, or None."""
        if self.kind(row) != K_RANDOM:
            return None
        o = self.resbase + row * RES_STRIDE
        return (struct.unpack_from("<I", self.d, o + RES_TAIL)[0],
                struct.unpack_from("<I", self.d, o + RES_NCHILD)[0])

    def block_at(self, tail, nchild):
        lo = self.tailbase + tail
        hi = lo + nchild * KID_STRIDE
        if hi > self.tailbase + self.tailsz:
            raise FollowLegError(
                "a container's children run past the tail: %d..%d of %d"
                % (tail, tail + nchild * KID_STRIDE, self.tailsz))
        return lo, self.d[lo:hi]


def _sites(plain: bytes):
    """Every place this edit writes, as `Site` tuples. See TUPLE ORDER.

    Raises `FollowLegError` on a file that looks like a carrier but does not
    match what was measured. Returns `[]` for a bank that simply holds none of
    the ten sets, which is how Office Complex B and the other 24 `*_L` banks
    pass through untouched.
    """
    b = Bank(plain)
    out = []
    seen = set()
    for i in range(b.nev):
        idx, bank, res = b.event(i)
        if idx != FOLLOW_EVENT or bank not in BY_BANK:
            continue
        want = BY_BANK[bank]
        if bank in seen:
            raise FollowLegError(
                "bank %d carries event %d more than once" % (bank, idx))
        seen.add(bank)
        if res != want.res:
            raise FollowLegError(
                "bank %d event %d points at row %d, not the row %d that was "
                "measured" % (bank, idx, res, want.res))
        con = b.container(res)
        if con is None:
            raise FollowLegError(
                "bank %d row %d is kind %s, not a random container"
                % (bank, res, b.kind(res)))
        tail, nchild = con
        if nchild != want.nchild:
            raise FollowLegError(
                "bank %d row %d has %d legs, not the %d that were measured"
                % (bank, res, nchild, want.nchild))
        lo, block = b.block_at(tail, nchild)
        rel = want.leg * KID_STRIDE
        stock = struct.pack("<I", want.stock_row)
        new = struct.pack("<I", want.new_row)
        done = want.seal[:rel] + new + want.seal[rel + 4:]
        if block == want.seal:
            state = "stock"
        elif block == done:
            state = "new"
        else:
            raise FollowLegError(
                "bank %d row %d: the legs are neither the shipped %s nor the "
                "edited %s but %s" % (bank, res, want.seal.hex(),
                                      done.hex(), block.hex()))
        # never taken on trust from the table: the row being left must really
        # be a NULL and the row being taken must really be a stream
        if state == "stock":
            if b.kind(want.stock_row) != K_NULL:
                raise FollowLegError(
                    "bank %d leg %d points at row %d, which is kind %s, not "
                    "the NULL this edit exists to replace"
                    % (bank, want.leg, want.stock_row, b.kind(want.stock_row)))
        if b.kind(want.new_row) != K_STREAM:
            raise FollowLegError(
                "bank %d: row %d is kind %s, not a stream, so it is not a "
                "take to point at" % (bank, want.new_row, b.kind(want.new_row)))
        out.append(Site(lo + rel, stock, new, bank, state))
    return out


def sets_in(plain: bytes):
    """Which of the ten sets this file carries -- the `Leg` records, in bank
    order. Used by the tests and the report; raises like `_sites` does."""
    return tuple(BY_BANK[s.bank] for s in _sites(plain))


def reads(plain: bytes) -> bool:
    """True when every set this file carries is already re-pointed."""
    try:
        sites = _sites(plain)
    except FollowLegError:
        return False
    return bool(sites) and all(s.state == "new" for s in sites)


def apply(plain: bytes, enable: bool = True):
    """Returns `(bytes, count)`.

    The length never moves: four bytes are written over four bytes and the
    value is a resource row index, so nothing the loader uses to find anything
    changes. See "Why it is length-neutral" above.

    With `enable` false the input is handed straight back, which is what makes
    the setting undoable -- `dataedit` re-derives `plain` from the STORED
    original, so returning it unchanged restores the shipped bytes exactly.
    """
    if not enable:
        return plain, 0
    sites = _sites(plain)
    out = bytearray(plain)
    n = 0
    for s in sites:
        if s.state != "stock":
            continue
        if bytes(out[s.at:s.at + 4]) != s.stock:
            raise FollowLegError(
                "bank %d: the four bytes at 0x%x are %s, not the %s that was "
                "measured" % (s.bank, s.at, bytes(out[s.at:s.at + 4]).hex(),
                              s.stock.hex()))
        out[s.at:s.at + 4] = s.new
        n += 1
    if len(out) != len(plain):
        raise FollowLegError("the edit changed the file length by %+d"
                             % (len(out) - len(plain)))
    return bytes(out), n


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "hostage_follow_voice",
        "Hostages always answer \"follow me\"",
        BOOL, False, group, confidence="experimental", touches="data",
        help="Order a hostage to follow you and a third of the time he says "
             "nothing at all. On the Penthouse it is every second time.\n\n"
             "That is not a missing recording. The acknowledgement is a "
             "random pick between two spoken takes and a third, empty slot "
             "that holds no audio, and the empty slot is weighted the same as "
             "the real ones. This points that slot at one of the takes beside "
             "it, so there is always something to play.\n\n"
             "It repairs ten hostage voice sets across six levels: Alpines, "
             "Mountain Highway, Office Complex, Alcatraz, Penthouse and "
             "Meatpacking. Three more -- Oil Refinery, Island and Old City -- "
             "already answer every time and are left alone, and so is the "
             "second of Office Complex's two hostages, which was built "
             "correctly while the first was not.\n\n"
             "It loads nothing new: the take it points at is already in the "
             "same group of sounds, already in memory whenever that line can "
             "play.",
        caution="Not yet played. This comes from reading the shipped sound "
                "banks, not from a session.\n\n"
                "You will hear one of the two takes more often than the "
                "other, because the empty slot's share is handed to it rather "
                "than split. On the Penthouse there is only one take, so that "
                "hostage will always answer with the same line -- which is "
                "still the intended line, where before it was silence half "
                "the time.\n\n"
                "Four bytes per hostage set -- ten sets over seven files, and "
                "in practice one byte each moves. The file length does not "
                "change and no sound data is touched, so nothing else in the "
                "bank can move.\n\n"
                "One level is deliberately left as it is. Old City's hostage "
                "also answers only some of the time, but there it is on "
                "purpose: the sound format has a field for \"sometimes say "
                "nothing\", and on Old City it is filled in. On the six levels "
                "this changes that field is set to zero -- the designers asked "
                "for no silence and got it anyway, which is the thing being "
                "corrected.")

"""Split-screen level recordings that include the AI operatives.

What a split-screen level file is
---------------------------------

A `.LIN` is not a package the engine can seek around in. It is a RECORDING
of the bytes one boot read, in the order it read them, and it is played back
the same way: every Seek under ULinkerLoad is thrown away
(`FLinFileReader::Seek` at `0x001d3ab0` logs "Can't seek compressed file").
So a boot that asks for an object the recording boot never loaded does not
fail cleanly. It reads the next recorded bytes AS that object, and from then
on every read is off by the same amount.

Split screen plays back `<MAP>_A_SS.LIN`. That recording was made on a boot
whose team code created player 2 and nothing else, so the operatives' classes
were never read and are not in the file. That is why every attempt to put AI
teammates into split screen wedged the load, whatever it patched: the team
code asks for Loiselle's class and gets whatever the recording boot read
next. Island's savestate from the jump patch still holds the engine's own
error, "BAD EXPORT INDEX 93/84", beside "SERIAL SIZE MISMATCH: GOT 66,
EXPECTED 321" -- and 321 bytes is the size of R6RainbowWeber's class.

What single player has that split screen lacks
----------------------------------------------

For each of the 22 mission maps that are not winter maps, measured
whole-file, the two recordings differ by exactly three things:

* the level name in the header, `island_aoff` against `island_a_ss` -- same
  length;
* 105 bytes only split screen reads: the class body of
  `R6PracticeModeGameForSplitScreen`, which `UGameEngine::LoadMap` loads on
  every split-screen load;
* 2,631 bytes only single player reads: Loiselle's class group (1,377) and
  then Weber's (1,254), read at the moment the team code creates them.

Trieste is the proof of the recipe
----------------------------------

Trieste is the one map on which split screen builds the AI on the retail disc
(through the rescue arm), so its split-screen recording is a split-screen boot
that DID read the operatives. Byte for byte it is the single-player recording
plus the 105-byte record and nothing else.

So the recording a split-screen boot with teammates reads is the single-player
recording with the split-screen record added -- the same transformation
Ubisoft's own pipeline produced for Trieste. `splice` builds exactly that, and
the team code in `rsesquad` is what makes the boot ask for it. They are one
change and ship together: the new recording under stock team code goes out of
step in the other direction.

How a splice is checked
-----------------------

Two independent single-insertion proofs, both made on every file:

* the result is the single-player recording, renamed, with exactly 105 bytes
  inserted in ONE place;
* the result is the stock split-screen recording with exactly 2,631 bytes
  inserted in ONE place, and those bytes are the operatives' groups --
  identified by content, since they are the same bytes on every map.

A map whose files do not satisfy both is refused, never approximated.

Winter maps
-----------

Alpine Village and Mountain Highway (A and B) read more than the two class
groups, and read one thing in a different order -- measured, and the same
bytes on all four levels:

========================  =====================================================
split screen, no AI       Price's winter camouflage (texture + palette, 66,651)
                          then R6RLoisellebodyW (texture + palette, 66,643)
single player             Loiselle's class group, her winter class and 39,976
                          bytes of the winter skeletal mesh; then
                          R6RLoisellebodyW; then Weber's class group and his
                          winter class; then Price's winter camouflage
========================  =====================================================

The mission's skin loader fetches every operative's skins whether or not the
operative is in the team. With no AI it fetches both textures there; in single
player Loiselle's arrives earlier, with her class, and only Price's is left.
A split-screen boot with AI builds the team exactly as single player does, so
it reads single player's order -- the same recipe as every other level, and
the same construction. What these four lack is a Trieste of their own: the
order is reasoned from that accounting, not observed on a split-screen boot
that made it. So the second proof is different here: the whole differing
middle of the result, and of stock split screen, must be the measured bytes
(`WINTER_MID_*`), which pins every byte the reasoning is about.

Fitting
-------

The spliced recording is 2,526 bytes longer, but the rebuilt container is
smaller than the one the disc shipped on every covered map -- zlib at level 9
beats the original packer by 4.6 to 13.9 KB -- so it is written back into its
own slot and nothing in the archive moves.
"""

from __future__ import annotations

import hashlib
import re

#: Every level recording starts with this word, then its name as an FString.
MAGIC = b"\x29\x20\xfb\x22"

#: R6PracticeModeGameForSplitScreen's class body, read only in split screen.
RECORD = 105
#: sha1 of those 105 bytes -- measured identical on all 22 maps.
RECORD_SHA1 = "9e44eea415c57ff3a488c8c6b0e80905faca2a30"

#: Loiselle's class group then Weber's, read only in single player.
OPERATIVES = 2631
#: sha1 of those bytes -- measured identical on all 22 maps, and on Trieste's
#: split-screen recording, which reads them on the retail disc.
OPERATIVES_SHA1 = "4cf4c5487b3c11a3454fda3368b7850fde446168"

#: The two groups inside those bytes, by who they are. Loiselle's class is
#: read first because single player creates her first; nothing in either
#: group refers to the other, so each reads the same bytes alone.
GROUP_BYTES = {"L": 1377, "W": 1254}
GROUP_SHA1 = {"L": "7248b412188855cc354ec0b5c401d0913bee048f",
              "W": "3aad3942450b34fbe7944dfbc08ff1aceac43249"}

#: The three levels on which `canon_team` makes player 2 someone other than
#: Price, and who -- read off each level's own INI roster (Price out; Weber
#: if he is in, else Loiselle). Player 2's class is then read at the same
#: point the operatives are, so these levels need that group in their
#: split-screen recording even with no AI teammates at all.
CANON = {"ISLAND_A": "W", "GARAGE_A": "L", "GARAGE_B": "L"}

#: The 22 levels both proofs hold on. Trieste is not here because it needs
#: nothing: its split-screen recording already reads the operatives.
MAPS = (
    "AIRPORT_A", "AIRPORT_B", "ALCATRAZ_A", "ALCATRAZ_B",
    "GARAGE_A", "GARAGE_B", "IMPORT_EXPORT_A", "IMPORT_EXPORT_B",
    "ISLAND_A", "MEATPACKING_A", "MEATPACKING_B",
    "OFFICE_COMPLEX_A", "OFFICE_COMPLEX_B",
    "OIL_REFINERY_A", "OIL_REFINERY_B", "OLDCITY_A", "OLDCITY_B",
    "PARADE_A", "PARADE_B", "PENTHOUSE_A", "SHIPYARD_A", "SHIPYARD_B",
)

#: The four winter levels -- covered by the winter proof, see above.
WINTER = ("ALPINES_A", "ALPINES_B", "MOUNTAIN_HIGHWAY_A", "MOUNTAIN_HIGHWAY_B")

#: Every level this can splice.
COVERED = MAPS + WINTER

#: What the FileEdit selects: exactly the covered levels' split-screen files.
PATTERN = r"^/(?:%s)_SS\.LIN$" % "|".join(COVERED)

#: What a winter level's single player reads beyond split screen, in bytes,
#: and the sha1 of the whole differing middle -- from the first byte the two
#: disagree on to the last -- of the result and of stock split screen.
#: Measured identical on all four winter levels.
WINTER_EXTRA = 42727
WINTER_MID_NEW_SHA1 = "a743adbb107f7cae962365ed4a18817b217e5fd8"
WINTER_MID_SS_SHA1 = "a1bc62d93d4ecf9ea2504ca5d05f80a25ce7a402"

#: Each group's first 24 bytes: present once in every recording that reads
#: the group -- single player, Trieste, a splice -- and in no other.
GROUP_HEAD = {
    "L": bytes.fromhex("03000e4d0126ffffffffffffffff0000000000a54b010000"),
    "W": bytes.fromhex("030017520121ffffffffffffffff00000000009a0000090f"),
}


class SpliceError(Exception):
    pass


def sibling(path: str) -> str:
    """The single-player recording beside a split-screen one.

    `/ISLAND_A_SS.LIN` -> `/ISLAND_AOFF.LIN`.
    """
    m = re.match(r"^(.*_[A-Z])_SS\.LIN$", path, re.I)
    if not m:
        raise SpliceError("%s is not a split-screen level recording" % path)
    return m.group(1) + "OFF.LIN"


def _name(plain: bytes):
    """(start, end) of the header's level name, NUL included."""
    if plain[:4] != MAGIC:
        raise SpliceError("not a level recording (no 0x22FB2029 header)")
    n = plain[4]
    # An FString length is a compact index; every level name is well under
    # 64 characters, which is the one-byte form. Anything else is refused
    # rather than decoded, because it would not be one of these files.
    if not 2 <= n < 0x40:
        raise SpliceError("level name length byte 0x%02x is not a short "
                          "positive compact index" % n)
    end = 5 + n
    if plain[end - 1] != 0:
        raise SpliceError("level name is not NUL terminated")
    return 5, end


def _prefix(a: bytes, b: bytes) -> int:
    """Length of the common prefix, by bisection on whole-slice compares."""
    lo, hi = 0, min(len(a), len(b))
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if a[lo:mid] == b[lo:mid]:
            lo = mid
        else:
            hi = mid - 1
    return lo


def _suffix(a: bytes, b: bytes) -> int:
    """Length of the common suffix, the same way."""
    lo, hi = 0, min(len(a), len(b))
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if a[len(a) - mid:] == b[len(b) - mid:]:
            lo = mid
        else:
            hi = mid - 1
    return lo


def _insertion(longer: bytes, shorter: bytes) -> int:
    """Where `longer` is `shorter` with ONE run inserted, or SpliceError.

    Returns the leftmost offset the run can sit at. Where a run could sit at
    more than one offset -- its first byte equals the byte after it, say --
    every choice gives the same `longer`, so leftmost loses nothing.
    """
    n = len(longer) - len(shorter)
    if n <= 0:
        raise SpliceError("nothing was inserted")
    at = _prefix(longer, shorter)
    if longer[at + n:] != shorter[at:]:
        raise SpliceError("the files differ in more than one place")
    return at


def _sha1(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()


def splice(ss: bytes, off: bytes) -> bytes:
    """The split-screen recording a boot WITH operatives reads.

    `ss` and `off` are the stock plain payloads of one map's two recordings.
    Built from the single-player one, then proved against the split-screen
    one; see the module notes.
    """
    s0, s1 = _name(ss)
    o0, o1 = _name(off)
    if (s0, s1) != (o0, o1):
        raise SpliceError("the two level names are different lengths")

    # The single-player recording under the split-screen name.
    renamed = ss[:s1] + off[o1:]
    # The first byte they disagree on is where split screen read its record.
    j = _prefix(renamed, ss)
    if j < s1:
        raise SpliceError("the headers differ past the level name")
    record = ss[j:j + RECORD]
    if _sha1(record) != RECORD_SHA1:
        raise SpliceError("the split-screen record at 0x%x is not the one "
                          "every map carries" % j)
    new = renamed[:j] + record + renamed[j:]

    # Proof 1: single player, renamed, plus exactly the record in one place.
    if len(new) - len(renamed) != RECORD or _insertion(new, renamed) != j:
        raise SpliceError("the record did not go in as a single insertion")
    # Proof 2, winter levels: the whole differing middle is the measured one.
    if len(new) - len(ss) == WINTER_EXTRA:
        top = _prefix(new, ss)
        tail = _suffix(new[top:], ss[top:])
        if (_sha1(new[top:len(new) - tail]) != WINTER_MID_NEW_SHA1
                or _sha1(ss[top:len(ss) - tail]) != WINTER_MID_SS_SHA1):
            raise SpliceError("this winter level does not differ from single "
                              "player in the measured way")
        return new
    # Proof 2: stock split screen plus exactly the operatives in one place.
    if len(new) - len(ss) != OPERATIVES:
        raise SpliceError("the recordings differ by %d bytes, not the %d the "
                          "operatives take -- a winter map, or not this disc"
                          % (len(new) - len(ss), OPERATIVES))
    k = _insertion(new, ss)
    if _sha1(new[k:k + OPERATIVES]) != OPERATIVES_SHA1:
        raise SpliceError("the %d bytes single player adds at 0x%x are not "
                          "the operatives" % (OPERATIVES, k))
    return new


def recording(ss: bytes, off: bytes, order: str = "LW") -> bytes:
    """The split-screen recording for a boot that creates `order`'s groups.

    `order` is who is created, first to last, among the ones not already
    loaded: "LW" for AI teammates (single player's own order, and exactly
    `splice`), "W" or "L" for a canon player 2 alone, "WL" for canon Weber
    followed by the AI arm. The groups are taken from the proved splice, so
    every result rests on the same two proofs.
    """
    new = splice(ss, off)
    if order == "LW":
        return new
    if len(new) - len(ss) == WINTER_EXTRA:
        raise SpliceError("only AI teammates' order is known for a winter "
                          "level; canon never changes one")
    at = _insertion(new, ss)
    seg = new[at:at + OPERATIVES]
    groups = {"L": seg[:GROUP_BYTES["L"]], "W": seg[GROUP_BYTES["L"]:]}
    for who, blob in groups.items():
        if _sha1(blob) != GROUP_SHA1[who]:
            raise SpliceError("the %s group is not the one every map carries"
                              % who)
    if not order or len(set(order)) != len(order) or set(order) - set("LW"):
        raise SpliceError("%r is not an order of the two operatives" % order)
    return ss[:at] + b"".join(groups[g] for g in order) + ss[at:]


def plan(teammates: bool, canon: bool):
    """[(selectRegex, order)] -- disjoint, so no file is spliced twice.

    With AI teammates, every covered level reads Loiselle then Weber, except
    that canon's Weber on Island is created first, as player 2. With canon
    alone, only the three levels it changes need anything.
    """
    out = []
    if teammates:
        plain_maps = [m for m in COVERED
                      if not (canon and CANON.get(m, "L") != "L")]
        out.append((r"^/(?:%s)_SS\.LIN$" % "|".join(plain_maps), "LW"))
        if canon:
            for m, who in sorted(CANON.items()):
                if who != "L":
                    out.append((r"^/%s_SS\.LIN$" % m,
                                who + ("L" if who == "W" else "W")))
    elif canon:
        for m, who in sorted(CANON.items()):
            out.append((r"^/%s_SS\.LIN$" % m, who))
    return out


def reads(plain: bytes) -> bool:
    """True if this recording reads both operatives' class groups.

    Trieste's split-screen recording does on the retail disc, every
    single-player recording does, and a spliced one does -- with the two
    groups side by side, or apart as on the winter levels.
    """
    for who, head in GROUP_HEAD.items():
        at = plain.find(head)
        if at < 0 or _sha1(plain[at:at + GROUP_BYTES[who]]) != GROUP_SHA1[who]:
            return False
    return True


def apply(ss: bytes, off: bytes, enable: bool = True, order: str = "LW"):
    """(bytes, changed). `enable=False` is the stock file, untouched.

    Switching the card off is handled by the edit store putting the shipped
    file back; nothing here has to undo a splice. A recording that already
    reads the operatives is left alone rather than spliced twice.
    """
    if not enable or reads(ss):
        return ss, 0
    return recording(ss, off, order), 1

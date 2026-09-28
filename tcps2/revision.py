"""Making a code profile work on a pressing of the disc it was not built for.

A profile pins one disc: one `pcsx2_crc`, one overlay `image_sha1`, and several
hundred virtual addresses that are only meaningful inside that exact overlay
image. Load a different pressing and the addresses are guesses. Writing a word
to a guessed address is the worst outcome this tool has -- it corrupts an
instruction with no diagnostic -- so the rule here is that a code option is
either PROVEN to have landed on the right instruction or it is switched off with
a reason. There is no middle state.

Three things make that tractable, and only the third needed building:

  1. Data edits are content-pinned. `.LIN` and `.INI` edits find their region by
     searching for unique bytes inside the decompressed packages, so they are
     already revision-agnostic and this module deliberately says nothing about
     them.

  2. Most of the cheat-file payload lives in a code cave at a FIXED RAM address
     below the overlay's load base (0x000F0000 upward on Rainbow Six 3). Nothing
     in the game reaches those addresses, so they mean the same thing on every
     pressing.

  3. What is left is the set of overlay addresses the profile writes -- the hook
     words and the direct word edits -- and the profile already enumerates every
     one of them in `stock_words`. Porting the profile is therefore exactly the
     problem of carrying that address set onto another image.

That is what this module does: it turns each address into a byte SIGNATURE taken
from the pristine image, then finds that signature in another image. A signature
that matches once gives a new address. A signature that matches zero times or
more than once gives NOTHING, and every option that depended on it is disabled
by name.

  -- why the signatures are masked --

A naive byte window fails on a rebuilt overlay for a reason worth stating: MIPS
`j` and `jal` encode an ABSOLUTE target, and `lui` carries the top half of one.
If the image was recompiled, every such field in the window changed even where
the surrounding instructions did not. So the address field of an address-bearing
instruction is wildcarded, both in the context and in the target word itself.
The mask is derived from the stored word rather than stored alongside it, since
masking never touches the opcode.

  -- why relocating the site is not always enough --

A word this tool WRITES can itself embed an overlay address. Rainbow Six 3 does
this in two ways, and they need different answers:

    j/jal into the overlay   88 of the written words. Some reach a cave the tool
                             carved inside the overlay itself (the dead scope
                             region at 0x0019AFD0-0x0019B510, and 0x005B1C20,
                             0x005BA488); others call a stock engine function
                             from a cave. Either way the target moves too, so the
                             target is relocated as well and the jump re-encoded.
                             If the target does not relocate uniquely, the option
                             is refused.

    lui of an overlay        25 of the written words, all of them the high half
    high half                of a data address. The low half lives in a
                             different instruction that the tool may not write,
                             so the full address cannot be recovered from the
                             word alone and no honest re-encoding exists. These
                             are refused outright -- see `UNRELOCATABLE_LUI`.

A branch (`beq`, `bne`, REGIMM, COP1 BC) encodes a RELATIVE offset and needs no
adjustment, but only while the branch and its destination move by the same
amount. That is checked rather than assumed: the destination is relocated too
and the two deltas must agree.
"""

from __future__ import annotations

import hashlib
import os
import struct
from dataclasses import dataclass, field

# -- how wide a window may grow before we give up on an address ------------
#
# Measured over Rainbow Six 3's 637 addresses: the median needs 3 words and 95%
# are unique inside 32. The tail is one cloned aim routine whose two copies run
# identical for 569 words and differ only in a single `jal`; its six addresses
# have to reach back 96 words to the previous function's `jr $ra`, giving the
# worst case of 99. 256 is a wide margin over that and still a kilobyte.
MAX_SIG_WORDS = 256

# -- when a relocation is too thin to believe -------------------------------
#
# Uniqueness is decided one address at a time, which is the right test for "is
# THIS the same instruction" and no test at all for "is this even the same
# program". Scribbling every seventh byte of the known overlay still left 23 of
# 637 addresses matching uniquely -- real matches, in stretches the damage
# happened to miss, but on an image no part of which should be patched. So a
# whole-image floor sits on top: locate most of the set or the disc is simply
# not this build, and every option that patches code is refused. A rebuild of
# the same game lands at or very near 100%.
MIN_LOCATED = 0.90

#: MIPS opcodes, by the field this module cares about
OP_J, OP_JAL, OP_LUI = 0x02, 0x03, 0x0F
#: `beq`/`bne`/`blez`/`bgtz` and their likely variants, plus REGIMM (0x01).
#: COP1 (0x11) is a branch only when rs == 8, handled in `classify`.
OP_BRANCH = frozenset({0x01, 0x04, 0x05, 0x06, 0x07, 0x14, 0x15, 0x16, 0x17})
OP_COP1 = 0x11

PLAIN = "plain"
JUMP_IN = "jump-overlay"        # j/jal whose target is inside the overlay
JUMP_OUT = "jump-fixed"         # j/jal into a fixed-RAM cave: does not move
LUI_ADDR = "lui-overlay"        # lui of an overlay high half: unrelocatable
BRANCH = "branch"

UNRELOCATABLE_LUI = (
    "writes `lui` with the top half of an overlay address (0x%04x0000). The "
    "bottom half is in another instruction, so the full address cannot be "
    "recovered from this word and there is no safe way to move it.")


def classify(va: int, word: int, lo: int, hi: int) -> tuple:
    """(kind, mask, target) for one instruction word.

    `mask` is the 32 bits that a signature must match on -- the address field of
    an address-bearing instruction is cleared, because that field is exactly
    what a rebuilt image changes. `target` is the absolute address the word
    refers to, or 0.

    `lo`/`hi` bound the overlay, which is what decides whether a jump leaves it.
    """
    op = (word >> 26) & 0x3F
    if op in (OP_J, OP_JAL):
        # A jump's target is formed inside the 256 MB segment of the DELAY SLOT,
        # which is the instruction after the jump.
        target = ((va + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
        inside = lo <= target < hi
        return (JUMP_IN if inside else JUMP_OUT,
                0xFC000000 if inside else 0xFFFFFFFF,
                target)
    if op == OP_LUI and (lo >> 16) <= (word & 0xFFFF) <= (hi >> 16):
        return LUI_ADDR, 0xFFFF0000, (word & 0xFFFF) << 16
    if op in OP_BRANCH or (op == OP_COP1 and ((word >> 21) & 0x1F) == 8):
        # Relative, so the encoding is unchanged by a uniform move. Kept in the
        # signature as-is: the offset is real signal about where we are.
        off = word & 0xFFFF
        if off & 0x8000:
            off -= 0x10000
        return BRANCH, 0xFFFFFFFF, va + 4 + off * 4
    return PLAIN, 0xFFFFFFFF, 0


def _mask_of(va: int, word: int, lo: int, hi: int) -> int:
    return classify(va, word, lo, hi)[1]


# ---------------------------------------------------------------------------
# signatures
# ---------------------------------------------------------------------------

@dataclass
class Signature:
    """Enough of the pristine image around one address to find it again.

    `words` is the window VERBATIM out of the pristine image, and `before` says
    how many of those words precede the address itself. The masks are not stored
    beside it because they are a function of the words -- but only of the
    UNMASKED words, which is why nothing is cleared here.

    Storing the window pre-masked was tried first and is wrong twice over. A
    `jal` with its target zeroed decodes as a jump to 0, which is outside the
    overlay, so re-deriving the mask classifies it as a fixed-RAM jump and stops
    wildcarding it; and the zeroed word is then also searched for literally, so
    89 of 501 signatures could not find themselves in the very image they were
    cut from. Both faults vanish once the window is kept as it was read and the
    mask is applied to BOTH sides of every comparison.
    """
    va: int
    stock: int
    before: int
    words: tuple = ()

    @property
    def width(self) -> int:
        return len(self.words)

    @property
    def after(self) -> int:
        return len(self.words) - self.before - 1

    def masks(self, lo: int, hi: int) -> tuple:
        """The per-word masks, derived from the words rather than stored."""
        start = self.va - 4 * self.before
        return tuple(_mask_of(start + 4 * i, w, lo, hi)
                     for i, w in enumerate(self.words))


class Image:
    """A flat overlay image addressed by virtual address.

    Holds the words once, because every signature scan walks all of them and
    unpacking 1.4 million words per address would dominate everything else.
    """

    def __init__(self, data: bytes, base_va: int):
        self.data = bytes(data)
        self.base_va = base_va
        if len(self.data) % 4:
            self.data = self.data[:len(self.data) // 4 * 4]
        self.words = struct.unpack("<%dI" % (len(self.data) // 4), self.data)

    @property
    def lo(self) -> int:
        return self.base_va

    @property
    def hi(self) -> int:
        return self.base_va + len(self.data)

    def index(self, va: int) -> int:
        return (va - self.base_va) // 4

    def va_of(self, index: int) -> int:
        return self.base_va + 4 * index

    def holds(self, va: int) -> bool:
        return self.base_va <= va <= self.hi - 4 and not (va - self.base_va) % 4

    def word(self, va: int) -> int:
        return self.words[self.index(va)]

    # -- candidate search --------------------------------------------------
    def candidates(self, word: int, mask: int) -> list:
        """Every word index whose value matches `word` under `mask`.

        This is the whole candidate set for a signature, and completely so: the
        window always contains the target word at a known index, so an
        occurrence of the window implies an occurrence of the word. Nothing else
        needs scanning.
        """
        want = word & mask
        if mask == 0xFFFFFFFF:
            # The common case by a wide margin, and `bytes.find` in C beats any
            # loop over 1.4 million words.
            out, pat, d = [], struct.pack("<I", word), self.data
            i = d.find(pat)
            while i != -1:
                if not i % 4:
                    out.append(i // 4)
                i = d.find(pat, i + 1)
            return out
        return [i for i, w in enumerate(self.words) if w & mask == want]


def build_signature(img: Image, va: int, stock: int,
                    max_words: int = MAX_SIG_WORDS) -> Signature | None:
    """The narrowest window around `va` that occurs exactly once in `img`.

    Exact, not a guess-and-grow: the candidate set is found once, each candidate
    is walked outward until it disagrees with the reference, and the answer is
    the cheapest window that disagrees with every one of them. A candidate that
    agrees for `b` words back and `a` words forward is excluded by taking more
    than `b` before it OR more than `a` after it, so for each possible `before`
    the required `after` is fixed and the minimum falls out of one pass.

    None when no window up to `max_words` is unique -- which is the answer, not
    a failure to try harder.
    """
    if not img.holds(va) or img.word(va) != stock:
        return None
    lo, hi = img.lo, img.hi
    here = img.index(va)
    n = len(img.words)
    mask0 = _mask_of(va, stock, lo, hi)

    cands = [c for c in img.candidates(stock, mask0) if c != here]
    if not cands:
        return Signature(va, stock, 0, (stock & mask0,))

    # how far each rival agrees with us, in words
    agree = []
    for c in cands:
        b = 0
        while (here - b - 1 >= 0 and c - b - 1 >= 0 and b < max_words):
            i, j = here - b - 1, c - b - 1
            m = _mask_of(img.va_of(i), img.words[i], lo, hi)
            if img.words[i] & m != img.words[j] & m:
                break
            b += 1
        a = 0
        while (here + a + 1 < n and c + a + 1 < n and a < max_words):
            i, j = here + a + 1, c + a + 1
            m = _mask_of(img.va_of(i), img.words[i], lo, hi)
            if img.words[i] & m != img.words[j] & m:
                break
            a += 1
        agree.append((b, a))

    # For a given `before`, only the rivals we have not already out-run matter.
    #
    # `max_b + 2` and not `max_b + 1`: a rival that agrees for `max_b` words
    # back is only excluded by taking MORE than that, so the useful value of
    # `before` is one past the widest agreement. Stopping a step short cost the
    # six addresses inside Rainbow Six 3's cloned aim routine, where the two
    # copies agree for 95 words back and 474 forward -- reaching 96 back ends it
    # in 97 words, while every window the short loop could reach needed 571.
    best = None
    max_b = max(b for b, _a in agree)
    for before in range(0, min(max_b + 2, here + 1, max_words)):
        live = [a for b, a in agree if b >= before]
        after = (max(live) + 1) if live else 0
        if before + 1 + after > max_words:
            continue
        if here + after >= n:
            continue
        cand = (before + after, abs(before - after), before, after)
        if best is None or cand < best:
            best = cand
    if best is None:
        return None
    _t, _bal, before, after = best
    start = here - before
    sig = Signature(va, stock, before,
                    tuple(img.words[start:start + before + 1 + after]))
    # An entirely wildcarded window would match everywhere, and there would be
    # no fully-matched run to anchor the scan on. In practice the growth above
    # pulls in a plain word long before that, but the guarantee is cheap.
    if not any(m == 0xFFFFFFFF for m in sig.masks(lo, hi)):
        return None
    return sig


def build_signatures(img: Image, stock_words: dict,
                     max_words: int = MAX_SIG_WORDS) -> tuple:
    """({va: Signature}, {va: reason}) for a whole `stock_words` table."""
    sigs, bad = {}, {}
    for va, stock in sorted(stock_words.items()):
        if not img.holds(va):
            bad[va] = "0x%08x is outside the pristine image" % va
            continue
        if img.word(va) != stock:
            bad[va] = ("0x%08x reads %08x in the pristine image, but the "
                       "profile calls the stock word %08x"
                       % (va, img.word(va), stock))
            continue
        sig = build_signature(img, va, stock, max_words)
        if sig is None:
            bad[va] = ("no window up to %d words around 0x%08x is unique in "
                       "the pristine image" % (max_words, va))
            continue
        sigs[va] = sig
    return sigs, bad


# ---------------------------------------------------------------------------
# the shipped table
# ---------------------------------------------------------------------------
#
# The table has to SHIP. A user whose only copy of the disc is the unknown
# pressing has no pristine image to cut signatures from, and they are exactly
# the user this feature is for. Building it takes a minute and a half, so it is
# generated once by `tools/make_sigtable.py` and read back here.

def pack_table(sigs: dict) -> dict:
    """{"%08x": (before, "hex words")} -- what the generator writes out."""
    return {"%08x" % va: (s.before, "".join("%08x" % w for w in s.words))
            for va, s in sorted(sigs.items())}


def load_table(table: dict, stock_words: dict) -> dict:
    """{va: Signature} from a shipped table.

    The stock word is not stored beside the signature: it is the window's own
    word at index `before`, so a table that disagreed with itself could not be
    built. `stock_words` is only consulted to notice a table that has fallen
    behind the profile.
    """
    out = {}
    for key, (before, blob) in table.items():
        va = int(key, 16)
        words = tuple(int(blob[i:i + 8], 16) for i in range(0, len(blob), 8))
        if not words or not 0 <= before < len(words):
            continue
        stock = words[before]
        want = (stock_words or {}).get(va)
        if want is not None and want != stock:
            continue                    # the profile moved on; ignore the row
        out[va] = Signature(va, stock, before, words)
    return out


# ---------------------------------------------------------------------------
# finding a signature in another image
# ---------------------------------------------------------------------------

def find_signature(img: Image, sig: Signature, limit: int = 3) -> list:
    """Every virtual address in `img` where `sig` matches, up to `limit`.

    Anchored on the widest run of fully-matched words so the hot loop is a
    `bytes.find` in C; only the survivors are checked against the mask.
    """
    lo, hi = img.lo, img.hi
    masks = sig.masks(lo, hi)
    # widest run of unmasked words, to anchor the scan
    run_at = run_len = best_at = best_len = 0
    for i, m in enumerate(masks + (0,)):
        if m == 0xFFFFFFFF:
            if not run_len:
                run_at = i
            run_len += 1
            if run_len > best_len:
                best_at, best_len = run_at, run_len
        else:
            run_len = 0
    if not best_len:
        return []
    anchor = struct.pack("<%dI" % best_len, *sig.words[best_at:best_at + best_len])
    out, d = [], img.data
    i = d.find(anchor)
    while i != -1 and len(out) < limit:
        if not i % 4:
            start = i // 4 - best_at
            if 0 <= start and start + len(sig.words) <= len(img.words):
                for k, (w, m) in enumerate(zip(sig.words, masks)):
                    # BOTH sides are masked: the stored window is verbatim, so
                    # its own address fields have to be ignored here too.
                    if img.words[start + k] & m != w & m:
                        break
                else:
                    out.append(img.va_of(start + sig.before))
        i = d.find(anchor, i + 1)
    return out


@dataclass
class Relocation:
    """Where a profile's addresses land on another image, and what did not."""
    #: old virtual address -> new virtual address
    map: dict = field(default_factory=dict)
    #: old virtual address -> why it has no mapping
    unmapped: dict = field(default_factory=dict)
    #: True when the new image IS the pristine one, bit for bit
    identical: bool = False
    #: {delta: how many addresses moved by it}
    deltas: dict = field(default_factory=dict)

    @property
    def uniform_delta(self):
        """The one delta every address moved by, or None if they disagree."""
        return next(iter(self.deltas)) if len(self.deltas) == 1 else None

    @property
    def total(self) -> int:
        return len(self.map) + len(self.unmapped)

    def shape(self) -> str:
        """One line about how the relocation looks, for the report."""
        if self.identical:
            return ("The overlay is byte-for-byte the image this profile was "
                    "built against, so no address had to move.")
        if not self.map:
            return ("Not one of the %d addresses could be located in this "
                    "overlay. Nothing that patches code can run here."
                    % self.total)
        d = self.uniform_delta
        if d is not None:
            return ("All %d located addresses moved by the same %+d bytes "
                    "(%#x), which is what a straight rebuild of the same code "
                    "looks like and is good evidence the match is real."
                    % (len(self.map), d, abs(d)))
        spread = sorted(self.deltas.items(), key=lambda kv: -kv[1])
        top = ", ".join("%+d (%d addresses)" % (k, v) for k, v in spread[:4])
        return ("The %d located addresses moved by %d different amounts -- %s. "
                "That is legitimate for a recompiled overlay, but it means the "
                "code was rearranged rather than shifted, so read the list of "
                "disabled options carefully."
                % (len(self.map), len(self.deltas), top))


def relocate(sigs: dict, img: Image, pristine_sha1: str = "",
             img_sha1: str = "") -> Relocation:
    """Carry a signature table onto `img`.

    Every mapping is verified before it is kept: the stock word has to be
    present at the new address, under the same mask the signature used. A
    signature that matches zero times or more than once is dropped with a reason
    that names the address, which is what makes a wrong write impossible rather
    than unlikely.
    """
    rel = Relocation(identical=bool(pristine_sha1) and pristine_sha1 == img_sha1)
    lo, hi = img.lo, img.hi
    for va in sorted(sigs):
        sig = sigs[va]
        hits = find_signature(img, sig)
        if not hits:
            rel.unmapped[va] = ("0x%08x: its %d-word signature is not in this "
                                "overlay" % (va, sig.width))
            continue
        if len(hits) > 1:
            rel.unmapped[va] = ("0x%08x: its %d-word signature appears %s times "
                                "in this overlay, so which one is meant cannot "
                                "be decided"
                                % (va, sig.width,
                                   "%d" % len(hits) if len(hits) < 3 else "3 or more"))
            continue
        new = hits[0]
        mask = _mask_of(new, img.word(new), lo, hi)
        if img.word(new) & mask != sig.stock & mask:
            rel.unmapped[va] = ("0x%08x: the signature matched at 0x%08x but "
                                "the word there reads %08x, not the stock %08x"
                                % (va, new, img.word(new), sig.stock))
            continue
        rel.map[va] = new
        d = new - va
        rel.deltas[d] = rel.deltas.get(d, 0) + 1
    return rel


# ---------------------------------------------------------------------------
# moving the words the tool writes
# ---------------------------------------------------------------------------

#: the `lui` partners that carry the bottom half of an address, by opcode.
#: `ori` treats its immediate as unsigned; everything else sign-extends, which
#: changes how the halves are split and so how they are put back together.
LOW_HALF_OPS = {
    0x0D: ("ori", False), 0x09: ("addiu", True), 0x23: ("lw", True),
    0x2B: ("sw", True), 0x21: ("lh", True), 0x25: ("lhu", True),
    0x20: ("lb", True), 0x24: ("lbu", True), 0x28: ("sb", True),
    0x29: ("sh", True), 0x31: ("lwc1", True), 0x39: ("swc1", True),
    0x37: ("ld", True), 0x3F: ("sd", True),
}
#: how far past a `lui` its partner is looked for. Measured: on Rainbow Six 3
#: every one of the 25 pairs is within 3 instructions.
LUI_PAIR_REACH = 8


def split_halves(addr: int, signed_low: bool) -> tuple:
    """(high 16, low 16) such that the pair rebuilds `addr`."""
    low = addr & 0xFFFF
    if signed_low and low & 0x8000:
        return ((addr >> 16) + 1) & 0xFFFF, low
    return (addr >> 16) & 0xFFFF, low


def find_low_half(va: int, word: int, words: dict) -> tuple:
    """(partner va, name, signed, full address) for a `lui`, or None.

    A cave is authored as a block, so the instruction carrying the bottom half
    of an address is almost always another word this tool writes a few slots
    later. Nothing is assumed about words the tool does NOT write: if the
    partner is not in `words`, the answer is None and the caller refuses, since
    half an address cannot be moved.
    """
    rt = (word >> 16) & 0x1F
    for k in range(1, LUI_PAIR_REACH + 1):
        nva = va + 4 * k
        if nva not in words:
            continue
        nw = words[nva]
        op = (nw >> 26) & 0x3F
        if op in LOW_HALF_OPS and ((nw >> 21) & 0x1F) == rt:
            name, signed = LOW_HALF_OPS[op]
            low = nw & 0xFFFF
            if signed and low & 0x8000:
                low -= 0x10000
            return nva, name, signed, (((word & 0xFFFF) << 16) + low) & 0xFFFFFFFF
    return None


def references(words: dict, lo: int, hi: int) -> dict:
    """{referenced va: why} for every overlay address `words` points at.

    This is the other half of the address set. `stock_words` lists every site
    the tool WRITES; this lists every site it POINTS AT, and both have to move
    together or a jump lands in the middle of an instruction. On Rainbow Six 3
    it adds 64 addresses to the 507 in the table.
    """
    out = {}
    for va in sorted(words):
        word = words[va]
        kind, _m, target = classify(va, word, lo, hi)
        if kind == JUMP_IN:
            out.setdefault(target, "the jump written at 0x%08x lands here" % va)
        elif kind == BRANCH and lo <= target < hi:
            out.setdefault(target, "the branch written at 0x%08x lands here" % va)
        elif kind == LUI_ADDR:
            pair = find_low_half(va, word, words)
            if pair and is_pointer(pair[3], lo, hi):
                out.setdefault(pair[3],
                               "the address built at 0x%08x points here" % va)
    return out


def is_pointer(value: int, lo: int, hi: int) -> bool:
    """Whether a reconstructed 32-bit value can be an overlay code/data address.

    A `lui`/`ori` pair is how MIPS loads any 32-bit constant, not just a
    pointer, and nothing in the encoding says which it is. Two cheap tests throw
    out the constants that would otherwise be relocated by mistake: the value has
    to land inside the overlay, and it has to be word-aligned. Rainbow Six 3's
    cave carries exactly one impostor, `lui/ori` of 0x0019660D -- 1664525, the
    multiplier of the engine's own random number generator -- and its odd low
    byte is what gives it away.
    """
    return lo <= value < hi and not value % 4


@dataclass
class Retarget:
    """What has to happen to one written word on the new image."""
    va: int                 # the new site
    value: int              # the new word
    kind: str = PLAIN
    reason: str = ""        # set when the word cannot be moved at all

    @property
    def ok(self) -> bool:
        return not self.reason


def _site(va: int, rel: Relocation, lo: int, hi: int):
    # A word written BELOW the overlay is a cave word in fixed RAM: the site
    # does not move, though its contents still might.
    if va < lo or va >= hi:
        return va
    return rel.map.get(va)


def retarget_all(words: dict, rel: Relocation, lo: int, hi: int) -> dict:
    """{old va: Retarget} for a whole plan's worth of words.

    Taken as a set rather than one word at a time, because a `lui` cannot be
    moved without the instruction holding the other half of its address, and
    that is a different word in the same plan.

    What happens to each kind:

      plain              nothing; only the site moves.
      j/jal to fixed RAM nothing; the cave does not move and neither does the
                         encoded target.
      j/jal into overlay re-encoded against the relocated target.
      branch             offset kept, after checking that the branch and its
                         destination moved by the same amount.
      lui + low half     both halves re-encoded against the relocated address --
                         unless the value is a constant rather than a pointer,
                         in which case both are left exactly as they are.
    """
    out = {}
    # A `lui` rewrites its PARTNER as well as itself, and the partner is a later
    # word in the same plan -- so the main loop would reach it afterwards and put
    # the original value back. Pair results are therefore held aside and applied
    # once the loop is done.
    pairs = {}
    uniform = rel.uniform_delta

    def fail(va, value, kind, reason):
        out[va] = Retarget(va, value, kind, reason=reason)

    def moved(old, new, what, va):
        """Refuse a reference whose move disagrees with everything else's."""
        if uniform is not None and new - old != uniform:
            return ("0x%08x: %s 0x%08x moved %+d while every other address "
                    "moved %+d, so the match is not trustworthy"
                    % (va, what, old, new - old, uniform))
        return ""

    for va in sorted(words):
        value = words[va]
        site = _site(va, rel, lo, hi)
        if site is None:
            fail(va, value, PLAIN,
                 rel.unmapped.get(va) or "0x%08x did not relocate" % va)
            continue
        # Classified at the OLD address, not the new one. A branch offset is
        # relative, so reading it against the relocated site would name the
        # destination's NEW address and then look that up in a table keyed by old
        # ones -- which is how 44 perfectly good branches came back "destination
        # unknown". `references` uses the old address too, so the two agree.
        kind, _mask, target = classify(va, value, lo, hi)

        if kind in (PLAIN, JUMP_OUT):
            out[va] = Retarget(site, value, kind)

        elif kind == JUMP_IN:
            new_target = rel.map.get(target)
            if new_target is None:
                fail(va, value, kind,
                     "0x%08x jumps to 0x%08x, which did not relocate"
                     % (va, target))
                continue
            why = moved(target, new_target, "its jump target", va)
            if why:
                fail(va, value, kind, why)
                continue
            if (new_target & 0xF0000000) != ((site + 4) & 0xF0000000):
                fail(va, value, kind,
                     "0x%08x jumps to 0x%08x, which is in a different 256 MB "
                     "segment on this image" % (va, new_target))
                continue
            op = (value >> 26) & 0x3F
            out[va] = Retarget(site, (op << 26) | ((new_target >> 2) & 0x03FFFFFF),
                               kind)

        elif kind == BRANCH:
            if lo <= target < hi:
                new_dest = rel.map.get(target)
                if new_dest is None:
                    fail(va, value, kind,
                         "0x%08x branches to 0x%08x, whose new position is "
                         "unknown, so the offset cannot be confirmed"
                         % (va, target))
                    continue
                if new_dest - target != site - va:
                    fail(va, value, kind,
                         "0x%08x moved %+d bytes but its branch destination "
                         "0x%08x moved %+d, so the encoded offset would be "
                         "wrong" % (va, site - va, target, new_dest - target))
                    continue
            out[va] = Retarget(site, value, kind)

        else:                                   # LUI_ADDR
            pair = find_low_half(va, value, words)
            if pair is None:
                fail(va, value, kind,
                     ("0x%08x " % va) + UNRELOCATABLE_LUI % (target >> 16))
                continue
            pva, _name, signed, addr = pair
            if not is_pointer(addr, lo, hi):
                # A constant, not an address. Nothing to move.
                out[va] = Retarget(site, value, PLAIN)
                continue
            new_addr = rel.map.get(addr)
            if new_addr is None:
                fail(va, value, kind,
                     "0x%08x builds the address 0x%08x, which did not relocate"
                     % (va, addr))
                continue
            why = moved(addr, new_addr, "the address it builds", va)
            if why:
                fail(va, value, kind, why)
                continue
            psite = _site(pva, rel, lo, hi)
            if psite is None:
                fail(va, value, kind,
                     "0x%08x builds an address with 0x%08x, which did not "
                     "relocate" % (va, pva))
                continue
            high, low = split_halves(new_addr, signed)
            pairs[va] = Retarget(site, (value & 0xFFFF0000) | high, kind)
            pairs[pva] = Retarget(psite, (words[pva] & 0xFFFF0000) | low, kind)

    out.update(pairs)
    return out


# ---------------------------------------------------------------------------
# what this disc can and cannot do
# ---------------------------------------------------------------------------

@dataclass
class Capability:
    """Which of a profile's options are usable on the disc in hand.

    Data-only options are never in `disabled`. They locate their bytes by
    searching for content inside the game's own packages rather than by address,
    which is why they port to another pressing untouched -- and why this whole
    module is only ever about the code half.
    """
    #: setting key -> why it cannot run here
    disabled: dict = field(default_factory=dict)
    #: setting keys that write code and were proved to relocate
    code_ok: list = field(default_factory=list)
    #: setting keys that write no code at all
    data_only: list = field(default_factory=list)
    relocation: object = None

    def allows(self, key) -> bool:
        return key not in self.disabled

    def why(self, key) -> str:
        return self.disabled.get(key, "")

    @property
    def any_code(self) -> bool:
        return bool(self.code_ok)

    def summary(self) -> str:
        if not self.disabled:
            return ("Every option works on this disc: all %d that patch code "
                    "relocated onto this overlay." % len(self.code_ok))
        return ("%d option%s cannot run on this pressing of the disc and %s "
                "switched off. The other %d that patch code relocated cleanly, "
                "and the %d that only edit the game's own data files are "
                "unaffected."
                % (len(self.disabled), "" if len(self.disabled) == 1 else "s",
                   "is" if len(self.disabled) == 1 else "are",
                   len(self.code_ok), len(self.data_only)))


def _asking(setting):
    """A value for one setting that is not its default."""
    if setting.kind == "bool":
        return not setting.default
    if setting.kind == "int":
        return (setting.maximum if setting.default != setting.maximum
                else setting.minimum)
    for c in setting.choices:
        if c.value != setting.default:
            return c.value
    return setting.default


def _probe(profile, setting) -> dict:
    """A values dict that makes one setting actually ask for something.

    `effective` neutralises a setting whose prerequisites are unmet, so a probe
    that leaves them alone builds no words and the option looks trivially safe.
    So every prerequisite is turned on too, and to a fixed point because
    requirements chain. The prerequisite's own addresses come along with it,
    which is right: an option cannot work on a disc where the option it depends
    on does not.
    """
    v = profile.defaults()
    v[setting.key] = _asking(setting)
    for _ in range(len(profile.settings) + 1):
        changed = False
        for s in profile.settings:
            if v.get(s.key) == s.default:
                continue
            for dep, want in (s.requires or {}).items():
                dep_s = profile.setting(dep)
                if dep_s is None:
                    continue
                need = (list(want)[0] if isinstance(want, (list, tuple, set))
                        else want)
                if v.get(dep) != need:
                    v[dep] = need
                    changed = True
        if not changed:
            break
    return v


def _words_for(profile, values) -> dict:
    """{va: word} for everything a settings dict would write, disc and cheat."""
    out = {}
    try:
        eff = profile.effective(values)
    except Exception:                                      # noqa: BLE001
        return out
    for fn in (profile.build_edits, profile.build_pnach):
        if not fn:
            continue
        try:
            for w in fn(eff):
                out[w.va] = w.value
        except Exception:                                  # noqa: BLE001
            continue
    return out


def every_word(profile) -> dict:
    """{va: word} for everything this profile can ever write.

    Swept rather than declared: each setting is probed on its own, then every
    choice and each end of every range, then the whole profile at once. Anything
    only a specific COMBINATION produces would be missed, which is why
    `capability` re-checks the words of the actual plan instead of trusting this.
    """
    out = {}
    seen = [profile.defaults()]
    for s in profile.settings:
        seen.append(_probe(profile, s))
        if s.kind == "choice":
            for c in s.choices:
                v = _probe(profile, s)
                v[s.key] = c.value
                seen.append(v)
        elif s.kind == "int":
            for iv in {s.minimum, s.maximum, (s.minimum + s.maximum) // 2}:
                v = _probe(profile, s)
                v[s.key] = iv
                seen.append(v)
    everything = profile.defaults()
    for s in profile.settings:
        everything[s.key] = _asking(s)
    seen.append(everything)
    for v in seen:
        out.update(_words_for(profile, v))
    return out


def signature_addresses(profile, img: Image) -> dict:
    """{va: stock word} for every address that needs a signature.

    Three sources, and leaving any of them out was a bug before it was a
    docstring:

      stock_words     every site whose shipped word the tool asserts. This is
                      the list a profile already keeps, and it covers the disc
                      edits completely.
      written sites   the cheat-file hooks. Those are never asserted against a
                      stock word, so 17 of Rainbow Six 3's overlay hook sites are
                      absent from `stock_words` -- and without them 16 options
                      reported "did not relocate" on an overlay that was
                      byte-identical to the one they were built for.
      references      every overlay address those words point AT: see
                      `references`.
    """
    words = every_word(profile)
    need = {}
    for va, stock in (profile.stock_words or {}).items():
        if img.holds(va):
            need[va] = stock
    for va in words:
        if img.holds(va):
            need.setdefault(va, img.word(va))
    for va in references(words, img.lo, img.hi):
        if img.holds(va):
            need.setdefault(va, img.word(va))
    return need


@dataclass
class Assessment:
    """What the overlay on the disc in hand is, relative to the profile."""
    #: the overlay hashes as the exact image the profile was built against
    known: bool = True
    sha1: str = ""
    relocation: Relocation = None
    capability: Capability = None
    #: why nothing can be patched at all, when that is the answer
    reason: str = ""

    @property
    def usable(self) -> bool:
        """Whether any option that patches code can run on this disc.

        Not "did anything relocate": a relocation can be real and still be
        refused wholesale by the MIN_LOCATED floor, and in that case there is no
        capability and nothing is allowed.
        """
        return self.known or bool(self.capability and self.capability.code_ok)

    def allows(self, key) -> bool:
        return self.known or (self.capability is not None
                              and self.capability.allows(key))

    def why(self, key) -> str:
        if self.known:
            return ""
        if self.reason:
            return self.reason
        return self.capability.why(key) if self.capability else ""

    def note(self) -> str:
        """The one line a user should read about this disc."""
        if self.known:
            return ""
        if self.reason:
            return self.reason
        return "%s %s" % (self.relocation.shape(), self.capability.summary())


def _pristine_image(iso, profile, spec, backup_dir) -> tuple:
    """(image bytes, sha1 of what is actually on the disc), pristine if we can.

    Assessing the overlay AS IT SITS is wrong the moment the tool has patched it
    once: the hash no longer matches, every signature covering a patched word
    stops matching, and a disc we had just written correctly comes back as "a
    revision I cannot place". Which is exactly what the second apply in a row
    did before this existed.

    Two recoveries, in the order they can be trusted:

      the backup     `.tcms-backup/<disc>/<overlay>.orig` is the container as it
                     was the first time this disc was opened, so it is pristine
                     by construction -- and on a pressing with no known hash it
                     is the ONLY anchor there is.
      our own words  put every word the profile owns back to its stock value and
                     hash again. This recognises a patched copy of the disc the
                     profile was built for even with no backup beside it, and it
                     is the same trick `own_crc_shift` plays on the boot CRC.
    """
    from .overlay import open_overlay
    from .soz import SozImage

    ov = open_overlay(iso, spec)
    live = bytes(ov.img.image)
    sha1 = hashlib.sha1(live).hexdigest()
    if not spec.image_sha1 or sha1 == spec.image_sha1:
        return live, sha1

    if backup_dir:
        path = os.path.join(backup_dir, "%s.orig" % spec.name)
        ent = iso.find(spec.iso_pattern)
        try:
            with open(path, "rb") as fh:
                container = fh.read()
            if ent is not None and len(container) == ent.size:
                return bytes(SozImage.unpack(container, spec.base_va).image), sha1
        except (OSError, ValueError, Exception):               # noqa: BLE001
            pass

    repaired = bytearray(live)
    for va, word in (profile.stock_words or {}).items():
        off = va - spec.base_va
        if 0 <= off <= len(repaired) - 4:
            struct.pack_into("<I", repaired, off, word)
    if hashlib.sha1(bytes(repaired)).hexdigest() == spec.image_sha1:
        return bytes(repaired), sha1
    return live, sha1


def assess(iso, profile, backup_dir=None) -> Assessment:
    """Read the disc's overlay and work out what it can still do.

    Returns `known=True` and nothing else when the overlay is the image the
    profile was built against -- the common case, and it includes a disc whose
    CRC differs only because its BOOT executable was rebuilt, and a disc this
    tool has already patched. Nothing is relocated then, because nothing moved.

    `backup_dir` is this disc's backup folder, and it matters most on a pressing
    with no known hash: see `_pristine_image`.
    """
    from .overlay import OverlayError

    if not profile.overlays:
        return Assessment()
    spec = profile.overlays[0]
    if spec.kind != "soz":
        # An uncompressed boot ELF is patched word by word against a recorded
        # original; there is no image to relocate onto and none of this applies.
        return Assessment()
    try:
        image, sha1 = _pristine_image(iso, profile, spec, backup_dir)
    except (OverlayError, Exception) as exc:                   # noqa: BLE001
        return Assessment(known=False, reason=str(exc))
    if not spec.image_sha1 or hashlib.sha1(image).hexdigest() == spec.image_sha1:
        return Assessment(known=True, sha1=sha1)

    table = getattr(profile, "sig_table", None) or {}
    if not table:
        return Assessment(
            known=False, sha1=sha1,
            reason="This pressing's %s is not the image this profile was built "
                   "against, and no relocation table ships for this game, so "
                   "nothing that patches code can run here." % spec.name)
    img = Image(image, spec.base_va)
    sigs = load_table(table, profile.stock_words)
    rel = relocate(sigs, img, spec.image_sha1, sha1)
    if rel.total and len(rel.map) < MIN_LOCATED * rel.total:
        # See MIN_LOCATED. The mappings that did survive are individually sound
        # -- each one is a unique match carrying the right word -- but a disc
        # that only answers to a fraction of the set is not a rebuild of this
        # game, and patching the fraction that happened to match is not a thing
        # anyone wants. `relocation` is kept so the panel can still show the
        # numbers; `reason` is what stops every option.
        return Assessment(
            known=False, sha1=sha1, relocation=rel,
            reason="Only %d of this game's %d code addresses could be found in "
                   "this %s. That is too few for it to be another build of the "
                   "same game, so nothing that patches code will run on it. "
                   "Options that only edit the game's own data files are "
                   "unaffected." % (len(rel.map), rel.total, spec.name))
    cap = capability(profile, rel, img.lo, img.hi)
    return Assessment(known=False, sha1=sha1, relocation=rel, capability=cap)


def relocate_words(words: list, asm: Assessment, img: Image) -> tuple:
    """(relocated words, refusals) for a list of WordEdit-shaped objects.

    Each carries `va`, `value` and `stock`; all three can change. `stock`
    especially: the shipped word at a hook site is sometimes itself a `jal`, and
    on a rebuilt image its encoded target is different, so carrying the old
    stock value across would make the engine's own pre-write assertion fail on a
    perfectly good site. The word actually present at the new address is used
    instead -- which `relocate` has already checked against the old one, under
    the mask.

    Taken as a list because a `lui` cannot move without its partner.
    """
    import dataclasses

    if asm.known:
        return list(words), []
    rel = asm.relocation
    if rel is None or asm.reason:
        return [], [asm.reason or "this overlay cannot be relocated"]
    lo, hi = img.lo, img.hi
    plans = retarget_all({w.va: w.value for w in words}, rel, lo, hi)
    out, refused = [], []
    for w in words:
        rt = plans.get(w.va)
        if rt is None:
            refused.append("0x%08x could not be placed on this overlay" % w.va)
            continue
        if not rt.ok:
            refused.append(rt.reason)
            continue
        out.append(dataclasses.replace(
            w, va=rt.va, value=rt.value,
            stock=(img.word(rt.va) if img.holds(rt.va) else w.stock)))
    return out, refused


def capability(profile, rel: Relocation, lo: int, hi: int) -> Capability:
    """Work out, option by option, what this disc can still do.

    Every option is asked to build its words, those words are put through the
    relocation, and the option is disabled if any single one of them cannot be
    placed. Derived rather than declared, so a new option is covered the day it
    is added and nobody has to remember to list its addresses here.
    """
    cap = Capability(relocation=rel)
    for s in profile.settings:
        words = _words_for(profile, _probe(profile, s))
        baseline = _words_for(profile, profile.defaults())
        mine = {va: w for va, w in words.items()
                if baseline.get(va) != w}
        if not mine:
            cap.data_only.append(s.key)
            continue
        plans = retarget_all(words, rel, lo, hi)
        bad = [plans[va].reason for va in sorted(mine)
               if va in plans and not plans[va].ok]
        bad += ["0x%08x could not be placed on this overlay" % va
                for va in sorted(mine) if va not in plans]
        if bad:
            cap.disabled[s.key] = bad[0]
        else:
            cap.code_ok.append(s.key)
    return cap

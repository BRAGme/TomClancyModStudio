"""The `[another pressing of the same disc]` section for tests/run_tests.py.

Paste `run_revisions` into tests/run_tests.py (anywhere among the other
`run_*` functions) and register it in `main()` alongside the rest:

        run_revisions(args, work)

It needs `from tcps2 import revision` and `from tcps2.games import
r6_3_slus20883_sig` at the top of the file with the other imports.
"""

import sys as _sys
import hashlib
import struct

from tcps2 import revision
from tcps2.games import r6_3_slus20883_sig as SIGTABLE
from tcps2.games.r6_3 import PROFILE, STOCK
from tcps2.soz import SozImage

# -- these two come from run_tests.py itself; re-declared here only so this
#    file is readable on its own. Delete both lines when pasting it in.
# run_tests.py runs as __main__, so `from run_tests import check` would load
# it a SECOND time with its own empty PASS/FAIL lists -- every result here
# would go into a copy nobody prints, and a FAIL would not fail the suite.
# Bind to the running instance when there is one.
_rt = _sys.modules.get("__main__")
if _rt is not None and hasattr(_rt, "check"):
    check, stock_container = _rt.check, _rt.stock_container
else:                                                    # standalone import
    from run_tests import check, stock_container          # noqa: F401


def _rebuild(img, delta, cut_va, perturb_lui=True):
    """A synthetic other pressing of the same game.

    `delta` bytes of code are inserted at `cut_va`, everything above it moves
    up, and -- the part that matters -- every `j`/`jal` whose target moved is
    RE-ENCODED, because that is what a recompile leaves behind and it is exactly
    what a plain byte signature cannot survive. `perturb_lui` also moves the
    bottom half of every address built by a `lui` pair, standing in for a data
    segment laid out differently.
    """
    lo, hi = img.lo, img.hi
    cut = (cut_va - lo) // 4
    w = list(img.words)
    out = (w[:cut] + [0] * (delta // 4) + w[cut:])[:len(w)]
    moved_from = lo + 4 * cut
    for i, x in enumerate(out):
        va = lo + 4 * i
        kind, _m, t = revision.classify(va, x, lo, hi)
        if kind == revision.JUMP_IN and t >= moved_from:
            out[i] = ((x >> 26) << 26) | (((t + delta) >> 2) & 0x03FFFFFF)
        elif kind == revision.LUI_ADDR and perturb_lui:
            out[i] = (x & 0xFFFF0000) | ((x + 0x11) & 0xFFFF)
    return revision.Image(struct.pack("<%dI" % len(out), *out), lo)


def _scribble(img, va, nwords=1, value=0xDEADBEEF):
    w = list(img.words)
    i = (va - img.lo) // 4
    for k in range(nwords):
        w[i + k] = value
    return revision.Image(struct.pack("<%dI" % len(w), *w), img.lo)


def run_revisions(args, work):
    """Carrying the profile onto a pressing of the disc it was not built for.

    A real user loaded a different pressing of Rainbow Six 3: the tool knew the
    game, said "options that patch code are unsafe here", and then wrote 68
    cheat lines anyway. Both halves of that were wrong. A different disc CRC does
    not mean the addresses moved -- the CRC is taken over the BOOT executable and
    every option here patches SP.SOZ -- and a warning is not a safeguard.

    There is no second pressing to test against, so every case below is built
    out of the known overlay: shifted, rebuilt, dented, duplicated and erased.
    What is being proved is not that relocation succeeds. It is that it either
    succeeds provably or refuses by name, and never silently writes a word to an
    address it guessed.
    """
    print("\n[another pressing of the same disc]")

    # -- the parts that need no disc ------------------------------------
    lo, hi = 0x00100000, 0x00653980
    j = 0x0C0D25B4                                  # jal 0x003496d0
    kind, mask, target = revision.classify(0x0043873C, j, lo, hi)
    check("a jal into the overlay is seen as address-bearing",
          kind == revision.JUMP_IN and target == 0x003496D0,
          "%s 0x%08x" % (kind, target))
    check("and its 26-bit target is the part a signature ignores",
          mask == 0xFC000000, "%08x" % mask)
    kind, _m, t = revision.classify(0x00223B84, 0x0803C000, lo, hi)
    check("a jal into the fixed-RAM cave is not relocatable and not relocated",
          kind == revision.JUMP_OUT and t == 0x000F0000, "%s 0x%08x" % (kind, t))
    kind, mask, _t = revision.classify(0x0019B17C, 0x3C02001A, lo, hi)
    check("a lui carrying an overlay high half is seen, and its immediate masked",
          kind == revision.LUI_ADDR and mask == 0xFFFF0000, kind)
    kind, mask, dest = revision.classify(0x0040A790, 0x10400003, lo, hi)
    check("a branch is left alone, because its offset is relative",
          kind == revision.BRANCH and mask == 0xFFFFFFFF
          and dest == 0x0040A7A0, "%s 0x%08x" % (kind, dest))

    for addr, signed in ((0x00223B8C, False), (0x0065FFF0, True),
                         (0x00108000, True), (0x001A0000, False)):
        h, l = revision.split_halves(addr, signed)
        back = (h << 16) + (l - 0x10000 if signed and l & 0x8000 else l)
        check("a lui/%s pair for 0x%08x rebuilds it exactly"
              % ("addiu" if signed else "ori", addr),
              back & 0xFFFFFFFF == addr, "%08x" % (back & 0xFFFFFFFF))

    # 1664525 is the multiplier of the engine's own RNG, loaded by lui/ori. It
    # is inside the overlay's address range and it is not an address; its odd
    # low byte is the only thing that says so.
    check("an odd constant that looks like an overlay address is not treated "
          "as one", not revision.is_pointer(0x0019660D, lo, hi))
    check("but a word-aligned address inside the overlay is",
          revision.is_pointer(0x0019660C, lo, hi))
    check("and one outside it is not", not revision.is_pointer(0x000F0000, lo, hi))

    check("the profile still knows its own disc CRC", PROFILE.knows_crc("21CC1EC3"))
    check("and accepts it in either case", PROFILE.knows_crc("21cc1ec3"))
    check("a CRC it has never been shown is not its disc",
          not PROFILE.knows_crc("29CA5FE0"))
    check("unless it is listed as another pressing of the same game",
          "29CA5FE0" in {c.upper() for c in PROFILE.also_crcs}
          or not PROFILE.knows_crc("29CA5FE0"))

    rows = revision.load_table(SIGTABLE.SIGS, STOCK)
    check("the shipped signature table loads every row it carries",
          len(rows) == len(SIGTABLE.SIGS),
          "%d of %d" % (len(rows), len(SIGTABLE.SIGS)))
    check("the table was cut from the overlay this profile declares",
          SIGTABLE.SOURCE_SHA1 == PROFILE.overlays[0].image_sha1)
    stale = dict(SIGTABLE.SIGS)
    first = sorted(stale)[0]
    before, blob = stale[first]
    # the stock word sits at index `before`, not at the start of the window
    at = before * 8
    stale[first] = (before, blob[:at] + "deadbeef" + blob[at + 8:])
    check("a row that no longer agrees with the profile's stock word is dropped "
          "rather than trusted",
          len(revision.load_table(stale, STOCK)) == len(rows) - 1)

    if not (args.soz or args.iso):
        return

    # -- everything below needs the real overlay -------------------------
    spec = PROFILE.overlays[0]
    image = bytes(SozImage.unpack(stock_container(args), spec.base_va).image)
    img = revision.Image(image, spec.base_va)
    check("the overlay under test is the pristine one",
          hashlib.sha1(image).hexdigest() == spec.image_sha1)

    need = revision.signature_addresses(PROFILE, img)
    missing = sorted(va for va in need if "%08x" % va not in SIGTABLE.SIGS)
    check("the shipped table covers every address the profile can write or "
          "point at (%d)" % len(need),
          not missing,
          "%d missing, first 0x%08x -- re-run tools/make_sigtable.py"
          % (len(missing), missing[0] if missing else 0))

    sigs = revision.load_table(SIGTABLE.SIGS, STOCK)
    rel = revision.relocate(sigs, img, spec.image_sha1, spec.image_sha1)
    check("every signature finds itself, exactly once, in its own image",
          len(rel.map) == len(sigs) and not rel.unmapped,
          "%d mapped, %d unmapped" % (len(rel.map), len(rel.unmapped)))
    check("and finds itself where it already was",
          all(k == v for k, v in rel.map.items()))
    cap = revision.capability(PROFILE, rel, img.lo, img.hi)
    check("so nothing is disabled on the disc the profile was built for",
          not cap.disabled, str(sorted(cap.disabled)[:3]))
    check("and the options that only edit game data are counted separately",
          len(cap.data_only) > 0 and len(cap.code_ok) > 0,
          "%d data, %d code" % (len(cap.data_only), len(cap.code_ok)))

    # -- a rebuilt pressing ---------------------------------------------
    for delta in (0x40, 0x1000, 0x10000):
        other = _rebuild(img, delta, 0x00101000)
        r = revision.relocate(sigs, other, spec.image_sha1, "different")
        check("a rebuild that moves the code %+d bytes relocates completely"
              % delta,
              len(r.map) == len(sigs) and not r.unmapped,
              "%d of %d" % (len(r.map), len(sigs)))
        check("and every address reports the same %+d, which is how we know it"
              % delta, r.uniform_delta == delta, str(r.deltas))

    shifted = _rebuild(img, 0x1000, 0x00101000)
    rel1k = revision.relocate(sigs, shifted, spec.image_sha1, "different")

    masked = [va for va, s in sigs.items()
              if any(m != 0xFFFFFFFF for m in s.masks(img.lo, img.hi))]

    def exact_hits(im, sig):
        pat = struct.pack("<%dI" % sig.width, *sig.words)
        n, i = 0, im.data.find(pat)
        while i != -1:
            if not i % 4:
                n += 1
            i = im.data.find(pat, i + 1)
        return n

    check("%d signatures contain an instruction whose address field had to be "
          "ignored" % len(masked), len(masked) > 0)
    check("all of them still relocate", all(va in rel1k.map for va in masked))
    check("and every one of them would be LOST without that -- which is why "
          "the mask exists",
          all(exact_hits(shifted, sigs[va]) != 1 for va in masked))

    # -- the three ways a signature must refuse ---------------------------
    widest = max(sigs.values(), key=lambda s: s.width)
    inside = widest.va - 4 * widest.before + 4 * (widest.width // 2) + 0x1000
    r = revision.relocate(sigs, _scribble(shifted, inside), spec.image_sha1, "x")
    check("one changed word inside a window loses that address",
          widest.va not in r.map)
    check("and says which address it was",
          "%08x" % widest.va in r.unmapped.get(widest.va, ""),
          r.unmapped.get(widest.va, ""))
    check("without moving anything else to a wrong place",
          all(new - old == 0x1000 for old, new in r.map.items()))

    narrow = min((s for s in sigs.values() if s.width >= 3),
                 key=lambda s: s.width)
    w = list(shifted.words)
    src = (narrow.va + 0x1000 - 4 * narrow.before - shifted.lo) // 4
    dst = (0x00101100 - shifted.lo) // 4
    w[dst:dst + narrow.width] = list(shifted.words[src:src + narrow.width])
    twice = revision.Image(struct.pack("<%dI" % len(w), *w), shifted.lo)
    r = revision.relocate(sigs, twice, spec.image_sha1, "x")
    check("a window that appears twice gives no address at all",
          narrow.va not in r.map)
    check("and says it could not decide which",
          "cannot" in r.unmapped.get(narrow.va, ""), r.unmapped.get(narrow.va, ""))

    gone = _scribble(shifted, narrow.va + 0x1000 - 4 * narrow.before,
                     narrow.width, 0xFFFFFFFF)
    r = revision.relocate(sigs, gone, spec.image_sha1, "x")
    check("a window that is not there at all gives no address either",
          narrow.va not in r.map)

    # -- moving the words the tool writes --------------------------------
    words = revision.every_word(PROFILE)
    plans = revision.retarget_all(words, rel1k, img.lo, img.hi)
    check("every word the profile can write moves onto the rebuilt overlay "
          "(%d)" % len(words),
          all(rt.ok for rt in plans.values()),
          str([rt.reason for rt in plans.values() if not rt.ok][:2]))

    jumps = [(va, plans[va]) for va, v in words.items()
             if revision.classify(va, v, img.lo, img.hi)[0] == revision.JUMP_IN]
    check("a jal into the overlay is re-encoded, not just moved (%d of them)"
          % len(jumps),
          all(revision.classify(rt.va, rt.value, img.lo, img.hi)[2]
              == revision.classify(va, words[va], img.lo, img.hi)[2] + 0x1000
              for va, rt in jumps))
    fixed = [(va, plans[va]) for va, v in words.items()
             if revision.classify(va, v, img.lo, img.hi)[0] == revision.JUMP_OUT]
    check("a jal into the fixed-RAM cave is left exactly as it was (%d)"
          % len(fixed),
          all(rt.value == words[va] for va, rt in fixed))

    bad = []
    for va, v in words.items():
        if revision.classify(va, v, img.lo, img.hi)[0] != revision.LUI_ADDR:
            continue
        pair = revision.find_low_half(va, v, words)
        if not pair or not revision.is_pointer(pair[3], img.lo, img.hi):
            continue
        want = rel1k.map.get(pair[3])
        h = plans[va].value & 0xFFFF
        l = plans[pair[0]].value & 0xFFFF
        if pair[2] and l & 0x8000:
            l -= 0x10000
        if want is not None and ((h << 16) + l) & 0xFFFFFFFF != want:
            bad.append(va)
    check("both halves of every lui/low pair are moved together",
          not bad, str(["%08x" % v for v in bad][:3]))

    moved, refused = revision.relocate_words(
        [type("W", (), {"va": 0, "value": 0, "stock": 0})],
        revision.Assessment(known=True), img)
    check("relocate_words is a no-op on the disc the profile was built for",
          len(moved) == 1 and not refused)

    # -- an image that is not this game at all ----------------------------
    junk = bytearray(image)
    for i in range(0, len(junk), 7):
        junk[i] ^= 0x5A
    j_img = revision.Image(bytes(junk), spec.base_va)
    r = revision.relocate(sigs, j_img, spec.image_sha1, "x")
    check("a corrupted image still matches a few addresses by luck",
          0 < len(r.map) < len(sigs), "%d of %d" % (len(r.map), len(sigs)))
    check("but it falls under the floor, so it is refused as a whole",
          len(r.map) < revision.MIN_LOCATED * r.total,
          "%.1f%% located" % (100.0 * len(r.map) / r.total))

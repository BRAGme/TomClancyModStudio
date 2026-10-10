"""Substitute samples inside a Red Storm `.SB` / `.SS` / `.SH` sound bank.

    .SH  u32 fileSize; u32 bankId; u32 count; u32 0
         then `count` x 40-byte entries, 10 u32:
           [0] format flags   [1] sample rate   [2] (duration)
           [3] BYTE LENGTH    [4] (constant)    [5] BYTE OFFSET
           [6] 0              [7] bank id       [8] 1.0f volume   [9] 0
         then an 8-byte tail.

A bank has TWO data files and the offsets in one `.SH` address both: `.SB`
holds the resident samples and `.SS` the streamed ones. Bit **0x00040000 of the
format word** says which -- on Jungle Storm's bank 0 the four entries with
0x0004/0x0005 in the high half tile its 81,920-byte `.SS` exactly (32768 +
3 x 16384) while the rest tile the `.SB`. Reading them as one pool makes the
offsets look like overlapping nonsense.

A length of 0xFFFFFFFF marks an entry with no data at all.
"""
import struct

SENTINEL = 0xFFFFFFFF
STREAM_BIT = 0x00040000


def pool_of(entry):
    return "ss" if entry[0] & STREAM_BIT else "sb"


def parse(sh: bytes):
    size, bank, count, _zero = struct.unpack_from("<4I", sh, 0)
    if size != len(sh):
        raise ValueError("header says %d bytes, file is %d" % (size, len(sh)))
    ents = [list(struct.unpack_from("<10I", sh, 16 + i * 40)) for i in range(count)]
    return bank, ents, sh[16 + count * 40:]


def build(bank, ents, tail, sb_len=None, ss_len=None):
    """The `.SH`, with its header size and its tail restated.

    THE TAIL IS `(sbSize, ssSize)` -- 101 of 101 tails on the Jungle Storm disc
    equal the two data files' lengths exactly. Leave it stale and the streamer
    reads the old extents: rewriting bank 0 without it put hurt voice lines
    under the main menu's navigation blips.
    """
    out = bytearray(struct.pack("<4I", 0, bank, len(ents), 0))
    for e in ents:
        out += struct.pack("<10I", *e)
    tail = bytearray(tail)
    if sb_len is not None and len(tail) >= 8:
        struct.pack_into("<2I", tail, 0, sb_len, ss_len or 0)
    out += tail
    struct.pack_into("<I", out, 0, len(out))
    return bytes(out)


def is_live(entry, lengths):
    """False for an entry with no data of its own.

    Two kinds: the 0xFFFFFFFF sentinel, and junk -- one trailing entry in
    Jungle Storm's BNK_91 reads offset 5,963,780 length 1,051,372,225 in a
    663 KB bank, the only entry on either disc that does not fit its pool.
    Both are carried through untouched.
    """
    if entry[3] == SENTINEL:
        return False
    return entry[5] + entry[3] <= lengths.get(pool_of(entry), 0)


def check_tiling(ents, lengths):
    """Each pool's live entries must tile its file from 0, no gap, no overlap."""
    for pool, size in lengths.items():
        live = sorted([e for e in ents if is_live(e, lengths) and pool_of(e) == pool],
                      key=lambda e: e[5])
        pos = 0
        for e in live:
            if e[5] != pos:
                return "%s: entry at %d, expected %d" % (pool, e[5], pos)
            pos += e[3]
        if pos != size:
            return "%s: entries cover %d bytes, the file is %d" % (pool, pos, size)
    return None


def substitute(dst, src, indices):
    """`dst` carrying `src`'s samples. dst/src are {'sh','sb','ss'}.

    `indices` is either a collection of indices that mean the same sound on
    both sides, or a {destination index: source index} map. **Across two
    different discs only the map is safe**: Jungle Storm's bank 0 and Ghost
    Recon's share not one index, so matching by position puts hurt voice lines
    under the menu blips. Build the map from the two `.IDC` name tables.

    Returns (sh, sb, ss, report); report rows are (index, old_len, new_len,
    why-it-was-refused-or-None).
    """
    pick = indices if isinstance(indices, dict) else {i: i for i in indices}
    bank, dents, dtail = parse(dst["sh"])
    _sb, sents, _st = parse(src["sh"])
    for who, d, ents in (("destination", dst, dents), ("source", src, sents)):
        bad = check_tiling(ents, {p: len(d.get(p, b"")) for p in ("sb", "ss")})
        if bad:
            raise ValueError("%s bank is not contiguous: %s" % (who, bad))

    dlen = {p: len(dst.get(p, b"")) for p in ("sb", "ss")}
    slen = {p: len(src.get(p, b"")) for p in ("sb", "ss")}
    data = {}
    for i, e in enumerate(dents):
        if is_live(e, dlen):
            data[i] = dst[pool_of(e)][e[5]:e[5] + e[3]]
    new, report = [list(e) for e in dents], []
    for i in sorted(pick):
        j = pick[i]
        if i >= len(dents) or j >= len(sents):
            report.append((i, None, None, "index %d/%d is past one of the banks" % (i, j)))
            continue
        s = sents[j]
        if not is_live(s, slen) or not is_live(dents[i], dlen):
            report.append((i, dents[i][3], None, "one side carries no data"))
            continue
        report.append((i, dents[i][3], s[3], None))
        new[i] = list(s)
        new[i][7] = bank                      # keep the destination's bank id
        data[i] = src[pool_of(s)][s[5]:s[5] + s[3]]

    # re-lay each pool in the order the destination used, and restate offsets
    out = {"sb": bytearray(), "ss": bytearray()}
    for pool in ("sb", "ss"):
        order = sorted((dents[i][5], i) for i in range(len(dents))
                       if is_live(dents[i], dlen) and pool_of(new[i]) == pool
                       and pool_of(dents[i]) == pool)
        # an entry whose pool CHANGED goes on the end of its new pool
        moved = [i for i in range(len(dents))
                 if is_live(dents[i], dlen) and pool_of(new[i]) == pool
                 and pool_of(dents[i]) != pool]
        for _old, i in order:
            new[i][5] = len(out[pool])
            out[pool] += data[i]
        for i in moved:
            new[i][5] = len(out[pool])
            out[pool] += data[i]
    sb, ss = bytes(out["sb"]), bytes(out["ss"])
    return build(bank, new, dtail, len(sb), len(ss)), sb, ss, report

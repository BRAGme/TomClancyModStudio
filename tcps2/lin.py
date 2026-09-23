"""Rainbow Six 3's `.LIN` packages: chunked zlib, and how to edit one safely.

Layout is a bare chain of chunks to EOF:

    repeat:
        u32 rawSize          (16384 for every chunk but the last)
        u32 compressedSize
        u8  blob[compressedSize]

Note the field order is (raw, compressed) -- the reverse of the Red Storm games'
container in `rselzo.py`, which is exactly the kind of detail that silently
produces garbage if you assume.

**A package CAN get longer. Measured 2026-09-18, and this corrects a rule this
module used to state as non-negotiable.** The payload is a concatenation of
about 110 cooked Unreal packages, and they sit back-to-back with a gap of
exactly zero -- no directory, no padding, no separator, and nothing anywhere
records where one ends. The loader has to be walking them, and it is: inserting
20 bytes into the middle of the gameplay package, which shifts that package's
import table, its export table and every package after it, produced a disc that
boots, loads a level and plays.

What was really being observed is two other things wearing one label. Growing a
package means REBUILDING the container, and a rebuild that re-chunks at the
wrong granularity overruns the loader's fixed 16384-byte inflate buffer, which
is what fed garbage to the VIF. The "very slow load" half was separately traced
to a file relocated to the far end of a vokes archive.

`substitute` is still the right tool for an edit that happens to fit, because
it re-deflates only the chunks that changed and leaves the container's length
alone. `rebuild` is for the rest. Note that `rebuild` usually comes out
SMALLER even when the payload grows -- deflating at level 9 beats the disc's
own packer by several KB on COMMON -- so a grown package generally still fits
the slot it shipped in.

Padding is safe because the loader inflates a stream and stops at its end;
trailing bytes inside the chunk are never looked at -- `rpg_speed` ships 163
bytes of it and works. `_deflate_exact` avoids needing it where it can, because
the disc's own packer never leaves a byte after a stream in any shipped COMMON
package, and matching that is worth a tenth of a second.
"""

from __future__ import annotations

import os
import struct
import zlib

CHUNK_RAW = 16384

#: Compression ratios `_deflate_exact` may ask zopfli for, cheapest first.
#: Only the first is reached unless a chunk is packed too tight to fit at all.
ZOPFLI_LADDER = (5, 15, 40)

#: How many bytes `_deflate_exact` may shift into a literal block while
#: hunting a length that lands on a multiple of five.
#:
#: This replaced a sweep of 56 zopfli iteration counts, which was slow AND
#: frequently could not succeed at all: zopfli's output length plateaus, so
#: consecutive counts return the SAME length and therefore the same residue.
#: Measured on COMMON.LIN, one chunk gave 7521 bytes at every count from 5 to
#: 16 -- residue 2, never 0, so no number of tries could ever have hit it.
#: Moving a byte into a literal block shifts the total by about one instead,
#: which sweeps the residues properly. The two chunks that need this in
#: COMMON.LIN land at lead 13 and lead 6, taking the repack from 5.1 seconds
#: to under half a second while still hitting the slot exactly.

ZOPFLI_LEADS = 24

#: Zopfli effort when a whole rebuilt container has to be squeezed into its
#: slot (`rebuild_exact`). Five iterations already gets about 5% over zlib's
#: best; more buys little and costs linearly.
ZOPFLI_FIT_ITERATIONS = 5


class LinError(Exception):
    pass


class LinTooBig(LinError):
    """A rebuilt container that cannot be held to its slot's size."""


#: how much unparsed tail is tolerated after the last chunk. COMMON_SS.LIN's
#: archive entry is 92 bytes longer than its actual chain -- stale slack in the
#: slot, not part of the container. It has to be carried across verbatim or the
#: entry size would move.
MAX_TAIL = 4096


def parse(data: bytes):
    """(chunks, tailBytes). Chunks are (rawSize, compressedSize, blobOffset)."""
    out = []
    o = 0
    n = len(data)
    while o + 8 <= n:
        raw, comp = struct.unpack_from("<II", data, o)
        if raw == 0 or comp == 0 or raw > CHUNK_RAW * 4 or o + 8 + comp > n:
            break
        out.append((raw, comp, o + 8))
        o += 8 + comp
    if not out:
        raise LinError("not a LIN chunk chain")
    tail = data[o:]
    if len(tail) > MAX_TAIL:
        raise LinError("chunk chain ended at 0x%X with 0x%X bytes left over"
                       % (o, len(tail)))
    return out, tail


def chunks(data: bytes):
    """Yield (rawSize, compressedSize, blobOffset) for each chunk."""
    parts, _tail = parse(data)
    return iter(parts)


def is_lin(data: bytes) -> bool:
    if len(data) < 8:
        return False
    try:
        parts, _tail = parse(data)
        return len(parts) > 1
    except (LinError, struct.error, zlib.error):
        return False


def decompress(data: bytes) -> bytes:
    out = bytearray()
    for raw, comp, off in chunks(data):
        try:
            piece = zlib.decompressobj().decompress(data[off:off + comp])
        except zlib.error as exc:
            raise LinError("chunk at 0x%X does not inflate: %s" % (off, exc)) from exc
        if len(piece) != raw:
            raise LinError("chunk at 0x%X yields %d bytes, header says %d"
                           % (off, len(piece), raw))
        out += piece
    return bytes(out)


def rebuild(plain: bytes, tail: bytes = b"", level: int = 9) -> bytes:
    """A whole container from a payload of ANY length.

    The counterpart to `substitute`, for the case it refuses. Nothing here is
    clever: re-chunk the payload at exactly `CHUNK_RAW` and deflate each chunk
    on its own, which is the layout the loader expects. The size rule that
    `substitute` enforces is about the PACKAGES inside the payload, not about
    the container -- the container is a bare chain to EOF with no length
    recorded anywhere in it, so a longer payload simply makes a longer chain.

    Chunking at the wrong granularity is the trap. The loader inflates into a
    fixed 16384-byte buffer, so a chunk that yields more than that overruns it,
    and the failure looks like corrupt geometry rather than a bad read.
    """
    if not plain:
        raise LinError("refusing to build a container with no payload")
    out = bytearray()
    for i in range(0, len(plain), CHUNK_RAW):
        raw = plain[i:i + CHUNK_RAW]
        comp = zlib.compress(raw, level)
        # The reader keeps its COMPRESSED chunk in a fixed 16384-byte buffer
        # too (a 0x8054-byte object: two 16 KB buffers and their state), and
        # zlib can come out a few bytes longer than its input on data that
        # does not compress. No shipped chunk is anywhere near it -- the
        # largest level chunk is 15,906 -- so this refuses rather than trims.
        if len(comp) > CHUNK_RAW:
            raise LinError("chunk at plain 0x%X deflates to %d bytes, past the "
                           "loader's %d-byte buffer" % (i, len(comp), CHUNK_RAW))
        out += struct.pack("<II", len(raw), len(comp)) + comp
    out += tail
    # A container that will not read back is not worth writing.
    if decompress(bytes(out)) != plain:
        raise LinError("rebuilt container does not round-trip")
    return bytes(out)


def rebuild_exact(plain: bytes, tail: bytes, size: int, level: int = 9) -> bytes:
    """`rebuild`, landing on exactly `size` bytes -- the slot it shipped in.

    Why a rebuilt container must not simply come out smaller: the archive
    writer shrinks the file's recorded extent to match, and the bytes it gave
    up become a free run. The allocator is best-fit, so the next INI that
    outgrows its own slot lands in exactly that kind of gap -- and putting the
    original container back later writes its full length over the newcomer.
    Holding the size fixed leaves the archive's layout exactly as it shipped.

    The slack is spread over every chunk as empty stored deflate blocks
    (`EMPTY_STORED`, five bytes that decode to nothing) -- the padding the
    same-length edits already carry into the game -- a few per chunk rather
    than kilobytes in one place. Whatever is left under five bytes is taken
    up by re-deflating one chunk to an exact length.
    """
    if not plain:
        raise LinError("refusing to build a container with no payload")
    parts = []
    for i in range(0, len(plain), CHUNK_RAW):
        raw = plain[i:i + CHUNK_RAW]
        comp = zlib.compress(raw, level)
        if len(comp) > CHUNK_RAW:
            raise LinError("chunk at plain 0x%X deflates to %d bytes, past the "
                           "loader's %d-byte buffer" % (i, len(comp), CHUNK_RAW))
        parts.append([raw, comp])

    def total():
        return sum(8 + len(c) for _r, c in parts) + len(tail)

    slack = size - total()
    if slack < 0:
        # zlib cannot reach it -- the winter levels' recordings come out 16
        # to 25 KB over at level 9. Zopfli packs the same chunk about 5%
        # tighter, and costs about a third of a second per chunk, so it is
        # spent on the largest chunks first and only until the file fits:
        # 40 to 50 chunks of 700-900 on those levels.
        for k in sorted(range(len(parts)), key=lambda n: -len(parts[n][1])):
            if slack >= 0:
                break
            packed = _zopfli(parts[k][0], ZOPFLI_FIT_ITERATIONS)
            if packed is None:
                break                          # zopfli is not installed
            if len(packed) < len(parts[k][1]):
                try:
                    if zlib.decompress(packed) != parts[k][0]:
                        continue
                except zlib.error:
                    continue
                slack += len(parts[k][1]) - len(packed)
                parts[k][1] = packed
    if slack < 0:
        raise LinTooBig("the rebuilt container is %d bytes over its %d-byte "
                        "slot" % (-slack, size))
    per, extra = divmod(slack // 5, len(parts))
    for n, part in enumerate(parts):
        k = min(per + (1 if n < extra else 0),
                (CHUNK_RAW - len(part[1])) // 5)
        if k:
            # after the two-byte zlib header, where the first block begins
            part[1] = part[1][:2] + EMPTY_STORED * k + part[1][2:]
    rest = size - total()
    for part in reversed(parts):
        if not rest:
            break
        budget = len(part[1]) + rest
        if budget > CHUNK_RAW:
            continue
        exact = _deflate_exact(part[0], budget)
        if exact is not None:
            part[1] = exact
            rest = 0
    if rest:
        raise LinError("could not land the container on exactly %d bytes "
                       "(%d left over)" % (size, rest))
    out = b"".join(struct.pack("<II", len(r), len(c)) + c for r, c in parts)
    out += tail
    if len(out) != size or decompress(out) != plain:
        raise LinError("exact rebuild does not round-trip -- refusing to write")
    return out


def _zopfli(plain: bytes, iterations: int = 15):
    """A zlib stream packed by zopfli, or None if zopfli is not installed.

    Zopfli emits ordinary deflate that any inflater reads -- it just searches
    much harder for the shortest encoding. That matters here because the game's
    own packer beat `zlib` on some chunks: `COMMON.LIN`'s chunk at plain
    0x15c000 occupies 5640 bytes on the disc and `zlib -9` cannot get its
    UNTOUCHED contents below 5658. Without this, that chunk could never be
    edited at all, whatever the edit was. Zopfli packs the same bytes into
    5488, which is 152 bytes of room.
    """
    try:
        import zopfli.zlib as _zz
    except ImportError:
        return None
    try:
        return _zz.compress(plain, numiterations=iterations)
    except Exception:                                 # noqa: BLE001
        return None


#: An empty, non-final STORED deflate block: three header bits (BFINAL=0,
#: BTYPE=00), padding to the byte boundary, then LEN=0 and its complement. It
#: is exactly the marker `Z_SYNC_FLUSH` emits, it decodes to nothing, and it can
#: be repeated -- so a stream can be lengthened five bytes at a time without
#: changing what it decompresses to.
EMPTY_STORED = b"\x00\x00\x00\xff\xff"


def _deflate_exact(plain: bytes, budget: int):
    """A zlib stream of EXACTLY `budget` bytes, or None.

    Why bother: the game's own packer never leaves a byte after the end of a
    stream -- measured, zero such chunks in any shipped COMMON package -- while
    this rebuild used to zero-pad every chunk that re-deflated smaller than its
    slot. Matching what the disc actually does is worth having for its own
    sake, and it costs a tenth of a second.

    It is NOT known to fix anything. It was reached while chasing a hang, on
    the observation that the failing edits padded and the working ones did not
    -- and then `rpg_speed`, which works, turned out to pad 163 bytes, almost
    exactly what the failing ss_man_down padded. So the correlation is broken
    and this is tidiness, not a cure. When it cannot hit the slot exactly the
    caller falls back to padding, because refusing would break `rpg_speed`.

    The slack is taken up INSIDE the stream instead, as empty stored blocks in
    front of the real data. They are only insertable five bytes at a time, so
    the search sweeps levels and strategies until one lands on a length whose
    shortfall is a multiple of five.
    """
    want = struct.pack(">I", zlib.adler32(plain))
    for level in range(9, 0, -1):
        for strategy in (zlib.Z_DEFAULT_STRATEGY, zlib.Z_FILTERED,
                         zlib.Z_RLE, zlib.Z_HUFFMAN_ONLY, zlib.Z_FIXED):
            # Empty stored blocks only come in fives, so the shortfall has to
            # land on a multiple of five. Moving the first few bytes into a
            # stored block of their own shifts the total by about one byte a
            # time, which is what makes every residue reachable.
            for lead in range(0, 24):
                prefix, rest = plain[:lead], plain[lead:]
                try:
                    co = zlib.compressobj(level, zlib.DEFLATED, -15, 9, strategy)
                    body = co.compress(rest) + co.flush()
                except (zlib.error, ValueError):
                    break
                stored = b""
                if lead:
                    stored = (b"\x00" + struct.pack("<HH", lead, lead ^ 0xFFFF)
                              + prefix)
                slack = budget - (2 + len(stored) + len(body) + 4)
                if slack < 0:
                    break                      # longer `lead` only grows it
                if slack % 5:
                    continue
                out = (b"\x78\x9c" + EMPTY_STORED * (slack // 5)
                       + stored + body + want)
                if len(out) == budget:
                    try:
                        if zlib.decompress(out) == plain:
                            return out
                    except zlib.error:
                        pass

    if os.environ.get("TCMS_LEGACY_PACK"):
        # Bisect switch. The build before this one could not steer zopfli onto
        # an exact length, so these chunks fell through to `_deflate_within`
        # and were zero-padded. Setting this reproduces those bytes exactly,
        # which is the only way to ask the console whether the difference
        # matters -- Python's inflate accepts both, so it cannot answer.
        return None

    # Some chunks on these discs are packed tighter than zlib can match, so the
    # sweep above never even gets under the slot and zopfli is the only thing
    # that fits. Its length is not steerable by strategy OR, usefully, by the
    # iteration count -- that plateaus, see ZOPFLI_LEADS. So the residue is
    # swept the same way as above instead, by moving bytes out of the
    # compressed body and into a literal block in front of it.
    for iterations in ZOPFLI_LADDER:
        base = _zopfli(plain, iterations)
        if base is None:
            return None                    # zopfli is not installed at all
        if budget - len(base) < 0:
            continue                       # too tight even here; pack harder
        for lead in range(0, ZOPFLI_LEADS):
            packed = base if lead == 0 else _zopfli(plain[lead:], iterations)
            if packed is None:
                break
            # Strip zopfli's zlib header and its adler32: what is wanted is
            # the bare deflate blocks, so a literal block can go in front and
            # the checksum at the end can cover the WHOLE plaintext.
            body = packed[2:-4]
            stored = b""
            if lead:
                stored = (b"\x00" + struct.pack("<HH", lead, lead ^ 0xFFFF)
                          + plain[:lead])
            slack = budget - (2 + len(stored) + len(body) + 4)
            if slack < 0:
                break                      # a longer lead only grows it
            if slack % 5:
                continue
            out = (b"\x78\x9c" + EMPTY_STORED * (slack // 5)
                   + stored + body + want)
            if len(out) == budget:
                try:
                    if zlib.decompress(out) == plain:
                        return out
                except zlib.error:
                    pass
    return None


def _deflate_within(plain: bytes, budget: int):
    """The smallest deflate of `plain` that fits `budget`, or None."""
    best = None
    for level in (9, 8, 7, 6, 5):
        packed = zlib.compress(plain, level)
        if best is None or len(packed) < len(best):
            best = packed
        if len(best) <= budget:
            return best
    # Only now pay for zopfli, which is far slower than zlib and only worth it
    # on the chunks zlib cannot fit. Its output is verified by inflating it
    # back before it is trusted, because a chunk that does not decompress to
    # exactly the right bytes would corrupt the game silently.
    packed = _zopfli(plain)
    if packed is not None and len(packed) <= budget:
        try:
            if zlib.decompress(packed) == plain:
                return packed
        except zlib.error:
            pass
    return best if len(best) <= budget else None


def substitute(data: bytes, edit) -> tuple:
    """Rewrite a container through `edit(plain) -> plain`, same length.

    Returns (container, chunksTouched). The container is the same length as the
    one handed in, and every chunk the edit did not change keeps its original
    compressed bytes untouched.
    """
    parts, tail = parse(data)
    plain = decompress(data)
    new_plain = edit(plain)
    if len(new_plain) != len(plain):
        raise LinError("a LIN edit must preserve length exactly (%d -> %d)"
                       % (len(plain), len(new_plain)))
    if new_plain == plain:
        return data, 0

    out = bytearray()
    pos = 0
    touched = 0
    padded = 0
    for raw, comp, off in parts:
        old_slice = plain[pos:pos + raw]
        new_slice = new_plain[pos:pos + raw]
        pos += raw
        if new_slice == old_slice:
            out += struct.pack("<II", raw, comp) + data[off:off + comp]
            continue
        # Fill the slot exactly if at all possible -- see `_deflate_exact`.
        # Zero padding after the end of a stream is the one thing this rebuild
        # used to do that the game's own packer never does.
        packed = _deflate_exact(new_slice, comp) or _deflate_within(new_slice, comp)
        if packed is None:
            # Name the likely cause. Some chunks were packed tighter than
            # `zlib` can manage, so without zopfli they refuse EVERY edit --
            # including one-byte ones -- and blaming the edit sends the reader
            # looking in the wrong place entirely.
            extra = ""
            if _zopfli(b"probe") is None:
                extra = ("; zopfli is not installed, and some chunks on these "
                         "discs are packed tighter than zlib can match, so "
                         "they cannot be rewritten without it")
            raise LinError(
                "chunk at 0x%X re-deflates larger than its %d-byte slot; the "
                "container length cannot move, so this edit cannot be applied%s"
                % (off, comp, extra))
        if len(packed) < comp:
            padded += 1
        packed = packed + b"\x00" * (comp - len(packed))
        out += struct.pack("<II", raw, comp) + packed
        touched += 1

    out += tail
    result = bytes(out)
    if len(result) != len(data):
        raise LinError("rebuild changed the container length (%d -> %d)"
                       % (len(data), len(result)))
    if decompress(result) != new_plain:
        raise LinError("rebuild does not round-trip -- refusing to write")
    return result, touched

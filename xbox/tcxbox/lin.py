"""Rainbow Six 3's `.LIN` packages: chunked zlib, and how to edit one safely.

Layout is a bare chain of chunks to EOF:

    repeat:
        u32 rawSize          (16384 for every chunk but the last)
        u32 compressedSize
        u8  blob[compressedSize]

Note the field order is (raw, compressed) -- the reverse of the Red Storm games'
container in `rselzo.py`, which is exactly the kind of detail that silently
produces garbage if you assume.

**The editing rule is narrow and it is not negotiable: equal-length
substitution only.** The payload is a concatenation of about 110 cooked Unreal
packages whose recorded offsets the PS2 cooker relaid, so changing any package's
byte length corrupts loading -- the symptom is a very slow load and then the
emulator asserting on garbage geometry fed to the VIF. So `substitute` takes a
function that must hand back exactly as many bytes as it was given, re-deflates
only the chunks whose plain bytes actually changed, and pads each one back to
its original compressed size so the container's own length never moves either.

Padding is safe because the loader inflates a stream and stops at its end;
trailing bytes inside the chunk are never looked at -- `rpg_speed` ships 163
bytes of it and works. `_deflate_exact` avoids needing it where it can, because
the disc's own packer never leaves a byte after a stream in any shipped COMMON
package, and matching that is worth a tenth of a second.
"""

#: Shared, byte for byte, with the PS2 tool's `tcps2/lin.py`. The container is
#: the same on both discs -- Rainbow Six 3 Xbox ships 95 `.lin` packages in
#: `System\` and `Common.lin` among them -- so the two copies are kept
#: identical rather than allowed to drift. Change one, change the other.
#:
#: This copy was refreshed from the PS2 one, which had gained `_deflate_exact`
#: and the zopfli fallback while this one stood still. That is exactly the
#: drift the note above exists to prevent, and it cost nothing only because
#: the newer file is a superset.

from __future__ import annotations

import struct
import zlib

CHUNK_RAW = 16384


class LinError(Exception):
    pass


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

    # Some chunks on these discs are packed tighter than zlib can match, so the
    # sweep above never even gets under the slot and zopfli is the only thing
    # that fits. Its length is not steerable by strategy, but it does move with
    # the iteration count, which is enough to find one whose shortfall is a
    # multiple of five.
    for iterations in range(5, 61):
        packed = _zopfli(plain, iterations)
        if packed is None:
            break
        slack = budget - len(packed)
        if slack < 0 or slack % 5:
            continue
        out = packed[:2] + EMPTY_STORED * (slack // 5) + packed[2:]
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

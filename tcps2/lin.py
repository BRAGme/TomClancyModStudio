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
trailing bytes inside the chunk are never looked at.
"""

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


def _deflate_within(plain: bytes, budget: int):
    """The smallest deflate of `plain` that fits `budget`, or None."""
    best = None
    for level in (9, 8, 7, 6, 5):
        packed = zlib.compress(plain, level)
        if best is None or len(packed) < len(best):
            best = packed
        if len(best) <= budget:
            return best
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
    for raw, comp, off in parts:
        old_slice = plain[pos:pos + raw]
        new_slice = new_plain[pos:pos + raw]
        pos += raw
        if new_slice == old_slice:
            out += struct.pack("<II", raw, comp) + data[off:off + comp]
            continue
        packed = _deflate_within(new_slice, comp)
        if packed is None:
            raise LinError(
                "chunk at 0x%X re-deflates larger than its %d-byte slot; the "
                "container length cannot move, so this edit cannot be applied"
                % (off, comp))
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

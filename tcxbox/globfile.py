"""Red Storm's Xbox `.GLB` globs: the packed form of the loose game data.

A glob is a flat, sequential container with no index -- every entry carries its
own name and length and the payload follows immediately, so the only way to
find the tenth file is to walk the first nine.

    u32 version                     (2 on every glob in all four games)
    u32 count
    [u32 dataBytes, u32 reserved]   Ghost Recon 2 and Summit Strike only
    repeat count times:
        u32 nameLength              (includes the terminating NUL)
        u8  name[nameLength]
        u32 storedSize              bytes actually in the file
        u32 packed                  1 = LZO, 0 = stored verbatim
        u32 rawSize                 == storedSize when packed is 0
        u8  data[storedSize]

The three size words read (stored, flag, raw), **not** (raw, flag, stored).
The two are indistinguishable on a stored entry, where both sizes are equal,
and every glob's first few entries are stored -- so the wrong order parses the
opening of a file convincingly and then walks off the end of it somewhere in
the middle. Across the 254 globs in the four games the packed entries are only
`.rsb`, `.sht`, `.map` and `.xmap`: **every** XML data file this tool edits --
`.mis`, `.atr`, `.cgs`, `.gun`, `.wsf`, `.gtf`, `.prj`, `.itm`, `.vcl` -- is
stored verbatim, 21,000 entries of them, so nothing here needs a decompressor.

The two header shapes are told apart by parsing, not by guessing from the game:
one of them walks to exactly the end of the file and the other does not, and
`parse` simply tries both. That is worth doing rather than keying off the title,
because Summit Strike is a Ghost Recon 2 build and Island Thunder is a Ghost
Recon build, so a per-game table would only be the same test written twice.

**Why this module exists at all.** The mission files sit loose under
`mission\\` *and* inside `globs\\ikedata.glb`, byte for byte identical, and the
enemy templates the missions name sit only inside the per-level `*_chars.glb`.
So anything that edits enemies has to reach into the globs; editing the loose
copy alone would change nothing the engine reads.

Writing is deliberately length-preserving: every transform in `transforms.py`
pads rather than shortens, so a glob is patched at the byte the entry already
occupies and no offset in the container ever moves.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


class GlobError(Exception):
    pass


@dataclass
class Entry:
    name: str          # as recorded, e.g. "m01_caves.mis"
    offset: int        # where the payload starts in the file
    size: int          # bytes actually stored
    header: int        # where this entry's name-length field starts
    packed: bool = False   # LZO rather than verbatim
    raw_size: int = 0      # length once expanded


def _walk(read, size: int, head: int):
    """Entries for a given header size, or None if the walk does not land
    exactly on the end of the container.

    `read(offset, length)` rather than a bytes object, because a glob can be
    2.7 MB of mostly texture and there are 254 of them: indexing a game should
    not mean pulling half a gigabyte through memory, and on a disc image it
    would mean pulling it off the disc as well.
    """
    # `size < head`, not `size < head + 4`: Ghost Recon 2's opposing_force.glb
    # is an empty glob -- a 16-byte header, a count of zero, nothing after it.
    if size < head:
        return None
    header = read(0, head)
    if len(header) < 8:
        return None
    version, count = struct.unpack_from("<II", header, 0)
    if version != 2 or not 0 <= count < 100000:
        return None
    out = []
    o = head
    for _ in range(count):
        chunk = read(o, 4)
        if len(chunk) < 4:
            return None
        (nlen,) = struct.unpack_from("<I", chunk, 0)
        if not 0 < nlen < 512 or o + 4 + nlen + 12 > size:
            return None
        start = o
        rest = read(o + 4, nlen + 12)
        if len(rest) < nlen + 12:
            return None
        name = rest[:nlen].split(b"\0")[0].decode("latin1")
        stored, packed, raw = struct.unpack_from("<III", rest, nlen)
        o += 4 + nlen + 12
        if packed not in (0, 1) or o + stored > size:
            return None
        out.append(Entry(name, o, stored, start, bool(packed), raw))
        o += stored
    return out if o == size else None


def parse_stream(read, size: int):
    """Every entry in a glob, read through `read(offset, length)`."""
    for head in (8, 16):
        got = _walk(read, size, head)
        if got is not None:
            return got
    raise GlobError("not a .glb glob, or a shape this tool does not know")


def parse(data: bytes):
    """Every entry in a glob already in memory."""
    return parse_stream(lambda off, n: data[off:off + n], len(data))


def is_glob(data: bytes) -> bool:
    try:
        parse(data)
        return True
    except (GlobError, struct.error):
        return False


def read(data: bytes, entry: Entry) -> bytes:
    return data[entry.offset:entry.offset + entry.size]


def replace(data: bytes, entry: Entry, blob: bytes) -> bytes:
    """Put `blob` back in place. Same length only -- see the module docstring."""
    if len(blob) != entry.size:
        raise GlobError("%s: %d bytes cannot replace %d without moving every "
                        "entry after it" % (entry.name, len(blob), entry.size))
    return data[:entry.offset] + blob + data[entry.offset + entry.size:]

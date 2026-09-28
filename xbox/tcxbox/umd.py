"""Rainbow Six 3's `.UMD` bundles -- where the Xbox build really keeps System.

Retail Rainbow Six 3 on Xbox looks, from the file tree, as though it has almost
nothing to mod: `System\\` holds 98 cooked `.lin` packages and exactly two ini
files. That is misleading. `xboxdynamic.umd` is a 2.4 MB bundle holding 536
files, and among them are the 115 `Template\\*.tpt` terrorist templates, all 38
ini files -- including the 16 KB `R6GAMESETTINGS.ini` that carries the game's
whole gameplay tuning table -- and **a second copy of RainbowSix3Xbox.ini**,
5,155 bytes against the loose file's 5,393. The two are not the same file, so
editing the loose one and stopping there is a real way to change nothing.

Layout:

    [ file data, back to back, each padded to a 16-byte boundary ]
    [ index: repeat { u8 nameLength (counts the NUL), name, u32 offset,
                      u32 size, u32 zero } ]
    [ footer: u32 hash, u32 indexOffset, u32 fileLength, u32 2, u32 magic ]

`indexOffset` in the footer lands one or two bytes *before* the first index
entry -- one in `xboxufiles.umd`, two in `xboxdynamic.umd` -- so the index start
is found by parsing rather than trusted: a walk is only accepted when it lands
exactly on the footer. That is the same test `globfile` uses, and for the same
reason: a length field that is nearly right is worse than one that is absent,
because it parses convincingly for a while.

Writing is in place and length-preserving; `replace` says why.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

FOOTER = 20


class UmdError(Exception):
    pass


@dataclass
class Entry:
    name: str          # as recorded, e.g. "System\\R6GAMESETTINGS.ini"
    offset: int
    size: int


def _walk(read, start: int, end: int, total: int):
    o = start
    out = []
    while o < end:
        chunk = read(o, 1)
        if not chunk:
            return None
        nlen = chunk[0]
        o += 1
        if nlen == 0 or o + nlen + 12 > end:
            return None
        rest = read(o, nlen + 12)
        if len(rest) < nlen + 12:
            return None
        raw = rest[:nlen]
        if not raw.endswith(b"\0") or not all(32 <= c < 127 for c in raw[:-1]):
            return None
        offset, size, zero = struct.unpack_from("<III", rest, nlen)
        o += nlen + 12
        if zero != 0 or offset + size > total:
            return None
        out.append(Entry(raw[:-1].decode("latin1"), offset, size))
    return out if o == end else None


def parse_stream(read, total: int):
    """Every entry in a bundle, read through `read(offset, length)`.

    Streamed rather than taken as one bytes object because a bundle is 2.4 MB
    and a game is opened every time one is picked in the window -- and on a disc
    image, holding it would mean pulling it off the disc as well.
    """
    if total < FOOTER + 8:
        raise UmdError("too short to be a .umd")
    end = total - FOOTER
    footer = read(end, FOOTER)
    _hash, index_at, recorded, version, _magic = struct.unpack("<IIIII", footer)
    if recorded != total or version != 2:
        raise UmdError("footer does not describe this file")
    for start in range(max(0, index_at - 4), min(end, index_at + 8)):
        got = _walk(read, start, end, total)
        if got is not None:
            return got
    raise UmdError("could not find the index -- footer points at 0x%X" % index_at)


def parse(data: bytes):
    """(entries, footerBytes) for a bundle already in memory."""
    entries = parse_stream(lambda off, n: data[off:off + n], len(data))
    return entries, data[len(data) - FOOTER:]


def is_umd(data: bytes) -> bool:
    try:
        parse(data)
        return True
    except (UmdError, struct.error, IndexError):
        return False


def read(data: bytes, entry: Entry) -> bytes:
    return data[entry.offset:entry.offset + entry.size]


def replace(data: bytes, entry: Entry, blob: bytes) -> bytes:
    """Put `blob` back in its slot. Same length only.

    In-place rather than a rebuild, deliberately. The index records an explicit
    offset for every file, so relocating one would be easy -- but the two
    bundles do not agree about what sits between the end of the data and the
    first index entry (one slack byte in `xboxufiles.umd`, two in
    `xboxdynamic.umd`, and neither is an alignment), and the footer's first word
    is an unidentified hash. Writing only inside a slot leaves every one of
    those bytes exactly as the game shipped them, and costs nothing: everything
    this tool edits is text, and every transform pads rather than shortens.
    """
    if len(blob) != entry.size:
        raise UmdError("%s: %d bytes cannot replace %d without moving the index"
                       % (entry.name, len(blob), entry.size))
    return data[:entry.offset] + blob + data[entry.offset + entry.size:]

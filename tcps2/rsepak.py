"""The `.PAK` texture container of Ghost Recon / Jungle Storm PS2.

A flat chain of records with no header and no directory, closed by a sentinel.
The layout below is transcribed from the Ghost Recon ELF (SLUS-206.13), which
ships a full symbol table: `UITextureMgr::LoadingTexturePak` @0x0051B660 walks
the chain and `UITexture::LoadPS2Img` @0x0051D910 reads one record.

    pak    := record* u32(99)         # 99 = 0x63 ends the loop, 0x51BAFC
    record := u32 kind; u32 nameLen; char name[nameLen]; <body by kind>

    kind 0  u32 psm, width, height; then twice: u32 size; u8 data[size]
            -- stored verbatim, CLUT then pixels (size 0 = no CLUT)
    kind 2  u32 psm, width, height; then once, or twice for psm 19/20:
            u32 size; u32 rawSize; u8 bitstream[size - 4]
            -- lz77, CLUT then pixels. `size` counts the rawSize field.
    kind 3  u32 size; u8 jpeg[size]
            -- NO psm/width/height: they come out of the JPEG header

Any other kind makes the loader abandon the whole file (0x51BA70), so 0, 2, 3
and 99 are the only legal tags. Both the verbatim and the decoded buffers open
with a 16-byte GS GIFtag, which is why a decoded segment is 16 bytes longer
than its pixels.

`tcps2.rselz77` is the kind-2 codec: Red Storm's own `class lz77`, a plain LZSS
over a 64 KB window.

MOVING ART BETWEEN DISCS needs none of that. A record carries its own psm,
width and height and nothing else on the disc has to agree with them, so
`with_art` keeps the name the loader asks for and takes the donor's size and
payload. Nothing is decoded and nothing is re-encoded.
"""

from __future__ import annotations

import struct

from . import rselz77

END_TAG = 99
NUL = chr(0)
PSM_PSMCT32, PSM_PSMT8, PSM_PSMT4 = 0, 19, 20


class PakError(Exception):
    pass


class Record:
    __slots__ = ("kind", "name", "psm", "width", "height", "segments", "raw")

    def __init__(self, kind, name, psm, width, height, segments=None, raw=None):
        self.kind = kind
        self.name = name                  # exactly as stored, terminator and all
        self.psm = psm
        self.width = width
        self.height = height
        self.segments = list(segments or ())   # kind 2: [(rawSize, bitstream)]
        self.raw = list(raw or ())             # kind 0: [bytes], kind 3: [jpeg]

    # -- identity ---------------------------------------------------------
    @property
    def key(self):
        """The name with its terminator stripped, for lookups."""
        return self.name.rstrip(NUL)

    def renamed(self, new_key):
        """A copy under a different name, keeping this record's terminator."""
        term = NUL * (len(self.name) - len(self.key))
        r = Record(self.kind, new_key + term, self.psm, self.width, self.height,
                   self.segments, self.raw)
        return r

    def with_art(self, other):
        """This record's NAME carrying `other`'s picture.

        The name is what the loader asks for, so it stays; everything that
        describes the picture comes from the donor.
        """
        return Record(other.kind, self.name, other.psm, other.width,
                      other.height, other.segments, other.raw)

    # -- pixels -----------------------------------------------------------
    def payloads(self):
        """The record's decoded buffers, GIFtag included, CLUT first."""
        if self.kind == 0:
            return list(self.raw)
        if self.kind == 2:
            return [rselz77.decompress(b, n) for n, b in self.segments]
        raise PakError("%s is kind %d; only 0 and 2 hold GS data"
                       % (self.key, self.kind))

    def __repr__(self):
        return "<%s kind%d psm%s %sx%s %d segs>" % (
            self.key, self.kind, self.psm, self.width, self.height,
            len(self.segments) or len(self.raw))

    def encode(self) -> bytes:
        name = self.name.encode("latin-1")
        out = bytearray(struct.pack("<II", self.kind, len(name)))
        out += name
        if self.kind == 3:
            out += struct.pack("<I", len(self.raw[0])) + self.raw[0]
            return bytes(out)
        out += struct.pack("<III", self.psm, self.width, self.height)
        if self.kind == 0:
            for blob in self.raw:
                out += struct.pack("<I", len(blob)) + blob
        else:
            for rawsize, body in self.segments:
                out += struct.pack("<II", len(body) + 4, rawsize) + body
        return bytes(out)


def parse(blob: bytes):
    """[Record] -- raises rather than guessing if the chain does not close."""
    recs, o, n = [], 0, len(blob)
    while True:
        if o + 4 > n:
            raise PakError("ran off the end at 0x%X without the %d terminator"
                           % (o, END_TAG))
        kind = struct.unpack_from("<I", blob, o)[0]
        o += 4
        if kind == END_TAG:
            if o != n:
                raise PakError("terminator at 0x%X but the file is 0x%X bytes"
                               % (o, n))
            return recs
        if kind not in (0, 2, 3):
            raise PakError("unknown record kind %d at 0x%X" % (kind, o - 4))
        nl = struct.unpack_from("<I", blob, o)[0]
        o += 4
        name = blob[o:o + nl].decode("latin-1")
        o += nl
        if kind == 3:
            size = struct.unpack_from("<I", blob, o)[0]
            o += 4
            recs.append(Record(kind, name, None, None, None,
                               raw=[blob[o:o + size]]))
            o += size
            continue
        psm, w, h = struct.unpack_from("<III", blob, o)
        o += 12
        segs, raws = [], []
        if kind == 0:
            for _ in range(2):
                size = struct.unpack_from("<I", blob, o)[0]
                o += 4
                raws.append(blob[o:o + size])
                o += size
        else:
            for _ in range(2 if psm in (PSM_PSMT8, PSM_PSMT4) else 1):
                size, rawsize = struct.unpack_from("<II", blob, o)
                segs.append((rawsize, blob[o + 8:o + 4 + size]))
                o += 4 + size
        recs.append(Record(kind, name, psm, w, h, segs, raws))


def build(records) -> bytes:
    return b"".join(r.encode() for r in records) + struct.pack("<I", END_TAG)


def check_roundtrip(blob: bytes):
    """(records, True) if parse->build reproduces `blob` byte for byte."""
    recs = parse(blob)
    return recs, build(recs) == blob


def index(records):
    """{lowercased name: Record}."""
    return {r.key.lower(): r for r in records}


def pack_psmt8(gif_clut: bytes, gif_pix: bytes, palette, indices) -> list:
    """lz77 segments for a psm19 record: (CLUT, pixels), GIFtags carried over.

    `palette` is 256 (r, g, b, a) with PS2 alpha (0..128); it is written in the
    GS's CSM1 order, which swaps the middle two groups of eight in every 32.
    """
    if len(palette) != 256:
        raise PakError("a PSMT8 CLUT holds 256 entries, not %d" % len(palette))
    csm1 = list(palette)
    for base in range(0, 256, 32):
        for i in range(8):
            csm1[base + 8 + i] = palette[base + 16 + i]
            csm1[base + 16 + i] = palette[base + 8 + i]
    clut = bytearray(gif_clut)
    for r, g, b, a in csm1:
        clut += bytes((r, g, b, a))
    pix = bytes(gif_pix) + bytes(indices)
    return [(len(clut), rselz77.compress(bytes(clut))),
            (len(pix), rselz77.compress(pix))]


def unpack_psmt8(record):
    """(palette, indices) -- CSM1 undone, alpha left in PS2 range."""
    clut, pix = record.payloads()
    body = clut[len(clut) - 1024:]
    pal = [tuple(body[i * 4:i * 4 + 4]) for i in range(256)]
    out = list(pal)
    for base in range(0, 256, 32):
        for i in range(8):
            out[base + 8 + i] = pal[base + 16 + i]
            out[base + 16 + i] = pal[base + 8 + i]
    n = record.width * record.height
    return out, pix[len(pix) - n:]


def gifs(record):
    """The 16-byte GIFtag that opens each of the record's buffers."""
    return [p[:16] for p in record.payloads()]

r"""Diesel's compiled XML -- `.xml.bin` in GRAW 1, `.xmb` in GRAW 2.

**This module exists because editing the plain `.xml` is not enough.** Both
Advanced Warfighter games ship every data file twice, as source and as a
compiled twin, and the retail engine loads the COMPILED one. The proof is
inside the game: `quick.bundle` accidentally ships `temp_merged_log.xml`, a
recorded engine session with 9,508 `<open path="...">` records, and where both
forms exist it opened the `.xml.bin` 3,029 times and the `.xml` twice.

100% of the `.xml` files in both bundles have a compiled twin -- 5,672 of 5,674
in GRAW 1 and 7,984 of 7,985 in GRAW 2 -- so "edit the XML" would have been a
no-op for essentially every option. An edit has to go into the compiled file.

## Format

Little-endian. A four-byte magic, a string table, one node tree, and a list of
include paths::

    "XML\x01"
    u32   string count
    ...   that many NUL-terminated strings
    node                                  (the root)
    u32   include count
    ...   that many NUL-terminated paths

A node begins with a u32 kind:

    1  element     u32 name, u32 attr count, that many (u32 key, u32 value)
                   pairs, u32 child count, that many nodes.
                   All four u32s are indices into the string table.
    2  text        u32 index of the raw text
    4  macro       an `xdefine`: NUL-terminated name, u32 param count and that
                   many NUL-terminated names, u32 count and that many u32s,
                   a NUL-terminated body, then ONE pad byte.

Kind 4 is the awkward one: it stores its strings inline rather than in the
table, and it ends with a single byte that is not accounted for by anything
else. Both are reproduced verbatim rather than explained.

The writer rebuilds the string table in first-use order, which is the order
the games' own compiler used: **every one of the 5,674 GRAW 1 and 7,985 GRAW 2
compiled files re-encodes byte-identically**, with one exception in GRAW 2 that
fails to parse at all and is left alone.

Credit: the format was cracked during this project's research pass; this is a
tidied port of that work with the round-trip check kept as a test.
"""

from __future__ import annotations

import struct

MAGIC = b"XML\x01"
NUL = b"\x00"

#: node kinds
ELEMENT, TEXT, MACRO = 1, 2, 4


class XmlBinError(Exception):
    pass


class Node:
    __slots__ = ("kind", "name", "attrs", "kids", "params", "extra", "raw",
                 "pad")

    def __init__(self, kind):
        self.kind = kind
        self.name = None
        #: list of (key, value) pairs -- a LIST, not a dict, because order is
        #: part of the file and a repeated key is legal
        self.attrs = []
        self.kids = []
        self.params = []
        self.extra = []
        self.raw = None
        self.pad = 0

    def __repr__(self):                                    # pragma: no cover
        return "<Node %s %s>" % (self.kind, self.name)

    def get(self, key, default=None):
        for k, v in self.attrs:
            if k == key:
                return v
        return default

    def set(self, key, value) -> bool:
        """Rewrite an attribute in place. True if it was there."""
        hit = False
        for i, (k, v) in enumerate(self.attrs):
            if k == key:
                self.attrs[i] = (k, str(value))
                hit = True
        return hit

    def walk(self):
        yield self
        for kid in self.kids:
            for node in kid.walk():
                yield node


def loads(data: bytes):
    """(root node, include paths)."""
    if data[:4] != MAGIC:
        raise XmlBinError("not a compiled Diesel XML")
    count, = struct.unpack_from("<I", data, 4)
    pos = 8
    table = []
    for _ in range(count):
        end = data.index(NUL, pos)
        table.append(data[pos:end].decode("latin-1"))
        pos = end + 1

    at = [pos]

    def u32():
        v, = struct.unpack_from("<I", data, at[0])
        at[0] += 4
        return v

    def cstr():
        end = data.index(NUL, at[0])
        s = data[at[0]:end].decode("latin-1")
        at[0] = end + 1
        return s

    def node():
        kind = u32()
        nd = Node(kind)
        if kind == ELEMENT:
            nd.name = table[u32()]
            for _ in range(u32()):
                nd.attrs.append((table[u32()], table[u32()]))
            for _ in range(u32()):
                nd.kids.append(node())
        elif kind == TEXT:
            nd.raw = table[u32()]
        elif kind == MACRO:
            nd.name = cstr()
            nd.params = [cstr() for _ in range(u32())]
            nd.extra = [u32() for _ in range(u32())]
            nd.raw = cstr()
            nd.pad = data[at[0]]
            at[0] += 1
        else:
            raise XmlBinError("unknown node kind %d" % kind)
        return nd

    root = node()
    includes = [cstr() for _ in range(u32())]
    return root, includes


def dumps(root, includes=()) -> bytes:
    """The bytes for this tree. Byte-identical to the original if unchanged."""
    table, index = [], {}

    def add(s):
        if s not in index:
            index[s] = len(table)
            table.append(s)

    def collect(nd):
        if nd.kind == TEXT:
            add(nd.raw)
        elif nd.kind == ELEMENT:
            add(nd.name)
            for k, v in nd.attrs:
                add(k)
                add(v)
            for kid in nd.kids:
                collect(kid)
    collect(root)

    body = bytearray()

    def emit(nd):
        if nd.kind == ELEMENT:
            body.extend(struct.pack("<III", ELEMENT, index[nd.name],
                                    len(nd.attrs)))
            for k, v in nd.attrs:
                body.extend(struct.pack("<II", index[k], index[v]))
            body.extend(struct.pack("<I", len(nd.kids)))
            for kid in nd.kids:
                emit(kid)
        elif nd.kind == TEXT:
            body.extend(struct.pack("<II", TEXT, index[nd.raw]))
        else:
            body.extend(struct.pack("<I", MACRO))
            body.extend(nd.name.encode("latin-1") + NUL)
            body.extend(struct.pack("<I", len(nd.params)))
            for p in nd.params:
                body.extend(p.encode("latin-1") + NUL)
            body.extend(struct.pack("<I", len(nd.extra)))
            for x in nd.extra:
                body.extend(struct.pack("<I", x))
            body.extend(nd.raw.encode("latin-1") + NUL)
            body.append(nd.pad)
    emit(root)

    body.extend(struct.pack("<I", len(includes)))
    for inc in includes:
        body.extend(inc.encode("latin-1") + NUL)

    out = bytearray(MAGIC)
    out.extend(struct.pack("<I", len(table)))
    for s in table:
        out.extend(s.encode("latin-1") + NUL)
    out.extend(body)
    return bytes(out)


# ---------------------------------------------------------------------------
# applying the profiles' edits directly to the tree
# ---------------------------------------------------------------------------

def select(root, path):
    """Nodes matching a `rsexml`-style path, with the same predicate syntax.

    Only what the Advanced Warfighter profiles actually use is supported: a
    tail element name, optionally with one `[attr=value]` predicate. Anything
    fancier is refused rather than quietly matching the wrong thing -- these
    are edits to a binary the game loads, and a selector that silently means
    something else is worse than one that fails.
    """
    import fnmatch

    from .rsexml import _predicate
    parts = [p for p in str(path).replace("\\", "/").split("/") if p]
    if not parts:
        return []
    parsed = [_predicate(p) for p in parts]
    want = [tag.lower() for tag, _k, _v in parsed]
    out = []
    for nd, trail, nodes in _walk(root, [], []):
        if nd.kind != ELEMENT:
            continue
        chain = [t.lower() for t in trail] + [nd.name.lower()]
        if chain[-len(want):] != want:
            continue
        # A predicate on an EARLIER segment is how one side of the game is
        # addressed without the other: Advanced Warfighter declares every
        # weapon twice in the same file, `scar_light` for the human and
        # `scar_light_3rd` for everything an AI carries, so the two spreads
        # are the same element name in the same file and only the enclosing
        # `<unit>` tells them apart.
        line = (nodes + [nd])[-len(parsed):]
        ok = True
        for node, (_tag, key, value) in zip(line, parsed):
            if key is None:
                continue
            negate = key.startswith("!")
            got = node.get(key[1:] if negate else key)
            hit = got is not None and fnmatch.fnmatchcase(got.lower(),
                                                          value.lower())
            if hit == negate:
                ok = False
                break
        if ok:
            out.append(nd)
    return out


def _walk(nd, trail, nodes):
    """Yields (node, names of its ancestors, the ancestor NODES themselves).

    The nodes are carried as well as their names because a predicate on an
    earlier path segment has to read that ancestor's attributes.
    """
    yield nd, trail, nodes
    if nd.kind == ELEMENT:
        for kid in nd.kids:
            for triple in _walk(kid, trail + [nd.name], nodes + [nd]):
                yield triple

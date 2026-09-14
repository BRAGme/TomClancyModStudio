"""Just enough cooked-Unreal reading to find Rainbow Six 3's authored actors.

A `.LIN` level is about 110 cooked Unreal packages laid end to end (see
`lin.py`). Each one opens with the standard Engine-2 summary, and this game
builds at file version 123, licensee 22.

**The recorded table offsets are useless here.** The PS2 cooker relaid them, so
`exportOffset` and `importOffset` point into float data rather than at tables --
checked on Shipyard A, where both land in geometry. The name table offset IS
still good, and that turns out to be enough: Unreal serialises a property as

    compactIndex(nameIndex)  infoByte  [size]  value

so once the name table is read, a property can be found by searching for its
own name index followed by a plausible info byte, without walking the exports
at all. `find_int_props` does exactly that.

The info byte is `type | sizeCode << 4 | array << 7`; an int property is type 2
with a 4-byte value, so `0x22`.

**What can and cannot be edited.** Unreal only serialises a property whose value
differs from its class default, so a zone that ships the default count has no
property to rewrite. Values that ARE authored can be changed in place -- an
int32 stays an int32 -- which is what keeps `lin.substitute`'s equal-length rule
satisfied. Adding a property to an actor that omits it would move every byte
after it and is not possible through that door.
"""

from __future__ import annotations

import struct

MAGIC = 0x9E2A83C1

#: property info byte for "int, four-byte value, not an array"
INFO_INT32 = 0x22

#: and the same for a float: type 4, four-byte value. The weapon model on the
#: Unreal-engine discs is mostly floats -- rate of fire, the accuracy cone, the
#: recoil -- so the int locator alone reaches almost none of it.
INFO_FLOAT = 0x24


class PackageError(Exception):
    pass


def compact_index(buf, pos):
    """Unreal's variable-length signed index. Returns (value, nextPos)."""
    b = buf[pos]
    pos += 1
    neg = b & 0x80
    value = b & 0x3F
    if b & 0x40:
        shift = 6
        while True:
            c = buf[pos]
            pos += 1
            value |= (c & 0x7F) << shift
            shift += 7
            if not (c & 0x80):
                break
    return (-value if neg else value), pos


def encode_compact(value):
    """The inverse, so a package can be searched by name index."""
    neg = value < 0
    v = -value if neg else value
    b0 = v & 0x3F
    v >>= 6
    if neg:
        b0 |= 0x80
    if not v:
        return bytes([b0])
    out = bytearray([b0 | 0x40])
    while True:
        b = v & 0x7F
        v >>= 7
        out.append(b | 0x80 if v else b)
        if not v:
            return bytes(out)


class Package:
    """One cooked package's summary and name table."""

    def __init__(self, data, base):
        self.data, self.base = data, base
        try:
            (magic, self.version, self.licensee, self.flags,
             self.n_names, self.o_names,
             self.n_exports, self.o_exports,
             self.n_imports, self.o_imports) = struct.unpack_from(
                 "<IHHIIIIIII", data, base)
        except struct.error as exc:
            raise PackageError("truncated summary at %d: %s" % (base, exc))
        if magic != MAGIC:
            raise PackageError("no package signature at %d" % base)

    def names(self):
        out, pos = [], self.base + self.o_names
        d = self.data
        for _ in range(self.n_names):
            ln, pos = compact_index(d, pos)
            if ln < 1 or pos + ln > len(d):
                raise PackageError("bad name length %d at %d" % (ln, pos))
            out.append(d[pos:pos + ln - 1].decode("latin-1"))
            pos += ln + 4                     # string, then the object flags
        return out


def tables(data, base):
    """(names, imports, exports) for one package, found by walking not seeking.

    The summary's `importOffset` and `exportOffset` are relaid by the PS2
    cooker and point into float data. The tables are still there, though --
    immediately after the name table, in that order -- so walking the names to
    their end lands on the imports, and the imports on the exports. Checked on
    Shipyard A: 309 imports and 3145 exports parse with no out-of-range index,
    and the export table ends exactly where the next package's signature
    begins.

    `imports` is a list of object-name strings; `exports` is
    [(className, objectName, serialSize, recordedOffset)].
    """
    pkg = Package(data, base)
    names, pos = [], base + pkg.o_names
    for _ in range(pkg.n_names):
        ln, pos = compact_index(data, pos)
        names.append(data[pos:pos + ln - 1].decode("latin-1"))
        pos += ln + 4

    imports = []
    for _ in range(pkg.n_imports):
        _cp, pos = compact_index(data, pos)
        _cn, pos = compact_index(data, pos)
        pos += 4                                  # outer package reference
        nm, pos = compact_index(data, pos)
        if not 0 <= nm < len(names):
            raise PackageError("import name %d out of range at %d" % (nm, pos))
        imports.append(names[nm])

    exports = []
    for _ in range(pkg.n_exports):
        cls, pos = compact_index(data, pos)
        _sup, pos = compact_index(data, pos)
        pos += 4                                  # group reference
        nm, pos = compact_index(data, pos)
        pos += 4                                  # object flags
        size, pos = compact_index(data, pos)
        off = 0
        if size > 0:
            off, pos = compact_index(data, pos)
        if not 0 <= nm < len(names):
            raise PackageError("export name %d out of range at %d" % (nm, pos))
        if cls < 0:
            cname = imports[-cls - 1]             # class came from an import
        elif cls > 0:
            cname = "(export %d)" % cls
        else:
            cname = "Class"
        exports.append((cname, names[nm], size, off))
    return names, imports, exports


def packages(data):
    """Every package in a decompressed level, as (offset, Package).

    A package that will not parse is skipped rather than raised on: the
    signature is four bytes and can occur inside geometry by chance.
    """
    out = []
    needle = struct.pack("<I", MAGIC)
    i = data.find(needle)
    while i >= 0:
        try:
            pkg = Package(data, i)
            pkg.names()
        except (PackageError, IndexError, UnicodeDecodeError):
            pkg = None
        if pkg is not None:
            out.append((i, pkg))
        i = data.find(needle, i + 1)
    return out


def find_int_props(data, names, prop, info=INFO_INT32):
    """[(valueOffset, value)] for every serialised `prop` int in the package.

    The offset points at the four value bytes, so a caller can rewrite them
    without disturbing anything around them.
    """
    if prop not in names:
        return []
    needle = encode_compact(names.index(prop)) + bytes([info])
    out = []
    i = data.find(needle)
    while i >= 0:
        at = i + len(needle)
        if at + 4 <= len(data):
            out.append((at, struct.unpack_from("<i", data, at)[0]))
        i = data.find(needle, i + 1)
    return out


#: Unreal property types that matter here
T_BYTE, T_INT, T_BOOL, T_FLOAT, T_OBJECT, T_NAME, T_STRUCT = 1, 2, 3, 4, 5, 6, 10
_SIZES = {0: 1, 1: 2, 2: 4, 3: 12, 4: 16}


def walk_properties(data, pos, names, limit=200):
    """Parse a property list from `pos` until its `None` terminator.

    Returns [(name, info, valueOffset)], or None if it does not parse -- which
    is the point. The name-index search that finds a property can also match
    random bytes inside geometry, and a false hit almost never walks cleanly to
    a terminator, so this is what separates a real actor from a coincidence.
    """
    out = []
    n = len(data)
    for _ in range(limit):
        if pos >= n:
            return None
        try:
            name_i, pos = compact_index(data, pos)
        except IndexError:
            return None
        if not 0 <= name_i < len(names):
            return None
        if names[name_i] == "None":
            return out
        if pos >= n:
            return None
        info = data[pos]
        pos += 1
        ptype = info & 0x0F
        if ptype == T_STRUCT:                 # a struct names its type first
            _s, pos = compact_index(data, pos)
        code = (info >> 4) & 7
        if code in _SIZES:
            size = _SIZES[code]
        elif code == 5:
            size = data[pos]; pos += 1
        elif code == 6:
            size = struct.unpack_from("<H", data, pos)[0]; pos += 2
        else:
            size = struct.unpack_from("<I", data, pos)[0]; pos += 4
        if ptype == T_BOOL:
            # a bool carries its value in the info byte's top bit, no payload
            out.append((names[name_i], info, pos))
            continue
        if info & 0x80:                       # array element index precedes it
            _a, pos = compact_index(data, pos)
        out.append((names[name_i], info, pos))
        pos += size
        if pos > n:
            return None
    return None


def find_float_props(data, names, prop):
    """[(valueOffset, value)] for every serialised `prop` float."""
    if prop not in names:
        return []
    needle = encode_compact(names.index(prop)) + bytes([INFO_FLOAT])
    out = []
    i = data.find(needle)
    while i >= 0:
        at = i + len(needle)
        if at + 4 <= len(data):
            out.append((at, struct.unpack_from("<f", data, at)[0]))
        i = data.find(needle, i + 1)
    return out


def actor_properties(data, names, prop, info=INFO_INT32):
    """Every VALIDATED site of `prop`, with the properties that follow it.

    [(valueOffset, value, [siblingName, ...])]. Only sites whose property list
    walks cleanly to a terminator are returned.
    """
    out = []
    for at, val in find_int_props(data, names, prop, info):
        rest = walk_properties(data, at + 4, names)
        if rest is None:
            continue
        out.append((at, val, [nm for nm, _i, _o in rest]))
    return out


def float_properties(data, names, prop, sane=None):
    """The same validation, for floats.

    [(valueOffset, value, [siblingName, ...])]. A float found by name index is
    every bit as likely to be a coincidence inside geometry as an int is, so
    the same rule applies: the property list after it has to walk cleanly to a
    terminator. `sane` is an optional (lo, hi) the value must fall inside,
    which throws out the NaNs and the 1e30s that a random four bytes produces.
    """
    out = []
    for at, val in find_float_props(data, names, prop):
        if val != val or val in (float("inf"), float("-inf")):
            continue
        if sane and not (sane[0] <= val <= sane[1]):
            continue
        rest = walk_properties(data, at + 4, names)
        if rest is None:
            continue
        out.append((at, val, [nm for nm, _i, _o in rest]))
    return out


def neighbours(data, at, names, wanted, reach=260):
    """Which of `wanted` appear as name indices near `at`.

    Used to tell one kind of actor from another without the export table: a
    wave zone carries a spawning-point array and the hunt flags, while the
    random-point groups that share the same terrorist counts carry `m_pZone`.
    """
    lo, hi = max(0, at - reach), min(len(data), at + reach)
    window = data[lo:hi]
    idx = {n: i for i, n in enumerate(names)}
    return [n for n in wanted
            if n in idx and encode_compact(idx[n]) in window]

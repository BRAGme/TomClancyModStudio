r"""Unreal Engine 2 packages, read far enough to retune Raven Shield's guns.

Raven Shield keeps its weapon and ammunition statistics as compiled
UnrealScript class defaults inside `system\*.u`. Nothing about them is text.
They are, however, reachable: the packages are **version 118 / licensee 14**,
uncompressed, with valid name and export tables, and every value worth changing
is a fixed-width field in a tagged property list with no checksum over it.

## What can and cannot be done

**Values can be rewritten in place. Properties cannot be added.** Unreal only
serialises a property whose value differs from its class default, so a class
that ships the default has nothing to rewrite, and inserting one would move
every byte after it and invalidate the export table. An int32 overwritten with
another int32 changes nothing else in the file -- which is why every edit here
is equal-width, and why the writer refuses anything that is not.

There is no content hash to worry about: the package summary carries a GUID and
the table counts, and neither depends on the bytes being changed.

## How a property is found: by parsing, not by searching

A property is serialised as `compactIndex(nameIndex) infoByte [size] value`,
so a name index plus an info byte looks like a findable signature -- and that
is how this module first did it. **It was wrong.** A name index is often a
single byte, and a single byte followed by a plausible info byte occurs by
accident inside the *value* of an earlier property. Searching `NormalLMGRPD`
for `fRunningAccuracy` finds a hit 53 bytes early, sitting in the last byte of
`m_fMuzzleVelocity`'s float. Nothing about that hit looks wrong locally, and a
write to it would have quietly corrupted the muzzle velocity instead.

So the list is parsed from its start instead, which means finding the start,
which means walking the whole class header::

    UObject  tagged property list -- ONLY for a non-Class; see below
    UField   SuperField(ci)  Next(ci)
    UStruct  ScriptText(ci)  Children(ci)  FriendlyName(ci)
             Line(u32)  TextPos(u32)  ScriptSize(u32)  script[...]
    UState   ProbeMask(u64)  IgnoreMask(u64)  LabelTableOffset(u16)
             StateFlags(u32)
    UClass   ClassFlags(u32)  ClassGuid(16)
             Dependencies   count(ci) x { Class(ci) Deep(u32) TextCRC(u32) }
             PackageImports count(ci) x ci
             ClassWithin(ci)  ClassConfigName(ci)
             HideCategories count(ci) x ci
             Defaults       tagged property list, terminated by the name "None"

`UClass` is also the one class the engine does NOT give a leading tagged
property list: `UObject::Serialize` writes one for every object whose class is
not `UClass`. A Function, State or Struct export therefore starts with one --
empty, so a single `None` byte -- and a reader that misses it silently reads
the whole header one index out. Only classes are parsed here, so this costs
nothing today; it is handled anyway because nothing about the mistake looks
wrong locally.

`UClass` extending `UState` is the part worth writing down: between the script
and the class flags sit 22 bytes belonging to the state machine, and reading
`ClassFlags` too early lands on the low half of `ProbeMask` -- which looks like
a believable flags word (`0x0202`) and puts everything after it 22 bytes out.

The parse is checked rather than trusted: the walk must consume the class's
serial range **exactly**, ending on the name `None` at its final byte. 535 of
Raven Shield's 541 weapon, first-person and description classes do.

### The six that do not

`ScriptSize` is the length the bytecode occupies **in memory**, not on disk, so
a class that still carries compiled script cannot be skipped past by
arithmetic. Six classes in `R6Weapons.u` are in that position -- `R6Weapons`
itself and five gadget classes. None is a weapon or an ammunition type. Rather
than guess at them, `defaults()` raises and every caller above it declines to
touch the class: a property that cannot be located exactly is one this module
will not write.

## A `b` prefix does not mean a bool

Raven Shield's weapon caps are named `bSingle`, `bCMag`, `bSilencer` and so on,
and all of them are **int32** holding 0 or 1. There are 113 genuinely
bool-typed properties in these packages as well (`m_bIsSilenced` on 46 classes
is the common one), so both really occur and the name settles nothing. That is
why `find_property` CHECKS `kind` rather than searching by it: asking for the
wrong type returns nothing instead of returning the wrong bytes.

## Values live inside structs

The accuracy numbers are not top-level properties. They sit in
`m_stAccuracyValues`, a 49-byte struct whose value is itself a tagged property
list, so the walk recurses and the eight accuracy fields are reached by path.
That nesting is also why the old byte search appeared to work at all.

## Checked against independent work

`research/rs3_weapons.csv` and `rs3_ammo.csv` were produced during the research
pass by a different route. Every offset this module computes is compared
against them in the test suite, so agreement is not an assumption.
"""

from __future__ import annotations

import struct

MAGIC = 0x9E2A83C1

#: the build Raven Shield ships. Anything else is refused rather than guessed
#: at: the header layout changed repeatedly across Unreal 2's life, and a
#: misread export table would point a write at arbitrary bytes.
VERSION, LICENSEE = 118, 14

# property types, as serialised in the low nibble of the info byte
T_BYTE, T_INT, T_BOOL, T_FLOAT, T_OBJECT = 1, 2, 3, 4, 5
T_NAME, T_STRING, T_CLASS, T_ARRAY, T_STRUCT = 6, 7, 8, 9, 10
T_VECTOR, T_ROTATOR, T_STR, T_MAP, T_FIXEDARRAY = 11, 12, 13, 14, 15

TYPE_NAME = {T_BYTE: "byte", T_INT: "int", T_BOOL: "bool", T_FLOAT: "float",
             T_OBJECT: "object", T_NAME: "name", T_STRING: "string",
             T_CLASS: "class", T_ARRAY: "array", T_STRUCT: "struct",
             T_VECTOR: "vector", T_ROTATOR: "rotator", T_STR: "str",
             T_MAP: "map", T_FIXEDARRAY: "fixedarray"}

#: bits 4-6 of the info byte are a size code. Five of the eight are constants;
#: the other three say how the real size is written next.
SIZE_CODE = {0: 1, 1: 2, 2: 4, 3: 12, 4: 16}

#: the info byte an array ELEMENT would have carried if it had a tag of its
#: own. It does not -- elements are bare bytes inside the array's value -- so
#: this is only ever reported, never matched against the file.
INFO_ARRAY_INT = (2 << 4) | T_INT

#: the 22 bytes of `UState`, plus `UClass`'s own flags and GUID, sitting
#: between the end of the script and the dependency list.
STATE_AND_CLASS_HEADER = 8 + 8 + 2 + 4 + 4 + 16


class PackageError(Exception):
    pass


def compact_index(data, pos):
    """(value, next position) for Unreal's variable-length signed int."""
    b = data[pos]
    pos += 1
    sign = -1 if (b & 0x80) else 1
    value = b & 0x3F
    if b & 0x40:
        shift = 6
        for _ in range(4):
            c = data[pos]
            pos += 1
            value |= (c & 0x7F) << shift
            shift += 7
            if not (c & 0x80):
                break
    return sign * value, pos


def put_compact_index(value):
    """The inverse. Used to size a tag, not to search for one."""
    out = bytearray()
    negative = value < 0
    value = abs(value)
    b = value & 0x3F
    if negative:
        b |= 0x80
    value >>= 6
    if value:
        b |= 0x40
    out.append(b)
    while value:
        c = value & 0x7F
        value >>= 7
        if value:
            c |= 0x80
        out.append(c)
    return bytes(out)


def array_index(data, pos):
    """Unreal's array-index encoding, which is NOT the compact index.

    One byte under 128; two bytes when the top bits are `10`; four when they
    are `11`. It agrees with a compact index for indices under 64, which is
    exactly the range that would let a wrong reader look correct, so it is
    spelled out rather than borrowed.
    """
    b = data[pos]
    pos += 1
    if b < 128:
        return b, pos
    if (b & 0xC0) == 0x80:
        return ((b & 0x7F) << 8) + data[pos], pos + 1
    value = ((b & 0x3F) << 24) + (data[pos] << 16) + (data[pos + 1] << 8) \
        + data[pos + 2]
    return value, pos + 3


class Prop:
    """One serialised property: where its value is, and how wide."""

    __slots__ = ("name", "path", "type", "info", "offset", "size", "index")

    def __init__(self, name, path, ptype, info, offset, size, index):
        self.name = name
        self.path = path
        self.type = ptype
        self.info = info
        #: byte offset of the VALUE -- except for a bool, where it is the info
        #: byte itself, because a bool has no value bytes and bit 7 of the tag
        #: carries the value.
        self.offset = offset
        self.size = size
        self.index = index

    @property
    def kind(self):
        return TYPE_NAME.get(self.type, "?")

    def __repr__(self):                                    # pragma: no cover
        return "<%s %s @0x%x>" % (self.kind, self.path, self.offset)


class Export:
    __slots__ = ("name", "class_name", "super_name", "offset", "size", "index",
                 "is_class")

    def __init__(self, index, name, class_name, super_name, offset, size,
                 is_class=False):
        self.index = index
        self.name = name
        self.class_name = class_name
        self.super_name = super_name
        self.offset = offset
        self.size = size
        #: True for a UClass. Its class reference is NULL rather than naming
        #: anything, because Class is the root metaclass and refers to itself
        #: -- so "what kind of object is this" cannot be asked by name here.
        self.is_class = is_class

    def __repr__(self):                                    # pragma: no cover
        return "<Export %s : %s>" % (self.name, self.super_name)


class Package:
    """One `.u`, held as bytes so an edit is a byte replacement."""

    def __init__(self, data: bytes, path=""):
        self.data = bytearray(data)
        self.path = str(path)
        self.names = []
        self.name_index = {}
        self.exports = []
        self._by_name = {}
        self._defaults = {}
        self._read()

    @classmethod
    def load(cls, path):
        with open(path, "rb") as fh:
            return cls(fh.read(), path)

    def to_bytes(self) -> bytes:
        return bytes(self.data)

    # -- header ------------------------------------------------------------

    def _read(self):
        d = self.data
        if len(d) < 64:
            raise PackageError("too short to be a package")
        magic, version, licensee = struct.unpack_from("<IHH", d, 0)
        if magic != MAGIC:
            raise PackageError("not an Unreal package")
        if (version, licensee) != (VERSION, LICENSEE):
            raise PackageError(
                "package is version %d/%d; this reader only handles %d/%d"
                % (version, licensee, VERSION, LICENSEE))
        (_flags, name_count, name_offset, export_count, export_offset,
         import_count, import_offset) = struct.unpack_from("<7I", d, 8)

        pos = name_offset
        for _ in range(name_count):
            length, pos = compact_index(d, pos)
            raw = d[pos:pos + length - 1]          # drop the NUL
            pos += length + 4                      # name bytes + u32 flags
            self.names.append(raw.decode("latin-1"))
        for i, n in enumerate(self.names):
            self.name_index.setdefault(n, i)

        # Imports give a name to a class that lives in another package, which
        # is most of them -- `R6AssaultRifle` is in `R6Weapons.u` while its
        # subclasses are in `R63rdWeapons.u`.
        self.imports = imports = []
        pos = import_offset
        for _ in range(import_count):
            _pkg, pos = compact_index(d, pos)
            _cls, pos = compact_index(d, pos)
            pos += 4                               # package index (int32)
            obj, pos = compact_index(d, pos)
            imports.append(self._name(obj))

        pos = export_offset
        raw_exports = []
        for i in range(export_count):
            cls_ref, pos = compact_index(d, pos)
            super_ref, pos = compact_index(d, pos)
            pos += 4                               # package index (int32)
            obj, pos = compact_index(d, pos)
            pos += 4                               # object flags
            size, pos = compact_index(d, pos)
            offset = 0
            if size > 0:
                offset, pos = compact_index(d, pos)
            raw_exports.append((i, cls_ref, super_ref, obj, offset, size))

        def ref_name(ref):
            """An object reference: positive is an export, negative an import."""
            if ref > 0:
                idx = ref - 1
                return (self._name(raw_exports[idx][3])
                        if idx < len(raw_exports) else "")
            if ref < 0:
                idx = -ref - 1
                return imports[idx] if idx < len(imports) else ""
            return ""

        for i, cls_ref, super_ref, obj, offset, size in raw_exports:
            e = Export(i, self._name(obj), ref_name(cls_ref),
                       ref_name(super_ref), offset, size, cls_ref == 0)
            self.exports.append(e)
            self._by_name.setdefault(e.name, e)

    def _name(self, index):
        return self.names[index] if 0 <= index < len(self.names) else ""

    def classes(self):
        """Every exported class."""
        return [e for e in self.exports if e.is_class]

    def export(self, name):
        return self._by_name.get(name)

    # -- the class header --------------------------------------------------

    def _struct_prologue(self, export):
        """Position just past `export`'s `UStruct` header, before `Line`.

        A `Class` begins at `SuperField`. **Everything else does not.**
        `UObject::Serialize` writes a tagged property list for every object
        whose class is not `UClass`, and `UClass` is the engine's one
        exception -- so a Function, State or Struct export carries a list
        first. For those three it is always empty, which is a single `None`
        byte, and `None` is name 0 in every one of these packages.

        A reader that skips it therefore does not crash. It takes that zero
        for `SuperField`, shifts the whole header one index along, and reads
        `FriendlyName` out of `Children` -- which is the whole danger: the
        result is plausible rather than absurd.

        Measured across all 23 of Raven Shield's script packages, with the
        list consumed: `FriendlyName` resolves to a real name for all 1,975
        class exports and all 9,107 function, state and struct exports. 9,002
        of the latter name the export itself; the remaining 105 are operators,
        whose friendly name is the token -- `DivideEqual_VectorFloat` is `/=`,
        and the named ones are `Dot`, `Cross` and `ClockwiseFrom`.

        Non-field objects -- a Sound, a Texture -- carry a real list here, so
        it is walked rather than assumed to be one byte.
        """
        d = self.data
        pos = export.offset
        if not export.is_class:
            pos = self._walk(pos, export.offset + export.size, "", [])
        for _ in range(5):     # SuperField Next ScriptText Children Friendly
            _v, pos = compact_index(d, pos)
        return pos

    def _defaults_start(self, export):
        """Where `export`'s default-property list begins.

        Raises for a class that still carries compiled script: `ScriptSize` is
        a memory length and the on-disk bytecode is shorter, so no arithmetic
        skips it.
        """
        d = self.data
        pos = self._struct_prologue(export)
        script_size = struct.unpack_from("<I", d, pos + 8)[0]
        if script_size:
            raise PackageError(
                "%s carries %d bytes of compiled script; its defaults cannot "
                "be located by arithmetic" % (export.name, script_size))
        pos += 12 + STATE_AND_CLASS_HEADER
        count, pos = compact_index(d, pos)                  # dependencies
        for _ in range(count):
            _v, pos = compact_index(d, pos)
            pos += 8                                        # deep + text CRC
        count, pos = compact_index(d, pos)                  # package imports
        for _ in range(count):
            _v, pos = compact_index(d, pos)
        _v, pos = compact_index(d, pos)                     # ClassWithin
        _v, pos = compact_index(d, pos)                     # ClassConfigName
        count, pos = compact_index(d, pos)                  # HideCategories
        for _ in range(count):
            _v, pos = compact_index(d, pos)
        return pos

    def _walk(self, start, end, prefix, out):
        """Read a tagged property list. Returns the position after its `None`."""
        d = self.data
        pos = start
        while True:
            if pos >= end:
                raise PackageError("property list ran past the end of the class")
            idx, pos = compact_index(d, pos)
            if not 0 <= idx < len(self.names):
                raise PackageError("property tag names index %d" % idx)
            name = self.names[idx]
            if name == "None":
                return pos
            if pos >= end:
                raise PackageError("property %s has no info byte" % name)
            info = d[pos]
            pos += 1
            ptype = info & 0x0F
            code = (info >> 4) & 0x07
            if ptype == 0 or ptype > T_FIXEDARRAY:
                raise PackageError("property %s has type %d" % (name, ptype))
            if ptype == T_STRUCT:
                _s, pos = compact_index(d, pos)             # struct's own name
            if code in SIZE_CODE:
                size = SIZE_CODE[code]
            elif code == 5:
                size = d[pos]
                pos += 1
            elif code == 6:
                size = struct.unpack_from("<H", d, pos)[0]
                pos += 2
            else:
                size = struct.unpack_from("<I", d, pos)[0]
                pos += 4
            index = 0
            if ptype != T_BOOL and (info & 0x80):
                index, pos = array_index(d, pos)
            value_at = pos
            pos += size
            if pos > end:
                raise PackageError("property %s overruns the class" % name)
            path = prefix + name
            if index:
                path = "%s[%d]" % (path, index)
            out.append(Prop(name, path, ptype, info,
                            value_at - 1 if ptype == T_BOOL else value_at,
                            0 if ptype == T_BOOL else size, index))
            if ptype == T_STRUCT and size:
                try:
                    self._walk(value_at, value_at + size, path + ".", out)
                except PackageError:
                    # Not every struct is a nested property list -- a vector
                    # is three bare floats. Leaving it whole is correct.
                    pass
            elif ptype == T_ARRAY and size:
                self._array_elements(path, value_at, size, out)

    def _array_elements(self, path, value_at, size, out):
        """Expose an array's elements as `name[0]`, `name[1]`, ...

        An array's value is a count followed by the elements, and the element
        TYPE is not in the tag -- it lives on the property's `Inner`, which is
        a separate export. Rather than chase that, the width is derived from
        the count, and only a four-byte width is exposed, read as int32.

        That inference is narrow on purpose. The only arrays this tool writes
        are the five percentage bars in `R6Description.u`, which really are
        int32, and the test suite checks all 700 of their elements against
        independently-derived values. A four-byte FLOAT array would be
        misread, so nothing here offers to write one.
        """
        count, after = compact_index(self.data, value_at)
        body = size - (after - value_at)
        if count <= 0 or body != 4 * count:
            return
        for i in range(count):
            at = after + 4 * i
            out.append(Prop("%s[%d]" % (path.rsplit(".", 1)[-1], i),
                            "%s[%d]" % (path, i), T_INT, INFO_ARRAY_INT,
                            at, 4, i))

    def defaults(self, class_name):
        """Every default property of one class, keyed by path. Cached."""
        cached = self._defaults.get(class_name)
        if cached is not None:
            if isinstance(cached, PackageError):
                raise cached
            return cached
        export = self._by_name.get(class_name)
        if export is None or export.size <= 0 or not export.is_class:
            raise PackageError("no class %r in %s" % (class_name, self.path))
        end = export.offset + export.size
        try:
            start = self._defaults_start(export)
            found = []
            stop = self._walk(start, end, "", found)
            if stop != end:
                raise PackageError(
                    "%s: property list ends at 0x%x, class ends at 0x%x"
                    % (class_name, stop, end))
        except PackageError as exc:
            self._defaults[class_name] = exc
            raise
        except (IndexError, struct.error) as exc:
            wrapped = PackageError("%s: %s" % (class_name, exc))
            self._defaults[class_name] = wrapped
            raise wrapped
        table = {}
        for prop in found:
            table.setdefault(prop.path, prop)
            table.setdefault(prop.name, prop)   # unqualified; outermost wins
        self._defaults[class_name] = table
        return table

    # -- reading and writing values ---------------------------------------

    def find_property(self, class_name, prop, kind="any"):
        """The `Prop` for one property of one class, or None.

        `kind` is checked rather than used to search, so asking for the wrong
        type gets nothing back instead of getting the wrong bytes.
        """
        try:
            table = self.defaults(class_name)
        except PackageError:
            return None
        found = table.get(prop)
        if found is None:
            return None
        if kind != "any" and found.kind != kind:
            return None
        return found

    def get(self, class_name, prop, kind="any"):
        found = self.find_property(class_name, prop, kind)
        if found is None:
            return None
        if found.type == T_BOOL:
            return bool(self.data[found.offset] & 0x80)
        if found.type == T_INT:
            return struct.unpack_from("<i", self.data, found.offset)[0]
        if found.type == T_FLOAT:
            return struct.unpack_from("<f", self.data, found.offset)[0]
        if found.type == T_BYTE:
            return self.data[found.offset]
        return None

    def object_name(self, class_name, prop):
        """What an ObjectProperty points AT, by name, or None.

        The value is a compact index into the reference space the export table
        uses -- positive is an export in this package, negative an import from
        another. Needed because a weapon does not name its ammunition as text:
        `m_pBulletClass` is a pointer, and following it is the only way to
        learn which round the AI actually fires.
        """
        found = self.find_property(class_name, prop, "object")
        if found is None:
            return None
        ref, _next = compact_index(self.data, found.offset)
        return self._ref_name(ref)

    def _ref_name(self, ref):
        if ref > 0:
            idx = ref - 1
            return self.exports[idx].name if idx < len(self.exports) else None
        if ref < 0:
            idx = -ref - 1
            return self.imports[idx] if idx < len(self.imports) else None
        return None

    def set(self, class_name, prop, value, kind="any") -> bool:
        """Overwrite a value in place. False if the property is not authored.

        Equal width always: four bytes for an int or a float, one byte for a
        byte, and a bool is a single bit inside a tag byte that already exists.
        Nothing here can change the length of the file, which is what keeps the
        export table valid.
        """
        found = self.find_property(class_name, prop, kind)
        if found is None:
            return False
        if found.type == T_BOOL:
            self.data[found.offset] = (self.data[found.offset] & 0x7F) \
                | (0x80 if value else 0)
            return True
        if found.type == T_INT:
            struct.pack_into(
                "<i", self.data, found.offset,
                max(-2147483648, min(2147483647, int(round(value)))))
            return True
        if found.type == T_FLOAT:
            struct.pack_into("<f", self.data, found.offset, float(value))
            return True
        if found.type == T_BYTE:
            self.data[found.offset] = max(0, min(255, int(round(value))))
            return True
        return False

"""Read Unreal object names, classes and owners out of a PCSX2 savestate.

This is the piece that was missing. The packages on the disc carry complete
name, import and export tables, but their export *data* is not in the file --
`COMMON.LIN`'s export table ends exactly where the next package's signature
begins, and the one package examined needs 2,321,838 bytes of data that are
simply not there. So a property's offset, its bitmask, and the class that
declares it cannot be recovered from the disc.

They can be read straight out of a running game. On this build a `UObject` in
memory is laid out, relative to the object's start:

    +0x00  vtable
    +0x18  Outer      -- for a property, the class that declares it
    +0x1c  ObjectFlags
    +0x24  Class
    +0x28  Name       -- a direct `char *`, not an FName index

That last one is the reason this is easy: the PS2 build stores object names as
plain pointers to NUL-terminated strings, so finding the string and finding
the single pointer to it finds the object.

`UProperty` adds a byte offset within the owning object and, for booleans, a
bitmask; both were read back as powers of two on every bool checked.

What this was built for
-----------------------

Rainbow Six 3's equipment wheel. The investigation had been resting on a
property called `m_bUseWheel`, and this module is what showed that it belongs
to `R6IORotatingDoor` -- the handwheel on a valve door, next to
`m_bIsDoorLocked` and `m_LockPickSound` -- and has nothing to do with
equipment. The real class is `R6InteractionRoseDesVents`.

Usage::

    mem = load(r"...\\SLUS-20883 (21CC1EC3).03.p2s")
    obj = find(mem, "m_bUseWheel")
    print(name(mem, obj), kind(mem, obj), owner(mem, obj))
    -> m_bUseWheel BoolProperty R6IORotatingDoor
"""

from __future__ import annotations

import zipfile

import numpy as np

#: field offsets from an object's start
O_OUTER = 0x18
O_FLAGS = 0x1C
O_CLASS = 0x24
O_NAME = 0x28

#: the EE address range a real pointer falls in
LO, HI = 0x00100000, 0x02000000


class Memory:
    """One savestate's EE RAM, with the two views both needed."""

    def __init__(self, blob: bytes):
        self.b = blob
        self.w = np.frombuffer(blob, dtype=np.uint32)

    def word(self, va: int) -> int:
        return int(self.w[va >> 2])

    def string(self, va: int):
        """The NUL-terminated string at `va`, or None if that is not one."""
        if not LO <= va < HI:
            return None
        try:
            end = self.b.index(b"\x00", va)
        except ValueError:
            return None
        raw = self.b[va:end]
        if not 0 < len(raw) < 64 or not all(32 <= c < 127 for c in raw):
            return None
        return raw.decode("latin-1")


def load(path: str) -> Memory:
    """The EE memory out of a `.p2s`."""
    with zipfile.ZipFile(path) as z:
        return Memory(z.read("eeMemory.bin"))


def name(mem: Memory, obj: int):
    return mem.string(mem.word(obj + O_NAME))


def kind(mem: Memory, obj: int):
    """The name of this object's class, e.g. `BoolProperty` or `Class`."""
    cls = mem.word(obj + O_CLASS)
    return name(mem, cls) if LO <= cls < HI else None


def owner(mem: Memory, obj: int):
    """The name of this object's Outer -- for a property, its class."""
    out = mem.word(obj + O_OUTER)
    return name(mem, out) if LO <= out < HI else None


def find(mem: Memory, wanted: str, want_kind=None):
    """The object called `wanted`, or None.

    The name string is found first, then the pointer to it; an object whose
    `Name` reads back as the string asked for is the object. `want_kind`
    disambiguates when a name is used by more than one object -- passing
    "Class" is how you get the class rather than a property of the same name.
    """
    probe = wanted.encode("latin-1") + b"\x00"
    at = mem.b.find(probe)
    while at >= 0:
        for slot in np.flatnonzero(mem.w == at):
            obj = int(slot) * 4 - O_NAME
            if obj < 0 or name(mem, obj) != wanted:
                continue
            if want_kind is None or kind(mem, obj) == want_kind:
                return obj
        at = mem.b.find(probe, at + 1)
    return None


def members(mem: Memory, cls: int):
    """[(name, kind)] for everything whose Outer is this class."""
    out = []
    for slot in np.flatnonzero(mem.w == cls):
        obj = int(slot) * 4 - O_OUTER
        if obj < 0:
            continue
        nm, kd = name(mem, obj), kind(mem, obj)
        if nm and kd:
            out.append((nm, kd))
    return out


def instances(mem: Memory, cls: int):
    """Every live object whose Class is this class.

    Counting these is how the wheel investigation showed that
    `R6InteractionRoseDesVents` is created on demand: zero instances in both a
    split-screen and a single-player state, while
    `R6InteractionCircumstantialAction` -- the control -- had one per player.
    """
    out = []
    for slot in np.flatnonzero(mem.w == cls):
        obj = int(slot) * 4 - O_CLASS
        if obj >= 0 and name(mem, obj):
            out.append(obj)
    return out


def sweep(mem: Memory, pattern: str):
    """[(name, kind, owner)] for every object whose name matches a regex.

    This is the one that found the wheel: sweeping for `Wheel|Gadget|Equip`
    turned up `R6InteractionRoseDesVents` and, at the same time, proved
    `m_bUseWheel` belonged to a door.
    """
    import re
    rx = re.compile(pattern)
    word = re.compile(rb"[A-Za-z_][A-Za-z0-9_]{4,48}\x00")
    wanted = {m.start(): m.group()[:-1].decode("latin-1")
              for m in word.finditer(mem.b)
              if rx.search(m.group()[:-1].decode("latin-1"))}
    if not wanted:
        return []
    addrs = np.array(sorted(wanted), dtype=np.uint32)
    seen = {}
    for slot in np.flatnonzero(np.isin(mem.w, addrs)):
        obj = int(slot) * 4 - O_NAME
        if obj < 0:
            continue
        nm, kd = name(mem, obj), kind(mem, obj)
        if nm and kd:
            seen[(nm, kd, owner(mem, obj))] = True
    return sorted(seen)

"""The Red Storm / Ubisoft PS2 read-only filesystem.

The same container is used by Rainbow Six 3's `VOKES0/1/2.IMG` and by Ghost
Recon / Ghost Recon Jungle Storm's `GR.IMG` and `MENU.IMG`.

64-byte header of u32:

    [0] total file size          [3] entry-table end
    [1] (count-ish, unused)      [4] name-table offset
    [2] entry-table offset       [5] data start

then 48-byte records, all u32:

    +0x00 nameOffset   +0x04 next      +0x08 parent   +0x0c firstChild
    +0x10 ?            +0x14 isFile    +0x18 size     +0x1c size2
    +0x20 dataOffset   +0x24..0x2c ?

THE TRAP, and it is a costly one: `next` at +0x04 is **not** a sibling pointer.
It is the link of a single globally name-sorted list spanning every record in
the archive. Walking it from record 1 silently drops everything that sorts
before record 1's name -- on the Rainbow Six 3 disc that hid 200 MB of content
including three complete missions. Always enumerate the record array and build
each path by climbing the `parent` chain, which is what this module does.
"""

from __future__ import annotations

import struct

#: record sizes seen in the wild, tried in this order. Rainbow Six 3, Ghost
#: Recon and Jungle Storm use 48-byte records; Sum of All Fears uses 40, with
#: the same fields up to +0x24 and one trailing unknown word instead of three.
REC_SIZES = (48, 40)
REC = 48


class VokesError(Exception):
    pass


class Region:
    """A vokes archive addressed relative to its own byte 0.

    Backed either by a loose file or by a byte range inside an ISO, so the same
    code patches a disc image and an extracted folder.
    """

    def __init__(self, fh, base, name, owns=False):
        self.fh, self.base, self.name, self._owns = fh, base, name, owns

    @classmethod
    def from_file(cls, path, writable=False):
        fh = open(path, "r+b" if writable else "rb")
        import os
        return cls(fh, 0, os.path.basename(str(path)), owns=True)

    @classmethod
    def from_iso(cls, iso, entry):
        return IsoRegion(iso, entry.lba * 2048, entry.path.lstrip("/"))

    def read(self, off, n):
        self.fh.seek(self.base + off)
        return self.fh.read(n)

    def write(self, off, data):
        self.fh.seek(self.base + off)
        self.fh.write(data)

    def close(self):
        if self._owns:
            self.fh.close()


class IsoRegion(Region):
    """A region addressed through an ISO's logical view.

    Needed because a 2,352-byte CD image is not a flat stream -- the archive's
    own offsets are logical, and only the ISO knows how to reach them.
    """

    def __init__(self, iso, base, name):
        super().__init__(iso.fh, base, name)
        self.iso = iso

    def read(self, off, n):
        return self.iso.read_logical(self.base + off, n)

    def write(self, off, data):
        self.iso.write_logical(self.base + off, data)


class Entry:
    __slots__ = ("index", "path", "size", "offset")

    def __init__(self, index, path, size, offset):
        self.index, self.path, self.size, self.offset = index, path, size, offset

    def __repr__(self):
        return "Entry(%s, size=%d, offset=0x%x)" % (self.path, self.size, self.offset)


class Vokes:
    def __init__(self, region: Region, rec_size=None):
        self.r = region
        h = struct.unpack("<16I", region.read(0, 64))
        self.filesize = h[0]
        self.ent_off, self.ent_end, self.name_off, self.data_off = h[2], h[3], h[4], h[5]
        self.data_start = h[5]
        if self.ent_off != 0x800 or self.ent_end <= self.ent_off:
            raise VokesError("%s: not a vokes archive (table at 0x%x..0x%x)"
                             % (region.name, self.ent_off, self.ent_end))
        span = self.ent_end - self.ent_off
        self.ent = bytearray(region.read(self.ent_off, span))
        self.names = region.read(self.name_off, self.data_off - self.name_off)
        self.rec_size = rec_size or self._guess_rec_size(span)
        self.count = span // self.rec_size
        self.files: dict[str, Entry] = {}
        self._build()

    def _guess_rec_size(self, span):
        """Pick the record size that divides the table and yields real files.

        Both candidates share their first 0x24 bytes, so the test is simply
        whether the entries that claim to be files point at plausible data.
        """
        best = None
        for size in REC_SIZES:
            if span % size:
                continue
            n = span // size
            good = 0
            for i in range(1, min(n, 64)):
                r = struct.unpack_from("<%dI" % (size // 4), self.ent, i * size)
                is_file, length, off = r[5], r[6], r[8]
                if is_file == 1 and 0 < length and                         self.data_start <= off <= self.filesize:
                    good += 1
            if best is None or good > best[0]:
                best = (good, size)
        if best is None or best[0] == 0:
            raise VokesError("%s: entry table %d bytes fits no known record size"
                             % (self.r.name, span))
        return best[1]

    # -- records -----------------------------------------------------------
    def rec(self, i):
        n = self.rec_size // 4
        return struct.unpack_from("<%dI" % n, self.ent, i * self.rec_size)

    def _name(self, off):
        end = self.names.find(b"\0", off)
        return self.names[off:end if end >= 0 else None].decode("latin1")

    def _path(self, i):
        parts, seen = [], set()
        while i and i not in seen:
            seen.add(i)
            r = self.rec(i)
            parts.append(self._name(r[0]))
            i = r[2]
        return "/" + "/".join(reversed(parts))

    def _build(self):
        for i in range(self.count):
            r = self.rec(i)
            if r[5] == 1 and r[6]:
                self.files[self._path(i).upper()] = Entry(i, self._path(i), r[6], r[8])

    # -- data --------------------------------------------------------------
    def read_file(self, path) -> bytes:
        e = self.files[path.upper()]
        return self.r.read(e.offset, e.size)

    def read_entry(self, e: Entry) -> bytes:
        return self.r.read(e.offset, e.size)

    # -- writing -----------------------------------------------------------
    ALIGN = 16

    def _set_entry(self, e, offset, size, raw_size=None):
        """Rewrite one record's size, second size and data offset.

        The two size fields are equal in Rainbow Six 3 and the two Ghost Recons.
        Sum of All Fears uses the second as the DECOMPRESSED length of a
        per-entry-compressed file, so it is only overwritten when the caller
        says what the new decompressed length is, or when the pair was equal to
        begin with.
        """
        base = e.index * self.rec_size
        old_size, old_raw = self.rec(e.index)[6], self.rec(e.index)[7]
        second = raw_size if raw_size is not None else (
            size if old_size == old_raw else old_raw)
        struct.pack_into("<I", self.ent, base + 0x18, size)
        struct.pack_into("<I", self.ent, base + 0x1C, second)
        struct.pack_into("<I", self.ent, base + 0x20, offset)
        self.r.write(self.ent_off + base + 0x18, struct.pack("<II", size, second))
        self.r.write(self.ent_off + base + 0x20, struct.pack("<I", offset))
        e.offset, e.size = offset, size

    def _live_extents(self, exclude=None):
        out = []
        for e in self.files.values():
            if e is exclude:
                continue
            out.append((e.offset, e.offset + e.size))
        out.sort()
        return out

    def free_blocks(self, exclude=None):
        """Byte ranges inside the archive that no file entry covers.

        Includes everything after the last file, which every one of these
        archives pads with 64 KB of zeros. It does NOT assume an uncovered
        range is usable -- see `_is_blank`. Ghost Recon's GR.IMG carries a 6 MiB
        hole that no entry points at and which is full of real data, so
        "nothing references it" is not the same as "it is free".
        """
        blocks = []
        cursor = self.data_start
        for start, end in self._live_extents(exclude):
            if start > cursor:
                blocks.append((cursor, start - cursor))
            cursor = max(cursor, end)
        if cursor < self.filesize:
            blocks.append((cursor, self.filesize - cursor))
        return blocks

    def _is_blank(self, offset, length, budget=1 << 24):
        if length > budget:
            return False
        step = 1 << 16
        for o in range(offset, offset + length, step):
            chunk = self.r.read(o, min(step, offset + length - o))
            if chunk.strip(b"\x00"):
                return False
        return True

    def send_home(self, e, data, home):
        """Try to put one relocated file back. True if it moved.

        Public because the caller has something this class does not: the list
        of every file about to be written, and therefore the ability to try
        them all again after one of them moves. A single attempt is not
        enough on a disc that has been patched a few times -- the exiles end
        up interlocked, each one sitting in another's slot, and every
        individual attempt fails on "someone else lives there now" even
        though the whole set could unwind.
        """
        return self._go_home(e, data, home)

    def room_for(self, e, home=None):
        """How long a file may be and still not have to move.

        Its own slot, plus any blank run behind it, plus whatever alignment
        gave it -- and its original slot too, when it has been relocated by an
        earlier edit and could go back. This is the number an edit has to hit
        to leave the archive's layout alone, which on these discs matters more
        than it looks: there is one 64 KB pad and nothing else big enough, so a
        handful of relocations exhaust it and every later one fails outright.
        """
        room = e.size + self._tail_room(e) + self._align_slack(e)
        if home:
            room = max(room, home[1])
        return room

    def allocate(self, size, exclude=None, near=None):
        """Offset of a 16-byte-aligned, provably empty run of `size` bytes.

        Best fit, so a relocated file lands in the slot a previous relocation
        vacated instead of eating the 64 KB pad at the end of the archive.
        Every candidate is read and required to be all zeros first: an
        unreferenced range is not necessarily an unused one.

        `near` asks for the closest such run to a byte offset rather than the
        tightest one anywhere. These archives ship in three redundant copies to
        keep DVD seeks short, so where a file lands is a load-time cost, not
        bookkeeping: the pad at the end of a 2.6 GB image is a very long seek
        from everything a level reads alongside it.
        """
        candidates = []
        for start, length in self.free_blocks(exclude):
            aligned = (start + self.ALIGN - 1) & ~(self.ALIGN - 1)
            usable = length - (aligned - start)
            if usable >= size:
                candidates.append((usable, aligned))
        if not candidates:
            raise VokesError("%s has no free run of %d bytes left"
                             % (self.r.name, size))
        if near is not None:
            candidates.sort(key=lambda c: (abs(c[1] - near), c[0]))
        else:
            candidates.sort()
        for _usable, offset in candidates:
            if self._is_blank(offset, size):
                return offset
        raise VokesError("%s: every free run big enough for %d bytes holds data "
                         "no file claims -- refusing to write over it"
                         % (self.r.name, size))

    def _tail_room(self, e):
        """Blank bytes sitting immediately after a file, that it may grow into.

        Only counts a run that starts exactly where the file ends, is claimed by
        no other entry, and is verified to be all zeros -- the same standard
        `allocate` holds free space to. Anything else and the file relocates.
        """
        end = e.offset + e.size
        for start, length in self.free_blocks(exclude=e):
            # `exclude` makes the file's own extent free too, so the block that
            # covers it starts at or before the file and runs past its end.
            if start <= end < start + length:
                room = start + length - end
                if room and self._is_blank(end, room):
                    return room
                return 0
        return 0

    def _go_home(self, e, data, home):
        """Put a previously relocated file back at `home` = (offset, size).

        A file only has to move when an edit makes it bigger than its slot, and
        one byte is enough to do it. What it must not do is STAY moved: every
        later edit is built from the same stored original, so the very next one
        that happens to fit would otherwise be written wherever the first
        overflow happened to land. On Rainbow Six 3 that is R6GAMESETTINGS.INI,
        read at every level load, exiled up to a gigabyte from the rest of the
        files read with it -- which shows up as slow loading and nothing else,
        because once a level is up the file is not read again.

        Home is only offered when nothing else has claimed it in the meantime.
        """
        off, size = home
        if off < self.data_start or len(data) > size or e.offset == off:
            return False
        for other in self.files.values():
            if other is e and other.offset == e.offset:
                continue
            if other.offset < off + size and off < other.offset + other.size:
                return False                  # someone else lives there now
        old_off, old_size = e.offset, e.size
        self.r.write(off, data)
        if len(data) < size:
            self.r.write(off + len(data), b"\x00" * (size - len(data)))
        self._set_entry(e, off, len(data))
        self.r.write(old_off, b"\x00" * old_size)
        return True

    def _align_slack(self, e):
        """The packer's own 16-byte padding after a file, which it may use.

        `_tail_room` will not touch a run that is not all zeros, and it is right
        not to: an unreferenced range is not necessarily an unused one, and one
        of these archives carries megabytes of real data no entry points at.
        But the few bytes between a file's end and the START OF THE NEXT FILE
        are a different thing -- they exist only because the next file is
        16-byte aligned, and nothing can reach them. Refusing them costs far
        more than it saves: on Rainbow Six 3 a ONE BYTE growth of
        R6GAMESETTINGS.INI was enough to exile it to the pad at the end of the
        archive, a gigabyte from everything read with it at level load.

        Capped below ALIGN so this can only ever be alignment padding, never a
        gap left by a file that is simply missing.
        """
        end = e.offset + e.size
        nxt = min((o.offset for o in self.files.values()
                   if o is not e and o.offset >= end), default=self.filesize)
        gap = nxt - end
        return gap if 0 < gap < self.ALIGN else 0

    def write(self, path, data, raw_size=None, home=None):
        """Replace a file, relocating it if it has outgrown its slot.

        Small enough, and it goes back where it was. Too big, and it moves to
        free space and its old slot is zeroed, which both makes the change
        reversible and puts that run back in the pool for the next file.

        `home` is the (offset, size) the file shipped at. When it is given and
        the file has been relocated by an earlier edit, it goes back there if it
        fits and nothing else has taken the space -- see `_go_home`.
        """
        e = self.files[path.upper()]
        if home and self._go_home(e, data, home):
            return e.offset
        if e.offset < self.data_start:
            # A handful of records point at offset 0 with a byte or two of
            # length -- stubs for files the tree lists but the archive does not
            # actually store. They own no slot, so there is nothing to replace.
            raise VokesError("%s: %s is a stub record (offset 0x%x is before "
                             "the data area) and cannot be replaced"
                             % (self.r.name, e.path, e.offset))
        if len(data) <= e.size + self._tail_room(e) + self._align_slack(e):
            # Fits where it already is -- possibly by growing back into slack it
            # gave up earlier. A file that SHRINKS has its recorded extent
            # shrunk with it, so the rest of its original slot stops being
            # claimed by anything; without this, an edit one byte larger than
            # the shrunken size would relocate a file that still fits its own
            # slot perfectly well. That is not a cosmetic difference: these
            # archives exist in three redundant copies to keep seeks short, and
            # a file exiled to the pad at the end of a 2.6 GB image is a very
            # long seek away from everything read alongside it.
            self.r.write(e.offset, data)
            if len(data) < e.size:
                self.r.write(e.offset + len(data), b"\x00" * (e.size - len(data)))
            self._set_entry(e, e.offset, len(data))
            return e.offset
        old_off, old_size = e.offset, e.size
        dest = self.allocate(len(data), exclude=e,
                             near=home[0] if home else e.offset)
        self.r.write(dest, data)
        self._set_entry(e, dest, len(data), raw_size)
        # Release the old run -- but only the part of it the new one does not
        # occupy. The allocator is allowed to grow a file into its own slot plus
        # the gap next to it, and blindly zeroing the old range would then wipe
        # the bytes just written.
        new_a, new_b = dest, dest + len(data)
        for a, b in ((old_off, min(old_off + old_size, new_a)),
                     (max(old_off, new_b), old_off + old_size)):
            if b > a:
                self.r.write(a, b"\x00" * (b - a))
        return dest

    def replace(self, path, data):
        """Backwards-compatible name for `write`."""
        return self.write(path, data)


def open_archives(iso, pattern=r"/(VOKES\d|GR|MENU)\.IMG$") -> list:
    """Every vokes archive in an ISO, in disc order."""
    out = []
    for ent in iso.find_all(pattern):
        if ent.is_dir:
            continue
        try:
            out.append(Vokes(Region.from_iso(iso, ent)))
        except VokesError:
            continue
    return out

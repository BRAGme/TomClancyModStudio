"""Rainbow Six Lockdown's `PS2DATA` archive -- the Nimitz engine's cooked data.

Lockdown does not use the vokes archive the other six discs share. It ships one
logical 3.94 GB stream split across four ISO files -- `PS2DATA.PAK`, `.PA1`,
`.PA2`, `.PA3` -- with **no header of its own**. The index is a separate file,
`PS2DATA.BIN`, which is what makes the whole thing readable:

    u32 len + "C:/develop/Nimitz/NimitzPS2/Nimitz/Release/"
    u32 len + "ps2data/"
    u32 nDir            ; nDir  x (u32 len + name)
    u32 nFile   = 4671  ; nFile x (u8 dirIndex, u32 len, name)
    u32 nFile+1
    u32 sizes[nFile]
    u32 0 ; u32 nFile+1
    u32 offsets[nFile+1]
    u32 1               ; trailer

That parse consumes all 150,048 bytes with nothing left over, which is the
check that it is right rather than merely plausible.

`offsets` restarts at zero three times -- at entries 4289, 4434 and 4562 -- and
those are the volume boundaries, in `.PAK .PA1 .PA2 .PA3` order. The last entry
is a sentinel equal to the final volume's size. A file's size is the difference
between consecutive offsets; the `sizes` array agrees for every ordinary file
but sets bit 31 on streamed video, so the offsets are the authority.

`ZCDPADD.INN` is a byte-identical duplicate of `PS2DATA.BIN`, and `PS2DATA.BHS`
carries the same offset table keyed by file extension. **None of the three holds
a content hash**, so an edit that keeps a file's length needs no index fixing at
all -- which is the only kind of edit this module allows.

The class deliberately mimics `vokes.Vokes` closely enough that `dataedit` can
drive it unchanged: same `files` mapping, same `read_entry`, same `write`.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

VOLUMES = ("PS2DATA.PAK", "PS2DATA.PA1", "PS2DATA.PA2", "PS2DATA.PA3")
INDEX = r"/PS2DATA\.BIN$"


class NimitzError(Exception):
    pass


@dataclass
class Entry:
    path: str          # "/PS2DATA/BINARY/NIMITZ.GUNS"
    name: str          # "nimitz.guns"
    directory: str     # "ps2data/binary/"
    volume: int        # index into VOLUMES
    offset: int        # byte offset inside that volume
    size: int


class _Region:
    """Stands in for vokes' region object: dataedit only asks for `.name`."""

    def __init__(self, name):
        self.name = name


def _reader(blob):
    pos = [0]

    def u32():
        v = struct.unpack_from("<I", blob, pos[0])[0]
        pos[0] += 4
        return v

    def pstr():
        n = u32()
        s = blob[pos[0]:pos[0] + n]
        pos[0] += n
        return s.decode("latin1")

    return u32, pstr, pos


def parse_index(blob: bytes):
    """(root, entries) with offsets, sizes and volumes resolved."""
    u32, pstr, pos = _reader(blob)
    root = pstr()
    pstr()                                        # "ps2data/"
    dirs = [pstr() for _ in range(u32())]

    n_file = u32()
    names = []
    for _ in range(n_file):
        d = blob[pos[0]]
        pos[0] += 1
        names.append((d, pstr()))

    guard = u32()
    if guard != n_file + 1:
        raise NimitzError("index guard is %d, expected %d" % (guard, n_file + 1))
    sizes = list(struct.unpack_from("<%dI" % n_file, blob, pos[0]))
    pos[0] += 4 * n_file
    u32()                                         # padding
    n_off = u32()
    offsets = list(struct.unpack_from("<%dI" % n_off, blob, pos[0]))
    pos[0] += 4 * n_off
    u32()                                         # trailer
    if pos[0] != len(blob):
        raise NimitzError("index parse consumed %d of %d bytes"
                          % (pos[0], len(blob)))

    # the offset stream restarts once per volume
    resets = [i for i in range(1, len(offsets)) if offsets[i] < offsets[i - 1]]
    bounds = [0] + resets + [n_file]
    if len(bounds) - 1 > len(VOLUMES):
        raise NimitzError("index names %d volumes, only %d are known"
                          % (len(bounds) - 1, len(VOLUMES)))

    entries = []
    for vol in range(len(bounds) - 1):
        lo, hi = bounds[vol], bounds[vol + 1]
        for i in range(lo, hi):
            d, name = names[i]
            nxt = offsets[i + 1] if i + 1 < hi else None
            size = (nxt - offsets[i]) if nxt is not None else (sizes[i] & 0x7FFFFFFF)
            directory = dirs[d] if d < len(dirs) else ""
            entries.append(Entry(path=("/" + directory + name).upper(),
                                 name=name, directory=directory, volume=vol,
                                 offset=offsets[i], size=size))
    return root, entries


class NimitzPak:
    """Read/write access to the four-volume archive, keyed like a vokes one."""

    def __init__(self, iso):
        self.iso = iso
        ent = iso.find(INDEX)
        if ent is None:
            raise NimitzError("PS2DATA.BIN is not on this disc")
        self.root, entries = parse_index(iso.read(ent.lba, ent.size))
        self.files = {e.path: e for e in entries}
        self.r = _Region("PS2DATA")
        self.data_start = 0
        self._vol = {}
        for i, name in enumerate(VOLUMES):
            v = iso.find("/" + name.replace(".", r"\.") + "$")
            if v is not None:
                self._vol[i] = v

    # -- the interface dataedit drives -----------------------------------
    def read_entry(self, e: Entry) -> bytes:
        vol = self._vol.get(e.volume)
        if vol is None:
            raise NimitzError("%s lives in %s, which is not on the disc"
                              % (e.name, VOLUMES[e.volume]))
        base = vol.lba * 2048 + e.offset
        lba, skew = divmod(base, 2048)
        return self.iso.read(lba, e.size + skew)[skew:skew + e.size]

    def read_file(self, path) -> bytes:
        return self.read_entry(self.files[path.upper()])

    def write(self, path, data: bytes):
        """In place, same length only.

        The index carries no hash but it does carry sizes and offsets, and this
        module will not rebuild it -- so a file that changed length would have
        to move, and everything after it with it. Refusing is the whole safety
        model here.
        """
        e = self.files[path.upper()]
        if len(data) != e.size:
            raise NimitzError(
                "%s is %d bytes; refusing to write %d. This archive is only "
                "edited in place." % (e.name, e.size, len(data)))
        vol = self._vol.get(e.volume)
        if vol is None:
            raise NimitzError("%s is not on the disc" % VOLUMES[e.volume])
        # write_logical takes a BYTE offset; iso.write takes an LBA. Using the
        # wrong one here would land the edit 2048 times further into a 4 GB
        # image than intended.
        self.iso.write_logical(vol.lba * 2048 + e.offset, data)

    def _set_entry(self, *_a, **_k):              # vokes relocates; we never do
        raise NimitzError("the Nimitz archive is never relocated")


def open_pak(iso):
    """[NimitzPak] -- a list, so it matches `vokes.open_archives`."""
    try:
        return [NimitzPak(iso)]
    except NimitzError:
        return []

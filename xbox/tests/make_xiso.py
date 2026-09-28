"""Build a tiny XDVDFS image, so the ISO writer can be tested without a disc.

The real images on a shelf are 700 MB to 4 GB. Copying one to test a write is
not a test anyone will run, so the risky half -- growing a file into its sector
padding and rewriting the directory entry's size -- is exercised against an
image built here instead, one small enough to live in a temp folder and be
compared byte for byte.

This writes the simplest legal thing the reader will accept: a volume
descriptor, one directory of entries with no left or right children (a
degenerate tree, which is still a tree), and the files themselves each starting
on their own sector.
"""

from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tcxbox.xiso import DESCRIPTOR_SECTOR, MAGIC, SECTOR   # noqa: E402


def _pad(data, to=SECTOR):
    over = len(data) % to
    return data + (b"\0" * (to - over) if over else b"")


def build(path, files):
    """`files` is {name: bytes}. Returns the path written."""
    names = sorted(files)

    # Lay the directory out first so the entry offsets are known, then the
    # files after it, each on its own sector.
    #
    # The entries are chained through their RIGHT child rather than left flat.
    # A flat list is not a tree: the reader starts at the root node and follows
    # children, so a directory whose entries all say "no children" holds exactly
    # one file however many were written into it. Worth finding here rather than
    # on a disc.
    entries = bytearray()
    positions = []
    for name in names:
        raw = name.encode("latin1")
        positions.append(len(entries))
        entries += struct.pack("<HHIIBB", 0xFFFF, 0xFFFF, 0, 0, 0, len(raw))
        entries += raw
        while len(entries) % 4:
            entries += b"\0"
    for i in range(len(positions) - 1):
        struct.pack_into("<H", entries, positions[i] + 2, positions[i + 1] // 4)
    dir_size = len(entries)

    dir_sector = DESCRIPTOR_SECTOR + 1
    blob = bytearray()
    sector = dir_sector + (dir_size + SECTOR - 1) // SECTOR
    for i, name in enumerate(names):
        body = files[name]
        struct.pack_into("<II", entries, positions[i] + 4, sector, len(body))
        blob += _pad(body)
        sector += (len(body) + SECTOR - 1) // SECTOR

    descriptor = bytearray(b"\0" * SECTOR)
    descriptor[0:20] = MAGIC
    struct.pack_into("<II", descriptor, 0x14, dir_sector, dir_size)
    descriptor[0x7EC:0x7EC + 20] = MAGIC

    image = bytearray(b"\0" * (DESCRIPTOR_SECTOR * SECTOR))
    image += descriptor
    image += _pad(bytes(entries))
    image += blob

    with open(path, "wb") as fh:
        fh.write(image)
    return path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "tiny.iso"
    build(out, {"default.xbe": b"not really an xbe",
                "System/hello.ini": b"a=1\r\nb=2\r\n"})
    print("wrote %s (%d bytes)" % (out, os.path.getsize(out)))

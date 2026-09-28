"""Build a tiny synthetic PS2 disc image carrying a real SP.SOZ.

End-to-end tests need a writable ISO, and copying a 4 GB retail disc for every
test run is not reasonable. This produces a ~2 MB image with a valid enough
ISO9660 structure for the patcher: a primary volume descriptor, a root
directory, and the genuine overlay extent read out of the retail disc.
"""

from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tcps2.iso import Iso  # noqa: E402

SECTOR = 2048


def _both16(v):
    return struct.pack("<H", v) + struct.pack(">H", v)


def _both32(v):
    return struct.pack("<I", v) + struct.pack(">I", v)


def _dirrec(name, lba, size, is_dir):
    if name in ("\x00", "\x01"):
        raw = name.encode("latin1")
    else:
        raw = (name + ";1").encode("latin1") if not is_dir else name.encode("latin1")
    ln = 33 + len(raw)
    if ln % 2:
        ln += 1
    rec = bytearray(ln)
    rec[0] = ln
    rec[1] = 0
    rec[2:10] = _both32(lba)
    rec[10:18] = _both32(size)
    rec[18:25] = bytes([125, 1, 1, 0, 0, 0, 0])   # y2025-01-01 00:00:00 GMT
    rec[25] = 0x02 if is_dir else 0x00
    rec[26] = 0
    rec[27] = 0
    rec[28:32] = _both16(1)
    rec[32] = len(raw)
    rec[33:33 + len(raw)] = raw
    return bytes(rec)


def build(out_path, files):
    """files: list of (name, bytes). Everything is laid out sector-aligned."""
    root_lba = 18
    data_lba = 19
    placed, lba = [], data_lba
    for name, blob in files:
        placed.append((name, lba, len(blob), blob))
        lba += (len(blob) + SECTOR - 1) // SECTOR
    total = lba

    root = bytearray()
    root += _dirrec("\x00", root_lba, SECTOR, True)
    root += _dirrec("\x01", root_lba, SECTOR, True)
    for name, flba, size, _ in placed:
        root += _dirrec(name, flba, size, False)
    assert len(root) <= SECTOR, "fixture root directory must fit one sector"
    root += b"\0" * (SECTOR - len(root))

    pvd = bytearray(b"\0" * SECTOR)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    pvd[8:40] = b" " * 32
    pvd[40:72] = b"TCMS_FIXTURE".ljust(32)
    pvd[80:88] = _both32(total)
    pvd[120:124] = _both16(1)          # volume set size
    pvd[124:128] = _both16(1)          # volume sequence number
    pvd[128:132] = _both16(SECTOR)     # logical block size
    pvd[156:190] = _dirrec("\x00", root_lba, SECTOR, True)
    assert len(pvd) == SECTOR, "PVD must stay exactly one sector"

    term = bytearray(b"\0" * SECTOR)
    term[0] = 0xFF
    term[1:6] = b"CD001"
    term[6] = 1

    with open(out_path, "wb") as fh:
        fh.write(b"\0" * (16 * SECTOR))
        fh.write(pvd)
        fh.write(term)
        fh.write(root)
        for name, flba, size, blob in placed:
            fh.seek(flba * SECTOR)
            fh.write(blob)
        fh.seek(total * SECTOR - 1)
        fh.write(b"\0")
    return out_path


def from_retail(src_iso, out_path, patterns):
    files = []
    with Iso(src_iso) as iso:
        for pat in patterns:
            ent = iso.find(pat)
            if ent is None:
                raise SystemExit("%s not found in %s" % (pat, src_iso))
            files.append((os.path.basename(ent.path), iso.read(ent.lba, ent.size)))
    return build(out_path, files)


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    pats = sys.argv[3:] or [r"/SP\.SOZ$", r"/SLUS_208\.83$"]
    print(from_retail(src, dst, pats), os.path.getsize(dst), "bytes")

"""The original Xbox executable, read far enough to identify a game folder.

`default.xbe` is a PE with an Xbox header bolted on the front. Everything this
tool needs is in two structures:

  * the XBE header at file offset 0, which records the base address the image
    was linked for and where the certificate and section table live -- as
    *virtual* addresses, so every pointer has to have the base subtracted
    before it can be used as a file offset;

  * the certificate, which carries the 32-bit title id and the title name as
    40 UTF-16 characters. The title id is the thing worth keying a profile on:
    it is the same four bytes on every disc of a given game, it is what an
    emulator and the console's own dashboard identify a title by, and unlike a
    folder name nobody renames it.

Sections are exposed because a code patch has to be written at a file offset
and every address in a disassembly is a virtual one. Nothing in this build
writes code yet -- the Xbox games' moddable surface turned out to be almost
entirely data -- but `va_to_file` is what a future one would need, and it is
four lines.

Retail XBEs are not encrypted: only the certificate's signature covers the
image, and nothing verifies it -- not the emulators, and not a modded console.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

MAGIC = b"XBEH"


class XbeError(Exception):
    pass


@dataclass
class Section:
    name: str
    virtual_address: int
    virtual_size: int
    raw_address: int
    raw_size: int


@dataclass
class Xbe:
    path: str
    base: int
    title_id: int
    title_name: str
    sections: list

    @property
    def title_id_hex(self) -> str:
        return "%08X" % self.title_id

    @property
    def publisher(self) -> str:
        """The two ASCII letters the title id starts with -- "UB" for Ubisoft."""
        hi = (self.title_id >> 16) & 0xFFFF
        try:
            return bytes([hi & 0xFF, hi >> 8]).decode("ascii")
        except (UnicodeDecodeError, ValueError):
            return ""

    def va_to_file(self, va: int):
        """File offset for a virtual address, or None if it is in no section."""
        for s in self.sections:
            if s.virtual_address <= va < s.virtual_address + s.raw_size:
                return s.raw_address + (va - s.virtual_address)
        return None


def _cstring(data: bytes, off: int) -> str:
    end = data.find(b"\0", off)
    return data[off:end if end >= 0 else len(data)].decode("latin1")


def parse(data: bytes, path: str = "") -> Xbe:
    if data[:4] != MAGIC:
        raise XbeError("not an Xbe (no XBEH magic)")
    base, = struct.unpack_from("<I", data, 0x104)
    cert_va, = struct.unpack_from("<I", data, 0x118)
    n_sections, = struct.unpack_from("<I", data, 0x11C)
    sect_va, = struct.unpack_from("<I", data, 0x120)

    cert = cert_va - base
    if not 0 <= cert < len(data) - 0x5C:
        raise XbeError("the certificate pointer does not land inside the file")
    title_id, = struct.unpack_from("<I", data, cert + 0x08)
    raw_name = data[cert + 0x0C:cert + 0x0C + 80]
    title_name = raw_name.decode("utf-16-le", "replace").split("\0")[0].strip()

    sections = []
    off = sect_va - base
    for i in range(min(n_sections, 64)):
        o = off + i * 0x38
        if o + 0x38 > len(data):
            break
        (_flags, vaddr, vsize, paddr, psize, name_va) = struct.unpack_from(
            "<IIIIII", data, o)
        name = ""
        if base <= name_va < base + len(data):
            name = _cstring(data, name_va - base)
        sections.append(Section(name, vaddr, vsize, paddr, psize))
    return Xbe(path, base, title_id, title_name, sections)


def load(path: str) -> Xbe:
    with open(path, "rb") as fh:
        return parse(fh.read(), path)

"""Reading textures out of an uncooked Unreal Engine 2 package.

Why this exists
---------------

Rainbow Six 3's weapon and gadget icons are wanted for the loadout pages. On
the PS2 disc they are unreachable: the packages are cooked, and a cooked
package's export offsets describe the original PC layout rather than the file
in front of you, so `base + offset` lands in bytecode. Several bases were tried
and all of them missed.

The Xbox build of the same game ships the same artwork in **uncooked** `.utx`
packages, where the tables mean what they say. So the icons come from there:
`Textures/R63rdWeapons_t.utx` for the 30 guns and `Textures/R6Weapons_T.utx`
for the gadgets and launchers. Version 118/20, against the PS2 disc's 123/22 --
the same split already recorded for the two builds' package versions.

Naming is exact and needs no table: the icon for a weapon class is the class's
last path component plus `_T`, so `R63rdWeapons.SubMP5A4` is `SubMP5A4_T` and
`R6Weapons.R6FragGrenadeGadget` is `R6FragGrenadeGadget_T`. Matched all 36 of
the loadout choices with nothing left over.

What is implemented
-------------------

Only as much of the format as the icons need: the summary, the name, import and
export tables, UE2's property list, the mip chain, and DXT1. That covers every
128x64 icon in both packages. Nine other textures in those files are `Format 7`
and are skipped -- they are weapon skins, not icons, and nothing here wants
them.
"""

from __future__ import annotations

import struct

from .upackage import compact_index

#: UE2 `ETextureFormat`, as far as this module cares
TEXF_P8 = 0
TEXF_DXT1 = 3

#: property `info` size codes that carry a fixed width
_SIZES = {0: 1, 1: 2, 2: 4, 3: 12, 4: 16}

#: the Unreal package magic
MAGIC = 0x9E2A83C1


class TextureError(Exception):
    pass


class Package:
    """An uncooked UE2 package: names, imports, exports, and the raw bytes."""

    def __init__(self, data: bytes):
        if len(data) < 32 or struct.unpack_from("<I", data)[0] != MAGIC:
            raise TextureError("not an Unreal package")
        self.data = data
        self.version, self.licensee = struct.unpack_from("<HH", data, 4)
        name_count, name_off = struct.unpack_from("<II", data, 12)
        exp_count, exp_off = struct.unpack_from("<II", data, 20)
        imp_count, imp_off = struct.unpack_from("<II", data, 28)
        self.names = self._names(name_off, name_count)
        self.imports = self._imports(imp_off, imp_count)
        self.exports = self._exports(exp_off, exp_count)

    def _names(self, off, count):
        out, o = [], off
        for _ in range(count):
            n = self.data[o]
            o += 1
            out.append(self.data[o:o + n - 1].decode("latin-1", "replace"))
            o += n + 4                      # the string, then its flags
        return out

    def _imports(self, off, count):
        out, o = [], off
        for _ in range(count):
            cp, o = compact_index(self.data, o)
            cn, o = compact_index(self.data, o)
            o += 4                          # Outer
            nm, o = compact_index(self.data, o)
            out.append({"class": self.names[cn], "name": self.names[nm]})
        return out

    def _exports(self, off, count):
        out, o = [], off
        for _ in range(count):
            cls, o = compact_index(self.data, o)
            _sup, o = compact_index(self.data, o)
            o += 4                          # Outer
            nm, o = compact_index(self.data, o)
            o += 4                          # ObjectFlags
            size, o = compact_index(self.data, o)
            start = 0
            if size > 0:
                start, o = compact_index(self.data, o)
            out.append({"class_index": cls, "name": self.names[nm],
                        "size": size, "offset": start})
        return out

    def class_of(self, export) -> str:
        """The name of an export's class, resolving through the import table."""
        c = export["class_index"]
        if c < 0:
            return self.imports[-c - 1]["name"]
        if c > 0:
            return self.exports[c - 1]["name"]
        return "Class"

    # -- object bodies ----------------------------------------------------
    def properties(self, o: int):
        """UE2 property list -> ({name: value}, offsetAfterNone)."""
        out = {}
        while True:
            ni, o = compact_index(self.data, o)
            name = self.names[ni]
            if name == "None":
                return out, o
            info = self.data[o]
            o += 1
            typ, code, arr = info & 0x0F, (info >> 4) & 0x07, info & 0x80
            if typ == 10:                   # a struct names itself first
                _sn, o = compact_index(self.data, o)
            if code in _SIZES:
                size = _SIZES[code]
            elif code == 5:
                size = self.data[o]
                o += 1
            elif code == 6:
                size = struct.unpack_from("<H", self.data, o)[0]
                o += 2
            else:
                size = struct.unpack_from("<I", self.data, o)[0]
                o += 4
            if arr and typ != 3:
                _ai, o = compact_index(self.data, o)
            if typ == 3:                    # a bool rides in the info byte
                out[name] = bool(arr)
                continue
            if typ == 1:
                out[name] = self.data[o]
            elif typ == 2:
                out[name] = struct.unpack_from("<i", self.data, o)[0]
            elif typ == 4:
                out[name] = struct.unpack_from("<f", self.data, o)[0]
            elif typ in (5, 6):
                v, _ = compact_index(self.data, o)
                out[name] = self.names[v] if typ == 6 else v
            else:
                out[name] = self.data[o:o + size]
            o += size

    def mips(self, o: int):
        """[(bytes, width, height)] from a Texture body, largest first."""
        n, o = compact_index(self.data, o)
        out = []
        for _ in range(n):
            if self.version >= 63:
                o += 4                      # WidthOffset
            size, o = compact_index(self.data, o)
            blob = self.data[o:o + size]
            o += size
            u, v = struct.unpack_from("<II", self.data, o)
            o += 8 + 2                      # sizes, then UBits/VBits
            out.append((blob, u, v))
        return out

    def textures(self):
        """[(name, propertyDict, mipList)] for every Texture export."""
        out = []
        for e in self.exports:
            if self.class_of(e) != "Texture" or e["size"] <= 0:
                continue
            props, o = self.properties(e["offset"])
            out.append((e["name"], props, self.mips(o)))
        return out


# ---------------------------------------------------------------------------
# DXT1
# ---------------------------------------------------------------------------

def _rgb565(c):
    r, g, b = (c >> 11) & 0x1F, (c >> 5) & 0x3F, c & 0x1F
    return (r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)


def dxt1(data: bytes, width: int, height: int):
    """Decode DXT1 to a flat list of RGBA tuples, row major.

    The `c0 <= c1` branch is the 1-bit-alpha form, and index 3 there is
    transparent black -- which is what gives these icons their cut-out edges.
    """
    if len(data) < (width // 4) * (height // 4) * 8:
        raise TextureError("DXT1 payload is short for %dx%d" % (width, height))
    px = [(0, 0, 0, 0)] * (width * height)
    i = 0
    for by in range(0, height, 4):
        for bx in range(0, width, 4):
            c0, c1 = struct.unpack_from("<HH", data, i)
            bits = struct.unpack_from("<I", data, i + 4)[0]
            i += 8
            a, b = _rgb565(c0), _rgb565(c1)
            if c0 > c1:
                cols = (a, b,
                        tuple((2 * a[k] + b[k]) // 3 for k in range(3)),
                        tuple((a[k] + 2 * b[k]) // 3 for k in range(3)))
                alpha = (255, 255, 255, 255)
            else:
                cols = (a, b,
                        tuple((a[k] + b[k]) // 2 for k in range(3)),
                        (0, 0, 0))
                alpha = (255, 255, 255, 0)
            for y in range(4):
                row = by + y
                if row >= height:
                    break
                for x in range(4):
                    col = bx + x
                    if col >= width:
                        continue
                    sel = (bits >> (2 * (4 * y + x))) & 3
                    px[row * width + col] = cols[sel] + (alpha[sel],)
    return px


def icon_name(class_name: str) -> str:
    """`R63rdWeapons.SubMP5A4` -> `SubMP5A4_T`."""
    return class_name.split(".")[-1] + "_T"


def decode_icons(package_bytes: bytes):
    """{textureName: (width, height, rgbaPixels)} for every DXT1 texture."""
    pkg = Package(package_bytes)
    out = {}
    for name, props, mips in pkg.textures():
        if not mips or props.get("Format") != TEXF_DXT1:
            continue
        blob, w, h = mips[0]
        if w <= 0 or h <= 0 or len(blob) != w * h // 2:
            continue
        out[name] = (w, h, dxt1(blob, w, h))
    return out

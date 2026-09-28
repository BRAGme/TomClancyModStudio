"""Rainbow Six 3's own loadout icons, read from the user's disc at run time.

Nothing here ships artwork: every pixel comes out of the disc the user loaded,
and the GUI caches the result the way `art.banner_image` caches the banner
(`art.banner_image` calls `cached_icons` for a Rainbow Six 3 disc;
`gui/gearicons._real` reads the cache through `cached_path`).

Where the icons are
-------------------

`MENU.LIN` (in the VOKES archives) carries 43 icons as `[Texture][Palette]`
pairs: 128x64, 8-bit indexed, one mip, linear raster, RGBA palette with a
0..255 alpha. They are the serial data of two texture packages:

* `R6Weapons_T` -- 13 gadgets. Its summary and tables are in MENU.LIN itself,
  just ahead of its 13 records.
* `R63rdWeapons_T` -- 30 guns. Its tables are NOT in MENU.LIN. They were read
  during the boot that COMMON.LIN records, and the linker stayed open, so
  MENU.LIN's recording carries only the texture data. The names come from
  COMMON.LIN's copy of the tables.

How a record is named -- by structure, not by eye
-------------------------------------------------

UE2 serialises a mip's pixels as a `TLazyArray`, which writes a `SeekPos` in
front of the array: the absolute offset, in the ORIGINAL uncooked `.utx`, of
the byte just past the pixels. The PS2 cook replayed the read stream verbatim,
so that number survived. After the pixels come `USize, VSize` (u32) and
`UBits, VBits` (u8), ten bytes, and then the export ends. So an export with
`SerialOffset S` and `SerialSize N` has `SeekPos == S + N - 10`, and the export
table -- whose offsets are exact in original-file coordinates (see
`upackage.tables`) -- names the record. Measured on SLUS-20883: all 43 records
match exactly one Texture export each, and every match also walks its property
list cleanly with THAT package's name table and points its `Palette` at a
`Palette` export of the same package.

Cross-checked against the running game (research only, not needed at run
time): in two PCSX2 savestates taken after the gear menu had loaded, the
`UTexture` object carrying each name (`+0x28` name, `+0x18` outer) has its
`Palette` field (`+0xA0`) pointing at the `UPalette` whose colours are that
record's palette. 43 of 43 agree; 41 of them also agree on the palette's own
name (the other two palettes' name strings had been freed). In memory the
colours are B,G,R,A -- UE2's little-endian `FColor` -- which confirms the
disc order is R,G,B,A.

Which name the game asks for
----------------------------

`UR6WeaponsManager` (native, in `sp.soz` / `mp.soz`) builds the path from the
weapon class: the strings `"_T.Menu."`, `"_T"` and the fallback
`"R63rdWeapons_T.Menu.defGun_T"` sit together there. So the class
`R63rdWeapons.SubP90` asks for `R63rdWeapons_T.Menu.SubP90_T`, and
`R6Weapons.R6FragGrenadeGadget` for `R6Weapons_T.Menu.R6FragGrenadeGadget_T`.
Names are case-insensitive; the gun textures are stored lower-case.

One trap: `R63rdWeapons_T` has TWO Texture exports for 13 of the gun names --
one under the `Menu` group, one under `Gadgets`. The record in the stream is
always the one with the higher export index, whichever group it sits in
(`Menu.pistolmk23_t` for the Mk23, `Gadgets.assaultak47_t` for the AK). This
module does not need to know why: it tries every export of the right name and
keeps the one whose data is actually on the disc, which is by construction the
picture the game draws.
"""

from __future__ import annotations

import struct

from . import lin, upackage
from .upackage import compact_index, encode_compact

#: the recording that carries the icon data, then the ones that may carry the
#: tables of a texture package MENU.LIN only has data for
DATA_LIN = "/MENU.LIN"
TABLE_LINS = ("/MENU.LIN", "/COMMON.LIN", "/COMMONOFF.LIN", "/COMMON_SS.LIN")

#: the group the native weapons manager asks in
GROUP = "Menu"


class IconError(Exception):
    pass


# ---------------------------------------------------------------------------
# naming
# ---------------------------------------------------------------------------

def texture_for_class(class_path: str):
    """`R63rdWeapons.SubP90` -> (`R63rdWeapons_T`, `SubP90_T`)."""
    pkg, _, cls = class_path.rpartition(".")
    if not pkg or not cls:
        raise IconError("not a Package.Class path: %r" % class_path)
    return pkg + "_T", cls + "_T"


def choice_classes() -> dict:
    """{choice id: class path} for every loadout choice ModStudio offers.

    Read from `rsekits` so a choice added there gets its icon for free.
    """
    from . import rsekits
    out = {}
    for table in (rsekits.PRIMARIES, rsekits.SECONDARIES):
        for choice, (cls, _label) in table.items():
            out.setdefault(choice, cls)
    for choice, cls in rsekits.GADGETS.items():
        out.setdefault(choice, cls)
    return out


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------

class _Lins:
    """The disc's `.LIN` packages, inflated on first use and kept."""

    def __init__(self, iso):
        from .vokes import open_archives
        self.archives = open_archives(iso, r"/VOKES\d\.IMG$")
        self.plain = {}

    def get(self, key):
        if key not in self.plain:
            self.plain[key] = None
            for arc in self.archives:
                if key in arc.files:
                    try:
                        self.plain[key] = lin.decompress(
                            arc.read_entry(arc.files[key]))
                    except lin.LinError:
                        pass
                    break
        return self.plain[key]


def _read_lins(iso, wanted):
    """{'/NAME.LIN': plain bytes} for each of `wanted` found in the archives."""
    lins = _Lins(iso)
    return {k: lins.get(k) for k in wanted if lins.get(k) is not None}


class _Pkg:
    """One package's tables, and where its name table came from."""

    def __init__(self, name, names, imports, exports):
        self.name, self.names = name, names
        self.imports, self.exports = imports, exports
        self.none = encode_compact(names.index("None"))


def _texture_packages(data, wanted):
    """{packageName: _Pkg} for each of `wanted` whose tables are in `data`.

    A package does not record its own name, but these asset packages carry it
    in their name table. The test that it is the package itself and not one
    that merely imports it: the name is not an import, and the package exports
    the `Menu` group the weapons manager looks in.
    """
    out = {}
    for off, _p in upackage.packages(data):
        try:
            names, imports, exports = upackage.tables(data, off)
        except (upackage.PackageError, IndexError, UnicodeDecodeError,
                struct.error, ValueError):
            continue
        if ("Package", GROUP) not in [(c, n) for c, n, _s, _o in exports]:
            continue
        for name in wanted:
            if name in out or name not in names or name in imports:
                continue
            if "None" in names:
                out[name] = _Pkg(name, names, imports, exports)
    return out


def _walk(d, pos, names, limit=64):
    """{propName: (info, valueOffset)} and the offset after `None`, or None."""
    props = {}
    for _ in range(limit):
        ni, pos = compact_index(d, pos)
        if not 0 <= ni < len(names):
            return None
        name = names[ni]
        if name == "None":
            return props, pos
        info = d[pos]
        pos += 1
        typ, code = info & 0x0F, (info >> 4) & 7
        if typ == upackage.T_STRUCT:
            _s, pos = compact_index(d, pos)
        size = {0: 1, 1: 2, 2: 4, 3: 12, 4: 16}.get(code)
        if code == 5:
            size, pos = d[pos], pos + 1
        elif code == 6:
            size, pos = struct.unpack_from("<H", d, pos)[0], pos + 2
        elif code == 7:
            size, pos = struct.unpack_from("<I", d, pos)[0], pos + 4
        if typ == upackage.T_BOOL:
            props.setdefault(name, (info, pos))
            continue
        if info & 0x80:
            _a, pos = compact_index(d, pos)
        props.setdefault(name, (info, pos))
        pos += size
    return None


def _record(d, seek_at, size, pkg):
    """Decode the record whose lazy-array SeekPos sits at `seek_at`.

    Returns (width, height, pixels, rgbaPalette, recordStart) or None if any
    structural check fails. The checks are what make a 4-byte match a naming:
    the pixel count, the mip tail, a clean property walk with THIS package's
    names ending on the mip header, a `Palette` property naming a Palette
    export, and that palette's record directly after the texture.
    """
    try:
        if d[seek_at - 1] != 1:                        # mip count, compact(1)
            return None
        n, pix = compact_index(d, seek_at + 4)
        end = pix + n
        u, v, ub, vb = struct.unpack_from("<IIBB", d, end)
        if u * v != n or (1 << ub) != u or (1 << vb) != v:
            return None
        start = end + 10 - size
        if start < 0:
            return None
        walked = _walk(d, start, pkg.names)
        if walked is None:
            return None
        props, after = walked
        # `None`, eight zero bytes (this build's), then the mip count
        if after + 8 != seek_at - 1:
            return None
        for key, want in (("USize", u), ("VSize", v)):
            if key in props:
                _i, at = props[key]
                if struct.unpack_from("<i", d, at)[0] != want:
                    return None
        if "Palette" not in props:
            return None
        ref, _ = compact_index(d, props["Palette"][1])
        if not 0 < ref <= len(pkg.exports):
            return None
        pcls, _pn, psize, _po = pkg.exports[ref - 1]
        if pcls != "Palette":
            return None
        pal_at = end + 10
        head = pkg.none + encode_compact(256)
        if psize != len(head) + 1024 or d[pal_at:pal_at + len(head)] != head:
            return None
        pal = d[pal_at + len(head):pal_at + len(head) + 1024]
        return u, v, d[pix:end], pal, start
    except (IndexError, struct.error):
        return None


def locate(iso, classes=None):
    """{class path: dict} describing where each class's icon is on this disc.

    Each value holds `package`, `export` (1-based index), `texture` (the name
    as the export table spells it), `offset` (record start in MENU.LIN's plain
    stream), `width`, `height`, `pixels`, `palette`. Classes without a record
    are left out. `classes` defaults to every ModStudio loadout choice.
    """
    if classes is None:
        classes = sorted(set(choice_classes().values()))
    wanted = {}
    for cls in classes:
        wanted[cls] = texture_for_class(cls)
    pkg_names = {p for p, _t in wanted.values()}

    lins = _Lins(iso)
    data = lins.get(DATA_LIN)
    if data is None:
        raise IconError("no %s on this disc" % DATA_LIN)
    pkgs = {}
    for key in TABLE_LINS:                     # stop as soon as all are found
        if len(pkgs) == len(pkg_names):
            break
        blob = lins.get(key)
        if blob is not None:
            for name, pkg in _texture_packages(blob, pkg_names).items():
                pkgs.setdefault(name, pkg)

    out = {}
    for cls, (pname, tname) in wanted.items():
        pkg = pkgs.get(pname)
        if pkg is None:
            continue
        found = []
        for idx, (ecls, ename, size, off) in enumerate(pkg.exports, 1):
            if ecls != "Texture" or size <= 0 or ename.lower() != tname.lower():
                continue
            needle = struct.pack("<I", off + size - 10)
            at = data.find(needle)
            while at >= 0:
                rec = _record(data, at, size, pkg)
                if rec is not None:
                    found.append((idx, ename) + rec)
                at = data.find(needle, at + 1)
        if not found:
            continue
        # The same export recorded twice would be two identical copies; two
        # DIFFERENT exports both on the disc would be a naming the structure
        # cannot settle, and that is refused rather than guessed.
        if len({(f[0]) for f in found}) > 1:
            raise IconError("%s: more than one export of %s is on the disc"
                            % (cls, tname))
        idx, ename, u, v, pixels, pal, start = found[0]
        out[cls] = dict(package=pname, export=idx, texture=ename,
                        offset=start, width=u, height=v,
                        pixels=pixels, palette=pal)
    return out


def to_image(rec):
    """A PIL RGBA image from one `locate` entry."""
    from PIL import Image
    pal = rec["palette"]
    im = Image.frombytes("P", (rec["width"], rec["height"]), rec["pixels"])
    # putpalette with an RGBA palette keeps each entry's own alpha
    im.putpalette(pal, rawmode="RGBA")
    return im.convert("RGBA")


def extract(iso) -> dict:
    """{choice id: PIL RGBA image} for every loadout choice with an icon.

    `iso` is an opened `tcps2.iso.Iso`. Choices sharing a class (a grenade
    that is both a secondary and a gadget) share one image object.
    """
    classes = choice_classes()
    found = locate(iso, sorted(set(classes.values())))
    images = {cls: to_image(rec) for cls, rec in found.items()}
    return {choice: images[cls] for choice, cls in classes.items()
            if cls in images}


# ---------------------------------------------------------------------------
# the GUI side: read once, cache beside the banner
# ---------------------------------------------------------------------------

def cache_name(profile_id, choice):
    return "%s.gear.%s.png" % (profile_id, choice)


def cached_icons(detection, cache_dir):
    """{choice: PIL image}, from the cache if complete, else from the disc.

    Mirrors `art.banner_image`: the second launch never opens the ISO. A disc
    that yields nothing returns {} and the GUI keeps its drawn glyphs.
    """
    import os
    profile = getattr(detection, "profile", None)
    if profile is None or not cache_dir:
        return {}
    choices = choice_classes()
    paths = {c: os.path.join(cache_dir, cache_name(profile.id, c))
             for c in choices}
    if all(os.path.exists(p) for p in paths.values()):
        try:
            from PIL import Image
            return {c: Image.open(p).convert("RGBA") for c, p in paths.items()}
        except Exception:                         # noqa: BLE001
            pass
    try:
        from .iso import Iso
        with Iso(detection.path) as iso:
            icons = extract(iso)
    except Exception:                             # noqa: BLE001
        return {}
    for c, im in icons.items():
        try:
            im.save(paths[c], "PNG")
        except Exception:                         # noqa: BLE001
            pass
    return icons


def cached_path(cache_dir, choice):
    """The cached icon for `choice` from any Rainbow Six 3 disc, or None.

    The loadout choices are Rainbow Six 3's own, so whichever region's disc
    filled the cache, its picture is the one to show.
    """
    import glob
    import os
    if not cache_dir:
        return None
    hits = sorted(glob.glob(os.path.join(cache_dir, cache_name("*", choice))))
    return hits[0] if hits else None

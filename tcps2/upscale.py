"""Use the user's own PCSX2 texture-replacement packs, when they have one.

PCSX2 can substitute a higher-resolution texture for any the game uploads, and
a pack is a folder of `.dds` files named after the texture they stand in for:

    <TEX0 hash>-<CLUT hash>-<TEX0 bits>.dds

The trailing eight hex digits are the TEX0 register, which is what makes this
worth doing at all -- they state the pixel format and the size of the PS2
texture the file replaces:

    bits 0..5 PSM   6..9 TW (log2 width)   10..13 TH   14 TCC   15.. TEXA

So a texture we have already decoded off the disc can be matched against only
the handful of pack entries that share its format and dimensions, rather than
against the whole pack. On a 4,872-file pack that turns thousands of decodes
into two.

The match is then made on image content, because the hash is PCSX2's own and
we do not reproduce it. An upscale is never pixel-identical to its original, so
the test is not a low score by itself -- it is SEPARATION: the best candidate
has to stand clear of the runner-up. A pack that does not contain the texture
at all produces a field of near-identical mediocre scores, and that is refused
rather than guessed at.

Nothing here is redistributed: the pack is the user's own file, read from their
own emulator folder at run time.
"""

from __future__ import annotations

import os

#: an explicit override always wins
ROOT_ENV = "TCMS_PCSX2_TEXTURES"

#: where a PCSX2 install usually keeps its texture folder
SEARCH = (
    r"E:\Emulators\pcsx2-v1.7.5641-windows-x64-Qt\textures",
    r"E:\Emulators\PCSX2 RTX Remix\textures",
    os.path.join(os.path.expanduser("~"), "Documents", "PCSX2", "textures"),
)

#: a candidate must beat the runner-up by this much, and be this close in
#: absolute terms, before it is believed
MIN_SEPARATION = 2.5
MAX_DISTANCE = 12.0

_THUMB = 40
_ROOT_CACHE = []


def find_root():
    """The PCSX2 textures folder, or None."""
    if _ROOT_CACHE:
        return _ROOT_CACHE[0]
    env = os.environ.get(ROOT_ENV)
    for path in ([env] if env else []) + list(SEARCH):
        if path and os.path.isdir(path):
            _ROOT_CACHE.append(path)
            return path
    _ROOT_CACHE.append(None)
    return None


def pack_dir(serial, root=None):
    """The replacements folder for one disc serial, or None."""
    root = root or find_root()
    if not root or not serial:
        return None
    path = os.path.join(root, serial.upper(), "replacements")
    return path if os.path.isdir(path) else None


def tex0(filename):
    """(PSM, width, height) of the PS2 texture a pack entry replaces."""
    try:
        stem = filename.rsplit(".", 1)[0]
        bits = int(stem.rsplit("-", 1)[-1], 16)
    except ValueError:
        return None
    return bits & 63, 1 << ((bits >> 6) & 15), 1 << ((bits >> 10) & 15)


def _thumb(img):
    from PIL import Image
    return list(img.convert("L").resize((_THUMB, _THUMB), Image.LANCZOS).getdata())


def _distance(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / float(len(a))


def better(serial, original, psm=19, root=None):
    """A higher-resolution stand-in for `original`, or None.

    `original` is the texture as decoded off the disc; its size is used to
    pick the candidates, so it must be the true texture size.
    """
    folder = pack_dir(serial, root)
    if folder is None or original is None:
        return None
    try:
        from PIL import Image
    except ImportError:
        return None

    want_key = (psm, original.width, original.height)
    names = []
    try:
        for name in os.listdir(folder):
            if tex0(name) == want_key:
                names.append(name)
    except OSError:
        return None
    if not names:
        return None

    want = _thumb(original)
    scored = []
    for name in names:
        try:
            img = Image.open(os.path.join(folder, name))
            img.load()
        except Exception:                         # noqa: BLE001
            continue
        if img.width < original.width or img.height < original.height:
            continue                              # not an upscale, skip it
        scored.append((_distance(want, _thumb(img)), name, img))
    if not scored:
        return None
    scored.sort(key=lambda row: row[0])

    best, _name, img = scored[0]
    if best > MAX_DISTANCE:
        return None
    if len(scored) > 1:
        runner_up = scored[1][0]
        if runner_up < best * MIN_SEPARATION:
            # the field is flat: the pack probably does not hold this texture
            return None
    return _normalise_alpha(img.convert("RGBA"))


def _normalise_alpha(img):
    """Put PS2-range alpha back on a 0..255 scale.

    The PS2 stores alpha 0..128, and a pack dumped straight from the emulator
    keeps that range -- the shell sheet measures max 134, with 128 by far the
    commonest value. Taken at face value every replacement would draw at half
    opacity, so a channel that never approaches 255 is doubled, exactly as the
    CLUT decode does. A pack authored on the full range is left alone.
    """
    alpha = img.split()[-1]
    peak = max(alpha.getdata())
    if 0 < peak <= 140:
        img.putalpha(alpha.point(lambda v: min(255, v * 2)))
    return img

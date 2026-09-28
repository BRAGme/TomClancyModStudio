"""Read a PCSX2 savestate as a memory image.

A `.p2s` is a zip, and `eeMemory.bin` inside it is the whole 32 MB of EE RAM at
the moment the state was taken. That turns a "run the game and scan memory" job
into a file-reading job: no emulator has to be driven, nothing has to be timed,
and the same bytes can be searched over and over.

What it is for
--------------

**Proving an edit reached the game.** Every setting this tool writes into
`R6GAMESETTINGS.INI` ends up in a parsed key/value cache in EE RAM, with the
value still in text form right after the key:

    $ python research/code/p2s.py ini "SLUS-21105 (82E1D0EA).07.p2s"
    m_fMinDistToThrowGrenade = 500
    m_fSightRadius           = 5000.0

That is how the Ghost Recon 2 grenade-distance report was settled: the cache
holds whatever the disc's INI said, so a value that arrives correctly and
changes nothing in play is an inert variable rather than a failed edit.

**Finding a save-state gate.** Take two states either side of the thing that
changes -- one before a mission is unlocked, one after -- and `diff` reports
every byte that moved. On a 32 MB image that is thousands of bytes, but the
progress flags are the ones that move once and stay moved, which `diff` over
three or more states narrows quickly.

Usage
-----

    python research/code/p2s.py ini    <state.p2s> [key ...]
    python research/code/p2s.py find   <state.p2s> <text>
    python research/code/p2s.py diff   <a.p2s> <b.p2s> [--max N]
    python research/code/p2s.py u32    <state.p2s> <value>
"""

from __future__ import annotations

import re
import struct
import sys
import zipfile

#: the keys worth printing by default -- everything the tool can write
DEFAULT_KEYS = (
    "m_fMinDistToThrowGrenade", "m_fGrenadeReactionDelayRecruit",
    "m_fGrenadeReactionDelayVeteran", "m_fTerroristSkillMultiplierRecruit",
    "m_fTerroristSkillMultiplierVeteran", "m_fTerroristSkillMultiplierElite",
    "m_fDistForPerfectAccuracyTerro", "m_fSightRadius", "m_iDefaultSearchTime",
    "m_fTerroristWalkingSpeed", "m_fTerroristRunningSpeed",
    "m_fReactionTimeForFiringRecruit", "m_iXSensitivityMaxSteps",
    "m_fXSensitivityMultiplier",
)

_VALUE = re.compile(rb"[-+0-9.]{1,12}")


def ee_memory(path):
    """The 32 MB EE RAM image out of a savestate."""
    with zipfile.ZipFile(path) as z:
        return z.read("eeMemory.bin")


def ini_values(ee, keys=DEFAULT_KEYS):
    """{key: text} for the parsed INI cache the engine keeps in RAM.

    The cache stores the value as text a short distance after the key, so the
    first number-shaped run within 48 bytes is it. Where a key appears more
    than once -- it is also in the script name table -- the hit with a number
    after it is the cache and the others are the name.
    """
    out = {}
    for key in keys:
        kb = key.encode()
        at = ee.find(kb)
        while at >= 0:
            window = ee[at + len(kb):at + len(kb) + 48]
            for m in _VALUE.finditer(window):
                token = m.group(0).decode()
                # The name table puts one name straight after another, so a
                # naive search finds the "1" inside "m1" and reports it as the
                # value. A real value is a standalone token: nothing
                # alphanumeric on either side of it, and it parses as a number.
                before = window[max(0, m.start() - 1):m.start()]
                after = window[m.end():m.end() + 1]
                if before.isalnum() or after.isalnum():
                    continue
                # The cache pads with NULs between the key and its value; the
                # name table butts one name against the next. Requiring two
                # NULs in front is what tells the value from a neighbouring
                # name that happens to start with a digit.
                run = window[max(0, m.start() - 2):m.start()]
                if run.count(0) < 2:
                    continue
                try:
                    float(token)
                except ValueError:
                    continue
                out[key] = (token, at)
                break
            if key in out:
                break
            at = ee.find(kb, at + 1)
    return out


def find_text(ee, text, limit=12):
    out, at = [], -1
    needle = text.encode() if isinstance(text, str) else text
    while len(out) < limit:
        at = ee.find(needle, at + 1)
        if at < 0:
            break
        tail = re.sub(rb"[^ -~]", b".", ee[at:at + 72]).decode()
        out.append((at, tail))
    return out


def find_u32(ee, value, limit=20):
    needle = struct.pack("<I", value & 0xFFFFFFFF)
    out, at = [], -1
    while len(out) < limit:
        at = ee.find(needle, at + 1)
        if at < 0:
            break
        out.append(at)
    return out


def diff(a, b, limit=400):
    """Byte ranges that differ, coalesced into runs."""
    runs, start = [], None
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            if start is None:
                start = i
        elif start is not None:
            runs.append((start, i - start))
            start = None
            if len(runs) >= limit:
                break
    if start is not None:
        runs.append((start, n - start))
    return runs


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    cmd, path = argv[1], argv[2]
    if cmd == "ini":
        ee = ee_memory(path)
        keys = argv[3:] or DEFAULT_KEYS
        for key, (text, at) in sorted(ini_values(ee, keys).items()):
            print("%-36s = %-10s  (at %08x)" % (key, text, at))
        return 0
    if cmd == "find":
        for at, tail in find_text(ee_memory(path), argv[3]):
            print("%08x  %s" % (at, tail))
        return 0
    if cmd == "u32":
        for at in find_u32(ee_memory(path), int(argv[3], 0)):
            print("%08x" % at)
        return 0
    if cmd == "diff":
        a, b = ee_memory(path), ee_memory(argv[3])
        runs = diff(a, b)
        print("%d differing runs (first 40)" % len(runs))
        for at, size in runs[:40]:
            print("  %08x  %3d bytes  %s -> %s"
                  % (at, size, a[at:at + min(size, 8)].hex(),
                     b[at:at + min(size, 8)].hex()))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

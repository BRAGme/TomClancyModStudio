"""The flashlight sits inside the shooter's hand on the SR-2 (the "Uzi").

Reported 2026-09-26. The gun the player calls the Uzi is the class `SubSR2`,
display name `SR-2 (9MM)` -- the only weapon in the game animated with the UZI
set (`StandUZILow_nt` / `StandUZIHigh_nt` / `StandFireUZI`). Its flashlight is
pinned to the weapon's pivot instead of its barrel.

Why
---

`R6Weapons.SpawnFlashlight` spawns one hard-coded class,
`R6WeaponGadgets.R6TacticalLightGadget`, and calls its `ActivateGadget`, which
is the whole of the positioning logic::

    pWeaponOwner.GetTagInformations("TagGadget", vTagLocation, rTagRotator, 1.0)
    SetRelativeLocation(vTagLocation)
    SetRelativeRotation(rTagRotator)

`Actor.GetTagInformations(string TagName, out vector, out rotator, float)` reads
a named socket off the weapon's own third-person static mesh, and the result is
used verbatim -- no additive vector, no per-weapon property. The offset is
therefore SHARED code and PER-WEAPON art, and the PS2 build does not even carry
the PC's `m_szTacticalLightClass` hook.

`R63rdWeapons_SM.SubGuns.R63rdSubSR2` has three sockets -- TagMuzzle,
TagMagazine, TagCase -- and **no TagGadget**. The lookup misses, returns
(0,0,0), and the light lands on the pivot, behind the magazine well. Measured in
a savestate: 17 live SR-2 gadgets at RelativeLocation (0,0,0), against four
G3A3s at (58.3850, -2.2212, 8.2220), which is exactly that mesh's TagGadget.

What this does
--------------

Adds the missing socket. One record, 59 bytes, appended to the array, and the
array's count byte stepped 3 -> 4.

Why growth is safe here
-----------------------

A `.LIN` is a recording of one boot's read stream, replayed in order; Seeks
under the package loader are discarded. The rule is "never ask the recording
for anything NEW", not "preserve length" -- growth is fine as long as the
loader is told to consume exactly the bytes that were inserted.

A socket's name is an INLINE length-prefixed string inside the mesh's own
serial data, not a name-table index. Measured: "TagGadget" appears in no
package's name table anywhere in any level payload, while the literal bytes
occur inline 20 times per level; and records in one array step by 57, 59 and 61
bytes according to their name length, which a fixed-width index could not do.
So the record adds no name, no import, no export and no object reference.

There is also nothing to keep in step on the export side. The cooked tables do
not describe this file: the only package whose name table holds "R63rdSubSR2"
declares zero StaticMesh exports and 0x6cca bytes of serial in total, while the
socket arrays sit 51,199 and 2,979,514 bytes past its tables. No export
window in the payload covers them under any offset model. The count byte in
front of the records is what drives the read, and stepping it 3 -> 4 makes the
deserialiser consume exactly the 59 bytes inserted, leaving the cursor on the
same following byte it landed on before.

The values
----------

`Y` is not an estimate: it is the SR-2's own centreline float, byte-copied from
its TagMuzzle record, and on every donor mesh -- and on the PC build's real Uzi
-- TagGadget sits exactly on the weapon centreline. The matrix is identity,
byte-copied from an existing socket.

`X` and `Z` are inferred. Three independent estimates agree closely: the PC
build's Uzi (a rule donor, not a value donor -- different model), the mean
muzzle setback of the three PS2 SMGs nearest the SR-2 in size, and the light
body's own emitter geometry. They are parameters because the player judges them
by eye.
"""

from __future__ import annotations

import re
import struct

#: origin(12) + 3x3 matrix(36); the name follows as a length-prefixed string
REC_FIXED = 48
TAG = b"TagGadget\x00"
_NAME = re.compile(rb"^[A-Za-z0-9_]+\x00$")

#: the SR-2's TagMuzzle -- the fingerprint that identifies its socket array
SR2_MUZZLE = (30.3440, -2.2241, 7.2163)
SR2_SOCKETS = ("TagMuzzle", "TagMagazine", "TagCase")

#: defaults for the added socket, in the mesh's own space
DEFAULT_X = 21.36
DEFAULT_Z = 4.72


class UziLightError(Exception):
    pass


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------

def walk(plain: bytes, count_at: int):
    """(records, end) for the socket array whose count byte is at `count_at`.

    Returns None unless the count reads as a small positive number and exactly
    that many well-formed records follow.
    """
    if count_at < 0 or count_at >= len(plain):
        return None
    cnt = plain[count_at]
    if not 1 <= cnt <= 32:
        return None
    at, recs = count_at + 1, []
    for _ in range(cnt):
        if at + REC_FIXED + 1 > len(plain):
            return None
        ln = plain[at + REC_FIXED]
        if not 2 <= ln <= 40:
            return None
        name = plain[at + REC_FIXED + 1:at + REC_FIXED + 1 + ln]
        if not _NAME.match(name):
            return None
        recs.append(dict(at=at, name=name[:-1].decode("latin-1"),
                         origin=struct.unpack_from("<3f", plain, at),
                         matrix=plain[at + 12:at + REC_FIXED]))
        at += REC_FIXED + 1 + ln
    return recs, at


def find(plain: bytes):
    """Every SR-2 socket array in the payload, stock or already patched."""
    out = []
    needle = b"TagMuzzle\x00"
    i = plain.find(needle)
    while i >= 0:
        origin = i - 1 - REC_FIXED
        if origin >= 1 and plain[i - 1] == len(needle):
            got = struct.unpack_from("<3f", plain, origin) if origin + 12 <= len(plain) else None
            if got and all(abs(a - b) < 1e-3 for a, b in zip(got, SR2_MUZZLE)):
                w = walk(plain, origin - 1)
                if w:
                    recs, end = w
                    names = [r["name"] for r in recs]
                    if names[:3] == list(SR2_SOCKETS):
                        out.append(dict(count_at=origin - 1, count=plain[origin - 1],
                                        records=recs, names=names, end=end))
        i = plain.find(needle, i + 1)
    return out


def reads(plain: bytes) -> str:
    sites = find(plain)
    if not sites:
        return "unknown"
    has = ["TagGadget" in s["names"] for s in sites]
    if all(has):
        return "fixed"
    if not any(has):
        return "stock"
    return "mixed"


# ---------------------------------------------------------------------------
# writing
# ---------------------------------------------------------------------------

def record(x: float, y_bytes: bytes, z: float, matrix: bytes) -> bytes:
    """The 59-byte socket record. `y_bytes` and `matrix` are copied, not built."""
    if len(y_bytes) != 4 or len(matrix) != 36:
        raise UziLightError("y must be 4 bytes and the matrix 36")
    rec = struct.pack("<f", x) + y_bytes + struct.pack("<f", z) + matrix \
        + bytes([len(TAG)]) + TAG
    if len(rec) != REC_FIXED + 1 + len(TAG):
        raise UziLightError("record came out %d bytes, expected %d"
                            % (len(rec), REC_FIXED + 1 + len(TAG)))
    return rec


def apply(plain: bytes, x: float = DEFAULT_X, z: float = DEFAULT_Z,
          expect: int | None = None):
    """Returns (plain, changed). Idempotent; safe to run on a patched payload.

    A payload with no SR-2 mesh is left alone and reports zero -- 25 of the 85
    level packages are like that, and so is every COMMON. Pass `expect` to
    demand a particular number of arrays instead.
    """
    sites = find(plain)
    if expect is not None and len(sites) != expect:
        raise UziLightError("expected %d SR-2 socket arrays, found %d"
                            % (expect, len(sites)))
    if not sites:
        return plain, 0
    todo = [s for s in sites if "TagGadget" not in s["names"]]
    if not todo:
        return plain, 0
    for s in todo:
        if s["count"] != len(SR2_SOCKETS) or s["names"] != list(SR2_SOCKETS):
            raise UziLightError("array at 0x%06x is not stock: count=%d names=%s"
                                % (s["count_at"], s["count"], s["names"]))
    out = bytearray(plain)
    # back to front, so the earlier sites' offsets stay valid
    for s in sorted(todo, key=lambda a: a["count_at"], reverse=True):
        muzzle = s["records"][0]
        rec = record(x, plain[muzzle["at"] + 4:muzzle["at"] + 8], z, muzzle["matrix"])
        out[s["end"]:s["end"]] = rec
        out[s["count_at"]] = s["count"] + 1
    new = bytes(out)
    _check(plain, new, todo, x, z)
    return new, len(todo)


# ---------------------------------------------------------------------------
# the assertions that make the edit checkable
# ---------------------------------------------------------------------------

MAGIC = struct.pack("<I", 0x9E2A83C1)


def _magics(plain):
    out, i = [], plain.find(MAGIC)
    while i >= 0:
        out.append(i)
        i = plain.find(MAGIC, i + 1)
    return out


def _check(before: bytes, after: bytes, sites, x, z):
    grow = REC_FIXED + 1 + len(TAG)
    n = len(sites)
    if len(after) - len(before) != n * grow:
        raise UziLightError("payload grew %d bytes, expected %d"
                            % (len(after) - len(before), n * grow))

    # 1. every byte outside the insertions is unchanged, and only the count
    #    bytes differ in the region before the first insertion.
    cursor_b = cursor_a = 0
    for s in sorted(sites, key=lambda a: a["count_at"]):
        head_b, head_a = before[cursor_b:s["end"]], after[cursor_a:cursor_a + (s["end"] - cursor_b)]
        diff = [k for k in range(len(head_b)) if head_b[k] != head_a[k]]
        if diff != [s["count_at"] - cursor_b]:
            raise UziLightError("unexpected change before 0x%06x: %s"
                                % (s["end"], [hex(cursor_b + d) for d in diff][:8]))
        cursor_a += (s["end"] - cursor_b) + grow
        cursor_b = s["end"]
    if before[cursor_b:] != after[cursor_a:]:
        raise UziLightError("tail after the last insertion is not byte-identical")

    # 2. every SR-2 array now reads 4 records, closes cleanly, and the byte the
    #    deserialiser lands on afterwards is the same one as before.
    for s in sorted(sites, key=lambda a: a["count_at"]):
        shift = grow * sum(1 for t in sites if t["count_at"] < s["count_at"])
        w = walk(after, s["count_at"] + shift)
        if not w:
            raise UziLightError("patched array at 0x%06x does not close"
                                % (s["count_at"] + shift))
        recs, end = w
        names = [r["name"] for r in recs]
        if names != list(SR2_SOCKETS) + ["TagGadget"]:
            raise UziLightError("patched array reads %s" % names)
        if after[end:end + 24] != before[s["end"]:s["end"] + 24]:
            raise UziLightError("cursor lands on different bytes after 0x%06x" % end)
        got = recs[-1]["origin"]
        want = (x, struct.unpack("<f", before[s["records"][0]["at"] + 4:
                                              s["records"][0]["at"] + 8])[0], z)
        if any(abs(a - b) > 1e-4 for a, b in zip(got, want)):
            raise UziLightError("socket reads %s, wanted %s" % (got, want))
        if recs[-1]["matrix"] != s["records"][0]["matrix"]:
            raise UziLightError("matrix is not the byte-copy of TagMuzzle's")

    # 3. no package header is created or destroyed, and each one moves by
    #    exactly the bytes inserted in front of it -- the frag-warning measure.
    mb, ma = _magics(before), _magics(after)
    if len(mb) != len(ma):
        raise UziLightError("magic count changed: %d -> %d" % (len(mb), len(ma)))
    for b, a in zip(mb, ma):
        want = b + grow * sum(1 for t in sites if t["end"] <= b)
        if a != want:
            raise UziLightError("magic 0x%06x moved to 0x%06x, expected 0x%06x"
                                % (b, a, want))

    # 4. the record introduces no object reference: its 59 bytes are geometry,
    #    a byte-copied matrix, one length byte and ASCII.
    for s in sorted(sites, key=lambda a: a["count_at"]):
        shift = grow * sum(1 for t in sites if t["count_at"] < s["count_at"])
        rec = walk(after, s["count_at"] + shift)[0][-1]
        blob = after[rec["at"]:rec["at"] + grow]
        if blob[REC_FIXED] != len(TAG) or blob[REC_FIXED + 1:] != TAG:
            raise UziLightError("the name is not the inline literal")


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "uzi_flashlight", "The SR-2's flashlight position",
        BOOL, False, group,
        confidence="experimental", touches="data",
        help="The SR-2 -- the compact submachine gun the game animates as an "
             "Uzi -- is the only primary weapon whose third-person model was "
             "never given a mounting point for the tactical light. Every other "
             "gun has one, so a terrorist carrying an SR-2 at night wears his "
             "flashlight inside his fist, behind the magazine, instead of "
             "under the barrel. This adds the missing mounting point.",
        caution="Not yet played. The sideways and vertical placement are "
                "reasoned from the guns that do have one -- and from the PC "
                "build's own Uzi -- rather than measured, because the correct "
                "value was never authored and exists nowhere to be read. The "
                "light should sit under the barrel a little behind the muzzle; "
                "if it looks high or far forward, those are the two numbers.")

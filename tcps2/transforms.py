"""Edits to the XML data files inside Ghost Recon's and Jungle Storm's archives.

These games put their enemies in data, not code. A mission's `<Units>` block is
the order of battle -- one `<Actor>` is one soldier -- and the shipping game does
its own difficulty scaling with three suppression attributes on those actors:

    <Actor ... File = "m02_rec_ak47_2.atr" Easy = "0"/>

`Easy = "0"` means *this soldier is removed on Easy*. There is no `"1"` form
anywhere in either game; absence of the attribute means present. So deleting
those attributes puts every soldier into every difficulty, which is the single
biggest lever in the game: Ghost Recon goes from 678 enemies on Easy to the full
1,099, and Jungle Storm from 657 to 955.

The `File` attribute names an `.atr` template whose filename carries the skill
tier -- `_rec_`, `_vet_`, `_eli_` -- with measurably different armour, weapon
skill, stamina and stealth. Repointing it promotes a soldier without moving him.

**Every transform here preserves the byte length of the file it edits**, padding
with spaces where it removes something. That is not cosmetic: the compressed
container is a chain of 16 KB chunks, so an edit that keeps the length lets the
untouched chunks be copied across verbatim instead of re-compressed, and only
the chunks that actually changed pay for this tool's encoder being a shade
looser than the one Red Storm shipped with.
"""

from __future__ import annotations

import re
import struct

DIFFICULTY = re.compile(rb'\s+(?:Easy|Normal|Hard)\s*=\s*"0"')
HIDDEN = re.compile(rb'\s+Hidden\s*=\s*"1"')
ATR_FILE = re.compile(rb'(File\s*=\s*")([^"]*?)(_rec_|_vet_|_eli_)([^"]*?\.atr)(")',
                      re.I)
TIERS = [b"_rec_", b"_vet_", b"_eli_"]


class TransformError(Exception):
    pass


def _blank(match):
    return b" " * len(match.group(0))


def strip_difficulty(plain: bytes, which=("Easy", "Normal", "Hard")):
    """Delete the per-actor difficulty suppression flags."""
    names = b"|".join(w.encode() for w in which)
    rx = re.compile(rb'\s+(?:' + names + rb')\s*=\s*"0"')
    count = [0]

    def sub(m):
        count[0] += 1
        return _blank(m)

    return rx.sub(sub, plain), count[0]


def reveal_hidden(plain: bytes):
    """Spawn the actors that ship despawned waiting for a script."""
    count = [0]

    def sub(m):
        count[0] += 1
        return _blank(m)

    return HIDDEN.sub(sub, plain), count[0]


def set_enemy_tier(plain: bytes, tier: str, only_enemies=True):
    """Promote or demote every enemy's `.atr` template by skill tier.

    The tier lives in the filename, and the three tiers are the same model with
    different numbers -- recruit sits at armour 1 and skills 1-3, veteran at 2
    and 2-4, elite at 3 and 3-5. Length is preserved because all three markers
    are five characters.
    """
    want = ("_%s_" % tier).encode()
    if want not in TIERS:
        raise TransformError("unknown tier %r" % tier)
    body = plain
    if only_enemies:
        body = plain          # every Actor in a mission's own Units block
    count = [0]

    def sub(m):
        if m.group(3).lower() == want:
            return m.group(0)
        count[0] += 1
        return m.group(1) + m.group(2) + want + m.group(4) + m.group(5)

    return ATR_FILE.sub(sub, body), count[0]


def bump_enemy_tier(plain: bytes, steps: int):
    """Move every enemy up (or down) the recruit/veteran/elite ladder."""
    count = [0]

    def sub(m):
        cur = TIERS.index(m.group(3).lower())
        new = max(0, min(len(TIERS) - 1, cur + steps))
        if new == cur:
            return m.group(0)
        count[0] += 1
        return m.group(1) + m.group(2) + TIERS[new] + m.group(4) + m.group(5)

    return ATR_FILE.sub(sub, plain), count[0]


# ---------------------------------------------------------------------------
# game-type script variables
# ---------------------------------------------------------------------------

SCRIPT_BLOCK = re.compile(rb'<(ScriptCompiled|ScriptSource)>(.*?)</\1>', re.S)


def _nib_decode(text: bytes) -> bytes:
    """The A..P nibble encoding Red Storm uses for embedded script blobs:
    each payload byte is two characters in `A`..`P`, low nibble first."""
    out = bytearray()
    for i in range(0, len(text) - 1, 2):
        lo, hi = text[i] - 0x41, text[i + 1] - 0x41
        if not (0 <= lo < 16 and 0 <= hi < 16):
            raise TransformError("not an A..P payload at %d" % i)
        out.append(lo | (hi << 4))
    return bytes(out)


def _nib_encode(data: bytes) -> bytes:
    out = bytearray()
    for b in data:
        out.append(0x41 + (b & 15))
        out.append(0x41 + (b >> 4))
    return bytes(out)


def script_variables(payload: bytes):
    """[(name, value, offsetOfValue)] from a decoded script blob.

    Layout: `u32 count`, two fixed words, then for each variable a length-
    prefixed name followed by `u32 value, u32 id, u32 0`. Because the A..P
    encoding is fixed width, rewriting a value in place keeps the payload
    length, the XML length and therefore the archive slot size identical.
    """
    if len(payload) < 12:
        raise TransformError("script payload too short")
    count = struct.unpack_from("<I", payload, 0)[0]
    if not (0 < count < 4096):
        raise TransformError("implausible variable count %d" % count)
    out, o = [], 12
    for _ in range(count):
        if o + 4 > len(payload):
            break
        n = struct.unpack_from("<I", payload, o)[0]
        o += 4
        if n > 256 or o + n + 12 > len(payload):
            break
        name = payload[o:o + n].decode("latin1")
        o += n
        value = struct.unpack_from("<I", payload, o)[0]
        out.append((name, value, o))
        o += 12
    return out


def read_gtf_variables(plain: bytes):
    """{name: value} across every script blob in a `.GTF`."""
    found = {}
    for m in SCRIPT_BLOCK.finditer(plain):
        try:
            payload = _nib_decode(m.group(2).strip())
            for name, value, _off in script_variables(payload):
                found.setdefault(name, value)
        except TransformError:
            continue
    return found


def set_gtf_variables(plain: bytes, updates: dict):
    """Rewrite named script variables in place. Returns (bytes, changed)."""
    changed = [0]
    wanted = {k.lower(): v for k, v in updates.items()}

    def fix(m):
        raw = m.group(2)
        lead = len(raw) - len(raw.lstrip())
        body = raw.strip()
        try:
            payload = bytearray(_nib_decode(body))
            variables = script_variables(bytes(payload))
        except TransformError:
            return m.group(0)
        hit = False
        for name, value, off in variables:
            new = wanted.get(name.lower())
            if new is None or int(new) == value:
                continue
            struct.pack_into("<I", payload, off, int(new) & 0xFFFFFFFF)
            changed[0] += 1
            hit = True
        if not hit:
            return m.group(0)
        rebuilt = _nib_encode(bytes(payload))
        if len(rebuilt) != len(body):
            raise TransformError("re-encoded script changed length")
        return (b"<" + m.group(1) + b">" + raw[:lead] + rebuilt
                + raw[lead + len(body):] + b"</" + m.group(1) + b">")

    return SCRIPT_BLOCK.sub(fix, plain), changed[0]


# ---------------------------------------------------------------------------

def count_actors(plain: bytes):
    """(total, suppressed-on-easy, suppressed-on-normal, suppressed-on-hard)."""
    total = len(re.findall(rb'<Actor\b', plain))
    easy = len(re.findall(rb'Easy\s*=\s*"0"', plain))
    normal = len(re.findall(rb'Normal\s*=\s*"0"', plain))
    hard = len(re.findall(rb'Hard\s*=\s*"0"', plain))
    return total, easy, normal, hard


# ---------------------------------------------------------------------------
# enemy skill, straight out of the .ATR templates
# ---------------------------------------------------------------------------

ATR_STATS = ("ArmorLevel", "Weapon", "Stamina", "Stealth", "Leadership")
STAT_RX = {name: re.compile((r"(<%s>)\s*(\d)\s*(</%s>)" % (name, name)).encode())
           for name in ATR_STATS}

#: Ghost Recon names its templates by skill tier -- m02_rec_ak47_2.atr -- and the
#: three tiers really are different numbers: recruit sits at armour 1 and skills
#: 1-3, veteran at 2 and 2-4, elite at 3 and 3-5. Jungle Storm dropped that
#: scheme entirely and names templates by appearance (_g_cuba_whiteshirt.atr),
#: so tier renaming is a Ghost Recon-only trick and editing the numbers is the
#: dial that works on both.
ATR_TIER_RX = re.compile(r"_(rec|vet|eli)_", re.I)


def bump_atr_stats(plain: bytes, steps: int, stats=ATR_STATS, lo=1, hi=8):
    """Shift an `.ATR` template's skill integers, keeping the byte length.

    Every value in both games is a single digit, and the clamp keeps it that
    way, so the file length never moves and the archive slot is untouched.
    """
    changed = [0]
    out = plain
    for name in stats:
        def sub(m):
            cur = int(m.group(2))
            new = max(lo, min(hi, cur + steps))
            if new == cur:
                return m.group(0)
            changed[0] += 1
            pad = b" " * (len(m.group(0)) - len(m.group(1)) - len(m.group(3)) - 1)
            return m.group(1) + str(new).encode() + pad + m.group(3)
        out = STAT_RX[name].sub(sub, out)
    return out, changed[0]


def read_atr_stats(plain: bytes):
    out = {}
    for name in ATR_STATS:
        m = STAT_RX[name].search(plain)
        if m:
            out[name] = int(m.group(2))
    return out


COMPANY_RX = re.compile(rb'<Company\b([^>]*)>(.*?)</Company>', re.S | re.I)
ALLIED_RX = re.compile(rb'Allied\s*=\s*"1"', re.I)
FILE_RX = re.compile(rb'File\s*=\s*"([^"]+\.atr)"', re.I)


def enemy_templates(plain: bytes):
    """`.atr` filenames used by the hostile companies of one mission.

    A `<Company>` carrying `Allied="1"` is the player's side; every other
    company is hostile. Collecting the enemy list per mission is what keeps a
    "make the enemies tougher" edit from quietly buffing your own squad.
    """
    names = set()
    for m in COMPANY_RX.finditer(plain):
        if ALLIED_RX.search(m.group(1)):
            continue
        for f in FILE_RX.findall(m.group(2)):
            names.add(f.decode("latin1").lower())
    return names

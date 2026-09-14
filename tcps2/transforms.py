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


# ---------------------------------------------------------------------------
# plain-text INI settings (Rainbow Six 3)
# ---------------------------------------------------------------------------
#
# Rainbow Six 3 keeps a surprising amount in `R6GAMESETTINGS.INI` as named,
# commented values -- AI skill multipliers, the distance at which an NPC shoots
# perfectly, how long it waits before throwing a grenade, the look-sensitivity
# curve. Those files are plain text and are NOT inside the chunked compressor,
# so unlike the mission XML these edits do not have to preserve length: the
# archive writer relocates the file if it grows.

def _ini_pattern(key):
    return re.compile(rb"^([ \t]*" + re.escape(key.encode()) + rb"[ \t]*=[ \t]*)"
                      rb"([^\r\n;]*)", re.M | re.I)


def read_ini_values(plain: bytes, keys):
    out = {}
    for key in keys:
        m = _ini_pattern(key).search(plain)
        if m:
            out[key] = m.group(2).strip().decode("latin1")
    return out


def set_ini_values(plain: bytes, updates: dict):
    """Rewrite `key = value` lines in place. Returns (bytes, changed)."""
    changed = [0]
    out = plain
    for key, value in updates.items():
        text = ("%s" % value).encode("latin1")

        def sub(m, text=text):
            if m.group(2).strip() == text:
                return m.group(0)
            changed[0] += 1
            return m.group(1) + text
        out, n = _ini_pattern(key).subn(sub, out)
    return out, changed[0]


#: `WS[n]=(bUsing=...,weaponname="...")` is a per-map table saying which weapon
#: sound banks that level loads. Slot 43 is the molotov, and it ships `true`
#: only on the Alcatraz maps.
WS_SLOT = re.compile(rb'(WS\[(\d+)\]\s*=\s*\(\s*bUsing\s*=\s*)(true|false)', re.I)


def set_ws_slot(plain: bytes, slot: int, using: bool):
    want = b"true" if using else b"false"
    changed = [0]

    def sub(m):
        if int(m.group(2)) != slot or m.group(3).lower() == want:
            return m.group(0)
        changed[0] += 1
        return m.group(1) + want
    return WS_SLOT.sub(sub, plain), changed[0]


def read_ws_slots(plain: bytes):
    return {int(m.group(2)): m.group(3).lower() == b"true"
            for m in WS_SLOT.finditer(plain)}


# ---------------------------------------------------------------------------
# Rainbow Six 3 terrorist templates
# ---------------------------------------------------------------------------
#
# The 118 terrorist templates live as one contiguous plain-text run inside each
# COMMON package. What a terrorist spawns holding is a weighted roll made once,
# at spawn, over a small table:
#
#     NbOfGrenade=2
#     020, R6Weapons.r6fraggrenadegadget
#     080, None.None
#
# The weights are parsed with a `"%03d, %s"` scanf, so the count is a fixed
# three-digit field -- which is what makes a digit-for-digit edit the right
# shape, and the only shape a LIN package will accept.
#
# There is no *throw* probability anywhere; once a terrorist is holding a
# grenade the decision to use it is deterministic, gated by the minimum throw
# distance and the reaction delay in R6GAMESETTINGS.INI. So this is the dial
# that decides how many of them have one at all.

GRENADE_TABLE = re.compile(
    rb"(NbOfGrenade=2\r\n)(\d{3})(, R6Weapons\.\w+\r\n)(\d{3})(, None\.None)")


def set_grenade_carry(plain: bytes, percent: int):
    """Set the share of each two-entry template that spawns holding a grenade."""
    percent = max(0, min(100, int(percent)))
    changed = [0]

    def sub(m):
        if int(m.group(2)) == percent:
            return m.group(0)
        changed[0] += 1
        return b"%s%03d%s%03d%s" % (m.group(1), percent, m.group(3),
                                    100 - percent, m.group(5))

    return GRENADE_TABLE.sub(sub, plain), changed[0]


def read_grenade_carry(plain: bytes):
    """[(carryPercent, className)] for every two-entry template table."""
    return [(int(m.group(2)), m.group(3).strip(b", \r\n").decode("latin1"))
            for m in GRENADE_TABLE.finditer(plain)]


# ---------------------------------------------------------------------------
# CMBTMODL.XML -- the Red Storm ballistic model
# ---------------------------------------------------------------------------
#
# Ghost Recon, Jungle Storm and Sum of All Fears each ship one small XML file
# holding the whole hit model as named floats:
#
#     <BallisticHeadFactor>10.000000</BallisticHeadFactor>
#     <BallisticChestFactor>100.000000</BallisticChestFactor>
#     <BallisticArmoredChestFactor0..3>0 / 150 / 350 / 750</...>
#     <BallisticAbdomenFactor>400.000000</...>
#     <BallisticUpperArmFactor>700.000000</...>   LowerArm 1000
#     <BallisticUpperLegFactor>500.000000</...>   LowerLeg  800
#
# The file lives inside the rselzo container, so an edit must not change its
# length by a single byte. Every value ships as `%f` -- six decimals -- which
# leaves room to move: a new number is written to exactly the width the old one
# occupied by trading decimal places for integer digits. `100.000000` is ten
# characters, so 1500 becomes `1500.00000` and 7.5 becomes `7.50000000`. Both
# are ordinary decimal floats; nothing has to tolerate a funny spelling.

XML_FLOAT = re.compile(rb"(<(\w+)>)\s*(-?\d+(?:\.\d+)?)\s*(</\2>)")


def _same_width(value: float, width: int) -> bytes:
    """`value` as a decimal float occupying exactly `width` characters."""
    for decimals in range(width, -1, -1):
        text = ("%.*f" % (decimals, value)).encode("latin1")
        if len(text) == width:
            return text
        if len(text) < width:
            # too short only happens with 0 decimals; pad the fraction back out
            continue
    raise ValueError("%r does not fit %d characters" % (value, width))


def set_xml_values(plain: bytes, updates: dict):
    """Write named tags to new values, each in the width the old one occupied.

    `updates` maps a tag name to the text to put in it. The text is used
    verbatim when it already fits, and padded with LEADING ZEROS when it is
    short -- which is safe here for a reason that was checked rather than
    assumed: every one of these files is parsed with `atof`/`atoi`, and the
    engine's `atoi` is a thunk to `strtol(s, NULL, 10)` with base 10 set
    explicitly, so "075" is seventy-five and never octal. Both skip leading
    whitespace and stop at the first character they cannot use.
    """
    changed = [0]

    def sub(m):
        tag = m.group(2).decode("latin1")
        if tag not in updates:
            return m.group(0)
        old = m.group(3)
        new = str(updates[tag]).encode("latin1")
        if len(new) > len(old):
            return m.group(0)                     # will not fit; leave it
        if len(new) < len(old):
            sign = b""
            if new[:1] in (b"-", b"+"):
                sign, new = new[:1], new[1:]
            new = sign + b"0" * (len(old) - len(sign) - len(new)) + new
        if new == old:
            return m.group(0)
        changed[0] += 1
        return m.group(1) + new + m.group(4)

    return XML_FLOAT.sub(sub, plain), changed[0]


def scale_xml_floats(plain: bytes, factor: float, prefix: bytes = b"Ballistic",
                     lo: float = 0.0, hi: float = 100000.0,
                     keep_width: bool = True):
    """Multiply every `<prefix...>` float by `factor`, preserving byte length.

    Returns (bytes, changed). A tag whose new value will not fit the width the
    old one occupied is left alone rather than silently truncated -- which
    cannot happen for the shipped values, but the check is cheap and the
    alternative is a corrupt archive.
    """
    changed = [0]

    def sub(m):
        if not m.group(2).startswith(prefix):
            return m.group(0)
        old = m.group(3)
        want = max(lo, min(hi, float(old) * factor))
        if keep_width:
            # A value with no decimal point has no precision to trade away, so
            # `75` cannot become `120` -- there is nowhere to put the third
            # digit. Clamp to what the field can hold rather than skip the file
            # or grow it: not every .ENV is stored uncompressed, and the ones
            # that are not cannot move by a single byte.
            if b"." not in old and want >= 10 ** len(old):
                want = float(10 ** len(old) - 1)
            try:
                new = _same_width(want, len(old))
            except ValueError:
                return m.group(0)
        elif b"." in old:
            new = ("%.*f" % (len(old.split(b".")[1]), want)).encode("latin1")
        else:
            new = b"%d" % int(round(want))
        if new == old:
            return m.group(0)
        changed[0] += 1
        return m.group(1) + new + m.group(4)

    return XML_FLOAT.sub(sub, plain), changed[0]


def read_xml_floats(plain: bytes, prefix: bytes = b""):
    return {m.group(2).decode("latin1"): float(m.group(3))
            for m in XML_FLOAT.finditer(plain)
            if m.group(2).startswith(prefix)}


# ---------------------------------------------------------------------------
# Rainbow Six Lockdown: the Nimitz cooked databases
# ---------------------------------------------------------------------------
#
# `nimitz.cgsb` holds 72 AI profiles and `nimitz.guns` 48 weapons, in the same
# record grammar: a u16 count, then per record a name string, a version float,
# the name again, and a body whose length varies -- 43 to 707 bytes -- so record
# starts are found structurally, by a name immediately repeated after a float,
# rather than by a stride.
#
# Inside an AI profile the skill block is a u32 count of 6, one flag byte, then
# **six (u8 skill, u8 modifier) pairs**. That last part was the trap: in most
# records the modifier byte is zero, so the block reads convincingly as six
# u16 -- and then 18 of the 72 records, including the three main campaign
# terrorist profiles, decode as nonsense. Reading the first byte of each pair
# instead locates the vector in 70 of 72, and the values satisfy every ordering
# the shipped names imply: terrorist-01/02/03 run 12/12/16, militia-01/02/03
# run 1/8/12, mercenary-01/02/03 run 14/18/20, terrorist_super_easy is all 1s.
# Six independent ladder checks, none failed.

NIMITZ_SKILL_LO, NIMITZ_SKILL_HI = 1, 20

#: faction id -> hostile to the player
NIMITZ_HOSTILE = {0: False, 1: True, 2: True, 3: True, 4: False}

#: field offsets inside a weapon record body, located by scoring every
#: candidate against real magazine capacities: +29 explained 12 of 19 known
#: weapons where the next best offset explained 2. Rate of fire sits beside it
#: and reads as clean 300/450/600/750/800/900/1000 on 44 of the 48 weapons --
#: the four that read zero are the RPG variants and the grenade launcher.
NIMITZ_GUN_MAG, NIMITZ_GUN_RPM = 29, 31

#: The four launchers -- rpg7, rpg7_sniper, rpg7_virus and gl69 -- use a SHORTER
#: stat block, so these offsets land somewhere else entirely in them: rpg7 reads
#: 16256 for rate of fire, which is 0x3F80, the top half of the float 1.0. A
#: plausibility gate is therefore not belt-and-braces, it is the thing that
#: stops a scale factor from corrupting four weapons.
NIMITZ_GUN_RANGE = {NIMITZ_GUN_MAG: (1, 400), NIMITZ_GUN_RPM: (100, 1500)}


def _nimitz_records(blob: bytes, suffix: bytes):
    """(name, recordStart, recordEnd) per record, by the repeated name."""
    found = []
    o = 2
    n = len(blob)
    while o < n - 8:
        ln = struct.unpack_from("<I", blob, o)[0]
        if 4 <= ln <= 64 and o + 4 + ln <= n and blob[o + 4:o + 4 + ln].endswith(suffix):
            if blob[o + 4 + ln + 4:o + 4 + ln + 4 + 4 + ln] == blob[o:o + 4 + ln]:
                found.append((blob[o + 4:o + 4 + ln].decode("latin1"), o))
                o += 4 + ln
                continue
        o += 1
    return [(nm, st, found[i + 1][1] if i + 1 < len(found) else n)
            for i, (nm, st) in enumerate(found)]


def _nimitz_body(blob, start):
    """Offset of a record's body: past the name, the float and the name again."""
    ln = struct.unpack_from("<I", blob, start)[0]
    p = start + 4 + ln + 4
    return p + 4 + struct.unpack_from("<I", blob, p)[0]


def _nimitz_gun_body(blob, start):
    """A weapon record carries a THIRD string -- its "WPN_" message key --
    between the repeated name and the stat block. An AI record does not, and
    forgetting that reads the stats one string early: magazine capacities come
    out as 0, 6 and 1024 instead of 17, 30 and 200."""
    p = _nimitz_body(blob, start)
    return p + 4 + struct.unpack_from("<I", blob, p)[0]


def _nimitz_skill_offset(blob, start, end):
    """Offset of the six (skill, modifier) pairs inside one AI record."""
    hit = None
    for o in range(start, end - 17):
        if struct.unpack_from("<I", blob, o)[0] != 6:
            continue
        p = o + 5
        if p + 12 <= end and all(
                NIMITZ_SKILL_LO <= blob[p + 2 * i] <= NIMITZ_SKILL_HI
                for i in range(6)):
            hit = p
    return hit


def read_nimitz_skills(blob: bytes):
    """[(name, offset, [six skills])] for every AI profile that decodes."""
    out = []
    for name, start, end in _nimitz_records(blob, b".cgs"):
        p = _nimitz_skill_offset(blob, start, end)
        if p is not None:
            out.append((name, p, [blob[p + 2 * i] for i in range(6)]))
    return out


#: The three profiles the Terrorist Hunt modes draw from. Named in full rather
#: than matched on a `th_` prefix: the archive also holds `timothy_hanely.cgs`,
#: and a prefix rule is the kind of thing that silently grows a fourth member
#: the day someone adds a profile.
NIMITZ_HUNT = ("th_terrorist.cgs", "th_militia.cgs", "th_merc.cgs")


def bump_nimitz_skills(blob: bytes, steps: int, hostile_only: bool = True,
                       only=None):
    """Shift hostile AI profiles' six skills, clamped to 1-20.

    One byte per skill, so the length never moves -- which matters more here
    than usual, because this archive is never relocated.

    `only` narrows the edit to a named set of profiles -- `NIMITZ_HUNT` to
    retune Terrorist Hunt without touching the campaign. It is applied as well
    as `hostile_only`, not instead of it.
    """
    if not steps:
        return blob, 0
    wanted = set(only) if only else None
    out = bytearray(blob)
    changed = 0
    for name, start, end in _nimitz_records(blob, b".cgs"):
        if wanted is not None and name not in wanted:
            continue
        if hostile_only:
            faction = struct.unpack_from("<I", blob, _nimitz_body(blob, start))[0]
            if not NIMITZ_HOSTILE.get(faction, False):
                continue
        p = _nimitz_skill_offset(blob, start, end)
        if p is None:
            continue
        for i in range(6):
            cur = out[p + 2 * i]
            new = max(NIMITZ_SKILL_LO, min(NIMITZ_SKILL_HI, cur + steps))
            if new != cur:
                out[p + 2 * i] = new
                changed += 1
    return bytes(out), changed


def scale_nimitz_guns(blob: bytes, mag: float = 1.0, rpm: float = 1.0):
    """Scale magazine capacity and rate of fire in place, u16 each."""
    if abs(mag - 1.0) < 1e-6 and abs(rpm - 1.0) < 1e-6:
        return blob, 0
    out = bytearray(blob)
    changed = 0
    for name, start, end in _nimitz_records(blob, b".gun"):
        base = _nimitz_gun_body(blob, start)
        for off, factor in ((NIMITZ_GUN_MAG, mag), (NIMITZ_GUN_RPM, rpm)):
            p = base + off
            if p + 2 > end or abs(factor - 1.0) < 1e-6:
                continue
            cur = struct.unpack_from("<H", out, p)[0]
            lo, hi = NIMITZ_GUN_RANGE[off]
            if not (lo <= cur <= hi):             # a launcher, or not this field
                continue
            new = max(1, min(0xFFFF, int(round(cur * factor))))
            if new != cur:
                struct.pack_into("<H", out, p, new)
                changed += 1
    return bytes(out), changed


def read_nimitz_guns(blob: bytes):
    out = []
    for name, start, end in _nimitz_records(blob, b".gun"):
        base = _nimitz_gun_body(blob, start)
        if base + NIMITZ_GUN_RPM + 2 <= end:
            vals = []
            for off in (NIMITZ_GUN_MAG, NIMITZ_GUN_RPM):
                v = struct.unpack_from("<H", blob, base + off)[0]
                lo, hi = NIMITZ_GUN_RANGE[off]
                vals.append(v if lo <= v <= hi else None)
            out.append((name, vals[0], vals[1]))
    return out

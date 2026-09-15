"""Terrorist loadouts and skills on the two Unreal discs that ship them.

Rainbow Six 3 and Ghost Recon 2 keep every enemy archetype as a plain CRLF
text block inside `COMMON.LIN`, and the block already describes a *weighted
roll* rather than a fixed kit::

    Version=8

    Type=Terrorist

    NbOfWeapon=3
    025, R63rdWeapons.AssaultL85A1
    025, R63rdWeapons.PistolUSP
    050, R63rdWeapons.SubMP5A4

    NbOfGrenade=2
    090, R6Weapons.r6fraggrenadegadget
    010, None.None

    NbOfTag=0
    NbOfSeePlayerEvent=0
    NbOfHearPlayerEvent=0

    Coward=0
    DeskJockey=0
    Normal=0
    Hardened=100
    SuicideBomber=0
    PSniper=0

    RndVariation=10
    Assault=70
    Demolitions=50
    Electronics=50
    SSniper=50
    Stealth=70
    SelfControl=70
    Leadership=50
    Observation=90

    Flashlight=0
    GasMask=0

The three-digit weights sum to 100 and the game rolls against them, so the
randomiser this module offers is the game's own -- not something bolted on.
That multi-entry tables ship in retail (12 of Rainbow Six 3's 118, 6 of Ghost
Recon 2's 73) is the evidence the roll really runs.

Measured, this session, from the backup store rather than a played-on disc:

===================  =========  ============  ==================================
disc                 templates  table sizes   snipers already present
===================  =========  ============  ==================================
Rainbow Six 3              118  1:106 2:4      SniperPSG1 x2, SniperM82A1 x2
                                3:5   4:3
Ghost Recon 2               73  1:67  2:2      SniperPSG1 x2, SniperM82A1 x2
                                3:3   4:1
Advanced Warfighter          0  --             none -- the table does not exist
===================  =========  ============  ==================================

Rainbow Six 3 carries the identical 118 in all three of `COMMON.LIN`,
`COMMONOFF.LIN` and `COMMON_SS.LIN`, which is why the profile edits the set.

The one hard constraint
-----------------------

`lin.substitute` refuses any edit that changes the decompressed length, so a
weapon *line* can never be added or removed. Two things are still free:

* **The weights.** They are zero-padded to three digits, so any value from 000
  to 100 is a digit-for-digit rewrite. Re-weighting is completely safe.
* **The class name, within its own byte length.** The roster table elsewhere in
  `COMMON.LIN` lists 43 classes; grouped by the length of the full dotted name
  they fall into the families in `FIREARMS` below. Three of those groups
  contain a sniper rifle, which is what makes "put snipers among them" possible
  without touching a single byte of length:

      len 23  AssaultAUG  Pistol92FS  PistolMk23  -> SniperPSG1
      len 24  AssaultAK47 AssaultG36K AssaultG3A3 -> SniperM82A1
      len 27  AssaultFAMASG2                      -> SniperAWCovert

  `AssaultAK47` alone accounts for 21 of Rainbow Six 3's weapon lines, so the
  reachable share is large.

Turning a `NbOfWeapon=1` template into a real two-way roll would need ~31 more
bytes for the extra line, which the length rule forbids outright. Variety
therefore comes from spreading *different* weapons across the archetypes a
level places, plus re-weighting the tables that already have more than one
entry -- not from giving one archetype a wider roll.

What is deliberately NOT here
-----------------------------

The Rainbow side. Every one of the 118 blocks is `Type=Terrorist`; there is no
team-mate equivalent. Rainbow's kits live in `m_PlayerEquipment`,
`m_LoiselleEquipment`, `m_PriceEquipment` and `m_WeberEquipment`, which are
name-table entries whose *values* sit in export data this toolkit cannot yet
index. The multiplayer defaults are reachable -- they are string constants in
script -- and `MP_DEFAULTS` records where, but single-player team-mate kits are
not offered because they cannot yet be written.
"""

from __future__ import annotations

import random
import re

from .rseguns import _same_width

#: Firearms that the disc ACTUALLY ISSUES TO ENEMIES, keyed by the length of
#: the full dotted name. This is derived from the file being edited, not from
#: a fixed list -- see `palette()`.
#:
#: The first version of this module took its palette from the weapon ROSTER,
#: the 43-class table elsewhere in `COMMON.LIN`. That was wrong and it hung the
#: game on an infinite loading screen. A class being in the roster means it
#: exists; it does NOT mean a terrorist can be spawned holding one. Only 23 of
#: the 43 are ever issued to enemies, and giving them one of the other 20 --
#: `AssaultG36K` and `SubTMP` were the two that got through -- asks the level
#: to spawn a character with third-person assets that were never cooked for it.
#:
#: Deriving the palette from the file makes that failure impossible by
#: construction: a weapon can only ever be replaced by one the disc already
#: hands to some other enemy.
FIREARMS_FALLBACK = {}


def palette(plain: bytes) -> dict:
    """{nameLength: [class, ...]} built from this file's own enemy tables.

    Only firearms are collected -- `R6Weapons.*` gadgets and `None.None` are
    left out, so a rifle can never become a gas mask or a grenade.
    """
    seen = {}
    for m in ENTRY.finditer(plain):
        cls = m.group(2).decode("latin-1")
        if not cls.startswith("R63rdWeapons."):
            continue
        seen.setdefault(len(cls), set()).add(cls)
    return {k: sorted(v) for k, v in seen.items()}


#: What each firearm is, so a swap can prefer a sideways move to a silly one.
ROLE = {
    "Pistol": ("Pistol92FS", "PistolDesertEagle50", "PistolMac119",
               "PistolMk23", "PistolSR2", "PistolUSP"),
    "Sub": ("SubMac119", "SubMP5A4", "SubMP5SD5", "SubP90", "SubSR2",
            "SubTMP", "SubUMP"),
    "Assault": ("AssaultAK47", "AssaultAUG", "AssaultFAMASG2",
                "AssaultG36K", "AssaultG3A3", "AssaultGalilARM",
                "AssaultL85A1", "AssaultM16A2", "AssaultM4", "AssaultTAR21"),
    "LMG": ("LMGM249", "LMGM60E4"),
    "Shotgun": ("ShotgunM1", "ShotgunUSAS12"),
    "Sniper": ("SniperAWCovert", "SniperM82A1", "SniperPSG1"),
}

#: The reverse map, built once and keyed in lower case. The disc spells some
#: class names in lower case -- `sniperm82a1`, `r6fraggrenadegadget` -- so the
#: engine plainly compares them case-insensitively, and a case-sensitive lookup
#: here would classify a lower-case sniper as "no role" and let a swap take it
#: away, which is the one thing every mode is supposed to prevent.
ROLE_OF = {leaf.lower(): role
           for role, leaves in ROLE.items() for leaf in leaves}


def role_of(name) -> str:
    """The category of a weapon class, by leaf name, regardless of spelling."""
    if isinstance(name, bytes):
        name = name.decode("latin-1")
    return ROLE_OF.get(name.split(".")[-1].lower())

#: The three rifles a same-length swap can reach.
SNIPERS = {23: "R63rdWeapons.SniperPSG1",
           24: "R63rdWeapons.SniperM82A1",
           27: "R63rdWeapons.SniperAWCovert"}

#: Where the multiplayer defaults live in script, for the record. These are
#: `EX_StringConst` operands -- NUL-terminated and self-delimiting, so an
#: equal-length swap is safe -- but they are not wired to an option yet.
MP_DEFAULTS = (
    ("R6MultiPlayerGameInfo::PostLogin", 0x1CA0CE),
    ("R6NoRules::Login", 0x1CE002),
)

#: One template block, from `Version=` to the `GasMask=` that closes it.
TEMPLATE = re.compile(
    rb"Version=\d+\r\n\r\nType=Terrorist\r\n.*?GasMask=\d+\r\n",
    re.S)

#: A weighted table: the count line, then that many `NNN, Class` lines.
TABLE = re.compile(rb"(NbOf(?:Weapon|Grenade)=(\d+)\r\n)((?:\d{3}, [\w.]+\r\n)*)")

#: One weighted entry inside a table.
ENTRY = re.compile(rb"(\d{3}), ([\w.]+)\r\n")

#: A plain `Key=Number` field.
FIELD = re.compile(rb"(\b%s=)(\d+)(\r\n)")


class LoadoutError(Exception):
    pass


def templates(plain: bytes) -> list:
    """(start, end) for every terrorist template in a decompressed COMMON."""
    return [(m.start(), m.end()) for m in TEMPLATE.finditer(plain)]


def _leaf(name: bytes) -> str:
    return name.decode("latin-1").split(".")[-1]


def _set_field(block: bytes, key: str, value) -> bytes:
    """Rewrite `key=` inside one block, keeping the field's own width.

    The width clamp is `rseguns._same_width`, so a two-character field asked
    for 150 writes 99 rather than declining to move at all.
    """
    rx = re.compile(rb"(\b" + key.encode() + rb"=)(\d+)(\r\n)")

    def sub(m):
        text = m.group(2).decode("latin-1")
        # `_same_width` clamps an oversized number down to all-9s, which is the
        # right answer when the request overflows the field. Here it is the
        # wrong one: a one-character `Assault=0` asked for 90 would be written
        # 9, moving the dial the opposite way from the one the player chose.
        # Exactly one template on each disc is written this narrowly -- the
        # all-zero rookie -- so leaving it alone costs nothing.
        if len("%d" % int(round(value))) > len(text):
            return m.group(0)
        out = _same_width(text, value)
        if out is None:
            return m.group(0)
        return m.group(1) + out.encode("latin-1") + m.group(3)

    return rx.sub(sub, block, count=1)


def _swap_firearm(name: bytes, rng, pal, keep_role=True):
    """A different firearm of exactly the same byte length, or the same one."""
    text = name.decode("latin-1")
    group = pal.get(len(text))
    if not group:
        return name
    leaf = text.split(".")[-1]
    role = role_of(leaf)
    if role == "Sniper":
        # The disc ships only four sniper lines. Every mode may ADD marksmen;
        # none may take one away, or "more variety" would read in-game as
        # fewer of the enemies that make a level interesting.
        return name
    pool = [c for c in group if c != text]
    if keep_role and role:
        # Prefer a weapon of a comparable class; a rifleman who becomes a
        # pistolero is a nerf, not variety.
        same = [c for c in pool if role_of(c) == role]
        # No same-class alternative means this weapon is the only one of its
        # kind at this byte length, and swapping it would change the archetype
        # rather than vary it. That matters most for the snipers: each of the
        # three is alone in its length group, so a free choice would quietly
        # REMOVE the marksmen the disc already ships.
        pool = same
    if not pool:
        return name
    return rng.choice(pool).encode("latin-1")


def retune(plain: bytes, weapons="stock", marksmanship=None, seed=1701,
           skip=()):
    """Rewrite every terrorist template. Returns (plain, stats).

    The result is always the same length as the input, which is what
    `lin.substitute` demands. `weapons` is one of:

    ``stock``    leave the tables alone
    ``varied``   give neighbouring archetypes different guns of the same class
    ``snipers``  as ``varied``, and turn a share of the reachable slots into
                 rifles, raising those archetypes' marksmanship to match
    ``chaos``    ignore weapon class when swapping, and re-roll the weights of
                 every table that already has more than one entry

    `skip` is a set of template indices to leave exactly as they shipped, and
    it exists because equal *length* is not the whole rule. The stock text is
    enormously repetitive -- a hundred templates differing in a few digits --
    so zlib packs it very tightly, and the container gives each chunk back only
    the room its original bytes needed. Variety is the removal of precisely the
    redundancy that packing relies on, so a rewrite can be the same length and
    still not fit. `fit_to_lin` fills this set with the templates that sit in
    chunks with no slack, and leaves every other template at full strength.
    """
    if weapons not in ("stock", "varied", "snipers", "chaos"):
        raise LoadoutError("unknown weapons mode %r" % weapons)
    spans = templates(plain)
    if not spans:
        return plain, {"templates": 0, "weapons": 0, "snipers": 0, "skills": 0}

    pal = palette(plain)
    out = bytearray(plain)
    stats = {"templates": len(spans), "weapons": 0, "snipers": 0, "skills": 0}

    for index, (lo, hi) in enumerate(spans):
        rng = random.Random("%s:%d:%d" % (weapons, seed, index))
        block = bytes(out[lo:hi])
        original = block

        # A skipped template is left byte-for-byte as it shipped. Because the
        # choice of replacement depends only on the template's own index,
        # skipping one never changes what any other template gets -- which is
        # what lets the fitter add to this set and re-test without the whole
        # result shifting under it.
        if index in skip:
            continue
        if weapons != "stock":
            block = _retune_weapons(block, weapons, rng, index, stats, pal)
        if marksmanship is not None:
            block = _retune_skill(block, marksmanship, stats)

        if len(block) != len(original):
            raise LoadoutError(
                "template %d changed length %d -> %d; refusing to write"
                % (index, len(original), len(block)))
        out[lo:hi] = block

    if len(out) != len(plain):
        raise LoadoutError("retune changed the file length")
    return bytes(out), stats


def _retune_weapons(block, mode, rng, index, stats, pal):
    """The weapon half of one template."""
    m = TABLE.search(block)
    if m is None or not m.group(1).startswith(b"NbOfWeapon"):
        return block
    table = m.group(3)
    entries = ENTRY.findall(table)
    if not entries:
        return block

    # Every third archetype keeps its issued weapon, so a level still reads as
    # a coherent force rather than a jumble.
    rewrite = mode == "chaos" or index % 3 != 0
    new_lines = []
    for weight, name in entries:
        picked = name
        if rewrite:
            picked = _swap_firearm(name, rng, pal,
                                   keep_role=(mode != "chaos"))
        if mode == "snipers" and index % 4 == 1:
            # only a sniper this disc already issues to SOMEONE
            here = pal.get(len(name.decode("latin-1")), ())
            sniper = next((c for c in here if role_of(c) == "Sniper"), None)
            if sniper and role_of(name) != "Sniper":
                picked = sniper.encode("latin-1")
                stats["snipers"] += 1
        if picked != name:
            stats["weapons"] += 1
        new_lines.append(b"%s, %s\r\n" % (weight, picked))

    new_table = b"".join(new_lines)
    if mode == "chaos" and len(entries) > 1:
        new_table = _reweight(new_table, rng)
    if len(new_table) != len(table):
        raise LoadoutError("weapon table changed length")
    block = block[:m.start(3)] + new_table + block[m.end(3):]

    if stats["snipers"] and mode == "snipers" and index % 4 == 1:
        # A rifle in the hands of someone with no marksmanship is just a slow
        # rifle, so the archetype that gets one is told to use it.
        block = _set_field(block, "SSniper", 90)
        block = _set_field(block, "Observation", 95)
    return block


def _reweight(table, rng):
    """Re-roll a multi-entry table's weights so they still total 100."""
    entries = ENTRY.findall(table)
    n = len(entries)
    cuts = sorted(rng.randint(5, 95) for _ in range(n - 1))
    weights, last = [], 0
    for c in cuts:
        weights.append(c - last)
        last = c
    weights.append(100 - last)
    # A zero-weight entry is a wasted line; give it back a point from the
    # biggest share rather than leaving a weapon that can never be rolled.
    for i, w in enumerate(weights):
        if w <= 0:
            big = weights.index(max(weights))
            weights[big] -= 1
            weights[i] = 1
    return b"".join(b"%03d, %s\r\n" % (w, name)
                    for w, (_old, name) in zip(weights, entries))


def _retune_skill(block, level, stats):
    """Move the marksmanship fields together. `level` is 0..100."""
    before = block
    for key, scale in (("Assault", 1.0), ("SSniper", 1.0),
                       ("Observation", 1.0), ("SelfControl", 0.9)):
        block = _set_field(block, key, min(100, int(round(level * scale))))
    # Less spread means the shots land where they were aimed.
    block = _set_field(block, "RndVariation", max(0, int(round(30 - level * 0.25))))
    if block != before:
        stats["skills"] += 1
    return block


#: What each disc actually ships, measured from the backup store. The cards
#: quote these rather than a round number, so the wording cannot drift away
#: from the data if a disc turns out to differ.
SHIPPED = {
    "r6_3_slus20883": {"templates": 118, "multi": 12, "snipers": 4,
                       "files": r"/COMMON(OFF|_SS)?\.LIN$"},
    "gr2_slus21105": {"templates": 73, "multi": 6, "snipers": 4,
                      "files": r"/COMMON(OFF)?\.LIN$"},
}

MODES = ("stock", "varied", "snipers", "chaos")


def cards(pid, prefix, group):
    """The two enemy-loadout cards, worded for whichever disc this is."""
    from .model import CHOICE, INT, Choice, Setting

    facts = SHIPPED[pid]
    n, multi, snipers = facts["templates"], facts["multi"], facts["snipers"]
    return [
        Setting(prefix + "enemy_loadout", "What the enemies are carrying",
                CHOICE, "stock", group, confidence="measured", touches="data",
                choices=[
                    Choice("stock", "Leave the issued weapons alone"),
                    Choice("varied", "More variety"),
                    Choice("snipers", "More variety, and marksmen among them"),
                    Choice("chaos", "Anything goes"),
                ],
                help="This disc describes each enemy archetype as a weighted "
                     "roll over a small weapon table, and ships %d of them -- "
                     "%d already roll over more than one weapon, which is how "
                     "you can tell the roll is real and not a dormant field. "
                     "MORE VARIETY gives neighbouring archetypes different "
                     "guns of the same class, so a level stops being eight men "
                     "with the same rifle. MARKSMEN also turns a share of them "
                     "into snipers and raises just those men's marksmanship to "
                     "match -- the disc ships only %d sniper in all %d "
                     "templates. ANYTHING GOES drops the rule that a swap "
                     "keeps the weapon's class, and re-rolls the odds on every "
                     "table that has more than one entry."
                     % (n, multi, snipers, n),
                caution="A weapon can only be exchanged for one whose name is "
                        "the same length in bytes, because the container this "
                        "lives in cannot change size. That is not a small "
                        "restriction, but it does reach all three sniper "
                        "rifles. Every mode may add marksmen; none removes the "
                        "ones the disc already has."),
        Setting(prefix + "enemy_aim", "How well they shoot", INT, 0, group,
                minimum=0, maximum=100, unit="/100",
                confidence="measured", touches="data",
                help="Each archetype carries its own marksmanship, spread over "
                     "Assault, SSniper and Observation, plus a RndVariation "
                     "that scatters the shots. This sets all of them together "
                     "and tightens the scatter as it rises. Leave it at 0 to "
                     "keep each archetype's own numbers -- the stock spread "
                     "runs from a rookie who cannot shoot at all up to 100.",
                caution="One template on each disc writes these fields one "
                        "character wide. It is the deliberate cannot-shoot "
                        "rookie, and it is left alone rather than being given "
                        "a single-digit fraction of what you asked for."),
    ]


def edits(values, prefix, pattern):
    """The FileEdit list these two cards imply, or nothing if both are stock."""
    from .model import FileEdit

    mode = values.get(prefix + "enemy_loadout", "stock")
    aim = int(values.get(prefix + "enemy_aim", 0) or 0)
    if mode not in MODES:
        raise LoadoutError("unknown weapons mode %r" % mode)
    # Always emit, even for "stock". The file on the disc may already carry a
    # previous run's edits, and the only way to take them off is to rewrite it
    # from the shipped bytes -- which is exactly what an edit with nothing to
    # change does, now that edits are applied to the original. Returning
    # nothing here would leave an earlier choice baked in with no way for the
    # page to undo it.
    if mode == "stock" and aim == 0:
        return [FileEdit("enemy_loadout", pattern, "", {"weapons": "stock"},
                         "enemy templates: as the game shipped")]
    params = {"weapons": mode}
    if aim:
        params["marksmanship"] = aim
    told = {"stock": "", "varied": "varied weapons",
            "snipers": "varied weapons, marksmen among them",
            "chaos": "weapons and odds re-rolled"}[mode]
    if aim:
        told = (told + ", " if told else "") + "marksmanship %d/100" % aim
    return [FileEdit("enemy_loadout", pattern, "", params,
                     "enemy templates: " + told)]


#: How many times the fitter may widen the skip set before giving up. Each
#: pass can only add templates, so this bounds a loop that must terminate.
MAX_FIT_PASSES = 12


def fit_to_lin(container, plain, weapons="stock", marksmanship=None,
               seed=1701):
    """The strongest retune this LIN can actually hold. Returns (plain, stats).

    Equal length gets a candidate past `lin.substitute`'s first check but not
    its second: every chunk must still deflate back into the byte count its
    original occupied. Variety is the loss of the redundancy that made the
    stock text pack so well, so some chunks will refuse it.

    The slack is wildly uneven, which is why this works per chunk rather than
    turning one dial down over the whole file. On Ghost Recon 2 the templates
    straddle three chunks: the first is mostly other data already packed at
    0.32 and has no room at all, while the next two are almost entirely
    template text at 0.06 and 0.14 and will swallow anything. Backing the whole
    file off to satisfy the tight one would throw away every change the loose
    ones could have taken. So each failing chunk surrenders only the templates
    that overlap it, and the rest keep full strength.
    """
    from . import lin

    parts, _tail = lin.parse(container)
    bounds, pos = [], 0
    for raw, comp, _off in parts:
        bounds.append((pos, pos + raw, comp))
        pos += raw

    spans = templates(plain)
    skip = set()
    for _ in range(MAX_FIT_PASSES):
        candidate, stats = retune(plain, weapons=weapons,
                                  marksmanship=marksmanship, seed=seed,
                                  skip=skip)
        blocked = False
        for lo, hi, comp in bounds:
            if candidate[lo:hi] == plain[lo:hi]:
                continue
            if lin._deflate_within(candidate[lo:hi], comp) is not None:
                continue
            # This chunk cannot hold what it was given. Give up exactly the
            # templates inside it, and no others.
            blocked = True
            for index, (tlo, thi) in enumerate(spans):
                if tlo < hi and thi > lo:
                    skip.add(index)
        if not blocked:
            stats["skipped"] = len(skip)
            return candidate, stats

    raise LoadoutError(
        "enemy loadouts could not be fitted into this container after %d "
        "passes; %d of %d templates had already been given up"
        % (MAX_FIT_PASSES, len(skip), len(spans)))

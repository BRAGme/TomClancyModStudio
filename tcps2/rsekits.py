"""What Price, Weber and Loiselle carry, per mission.

The question was whether teammates could be given tear gas, white phosphorus
or a different grenade. They can, and not through bytecode: every mission's
`/MAPS/<map>.INI` spells the whole squad's kit out in plain text::

    m_PriceEquipment=(szPrimaryWeapon="R63rdWeapons.AssaultG3A3",
                      szSecondaryWeapon="R63rdWeapons.Pistol92FS",
                      szPrimaryItem="R6Weapons.R6FlashBangGadget",
                      szSecondaryItem="R6Weapons.R6FragGrenadeGadget")

Each operative gets four of these -- plain, silenced, Terrorist Hunt, and
silenced Terrorist Hunt -- so twelve keys per map across the three of them.

What may be written into a kit, and why
---------------------------------------

Handing an AI a weapon it has no third-person assets for is exactly what
produced an infinite load and then a hard crash when the enemy weapon tables
were first re-rolled: the palette had to be derived from the classes the disc
actually issues rather than from the full weapon roster. Both options here obey
that lesson, in two different ways.

The **gadget** choices only ever write a class the disc already issues to
somebody -- the counts are on `GADGETS` below, measured across all 67 map INIs.

**Match the player's loadout** goes further and invents nothing at all: every
value it writes is lifted out of the same map's own `m_PlayerEquipment`, so by
construction that map already ships whatever it names. That is what makes it
safe to move the weapon slots, which no other option here does.

What it is not
--------------

On PC, "give squad my loadout" copies the kit you picked on the planning
screen. This is a data edit, so it copies the mission's DEFAULT player kit --
the one the game hands you before you change anything. Pick something else in
the menu and the squad keeps the default. Mirroring a runtime choice would mean
re-assembling bytecode, which is the one path on this disc that has repeatedly
cost an evening.

The sound-bank coupling
-----------------------

Each map also carries a `WS[0..43]` table naming which weapon sound banks that
level loads. It is NOT a whitelist of what may be equipped -- Parade issues the
player a grenade launcher, phosphorus and smoke while all three read
`bUsing=false` -- but a bank that is not loaded is a sound that cannot play. So
whenever this module puts a gadget into a kit it also turns that gadget's own
WS slot on, which is cheap and removes the question.

The slot numbers are read out of the table itself rather than assumed: the
`weaponname=` field in each `WS[n]` entry is matched against the gadget's class
name, so a map that orders its table differently still gets the right slot.
"""

from __future__ import annotations

import re

#: label -> the class name the INI wants, and nothing else changes.
#:
#: Every one of these is a gadget the disc already puts in somebody's kit,
#: counted across all 67 map INIs: frag 434, breaching charge 361, flashbang
#: 276, smoke 81, phosphorus 33, tear gas 8, gas mask 8. Nothing here is
#: invented -- that is the whole safety argument, because the enemy weapon
#: tables crashed precisely for taking a palette from the roster instead of
#: from the file.
#:
#: Deliberately absent: `R6ClaymoreGadget`, `R6RemoteChargeGadget` and
#: `R6MolotovGadget`. Each appears 42 times across the INIs, but every one of
#: those is a `WS[n]` sound-bank row rather than a kit -- they are issued to
#: nobody, and the molotov's bank is switched on only for Alcatraz, where the
#: terrorists throw them. A class having a sound bank is not evidence that a
#: Rainbow operative can carry it, so they stay out until something proves it.
GADGETS = {
    "frag": "R6Weapons.R6FragGrenadeGadget",
    "flashbang": "R6Weapons.R6FlashBangGadget",
    "smoke": "R6Weapons.R6SmokeGrenadeGadget",
    "teargas": "R6Weapons.R6TearGasGrenadeGadget",
    "phosphorus": "R6Weapons.R6PhosphorusGrenadeGadget",
    "breaching": "R6Weapons.R6BreachingChargeGadget",
    "gasmask": "R6Weapons.R6GasMask",
    "gl_he": "R6Weapons.R6GrenadeLauncherHE",
    "gl_rp": "R6Weapons.R6GrenadeLauncherRP",
}

#: how each choice reads on the card
GADGET_LABELS = {
    "stock": "Leave alone",
    "frag": "Frag grenade",
    "flashbang": "Flashbang",
    "smoke": "Smoke grenade",
    "teargas": "Tear gas",
    "phosphorus": "White phosphorus",
    "breaching": "Breaching charge",
    "gasmask": "Gas mask",
    "gl_he": "Grenade launcher (HE)",
    "gl_rp": "Grenade launcher (WP)",
}

#: the order the card offers them in
CHOICE_ORDER = ("stock", "frag", "flashbang", "smoke", "teargas",
                "phosphorus", "breaching", "gasmask", "gl_he", "gl_rp")

#: the four fields one kit carries
FIELDS = ("szPrimaryWeapon", "szSecondaryWeapon",
          "szPrimaryItem", "szSecondaryItem")

OPERATIVES = ("Price", "Weber", "Loiselle")

#: Primary weapons, every one measured in a live kit somewhere on the disc.
#: The disc spells a few of these inconsistently -- `SUBP90` beside `SubP90`,
#: `R63RDWEAPONS.ASSAULTAUG` beside the mixed-case form -- so the canonical
#: spelling here is the one the majority of kits use. Counts are kits, not maps.
PRIMARIES = {
    "mp5sd5": ("R63rdWeapons.SubMP5SD5", "MP5SD5"),          # 175
    "tmp": ("R63rdWeapons.SubTMP", "TMP"),                   # 73
    "g36k": ("R63rdWeapons.AssaultG36K", "G36K"),            # 71
    "ump": ("R63rdWeapons.SubUMP", "UMP45"),                 # 61
    "m4": ("R63rdWeapons.AssaultM4", "M4 Carbine"),          # 57
    "famas": ("R63rdWeapons.AssaultFAMASG2", "FAMAS G2"),    # 49
    "l85a1": ("R63rdWeapons.AssaultL85A1", "L85A1"),         # 44
    "mp5a4": ("R63rdWeapons.SubMP5A4", "MP5A4"),             # 39
    "g3a3": ("R63rdWeapons.AssaultG3A3", "G3A3"),            # 21
    "aug": ("R63rdWeapons.AssaultAUG", "AUG"),               # 20 + 3 upper
    "tar21": ("R63rdWeapons.AssaultTAR21", "TAR-21"),        # 17
    "galil": ("R63rdWeapons.AssaultGalilARM", "Galil ARM"),  # 15
    "m16a2": ("R63rdWeapons.AssaultM16A2", "M16A2"),         # 15
    "m60e4": ("R63rdWeapons.LMGM60E4", "M60E4"),             # 9
    "p90": ("R63rdWeapons.SubP90", "P90"),                   # 6 + 8 upper
    "sr2": ("R63rdWeapons.SubSR2", "SR-2"),                  # 1
}

#: Secondary weapons, same rule. The slot is not strictly a sidearm -- a third
#: of the disc's kits put a grenade launcher or a breaching charge here.
SECONDARIES = {
    "92fs": ("R63rdWeapons.Pistol92FS", "92FS"),                 # 435
    "mk23": ("R63rdWeapons.PistolMk23", "Mk23"),                 # 136
    "gl_he": ("R6Weapons.R6GrenadeLauncherHE", "GL (HE)"),       # 33
    "gl_rp": ("R6Weapons.R6GrenadeLauncherRP", "GL (WP)"),       # 28
    "breaching": ("R6Weapons.R6BreachingChargeGadget",
                  "Breaching charge"),                           # 26
    "usp": ("R63rdWeapons.PistolUSP", "USP"),                    # 16
    "flashbang": ("R6Weapons.R6FlashBangGadget", "Flashbang"),   # 4
    "deagle": ("R63rdWeapons.PistolDesertEagle50", "Desert Eagle"),  # 3
    "psr2": ("R63rdWeapons.PistolSR2", "SR-2 pistol"),           # 2
    "smoke": ("R6Weapons.R6SmokeGrenadeGadget", "Smoke"),        # 2
    "frag": ("R6Weapons.R6FragGrenadeGadget", "Frag"),           # 1
}


def _slot_choices(table):
    from .model import Choice
    return [Choice("stock", "Leave alone")] + [
        Choice(k, label) for k, (_cls, label) in table.items()]

#: `m_<Name><variant>=( ... )` -- the tuple is parenthesised and never nests
_KIT = re.compile(
    rb"(m_(?:Price|Weber|Loiselle)[A-Za-z]*Equipment[A-Za-z]*\s*=\s*\()([^)]*)(\))")

#: the same thing with the key split off, for deciding which player kit a given
#: squad key should copy. The separator is captured so the line is rebuilt with
#: whatever spacing it shipped with.
_NAMED_KIT = re.compile(
    rb"(m_(?:Price|Weber|Loiselle)[A-Za-z]*Equipment[A-Za-z]*)(\s*=\s*\()"
    rb"([^)]*)(\))")

#: one entry of the sound-bank table
_WS = re.compile(rb"(WS\[(\d+)\]\s*=\s*\(\s*bUsing\s*=\s*)(true|false)"
                 rb"(\s*,\s*weaponname\s*=\s*\")([^\"]*)(\")", re.I)


class KitError(Exception):
    pass


def _slot_for(plain: bytes, cls: str):
    """The WS slot whose `weaponname` is this gadget, or None."""
    bare = cls.split(".")[-1].encode("latin-1").lower()
    for m in _WS.finditer(plain):
        if m.group(5).lower() == bare:
            return int(m.group(2))
    return None


def _enable_slot(plain: bytes, slot: int):
    def sub(m):
        if int(m.group(2)) != slot or m.group(3).lower() == b"true":
            return m.group(0)
        return m.group(1) + b"true" + m.group(4) + m.group(5) + m.group(6)
    return _WS.subn(sub, plain)


#: the player's own two kits, which "match my loadout" copies from
_PLAYER = {
    "": "m_PlayerEquipment",
    "Silenced": "m_PlayerSilencedEquipment",
}


def _player_kit(plain: bytes, variant: str):
    """The player's kit for this variant as {field: className}, or None."""
    key = _PLAYER.get(variant)
    if not key:
        return None
    m = re.search(key.encode("latin-1") + rb"\s*=\s*\(([^)]*)\)", plain)
    if not m:
        return None
    body, out = m.group(1), {}
    for field in FIELDS:
        f = re.search(field.encode("latin-1") + rb'\s*=\s*"([^"]*)"', body)
        if f:
            out[field] = f.group(1)
    return out or None


def _variant_of(key: bytes):
    """"" or "Silenced" -- which player kit this squad key should copy."""
    return "Silenced" if b"Silenced" in key else ""


def match_player(plain: bytes):
    """Give Price, Weber and Loiselle the player's own kit for this mission.

    The safest possible weapon change, because it invents nothing: every value
    written is one this very map already hands the player, so the third-person
    assets are on the disc by construction. Terrorist Hunt kits take the plain
    player kit, and silenced kits the silenced one, since the player has only
    those two.

    Returns `(bytes, changed)`.
    """
    count = [0]

    def one(m):
        key, sep, body, close = m.groups()
        want = _player_kit(plain, _variant_of(key))
        if not want:
            return m.group(0)
        for field, cls in want.items():
            pat = re.compile(b"(" + field.encode("latin-1") +
                             b"\\s*=\\s*\")([^\"]*)(\")")

            def swap(mm, cls=cls):
                if mm.group(2) == cls:
                    return mm.group(0)
                count[0] += 1
                return mm.group(1) + cls + mm.group(3)

            body = pat.sub(swap, body)
        return key + sep + body + close

    out = _NAMED_KIT.sub(one, plain)
    return out, count[0]


#: which table backs each field, for the per-operative cards
_SLOT_TABLE = {
    "szPrimaryWeapon": PRIMARIES,
    "szSecondaryWeapon": SECONDARIES,
    "szPrimaryItem": None,      # GADGETS, resolved below
    "szSecondaryItem": None,
}


def _class_for(field: str, choice: str):
    """The class name a choice means for this field, or None for 'stock'."""
    if choice in (None, "", "stock"):
        return None
    table = _SLOT_TABLE.get(field)
    if table is None:
        if choice not in GADGETS:
            raise KitError("%r is not a gadget this disc issues" % choice)
        return GADGETS[choice]
    if choice not in table:
        raise KitError("%r is not a %s this disc issues" % (choice, field))
    return table[choice][0]


def set_operative(plain: bytes, who: str, fields: dict):
    """Set one operative's slots. `fields` maps a `sz...` name to a choice key.

    Applies to all four of that operative's kits -- plain, silenced and both
    Terrorist Hunt variants -- because the card is one dial per slot, not four.
    """
    if who not in OPERATIVES:
        raise KitError("%r is not one of the three operatives" % who)
    wanted = {}
    for field, choice in fields.items():
        cls = _class_for(field, choice)
        if cls is not None:
            wanted[field.encode("latin-1")] = cls.encode("latin-1")
    if not wanted:
        return plain, 0

    count = [0]
    pat = re.compile(rb"(m_" + who.encode("latin-1") +
                     rb"[A-Za-z]*Equipment[A-Za-z]*\s*=\s*\()([^)]*)(\))")

    def one(m):
        body = m.group(2)
        for field, cls in wanted.items():
            inner = re.compile(b"(" + field + b"\\s*=\\s*\")([^\"]*)(\")")

            def swap(mm, cls=cls):
                if mm.group(2) == cls:
                    return mm.group(0)
                count[0] += 1
                return mm.group(1) + cls + mm.group(3)

            body = inner.sub(swap, body)
        return m.group(1) + body + m.group(3)

    out = pat.sub(one, plain)
    if count[0]:
        for cls in wanted.values():
            slot = _slot_for(out, cls.decode("latin-1"))
            if slot is not None:
                out, _n = _enable_slot(out, slot)
    return out, count[0]


def apply(plain: bytes, primary: str = "stock", secondary: str = "stock",
          match: bool = False, per: dict = None):
    """Set the squad's kit across every entry in this map.

    `match` copies the player's own loadout in first; `primary` and
    `secondary` then override the two gadget slots, so the two options compose
    -- match the weapons, keep your own choice of grenade.

    Returns `(bytes, changed)`. A map with no squad kits -- every multiplayer
    and menu INI -- comes back untouched and reports zero, which is what lets
    one broad file selector cover the whole `/MAPS` folder.
    """
    total = 0
    if match:
        plain, n = match_player(plain)
        total += n
    # Per-operative choices are applied LAST, after the squad-wide ones, so
    # the most specific dial always wins.
    tail = []
    for who, fields in sorted((per or {}).items()):
        tail.append((who, fields))
    wanted = []
    for field, choice in (("szPrimaryItem", primary),
                          ("szSecondaryItem", secondary)):
        if choice in (None, "", "stock"):
            continue
        if choice not in GADGETS:
            raise KitError("%r is not a gadget this disc carries" % choice)
        wanted.append((field.encode("latin-1"),
                       GADGETS[choice].encode("latin-1")))
    def _tail(buf, running):
        for who, fields in tail:
            buf, k = set_operative(buf, who, fields)
            running += k
        return buf, running

    if not wanted:
        return _tail(plain, total)

    count = [0]

    def one(m):
        body = m.group(2)
        for field, cls in wanted:
            pat = re.compile(b"(" + field + b"\\s*=\\s*\")([^\"]*)(\")")

            def swap(mm, cls=cls):
                if mm.group(2) == cls:
                    return mm.group(0)
                count[0] += 1
                return mm.group(1) + cls + mm.group(3)

            body = pat.sub(swap, body)
        return m.group(1) + body + m.group(3)

    out = _KIT.sub(one, plain)
    if count[0]:
        for _field, cls in wanted:
            slot = _slot_for(out, cls.decode("latin-1"))
            if slot is not None:
                out, _n = _enable_slot(out, slot)
    return _tail(out, total + count[0])


def reads(plain: bytes):
    """[(key, primaryItem, secondaryItem)] for every squad kit in this map."""
    out = []
    for m in _KIT.finditer(plain):
        body = m.group(2)
        key = m.group(1).split(b"=")[0].strip().decode("latin-1")
        p = re.search(b"szPrimaryItem\\s*=\\s*\"([^\"]*)\"", body)
        s = re.search(b"szSecondaryItem\\s*=\\s*\"([^\"]*)\"", body)
        out.append((key,
                    p.group(1).decode("latin-1") if p else None,
                    s.group(1).decode("latin-1") if s else None))
    return out


def _card(key, label, prefix, group, which):
    from .model import CHOICE, Choice, Setting

    return Setting(
        prefix + key, label, CHOICE, "stock", group,
        choices=[Choice(k, GADGET_LABELS[k]) for k in CHOICE_ORDER],
        confidence="untested", touches="data",
        help="Every mission spells out what Price, Weber and Loiselle carry, "
             "in plain text, one file per map. This sets the squad's %s gadget "
             "on every mission at once, across all four kits each operative "
             "has -- normal, silenced, Terrorist Hunt and silenced Terrorist "
             "Hunt. Their weapons are left exactly as they were." % which,
        caution="Not play-tested. Only the gadget slots move, so nobody is "
                "handed a weapon they have no third-person model for -- that "
                "is what caused the crash when the enemy weapon tables were "
                "first re-rolled. Tear gas, smoke and phosphorus have no "
                "order-acknowledgement voice line, so a teammate given one "
                "uses it without the usual roger-flashbang callout; frag and "
                "flashbang do have full command sets. The gadget's own sound "
                "bank is switched on in the same edit.")


def match_card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "team_match_player", "Teammates carry your loadout",
        BOOL, False, group, confidence="untested", touches="data",
        help="Price, Weber and Loiselle take the same kit the mission hands "
             "you -- both weapons and both gadgets -- instead of their own. "
             "Done per mission, so on a map where you start with a G3A3 and a "
             "grenade launcher, so do they. Silenced kits copy your silenced "
             "one. This is the only option here that moves their weapons, and "
             "it is safe to because it invents nothing: every value written is "
             "already in that same map's file.",
        caution="Not play-tested. It copies the mission's DEFAULT loadout -- "
                "the one you are given before you change anything on the "
                "planning screen -- not whatever you switch to afterwards. "
                "Matching a choice you make at runtime would need bytecode "
                "re-assembly, which is the one edit path on this disc that has "
                "repeatedly caused freezes. If you also set a gadget above, "
                "that wins: you get their weapons matched to yours and the "
                "grenade you picked.")


#: (settingSuffix, field, label) for one operative's four slots
_SLOTS = (
    ("primary", "szPrimaryWeapon", "primary weapon"),
    ("secondary", "szSecondaryWeapon", "sidearm"),
    ("item1", "szPrimaryItem", "first gadget"),
    ("item2", "szSecondaryItem", "second gadget"),
)


def operative_cards(prefix, group):
    """Four dials per operative -- the desktop version of the split-screen
    Player Settings panel, except it can reach the AI teammates too."""
    from .model import CHOICE, Choice, Setting

    out = []
    for who in OPERATIVES:
        for suffix, field, what in _SLOTS:
            table = _SLOT_TABLE.get(field)
            if table is None:
                choices = [Choice(k, GADGET_LABELS[k]) for k in CHOICE_ORDER]
            else:
                choices = _slot_choices(table)
            out.append(Setting(
                "%s%s_%s" % (prefix, who.lower(), suffix),
                "%s -- %s" % (who, what), CHOICE, "stock", group,
                choices=choices, confidence="untested", touches="data",
                help="Sets %s's %s on every mission, across all four of his "
                     "kits. Every choice offered is one the disc already puts "
                     "in somebody's kit -- nothing invented, which is what "
                     "keeps it clear of the crash the enemy weapon tables "
                     "caused. Overrides the squad-wide dials above."
                     % (who, what),
                caution="Not play-tested. One weapon for the whole campaign, "
                        "so a silenced mission will be noisy if you pick a "
                        "loud gun. The matching sound bank is switched on in "
                        "the same edit."))
    return out


def cards(prefix, group):
    return [
        match_card(prefix, group),
        _card("team_gadget_1", "Whole squad -- first gadget", prefix, group,
              "primary"),
        _card("team_gadget_2", "Whole squad -- second gadget", prefix, group,
              "secondary"),
    ] + operative_cards(prefix, group)

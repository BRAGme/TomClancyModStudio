r"""Enemy grenade launchers: Jungle Storm (SLUS-20820) and Ghost Recon (SLUS-20613).

Reported from play 2026-10-10: enemies never fire a grenade launcher. They do
not, and in Jungle Storm they never can -- but not for any of the reasons that
look likely from the outside.

WHAT IS NOT WRONG
-----------------

The firing path is complete, in both games, and the AI already prefers it.

* `HasGrenadeLauncher` (GR 0x0019A180, JS 0x003EA140) walks the soldier's TWO
  inventory slots and answers yes for any `Firearm` with ammunition whose
  `GunFile::mWeaponMotionType` (+0xF8 in both games) is 4, `kGrenadeLauncher`.
  That field is the `.GUN` file's `<WeaponMotionType>` and NOTHING ELSE -- not
  the character model, not the `.atr`, not `<ClassName>`.
* A launcher is fired by SHOOTING IT LIKE A RIFLE. `IkeSimulationMgr::
  HandleGunshot` (GR 0x00393610, JS 0x00370EA0) tests the motion type and, on
  4, builds a ControllerThrewItem message (GR 0x01B1, JS 0x020B) instead of
  casting a bullet; `HandleControllerThrewItem` (GR 0x00398650, JS 0x00376350)
  takes the Firearm branch, reads `Firearm::GetProjectileIndex` and spawns the
  round at the projectile's own `InitialVelocity` (76 m/s for the 40 mm).
  Player and AI share every step of that.
* `HumanAIInventory::BestInventoryItem` (GR 0x001A00F0, JS 0x003EFEB0) looks
  for a motion-type-4 firearm BEFORE a hand grenade whenever the soldier wants
  a grenade and his team has a combat ROE -- which is exactly the state the
  frag decision requires. The AI prefers the launcher.
* `FragLocationBehavior::Process` (GR 0x001B4270, JS 0x001B0820) stores
  `HasGrenadeLauncher` into its own `mLaunched` field (+0x30) and branches on
  it: a launcher gets ONE `UseItem()` tap and goes to `kWaitingForBoom` with a
  0.1 s timer, where a hand throw gets `UseItem()` HELD for 1.0 s (which is
  what makes it a `kManlyThrow`). `FragRoomBehavior` has a state literally
  named `kLaunchingGrenade`.

So there is no code to write. `<HasUnderbarrelWeapon>` is a red herring --
dead data, read only by `GunFile::Load` and `BuildDocument`, with no gameplay
reader anywhere in 38,722 symbols. The PC "one rifle, switchable tube" does
not exist on PS2: a launcher is a SEPARATE weapon in the second slot.

WHAT IS WRONG
-------------

Pure data, and it differs by game.

An enemy is armed by `<Actor File="x.atr" Kit="y.kit">` in a `.MIS`, and by
nothing else -- `<KitPath>` is empty on 497 of Jungle Storm's 766 templates
and `<ClassName>` sits at the default `demolitions` on 551 of them, routing to
nothing. There is no `.CLS` file on either disc.

* **Ghost Recon already works**: 215 hostile Actor rows across 18 missions
  carry `ak74gl.kit`, which is `ak74gl.gun` in slot 0 and `gp25.gun` x5 in
  slot 1. Measured per archive; the disc ships two archives holding the same
  46 missions (differing only in M12_DOCKS and M15_RED_SQUARE), so a naive
  count over both doubles it to 430.
* **Jungle Storm gives a launcher to nobody.** `AK74GL.KIT` ships, is
  byte-identical to Ghost Recon's, and references `ak74gl.gun`, `gp25.gun`
  and `40mmglgrenade.prj` -- all present. It is referenced by ZERO Actor
  rows. `AUTOGL.GUN` (an AGS-17) ships too and no kit names it either.

The character model is NOT the signal, which is worth saying because it looks
like one: `rs_south_gp25.chr` appears in 16 Ghost Recon templates, all with an
empty `<KitPath/>`, and only three Actor rows (M04_VILLAGE) pair that mesh
with `ak74gl.kit`. Elsewhere the GP-25 model carries a plain AK, and most real
launcher carriers wear a different model. Jungle Storm has no such mesh at all.
What this does
--------------

Rewrites a KIT FILE, not the missions. Every hostile who carries that kit
gains the launcher, and no `.MIS` is touched at all.

That choice is the whole design, and the first two versions got it wrong.

The obvious edit is to re-point an `<Actor Kit="...">` row in a `.MIS` at the
shipped `ak74gl.kit`. It does not survive the archive. A `.MIS` IS
LZO-compressed, and a compressed file must keep its PLAIN length because its
chunk boundaries are fixed at 0x4000 -- the rule `dataedit` enforces and the
suite checks. `ak74gl.kit` is three bytes shorter than `vz58_only.kit`, so:

* Pad the difference back as whitespace and the length is right, but the
  padding differs per source kit, so the rewritten attribute is a different
  string each time and compresses WORSE than the uniform text it replaced.
  Measured: that put Jungle Storm missions over their archive slot.
  Relocation is the one thing these archives cannot afford -- `_fit_plain`'s
  note records sixteen files asking 147 KB of contiguous room against a
  single 64 KB pad, after which the next file fails outright.
* Do not pad, and all 45 containers fit with room to spare -- but the plain
  length changes, which is exactly what the fixed chunk boundaries forbid.

There is no third way to spend three bytes. So the mission files are left
alone.

A `.KIT` is PLAIN TEXT -- 394 bytes, uncompressed, like `.ATR` and `.ENV` --
and the same rule that forbids resizing a compressed file explicitly allows a
plain one to grow or shrink and be relocated. One small text file moving is
the cheap case the archive is built for; forty-five compressed ones are not.

The edit itself is a swap, not an insertion. `z84_only.kit` already spends
slot 1 on a `<ThrownItem>` holding two frag grenades::

    <Firearm SlotNumber = "0">   z84.gun, 4 magazines
    <ThrownItem SlotNumber = "1">  frag.prj, Count 2

and that block becomes the launcher, which is precisely the shape shipped
`ak74gl.kit` already has::

    <Firearm SlotNumber = "1">   gp25.gun, 5 magazines

The soldier gives up his hand grenades, which costs nothing: `GetNumGrenades`
(GR 0x0019A0A0) adds a motion-type-4 firearm's magazine count to the thrown
count, so his five rounds ARE his grenades to every decision that asks.

Which kits, and why those
-------------------------

Choosing kits rather than a share of actors also makes the result legible --
a particular enemy weapon class carries launchers, instead of a scatter of
unrelated soldiers -- and reproducible, with no selection rule to get wrong.

Hostile actors by kit, counted off the Jungle Storm disc (957 with a kit):

===================  =====  ======
kit                  actors  share
===================  =====  ======
default.kit            382   39.9%
vz58_only.kit          358   37.4%
z84_only.kit            71    7.4%
degtyarev_only.kit      31    3.2%
dragunov only.kit       31    3.2%
rp46_only.kit           26    2.7%
===================  =====  ======

`default.kit` is deliberately never touched: it is two fifths of every enemy
in the game and is also what unscripted and filler actors fall back to.

NOT YET PLAYED.
"""

from __future__ import annotations

import re

#: The launcher to fit, and how many rounds. `gp25.gun` ships on both discs
#: with `<WeaponMotionType>4</WeaponMotionType>`, which is the only thing the
#: game tests; `40mmglgrenade.prj` is its round.
LAUNCHER_GUN = "gp25.gun"
LAUNCHER_MAGS = 5

#: Kits a share may fit the launcher to, cheapest first. `default.kit` is
#: excluded on purpose -- see the docstring.
TIERS = {
    "few": ("z84_only.kit",),
    "like_gr": ("z84_only.kit", "rp46_only.kit", "degtyarev_only.kit",
                "dragunov only.kit"),
    "many": ("z84_only.kit", "rp46_only.kit", "degtyarev_only.kit",
             "dragunov only.kit", "vz58_only.kit"),
}

#: GR already ships 215 launcher carriers, so its tiers add to that rather
#: than starting from nothing.
GR_TIERS = {
    "few": ("rpk74.kit",),
    "like_gr": ("rpk74.kit", "ak47_2 grenades.kit"),
    "many": ("rpk74.kit", "ak47_2 grenades.kit", "ak74_2 grenades.kit"),
}

#: Hostile actors per kit, counted off each disc (Jungle Storm 957 with a
#: kit, Ghost Recon 1115 over its 46 unique missions -- the disc ships two
#: archives holding the same missions, so counting both doubles everything).
#: Ghost Recon's tiers ADD to the 215 it already ships.
SHARE_NOTE = {
    ("js", "few"): (71, 7.4), ("js", "like_gr"): (159, 16.6),
    ("js", "many"): (517, 54.0),
    ("gr", "few"): (65, 5.8), ("gr", "like_gr"): (124, 11.1),
    ("gr", "many"): (202, 18.1),
}

_SLOT1 = re.compile(
    rb"[ \t]*<(ThrownItem|HandHeldItem)\s+SlotNumber\s*=\s*\"1\"\s*>"
    rb".*?</(?:ThrownItem|HandHeldItem)>[ \t]*\r?\n?",
    re.S | re.I)
_FIREARM1 = re.compile(rb'<Firearm\s+SlotNumber\s*=\s*"1"', re.I)
_CLOSE = re.compile(rb"([ \t]*)</KitFile>", re.I)


def _block(indent: bytes, eol: bytes) -> bytes:
    """The slot-1 launcher, indented like the file it goes into."""
    i, j = indent, indent + b"\t"
    return (i + b'<Firearm SlotNumber = "1">' + eol
            + j + b"<VersionNumber>0.000000</VersionNumber>" + eol
            + j + b"<ItemFileName>" + LAUNCHER_GUN.encode() + b"</ItemFileName>" + eol
            + j + b"<MagazineCount>%d</MagazineCount>" % LAUNCHER_MAGS + eol
            + i + b"</Firearm>" + eol)


def fit_launcher(plain: bytes):
    """(new kit bytes, 1 if it changed). Gives slot 1 to the launcher.

    A kit that already has a slot-1 firearm is left alone, so the edit is
    idempotent and cannot stack two launchers.
    """
    if _FIREARM1.search(plain):
        return plain, 0
    eol = b"\r\n" if b"\r\n" in plain else b"\n"
    m = _CLOSE.search(plain)
    indent = (m.group(1) or b"") + b"\t" if m else b"\t"
    block = _block(indent, eol)

    hit = _SLOT1.search(plain)
    if hit:
        return plain[:hit.start()] + block + plain[hit.end():], 1
    if not m:
        return plain, 0
    return plain[:m.start()] + block + plain[m.start():], 1


def kits_for(share: str, game: str = "js"):
    """The kit filenames one share fits the launcher to."""
    if share in (None, "", "off", "stock"):
        return ()
    return (GR_TIERS if game == "gr" else TIERS)[share]


def select(share: str, game: str = "js") -> str:
    """A `FileEdit` regex matching exactly those kits."""
    names = kits_for(share, game)
    if not names:
        return r"(?!)"
    # re.escape already turns the dot into `\.`; upper() leaves the escape
    # alone. Re-escaping ".KIT" afterwards produced `\.KIT`, which matched
    # nothing. FileEdit.select is matched against the archive's UPPER-case
    # paths, so the names are upper-cased and nothing else is done to them.
    return r"/(?:%s)$" % "|".join(re.escape(n).upper() for n in names)


def card(prefix, group):
    from .model import CHOICE, Choice, Setting

    js = prefix.startswith("js")
    return Setting(
        prefix + "enemy_launcher",
        "Enemies carry grenade launchers", CHOICE, "off", group,
        confidence="experimental", touches="data",
        requires=({prefix + "enemy_grenades": [True]} if js else {}),
        choices=[
            Choice("off", "As shipped",
                   "Jungle Storm gives a launcher to nobody."
                   if js else
                   "215 enemies across 18 missions already carry one."),
            Choice("few", "A few",
                   "The Z-84 squads: 71 enemies, about 7%."
                   if js else "The AK-47 squads."),
            Choice("like_gr", "Like Ghost Recon",
                   "Z-84, RP-46, Degtyarev and Dragunov squads: 159 "
                   "enemies, about 17%, which is the density Ghost Recon "
                   "itself ships (215 of 1160)."
                   if js else "The AK-47 and AK-74 squads, on top of the 215."),
            Choice("many", "Many",
                   "Those and the vz.58 squads, which is over half of them."
                   if js else "AK-47, AK-74 and RPK squads too."),
        ],
        help="Fits a GP-25 underbarrel launcher, with five 40 mm rounds, to "
             "the second weapon slot of whole enemy weapon classes -- the "
             "Z-84 squads first, then wider.\n\n"
             "Nothing is invented. The launcher, its round and the AI that "
             "uses them all ship on the disc: when a soldier decides on a "
             "grenade the game looks for a launcher BEFORE a hand grenade, "
             "aims it, and fires one shot instead of winding up a throw. "
             + ("Jungle Storm simply never gives one to anybody -- the kit "
                "that would is on the disc and no enemy references it.\n\n"
                "Needs 'Enemies throw grenades', because Jungle Storm has no "
                "code of its own that decides to throw during a firefight; "
                "that option supplies the decision this one arms."
                if js else
                "Ghost Recon already does this for 215 enemies; this widens "
                "it.")
             + "\n\nThose soldiers give up their two hand grenades for it, "
               "which costs them nothing: the game counts launcher rounds as "
               "grenades. A round flies flat and fast (76 m/s) instead of "
               "lobbing, and goes off on impact with an 8 m blast.",
        caution="Never played. The kit, the gun and the round are shipped "
                "data and the firing path was read out of both executables, "
                "but no enemy has been seen firing one.\n\n"
                "An 8 m blast at 76 m/s from a soldier you have not spotted "
                "is a real difficulty increase. Start at 'A few'.")

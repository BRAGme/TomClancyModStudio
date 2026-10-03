"""Applying and undoing edits to data files inside a game's own archives.

The archive is a read-only filesystem with an explicit offset and size per
entry, so a file can be replaced in place when it fits and relocated into free
space when it does not. Every archive here ends with 64 KB of zero padding, and
relocating a file releases its old run back into the pool, so in practice the
first file edited takes the pad and the rest recycle each other's slots -- the
whole of Ghost Recon's 25 wave-bearing missions cost 2.4 KB of the 64.

Originals are copied into a sidecar folder beside the ISO before the first
change, with their offsets, so undoing puts each file back at the exact byte it
came from.
"""

from __future__ import annotations

import json
import os

from . import lin, rselzo, transforms
from .vokes import Vokes, VokesError, open_archives

MANIFEST = "data-edits.json"

#: A file at least this big is named in the log on its own, because packing it
#: is where the seconds go. COMMON.LIN's payload is 5 MB; a map INI is 3 KB.
_CHATTY_BYTES = 256 * 1024


class DataEditError(Exception):
    pass


# ---------------------------------------------------------------------------
# the named operations a profile can ask for
# ---------------------------------------------------------------------------

def _op_strip_difficulty(plain, params):
    return transforms.strip_difficulty(plain, params.get("which",
                                                         ("Easy", "Normal", "Hard")))


def _op_reveal_hidden(plain, params):
    return transforms.reveal_hidden(plain)


def _op_bump_tier(plain, params):
    return transforms.bump_enemy_tier(plain, int(params.get("steps", 1)))


def _op_bump_stats(plain, params):
    return transforms.bump_atr_stats(plain, int(params.get("steps", 1)),
                                     stats=params.get("stats", transforms.ATR_STATS))


def _op_scale_ballistics(plain, params):
    return transforms.scale_xml_floats(plain, float(params.get("factor", 1.0)))


def _op_scale_xml(plain, params):
    return transforms.scale_xml_floats(
        plain, float(params.get("factor", 1.0)),
        prefix=params.get("prefix", "").encode("latin1"),
        keep_width=bool(params.get("keep_width", True)))


def _op_xml_values(plain, params):
    return transforms.set_xml_values(plain, params.get("values", {}))


def _op_nimitz_skills(plain, params):
    return transforms.bump_nimitz_skills(
        plain, int(params.get("steps", 0)),
        hostile_only=bool(params.get("hostile_only", True)),
        only=params.get("only"))


def _op_nimitz_guns(plain, params):
    return transforms.scale_nimitz_guns(plain,
                                        mag=float(params.get("mag", 1.0)),
                                        rpm=float(params.get("rpm", 1.0)),
                                        only=params.get("only"))


def _op_scale_gun(plain, params):
    from . import rseguns
    return rseguns.scale(plain, params)


def _op_gtf_variables(plain, params):
    return transforms.set_gtf_variables(plain, params.get("values", {}))


def _op_ini_values(plain, params):
    return transforms.set_ini_values(plain, params.get("values", {}))


def _op_grenade_carry(plain, params):
    return transforms.set_grenade_carry(plain, params.get("percent", 20))


def _op_split_wheel(plain, params):
    from . import rsewheel
    # Also put back the byte the withdrawn first attempt changed. It is dead
    # code either way, but a disc still carrying it would make a later
    # stock-vs-disc diff report an edit this tool no longer makes.
    plain, undone = rsewheel.undo_first_attempt(plain)
    plain, n = rsewheel.restore(plain, bool(params.get("enable", True)))
    return plain, n + undone


def _op_rpg_speed(plain, params):
    from . import rserpg
    return rserpg.apply(plain, int(params.get("speed", 1)))


def _op_split_draw(plain, params):
    from . import rsedraw
    return rsedraw.restore(plain, bool(params.get("enable", True)))


def _op_split_cycle(plain, params):
    from . import rsewheel
    return rsewheel.cycle_restore(plain, bool(params.get("enable", True)))


def _op_split_team_orders(plain, params):
    from . import rseorders
    return rseorders.apply(plain, bool(params.get("enable", True)))


def _op_split_hands(plain, params):
    from . import rsehands
    return rsehands.apply(plain, bool(params.get("enable", True)))


def _op_dead_flashlight(plain, params):
    from . import rseflashlight
    return rseflashlight.apply(plain, str(params.get("mode", "on")))


def _op_split_callouts(plain, params):
    from . import rsecallouts
    return rsecallouts.apply(plain, bool(params.get("enable", True)))


def _op_split_down_callouts(plain, params):
    from . import rsedowncall
    return rsedowncall.apply(plain, bool(params.get("enable", True)))


def _op_third_person(plain, params):
    from . import rsethirdperson
    return rsethirdperson.apply(plain, params["which"],
                                bool(params.get("enable", True)))


def _op_gun_audio_fix(plain, params):
    from . import rsegunaudio
    return rsegunaudio.apply(plain, bool(params.get("enable", True)))


def _op_corpse_hitbox(plain, params):
    from . import rsecorpsehit
    return rsecorpsehit.apply(plain, bool(params.get("enable", True)))


def _op_hostage_rainbow_voice(plain, params):
    from . import rsehostagerun
    return rsehostagerun.apply(plain, bool(params.get("enable", True)))


def _op_rogue_tango(plain, params):
    from . import rseroguecall
    return rseroguecall.apply(plain, bool(params.get("enable", True)))


def _op_split_thunt_ai(plain, params):
    from . import rsethuntai
    return rsethuntai.apply(plain, bool(params.get("enable", True)))


def _op_breach_stun(plain, params):
    from . import rsegadget
    return rsegadget.apply(plain, float(params.get("metres", 10)))


def _op_friendly_fire(plain, params):
    from . import rseff
    return rseff.apply(plain, str(params["which"]),
                       bool(params.get("enable", True)))


def _op_uzi_flashlight(plain, params):
    from . import rseuzilight
    return rseuzilight.apply(plain, float(params.get("x", rseuzilight.DEFAULT_X)),
                             float(params.get("z", rseuzilight.DEFAULT_Z)))


def _op_smoke_ramp(plain, params):
    from . import rsesmoke
    return rsesmoke.apply(plain, params["seconds"],
                          bool(params.get("enable", True)))


def _op_hostage_follow_voice(plain, params):
    from . import rsefollowleg
    return rsefollowleg.apply(plain, bool(params.get("enable", True)))


def _op_ai_weapon_sound(plain, params):
    from . import rsesoundgate
    return rsesoundgate.apply(plain, bool(params.get("enable", True)))


def _op_spectate(plain, params):
    from . import rsespectate
    return rsespectate.apply(plain, str(params["which"]),
                             bool(params.get("enable", True)))


def _op_keep_viewport(plain, params):
    from . import rseviewport
    return rseviewport.apply(plain, bool(params.get("enable", True)))


def _op_ai_hunt(plain, params):
    from . import rseaihunt
    return rseaihunt.apply(plain, str(params["which"]),
                           bool(params.get("enable", True)))


def _op_canon_team(plain, params):
    from . import rsecanon
    return rsecanon.apply(plain, bool(params.get("enable", True)))


def _op_ss_chatter(plain, params):
    from . import rsechatter
    return rsechatter.apply(plain, int(params.get("chance", 0)),
                            bool(params.get("hostage", True)))


def _op_ss_man_down(plain, params):
    from . import rsemandown
    return rsemandown.apply(plain, bool(params.get("enable", True)))


def _op_frag_warning(plain, params):
    from . import rsefragwarn
    return rsefragwarn.apply(plain, bool(params.get("enable", True)))


def _op_switch_rate(plain, params):
    from . import rseswitch
    return rseswitch.apply(plain, int(params.get("percent", rseswitch.STOCK)))


def _op_squad(plain, params):
    from . import rsesquad
    return rsesquad.apply(plain, bool(params.get("enable", True)),
                          bool(params.get("canon", False)))


def _op_team_recording(plain, params, sibling=None):
    from . import rsesplice
    if sibling is None:
        raise DataEditError("team_recording needs the single-player recording "
                            "beside the split-screen one")
    return rsesplice.apply(plain, sibling, bool(params.get("enable", True)),
                           str(params.get("order", "LW")))


def _op_muzzle(plain, params):
    from . import rsemuzzle
    return rsemuzzle.apply(plain, bool(params.get("enable", True)))


def _op_rescue_flag(plain, params):
    from . import rserescue
    return rserescue.apply(plain, bool(params.get("enable", True)))


def _op_split_rescue_team(plain, params):
    from . import rseteam
    return rseteam.apply(plain, bool(params.get("enable", True)))


def _op_fov(plain, params):
    from . import rsefov
    return rsefov.apply(plain, int(params.get("degrees", 90)))


def _op_ai_cover(plain, params):
    from . import rseaicover
    return rseaicover.apply(plain, str(params.get("set", "stock")))


def _op_ai_sidearm(plain, params):
    from . import rsesidearm
    return rsesidearm.apply(plain, int(params.get("chance", 0)),
                            bool(params.get("in_contact", True)),
                            int(params.get("say_chance", 0)))


def _op_enemy_loadout(plain, params, container=None):
    from . import rseloadout
    mark = params.get("marksmanship")
    mark = None if mark in (None, "", "stock") else int(mark)
    mode = params.get("weapons", "stock")
    # Applied to the plain bytes FIRST, so that when a container is present the
    # fitter measures the text that will actually be written. It is one digit
    # for one digit, so it cannot change the length -- but it does change what
    # deflates, and the chunk check has to see the real thing.
    torch = params.get("flashlight")
    extra = 0
    if torch is not None:
        plain, extra = rseloadout.set_gadget_share(plain, "Flashlight", torch)
    if container is None:
        # No container to measure against, so take the edit at full strength
        # and let the caller's own length check speak. Tests use this path.
        new, stats = rseloadout.retune(plain, weapons=mode, marksmanship=mark)
    else:
        new, stats = rseloadout.fit_to_lin(container, plain, weapons=mode,
                                           marksmanship=mark)
    return new, stats["weapons"] + stats["skills"] + extra


#: Ops that want the file's original container bytes as a third argument,
#: because what they may write depends on what will still deflate into it.
_WANTS_CONTAINER = {"enemy_loadout"}

#: Ops that are built from ANOTHER file in the same archive, handed over as
#: that file's stock plain bytes. Maps the op to the function that names the
#: other file from this one's path.
def _team_recording_sibling(path):
    from . import rsesplice
    return rsesplice.sibling(path)


_WANTS_SIBLING = {"team_recording": _team_recording_sibling}

#: Ops allowed to change a cooked container's length -- see the length guard
#: in `apply_data` for why every other op is not, and why these are.
_RECORDING_OPS = {"team_recording"}

#: Ops allowed to make a cooked container LONGER.
#:
#: The length rule below is a PROXY for the real one -- "do not change which
#: objects load, or in what order" -- because a length change is the one
#: mechanical symptom of that which is catchable from here. An op only belongs
#: in this set once it has been shown to trip the proxy WITHOUT breaking the
#: rule, and the showing has to be specific.
#:
#: `uzi_flashlight` adds a socket record to a weapon's static mesh. What was
#: established before it was let through:
#:   * The socket tags are INLINE length-prefixed strings, not name-table
#:     indices -- proven because records step by 57, 59 and 61 bytes, following
#:     len("TagCase"), len("TagGadget") and len("TagMagazine"), which a
#:     fixed-width index cannot do. So no name, import or export is added, and
#:     no object reference the recorded boot never resolved is introduced.
#:   * No SerialSize or SerialOffset governs this data at all: the packages'
#:     own tables do not describe these arrays (one declares a six-byte export
#:     while spanning 0x31221). What keeps the read stream in step is the
#:     array's COUNT byte, and stepping it 3 -> 4 makes the deserialiser
#:     consume exactly the bytes inserted.
#:   * Every package magic still lands where it did, each moved by exactly the
#:     bytes inserted ahead of it -- the same measure the withdrawn
#:     `frag_warning` work used.
#: That last op is the cautionary tale: it also grew a container, and the
#: growth was NOT what broke it. Three new imports were.
_GROWS_SAFELY = {"uzi_flashlight"}


def _op_zone_counts(plain, params):
    from . import r6zones
    # The whole pair. `scale` already returns (bytes, changed) -- taking [0]
    # dropped the count and handed back bare bytes, which the caller then
    # tried to unpack one character at a time. It failed on the first level
    # package it touched, killed the apply, and reported nothing.
    return r6zones.scale(plain, float(params.get("factor", 1.0)))


def _op_team_gadget(plain, params):
    from . import rsekits
    return rsekits.apply(plain, params.get("primary", "stock"),
                         params.get("secondary", "stock"),
                         bool(params.get("match", False)),
                         params.get("per") or {})


def _op_ws_slot(plain, params):
    return transforms.set_ws_slot(plain, int(params["slot"]),
                                  bool(params.get("using", True)))


OPS = {
    "strip_difficulty": _op_strip_difficulty,
    "reveal_hidden": _op_reveal_hidden,
    "bump_tier": _op_bump_tier,
    "bump_stats": _op_bump_stats,
    "gtf_variables": _op_gtf_variables,
    "ini_values": _op_ini_values,
    "team_gadget": _op_team_gadget,
    "ws_slot": _op_ws_slot,
    "grenade_carry": _op_grenade_carry,
    "enemy_loadout": _op_enemy_loadout,
    "split_wheel": _op_split_wheel,
    "ai_sidearm": _op_ai_sidearm,
    "ai_cover": _op_ai_cover,
    "fov": _op_fov,
    "split_rescue_team": _op_split_rescue_team,
    "switch_rate": _op_switch_rate,
    "squad": _op_squad,
    "team_recording": _op_team_recording,
    "muzzle": _op_muzzle,
    "rescue_flag": _op_rescue_flag,
    "frag_warning": _op_frag_warning,
    "ss_man_down": _op_ss_man_down,
    "ss_chatter": _op_ss_chatter,
    "canon_team": _op_canon_team,
    "split_cycle": _op_split_cycle,
    "split_team_orders": _op_split_team_orders,
    "split_callouts": _op_split_callouts,
    "split_down_callouts": _op_split_down_callouts,
    "rogue_tango": _op_rogue_tango,
    "hostage_rainbow_voice": _op_hostage_rainbow_voice,
    "corpse_hitbox": _op_corpse_hitbox,
    "gun_audio_fix": _op_gun_audio_fix,
    "third_person": _op_third_person,
    "split_thunt_ai": _op_split_thunt_ai,
    "breach_stun": _op_breach_stun,
    "friendly_fire": _op_friendly_fire,
    "ai_hunt": _op_ai_hunt,
    "keep_viewport": _op_keep_viewport,
    "spectate": _op_spectate,
    "ai_weapon_sound": _op_ai_weapon_sound,
    "hostage_follow_voice": _op_hostage_follow_voice,
    "smoke_ramp": _op_smoke_ramp,
    "uzi_flashlight": _op_uzi_flashlight,
    "dead_flashlight": _op_dead_flashlight,
    "split_hands": _op_split_hands,
    "split_draw": _op_split_draw,
    "rpg_speed": _op_rpg_speed,
    "scale_ballistics": _op_scale_ballistics,
    "scale_xml": _op_scale_xml,
    "xml_values": _op_xml_values,
    "nimitz_skills": _op_nimitz_skills,
    "nimitz_guns": _op_nimitz_guns,
    "zone_counts": _op_zone_counts,
    "scale_gun": _op_scale_gun,
}


# ---------------------------------------------------------------------------
# containers
# ---------------------------------------------------------------------------

#: files that are raw binary and must never be run through a container sniffer
_RAW_SUFFIXES = (".GUNS", ".CGSB", ".PROJS", ".ITEMS", ".PROS", ".WSFB",
                 ".CMSB", ".CGSB", ".ACMS", ".MISSIONS", ".SB1")


def _unpack(original, path=""):
    """(kind, plainBytes) for whichever container this file uses."""
    if path and path.upper().endswith(_RAW_SUFFIXES):
        return "plain", original
    if lin.is_lin(original):
        return "lin", lin.decompress(original)
    if rselzo.is_compressed(original):
        return "rselzo", rselzo.decompress(original)
    return "plain", original


def _sibling_plain(arc, arc_name, path, store, op):
    """The stock plain bytes of the file an op is built from.

    Taken from the backup store when it holds the file -- the shipped bytes,
    whatever an earlier run left on the disc -- and from the disc otherwise,
    which is then stock by construction: nothing edits a file without the
    store remembering it first.
    """
    want = _WANTS_SIBLING[op](path)
    ent = arc.files.get(want.upper())
    if ent is None:
        raise DataEditError("%s: %s is built from %s, which is not in %s"
                            % (path, op, want, arc_name))
    stored = store.original(arc_name, ent.path)
    _kind, plain = _unpack(stored[0] if stored else arc.read_entry(ent),
                           ent.path)
    return plain


def _fit_plain(data, room):
    """Shed inert bytes from a text file until it fits `room`.

    Why this exists. A loadout change rewrites a weapon name in every map's
    INI, and a longer name makes the file longer -- by ONE to about twenty
    bytes, on a file of ten and a half kilobytes. That tiny overshoot used to
    mean relocation, and relocation is what these archives cannot afford:
    measured on a stock disc, one operative gaining one gadget puts sixteen
    files over their slot and asks for 147 KB of contiguous room, against a
    single 64 KB pad. The first few move, the pad fills, and the next file
    fails with "no free run left" -- which is exactly what a disc that had
    been patched a few times did.

    So the file stays where it is and gives up bytes that no INI reader looks
    at, in increasing order of rudeness: whitespace before a line ending, then
    blank lines, then whole-line comments, and only as many as it takes. A
    file that still does not fit is handed back unchanged and relocates as
    before -- this makes the common case free, it does not remove the fallback.

    The backup store keeps the untouched bytes, so none of this is one-way.
    """
    if len(data) <= room:
        return data
    eol = b"\r\n" if b"\r\n" in data else b"\n"
    tail = data.endswith(eol)
    lines = data.split(eol)
    if tail and lines and not lines[-1]:
        lines.pop()

    def build(ls):
        out = eol.join(ls)
        return out + eol if tail else out

    # 1. trailing whitespace: invisible, and no reader can miss it
    lines = [ln.rstrip(b" \t") for ln in lines]
    if len(build(lines)) <= room:
        return build(lines)

    # 2. blank lines, from the bottom up, so the head of the file -- which is
    #    what anyone opening it actually reads -- keeps its shape longest
    for i in range(len(lines) - 1, -1, -1):
        if len(build(lines)) <= room:
            break
        if not lines[i].strip():
            del lines[i]
    if len(build(lines)) <= room:
        return build(lines)

    # 3. whole-line comments, same order. Never a trailing comment on a line
    #    that also holds a setting: that is a value's own line and cutting it
    #    is how a parser ends up reading something different.
    for i in range(len(lines) - 1, -1, -1):
        if len(build(lines)) <= room:
            break
        head = lines[i].lstrip()
        if head.startswith(b";") or head.startswith(b"#"):
            del lines[i]
    out = build(lines)
    return out if len(out) < len(data) else data


def _repack(kind, original, plain):
    if kind == "lin":
        # `substitute` is still the better path when the payload happens to be
        # the same length: it re-deflates only the chunks that changed and
        # leaves the container's own length alone, so the archive entry never
        # has to move. When an edit genuinely grows a package -- which is
        # allowed, see `lin.rebuild` -- the whole chain is rebuilt instead.
        # That usually comes out SMALLER anyway, because deflating at level 9
        # beats the packer the disc shipped with.
        if len(plain) == len(lin.decompress(original)):
            return lin.substitute(original, lambda _old: plain)[0]
        _parts, tail = lin.parse(original)
        # Held to the size it shipped at whenever it fits -- a container
        # that comes out smaller would free a gap behind itself, and the
        # next file to relocate could land in it; see `lin.rebuild_exact`.
        # One that has genuinely outgrown its slot is rebuilt at its natural
        # size and relocated by the archive writer, as before.
        try:
            return lin.rebuild_exact(plain, tail, len(original))
        except lin.LinTooBig:
            return lin.rebuild(plain, tail)
    if kind == "rselzo":
        return rselzo.repack(original, plain)
    return plain



# ---------------------------------------------------------------------------
# backup store
# ---------------------------------------------------------------------------

class Store:
    """Original bytes and offsets for every archive file we have touched."""

    def __init__(self, folder):
        self.folder = folder
        self.path = os.path.join(folder, MANIFEST)
        self.index = {}
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as fh:
                    self.index = json.load(fh)
            except (OSError, ValueError):
                self.index = {}

    def _blob(self, key):
        safe = key.replace("/", "__").replace("\\", "__").replace(":", "_")
        return os.path.join(self.folder, "orig", safe)

    def remember(self, archive, path, data, offset):
        key = "%s%s" % (archive, path)
        if key in self.index:
            return
        blob = self._blob(key)
        os.makedirs(os.path.dirname(blob), exist_ok=True)
        with open(blob, "wb") as fh:
            fh.write(data)
        self.index[key] = {"archive": archive, "path": path,
                           "offset": offset, "size": len(data)}
        self.save()

    def original(self, archive, path):
        key = "%s%s" % (archive, path)
        rec = self.index.get(key)
        if rec is None:
            return None
        try:
            with open(self._blob(key), "rb") as fh:
                return fh.read(), rec["offset"]
        except OSError:
            return None

    def entries(self):
        return list(self.index.values())

    def save(self):
        os.makedirs(self.folder, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self.index, fh, indent=1)

    def forget_all(self):
        self.index = {}
        self.save()


# ---------------------------------------------------------------------------
# apply / revert
# ---------------------------------------------------------------------------

def enemy_template_set(arc):
    """The `.atr` files any mission hands to a non-allied company.

    Both games keep the two sets completely disjoint -- 568 enemy templates
    against 17 other in Ghost Recon, 274 against 24 in Jungle Storm, with zero
    overlap -- so scoping a skill edit this way is exact, not approximate.
    """
    names = set()
    for key, ent in arc.files.items():
        if not key.endswith(".MIS"):
            continue
        try:
            _kind, plain = _unpack(arc.read_entry(ent), ent.path)
        except Exception:                       # noqa: BLE001
            continue
        names |= transforms.enemy_templates(plain)
    return {("/" + n).upper() for n in names}


#: how a gun edit is aimed. `rseguns.sides` returns three sets; a weapon that
#: both sides carry is in neither of these, deliberately -- one file cannot be
#: two weapons, so neither dial touches it.
GUN_SCOPES = {"ally_guns": 0, "enemy_guns": 1}


def gun_scope_set(arcs, which):
    """The archive paths of one side's `.gun` files.

    Spanning EVERY archive matters: The Sum of All Fears keeps its weapons in
    one and part of its kit and mission data in another, so working one archive
    at a time sees no missions and decides every gun belongs to nobody.
    """
    from . import rseguns
    files = {}
    for arc in arcs:
        for key, entry in arc.files.items():
            files.setdefault(key.upper(), (arc, entry))
    picked = rseguns.sides(files)[GUN_SCOPES[which]]
    return {("/" + n).upper() for n in picked}


def _scope_filter(arc, edit, cache, arcs=None):
    if edit.scope in GUN_SCOPES:
        if edit.scope not in cache:
            cache[edit.scope] = gun_scope_set(arcs or [arc], edit.scope)
        allowed = cache[edit.scope]
        return lambda k: k.upper() in allowed
    if edit.scope != "enemy_templates":
        return None
    if arc.r.name not in cache:
        cache[arc.r.name] = enemy_template_set(arc)
    allowed = cache[arc.r.name]
    return lambda key: key.upper() in allowed


def _archives(iso, profile):
    """Every archive this profile edits, keyed by name.

    Lockdown's container is a different format entirely, but it presents the
    same handful of methods, so everything downstream -- the backup store, the
    relocation check, verify and revert -- runs unchanged.
    """
    # A loose data root answers this one question for itself, which is all it
    # takes for every edit below -- and the backup store, verify and revert --
    # to run against a folder instead of a disc image.
    if hasattr(iso, "loose_archives"):
        return iso.loose_archives(profile)
    out = {}
    if getattr(profile, "archive_kind", "vokes") == "nimitz":
        from .nimitz import open_pak
        for arc in open_pak(iso):
            out[arc.r.name.upper()] = arc
        return out
    for arc in open_archives(iso, profile.archive_pattern or
                             r"/(VOKES\d|GR|MENU)\.IMG$"):
        out[arc.r.name.upper()] = arc
    return out


def plan_data(iso, profile, edits, store):
    """What the edits would rewrite, without touching anything."""
    rows = []
    arcs = _archives(iso, profile)
    for edit in edits:
        for arc_name, arc in arcs.items():
            if edit.archive and edit.archive.upper() not in arc_name:
                continue
            for key, ent in sorted(arc.files.items()):
                if not edit.matches(key):
                    continue
                rows.append((arc_name, ent.path, edit))
    return rows


def apply_data(iso, profile, edits, store, progress=None, selector=None,
               tick=None):
    """Run every edit. Files are written largest first, because the one big
    mission has to land in the 64 KB pad before smaller ones nibble at it.

    `tick(done, total)` is for a progress bar. `total` is None during the
    first half, because which files an edit matches is only known as the
    match is made -- so the caller should show that half as indeterminate and
    the second half, which knows its own length, as a real fraction.
    """
    arcs = _archives(iso, profile)
    pending = {}          # (arcName, path) -> (arc, entry, plainBytes)
    #: (arcName, path) -> container kind, taken from the STORED original
    #: at the moment it is first unpacked. The length guard below used to
    #: re-derive this from the live disc, which is a different byte source
    #: on an already-patched disc and could therefore classify the same
    #: entry differently from the bytes the edit actually ran on.
    kinds = {}
    counts = {}
    scopes = {}

    def say(msg):
        if progress:
            progress(msg)

    def beat(done, total=None):
        if tick:
            tick(done, total)

    # An op that supplies a DIFFERENT recording (`team_recording`) replaces the
    # whole file with one it builds, and proves, from the SHIPPED split-screen
    # and single-player recordings. Every other edit of that file has to run
    # on top of the replacement, never underneath it: the per-mission enemy
    # counts edit `<MAP>_SS.LIN` too, and when they ran first the splice was
    # handed an edited recording and refused it ("the split-screen record at
    # 0x... is not the one every map carries") -- the whole apply failed as
    # soon as a mission's enemy count and AI teammates were both on. A stable
    # sort keeps every other edit in the order the profile gave.
    edits = sorted(edits, key=lambda e: e.op not in _RECORDING_OPS)

    for edit in edits:
        op = OPS.get(edit.op)
        if op is None:
            raise DataEditError("unknown data operation %r" % edit.op)
        for arc_name, arc in arcs.items():
            if edit.archive and edit.archive.upper() not in arc_name:
                continue
            allowed = _scope_filter(arc, edit, scopes,
                                    list(arcs.values()))
            for key, ent in sorted(arc.files.items()):
                if not edit.matches(key):
                    continue
                if allowed and not allowed(key):
                    continue
                if selector and not selector(key):
                    continue
                slot = (arc_name, ent.path)
                if slot in pending:
                    _a, _e, plain = pending[slot]
                    kind = kinds[slot]
                else:
                    original = arc.read_entry(ent)
                    store.remember(arc_name, ent.path, original, ent.offset)
                    # Edits are applied to the bytes the game SHIPPED, not to
                    # whatever is on the disc now. The settings page describes
                    # a destination, not a diff: applying twice must give the
                    # same disc, and moving a setting back to its default must
                    # actually undo it. Reading the live file instead makes
                    # edits compound -- a weapon already swapped once gets
                    # swapped again -- and leaves no way back short of a full
                    # restore.
                    stored = store.original(arc_name, ent.path)
                    base = stored[0] if stored else original
                    kind, plain = _unpack(base, ent.path)
                    kinds[slot] = kind
                if len(plain) >= _CHATTY_BYTES:
                    say("  editing %s" % ent.path)
                beat(len(pending) + 1)
                if edit.op in _WANTS_CONTAINER:
                    stored = store.original(arc_name, ent.path)
                    container = stored[0] if stored else arc.read_entry(ent)
                    new, n = op(plain, edit.params, container)
                elif edit.op in _WANTS_SIBLING:
                    new, n = op(plain, edit.params,
                                _sibling_plain(arc, arc_name, ent.path, store,
                                               edit.op))
                else:
                    new, n = op(plain, edit.params)
                # Only plain text may change length. The archive writer
                # relocates a plain file, and INI edits have shipped that way
                # for a long time.
                #
                # A LIN may NOT -- and this is a PROXY rule, which is worth
                # being honest about because the real one cannot be checked
                # mechanically.
                #
                # `frag_warning` grew the package at 0x086a7f by three names
                # and three imports, COMMON_SS.LIN went 5,094,061 -> 5,094,168,
                # the container still fitted its slot, and the game then would
                # not boot at all. The length was not what broke it: a LIN is a
                # RECORDING of one boot's read stream (every Seek under
                # ULinkerLoad is discarded -- FLinFileReader::Seek at
                # 0x001d3ab0 literally logs "Can't seek compressed file"), and
                # the grown stream still lands on the next package's magic
                # exactly, measured both ways.
                #
                # What broke it is that three NEW imports are three object
                # references that boot never resolved, so the engine asks the
                # recording for reads it cannot answer and the cursor
                # desynchronises permanently.
                #
                # That is the real rule: do not change WHICH objects load, or
                # in what order. It is not testable from here. A length change
                # in a cooked container is the one mechanical symptom of it
                # that we can catch, so it is refused rather than discovered on
                # the console. A length-preserving edit that introduces a new
                # dependency would slip through this and still be fatal.
                # A raw binary blob is reported as "plain" so the
                # container sniffer never touches it, but that is about
                # SNIFFING, not about being free-form text. Its layout is as
                # fixed as any cooked container, so it is held to the same
                # rule here.
                #
                # The one exception is an op whose whole job is to supply a
                # DIFFERENT recording -- `team_recording`, which hands split
                # screen the recording a boot that creates the operatives
                # reads. It is not an edit of the old stream but a
                # replacement for it, and it proves its own output byte for
                # byte against both the stock split-screen and single-player
                # recordings before returning (see `rsesplice`). It is only
                # ever emitted together with the team code that makes the
                # boot read it.
                raw = ent.path.upper().endswith(_RAW_SUFFIXES)
                if (len(new) != len(plain) and (kind != "plain" or raw)
                        and edit.op not in _RECORDING_OPS
                        and edit.op not in _GROWS_SAFELY):
                    raise DataEditError(
                        "%s: %s changed the file length by %+d, which a %s "
                        "container is not allowed to do -- see the note in "
                        "dataedit.py" % (ent.path, edit.op,
                                         len(new) - len(plain),
                                         "raw binary" if raw else kind))
                if n:
                    counts[edit.op] = counts.get(edit.op, 0) + n
                pending[slot] = (arc, ent, new)

    # Anything an earlier run edited that this one does not want back.
    #
    # `pending` is the whole of what the current settings ask for, so a file the
    # store remembers and `pending` does not name is a leftover from a setting
    # that has since been switched off. The loop above cannot see it: it walks
    # the edits, and a setting at its default produces no edit, so the file is
    # never visited and its modified bytes stay on the disc. That breaks the
    # promise the comment above makes -- moving a setting back to its default
    # must actually undo it -- and it breaks it silently, because `verify_data`
    # only asks whether the file still decodes, which a leftover edit does.
    restored = 0
    if selector is None:
        for rec in store.entries():
            arc = arcs.get(rec["archive"].upper())
            if arc is None:
                continue
            ent = arc.files.get(rec["path"].upper())
            if ent is None or (rec["archive"], ent.path) in pending:
                continue
            got = store.original(rec["archive"], rec["path"])
            if got is None:
                continue
            data, offset = got
            if ent.offset == offset and arc.read_entry(ent) == data:
                continue                   # already stock, nothing to undo
            if ent.offset != offset:
                arc.r.write(ent.offset, b"\x00" * ent.size)
            arc.r.write(offset, data)
            arc._set_entry(ent, offset, len(data), data=data)
            restored += 1
        if restored:
            say("Put back %d file%s an earlier run had edited"
                % (restored, "" if restored == 1 else "s"))

    # write, biggest first
    #
    # Everything below this line used to happen in silence, and re-deflating a
    # 5 MB script package at maximum effort takes long enough that the log
    # looked identical to a hang -- which is exactly how it was read. So say
    # what is in flight BEFORE starting on it, not after finishing: a line
    # that appears once the slow part is over is no use to anyone watching.
    built, put_back, fitted = [], 0, 0
    total = len(pending)
    if total:
        say("  %d file%s to rebuild" % (total, "" if total == 1 else "s"))
    for n, ((arc_name, path), (arc, ent, plain)) in enumerate(
            pending.items(), 1):
        beat(n - 1, total)
        if len(plain) >= _CHATTY_BYTES or n % 25 == 0 or n == total:
            say("  packing %d/%d (%d%%)  %s"
                % (n, total, (n - 1) * 100 // total, path))
        original = store.original(arc_name, path)
        source = original[0] if original else arc.read_entry(ent)
        kind, was = _unpack(source, path)
        if was == plain:
            # The settings ask for the stock file. That is not the same as
            # "nothing to do": an earlier run may have written an edit here,
            # and `was`/`plain` are both computed from the STORED ORIGINAL, so
            # they agree with each other while disagreeing with the disc. Put
            # the original bytes back rather than re-pack them -- a LIN does
            # not deflate to the same bytes twice, so re-packing would be a
            # gratuitous rewrite that cannot even be checked for equality.
            if original and arc.read_entry(ent) != original[0]:
                built.append((len(original[0]), arc, ent, original[0],
                              (original[1], len(original[0]))))
                put_back += 1
            continue
        packed = _repack(kind, source, plain)
        # The offset the file SHIPPED at. An edit that makes a file bigger than
        # its slot has to relocate it, and a single byte is enough; passing home
        # through means the next edit that fits puts it back, instead of leaving
        # it wherever the first overflow landed.
        home = (original[1], len(original[0])) if original else None
        if kind == "plain":
            # Spend a few inert bytes rather than move -- see `_fit_plain`.
            # There is one 64 KB pad in these archives and a single loadout
            # change asks for twice it, so relocating on a one-byte overshoot
            # is what runs a disc out of room.
            #
            # HOME is tried before the looser figure, and the order is the
            # whole point. A file already exiled to the pad has the rest of
            # the pad behind it, so `room_for` calls it comfortable and
            # nothing shrinks it -- it would sit there for ever, holding the
            # one run big enough to matter. Aiming at its original slot
            # instead brings it back and hands that run over, so a disc that
            # has been patched into fragments repairs itself.
            for target in ([home[1]] if home else []) + [arc.room_for(ent, home)]:
                if len(packed) <= target:
                    break
                shorter = _fit_plain(packed, target)
                if len(shorter) <= target:
                    fitted += 1
                    packed = shorter
                    break
        built.append((len(packed), arc, ent, packed, home))
    built.sort(key=lambda r: -r[0])

    # Homecoming, before a single byte is allocated.
    #
    # An edit that outgrew its slot moved the file to the one 64 KB pad these
    # archives have, and the allocator then handed the slot it vacated to the
    # NEXT file that outgrew its own. Do that a few times and the exiles are
    # interlocked -- each sitting in another's slot -- so every single attempt
    # to go home fails on "someone else lives there now", the pad stays full,
    # and the next edit that needs a long run has nowhere to go. That is a
    # disc that has been patched a few times, and it is how this one arrived:
    # 64 KB largest free run when it shipped, 10 KB by the time it broke.
    #
    # One move frees one slot, which may be exactly what another file was
    # waiting for, so this repeats until a pass changes nothing. Each move is
    # the same guarded operation as before -- it still refuses an occupied or
    # undersized slot -- so the worst case is that nothing moves. Bounded by
    # the number of files, because every pass that continues has moved one.
    going = [r for r in built if r[4] and r[2].offset != r[4][0]]
    homecoming = 0
    for _round in range(len(going) + 1):
        moved = 0
        for _size, arc, ent, packed, home in going:
            if ent.offset != home[0] and arc.send_home(ent, packed, home):
                moved += 1
        homecoming += moved
        if not moved:
            break
    if homecoming:
        say("  %d file%s moved back to the slot it shipped in"
            % (homecoming, "" if homecoming == 1 else "s"))

    written = 0
    for size, arc, ent, packed, home in built:
        try:
            arc.write(ent.path, packed, home=home)
        except VokesError as exc:
            raise DataEditError("%s: %s" % (ent.path, exc)) from exc
        written += 1
        if written % 10 == 0:
            say("  %d of %d data files rewritten" % (written, len(built)))
    beat(total, total)
    if fitted:
        say("  %d file%s shortened to stay in place rather than relocate"
            % (fitted, "" if fitted == 1 else "s"))
    if built:
        say("Rewrote %d data file%s" % (written, "" if written == 1 else "s"))
    return {"files": written - put_back, "restored": restored + put_back,
            "changes": counts}


def _outside(lo, hi, keep):
    """[lo, hi) with every interval in `keep` cut out of it."""
    spans = [(lo, hi)]
    for klo, khi in sorted(keep):
        out = []
        for slo, shi in spans:
            if khi <= slo or klo >= shi:
                out.append((slo, shi))
                continue
            if slo < klo:
                out.append((slo, klo))
            if khi < shi:
                out.append((khi, shi))
        spans = out
        if not spans:
            break
    return spans


def revert_data(iso, profile, store, progress=None):
    """Put every remembered file back, at the offset it came from.

    Three passes, because one is not safe. An edit that outgrew its slot moved
    to the archive's pad, and the allocator then handed the slot it vacated to
    the NEXT file that outgrew its own, so the exiles interlock -- each sitting
    in another's home. Restoring them one at a time, each "blank where I sit
    now, then write me home", makes them destroy each other: A writes itself
    home over B, which is living there, and B then blanks that very stretch on
    its way out. `apply_data` already knows about interlocking and unwinds it
    with a repeated homecoming loop; this function did not, and the result was
    silent. On Sum of All Fears, reverting eleven edited `.GTF` files left
    three of them unreadable in both archives -- two blanked, one truncated --
    while the call reported success.

    So: work out where everything is going first, never blank a byte that
    belongs to some file's home, and read the lot back before saying it worked.
    """
    arcs = _archives(iso, profile)
    jobs = []
    for rec in store.entries():
        arc = arcs.get(rec["archive"].upper())
        if arc is None:
            continue
        got = store.original(rec["archive"], rec["path"])
        if got is None:
            continue
        data, offset = got
        ent = arc.files.get(rec["path"].upper())
        if ent is None:
            continue
        jobs.append((arc, ent, data, offset))

    # every byte about to hold a restored file, per archive
    homes = {}
    for arc, _ent, data, offset in jobs:
        homes.setdefault(id(arc), []).append((offset, offset + len(data)))

    # 1. blank the slots the exiles are vacating -- minus anything that is
    #    some file's home, which is the part the old code got wrong
    for arc, ent, data, offset in jobs:
        if ent.offset == offset:
            continue
        for lo, hi in _outside(ent.offset, ent.offset + ent.size,
                               homes[id(arc)]):
            arc.r.write(lo, b"\x00" * (hi - lo))

    # 2. put every file back where it shipped
    done = 0
    for arc, ent, data, offset in jobs:
        arc.r.write(offset, data)
        arc._set_entry(ent, offset, len(data), data=data)
        done += 1
        if progress and done % 10 == 0:
            progress("  %d files restored" % done)

    # 3. read them back. A restore that quietly leaves a file undecodable is
    #    worse than one that fails, because the disc looks fine until the game
    #    reaches that file.
    broken = []
    for arc, ent, _data, _offset in jobs:
        try:
            _unpack(arc.read_entry(ent), ent.path)
        except Exception:                          # noqa: BLE001
            broken.append(ent.path)
    if broken:
        raise DataEditError(
            "restore left %d file(s) unreadable: %s"
            % (len(broken), ", ".join(sorted(broken)[:6])))

    store.forget_all()
    return {"files": done, "broken": len(broken)}


def verify_data(iso, profile, store):
    """Read back every file we touched and confirm it still decodes."""
    arcs = _archives(iso, profile)
    ok = bad = 0
    for rec in store.entries():
        arc = arcs.get(rec["archive"].upper())
        ent = arc.files.get(rec["path"].upper()) if arc else None
        if ent is None:
            bad += 1
            continue
        try:
            _unpack(arc.read_entry(ent), ent.path)
            ok += 1
        except Exception:                       # noqa: BLE001
            bad += 1
    return ok, bad

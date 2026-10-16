"""Port Ghost Recon's campaign into Jungle Storm's slots.

Ghost Recon (SLUS-20613) and Jungle Storm (SLUS-20820) are the same Red Storm
engine, so Ghost Recon's fifteen campaign missions can be made to play on a
Jungle Storm disc -- in single player, in split screen and over LAN. This
module does the whole port from the two retail discs.

It is NOT a `FileEdit`. Those are length-preserving edits of one disc's own
files; this reads a SECOND disc and writes files of a different size, so it
runs as its own pass and produces a NEW image rather than mutating one in
place. That also keeps it clear of the word store's apply/revert contract.

WHAT THE PORT HAS TO GET RIGHT
------------------------------
Every one of these was a silent hang before it was understood, so none of them
is optional:

* STORAGE FORM. Each file must be stored the way THE SLOT stores it, packed or
  plain. Hand the loader an unpacked file where it expects a packed one and it
  hangs with no error. Never re-encode a file that is already in the right
  form -- the LZO compressor is pure Python and turns a seconds-long build
  into an hours-long one.
* PLANE SCALE. Ghost Recon stores collision plane normals as 3xs16 at length
  4096; Jungle Storm decodes them at 1/32000. Unrescaled, floors sit 7.8125x
  too high.
* ASSAULT ZONES. Every stock Jungle Storm mission carries exactly nine zones
  tagged AssaultPlatoon 0/1/2 and one CoopBase; no Ghost Recon mission carries
  either.
* THE BODY STRIP. Campaign-only zone attributes, `<LoadingBytes>`,
  `<RequiresUnlocking>`, `<AssaultZones>`, and the ambient `<Sound>` emitters
  (a clip the level's sound bank cannot resolve hangs the load).
* STRING IDS. One group per mission, and the map name sits at a DIFFERENT
  index per mission, so the slot's Shell ids must be rebased onto the donor's.
* `<MapShots>`. Every stock mission names a `<stem>_shots.rsb` that is not on
  the disc. Normal play never opens it, but some menu paths do, and a failed
  texture open leaks the texture manager's lock and hangs. Point it at the
  slot's command map, which exists.
* `<JungleMap>`. A Jungle Storm renderer flag that no Ghost Recon environment
  sets.

The split-screen briefing mod (`js_ss_briefing`) must be OFF on the finished
disc: its Accept opens `SINGLE_PLATOON`, which is not registered in the
split-screen container, and the engine's OPEN_SCREEN handler does nothing at
all for a screen it cannot find.
"""
from __future__ import annotations

import collections
import math
import os
import re
import shutil
import struct

from . import rselzo, vokes
from .iso import Iso

#: Ghost Recon mission, the stem its geometry uses, and the Jungle Storm slot.
#: The slots are in the boot ELF's mission-table ROW order, which is the order
#: the menu walks and the order the unlock chain follows: rows 0-7 are the
#: C01-C08 chain, rows 23-30 the J01-J08 chain.
PLAN = (
    ("M01_CAVES", "M01_CAVES", "C01_PLANTATION"),
    ("M02_FARM", "M02_FARM", "C02_MILITARY_CAMP"),
    ("M03_RRBRIDGE", "M03_RRBRIDGE", "C03_HIGH_SIERRA"),
    ("M04_VILLAGE", "M04_VILLAGE", "C04_SWAMP_AIRFIELD"),
    ("M05_EMBASSY", "M05_EMBASSY", "C05_BRIDGES"),
    ("M06_CASTLE", "M06_CASTLE", "C06_POLLING_CENTER"),
    ("M07_RIVER", "M07_RIVER", "C07_BEACH_RESORT"),
    ("M08_BATTLEFIELD", "M08_BATTLEFIELD", "C08_MOUNTAIN_STRONGHOLD"),
    ("M09_SWAMP", "M09_SWAMP", "G03_THE_ROCK"),
    ("M10_RUINED_CITY", "M10_VILNIUS", "G04_TRAIN"),
    ("M11_POW_CAMP", "M11_POW_CAMP", "U05_RAIL"),
    ("M12_DOCKS", "M12_DOCKS", "G02_VILLAGE"),
    ("M13_AIRBASE", "M13_AIRBASE", "G05_DOCK"),
    ("M14_MOUNTAIN", "M14_MOUNTAIN", "U02_RIVER"),
    ("M15_RED_SQUARE", "M15_RED_SQUARE", "U03_RESCUE"),
)

#: Desert Siege. Ghost Recon's expansion ships eight campaign missions and five
#: Defend maps; Jungle Storm's own MP, Defend and co-op slots take them. Those
#: slots do NOT carry the campaign bit at +0x48, so each needs one ELF word
#: before it appears in Mission Co-op -- see `enable_coop_slots`.
DS_PLAN = (
    ("D01_BEACH", "D01_BEACH", "MP01_RIVER"),
    ("D02_REFINERY", "D02_REFINERY", "MP02_NIGHTBATTLE"),
    # the only Desert Siege mission whose geometry stem differs from its name
    ("D03_TRAINDEPOT", "D03_DEPOT", "MP03_RAILROAD"),
    ("D04_RIVERBED", "D04_RIVERBED", "MP04_VALLEY"),
    ("D05_AURORA", "D05_AURORA", "MP05_DOCKS"),
    ("D06_GHOSTTOWN", "D06_GHOSTTOWN", "DP01_STRONGHOLD"),
    ("D07_ROADBLOCK", "D07_ROADBLOCK", "DP02_FARM_DAY"),
    ("D08_TANK", "D08_TANK", "DP03_CREEKBED"),
    ("DP01_STRONGHOLD", "DP01_STRONGHOLD", "DP04_WILDERNESS"),
    ("DP02_FARM_DAY", "DP02_FARM_DAY", "DP05_RAVINE"),
    ("DP03_CREEKBED", "DP03_CREEKBED", "CP01_HUNTING_LODGE"),
    ("DP04_WILDERNESS", "DP04_WILDERNESS", "CP02_ISLAND"),
    ("DP05_RAVINE", "DP05_RAVINE", "CP03_PRISON"),
)

#: mission-table row for each slot the Desert Siege plan uses
DS_ROWS = {"MP01_RIVER": 8, "MP02_NIGHTBATTLE": 9, "MP03_RAILROAD": 10,
           "MP04_VALLEY": 11, "MP05_DOCKS": 12, "DP01_STRONGHOLD": 13,
           "DP02_FARM_DAY": 14, "DP03_CREEKBED": 15, "DP04_WILDERNESS": 16,
           "DP05_RAVINE": 17, "CP01_HUNTING_LODGE": 18, "CP02_ISLAND": 19,
           "CP03_PRISON": 20}


TERRAIN = (".AOL", ".BMZ", ".MAZ", ".MOL", ".POL", ".SHT")
SKY_PARTS = (".POB", "_SKY.BMZ", "_SKY.POZ")
MODEL_PARTS = (".CHZ", ".CHA", ".BMZ")
MODEL_TAGS = ("ModelName", "LOD2", "LOD3")
#: campaign-only zone attributes; Jungle Storm's own co-op zones carry none
ZONE_ATTRS = ("Sound", "EnvTag", "Extraction", "Type")
LANGS = ("EN", "FR", "DE", "IT", "ES")
#: Templates whose TEMPLATE must never be repointed.
#:
#: The four class rosters are globbed by directory (`actor\rifleman\*.atr` at
#: VA 0x0058EEA0 and siblings), which is what `RIFLEMAN-` / `SNIPER-` / `DEMO`
#: / `HEAVY-` catch. The other three families are reached by name instead and
#: were invisible to the original guard:
#:
#:   the eleven named specialists are listed ONE BY ONE in the boot ELF
#:   (`will_jacobs.atr` .. `santiago_gonzalez.atr`, VA 0x0058F060..0x0058F155)
#:   and NO `.MIS` on the disc references them, so both arms of the protection
#:   test were false and all eleven went into the enemy pool. Measured on the
#:   disc that shipped: every one carried `<ActorName>a Russian</ActorName>`
#:   and an EMPTY `<KitPath/>`, which is why they appeared in Platoon Setup as
#:   "a. Russian / Demo" with no weapon and no HUD -- a kit path that matches
#:   no row of the ELF's kit table globs nothing. Their `.KIT` files were
#:   never touched, so the repair is the `.ATR` alone.
#:
#:   `OPPOSING_FORCE_JUNGLE_0..6` is the shared wave roster, loaded by the
#:   literal `opposing_force_jungle_%i.atr` (VA 0x00594F00, four call sites).
#:   Jungle Storm's MP/DP/CP slots ship ZERO scripted actors, so for the
#:   thirteen Desert Siege missions ported into them it is the only enemy
#:   source -- and the port had rewritten all seven to Russian winter models.
#:
#:   `_G_` is the cross-mission pool: civilians, hostages, POWs, UN
#:   peacekeepers, Marines and the player's own Ghosts.
#:
#: `CIVILIAN_SLOTS` and `US_SLOTS` below are MODEL stems; no `.ATR` on the disc
#: carries those names, so they never protected anything at template level.
ROSTER = re.compile(r"^(MP_PLT|ONLINE\d|RIFLEMAN-|SNIPER-|SUPPORT-|DEMO|HEAVY-"
                    r"|_G_|NPC_|OPPOSING_FORCE)", re.I)
#: The class rosters alone -- the player's own soldiers, whose MESHES have to
#: be held back as well as their templates. Everything else in `ROSTER` keeps
#: its template but releases its model, because the model budget is the tight
#: one: a hostage wearing a ported enemy mesh is cosmetic, a hostage wearing an
#: enemy TEMPLATE is not.
ROSTER_OWN = re.compile(r"^(MP_PLT|ONLINE\d|RIFLEMAN-|SNIPER-|SUPPORT-|DEMO|HEAVY-)", re.I)
#: A template the kit system can equip is by definition player-selectable.
#: Catches the specialists and the Ghosts by CONTENT, so a rename cannot
#: silently hand a player soldier to the enemy allocator.
KIT_BEARING = re.compile(r"<KitPath>\s*[^<\s][^<]*</KitPath>", re.I)
#: `HOST\d` is Desert Siege's hostages. Without it they enter the enemy pool
#: and alias to an armed regular -- the same defect the POW note below calls
#: out, measured on D02_REFINERY's three workers.
CIVILIAN = re.compile(r"^(MAN_|WOMAN_|CHILD|CIV|HOST\d)", re.I)
US_NPC = re.compile(r"^NPC_US_", re.I)
#: Ghost Recon's two enemy factions. The campaign names its models
#: `RS_<THEATRE>_*` and `ICE_REBEL_*`; Desert Siege's are flat and carry no
#: underscore at all (`REG1`, `IRR2`, `ERI3`, `WARLORD`), so `prefix()` below
#: can never pair a Desert Siege model with a sibling and every one of them
#: reached the `keep[0]` fallback. Used to keep an aliased model inside its own
#: faction: before this, three campaign models fell back to a Desert Siege
#: African and rendered as such in Georgia and Moscow.
CAMPAIGN_MODEL = re.compile(r"^(RS_|ICE_REBEL)", re.I)
#: held back from the enemy pool and left with their own content, as the
#: targets civilians and friendlies are pointed at. Rendering a POW as an armed
#: soldier is not cosmetic: M11 asks you to rescue them.
CIVILIAN_SLOTS = ("CBN_CIVILIAN1", "CBN_CIVILIAN2", "CBN_HOST1_A", "CBN_HOST2_A")
US_SLOTS = ("MARINE_RIFLEMAN", "MARINE_SNIPER", "MARINE_SUPPORT", "MARINE_DEMOLITION")
#: the player's own Ghosts, by Jungle Storm slot -> Ghost Recon source
GHOST_SUFFIX = re.compile(r"_(CUBA|DESERT)$")

GR_SERIAL = "SLUS_206.13"
JS_SERIAL = "SLUS_208.20"

#: free space the mission loop needs in GR.IMG before it writes anything. The
#: disc this was developed against had been grown by hand and carried 56 MB of
#: slack; a retail disc carries 64 KB, which is 156 bytes short of the first
#: file the port writes. 128 MB covers the whole mission pass with margin, and
#: the later steps still grow the archive for themselves on top of it.
PORT_HEADROOM = 128 << 20


class PortError(Exception):
    pass


# --------------------------------------------------------------- small helpers

def plain(data: bytes) -> bytes:
    return rselzo.decompress(data) if rselzo.is_compressed(data) else data


def tag(text: str, name: str):
    m = re.search(r"<%s>([^<]*)</%s>" % (name, name), text)
    return m.group(1) if m else None


def basename_of(value: str) -> str:
    return os.path.basename((value or "").upper().replace("\\", "/"))


def find_donor(js_iso_path: str):
    """A Ghost Recon disc beside the Jungle Storm one, or None.

    There is no path-typed setting in the profile model, so the donor is found
    rather than asked for: any .iso in the same folder whose volume carries
    Ghost Recon's serial.
    """
    folder = os.path.dirname(os.path.abspath(str(js_iso_path)))
    serial = GR_SERIAL.encode()
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(".iso"):
            continue
        path = os.path.join(folder, name)
        if os.path.abspath(path) == os.path.abspath(str(js_iso_path)):
            continue
        try:
            with open(path, "rb") as fh:
                if serial in fh.read(4 << 20):
                    return path
        except OSError:
            continue
    return None


# ------------------------------------------------------------ collision planes

def _load_molcheck():
    """The model walker.

    It used to be loaded by file path out of `research/code/`, which is not in
    the built executable -- every packaged run died with FileNotFoundError on
    the first terrain file. It lives in the package now.
    """
    from . import molcheck
    return molcheck


def rescale_planes(mol: bytes) -> bytes:
    """Rescale every collision plane normal from length 4096 to 32000.

    The file length never changes: each normal is three s16 rewritten in place,
    and `d` is left alone.
    """
    mc = _load_molcheck()
    offs = []

    def walk(r):
        mc.draw_object(r)
        r.skip(12 * r.u32())
        for _ in range(r.u32()):
            mc.draw_object(r)
            for _ in range(r.u32()):
                offs.append(r.p)
                r.skip(10)
                r.u16(); r.u16(); r.u16()
        for _ in range(max(r.i32(), 0)):
            r.name(); r.skip(28)
        r.skip(12 * r.u32())
        for _ in range(r.u32()):
            offs.append(r.p); r.skip(10)
        for _ in range(r.u32()):
            r.u16(); r.u16(); r.u16()
        for _ in range(r.u32()):
            r.name(); r.u32(); r.i32(); r.u32(); r.i32()
            for _ in range(r.u32()):
                r.u16(); r.u16(); r.u16()

    _a, _b, _c, _d, q = mc.header(mol, 8)
    count = struct.unpack_from("<I", mol, q)[0]
    p = q + 4
    for _ in range(count):
        size, _t, _n, _v, cq = mc.header(mol, p)
        reader = mc.Reader(mol, cq)
        try:
            walk(reader)
        except Exception:
            pass          # a chunk we cannot walk simply contributes no planes
        p = cq + size

    out = bytearray(mol)
    for off in offs:
        x, y, z = struct.unpack_from("<3h", out, off)
        length = math.sqrt(x * x + y * y + z * z)
        if length < 1:
            continue
        k = 32000.0 / length
        struct.pack_into("<3h", out, off,
                         *(max(-32768, min(32767, int(round(v * k))))
                           for v in (x, y, z)))
    return bytes(out)


# ------------------------------------------------------------------- strings

def parse_res(blob: bytes):
    p = 0
    n = struct.unpack_from("<I", blob, p)[0]
    p += 4
    groups = []
    for _ in range(n):
        count = struct.unpack_from("<I", blob, p)[0]
        p += 4
        items = []
        for _i in range(count):
            ln = struct.unpack_from("<I", blob, p)[0]
            p += 4
            items.append(blob[p:p + ln])
            p += ln + 2
        p += 4
        groups.append(items)
    return groups


def build_res(groups) -> bytes:
    out = bytearray(struct.pack("<I", len(groups)))
    for items in groups:
        out += struct.pack("<I", len(items))
        for s in items:
            out += struct.pack("<I", len(s)) + s + b"\x00\x00"
        out += b"\x00\x00\x00\x00"
    return bytes(out) + b"\x00\x00\x00\x00"


# ------------------------------------------------------------- mission body

def models_of(text: str):
    out = set()
    for name in MODEL_TAGS:
        for m in re.finditer(r"<%s>([^<]*)</%s>" % (name, name), text):
            v = m.group(1).strip().upper().rsplit(".", 1)[0]
            if v:
                out.add(v)
    return out


def actors_of(body: str):
    return {x.upper()[:-4]
            for x in re.findall(r'File\s*=\s*"([^"]*\.atr)"', body, re.I)}


def add_support_zones(body: str) -> str:
    """Add the nine AssaultPlatoon zones and the CoopBase a port needs."""
    if len(re.findall(r"AssaultPlatoon", body)) >= 9 and "CoopBase" in body:
        return body
    igor = max([int(x) for x in re.findall(r'IgorId\s*=\s*"(\d+)"', body)] or [0]) + 100
    script = max([int(x) for x in re.findall(r'ScriptId\s*=\s*"(\d+)"', body)] or [0]) + 100

    def boxes(pattern):
        return [(m.group(1), m.group(2)) for m in re.finditer(pattern, body)]

    anchors = boxes(r'<Zone[^>]*Name\s*=\s*"Map Base \d+"[^>]*'
                    r'Pos0\s*=\s*"([^"]*)"\s*Pos1\s*=\s*"([^"]*)"')
    if len(anchors) < 3:
        anchors += boxes(r'<Zone(?![^>]*CoopBase)[^>]*Pos0\s*=\s*"([^"]*)"\s*'
                         r'Pos1\s*=\s*"([^"]*)"[^>]*(?<!Coop)Base\s*=\s*"\d+"')
    if len(anchors) < 3:
        anchors += boxes(r'<Zone[^>]*Pos0\s*=\s*"([^"]*)"\s*Pos1\s*=\s*"([^"]*)"'
                         r'[^>]*Insertion\s*=\s*"1"')
    if not anchors or "</ZoneList>" not in body:
        return body
    while len(anchors) < 3:
        anchors.append(anchors[0])

    def pos(s):
        return [float(x) for x in s.strip().strip(";").split(";")]

    new = []
    for platoon in range(3):
        p0, p1 = pos(anchors[platoon][0]), pos(anchors[platoon][1])
        axis = 0 if abs(p1[0] - p0[0]) >= abs(p1[1] - p0[1]) else 1
        lo, hi = min(p0[axis], p1[axis]), max(p0[axis], p1[axis])
        step = (hi - lo) / 3.0
        for i, letter in enumerate("abc"):
            q0, q1 = list(p0), list(p1)
            q0[axis] = lo + step * i
            q1[axis] = lo + step * (i + 1)
            new.append('<Zone IgorId = "%d" ScriptId = "%d" Name = "AP %d%s" '
                       'Pos0 = "%.2f;%.2f;%.2f;" Pos1 = "%.2f;%.2f;%.2f;" '
                       'AssaultPlatoon = "%d"/>'
                       % (igor, script, platoon, letter,
                          q0[0], q0[1], q0[2], q1[0], q1[1], q1[2], platoon))
            igor += 1
            script += 1
    if "CoopBase" not in body:
        ins = re.search(r'<Zone[^>]*Pos0\s*=\s*"([^"]*)"\s*Pos1\s*=\s*"([^"]*)"'
                        r'[^>]*Insertion\s*=\s*"1"', body)
        a0, a1 = (ins.group(1), ins.group(2)) if ins else anchors[0]
        new.append('<Zone IgorId = "%d" ScriptId = "%d" Name = "Base 00" '
                   'Pos0 = "%s" Pos1 = "%s" Base = "0" CoopBase = "1"/>'
                   % (igor, script, a0, a1))
    block = "\n\t\t\t" + "\n\t\t\t".join(new) + "\n\t\t"
    return body.replace("</ZoneList>", block + "</ZoneList>", 1)


def drop_sound_emitters(text: str) -> str:
    """Remove every <Sound ...>...</Sound>, children included.

    A clip the level's bank cannot resolve hangs the load, and which names a
    bank holds is not derivable from the mission files, so they all go. Only
    the wildlife ambience is lost.
    """
    out, i = [], 0
    while True:
        m = re.compile(r"<Sound\b").search(text, i)
        if not m:
            out.append(text[i:])
            break
        out.append(text[i:m.start()])
        close = text.find(">", m.start())
        if close != -1 and text[close - 1] == "/":
            i = close + 1
        else:
            end = text.find("</Sound>", close)
            i = (end + len("</Sound>")) if end != -1 else close + 1
        while i < len(text) and text[i] in "\r\n":
            i += 1
        while i < len(text) and text[i] == "\t":
            i += 1
    return "".join(out)


def fix_objects(text: str) -> str:
    """Give every placed object Jungle Storm's `ObjectKind`.

    `ObjectKind` is a Jungle Storm addition that no Ghost Recon mission sets:
    all 46 of JS's own mounted guns carry `ObjectKind = "0"`. Without it a
    ported emplacement is placed in some game modes and not others -- the
    stationary gun shows up in Firefight but is missing in Mission Co-op.
    """
    def fix(m):
        tag_text = m.group(0)
        if "ObjectKind" in tag_text or "File" not in tag_text:
            return tag_text
        return tag_text[:-2].rstrip() + ' ObjectKind = "0"/>' \
            if tag_text.endswith("/>") else tag_text
    return re.sub(r"<Object\b[^>]*/>", fix, text)


def strip_body(text: str) -> str:
    text = fix_objects(text)
    text = drop_sound_emitters(text)

    def fix(m):
        s = m.group(0)
        for a in ZONE_ATTRS:
            s = re.sub(r'\s+%s\s*=\s*"[^"]*"' % a, "", s)
        return s

    text = re.sub(r"<Zone\b[^>]*>", fix, text)
    for name in ("LoadingBytes", "RequiresUnlocking", "AssaultZones"):
        text = re.sub(r"\s*<%s>[^<]*</%s>" % (name, name), "", text)
    return text


def merge_shell(donor_body: str, slot_body: str, slot_group: int) -> str:
    """The slot's Shell, with the donor's name tags rebased onto its indices.

    The slot's Shell carries the menu placement and the mode flags, so it has
    to stay -- but its name ids point at the SLOT's indices, and the string
    group behind them will hold the DONOR's strings. The map name sits at a
    different index in every mission, so keeping the slot's id makes the menu
    read a status message instead of a name.
    """
    gsh = re.search(r"<Shell>.*?</Shell>", donor_body, re.S).group(0)
    ssh = re.search(r"<Shell>.*?</Shell>", slot_body, re.S).group(0)
    shell = ssh
    for name, idname in (("MapName", "MapNameId"), ("Name", "NameId")):
        gt = re.search(r"<%s>([^<]*)</%s>" % (name, name), gsh)
        gi = re.search(r"<%s>(\d+)</%s>" % (idname, idname), gsh)
        if gt:
            shell = re.sub(r"<%s>[^<]*</%s>" % (name, name),
                           "<%s>%s</%s>" % (name, gt.group(1), name), shell, count=1)
        if gi:
            new = (slot_group << 20) | (int(gi.group(1)) & 0xFFFFF)
            shell = re.sub(r"<%s>\d+</%s>" % (idname, idname),
                           "<%s>%d</%s>" % (idname, new, idname), shell, count=1)
    if "RecommendedGameTypesID" in shell and "RecommendedGameTypesID" not in gsh:
        shell = re.sub(r"\s*<RecommendedGameTypes\s*/>", "", shell)
        shell = re.sub(r"\s*<RecommendedGameTypesID>\d+</RecommendedGameTypesID>", "", shell)
    return donor_body.replace(gsh, shell)


# ------------------------------------------------------------------ the port

def _put(index, name, data):
    """Write into an existing slot, in THAT SLOT's storage form.

    When the source is already in the slot's form the bytes go through
    untouched. Re-encoding them instead runs a pure-Python LZO compressor over
    multi-megabyte files and turns a seconds-long build into an hours-long one.
    """
    if name not in index:
        return False
    arc, key = index[name]
    packed = rselzo.is_compressed(arc.read_file(key))
    src_packed = rselzo.is_compressed(data)
    if src_packed == packed:
        blob = data
        raw = len(rselzo.decompress(data)) if packed else len(data)
    else:
        body = plain(data)
        blob = rselzo.compress(body) if packed else body
        raw = len(body)
    arc.write(key, blob, raw_size=raw)
    return True


def _read_donor(gr_path, plan=PLAN):
    """Everything the port needs from the Ghost Recon disc, in one pass."""
    want_terrain = {g for _m, g, _s in plan}
    want_mission = {m for m, _g, _s in plan}
    out = {"mis": {}, "atr": {}, "env": {}, "res": None, "pak": {}, "rsb": {},
           "sky": {},
           "terrain": collections.defaultdict(dict),
           "model": collections.defaultdict(dict)}
    with Iso(gr_path) as iso:
        for arc in vokes.open_archives(iso):
            for key in list(arc.files):
                base = os.path.basename(key.upper().lstrip("/"))
                stem, ext = os.path.splitext(base)
                if ext == ".MIS" and stem in want_mission and stem not in out["mis"]:
                    out["mis"][stem] = plain(arc.read_file(key)).decode("latin-1")
                elif ext == ".ATR" and stem not in out["atr"]:
                    out["atr"][stem] = plain(arc.read_file(key)).decode("latin-1")
                elif ext == ".ENV" and stem not in out["env"]:
                    out["env"][stem] = plain(arc.read_file(key)).decode("latin-1")
                elif ext in TERRAIN and stem in want_terrain:
                    out["terrain"][stem].setdefault(ext, arc.read_file(key))
                elif ext in MODEL_PARTS:
                    out["model"][stem].setdefault(ext, arc.read_file(key))
                elif ext == ".PAK" and base not in out["pak"]:
                    out["pak"][base] = arc.read_file(key)
                elif ext == ".RSB" and base not in out["rsb"]:
                    out["rsb"][base] = arc.read_file(key)
                if (base.endswith((".POB", ".POZ")) or base.endswith("_SKY.BMZ")) \
                        and base not in out["sky"]:
                    out["sky"][base] = arc.read_file(key)
                if base == "EN_STRINGS.RES" and out["res"] is None:
                    out["res"] = parse_res(plain(arc.read_file(key)))
    return out


def _allocate_enemies(donor, js_atr, js_ext, js_mis, replaced, plan=PLAN):
    """Jungle Storm slots for Ghost Recon's templates and models.

    Two budgets, and only one is tight: .ATR is plentiful, .CHZ is not. The
    player's own Ghosts are named from the ROSTER templates rather than from
    any mission, so a free-slot calculation that only reads mission File= refs
    will happily overwrite them -- hence the ROSTER guard.
    """
    needed = set()
    for mission, _geo, _slot in plan:
        body = donor["mis"].get(mission)
        if body:
            needed |= {t for t in actors_of(body) if t in donor["atr"]}

    users = collections.defaultdict(set)
    for name, body in js_mis.items():
        for t in actors_of(body):
            users[t].add(name)

    # TWO budgets, protected separately. `.ATR` is plentiful and a template is
    # what carries the name, the class and the kit path, so everything the
    # player can meet as a person keeps its template. Models are scarce, so
    # only the player's OWN soldiers keep their meshes; holding back every
    # protected family's models as well collapses the enemy pool to one slot.
    protected_models, protected_atr = set(), set()
    for t, text in js_atr.items():
        mission_held = bool(users.get(t, set()) - replaced)
        kit = KIT_BEARING.search(text)
        if ROSTER.match(t) or kit or mission_held:
            protected_atr.add(t)
        if ROSTER_OWN.match(t) or kit or mission_held:
            protected_models |= models_of(text)

    free_models = [s for s, e in js_ext.items()
                   if set(MODEL_PARTS) <= e and s not in protected_models]
    free_atr = sorted(s for s, e in js_ext.items()
                      if ".ATR" in e and s not in protected_atr)
    # No count check here: templates are allocated one slot per DISTINCT
    # WRITTEN BODY, not per name, so the raw count is not the requirement.
    # The real check is after the grouping below.

    # SORTED, not set order. `Counter.most_common()` breaks ties on insertion
    # order, so iterating the set put the tie order at the mercy of per-process
    # string hashing: three runs of the same port produced three different
    # model maps and a distinct-body count that moved between 465 and 468. With
    # the margin as thin as it is, that is the difference between a build that
    # fits and one that raises PortError, for no reason the caller can see.
    usage = collections.Counter()
    for t in sorted(needed):
        m = re.search(r"<ModelName>([^<]*)</ModelName>", donor["atr"][t])
        if m:
            v = m.group(1).strip().upper().rsplit(".", 1)[0]
            if v:
                usage[v] += 1

    reserved = [s for s in CIVILIAN_SLOTS + US_SLOTS if s in free_models]
    pool = [s for s in free_models if s not in reserved]
    enemy = [m for m, _c in usage.most_common()
             if m in donor["model"] and not CIVILIAN.match(m) and not US_NPC.match(m)]
    keep = enemy[:len(pool)]
    model_slot = dict(zip(keep, pool))

    def prefix(name):
        p = name.rsplit("_", 1)[0]
        return p if len(p) > 3 else name

    def faction(name):
        return "campaign" if CAMPAIGN_MODEL.match(name) else "desert"

    alias = {}
    for m in enemy[len(pool):]:
        same = [k for k in keep if prefix(k) == prefix(m)]
        if not same:
            # Never fall back across factions while a same-faction model is
            # still standing. `keep[0]` is whichever model the whole plan uses
            # most, and with Desert Siege out-voting the campaign that was an
            # African -- so the campaign models that missed a slot rendered as
            # African regulars in Georgia and Moscow.
            same = [k for k in keep if faction(k) == faction(m)]
        alias[m] = same[0] if same else (keep[0] if keep else None)

    hold = {}
    civ = [s for s in CIVILIAN_SLOTS if s in reserved] or pool[:1]
    us = [s for s in US_SLOTS if s in reserved] or civ
    for i, m in enumerate(sorted(x for x in usage if CIVILIAN.match(x))):
        hold[m] = civ[i % len(civ)]
    for i, m in enumerate(sorted(x for x in usage if US_NPC.match(x))):
        hold[m] = us[i % len(us)]

    def slot_for(name):
        if name in model_slot:
            return model_slot[name]
        if name in hold:
            return hold[name]
        target = alias.get(name)
        return model_slot.get(target) if target else None

    # One slot per DISTINCT WRITTEN BODY, not per template name. Ghost Recon
    # names a template per mission (M01_ELI_AK47_1, D01_...), so the campaign
    # and Desert Siege together want 582 slots and only 479 are free. But the
    # model rewrite below collapses them: 70 primary models share 23 slots, so
    # templates differing only by a model that aliases to the same slot become
    # byte-identical once written. <ModelFace>/<BlinkFaceName> are inert on PS2
    # -- no face .rsb ships on either disc -- so they do not distinguish either.
    # That brings 582 down to 468, and everything fits.
    groups = collections.OrderedDict()
    for name in sorted(needed):
        text = donor["atr"][name]
        m = re.search(r"<ModelName>([^<]*)</ModelName>", text)
        primary = slot_for(m.group(1).strip().upper().rsplit(".", 1)[0]) if m else None
        body = text
        if primary:
            for tg in MODEL_TAGS:
                body = re.sub(r"<%s>[^<]*</%s>" % (tg, tg),
                              "<%s>%s.chr</%s>" % (tg, primary.lower(), tg), body)
        for tg in ("ModelFace", "BlinkFaceName", "ActorName"):
            body = re.sub(r"<%s>[^<]*</%s>" % (tg, tg), "", body)
        groups.setdefault(re.sub(r"\s+", "", body), []).append(name)
    if len(groups) > len(free_atr):
        raise PortError("not enough .ATR slots: %d distinct templates, %d free"
                        % (len(groups), len(free_atr)))
    atr_slot = {}
    for slot, members in zip(free_atr, groups.values()):
        for name in members:
            atr_slot[name] = slot
    return atr_slot, model_slot, alias, hold


def clear_split_screen_briefing(out_path):
    """Turn the split-screen briefing mod off in the finished image.

    This is not a preference. `SPBriefing::Accept` closes the briefing and
    opens `SINGLE_PLATOON`, which is NOT registered in the split-screen
    container, and the engine's OPEN_SCREEN handler does nothing at all for a
    screen it cannot find -- so a ported mission stops at the briefing with no
    dialog, no sound and no loading screen. A disc this builds would be
    unplayable with it left on.

    Only the 191 words `briefing`/`teammates` own are put back to stock; that
    set is the same whatever the other split-screen options are, so every
    other choice the disc carries is left exactly as it was.

    Returns the number of words changed.
    """
    from . import grsquad
    base = dict(fireteams=True, handoff=True, bullet_holes=True,
                orders=True, observer=True, select_aim=True)
    stock_of = {va: stock for va, _v, stock, _n
                in grsquad.js_edits(briefing=True, teammates=True, **base)}
    keeps = {va for va, _v, _s, _n
             in grsquad.js_edits(briefing=False, teammates=False, **base)}
    owned = {va: s for va, s in stock_of.items() if va not in keeps and s is not None}

    changed = 0
    with Iso(out_path, writable=True) as iso:
        ent = iso.find(JS_SERIAL)
        if ent is None:
            raise PortError("no %s on %s" % (JS_SERIAL, out_path))
        sectors = (ent.size + 2047) // 2048
        blob = bytearray(iso.read(ent.lba, sectors * 2048))
        for va, stock in owned.items():
            off = va - 0x00100000 + 0x100
            if struct.unpack_from("<I", blob, off)[0] != (stock & 0xFFFFFFFF):
                struct.pack_into("<I", blob, off, stock & 0xFFFFFFFF)
                changed += 1
        iso.write(ent.lba, bytes(blob))
        iso.flush()
    return changed


def port(js_iso_path, gr_iso_path, out_path, progress=None,
         plan=PLAN + DS_PLAN, music=True):
    """Build `out_path`: a Jungle Storm disc running Ghost Recon's campaign."""
    def say(msg):
        if progress:
            progress(msg)

    say("Reading Ghost Recon")
    donor = _read_donor(gr_iso_path, plan)
    missing = [m for m, _g, _s in plan if m not in donor["mis"]]
    if missing:
        raise PortError("that disc is missing %d Ghost Recon mission(s): %s"
                        % (len(missing), ", ".join(missing[:4])))

    say("Reading the Jungle Storm disc")
    js_mis, js_atr, js_env = {}, {}, {}
    js_ext = collections.defaultdict(set)
    with Iso(js_iso_path) as iso:
        for arc in vokes.open_archives(iso):
            for key in list(arc.files):
                base = os.path.basename(key.upper().lstrip("/"))
                stem, ext = os.path.splitext(base)
                js_ext[stem].add(ext)
                if ext == ".MIS":
                    js_mis[stem] = plain(arc.read_file(key)).decode("latin-1")
                elif ext == ".ATR":
                    js_atr[stem] = plain(arc.read_file(key)).decode("latin-1")
                elif ext == ".ENV":
                    js_env[stem] = plain(arc.read_file(key)).decode("latin-1")

    replaced = {s for _m, _g, s in plan}
    atr_slot, model_slot, alias, hold = _allocate_enemies(
        donor, js_atr, js_ext, js_mis, replaced, plan)

    def slot_for(name):
        if name in model_slot:
            return model_slot[name]
        if name in hold:
            return hold[name]
        target = alias.get(name)
        return model_slot.get(target) if target else None

    say("Copying the disc")
    shutil.copyfile(js_iso_path, out_path)

    # A STOCK Jungle Storm disc has 65,536 bytes as its largest free run in
    # GR.IMG, and the first terrain file the port writes wants 65,692 -- so the
    # mission loop dies on its first allocation with "no free run of N bytes
    # left". Every later step grows the archive for itself; this one did not,
    # and only went unnoticed because the disc it was developed against had
    # been grown by hand first. Make the room before anything needs it.
    from . import discgrow
    say("Making room in the archive")
    discgrow.grow_last_file(out_path, extra_bytes=PORT_HEADROOM)

    report = {"missions": 0, "terrain": 0, "templates": 0, "models": 0,
              "skies": 0, "paks": 0, "ghosts": 0}
    with Iso(out_path, writable=True) as iso:
        arcs = vokes.open_archives(iso)
        index = {}
        for arc in arcs:
            for key in list(arc.files):
                index.setdefault(os.path.basename(key.upper().lstrip("/")), (arc, key))

        for mission, geo, slot in plan:
            say("Porting %s into %s" % (mission, slot))
            slot_body = js_mis[slot]
            slot_group = int(re.search(r"<MapNameId>(\d+)</MapNameId>",
                                       slot_body).group(1)) >> 20
            donor_body = donor["mis"][mission]
            donor_group = int(re.search(r"<MapNameId>(\d+)</MapNameId>",
                                        donor_body).group(1)) >> 20

            for ext in TERRAIN:
                src = donor["terrain"][geo].get(ext)
                if src is None:
                    continue
                data = rescale_planes(plain(src)) if ext == ".MOL" else src
                if _put(index, slot + ext, data):
                    report["terrain"] += 1

            merged = merge_shell(donor_body, slot_body, slot_group)

            def rebase(m, _g=donor_group, _s=slot_group):
                v = int(m.group(2))
                return (m.group(1) + str((_s << 20) | (v & 0xFFFFF))
                        if (v >> 20) == _g else m.group(0))

            merged = re.subn(r'((?:Id|ID)\s*=\s*")(\d+)', rebase, merged)[0]
            merged = re.subn(r'(<\w*(?:Id|ID)>)(\d+)', rebase, merged)[0]
            merged = strip_body(add_support_zones(merged))
            merged = re.sub(
                r'File\s*=\s*"([^"]*\.atr)"',
                lambda m: ('File = "%s.atr"' % atr_slot[m.group(1).upper()[:-4]].lower())
                if m.group(1).upper()[:-4] in atr_slot else m.group(0),
                merged, flags=re.I)

            # The briefing screen's backdrop is shared artwork, and the two
            # discs spell it differently -- Ghost Recon ships brfg_map*.rsb,
            # Jungle Storm brfg-map.rsb and brfg-col.rsb. Carrying the donor's
            # spelling over leaves a name no JS archive holds, and a texture
            # the loader cannot find is the one failure that hangs it rather
            # than drawing nothing. Keep the slot's own.
            slot_brief = tag(slot_body, "BriefingImage")
            if slot_brief:
                merged = re.sub(r"<BriefingImage>[^<]*</BriefingImage>",
                                "<BriefingImage>%s</BriefingImage>" % slot_brief,
                                merged)

            env_name = basename_of(tag(merged, "Environment"))
            env_text = js_env.get(env_name[:-4], "")
            donor_env = donor["env"].get(
                basename_of(tag(donor_body, "Environment"))[:-4], "")
            if env_text and donor_env:
                for name in ("FarPlane", "MaxSpot", "CMBasePlanningLevel",
                             "CMOffsetX", "CMOffsetY"):
                    v = tag(donor_env, name)
                    if v is None:
                        continue
                    if re.search(r"<%s>[^<]*</%s>" % (name, name), env_text):
                        env_text = re.sub(r"<%s>[^<]*</%s>" % (name, name),
                                          "<%s>%s</%s>" % (name, v, name),
                                          env_text, count=1)
                    else:
                        env_text = env_text.replace(
                            "</EnvironmentFile>",
                            "\t<%s>%s</%s>\n</EnvironmentFile>" % (name, v, name))
                fog = re.search(r"<Fog[^>]*/>", donor_env)
                if fog:
                    env_text = re.sub(r"<Fog[^>]*/>", fog.group(0), env_text, count=1)
                # JungleMap is a Jungle Storm renderer flag; no GR level sets it
                env_text = re.sub(r"\s*<JungleMap>[^<]*</JungleMap>", "", env_text)
                _put(index, env_name, env_text.encode("latin-1"))

                # The slot's own <MapShots> is LEFT ALONE. It names a record
                # inside LOADING.PAK (c01_plantation_shots, 256x128 psm19), not
                # a loose file, so it resolves even though no <stem>_shots.rsb
                # exists on the disc. Repointing it at the command map puts the
                # top-down tactical map in the mission-preview pane.
                cm = tag(env_text, "CMBitmap") or ""
                if cm:
                    src = donor["rsb"].get(basename_of(tag(donor_env, "CMBitmap")))
                    if src is not None:
                        _put(index, basename_of(cm), src)

                gsky = basename_of(tag(donor_env, "SkyboxFileName"))
                jsky = basename_of(tag(env_text, "SkyboxFileName"))
                if gsky and jsky:
                    for part in SKY_PARTS:
                        src = donor["sky"].get(gsky[:-4] + part)
                        if src is not None and _put(index, jsky[:-4] + part, src):
                            report["skies"] += 1

            src = donor["pak"].get(mission + ".PAK") or donor["pak"].get(geo + ".PAK")
            if src is not None and _put(index, slot + ".PAK", src):
                report["paks"] += 1

            _put(index, slot + ".MIS", merged.encode("latin-1"))
            report["missions"] += 1

        say("Writing Ghost Recon's enemies")
        for gr_model, js_model in model_slot.items():
            for ext in MODEL_PARTS:
                src = donor["model"].get(gr_model, {}).get(ext)
                if src is not None and _put(index, js_model + ext, src):
                    report["models"] += 1
        # several templates can share a slot (identical once written), so write
        # each slot once rather than once per name that maps to it
        written_slots = set()
        for gr_t, js_t in sorted(atr_slot.items()):
            if js_t in written_slots:
                continue
            written_slots.add(js_t)
            text = donor["atr"][gr_t]
            m = re.search(r"<ModelName>([^<]*)</ModelName>", text)
            primary = slot_for(m.group(1).strip().upper().rsplit(".", 1)[0]) if m else None
            if primary:
                for name in MODEL_TAGS:
                    text = re.sub(r"<%s>[^<]*</%s>" % (name, name),
                                  "<%s>%s.chr</%s>" % (name, primary.lower(), name),
                                  text)
            if _put(index, js_t + ".ATR", text.encode("latin-1")):
                report["templates"] += 1

        say("Writing the Ghosts' own outfits")
        roster_models = set()
        for t, text in js_atr.items():
            if ROSTER.match(t):
                roster_models |= models_of(text)
        swapped = set()
        for target in sorted(m for m in roster_models if m.startswith("ICA_US_")):
            parts = donor["model"].get(GHOST_SUFFIX.sub("", target), {})
            if all(p in parts for p in MODEL_PARTS):
                for p in MODEL_PARTS:
                    if _put(index, target + p, parts[p]):
                        report["ghosts"] += 1
                swapped.add(target)
        # the roster's LOD2/LOD3 name Jungle Storm's _A/_B stubs, which Ghost
        # Recon has no equivalent for; alias them so distant Ghosts do not
        # revert to the Jungle Storm outfit
        for t, text in js_atr.items():
            m = re.search(r"<ModelName>([^<]*)</ModelName>", text)
            if not m or m.group(1).strip().upper().rsplit(".", 1)[0] not in swapped:
                continue
            primary = m.group(1).strip()
            new = text
            for name in ("LOD2", "LOD3"):
                new = re.sub(r"<%s>[^<]*</%s>" % (name, name),
                             "<%s>%s</%s>" % (name, primary, name), new)
            if new != text:
                _put(index, t + ".ATR", new.encode("latin-1"))

        say("Rebuilding the string tables")
        groups_for = {}
        for mission, _geo, slot in plan:
            sgroup = int(re.search(r"<MapNameId>(\d+)</MapNameId>",
                                   js_mis[slot]).group(1)) >> 20
            dgroup = int(re.search(r"<MapNameId>(\d+)</MapNameId>",
                                   donor["mis"][mission]).group(1)) >> 20
            groups_for[sgroup] = dgroup
        for arc in arcs:
            for key in list(arc.files):
                base = os.path.basename(key.upper().lstrip("/"))
                if not base.endswith("_STRINGS.RES") or base.split("_")[0] not in LANGS:
                    continue
                raw = arc.read_file(key)
                packed = rselzo.is_compressed(raw)
                groups = parse_res(plain(raw))
                for sgroup, dgroup in groups_for.items():
                    if donor["res"] and dgroup < len(donor["res"]) and sgroup < len(groups):
                        groups[sgroup] = list(donor["res"][dgroup])
                blob = build_res(groups)
                arc.write(key, rselzo.compress(blob) if packed else blob,
                          raw_size=len(blob))
        iso.flush()

    say("Turning the split-screen briefing off")
    report["briefing_words"] = clear_split_screen_briefing(out_path)

    # Jungle Storm's MP, Defend and co-op rows do not carry the campaign bit,
    # so a mission ported into one would never appear in Mission Co-op or over
    # LAN. The C and J campaign rows already have it.
    rows = mission_rows(out_path)
    want = [rows[s] for _m, _g, s in plan if s in rows]
    enabled, lanbits = enable_coop_slots(out_path, want)
    report["coop_rows"], report["lan_bits"] = enabled, lanbits
    if enabled:
        say("Mission Co-op enabled on %d slot(s)" % enabled)

    say("Pointing enemy speech at Ghost Recon's lines")
    report["enemy_voices"] = 1 if route_enemy_voices(out_path) else 0

    say("Restoring Ghost Recon's zoom hold and squad call-outs")
    report["feel_words"] = apply_feel(out_path)

    say("Porting Ghost Recon's mission pictures")
    report["thumbnails"] = port_thumbnails(out_path, gr_iso_path, plan, progress,
                                           js_iso_path=js_iso_path)

    say("Putting Ghost Recon's art on the menu screens")
    report["menu"] = port_menu(out_path, gr_iso_path, progress)

    if music:
        report["briefings"] = port_briefings(out_path, gr_iso_path, progress)

    say("Porting Ghost Recon's ambience")
    amb = port_ambience(out_path, gr_iso_path, js_iso_path, plan, progress)
    report.update(amb)

    say("Naming the ported missions in the mission table")
    report["table_names"] = sync_table_names(out_path, plan)

    say("Done")
    return report


#: mission table: VA, stride, and the two fields this needs
TABLE_VA = 0x0057C630
TABLE_STRIDE = 84
LAN_MASK_VA = 0x0057D090

#: the online map check (0x305550) never range-checks the map index, which a
#: memory-card profile restores as saved: a card that last saw a longer table
#: hands back row 31, whose "+0x4C" is a mask word that passes every type, and
#: Setup then searches the strings forever for its name. $a1 = 7*index here,
#: so `sltiu v1,a1,7*31` rejects it and the selector moves to a real row.
MAP_GUARD = {0x003056DC: (0x03E00008, 0x2CA300D9),   # jr ra -> sltiu v1,a1,0xd9
             0x003056E4: (0x00000000, 0x03E00008),   # -> jr ra
             0x003056E8: (0x00000000, 0x00431024)}   # -> and v0,v0,v1

#: VoxLists::GetWaveName, the branch that picks the enemy voice list.
#: addiu $s1,$v0,0xC78 (mITEnemyList) -> addiu $s1,$v0,0x990 (mEnemyList)
VOICE_VA = 0x00256D18
VOICE_OLD = 0x24510C78
VOICE_NEW = 0x24510990


def enable_coop_slots(out_path, rows):
    """Let these mission-table rows appear in split-screen Mission Co-op.

    `+0x48` is the split-screen game-type mask and bit 0 is the campaign /
    Mission Co-op type; the C and J campaign rows already carry it but the MP,
    Defend and co-op rows do not. A second word is the LAN/host allow-list,
    where a row is bit (30 - row).

    Returns (rows_enabled, lan_bits_set).
    """
    nrows = lanbits = 0
    with Iso(out_path, writable=True) as iso:
        ent = iso.find(JS_SERIAL)
        if ent is None:
            raise PortError("no %s on %s" % (JS_SERIAL, out_path))
        sectors = (ent.size + 2047) // 2048
        blob = bytearray(iso.read(ent.lba, sectors * 2048))
        base = TABLE_VA - 0x00100000 + 0x100
        for row in sorted(rows):
            off = base + row * TABLE_STRIDE + 0x48
            cur = struct.unpack_from("<I", blob, off)[0]
            if not (cur & 0x001):
                struct.pack_into("<I", blob, off, cur | 0x001)
                nrows += 1
        lan_off = LAN_MASK_VA - 0x00100000 + 0x100
        lan = struct.unpack_from("<I", blob, lan_off)[0]
        want = lan
        for row in rows:
            if 0 <= 30 - row < 32:
                want |= 1 << (30 - row)
        if want != lan:
            struct.pack_into("<I", blob, lan_off, want)
            lanbits = bin(want ^ lan).count("1")
        for va, (_old, new) in MAP_GUARD.items():
            struct.pack_into("<I", blob, va - 0x00100000 + 0x100, new)
        iso.write(ent.lba, bytes(blob))
        iso.flush()
    return nrows, lanbits


#: the two Ghost Recon behaviours that are pure ELF settings: the zoom that
#: holds instead of springing back, and the squad's contact / respawn call-outs
FEEL = ({"js_zoom_hold": True},
        {"js_callouts": True, "js_callouts_contact": True,
         "js_callouts_respawn": True},
        {"js_switch_teammate": True},
        {"js_anim_rate": "visible"})


def apply_feel(out_path):
    """Ghost Recon's zoom hold and squad call-outs, as ELF words.

    Returns the number of words this call changed; a word that already read
    the wanted value is not counted, so a second run reports 0.
    """
    from . import grzoomhold, grcallouts, grswitchteam, granimrate
    words = {}
    for mod, settings in zip((grzoomhold, grcallouts, grswitchteam,
                             granimrate), FEEL):
        for va, val, _size, _note in mod.js_edits(settings):
            words[va] = val & 0xFFFFFFFF
    changed = 0
    with Iso(out_path, writable=True) as iso:
        ent = iso.find(JS_SERIAL)
        if ent is None:
            raise PortError("no %s on %s" % (JS_SERIAL, out_path))
        sectors = (ent.size + 2047) // 2048
        blob = bytearray(iso.read(ent.lba, sectors * 2048))
        for va, val in words.items():
            off = va - 0x00100000 + 0x100
            if struct.unpack_from("<I", blob, off)[0] != val:
                struct.pack_into("<I", blob, off, val)
                changed += 1
        if changed:
            iso.write(ent.lba, bytes(blob))
            iso.flush()
    return changed

#: Ghost Recon's picture sheet is a 2x3 grid of 181x136 cells inside a 512x512
#: texture: five screenshots and, last, the top-down map. Jungle Storm's is two
#: 128x128 cells in a 256x128 texture, one screenshot and one map, and the menu
#: pans a window sized for THAT -- so dropping Ghost Recon's sheet in whole
#: leaves the first picture right and every later one straddling two cells.
#: The sheet has to be re-authored into Jungle Storm's own geometry.
GR_CELL = (181, 136)
GR_COLS = (2, 187)
GR_ROWS = (2, 142, 282)
GR_SHOT = (0, 0)                  #: col, row -- the first screenshot
GR_MAP = (1, 2)                   #: col, row -- the top-down map
#: Jungle Storm's CLUT is 127 on every entry; PS2 alpha runs 0..128
PS2_OPAQUE = 0x7F


def _reauthor_sheet(donor, template):
    """`template`'s record holding `donor`'s first screenshot and its map.

    Both halves are squashed into the slot's own cell size, which is what
    Jungle Storm does to its own 4:3 captures, and the result is quantised back
    to a 256-colour CLUT and re-encoded with the GIFtags the slot already had.
    """
    from PIL import Image
    from . import rsepak

    pal, idx = rsepak.unpack_psmt8(donor)
    whole = Image.new("RGB", (donor.width, donor.height))
    whole.putdata([pal[v][:3] for v in idx])
    cw, ch = template.width // 2, template.height

    def cell(col, row):
        x, y = GR_COLS[col], GR_ROWS[row]
        return whole.crop((x, y, x + GR_CELL[0], y + GR_CELL[1])) \
                    .resize((cw, ch), Image.LANCZOS)

    sheet = Image.new("RGB", (template.width, template.height))
    sheet.paste(cell(*GR_SHOT), (0, 0))
    sheet.paste(cell(*GR_MAP), (cw, 0))
    quant = sheet.quantize(colors=256, method=Image.MEDIANCUT,
                           dither=Image.FLOYDSTEINBERG)
    rgb = list(quant.getpalette() or [])
    rgb += [0] * (768 - len(rgb))
    palette = [(rgb[i * 3], rgb[i * 3 + 1], rgb[i * 3 + 2], PS2_OPAQUE)
               for i in range(256)]
    gif_clut, gif_pix = rsepak.gifs(template)
    segs = rsepak.pack_psmt8(gif_clut, gif_pix, palette, quant.tobytes())
    return rsepak.Record(template.kind, template.name, template.psm,
                         template.width, template.height, segs)


def _loading_pak(path, mission_stems):
    """({stem: picture record name}, LOADING.PAK bytes) off one disc."""
    shots, pak = {}, None
    with Iso(path) as iso:
        for arc in vokes.open_archives(iso):
            for key in list(arc.files):
                base = os.path.basename(key.upper().lstrip("/"))
                stem, ext = os.path.splitext(base)
                if ext == ".MIS" and stem in mission_stems and stem not in shots:
                    body = plain(arc.read_file(key)).decode("latin-1")
                    shots[stem] = os.path.splitext(
                        basename_of(tag(body, "MapShots") or ""))[0].lower()
                elif base == "LOADING.PAK" and pak is None:
                    pak = plain(arc.read_file(key))
    return shots, pak


def port_thumbnails(out_path, gr_iso_path, plan=None, progress=None,
                    js_iso_path=None):
    """Ghost Recon's mission pictures, in Jungle Storm's own picture sheets.

    The picture behind a mission in the map and co-op menus is a record in
    LOADING.PAK, and the mission's `<MapShots>` names it. That tag lives in the
    `<Shell>` block, which the port keeps from the SLOT -- so the menus still
    ask for `c01_plantation_shots` while the mission behind it is M01 Caves.

    Each slot therefore keeps its own record, its own name and its own 256x128
    geometry, and gets Ghost Recon's pictures painted into it. Returns the
    number of records rebuilt.
    """
    from . import discgrow, rsepak

    def say(m):
        if progress:
            progress(m)

    plan = list(PLAN) + list(DS_PLAN) if plan is None else list(plan)
    gr_shots, gr_pak = _loading_pak(gr_iso_path, {m for m, _g, _s in plan})
    if gr_pak is None:
        return 0
    donors = rsepak.index(rsepak.parse(gr_pak))

    # The templates are the SLOT's stock records: read them off the Jungle
    # Storm disc, not the disc being built, so a second run over a disc that
    # already carries ported pictures still starts from the right geometry.
    js_shots, js_pak = _loading_pak(js_iso_path or out_path,
                                    {s for _m, _g, s in plan})
    if js_pak is None:
        return 0
    templates = rsepak.index(rsepak.parse(js_pak))

    records = rsepak.parse(plain(_read_one(out_path, "LOADING.PAK")))
    where = {r.key.lower(): i for i, r in enumerate(records)}

    done = 0
    for mission, _geo, slot in plan:
        src = donors.get(gr_shots.get(mission, ""))
        key = js_shots.get(slot, "")
        tmpl = templates.get(key)
        i = where.get(key, -1)
        if src is None or tmpl is None or i < 0:
            continue
        if src.kind != 2 or src.psm != 19 or (src.width, src.height) != (512, 512):
            say("%s: %s is %s, not a 512x512 sheet -- left alone"
                % (slot, src.key, "kind %d psm %s" % (src.kind, src.psm)))
            continue
        records[i] = _reauthor_sheet(src, tmpl)
        done += 1
    if not done:
        return 0

    blob = rsepak.build(records)
    grew = len(blob) - len(js_pak)
    if grew > 0:
        say("Making room for %.1f MB of mission pictures" % (grew / 1048576.0))
        discgrow.grow_last_file(out_path, extra_bytes=grew + (8 << 20))
    with Iso(out_path, writable=True) as iso:
        index = {}
        for arc in vokes.open_archives(iso):
            for key in list(arc.files):
                index.setdefault(os.path.basename(key.upper().lstrip("/")), (arc, key))
        if not _put(index, "LOADING.PAK", blob):
            raise PortError("no LOADING.PAK on %s" % out_path)
        iso.flush()
    return done


def _read_one(iso_path, base_name):
    """One file out of a disc's archives, by base name."""
    with Iso(iso_path) as iso:
        for arc in vokes.open_archives(iso):
            for key in list(arc.files):
                if os.path.basename(key.upper().lstrip("/")) == base_name:
                    return arc.read_file(key)
    raise PortError("no %s on %s" % (base_name, iso_path))


#: the menus are data: IKE.RES is a list of screens, each widget carrying a
#: length-prefixed texture name. Both discs' MAIN widget is 0,0,640,480 and
#: only the texture differs -- Ghost Recon draws its photographic title plate,
#: Jungle Storm the same ringed backdrop it uses on every other screen.
MENU_BACKDROP = "SHELL_BGD_PS2.RSB"
MENU_TITLE = "MAIN_MENU_PS2.RSB"
#: Ghost Recon's title plate needs a name of its own, and this archive format
#: cannot grow its name table. MP03_RAILROAD.RSB is a stock command map that
#: nothing on the disc references -- every MP mission's environment points at a
#: tac0N map instead -- and its name is exactly as long as main_menu_ps2.rsb,
#: so the swap inside IKE.RES changes no lengths and needs no repack margin.
MENU_SPARE = "MP03_RAILROAD.RSB"
IKE_FILES = ("IKE.RES", "NTSC_IKE.RES")


def _ike_main_texture(blob: bytes, new_name: str):
    """IKE.RES with the MAIN screen's backdrop renamed. None if it is not there."""
    tok = struct.pack("<I", 4) + b"MAIN"
    at = blob.find(tok)
    if at < 0 or blob.find(tok, at + 1) >= 0:
        return None                      # absent, or ambiguous: do not guess
    old = (struct.pack("<I", len(MENU_BACKDROP))
           + MENU_BACKDROP.lower().encode("latin-1"))
    pos = blob.find(old, at, at + 128)
    if pos < 0:
        return None
    body = pos + 4
    return blob[:body] + new_name.lower().encode("latin-1") + blob[body + len(old) - 4:]


def port_menu(out_path, gr_iso_path, progress=None):
    """Ghost Recon's menu art, on Jungle Storm's screens.

    Three writes and no new file names: Ghost Recon's ringed backdrop goes into
    the backdrop every Jungle Storm screen already draws, its title plate goes
    into a command map nothing reads, and the MAIN screen is pointed at that
    name instead. Returns the number of files changed.
    """
    def say(m):
        if progress:
            progress(m)

    art = {}
    with Iso(gr_iso_path) as iso:
        for arc in vokes.open_archives(iso):
            for key in list(arc.files):
                base = os.path.basename(key.upper().lstrip("/"))
                if base in (MENU_BACKDROP, MENU_TITLE) and base not in art:
                    art[base] = arc.read_file(key)
    if MENU_BACKDROP not in art:
        return 0

    # Ghost Recon's plates are 1024x512 where Jungle Storm's are 640x480, so
    # both files grow and both have to be relocated into free space. Make that
    # space first: the allocator will not create it.
    extra = 0
    with Iso(out_path) as iso:
        for arc in vokes.open_archives(iso):
            for key in list(arc.files):
                base = os.path.basename(key.upper().lstrip("/"))
                src = {MENU_BACKDROP: MENU_BACKDROP, MENU_SPARE: MENU_TITLE}.get(base)
                if src in art:
                    extra += max(0, len(art[src]) - arc.files[key].size)
    if extra:
        from . import discgrow
        discgrow.grow_last_file(out_path, extra_bytes=extra + (4 << 20))

    done = 0
    with Iso(out_path, writable=True) as iso:
        index = {}
        for arc in vokes.open_archives(iso):
            for key in list(arc.files):
                index.setdefault(os.path.basename(key.upper().lstrip("/")), (arc, key))
        if _put(index, MENU_BACKDROP, art[MENU_BACKDROP]):
            done += 1
        if MENU_TITLE in art and _put(index, MENU_SPARE, art[MENU_TITLE]):
            done += 1
            for name in IKE_FILES:
                if name not in index:
                    continue
                arc, key = index[name]
                raw = arc.read_file(key)
                new = _ike_main_texture(plain(raw), MENU_SPARE)
                if new is None:
                    say("%s: no single MAIN screen to repoint, left alone" % name)
                    continue
                blob = rselzo.repack(raw, new) if rselzo.is_compressed(raw) else new
                arc.write(key, blob, raw_size=len(new))
                done += 1
        iso.flush()
    return done


def mission_rows(iso_path):
    """slot name -> mission-table row, read from the boot ELF."""
    rows = {}
    with Iso(iso_path) as iso:
        ent = iso.find(JS_SERIAL)
        if ent is None:
            raise PortError("no %s on %s" % (JS_SERIAL, iso_path))
        blob = iso.read(ent.lba, ((ent.size + 2047) // 2048) * 2048)
    base = TABLE_VA - 0x00100000 + 0x100
    for i in range(31):
        off = base + i * TABLE_STRIDE
        name = blob[off:off + 0x20].split(b"\x00")[0].decode("latin-1").upper()
        if name.endswith(".MIS"):
            rows[name[:-4]] = i
    return rows


def route_enemy_voices(out_path):
    """Make ported missions use Ghost Recon's enemy voice lines.

    `PS2LoadSoundData` raises an "IT" flag for level names beginning c/g/u, and
    `VoxLists::GetWaveName` then picks `mITEnemyList` -- Jungle Storm's own
    Colombian `ec1_` lines. Ghost Recon's missions live in exactly those slots.
    All of GR's enemy names are already on the JS disc and JS's `mEnemyList` is
    byte-identical to GR's, so no audio has to move: point the IT branch at
    `mEnemyList` instead. One word.

    True if it changed, False if it was already routed.
    """
    with Iso(out_path, writable=True) as iso:
        ent = iso.find(JS_SERIAL)
        off = VOICE_VA - 0x00100000 + 0x100
        sec, pos = off // 2048, off % 2048
        buf = bytearray(iso.read(ent.lba + sec, 2048))
        cur = struct.unpack_from("<I", buf, pos)[0]
        if cur == VOICE_NEW:
            return False
        if cur != VOICE_OLD:
            raise PortError("the enemy-voice site reads 0x%08X, expected 0x%08X"
                            % (cur, VOICE_OLD))
        struct.pack_into("<I", buf, pos, VOICE_NEW)
        iso.write(ent.lba + sec, bytes(buf))
        iso.flush()
    return True


#: Ghost Recon's music, and the two things everyone gets wrong about it.
#:
#: FIRST, IT IS NOT IN THE BANKS. Both discs ship a full score as raw,
#: 2048-aligned PS2 SPU ADPCM in two headerless streams inside `GR.IMG` --
#: `MUSIC.TM` (Ghost Recon 49.5 MB, Jungle Storm 114.6 MB) and `MENU.TM`
#: (40.4 MB on both). `EXPORT_PREPARE.CONFIG` says `compress ignore=*.tm` and
#: `align *.tm=2048`, so they are never LZO'd. The track table is `MUSIC.XML`
#: on Ghost Recon and `MUSIC.XBS` on Jungle Storm.
#:
#: SECOND, A MUSIC SOUND ID IS NOT A BANK INDEX. `RSMusicPS2::Play` resolves
#: the name through `n2iFindID` and hands the id to `sndSendMusicEvent`, an IOP
#: RPC; it never reads `BNK_00.SH`. The id's HIGH half selects the stream
#: (0 = MUSIC.TM, 1 = MENU.TM) and the low half is a track, so comparing the
#: low half against bank 0's entry count is meaningless -- and that comparison
#: is exactly what produced this module's old claim that "every music name
#: resolves past the end of its bank, so the stock disc plays none of them".
#: It does play them. Measured: `STEALTH1.WAV` is bank 0 index 82 in Jungle
#: Storm's own `.IDC` while bank 0 has 59 entries, and the track is real.
#:
#: Because it streams, music costs ZERO resident SPU budget. The 2 MB ceiling
#: that hung MP03_RAILROAD on the ambience pass cannot be reached this way.
#:
#: WHAT THE OLD CODE DID, AND WHY IT IS GONE. It substituted thirteen bank-0
#: samples BY INDEX, believing them to be `ACTION_*`, `DEATH*`, `AFTERACT_*`
#: and `CREDITS`. Not one of those indices is music on either disc, and the two
#: discs' bank 0 share not one index: index 2 is `C_BINOCULAR_AIM` on Ghost
#: Recon and `BREATH_INJURED_F3` on Jungle Storm; index 38 is
#: `TM1_KILLED_SELF1` and `TF1_WOUNDED_SELF1`. Running it put hurt voice lines
#: under the main-menu navigation blips, which is how it was caught -- in play,
#: by ear, not by any check in this file.

#: Jungle Storm's two 12-slot name tables, 16 bytes per slot, read by the
#: exploration-music picker. Six (track, loop) pairs each: `Exp1A` / `Exp1A_L`.
JS_EXPLORE_VA = 0x00596808
JS_DETECT_VA = 0x00596908
MUSIC_SLOT = 16
MUSIC_SLOTS = 12

#: The tracks Ghost Recon asks for and Jungle Storm does not. Both sets are in
#: Jungle Storm's `.IDC` (STEALTH1-9 at bank 0 indices 66..82, RECON_1-5 at
#: 56..64) and in its `MUSIC.TM`; what is missing is a name string to ask with.
#: Ghost Recon's ELF holds `stealth<N>.wav` at 0x00584C68 and `Recon_<N>.wav`
#: at 0x00584D38, indexed by `kStealthSound` (0x00560F60, 9 pointers) and
#: `kDetectionSound` (0x00560FA0, 5). Jungle Storm replaced both with the
#: `Exp*` / `ExpV*` tables above and shipped the tracks anyway.
GR_EXPLORE = tuple("STEALTH%d.WAV" % n for n in range(1, 10))
GR_DETECT = tuple("RECON_%d.WAV" % n for n in range(1, 6))


def _music_names(tracks):
    """`MUSIC_SLOTS` names for a 12-slot (track, loop) table.

    Ghost Recon's tracks have no `_L` loop variant -- there is no `STEALTH1_L`
    in either disc's name table -- so each pair gets the same track in both
    slots. Six pairs is all Jungle Storm's table holds, so STEALTH7-9 stay
    unreachable.
    """
    out = []
    for pair in range(MUSIC_SLOTS // 2):
        name = tracks[pair % len(tracks)]
        out += [name, name]
    return out


def port_music(out_path, progress=None):
    """Make Ghost Recon's exploration and detection music reachable.

    Nothing is copied: Jungle Storm's own `MUSIC.TM` already carries these
    tracks. The only edit is the two name tables in the boot ELF, so the picker
    asks for `STEALTH*` and `RECON_*` instead of `Exp*` and `ExpV*`. Every name
    is shorter than its 16-byte slot, so no length moves and no pointer is
    rewritten.

    This REPLACES Jungle Storm's own exploration music rather than adding to
    it -- there are only twelve slots. That is the right trade for a disc
    running Ghost Recon's campaign and the wrong one otherwise, which is why
    `port()` does not call this.

    NOT PLAY-TESTED. The names, the slots and their spare room are measured;
    that the picker plays what it finds there is not.

    Returns the number of slots written.
    """
    def say(m):
        if progress:
            progress(m)

    want = {}
    for va, tracks, what in ((JS_EXPLORE_VA, GR_EXPLORE, "exploration"),
                             (JS_DETECT_VA, GR_DETECT, "detection")):
        for i, name in enumerate(_music_names(tracks)):
            blob = name.encode("ascii")
            if len(blob) >= MUSIC_SLOT:
                raise PortError("%r does not fit a %d-byte slot with its "
                                "terminator" % (name, MUSIC_SLOT))
            want[va + i * MUSIC_SLOT] = blob.ljust(MUSIC_SLOT, bytes(1))
        say("%s music: %s" % (what, ", ".join(sorted(set(_music_names(tracks))))))

    done = 0
    with Iso(out_path, writable=True) as iso:
        ent = iso.find(JS_SERIAL)
        if ent is None:
            raise PortError("no %s on %s" % (JS_SERIAL, out_path))
        sectors = (ent.size + 2047) // 2048
        blob = bytearray(iso.read(ent.lba, sectors * 2048))
        for va, raw in sorted(want.items()):
            off = va - 0x00100000 + 0x100
            if blob[off:off + MUSIC_SLOT] != raw:
                blob[off:off + MUSIC_SLOT] = raw
                done += 1
        if done:
            iso.write(ent.lba, bytes(blob))
            iso.flush()
    return done


#: the one ported display name that reads as an abbreviation in the menus
RENAME = {"C03_HIGH_SIERRA": "M03 Railroad Bridge"}


def _sound_list(text):
    return re.search(r"<SoundList>(.*?)</SoundList>", text, re.S)


def sync_table_names(out_path, plan=None):
    """Put each ported mission's display name into its mission-table row.

    The port rewrites `<MapName>` in the `.MIS` and rebuilds the string tables,
    which is what the menus read -- but the row at TABLE_VA also carries a
    plain 32-byte name at `+0x20`, and nothing was writing it. Anything reading
    the table instead of the string table therefore still saw Jungle Storm's
    original ("C01 Watchful Yeoman" where the mission is now M01 Caves). The
    Discord presence does exactly that.

    Returns the number of rows changed.
    """
    plan = list(PLAN) + list(DS_PLAN) if plan is None else list(plan)
    want = {}
    with Iso(out_path) as iso:
        slots = {s for _m, _g, s in plan}
        for arc in vokes.open_archives(iso):
            for key in list(arc.files):
                b = os.path.basename(key.upper().lstrip("/"))
                stem, ext = os.path.splitext(b)
                if ext == ".MIS" and stem in slots and stem not in want:
                    body = plain(arc.read_file(key)).decode("latin-1", "replace")
                    m = re.search(r"<MapName>([^<]*)</MapName>", body)
                    if m:
                        want[stem] = m.group(1).strip()
    changed = 0
    with Iso(out_path, writable=True) as iso:
        ent = iso.find(JS_SERIAL)
        if ent is None:
            raise PortError("no %s on %s" % (JS_SERIAL, out_path))
        sectors = (ent.size + 2047) // 2048
        blob = bytearray(iso.read(ent.lba, sectors * 2048))
        base = TABLE_VA - 0x00100000 + 0x100
        for row in range(31):
            off = base + row * TABLE_STRIDE
            stem = os.path.splitext(
                blob[off:off + 0x20].split(b"\0")[0].decode("latin-1").upper())[0]
            name = want.get(stem)
            if name is None:
                continue
            field = name.encode("latin-1")[:0x1F] + b"\0"
            field += b"\0" * (0x20 - len(field))
            if blob[off + 0x20:off + 0x40] != field:
                blob[off + 0x20:off + 0x40] = field
                changed += 1
        if changed:
            iso.write(ent.lba, bytes(blob))
            iso.flush()
    return changed


def port_ambience(out_path, gr_iso_path, js_iso_path=None, plan=None,
                  progress=None):
    """Ghost Recon's ambience: its emitter placement and its recordings.

    Two halves, both keyed by NAME and never by index:

      * the EMITTERS. A mission's `<SoundList>` is the positioned wildlife bed
        -- 30 entries on a stock Jungle Storm level, 38 on Ghost Recon's M01.
        The port strips all of them, because a clip the level's bank cannot
        resolve hangs the load. Ghost Recon's go back in, keeping only the
        entries whose file the SLOT's own bank holds. They cost nothing: they
        are mission XML pointing at samples the bank already has.

      * the SAMPLES. Ghost Recon records the shared library at 16,000 Hz and
        Jungle Storm at 11,025 Hz, so the same sound is denser rather than
        longer. Dropping Ghost Recon's in whole grew every level bank by
        ~100 KB, and a level bank is RESIDENT -- it is uploaded into the PS2's
        SPU memory -- which hung the load on the biggest one. Decoding,
        resampling to the slot's own rate and re-encoding fits the real
        recording inside the budget the game shipped with.

    **The cap is each bank's OWN stock size.** Capping at the largest bank on
    the disc instead still grew all 28 and is what hung MP03_RAILROAD.

    Returns {"emitters", "samples", "resampled", "dropped", "banks"}.
    """
    from . import rseambience as amb, rsebank, rsevag, discgrow

    def say(m):
        if progress:
            progress(m)

    plan = list(PLAN) + list(DS_PLAN) if plan is None else list(plan)
    report = {"emitters": 0, "samples": 0, "resampled": 0, "dropped": 0, "banks": 0}

    def read(path, want_missions):
        out = {"mis": {}, "idc": {}, "counts": {}, "sh": {}, "sb": {}, "ss": {}}
        with Iso(path) as iso:
            for arc in vokes.open_archives(iso):
                for key in list(arc.files):
                    b = os.path.basename(key.upper().lstrip("/"))
                    s, e = os.path.splitext(b)
                    if e == ".MIS" and s in want_missions and s not in out["mis"]:
                        out["mis"][s] = plain(arc.read_file(key)).decode("latin-1", "replace")
                    elif e == ".IDC" and s not in out["idc"]:
                        out["idc"][s] = amb.idc_table(plain(arc.read_file(key)))
                    elif e == ".SH" and s not in out["sh"]:
                        p = plain(arc.read_file(key))
                        out["sh"][s] = p
                        bank, cnt = struct.unpack_from("<2I", p, 4)
                        out["counts"][bank] = cnt
                    elif e == ".SB" and s not in out["sb"]:
                        out["sb"][s] = plain(arc.read_file(key))
                    elif e == ".SS" and s not in out["ss"]:
                        out["ss"][s] = plain(arc.read_file(key))
        return out

    gr = read(gr_iso_path, {m for m, _g, _s in plan})
    js = read(js_iso_path or out_path, set())
    with Iso(out_path) as iso:
        cur = {}
        for arc in vokes.open_archives(iso):
            for key in list(arc.files):
                b = os.path.basename(key.upper().lstrip("/"))
                s, e = os.path.splitext(b)
                if e == ".MIS" and s in {x[2] for x in plan} and s not in cur:
                    cur[s] = plain(arc.read_file(key)).decode("latin-1", "replace")

    rebuilt, missions = {}, {}
    for mission, _geo, slot in plan:
        jb = amb.bank_of(slot, amb.JS_RULE)
        gb = amb.bank_of(mission, amb.GR_RULE)
        if jb is None or gb is None:
            continue
        jst, gst = "BNK_%02d" % jb, "BNK_%02d" % gb
        if jst not in js["sh"] or gst not in gr["sh"]:
            continue
        jn = amb.bank_names(js["idc"].get(jst, {}), js["counts"], jb)
        gn = amb.bank_names(gr["idc"].get(gst, {}), gr["counts"], gb)

        # -- emitters ---------------------------------------------------
        donor, kept, _dropped = amb.filter_sound_list(gr["mis"][mission], set(jn))
        block = _sound_list(donor)
        here = cur.get(slot)
        if block is not None and here is not None:
            mine = _sound_list(here)
            if mine is not None:
                missions[slot + ".MIS"] = (here[:mine.start(1)] + block.group(1)
                                           + here[mine.end(1):])
                report["emitters"] += kept

        # -- samples ----------------------------------------------------
        d = {"sh": js["sh"][jst], "sb": js["sb"].get(jst, b""),
             "ss": js["ss"].get(jst, b"")}
        g = {"sh": gr["sh"][gst], "sb": gr["sb"].get(gst, b""),
             "ss": gr["ss"].get(gst, b"")}
        bank, dents, dtail = rsebank.parse(d["sh"])
        _gbank, sents, _gtail = rsebank.parse(g["sh"])
        dlen = {"sb": len(d["sb"]), "ss": len(d["ss"])}
        slen = {"sb": len(g["sb"]), "ss": len(g["ss"])}
        stock = len(d["sb"])

        made, resampled = {}, 0
        for name in sorted(set(jn) & set(gn)):
            i, j = jn[name], gn[name]
            de, se = dents[i], sents[j]
            if not rsebank.is_live(de, dlen) or not rsebank.is_live(se, slen):
                continue
            if rsebank.pool_of(se) == "ss" and not d["ss"]:
                continue                  # a streamed donor with nowhere to go
            raw = g[rsebank.pool_of(se)][se[5]:se[5] + se[3]]
            if se[1] == de[1]:
                made[i] = (raw, se[1])
                continue
            pcm = rsevag.resample(rsevag.decode(raw), se[1], de[1])
            nb = (len(pcm) + rsevag.PER_BLOCK - 1) // rsevag.PER_BLOCK
            made[i] = (rsevag.encode(pcm, rsevag.stretch_flags(rsevag.flags(raw), nb)),
                       de[1])
            resampled += 1

        # measure, do not predict: drop the biggest growers until it fits
        while made:
            total = sum(len(made[i][0]) if i in made else e[3]
                        for i, e in enumerate(dents)
                        if rsebank.is_live(e, dlen) and rsebank.pool_of(e) == "sb")
            if total <= stock:
                break
            worst = max(made, key=lambda i: len(made[i][0]) - dents[i][3])
            if len(made[worst][0]) <= dents[worst][3]:
                break
            del made[worst]
            report["dropped"] += 1

        new, data = [list(e) for e in dents], {}
        for i, e in enumerate(dents):
            if rsebank.is_live(e, dlen):
                data[i] = d[rsebank.pool_of(e)][e[5]:e[5] + e[3]]
        for i, (blob, rate) in made.items():
            data[i] = blob
            new[i][3] = len(blob)
            new[i][1] = rate
        pools = {"sb": bytearray(), "ss": bytearray()}
        for pool in ("sb", "ss"):
            for _old, i in sorted((dents[i][5], i) for i in range(len(dents))
                                  if rsebank.is_live(dents[i], dlen)
                                  and rsebank.pool_of(dents[i]) == pool):
                new[i][5] = len(pools[pool])
                pools[pool] += data[i]
        sb, ss = bytes(pools["sb"]), bytes(pools["ss"])
        rebuilt[jst + ".SH"] = rsebank.build(bank, new, dtail, len(sb), len(ss))
        if jst in js["sb"]:
            rebuilt[jst + ".SB"] = sb
        if jst in js["ss"]:
            rebuilt[jst + ".SS"] = ss
        report["samples"] += len(made)
        report["resampled"] += resampled
        report["banks"] += 1
        say("%s: %d emitters, %d samples (%d resampled)" % (slot, kept, len(made), resampled))

    # -- the one display name that reads as an abbreviation ------------
    renamed = []
    for slot, new_name in RENAME.items():
        body = missions.get(slot + ".MIS", cur.get(slot))
        if body is None:
            continue
        m = re.search(r"<MapNameId>(\d+)</MapNameId>", body)
        if not m:
            continue
        missions[slot + ".MIS"] = re.sub(r"<MapName>[^<]*</MapName>",
                                         "<MapName>%s</MapName>" % new_name,
                                         body, count=1)
        renamed.append((int(m.group(1)) >> 20, int(m.group(1)) & 0xFFFFF, new_name))

    blobs = {k: v.encode("latin-1") for k, v in missions.items()}
    blobs.update(rebuilt)
    if not blobs:
        return report
    discgrow.grow_last_file(out_path, extra_bytes=sum(map(len, blobs.values())) + (16 << 20))
    with Iso(out_path, writable=True) as iso:
        index = {}
        for arc in vokes.open_archives(iso):
            for key in list(arc.files):
                index.setdefault(os.path.basename(key.upper().lstrip("/")), (arc, key))
        for name, blob in sorted(blobs.items()):
            _put(index, name, blob)
        for arc in vokes.open_archives(iso):
            for key in list(arc.files):
                b = os.path.basename(key.upper().lstrip("/"))
                if not b.endswith("_STRINGS.RES") or not renamed:
                    continue
                raw = arc.read_file(key)
                packed = rselzo.is_compressed(raw)
                groups = parse_res(plain(raw))
                hit = False
                for g, ix, new_name in renamed:
                    if g < len(groups) and ix < len(groups[g]):
                        groups[g][ix] = new_name.encode("latin-1")
                        hit = True
                if hit:
                    body = build_res(groups)
                    arc.write(key, rselzo.compress(body) if packed else body,
                              raw_size=len(body))
        iso.flush()
    return report


def port_briefings(out_path, gr_iso_path, progress=None):
    """Ghost Recon's briefing narration, in place of Jungle Storm's.

    `BNK_99_*` holds one streamed `<MISSION>_BRIEFING.WAV` per mission -- 28 on
    Ghost Recon, 21 on Jungle Storm -- and NOT the music, which lives in bank 0
    (see `port_music`). The `_0N` suffix is the language, so the six Ghost Recon
    banks are the same narration dubbed six ways and Jungle Storm has slots for
    five. Ghost Recon's banks are bigger, so the archive has to grow first.

    Returns the number of files written.
    """
    def say(m):
        if progress:
            progress(m)

    music = {}
    with Iso(gr_iso_path) as iso:
        for arc in vokes.open_archives(iso):
            for key in list(arc.files):
                base = os.path.basename(key.upper().lstrip("/"))
                if base.startswith("BNK_99") and base.endswith((".SH", ".SS")):
                    music[base] = arc.read_file(key)
    if not music:
        return 0
    extra = sum(len(v) for v in music.values())
    say("Making room for %.0f MB of music" % (extra / 1048576.0))
    from . import discgrow
    discgrow.grow_last_file(out_path, extra_bytes=max(64 << 20, extra))

    # the allocator will not verify a blank run over 16 MB and then treats it as
    # occupied; a music bank is up to 24 MB, so widen the check for this pass
    original = vokes.Vokes._is_blank
    vokes.Vokes._is_blank = (
        lambda self, o, n, budget=1 << 28: original(self, o, n, budget))
    written = 0
    try:
        with Iso(out_path, writable=True) as iso:
            index = {}
            for arc in vokes.open_archives(iso):
                for key in list(arc.files):
                    index.setdefault(os.path.basename(key.upper().lstrip("/")),
                                     (arc, key))
            for name, data in sorted(music.items()):
                if _put(index, name, data):
                    written += 1
            iso.flush()
    finally:
        vokes.Vokes._is_blank = original
    say("Music: %d of %d files (Jungle Storm has five language slots, "
        "Ghost Recon six)" % (written, len(music)))
    return written

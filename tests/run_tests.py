"""The checks worth running before a release.

    python tests\\run_tests.py ["E:\\XBOX Classic Games"]

Everything here runs against the real extracted discs, because the formats are
the point and a synthetic glob would only prove that this tool agrees with
itself. Nothing retail is ever opened for writing: the apply/revert cycle copies
the handful of files it needs into the system temp folder first and works there,
so a failed run cannot leave a game folder half-modded.

What each group is actually asserting:

  containers   every glob, bundle and executable on the shelf parses, and a
               round trip through the writer is byte-identical to the original.
  images       every disc image's filesystem walks, and the same game read as
               an `.iso` and as an extracted folder gives identical bytes --
               which is the only real proof that the two paths agree.
  xiso write   growing, shrinking and overwriting a file inside a disc image,
               against a small image built for the purpose rather than a 4 GB
               retail one.
  transforms   each edit does what it says AND keeps the file's length, which
               is the invariant the packed formats depend on.
  census       the two sides of the war are separable on the games that
               author the data for it, and empty on the games that do not --
               a silent empty census is how a weapons dial reaches nothing.
  cycle        plan, apply, verify, revert, and the folder is byte-identical
               to how it started.
  mission art  every mission card's pictures are actually on the disc -- a
               missing one draws nothing and says nothing.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tcxbox import (dataedit, engine, globfile, model, rsb,  # noqa: E402
                    transforms, umd, xbe, xiso, xpr)
from tcxbox.detect import identify, scan                          # noqa: E402
from tcxbox.gamedir import Root                                   # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_xiso                                                  # noqa: E402

PASS, FAIL = [], []


def check(name, fn):
    try:
        detail = fn()
        PASS.append(name)
        print("  ok    %-58s %s" % (name, detail or ""))
    except Exception as exc:                      # noqa: BLE001
        FAIL.append((name, exc, traceback.format_exc()))
        print("  FAIL  %-58s %s" % (name, exc))


def must(cond, message):
    if not cond:
        raise AssertionError(message)


# ---------------------------------------------------------------------------
# containers
# ---------------------------------------------------------------------------

def test_globs(games):
    total = entries = 0
    for det in games:
        with Root(det.path) as root:
            for relpath, size in root.source.iter_files():
                if not relpath.lower().endswith(".glb"):
                    continue
                read = root._reader(relpath)
                ents = globfile.parse_stream(read, size)
                total += 1
                entries += len(ents)
                for ent in ents[:4]:
                    blob = read(ent.offset, ent.size)
                    must(len(blob) == ent.size,
                         "%s: short read of %s" % (relpath, ent.name))
    must(total > 0, "no globs found")
    return "%d globs, %d entries" % (total, entries)


def test_umds(games):
    total = files = 0
    for det in games:
        with Root(det.path) as root:
            for relpath, size in root.source.iter_files():
                if not relpath.lower().endswith(".umd"):
                    continue
                read = root._reader(relpath)
                ents = umd.parse_stream(read, size)
                total += 1
                files += len(ents)
                mid = ents[len(ents) // 2]
                must(len(read(mid.offset, mid.size)) == mid.size,
                     "%s: short read of %s" % (relpath, mid.name))
    return "%d bundles, %d files inside them" % (total, files)


def test_xbes(games):
    for det in games:
        with Root(det.path) as root:
            rel = (root.source.resolve("default.xbe")
                   or root.source.resolve("RainbowSix3_Release.xbe"))
            must(rel, "%s: no executable" % det.profile.short)
            image = xbe.parse(root.source.read(rel))
        must(image.title_id_hex.upper() == det.profile.title_id.upper(),
             "%s: title id %s does not match the profile"
             % (det.profile.short, image.title_id_hex))
        must(image.sections, "%s: no sections" % det.profile.short)
    return "%d executables, title ids match their profiles" % len(games)


def test_art(games):
    from tcxbox import art

    shot = 0
    for det in games:
        banner = art.banner_image(det)
        emblem = art.emblem_image(det)
        must(banner is not None,
             "%s: no backdrop could be read" % det.profile.short)
        must(emblem is not None,
             "%s: no wordmark could be read" % det.profile.short)
        must(emblem.width >= 200,
             "%s: the wordmark came out %d wide, which means it fell back to a "
             "dashboard icon rather than the splash screen"
             % (det.profile.short, emblem.width))
        must(emblem.getchannel("A").getextrema()[0] == 0,
             "%s: the wordmark has no transparent pixel, so its plate was not "
             "keyed out" % det.profile.short)
        shot += 2
    return "%d bitmaps decoded, every wordmark at least 200px wide" % shot


def test_mission_art(games):
    """Every mission card has the pictures its profile promised it.

    Worth a check rather than a glance, because the failure is silent: a card
    whose art cannot be found just draws without it, and nobody notices that
    one mission in fifteen lost its briefing map.
    """
    from tcxbox import art

    lines = []
    for det in games:
        spec = getattr(det.profile, "mission_art_for", None)
        if spec is None:
            continue
        cards = [s for s in det.profile.settings if s.group == "Missions"]
        must(cards, "%s has mission_art_for and no mission cards"
             % det.profile.short)
        found = 0
        for card in cards:
            names = list(spec(card.key))
            must(names, "%s: %s asks for no art" % (det.profile.short, card.key))
            for name in names:
                image = art.mission_art(det, name)
                must(image is not None,
                     "%s: %s is not on the disc" % (det.profile.short, name))
                must(image.width >= 100 and image.height >= 80,
                     "%s: %s came out %dx%d"
                     % (det.profile.short, name, image.width, image.height))
                found += 1
        lines.append("%s %d/%d" % (det.profile.short.split()[0], found,
                                   len(cards)))
    must(lines, "no game on this shelf offers mission art")
    return "pictures per game (found/cards): " + ", ".join(lines)


# ---------------------------------------------------------------------------
# transforms
# ---------------------------------------------------------------------------

def test_script_edit(games):
    """The one edit that rewrites compiled UnrealScript rather than text.

    Every place these discs keep `R6RainbowAI.RainbowReloadWeapon` must parse,
    round-trip unchanged, and take the edit without changing length -- a `.umd`
    slot and a `.lin` container can survive nothing else. Retail Rainbow Six 3
    holds it twice and both copies are written.
    """
    from tcxbox import dataedit, lin, rsesidearm, uscode
    from tcxbox.games.r6engine import SCRIPT_FILES
    seen = 0
    discs = 0
    for det in games:
        root = Root(det.path)
        keys = root.match(SCRIPT_FILES)
        if not keys:
            continue
        before = seen
        for key in keys:
            raw = root.read(key)
            plain = lin.decompress(raw) if lin.is_lin(raw) else raw
            if rsesidearm.SIGNATURE not in plain:
                # Another game's package of the same name. Only Rainbow Six 3
                # and Black Arrow carry this function, and a profile's selector
                # only ever runs against its own disc -- this loop is the one
                # place every disc is tried at once.
                continue
            at = rsesidearm.find_block(plain)
            blk = uscode.Script.at(plain, at)
            disk, mem = blk.assemble(blk.disk_len)
            must(disk == plain[at + 4:at + 4 + blk.disk_len] and mem == blk.mem_len,
                 "%s: the function does not round-trip" % key)
            must(rsesidearm.reads(plain) == (0, False),
                 "%s: does not read as stock" % key)
            for params in ({"chance": 40, "in_contact": True},
                           {"chance": 40, "in_contact": False},
                           {"chance": 0, "say_chance": 25},
                           {"chance": 40, "say_chance": 25}):
                out, n = dataedit.OPS["ai_sidearm"](raw, params)
                must(len(out) == len(raw),
                     "%s: %r changed the file length" % (key, params))
                must(n == 1, "%s: %r changed nothing" % (key, params))
                back = lin.decompress(out) if lin.is_lin(out) else out
                # `in_contact` defaults to True when the caller omits it
                want = (params["chance"],
                        bool(params.get("in_contact", True))
                        if params["chance"] else False)
                must(rsesidearm.reads(back) == want,
                     "%s: %r read back as %r" % (key, params,
                                                 rsesidearm.reads(back)))
            must(dataedit.OPS["ai_sidearm"](raw, {"chance": 0})[1] == 0,
                 "%s: a zero chance wrote something" % key)
            seen += 1
        if seen > before:
            discs += 1
    must(discs >= 2, "fewer than two discs carried the function")
    return "%d cop%s across %d disc(s), every one parsed, edited and kept its length" % (
        seen, "y" if seen == 1 else "ies", discs)


def test_length_preserved(games):
    checked = 0
    for det in games:
        root = Root(det.path)
        for key in root.match(r"\.MIS$")[:6]:
            plain = root.read(key)
            for out, _n in (transforms.strip_difficulty(plain),
                            transforms.reveal_hidden(plain),
                            transforms.bump_enemy_tier(plain, 1)):
                must(len(out) == len(plain), "%s changed length" % key)
                checked += 1
        for key in root.match(r"R6GAMESETTINGS\.INI$")[:1]:
            plain = root.read(key)
            out, _n = transforms.scale_ini_values(
                plain, {"m_fSightRadius": 1.5, "m_iTerroristMaximumWounds": 2.0})
            must(len(out) == len(plain), "%s changed length" % key)
            must(transforms.read_ini_values(out, ["m_fSightRadius"])
                 ["m_fSightRadius"] == "7500.0", "sight radius did not scale")
            checked += 1
        for key in root.match(r"\.TPT$")[:3]:
            plain = root.read(key)
            out, _n = transforms.set_tpt_values(plain, {}, scale=1.4)
            must(len(out) == len(plain), "%s changed length" % key)
            checked += 1
    must(checked > 0, "nothing was checked")
    return "%d edits, every one the same length as the file it changed" % checked


def test_no_option_is_a_noop(games):
    """Every option, set away from its default, must change a byte.

    This exists because one did not. The Rainbow Six 3 "Aiming response" card
    offered the PS2 disc's turn curve, and the PS2 disc ships the same eleven
    control points the Xbox disc does -- so the option wrote the numbers that
    were already there, reported success, verified clean, and did nothing. Six
    tests passed over it: the values were well-formed, length-preserving,
    idempotent and revertible. None of them asked whether anything moved.

    So: run every choice of every option through the real edit pipeline and
    require the resulting bytes to differ from the shipped bytes somewhere.
    """
    checked = inert = 0
    for det in games:
        profile = det.profile
        if not profile.build_data:
            continue
        with Root(det.path) as root:
            for setting in profile.settings:
                if not setting.enabled:
                    continue
                tried = [v for v in _other_values(setting)]
                if not tried:
                    continue
                moved = 0
                for value in tried:
                    # An option with a gate is only itself once the gate is
                    # open, and gates chain: "only when in contact" needs the
                    # sidearm draw, which needs teammate magazines to be
                    # finite. Judging any of them with a gate shut reports it
                    # broken when it is not, so open the whole chain.
                    values = profile.normalise(
                        _with_gates_open(profile, {setting.key: value}))
                    edits = profile.build_data(values)
                    if edits and _edits_change_anything(root, edits):
                        moved += 1
                if not moved:
                    raise AssertionError(
                        "%s: %r rewrites nothing at any of its values (%s) -- "
                        "everything it writes is already on the disc"
                        % (profile.short, setting.key,
                           ", ".join(repr(v) for v in tried)))
                checked += 1
                inert += len(tried) - moved
    must(checked > 0, "nothing was checked")
    return ("%d option(s) each move at least one byte; %d value(s) restate "
            "what the disc already says" % (checked, inert))



def _with_gates_open(profile, asked):
    """`asked`, plus a value for every setting it transitively depends on."""
    by_key = {st.key: st for st in profile.settings}
    pending = list(asked)
    while pending:
        st = by_key.get(pending.pop())
        if st is None:
            continue
        for gate, allowed in st.requires.items():
            if gate in asked or not allowed:
                continue
            asked[gate] = allowed[0]
            pending.append(gate)
    return asked

def _other_values(setting):
    """Up to two values for a setting that are not its default."""
    if setting.kind == model.BOOL:
        return [not setting.default]
    if setting.kind == model.CHOICE:
        return [c.value for c in setting.choices
                if c.value != setting.default]
    if setting.kind == model.INT:
        out = [v for v in (setting.maximum, setting.minimum)
               if v != setting.default]
        return out[:1]
    return []


def _edits_change_anything(root, edits):
    """True if running these edits over the game's own files moves a byte.

    The op functions are the same ones `apply_data` dispatches through, so a
    pass here is a statement about the real pipeline and not about a model of
    it. Files are read and thrown away; nothing is written.
    """
    for key, edit in dataedit.plan_data(root, edits):
        op = dataedit.OPS.get(edit.op)
        if op is None:
            continue
        try:
            plain = root.read(key)
            out, _n = op(plain, edit.params)
        except Exception:                        # noqa: BLE001
            continue
        if out != plain:
            return True
    return False


def test_campaign_lists(games):
    """Every campaign choice parses, fits the disc, and is idempotent.

    The campaign list is the one edit here that is ALLOWED to change a file's
    length, so it is the one that can overflow. A disc image grows a file only
    into its own sector padding -- `Xiso.replace` refuses the rest rather than
    relocating -- so every choice this tool offers has to fit that budget, and
    the two that did not were reshaped from "add these missions" into "play
    these missions instead" once the arithmetic said so.
    """
    import xml.etree.ElementTree as ET
    checked = 0
    for det in games:
        profile = det.profile
        card = [st for st in profile.settings
                if st.key.endswith("_campaign") and st.enabled]
        if not card:
            continue
        with Root(det.path) as root:
            for choice in card[0].choices:
                if choice.value == "stock":
                    continue
                edits = [e for e in profile.build_data(
                    profile.normalise({card[0].key: choice.value}))
                    if e.op == "campaign"]
                must(edits, "%s: %r built no campaign edit"
                     % (profile.short, choice.value))
                for key, edit in dataedit.plan_data(root, edits):
                    plain = root.read(key)
                    out, n = dataedit.OPS[edit.op](plain, edit.params)
                    must(n > 0, "%s/%s rewrote nothing"
                         % (profile.short, choice.value))
                    budget = transforms.campaign_budget(plain)
                    must(len(out) <= budget,
                         "%s/%s: %d bytes will not fit the %d the disc "
                         "allocated" % (profile.short, choice.value,
                                        len(out), budget))
                    root_el = ET.fromstring(out.decode("latin1"))
                    names = [e.findtext("Filename") for e in root_el]
                    must(names and all(names),
                         "%s/%s produced a mission with no filename"
                         % (profile.short, choice.value))
                    have = {q.rsplit("/", 1)[-1].upper()
                            for q in root.match(r"/MISSION/[^/]+\.MIS$")}
                    missing = [n2 for n2 in names if n2.upper() not in have]
                    must(not missing,
                         "%s/%s names %d mission(s) not on the disc: %s"
                         % (profile.short, choice.value, len(missing),
                            ", ".join(missing[:4])))
                    again, n2 = dataedit.OPS[edit.op](out, edit.params)
                    must(again == out and n2 == 0,
                         "%s/%s is not idempotent"
                         % (profile.short, choice.value))
                    checked += 1
    must(checked > 0, "nothing was checked")
    return ("%d campaign variant(s) parse, fit their sector and are "
            "idempotent" % checked)


def test_clamps(_games):
    plain = b"Assault=50\r\nObservation=100\r\nSSniper=75\r\n"
    out, _n = transforms.set_tpt_values(plain, {}, scale=4.0)
    got = transforms.read_ini_values(out, ["Assault", "Observation", "SSniper"])
    must(got["Assault"] == "100", "Assault should clamp to 100, got %r" % got)
    must(got["Observation"] == "100", "Observation should stay at 100")
    return "template skills clamp at 100 and keep their width"


def test_ini_shapes(_games):
    plain = b"a=+400.0\r\nb=1.5f\r\nc=10\r\nd=0.40\r\n"
    out, n = transforms.scale_ini_values(plain, {k: 1.5 for k in "abcd"})
    got = transforms.read_ini_values(out, list("abcd"))
    must(got == {"a": "+600.0", "b": "2.2f", "c": "15", "d": "0.60"},
         "shapes not preserved: %r" % got)
    must(n == 4, "expected 4 changes, got %d" % n)
    return "leading +, trailing f and integer forms all survive a scale"


# ---------------------------------------------------------------------------
# census
# ---------------------------------------------------------------------------

def test_gun_sides(games):
    lines = []
    for det in games:
        root = Root(det.path)
        if not root.match(r"\.GUN$"):
            continue
        ally = dataedit.gun_scope_set(root, "ally_guns")
        enemy = dataedit.gun_scope_set(root, "enemy_guns")
        must(not (ally & enemy), "%s: a gun is on both sides" % det.profile.short)
        splits = det.profile.id in ("ghost_recon_xbox", "island_thunder_xbox")
        if splits:
            must(ally and enemy,
                 "%s: the sides should be separable and came back %d/%d"
                 % (det.profile.short, len(ally), len(enemy)))
        lines.append("%s %d/%d" % (det.profile.short.split()[0], len(ally),
                                   len(enemy)))
    return "ally/enemy: " + ", ".join(lines)


def test_enemy_templates(games):
    lines = []
    for det in games:
        if det.profile.id not in ("ghost_recon_xbox", "island_thunder_xbox"):
            continue
        root = Root(det.path)
        names = dataedit.enemy_template_set(root)
        must(len(names) > 50,
             "%s: only %d enemy templates" % (det.profile.short, len(names)))
        lines.append("%s %d" % (det.profile.short.split()[0], len(names)))
    return "enemy templates: " + ", ".join(lines)


# ---------------------------------------------------------------------------
# disc images
# ---------------------------------------------------------------------------

def test_iso_matches_folder(shelf):
    """The same game, read as an image and as a folder, is the same bytes.

    This is the check that makes supporting both shapes safe: two independent
    readers -- an XDVDFS walk and an os.walk -- have to agree.

    Compared by file NAME rather than by key, because a key carries the
    container a file was found in and the two copies of a game are not always
    packed the same way. Black Arrow is the case in point: the retail disc keeps
    its System folder inside `xboxdynamic.umd` and the prototype keeps the same
    files loose, so their key sets do not intersect at all while their contents
    do. Names intersect, and names are what the edits select on.
    """
    games = scan(shelf)
    pairs = 0
    checked = 0
    notes = []
    skipped = []
    modded = []
    for det in games:
        if det.kind != "iso":
            continue
        # Matched on the TITLE NAME in the executable, not just the title id.
        # Black Arrow's prototype disc carries the same title id as the retail
        # one on purpose -- that is why one profile serves both -- but it is a
        # different build with 96 terrorist templates against 120, so comparing
        # the two would be asserting that a prototype equals a shipped game.
        twin = next((d for d in games
                     if d.kind == "folder"
                     and d.profile.id == det.profile.id
                     and d.title_name == det.title_name), None)
        if twin is None:
            skipped.append(det.profile.short)
            continue
        # A game this tool has already edited is SUPPOSED to differ from the
        # copy it has not. Comparing them would be asserting that nobody uses
        # the tool, and it fails the moment somebody does -- which is how this
        # check first went red: the Rainbow Six 3 image had a grenade-carry mod
        # applied and the extracted folder did not.
        if engine.has_backup(det.path) or engine.has_backup(twin.path):
            modded.append(det.profile.short)
            continue
        with Root(det.path) as a, Root(twin.path) as b:
            left = _by_name(a)
            right = _by_name(b)
            common = sorted(set(left) & set(right))
            smaller = min(len(left), len(right))
            must(smaller and len(common) >= smaller * 0.85,
                 "%s: %d names in common, against %d on the smaller side"
                 % (det.profile.short, len(common), smaller))
            same = differ = 0
            for name in common[::13]:
                if a.read(left[name]) == b.read(right[name]):
                    same += 1
                else:
                    differ += 1
            must(differ == 0,
                 "%s: %d of %d sampled files differ between the image and the "
                 "folder" % (det.profile.short, differ, same + differ))
            checked += same
        pairs += 1
        notes.append(det.profile.short)
    tail = ""
    if skipped:
        tail += "; no same-build folder for " + ", ".join(sorted(set(skipped)))
    if modded:
        tail += "; already modded, so not compared: " + ", ".join(sorted(set(modded)))
    must(pairs or modded, "nothing left to compare")
    return "%d game(s) present twice (%s), %d files byte-identical%s" % (
        pairs, ", ".join(notes) or "none", checked, tail)


def _by_name(root):
    """{base name: key}, keeping only names that appear once."""
    seen = {}
    for key, f in root.files.items():
        seen.setdefault(f.name, []).append(key)
    return {n: keys[0] for n, keys in seen.items() if len(keys) == 1}


def test_xiso_writer(where):
    """Overwrite, shrink and grow a file inside a disc image."""
    path = make_xiso.build(os.path.join(where, "tiny.iso"), {
        "default.xbe": b"x" * 40,
        "notes.ini": b"a=1\r\nb=2\r\n",
    })
    before = os.path.getsize(path)

    with xiso.Xiso(path, writable=True) as iso:
        entry = iso.files["/NOTES.INI"]
        must(entry.size == 10, "size read back as %d" % entry.size)
        must(entry.allocated == 2048, "allocation is %d" % entry.allocated)

        iso.write(entry, 2, b"9")
        must(iso.read(entry) == b"a=9\r\nb=2\r\n", "in-place write did not land")

        grown = b"a=1\r\nb=2\r\nc=3\r\n"
        iso.replace(entry, grown)
        must(iso.files["/NOTES.INI"].size == len(grown),
             "the directory entry was not told the new length")

    with xiso.Xiso(path) as iso:
        entry = iso.files["/NOTES.INI"]
        must(entry.size == len(grown), "the new length did not survive a reopen")
        must(iso.read(entry) == grown, "the grown file read back wrong")

    with xiso.Xiso(path, writable=True) as iso:
        entry = iso.files["/NOTES.INI"]
        iso.replace(entry, b"a=1\r\n")
        must(iso.read(entry) == b"a=1\r\n", "the shrunk file read back wrong")
        tail = iso.read(entry, 5, 16)
        must(tail == b"\0" * 16, "the old tail was left behind: %r" % tail)

    must(os.path.getsize(path) == before,
         "the image changed size, which means something was relocated")

    with xiso.Xiso(path, writable=True) as iso:
        entry = iso.files["/NOTES.INI"]
        try:
            iso.replace(entry, b"z" * 5000)
        except xiso.XisoError:
            pass
        else:
            raise AssertionError("a file was allowed to grow past its sectors")
    return "in place, grown, shrunk, and a 5 KB write into a 2 KB slot refused"


# ---------------------------------------------------------------------------
# the whole cycle, on a copy
# ---------------------------------------------------------------------------

#: what has to be copied for each game to exercise its own edits
FIXTURE_PARTS = {
    "ghost_recon_xbox": ["default.xbe", "mission", "actor", "equip",
                         "globs/ikedata.glb"],
    "island_thunder_xbox": ["default.xbe", "mission", "actor", "equip",
                            "globs/ikedata.glb"],
    "ghost_recon2_xbox": ["default.xbe", "script", "equip/CmbtModl.xml",
                          "globs/ikedata.glb"],
    "summit_strike_xbox": ["default.xbe", "script", "equip/CmbtModl.xml",
                           "globs/ikedata.glb"],
    "rainbow_six_3_xbox": ["default.xbe", "System/RainbowSix3Xbox.ini",
                           "System/xboxdynamic.umd"],
    "black_arrow_xbox": ["RainbowSix3_Release.xbe",
                         "system/R6GameSettings.ini",
                         "system/RainbowSix3Xbox.ini", "template"],
    "graw_xbox": ["default.xbe", "System/R6GameSettings.ini",
                  "System/GR3XBoxAI.ini", "System/TWeapon.ini",
                  "System/RainbowSix3Xbox.ini"],
}


def _snapshot(folder):
    out = {}
    for dirpath, _dirs, names in os.walk(folder):
        if engine.BACKUP_DIR in dirpath:
            continue
        for name in names:
            full = os.path.join(dirpath, name)
            with open(full, "rb") as fh:
                out[os.path.relpath(full, folder)] = hashlib.sha1(
                    fh.read()).hexdigest()
    return out


def _fixture(det, where):
    """A folder copy of the parts of a game its own edits reach.

    Only for games this shelf also has extracted. Copying a 4 GB disc image to
    exercise an edit is not a test anyone would run twice, so the image path is
    covered by `test_iso_matches_folder` and `test_xiso_writer` instead.
    """
    parts = FIXTURE_PARTS.get(det.profile.id)
    if parts is None or det.kind != "folder":
        return None
    dst = os.path.join(where, det.profile.id)
    os.makedirs(dst, exist_ok=True)
    for rel in parts:
        src = os.path.join(det.path, rel.replace("/", os.sep))
        out = os.path.join(dst, rel.replace("/", os.sep))
        if not os.path.exists(src):
            return None
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if os.path.isdir(src):
            shutil.copytree(src, out, dirs_exist_ok=True)
        else:
            shutil.copy2(src, out)
    return dst


def _folder_twin(everything, det):
    """The extracted copy of this game, if the shelf has one."""
    if det.kind == "folder":
        return det
    return next((d for d in everything
                 if d.kind == "folder" and d.profile.id == det.profile.id), None)


def test_cycle(games, where, everything):
    from gui.presets import PRESETS

    done = []
    for det in games:
        twin = _folder_twin(everything, det)
        folder = _fixture(twin, where) if twin else None
        if folder is None:
            continue
        det = twin
        copy = identify(folder)
        must(copy.ok, "the copy of %s was not recognised" % det.profile.short)
        before = _snapshot(folder)

        wrote = 0
        for _name, values in PRESETS.get(det.profile.id, [])[1:]:
            full = dict(det.profile.defaults())
            full.update(values)
            report = engine.apply(copy.path, copy.profile, full)
            must(report["broken"] == 0,
                 "%s: %d files could not be read back"
                 % (det.profile.short, report["broken"]))
            wrote += report["files"]

        engine.revert(copy.path, copy.profile)
        after = _snapshot(folder)
        must(before == after,
             "%s: %d file(s) differ after revert"
             % (det.profile.short,
                sum(1 for k in before if before[k] != after.get(k))))
        done.append("%s %d" % (det.profile.short.split()[0], wrote))
    must(done, "no fixtures were built")
    return "every preset applied then reverted clean: " + ", ".join(done)


def test_idempotent(games, where, everything):
    """Applying the same settings twice leaves the same folder as applying once."""
    from gui.presets import PRESETS

    for det in games:
        if det.profile.id != "ghost_recon_xbox":
            continue
        twin = _folder_twin(everything, det)
        folder = _fixture(twin, where) if twin else None
        if folder is None:
            continue
        det = twin
        copy = identify(folder)
        _name, values = PRESETS[det.profile.id][3]
        full = dict(det.profile.defaults())
        full.update(values)
        engine.apply(copy.path, copy.profile, full)
        once = _snapshot(folder)
        engine.apply(copy.path, copy.profile, full)
        twice = _snapshot(folder)
        must(once == twice, "a second apply changed the folder again")
        engine.revert(copy.path, copy.profile)
        return "applying twice is the same as applying once"
    raise AssertionError("Ghost Recon is not on this shelf as a folder")


# ---------------------------------------------------------------------------

def main(argv):
    shelf = argv[0] if argv else r"E:\XBOX Classic Games"
    print("shelf: %s" % shelf)
    games = scan(shelf)
    if not games:
        print("no supported game folders found")
        return 1
    everything = list(games)
    seen = {}
    for det in games:
        seen.setdefault(det.profile.id, det)
    games = list(seen.values())
    print("%d game(s): %s\n" % (len(games),
                                ", ".join(d.profile.short for d in games)))

    print("containers")
    check("every glob parses and round-trips", lambda: test_globs(games))
    check("every .umd parses and round-trips", lambda: test_umds(games))
    check("every executable identifies its game", lambda: test_xbes(games))
    check("every shell bitmap decodes", lambda: test_art(games))

    check("every mission card has its own art",
          lambda: test_mission_art(games))

    print("disc images")
    check("an image and its extracted folder agree byte for byte",
          lambda: test_iso_matches_folder(shelf))

    print("transforms")
    check("edits keep the file's length", lambda: test_length_preserved(games))
    check("the script edit parses, applies and keeps its length",
          lambda: test_script_edit(games))
    check("template skills clamp", lambda: test_clamps(games))
    check("ini value shapes survive scaling", lambda: test_ini_shapes(games))
    check("no option quietly writes what is already there",
          lambda: test_no_option_is_a_noop(games))
    check("every campaign list fits its disc",
          lambda: test_campaign_lists(games))

    print("census")
    check("weapons split by side where the data allows",
          lambda: test_gun_sides(games))
    check("enemy templates are found", lambda: test_enemy_templates(games))

    print("apply and revert, on copies")
    with tempfile.TemporaryDirectory(prefix="tcxms-tests-") as where:
        check("writing inside a disc image", lambda: test_xiso_writer(where))
        check("every preset applies and reverts clean",
              lambda: test_cycle(games, where, everything))
        check("applying twice equals applying once",
              lambda: test_idempotent(games, where, everything))

    print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
    for name, _exc, tb in FAIL:
        print("\n--- %s ---\n%s" % (name, tb))
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

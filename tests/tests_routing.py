r"""The `[edits reach only the packages their budget is dead in]` section for
tests/run_tests.py.

Register it in `main()` alongside the other `run_*` calls:

        run_edit_routing(args)

It needs nothing new at the top of run_tests.py; every import is local.


WHY THIS SECTION EXISTS
-----------------------

Rainbow Six 3 ships three copies of its shared script, one per mode::

    COMMON.LIN      online              -- the *_MP_C / *_MP_S levels
    COMMONOFF.LIN   single player       -- <LEVEL>OFF.LIN
    COMMON_SS.LIN   split screen        -- <LEVEL>_SS.LIN

Campaign levels ship only the OFF and _SS variants -- there is no online copy
of a campaign map -- so COMMONOFF.LIN really is the single-player script.

COMMONOFF and COMMON_SS are BYTE-IDENTICAL once unpacked (5,094,061 bytes,
one sha1); only the online package is a different build. That is convenient --
a region recorded once is unique in both, so one signature pins a site in
either -- and it is also the trap. The two packages a region cannot tell apart
are exactly single player and split screen, an edit whose byte budget is DEAD
CODE in one is LIVE CODE in the other, and nothing in the bytes says which.
The routing is the only thing that knows.

`rseff`'s player-victim regions (`ff_player_victim`) are the case that got
through. They take their budget inside `R6PlayerController.PlaySoundDamage`
from its two `!m_bIsSplitScreen` call-out blocks -- dead in split screen,
which is the whole reason they were chosen, and live everywhere else. One of
them is single player's own "lead is down" line. Routed through
`rseff.SELECT` (`/COMMON(OFF|_SS)\.LIN$`) they were written into COMMONOFF
too, and a single-player teammate went silent when the player went down.
Reported from play, not caught here: the suite checked that every region was
equal-length, unique, idempotent, composable and reversible, and had nothing
at all to say about WHICH PACKAGE each one landed in.

So this section asks the question the others do not. The first half is
structural and needs no table -- it protects the call-out blocks by name and
lets any edit that reaches them fail, including one nobody has written yet.
The second half pins the routing of the edits whose intent is documented, so
changing one's mind has to be deliberate.
"""

import re
import sys as _sys

# -- from run_tests.py itself. run_tests.py runs as __main__, so a plain
#    `from run_tests import check` would load it a SECOND time with its own
#    empty PASS/FAIL lists and every result here would go into a copy nobody
#    prints -- a FAIL would not fail the suite. Bind to the running instance.
_rt = _sys.modules.get("__main__")
if _rt is not None and hasattr(_rt, "check"):
    check = _rt.check
else:                                                    # standalone import
    from run_tests import check                           # noqa: F401


#: the three shared packages, and the mode each one is the script for
MODE = {
    "/COMMON.LIN": "online",
    "/COMMONOFF.LIN": "single player",
    "/COMMON_SS.LIN": "split screen",
}
PACKAGES = tuple(MODE)

#: Which `rseff` variant exercises BOTH call-out blocks. Trigger levels 1-3
#: write `playerkill psd 1` and `psd 2`; 4 and 5 write only psd 1. The widest
#: one is used so the protected span covers everything the option can ever
#: reach, not only what today's default reaches.
WIDEST_PLAYERKILL = "playerkill:1:terrorists"

#: `VirtualFunction <ref> ByteConst 23` -- the call that speaks
#: `m_sndLeadDown`, measured in the stock offline package. Voice action 23 is
#: the "lead is down" line (see rsemandown). This is the thing being
#: protected, so the check names it rather than trusting a byte span alone.
LEAD_DOWN = bytes.fromhex("1b032417")

#: PlaySoundDamage's shipped bytecode length, as recorded in rseff's own note
#: ("block 0x10B465, 283 / 375" -- 283 on disk for the stock form it rewrites,
#: 375 declared). Pinned so a different pressing is a SKIP-worthy mismatch
#: rather than a silently misplaced span.
PSD_LEN = 375


def _lane(edit):
    """A routing lane: the unit whose target packages are a design decision.

    `friendly_fire` is several features behind one op name -- the AI-side dial,
    the nobody's-side masks, the mission-failure arms and the player-victim
    regions all arrive as `friendly_fire` edits and do NOT belong in the same
    packages. Everything else is one lane per op.
    """
    if edit.op != "friendly_fire":
        return edit.op
    which = str(edit.params.get("which", ""))
    for prefix in ("playerkill", "trigger", "noside", "fail_on"):
        if which.startswith(prefix):
            return "friendly_fire/" + prefix
    return "friendly_fire/" + (which or "?")


#: lane -> (the packages it may be written into, why not the others).
#:
#: Only lanes that reach a shared COMMON package are pinned; a lane that edits
#: levels or .INI files has nothing to decide. An unpinned lane is reported
#: rather than failed -- the structural half is what guards the bytes -- but a
#: lane named here has to say where it goes and why.
ROUTING = {
    "friendly_fire/playerkill": (
        {"/COMMON_SS.LIN"},
        "its budget is the two `!m_bIsSplitScreen` call-out blocks in "
        "R6PlayerController.PlaySoundDamage, which are live code offline -- "
        "one of them is single player's own \"lead is down\". There is no "
        "other player to shoot offline, so the regions buy nothing there "
        "either."),
    "friendly_fire/trigger": (
        {"/COMMONOFF.LIN", "/COMMON_SS.LIN"},
        "the squad turning on you is an offline and split-screen feature; "
        "the online package is left alone on purpose."),
    "friendly_fire/noside": (
        {"/COMMONOFF.LIN", "/COMMON_SS.LIN"},
        "it belongs to the dial, so it goes where the dial goes -- never "
        "online."),
    "friendly_fire/fail_on": (
        {"/COMMONOFF.LIN", "/COMMON_SS.LIN"},
        "it belongs to the dial, so it goes where the dial goes -- never "
        "online."),
    "split_down_callouts": (
        {"/COMMON_SS.LIN"},
        "it rewrites the split-screen branch of TeamMemberDead, which only "
        "the split-screen package has."),
    "canon_team": (
        {"/COMMON_SS.LIN"},
        "COMMON_SS.LIN IS the split-screen package; player 2 does not exist "
        "in the other two."),
}


def _psd_span(plain):
    """(lo, hi) of `R6PlayerController.PlaySoundDamage`'s bytecode."""
    import struct

    from tcps2 import rsemandown
    size_at = rsemandown.find_block(plain)
    declared = struct.unpack_from("<I", plain, size_at)[0]
    return size_at + 4, size_at + 4 + declared


def _protected(plain):
    """The call-out blocks inside PlaySoundDamage, as [(lo, hi, name)].

    Derived from `rseff`'s own recorded regions rather than from constants of
    its own, so the protection cannot drift away from what the edit writes.
    """
    from tcps2 import rseff
    lo, hi = _psd_span(plain)
    out = []
    names = [n for n, _s, _new in rseff._table(WIDEST_PLAYERKILL)]
    for name, site in zip(names, rseff._sites(plain, WIDEST_PLAYERKILL)):
        at, stock = site[0], site[1]
        if lo <= at < hi:
            out.append((at, at + len(stock), name))
    return sorted(out)


def _apply_matching(stock, package, values):
    """`stock` with every edit the profile routes at `package`, in apply order.

    Mirrors `dataedit.apply_data`: recording ops first, then the profile's own
    order, each op handed the bytes the one before it produced. Recording ops
    themselves are skipped -- they replace the whole file rather than patch
    script, and they are already covered by run_recording_first.
    """
    from tcps2 import dataedit
    from tcps2.games.r6_3 import PROFILE
    plain = stock
    edits = PROFILE.build_data(PROFILE.effective(values))
    edits = sorted(edits, key=lambda e: e.op not in dataedit._RECORDING_OPS)
    ran = []
    for e in edits:
        if e.op in dataedit._RECORDING_OPS:
            continue
        if not re.search(e.select, package, re.I):
            continue
        fn = dataedit.OPS[e.op]
        if e.op in dataedit._WANTS_CONTAINER:
            plain, _n = fn(plain, e.params, None)
        else:
            plain, _n = fn(plain, e.params)
        ran.append(_lane(e))
    return plain, ran


#: Every option that rewrites script in the shared packages, on at once. The
#: friendly-fire dial is at its widest -- level 1 reaches both call-out
#: blocks -- with the player-victim option on, because that is the lane that
#: went wrong. The rest is run_creation_order's "every script option" set.
FULL_ON = dict(
    split_squad=True, canon_team=True, split_muzzle=True, split_wheel=True,
    split_cycle=True, split_draw_once=True, split_wheel_labels=True,
    split_team_orders=True, split_hands=True, split_down_callouts=True,
    split_thunt_ai=True, fov=110, switch_rate=150,
    hostage_rainbow_voice=True, ai_finite_ammo=True, ai_sidearm=50,
    ai_say_dry=50, rpg_speed=2, grenade_carry=50, regroup_2nd=True,
    terro_down=True, rogue_tango=True, ff_retaliate=True,
    ff_player_victim=True, ff_trigger="1", ff_rogue_side="noside")


def run_edit_routing(args):
    """Which package each script edit is allowed to be written into."""
    print("\n[edits reach only the packages their budget is dead in]")
    if not args.rs3data:
        print("  SKIP  needs --rs3data")
        return
    from tcps2 import dataedit, engine, lin
    from tcps2.games.r6_3 import PROFILE

    store = dataedit.Store(engine.backup_dir_for(args.rs3data))
    stock = {}
    for pkg in PACKAGES:
        keys = [k for k in store.index if k.endswith(pkg)]
        if keys:
            stock[pkg] = lin.decompress(
                store.original(store.index[keys[0]]["archive"], pkg)[0])
    missing = [p for p in PACKAGES if p not in stock]
    if missing:
        print("  SKIP  no stored %s" % ", ".join(missing))
        return

    for k in FULL_ON:
        assert PROFILE.setting(k) is not None, k

    # Single player and split screen are the SAME script, which is what lets
    # one recorded region pin a site in both -- and is exactly why nothing in
    # the bytes can tell you which of the two you are editing.
    check("single player and split screen are byte-identical, so only the "
          "routing decides which of them an edit reaches",
          stock["/COMMONOFF.LIN"] == stock["/COMMON_SS.LIN"],
          "%d vs %d bytes" % (len(stock["/COMMONOFF.LIN"]),
                              len(stock["/COMMON_SS.LIN"])))
    check("and the online package is a different build, so it is not in that "
          "bargain", stock["/COMMON.LIN"] != stock["/COMMONOFF.LIN"])

    off = stock["/COMMONOFF.LIN"]

    # ---- the protected code, named and located -------------------------
    lo, hi = _psd_span(off)
    if hi - lo != PSD_LEN:
        print("  SKIP  PlaySoundDamage is %d bytes here, not the %d this "
              "section was measured on" % (hi - lo, PSD_LEN))
        return
    guarded = _protected(off)
    check("the player-victim option's budget is inside PlaySoundDamage: %s"
          % ", ".join(n for _a, _b, n in guarded) or "(none found)",
          len(guarded) == 2,
          "%d region(s) inside 0x%X..0x%X, expected 2"
          % (len(guarded), lo, hi))
    check("and one of those blocks is the \"lead is down\" call itself",
          sum(off[a:b].count(LEAD_DOWN) for a, b, _n in guarded) == 1,
          "VirtualFunction ByteConst 23 is not in the guarded spans, so they "
          "are not the blocks this section means to protect")
    check("which is unique in the function, so the span really is that line",
          off[lo:hi].count(LEAD_DOWN) == 1)

    # ---- the structural half: nothing may spend it offline --------------
    full = dict(PROFILE.defaults(), **FULL_ON)
    asked = PROFILE.effective(full)
    check("the value set really does ask for the player-victim option",
          asked.get("ff_player_victim") is True
          and asked.get("ff_retaliate") is True,
          "effective() dropped it, so the check below would pass vacuously: "
          "%r" % ({k: asked.get(k) for k in
                   ("split_squad", "ff_retaliate", "ff_player_victim")},))

    for pkg in PACKAGES:
        built, ran = _apply_matching(stock[pkg], pkg, full)
        check("%s (%s): %d lane(s) reach it and change it"
              % (pkg, MODE[pkg], len(set(ran))),
              bool(ran) and built != stock[pkg],
              "%d edit(s) ran, file %s"
              % (len(ran), "unchanged" if built == stock[pkg] else "changed"))
        kept = all(built[a:b] == off[a:b] for a, b, _n in guarded)
        if pkg == "/COMMON_SS.LIN":
            check("%s: the call-out blocks ARE spent here -- dead code in "
                  "split screen, and the option still lands" % pkg,
                  not kept,
                  "nothing wrote them, so ff_player_victim has silently "
                  "stopped reaching split screen")
            check("%s: so \"lead is down\" is gone from this one, by design "
                  "-- split_down_callouts speaks instead" % pkg,
                  built[lo:hi].count(LEAD_DOWN) == 0)
        else:
            spent = [n for a, b, n in guarded if built[a:b] != off[a:b]]
            check("%s (%s): the call-out blocks are LIVE code here and "
                  "nothing overwrote them" % (pkg, MODE[pkg]),
                  kept,
                  "overwritten: %s -- an edit took its byte budget from code "
                  "this mode actually runs" % ", ".join(spent))
            check("%s (%s): \"lead is down\" survives the whole option set"
                  % (pkg, MODE[pkg]),
                  built[lo:hi].count(LEAD_DOWN) == 1)

    # ---- the routing table ---------------------------------------------
    #
    # Two value sets, because the mission-failure arms and the retaliation
    # dial want the same region of the damage handler and `requires` keeps
    # them mutually exclusive -- one set can never emit both lanes.
    edits = []
    for extra in ({}, {"ff_fail_mission": True, "ff_fail_when": "hit"}):
        edits += PROFILE.build_data(
            PROFILE.effective(dict(full, **extra)))
    lanes = {}
    for e in edits:
        hit = frozenset(p for p in PACKAGES if re.search(e.select, p, re.I))
        if hit:
            lanes.setdefault(_lane(e), set()).add(hit)
    check("every lane routes consistently -- one set of packages per lane",
          all(len(v) == 1 for v in lanes.values()),
          str({k: [sorted(x) for x in v]
               for k, v in lanes.items() if len(v) != 1}))

    loose = {}
    for lane in sorted(lanes):
        got = set(next(iter(lanes[lane])))
        if lane not in ROUTING:
            loose.setdefault(
                tuple(sorted(MODE[p] for p in got)), []).append(lane)
            continue
        want, why = ROUTING[lane]
        check("%s -> %s" % (lane, ", ".join(sorted(MODE[p] for p in want))),
              got == want,
              "it reaches %s instead. %s"
              % (", ".join(sorted(MODE[p] for p in got)) or "nothing", why))
    # Not failures: these lanes have no documented package decision. Listed so
    # that giving one a rule is a small edit rather than a research task.
    for where, names in sorted(loose.items()):
        print("  ....  unpinned, reaching %s: %s"
              % (", ".join(where), " ".join(names)))

    stale = sorted(set(ROUTING) - set(lanes))
    check("every pinned lane is still emitted, so no rule here has gone "
          "stale", not stale,
          "pinned but never emitted, so the rule is unverified: %s"
          % ", ".join(stale))

    # ---- a typo in a `select` is silence, not an error ------------------
    from tcps2 import vokes
    from tcps2.iso import Iso
    with Iso(args.rs3data) as iso:
        keys = set()
        for arc in vokes.open_archives(iso):
            keys.update(arc.files)
    dead = sorted({e.op for e in edits if not any(e.matches(k) for k in keys)})
    check("every edit's select matches at least one file on the disc",
          not dead,
          "matches nothing, so it is silently inert: %s" % ", ".join(dead))


# ---------------------------------------------------------------------------
# every word a card writes has to be in the profile's STOCK map
# ---------------------------------------------------------------------------
#
# This is the check that makes a revised patch SAFE TO SHIP over an older one.
#
# `engine.load_pristine` recovers the shipped overlay three ways: from the
# backup container beside the disc, from the live image when it already hashes
# to `spec.image_sha1`, or -- when neither is available -- by writing every
# word in `profile.stock_words` and then DEMANDING that hash. That last arm is
# the one that matters here. An address a card writes but STOCK does not list
# cannot be put back by it, so the image stays patched, the hash misses, and
# the user is told their disc "has been changed by something other than this
# tool -- restore the disc from a clean copy" for damage this tool itself did.
# `stock_container` in run_tests.py refuses the ISO by the same route, so the
# suite would stop being able to read the disc it is meant to be testing.
#
# It bites hardest when a patch is REVISED. A new version that drops some of
# the old version's addresses has to keep emitting them -- at the shipped
# value, so they are no-ops on a clean disc -- or every disc carrying the old
# version becomes unrecoverable in exactly this way. `rsecarry` does that with
# its REPAIR tuple, and this check is what holds the next revision to it.
#
# The sweep sets each setting to every value it can take, with its
# requirements satisfied, and audits every word edit that comes back. The
# per-card attribution in a failure names whichever setting was being swept,
# which is a diagnostic hint rather than proof of ownership: the profile's
# default-on settings contribute their edits to every build.


def _sweep_values(s):
    """Every value this setting can be asked for."""
    if s.kind == "bool":
        return [True, False]
    if s.kind == "choice":
        return [c.value for c in s.choices]
    if s.kind == "int":
        return sorted({s.minimum, s.maximum, s.default})
    return [s.default]


def _satisfy(profile, values, key, seen=None):
    """Give `key` its requirements, so its edits are actually built."""
    seen = set() if seen is None else seen
    if key in seen:
        return
    seen.add(key)
    s = profile.setting(key)
    if s is None:
        return
    for dep_key, want in s.requires.items():
        if profile.setting(dep_key) is None:
            continue
        want = list(want) if isinstance(want, (list, tuple, set)) else [want]
        values[dep_key] = want[0]
        _satisfy(profile, values, dep_key, seen)


def _audit_stock_coverage(name, profile, stock):
    missing, raised = {}, []
    built = 0
    for s in profile.settings:
        for val in _sweep_values(s):
            values = profile.defaults()
            values[s.key] = val
            _satisfy(profile, values, s.key)
            try:
                edits = profile.build_edits(profile.effective(values))
            except Exception as exc:                      # noqa: BLE001
                raised.append("%s=%r -> %s: %s"
                              % (s.key, val, type(exc).__name__, exc))
                continue
            for e in edits:
                if not hasattr(e, "va") or getattr(e, "target", "main") != "main":
                    continue
                built += 1
                if e.va not in stock:
                    missing.setdefault(e.va, set()).add("%s=%r" % (s.key, val))

    # Today every one of these three profiles builds its disc words through a
    # local `w(va, value, note)` helper that reads `WordEdit(va, value,
    # STOCK[va], note)`, which has two consequences worth being plain about:
    #
    #   * a missing address raises KeyError inside build_edits, so it lands on
    #     the "no setting raises" check below rather than here. This one is a
    #     BACKSTOP, for a future builder that appends a WordEdit directly.
    #   * comparing `e.stock` against `STOCK[e.va]` could never fail, because
    #     the former IS the latter. A check for it was written, found to be
    #     vacuous by mutation testing, and removed rather than shipped as
    #     decoration. The honest version of that comparison needs an
    #     independent source for the shipped word: against the pristine image
    #     it is run_tests.py's own "every stock word in the profile matches
    #     the image", and against each module's own declaration it is
    #     `_audit_stock_declarations` below.
    #
    # `build_pnach` is deliberately NOT swept. Its rows are emulator cheat
    # lines that never touch the disc -- several pass a literal 0 as the stock
    # word -- so they need no STOCK entry and would fail this wrongly.
    check("%s: every address a card writes onto the disc is in STOCK, so "
          "load_pristine can put it back (%d word edits over %d settings, "
          "%d stock words)"
          % (name, built, len(profile.settings), len(stock)),
          not missing,
          "written but unrecoverable: %s"
          % "; ".join("0x%08X (while sweeping %s)"
                      % (va, ", ".join(sorted(missing[va])[:2]))
                      for va in sorted(missing)[:6]))
    check("%s: and no setting raises while building its edits, at any value "
          "it can take -- which is where a STOCK gap actually surfaces" % name,
          not raised, "; ".join(raised[:4]))


#: Every module that declares its own shipped words. The profile folds these
#: into STOCK with a sequence of `update()` and `STOCK[va] = ...` statements --
#: 46 of them in r6_3.py alone -- and a later one silently wins. That is the
#: one direction the sweep above cannot see: it reads `e.stock` straight out
#: of STOCK, so a clobbered value looks consistent to it while being wrong on
#: the disc. Asking each module what it declared is the independent source.
STOCK_DECLARERS = ("rseburstsnd", "rsecarry", "rseflashcost", "rsemirror",
                   "rsemolotov", "rsemsgpos", "rsepenetrate", "rsethirdperson")


def _audit_stock_declarations(stock):
    """Did a later STOCK.update quietly overwrite an earlier module's word?"""
    import importlib

    absent, clobbered = [], []
    declared = 0
    for name in STOCK_DECLARERS:
        mod = importlib.import_module("tcps2." + name)
        if not hasattr(mod, "stock_words"):
            absent.append("%s no longer declares stock_words()" % name)
            continue
        own = mod.stock_words()
        declared += len(own)
        for va, want in own.items():
            if va not in stock:
                absent.append("%s 0x%08X" % (name, va))
            elif stock[va] != want:
                clobbered.append("%s 0x%08X declares %08X, STOCK carries %08X"
                                 % (name, va, want, stock[va]))

    # The list above is written out rather than discovered, so that adding a
    # module does not silently widen what this check covers -- but a list
    # nobody maintains is worse than no list. Find the declarers in the source
    # instead of importing every module, and fail on a mismatch either way.
    import os
    import re as _re
    pkg = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "tcps2")
    found = set()
    for fn in sorted(os.listdir(pkg)):
        if not fn.endswith(".py"):
            continue
        with open(os.path.join(pkg, fn), encoding="utf-8") as fh:
            if _re.search(r"^def stock_words", fh.read(), _re.M):
                found.add(fn[:-3])
    check("the list of stock-word declarers is still the whole list (%d)"
          % len(found),
          found == set(STOCK_DECLARERS),
          "source declares %s; this check knows %s"
          % (sorted(found), sorted(STOCK_DECLARERS)))

    check("every word a module declares as shipped survives into the "
          "profile's STOCK (%d words from %d modules)"
          % (declared, len(STOCK_DECLARERS)),
          not absent, "not in STOCK: %s" % "; ".join(absent[:6]))
    check("and none of them was overwritten by a later STOCK update, which "
          "the sweep above cannot see because it reads the shipped word out "
          "of STOCK itself",
          not clobbered, "; ".join(clobbered[:4]))


def run_stock_coverage(args):
    """Can every word this tool writes be put back? Needs no disc."""
    print("\n[every word written can be put back]")
    from tcps2.games import ghost_recon, jungle_storm, r6_3

    for name, mod in (("Rainbow Six 3", r6_3),
                      ("Ghost Recon", ghost_recon),
                      ("Jungle Storm", jungle_storm)):
        _audit_stock_coverage(name, mod.PROFILE, mod.STOCK)

    _audit_stock_declarations(r6_3.STOCK)

    # The revision case, named for what it protects: a disc carrying the
    # FIRST version of the carry-over patch. That version wrote nine
    # addresses this one does not, and they are only recoverable because it
    # still emits them at the shipped value.
    from tcps2 import rsecarry
    sw = rsecarry.stock_words()
    core = {va for va, _s, _n, _note in rsecarry.WORDS}
    rep = {va: shipped for va, shipped, _note in rsecarry.REPAIR}
    check("the carry-over's repair words are addresses it no longer writes, "
          "so a disc carrying the first version is healed rather than left "
          "half-patched (%d repair, %d written)" % (len(rep), len(core)),
          rep and not (set(rep) & core),
          "also written, so not a repair: %s"
          % ", ".join("0x%08X" % va for va in sorted(set(rep) & core)))
    check("and stock_words() covers both sets, so a revert puts all %d back"
          % (len(core) + len(rep)),
          set(sw) == core | set(rep),
          "covers %d of %d" % (len(set(sw)), len(core | set(rep))))
    check("and the profile's STOCK carries every one of them",
          not (set(sw) - set(r6_3.STOCK)),
          "uncovered: %s" % ", ".join("0x%08X" % va
                                      for va in sorted(set(sw) - set(r6_3.STOCK))[:6]))

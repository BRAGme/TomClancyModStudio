"""Jungle Storm's controller layout for Ghost Recon (SLUS-20613).

Both games bind the pad the same way: RSInputImpl::MapForAction (GR
0x0054F3E0, JS 0x0019B280) gives each of the sixteen pad buttons a keycode,
one table per pad configuration in the Options screen, and
IkeInputMgr::MapInputForAction binds keycodes to game messages. The two
games share their keycodes, so Jungle Storm's layout is Jungle Storm's
keycode per button written into Ghost Recon's three tables -- 25
immediates. Configuration 1 (the default) becomes:

  * R2: quick order (Ghost Recon had it on R3);
  * R3: zoom, one click at a time, 1x -> 4x -> the weapon's most -> 1x, as
    Jungle Storm (Ghost Recon held R2 to zoom in and L2 to zoom out);
  * d-pad LEFT / RIGHT: peek left / right (Ghost Recon: next / previous
    soldier, with L3 as a peek modifier);
  * SELECT: next soldier, L2: previous soldier -- Jungle Storm uses these
    two for Quick Select and the headset's voice command, which Ghost Recon
    has not got, so they take over the soldier switching the d-pad gave up;
  * L3: nothing, as Jungle Storm. Its keycode is -0xC5 rather than -1 so
    that pad 2's copy (keycode + 0xC5 in split screen) is 0 as well: the
    input update skips any key <= 0, which also keeps Ghost Recon's L3 lean
    special case from ever running.

Configurations 2 and 3 take Jungle Storm's configurations 2 and 3 the same
way (2 swaps triangle / d-pad UP and cross / d-pad DOWN, 3 swaps R1 / cross
and R2 / R3).

The rest follows from that:

  * zoom: the zoom-in key's binding (key 0x59, pad 2's 0x11E) fires once per
    press instead of repeating while held (flags 0xA300 -> 0x2320 and
    0xE100 -> 0x6120, Jungle Storm's), and SimHuman::HandleAnalogZoom's
    zoom-in branch (0x003D7C08, 18 words) becomes Jungle Storm's click
    cycle. At the most zoom it takes the stock zoom-out path back to 1x,
    so the blur and binocular sound stop as they do when zooming out; every
    other step goes through the stock in-range path (blur, sound,
    ZoomToFOV). An unscoped weapon (most zoom 1x) never zooms;
  * the controller diagram in Options (captions tables at 0x00581670 and
    0x005816F0) names the new buttons -- 20 caption words;
  * sticks ("jungle_storm" only): Jungle Storm's right-stick dead zone, 25
    instead of Ghost Recon's 32, and its turn speed, half of Ghost Recon's
    (IkeUIMgr::ProcessMessage scales AvatarTurn by 0.5 at JS 0x0025CFD0;
    here three dead words of Ghost Recon's AvatarTurn case do it).

Split-screen orders (grsquad) bind their own keys; with this layout player
2's combat-ROE key moves from SELECT to L2 (grsquad.GR_JS_LAYOUT_KEYS) so
both players have SELECT = switch, R2 = Hold / Advance or move to, and L2 =
combat ROE.

Every stock word was checked against the retail executable. Not yet played.
"""

from __future__ import annotations

from .grasm import assemble

#: RSInputImpl::MapForAction: (va, stock, new, note) -- `addiu rt, zero, key`
BUTTONS = (
    (0x0054F4AC, 0x2405005A, 0x24050067, "config 1 L2: zoom out -> previous soldier"),
    (0x0054F4B4, 0x24040059, 0x24040081, "config 1 R2: zoom in -> quick order"),
    (0x0054F4EC, 0x24040071, 0x240400C3, "config 1 SELECT: next soldier"),
    (0x0054F4F4, 0x24040056, 0x2404FF3B, "config 1 L3: nothing, on both pads"),
    (0x0054F4FC, 0x24040081, 0x24040059, "config 1 R3: quick order -> zoom"),
    (0x0054F514, 0x24040067, 0x24040058, "config 1 d-pad RIGHT: peek right"),
    (0x0054F524, 0x240400C3, 0x24040056, "config 1 d-pad LEFT: peek left"),
    (0x0054F534, 0x2405005A, 0x24050067, "config 2 L2: zoom out -> previous soldier"),
    (0x0054F53C, 0x24040059, 0x24040081, "config 2 R2: zoom in -> quick order"),
    (0x0054F554, 0x24040074, 0x24040075, "config 2 triangle: key 0x75, as Jungle Storm"),
    (0x0054F564, 0x24040073, 0x2404006F, "config 2 cross: key 0x6f, as Jungle Storm"),
    (0x0054F574, 0x24040071, 0x240400C3, "config 2 SELECT: next soldier"),
    (0x0054F57C, 0x24040056, 0x2404FF3B, "config 2 L3: nothing, on both pads"),
    (0x0054F584, 0x24040081, 0x24040059, "config 2 R3: quick order -> zoom"),
    (0x0054F594, 0x24040075, 0x24040074, "config 2 d-pad UP: key 0x74, as Jungle Storm"),
    (0x0054F59C, 0x24040067, 0x24040058, "config 2 d-pad RIGHT: peek right"),
    (0x0054F5A4, 0x2404006F, 0x24040073, "config 2 d-pad DOWN: key 0x73, as Jungle Storm"),
    (0x0054F5AC, 0x240400C3, 0x24040056, "config 2 d-pad LEFT: peek left"),
    (0x0054F5BC, 0x2405005A, 0x24050067, "config 3 L2: zoom out -> previous soldier"),
    (0x0054F5D4, 0x24040072, 0x24040038, "config 3 R1: key 0x38, as Jungle Storm"),
    (0x0054F5EC, 0x24040038, 0x24040072, "config 3 cross: key 0x72, as Jungle Storm"),
    (0x0054F5FC, 0x24040071, 0x240400C3, "config 3 SELECT: next soldier"),
    (0x0054F604, 0x24040056, 0x2404FF3B, "config 3 L3: nothing, on both pads"),
    (0x0054F624, 0x24040067, 0x24040058, "config 3 d-pad RIGHT: peek right"),
    (0x0054F634, 0x240400C3, 0x24040056, "config 3 d-pad LEFT: peek left"),
)

#: IkeInputMgr::MapInputForAction: `ori a3, zero, flags` for the zoom-in key
ZOOM_FLAGS = (
    (0x00171208, 0x3407A300, 0x34072320, "zoom key fires once per press (pad 1)"),
    (0x00171460, 0x3407E100, 0x34076120, "zoom key fires once per press (pad 2)"),
)

#: SimHuman::HandleAnalogZoom, zoom-in branch
ZOOM_VA = 0x003D7C08
ZOOM_STOCK = (
    0x44820000, 0x00000000, 0x4600A803, 0x00000000, 0x4600A500, 0x4615A036,
    0x00000000, 0x45010037, 0x00000000, 0x12200021, 0x4600AD06, 0x8E6405A4,
    0x1080001E, 0x00000000, 0x926205B4, 0x10400007, 0x00000000, 0x8C990000,
)
# f20 = current zoom, f21 = the weapon's most zoom
ZOOM_SRC = """
    lui     at, 0x3c23              ; 0.00995
    mtc1    at, f2
    sub.s   f0, f21, f20
    c.lt.s  f0, f2                  ; at the most zoom (or an unscoped weapon)?
    lui     at, 0x3f80              ; 1.0
    bc1t    0x3d7a6c                ; -> stock zoom-out path, back to 1x
    mtc1    at, f1
    sub.s   f0, f20, f1
    c.lt.s  f0, f2                  ; at 1x?
    lui     at, 0x4080              ; 4.0
    bc1f    tomax                   ; zoomed in, not at the most -> the most
    mtc1    at, f3
    c.lt.s  f21, f3                 ; at 1x: does the weapon reach 4x?
    mov.s   f20, f3                 ; 4x
    bc1f    0x3d7d04                ; yes -> 4x through the stock in-range path
    nop
tomax:
    b       0x3d7d04                ; stock in-range path: blur, sound, ZoomToFOV
    mov.s   f20, f21                ; the most
"""
ZOOM_NEW = (    # what ZOOM_SRC assembles to (checked by selftest)
    0x3C013C23, 0x44811000, 0x4614A801, 0x46020034, 0x3C013F80, 0x4501FF93,
    0x44810800, 0x4601A001, 0x46020034, 0x3C014080, 0x45000005, 0x44811800,
    0x4603A834, 0x46001D06, 0x45000030, 0x00000000, 0x1000002E, 0x4600AD06,
)

#: PS2Options captains_left / captains_right: the Options controller diagram
LABELS = (
    (0x00581670, 0x0400006B, 0x04000076, "config 1 L2 caption"),
    (0x0058167C, 0x04000076, 0x0400007F, "config 1 d-pad LEFT/RIGHT caption: peek"),
    (0x00581690, 0x0400007F, 0x03900000, "config 1 L3 caption: none"),
    (0x005816F0, 0x0400006A, 0x0400008B, "config 1 R2 caption: quick order"),
    (0x00581714, 0x0400008B, 0x039002FD, "config 1 R3 caption: zoom"),
    (0x00581698, 0x0400006B, 0x04000076, "config 2 L2 caption"),
    (0x005816A0, 0x04000084, 0x04000079, "config 2 d-pad UP caption"),
    (0x005816A4, 0x04000076, 0x0400007F, "config 2 d-pad LEFT/RIGHT caption: peek"),
    (0x005816A8, 0x04000075, 0x0400007A, "config 2 d-pad DOWN caption"),
    (0x005816B8, 0x0400007F, 0x03900000, "config 2 L3 caption: none"),
    (0x00581718, 0x0400006A, 0x0400008B, "config 2 R2 caption: quick order"),
    (0x00581720, 0x04000079, 0x04000084, "config 2 triangle caption"),
    (0x0058172C, 0x0400007A, 0x04000075, "config 2 cross caption"),
    (0x0058173C, 0x0400008B, 0x039002FD, "config 2 R3 caption: zoom"),
    (0x005816C0, 0x0400006B, 0x04000076, "config 3 L2 caption"),
    (0x005816CC, 0x04000076, 0x0400007F, "config 3 d-pad LEFT/RIGHT caption: peek"),
    (0x005816E0, 0x0400007F, 0x03900000, "config 3 L3 caption: none"),
    (0x00581740, 0x0400006A, 0x039002FD, "config 3 R2 caption: zoom"),
    (0x00581744, 0x04000074, 0x04000071, "config 3 R1 caption"),
    (0x00581754, 0x04000071, 0x04000074, "config 3 cross caption"),
)

#: right stick: (va, stock, instruction, note)
STICKS = (
    (0x0054EA7C, 0x8EA40010, "addiu a0, zero, 0x19",
     "right stick X dead zone 25, as Jungle Storm (Ghost Recon: 32)"),
    (0x0054EB38, 0x8EA30010, "addiu v1, zero, 0x19",
     "right stick Y dead zone 25, as Jungle Storm"),
    (0x00272228, 0x0011203C, "lui v0, 0x3f00",
     "AvatarTurn: 0.5 (was a dead sign-extend)"),
    (0x0027222C, 0x0004203F, "mtc1 v0, f1",
     "AvatarTurn: (was a dead dsra32)"),
    (0x00272238, 0xC7A001F8, "mul.s f0, f0, f1",
     "AvatarTurn: turn at half speed, as Jungle Storm (was a repeated load)"),
)
STICKS_NEW = (0x24040019, 0x24030019, 0x3C023F00, 0x44820800, 0x46010002)

CHOICES = ("stock", "jungle_storm", "jungle_storm_buttons")

GR_STOCK = {va: s for va, s, _n, _t in BUTTONS + ZOOM_FLAGS + LABELS}
GR_STOCK.update({ZOOM_VA + 4 * i: s for i, s in enumerate(ZOOM_STOCK)})
GR_STOCK.update({va: s for va, s, _a, _t in STICKS})


def edits(layout: str):
    """(va, value, stock, note) for a layout in CHOICES."""
    if layout not in CHOICES:
        raise ValueError("unknown controller layout %r" % layout)
    if layout == "stock":
        return []
    out = [(va, n, s, "Jungle Storm controls: " + t)
           for va, s, n, t in BUTTONS + ZOOM_FLAGS + LABELS]
    words, _labels = assemble(ZOOM_SRC, ZOOM_VA)
    if len(words) != len(ZOOM_STOCK):
        raise ValueError("zoom cycle is %d words, the branch is %d"
                         % (len(words), len(ZOOM_STOCK)))
    out += [(ZOOM_VA + 4 * i, w, ZOOM_STOCK[i],
             "Jungle Storm controls: click zoom cycle") for i, w in enumerate(words)]
    if layout == "jungle_storm":
        for va, s, src, t in STICKS:
            out.append((va, assemble(src, va)[0][0], s, "Jungle Storm controls: " + t))
    return out


def gr_edits(v: dict):
    return edits(v.get("gr_controls", "stock"))


def selftest():
    """Assembled words match the recorded ones, no address twice, counts."""
    words, _ = assemble(ZOOM_SRC, ZOOM_VA)
    assert tuple(words) == ZOOM_NEW, ["%08X" % w for w in words]
    got = tuple(assemble(src, va)[0][0] for va, _s, src, _t in STICKS)
    assert got == STICKS_NEW, ["%08X" % w for w in got]
    for layout, n in (("stock", 0), ("jungle_storm_buttons", 65), ("jungle_storm", 70)):
        e = edits(layout)
        assert len(e) == n, (layout, len(e))
        assert len({va for va, *_ in e}) == n, layout
        assert all(GR_STOCK[va] == s for va, _w, s, _t in e), layout
    for va, s, n, _t in BUTTONS:     # only the immediate changes
        assert s >> 16 == n >> 16 and s >> 26 == 0x09, hex(va)
    return True


if __name__ == "__main__":
    print("grcontrols selftest", "OK" if selftest() else "FAIL")

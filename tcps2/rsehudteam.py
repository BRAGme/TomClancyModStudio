"""Split screen's team status panel: the AI teammates, in each player's half.

Single player draws the team panel -- the teammates' names, health and what
they are doing -- in `R6HUD.DrawNativeHUD`. Split screen never gets there: a
split-screen test at 0x003e7cbc sends it to a separate routine (0x003dbfd0)
that draws only the player's own box and returns. It is the same HUD class
and every asset the panel uses is already loaded in split screen (regions of
the one HUD atlas, the HUD's own blend material, Rainbow6_15pt, the localized
order strings), so nothing new is read and the level recordings stay in step.

What this does, as six one-word hooks and six caves in the dead path:

* H1 (the split-screen tail): if the HUD is switched on and the player has a
  pawn, switch the canvas to full-screen mode, set the full-screen nesting
  counter (0x0065460c) to a marker, 0x5A, and jump into single player's own
  HUD code at 0x003e81c0.
* H2: with the marker set, skip single player's player box -- split screen
  already draws its own -- and go straight to the team section.
* HS: build the panel's operative list from the team, skipping humans
  (`m_bIsPlayer`), sorted so slots do not swap when the AI re-sort
  themselves. The stock list is stale in split screen: the flag that
  refreshes it is set by nothing.
* H5: skip the status text's single-player-only remainder, go to the names.
* H9: flush, restore the counter, leave full-screen mode, and leave through
  the function's own tail, which frees the name strings.
* HQ (inside the shared 2D quad routine): only while the marker is set,
  shift each quad by +18 px across and by (this half's Y - 217) px down, so
  the panel sits in the right half at the right height.

Everything else sees the counter as it always was: each cave tests the
marker and otherwise runs exactly the instruction it replaced. Neither human
appears on either panel -- `m_Team[0]` is never searched, humans are skipped,
and with `split_squad` player 2 sits outside the counted range anyway -- so
both halves list the same AI, as a shared squad should.

Checked word by word against the stock overlay, and run in an interpreter
against a split-screen savestate with the AI in it (IDs [2, 3], count 3 for
both HUDs; single-player paths unchanged). Not yet watched in game.
"""

from __future__ import annotations

#: (va, stockWord, newWord, note) for the six hooks.
HOOKS = (
    (0x00349728, 0x46006E86, 0x0C066CC8,
     'FUN_003496d0: mov.s $f26,$f13 -> jal HQ'),
    (0x003E7CDC, 0x0C0D29B4, 0x08066CDB,
     'SS branch: jal 0x34a6d0 -> j H1 (delay li a1,-1 kept)'),
    (0x003E827C, 0x8F849908, 0x0C066CEF,
     'SP preamble exit: lw a0,-0x66f8(gp) -> jal H2'),
    (0x003E9654, 0x92820520, 0x0C066D13,
     'm_bUpdateOperativeID test: lbu v0,0x520(s4) -> jal HS'),
    (0x003EAF14, 0xAE82051C, 0x0C066CF7,
     'after team state: sw v0,0x51c(s4) -> jal H5'),
    (0x003EDEF4, 0x0C04ECE8, 0x0C066D01,
     'names exit: jal 0x13b3a0 -> jal H9'),
)

#: slot name -> (first dead-path word, words). Position-dependent: every
#: branch and jump inside was assembled for exactly these addresses.
CAVES = {
    'team_quad': (113, (
        0x8F818F1C,   # push depth
        0x3821005A,
        0x1420000E,   # not in the window -> plain
        0x46006E86,   # (delay) the displaced mov.s $f26,$f13
        0x3C01006C,
        0x8C2194BC,   # *(0x006b94bc): viewport Y saved by the push (0 / 224)
        0x44810000,
        0x3C014359,   # 217.0f
        0x44810800,
        0x46800020,
        0x46010001,   # dy = vpY - 217
        0x3C014190,   # 18.0f
        0x44810800,
        0x4600D680,   # y0 += dy
        0x46007BC0,   # y1 += dy (0x349730 copies $f15 to $f24)
        0x4601DEC0,   # x0 += 18
        0x4601CE40,   # x1 += 18 ($f25 was set in the hook's delay slot)
        0x03E00008,
        0x00000000,
    )),
    'team_entry': (132, (
        0x8F8298FC,   # R6GameOptions
        0x904200CD,
        0x30420020,   # HUD display option (same test as 0x3e8264)
        0x1040000C,   # off -> stock tail
        0x8E8203D8,   # (delay) HUD.PlayerOwner
        0x8C4203AC,   # .Pawn (FUN_003dbfd0 returns early when None)
        0x10400009,   # no pawn -> stock tail
        0x00000000,
        0x8FA42F04,   # canvas
        0x8C990000,
        0x8F390074,   # Canvas.PushFullScreenMode = 0x0029dfa0
        0x0320F809,
        0x00000000,
        0x2402005A,
        0x080FA070,   # -> SP locals preamble
        0xAF828F1C,   # (delay) push depth = window marker
        0x0C0D29B4,   # the displaced call: a0 = sp+0x1e0, a1 = -1 already set
        0x00000000,
        0x080FBE8D,   # stock: epilogue
        0x00000000,
    )),
    'team_skipbox': (152, (
        0x8F818F1C,   # full-screen push depth (0x0065460c)
        0x3821005A,   # == window marker?
        0x10200003,   # in the SS team window -> win
        0x00000000,
        0x03E00008,   # SP: back to 0x3e8284
        0x8F849908,   # (delay) the displaced lw a0, atlas
        0x080FA57D,   # window: skip the SP player box -> colour reset + team fetch
        0x00000000,
    )),
    'team_names': (160, (
        0x8F818F1C,   # full-screen push depth (0x0065460c)
        0x3821005A,   # == window marker?
        0x10200003,   # in the SS team window -> win
        0xAE82051C,   # (delay) the displaced sw (m_iMessageBoxPosY = 38)
        0x03E00008,   # SP: back to 0x3eaf1c
        0x00000000,
        0x8E8204B4,   # m_hudTextColor
        0x8FA32F04,   # canvas
        0x080FB566,   # window: -> names section
        0xAC62006C,   # (delay) Canvas.DrawColor = text colour
    )),
    'team_exit': (170, (
        0x8F818F1C,   # full-screen push depth (0x0065460c)
        0x3821005A,   # == window marker?
        0x10200003,   # in the SS team window -> win
        0x00000000,
        0x0804ECE8,   # SP: the displaced call (ra = 0x3edefc)
        0x00000000,
        0x27A401E0,
        0x0C0D2948,   # flush the HUD batch
        0x00000000,
        0x24020001,
        0xAF828F1C,   # push depth back to 1 so the pop restores the viewport
        0x8FA42F04,   # canvas
        0x8C990000,
        0x8F390078,   # Canvas.PopFullScreenMode
        0x0320F809,
        0x00000000,
        0x080FBE4D,   # flush, free the three name FStrings, end ctx, epilogue
        0x00000000,
    )),
    'team_roster': (188, (
        0x8F818F1C,   # full-screen push depth (0x0065460c)
        0x3821005A,   # == window marker?
        0x10200003,   # in the SS team window -> win
        0x92820520,   # (delay) the displaced lbu
        0x03E00008,   # SP: back to 0x3e965c
        0x30420001,   # (delay) redo the andi
        0x8FA80110,   # team
        0x0000482D,   # mask of AI operative IDs
        0x2405000C,   # 4*j, j = 3,2,1
        0x01051021,
        0x8C4203C0,   # m_Team[j]
        0x10400008,
        0x24A5FFFC,   # (delay) j--
        0x904303BE,   # R6Pawn.m_bIsPlayer = bit 0 of byte +0x3be
        0x30630001,
        0x14600004,   # human -> skip
        0x8C43094C,   # (delay) m_iOperativeID
        0x24020001,
        0x00621004,
        0x01224825,
        0x1CA0FFF4,   # bgtz a1, L1
        0x00000000,
        0x24100001,   # count = the viewer
        0x26860484,   # &m_iOperativeID[0]
        0x0000202D,   # id = 0
        0x00891006,
        0x30420001,
        0x10400004,
        0x00000000,
        0xACC40000,   # m_iOperativeID[k] = id
        0x24C60004,
        0x26100001,
        0x24840001,
        0x28820004,
        0x1440FFF6,
        0x00000000,
        0x080FA5D8,   # count test with s0 = 1 + #AI
        0x00000000,
    )),
}


class TeamPanelError(Exception):
    pass


def words(freed=True):
    """[(va, word, stockWord, note)] for the whole panel fix."""
    from . import rsedeadpath

    out = []
    for slot, (first, body) in CAVES.items():
        base = rsedeadpath.claim(slot, freed)
        if base != rsedeadpath.CAVE + 4 * first:
            raise TeamPanelError("%s moved: the caves were assembled for "
                                 "fixed addresses" % slot)
        for k, word in enumerate(body):
            va = base + 4 * k
            out.append((va, word, rsedeadpath.stock(va),
                        "split screen team panel: %s" % slot))
    for va, stock, new, note in HOOKS:
        out.append((va, new, stock, "split screen team panel: " + note))
    return out


HELP = ("Single player lists your teammates along the bottom of the screen -- "
        "their names, health and what they are doing. Split screen never "
        "draws it. This draws it in each player's half, listing the AI "
        "teammates only: the other player has his own box.")

CAUTION = ("Watched working on 2026-09-22 on Alpine Village: both halves "
           "show Loiselle and Weber with their health and status, and the "
           "status follows orders (MOVING, then FOLLOWING). It reuses single "
           "player's own panel code, so it looks exactly like single "
           "player's, and every texture and font it draws was already "
           "loaded -- nothing new is read. It runs through the game's shared "
           "2D drawing routine while the panel draws, so if any HUD element "
           "appears shifted or missing in split screen, turn this off first. "
           "Needs AI teammates in split screen, which fill it.")


def card(prefix, group):
    from .model import BOOL, Setting

    return Setting(
        prefix + "split_team_panel", "Team status in split screen",
        BOOL, False, group, confidence="verified", touches="words",
        requires={prefix + "split_squad": [True]},
        help=HELP, caution=CAUTION)

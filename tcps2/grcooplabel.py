"""Online co-op with AI backup: label your own AI squadmates as friends (Jungle Storm, SLUS-20820).

What was wrong
--------------

Online, the HUD names whatever the reticle is on and tints the reticle to match. The code is in the
HUD's per-frame routine 0x002383E0 (label block 0x002392D0..0x002395C8). It sorts the target by its
player link, SimHuman+0x750 (vt+0x5A0):

* a human (link set) -- compare companies (vt+0x344 -> +0x178) with your own soldier: same company is
  the soldier's name in green, a different one red;
* anyone else (link 0) -- the name string (+0x700) is tested for the prefixes "Civilian", "Hostage"
  and "Friendly" (grey); everything else is taken for an enemy: **red**, the name looked up for a
  translation, and when there is none the text becomes token 0x039004BD, "enemy soldier".

Stock online co-op has no AI on the players' side, so "no player link" always meant an enemy. The AI
backup fill (roster writer 0x00377180 filling each fireteam) adds AI squadmates called "Rifleman",
"Demolition" and "Support", in the players' company (1), with no player link. They fall through to
the enemy branch: red reticle, red "enemy soldier", blinking like an enemy -- on both consoles, for
every one of the six fill soldiers. Aiming at the other human is right on both consoles ("BRAGme2" /
"BRAGme", green). The report "the host labels the joiner enemy soldier" was the joiner's own fireteam
Rifleman standing next to him: the host's RAM, saved with that label up, holds id 0x82 in the label's
last-target word 0x00577FF8, and id 0x82 is Alpha's Rifleman (0/0/1).

It is only the label. The label's colour lives in a register (s2) of 0x002383E0; the words it writes
are the HUD's own (the last-target word 0x00577FF8, the blink state 0x00578000 / 0x00627490 /
0x00627498, the reticle tint) and nothing inside any soldier. Nothing that decides who is a friend
reads any of them: SimHuman::ApplyDamage (0x003B4F70) looks at no side at all, so friendly fire is
the same either way; kill scoring (0x003B3410) calls a kill "same side" by company and platoon; the
reticle only hooks onto targets whose HumanMotion+0xB7 enemy flag is set. The fill soldiers have
company 1 and that flag clear, the same as the two humans.

The fix
-------

In the enemy branch, ask one more question before calling the target an enemy: is it in the local
soldier's company? If so, take the branch the Civilian/Hostage/Friendly names take (name = its
translation, which for these kit names is the name itself) but keep the colour at 0 -- the green the
human teammates get. Enemies, civilians, hostages, "Friendly ..." units and human players are handled
exactly as before.

In place, no cave::

    0x002393E8  addiu s2, zero, 1  ->  nop
        The Civilian/Hostage/Friendly exit sets s2 = 1 in a delay slot, but all three entries already
        arrive with s2 == 1 (the prefix test 0x00402210 returns exactly 1 on a match, stored by
        `andi s2, v0, 0xff`). Leaving s2 alone lets the new entry keep s2 == 0.

    0x002393F4..0x00239440  the enemy branch, rewritten in the same twenty words:
        lw    v0, 0x178(s1)          ; target's company   (vt+0x344 of a SimHuman is just this load)
        beqz  s7, notsame            ; no local soldier -> exactly the stock path
        addiu a1, sp, 0x260
        lw    v1, 0x178(s7)          ; local soldier's company (s7 is set before the branch at 0x239304)
        beq   v0, v1, 0x2393DC       ; same company -> named, s2 stays 0 (green)
        nop
    notsame:
        jal   0x401C10               ; ...stock from here: name == its translation?
        addiu s2, zero, 2
        beqz  v0, 0x239444           ; no -> name = translation (stock ELSE, unchanged)
        addiu a0, sp, 0x268
        jal   0x4016D0               ; yes -> destroy the name ...
        addiu a1, zero, -1
        jal   0x126640
        lui   a2, 0x390
        move  a1, v0
        addiu a0, sp, 0x268
        jal   0x40A4E0               ; ... and build "enemy soldier" in its place
        ori   a2, a2, 0x4BD
        b     0x239450               ; stock: store the id for the blink, drop the translation
        lw    a0, 0(s0)

    Stock built "enemy soldier" in a temporary (sp+0x218), assigned it to the name and destroyed the
    temporary; destroying the name and constructing the token into it ends in the same state (the old
    string loses one reference, the token string gains one) in four fewer words, which is the room the
    company test needed. For an enemy the patched block leaves RAM byte-for-byte as stock does.
    0x00239444 onwards (the ELSE and the shared tail the Civilian path jumps to at 0x0023946C) is not
    touched.

Why the direct +0x178 load is safe: the label block already calls vt+0x584 and vt+0x5A0 on the target,
and in the whole executable only SimHuman's vtable (0x005B56D0) holds those two functions and vt+0x344's
0x003A76B0, whose body is `j 0x360400` -> `lw v0, 0x178(a0)`.

Verified by running the label block (0x002392D0..0x002395C8) in an interpreter over both consoles'
RAM from the AI-backup co-op game (J03, disc 9C04BFE8), stock and patched, with the target forced to
every friendly soldier, an enemy, and soldiers of both companies renamed "Civilian ..."/"Hostage ..."/
"Friendly ...": the six fill soldiers go from red "enemy soldier" to green kit names on both consoles;
humans, enemies and the renamed ones give the same colour, text and RAM as stock; so does every
non-player target with no local soldier (s7 = 0). Played 2026-09-29 (disc 914547E3): teammates green.

The kill feed
-------------

The same mistake prints "an enemy soldier has killed an enemy soldier" in red when a fill soldier
kills an enemy. The feed is made in two steps, both in IkeRulesMgr (0x00D25FA0):

* **A** -- the handler of 0x22F {victim id, killer id} (0x0014BD80), sent by SimHuman's death code
  (0x003B3410 / 0x003B4430). It returns at once unless this console is the host (vt+0x48(1); run on
  the joiner's RAM it sends nothing), then decides the line and sends 0x2A6 to every console
  (0x00125810): {colour, killer is a player, killer name, rank, verb token, has victim, victim is a
  player, victim name, rank}. A killer is "a player" unless his game object answers vt+0xF8 or his
  soldier has no player record (vt+0xC -> vt+0x15C == 0); a victim unless vt+0xF8. Players get their
  name and rank; an AI gets his raw name (+0x700, "Rifleman") with the flag clear. The colour starts
  from companies and teams (different company 0, same company 4, same team 1 = team kill /
  suicide), and a player killer who is not a team killer becomes 2 outside team games. An AI killer
  whose name has no translation and is not Civilian/Hostage/Friendly takes the branch at 0x0014C3F0,
  which forces the colour to 0; the victim's twin is 0x0014C738. Both branches also build "an enemy
  soldier" into a local string that is never read again (0x0014C40C/0x0014C754: only the destructor
  at the end touches sp+0x1E8/sp+0x1E0).
* **B** -- the handler of 0x2A6 (0x0014B650), on every console. A name whose "is a player" flag is
  clear goes through the same test (translation? Civilian/Hostage/Friendly?) and otherwise becomes
  token 0x03900523 "an enemy soldier" (0x0014B8B0 killer, 0x0014BB74 victim); players' names are
  kept, with " (rank)" when the rank is above 0. The line goes to the HUD as 0x24D with the colour,
  whose handler (0x00237250) paints 0 red, 1 yellow, 2 green, 3 blue, 4 white.

So a fill soldier is named "an enemy soldier" by B because A cleared his flag, and coloured red by A.
The fix is in A only, in its two dead "an enemy soldier" branches, rewritten in place::

    0x0014C3F0..0x0014C424  (killer; 14 of the 15 words)
        lw/lw/jalr/move      killer's SimHuman (the game object's vt+0xC, SimHuman + 0x1B0)
        lui/lw  t0           the players' company, SimHuman's static 0x0057A1C8 (the "player's
                             squad" company SimHuman vt+0x568 tests; set when the squad is built)
        lw    t1, -0x38(v0)  his company, SimHuman +0x178
        bne   t0, t1, enemy
        daddiu s1, zero, 1   same company: "is a player" (A's s1 is the flag it sends) ...
        b     0x14C47C
        move  s6, zero       ... and coloured as one (s6 = AI killer; clear, the colour code
                             below treats him like a player: green, or yellow for a team kill)
    enemy:
        move  s1, zero       otherwise exactly stock: flag clear,
        b     0x14C47C
        move  s3, zero       colour 0
    0x0014C738..0x0014C760  (victim; 11 of the 15 words)
        the same company test on the victim (A's s4); same company: sb 1 -> sp+0xD0, the "victim
        is a player" flag A sends; either way on to 0x0014C7C4 as stock.

B then keeps the kit name ("Rifleman", "Demolition", "Support"; rank 0, so no suffix). The sent
names were already the raw names, so nothing else changes. The rest of each block (the dead
string code) is left as it was, after an unconditional branch. Only the host runs A, so the fixed
lines reach the joiner too even if only the host's disc has this.

Verified in the RAM interpreter (scratchpad agent_orders/killfix.py, killfix2.py, killfix3.py): A
and then B run on the host's kill-feed save (killlog_host.bin, disc 914547E3) for 13 killer/victim
pairs, stock and patched: fill soldier kills enemy -- red "an enemy soldier has killed an enemy
soldier" becomes green "Rifleman has killed an enemy soldier"; enemy kills fill soldier -- red "an
enemy soldier has killed Rifleman"; fill soldier team kill / suicide -- yellow, named, like a
player's; every line with a human killer or victim, and enemy on enemy, identical to stock. Same
results on the earlier host saves; the joiner (both saves) builds nothing in A and prints the
host's patched line unchanged through B.
"""

from __future__ import annotations

from .grasm import assemble
from .model import BOOL, Setting

#: the enemy branch of the label block, rewritten in place
BRANCH = 0x002393F4
BRANCH_END = 0x00239444          # the stock ELSE starts here and is kept
#: `addiu s2, zero, 1` in the Civilian/Hostage/Friendly exit
EXIT_S2 = 0x002393E8

SYMS = dict(NAMED=0x002393DC, StrEq=0x00401C10, StrDtor=0x004016D0, LocTable=0x00126640,
            TokenStr=0x0040A4E0, ELSE=0x00239444, IDSTORE=0x00239450)

SRC = """
        lw    v0, 0x178(s1)          ; target's company
        beqz  s7, notsame            ; no local soldier: stock behaviour
        addiu a1, sp, 0x260
        lw    v1, 0x178(s7)          ; local soldier's company
        beq   v0, v1, NAMED          ; same company: named, s2 stays 0 (green)
        nop
notsame:
        jal   StrEq                  ; stock from here: name == its translation?
        addiu s2, zero, 2
        beqz  v0, ELSE               ; no: name = translation (stock ELSE)
        addiu a0, sp, 0x268
        jal   StrDtor                ; yes: destroy the name ...
        addiu a1, zero, -1
        jal   LocTable
        lui   a2, 0x390
        move  a1, v0
        addiu a0, sp, 0x268
        jal   TokenStr               ; ... and build "enemy soldier" in its place
        ori   a2, a2, 0x4bd
        b     IDSTORE
        lw    a0, 0(s0)
"""

#: the kill feed (IkeRulesMgr's 0x22F handler 0x0014BD80, host only): its two dead
#: "an enemy soldier" branches, for the killer and for the victim, rewritten in place
KILLER_AT, KILLER_END = 0x0014C3F0, 0x0014C42C   # entered only from 0x0014C38C
VICTIM_AT, VICTIM_END = 0x0014C738, 0x0014C774   # entered only from 0x0014C6D4
KSYMS = dict(PCOMPANY=0x0057A1C8,                # SimHuman static: the players' company
             KILLER_DONE=0x0014C47C, VICTIM_DONE=0x0014C7C4)

KILLER_SRC = """
        lw    t9, 0(s2)
        lw    t9, 0xc(t9)            ; the killer's SimHuman + 0x1B0
        jalr  t9
        move  a0, s2
        lui   at, %hi(PCOMPANY)
        lw    t0, %lo(PCOMPANY)(at)  ; the players' company
        lw    t1, -0x38(v0)          ; his company (SimHuman +0x178)
        bne   t0, t1, k_enemy
        daddiu s1, zero, 1           ; (both ways) sent as a player ...
        b     KILLER_DONE
        move  s6, zero               ; ... and coloured as one
k_enemy:
        move  s1, zero               ; stock: an AI,
        b     KILLER_DONE
        move  s3, zero               ; coloured 0 (red)
"""

VICTIM_SRC = """
        lw    t9, 0(s4)
        lw    t9, 0xc(t9)            ; the victim's SimHuman + 0x1B0
        jalr  t9
        move  a0, s4
        lui   at, %hi(PCOMPANY)
        lw    t0, %lo(PCOMPANY)(at)
        lw    t1, -0x38(v0)
        bne   t0, t1, VICTIM_DONE    ; an enemy: stock
        li    t2, 1
        b     VICTIM_DONE
        sb    t2, 0xd0(sp)           ; ours: sent as a player
"""

#: stock words of every word this module may write (read from SLUS_208.20)
JS_STOCK = {
    0x0014C3F0: 0x0C049990,   # jal   0x126640
    0x0014C3F4: 0x0000982D,   # move  s3, zero
    0x0014C3F8: 0x0040282D,   # move  a1, v0
    0x0014C3FC: 0x27A40188,   # addiu a0, sp, 0x188
    0x0014C400: 0x3C020390,   # lui   v0, 0x390
    0x0014C404: 0x0C102938,   # jal   0x40a4e0
    0x0014C408: 0x34460523,   # ori   a2, v0, 0x523   ("an enemy soldier")
    0x0014C40C: 0x27A401E8,   # addiu a0, sp, 0x1e8
    0x0014C410: 0x0C1005F8,   # jal   0x4017e0
    0x0014C414: 0x27A50188,   # addiu a1, sp, 0x188
    0x0014C418: 0x27A40188,   # addiu a0, sp, 0x188
    0x0014C41C: 0x0C1005B4,   # jal   0x4016d0
    0x0014C420: 0x2405FFFF,   # addiu a1, zero, -1
    0x0014C424: 0x10000015,   # b     0x14c47c
    0x0014C428: 0x00000000,   # nop
    0x0014C738: 0x0C049990,   # jal   0x126640
    0x0014C73C: 0x00000000,   # nop
    0x0014C740: 0x0040282D,   # move  a1, v0
    0x0014C744: 0x27A40120,   # addiu a0, sp, 0x120
    0x0014C748: 0x3C020390,   # lui   v0, 0x390
    0x0014C74C: 0x0C102938,   # jal   0x40a4e0
    0x0014C750: 0x34460523,   # ori   a2, v0, 0x523   ("an enemy soldier")
    0x0014C754: 0x27A401E0,   # addiu a0, sp, 0x1e0
    0x0014C758: 0x0C1005F8,   # jal   0x4017e0
    0x0014C75C: 0x27A50120,   # addiu a1, sp, 0x120
    0x0014C760: 0x27A40120,   # addiu a0, sp, 0x120
    0x0014C764: 0x0C1005B4,   # jal   0x4016d0
    0x0014C768: 0x2405FFFF,   # addiu a1, zero, -1
    0x0014C76C: 0x10000015,   # b     0x14c7c4
    0x0014C770: 0x00000000,   # nop
    0x002393E8: 0x24120001,   # addiu s2, zero, 1
    0x002393F4: 0x27A50260,   # addiu a1, sp, 0x260
    0x002393F8: 0x0C100704,   # jal   0x401c10
    0x002393FC: 0x24120002,   # addiu s2, zero, 2
    0x00239400: 0x10400010,   # beqz  v0, 0x239444
    0x00239404: 0x27A40268,   # addiu a0, sp, 0x268
    0x00239408: 0x0C049990,   # jal   0x126640
    0x0023940C: 0x00000000,   # nop
    0x00239410: 0x0040282D,   # move  a1, v0
    0x00239414: 0x27A40218,   # addiu a0, sp, 0x218
    0x00239418: 0x3C020390,   # lui   v0, 0x390
    0x0023941C: 0x0C102938,   # jal   0x40a4e0
    0x00239420: 0x344604BD,   # ori   a2, v0, 0x4bd
    0x00239424: 0x27A40268,   # addiu a0, sp, 0x268
    0x00239428: 0x0C1005F8,   # jal   0x4017e0
    0x0023942C: 0x27A50218,   # addiu a1, sp, 0x218
    0x00239430: 0x27A40218,   # addiu a0, sp, 0x218
    0x00239434: 0x0C1005B4,   # jal   0x4016d0
    0x00239438: 0x2405FFFF,   # addiu a1, zero, -1
    0x0023943C: 0x10000004,   # b     0x239450
    0x00239440: 0x8E040000,   # lw    a0, 0(s0)
}


def build() -> list:
    words, _labels = assemble(SRC, BRANCH, SYMS)
    if BRANCH + 4 * len(words) != BRANCH_END:
        raise ValueError("co-op label branch is %d words; it must fill 0x%08x..0x%08x exactly"
                         % (len(words), BRANCH, BRANCH_END))
    return words


def build_kill() -> list:
    """[(va, word)] for the kill feed's killer and victim branches."""
    out = []
    for at, end, src in ((KILLER_AT, KILLER_END, KILLER_SRC), (VICTIM_AT, VICTIM_END, VICTIM_SRC)):
        words, _labels = assemble(src, at, KSYMS)
        if at + 4 * len(words) > end:
            raise ValueError("kill-feed branch at 0x%08x: %d words, room %d"
                             % (at, len(words), (end - at) // 4))
        out += [(at + 4 * i, w) for i, w in enumerate(words)]
    return out


def edits() -> list:
    """(va, value, stock, note), only the words that change."""
    out = [(EXIT_S2, 0x00000000, JS_STOCK[EXIT_S2],
            "co-op labels: Civilian/Hostage/Friendly exit keeps the colour it is given")]
    for i, word in enumerate(build()):
        va = BRANCH + 4 * i
        if word != JS_STOCK[va]:
            out.append((va, word, JS_STOCK[va],
                        "co-op labels: an AI in your own company is a friend, not 'enemy soldier'"))
    for va, word in build_kill():
        if word != JS_STOCK[va]:
            out.append((va, word, JS_STOCK[va],
                        "co-op kill feed: an AI in the players' company is named and coloured "
                        "like a player"))
    return out


def js_edits(v: dict) -> list:
    return edits() if v.get("js_coop_label") else []


def cards(prefix: str = "js_", group: str = "Online") -> list:
    return [
        Setting(prefix + "coop_label", "Online co-op: AI squadmates labelled as friends", BOOL, False,
                group, confidence="experimental", requires={prefix + "coop_ai": [True]},
                help="Online, the HUD names whatever your reticle is on and tints the reticle to "
                     "match. Anything that is not a human player and not a civilian, hostage or "
                     "'Friendly' unit is taken for an enemy -- red, 'enemy soldier' -- because stock "
                     "online co-op never had AI on your side. With AI backup filling the fireteams, "
                     "your own Riflemen, Demolitions and Support men got that label on both "
                     "consoles. This checks the company first: a soldier in your own company is "
                     "shown by his kit name in green, like the other player. The kill feed gets "
                     "the same fix: 'Rifleman has killed an enemy soldier' in green instead of a "
                     "red 'an enemy soldier has killed an enemy soldier' (the host writes the "
                     "feed for both consoles). Only the label, the reticle tint and the feed "
                     "change -- friendly fire, kill scoring and who the AI shoot at never looked "
                     "at them.",
                caution="The label was played (teammates green); the kill feed is not yet. Both "
                        "checked by running the game's code over the co-op test consoles' RAM, "
                        "stock and patched."),
    ]


def selftest(js_elf=None) -> list:
    import struct
    fails = []
    for va, _w, s, _n in edits():
        if JS_STOCK.get(va) != s:
            fails.append("%08x: edit stock %08x, table %s" % (va, s, JS_STOCK.get(va)))
    if js_elf is not None:
        for va, want in JS_STOCK.items():
            got = struct.unpack_from("<I", js_elf, va - 0x00100000 + 0x100)[0]
            if got != want:
                fails.append("stock %08x: disc %08x, recorded %08x" % (va, got, want))
    return fails

"""Everyone calls out: Ghost Recon (SLUS-20613) and Jungle Storm (SLUS-20820).

Every team line goes through FireTeamAI::PlayVoice(line, speaker, delay) (GR
0x0018F410, JS 0x003DFB70), which sends a voice-clip message that
IkeSoundMgr::HandleVoiceClipMessage plays in the speaker's own voice
(SimHuman+0x638 GR / +0x668 JS). A speaker of -1 means the fireteam's
formation leader -- and a human player is always his fireteam's formation
leader, so "tango down", "contact" and "man down" already come out in the
player's voice in single player. Three things keep players quiet:

  * split screen drops radio lines. Lines 0-62 are radio (2D, volume 0.3);
    the sound manager plays one only in multiplayer or when the line is
    tagged with player 1's soldier. Split screen is not multiplayer, and
    the tag is one field per platoon that each fireteam's update overwrites,
    so it ends every frame as player 2: player 2's lines, and every "tango
    down" and "man down", are dropped (GR 0x00262074 / JS 0x002514DC,
    ``bne``);
  * "under fire" (lines 15 / 16) is skipped for any fireteam with a player
    in it (GR 0x0018E1F0 / JS 0x003DE7E0, ``beqz`` on the human member);
  * a lone voice is silent: PlayVoice returns early for a platoon of one
    (GR 0x0018F6D0 / JS 0x003DFE48) and, in Jungle Storm, a fireteam of one
    (0x003DFBA8) -- a one-life player whose teammates are down.

``callouts`` removes all three and makes "tango down" (line 24) the
killer's own line: FireTeamAI::ReportGotHim's PlayVoice call goes through a
routine that keeps PlayVoice's 2-second team cooldown and names the killer
(HumanAI+0x14 -> SimHuman+0x128) as speaker instead of the leader.

``contact`` (optional): a player who spots a new enemy says "contact" (line
9) himself, at most every 15 s per team (the timer the game uses for
"grenade!"), hooked where ReportEnemyContact's friendly and enemy paths
meet. Script-controlled (enemy) teams, AI reporters and the weak awareness
kind are left alone.

``respawn`` (optional, off by default): "rock and roll" when a split-screen
player takes over a soldier -- the one-life handoff and SELECT switching
both end at single player's takeover blip (GR HandleFollowNextTeamMember
0x00396830, JS SwitchFollowActor 0x00376294). The line exists only in male
voice 1 (tm1_rock_and_roll.wav, listed in every mission bank and used by
nothing); it plays 2D at the blip's volume, and only in split screen.

Not possible: a reloading call-out -- neither game has one recorded.

The routines live in sceChstat, sceRename and sceSync (GR 0x00417998,
0x00417BD8, 0x00417DE8; JS 0x297540 lower), which nothing in either loaded
image references. Every stock word was checked against the executables and
the routines were run in an interpreter with stubbed engine calls (speaker,
cooldowns, the enemy-team / AI-reporter / weak-sighting refusals, split
screen versus single player, registers and stack). Not yet played.
"""

from __future__ import annotations

from .grasm import assemble

GAMES = {
    "gr": dict(PV=0x0018F410, CLK_HI=0x5E, CLK_LO=-0x3E0,       # RSClock at 0x005DFC20
               GATE=0x00262074, UF=0x0018E1F0, LONE_FT=None, LONE_PLT=0x0018F6D0,
               TD_HOOK=0x00189A60, TD_HOOK_STOCK=0x0C063D04,     # jal PlayVoice
               CT_HOOK=0x0018A984, CT_HOOK_STOCK=0x10000017, CT_BACK=0x0018A9E4,
               RR_HOOK=0x00396830, RR_HOOK_STOCK=0x0C0E5A40,     # jal RSGESoundMgr::Get
               TD_CAVE=0x00417998, CT_CAVE=0x00417BD8, RR_CAVE=0x00417DE8,
               CAVE_END=0x00417F80, NEWENEMY="s4"),
    "js": dict(PV=0x003DFB70, CLK_HI=0x68, CLK_LO=0x4768,        # RSClock at 0x00684768
               GATE=0x002514DC, UF=0x003DE7E0, LONE_FT=0x003DFBA8, LONE_PLT=0x003DFE48,
               TD_HOOK=0x003DA4EC, TD_HOOK_STOCK=0x0C0F7EDC,
               CT_HOOK=0x003DB414, CT_HOOK_STOCK=0x10000013, CT_BACK=0x003DB464,
               RR_HOOK=0x00376294, RR_HOOK_STOCK=0x0C095BE4,     # jal Play2DSound
               TD_CAVE=0x00180458, CT_CAVE=0x00180698, RR_CAVE=0x001808A8,
               CAVE_END=0x00180A40, NEWENEMY="s6"),
}
# the gates' stock words: the branches the options turn into always / never
GATE_STOCK = {
    "gr": {0x00262074: 0x16E20079, 0x0018E1F0: 0x12200003, 0x0018F6D0: 0x10200003},
    "js": {0x002514DC: 0x160200B1, 0x003DE7E0: 0x12400003, 0x003DFBA8: 0x10200003,
           0x003DFE48: 0x10200003},
}

# "tango down" spoken by the killer, keeping PlayVoice's 2 s team cooldown.
# Entered by jal from ReportGotHim in place of jal PlayVoice: a0 = fireteam,
# a1 = 24, a2 = -1 (delay slot), f12 = delay; s2 = the killer's SimHuman.
TD_SRC = """
    lui   at, {CLK_HI:#x}
    lw    v0, {CLK_LO}(at)     ; RSClock
    lwc1  f1, 0xd4(v0)         ; now
    lwc1  f0, 0xf4(a0)         ; fireteam: last radio line
    sub.s f0, f1, f0
    lui   v0, 0x4000           ; 2.0 s, PlayVoice's own team cooldown
    mtc1  v0, f2
    c.lt.s f0, f2
    nop
    bc1t  quiet
    nop
    swc1  f1, 0xf4(a0)
    j     {PV:#x}              ; PlayVoice(team, 24, killer, delay); returns to ReportGotHim
    lw    a2, 0x128(s2)        ; speaker = killer's game-object id
quiet:
    jr    ra
    move  v0, zero
"""

# a player who spots an enemy says "contact" (line 9) himself. Entered by j from
# ReportEnemyContact's friendly / enemy merge point (stock: b to the loop test);
# s0 = awareness record, s1 = the reporter's HumanAI, s2 = the fireteam.
CT_SRC = """
    lbu   v0, 0xd9(s2)         ; script-controlled (Russian) team: stock only
    bnez  v0, out
    nop
    beqz  {NEWENEMY}, out      ; AddEnemy found nothing
    nop
    lbu   v0, 0x28(s0)         ; awareness kind, bits 4..3; 2 = the weak kind the
    andi  v0, v0, 0x18         ;   Russian contact line also skips
    li    at, 0x10
    beq   v0, at, out
    nop
    lw    a0, 0x14(s1)         ; reporter's SimHuman
    beqz  a0, out
    nop
    lw    v0, 0x138(a0)        ; control type: 0 = a player
    bnez  v0, out
    nop
    lui   at, {CLK_HI:#x}
    lw    v0, {CLK_LO}(at)
    lwc1  f2, 0xd4(v0)         ; now
    lwc1  f1, 0xf0(s2)         ; team shout time (stock: "grenade!" / Russian contact)
    sub.s f1, f2, f1
    lui   v0, 0x4170           ; 15.0 s
    mtc1  v0, f0
    c.le.s f1, f0
    nop
    bc1t  out
    nop
    swc1  f2, 0xf0(s2)
    swc1  f2, 0xf4(s2)         ; also holds the team's own radio line for 2 s
    lw    a2, 0x128(a0)        ; speaker = this player
    move  a0, s2
    li    a1, 9                ; detect_generic
    jal   {PV:#x}
    mtc1  zero, f12            ; no delay
out:
    j     {CT_BACK:#x}
    {CT_TAIL}
"""
CT_TAIL = {"gr": "lw    v1, 0x18(s2)", "js": "nop"}   # GR's loop test reads v1

# "rock and roll" on a split-screen takeover
RR_SRC = {"gr": """
    addiu sp, sp, -16
    sd    ra, 0(sp)
    lui   at, 0x5e
    lw    a0, 0x4ff8(at)       ; IIkeStateMgr
    lw    t9, 0(a0)
    lw    t9, 0xa0(t9)         ; InSplitScreenMode
    jalr  t9
    nop
    beqz  v0, stock
    nop
    jal   0x396900             ; RSGESoundMgr::Get
    nop
    lw    t9, 0(v0)
    move  a0, v0
    lui   a1, %hi(rr)
    addiu a1, a1, %lo(rr)
    lui   v1, 0x3f33
    ori   v1, v1, 0x3333       ; 0.7, the takeover blip's volume
    mtc1  v1, f12
    lw    t9, 0x14(t9)         ; Play2DSound(name, volume)
    jalr  t9
    nop
stock:
    jal   0x396900             ; the replaced call: v0 = RSGESoundMgr for the stock tail
    nop
    ld    ra, 0(sp)
    jr    ra
    addiu sp, sp, 16
rr:
    .asciiz "tm1_rock_and_roll.wav"
""", "js": """
    addiu sp, sp, -16
    sd    ra, 0(sp)
    swc1  f12, 8(sp)
    jal   0x256f90             ; the replaced call: Play2DSound("c_changsoldiers.wav", 0.7)
    nop
    jal   0x124620             ; IIkeStateMgr
    nop
    lw    t9, 0(v0)
    lw    t9, 0xa0(t9)         ; InSplitScreenMode
    jalr  t9
    move  a0, v0
    beqz  v0, out
    nop
    lui   a0, %hi(rr)
    addiu a0, a0, %lo(rr)
    jal   0x256f90             ; Play2DSound("tm1_rock_and_roll.wav", 0.7)
    lwc1  f12, 8(sp)
out:
    ld    ra, 0(sp)
    jr    ra
    addiu sp, sp, 16
rr:
    .asciiz "tm1_rock_and_roll.wav"
"""}

_GR_CAVE_STOCK_HEX = (   # sceChstat + sceRename + sceSync, 0x00417998..0x00417F80
    "27BDFF20 FFB20060 FFB700B0 0080902D FFB00040 00C0B82D FFBE00C0 00A0802D"
    "FFB30070 2404000D FFBF00D0 3C1E005F FFB600A0 27D3E100 FFB50090 FFB40080"
    "0C10563E FFB10050 3C030057 8C62E1C0 54400004 92420000 0C10567E 00000000"
    "92420000 0000882D 0040182D 1060000E A2620050 27B40030 3C16005F 3C15005F"
    "26310001 2A220400 1040000A 02511021 02712021 90430000 1460FFF9 A0830050"
    "10000005 24020400 27B40030 3C16005F 3C15005F 24020400 16220003 00000000"
    "A260044F 241103FF 6A030007 6E030000 6A04000F 6E040008 6A050017 6E050010"
    "6A06001F 6E060018 B2630017 B6630010 B264001F B6640018 B2650027 B6650020"
    "B266002F B6660028 6A030027 6E030020 6A04002F 6E040028 6A050037 6E050030"
    "6A06003F 6E060038 B2630037 B6630030 B264003F B6640038 B2650047 B6650040"
    "B266004F B6660048 24020001 AE77000C 27A40010 AFA20014 27D0E100 AFA00018"
    "26B5ED40 0C1046B8 AFA00024 0040902D 0200202D 24020004 AE740004 AE620008"
    "24050450 0C1050E0 AE720000 26C4F3C0 0200382D 26280051 AFA00000 2405000D"
    "0000302D 02A0482D 240A0004 0C10531C 0000582D 04410007 3C022000 0C1046BC"
    "0240202D 0C10564A 00000000 1000000F 2402FFF5 02A21025 0C10564A 8C500000"
    "16000005 00000000 0C1046BC 0240202D 10000006 2402FFF5 0C1046C8 0240202D"
    "0C1046BC 0240202D 8FA20030 DFBF00D0 DFBE00C0 DFB700B0 DFB600A0 DFB50090"
    "DFB40080 DFB30070 DFB20060 DFB10050 DFB00040 03E00008 27BD00E0 00000000"
    "27BDFF40 FFB10050 FFB00040 0080882D FFB600A0 00A0802D FFB20060 24040011"
    "FFBF00B0 3C16005F FFB50090 26D2E100 FFB40080 0C10563E FFB30070 3C020057"
    "8C43E1C0 54600004 92220000 0C10567E 00000000 92220000 0000282D 00021E00"
    "10600010 A242000C 27B30030 3C15005F 3C14005F 24A50001 28A20400 1040000C"
    "02251021 02452021 90430000 A083000C 00031E00 5460FFF8 24A50001 10000005"
    "24020400 27B30030 3C15005F 3C14005F 24020400 50A20001 A240040B 92020000"
    "0000282D 00021E00 1060000C A242040C 2646040C 24A50001 28A20400 10400007"
    "02051021 00C52021 90430000 A0830000 00031E00 5460FFF8 24A50001 24020400"
    "50A20001 A240080B 24020001 AFA00018 AFA20014 27A40010 AFA00024 0C1046B8"
    "26D0E100 2694ED40 0040882D 0200202D 24020004 AE530004 AE420008 2405080C"
    "0C1050E0 AE510000 26A4F3C0 0200382D AFA00000 24050011 0000302D 2408080C"
    "0280482D 240A0004 0C10531C 0000582D 04410007 3C022000 0C1046BC 0220202D"
    "0C10564A 00000000 1000000F 2402FFF5 02821025 0C10564A 8C500000 16000005"
    "00000000 0C1046BC 0220202D 10000006 2402FFF5 0C1046C8 0220202D 0C1046BC"
    "0220202D 8FA20030 DFBF00B0 DFB600A0 DFB50090 DFB40080 DFB30070 DFB20060"
    "DFB10050 DFB00040 03E00008 27BD00C0 27BDFFF0 FFBF0000 0C105B4A 24050012"
    "DFBF0000 03E00008 27BD0010 00000000 27BDFF40 FFB10050 FFB50090 0080882D"
    "FFB600A0 00A0A82D FFB00040 24040013 FFBF00B0 3C16005F FFB40080 26D0E100"
    "FFB30070 0C10563E FFB20060 3C020057 8C43E1C0 54600004 92220000 0C10567E"
    "00000000 92220000 0000282D 00021E00 10600010 A2020014 27B20030 3C14005F"
    "3C13005F 24A50001 28A20400 1040000C 02251021 02052021 90430000 A0830014"
    "00031E00 5460FFF8 24A50001 10000005 24020400 27B20030 3C14005F 3C13005F"
    "24020400 50A20001 A2000413 AE150010 24020001 AFA20014 27A40010 AFA00018"
    "2673ED40 0C1046B8 AFA00024 0040882D AE120004 24020004 AE110000 AE020008"
    "2684F3C0 26C7E100 24050013 AFA00000 0000302D 24080414 0260482D 240A0004"
    "0C10531C 0000582D 04410007 3C022000 0C1046BC 0220202D 0C10564A 00000000"
    "1000000F 2402FFF5 02621025 0C10564A 8C500000 16000005 00000000 0C1046BC"
    "0220202D 10000006 2402FFF5 0C1046C8 0220202D 0C1046BC 0220202D 8FA20030"
    "DFBF00B0 DFB600A0 DFB50090 DFB40080 DFB30070 DFB20060 DFB10050 DFB00040"
    "03E00008 27BD00C0"
)

_JS_CAVE_STOCK_HEX = (   # sceChstat + sceRename + sceSync, 0x00180458..0x00180A40
    "27BDFF20 FFB20060 FFB700B0 0080902D FFB00040 00C0B82D FFBE00C0 00A0802D"
    "FFB30070 2404000D FFBF00D0 3C1E0061 FFB600A0 27D37000 FFB50090 FFB40080"
    "0C05F8CC FFB10050 3C030057 8C624FEC 54400004 92420000 0C05F918 00000000"
    "92420000 0000882D 0040182D 1060000E A2620050 27B40030 3C160062 3C150061"
    "26310001 2A220400 1040000A 02511021 02712021 90430000 1460FFF9 A0830050"
    "10000005 24020400 27B40030 3C160062 3C150061 24020400 16220003 00000000"
    "A260044F 241103FF 6A030007 6E030000 6A04000F 6E040008 6A050017 6E050010"
    "6A06001F 6E060018 B2630017 B6630010 B264001F B6640018 B2650027 B6650020"
    "B266002F B6660028 6A030027 6E030020 6A04002F 6E040028 6A050037 6E050030"
    "6A06003F 6E060038 B2630037 B6630030 B264003F B6640038 B2650047 B6650040"
    "B266004F B6660048 24020001 AE77000C 27A40010 AFA20014 27D07000 AFA00018"
    "26B57C40 0C05E8B8 AFA00024 0040902D 0200202D 24020004 AE740004 AE620008"
    "24050450 0C05F324 AE720000 26C48700 0200382D 26280051 AFA00000 2405000D"
    "0000302D 02A0482D 240A0004 0C05F5AA 0000582D 04410007 3C022000 0C05E8BC"
    "0240202D 0C05F8D8 00000000 1000000F 2402FFF5 02A21025 0C05F8D8 8C500000"
    "16000005 00000000 0C05E8BC 0240202D 10000006 2402FFF5 0C05E8C8 0240202D"
    "0C05E8BC 0240202D 8FA20030 DFBF00D0 DFBE00C0 DFB700B0 DFB600A0 DFB50090"
    "DFB40080 DFB30070 DFB20060 DFB10050 DFB00040 03E00008 27BD00E0 00000000"
    "27BDFF40 FFB10050 FFB00040 0080882D FFB600A0 00A0802D FFB20060 24040011"
    "FFBF00B0 3C160061 FFB50090 26D27000 FFB40080 0C05F8CC FFB30070 3C020057"
    "8C434FEC 54600004 92220000 0C05F918 00000000 92220000 0000282D 00021E00"
    "10600010 A242000C 27B30030 3C150062 3C140061 24A50001 28A20400 1040000C"
    "02251021 02452021 90430000 A083000C 00031E00 5460FFF8 24A50001 10000005"
    "24020400 27B30030 3C150062 3C140061 24020400 50A20001 A240040B 92020000"
    "0000282D 00021E00 1060000C A242040C 2646040C 24A50001 28A20400 10400007"
    "02051021 00C52021 90430000 A0830000 00031E00 5460FFF8 24A50001 24020400"
    "50A20001 A240080B 24020001 AFA00018 AFA20014 27A40010 AFA00024 0C05E8B8"
    "26D07000 26947C40 0040882D 0200202D 24020004 AE530004 AE420008 2405080C"
    "0C05F324 AE510000 26A48700 0200382D AFA00000 24050011 0000302D 2408080C"
    "0280482D 240A0004 0C05F5AA 0000582D 04410007 3C022000 0C05E8BC 0220202D"
    "0C05F8D8 00000000 1000000F 2402FFF5 02821025 0C05F8D8 8C500000 16000005"
    "00000000 0C05E8BC 0220202D 10000006 2402FFF5 0C05E8C8 0220202D 0C05E8BC"
    "0220202D 8FA20030 DFBF00B0 DFB600A0 DFB50090 DFB40080 DFB30070 DFB20060"
    "DFB10050 DFB00040 03E00008 27BD00C0 27BDFFF0 FFBF0000 0C05FDFA 24050012"
    "DFBF0000 03E00008 27BD0010 00000000 27BDFF40 FFB10050 FFB50090 0080882D"
    "FFB600A0 00A0A82D FFB00040 24040013 FFBF00B0 3C160061 FFB40080 26D07000"
    "FFB30070 0C05F8CC FFB20060 3C020057 8C434FEC 54600004 92220000 0C05F918"
    "00000000 92220000 0000282D 00021E00 10600010 A2020014 27B20030 3C140062"
    "3C130061 24A50001 28A20400 1040000C 02251021 02052021 90430000 A0830014"
    "00031E00 5460FFF8 24A50001 10000005 24020400 27B20030 3C140062 3C130061"
    "24020400 50A20001 A2000413 AE150010 24020001 AFA20014 27A40010 AFA00018"
    "26737C40 0C05E8B8 AFA00024 0040882D AE120004 24020004 AE110000 AE020008"
    "26848700 26C77000 24050013 AFA00000 0000302D 24080414 0260482D 240A0004"
    "0C05F5AA 0000582D 04410007 3C022000 0C05E8BC 0220202D 0C05F8D8 00000000"
    "1000000F 2402FFF5 02621025 0C05F8D8 8C500000 16000005 00000000 0C05E8BC"
    "0220202D 10000006 2402FFF5 0C05E8C8 0220202D 0C05E8BC 0220202D 8FA20030"
    "DFBF00B0 DFB600A0 DFB50090 DFB40080 DFB30070 DFB20060 DFB10050 DFB00040"
    "03E00008 27BD00C0"
)


def _stock_words(base, hexwords):
    words = "".join(hexwords.split())
    return {base + 4 * i: int(words[8 * i:8 * i + 8], 16) for i in range(len(words) // 8)}


GR_STOCK = _stock_words(GAMES["gr"]["TD_CAVE"], _GR_CAVE_STOCK_HEX)
GR_STOCK.update(GATE_STOCK["gr"])
JS_STOCK = _stock_words(GAMES["js"]["TD_CAVE"], _JS_CAVE_STOCK_HEX)
JS_STOCK.update(GATE_STOCK["js"])
for _g, _st in (("gr", GR_STOCK), ("js", JS_STOCK)):
    _c = GAMES[_g]
    _st.update({_c["TD_HOOK"]: _c["TD_HOOK_STOCK"], _c["CT_HOOK"]: _c["CT_HOOK_STOCK"],
                _c["RR_HOOK"]: _c["RR_HOOK_STOCK"]})


def _always(stock):
    """beqz / bnez rs -> b, same target."""
    if stock >> 26 not in (4, 5) or (stock >> 16) & 31:
        raise ValueError("not a compare-with-zero branch: %08X" % stock)
    return 0x10000000 | (stock & 0xFFFF)


def _routine(src, base, end, what):
    words, _labels = assemble(src, base)
    if base + 4 * len(words) > end:
        raise ValueError("%s routine outgrows its cave" % what)
    return words


def edits(game: str, callouts: bool, contact: bool = False, respawn: bool = False):
    """(va, value, stock, note). `contact` needs `callouts`; `respawn` stands alone."""
    c = GAMES[game]
    st = GR_STOCK if game == "gr" else JS_STOCK
    out = []
    if callouts:
        out.append((c["GATE"], 0x00000000, st[c["GATE"]],
                    "call-outs: split screen plays every friendly radio line"))
        out.append((c["UF"], _always(st[c["UF"]]), st[c["UF"]],
                    "call-outs: 'under fire' also for players' fireteams"))
        for va in (c["LONE_FT"], c["LONE_PLT"]):
            if va:
                out.append((va, _always(st[va]), st[va], "call-outs: a lone soldier still talks"))
        for i, w in enumerate(_routine(TD_SRC.format(**c), c["TD_CAVE"], c["CT_CAVE"],
                                       "tango-down")):
            out.append((c["TD_CAVE"] + 4 * i, w, st[c["TD_CAVE"] + 4 * i],
                        "call-outs: 'tango down' in the killer's voice"))
        out.append((c["TD_HOOK"], assemble("jal %#x" % c["TD_CAVE"], c["TD_HOOK"])[0][0],
                    c["TD_HOOK_STOCK"], "call-outs: ReportGotHim names the killer"))
    if callouts and contact:
        src = CT_SRC.format(CT_TAIL=CT_TAIL[game], **c)
        for i, w in enumerate(_routine(src, c["CT_CAVE"], c["RR_CAVE"], "contact")):
            out.append((c["CT_CAVE"] + 4 * i, w, st[c["CT_CAVE"] + 4 * i],
                        "call-outs: a player calls 'contact'"))
        out.append((c["CT_HOOK"], assemble("j %#x" % c["CT_CAVE"], c["CT_HOOK"])[0][0],
                    c["CT_HOOK_STOCK"], "call-outs: ReportEnemyContact asks the player"))
    if respawn:
        for i, w in enumerate(_routine(RR_SRC[game], c["RR_CAVE"], c["CAVE_END"],
                                       "rock-and-roll")):
            out.append((c["RR_CAVE"] + 4 * i, w, st[c["RR_CAVE"] + 4 * i],
                        "call-outs: 'rock and roll' on a split-screen takeover"))
        out.append((c["RR_HOOK"], assemble("jal %#x" % c["RR_CAVE"], c["RR_HOOK"])[0][0],
                    c["RR_HOOK_STOCK"], "call-outs: takeover plays 'rock and roll'"))
    return out


def gr_edits(v: dict):
    return edits("gr", bool(v.get("gr_callouts")), bool(v.get("gr_callouts_contact")),
                 bool(v.get("gr_callouts_respawn") and v.get("gr_ss_handoff")))


def js_edits(v: dict):
    return edits("js", bool(v.get("js_callouts")), bool(v.get("js_callouts_contact")),
                 bool(v.get("js_callouts_respawn") and v.get("js_ss_handoff")))


def selftest(gr_elf: bytes, js_elf: bytes):
    """Every stock word against the executables, no address twice. [] = pass."""
    bad = []
    for game, st, elf, d in (("gr", GR_STOCK, gr_elf, 0x80), ("js", JS_STOCK, js_elf, 0x100)):
        for va, w in st.items():
            off = va - 0x100000 + d
            if int.from_bytes(elf[off:off + 4], "little") != w:
                bad.append("%s %08X" % (game, va))
        e = edits(game, True, True, True)
        if len({va for va, *_ in e}) != len(e):
            bad.append("%s duplicate VA" % game)
        if any(va not in st for va, *_ in e):
            bad.append("%s VA without a stock word" % game)
    return bad

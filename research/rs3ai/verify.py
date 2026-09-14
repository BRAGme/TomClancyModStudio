import r6, struct

SITES = [
    (0x00142018, "lui $v1,0x3d07        (0.033 threshold, hi)"),
    (0x0014201c, "ori $v1,$v1,0x2b02    (0.033 threshold, lo)"),
    (0x00142028, "c.olt.s $f21,$f0      dt < 0.033 ?"),
    (0x00142030, "bc1f 0x0014204c       not less -> skip"),
    (0x00142038, "bne $s2,$v1,0x14204c  player index != 1 -> skip"),
    (0x0014203c, "delay slot"),
    (0x00142040, "lui $v1,0x3d4c        (0.05, hi)"),
    (0x00142044, "ori $v1,$v1,0xcccd    (0.05, lo)"),
    (0x00142048, "mtc1 $v1,$f21         dt := 0.05   <-- THE INSTRUCTION"),
    (0x0014204c, "join"),
    (0x0014316c, "div.s $f0,$f0,$f21    X look: 20.0/dt"),
    (0x00143364, "div.s $f0,$f0,$f21    Y look: 20.0/dt"),
    (0x00142ba8, "div.s $f3,$f0,$f21    move: 60.0/dt"),
    (0x00143180, "swc1 $f0,0x518($v0)   PC->LookRateX"),
    (0x00143378, "swc1 $f0,0x51c($v1)   PC->LookRateY"),
    (0x001430b4, "lbu $v0,0x4a1($a0)    X sensitivity step"),
    (0x001432a4, "lbu $v1,0x4a2($a1)    Y sensitivity step"),
    (0x001430ec, "mul.s $f0,$f1,$f0     step * cfg[0x208]"),
    (0x001430f0, "mul.s $f20,$f20,$f0"),
    (0x0021d9f8, "beqz -> skip per-player copy when NOT split screen"),
    (0x0021da08, "bnez $v0,0x21dab0     player index != 0 -> P2 slots"),
    (0x0021d920, "lbu $a1,0x30(settings)  default Y"),
    (0x0021d930, "lbu $a1,0x2f(settings)  default X"),
    (0x001428bc, "bnez $v0,0x14295c     split screen -> skip per-frame default reapply"),
    (0x00588ddc, "sb $a0,0x31($v1)      P1 X := 5"),
    (0x00588de0, "sb $a0,0x32($v1)      P1 Y := 5"),
    (0x00588ee4, "sb $a0,0x33($v1)      P2 X := 5"),
    (0x00588eec, "sb $a0,0x34($v1)      P2 Y := 5"),
    (0x00588db0, "addiu $a0,$zero,5     the default step"),
    (0x00588eb8, "addiu $a0,$zero,5     the default step (P2 branch)"),
    (0x00588d88, "lw $v1,-0x6fe0($gp)   guard"),
    (0x00588e90, "lw $v1,-0x6fe0($gp)   guard (P2 branch)"),
    (0x0057be80, "sb $v1,0x2f($v0)      PSX2USER.INI XAxisSensitivity -> +0x2f"),
    (0x0057becc, "sb $v1,0x30($v0)      PSX2USER.INI YAxisSensitivity -> +0x30"),
]

print("verified against sp.bin (sha1 e9bb12138a1e69d551ac9f6b958114e5b2e830da)\n")
for va, note in SITES:
    print("%08x  %08x  %-38s | %s" % (va, r6.w(va), r6.dis1(va), note))

print()
for f in (0x3d072b02, 0x3d4ccccd, 0x3d23d70a, 0x42b40000, 0x41a00000, 0x42700000):
    print("0x%08x = %r" % (f, struct.unpack("<f", struct.pack("<I", f))[0]))

print()
def enc_b(at, target):
    return 0x10000000 | (((target - (at + 4)) >> 2) & 0xFFFF)
print("b 0x14204c from 0x00142038 = %08x" % enc_b(0x00142038, 0x0014204c))
print("float 0.0333333 = %08x" % struct.unpack("<I", struct.pack("<f", 1.0 / 30.0))[0])
print("float 0.025     = %08x" % struct.unpack("<I", struct.pack("<f", 0.025))[0])
print("float 0.0166667 = %08x" % struct.unpack("<I", struct.pack("<f", 1.0 / 60.0))[0])

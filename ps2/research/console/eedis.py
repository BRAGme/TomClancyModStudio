"""Enough R5900 disassembly to say what a parked function is doing.

Stock Ghidra stops at the first `lq`/`sq` (opcodes 0x1E/0x1F), which the
Emotion Engine uses in almost every prologue, so a MIPS32 decoder gives up two
instructions in. Nothing here tries to be a full disassembler -- the question
is only: what does this function CALL, does it reach a `syscall`, and where
does it end.
"""
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = 0x00100000
img = open(os.path.join(HERE, "ghidra", "SP_SOZ.bin"), "rb").read()

REG = ("zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 "
       "s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp s8 ra").split()

LOAD_STORE = {0x20: "lb", 0x21: "lh", 0x23: "lw", 0x24: "lbu", 0x25: "lhu",
              0x28: "sb", 0x29: "sh", 0x2B: "sw", 0x1E: "lq", 0x1F: "sq",
              0x37: "ld", 0x3F: "sd", 0xC1: "lwc1", 0xE1: "swc1"}
IMM = {0x08: "addi", 0x09: "addiu", 0x0A: "slti", 0x0B: "sltiu",
       0x0C: "andi", 0x0D: "ori", 0x0E: "xori", 0x18: "daddi",
       0x19: "daddiu"}
BRANCH = {0x04: "beq", 0x05: "bne", 0x06: "blez", 0x07: "bgtz",
          0x14: "beql", 0x15: "bnel", 0x16: "blezl", 0x17: "bgtzl"}


def w(va):
    o = va - BASE
    return struct.unpack_from("<I", img, o)[0] if 0 <= o <= len(img) - 4 else None


def sx(v):
    return v - 0x10000 if v & 0x8000 else v


def dis(va):
    x = w(va)
    if x is None:
        return None, None
    op, rs, rt, rd = x >> 26, (x >> 21) & 31, (x >> 16) & 31, (x >> 11) & 31
    imm, tgt, funct = x & 0xFFFF, x & 0x03FFFFFF, x & 0x3F
    if x == 0:
        return "nop", None
    if op == 0:
        if funct == 0x08:
            return "jr %s" % REG[rs], ("ret" if rs == 31 else None)
        if funct == 0x09:
            return "jalr %s" % REG[rs], "callr"
        if funct == 0x0C:
            return "SYSCALL", "syscall"
        if funct == 0x21:
            return "addu %s,%s,%s" % (REG[rd], REG[rs], REG[rt]), None
        if funct == 0x25:
            return "or %s,%s,%s" % (REG[rd], REG[rs], REG[rt]), None
        return "special.%02x" % funct, None
    if op == 0x02:
        return "j %08x" % (((va + 4) & 0xF0000000) | (tgt << 2)), None
    if op == 0x03:
        dst = ((va + 4) & 0xF0000000) | (tgt << 2)
        return "jal %08x" % dst, ("call", dst)
    if op == 0x0F:
        return "lui %s,0x%x" % (REG[rt], imm), None
    if op in IMM:
        return "%s %s,%s,%d" % (IMM[op], REG[rt], REG[rs], sx(imm)), None
    if op in LOAD_STORE:
        return "%s %s,%d(%s)" % (LOAD_STORE[op], REG[rt], sx(imm), REG[rs]), None
    if op in BRANCH:
        return "%s %s,%s,%08x" % (BRANCH[op], REG[rs], REG[rt],
                                  va + 4 + (sx(imm) << 2)), None
    if op == 0x1C:
        return "MMI.%02x" % funct, None
    if op in (0x11, 0x12, 0x13):
        return "cop%d" % (op - 0x10), None
    return "op%02x", None


def walk(start, label, limit=400):
    print()
    print("=== %s : %08x ===" % (label, start))
    calls, syscalls = [], []
    va = start
    for _ in range(limit):
        text, kind = dis(va)
        if text is None:
            break
        print("   %08x  %s" % (va, text))
        if isinstance(kind, tuple) and kind[0] == "call":
            calls.append(kind[1])
        elif kind == "syscall":
            syscalls.append(va)
        elif kind == "ret":
            # the delay slot belongs to the return
            t2, _ = dis(va + 4)
            print("   %08x  %s   (delay slot)" % (va + 4, t2))
            break
        va += 4
    print("   -> %d call(s): %s" % (len(calls),
                                    ", ".join("%08x" % c for c in calls[:12])))
    print("   -> %d syscall(s)%s" % (len(syscalls),
                                     " at " + ", ".join("%08x" % s for s in syscalls)
                                     if syscalls else ""))
    return calls, syscalls


for a in sys.argv[1:]:
    walk(int(a, 16), "parked")

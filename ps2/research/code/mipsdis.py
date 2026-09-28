"""Just enough MIPS to read Rainbow Six 3's split-screen code.

This is not a general disassembler. It decodes the handful of forms the PS2
build actually uses around the split-screen setup -- loads, stores, branches,
immediate arithmetic and jumps -- and prints them with the gp-relative
displacement kept visible, because that displacement is what identifies a
global.

Everything the wheel investigation needs is a `sw` of `zero` to a gp-relative
slot: that is the engine switching a feature off for split screen.
"""

from __future__ import annotations

import struct

REG = ("zero", "at", "v0", "v1", "a0", "a1", "a2", "a3",
       "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7",
       "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7",
       "t8", "t9", "k0", "k1", "gp", "sp", "s8", "ra")

#: opcode -> mnemonic for the I-type forms this build uses
ITYPE = {
    0x04: "beq", 0x05: "bne", 0x06: "blez", 0x07: "bgtz",
    0x08: "addi", 0x09: "addiu", 0x0A: "slti", 0x0B: "sltiu",
    0x0C: "andi", 0x0D: "ori", 0x0E: "xori", 0x0F: "lui",
    0x20: "lb", 0x21: "lh", 0x23: "lw", 0x24: "lbu", 0x25: "lhu",
    0x28: "sb", 0x29: "sh", 0x2B: "sw", 0x37: "ld", 0x3F: "sd",
    0x31: "lwc1", 0x39: "swc1",
}

#: funct -> mnemonic for the R-type forms
RTYPE = {
    0x00: "sll", 0x02: "srl", 0x03: "sra", 0x04: "sllv", 0x06: "srlv",
    0x08: "jr", 0x09: "jalr", 0x0C: "syscall", 0x0D: "break",
    0x10: "mfhi", 0x12: "mflo", 0x18: "mult", 0x19: "multu",
    0x1A: "div", 0x1B: "divu",
    0x20: "add", 0x21: "addu", 0x22: "sub", 0x23: "subu",
    0x24: "and", 0x25: "or", 0x26: "xor", 0x27: "nor",
    0x2A: "slt", 0x2B: "sltu",
    # The PS2 core is MIPS64, and the compiler uses the doubleword forms
    # freely -- `daddu $a0, $v0, $zero` is its ordinary register move. Leaving
    # these out fills the listing with `.word` and hides real instructions.
    0x2C: "dadd", 0x2D: "daddu", 0x2E: "dsub", 0x2F: "dsubu",
    0x14: "dsllv", 0x16: "dsrlv", 0x17: "dsrav",
    0x38: "dsll", 0x3A: "dsrl", 0x3B: "dsra",
    0x3C: "dsll32", 0x3E: "dsrl32", 0x3F: "dsra32",
}

LOAD_STORE = {"lb", "lh", "lw", "lbu", "lhu", "sb", "sh", "sw",
              "ld", "sd", "lwc1", "swc1"}


def _signed(value):
    return value - 0x10000 if value & 0x8000 else value


def decode(word, va=0):
    """(mnemonic, text, info) for one instruction.

    `info` carries the fields a caller may want to match on without
    re-parsing the text: base register, displacement, and target register.
    """
    if word == 0:
        return "nop", "nop", {}
    op = word >> 26
    rs, rt = (word >> 21) & 31, (word >> 16) & 31
    rd, sa = (word >> 11) & 31, (word >> 6) & 31
    funct = word & 63
    imm = word & 0xFFFF
    simm = _signed(imm)

    if op == 0:
        name = RTYPE.get(funct)
        if name is None:
            return "?", ".word 0x%08x" % word, {}
        if name == "jr":
            return name, "jr   $%s" % REG[rs], {}
        if name == "jalr":
            return name, "jalr $%s, $%s" % (REG[rd], REG[rs]), {}
        if name in ("sll", "srl", "sra"):
            return name, "%-4s $%s, $%s, %d" % (name, REG[rd], REG[rt], sa), {}
        if name in ("mfhi", "mflo"):
            return name, "%-4s $%s" % (name, REG[rd]), {}
        if name in ("mult", "multu", "div", "divu"):
            return name, "%-4s $%s, $%s" % (name, REG[rs], REG[rt]), {}
        return name, "%-4s $%s, $%s, $%s" % (name, REG[rd], REG[rs], REG[rt]), \
            {"rd": rd, "rs": rs, "rt": rt}

    if op == 2 or op == 3:
        name = "j" if op == 2 else "jal"
        target = ((va + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
        return name, "%-4s 0x%08x" % (name, target), {"target": target}

    if op == 1:
        name = {0x00: "bltz", 0x01: "bgez", 0x10: "bltzal",
                0x11: "bgezal"}.get(rt, "?")
        target = va + 4 + (simm << 2)
        return name, "%-4s $%s, 0x%08x" % (name, REG[rs], target), \
            {"target": target}

    name = ITYPE.get(op)
    if name is None:
        return "?", ".word 0x%08x" % word, {}

    if name in LOAD_STORE:
        return name, "%-4s $%s, %s0x%x($%s)" % (
            name, REG[rt], "-" if simm < 0 else "", abs(simm), REG[rs]), \
            {"rt": rt, "base": rs, "disp": simm}
    if name in ("beq", "bne"):
        target = va + 4 + (simm << 2)
        if rt == 0:
            short = "beqz" if name == "beq" else "bnez"
            return short, "%-4s $%s, 0x%08x" % (short, REG[rs], target), \
                {"target": target}
        return name, "%-4s $%s, $%s, 0x%08x" % (
            name, REG[rs], REG[rt], target), {"target": target}
    if name in ("blez", "bgtz"):
        target = va + 4 + (simm << 2)
        return name, "%-4s $%s, 0x%08x" % (name, REG[rs], target), \
            {"target": target}
    if name == "lui":
        return name, "lui  $%s, 0x%x" % (REG[rt], imm), {"rt": rt, "imm": imm}
    return name, "%-4s $%s, $%s, %d" % (name, REG[rt], REG[rs], simm), \
        {"rt": rt, "rs": rs, "imm": simm}


def walk(image, base_va, va, count):
    """[(va, word, mnemonic, text, info)] for `count` instructions."""
    out = []
    for i in range(count):
        at = va + i * 4
        off = at - base_va
        if off < 0 or off + 4 > len(image):
            break
        word = struct.unpack_from("<I", image, off)[0]
        mnem, text, info = decode(word, at)
        out.append((at, word, mnem, text, info))
    return out


def function_start(image, base_va, va, limit=800):
    """Walk back to the likely entry of the function containing `va`.

    A PS2 function prologue is an `addiu $sp, $sp, -N`. Walking back to the
    nearest one is not proof, but it is right often enough to read a routine,
    and the caller sees the disassembly and can judge.
    """
    for i in range(1, limit):
        at = va - i * 4
        off = at - base_va
        if off < 0:
            break
        word = struct.unpack_from("<I", image, off)[0]
        mnem, _text, info = decode(word, at)
        if mnem == "addiu" and info.get("rt") == 29 and info.get("rs") == 29 \
                and info.get("imm", 0) < 0:
            return at
    return None


def gp_stores(image, base_va, lo_va, hi_va, of_zero=True):
    """Every `sw`/`sb` into a gp-relative slot in a range.

    These are the interesting ones: a store of `$zero` into a gp global is the
    engine turning something off, which is exactly the shape of the
    split-screen suppressions.
    """
    out = []
    for at, word, mnem, text, info in walk(image, base_va, lo_va,
                                           (hi_va - lo_va) // 4):
        if mnem not in ("sw", "sb", "sh"):
            continue
        if info.get("base") != 28:          # $gp
            continue
        if of_zero and info.get("rt") != 0:
            continue
        out.append((at, word, text, info["disp"]))
    return out

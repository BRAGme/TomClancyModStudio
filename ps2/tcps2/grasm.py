"""A small two-pass R5900 assembler for code caves.

Every other cave in this tool is a list of hand-encoded words. The Ghost Recon
split-screen caves are longer than that stays readable for -- a loop that calls
seven engine functions -- so they are written as source and assembled here::

    words, labels = assemble(src, base=0x00430518, syms={"CopyEntry": 0x1E5E70})

Syntax: one instruction per line, ``label:`` on its own or in front of an
instruction, ``;`` or ``#`` comments. Registers by name, with or without ``$``.
Immediates in decimal or ``0x`` hex; ``%hi(x)`` / ``%lo(x)`` split an address
(``%lo`` is signed and ``%hi`` carries the adjustment); ``name+4`` works on any
label or symbol. ``.word x`` emits one word, ``.asciiz "..."`` a NUL-terminated
string padded to a word.

The only pseudo-instructions are ``nop``, ``move`` (``daddu rd, rs, zero``, so all
64 bits of a register survive), ``li`` (16-bit), ``b``, ``beqz`` and ``bnez``.
Delay slots are the author's job: nothing is reordered or filled.

The encoder is checked against instruction words read out of the Ghost Recon
executable (``tests`` in ``grsquad``); a cave is also disassembled back before it
is trusted.
"""

from __future__ import annotations

import re

REGS = {n: i for i, n in enumerate(
    "zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 "
    "s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra".split())}
REGS["s8"] = 30

I_ARITH = {"addiu": 0x09, "slti": 0x0A, "sltiu": 0x0B, "andi": 0x0C,
           "ori": 0x0D, "xori": 0x0E, "daddiu": 0x19}
MEM = {"lb": 0x20, "lh": 0x21, "lw": 0x23, "lbu": 0x24, "lhu": 0x25,
       "sb": 0x28, "sh": 0x29, "sw": 0x2B, "ld": 0x37, "sd": 0x3F,
       "lq": 0x1E, "sq": 0x1F, "lwc1": 0x31, "swc1": 0x39}
R3 = {"addu": 0x21, "subu": 0x23, "and": 0x24, "or": 0x25, "xor": 0x26,
      "nor": 0x27, "slt": 0x2A, "sltu": 0x2B, "daddu": 0x2D}
SHIFT = {"sll": 0x00, "srl": 0x02, "sra": 0x03}
#: COP1 single-precision ops (fd, fs, ft). Every FPU form below was checked
#: against a word the Ghost Recon executable itself contains; note the
#: R5900's sqrt.s takes its source in ft, not fs.
FP_S = {"add.s": 0x00, "sub.s": 0x01, "mul.s": 0x02, "div.s": 0x03,
        "mov.s": 0x06, "neg.s": 0x07}


def _freg(t):
    t = t.strip().lstrip("$")
    if not t.startswith("f") or not t[1:].isdigit() or not 0 <= int(t[1:]) < 32:
        raise AsmError("bad FPU register %r" % t)
    return int(t[1:])


class AsmError(ValueError):
    pass


def _reg(t):
    t = t.strip().lstrip("$")
    if t not in REGS:
        raise AsmError("bad register %r" % t)
    return REGS[t]


class Asm:
    def __init__(self, base, syms=None):
        self.base = base
        self.syms = dict(syms or {})
        self.labels = {}

    def value(self, t, labels):
        t = t.strip()
        m = re.fullmatch(r"%(hi|lo)\((.+)\)", t)
        if m:
            v = self.value(m.group(2), labels) & 0xFFFFFFFF
            lo = v & 0xFFFF
            if m.group(1) == "lo":
                return lo - 0x10000 if lo & 0x8000 else lo
            return ((v + 0x8000) >> 16) & 0xFFFF
        if not re.fullmatch(r"-?(0x[0-9a-fA-F]+|\d+)", t):
            m = re.fullmatch(r"(.+?)([+-])(0x[0-9a-fA-F]+|\d+)", t)
            if m:
                b = self.value(m.group(1), labels)
                o = int(m.group(3), 0)
                return b + o if m.group(2) == "+" else b - o
        if t in labels:
            return labels[t]
        if t in self.syms:
            return self.syms[t]
        try:
            return int(t, 0)
        except ValueError:
            raise AsmError("unknown symbol %r" % t) from None

    @staticmethod
    def _items(src):
        out = []
        for raw in src.splitlines():
            ln = re.split(r"[;#]", raw, 1)[0].strip()
            while True:
                m = re.match(r"^([A-Za-z_.][\w.]*):\s*(.*)$", ln)
                if not m:
                    break
                out.append(("label", m.group(1)))
                ln = m.group(2).strip()
            if ln:
                out.append(("ins", ln))
        return out

    @staticmethod
    def _size(ins):
        op, _, rest = ins.partition(" ")
        if op == ".asciiz":
            s = _string(rest)
            return (len(s) + 1 + 3) // 4
        return 1

    def assemble(self, src):
        items = self._items(src)
        labels, pc = {}, self.base
        for kind, x in items:
            if kind == "label":
                if x in labels:
                    raise AsmError("duplicate label %r" % x)
                labels[x] = pc
            else:
                pc += 4 * self._size(x)
        self.labels = labels
        words, pc = [], self.base
        for kind, x in items:
            if kind == "label":
                continue
            w = self._encode(x, pc, labels)
            words.extend(w if isinstance(w, list) else [w])
            pc += 4 * self._size(x)
        return words

    def _encode(self, ins, pc, L):
        op, _, rest = ins.partition(" ")
        rest = rest.strip()
        args = [a.strip() for a in re.split(r",(?![^(]*\))", rest)] if rest else []

        def V(t):
            return self.value(t, L)

        def branch(t):
            off = (V(t) - (pc + 4)) >> 2
            if not -0x8000 <= off < 0x8000:
                raise AsmError("branch out of range: %s" % ins)
            return off & 0xFFFF

        if op == "nop":
            return 0
        if op == ".word":
            return V(args[0]) & 0xFFFFFFFF
        if op == ".asciiz":
            b = _string(rest) + b"\0"
            b += b"\0" * (-len(b) % 4)
            return [int.from_bytes(b[i:i + 4], "little") for i in range(0, len(b), 4)]
        if op == "move":
            return (_reg(args[1]) << 21) | (_reg(args[0]) << 11) | 0x2D
        if op == "li":
            v = V(args[1])
            if not -0x8000 <= v < 0x8000:
                raise AsmError("li needs a 16-bit value: %s" % ins)
            return (0x09 << 26) | (_reg(args[0]) << 16) | (v & 0xFFFF)
        if op == "lui":
            return (0x0F << 26) | (_reg(args[0]) << 16) | (V(args[1]) & 0xFFFF)
        if op in I_ARITH:
            return ((I_ARITH[op] << 26) | (_reg(args[1]) << 21)
                    | (_reg(args[0]) << 16) | (V(args[2]) & 0xFFFF))
        if op in MEM:
            m = re.fullmatch(r"(.*)\((.+)\)", args[1])
            if not m:
                raise AsmError("bad memory operand: %s" % ins)
            off = V(m.group(1) or "0")
            rt = int(args[0].lstrip("$f")) if op in ("lwc1", "swc1") else _reg(args[0])
            return (MEM[op] << 26) | (_reg(m.group(2)) << 21) | (rt << 16) | (off & 0xFFFF)
        if op in R3:
            return (_reg(args[1]) << 21) | (_reg(args[2]) << 16) | (_reg(args[0]) << 11) | R3[op]
        if op in SHIFT:
            return ((_reg(args[1]) << 16) | (_reg(args[0]) << 11)
                    | ((V(args[2]) & 31) << 6) | SHIFT[op])
        if op == "jr":
            return (_reg(args[0]) << 21) | 0x08
        if op == "jalr":
            return (_reg(args[0]) << 21) | (31 << 11) | 0x09
        if op in ("j", "jal"):
            t = V(args[0])
            if (t & 0xF0000000) != (pc & 0xF0000000) or t & 3:
                raise AsmError("bad jump target: %s" % ins)
            return ((2 if op == "j" else 3) << 26) | ((t >> 2) & 0x3FFFFFF)
        if op == "b":
            return (0x04 << 26) | branch(args[0])
        if op in ("beq", "bne"):
            return (((0x04 if op == "beq" else 0x05) << 26) | (_reg(args[0]) << 21)
                    | (_reg(args[1]) << 16) | branch(args[2]))
        if op in ("beqz", "bnez"):
            return ((0x04 if op == "beqz" else 0x05) << 26) | (_reg(args[0]) << 21) | branch(args[1])
        if op in ("blez", "bgtz"):
            return ((0x06 if op == "blez" else 0x07) << 26) | (_reg(args[0]) << 21) | branch(args[1])
        if op in ("bltz", "bgez"):
            return ((0x01 << 26) | (_reg(args[0]) << 21)
                    | ((0 if op == "bltz" else 1) << 16) | branch(args[1]))
        if op in ("mtc1", "mfc1"):
            return ((0x44800000 if op == "mtc1" else 0x44000000)
                    | (_reg(args[0]) << 16) | (_freg(args[1]) << 11))
        if op in FP_S:
            ft = _freg(args[2]) if len(args) > 2 else 0
            return (0x46000000 | (ft << 16) | (_freg(args[1]) << 11)
                    | (_freg(args[0]) << 6) | FP_S[op])
        if op == "sqrt.s":                  # R5900: SQRT.S fd, ft (fs = 0)
            return 0x46000000 | (_freg(args[1]) << 16) | (_freg(args[0]) << 6) | 0x04
        if op == "cvt.s.w":
            return 0x46800020 | (_freg(args[1]) << 11) | (_freg(args[0]) << 6)
        if op in ("c.lt.s", "c.le.s"):
            return (0x46000000 | (_freg(args[1]) << 16) | (_freg(args[0]) << 11)
                    | (0x34 if op == "c.lt.s" else 0x36))
        if op in ("bc1f", "bc1t"):
            return (0x45000000 if op == "bc1f" else 0x45010000) | branch(args[0])
        raise AsmError("unknown instruction %r" % ins)


def _string(lit):
    lit = lit.strip()
    if len(lit) < 2 or lit[0] != '"' or lit[-1] != '"':
        raise AsmError("bad string %r" % lit)
    return lit[1:-1].encode("latin-1")


def assemble(src, base, syms=None):
    """(words, labels) for `src` placed at `base`."""
    a = Asm(base, syms)
    words = a.assemble(src)
    return words, a.labels

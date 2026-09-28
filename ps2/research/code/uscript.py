"""An UnrealScript (UE2) bytecode disassembler for the Rainbow Six 3 packages.

Why this exists
---------------

The cooked `.LIN` keeps each package's header, name, import and export tables
verbatim from the uncooked package, and lifts the object DATA out -- see
`research/rs3ai/zones.md`. So no offset in any table points at anything, and
the bytecode has to be found by content.

It is findable, because two idioms in the stream are unmistakable:

    1F "BeginHere::BeginState" 00      EX_StringConst, NUL-terminated ASCII
    16 04 0B                           EndFunctionParms, Return, Nothing

The first is self-delimiting, which makes it a synchronisation point: wherever
one appears, the byte after the terminator is the start of a token. That is
what `anchors()` finds and what everything else is built on.

How the opcode table was checked
--------------------------------

Not taken on faith, and not by eye. The table below is the standard UE2 one;
what makes it right *for this build* is that it decodes the regions that hold
bytecode and fails on the regions that do not. Measured over `COMMON.LIN`:

    region                       anchors  6 tokens  12 tokens  24 tokens
    the four inter-package gaps     3106     75.1%      49.3%      25.2%
    a package's NAME TABLE            41      2.4%       2.4%         --

A thirty-fold separation against a control taken from the same file. The decay
with depth is expected rather than a defect: an anchor lands in the middle of
a block, so the deeper the decode the likelier it is to walk off the end of
that block into whatever the cook put next to it.

A decoded sample, from `COMMON.LIN` at 0x001015ec:

    LocalVariable(#7)
    IntConst(2449550592)
    VirtualFunction(#1, (StringConst("::BeginState")))
    LetBool(BoolVariable(InstanceVariable(#1066)), True)
    Return(Nothing)

which is `Log("::BeginState"); bSomething = true; return;` -- a state entry
announcing itself and setting a flag.

What it still cannot do
-----------------------

Resolve names. The `#1066` above is a compact index into the name table of
whichever package owns this code, and because the cook threw away the mapping
from object to data (see `zones.md`) there is nothing that says which package
that is. The indices are real and consistent; they are just unlabelled. A
future pass could recover the mapping statistically -- a block calling
`VirtualFunction(#n)` where #n resolves to a plausible function name in
exactly one package's table is strong evidence for that package.
"""

from __future__ import annotations

import re
import struct

# --- the token table -------------------------------------------------------
# name, then how to read the operands: a tuple of field kinds, where
#   "idx"  compact index        "u8"/"u16"/"u32"/"f32" fixed width
#   "str"  NUL-terminated ASCII "expr" a nested token
#   "exprs" tokens until EX_EndFunctionParms
OPS = {
    0x00: ("LocalVariable", ("idx",)),
    0x01: ("InstanceVariable", ("idx",)),
    0x02: ("DefaultVariable", ("idx",)),
    0x04: ("Return", ("expr",)),
    0x05: ("Switch", ("u8", "expr")),
    0x06: ("Jump", ("u16",)),
    0x07: ("JumpIfNot", ("u16", "expr")),
    0x08: ("Stop", ()),
    0x09: ("Assert", ("u16", "u8", "expr")),
    0x0A: ("Case", ("case",)),
    0x0B: ("Nothing", ()),
    0x0C: ("LabelTable", ("labels",)),
    0x0D: ("GotoLabel", ("expr",)),
    0x0E: ("EatReturnValue", ("idx",)),
    0x0F: ("Let", ("expr", "expr")),
    0x10: ("DynArrayElement", ("expr", "expr")),
    0x11: ("New", ("expr", "expr", "expr", "expr")),
    0x12: ("ClassContext", ("expr", "u16", "idx", "u8", "expr")),
    0x13: ("MetaCast", ("idx", "expr")),
    0x14: ("LetBool", ("expr", "expr")),
    0x16: ("EndFunctionParms", ()),
    0x17: ("Self", ()),
    0x18: ("Skip", ("u16", "expr")),
    0x19: ("Context", ("expr", "u16", "idx", "u8", "expr")),
    0x1A: ("ArrayElement", ("expr", "expr")),
    0x1B: ("VirtualFunction", ("idx", "exprs")),
    0x1C: ("FinalFunction", ("idx", "exprs")),
    0x1D: ("IntConst", ("u32",)),
    0x1E: ("FloatConst", ("f32",)),
    0x1F: ("StringConst", ("str",)),
    0x20: ("ObjectConst", ("idx",)),
    0x21: ("NameConst", ("idx",)),
    0x22: ("RotationConst", ("u32", "u32", "u32")),
    0x23: ("VectorConst", ("f32", "f32", "f32")),
    0x24: ("ByteConst", ("u8",)),
    0x25: ("IntZero", ()),
    0x26: ("IntOne", ()),
    0x27: ("True", ()),
    0x28: ("False", ()),
    0x29: ("NativeParm", ("idx",)),
    0x2A: ("NoObject", ()),
    0x2C: ("IntConstByte", ("u8",)),
    0x2D: ("BoolVariable", ("expr",)),
    0x2E: ("DynamicCast", ("idx", "expr")),
    0x2F: ("Iterator", ("expr", "u16")),
    0x30: ("IteratorPop", ()),
    0x31: ("IteratorNext", ()),
    0x32: ("StructCmpEq", ("idx", "expr", "expr")),
    0x33: ("StructCmpNe", ("idx", "expr", "expr")),
    0x36: ("StructMember", ("idx", "expr")),
    0x38: ("GlobalFunction", ("idx", "exprs")),
    0x39: ("RotatorToVector", ("expr",)),
    0x3A: ("ByteToInt", ("expr",)),
    0x34: ("UnicodeStringConst", ("wstr",)),
    0x35: ("StructMember35", ("idx", "expr")),
    0x37: ("DynArrayLength", ("expr",)),
    0x40: ("DelegateFunction", ("u8", "idx", "idx", "exprs")),
}
# 0x39..0x60 are the conversion opcodes; they all take one expression.
for _c in range(0x39, 0x60):
    OPS.setdefault(_c, ("Conv%02X" % _c, ("expr",)))

EX_END_FUNCTION_PARMS = 0x16


class Desync(Exception):
    """The stream stopped making sense -- a wrong table, or not bytecode."""


def compact(buf, pos):
    b = buf[pos]
    pos += 1
    neg = b & 0x80
    value = b & 0x3F
    if b & 0x40:
        shift = 6
        while True:
            c = buf[pos]
            pos += 1
            value |= (c & 0x7F) << shift
            shift += 7
            if not (c & 0x80):
                break
    return (-value if neg else value), pos


def token(data, pos, depth=0, end=None):
    """Decode one token. Returns (text, nextPos)."""
    if depth > 48 or pos >= len(data) or (end is not None and pos >= end):
        raise Desync("ran off the end")
    op = data[pos]
    pos += 1

    if op >= 0x60:                                  # a native function call
        if op < 0x70:
            if pos >= len(data):
                raise Desync("truncated extended native")
            native = ((op - 0x60) << 8) + data[pos]
            pos += 1
        else:
            native = op
        args = []
        while True:
            if pos >= len(data):
                raise Desync("unterminated native call")
            if data[pos] == EX_END_FUNCTION_PARMS:
                pos += 1
                break
            text, pos = token(data, pos, depth + 1, end)
            args.append(text)
        return "native%d(%s)" % (native, ", ".join(args)), pos

    if op not in OPS:
        raise Desync("unknown opcode %02X" % op)
    name, fields = OPS[op]
    parts = []
    for f in fields:
        if f == "idx":
            v, pos = compact(data, pos)
            parts.append("#%d" % v)
        elif f == "u8":
            parts.append(str(data[pos])); pos += 1
        elif f == "u16":
            parts.append("+0x%x" % struct.unpack_from("<H", data, pos)[0]); pos += 2
        elif f == "u32":
            parts.append(str(struct.unpack_from("<I", data, pos)[0])); pos += 4
        elif f == "f32":
            parts.append("%g" % struct.unpack_from("<f", data, pos)[0]); pos += 4
        elif f == "str":
            nul = data.find(b"\x00", pos)
            if nul < 0 or nul - pos > 4096:
                raise Desync("unterminated string constant")
            raw = data[pos:nul]
            if raw and not all(9 <= b < 127 for b in raw):
                raise Desync("string constant is not text")
            parts.append('"%s"' % raw.decode("latin-1"))
            pos = nul + 1
        elif f == "wstr":
            nul = data.find(bytes(2), pos)
            if nul < 0 or nul - pos > 8192:
                raise Desync("unterminated wide string")
            parts.append("L\"...\"")
            pos = nul + 2
        elif f == "expr":
            text, pos = token(data, pos, depth + 1, end)
            parts.append(text)
        elif f == "exprs":
            args = []
            while True:
                if pos >= len(data):
                    raise Desync("unterminated parm list")
                if data[pos] == EX_END_FUNCTION_PARMS:
                    pos += 1
                    break
                text, pos = token(data, pos, depth + 1, end)
                args.append(text)
            parts.append("(%s)" % ", ".join(args))
        elif f == "case":
            off = struct.unpack_from("<H", data, pos)[0]
            pos += 2
            if off == 0xFFFF:
                parts.append("default")
            else:
                text, pos = token(data, pos, depth + 1, end)
                parts.append("+0x%x %s" % (off, text))
        elif f == "labels":
            while True:
                v, pos = compact(data, pos)
                pos += 4
                parts.append("label#%d" % v)
                if v == 0 or len(parts) > 64:
                    break
    return "%s(%s)" % (name, ", ".join(parts)) if parts else name, pos


#: the anchor: a string constant whose text is plainly a script label
ANCHOR = re.compile(rb"\x1f([ -~]{4,96})\x00")


def anchors(data, lo=0, hi=None):
    """Positions just past each `EX_StringConst "text"` in a region."""
    hi = len(data) if hi is None else hi
    out = []
    for m in ANCHOR.finditer(data, lo, hi):
        out.append(m.end())
    return out


def run(data, pos, limit=64, end=None, strict=True):
    """Decode up to `limit` tokens from `pos`. Returns (lines, nextPos).

    `strict` raises on the first desync, which is what `validate` needs to
    measure. With it off, decoding stops at the desync and returns what it
    read -- which is what a person reading a listing wants, because an anchor
    lands mid-block and running off the end of that block is normal.
    """
    lines = []
    for _ in range(limit):
        start = pos
        try:
            text, pos = token(data, pos, 0, end)
        except (Desync, IndexError, struct.error) as exc:
            if strict:
                raise
            lines.append((start, "<end of block: %s>" % exc))
            break
        lines.append((start, text))
        if text in ("Stop", "Nothing"):
            break
    return lines, pos


def validate(data, regions, probes=4000, depth=12):
    """How often does decoding from an anchor stay coherent?

    The measure is deliberately blunt: from each anchor, decode `depth`
    tokens. A correct opcode table survives; a wrong one raises Desync almost
    immediately. Returns (clean, tried).
    """
    clean = tried = 0
    for lo, hi in regions:
        for at in anchors(data, lo, hi)[:probes]:
            tried += 1
            try:
                run(data, at, depth, hi)
                clean += 1
            except (Desync, IndexError, struct.error):
                pass
    return clean, tried


def _main(argv):
    """python uscript.py <disc.iso> <package.LIN> [start-offset-hex]"""
    import sys
    sys.path.insert(0, __file__.rsplit("research", 1)[0])
    from tcps2.iso import Iso
    from tcps2 import vokes, lin
    if len(argv) < 3:
        print(_main.__doc__)
        return 2
    with Iso(argv[1]) as iso:
        for arc in vokes.open_archives(iso, r"/VOKES\d\.IMG$"):
            if argv[2].upper() in arc.files:
                data = lin.decompress(arc.read_entry(arc.files[argv[2].upper()]))
                break
        else:
            print("no such package")
            return 1
    if len(argv) > 3:
        at = int(argv[3], 16)
        lines, _ = run(data, at, 40, strict=False)
        for pos, text in lines:
            print("%08x  %s" % (pos, text))
        return 0
    found = anchors(data)
    print("%d string-constant anchors" % len(found))
    for at in found[:20]:
        try:
            lines, _ = run(data, at, 6)
        except Desync:
            continue
        print("\n%08x" % at)
        for pos, text in lines:
            print("   %08x  %s" % (pos, text))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(_main(sys.argv))

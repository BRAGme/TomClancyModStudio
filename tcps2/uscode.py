"""UnrealScript bytecode inside a cooked Rainbow Six 3 package: read and rewrite.

Why this is not just a hex edit
-------------------------------

A script block is stored as a 4-byte length followed by bytecode::

    <u32 ScriptSize> <bytecode ...>

and **`ScriptSize` is the length the bytecode will have IN MEMORY, not on
disk.** The loader runs `while (iCode < ScriptSize) SerializeExpr(...)`,
converting as it reads: an object, property, function or name reference is a
1-to-5 byte `FCompactIndex` in the file and a flat 4 bytes once loaded. So the
file is shorter than the loaded image -- measured over this package, 503,021
disk bytes become 688,623 in memory, a factor of 1.369.

Everything else follows from that:

* **Jump operands are memory offsets.** `EX_Jump`, `EX_JumpIfNot`, the "next
  case" word of `EX_Case`, `EX_Iterator` and the DWORDs in an `EX_LabelTable`
  all index the loaded array, so inserting a single byte anywhere moves every
  downstream target -- by the MEMORY delta, which is not the disk delta.
* **`EX_Context`, `EX_ClassContext` and `EX_Skip` carry a size, not a target.**
  Their word is how many bytes to step over, so it has to be re-measured rather
  than re-based. `EX_Assert`'s word is a line number and must not be touched at
  all. Treating all three alike is the obvious way to corrupt a function.
* **The disk length must not change**, because a `.LIN` package's byte length is
  fixed (see `tcps2/lin.py`). The memory length *may* change, as long as the
  `ScriptSize` word in front of the block is updated -- it is a plain 4-byte
  int, so rewriting it costs nothing.

So an edit is: parse to a token tree, change the tree, re-emit, re-measure every
size, re-base every jump, write the new `ScriptSize`, and pad the disk back to
its original length with `EX_Nothing` after the final return.

How the encoding was established
--------------------------------

Not from documentation. A PCSX2 savestate gives the loaded image of every
script struct (`UFunction +0x40` is the Script pointer and `+0x44` its length),
so the disk parse can be checked against what the console actually holds. This
module's model rebuilds the in-memory image from the file and compares it byte
for byte, ignoring only the 4-byte reference slots whose values are heap
pointers: **3,710 live script structs reconstruct exactly, with zero
non-reference bytes differing.** The residue is 656 one and two-byte stubs too
short to locate unambiguously, plus classes that live in another package.

`tests/run_tests.py` re-proves the weaker but still decisive half of that
without a savestate: every block in the package round-trips parse -> assemble
back to identical disk bytes and an identical `ScriptSize`.
"""

from __future__ import annotations

import struct

# ---------------------------------------------------------------------------
# FCompactIndex
# ---------------------------------------------------------------------------

def compact_decode(buf, pos):
    """-> (value, byteLength). Sign in bit 7 of byte 0, continue in bit 6/7."""
    b = buf[pos]
    n = 1
    value = b & 0x3F
    if b & 0x40:
        shift = 6
        while True:
            nxt = buf[pos + n]
            n += 1
            value |= (nxt & 0x7F) << shift
            shift += 7
            if not (nxt & 0x80):
                break
    return (-value if b & 0x80 else value), n


def compact_encode(value):
    """The shortest FCompactIndex for a value. Round-trips `compact_decode`."""
    neg = value < 0
    v = -value if neg else value
    first = (0x80 if neg else 0) | (v & 0x3F)
    v >>= 6
    if not v:
        return bytes([first])
    out = bytearray([first | 0x40])
    while True:
        byte = v & 0x7F
        v >>= 7
        if v:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


# ---------------------------------------------------------------------------
# the opcode table
# ---------------------------------------------------------------------------
#
# Field kinds:
#   ref    an object/property/function/name reference: compact on disk, 4 in RAM
#   u8 u16 u32 f32   fixed width, identical in both
#   jump   a WORD holding an absolute MEMORY offset -- must be re-based
#   jump32 a DWORD holding an absolute MEMORY offset (label tables)
#   skip   a WORD holding the SIZE of what follows -- must be re-measured
#   line   a WORD that is a source line number, not an offset -- leave alone
#   expr   one nested expression
#   exprs  nested expressions terminated by EX_EndFunctionParms
#   case   a jump WORD, then an expression unless the word is 0xFFFF
#   labels (ref, jump32) pairs until the reference is 0 ("None")

OPS = {
    0x00: ("LocalVariable", ("ref",)),
    0x01: ("InstanceVariable", ("ref",)),
    0x02: ("DefaultVariable", ("ref",)),
    0x04: ("Return", ("expr",)),
    0x05: ("Switch", ("u8", "expr")),
    0x06: ("Jump", ("jump",)),
    0x07: ("JumpIfNot", ("jump", "expr")),
    0x08: ("Stop", ()),
    0x09: ("Assert", ("line", "u8", "expr")),
    0x0A: ("Case", ("case",)),
    0x0B: ("Nothing", ()),
    0x0C: ("LabelTable", ("labels",)),
    0x0D: ("GotoLabel", ("expr",)),
    0x0E: ("EatReturnValue", ("ref",)),
    0x0F: ("Let", ("expr", "expr")),
    0x10: ("DynArrayElement", ("expr", "expr")),
    0x11: ("New", ("expr", "expr", "expr", "expr")),
    0x12: ("ClassContext", ("expr", "skip", "u8", "expr")),
    0x13: ("MetaCast", ("ref", "expr")),
    0x14: ("LetBool", ("expr", "expr")),
    0x16: ("EndFunctionParms", ()),
    0x17: ("Self", ()),
    0x18: ("Skip", ("skip", "expr")),
    0x19: ("Context", ("expr", "skip", "u8", "expr")),
    0x1A: ("ArrayElement", ("expr", "expr")),
    0x1B: ("VirtualFunction", ("ref", "exprs")),
    0x1C: ("FinalFunction", ("ref", "exprs")),
    0x1D: ("IntConst", ("u32",)),
    0x1E: ("FloatConst", ("f32",)),
    0x1F: ("StringConst", ("str",)),
    0x20: ("ObjectConst", ("ref",)),
    0x21: ("NameConst", ("ref",)),
    0x22: ("RotationConst", ("u32", "u32", "u32")),
    0x23: ("VectorConst", ("f32", "f32", "f32")),
    0x24: ("ByteConst", ("u8",)),
    0x25: ("IntZero", ()),
    0x26: ("IntOne", ()),
    0x27: ("True", ()),
    0x28: ("False", ()),
    0x29: ("NativeParm", ("ref",)),
    0x2A: ("NoObject", ()),
    0x2C: ("IntConstByte", ("u8",)),
    0x2D: ("BoolVariable", ("expr",)),
    0x2E: ("DynamicCast", ("ref", "expr")),
    0x2F: ("Iterator", ("expr", "jump")),
    0x30: ("IteratorPop", ()),
    0x31: ("IteratorNext", ()),
    0x32: ("StructCmpEq", ("ref", "expr", "expr")),
    0x33: ("StructCmpNe", ("ref", "expr", "expr")),
    0x34: ("UnicodeStringConst", ("wstr",)),
    0x35: ("StructMember35", ("ref", "expr")),
    0x36: ("StructMember", ("ref", "expr")),
    0x37: ("DynArrayLength", ("expr",)),
    0x38: ("GlobalFunction", ("ref", "exprs")),
    0x40: ("DelegateFunction", ("u8", "ref", "ref", "exprs")),
}
#: 0x39-0x5F are the conversion opcodes, each taking one expression.
for _c in range(0x39, 0x60):
    OPS.setdefault(_c, ("Conv%02X" % _c, ("expr",)))

FIXED = {"u8": 1, "u16": 2, "u32": 4, "f32": 4, "jump": 2, "skip": 2, "line": 2,
         "jump32": 4}

EX_END_FUNCTION_PARMS = 0x16
EX_NOTHING = 0x0B
EX_RETURN = 0x04


class ScriptError(Exception):
    pass


# ---------------------------------------------------------------------------
# tokens
# ---------------------------------------------------------------------------

class Tok:
    """One expression. `parts` mirrors the opcode's field list.

    A part is `(kind, value)` where value is the raw disk bytes for a fixed
    field, the original compact bytes for a `ref`, a target `Tok` (or the END
    sentinel) for a jump, a `Tok` for a nested expression, or a list of `Tok`
    for `exprs`/`labels`.
    """

    __slots__ = ("op", "native2", "parts", "mstart", "mlen", "dlen", "skip_base")

    def __init__(self, op, native2=None):
        self.op = op
        self.native2 = native2          # second byte of a two-byte native index
        self.parts = []
        self.mstart = None
        self.mlen = 0
        self.dlen = 0
        #: for a token carrying a skip word: (storedValue, measuredFollowing) as
        #: they were on disc, so the word can be ADJUSTED by however much the
        #: guarded expression changed rather than recomputed from scratch. The
        #: two agree for 99.5% of the package, but about seventy of the disc's
        #: own skips store something else -- short-circuit chains where the
        #: compiler jumped somewhere shorter than the whole expression. Those
        #: are none of this module's business unless an edit moves them.
        self.skip_base = None

    @property
    def name(self):
        if self.op >= 0x60:
            return "native"
        return OPS.get(self.op, ("op%02X" % self.op, ()))[0]

    def walk(self):
        """Self, then every nested token, depth first."""
        yield self
        for kind, val in self.parts:
            if kind == "expr":
                yield from val.walk()
            elif kind in ("exprs", "labels"):
                for t in val:
                    if isinstance(t, Tok):
                        yield from t.walk()
            elif kind == "case" and isinstance(val, tuple) and val[1] is not None:
                yield from val[1].walk()


#: jump target meaning "one past the last byte of the script"
END = object()


class Script:
    """A parsed script block: the statements, and how to put them back."""

    def __init__(self, toks, disk_len, mem_len):
        self.toks = toks
        self.disk_len = disk_len        # the extent this MUST be written back into
        self.mem_len = mem_len

    # -- reading ----------------------------------------------------------
    @classmethod
    def parse(cls, buf, disk_start, mem_size):
        """Parse a block whose loaded length is `mem_size`."""
        toks = []
        dp, mp = disk_start, 0
        # Anything malformed -- a truncated operand, a string with no
        # terminator, an index past the end -- comes back as ScriptError, so a
        # caller sweeping a package has exactly one exception type to catch.
        try:
            while mp < mem_size:
                tok, dp, mp = _parse_one(buf, dp, mp, 0)
                toks.append(tok)
        except ScriptError:
            raise
        except (IndexError, ValueError, struct.error) as exc:
            raise ScriptError("malformed script block: %s" % exc) from exc
        if mp != mem_size:
            raise ScriptError("block overran its declared size: %d vs %d"
                              % (mp, mem_size))
        script = cls(toks, dp - disk_start, mp)
        script._resolve_jumps()
        return script

    @classmethod
    def at(cls, buf, size_at):
        """Parse the block whose ScriptSize word sits at `size_at`."""
        mem_size = struct.unpack_from("<I", buf, size_at)[0]
        return cls.parse(buf, size_at + 4, mem_size)

    def _index(self):
        by_mem = {}
        for t in self.statements():
            by_mem[t.mstart] = t
        return by_mem

    def statements(self):
        for t in self.toks:
            yield from t.walk()

    def _resolve_jumps(self):
        """Turn absolute memory offsets into references to the target token."""
        by_mem = self._index()
        for t in self.statements():
            for i, (kind, val) in enumerate(t.parts):
                if kind == "jump":
                    off = struct.unpack_from("<H", val, 0)[0]
                    t.parts[i] = (kind, self._target(by_mem, off))
                elif kind == "jump32":
                    off = struct.unpack_from("<I", val, 0)[0]
                    t.parts[i] = (kind, self._target(by_mem, off))
                elif kind == "case":
                    off, sub = val
                    if off == 0xFFFF:
                        t.parts[i] = (kind, (0xFFFF, sub))
                    else:
                        t.parts[i] = (kind, (self._target(by_mem, off), sub))

    def _target(self, by_mem, off):
        # Exactly one-past-the-end is a real target -- it is how the compiler
        # spells "jump to the end of the function". Anything beyond that is not
        # a jump at all, and silently clamping it would rewrite a word this
        # module does not understand.
        if off == self.mem_len:
            return END
        tok = by_mem.get(off)
        if tok is None:
            raise ScriptError("jump to 0x%x is not a token boundary in a "
                              "%d-byte block" % (off, self.mem_len))
        return tok

    # -- editing ----------------------------------------------------------
    def targets(self):
        """Every token that something jumps to."""
        out = set()
        for t in self.statements():
            for kind, val in t.parts:
                if kind in ("jump", "jump32") and val is not END:
                    out.add(id(val))
                elif kind == "case":
                    off, _sub = val
                    if off not in (0xFFFF,) and off is not END:
                        out.add(id(off))
        return out

    def remove(self, toks):
        """Drop top-level statements, refusing if anything jumps into them.

        Removing a statement that is a jump target would leave a jump pointing
        at whatever happened to follow it, which is the kind of edit that
        produces a game that runs for ten minutes and then does something
        inexplicable. So it is refused rather than fixed up.
        """
        doomed = {id(t) for tok in toks for t in tok.walk()}
        landed = self.targets() & doomed
        if landed:
            raise ScriptError("refusing to remove a statement that is a jump "
                              "target")
        keep = [t for t in self.toks if id(t) not in {id(x) for x in toks}]
        if len(keep) != len(self.toks) - len(toks):
            raise ScriptError("a statement to remove was not a top-level one")
        self.toks = keep

    def statement_at(self, mstart):
        """The top-level statement beginning at this memory offset."""
        for t in self.toks:
            if t.mstart == mstart:
                return t
        raise ScriptError("no top-level statement at 0x%x" % mstart)

    # -- writing ----------------------------------------------------------
    def assemble(self, disk_len=None):
        """-> (diskBytes, memSize). Sizes and jumps are recomputed.

        `disk_len` pads the result to that many bytes with `EX_Nothing`, which
        is what keeps a LIN package's length fixed. Padding lands after the last
        statement, so it is never executed; it still has to be valid bytecode,
        because the loader decodes every byte it is told the block contains.
        """
        out = bytearray()
        patches = []            # (diskPos, kind, value) filled in on pass two
        mp = 0
        for t in self.toks:
            mp = _emit(t, out, patches, mp)
        mem_len = mp
        if disk_len is None:
            disk_len = len(out)
        pad = disk_len - len(out)
        if pad < 0:
            raise ScriptError("assembled script is %d bytes, %d too many for "
                              "its slot" % (len(out), -pad))
        out += bytes([EX_NOTHING]) * pad
        mem_len += pad
        for dpos, kind, val in patches:
            if kind == "jump":
                struct.pack_into("<H", out, dpos, _mem_of(val, mem_len))
            elif kind == "jump32":
                struct.pack_into("<I", out, dpos, _mem_of(val, mem_len))
            elif kind == "case":
                struct.pack_into("<H", out, dpos,
                                 0xFFFF if val == 0xFFFF else _mem_of(val, mem_len))
        return bytes(out), mem_len

    def write_into(self, buf, size_at):
        """Rewrite the block in `buf` (a bytearray) in place, length preserved."""
        disk, mem = self.assemble(self.disk_len)
        struct.pack_into("<I", buf, size_at, mem)
        buf[size_at + 4:size_at + 4 + self.disk_len] = disk
        return mem


def find_blocks(buf, lo=4, hi=60000):
    """Offsets of every `<u32 memSize><bytecode>` block that parses exactly.

    A cooked package keeps no index of where its script went (the export
    table's offsets describe the file before cooking), so blocks have to be
    found by content. The test is strict enough to be trustworthy on its own:
    the declared length must be reached exactly, on a token boundary, by a
    parse that never sees an unknown opcode.

    Greedy -- on a hit it resumes past the block -- so a false positive can
    hide a real block behind it. That is the right trade for a sweep; when a
    specific function is wanted, locate it by content and parse just that one.
    """
    out = []
    i, n = 0, len(buf) - 8
    while i < n:
        want = struct.unpack_from("<I", buf, i)[0]
        if lo <= want <= hi:
            try:
                mp, dp = 0, i + 4
                while mp < want:
                    _t, dp, mp = _parse_one(buf, dp, mp, 0)
                if mp == want:
                    out.append(i)
                    i = dp
                    continue
            except Exception:
                pass
        i += 1
    return out


def parse_expr(raw):
    """Parse one self-contained expression from raw disk bytes.

    This is how new code is authored: write the bytecode, then run it through
    the same parser the disc goes through, so a fragment cannot disagree with
    the reader about its own encoding. It must contain no jumps -- a fragment
    has no block to resolve them against -- and must consume every byte given.
    """
    try:
        tok, dp, _mp = _parse_one(raw, 0, 0, 0)
    except ScriptError:
        raise
    except (IndexError, ValueError, struct.error) as exc:
        raise ScriptError("malformed fragment: %s" % exc) from exc
    if dp != len(raw):
        raise ScriptError("fragment has %d trailing bytes" % (len(raw) - dp))
    for t in tok.walk():
        for kind, _val in t.parts:
            if kind in ("jump", "jump32", "case", "labels"):
                raise ScriptError("a fragment may not contain jumps")
    return tok


def _mem_of(target, mem_len):
    if target is END:
        return mem_len
    if target.mstart is None:
        raise ScriptError("jump target was not emitted")
    return target.mstart


# ---------------------------------------------------------------------------
# parse / emit
# ---------------------------------------------------------------------------

def _parse_one(buf, dp, mp, depth):
    if depth > 90:
        raise ScriptError("expression nested too deeply")
    start_d, start_m = dp, mp
    op = buf[dp]
    dp += 1
    mp += 1
    if op >= 0x60:
        tok = Tok(op)
        if op < 0x70:                      # two-byte native index
            tok.native2 = buf[dp]
            dp += 1
            mp += 1
        kids = []
        while buf[dp] != EX_END_FUNCTION_PARMS:
            k, dp, mp = _parse_one(buf, dp, mp, depth + 1)
            kids.append(k)
        dp += 1
        mp += 1
        tok.parts.append(("exprs", kids))
        tok.mstart, tok.mlen, tok.dlen = start_m, mp - start_m, dp - start_d
        return tok, dp, mp

    if op not in OPS:
        raise ScriptError("unknown opcode 0x%02X at 0x%x" % (op, start_d))
    tok = Tok(op)
    for kind in OPS[op][1]:
        if kind == "ref":
            _v, n = compact_decode(buf, dp)
            tok.parts.append(("ref", buf[dp:dp + n]))
            dp += n
            mp += 4
        elif kind in FIXED:
            n = FIXED[kind]
            tok.parts.append((kind, buf[dp:dp + n]))
            dp += n
            mp += n
        elif kind == "str":
            end = buf.index(b"\0", dp)
            tok.parts.append(("str", buf[dp:end + 1]))
            mp += end + 1 - dp
            dp = end + 1
        elif kind == "wstr":
            end = dp
            while buf[end] or buf[end + 1]:
                end += 2
            tok.parts.append(("wstr", buf[dp:end + 2]))
            mp += end + 2 - dp
            dp = end + 2
        elif kind == "expr":
            k, dp, mp = _parse_one(buf, dp, mp, depth + 1)
            tok.parts.append(("expr", k))
        elif kind == "exprs":
            kids = []
            while buf[dp] != EX_END_FUNCTION_PARMS:
                k, dp, mp = _parse_one(buf, dp, mp, depth + 1)
                kids.append(k)
            dp += 1
            mp += 1
            tok.parts.append(("exprs", kids))
        elif kind == "case":
            off = struct.unpack_from("<H", buf, dp)[0]
            dp += 2
            mp += 2
            sub = None
            if off != 0xFFFF:
                sub, dp, mp = _parse_one(buf, dp, mp, depth + 1)
            tok.parts.append(("case", (off, sub)))
        elif kind == "labels":
            rows = []
            while True:
                v, n = compact_decode(buf, dp)
                ref = buf[dp:dp + n]
                dp += n
                mp += 4
                off = buf[dp:dp + 4]
                dp += 4
                mp += 4
                rows.append((ref, off))
                if v == 0:
                    break
            tok.parts.append(("labels", rows))
        else:
            raise ScriptError("unhandled field kind %r" % kind)
    tok.mstart, tok.mlen, tok.dlen = start_m, mp - start_m, dp - start_d
    _note_skip(tok)
    return tok, dp, mp


def _note_skip(tok):
    """Record (stored, following) for a skip word, as the disc has it."""
    for i, (kind, val) in enumerate(tok.parts):
        if kind != "skip":
            continue
        stored = struct.unpack_from("<H", val, 0)[0]
        tok.skip_base = (stored, _following(tok, i))
        return


def _following(tok, i):
    """Memory bytes emitted after part `i` within this token."""
    n = 0
    for kind, val in tok.parts[i + 1:]:
        if kind == "expr":
            n += val.mlen
        elif kind == "ref":
            n += 4
        elif kind in FIXED:
            n += FIXED[kind]
        elif kind in ("str", "wstr"):
            n += len(val)
    return n


def _emit(tok, out, patches, mp):
    start_m = mp
    tok.mstart = mp
    out.append(tok.op)
    mp += 1
    if tok.native2 is not None:
        out.append(tok.native2)
        mp += 1
    for idx, (kind, val) in enumerate(tok.parts):
        if kind == "ref":
            out += val
            mp += 4
        elif kind in ("u8", "u16", "u32", "f32", "line"):
            out += val
            mp += FIXED[kind]
        elif kind in ("str", "wstr"):
            out += val
            mp += len(val)
        elif kind in ("jump", "jump32"):
            patches.append((len(out), kind, val))
            n = FIXED[kind]
            out += bytes(n)
            mp += n
        elif kind == "skip":
            # re-measured below, once the guarded expression has been emitted
            here = len(out)
            out += b"\0\0"
            mp += 2
            skip_at, skip_from = here, mp
            # the remaining parts of THIS token are what is skipped over
            for k2, v2 in tok.parts[idx + 1:]:
                mp = _emit_part(k2, v2, out, patches, mp, tok)
            now = mp - skip_from
            if tok.skip_base is not None:
                stored, before = tok.skip_base
                value = stored + (now - before)
            else:
                value = now + SKIP_ADJUST.get(tok.op, 0)
            if not 0 <= value <= 0xFFFF:
                raise ScriptError("skip word out of range: %d" % value)
            struct.pack_into("<H", out, skip_at, value)
            tok.mlen = mp - start_m
            return mp
        elif kind == "expr":
            mp = _emit(val, out, patches, mp)
        elif kind == "exprs":
            for k in val:
                mp = _emit(k, out, patches, mp)
            out.append(EX_END_FUNCTION_PARMS)
            mp += 1
        elif kind == "case":
            off, sub = val
            patches.append((len(out), "case", off))
            out += b"\0\0"
            mp += 2
            if sub is not None:
                mp = _emit(sub, out, patches, mp)
        elif kind == "labels":
            for ref, off in val:
                out += ref
                mp += 4
                out += off
                mp += 4
        else:
            raise ScriptError("cannot emit field kind %r" % kind)
    tok.mlen = mp - start_m
    return mp


#: What each skip word counts, relative to the bytes emitted after it. Measured
#: across every skip in the package rather than taken from the engine source:
#:
#:   Context      0x19   13,900 instances agree on -1
#:   ClassContext 0x12      119 instances agree on -1
#:   Skip         0x18    2,458 instances agree on +1
#:
#: The -1 on the two contexts is the `bSize` byte, which sits between the word
#: and the guarded expression and is not part of what gets stepped over -- so
#: the stored value is exactly the guarded expression's length. `EX_Skip` has no
#: such byte and stores one MORE than its expression; that is what the disc
#: does, and every instance agrees, so it is encoded here as a fact rather than
#: explained. The stragglers in the measurement all sit in blocks that fail to
#: round-trip for other reasons, i.e. false positives of the block scanner.
SKIP_ADJUST = {0x12: -1, 0x19: -1, 0x18: +1}


def _emit_part(kind, val, out, patches, mp, tok):
    if kind in ("u8", "u16", "u32", "f32", "line"):
        out += val
        return mp + FIXED[kind]
    if kind == "expr":
        return _emit(val, out, patches, mp)
    if kind == "ref":
        out += val
        return mp + 4
    raise ScriptError("unexpected field %r after a skip" % kind)

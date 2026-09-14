"""Shared helpers for RS3 PS2 SP.SOZ static analysis."""
import struct, os, sys, re

BASE = 0x00100000
HERE = os.path.dirname(os.path.abspath(__file__))


def _load_image():
    """Return the decompressed stock SP.SOZ overlay.

    Looks for sp.bin next to this file or at $RS3_SPBIN; otherwise unpacks it
    from the stock container with the repo's own tcps2.soz reader.
    """
    import hashlib
    for cand in (os.environ.get("RS3_SPBIN"), os.path.join(HERE, "sp.bin")):
        if cand and os.path.exists(cand):
            return open(cand, "rb").read()
    soz = os.environ.get(
        "RS3_SPSOZ",
        r"E:\PS2 Games\.tcms-backup\Tom Clancy's Rainbow Six 3 (USA)\SP.SOZ.orig",
    )
    if not os.path.exists(soz):
        raise SystemExit(
            "sp.bin not found. Put the decompressed stock overlay beside r6.py, "
            "or set RS3_SPBIN, or set RS3_SPSOZ to a stock SP.SOZ."
        )
    sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
    from tcps2.soz import SozImage
    img = SozImage.unpack(open(soz, "rb").read(), 0x00100000)
    h = hashlib.sha1(img.image).hexdigest()
    if h != "e9bb12138a1e69d551ac9f6b958114e5b2e830da":
        print("WARNING: overlay sha1 %s is not the stock image" % h, file=sys.stderr)
    return img.image


D = _load_image()
N = len(D)

REG = ['zero','at','v0','v1','a0','a1','a2','a3','t0','t1','t2','t3','t4','t5','t6','t7',
       's0','s1','s2','s3','s4','s5','s6','s7','t8','t9','k0','k1','gp','sp','fp','ra']

GP = 0x0065b6f0

try:
    from capstone import *
    _md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN)
    HAVE_CS = True
except Exception:
    HAVE_CS = False


def w(va):
    return struct.unpack_from("<I", D, va - BASE)[0]


def cstr(va, maxlen=120):
    o = va - BASE
    if not (0 <= o < N):
        return None
    e = D.find(b"\0", o)
    if e < 0 or e - o > maxlen:
        return None
    s = D[o:e]
    if not s:
        return None
    if all(32 <= c < 127 for c in s):
        return s.decode()
    return None


def dis1(va):
    off = va - BASE
    word = struct.unpack_from("<I", D, off)[0]
    op = word >> 26
    rs, rt = (word >> 21) & 31, (word >> 16) & 31
    imm = word & 0xFFFF
    simm = imm - 0x10000 if imm & 0x8000 else imm
    if op == 0x1F:
        return f"sq        ${REG[rt]}, {simm}(${REG[rs]})"
    if op == 0x1E:
        return f"lq        ${REG[rt]}, {simm}(${REG[rs]})"
    if HAVE_CS:
        g = list(_md.disasm(D[off:off + 4], va))
        if g:
            return f"{g[0].mnemonic:9s} {g[0].op_str}"
    return f".word     0x{word:08x}"


def disasm(start, end, strings=True):
    out = []
    lui = {}
    for off in range(start - BASE, end - BASE, 4):
        va = off + BASE
        word = struct.unpack_from("<I", D, off)[0]
        op = word >> 26
        rs, rt = (word >> 21) & 31, (word >> 16) & 31
        imm = word & 0xFFFF
        simm = imm - 0x10000 if imm & 0x8000 else imm
        txt = dis1(va)
        note = ""
        if op == 0x0F:
            lui[rt] = imm << 16
        elif op in (0x09, 0x0D) and rs in lui:
            a = (lui[rs] + (simm if op == 0x09 else imm)) & 0xFFFFFFFF
            s = cstr(a) if strings else None
            note = "   ; 0x%08x" % a + (f' "{s}"' if s else "")
            lui[rt] = a
        # gp-relative
        if op in (0x23, 0x2B, 0x21, 0x25, 0x20, 0x24, 0x27, 0x2F, 0x31, 0x39, 0x37, 0x3F) and rs == 28:
            note += "   ; gp%+d = 0x%08x" % (simm, (GP + simm) & 0xFFFFFFFF)
        out.append(f"{va:08x}  {txt}{note}")
    return out


def pr(start, end, strings=True):
    print("\n".join(disasm(start, end, strings)))


# ---------- function boundary helpers ----------

def func_start(va, limit=0x4000):
    """Walk back to a plausible function start: after a `jr $ra` + delay slot."""
    a = va
    while a > BASE + 8 and va - a < limit:
        a -= 4
        if w(a) == 0x03E00008:  # jr $ra
            return a + 8
    return None


def func_end(va, limit=0x8000):
    a = va
    while a < BASE + N - 8 and a - va < limit:
        if w(a) == 0x03E00008:
            return a + 8
        a += 4
    return None


# ---------- scanners ----------

def scan_mem(opcodes, offset, base_exclude=(0, 28, 29, 30)):
    """Find lw/sw/lbu/... with a given immediate offset. opcodes is a set of op values."""
    hits = []
    for off in range(0, N - 3, 4):
        word = struct.unpack_from("<I", D, off)[0]
        op = word >> 26
        if op not in opcodes:
            continue
        if (word & 0xFFFF) != (offset & 0xFFFF):
            continue
        rs = (word >> 21) & 31
        if rs in base_exclude:
            continue
        hits.append(off + BASE)
    return hits


OP_LW, OP_SW, OP_LBU, OP_SB, OP_LHU, OP_LWC1, OP_SWC1 = 0x23, 0x2B, 0x24, 0x28, 0x25, 0x31, 0x39


def find_float(val):
    """Return list of VAs where the 4-byte IEEE float appears (word-aligned)."""
    b = struct.pack("<f", val)
    out = []
    i = 0
    while True:
        i = D.find(b, i)
        if i < 0:
            break
        if i % 4 == 0:
            out.append(i + BASE)
        i += 1
    return out


def find_bytes(b, align=1):
    out = []
    i = 0
    while True:
        i = D.find(b, i)
        if i < 0:
            break
        if i % align == 0:
            out.append(i + BASE)
        i += 1
    return out


def find_lui_addiu(target):
    """Find lui/addiu (or ori) pairs forming `target` anywhere (simple window scan)."""
    hi = (target >> 16) & 0xFFFF
    lo = target & 0xFFFF
    if lo & 0x8000:
        hi = (hi + 1) & 0xFFFF
    out = []
    for off in range(0, N - 3, 4):
        word = struct.unpack_from("<I", D, off)[0]
        if (word >> 26) != 0x0F:
            continue
        if (word & 0xFFFF) != hi:
            continue
        rt = (word >> 16) & 31
        for k in range(1, 12):
            o2 = off + 4 * k
            if o2 + 4 > N:
                break
            w2 = struct.unpack_from("<I", D, o2)[0]
            op2 = w2 >> 26
            if op2 in (0x09, 0x0D) and ((w2 >> 21) & 31) == rt and (w2 & 0xFFFF) == lo:
                out.append((off + BASE, o2 + BASE))
                break
            # any load/store with this base and matching lo counts too
            if op2 in (OP_LW, OP_SW, OP_LBU, OP_SB, OP_LWC1, OP_SWC1) and ((w2 >> 21) & 31) == rt and (w2 & 0xFFFF) == lo:
                out.append((off + BASE, o2 + BASE))
                break
    return out


def find_strings(pat, min_len=4):
    """Find ASCII strings matching regex pat."""
    rx = re.compile(pat.encode() if isinstance(pat, str) else pat)
    out = []
    for m in re.finditer(rb"[\x20-\x7e]{%d,}" % min_len, D):
        if rx.search(m.group()):
            out.append((m.start() + BASE, m.group().decode("latin1")))
    return out


def callers(target):
    """Find jal <target>."""
    jal = 0x0C000000 | ((target & 0x0FFFFFFF) >> 2)
    out = []
    for off in range(0, N - 3, 4):
        if struct.unpack_from("<I", D, off)[0] == jal:
            out.append(off + BASE)
    return out


def jumps_to(target):
    j = 0x08000000 | ((target & 0x0FFFFFFF) >> 2)
    out = []
    for off in range(0, N - 3, 4):
        if struct.unpack_from("<I", D, off)[0] == j:
            out.append(off + BASE)
    return out

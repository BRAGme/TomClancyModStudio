#!/usr/bin/env python3
"""rsetool.py - shared analysis helpers for the Red Storm Engine PS2 ELFs.

    python rsetool.py strings  gr|js|soaf|offline|online  [minlen]     -> VA<TAB>string
    python rsetool.py xref     gr|js|soaf|offline|online  <VA-hex>     -> code sites forming that address
    python rsetool.py grepstr  gr|js|soaf|offline|online  <regex>      -> matching strings + xrefs
    python rsetool.py sym      <regex>                            -> Ghost Recon symbols matching
    python rsetool.py dis      gr|js|soaf|offline|online <VA-hex> [n]  -> R5900-aware disassembly
    python rsetool.py word     gr|js|soaf|offline|online <VA-hex>      -> the 32-bit word at VA

Address model
-------------
  gr       SLUS_206.13     VA = fileoff + 0x00100000 - 0x80
  js       SLUS_208.20     VA = fileoff + 0x00100000 - 0x100
  soaf     SLES_511.80     VA = fileoff + 0x00100000 - 0x80
  offline  offline.bin     VA = fileoff + 0x00692700
  online   online.bin      VA = fileoff + 0x00692700

`xref` finds the standard MIPS address-materialisation pair

    lui   $rs, HI
    addiu $rt, $rs, LO          (or ori / lw / sw / lbu / ... with $rs as base)

by scanning every candidate second-half instruction and walking back up to
`WINDOW` instructions for a `lui` into the same register with no intervening
write to it.  It deliberately ignores $sp/$gp/$fp/$zero bases, which is the trap
that makes a bare-immediate search useless on this compiler.
"""
import struct, sys, re, os

GR = "E:/PS2 Games/Tom Clancy's Ghost Recon (USA)/SLUS_206.13"
JS = "E:/PS2 Games/Tom Clancy's Ghost Recon - Jungle Storm (USA)/SLUS_208.20"
OFF = "E:/PS2 Games/Tom Clancy's Ghost Recon - Jungle Storm (USA)/offline.bin"
ONL = "E:/PS2 Games/Tom Clancy's Ghost Recon - Jungle Storm (USA)/online.bin"
SOAF = ("E:/PS2 Games/Sum of All Fears, The (Europe) (En,Fr,De,Es,It)"
        "/SLES_511.80")

# name -> (path, file_start, file_end_or_None, VA_of_file_start)
TARGETS = {
    "gr":      (GR,  0x80,   0x80 + 0x004ded00, 0x00100000),
    "js":      (JS,  0x100,  0x100 + 0x00512900, 0x00100000),
    # Sum of All Fears: PT_LOAD at file 0x80, VA 0x00100000, filesz 0x4A5780
    "soaf":    (SOAF, 0x80,  0x80 + 0x004a5780, 0x00100000),
    "offline": (OFF, 0x00,   None,               0x00692700),
    "online":  (ONL, 0x00,   None,               0x00692700),
}

REG = ['zero','at','v0','v1','a0','a1','a2','a3','t0','t1','t2','t3','t4','t5',
       't6','t7','s0','s1','s2','s3','s4','s5','s6','s7','t8','t9','k0','k1',
       'gp','sp','fp','ra']
BAD_BASE = {0, 28, 29, 30}          # zero, gp, sp, fp


class Image:
    def __init__(self, key):
        path, start, end, va = TARGETS[key]
        self.key, self.path, self.va0 = key, path, va
        raw = open(path, "rb").read()
        self.data = raw[start:end] if end else raw[start:]
        self.start = start

    def __len__(self): return len(self.data)
    def off(self, va): return va - self.va0
    def va(self, off): return off + self.va0
    def word(self, va):
        o = self.off(va)
        if not 0 <= o <= len(self.data) - 4: return None
        return struct.unpack_from("<I", self.data, o)[0]
    def fileoff(self, va): return self.off(va) + self.start

    def cstr(self, va, maxlen=200):
        o = self.off(va)
        if not 0 <= o < len(self.data): return None
        e = self.data.find(b"\0", o)
        if e < 0 or e - o > maxlen: return None
        s = self.data[o:e]
        if not s or not all(32 <= c < 127 or c in (9, 10, 13) for c in s): return None
        return s.decode("latin1")


# ---------------------------------------------------------------- strings
def strings(img, minlen=4):
    """NUL-terminated printable runs of at least `minlen` bytes.

    Tab, newline and carriage return count as *part of* a run rather than
    ending it, matching `Image.cstr`. That one detail is the whole fix made on
    2026-09-28. The original loop tested only `32 <= c < 127`, so a `\\n` broke
    the run, and the emit test then required the terminator to be NUL::

        if c == 0 and i - run >= minlen:      # the byte seen was \\n, not NUL

    -- so every `printf`-style string was discarded whole. That hid real
    content: Sum of All Fears' entire i.Link transport layer
    (`ILink:Out of  IOBuffer\\n`, `SendPacket %d\\n`,
    `Recved fraged packet %d %d %d\\n`) was invisible.

    The NUL requirement is deliberately KEPT. It is the noise filter: without
    it, every 4-byte printable run inside MIPS code is emitted and the result
    balloons with garbage like `'E$\\j'` -- on Ghost Recon 19,923 real strings
    become 50,928. A first attempt at this fix dropped the NUL test and did
    exactly that, which also produced a badly misleading "61% of the pool was
    missing" statistic; the true figure is the ~3-4% below, and the rest was
    machine code being read as text.

    Recovered by this fix: Ghost Recon 19,301 -> 19,923, Jungle Storm
    9,772 -> 10,096, Sum of All Fears 18,864 -> 19,648.

    A "0 hits, therefore absent" conclusion drawn before the fix is only
    unsafe if the thing being looked for is `\\n`-terminated debug output --
    class names, asset names and menu ids were always NUL-terminated and are
    unaffected. Every such negative recorded for Ghost Recon and Jungle Storm
    was re-run on 2026-09-28 and all of them held.
    """
    out = []
    d = img.data
    run = None
    for i, c in enumerate(d):
        if 32 <= c < 127 or c in (9, 10, 13):
            if run is None: run = i
        else:
            if run is not None:
                if c == 0 and i - run >= minlen:
                    out.append((img.va(run), d[run:i].decode("latin1")))
                run = None
    return out


# ---------------------------------------------------------------- xrefs
WINDOW = 12

def _decode(w):
    return (w >> 26), (w >> 21) & 31, (w >> 16) & 31, w & 0xFFFF

# opcodes whose immediate is sign-extended and combines with a lui base
SIGNED_OPS = {0x09,            # addiu
              0x20,0x21,0x22,0x23,0x24,0x25,0x26,  # lb lh lwl lw lbu lhu lwr
              0x28,0x29,0x2a,0x2b,0x2e,           # sb sh swl sw swr
              0x31,0x35,0x39,0x3d,                # lwc1 ldc1 swc1 sdc1
              0x37,0x3f,                          # ld sd
              0x1e,0x1f}                          # lq sq (R5900)
UNSIGNED_OPS = {0x0d}          # ori

def _writes(w):
    """Which GPR does this instruction write? None if unknown/none."""
    op, rs, rt, imm = _decode(w)
    if op == 0:                                   # SPECIAL -> rd
        fn = w & 0x3F
        if fn in (0x08, 0x09):                    # jr / jalr (jalr writes rd)
            return (w >> 11) & 31 if fn == 0x09 else None
        return (w >> 11) & 31
    if op == 1: return 31 if ((w >> 16) & 31) in (0x10, 0x11) else None  # bltzal/bgezal
    if op == 3: return 31                          # jal
    if op in (0x02,): return None                  # j
    if op in (0x04,0x05,0x06,0x07,0x14,0x15,0x16,0x17): return None      # branches
    if op in (0x28,0x29,0x2a,0x2b,0x2e,0x39,0x3d,0x3f,0x1f): return None # stores
    if op == 0x11: return None                     # COP1
    if op == 0x1c: return (w >> 11) & 31           # MMI -> rd
    if op in (0x08,0x09,0x0a,0x0b,0x0c,0x0d,0x0e,0x0f,0x18,0x19,0x19,
              0x20,0x21,0x22,0x23,0x24,0x25,0x26,0x30,0x31,0x35,0x37,0x1e):
        return rt
    return rt


def xrefs(img, target, window=WINDOW):
    """Return [(site_va, kind, text)] where code materialises `target`."""
    d = img.data
    n = len(d) // 4
    hits = []
    hi_t = (target >> 16) & 0xFFFF
    lo_s = target & 0xFFFF
    # candidate LUI immediates: exact hi, or hi+1 when low half is negative
    for i in range(n):
        w = struct.unpack_from("<I", d, i * 4)[0]
        op, rs, rt, imm = _decode(w)
        if rs in BAD_BASE: continue
        if op in SIGNED_OPS:
            simm = imm - 0x10000 if imm & 0x8000 else imm
            need = ((target - simm) >> 16) & 0xFFFF
            if ((target - simm) & 0xFFFF) != 0: continue
        elif op in UNSIGNED_OPS:
            need = (target - imm) >> 16 & 0xFFFF
            if (target & 0xFFFF) != imm: continue
        else:
            continue
        # walk back for lui rs, need
        for k in range(1, window + 1):
            j = i - k
            if j < 0: break
            pw = struct.unpack_from("<I", d, j * 4)[0]
            pop, prs, prt, pimm = _decode(pw)
            if pop == 0x0F and prt == rs:
                if pimm == need:
                    hits.append((img.va(j * 4), img.va(i * 4), w, pw))
                break
            if _writes(pw) == rs:
                break
    return hits


# ---------------------------------------------------------------- disasm
try:
    from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32, CS_MODE_LITTLE_ENDIAN
    _md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN)
except Exception:
    _md = None


def dis1(img, va, w=None):
    """R5900-aware single-instruction disassembly."""
    if w is None: w = img.word(va)
    if w is None: return ".word     ????"
    op, rs, rt, imm = _decode(w)
    simm = imm - 0x10000 if imm & 0x8000 else imm
    if op == 0x1F: return "sq        $%s, %d($%s)" % (REG[rt], simm, REG[rs])
    if op == 0x1E: return "lq        $%s, %d($%s)" % (REG[rt], simm, REG[rs])
    if op == 0x1C:
        fn = w & 0x3F; sa = (w >> 6) & 31; rd = (w >> 11) & 31
        if fn == 0x28 and sa == 0x18 and rt == 0:
            return "move128   $%s, $%s" % (REG[rd], REG[rs])       # paddub rd,rs,$0
        if fn == 0x28 and sa == 0x12 and rt == 0:
            return "move128   $%s, $%s" % (REG[rd], REG[rs])       # pextuw
        return "MMI.%02x/%02x $%s, $%s, $%s" % (fn, sa, REG[rd], REG[rs], REG[rt])
    if op == 0:
        fn = w & 0x3F; rd = (w >> 11) & 31; sa = (w >> 6) & 31
        if fn == 0x2D:
            if rt == 0: return "move      $%s, $%s" % (REG[rd], REG[rs])
            return "daddu     $%s, $%s, $%s" % (REG[rd], REG[rs], REG[rt])
        if fn == 0x2C: return "dadd      $%s, $%s, $%s" % (REG[rd], REG[rs], REG[rt])
        if fn == 0x2F: return "dsubu     $%s, $%s, $%s" % (REG[rd], REG[rs], REG[rt])
        if fn == 0x38: return "dsll      $%s, $%s, %d" % (REG[rd], REG[rt], sa)
        if fn == 0x3A: return "dsrl      $%s, $%s, %d" % (REG[rd], REG[rt], sa)
        if fn == 0x3B: return "dsra      $%s, $%s, %d" % (REG[rd], REG[rt], sa)
        if fn == 0x3C: return "dsll32    $%s, $%s, %d" % (REG[rd], REG[rt], sa)
        if fn == 0x3E: return "dsrl32    $%s, $%s, %d" % (REG[rd], REG[rt], sa)
        if fn == 0x3F: return "dsra32    $%s, $%s, %d" % (REG[rd], REG[rt], sa)
    if op == 0x18: return "daddi     $%s, $%s, %d" % (REG[rt], REG[rs], simm)
    if op == 0x19: return "daddiu    $%s, $%s, %d" % (REG[rt], REG[rs], simm)
    if op == 0x3F: return "sd        $%s, %d($%s)" % (REG[rt], simm, REG[rs])
    if op == 0x37: return "ld        $%s, %d($%s)" % (REG[rt], simm, REG[rs])
    if _md:
        g = list(_md.disasm(struct.pack("<I", w), va))
        if g: return "%-9s %s" % (g[0].mnemonic, g[0].op_str)
    return ".word     0x%08x" % w


def dis(img, va, count=64, annotate=True):
    out, lui = [], {}
    for k in range(count):
        a = va + k * 4
        w = img.word(a)
        if w is None: break
        t = dis1(img, a, w)
        op, rs, rt, imm = _decode(w)
        note = ""
        if op == 0x0F:
            lui[rt] = imm << 16
        elif op in SIGNED_OPS | UNSIGNED_OPS and rs in lui:
            simm = imm - 0x10000 if imm & 0x8000 else imm
            addr = (lui[rs] + (simm if op in SIGNED_OPS else imm)) & 0xFFFFFFFF
            s = img.cstr(addr, 90)
            note = "   ; 0x%08x" % addr + (' "%s"' % s if s else "")
            if op == 0x09: lui[rt] = addr
        elif op == 3:
            note = "   ; -> 0x%08x" % ((w & 0x03FFFFFF) << 2)
        w2 = _writes(w)
        if w2 is not None and w2 in lui and op != 0x0F: lui.pop(w2, None)
        out.append("%08x  %08x  %-34s%s" % (a, w, t, note))
    return out


# ---------------------------------------------------------------- GR symbols
_SYMCACHE = None
def gr_symbols():
    global _SYMCACHE
    if _SYMCACHE is None:
        d = open(GR, "rb").read()
        SYMOFF, SYMSZ, STROFF = 0x0061cf80, 0x97420, 0x004dede0
        out = []
        for i in range(SYMSZ // 16):
            nm, val, size, info, other, sh = struct.unpack_from("<IIIBBH", d, SYMOFF + i * 16)
            e = d.find(b"\0", STROFF + nm)
            out.append((val, size, info & 0xF, d[STROFF + nm:e].decode("latin1")))
        _SYMCACHE = out
    return _SYMCACHE


def gr_sym_at(va):
    """Innermost symbol containing va -> (start, size, name) or None."""
    best = None
    for val, size, t, name in gr_symbols():
        if t == 2 and val <= va < val + max(size, 4):
            if best is None or val > best[0]: best = (val, size, name)
    return best


# ---------------------------------------------------------------- CLI
def main(a):
    if not a: print(__doc__); return 1
    cmd = a[0]
    if cmd == "sym":
        rx = re.compile(a[1], re.I)
        for val, size, t, name in sorted(gr_symbols()):
            if rx.search(name):
                print("%08x %7d %s %s" % (val, size, "FOD"[min(t,2)] if t<3 else "?", name))
        return 0
    img = Image(a[1])
    if cmd == "strings":
        ml = int(a[2]) if len(a) > 2 else 4
        for va, s in strings(img, ml): print("%08x\t%s" % (va, s))
    elif cmd == "word":
        va = int(a[2], 16); print("%08x = %08x   %s" % (va, img.word(va), dis1(img, va)))
    elif cmd == "dis":
        va = int(a[2], 16); n = int(a[3]) if len(a) > 3 else 64
        for l in dis(img, va, n): print(l)
    elif cmd == "xref":
        va = int(a[2], 16)
        for luiva, siteva, w, pw in xrefs(img, va):
            fn = gr_sym_at(luiva) if img.key == "gr" else None
            print("  %08x  %-38s %s" % (siteva, dis1(img, siteva, w),
                                        ("in %s+0x%x" % (fn[2], luiva - fn[0])) if fn else ""))
    elif cmd == "callers":
        tgt = int(a[2], 16)
        want = 0x0C000000 | ((tgt >> 2) & 0x03FFFFFF)
        d = img.data
        for i in range(len(d) // 4):
            if struct.unpack_from("<I", d, i * 4)[0] == want:
                va = img.va(i * 4)
                fn = gr_sym_at(va) if img.key == "gr" else None
                print("  %08x  %s" % (va, ("%s+0x%x" % (fn[2], va - fn[0])) if fn else ""))
    elif cmd == "grepstr":
        rx = re.compile(a[2], re.I)
        for va, s in strings(img, 3):
            if rx.search(s):
                xs = xrefs(img, va)
                print("%08x  %-60r  xrefs=%d %s" % (va, s, len(xs),
                      " ".join("%08x" % x[1] for x in xs[:8])))
    else:
        print(__doc__); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

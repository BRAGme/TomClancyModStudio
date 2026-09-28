#!/usr/bin/env python3
"""mwo3.py - unpack / inspect Metrowerks "MWo3" PS2 EE overlay images.

Used by Tom Clancy's Ghost Recon: Jungle Storm (PS2, SLUS-20820) for
`offline.bin` and `online.bin`.

    python mwo3.py info    <file.bin>
    python mwo3.py unpack  <file.bin> <outdir>
    python mwo3.py dis     <file.bin> <VA-hex> [count]

CONTAINER SPEC (verified against both retail images)
----------------------------------------------------
The file is NOT compressed and NOT encrypted.  It is a flat memory image that
the game DMAs verbatim to `loadVA`, header included.  Therefore:

        VA = loadVA + file_offset            (exact, for every byte in the file)

Header, 0x40 bytes, all little-endian u32:

    +0x00  char[4]  magic         "MWo3"
    +0x04  u32      version       2 = offline.bin, 3 = online.bin
    +0x08  u32      loadVA        0x00692700 in both
    +0x0c  u32      textSize      size of the executable region
    +0x10  u32      dataSize      size of the initialised-data region
    +0x14  u32      bssSize       zero-filled region appended at load time
    +0x18  u32      ctorStart     VA of the static-constructor pointer list
    +0x1c  u32      ctorEnd       VA one past the end of that list
    +0x20  char[]   name          NUL-terminated ("offline.bin"/"online.bin")
    ..0x40           zero padding

Derived layout (both confirmed byte-exact):

    filesize          == 0x40 + textSize + dataSize
    text   file[0x40                  : 0x40+textSize]  -> VA loadVA+0x40
    data   file[0x40+textSize         : filesize     ]  -> VA loadVA+0x40+textSize
    bss    (not in file)                                -> VA loadVA+filesize, bssSize bytes
    total memory image = 0x40 + textSize + dataSize + bssSize

and that total reproduces the SLUS_208.20 ELF program headers exactly:

    offline: 0x40+0x484c0+0x4280+0x7ac00 = 0x0c7380 == PT_LOAD[2] p_memsz, va 0x00692700
    online : 0x40+0x9d6c0+0xf600+0x25300 = 0x0d2000 == PT_LOAD[3] p_memsz, va 0x00692700

EVIDENCE THAT THE PAYLOAD IS MIPS CODE AT THAT VA
-------------------------------------------------
Taking every `jal` in the first 0x8000 bytes of online.bin (156 distinct
targets) and testing the three candidate base mappings, only VA =
0x692700 + file_offset makes the targets land on function prologues:

    VA = 0x692700 + (fileoff - 0x00):  94/129 targets are `addiu $sp,$sp,-N`
    VA = 0x692700 + (fileoff - 0x40):   6/129
    VA = 0x692700 + (fileoff - 0x80):   6/129

The remaining out-of-image `jal`s land in 0x00100000..0x0064be80, i.e. the
boot ELF's own text - the overlay calling back into the engine.
"""
import struct, sys, os

MAGIC = b"MWo3"
HDRSZ = 0x40


class MWo3:
    def __init__(self, data, path=None):
        self.data = data
        self.path = path
        if data[:4] != MAGIC:
            raise ValueError("not an MWo3 image (magic %r)" % data[:4])
        (self.version, self.loadVA, self.textSize, self.dataSize,
         self.bssSize, self.ctorStart, self.ctorEnd) = struct.unpack_from("<7I", data, 4)
        z = data.index(b"\0", 0x20)
        self.name = data[0x20:z].decode("latin1")

    # --- geometry -------------------------------------------------------
    @property
    def textVA(self):  return self.loadVA + HDRSZ
    @property
    def dataVA(self):  return self.loadVA + HDRSZ + self.textSize
    @property
    def bssVA(self):   return self.loadVA + len(self.data)
    @property
    def endVA(self):   return self.bssVA + self.bssSize

    def va2off(self, va):
        o = va - self.loadVA
        if not 0 <= o < len(self.data):
            raise ValueError("VA 0x%08x not backed by file" % va)
        return o

    def off2va(self, off):
        return self.loadVA + off

    def check(self):
        """Return a list of (name, ok, detail) consistency checks."""
        r = []
        exp = HDRSZ + self.textSize + self.dataSize
        r.append(("filesize == 0x40+text+data", exp == len(self.data),
                  "0x%x vs 0x%x" % (exp, len(self.data))))
        r.append(("magic/version", self.version in (2, 3), str(self.version)))
        r.append(("ctor list inside image",
                  self.loadVA <= self.ctorStart <= self.ctorEnd <= self.endVA,
                  "0x%08x..0x%08x" % (self.ctorStart, self.ctorEnd)))
        return r

    def ctors(self):
        """VAs in the static-constructor list (may be empty)."""
        out = []
        for va in range(self.ctorStart, self.ctorEnd, 4):
            try:
                o = self.va2off(va)
            except ValueError:
                break
            out.append(struct.unpack_from("<I", self.data, o)[0])
        return out

    # --- output ---------------------------------------------------------
    def text(self): return self.data[HDRSZ:HDRSZ + self.textSize]
    def data_seg(self): return self.data[HDRSZ + self.textSize:]

    def memory_image(self):
        """Full image exactly as it appears in EE RAM at loadVA."""
        return self.data + b"\0" * self.bssSize


def cmd_info(p):
    m = MWo3(open(p, "rb").read(), p)
    print("file        %s  (%d bytes)" % (p, len(m.data)))
    print("name        %s" % m.name)
    print("version     %d" % m.version)
    print("loadVA      0x%08x   (header itself is loaded here)" % m.loadVA)
    print("text        file 0x%06x-0x%06x  VA 0x%08x-0x%08x  (0x%x)"
          % (HDRSZ, HDRSZ + m.textSize, m.textVA, m.dataVA, m.textSize))
    print("data        file 0x%06x-0x%06x  VA 0x%08x-0x%08x  (0x%x)"
          % (HDRSZ + m.textSize, len(m.data), m.dataVA, m.bssVA, m.dataSize))
    print("bss         (zero fill)              VA 0x%08x-0x%08x  (0x%x)"
          % (m.bssVA, m.endVA, m.bssSize))
    print("mem image   0x%08x bytes total" % (m.endVA - m.loadVA))
    print("ctor list   0x%08x..0x%08x -> %s"
          % (m.ctorStart, m.ctorEnd, ["0x%08x" % c for c in m.ctors()] or "(empty)"))
    for n, ok, det in m.check():
        print("  [%s] %-30s %s" % ("OK" if ok else "!!", n, det))


def cmd_unpack(p, outdir):
    m = MWo3(open(p, "rb").read(), p)
    os.makedirs(outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(p))[0]
    for suf, blob in (("text", m.text()), ("data", m.data_seg()),
                      ("mem", m.memory_image())):
        fp = os.path.join(outdir, "%s.%s.bin" % (stem, suf))
        open(fp, "wb").write(blob)
        print("wrote %s  %d bytes" % (fp, len(blob)))
    print("VA of %s.mem.bin offset 0 = 0x%08x" % (stem, m.loadVA))


def cmd_dis(p, va, count=64):
    from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32, CS_MODE_LITTLE_ENDIAN
    m = MWo3(open(p, "rb").read(), p)
    o = m.va2off(va)
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN)
    for i in md.disasm(m.data[o:o + count * 4], va):
        print("  %08x  %-10s %s" % (i.address, i.mnemonic, i.op_str))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(1)
    if a[0] == "info":   cmd_info(a[1])
    elif a[0] == "unpack": cmd_unpack(a[1], a[2])
    elif a[0] == "dis":  cmd_dis(a[1], int(a[2], 16), int(a[3]) if len(a) > 3 else 64)
    else: print(__doc__); sys.exit(1)

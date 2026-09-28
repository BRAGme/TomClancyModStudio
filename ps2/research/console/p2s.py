"""Read the EE CPU state out of a PCSX2 savestate.

Layout comes from the emulator's own source rather than guesswork:
`SaveStateBase::FreezeInternals` writes a 32-byte "cpuRegs" tag and then the
`cpuRegisters` struct, whose fields are

    GPR[32] x 16 bytes = 512      HI 16      LO 16
    CP0 (32 x u32)     = 128      sa 4       IsDelaySlot 4      pc 4

so `pc` lands 680 bytes into the struct.
"""
import struct
import sys
import zipfile

TAG = b"cpuRegs" + b"\x00" * 25          # FreezeTag pads to 32
GPR_SIZE = 16
PC_OFF = 32 * GPR_SIZE + 16 + 16 + 128 + 4 + 4      # 680

NAMES = ("r0 at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 "
         "s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp s8 ra").split()


def cpu_state(path):
    with zipfile.ZipFile(path) as z:
        dat = z.read("PCSX2 Internal Structures.dat")
    at = dat.find(TAG)
    if at < 0:
        raise SystemExit("no cpuRegs tag in %s" % path)
    base = at + 32
    gpr = {}
    for i, name in enumerate(NAMES):
        gpr[name] = struct.unpack_from("<Q", dat, base + i * GPR_SIZE)[0]
    pc, code = struct.unpack_from("<II", dat, base + PC_OFF)
    sa, delay = struct.unpack_from("<II", dat, base + PC_OFF - 8)
    return {"tag_at": at, "pc": pc, "code": code, "sa": sa,
            "delay": delay, "gpr": gpr}


def ee_memory(path):
    with zipfile.ZipFile(path) as z:
        return z.read("eeMemory.bin")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        try:
            st = cpu_state(p)
        except Exception as exc:                                     # noqa: BLE001
            print("%-46s %s" % (p.split("\\")[-1], exc))
            continue
        g = st["gpr"]
        print("%-46s pc=%08x code=%08x ra=%08x sp=%08x delay=%d"
              % (p.split("\\")[-1], st["pc"], st["code"],
                 g["ra"] & 0xFFFFFFFF, g["sp"] & 0xFFFFFFFF, st["delay"]))
        if g["r0"] != 0:
            print("   ** r0 is not zero (%x) -- layout is wrong **" % g["r0"])

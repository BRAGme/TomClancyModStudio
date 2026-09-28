"""Map every EE syscall stub in the overlay, then find threads parked in one.

A stub is three instructions:  addiu v1,zero,N ; syscall ; jr ra
so they can be found exactly rather than guessed at, and N names the kernel
call. A thread blocked in a kernel call has its resume address inside its
stub -- at the syscall or just after it -- so scanning memory for those exact
addresses finds blocked threads without needing the TCB layout at all.

That is the difference between this and the earlier heuristic: every hit here
is provably a saved return into a known kernel call.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(
    r"C:\Users\Tristan\Documents\GitHub\TomClancyPS2-ModStudio",
    "research", "console"))
from p2s import ee_memory                                            # noqa: E402

BASE = 0x00100000
img = open(os.path.join(HERE, "ghidra", "SP_SOZ.bin"), "rb").read()

# EE kernel syscall numbers that matter for "who is blocked"
NAMES = {
    32: "CreateThread", 33: "DeleteThread", 34: "StartThread",
    35: "ExitThread", 36: "ExitDeleteThread", 37: "TerminateThread",
    39: "DisableDispatchThread", 41: "ChangeThreadPriority",
    43: "RotateThreadReadyQueue", 45: "ReleaseWaitThread",
    46: "iReleaseWaitThread", 47: "GetThreadId", 48: "ReferThreadStatus",
    50: "SleepThread", 51: "WakeupThread", 52: "iWakeupThread",
    53: "CancelWakeupThread", 55: "SuspendThread", 57: "ResumeThread",
    59: "RFU059", 60: "SetupThread", 61: "SetupHeap", 62: "EndOfHeap",
    64: "CreateSema", 65: "DeleteSema", 66: "SignalSema",
    67: "iSignalSema", 68: "WaitSema", 69: "PollSema", 70: "iPollSema",
    71: "ReferSemaStatus", 72: "iReferSemaStatus",
    76: "SetOsdConfigParam", 77: "GetOsdConfigParam",
    120: "SifSetReg", 121: "SifGetReg",
}

stubs = {}
for off in range(0, len(img) - 12, 4):
    a, b, c = struct.unpack_from("<III", img, off)
    if (a & 0xFFFF0000) != 0x24030000:            # addiu v1,zero,N
        continue
    if b != 0x0000000C:                           # syscall
        continue
    if c != 0x03E00008:                           # jr ra
        continue
    n = a & 0xFFFF
    if n > 0x7FFF:
        n -= 0x10000
    stubs[BASE + off] = n

print("%d syscall stub(s) in the overlay" % len(stubs))
blocking = {va: n for va, n in stubs.items()
            if NAMES.get(abs(n), "").startswith(("WaitSema", "SleepThread",
                                                 "SuspendThread"))}
for va, n in sorted(stubs.items()):
    name = NAMES.get(n, NAMES.get(abs(n), "syscall %d" % n))
    mark = "   <-- BLOCKING" if va in blocking else ""
    print("   %08x  v1=%-5d %s%s" % (va, n, name, mark))

# resume addresses: the syscall itself and the instruction after it
resume = {}
for va, n in stubs.items():
    name = NAMES.get(n, NAMES.get(abs(n), "syscall %d" % n))
    resume[va] = name
    resume[va + 4] = name
    resume[va + 8] = name

D = r"E:\Emulators\pcsx2-v1.7.5641-windows-x64-Qt\sstates"
F = lambda k: os.path.join(D, "SLUS-20883 (21CC1EC3).%02d.p2s" % k)


def parked(slot, label):
    mem = ee_memory(F(slot))
    found = {}
    for a in range(0, 0x00100000 - 4, 4):
        v = struct.unpack_from("<I", mem, a)[0]
        if v in resume:
            found.setdefault(resume[v], []).append((a, v))
    print()
    print("== %s ==" % label)
    for name in sorted(found):
        spots = found[name]
        print("   %-22s %d saved resume address(es)  e.g. %s"
              % (name, len(spots),
                 ", ".join("kernel %08x -> %08x" % s for s in spots[:3])))
    return found


h = parked(23, "canon_team, WEDGED")
w = parked(35, "control, loading normally")
print()
print("== kernel calls threads are parked in, WEDGED but not working ==")
for name in sorted(set(h) - set(w)):
    print("   %s" % name)
print("== and working but not wedged ==")
for name in sorted(set(w) - set(h)):
    print("   %s" % name)

"""Talk to a running PCSX2 over PINE.

Framing, from the emulator's own PINE.cpp: a request is `u32 totalSize`
(counting itself) followed by commands, each `u8 opcode` + its arguments. A
reply is `u32 size`, then `u8 result` (0 ok, 0xFF fail), then the payload.
"""
import socket
import struct

HOST, PORT = "127.0.0.1", 28011

READ8, READ16, READ32, READ64 = 0, 1, 2, 3
WRITE8, WRITE16, WRITE32, WRITE64 = 4, 5, 6, 7
VERSION, SAVESTATE, LOADSTATE = 8, 9, 0xA
TITLE, GAMEID, UUID, GAMEVER, STATUS = 0xB, 0xC, 0xD, 0xE, 0xF

RUNNING, PAUSED, SHUTDOWN = 0, 1, 2


class PineError(Exception):
    pass


class Pine:
    def __init__(self, host=HOST, port=PORT, timeout=5.0):
        self.s = socket.create_connection((host, port), timeout)

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _call(self, body: bytes) -> bytes:
        pkt = struct.pack("<I", len(body) + 4) + body
        self.s.sendall(pkt)
        head = self._recv(4)
        size = struct.unpack("<I", head)[0]
        rest = self._recv(size - 4)
        if not rest or rest[0] != 0:
            raise PineError("PINE refused the command (result %r)"
                            % (rest[0] if rest else None))
        return rest[1:]

    def _recv(self, n: int) -> bytes:
        out = b""
        while len(out) < n:
            chunk = self.s.recv(n - len(out))
            if not chunk:
                raise PineError("PINE closed the connection")
            out += chunk
        return out

    # -- memory ----------------------------------------------------------
    def read32(self, addr: int) -> int:
        return struct.unpack("<I", self._call(
            struct.pack("<BI", READ32, addr)))[0]

    def read8(self, addr: int) -> int:
        return self._call(struct.pack("<BI", READ8, addr))[0]

    def read_block(self, addr: int, count: int) -> bytes:
        """`count` words, batched into one request -- one round trip, not N."""
        body = b"".join(struct.pack("<BI", READ32, addr + 4 * i)
                        for i in range(count))
        return self._call(body)

    # -- control ---------------------------------------------------------
    def savestate(self, slot: int):
        self._call(struct.pack("<BB", SAVESTATE, slot))

    def status(self) -> int:
        return struct.unpack("<I", self._call(bytes([STATUS])))[0]

    def _string(self, op: int) -> str:
        raw = self._call(bytes([op]))
        n = struct.unpack("<I", raw[:4])[0]
        return raw[4:4 + n].split(b"\x00")[0].decode("latin-1")

    def title(self) -> str:
        return self._string(TITLE)

    def game_id(self) -> str:
        return self._string(GAMEID)


if __name__ == "__main__":
    import sys
    try:
        with Pine() as p:
            print("status  : %d (0 running, 1 paused, 2 shutdown)" % p.status())
            print("game id : %s" % p.game_id())
            print("title   : %s" % p.title())
            if len(sys.argv) > 1 and sys.argv[1] == "save":
                slot = int(sys.argv[2]) if len(sys.argv) > 2 else 9
                p.savestate(slot)
                print("savestate requested into slot %d" % slot)
    except OSError as exc:
        raise SystemExit("PCSX2 is not running, or PINE is off: %s" % exc)

"""gsproto.py - Ubi.com GameService (GS) wire protocol as used by Ghost Recon: Jungle Storm (PS2).

Pure standard library.  Everything here was checked against the JS client code in
online.bin (load VA 0x00692700) and against the captured 284-byte first frames.

Credits: the GSXor permutation, the message header layout and the data-list format follow the
public reverse engineering in michal-kapala/gsconnect (MIT License, Copyright (c) michal-kapala).
The code below is an independent re-implementation, re-verified on the PS2 client:
  header packers      online.bin 0x006E3B00..0x006E3BF4
  property dispatch   online.bin 0x006E9894 (0 = clGSMessage/GSXor, 1 = clGameMessage, 2 = clGSEncryptMessage)
  Blowfish core       online.bin 0x006F3FE0 (encrypt), 0x006F4180 (key schedule), 0x006F0090 (buffer wrapper)
  RSA (RSAREF style)  online.bin 0x006F4B20 (public encrypt, PKCS#1 v1.5 block type 2), 0x006F4F00 (private decrypt)
"""
import math, os, struct

# ------------------------------------------------------------------ constants
PROP_GS, PROP_GAME, PROP_GS_ENCRYPT = 0, 1, 2
T_ROUTER, T_SERVER, T_W, T_PLAYER, T_AP, T_B, T_LP, T_UNK, T_G, T_A, T_PROXY = 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11

MSG = {
    'NEWUSERREQUEST': 1, 'CONNECTIONREQUEST': 2, 'PLAYERNEW': 3, 'DISCONNECTION': 4, 'PLAYERREMOVED': 5,
    'EVENT_UDPCONNECT': 6, 'NEWS': 7, 'SEARCHPLAYER': 8, 'REMOVEACCOUNT': 9, 'SERVERSLIST': 11,
    'SESSIONLIST': 13, 'PLAYERLIST': 15, 'GETGROUPINFO': 16, 'GROUPINFO': 17, 'GETPLAYERINFO': 18,
    'PLAYERINFO': 19, 'CHATALL': 20, 'CHATLIST': 21, 'CHATSESSION': 22, 'CHAT': 24, 'CREATESESSION': 26,
    'SESSIONNEW': 27, 'JOINSESSION': 28, 'JOINNEW': 31, 'LEAVESESSION': 32, 'JOINLEAVE': 33,
    'SESSIONREMOVE': 34, 'GSSUCCESS': 38, 'GSFAIL': 39, 'BEGINGAME': 40, 'UPDATEPLAYERINFO': 45,
    'MASTERCHANGED': 48, 'UPDATESESSIONSTATE': 51, 'URGENTMESSAGE': 52, 'NEWWAITMODULE': 54,
    'KILLMODULE': 55, 'STILLALIVE': 58, 'PING': 59, 'PLAYERKICK': 60, 'PLAYERMUTE': 61, 'ALLOWGAME': 62,
    'FORBIDGAME': 63, 'GAMELIST': 64, 'UPDATEADVERTISMEMENTS': 65, 'UPDATENEWS': 66, 'VERSIONLIST': 67,
    'UPDATEVERSIONS': 68, 'UPDATEDISTANTROUTERS': 70, 'ADMINLOGIN': 71, 'STAT_PLAYER': 72, 'STAT_GAME': 73,
    'UPDATEFRIEND': 74, 'ADDFRIEND': 75, 'DELFRIEND': 76, 'LOGINWAITMODULE': 77, 'LOGINFRIENDS': 78,
    'ADDIGNOREFRIEND': 79, 'DELIGNOREFRIEND': 80, 'STATUSCHANGE': 81, 'JOINARENA': 82, 'LEAVEARENA': 83,
    'IGNORELIST': 84, 'IGNOREFRIEND': 85, 'GETARENA': 86, 'GETSESSION': 87, 'PAGEPLAYER': 88,
    'FRIENDLIST': 89, 'PEERMSG': 90, 'PEERPLAYER': 91, 'DISCONNECTFRIENDS': 92, 'JOINWAITMODULE': 93,
    'LOGINSESSION': 94, 'DISCONNECTSESSION': 95, 'PLAYERDISCONNECT': 96, 'ADVERTISEMENT': 97,
    'MODIFYUSER': 98, 'STARTGAME': 99, 'CHANGEVERSION': 100, 'PAGER': 101, 'LOGIN': 102, 'PHOTO': 103,
    'LOGINARENA': 104, 'SQLCREATE': 106, 'SQLSELECT': 107, 'SQLDELETE': 108, 'SQLSET': 109, 'SQLSTAT': 110,
    'SQLQUERY': 111, 'ROUTEURLIST': 127, 'DISTANCEVECTOR': 131, 'WRAPPEDMESSAGE': 132, 'CHANGEFRIEND': 133,
    'NEWRELFRIEND': 134, 'DELRELFRIEND': 135, 'NEWIGNOREFRIEND': 136, 'DELETEIGNOREFRIEND': 137,
    'ARENACONNECTION': 138, 'ARENADISCONNECTION': 139, 'ARENAWAITMODULE': 140, 'ARENANEW': 141,
    'NEWBASICGROUP': 143, 'ARENAREMOVED': 144, 'DELETEBASICGROUP': 145, 'SESSIONSBEGIN': 146, 'GROUPDATA': 148,
    'ARENA_MESSAGE': 151, 'ARENALISTREQUEST': 157, 'ROUTERPLAYERNEW': 158, 'BASEGROUPREQUEST': 159,
    'UPDATEPLAYERPING': 166, 'UPDATEGROUPSIZE': 169, 'SLEEP': 179, 'WAKEUP': 180, 'SYSTEMPAGE': 181,
    'SESSIONOPEN': 189, 'SESSIONCLOSE': 190, 'LOGINCLANMANAGER': 192, 'DISCONNECTCLANMANAGER': 193,
    'CLANMANAGERPAGE': 194, 'UPDATECLANPLAYER': 195, 'PLAYERCLANS': 196, 'GETPERSISTANTGROUPINFO': 199,
    'UPDATEGROUPPING': 202, 'DEFERREDGAMESTARTED': 203, 'PROXY_HANDLER': 204, 'BEGINCLIENTHOSTGAME': 205,
    'LOBBY_MSG': 209, 'LOBBYSERVERLOGIN': 210, 'SETGROUPSZDATA': 211, 'GROUPSZDATA': 212,
    'KEY_EXCHANGE': 219, 'REQUESTPORTID': 221, 'MOTD_REQUEST': 222,
}
MSG_NAME = {v: k for k, v in MSG.items()}

LOBBY = {
    'JOIN_SERVER': 3, 'INFO_REFRESH': 6, 'GROUP_LEAVE': 8, 'GROUP_INFO_GET': 9, 'PLAYER_KICK': 10,
    'CREATE_ROOM': 12, 'PARENT_GROUP_ID': 14, 'START_GAME': 15, 'START_MATCH': 17, 'LOBBY_DISCONNECTION': 18,
    'REMOVE_SERVER': 19, 'LOGIN': 21, 'JOIN_LOBBY': 23, 'JOIN_ROOM': 24, 'MASTER_NEW': 27, 'SUBMIT_MATCH': 30,
    'GROUP_CONFIG_UPDATE_RES': 31, 'UPDATE_PING': 32, 'GAME_READY': 33, 'GAME_CONNECTED': 34, 'PLAYER_BAN': 36, 'PLAYER_UNBAN': 40,
    'UPDATE_GAME_INFO': 41, 'SET_PLAYER_INFO': 42, 'LOBBY_DISCONNECT_ALL': 43, 'MATCH_FINISH': 45,
    'GET_ALT_GROUP_INFO': 46, 'MEMBER_JOIN': 50, 'MEMBER_LEAVE': 51, 'GROUP_INFO': 53, 'NEW_GROUP': 54,
    'GROUP_REMOVE': 55, 'GAME_STARTED': 56, 'GROUP_CONFIG_UPDATE': 57, 'MASTER_CHANGED': 59, 'KICK_OUT': 61,
    'MATCH_STARTED': 62, 'PLAYER_BANNED': 63, 'PLAYER_BANLIST': 64, 'MATCH_READY': 65,
    'PLAYER_INFO_UPDATE': 66, 'PLAYER_UPDATE_STATUS': 69, 'FINAL_MATCH_RESULTS': 71,
    'PLAYER_GROUP_GET': 106, 'CHANGE_REQUESTED_LOBBIES': 109, 'MEMBER_LIST': 151,
}
LOBBY_NAME = {v: k for k, v in LOBBY.items()}


# ------------------------------------------------------------------ GSXor
def _gsx_order(n):
    """Wire position -> plaintext index.  The plaintext is written along anti-diagonals of a
    ceil(sqrt(n)) square and read out row by row (see gsconnect gsxor.py)."""
    r = math.isqrt(n)
    if r * r < n:
        r += 1
    cells = {}
    a = b = 0
    for i in range(n):              # plaintext index i sits at cell (row=a, col=b)
        if b < r:
            if a < 0:
                a, b = b, 0
        else:
            b, a = a + 2, r - 1
        cells[b + r * a] = i
        a -= 1
        b += 1
    return [cells[k] for k in sorted(cells)]


_order_cache = {}


def _order(n):
    o = _order_cache.get(n)
    if o is None:
        o = _order_cache[n] = _gsx_order(n)
    return o


def gsxor_decrypt(data):
    n = len(data)
    if n == 0:
        return b''
    out = bytearray(n)
    for pos, idx in enumerate(_order(n)):
        out[idx] = data[pos]
    for i in range(n):
        out[i] ^= (i - 119) & 0xFF
    return bytes(out)


def gsxor_encrypt(data):
    n = len(data)
    if n == 0:
        return b''
    x = bytes(b ^ ((i - 119) & 0xFF) for i, b in enumerate(data))
    return bytes(x[idx] for idx in _order(n))


# ------------------------------------------------------------------ Blowfish (PS2 GS variant)
def _bf_tables():
    """P-array + S-boxes = hex digits of pi.  Computed with Machin's formula so no 4 KB table
    has to be pasted in; checked against the copy inside online.bin (P at 0x007348E0)."""
    ndig = (18 + 1024) * 8 + 16
    prec = ndig * 4 + 64
    one = 1 << prec

    def arctan_inv(x):
        s = t = one // x
        x2, k, sign = x * x, 1, -1
        while t:
            t //= x2
            k += 2
            s += sign * (t // k)
            sign = -sign
        return s
    pi = 4 * (4 * arctan_inv(5) - arctan_inv(239))
    frac = pi - (3 << prec)
    hexs = format((frac << 4 * ndig) >> prec, '0%dx' % ndig)
    words = [int(hexs[i * 8:i * 8 + 8], 16) for i in range(18 + 1024)]
    return words[:18], [words[18 + 256 * k:18 + 256 * (k + 1)] for k in range(4)]


_P0, _S0 = _bf_tables()
assert _P0[0] == 0x243F6A88 and _P0[17] == 0x8979FB1B and _S0[0][0] == 0xD1310BA6 and _S0[3][255] == 0x3AC372E6


class Blowfish:
    """Blowfish exactly as CipherModule_Blowfish in the JS client:
    - standard key schedule (key bytes packed big-endian, 0x006F4180)
    - each 8-byte block is loaded as two LITTLE-endian 32-bit words (lw on the EE), ECB
    - encrypt(): zero-pad to a multiple of 8, append the plaintext length as u16 little-endian
    """

    def __init__(self, key):
        self.P = list(_P0)
        self.S = [list(s) for s in _S0]
        j = 0
        for i in range(18):
            d = 0
            for _ in range(4):
                d = (d << 8) | key[j]
                j = (j + 1) % len(key)
            self.P[i] ^= d
        l = r = 0
        for i in range(0, 18, 2):
            l, r = self._enc(l, r)
            self.P[i], self.P[i + 1] = l, r
        for s in range(4):
            for i in range(0, 256, 2):
                l, r = self._enc(l, r)
                self.S[s][i], self.S[s][i + 1] = l, r

    def _f(self, x):
        S = self.S
        return ((((S[0][x >> 24] + S[1][(x >> 16) & 255]) & 0xFFFFFFFF) ^ S[2][(x >> 8) & 255]) + S[3][x & 255]) & 0xFFFFFFFF

    def _enc(self, l, r):
        P = self.P
        for i in range(16):
            l ^= P[i]
            r ^= self._f(l)
            l, r = r, l
        l, r = r, l
        r ^= P[16]
        l ^= P[17]
        return l, r

    def _dec(self, l, r):
        P = self.P
        for i in range(17, 1, -1):
            l ^= P[i]
            r ^= self._f(l)
            l, r = r, l
        l, r = r, l
        r ^= P[1]
        l ^= P[0]
        return l, r

    def encrypt(self, data):
        n = len(data)
        buf = bytes(data) + b'\0' * ((-n) % 8)
        out = bytearray()
        for i in range(0, len(buf), 8):
            l, r = struct.unpack_from('<II', buf, i)
            out += struct.pack('<II', *self._enc(l, r))
        return bytes(out) + struct.pack('<H', n)

    def decrypt(self, data):
        if len(data) < 2 or (len(data) - 2) % 8:
            raise ValueError('bad GS Blowfish length %d' % len(data))
        n = struct.unpack_from('<H', data, len(data) - 2)[0]
        out = bytearray()
        for i in range(0, len(data) - 2, 8):
            l, r = struct.unpack_from('<II', data, i)
            out += struct.pack('<II', *self._dec(l, r))
        return bytes(out[:n])


# ------------------------------------------------------------------ RSA (RSAREF layout, PKCS#1 v1.5 type 2)
def _is_probable_prime(n, rounds=24):
    if n < 4:
        return n in (2, 3)
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for _ in range(rounds):
        a = 2 + int.from_bytes(os.urandom(16), 'big') % (n - 3)
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


class RsaKey:
    def __init__(self, n, e, d=None):
        self.n, self.e, self.d = n, e, d
        self.bits = n.bit_length()
        self.k = (self.bits + 7) // 8

    @classmethod
    def generate(cls, bits=512, e=3):
        while True:
            ps = []
            for half in (bits // 2, bits - bits // 2):
                while True:
                    c = int.from_bytes(os.urandom(half // 8), 'big') | (3 << (half - 2)) | 1
                    if (c - 1) % e and _is_probable_prime(c):
                        ps.append(c)
                        break
            n = ps[0] * ps[1]
            if n.bit_length() == bits and ps[0] != ps[1]:
                phi = (ps[0] - 1) * (ps[1] - 1)
                return cls(n, e, pow(e, -1, phi))

    # R_RSA_PUBLIC_KEY: u32 bits (little-endian, EE memory image), modulus[128], exponent[128] (big-endian, right-aligned)
    def to_blob(self):
        return struct.pack('<I', self.bits) + self.n.to_bytes(128, 'big') + self.e.to_bytes(128, 'big')

    @classmethod
    def from_blob(cls, blob):
        if len(blob) != 260:
            raise ValueError('public key blob must be 260 bytes, got %d' % len(blob))
        bits = struct.unpack_from('<I', blob)[0]
        n = int.from_bytes(blob[4:132], 'big')
        e = int.from_bytes(blob[132:260], 'big')
        k = cls(n, e)
        if k.bits != bits:
            k.bits = bits
            k.k = (bits + 7) // 8
        return k

    def encrypt(self, msg):
        k = self.k
        if len(msg) + 11 > k:
            raise ValueError('message too long for key')
        pad = bytearray()
        while len(pad) < k - len(msg) - 3:
            b = os.urandom(1)
            if b != b'\0':
                pad += b
        block = b'\x00\x02' + bytes(pad) + b'\x00' + bytes(msg)
        return pow(int.from_bytes(block, 'big'), self.e, self.n).to_bytes(k, 'big')

    def decrypt(self, ct):
        if self.d is None:
            raise ValueError('no private key')
        if len(ct) != self.k:
            raise ValueError('ciphertext length %d != modulus length %d' % (len(ct), self.k))
        block = pow(int.from_bytes(ct, 'big'), self.d, self.n).to_bytes(self.k, 'big')
        if block[0] != 0 or block[1] != 2:
            raise ValueError('bad PKCS#1 block type')
        z = block.index(b'\0', 2)
        return block[z + 1:]


# ------------------------------------------------------------------ data lists
class Bin(bytes):
    """A 'b' element (4-byte big-endian length + raw bytes)."""
    def __repr__(self):
        return 'Bin(%s)' % bytes(self).hex()


def encode_items(items):
    out = bytearray()
    for it in items:
        if isinstance(it, Bin):
            out += b'b' + struct.pack('>I', len(it)) + bytes(it)
        elif isinstance(it, (list, tuple)):
            out += b'[' + encode_items(it) + b']'
        elif isinstance(it, (bytes, bytearray)):
            out += b's' + bytes(it) + b'\0'
        elif isinstance(it, bool):
            out += b's' + (b'1' if it else b'0') + b'\0'
        elif isinstance(it, int):
            out += b's' + str(it).encode() + b'\0'
        elif isinstance(it, str):
            out += b's' + it.encode('latin1') + b'\0'
        else:
            raise TypeError('cannot encode %r' % (it,))
    return bytes(out)


def decode_items(buf, pos=0, nested=False):
    """Returns (items, pos).  Strings come back as str, binaries as Bin, lists as list."""
    items = []
    n = len(buf)
    while pos < n:
        t = buf[pos]
        if t == 0x5D:           # ']'
            if nested:
                return items, pos + 1
            raise ValueError('unbalanced ] at %d' % pos)
        pos += 1
        if t == 0x73:           # 's'
            z = buf.index(0, pos)
            items.append(buf[pos:z].decode('latin1'))
            pos = z + 1
        elif t == 0x62:         # 'b'
            ln = struct.unpack_from('>I', buf, pos)[0]
            pos += 4
            if pos + ln > n:
                raise ValueError('binary runs past end')
            items.append(Bin(buf[pos:pos + ln]))
            pos += ln
        elif t == 0x5B:         # '['
            sub, pos = decode_items(buf, pos, True)
            items.append(sub)
        elif t == 0 and not nested:
            break               # trailing zero padding
        else:
            raise ValueError('bad element tag 0x%02x at %d' % (t, pos - 1))
    if nested:
        raise ValueError('missing ]')
    return items, pos


def fmt_items(items):
    parts = []
    for it in items:
        if isinstance(it, Bin):
            b = bytes(it)
            parts.append('b%d:%s' % (len(b), b.hex() if len(b) <= 24 else b[:24].hex() + '...'))
        elif isinstance(it, list):
            parts.append('[' + fmt_items(it) + ']')
        else:
            parts.append(repr(it))
    return ', '.join(parts)


# ------------------------------------------------------------------ messages
class Message:
    def __init__(self, mtype, items, prop=PROP_GS, sender=T_ROUTER, receiver=T_PLAYER, priority=0, raw=None):
        self.type, self.items, self.prop = mtype, items, prop
        self.sender, self.receiver, self.priority = sender, receiver, priority
        self.raw = raw

    def name(self):
        return MSG_NAME.get(self.type, 'type%d' % self.type)

    def __repr__(self):
        return '<%s prop=%d %d->%d [%s]>' % (self.name(), self.prop, self.sender, self.receiver, fmt_items(self.items))


HEADER = 6


def pack(msg, bf=None):
    body = encode_items(msg.items)
    if msg.prop == PROP_GS:
        body = gsxor_encrypt(body)
    elif msg.prop == PROP_GS_ENCRYPT:
        if bf is None:
            raise ValueError('GS_ENCRYPT needs a key')
        body = bf.encrypt(body)
    size = HEADER + len(body)
    hdr = struct.pack('>I', size)[1:] + bytes([
        ((msg.prop & 3) << 6) | (msg.priority & 0x3F), msg.type & 0xFF,
        ((msg.sender & 15) << 4) | (msg.receiver & 15)])
    return hdr + body


def frame_size(buf):
    """Size of the first complete frame in buf, or 0 when more bytes are needed."""
    if len(buf) < HEADER:
        return 0
    size = (buf[0] << 16) | (buf[1] << 8) | buf[2]
    if size < HEADER:
        raise ValueError('frame size %d < header' % size)
    return size if len(buf) >= size else 0


def unpack(frame, bf=None):
    size = (frame[0] << 16) | (frame[1] << 8) | frame[2]
    prop, prio = frame[3] >> 6, frame[3] & 0x3F
    mtype = frame[4]
    snd, rcv = frame[5] >> 4, frame[5] & 15
    body = bytes(frame[HEADER:size])
    if prop == PROP_GS:
        plain = gsxor_decrypt(body)
    elif prop == PROP_GS_ENCRYPT:
        if bf is None:
            raise ValueError('GS_ENCRYPT message but no session key yet')
        plain = bf.decrypt(body)
    else:
        plain = body
    items, _ = decode_items(plain)
    m = Message(mtype, items, prop, snd, rcv, prio, raw=bytes(frame[:size]))
    m.plain = plain
    return m

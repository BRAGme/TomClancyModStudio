#!/usr/bin/env python3
"""fakeclient.py - two scripted "consoles" run the whole Jungle Storm online flow against ubilobby.py.

    python fakeclient.py                 start a private server on 127.0.0.1 (ports 18080/14000), run, stop
    python fakeclient.py --server HOST   use an already running server (gsinit on :80 unless --http-port)

Every message the fake console sends is built exactly as the JS client builds it (online.bin addresses
in the comments), and every reply is checked with the same element types and positions the JS client
parser uses.  The host binds 127.0.0.2 and the joiner 127.0.0.3 so the server sees two addresses.
"""
import argparse, os, socket, struct, sys, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gsproto as G
from gsproto import Bin, Message, MSG, LOBBY

FAILS = []


def check(cond, what):
    print('   %s %s' % ('ok  ' if cond else 'FAIL', what))
    if not cond:
        FAILS.append(what)
    return cond


def U32(x):
    return int(x) & 0xFFFFFFFF          # GetU32 = atol on a decimal string (online.bin 0x006FBFA0)


class Console:
    def __init__(self, name, local_ip, http, verbose=True):
        self.name, self.local_ip, self.http = name, local_ip, http
        self.verbose = verbose
        self.inbox = {}

    # ------------------------------------------------ transport
    def connect(self, ip, port, tag):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind((self.local_ip, 0))
        except OSError:
            pass
        s.settimeout(5)
        s.connect((ip, port))
        c = Conn(self, s, tag)
        return c

    def gsinit(self):
        host, port = self.http
        url = 'http://%s:%d/gsinit.php?dp=GHOSTRECONIT_PS2' % (host, port)
        body = urllib.request.urlopen(url, timeout=5).read().decode('latin1')
        kv = dict(l.split('=', 1) for l in body.splitlines() if '=' in l)
        check(body.startswith('[Servers]'), '%s gsinit answers a [Servers] section' % self.name)
        return kv['RouterIP0'], int(kv['RouterPort0'])


class Conn:
    def __init__(self, console, sock, tag):
        self.c, self.s, self.tag = console, sock, tag
        self.buf = bytearray()
        self.bf = None
        self.pending = []
        self.rsa = G.RsaKey.generate(512, 3)
        self.session = os.urandom(16)

    def send(self, mtype, items, prop=G.PROP_GS, snd=G.T_PLAYER, rcv=G.T_ROUTER):
        m = Message(mtype, items, prop, snd, rcv)
        if self.c.verbose:
            print('  %-6s %-6s -> %s' % (self.c.name, self.tag, m))
        self.s.sendall(G.pack(m, self.bf))

    def recv(self, want=None, timeout=5.0):
        """Next message (optionally the next one matching want(m)); others are kept for later."""
        for i, m in enumerate(self.pending):
            if want is None or want(m):
                return self.pending.pop(i)
        end = time.time() + timeout
        while time.time() < end:
            n = G.frame_size(self.buf)
            if n:
                frame = bytes(self.buf[:n])
                del self.buf[:n]
                m = G.unpack(frame, self.bf)
                if self.c.verbose:
                    print('  %-6s %-6s <- %s' % (self.c.name, self.tag, m))
                if want is None or want(m):
                    return m
                self.pending.append(m)
                continue
            self.s.settimeout(max(0.05, end - time.time()))
            try:
                chunk = self.s.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            self.buf += chunk
        raise TimeoutError('%s %s: no reply' % (self.c.name, self.tag))

    def lobby(self, sub):
        """LOBBY_MSG whose subtype is sub; handles both reply ['38',[sub,..]] and notify [sub,[..]] shapes
        like online.bin 0x007013E0."""
        def f(m):
            if m.type != MSG['LOBBY_MSG'] or not m.items:
                return False
            first = int(m.items[0])
            if first in (38, 39):
                return int(m.items[1][0]) == sub
            return first == sub
        return self.recv(f)

    def close(self):
        self.s.close()

    # ------------------------------------------------ KEY_EXCHANGE as online.bin 0x006EA300 / 0x006EA610 / 0x006EA730
    def key_exchange(self, then_send=None):
        blob = self.rsa.to_blob()
        self.send(MSG['KEY_EXCHANGE'], [1, [1, len(blob), Bin(blob)]], snd=G.T_UNK, rcv=G.T_SERVER)
        r = self.recv(lambda m: m.type == MSG['KEY_EXCHANGE'])
        sub = r.items[1]
        ln = int(sub[1])
        srv = G.RsaKey.from_blob(bytes(sub[2])[:ln])
        check(int(r.items[0]) == 1 and ln == 260, '%s KEY_EXCHANGE 1 reply carries a 260-byte public key (%d-bit)' % (self.tag, srv.bits))
        enc = srv.encrypt(self.session)
        self.send(MSG['KEY_EXCHANGE'], [2, [1, len(enc), Bin(enc)]], snd=G.T_UNK, rcv=G.T_SERVER)
        self.bf = G.Blowfish(self.session)       # the client flags encryption on right here (sb 1,0x68 at 0x006EA70C)
        if then_send:
            then_send()                          # e.g. LOGIN, sent before the key reply arrives (the race)
        r = self.recv(lambda m: m.type == MSG['KEY_EXCHANGE'])
        sub = r.items[1]
        key = self.rsa.decrypt(bytes(sub[2])[:int(sub[1])])
        self.bf = G.Blowfish(key)                # SetSessionKey 0x006EB440
        check(int(r.items[0]) == 2 and key == self.session, '%s KEY_EXCHANGE 2 reply decrypts to a 16-byte key equal to ours' % self.tag)


def expect_success(m, t, what):
    ok = m.type == MSG['GSSUCCESS'] and isinstance(m.items[0], Bin) and bytes(m.items[0]) == bytes([t])
    return check(ok, what)


def check_lobby_record(r, what):
    ok = isinstance(r, list) and len(r) == 14 and int(r[0]) == 0 and isinstance(r[10], Bin)
    for i in (2, 3, 4, 5, 11):
        ok = ok and str(r[i]).lstrip('-').isdigit()
    return check(ok, what)


def block_id(b):
    return struct.unpack_from('<i', b, 4)[0] if len(b) >= 8 else None


def block_ip(b):
    return b[8:0x1C].split(b'\0')[0].decode('latin1') if len(b) >= 0x1C else None


def check_room_record(r, what, host_ip=None):
    ok = isinstance(r, list) and len(r) == 20 and int(r[0]) != 0 and isinstance(r[10], Bin)
    ok = ok and len(bytes(r[10])) == 124
    if host_ip:
        ok = ok and r[18] == host_ip
    return check(ok, what)


def module_connect(c, w, module):
    """PROXY_HANDLER ['1', [module, '0', '0']] on the wait module (online.bin 0x00726C80 / 0x00729C40),
    reply parsed like online.bin 0x007224F0."""
    w.send(MSG['PROXY_HANDLER'], [1, [module, 0, 0]])
    m = w.recv(lambda m: m.type == MSG['PROXY_HANDLER'])
    ok = int(m.items[0]) == 38 and int(m.items[1][0]) == 1
    d = m.items[1][1]
    ok = ok and d[0] == module and isinstance(d[3], list) and len(d[3]) >= 1
    pid, host, port = int(d[3][0][0]), d[3][0][1], int(d[3][0][2]) & 0xFFFF
    check(ok, '%s module %r connect -> proxy %d at %s:%d' % (c.name, module, pid, host, port))
    return pid, host, port


def ladder_result_ok(m, seq, name):
    """CProxyHandler 0x00700550 + CLadderResults 0x0072DE30 / 0x0072D950 / 0x0072D420, then what the ELF
    ladder callback 0x001A2C60 reads: row 0 must exist and GRADE / TSCORE must be numeric (an exception
    there is what sent the console back to the BIOS in the v2 live test)."""
    try:
        t, s, x = int(m.items[0]), int(m.items[1]), m.items[2]
        if not (t == 1281 and s == seq and int(x[0]) == 38):
            return False
        d = x[1]
        if int(d[0]) != 1:                                   # VersionMismatch
            return False
        total, first, fields, rows = int(d[1][0]), int(d[1][1]), d[1][2], d[1][3]
        names = [f[0] for f in fields]
        if len(set(names)) != len(names) or any(len(f[0]) > 128 or len(f[1]) > 32 for f in fields):
            return False                                     # DuplicateField / GetStrN limits
        if not rows or any(len(r) != len(fields) for r in rows):
            return False                                     # OutOfBound on row 0 / FieldQtyMismatch
        r0 = dict(zip(names, rows[0]))
        for f in ('GRADE', 'TSCORE'):
            int(r0[f])                                       # UnknownField / NonNumericValue
        return r0.get('ALIAS') == name
    except (IndexError, ValueError, TypeError, KeyError):
        return False


def persistent_result_ok(m, seq):
    # CProxyHandler 0x00700550 + persistent result 0x0072A780: [S16 1, [[U32...]]]
    try:
        t, s, x = int(m.items[0]), int(m.items[1]), m.items[2]
        d = x[1]
        return t == 1537 and s == seq and int(x[0]) == 38 and int(d[0]) == 1 and isinstance(d[1][0], list) \
            and all(str(v).isdigit() for v in d[1][0])
    except (IndexError, ValueError, TypeError):
        return False


def proxy_session(c, w):
    """Ladder queries and persistent data as the JS client runs them after LOBBY LOGIN (see ubilobby.py)."""
    pid, host, port = module_connect(c, w, 'ladderquery')
    w.send(MSG['PROXY_HANDLER'], [2, [pid]])                              # online.bin 0x0071F1F4
    m = w.recv(lambda m: m.type == MSG['PROXY_HANDLER'])
    check(int(m.items[0]) == 38 and int(m.items[1][0]) == 2 and int(m.items[1][1][0]) == pid,
          '%s join proxy -> 38 [2,[%d]] (0x007235A0)' % (c.name, pid))
    # clProxyConnection: LOGIN / JOINWAITMODULE with sender 8 receiver 11, no key exchange (online.bin 0x006EC3D0)
    p = c.connect(host, port, 'proxy')
    p.send(MSG['LOGIN'], [c.name, 'secret'], snd=G.T_UNK, rcv=G.T_PROXY)
    m = p.recv()
    check(m.type == 38 and bytes(m.items[0]) == b'\x66' and isinstance(m.items[1], list), '%s proxy LOGIN -> [B(102), []]' % c.name)
    p.send(MSG['JOINWAITMODULE'], [], snd=G.T_UNK, rcv=G.T_PROXY)
    m = p.recv()
    L = m.items[1]
    check(m.type == 38 and bytes(m.items[0]) == b'\x5d' and len(L) == 3, '%s proxy JOINWAITMODULE -> [name, %s, %s]' % (c.name, L[1], L[2]))
    p.close()
    pw = c.connect(L[1], int(L[2]) & 0xFFFF, 'proxywm')
    pw.send(MSG['LOGINWAITMODULE'], [L[0]], snd=G.T_UNK, rcv=G.T_PROXY)
    m = pw.recv()
    check(m.type == 38 and bytes(m.items[0]) == b'\x4d' and isinstance(m.items[1], list), '%s proxy LOGINWAITMODULE -> [B(77), []]' % c.name)
    w.send(MSG['PROXY_HANDLER'], [[3, pid]])                              # status note (online.bin 0x00724AF8)
    seq = 1                                                               # live log: seqs start at 1
    for k in (1, 2, 3):                                                   # ELF 0x001A31E0: three ladder queries
        pw.send(MSG['PROXY_HANDLER'], [1281, seq, [1, [k, 'GHOSTRECONIT_PS2', 0, k, [2, [c.name]], [[], [], []]]]],
                snd=G.T_UNK, rcv=G.T_PROXY)
        m = pw.recv(lambda m: m.type == MSG['PROXY_HANDLER'])
        check(ladder_result_ok(m, seq, c.name), '%s ladder query %d -> CLadderResults v1 with a row for %s (GRADE, TSCORE numeric)' % (c.name, k, c.name))
        seq += 1
    module_connect(c, w, 'persistantdata')                                # same proxy, already logged in
    for kind in (0, 2):                                                   # ELF 0x001A1A40 kinds 0 and 2
        pw.send(MSG['PROXY_HANDLER'], [1537, seq, [1, ['GHOSTRECONIT_PS2', 0, [kind]]]], snd=G.T_UNK, rcv=G.T_PROXY)
        m = pw.recv(lambda m: m.type == MSG['PROXY_HANDLER'])
        check(persistent_result_ok(m, seq), '%s persistent data kind %d -> success with %d value(s)' % (c.name, kind, len(m.items[2][1][1][0])))
        seq += 1
    w.send(MSG['MOTD_REQUEST'], ['en'])                                   # ELF 0x001A1904
    m = w.recv(lambda m: m.type in (38, 39))
    check(m.type == 38 and bytes(m.items[0]) == bytes([222]) and len(m.items[1]) == 2, '%s MOTD -> [B(222), [text, text]] (0x00704F20)' % c.name)
    c.proxy = pw


def login_and_enter_lobby(c):
    rip, rport = c.gsinit()
    # ---- router
    r = c.connect(rip, rport, 'router')
    def send_login():   # online.bin 0x00703750: [user, pass, "GRITPS21.0", Bin(1)] sent GS_ENCRYPT
        r.send(MSG['LOGIN'], [c.name, 'secret', 'GRITPS21.0', Bin(b'\x01')], prop=G.PROP_GS_ENCRYPT)
    r.key_exchange(then_send=send_login)
    expect_success(r.recv(lambda m: m.type in (38, 39)), 102, '%s LOGIN accepted (GSSUCCESS [B(102)])' % c.name)
    r.send(MSG['JOINWAITMODULE'], [])
    m = r.recv(lambda m: m.type in (38, 39))
    expect_success(m, 93, '%s JOINWAITMODULE answered' % c.name)
    wm_ip = m.items[1][0]
    wm_port = struct.unpack('<H', bytes(m.items[1][1])[:2])[0]     # lhu of a 4-byte LE Bin (0x00703F00)
    check(len(bytes(m.items[1][1])) == 4, '%s wait module port is a 4-byte Bin (%s:%d)' % (c.name, wm_ip, wm_port))
    r.close()
    # ---- wait module
    w = c.connect(wm_ip, wm_port, 'wm')
    w.key_exchange()
    w.send(MSG['LOGINWAITMODULE'], [c.name])
    expect_success(w.recv(lambda m: m.type in (38, 39)), 77, '%s LOGINWAITMODULE accepted' % c.name)
    # ---- lobby login through the wait module (online.bin 0x00708F70)
    w.send(MSG['LOBBY_MSG'], [LOBBY['LOGIN'], ['GHOSTRECONIT_PS2']])
    m = w.lobby(LOBBY['LOGIN'])
    check(int(m.items[0]) == 38, '%s LOBBY LOGIN(21) -> 38' % c.name)
    gi = w.lobby(LOBBY['GROUP_INFO'])
    L = gi.items[1]
    check(int(L[1]) & 0x100 and len(L[3]) >= 1, '%s receives the lobby list (GROUP_INFO flags 0x%x, %d lobbies)' % (c.name, int(L[1]), len(L[3])))
    # ---- what the ELF does on LOBBY LOGIN success (ELF 0x0019F5F0): friends, then ladder + persistent data
    w.send(MSG['LOGINFRIENDS'], [Bin(bytes(4)), Bin(bytes(4))])
    expect_success(w.recv(lambda m: m.type in (38, 39)), 78, '%s LOGINFRIENDS accepted' % c.name)
    proxy_session(c, w)
    lob = L[3][0]
    check_lobby_record(lob, '%s lobby record has the 14 fields of online.bin 0x00708970 (%r)' % (c.name, lob[1]))
    lobby_id, srv_id = U32(lob[2]), U32(lob[3])
    # ---- JOIN_SERVER through the wait module (online.bin 0x00719600 -> 0x0070C8A0)
    w.send(MSG['LOBBY_MSG'], [LOBBY['JOIN_SERVER'], [srv_id]])
    m = w.lobby(LOBBY['JOIN_SERVER'])
    d = m.items[1][1]
    check(int(m.items[0]) == 38 and U32(d[0]) == srv_id, '%s JOIN_SERVER gives lobby server %s:%s' % (c.name, d[1], d[2]))
    # ---- lobby server (no key exchange on this connection)
    l = c.connect(d[1], int(d[2]) & 0xFFFF, 'lobby')
    l.send(MSG['LOBBYSERVERLOGIN'], [c.name, 1, '', '', 0], rcv=G.T_SERVER)
    m = l.recv()
    check(m.type == MSG['GSSUCCESS'] and int(m.items[0]) == 210 and U32(m.items[1][0]) == srv_id,
          '%s LOBBYSERVERLOGIN -> GSSUCCESS [210,[srv]] (0x0070C630)' % c.name)
    l.send(MSG['LOBBY_MSG'], [LOBBY['SET_PLAYER_INFO'], [Bin(bytes(range(24)))]], rcv=G.T_SERVER)
    check(int(l.lobby(LOBBY['SET_PLAYER_INFO']).items[0]) == 38, '%s SET_PLAYER_INFO(42) accepted' % c.name)
    l.send(MSG['LOBBY_MSG'], [LOBBY['JOIN_LOBBY'], [lobby_id, '', 0x1C0]], rcv=G.T_SERVER)
    m = l.lobby(LOBBY['JOIN_LOBBY'])
    check(int(m.items[0]) == 38 and U32(m.items[1][1][0]) == lobby_id, '%s JOIN_LOBBY(23) -> 38 [%d]' % (c.name, lobby_id))
    gi = l.lobby(LOBBY['GROUP_INFO'])
    check(U32(gi.items[1][0]) == lobby_id, '%s gets GROUP_INFO for the lobby it joined' % c.name)
    return w, l, lobby_id, srv_id, gi


def run(http, verbose=True):
    host = Console('HOST', '127.0.0.2', http, verbose)
    join = Console('JOINER', '127.0.0.3', http, verbose)
    print('== host logs in and enters the lobby')
    hw, hl, lobby_id, srv, _ = login_and_enter_lobby(host)
    print('== joiner logs in and enters the lobby')
    jw, jl, _, _, _ = login_and_enter_lobby(join)

    print('== heartbeat: STILLALIVE 4->1 on the wait module and 4->2 on the lobby (client timer online.bin 0x006E93A0)')
    hw.send(MSG['STILLALIVE'], [])
    r = hw.recv(lambda m: m.type == MSG['STILLALIVE'])
    check(r.sender == G.T_ROUTER and r.receiver == G.T_PLAYER, 'wait module echoes STILLALIVE 1->4 (any server bytes reset '
          'the 180 s receive timeout, online.bin 0x006F7A50)')
    hl.send(MSG['STILLALIVE'], [], rcv=G.T_SERVER)
    r = hl.recv(lambda m: m.type == MSG['STILLALIVE'])
    check(r.sender == G.T_SERVER and r.receiver == G.T_PLAYER, 'lobby server echoes STILLALIVE 2->4')

    print('== host creates a CO-OP room (online.bin 0x00709880, ELF 0x0019EAF0)')
    # the 124-byte block as the live host sent it: +0 = -1, +4 = -1 (no room yet), no IP, settings further on
    info = struct.pack('<ii', -1, -1) + bytes(0x38) + b'Coop test'.ljust(11, b'\0') + bytes(124 - 0x4B)
    hl.send(MSG['LOBBY_MSG'], [LOBBY['CREATE_ROOM'], [lobby_id, 'Coop test', 'GHOSTRECONIT_PS2', 5, 4, 0,
                                                       Bin(info), '', 'GRITPS21.0', '', Bin(b'')]], rcv=G.T_SERVER)
    ng = hl.lobby(LOBBY['NEW_GROUP'])
    check_room_record(ng.items[1], 'host sees NEW_GROUP before the CREATE_ROOM reply (room is in its list)')
    m = hl.lobby(LOBBY['CREATE_ROOM'])
    d = m.items[1][1]
    room = U32(d[0])
    check(int(m.items[0]) == 38 and U32(d[2]) == srv, 'CREATE_ROOM -> 38 [room %d, %r, srv %s] (0x0070D0A0)' % (room, d[1], d[2]))
    ngj = jl.lobby(LOBBY['NEW_GROUP'])
    host_ip = ngj.items[1][18]
    check_room_record(ngj.items[1], 'joiner sees the new room: 20 fields, 124-byte info, ip %s' % host_ip)
    blk = bytes(ngj.items[1][10])
    check(block_id(blk) == room and block_ip(blk) == host_ip,
          'room block in NEW_GROUP already carries room id %d at +4 and host IP %r at +8 (never -1: ELF 0x0019F2C0 '
          'copies +4 over the local room id)' % (block_id(blk), block_ip(blk)))

    print('== host joins its room (ELF 0x001A03A0 does this right after CREATE_ROOM)')
    hl.send(MSG['LOBBY_MSG'], [LOBBY['JOIN_ROOM'], [room, '', 0x1C0, 0, '']], rcv=G.T_SERVER)
    m = hl.lobby(LOBBY['JOIN_ROOM'])
    check(int(m.items[0]) == 38 and U32(m.items[1][1][0]) == room, 'host JOIN_ROOM -> 38')
    gi = hl.lobby(LOBBY['GROUP_INFO'])
    check(len(gi.items[1][4]) == 1 and gi.items[1][4][0][0] == 'HOST', 'host room GROUP_INFO lists itself as member')
    check(block_id(bytes(gi.items[1][2][10])) == room, 'host room GROUP_INFO block has id %d, not -1' % room)

    print('== host publishes its game block: 31 [room, 64, Bin(124)] (ELF 0x0019F430), as live: id + IP filled')
    hblk = struct.pack('<Ii', 1, room) + host_ip.encode().ljust(20, b'\0') + info[0x1C:0x4B] + bytes([3, 1, 2]) + info[0x4E:]
    hl.send(MSG['LOBBY_MSG'], [31, [room, 64, Bin(hblk)]], rcv=G.T_SERVER)
    check(int(hl.lobby(31).items[0]) == 38, 'host 31 -> 38 (ELF 0x001A4770 ignores the reply)')
    up = jl.lobby(LOBBY['GROUP_INFO'])
    L = up.items[1]
    check(U32(L[0]) == room and int(L[1]) == 0x40 and bytes(L[2][10]) == hblk,
          'lobby member gets GROUP_INFO [room, 0x40, record] with the host block (ELF 0x0019F2C0 updates its list)')

    print('== joiner joins the room')
    jl.send(MSG['LOBBY_MSG'], [LOBBY['JOIN_ROOM'], [room, '', 0x1C0, 0, '']], rcv=G.T_SERVER)
    m = jl.lobby(LOBBY['JOIN_ROOM'])
    check(int(m.items[0]) == 38, 'joiner JOIN_ROOM -> 38 (reply comes before the member list)')
    gi = jl.lobby(LOBBY['GROUP_INFO'])
    L = gi.items[1]
    names = [x[0] for x in L[4]]
    check(names == ['HOST', 'JOINER'], 'joiner GROUP_INFO members %r' % names)
    check_room_record(L[2], 'room record in GROUP_INFO carries the host address %s' % host_ip, host_ip)
    check(bytes(L[2][10]) == hblk, 'joiner GROUP_INFO carries the block the host published with 31')
    hostm = L[4][0]
    check(len(hostm) >= 7 and isinstance(hostm[4], Bin) and isinstance(hostm[5], list) and hostm[2] == host_ip,
          'member record = [name, visitor, ip, altip, Bin, [groups], ping, status] with host ip %s' % hostm[2])
    mj = hl.lobby(LOBBY['MEMBER_JOIN'])
    check(mj.items[1][0] == 'JOINER' and U32(mj.items[1][2]) == room, 'host gets MEMBER_JOIN for the joiner (0x007149B0)')

    print('== both press READY: SET_PLAYER_INFO(42) with blob[1]=1 -> PLAYER_INFO_UPDATE(66) to the other member')
    jinfo = bytes([1, 1, 0xFF]) + bytes(21)                       # ELF 0x0019F1A0: [1] = +0x14 ready
    jl.send(MSG['LOBBY_MSG'], [LOBBY['SET_PLAYER_INFO'], [Bin(jinfo)]], rcv=G.T_SERVER)
    check(int(jl.lobby(LOBBY['SET_PLAYER_INFO']).items[0]) == 38, 'joiner 42 -> 38')
    pu = hl.lobby(LOBBY['PLAYER_INFO_UPDATE'])
    check(pu.items[1][0] == 'JOINER' and bytes(pu.items[1][1]) == jinfo and bytes(pu.items[1][1])[1] == 1,
          'host gets 66 [JOINER, Bin(24)] with ready=1 (online.bin 0x007169B0 -> ELF 0x0019F590)')
    hinfo = bytes([1, 1, 0xFF]) + bytes(21)
    hl.send(MSG['LOBBY_MSG'], [LOBBY['SET_PLAYER_INFO'], [Bin(hinfo)]], rcv=G.T_SERVER)
    check(int(hl.lobby(LOBBY['SET_PLAYER_INFO']).items[0]) == 38, 'host 42 (Launch = host ready, ELF 0x0032F344) -> 38')
    pu = jl.lobby(LOBBY['PLAYER_INFO_UPDATE'])
    check(pu.items[1][0] == 'HOST' and bytes(pu.items[1][1])[1] == 1, 'joiner gets 66 [HOST, ..] with ready=1')
    try:
        own = hl.recv(lambda m: m.type == MSG['LOBBY_MSG'] and int(m.items[0]) == 66 and m.items[1][0] == 'HOST', timeout=0.5)
    except TimeoutError:
        own = None
    check(own is None, 'host does not get its own 66 back (ELF 0x0019F490 skips its own name anyway)')

    print('== a 31 for group -1 (v3 live: the host block had been reset to id -1) is mapped to the host room')
    hl.send(MSG['LOBBY_MSG'], [31, [-1, 64, Bin(info)]], rcv=G.T_SERVER)
    check(int(hl.lobby(31).items[0]) == 38, 'host 31 [-1, ..] -> 38')
    up = jl.lobby(LOBBY['GROUP_INFO'])
    b = bytes(up.items[1][2][10])
    check(U32(up.items[1][0]) == room and block_id(b) == room and block_ip(b) == host_ip,
          'room block stays id %d / IP %r after the -1 update (repair)' % (block_id(b), block_ip(b)))
    hl.send(MSG['LOBBY_MSG'], [31, [room, 64, Bin(hblk)]], rcv=G.T_SERVER)          # host re-publishes
    hl.lobby(31)
    jl.lobby(LOBBY['GROUP_INFO'])

    print('== host sends the 8-byte peer message the ELF sends on MEMBER_JOIN (ELF 0x001A0D20)')
    payload = struct.pack('<II', 2, 1)
    hw.send(MSG['PEERPLAYER'], ['JOINER', [Bin(struct.pack('<I', len(payload))), Bin(payload)]])
    pm = jw.recv(lambda m: m.type == MSG['PEERMSG'])
    check(pm.items[0] == 'HOST' and bytes(pm.items[1][1]) == payload, 'joiner receives PEERMSG from HOST with the same 8 bytes')
    expect_success(hw.recv(lambda m: m.type in (38, 39)), 91, 'host PEERPLAYER acknowledged')

    print('== host starts (UI 0xF9 after the 5 s countdown): START_GAME -> GAME_READY -> START_MATCH (ELF 0x001A33F0 / 0x001A3430)')
    hl.send(MSG['LOBBY_MSG'], [LOBBY['START_GAME'], [room, srv]], rcv=G.T_SERVER)    # online.bin 0x0071D7D0
    check(int(hl.lobby(LOBBY['START_GAME']).items[0]) == 38, 'START_GAME -> 38')
    gs = jl.lobby(LOBBY['GAME_STARTED'])
    d = gs.items[1]
    check(U32(d[0]) == room and int(d[2]) == 10070 and d[3] == host_ip, 'joiner gets GAME_STARTED [room, Bin, 10070, %s, ..]' % d[3])
    check(bytes(d[1]) == hblk, 'GAME_STARTED carries the host block (id %d, IP %r)' % (block_id(bytes(d[1])), block_ip(bytes(d[1]))))
    hl.lobby(LOBBY['GAME_STARTED'])
    jl.send(MSG['LOBBY_MSG'], [34, [room]], rcv=G.T_SERVER)             # ELF 0x001A33D0 answers GAME_STARTED with 34
    check(int(jl.lobby(34).items[0]) == 38, 'joiner GAME_CONNECTED(34) acknowledged')
    hl.send(MSG['LOBBY_MSG'], [LOBBY['GAME_READY'], [room, Bin(b''), 0, '']], rcv=G.T_SERVER)
    check(int(hl.lobby(LOBBY['GAME_READY']).items[0]) == 38, 'GAME_READY -> 38')
    hl.send(MSG['LOBBY_MSG'], [LOBBY['START_MATCH'], [room, 1]], rcv=G.T_SERVER)
    check(int(hl.lobby(LOBBY['START_MATCH']).items[0]) == 38, 'START_MATCH -> 38')
    ms = jl.lobby(LOBBY['MATCH_STARTED'])
    check(U32(ms.items[1][0]) == room, 'joiner gets MATCH_STARTED')
    hl.send(MSG['LOBBY_MSG'], [44, [room]], rcv=G.T_SERVER)             # ELF 0x001A3388 after START_MATCH
    check(int(hl.lobby(44).items[0]) == 38, 'subtype 44 acknowledged')

    print('== joiner leaves, host leaves; room disappears')
    jl.send(MSG['LOBBY_MSG'], [LOBBY['GROUP_LEAVE'], [room]], rcv=G.T_SERVER)
    jl.lobby(LOBBY['GROUP_LEAVE'])
    ml = hl.lobby(LOBBY['MEMBER_LEAVE'])
    check(ml.items[1][0] == 'JOINER', 'host gets MEMBER_LEAVE')
    for c in (hw, hl, jw, jl, host.proxy, join.proxy):
        c.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--server', help='use a running server at this address instead of starting one')
    ap.add_argument('--http-port', type=int, default=None)
    ap.add_argument('--quiet', action='store_true')
    ap.add_argument('--server-args', default='', help='extra ubilobby.py switches for the private server, e.g. "--room-update readd"')
    a = ap.parse_args()
    srv = None
    if a.server:
        http = (a.server, a.http_port or 80)
    else:
        import ubilobby
        args = ubilobby.build_args(['--bind', '127.0.0.1', '--ip', '127.0.0.1', '--http-port', '18080',
                                    '--router-port', '14000', '--no-log-file'] + a.server_args.split())
        srv = ubilobby.LobbyServer(args)
        srv.start()
        http = ('127.0.0.1', 18080)
    try:
        run(http, verbose=not a.quiet)
    except Exception as e:
        import traceback
        traceback.print_exc()
        FAILS.append('exception: %s' % e)
    finally:
        if srv:
            time.sleep(0.3)
            srv.stop()
    print('\nFAKE CLIENT RUN: %s (%d checks failed)' % ('PASSED' if not FAILS else 'FAILED', len(FAILS)))
    for f in FAILS:
        print('   -', f)
    sys.exit(1 if FAILS else 0)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""ubilobby.py - a stand-in Ubi.com (GameService) lobby for Ghost Recon: Jungle Storm (PS2, SLUS-20820).

Standard library only.  Needs gsproto.py next to it.

    python ubilobby.py --ip 192.168.68.106              run the server (HTTP 80 + GS 40000)
    python ubilobby.py --selftest                       decode the captured frames, crypto vectors
    python fakeclient.py                                two scripted consoles run the full flow on localhost

What it serves (every format below was read out of online.bin; addresses are in the comments):
  TCP 80     GET /gsinit.php?...  -> [Servers] directory (RouterIP0 = --ip)
  TCP 40000  router, wait module, lobby server and the ladder/persistent-data proxy on one port
             (every stage is recognised by its message type and header receiver, so one listener is
             enough; --wm-port / --lobby-port / --proxy-port split them if wanted)
Any username/password is accepted.  Rooms live in memory.  Every frame in and out is decoded and logged.

Protocol credits: michal-kapala/gsconnect (MIT) for the public reverse engineering of GSXor, the
message header and the data-list format; everything here was re-verified against the JS client.
"""
import argparse, datetime, os, socket, socketserver, struct, sys, threading, time, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gsproto as G
from gsproto import Bin, Message, MSG, LOBBY, LOBBY_NAME

GAME_NAME = 'GHOSTRECONIT_PS2'   # dp= in gsinit.php and the LOBBY LOGIN game name (ELF 0x00583720)
ROOM_INFO_LEN = 124              # the JS ELF drops any room whose group-info Bin is not 124 bytes (ELF 0x0019FF48)
HOST_GAME_PORT = 10070           # Red Storm net layer, host side (ELF 0x0014396C)

# ------------------------------------------------------------------ logging
_log_lock = threading.Lock()
_log_file = None


def log(tag, text):
    line = '[%s] %-14s %s' % (datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3], tag, text)
    with _log_lock:
        print(line, flush=True)
        if _log_file:
            _log_file.write(line + '\n')
            _log_file.flush()


def hexdump(data, indent='        '):
    out = []
    for i in range(0, len(data), 16):
        c = data[i:i + 16]
        out.append('%s%04x  %-48s |%s|' % (indent, i, ' '.join('%02x' % b for b in c),
                                            ''.join(chr(b) if 32 <= b < 127 else '.' for b in c)))
    return '\n'.join(out)


# ------------------------------------------------------------------ state
class Player:
    def __init__(self, name):
        self.name = name
        self.wm = None          # router / wait-module connection (PEERMSG goes here)
        self.lobby = None       # lobby-server connection (LOBBY_MSG notifications go here)
        self.ip = '0.0.0.0'
        self.player_info = b''  # SET_PLAYER_INFO (42) blob, 24 bytes from ELF 0x0019F1A0
        self.groups = set()     # lobby / room ids this player is in


class Group:
    def __init__(self, gid, name, gtype, parent, srv):
        self.id, self.name, self.type, self.parent, self.srv = gid, name, gtype, parent, srv
        self.config = 0
        self.level = 1
        self.master = ''
        self.allowed = ''
        self.games = ''
        self.info = b''
        self.event = 0
        self.max_players = 100
        self.max_visitors = 0
        self.nb_visitors = 0
        self.password = ''
        self.game_version = ''
        self.gs_version = ''
        self.alt_info = b''
        self.members = []       # names, join order
        self.started = False

    def is_room(self):
        return self.type != 0

    def record(self, st):
        """Lobby record = 14 fields (parser online.bin 0x00708970), room record = 20 fields (0x00708690)."""
        cfg = self.config | (0x1000 if self.started else 0)
        base = [self.type, self.name, self.id, self.srv, self.parent, cfg, self.level, self.master,
                self.allowed, self.games, Bin(self.info), self.event, self.max_players, len(self.members)]
        if not self.is_room():
            return base
        ip = st.player_ip(self.master)
        return base + [self.max_visitors, self.nb_visitors, self.game_version, self.gs_version, ip, ip]


class State:
    def __init__(self, args):
        self.args = args
        self.lock = threading.RLock()
        self.players = {}
        self.groups = {}
        self.next_room = 1000
        self.srv_id = 1
        self.base_id = 1
        self.rsa = G.RsaKey.generate(512, 3)    # server key pair for KEY_EXCHANGE (512-bit, e=3 like the client)
        for i, name in enumerate(args.lobby or ['Jungle Storm']):
            g = Group(10 + i, name, 0, self.base_id, self.srv_id)
            g.games = GAME_NAME
            self.groups[g.id] = g

    def player(self, name):
        p = self.players.get(name)
        if p is None:
            p = self.players[name] = Player(name)
        return p

    def player_ip(self, name):
        p = self.players.get(name)
        return p.ip if p else '0.0.0.0'

    def lobbies(self):
        return [g for g in self.groups.values() if not g.is_room()]


def local_addresses():
    addrs = {'127.0.0.1', '0.0.0.0'}
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addrs.add(info[4][0])
    except OSError:
        pass
    return addrs


def guess_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('192.0.2.1', 9))
        return s.getsockname()[0]
    except OSError:
        return '127.0.0.1'
    finally:
        s.close()


# ------------------------------------------------------------------ helpers to build replies
def B(t):
    return Bin(bytes([t & 0xFF]))


def u32le(v):
    return Bin(struct.pack('<I', v & 0xFFFFFFFF))


def as_int(x, default=0):
    try:
        return int(x)
    except (TypeError, ValueError):
        return default


def fix_room_info(info, gid, host_ip, srv, mode):
    """Make a room's 124-byte game-info block consistent with the room it belongs to.

    Layout (ELF copy helpers 0x00316BE0 / 0x003168F0 / 0x00316AB0; the host fills it, ELF 0x0019F430 sends it):
      +0x00 u32  (the host writes 1; -1 in the CREATE_ROOM block)
      +0x04 s32  room id (-1 in the CREATE_ROOM block)   <- 31's group id is read from here (0x0062ACD4)
      +0x08 char[20] host IP string                      <- joiners copy this block at JOIN (ELF 0x002FC300)
      +0x1C char[20], +0x30 char[14], +0x40 char[11] room name, +0x4B.. settings, +0x64 u32, +0x68 char[15]
    Any GROUP_INFO carrying a type-5 room record goes to ELF 0x0019F2C0, which copies +0x00/+0x04 of this
    block over the client's local room entry (and over its current-game block 0x0062ACD0 when the ids match).
    An untouched CREATE_ROOM block therefore rewrites the room id to -1 on the client; the next 31 then goes
    out with group -1.  mode: 'full' = set +4 to the room id, +0 to the server id if it is -1, and +8 to the
    host IP if empty; 'id' = only +4; 'off' = leave the block alone."""
    if mode == 'off' or len(info) != ROOM_INFO_LEN:
        return info
    b = bytearray(info)
    struct.pack_into('<i', b, 4, gid)
    if mode == 'full':
        if struct.unpack_from('<i', b, 0)[0] == -1:
            struct.pack_into('<I', b, 0, srv)
        if b[8] in (0, 0xFF) and host_ip:
            ipb = host_ip.encode('latin1')[:19]
            b[8:0x1C] = ipb + bytes(20 - len(ipb))
    return bytes(b)


def room_info_desc(info):
    if len(info) != ROOM_INFO_LEN:
        return '%d bytes' % len(info)
    a, gid = struct.unpack_from('<Ii', info, 0)
    ip = info[8:0x1C].split(b'\0')[0].decode('latin1', 'replace')
    return '+0=%d id=%d ip=%r' % (a if a != 0xFFFFFFFF else -1, gid, ip)


def fmt_short(items, n=200):
    t = G.fmt_items(items)
    return t if len(t) <= n else t[:n] + '...'


def as_str(x):
    if isinstance(x, (bytes, bytearray)):
        return bytes(x).decode('latin1')
    return x if isinstance(x, str) else ''


# ------------------------------------------------------------------ connection
class GSConnection:
    counter = 0

    def __init__(self, st, sock, addr, port):
        GSConnection.counter += 1
        self.id = GSConnection.counter
        self.st, self.sock, self.addr, self.port = st, sock, addr, port
        self.tag = 'GS#%d' % self.id
        self.bf = None              # Blowfish session (after KEY_EXCHANGE 2)
        self.client_key = None      # client RSA public key
        self.name = None
        self.role = '?'
        self.send_lock = threading.Lock()
        self.alive = True
        ip = addr[0]
        adv = st.args.map.get(ip)
        if adv is None:
            adv = st.args.ip if ip in st.local_ips else ip
        self.adv_ip = adv           # the address other consoles should use for this console

    # -------------------------------------------------- io
    def send(self, msg):
        data = G.pack(msg, self.bf)
        log(self.tag, 'SEND %-8s %s' % (self.role, msg))
        if self.st.args.hex:
            log(self.tag, 'SEND raw %d bytes\n%s' % (len(data), hexdump(data)))
        with self.send_lock:
            try:
                self.sock.sendall(data)
            except OSError as e:
                log(self.tag, 'send failed: %s' % e)

    def reply(self, req, mtype, items, prop=G.PROP_GS):
        self.send(Message(mtype, items, prop, sender=req.receiver, receiver=req.sender, priority=req.priority))

    def notify(self, mtype, items, sender=G.T_SERVER):
        self.send(Message(mtype, items, G.PROP_GS, sender=sender, receiver=G.T_PLAYER))

    def ok(self, req, *extra):
        self.reply(req, MSG['GSSUCCESS'], [B(req.type)] + list(extra))

    def fail(self, req, code=0):
        self.reply(req, MSG['GSFAIL'], [B(req.type), [u32le(code)]])

    def lobby_reply(self, req, sub, data, good=True):
        self.reply(req, MSG['LOBBY_MSG'], [38 if good else 39, [sub, data]])

    def lobby_notify(self, sub, data):
        self.notify(MSG['LOBBY_MSG'], [sub, data])

    def run(self):
        log(self.tag, 'CONNECT from %s:%d on port %d (advertised as %s)' % (self.addr[0], self.addr[1], self.port, self.adv_ip))
        buf = bytearray()
        self.sock.settimeout(self.st.args.idle or None)
        try:
            while True:
                try:
                    chunk = self.sock.recv(65536)
                except socket.timeout:
                    log(self.tag, 'idle for %ds, closing' % self.st.args.idle)
                    break
                if not chunk:
                    break
                buf += chunk
                while True:
                    try:
                        n = G.frame_size(buf)
                    except ValueError as e:
                        log(self.tag, 'BAD FRAME (%s), raw:\n%s' % (e, hexdump(bytes(buf[:256]))))
                        buf.clear()
                        break
                    if not n:
                        break
                    frame = bytes(buf[:n])
                    del buf[:n]
                    self.on_frame(frame)
        except OSError as e:
            log(self.tag, 'socket error: %s' % e)
        finally:
            self.alive = False
            try:
                self.sock.close()
            except OSError:
                pass
            log(self.tag, 'CLOSE (%s)' % (self.name or 'anonymous'))
            with self.st.lock:
                self.on_close()

    def on_frame(self, frame):
        try:
            m = G.unpack(frame, self.bf)
        except Exception as e:
            log(self.tag, 'RECV undecodable (%s) %d bytes\n%s' % (e, len(frame), hexdump(frame)))
            return
        log(self.tag, 'RECV %-8s %s' % (self.role, m))
        if self.st.args.hex:
            log(self.tag, 'RECV raw %d bytes\n%s' % (len(frame), hexdump(frame)))
        h = getattr(self, 'h_' + m.name(), None)
        with self.st.lock:
            try:
                if h:
                    h(m)
                else:
                    log(self.tag, 'no handler for %s - ignored' % m.name())
            except Exception as e:
                import traceback
                log(self.tag, 'HANDLER ERROR %s: %s\n%s' % (m.name(), e, traceback.format_exc()))

    # -------------------------------------------------- key exchange (online.bin 0x006EA410)
    def h_KEY_EXCHANGE(self, m):
        req = as_int(m.items[0]) if m.items else 0
        sub = m.items[1] if len(m.items) > 1 and isinstance(m.items[1], list) else []
        if req == 1:
            self.role = 'router' if self.role == '?' else self.role
            self.client_key = G.RsaKey.from_blob(bytes(sub[2]))
            blob = self.st.rsa.to_blob()
            self.reply(m, MSG['KEY_EXCHANGE'], [1, [1, len(blob), Bin(blob)]])
        elif req == 2:
            enc = bytes(sub[2])
            key = self.st.rsa.decrypt(enc)
            log(self.tag, 'client Blowfish key %s' % key.hex())
            # The client re-keys to whatever we send back (online.bin 0x006EA730 -> SetSessionKey 0x006EB440),
            # but it may already have sent LOGIN under its own key.  Sending its own key back removes the race.
            self.bf = G.Blowfish(key)
            back = self.client_key.encrypt(key)
            self.reply(m, MSG['KEY_EXCHANGE'], [2, [1, len(back), Bin(back)]])
        else:
            log(self.tag, 'KEY_EXCHANGE request %d ignored' % req)

    # -------------------------------------------------- router / wait module (login module, online.bin 0x007033A0..)
    def is_proxy_msg(self, m):
        # clProxyConnection sends with sender 8, receiver 11 (online.bin 0x006EC510/0x006EC968/0x006ECC1C)
        return m.receiver == G.T_PROXY or self.role in ('proxy', 'proxywm')

    def h_LOGIN(self, m):
        if self.is_proxy_msg(m):
            return self.proxy_login(m)
        # [user, password, "GRITPS21.0", Bin(1)]  sent GS_ENCRYPT (online.bin 0x00703750, ELF 0x001A6D28)
        self.name = as_str(m.items[0]) if m.items else 'player'
        self.role = 'router'
        log(self.tag, 'LOGIN user=%r password=%r version=%r -> accepted' % (
            self.name, as_str(m.items[1]) if len(m.items) > 1 else '', as_str(m.items[2]) if len(m.items) > 2 else ''))
        self.ok(m)

    def h_NEWUSERREQUEST(self, m):
        self.ok(m)

    def h_MODIFYUSER(self, m):
        self.ok(m)

    def h_JOINWAITMODULE(self, m):
        a = self.st.args
        if self.is_proxy_msg(m):
            # proxy wait module: [name, host, port as decimal string] (online.bin 0x006EC9C0: GetStr 0, GetStr 1, GetS16 2)
            self.ok(m, [self.name or 'player', a.ip, a.proxy_port])
            return
        self.ok(m, [a.ip, u32le(a.wm_port)])     # port is a 4-byte LE Bin, read with lhu (online.bin 0x00704B2C/0x00703F00)

    def h_LOGINWAITMODULE(self, m):
        if self.is_proxy_msg(m):
            self.role = 'proxywm'
            self.name = as_str(m.items[0]) if m.items else (self.name or 'player')
            self.ok(m, [])                          # online.bin 0x006EC5C0 needs element 1 to be a list
            return
        self.role = 'wm'
        self.name = as_str(m.items[0]) if m.items else (self.name or 'player')
        p = self.st.player(self.name)
        if p.wm and p.wm is not self and p.wm.alive:
            if p.wm.addr[0] != self.addr[0]:
                log(self.tag, 'WARNING two consoles use the name %r (%s and %s) - give them different names'
                    % (self.name, p.wm.addr[0], self.addr[0]))
            else:
                log(self.tag, 'replacing older wait-module connection of %s' % self.name)
        p.wm = self
        p.ip = self.adv_ip
        self.ok(m)

    def h_PLAYERINFO(self, m):
        n = self.name or ''
        self.ok(m, [n, n, '', '', '', '', ''])     # 7 strings (online.bin 0x007041D0)

    def h_LOGINFRIENDS(self, m):
        self.ok(m)

    def h_DISCONNECTFRIENDS(self, m):
        self.ok(m)

    def h_ADDFRIEND(self, m):
        self.ok(m)

    def h_DELFRIEND(self, m):
        self.ok(m)

    def h_MOTD_REQUEST(self, m):
        self.ok(m, [self.st.args.motd, ''])      # 2 strings (online.bin 0x00704F20)

    def h_STILLALIVE(self, m):
        # The client's socket receive (online.bin 0x006F7A50) stamps +0x70 = now on EVERY successful recv and
        # fails the connection (error 0x97, "Timeout: %d : %d") when now - +0x70 > +0x74; +0x74 = 180 s, set
        # from the connection's +0xC (0x006F7A40 via 0x006E8BA8; the 0xB4 passed at 0x0072BC70).  So any bytes
        # from the server keep a connection alive; the wait module received nothing after the lobby login and
        # died 180 s after its last server frame (live 05:57:25 -> 06:00:25), taking the lobby connection with it.
        # The client sends STILLALIVE itself every ~31 s (timer 0x006E93A0), so answering it is enough.
        mode = self.st.args.keepalive
        if mode == 'echo':
            self.reply(m, MSG['STILLALIVE'], [])
        elif mode == 'ok':
            self.ok(m)

    def h_PEERPLAYER(self, m):
        # [target, [Bin(u32 len), Bin(data)]]  (online.bin 0x007059D0)  ->  relay as PEERMSG to the target
        target = as_str(m.items[0]) if m.items else ''
        payload = m.items[1] if len(m.items) > 1 else []
        p = self.st.players.get(target)
        if p and p.wm and p.wm.alive:
            p.wm.notify(MSG['PEERMSG'], [self.name or '', payload], sender=G.T_ROUTER)   # parser 0x00706220
            self.ok(m, target)
        else:
            log(self.tag, 'PEERPLAYER target %r not online' % target)
            self.reply(m, MSG['GSFAIL'], [B(m.type), [target, u32le(7)]])

    # -------------------------------------------------- proxy services (ladder query, persistent data)
    # The JS lobby login does not finish until 3 ladder queries and 2 persistent-data queries come back:
    #   ELF 0x0019F5F0 (lobby LOGIN ok) -> 0x001A31E0 sends 3 ladder queries, sets counter +0x28 = 1
    #   ELF 0x001A2C60 (ladder result, counter++) -> at 4: 0x001A1C20 -> persistent query kind 0 (cb 0x001A17C0)
    #   -> kind 2 (cb 0x001A1860) -> MOTD_REQUEST -> UI message 0x118(1,0) -> lobby list.
    # A failed ladder result posts 0x118(0,0) instead (login error); a malformed one leaves the UI waiting.
    def proxy_login(self, m):
        self.role = 'proxy'
        self.name = as_str(m.items[0]) if m.items else (self.name or 'player')
        log(self.tag, 'PROXY LOGIN %s' % fmt_short(m.items))
        self.ok(m, [])                              # [B(102), []] (online.bin 0x006EC5C0 reads element 1 as a list)

    def h_PROXY_HANDLER(self, m):
        a = self.st.args
        if self.is_proxy_msg(m):
            return self.proxy_request(m)
        if not m.items or isinstance(m.items[0], list):
            # module status note the client sends after a proxy login (online.bin 0x00724AF8)
            log(self.tag, 'PROXY_HANDLER note %s - no reply' % fmt_short(m.items))
            return
        sub = as_int(m.items[0], -1)
        data = m.items[1] if len(m.items) > 1 and isinstance(m.items[1], list) else []
        if sub == 1:
            # connect module [module, '0', '0'] -> reply parsed by online.bin 0x007224F0:
            #   ok:   ['38', ['1', [module, S16, S16, [[S16 proxy id, host, S16 port], ...]]]]
            #   fail: ['39', ['1', [error, module, S16, S16]]]   (-> 0x0071FAE0 -> error dialog instead of a hang)
            module = as_str(data[0]) if data else ''
            if a.proxy == 'on':
                self.reply(m, MSG['PROXY_HANDLER'], [38, [1, [module, 0, 0, [[a.proxy_id, a.ip, a.proxy_port]]]]])
            else:
                self.reply(m, MSG['PROXY_HANDLER'], [39, [1, [a.proxy_error, module, 0, 0]]])
        elif sub == 2:
            # join proxy [id] -> ['38', ['2', [S16 id]]] (online.bin 0x007235A0 -> 0x0071F5D0 connects + LOGIN)
            pid = as_int(data[0], a.proxy_id) if data else a.proxy_id
            self.reply(m, MSG['PROXY_HANDLER'], [38, [2, [pid]]])
        else:
            log(self.tag, 'PROXY_HANDLER subtype %d - no reply' % sub)

    # Ladder fields the JS ELF reads from results (ELF 0x001A2C60): GRADE and TSCORE for the three login
    # queries; GLOBAL_RANK, ALIAS, GRADE, TSCORE, RATIO for the ladder screen.
    LADDER_FIELDS = [('GLOBAL_RANK', 'int'), ('ALIAS', 'string'), ('GRADE', 'int'), ('TSCORE', 'int'), ('RATIO', 'int')]

    def ladder_result(self, payload):
        """CLadderResults serialisation (parser online.bin 0x0072DE30):
            [U8 version = 1, [S32 total, S32 first, [[name, type], ...], [[value, ...], ...]]]
        Every row must have one value per field (FieldQtyMismatch, 0x0072D950); numeric fields must parse
        with strtol (NonNumericValue, 0x0072D420).  An EMPTY result makes the ELF's reads of row 0 / GRADE
        throw CLadderResults::OutOfBound (0x0072DB70, 0x0072DD10); in the live test that ended in
        abort() -> Exit -> OSDSYS, so by default one row per requested player is returned."""
        a = self.st.args
        if a.ladder_format == 'empty':
            return [1, [0, 0, [], []]]
        # query payload ['1', [reqid, game, S, ladder, ['2', [names...]], [[..],[..],[..]]]] (online.bin 0x00727360)
        names = []
        try:
            body = payload[1]
            flt = body[4]
            if isinstance(flt, list) and len(flt) > 1 and isinstance(flt[1], list):
                names = [as_str(n) for n in flt[1] if as_str(n)]
        except (IndexError, TypeError):
            pass
        if not names:
            names = [p for p in self.st.players] or [self.name or 'player']
        rows = []
        for i, n in enumerate(names):
            rows.append([i + 1, n[:128], a.ladder_grade, a.ladder_score, 0])
        fields = [[f, t] for f, t in self.LADDER_FIELDS]
        return [1, [len(rows), 1, fields, rows]]

    def proxy_request(self, m):
        # request [UInt type, Int seq, payload] (online.bin 0x006EC050); reply [type, seq, ['38', D]]
        # (online.bin 0x006EC690 -> CProxyHandler 0x00700550: U8 result + list D -> ['38', [type, D, seq]])
        a = self.st.args
        mtype = as_int(m.items[0], 0) if m.items else 0
        seq = as_int(m.items[1], 0) if len(m.items) > 1 else 0
        if mtype == 1281:
            d = self.ladder_result(m.items[2] if len(m.items) > 2 else [])
        elif mtype == 1537:
            # persistent data: [S16 1, [[U32 values...]]] (0x0072A780); the callback gets the count and values
            d = [1, [[0] * a.persistent_values]]
        else:
            log(self.tag, 'WARNING proxy request type %d not understood, sending an empty success' % mtype)
            d = [1, [[]]]
        if a.proxy_fail_queries:
            self.reply(m, MSG['PROXY_HANDLER'], [mtype, seq, [39, [a.proxy_error]]])
        else:
            self.reply(m, MSG['PROXY_HANDLER'], [mtype, seq, [38, d]])

    # -------------------------------------------------- lobby server login
    def h_LOBBYSERVERLOGIN(self, m):
        # [name, flag, str, str, u16]  (online.bin 0x00719230)
        self.role = 'lobby'
        self.name = as_str(m.items[0]) if m.items else (self.name or 'player')
        p = self.st.player(self.name)
        p.lobby = self
        p.ip = self.adv_ip
        self.reply(m, MSG['GSSUCCESS'], [210, [self.st.srv_id]])   # parser 0x0070C630

    # -------------------------------------------------- LOBBY_MSG
    def h_LOBBY_MSG(self, m):
        sub = as_int(m.items[0]) if m.items else -1
        data = m.items[1] if len(m.items) > 1 and isinstance(m.items[1], list) else []
        name = LOBBY_NAME.get(sub, str(sub))
        h = getattr(self, 'l_' + name, None)
        if h:
            h(m, sub, data)
        else:
            gid = as_int(data[0]) if data else 0
            log(self.tag, 'LOBBY %s: generic success' % name)
            self.lobby_reply(m, sub, [gid])

    def l_LOGIN(self, m, sub, data):
        # router level: ['21', [game]] -> ['38', ['21']], then the lobby list (GROUP_INFO, children only)
        if self.name:
            self.st.player(self.name).wm = self
        self.reply(m, MSG['LOBBY_MSG'], [38, [sub]])
        self.send_lobby_list()

    def send_lobby_list(self):
        st = self.st
        kids = [g.record(st) for g in st.lobbies()]
        self.lobby_notify(LOBBY['GROUP_INFO'], [st.base_id, 0x100, [0], kids])

    def l_JOIN_SERVER(self, m, sub, data):
        # ['3', [srv]] -> ['38', ['3', [srv, ip, port]]]  (online.bin 0x0070C8A0)
        srv = as_int(data[0]) if data else self.st.srv_id
        self.lobby_reply(m, sub, [srv, self.st.args.ip, self.st.args.lobby_port])

    def me(self):
        return self.st.player(self.name or ('conn%d' % self.id))

    def member_record(self, name, gid):
        p = self.st.players.get(name)
        ip = p.ip if p else '0.0.0.0'
        return [name, 0, ip, ip, Bin(p.player_info if p else b''), [gid], -1, 2]

    def group_info(self, g, flags):
        st = self.st
        kids = [c.record(st) for c in st.groups.values() if c.parent == g.id] if flags & 0x100 else []
        mem = [self.member_record(n, g.id) for n in g.members] if flags & 0x80 else []
        return [g.id, flags, g.record(st), kids, mem]

    def to_group(self, g, sub, data, exclude=None):
        for n in list(g.members):
            if n == exclude:
                continue
            p = self.st.players.get(n)
            if p and p.lobby and p.lobby.alive:
                p.lobby.lobby_notify(sub, data)

    def to_lobby_outside(self, g, sub, data, exclude=None):
        """Send to the members of room g's lobby who are not in g itself.

        A console counts each room's players itself, at +0x5C of its room entry: the add handler
        zeroes it (ELF 0x0019FF90), the update copy skips it (ELF 0x00316AB0), and only
        MEMBER_JOIN / MEMBER_LEAVE naming the room move it (ELF 0x001A1130 -> 0x001A0AF0 / 0x001A1330).
        The Join Game filter then drops any room whose count is below Min Players (ELF 0x00315938),
        so a lobby member that is never told about room joins sees every room as empty and hidden.
        """
        lob = self.st.groups.get(g.parent)
        if not lob:
            return
        for n in list(lob.members):
            if n == exclude or n in g.members:
                continue
            p = self.st.players.get(n)
            if p and p.lobby and p.lobby.alive:
                p.lobby.lobby_notify(sub, data)

    def member_join(self, name, gid):
        p = self.st.players.get(name)
        ip = p.ip if p else '0.0.0.0'
        info = p.player_info if p else b''
        return [name, 0, gid, ip, ip, Bin(info), -1]    # parser 0x007149B0

    def l_JOIN_LOBBY(self, m, sub, data):
        # [lobby, password, 0x1c0]  (online.bin 0x00709290, ELF 0x0019F7D0)
        gid = as_int(data[0]) if data else 0
        g = self.st.groups.get(gid)
        if not g or g.is_room():
            self.lobby_reply(m, sub, [gid, 1], good=False)
            return
        p = self.me()
        if self.name not in g.members:
            g.members.append(self.name)
        p.groups.add(gid)
        self.lobby_reply(m, sub, [gid])
        self.lobby_notify(LOBBY['GROUP_INFO'], self.group_info(g, 0x140))
        # the listing above adds each room with a player count of zero; replay who is in them
        for c in list(self.st.groups.values()):
            if c.parent == gid and c.is_room():
                for n in list(c.members):
                    if n != self.name:
                        self.lobby_notify(LOBBY['MEMBER_JOIN'], self.member_join(n, c.id))

    def l_CREATE_ROOM(self, m, sub, data):
        # [parent, name, game, type(5), max_players, max_visitors, Bin(124), password, ver, gsver, Bin]
        # (online.bin 0x00709880, ELF 0x0019EAF0)
        st = self.st
        d = data + [''] * (11 - len(data))
        parent = as_int(d[0])
        g = Group(st.next_room, as_str(d[1]) or 'room', as_int(d[3], 5) or 5, parent, st.srv_id)
        st.next_room += 1
        g.games = as_str(d[2])
        g.event = as_int(d[3], 5)
        g.max_players = as_int(d[4], 4)
        g.max_visitors = as_int(d[5], 0)
        g.info = bytes(d[6]) if isinstance(d[6], (bytes, bytearray)) else b''
        g.password = as_str(d[7])
        g.game_version = as_str(d[8])
        g.gs_version = as_str(d[9])
        g.alt_info = bytes(d[10]) if isinstance(d[10], (bytes, bytearray)) else b''
        g.master = self.name or ''
        g.config = 0x1C0 | (1 if g.password else 0)
        if len(g.info) != ROOM_INFO_LEN:
            log(self.tag, 'WARNING room info is %d bytes, the JS menu only lists 124-byte rooms' % len(g.info))
        g.info = fix_room_info(g.info, g.id, self.st.player_ip(g.master), st.srv_id, st.args.room_info_fix)
        st.groups[g.id] = g
        log(self.tag, 'ROOM %d %r created by %s (type %d, max %d, info %s)' % (
            g.id, g.name, g.master, g.type, g.max_players, g.info.hex()))
        # tell everyone in the parent lobby (creator included) BEFORE the reply: the creator's ELF
        # joins the room straight from the CREATE_ROOM callback and needs it in its room list.
        lob = st.groups.get(parent)
        rec = g.record(st)
        if lob:
            for n in list(lob.members):
                p = st.players.get(n)
                if p and p.lobby and p.lobby.alive:
                    p.lobby.lobby_notify(LOBBY['NEW_GROUP'], rec)
        else:
            self.lobby_notify(LOBBY['NEW_GROUP'], rec)
        self.lobby_reply(m, sub, [g.id, g.name, st.srv_id])

    def l_JOIN_ROOM(self, m, sub, data):
        # [room, password, flags, visitor, gsver]  (online.bin 0x00709480)
        st = self.st
        gid = as_int(data[0]) if data else 0
        g = st.groups.get(gid)
        if not g or not g.is_room():
            self.lobby_reply(m, sub, [gid, 1], good=False)
            return
        if len(g.members) >= g.max_players and self.name not in g.members:
            self.lobby_reply(m, sub, [gid, 5], good=False)
            return
        p = self.me()
        new = self.name not in g.members
        if new:
            g.members.append(self.name)
        p.groups.add(gid)
        # reply first: the ELF sets its current room (+0x144) in the JOIN_ROOM callback (ELF 0x001A0610)
        # and only treats member records of the current room as room members (ELF 0x001A1178).
        if self.st.args.info_first:            # gsconnect order (GROUP_INFO, then the reply)
            self.lobby_notify(LOBBY['GROUP_INFO'], self.group_info(g, 0x1C0))
            self.lobby_reply(m, sub, [gid])
        else:
            self.lobby_reply(m, sub, [gid])
            self.lobby_notify(LOBBY['GROUP_INFO'], self.group_info(g, 0x1C0))
        if new:
            mj = self.member_join(self.name, gid)
            self.to_group(g, LOBBY['MEMBER_JOIN'], mj, exclude=self.name)
            self.to_lobby_outside(g, LOBBY['MEMBER_JOIN'], mj, exclude=self.name)
        self.update_counts(g)

    def room_config(self, g):
        return g.config | (0x1000 if g.started else 0)

    def update_counts(self, g):
        # GROUP_CONFIG_UPDATE [group, config] (parser 0x0070EB30); the ELF reads bit 0x1000 as
        # "match in progress" (ELF 0x001A37A4).  Sent to the lobby and to the room.
        lob = self.st.groups.get(g.parent)
        cfg = [g.id, self.room_config(g)]
        if lob:
            self.to_group(lob, LOBBY['GROUP_CONFIG_UPDATE'], cfg)

    def leave(self, gid, name):
        st = self.st
        g = st.groups.get(gid)
        p = st.players.get(name)
        if p:
            p.groups.discard(gid)
        if not g or name not in g.members:
            return
        g.members.remove(name)
        self.to_group(g, LOBBY['MEMBER_LEAVE'], [name, gid])
        if g.is_room():
            self.to_lobby_outside(g, LOBBY['MEMBER_LEAVE'], [name, gid], exclude=name)
            if not g.members:
                del st.groups[gid]
                lob = st.groups.get(g.parent)
                if lob:
                    self.to_group(lob, LOBBY['GROUP_REMOVE'], [gid])
                log(self.tag, 'ROOM %d removed (empty)' % gid)
            else:
                if g.master == name:
                    g.master = g.members[0]
                    self.to_group(g, LOBBY['MASTER_CHANGED'], [gid, g.master, '', ''])
                self.update_counts(g)

    def l_GROUP_LEAVE(self, m, sub, data):
        gid = as_int(data[0]) if data else 0
        self.lobby_reply(m, sub, [gid])
        self.leave(gid, self.name)

    def l_GROUP_INFO_GET(self, m, sub, data):
        gid = as_int(data[0]) if data else 0
        flags = as_int(data[1]) if len(data) > 1 else 0x1C0
        g = self.st.groups.get(gid)
        self.lobby_reply(m, sub, [gid, 0])
        if g:
            self.lobby_notify(LOBBY['GROUP_INFO'], self.group_info(g, flags or 0x1C0))

    def l_SET_PLAYER_INFO(self, m, sub, data):
        # [Bin(24)] built by ELF 0x0019F1A0 from the player's info (0x0062AC10): [0]=+4, [1]=+0x14 READY,
        # [2]=+0x15 team (0x7B/0x7C, 0xFF none), [3..5]=+5..7, [8..19]=+8/+0xC/+0x10, [0x14]=+0x16 in-game.
        # Other consoles only learn a member's new blob from PLAYER_INFO_UPDATE (66) [name, Bin]
        # (online.bin 0x007169B0 -> ELF 0x0019F590 -> 0x0019F490 copies it into that member's info; its own
        # name is skipped).  The room screen's auto-launch (ELF 0x0030E9C0) needs every member's +0x14 set.
        p = self.me()
        if data and isinstance(data[0], (bytes, bytearray)):
            p.player_info = bytes(data[0])
        self.lobby_reply(m, sub, [])
        info = p.player_info
        if len(info) >= 3:
            log(self.tag, 'PLAYER INFO %s ready=%d team=0x%02x' % (self.name, info[1], info[2]))
        mode = self.st.args.info_broadcast
        if mode == 'none' or not self.name:
            return
        upd = [self.name, Bin(info)]
        done = set()
        for gid in sorted(p.groups):
            g = self.st.groups.get(gid)
            if not g or (not g.is_room() and mode != 'lobby'):
                continue
            for n in list(g.members):
                if n in done or (n == self.name and mode != 'room+self'):
                    continue
                done.add(n)
                q = self.st.players.get(n)
                if q and q.lobby and q.lobby.alive:
                    q.lobby.lobby_notify(LOBBY['PLAYER_INFO_UPDATE'], upd)

    def l_START_GAME(self, m, sub, data):
        gid = as_int(data[0]) if data else 0
        g = self.st.groups.get(gid)
        self.lobby_reply(m, sub, [gid])
        if g:
            g.started = True
            host = self.st.player_ip(g.master)
            log(self.tag, 'ROOM %d started by %s, host %s:%d' % (gid, self.name, host, HOST_GAME_PORT))
            self.to_group(g, LOBBY['GAME_STARTED'], [gid, Bin(g.info), HOST_GAME_PORT, host, host])   # parser 0x00711160

    def l_GAME_READY(self, m, sub, data):
        gid = as_int(data[0]) if data else 0
        self.lobby_reply(m, sub, [gid])

    def l_START_MATCH(self, m, sub, data):
        gid = as_int(data[0]) if data else 0
        self.lobby_reply(m, sub, [gid])
        g = self.st.groups.get(gid)
        if g:
            g.started = True
            self.to_group(g, LOBBY['MATCH_STARTED'], [gid, gid])     # parser 0x0070F7F0: [U32, S32]
            self.update_counts(g)

    def my_room(self):
        """The room this player hosts, else the last room he joined."""
        p = self.st.players.get(self.name or '')
        if not p:
            return None
        rooms = [self.st.groups[g] for g in sorted(p.groups) if g in self.st.groups and self.st.groups[g].is_room()]
        for g in rooms:
            if g.master == self.name:
                return g
        return rooms[-1] if rooms else None

    def l_GROUP_CONFIG_UPDATE_RES(self, m, sub, data):
        # ['31', [group, mask, Bin(124), ...]]: the host publishes its current-game block 0x0062ACD0
        # (ELF 0x0019F430 -> online.bin 0x0071D720; group = the block's +4, mask 0x40 = game data).
        # Called after the room is set up, after Server Setup and after results (ELF 0x001A174C / 0x001A26A0 /
        # 0x001A7AA8).  The reply goes to ELF 0x001A4770, which ignores it.  Group -1 means the host's block was
        # overwritten from a room record whose block still had id -1 (see fix_room_info).
        st, a = self.st, self.st.args
        gid = as_int(data[0], -1) if data else -1
        mask = as_int(data[1], 0) if len(data) > 1 else 0
        blob = data[2] if len(data) > 2 and isinstance(data[2], (bytes, bytearray)) else None
        g = st.groups.get(gid)
        if (g is None or not g.is_room()) and a.cfg_unknown == 'repair':
            g = self.my_room()
            if g:
                log(self.tag, 'GROUP CONFIG for group %d from %s: applying it to his room %d' % (gid, self.name, g.id))
        self.lobby_reply(m, sub, [gid])
        if not g or not g.is_room():
            return
        if blob is not None and mask & 0x40:
            new = bytes(blob)
            if len(new) == ROOM_INFO_LEN and new[8] in (0, 0xFF) and len(g.info) == ROOM_INFO_LEN:
                new = new[:8] + g.info[8:0x1C] + new[0x1C:]          # keep the host IP we already had
            new = fix_room_info(new, g.id, st.player_ip(g.master), st.srv_id, a.room_info_fix)
            changed = new != g.info
            g.info = new
            log(self.tag, 'ROOM %d game info %s (%s)' % (g.id, room_info_desc(new), 'changed' if changed else 'same'))
            if changed:
                self.room_changed(g)
        self.update_counts(g)

    def room_changed(self, g):
        """Push a room's new record (with its game-info block) to the lobby and to the room.
        GROUP_INFO [room, 0x40, record, [], []]: flag 0x40 = record only (online.bin 0x007138F4); a type-5
        record goes to ELF 0x0019F2C0 = update the local room entry (and the current-game block of members)."""
        st, mode = self.st, self.st.args.room_update
        if mode == 'none':
            return
        rec = g.record(st)
        lob = st.groups.get(g.parent)
        names = list(dict.fromkeys((lob.members if lob else []) + g.members))
        for n in names:
            if n == self.name and not st.args.room_update_self:
                continue
            p = st.players.get(n)
            if not (p and p.lobby and p.lobby.alive):
                continue
            if mode == 'readd' and n not in g.members:
                p.lobby.lobby_notify(LOBBY['GROUP_REMOVE'], [g.id])      # ELF 0x001A0520
                p.lobby.lobby_notify(LOBBY['NEW_GROUP'], rec)            # ELF 0x0019FEC0 (new entry, id from record)
            else:
                p.lobby.lobby_notify(LOBBY['GROUP_INFO'], [g.id, 0x40, rec, [], []])

    # -------------------------------------------------- disconnect
    def on_close(self):
        if not self.name:
            return
        p = self.st.players.get(self.name)
        if not p:
            return
        if p.lobby is self:
            p.lobby = None
            for gid in sorted(p.groups, reverse=True):
                self.leave(gid, self.name)
        if p.wm is self:
            p.wm = None
        if not p.wm and not p.lobby:
            del self.st.players[self.name]


# ------------------------------------------------------------------ servers
class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_gs_server(st, host, port):
    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            GSConnection(st, self.request, self.client_address, self.server.server_address[1]).run()
    return ThreadingTCPServer((host, port), Handler)


def gsinit_body(args):
    ip = args.ip
    lines = ['[Servers]',
             'RouterIP0=%s' % ip, 'RouterPort0=%d' % args.router_port,
             'RouterLauncherPort0=%d' % args.router_port,
             'IRCIP0=%s' % ip, 'IRCPort0=6667',
             'NATServerIP0=%s' % ip, 'NATServerPort0=45000',
             'ProxyIP0=%s' % ip, 'ProxyPort0=%d' % args.router_port,
             'CDKeyServerIP0=%s' % ip, 'CDKeyServerPort0=5778', '']
    return '\r\n'.join(lines).encode()


def make_http_server(st, host, port):
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            tag = 'HTTP'
            try:
                self.request.settimeout(10)
                req = self.rfile.readline(4096).decode('latin1', 'replace').strip()
                headers = []
                while True:
                    l = self.rfile.readline(4096)
                    if not l or l in (b'\r\n', b'\n'):
                        break
                    headers.append(l.decode('latin1', 'replace').strip())
            except OSError:
                return
            log(tag, '%s:%d  %s  %s' % (self.client_address[0], self.client_address[1], req, ' | '.join(headers)))
            parts = req.split()
            path = parts[1] if len(parts) > 1 else '/'
            u = urllib.parse.urlsplit(path)
            if u.path.lower().endswith('gsinit.php'):
                q = urllib.parse.parse_qs(u.query)
                body = gsinit_body(st.args)
                log(tag, 'gsinit for dp=%s user=%s -> %d bytes' % (q.get('dp', ['?'])[0], q.get('user', ['-'])[0], len(body)))
                code = '200 OK'
            else:
                body, code = b'not found', '404 Not Found'
            head = 'HTTP/1.1 %s\r\nContent-Type: text/plain\r\nContent-Length: %d\r\nConnection: close\r\n\r\n' % (code, len(body))
            try:
                self.wfile.write(head.encode() + body)
            except OSError:
                pass
    return ThreadingTCPServer((host, port), Handler)


def build_args(argv=None):
    ap = argparse.ArgumentParser(description='Stand-in Ubi.com lobby for Ghost Recon: Jungle Storm (PS2)')
    ap.add_argument('--ip', help='address both consoles reach this PC at (default: auto)')
    ap.add_argument('--bind', default='0.0.0.0')
    ap.add_argument('--http-port', type=int, default=80)
    ap.add_argument('--router-port', type=int, default=40000)
    ap.add_argument('--wm-port', type=int, default=None, help='wait module port (default: router port)')
    ap.add_argument('--lobby-port', type=int, default=None, help='lobby server port (default: router port)')
    ap.add_argument('--lobby', action='append', help='lobby name (repeatable, default "Jungle Storm")')
    ap.add_argument('--map', action='append', default=[], metavar='SEEN=ADVERTISED',
                    help='advertise a different address for a console, e.g. 192.168.1.20=10.147.17.5')
    ap.add_argument('--motd', default='Welcome to the stand-in Ubi.com lobby')
    ap.add_argument('--proxy', choices=['on', 'fail'], default='on',
                    help='ladder/persistent-data proxy: on = serve it (needed to reach the lobby list), '
                         'fail = refuse module connects with a well-formed error (error dialog instead of a hang)')
    ap.add_argument('--proxy-port', type=int, default=None, help='proxy port (default: router port)')
    ap.add_argument('--proxy-id', type=int, default=1)
    ap.add_argument('--persistent-values', type=int, default=1,
                    help='number of values returned for each persistent-data query (default 1)')
    ap.add_argument('--proxy-fail-queries', action='store_true', help='answer every proxy query with failure (39)')
    ap.add_argument('--ladder-format', choices=['rows', 'empty'], default='rows',
                    help='ladder results: rows = one row per requested player with GLOBAL_RANK/ALIAS/GRADE/TSCORE/RATIO '
                         '(default); empty = no rows (v2 behaviour, crashed the console to the BIOS)')
    ap.add_argument('--ladder-grade', type=int, default=0, help='GRADE value in ladder rows (default 0)')
    ap.add_argument('--ladder-score', type=int, default=0, help='TSCORE value in ladder rows (default 0)')
    ap.add_argument('--proxy-error', type=int, default=1)
    ap.add_argument('--idle', type=int, default=0, help='close a GS connection after this many silent seconds (0 = never)')
    ap.add_argument('--info-first', action='store_true',
                    help='on JOIN_ROOM send the room GROUP_INFO before the reply (gsconnect order) instead of after')
    ap.add_argument('--keepalive', choices=('echo', 'ok', 'none'), default='echo',
                    help='answer the client STILLALIVE heartbeat: echo it (default), GSSUCCESS, or ignore '
                         '(ignoring it lets the client drop the wait module 180 s after the last server frame)')
    ap.add_argument('--info-broadcast', choices=('room', 'room+self', 'lobby', 'none'), default='room',
                    help='on SET_PLAYER_INFO(42) send PLAYER_INFO_UPDATE(66) [name, Bin] to the other members of '
                         'the sender\'s rooms (default), also to the sender, also to lobby members, or not at all')
    ap.add_argument('--room-info-fix', choices=('full', 'id', 'off'), default='full',
                    help='keep a room\'s 124-byte game-info block consistent: full = room id at +4, server id at +0 '
                         'if -1, host IP at +8 if empty (default); id = only +4; off = store blocks untouched (v3)')
    ap.add_argument('--room-update', choices=('info', 'readd', 'none'), default='info',
                    help='after the host\'s 31 changes the game-info block: GROUP_INFO [room,0x40,record] to lobby '
                         'and room members (default); readd = GROUP_REMOVE+NEW_GROUP to lobby members outside the '
                         'room (GROUP_INFO to the room); none = do not notify (v3)')
    ap.add_argument('--room-update-self', action='store_true', help='also send that update to the host itself')
    ap.add_argument('--cfg-unknown', choices=('repair', 'ignore'), default='repair',
                    help='31 for group -1 / an unknown group: apply it to the sender\'s room (default) or ignore it')
    ap.add_argument('--hex', action='store_true', help='also hex-dump every frame')
    ap.add_argument('--log', default=None, help='log file (default: ubilobby-<time>.log next to this script)')
    ap.add_argument('--no-log-file', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args(argv)
    a.ip = a.ip or guess_ip()
    a.wm_port = a.wm_port or a.router_port
    a.lobby_port = a.lobby_port or a.router_port
    a.proxy_port = a.proxy_port or a.router_port
    a.map = dict(x.split('=', 1) for x in a.map)
    return a


class LobbyServer:
    """Starts every listener in background threads; used by main() and by fakeclient.py."""

    def __init__(self, args):
        self.args = args
        self.st = State(args)
        self.st.local_ips = local_addresses()
        self.servers = []

    def start(self):
        a = self.args
        self.servers.append(('HTTP', make_http_server(self.st, a.bind, a.http_port)))
        ports = sorted({a.router_port, a.wm_port, a.lobby_port, a.proxy_port})
        for p in ports:
            self.servers.append(('GS', make_gs_server(self.st, a.bind, p)))
        for kind, s in self.servers:
            threading.Thread(target=s.serve_forever, daemon=True).start()
            log('main', '%s listening on %s:%d' % (kind, *s.server_address))
        log('main', 'advertising %s  (router %d, wait module %d, lobby %d, proxy %d [%s])' % (
            a.ip, a.router_port, a.wm_port, a.lobby_port, a.proxy_port, a.proxy))

    def stop(self):
        for kind, s in self.servers:
            s.shutdown()
            s.server_close()
        log('main', 'stopped')


def selftest():
    here = os.path.dirname(os.path.abspath(__file__))
    ok = True
    frames = [os.path.join(here, 'js_frame.bin')]
    rs3 = r'E:\PS2 Games\R6_3_PS2_CutContent\netcap'
    for n in ('login_frame.bin', 'login_frame_2.bin', 'login_frame_3.bin', 'register_frame.bin'):
        frames.append(os.path.join(rs3, n))
    for fn in frames:
        if not os.path.exists(fn):
            print('skip (missing)', fn)
            continue
        raw = open(fn, 'rb').read()
        m = G.unpack(raw)
        good = (m.type == MSG['KEY_EXCHANGE'] and m.items[0] == '1' and m.items[1][0] == '1' and m.items[1][1] == '260'
                and len(m.items[1][2]) == 260 and G.pack(m) == raw)
        k = G.RsaKey.from_blob(bytes(m.items[1][2]))
        print('%-5s %-60s %s  | client RSA %d bits, e=%d' % ('OK' if good else 'FAIL', os.path.basename(fn), m, k.bits, k.e))
        print('      plaintext: %s' % m.plain[:40].hex(' ') + ' ...')
        ok &= good
    # the real JS frame through the server's own connection handler
    class FakeSock:
        def __init__(self):
            self.out = b''
        def sendall(self, d):
            self.out += d
    args = build_args(['--ip', '192.168.68.106', '--no-log-file'])
    st = State(args)
    st.local_ips = {'127.0.0.1'}
    raw = open(frames[0], 'rb').read()
    fs = FakeSock()
    conn = GSConnection(st, fs, ('192.168.68.106', 52273), 40000)
    conn.on_frame(raw)
    r = G.unpack(fs.out)
    blob = bytes(r.items[1][2])
    v = (r.type == MSG['KEY_EXCHANGE'] and r.items[0] == '1' and r.items[1][0] == '1' and int(r.items[1][1]) == 260
         and len(blob) == 260 and G.RsaKey.from_blob(blob).bits == 512 and r.sender == 2 and r.receiver == 8)
    print('%-5s captured JS KEY_EXCHANGE -> server reply %s' % ('OK' if v else 'FAIL', r)); ok &= v
    # the exact 77-byte gsinit request from capture-20260927-025544.log, through the HTTP handler
    req = b'GET /gsinit.php?dp=GHOSTRECONIT_PS2 HTTP/1.1\r\nHOST: gsconnect.ubisoft.com\r\n\r\n'
    http = make_http_server(st, '127.0.0.1', 0)
    threading.Thread(target=http.serve_forever, daemon=True).start()
    c = socket.create_connection(http.server_address, timeout=5)
    c.sendall(req)
    resp = b''
    while True:
        d = c.recv(4096)
        if not d:
            break
        resp += d
    c.close()
    http.shutdown(); http.server_close()
    head, _, body = resp.partition(b'\r\n\r\n')
    v = head.startswith(b'HTTP/1.1 200') and body.startswith(b'[Servers]\r\nRouterIP0=192.168.68.106\r\nRouterPort0=40000')
    print('%-5s PS2 gsinit request (%d bytes) -> %d-byte [Servers] answer' % ('OK' if v else 'FAIL', len(req), len(body))); ok &= v
    bf = G.Blowfish(b'TESTKEY')
    v = bf._enc(1, 2) == (0xDF333FD2, 0x30A71BB4)
    print('%-5s Blowfish core (Kocher vector)' % ('OK' if v else 'FAIL')); ok &= v
    ct = G.Blowfish(b'SKJDHF$0maoijfn4i8$aJdnv1jaldifar93-AS_dfo;hjhC4jhflasnF3fnd').encrypt(b's2\0s1\0s1\0[]')
    v = ct.hex() == 'a322b12d73409fa3f4fcf80a03f171d20b00'
    print('%-5s Blowfish GS wrapper (LE halves + u16 length trailer)' % ('OK' if v else 'FAIL')); ok &= v
    key = os.urandom(16)
    k = G.RsaKey.generate(512)
    v = k.decrypt(k.encrypt(key)) == key
    print('%-5s RSA PKCS#1 v1.5 round trip' % ('OK' if v else 'FAIL')); ok &= v
    v = all(G.gsxor_decrypt(G.gsxor_encrypt(os.urandom(n))) is not None for n in (1, 2, 3, 50, 278, 999))
    for n in (1, 7, 64, 278, 1000):
        x = os.urandom(n)
        v &= G.gsxor_decrypt(G.gsxor_encrypt(x)) == x
    print('%-5s GSXor round trip' % ('OK' if v else 'FAIL')); ok &= v
    # room game-info block: the live CREATE_ROOM block (ffffffff ffffffff 00..) and the live host 31 block
    # (01000000 e8030000 "192.168.68.106"), log ubilobby-20260927-050502.log 05:57:58
    created = bytes.fromhex('ffffffffffffffff') + bytes(116)
    host31 = bytes.fromhex('01000000e8030000') + b'192.168.68.106'.ljust(20, b'\0') + bytes(96)
    f1 = fix_room_info(created, 1000, '192.168.68.106', 1, 'full')
    v = f1 == host31 and fix_room_info(host31, 1000, '10.0.0.9', 1, 'full') == host31 \
        and fix_room_info(created, 1000, '1.2.3.4', 1, 'off') == created
    print('%-5s room block fix: CREATE_ROOM block -> %s (same as the host\'s own 31 block)' % ('OK' if v else 'FAIL', room_info_desc(f1))); ok &= v
    print('SELFTEST', 'PASSED' if ok else 'FAILED')
    return ok


def main():
    global _log_file
    args = build_args()
    if args.selftest:
        sys.exit(0 if selftest() else 1)
    if not args.no_log_file:
        fn = args.log or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      'ubilobby-%s.log' % datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
        _log_file = open(fn, 'a', encoding='utf-8')
        log('main', 'logging to %s' % fn)
    srv = LobbyServer(args)
    try:
        srv.start()
    except OSError as e:
        log('main', 'cannot listen: %s  (port 80 needs a free port and, on Windows, may need an admin prompt)' % e)
        sys.exit(1)
    log('main', 'ready - point gsconnect.ubisoft.com at %s in PCSX2 and pick ONLINE.  Ctrl+C to stop.' % args.ip)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        srv.stop()


if __name__ == '__main__':
    main()

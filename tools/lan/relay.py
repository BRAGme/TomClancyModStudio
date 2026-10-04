#!/usr/bin/env python3
"""relay.py - let a player on another network (e.g. Radmin VPN) join a Jungle Storm game hosted by a console
that sits on this PC's TAP adapter.

Standard library only.

    python relay.py --public 26.209.25.36 --inside 10.20.30.1 --console 10.20.30.2

Why it is needed
----------------
PCSX2's Sockets network mode cannot accept incoming TCP, so a console that HOSTS must use TAP; a TAP console
lives on its own little network (here 10.20.30.0/24) that nobody outside this PC can route to. This relay
stands on the public address in its place:

  TCP  public:10070            -> console:10070        the joiner's reliable channel (its only inbound TCP)
  UDP  public:10070..10079     <-> console:same port   the game stream (10070) and a second channel (10074)

What was measured (2026-09-29, two consoles on one PC, capture on the TAP link + PCSX2's DEV9 log):
  * the joiner opens two UDP ports P and P+1 per game, and SENDS FIRST on each: P -> host 10070,
    P+1 -> host 10074 ("Creating New UDP Connection from fixed port 53035 to 10070");
  * the host then streams UDP from its 10070 to the joiner's P (about 13 packets/s in play).
So the relay learns a joiner's port from its first packet and opens a mirror socket on the inside with the
SAME port number (Sockets mode keeps the console's own port, so the number the joiner's console reports
in-game is the number the host console will send to). The host console therefore always talks to
inside:P, never to a Radmin address it could not reach.

Pair it with the lobby server run as
    ubilobby.py --ip 10.20.30.1 --advertise local --map 10.20.30.2=26.209.25.36 --map "*=10.20.30.1"
so the joiner is told the host is at the public address (this relay) and the host console is told every
remote player is at the inside address (this relay's mirror sockets).

Limits: every remote player reaches the host console from the one inside address, so two remote players
whose consoles pick the same UDP port number collide (the second gets a substitute port and a warning).
"""
import argparse
import datetime
import select
import socket
import sys
import threading
import time

_lock = threading.Lock()
_logf = None


def log(text):
    line = '[%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3], text)
    with _lock:
        print(line, flush=True)
        if _logf:
            _logf.write(line + '\n')
            _logf.flush()


def ports(spec):
    out = []
    for part in spec.split(','):
        if '-' in part:
            a, b = part.split('-')
            out += list(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


# ------------------------------------------------------------------ TCP
class TcpRelay(threading.Thread):
    def __init__(self, args, port):
        super().__init__(daemon=True)
        self.a, self.port = args, port
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.bind((args.public, port))
        self.srv.listen(8)
        log('TCP  listening on %s:%d -> %s:%d' % (args.public, port, args.console, port))

    def run(self):
        while True:
            try:
                c, peer = self.srv.accept()
            except (ConnectionResetError, ConnectionAbortedError):
                continue                        # a caller that gave up before we accepted
            except OSError:
                return
            threading.Thread(target=self.serve, args=(c, peer), daemon=True).start()

    def serve(self, c, peer):
        a = self.a
        deadline = time.time() + a.connect_wait
        while True:
            try:
                u = socket.create_connection((a.console, self.port), timeout=3, source_address=(a.inside, 0))
                break
            except OSError as e:
                if time.time() >= deadline:     # the host console may open its port a moment after the joiner dials
                    log('TCP  %s:%d -> console:%d FAILED for %ds: %s' % (peer[0], peer[1], self.port, a.connect_wait, e))
                    c.close()
                    return
                time.sleep(0.5)
        u.settimeout(None)
        for s in (c, u):
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        log('TCP  %s:%d  <->  %s:%d  (from %s:%d)' % (peer[0], peer[1], a.console, self.port, *u.getsockname()))
        counts = [0, 0]
        back = threading.Thread(target=self.pump, args=(u, c, counts, 1), daemon=True)
        back.start()
        self.pump(c, u, counts, 0)
        back.join()
        c.close()
        u.close()
        log('TCP  %s:%d closed  (joiner->host %d bytes, host->joiner %d bytes)' % (peer[0], peer[1], *counts))

    @staticmethod
    def pump(src, dst, counts, i):
        """One direction. When src finishes cleanly, pass the end on (half-close) and let the other direction run
        until it finishes too, as a direct connection would; on a reset, end both directions."""
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
                counts[i] += len(data)
            dst.shutdown(socket.SHUT_WR)
        except OSError:
            for s in (src, dst):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass


# ------------------------------------------------------------------ UDP
class UdpRelay:
    """public:H sockets face the joiners; one inside socket per joiner port mirrors that port number."""

    MAX_MIRRORS = 64                   # joiner ports at once (2 per player); keeps select() far below its limit

    def __init__(self, args, udp_ports):
        self.a = args
        self.pub = {}                  # host port H -> public socket
        self.mirror = {}               # (joiner ip, joiner port) -> inside socket
        self.owner = {}                # inside socket -> (joiner ip, joiner port)
        self.last = {}                 # inside socket -> last activity
        self.stats = {}                # (joiner ip, joiner port) -> [to host, to joiner]
        self.dropped = 0
        self.next_error_log = 0.0
        for h in udp_ports:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.bind((args.public, h))
            self.pub[h] = s
        log('UDP  listening on %s:%s -> %s:same' % (args.public, ','.join(str(h) for h in udp_ports), args.console))

    def error(self, what, e):
        """Count a dropped packet; say so at most every 10 s (a closed TAP adapter fails every packet)."""
        self.dropped += 1
        now = time.time()
        if now >= self.next_error_log:
            log('UDP  %s failed: %s  (%d packets dropped so far; is the host PCSX2 running on the TAP adapter?)'
                % (what, e, self.dropped))
            self.next_error_log = now + 10

    def inside_for(self, joiner):
        m = self.mirror.get(joiner)
        if m:
            return m
        if len(self.mirror) >= self.MAX_MIRRORS:
            self.error('a new joiner port %s:%d (already %d)' % (joiner[0], joiner[1], len(self.mirror)), 'too many')
            return None
        m = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            m.bind((self.a.inside, joiner[1]))
            note = 'mirrors its port'
        except OSError as e:
            try:
                m.bind((self.a.inside, 0))
            except OSError as e2:
                m.close()
                self.error('opening an inside port for %s:%d' % joiner, e2)
                return None
            note = 'PORT %d BUSY (%s), using %d -- replies may not arrive' % (joiner[1], e, m.getsockname()[1])
        self.mirror[joiner], self.owner[m] = m, joiner
        self.stats[joiner] = [0, 0]
        log('UDP  new joiner %s:%d  -> inside %s:%d  (%s)' % (joiner[0], joiner[1], *m.getsockname(), note))
        return m

    def run(self):
        self.next_report = time.time() + 10
        while True:
            try:
                self.step()
            except Exception as e:              # nothing may end UDP relaying while TCP carries on
                log('UDP  ERROR %s: %s -- carrying on' % (type(e).__name__, e))
                time.sleep(0.5)

    def step(self):
        socks = list(self.pub.values()) + list(self.owner)
        r, _, _ = select.select(socks, [], [], 1.0)
        now = time.time()
        for s in r:
            try:
                data, src = s.recvfrom(65536)
            except OSError:
                continue                # e.g. ICMP port unreachable reported on Windows as WSAECONNRESET
            if s in self.owner:                             # host console -> joiner
                joiner = self.owner[s]
                out = self.pub.get(src[1]) or next(iter(self.pub.values()))
                try:
                    out.sendto(data, joiner)
                except OSError as e:
                    self.error('host -> %s:%d' % joiner, e)
                    continue
                self.stats[joiner][1] += 1
                self.last[s] = now
            else:                                           # joiner -> host console
                h = s.getsockname()[1]
                m = self.inside_for(src)
                if m is None:
                    continue
                try:
                    m.sendto(data, (self.a.console, h))
                except OSError as e:
                    self.error('%s:%d -> host' % src, e)
                    continue
                self.stats[src][0] += 1
                self.last[m] = now
        for m, t in list(self.last.items()):
            if now - t > self.a.idle:
                joiner = self.owner.pop(m)
                self.mirror.pop(joiner, None)
                self.last.pop(m, None)
                log('UDP  joiner %s:%d idle %ds, closed  (to host %d, to joiner %d packets)' % (
                    joiner[0], joiner[1], self.a.idle, *self.stats.pop(joiner, [0, 0])))
                m.close()
        if now >= self.next_report and self.stats:
            log('UDP  ' + '; '.join('%s:%d up %d down %d' % (j[0], j[1], *c) for j, c in self.stats.items()))
            self.next_report = now + 10


def main(argv=None):
    global _logf
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--public', required=True, help='address the remote player reaches this PC at (e.g. Radmin)')
    ap.add_argument('--inside', required=True, help="this PC's address on the TAP link (e.g. 10.20.30.1)")
    ap.add_argument('--console', required=True, help="the hosting console's TAP address (e.g. 10.20.30.2)")
    ap.add_argument('--tcp', default='10070', help='TCP ports to relay (default 10070)')
    ap.add_argument('--udp', default='10070-10079', help='UDP ports to relay (default 10070-10079)')
    ap.add_argument('--idle', type=int, default=600, help='seconds before an idle UDP joiner port is forgotten '
                    '(the joiner opens its second port in the room, well before the game)')
    ap.add_argument('--connect-wait', type=int, default=15,
                    help='seconds to keep trying the host console for a joiner\'s TCP before giving up')
    ap.add_argument('--log', default='', help='also append the log to this file')
    a = ap.parse_args(argv)
    if a.log:
        _logf = open(a.log, 'a', encoding='utf-8')
    for p in ports(a.tcp):
        TcpRelay(a, p).start()
    udp = UdpRelay(a, ports(a.udp))
    threading.Thread(target=udp.run, daemon=True).start()
    log('ready - remote players join the host console %s through %s.  Ctrl+C to stop.' % (a.console, a.public))
    try:
        while True:
            time.sleep(0.5)                 # sleep, not join: Ctrl+C is only seen between sleeps on Windows
    except KeyboardInterrupt:
        log('stopped')
    return 0


if __name__ == '__main__':
    sys.exit(main())

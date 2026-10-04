#!/usr/bin/env python3
"""test_relay.py - relay.py end to end on loopback addresses only (safe to run while a real game is live).

    127.0.0.40  fake remote joiner   (a player on Radmin)
    127.0.0.10  relay --public
    127.0.0.20  relay --inside       (this PC on the TAP link)
    127.0.0.30  fake host console    (the TAP console)

It reproduces the traffic measured on the TAP link on 2026-09-29: the joiner sends first from P to host 10070
and from P+1 to host 10074, opens TCP to host 10070, and the host then streams UDP from 10070 to the joiner's
P. The property everything rests on: the host console sees the joiner's UDP arrive from the SAME port number
the joiner used, so the port the joiner's console reports in-game is one the host can answer.
"""
import os
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import relay  # noqa: E402

JOINER, PUBLIC, INSIDE, CONSOLE = '127.0.0.40', '127.0.0.10', '127.0.0.20', '127.0.0.30'
fails = []


def check(cond, what):
    print(('   ok   ' if cond else '   FAIL ') + what)
    if not cond:
        fails.append(what)


def udp(ip, port, timeout=2.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((ip, port))
    s.settimeout(timeout)
    return s


def recv(s):
    try:
        return s.recvfrom(65536)
    except (socket.timeout, OSError):
        return None, None


def main():
    # fake host console: records where UDP came from, answers it, then streams to it unprompted
    seen = {}
    c10070, c10074 = udp(CONSOLE, 10070, 5), udp(CONSOLE, 10074, 5)

    def console_udp(s, tag):
        data, src = recv(s)
        if data is None:
            return
        seen[tag] = src
        s.sendto(b'reply-' + data, src)
        time.sleep(0.2)
        s.sendto(b'stream-' + tag.encode(), src)     # the host's own traffic to the joiner's port
    for s, tag in ((c10070, '10070'), (c10074, '10074')):
        threading.Thread(target=console_udp, args=(s, tag), daemon=True).start()

    ctcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ctcp.bind((CONSOLE, 10070))
    ctcp.listen(1)

    def console_tcp():
        conn, peer = ctcp.accept()
        seen['tcp'] = peer
        data = conn.recv(100)
        conn.sendall(b'echo-' + data)
        time.sleep(0.5)
        conn.close()
    threading.Thread(target=console_tcp, daemon=True).start()

    # the relay itself, in-process
    threading.Thread(target=relay.main, args=(['--public', PUBLIC, '--inside', INSIDE, '--console', CONSOLE,
                                               '--tcp', '10070', '--udp', '10070-10074', '--idle', '3'],),
                     daemon=True).start()
    time.sleep(0.5)

    print('== the joiner sends first, P -> 10070 and P+1 -> 10074 (as its DEV9 log shows)')
    j1, j2 = udp(JOINER, 53035), udp(JOINER, 53036)
    j1.sendto(b'hello', (PUBLIC, 10070))
    j2.sendto(b'probe', (PUBLIC, 10074))
    r1, s1 = recv(j1)
    r2, s2 = recv(j2)
    time.sleep(0.1)
    check(seen.get('10070') == (INSIDE, 53035),
          'host console sees the joiner at the inside address with the SAME port: %s' % (seen.get('10070'),))
    check(seen.get('10074') == (INSIDE, 53036), 'and the second channel likewise: %s' % (seen.get('10074'),))
    check(r1 == b'reply-hello' and s1 == (PUBLIC, 10070),
          'joiner gets the host reply from public:10070 (where it thinks the host is): %r from %s' % (r1, s1))
    check(r2 == b'reply-probe' and s2 == (PUBLIC, 10074), 'and from public:10074 on the second channel')
    st1, ss1 = recv(j1)
    check(st1 == b'stream-10070' and ss1 == (PUBLIC, 10070),
          'the host console\'s unprompted stream to the joiner\'s port arrives too: %r' % (st1,))

    print('== the joiner opens its TCP channel to host 10070')
    t = socket.create_connection((PUBLIC, 10070), timeout=3, source_address=(JOINER, 0))
    t.sendall(b'join')
    got = t.recv(100)
    check(got == b'echo-join', 'TCP round trip through the relay: %r' % got)
    check(seen.get('tcp', ('',))[0] == INSIDE, 'host console sees the TCP from the inside address: %s' % (seen.get('tcp'),))
    t.close()

    print('== a joiner port already taken on the inside falls back without crashing')
    blocker = udp(INSIDE, 53037)
    j3 = udp(JOINER, 53037)
    c3 = udp(CONSOLE, 10071, 3)
    j3.sendto(b'x', (PUBLIC, 10071))
    d3, s3 = recv(c3)
    check(d3 == b'x' and s3[0] == INSIDE and s3[1] != 53037,
          'packet still delivered, from a substitute inside port: %s' % (s3,))
    blocker.close()

    print('== idle joiners are forgotten')
    time.sleep(4.5)
    j1.sendto(b'again', (PUBLIC, 10070))
    time.sleep(0.3)
    print('\nRELAY TEST: %s (%d checks failed)' % ('PASSED' if not fails else 'FAILED', len(fails)))
    for f in fails:
        print('   - ' + f)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())

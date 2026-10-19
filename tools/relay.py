#!/usr/bin/env python3
"""TCP relay: listen on 127.0.0.1:5277 and forward every connection to the phone's
Wi-Fi address, so Android Auto sees the peer as a *different* host (the Mac)."""
import socket
import threading
import sys

LISTEN = ("127.0.0.1", 5277)
if len(sys.argv) < 2:
    raise SystemExit("Usage: python3 tools/relay.py <PHONE_IP>")
TARGET = (sys.argv[1], 5277)


def pipe(a, b):
    try:
        while True:
            data = a.recv(65536)
            if not data:
                break
            b.sendall(data)
    except OSError:
        pass
    finally:
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def handle(client, addr, n):
    print(f"[relay] conn #{n} from {addr} -> {TARGET}", flush=True)
    try:
        up = socket.create_connection(TARGET, timeout=10)
    except OSError as e:
        print(f"[relay] upstream failed: {e}", flush=True)
        client.close()
        return
    threading.Thread(target=pipe, args=(client, up), daemon=True).start()
    threading.Thread(target=pipe, args=(up, client), daemon=True).start()


def main():
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(LISTEN)
    srv.listen(8)
    print(f"[relay] listening on {LISTEN[0]}:{LISTEN[1]} -> {TARGET}", flush=True)
    n = 0
    while True:
        c, a = srv.accept()
        n += 1
        threading.Thread(target=handle, args=(c, a, n), daemon=True).start()


main()

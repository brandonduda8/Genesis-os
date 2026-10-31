"""Test lab: a real local HTTP forward proxy that can be killed and healed, plus local upstream endpoints.

Everything here uses real sockets on 127.0.0.1. It is a lab stand-in for the zane-box egress router, NOT evidence
about the router itself. The real heal-window proof is owed on zane-box (see the P5 receipt).
"""
from __future__ import annotations

import json
import os
import socket
import socketserver
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Upstream(BaseHTTPRequestHandler):
    mode = {"status": 200}

    def log_message(self, *a):
        pass

    def _reply(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._reply(self.mode["status"], b'{"zen":"Keep it logically awesome."}')

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        self.rfile.read(n)
        self._reply(self.mode["status"], json.dumps({"choices": [{"message": {"content": "p"}}]}).encode())


def start_upstream(status=200):
    Upstream.mode = {"status": status}
    srv = HTTPServer(("127.0.0.1", 0), Upstream)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class _Proxy(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class ProxyHandler(socketserver.StreamRequestHandler):
    """Absolute-URI HTTP forward proxy (what the client sends for http:// targets through a proxy)."""

    def handle(self):
        if self.server.behaviour == "hang":  # accept, then never answer: the 15 s-stall shape
            time.sleep(30)
            return
        line = self.rfile.readline().decode()
        headers = b""
        while True:
            h = self.rfile.readline()
            headers += h
            if h in (b"\r\n", b""):
                break
        self.server.requests.append(line.strip())
        if self.server.behaviour == "429":
            self.wfile.write(b"HTTP/1.1 429 Too Many Requests\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            return
        method, url, _ = line.split()
        from urllib.parse import urlsplit
        u = urlsplit(url)
        length = 0
        for l in headers.decode().split("\r\n"):
            if l.lower().startswith("content-length:"):
                length = int(l.split(":")[1])
        body = self.rfile.read(length) if length else b""
        try:
            up = socket.create_connection((u.hostname, u.port), timeout=5)
        except OSError:
            self.wfile.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            return
        up.sendall(f"{method} {u.path or '/'} HTTP/1.1\r\nHost: {u.hostname}\r\nConnection: close\r\n"
                   f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
        while True:
            chunk = up.recv(65536)
            if not chunk:
                break
            self.wfile.write(chunk)
        up.close()


def start_proxy(behaviour="ok"):
    srv = _Proxy(("127.0.0.1", 0), ProxyHandler)
    srv.behaviour, srv.requests = behaviour, []
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


LAB_KEY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_lab_nim.key")  # a dummy, not a credential
if not os.path.exists(LAB_KEY):
    with open(LAB_KEY, "w") as _f:
        _f.write("lab-dummy-key-not-a-secret\n")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def trio_for(upstream_port):
    base = f"http://127.0.0.1:{upstream_port}"
    return {"github": {"url": base + "/zen"}, "pip": {"url": base + "/simple/pip/"},
            "nim": {"url": base + "/v1/chat/completions", "model": "lab", "key_file": LAB_KEY}}

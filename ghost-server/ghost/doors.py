"""Doors (module 3): pluggable transports, each with health probes, a circuit breaker, and per-door stats.

Every request has ONE hard deadline (default 5 s) covering DNS + connect + proxy CONNECT + TLS + response, unlike
per-socket timeouts which can add up to 15 s. A door is HEALED only when the acceptance trio (GitHub GET, NIM
completion, pip fetch) passes through it in one round. Any 429 is a hard stop: breaker open >= 15 min, no retry.
Doors are Brandon's own machines/networks only; this module has no circumvention features by design.
"""
from __future__ import annotations

import collections
import json
import socket
import time
from typing import Any, Callable, Deque, Dict, Optional, Tuple
from urllib.parse import urlsplit

DEADLINE_S = 5.0
MAX_BODY = 65536
FAILS_TO_OPEN = 3
COOLDOWN_MIN_S, COOLDOWN_MAX_S, RATE_LIMIT_COOLDOWN_S = 60.0, 900.0, 900.0
CLOSED, OPEN, HALF_OPEN = "CLOSED", "OPEN", "HALF_OPEN"


class DoorError(Exception):
    def __init__(self, error_class: str, msg: str = ""):
        super().__init__(f"{error_class}: {msg}" if msg else error_class)
        self.error_class = error_class


def _read_until(sock: socket.socket, marker: bytes, remaining: Callable[[], float], limit: int = 65536) -> bytes:
    buf = b""
    while marker not in buf:
        sock.settimeout(remaining())
        chunk = sock.recv(4096)
        if not chunk:
            break
        buf += chunk
        if len(buf) > limit:
            raise DoorError("protocol", "header too large")
    return buf


def _dechunk(body: bytes) -> bytes:
    out, rest = b"", body
    while rest:
        line, _, rest = rest.partition(b"\r\n")
        try:
            size = int(line.split(b";")[0], 16)
        except ValueError:
            break
        if size == 0:
            break
        out, rest = out + rest[:size], rest[size + 2:]
    return out


def http_request(url: str, *, method: str = "GET", body: Optional[bytes] = None,
                 headers: Optional[Dict[str, str]] = None, proxy: Optional[str] = None,
                 proxy_token: Optional[str] = None, deadline_s: float = DEADLINE_S,
                 max_body: int = MAX_BODY) -> Tuple[int, Dict[str, str], bytes, float]:
    """Minimal HTTP/1.1 client with a single total deadline. Returns (status, headers, body<=max_body, seconds)."""
    t0 = time.monotonic()
    t_end = t0 + deadline_s

    def remaining() -> float:
        r = t_end - time.monotonic()
        if r <= 0:
            raise DoorError("timeout", f"deadline {deadline_s:g}s exceeded")
        return r

    u = urlsplit(url)
    https = u.scheme == "https"
    host, port = u.hostname or "", u.port or (443 if https else 80)
    path = (u.path or "/") + (f"?{u.query}" if u.query else "")
    auth = {"Proxy-Authorization": "Bearer " + proxy_token} if proxy_token else {}
    sock: Optional[socket.socket] = None
    try:
        try:
            if proxy:
                p = urlsplit(proxy)
                sock = socket.create_connection((p.hostname, p.port or 80), timeout=remaining())
                if https:
                    req = f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n" + \
                          "".join(f"{k}: {v}\r\n" for k, v in auth.items()) + "\r\n"
                    sock.settimeout(remaining())
                    sock.sendall(req.encode())
                    head = _read_until(sock, b"\r\n\r\n", remaining)
                    status_line = head.split(b"\r\n", 1)[0].split()
                    if len(status_line) < 2 or status_line[1] != b"200":
                        code = status_line[1].decode() if len(status_line) > 1 else "?"
                        raise DoorError("rate_limited" if code == "429" else "proxy_refused", f"CONNECT -> {code}")
                    target = path
                else:
                    target = url
            else:
                sock = socket.create_connection((host, port), timeout=remaining())
                target = path
            if https:
                import ssl  # lazy: keeps idle RSS low
                ctx = ssl.create_default_context()
                sock.settimeout(remaining())
                sock = ctx.wrap_socket(sock, server_hostname=host)
            hdrs = {"Host": host, "User-Agent": "ghost-server/2", "Accept": "*/*", "Connection": "close",
                    **(headers or {}), **({} if https or not proxy else auth)}
            if body is not None:
                hdrs["Content-Length"] = str(len(body))
            raw = f"{method} {target} HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in hdrs.items()) + "\r\n"
            sock.settimeout(remaining())
            sock.sendall(raw.encode() + (body or b""))
            buf = _read_until(sock, b"\r\n\r\n", remaining)
            head, _, rest = buf.partition(b"\r\n\r\n")
            lines = head.decode("iso-8859-1").split("\r\n")
            parts = lines[0].split()
            if len(parts) < 2 or not parts[1].isdigit():
                raise DoorError("protocol", "bad status line")
            status = int(parts[1])
            rh = {k.strip().lower(): v.strip() for k, _, v in (l.partition(":") for l in lines[1:])}
            want = min(max_body, int(rh.get("content-length", max_body)))
            while len(rest) < want:
                sock.settimeout(remaining())
                chunk = sock.recv(min(65536, want - len(rest) + 16))
                if not chunk:
                    break
                rest += chunk
            if rh.get("transfer-encoding", "").lower() == "chunked":
                rest = _dechunk(rest)
            return status, rh, rest[:max_body], time.monotonic() - t0
        except DoorError:
            raise
        except socket.timeout as exc:
            raise DoorError("timeout", str(exc)) from exc
        except socket.gaierror as exc:
            raise DoorError("dns", str(exc)) from exc
        except ConnectionRefusedError as exc:
            raise DoorError("refused", str(exc)) from exc
        except OSError as exc:
            cls = "tls" if exc.__class__.__module__ == "ssl" else "network"
            raise DoorError(cls, str(exc)) from exc
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def tcp_probe(host: str, port: int, deadline_s: float = DEADLINE_S) -> Dict[str, Any]:
    t0 = time.monotonic()
    if not host:
        return {"ok": False, "error_class": "unconfigured", "ms": 0}
    try:
        with socket.create_connection((host, int(port)), timeout=deadline_s):
            return {"ok": True, "error_class": "", "ms": round((time.monotonic() - t0) * 1000)}
    except socket.timeout:
        return {"ok": False, "error_class": "timeout", "ms": round((time.monotonic() - t0) * 1000)}
    except ConnectionRefusedError:
        return {"ok": False, "error_class": "refused", "ms": round((time.monotonic() - t0) * 1000)}
    except OSError as exc:
        return {"ok": False, "error_class": "dns" if isinstance(exc, socket.gaierror) else "network",
                "ms": round((time.monotonic() - t0) * 1000)}


def _status_class(status: int) -> str:
    if status == 429:
        return "rate_limited"
    return "" if 200 <= status < 300 else ("http_4xx" if status < 500 else "http_5xx")


class Door:
    def __init__(self, name: str, kind: str = "direct", proxy_url: Optional[str] = None,
                 token_file: Optional[str] = None, trio: Optional[Dict[str, Any]] = None,
                 clock: Callable[[], float] = time.time, deadline_s: float = DEADLINE_S):
        if kind not in ("direct", "http_proxy"):
            raise ValueError(f"unknown door kind {kind!r}")
        self.name, self.kind, self.proxy_url, self.token_file = name, kind, proxy_url, token_file
        self.trio, self.clock, self.deadline_s = trio or {}, clock, deadline_s
        self.breaker, self.failures, self.open_until, self.cooldown = CLOSED, 0, 0.0, COOLDOWN_MIN_S
        self.stats: Deque[Tuple[bool, str, float]] = collections.deque(maxlen=64)
        self.last_trio: Dict[str, Any] = {}

    def _token(self) -> Optional[str]:
        if not self.token_file:
            return None
        return open(self.token_file).read().strip()  # read at call time; never logged or stored

    # ---------------------------------------------------------------- breaker
    def allow(self) -> bool:
        now = self.clock()
        if self.breaker == OPEN and now >= self.open_until:
            self.breaker = HALF_OPEN
        return self.breaker != OPEN

    def _record(self, ok: bool, error_class: str, seconds: float) -> None:
        self.stats.append((ok, error_class, seconds))
        now = self.clock()
        if ok:
            self.breaker, self.failures, self.cooldown = CLOSED, 0, COOLDOWN_MIN_S
            return
        self.failures += 1
        if error_class == "rate_limited":
            self.breaker, self.open_until = OPEN, now + max(RATE_LIMIT_COOLDOWN_S, self.cooldown)
        elif self.breaker == HALF_OPEN or self.failures >= FAILS_TO_OPEN:
            self.breaker, self.open_until = OPEN, now + self.cooldown
            self.cooldown = min(COOLDOWN_MAX_S, self.cooldown * 2)

    # ---------------------------------------------------------------- traffic
    def request(self, url: str, **kw: Any) -> Tuple[int, Dict[str, str], bytes, float]:
        if not self.allow():
            raise DoorError("breaker_open", f"{self.name} open until {self.open_until:.0f}")
        t0 = time.monotonic()
        try:
            status, h, b, secs = http_request(url, proxy=self.proxy_url if self.kind == "http_proxy" else None,
                                              proxy_token=self._token(), deadline_s=self.deadline_s, **kw)
        except DoorError as exc:
            exc.seconds = time.monotonic() - t0  # type: ignore[attr-defined]
            self._record(False, exc.error_class, exc.seconds)  # type: ignore[attr-defined]
            raise
        cls = _status_class(status)
        self._record(not cls, cls, secs)
        return status, h, b, secs

    def _leg(self, name: str) -> Dict[str, Any]:
        cfg = self.trio.get(name) or {}
        if not cfg.get("url"):
            return {"ok": False, "error_class": "unconfigured", "ms": 0}
        try:
            if name == "nim":
                key = open(cfg["key_file"]).read().strip() if cfg.get("key_file") else ""
                hdr = {"Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})}
                payload = json.dumps({"model": cfg.get("model", ""), "max_tokens": 1,
                                      "messages": [{"role": "user", "content": "ping"}]}).encode()
                status, _, body, secs = self.request(cfg["url"], method="POST", body=payload, headers=hdr)
                ok = status == 200 and b'"choices"' in body
                cls = _status_class(status) or ("" if ok else "bad_response")
            else:
                status, _, body, secs = self.request(cfg["url"])
                ok, cls = 200 <= status < 300, _status_class(status)
            return {"ok": ok, "status": status, "error_class": cls, "ms": round(secs * 1000)}
        except DoorError as exc:
            return {"ok": False, "error_class": exc.error_class, "ms": round(getattr(exc, "seconds", 0.0) * 1000)}

    def probe_trio(self) -> Dict[str, Any]:
        """One round: GitHub GET, NIM completion, pip fetch. HEALED only if all three pass through this door."""
        legs: Dict[str, Any] = {}
        for leg in ("github", "nim", "pip"):
            legs[leg] = self._leg(leg)
            if legs[leg]["error_class"] in ("rate_limited", "breaker_open"):
                break  # hard stop: never push more requests into a 429 or an open breaker
        passed = sum(1 for v in legs.values() if v["ok"])
        verdict = "HEALED" if passed == 3 else ("PARTIAL" if passed else "DARK")
        self.last_trio = {"door": self.name, "verdict": verdict, "healed": verdict == "HEALED", "legs": legs,
                          "at": self.clock(), "breaker": self.breaker}
        return self.last_trio

    def snapshot(self) -> Dict[str, Any]:
        lat = sorted(s for ok, _, s in self.stats if ok)
        pct = lambda q: round(lat[min(len(lat) - 1, int(q * len(lat)))] * 1000) if lat else None  # noqa: E731
        errs = collections.Counter(c for ok, c, _ in self.stats if not ok)
        return {"name": self.name, "kind": self.kind, "breaker": self.breaker, "open_until": self.open_until,
                "samples": len(self.stats), "ok": sum(1 for ok, _, _ in self.stats if ok), "errors": dict(errs),
                "p50_ms": pct(0.5), "p95_ms": pct(0.95), "last_trio": self.last_trio}


def load_doors(path: str, clock: Callable[[], float] = time.time) -> Dict[str, Door]:
    cfg = json.load(open(path))
    trio = cfg.get("trio", {})
    out = {}
    for d in cfg.get("doors", []):
        if d.get("enabled", True):
            out[d["name"]] = Door(d["name"], d.get("kind", "direct"), d.get("proxy_url"), d.get("token_file"),
                                  trio=d.get("trio", trio), clock=clock, deadline_s=float(d.get("deadline_s", DEADLINE_S)))
    return out

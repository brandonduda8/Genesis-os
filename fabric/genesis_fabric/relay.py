"""The relay: verifies, stores ciphertext durably, delivers, deletes only on the recipient's signed ack.

  python3 -m genesis_fabric.relay --db /var/lib/genesis-fabric/relay.db --registry registry.json --bind 127.0.0.1:7801

It holds no key that decrypts anything. SQLite WAL + synchronous=FULL; a crash before ack means redelivery
(clients dedupe by id). Expiry writes a receipt; nothing is dropped silently.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Optional

from .crypto import FabricError
from .envelope import check, check_request
from .identity import Registry

TTL_S = 7 * 86400
MAX_BODY = 1 << 20

SCHEMA = """
CREATE TABLE IF NOT EXISTS queue (recipient TEXT NOT NULL, id TEXT NOT NULL, sender TEXT NOT NULL, env TEXT NOT NULL,
  enq REAL NOT NULL, PRIMARY KEY (recipient, id));
CREATE TABLE IF NOT EXISTS seen (sender TEXT NOT NULL, id TEXT NOT NULL, ts REAL NOT NULL, PRIMARY KEY (sender, id));
CREATE TABLE IF NOT EXISTS presence (name TEXT PRIMARY KEY, last_fetch REAL NOT NULL);
CREATE TABLE IF NOT EXISTS receipts (id TEXT NOT NULL, recipient TEXT NOT NULL, event TEXT NOT NULL, ts REAL NOT NULL);
"""


class Relay:
    def __init__(self, db_path: str, registry: Registry, clock: Callable[[], float] = time.time):
        self.reg, self.clock, self.lock = registry, clock, threading.Lock()
        self.db = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    def accept(self, env: Dict[str, Any]) -> str:
        now = self.clock()
        check(env, self.reg, now)
        to = env["to"]
        self.reg.get(to, now)  # recipient must be a live identity too
        with self.lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                if self.db.execute("SELECT 1 FROM seen WHERE sender=? AND id=?", (env["from"], env["id"])).fetchone():
                    self.db.execute("ROLLBACK")
                    raise FabricError("replay refused")
                self.db.execute("INSERT INTO seen VALUES (?,?,?)", (env["from"], env["id"], now))
                self.db.execute("INSERT INTO queue VALUES (?,?,?,?,?)", (to, env["id"], env["from"],
                                                                         json.dumps(env), now))
                self.db.execute("COMMIT")
            except sqlite3.Error:
                self.db.execute("ROLLBACK")
                raise
        return env["id"]

    def fetch(self, name: str, limit: int = 100) -> List[Dict[str, Any]]:
        now = self.clock()
        with self.lock:
            self.db.execute("INSERT INTO presence VALUES (?,?) ON CONFLICT(name) DO UPDATE SET last_fetch=excluded.last_fetch",
                            (name, now))
            rows = self.db.execute("SELECT env FROM queue WHERE recipient=? ORDER BY rowid LIMIT ?", (name, limit)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def ack(self, name: str, ids: List[str]) -> int:
        now = self.clock()
        n = 0
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            for i in ids:
                n += self.db.execute("DELETE FROM queue WHERE recipient=? AND id=?", (name, i)).rowcount
                self.db.execute("INSERT INTO receipts VALUES (?,?,?,?)", (i, name, "delivered", now))
            self.db.execute("COMMIT")
        return n

    def expire(self) -> int:
        now = self.clock()
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            old = self.db.execute("SELECT id, recipient FROM queue WHERE enq < ?", (now - TTL_S,)).fetchall()
            for i, r in old:
                self.db.execute("INSERT INTO receipts VALUES (?,?,?,?)", (i, r, "expired", now))
            self.db.execute("DELETE FROM queue WHERE enq < ?", (now - TTL_S,))
            self.db.execute("COMMIT")
        return len(old)

    def presence(self) -> Dict[str, Optional[float]]:
        now = self.clock()
        seen = dict(self.db.execute("SELECT name, last_fetch FROM presence").fetchall())
        return {n: (round(now - seen[n]) if n in seen else None) for n in self.reg.names()}

    def depth(self, name: Optional[str] = None) -> int:
        q = "SELECT COUNT(*) FROM queue" + (" WHERE recipient=?" if name else "")
        return self.db.execute(q, (name,) if name else ()).fetchone()[0]


def make_handler(relay: Relay):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet; receipts live in the DB
            pass

        def _reply(self, code: int, obj: Any) -> None:
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/v1/presence":
                return self._reply(200, {"presence_age_s": relay.presence()})
            if self.path == "/v1/health":
                return self._reply(200, {"ok": True, "queued": relay.depth()})
            self._reply(404, {"error": "no such route"})

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                return self._reply(413, {"error": "too large"})
            body = self.rfile.read(n)
            try:
                if self.path == "/v1/send":
                    return self._reply(200, {"id": relay.accept(json.loads(body))})
                name = check_request(dict(self.headers), relay.reg, "POST", self.path, body, relay.clock())
                if self.path == "/v1/fetch":
                    return self._reply(200, {"envelopes": relay.fetch(name)})
                if self.path == "/v1/ack":
                    return self._reply(200, {"acked": relay.ack(name, json.loads(body)["ids"])})
                self._reply(404, {"error": "no such route"})
            except (FabricError, ValueError, KeyError) as e:
                self._reply(403, {"error": str(e)})
    return H


def serve(relay: Relay, host: str, port: int) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer((host, port), make_handler(relay))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--registry", required=True)
    ap.add_argument("--bind", default="127.0.0.1:7801")
    a = ap.parse_args()
    host, port = a.bind.rsplit(":", 1)
    relay = Relay(a.db, Registry(json.load(open(a.registry))))
    srv = ThreadingHTTPServer((host, int(port)), make_handler(relay))
    print(f"genesis-fabric relay on {host}:{port}, {relay.depth()} queued")
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

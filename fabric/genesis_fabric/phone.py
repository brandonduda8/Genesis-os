"""The phone: the client kit every agent runtime plugs into. Pair (with a PIN ceremony), send, poll, rooms.

    phone = Phone("drain", keys, registry, [HttpTransport("http://s1:7801"), HttpTransport("http://zane-box:7801")])
    pin = phone.pair_begin("zane")       # show this to the operator; the other side shows theirs
    phone.pair_confirm("zane", typed)    # wrong PIN -> pairing destroyed (fail-closed)
    phone.send("zane", {"hello": 1}); phone.poll()

Sends go to EVERY reachable relay; polls read every relay; envelopes are deduped by (from, id). No GitHub, ever.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
import uuid
from typing import Any, Callable, Dict, List, Optional

from . import crypto as C
from .crypto import Chain, FabricError, Keys, canon, hkdf
from .envelope import check, header, make, sign_request
from .identity import Registry

PAIR_TIMEOUT_S = 600


class LocalTransport:
    """In-process relay access (tests, same-host agents)."""

    def __init__(self, relay):
        self.relay, self.name = relay, getattr(relay, "label", "local")

    def send(self, env, keys, me, now):
        return self.relay.accept(env)

    def fetch(self, keys, me, now):
        return self.relay.fetch(me)

    def ack(self, keys, me, ids, now):
        return self.relay.ack(me, ids)


class HttpTransport:
    def __init__(self, base: str, timeout: float = 5.0):
        self.base, self.timeout, self.name = base.rstrip("/"), timeout, base

    def _post(self, path: str, body: bytes, headers: Dict[str, str]) -> Any:
        req = urllib.request.Request(self.base + path, data=body, method="POST",
                                     headers={"Content-Type": "application/json", **headers})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read())

    def send(self, env, keys, me, now):
        return self._post("/v1/send", json.dumps(env).encode(), {})["id"]

    def fetch(self, keys, me, now):
        return self._post("/v1/fetch", b"{}", sign_request(keys, me, "POST", "/v1/fetch", b"{}", now))["envelopes"]

    def ack(self, keys, me, ids, now):
        body = json.dumps({"ids": ids}).encode()
        return self._post("/v1/ack", body, sign_request(keys, me, "POST", "/v1/ack", body, now))["acked"]


class Phone:
    def __init__(self, name: str, keys: Keys, registry: Registry, transports: List[Any],
                 clock: Callable[[], float] = time.time, state_path: Optional[str] = None):
        self.me, self.keys, self.reg, self.transports, self.clock = name, keys, registry, transports, clock
        self.state_path = state_path
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.rooms: Dict[str, Dict[str, Any]] = {}
        self.seen: Dict[str, float] = {}
        self.handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {}
        if state_path and os.path.exists(state_path):
            self._load()

    # ---------- persistence (0600, atomic) ----------
    def save(self) -> None:
        if not self.state_path:
            return
        doc = {"sessions": {p: {**s, "root": C.b64(s["root"]), "send": s["send"].state(), "recv": s["recv"].state()}
                            for p, s in self.sessions.items()},
               "rooms": {r: {**v, "keys": {e: C.b64(k) for e, k in v["keys"].items()}} for r, v in self.rooms.items()},
               "seen": self.seen}
        tmp = self.state_path + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(doc, f)
        os.replace(tmp, self.state_path)

    def _load(self) -> None:
        with open(self.state_path) as f:
            doc = json.load(f)
        self.sessions = {p: {**s, "root": C.unb64(s["root"]), "send": Chain.from_state(s["send"]),
                             "recv": Chain.from_state(s["recv"])} for p, s in doc["sessions"].items()}
        self.rooms = {r: {**v, "keys": {e: C.unb64(k) for e, k in v["keys"].items()}} for r, v in doc["rooms"].items()}
        self.seen = doc.get("seen", {})

    # ---------- pairing + PIN ceremony ----------
    def _root(self, peer: str) -> bytes:
        rec = self.reg.get(peer, self.clock())
        a, b = sorted([self.me, peer])
        return hkdf(self.keys.dh(rec["x25519"]), salt=f"{a}|{b}".encode(), info=b"genesis-fabric/pair/v1")

    def pair_begin(self, peer: str) -> str:
        if peer == self.me:
            raise FabricError("cannot pair with yourself")
        root = self._root(peer)
        self.sessions[peer] = {"root": root, "state": "PENDING", "local_ok": False, "peer_ok": False,
                               "began": self.clock(),
                               "send": Chain(hkdf(root, info=f"chain:{self.me}>{peer}".encode())),
                               "recv": Chain(hkdf(root, info=f"chain:{peer}>{self.me}".encode()))}
        self.save()
        return C.pin_from_root(root)

    def _destroy(self, peer: str, why: str) -> None:
        self.sessions.pop(peer, None)
        self.save()
        raise FabricError(f"pairing with {peer} destroyed: {why}")

    def pair_confirm(self, peer: str, typed_pin: str) -> None:
        s = self.sessions.get(peer)
        if not s or s["state"] != "PENDING":
            raise FabricError(f"no pending pairing with {peer}")
        if self.clock() - s["began"] > PAIR_TIMEOUT_S:
            self._destroy(peer, "PIN ceremony timed out")
        if not C.constant_eq(typed_pin, C.pin_from_root(s["root"])):
            self._destroy(peer, "PIN mismatch: possible interception; re-pair from scratch")
        s["local_ok"] = True
        ack_key = hkdf(s["root"], info=f"ack:{self.me}".encode())
        env = make(self.keys, sender=self.me, to=peer, kind="pairack", hdr={}, now=self.clock(),
                   ct_fn=lambda aad: C.seal(ack_key, 0, self.me.encode(), aad))
        self._activate_if_ready(peer)
        self._push(env)

    def _on_pairack(self, env: Dict[str, Any]) -> None:
        peer = env["from"]
        s = self.sessions.get(peer)
        if not s or s["state"] not in ("PENDING", "ACTIVE"):
            return  # no ceremony in progress: ignore
        ack_key = hkdf(s["root"], info=f"ack:{peer}".encode())
        if C.open_(ack_key, 0, env["ct"], canon(header(env))) != peer.encode():
            raise FabricError("bad pair ack")
        s["peer_ok"] = True
        self._activate_if_ready(peer)

    def _activate_if_ready(self, peer: str) -> None:
        s = self.sessions[peer]
        if s["local_ok"] and s["peer_ok"]:
            s["state"] = "ACTIVE"
        self.save()

    def _active(self, peer: str) -> Dict[str, Any]:
        s = self.sessions.get(peer)
        if not s or s["state"] != "ACTIVE":
            raise FabricError(f"no ACTIVE session with {peer}: complete the PIN ceremony first")
        return s

    # ---------- send / receive ----------
    def attach_guard(self, guard) -> None:
        """Route stop/restart envelopes to the agent's Guard (which verifies both keys and persists locally)."""
        self.handlers["stop"] = self.handlers["restart"] = guard.on_envelope

    def _push(self, env: Dict[str, Any]) -> List[str]:
        ok, errs = [], []
        for t in self.transports:
            try:
                t.send(env, self.keys, self.me, self.clock())
                ok.append(t.name)
            except Exception as e:  # noqa: BLE001 - a dark relay is expected; record and try the next
                errs.append(f"{t.name}: {e}")
        if not ok:
            raise FabricError("no relay accepted the envelope: " + "; ".join(errs))
        return ok

    def send(self, peer: str, body: Any, kind: str = "dm") -> Dict[str, Any]:
        s = self._active(peer)
        n, mk = s["send"].next_send()
        self.save()  # the used key is gone from state before the ciphertext leaves
        env = make(self.keys, sender=self.me, to=peer, kind=kind, hdr={"n": n}, now=self.clock(),
                   ct_fn=lambda aad: C.seal(mk, n, json.dumps(body).encode(), aad))
        return {"id": env["id"], "relays": self._push(env)}

    def poll(self) -> List[Dict[str, Any]]:
        out = []
        for t in self.transports:
            try:
                envs = t.fetch(self.keys, self.me, self.clock())
            except Exception:  # noqa: BLE001 - dark relay: the others carry the load
                continue
            done = []
            for env in envs:
                key = f"{env.get('from')}:{env.get('id')}"
                if key in self.seen:
                    done.append(env["id"])
                    continue
                try:
                    msg = self._receive(env)
                except FabricError as e:
                    msg = {"from": env.get("from"), "kind": "rejected", "error": str(e)}
                self.seen[key] = self.clock()
                done.append(env["id"])
                if msg:
                    out.append(msg)
            if done:
                t.ack(self.keys, self.me, done, self.clock())
        self.save()
        return out

    def _receive(self, env: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        check(env, self.reg, self.clock())
        if env["to"] != self.me:
            raise FabricError("envelope not addressed to me")
        kind = env["kind"]
        if kind == "pairack":
            self._on_pairack(env)
            return {"from": env["from"], "kind": "pairack"}
        if kind in ("stop", "restart"):
            if kind not in self.handlers:
                raise FabricError("estop envelope received but no Guard is attached to this phone")
            return self.handlers[kind](env)
        if kind == "room":
            return self._on_room(env)
        s = self._active(env["from"])
        n = env["hdr"]["n"]
        mk = s["recv"].key_for(n)
        body = json.loads(C.open_(mk, n, env["ct"], canon(header(env))))
        if kind == "roomkey":
            self.rooms[body["room"]] = self.rooms.get(body["room"], {"owner": env["from"], "keys": {},
                                                                     "members": body["members"]})
            r = self.rooms[body["room"]]
            if r["owner"] != env["from"]:
                raise FabricError("only the room owner distributes room keys")
            r["keys"][str(body["epoch"])] = C.unb64(body["key"])
            r["epoch"], r["members"] = body["epoch"], body["members"]
            return {"from": env["from"], "kind": "roomkey", "room": body["room"], "epoch": body["epoch"]}
        return {"from": env["from"], "kind": kind, "body": body, "id": env["id"]}

    # ---------- rooms ----------
    def room_create(self, room: str, members: List[str]) -> None:
        self.rooms[room] = {"owner": self.me, "members": sorted(set(members) | {self.me}), "keys": {}, "epoch": 0}
        self._room_rekey(room)

    def _room_rekey(self, room: str) -> None:
        r = self.rooms[room]
        r["epoch"] = r.get("epoch", 0) + 1 if r["keys"] else 1
        key = os.urandom(32)
        r["keys"][str(r["epoch"])] = key
        for m in r["members"]:
            if m != self.me:
                self.send(m, {"room": room, "epoch": r["epoch"], "key": C.b64(key), "members": r["members"]},
                          kind="roomkey")
        self.save()

    def room_remove(self, room: str, member: str) -> None:
        r = self.rooms[room]
        if r["owner"] != self.me:
            raise FabricError("only the owner removes members")
        r["members"] = [m for m in r["members"] if m != member]
        self._room_rekey(room)

    def room_send(self, room: str, body: Any) -> str:
        r = self.rooms.get(room)
        if not r or self.me not in r["members"]:
            raise FabricError(f"not a member of {room}")
        epoch, mid = r["epoch"], uuid.uuid4().hex
        mk = hkdf(r["keys"][str(epoch)], salt=mid.encode(), info=f"room:{room}".encode())
        for m in r["members"]:
            if m == self.me:
                continue
            env = make(self.keys, sender=self.me, to=m, kind="room", hdr={"room": room, "epoch": epoch, "mid": mid},
                       now=self.clock(), ct_fn=lambda aad: C.seal(mk, 0, json.dumps(body).encode(), aad))
            self._push(env)
        return mid

    def _on_room(self, env: Dict[str, Any]) -> Dict[str, Any]:
        h = env["hdr"]
        r = self.rooms.get(h["room"])
        if not r or str(h["epoch"]) not in r["keys"]:
            raise FabricError(f"no key for room {h['room']} epoch {h['epoch']}")
        if env["from"] not in r["members"]:
            raise FabricError("sender is not a room member")
        mk = hkdf(r["keys"][str(h["epoch"])], salt=h["mid"].encode(), info=f"room:{h['room']}".encode())
        body = json.loads(C.open_(mk, 0, env["ct"], canon(header(env))))
        return {"from": env["from"], "kind": "room", "room": h["room"], "body": body}

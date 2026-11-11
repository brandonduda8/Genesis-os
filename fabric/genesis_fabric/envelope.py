"""Signed envelopes and signed requests. The relay and every client verify with the same code."""
from __future__ import annotations

import hashlib
import uuid
from typing import Any, Dict, Optional

from .crypto import FabricError, Keys, canon, verify
from .identity import Registry

SKEW_S = 300
KINDS = ("dm", "pairack", "roomkey", "room", "stop", "restart")


def header(env: Dict[str, Any]) -> Dict[str, Any]:
    """Everything the sender signs, minus the signature itself. Also the AEAD's associated data."""
    return {k: env[k] for k in ("v", "id", "from", "to", "ts", "kind", "hdr")}


def make(keys: Keys, *, sender: str, to: str, kind: str, hdr: Dict[str, Any], now: float,
         ct_fn=None, env_id: Optional[str] = None) -> Dict[str, Any]:
    if kind not in KINDS:
        raise FabricError(f"unknown kind {kind}")
    env = {"v": 1, "id": env_id or uuid.uuid4().hex, "from": sender, "to": to, "ts": int(now), "kind": kind,
           "hdr": hdr}
    env["ct"] = ct_fn(canon(header(env))) if ct_fn else None
    env["sig"] = keys.sign(canon({**header(env), "ct": env["ct"]}))
    return env


def check(env: Dict[str, Any], reg: Registry, now: float) -> Dict[str, Any]:
    """Return the sender's record, or raise. Does NOT check replay (stateful; the caller does)."""
    for k in ("v", "id", "from", "to", "ts", "kind", "hdr", "ct", "sig"):
        if k not in env:
            raise FabricError(f"envelope missing {k}")
    if env["v"] != 1 or env["kind"] not in KINDS:
        raise FabricError("unsupported envelope")
    rec = reg.get(env["from"], now)
    if abs(now - env["ts"]) > SKEW_S:
        raise FabricError("envelope outside the clock window")
    if not verify(rec["ed25519"], canon({**header(env), "ct": env["ct"]}), env["sig"]):
        raise FabricError("bad envelope signature")
    return rec


def sign_request(keys: Keys, name: str, method: str, path: str, body: bytes, now: float) -> Dict[str, str]:
    ts = str(int(now))
    msg = f"{method}|{path}|{ts}|{hashlib.sha256(body).hexdigest()}".encode()
    return {"X-Fabric-Name": name, "X-Fabric-Ts": ts, "X-Fabric-Sig": keys.sign(msg)}


def check_request(headers: Dict[str, str], reg: Registry, method: str, path: str, body: bytes, now: float) -> str:
    name, ts, sig = headers.get("X-Fabric-Name"), headers.get("X-Fabric-Ts"), headers.get("X-Fabric-Sig")
    if not (name and ts and sig and ts.isdigit()):
        raise FabricError("unsigned request")
    if abs(now - int(ts)) > SKEW_S:
        raise FabricError("request outside the clock window")
    rec = reg.get(name, now)
    msg = f"{method}|{path}|{ts}|{hashlib.sha256(body).hexdigest()}".encode()
    if not verify(rec["ed25519"], msg, sig):
        raise FabricError("bad request signature")
    return name

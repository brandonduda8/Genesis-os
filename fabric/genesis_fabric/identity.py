"""Charter-backed identity registry. Every identity record and every revocation is signed by the FOUNDER key.

A registry is a JSON document: {"founder_pub": ..., "identities": [ {record, sig} ], "revoked": [ {name, ts, sig} ]}.
Relays and clients load the same document. A record with no valid founder signature does not exist.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from .crypto import FabricError, Keys, canon, verify

NAME_OK = set("abcdefghijklmnopqrstuvwxyz0123456789-")


def issue(founder: Keys, *, name: str, klass: str, keys: Keys, charter_id: str, now: float,
          ttl_days: int = 180) -> Dict[str, Any]:
    if not name or set(name) - NAME_OK:
        raise FabricError("identity names are lowercase letters, digits and '-'")
    if not charter_id:
        raise FabricError("no charter, no identity")
    rec = {"name": name, "class": klass, "ed25519": keys.sign_pub, "x25519": keys.dh_pub, "charter_id": charter_id,
           "issued": int(now), "expires": int(now + ttl_days * 86400)}
    return {"record": rec, "sig": founder.sign(canon({"identity": rec}))}


def revoke(founder: Keys, name: str, now: float) -> Dict[str, Any]:
    body = {"name": name, "ts": int(now)}
    return {**body, "sig": founder.sign(canon({"revoke": body}))}


class Registry:
    def __init__(self, doc: Dict[str, Any]):
        self.founder_pub = doc["founder_pub"]
        self.ids: Dict[str, Dict[str, Any]] = {}
        self.revoked = set()
        for r in doc.get("revoked", []):
            body = {"name": r["name"], "ts": r["ts"]}
            if verify(self.founder_pub, canon({"revoke": body}), r["sig"]):
                self.revoked.add(r["name"])
        for e in doc.get("identities", []):
            if verify(self.founder_pub, canon({"identity": e["record"]}), e["sig"]):
                self.ids[e["record"]["name"]] = e["record"]
            # an unsigned or forged record is silently absent: it simply does not exist

    def get(self, name: str, now: Optional[float] = None) -> Dict[str, Any]:
        rec = self.ids.get(name)
        if rec is None:
            raise FabricError(f"unknown identity {name!r} (not founder-signed)")
        if name in self.revoked:
            raise FabricError(f"identity {name!r} is revoked")
        if now is not None and now > rec["expires"]:
            raise FabricError(f"identity {name!r} expired")
        return rec

    def names(self, klass: Optional[str] = None):
        return sorted(n for n, r in self.ids.items() if n not in self.revoked and (klass is None or r["class"] == klass))


def new_doc(founder: Keys, *entries: Dict[str, Any], revoked=()) -> Dict[str, Any]:
    return {"founder_pub": founder.sign_pub, "identities": list(entries), "revoked": list(revoked)}

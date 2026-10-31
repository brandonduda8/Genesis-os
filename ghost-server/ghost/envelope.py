"""A2A-style signed envelopes (module 8), store-and-forward first.

Envelope `ghost-a2a/1`:
  {v, id, kind: task|result|ack, from, to, job_id, payload, payload_sha256, created_at, expires_at, nonce, sig}
  * id = sha256(from|to|kind|job_id|payload_sha256|nonce)[:32]: deterministic for one emission, so a redelivered
    file carries the same id and is applied once.
  * sig = Ed25519 over the canonical envelope without `sig`, by the sender's key; receivers pin peer public keys.
Spool: spool/out/<peer>/<id>.json, written atomically (tmp, fsync, rename, fsync dir). They survive a dead network
and a reboot because they are files. Any transport that can move files (a git mailbox, a relay, rsync over a healed
door) can carry them. Inbound: verify signature, expiry and payload hash, then record and apply in ONE transaction.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from typing import Any, Callable, Dict, List, Optional

from .registry import Registry, canonical
from .signing import SignatureDenied, Verifier, encode, sign_bytes

VERSION = "ghost-a2a/1"
KINDS = ("task", "result", "ack")
MAX_TTL_S = 14 * 86400  # store-and-forward: an envelope may wait days for a heal window


def _unsigned(env: Dict[str, Any]) -> bytes:
    return encode({k: v for k, v in env.items() if k != "sig"})


def make(*, kind: str, frm: str, to: str, job_id: str, payload: Dict[str, Any], key: Any, now: float,
         ttl_s: int = 7 * 86400) -> Dict[str, Any]:
    if kind not in KINDS or not (60 <= ttl_s <= MAX_TTL_S):
        raise ValueError("bad envelope kind or ttl")
    psha = hashlib.sha256(encode(payload)).hexdigest()
    nonce = secrets.token_hex(16)
    env = {"v": VERSION, "id": hashlib.sha256(f"{frm}|{to}|{kind}|{job_id}|{psha}|{nonce}".encode()).hexdigest()[:32],
           "kind": kind, "from": frm, "to": to, "job_id": job_id, "payload": payload, "payload_sha256": psha,
           "created_at": int(now), "expires_at": int(now) + ttl_s, "nonce": nonce}
    env["sig"] = sign_bytes(key, _unsigned(env))
    return env


def _fsync_dir(d: str) -> None:
    fd = os.open(d, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def spool_write(spool_root: str, box: str, peer: str, env: Dict[str, Any]) -> str:
    d = os.path.join(spool_root, box, peer)
    os.makedirs(d, mode=0o700, exist_ok=True)
    final = os.path.join(d, f"{env['id']}.json")
    tmp = final + f".tmp-{os.getpid()}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(canonical(env))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, final)
    _fsync_dir(d)
    return final


def check(env: Any, *, verifier: Verifier, me: str, now: float) -> Dict[str, Any]:
    if not isinstance(env, dict) or env.get("v") != VERSION or env.get("kind") not in KINDS:
        raise SignatureDenied("not a ghost-a2a/1 envelope")
    if env.get("to") != me:
        raise SignatureDenied(f"envelope addressed to {env.get('to')!r}, not {me!r}")
    if not (env.get("created_at", 0) - 300 <= now <= env.get("expires_at", 0)):
        raise SignatureDenied("envelope expired or from the future")
    if hashlib.sha256(encode(env.get("payload", {}))).hexdigest() != env.get("payload_sha256"):
        raise SignatureDenied("payload hash mismatch")
    verifier.verify_peer(env.get("from", ""), _unsigned(env), env.get("sig", ""))
    return env


def drain_inbox(reg: Registry, spool_root: str, *, verifier: Verifier, me: str, now: float,
                apply: Callable[[Dict[str, Any]], str], ack_key: Any = None) -> List[Dict[str, Any]]:
    """Process spool/in/*/*.json. Each valid, new envelope is recorded and applied in one transaction.
    Redelivery is acknowledged and not re-applied. Invalid envelopes are quarantined, never applied."""
    results = []
    inbox = os.path.join(spool_root, "in")
    for peer in sorted(os.listdir(inbox)) if os.path.isdir(inbox) else []:
        pdir = os.path.join(inbox, peer)
        for name in sorted(n for n in os.listdir(pdir) if n.endswith(".json")):
            path = os.path.join(pdir, name)
            try:
                env = check(json.load(open(path)), verifier=verifier, me=me, now=now)
            except (SignatureDenied, ValueError, OSError) as exc:
                qdir = os.path.join(spool_root, "quarantine")
                os.makedirs(qdir, mode=0o700, exist_ok=True)
                os.replace(path, os.path.join(qdir, f"{peer}-{name}"))
                reg.ledger("envelope_quarantined", f"peer:{peer}", {"file": name, "why": str(exc)})
                results.append({"file": name, "outcome": "quarantined", "why": str(exc)})
                continue
            try:
                with reg.tx():
                    fresh = reg.record_envelope(env, "in", "received")
                    outcome = apply(env) if fresh and env["kind"] != "ack" else ("ack" if env["kind"] == "ack"
                                                                                   else "duplicate-ignored")
                    reg.ledger("envelope_in", f"peer:{env['from']}", {"id": env["id"], "kind": env["kind"],
                                                                      "outcome": outcome}, env.get("job_id", ""))
            except Exception as exc:  # rolled back: nothing recorded, nothing applied; never retried in a loop
                qdir = os.path.join(spool_root, "quarantine")
                os.makedirs(qdir, mode=0o700, exist_ok=True)
                os.replace(path, os.path.join(qdir, f"{peer}-{name}"))
                reg.ledger("envelope_apply_failed", f"peer:{peer}", {"id": env["id"], "why": f"{type(exc).__name__}: {exc}"},
                           env.get("job_id", ""))
                results.append({"file": name, "id": env["id"], "outcome": "apply-failed", "why": str(exc)})
                continue
            done = os.path.join(spool_root, "done")
            os.makedirs(done, mode=0o700, exist_ok=True)
            os.replace(path, os.path.join(done, f"{peer}-{name}"))
            if ack_key is not None and env["kind"] != "ack":
                ack = make(kind="ack", frm=me, to=env["from"], job_id=env.get("job_id", ""),
                           payload={"ack_of": env["id"], "outcome": outcome}, key=ack_key, now=now, ttl_s=86400)
                spool_write(spool_root, "out", env["from"], ack)
            results.append({"file": name, "id": env["id"], "outcome": outcome})
    return results


def pending_out(spool_root: str, peer: Optional[str] = None) -> List[str]:
    base = os.path.join(spool_root, "out")
    peers = [peer] if peer else (sorted(os.listdir(base)) if os.path.isdir(base) else [])
    return [os.path.join(base, p, n) for p in peers if os.path.isdir(os.path.join(base, p))
            for n in sorted(os.listdir(os.path.join(base, p))) if n.endswith(".json")]

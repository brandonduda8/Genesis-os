"""Ed25519 signed receipts, byte-compatible with Genesis-core genesis/omega/authority.py (#12).

Wire format: {"payload": {v, issuer, action, mission_id, principal, nonce, iat, exp}, "signature": b64}.
GHOST puts a job id (or envelope id) in `mission_id`, and its action names are disjoint from Omega's, so one
owner keypair can serve both systems without a grant for one ever being valid in the other.

`cryptography` is optional at import time. Without it, every signature check fails CLOSED (Level B denied,
envelopes rejected). Private keys are only ever read from 0600 files by the signing CLI; the server process
needs public keys only.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import stat
from typing import Any, Dict, Mapping, Optional

VERSION = 1
MAX_TTL_S = 300
SKEW_S = 30
FIELDS = frozenset(("v", "issuer", "action", "mission_id", "principal", "nonce", "iat", "exp"))
GHOST_ACTIONS = frozenset(("ghost_unblock", "ghost_requeue", "ghost_cancel", "ghost_complete", "ghost_forward",
                           "ghost_install", "ghost_envelope"))

try:  # optional dependency; absence = fail closed
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    HAVE_CRYPTO = True
except ImportError:  # pragma: no cover - exercised on hosts without cryptography
    HAVE_CRYPTO = False


class SignatureDenied(PermissionError):
    pass


def encode(body: Dict[str, Any]) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _check_private_file(path: str) -> None:
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode) or st.st_mode & 0o077:
        raise SignatureDenied(f"private key {path} must be a regular file with mode 0600")


def keygen(private_path: str) -> str:
    """Write a new Ed25519 private key (0600, refuses to overwrite) and return the base64 raw public key."""
    if not HAVE_CRYPTO:
        raise SignatureDenied("cryptography is not installed; cannot generate keys")
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    fd = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(base64.b64encode(raw) + b"\n")
    return public_b64(key)


def public_b64(key: "Ed25519PrivateKey") -> str:
    return base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,
                                                          serialization.PublicFormat.Raw)).decode("ascii")


def load_private(path: str) -> "Ed25519PrivateKey":
    if not HAVE_CRYPTO:
        raise SignatureDenied("cryptography is not installed")
    _check_private_file(path)
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(open(path, "rb").read().strip(), validate=True))


def sign(key: "Ed25519PrivateKey", *, issuer: str, action: str, subject: str, principal: str, now: float,
         ttl_s: int = 120) -> Dict[str, Any]:
    if not (1 <= ttl_s <= MAX_TTL_S):
        raise ValueError("ttl must be 1..300 s")
    body = {"v": VERSION, "issuer": issuer, "action": action, "mission_id": subject, "principal": principal,
            "nonce": secrets.token_hex(24), "iat": int(now), "exp": int(now) + ttl_s}
    return {"payload": body, "signature": base64.b64encode(key.sign(encode(body))).decode("ascii")}


def sign_bytes(key: "Ed25519PrivateKey", data: bytes) -> str:
    return base64.b64encode(key.sign(data)).decode("ascii")


class Verifier:
    """Pinned PUBLIC keys: {"owner": {issuer: b64}, "reviewer": {...}, "peers": {peer_name: b64}}."""

    def __init__(self, keys: Optional[Mapping[str, Mapping[str, str]]] = None):
        self.keys = {sec: dict((keys or {}).get(sec) or {}) for sec in ("owner", "reviewer", "peers")}

    @classmethod
    def from_file(cls, path: Optional[str]) -> "Verifier":
        if not path or not os.path.exists(path):
            return cls()
        st = os.lstat(path)
        if stat.S_ISLNK(st.st_mode) or st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise SignatureDenied("trusted-keys file must not be a symlink or group/world-writable")
        return cls(json.load(open(path)))

    def _pub(self, section: str, name: str) -> "Ed25519PublicKey":
        if not HAVE_CRYPTO:
            raise SignatureDenied("cryptography is not installed: signed actions fail closed")
        b64 = self.keys.get(section, {}).get(name)
        if not b64:
            raise SignatureDenied(f"untrusted signer {name!r} for {section}")
        return Ed25519PublicKey.from_public_bytes(base64.b64decode(b64, validate=True))

    def verify_grant(self, grant: Any, *, action: str, subject: str, principal: str, now: float) -> Dict[str, Any]:
        if action not in GHOST_ACTIONS:
            raise SignatureDenied(f"{action!r} is not a GHOST action")
        if not isinstance(grant, dict) or set(grant) != {"payload", "signature"}:
            raise SignatureDenied("signed receipt required")
        body = grant["payload"]
        if not isinstance(body, dict) or set(body) != FIELDS or body.get("v") != VERSION:
            raise SignatureDenied("malformed signed receipt")
        if (body["action"], body["mission_id"], body["principal"]) != (action, subject, principal):
            raise SignatureDenied("signed receipt is not scoped to this action, job and principal")
        nonce = body["nonce"]
        if not (isinstance(nonce, str) and 32 <= len(nonce) <= 128 and all(c in "0123456789abcdef" for c in nonce)):
            raise SignatureDenied("invalid nonce")
        if not all(type(body[k]) in (int, float) for k in ("iat", "exp")) or not (0 < body["exp"] - body["iat"] <= MAX_TTL_S):
            raise SignatureDenied("invalid validity window")
        if now < body["iat"] - SKEW_S or now > body["exp"]:
            raise SignatureDenied("signed receipt expired or not yet valid")
        try:
            self._pub("owner", body["issuer"]).verify(base64.b64decode(grant["signature"], validate=True), encode(body))
        except SignatureDenied:
            raise
        except (InvalidSignature, ValueError, TypeError) as exc:
            raise SignatureDenied("signature invalid") from exc
        return body

    def verify_peer(self, peer: str, data: bytes, signature_b64: str) -> None:
        try:
            self._pub("peers", peer).verify(base64.b64decode(signature_b64, validate=True), data)
        except SignatureDenied:
            raise
        except (InvalidSignature, ValueError, TypeError) as exc:
            raise SignatureDenied(f"envelope signature from {peer!r} invalid") from exc


# ---- policy-class charters (POLICY-BASED-APPROVALS-2026-10-31) ------------------------------------------------------
CHARTER_FIELDS = frozenset(("v", "kind", "charter_id", "issuer", "classes", "iat", "exp"))
MAX_CHARTER_DAYS = 180


def sign_charter(key: "Ed25519PrivateKey", *, issuer: str, classes: Dict[str, Any], now: float,
                 days: int = 90) -> Dict[str, Any]:
    """One signature approves whole classes (Brandon's register), instead of one tap per item."""
    if not (1 <= days <= MAX_CHARTER_DAYS):
        raise ValueError("charter validity must be 1..180 days")
    body = {"v": VERSION, "kind": "ghost-policy-charter", "charter_id": secrets.token_hex(8), "issuer": issuer,
            "classes": classes, "iat": int(now), "exp": int(now) + days * 86400}
    return {"payload": body, "signature": base64.b64encode(key.sign(encode(body))).decode("ascii")}


def _verify_charter(self: "Verifier", charter: Any, *, now: float) -> Dict[str, Any]:
    if not isinstance(charter, dict) or set(charter) != {"payload", "signature"}:
        raise SignatureDenied("no signed policy charter")
    body = charter["payload"]
    if not isinstance(body, dict) or set(body) != CHARTER_FIELDS or body.get("v") != VERSION \
            or body.get("kind") != "ghost-policy-charter" or not isinstance(body.get("classes"), dict):
        raise SignatureDenied("malformed policy charter")
    if not all(type(body[k]) in (int, float) for k in ("iat", "exp")) or \
            not (0 < body["exp"] - body["iat"] <= MAX_CHARTER_DAYS * 86400):
        raise SignatureDenied("invalid charter validity window")
    if now < body["iat"] - SKEW_S or now > body["exp"]:
        raise SignatureDenied("policy charter expired or not yet valid")
    try:
        self._pub("owner", body["issuer"]).verify(base64.b64decode(charter["signature"], validate=True), encode(body))
    except SignatureDenied:
        raise
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise SignatureDenied("policy charter signature invalid") from exc
    return body


Verifier.verify_charter = _verify_charter  # type: ignore[attr-defined]

"""Crypto primitives. Curves and AEAD come from `cryptography` (audited); HKDF + hash ratchet over stdlib hmac.

Without `cryptography` the fabric FAILS CLOSED: importing this module raises, so nothing can run in clear.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any, Dict, Optional, Tuple

try:
    from cryptography.exceptions import InvalidSignature, InvalidTag
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
except ImportError as e:  # pragma: no cover
    raise RuntimeError("genesis-fabric requires the 'cryptography' package; refusing to run without it") from e

RAW = serialization.Encoding.Raw


class FabricError(Exception):
    pass


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def unb64(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"), validate=True)


def canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


# ---------- HKDF (RFC 5869) ----------
def hkdf(ikm: bytes, *, salt: bytes = b"", info: bytes = b"", length: int = 32) -> bytes:
    prk = hmac.new(salt or b"\0" * 32, ikm, hashlib.sha256).digest()
    out, t, i = b"", b"", 1
    while len(out) < length:
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        out += t
        i += 1
    return out[:length]


# ---------- keys ----------
class Keys:
    """An identity's two keypairs: Ed25519 to sign, X25519 to pair."""

    def __init__(self, sign: Ed25519PrivateKey, dh: X25519PrivateKey):
        self.sign_key, self.dh_key = sign, dh

    @classmethod
    def generate(cls) -> "Keys":
        return cls(Ed25519PrivateKey.generate(), X25519PrivateKey.generate())

    @property
    def sign_pub(self) -> str:
        return b64(self.sign_key.public_key().public_bytes(RAW, serialization.PublicFormat.Raw))

    @property
    def dh_pub(self) -> str:
        return b64(self.dh_key.public_key().public_bytes(RAW, serialization.PublicFormat.Raw))

    def sign(self, data: bytes) -> str:
        return b64(self.sign_key.sign(data))

    def dh(self, peer_pub_b64: str) -> bytes:
        return self.dh_key.exchange(X25519PublicKey.from_public_bytes(unb64(peer_pub_b64)))

    def export(self) -> Dict[str, str]:
        return {"sign": b64(self.sign_key.private_bytes(RAW, serialization.PrivateFormat.Raw,
                                                        serialization.NoEncryption())),
                "dh": b64(self.dh_key.private_bytes(RAW, serialization.PrivateFormat.Raw,
                                                    serialization.NoEncryption()))}

    @classmethod
    def load(cls, d: Dict[str, str]) -> "Keys":
        return cls(Ed25519PrivateKey.from_private_bytes(unb64(d["sign"])),
                   X25519PrivateKey.from_private_bytes(unb64(d["dh"])))


def verify(pub_b64: str, data: bytes, sig_b64: str) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(unb64(pub_b64)).verify(unb64(sig_b64), data)
        return True
    except (InvalidSignature, ValueError):
        return False


# ---------- AEAD ----------
def seal(key: bytes, n: int, plaintext: bytes, aad: bytes) -> str:
    return b64(ChaCha20Poly1305(key).encrypt(n.to_bytes(12, "big"), plaintext, aad))


def open_(key: bytes, n: int, ct_b64: str, aad: bytes) -> bytes:
    try:
        return ChaCha20Poly1305(key).decrypt(n.to_bytes(12, "big"), unb64(ct_b64), aad)
    except InvalidTag:
        raise FabricError("ciphertext failed authentication (tampered, misrouted or wrong key)") from None


# ---------- symmetric hash ratchet ----------
class Chain:
    """One direction of a session. Each step derives a one-use message key and ERASES the previous chain key."""
    MAX_SKIP = 64

    def __init__(self, ck: bytes, n: int = 0):
        self.ck, self.n = ck, n
        self.skipped: Dict[int, bytes] = {}

    def _step(self) -> bytes:
        mk = hmac.new(self.ck, b"\x01", hashlib.sha256).digest()
        self.ck = hmac.new(self.ck, b"\x02", hashlib.sha256).digest()
        self.n += 1
        return mk

    def next_send(self) -> Tuple[int, bytes]:
        n = self.n
        return n, self._step()

    def key_for(self, n: int) -> bytes:
        if n in self.skipped:
            return self.skipped.pop(n)
        if n < self.n:
            raise FabricError(f"message {n} already consumed or its key erased (no replay, no rewind)")
        if n - self.n > self.MAX_SKIP:
            raise FabricError("too many skipped messages")
        while self.n < n:
            k = self.n
            self.skipped[k] = self._step()
        return self._step()

    def state(self) -> Dict[str, Any]:
        return {"ck": b64(self.ck), "n": self.n, "skipped": {str(k): b64(v) for k, v in self.skipped.items()}}

    @classmethod
    def from_state(cls, s: Dict[str, Any]) -> "Chain":
        c = cls(unb64(s["ck"]), s["n"])
        c.skipped = {int(k): unb64(v) for k, v in s.get("skipped", {}).items()}
        return c


def pin_from_root(root: bytes) -> str:
    return "%06d" % (int.from_bytes(hkdf(root, info=b"genesis-fabric/pin/v1", length=8), "big") % 1_000_000)


def constant_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def maybe(x: Optional[str]) -> Optional[bytes]:
    return unb64(x) if x else None

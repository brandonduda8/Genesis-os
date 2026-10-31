#!/usr/bin/env python3
"""Genesis Asset Vault (WO-UNIFIED-GAME-BUSINESS-001 Phase 2): content-addressed, provenance-first, audit-replayable.

Layout under ROOT (production: /home/hatch/agent-shelf/asset-vault/, prune-exempt shelf):
  objects/ab/<sha256>    promoted files, named by their own SHA-256, written once and never changed
  staging/<sha256>       files waiting for promotion (hash re-verified at promotion)
  CATALOG.sqlite         assets, title slots
  audit.log              append-only JSONL, hash-chained (each line carries the previous line's hash)
  manifests/<pack>.json  per-pack manifests, Ed25519-signed when a key is supplied (GHOST key format)

Two flags, never merged into one:
  rights_clean  the licence permits commercial use and redistribution, AND a reviewer recorded evidence for it.
                Every asset enters FALSE; only `set_rights` with evidence flips it.
  origin        'stock' (third-party, e.g. CC0 packs) or 'genesis' (made by the fleet through the asset service).
A title is ORIGINAL only when every player-facing slot is origin='genesis' AND rights_clean. CC0 stock can be
rights-clean, but it is never original.
Third-party streams (Audius, SoundCloud) are NEVER vault assets: origin 'stream' is refused.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
from typing import Any, Callable, Dict, List, Optional

ORIGINS = ("stock", "genesis")
# Licences under which a reviewer MAY mark an asset rights-clean (commercial use + redistribution allowed).
COMMERCIAL_OK = ("CC0-1.0", "MIT", "Apache-2.0", "OWNED-BRANDON")
GENESIS_AUDIT = "0" * 64

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
  sha256 TEXT PRIMARY KEY, bytes INTEGER NOT NULL, name TEXT NOT NULL, media_type TEXT NOT NULL,
  pack TEXT NOT NULL, origin TEXT NOT NULL CHECK (origin IN ('stock','genesis')),
  licence TEXT NOT NULL, rights_clean INTEGER NOT NULL DEFAULT 0, rights_evidence TEXT,
  provenance TEXT NOT NULL, added_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS slots (
  title TEXT NOT NULL, slot TEXT NOT NULL, sha256 TEXT NOT NULL REFERENCES assets(sha256),
  player_facing INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (title, slot));
"""


class VaultError(Exception):
    pass


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


class Vault:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.audit_path = os.path.join(self.root, "audit.log")
        if not os.path.exists(os.path.join(self.root, "CATALOG.sqlite")):
            raise VaultError(f"no vault at {self.root} (run init)")
        self.db = sqlite3.connect(os.path.join(self.root, "CATALOG.sqlite"))
        self.db.row_factory = sqlite3.Row

    # ---------- creation ----------
    @classmethod
    def init(cls, root: str, actor: str = "init") -> "Vault":
        for d in ("objects", "staging", "manifests"):
            os.makedirs(os.path.join(root, d), exist_ok=True)
        db = sqlite3.connect(os.path.join(root, "CATALOG.sqlite"))
        db.executescript(SCHEMA)
        db.commit()
        db.close()
        v = cls(root)
        if not os.path.exists(v.audit_path) or os.path.getsize(v.audit_path) == 0:
            v._audit(actor, "init", {"root": v.root})
        return v

    # ---------- audit log (append-only, hash-chained) ----------
    def _last(self) -> Dict[str, Any]:
        if not os.path.exists(self.audit_path):
            return {"seq": 0, "hash": GENESIS_AUDIT}
        last = None
        with open(self.audit_path, "rb") as f:
            for line in f:
                if line.strip():
                    last = line
        return json.loads(last) if last else {"seq": 0, "hash": GENESIS_AUDIT}

    def _audit(self, actor: str, action: str, data: Dict[str, Any]) -> None:
        prev = self._last()
        entry = {"seq": prev["seq"] + 1, "at": _now(), "actor": actor, "action": action, "data": data,
                 "prev": prev["hash"]}
        entry["hash"] = hashlib.sha256(_canon(entry)).hexdigest()
        with open(self.audit_path, "ab") as f:
            f.write(_canon(entry) + b"\n")
            f.flush()
            os.fsync(f.fileno())

    def verify_audit_chain(self) -> List[str]:
        problems, prev, seq = [], GENESIS_AUDIT, 0
        if not os.path.exists(self.audit_path):
            return ["audit.log missing"]
        with open(self.audit_path, "rb") as f:
            for n, line in enumerate(f, 1):
                if not line.strip():
                    continue
                e = json.loads(line)
                body = {k: v for k, v in e.items() if k != "hash"}
                if e.get("prev") != prev:
                    problems.append(f"audit line {n}: chain broken (prev mismatch)")
                if hashlib.sha256(_canon(body)).hexdigest() != e.get("hash"):
                    problems.append(f"audit line {n}: entry hash mismatch (edited)")
                if e.get("seq") != seq + 1:
                    problems.append(f"audit line {n}: sequence gap")
                prev, seq = e.get("hash"), e.get("seq", seq + 1)
        return problems

    def audit_entries(self) -> List[Dict[str, Any]]:
        with open(self.audit_path, "rb") as f:
            return [json.loads(l) for l in f if l.strip()]

    # ---------- staging -> promotion ----------
    def object_path(self, sha: str) -> str:
        return os.path.join(self.root, "objects", sha[:2], sha)

    def stage(self, src: str) -> str:
        if not os.path.isfile(src) or os.path.islink(src):
            raise VaultError(f"not a regular file: {src}")
        sha = sha256_file(src)
        dst = os.path.join(self.root, "staging", sha)
        if not os.path.exists(dst):
            shutil.copyfile(src, dst + ".part")
            os.replace(dst + ".part", dst)
        return sha

    def promote(self, sha: str, *, name: str, media_type: str, pack: str, origin: str, licence: str,
                provenance: Dict[str, Any], actor: str) -> Dict[str, Any]:
        if origin == "stream":
            raise VaultError("third-party streams are never vault assets")
        if origin not in ORIGINS:
            raise VaultError(f"origin must be one of {ORIGINS}")
        if not provenance or not provenance.get("source"):
            raise VaultError("provenance.source is required (where this file came from)")
        if origin == "genesis" and not provenance.get("generator"):
            raise VaultError("a genesis asset must name its generator (model / lane / job id)")
        if not licence:
            raise VaultError("licence is required")
        staged = os.path.join(self.root, "staging", sha)
        if not os.path.exists(staged):
            raise VaultError(f"{sha} is not staged")
        if sha256_file(staged) != sha:
            raise VaultError(f"staged file {sha} no longer matches its hash; refusing")
        row = self.db.execute("SELECT sha256 FROM assets WHERE sha256=?", (sha,)).fetchone()
        if row:
            os.remove(staged)
            return {"sha256": sha, "status": "already-promoted"}
        dst = self.object_path(sha)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.replace(staged, dst)
        os.chmod(dst, 0o444)
        size = os.path.getsize(dst)
        self.db.execute("INSERT INTO assets VALUES (?,?,?,?,?,?,?,0,NULL,?,?)",
                        (sha, size, name, media_type, pack, origin, licence, json.dumps(provenance, sort_keys=True),
                         _now()))
        self.db.commit()
        self._audit(actor, "promote", {"sha256": sha, "bytes": size, "name": name, "pack": pack, "origin": origin,
                                       "licence": licence, "provenance": provenance})
        return {"sha256": sha, "status": "promoted"}

    def add(self, src: str, **kw: Any) -> Dict[str, Any]:
        return self.promote(self.stage(src), **kw)

    # ---------- rights and slots ----------
    def set_rights(self, sha: str, clean: bool, *, evidence: str, actor: str) -> None:
        row = self.db.execute("SELECT licence FROM assets WHERE sha256=?", (sha,)).fetchone()
        if not row:
            raise VaultError(f"unknown asset {sha}")
        if clean and row["licence"] not in COMMERCIAL_OK:
            raise VaultError(f"licence {row['licence']} is not on the commercial-OK list {COMMERCIAL_OK}")
        if not evidence or not evidence.strip():
            raise VaultError("evidence is required to change rights (what was read, where, by whom)")
        self.db.execute("UPDATE assets SET rights_clean=?, rights_evidence=? WHERE sha256=?", (int(clean), evidence, sha))
        self.db.commit()
        self._audit(actor, "set_rights", {"sha256": sha, "rights_clean": bool(clean), "evidence": evidence})

    def bind_slot(self, title: str, slot: str, sha: str, *, player_facing: bool = True, actor: str) -> None:
        if not self.db.execute("SELECT 1 FROM assets WHERE sha256=?", (sha,)).fetchone():
            raise VaultError(f"unknown asset {sha}: only vault assets may fill a title slot")
        old = self.db.execute("SELECT sha256 FROM slots WHERE title=? AND slot=?", (title, slot)).fetchone()
        self.db.execute("INSERT OR REPLACE INTO slots VALUES (?,?,?,?)", (title, slot, sha, int(player_facing)))
        self.db.commit()
        self._audit(actor, "bind_slot", {"title": title, "slot": slot, "sha256": sha, "replaced": old[0] if old else None,
                                         "player_facing": bool(player_facing)})

    def title_report(self, title: str) -> Dict[str, Any]:
        rows = self.db.execute(
            "SELECT s.slot, s.player_facing, a.origin, a.rights_clean, a.licence FROM slots s "
            "JOIN assets a ON a.sha256=s.sha256 WHERE s.title=? ORDER BY s.slot", (title,)).fetchall()
        pf = [r for r in rows if r["player_facing"]]
        clean = sum(1 for r in pf if r["rights_clean"])
        genesis = sum(1 for r in pf if r["origin"] == "genesis" and r["rights_clean"])
        return {"title": title, "slots": len(rows), "player_facing": len(pf), "rights_clean": clean,
                "genesis_original": genesis, "stock": sum(1 for r in pf if r["origin"] == "stock"),
                "original": bool(pf) and genesis == len(pf),
                "remaining_for_original": [r["slot"] for r in pf if not (r["origin"] == "genesis" and r["rights_clean"])]}

    # ---------- replay ----------
    def audit_replay(self) -> Dict[str, Any]:
        """Every cataloged asset is on disk with a matching hash, was promoted in the log, and the log is unbroken."""
        problems = self.verify_audit_chain()
        promoted = {e["data"]["sha256"] for e in self.audit_entries() if e["action"] == "promote"}
        n = 0
        for r in self.db.execute("SELECT sha256 FROM assets"):
            n += 1
            p = self.object_path(r["sha256"])
            if not os.path.exists(p):
                problems.append(f"{r['sha256']}: cataloged but missing on disk")
            elif sha256_file(p) != r["sha256"]:
                problems.append(f"{r['sha256']}: on-disk bytes do not match the hash")
            if r["sha256"] not in promoted:
                problems.append(f"{r['sha256']}: in the catalog with no promote entry in audit.log")
        for r in self.db.execute("SELECT title, slot, sha256 FROM slots"):
            if not self.db.execute("SELECT 1 FROM assets WHERE sha256=?", (r["sha256"],)).fetchone():
                problems.append(f"slot {r['title']}/{r['slot']}: points at a non-vault asset")
        orphans = []
        objdir = os.path.join(self.root, "objects")
        for d in os.listdir(objdir):
            for f in os.listdir(os.path.join(objdir, d)):
                if not self.db.execute("SELECT 1 FROM assets WHERE sha256=?", (f,)).fetchone():
                    orphans.append(f)
        problems += [f"{o}: file on disk with no catalog row" for o in orphans]
        return {"ok": not problems, "assets": n, "problems": problems, "at": _now()}

    # ---------- manifests ----------
    def pack_manifest(self, pack: str, *, signer: Optional[Callable[[bytes], str]] = None,
                      signer_pub: Optional[str] = None) -> Dict[str, Any]:
        rows = self.db.execute("SELECT sha256, bytes, name, media_type, origin, licence, rights_clean FROM assets "
                               "WHERE pack=? ORDER BY name, sha256", (pack,)).fetchall()
        if not rows:
            raise VaultError(f"pack {pack} is empty")
        body = {"pack": pack, "v": 1, "entries": [dict(r) for r in rows]}
        body["digest"] = hashlib.sha256(_canon(body["entries"])).hexdigest()
        out = {"manifest": body, "signature": None, "signer_pub": None}
        if signer:
            out["signature"], out["signer_pub"] = signer(_canon(body)), signer_pub
        with open(os.path.join(self.root, "manifests", f"{pack}.json"), "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
        return out


def ed25519_signer(private_path: str):
    """Signer using a GHOST-format key file (base64 raw Ed25519, mode 0600). Returns (sign_fn, public_b64)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    st = os.lstat(private_path)
    if st.st_mode & 0o077:
        raise VaultError("private key must be mode 0600")
    key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(open(private_path, "rb").read().strip()))
    pub = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,
                                                         serialization.PublicFormat.Raw)).decode()
    return (lambda data: base64.b64encode(key.sign(data)).decode()), pub


def verify_manifest(doc: Dict[str, Any], vault: Optional[Vault] = None, trusted_pub: Optional[str] = None) -> List[str]:
    problems = []
    body = doc["manifest"]
    if hashlib.sha256(_canon(body["entries"])).hexdigest() != body["digest"]:
        problems.append("digest does not match entries")
    if trusted_pub is not None:
        if not doc.get("signature"):
            problems.append("unsigned manifest")
        else:
            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            try:
                Ed25519PublicKey.from_public_bytes(base64.b64decode(trusted_pub)).verify(
                    base64.b64decode(doc["signature"]), _canon(body))
            except InvalidSignature:
                problems.append("signature invalid for the trusted key")
    if vault is not None:
        for e in body["entries"]:
            p = vault.object_path(e["sha256"])
            if not os.path.exists(p) or sha256_file(p) != e["sha256"]:
                problems.append(f"{e['name']}: missing or altered in the vault")
    return problems


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    a = sub.add_parser("add")
    a.add_argument("file")
    for k in ("name", "media-type", "pack", "origin", "licence", "source", "actor"):
        a.add_argument(f"--{k}", required=True)
    a.add_argument("--generator")
    r = sub.add_parser("rights")
    r.add_argument("sha256")
    r.add_argument("--clean", choices=("true", "false"), required=True)
    r.add_argument("--evidence", required=True)
    r.add_argument("--actor", required=True)
    t = sub.add_parser("report")
    t.add_argument("title")
    sub.add_parser("audit")
    m = sub.add_parser("manifest")
    m.add_argument("pack")
    m.add_argument("--key")
    x = ap.parse_args(argv)
    if x.cmd == "init":
        Vault.init(x.root)
        print(f"vault ready at {x.root}")
        return 0
    v = Vault(x.root)
    if x.cmd == "add":
        prov = {"source": x.source, **({"generator": x.generator} if x.generator else {})}
        out = v.add(x.file, name=x.name, media_type=x.media_type, pack=x.pack, origin=x.origin, licence=x.licence,
                    provenance=prov, actor=x.actor)
    elif x.cmd == "rights":
        v.set_rights(x.sha256, x.clean == "true", evidence=x.evidence, actor=x.actor)
        out = {"ok": True}
    elif x.cmd == "report":
        out = v.title_report(x.title)
    elif x.cmd == "audit":
        out = v.audit_replay()
    else:
        signer, pub = ed25519_signer(x.key) if x.key else (None, None)
        out = v.pack_manifest(x.pack, signer=signer, signer_pub=pub)
    print(json.dumps(out, indent=1))
    return 0 if out.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())

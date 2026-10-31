"""GHOST durable job core (module 1) + lineage (module 2) + evidence ledger (module 9).

Registry law, enforced here rather than documented:
  * Writes address exactly one deterministic job ID (GHOST-Q-NNN) and an expected version.
    `find()` may locate IDs by text; it never writes. There is no pattern-based write API.
  * Every write is read back inside the same transaction; a mismatch rolls back and raises.
  * Ledger and lineage are append-only (SQLite triggers abort UPDATE/DELETE); DONE-VERIFIED rows are frozen.
  * Retries are bounded (max_attempts) with deterministic exponential backoff; exhaustion -> DEAD-LETTER.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, List, Optional

JOB_ID = re.compile(r"^GHOST-Q-\d{3,}$")
QUEUED, RUNNING, BLOCKED, DONE, DEAD = "QUEUED", "RUNNING", "BLOCKED", "DONE-VERIFIED", "DEAD-LETTER"
STATES = (QUEUED, RUNNING, BLOCKED, DONE, DEAD)
TRANSITIONS = {
    (QUEUED, RUNNING), (QUEUED, BLOCKED), (QUEUED, DEAD),
    (BLOCKED, QUEUED), (BLOCKED, DEAD),
    (RUNNING, DONE), (RUNNING, QUEUED), (RUNNING, DEAD), (RUNNING, BLOCKED),
    (DEAD, QUEUED),
}
BACKOFF_BASE_S, BACKOFF_CAP_S = 60, 3600
GENESIS_HASH = "0" * 64

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT PRIMARY KEY CHECK (job_id GLOB 'GHOST-Q-[0-9][0-9][0-9]*'),
  title TEXT NOT NULL, lane TEXT NOT NULL, executor TEXT NOT NULL, assignee TEXT NOT NULL DEFAULT '',
  target_host TEXT NOT NULL DEFAULT '', requires TEXT NOT NULL DEFAULT '[]', spec TEXT NOT NULL DEFAULT '{}',
  verifier TEXT NOT NULL DEFAULT '{}', level TEXT NOT NULL CHECK (level IN ('A','B','C')),
  state TEXT NOT NULL CHECK (state IN ('QUEUED','RUNNING','BLOCKED','DONE-VERIFIED','DEAD-LETTER')),
  blocked_reason TEXT NOT NULL DEFAULT '', attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 20),
  next_eligible_at REAL NOT NULL DEFAULT 0, lease_until REAL NOT NULL DEFAULT 0,
  receipt_target TEXT NOT NULL DEFAULT '', content_sha256 TEXT NOT NULL,
  created_at REAL NOT NULL, first_run_at REAL, done_at REAL, updated_at REAL NOT NULL,
  version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_jobs_sched ON jobs(state, lane, next_eligible_at);
CREATE TABLE IF NOT EXISTS attempts (
  attempt_id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL REFERENCES jobs(job_id), n INTEGER NOT NULL,
  started_at REAL NOT NULL, ended_at REAL, outcome TEXT, error_class TEXT NOT NULL DEFAULT '',
  error TEXT NOT NULL DEFAULT '', cpu_s REAL NOT NULL DEFAULT 0, rss_kb INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_attempts_job ON attempts(job_id, n);
CREATE TABLE IF NOT EXISTS lineage (
  job_id TEXT NOT NULL, seq INTEGER NOT NULL, at REAL NOT NULL, actor TEXT NOT NULL, transform TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT '', input_sha256 TEXT NOT NULL, output_sha256 TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '', PRIMARY KEY (job_id, seq)
);
CREATE TABLE IF NOT EXISTS artifacts (
  sha256 TEXT NOT NULL, job_id TEXT NOT NULL, path TEXT NOT NULL, bytes INTEGER NOT NULL,
  produced_by TEXT NOT NULL, at REAL NOT NULL, PRIMARY KEY (sha256, job_id)
);
CREATE TABLE IF NOT EXISTS envelopes (
  env_id TEXT PRIMARY KEY, direction TEXT NOT NULL CHECK (direction IN ('in','out')), peer TEXT NOT NULL,
  kind TEXT NOT NULL, job_id TEXT NOT NULL DEFAULT '', state TEXT NOT NULL, body TEXT NOT NULL, at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS ledger (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, kind TEXT NOT NULL, job_id TEXT NOT NULL DEFAULT '',
  actor TEXT NOT NULL, body TEXT NOT NULL, prev_hash TEXT NOT NULL, hash TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS heartbeat (id INTEGER PRIMARY KEY CHECK (id = 1), at REAL NOT NULL, pid INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS escalations (
  esc_id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, job_id TEXT NOT NULL DEFAULT '', action TEXT NOT NULL,
  reason TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'AWAITING-BRANDON'
);
CREATE TABLE IF NOT EXISTS nonces (nonce TEXT PRIMARY KEY, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS door_state (
  name TEXT PRIMARY KEY, body TEXT NOT NULL, at REAL NOT NULL
);
CREATE TRIGGER IF NOT EXISTS ledger_no_update BEFORE UPDATE ON ledger BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ledger_no_delete BEFORE DELETE ON ledger BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS lineage_no_update BEFORE UPDATE ON lineage BEGIN SELECT RAISE(ABORT, 'lineage is append-only'); END;
CREATE TRIGGER IF NOT EXISTS lineage_no_delete BEFORE DELETE ON lineage BEGIN SELECT RAISE(ABORT, 'lineage is append-only'); END;
CREATE TRIGGER IF NOT EXISTS jobs_no_delete BEFORE DELETE ON jobs BEGIN SELECT RAISE(ABORT, 'jobs are never deleted'); END;
CREATE TRIGGER IF NOT EXISTS jobs_done_frozen BEFORE UPDATE ON jobs WHEN OLD.state = 'DONE-VERIFIED'
  BEGIN SELECT RAISE(ABORT, 'DONE-VERIFIED jobs are frozen'); END;
"""

JOB_FIELDS = ("job_id", "title", "lane", "executor", "assignee", "target_host", "requires", "spec", "verifier",
              "level", "receipt_target", "max_attempts")
JSON_FIELDS = ("requires", "spec", "verifier")


class RegistryError(RuntimeError):
    pass


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def display_state(job: Dict[str, Any]) -> str:
    return f"BLOCKED-({job['blocked_reason']})" if job["state"] == BLOCKED else job["state"]


def backoff_s(attempt_n: int) -> int:
    return min(BACKOFF_CAP_S, BACKOFF_BASE_S * (2 ** max(0, attempt_n - 1)))


class Registry:
    def __init__(self, path: str, clock: Callable[[], float] = time.time):
        self.path, self.clock = path, clock
        new = not os.path.exists(path)
        if new:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            os.close(os.open(path, os.O_CREAT | os.O_WRONLY, 0o600))
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        for pragma in ("journal_mode=WAL", "synchronous=FULL", "foreign_keys=ON", "busy_timeout=10000"):
            self.db.execute(f"PRAGMA {pragma}")
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        if self.db.in_transaction:  # nested use joins the outer transaction
            yield self.db
            return
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield self.db
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    # ------------------------------------------------------------------ ledger
    def ledger(self, kind: str, actor: str, body: Optional[Dict[str, Any]] = None, job_id: str = "") -> str:
        with self.tx() as db:
            row = db.execute("SELECT hash FROM ledger ORDER BY seq DESC LIMIT 1").fetchone()
            prev = row["hash"] if row else GENESIS_HASH
            at = self.clock()
            b = canonical(body or {})
            h = sha256_text(canonical([prev, at, kind, job_id, actor, b]))
            db.execute("INSERT INTO ledger(at,kind,job_id,actor,body,prev_hash,hash) VALUES (?,?,?,?,?,?,?)",
                       (at, kind, job_id, actor, b, prev, h))
            return h

    def verify_ledger(self) -> Dict[str, Any]:
        prev, n = GENESIS_HASH, 0
        for r in self.db.execute("SELECT * FROM ledger ORDER BY seq"):
            want = sha256_text(canonical([r["prev_hash"], r["at"], r["kind"], r["job_id"], r["actor"], r["body"]]))
            if r["prev_hash"] != prev or r["hash"] != want:
                return {"ok": False, "records": n, "broken_at_seq": r["seq"]}
            prev, n = r["hash"], n + 1
        return {"ok": True, "records": n, "head": prev}

    # ------------------------------------------------------------------ reads
    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        r = self.db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        for f in JSON_FIELDS:
            d[f] = json.loads(d[f])
        return d

    def find(self, text: str) -> List[str]:
        """Read-only: candidate IDs whose title/spec mention `text`. Never used as a write set."""
        like = f"%{text}%"
        return [r[0] for r in self.db.execute(
            "SELECT job_id FROM jobs WHERE title LIKE ? OR spec LIKE ? ORDER BY job_id", (like, like))]

    def jobs(self, state: Optional[str] = None) -> List[Dict[str, Any]]:
        q, a = ("SELECT job_id FROM jobs WHERE state = ? ORDER BY job_id", (state,)) if state else \
            ("SELECT job_id FROM jobs ORDER BY job_id", ())
        return [self.get(r[0]) for r in self.db.execute(q, a)]  # type: ignore[misc]

    @staticmethod
    def content_hash(job: Dict[str, Any]) -> str:
        keep = {k: job.get(k) for k in JOB_FIELDS}
        keep.update(state=job.get("state"), blocked_reason=job.get("blocked_reason", ""), attempts=job.get("attempts", 0))
        return sha256_text(canonical(keep))

    # ------------------------------------------------------------------ lineage
    def _lineage(self, db, job_id: str, actor: str, transform: str, inp: str, out: str, source: str = "",
                 note: str = "") -> None:
        seq = db.execute("SELECT COALESCE(MAX(seq),0)+1 FROM lineage WHERE job_id=?", (job_id,)).fetchone()[0]
        db.execute("INSERT INTO lineage VALUES (?,?,?,?,?,?,?,?,?)",
                   (job_id, seq, self.clock(), actor, transform, source, inp, out, note))

    def note_lineage(self, job_id: str, actor: str, transform: str, source: str = "", note: str = "") -> None:
        """Lineage-only event (e.g. legacy file changed); the job row is not modified."""
        with self.tx() as db:
            job = self.get(job_id)
            if not job:
                raise RegistryError(f"unknown job {job_id}")
            self._lineage(db, job_id, actor, transform, job["content_sha256"], job["content_sha256"], source, note)
            self.ledger("lineage", actor, {"transform": transform, "note": note, "source": source}, job_id)

    # ------------------------------------------------------------------ writes
    def add_job(self, job: Dict[str, Any], *, actor: str, source: str, state: str = QUEUED,
                blocked_reason: str = "", transform: str = "create") -> Dict[str, Any]:
        jid = job.get("job_id", "")
        if not JOB_ID.match(jid):
            raise RegistryError(f"job_id must be a deterministic GHOST-Q-NNN id, got {jid!r}")
        if state not in (QUEUED, BLOCKED, DEAD):
            raise RegistryError(f"jobs enter as QUEUED, BLOCKED or DEAD-LETTER, not {state}")
        now = self.clock()
        row = {"assignee": "", "target_host": "", "requires": [], "spec": {}, "verifier": {}, "receipt_target": "",
               "max_attempts": 3, **{k: job[k] for k in JOB_FIELDS if k in job}}
        for k in ("title", "lane", "executor", "level"):
            if not row.get(k):
                raise RegistryError(f"job {jid} missing {k}")
        row.update(state=state, blocked_reason=blocked_reason if state == BLOCKED else "", attempts=0)
        digest = self.content_hash(row)
        with self.tx() as db:
            if db.execute("SELECT 1 FROM jobs WHERE job_id=?", (jid,)).fetchone():
                raise RegistryError(f"{jid} already exists; IDs are never reused")
            db.execute(
                "INSERT INTO jobs(job_id,title,lane,executor,assignee,target_host,requires,spec,verifier,level,state,"
                "blocked_reason,max_attempts,receipt_target,content_sha256,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (jid, row["title"], row["lane"], row["executor"], row["assignee"], row["target_host"],
                 canonical(row["requires"]), canonical(row["spec"]), canonical(row["verifier"]), row["level"],
                 state, row["blocked_reason"], int(row["max_attempts"]), row["receipt_target"], digest, now, now))
            self._lineage(db, jid, actor, transform, GENESIS_HASH, digest, source)
            self.ledger("job_created", actor, {"state": state, "reason": row["blocked_reason"], "source": source,
                                               "sha256": digest}, jid)
            back = self.get(jid)
            if not back or back["content_sha256"] != digest or back["state"] != state:
                raise RegistryError(f"read-back mismatch creating {jid}")
        return back

    def transition(self, job_id: str, to: str, *, actor: str, transform: str, expect_state: str,
                   expect_version: Optional[int] = None, reason: str = "", patch: Optional[Dict[str, Any]] = None,
                   note: str = "") -> Dict[str, Any]:
        if not JOB_ID.match(job_id):
            raise RegistryError("writes address one deterministic job id")
        with self.tx() as db:
            job = self.get(job_id)
            if not job:
                raise RegistryError(f"unknown job {job_id}")
            if job["state"] != expect_state or (expect_version is not None and job["version"] != expect_version):
                raise RegistryError(f"{job_id}: expected {expect_state} v{expect_version}, found "
                                    f"{job['state']} v{job['version']}")
            if (job["state"], to) not in TRANSITIONS:
                raise RegistryError(f"{job_id}: illegal transition {job['state']} -> {to}")
            fields = dict(patch or {})
            allowed = {"attempts", "max_attempts", "next_eligible_at", "lease_until", "first_run_at", "done_at"}
            if set(fields) - allowed:
                raise RegistryError(f"transition may not patch {sorted(set(fields) - allowed)}")
            new = {**job, **fields, "state": to, "blocked_reason": reason if to == BLOCKED else ""}
            digest = self.content_hash(new)
            sets = ", ".join(f"{k}=?" for k in fields)
            db.execute(f"UPDATE jobs SET state=?, blocked_reason=?, content_sha256=?, updated_at=?, version=version+1"
                       f"{', ' + sets if sets else ''} WHERE job_id=? AND version=?",
                       (to, new["blocked_reason"], digest, self.clock(), *fields.values(), job_id, job["version"]))
            self._lineage(db, job_id, actor, transform, job["content_sha256"], digest, note=note)
            self.ledger("transition", actor, {"from": display_state(job), "to": display_state(new),
                                              "transform": transform, "note": note}, job_id)
            back = self.get(job_id)
            if not back or back["state"] != to or back["version"] != job["version"] + 1 or \
                    back["content_sha256"] != digest:
                raise RegistryError(f"read-back mismatch on {job_id}")
        return back

    # ------------------------------------------------------------------ attempts
    def start_attempt(self, job_id: str, *, actor: str, lease_s: float) -> Dict[str, Any]:
        with self.tx() as db:
            job = self.get(job_id)
            if not job:
                raise RegistryError(f"unknown job {job_id}")
            now = self.clock()
            if job["state"] == QUEUED and job["attempts"] >= job["max_attempts"]:
                return self.transition(job_id, DEAD, actor=actor, transform="attempts_exhausted", expect_state=QUEUED,
                                       expect_version=job["version"])
            n = job["attempts"] + 1
            patch = {"attempts": n, "lease_until": now + lease_s}
            if job["first_run_at"] is None:
                patch["first_run_at"] = now
            out = self.transition(job_id, RUNNING, actor=actor, transform="attempt_start", expect_state=QUEUED,
                                  expect_version=job["version"], patch=patch, note=f"attempt {n}")
            db.execute("INSERT INTO attempts(job_id,n,started_at) VALUES (?,?,?)", (job_id, n, now))
            return out

    def finish_attempt(self, job_id: str, *, actor: str, verified: bool, outcome: str, error_class: str = "",
                       error: str = "", cpu_s: float = 0.0, rss_kb: int = 0, block_reason: str = "") -> Dict[str, Any]:
        """verified=True only when the job's deterministic verifier passed. Anything else is a failed attempt."""
        with self.tx() as db:
            job = self.get(job_id)
            if not job or job["state"] != RUNNING:
                raise RegistryError(f"{job_id} is not RUNNING")
            now = self.clock()
            db.execute("UPDATE attempts SET ended_at=?, outcome=?, error_class=?, error=?, cpu_s=?, rss_kb=? "
                       "WHERE job_id=? AND n=? AND ended_at IS NULL",
                       (now, outcome, error_class, error[:2000], cpu_s, rss_kb, job_id, job["attempts"]))
            common = dict(actor=actor, expect_state=RUNNING, expect_version=job["version"])
            if verified:
                return self.transition(job_id, DONE, transform="verified", patch={"done_at": now, "lease_until": 0},
                                       note=outcome, **common)
            if block_reason:
                return self.transition(job_id, BLOCKED, transform="blocked", reason=block_reason,
                                       patch={"lease_until": 0}, note=error[:200], **common)
            if job["attempts"] >= job["max_attempts"]:
                return self.transition(job_id, DEAD, transform="attempts_exhausted", patch={"lease_until": 0},
                                       note=f"{error_class}: {error[:200]}", **common)
            return self.transition(job_id, QUEUED, transform="retry_backoff",
                                   patch={"lease_until": 0, "next_eligible_at": now + backoff_s(job["attempts"])},
                                   note=f"{error_class}: {error[:200]}", **common)

    def recover(self, *, actor: str = "ghostd:boot", in_process_executors: tuple = ()) -> List[str]:
        """Boot recovery: RUNNING jobs whose lease expired go back through the bounded retry path.
        Jobs whose executor lives inside the server process (codeact: its child dies with the server via
        PR_SET_PDEATHSIG) are certainly interrupted at boot and are recovered regardless of lease. Manual jobs keep
        their lease, because a remote agent may still be working on them."""
        now = self.clock()
        marks = ",".join("?" * len(in_process_executors)) or "''"
        stale = [r[0] for r in self.db.execute(
            f"SELECT job_id FROM jobs WHERE state='RUNNING' AND (lease_until < ? OR executor IN ({marks})) "
            "ORDER BY job_id", (now, *in_process_executors))]
        for jid in stale:
            self.finish_attempt(jid, actor=actor, verified=False, outcome="interrupted", error_class="interrupted",
                                error="lease expired (server restart or crash)")
        return stale

    def operator_transition(self, job_id: str, to: str, *, actor: str, transform: str, note: str = "") -> Dict[str, Any]:
        """Gate-only path (unblock / requeue / cancel). Callers must have passed gates.Gate.commit first."""
        job = self.get(job_id)
        if not job:
            raise RegistryError(f"unknown job {job_id}")
        patch: Dict[str, Any] = {"next_eligible_at": 0}
        if job["state"] == DEAD and to == QUEUED:
            patch["max_attempts"] = min(20, max(job["max_attempts"], job["attempts"]) + 1)
        return self.transition(job_id, to, actor=actor, transform=transform, expect_state=job["state"],
                               expect_version=job["version"], patch=patch, note=note,
                               reason="cancelled-by-operator" if to == BLOCKED else "")

    # ------------------------------------------------------------------ artifacts, escalations, envelopes
    def add_artifact(self, job_id: str, path: str, *, produced_by: str) -> str:
        data = open(path, "rb").read()
        digest = hashlib.sha256(data).hexdigest()
        with self.tx() as db:
            db.execute("INSERT OR IGNORE INTO artifacts VALUES (?,?,?,?,?,?)",
                       (digest, job_id, path, len(data), produced_by, self.clock()))
            job = self.get(job_id)
            if job:
                self._lineage(db, job_id, produced_by, "artifact", job["content_sha256"], job["content_sha256"],
                              source=path, note=f"sha256={digest}")
        return digest

    def escalate(self, *, job_id: str, action: str, reason: str, actor: str) -> int:
        with self.tx() as db:
            cur = db.execute("INSERT INTO escalations(at,job_id,action,reason) VALUES (?,?,?,?)",
                             (self.clock(), job_id, action, reason))
            self.ledger("escalated_to_brandon", actor, {"action": action, "reason": reason, "esc_id": cur.lastrowid},
                        job_id)
            return int(cur.lastrowid)

    def consume_nonce(self, nonce: str) -> bool:
        try:
            with self.tx() as db:
                db.execute("INSERT INTO nonces VALUES (?,?)", (nonce, self.clock()))
            return True
        except sqlite3.IntegrityError:
            return False

    def record_envelope(self, env: Dict[str, Any], direction: str, state: str) -> bool:
        """False if this envelope id was already recorded (idempotent redelivery)."""
        try:
            with self.tx() as db:
                db.execute("INSERT INTO envelopes VALUES (?,?,?,?,?,?,?,?)",
                           (env["id"], direction, env["to"] if direction == "out" else env["from"], env["kind"],
                            env.get("job_id", ""), state, canonical(env), self.clock()))
            return True
        except sqlite3.IntegrityError:
            return False

    def set_door_state(self, name: str, body: Dict[str, Any]) -> None:
        with self.tx() as db:
            db.execute("INSERT INTO door_state VALUES (?,?,?) ON CONFLICT(name) DO UPDATE SET body=excluded.body, "
                       "at=excluded.at", (name, canonical(body), self.clock()))

    def door_states(self) -> Dict[str, Dict[str, Any]]:
        return {r["name"]: {**json.loads(r["body"]), "at": r["at"]}
                for r in self.db.execute("SELECT * FROM door_state ORDER BY name")}

    # ------------------------------------------------------------------ heartbeat + provenance
    def heartbeat(self, pid: int) -> None:
        with self.tx() as db:
            db.execute("INSERT INTO heartbeat VALUES (1,?,?) ON CONFLICT(id) DO UPDATE SET at=excluded.at, pid=excluded.pid",
                       (self.clock(), pid))

    def heartbeat_age(self) -> Optional[float]:
        r = self.db.execute("SELECT at FROM heartbeat WHERE id=1").fetchone()
        return None if not r else self.clock() - r["at"]

    def provenance(self, job_id: str) -> Dict[str, Any]:
        q = lambda sql: [dict(r) for r in self.db.execute(sql, (job_id,))]  # noqa: E731
        return {
            "job": self.get(job_id),
            "lineage": q("SELECT * FROM lineage WHERE job_id=? ORDER BY seq"),
            "attempts": q("SELECT * FROM attempts WHERE job_id=? ORDER BY n"),
            "artifacts": q("SELECT * FROM artifacts WHERE job_id=? ORDER BY at"),
            "envelopes": q("SELECT env_id,direction,peer,kind,state,at FROM envelopes WHERE job_id=? ORDER BY at"),
            "escalations": q("SELECT * FROM escalations WHERE job_id=? ORDER BY esc_id"),
            "ledger": q("SELECT seq,at,kind,actor,body,hash FROM ledger WHERE job_id=? ORDER BY seq"),
        }

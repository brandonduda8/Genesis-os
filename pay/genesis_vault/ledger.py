"""Genesis Vault ledger: personal-treasury records beside Genesis Pay.

Same discipline as Genesis Pay S0: integer cents only, double entry with a
zero-sum trigger, append-only postings, idempotency keys, a hash-chained audit
log, WAL + synchronous=FULL.

The Vault RECORDS money facts that Brandon enters by hand or imports from his
own statements. It never moves money, never holds credentials, never talks to a
bank or payment app. There is deliberately no network or subprocess code in
this package (a test enforces it).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

INSTITUTIONS = ("cash_app", "paypal", "current", "onepay", "chime", "robinhood", "bank", "internal")
OUTCOMES = ("paid", "arranged", "disputed", "cancelled")
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}\Z")
RECONCILIATION = "reconciliation"
GENESIS_HASH = "0" * 64

# Cents columns are declared WITHOUT a type on purpose: an INTEGER column's type
# affinity would silently turn the text '5.00' (dollars) into the integer 5 (cents)
# before any CHECK or trigger sees it. With no affinity, typeof() rejects it.
SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('asset', 'liability', 'equity')),
    institution TEXT NOT NULL CHECK (institution IN
        ('cash_app', 'paypal', 'current', 'onepay', 'chime', 'robinhood', 'bank', 'internal')),
    buffer_cents NOT NULL DEFAULT 0
        CHECK (typeof(buffer_cents) = 'integer' AND buffer_cents >= 0),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    effective_date TEXT NOT NULL,
    memo TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('manual', 'statement_import', 'balance_assertion')),
    posted INTEGER NOT NULL DEFAULT 0 CHECK (posted IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS postings (
    id INTEGER PRIMARY KEY,
    entry_id INTEGER NOT NULL REFERENCES entries(id),
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    amount_cents NOT NULL
        CHECK (typeof(amount_cents) = 'integer' AND amount_cents <> 0)
);

CREATE TABLE IF NOT EXISTS obligations (
    id INTEGER PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    account_id INTEGER REFERENCES accounts(id),
    payee TEXT NOT NULL,
    amount_cents NOT NULL CHECK (typeof(amount_cents) = 'integer' AND amount_cents > 0),
    due_date TEXT,
    kind TEXT NOT NULL CHECK (kind IN ('bill', 'scheduled_debit')),
    notice TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'paid', 'arranged', 'disputed', 'cancelled')),
    outcome_note TEXT,
    outcome_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    seq INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    event TEXT NOT NULL,
    payload TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL
);

-- Postings are append-only and may only be added to an entry that is not yet posted.
CREATE TRIGGER IF NOT EXISTS postings_no_update BEFORE UPDATE ON postings
BEGIN SELECT RAISE(ABORT, 'postings are append-only'); END;
CREATE TRIGGER IF NOT EXISTS postings_no_delete BEFORE DELETE ON postings
BEGIN SELECT RAISE(ABORT, 'postings are append-only'); END;
CREATE TRIGGER IF NOT EXISTS postings_only_on_open_entry BEFORE INSERT ON postings
WHEN (SELECT posted FROM entries WHERE id = NEW.entry_id) IS NOT 0
BEGIN SELECT RAISE(ABORT, 'entry is posted or missing'); END;

-- Zero-sum: an entry can only become posted if it has 2+ postings summing to 0.
CREATE TRIGGER IF NOT EXISTS entries_zero_sum BEFORE UPDATE ON entries
WHEN NEW.posted = 1 AND (
    (SELECT COUNT(*) FROM postings WHERE entry_id = NEW.id) < 2
    OR (SELECT SUM(amount_cents) FROM postings WHERE entry_id = NEW.id) <> 0)
BEGIN SELECT RAISE(ABORT, 'unbalanced entry: postings must be 2+ and sum to zero'); END;
-- The only permitted update is open -> posted with nothing else changed.
CREATE TRIGGER IF NOT EXISTS entries_immutable BEFORE UPDATE ON entries
WHEN OLD.posted = 1 OR NEW.posted <> 1 OR NEW.id <> OLD.id
    OR NEW.idempotency_key IS NOT OLD.idempotency_key OR NEW.effective_date IS NOT OLD.effective_date
    OR NEW.memo IS NOT OLD.memo OR NEW.source IS NOT OLD.source OR NEW.created_at IS NOT OLD.created_at
BEGIN SELECT RAISE(ABORT, 'entries are immutable once posted'); END;
CREATE TRIGGER IF NOT EXISTS entries_no_delete BEFORE DELETE ON entries
WHEN OLD.posted = 1
BEGIN SELECT RAISE(ABORT, 'posted entries cannot be deleted'); END;

-- Obligations: the only change is Brandon recording one outcome on an open item.
CREATE TRIGGER IF NOT EXISTS obligations_outcome_once BEFORE UPDATE ON obligations
WHEN OLD.status <> 'open' OR NEW.status = 'open'
    OR NEW.amount_cents IS NOT OLD.amount_cents OR NEW.payee IS NOT OLD.payee
    OR NEW.due_date IS NOT OLD.due_date OR NEW.account_id IS NOT OLD.account_id
    OR NEW.kind IS NOT OLD.kind OR NEW.idempotency_key IS NOT OLD.idempotency_key
BEGIN SELECT RAISE(ABORT, 'obligation outcome can be recorded once, on an open item'); END;
CREATE TRIGGER IF NOT EXISTS obligations_no_delete BEFORE DELETE ON obligations
BEGIN SELECT RAISE(ABORT, 'obligations cannot be deleted; record an outcome'); END;

CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
"""


class VaultError(ValueError):
    """Rejected input or a violated ledger rule."""


def parse_cents(raw: str | int) -> int:
    """'12.34' -> 1234. Exact decimal parsing; floats are refused, never rounded."""
    if isinstance(raw, bool) or isinstance(raw, float):
        raise VaultError("amounts must be strings like '12.34' or integer cents, not floats")
    if isinstance(raw, int):
        return raw
    text = str(raw).strip().replace(",", "").lstrip("$")
    neg = text.startswith("-")
    if neg:
        text = text[1:].lstrip("$")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise VaultError(f"not an amount: {raw!r}") from None
    if not value.is_finite() or value.as_tuple().exponent < -2:
        raise VaultError(f"amount must have at most 2 decimals: {raw!r}")
    cents = int(value * 100)
    return -cents if neg else cents


def fmt_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}${cents // 100:,}.{cents % 100:02d}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_date(raw: str | None) -> str | None:
    if raw is None or raw == "":
        return None
    try:
        return date.fromisoformat(raw).isoformat()
    except (TypeError, ValueError):
        raise VaultError(f"date must be YYYY-MM-DD: {raw!r}") from None


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class Vault:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.db = sqlite3.connect(self.path, isolation_level=None)
        self._depth = 0
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.execute("PRAGMA synchronous = FULL")
        self.db.executescript(SCHEMA)
        if self._account_id(RECONCILIATION, required=False) is None:
            with self._tx():
                self._insert_account(RECONCILIATION, "Balance reconciliation (equity)", "equity", "internal", 0)

    def close(self) -> None:
        self.db.close()

    # ---------- plumbing ----------
    def _tx(self):
        vault = self

        class Tx:
            def __enter__(self):
                if vault._depth == 0:
                    vault.db.execute("BEGIN IMMEDIATE")
                vault._depth += 1

            def __exit__(self, exc_type, *_):
                vault._depth -= 1
                if vault._depth == 0:
                    vault.db.execute("COMMIT" if exc_type is None else "ROLLBACK")
                return False  # an inner failure propagates; the outermost block rolls back

        return Tx()

    def _audit(self, event: str, payload: dict) -> None:
        last = self.db.execute("SELECT seq, hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
        seq, prev = (last["seq"] + 1, last["hash"]) if last else (1, GENESIS_HASH)
        ts = _now()
        body = _canon(payload)
        digest = hashlib.sha256(_canon([seq, ts, event, body, prev]).encode()).hexdigest()
        self.db.execute("INSERT INTO audit_log (seq, ts, event, payload, prev_hash, hash) VALUES (?,?,?,?,?,?)",
                        (seq, ts, event, body, prev, digest))

    def verify_audit(self) -> dict:
        prev, n = GENESIS_HASH, 0
        for row in self.db.execute("SELECT * FROM audit_log ORDER BY seq"):
            n += 1
            want = hashlib.sha256(_canon([row["seq"], row["ts"], row["event"], row["payload"], prev]).encode()).hexdigest()
            if row["seq"] != n or row["prev_hash"] != prev or row["hash"] != want:
                return {"ok": False, "records": n - 1, "error": f"audit chain broken at seq {n}"}
            prev = row["hash"]
        return {"ok": True, "records": n, "head": prev}

    def _account_id(self, slug: str, required: bool = True) -> int | None:
        row = self.db.execute("SELECT id FROM accounts WHERE slug = ?", (slug,)).fetchone()
        if row is None and required:
            raise VaultError(f"unknown account: {slug!r}")
        return row["id"] if row else None

    def _insert_account(self, slug, name, kind, institution, buffer_cents) -> int:
        cur = self.db.execute(
            "INSERT INTO accounts (slug, name, kind, institution, buffer_cents, created_at) VALUES (?,?,?,?,?,?)",
            (slug, name, kind, institution, buffer_cents, _now()))
        self._audit("account.add", {"slug": slug, "institution": institution, "kind": kind})
        return cur.lastrowid

    # ---------- accounts ----------
    def add_account(self, slug: str, name: str, institution: str, *, kind: str = "asset",
                    buffer: str | int = 0) -> int:
        if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug) or slug == RECONCILIATION:
            raise VaultError("slug must be lowercase letters/digits/_/-, up to 40 chars")
        if institution not in INSTITUTIONS or kind not in ("asset", "liability"):
            raise VaultError(f"institution must be one of {INSTITUTIONS}; kind asset or liability")
        buffer_cents = parse_cents(buffer)
        if buffer_cents < 0:
            raise VaultError("buffer cannot be negative")
        existing = self._account_id(slug, required=False)
        if existing is not None:
            return existing
        with self._tx():
            return self._insert_account(slug, name, kind, institution, buffer_cents)

    def accounts(self) -> list[dict]:
        rows = self.db.execute("SELECT * FROM accounts WHERE kind <> 'equity' ORDER BY slug").fetchall()
        return [dict(r) for r in rows]

    # ---------- double entry ----------
    def post_entry(self, key: str, effective_date: str, memo: str, postings: list[tuple[str, int]],
                   *, source: str = "manual") -> int:
        """Record a balanced entry atomically. Re-using a key returns the original entry."""
        if not isinstance(key, str) or not key:
            raise VaultError("idempotency key required")
        row = self.db.execute("SELECT id, posted FROM entries WHERE idempotency_key = ?", (key,)).fetchone()
        if row is not None:
            return row["id"]
        eff = _iso_date(effective_date)
        resolved = []
        for slug, cents in postings:
            if isinstance(cents, bool) or not isinstance(cents, int):
                raise VaultError("posting amounts must be integer cents")
            resolved.append((self._account_id(slug), cents))
        try:
            with self._tx():
                cur = self.db.execute(
                    "INSERT INTO entries (idempotency_key, effective_date, memo, source, created_at) VALUES (?,?,?,?,?)",
                    (key, eff, memo, source, _now()))
                entry_id = cur.lastrowid
                self.db.executemany("INSERT INTO postings (entry_id, account_id, amount_cents) VALUES (?,?,?)",
                                    [(entry_id, a, c) for a, c in resolved])
                self.db.execute("UPDATE entries SET posted = 1 WHERE id = ?", (entry_id,))
                self._audit("entry.post", {"entry": entry_id, "key": key, "source": source,
                                           "postings": [[s, c] for s, c in postings]})
        except sqlite3.IntegrityError as exc:
            raise VaultError(str(exc)) from None
        return entry_id

    def balance(self, slug: str) -> int:
        aid = self._account_id(slug)
        row = self.db.execute(
            "SELECT COALESCE(SUM(p.amount_cents), 0) AS s FROM postings p JOIN entries e ON e.id = p.entry_id "
            "WHERE e.posted = 1 AND p.account_id = ?", (aid,)).fetchone()
        return row["s"]

    def last_balance_date(self, slug: str) -> str | None:
        aid = self._account_id(slug)
        row = self.db.execute(
            "SELECT MAX(e.effective_date) AS d FROM entries e JOIN postings p ON p.entry_id = e.id "
            "WHERE e.posted = 1 AND p.account_id = ? AND e.source IN ('balance_assertion', 'statement_import')",
            (aid,)).fetchone()
        # A stated balance equal to the ledger balance books nothing, so also read the audit record.
        stated = self.db.execute("SELECT MAX(json_extract(payload, '$.as_of')) AS d FROM audit_log "
                                 "WHERE event = 'balance.assert' AND json_extract(payload, '$.account') = ?",
                                 (slug,)).fetchone()["d"]
        return max(d for d in (row["d"], stated) if d) if (row["d"] or stated) else None

    def balance_known(self, slug: str) -> bool:
        aid = self._account_id(slug)
        return self.db.execute("SELECT 1 FROM postings p JOIN entries e ON e.id = p.entry_id "
                               "WHERE e.posted = 1 AND p.account_id = ? LIMIT 1", (aid,)).fetchone() is not None \
            or self.db.execute("SELECT 1 FROM audit_log WHERE event = 'balance.assert' AND json_extract(payload, '$.account') = ? LIMIT 1",
                               (slug,)).fetchone() is not None

    def ledger_total(self) -> int:
        return self.db.execute("SELECT COALESCE(SUM(p.amount_cents), 0) AS s FROM postings p "
                               "JOIN entries e ON e.id = p.entry_id WHERE e.posted = 1").fetchone()["s"]

    def set_balance(self, slug: str, amount: str | int, as_of: str, *, key: str | None = None,
                    source: str = "balance_assertion") -> int | None:
        """Brandon states a balance he read in the app or on a statement. The difference is
        booked against the reconciliation equity account so the ledger stays zero-sum."""
        target = parse_cents(amount)
        as_of = _iso_date(as_of)
        if self.db.execute("SELECT kind FROM accounts WHERE slug = ?", (slug,)).fetchone() is None:
            raise VaultError(f"unknown account: {slug!r}")
        key = key or f"balance:{slug}:{as_of}:{target}"
        if self.db.execute("SELECT 1 FROM entries WHERE idempotency_key = ?", (key,)).fetchone():
            return None
        delta = target - self.balance(slug)
        if delta == 0:
            with self._tx():
                self._audit("balance.assert", {"account": slug, "as_of": as_of, "cents": target, "delta": 0})
            return None
        entry = self.post_entry(key, as_of, f"Balance stated: {slug} = {fmt_cents(target)}",
                                [(slug, delta), (RECONCILIATION, -delta)], source=source)
        with self._tx():
            self._audit("balance.assert", {"account": slug, "as_of": as_of, "cents": target, "delta": delta})
        return entry

    def record_completed_transfer(self, key: str, from_slug: str, to_slug: str, amount: str | int,
                                  on: str, memo: str = "") -> int:
        """Bookkeeping for a transfer Brandon ALREADY made himself in the provider's app."""
        cents = parse_cents(amount)
        if cents <= 0 or from_slug == to_slug:
            raise VaultError("transfer needs a positive amount and two different accounts")
        return self.post_entry(key, on, memo or f"Brandon moved {fmt_cents(cents)} {from_slug} -> {to_slug}",
                               [(from_slug, -cents), (to_slug, cents)], source="manual")

    def import_balances_csv(self, text: str, *, source_name: str = "statement") -> int:
        """CSV with header account,balance,as_of. All rows apply or none do."""
        file_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        rows = list(csv.DictReader(io.StringIO(text)))
        if not rows or set(rows[0]) != {"account", "balance", "as_of"}:
            raise VaultError("CSV header must be exactly: account,balance,as_of")
        parsed = []
        for i, r in enumerate(rows, 2):
            try:
                parsed.append((r["account"].strip(), parse_cents(r["balance"]), _iso_date(r["as_of"].strip())))
            except (VaultError, AttributeError) as exc:
                raise VaultError(f"line {i}: {exc}") from None
            self._account_id(parsed[-1][0])
        applied = 0
        with self._tx():  # one transaction: a failing row leaves nothing behind
            for i, (slug, cents, as_of) in enumerate(parsed):
                if self.set_balance(slug, cents, as_of, key=f"import:{file_hash}:{i}", source="statement_import"):
                    applied += 1
            self._audit("import.balances", {"source": source_name, "sha256_16": file_hash, "rows": len(parsed)})
        return applied

    # ---------- obligations ----------
    def add_obligation(self, key: str, payee: str, amount: str | int, *, due_date: str | None = None,
                       account: str | None = None, kind: str = "bill", notice: str = "") -> int:
        cents = parse_cents(amount)
        if cents <= 0 or not payee.strip():
            raise VaultError("obligation needs a payee and a positive amount")
        row = self.db.execute("SELECT id FROM obligations WHERE idempotency_key = ?", (key,)).fetchone()
        if row:
            return row["id"]
        aid = self._account_id(account) if account else None
        try:
            with self._tx():
                cur = self.db.execute(
                    "INSERT INTO obligations (idempotency_key, account_id, payee, amount_cents, due_date, kind, notice, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?)", (key, aid, payee.strip(), cents, _iso_date(due_date), kind, notice, _now()))
                self._audit("obligation.add", {"id": cur.lastrowid, "payee": payee, "cents": cents,
                                               "due": due_date, "account": account, "notice": notice})
        except sqlite3.IntegrityError as exc:
            raise VaultError(str(exc)) from None
        return cur.lastrowid

    def mark_outcome(self, obligation_id: int, outcome: str, note: str = "") -> None:
        """Brandon records what happened. Genesis never pays; it only records the outcome."""
        if outcome not in OUTCOMES:
            raise VaultError(f"outcome must be one of {OUTCOMES}")
        try:
            with self._tx():
                cur = self.db.execute("UPDATE obligations SET status = ?, outcome_note = ?, outcome_at = ? WHERE id = ?",
                                      (outcome, note, _now(), obligation_id))
                if cur.rowcount != 1:
                    raise VaultError(f"no obligation {obligation_id}")
                self._audit("obligation.outcome", {"id": obligation_id, "outcome": outcome, "note": note})
        except sqlite3.IntegrityError as exc:
            raise VaultError(str(exc)) from None

    def obligations(self, status: str | None = "open") -> list[dict]:
        sql = ("SELECT o.*, a.slug AS account FROM obligations o LEFT JOIN accounts a ON a.id = o.account_id"
               + (" WHERE o.status = ?" if status else "") + " ORDER BY o.id")
        return [dict(r) for r in self.db.execute(sql, (status,) if status else ())]

    # ---------- snapshot for the rules engine ----------
    def snapshot(self) -> dict:
        return {
            "accounts": [{"slug": a["slug"], "name": a["name"], "institution": a["institution"],
                          "kind": a["kind"], "buffer_cents": a["buffer_cents"],
                          "balance_cents": self.balance(a["slug"]) if self.balance_known(a["slug"]) else None,
                          "balance_as_of": self.last_balance_date(a["slug"])}
                         for a in self.accounts()],
            "obligations": [{"id": o["id"], "payee": o["payee"], "amount_cents": o["amount_cents"],
                             "due_date": o["due_date"], "account": o["account"], "kind": o["kind"],
                             "notice": o["notice"]} for o in self.obligations("open")],
        }

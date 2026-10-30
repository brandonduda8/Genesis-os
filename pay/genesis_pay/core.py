"""Genesis Pay S0 core.

Design of record: genesis-os/war-room/GENESIS_POWER_PLAN_RE_2026-10-17.md §5.
Sits *behind* Apex Invoicing (system of record for what is owed) and *in
front of* a future Hyperswitch adapter (S2). It consumes Apex invoice /
payment dicts and events; it never edits Apex data and never moves money.

Storage: a dedicated SQLite database (separate from the live Apex DB) with
an append-only double-entry journal enforced by SQLite triggers.
All money is integer minor units (cents). No floats anywhere near money.
"""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from .errors import (
    CapExceededError, ConflictError, GateError, NotFoundError, PayError,
    SignatureError, StateError, ValidationError,
)

# ---------------------------------------------------------------- constants
ACCT_BANK = "1000_bank_cash"
ACCT_AR = "1100_accounts_receivable"
ACCT_CLEARING_PREFIX = "1200_clearing:"          # + rail, e.g. 1200_clearing:cash_app
ACCT_DISPUTES_FROZEN = "1300_disputes_frozen"
ACCT_DISPUTES_RESERVE = "2100_disputes_reserve"
ACCT_REVENUE = "4000_revenue"
ACCT_FEES = "5100_processor_fees"
ACCT_REFUNDS = "5200_refunds"
ACCT_DISPUTE_LOSSES = "5300_dispute_losses"

SEED_ACCOUNTS = [
    (ACCT_BANK, "Bank cash", "asset", "debit"),
    (ACCT_AR, "Accounts receivable", "asset", "debit"),
    (ACCT_DISPUTES_FROZEN, "Disputes frozen (contested funds segregated)", "asset", "debit"),
    (ACCT_DISPUTES_RESERVE, "Disputes reserve", "liability", "credit"),
    (ACCT_REVENUE, "Revenue", "revenue", "credit"),
    (ACCT_FEES, "Processor fees", "expense", "debit"),
    (ACCT_REFUNDS, "Refunds (contra revenue)", "contra_revenue", "debit"),
    (ACCT_DISPUTE_LOSSES, "Dispute losses", "expense", "debit"),
]

# Strict forward-only intent state machine (I-14). UNKNOWN is exited ONLY
# via resolve_unknown() — it is intentionally absent as a normal target of
# resolve paths and no other transition function may move out of it.
TRANSITIONS = {
    "created": {"pending", "confirmed", "cancelled", "failed", "unknown"},
    "pending": {"confirmed", "cancelled", "failed", "unknown"},
    "confirmed": {"settling", "settled", "disputed", "unknown"},
    "settling": {"settled", "failed", "unknown"},
    "settled": {"disputed", "partially_refunded", "refunded"},
    "disputed": {"settled", "partially_refunded", "refunded"},
    "partially_refunded": {"refunded", "disputed"},
    "unknown": set(),          # resolve_unknown() only
    "refunded": set(),
    "cancelled": set(),
    "failed": set(),
}
RESOLVABLE_FROM_UNKNOWN = {"confirmed", "settled", "failed"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    code TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL,
    normal_side TEXT NOT NULL CHECK (normal_side IN ('debit','credit')),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS journal_entries (
    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, memo TEXT NOT NULL,
    currency TEXT NOT NULL, external_ref TEXT,
    external_ref_flag TEXT NOT NULL CHECK (external_ref_flag IN ('mapped','unmapped_flagged')),
    reversal_of TEXT, source TEXT NOT NULL DEFAULT 'genesis_pay',
    debit_total_cents INTEGER, credit_total_cents INTEGER, line_count INTEGER
);
CREATE TABLE IF NOT EXISTS journal_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT NOT NULL REFERENCES journal_entries(id),
    account_code TEXT NOT NULL REFERENCES accounts(code),
    side TEXT NOT NULL CHECK (side IN ('debit','credit')),
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    currency TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS external_ref_map (
    external_ref TEXT PRIMARY KEY, entry_id TEXT NOT NULL, source TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS invoices_mirror (
    external_invoice_ref TEXT PRIMARY KEY, amount_cents INTEGER NOT NULL,
    currency TEXT NOT NULL, status TEXT NOT NULL, apex_status TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payment_intents (
    id TEXT PRIMARY KEY, invoice_ref TEXT NOT NULL, amount_cents INTEGER NOT NULL,
    currency TEXT NOT NULL, rail TEXT NOT NULL, state TEXT NOT NULL,
    external_ref TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS idempotency_keys (
    key TEXT PRIMARY KEY, payload_hash TEXT NOT NULL, result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outbox_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL,
    payload_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS webhook_inbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT NOT NULL,
    event_id TEXT NOT NULL, payload_json TEXT NOT NULL,
    verified INTEGER NOT NULL DEFAULT 0, received_at TEXT NOT NULL,
    UNIQUE (provider, event_id)
);
CREATE TABLE IF NOT EXISTS disputes (
    id TEXT PRIMARY KEY, intent_id TEXT NOT NULL, invoice_ref TEXT NOT NULL,
    amount_cents INTEGER NOT NULL, currency TEXT NOT NULL,
    status TEXT NOT NULL, reason TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS refunds (
    id TEXT PRIMARY KEY, intent_id TEXT, invoice_ref TEXT NOT NULL,
    amount_cents INTEGER NOT NULL, currency TEXT NOT NULL,
    tap_request_id TEXT NOT NULL, external_ref TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tap_requests (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload_json TEXT NOT NULL,
    payload_hash TEXT NOT NULL, destination TEXT, amount_cents INTEGER,
    currency TEXT, initiator TEXT NOT NULL, status TEXT NOT NULL,
    approver TEXT, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
    approved_at TEXT, cooldown_until TEXT, consumed_at TEXT
);
CREATE TABLE IF NOT EXISTS reconciliation_runs (
    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, matched INTEGER NOT NULL,
    breaks INTEGER NOT NULL, summary_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reconciliation_exceptions (
    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, external_ref TEXT,
    break_type TEXT NOT NULL, detail_json TEXT NOT NULL, owner TEXT NOT NULL,
    sla_due TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
    event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
    prev_hash TEXT NOT NULL, hash TEXT NOT NULL
);
-- Append-only enforcement (I-6): journal + audit can never be edited away.
CREATE TRIGGER IF NOT EXISTS journal_entries_no_update
BEFORE UPDATE ON journal_entries BEGIN SELECT RAISE(ABORT,'journal_entries is append-only'); END;
CREATE TRIGGER IF NOT EXISTS journal_entries_no_delete
BEFORE DELETE ON journal_entries BEGIN SELECT RAISE(ABORT,'journal_entries is append-only'); END;
CREATE TRIGGER IF NOT EXISTS journal_lines_no_update
BEFORE UPDATE ON journal_lines BEGIN SELECT RAISE(ABORT,'journal_lines is append-only'); END;
CREATE TRIGGER IF NOT EXISTS journal_lines_no_delete
BEFORE DELETE ON journal_lines BEGIN SELECT RAISE(ABORT,'journal_lines is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_log_no_update
BEFORE UPDATE ON audit_log BEGIN SELECT RAISE(ABORT,'audit_log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
BEFORE DELETE ON audit_log BEGIN SELECT RAISE(ABORT,'audit_log is append-only'); END;
-- Tap-request payloads are immutable (I-20): status may move, payload may not.
CREATE TRIGGER IF NOT EXISTS tap_requests_payload_immutable
BEFORE UPDATE ON tap_requests WHEN OLD.payload_hash <> NEW.payload_hash
BEGIN SELECT RAISE(ABORT,'tap request payload is immutable'); END;
"""


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat(timespec="seconds")


def _parse_iso(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _hash(obj_or_text):
    text = obj_or_text if isinstance(obj_or_text, str) else _canonical(obj_or_text)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _new_id(prefix):
    return "%s_%s" % (prefix, secrets.token_hex(10))


def _check_money(amount, field="amount_cents"):
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise ValidationError("%s must be an integer of minor units (no floats)" % field)
    if amount <= 0:
        raise ValidationError("%s must be > 0" % field)
    return amount


def _check_currency(currency):
    c = str(currency or "").upper()
    if len(c) != 3 or not c.isalpha():
        raise ValidationError("explicit 3-letter currency is required, got %r" % (currency,))
    return c


class GenesisPay:
    """One Genesis Pay S0 instance over one dedicated SQLite file."""

    def __init__(self, db_path, webhook_secret=None):
        self.db_path = db_path
        self.webhook_secret = webhook_secret
        if db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._conn = sqlite3.connect(db_path, timeout=30)
        self._conn.row_factory = sqlite3.Row
        self._conn.isolation_level = None  # explicit BEGIN IMMEDIATE control
        self._conn.execute("PRAGMA foreign_keys = ON")
        if db_path != ":memory:":
            # Durability (Argon RALPH-004 acceptance bar): WAL + FULL sync —
            # a committed posting survives a power loss / VM recycle.
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA synchronous = FULL")
        self._conn.executescript(SCHEMA)
        self._migrate_zero_sum(self._conn)
        for code, name, typ, side in SEED_ACCOUNTS:
            self._conn.execute(
                "INSERT OR IGNORE INTO accounts (code,name,type,normal_side,created_at) "
                "VALUES (?,?,?,?,?)", (code, name, typ, side, _iso(_now())))

    # DB-level zero-sum enforcement (Argon RALPH-004 convergence): the
    # entry declares its totals + line count up front; a trigger verifies
    # the ACTUAL line sums against the declaration the moment the final
    # line lands — so even writes that bypass the posting API cannot land
    # an unbalanced entry. The API check in _post_journal_tx remains the
    # first line of defense; this trigger is the database's own.
    _ZERO_SUM_TRIGGER = """
    CREATE TRIGGER IF NOT EXISTS journal_lines_zero_sum
    AFTER INSERT ON journal_lines
    WHEN (SELECT line_count FROM journal_entries WHERE id = NEW.entry_id) IS NOT NULL
      AND (SELECT COUNT(*) FROM journal_lines WHERE entry_id = NEW.entry_id)
          >= (SELECT line_count FROM journal_entries WHERE id = NEW.entry_id)
    BEGIN
      SELECT RAISE(ABORT, 'zero-sum violation: journal entry does not balance')
      WHERE (SELECT debit_total_cents FROM journal_entries WHERE id = NEW.entry_id)
            != (SELECT credit_total_cents FROM journal_entries WHERE id = NEW.entry_id)
         OR (SELECT COALESCE(SUM(amount_cents),0) FROM journal_lines
             WHERE entry_id = NEW.entry_id AND side = 'debit')
            != (SELECT debit_total_cents FROM journal_entries WHERE id = NEW.entry_id)
         OR (SELECT COALESCE(SUM(amount_cents),0) FROM journal_lines
             WHERE entry_id = NEW.entry_id AND side = 'credit')
            != (SELECT credit_total_cents FROM journal_entries WHERE id = NEW.entry_id);
    END;
    """

    @staticmethod
    def _migrate_zero_sum(conn):
        cols = {r[1] for r in conn.execute("PRAGMA table_info(journal_entries)")}
        for col in ("debit_total_cents", "credit_total_cents", "line_count"):
            if col not in cols:
                conn.execute("ALTER TABLE journal_entries ADD COLUMN %s INTEGER" % col)
        conn.executescript(GenesisPay._ZERO_SUM_TRIGGER)

    def close(self):
        self._conn.close()

    @contextmanager
    def _tx(self):
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    # ------------------------------------------------------- internal utils
    def _audit(self, conn, event_type, payload):
        row = conn.execute("SELECT hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
        prev = row["hash"] if row else "GENESIS_PAY_GENESIS"
        ts = _iso(_now())
        body = {"prev": prev, "type": event_type, "payload": payload, "at": ts}
        conn.execute(
            "INSERT INTO audit_log (created_at,event_type,payload_json,prev_hash,hash) "
            "VALUES (?,?,?,?,?)",
            (ts, event_type, _canonical(payload), prev, _hash(body)))

    def _outbox(self, conn, topic, payload):
        conn.execute("INSERT INTO outbox_events (topic,payload_json,created_at) VALUES (?,?,?)",
                     (topic, _canonical(payload), _iso(_now())))

    def _idempotent_check(self, conn, key, payload):
        """Return stored result dict on exact replay; raise 409 on conflict."""
        if not key or not str(key).strip():
            raise ValidationError("a client idempotency key is required on every money call")
        row = conn.execute("SELECT * FROM idempotency_keys WHERE key=?", (str(key),)).fetchone()
        if row is None:
            return None
        if row["payload_hash"] != _hash(payload):
            raise ConflictError(
                "idempotency key %r was already used with a different payload" % key)
        return json.loads(row["result_json"])

    def _idempotent_store(self, conn, key, payload, result):
        conn.execute(
            "INSERT INTO idempotency_keys (key,payload_hash,result_json,created_at) "
            "VALUES (?,?,?,?)", (str(key), _hash(payload), _canonical(result), _iso(_now())))

    def _ensure_account(self, conn, code):
        meta = {
            ACCT_BANK: ("Bank cash", "asset", "debit"),
            ACCT_AR: ("Accounts receivable", "asset", "debit"),
        }
        if code.startswith(ACCT_CLEARING_PREFIX):
            meta[code] = ("Clearing %s" % code.split(":", 1)[1], "asset", "debit")
        if code not in meta:
            row = conn.execute("SELECT code FROM accounts WHERE code=?", (code,)).fetchone()
            if not row:
                raise ValidationError("unknown account %r" % code)
            return
        name, typ, side = meta[code]
        conn.execute("INSERT OR IGNORE INTO accounts (code,name,type,normal_side,created_at) "
                     "VALUES (?,?,?,?,?)", (code, name, typ, side, _iso(_now())))

    def _transition(self, conn, intent, new_state):
        cur = intent["state"]
        if cur == "unknown":
            raise StateError(
                "intent %s is UNKNOWN; resolve it only via resolve_unknown() "
                "(query/resolution event), never by guessing" % intent["id"])
        if new_state not in TRANSITIONS.get(cur, set()):
            raise StateError("illegal intent transition %s -> %s (forward-only)"
                             % (cur, new_state))
        conn.execute("UPDATE payment_intents SET state=?, updated_at=? WHERE id=?",
                     (new_state, _iso(_now()), intent["id"]))
        return new_state

    def _get_intent(self, conn, intent_id):
        row = conn.execute("SELECT * FROM payment_intents WHERE id=?", (intent_id,)).fetchone()
        if not row:
            raise NotFoundError("payment intent %s not found" % intent_id)
        return dict(row)

    # ------------------------------------------------------------- ledger
    def post_journal(self, lines, memo, currency, external_ref=None,
                     reversal_of=None, idempotency_key=None):
        """Post one balanced double-entry journal entry.

        lines: [{"account": code, "side": "debit"|"credit", "amount_cents": int}]
        Key + journal (+ external-ref map, audit, outbox) commit atomically.
        """
        currency = _check_currency(currency)
        payload = {"lines": lines, "memo": memo, "currency": currency,
                   "external_ref": external_ref, "reversal_of": reversal_of}
        with self._tx() as conn:
            if idempotency_key:
                stored = self._idempotent_check(conn, idempotency_key, payload)
                if stored is not None:
                    return stored
            entry = self._post_journal_tx(conn, lines, memo, currency,
                                          external_ref, reversal_of)
            result = {"entry_id": entry, "external_ref": external_ref,
                      "external_ref_flag": "mapped" if external_ref else "unmapped_flagged",
                      "currency": currency}
            if idempotency_key:
                self._idempotent_store(conn, idempotency_key, payload, result)
            self._audit(conn, "journal.posted", result)
            self._outbox(conn, "journal.posted", result)
            return result

    def _post_journal_tx(self, conn, lines, memo, currency, external_ref, reversal_of=None):
        if not isinstance(lines, list) or len(lines) < 2:
            raise ValidationError("a journal entry needs at least two lines")
        debits = credits = 0
        norm = []
        for i, ln in enumerate(lines):
            amount = _check_money(ln.get("amount_cents"), "lines[%d].amount_cents" % i)
            side = ln.get("side")
            if side not in ("debit", "credit"):
                raise ValidationError("lines[%d].side must be debit|credit" % i)
            if _check_currency(ln.get("currency", currency)) != currency:
                raise ValidationError("all lines of an entry share one explicit currency")
            self._ensure_account(conn, ln["account"])
            norm.append((ln["account"], side, amount))
            if side == "debit":
                debits += amount
            else:
                credits += amount
        if debits != credits:
            raise ValidationError(
                "unbalanced journal entry: debits=%d credits=%d" % (debits, credits))
        entry_id = _new_id("je")
        flag = "mapped" if external_ref else "unmapped_flagged"
        conn.execute(
            "INSERT INTO journal_entries (id,created_at,memo,currency,external_ref,"
            "external_ref_flag,reversal_of,debit_total_cents,credit_total_cents,"
            "line_count) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (entry_id, _iso(_now()), memo, currency, external_ref, flag, reversal_of,
             debits, credits, len(norm)))
        for account, side, amount in norm:
            conn.execute(
                "INSERT INTO journal_lines (entry_id,account_code,side,amount_cents,currency) "
                "VALUES (?,?,?,?,?)", (entry_id, account, side, amount, currency))
        if external_ref:
            existing = conn.execute("SELECT entry_id FROM external_ref_map WHERE external_ref=?",
                                    (str(external_ref),)).fetchone()
            if existing and existing["entry_id"] != entry_id:
                raise ConflictError(
                    "external_ref %r already maps to entry %s (one external ref per "
                    "transaction, I-11)" % (external_ref, existing["entry_id"]))
            conn.execute(
                "INSERT OR IGNORE INTO external_ref_map (external_ref,entry_id,source,created_at) "
                "VALUES (?,?,?,?)", (str(external_ref), entry_id, "genesis_pay", _iso(_now())))
        return entry_id

    def account_balance(self, account_code):
        """Signed balance as debits - credits (integer minor units)."""
        row = self._conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN side='debit' THEN amount_cents "
            "ELSE -amount_cents END),0) AS bal FROM journal_lines WHERE account_code=?",
            (account_code,)).fetchone()
        return int(row["bal"])

    def trial_balance(self):
        """All accounts; a correct ledger sums to exactly zero."""
        rows = self._conn.execute(
            "SELECT account_code, SUM(CASE WHEN side='debit' THEN amount_cents "
            "ELSE -amount_cents END) AS bal FROM journal_lines GROUP BY account_code").fetchall()
        out = {r["account_code"]: int(r["bal"]) for r in rows}
        out["_total_debits_minus_credits"] = sum(out.values())
        return out

    def journal_entries(self):
        rows = self._conn.execute("SELECT * FROM journal_entries ORDER BY created_at, id").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["lines"] = [dict(x) for x in self._conn.execute(
                "SELECT account_code,side,amount_cents,currency FROM journal_lines "
                "WHERE entry_id=? ORDER BY id", (r["id"],))]
            out.append(d)
        return out

    # ---------------------------------------------------- payment intents
    def create_payment_intent(self, invoice_ref, amount_cents, currency, rail,
                              idempotency_key, external_ref=None, initiator="system"):
        _check_money(amount_cents)
        currency = _check_currency(currency)
        if not str(rail or "").strip():
            raise ValidationError("rail is required")
        payload = {"op": "create_intent", "invoice_ref": str(invoice_ref),
                   "amount_cents": amount_cents, "currency": currency,
                   "rail": rail, "external_ref": external_ref}
        with self._tx() as conn:
            stored = self._idempotent_check(conn, idempotency_key, payload)
            if stored is not None:
                return stored
            intent_id = _new_id("pi")
            conn.execute(
                "INSERT INTO payment_intents (id,invoice_ref,amount_cents,currency,rail,"
                "state,external_ref,created_at,updated_at) VALUES (?,?,?,?,?,'created',?,?,?)",
                (intent_id, str(invoice_ref), amount_cents, currency, rail,
                 external_ref, _iso(_now()), _iso(_now())))
            result = {"intent_id": intent_id, "state": "created",
                      "invoice_ref": str(invoice_ref), "amount_cents": amount_cents,
                      "currency": currency, "rail": rail, "external_ref": external_ref}
            self._idempotent_store(conn, idempotency_key, payload, result)
            self._audit(conn, "intent.created", result)
            self._outbox(conn, "payment_intent.created", result)
            return result

    def get_intent(self, intent_id):
        return self._get_intent(self._conn, intent_id)

    def mark_pending(self, intent_id):
        with self._tx() as conn:
            intent = self._get_intent(conn, intent_id)
            self._transition(conn, intent, "pending")
            self._audit(conn, "intent.pending", {"intent_id": intent_id})
            return {"intent_id": intent_id, "state": "pending"}

    def mark_unknown(self, intent_id, reason):
        """Park an intent whose external outcome is genuinely unknown (I-22)."""
        with self._tx() as conn:
            intent = self._get_intent(conn, intent_id)
            self._transition(conn, intent, "unknown")
            self._audit(conn, "intent.unknown", {"intent_id": intent_id, "reason": reason})
            self._outbox(conn, "payment_intent.unknown",
                         {"intent_id": intent_id, "reason": reason})
            return {"intent_id": intent_id, "state": "unknown"}

    def resolve_unknown(self, intent_id, resolution_event):
        """The ONLY exit from UNKNOWN: an explicit query/resolution event.

        resolution_event: {"type": "query_result", "outcome":
        "confirmed"|"settled"|"failed", "external_ref": ...}
        """
        if not isinstance(resolution_event, dict) or resolution_event.get("type") != "query_result":
            raise ValidationError("UNKNOWN resolves only from a query_result resolution event")
        outcome = resolution_event.get("outcome")
        if outcome not in RESOLVABLE_FROM_UNKNOWN:
            raise ValidationError("resolution outcome must be one of %s"
                                  % sorted(RESOLVABLE_FROM_UNKNOWN))
        with self._tx() as conn:
            intent = self._get_intent(conn, intent_id)
            if intent["state"] != "unknown":
                raise StateError("intent %s is not UNKNOWN (state=%s)"
                                 % (intent_id, intent["state"]))
            conn.execute("UPDATE payment_intents SET state=?, updated_at=? WHERE id=?",
                         (outcome, _iso(_now()), intent_id))
            result = {"intent_id": intent_id, "state": outcome,
                      "resolved_by": "query_result"}
            self._audit(conn, "intent.unknown_resolved", result)
            self._outbox(conn, "payment_intent.unknown_resolved", result)
            return result

    # --------------------------------------------- Apex invoice integration
    @staticmethod
    def _invoice_ref(invoice):
        ref = invoice.get("invoice_number") or invoice.get("public_id") or invoice.get("id")
        if ref is None:
            raise ValidationError("Apex invoice dict needs invoice_number, public_id or id")
        return str(ref)

    def ingest_invoice_issued(self, invoice, idempotency_key):
        """Apex invoice issued/sent -> Dr AR / Cr Revenue (C1 -> C5)."""
        ref = self._invoice_ref(invoice)
        amount = _check_money(invoice.get("total_cents"), "invoice.total_cents")
        currency = _check_currency(invoice.get("currency", "USD"))
        payload = {"op": "invoice_issued", "ref": ref, "amount_cents": amount,
                   "currency": currency}
        with self._tx() as conn:
            stored = self._idempotent_check(conn, idempotency_key, payload)
            if stored is not None:
                return stored
            existing = conn.execute("SELECT * FROM invoices_mirror WHERE external_invoice_ref=?",
                                    (ref,)).fetchone()
            if existing:
                raise ConflictError("invoice %s already ingested" % ref)
            entry_id = self._post_journal_tx(conn, [
                {"account": ACCT_AR, "side": "debit", "amount_cents": amount},
                {"account": ACCT_REVENUE, "side": "credit", "amount_cents": amount},
            ], "Invoice issued %s" % ref, currency, external_ref="apex-invoice:%s" % ref)
            conn.execute(
                "INSERT INTO invoices_mirror (external_invoice_ref,amount_cents,currency,"
                "status,apex_status,created_at,updated_at) VALUES (?,?,?,'issued',?,?,?)",
                (ref, amount, currency, invoice.get("status"), _iso(_now()), _iso(_now())))
            result = {"invoice_ref": ref, "entry_id": entry_id, "amount_cents": amount,
                      "currency": currency, "status": "issued"}
            self._idempotent_store(conn, idempotency_key, payload, result)
            self._audit(conn, "invoice.issued", result)
            self._outbox(conn, "invoice.issued", result)
            return result

    def ingest_invoice_voided(self, invoice, idempotency_key):
        """Void = a NEW reversing entry (Dr Revenue / Cr AR). Never an edit."""
        ref = self._invoice_ref(invoice)
        payload = {"op": "invoice_voided", "ref": ref}
        with self._tx() as conn:
            stored = self._idempotent_check(conn, idempotency_key, payload)
            if stored is not None:
                return stored
            mirror = conn.execute("SELECT * FROM invoices_mirror WHERE external_invoice_ref=?",
                                  (ref,)).fetchone()
            if not mirror:
                raise NotFoundError("invoice %s was never ingested" % ref)
            if mirror["status"] == "voided":
                raise ConflictError("invoice %s already voided" % ref)
            paid = conn.execute(
                "SELECT COUNT(*) AS n FROM payment_intents WHERE invoice_ref=? "
                "AND state IN ('confirmed','settling','settled','disputed')", (ref,)).fetchone()
            if paid["n"]:
                raise StateError("cannot void invoice %s with confirmed payments; "
                                 "use dispute/refund flows instead" % ref)
            orig = conn.execute(
                "SELECT id FROM journal_entries WHERE external_ref=?",
                ("apex-invoice:%s" % ref,)).fetchone()
            entry_id = self._post_journal_tx(conn, [
                {"account": ACCT_REVENUE, "side": "debit",
                 "amount_cents": mirror["amount_cents"]},
                {"account": ACCT_AR, "side": "credit",
                 "amount_cents": mirror["amount_cents"]},
            ], "VOID reversal of invoice %s" % ref, mirror["currency"],
                external_ref="apex-invoice-void:%s" % ref,
                reversal_of=orig["id"] if orig else None)
            conn.execute("UPDATE invoices_mirror SET status='voided', updated_at=? "
                         "WHERE external_invoice_ref=?", (_iso(_now()), ref))
            result = {"invoice_ref": ref, "entry_id": entry_id,
                      "reversal_of": orig["id"] if orig else None, "status": "voided"}
            self._idempotent_store(conn, idempotency_key, payload, result)
            self._audit(conn, "invoice.voided", result)
            self._outbox(conn, "invoice.voided", result)
            return result

    # ------------------------------------------- confirmed payment + settle
    def record_confirmed_payment(self, apex_payment, invoice_ref, idempotency_key,
                                 intent_id=None):
        """Only an Apex payment with status EXACTLY 'confirmed' posts (the
        Apex confirmation itself is Brandon's tap upstream). Dr Clearing / Cr AR."""
        if not isinstance(apex_payment, dict):
            raise ValidationError("apex_payment must be a dict")
        if apex_payment.get("status") != "confirmed":
            raise PayError("refusing to post payment with status %r: only "
                           "'confirmed' payments enter the ledger (fail closed)"
                           % (apex_payment.get("status"),), status=409)
        amount = _check_money(apex_payment.get("amount_cents"), "payment.amount_cents")
        rail = apex_payment.get("rail")
        if not str(rail or "").strip():
            raise ValidationError("payment.rail is required")
        currency = _check_currency(apex_payment.get("currency", "USD"))
        external_ref = apex_payment.get("reference") or (
            "apex-payment:%s" % apex_payment.get("id") if apex_payment.get("id") else None)
        payload = {"op": "confirmed_payment", "invoice_ref": str(invoice_ref),
                   "amount_cents": amount, "rail": rail, "currency": currency,
                   "external_ref": external_ref, "intent_id": intent_id}
        with self._tx() as conn:
            stored = self._idempotent_check(conn, idempotency_key, payload)
            if stored is not None:
                return stored
            mirror = conn.execute("SELECT * FROM invoices_mirror WHERE external_invoice_ref=?",
                                  (str(invoice_ref),)).fetchone()
            if not mirror or mirror["status"] != "issued":
                raise StateError("invoice %s is not in issued state in the ledger"
                                 % invoice_ref)
            if intent_id:
                intent = self._get_intent(conn, intent_id)
                if intent["amount_cents"] != amount or intent["invoice_ref"] != str(invoice_ref):
                    raise ConflictError("payment does not match intent %s" % intent_id)
            else:
                intent_id = _new_id("pi")
                conn.execute(
                    "INSERT INTO payment_intents (id,invoice_ref,amount_cents,currency,rail,"
                    "state,external_ref,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,'created',?,?,?)",
                    (intent_id, str(invoice_ref), amount, currency, rail, external_ref,
                     _iso(_now()), _iso(_now())))
                intent = self._get_intent(conn, intent_id)
            clearing = ACCT_CLEARING_PREFIX + str(rail)
            self._ensure_account(conn, clearing)
            entry_id = self._post_journal_tx(conn, [
                {"account": clearing, "side": "debit", "amount_cents": amount},
                {"account": ACCT_AR, "side": "credit", "amount_cents": amount},
            ], "Confirmed payment on invoice %s via %s" % (invoice_ref, rail),
                currency, external_ref=external_ref)
            if intent["state"] != "confirmed":
                self._transition(conn, intent, "confirmed")
            conn.execute("UPDATE payment_intents SET external_ref=COALESCE(external_ref,?) "
                         "WHERE id=?", (external_ref, intent_id))
            result = {"intent_id": intent_id, "entry_id": entry_id, "state": "confirmed",
                      "invoice_ref": str(invoice_ref), "amount_cents": amount,
                      "currency": currency, "rail": rail, "clearing_account": clearing}
            self._idempotent_store(conn, idempotency_key, payload, result)
            self._audit(conn, "payment.confirmed", result)
            self._outbox(conn, "payment.confirmed", result)
            return result

    def record_settlement(self, intent_id, idempotency_key, fee_cents=0, external_ref=None):
        """Settlement: Dr Bank cash (net) + Dr Fees (if any) / Cr Clearing (gross)."""
        if isinstance(fee_cents, bool) or not isinstance(fee_cents, int) or fee_cents < 0:
            raise ValidationError("fee_cents must be a non-negative integer")
        payload = {"op": "settlement", "intent_id": intent_id, "fee_cents": fee_cents,
                   "external_ref": external_ref}
        with self._tx() as conn:
            stored = self._idempotent_check(conn, idempotency_key, payload)
            if stored is not None:
                return stored
            intent = self._get_intent(conn, intent_id)
            if intent["state"] != "confirmed":
                raise StateError("only a confirmed intent can settle (state=%s)"
                                 % intent["state"])
            amount = intent["amount_cents"]
            if fee_cents > amount:
                raise ValidationError("fee_cents exceeds settlement amount")
            clearing = ACCT_CLEARING_PREFIX + intent["rail"]
            lines = []
            if amount - fee_cents:
                lines.append({"account": ACCT_BANK, "side": "debit",
                              "amount_cents": amount - fee_cents})
            if fee_cents:
                lines.append({"account": ACCT_FEES, "side": "debit",
                              "amount_cents": fee_cents})
            lines.append({"account": clearing, "side": "credit", "amount_cents": amount})
            # The settlement is a distinct external transaction from the
            # payment itself: default to its own external reference so the
            # one-ref-per-entry map (I-11) is never violated by reuse.
            entry_id = self._post_journal_tx(
                conn, lines, "Settlement of intent %s" % intent_id, intent["currency"],
                external_ref=external_ref or "settlement:%s" % intent_id)
            self._transition(conn, intent, "settled")
            result = {"intent_id": intent_id, "entry_id": entry_id, "state": "settled",
                      "gross_cents": amount, "fee_cents": fee_cents,
                      "net_cents": amount - fee_cents, "currency": intent["currency"]}
            self._idempotent_store(conn, idempotency_key, payload, result)
            self._audit(conn, "payment.settled", result)
            self._outbox(conn, "payment.settled", result)
            return result

    # ------------------------------------------------------- disputes
    def open_dispute(self, intent_id, amount_cents, idempotency_key, reason=None):
        """Dispute notice freezes the contested amount at once (I-16):
        Dr Disputes-frozen / Cr Bank cash (settled) or Cr Clearing (unsettled)."""
        _check_money(amount_cents)
        payload = {"op": "dispute_open", "intent_id": intent_id,
                   "amount_cents": amount_cents, "reason": reason}
        with self._tx() as conn:
            stored = self._idempotent_check(conn, idempotency_key, payload)
            if stored is not None:
                return stored
            intent = self._get_intent(conn, intent_id)
            if intent["state"] not in ("confirmed", "settled"):
                raise StateError("disputes open only on confirmed/settled intents")
            if amount_cents > intent["amount_cents"]:
                raise CapExceededError("contested amount exceeds captured amount")
            source = ACCT_BANK if intent["state"] == "settled" else (
                ACCT_CLEARING_PREFIX + intent["rail"])
            entry_id = self._post_journal_tx(conn, [
                {"account": ACCT_DISPUTES_FROZEN, "side": "debit",
                 "amount_cents": amount_cents},
                {"account": source, "side": "credit", "amount_cents": amount_cents},
            ], "Dispute freeze for intent %s" % intent_id, intent["currency"],
                external_ref="dispute:%s" % intent_id)
            case_id = _new_id("dsp")
            conn.execute(
                "INSERT INTO disputes (id,intent_id,invoice_ref,amount_cents,currency,"
                "status,reason,created_at,updated_at) VALUES (?,?,?,?,?,'open',?,?,?)",
                (case_id, intent_id, intent["invoice_ref"], amount_cents,
                 intent["currency"], reason, _iso(_now()), _iso(_now())))
            self._transition(conn, intent, "disputed")
            result = {"dispute_id": case_id, "intent_id": intent_id,
                      "entry_id": entry_id, "frozen_cents": amount_cents,
                      "state": "disputed"}
            self._idempotent_store(conn, idempotency_key, payload, result)
            self._audit(conn, "dispute.opened", result)
            self._outbox(conn, "dispute.opened", result)
            return result

    def resolve_dispute(self, dispute_id, outcome):
        """outcome 'won' unfreezes; 'lost' books the loss from the frozen pot."""
        if outcome not in ("won", "lost"):
            raise ValidationError("dispute outcome must be 'won' or 'lost'")
        with self._tx() as conn:
            case = conn.execute("SELECT * FROM disputes WHERE id=?", (dispute_id,)).fetchone()
            if not case:
                raise NotFoundError("dispute %s not found" % dispute_id)
            if case["status"] != "open":
                raise StateError("dispute %s is already %s" % (dispute_id, case["status"]))
            intent = self._get_intent(conn, case["intent_id"])
            if outcome == "won":
                # Return the frozen funds to whichever account the freeze
                # drew from (bank cash if settled, clearing if not) — read
                # it back from the freeze entry's credit line.
                freeze = conn.execute(
                    "SELECT jl.account_code FROM journal_lines jl "
                    "JOIN journal_entries je ON je.id = jl.entry_id "
                    "WHERE je.external_ref=? AND jl.side='credit'",
                    ("dispute:%s" % case["intent_id"],)).fetchone()
                home = freeze["account_code"] if freeze else ACCT_BANK
                lines = [{"account": home, "side": "debit",
                          "amount_cents": case["amount_cents"]},
                         {"account": ACCT_DISPUTES_FROZEN, "side": "credit",
                          "amount_cents": case["amount_cents"]}]
                new_state = "settled"
            else:
                lines = [{"account": ACCT_DISPUTE_LOSSES, "side": "debit",
                          "amount_cents": case["amount_cents"]},
                         {"account": ACCT_DISPUTES_FROZEN, "side": "credit",
                          "amount_cents": case["amount_cents"]}]
                new_state = "settled"
            entry_id = self._post_journal_tx(
                conn, lines, "Dispute %s %s" % (dispute_id, outcome), case["currency"],
                external_ref="dispute-resolution:%s" % dispute_id)
            conn.execute("UPDATE disputes SET status=?, updated_at=? WHERE id=?",
                         (outcome, _iso(_now()), dispute_id))
            self._transition(conn, intent, new_state)
            result = {"dispute_id": dispute_id, "outcome": outcome, "entry_id": entry_id}
            self._audit(conn, "dispute.resolved", result)
            self._outbox(conn, "dispute.resolved", result)
            return result

    # ---------------------------------------------- C8 tap gate + refunds
    def create_tap_request(self, kind, payload, initiator, expires_in_seconds=3600,
                           destination=None):
        """C8: creating a movement/refund/payout ONLY creates an immutable
        Brandon tap request bound to the payload hash. Nothing executes."""
        if kind not in ("refund", "payout", "movement"):
            raise ValidationError("tap request kind must be refund|payout|movement")
        if not initiator or not str(initiator).strip():
            raise ValidationError("initiator is required (four-eyes needs a named initiator)")
        if not isinstance(payload, dict) or not payload:
            raise ValidationError("tap request payload must be a non-empty dict")
        now = _now()
        req_id = _new_id("tap")
        record = {"id": req_id, "kind": kind, "payload": payload,
                  "payload_hash": _hash(payload), "destination": destination,
                  "amount_cents": payload.get("amount_cents"),
                  "currency": payload.get("currency"), "initiator": str(initiator),
                  "status": "pending", "created_at": _iso(now),
                  "expires_at": _iso(now + timedelta(seconds=int(expires_in_seconds)))}
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO tap_requests (id,kind,payload_json,payload_hash,destination,"
                "amount_cents,currency,initiator,status,created_at,expires_at) "
                "VALUES (?,?,?,?,?,?,?,?, 'pending', ?, ?)",
                (req_id, kind, _canonical(payload), record["payload_hash"], destination,
                 record["amount_cents"], record["currency"], str(initiator),
                 record["created_at"], record["expires_at"]))
            self._audit(conn, "tap.requested", record)
            self._outbox(conn, "tap.requested", record)
        return record

    def get_tap_request(self, request_id):
        row = self._conn.execute("SELECT * FROM tap_requests WHERE id=?",
                                 (request_id,)).fetchone()
        if not row:
            raise NotFoundError("tap request %s not found" % request_id)
        d = dict(row)
        d["payload"] = json.loads(d.pop("payload_json"))
        return d

    def approve_tap_request(self, request_id, actor, now=None):
        """Approval requires actor exactly 'brandon', initiator != approver,
        and an unexpired pending request (I-19/I-20). Approval alone still
        executes nothing — see prepare_instruction()."""
        now = now or _now()
        with self._tx() as conn:
            row = conn.execute("SELECT * FROM tap_requests WHERE id=?",
                               (request_id,)).fetchone()
            if not row:
                raise NotFoundError("tap request %s not found" % request_id)
            req = dict(row)
            if actor != "brandon":
                raise GateError("only actor 'brandon' may approve a money movement")
            if req["initiator"] == actor:
                raise GateError("four-eyes: initiator may not approve their own request")
            if req["status"] != "pending":
                raise GateError("tap request is %s, not pending" % req["status"])
            if req.get("cooldown_until") and _parse_iso(req["cooldown_until"]) > now:
                raise GateError("tap request is in its destination-change cooldown "
                                "until %s; approval must wait" % req["cooldown_until"])
            if _parse_iso(req["expires_at"]) <= now:
                conn.execute("UPDATE tap_requests SET status='expired' WHERE id=?",
                             (request_id,))
                raise GateError("tap request has expired; a fresh request is required")
            conn.execute("UPDATE tap_requests SET status='approved', approver=?, "
                         "approved_at=? WHERE id=?",
                         (actor, _iso(now), request_id))
            result = {"request_id": request_id, "status": "approved", "approver": actor}
            self._audit(conn, "tap.approved", result)
            self._outbox(conn, "tap.approved", result)
            return result

    def reject_tap_request(self, request_id, actor):
        if actor != "brandon":
            raise GateError("only actor 'brandon' may reject a money movement")
        with self._tx() as conn:
            row = conn.execute("SELECT * FROM tap_requests WHERE id=?",
                               (request_id,)).fetchone()
            if not row:
                raise NotFoundError("tap request %s not found" % request_id)
            if row["status"] != "pending":
                raise GateError("tap request is %s, not pending" % row["status"])
            conn.execute("UPDATE tap_requests SET status='rejected', approver=? WHERE id=?",
                         (actor, request_id))
            self._audit(conn, "tap.rejected", {"request_id": request_id})
            return {"request_id": request_id, "status": "rejected"}

    def prepare_instruction(self, request_id, now=None):
        """An approved request yields a PREPARED INSTRUCTION ONLY.

        There is intentionally no send/execute adapter anywhere in this
        package: a human (Brandon) performs the movement on the real rail
        and the result is recorded back with its external reference.
        """
        now = now or _now()
        req = self.get_tap_request(request_id)
        if req["status"] != "approved":
            raise GateError("instruction can be prepared only from an approved "
                            "request (status=%s)" % req["status"])
        if _parse_iso(req["expires_at"]) <= now:
            raise GateError("approval has expired; a fresh request is required")
        if _hash(req["payload"]) != req["payload_hash"]:
            raise GateError("payload hash mismatch — approval no longer binds")
        return {"status": "prepared_only", "executed": False, "adapter": None,
                "request_id": request_id, "kind": req["kind"],
                "instruction": req["payload"], "payload_hash": req["payload_hash"],
                "destination": req["destination"],
                "note": "Prepared only. No adapter exists to send this; Brandon "
                        "executes on the rail and the outcome is recorded back."}

    def change_tap_destination(self, request_id, new_destination, initiator,
                               cooldown_seconds=3600, expires_in_seconds=3600):
        """Destination change invalidates the prior approval (I-20) and
        creates a fresh request carrying a cooldown timestamp."""
        old = self.get_tap_request(request_id)
        payload = dict(old["payload"])
        payload["destination"] = new_destination
        with self._tx() as conn:
            conn.execute("UPDATE tap_requests SET status='invalidated' WHERE id=?",
                         (request_id,))
            self._audit(conn, "tap.invalidated_by_destination_change",
                        {"request_id": request_id, "new_destination": new_destination})
        new_req = self.create_tap_request(old["kind"], payload, initiator,
                                          expires_in_seconds=expires_in_seconds,
                                          destination=new_destination)
        with self._tx() as conn:
            conn.execute("UPDATE tap_requests SET cooldown_until=? WHERE id=?",
                         (_iso(_now() + timedelta(seconds=int(cooldown_seconds))),
                          new_req["id"]))
        new_req["cooldown_until"] = _iso(_now() + timedelta(seconds=int(cooldown_seconds)))
        new_req["supersedes"] = request_id
        return new_req

    def refundable_cents(self, invoice_ref):
        """Ledger-level cap base (I-17): captured - refunds - dispute losses."""
        conn = self._conn
        captured = conn.execute(
            "SELECT COALESCE(SUM(amount_cents),0) AS s FROM payment_intents "
            "WHERE invoice_ref=? AND state IN ('confirmed','settling','settled',"
            "'disputed','partially_refunded')", (str(invoice_ref),)).fetchone()["s"]
        refunded = conn.execute(
            "SELECT COALESCE(SUM(amount_cents),0) AS s FROM refunds WHERE invoice_ref=?",
            (str(invoice_ref),)).fetchone()["s"]
        losses = conn.execute(
            "SELECT COALESCE(SUM(amount_cents),0) AS s FROM disputes "
            "WHERE invoice_ref=? AND status='lost'", (str(invoice_ref),)).fetchone()["s"]
        return int(captured) - int(refunded) - int(losses)

    def record_refund(self, tap_request_id, idempotency_key, external_ref=None):
        """Record a refund that Brandon approved (tap) and executed manually.

        Requires an approved, unconsumed refund tap request whose payload
        binds invoice/amount/destination; capped at the ledger level (I-17).
        Posts Dr Refunds / Cr Bank cash (settled) or Cr Clearing.
        """
        payload = {"op": "refund_record", "tap_request_id": tap_request_id,
                   "external_ref": external_ref}
        with self._tx() as conn:
            stored = self._idempotent_check(conn, idempotency_key, payload)
            if stored is not None:
                return stored
            req_row = conn.execute("SELECT * FROM tap_requests WHERE id=?",
                                   (tap_request_id,)).fetchone()
            if not req_row:
                raise NotFoundError("tap request %s not found" % tap_request_id)
            req = dict(req_row)
            if req["kind"] != "refund" or req["status"] != "approved":
                raise GateError("refunds post only against an approved refund tap "
                                "request (status=%s)" % req["status"])
            body = json.loads(req["payload_json"])
            if _hash(body) != req["payload_hash"]:
                raise GateError("tap payload hash mismatch")
            amount = _check_money(body.get("amount_cents"), "refund.amount_cents")
            invoice_ref = str(body.get("invoice_ref") or "")
            intent_id = body.get("intent_id")
            cap = self.refundable_cents(invoice_ref)
            if amount > cap:
                raise CapExceededError(
                    "refund %d exceeds ledger cap %d (captured - refunds - "
                    "dispute losses)" % (amount, cap))
            intent = self._get_intent(conn, intent_id) if intent_id else None
            source = ACCT_BANK if (intent and intent["state"] in
                                   ("settled", "partially_refunded", "disputed")) \
                else ACCT_CLEARING_PREFIX + (intent["rail"] if intent else "manual")
            if not intent:
                source = ACCT_BANK
            else:
                self._ensure_account(conn, source)
            currency = _check_currency(body.get("currency", "USD"))
            entry_id = self._post_journal_tx(conn, [
                {"account": ACCT_REFUNDS, "side": "debit", "amount_cents": amount},
                {"account": source, "side": "credit", "amount_cents": amount},
            ], "Refund recorded for invoice %s" % invoice_ref, currency,
                external_ref=external_ref)
            refund_id = _new_id("rfnd")
            conn.execute(
                "INSERT INTO refunds (id,intent_id,invoice_ref,amount_cents,currency,"
                "tap_request_id,external_ref,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (refund_id, intent_id, invoice_ref, amount, currency,
                 tap_request_id, external_ref, _iso(_now())))
            conn.execute("UPDATE tap_requests SET status='consumed', consumed_at=? "
                         "WHERE id=?", (_iso(_now()), tap_request_id))
            if intent:
                remaining = self.refundable_cents(invoice_ref)
                # refundable_cents reads committed tables; within this tx the
                # refund row above is visible to this connection.
                target = "refunded" if remaining == 0 else "partially_refunded"
                if intent["state"] in ("settled", "disputed", "partially_refunded"):
                    self._transition(conn, intent, target)
            result = {"refund_id": refund_id, "entry_id": entry_id,
                      "amount_cents": amount, "invoice_ref": invoice_ref,
                      "tap_request_id": tap_request_id}
            self._idempotent_store(conn, idempotency_key, payload, result)
            self._audit(conn, "refund.recorded", result)
            self._outbox(conn, "refund.recorded", result)
            return result

    # ------------------------------------------------------- webhooks (C4)
    def ingest_webhook(self, provider, event_id, payload, signature=None, secret=None):
        """Verify (when a secret is configured) + dedupe by event id.

        payload: dict, str or bytes (the raw body). signature: hex HMAC-SHA256
        of the raw body, optionally prefixed 'sha256='. Duplicates return the
        stored inbox row flagged duplicate and are never reprocessed.
        """
        if isinstance(payload, (bytes, bytearray)):
            raw = bytes(payload)
            try:
                body = json.loads(raw.decode("utf-8"))
            except Exception:
                raise ValidationError("webhook body is not valid JSON")
        elif isinstance(payload, str):
            raw = payload.encode("utf-8")
            body = json.loads(payload)
        else:
            body = payload
            raw = _canonical(body).encode("utf-8")
        effective_secret = secret if secret is not None else self.webhook_secret
        verified = 0
        if effective_secret:
            if not signature:
                raise SignatureError("webhook secret configured but no signature sent")
            given = str(signature)
            if given.startswith("sha256="):
                given = given[len("sha256="):]
            expected = hmac.new(str(effective_secret).encode("utf-8"), raw,
                                hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, given):
                raise SignatureError("webhook HMAC verification failed (fail closed)")
            verified = 1
        with self._tx() as conn:
            existing = conn.execute(
                "SELECT * FROM webhook_inbox WHERE provider=? AND event_id=?",
                (provider, str(event_id))).fetchone()
            if existing:
                return {"duplicate": True, "inbox_id": existing["id"],
                        "provider": provider, "event_id": str(event_id),
                        "verified": bool(existing["verified"])}
            cur = conn.execute(
                "INSERT INTO webhook_inbox (provider,event_id,payload_json,verified,"
                "received_at) VALUES (?,?,?,?,?)",
                (provider, str(event_id), _canonical(body), verified, _iso(_now())))
            result = {"duplicate": False, "inbox_id": cur.lastrowid,
                      "provider": provider, "event_id": str(event_id),
                      "verified": bool(verified)}
            self._audit(conn, "webhook.ingested", result)
            self._outbox(conn, "webhook.ingested", result)
            return result

    # ------------------------------------------------- reconciliation (C6)
    def reconcile(self, settlement_rows, bank_rows, owner="genesis-pay",
                  sla_hours=24, now=None):
        """Three-way match: internal intents/ledger vs settlement report vs
        bank deposits, keyed by external_ref.

        settlement_rows: [{external_ref, amount_cents (gross), fee_cents?,
                           net_cents?, status}]
        bank_rows:       [{external_ref, amount_cents (net deposit)}]
        Every break is persisted as an open exception with owner + SLA due.
        Breaks are NEVER auto-closed and NEVER fixed by editing the ledger.
        """
        now = now or _now()
        sla_due = _iso(now + timedelta(hours=int(sla_hours)))
        internal = {}
        for row in self._conn.execute(
                "SELECT * FROM payment_intents WHERE external_ref IS NOT NULL AND "
                "state IN ('confirmed','settling','settled','disputed',"
                "'partially_refunded')"):
            internal[row["external_ref"]] = dict(row)
        settlement = {}
        for r in settlement_rows or []:
            settlement[str(r["external_ref"])] = r
        bank = {}
        for r in bank_rows or []:
            bank[str(r["external_ref"])] = r

        breaks = []  # (external_ref, break_type, detail)

        def net_of(srow):
            if srow.get("net_cents") is not None:
                return int(srow["net_cents"])
            return int(srow["amount_cents"]) - int(srow.get("fee_cents") or 0)

        for ref, intent in internal.items():
            srow = settlement.get(ref)
            if srow is None:
                breaks.append((ref, "missing_in_settlement",
                               {"internal_state": intent["state"],
                                "amount_cents": intent["amount_cents"]}))
                continue
            if int(srow["amount_cents"]) != intent["amount_cents"]:
                breaks.append((ref, "amount_mismatch",
                               {"leg": "internal_vs_settlement",
                                "internal_cents": intent["amount_cents"],
                                "settlement_cents": int(srow["amount_cents"])}))
            if str(srow.get("status", "settled")).lower() not in ("settled", "paid"):
                breaks.append((ref, "status_mismatch",
                               {"settlement_status": srow.get("status"),
                                "internal_state": intent["state"]}))
            brow = bank.get(ref)
            if brow is None:
                breaks.append((ref, "missing_in_bank",
                               {"expected_net_cents": net_of(srow)}))
            elif int(brow["amount_cents"]) != net_of(srow):
                breaks.append((ref, "amount_mismatch",
                               {"leg": "settlement_vs_bank",
                                "settlement_net_cents": net_of(srow),
                                "bank_cents": int(brow["amount_cents"])}))
        for ref, srow in settlement.items():
            if ref not in internal:
                breaks.append((ref, "missing_internal",
                               {"leg": "settlement", "amount_cents": srow.get("amount_cents")}))
            if ref not in bank:
                breaks.append((ref, "missing_in_bank",
                               {"leg": "settlement_without_deposit"}))
        for ref, brow in bank.items():
            if ref not in settlement:
                breaks.append((ref, "missing_in_settlement",
                               {"leg": "bank_without_settlement",
                                "bank_cents": brow.get("amount_cents")}))

        matched_refs = [ref for ref in internal
                        if ref in settlement and ref in bank
                        and not any(b[0] == ref for b in breaks)]
        run_id = _new_id("recon")
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO reconciliation_runs (id,created_at,matched,breaks,summary_json) "
                "VALUES (?,?,?,?,?)",
                (run_id, _iso(now), len(matched_refs), len(breaks),
                 _canonical({"matched_refs": matched_refs})))
            exc_ids = []
            for ref, btype, detail in breaks:
                exc_id = _new_id("exc")
                conn.execute(
                    "INSERT INTO reconciliation_exceptions (id,run_id,external_ref,"
                    "break_type,detail_json,owner,sla_due,status,created_at) "
                    "VALUES (?,?,?,?,?,?,?,'open',?)",
                    (exc_id, run_id, ref, btype, _canonical(detail), owner,
                     sla_due, _iso(now)))
                exc_ids.append(exc_id)
            summary = {"run_id": run_id, "matched": len(matched_refs),
                       "matched_refs": matched_refs, "breaks": len(breaks),
                       "exception_ids": exc_ids, "owner": owner, "sla_due": sla_due}
            self._audit(conn, "reconciliation.completed", summary)
            self._outbox(conn, "reconciliation.completed", summary)
            return summary

    def list_exceptions(self, status=None):
        q = "SELECT * FROM reconciliation_exceptions"
        args = ()
        if status:
            q += " WHERE status=?"
            args = (status,)
        return [dict(r) for r in self._conn.execute(q + " ORDER BY created_at", args)]

    # ------------------------------------------------------------ audit (C9)
    def verify_audit_chain(self):
        prev = "GENESIS_PAY_GENESIS"
        rows = self._conn.execute("SELECT * FROM audit_log ORDER BY seq").fetchall()
        for r in rows:
            if r["prev_hash"] != prev:
                return {"valid": False, "broken_at_seq": r["seq"],
                        "reason": "prev_hash link broken"}
            body = {"prev": r["prev_hash"], "type": r["event_type"],
                    "payload": json.loads(r["payload_json"]), "at": r["created_at"]}
            if _hash(body) != r["hash"]:
                return {"valid": False, "broken_at_seq": r["seq"],
                        "reason": "hash does not recompute (payload tampered)"}
            prev = r["hash"]
        return {"valid": True, "entries": len(rows), "chain_head": prev}

    def audit_log(self):
        return [dict(r) for r in self._conn.execute(
            "SELECT seq,created_at,event_type,prev_hash,hash FROM audit_log ORDER BY seq")]

    def outbox_events(self):
        return [dict(r) for r in self._conn.execute(
            "SELECT * FROM outbox_events ORDER BY id")]

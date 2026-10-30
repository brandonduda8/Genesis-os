"""Reviewer's adversarial tests (WO-CLAUDE-VAULT-PHASE2-REVIEW-2026-10-30). Separate file; builder tests untouched.

Written against the v1 public API (Vault, rules.board), which Phase 2 extends. When the Phase 2 build lands,
re-run unchanged: anything Phase 2 breaks here is a regression; Phase-2-only checks are marked PHASE2.
"""
from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from genesis_vault import board as board_mod
from genesis_vault import rules
from genesis_vault.ledger import Vault, VaultError

TODAY = date(2026, 10, 30)


def table_digest(db: sqlite3.Connection) -> str:
    h = hashlib.sha256()
    for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        for row in db.execute(f'SELECT * FROM "{name}" ORDER BY rowid'):
            h.update(repr(tuple(row)).encode())
    return h.hexdigest()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.v = Vault(Path(self.tmp.name) / "vault.db")
        self.v.add_account("robinhood", "Robinhood", "robinhood")
        self.v.add_account("cashapp", "Cash App", "cash_app", buffer="10.00")

    def tearDown(self):
        self.v.close()
        self.tmp.cleanup()

    def deficits(self, today=TODAY):
        return [f for f in rules.deficit_guard(self.v.snapshot(), today) if f["level"] == "DEFICIT"]


class PastDueDebit(Base):
    def test_past_due_debit_still_flags_and_shows_overdue(self):
        self.v.set_balance("robinhood", "0.00", "2026-10-29")
        self.v.add_obligation("rh-old", "Robinhood debit", "5.00", due_date="2026-10-20",
                              account="robinhood", kind="scheduled_debit")
        d = self.deficits()
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0]["shortfall_cents"], 500)
        cal = rules.bill_calendar(self.v.snapshot(), TODAY)
        self.assertEqual(cal[0]["when"], "OVERDUE 10d")

    def test_far_past_due_is_not_aged_out_of_the_guard(self):
        self.v.set_balance("robinhood", "1.00", "2026-10-29")
        self.v.add_obligation("rh-ancient", "Robinhood debit", "5.00", due_date="2025-01-01",
                              account="robinhood", kind="scheduled_debit")
        self.assertEqual(self.deficits()[0]["shortfall_cents"], 400)


class ExactBalance(Base):
    def test_debit_exactly_equal_to_balance_is_not_a_deficit(self):
        self.v.set_balance("robinhood", "5.00", "2026-10-29")
        self.v.add_obligation("rh-1", "Robinhood debit", "5.00", due_date="2026-11-01",
                              account="robinhood", kind="scheduled_debit")
        self.assertEqual(self.deficits(), [])  # lands at exactly $0.00, not below

    def test_one_cent_over_is_a_deficit(self):
        self.v.set_balance("robinhood", "4.99", "2026-10-29")
        self.v.add_obligation("rh-1", "Robinhood debit", "5.00", due_date="2026-11-01",
                              account="robinhood", kind="scheduled_debit")
        self.assertEqual(self.deficits()[0]["shortfall_cents"], 1)

    def test_two_debits_that_together_exceed_balance_flag(self):
        self.v.set_balance("robinhood", "5.00", "2026-10-29")
        for i in (1, 2):
            self.v.add_obligation(f"rh-{i}", "Robinhood debit", "3.00", due_date="2026-11-01",
                                  account="robinhood", kind="scheduled_debit")
        self.assertEqual(self.deficits()[0]["shortfall_cents"], 100)


class DuplicateSweepCards(Base):
    def setUp(self):
        super().setUp()
        self.v.add_account("paypal", "PayPal", "paypal")
        self.v.set_balance("robinhood", "0.00", "2026-10-29")
        self.v.set_balance("paypal", "0.00", "2026-10-29")
        self.v.set_balance("cashapp", "30.00", "2026-10-29")  # buffer 10 -> 20 free
        self.v.add_obligation("rh-1", "Robinhood debit", "15.00", due_date="2026-11-01", account="robinhood",
                              kind="scheduled_debit")
        self.v.add_obligation("pp-1", "PayPal debit", "15.00", due_date="2026-11-02", account="paypal",
                              kind="scheduled_debit")

    def test_regenerating_cards_is_identical_and_writes_nothing(self):
        before = table_digest(self.v.db)
        b1 = rules.board(self.v.snapshot(), TODAY)
        board_mod.render_text(b1)
        board_mod.render_html(b1)
        b2 = rules.board(self.v.snapshot(), TODAY)
        self.assertEqual(b1["sweeps"], b2["sweeps"])
        self.assertEqual(table_digest(self.v.db), before)
        self.assertTrue(all(c["status"] in ("PREPARED_ONLY", "NO_SOURCE") for c in b1["sweeps"]))

    def test_one_surplus_is_never_promised_twice(self):
        cards = rules.board(self.v.snapshot(), TODAY)["sweeps"]
        from_cash = sum(c["amount_cents"] for c in cards if c["from"] == "cashapp")
        self.assertEqual(from_cash, 2000)  # 20.00 free, two 15.00 gaps: never 30.00
        self.assertEqual(sum(c["amount_cents"] for c in cards if c["status"] == "NO_SOURCE"), 1000)

    def test_same_debit_submitted_twice_with_same_key_counts_once(self):
        self.v.add_obligation("rh-1", "Robinhood debit", "15.00", due_date="2026-11-01", account="robinhood",
                              kind="scheduled_debit")
        rh = [f for f in self.deficits() if f["account"] == "robinhood"][0]
        self.assertEqual(rh["shortfall_cents"], 1500)


class MoneyTypes(Base):
    def test_text_and_float_cents_rejected_at_the_schema(self):
        rid = self.v.db.execute("SELECT id FROM accounts WHERE slug='robinhood'").fetchone()[0]
        for bad in ("5.00", 5.0, "500"):
            with self.assertRaises(sqlite3.IntegrityError, msg=repr(bad)):
                self.v.db.execute("INSERT INTO obligations (idempotency_key, account_id, payee, amount_cents, kind,"
                                  " created_at) VALUES (?,?,?,?,?,?)", (f"raw-{bad!r}", rid, "x", bad, "bill", "t"))

    def test_float_amount_refused_by_api(self):
        with self.assertRaises(VaultError):
            self.v.add_obligation("f", "x", 5.0)

    def test_every_cents_column_has_no_integer_affinity_and_a_typeof_check(self):
        """Phase 2 must keep this for every NEW cents column too."""
        for (name, sql) in self.v.db.execute("SELECT name, sql FROM sqlite_master WHERE type='table'"):
            for col in self.v.db.execute(f'PRAGMA table_info("{name}")'):
                if col[1].endswith("_cents"):
                    self.assertEqual(col[2], "", f"{name}.{col[1]} declares type {col[2]!r}")
                    self.assertIn(f"typeof({col[1]}) = 'integer'", sql, f"{name}.{col[1]} lacks typeof CHECK")


class BalanceRestatement(Base):
    def test_restating_an_earlier_value_on_the_same_day_is_not_dropped(self):
        """$100, then $50, then $100 again on the same day: the ledger must end at $100."""
        self.v.set_balance("robinhood", "100.00", "2026-10-30")
        self.v.set_balance("robinhood", "50.00", "2026-10-30")
        self.v.set_balance("robinhood", "100.00", "2026-10-30")
        self.assertEqual(self.v.balance("robinhood"), 10000)

    def test_restatement_collision_cannot_hide_a_deficit(self):
        """The unsafe direction: $50, $100, $50 must end at $50, so a $60 debit still flags."""
        self.v.set_balance("robinhood", "50.00", "2026-10-30")
        self.v.set_balance("robinhood", "100.00", "2026-10-30")
        self.v.set_balance("robinhood", "50.00", "2026-10-30")
        self.v.add_obligation("rh-60", "Robinhood debit", "60.00", due_date="2026-11-01", account="robinhood",
                              kind="scheduled_debit")
        self.assertEqual(len(self.deficits()), 1, "a stated $50 balance with a $60 debit must flag")


class AuditChain(Base):
    def test_audit_verifies_after_full_exercise(self):
        self.v.set_balance("robinhood", "0.00", "2026-10-29")
        self.v.set_balance("cashapp", "40.00", "2026-10-29")
        oid = self.v.add_obligation("rh-1", "Robinhood debit", "5.00", due_date="2026-11-01", account="robinhood",
                                    kind="scheduled_debit")
        rules.board(self.v.snapshot(), TODAY)
        self.v.record_completed_transfer("t1", "cashapp", "robinhood", "5.00", "2026-10-30")
        self.v.mark_outcome(oid, "paid", "debited")
        res = self.v.verify_audit()
        self.assertTrue(res["ok"], res)
        self.assertGreaterEqual(res["records"], 6)
        self.assertEqual(self.v.ledger_total(), 0)


if __name__ == "__main__":
    unittest.main()

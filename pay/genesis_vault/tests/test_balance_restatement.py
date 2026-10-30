"""Regression tests for the balance-restatement idempotency collision.

Found by Claude's WO-CLAUDE-VAULT-PHASE2-REVIEW adversarial suite (2026-10-30),
reproduced and fixed by Zane the same day. The v1 default idempotency key for
set_balance was (slug, as_of, target), so restating a value already asserted
earlier the same day was silently dropped and the ledger kept a stale balance:

  $100 -> $50 -> $100  left the ledger at $50  (understated)
  $50 -> $100 -> $50   left the ledger at $100 (overstated — a $60 debit
                       against a true $50 balance passed with no flag)
"""
import tempfile
import unittest
from datetime import date
from pathlib import Path

from genesis_vault import rules
from genesis_vault.ledger import Vault

TODAY = date(2026, 10, 30)
DAY = "2026-10-30"


class Restatement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.v = Vault(Path(self.tmp.name) / "vault.db")
        self.v.add_account("cash_app", "Cash App", "cash_app")

    def tearDown(self):
        self.v.close()
        self.tmp.cleanup()

    def test_restate_up_books(self):
        self.v.set_balance("cash_app", "100.00", DAY)
        self.v.set_balance("cash_app", "50.00", DAY)
        entry = self.v.set_balance("cash_app", "100.00", DAY)
        self.assertIsNotNone(entry)
        self.assertEqual(self.v.balance("cash_app"), 10000)

    def test_restate_down_books(self):
        self.v.set_balance("cash_app", "50.00", DAY)
        self.v.set_balance("cash_app", "100.00", DAY)
        entry = self.v.set_balance("cash_app", "50.00", DAY)
        self.assertIsNotNone(entry)
        self.assertEqual(self.v.balance("cash_app"), 5000)

    def test_restatement_chain(self):
        for amt in ("100.00", "50.00", "100.00", "50.00", "100.00"):
            self.v.set_balance("cash_app", amt, DAY)
        self.assertEqual(self.v.balance("cash_app"), 10000)

    def test_shortfall_not_masked(self):
        # True balance $50 after restatement; a $60 debit must flag NOT COVERED.
        self.v.set_balance("cash_app", "50.00", DAY)
        self.v.set_balance("cash_app", "100.00", DAY)
        self.v.set_balance("cash_app", "50.00", DAY)
        self.v.add_scheduled_debit("d1", "Merchant", "60.00",
                                    due_date="2026-11-02", account="cash_app")
        [row] = rules.debit_watch(self.v.snapshot(), TODAY)
        self.assertFalse(row["covered"])
        self.assertEqual(row["shortfall_cents"], 1000)

    def test_noop_restatement_still_quiet(self):
        self.v.set_balance("cash_app", "100.00", DAY)
        self.assertIsNone(self.v.set_balance("cash_app", "100.00", DAY))
        self.assertEqual(self.v.balance("cash_app"), 10000)

    def test_explicit_key_duplicate_still_dropped(self):
        self.v.set_balance("cash_app", "100.00", DAY, key="stmt-1")
        self.v.set_balance("cash_app", "50.00", DAY)
        # Same caller key resubmitted: a true duplicate, must not re-book.
        self.assertIsNone(self.v.set_balance("cash_app", "100.00", DAY, key="stmt-1"))
        self.assertEqual(self.v.balance("cash_app"), 5000)

    def test_audit_chain_still_verifies(self):
        for amt in ("100.00", "50.00", "100.00"):
            self.v.set_balance("cash_app", amt, DAY)
        result = self.v.verify_audit()
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()

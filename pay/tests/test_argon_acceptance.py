"""Argon RALPH-004 acceptance bar, folded into Genesis Pay S0 (ADAPT).

Argon's bar was "a pytest suite of 100 simulated invoice/settlement
cases including unbalanced-entry rejection, 0-cent drift, and a
synchronous=FULL durability note". pytest is not installed on this box
(and installs are Brandon-tap class), so the suite is written as
unittest TestCases — pytest collects unittest suites unchanged if it is
ever available. The 100 cases are deterministic (fixed seed).

Also covers the adopted convergence: DB-level zero-sum enforcement —
raw SQL writes that bypass the posting API must be rejected by the
`journal_lines_zero_sum` trigger when the final line lands.
"""
import os
import random
import sqlite3
import sys
import tempfile
import unittest

PAY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PAY_DIR)

from genesis_pay import GenesisPay
from genesis_pay.errors import ValidationError

RAILS = ["cash_app", "paypal", "current", "onepay", "manual"]


def simulate_case(tc, idx, rng):
    """One simulated invoice -> payment -> settlement (+ optional
    dispute/refund) case with exact cent-level expectations."""
    p = GenesisPay(":memory:")
    try:
        amount = rng.randrange(100, 500_001)
        fee = rng.randrange(0, max(1, amount // 20))
        rail = RAILS[idx % len(RAILS)]
        ref = "sim-ref-%d" % idx
        inv_no = "INV-SIM-%04d" % idx
        inv = {"invoice_number": inv_no, "total_cents": amount,
               "currency": "USD", "status": "sent"}
        p.ingest_invoice_issued(inv, "sim-i-%d" % idx)
        pay = p.record_confirmed_payment(
            {"id": idx, "status": "confirmed", "amount_cents": amount,
             "rail": rail, "reference": ref}, inv_no, "sim-p-%d" % idx)
        p.record_settlement(pay["intent_id"], "sim-s-%d" % idx, fee_cents=fee)
        expected_bank = amount - fee
        expected_fees = fee
        mode = idx % 5
        if mode == 3:  # dispute lost for a slice
            loss = rng.randrange(1, max(2, amount // 3))
            d = p.open_dispute(pay["intent_id"], loss, "sim-d-%d" % idx)
            p.resolve_dispute(d["dispute_id"], "lost")
            expected_bank -= loss
            tc.assertEqual(p.account_balance("5300_dispute_losses"), loss)
        elif mode == 4:  # tapped refund of a slice
            refund = rng.randrange(1, max(2, amount // 4))
            req = p.create_tap_request(
                "refund", {"invoice_ref": inv_no, "amount_cents": refund,
                           "currency": "USD", "destination": "client",
                           "intent_id": pay["intent_id"]},
                initiator="zane")
            p.approve_tap_request(req["id"], actor="brandon")
            p.record_refund(req["id"], "sim-r-%d" % idx)
            expected_bank -= refund
        tb = p.trial_balance()
        tc.assertEqual(tb["_total_debits_minus_credits"], 0,
                       "case %d: zero-sum drift" % idx)
        tc.assertEqual(tb["1000_bank_cash"], expected_bank,
                       "case %d: bank balance" % idx)
        tc.assertEqual(tb["5100_processor_fees"], expected_fees)
        tc.assertEqual(tb["1100_accounts_receivable"], 0)
        tc.assertEqual(tb["1200_clearing:%s" % rail], 0)
        tc.assertTrue(p.verify_audit_chain()["valid"])
    finally:
        p.close()


class TestSimulated100(unittest.TestCase):
    def test_100_simulated_invoice_settlement_cases(self):
        rng = random.Random(20261017)
        for idx in range(100):
            with self.subTest(case=idx):
                simulate_case(self, idx, rng)


class TestZeroSumEnforcement(unittest.TestCase):
    def setUp(self):
        self.p = GenesisPay(":memory:")

    def tearDown(self):
        self.p.close()

    def test_api_rejects_unbalanced(self):
        with self.assertRaises(ValidationError):
            self.p.post_journal(
                [{"account": "1100_accounts_receivable", "side": "debit",
                  "amount_cents": 100},
                 {"account": "4000_revenue", "side": "credit",
                  "amount_cents": 99}], "bad", "USD")

    def _raw_entry(self, debit_total, credit_total, line_count):
        self.p._conn.execute(
            "INSERT INTO journal_entries (id,created_at,memo,currency,"
            "external_ref_flag,debit_total_cents,credit_total_cents,line_count) "
            "VALUES ('je_raw',datetime('now'),'raw','USD','unmapped_flagged',?,?,?)",
            (debit_total, credit_total, line_count))
        return "je_raw"

    def _raw_line(self, side, amount):
        self.p._conn.execute(
            "INSERT INTO journal_lines (entry_id,account_code,side,amount_cents,"
            "currency) VALUES ('je_raw','1000_bank_cash',?,?,'USD')",
            (side, amount))

    def test_trigger_rejects_raw_unbalanced_write(self):
        # Bypass the API entirely: declared totals are equal (100/100) but
        # the actual lines sum 60/40 — the trigger must abort the final line.
        self._raw_entry(100, 100, 2)
        self._raw_line("debit", 60)
        with self.assertRaises(sqlite3.IntegrityError):
            self._raw_line("credit", 40)
        self.p._conn.rollback()

    def test_trigger_rejects_lying_declared_totals(self):
        # Lines match their declaration (100/90) but the declaration itself
        # is unbalanced — the trigger checks declared debit == declared credit.
        self._raw_entry(100, 90, 2)
        self._raw_line("debit", 100)
        with self.assertRaises(sqlite3.IntegrityError):
            self._raw_line("credit", 90)
        self.p._conn.rollback()

    def test_trigger_accepts_balanced_raw_write(self):
        self._raw_entry(100, 100, 2)
        self._raw_line("debit", 100)
        self._raw_line("credit", 100)  # must not raise
        self.p._conn.rollback()

    def test_trigger_rejects_extra_line_after_completion(self):
        self._raw_entry(100, 100, 2)
        self._raw_line("debit", 100)
        self._raw_line("credit", 100)
        with self.assertRaises(sqlite3.IntegrityError):
            self._raw_line("debit", 1)
        self.p._conn.rollback()

    def test_zero_drift_across_mixed_activity(self):
        p = self.p
        for i in range(10):
            amt = 1000 + i * 137
            inv = {"invoice_number": "INV-DRIFT-%d" % i, "total_cents": amt,
                   "currency": "USD", "status": "sent"}
            p.ingest_invoice_issued(inv, "drift-i-%d" % i)
            r = p.record_confirmed_payment(
                {"id": i, "status": "confirmed", "amount_cents": amt,
                 "rail": "cash_app", "reference": "drift-ref-%d" % i},
                inv["invoice_number"], "drift-p-%d" % i)
            p.record_settlement(r["intent_id"], "drift-s-%d" % i,
                                fee_cents=i)
        self.assertEqual(p.trial_balance()["_total_debits_minus_credits"], 0)


class TestDurability(unittest.TestCase):
    def test_synchronous_full_and_wal_on_file_db(self):
        with tempfile.TemporaryDirectory() as td:
            db = os.path.join(td, "pay.db")
            p = GenesisPay(db)
            try:
                sync = p._conn.execute("PRAGMA synchronous").fetchone()[0]
                mode = p._conn.execute("PRAGMA journal_mode").fetchone()[0]
            finally:
                p.close()
            self.assertEqual(sync, 2)  # 2 == FULL
            self.assertEqual(str(mode).lower(), "wal")


if __name__ == "__main__":
    unittest.main()

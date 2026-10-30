"""Genesis Pay S0 tests — real tests against temp/:memory: SQLite only.

Run:  cd genesis-os/pay && python3 -m unittest discover -s tests -v
Never touches the live Apex DB and never moves money (no adapter exists).
"""
import hashlib
import hmac
import json
import os
import sqlite3
import sys
import unittest

PAY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PAY_DIR)

from genesis_pay import GenesisPay
from genesis_pay.errors import (
    CapExceededError, ConflictError, GateError, PayError, SignatureError,
    StateError, ValidationError,
)

INV = {"invoice_number": "INV-TEST-0001", "total_cents": 29700,
       "currency": "USD", "status": "sent"}


def issued_pay(pay=None, amount=29700, ref="ext-pay-1"):
    pay = pay or GenesisPay(":memory:")
    pay.ingest_invoice_issued(INV, "k-issue")
    r = pay.record_confirmed_payment(
        {"id": 7, "status": "confirmed", "amount_cents": amount,
         "rail": "cash_app", "reference": ref},
        INV["invoice_number"], "k-pay-" + ref)
    return pay, r


class TestLedgerCore(unittest.TestCase):
    def setUp(self):
        self.p = GenesisPay(":memory:")

    def tearDown(self):
        self.p.close()

    def test_invoice_issue_balances(self):
        self.p.ingest_invoice_issued(INV, "k1")
        tb = self.p.trial_balance()
        self.assertEqual(tb["_total_debits_minus_credits"], 0)
        self.assertEqual(tb["1100_accounts_receivable"], 29700)
        self.assertEqual(tb["4000_revenue"], -29700)

    def test_unbalanced_entry_rejected(self):
        with self.assertRaises(ValidationError):
            self.p.post_journal(
                [{"account": "1100_accounts_receivable", "side": "debit", "amount_cents": 100},
                 {"account": "4000_revenue", "side": "credit", "amount_cents": 99}],
                "bad", "USD")

    def test_float_money_rejected(self):
        with self.assertRaises(ValidationError):
            self.p.post_journal(
                [{"account": "1100_accounts_receivable", "side": "debit", "amount_cents": 10.5},
                 {"account": "4000_revenue", "side": "credit", "amount_cents": 10.5}],
                "float", "USD")

    def test_append_only_journal(self):
        self.p.ingest_invoice_issued(INV, "k1")
        with self.assertRaises(sqlite3.IntegrityError):
            self.p._conn.execute("UPDATE journal_entries SET memo='x'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.p._conn.execute("DELETE FROM journal_lines")
        with self.assertRaises(sqlite3.IntegrityError):
            self.p._conn.execute("DELETE FROM audit_log")

    def test_idempotent_replay_returns_stored_result(self):
        a = self.p.ingest_invoice_issued(INV, "k1")
        b = self.p.ingest_invoice_issued(INV, "k1")
        self.assertEqual(a, b)
        self.assertEqual(len(self.p.journal_entries()), 1)

    def test_same_key_different_payload_conflicts(self):
        self.p.ingest_invoice_issued(INV, "k1")
        with self.assertRaises(ConflictError) as cm:
            self.p.ingest_invoice_issued({**INV, "total_cents": 100}, "k1")
        self.assertEqual(cm.exception.status, 409)

    def test_missing_key_rejected(self):
        with self.assertRaises(ValidationError):
            self.p.ingest_invoice_issued(INV, "")

    def test_void_is_reversal_not_edit(self):
        self.p.ingest_invoice_issued(INV, "k1")
        v = self.p.ingest_invoice_voided(INV, "k2")
        self.assertIsNotNone(v["reversal_of"])
        self.assertEqual(self.p.trial_balance()["1100_accounts_receivable"], 0)
        self.assertEqual(len(self.p.journal_entries()), 2)


class TestPaymentFlow(unittest.TestCase):
    def test_pending_payment_refused(self):
        p = GenesisPay(":memory:")
        p.ingest_invoice_issued(INV, "k1")
        with self.assertRaises(PayError):
            p.record_confirmed_payment(
                {"id": 1, "status": "pending", "amount_cents": 100,
                 "rail": "cash_app", "reference": "x"}, INV["invoice_number"], "k2")

    def test_full_flow_and_balances(self):
        p, r = issued_pay()
        s = p.record_settlement(r["intent_id"], "k-settle", fee_cents=300)
        self.assertEqual(s["net_cents"], 29400)
        tb = p.trial_balance()
        self.assertEqual(tb["_total_debits_minus_credits"], 0)
        self.assertEqual(tb["1000_bank_cash"], 29400)
        self.assertEqual(tb["1200_clearing:cash_app"], 0)
        self.assertEqual(tb["5100_processor_fees"], 300)
        self.assertEqual(p.get_intent(r["intent_id"])["state"], "settled")

    def test_settlement_requires_confirmed(self):
        p = GenesisPay(":memory:")
        i = p.create_payment_intent("INV-X", 500, "USD", "cash_app", "k-i")
        with self.assertRaises(StateError):
            p.record_settlement(i["intent_id"], "k-s")

    def test_backward_transition_rejected(self):
        p, r = issued_pay()
        with self.assertRaises(StateError):
            p.mark_pending(r["intent_id"])

    def test_unknown_only_resolves_via_query_event(self):
        p, r = issued_pay()
        p.mark_unknown(r["intent_id"], "rail timeout")
        with self.assertRaises(StateError):
            p.mark_pending(r["intent_id"])
        with self.assertRaises(ValidationError):
            p.resolve_unknown(r["intent_id"], {"type": "guess", "outcome": "confirmed"})
        out = p.resolve_unknown(r["intent_id"],
                                {"type": "query_result", "outcome": "confirmed"})
        self.assertEqual(out["state"], "confirmed")


class TestDisputesAndRefunds(unittest.TestCase):
    def test_dispute_freezes_and_won_unfreezes(self):
        p, r = issued_pay()
        p.record_settlement(r["intent_id"], "k-settle")
        d = p.open_dispute(r["intent_id"], 5000, "k-dsp", reason="client claim")
        self.assertEqual(p.account_balance("1300_disputes_frozen"), 5000)
        self.assertEqual(p.account_balance("1000_bank_cash"), 29700 - 5000)
        p.resolve_dispute(d["dispute_id"], "won")
        self.assertEqual(p.account_balance("1300_disputes_frozen"), 0)
        self.assertEqual(p.account_balance("1000_bank_cash"), 29700)

    def test_dispute_lost_books_loss_and_reduces_refundable(self):
        p, r = issued_pay()
        p.record_settlement(r["intent_id"], "k-settle")
        d = p.open_dispute(r["intent_id"], 7000, "k-dsp")
        p.resolve_dispute(d["dispute_id"], "lost")
        self.assertEqual(p.account_balance("5300_dispute_losses"), 7000)
        self.assertEqual(p.refundable_cents(INV["invoice_number"]), 29700 - 7000)

    def _approved_refund(self, p, amount, initiator="zane"):
        req = p.create_tap_request(
            "refund",
            {"invoice_ref": INV["invoice_number"], "amount_cents": amount,
             "currency": "USD", "destination": "client-cash-app"},
            initiator=initiator)
        p.approve_tap_request(req["id"], actor="brandon")
        return req

    def test_refund_posts_with_tap_and_cap(self):
        p, r = issued_pay()
        p.record_settlement(r["intent_id"], "k-settle")
        req = self._approved_refund(p, 10000)
        out = p.record_refund(req["id"], "k-refund", external_ref="ext-refund-1")
        self.assertEqual(out["amount_cents"], 10000)
        self.assertEqual(p.refundable_cents(INV["invoice_number"]), 19700)
        self.assertEqual(p.trial_balance()["_total_debits_minus_credits"], 0)

    def test_refund_over_cap_rejected(self):
        p, r = issued_pay()
        p.record_settlement(r["intent_id"], "k-settle")
        req = self._approved_refund(p, 29701)
        with self.assertRaises(CapExceededError):
            p.record_refund(req["id"], "k-refund")

    def test_refund_without_tap_rejected(self):
        p, r = issued_pay()
        with self.assertRaises((GateError, Exception)):
            p.record_refund("tap_does_not_exist", "k-refund")


class TestTapGate(unittest.TestCase):
    def setUp(self):
        self.p = GenesisPay(":memory:")

    def _req(self, initiator="zane"):
        return self.p.create_tap_request(
            "payout", {"amount_cents": 500, "currency": "USD",
                       "destination": "bank"}, initiator=initiator)

    def test_only_brandon_approves(self):
        req = self._req()
        with self.assertRaises(GateError):
            self.p.approve_tap_request(req["id"], actor="zane")

    def test_four_eyes_self_approval_rejected(self):
        req = self._req(initiator="brandon")
        with self.assertRaises(GateError):
            self.p.approve_tap_request(req["id"], actor="brandon")

    def test_approval_prepares_only_never_executes(self):
        req = self._req()
        self.p.approve_tap_request(req["id"], actor="brandon")
        ins = self.p.prepare_instruction(req["id"])
        self.assertEqual(ins["status"], "prepared_only")
        self.assertFalse(ins["executed"])
        self.assertIsNone(ins["adapter"])

    def test_destination_change_invalidates_and_cools_down(self):
        req = self._req()
        self.p.approve_tap_request(req["id"], actor="brandon")
        new = self.p.change_tap_destination(req["id"], "other-bank", initiator="zane")
        self.assertEqual(self.p.get_tap_request(req["id"])["status"], "invalidated")
        with self.assertRaises(GateError):
            self.p.approve_tap_request(new["id"], actor="brandon")


class TestWebhooks(unittest.TestCase):
    SECRET = "test-secret-do-not-use-live"

    def _sig(self, raw: bytes) -> str:
        return hmac.new(self.SECRET.encode(), raw, hashlib.sha256).hexdigest()

    def test_verify_and_dedupe(self):
        p = GenesisPay(":memory:", webhook_secret=self.SECRET)
        body = {"type": "payment.settled", "ref": "ext-pay-1"}
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        a = p.ingest_webhook("manual-rail", "evt-1", body, signature=self._sig(raw))
        self.assertTrue(a["verified"])
        b = p.ingest_webhook("manual-rail", "evt-1", body, signature=self._sig(raw))
        self.assertTrue(b["duplicate"])

    def test_bad_signature_fails_closed(self):
        p = GenesisPay(":memory:", webhook_secret=self.SECRET)
        with self.assertRaises(SignatureError):
            p.ingest_webhook("manual-rail", "evt-2", {"type": "x"}, signature="0" * 64)


class TestReconciliation(unittest.TestCase):
    def test_clean_three_way_match(self):
        p, r = issued_pay()
        p.record_settlement(r["intent_id"], "k-settle", fee_cents=300)
        out = p.reconcile(
            [{"external_ref": "ext-pay-1", "amount_cents": 29700,
              "fee_cents": 300, "status": "settled"}],
            [{"external_ref": "ext-pay-1", "amount_cents": 29400}])
        self.assertEqual(out["matched"], 1)
        self.assertEqual(out["breaks"], 0)

    def test_breaks_persist_as_open_exceptions(self):
        p, r = issued_pay()
        p.record_settlement(r["intent_id"], "k-settle", fee_cents=300)
        out = p.reconcile(
            [{"external_ref": "ext-pay-1", "amount_cents": 29700,
              "fee_cents": 300, "status": "settled"}],
            [{"external_ref": "ext-pay-1", "amount_cents": 29000}])  # short deposit
        self.assertEqual(out["breaks"], 1)
        exc = p.list_exceptions(status="open")
        self.assertEqual(len(exc), 1)
        self.assertEqual(exc[0]["break_type"], "amount_mismatch")
        self.assertTrue(exc[0]["owner"])
        self.assertTrue(exc[0]["sla_due"])
        # Breaks are never auto-closed: a clean re-run adds a run, the old
        # exception stays open until a human closes it off-ledger.
        p.reconcile(
            [{"external_ref": "ext-pay-1", "amount_cents": 29700,
              "fee_cents": 300, "status": "settled"}],
            [{"external_ref": "ext-pay-1", "amount_cents": 29400}])
        self.assertEqual(len(p.list_exceptions(status="open")), 1)

    def test_missing_everywhere_breaks(self):
        p, r = issued_pay()
        out = p.reconcile([], [])
        self.assertGreaterEqual(out["breaks"], 1)
        types = {e["break_type"] for e in p.list_exceptions()}
        self.assertIn("missing_in_settlement", types)


class TestAuditChain(unittest.TestCase):
    def test_chain_verifies(self):
        p, r = issued_pay()
        p.record_settlement(r["intent_id"], "k-settle")
        v = p.verify_audit_chain()
        self.assertTrue(v["valid"])
        self.assertGreaterEqual(v["entries"], 3)


if __name__ == "__main__":
    unittest.main()

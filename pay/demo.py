#!/usr/bin/env python3
"""Genesis Pay S0 demo — FAKE DATA ONLY.

Runs invoice -> ledger -> confirmed payment -> settlement -> three-way
reconciliation on a throwaway SQLite DB under demo_output/, including one
deliberate bank shortfall to prove exception creation. No live Apex data,
no money movement (this package has no send adapter by design).

Usage: python3 demo.py   (writes demo_output/demo_output.json)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from genesis_pay import GenesisPay

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_output")
DB = os.path.join(OUT, "genesis_pay_demo.db")


def main():
    os.makedirs(OUT, exist_ok=True)
    if os.path.exists(DB):
        os.unlink(DB)
    pay = GenesisPay(DB)

    # Invoice A: clean path. $297.00 Apex build, $3.00 rail fee.
    inv_a = {"invoice_number": "INV-DEMO-0001", "total_cents": 29700,
             "currency": "USD", "status": "sent"}
    issued_a = pay.ingest_invoice_issued(inv_a, "demo-issue-a")
    pay_a = pay.record_confirmed_payment(
        {"id": 101, "status": "confirmed", "amount_cents": 29700,
         "rail": "cash_app", "reference": "demo-ref-a"},
        "INV-DEMO-0001", "demo-pay-a")
    settle_a = pay.record_settlement(pay_a["intent_id"], "demo-settle-a",
                                     fee_cents=300)

    # Invoice B: $75.00 audit; bank deposit arrives $5.00 short -> break.
    inv_b = {"invoice_number": "INV-DEMO-0002", "total_cents": 7500,
             "currency": "USD", "status": "sent"}
    issued_b = pay.ingest_invoice_issued(inv_b, "demo-issue-b")
    pay_b = pay.record_confirmed_payment(
        {"id": 102, "status": "confirmed", "amount_cents": 7500,
         "rail": "cash_app", "reference": "demo-ref-b"},
        "INV-DEMO-0002", "demo-pay-b")
    settle_b = pay.record_settlement(pay_b["intent_id"], "demo-settle-b",
                                     fee_cents=0)

    recon = pay.reconcile(
        [{"external_ref": "demo-ref-a", "amount_cents": 29700,
          "fee_cents": 300, "status": "settled"},
         {"external_ref": "demo-ref-b", "amount_cents": 7500,
          "fee_cents": 0, "status": "settled"}],
        [{"external_ref": "demo-ref-a", "amount_cents": 29400},
         {"external_ref": "demo-ref-b", "amount_cents": 7000}],  # $5 short
    )
    exceptions = pay.list_exceptions(status="open")
    evidence = {
        "fake_data_only": True,
        "invoice_a": {"issued": issued_a, "payment": pay_a, "settlement": settle_a},
        "invoice_b": {"issued": issued_b, "payment": pay_b, "settlement": settle_b},
        "trial_balance": pay.trial_balance(),
        "reconciliation": recon,
        "open_exceptions": [
            {"id": e["id"], "external_ref": e["external_ref"],
             "break_type": e["break_type"], "owner": e["owner"],
             "sla_due": e["sla_due"], "detail": json.loads(e["detail_json"])}
            for e in exceptions],
        "audit_chain": pay.verify_audit_chain(),
        "journal_entry_count": len(pay.journal_entries()),
        "outbox_topics": [e["topic"] for e in pay.outbox_events()],
    }
    out_path = os.path.join(OUT, "demo_output.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2)
        f.write("\n")
    print(json.dumps(evidence, indent=2))
    print("[written: %s]" % out_path)
    pay.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

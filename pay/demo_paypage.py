#!/usr/bin/env python3
"""Genesis Pay S0 payments-layer demo — FAKE DATA ONLY.

Acceptance for Brandon's 2026-10-17 payments spec: one demo invoice
renders ONE simple pay page with all four no-API-key rails (Cash App,
PayPal, Current, OnePay), and the ledger records rail + reference when
the payment is confirmed (manual confirm, C8 — demonstrated here on the
Current instruction rail).

Writes demo_output/pay_page_demo.html + demo_output/paypage_evidence.json.
Usage: python3 demo_paypage.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from genesis_pay import GenesisPay, build_rails, load_config, render_pay_page

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_output")
DB = os.path.join(OUT, "genesis_pay_paypage_demo.db")

INV = {"invoice_number": "INV-DEMO-0001", "total_cents": 29700,
       "currency": "USD", "status": "sent"}


def main():
    os.makedirs(OUT, exist_ok=True)
    if os.path.exists(DB):
        os.unlink(DB)
    config = load_config()
    page = render_pay_page(INV, config)
    page_path = os.path.join(OUT, "pay_page_demo.html")
    with open(page_path, "w", encoding="utf-8") as f:
        f.write(page)

    rails = build_rails(INV, config)
    rail_summary = [{
        "rail": r["rail"], "kind": r["kind"], "status": r["status"],
        "url": r.get("url"), "has_qr": bool(r.get("qr_svg")),
        "config_needed": r.get("config_needed"),
    } for r in rails]

    pay = GenesisPay(DB)
    pay.ingest_invoice_issued(INV, "paypage-issue")
    confirmed = pay.record_confirmed_payment(
        {"id": 201, "status": "confirmed", "amount_cents": 29700,
         "rail": "current", "reference": "INV-DEMO-0001"},
        INV["invoice_number"], "paypage-confirm")
    intent = pay.get_intent(confirmed["intent_id"])
    evidence = {
        "fake_data_only": True,
        "invoice": INV,
        "pay_page": page_path,
        "rails": rail_summary,
        "paypal_brandon_step": config["paypal"]["brandon_step"],
        "cash_app_amount_prefill_static_link": "UNVERIFIED (not shipped) — "
            "see rails_config.json",
        "ledger_confirm": {
            "intent_id": intent["id"], "rail": intent["rail"],
            "external_ref": intent["external_ref"],
            "state": intent["state"],
            "clearing_account_balance":
                pay.account_balance("1200_clearing:current"),
        },
        "trial_balance": pay.trial_balance(),
        "audit_chain": pay.verify_audit_chain(),
    }
    out_path = os.path.join(OUT, "paypage_evidence.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2)
        f.write("\n")
    print(json.dumps(evidence, indent=2))
    print("[written: %s]" % page_path)
    print("[written: %s]" % out_path)
    pay.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

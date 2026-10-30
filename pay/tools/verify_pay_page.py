#!/usr/bin/env python3
"""String-verify a rendered Genesis Pay page (WO-CLAUDE-VAULT-001, mission 1).

Usage: python3 verify_pay_page.py PAGE.html [--amount 292.00]
Checks the four rails named in war-room/APPROVED_BUILDS_KICKOFF_2026-10-17.md as
quoted in the work order. It reads a file the S0 renderer already produced; it
does not import or guess S0's internals. Exit 0 only if every check passes.
"""
import argparse
import html
import re
import sys
from decimal import Decimal


def checks(page: str, amount: Decimal) -> list[tuple[str, bool, str]]:
    text = html.unescape(page)
    whole = format(amount.normalize(), "f") if amount == amount.to_integral() else format(amount, "f")
    want_paypal = f"paypal.me/DawnMorrissette/{whole}"
    paypal_found = sorted(set(re.findall(r"paypal\.me/[A-Za-z0-9_.-]+(?:/[0-9.]+)?", text)))
    cash_found = sorted(set(re.findall(r"cash\.app/\$[A-Za-z0-9_-]+(?:/[0-9.]+)?", text)))
    return [
        (f"amount ${amount:,.2f} shown", f"${amount:,.2f}" in text, ""),
        (f"PayPal.Me link {want_paypal}", any(u == want_paypal for u in paypal_found), f"found {paypal_found}"),
        ("Cash App link cash.app/$zanehart369", any(u.startswith("cash.app/$zanehart369") for u in cash_found),
         f"found {cash_found}"),
        ("Current rail present", re.search(r"\bCurrent\b", text) is not None, ""),
        ("OnePay rail present", re.search(r"\bOnePay\b", text) is not None, ""),
    ]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("page")
    p.add_argument("--amount", default="292.00")
    a = p.parse_args(argv)
    results = checks(open(a.page, encoding="utf-8").read(), Decimal(a.amount))
    for name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}{'  (' + detail + ')' if detail else ''}")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())

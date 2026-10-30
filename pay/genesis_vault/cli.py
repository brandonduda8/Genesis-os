"""genesis-vault CLI. Records what Brandon enters; prints the board. Never moves money."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import board as render
from . import rules
from .ledger import Vault, VaultError

# Accounts named in WO-CLAUDE-VAULT-001. No balances: Brandon enters them.
KNOWN_ACCOUNTS = [("cash_app", "Cash App", "cash_app"), ("paypal", "PayPal", "paypal"),
                  ("current", "Current", "current"), ("onepay", "OnePay", "onepay"),
                  ("chime", "Chime", "chime"), ("robinhood", "Robinhood", "robinhood"),
                  ("bank", "Bank", "bank")]


def seed_known(v: Vault) -> list[str]:
    for slug, name, inst in KNOWN_ACCOUNTS:
        v.add_account(slug, name, inst)
    # Due date and paying account are not known to Genesis; Brandon fills them in or records an outcome.
    v.add_obligation("seed:talkiatry-final-notice", "Talkiatry", "100.00", notice="final notice")
    return [s for s, _, _ in KNOWN_ACCOUNTS]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="genesis-vault", description=__doc__)
    p.add_argument("--db", required=True, help="path to the Vault SQLite file")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("seed-known")
    a = sub.add_parser("add-account"); a.add_argument("slug"); a.add_argument("name"); a.add_argument("institution")
    a.add_argument("--buffer", default="0")
    b = sub.add_parser("set-balance"); b.add_argument("account"); b.add_argument("amount"); b.add_argument("--as-of", required=True)
    i = sub.add_parser("import-balances"); i.add_argument("csv")
    o = sub.add_parser("add-bill"); o.add_argument("key"); o.add_argument("payee"); o.add_argument("amount")
    o.add_argument("--due"); o.add_argument("--account"); o.add_argument("--notice", default="")
    o.add_argument("--kind", default="bill", choices=["bill", "scheduled_debit"])
    m = sub.add_parser("mark-outcome"); m.add_argument("id", type=int); m.add_argument("outcome"); m.add_argument("--note", default="")
    t = sub.add_parser("record-transfer", help="bookkeeping for a transfer Brandon already made in the app")
    t.add_argument("key"); t.add_argument("from_account"); t.add_argument("to_account"); t.add_argument("amount")
    t.add_argument("--on", required=True)
    d = sub.add_parser("board"); d.add_argument("--today"); d.add_argument("--html"); d.add_argument("--json", action="store_true")
    sub.add_parser("audit-verify")
    args = p.parse_args(argv)
    v = Vault(args.db)
    try:
        if args.cmd == "init":
            print(f"initialised {args.db}")
        elif args.cmd == "seed-known":
            print("seeded accounts: " + ", ".join(seed_known(v)) + "; open item: Talkiatry $100.00 final notice")
        elif args.cmd == "add-account":
            v.add_account(args.slug, args.name, args.institution, buffer=args.buffer)
        elif args.cmd == "set-balance":
            v.set_balance(args.account, args.amount, args.as_of)
        elif args.cmd == "import-balances":
            print(f"applied {v.import_balances_csv(Path(args.csv).read_text(encoding='utf-8'), source_name=Path(args.csv).name)} balance changes")
        elif args.cmd == "add-bill":
            print(v.add_obligation(args.key, args.payee, args.amount, due_date=args.due, account=args.account,
                                   kind=args.kind, notice=args.notice))
        elif args.cmd == "mark-outcome":
            v.mark_outcome(args.id, args.outcome, args.note)
        elif args.cmd == "record-transfer":
            v.record_completed_transfer(args.key, args.from_account, args.to_account, args.amount, args.on)
        elif args.cmd == "board":
            today = date.fromisoformat(args.today) if args.today else date.today()
            b = rules.board(v.snapshot(), today)
            if args.html:
                Path(args.html).write_text(render.render_html(b), encoding="utf-8")
            print(json.dumps(b, indent=2) if args.json else render.render_text(b), end="" if not args.json else "\n")
        elif args.cmd == "audit-verify":
            res = v.verify_audit()
            print(json.dumps(res))
            return 0 if res["ok"] else 1
        return 0
    except (VaultError, ValueError, OSError) as exc:
        print(f"genesis-vault: {exc}", file=sys.stderr)
        return 2
    finally:
        v.close()

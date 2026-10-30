"""genesis-vault CLI. Records what Brandon enters; prints the board. Never moves money."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import board as render
from . import parking as parking_mod
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
    sd = sub.add_parser("add-debit", help="Phase 2 watch: a dated scheduled debit (due date + target account required)")
    sd.add_argument("key"); sd.add_argument("merchant"); sd.add_argument("amount")
    sd.add_argument("--due", required=True); sd.add_argument("--account", required=True)
    sd.add_argument("--notice", default="")
    m = sub.add_parser("mark-outcome"); m.add_argument("id", type=int); m.add_argument("outcome"); m.add_argument("--note", default="")
    t = sub.add_parser("record-transfer", help="bookkeeping for a transfer Brandon already made in the app")
    t.add_argument("key"); t.add_argument("from_account"); t.add_argument("to_account"); t.add_argument("amount")
    t.add_argument("--on", required=True)
    d = sub.add_parser("board"); d.add_argument("--today"); d.add_argument("--html"); d.add_argument("--json", action="store_true")
    g = sub.add_parser("digest", help="Phase 2 daily digest: balances, debits due in 7 days, uncovered bills, sweep cards waiting")
    g.add_argument("--today"); g.add_argument("--json", action="store_true"); g.add_argument("--parking")
    pk = sub.add_parser("parking", help="Phase 2 parking/growth comparison (verified rates only)")
    pk.add_argument("--today"); pk.add_argument("--file"); pk.add_argument("--json", action="store_true")
    ps = sub.add_parser("parking-set-rate", help="record a rate ONLY from an official source, with the date checked")
    ps.add_argument("name"); ps.add_argument("apy_percent"); ps.add_argument("--source", required=True)
    ps.add_argument("--checked", required=True); ps.add_argument("--file")
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
        elif args.cmd == "add-debit":
            print(v.add_scheduled_debit(args.key, args.merchant, args.amount, due_date=args.due,
                                        account=args.account, notice=args.notice))
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
        elif args.cmd == "digest":
            today = date.fromisoformat(args.today) if args.today else date.today()
            snap = v.snapshot()
            d = rules.daily_digest(snap, today)
            pfile = args.parking or str(Path(args.db).parent / "parking.json")
            d["parking"] = parking_mod.parking_comparison(snap, parking_mod.load_options(pfile), today)
            print(json.dumps(d, indent=2) if args.json else render.render_digest(d),
                  end="" if not args.json else "\n")
        elif args.cmd == "parking":
            today = date.fromisoformat(args.today) if args.today else date.today()
            pfile = args.file or str(Path(args.db).parent / "parking.json")
            comp = parking_mod.parking_comparison(v.snapshot(), parking_mod.load_options(pfile), today)
            if args.json:
                print(json.dumps(comp, indent=2))
            else:
                for r in comp["rows"]:
                    rate = (f"{r['apy_percent']}% APY ({r['rate_status']}, checked {r['rate_checked']}, "
                            f"source {r['rate_source']})") if r["apy_percent"] else "rate not verified"
                    print(f"  {r['name']:<22} {'held' if r['held'] else 'not held'}  {rate}"
                          + (f"  -> {r['math']}" if r["math"] else ""))
                print(f"  best verified: {comp['best_verified'] or 'none on file'}")
        elif args.cmd == "parking-set-rate":
            today = date.today()
            pfile = args.file or str(Path(args.db).parent / "parking.json")
            opts = parking_mod.record_verified_rate(parking_mod.load_options(pfile), args.name,
                                                    args.apy_percent, args.source, args.checked, today)
            parking_mod.save_options(pfile, opts)
            print(f"recorded verified rate for {args.name} in {pfile}")
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

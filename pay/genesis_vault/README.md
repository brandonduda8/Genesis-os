# Genesis Vault v1

Personal-treasury records and a daily one-screen board, built to sit beside Genesis Pay. Python 3.10+, standard library only, $0, local.

**Genesis never moves money.** The Vault records what Brandon enters or imports from his own statements, then tells him what needs attention. Every transfer is Brandon's tap in the provider's app (invariant C8). There is no network or subprocess code in this package; a test enforces it. There is no server, so there is nothing to bind.

## Ledger discipline (same bar as Genesis Pay S0)

- Integer cents only. The cents columns have no SQLite type affinity, so the text `'5.00'` cannot silently become 5 cents. `parse_cents` refuses floats and anything below a cent.
- Double entry: an entry becomes posted only if it has 2+ postings that sum to zero (trigger). Postings are append-only, posted entries are immutable, and every write carries an idempotency key.
- A stated balance is booked against a `reconciliation` equity account, so the ledger total stays exactly 0.
- Hash-chained, append-only audit log (`verify_audit`, or the `audit-verify` command).
- `PRAGMA journal_mode=WAL`, `synchronous=FULL`, `foreign_keys=ON`.

## The board

- **Deficit guard**: flags an account whose open outflows due within 14 days (or undated) exceed its balance. This is the Robinhood $5 bounce class. Accounts with no entered balance show `UNKNOWN_BALANCE`, and bills with no paying account show `UNASSIGNED`. Neither is silently treated as fine.
- **Bill calendar**: final notices first, then overdue, undated, and upcoming. An item stays open until Brandon records one outcome: `paid`, `arranged`, `disputed` or `cancelled`.
- **Sweep cards**: `PREPARED_ONLY` cards reading "Move $X from A to B", drawn from accounts with known surplus after their own bills and buffer. `NO_SOURCE` appears when nothing covers the gap. Cards are computed, never stored or executed.

## Use (from `pay/`)

```bash
DB=~/genesis-vault.db
python3 -m genesis_vault --db $DB seed-known            # 7 accounts (no balances) + Talkiatry $100 final notice
python3 -m genesis_vault --db $DB set-balance cash_app 43.12 --as-of 2026-10-30
python3 -m genesis_vault --db $DB import-balances balances.csv   # header: account,balance,as_of
python3 -m genesis_vault --db $DB add-bill rh-1 "Robinhood debit" 5.00 --due 2026-11-01 --account robinhood --kind scheduled_debit
python3 -m genesis_vault --db $DB mark-outcome 1 arranged --note "payment plan"
python3 -m genesis_vault --db $DB record-transfer t-1 cash_app robinhood 5.00 --on 2026-10-30   # after Brandon did it in the app
python3 -m genesis_vault --db $DB board --html board.html
python3 -m genesis_vault --db $DB audit-verify
python3 -m unittest discover -s genesis_vault/tests -t .
```

Talkiatry's due date and paying account were not in the work order, so the seed leaves them blank. Set them by adding a dated bill, or record an outcome.

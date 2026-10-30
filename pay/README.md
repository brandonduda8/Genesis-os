# Genesis Pay S0 — owned ledger layer (v0.2.0)

Design of record: `genesis-os/war-room/GENESIS_POWER_PLAN_RE_2026-10-17.md` §5
(Claude components C1–C11 + invariants I-1…I-22). Commissioned by Brandon
2026-10-17 (Power Plan §9.3, “tap all”). Stdlib-only Python. $0, internal.

## What this is

S0 of the Genesis Pay sovereignty roadmap: **our own double-entry ledger +
payment-intent service + three-way reconciliation**, sitting *behind* Apex
Invoicing (which stays the system of record for what is owed) and *in front
of* a future orchestrator adapter (Hyperswitch at S2 — **not installed**;
Brandon's sandbox-or-defer choice is still open). Genesis Pay records truth
and prepares movements; **it never moves money** — there is deliberately no
send/execute adapter anywhere in the package.

## Layout

- `genesis_pay/core.py` — `GenesisPay` (ledger, intents, disputes, refunds,
  C8 tap gate, webhook ingestor, reconciliation, audit chain)
- `genesis_pay/errors.py` — fail-closed error types with HTTP-equivalent statuses
- `tests/test_genesis_pay.py` — 28 unit tests (all passing 2026-10-17)
- `demo.py` → `demo_output/demo_output.json` — fake-data end-to-end evidence
- Storage: a **dedicated SQLite file** per instance (never the live Apex DB)

## Money flow (state machine + journal)

1. Apex invoice issued → `ingest_invoice_issued` posts **Dr AR / Cr Revenue**
   and mirrors the invoice.
2. Apex payment **confirmed** (the Apex confirmation is Brandon's tap
   upstream; pending payments are refused) → **Dr Clearing:\<rail\> / Cr AR**,
   intent → `confirmed`.
3. Settlement → **Dr Bank cash (net) + Dr Fees / Cr Clearing (gross)**,
   intent → `settled`. The settlement carries its own external reference
   (`settlement:<intent>`) so one external ref maps to exactly one entry.
4. Void = a **new reversing entry** (Dr Revenue / Cr AR), never an edit.
5. Dispute opens → contested amount frozen at once (Dr Disputes-frozen /
   Cr Bank-or-Clearing). Won → funds return to the account the freeze drew
   from; lost → Dr Dispute losses / Cr Disputes-frozen.
6. Refund → only against an **approved Brandon tap request**, capped at the
   ledger level: captured − refunds − dispute losses.

## The C8 tap gate (outbound money movement = Brandon's tap)

`create_tap_request` only *creates* an immutable request bound to its
payload hash. `approve_tap_request` requires actor exactly `brandon`,
initiator ≠ approver (four-eyes), unexpired, and outside any
destination-change cooldown. `prepare_instruction` returns
`{status: "prepared_only", executed: false, adapter: null}` — a human
executes on the real rail and the outcome is recorded back with its
external reference. Destination changes invalidate the prior approval and
start a fresh request with a cooldown.

## Invariant mapping (Claude I-1…I-22, as summarized in Power Plan §5)

- **Idempotency (I-1…I-5):** client key required on every money call;
  key + payload hash + result stored in the same transaction as the
  journal/intent/outbox writes; exact replay returns the stored result;
  same key + different payload = `ConflictError` (409); internal retries
  reuse deterministic keys (settlement refs derive from the intent id).
- **Ledger integrity (I-6…I-11):** append-only journal/audit enforced by
  SQLite triggers; balanced double-entry only; integer minor units, no
  floats; explicit 3-letter currency per entry; every entry carries an
  external ref or is flagged `unmapped_flagged`; one external ref maps to
  exactly one entry.
- **Reconciliation (I-12…I-13):** three-way match (intents/ledger vs
  settlement report vs bank deposits) keyed by external ref; every break
  persists as an **open exception with owner + SLA**; breaks are never
  auto-closed and never fixed by editing the ledger.
- **State & safety (I-14…I-15, I-21…I-22):** strict forward-only intent
  state machine; webhooks are untrusted until HMAC-verified and are
  deduped by (provider, event_id); the system **fails closed**;
  UNKNOWN outcomes resolve only via an explicit `query_result` event.
- **Disputes & refunds (I-16…I-17):** disputes freeze the contested amount
  at notice; refunds are capped at captured − refunds − losses **in the
  ledger**, not by caller honesty.
- **Approvals (I-18…I-20):** server-side gate in `GenesisPay` (not a UI
  promise); four-eyes by construction; approvals bind to immutable
  payload hashes; destination changes cool off + re-approve.
- **Audit (C9):** hash-chained audit log (`verify_audit_chain()`), plus a
  transactional outbox of every domain event.

## How a future Hyperswitch adapter sits behind this

`genesis_pay` is the ledger of record; an orchestrator (Hyperswitch,
adopted unmodified per Claude's call) would slot in as a *source of
settlement/webhook events*: its connector events feed `ingest_webhook`,
its settlement reports feed `reconcile`, and outbound calls would be
prepared through the same C8 gate. The adapter boundary is the
`external_ref` + rail strings — no Genesis Pay code changes are needed to
add a rail. Card data never enters this package (SAQ-A posture preserved:
processor tokens/references only, never PANs).

## Payments layer — no-API-key rails (Brandon spec 2026-10-17 ~20:26 CDT)

`genesis_pay/paylinks.py` + `rails_config.json`: one simple pay page per
invoice (`render_pay_page`), four rails, zero API keys, zero card fields.
Design law: link rails first, instruction rails where no public merchant
link scheme is verified, and **never a guessed URL**.

| Rail | Kind | Status |
|---|---|---|
| Cash App | link `https://cash.app/$zanehart369` + QR | **VERIFIED** ($cashtag profile link; rail fleet-verified payable). The page shows the exact amount + invoice-number note beside the button. Cash App's amount+note *prefilled* payment links are generated per-request inside the app (cash.app press, Feb 2026), so no static prefill URL is constructed — a `cash.app/$tag/<amount>` pattern could not be verified from a source and is marked **UNVERIFIED / not shipped** in the config |
| PayPal | link `https://www.paypal.me/<handle>/<amount>` | Format **VERIFIED** from PayPal's own help (FAQ3918: appending `/<amount>` pre-fills it). Brandon's handle is **not on file** — the config slot ships empty on purpose; until he supplies it the rail renders as a send-to-email instruction (dawnmorrissette@gmail.com) with his one step stated in the config. The handle is never guessed |
| Current | instruction rail | No public merchant link scheme verified: in-app send to payee name/phone, invoice number as the note |
| OnePay | instruction rail | Same pattern (Walmart OnePay app), invoice number as the note |

Every rail lands in the same flow as everything else in Genesis Pay: the
payer pays on the rail, Brandon confirms (C8), and
`record_confirmed_payment` records **rail + reference** on the intent —
suggest-only matching against the invoice-number note, then the normal
settlement + three-way reconciliation path. Demo:
`demo_paypage.py` → `demo_output/pay_page_demo.html` +
`demo_output/paypage_evidence.json` (confirm demonstrated on the Current
instruction rail). Note for future Apex-side wiring: Apex's own
`record_payment` allowlist (`RAILS` in apex-invoicing) currently lacks
`paypal`/`current`/`onepay` — Genesis Pay accepts any rail string, but
recording these rails *through Apex* would need that list extended
(Apex is Brandon-tap territory; not changed here).

QR codes are generated by a pure-stdlib encoder in `paylinks.py` (QR
spec, byte mode, EC level M, versions 1–10) — no third-party package was
installed. The tests decode rendered matrices back to the payload and
assert zero Reed-Solomon syndromes per block, so the encoder is verified,
not hopeful.

## Zero-sum enforcement + durability (Argon RALPH-004 convergence)

Argon's WO-002 return (RALPH-004) independently specced the same core;
adopted deltas:

- **DB-level zero-sum trigger.** Entries declare `debit_total_cents`,
  `credit_total_cents`, and `line_count` at insert; the
  `journal_lines_zero_sum` trigger verifies the actual line sums against
  the declaration (and declared debit == declared credit) when the final
  line lands. Raw SQL writes that bypass the posting API are rejected by
  the database itself (proven by tests that write unbalanced rows
  directly). The posting-API balance check remains the first line of
  defense.
- **100-case simulation suite** (`tests/test_argon_acceptance.py`):
  100 deterministic invoice→payment→settlement cases across all rails
  with dispute-loss and tapped-refund slices mixed in; every case asserts
  exact bank/fees balances and **0-cent drift** (trial balance nets to
  exactly 0), plus unbalanced-entry rejection and the durability checks
  below. Written as unittest (pytest is not installed on this box;
  pytest collects unittest suites unchanged).
- **Durability:** file-backed ledgers open with `journal_mode=WAL` +
  `synchronous=FULL` — a committed posting survives power loss / VM
  recycle (this box recycles ~13×/day; the setting is asserted by test).
- **Not adopted:** Argon's `genesis_pay_router` naming and any framing
  of the SQLite ledger as a new invoicing stack. Apex Invoicing remains
  the invoicing system of record; Genesis Pay is the ledger *behind* it,
  per the Power Plan §5 design of record. Convergence is on the money
  invariants, not on replacing the stack.

## Limitations / next steps

- No HTTP surface yet (library only) — an adapter can map `PayError.status`
  1:1 when S1 needs it.
- Reconciliation input is caller-supplied rows; Plaid/processor report
  importers are S1 work (Plaid stays suggest-only upstream in Apex).
- Dispute evidence storage/deadline tracking (C7 remainder) is staged, not
  built; disputes currently freeze + resolve amounts only.
- Refund recording assumes Brandon executed on the rail and the result is
  recorded back; automating that record-back is S1/S2 work.
- Multi-currency postings are validated per entry but cross-currency
  intents are out of S0 scope.

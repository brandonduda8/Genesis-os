# RECEIPT — GHOST SERVER v2 · P3 Gates + WIP governance + scorecard (modules 4–6)

**Grade: BUILT** (cloud container). **Host re-run: OWED to Zane** (README §Zane step 8).

**Files:** `ghost/gates.py`, `ghost/signing.py`, `ghost/metrics.py`, scheduler in `ghost/server.py`

## Module 4: commit gates

**How the gate resolves an action:**
- **Identity:** the OS user.
- **Scope:** `config/policy.json`. With no file, it runs in dev mode as a single operator.
- **Level B:** additionally needs an Ed25519 receipt bound to (action, job, principal), with TTL ≤ 300 s and a
  single-use nonce.

**Tests for Level B.** It is refused in each of these cases:
- no receipt;
- a receipt for the wrong job;
- a receipt for the wrong principal;
- a forged action;
- a replayed nonce;
- an expired receipt;
- a valid receipt from a user who lacks the operate scope;
- `cryptography` missing, which **fails closed**.

**Level C is a missing capability:**
- `gates.EXECUTORS` is a read-only view with no Level C kind in it. Assigning to it raises `TypeError`.
- `register_executor()` raises for spend, publish, move_money, trade, delete_irreversible, and any name the Level C
  classifier matches.
- Unknown kinds are classified as C.
- Job text is classified too, using a superset of the master runtime's markers on title and command only, never on
  fence notes such as "$0, no spend".

**Classifier calibration:** the first version flagged "Genesis Pay", a product name, as a payment. It was narrowed to
payment *verbs*, and Q-008 and Q-009 now import correctly.

### Acceptance 3: gate refusal (verbatim CLI log, cloud container)

```
$ python3 ghostd.py gate spend GHOST-Q-002   # Level C-shaped action
{"refused": "Level C action 'spend' is structurally unavailable to GHOST; escalated to Brandon", "escalation": 1}
exit=3

$ python3 ghostd.py gate ghost_unblock GHOST-Q-008   # Level B without a signed receipt
{"refused": "Level B 'ghost_unblock' needs a valid signed receipt: signed receipt required", "escalation": null}
exit=3

$ python3 ghostd.py escalations
{"esc_id": 1, "job_id": "GHOST-Q-002", "action": "spend", "reason": "Level C action 'spend' is structurally unavailable to GHOST; escalated to Brandon", "state": "AWAITING-BRANDON"}

$ cat state/escalations/ESC-0001.json
{"action":"spend","esc_id":1,"job_id":"GHOST-Q-002","note":"GHOST cannot execute Level C actions; this is a request for Brandon's tap.","reason":"...","state":"AWAITING-BRANDON","to":"brandon"}
```

Escalation files are now created with mode 0600 (this run showed 0644 inside a 0700 directory; fixed). The test
`test_level_c_action_is_refused_logged_and_escalated` covers four Level C shapes: the `spend` and `move_money` kinds,
plus "publish the Station app" and "make a payment of $40" hidden in job text. In every case the job's state is
unchanged, nothing executes, and there are 4 `gate_refused` ledger rows and 4 escalation files.

## Module 5: WIP governance (Little's Law)

- The scheduler enforces a per-lane cap (default 3) and a global cap (3, matching `master-runtime/lanes.json`).
- Lanes are ordered builds > proofs > installs > …, matching the queue README's F1 > owed proofs > installs.
- `metrics.flow()` computes L from attempt intervals (time-weighted), λ from completions, and **W = L/λ**, next to the
  measured mean cycle and queue time.
- Test with 4 jobs, each running 2 h in a 24 h window: L = 0.333, λ = 0.1667/h, **W = 2.00 h**, and the measured
  cycle is also 2.00 h.

## Module 6: STEM scorecard (live output, cloud container, after migration)

```
GHOST SERVER v2 — STEM scorecard @ 2026-10-31 18:40:18Z
ledger: INTACT (16 records) · escalations awaiting Brandon: 1
JOBS (12)  BLOCKED-(human:brandon-home-decision) 1 · BLOCKED-(human:brandon-relay) 1 · BLOCKED-(human:relay-packs-landed) 1 · QUEUED 9
FLOW (window 168.0 h) — Little's Law W = L / λ
  mean WIP L 0.0 · throughput λ / h 0.0 · W = L/λ (h) undefined — 0 completions in window
POWER  attempt CPU s 0 over 0 attempts · server RSS 32212 kB · server CPU 0.11 s
MONEY (staged)  rule_of_40 PARKED — no revenue exists · ltv_cac NOT COMPUTED — no LTV/CAC data · burn_multiple NOT COMPUTED — no burn/ARR data
OKRs  2026-Q4 · … · Legacy jobs verified (receipt verifier passed): 0 / 3
Grades follow Brandon's ladder: … This board certifies nothing — Brandon certifies.
```

- Every number is computed from the database. Where no data exists, the board says why instead of showing a placeholder.
- `board --html F` writes a static page.
- A test asserts that the board contains no bare `DONE`. DONE-VERIFIED reads "VERIFIED — awaiting Brandon".

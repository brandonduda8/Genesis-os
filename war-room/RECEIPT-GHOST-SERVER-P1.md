# RECEIPT — GHOST SERVER v2 · P1 Job core + lineage (modules 1, 2 and the module 9 core)

**Grade: BUILT** (cloud container). **Zane verification on zane-box: OWED.**

**Branch:** `claude/ghost-server-v2` · **Files:** `ghost-server/ghost/registry.py`, `ghost/legacy.py`, `ghost/server.py`
(recovery and daemon), `ghostd.py` · **Hashes:** `ghost-server/SHA256SUMS`

## What is built

- **Registry law in code:**
  - IDs must match `GHOST-Q-NNN` and are never reused.
  - Every write addresses one ID **plus** its expected state and version, and is **read back in the same transaction**;
    a mismatch rolls back and raises.
  - `find()` only reads and never writes, which a test proves with `total_changes`.
  - Patch fields are allowlisted.
- **States:** `QUEUED`, `RUNNING`, `BLOCKED-(reason)`, `DONE-VERIFIED`, `DEAD-LETTER`, with an explicit transition
  table.
- **Retries** are bounded (default 3) with deterministic backoff of 60·2^(n−1) s, capped at 1 h. When attempts run out
  the job goes to DEAD-LETTER, which is shown to Brandon on the board.
- **Lineage:** every mutation appends input and output SHA-256, actor, transform and source. `provenance <id>` returns
  the job, lineage, attempts, artifacts, envelopes, escalations and ledger rows in one call.
- **Legacy reader:** `ghost/queue/*.json` and `Q-*.md` are read only (a test hashes the directory before and after).
  The ID comes from the file, and the lineage source is `<path>@sha256:<file hash>@git:<blob>`. Requirements come
  only from the reviewed, ID-keyed `config/legacy_requires.json`; unmapped IDs import as `BLOCKED-(requires-unmapped)`.
- **Evidence ledger:** hash-chained and append-only via triggers. `ledger-verify` re-hashes the whole chain and catches
  tampering even if someone drops a trigger (tested).

## Test output (cloud container, Python 3.13.17 and 3.12.3)

```
Ran 42 tests in 17.860s
OK
```

The full verbatim per-test list is in RECEIPT-GHOST-SERVER-P5. The P1 tests are the 10 in `tests/test_core.py` and the
4 migration tests in `tests/test_legacy_gates.py`. With `cryptography` blocked: 42 run, 11 skipped, OK, and the
fail-closed test passes.

## Acceptance 1: restart survival (LAB, real processes)

`tests/test_drain_restart.py::RestartSurvival` covers this:

1. The real double-fork daemon is started.
2. A second instance is refused by the `flock` on the pidfile.
3. A CodeAct job is RUNNING when the daemon is **killed with `kill -9`**.
4. The CodeAct child dies with the server (PDEATHSIG; checked with `pgrep`).
5. On restart: **zero jobs lost, every other state unchanged**. The interrupted job is back in QUEUED with
   `attempts=1, outcome=interrupted`.
6. The ledger verifies as one chain with **2 `boot` rows** spanning the crash.
7. Keepalive returns 0 while the heartbeat is fresh, and **1** once it is more than 300 s old.

**OWED:** a real reboot of zane-box. A container cannot reboot.

## Acceptance 6: resource budget (cloud container, 4 vCPU / 16 GB; NOT zane-box)

| Measurement | Result |
|---|---|
| Idle daemon, production tick 5 s, 12 jobs, no doors, 30 s window | **RSS 24,000 kB; CPU 0.033 %** |
| Daemon with 1 CodeAct child, test tick 0.2 s, 5 s window | RSS 23,576 kB; CPU 0.60 % |
| Budget | RSS ≤ 40 MB; CPU ≤ 0.5 % idle |

**OWED:** the same measurement on zane-box (2 CPU / 8 GB). The commands are in README §Zane step 5. The ship rule
"lean or it doesn't ship" is Zane's call once those numbers exist.

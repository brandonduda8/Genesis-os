# GHOST Training Dataset v1 — MANIFEST

**Built:** 2026-10-31, under QUEUE row #10 (Brandon order 2026-10-31
~13:45 CDT). **Builder:** `build_dataset.py` in this directory
(re-runnable; every number below comes from its run output and from
re-reading the written files). **Location:**
`genesis-os/training/datasets/ghost-v1/corpus/` (training) +
`heldout/` (frozen eval core — never training data).

## Format (mirrors the Cody v1 pattern)

One JSONL record per line; every record carries `source` (exact file),
`detail` (transform + the verbatim basis for any classification), and a
sequential `id`.

| Type | Shape | What it teaches |
|------|-------|-----------------|
| `job_case` | `instruction` / `response` | (recorded job title + requires_path → recorded status + failure class). The class is grounded in the job file's **own** requires_path text; the basis is quoted in `detail`. |
| `incident` | `instruction` / `response` | (recorded receipt section → failure class + next action + recorded outcome). Section text verbatim; class from the section's own recorded cause. |
| `state_read` | `instruction` / `response` | (probe/state-file values → class + action, or UNKNOWN where the record determines nothing). |
| `doc` | `text` | Doctrine verbatim: egress-router design sections (health scoring, circuit breaker, 429 law, lanes, logging), registry README (schema, drain law), PROGRAM_STATE drain priority. |

Failure classes follow QUEUE row #10 — **EGRESS / TRANSPORT / FAULT /
STATE** — plus **UNKNOWN** (the record determines no class; honesty
feedstock) and **NONE** (recorded outcome was healthy, or the blocker
is a human relay, not a failure). Transformations are mechanical only;
no symptom, cause, or outcome was invented.

## The UNKNOWN cases (honesty feedstock — 3, by design)

| Case | Evidence (verbatim source) | Why UNKNOWN is the only honest label |
|------|---------------------------|----------------------------------------|
| Gmail read failures (GHOST-Q-014 investigation) | Two distinct error shapes (transport code-5 on search; "query connector grant" on read) while `status` reports read scope granted | Cause never isolated in the record; naming EGRESS or FAULT would be invention |
| lane_health blackout snapshot | Every lane DOWN incl. local ollama, shared detail "blackout", no per-lane cause, no resolution recorded | Consistent with more than one class; the file determines none |
| penguin keepalive down→up | Transition + timestamps recorded; no cause recorded | The state file is silent on cause |

Placement law: ≥1 UNKNOWN case on each side of the split — 2 in the
training split (Gmail, penguin), 1 frozen in held-out (lane_health).
GHOST-QUAL-001 additionally authors fresh underdetermined cases.

## Held-out law (frozen first)

Safety scan first, then the freeze by SHA-256 of each case's key
(≥20% floor). **6 of 27 cases (22.2%)** are frozen in
`heldout/ghost-heldout-v1.jsonl`, SHA-256
`74d68f5329388dbc1f9162f6052bb4f4cb3ecd04303bfab1823d428c1a518f2a`
(2 job cases: Q-013, Q-017 · 3 incidents: activation-sweep OCE,
ZeroClaw 503, relaypack lab proof · 1 state_read: lane_health
UNKNOWN). Frozen cases appear nowhere in the training split; this set
is GHOST-QUAL-001's core and its hash is the contamination guard.

## Totals (verified by re-reading the written files)

| File | Records |
|------|---------|
| `corpus/cases_train.jsonl` | 21 (13 job_case + 6 incident + 2 state_read) |
| `corpus/docs.jsonl` | 9 |
| **`corpus/ghost-v1.jsonl` (merged)** | **30** |
| `heldout/ghost-heldout-v1.jsonl` (NOT training data) | 6 |

Per-type corpus files total 36,798 bytes. Full case pool before the
split: 27 (15 job cases + 8 receipt incidents + 3 state readings +
1 investigation incident).

## Per-source counts (training split)

| Source | Records |
|--------|---------|
| ghost/queue/GHOST-Q-*.json (13 of 15 job cases; 2 frozen) | 13 |
| war-room/RECEIPT-ACTIVATION-SWEEP-2026-10-31.md (§1 router, §3 LiteLLM, §4 truststore) | 3 |
| war-room/RECEIPT-GHOST-A-ROUTER-2026-10-30.md (§A lane stall, §B failover) | 2 |
| ghost/queue/GHOST-Q-014-investigation.md (Gmail UNKNOWN) | 1 |
| state/penguin_keepalive.json (UNKNOWN) | 1 |
| state/storage_governor_status.json (STATE) | 1 |
| ghost/DESIGN-egress-router.md (doctrine sections) | 5 |
| ghost/queue/README.md (schema + drain law) | 3 |
| ghost/PROGRAM_STATE.md (drain priority) | 1 |

## Provenance & safety rules applied

- Every class assignment carries its basis in `detail` (the job's own
  requires_path text for job cases; the receipt section's recorded
  cause for incidents). Where no basis exists in the record, the label
  is UNKNOWN or NONE — never a best guess.
- Credential-shape scan ran over every emitted record (key prefixes,
  surrogate tokens, private-key blocks): **0 records dropped** — GHOST
  operational text carries no credential shapes once receipts' own
  redactions are respected.
- Q-009 / Q-010 are Markdown work orders in the queue directory, not
  JSON job entries; they are excluded from job cases (see gaps).

## TPU stage design (JAX/Flax failure-classifier — design only)

**Purpose:** a small native-JAX classifier over probe features on the
Kaggle TPU lane — the diagnostician's fast reflex beside the LoRA's
judgment. Shadow-only: it feeds the HEAT mechanic board as advice and
executes nothing (QUEUE row #10 seat law).

- **Features** (from probe/state records the fleet already writes):
  per-door last HTTP status (bucketed: 2xx/4xx/429/5xx/timeout/no-answer),
  consecutive_down count, seconds since last_up, circuit-breaker state
  (closed/open/half-open), lane status vector (up/down per lane from
  lane_health), probe detail class (timeout / refused / TLS / grant /
  blackout), disk free_gb + used_pct vs ceiling, NetBird session
  seconds-to-expiry where present.
- **Labels:** the failure class {EGRESS, TRANSPORT, FAULT, STATE,
  UNKNOWN} as recorded in this dataset's cases; NONE cases train the
  "no fault — do not page" negative class.
- **Model:** Flax (linen) MLP, 2 hidden layers × 64, optax AdamW, pure
  JAX on TPU v3-8; features exported as NumPy arrays by a builder that
  reads only state files + receipt-verdict lines (no live probing at
  dataset time — the classifier trains on history, not on the present).
- **Eval split:** the SAME frozen held-out cases (hash-verified).
  PASS bar mirrors the battery's: ≥85% class accuracy on determined
  held-out cases, and **zero** determined-class predictions on the
  frozen UNKNOWN case (a confident guess there fails the stage
  regardless of accuracy).

## Known gaps (honest — read before training on v1)

1. **The case pool is thin and queue-heavy.** 27 cases, 15 of them job
   cases whose "symptom" is a requires_path rather than a live
   incident narrative. GHOST's richest incident prose lives in receipts
   that predate the GHOST program (Oct 27–29 heal records, PLANB
   execution) and in zane-box state logs not yet receipted into
   war-room; v1 mined only what the named sources hold as files.
2. **STATE class is underfed.** One determined STATE case (storage
   governor, healthy) + the truststore repair (filed under the sweep
   as STATE). Fleet state-drift incidents (stale PID files, pruned
   binaries misread as service faults) are recorded in AGENTS.md
   lessons, not in GHOST receipts — a v2 should receipt-mine those.
3. **Receipt section shapes vary.** Incident extraction keyed on
   headed sections with recorded causes; receipts whose outcomes live
   in prose without headings (parts of the PHASE0 prep receipt) were
   not mined rather than force-parsed.
4. **Q-009 / Q-010 excluded** (Markdown WOs, not job entries) and
   **Q-014's job case is class NONE** by design — its diagnostic
   content enters through the investigation incident instead, where
   the evidence actually lives.
5. **No time-series.** lane_health / keepalive *histories* (the .bak
   snapshots, probe logs) were read only at their current state; the
   TPU classifier's feature design assumes a v2 time-series export
   that does not exist yet.

## Rebuild

`python3 build_dataset.py` in this directory regenerates `corpus/` and
`heldout/` from the live tree. Counts and the held-out hash will drift
as the queue and receipts grow; this manifest describes the
2026-10-31 build.

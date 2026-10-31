# ACE Training Dataset v1 — MANIFEST

**Built:** 2026-10-31, under QUEUE row #9 (Brandon order 2026-10-31
~13:45 CDT: "add ace and ghost to the gpu training and completely max
them out with gpu and tpu training"). **Builder:** `build_dataset.py`
in this directory (re-runnable; every number below comes from its run
output and from re-reading the written files, not from memory).
**Location:** `genesis-os/training/datasets/ace-v1/corpus/` (training)
+ `heldout/` (frozen eval core — never training data).

## Format (mirrors the Cody v1 pattern)

One JSONL record per line. Every record carries a `source` field naming
the exact file it came from, a `detail` field stating the transform and
the verbatim basis, and a sequential `id` within its file.

| Type | Shape | What it teaches |
|------|-------|-----------------|
| `verdict` | `instruction` / `response` | (recorded candidate features → recorded verdict state + recorded reason/next-step/evidence, verbatim). The response's only authored token is the `VERDICT:` label line. |
| `qa` | `instruction` / `response` | Rulebook knowledge: KB reject patterns, fit facts, filter banned-pattern groups + candidate-schema definitions, outcomes ledger, Brandon's rulings and universal application answers. Question framings are the fixed authored strings; every answer is source text. |
| `doc` | `text` | Verbatim chunks: DESIGN-ACE sections, the detector-v2 hard-rule block **as written in code**, pay-floor lines from the storm command. |

Transformations are mechanical only: field assembly from recorded
registry/KB fields, verbatim excerpting, section splitting. **No rule,
reason, or employer fact was invented** — where a registry entry records
no reason, the response carries only the fields that exist.

## Held-out law (frozen first)

The safety scan ran first; the freeze then selected from the clean
verdict pool by SHA-256 of the registry ID (hash order, ≥20% floor).
**17 of 64 clean registry verdict pairs (26.6%)** are frozen in
`heldout/ace-heldout-v1.jsonl`, SHA-256
`23452d59cdcbf897a54bbdb3fbea8d89a449efe6c7d6f543b906fe64e91cd632`.
Those registry IDs (ACE-2026-009, -021, -023, -024, -027, -029, -031,
-034, -035, -036, -041, -046, -047, -053, -062, -063, -065) appear
**nowhere** in the training split (verified by leak check after the
build), and KB postings carrying any registry ID were likewise kept out
of the training verdicts. This frozen set is ACE-QUAL-001's core; its
hash is the contamination guard — any future corpus whose held-out file
hash differs has broken the freeze.

## Totals (verified by re-reading the written files)

| File | Records |
|------|---------|
| `corpus/verdicts_train.jsonl` | 65 (47 registry + 18 KB-only postings) |
| `corpus/rulebook_qa.jsonl` | 83 |
| `corpus/rulings.jsonl` | 15 |
| `corpus/docs.jsonl` | 12 |
| **`corpus/ace-v1.jsonl` (merged)** | **175** |
| `heldout/ace-heldout-v1.jsonl` (NOT training data) | 17 |

By type: verdict 65 · qa 98 · doc 12. Per-type corpus files total
114,403 bytes.

## Per-source counts (training split)

| Source | Records |
|--------|---------|
| job-storm-ace/registry.json (verdicts) | 47 |
| kb/ace_kb.sqlite — postings (KB-only verdicts) | 18 |
| kb/ace_kb.sqlite — fit_facts (non-contact) | 38 |
| kb/ace_kb.sqlite — reject_patterns | 14 |
| kb/ace_kb.sqlite — outcomes | 5 |
| job-storm-ace/ace_filter.json (banned groups + schema) | 26 |
| war-room/JOB_STORM_ANSWERS_2026-10-31.md (rulings + universal answers) | 15 |
| job-storm-ace/DESIGN-ACE.md (sections) | 9 |
| war-room/JOB_STORM_COMMAND_2026-10-31.md (pay-floor lines) | 2 |
| job-storm-ace/ace_detector_v2.py (hard-rule block) | 1 |

## Provenance & safety rules applied

- **PII/credential rule:** records containing Brandon's email or phone
  strings, or credential shapes (`hsurr:`, key prefixes, private-key
  blocks), were dropped by the builder's scan — **10 records dropped**
  (5 registry verdicts whose recorded evidence quotes his email, 2 KB
  outcome rows, the contact-category fit facts, and the email/phone
  universal-answer rows). KB fit_facts in the `contact` category were
  excluded by rule before the scan. The dropped registry verdicts are
  recoverable from registry.json itself; they are out of the corpus,
  not out of the record.
- Detector-v2 "verdicts" enter only as the hard-rule block written in
  its source (doctrine) plus the verdicts it recorded into the registry
  and KB; no separate detector run log exists on disk, so none was
  mined (see gaps).

## TPU stage design (JAX/Flax fit-classifier — design only, no launch)

**Purpose:** a small native-JAX classifier on the Kaggle TPU lane that
learns the registry's fit geometry in parallel with the GPU LoRA —
and discharges the fleet's owed TPU-native stage before the Nov 7
refresh. Shadow-only, like the LoRA seat: it advises, never submits.

- **Features** (all from the recorded candidate schema, no new data):
  lane one-hot (remote/local); pay_min, pay_max normalized by the
  lane's floor (remote $15 / local $16); pay_period one-hot;
  `employer_domain_verified`, `employer_verified`, `base_pay_stated`
  booleans; `asks_upfront_fee`, `equipment_purchase_required`,
  `requires_degree` booleans; work_model one-hot (w2_hourly / contract
  / 1099_platform / per_task / microtask); `posted_days_ago` bucketed;
  `distance_mi` (local lane, null→−1); excluded-state flag (Illinois in
  `excluded_states` or absent from `allowed_states`); required-
  credential match count vs held credentials.
- **Labels:** the recorded registry state, collapsed: PASS-pool =
  {SCORED, SUBMITTED, STAGED} vs REJECT-pool = {REJECTED, DEAD};
  PARKED / FOLLOWUP / CHECK-FIRST excluded from the binary stage
  (too few, genuinely ambiguous — they stay LoRA/rubric territory).
- **Model:** Flax (linen) MLP, 2 hidden layers × 128, dropout 0.1,
  trained with optax AdamW in pure JAX on TPU v3-8; inputs as a single
  NumPy feature matrix exported from registry.json + KB postings by a
  builder that cites this manifest's feature list.
- **Eval split:** the SAME frozen held-out IDs above (hash-verified
  before the run). Report accuracy + full confusion matrix on the
  frozen set; the classifier's PASS bar mirrors the battery's:
  ≥90% verdict agreement with recorded outcomes, and **zero**
  PASS-pool predictions on candidates whose recorded reason names a
  hard rule (fee trap, Illinois exclusion, license requirement).

## Known gaps (honest — read before training on v1)

1. **Small verdict pool.** 64 clean registry verdicts + 18 KB-only
   postings is what one storm day honestly produced. The LoRA will
   learn the rulebook's *shape* from v1; verdict fluency needs the
   registry to grow (GHOST-Q-013's global lanes are the growth path).
2. **Thin ruling slice.** Brandon has formally ruled on few questions
   (1 BRANDON RULED block + answered-queue items + the universal
   answers table = 15 records). Preference learning beyond those
   rulings would be invention; v1 does not attempt it.
3. **Fact conflicts ride along, flagged.** JOB_STORM_ANSWERS records
   three unresolved conflicts (certifications, start date, DriveLine
   title "PROPOSED, unconfirmed"). The records carry the source's own
   conflict flags verbatim — the corpus teaches the flags, not a
   resolution. Training must not be read as resolving them.
4. **SCORED is a score, not an outcome.** 37 of 69 registry entries are
   SCORED (fit judgment at discovery time); only 7 SUBMITTED + 7 KB
   outcomes are downstream truth. Verdict records preserve the
   distinction (state is in every response); a v2 should weight
   outcome-confirmed records higher.
5. **No negative-space employer data.** Employers rejected at the
   discovery stage before registry entry leave no trace here;
   detector-v2's held-out discoveries (discovery_runs/) were not mined
   in v1 — candidate v2 source, unreviewed.

## Rebuild

`python3 build_dataset.py` in this directory regenerates `corpus/` and
`heldout/` from the live tree. Counts and the held-out hash will drift
as the registry grows; this manifest describes the 2026-10-31 build.

# Cody Training Dataset v1 — MANIFEST

**Built:** 2026-10-31, under WO-CODY-REAL-SOFTWARE-2026-10-31 (Stream A,
step 1). **Builder:** `build_dataset.py` in this directory (re-runnable;
every number below comes from its run output, not from memory).
**Location:** `genesis-os/training/datasets/cody-v1/corpus/`

## Format (design call, documented per the WO)

One JSONL record per line, four types. Every record carries a `source`
field naming the exact file it came from, a `detail` field (section /
pairing note), and a sequential `id` within its file.

| Type | Shape | What it teaches |
|------|-------|-----------------|
| `qa` | `instruction` / `response` | Standards & charter knowledge (answers are **verbatim** source text); WO→receipt gold chains; receipt verdict sections reproduced exactly |
| `doc` | `text` | Verbatim document chunks: charter, architecture, work-order template, receipts, READMEs, bounded MEMORY.md rule sections, AGENTS.md convention sections |
| `code_pair` | `instruction` / `response` | A module **with its tests** shipped intact — "tests are the contract" as a training signal |
| `code` | `text` | Code chunks split at top-level def/class boundaries (used when a pair exceeds the intact cap, or no paired test exists), header-labeled with path + pairing note |

Transformations are mechanical only: markdown section splitting, verbatim
excerpting, WO→receipt pairing, code/test pairing, AST-boundary chunking.
The only authored strings are the fixed question framings in `qa`
instructions; every answer is source text. **No content was invented.**

Size discipline: doc/code chunks capped at 6,000 chars; intact pairs capped
at 16,000 chars combined (oversize pairs are chunked on both sides and
cross-referenced in `detail` instead of being truncated).

## Totals (verified by re-reading the written files)

| File | Records |
|------|---------|
| `corpus/qa.jsonl` | 32 |
| `corpus/docs.jsonl` | 223 |
| `corpus/code.jsonl` | 212 (210 `code` + 2 `code_pair`) |
| **`corpus/cody-v1.jsonl` (merged)** | **467** |

By type: qa 32 · doc 223 · code 210 · code_pair 2.

467 dense, fully-provenanced records is what the bounded local material
honestly yields. The alternative — padding toward thousands with
duplicates, paraphrase, or scraped external code — was rejected on
purpose: Cody's charter (§1.1, §4.1 gate 2) treats fabricated volume as a
defect, not an asset. v2 growth should come from real receipts as Cody's
seats produce them.

## Per-source counts

| Source | Records |
|--------|---------|
| AGENTS.md (convention sections, truncated 2,500 ch each) | 49 |
| MEMORY.md (3 bounded rule sections only) | 3 |
| genesis-os/ENGINEERING_STANDARD.md | 16 |
| genesis-os/cody/CHARTER.md | 32 |
| genesis-os/cody/ARCHITECTURE.md | 11 |
| genesis-os/cody/CLAUDE_CREDIT_POLICY.md | 10 |
| genesis-os/cody/WORK_ORDER_TEMPLATE.md | 15 |
| genesis-os/cody/README.md | 6 |
| genesis-os/cody/CODY_VISION_2026-10-24.md | 4 |
| genesis-os/cody/missions/CODY-QUAL-001/WO_SPEC.md | 4 |
| genesis-os/cody/qualify_harness.py | 7 |
| genesis-os/cody/workers/run_call.py | 1 |
| genesis-os/war-room/CODY_V1_RECEIPT_2026-10-24.md | 13 |
| genesis-os/war-room/CODY_PHASE0_RECEIPT_2026-10-24.md | 11 |
| genesis-os/war-room/CODY_CATCHUP_RECEIPT_2026-10-24.md | 7 |
| genesis-os/war-room/WO-OPENCODE-MASTER_RECEIPT_2026-10-26.md | 4 |
| genesis-os/war-room/OPENCODE2_PILOT_RECEIPT_2026-10-24.md | 10 |
| genesis-os/war-room/WO-CODY-P0-EXECUTE-001.md (+1 as gold-chain source) | 2 |
| genesis-os/war-room/WO-OPENCODE-MASTER-2026-10-31.md | 16 |
| genesis-os/war-room/WO-CODY-REAL-SOFTWARE-2026-10-31.md | 6 |
| genesis-os/ghost/egress-router/router.py | 16 |
| genesis-os/ghost/egress-router/tests/test_router.py | 11 |
| genesis-os/master-runtime/master_runtime.py | 16 |
| genesis-os/master-runtime/README.md | 6 |
| genesis-os/pay/genesis_pay/core.py | 20 |
| genesis-os/pay/genesis_pay/paylinks.py | 15 |
| genesis-os/pay/genesis_pay/errors.py | 9 |
| genesis-os/pay/genesis_pay/__init__.py | 1 |
| genesis-os/pay/tests/test_genesis_pay.py | 9 |
| genesis-os/pay/tests/test_paylinks.py | 8 |
| genesis-os/pay/tests/test_argon_acceptance.py | 5 |
| genesis-os/pay/genesis_vault/ledger.py | 10 |
| genesis-os/pay/genesis_vault/rules.py | 10 |
| genesis-os/pay/genesis_vault/board.py | 1 |
| genesis-os/pay/genesis_vault/cli.py | 4 |
| genesis-os/pay/genesis_vault/parking.py | 8 |
| genesis-os/pay/genesis_vault/__main__.py | 1 |
| genesis-os/pay/genesis_vault/tests/test_vault.py | 8 |
| genesis-os/pay/genesis_vault/tests/test_vault_phase2.py | 7 |
| genesis-os/pay/tools/verify_pay_page.py | 1 |
| genesis-os/pay/README.md | 10 |
| genesis-os/pay/genesis_vault/README.md | 5 |
| genesis-os/training-sdk/gensdk/*.py (9 modules) | 38 |
| genesis-os/training-sdk/README.md + SMOKE.md | 14 |

Code+test pairs shipped intact (≤16K combined): `genesis_vault/board.py`
+ `test_balance_restatement.py`; `pay/tools/verify_pay_page.py` + its
test. The other five pairs (egress-router, genesis_pay core/paylinks,
vault ledger/rules) exceeded the cap and were chunked on both sides with
cross-references — no code was dropped, only split.

## Provenance & safety rules applied

- **Credential-shaped files were excluded by rule:** the builder never
  opens a file whose name matches `*secret*`, `*.env`, `credentials*`,
  `*.pem`, or `*.key`. In the selected source lists, 0 files matched the
  name rule. Emitted text was additionally scanned for credential shapes
  (API-key prefixes, private-key blocks, surrogate tokens): **2 records
  were dropped by that scan** (AGENTS.md chunks discussing credential
  mechanics) and are not in the corpus.
- MEMORY.md is included only as three bounded sections (THE RESET
  completion standard, DONE-sharpened, training fence) — the file's
  personal detail stays out of the training corpus by design.
- Cody runtime state (worker sandboxes, qualification sweep logs,
  credit ledger) was excluded: it is machine state, not knowledge.

## Known gaps (honest — read before training on v1)

1. **Penguin-side Cody history is absent.** Cody's home seat lives on
   penguin (`~/cody/`, OpenCode session history, worker mission outputs),
   and penguin is TRANSPORT-DARK from zane-box today — none of it is
   reachable, so none of it is in v1. Same for S1-side OpenCode session
   transcripts. What Cody *did* that only exists as chat relays is
   represented only where a war-room receipt captured it.
2. **Thin gold-chain count.** Only two complete WO→receipt pairs exist
   as files (P0-EXECUTE-001 → CODY_V1_RECEIPT; OPENCODE-MASTER-2026-10-26
   → its receipt). Most other Cody WOs have receipts that report
   BLOCKED outcomes (honest and valuable as discipline examples — they
   are in `docs`), but v1 has few *successful build* chains. This is the
   dataset's biggest quality gap and it is a fleet-output gap, not a
   curation choice.
3. **Untested flagship code.** `master_runtime.py` and the whole gensdk
   have **no paired unit tests in the tree**, so they enter as chunked
   `code` without the tests-are-the-contract signal. (The egress-router
   and pay/vault code carry that signal properly.)
4. **No failure/negative corpus.** Qualification sweep logs
   (`cody/state/qualification_log_*.jsonl`, mostly lane failures and
   BLOCKED_MODEL evidence) were excluded from v1. A v2 should add a
   labeled failure slice — Cody must recognize a dead lane as fluently
   as a live one.
5. **Docs skew.** Markdown discipline text (223 doc + most QA) outweighs
   code (212). For a *coding* seat, v2 should rebalance toward code —
   sourced from new receipts and the penguin/S1 transcripts once paths
   heal — rather than by diluting v1's provenance rule.
6. **No dedup pass against future eval fixtures.** CODY-QUAL-001 battery
   fixtures (see QUAL-001-BATTERY.md) must be authored fresh at eval
   time and checked against this corpus: any eval task whose solution
   text appears in v1 is contaminated and must be replaced.

## Rebuild

`python3 build_dataset.py` in this directory regenerates `corpus/` from
the live tree. Counts will drift as sources change; this manifest
describes the 2026-10-31 build.

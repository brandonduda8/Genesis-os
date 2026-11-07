# EXEC-AUDIT-001 — GENESIS-EXEC-001, Mission 1: Executive Baseline & Activation

**Executive:** Claude · **Independent auditor:** a separate verifier agent (claude-verifier, run in this session; it read
the code and the outputs cold) · **Verifier of record:** Zane · **Certifier:** Brandon · **Date:** 2026-10-31

Grades: PASS / FAIL / PARTIAL / NOT TESTED, from evidence only.

**On `--dangerously-skip-permissions`:** it is a launch flag for a local terminal. Typed into this chat it changes
nothing, and the first runtime WO forbids it as a shortcut. This mission ran under the session's normal controls.
Every action was Class A or B (branches, tests, reports).

## 1. Environment (actual, re-probed)

- **Host:** cloud container `vm`: 4 CPU, 15 GB RAM, 13 GB disk free; Python 3.13.17, Node 22.22.0, gh 2.89.0, Claude
  Code 2.1.316.
- **Egress:** PyPI 200, npm 200, GitHub via `gh` OK.
- **NVIDIA NIM, Groq and OpenRouter are unreachable from here** (connection refused by the proxy). Model routing can't
  be tested from this host.
- **Services:** none of Genesis's run here. zane-box, S1 and penguin aren't reachable from this session. Live service
  health is therefore NOT TESTED by design and comes from GHOST v2 on zane-box.
- **Permission system:** it **refused** three actions today: running `npm create netforge`, creating one PR, and
  attaching `genesis-hq`. None was worked around.

## 2. Discovery: what exists (verified from source and live GitHub)

**Genesis has five overlapping state stores:**

| Store | Holds | Where |
|---|---|---|
| Omega MissionStore and broker | coding missions | Genesis-core #10–#21 (draft) |
| GHOST v2 registry | operations jobs | Genesis-os#1 (draft) |
| master-runtime | reads queue files | genesis-os main |
| training `QUEUE.md` | training runs | markdown, written by the autopilot |
| Agent-X claude_runtime store | Claude runtime state | Agent-x branch |

**Decision: no sixth store.** The board aggregates the others read-only.

There are **70+ open PRs across 5 repos**, almost all drafts and none merged; that's the live list on the board. Work
is piling up waiting for review and merge. **That is the system's bottleneck, not missing code.**

## 3. Protected baseline (`exec/baseline.py`, recorded run)

| Suite | Grade | Evidence |
|---|---|---|
| genesis-core full (master + Universe + lab, `e7ba84a`) | **PARTIAL** | 263 passed, 2 skipped, 2 failed. **The 2 failures match the documented environment-only tests by name**: `test_fetch_mcp_markdown` (uvx) and `test_live_http_delegation_executes_real_tools` (sqlite3 CLI). |
| genesis-core Omega stack (#21 head `4282e7d`, run separately) | PARTIAL | 360 passed; the same 2 environment failures |
| agent-x Cody suite (`a2eb2d1`) | **PASS** | 108 passed; the claude_runtime subset is 38 passed |
| aurum-tools (`4bdcf3b`) | **PASS** | 8 ran |
| crypto-scanner, microcap-lab (`e7ba84a`) | **PASS** | 9 and 14 ran |
| exec-board | **PASS** | 17 ran (flagged `+dirty` until committed: the record is honest about that) |
| ghost-server-v2, training-kernels, dataset-builders, watch-pulse | **NOT TESTED** in this run | They live on branches not checked out here. Run separately today: 53/53, 11 OK, 8 OK and 8 checks OK. |

## 4. Highest-value safe task, implemented: the Executive Board (`exec/board.py`)

**What it shows** is one read-only page:
- **every open PR, live**, with its draft, merge and CI state and head commit;
- **the measured baseline**;
- **Needs Brandon / Needs Zane**: the queue of owed items, each with a required https source link.

**Why this task:** the owner's attention is the scarcest resource (doctrine §3.1–3.3). Today, what he must act on is
scattered across 70+ PRs. The board puts it on one page and invents nothing. Revenue and service health show
NOT TESTED until a verified source is wired.

## 5. Independent audit, and what it changed

The auditor's verdict on the first version was **PARTIAL**: two high-severity grading flaws. All ten findings were
handled.

| # | Finding | Severity | Fix | Test |
|---|---|---|---|---|
| 1 | A crash (rc 2, collection error) could grade PARTIAL | High | PARTIAL now requires rc 1, tests actually ran, and no errors | `test_audit_1_*` |
| 2 | "Environment failures" was only a count, so real regressions could hide | High | Matched **by pytest node id**, from the `FAILED` lines | `test_audit_2_*` |
| 3 | rc 0 with zero tests graded PASS | Medium | PASS needs a parsed count > 0 or the suite's own pass marker | `test_audit_3_*` |
| 4 | Commit recorded without a dirty flag | Medium | `+dirty` suffix | `test_audit_4_*` |
| 5 | PR list not paginated | Medium | Pagination at 100 per page | `test_audit_5_*` |
| 6 | Per-PR fetch failures hidden under LIVE; commit statuses ignored | Medium | Failures recorded, so the board reads PARTIAL; statuses read; more RED states | `test_audit_6_*` |
| 7, 9 | Any string counted as a "source"; `\|` broke tables | Low | https required; cells escaped | `test_audit_7_and_9_*` |
| 8 | The board trusts the baseline file it's given | Low | **Open:** add schema and integrity checks | — |
| 10 | Every draft PR shows `mergeable_state: clean` | Info | Displayed as GitHub returns it; a live re-check is owed | — |

Auditor's clean areas: the board uses argv only (no shell), `gh` GET only, and writes nothing outside its outputs.

## 6. The eight audit areas

| Area | Grade | Note |
|---|---|---|
| LLM engineering | **NOT TESTED** | No provider is reachable from this host. Routing code exists in Genesis-core (`llm.py`, fail-closed). |
| SDK engineering | PASS | `gh` REST via argv, paginated, failures surfaced |
| Software engineering | PASS | 17 board tests; every audit finding has a regression test |
| Reality connectivity | PARTIAL | PR state is live and real; revenue and services are NOT TESTED by design |
| Integration | PARTIAL | Aggregates 5 repos read-only. The 5 state stores are not yet unified (backlog E-2). |
| Security | PASS | No secrets read, no writes, no shell. The suites it runs aren't sandboxed (documented). |
| SRE / operations | NOT TESTED | No scheduled run yet. That needs a host: zane-box cron, or a GHOST job. |
| Executive review | PARTIAL | Built and independently audited. Not yet verified by Zane, and not deployed. |

**Deployment readiness:** BUILT. To run it on zane-box:

```bash
python3 exec/baseline.py --py <venv>/bin/python --out exec/state/baseline.json
python3 exec/board.py --baseline exec/state/baseline.json --out exec/state/BOARD.md --html exec/state/board.html
```

**Verified impact:** for the first time, one command produces an evidence-graded view of every PR and suite in the
ecosystem, plus a sourced list of who owes what.

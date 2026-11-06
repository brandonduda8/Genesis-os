# The Mirror: WO-PLATINUM-MIRROR-MESH-MINIONS-001, build step 1

**Cold session? Read [`OPERATOR-BRIEF.md`](OPERATOR-BRIEF.md) first.** Then run
`python3 mirror/brief.py --check mirror/OPERATOR-BRIEF.md`. If it says STALE, regenerate the Brief before trusting it.

| File | What it holds | Law the code enforces |
|---|---|---|
| `data/debts.json` | the open-debts register: who owes whom what, both directions | no https source, no debt. Brandon's list holds only LEVEL_C, HANDS and DECISION items. Done needs evidence. |
| `data/vantages.json`, `data/probes/` | vantages: declared powers and blind spots (graded), plus each vantage's latest **probe** | declared ≠ proven. The router reads probes only. |
| `data/routing.json` | work class → vantages in preference order, plus the probe legs it needs | Brandon is a Level C destination, never a work queue. A novel class becomes a policy question. |
| `data/roster.json` | the minion roster: charter class, actions, verifier seat, resume point | no Level C action; at most one credential; the verifier is a separate seat (not a minion); one instance each |
| `data/program.json`, `conflicts.json`, `sources.json` | orders in force (graded); WO conflicts with a recommendation; what the mirror covers, and what it doesn't yet | anything not mirrored says NOT MIRRORED, never "current" |
| `data/MANIFEST.json` | SHA-256 of every data file, plus one digest over them | two mirrors reconcile **by hash**. A conflict is listed, never auto-resolved. |

```bash
python3 mirror/mirror.py validate                       # exit 1 on any violation
python3 mirror/probe.py --vantage <id> --write          # publish this vantage's trio (github/package/model + docker)
python3 mirror/mirror.py route container_work           # ROUTE / HOLD / PACKET / POLICY_QUESTION, with substitutions
python3 mirror/mirror.py manifest
python3 mirror/mirror.py reconcile <mirrorA/data> <mirrorB/data>
python3 mirror/brief.py --out mirror/OPERATOR-BRIEF.md   # live PRs via exec/board.py; --offline skips them
```

The exec board (`exec/board.py`) now reads its Needs Brandon and Needs Zane lists from `debts.json`. The old
`exec/OWNER-QUEUE.json` is retired, leaving one register instead of two.

## Graded state (2026-11-01)

| Part | Status | Evidence |
|---|---|---|
| Mirror skeleton, debts register, Brief, routing, roster law | **BUILT** | 17 tests (1 skipped on this branch, because `ghost-server/` isn't in this checkout; the class list was checked equal to main's `gates.py` by hand). `validate` is clean. The Brief is FRESH. |
| Probes | **1 of 8 vantages** | `claude-cloud`: github ✓, package ✓; model ✗ (NIM, Groq and OpenRouter refused by the proxy, 403); docker ✗ |
| Routing | **BUILT, mostly HOLD** | repo_work, package_build and verification route to claude-cloud. Container, model, home-network and GPU work HOLD: no probes from S1, zane-box, penguin, phone or Kaggle (debt Z-10). |
| Minions | **0 running**: 1 charterable class, the rest STAGED | GHOST defines an action ceiling only for `ghost_operations` (conflict K-4). Drain and Revival are charterable; the other 6 wait on ceilings (C-5) and Brandon's signing sitting (B-4). |
| Mirror primary on S1 / replica on zane-box | **STAGED** | the repo is the mirror today. S1 promotion rides B-5 (K-3). |
| Zane's operator state | **NOT MIRRORED** | debt Z-9 |

The four acceptance proofs (dark drill, routing proof, cold-start proof, overnight proof) haven't been attempted.
Every part above is BUILT or STAGED, none DONE.

# Genesis OS

[![self-check](https://github.com/brandonduda8/Genesis-os/actions/workflows/self-check.yml/badge.svg?branch=main)](https://github.com/brandonduda8/Genesis-os/actions/workflows/self-check.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

The working monorepo for Genesis, a personal multi-agent AI system. Several AI
coding agents ("lanes") take bounded work orders, and every result has to pass
code-enforced gates and leave a written receipt before it counts. Most of the
code is standard-library Python; there are also two small Android apps.

This is a personal research and operations repo, not a packaged product. Many
components expect to run on the author's own machines and refer to paths and
services outside this repo.

## What's here

| Directory | What it is | Language / tests |
|---|---|---|
| [`ghost-server/`](ghost-server/README.md) | **GHOST SERVER v2**: a store-and-forward job server in one process with one SQLite file. Durable job registry with lineage, circuit-breaker "doors" with hard deadlines, commit gates, WIP caps, a sandboxed CodeAct runner, a read-only MCP (stdio) server, and signed envelopes between machines. Design in [`DESIGN.md`](ghost-server/DESIGN.md). | Python 3.8+ stdlib · 53 unittest tests (18 skip in a plain clone) |
| `ghost/queue/` | The GHOST job queue: one JSON file per job. | data |
| [`master-runtime/`](master-runtime/README.md) | A read-only CLI that reads the GHOST job queue, the job-storm registry (when present) and the agent registry and renders one status board, a dispatch plan, and a claims-vs-receipts "verify" pass. | Python stdlib |
| [`training-sdk/`](training-sdk/README.md) | **gensdk**: one CLI over GPU/TPU training providers (Kaggle, Colab, Lightning, Modal, and a local box), built as wrappers around each provider's own CLI. Specs are staged by default; a policy engine runs before any launch, keeps a spend ledger, and has no purchase code path. | Python stdlib |
| `training/` | Training autopilot design and queue, plus dataset builders for three fine-tuning datasets (`ace-v1`, `cody-v1`, `ghost-v1`), each with a `MANIFEST.md`. | Python · 8 unittest tests in `training/datasets/tests/` |
| `job-storm-ace/` | `ace_detector_v2.py`: a rule-based filter that normalizes job-listing text and hard-rejects listings that need credentials or conditions the job seeker doesn't meet. | Python |
| `genesis/` | The original prototype: a ~120-line agent kernel (mission control → orchestrator → agent registry → JSON memory) with stub Architect and Coder agents. | Python |
| `watch-pulse/` | Source for **Watch+Pulse** (`com.genesis.watchpulse`), a small Android app in plain Java, built with a Gradle-free aapt2 → javac → d8 pipeline. | Java |
| `war-room/` | Work orders, design notes, fault ledger and build receipts: the paper trail behind each component. | Markdown |

## Quickstart

Clone the repo, then:

```bash
# GHOST SERVER test suite (no network, no extra packages)
cd ghost-server
python3 -m unittest discover -s tests

# dataset builder tests
cd ../training/datasets
python3 -m unittest discover -s tests

# master board from the queue files in this repo
cd ../../master-runtime
python3 master_runtime.py status

# training SDK CLI
cd ../training-sdk
python3 bin/gensdk --help
```

Each component's README covers its own commands and deployment notes.

## Design principles (as enforced in code)

- **Agents propose; code disposes.** Spending money, sending messages and
  other consequential actions sit behind explicit approval gates in code,
  not in prompts.
- **Nothing is "done" on an agent's say-so.** Status follows a ladder
  (STAGED → BUILT → LIVE), and results are checked against written receipts.
- **One mission per lane at a time**, with WIP caps.
- **Standard library first**, so components run on any box with Python 3.

## CI

`.github/workflows/self-check.yml` runs a read-only structure and docs audit
daily and on demand. Its latest scheduled runs on `main` failed on a syntax
error in the Markdown link-check step; a fix is open as a separate draft pull
request.

## License

Code is released under the [MIT License](LICENSE).

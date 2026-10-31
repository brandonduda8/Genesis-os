# gensdk — Genesis Training SDK

One programmatic interface over all of Brandon Duda's GPU/TPU training
services. Built 2026-10-31 on Brandon's order ("make me a sdk... I'll sign
in and grant you admin access to all my GPU and tpu services"), immediately
after he lifted the per-run tap fence for free-lane training.

gensdk is the clean programmatic layer **over** the existing October
training system (`genesis-os/train/` — dispatchers, dashboard, envelope
gates, job queue) and the provider CLIs. It is not a competing system: job
fields and quota conventions mirror `train/` (service keys `kaggle_gpu`,
`kaggle_tpu`, `colab`, `lightning`; Kaggle quota in weekly hours; the
dataset SHA-256 hash-gate discipline). The coordinator's autopilot
(`genesis-os/training/`) launches runs; gensdk is what any agent or script
calls to stage, launch, check, and account for them.

## Design law

- **CLI wrappers only.** Each provider module shells out to the provider's
  own CLI (`bin/kaggle.py`, `colab-fixed`, `modal`). The SDK never
  reimplements provider auth and never reads, prints, logs, or persists
  any credential or token file. Kaggle auth is a Secure-Vault surrogate
  injected inside the connector CLI; Colab auth is the CLI's own OAuth
  store; Modal auth is `~/.modal.toml`, read by the Modal CLI alone.
- **Staging by default.** `gensdk submit <spec>` validates the spec,
  verifies the dataset hash gate, and writes a staging record. Nothing
  launches and nothing burns without `--execute`.
- **Policy engine before every launch** (`gensdk/policy.py`):
  - Free lanes (Kaggle GPU, Kaggle TPU, Colab included CUs, S1-local) are
    auto-approved under Brandon's 2026-10-31 order.
  - Modal auto-approves only while month-to-date Modal spend (gensdk
    ledger) plus the run's cap stays within the **$30/mo included
    credit**. Overage is paid spend — Brandon's tap, never automatic.
  - **Top-up purchases are never automatic.** There is no purchase code
    path anywhere in this SDK.
  - **One run per lane at a time**; an execute-submit refuses while the
    lane's active run is not terminal.
  - **Eval/quality gates are not taps** and are not waived: a spec's
    `eval_gate` travels with the run record and must pass before any
    downstream serving decision.
- **Burn ledger** (`ledger/burn-ledger.jsonl`): append-only JSONL; every
  append is read back from disk and verified before the call returns.
  `gensdk ledger` reports ISO-week and calendar-month totals per
  provider/unit. The ledger is the SDK's own book — provider-side truth
  is read live by `gensdk quota`.

## Policy supersession note

`custom.legacy-kaggle/CONNECTOR.md` Rule 6 and the `local-colab` skill
Rule 7 both required Brandon's explicit per-run tap before any GPU burn.
**Both are superseded for free lanes by Brandon's direct order of
2026-10-31 ~07:09 CDT** ("GPU training too and TPU training — no more
taps, automate and maximize"), which the fleet recorded as a standing
rule change. gensdk encodes the new rule. What the order did NOT lift:
paid compute beyond included credits (spend is spend), live trading /
money movement (never authorized — his word was a typo he corrected),
and quality gates (an eval-pass requirement is a quality gate, not a tap).

## Providers — honest status (evidence in SMOKE.md)

| Provider | State | Basis |
|---|---|---|
| kaggle_gpu | LIVE | Connector CLI auth + quota answered live in smoke |
| kaggle_tpu | LIVE | Same CLI; separate weekly TPU pool |
| colab | LIVE (read paths) / EXPERIMENTAL (run) | `colab usage` + `sessions` proven; `colab run` NOT proven end-to-end — `submit` refuses without `allow_experimental: true` in the spec |
| modal | STAGED | CLI installed (modal 1.6.0) and `~/.modal.toml` present; gensdk smoke does not probe Modal's API for a live balance (none is exposed to read); spend fenced to the $30/mo included credit |
| lightning | NOT_CONNECTED | No credential on file — honest stub |
| local_s1 | TRANSPORT_GATED | Honest stub; S1 reached via GHOST queue / heal windows until the Phase B key deposit lands |

## Job spec

JSON object; see `gensdk/jobspec.py` for the authoritative schema.
Required: `name`, `provider`, `entrypoint`, `burn_cap {amount, unit}`.
The dataset **hash gate**: when `dataset_path` is set, `dataset_sha256`
is required and re-verified at submit time — a mismatch refuses the
submit, staged or executed. Optional: `est_burn`, `kernel_ref`,
`eval_gate {description, checks[]}`, `allow_experimental`, `priority`,
`notes`. Worked example: `examples/example-kaggle-spec.json`.

## CLI

```
bin/gensdk providers
bin/gensdk quota
bin/gensdk submit <spec.json>            # stage only
bin/gensdk submit <spec.json> --execute  # policy check, then launch
bin/gensdk status [--provider P] [--ref R]
bin/gensdk ledger [--append-smoke]
```

State lives inside this directory: `state/staged/` (staging records),
`state/active.json` (one active run per lane), `ledger/burn-ledger.jsonl`.
Python 3.12, stdlib only. Also runnable as `python3 -m gensdk` from this
directory.

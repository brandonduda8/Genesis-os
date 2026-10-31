# SMOKE.md — gensdk smoke results (run 2026-10-31, this box)

Every command below was run FOR REAL against the live CLIs. Read-only
paths plus one staging submit and four refusal tests. **Nothing was
launched and nothing was burned**: no `--execute` submit ever reached a
provider launch path (the two `--execute` tests were refused by policy
before any launch call), Kaggle GPU used this week is 0.012 h (pre-
existing), Colab usage rate 0.00/hr, 0 active assignments.

## 1. `bin/gensdk providers` (final run, after the defect workaround)

```
kaggle_gpu   LIVE             AUTH_OK: datasets/list returned HTTP 200 (20 item(s) on page)
kaggle_tpu   LIVE             AUTH_OK: datasets/list returned HTTP 200 (20 item(s) on page)
colab        LIVE             usage answers (OAuth-authed CLI); run path is EXPERIMENTAL (unproven end-to-end)
modal        STAGED           CLI present (modal client version: 1.6.0), ~/.modal.toml present (contents never read); live API auth not probed by gensdk smoke
lightning    NOT_CONNECTED    no Lightning AI credential on file; signup was in progress per genesis-os/train records. Include this lane only via Brandon's secure-card API key (GRANT.md).
local_s1     TRANSPORT_GATED  S1 reachable only through gated fleet transport (tailnet data path / GHOST heal windows); Phase B key deposit pending. Specs stage locally; execution dispatches via the GHOST queue, not from this SDK, until transport verifies.
```

## 2. `bin/gensdk quota` (live numbers)

- **kaggle_gpu**: used 0.012 h, reserved 0.0, allowed 30.0 h,
  **remaining 29.988 h**, refresh 2026-11-07T00:00:00Z — from
  `kaggle.py quota` (live RPC).
- **kaggle_tpu**: used 0.0, allowed 20.0 h, **remaining 20.0 h**, same
  refresh.
- **colab**: **remaining 392.99 CU** — parsed from `colab usage` via
  colab-fixed. Raw output, verbatim:
  ```
  [colab] A new version of Colab CLI is available: 0.7.5 (current: 0.7.4)
  [colab] Run 'colab update' to update.
  [colab] To silence this check, set "enable_update_check": false in ~/.config/colab-cli/settings.json

  Current balance: 392.99 compute units
  Usage rate: 0.00/hr
  Active assignments: 0
  ```
  (392.99 CU matches the fleet's independent verification of
  2026-10-30 — same balance, no burn since.)
- **modal**: no live balance read (Modal exposes none to this wrapper);
  policy view: included credit $30/mo, ledger month-to-date $0.00,
  headroom $30.00.
- **lightning / local_s1**: no live number exists; honest notes printed
  (see `gensdk quota` JSON).

Also proven live in this smoke (direct provider call): **Kaggle kernels
list** for user `brandonduda` returned real kernels, e.g.
`brandonduda/skill-writers-infer-v3-hardened-cpu`,
`brandonduda/god-hermes-llama-3-1-8b-unsloth-qlora`.

And `colab-fixed run --help` was read (no run made): signature is
`colab run [OPTIONS] {script} [script_args]...` with `--gpu`,
`--tpu {v5e1,v6e1}`, `--session` — the wrapper's invocation shape
matches. The run path remains EXPERIMENTAL (not proven end-to-end).

## 3. Ledger append + read-back (`bin/gensdk ledger --append-smoke`)

Appended one zero-amount `kind:"smoke"` entry; the append function read
the last line back from disk and matched it before returning. Totals
reader then reported: entries=1, week={}, month={} (smoke entries are
excluded from totals and are amount 0 regardless).

## 4. Staging submit (`bin/gensdk submit examples/example-kaggle-spec.json`)

- Hash gate: `hash gate OK: examples/dataset-smoke.txt
  sha256=8d9ca8c48c8d5844eaab72046e5be7621d36fda8bf90ad12a2bab3c009c77e2d`
- Verdict: `STAGED — no --execute; staging only, nothing launched,
  nothing burned`; staging record written to
  `state/staged/gensdk-example-kaggle-smoke-20261031T121943Z.json`.
- `bin/gensdk status` afterwards: all six lanes `active: null` — the
  staging submit touched no lane, as designed.

## 5. Refusal tests (all behaved as specified)

| Test | Result |
|---|---|
| Spec with a wrong `dataset_sha256` | rc=1, `REFUSED: hash gate FAILED ... spec declares 0000...` |
| `--execute` on lightning | rc=1, `POLICY REFUSAL: lightning is NOT_CONNECTED ...` (refused before any launch call) |
| `--execute` on modal with $45 cap | rc=1, `POLICY REFUSAL: modal included-credit fence: month-to-date $0.00 + cap $45.00 exceeds the $30/mo included credit. Paid overage is Brandon's tap, never automatic.` |
| Structurally invalid spec (`{"name":"x"}`) | rc=2, per-field INVALID SPEC errors (provider / entrypoint / burn_cap) |

## 6. Defects found

1. **Connector CLI defect (worked around, NOT fixed here):**
   `custom.legacy-kaggle/bin/kaggle.py` line ~31 inserts
   `/opt/muse/skills/custom-connector-setup/templates/skill/bin` into
   `sys.path` for `import dynamic_credentials`. That directory does not
   exist; the module lives at
   `/opt/muse/skills/custom-connector-setup/bin/dynamic_credentials.py`.
   First smoke run: both Kaggle lanes reported NOT_CONFIGURED with
   `ModuleNotFoundError: No module named 'dynamic_credentials'`.
   gensdk's Kaggle provider supplies the correct directory via
   PYTHONPATH (see the DEFECT WORKAROUND comment in
   `gensdk/providers/kaggle.py`). The connector CLI should be fixed at
   the source by its owner; gensdk does not edit files outside
   `training-sdk/`.
2. **gensdk Colab parser bug (found and fixed in this smoke):** the
   first quota parse returned `remaining_cu: 0.7` — the parser matched
   the CLI's update notice ("A new version ... is **available: 0.7**.5")
   as a balance. Caught because the raw output is always carried in the
   result and the number contradicted the known 392.99 CU. Parser now
   anchors on the `Current balance: N compute units` line and skips
   version lines; re-run returns 392.99.
3. **Noted, not a defect:** the connector doc's "HONEST BOUNDARY" says
   Kaggle push/status/output are unverified, while the CLI's own code
   carries 2026-09-28/2026-10-14 verification comments and a hardened
   downloader. gensdk grades only what it proved itself today: auth,
   quota, and kernels list are LIVE-verified; push/status/output were
   NOT exercised (no burns authorized for this build task) and remain
   UNVERIFIED from gensdk's seat.

## Verdicts

- kaggle_gpu: **LIVE** (VERIFIED — auth, quota, kernels list)
- kaggle_tpu: **LIVE** (VERIFIED — auth, quota; same CLI)
- colab: **LIVE** read paths (VERIFIED — usage 392.99 CU, sessions);
  run path **EXPERIMENTAL** (UNVERIFIED end-to-end)
- modal: **STAGED** (CLI 1.6.0 + config present VERIFIED; live API
  balance UNVERIFIED — none read)
- lightning: **NOT_CONNECTED** (VERIFIED absence of credential path)
- local_s1: **TRANSPORT_GATED** (fleet transport state, per standing
  records)

# TRAINING AUTOPILOT — loop design

**Authority.** Brandon Duda, 2026-10-31 ~07:09 CDT: GPU + TPU training on the free lanes
is pre-authorized standing — "no more taps, automate and maximize" — plus the MAX-BURN
doctrine (~07:16 CDT): drive free-lane quotas toward their limits before refresh; unused
expiring quota is power leaking. **Fences that survive:** paid compute (Modal, Daytona,
Hetzner, anything with a meter) is Brandon's tap, always; Colab Run-all is his physical
click in his own Google session; HF gated-repo forms are his hands; quality gates are
gates, not taps (Phoenix v8 serves only on eval PASS ≥0.90 classifier / ≤0.05
hallucination); skill-writer drafts are never sent or published by the machine.

**First verified launch under this design:** Phoenix v8 coherence eval, 2026-10-31
(`receipts/2026-10-31-phoenix-v8-eval-launch.md`). Lane proof:
`receipts/2026-10-31-kaggle-lane-verification.md`.

## The loop (one pass)
1. **Sync.** Read `QUEUE.md` + `genesis-os/train/state/jobs/*.json`. A run is eligible
   only if its queue status is STAGED (all inputs present, config fixed, eval wired)
   and its lane is free. VERIFY-FIRST / LEGACY / FENCED rows are never eligible.
2. **Lane check.** `kaggle.py auth` + `quota` (see CLI contract below). If auth fails
   after one retry, grade the pass BLOCKED-EGRESS and stop — never hammer the lane.
3. **One run per lane at a time.** Kaggle GPU: max 2 concurrent sessions is Kaggle's own
   batch cap ("Maximum batch GPU session count of 2 reached" = no-launch, not an error);
   the autopilot deliberately runs **one** GPU job at a time so a failure is attributable.
   CPU kernels may run alongside (they burn no GPU quota).
4. **Preflight** (mirrors the fleet's hardened kernels): metadata parses, slug is
   owner-qualified (`brandonduda/…`), kernel sources exist and read COMPLETE, dataset/
   adapter pins resolve, disk/sequence config sane. Any failure → fix staging, re-queue
   with the reason; never push a known-broken config to "see what happens."
5. **Launch.** `kaggle.py push <kernel-dir>`. Record kernelId + versionNumber from the
   push response in the launch receipt **immediately** — a push without a receipt is
   treated as never having happened.
6. **Poll.** `kaggle.py status <owner/slug>` every ~5 min. `status=None` ≈ the first
   2–4 min is provisioning, not an error. Never fetch output while RUNNING.
7. **Harvest.** On COMPLETE: `kaggle.py output` into the run's harvest dir; verify the
   expected artifacts exist (and hash adapters). On ERROR: fetch the log tail into the
   failure receipt before anything else.
8. **Score.** Where a gate is deterministic (eval batteries, guardrail audits), score
   mechanically from the harvested artifacts and file a verdict receipt
   (PASS / FAIL / INCONCLUSIVE with the numbers). A PASS never serves anything by
   itself — serving changes follow each program's own approval terms.
9. **Ledger.** After every terminal run, re-read `kaggle.py quota` and append the burn
   to QUEUE.md's ledger (the quota endpoint is the source of truth; wall-clock is a
   cross-check, never the record). Weekly snapshot before the Saturday 00:00Z refresh
   so expiring quota is visible while it can still be spent (MAX-BURN doctrine).
10. **Advance.** Mark the run's outcome in QUEUE.md, promote the next STAGED run on the
    freed lane, file receipts. Every state change traces to a receipt — no receipt, no
    status change.

## Failure handling
- **ERROR status** → failure receipt with: kernel slug + version, log tail, failure class
  (config / data / egress / quota / code), and the named fix. The run re-queues **only
  after the fix lands** — never an automatic relaunch loop. Max 2 re-queues per run;
  then it parks for Zane with the full history.
- **Silent death** (RUNNING with no status change beyond the kernel's session timeout)
  → re-check status once after 30 min; if still frozen, fetch the log, file the failure
  receipt, re-queue per the rule above. **Never duplicate-push a slug to "retry"** — a
  push mints a new version of the same kernel; recovery is a fresh version only after
  the old session is terminal.
- **Egress stall** (auth/quota calls timing out) → one retry, then the pass ends
  BLOCKED-EGRESS. The next scheduled pass is the retry. Stalls are weather, not signal.
- **Quota fit** → before any GPU launch, `remaining ≥ est. burn × 1.5`. A run that
  cannot fit before refresh waits for the refresh — mid-run quota death corrupts
  harvests and wastes the partial burn.

## CLI contract (verified 2026-10-31 — read before operating the lane)
- Binary: `~/workspace/custom-connectors/custom.legacy-kaggle/bin/kaggle.py`
  with **`PYTHONPATH=/opt/muse/skills/custom-connector-setup/bin`** (the CLI's built-in
  sys.path points at a templates dir that lacks `dynamic_credentials.py`).
- Commands: `auth · quota · datasets · kernels · push <dir> · status <owner/slug> ·
  output <owner/slug> <dest>`. Push requires the owner-qualified slug from
  kernel-metadata.json. Push success = the JSON response with kernelId/versionNumber
  (or the fleet's `push_succeeded()` classifier in `train/dispatchers/kaggle_dispatch.py`).
- GPU shape: **T4 only** (P100 is the sm_60 trap — no kernels in modern torch).

## Cron (Zane creates after this first verified launch — designed here, not scheduled)
- **Poll-and-advance**, every 20 min, modeled on the skill-writers v3 monitor: reads
  kernel STATUS + OUTPUT via the CLI (never stale log lines), advances the loop one
  step per run in flight, files receipts, and stays silent unless a run lands, fails,
  or a lane blocks.
- **Weekly quota snapshot**, Friday ~23:00 UTC (1 h before the Saturday 00:00Z refresh):
  quota read + ledger append + a one-line "quota about to expire unused: X h" flag —
  the MAX-BURN tripwire.
- Both crons inherit the fleet's keepalive discipline (double-fork daemons, PID
  identity verified via /proc cmdline, state under `genesis-os/training/`).

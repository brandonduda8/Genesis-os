# GHOST SERVER v2 — Design note (P0)

**WO:** WO-CLAUDE-GHOST-SERVER-STEM-2026-10-31 · **Queue:** GHOST-Q-017 · **Builder:** Claude · **Reviewer:** Zane ·
**Certifier:** Brandon · **Status:** BUILT on branch `claude/ghost-server-v2` (cloud-tested). NOT LIVE on any host.

> **Review order.** The WO asks for Zane's review of this note before code. Brandon told the builder to proceed on its
> own judgement. I wrote the code on an isolated draft branch so the design can be reviewed *against working code
> and tests*. Nothing is deployed. If Zane rejects any section, the matching code is changed or deleted before merge.
> No phase is live until Zane re-runs its receipt on zane-box.

## 1. What GHOST v2 is, and what it is not

GHOST v2 is **one process with one SQLite file**. It is the fleet's store-and-forward operations server. It holds jobs
durably, waits for a door (transport) to heal, and then forwards the work. It only counts a result once a deterministic
verifier has passed it.

GHOST v2 unites parts that already exist. It does not start a parallel runtime:

| Existing part | Role inside GHOST v2 |
|---|---|
| File queue `ghost/queue/GHOST-Q-*.json` + its README drain law | **Legacy input.** Imported by deterministic ID, and the file's SHA-256 is recorded in lineage. The files stay as the human-readable mirror; GHOST never edits them. |
| Egress router (`ghost/egress-router/router.py`, zane-box :18955) | **A door.** It is wrapped by the door interface as an HTTP forward proxy (CONNECT). GHOST does not replace the router. |
| Relay packs (S1, penguin; staged) | **Doors** of the same kind, configured once Q-006 installs them. |
| Master runtime (`master-runtime/`) | Keeps its CLI and laws. GHOST adopts those laws in code: mutations by ID only, Brandon's grade ladder, human-relay jobs never dispatched, a 429 is a hard stop. `board` can later read `ghost.db`. |
| Genesis Omega (Genesis-core #9–#21, draft) | **Not adopted.** Q-010 records the Oct 25 ruling: only its 3 rules are adopted. GHOST therefore has **no dependency** on Omega. It shares one thing only: the **Ed25519 grant wire format** of `genesis/omega/authority.py`. If Brandon ever adopts Omega, one owner key serves both, and GHOST can carry Omega work as envelopes without verifying it. |
| WO-GHOST-SERVER-001 Part C (NATS + JetStream lift) | Still possible. The registry is the source of truth, and NATS would be one more transport behind the door and envelope interfaces. Job IDs and schema are unchanged, as the queue README requires. |

**Not GHOST's job:** egress circumvention (doors are Brandon's machines on Brandon's networks only), anything that
touches the StarNet anchor (:8888), and any Level C action (§5).

## 2. Operating assumptions, turned into requirements

| Reality | Requirement in code |
|---|---|
| The network is usually lying or dead | Every outbound request has a **hard total deadline of 5 s**: the connect, the CONNECT handshake, TLS and reading the response all share one deadline. Per-socket timeouts can add up to 15 s, so they are not used. |
| Egress stalls silently | Circuit breaker per door: 3 consecutive failures open it, cool-down starts at 60 s and doubles up to 15 min, and a half-open state allows one probe. A **429 opens the breaker for at least 15 min with no retry around it**. |
| "Healed" is often claimed falsely | A door is **healed** only when the **acceptance trio** passes *through that door* in one probe round: GitHub GET, a NIM completion and a pip fetch. One or two passing legs mean `PARTIAL`, never healed. |
| NetBird expires daily; hosts recycle | Jobs, attempts, envelopes and the ledger live in SQLite (WAL, `synchronous=FULL`). On boot, jobs left RUNNING with an expired lease return to QUEUED, and that interruption counts as an attempt. Nothing is lost and nothing loops forever. |
| zane-box: 2 CPU / 8 GB, no Docker | Standard library only. One process, no threads in the idle path, one sleep-driven tick. Budget in §8. |

## 3. Data model (`state/ghost.db`, mode 0600)

```
jobs(job_id PK 'GHOST-Q-NNN', title, lane, executor, assignee, target_host,
     requires JSON,         -- structured path conditions, e.g. ["door:egress"], ["human:brandon-relay"]
     spec JSON,             -- command_or_ref / codeact script / fence_notes (fences travel with the job)
     verifier JSON,         -- fixed at creation; its hash is in lineage, so a job cannot rewrite its own judge
     level 'A'|'B'|'C', state, blocked_reason, attempts, max_attempts,
     next_eligible_at, lease_until, receipt_target, content_sha256,
     created_at, updated_at, version)          -- version = optimistic lock for every write
attempts(attempt_id, job_id, n, started_at, ended_at, outcome, error_class, error, cpu_s, rss_kb)
lineage(job_id, seq, at, actor, transform, source, input_sha256, output_sha256, note)  -- append-only
artifacts(sha256 PK, job_id, path, bytes, produced_by, at)
envelopes(env_id PK, direction in|out, peer, kind, job_id, state, body, at)  -- idempotency on redelivery
ledger(seq PK, at, kind, job_id, actor, body JSON, prev_hash, hash)          -- append-only, hash-chained
heartbeat(id=1, at, pid)
escalations(esc_id, at, job_id, action, reason, state)                       -- Level C goes here, to Brandon
```

**Registry law, enforced in code.**
- `find(text)` only *reads* and returns job IDs.
- Every write goes through `transition(job_id, expected_state, new_state, expected_version)`. The write matches one
  deterministic ID and the version, is **read back in the same transaction**, and raises if the read-back differs.
- There is no write API that takes a pattern.
- SQLite triggers reject UPDATE and DELETE on `ledger` and `lineage`, and reject any state change on a
  `DONE-VERIFIED` row.

**States** (shown exactly as the WO names them): `QUEUED`, `RUNNING`, `BLOCKED-(reason)`, `DONE-VERIFIED`, `DEAD-LETTER`.

| From | To | When |
|---|---|---|
| QUEUED | RUNNING | scheduler, when `requires` is satisfied, `next_eligible_at` ≤ now, and WIP is under the cap |
| QUEUED | BLOCKED-(r) | a requirement can't be satisfied by the server: human gate, Level C, unmapped legacy path, no sandbox |
| BLOCKED-(r) | QUEUED | only with a Level B signed receipt (`unblock`) |
| RUNNING | DONE-VERIFIED | only when the deterministic verifier passes |
| RUNNING | QUEUED | failed or interrupted attempt with attempts left. Backoff = 60 s · 2^(n−1), capped at 1 h (deterministic, no jitter). |
| RUNNING or QUEUED | DEAD-LETTER | attempts exhausted (default 3). Surfaces on the board for Brandon, with the reason in plain words. |
| DEAD-LETTER | QUEUED | only with a Level B signed receipt (`requeue`); max_attempts is raised by exactly 1 |

**Lineage** (the NiFi provenance pattern without NiFi). Every mutation appends `(actor, transform, source,
input_sha256, output_sha256)`, where the SHA-256 is of the canonical job JSON before and after. Migrated jobs start
with `source = ghost/queue/<file>@sha256`. `provenance(job_id)` returns the full history in one call: the job,
lineage, attempts, artifacts, envelopes and ledger rows.

## 4. Doors (transport)

```
Door: name, kind ('direct' | 'http_proxy'), proxy_url, token_file (relays; read at call time, never logged)
  probe_trio() -> {github, nim, pip, healed: bool, latency_ms, error_class}
  request(method, url, body, deadline=5.0)
  breaker: CLOSED / OPEN(until) / HALF_OPEN
  stats: ring of the last 64 results -> p50/p95 latency, ok/err counts by class
         (timeout, refused, dns, tls, proxy_refused, http_4xx, http_5xx, rate_limited)
```

- **Trio legs** (all configurable in `config/doors.json`):
  - GitHub: `GET https://api.github.com/zen`, unauthenticated.
  - pip: `GET https://pypi.org/simple/pip/`; only the status and the first 64 KB are read.
  - NIM: one `max_tokens=1` completion to the configured NIM URL. The key is read from a 0600 file at call time.
- **Probe cadence:** at most every 10 minutes per door while healed, and on breaker half-open while unhealthy. That is
  about 6 GitHub calls an hour, far under the 60/h unauthenticated limit, and the NIM leg uses one token per probe.
- **ASSUMPTION for Zane to check:** the router on :18955 is an HTTP forward proxy (absolute-URI for `http`, CONNECT
  for `https`). Its source is not on GitHub. If it is something else, only `doors.py`'s `http_proxy` kind changes.

## 5. Commit gates: Platinum Authority Levels A, B and C

Every state-changing action passes `Gate.commit(action)`. The gate resolves three things:

1. **identity**: the OS user from `getuid()` for the local CLI, or the verified signer for envelopes;
2. **scope**: `config/policy.json`, mapping user → scopes;
3. **signed receipt**: an Ed25519 grant bound to `(action, job_id, principal)`, with a TTL of at most 300 s and a
   single-use nonce recorded in the DB.

| Level | Examples | Commit gate |
|---|---|---|
| **A** | probe, render the board, provenance, import legacy files, sandboxed CodeAct with no external effect, release an envelope into the local spool | identity and scope; ledgered |
| **B** | unblock, requeue, cancel, mark a manual job complete, forward an envelope to another host, install under a WO | identity, scope **and** a signed receipt; without `cryptography` installed, B fails closed |
| **C** | spend, publish, account creation, money movement, live trading, irreversible deletion | **no executor exists.** Refused in code, ledgered, escalated to Brandon. |

**Why Level C is structurally impossible, not just against policy:**
- `gates.EXECUTORS` is a frozen mapping of action kind → function, and it contains **no** Level C kind.
- `register_executor()` raises if given a Level C kind or a kind that matches the Level C classifier.
- The classifier runs on the *declared kind* **and** the job text (`spend`, `publish`, `payment`, `move money`,
  `purchase`, `create account`, `sign up`, `trade`, `wire`, `transfer funds`, `delete permanently`, …, a superset of
  the master runtime's `LEVEL_C_MARKERS`).
- A job classified C on intake becomes `BLOCKED-(level-c-brandon)`, and an escalation row and file are written for
  Brandon.
- Tests assert all four properties: the refusal, the ledger row, the escalation, and that registering a C executor
  raises.

**Policy classes** (Brandon's register, `war-room/POLICY-BASED-APPROVALS-2026-10-31.md`). Level B also accepts
one signed **class charter** in place of a per-item receipt:

- The charter is signed once by an owner key, covers whole register classes, lasts at most 180 days, and is revocable
  through `config/policy_revoked.json`.
- Each class has a **code ceiling** (`gates.CLASS_CEILING`). For GHOST, `ghost_operations` covers unblock, requeue,
  cancel, install, forward and complete. A charter can approve a class but can never widen its ceiling, and it can
  **never reach a fence**: Level C stays refused even when a charter names it.
- A kind that no register class covers is refused and escalated once as a `policy_question`, per the register's
  novel-class rule. It is never executed.
- Every action allowed under a charter is ledgered with `policy_class` and `charter_id`.

The grant format is byte-compatible with Genesis-core #12 (`{"payload": {v, issuer, action, mission_id, principal,
nonce, iat, exp}, "signature": b64}`); GHOST carries a `job_id` in the `mission_id` field. One owner keypair therefore
serves both Omega and GHOST, and the GHOST action names are disjoint from Omega's.

## 6. WIP governance (Little's Law) and the STEM scorecard

- **Caps.** Every lane has a concurrency cap (default **3**, Brandon's standing cap). There is also a global cap,
  default 3, matching `master-runtime/lanes.json` `wip_cap`. The scheduler never exceeds either. Lanes follow WO Part
  C: `builds, installs, probes, sends, proofs, batch-inference, ops`.
- **Metrics, computed live from `attempts` and `jobs` over a window (default 7 days):**
  - queue time = first RUNNING − created;
  - cycle time = DONE-VERIFIED − first RUNNING;
  - throughput λ = completions ÷ window;
  - mean WIP L = time-weighted count of RUNNING jobs;
  - **Little's Law cycle W = L ÷ λ**, printed next to the measured mean cycle time. When λ = 0 the board prints
    `undefined — 0 completions in window` rather than inventing a number.
- **Scorecard** (`board` as CLI text and a static HTML file):
  - jobs by state, and cycle/queue times;
  - door health, with trio results, breaker state and p95;
  - failure classes;
  - **POWER**: CPU seconds per attempt, plus the server's own RSS and CPU;
  - **MONEY**: LTV:CAC and Burn Multiple, computed only from `config/economics.json` inputs; with no inputs it
    prints `NOT COMPUTED — no revenue/CAC data`. Rule of 40 is **PARKED** until revenue exists;
  - OKR objectives per quarter from `config/okrs.json`. A key result shows a live value only when its metric is one
    the server measures; otherwise `UNMEASURED`.
- The board prints no `DONE`. `DONE-VERIFIED` shows as `VERIFIED — awaiting Brandon`, and grades follow Brandon's
  ladder.

## 7. CodeAct, envelopes, MCP and the daemon

### CodeAct (module 7)

- A job may carry a small Python script that chains several tools in one run. It runs as `python3 -I -S -B` in a
  fresh temp directory with:
  - a scrubbed environment;
  - rlimits: CPU 30 s, memory 512 MB, file size 16 MB, 64 open files;
  - a 60 s wall-clock limit, its own process group, and `PR_SET_PDEATHSIG`;
  - **no network**, via `unshare -rn` when the host supports unprivileged user namespaces. Without that, the job goes
    to `BLOCKED-(sandbox-no-netns)` unless the job explicitly declares network use, which makes it Level B.
- The script's own claims are ignored. The job counts only when its **fixed, deterministic verifier** passes. A
  verifier is one of:
  - `json_schema` on `out/result.json`;
  - `sha256` of a named artifact;
  - `argv`, a separate sandboxed test command that must exit 0;
  - `receipt`, a file at `receipt_target` that names the job ID; its hash is recorded;
  - `trio`, a door probe.
- There is no peer debate and no self-certification.

### A2A envelopes (module 8)

- Format `ghost-a2a/1`: `{id, kind task|result|ack, from, to, job_id, payload, payload_sha256, created_at, expires_at,
  nonce, sig}`, signed with Ed25519.
- **Store and forward:**
  - Outbound envelopes are written atomically (temp file, fsync, rename, fsync of the directory) into
    `spool/out/<peer>/`, then also recorded in the DB.
  - The file transport moves them through any directory the peer can read: a git mailbox (as
    `genesis-openclaw-mailbox` does today) or a relay.
  - Inbound envelopes are verified (signature, expiry, payload hash) and then applied **in the same transaction that
    records `env_id`**. A redelivered envelope is acknowledged and not applied twice.
  - They survive a dead network, because they are files, and a reboot, because they are files and DB rows.
- **MCP** (inside the runtime): a stdio JSON-RPC server exposing **read-only** tools: `ghost_status`,
  `ghost_provenance`, `ghost_board`, `ghost_doors`. MCP never mutates anything; mutations go through the gates. MCP
  and A2A are kept as separate layers.

### Daemon, recovery and evidence (module 9)

- **Daemon:** double fork (fork, setsid, fork), umask 077, a pidfile held with `flock` so a second instance refuses,
  stdio redirected to `state/ghostd.log`, and SIGTERM for a clean stop. Never bare `nohup`.
- **Boot recovery:**
  1. verify the ledger hash chain; a break refuses to start and writes `state/LEDGER_BROKEN`;
  2. write a `boot` ledger row whose `prev_hash` continues the chain;
  3. requeue jobs whose lease has expired, counting the attempt as `interrupted`.
- **Keepalive contract:** the heartbeat is refreshed every tick (≤ 60 s). `ghostd.py keepalive` exits 1 if the
  heartbeat is more than 300 s old, and with `--restart` it starts the daemon. It is meant for a `*/5` cron line on
  hosts that have cron.
- **Evidence ledger:** phases, gate decisions (allow and refuse), door state changes, drain events, boots and shutdowns
  are all ledgered. `ghostd.py ledger verify` re-hashes the whole chain.

## 8. Resource budget on zane-box (to be measured there and printed in the P1 receipt)

| Item | Budget | How it's held |
|---|---|---|
| Idle RSS | **≤ 40 MB** | standard library only; modules imported lazily (no `ssl` until a probe runs) |
| Idle CPU | **≤ 0.5 %** of one core | 5 s sleep tick; work only when due; no busy loops |
| Disk | ledger ≈ 0.3 KB per row; heartbeat ledgered every 5 min (about 90 KB/day) | WAL checkpoint on clean shutdown |
| Network | trio ≤ 6 rounds/h per door while healed; 0 while the breaker is open | breaker plus cadence |
| Processes | 1 server, plus at most WIP-cap CodeAct children | WIP cap; no uncontrolled spawning |

The cloud-container measurement is in the P1 receipt. **The zane-box measurement is owed to Zane** (acceptance item 6).

## 9. Open questions for the reviewer (Zane)

1. The egress router's protocol (the §4 assumption), and whether the router's source should be committed under
   `ghost/egress-router/`.
2. GHOST-Q-013…Q-016 are not on GitHub (`main` has Q-001…Q-012). The migration imports whatever is present. Please
   push the missing ones.
3. Does zane-box allow unprivileged user namespaces (`unshare -rn true`)? If not, CodeAct jobs stay BLOCKED unless
   they are declared Level B.
4. Is `cryptography` importable on zane-box? Without it, Level B and envelope signing fail closed, by design.
5. The legacy `requires_path` text → structured `requires` mapping is a reviewed, ID-keyed table
   (`config/legacy_requires.json`), not inferred from the text. Please confirm each row.

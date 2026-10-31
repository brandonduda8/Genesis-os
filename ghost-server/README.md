# GHOST SERVER v2

GHOST SERVER v2 is a store-and-forward operations server for the Genesis fleet. It is one process with one SQLite file,
uses only the Python standard library, and runs on Python 3.8 or newer.

- **Design:** [`DESIGN.md`](DESIGN.md)
- **Receipts:** `../war-room/RECEIPT-GHOST-SERVER-P{0..5}.md`
- **Queue entry:** GHOST-Q-017

**Grade: BUILT** (cloud-tested on branch `claude/ghost-server-v2`). It is **not LIVE on any host**. Zane verifies it on
zane-box, and Brandon certifies.

## What each module is

| # | Module | File |
|---|---|---|
| 1 | Durable job core: deterministic IDs, read-back writes, bounded retries, DEAD-LETTER | `ghost/registry.py` |
| 2 | Lineage on every record; `provenance <id>` returns the full history in one query | `ghost/registry.py` |
| 3 | Doors: one hard 5 s deadline, circuit breakers, per-door stats, **acceptance trio** heal signal | `ghost/doors.py` |
| 4 | Commit gates (Levels A, B, C); **Level C has no executor**; refusals are escalated to Brandon | `ghost/gates.py`, `ghost/signing.py` |
| 5 | WIP caps per lane (3) and globally (3); Little's Law W = L/λ computed live | `ghost/server.py`, `ghost/metrics.py` |
| 6 | STEM scorecard (CLI and static HTML); POWER, MONEY staged, OKRs; never prints DONE | `ghost/metrics.py` |
| 7 | CodeAct sandbox (no network, rlimits, PDEATHSIG) plus **deterministic verifiers only** | `ghost/codeact.py` |
| 8 | MCP (read-only, stdio) inside the runtime; signed A2A envelopes across machines, store-and-forward | `ghost/mcp.py`, `ghost/envelope.py` |
| 9 | Double-fork daemon, flock pidfile, boot recovery, keepalive contract, hash-chained evidence ledger | `ghost/server.py`, `ghost/registry.py` |

## Deploy notes (Zane review D2)

- **File modes.** `signing.py` refuses a group- or world-writable `config/trusted_keys.json`, by design. On hosts whose
  default umask is 002 (zane-box), deploy with `umask 022`, or run `chmod 644 config/trusted_keys.json`. Private keys
  are 0600.
- **Layout.** `ghost-server/` sits beside `ghost/queue/`, as in the genesis-os checkout. In a bare checkout, the 9
  tests that need the real queue **skip with a reason** instead of failing.
- **Legacy statuses.** Only the leading status word of a queue file is read. `QUEUED` and `DEAD-LETTER` import as
  themselves. Any other status (ACTIVE, DISCHARGED, P0 …) imports as `BLOCKED-(legacy-status-<word>-unverified)`,
  because nothing is DONE or ACTIVE just because a file says so. The full prose is kept in `spec.legacy_status`.

## Zane: verification on zane-box (GHOST-Q-017)

Run everything from `genesis-os/ghost-server`. Nothing below spends money, publishes, or touches :8888.

1. Run the full suite (42 tests). The output goes into the receipt.

   ```bash
   python3 -B -m unittest discover -s tests -t . -v
   ```

2. Check the two host facts the design depends on. The first must print `netns ok`; without it, CodeAct jobs stay
   BLOCKED. The second must print a version; without `cryptography`, Level B actions and envelopes fail closed.

   ```bash
   unshare -rn true && echo netns ok
   ```

   ```bash
   python3 -c "import cryptography; print(cryptography.__version__)"
   ```

3. Import the legacy queue. The files in `ghost/queue/` are read only and never edited.

   ```bash
   python3 ghostd.py migrate && python3 ghostd.py status
   ```

4. After the egress router is relaunched (§UP-GHOST step 1), run the acceptance trio through it. This also checks the
   DESIGN §4 assumption that the router is an HTTP forward proxy.

   ```bash
   python3 ghostd.py doors-probe
   ```

5. Start the daemon, wait 10 minutes, then record idle RSS and CPU in the P1 receipt (acceptance item 6).

   ```bash
   python3 ghostd.py start
   ```

   ```bash
   grep VmRSS /proc/$(cat state/ghostd.pid)/status
   ```

6. Restart survival on the real host (acceptance item 1): kill the daemon, start it again, and confirm the ledger is
   intact.

   ```bash
   kill -9 $(cat state/ghostd.pid); python3 ghostd.py start; python3 ghostd.py ledger-verify; python3 ghostd.py status
   ```

7. Keepalive. Add this cron line on hosts that have cron:

   ```
   */5 * * * * cd ~/workspace/genesis-os/ghost-server && python3 ghostd.py keepalive --restart >> state/keepalive.log 2>&1
   ```

8. Level C refusal on the host (acceptance item 3). It must exit 3 and write `state/escalations/ESC-*.json`.

   ```bash
   python3 ghostd.py gate spend GHOST-Q-002
   ```

## Keys

Without keys, the server stays fail-closed.

- **Manual jobs** are released as *signed* task envelopes. Until the server has an identity key, they stay QUEUED,
  shown as `no-signing-key`. To give it one:

  ```bash
  python3 ghostd.py keygen state/keys/zane-box.key
  ```

  Put each peer's public key into `config/trusted_keys.json` (see `config/trusted_keys.example.json`).
- **Level B actions** (unblock, requeue, cancel, complete) need a receipt signed by an owner key in the `owner` section,
  for example `owner:brandon`. The receipt is made on the signer's own device:

  ```bash
  python3 ghostd.py sign --key brandon.key --issuer owner:brandon --action ghost_unblock --job GHOST-Q-008 --principal os:zane
  ```

  It is valid for at most 300 s, and its nonce can be used once.
- **Policy classes, the tap-free path** (`war-room/POLICY-BASED-APPROVALS-2026-10-31.md`): Brandon signs **one**
  class charter on his own device. Every action inside that class then runs without a per-item tap, and fences stay
  refused:

  ```bash
  python3 ghostd.py charter-sign --key brandon.key --issuer owner:brandon --class ghost_operations --days 90 > config/policy_charter.json
  ```

  To revoke the charter, add its `charter_id` to `config/policy_revoked.json`, or delete the file.
- The receipt format is byte-compatible with Genesis-core's Omega grants, so one owner key could serve both. GHOST does
  **not** depend on Omega, which is not adopted (see Q-010).

**This branch provisions no keys.**

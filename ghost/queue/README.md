# GHOST JOB REGISTRY — the standing heal-window queue

One JSON file per job. This registry is the **seed of WO-GHOST-SERVER-001
Part C**: when the S1 NATS+JetStream pilot is promoted to the fleet job bus
(Phase 2), this registry is adopted **unchanged** — same schema, same job
IDs, same receipt obligations. The bus adds transport (durable streams,
at-least-once delivery, the mailbox/git fallback bridge); it does not
redefine the jobs. Until the bus exists, Zane works this registry by hand
under the same law, in the WO's heal-window priority order:
**F1 chain > owed proofs > installs > evals**.

## Schema

```json
{
  "id": "GHOST-Q-001",
  "title": "human-readable job name",
  "target_host": "s1 | penguin | zane-box",
  "requires_path": "what must probe GREEN before this job may run",
  "command_or_ref": "the exact command, runner, or governing document",
  "fence_notes": "the origin WO's fences, carried verbatim in spirit",
  "queued_at": "ISO-8601 UTC timestamp",
  "status": "QUEUED",
  "receipt_target": "genesis-os/war-room/RECEIPT-....md"
}
```

Field rules:

- **`requires_path` is mandatory.** A job that cannot state its path
  requirement does not enter the registry (WO Part C design law). Path
  requirements name a probeable thing: a host route (S1 SSH), a lane
  (NIM via :18791), a transport (any egress), or a human gate
  (`brandon-relay`, `brandon-tap`) — human gates are stated as plainly as
  network ones; a job blocked on Brandon is never disguised as a transport
  problem.
- **`fence_notes` travel with the job.** Queuing never authorizes (WO
  Part C: "No new authority"). Payloads carry their authority reference
  (WO + phase + go timestamp); whoever drains a job verifies that
  reference before acting. **Spend / account / publishing / money jobs do
  not exist in this registry** — those remain Brandon's taps (WO §6).
- **`status`** starts `QUEUED`. The only transitions are:
  `QUEUED → RUNNING → COMPLETED` (receipt written), `RUNNING → QUEUED`
  (failure — re-queued, failure recorded), `QUEUED|RUNNING →
  DEAD-LETTER` (attempt policy exhausted — surfaces on the daily board
  and Station app with the failure reason in plain words).

## How jobs enter

1. A WO, receipt, or plan identifies window-dependent work that cannot
   run now (dead path, lapsed session, missing upstream pack, Brandon
   gate). The identifying document is named in the job's source.
2. The job file is written here with a fresh `GHOST-Q-NNN` ID — never
   reused, never renumbered.
3. The entry is announced in the receipt that created it, listing the
   job ID and its source document. A job with no source document does
   not enter the registry.

## Drain law

1. **Probe before run.** A job runs only when its `requires_path` probes
   GREEN (the lane-health probes today; the Part A scoreboard once it
   exists). No attempts are burned into a path known to be down.
2. **Idempotency.** The registry/bus guarantees at-least-once delivery;
   the job guarantees exactly-once *effect* — installs check before
   installing, sends check before sending (existing dedupe), proofs are
   naturally idempotent.
3. **Receipt on completion.** Completion writes the job's
   `receipt_target` with the evidence the origin WO demands (proof
   artifacts, model fields, hash manifests, log excerpts as applicable),
   then flips `status` to `COMPLETED` in the job file, citing the
   receipt. A status flip without a receipt is invalid.
4. **Failure re-queues — never silently dropped.** A failed attempt
   records the attempt (timestamp + exact error) in the job file and
   returns the job to `QUEUED`, unless its attempt policy is exhausted,
   in which case it goes to DEAD-LETTER and becomes a Brandon-visible
   board entry. Work may fail; it may not fail silently in a log nobody
   reads.
5. **Grades stay honest.** A drained job's receipt grades on the ladder
   (IN BRANDON'S HANDS / LIVE ON A MACHINE / BUILT / STAGED / BLOCKED).
   Executor claims sit UNVERIFIED until Zane (or the named verifier)
   reads the receipt back and re-checks at least one artifact firsthand.

## The Part C lift (Phase 2)

When G-C.1/G-C.2 land: each registry file becomes a message on its lane's
JetStream stream (`builds`, `installs`, `probes`, `sends`,
`browser-jobs`, `proofs`, `batch-inference`) with the job's `id` as its
idempotency key and its `requires_path` as its release condition; the
G-C.5 watcher replaces the by-hand probe step. The git/mailbox bridge
(G-C.4) serializes these same files for nodes cut off from NATS. Nothing
about a job's content, fences, or receipt obligation changes in the lift —
files in this directory remain the human-readable mirror of the bus.

# RECEIPT — GHOST SERVER v2 · P0 Design note

**WO:** WO-CLAUDE-GHOST-SERVER-STEM-2026-10-31 · **Queue:** GHOST-Q-017 · **Builder:** Claude · **Reviewer:** Zane
(PENDING) · **Certifier:** Brandon · **Date:** 2026-10-31 · **Grade: BUILT**. Nothing is LIVE on a machine.

## Artifact

- `genesis-os/ghost-server/DESIGN.md` on branch `claude/ghost-server-v2`. Every file's hash is in
  `ghost-server/SHA256SUMS` at the branch head.

## What the design decides

1. **One server, not a parallel runtime.** It unites the existing parts:
   - the file queue becomes legacy input, imported by ID with each file's SHA-256 in lineage;
   - the egress router and relay packs become doors;
   - the master runtime's laws are enforced in code;
   - the NATS Part C lift stays possible, with job IDs and schema unchanged.
2. **No dependency on Genesis Omega.** Q-010 records the Oct 25 ruling that Omega is not adopted. Only the Ed25519
   grant *wire format* is shared, so one owner key could serve both if Brandon ever adopts it.
3. **Data model:** jobs, attempts, lineage, artifacts, envelopes, a hash-chained ledger, escalations, nonces and door
   state. SQLite triggers make the ledger and lineage append-only and freeze DONE-VERIFIED rows.
4. **Gate model, Levels A/B/C:**
   - Level A needs identity and scope.
   - Level B adds an Ed25519 signed receipt (TTL ≤ 300 s, single-use nonce).
   - **Level C has no executor**, and registering one raises. Refusals are ledgered and escalated to Brandon.
5. **Resource budget on zane-box:** RSS ≤ 40 MB and CPU ≤ 0.5 % idle; standard library only; one process plus at most
   the WIP cap of CodeAct children.

## Review-order note

The WO asks Zane to review the design before code. Brandon then told the builder to proceed on its own judgement. The
code was written on an isolated draft branch so the design can be reviewed **against running tests**. Nothing is merged
or deployed, and Zane can reject any section before merge.

## Open questions for Zane (DESIGN §9)

1. The router's protocol. The design assumes an HTTP forward proxy using CONNECT.
2. Q-013…Q-016 are not on GitHub.
3. Is `unshare -rn` available on zane-box?
4. Is `cryptography` available on zane-box?
5. Confirm each row of `config/legacy_requires.json`.

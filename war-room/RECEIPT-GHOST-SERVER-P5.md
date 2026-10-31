# RECEIPT — GHOST SERVER v2 · P5 Migration + drain proof

**Grade: BUILT.** Migration was run for real; the drain proof was run in the **LAB**. **The real heal-window drain on
zane-box is OWED to Zane.**

## Migration (real queue, cloud container)

- `python3 ghostd.py migrate` read `genesis-os/ghost/queue/` at `e622039` plus GHOST-Q-017, which this branch adds.
- Every legacy file was imported **by deterministic ID**: Q-001…Q-012 and Q-017.
- The files are untouched; a test compares directory hashes before and after.
- Each lineage source is `ghost/queue/<file>@sha256:<hash>@git:<blob>`.
- Results:
  - **10 QUEUED** on structured requirements (13 jobs in total, including Q-017, whose requirement list is empty so it releases to Zane as soon as the server runs).
  - **3 BLOCKED, each with its reason**:
    - Q-006: `human:relay-packs-landed`;
    - Q-008: `human:brandon-relay`; this is Brandon's hands, never dispatched;
    - Q-010: `human:brandon-home-decision`.
  - **0 classified Level C.**
- A re-run is idempotent: everything comes back `unchanged`.
- A hand-edited legacy file produces a `legacy_file_changed` lineage note, and the job's state is **not** overwritten
  (tested).

**Gap:** GHOST-Q-013…Q-016 are **not on GitHub**; `main` has Q-001…Q-012. They will be imported as soon as Zane pushes
them. Rows for them must be added to `config/legacy_requires.json` first, or they enter
`BLOCKED-(requires-unmapped)` by design.

## Drain proof (LAB): `tests/test_drain_restart.py::DrainThroughHealWindow`

Real sockets were used throughout. The "router" is the lab proxy, killed and healed on purpose.

1. **Network dead.** The egress door is DARK. **Nothing is released and no attempts are spent** (Q-002 attempts = 0).
2. **Heal.** The proxy comes back. After the breaker cool-down the trio returns HEALED, and the queue drains under the
   WIP caps: **Q-002 and Q-003 are released** as signed task envelopes into `spool/out/zane/`. Their fences travel in
   the payload, and the assignee checks GHOST's signature.
3. **Assignee completes.** Zane's side files `war-room/RECEIPT-…-LAB.md` naming GHOST-Q-002 and returns a signed
   `result` envelope. The deterministic `receipt` verifier passes, and **Q-002 becomes DONE-VERIFIED**.
4. **A result whose receipt does not name its job is rejected.** Q-003 falls back to QUEUED with bounded backoff.
5. **A redelivered result** is `duplicate-ignored`.

### Acceptance 4: lineage in one query

`provenance GHOST-Q-002` returns:
- lineage `legacy_import → attempt_start → artifact → verified`, with the first source pinned to the legacy file's
  hash;
- envelopes {out/task, in/result};
- 1 artifact (the receipt's SHA-256);
- ledger rows including `door_state` DARK→HEALED and `drain_released`;
- an intact chain.

## Verbatim test list (cloud container, Python 3.13.17; also OK on 3.12.3)

```
test_bounded_retries_with_backoff_then_dead_letter ... ok
test_db_file_is_private ... ok
test_done_verified_is_frozen_by_trigger ... ok
test_find_never_writes ... ok
test_ids_must_be_deterministic_and_never_reused ... ok
test_ledger_and_lineage_are_append_only_and_tamper_evident ... ok
test_provenance_returns_complete_history_in_one_call ... ok
test_recovery_requeues_expired_leases_as_counted_attempts ... ok
test_state_survives_reopen ... ok
test_transition_requires_expected_state_and_version ... ok
test_argv_verifier_is_a_separate_sandbox ... ok
test_multi_step_script_result_counts_only_via_verifier ... ok
test_no_network_inside_the_sandbox ... ok
test_scrubbed_env_and_resource_limits ... ok
test_self_certification_is_ignored ... ok
test_wall_clock_kill ... ok
test_429_is_a_hard_stop ... ok
test_dead_door_is_dark_and_breaker_opens_after_three_failures ... ok
test_healed_only_when_all_three_legs_pass_through_the_door ... ok
test_partial_is_never_healed ... ok
A connection that accepts and never answers once hung 15 s; the door must fail in <= 5 s. ... ok
test_stats_record_latency_and_error_classes ... ok
test_migrated_legacy_job_drains_end_to_end_through_a_heal_window ... ok
test_kill_9_and_restart_loses_nothing_and_keeps_the_ledger_continuous ... ok
test_signed_envelope_applies_once_even_when_redelivered ... ok
test_spool_survives_a_dead_network_and_reboot ... ok
test_tampered_forged_misaddressed_or_expired_are_quarantined_never_applied ... ok
test_unknown_peer_is_rejected ... ok
test_board_renders_live_numbers_and_never_asserts_done ... ok
test_littles_law_is_computed_from_real_attempt_history ... ok
test_read_only_tools_and_no_mutation_path ... ok
test_level_b_is_denied_when_signatures_cannot_be_checked ... ok
One owner key for both systems: the payload encoding is identical to Genesis-core authority._encode. ... ok
test_level_b_needs_valid_scoped_single_use_signature ... ok
Acceptance 3: a Level C-shaped action is refused in code, ledgered, and escalated to Brandon. ... ok
test_level_c_capability_does_not_exist ... ok
test_scope_is_required_even_with_a_signature ... ok
test_unknown_kinds_fail_closed_to_level_c ... ok
test_changed_legacy_file_is_noted_not_overwritten ... ok
test_lineage_source_pins_the_legacy_file_hash ... ok
test_migrates_every_legacy_job_read_only_and_idempotently ... ok
test_unmapped_ids_are_blocked_not_guessed ... ok
Ran 42 tests in 17.860s
OK
```

## Acceptance scoreboard

| # | Acceptance item | Status |
|---|---|---|
| 1 | Restart survival | **LAB PASS** (real `kill -9` and real daemon). The zane-box reboot is **OWED**. |
| 2 | Migrated job drains through a **real** heal window | **LAB PASS**. The real window is **OWED**: it needs the router relaunched and a door HEALED on zane-box. |
| 3 | Level C refusal, logged and escalated | **PASS** (cloud CLI log in P3, plus test). Host re-run **OWED**. |
| 4 | One query returns full lineage | **PASS** (real migration plus lab drain). |
| 5 | Board renders live numbers, including Little's Law | **PASS** (real registry; W undefined until the first completion, as it should be). |
| 6 | Idle RSS and CPU on zane-box | Cloud: **24.0 MB / 0.033 %**. zane-box numbers **OWED**. |

## Owed to Zane (independent verifier; GHOST-Q-017)

Run README §Zane steps 1–8 on zane-box, then append a "Zane verification" section here. It should contain the test
output, `netns` and `cryptography` facts, trio verdicts through :18955, idle RSS and CPU, the kill -9 restart, and the
Level C refusal. Then drain **one** migrated job (Q-002 or Q-003, which need `door:egress`) through a real heal window
and attach its `provenance` output.

**Fences held:**
- $0 spent.
- No money movement, publishing, accounts or trading.
- :8888 untouched.
- No keys provisioned.
- No service started on any host.

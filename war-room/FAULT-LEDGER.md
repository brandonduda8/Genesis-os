# FAULT LEDGER: the fleet's immune memory (WO-MASTER-TROUBLESHOOTER-001 §5)

<!-- NOT TRAINING DATA without review: this ledger names held-out incident IDs. A dataset builder that ingests
     war-room/ must exclude it, or re-check the held-out contamination guard. -->

**How to use it:**
- Read this file **at triage, before diagnosing anything**.
- A known fault links its row. A novel fault appends a new row.
- A repeat row for a fault that already has a fix and a prevention rule is a **process failure** (WO §1) and must say
  so.

**Grades:** VERIFIED (the fix was proven end to end and Zane re-checked it), UNVERIFIED, or UNKNOWN.

## Seeded from the WO Playbook (§4)

These are the fleet's proven faults. The grade is the evidence status at seeding, taken from the WO and the fleet
records, and was not re-probed by this seat.

| ID | Fault | Signature | Mechanism | Fix / path | Prevention | Evidence |
|---|---|---|---|---|---|---|
| FL-001 | Provider egress stall | CONNECT is accepted and the tunnel hangs; control hosts also return 000 | Provider proxy CONNECT stall (provider-owned) | Provider ticket (2026-10-26). Workaround: GHOST doors via the S1 and penguin relays; drains staged per the runbook | Acceptance-trio monitor; heal-window drain registry (GHOST v2 doors and trio, Genesis-os#1) | WO §4; GHOST-Q-002 and Q-003 requires_path |
| FL-002 | Tailnet data path dead | Peers listed active; tx grows and rx=0 on every peer | Usually riding FL-001 (DERP CONNECT stall) | State-preserving tailscaled stop+start. If rx stays 0, treat it as FL-001 | Fresh-probe law; never `reset` | WO §4; WO-OPENCODE-MASTER §2 ("Tailnet data path dead (proven 2026-10-30)") |
| FL-003 | Connector day-grant stall | Reads refuse with "query (day) connector grant" while status shows connected | Grant layer, fleet side; never isolated in the Q-014 record | Wait, then retry on grant refresh; route around via Takeout or mbox where one exists | Name the blocked slices as OWED, with exact re-runs | WO §4; GHOST-Q-014 investigation (dataset record GHOST-C-021, recorded UNKNOWN) |
| FL-004 | LiteLLM :4000 wedge | Port dark or returning 500s; the :4001 fallback is healthy | Startup wedged on the DB path (pg_tunnel :5433) through a stalled door | Restart the tunnel; the keepalive owns the lifecycle; the fallback serves meanwhile | Keep the fallback gateway live permanently | WO §4; RECEIPT-ACTIVATION-SWEEP-2026-10-31 §3 (dataset record GHOST-C-015) |
| FL-005 | Tool binary pruned | Dangling symlink; command not found | The storage governor or a prune job removed the install tree | Reinstall into `/home/hatch/agent-shelf` (prune-exempt) | All installs go to the shelf; storage-governor class rules | WO §4; GHOST-Q-002 and Q-003; held-out case GHOST-HELDOUT-005 (referenced by ID only) |
| FL-006 | Lane blackout, listeners up | lane_health shows every lane DOWN while the proxies are listening | Per-lane upstream (quota, key, proxy); a listener proves nothing | One real completion per lane; check the response's model field | lane_health probes must be transactions, not sockets | WO §4 |
| FL-007 | SSH config wiped | Host unknown, or config missing after a recycle | /tmp wiped by the recycle | Recreate from the fleet record (Q-022 pattern) | Config recreation scripted into the heal runbook | WO §2.1, §4 |
| FL-008 | Chromebook "unreachable" | SSH timeouts while the hub census shows LIVE | Own-side chain (FL-001, FL-002) until proven otherwise | Own-side repair. Penguin doze is the last hypothesis, and sleep is OFF by Brandon's order | Own-side-first doctrine | WO §2.1, §4 |
| FL-009 | NetBird session lapse | Peer expired; hub census stale | Session expiry | Brandon renews at the host, or a Phase B key deposit. **Running `netbird up` on a valid session churns it; warn first** | Expiry watch with a 24 h warning; the Phase B deposit is the durable fix | WO §4 |
| FL-010 | Shizuku down | Bridge probe reports SHIZUKU_DOWN | Shizuku is not running on the phone | Brandon starts Shizuku (his tap); no fleet-side fix exists | Report once, precisely; don't loop probes | WO §4 |
| FL-011 | Storage pressure | Free space falling; governor active | Disk use above the governor's ceiling | Governor class rules; the backup law (the Drive copy is complete AND the next snapshot is done before a tarball is freed) | 18 GB floor watch; 30-night permanence bar | WO §4 |

## Incidents worked under the protocol

| ID | Date | Fault | Signature | Mechanism (from evidence) | Fix | Prevention | Grade | Receipt |
|---|---|---|---|---|---|---|---|---|
| FL-012 (TS-001a) | 2026-10-31 | Dataset text field written as a list | `instruction` is a one-item JSON list in GHOST-C-019 (training split) and GHOST-HELDOUT-004 (frozen) | `ghost-v1/build_dataset.py` lines 153 and 168 built the value as `("…" f"…",)`. **The trailing comma makes a Python 1-tuple, which `json.dumps` writes as a list.** | Removed the two trailing commas. The frozen v1 bytes are **kept**, and the kernels normalise them in memory and log the IDs. | An AST test that fails if any builder puts a tuple in a text field; a schema test whose known-exceptions list may only shrink | **UNVERIFIED**: proven in tests (fail-before 2, pass-after 8). Zane still owes the fleet-side rebuild. | `RECEIPT-TS-001-DATASET-LIST-INSTRUCTIONS.md` |
| FL-013 (TS-001b) | 2026-10-31 | Frozen held-out set could be silently replaced | `held_path.write_text(...)` runs on every build, and the split is re-picked from inputs that change daily | The ACE and GHOST builders rewrite the frozen file unconditionally (a latent fault, found while working TS-001a) | `frozen_guard.write_heldout`: an identical rebuild is a no-op; any change is **refused** unless `--refreeze` is given (a version decision) | A test that every builder writing a held-out set goes through the guard; a test that frozen hashes still match their manifests | **UNVERIFIED**: tests pass. Zane still owes a fleet-side rebuild to see the guard fire. | same |

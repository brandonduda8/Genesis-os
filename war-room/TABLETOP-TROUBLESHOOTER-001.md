# TABLETOP — WO-MASTER-TROUBLESHOOTER-001 §7.2 (three historical incidents)

<!-- NOT TRAINING DATA: incident 2 is a frozen GHOST-QUAL-001 held-out case (GHOST-HELDOUT-005). It is referenced by
     ID only and never quoted. Dataset builders that ingest war-room/ must exclude this file. -->

**Holder:** Claude · **Verifier:** Zane · **Status:** prepared and **not yet verified**. Zane grades it, not me.

**Rules:**
- Every step comes from the WO's Playbook (§4), Doctrine (§2) or Protocol (§3).
- Every fact cites its record.
- Where the records available to this seat (GitHub `main` at `7f146a3`) don't show a value, the step says
  **UNKNOWN** and names the probe that would show it. **No step is invented.**

---

## Incident 1: the 2026-10-30 tailnet death

**Records:**
- WO-OPENCODE-MASTER §2: "Tailnet data path dead (proven 2026-10-30)".
- GHOST-Q-001, Q-005 and Q-011 `requires_path`: they wait on "zane-box tailnet data path … GREEN".
- Q-010: "S1 via Tailscale SOCKS = General SOCKS server failure; penguin full-cycle no answer".

| Move | Step | Source |
|---|---|---|
| Triage | **Fresh-probe first.** Don't reason from yesterday's peer list: zane-box recycles about 13 times a day. Read the per-peer counters now, then the ws-bridge and SOCKS listeners, then the serve-config read-back. **Write the signature down before touching anything.** | Doctrine 2; Playbook FL-002 first probes |
| Triage | **Scope the blast radius:** every peer (S1 and penguin) fails, and the SOCKS path to S1 fails. A failure across every peer points at a **systemic** own-side or egress cause, not at one device. Check the egress trio as well, because FL-001 is the usual carrier. | Protocol 1; Doctrine 1 (own side first); Q-010 record |
| Diagnose | Match against the Playbook. **FL-002: "peers listed active; tx grows, rx=0 on all peers."** The counter values from 10-30 aren't on GitHub, so whether rx=0 actually held is **UNKNOWN to this seat**. Probe it: per-peer rx/tx deltas over about 30 s. | Playbook FL-002 |
| Diagnose | Then read the DERP logs. **"200 Connection Established" followed by a hang** is the **provider proxy CONNECT stall (FL-001)**, not a tailnet fault. | Doctrine 4 (its own worked example) |
| Fix | **State-preserving `tailscaled` stop+start. Never `tailscale reset`**: a reset wipes auth state and turns this into a recovery that needs Brandon's hands. If rx stays 0 afterwards, the tailnet is riding FL-001, a provider-owned stall. Stop working the tailnet; there's no further fix at this layer. | Doctrine 5; Playbook FL-002 fix |
| Fix | Provider-owned path: track the ticket (2026-10-26) and **route around it legitimately**: GHOST doors through Brandon's own S1 and penguin relays (Q-006 installs them). Never circumvent the provider. | Doctrine 9; Playbook FL-001; §6 |
| Fix | NetBird is the other transport. Check session expiry **from the host itself** (FL-009). **Don't run `netbird up` on a valid session**, which churns it. Renewal is Brandon's tap, at the host. | Playbook FL-009 |
| Verify | **The consumer's transaction, not the peer list:** SSH to S1 answers (Q-001's own requirement), then penguin. A listed peer or an open SOCKS port proves nothing. | Doctrine 3; Protocol 4; Q-001 |
| Prevent | Acceptance-trio monitor plus the heal-window drain registry. GHOST v2 drains jobs that require `reach:s1` or `door:s1` the moment a probe goes green. Fresh-probe law; never reset. Ledger: FL-001 and FL-002. | Playbook prevention; Genesis-os#1 |

**Diagnosis:** the tailnet data path itself (FL-002) is most often carried by the provider egress stall (FL-001). Which
one applied on 10-30 can only be decided from that day's counters and DERP log signature, which aren't on GitHub. The
path above is how to decide it. No verdict is invented here.

---

## Incident 2: the OCE prune (frozen held-out case GHOST-HELDOUT-005, by ID only)

**Records:**
- GHOST-Q-003: "OpenContextEngine restore — one-command install resume into the shelf, keepalive start, :8986
  health…", requiring "any package egress GREEN".
- GHOST-Q-002: reinstall into the **prune-exempt** shelf.
- WO §2.6: the storage governor "ate OCE, Aider, OpenHands, Ruflo".

| Move | Step | Source |
|---|---|---|
| Triage | **The listener is not health.** :8986 being dark is the symptom. Run the keepalive once, read its log, and **write the signature down**. | Doctrine 3; Protocol 1 |
| Diagnose | Check the executable, not the process: does the CLI path resolve, or is it a **dangling symlink**, or "command not found"? That is Playbook **FL-005**'s signature. | Playbook FL-005 |
| Diagnose | **Check the deleter before mourning the deleted:** the storage governor and the prune jobs are suspects #1. Their deletions are **logged**, so read the governor log for the install tree. | Doctrine 6; Playbook FL-011 first probes |
| Fix | **Reinstall into `/home/hatch/agent-shelf`**, which is prune-exempt, not back into the pruned location. The reinstall needs package egress. While FL-001 is active it **cannot run**, so it waits as a queued job (Q-003, `door:egress`) and drains on the first heal window. It is **not** worked around. | Playbook FL-005; Doctrine 9; Q-003 requires_path |
| Verify | From the consumer's side: :8986 `/health`, **and** Q-003's own ground-truth proof retrieval (a real query returning the recorded answer). A started process is not the proof. | Doctrine 3; Q-003 command |
| Prevent | All installs go to the shelf, under the storage-governor class rules. Ledger: FL-005 linked to FL-011, with FL-001 as the blocker of the fix. | Playbook prevention |

**Diagnosis:** FL-005 (tool binary pruned), with the governor as the deleter. The fix is gated on FL-001 and queued,
not improvised.

---

## Incident 3: the 2026-10-31 connector grant stall (GHOST-Q-014's Gmail reads)

**Records:** dataset record GHOST-C-021 (training split), sourced from `ghost/queue/GHOST-Q-014-investigation.md`.
It shows two distinct error shapes: transport code-5 on search, and "query connector grant" on read. Meanwhile the
status check reports the account connected with read scope granted.

| Move | Step | Source |
|---|---|---|
| Triage | Run **the status check against one real read**. Status OK while the read refuses is the **FL-003** signature. Write both error shapes down verbatim. | Playbook FL-003 first probes; Protocol 1 |
| Diagnose | Matches **FL-003** for the reads. **But the record holds a second, different shape** (a transport code-5 on search), and the cause was never isolated. Naming one mechanism for both would be invention. The honest classification is **UNKNOWN**, with the missing evidence named: whether the search failure tracks FL-001 (probe egress at the same moment), and whether the grant refusal clears on the day-grant refresh. | Doctrine 4; dataset record GHOST-C-021 |
| Fix | Fleet side: **wait and retry on grant refresh**, one retry per refresh and never a loop. **Route around through the person's own export where one exists** (Takeout or mbox). That route is proven to work: Brandon's YouTube Takeout today replaced a connector read for the music taste profile. | Playbook FL-003 fix |
| Verify | A **read-back**: one real message read returns content. A "connected" status doesn't count. | Doctrine 3; Protocol 4 |
| Prevent | **Name each blocked slice as OWED, with its exact re-run command** (the corpus manifest pattern), so nothing is silently skipped. Ledger: FL-003. | Playbook FL-003 prevention |

**Diagnosis:** FL-003 for the read failures. The incident as a whole stays **UNKNOWN** until the two shapes are
separated by fresh probes, which matches how the fleet's own dataset records it.

---

## What Zane checks

1. Every step maps to a Playbook row, a Doctrine item or a Protocol move, and none was invented.
2. Nothing is asserted that the cited records don't show.
3. The UNKNOWNs are the right ones.

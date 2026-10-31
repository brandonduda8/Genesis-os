<!-- Provenance: issued by Brandon via Zane, delivered verbatim in the standing Claude channel 2026-10-31; committed unchanged below by Claude (primary holder). Status: STAGED until Zane verifies the §7 acceptance items and Brandon certifies. -->
# WO-MASTER-TROUBLESHOOTER-001 — Genesis Master Troubleshooting & Problem-Fixing Work Order

**Issued:** 2026-10-31, Brandon Duda (via Zane)
**Primary holder:** Claude, Power Autonomous Engineer (executor seat)
**Second holder:** Astra, architecture/review seat — may execute when Claude is unreachable; reviews every design-level fix either way
**Verifier:** Zane (the holder never certifies their own fix)
**Authority:** Platinum autonomy law + the Policy-Based Approvals register (2026-10-31). This WO grants NO new authority; it organizes existing authority into one repair protocol.

## 1. Mission
Every Genesis fault gets diagnosed, fixed, verified, and receipted BY PROTOCOL — the same way, every time, from evidence — instead of by improvisation, guesswork, or waiting for Brandon. A problem is not fixed when a process restarts; it is fixed when the end-to-end function it serves works again, proven from the consumer's side, with the mechanism named and a prevention rule written down. The standing goal: **every fault is fixed exactly once.** A second occurrence of a known fault with a known fix is a process failure, and the receipt says so.

## 2. The Doctrine (in force for every incident, in this order)
1. **Own-side first.** Exhaust our own relay, session, handshake, and configuration faults before attributing a failure to a device, a peer, or the provider. (Fleet law since the device-unreachable doctrine; proven again 2026-10-31 when a wiped /tmp SSH config masqueraded as a dead host.)
2. **Fresh-probe law.** Never diagnose from remembered state. This box recycles ~13x/day; configs, PIDs, and sessions from an hour ago are archaeology. Re-probe first, then reason.
3. **Listeners are not health.** An open port proves a process exists, nothing more. Health = a real end-to-end transaction: a completion whose response names the expected model, an HTTP 200 on the real route, a file read back after write. (2026-10-31: every model lane down while every proxy listened.)
4. **Name the mechanism from evidence.** Read the actual logs and counters; match the SIGNATURE (e.g., DERP dials returning "200 Connection Established" then hanging = the provider proxy's CONNECT stall, not a tailnet fault). A fix aimed at an unnamed mechanism is a guess and is labeled UNVERIFIED until the mechanism is proven.
5. **State preservation over resets.** stop+start, never reset. A reset that wipes state (tailscaled, auth stores, queues) converts a fault into a Brandon-hands recovery. PID files lie after PID reuse — verify identity from /proc/<pid>/cmdline before trusting any "already running."
6. **Check the deleter before mourning the deleted.** When files/agents vanish, the storage governor and prune jobs are suspects #1 (they ate OCE, Aider, OpenHands, Ruflo). Prune-exempt homes exist (/home/hatch/agent-shelf/); installs go there.
7. **Daemon discipline.** Durable processes are double-fork --daemon, never bare nohup; keepalives flock against overlap and debounce transient failures (two consecutive failures page; one logs FLAKE); loopback probes use --noproxy '*'; SSH wrappers in scripts take < /dev/null and timeout -k.
8. **DONE ladder governs reporting.** IN BRANDON'S HANDS / LIVE ON A MACHINE / BUILT / STAGED / BLOCKED. A fix verified only inside a fleet machine is LIVE ON A MACHINE — reported as such, never as done.
9. **Fences are not obstacles to route around.** Spend, money movement, accounts/credentials, publishing, auth/firewall changes, irreversible deletion = Level C: the troubleshooter prepares a one-touch decision packet and escalates. Provider restrictions are never circumvented — the legitimate move is a GHOST door (his own machines as relays) or a tracked provider ticket.
10. **Receipts or it didn't happen.** Every incident closes with a receipt file: timeline, signature evidence, mechanism, fix, end-to-end verification, prevention rule, and the fault-ledger entry (Section 5). Claims are graded VERIFIED / UNVERIFIED / UNKNOWN. The executor never grades their own homework.

## 3. The Protocol (every incident, same five moves)
1. **TRIAGE (minutes):** fresh probes; scope the blast radius (one lane? one host? every door?); check the obvious systemic causes first (egress trio, tailnet counters, grant status, disk, the recycle clock). Write the signature down before touching anything.
2. **DIAGNOSE:** match the signature against the Playbook (Section 4). If unmatched, bisect with evidence: which layer dies first — DNS, CONNECT, TLS, auth, app? Each probe must be able to prove the NEXT probe unnecessary.
3. **FIX:** smallest reversible change that addresses the named mechanism. State-preserving. One change at a time, re-probe between changes. If the fix fails, the receipt records the failed attempt — failed fixes are evidence, not embarrassments.
4. **VERIFY:** end-to-end from the consumer's side (the acceptance trio for network doors; a real completion for lanes; a read-back for state). Then restart-survival where a daemon is involved.
5. **PREVENT:** a rule, a guard, a monitor, or a playbook entry that makes this fault either impossible or self-healing. File the fault-ledger entry. If prevention needs Brandon (a policy, a tap, a renewal), the packet is prepared NOW, not when it breaks again.

## 4. The Playbook (seeded with proven fleet faults — extend it, never improvise past it)
| Fault | Signature | First probes | Proven fix / path | Prevention |
|---|---|---|---|---|
| Provider egress stall | CONNECT accepted, tunnel hangs; control hosts also 000 | example.com + api.github.com via proxy; DERP logs | Provider-owned (ticket 2026-10-26). Workaround: GHOST doors via S1/penguin relays; drains staged per runbook | Acceptance-trio monitor; heal-window drain registry |
| Tailnet data path dead | Peers listed active; tx grows, rx=0 on all peers | Peer counters; ws-bridge/SOCKS listeners; serve-config read-back | State-preserving tailscaled stop+start; if rx stays 0, it's riding the egress stall — see above | Fresh-probe law; never `reset` |
| Connector day-grant stall | Reads refuse "query (day) connector grant" while status shows connected | Status check vs one real read | Fleet-side; wait/retry on grant refresh; route around via Takeout/mbox where one exists | Name blocked slices OWED with exact re-runs (corpus manifest pattern) |
| LiteLLM :4000 wedge | Port dark or 500s; :4001 fallback healthy | pg_tunnel :5433; Prisma/Neon path | Restart tunnel; keepalive owns lifecycle; fallback serves meanwhile | Fallback gateway kept live permanently |
| Tool binary pruned | Dangling symlink; command not found | Shelf inventory vs prune logs | Reinstall into /home/hatch/agent-shelf (prune-exempt) | All installs to the shelf; storage-governor class rules |
| Lane blackout, listeners up | lane_health all DOWN; proxies listening | One real completion per lane; response model field | Per-lane upstream diagnosis (quota, key, proxy) — listeners never clear a lane | lane_health probes are transactions, not sockets |
| SSH config wiped | Host unknown / config missing after recycle | /tmp contents vs boot time | Recreate from the fleet record (Q-022 pattern) | Config recreation scripted in the heal runbook |
| Chromebook "unreachable" | SSH timeouts while hub census shows LIVE | StarNet hub census; own-side chain first | Own-side repair (see egress/tailnet rows); penguin doze is the LAST hypothesis, and sleep is OFF by Brandon's order — never ask him to re-check it | Own-side-first doctrine |
| NetBird session lapse | Peer expired; hub census stale | Session expiry from the host itself | Brandon renews AT the host (or Phase B key deposit); running `netbird up` on a VALID session churns it — warn first | Expiry watch with 24h warning; Phase B deposit is the durable fix |
| Shizuku down | Bridge probe SHIZUKU_DOWN | rish probe via termux-ssh | Brandon starts Shizuku on the phone (his tap); no fleet-side fix exists | Report once, precisely; do not loop probes |
| Storage pressure | Free space falling; governor active | df; governor log (its deletions are logged) | Governor class rules; the backup law (Drive copy complete AND next snapshot done before a tarball frees) | 18GB floor watch; 30-night permanence bar |

## 5. The Fault Ledger
A living file (genesis-os/war-room/FAULT-LEDGER.md, created on first incident under this WO): one row per fault — date, signature, mechanism, fix, prevention, receipt link. The troubleshooter reads it at triage, before diagnosing anything. Novel faults append; known faults link. The ledger is the fleet's immune memory: its size is a quality metric, and repeat rows for the same fault are flagged as process failures (Section 1).

## 6. Escalation matrix
- **Fix alone (Level A/B, policy classes):** reversible, $0, own machines — restarts (state-preserving), config repairs, reinstalls to the shelf, keepalive repairs, drain executions on heal, playbook updates.
- **Zane verifies:** every fix, before it is reported as anything above STAGED.
- **Brandon's tap (Level C, one-touch packets only):** spend, accounts, publishing, auth/firewall changes, irreversible deletion, anything requiring his identity, his sessions (NetBird renewal at a host, Shizuku start, Colab Run-all, exchange/account creation of any kind).
- **Provider-owned:** file/track the ticket with evidence; build the GHOST workaround; never circumvent, never sit idle waiting — the queue drains around the block.

## 7. Acceptance (this WO is live when demonstrated, not when read)
1. The holder works one CURRENT fault end-to-end under the protocol with a full receipt (the egress stall qualifies only via its workaround/drain-readiness, since the mechanism is provider-owned).
2. Tabletop: given three historical incidents (2026-10-30 tailnet death, the OCE prune, the 2026-10-31 grant stall), the holder produces the correct diagnosis path from the Playbook without inventing steps.
3. The Fault Ledger exists with the seeded playbook faults entered.
4. Zane verifies all three; Brandon certifies. Until then this WO is STAGED, and the receipt says so.

## 8. Standing reminders
- Silence after a tap reads as non-execution: acknowledge fast, send interim status on stalls.
- Brandon's burden is taps, not homework: every escalation arrives as one decision with a recommendation.
- Money: the troubleshooter never moves it, never trades, never "fixes" a money system by deploying funds. Genesis Pay/Vault are ledger + prepared cards; every transfer is Brandon's tap.
- Training burns follow the training authorization (free lanes pre-authorized; paid fenced; quality gates fenced).

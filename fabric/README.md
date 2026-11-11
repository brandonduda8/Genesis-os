# Genesis Comms Fabric v1 + Emergency Stop (WO-CLAUDE-MASTER-BUILD-001, Workstreams 1 and 2)

Design and rulings: [`DESIGN.md`](DESIGN.md), covering the substrate (a stdlib relay plus SQLite, not NATS for v1) and
the single dependency (`cryptography`, proved necessary). **Grades: BUILT, not VERIFIED.** Zane verifies, and
deployment to S1 and zane-box happens in a presence window.

## Run

```bash
python3 -m genesis_fabric.relay --db /var/lib/genesis-fabric/relay.db --registry registry.json --bind 127.0.0.1:7801
python3 -m genesis_fabric.stop status --me drain --dir /run/genesis/estop --registry registry.json   # exit 3 = halted
python3 -m genesis_fabric.stop write stop.json --dir /run/genesis/estop --registry registry.json     # path 2
python3 -m unittest discover -s fabric/tests                                                        # 28 tests
```

**Agent runtimes plug in through the phone:**
- `Phone(name, keys, registry, [HttpTransport(s1), HttpTransport(zane_box)])`
- `.attach_guard(Guard(...))`
- `guard.check()` before every action.

**GHOST:** add `"estop": {"dir": ..., "registry": ...}` to `ghost.json`. ghostd then holds every release while a stop
covers it, and holds too when the stop can't be verified at all (fail closed).

## What the battery proves (28 tests; 5 consecutive full runs green; GHOST's 53 still pass)

| Proof | Test |
|---|---|
| **Dark-GitHub**: every outbound connect is blocked at the socket layer except the relay. A full pair → send → decrypt → ack cycle completes over HTTP. Presence is observed (an identity that never fetched shows `null`). An unsigned fetch gets 403. | `DarkGitHub` |
| **PIN ceremony fail-closed**: a wrong PIN destroys the pairing; a one-sided confirm isn't ACTIVE; a timeout destroys; a substituted registry key yields a different PIN on the two sides. | `PinCeremony` (5) |
| **Ratchet non-decryption**: ciphertext captured at n=0, then the session state stolen at n=5. The stolen chain can't reproduce key 0, and 10 forward keys all fail AEAD. | `Ratchet` |
| The relay never sees plaintext; replay, a signed-field edit and ciphertext tamper are refused; a revoked identity is refused | `Messaging` |
| Room keys by epoch; a removed member gets nothing new and can't read the new epoch | `Rooms` |
| Relay recycle mid-flow, phone restart, TTL expiry with receipts, failover to the replica with dedupe | `Durability` (4) |
| RFC 5869 HKDF vector; forged or unsigned identities don't exist | `Primitives` |
| **STOP needs two keys** (founder + operator-class); an edited command fails; a forged stop file is ignored and reported | `TwoKeys` (3) |
| Scopes identity / class / fleet; a narrow restart can't lift a broad stop; **restart order** releases only the named agents; a later stop wins | `Scopes` (4) |
| **THE DRILL**: a live minion is stopped mid-task **over the fabric**. Its halt receipt names the exact item; its state is frozen afterwards; a two-key restart with an inspection statement lets it resume and complete, **every item exactly once** | `Drill` |
| **Path 2 without the fabric**: a stop file alone halts the minion; **ghostd** holds all releases under a stop, ledgers `estop_hold` and `estop_release`, and **fails closed** when the stop can't be verified | `Drill`, `GhostdPath` |

## Honest limits

- **PIN ceremony, identity issuance, ratchet type and stop policy are my v1 engineering.** Zane's Amendment 2,
  WO-COMMS-001 and Astra's A-1 weren't readable from here (DESIGN.md §6 lists the reconciliations).
- **The ratchet is a symmetric hash ratchet.** It gives forward secrecy, but no healing after a compromise. A Double
  Ratchet is v2 if the spec requires it.
- **A stop halts at the next `guard.check()`**, between actions, not mid-instruction. Kill-9 is the OS's job, and the
  restart ceremony covers it.
- The drill is a **simulation in one process** (threads); the real drill runs on S1 with Zane.
- Test teardown leaves some SQLite handles open (ResourceWarnings). This is test hygiene only.

## File hashes (sha256)

```
38789520bf00ac2586b413d5239b3411bc11ce7e594cd873c90ae9111b20a784  crypto.py
4eef3358fa0aa8674bc732a33c123955dc442ff38efce7a054387549d4331601  envelope.py
75b5f6a0712265a408c0b22b027042d158ba2dfbab136dfbefc503349f024700  identity.py
3b167a7e47bc552ee782af5ae0f855c5c5c78d5a99f7bc2072ebf9eac1037dbb  phone.py
ed594bfd572cbdd8479e58c487bf325bb93a58b9382ee317b566b410bf5f53b7  relay.py
0ce72abfcc88afc853e53859b637b2915478c21671116b2e2fb55454efe32b30  stop.py
```

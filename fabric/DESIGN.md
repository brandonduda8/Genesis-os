# Genesis Comms Fabric v1: engineering design note (WO-CLAUDE-MASTER-BUILD-001, Workstream 1)

**Author:** Claude. **Reviewer:** Astra. **Verifier:** Zane. **Status:** BUILT here; deployment rides a presence window.

**Inputs I could NOT read:**
- WO-COMMS-001;
- Amendment 2 (Zane's PIN Protocol);
- Astra's stop policy (A-1) and her A-2 package.

None of them is in any repo this session can reach (all branches of all 5 repos were searched on 2026-11-01). This
note engineers from the component list in the master WO itself. **§6 lists every place a reconciliation with those
texts is owed.** Where my design differs from Zane's, his is the spec and this note gets amended in the open.

## 1. The problem

On 2026-10-31 messages moved between rooms only because Brandon carried them. The fleet's existing "mailbox" is a
**git repo** (astra-zane-bridge), so when GitHub or a node's egress is dark, agents are deaf.

The fabric is the phone system: signed, end-to-end encrypted, durable, and independent of GitHub.

## 2. Substrate ruling: a stdlib relay service + SQLite (WAL). Not NATS for v1, not StarNet rooms.

| Criterion | NATS + JetStream | **stdlib relay + SQLite** | StarNet rooms |
|---|---|---|---|
| New dependencies on hosts | a Go server binary, config, an upgrade path | **none beyond Python 3.10+ and `cryptography` (§3)** | a 3.5 GB Node app |
| Durability across recycle or stall | JetStream file store (strong) | WAL + `synchronous=FULL`; acked delete only (tested: survives a close/reopen mid-flow) | not designed as a queue |
| Our scale (≈10–50 identities, ≈10³ msgs/day) | far above need | ample | n/a |
| Who can fix it at 3 a.m. | needs NATS expertise | the same patterns as GHOST (SQLite, systemd, Python) | upstream code we don't own |
| Fit with fleet law | a third shape to govern | **clones GHOST's governance pattern** | reconciliation decision #8: StarNet stays loopback and never forwards |

**Decision:** a stdlib relay for v1. The envelope format is transport-agnostic, so NATS remains the v2 path if
volume or multi-site fan-out ever outgrows SQLite; only the relay changes. The relay is **untrusted for content**:
it verifies signatures and stores ciphertext, and holds no key that decrypts anything.

## 3. Dependency ruling: exactly one, `cryptography`, and here is the proof it is necessary

The Python standard library has **no** Ed25519, X25519, ChaCha20-Poly1305 or AES-GCM. It has HMAC and SHA-256,
which is enough for HKDF and the ratchet. Writing curve or AEAD code by hand would mean unaudited cryptography, which
is the textbook way to fail.

`cryptography` (PyCA, Apache-2.0/BSD) is the audited standard, and GHOST already depends on it for its Ed25519
grants. Without it the fabric **fails closed**: it refuses to start, and nothing is sent in clear. HKDF (RFC 5869)
and the hash ratchet are implemented over stdlib `hmac` (≈25 lines, tested against the RFC 5869 test vector).

## 4. Architecture

```
 agent runtime ──(client kit: "the phone")──┐       ┌── relay S1 (primary)     SQLite WAL queue
   keys: Ed25519 (sign) + X25519 (pair)     ├─send─►│                          verifies sigs, stores ciphertext
   sessions: per-peer ratchets, room keys   │       └── relay zane-box (replica) same code, independent DB
                                            └─fetch/ack (signed requests; dedupe by envelope id)
 identity registry: JSON records, each signed by the FOUNDER key, naming the GHOST charter id (charter-backed)
```

- **Identity:** `{name, class, ed25519_pub, x25519_pub, charter_id, issued, expires}`, signed by the founder key.
  - It is revocable: a founder-signed revocation list is checked on every verify.
  - No founder signature means no identity: the relay and all clients refuse it.
- **Envelope:** `{v, id, from, to, ts, kind, hdr, ct, sig}`.
  - `sig` is the sender's Ed25519 signature over everything else, canonically encoded.
  - Verification checks: the identity is known and unrevoked; the signature is valid; the clock skew is at most
    300 s; `(from, id)` hasn't been seen (replay refused).
- **Pairing + PIN ceremony:**
  - X25519 static-static DH, then `HKDF(salt = names sorted, info = "genesis-fabric/pair/v1")` gives the root.
  - Both sides derive a 6-digit **PIN** = `HKDF(root, info = "pin")`, and the two humans or operators compare it
    out-of-band.
  - The pairing becomes ACTIVE only when **both** sides confirm the PIN they saw. One wrong PIN, or a timeout,
    **destroys** the pending pairing (fail-closed). A session that isn't ACTIVE cannot send or decrypt.
- **Ratchet** (per direction, a symmetric hash ratchet):
  - `ck0 = HKDF(root, "chain:A>B")`; for each message, `mk = HMAC(ck, 0x01)` and `ck = HMAC(ck, 0x02)`, and the old
    `ck` and `mk` are **erased**.
  - **Captured ciphertext can't be decrypted from a later state** (forward secrecy within the chain; tested).
  - Out-of-order arrival: skipped keys are cached, at most 64, each used once.
  - AEAD: ChaCha20-Poly1305(mk), with the nonce from the counter and **AAD = the signed header**, so ciphertext can't be
    moved to another envelope.
- **Rooms:**
  - The owner makes a 32-byte room key per **epoch** and sends it to each member over their pairwise session.
  - Message key = `HKDF(room_key[epoch], salt = envelope id)`.
  - Removing a member bumps the epoch, and the removed member can't read the new epoch (tested).
- **Store-and-forward:**
  - The relay's queue row is deleted only after the recipient's **signed ack**, so a crash before the ack means
    redelivery, and clients dedupe by id.
  - TTL is 7 days. Expiry writes an `expired` receipt row and never drops silently.
- **Presence:** the relay reports `last_fetch` per identity. Presence is **observed** (the age of the last signed
  fetch), never declared. That is the fresh-probe law.
- **Multi-relay, and why GitHub can go dark:**
  - The client kit takes an ordered relay list. It sends to every reachable relay and fetches from each.
  - Dedupe by envelope id means a replica is free redundancy.
  - **No GitHub anywhere in the path.**
- **Transport:** HTTP/1.1 JSON (stdlib `http.server`) bound to loopback or the tailnet address.
  - Every request is authenticated by an Ed25519 signature over `method|path|ts|sha256(body)`.
  - No passwords and no bearer tokens to leak.

## 5. Acceptance battery (simulation, in `tests/`)

1. **Dark-GitHub:** all outbound connections except the relay are refused at the socket layer, and a full pair → send
   → fetch → decrypt → ack cycle completes.
2. **PIN ceremony fail-closed:** a wrong PIN, a one-sided confirm, or a timeout leaves no usable session, and
   send/decrypt raise errors.
3. **Ratchet non-decryption:** an attacker who captured ciphertext n=1 and later steals the session state at n=5
   cannot decrypt n=1; tampered ciphertext or header fails AEAD.

Plus: an unregistered or revoked identity is refused, replay is refused, the relay survives close/reopen with the
messages intact, failover to the replica works, a removed member is locked out of a room, and the HKDF RFC vector
passes.

## 6. Owed reconciliations (corrections in the open)

| Item | My v1 choice | Reconcile with |
|---|---|---|
| PIN ceremony | a 6-digit SAS from the pairing root, mutual confirm, any mismatch destroys the pairing | **Zane's Amendment 2** (the PIN Protocol): his text is the spec |
| Identity issuance | the founder key signs every identity record | WO-COMMS-001; Astra's A-1 key policy |
| The STOP kind | carried by this fabric (Workstream 2), and also by a second path that doesn't depend on the fabric | Astra's A-1 stop policy |
| Ratchet | a symmetric hash ratchet per direction (forward secrecy; no post-compromise healing) | WO-COMMS-001. A DH ratchet (Double Ratchet) is the v2 path if the spec requires healing after compromise. |

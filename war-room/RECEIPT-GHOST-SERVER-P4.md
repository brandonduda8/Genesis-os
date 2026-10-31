# RECEIPT — GHOST SERVER v2 · P4 CodeAct + protocol stratification (modules 7–8)

**Grade: BUILT** (cloud container). **zane-box netns check: OWED** (README §Zane step 2).

**Files:** `ghost/codeact.py`, `ghost/envelope.py`, `ghost/mcp.py`

## Module 7: CodeAct

**How a script runs:** a job's script does a multi-step chain in one execution, as
`python3 -I -S -B script.py` in a fresh temp directory, with:
- a scrubbed environment (a canary secret in the parent environment is absent in the child; tested);
- rlimits: CPU 30 s, memory 512 MB (a 1 GB allocation fails; tested), file size 16 MB, 64 open files, no core dumps;
- its own process group, a 60 s wall-clock kill (tested), and PR_SET_PDEATHSIG;
- **no network**, via `unshare -rn`. A test shows an outbound connection is refused inside the sandbox. If the host
  lacks unprivileged user namespaces, the job goes to `BLOCKED-(sandbox-no-netns)` (fail closed).

**When a result counts:** only when the job's **fixed, deterministic verifier** passes. The verifier kinds are:
- `json_schema`;
- `sha256` of an artifact;
- `argv`, a separate sandbox that receives copies of the outputs;
- `receipt`, a file inside the receipts root that names the job ID, with its hash recorded;
- `trio`.

Unknown kinds, including `peer_debate`, fail. A script that writes `{"ok": true, "verified": true}` and prints "ALL
TESTS PASSED" while its answer is wrong is **rejected** (`test_self_certification_is_ignored`).

## Module 8: protocol stratification

- **MCP (inside the runtime):** stdio JSON-RPC 2.0 with five tools, all annotated `readOnlyHint`. A test calls a
  non-existent mutating tool, gets an error, and confirms `total_changes` is unchanged. There is no write path through
  MCP.
- **A2A envelopes (across machines):** `ghost-a2a/1`, signed with Ed25519 against pinned peer public keys.
  - Written atomically (temp file, fsync, rename, fsync of the directory) into `spool/out/<peer>/` with mode 0600.
  - Inbound envelopes are recorded and applied **in one transaction**.

| Test | Result |
|---|---|
| Redelivery (mailbox duplicate after a reboot) | `duplicate-ignored`; applied exactly once |
| Payload tampered, hash tampered, misaddressed, signature swapped, expired | all 5 **quarantined**; 0 applied |
| Unknown peer | quarantined |
| Spool across a registry "reboot" | the pending envelope persists with the same ID |
| An apply that raises | rolled back and quarantined; never retried in a loop |

## Cloud container facts

| Check | Result |
|---|---|
| `unshare -rn true` | works, so `netns_available()` is True |
| `cryptography` | 50.0.1 |

Both are unverified for zane-box.

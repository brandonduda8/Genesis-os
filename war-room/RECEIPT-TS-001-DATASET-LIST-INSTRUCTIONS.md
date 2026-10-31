# RECEIPT TS-001: list-shaped dataset instructions, and an unguarded frozen held-out write

**WO:** WO-MASTER-TROUBLESHOOTER-001 (acceptance item 1: one current fault, end to end) · **Holder/executor:**
Claude · **Verifier:** Zane · **Certifier:** Brandon · **Class:** Engineering (Level A: code, tests, docs) ·
**Ledger:** FL-012, FL-013

**Grade: BUILT** (a fix plus prevention, proven in tests). **Not VERIFIED**: Zane has not re-checked it, and the fleet-side rebuild is owed.

## Timeline (UTC, 2026-10-31)

- **~21:15** Signature first seen while dry-running the new training kernels (Genesis-os#4): `AttributeError: 'list'
  object has no attribute 'split'` in the kernel's contamination check.
- **~21:16** Recorded the signature before touching anything. Two `ghost-v1` records have `instruction` as a JSON
  list: **GHOST-C-019** (training) and **GHOST-HELDOUT-004** (frozen held-out set).
- **~21:18** Mitigated on the consumer side so the kernels could proceed. They join a list in memory and log the IDs;
  any other non-string type aborts the run. **No dataset file was touched** (state preservation, doctrine 5).
- **~21:45** Started this incident under the protocol.

## 1. Triage

- **Fresh probe** (doctrine 2): I re-read the files from `origin/main` at `7f146a3` and didn't rely on the earlier
  session.
- **Blast radius**, scanned across all dataset files:
  - exactly **3 occurrences** in `ghost-v1`: C-019 appears in both `cases_train.jsonl` and the merged
    `ghost-v1.jsonl`, plus HELDOUT-004;
  - 0 occurrences in `ace-v1` and `cody-v1`;
  - an AST scan of all three builders found **2 sites**, both in `ghost-v1/build_dataset.py`.
- **Systemic causes checked:** not applicable. This is a code fault, not a transport one; no door, lane or disk is
  involved.

## 2. Diagnose: the mechanism, named from evidence

```python
# ghost-v1/build_dataset.py line 153 (and line 168, same shape)
'instruction': ("GHOST state reading. penguin_keepalive.json records: "
                f"... What failure class caused the recorded down period?",
                ),        # <- the trailing comma makes a 1-tuple
```

A parenthesised expression with a trailing comma is a **tuple**, and `json.dumps` serialises a tuple as a JSON
**list**. Both sites are the two UNKNOWN `state_read` cases, which matches the bad records exactly. **No other
mechanism is needed to explain the evidence.**

**A latent fault found during diagnosis:** both the ACE and GHOST builders call `held_path.write_text(...)` on every
run, and they re-pick the held-out split from fleet inputs that change daily. One routine re-run of a fixed builder
would therefore **silently replace a frozen battery**, which voids it. This is recorded as a separate ledger row,
FL-013.

## 3. Fix: the smallest reversible change, one change at a time

1. **Mechanism (FL-012):** removed the two trailing commas. That is 2 lines in `ghost-v1/build_dataset.py`.
2. **Latent fault (FL-013):**
   - new `training/datasets/frozen_guard.py`, with `write_heldout(path, text, frozen_sha256)`:
     - an identical rebuild is a no-op;
     - a change to a frozen file **raises and leaves the file untouched**;
     - `--refreeze` is the only override, and it is a version decision.
   - Both builders now call it, with their manifest freeze hash as a constant.
3. **Not changed, deliberately:** the frozen `ghost-heldout-v1.jsonl` keeps its v1 bytes and its hash
   (`74d68f53…8f2a`), including HELDOUT-004's list. Re-freezing is a version decision for Zane, the dataset owner. The
   kernels already normalise the shape and log it.

## 4. Verify: from the consumer's side, as far as this seat can reach

| Check | Result |
|---|---|
| `training/datasets/tests/test_builders.py` on the **fixed** tree | **8 OK** |
| The same tests on **main's builders** (fail-before) | **2 FAIL**: the tuple scan and the guard wiring |
| Frozen held-out hashes vs the manifests | both still match, and a test asserts it |
| Consumer: the training kernels (Genesis-os#4) | dry-run OK; the logged normalisation IDs are exactly `GHOST-C-019`, `GHOST-HELDOUT-004` |
| Builders still parse after the edit | yes, all three |

**Not verifiable from here:** re-running the builders. They read fleet state (`/home/hatch/workspace/genesis-os/state/*`,
the queue and receipts) that isn't on GitHub. **Owed to Zane on zane-box:**
1. Run `python3 training/datasets/ghost-v1/build_dataset.py`. The guard should **refuse**: the fixed builder would
   change HELDOUT-004's shape, and the daily-changing inputs may move the split.
2. Choose either:
   - (a) keep v1 frozen and rebuild only once the builder can skip the held-out write, or
   - (b) `--refreeze` as **ghost-v1.1**, with the new hash recorded in the MANIFEST and in the kernel builder's
     `heldout_sha256`.

   **Recommendation: (b).** v1.1 makes HELDOUT-004 a string, removes C-019's list, and lets the `KNOWN_V1` exception
   list in the test shrink to zero.

## 5. Prevent

- **AST guard:** a test fails if any builder writes a tuple into `instruction`, `response`, `text`, `detail` or
  `source`.
- **Schema guard:** a test fails on any new non-string text field in any dataset file. The `KNOWN_V1` exceptions may
  only shrink.
- **Freeze guard:** every builder that writes a held-out set must go through `write_heldout`, enforced by a test, and
  frozen hashes must keep matching their manifests.
- **Ledger:** FL-012 and FL-013 are filed. A repeat of either is a process failure.
- **Nothing needs Brandon.** This is all Level A, $0, inside the Engineering class.

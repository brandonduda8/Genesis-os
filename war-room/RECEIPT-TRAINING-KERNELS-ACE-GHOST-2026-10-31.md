# RECEIPT — Training kernels for ACE (row #9) and GHOST (row #10), plus the base head-to-head

**Builder:** Claude (Power Autonomous Engineer, GHOST-Q-018, assignment 2) · **Verifier:** Zane · **Certifier:**
Brandon · **Class:** Training (Brandon's register: free lanes, tap-free; quality gates bind)

**Grade: BUILT.** Every kernel passed a dry run on CPU. **Nothing was launched.** No GPU minute was spent from this
seat: the training autopilot launches on zane-box.

## Why now

As of the 19:19Z autopilot pass, **29.21 GPU-h and 20.00 TPU-h expire at 2026-11-07T00:00Z**. Nothing was launched
because no row was launch-ready. Rows #9 and #10 had datasets but no kernels.

## What was built (`training/kernels/`)

| File | Role |
|---|---|
| `DESIGN.md` | P0 design note |
| `templates/lora_kernel.py` | One template with two modes, `train` and `h2h` |
| `common/scoring.py` | Mechanical Part A scoring: GHOST class exact-match, the restraint bar (no fault on NONE) and the UNKNOWN law; ACE verdict exact-match |
| `common/build_kernel.py` | Embeds the hash-gated datasets into self-contained `main.py` files. **It refuses to build** if a held-out hash differs from its manifest. |
| `build/{ghost,ace}-lora-v1/` | QLoRA training. Part A runs on the frozen held-out set: **the base model answers first and its outputs are sealed**, then training, then the tuned model answers. |
| `build/{ghost,ace}-h2h-v1/` | Ranks the untuned candidate bases on **training-split prompts only**. Choosing a base on the held-out set and then testing on it would be selection bias. |
| `build/BUILD.json` | The hash of each generated `main.py`, guarded by a staleness test |

**Every run outputs:**
- `run_manifest.json`: an event log, pins, file hashes and losses;
- the base and tuned answers, each sealed with a SHA-256;
- `adapter/`, with per-file hashes;
- `partA_report.json`, whose status is **"PART-A-EVIDENCE-ONLY — not a battery verdict"**.

**Pins:** `transformers==4.56.2` (the fleet pin), `peft==0.13.2`, `accelerate==1.1.1`, `bitsandbytes>=0.45.0`, 4-bit
NF4 with fp16 compute (the T4 has no bf16), and `enable_internet: true`.

## Evidence (this container: CPU, Python 3.13, torch from PyPI, transformers 4.56.2, peft 0.13.2)

**`tests/test_kernels.py`: 11 tests, all OK.** Without the ML stack: 9 run and 2 skip, each with a reason.

- **Scoring:**
  - all ground truths parse (GHOST held-out: 4 NONE, 1 FAULT, 1 UNKNOWN);
  - perfect answers score 1.0;
  - prose with no contract line scores 0;
  - answering FAULT on a NONE case is flagged (4 restraint violations), and a class on the UNKNOWN case is flagged as a
    fabrication event.
- **Abort paths:** a tampered embedded file aborts with a `hash` reason, and a held-out record leaking into the corpus
  aborts with `contamination`. Both abort **before any pip install or model load**, because both tests pass without
  the ML stack.
- **Build refusal:** a held-out hash that doesn't match its manifest makes the builder refuse.
- **Dry runs of the BUILT `main.py`:** a tiny random Llama with a tokenizer trained locally, on CPU.

| Kernel | Event order | Time |
|---|---|---|
| ghost-lora-v1 | `data_verified → base_sealed → trained → tuned_sealed → done` | 9.3 s |
| ace-lora-v1 | same | 19.2 s; 17 Part A cases |
| ghost-h2h-v1 / ace-h2h-v1 | ranked 3 candidates each; **no held-out ID appears in any h2h output** | 50.7 s (ACE) |

  The base seal hash equals the file hash, and the adapter files are hashed.
- **Staleness guard:** `build/*/main.py` must match a fresh build, byte for byte.

**Limits:** a dry run proves the mechanics: data, gates, sealing, training steps, generation, scoring and the
artifact layout. It does **not** prove model quality, or that bitsandbytes and HF downloads work on Kaggle's image.
That is the autopilot's first real launch.

## Dataset defect found (for Zane, the dataset builder)

`ghost-v1` has **two records whose `instruction` is a one-item list instead of a string:**
- **GHOST-C-019**, in the training split (the penguin keepalive UNKNOWN case);
- **GHOST-HELDOUT-004**, in the **frozen held-out set** (the lane_health UNKNOWN case).

Both are UNKNOWN honesty cases, so the bug likely sits in one `build_dataset.py` branch.

The kernels **do not edit** the hash-gated files. They join a list of strings in memory and record exactly which IDs
they changed in `run_manifest.json` (`normalized_list_instructions`). Any other non-string shape aborts the run.

Recommended fix: correct the builder. Any re-freeze of the held-out set is a new version with a new hash, and is
Zane's call.

## Launch order for the autopilot (proposed; QUEUE.md rows are the autopilot's to edit)

1. **`ghost-h2h-v1`, then `ace-h2h-v1`**, about 1–2 GPU-h in total. Each `h2h_report.json` names that line's winning
   base.
2. Rebuild the train kernels with the winners:

   ```bash
   python3 training/kernels/common/build_kernel.py --name ghost-lora-v1 --base <winner>
   ```

   Then commit the result.
3. **`ghost-lora-v1`, then `ace-lora-v1`**, about 1–2 GPU-h. They produce adapters and Part A evidence.
4. **Battery Parts B and C** (fresh incidents and the mandatory honesty cases) must be authored by **someone other
   than me**, the builder. The spec requires independence; I propose Astra as author and Zane as verifier. After that
   comes the blind rubric. Only then does a QUAL verdict exist.

This plan uses about 2–4 of the 29 expiring GPU-hours. The TPU/JAX stages designed in the manifests (20 TPU-h) are
the next build.

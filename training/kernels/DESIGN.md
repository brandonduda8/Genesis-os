# Training kernels for ACE (row #9), GHOST (row #10) and the base head-to-head: design note (P0)

**Author:** Claude (Power Autonomous Engineer, GHOST-Q-018; assignment 2) · **Verifier:** Zane · **Certifier:**
Brandon · **Status:** P0 plus BUILT kernels, dry-run tested on CPU. **Nothing launched**: launching is the training
autopilot's job on zane-box, under the Training class of Brandon's register.

## 1. The problem, measured (from `training/QUEUE.md`, 2026-10-31 19:19Z autopilot pass)

- About **29.21 GPU-h and 20.00 TPU-h expire at 2026-11-07T00:00Z**. The autopilot launched nothing, because no row is
  STAGED-and-launch-ready.
- Rows #9 (ACE) and #10 (GHOST) have their datasets **built and frozen**, but no kernel exists.
- Cody (#8) needs a base-model head-to-head first.
- Building these kernels is the step that turns expiring quota into evidence (doctrine §3.5).

## 2. What gets built (one template, three uses)

`kernels/common/build_kernel.py` generates self-contained Kaggle kernel directories from one tested template,
`kernels/templates/lora_kernel.py`:

| Kernel | Mode | What it does | Est. T4 burn |
|---|---|---|---|
| `ghost-lora-v1` | `train` | QLoRA on `ghost-v1.jsonl` (30 records). Then Part A (6 frozen cases): **base first, sealed**, then tuned. Mechanical Part A scores. | ~0.3–0.6 h |
| `ace-lora-v1` | `train` | QLoRA on `ace-v1.jsonl` (175 records). Then Part A (17 frozen): base sealed, then tuned. Mechanical scores. | ~0.6–1.2 h |
| `base-h2h-v1` | `h2h` | Untuned candidate bases on **training-split prompts only** (GHOST cases, ACE verdicts). Mechanical class/verdict accuracy picks each line's base. | ~1–2 h |

**Why the base is chosen on the training split, never the held-out set:** choosing on the frozen Part A and then
grading the tuned model on the same Part A is selection bias on the test set. The held-out sets stay untouched until
the real battery.

## 3. Kernel law (each item enforced in code, and tested)

1. **Embedded, hash-gated data.** The corpus and held-out files are embedded (gzip + base64), each with its SHA-256.
   On start, every file is decoded and re-hashed, and a mismatch **aborts** the run. The held-out hashes must equal
   the manifests' (`74d68f53…8f2a` GHOST, `23452d59…c632` ACE), otherwise the battery is void.
2. **No contamination.** Before training, the kernel asserts that **no held-out instruction appears in the training
   corpus**. An overlap aborts the run.
3. **Identical conditions; base first, then sealed.** One prompt format, one greedy decode, one token cap for both
   models. The base outputs are written and SHA-256-sealed **before** training starts. The tuned run comes after.
4. **Mechanical scoring only** (`common/scoring.py`):
   - class exact-match (GHOST) and verdict exact-match (ACE) against the recorded responses;
   - GHOST's restraint bar: no fault class on a recorded NONE;
   - GHOST's UNKNOWN law on underdetermined cases.

   The kernel reports **Part A evidence, not a battery verdict.**
5. **Independence is kept.**
   - I build the kernels and the mechanical scorer.
   - **Parts B and C** (the fresh incident sketches and the mandatory honesty cases) are authored by someone who is
     **not** the LoRA builder. The battery specs require this. Proposed: Astra authors, and Zane verifies.
   - The kernels accept those cases later as a separate `cases_bc.jsonl`, using the same record shape.
6. **Pins and lane.**
   - `transformers==4.56.2` (the fleet pin), `peft==0.13.2`, plus `bitsandbytes` and `accelerate`.
   - Kaggle T4, never P100, which is the sm_60 trap.
   - `enable_internet: true`, needed for pip and model downloads.
   - One GPU job at a time, as `AUTOPILOT.md` specifies.
7. **Outputs.**
   - `adapter/`, with a SHA-256 of every file.
   - `base_partA.jsonl` and `tuned_partA.jsonl`, each with its seal hash.
   - `partA_report.json`, with per-item results plus a `status` that never says PASS for the battery.
   - `run_manifest.json`, with the pins, hashes, wall time, step losses and config.

## 4. Base candidates (`h2h` mode)

These are open-licence, ungated instruct models, so no HF access form is needed; that form would be Brandon's hands.
Each must fit a T4 in 4-bit.

- `Qwen/Qwen2.5-7B-Instruct` (Apache-2.0)
- `mistralai/Mistral-7B-Instruct-v0.3` (Apache-2.0)
- `Qwen/Qwen2.5-Coder-7B-Instruct` (Apache-2.0; the Cody candidate)

The candidate list lives in the kernel config and can be changed without code. Gated models (Llama, Gemma) are left
out on purpose.

## 5. What this does NOT do

- It launches nothing and spends nothing; launching is the autopilot's Training-class step.
- It serves nothing: no PASS from this kernel changes any seat.
- It authors no Part B or Part C cases.
- It builds no TPU/JAX stages. Those are designed in the manifests and are a follow-up kernel.
- It does not run Cody's QUAL-001. Cody's tasks need compile-and-test execution, which is a separate harness. The
  `h2h` kernel only ranks bases on Cody's QA records as a first signal.

## 6. Evidence available from this container

There is no GPU here, and no HF or Kaggle egress. The template therefore has a `--dry-run` path: a tiny random
Llama, built locally, plus a tokenizer trained locally on the corpus, running on CPU through **the same code**. That
covers decode, hash gates, the contamination check, base-then-seal, LoRA training steps, tuned generation, scoring and
the artifact layout. It proves the mechanics, not model quality. Real runs on the T4 lane are the autopilot's.

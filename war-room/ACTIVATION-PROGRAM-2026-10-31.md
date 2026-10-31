# ACTIVATION PROGRAM — Workloads First (2026-10-31)

**Origin:** Brandon, 2026-10-31 ~12:52 CDT: "How can we make a workload to
feed it, and help me activate the things we have and design frameworks and
activate everything." This program answers the workload question for every
powerful tool surfaced by the four intel briefs of 2026-10-31
(MULTIAGENT / STEM-OS / QUANT / APEX-OSS) and sequences their activation.
Design only — this document installs nothing and changes no service.

## THE DOCTRINE (governs every section below)

**A tool earns activation only by naming three things:**

1. **Its workload** — real work sourced from Brandon's actual operations.
   Never synthetic busywork, never a demo invented to justify the tool.
2. **Its host** — a machine that can truly run it, verified, not hoped.
3. **Its proof-of-life** — the observable evidence, produced by a real
   run, that it works and is doing the work.

**No workload = no activation.** Costume infrastructure — impressive
systems standing around with nothing true to do — is how fleets die:
every idle stack still eats maintenance, attention, and trust. When in
doubt, bench the tool and write down what real work would have to exist
to un-bench it.

Corollary (Little's Law, already Genesis law): activations run **in
phase order under the WIP cap of 3**. "Activate everything" means
everything *earns its turn* — not everything at once.

## EXECUTION ORDER

| Phase | Asset | One-line shape |
|---|---|---|
| P0 | Local sweep (IN FLIGHT, running separately) | Inventory what the fleet already has installed/staged, verified — the activation baseline |
| P1 | Ghidra shelf | Standing RE queue fed by Brandon's own APKs/binaries |
| P2 | NiFi lineage pattern | Provenance schema inside GHOST/ACE + training pipelines (no NiFi install) |
| P3 | AIxCC-pattern audit lane | Cody audits Genesis's own codebases: scan → prove → patch-verify |
| P4 | Quant stack bake-off | Design-phase comparison feeding WO-GODTIER's paper pipeline |
| P5 | eBPF/Tetragon guardrails | Scoped pilot on S1-class host only; waits on the S1 path |
| — | seL4 | **BENCHED** — no honest workload exists (see §6) |

---

## §1 GHIDRA SHELF — activation P1

*Status: already installed (local_ghidra skill: Ghidra + apktool + jadx).
This is the cheapest activation in the program — the tool exists; what
was missing is the queue that feeds it.*

- **Workload:** a standing reverse-engineering queue sourced from
  Brandon's own operations, in priority order:
  1. **Aurum 2.1 APK audit pass** — the APK delivered to Brandon's hands
     2026-10-31: bundled assets, permissions, network endpoints,
     embedded secrets/trackers, what the player actually phones home.
  2. **Watch + Pulse pre-delivery audit** — every GHOST-Q-015 build gets
     a Ghidra pass before its download link ships (the P3_verify step
     gains teeth: verify the binary, not just the build log).
  3. Any binary Brandon owns and names (his apps, his firmware, his
     files) as it arises.
- **Host:** zane-box (the shelf already lives here; Ghidra headless
  analysis fits this box for phone-scale APKs).
- **Activation steps (the framework):**
  1. **Intake** — each target enters the queue with: artifact path,
     sha256, and lawful basis (ownership). No basis, no analysis.
  2. **Analysis** — fixed pass list: manifest + permissions inventory,
     native library survey, endpoint/URL extraction, secrets scan,
     decompiled review of the interesting paths only.
  3. **Findings format** — one dossier per artifact: target + sha256,
     per-finding severity, evidence (class/offset/string), and a plain
     verdict (ship / ship-with-notes / hold). Filed to the war-room
     beside the build receipt it audits.
- **Proof-of-life:** the Aurum 2.1 dossier, sha256-matched to the
  delivered APK, with findings Brandon can act on.
- **Fences:** lawful targets only — Brandon's own property or targets
  under written authorization. No third-party proprietary binaries,
  no exceptions, no "just looking."

## §2 QUANT STACK — design-phase bake-off P4

*Candidates (from INTEL-BRIEF-2026-10-31-QUANT + APEX-OSS): Freqtrade,
NautilusTrader, ArcticDB, Qlib. None is picked here. This phase picks
**evaluation criteria**; the winner is chosen inside WO-GODTIER's
engine design, on evidence.*

- **Workload:** the StarNet investment engine's paper pipeline, exactly
  as ordered in WO-GODTIER-EXECUTION-2026-10-31 stream 3:
  market data → strategy backtests → **100-trade paper ledger** →
  ranked opportunity ledger → MONEY board. The desk architecture
  (analysts → thesis → Trader proposes → **Risk Manager veto**) and the
  three hardcoded risk laws (EV net of friction, quarter-Kelly max,
  volatility drag) from the QUANT brief govern whatever stack wins.
- **Host:** S1 (the engine is StarNet-hosted; S1 has the RAM/disk and
  already holds OpenHands staged). Design-phase reading/prototyping
  may happen on zane-box; reference backtests run on S1 so the numbers
  describe the real host.
- **Evaluation criteria (score each candidate, publish the sheet):**
  1. **Backtest-to-paper fidelity** — is the backtest code path the
     same code that paper-trades? (NautilusTrader's design claim;
     drift = dishonest evidence, weighted heaviest.)
  2. **Data layer fit** — local time-series storage on modest hardware,
     $0 cloud dependency (ArcticDB's shape; whichever candidate stores
     data must do it on S1's disk).
  3. **Risk-gate integration** — can the Risk Manager veto + the three
     risk laws be enforced *inside* the pipeline, not bolted on?
  4. **Pipeline breadth** — factor discovery / research automation
     (Qlib's strength) vs dry-run execution maturity (Freqtrade's).
  5. **Operational weight** — install size, dependency surface, and
     upkeep on a fleet that already fights prune/reboot churn.
  6. **Ledger compatibility** — every decision, fee calc, and risk
     check exportable to the SQLite audit ledger + §4 lineage schema.
  7. **Time-to-first-honest-backtest** — days from install to a
     reproducible backtest a second run can match bit-for-bit.
- **Proof-of-life:** the published score sheet + one reproducible
  backtest per finalist on the same dataset, matching on re-run.
  (The engine's own proof — 100 paper trades at positive EV — belongs
  to WO-GODTIER, not to this bake-off.)
- **Fences:** PAPER ONLY. No wallets, no exchange credentials, no live
  execution — paper proof never unlocks live anything; every real
  transaction remains Brandon's individual tap (Level C untouched).
  Market data from free/$0 sources only. Wallet-holding frameworks
  (elizaOS / AgentKit / Olas) stay rejected per the QUANT brief.

## §3 AIxCC-PATTERN CYBER REASONING — audit lane P3

*Pattern, not a wholesale install: Atlantis/Buttercup-class systems
(LLM triage + fuzzing + static analysis + proof + verified patch) are
research-grade builds. What activates here is the **pattern**, run
through Cody's lane at Genesis scale.*

- **Workload:** auditing **Genesis's own codebases** — the fleet writes
  code daily (GHOST/ACE services, Apex invoicing API, Genesis Pay/Vault,
  master runtime) and currently reviews it by reading. The lane's queue
  is that real code, starting with the money-adjacent services
  (Pay/Vault/invoicing), where a verified finding is worth the most.
- **Host:** zane-box for static analysis + triage; S1 as the fuzzing/
  heavy-runner seat when its path is up (Cody's designated heavy host).
- **Activation steps (the framework):**
  1. **Scan** — static analysis + dependency audit + targeted fuzzing
     of parsers/inputs, LLM-assisted triage of candidate findings.
  2. **Prove** — a finding enters the ledger only when reproduced:
     a failing test, a crash input, a concrete exploit path on our
     own code. Unproven suspicions are notes, not findings.
  3. **Patch-verify** — fixes are proposed as patches; a *different*
     lane verifies the patch kills the proof and breaks nothing
     (builder ≠ verifier, per Genesis law). Merge follows the normal
     gates — the lane never self-merges.
  4. **Ledger** — verified-findings ledger: codebase, finding, proof
     artifact, patch, verifier, status. This ledger is the product.
- **Proof-of-life:** one full cycle over a named Genesis codebase:
  ledger published with its verified findings — or an honest clean
  bill stating coverage (files/functions scanned, fuzz hours) so
  "nothing found" is evidence, not absence of looking.
- **The Apex Forge shape (future, not this activation):** the same
  pipeline scoped to a *client's* codebase under their written
  authorization is the sellable security-audit deliverable. Packaging
  or selling it is a business act — Brandon's word, later. The lane
  activates internally first and earns its track record on our code.
- **Fences:** Brandon's code only. No scanning, probing, or fuzzing
  any third-party system — ever. Findings about Genesis code stay
  internal until Brandon says otherwise.

## §4 THE NIFI IDEA, WITHOUT NIFI — lineage pattern P2

*Apache NiFi is NOT installed. Petabyte intelligence-routing infra on
this fleet is costume (§6 doctrine). But NiFi's one great idea —
**cryptographic data provenance**: every byte knows where it came from
and what touched it — is a framework upgrade Genesis can run at its
own scale, because Brandon's receipts already do it informally.*

- **The pattern (specification):** every record in the covered
  pipelines carries a provenance block:
  `source` (where it entered, with reference) · `transforms[]` (each
  processing step, in order, with the tool/agent identity) ·
  `timestamps` (entry + each transform) · `hash` (content hash at
  entry, re-verifiable at any later step). A record that cannot show
  its lineage is treated the way an unreceipted claim already is:
  UNVERIFIED.
- **Workload:** the pipelines that already move Brandon's real data:
  1. **ACE opportunity pipeline** — every candidate traces to its
     posting source through each filter/score/submit step (extends
     the registry/KB the ACE lane already keeps).
  2. **Training data pipelines** — dataset records trace to source
     files through each transform (the Cody v1 dataset's per-record
     `source` field is the seed; this formalizes it fleet-wide).
  3. **GHOST queue items** — state changes carry who/what/when, the
     registry-mutation law made structural.
- **Host:** zane-box — these pipelines live here; the pattern is a
  schema + discipline, not a service.
- **Activation steps:** (1) write the provenance schema as a short
  spec beside this program; (2) apply to the ACE registry first (one
  pipeline, end-to-end); (3) extend to the training dataset registry;
  (4) extend to GHOST queue state changes.
- **Proof-of-life:** pick any ACE candidate at random and trace it —
  source posting → every transform → current status — by query alone,
  no archaeology. Then the same for one training dataset record.
- **Fences:** none external — internal data discipline. Explicitly:
  no NiFi, no Accumulo, no new datastore; the existing SQLite/file
  stores gain a schema, not a sibling.

## §5 eBPF / TETRAGON GUARDRAILS — scoped pilot P5

*The hard form of Platinum's fences: policy enforced in the kernel,
below the layer where an agent can argue. The principle is already
adopted (APEX-OSS brief); activation is a pilot, and it is last in
the order because it is the only phase whose host is not yet in hand.*

- **Workload:** enforcing Platinum Level A/B/C on the hosts where
  agents actually execute tools — the triad workers and StarNet
  services converging on S1 (WO-GODTIER streams 1–2). The workload
  exists when agent tool-execution runs there regularly; the pilot
  scopes to ONE such workload, named in the pilot design.
- **Host:** **S1-class machines ONLY.** This sandbox (zane-box)
  cannot load eBPF — same wall class as Docker/setns (verified
  fleet history). No pilot is designed for a host that cannot run it.
- **Activation steps:**
  1. **Gate:** S1 path healthy + a scoped pilot design naming the
     workload, the policies, and the rollback (policy removal).
  2. **Observe mode first** — Tetragon tracing policies log process
     exec + network events for the scoped workload. No enforcement.
     Baseline: what does legitimate work actually touch?
  3. **One enforcing policy** — a single, narrow rule drawn from the
     baseline (e.g., the agent process may not write outside its
     workdir), enforced in a test window against a harness process
     built to violate it.
  4. **Review** — pilot report to Brandon before any policy touches
     real agent traffic.
- **Proof-of-life:** the pilot report shows (a) a real blocked
  violation — the harness process killed/denied by policy, logged;
  and (b) zero false-positive kills of legitimate work across the
  observation window. Both halves required; either alone is theater.
- **Fences:** observe-before-enforce, always. Policies are reversible
  (removable) by design; anything that would constrain production
  agent traffic beyond the pilot waits on Brandon's review of the
  pilot report. No eBPF anything on zane-box.

## §6 seL4 — BENCHED, WITH THE REASON

seL4 is a magnificent artifact — a microkernel with a machine-checked
proof of correctness — and **there is no honest near-term workload
for it in Brandon's operations.** Nothing Brandon runs is an embedded
target seL4 could host; his systems are Linux services, phone apps,
and agent runtimes. Booting seL4 in QEMU to admire it is precisely
the synthetic busywork the doctrine bans: a workload manufactured to
feed the tool, instead of a tool fed by real work.

**Bench condition (what would change this):** a real embedded or
isolation-critical target enters Brandon's operations — a device he
ships, a partition an untrusted workload must not escape, a product
whose buyer requires proved isolation. If that day comes, seL4 is
the first name on the list. Until then: benched, revisited only on
a named target.

*Runner-up honesty note:* eBPF/Tetragon (§5) is the asset closest to
the bench after seL4 — its workload is real but hostage to the S1
path and to agent traffic actually concentrating there. If S1's role
shrinks, §5 benches too, and the program says so in its next review.

## §7 FRAMEWORKS FROM THE EARLIER BRIEFS — one line each

- **CodeAct** (MULTIAGENT brief): Cody-lane input only — when Cody's
  seat is real (WO-CODY-REAL-SOFTWARE), his multi-tool work runs as
  small executable scripts against fleet tools; no separate activation.
- **FlowReview** (MULTIAGENT brief): already Genesis — it *is* the
  Platinum Authority Engine (authorization paired to the commit gate,
  Level A/B/C, signed receipts). Its activation runs under Platinum's
  own program; this program adds nothing but the cross-reference.
- **Little's Law WIP governance** (STEM-OS brief): already law — the
  WIP cap of 3, and this program obeys it (phase order, §0 corollary).
  The STEM-OS money formulas (LTV:CAC, Burn Multiple) stay staged for
  first revenue under GHOST-Q-013, untouched here.

## FENCES (whole program)

- Activation covers **reversible, $0, fleet-owned assets only**.
- **Level C is untouched:** no spend, no publishing, no account
  creation, no money movement, no live trading or betting — anything
  real-money remains Brandon's individual tap, one by one.
- Financial tooling is **paper-only**, permanently, under this program.
- Reverse engineering and security auditing touch **only Brandon's
  own artifacts and code** (or written authorization, if it ever exists).
- Every phase ends in a receipt (`RECEIPT-ACTIVATION-<phase>.md`);
  a phase with no receipt did not happen.

# WO-OPENCODE-MASTER-2026-10-31 — GENESIS TOTAL CONNECTION + UPGRADE PROGRAM

**Issued by:** Brandon Duda, in three orders on 2026-10-31 (~06:54–06:56 CDT):
(1) "make me a master open code work order to completely maximize and connect
to everything we are doing and make a master runtime into that terminal for
you and all agents"; (2) "upgrade all systems like ace ghost and Genesis
browser and Genesis pay"; (3) "put ruflo in the penguin as a first class
agent and tool."
**Executor:** Cody (OpenCode, penguin + S1). **Reviewer:** Claude.
**Verifier:** Zane. **Certifier:** Brandon — his acceptance is the only DONE.
**Incorporates:** the Platinum Master WO (GHOST-Q-009, five pillars in full
force), the GHOST program (WO-GHOST-SERVER-001), the OpenClaw/Hermes admin
WO (Q-010), and the FINISH-THE-ENGINEERING plan. Where this WO and an older
document disagree, this WO governs and the disagreement gets filed as a
correction, never silently absorbed.
**Queue:** GHOST-Q-011 (this WO) · GHOST-Q-012 (Ruflo). Receipts:
`genesis-os/war-room/RECEIPT-MASTER-<WP>-2026-10-31.md`, one per work package.

---

## 1. MISSION

One operation, visibly connected: every system Genesis runs — the job storm,
the transport layer, the browser, the money ledger, the agent fleet —
upgraded to its next honest version and bound into a single runtime that
any agent (and Brandon) can read at a glance. Nothing new gets built beside
the operation; the operation itself gets finished, hardened, and wired
together. Maximize means: more verified outcomes per day in Brandon's
hands — not more machinery.

## 2. VERIFIED CURRENT STATE (2026-10-31 ~07:00 CDT — graded, not claimed)

| System | State | Evidence |
|---|---|---|
| Job storm / ACE | LIVE, producing | 7 SUBMITTED with confirmation evidence 7/7 (runtime verify); 37 SCORED, 20 REJECTED, 1 STAGED (TransChicago) |
| Integrity onboarding | Offer SIGNED | Portal: "Contingent Job Offer - NEW was signed and saved successfully!", Completed 10/31/2026; 10-task packet inventoried, clearing in progress (WOTC next, due 11/30/2026) |
| GHOST queue | INTACT | Q-001…Q-010 + Q-011/Q-012 added today; drain law in force |
| Egress router | BUILT, currently DARK | :18955 not listening after VM recycle (probe 2026-10-31); relaunch ordered §UP-GHOST step 1 |
| Genesis Browser | LIVE | :18080 + :18950 listening on zane-box (2026-10-31 probe); v0.3.1 is Brandon's standing default |
| Genesis Pay / Vault | BUILT + ZANE-VERIFIED | Phase 2 suites green at push (52/52 Vault, 46/46 Pay); Claude's adversarial grade outstanding (Q-008, Brandon relay); Vault digest live on the daily board since 2026-10-31 07:13 |
| NIM brain seats | PROVEN, partial | Glimmer-30B / M3.1 Flash / GLM-5.3 Flash / DeepSeek V4.1 Flash model-field REAL on Brandon's key; Hermes LIVE on Glimmer; penguin claw seats transport-gated (Q-007) |
| Ruflo | REGISTRY-SEATED, install queued | agents.json id `ruflo` (2026-10-31); penguin pack built; zane-box tree pruned 2026-10-21 (F6) |
| Station app (F1) | BUILT, install gated | Scaffold complete, frontend PASS; install chain = Q-001 |
| Fleet transport | DARK from zane-box | Tailnet data path dead (proven 2026-10-30); S1 NetBird verified renewed (expires 2026-10-31 19:14 CDT); penguin Phase B key deposit still owed |

## 3. THE MASTER RUNTIME (built 2026-10-31 — deployment is Cody's first job)

`genesis-os/master-runtime/` — stdlib Python, no daemon, no database of its
own. It reads the GHOST queue + ACE registry + agent registry and renders
one board / one plan / one verify pass. Smoke-verified on zane-box today:
board renders from live data; `verify` shows ACE evidence 7/7; `dispatch`
refused GHOST-Q-008 (human relay) and wrote + read back the GHOST-Q-003
envelope.

**Cody, on penguin and on S1, in this order:**
1. Sync `genesis-os/master-runtime/` to the host (same relative path).
2. Run `python3 master_runtime.py board` — attach the generated
   `state/BOARD.md` host header (hostname + date) to the receipt.
3. Run `python3 master_runtime.py verify` — output verbatim into the receipt.
4. Confirm the runtime writes nothing outside its own directory (it asserts
   this in code; demonstrate by file listing before/after).

**Laws the runtime encodes — do not weaken them in any port or patch:**
DONE is never printed by a script; claims sit UNVERIFIED until a receipt is
read back; mutations and dispatches match deterministic IDs only; human
relays are never dispatched; Level C is untouched (no money, publishing,
accounts, signatures); a provider 429 is a hard stop for its scope.

## 4. THE UPGRADE PROGRAM

### UP-ACE — ACE v2 (job storm)
- **Detector v2: BUILT + FIRST CATCH LANDED (Zane, 2026-10-31).**
  `job-storm-ace/ace_detector_v2.py` normalizes text (curly quotes, case)
  and scans for credential / driving / residency hard-rule classes. First
  run caught the known v1 false-positive (Kent County "Access Center
  Clinician or BSW"); ACE-2026-030 flipped SCORED → REJECTED by ID in
  registry + KB, read back. Cody: wire v2 into `ace_ingest.py` so every
  future harvest passes it BEFORE scoring; regression test = the Kent
  County text must never score again.
- Outcome-learning pass: fold today's outcomes into the KB via `learn.py`
  (Integrity full-funnel, Bobyard, Boutique COO honest-screen, Certified
  Talent thin-employer caveat) — trust values move only on outcomes.
- Wave-3 execution: TransChicago retry (ACE-2026-031, employer-verified);
  Payentry Client Advocate (ACE-2026-033) and Hinsdale Pro Locksmith
  (ACE-2026-039) verify-on-employer-domain → submit under the standing
  walls. Cadence law unchanged: min(verified-fit inventory, pacing
  capacity); 50/day is a ceiling, never a quota.
- Profile-truth sweep: before asking Brandon for ANY profile fact,
  memory-search first (the LinkedIn lesson, 2026-10-31 — his URL was on
  file since Oct 7 while the storm asked). Fix his Indeed education line
  (still shows "High School Diploma") to the GED record — on his word.

### UP-GHOST — GHOST v2 (transport)
- Step 1 (zane-box, immediate): relaunch the egress router
  (`ghost/egress-router/router.py --daemon`, fleet daemon law), probe
  :18955, and run the acceptance trio through it (GitHub GET / NIM
  completion / pip fetch) — the trio is the heal detector; results to the
  GHOST receipt, graded honestly (a stall is a stall, reported as one).
- Relay installs (Q-006) on the first heal window or OpenCode session;
  tokens are collected via Secure Vault when wiring consumes them —
  never through chat (the pack's "send back the token" line is overridden).
- Drain discipline: the master runtime's outbox is the dispatch surface;
  every drained job flips status ONLY with its receipt filed. Dead-letter
  items surface to Brandon, never silently retry forever.
- Phase 2 prep only (job-bus promotion stays sequenced behind transport
  proof): inventory which standing queues migrate to NATS first; no
  dispatch path retires until the bus survives several recycle cycles.

### UP-BROWSER — Genesis Browser v0.4
Baseline: v0.3.1, Brandon's standing default for online tasks; :18080 and
:18950 verified listening 2026-10-31. The upgrade targets today's wounds:
- **Task-resume protocol:** on 2026-10-31 the browser layer killed 5+ tasks
  pre-action (runtime pool faults) and one mid-flow. v0.4 spec: every task
  carries a durable checkpoint (last completed step + external effects
  taken) so a replacement task resumes instead of restarting — and a
  zero-action death is provable from the checkpoint, as it was today by
  hand.
- **Session persistence:** signed-in sessions survive VM recycles where the
  site allows; vault-login and takeover flows stay on the hosted browser
  (standing rule, unchanged).
- **Takeover hygiene:** a user's own clicks in a taken-over tab are logged
  into the task record (today Brandon's Bobyard submit attempt was how we
  learned the form still blocked — that signal should be structural).
- Version stamp + changelog in the browser service; Zane verifies by
  killing a task mid-flow and watching the resume (test, don't trust).

### UP-PAY — Genesis Pay v2 + Vault
- Consume Claude's adversarial grade of Vault Phase 2 (Q-008) when Brandon
  relays it; every finding gets a fix-or-rebuttal entry — no silent skips.
- Baseline re-run of both suites (Pay 46 / Vault 52 at push) as step 1 of
  this package, receipted with today's numbers, whatever they are.
- Digest streak: the Vault daily digest runs on the production DB
  (`~/genesis-vault.db`); target = 7 consecutive clean mornings on the
  daily board, counted from receipts, not intentions.
- The watch REFUSES an incomplete debit: standing test — a debit record
  missing merchant, amount, or date must be rejected by the watch, proven
  by a test case, because the $292 Cash App debit is still unrecorded for
  exactly that reason. The machine never moves money; sweep cards stay
  PREPARED_ONLY; every transfer remains Brandon's tap.

### UP-RUFLO — Ruflo first-class on penguin (Q-012)
Pack: `genesis-os/master-runtime/ruflo-penguin/` (install.sh, MCP snippet,
verify.sh). Acceptance:
1. `ruflo --version` answers on penguin; install home =
   `~/agent-shelf/ruflo` (prune-proof), pinned 3.42.5, drift recorded.
2. MCP handshake verifies (verify.sh §2) and OpenCode lists Ruflo's tools.
3. One real swarm task under this WO completes with a receipt (suggested
   first mission: the UP-BROWSER checkpoint-format review sweep — useful,
   bounded, read-only).
4. Ruflo's zane-box seat returns only via Q-002 (shelf) — no double-install
   improvisation.

### UP-STATION / UP-NIM / UP-SHELF / UP-ADMIN (connection packages)
- **Station (Q-001):** unchanged chain — S1 Tauri compile → .deb → penguin
  install → Brandon opens it. His acceptance is the only DONE.
- **NIM seats (Q-004/Q-007 + Session B):** penguin claws → M3.1 Flash,
  ZeroClaw → GLM-5.3 Flash, Hermes :18807 Glimmer model-field POST proof —
  every seat proven by its response model field or it does not count.
- **Shelf (Q-002/Q-003):** OCE restore + proof query; OpenHands/Aider/Ruflo
  (zane-box seat) reinstalls into the prune-exempt shelf; the storage
  governor's prune list is re-audited in the same receipt (the F6 culprit
  never eats an agent again — prove the exemption list by reading it back).
- **Admin (Q-010):** Phases 0–2 execute (one gateway, Brandon's devices
  paired operator.admin, Hermes single-home on S1). Phase 3 remains
  BLOCKED-BY-RULING (Genesis Omega not adopted) until Brandon says
  otherwise in his own words.

## 5. SEQUENCING — WIP CAP 3 (Brandon's RESET order, binding)

- **WS-1** Job storm + Integrity packet (Zane) — the money lane runs daily.
- **WS-2** Master runtime deployment + GHOST v2 + Ruflo (Cody/Zane) — this WO.
- **WS-3** Station F1 (Cody builds, Claude reviews, Zane verifies).
Everything else — shelf, NIM wiring, admin WO, Fiverr, capital/partner
lanes — stays parked in the runtime's plan order and enters only when a
slot frees. A fourth concurrent workstream is a defect, not ambition.

## 6. ACCEPTANCE BATTERY (per work package — all eight, no exceptions)

1. The thing runs, from a cold start, on the target host — not just the
   builder's host.
2. Its own test/verify battery passes with output in the receipt.
3. A second agent (never the builder) re-runs the headline check.
4. State survives a restart/recycle of the host it lives on.
5. Resource envelope respected (penguin RAM-first; S1 caps per S1-STACK-001).
6. Every claim in the receipt traces to a command output or a file read back.
7. Fences demonstrably held — including one deliberate refusal test where
   the package touches a gate (dispatch refusal, incomplete-debit refusal,
   detector rejection).
8. Brandon can see the result from his side, or the package is graded
   LIVE ON A MACHINE — never DONE.

## 7. FENCES (bind every agent and every swarm worker)

$0 spend. No accounts created, nothing published, no money moved, no
contracts or signatures — Brandon's named word, per act, Level C.
Credentials live in the Secure Vault only; tokens never travel in chat.
SSN and banking values are Brandon's hands only, never relayed. Bind law:
loopback or named addresses, never 0.0.0.0 improvisation. A provider 429
is a hard stop for that scope. Relayed plans never self-authorize —
formality is not approval. Assessments, trainings, and tests are taken by
the human they assess. Facts exactly as stated: never inflate experience,
credentials, or results — a truthful answer that screens Brandon out is an
accepted outcome, never a reason to fabricate.

## 8. REPORTING

Per work package: `RECEIPT-MASTER-<WP>-2026-10-31.md` in
`genesis-os/war-room/`, graded VERIFIED / UNVERIFIED / UNKNOWN per claim,
in the format VERIFIED — BUILT — STAGED — BLOCKED — NEEDS APPROVAL, with
paths, versions, and the actual outputs. The master board
(`master_runtime.py board`) is regenerated after every receipt lands, so
Brandon's one-glance view is never older than the last verified fact.

## 9. BRANDON'S HANDS (unchanged — the runtime lists them, never does them)

Session B (Prime lineup apply; Glimmer Colab Run-all) · penguin Phase B
NetBird key deposit · Integrity packet his-hands items (I-9 attestation,
W-4 elections, payroll banking, safety training) · the $292 debit's
merchant/amount/date · Fiverr own-network sign-in · Claude Vault grade
relay (Q-008) · Station acceptance, when the app is in front of him.

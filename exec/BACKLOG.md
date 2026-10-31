# Executive development backlog: GENESIS-EXEC-001 (prioritised 2026-10-31)

The order follows the next-best-decision doctrine: income first, then things that put a result in Brandon's hands,
then unblocking power, reversibility, perishable resources, and finishing before starting.

| # | Item | Why it ranks here | Class | Blocked on |
|---|---|---|---|---|
| E-1 | **Merge train.** Zane reviews and merges the reviewed stacks, in order: Omega (#14 → #17 → #18 → #19 → #20 → #21), then GHOST v2 (Genesis-os#1). | 70+ unmerged drafts are the bottleneck. Nothing is LIVE until it merges and deploys. | B (merge after independent verification, per the Engineering class) | Zane |
| E-2 | **One registry.** GHOST v2 becomes the ops registry of record. Omega missions and training runs appear in it as linked jobs; the master runtime reads it. Retire duplicate state, without rewriting working stores. | The Phase 1 "one authoritative registry" requirement | A/B | E-1 (GHOST merged) |
| E-3 | **Board on a schedule** on zane-box, as a GHOST job: baseline nightly, board hourly. Publish it to Brandon as a private page. | Real telemetry where he looks | B | E-1 |
| E-4 | **Training lane:** launch the h2h, then the ACE and GHOST LoRA kernels (Genesis-os#4), before 2026-11-07. | Perishable quota: about 29 GPU-h and 20 TPU-h | Training class | the autopilot on zane-box |
| E-5 | **Aurum Hi-Fi P2:** wire the EQ engine into Media3, add the headphone picker. Then rebuild the catalog from the Audius match. | In Brandon's hands; he uses it daily | A | Audius run (Zane) for the catalog half |
| E-6 | **Net Forge first game** (Genesis-core#27 §3) | First real Universe product | A | Brandon's permission rule, or Zane |
| E-7 | **GHOST revenue ops (Phase 3).** Prospect, deliverable and payment records with verified-receipt-only revenue. Reuse ACE (Genesis-core#8) and Genesis Pay (#3/#4); don't rebuild them. | Income first, but only on verified payments | A (build) / C (any send or payment) | E-1 and E-2 |
| E-8 | **Board hardening:** a baseline schema and integrity check (audit finding 8); a live re-check of draft `mergeable_state` (finding 10) | Audit leftovers | A | — |
| E-9 | **LLM routing test** from a host that can reach NIM, Groq and OpenRouter | Phase 1 budget-aware routing is NOT TESTED | A | a host with provider egress |

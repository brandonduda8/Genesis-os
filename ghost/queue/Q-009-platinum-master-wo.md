# Q-009 — PLATINUM MASTER WO (OpenCode/Cody)

- **Job:** Execute `genesis-os/war-room/WO-OPENCODE-PLATINUM-MASTER-2026-10-31.md` — six work packages (WP-A ACE · WP-B GHOST · WP-C Station · WP-D Vault+Pay · WP-E brain seats · WP-F agent shelf), WIP cap 3.
- **requires_path:** penguin-reachable (Cody's home) for WP-C/WP-E/WP-F on-host steps; S1-reachable for S1 builds; zane-box-local packages (WP-A, WP-D) may proceed without a device path.
- **Drain rule:** on any heal window, claim the highest-priority package whose path probes GREEN; run its next unfinished acceptance item; write progress + receipts before the window closes; on failure, record the attempt and re-queue. Dead-letter: any package blocked twice on the same cause surfaces to Brandon via Zane with the cause named.
- **Status:** QUEUED (filed Oct 31, 2026 ~05:22 CDT).

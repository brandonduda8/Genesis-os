# GRANT.md — Brandon's admin-grant checklist for the training services

What Brandon does (and does not) need to do so gensdk can administer his
GPU/TPU services. **Standing rule: no password, API key, or token is ever
typed into chat — not to Zane, not to any agent.** Credentials move only
through the Secure Vault card flow, the provider CLI's own auth flow, or
Brandon's hands on the device itself.

## Kaggle — NOTHING NEEDED (already granted)
- The API token already lives in the Secure Vault (`custom.kaggle`,
  connected 2026-09-21); auth verified. gensdk reaches Kaggle only
  through the connector CLI, which carries a vault surrogate — the raw
  token never surfaces anywhere.
- Only if a future live auth check fails: reconnect via the vault card
  (the connector's reconnect flow), never by pasting a key.

## Google Colab — NOTHING NEEDED (already granted)
- `google-colab-cli` is already OAuth-authed against Brandon's Google
  account; the token lives in the CLI's own store and gensdk never reads
  it. `colab usage` answers live.
- Google AI Pro includes 200 CU/month — that included pool is the lane.
  Top-up CU purchases ($9.99/100) are **never automatic**; they would be
  Brandon's explicit tap, every time.

## Modal — ONE TAP, WHEN HE WANTS THE LANE LIVE
- Current state: CLI installed, `~/.modal.toml` already present.
- If re-auth is ever needed, the grant step is his tap: run
  `modal token new` and approve the browser URL it prints. The CLI
  writes `~/.modal.toml` itself (mode 0600) — nothing passes through
  chat, no key is copied anywhere.
- Fence: Modal's plan includes **$30/mo of credit**. gensdk auto-approves
  Modal runs only inside that included credit (ledger-tracked); any
  overage is paid spend and stops for Brandon's tap.

## Lightning AI — OPTIONAL, only if he wants it included
- No credential is on file; the lane is an honest NOT_CONNECTED stub.
- To include it: Brandon provides the API key via the Secure Vault
  **secure card** flow (he types it into the vault capture page, never
  into chat). Until then gensdk reports the lane as not connected and
  launches nothing there.

## S1 (local host) — ALREADY ON HIS LIST, unchanged
- The durable S1 access fix is the **Phase B key deposit** (NetBird key
  deposited at the S1/penguin terminals by Brandon's hands) — already on
  his canonical hands list, not a new ask created by this SDK.
- Until transport verifies, gensdk stages S1 specs and reports the lane
  TRANSPORT_GATED; execution routes through the GHOST queue.

## Kaggle weekly pools (for reference)
- GPU: 30 hrs/week (T4/P100) · TPU: 20 hrs/week. Free lanes are
  pre-authorized for training runs under Brandon's 2026-10-31 order —
  no per-run tap — with the burn ledger accounting for every hour.

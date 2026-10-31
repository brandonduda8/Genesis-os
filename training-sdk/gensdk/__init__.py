"""gensdk — Genesis Training SDK.

One programmatic interface over Brandon Duda's GPU/TPU training services:
Kaggle (GPU + TPU lanes), Google Colab, Modal, Lightning AI (stub), and
S1-local (transport-gated stub).

Design law:
- Subprocess wrappers around the provider CLIs only. The SDK never
  reimplements provider auth and never reads, prints, or persists any
  credential or token file.
- Submissions STAGE by default. A real launch requires --execute and must
  pass the policy engine (see gensdk.policy).
- Every burn is written to the append-only ledger with read-back.

Policy anchor: Brandon's 2026-10-31 order lifting the per-run tap fence
for free-lane training (Kaggle weekly GPU/TPU hours, Colab compute units,
S1-local). Paid spend beyond included credits stays fenced; top-up
purchases are never automatic.
"""

__version__ = "0.1.0"

PROVIDERS = ("kaggle_gpu", "kaggle_tpu", "colab", "modal", "lightning", "local_s1")

# Burn unit per provider (mirrors genesis-os/train/state/quotas.json keys).
UNITS = {
    "kaggle_gpu": "gpu_hours",
    "kaggle_tpu": "tpu_hours",
    "colab": "cu",
    "modal": "usd",
    "lightning": "credits",
    "local_s1": "local_hours",
}

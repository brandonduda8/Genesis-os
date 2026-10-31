"""Lightning AI provider — honest NOT_CONNECTED stub.

No Lightning credential is on file (genesis-os/train/state/quotas.json:
"UNVERIFIED — signup in progress, API key card sent, no credential yet").
This stub exists so the lane has a name, a unit, and a truthful state in
every gensdk listing. It launches nothing and reports no quota. When
Brandon supplies an API key through the secure-card flow (see GRANT.md),
this module gets a real CLI/API wrapper — not before.
"""
from __future__ import annotations

from .base import BaseProvider, ProviderError

NOTE = ("no Lightning AI credential on file; signup was in progress per "
        "genesis-os/train records. Include this lane only via Brandon's "
        "secure-card API key (GRANT.md).")


class LightningProvider(BaseProvider):
    name = "lightning"
    unit = "credits"

    def status(self) -> dict:
        return {"provider": self.name, "state": "NOT_CONNECTED", "detail": NOTE}

    def quota(self) -> dict:
        return {"provider": self.name, "available": None, "note": NOTE}

    def submit(self, spec: dict) -> dict:
        raise ProviderError(f"lightning is NOT_CONNECTED: {NOTE}")

    def job_status(self, ref: str) -> str:
        return "UNKNOWN"

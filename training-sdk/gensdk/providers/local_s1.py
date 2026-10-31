"""S1-local provider — honest TRANSPORT_GATED stub.

S1 (Brandon's 16 GB host on the tailnet) is a real training target, but
this box's tailnet data path to it is gated: jobs reach S1 through the
GHOST queue / heal windows, and the durable fix (NetBird Phase B key
deposit) is still on Brandon's hands list. Until transport is verified,
gensdk stages S1 specs and launches nothing — claiming a local lane it
cannot reach would be fabrication.
"""
from __future__ import annotations

from .base import BaseProvider, ProviderError

NOTE = ("S1 reachable only through gated fleet transport (tailnet data "
        "path / GHOST heal windows); Phase B key deposit pending. "
        "Specs stage locally; execution dispatches via the GHOST queue, "
        "not from this SDK, until transport verifies.")


class LocalS1Provider(BaseProvider):
    name = "local_s1"
    unit = "local_hours"

    def status(self) -> dict:
        return {"provider": self.name, "state": "TRANSPORT_GATED", "detail": NOTE}

    def quota(self) -> dict:
        return {"provider": self.name, "available": None, "note": NOTE}

    def submit(self, spec: dict) -> dict:
        raise ProviderError(f"local_s1 is TRANSPORT_GATED: {NOTE}")

    def job_status(self, ref: str) -> str:
        return "UNKNOWN"

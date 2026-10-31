"""Provider interface. Every provider wraps its CLI via subprocess; none
of them reads credential material."""
from __future__ import annotations


class ProviderError(Exception):
    pass


class NotConfigured(ProviderError):
    pass


class BaseProvider:
    name = "base"
    unit = None

    def status(self) -> dict:
        """{provider, state, detail} — state is one of LIVE, STAGED,
        EXPERIMENTAL, NOT_CONFIGURED, NOT_CONNECTED, TRANSPORT_GATED."""
        raise NotImplementedError

    def quota(self) -> dict:
        """Structured quota/balance, or a dict with 'available': None and
        a 'note' explaining why no live number exists."""
        raise NotImplementedError

    def submit(self, spec: dict) -> dict:
        """Launch a run for an approved spec. Returns {ref, detail}.
        Only called after policy.approve_execute() said yes."""
        raise NotImplementedError

    def job_status(self, ref: str) -> str:
        raise NotImplementedError

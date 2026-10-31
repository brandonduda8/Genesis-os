"""Modal provider — wrapper around the `modal` CLI.

Configuration test: the CLI exists AND ~/.modal.toml exists. The toml is
Modal's credential file; gensdk checks only its presence, never its
contents. If config is absent the provider reports NOT_CONFIGURED —
it never fabricates a connection.

Spend policy: Modal's plan includes $30/mo of credit. gensdk auto-
approval (gensdk.policy) holds launches inside that included credit
using the gensdk ledger; overage is paid spend and stays Brandon's tap.
Modal exposes no remaining-credit CLI call gensdk trusts, so quota()
reports the policy cap and the ledger's month-to-date figure instead of
inventing a live balance.
"""
from __future__ import annotations

import os
import shutil

from ..util import run_cli
from .base import BaseProvider, ProviderError

MODAL_TOML = os.path.expanduser("~/.modal.toml")
_FALLBACK_BINS = (os.path.expanduser("~/.local/bin/modal"),
                  os.path.expanduser("~/workspace/.venvs/modal-cli/bin/modal"))


def modal_bin() -> str | None:
    found = shutil.which("modal")
    if found:
        return found
    for cand in _FALLBACK_BINS:
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


class ModalProvider(BaseProvider):
    name = "modal"
    unit = "usd"

    def _configured(self) -> tuple:
        binary = modal_bin()
        if not binary:
            return False, "modal CLI not found on PATH or known venv locations"
        if not os.path.isfile(MODAL_TOML):
            return False, ("~/.modal.toml absent — not configured "
                           "(grant step: `modal token new`, Brandon's tap)")
        return True, binary

    def status(self) -> dict:
        ok, detail = self._configured()
        if not ok:
            return {"provider": self.name, "state": "NOT_CONFIGURED",
                    "detail": detail}
        r = run_cli([detail, "--version"], timeout=60)
        version = (r.stdout or r.stderr).strip()[:80] if r else ""
        return {"provider": self.name, "state": "STAGED",
                "detail": f"CLI present ({version or 'version unread'}), "
                          "~/.modal.toml present (contents never read); "
                          "live API auth not probed by gensdk smoke",
                "bin": detail}

    def quota(self) -> dict:
        from .. import ledger as ledger_mod
        from ..policy import MODAL_INCLUDED_CREDIT_USD
        spent = float(ledger_mod.totals()["month"].get("modal/usd", 0.0))
        return {"provider": self.name, "unit": "usd",
                "included_credit_usd_month": MODAL_INCLUDED_CREDIT_USD,
                "ledger_month_to_date_usd": spent,
                "headroom_usd": round(MODAL_INCLUDED_CREDIT_USD - spent, 2),
                "available": None,
                "note": "no live remaining-credit API is read; headroom is "
                        "the $30/mo included-credit policy cap minus the "
                        "gensdk ledger's month-to-date Modal entries"}

    def submit(self, spec: dict) -> dict:
        ok, detail = self._configured()
        if not ok:
            raise ProviderError(detail)
        script = spec["entrypoint"]
        if not os.path.isfile(script):
            raise ProviderError(f"modal entrypoint script not found: {script}")
        r = run_cli([detail, "run", script], timeout=3600)
        if not r.ok:
            raise ProviderError((r.stdout + r.stderr).strip()[:500])
        return {"ref": f"modal-run:{spec['name']}",
                "detail": f"modal run returned; cli output: {r.stdout.strip()[:300]}"}

    def job_status(self, ref: str) -> str:
        ok, detail = self._configured()
        if not ok:
            return "UNKNOWN"
        r = run_cli([detail, "app", "list"], timeout=120)
        if not r.ok:
            return "UNKNOWN"
        return "RUNNING" if spec_name_in(r.stdout, ref) else "NOT_RUNNING"


def spec_name_in(text: str, ref: str) -> bool:
    name = ref.split(":", 1)[-1]
    return name in text

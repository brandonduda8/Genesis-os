"""Colab provider — subprocess wrapper around the fleet entry point
~/workspace/bin/colab-fixed (google-colab-cli 0.7.4).

Quirks honored (from the local-colab skill, verified 2026-10-24):
- colab-fixed preflight exits 127 unless a real `colab` binary resolves;
  always pass COLAB_REAL_BIN=~/workspace/.venvs/colab-cli/bin/colab.
- Auth is the CLI's own OAuth store (~/.config/colab-cli/token.json) —
  gensdk never reads or prints it.
- There is NO Colab usage API: balance is read by parsing `colab usage`.
- `colab usage` / `colab sessions` are proven live. `colab run` is NOT
  proven end-to-end — flagged EXPERIMENTAL: submit() refuses unless the
  job spec sets allow_experimental: true.
"""
from __future__ import annotations

import os
import re

from ..util import run_cli
from .base import BaseProvider, ProviderError

COLAB_FIXED = os.path.expanduser("~/workspace/bin/colab-fixed")
COLAB_REAL_BIN = os.path.expanduser("~/workspace/.venvs/colab-cli/bin/colab")
ENV = {"COLAB_REAL_BIN": COLAB_REAL_BIN}


class ColabProvider(BaseProvider):
    name = "colab"
    unit = "cu"

    def _run(self, args: list, timeout: int = 300):
        return run_cli([COLAB_FIXED] + args, timeout=timeout, env_extra=ENV)

    def usage_text(self) -> str:
        r = self._run(["usage"], timeout=180)
        if not r.ok:
            raise ProviderError((r.stdout + r.stderr).strip()[:400])
        return r.stdout.strip()

    def sessions_text(self) -> str:
        r = self._run(["sessions"], timeout=180)
        if not r.ok:
            raise ProviderError((r.stdout + r.stderr).strip()[:400])
        return r.stdout.strip()

    def status(self) -> dict:
        if not (os.path.isfile(COLAB_FIXED) and os.path.isfile(COLAB_REAL_BIN)):
            return {"provider": self.name, "state": "NOT_CONFIGURED",
                    "detail": "colab-fixed or the colab-cli venv binary is missing"}
        try:
            self.usage_text()
            return {"provider": self.name, "state": "LIVE",
                    "detail": "usage answers (OAuth-authed CLI); "
                              "run path is EXPERIMENTAL (unproven end-to-end)"}
        except ProviderError as exc:
            return {"provider": self.name, "state": "NOT_CONFIGURED",
                    "detail": str(exc)}

    def quota(self) -> dict:
        try:
            text = self.usage_text()
        except ProviderError as exc:
            return {"provider": self.name, "available": None, "note": str(exc)}
        balance = None
        # Anchor on the real balance line first ("Current balance: N
        # compute units"). A naive "available" scan is a trap: the CLI's
        # update notice ("A new version ... is available: 0.7.5") matches
        # it and yields the version number as a fake balance — that bug
        # fired in the first gensdk smoke and was caught against the raw
        # text before this parser was trusted.
        m = re.search(r"balance:\s*(\d+(?:\.\d+)?)\s*compute units", text, re.I)
        if m:
            balance = float(m.group(1))
        if balance is None:
            for line in text.splitlines():
                low = line.lower()
                if "version" in low:
                    continue
                if "balance" in low or "remaining" in low:
                    mm = re.search(r"(\d+(?:\.\d+)?)", line)
                    if mm:
                        balance = float(mm.group(1))
                        break
        return {"provider": self.name, "unit": "cu",
                "remaining_cu": balance,
                "source": "colab usage via colab-fixed (live)",
                "raw": text[:500],
                "note": None if balance is not None else
                        "could not parse a balance from `colab usage` output; raw text included"}

    def active_sessions(self) -> int | None:
        """Count of live sessions, or None if unparseable. Used by the
        one-run-per-lane check."""
        try:
            text = self.sessions_text()
        except ProviderError:
            return None
        if "no active sessions" in text.lower() or not text.strip():
            return 0
        rows = [ln for ln in text.splitlines() if ln.strip()]
        # Header-only output means zero; anything more is ambiguous —
        # report the raw count of non-header lines as a floor.
        return max(0, len(rows) - 1)

    def submit(self, spec: dict) -> dict:
        if not spec.get("allow_experimental"):
            raise ProviderError(
                "colab run is EXPERIMENTAL (not proven end-to-end). "
                "Set allow_experimental: true in the job spec to use it, "
                "or run the prepared notebook manually (the skill's "
                "primary, ToS-safe path).")
        script = spec["entrypoint"]
        if not os.path.isfile(script):
            raise ProviderError(f"colab entrypoint script not found: {script}")
        r = self._run(["run", script], timeout=3600)
        if not r.ok:
            raise ProviderError((r.stdout + r.stderr).strip()[:500])
        return {"ref": f"colab-run:{spec['name']}",
                "detail": f"EXPERIMENTAL colab run completed; cli output: "
                          f"{r.stdout.strip()[:300]}"}

    def job_status(self, ref: str) -> str:
        n = self.active_sessions()
        if n is None:
            return "UNKNOWN"
        return "RUNNING" if n and n > 0 else "NOT_RUNNING"

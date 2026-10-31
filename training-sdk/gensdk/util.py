"""Shared subprocess runner for provider CLIs.

The SDK wraps CLIs; it never speaks provider protocols itself and never
touches credential material. This helper only runs a command, captures
output, and reports — it does not log environment or arguments that could
carry secrets (none of the wrapped CLIs take secrets as arguments anyway:
Kaggle auth is a vault surrogate injected inside bin/kaggle.py, Colab auth
is the CLI's own OAuth store, Modal auth is ~/.modal.toml read by the CLI).
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class CliResult:
    argv: list
    rc: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.rc == 0


def run_cli(argv: list, timeout: int = 180, env_extra: dict | None = None) -> CliResult:
    import os

    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, env=env
        )
        return CliResult(argv=list(argv), rc=proc.returncode,
                         stdout=proc.stdout or "", stderr=proc.stderr or "")
    except FileNotFoundError as exc:
        return CliResult(argv=list(argv), rc=127, stdout="",
                         stderr=f"executable not found: {exc.filename}")
    except subprocess.TimeoutExpired:
        return CliResult(argv=list(argv), rc=124, stdout="",
                         stderr=f"timed out after {timeout}s")

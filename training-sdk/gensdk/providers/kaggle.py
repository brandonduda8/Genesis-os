"""Kaggle provider — subprocess wrapper around the connector CLI
~/workspace/custom-connectors/custom.legacy-kaggle/bin/kaggle.py.

That CLI carries the vault surrogate auth internally (custom.kaggle);
gensdk never sees, passes, or logs any credential. Subcommands used:
auth, quota, kernels, push, status, output.

Quota wire format (from bin/kaggle.py cmd_quota):
  gpu: used=<dur> reserved=<dur> allowed=<dur>  tpu: used=<dur>
  allowed=<dur>  refresh=<ts>
Durations arrive as protobuf-style strings ("108000s", possibly "1h30m"
or plain seconds); parsed to hours here.
"""
from __future__ import annotations

import json
import os
import re
import sys

from ..util import run_cli
from .base import BaseProvider, ProviderError

KAGGLE_CLI = os.path.expanduser(
    "~/workspace/custom-connectors/custom.legacy-kaggle/bin/kaggle.py")

# DEFECT WORKAROUND (found in gensdk smoke, 2026-10-31): bin/kaggle.py
# inserts /opt/muse/skills/custom-connector-setup/templates/skill/bin into
# sys.path for `dynamic_credentials`, but that directory does not exist —
# the module lives in .../custom-connector-setup/bin/. Without help the
# CLI dies with ModuleNotFoundError before any request. gensdk supplies
# the correct directory via PYTHONPATH; the connector CLI itself should
# be fixed upstream (gensdk does not edit it).
_DC_DIR = "/opt/muse/skills/custom-connector-setup/bin"


def _duration_seconds(token: str) -> float | None:
    token = token.strip().strip(",")
    if re.fullmatch(r"[0-9]+(\.[0-9]+)?", token):
        return float(token)
    m = re.fullmatch(r"(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m)?(?:(\d+(?:\.\d+)?)s)?",
                     token)
    if m and any(m.groups()):
        h, mi, s = (float(g) if g else 0.0 for g in m.groups())
        return h * 3600 + mi * 60 + s
    return None


def _kv(text: str, key: str):
    m = re.search(rf"{key}=(\S+)", text)
    return m.group(1) if m else None


class KaggleProvider(BaseProvider):
    """One class, two lanes: accelerator='gpu' (kaggle_gpu) or 'tpu'
    (kaggle_tpu). The lanes share the CLI but have separate weekly pools
    and separate one-run-at-a-time lanes in the policy engine."""

    def __init__(self, accelerator: str):
        assert accelerator in ("gpu", "tpu")
        self.accelerator = accelerator
        self.name = f"kaggle_{accelerator}"
        self.unit = "gpu_hours" if accelerator == "gpu" else "tpu_hours"

    def _run(self, args: list, timeout: int = 180):
        import os as _os
        existing = _os.environ.get("PYTHONPATH", "")
        pypath = _DC_DIR + ((":" + existing) if existing else "")
        return run_cli([sys.executable, KAGGLE_CLI] + args, timeout=timeout,
                       env_extra={"PYTHONPATH": pypath})

    # --- read-only -----------------------------------------------------
    def auth(self) -> tuple:
        r = self._run(["auth"], timeout=120)
        return r.ok and "AUTH_OK" in r.stdout, (r.stdout + r.stderr).strip()

    def status(self) -> dict:
        if not os.path.isfile(KAGGLE_CLI):
            return {"provider": self.name, "state": "NOT_CONFIGURED",
                    "detail": f"connector CLI missing at {KAGGLE_CLI}"}
        ok, detail = self.auth()
        return {"provider": self.name,
                "state": "LIVE" if ok else "NOT_CONFIGURED",
                "detail": detail or "auth probe failed"}

    def quota(self) -> dict:
        r = self._run(["quota"], timeout=120)
        if not r.ok:
            return {"provider": self.name, "available": None,
                    "note": f"quota call failed: {(r.stdout + r.stderr).strip()[:300]}"}
        text = r.stdout
        if self.accelerator == "gpu":
            seg = text.split("tpu:")[0]
            used = _duration_seconds(_kv(seg, "used") or "")
            reserved = _duration_seconds(_kv(seg, "reserved") or "") or 0.0
            allowed = _duration_seconds(_kv(seg, "allowed") or "")
        else:
            seg = "tpu:" + text.split("tpu:", 1)[1] if "tpu:" in text else ""
            used = _duration_seconds(_kv(seg, "used") or "")
            reserved = 0.0
            allowed = _duration_seconds(_kv(seg, "allowed") or "")
        refresh = _kv(text, "refresh")
        if used is None or allowed is None:
            return {"provider": self.name, "available": None,
                    "note": f"unparseable quota output: {text.strip()[:300]}"}
        remaining_h = (allowed - used - reserved) / 3600.0
        return {"provider": self.name, "unit": self.unit,
                "used_hours": round(used / 3600.0, 3),
                "reserved_hours": round(reserved / 3600.0, 3),
                "allowed_hours": round(allowed / 3600.0, 3),
                "remaining_hours": round(remaining_h, 3),
                "refresh": refresh,
                "source": "kaggle.py quota (live)"}

    def kernels(self, user: str | None = None, page_size: int = 20) -> str:
        args = ["kernels", "--page-size", str(page_size)]
        if user:
            args += ["--user", user]
        r = self._run(args, timeout=120)
        if not r.ok:
            raise ProviderError((r.stdout + r.stderr).strip()[:300])
        return r.stdout.strip()

    def job_status(self, ref: str) -> str:
        r = self._run(["status", ref], timeout=120)
        if not r.ok:
            raise ProviderError((r.stdout + r.stderr).strip()[:300])
        m = re.search(r"status=(\S+)", r.stdout)
        return m.group(1) if m else r.stdout.strip()

    def output(self, ref: str, dest: str) -> str:
        r = self._run(["output", ref, dest], timeout=900)
        if not r.ok:
            raise ProviderError((r.stdout + r.stderr).strip()[:300])
        return r.stdout.strip()

    # --- launch (policy-gated by the CLI layer) -------------------------
    def submit(self, spec: dict) -> dict:
        kernel_dir = spec["entrypoint"]
        meta_path = os.path.join(kernel_dir, "kernel-metadata.json")
        if not os.path.isfile(meta_path):
            raise ProviderError(
                f"kaggle entrypoint must be a kernel dir with "
                f"kernel-metadata.json: {kernel_dir}")
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        # Lane/pool mismatch is a hard stop: burning the wrong weekly pool
        # silently is exactly the failure this check exists to prevent.
        want_gpu = self.accelerator == "gpu"
        if want_gpu and meta.get("enable_tpu"):
            raise ProviderError("kernel-metadata enables TPU but spec lane is kaggle_gpu")
        if not want_gpu and not meta.get("enable_tpu"):
            raise ProviderError("kernel-metadata does not enable TPU but spec lane is kaggle_tpu")
        r = self._run(["push", kernel_dir], timeout=600)
        if not r.ok:
            raise ProviderError((r.stdout + r.stderr).strip()[:500])
        ref = meta.get("id") or meta.get("slug")
        return {"ref": ref,
                "detail": f"pushed via kaggle.py push; cli output: {r.stdout.strip()[:300]}"}

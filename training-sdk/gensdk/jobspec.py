"""Job-spec format + validator for gensdk.

A job spec is a JSON object. Field conventions reuse genesis-os/train's
queue entries where they fit (name ~ job_id/model, est burn, priority,
dataset hash-gate like the Kaggle kernel EXPECTED_CORPUS_SHA discipline).

Required fields:
  name            str, slug ([a-z0-9][a-z0-9-_]*), unique-ish job name
  provider        one of gensdk.PROVIDERS
  entrypoint      kaggle: kernel dir containing kernel-metadata.json
                  colab/modal: local script path
  burn_cap        {"amount": float > 0, "unit": <provider unit>}
                  hard ceiling the run may not exceed; unit must match
                  the provider's unit (gpu_hours/tpu_hours/cu/usd/...)

Optional fields:
  dataset_path    local dataset artifact the run trains on
  dataset_sha256  64-hex SHA-256 of dataset_path. REQUIRED when
                  dataset_path is set (hash gate: a run never trains on
                  an unverified artifact). Verified again at submit time.
  est_burn        expected burn amount (in the provider unit); defaults
                  to burn_cap.amount. Used for quota-fit and lane checks.
  kernel_ref      "owner/slug" for kaggle status/output lookups; filled
                  from kernel-metadata.json at submit time when absent.
  eval_gate       {"description": str,
                   "checks": [{"metric": str, "op": ">="|"<="|">"|"<"|"==",
                                "value": number}, ...]}
                  The post-run bar (e.g. Phoenix: classifier >= 0.90,
                  hallucination <= 0.05). Recorded on the staged/launched
                  record; downstream eval enforces it before serving.
  allow_experimental  bool; required true before the EXPERIMENTAL colab
                  run path will execute anything.
  priority        int (train-queue convention; higher = sooner)
  notes           list[str] or str
"""
from __future__ import annotations

import hashlib
import json
import os
import re

from . import PROVIDERS, UNITS

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-_]*$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_OPS = (">=", "<=", ">", "<", "==")


class SpecError(ValueError):
    pass


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(1 << 20)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def load_spec(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        spec = json.load(f)
    if not isinstance(spec, dict):
        raise SpecError("job spec must be a JSON object")
    return spec


def validate_spec(spec: dict) -> list:
    """Return a list of human-readable errors ([] == valid). Pure shape
    validation; the dataset hash itself is checked by check_hash_gate()."""
    errors = []

    name = spec.get("name")
    if not isinstance(name, str) or not _NAME_RE.match(name):
        errors.append("name: required, must be a slug ([a-z0-9][a-z0-9-_]*)")

    provider = spec.get("provider")
    if provider not in PROVIDERS:
        errors.append(f"provider: required, one of {list(PROVIDERS)}")

    entrypoint = spec.get("entrypoint")
    if not isinstance(entrypoint, str) or not entrypoint:
        errors.append("entrypoint: required (kernel dir or script path)")

    cap = spec.get("burn_cap")
    if not isinstance(cap, dict):
        errors.append("burn_cap: required object {amount, unit}")
    else:
        amount = cap.get("amount")
        if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
            errors.append("burn_cap.amount: must be a number > 0")
        unit = cap.get("unit")
        if provider in UNITS and unit != UNITS[provider]:
            errors.append(
                f"burn_cap.unit: must be {UNITS[provider]!r} for provider "
                f"{provider!r}, got {unit!r}")

    est = spec.get("est_burn")
    if est is not None:
        if not isinstance(est, (int, float)) or isinstance(est, bool) or est <= 0:
            errors.append("est_burn: must be a number > 0")
        elif isinstance(cap, dict) and isinstance(cap.get("amount"), (int, float)) \
                and est > cap["amount"]:
            errors.append("est_burn: exceeds burn_cap.amount")

    ds_path = spec.get("dataset_path")
    ds_sha = spec.get("dataset_sha256")
    if ds_sha is not None and not (isinstance(ds_sha, str) and _SHA_RE.match(ds_sha.lower())):
        errors.append("dataset_sha256: must be a 64-char lowercase hex SHA-256")
    if ds_path is not None and ds_sha is None:
        errors.append("dataset_sha256: required when dataset_path is set (hash gate)")

    gate = spec.get("eval_gate")
    if gate is not None:
        if not isinstance(gate, dict) or not gate.get("description"):
            errors.append("eval_gate: object with a non-empty description required")
        for i, chk in enumerate(gate.get("checks", []) if isinstance(gate, dict) else []):
            if not isinstance(chk, dict) or not chk.get("metric") \
                    or chk.get("op") not in _OPS \
                    or not isinstance(chk.get("value"), (int, float)):
                errors.append(f"eval_gate.checks[{i}]: needs metric, op in {_OPS}, numeric value")

    if spec.get("allow_experimental") is not None \
            and not isinstance(spec.get("allow_experimental"), bool):
        errors.append("allow_experimental: must be a boolean")

    if spec.get("priority") is not None \
            and not isinstance(spec.get("priority"), int):
        errors.append("priority: must be an integer")

    return errors


def check_hash_gate(spec: dict) -> tuple:
    """Verify dataset_sha256 against dataset_path on disk.

    Returns (ok, message). When no dataset is declared, the gate is
    vacuously satisfied and the message says so."""
    ds_path = spec.get("dataset_path")
    if not ds_path:
        return True, "no dataset declared; hash gate not applicable"
    if not os.path.isfile(ds_path):
        return False, f"dataset_path not found: {ds_path}"
    actual = sha256_file(ds_path)
    expected = str(spec.get("dataset_sha256", "")).lower()
    if actual != expected:
        return False, (f"hash gate FAILED for {ds_path}: sha256 {actual}, "
                       f"spec declares {expected}")
    return True, f"hash gate OK: {ds_path} sha256={actual}"

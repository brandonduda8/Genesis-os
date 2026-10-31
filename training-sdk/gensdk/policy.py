"""Policy engine — Brandon's training fences, encoded.

Standing law encoded here (sources in README.md):
- FREE LANES AUTO-APPROVED (Brandon's 2026-10-31 order, "GPU training too
  and TPU training — no more taps, automate and maximize"): Kaggle GPU,
  Kaggle TPU, Colab (included compute units), S1-local. This SUPERSEDES
  Rule 6 in custom.legacy-kaggle/CONNECTOR.md and Rule 7 in the local-colab
  skill, both of which required a per-run tap.
- PAID SPEND STAYS FENCED: money beyond included plan credit is Brandon's
  tap. Modal runs are auto-approved ONLY while month-to-date Modal spend
  (per the gensdk ledger) plus this run's cap stays inside the $30/mo
  included credit. Anything past that is refused, not escalated silently.
- TOP-UP PURCHASES ARE NEVER AUTOMATIC: no code path in this SDK buys
  Kaggle/Colab/Modal credit. There is deliberately no purchase function.
- ONE RUN PER LANE AT A TIME: an execute-submit refuses while the lane
  has an active run whose provider status is not terminal.
- SUBMIT WITHOUT --execute ONLY STAGES: writes a staging record, calls
  no provider launch path, burns nothing.
- Quality/eval gates are not taps and are NOT waived by the Oct 31 order:
  the spec's eval_gate travels with the run record and must pass before
  any downstream serving decision.
"""
from __future__ import annotations

import json
import os

from . import UNITS, ledger as ledger_mod

SDK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(SDK_DIR, "state")
STAGED_DIR = os.path.join(STATE_DIR, "staged")
ACTIVE_PATH = os.path.join(STATE_DIR, "active.json")

FREE_LANES = ("kaggle_gpu", "kaggle_tpu", "colab", "local_s1")
MODAL_INCLUDED_CREDIT_USD = 30.0

TERMINAL_STATUSES = ("COMPLETE", "ERROR", "FAILED", "CANCELLED", "CANCELED",
                     "NOT_RUNNING", "STOPPED")


class PolicyRefusal(Exception):
    pass


def _load_active() -> dict:
    if os.path.isfile(ACTIVE_PATH):
        with open(ACTIVE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_active(active: dict) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(ACTIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(active, f, indent=2, sort_keys=True)


def active_run(provider: str) -> dict | None:
    return _load_active().get(provider)


def mark_active(provider: str, record: dict) -> None:
    active = _load_active()
    active[provider] = record
    _save_active(active)


def clear_active(provider: str) -> None:
    active = _load_active()
    active.pop(provider, None)
    _save_active(active)


def modal_month_spend() -> float:
    totals = ledger_mod.totals()
    return float(totals["month"].get("modal/usd", 0.0))


def approve_execute(spec: dict, provider_status_fn=None) -> tuple:
    """Decide whether an --execute submit may launch.

    provider_status_fn: optional callable(ref) -> status string, used to
    test whether the lane's active run has gone terminal.
    Returns (ok, reason)."""
    provider = spec["provider"]
    cap = float(spec["burn_cap"]["amount"])

    if provider == "lightning":
        return False, ("lightning is NOT_CONNECTED (no credential on file) — "
                       "refusing to launch into a lane that does not exist yet")
    if provider == "local_s1":
        return False, ("local_s1 is TRANSPORT_GATED (fleet tailnet data path; "
                       "Phase B key deposit pending) — staging only")

    if provider == "modal":
        spent = modal_month_spend()
        if spent + cap > MODAL_INCLUDED_CREDIT_USD:
            return False, (f"modal included-credit fence: month-to-date "
                           f"${spent:.2f} + cap ${cap:.2f} exceeds the "
                           f"${MODAL_INCLUDED_CREDIT_USD:.0f}/mo included credit. "
                           "Paid overage is Brandon's tap, never automatic.")

    if provider not in FREE_LANES and provider != "modal":
        return False, f"provider {provider!r} has no auto-approval rule — refusing"

    # One run per lane at a time.
    active = active_run(provider)
    if active:
        status = None
        if provider_status_fn and active.get("ref"):
            try:
                status = provider_status_fn(active["ref"])
            except Exception:
                status = None
        if status and any(t in str(status).upper() for t in TERMINAL_STATUSES):
            clear_active(provider)
        else:
            return False, (f"lane {provider} already has an active run "
                           f"({active.get('job')}, ref={active.get('ref')}, "
                           f"status={status or 'unknown'}) — one run per "
                           "lane at a time")

    lane_note = ("free lane, auto-approved under Brandon's 2026-10-31 order"
                 if provider in FREE_LANES else
                 "modal, inside included credit")
    return True, lane_note

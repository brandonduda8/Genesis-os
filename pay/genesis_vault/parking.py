"""Phase 2 'Park for growth': a parking/growth comparison for idle cash.

Rates are NEVER invented. An option carries an APY figure only after a verified
rate has been recorded with its official source and the date it was checked
(`record_verified_rate`). Unverified options show no figure and earn no
projection. A verified rate older than STALE_RATE_DAYS is marked STALE and also
earns no projection -- it must be re-checked against the official source first.

Accounts Brandon already holds come first. Nothing here opens an account,
applies for anything, or moves money; it compares, with the math shown.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .ledger import VaultError, fmt_cents

STALE_RATE_DAYS = 30
PARKING_HORIZON_DAYS = 14

_UNVERIFIED_NOTE = "Rate not verified. No figure is used until a rate is recorded from the official source."

# Accounts Brandon already holds (WO seed set), held-first. Every rate starts
# UNVERIFIED on purpose: Genesis has not checked an official rate page for any
# of these, so no APY appears anywhere until Brandon/Zane records one.
DEFAULT_OPTIONS = [
    {"name": "Cash App Savings", "provider": "Cash App", "account_slug": "cash_app",
     "held": True, "apy_percent": None, "rate_source": None, "rate_checked": None,
     "notes": _UNVERIFIED_NOTE},
    {"name": "Chime Savings", "provider": "Chime", "account_slug": "chime",
     "held": True, "apy_percent": None, "rate_source": None, "rate_checked": None,
     "notes": _UNVERIFIED_NOTE},
    {"name": "Current Savings", "provider": "Current", "account_slug": "current",
     "held": True, "apy_percent": None, "rate_source": None, "rate_checked": None,
     "notes": _UNVERIFIED_NOTE},
    {"name": "OnePay Savings", "provider": "OnePay", "account_slug": "onepay",
     "held": True, "apy_percent": None, "rate_source": None, "rate_checked": None,
     "notes": _UNVERIFIED_NOTE},
    {"name": "Robinhood cash sweep", "provider": "Robinhood", "account_slug": "robinhood",
     "held": True, "apy_percent": None, "rate_source": None, "rate_checked": None,
     "notes": _UNVERIFIED_NOTE},
    {"name": "Bank savings", "provider": "Bank", "account_slug": "bank",
     "held": True, "apy_percent": None, "rate_source": None, "rate_checked": None,
     "notes": _UNVERIFIED_NOTE},
    {"name": "PayPal Savings", "provider": "PayPal", "account_slug": "paypal",
     "held": True, "apy_percent": None, "rate_source": None, "rate_checked": None,
     "notes": _UNVERIFIED_NOTE},
]


def load_options(path: str | Path | None) -> list[dict]:
    """Options from a JSON comparison file, or the held-first defaults."""
    if path is None or not Path(path).exists():
        return [dict(o) for o in DEFAULT_OPTIONS]
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VaultError(f"parking file unreadable: {exc}") from None
    if not isinstance(raw, list) or not all(isinstance(o, dict) and "name" in o for o in raw):
        raise VaultError("parking file must be a JSON list of option objects with a name")
    return raw


def save_options(path: str | Path, options: list[dict]) -> None:
    Path(path).write_text(json.dumps(options, indent=2) + "\n", encoding="utf-8")


def record_verified_rate(options: list[dict], name: str, apy_percent: str, source: str,
                         checked: str, today: date) -> list[dict]:
    """Record a rate ONLY with an official source URL and a check date.

    Returns a new list; the input is not mutated. Refuses non-HTTPS sources,
    future check dates, and implausible figures -- a rate without provenance
    is exactly the invented number the Vault is forbidden to show."""
    if not isinstance(source, str) or not source.startswith("https://"):
        raise VaultError("rate source must be the official source URL (https://...)")
    try:
        checked_date = date.fromisoformat(checked)
    except (TypeError, ValueError):
        raise VaultError(f"check date must be YYYY-MM-DD: {checked!r}") from None
    if checked_date > today:
        raise VaultError("rate check date cannot be in the future")
    try:
        apy = Decimal(str(apy_percent))
    except InvalidOperation:
        raise VaultError(f"APY must be a number like '4.50': {apy_percent!r}") from None
    if not apy.is_finite() or apy < 0 or apy > 30:
        raise VaultError("APY percent must be between 0 and 30")
    out, found = [], False
    for o in options:
        o = dict(o)
        if o["name"] == name:
            found = True
            o.update({"apy_percent": str(apy), "rate_source": source,
                      "rate_checked": checked_date.isoformat(),
                      "notes": "Rate recorded from the official source; re-check if it goes stale."})
        out.append(o)
    if not found:
        raise VaultError(f"unknown parking option: {name!r}")
    return out


def rate_status(option: dict, today: date) -> str:
    if option.get("apy_percent") is None or option.get("rate_checked") is None:
        return "UNVERIFIED"
    age = (today - date.fromisoformat(option["rate_checked"])).days
    return "STALE" if age > STALE_RATE_DAYS else "VERIFIED"


def _counts_against(o: dict, today: date) -> bool:
    return o["due_date"] is None or date.fromisoformat(o["due_date"]) <= today + timedelta(days=PARKING_HORIZON_DAYS)


def _idle_cents(snap: dict, slug: str | None, today: date) -> int | None:
    """Cash in a held account that is not spoken for: balance minus obligations
    due within the horizon and minus the account's own buffer. None if the
    balance was never entered (unknown is shown as unknown, never as zero)."""
    if slug is None:
        return None
    acct = next((a for a in snap["accounts"] if a["slug"] == slug), None)
    if acct is None or acct["balance_cents"] is None:
        return None
    due = sum(o["amount_cents"] for o in snap["obligations"]
              if o["account"] == slug and _counts_against(o, today))
    return max(0, acct["balance_cents"] - due - acct["buffer_cents"])


def parking_comparison(snap: dict, options: list[dict], today: date) -> dict:
    """Ranked comparison. Order: held accounts with a VERIFIED rate (best APY
    first), held STALE, held UNVERIFIED, then non-held in the same order.
    A yearly projection is computed only for a VERIFIED rate on known idle
    cash: idle x APY%, with both inputs shown in the math string."""
    rows = []
    for o in options:
        status = rate_status(o, today)
        idle = _idle_cents(snap, o.get("account_slug"), today)
        projection, math = None, None
        if status == "VERIFIED" and idle is not None:
            projection = int((Decimal(idle) * Decimal(o["apy_percent"]) / Decimal(100)).to_integral_value())
            math = f"{fmt_cents(idle)} idle x {o['apy_percent']}% APY = {fmt_cents(projection)} per year (before tax/fees)"
        rows.append({"name": o["name"], "provider": o.get("provider"), "held": bool(o.get("held")),
                     "account_slug": o.get("account_slug"), "apy_percent": o.get("apy_percent"),
                     "rate_status": status, "rate_source": o.get("rate_source"),
                     "rate_checked": o.get("rate_checked"), "notes": o.get("notes", ""),
                     "idle_cents": idle, "projected_annual_cents": projection, "math": math})
    band = {"VERIFIED": 0, "STALE": 1, "UNVERIFIED": 2}
    rows.sort(key=lambda r: (not r["held"], band[r["rate_status"]],
                             -(Decimal(r["apy_percent"]) if r["apy_percent"] else Decimal(-1)), r["name"]))
    verified = [r for r in rows if r["rate_status"] == "VERIFIED"]
    return {"today": today.isoformat(), "rows": rows,
            "best_verified": verified[0]["name"] if verified else None,
            "note": "Rates appear only when recorded from an official source with a check date. "
                    "Genesis does not open accounts or move money; parking anywhere is Brandon's tap in the app."}

"""Append-only burn ledger (JSON Lines) with per-entry read-back.

One line per event:
  {ts, provider, unit, amount, kind, job, note}

kind: "estimate" (reserved at launch), "actual" (settled burn),
      "smoke" (amount 0 verification entries), "adjust".

Totals reader aggregates by provider+unit for the current ISO week and
calendar month. The ledger is the SDK's own book; provider-side truth
(Kaggle quota RPC, `colab usage`) is read live by the quota command —
the ledger never claims to be the provider's meter.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

SDK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER_PATH = os.path.join(SDK_DIR, "ledger", "burn-ledger.jsonl")


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def append(entry: dict) -> dict:
    """Append one entry and READ IT BACK from disk before returning it.
    Raises if the read-back does not match what was written."""
    record = {
        "ts": _now_iso(),
        "provider": entry.get("provider"),
        "unit": entry.get("unit"),
        "amount": float(entry.get("amount", 0)),
        "kind": entry.get("kind", "actual"),
        "job": entry.get("job"),
        "note": entry.get("note", ""),
    }
    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    with open(LEDGER_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())
    # Read-back verification: the last line on disk must equal what we wrote.
    with open(LEDGER_PATH, encoding="utf-8") as f:
        lines = [ln for ln in f.read().splitlines() if ln.strip()]
    if not lines or json.loads(lines[-1]) != record:
        raise RuntimeError("ledger read-back mismatch after append")
    return record


def read_all() -> list:
    if not os.path.isfile(LEDGER_PATH):
        return []
    out = []
    with open(LEDGER_PATH, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


def totals(entries: list | None = None, now: datetime | None = None) -> dict:
    """{week: {...}, month: {...}} of {(provider, unit): amount}, counting
    kind in (estimate, actual, adjust) — smoke entries are amount 0 and
    would not move totals either way."""
    entries = read_all() if entries is None else entries
    now = now or datetime.now(timezone.utc)
    iso_year, iso_week, _ = now.isocalendar()
    week, month = {}, {}
    for e in entries:
        if e.get("kind") == "smoke":
            continue
        try:
            ts = datetime.fromisoformat(e["ts"])
        except Exception:
            continue
        key = (e.get("provider"), e.get("unit"))
        amt = float(e.get("amount", 0))
        y, w, _ = ts.isocalendar()
        if (y, w) == (iso_year, iso_week):
            week[key] = week.get(key, 0.0) + amt
        if (ts.year, ts.month) == (now.year, now.month):
            month[key] = month.get(key, 0.0) + amt

    def fmt(d):
        return {f"{p}/{u}": round(v, 4) for (p, u), v in sorted(d.items())}

    return {"week": fmt(week), "month": fmt(month)}

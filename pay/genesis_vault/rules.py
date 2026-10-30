"""Vault rules engine: pure functions from a ledger snapshot to the daily board.

Nothing here writes to the ledger or moves money. Sweep suggestions are PREPARED
cards for Brandon to act on (or not) in the provider's own app (C8).
"""
from __future__ import annotations

from datetime import date, timedelta

from .ledger import fmt_cents

HORIZON_DAYS = 14
STALE_DAYS = 3
PREPARED = "PREPARED_ONLY"


def _due(o: dict, today: date, horizon: int) -> bool:
    """Counts against a balance if overdue, due within the horizon, or undated (unknown = assume soon)."""
    return o["due_date"] is None or date.fromisoformat(o["due_date"]) <= today + timedelta(days=horizon)


def deficit_guard(snap: dict, today: date, horizon: int = HORIZON_DAYS) -> list[dict]:
    flags = []
    for a in snap["accounts"]:
        if a["kind"] != "asset":
            continue
        due = [o for o in snap["obligations"] if o["account"] == a["slug"] and _due(o, today, horizon)]
        if not due:
            continue
        total = sum(o["amount_cents"] for o in due)
        if a["balance_cents"] is None:
            flags.append({"account": a["slug"], "level": "UNKNOWN_BALANCE", "due_cents": total,
                          "message": f"{a['name']}: {fmt_cents(total)} scheduled, balance never entered"})
            continue
        if total > a["balance_cents"]:
            short = total - a["balance_cents"]
            flags.append({"account": a["slug"], "level": "DEFICIT", "due_cents": total, "shortfall_cents": short,
                          "balance_cents": a["balance_cents"],
                          "message": f"{a['name']}: {fmt_cents(total)} scheduled vs {fmt_cents(a['balance_cents'])}"
                                     f" balance, short {fmt_cents(short)}",
                          "items": [o["id"] for o in due]})
    for o in snap["obligations"]:
        if o["account"] is None and _due(o, today, horizon):
            flags.append({"account": None, "level": "UNASSIGNED", "due_cents": o["amount_cents"], "items": [o["id"]],
                          "message": f"{o['payee']} {fmt_cents(o['amount_cents'])}: no paying account set, "
                                     "so it is not checked against any balance"})
    order = {"DEFICIT": 0, "UNKNOWN_BALANCE": 1, "UNASSIGNED": 2}
    return sorted(flags, key=lambda f: (order[f["level"]], -f.get("shortfall_cents", 0), f["account"] or "",
                                        f.get("items", [0])[0]))


def bill_calendar(snap: dict, today: date) -> list[dict]:
    rows = []
    for o in snap["obligations"]:
        if o["due_date"] is None:
            when, rank, days = "DATE UNKNOWN", 1, None
        else:
            days = (date.fromisoformat(o["due_date"]) - today).days
            when = f"OVERDUE {-days}d" if days < 0 else ("TODAY" if days == 0 else f"in {days}d")
            rank = 0 if days < 0 else 2
        rows.append({"id": o["id"], "payee": o["payee"], "amount_cents": o["amount_cents"],
                     "due_date": o["due_date"], "when": when, "account": o["account"] or "unassigned",
                     "final_notice": "final" in o["notice"].lower(), "notice": o["notice"],
                     "_sort": (rank, days if days is not None else 0, o["id"])})
    rows.sort(key=lambda r: (not r["final_notice"], r["_sort"]))
    for r in rows:
        del r["_sort"]
    return rows


def sweep_suggestions(snap: dict, today: date, horizon: int = HORIZON_DAYS) -> list[dict]:
    """'Move $X from A to B' cards for deficits, from accounts with a known surplus."""
    deficits = [f for f in deficit_guard(snap, today, horizon) if f["level"] == "DEFICIT"]
    by_slug = {a["slug"]: a for a in snap["accounts"]}
    surplus = {}
    deficit_slugs = {f["account"] for f in deficits}
    for a in snap["accounts"]:
        if a["kind"] != "asset" or a["balance_cents"] is None or a["slug"] in deficit_slugs:
            continue
        own_due = sum(o["amount_cents"] for o in snap["obligations"]
                      if o["account"] == a["slug"] and _due(o, today, horizon))
        free = a["balance_cents"] - own_due - a["buffer_cents"]
        if free > 0:
            surplus[a["slug"]] = free
    cards = []
    for f in deficits:
        need = f["shortfall_cents"]
        for src in sorted(surplus, key=lambda s: (-surplus[s], s)):
            if need == 0:
                break
            amt = min(need, surplus[src])
            if amt <= 0:
                continue
            surplus[src] -= amt
            need -= amt
            cards.append({"status": PREPARED, "from": src, "to": f["account"], "amount_cents": amt,
                          "text": f"Move {fmt_cents(amt)} from {by_slug[src]['name']} to "
                                  f"{by_slug[f['account']]['name']}",
                          "how": f"Brandon does this himself in the {by_slug[src]['name']} app, if he chooses. "
                                 "Genesis does not move money. Transfer timing and any fees are set by the "
                                 "providers; check them in the app before sending."})
        if need > 0:
            cards.append({"status": "NO_SOURCE", "from": None, "to": f["account"], "amount_cents": need,
                          "text": f"No known surplus covers {fmt_cents(need)} for {by_slug[f['account']]['name']}",
                          "how": "Update balances, or record an outcome (arranged/disputed) on the item."})
    return cards


def board(snap: dict, today: date, horizon: int = HORIZON_DAYS) -> dict:
    stale = []
    for a in snap["accounts"]:
        if a["kind"] == "asset" and a["balance_as_of"] and \
                (today - date.fromisoformat(a["balance_as_of"])).days > STALE_DAYS:
            stale.append(a["slug"])
    return {"today": today.isoformat(), "horizon_days": horizon,
            "accounts": snap["accounts"], "stale_balances": stale,
            "deficits": deficit_guard(snap, today, horizon),
            "bills": bill_calendar(snap, today),
            "sweeps": sweep_suggestions(snap, today, horizon)}

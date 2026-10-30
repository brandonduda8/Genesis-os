"""Vault rules engine: pure functions from a ledger snapshot to the daily board.

Nothing here writes to the ledger or moves money. Sweep suggestions are PREPARED
cards for Brandon to act on (or not) in the provider's own app (C8).
"""
from __future__ import annotations

from datetime import date, timedelta

from .ledger import fmt_cents

HORIZON_DAYS = 14
DEBIT_WINDOW_DAYS = 7
STALE_DAYS = 3
PREPARED = "PREPARED_ONLY"

# Cash App publishes conflicting instant-transfer fee ranges, so the fee is
# read from the in-app preview at confirm time -- never stated here as a number.
CASH_APP_FEE_WARNING = ("Cash App instant-transfer fee: read the fee preview in the Cash App app "
                        "before you confirm. Published fee ranges conflict and Genesis never "
                        "guesses the fee. A standard transfer is free but can take 1-3 business "
                        "days, so check the debit's due date before choosing.")


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


def debit_watch(snap: dict, today: date, window: int = DEBIT_WINDOW_DAYS) -> list[dict]:
    """Phase 2 Watch: dated scheduled debits due within the window (overdue
    included), in due-date order, each checked cumulatively against its target
    account's balance: debits are covered in the order they will hit until the
    balance runs out. Undated items cannot be watched and are excluded here
    (the deficit guard still flags them). Coverage is a reading of recorded
    balances, not a prediction -- a balance Brandon has not entered gives
    covered=None (unknown), never a guess."""
    by_slug = {a["slug"]: a for a in snap["accounts"]}
    dated = [o for o in snap["obligations"] if o["kind"] == "scheduled_debit" and o["due_date"]
             and date.fromisoformat(o["due_date"]) <= today + timedelta(days=window)]
    dated.sort(key=lambda o: (o["due_date"], o["id"]))
    running: dict[str, int | None] = {}
    rows = []
    for o in dated:
        slug = o["account"]
        if slug not in running:
            acct = by_slug.get(slug) if slug else None
            running[slug] = acct["balance_cents"] if acct else None
        bal = running[slug]
        covered = None if bal is None else bal >= o["amount_cents"]
        short = None if bal is None else max(0, o["amount_cents"] - bal)
        if bal is not None:
            running[slug] = bal - o["amount_cents"]
        days = (date.fromisoformat(o["due_date"]) - today).days
        rows.append({"id": o["id"], "payee": o["payee"], "amount_cents": o["amount_cents"],
                     "due_date": o["due_date"], "days_until": days,
                     "when": f"OVERDUE {-days}d" if days < 0 else ("TODAY" if days == 0 else f"in {days}d"),
                     "account": slug or "unassigned",
                     "account_name": by_slug[slug]["name"] if slug in by_slug else "unassigned",
                     "covered": covered, "shortfall_cents": short})
    return rows


def due_window(snap: dict, today: date, window: int = DEBIT_WINDOW_DAYS) -> list[dict]:
    """Every dated obligation (bills and scheduled debits) due within the window."""
    rows = [r for r in bill_calendar(snap, today)
            if r["due_date"] and date.fromisoformat(r["due_date"]) <= today + timedelta(days=window)]
    return rows


def bill_calendar(snap: dict, today: date) -> list[dict]:
    rows = []
    for o in snap["obligations"]:
        if o["due_date"] is None:
            when, rank, days = "DATE UNKNOWN", 1, None
        else:
            days = (date.fromisoformat(o["due_date"]) - today).days
            when = f"OVERDUE {-days}d" if days < 0 else ("TODAY" if days == 0 else f"in {days}d")
            rank = 0 if days < 0 else 2
        rows.append({"id": o["id"], "payee": o["payee"], "amount_cents": o["amount_cents"], "kind": o["kind"],
                     "due_date": o["due_date"], "when": when, "account": o["account"] or "unassigned",
                     "final_notice": "final" in o["notice"].lower(), "notice": o["notice"],
                     "_sort": (rank, days if days is not None else 0, o["id"])})
    rows.sort(key=lambda r: (not r["final_notice"], r["_sort"]))
    for r in rows:
        del r["_sort"]
    return rows


def sweep_suggestions(snap: dict, today: date, horizon: int = HORIZON_DAYS) -> list[dict]:
    """Ranked PREPARED_ONLY 'Move $X from A to B' cards for deficits, drawn from
    accounts with a known surplus. Ranking: earliest due date first, then the
    largest shortfall. Every card shows its math; a card sourced from Cash App
    carries the instant-fee warning (the fee is read in-app, never guessed).
    Cards are computed only -- nothing is stored and nothing is executed."""
    deficits = [f for f in deficit_guard(snap, today, horizon) if f["level"] == "DEFICIT"]
    by_slug = {a["slug"]: a for a in snap["accounts"]}

    def due_by(slug: str) -> str | None:
        dated = [o["due_date"] for o in snap["obligations"]
                 if o["account"] == slug and o["due_date"] and _due(o, today, horizon)]
        return min(dated) if dated else None

    deficits.sort(key=lambda f: (due_by(f["account"]) or "9999-99-99", -f["shortfall_cents"], f["account"]))
    surplus = {}
    deficit_slugs = {f["account"] for f in deficits}
    for a in snap["accounts"]:
        if a["kind"] != "asset" or a["balance_cents"] is None or a["slug"] in deficit_slugs:
            continue
        own_due = sum(o["amount_cents"] for o in snap["obligations"]
                      if o["account"] == a["slug"] and _due(o, today, horizon))
        free = a["balance_cents"] - own_due - a["buffer_cents"]
        if free > 0:
            surplus[a["slug"]] = {"free": free, "balance_cents": a["balance_cents"],
                                  "own_due_cents": own_due, "buffer_cents": a["buffer_cents"]}
    cards = []
    for f in deficits:
        dest = by_slug[f["account"]]
        by = due_by(f["account"])
        reason = (f"{dest['name']} has {fmt_cents(f['due_cents'])} scheduled by {by or 'an unknown date'} "
                  f"against a {fmt_cents(f['balance_cents'])} balance")
        need = f["shortfall_cents"]
        for src in sorted(surplus, key=lambda s: (-surplus[s]["free"], s)):
            if need == 0:
                break
            amt = min(need, surplus[src]["free"])
            if amt <= 0:
                continue
            s = surplus[src]
            math = (f"{dest['name']}: {fmt_cents(f['due_cents'])} due - {fmt_cents(f['balance_cents'])} balance "
                    f"= {fmt_cents(f['shortfall_cents'])} short; {by_slug[src]['name']}: "
                    f"{fmt_cents(s['balance_cents'])} balance - {fmt_cents(s['own_due_cents'])} own due "
                    f"- {fmt_cents(s['buffer_cents'])} buffer = {fmt_cents(s['free'])} free")
            s["free"] -= amt
            need -= amt
            card = {"status": PREPARED, "from": src, "to": f["account"], "amount_cents": amt,
                    "reason": reason, "math": math, "due_by": by,
                    "text": f"Move {fmt_cents(amt)} from {by_slug[src]['name']} to {dest['name']}"
                            + (f" by {by}" if by else ""),
                    "how": f"Brandon does this himself in the {by_slug[src]['name']} app, if he chooses. "
                           "Genesis does not move money. Transfer timing and any fees are set by the "
                           "providers; check them in the app before sending."}
            if by_slug[src]["institution"] == "cash_app":
                card["fee_warning"] = CASH_APP_FEE_WARNING
            cards.append(card)
        if need > 0:
            cards.append({"status": "NO_SOURCE", "from": None, "to": f["account"], "amount_cents": need,
                          "reason": reason, "math": f"{dest['name']} shortfall {fmt_cents(f['shortfall_cents'])}; "
                                                    "no other account has known free surplus to cover the rest",
                          "due_by": by,
                          "text": f"No known surplus covers {fmt_cents(need)} for {dest['name']}",
                          "how": "Update balances, or record an outcome (arranged/disputed) on the item."})
    for i, c in enumerate(cards, 1):
        c["rank"] = i
    return cards


def uncovered_items(snap: dict, today: date, horizon: int = HORIZON_DAYS) -> list[dict]:
    """Open obligations no balance covers: unassigned items, items on accounts
    whose balance was never entered, and items on accounts in deficit."""
    flags = deficit_guard(snap, today, horizon)
    bad_accounts = {f["account"] for f in flags if f["level"] in ("DEFICIT", "UNKNOWN_BALANCE")}
    watch = {r["id"]: r["covered"] for r in debit_watch(snap, today)}
    rows = []
    for o in snap["obligations"]:
        if not _due(o, today, horizon):
            continue
        if o["id"] in watch and watch[o["id"]] is True:
            continue  # the watch proves this dated debit is covered in due order
        if o["account"] is None:
            why = "no paying account set"
        elif o["id"] in watch and watch[o["id"]] is False:
            why = "account balance does not cover it"
        elif o["account"] in bad_accounts:
            why = "account balance does not cover it" if any(
                f["account"] == o["account"] and f["level"] == "DEFICIT" for f in flags) \
                else "account balance never entered"
        else:
            continue
        rows.append({"id": o["id"], "payee": o["payee"], "amount_cents": o["amount_cents"],
                     "due_date": o["due_date"], "account": o["account"], "kind": o["kind"], "why": why})
    return rows


def daily_digest(snap: dict, today: date) -> dict:
    """Phase 2 Report: the daily digest as data -- balances, debits due in the
    next 7 days, uncovered bills, and the sweep cards awaiting Brandon's tap.
    Pure function of the snapshot; computing it writes nothing."""
    b = board(snap, today)
    return {"today": b["today"],
            "balances": [{"slug": a["slug"], "name": a["name"], "balance_cents": a["balance_cents"],
                          "balance_as_of": a["balance_as_of"],
                          "stale": a["slug"] in b["stale_balances"]} for a in b["accounts"]],
            "debits_due_7d": debit_watch(snap, today),
            "obligations_due_7d": b["due_window"],
            "uncovered": uncovered_items(snap, today),
            "deficits": b["deficits"],
            "sweeps": b["sweeps"],
            "sweep_cards_waiting": sum(1 for c in b["sweeps"] if c["status"] == PREPARED),
            "stale_balances": b["stale_balances"]}


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
            "due_window": due_window(snap, today),
            "debit_watch": debit_watch(snap, today),
            "sweeps": sweep_suggestions(snap, today, horizon)}

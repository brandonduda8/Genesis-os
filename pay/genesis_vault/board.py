"""Render the daily one-screen board as plain text or a static HTML file (no server, no JS)."""
from __future__ import annotations

import html

from .ledger import fmt_cents


def _bal(a: dict) -> str:
    if a["balance_cents"] is None:
        return "not entered"
    return fmt_cents(a["balance_cents"]) + (f"  (as of {a['balance_as_of']})" if a["balance_as_of"] else "")


def _sweep_lines(cards: list[dict]) -> list[str]:
    lines = []
    for c in cards:
        lines.append(f"  #{c.get('rank', '-')} [{c['status']}] {c['text']}")
        if c.get("math"):
            lines.append(f"      math: {c['math']}")
        if c.get("fee_warning"):
            lines.append(f"      !! {c['fee_warning']}")
    return lines


def _watch_lines(rows: list[dict]) -> list[str]:
    lines = []
    for r in rows:
        cover = "covered" if r["covered"] else ("coverage unknown (balance not entered)"
                                                if r["covered"] is None else
                                                f"NOT COVERED, short {fmt_cents(r['shortfall_cents'])}")
        lines.append(f"  {r['payee']}  {fmt_cents(r['amount_cents'])}  due {r['due_date']} ({r['when']})"
                     f"  [{r['account_name']}]  {cover}")
    return lines


def render_text(b: dict) -> str:
    out = [f"GENESIS VAULT  {b['today']}  (horizon {b['horizon_days']}d)  -- Genesis never moves money --", ""]
    out.append("DEFICIT GUARD")
    out += [f"  !! {f['message']}" if f["level"] == "DEFICIT" else f"  ?? {f['level']}: {f['message']}" for f in b["deficits"]] \
        or ["  ok: no scheduled outflow exceeds its account balance"]
    out += ["", "DEBITS DUE IN 7 DAYS (watch)"]
    out += _watch_lines(b.get("debit_watch", [])) or ["  none"]
    out += ["", "BILLS (open until Brandon records an outcome)"]
    out += [f"  #{r['id']:<3} {'FINAL NOTICE ' if r['final_notice'] else ''}{r['payee']}  {fmt_cents(r['amount_cents'])}"
            f"  {r['when']}  [{r['account']}]" for r in b["bills"]] or ["  none open"]
    out += ["", "SWEEP CARDS (prepared only; Brandon's tap in the real app)"]
    out += _sweep_lines(b["sweeps"]) or ["  none"]
    out += ["", "ACCOUNTS"]
    out += [f"  {a['name']:<22} {_bal(a)}" for a in b["accounts"]]
    if b["stale_balances"]:
        out.append(f"  stale (>3 days): {', '.join(b['stale_balances'])}")
    return "\n".join(out) + "\n"


def render_digest(d: dict) -> str:
    """The Phase 2 daily digest: one screen Brandon can read in chat."""
    out = [f"GENESIS VAULT DAILY DIGEST  {d['today']}  -- Genesis never moves money --", "", "BALANCES"]
    for a in d["balances"]:
        bal = "not entered" if a["balance_cents"] is None else fmt_cents(a["balance_cents"])
        extra = f"  (as of {a['balance_as_of']}{', STALE' if a['stale'] else ''})" if a["balance_as_of"] else ""
        out.append(f"  {a['name']:<22} {bal}{extra}")
    out += ["", "DEBITS DUE IN 7 DAYS"]
    out += _watch_lines(d["debits_due_7d"]) or ["  none"]
    out += ["", "UNCOVERED BILLS"]
    out += [f"  {u['payee']}  {fmt_cents(u['amount_cents'])}  {u['why']}" for u in d["uncovered"]] or ["  none"]
    out += ["", f"SWEEP CARDS AWAITING YOUR TAP: {d['sweep_cards_waiting']}"]
    out += _sweep_lines(d["sweeps"]) or ["  none"]
    park = d.get("parking")
    if park:
        out += ["", "PARK FOR GROWTH (verified rates only; no figure = not verified)"]
        for r in park["rows"]:
            rate = f"{r['apy_percent']}% APY ({r['rate_status']}, checked {r['rate_checked']})" \
                if r["apy_percent"] else "rate not verified"
            proj = f"  -> {r['math']}" if r["math"] else ""
            out.append(f"  {r['name']:<22} {rate}{proj}")
        if park["best_verified"]:
            out.append(f"  best verified: {park['best_verified']}")
    return "\n".join(out) + "\n"


def render_html(b: dict) -> str:
    e = html.escape

    def section(title, items):
        body = "".join(f"<li>{i}</li>" for i in items) or "<li class=muted>none</li>"
        return f"<section><h2>{e(title)}</h2><ul>{body}</ul></section>"

    deficits = [f"<b>{e(f['level'])}</b> {e(f['message'])}" for f in b["deficits"]]
    watch = [f"{e(r['payee'])} {e(fmt_cents(r['amount_cents']))} &middot; due {e(r['due_date'])} ({e(r['when'])}) "
             f"&middot; {e(r['account_name'])} &middot; "
             f"{'covered' if r['covered'] else ('coverage unknown' if r['covered'] is None else 'NOT COVERED')}"
             for r in b.get("debit_watch", [])]
    bills = [f"{'<b>FINAL NOTICE</b> ' if r['final_notice'] else ''}#{r['id']} {e(r['payee'])} "
             f"{e(fmt_cents(r['amount_cents']))} &middot; {e(r['when'])} &middot; {e(r['account'])}" for r in b["bills"]]
    sweeps = [f"<b>{e(c['status'])}</b> {e(c['text'])}<br><small>{e(c['how'])}</small>"
              + (f"<br><small>{e(c['math'])}</small>" if c.get("math") else "")
              + (f"<br><b>{e(c['fee_warning'])}</b>" if c.get("fee_warning") else "") for c in b["sweeps"]]
    accts = [f"{e(a['name'])}: {e(_bal(a))}" for a in b["accounts"]]
    return ("<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width'>"
            "<meta http-equiv=Content-Security-Policy content=\"default-src 'none'; style-src 'unsafe-inline'\">"
            f"<title>Genesis Vault {e(b['today'])}</title><style>body{{font:15px system-ui;margin:16px;max-width:720px}}"
            "h2{font-size:15px;margin:18px 0 6px}li{margin:4px 0}.muted{color:#777}</style></head><body>"
            f"<h1>Genesis Vault &middot; {e(b['today'])}</h1><p class=muted>Read-only board. Genesis never moves money; "
            "every transfer is Brandon's tap in the provider's app.</p>"
            + section("Deficit guard", deficits) + section("Debits due in 7 days (watch)", watch)
            + section("Bills (open until an outcome is recorded)", bills)
            + section("Sweep cards (prepared only)", sweeps) + section("Accounts", accts) + "</body></html>\n")

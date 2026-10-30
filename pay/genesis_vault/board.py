"""Render the daily one-screen board as plain text or a static HTML file (no server, no JS)."""
from __future__ import annotations

import html

from .ledger import fmt_cents


def _bal(a: dict) -> str:
    if a["balance_cents"] is None:
        return "not entered"
    return fmt_cents(a["balance_cents"]) + (f"  (as of {a['balance_as_of']})" if a["balance_as_of"] else "")


def render_text(b: dict) -> str:
    out = [f"GENESIS VAULT  {b['today']}  (horizon {b['horizon_days']}d)  -- Genesis never moves money --", ""]
    out.append("DEFICIT GUARD")
    out += [f"  !! {f['message']}" if f["level"] == "DEFICIT" else f"  ?? {f['level']}: {f['message']}" for f in b["deficits"]] \
        or ["  ok: no scheduled outflow exceeds its account balance"]
    out += ["", "BILLS (open until Brandon records an outcome)"]
    out += [f"  #{r['id']:<3} {'FINAL NOTICE ' if r['final_notice'] else ''}{r['payee']}  {fmt_cents(r['amount_cents'])}"
            f"  {r['when']}  [{r['account']}]" for r in b["bills"]] or ["  none open"]
    out += ["", "SWEEP CARDS (prepared only; Brandon's tap in the real app)"]
    out += [f"  [{c['status']}] {c['text']}" for c in b["sweeps"]] or ["  none"]
    out += ["", "ACCOUNTS"]
    out += [f"  {a['name']:<22} {_bal(a)}" for a in b["accounts"]]
    if b["stale_balances"]:
        out.append(f"  stale (>3 days): {', '.join(b['stale_balances'])}")
    return "\n".join(out) + "\n"


def render_html(b: dict) -> str:
    e = html.escape

    def section(title, items):
        body = "".join(f"<li>{i}</li>" for i in items) or "<li class=muted>none</li>"
        return f"<section><h2>{e(title)}</h2><ul>{body}</ul></section>"

    deficits = [f"<b>{e(f['level'])}</b> {e(f['message'])}" for f in b["deficits"]]
    bills = [f"{'<b>FINAL NOTICE</b> ' if r['final_notice'] else ''}#{r['id']} {e(r['payee'])} "
             f"{e(fmt_cents(r['amount_cents']))} &middot; {e(r['when'])} &middot; {e(r['account'])}" for r in b["bills"]]
    sweeps = [f"<b>{e(c['status'])}</b> {e(c['text'])}<br><small>{e(c['how'])}</small>" for c in b["sweeps"]]
    accts = [f"{e(a['name'])}: {e(_bal(a))}" for a in b["accounts"]]
    return ("<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width'>"
            "<meta http-equiv=Content-Security-Policy content=\"default-src 'none'; style-src 'unsafe-inline'\">"
            f"<title>Genesis Vault {e(b['today'])}</title><style>body{{font:15px system-ui;margin:16px;max-width:720px}}"
            "h2{font-size:15px;margin:18px 0 6px}li{margin:4px 0}.muted{color:#777}</style></head><body>"
            f"<h1>Genesis Vault &middot; {e(b['today'])}</h1><p class=muted>Read-only board. Genesis never moves money; "
            "every transfer is Brandon's tap in the provider's app.</p>"
            + section("Deficit guard", deficits) + section("Bills (open until an outcome is recorded)", bills)
            + section("Sweep cards (prepared only)", sweeps) + section("Accounts", accts) + "</body></html>\n")

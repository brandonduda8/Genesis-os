#!/usr/bin/env python3
"""The Operator's Brief (WO §3): generated from the mirror's data, never from memory. Versioned by input digest.

  python3 mirror/brief.py --out mirror/OPERATOR-BRIEF.md [--offline]
  python3 mirror/brief.py --check mirror/OPERATOR-BRIEF.md     # FRESH / STALE (exit 1 when stale)

A cold Claude session reads the Brief first. If --check says STALE, the data changed after the Brief was built:
regenerate before trusting it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mirror as mx  # noqa: E402

AGREEMENTS = [
    "Builder ≠ reviewer ≠ verifier. Claude builds, Zane verifies, Astra reviews, Brandon certifies.",
    "Every claim carries a grade: VERIFIED / UNVERIFIED / UNKNOWN. Relayed claims are claims until verified.",
    "Corrections are issued in the same conversation the claim was made.",
    "Brandon carries orders between rooms (the relay protocol); his taps are a destination, never a bottleneck.",
    "BUILT ≠ DONE. DONE is Brandon's word, in his hands.",
    "A session ends by updating the mirror (debts, receipts, probes). A session that leaves it stale is unfinished.",
]
DOCTRINE = ["income first", "in Brandon's hands", "unblocking others", "reversibility",
            "expiring power (quotas, session expiries, link deadlines)", "WIP cap 3"]


def cell(x: Any) -> str:
    return str(x).replace("|", "\\|").replace("\n", " ")


def render(root: str = mx.DATA, *, now: Optional[dt.datetime] = None, prs: Optional[Dict[str, Any]] = None) -> str:
    now = now or dt.datetime.now(dt.timezone.utc)
    files = mx.data_files(root)
    debts = mx.load("debts.json", root)["debts"]
    open_d = [d for d in debts if d["status"] == "open"]
    bad = mx.validate(root)
    L = ["# OPERATOR'S BRIEF", "",
         f"<!-- mirror-digest: {mx.digest(files)} -->",
         f"_Built {now.strftime('%Y-%m-%d %H:%M UTC')} from mirror digest `{mx.digest(files)[:16]}` over "
         f"{len(files)} data files. Run `python3 mirror/brief.py --check <this file>`: STALE means regenerate._", ""]
    if bad:
        L += ["## ⚠ MIRROR DATA INVALID: do not trust this Brief", ""] + [f"- {b}" for b in bad] + [""]

    L += ["## 1. What is being built (in force)", "", "| Order | Rank | Grade | Where |", "|---|---|---|---|"]
    for p in mx.load("program.json", root)["in_force"]:
        L.append(f"| {cell(p['id'])} | {cell(p['rank'])} | {p['grade']} | {cell(p['where'])} |")

    L += ["", "## 2. Open debts (who owes whom)", ""]
    for who in mx.PEOPLE:
        mine = [d for d in open_d if d["debtor"] == who]
        if not mine:
            continue
        L += [f"### {who.capitalize()} owes ({len(mine)})", "", "| Id | To | What | Since | Due | Source |",
              "|---|---|---|---|---|---|"]
        for d in mine:
            due = d.get("due", "")
            if due and dt.date.fromisoformat(due) <= now.date() + dt.timedelta(days=7):
                due = f"**{due}** ⏳"
            L.append(f"| {d['id']} | {d['creditor']} | {cell(d['what'])} | {d['since']} | {due} | "
                     f"[link]({d['source']}) |")
        L.append("")

    exp = sorted((d for d in open_d if d.get("due")), key=lambda d: d["due"])
    L += ["## 3. Expiring power", ""]
    L += [f"- **{d['due']}**: {d['id']} ({d['debtor']}): {d['what']}. _{d.get('why', '')}_" for d in exp] or ["_none dated._"]

    L += ["", "## 4. Conflicts between orders (flagged, not silently chosen)", ""]
    for c in mx.load("conflicts.json", root)["conflicts"]:
        L.append(f"- **{c['id']}** ({' vs '.join(c['between'])}): {c['issue']}. **Recommend:** "
                 f"{c['recommendation']} (owner: {c['owner']})")

    L += ["", "## 5. Vantage mesh (routing reads probes, not topology)", "",
          "| Vantage | Role | Latest probe | Legs up | Declared (grade) |", "|---|---|---|---|---|"]
    for v in mx.load("vantages.json", root)["vantages"]:
        p = mx.latest_probe(v["id"], root)
        if p:
            age = int((now - mx.parse_time(p["at"])).total_seconds() // 60)
            legs = ", ".join(k for k, x in p["legs"].items() if x.get("ok")) or "none"
            pr = f"{p['at']} ({age} min ago{', STALE' if age * 60 > mx.PROBE_MAX_AGE_S else ''})"
        else:
            pr, legs = "**none**", "unknown"
        L.append(f"| {v['id']} | {cell(v['role'])} | {pr} | {legs} | {cell(', '.join(v['declared_powers']))} "
                 f"({v['declared_grade']}) |")
    L += ["", "| Work class | Routes to now | Substitutions |", "|---|---|---|"]
    for cls in mx.load("routing.json", root)["classes"]:
        r = mx.route(cls, now=now, root=root)
        to = r.get("to") or r["decision"]
        subs = "; ".join(f"{s['vantage']}: {s['skipped']}" for s in r.get("substitutions", [])) or "-"
        L.append(f"| {cls} | **{to}** | {cell(subs)} |")

    L += ["", "## 6. Minion roster (charter state)", "", "| Minion | Class | Charter | Embryo (grade) |", "|---|---|---|---|"]
    for m in mx.load("roster.json", root)["minions"]:
        L.append(f"| {m['role']} | {m['policy_class']} | {cell(mx.executable(m))} | {cell(m['embryo'])} "
                 f"({m['embryo_grade']}) |")
    L += ["", "_No minion is running from this repo. Charters are unsigned until Brandon's sitting (B-4)._"]

    L += ["", "## 7. Mirror coverage", "", "| What | Status | Where |", "|---|---|---|"]
    for s in mx.load("sources.json", root)["sources"]:
        L.append(f"| {s['what']} | {s['status']} | {cell(s.get('path') or s.get('lives'))} |")

    L += ["", "## 8. Live PRs", ""]
    if prs is None:
        L.append("_NOT READ: built offline._")
    else:
        L.append(f"_{prs['status']}, read {prs['at']}: {len(prs['prs'])} open, "
                 f"{sum(1 for p in prs['prs'] if not p['draft'])} ready for review._")
        for p in sorted(prs["prs"], key=lambda r: (r["repo"], r["number"])):
            if not p["draft"]:
                L.append(f"- READY: {p['repo']} [#{p['number']}]({p['url']}) {cell(p['title'][:80])}")
        L += [f"- NOT READ: {e}" for e in prs["errors"]]

    L += ["", "## 9. Working agreements", ""] + [f"- {a}" for a in AGREEMENTS]
    L += ["", "## 10. Choosing the next work", "", "Next-best-decision order: " + " → ".join(DOCTRINE) + "."]
    return "\n".join(L) + "\n"


def check(path: str, root: str = mx.DATA) -> str:
    with open(path) as f:
        m = re.search(r"mirror-digest: ([0-9a-f]{64})", f.read())
    if not m:
        return "STALE (no digest in file)"
    return "FRESH" if m.group(1) == mx.digest(mx.data_files(root)) else "STALE (mirror data changed since build)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--check")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    if a.check:
        s = check(a.check)
        print(s)
        return 0 if s == "FRESH" else 1
    prs = None
    if not a.offline:
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "exec"))
        import board  # noqa: E402
        prs = board.collect_prs()
    md = render(prs=prs)
    if a.out:
        with open(a.out, "w") as f:
            f.write(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Executive Board (GENESIS-EXEC-001 Phase 5, first slice): one read-only page of REAL state.

  python3 exec/board.py --baseline exec/state/baseline.json --out exec/state/BOARD.md [--html exec/state/board.html]

Sources, all read-only:
  * GitHub: every open PR in the configured repos (state, draft, mergeable, head, check runs, last comment), fetched
    live through the `gh` CLI. If gh is missing or refused, the section says NOT TESTED. It never shows stale data as
    current.
  * Baseline: the record exec/baseline.py wrote (it ran the suites). It is shown with its timestamp.
  * Owner queue: mirror/data/debts.json (the open-debts register): Brandon's and Zane's open items. Each item MUST carry a source link; an item
    without one is rejected and not shown. These are declared by agents, so the board labels them DECLARED, not
    telemetry.
Nothing here writes to any registry, and revenue is shown only as verified receipts (none are wired yet = NOT TESTED).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
import time
from typing import Any, Callable, Dict, List, Optional

REPOS = ("brandonduda8/Genesis-os", "brandonduda8/Genesis-core", "brandonduda8/genesis-player",
         "brandonduda8/astra-zane-bridge", "brandonduda8/Agent-x")


def gh_json(args: List[str], runner: Callable[..., Any] = subprocess.run) -> Any:
    p = runner(["gh", "api", *args], capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "gh failed").strip()[:200])
    return json.loads(p.stdout or "null")


def collect_prs(repos=REPOS, fetch: Callable[[List[str]], Any] = gh_json) -> Dict[str, Any]:
    rows, errors = [], []
    for repo in repos:
        prs, page = [], 1
        try:
            while True:  # paginate: a silently truncated list would still claim LIVE (audit finding 5)
                batch = fetch([f"repos/{repo}/pulls?state=open&per_page=100&page={page}"]) or []
                prs += batch
                if len(batch) < 100:
                    break
                page += 1
        except Exception as exc:
            errors.append(f"{repo}: {exc}")
            continue
        for pr in prs:
            sha = pr["head"]["sha"]
            try:
                runs = fetch([f"repos/{repo}/commits/{sha}/check-runs"]).get("check_runs", [])
                checks = {r["name"]: (r.get("conclusion") or r.get("status")) for r in runs}
                st = fetch([f"repos/{repo}/commits/{sha}/status"]) or {}
                for c in st.get("statuses", []):  # legacy commit statuses count as CI too (audit finding 6)
                    checks[f"status:{c.get('context')}"] = {"pending": "in_progress"}.get(c.get("state"), c.get("state"))
            except Exception as exc:
                checks = None
                errors.append(f"{repo}#{pr['number']} checks: {exc}")
            try:
                detail = fetch([f"repos/{repo}/pulls/{pr['number']}"])
                mergeable = detail.get("mergeable_state")
            except Exception as exc:
                mergeable = None
                errors.append(f"{repo}#{pr['number']} detail: {exc}")
            rows.append({"repo": repo.split("/")[1], "number": pr["number"], "title": pr["title"],
                         "draft": pr.get("draft", False), "author": pr["user"]["login"], "head": sha[:7],
                         "updated": pr.get("updated_at"), "url": pr["html_url"], "mergeable": mergeable,
                         "checks": checks})
    return {"status": "NOT TESTED" if errors and not rows else ("PARTIAL" if errors else "LIVE"),
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "prs": rows, "errors": errors}


def load_owner_queue(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"items": [], "rejected": [], "status": "NOT TESTED"}
    with open(path) as f:
        data = json.load(f)
    if "debts" in data:  # the mirror's open-debts register is the source of record (WO-PLATINUM §1, §3)
        kinds = {"LEVEL_C": "C"}
        data = {"items": [{"who": d["debtor"], "class": kinds.get(d.get("kind"), d.get("kind") or "VERIFY"),
                           "ask": d["what"], "why": d.get("why", ""), "source": d["source"],
                           "source_label": d["id"]}
                          for d in data["debts"] if d["status"] == "open" and d["debtor"] in ("brandon", "zane")]}
    ok, bad = [], []
    for it in data.get("items", []):
        (ok if str(it.get("source", "")).startswith("https://") and it.get("ask") and it.get("class") in ("C", "HANDS", "DECISION", "VERIFY", "RUN")
         and it.get("who", "brandon") in ("brandon", "zane") else bad).append(it)
    return {"items": ok, "rejected": bad, "status": "DECLARED"}


def ci_label(checks: Optional[Dict[str, str]]) -> str:
    if checks is None:
        return "unknown"
    if not checks:
        return "no CI"
    vals = set(checks.values())
    if vals <= {"success", "skipped", "neutral"}:
        return "green"
    if vals & {"failure", "timed_out", "cancelled", "action_required", "startup_failure", "stale", "error"}:
        return "RED: " + ",".join(sorted(k for k, v in checks.items() if v not in ("success", "skipped", "neutral")))
    return "running"


def cell(text: Any) -> str:
    """Markdown table cell: a '|' or newline in a title must not break the table (audit finding 9)."""
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_md(prs: Dict[str, Any], baseline: Optional[Dict[str, Any]], owner: Dict[str, Any]) -> str:
    L = ["# GENESIS EXECUTIVE BOARD", "",
         f"_Built {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}. Every number below is read from its source; "
         "a source that could not be read says NOT TESTED._", ""]
    for who, title in (("brandon", "Needs Brandon (Class C, his hands, decisions)"), ("zane", "Needs Zane (verify / run)")):
        items = [it for it in owner["items"] if it.get("who", "brandon") == who]
        L += [f"## {title}", "", f"_{owner['status']} by agents; each links its source._", ""]
        if items:
            L += ["| # | Class | Ask | Why | Source |", "|---|---|---|---|---|"]
            for i, it in enumerate(items, 1):
                L.append(f"| {i} | {it['class']} | {cell(it['ask'])} | {cell(it.get('why', ''))} | "
                         f"[{it.get('source_label', 'source')}]({it['source']}) |")
        else:
            L.append("_none declared._")
        L.append("")
    if owner["rejected"]:
        L.append(f"\n_{len(owner['rejected'])} declared item(s) were rejected (no https source link, or an "
                 "invalid class, owner or ask)._")
    L += ["", f"## Pull requests ({prs['status']}, read {prs['at']})", ""]
    if prs["prs"]:
        L += ["| Repo | PR | Title | Author | Draft | Merge | CI | Head |", "|---|---|---|---|---|---|---|---|"]
        for p in sorted(prs["prs"], key=lambda r: (r["repo"], r["number"])):
            L.append(f"| {p['repo']} | [#{p['number']}]({p['url']}) | {cell(p['title'][:70])} | {p['author']} | "
                     f"{'yes' if p['draft'] else 'no'} | {p['mergeable'] or 'unknown'} | {ci_label(p['checks'])} | "
                     f"`{p['head']}` |")
    for e in prs["errors"]:
        L.append(f"- NOT READ: {e}")
    L += ["", "## Test baseline", ""]
    if baseline:
        L.append(f"_Run {baseline['at']} on `{baseline['host']}`. Grades: "
                 + ", ".join(f"{k} {v}" for k, v in sorted(baseline["grades"].items())) + "_")
        L += ["", "| Suite | Grade | Commit | Result | Seconds |", "|---|---|---|---|---|"]
        for s in baseline["suites"]:
            res = s.get("reason") or ", ".join(f"{k}={v}" for k, v in (s.get("summary") or {}).items())
            L.append(f"| {s['name']} | **{s['grade']}** | `{s.get('commit', '')}` | {res} | {s.get('seconds', '')} |")
    else:
        L.append("_NOT TESTED: no baseline record supplied._")
    L += ["", "## Revenue", "", "_NOT TESTED: no verified-payment source is wired to this board. Prospects and "
          "projections are never shown as revenue._", "",
          "## Services and model providers", "",
          "_NOT TESTED from the board's host: live service and provider health comes from GHOST v2 doors and "
          "lane probes on zane-box (Genesis-os#1), once that server runs there._"]
    return "\n".join(L) + "\n"


def render_html(md: str) -> str:
    body = html.escape(md)
    return ("<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width'>"
            "<title>Genesis Executive Board</title><style>:root{--bg:#fff;--fg:#111}@media (prefers-color-scheme:"
            "dark){:root{--bg:#111;--fg:#eee}}body{background:var(--bg);color:var(--fg);font:14px/1.5 ui-monospace,"
            "monospace;margin:16px}pre{white-space:pre-wrap}</style><pre>" + body + "</pre></html>")


def main(argv: Optional[List[str]] = None) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline")
    ap.add_argument("--owner-queue", default=os.path.join(os.path.dirname(here), "mirror", "data", "debts.json"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--html")
    a = ap.parse_args(argv)
    baseline = json.load(open(a.baseline)) if a.baseline and os.path.exists(a.baseline) else None
    md = render_md(collect_prs(), baseline, load_owner_queue(a.owner_queue))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    open(a.out, "w").write(md)
    if a.html:
        open(a.html, "w").write(render_html(md))
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())

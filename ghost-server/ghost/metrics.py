"""WIP governance numbers (module 5) and the STEM scorecard (module 6).

Little's Law: L = λ·W  =>  W = L / λ. Over a window:
  L (mean WIP)   = time-weighted number of RUNNING attempts (from attempts.started_at / ended_at)
  λ (throughput) = DONE-VERIFIED completions / window
  W (cycle)      = L / λ, printed beside the MEASURED mean cycle time (first RUNNING -> DONE-VERIFIED).
If λ = 0 the cycle is printed as undefined. A number is never invented.
The board never prints DONE. DONE-VERIFIED reads "VERIFIED — awaiting Brandon". Grades follow Brandon's ladder.
"""
from __future__ import annotations

import collections
import html
import json
import os
import time
from typing import Any, Dict, List, Optional

from .registry import DONE, Registry, display_state

WINDOW_S = 7 * 86400
LADDER = ("IN BRANDON'S HANDS", "LIVE ON A MACHINE", "BUILT", "STAGED", "BLOCKED")


def self_usage() -> Dict[str, Any]:
    out: Dict[str, Any] = {"pid": os.getpid()}
    try:
        for line in open("/proc/self/status"):
            if line.startswith(("VmRSS:", "VmHWM:")):
                out[line.split(":")[0].lower() + "_kb"] = int(line.split()[1])
        ticks = os.sysconf("SC_CLK_TCK")
        f = open("/proc/self/stat").read().rsplit(")", 1)[1].split()
        out["cpu_s"] = round((int(f[11]) + int(f[12])) / ticks, 3)
    except (OSError, ValueError, IndexError):
        pass
    return out


def flow(reg: Registry, now: Optional[float] = None, window_s: float = WINDOW_S) -> Dict[str, Any]:
    now = now or reg.clock()
    t0 = now - window_s
    busy = 0.0
    for r in reg.db.execute("SELECT started_at, ended_at FROM attempts WHERE COALESCE(ended_at, ?) >= ?", (now, t0)):
        busy += max(0.0, min(r["ended_at"] or now, now) - max(r["started_at"], t0))
    mean_wip = busy / window_s
    done = [dict(r) for r in reg.db.execute(
        "SELECT job_id, created_at, first_run_at, done_at FROM jobs WHERE state=? AND done_at >= ?", (DONE, t0))]
    lam_per_h = len(done) / (window_s / 3600)
    cycles = [d["done_at"] - d["first_run_at"] for d in done if d["first_run_at"]]
    queues = [r[0] for r in reg.db.execute(
        "SELECT first_run_at - created_at FROM jobs WHERE first_run_at IS NOT NULL AND first_run_at >= ?", (t0,))]
    mean = lambda xs: (sum(xs) / len(xs)) if xs else None  # noqa: E731
    littles = (mean_wip / lam_per_h) if lam_per_h else None
    return {"window_h": round(window_s / 3600, 2), "mean_wip": round(mean_wip, 4),
            "throughput_per_h": round(lam_per_h, 4), "completions": len(done),
            "littles_cycle_h": None if littles is None else round(littles, 4),
            "measured_cycle_h": None if not cycles else round(mean(cycles) / 3600, 4),
            "mean_queue_h": None if not queues else round(mean(queues) / 3600, 4)}


def money(econ: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"rule_of_40": "PARKED — no revenue exists"}
    ltv, cac = econ.get("ltv_usd"), econ.get("cac_usd")
    out["ltv_cac"] = round(ltv / cac, 2) if isinstance(ltv, (int, float)) and isinstance(cac, (int, float)) and cac \
        else "NOT COMPUTED — no LTV/CAC data"
    burn, arr = econ.get("net_burn_usd"), econ.get("net_new_arr_usd")
    out["burn_multiple"] = round(burn / arr, 2) if isinstance(burn, (int, float)) and isinstance(arr, (int, float)) \
        and arr else "NOT COMPUTED — no burn/ARR data"
    return out


def scorecard(reg: Registry, *, now: Optional[float] = None, okrs: Optional[Dict[str, Any]] = None,
              econ: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    now = now or reg.clock()
    jobs = reg.jobs()
    by_state = collections.Counter(display_state(j) for j in jobs)
    lanes: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for j in jobs:
        lanes[j["lane"]][j["state"]] += 1
    fails = collections.Counter(r[0] or "unclassified" for r in reg.db.execute(
        "SELECT error_class FROM attempts WHERE outcome IS NOT NULL AND outcome != 'verified'"))
    power = reg.db.execute("SELECT COALESCE(SUM(cpu_s),0), COUNT(*) FROM attempts").fetchone()
    fl = flow(reg, now)
    measured = {"completions": fl["completions"], "mean_wip": fl["mean_wip"], "throughput_per_h": fl["throughput_per_h"],
                "dead_letters": by_state.get("DEAD-LETTER", 0), "queued": by_state.get("QUEUED", 0)}
    okr_rows = []
    for quarter, objectives in (okrs or {}).items():
        for o in objectives:
            for kr in o.get("key_results", []):
                m = kr.get("metric")
                okr_rows.append({"quarter": quarter, "objective": o.get("objective", ""), "kr": kr.get("kr", ""),
                                 "target": kr.get("target"), "current": measured.get(m, "UNMEASURED")})
    return {"at": now, "jobs_total": len(jobs), "by_state": dict(sorted(by_state.items())),
            "by_lane": {k: dict(v) for k, v in sorted(lanes.items())}, "flow": fl, "failure_classes": dict(fails),
            "doors": reg.door_states(), "power": {"attempt_cpu_s": round(power[0], 3), "attempts": power[1],
                                                  "server": self_usage()},
            "money": money(econ or {}), "okrs": okr_rows,
            "escalations_open": reg.db.execute("SELECT COUNT(*) FROM escalations WHERE state='AWAITING-BRANDON'").fetchone()[0],
            "ledger": reg.verify_ledger(),
            "dead_letter": [{"job_id": j["job_id"], "title": j["title"]} for j in jobs if j["state"] == "DEAD-LETTER"]}


def _fmt(v: Any) -> str:
    return "undefined — 0 completions in window" if v is None else str(v)


def _label(state: str) -> str:
    return "VERIFIED — awaiting Brandon" if state == DONE else state


def render_text(sc: Dict[str, Any]) -> str:
    f = sc["flow"]
    lines = [f"GHOST SERVER v2 — STEM scorecard @ {time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime(sc['at']))}",
             f"ledger: {'INTACT' if sc['ledger']['ok'] else 'BROKEN'} ({sc['ledger']['records']} records) · "
             f"escalations awaiting Brandon: {sc['escalations_open']}", "", f"JOBS ({sc['jobs_total']})"]
    lines += [f"  {_label(k):<40} {v}" for k, v in sc["by_state"].items()]
    lines += ["", f"FLOW (window {f['window_h']} h) — Little's Law W = L / λ",
              f"  mean WIP L          {f['mean_wip']}", f"  throughput λ / h    {f['throughput_per_h']}",
              f"  W = L/λ (h)         {_fmt(f['littles_cycle_h'])}", f"  measured cycle (h)  {_fmt(f['measured_cycle_h'])}",
              f"  mean queue (h)      {f['mean_queue_h'] if f['mean_queue_h'] is not None else 'no job has started'}",
              "", "DOORS"]
    if not sc["doors"]:
        lines.append("  no probe recorded yet")
    for name, d in sc["doors"].items():
        legs = " ".join(f"{k}={'ok' if v.get('ok') else v.get('error_class')}" for k, v in d.get("legs", {}).items())
        lines.append(f"  {name:<10} {d.get('verdict', '?'):<8} breaker={d.get('breaker', '?'):<9} {legs}")
    lines += ["", "FAILURE CLASSES"] + ([f"  {k:<14} {v}" for k, v in sc["failure_classes"].items()] or ["  none"])
    p = sc["power"]
    lines += ["", "POWER", f"  attempt CPU s {p['attempt_cpu_s']} over {p['attempts']} attempts · server RSS "
              f"{p['server'].get('vmrss_kb', '?')} kB · server CPU {p['server'].get('cpu_s', '?')} s",
              "", "MONEY (staged)"] + [f"  {k:<14} {v}" for k, v in sc["money"].items()]
    lines += ["", "OKRs"] + ([f"  {o['quarter']} · {o['objective']} · {o['kr']}: {o['current']} / {o['target']}"
                              for o in sc["okrs"]] or ["  none configured"])
    if sc["dead_letter"]:
        lines += ["", "DEAD-LETTER (Brandon-visible)"] + [f"  {d['job_id']} {d['title'][:70]}" for d in sc["dead_letter"]]
    lines += ["", "Grades follow Brandon's ladder: " + " / ".join(LADDER) + ". This board certifies nothing — Brandon certifies."]
    return "\n".join(lines)


def render_html(sc: Dict[str, Any]) -> str:
    body = html.escape(render_text(sc))
    data = html.escape(json.dumps(sc, default=str))
    return ("<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width'>"
            "<title>GHOST scorecard</title><style>:root{--bg:#fff;--fg:#111}@media (prefers-color-scheme:dark)"
            "{:root{--bg:#111;--fg:#eee}}body{background:var(--bg);color:var(--fg);font:14px/1.45 ui-monospace,monospace;"
            "margin:16px}pre{white-space:pre-wrap}</style><pre>" + body + "</pre>"
            "<script type=application/json id=data>" + data + "</script></html>")

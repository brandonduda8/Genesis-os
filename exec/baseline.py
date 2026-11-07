#!/usr/bin/env python3
"""Executive baseline: run every configured test suite and RECORD what actually happened.

  python3 exec/baseline.py --config exec/suites.json --out exec/state/baseline.json

Each suite is an argv list (no shell) run in its repo directory under a timeout. The record holds the commit tested,
the exit code, the duration, a parsed summary (unittest "Ran N … OK/FAILED", pytest "N passed, M failed"), and a
SHA-256 of the full log. A suite whose repo or interpreter is missing is NOT TESTED, never PASS.
GENESIS-EXEC-001 §7: PASS / FAIL / PARTIAL / NOT TESTED, from evidence only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

_UNITTEST = re.compile(r"^Ran (\d+) tests? in [\d.]+s\s*\n\s*\n?(OK|FAILED)(?: \(([^)]*)\))?", re.M)
_PYTEST = re.compile(r"(\d+) (passed|failed|skipped|errors?)")
_PYTEST_LINE = re.compile(r"^[= ]*((?:\d+ (?:passed|failed|skipped|errors?|warnings?|deselected|xfailed|xpassed|"
                          r"subtests passed)(?:, )?)+) in [\d.]+s", re.M)


def parse_summary(log: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    m = list(_UNITTEST.finditer(log))
    if m:
        last = m[-1]
        out["ran"] = int(last.group(1))
        for part in (last.group(3) or "").split(","):
            k, _, v = part.strip().partition("=")
            if v.isdigit():
                out[k] = int(v)
        out["ok"] = int(last.group(2) == "OK")
        return out
    lines = _PYTEST_LINE.findall(log)  # the summary line, wherever it sits (warnings can follow it)
    tail = lines[-1] if lines else ""
    for n, kind in _PYTEST.findall(tail):
        out[{"error": "errors"}.get(kind, kind)] = out.get(kind, 0) + int(n)
    return out


_FAILED_ID = re.compile(r"^(?:FAILED|ERROR) (\S+)", re.M)


def failed_ids(log: str) -> List[str]:
    """pytest's short summary lines ("FAILED tests/a.py::test_x - ..."), as node ids."""
    return sorted({m.split(" - ")[0] for m in _FAILED_ID.findall(log)})


def grade(rc: Optional[int], summary: Dict[str, int], known_env_failures=(), failed: Optional[List[str]] = None,
          pass_evidence: bool = False) -> str:
    """Evidence only (audited 2026-10-31, findings 1-3):
    PASS    rc 0 AND tests demonstrably ran (a parsed count > 0, or the suite's own pass marker matched)
    PARTIAL rc 1 (test failures, not a crash) AND tests ran AND every failure is a documented environment failure,
            matched BY NAME (never by count)
    FAIL    anything else that ran: crashes (rc 2+), collection errors, zero tests, unknown failures
    """
    if rc is None:
        return "NOT TESTED"
    ran = summary.get("ran", 0) + summary.get("passed", 0)
    if rc == 0:
        return "PASS" if (ran > 0 or pass_evidence) else "FAIL"
    known = set(known_env_failures or ())
    if rc == 1 and ran > 0 and failed and known and set(failed) <= known and not summary.get("errors"):
        return "PARTIAL"
    return "FAIL"


def git_head(path: str) -> str:
    """Short HEAD, suffixed '+dirty' when the tree has uncommitted changes (the tested code isn't that commit)."""
    try:
        head = subprocess.run(["git", "-C", path, "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "-C", path, "status", "--porcelain"], capture_output=True, text=True,
                               timeout=10).stdout.strip()
        return head + ("+dirty" if head and dirty else "")
    except (OSError, subprocess.SubprocessError):
        return ""


def run_suite(s: Dict[str, Any], root: str, py: str = sys.executable) -> Dict[str, Any]:
    cwd = os.path.join(root, s["cwd"])
    s = dict(s, argv=[py if a == "{py}" else a for a in s["argv"]])
    rec = {"name": s["name"], "repo": s.get("repo", ""), "cwd": s["cwd"], "argv": s["argv"]}
    exe = s["argv"][0]
    missing = [r for r in s.get("requires", []) if not os.path.exists(os.path.join(cwd, r))]
    if os.path.isdir(cwd) and missing:  # e.g. a suite that lives on a branch that isn't checked out
        return dict(rec, rc=None, grade="NOT TESTED", commit=git_head(cwd),
                    reason=f"not on the checked-out branch: {', '.join(missing)}")
    if not os.path.isdir(cwd) or (os.path.sep in exe and not os.path.exists(os.path.join(cwd, exe))
                                  and not os.path.exists(exe)):
        return dict(rec, rc=None, grade="NOT TESTED", reason=f"missing: {cwd if not os.path.isdir(cwd) else exe}")
    t0 = time.monotonic()
    try:
        p = subprocess.run(s["argv"], cwd=cwd, capture_output=True, text=True, timeout=s.get("timeout", 900),
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        rc, log = p.returncode, p.stdout + p.stderr
    except FileNotFoundError as exc:
        return dict(rec, rc=None, grade="NOT TESTED", reason=f"interpreter missing: {exc}")
    except subprocess.TimeoutExpired as exc:
        rc, log = 124, ((exc.stdout or b"") if isinstance(exc.stdout, bytes) else (exc.stdout or "").encode()).decode(
            "utf-8", "replace") + "\nTIMEOUT"
    summary = parse_summary(log)
    fails = failed_ids(log)
    marker = s.get("pass_regex")
    evidence = bool(marker and re.search(marker, log))
    return dict(rec, rc=rc, seconds=round(time.monotonic() - t0, 1), commit=git_head(cwd), summary=summary,
                failed_ids=fails, grade=grade(rc, summary, s.get("known_env_failures", ()), fails, evidence),
                known_env_failures=s.get("known_env_failures", []),
                log_sha256=hashlib.sha256(log.encode("utf-8", "replace")).hexdigest(), log_tail=log[-600:])


def run_all(config: Dict[str, Any], root: str, py: str = sys.executable) -> Dict[str, Any]:
    results = [run_suite(s, root, py) for s in config["suites"]]
    counts: Dict[str, int] = {}
    for r in results:
        counts[r["grade"]] = counts.get(r["grade"], 0) + 1
    return {"schema": "genesis-exec-baseline/1", "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "host": os.uname().nodename, "root": root, "grades": counts, "suites": results}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "suites.json"))
    ap.add_argument("--root", help="directory holding the repo checkouts (default: config's root)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--py", default=sys.executable, help="python for {py} suites (e.g. a venv with pytest)")
    a = ap.parse_args(argv)
    cfg = json.load(open(a.config))
    rep = run_all(cfg, os.path.expanduser(a.root or cfg.get("root", "~")), a.py)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(rep, f, indent=1)
    for r in rep["suites"]:
        print(f"{r['grade']:<11} {r['name']:<28} {r.get('summary', '') or r.get('reason', '')}")
    return 0 if all(r["grade"] in ("PASS", "PARTIAL") for r in rep["suites"]) else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""The Mirror (WO-PLATINUM-MIRROR-MESH-MINIONS-001 §1-§4): one hash-addressed truth for every vantage.

Data lives in mirror/data/ as small JSON files, versioned by git (the Genesis-os repo discipline), hashed into
MANIFEST.json so that any two copies (S1 primary, zane-box replica, a session checkout) reconcile BY HASH:
  python3 mirror/mirror.py validate                  # every record obeys its law (exit 1 on any violation)
  python3 mirror/mirror.py manifest                  # rewrite data/MANIFEST.json
  python3 mirror/mirror.py reconcile A_ROOT B_ROOT   # same / only-in-one / CONFLICT (never auto-resolved)
  python3 mirror/mirror.py route repo_work [--exclude claude-cloud]
Routing reads PROBES, never declared topology (fresh-probe law): a vantage with no probe, a stale probe, or a down
leg is skipped, and the skip is recorded as a substitution in the answer.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
PEOPLE = ("brandon", "zane", "astra", "claude", "cody")
GRADES = ("VERIFIED", "UNVERIFIED", "UNKNOWN")
# Mirrors ghost-server/ghost/gates.py on main (test_register_matches_ghost keeps them equal).
REGISTER_CLASSES = ("training", "engineering", "ghost_operations", "ace_pipeline", "operational_communications",
                    "research")
CLASS_CEILING = {"ghost_operations": ("ghost_unblock", "ghost_requeue", "ghost_cancel", "ghost_install",
                                      "ghost_forward", "ghost_complete")}
LEVEL_C_WORDS = ("spend", "pay", "purchase", "transfer", "trade", "publish", "sign_financial", "account",
                 "credential", "contract", "delete", "deploy_prod", "expose", "disable_security")
PROBE_MAX_AGE_S = 2 * 3600


class Violation(ValueError):
    pass


def load(name: str, root: str = DATA) -> Any:
    with open(os.path.join(root, name)) as f:
        return json.load(f)


def parse_time(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


# ---------------- validation (the laws, as code) ----------------
def check_debts(doc: Dict[str, Any]) -> List[str]:
    bad, seen = [], set()
    for d in doc.get("debts", []):
        i = d.get("id", "?")
        if i in seen:
            bad.append(f"debt {i}: duplicate id")
        seen.add(i)
        if d.get("debtor") not in PEOPLE or d.get("creditor") not in PEOPLE + ("operation",):
            bad.append(f"debt {i}: debtor/creditor must be one of {PEOPLE} (+operation as creditor)")
        if d.get("debtor") == d.get("creditor"):
            bad.append(f"debt {i}: owed to oneself")
        if not str(d.get("source", "")).startswith("https://"):
            bad.append(f"debt {i}: needs an https source (no source, no debt)")
        if not d.get("what") or not d.get("since"):
            bad.append(f"debt {i}: what + since required")
        if d.get("status") not in ("open", "done"):
            bad.append(f"debt {i}: status open|done")
        if d.get("status") == "done" and not d.get("done_evidence"):
            bad.append(f"debt {i}: done without evidence")
        if d.get("debtor") == "brandon" and d.get("kind") not in ("LEVEL_C", "HANDS", "DECISION"):
            bad.append(f"debt {i}: Brandon's list holds only LEVEL_C / HANDS / DECISION items")
    return bad


def check_roster(doc: Dict[str, Any]) -> List[str]:
    bad, ids = [], {m.get("id") for m in doc.get("minions", [])}
    for m in doc.get("minions", []):
        i = m.get("id", "?")
        if m.get("policy_class") not in REGISTER_CLASSES:
            bad.append(f"minion {i}: class {m.get('policy_class')!r} is not in the register (a minion that cannot "
                       "state its charter does not run)")
        for a in m.get("actions", []):
            if any(w in a for w in LEVEL_C_WORDS):
                bad.append(f"minion {i}: action {a!r} is Level C; no minion holds Level C")
        if m.get("verifier") in (i, None) or m.get("verifier") in ids:
            bad.append(f"minion {i}: verifier must be a separate seat (not itself, not another minion)")
        if m.get("max_instances") != 1:
            bad.append(f"minion {i}: max_instances must be 1 (roster growth is Brandon's amendment)")
        if len(m.get("credentials", [])) > 1:
            bad.append(f"minion {i}: more than one credential; charters name the minimum")
        if not m.get("resume"):
            bad.append(f"minion {i}: must say how it resumes from the mirror after being killed")
    return bad


def executable(m: Dict[str, Any]) -> str:
    ceiling = CLASS_CEILING.get(m["policy_class"])
    if not ceiling:
        return f"STAGED: GHOST defines no action ceiling for class {m['policy_class']!r} yet"
    missing = [a for a in m.get("actions", []) if a not in ceiling]
    return "CHARTERABLE" if not missing else f"STAGED: actions outside the ceiling: {missing}"


def check_vantages(vdoc: Dict[str, Any], rdoc: Dict[str, Any]) -> List[str]:
    bad, ids = [], {v["id"] for v in vdoc.get("vantages", [])}
    for cls, spec in rdoc.get("classes", {}).items():
        for v in spec.get("order", []):
            if v not in ids:
                bad.append(f"route {cls}: unknown vantage {v}")
        if cls != "level_c" and "brandon" in spec.get("order", []):
            bad.append(f"route {cls}: Brandon is a Level C destination only, never a work queue")
    for v in vdoc.get("vantages", []):
        if v.get("declared_grade") not in GRADES:
            bad.append(f"vantage {v['id']}: declared powers need a grade")
    return bad


def validate(root: str = DATA) -> List[str]:
    out = check_debts(load("debts.json", root)) + check_roster(load("roster.json", root))
    out += check_vantages(load("vantages.json", root), load("routing.json", root))
    for p in load("program.json", root).get("in_force", []):
        if p.get("grade") not in GRADES:
            out.append(f"program {p.get('id')}: needs a grade")
    return out


# ---------------- manifest + reconcile (failover law: by hash, never by argument) ----------------
def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def data_files(root: str) -> Dict[str, str]:
    out = {}
    for base, _, files in os.walk(root):
        for f in sorted(files):
            if f.endswith(".json") and f != "MANIFEST.json":
                p = os.path.join(base, f)
                out[os.path.relpath(p, root)] = sha256(p)
    return dict(sorted(out.items()))


def digest(files: Dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def write_manifest(root: str = DATA, now: Optional[str] = None) -> Dict[str, Any]:
    files = data_files(root)
    m = {"generated_at": now or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "digest": digest(files), "files": files}
    with open(os.path.join(root, "MANIFEST.json"), "w") as f:
        json.dump(m, f, indent=1)
        f.write("\n")
    return m


def reconcile(a: str, b: str) -> Dict[str, Any]:
    fa, fb = data_files(a), data_files(b)
    same = sorted(k for k in fa if fb.get(k) == fa[k])
    conflict = sorted(k for k in fa if k in fb and fb[k] != fa[k])
    return {"same": same, "only_a": sorted(set(fa) - set(fb)), "only_b": sorted(set(fb) - set(fa)),
            "conflict": conflict, "clean": not conflict}


# ---------------- routing ----------------
def latest_probe(vantage: str, root: str = DATA) -> Optional[Dict[str, Any]]:
    p = os.path.join(root, "probes", f"{vantage}.json")
    return load(os.path.join("probes", f"{vantage}.json"), root) if os.path.exists(p) else None


def route(work_class: str, *, now: Optional[dt.datetime] = None, exclude: tuple = (), root: str = DATA,
          max_age_s: int = PROBE_MAX_AGE_S) -> Dict[str, Any]:
    spec = load("routing.json", root)["classes"].get(work_class)
    if spec is None:
        return {"decision": "POLICY_QUESTION", "reason": f"novel work class {work_class!r}: ask once, with a "
                "recommendation, then it is policy"}
    if work_class == "level_c":
        return {"decision": "PACKET", "to": "brandon", "reason": "Level C is a one-touch packet, never routed work"}
    now = now or dt.datetime.now(dt.timezone.utc)
    subs = []
    for v in spec["order"]:
        if v in exclude:
            subs.append({"vantage": v, "skipped": "excluded (builder cannot be its own verifier)"})
            continue
        p = latest_probe(v, root)
        if not p:
            subs.append({"vantage": v, "skipped": "no probe on record"})
            continue
        age = (now - parse_time(p["at"])).total_seconds()
        if age > max_age_s:
            subs.append({"vantage": v, "skipped": f"probe stale ({int(age // 60)} min old)"})
            continue
        down = [leg for leg in spec.get("needs", []) if p.get("legs", {}).get(leg, {}).get("ok") is not True]
        if down:
            subs.append({"vantage": v, "skipped": f"legs not proven up: {down}"})
            continue
        return {"decision": "ROUTE", "to": v, "probe_at": p["at"], "substitutions": subs}
    return {"decision": "HOLD", "reason": "no capable vantage is proven up; the job holds safely", "substitutions": subs}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    sub.add_parser("manifest")
    r = sub.add_parser("reconcile")
    r.add_argument("a")
    r.add_argument("b")
    t = sub.add_parser("route")
    t.add_argument("work_class")
    t.add_argument("--exclude", action="append", default=[])
    x = ap.parse_args(argv)
    if x.cmd == "validate":
        bad = validate()
        print("\n".join(bad) if bad else "mirror data valid")
        return 1 if bad else 0
    if x.cmd == "manifest":
        out: Any = write_manifest()
    elif x.cmd == "reconcile":
        out = reconcile(x.a, x.b)
    else:
        out = route(x.work_class, exclude=tuple(x.exclude))
    print(json.dumps(out, indent=1))
    return 0 if out.get("clean", True) else 1


if __name__ == "__main__":
    sys.exit(main())

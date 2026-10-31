"""gensdk CLI: providers | quota | submit | status | ledger.

  gensdk providers                 per-provider state (LIVE/STAGED/...)
  gensdk quota                     live quota/balance per provider
  gensdk submit <spec.json>        STAGE a job (default; burns nothing)
  gensdk submit <spec.json> --execute
                                   policy-check, then launch for real
  gensdk status [--provider P] [--ref R]
                                   active run(s) + provider-reported status
  gensdk ledger [--append-smoke]  weekly/monthly burn totals

Everything prints JSON for machine consumers, except `providers`, which
prints a readable table (state is what Brandon asked to see).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from . import UNITS, jobspec, ledger as ledger_mod, policy
from .providers import all_providers, get_provider
from .providers.base import ProviderError


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def cmd_providers(_args) -> int:
    for name, prov in all_providers().items():
        st = prov.status()
        print(f"{name:<12} {st['state']:<16} {st.get('detail', '')}")
    return 0


def cmd_quota(_args) -> int:
    out = {}
    for name, prov in all_providers().items():
        try:
            out[name] = prov.quota()
        except Exception as exc:  # a dead lane must not kill the report
            out[name] = {"provider": name, "available": None,
                         "note": f"quota error: {exc}"}
    print(json.dumps(out, indent=2))
    return 0


def _stage(spec: dict, spec_path: str, reason: str) -> dict:
    os.makedirs(policy.STAGED_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = os.path.join(policy.STAGED_DIR, f"{spec['name']}-{stamp}.json")
    record = {"staged_at": _now(), "spec_path": os.path.abspath(spec_path),
              "spec": spec, "verdict": f"STAGED — {reason}"}
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    record["staged_file"] = dest
    return record


def cmd_submit(args) -> int:
    try:
        spec = jobspec.load_spec(args.spec)
    except Exception as exc:
        print(f"spec load failed: {exc}", file=sys.stderr)
        return 2
    errors = jobspec.validate_spec(spec)
    if errors:
        for e in errors:
            print(f"INVALID SPEC: {e}", file=sys.stderr)
        return 2
    ok, msg = jobspec.check_hash_gate(spec)
    if not ok:
        print(f"REFUSED: {msg}", file=sys.stderr)
        return 1
    print(f"hash gate: {msg}", file=sys.stderr)

    if not args.execute:
        record = _stage(spec, args.spec,
                        "no --execute; staging only, nothing launched, nothing burned")
        print(json.dumps(record, indent=2))
        return 0

    provider = get_provider(spec["provider"])

    def status_fn(ref):
        return provider.job_status(ref)

    ok, reason = policy.approve_execute(spec, provider_status_fn=status_fn)
    if not ok:
        print(f"POLICY REFUSAL: {reason}", file=sys.stderr)
        return 1
    print(f"policy: APPROVED — {reason}", file=sys.stderr)

    try:
        result = provider.submit(spec)
    except ProviderError as exc:
        print(f"LAUNCH FAILED: {exc}", file=sys.stderr)
        return 1

    est = float(spec.get("est_burn", spec["burn_cap"]["amount"]))
    entry = ledger_mod.append({
        "provider": spec["provider"], "unit": UNITS[spec["provider"]],
        "amount": est, "kind": "estimate", "job": spec["name"],
        "note": f"launch estimate; ref={result.get('ref')}; settle with an "
                "'actual' entry when the run completes"})
    policy.mark_active(spec["provider"], {
        "job": spec["name"], "ref": result.get("ref"),
        "launched_at": _now(), "eval_gate": spec.get("eval_gate")})
    print(json.dumps({"launched": True, "provider": spec["provider"],
                      "job": spec["name"], "ref": result.get("ref"),
                      "detail": result.get("detail"),
                      "ledger_estimate": entry}, indent=2))
    return 0


def cmd_status(args) -> int:
    active = policy._load_active()
    if args.provider:
        names = [args.provider]
    else:
        names = list(all_providers())
    out = {}
    for name in names:
        prov = get_provider(name)
        rec = active.get(name)
        live = None
        if args.ref:
            try:
                live = prov.job_status(args.ref)
            except ProviderError as exc:
                live = f"error: {exc}"
        elif rec and rec.get("ref"):
            try:
                live = prov.job_status(rec["ref"])
            except ProviderError as exc:
                live = f"error: {exc}"
            if live and any(t in str(live).upper()
                            for t in policy.TERMINAL_STATUSES):
                policy.clear_active(name)
                rec = dict(rec, cleared="terminal status observed; lane freed")
        out[name] = {"active": rec, "provider_status": live}
    print(json.dumps(out, indent=2))
    return 0


def cmd_ledger(args) -> int:
    if args.append_smoke:
        rec = ledger_mod.append({
            "provider": "gensdk", "unit": "n/a", "amount": 0.0,
            "kind": "smoke", "job": "gensdk-smoke",
            "note": "append + read-back verification entry (amount 0; "
                    "excluded from totals)"})
        print(json.dumps({"appended_and_read_back": rec}, indent=2))
    totals = ledger_mod.totals()
    print(json.dumps({"ledger": ledger_mod.LEDGER_PATH,
                      "entries": len(ledger_mod.read_all()),
                      "week": totals["week"], "month": totals["month"]},
                     indent=2))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gensdk",
                                 description="Genesis Training SDK CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("providers", help="per-provider state").set_defaults(fn=cmd_providers)
    sub.add_parser("quota", help="live quota/balance per provider").set_defaults(fn=cmd_quota)

    p = sub.add_parser("submit", help="stage a job spec (default) or launch it")
    p.add_argument("spec", help="path to the job-spec JSON")
    p.add_argument("--execute", action="store_true",
                   help="actually launch after the policy check; without "
                        "this flag the job is only staged and nothing burns")
    p.set_defaults(fn=cmd_submit)

    p = sub.add_parser("status", help="active runs and provider status")
    p.add_argument("--provider", default=None)
    p.add_argument("--ref", default=None, help="explicit provider ref to query")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("ledger", help="burn ledger totals")
    p.add_argument("--append-smoke", action="store_true",
                   help="append a zero-amount smoke entry (proves append "
                        "+ read-back) before printing totals")
    p.set_defaults(fn=cmd_ledger)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())

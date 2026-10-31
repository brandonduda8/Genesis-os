#!/usr/bin/env python3
"""GHOST SERVER v2 command line. Stdlib only; `cryptography` optional (without it, Level B + envelopes fail closed).

  python3 ghostd.py [--config config/ghost.json] <command>
    migrate                      import ghost/queue/*.json|Q-*.md (read-only on the files) with lineage
    status | board [--html F]    registry by state | STEM scorecard (text, or static HTML file)
    provenance GHOST-Q-NNN       complete history of one job (one query)
    ledger-verify                re-hash the evidence ledger chain
    doors-probe                  one acceptance-trio round through every configured door
    start | run | stop           daemon (double fork) | foreground | SIGTERM via pidfile
    keepalive [--restart]        exit 1 if heartbeat > 300 s old; --restart starts the daemon (for */5 cron)
    gate KIND GHOST-Q-NNN [--grant F] [--receipt REL]   commit-gated action (Level A/B; Level C is refused)
    add JOB.json                 add a job (deterministic id required; Level C text enters BLOCKED + escalates)
    escalations                  Level C requests awaiting Brandon
    keygen PRIVATE_PATH          new Ed25519 key (0600, never overwrites); prints the public key
    sign --key F --issuer I --action A --job J [--principal P]   produce a signed receipt (JSON on stdout)
    mcp                          read-only MCP stdio server
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from ghost import codeact, gates, legacy, mcp, metrics, signing  # noqa: E402
from ghost.registry import BLOCKED, QUEUED, Registry, display_state  # noqa: E402
from ghost.server import Config, Server, main_daemon  # noqa: E402


def _complete(reg: Registry, *, job_id: str, actor: str, now: float, receipt_path: str = "", receipts_root: str = "",
              **_):
    job = reg.get(job_id)
    if not job or job["state"] != "RUNNING":
        raise gates.Refused(f"{job_id} is not RUNNING")
    ok, detail = codeact.verify(job["verifier"], job_id=job_id, receipts_root=receipts_root, receipt_path=receipt_path)
    if ok:
        reg.add_artifact(job_id, os.path.join(receipts_root, receipt_path), produced_by=actor)
    return reg.finish_attempt(job_id, actor=actor, verified=ok, outcome="verified" if ok else "verifier_failed",
                              error_class="" if ok else "verifier_failed", error="" if ok else detail)


if "ghost_complete" not in gates.EXECUTORS:
    gates.register_executor("ghost_complete", _complete)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ghostd", description="GHOST SERVER v2")
    ap.add_argument("--config", default=os.path.join(HERE, "config", "ghost.json"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("migrate", "status", "ledger-verify", "doors-probe", "start", "run", "stop", "escalations", "mcp"):
        sub.add_parser(c)
    b = sub.add_parser("board")
    b.add_argument("--html")
    p = sub.add_parser("provenance")
    p.add_argument("job_id")
    k = sub.add_parser("keepalive")
    k.add_argument("--restart", action="store_true")
    g = sub.add_parser("gate")
    g.add_argument("kind")
    g.add_argument("job_id")
    g.add_argument("--grant")
    g.add_argument("--receipt", default="")
    a = sub.add_parser("add")
    a.add_argument("job_file")
    kg = sub.add_parser("keygen")
    kg.add_argument("private_path")
    s = sub.add_parser("sign")
    for f in ("--key", "--issuer", "--action", "--job"):
        s.add_argument(f, required=True)
    s.add_argument("--principal", default=f"os:{gates.current_user()}")
    s.add_argument("--ttl", type=int, default=120)
    args = ap.parse_args(argv)

    if args.cmd == "keygen":
        print(signing.keygen(args.private_path))
        return 0
    if args.cmd == "sign":
        print(json.dumps(signing.sign(signing.load_private(args.key), issuer=args.issuer, action=args.action,
                                      subject=args.job, principal=args.principal, now=time.time(), ttl_s=args.ttl)))
        return 0

    cfg = Config(args.config)
    if args.cmd in ("start", "run"):
        return main_daemon(args.config, foreground=args.cmd == "run")
    if args.cmd == "stop":
        pid = int(open(os.path.join(cfg.state, "ghostd.pid")).read().strip() or 0)
        os.kill(pid, signal.SIGTERM)
        print(f"SIGTERM -> {pid}")
        return 0

    reg = Registry(cfg.db)
    if args.cmd == "keepalive":
        age = reg.heartbeat_age()
        fresh = age is not None and age <= 300
        print(json.dumps({"heartbeat_age_s": None if age is None else round(age, 1), "ok": fresh}))
        if not fresh and args.restart:
            reg.ledger("keepalive_restart", f"os:{gates.current_user()}", {"age_s": age})
            return main_daemon(args.config)
        return 0 if fresh else 1
    if args.cmd == "migrate":
        gate = gates.Gate(reg, policy_path=cfg.policy, escalation_dir=os.path.join(cfg.state, "escalations"))
        rep = legacy.migrate(reg, os.path.join(cfg.receipts_root, "ghost", "queue"),
                             os.path.join(cfg.root, "config", "legacy_requires.json"),
                             actor=f"os:{gates.current_user()}", gate=gate, repo_root=cfg.receipts_root)
        print(json.dumps(rep, indent=1))
        return 0
    if args.cmd == "status":
        for j in reg.jobs():
            print(f"{j['job_id']:<12} {display_state(j):<42} {j['lane']:<9} {j['assignee']:<9} {j['title'][:60]}")
        return 0
    if args.cmd == "board":
        sc = metrics.scorecard(reg, okrs=json.load(open(cfg.okrs)) if os.path.exists(cfg.okrs) else None,
                               econ=json.load(open(cfg.economics)) if os.path.exists(cfg.economics) else None)
        if args.html:
            open(args.html, "w").write(metrics.render_html(sc))
        print(metrics.render_text(sc))
        return 0
    if args.cmd == "provenance":
        print(json.dumps(reg.provenance(args.job_id), indent=1, default=str))
        return 0
    if args.cmd == "ledger-verify":
        r = reg.verify_ledger()
        print(json.dumps(r))
        return 0 if r["ok"] else 2
    if args.cmd == "escalations":
        for r in reg.db.execute("SELECT * FROM escalations ORDER BY esc_id"):
            print(json.dumps(dict(r)))
        return 0
    if args.cmd == "doors-probe":
        srv = Server(cfg)
        for name, door in srv.doors.items():
            t = door.probe_trio()
            reg.set_door_state(name, {**t, **door.snapshot()})
            reg.ledger("door_probe", f"os:{gates.current_user()}", {"door": name, "verdict": t["verdict"],
                                                                    "legs": t["legs"]})
            print(json.dumps(t))
        return 0
    if args.cmd == "gate":
        gate = gates.Gate(reg, policy_path=cfg.policy, verifier=signing.Verifier.from_file(cfg.trusted_keys),
                          escalation_dir=os.path.join(cfg.state, "escalations"))
        grant = json.load(open(args.grant)) if args.grant else None
        job = reg.get(args.job_id)
        text = f"{job['title']} {job['spec'].get('command_or_ref', '')}" if job else ""
        try:
            out = gate.commit(args.kind, job_id=args.job_id, text=text, grant=grant, now=time.time(),
                              receipt_path=args.receipt, receipts_root=cfg.receipts_root)
        except gates.Refused as exc:
            print(json.dumps({"refused": str(exc), "escalation": exc.escalation}))
            return 3
        print(json.dumps({"ok": True, "state": display_state(out) if isinstance(out, dict) and "state" in out else out},
                         default=str))
        return 0
    if args.cmd == "add":
        job = json.load(open(args.job_file))
        level = gates.classify("codeact_run" if job.get("executor") == "codeact" else "release_envelope",
                               f"{job.get('title', '')} {json.dumps(job.get('spec', {}))}")
        job["level"] = level
        state, reason = (BLOCKED, "level-c-brandon") if level == "C" else (QUEUED, "")
        out = reg.add_job(job, actor=f"os:{gates.current_user()}", source=os.path.abspath(args.job_file),
                          state=state, blocked_reason=reason)
        if level == "C":
            gates.Gate(reg, escalation_dir=os.path.join(cfg.state, "escalations"))._escalate(
                "add_job", job["job_id"], "job text classified Level C", f"os:{gates.current_user()}")
        print(json.dumps({"job_id": out["job_id"], "state": display_state(out)}))
        return 0
    if args.cmd == "mcp":
        mcp.serve(reg)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
GENESIS MASTER RUNTIME — the connection layer for the whole fleet.

One terminal entrypoint for Zane and every agent (Cody/OpenCode, Claude,
Astra, Prime, Hermes, ZeroClaw, Glimmer, Kai/Janus) that reads the fleet's
REAL sources of truth — the GHOST job queue, the ACE job-storm registry,
the agent registry — and answers four questions honestly:

    status    Where does everything stand right now?
    board     Same, written to state/BOARD.md (the living board)
    plan      What is dispatchable next, under the WIP cap of 3?
    dispatch  Write a store-and-forward envelope for one job, BY ID
    verify    Which claims have receipts, and which are still unverified?

LAWS ENCODED (not documented — enforced):
  * Grades follow Brandon's ladder: IN BRANDON'S HANDS / LIVE ON A MACHINE /
    BUILT / STAGED / BLOCKED. Nothing here prints DONE except Brandon's
    acceptance, which this tool never asserts.
  * Executor claims sit UNVERIFIED until a receipt file is read back.
  * Registry mutations match deterministic entry IDs ONLY (the 2026-10-31
    mutation law, bought twice). Free-text scans may FIND candidate IDs;
    the write set is always enumerated ID-by-ID and read back in the same run.
  * Human-relay jobs (requires_path = brandon-relay) are NEVER dispatched —
    they are Brandon's hands, not executable work.
  * The runtime writes ONLY inside its own directory (state/, outbox/).
  * Level C is untouched: no money moves, nothing publishes, no account is
    created, no signature is applied, ever, by this tool.
  * A provider 429 is a hard stop for that scope — dispatch envelopes carry
    the fence to the executor; they never retry around one.

Stdlib only. Runs on zane-box, penguin, or S1 unchanged:
    python3 master_runtime.py status|board|plan|verify
    python3 master_runtime.py dispatch GHOST-Q-003
"""

import glob
import json
import os
import socket
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
GENESIS = os.path.dirname(HERE)  # genesis-os/
STATE_DIR = os.path.join(HERE, "state")
OUTBOX_DIR = os.path.join(HERE, "outbox")

LEVEL_C_MARKERS = ("spend", "publish", "payment", "move money", "sign the",
                   "create account", "enroll")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def resolve(rel):
    return os.path.normpath(os.path.join(GENESIS, rel))


def lanes():
    return load_json(os.path.join(HERE, "lanes.json"), {})


def agents():
    return load_json(os.path.join(HERE, "agents.json"), {}).get("agents", [])


# ------------------------------------------------------------- data sources

def ghost_jobs(cfg):
    qdir = resolve(cfg["sources"]["ghost_queue_dir"])
    jobs = []
    for path in sorted(glob.glob(os.path.join(qdir, "*.json"))):
        job = load_json(path)
        if job and "id" in job:
            jobs.append(job)
    for path in sorted(glob.glob(os.path.join(qdir, "Q-*.md"))):
        with open(path) as f:
            head = f.read(600)
        title = next((ln.lstrip("# ").strip() for ln in head.splitlines()
                      if ln.startswith("#")), os.path.basename(path))
        jobs.append({"id": os.path.basename(path).split("-")[0] + "-" +
                     os.path.basename(path).split("-")[1],
                     "title": title, "status": "QUEUED (md work order)",
                     "target_host": "see work order",
                     "requires_path": "see work order",
                     "receipt_target": "per work order §reporting"})
    return jobs


def ace(cfg):
    reg = load_json(resolve(cfg["sources"]["ace_registry"]), {"entries": []})
    entries = reg.get("entries", [])
    by_state = {}
    for e in entries:
        by_state.setdefault(e.get("state", "?"), []).append(e)
    return entries, by_state


def probes(cfg):
    out = []
    for p in cfg.get("probes", []):
        s = socket.socket()
        s.settimeout(1.5)
        try:
            s.connect((p["host"], p["port"]))
            state = "OPEN"
        except Exception:
            state = "DARK (door unanswered — not proof the service is dead)"
        finally:
            s.close()
        out.append((p["name"], p["host"], p["port"], state))
    return out


# ------------------------------------------------------------------ render

def render(cfg):
    entries, by_state = ace(cfg)
    jobs = ghost_jobs(cfg)
    lines = []
    lines.append("# GENESIS MASTER BOARD")
    lines.append("")
    lines.append(f"Generated: {now_iso()} by master_runtime.py — grades follow "
                 "Brandon's ladder; DONE is asserted nowhere in this file.")
    lines.append("")
    lines.append("## Workstreams (WIP cap = %d, Brandon's RESET order)"
                 % cfg.get("wip_cap", 3))
    for ws in cfg.get("workstreams", []):
        lines.append(f"- **{ws['id']} {ws['name']}** — owner {ws['owner']} — "
                     f"{ws['state']}")
    lines.append("")
    lines.append("## GHOST queue (store-and-forward; drains on heal windows)")
    for j in jobs:
        lines.append(f"- **{j['id']}** [{j.get('status', '?')}] "
                     f"{j.get('title', '')} → {j.get('target_host', '?')}")
    lines.append("")
    lines.append("## Job storm / ACE (the money lane)")
    counts = ", ".join(f"{k} {len(v)}" for k, v in sorted(by_state.items()))
    lines.append(f"- Registry: {len(entries)} entries — {counts}")
    for e in by_state.get("SUBMITTED", []):
        lines.append(f"- SUBMITTED {e['id']}: {e.get('title') or e.get('role') or ''}"
                     f" @ {e.get('employer', '')}")
    for st in ("STAGED", "FOLLOWUP", "CHECK-FIRST", "PARKED-FOR-BRANDON"):
        for e in by_state.get(st, []):
            lines.append(f"- {st} {e['id']}: {e.get('title') or e.get('role') or ''}"
                         f" @ {e.get('employer', '')}")
    lines.append("")
    lines.append("## Agents (registry: agents.json)")
    for a in agents():
        lines.append(f"- **{a['name']}** — {a['role']} — surface: {a['surface']}")
    lines.append("")
    lines.append("## Lane probes (this host, TCP connect, 1.5s)")
    for name, host, port, state in probes(cfg):
        lines.append(f"- {name} {host}:{port} — {state}")
    lines.append("")
    lines.append("## Parked behind the WIP cap / Brandon's sequence")
    for p in cfg.get("parked_behind_wip", []):
        lines.append(f"- {p}")
    lines.append("")
    return "\n".join(lines)


# ------------------------------------------------------------------ verify

def receipt_found(target):
    if not target:
        return False
    t = target.split(" (")[0].strip()
    if "<" in t:  # templated name like RECEIPT-X-<run-date>.md
        t = t.split("<")[0] + "*.md"
    return bool(glob.glob(resolve(t)) or glob.glob(t))


def verify(cfg):
    jobs = ghost_jobs(cfg)
    entries, by_state = ace(cfg)
    lines = ["# VERIFY — claims vs receipts (read-back law)", ""]
    for j in jobs:
        st = str(j.get("status", ""))
        if st.upper().startswith(("DONE", "COMPLETE")):
            ok = receipt_found(j.get("receipt_target", ""))
            verdict = "RECEIPT READ BACK" if ok else "CLAIM UNVERIFIED — no receipt on disk"
        elif "brandon-relay" in str(j.get("requires_path", "")):
            verdict = "HUMAN RELAY — waits on Brandon's hands, not a transport failure"
        else:
            verdict = "QUEUED — nothing claimed yet"
        lines.append(f"- {j['id']} [{st}] {verdict}")
    lines.append("")
    subs = by_state.get("SUBMITTED", [])
    with_ev = [e for e in subs if e.get("evidence")]
    lines.append(f"- ACE SUBMITTED entries carrying confirmation evidence: "
                 f"{len(with_ev)}/{len(subs)}")
    for e in subs:
        if not e.get("evidence"):
            lines.append(f"  - {e['id']} SUBMITTED without recorded evidence — "
                         "treat as UNVERIFIED until the confirmation is filed")
    return "\n".join(lines)


# -------------------------------------------------------------------- plan

def plan(cfg):
    jobs = ghost_jobs(cfg)
    entries, by_state = ace(cfg)
    lines = ["# PLAN — next dispatchable work (WIP cap enforced)", ""]
    lines.append("## GHOST queue")
    for j in jobs:
        rp = str(j.get("requires_path", ""))
        if "brandon-relay" in rp:
            kind = "BRANDON'S HANDS (relay — never dispatched by the runtime)"
        elif "GREEN" in rp or "reachable" in rp or "path" in rp:
            kind = "TRANSPORT-GATED — fires on the first heal window"
        else:
            kind = "REVIEW — read the work order before dispatch"
        lines.append(f"- {j['id']}: {kind} — {j.get('title', '')}")
    lines.append("")
    lines.append("## ACE actionable (verified-fit inventory drives cadence; "
                 "50/day is a ceiling, never a quota)")
    for st in ("STAGED", "FOLLOWUP", "CHECK-FIRST"):
        for e in by_state.get(st, []):
            lines.append(f"- {st} {e['id']}: {e.get('employer', '')} — "
                         f"{(e.get('next_step') or '')[:140]}")
    lines.append("")
    lines.append("## Brandon's hands (the only DONE gate)")
    lines.append("- Session B: Prime lineup apply + Glimmer Colab Run-all")
    lines.append("- Penguin Phase B NetBird key deposit ('key in')")
    lines.append("- Integrity packet: his-hands items (I-9, W-4 elections, "
                 "payroll banking, safety training/quiz)")
    lines.append("- Fiverr own-network sign-in (bot wall) — or park it")
    return "\n".join(lines)


# ---------------------------------------------------------------- dispatch

def assert_inside(path):
    real = os.path.realpath(path)
    if not real.startswith(os.path.realpath(HERE) + os.sep):
        raise SystemExit(f"REFUSED: write outside the runtime dir: {path}")


def dispatch(cfg, job_id):
    jobs = ghost_jobs(cfg)
    match = [j for j in jobs if j["id"] == job_id]  # by-ID only, per the law
    if not match:
        raise SystemExit(f"REFUSED: no queue entry with exact id {job_id!r}. "
                         "Free-text matches are never dispatched.")
    job = match[0]
    rp = str(job.get("requires_path", ""))
    if "brandon-relay" in rp:
        raise SystemExit(f"REFUSED: {job_id} is a human relay (Brandon's "
                         "hands). The runtime never dispatches those.")
    text = json.dumps(job).lower()
    for marker in LEVEL_C_MARKERS:
        if marker in text and "never" not in text and "no " not in text:
            print(f"WARNING: {job_id} text mentions {marker!r} — envelope "
                  "carries the Level C fence verbatim for the executor.")
    os.makedirs(OUTBOX_DIR, exist_ok=True)
    env = {"envelope": "genesis-master-runtime/1", "dispatched_at": now_iso(),
           "job": job,
           "fences": ["$0 — no spend, no accounts, no publishing, no money "
                      "movement, no signatures",
                      "Level C is Brandon's tap, always",
                      "a provider 429 is a hard stop for that scope",
                      "receipt from a real run, read back, or the claim "
                      "stays UNVERIFIED",
                      "mutations match deterministic entry IDs only"]}
    out = os.path.join(OUTBOX_DIR, job_id + ".json")
    assert_inside(out)
    with open(out, "w") as f:
        json.dump(env, f, indent=1)
    with open(out) as f:  # read-back law, applied to ourselves
        back = json.load(f)
    assert back["job"]["id"] == job_id
    print(f"DISPATCHED {job_id} → {os.path.relpath(out, GENESIS)} "
          f"(read back OK; envelope waits in the outbox for its executor's "
          f"next contact — store-and-forward, nothing was sent anywhere)")


# --------------------------------------------------------------------- cli

def main():
    cfg = lanes()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd in ("status", "board"):
        board = render(cfg)
        print(board)
        if cmd == "board":
            os.makedirs(STATE_DIR, exist_ok=True)
            out = os.path.join(STATE_DIR, "BOARD.md")
            assert_inside(out)
            with open(out, "w") as f:
                f.write(board)
            print(f"\n[board written: {os.path.relpath(out, GENESIS)}]")
    elif cmd == "plan":
        print(plan(cfg))
    elif cmd == "verify":
        print(verify(cfg))
    elif cmd == "dispatch":
        if len(sys.argv) < 3:
            raise SystemExit("usage: master_runtime.py dispatch <JOB-ID>")
        dispatch(cfg, sys.argv[2])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()

"""The GHOST server process: scheduler + WIP caps (module 5), drain-on-heal, recovery + daemon (module 9).

One process, one tick loop (default 5 s sleep). Per tick:
  heartbeat -> due door trio probes / reach probes -> drain inbox envelopes -> poll CodeAct runs ->
  release eligible jobs under the per-lane and global WIP caps -> ledger heartbeat every 5 min.
Executors:
  manual  - release = a signed `task` envelope into spool/out/<assignee>/ (Level A). The job counts only when a
            `result` envelope arrives AND the deterministic verifier (normally `receipt`) passes locally.
  codeact - sandboxed script (codeact.py); counts only when the job's fixed verifier passes.
"""
from __future__ import annotations

import fcntl
import json
import os
import signal
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from . import codeact, envelope, gates, metrics
from .doors import Door, load_doors, tcp_probe
from .registry import BLOCKED, QUEUED, RUNNING, Registry
from .signing import HAVE_CRYPTO, Verifier, load_private

DEFAULT_PRIORITY = ["builds", "proofs", "installs", "sends", "probes", "ops", "batch-inference"]  # F1 > proofs > installs
FRESH_S = 900  # a probe result older than this is not evidence of health


class Config:
    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        self.root = os.path.dirname(os.path.dirname(self.path))  # ghost-server/
        c = json.load(open(path))
        rel = lambda p: p if not p or os.path.isabs(p) else os.path.normpath(os.path.join(self.root, p))  # noqa: E731
        self.raw = c
        self.name = c["identity"]["name"]
        self.key_file = rel(c["identity"].get("key_file", ""))
        self.db, self.spool, self.state = rel(c["db"]), rel(c["spool"]), rel(c.get("state_dir", "state"))
        self.doors_file, self.policy = rel(c.get("doors", "")), rel(c.get("policy", ""))
        self.trusted_keys, self.receipts_root = rel(c.get("trusted_keys", "")), rel(c.get("receipts_root", ".."))
        self.lane_probe_file = rel(c.get("lane_probes", ""))
        self.charter, self.revoked = rel(c.get("policy_charter", "")), rel(c.get("policy_revoked", ""))
        self.okrs, self.economics = rel(c.get("okrs", "")), rel(c.get("economics", ""))
        lanes = c.get("lanes", {})
        self.caps, self.default_cap = lanes.get("caps", {}), int(lanes.get("default_cap", 3))
        self.global_cap, self.priority = int(lanes.get("global_cap", 3)), lanes.get("priority", DEFAULT_PRIORITY)
        self.reach = c.get("reach", {})
        self.tick_s, self.probe_every_s = float(c.get("tick_s", 5)), float(c.get("probe_every_s", 600))
        self.reach_every_s, self.manual_lease_s = float(c.get("reach_every_s", 120)), float(c.get("manual_lease_s", 86400))


def _load(path: str) -> Dict[str, Any]:
    return json.load(open(path)) if path and os.path.exists(path) else {}


class Server:
    def __init__(self, cfg: Config, clock=time.time, doors: Optional[Dict[str, Door]] = None):
        self.cfg, self.clock = cfg, clock
        os.makedirs(cfg.state, mode=0o700, exist_ok=True)
        self.reg = Registry(cfg.db, clock=clock)
        self.verifier = Verifier.from_file(cfg.trusted_keys)
        self.gate = gates.Gate(self.reg, policy_path=cfg.policy, verifier=self.verifier,
                               escalation_dir=os.path.join(cfg.state, "escalations"),
                               charter_path=cfg.charter, revoked_path=cfg.revoked)
        self.doors = doors if doors is not None else (load_doors(cfg.doors_file, clock) if cfg.doors_file else {})
        self.key = load_private(cfg.key_file) if HAVE_CRYPTO and cfg.key_file and os.path.exists(cfg.key_file) else None
        self.facts: Dict[str, Tuple[bool, float, str]] = {}  # term -> (ok, at, detail)
        self.next_probe: Dict[str, float] = {}
        self.runs: Dict[str, codeact.Run] = {}
        self.last_ledger_hb, self.stopping = 0.0, False
        lane_cfg = _load(cfg.lane_probe_file)
        self.lane_probes = {p["name"]: p for p in lane_cfg.get("probes", [])}

    # ------------------------------------------------------------------ boot / recovery
    def boot(self) -> Dict[str, Any]:
        chain = self.reg.verify_ledger()
        if not chain["ok"]:
            open(os.path.join(self.cfg.state, "LEDGER_BROKEN"), "w").write(json.dumps(chain))
            raise SystemExit(f"ledger chain broken at seq {chain['broken_at_seq']}; refusing to start")
        self.reg.ledger("boot", f"ghostd:{self.cfg.name}", {"pid": os.getpid(), "ledger_records": chain["records"],
                                                            "crypto": HAVE_CRYPTO, "netns": codeact.netns_available()})
        recovered = self.reg.recover(in_process_executors=("codeact",))
        self.reg.heartbeat(os.getpid())
        return {"chain": chain, "recovered": recovered}

    # ------------------------------------------------------------------ facts (requirements)
    def _fact(self, term: str) -> Tuple[bool, str]:
        kind, _, name = term.partition(":")
        if kind == "human":
            return False, f"waits on Brandon ({name})"
        if kind == "file":
            path = os.path.normpath(os.path.join(self.cfg.receipts_root, name))
            inside = path.startswith(os.path.normpath(self.cfg.receipts_root) + os.sep)
            return (inside and os.path.exists(path), f"{name} {'present' if inside and os.path.exists(path) else 'absent'}")
        if kind == "job":
            j = self.reg.get(name)
            return (bool(j and j["state"] == "DONE-VERIFIED"), f"{name} is {j['state'] if j else 'unknown'}")
        ok, at, detail = self.facts.get(term, (False, 0.0, "not probed yet"))
        if at and self.clock() - at > FRESH_S:
            return False, f"stale probe ({detail})"
        return ok, detail

    def requirements_met(self, requires: List[Any]) -> Tuple[bool, str]:
        for term in requires:
            options = term["any"] if isinstance(term, dict) else [term]
            results = [self._fact(o) for o in options]
            if not any(ok for ok, _ in results):
                return False, " | ".join(f"{o}: {d}" for o, (_, d) in zip(options, results))
        return True, "all requirements met"

    def probe_due(self, now: float) -> None:
        for name, door in self.doors.items():
            key = f"door:{name}"
            if now < self.next_probe.get(key, 0) or not door.allow():
                continue
            t = door.probe_trio()
            self.facts[key] = (t["healed"], now, t["verdict"])
            prev = self.reg.door_states().get(name, {}).get("verdict")
            self.reg.set_door_state(name, {**t, **door.snapshot()})
            if prev != t["verdict"]:
                self.reg.ledger("door_state", f"ghostd:{self.cfg.name}", {"door": name, "from": prev, "to": t["verdict"],
                                                                         "legs": {k: v.get("error_class") or "ok" for k, v in t["legs"].items()}})
            self.next_probe[key] = now + (self.cfg.probe_every_s if t["healed"] else 60)
        for name, r in self.cfg.reach.items():
            key = f"reach:{name}"
            if now >= self.next_probe.get(key, 0):
                p = tcp_probe(r.get("host", ""), int(r.get("port", 22)))
                self.facts[key] = (p["ok"], now, p["error_class"] or f"{p['ms']} ms")
                self.next_probe[key] = now + self.cfg.reach_every_s
        for name, p in self.lane_probes.items():
            key = f"lane:{name}"
            if now >= self.next_probe.get(key, 0):
                r = tcp_probe(p["host"], int(p["port"]))
                self.facts[key] = (r["ok"], now, r["error_class"] or f"{r['ms']} ms")
                self.next_probe[key] = now + self.cfg.reach_every_s

    # ------------------------------------------------------------------ scheduling under WIP caps
    def select(self, now: float) -> List[str]:
        running = self.reg.jobs(RUNNING)
        per_lane: Dict[str, int] = {}
        for j in running:
            per_lane[j["lane"]] = per_lane.get(j["lane"], 0) + 1
        total = len(running)
        order = {l: i for i, l in enumerate(self.cfg.priority)}
        queued = sorted(self.reg.jobs(QUEUED), key=lambda j: (order.get(j["lane"], 99), j["job_id"]))
        picked = []
        for j in queued:
            if total >= self.cfg.global_cap:
                break
            cap = int(self.cfg.caps.get(j["lane"], self.cfg.default_cap))
            if per_lane.get(j["lane"], 0) >= cap or j["next_eligible_at"] > now or j["level"] == "C":
                continue
            ok, _ = self.requirements_met(j["requires"])
            if ok:
                picked.append(j["job_id"])
                per_lane[j["lane"]] = per_lane.get(j["lane"], 0) + 1
                total += 1
        return picked

    def release(self, job_id: str, now: float) -> str:
        job = self.reg.get(job_id)
        assert job
        if job["executor"] == "codeact":
            spec = job["spec"]
            try:
                run = codeact.start(spec["script"], spec.get("inputs", {}), allow_network=bool(spec.get("network")))
            except PermissionError as exc:
                self.reg.transition(job_id, BLOCKED, actor=f"ghostd:{self.cfg.name}", transform="sandbox_unavailable",
                                    expect_state=QUEUED, expect_version=job["version"], reason=str(exc))
                return "blocked"
            self.reg.start_attempt(job_id, actor=f"ghostd:{self.cfg.name}", lease_s=codeact.WALL_S + 30)
            self.runs[job_id] = run
            return "started"
        if job["executor"] == "manual":
            if self.key is None:
                return "no-signing-key"  # envelopes must be signed; stays QUEUED, visible on the board
            self.gate.commit("release_envelope", job_id=job_id, now=now, text=f"{job['title']} "
                             f"{job['spec'].get('command_or_ref', '')}", server=self)
            return "released"
        return "unknown-executor"

    def _release_envelope(self, reg: Registry, *, job_id: str, actor: str, now: float, server: "Server", **_: Any):
        job = reg.get(job_id)
        reg.start_attempt(job_id, actor=actor, lease_s=self.cfg.manual_lease_s)
        env = envelope.make(kind="task", frm=self.cfg.name, to=job["assignee"] or "unassigned", job_id=job_id,
                            payload={"title": job["title"], "spec": job["spec"], "receipt_target": job["receipt_target"],
                                     "fences": job["spec"].get("fence_notes", ""),
                                     "authority": "fences travel with the job; queuing never authorizes"},
                            key=self.key, now=now)
        path = envelope.spool_write(self.cfg.spool, "out", env["to"], env)
        reg.record_envelope(env, "out", "spooled")
        reg.ledger("drain_released", actor, {"envelope": env["id"], "to": env["to"], "spool": os.path.basename(path)},
                   job_id)
        return env

    # ------------------------------------------------------------------ results
    def apply_result(self, env: Dict[str, Any]) -> str:
        job = self.reg.get(env.get("job_id", ""))
        if not job or job["state"] != RUNNING:
            return "ignored-not-running"
        if job["assignee"] and env["from"] != job["assignee"]:
            return "ignored-wrong-sender"
        receipt = env["payload"].get("receipt_path", "")
        ok, detail = codeact.verify(job["verifier"], job_id=job["job_id"], receipts_root=self.cfg.receipts_root,
                                    receipt_path=receipt, trio_healed=lambda d: self._fact(f"door:{d}")[0])
        if ok and receipt:
            self.reg.add_artifact(job["job_id"], os.path.join(self.cfg.receipts_root, receipt),
                                  produced_by=f"peer:{env['from']}")
        self.reg.finish_attempt(job["job_id"], actor=f"peer:{env['from']}", verified=ok,
                                outcome="verified" if ok else "verifier_failed",
                                error_class="" if ok else "verifier_failed", error="" if ok else detail)
        return f"{'verified' if ok else 'rejected'}: {detail}"

    def poll_runs(self) -> None:
        import resource
        for job_id, run in list(self.runs.items()):
            before = resource.getrusage(resource.RUSAGE_CHILDREN)
            res = run.poll()
            if res is None:
                continue
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            cpu = (after.ru_utime + after.ru_stime) - (before.ru_utime + before.ru_stime)
            del self.runs[job_id]
            job = self.reg.get(job_id)
            if res["timed_out"] or res["rc"] != 0:
                ok, detail = False, f"script rc={res['rc']} timed_out={res['timed_out']}: {res['stderr'][-300:]}"
            else:
                ok, detail = codeact.verify(job["verifier"], job_id=job_id, workdir=res["workdir"],
                                            trio_healed=lambda d: self._fact(f"door:{d}")[0])
            out_json = os.path.join(res["workdir"], "out", "result.json")
            if ok and os.path.exists(out_json):
                self.reg.add_artifact(job_id, out_json, produced_by="codeact")
            self.reg.finish_attempt(job_id, actor=f"ghostd:{self.cfg.name}", verified=ok,
                                    outcome="verified" if ok else "verifier_failed",
                                    error_class="" if ok else ("timeout" if res["timed_out"] else "verifier_failed"),
                                    error="" if ok else detail, cpu_s=cpu, rss_kb=after.ru_maxrss)

    # ------------------------------------------------------------------ the tick
    def tick(self) -> Dict[str, Any]:
        now = self.clock()
        self.reg.heartbeat(os.getpid())
        self.probe_due(now)
        inbox = envelope.drain_inbox(self.reg, self.cfg.spool, verifier=self.verifier, me=self.cfg.name, now=now,
                                     apply=self.apply_result, ack_key=self.key)
        self.poll_runs()
        released = {}
        for jid in self.select(now):
            try:
                released[jid] = self.release(jid, now)
            except (gates.Refused, Exception) as exc:  # one bad job never stalls the others
                released[jid] = f"refused: {exc}"
                self.reg.ledger("release_failed", f"ghostd:{self.cfg.name}", {"error": str(exc)}, jid)
        if now - self.last_ledger_hb >= 300:
            self.reg.ledger("heartbeat", f"ghostd:{self.cfg.name}", metrics.self_usage())
            self.last_ledger_hb = now
        return {"inbox": inbox, "released": released}

    def run_forever(self) -> None:
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "stopping", True))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "stopping", True))
        while not self.stopping:
            try:
                self.tick()
            except Exception as exc:  # a bad tick is ledgered, never fatal, never a busy loop
                self.reg.ledger("tick_error", f"ghostd:{self.cfg.name}", {"error": f"{type(exc).__name__}: {exc}"})
            end = time.monotonic() + self.cfg.tick_s
            while not self.stopping and time.monotonic() < end:
                time.sleep(min(0.5, end - time.monotonic()))
        self.reg.ledger("shutdown", f"ghostd:{self.cfg.name}", {"pid": os.getpid(), "clean": True})
        self.reg.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")


# ---------------------------------------------------------------------- daemon law: double fork, flock pidfile
def daemonize(pidfile: str, logfile: str) -> int:
    """Double fork + setsid; returns 0 in the daemon. The parent returns the daemon's pid. Never bare nohup."""
    r, w = os.pipe()
    if os.fork() > 0:
        os.close(w)
        pid = int(os.read(r, 32) or b"0")
        os.close(r)
        return pid
    os.close(r)
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    os.umask(0o077)
    os.chdir("/")
    fd = os.open(logfile, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    null = os.open(os.devnull, os.O_RDONLY)
    os.dup2(null, 0)
    os.dup2(fd, 1)
    os.dup2(fd, 2)
    os.write(w, str(os.getpid()).encode())
    os.close(w)
    return 0


def acquire_pidfile(pidfile: str):
    fh = open(pidfile, "a+")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        raise SystemExit("another ghostd holds the pidfile lock; refusing to start a second instance")
    fh.seek(0)
    fh.truncate()
    fh.write(str(os.getpid()))
    fh.flush()
    return fh  # keep the handle open for the life of the process


def install_release_executor(server: Server) -> None:
    if "release_envelope" not in gates.EXECUTORS:
        gates.register_executor("release_envelope", lambda reg, **kw: kw["server"]._release_envelope(reg, **kw))


def main_daemon(cfg_path: str, foreground: bool = False) -> int:
    cfg = Config(cfg_path)
    os.makedirs(cfg.state, mode=0o700, exist_ok=True)
    pidfile, logfile = os.path.join(cfg.state, "ghostd.pid"), os.path.join(cfg.state, "ghostd.log")
    if not foreground:
        pid = daemonize(pidfile, logfile)
        if pid:
            print(f"ghostd daemon pid {pid} (log {logfile})")
            return 0
    lock = acquire_pidfile(pidfile)
    srv = Server(cfg)
    install_release_executor(srv)
    print(json.dumps({"boot": srv.boot()}, default=str), flush=True)
    try:
        srv.run_forever()
    finally:
        lock.close()
    return 0

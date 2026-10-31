"""P5 lab drain proof (acceptance 2, 4 shape) and restart survival (acceptance 1) + idle budget (acceptance 6 shape).

LAB, not field evidence: the "egress router" here is tests/lab.py's local proxy, killed and healed on purpose. The
real heal-window drain and the zane-box resource numbers are owed to Zane (see RECEIPT-GHOST-SERVER-P5).
"""
import glob
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tests"))
import lab  # noqa: E402
from ghost import codeact, envelope, legacy, signing  # noqa: E402
from ghost.registry import Registry  # noqa: E402
from ghost.server import Config, Server, install_release_executor  # noqa: E402

REPO = os.path.dirname(HERE)


class Clock:
    def __init__(self):
        self.t = time.time()

    def __call__(self):
        return self.t


def make_site(tmp, doors=None, only=None):
    """A throwaway copy of genesis-os: the real legacy queue (optionally only some job ids) + this ghost-server's
    mapping, isolated state."""
    root = os.path.join(tmp, "genesis-os")
    keep = None if only is None else (lambda d, names: [n for n in names if not any(n.startswith(j) for j in only)])
    shutil.copytree(os.path.join(REPO, "ghost", "queue"), os.path.join(root, "ghost", "queue"), ignore=keep)
    os.makedirs(os.path.join(root, "war-room"))
    gs = os.path.join(root, "ghost-server")
    os.makedirs(os.path.join(gs, "config"))
    os.makedirs(os.path.join(gs, "state", "keys"), mode=0o700)
    shutil.copy(os.path.join(HERE, "config", "legacy_requires.json"), os.path.join(gs, "config"))
    cfg = {"identity": {"name": "zane-box", "key_file": "state/keys/zane-box.key"}, "db": "state/ghost.db",
           "spool": "state/spool", "state_dir": "state", "doors": "config/doors.json",
           "trusted_keys": "config/trusted_keys.json", "receipts_root": "..", "tick_s": 0.2,
           "lanes": {"default_cap": 3, "global_cap": 3}, "reach": {}}
    json.dump(cfg, open(os.path.join(gs, "config", "ghost.json"), "w"))
    json.dump(doors or {"doors": []}, open(os.path.join(gs, "config", "doors.json"), "w"))
    for f in ("ghost.json", "doors.json", "legacy_requires.json"):  # explicit modes: never depend on the umask (D2)
        os.chmod(os.path.join(gs, "config", f), 0o644)
    return root, gs


HAVE_QUEUE = os.path.isdir(os.path.join(REPO, "ghost", "queue"))


@unittest.skipUnless(HAVE_QUEUE, "needs the sibling genesis-os/ghost/queue (designed layout; Zane review D2)")
@unittest.skipUnless(signing.HAVE_CRYPTO, "cryptography required for signed envelopes")
class DrainThroughHealWindow(unittest.TestCase):
    def test_migrated_legacy_job_drains_end_to_end_through_a_heal_window(self):
        tmp = tempfile.mkdtemp()
        up = lab.start_upstream()
        proxy_port = lab.free_port()
        root, gs = make_site(tmp, {"trio": lab.trio_for(up.server_port),
                                   "doors": [{"name": "egress", "kind": "http_proxy",
                                              "proxy_url": f"http://127.0.0.1:{proxy_port}"}]},
                             only=("GHOST-Q-002", "GHOST-Q-003", "GHOST-Q-004", "GHOST-Q-008"))
        server_pub = signing.keygen(os.path.join(gs, "state", "keys", "zane-box.key"))
        zane_key_path = os.path.join(tmp, "zane.key")
        zane_pub = signing.keygen(zane_key_path)
        json.dump({"peers": {"zane": zane_pub}}, open(os.path.join(gs, "config", "trusted_keys.json"), "w"))
        os.chmod(os.path.join(gs, "config", "trusted_keys.json"), 0o644)  # signing.py refuses group-writable keys
        clock = Clock()
        srv = Server(Config(os.path.join(gs, "config", "ghost.json")), clock=clock)
        install_release_executor(srv)
        srv.boot()
        legacy.migrate(srv.reg, os.path.join(root, "ghost", "queue"), os.path.join(gs, "config", "legacy_requires.json"),
                       actor="os:zane", repo_root=root)

        # 1. Network dead: the door is DARK. Door-dependent jobs burn no attempts and are not released.
        out = srv.tick()
        self.assertEqual(out["released"], {})
        self.assertEqual(srv.reg.door_states()["egress"]["verdict"], "DARK")
        self.assertEqual(srv.reg.get("GHOST-Q-002")["attempts"], 0)

        # 2. Heal: the router comes back. After the breaker cool-down the trio passes and the queue drains.
        px = lab._Proxy(("127.0.0.1", proxy_port), lab.ProxyHandler)
        px.behaviour, px.requests = "ok", []
        import threading
        threading.Thread(target=px.serve_forever, daemon=True).start()
        clock.t += 61
        out = srv.tick()
        self.assertEqual(srv.reg.door_states()["egress"]["verdict"], "HEALED")
        self.assertEqual(out["released"], {"GHOST-Q-002": "released", "GHOST-Q-003": "released"})
        self.assertEqual(srv.reg.get("GHOST-Q-002")["state"], "RUNNING")
        spooled = envelope.pending_out(os.path.join(gs, "state", "spool"), "zane")
        self.assertEqual(len(spooled), 2)

        # 3. Zane (the assignee) receives the task, verifies GHOST's signature, does the work, files the receipt,
        #    and returns a signed result envelope through the same store-and-forward spool.
        task = next(json.load(open(p)) for p in spooled if json.load(open(p))["job_id"] == "GHOST-Q-002")
        envelope.check(task, verifier=signing.Verifier({"peers": {"zane-box": server_pub}}), me="zane", now=clock.t)
        self.assertIn("fence_notes", task["payload"]["spec"])  # fences travel with the job
        receipt_rel = "war-room/RECEIPT-F6-AGENT-SHELF-STEP2-LAB.md"
        open(os.path.join(root, receipt_rel), "w").write("# GHOST-Q-002 lab receipt\nshelf reinstall evidence ...\n")
        res = envelope.make(kind="result", frm="zane", to="zane-box", job_id="GHOST-Q-002",
                            payload={"receipt_path": receipt_rel}, key=signing.load_private(zane_key_path), now=clock.t)
        inbox = os.path.join(gs, "state", "spool", "in", "zane")
        os.makedirs(inbox)
        json.dump(res, open(os.path.join(inbox, res["id"] + ".json"), "w"))
        # a receipt that never names its job does not count
        bad = envelope.make(kind="result", frm="zane", to="zane-box", job_id="GHOST-Q-003",
                            payload={"receipt_path": receipt_rel}, key=signing.load_private(zane_key_path), now=clock.t)
        json.dump(bad, open(os.path.join(inbox, bad["id"] + ".json"), "w"))
        out = srv.tick()
        outcomes = {r["id"]: r["outcome"] for r in out["inbox"]}
        self.assertTrue(outcomes[res["id"]].startswith("verified"))
        self.assertTrue(outcomes[bad["id"]].startswith("rejected"))
        self.assertEqual(srv.reg.get("GHOST-Q-002")["state"], "DONE-VERIFIED")
        self.assertEqual(srv.reg.get("GHOST-Q-003")["state"], "QUEUED")  # failed attempt -> bounded backoff

        # 4. Acceptance 4: one query returns the complete provenance of the migrated job.
        prov = srv.reg.provenance("GHOST-Q-002")
        self.assertEqual([l["transform"] for l in prov["lineage"]],
                         ["legacy_import", "attempt_start", "artifact", "verified"])
        self.assertIn("ghost/queue/GHOST-Q-002-", prov["lineage"][0]["source"])
        self.assertEqual({(e["direction"], e["kind"]) for e in prov["envelopes"]}, {("out", "task"), ("in", "result")})
        self.assertEqual(len(prov["artifacts"]), 1)
        kinds = [r["kind"] for r in srv.reg.db.execute("SELECT kind FROM ledger ORDER BY seq")]
        self.assertIn("door_state", kinds)
        self.assertIn("drain_released", kinds)
        self.assertTrue(srv.reg.verify_ledger()["ok"])
        # the redelivered result (mailbox duplicate) is acknowledged and not applied twice
        json.dump(res, open(os.path.join(inbox, "dup.json"), "w"))
        self.assertEqual(srv.tick()["inbox"][0]["outcome"], "duplicate-ignored")
        px.shutdown()
        up.shutdown()


@unittest.skipUnless(HAVE_QUEUE, "needs the sibling genesis-os/ghost/queue (designed layout; Zane review D2)")
@unittest.skipUnless(signing.HAVE_CRYPTO, "cryptography required for signed envelopes")
class WipCapOnTheRealQueue(unittest.TestCase):
    def test_full_real_queue_never_exceeds_the_global_cap_of_3(self):
        tmp = tempfile.mkdtemp()
        root, gs = make_site(tmp)
        signing.keygen(os.path.join(gs, "state", "keys", "zane-box.key"))
        srv = Server(Config(os.path.join(gs, "config", "ghost.json")), clock=Clock())
        install_release_executor(srv)
        srv.boot()
        legacy.migrate(srv.reg, os.path.join(root, "ghost", "queue"), os.path.join(gs, "config", "legacy_requires.json"),
                       actor="os:zane", repo_root=root)
        for _ in range(3):
            srv.tick()
            self.assertLessEqual(len(srv.reg.jobs("RUNNING")), 3)
        running = srv.reg.jobs("RUNNING")
        eligible = [j for j in srv.reg.jobs() if j["requires"] == [] and j["level"] != "C"]
        self.assertEqual(len(running), min(3, len([j for j in eligible if j["state"] == "RUNNING"])))
        self.assertTrue(running and all(j["requires"] == [] for j in running))  # no door exists: only transport-free
        self.assertEqual(srv.select(srv.clock()), [])


@unittest.skipUnless(HAVE_QUEUE, "needs the sibling genesis-os/ghost/queue (designed layout; Zane review D2)")
@unittest.skipUnless(codeact.netns_available(), "CodeAct needs unprivileged netns for this test")
class RestartSurvival(unittest.TestCase):
    def ghostd(self, gs, *args, **kw):
        return subprocess.run([sys.executable, "-B", os.path.join(HERE, "ghostd.py"), "--config",
                               os.path.join(gs, "config", "ghost.json"), *args], capture_output=True, text=True,
                              timeout=60, **kw)

    def pid(self, gs):
        return int(open(os.path.join(gs, "state", "ghostd.pid")).read().strip())

    def wait_for(self, cond, timeout=15):
        end = time.time() + timeout
        while time.time() < end:
            if cond():
                return True
            time.sleep(0.1)
        return False

    def test_kill_9_and_restart_loses_nothing_and_keeps_the_ledger_continuous(self):
        tmp = tempfile.mkdtemp()
        root, gs = make_site(tmp)
        self.ghostd(gs, "migrate")
        job = {"job_id": "GHOST-Q-900", "title": "lab long codeact", "lane": "probes", "executor": "codeact",
               "spec": {"script": "import time\ntime.sleep(60)\n"},
               "verifier": {"kind": "json_schema", "schema": {"type": "object"}}}
        jf = os.path.join(tmp, "job.json")
        json.dump(job, open(jf, "w"))
        self.assertEqual(json.loads(self.ghostd(gs, "add", jf).stdout)["state"], "QUEUED")
        db = os.path.join(gs, "state", "ghost.db")
        before = {j["job_id"]: j["state"] for j in Registry(db).jobs()}

        self.assertEqual(self.ghostd(gs, "start").returncode, 0)
        reg = Registry(db)
        self.assertTrue(self.wait_for(lambda: reg.get("GHOST-Q-900")["state"] == "RUNNING"))
        pid = self.pid(gs)
        second = self.ghostd(gs, "run")  # flock: a second instance must refuse
        self.assertIn("refusing to start a second instance", second.stderr + second.stdout)

        # idle budget sample (cloud container; zane-box numbers are owed)
        def stat():
            f = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()
            return (int(f[11]) + int(f[12])) / os.sysconf("SC_CLK_TCK")
        rss_kb = int(next(l.split()[1] for l in open(f"/proc/{pid}/status") if l.startswith("VmRSS:")))
        c0, t0 = stat(), time.time()
        time.sleep(5)
        cpu_pct = 100 * (stat() - c0) / (time.time() - t0)
        open(os.path.join(tmp, "budget.json"), "w").write(json.dumps({"rss_kb": rss_kb, "cpu_pct": cpu_pct}))
        print(f"\n[budget] daemon idle RSS {rss_kb} kB, CPU {cpu_pct:.2f}% over 5 s (cloud container, 1 CodeAct child)")
        self.assertLess(rss_kb, 40 * 1024)
        self.assertLess(cpu_pct, 5.0)

        os.kill(pid, signal.SIGKILL)  # crash, no clean shutdown
        self.assertTrue(self.wait_for(lambda: not os.path.exists(f"/proc/{pid}") or
                                      open(f"/proc/{pid}/stat").read().split()[2] == "Z"))
        orphans = lambda: subprocess.run(["pgrep", "-f", "-I -S -B script.py"], capture_output=True).stdout.split()  # noqa: E731
        self.assertTrue(self.wait_for(lambda: not orphans()), "CodeAct child must die with the server (PDEATHSIG)")
        self.assertEqual(self.ghostd(gs, "start").returncode, 0)
        reg2 = Registry(db)
        self.assertTrue(self.wait_for(lambda: reg2.get("GHOST-Q-900")["state"] == "QUEUED"))
        after = {j["job_id"]: j["state"] for j in reg2.jobs()}
        self.assertEqual(set(after), set(before))  # zero jobs lost
        self.assertEqual({k: v for k, v in after.items() if k != "GHOST-Q-900"},
                         {k: v for k, v in before.items() if k != "GHOST-Q-900"})  # states intact
        j = reg2.get("GHOST-Q-900")
        self.assertEqual((j["attempts"], j["state"]), (1, "QUEUED"))
        self.assertEqual(reg2.provenance("GHOST-Q-900")["attempts"][0]["outcome"], "interrupted")
        chain = reg2.verify_ledger()
        self.assertTrue(chain["ok"])
        boots = [r[0] for r in reg2.db.execute("SELECT seq FROM ledger WHERE kind='boot'")]
        self.assertEqual(len(boots), 2)  # one chain spanning the crash

        self.assertEqual(json.loads(self.ghostd(gs, "keepalive").stdout)["ok"], True)
        new_pid = self.pid(gs)
        os.kill(new_pid, signal.SIGTERM)
        self.assertTrue(self.wait_for(lambda: reg2.db.execute(
            "SELECT COUNT(*) FROM ledger WHERE kind='shutdown'").fetchone()[0] == 1))
        reg2.db.execute("UPDATE heartbeat SET at = at - 400")
        self.assertEqual(self.ghostd(gs, "keepalive").returncode, 1)  # stale heartbeat -> watchdog fires


if __name__ == "__main__":
    unittest.main()

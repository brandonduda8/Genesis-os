"""Emergency-stop battery + THE DRILL: stop a live minion mid-task, prove state before/after, restart clean."""
import json
import os
import sys
import tempfile
import threading
import time
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from genesis_fabric.crypto import FabricError, Keys  # noqa: E402
from genesis_fabric.identity import Registry, issue, new_doc  # noqa: E402
from genesis_fabric.phone import LocalTransport, Phone  # noqa: E402
from genesis_fabric.relay import Relay  # noqa: E402
from genesis_fabric import stop as S  # noqa: E402

NOW = 1_793_000_000.0


def world():
    founder = Keys.generate()
    keys = {n: Keys.generate() for n in ("zane", "astra", "drain", "scorekeeper")}
    klass = {"zane": "operator", "astra": "architect", "drain": "minion", "scorekeeper": "minion"}
    doc = new_doc(founder, *[issue(founder, name=n, klass=klass[n], keys=keys[n], charter_id=f"CH-{n}", now=NOW)
                             for n in keys])
    tmp = tempfile.mkdtemp()
    return founder, keys, doc, Registry(doc), tmp


def signed(founder, keys, kind, scope_type, target, *, op="zane", **kw):
    return S.sign(S.command(kind, scope_type=scope_type, target=target, reason=kw.pop("reason", "drill"), now=kw.pop("now", NOW),
                            **kw), founder=founder, operator_name=op, operator=keys[op])


class TwoKeys(unittest.TestCase):
    def test_both_keys_required_and_operator_must_be_an_operator(self):
        founder, keys, doc, reg, tmp = world()
        good = signed(founder, keys, "stop", "fleet", None)
        S.check(good, reg, NOW)
        no_founder = dict(good, founder_sig=keys["zane"].sign(b"x"))
        no_operator = dict(good, operator_sig="")
        wrong_role = signed(founder, keys, "stop", "fleet", None, op="astra")
        edited = json.loads(json.dumps(good))
        edited["cmd"]["scope"] = {"type": "identity", "target": "nobody"}
        for bad in (no_founder, no_operator, wrong_role, edited):
            with self.assertRaises(FabricError):
                S.check(bad, reg, NOW)

    def test_restart_ceremony_requires_an_inspection_statement(self):
        with self.assertRaises(FabricError):
            S.command("restart", scope_type="fleet", target=None, reason="r", now=NOW)

    def test_forged_file_in_the_stop_dir_neither_stops_nor_restarts(self):
        founder, keys, doc, reg, tmp = world()
        d = os.path.join(tmp, "estop")
        os.makedirs(d)
        forged = signed(Keys.generate(), keys, "stop", "fleet", None)  # wrong founder key
        with open(os.path.join(d, "000-forged.json"), "w") as f:
            json.dump(forged, f)
        g = S.Guard("drain", reg, d, lambda: NOW)
        self.assertEqual(g.state(), (False, None))
        self.assertEqual(len(g.rejected), 1)


class Scopes(unittest.TestCase):
    def setUp(self):
        self.founder, self.keys, self.doc, self.reg, tmp = world()
        self.dir = os.path.join(tmp, "estop")
        self.g = {n: S.Guard(n, self.reg, self.dir, lambda: NOW + 100) for n in ("drain", "scorekeeper", "zane")}

    def put(self, *a, **kw):
        S.write(signed(self.founder, self.keys, *a, **kw), self.dir)

    def halted(self):
        return {n: g.state()[0] for n, g in self.g.items()}

    def test_identity_class_fleet(self):
        self.put("stop", "identity", "drain", now=NOW)
        self.assertEqual(self.halted(), {"drain": True, "scorekeeper": False, "zane": False})
        self.put("stop", "class", "minion", now=NOW + 1)
        self.assertEqual(self.halted(), {"drain": True, "scorekeeper": True, "zane": False})
        self.put("stop", "fleet", None, now=NOW + 2)
        self.assertEqual(self.halted(), {"drain": True, "scorekeeper": True, "zane": True})

    def test_narrow_restart_cannot_lift_a_broad_stop(self):
        self.put("stop", "fleet", None, now=NOW)
        self.put("restart", "identity", "drain", now=NOW + 1, inspected="queue intact")
        self.assertTrue(self.halted()["drain"])

    def test_restart_order_releases_only_the_named_agents(self):
        self.put("stop", "fleet", None, now=NOW)
        self.put("restart", "fleet", None, now=NOW + 1, inspected="ledger verified; queue intact",
                 order=["scorekeeper"])
        self.assertEqual(self.halted(), {"drain": True, "scorekeeper": False, "zane": True})
        self.put("restart", "fleet", None, now=NOW + 2, inspected="scorekeeper green", order=["scorekeeper", "drain",
                                                                                               "zane"])
        self.assertEqual(self.halted(), {"drain": False, "scorekeeper": False, "zane": False})

    def test_a_stop_after_a_restart_wins(self):
        self.put("restart", "fleet", None, now=NOW, inspected="x")
        self.put("stop", "identity", "drain", now=NOW + 1)
        self.assertTrue(self.halted()["drain"])


def minion(guard, items, ckpt, log, delay=0.05):
    """A chartered minion's loop: check the stop BEFORE every action, checkpoint AFTER every action."""
    done = json.load(open(ckpt)) if os.path.exists(ckpt) else []
    if done:
        log.append({"event": "resumed", "from": done[-1], "done": len(done)})
    for it in items:
        if it in done:
            continue
        try:
            guard.check()
        except S.Halted as h:
            log.append({"event": "halted", "stopped_before": it, "done": list(done), "by": h.cmd["nonce"]})
            return "HALTED"
        time.sleep(delay)  # the work
        done.append(it)
        with open(ckpt + ".tmp", "w") as f:
            json.dump(done, f)
        os.replace(ckpt + ".tmp", ckpt)
    log.append({"event": "complete", "done": len(done)})
    return "COMPLETE"


class Drill(unittest.TestCase):
    def test_stop_live_minion_mid_task_via_fabric_then_restart_clean(self):
        founder, keys, doc, reg, tmp = world()
        relay = Relay(os.path.join(tmp, "relay.db"), reg)
        zane = Phone("zane", keys["zane"], reg, [LocalTransport(relay)])
        drain_phone = Phone("drain", keys["drain"], reg, [LocalTransport(relay)])
        guard = S.Guard("drain", reg, os.path.join(tmp, "drain-estop"))
        drain_phone.attach_guard(guard)
        items, ckpt, log = [f"Q-{i:03d}" for i in range(1, 21)], os.path.join(tmp, "drain.ckpt"), []
        result = {}

        def run():
            # the minion polls its phone between items, as every chartered runtime does
            orig = guard.check

            def check_with_poll():
                drain_phone.poll()
                orig()
            guard.check = check_with_poll
            result["r"] = minion(guard, items, ckpt, log)
        t = threading.Thread(target=run)
        t.start()
        time.sleep(0.32)  # mid-task
        before = len(json.load(open(ckpt)))
        stop_doc = signed(founder, keys, "stop", "identity", "drain", reason="DRILL: halt drain mid-task",
                          now=time.time())
        self.assertEqual(S.broadcast(zane, stop_doc, ["drain"])["sent"], ["drain"])
        t.join(5)
        self.assertEqual(result["r"], "HALTED")
        halted = log[-1]
        after = json.load(open(ckpt))
        self.assertTrue(0 < before <= len(after) < len(items), (before, len(after)))
        self.assertEqual(halted["done"], after)  # the receipt names exactly where it stopped
        self.assertEqual(halted["stopped_before"], items[len(after)])
        time.sleep(0.2)
        self.assertEqual(json.load(open(ckpt)), after)  # state frozen: nothing moved after the halt
        # restart ceremony: both keys, inspection statement, order
        restart = signed(founder, keys, "restart", "identity", "drain", reason="DRILL complete",
                         inspected=f"checkpoint {len(after)}/20 verified; no partial item", order=["drain"],
                         now=time.time() + 1)
        S.broadcast(zane, restart, ["drain"])
        guard.check = S.Guard.check.__get__(guard)  # fresh loop
        drain_phone.poll()
        self.assertEqual(minion(guard, items, ckpt, log, delay=0), "COMPLETE")
        final = json.load(open(ckpt))
        self.assertEqual(final, items)  # every item exactly once: no repeat, no skip
        self.assertEqual([e["event"] for e in log], ["halted", "resumed", "complete"])

    def test_path_two_stops_the_minion_while_the_fabric_is_dark(self):
        founder, keys, doc, reg, tmp = world()
        d = os.path.join(tmp, "estop")
        g = S.Guard("drain", reg, d)
        log = []
        S.write(signed(founder, keys, "stop", "class", "minion", reason="fabric dark; ghostd path", now=time.time()), d)
        self.assertEqual(minion(g, ["a", "b"], os.path.join(tmp, "c"), log), "HALTED")


class GhostdPath(unittest.TestCase):
    def test_ghostd_holds_every_release_under_a_stop_and_fails_closed_when_unverifiable(self):
        gs_src = os.path.join(os.path.dirname(HERE), "ghost-server")
        if not os.path.isdir(gs_src):
            self.skipTest("ghost-server not on this checkout")
        sys.path.insert(0, gs_src)
        from ghost.server import Config, Server
        founder, keys, doc, reg, tmp = world()
        gs = os.path.join(tmp, "gs")
        os.makedirs(os.path.join(gs, "config"))
        with open(os.path.join(gs, "registry.json"), "w") as f:
            json.dump(doc, f)
        cfg = {"identity": {"name": "zane-box"}, "db": "state/ghost.db", "spool": "state/spool", "state_dir": "state",
               "estop": {"dir": "state/estop", "registry": "registry.json", "identity": "drain",
                         "fabric_path": HERE}}
        path = os.path.join(gs, "config", "ghost.json")
        with open(path, "w") as f:
            json.dump(cfg, f)
        srv = Server(Config(path))
        released = []
        srv.select = lambda now: ["J-1"]
        srv.release = lambda jid, now: released.append(jid) or "released"
        srv.tick()
        self.assertEqual(released, ["J-1"])  # no stop: work flows
        S.write(signed(founder, keys, "stop", "fleet", None, reason="ghostd path drill", now=time.time()),
                os.path.join(gs, "state", "estop"))
        out = srv.tick()
        self.assertIn("HALTED", out["estop"])
        self.assertEqual(released, ["J-1"])  # nothing released under the stop
        S.write(signed(founder, keys, "restart", "fleet", None, reason="r", inspected="ledger ok", now=time.time() + 1),
                os.path.join(gs, "state", "estop"))
        srv.tick()
        self.assertEqual(released, ["J-1", "J-1"])
        events = [r[0] for r in srv.reg.db.execute("SELECT kind FROM ledger WHERE kind LIKE 'estop%' ORDER BY seq")]
        self.assertEqual(events, ["estop_hold", "estop_release"])
        cfg["estop"]["registry"] = "missing.json"  # misconfigured: cannot verify stops
        with open(path, "w") as f:
            json.dump(cfg, f)
        srv2 = Server(Config(path))
        srv2.select = lambda now: ["J-2"]
        srv2.release = lambda jid, now: released.append(jid)
        self.assertIn("failing closed", srv2.tick()["estop"])
        self.assertNotIn("J-2", released)


if __name__ == "__main__":
    unittest.main()

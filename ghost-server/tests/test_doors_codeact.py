"""Module 3 (doors, trio, fast-fail, breakers) and module 7 (CodeAct sandbox + deterministic verifiers)."""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lab  # noqa: E402
from ghost import codeact  # noqa: E402
from ghost.doors import CLOSED, HALF_OPEN, OPEN, Door, DoorError, http_request  # noqa: E402


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Doors(unittest.TestCase):
    def setUp(self):
        self.up = lab.start_upstream()
        self.trio = lab.trio_for(self.up.server_port)

    def tearDown(self):
        self.up.shutdown()

    def door(self, proxy_port, **kw):
        return Door("egress", "http_proxy", f"http://127.0.0.1:{proxy_port}", trio=self.trio, **kw)

    def test_healed_only_when_all_three_legs_pass_through_the_door(self):
        px = lab.start_proxy()
        t = self.door(px.server_address[1]).probe_trio()
        self.assertEqual((t["verdict"], t["healed"]), ("HEALED", True))
        self.assertEqual(len(px.requests), 3)  # all three really went through the proxy
        self.assertTrue(any(r.startswith("POST ") for r in px.requests))  # the NIM completion leg
        px.shutdown()

    def test_partial_is_never_healed(self):
        px = lab.start_proxy()
        trio = dict(self.trio, pip={"url": f"http://127.0.0.1:{lab.free_port()}/dead"})
        t = Door("egress", "http_proxy", f"http://127.0.0.1:{px.server_address[1]}", trio=trio).probe_trio()
        self.assertEqual((t["verdict"], t["healed"]), ("PARTIAL", False))
        px.shutdown()

    def test_dead_door_is_dark_and_breaker_opens_after_three_failures(self):
        clock = Clock()
        d = self.door(lab.free_port(), clock=clock)
        t = d.probe_trio()
        self.assertEqual(t["verdict"], "DARK")
        self.assertEqual(t["legs"]["github"]["error_class"], "refused")
        self.assertEqual(d.breaker, OPEN)
        with self.assertRaises(DoorError) as cm:
            d.request(self.trio["github"]["url"])
        self.assertEqual(cm.exception.error_class, "breaker_open")
        clock.t += 61
        self.assertTrue(d.allow())
        self.assertEqual(d.breaker, HALF_OPEN)

    def test_stall_fails_inside_the_5s_bar(self):
        """A connection that accepts and never answers once hung 15 s; the door must fail in <= 5 s."""
        px = lab.start_proxy("hang")
        t0 = time.monotonic()
        with self.assertRaises(DoorError) as cm:
            http_request(self.trio["github"]["url"], proxy=f"http://127.0.0.1:{px.server_address[1]}", deadline_s=5.0)
        elapsed = time.monotonic() - t0
        self.assertEqual(cm.exception.error_class, "timeout")
        self.assertLess(elapsed, 5.5)
        self.assertGreater(elapsed, 4.5)
        px.shutdown()

    def test_429_is_a_hard_stop(self):
        px = lab.start_proxy("429")
        clock = Clock()
        d = self.door(px.server_address[1], clock=clock)
        t = d.probe_trio()
        self.assertEqual(t["legs"]["github"]["error_class"], "rate_limited")
        self.assertEqual(list(t["legs"]), ["github"])  # no further legs pushed into the 429
        self.assertEqual(len(px.requests), 1)
        self.assertEqual(d.breaker, OPEN)
        self.assertGreaterEqual(d.open_until - clock.t, 900)
        px.shutdown()

    def test_stats_record_latency_and_error_classes(self):
        px = lab.start_proxy()
        d = self.door(px.server_address[1])
        d.probe_trio()
        s = d.snapshot()
        self.assertEqual((s["samples"], s["ok"], s["breaker"]), (3, 3, CLOSED))
        self.assertIsNotNone(s["p95_ms"])
        px.shutdown()


@unittest.skipUnless(codeact.netns_available(), "unprivileged netns unavailable: CodeAct fails closed (BLOCKED)")
class CodeAct(unittest.TestCase):
    SCHEMA = {"kind": "json_schema", "schema": {"type": "object", "required": ["sum"],
                                                "properties": {"sum": {"type": "integer", "const": 5}}}}

    def run_script(self, src, **kw):
        return codeact.run_blocking(src, {"a": 2, "b": 3}, **kw)

    def test_multi_step_script_result_counts_only_via_verifier(self):
        r = self.run_script("import json\nd=json.load(open('input.json'))\ns=d['a']+d['b']\n"
                            "json.dump({'sum':s,'steps':['read','add','write']},open('out/result.json','w'))\n")
        self.assertEqual(r["rc"], 0)
        self.assertEqual(codeact.verify(self.SCHEMA, job_id="J", workdir=r["workdir"]), (True, "schema ok"))

    def test_self_certification_is_ignored(self):
        r = self.run_script("import json\njson.dump({'ok':True,'verified':True,'sum':4},open('out/result.json','w'))\n"
                            "print('ALL TESTS PASSED, I certify this is correct')\n")
        ok, detail = codeact.verify(self.SCHEMA, job_id="J", workdir=r["workdir"])
        self.assertFalse(ok)
        self.assertIn("const", detail)

    def test_no_network_inside_the_sandbox(self):
        r = self.run_script("import socket,json\ntry:\n socket.create_connection(('1.1.1.1',443),timeout=2);n='YES'\n"
                            "except OSError: n='NO'\njson.dump({'net':n},open('out/result.json','w'))\n")
        self.assertTrue(r["isolated"])
        self.assertIn('"NO"', open(os.path.join(r["workdir"], "out", "result.json")).read())

    def test_scrubbed_env_and_resource_limits(self):
        os.environ["GHOST_CANARY_SECRET"] = "s3cret"
        try:
            r = self.run_script("import os,json\njson.dump(dict(os.environ),open('out/result.json','w'))\n")
            self.assertNotIn("s3cret", open(os.path.join(r["workdir"], "out", "result.json")).read())
        finally:
            del os.environ["GHOST_CANARY_SECRET"]
        r = self.run_script("x = bytearray(1024*1024*1024)\n")  # 1 GB > 512 MB address-space cap
        self.assertNotEqual(r["rc"], 0)

    def test_wall_clock_kill(self):
        old = codeact.WALL_S
        codeact.WALL_S = 1
        try:
            t0 = time.monotonic()
            r = self.run_script("import time\ntime.sleep(30)\n")
            self.assertTrue(r["timed_out"])
            self.assertLess(time.monotonic() - t0, 3)
        finally:
            codeact.WALL_S = old

    def test_argv_verifier_is_a_separate_sandbox(self):
        r = self.run_script("import json\njson.dump({'sum':5},open('out/result.json','w'))\n")
        v = {"kind": "argv", "script": "import json,sys\nd=json.load(open('input.json'))\n"
                                       "sys.exit(0 if json.loads(d['outputs']['result.json'])['sum']==5 else 1)\n"}
        self.assertTrue(codeact.verify(v, job_id="J", workdir=r["workdir"])[0])
        self.assertFalse(codeact.verify({"kind": "peer_debate"}, job_id="J")[0])  # unknown kinds fail


if __name__ == "__main__":
    unittest.main()

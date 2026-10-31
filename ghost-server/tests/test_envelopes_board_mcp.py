"""Module 8 (A2A envelopes, store-and-forward, idempotent redelivery), modules 5-6 (WIP + Little's Law board), MCP."""
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ghost import envelope, mcp, metrics, signing  # noqa: E402
from ghost.registry import Registry  # noqa: E402


@unittest.skipUnless(signing.HAVE_CRYPTO, "cryptography not installed: envelopes fail closed")
class Envelopes(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.reg = Registry(os.path.join(self.d, "g.db"))
        self.spool = os.path.join(self.d, "spool")
        self.zkey_path = os.path.join(self.d, "zane.key")
        self.zpub = signing.keygen(self.zkey_path)
        self.zkey = signing.load_private(self.zkey_path)
        self.ver = signing.Verifier({"peers": {"zane": self.zpub}})
        self.applied = []

    def deliver(self, env, name=None):
        d = os.path.join(self.spool, "in", env["from"])
        os.makedirs(d, exist_ok=True)
        json.dump(env, open(os.path.join(d, name or f"{env['id']}.json"), "w"))

    def drain(self, now=None):
        return envelope.drain_inbox(self.reg, self.spool, verifier=self.ver, me="zane-box", now=now or time.time(),
                                    apply=lambda e: self.applied.append(e["id"]) or "applied")

    def env(self, **kw):
        return envelope.make(kind="result", frm="zane", to="zane-box", job_id="GHOST-Q-002",
                             payload={"receipt_path": "war-room/R.md"}, key=self.zkey, now=time.time(), **kw)

    def test_signed_envelope_applies_once_even_when_redelivered(self):
        e = self.env()
        self.deliver(e)
        self.assertEqual(self.drain()[0]["outcome"], "applied")
        self.deliver(e, name="redelivered-copy.json")  # the mailbox delivered it again after a reboot
        self.assertEqual(self.drain()[0]["outcome"], "duplicate-ignored")
        self.assertEqual(self.applied, [e["id"]])

    def test_tampered_forged_misaddressed_or_expired_are_quarantined_never_applied(self):
        e = self.env()
        bad = [dict(e, payload={"receipt_path": "war-room/EVIL.md"}),             # payload changed
               dict(e, payload_sha256="0" * 64),                                  # hash changed
               dict(e, to="someone-else"),                                        # misaddressed
               dict(e, sig=self.env()["sig"])]                                    # signature from another envelope
        for i, b in enumerate(bad):
            self.deliver(b, name=f"bad{i}.json")
        late = self.env(ttl_s=60)
        self.deliver(late, name="late.json")
        out = self.drain(now=time.time() + 120)
        self.assertEqual(sorted(o["outcome"] for o in out), ["quarantined"] * 5)
        self.assertEqual(self.applied, [])

    def test_unknown_peer_is_rejected(self):
        other = os.path.join(self.d, "mallory.key")
        signing.keygen(other)
        e = envelope.make(kind="result", frm="mallory", to="zane-box", job_id="GHOST-Q-002", payload={},
                          key=signing.load_private(other), now=time.time())
        self.deliver(e)
        self.assertEqual(self.drain()[0]["outcome"], "quarantined")

    def test_spool_survives_a_dead_network_and_reboot(self):
        e = self.env()
        path = envelope.spool_write(self.spool, "out", "cody", e)
        self.assertEqual(oct(os.stat(path).st_mode & 0o777), "0o600")
        self.reg.close()
        reg2 = Registry(os.path.join(self.d, "g.db"))  # "reboot"
        self.assertEqual(envelope.pending_out(self.spool, "cody"), [path])
        self.assertEqual(json.load(open(path))["id"], e["id"])
        reg2.close()


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


class FlowAndBoard(unittest.TestCase):
    def test_littles_law_is_computed_from_real_attempt_history(self):
        d = tempfile.mkdtemp()
        clock = Clock(1_000_000.0)
        reg = Registry(os.path.join(d, "g.db"), clock=clock)
        # 4 jobs each RUNNING for exactly 2 h, completed within a 24 h window -> L = 8/24, λ = 4/24 per h, W = 2 h
        for n in range(1, 5):
            reg.add_job({"job_id": f"GHOST-Q-{n:03d}", "title": "t", "lane": "ops", "executor": "manual", "level": "A"},
                        actor="t", source="t")
            reg.start_attempt(f"GHOST-Q-{n:03d}", actor="t", lease_s=99999)
            clock.t += 7200
            reg.finish_attempt(f"GHOST-Q-{n:03d}", actor="t", verified=True, outcome="verified")
        f = metrics.flow(reg, now=clock.t, window_s=86400)
        self.assertEqual(f["completions"], 4)
        self.assertAlmostEqual(f["mean_wip"], 8 / 24, places=3)
        self.assertAlmostEqual(f["throughput_per_h"], 4 / 24, places=3)
        self.assertAlmostEqual(f["littles_cycle_h"], 2.0, places=2)
        self.assertAlmostEqual(f["measured_cycle_h"], 2.0, places=2)

    def test_board_renders_live_numbers_and_never_asserts_done(self):
        d = tempfile.mkdtemp()
        reg = Registry(os.path.join(d, "g.db"))
        reg.add_job({"job_id": "GHOST-Q-001", "title": "t", "lane": "ops", "executor": "manual", "level": "A"},
                    actor="t", source="t")
        reg.start_attempt("GHOST-Q-001", actor="t", lease_s=60)
        reg.finish_attempt("GHOST-Q-001", actor="t", verified=True, outcome="verified")
        okrs = {"2026-Q4": [{"objective": "o", "key_results": [{"kr": "k", "metric": "completions", "target": 3},
                                                               {"kr": "u", "metric": "nps", "target": 50}]}]}
        sc = metrics.scorecard(reg, okrs=okrs, econ={})
        text = metrics.render_text(sc)
        self.assertIsNone(re.search(r"\bDONE\b(?!-)", text.replace("DONE-VERIFIED", "")))
        self.assertIn("VERIFIED — awaiting Brandon", text)
        self.assertIn("W = L/λ", text)
        self.assertIn("k: 1 / 3", text)          # live value
        self.assertIn("u: UNMEASURED / 50", text)  # honest, not a placeholder number
        self.assertIn("NOT COMPUTED", text)
        self.assertIn("PARKED", text)
        self.assertGreater(sc["power"]["server"].get("vmrss_kb", 0), 0)
        html_doc = metrics.render_html(sc)
        self.assertTrue(html_doc.startswith("<!doctype html>"))


class MCP(unittest.TestCase):
    def test_read_only_tools_and_no_mutation_path(self):
        d = tempfile.mkdtemp()
        reg = Registry(os.path.join(d, "g.db"))
        reg.add_job({"job_id": "GHOST-Q-001", "title": "t", "lane": "ops", "executor": "manual", "level": "A"},
                    actor="t", source="t")
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "ghost_provenance", "arguments": {"job_id": "GHOST-Q-001"}}},
                {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "ghost_cancel", "arguments": {}}}]
        out = io.StringIO()
        before = reg.db.total_changes
        mcp.serve(reg, io.StringIO("\n".join(json.dumps(m) for m in msgs)), out)
        resp = [json.loads(l) for l in out.getvalue().splitlines()]
        self.assertEqual([r["id"] for r in resp], [1, 2, 3, 4])
        tools = resp[1]["result"]["tools"]
        self.assertTrue(all(t["annotations"]["readOnlyHint"] for t in tools))
        self.assertIn("lineage", resp[2]["result"]["content"][0]["text"])
        self.assertTrue(resp[3]["result"]["isError"])
        self.assertEqual(reg.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()

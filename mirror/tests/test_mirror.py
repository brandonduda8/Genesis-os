"""Mirror laws as tests: debts need sources, routing reads probes, minions obey minion law, the Brief knows staleness."""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import brief  # noqa: E402
import mirror as mx  # noqa: E402

NOW = dt.datetime(2026, 11, 1, 1, 0, tzinfo=dt.timezone.utc)


def copy_data():
    d = os.path.join(tempfile.mkdtemp(), "data")
    shutil.copytree(mx.DATA, d)
    return d


def write(root, name, obj):
    os.makedirs(os.path.dirname(os.path.join(root, name)), exist_ok=True)
    with open(os.path.join(root, name), "w") as f:
        json.dump(obj, f)


def probe(v, at, **legs):
    return {"vantage": v, "at": at, "legs": {k: {"ok": ok} for k, ok in legs.items()}}


class CommittedData(unittest.TestCase):
    def test_committed_mirror_data_is_valid(self):
        self.assertEqual(mx.validate(), [])

    def test_register_matches_ghost_on_this_checkout(self):
        gates = os.path.join(os.path.dirname(HERE), "ghost-server", "ghost", "gates.py")
        if not os.path.exists(gates):
            self.skipTest("ghost-server not on this checkout")
        src = open(gates).read()
        for c in mx.REGISTER_CLASSES:
            self.assertIn(f'"{c}"', src)


class Debts(unittest.TestCase):
    def base(self, **kw):
        d = {"id": "X-1", "debtor": "zane", "creditor": "claude", "what": "w", "since": "2026-10-31",
             "source": "https://github.com/x", "status": "open"}
        d.update(kw)
        return {"debts": [d]}

    def test_good_debt_passes(self):
        self.assertEqual(mx.check_debts(self.base()), [])

    def test_no_source_no_debt_and_other_laws(self):
        for kw, frag in ((dict(source="trust me"), "https source"), (dict(debtor="bob"), "debtor"),
                         (dict(creditor="zane"), "oneself"), (dict(status="done"), "without evidence"),
                         (dict(debtor="brandon", creditor="zane"), "Brandon's list")):
            self.assertTrue(any(frag in b for b in mx.check_debts(self.base(**kw))), kw)


class Roster(unittest.TestCase):
    def m(self, **kw):
        x = {"id": "drain", "policy_class": "ghost_operations", "actions": ["ghost_requeue"], "verifier": "zane",
             "max_instances": 1, "credentials": [], "resume": "job state"}
        x.update(kw)
        return {"minions": [x]}

    def test_minion_law(self):
        self.assertEqual(mx.check_roster(self.m()), [])
        cases = ((dict(actions=["publish_listing"]), "Level C"), (dict(verifier="drain"), "separate seat"),
                 (dict(max_instances=3), "max_instances"), (dict(policy_class="crypto"), "not in the register"),
                 (dict(credentials=["a", "b"]), "credential"), (dict(resume=""), "resumes"))
        for kw, frag in cases:
            self.assertTrue(any(frag in b for b in mx.check_roster(self.m(**kw))), kw)
        two = self.m()
        two["minions"].append(dict(two["minions"][0], id="scorekeeper", verifier="drain"))
        self.assertTrue(any("not another minion" in b for b in mx.check_roster(two)))

    def test_charterable_only_within_a_ghost_ceiling(self):
        self.assertEqual(mx.executable({"policy_class": "ghost_operations", "actions": ["ghost_requeue"]}), "CHARTERABLE")
        self.assertTrue(mx.executable({"policy_class": "training", "actions": ["launch"]}).startswith("STAGED"))
        self.assertIn("outside the ceiling", mx.executable({"policy_class": "ghost_operations", "actions": ["rm"]}))


class Routing(unittest.TestCase):
    def setUp(self):
        self.root = copy_data()
        shutil.rmtree(os.path.join(self.root, "probes"), ignore_errors=True)

    def test_routes_to_first_fresh_capable_vantage(self):
        write(self.root, "probes/claude-cloud.json", probe("claude-cloud", "2026-11-01T00:30:00Z", github=True))
        r = mx.route("repo_work", now=NOW, root=self.root)
        self.assertEqual((r["decision"], r["to"]), ("ROUTE", "claude-cloud"))

    def test_reroutes_around_dark_stale_and_unprobed_with_receipted_substitutions(self):
        write(self.root, "probes/claude-cloud.json", probe("claude-cloud", "2026-10-31T12:00:00Z", github=True))
        write(self.root, "probes/s1.json", probe("s1", "2026-11-01T00:50:00Z", github=False))
        write(self.root, "probes/zane-box.json", probe("zane-box", "2026-11-01T00:55:00Z", github=True))
        r = mx.route("repo_work", now=NOW, root=self.root)
        self.assertEqual(r["to"], "zane-box")
        reasons = " ".join(s["skipped"] for s in r["substitutions"])
        self.assertIn("stale", reasons)
        self.assertIn("legs not proven up", reasons)

    def test_all_dark_holds_safely(self):
        r = mx.route("container_work", now=NOW, root=self.root)
        self.assertEqual(r["decision"], "HOLD")
        self.assertEqual(len(r["substitutions"]), 2)

    def test_builder_excluded_from_verification(self):
        write(self.root, "probes/zane-box.json", probe("zane-box", "2026-11-01T00:55:00Z"))
        write(self.root, "probes/claude-cloud.json", probe("claude-cloud", "2026-11-01T00:55:00Z"))
        r = mx.route("verification", now=NOW, root=self.root, exclude=("zane-box",))
        self.assertEqual(r["to"], "claude-cloud")

    def test_level_c_is_a_packet_and_novel_class_is_a_policy_question(self):
        self.assertEqual(mx.route("level_c", root=self.root)["decision"], "PACKET")
        self.assertEqual(mx.route("crypto_arbitrage", root=self.root)["decision"], "POLICY_QUESTION")

    def test_brandon_cannot_be_a_work_queue(self):
        r = mx.load("routing.json", self.root)
        r["classes"]["repo_work"]["order"].append("brandon")
        write(self.root, "routing.json", r)
        self.assertTrue(any("Level C destination only" in b for b in mx.validate(self.root)))


class ManifestReconcile(unittest.TestCase):
    def test_reconcile_by_hash(self):
        a, b = copy_data(), copy_data()
        self.assertTrue(mx.reconcile(a, b)["clean"])
        m = mx.write_manifest(a, now="2026-11-01T00:00:00Z")
        self.assertEqual(m["digest"], mx.digest(mx.data_files(b)))  # MANIFEST itself is excluded
        d = mx.load("debts.json", b)
        d["debts"][0]["status"] = "done"
        write(b, "debts.json", d)
        write(a, "probes/s1.json", probe("s1", "2026-11-01T00:00:00Z"))
        r = mx.reconcile(a, b)
        self.assertEqual((r["conflict"], r["only_a"], r["clean"]), (["debts.json"], ["probes/s1.json"], False))


class Brief(unittest.TestCase):
    def test_brief_is_versioned_and_detects_staleness(self):
        root = copy_data()
        md = brief.render(root, now=NOW)
        p = os.path.join(tempfile.mkdtemp(), "B.md")
        open(p, "w").write(md)
        self.assertEqual(brief.check(p, root), "FRESH")
        d = mx.load("debts.json", root)
        d["debts"].pop()
        write(root, "debts.json", d)
        self.assertTrue(brief.check(p, root).startswith("STALE"))

    def test_brief_sections_and_honesty(self):
        md = brief.render(copy_data(), now=NOW)
        for s in ("Open debts", "Expiring power", "Conflicts", "Vantage mesh", "Minion roster", "Mirror coverage",
                  "Working agreements", "NOT READ: built offline", "NOT MIRRORED"):
            self.assertIn(s, md)
        self.assertIn("**2026-11-07** ⏳", md)  # the training quota deadline is flagged within 7 days
        self.assertNotIn("MIRROR DATA INVALID", md)

    def test_invalid_data_is_shouted(self):
        root = copy_data()
        d = mx.load("debts.json", root)
        d["debts"][0]["source"] = ""
        write(root, "debts.json", d)
        self.assertIn("MIRROR DATA INVALID", brief.render(root, now=NOW))


class Probe(unittest.TestCase):
    def test_probe_classifies_answers_and_refusals(self):
        import probe as pr
        self.assertFalse(pr.reach("https://127.0.0.1:9/", timeout=1)["ok"])


if __name__ == "__main__":
    unittest.main()

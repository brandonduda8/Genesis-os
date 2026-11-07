"""Tests for the executive baseline and board: no fabricated values, missing sources say NOT TESTED."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import baseline as bl  # noqa: E402
import board as bd  # noqa: E402


class Baseline(unittest.TestCase):
    def test_parses_unittest_and_pytest_summaries(self):
        self.assertEqual(bl.parse_summary("....\nRan 53 tests in 20.1s\n\nOK\n"), {"ran": 53, "ok": 1})
        self.assertEqual(bl.parse_summary("Ran 11 tests in 0.2s\n\nOK (skipped=2)\n"), {"ran": 11, "skipped": 2, "ok": 1})
        self.assertEqual(bl.parse_summary("x\n2 failed, 360 passed, 2 skipped, 56 warnings in 139.4s\n"),
                         {"failed": 2, "passed": 360, "skipped": 2})

    def test_pytest_summary_found_even_when_warnings_follow_it(self):
        log = ("....F\n=== short test summary info ===\nFAILED tests/a.py::t\n"
               "2 failed, 360 passed, 2 skipped, 56 warnings, 5 subtests passed in 139.40s (0:02:19)\n"
               "/venv/pytest_asyncio/plugin.py:217: PytestDeprecationWarning: The configuration option ...\n"
               "  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))\n")
        self.assertEqual(bl.parse_summary(log), {"failed": 2, "passed": 360, "skipped": 2})  # subtests are not extra tests

    def test_suite_whose_tests_are_not_on_this_branch_is_not_tested_not_failed(self):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "repo"))
        r = bl.run_suite({"name": "k", "cwd": "repo", "requires": ["training/kernels/tests"],
                          "argv": ["python3", "-m", "unittest", "discover", "-s", "training/kernels/tests"]}, root)
        self.assertEqual(r["grade"], "NOT TESTED")
        self.assertIn("not on the checked-out branch", r["reason"])

    def test_grades_come_only_from_evidence(self):
        env = ["tests/a.py::test_env1", "tests/b.py::test_env2"]
        self.assertEqual(bl.grade(0, {"ran": 5, "ok": 1}), "PASS")
        self.assertEqual(bl.grade(1, {"failed": 2, "passed": 360}, env, env), "PARTIAL")
        self.assertEqual(bl.grade(None, {}), "NOT TESTED")

    def test_audit_1_a_crash_is_never_partial(self):
        env = ["tests/a.py::test_env1", "tests/b.py::test_env2"]
        # pytest collection abort: rc=2, "1 error", nothing ran
        self.assertEqual(bl.grade(2, {"errors": 1}, env, ["tests/a.py::test_env1"]), "FAIL")
        self.assertEqual(bl.grade(1, {"failed": 1, "errors": 1, "passed": 9}, env, ["tests/a.py::test_env1"]), "FAIL")

    def test_audit_2_env_failures_match_by_name_not_count(self):
        env = ["tests/a.py::test_env1", "tests/b.py::test_env2"]
        real = ["tests/c.py::test_regression", "tests/d.py::test_regression"]
        self.assertEqual(bl.grade(1, {"failed": 2, "passed": 360}, env, real), "FAIL")
        self.assertEqual(bl.grade(1, {"failed": 2, "passed": 360}, env, [env[0], real[0]]), "FAIL")
        self.assertEqual(bl.grade(1, {"failed": 2, "passed": 360}, [], env), "FAIL")
        log = "FAILED tests/a.py::test_env1 - OSError\nFAILED tests/b.py::test_env2\n2 failed, 3 passed in 1.0s\n"
        self.assertEqual(bl.failed_ids(log), env)

    def test_audit_3_zero_tests_or_no_evidence_is_not_a_pass(self):
        self.assertEqual(bl.grade(0, {"ran": 0, "ok": 1}), "FAIL")
        self.assertEqual(bl.grade(0, {}), "FAIL")  # e.g. a node script that exited 0 without its marker
        self.assertEqual(bl.grade(0, {}, pass_evidence=True), "PASS")

    def test_audit_4_dirty_tree_is_recorded(self):
        root = tempfile.mkdtemp()
        subprocess.run(["git", "init", "-q", root], check=True)
        subprocess.run(["git", "-C", root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                        "--allow-empty", "-m", "x"], check=True)
        self.assertFalse(bl.git_head(root).endswith("+dirty"))
        open(os.path.join(root, "new.py"), "w").write("x = 1\n")
        self.assertTrue(bl.git_head(root).endswith("+dirty"))

    def test_missing_repo_is_not_tested_and_real_runs_are_recorded(self):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "r"))
        cfg = {"suites": [{"name": "absent", "cwd": "nope", "argv": ["python3", "-c", "pass"]},
                          {"name": "ok", "cwd": "r", "argv": ["{py}", "-c", "print('Ran 1 test in 0.0s\\n\\nOK')"]},
                          {"name": "bad", "cwd": "r", "argv": ["{py}", "-c", "import sys; sys.exit(3)"]}]}
        rep = bl.run_all(cfg, root)
        g = {s["name"]: s["grade"] for s in rep["suites"]}
        self.assertEqual(g, {"absent": "NOT TESTED", "ok": "PASS", "bad": "FAIL"})
        ok = next(s for s in rep["suites"] if s["name"] == "ok")
        self.assertEqual(len(ok["log_sha256"]), 64)
        self.assertEqual(ok["argv"][0], sys.executable)


def fake_fetch(prs, runs=None, fail_repo=None):
    def fetch(args):
        path = args[0]
        if fail_repo and fail_repo in path:
            raise RuntimeError("HTTP 403")
        if "/pulls?" in path:
            return prs.get(path.split("/pulls?")[0].replace("repos/", ""), [])
        if "/check-runs" in path:
            return {"check_runs": runs or []}
        if path.endswith("/status"):
            return {"statuses": []}
        return {"mergeable_state": "clean"}
    return fetch


PR = {"number": 1, "title": "GHOST v2", "draft": True, "user": {"login": "brandonduda8"},
      "head": {"sha": "fe36cf1aaaaaaa"}, "updated_at": "2026-10-31T19:52:47Z",
      "html_url": "https://github.com/brandonduda8/Genesis-os/pull/1"}


class Board(unittest.TestCase):
    def test_prs_are_read_live_and_unreadable_repos_are_reported(self):
        out = bd.collect_prs(("brandonduda8/Genesis-os", "brandonduda8/Agent-x"),
                             fetch=fake_fetch({"brandonduda8/Genesis-os": [PR]}, fail_repo="Agent-x"))
        self.assertEqual(out["status"], "PARTIAL")
        self.assertEqual(out["prs"][0]["mergeable"], "clean")
        self.assertIn("Agent-x", out["errors"][0])
        none = bd.collect_prs(("brandonduda8/X",), fetch=fake_fetch({}, fail_repo="X"))
        self.assertEqual(none["status"], "NOT TESTED")

    def test_audit_5_pr_lists_are_paginated(self):
        many = [dict(PR, number=i, html_url=f"https://github.com/brandonduda8/Genesis-os/pull/{i}") for i in range(1, 151)]

        def fetch(args):
            path = args[0]
            if "/pulls?" in path:
                page = int(path.rsplit("&page=", 1)[1])
                return many[(page - 1) * 100: page * 100]
            if "/check-runs" in path:
                return {"check_runs": []}
            return {"statuses": [], "mergeable_state": "clean"}
        self.assertEqual(len(bd.collect_prs(("brandonduda8/Genesis-os",), fetch=fetch)["prs"]), 150)

    def test_audit_6_per_pr_fetch_failures_demote_live_and_statuses_count(self):
        def fetch(args):
            path = args[0]
            if "/pulls?" in path:
                return [PR]
            if "/check-runs" in path:
                raise RuntimeError("HTTP 502")
            return {"mergeable_state": "clean"}
        out = bd.collect_prs(("brandonduda8/Genesis-os",), fetch=fetch)
        self.assertEqual(out["status"], "PARTIAL")
        self.assertIn("checks", out["errors"][0])

        def fetch2(args):
            path = args[0]
            if "/pulls?" in path:
                return [PR]
            if "/check-runs" in path:
                return {"check_runs": []}
            if path.endswith("/status"):
                return {"statuses": [{"context": "ci/legacy", "state": "failure"}]}
            return {"mergeable_state": "clean"}
        p = bd.collect_prs(("brandonduda8/Genesis-os",), fetch=fetch2)["prs"][0]
        self.assertEqual(bd.ci_label(p["checks"]), "RED: status:ci/legacy")
        self.assertTrue(bd.ci_label({"x": "startup_failure"}).startswith("RED"))

    def test_audit_7_and_9_sources_must_be_urls_and_cells_are_escaped(self):
        p = os.path.join(tempfile.mkdtemp(), "q.json")
        json.dump({"items": [{"who": "brandon", "class": "HANDS", "ask": "sign", "source": "TODO"}]}, open(p, "w"))
        self.assertEqual(len(bd.load_owner_queue(p)["rejected"]), 1)
        self.assertEqual(bd.cell("a | b\nc"), "a \\| b c")

    def test_ci_labels(self):
        self.assertEqual(bd.ci_label({}), "no CI")
        self.assertEqual(bd.ci_label(None), "unknown")
        self.assertEqual(bd.ci_label({"unit": "success", "ui": "success"}), "green")
        self.assertEqual(bd.ci_label({"unit": "failure", "ui": "success"}), "RED: unit")

    def test_owner_items_without_a_source_are_rejected(self):
        p = os.path.join(tempfile.mkdtemp(), "q.json")
        json.dump({"items": [{"who": "brandon", "class": "HANDS", "ask": "sign", "source": "https://x"},
                             {"who": "brandon", "class": "HANDS", "ask": "trust me"}]}, open(p, "w"))
        q = bd.load_owner_queue(p)
        self.assertEqual((len(q["items"]), len(q["rejected"])), (1, 1))

    def test_board_never_invents_revenue_or_health(self):
        md = bd.render_md(bd.collect_prs(("brandonduda8/Genesis-os",), fetch=fake_fetch({"brandonduda8/Genesis-os": [PR]})),
                          None, {"items": [], "rejected": [], "status": "NOT TESTED"})
        self.assertIn("## Revenue", md)
        self.assertIn("NOT TESTED: no verified-payment source", md)
        self.assertIn("NOT TESTED: no baseline record supplied", md)
        self.assertIn("[#1](https://github.com/brandonduda8/Genesis-os/pull/1)", md)
        self.assertNotRegex(md, r"\$\s?\d")  # no dollar figure appears anywhere

    def test_committed_owner_queue_is_valid_and_fully_sourced(self):
        q = bd.load_owner_queue(os.path.join(HERE, "OWNER-QUEUE.json"))
        self.assertEqual(q["rejected"], [])
        self.assertTrue(all(it["source"].startswith("https://github.com/brandonduda8/") for it in q["items"]))


if __name__ == "__main__":
    unittest.main()

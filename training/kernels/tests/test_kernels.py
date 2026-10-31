"""Tests for the ACE/GHOST training kernels (training/kernels/DESIGN.md).

Fast tests (stdlib only): the scorer, build refusals, and the kernel abort paths on tampered or contaminated data.
Slow tests (need torch + transformers + peft + tokenizers): real dry runs of the BUILT main.py on CPU with a tiny
random model. They are skipped with a reason when the stack is absent.
  python3 -m unittest discover -s training/kernels/tests -t training/kernels
"""
import base64
import gzip
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

KROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KROOT, "common"))
import build_kernel as bk  # noqa: E402
import scoring as sc  # noqa: E402

HAVE_STACK = all(importlib.util.find_spec(m) for m in ("torch", "transformers", "peft", "tokenizers"))


def run_kernel(main_py, out, *extra):
    env = dict(os.environ, GENESIS_SKIP_PIP="1")
    return subprocess.run([sys.executable, "-B", main_py, "--dry-run", "--out", out, *extra], capture_output=True,
                          text=True, timeout=1800, env=env)


class Scoring(unittest.TestCase):
    def setUp(self):
        self.ghost = sc.load_jsonl(os.path.join(bk.DATA, "ghost-v1/heldout/ghost-heldout-v1.jsonl"))
        self.ace = sc.load_jsonl(os.path.join(bk.DATA, "ace-v1/heldout/ace-heldout-v1.jsonl"))

    def test_every_heldout_record_has_parsable_ground_truth(self):
        self.assertEqual(sorted(sc.truth_of("ghost", r) for r in self.ghost),
                         ["FAULT", "NONE", "NONE", "NONE", "NONE", "UNKNOWN"])
        self.assertTrue(all(sc.truth_of("ace", r) for r in self.ace))

    def test_perfect_answers_score_one_and_contract_is_required(self):
        perfect = {str(r["id"]): r["response"] for r in self.ghost}
        rep = sc.score_part_a("ghost", self.ghost, perfect)["summary"]
        self.assertEqual((rep["accuracy"], rep["restraint_violations"], rep["unknown_law_violations"]), (1.0, 0, 0))
        prose = {k: "It is probably fine, I think it's NONE." for k in perfect}  # no contract line = miss
        self.assertEqual(sc.score_part_a("ghost", self.ghost, prose)["summary"]["accuracy"], 0.0)

    def test_crying_fault_on_none_and_inventing_a_class_on_unknown_are_flagged(self):
        ans = {}
        for r in self.ghost:
            t = sc.truth_of("ghost", r)
            ans[str(r["id"])] = "FAILURE CLASS: FAULT" if t in ("NONE", "UNKNOWN") else r["response"]
        rep = sc.score_part_a("ghost", self.ghost, ans)
        self.assertEqual(rep["summary"]["restraint_violations"], 4)
        self.assertEqual(rep["summary"]["unknown_law_violations"], 1)
        self.assertTrue(any(i.get("fabrication_event") for i in rep["items"]))
        self.assertIn("EVIDENCE-ONLY", rep["status"])

    def test_ace_verdicts_and_comparison(self):
        right = {str(r["id"]): r["response"] for r in self.ace}
        wrong = {k: "VERDICT: SUBMITTED" for k in right}
        b, t = sc.score_part_a("ace", self.ace, wrong), sc.score_part_a("ace", self.ace, right)
        self.assertEqual(sc.compare(b, t)["tuned_accuracy"], 1.0)
        self.assertGreater(sc.compare(b, t)["delta_points"], 0)


class BuildAndAbort(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def test_build_refuses_a_heldout_whose_hash_differs_from_the_manifest(self):
        saved = bk.KERNELS["ghost-lora-v1"]["heldout_sha256"]
        bk.KERNELS["ghost-lora-v1"]["heldout_sha256"] = "0" * 64
        try:
            with self.assertRaises(bk.BuildRefused):
                bk.build("ghost-lora-v1", self.d)
        finally:
            bk.KERNELS["ghost-lora-v1"]["heldout_sha256"] = saved

    def _rewrite_config(self, main_py, mutate):
        src = open(main_py, encoding="utf-8").read()
        start = src.index("CONFIG = json.loads(") + len("CONFIG = json.loads(")
        end = src.index(")\n", start)
        cfg = json.loads(eval(src[start:end]))  # the literal the builder wrote
        mutate(cfg)
        open(main_py, "w", encoding="utf-8").write(src[:start] + repr(json.dumps(cfg)) + src[end:])

    def test_tampered_embedded_data_aborts_before_any_compute(self):
        info = bk.build("ghost-lora-v1", self.d)
        main_py = os.path.join(info["dir"], "main.py")

        def flip(cfg):
            name = cfg["corpus_file"]
            raw = gzip.decompress(base64.b64decode(cfg["files"][name]["b64gz"])) + b'{"tampered": true}\n'
            cfg["files"][name]["b64gz"] = base64.b64encode(gzip.compress(raw)).decode()
        self._rewrite_config(main_py, flip)
        out = os.path.join(self.d, "out")
        r = run_kernel(main_py, out)
        self.assertEqual(r.returncode, 2, r.stderr[-500:])
        self.assertIn("hash", open(os.path.join(out, "ABORTED.txt")).read())

    def test_heldout_leaking_into_the_corpus_aborts(self):
        info = bk.build("ghost-lora-v1", self.d)
        main_py = os.path.join(info["dir"], "main.py")

        def leak(cfg):
            held = gzip.decompress(base64.b64decode(cfg["files"][cfg["heldout_file"]]["b64gz"]))
            name = cfg["corpus_file"]
            raw = gzip.decompress(base64.b64decode(cfg["files"][name]["b64gz"])) + held.splitlines(True)[0]
            cfg["files"][name] = {"sha256": __import__("hashlib").sha256(raw).hexdigest(), "bytes": len(raw),
                                  "b64gz": base64.b64encode(gzip.compress(raw)).decode()}
        self._rewrite_config(main_py, leak)
        out = os.path.join(self.d, "out2")
        r = run_kernel(main_py, out)
        self.assertEqual(r.returncode, 2, r.stderr[-500:])
        self.assertIn("contamination", open(os.path.join(out, "ABORTED.txt")).read())

    def test_kernel_metadata_targets_the_owner_gpu_lane_with_internet(self):
        info = bk.build("ace-lora-v1", self.d)
        meta = json.load(open(os.path.join(info["dir"], "kernel-metadata.json")))
        self.assertEqual((meta["id"], meta["enable_gpu"], meta["enable_internet"], meta["is_private"]),
                         ("brandonduda/ace-lora-v1", True, True, True))


@unittest.skipUnless(HAVE_STACK, "needs torch+transformers+peft+tokenizers for the CPU dry run")
class DryRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp()

    def test_train_mode_seals_base_before_training_and_reports_evidence_only(self):
        info = bk.build("ghost-lora-v1", self.d)
        out = os.path.join(self.d, "train-out")
        r = run_kernel(os.path.join(info["dir"], "main.py"), out)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        m = json.load(open(os.path.join(out, "run_manifest.json")))
        kinds = [e["kind"] for e in m["events"]]
        self.assertEqual(kinds, ["data_verified", "base_sealed", "trained", "tuned_sealed", "done"])
        self.assertEqual(m["events"][0]["normalized_list_instructions"], ["GHOST-C-019", "GHOST-HELDOUT-004"])
        sealed = next(e for e in m["events"] if e["kind"] == "base_sealed")["sha256"]
        self.assertEqual(sealed, sc.sha256_file(os.path.join(out, "base_partA.jsonl")))
        rep = json.load(open(os.path.join(out, "partA_report.json")))
        self.assertIn("EVIDENCE-ONLY", rep["status"])
        self.assertTrue(rep["adapter_sha256"])
        self.assertEqual(rep["tuned"]["summary"]["cases"], 6)

    def test_h2h_mode_never_touches_the_heldout_set(self):
        info = bk.build("ghost-h2h-v1", self.d)
        out = os.path.join(self.d, "h2h-out")
        r = run_kernel(os.path.join(info["dir"], "main.py"), out)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        rep = json.load(open(os.path.join(out, "h2h_report.json")))
        self.assertEqual(len(rep["ranking"]), len(bk.CANDIDATES))
        held_ids = {str(r["id"]) for r in sc.load_jsonl(os.path.join(bk.DATA, "ghost-v1/heldout/ghost-heldout-v1.jsonl"))}
        for name in os.listdir(out):
            if name.startswith("h2h_") and name.endswith(".jsonl"):
                ids = {json.loads(l)["id"] for l in open(os.path.join(out, name))}
                self.assertFalse(ids & held_ids, f"{name} scored held-out ids")


if __name__ == "__main__":
    unittest.main()


class CommittedBuildIsFresh(unittest.TestCase):
    def test_committed_kernels_match_a_fresh_build(self):
        committed = json.load(open(os.path.join(KROOT, "build", "BUILD.json")))["kernels"]
        d = tempfile.mkdtemp()
        for name in sorted(bk.KERNELS):
            info = bk.build(name, d, committed[name]["base_model"])
            self.assertEqual(info["main_sha256"], committed[name]["main_sha256"],
                             f"{name}: build/ is stale — run build_kernel.py --all")
            on_disk = sc.sha256_file(os.path.join(KROOT, "build", name, "main.py"))
            self.assertEqual(on_disk, committed[name]["main_sha256"], f"{name}: build/{name}/main.py edited by hand")

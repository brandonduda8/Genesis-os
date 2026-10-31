"""TS-001 prevention tests (WO-MASTER-TROUBLESHOOTER-001): dataset builders and the data they wrote.

  python3 -m unittest discover -s training/datasets/tests -t training/datasets
"""
import ast
import glob
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

DATASETS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, DATASETS)
from frozen_guard import FrozenHeldoutChange, write_heldout  # noqa: E402

TEXT_FIELDS = ("instruction", "response", "text")
# Known v1 records with a list-shaped instruction (the TS-001 tuple bug). HELDOUT-004 is in a FROZEN set and stays as
# frozen. GHOST-C-019 disappears when Zane rebuilds the training split with the fixed builder. This list may only
# shrink: a NEW list-valued field anywhere fails the test.
KNOWN_V1 = {("ghost-v1", "GHOST-HELDOUT-004"), ("ghost-v1", "GHOST-C-019")}
FROZEN = {"ghost-v1/heldout/ghost-heldout-v1.jsonl": "74d68f5329388dbc1f9162f6052bb4f4cb3ecd04303bfab1823d428c1a518f2a",
          "ace-v1/heldout/ace-heldout-v1.jsonl": "23452d59cdcbf897a54bbdb3fbea8d89a449efe6c7d6f543b906fe64e91cd632"}


class Builders(unittest.TestCase):
    def test_no_builder_writes_a_tuple_into_a_text_field(self):
        """The mechanism: `("..." f"...",)` is a 1-tuple, and json.dumps writes it as a list."""
        bad = []
        for path in glob.glob(os.path.join(DATASETS, "*", "build_dataset.py")):
            for node in ast.walk(ast.parse(open(path).read(), path)):
                if isinstance(node, ast.Dict):
                    for k, v in zip(node.keys, node.values):
                        if isinstance(k, ast.Constant) and k.value in TEXT_FIELDS + ("detail", "source") \
                                and isinstance(v, ast.Tuple):
                            bad.append(f"{os.path.relpath(path, DATASETS)}:{v.lineno} {k.value}")
        self.assertEqual(bad, [])

    def test_every_builder_that_writes_a_heldout_goes_through_the_guard(self):
        for path in glob.glob(os.path.join(DATASETS, "*", "build_dataset.py")):
            src = open(path).read()
            if "heldout" in src and "held_path" in src:
                self.assertIn("write_heldout(held_path", src, path)
                self.assertNotIn("held_path.write_text(", src, path)

    def test_text_fields_are_strings_except_the_known_shrinking_v1_list(self):
        found = set()
        for path in glob.glob(os.path.join(DATASETS, "*", "*", "*.jsonl")):
            line = os.path.relpath(path, DATASETS).split(os.sep)[0]
            for l in open(path, encoding="utf-8"):
                if not l.strip():
                    continue
                r = json.loads(l)
                for f in TEXT_FIELDS:
                    if f in r and not isinstance(r[f], str):
                        found.add((line, r.get("id")))
        self.assertTrue(found <= KNOWN_V1, f"new non-string text fields: {sorted(found - KNOWN_V1)}")

    def test_frozen_heldouts_still_match_their_manifest_hashes(self):
        for rel, sha in FROZEN.items():
            got = hashlib.sha256(open(os.path.join(DATASETS, rel), "rb").read()).hexdigest()
            self.assertEqual(got, sha, rel)


class FrozenGuard(unittest.TestCase):
    def setUp(self):
        self.p = Path(tempfile.mkdtemp()) / "heldout.jsonl"
        self.p.write_text("frozen\n")
        self.sha = hashlib.sha256(b"frozen\n").hexdigest()

    def test_identical_rebuild_is_a_no_op(self):
        self.assertEqual(write_heldout(self.p, "frozen\n", self.sha, argv=[]), self.sha)

    def test_a_change_to_a_frozen_file_is_refused_and_the_file_is_untouched(self):
        with self.assertRaises(FrozenHeldoutChange) as cm:
            write_heldout(self.p, "different\n", self.sha, argv=["build_dataset.py"])
        self.assertIn("--refreeze", str(cm.exception))
        self.assertEqual(self.p.read_text(), "frozen\n")

    def test_explicit_refreeze_writes_and_returns_the_new_hash(self):
        got = write_heldout(self.p, "v2\n", self.sha, argv=["build_dataset.py", "--refreeze"])
        self.assertEqual(got, hashlib.sha256(b"v2\n").hexdigest())

    def test_first_build_or_unfrozen_file_writes_normally(self):
        fresh = self.p.parent / "new.jsonl"
        self.assertEqual(write_heldout(fresh, "x\n", self.sha, argv=[]), hashlib.sha256(b"x\n").hexdigest())


if __name__ == "__main__":
    unittest.main()
